"""UJ-1 fixtures — USDJPY dedicated Engine (ZoneEnginePracticalUSDJPY) and GBPJPY position sizing in ZoneStrategyUSDJPY.

  US : static — the Engine == ZoneEnginePracticalSwingMax.pine (the published ZoneEnginePractical/6 source) except the
       library name, same exports; Visual / Strategy rebuild from their pre-UJ-1 text (3568c05) and strip back byte for
       byte; Visual delta = import + Zone Half Width 0.03 (user decision), Strategy delta = import + sizing; both import
       ZoneEnginePracticalUSDJPY/1 and share every Zone input / ZoneCfg / feed / FVG block; the sizing code equals the
       GBPJPY f_stQty and is used for both the limit and the market entry, before any order / Track state is written;
       every other Strategy setting unchanged (D, Long Only, SL Buffer, Zone TP, RR, BE, session, calc_on_every_tick);
       RN stays OFF; only the USDJPY files and the exactly-adapted older fixtures change vs 3568c05
  UM : model (Python port, not a TradingView run) — quantity: 9,000 JPY budget, pointvalue 1: 0.10 -> 90,000 (0.90 lot),
       0.13 -> 69,000 (0.69 lot, planned loss 8,970); Long / Short, floor, invalid, below one lot step

Evidence class: PINE_NOT_VERIFIED (library publish, TradingView compile / backtest external).
"""
import math
import os
import random
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import uj_build as ub            # noqa: E402
import eu_sim as es              # noqa: E402
import fvg_re10045_sim as fr     # noqa: E402

ROOT = ub.ROOT
rd = lambda p: open(os.path.join(ROOT, p), encoding="utf-8").read()
git = lambda *a: subprocess.run(["git", "-C", ROOT] + list(a), capture_output=True, text=True).stdout
code_only, input_decls, input_values, func, seg = es.code_only, es.input_decls, es.input_values, es.func, es.seg
E6, EU = rd(ub.ENG_SRC), rd(ub.ENG_PATH)
V0, S0 = ub.base(ub.VIS_PATH), ub.base(ub.STR_PATH)
V, S = rd(ub.VIS_PATH), rd(ub.STR_PATH)
GBS = rd("ZoneStrategyGBPJPY.pine")
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


SIZE_INPUTS = {"stCapBase", "stRiskPct", "stLotUnits", "stLotStep"}


