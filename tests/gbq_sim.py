"""GBS-4 fixtures — ZoneStrategyGBPJPY position size: fixed (simple-interest) loss budget / fixed SL distance.

  GQ : static — Strategy == gbs_build.build(); strip_qty gives the dedfbbc Strategy byte for byte (signals, order prices,
       SL / TP, session, Track limits and alert conditions unchanged apart from the size); Visual / Library / import /3,
       Gold and USDJPY unchanged; strategy(): initial capital 300,000, currency JPY, no margin parameter added (order
       model settings unchanged); inputs 300,000 / 3 % / 100,000 / 0.01; f_stQty never reads equity / P&L; both entries
       pass qty = pQty computed from the reference price already used for the RR pre-check and the fixed SL; no order when
       pQty is na; the quantity is not changed after the fill; confirmed alert uses the same pQty, provisional alert a
       reference value with the same function; no request / loop added
  GM : model — a Pine port of f_stQty: 0.30 円 -> 30,000 units (0.30 lot, 9,000 円), 0.28 円 -> 32,000 (8,960 円), Long /
       Short, float distance 190.150 - 189.850, truncation (0.047 -> 0.04 lot), minimum lot boundary, invalid SL, loss
       <= budget and maximality on a distance grid, budget unchanged after profits / losses, no lot double conversion

Evidence class: PINE_NOT_VERIFIED. TradingView compile / Strategy Tester (fills, gaps, slippage, commission) external.
"""
import math
import os
import random
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gbs_build as gs          # noqa: E402
import gbj_build as gb          # noqa: E402
import gbe_build as ge          # noqa: E402
import fvg_re10045_sim as fr    # noqa: E402

ROOT = gs.ROOT
PREV = "dedfbbc"
rd = lambda p: open(os.path.join(ROOT, p), encoding="utf-8").read() if os.path.exists(os.path.join(ROOT, p)) else ""
show = lambda p, rev=PREV: subprocess.run(["git", "-C", ROOT, "show", f"{rev}:{p}"], capture_output=True, text=True).stdout
GBS, GBS0 = rd(gs.GBS_PATH), show(gs.GBS_PATH)
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


def code_only(src):
    return "\n".join(l for l in src.split("\n") if not l.lstrip().startswith("//"))


def func(src, head):
    i = src.index("\n" + head) + 1
    m = re.search(r"\n(?=\S)", src[i + len(head):])
    return src[i:i + len(head) + m.start() + 1]


PROTECTED = ["ZoneVisualGBPJPY.pine", "ZoneEnginePracticalGBPJPY.pine", "ZoneEnginePracticalSwingMax.pine",
             "ZoneVisualPractical.pine", "ZoneStrategyXAU.pine", "ZoneVisualUSDJPY.pine", "ZoneStrategyUSDJPY.pine"]