def gate_static():
    ev = git("show", "67f8fd2", "--", "ZoneVisualPractical.pine")
    check("US-01 /6 source evidence: ZoneEnginePracticalSwingMax.pine was created in 110e5b0 (SW-1) and is unchanged since; "
          "the next commit 67f8fd2 switched the import /5 -> /6 ('Swing max-score, SW-1'); it is what gbe_build already uses",
          git("log", "--format=%h", "--", ub.ENG_SRC).split() == ["110e5b0"]
          and "+import sekine3310/ZoneEnginePractical/6 as zn" in ev and "-import sekine3310/ZoneEnginePractical/5 as zn" in ev
          and git("log", "-1", "--format=%h", "67f8fd2^") .strip() == "110e5b0" and __import__("gbe_build").SRC_PATH == ub.ENG_SRC)
    exports = lambda t: re.findall(r"^export .*$", t, re.M)
    check("US-02 Engine: ZoneEnginePracticalUSDJPY.pine == build from the /6 source; code identical except the library name "
          "(Zone generation, scoring, Break / Flip, Accum detection, RN unchanged); every export identical",
          ub.build_engine() == EU and ub.strip_engine(EU) == E6
          and code_only(EU).replace('library("ZoneEnginePracticalUSDJPY", overlay = true)', 'library("ZoneEnginePractical", overlay = true)') == code_only(E6)
          and exports(EU) == exports(E6) and len(exports(EU)) > 30)
    check("US-03 Visual / Strategy rebuild from their pre-UJ-1 text (3568c05) and strip back byte for byte",
          ub.build_visual() == V and ub.build_strategy() == S and ub.strip_visual(V) == V0 and ub.strip_strategy(S) == S0
          and all(k in ("header", "name", "import", "default", "size") for k, _, _ in ub.ENGINE_EDITS + ub.VISUAL_EDITS + ub.STRATEGY_EDITS))
    cv = es.changed_code(V0, V)
    check("US-04 Visual code delta = the import and the Zone Half Width default 0.05 -> 0.03 (user decision)",
          sorted(cv) == sorted([ub.IMPORT_6.strip(), ub.IMPORT_UJ.strip(),
                                'zoneHalfWidth = input.float(0.05, "Zone Half Width (円)", minval = 0.005, step = 0.005, group = G_ZONE,',
                                'zoneHalfWidth = input.float(0.03, "Zone Half Width (円)", minval = 0.005, step = 0.005, group = G_ZONE,']), str(cv))
    size_lines = [l.strip() for l in code_only(ub.QTY_INPUTS_UJ).split("\n") if l.strip()] + [
        "initial_capital        = 10000,", "initial_capital        = 300000,", "currency               = currency.JPY,",
        "float  pQty = f_stQty(side, ref, pSL)", "if not skipRef", "if not skipRef and not na(pQty)",
        "strategy.entry(oEid, side == 1 ? strategy.long : strategy.short, limit = oL)",
        "strategy.entry(oEid, side == 1 ? strategy.long : strategy.short, qty = pQty, limit = oL)",
        "strategy.entry(oEid, side == 1 ? strategy.long : strategy.short)",
        "strategy.entry(oEid, side == 1 ? strategy.long : strategy.short, qty = pQty)",
        ub.IMPORT_6.strip(), ub.IMPORT_UJ.strip()]
    cs = es.changed_code(S0, S)
    check("US-05 Strategy code delta = the import and the sizing (capital / currency, sizing inputs + f_stQty, the pQty gate, "
          "qty on both entries) only", cs and all(l in size_lines or l == "" for l in cs),
          str([l for l in cs if l not in size_lines and l != ""][:4]))
    vd, sd = input_decls(V), input_decls(S)
    zone_names = set(input_decls(S[:S.index("// ==== ZONE Strategy · Zone evaluation (begin)")]))
    cfg = lambda t: re.findall(r"^zoneCfg\.\w+\s*:=.*$", t, re.M)
    feed = lambda t: code_only(seg(t, "// ---- 3.2 Zone Engine Feed", "//  ★ 5分足専用: 5分足以外では zn.update"))
    fvg = lambda t: code_only(seg(t, "// ==== FVG Batch A (begin)", "// ==== FVG Batch A (end)"))
    check("US-06 Visual / Strategy: both import ZoneEnginePracticalUSDJPY/1; identical Zone input declarations (Half Width "
          "0.03 in both), ZoneCfg assignments, feeds (10 request.security) and FVG Batch A",
          re.findall(r"^import .*$", V + S, re.M) == [ub.IMPORT_UJ.strip()] * 2
          and zone_names == set(vd) - es.DISPLAY_INPUTS and all(vd[n] == sd[n] for n in zone_names)
          and input_values(S)["zoneHalfWidth"] == "0.03" and cfg(V) == cfg(S) and feed(V) == feed(S) and fvg(V) == fvg(S)
          and len(re.findall(r"request\.security\(", feed(S) + fvg(S))) == 10, str([n for n in zone_names if vd.get(n) != sd.get(n)]))
    q, qg = func(S, "f_stQty(int side, float ref, float sl) =>"), func(GBS, "f_stQty(int side, float ref, float sl) =>")
    v = input_values(S)
    check("US-07 sizing = the GBPJPY version: f_stQty code identical (budget = 元金基準額 x 損失率, fixed / simple; "
          "floor(budget / (distance x syminfo.pointvalue x lot step units)); invalid / wrong side / zero / below one step -> "
          "na); strategy(initial_capital 300000, currency JPY); 300,000 / 3 % / 100,000 / 0.01; no FX conversion, no fixed "
          "pointvalue",
          code_only(q) == code_only(qg) and "float stBudget = stCapBase * stRiskPct / 100.0" in S
          and "     initial_capital        = 300000,\n     currency               = currency.JPY,\n" in S
          and (v["stCapBase"], v["stRiskPct"], v["stLotUnits"], v["stLotStep"]) == ("300000.0", "3.0", "100000.0", "0.01")
          and "convert_to_symbol" not in S and "syminfo.pointvalue" in q and not re.search(r"pointvalue\s*=", code_only(S)))
    order = code_only(seg(S, "            float  pQty = f_stQty(side, ref, pSL)", "    stPrev := cur"))
    check("US-08 every order path uses the same quantity: the limit (A) and market (B / C / D) entries both pass qty = pQty from "
          "the same call with ref = A limit / B, C, D confirmed close; an invalid quantity skips the whole branch before "
          "oSeq / oState / order ids are written (the Track is marked used only on a fill, unchanged)",
          code_only(S).count("strategy.entry(") == 2 and code_only(S).count("qty = pQty") == 2 and code_only(S).count("f_stQty(") == 2
          and "float  ref = stModeA ? pL : close" in S and order.index("if not skipRef and not na(pQty)") < order.index("oSeq    += 1")
          < order.index("oState  := 1") < order.index("strategy.entry(")
          and "map.put(stUsed, oTrack, true)" in seg(S, "    // (1) 発注済み Entry", "    // (2) Zone の走査"))
    v0 = input_values(S0)
    keep = [n for n in v0 if v0[n] != v.get(n) or (n not in SIZE_INPUTS and input_decls(S0)[n] != input_decls(S)[n])]
    check("US-09 every other Strategy setting unchanged: Entry D, Long Only (user decision), SL Buffer 0.05, Zone TP OFF, RR 1.3, "
          "BE OFF, session 09:00-02:00, Zone / Source / slope / Accum inputs; calc_on_every_tick true, process_orders_on_close "
          "false; confirmed-bar Engine update; the alert code untouched",
          not keep and (v["stMode"], v["stDir"], v["stBuffer"], v["stRR"], v["stTpZone"], v["stBE"]) == (
              '"D: 1M BOS Rebound"', '"Long Only"', "0.05", "1.3", "false", "false")
          and "calc_on_every_tick     = true," in S and "process_orders_on_close = false," in S
          and "if is5mChart and barstate.isconfirmed\n    zoneCountNow := zn.update(zoneEng, zoneCfg, zoneFeed)" in S
          and func(S, "f_stAlertMsg(") == func(S0, "f_stAlertMsg("), str(keep))
    check("US-10 RN stays OFF with its existing gate (no USDJPY RN tuning)",
          all(input_values(t)["enableRn"] == "false" and 'enableRn and syminfo.ticker == "XAUUSD"' in t for t in (V, S)))
    req = lambda t: re.findall(r"request\.\w+\(", code_only(t))
    check("US-11 no extra request / loop; RE10045 lint clean", req(V) == req(V0) and req(S) == req(S0)
          and all(fr.lint_eager_guards(code_only(t)) == [] for t in (EU, V, S)))
    mod = git("diff", "--name-only", "--diff-filter=MDR", ub.BASE_REV, "--").split()
    rest = [m for m in mod if m not in ub.UJ_FILES and not ub.test_ok(m)]
    check("US-12 vs 3568c05: only the USDJPY Visual / Strategy change among existing Pine files (exactly by UJ-1); every "
          "modified older fixture differs only by its recorded TEST_ADAPT edits; GBPJPY / EURUSD / GBPUSD / BTC / Gold "
          "Pine files and the shared Engines untouched", set(ub.UJ_FILES) <= set(mod) and not rest
          and all(ub.uj_ok(f, ub.BASE_REV) for f in ub.UJ_FILES) and not [m for m in mod if m.endswith(".pine") and m not in ub.UJ_FILES],
          str(rest))
    m = S.replace("strategy.entry(oEid, side == 1 ? strategy.long : strategy.short, qty = pQty)\n",
                  "strategy.entry(oEid, side == 1 ? strategy.long : strategy.short)\n")
    check("US-13 mutation: dropping qty on the market entry is detected", code_only(m).count("qty = pQty") == 1
          and ub.strip_strategy(m) is None)