def gate_static():
    check("GQ-01 Strategy == gbs_build.build() (rebuild identical); reverting the position-size edits gives the " + PREV
          + " Strategy byte for byte: signals, order prices, SL / TP, session, Track limits and alert conditions are "
          "unchanged apart from the size", bool(GBS) and gs.build() == GBS and gs.build() == gs.build()
          and gs.strip_qty(GBS) == GBS0 and bool(GBS0))
    G4 = gs.strip_msg(GBS) or ""     # GBS-5 / GBS-6 (alert text, labels) reverted: these checks pin GBS-4 (gbn_sim pins 5 / 6)
    decl = G4[G4.index("strategy(\n"):G4.index(")\n", G4.index("strategy(\n")) + 2]
    decl0 = GBS0[GBS0.index("strategy(\n"):GBS0.index(")\n", GBS0.index("strategy(\n")) + 2]
    check("GQ-02 strategy(): initial capital 300,000, currency JPY; calc_on_every_tick / process_orders_on_close / "
          "pyramiding / default qty unchanged; no margin_long / margin_short added (margin left at the Pine v5 default)",
          "initial_capital        = 300000," in decl and "currency               = currency.JPY," in decl
          and decl.replace("     initial_capital        = 300000,\n     currency               = currency.JPY,\n",
                           "     initial_capital        = 10000,\n") == decl0
          and "margin" not in code_only(G4), decl)
    inp = lambda n: (re.search(r"^" + n + r"\s*=\s*input\.\w+\(([^,]+),", G4, re.M) or [None, None])[1]
    q = func(G4, "f_stQty(")
    check("GQ-03 inputs (changeable) 元金基準額 300,000 / 損失予算 3 % / 1 lot 100,000 通貨 / lot 刻み 0.01; budget = base x "
          "% / 100 fixed (f_stQty and the budget never read equity, net profit or position: simple interest); "
          "qty = floor(budget / (distance x pointvalue x step units) + 1e-9) x step units (1e-9 absorbs float noise only), na "
          "below one step or for an "
          "invalid distance", [inp(n) for n in ("stCapBase", "stRiskPct", "stLotUnits", "stLotStep")]
          == ["300000.0", "3.0", "100000.0", "0.01"]
          and "float stBudget = stCapBase * stRiskPct / 100.0" in G4
          and "    float dist  = side == 1 ? ref - sl : sl - ref\n" in q
          and "    float stepU = stLotUnits * stLotStep\n" in q
          and "if not na(dist) and dist > 0 and syminfo.pointvalue > 0 and stepU > 0 and stBudget > 0" in q
          and "math.floor(stBudget / (dist * syminfo.pointvalue * stepU) + 1e-9)" in q
          and "        if n >= 1\n            q := n * stepU\n" in q
          and not re.search(r"strategy\.(equity|netprofit|initial_capital|position_size|openprofit)", q + "stBudget"))
    ob = G4[G4.index("            float  pQty = f_stQty(side, ref, pSL)"):G4.index("    stPrev := cur\n")]
    check("GQ-04 orders: pQty from the same reference price as the RR pre-check (ref = A limit / B, C, D confirmed 5M "
          "close) and the fixed SL; no order when it is na; both strategy.entry calls pass qty = pQty (units, not lots); "
          "strategy.exit unchanged (whole position); qty is never set again after the fill",
          "            float  ref = stModeA ? pL : close\n" in G4 and "if not skipRef and not na(pQty)\n" in ob
          and ob.count("qty = pQty") == 2 and "strategy.exit(oXid, oEid, stop = oSL)\n" in ob
          and len(re.findall(r"\bqty\s*=", code_only(G4))) == 2 and "strategy.order(" not in G4
          and "pQty * stLotUnits" not in G4 and "stLotUnits * pQty" not in G4)
    pv = G4[G4.index("        [pSide, pPx, pSL] = f_stProvEval()\n"):]
    check("GQ-05 alerts: the confirmed alert carries the order's pQty (lot = qty / units per lot) in the order branch; the "
          "provisional alert computes a reference size with the same function (labelled 参考値), is sent only when that "
          "size is valid like the order, and keeps its once-per-bar state; message strings only inside alert()",
          'alert(f_stAlertMsg("確定", side, stModeA ? oL : close, oSL, pQty), alert.freq_all)' in ob
          and "float pvQty = pSide != 0 ? f_stQty(pSide, pPx, pSL) : na" in pv
          and "if pSide != 0 and not na(pvQty)\n            stProvBar := bar_index\n" in pv
          and '"\\nLot: " + f_num(qty / stLotUnits, "0.00")' in G4 and "参考値" in G4
          and code_only(G4).count("f_stAlertMsg(") == 3)
    req = lambda s: re.findall(r"request\.\w+\(.*$", code_only(s), re.M)
    cnt = lambda s, p: len(re.findall(p, code_only(s)))
    check("GQ-06 lightweight: requests (11), zone loops, for-loops, drawing and plots unchanged (the size is two "
          "multiplications and a floor in the existing order branch); RE10045 lint clean",
          req(G4) == req(GBS0) and all(cnt(G4, p) == cnt(GBS0, p) for p in (r"zn\.zoneAt\(", r"\bfor\b", r"\bwhile\b",
                                                                          r"\b(box|label|line|table)\.new\(", r"\bplot\("))
          and fr.lint_eager_guards(code_only(G4)) == [])
    d = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", PREV, "--"] + PROTECTED, capture_output=True, text=True)
    check("GQ-07 Visual, Library (/3 source), shared /6, Gold and USDJPY unchanged vs " + PREV + "; import stays /3",
          d.returncode == 0 and __import__("uj_build").drop_uj(d.stdout.split(), PREV) == [] and re.findall(r"^import .*$", G4, re.M) == [ge.IMPORT_GBE.strip()],
          d.stdout)