def qty(side, ref, sl, budget=9000.0, pv=1.0, units=100000.0, step=0.01):
    """port of f_stQty (GBPJPY = USDJPY)."""
    dist = (ref - sl) if side == 1 else (sl - ref)
    step_u = units * step
    if dist is None or dist <= 0 or pv is None or pv <= 0 or step_u <= 0 or budget <= 0:
        return None
    n = math.floor(budget / (dist * pv * step_u) + 1e-9)
    return n * step_u if n >= 1 else None


def gate_model():
    a, b = qty(1, 150.000, 149.900), qty(-1, 150.000, 150.130)
    check("UM-01 [model] budget 9,000 JPY, pointvalue 1: SL 0.10 -> 90,000 units = 0.90 lot (Long); SL 0.13 -> 69,000 units = "
          "0.69 lot, planned loss 8,970 JPY (Short; floor of 69.23 steps)",
          round(a) == 90000 and round(b) == 69000 and round(b * 0.13) == 8970, str((a, b)))
    inval = [qty(1, 150.0, 150.0), qty(1, 149.9, 150.0), qty(-1, 150.0, 149.9), qty(1, 150.0, 149.9, pv=0.0),
             qty(1, 150.0, 140.0), qty(1, 150.0, 149.9, budget=0.0)]
    check("UM-02 [model] no order: zero distance, SL on the wrong side (Long / Short), pointvalue 0, below one lot step "
          "(SL 10.0 -> 0.9 step), zero budget", all(q is None for q in inval), str(inval))
    rng, bad = random.Random(3), []
    for _ in range(100000):
        side, dist = rng.choice([1, -1]), round(rng.uniform(0.001, 2.0), 3)
        q = qty(side, 150.0, 150.0 - side * dist)
        if q is not None:
            n = round(q / 1000)
            if abs(q / 1000 - n) > 1e-9 or q * dist > 9000 * (1 + 1e-9) or (n + 1) * 1000 * dist <= 9000 * (1 - 1e-9):
                bad.append((side, dist, q))
        elif math.floor(9000 / (dist * 1000) * (1 - 1e-12)) >= 1:
            bad.append(("missed", side, dist))
    check("UM-03 [model] 100k random Long / Short cases: quantity on the 0.01-lot grid, planned loss <= 9,000 JPY (1e-9 slack "
          "of the floor), largest such quantity", not bad, str(bad[:3]))


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