# ---- model --------------------------------------------------------------------------------------------------------------
def qty(side, ref, sl, base=300000.0, pct=3.0, units=100000.0, step=0.01, pv=1.0):
    """Pine port of f_stQty."""
    budget = base * pct / 100.0
    if ref is None or sl is None:
        return None
    dist = ref - sl if side == 1 else sl - ref
    step_u = units * step
    if not (dist > 0 and pv > 0 and step_u > 0 and budget > 0):
        return None
    n = math.floor(budget / (dist * pv * step_u) + 1e-9)
    return n * step_u if n >= 1 else None


def gate_model():
    q30 = qty(1, 190.300, 190.000)
    check("GM SL distance 0.30 円, pointvalue 1 -> 30,000 units = 0.30 lot, loss 9,000 円",
          q30 == 30000.0 and q30 / 100000 == 0.30 and abs(q30 * 0.30 - 9000) < 1e-6, str(q30))
    q28 = qty(1, 190.280, 190.000)
    check("GM SL distance 0.28 円 -> 32,000 units = 0.32 lot, loss 8,960 円 (0.33 lot would be 9,240 円)",
          q28 == 32000.0 and abs(q28 * 0.28 - 8960) < 1e-6 and (q28 + 1000) * 0.28 > 9000, str(q28))
    check("GM Long and Short are symmetric (Long 190.150 / SL 189.850, Short 189.850 / SL 190.150 -> 30,000); the float "
          "distance 190.150 - 189.850 = 0.30000000000001 still gives 30,000 (not 29,000)",
          qty(1, 190.150, 189.850) == qty(-1, 189.850, 190.150) == 30000.0 and 190.150 - 189.850 != 0.30)
    d47 = 9000 / 4700.0
    check("GM truncation: raw 0.047 lot (4,700 units, distance 1.9149 円) -> 0.04 lot (4,000 units), never rounded up",
          qty(1, 190.0 + d47, 190.0) == 4000.0 and qty(1, 190.0 + 9000 / 4999.0, 190.0) == 4000.0)
    check("GM minimum lot: distance 9.00 円 -> exactly 0.01 lot (1,000 units); 9.01 円 -> below 0.01 lot -> no order",
          qty(1, 199.0, 190.0) == 1000.0 and qty(1, 199.01, 190.0) is None)
    check("GM invalid SL: distance 0, SL on the wrong side (Long SL above / Short SL below), na price -> no order",
          qty(1, 190.0, 190.0) is None and qty(1, 190.0, 190.1) is None and qty(-1, 190.0, 189.9) is None
          and qty(1, None, 190.0) is None and qty(1, 190.0, None) is None)
    rng = random.Random(3)
    bad = []
    for k in range(1, 3001):
        for off in (0.0, rng.random() * 0.001):           # on and off the 0.001 grid (MA-based zone edges)
            ref, sl = 190.0 + k / 1000.0, 190.0 - off
            q = qty(1, ref, sl)
            dist = ref - sl
            if q is None:
                if 9000 / dist >= 1000 * (1 + 1e-9):
                    bad.append(("none", k, off))
                continue
            if q * dist > 9000 * (1 + 2e-9) or (q + 1000) * dist <= 9000 * (1 - 1e-9):
                bad.append((k, off, q))
    check("GM distances 0.001-3.000 円 on / off the price grid (random off-grid SL): computed loss <= 9,000 円 (float noise "
          "<= 2e-9 relative, < 0.0001 円) and one more "
          "0.01 lot would exceed it (largest allowed size)", bad == [], str(bad[:5]))
    eq, out = 300000.0, []
    for pnl in (+25000.0, -9000.0, -9000.0, +40000.0):
        out.append(qty(1, 190.300, 190.000))
        eq += pnl
    check("GM simple interest: after profits and losses the budget stays 9,000 円 (same distance -> same 30,000 units; "
          "f_stQty has no equity input)", out == [30000.0] * 4)
    check("GM no double lot conversion: pointvalue 1 means 1 unit x 1 円 move = 1 円, so 0.30 lot is passed as 30,000 "
          "units (passing lots x 100,000 again would be 3,000,000,000 units)", qty(1, 190.300, 190.000) == 30000.0
          and qty(1, 190.300, 190.000, pv=100000.0) is None)


def main():
    for g in (gate_static, gate_model):
        try:
            g()
        except Exception:
            import traceback
            check(f"{g.__name__} completed without error", False, traceback.format_exc()[-900:])
    fails = 0
    for n, ok, d in RESULTS:
        fails += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {n[:150].ljust(150)}  {'' if ok else d}")
    print(f"\n{len(RESULTS) - fails}/{len(RESULTS)} passed  [PINE_NOT_VERIFIED: exact build / static / model]")
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
