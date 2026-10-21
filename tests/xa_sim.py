"""XA-1 / XA-2 / XA-3 fixtures — Gold comparison defaults in ZoneStrategyXAU.pine (ZONE-ST) and ZoneVisualPractical.pine (ZONE-P),
and the XA-2 position size (300,000 JPY base x 3 % = fixed 9,000 JPY planned-loss budget, simple interest) in ZONE-ST.

  XS : static — both files rebuild from f253890 + the XA-1 edits and strip back byte for byte; the code delta is only the
       specified input defaults; the table (Zone Half Width 6, Cluster 5, Break 10, Flip 10 in both; Strategy Entry C, Short
       Only, SL Buffer 3, RR 1.5, opposite-zone TP OFF, breakeven OFF); Visual / Strategy shared Zone inputs and ZoneCfg
       identical; every other input, strategy() (capital 10,000, fixed qty 1, no commission / slippage / margin added),
       Engine import /6, logic unchanged; vs f253890 only these two Pine files (exactly) and exactly-recorded test edits
       (XS runs on the XA-1 layer: the Strategy with only XA-2 reverted == commit 2732772)
  XQ : XA-2 — the Strategy == the XA-1 file + the XA-2 edits and strips back to 2732772 byte for byte; the code delta is only
       initial capital 300,000 / currency JPY, the sizing inputs and f_stQty, the pQty gate and qty on both entries;
       f_stQty uses strategy.convert_to_symbol and syminfo.pointvalue (no fixed USDJPY / equity link); the gate sits before
       every order-state change; Track use stays fill-only; Visual / other inputs / fees / requests unchanged; a Python
       model of f_stQty (USDJPY 150 test assumption -> 60 USD): SL 20 -> 0.03 lot qty 3 loss 60, SL 25 -> 0.02 lot qty 2
       loss 50, SL > 60 -> no order, pointvalue 10 -> qty 0.3, Long / Short, na, invalid values, step boundaries, random
       property (planned loss <= budget, one more step would exceed it)  (XQ runs on the XA-1 + XA-2 layer == 69e6f0c)
  XT : XA-3 — the Gold Short adopted defaults (検証継続中の初期値): both files == the 69e6f0c files + the XA-3 edits and strip back
       to them byte for byte; the code delta is only Flip 10 -> 5, MA base 2 -> 3, Slope aggregation Sum -> Max (both) and
       SL Buffer 3 -> 1.5 (Strategy); every table value; Visual / Strategy Zone parity; no Strategy trading input in the
       Visual; sizing (XA-2) / logic / other inputs / breakeven trigger / requests / Engine import unchanged; header wording

Evidence class: PINE_NOT_VERIFIED (TradingView backtest not reproduced locally).
"""
import math
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xa_build as xb            # noqa: E402
import eu_sim as es              # noqa: E402

ROOT = xb.ROOT
rd = lambda p: open(os.path.join(ROOT, p), encoding="utf-8").read()
git = lambda *a: subprocess.run(["git", "-C", ROOT] + list(a), capture_output=True, text=True).stdout
code_only, input_decls, input_values, func, seg = es.code_only, es.input_decls, es.input_values, es.func, es.seg
VF, SF = rd(xb.VIS_PATH), rd(xb.STR_PATH)
V = xb.strip_visual3(VF) or ""                         # XA-1 layer (XA-3 reverted exactly)
S2 = xb.strip_strategy3(SF) or ""                      # XA-1 + XA-2 layer (XA-3 reverted exactly) == 69e6f0c
S = xb.strip_strategy2(S2) or ""                       # XA-1 layer (XA-2 reverted exactly) == 2732772
XA2_REV = "69e6f0c"
V0, S0 = xb.show(xb.BASE_REV, xb.VIS_PATH), xb.show(xb.BASE_REV, xb.STR_PATH)
XA1_REV = "2732772"
S1 = xb.show(XA1_REV, xb.STR_PATH)
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


ZONE = {"zoneHalfWidth": "6.0", "clusterDist": "5.0", "breakBuffer": "10.0", "flipConfirmDist": "10.0"}
ST = {"stMode": '"C: Candle Pattern"', "stDir": '"Short Only"', "stBuffer": "3.0", "stRR": "1.5", "stTpZone": "false",
      "stBE": "false"}
CHANGED_V = {"zoneHalfWidth", "breakBuffer"}
CHANGED_S = CHANGED_V | {"stMode", "stDir", "stTpZone"}


def gate_static():
    check("XS-01 both files == f253890 + the XA-1 edits (rebuild identical) and strip back byte for byte",
          xb.build_visual1() == V and xb.build_strategy1() == S and xb.strip_visual(VF) == V0 and xb.strip_strategy(SF) == S0
          and xb._revert(V, xb.VISUAL_EDITS) == V0
          and xb._revert(S, xb.STRATEGY_EDITS) == S0
          and all(k in ("header", "default") for k, _, _ in xb.VISUAL_EDITS + xb.STRATEGY_EDITS))
    bad = [l for old, new, names in ((V0, V, CHANGED_V), (S0, S, CHANGED_S)) for l in es.changed_code(old, new)
           if not re.match(r"^(" + "|".join(sorted(names)) + r")\s*=\s*input\.\w+\(", l)]
    check("XS-02 the code delta is only the specified input defaults (Visual: Half Width, Break Buffer; Strategy: those + "
          "Entry Mode, Direction, opposite-zone TP); no logic / order / alert / label / Engine change", not bad, str(bad[:4]))
    vv, vs = input_values(V), input_values(S)
    zb = [n for n, x in ZONE.items() if vv.get(n) != x or vs.get(n) != x]
    sb = [n for n, x in ST.items() if vs.get(n) != x]
    check("XS-03 table values: Zone Half Width 6, Cluster 5, Break 10, Flip 10 (both files); Strategy Entry C: Candle Pattern, "
          "Short Only, SL Buffer 3, fixed RR 1.5, opposite-zone TP OFF, breakeven OFF", not zb and not sb, str((zb, sb)))
    vd, sd = input_decls(V), input_decls(S)
    zone_names = set(input_decls(S[:S.index("// ==== ZONE Strategy · Zone evaluation (begin)")]))
    check("XS-04 Visual / Strategy share every Zone input declaration and ZoneCfg assignment",
          zone_names and all(vd.get(n) == sd[n] for n in zone_names)
          and re.findall(r"^zoneCfg\.\w+\s*:=.*$", V, re.M) == re.findall(r"^zoneCfg\.\w+\s*:=.*$", S, re.M),
          str([n for n in zone_names if vd.get(n) != sd.get(n)]))
    same_v = [n for n in input_decls(V0) if n not in CHANGED_V and input_decls(V0)[n] != vd.get(n)]
    same_s = [n for n in input_decls(S0) if n not in CHANGED_S and input_decls(S0)[n] != sd.get(n)]
    check("XS-05 everything else unchanged: all other inputs (Accum detection, MA / Swing / FVG / RN / session / BE trigger / "
          "TP-zone RR ...), strategy() options (initial capital 10,000, fixed qty 1, no currency / commission / slippage / "
          "margin added), Engine import ZoneEnginePractical/6, Entry / Direction option lists",
          not same_v and not same_s and set(input_decls(V0)) == set(vd) and set(input_decls(S0)) == set(sd)
          and seg(S, "strategy(", "import ") == seg(S0, "strategy(", "import ")
          and "initial_capital        = 10000," in S and "default_qty_type       = strategy.fixed," in S
          and "default_qty_value      = 1)" in S and not re.search(r"commission|slippage|margin_|currency\s*=", seg(S, "strategy(", "import "))
          and re.findall(r"^import .*$", V + S, re.M) == ["import sekine3310/ZoneEnginePractical/6 as zn"] * 2
          and 'options = ["Long Only", "Short Only", "Both"]' in S and '"D: 1M BOS Rebound"], group = G_ST)' in S,
          str((same_v, same_s)))
    hdr = V[:V.index("//@version=5")] + S[:S.index("//@version=5")]
    check("XS-06 header: 比較継続中の初期値 (not optimised / future validity not confirmed) in both files; no completion claim",
          hdr.count(xb.NOTE) == 2 and not re.search(r"最適値です|最適化済み|検証完了|将来も有効", hdr.replace(xb.NOTE, "")))
    mod = git("diff", "--name-only", "--diff-filter=MDR", xb.BASE_REV, "--").split()
    rest = [m for m in mod if not (xb.xa_ok(m, xb.BASE_REV) or xb.test_ok(m))]
    check("XS-07 vs f253890: ZONE-P / ZONE-ST differ exactly by XA-1 (+ XA-2 on ZONE-ST); every other changed file is a test / generator whose edits "
          "are recorded exactly in xa_build.TEST_ADAPT; other Pine files and Engines untouched",
          set(xb.XA_FILES) <= set(mod) and not rest and not [m for m in mod if m.endswith(".pine") and m not in xb.XA_FILES],
          str(rest))
    m = SF.replace('stTpZone = input.bool(false', 'stTpZone = input.bool(true')
    check("XS-08 mutation: a Strategy with opposite-zone TP still ON is detected", input_values(m)["stTpZone"] == "true"
          and xb.strip_strategy(m) is None)


# ---- XA-2 model: f_stQty transcribed (same expressions, same order) -----------------------------------------------------
def st_qty(side, ref, sl, bud_jpy=9000.0, usdjpy=150.0, pv=1.0, lot_oz=100.0, lot_min=0.01, lot_step=0.01):
    """returns (qty, lot, planned loss USD) or None (no order). usdjpy None models convert_to_symbol == na."""
    if ref is None or sl is None:
        return None
    dist = ref - sl if side == 1 else sl - ref
    bud = (bud_jpy / usdjpy if usdjpy else None) if bud_jpy > 0 else None
    if not (dist > 0 and pv is not None and pv > 0 and lot_oz > 0 and lot_step > 0 and lot_min > 0 and bud is not None and bud > 0):
        return None
    n = math.floor(bud / (dist * lot_oz * lot_step) + 1e-9)
    if n * lot_step * lot_oz * dist > bud:
        n -= 1
    if not (n >= 1 and n * lot_step >= lot_min * (1 - 1e-9)):
        return None
    q = n * lot_step * lot_oz / pv
    return q, n * lot_step, dist * q * pv


def gate_qty():
    check("XQ-01 Strategy == the XA-1 file (2732772) + the XA-2 edits (rebuild identical), strips back to 2732772 byte for "
          "byte; Visual unchanged since 2732772 (XA-1 layer)", xb.build_strategy2() == S2 and S2 == xb.show(XA2_REV, xb.STR_PATH) and S == S1 and S1
          and V == xb.show(XA1_REV, xb.VIS_PATH) and all(k in ("header", "size") for k, _, _ in xb.STRATEGY_EDITS2))
    allowed = (r"^(stCapBase|stRiskPct|stLotOz|stLotMin|stLotStep)\s*=\s*input\.float\(|^var string G_STQ = |^float stBudget = "
               r"|^f_stQty\(int side, float ref, float sl\) =>$|^float  pQty = f_stQty\(side, ref, pSL\)$"
               r"|^if not skipRef and not na\(pQty\)$|^currency\s+= currency\.JPY,$|^initial_capital\s+= 300000,$"
               r"|^strategy\.entry\(oEid, side == 1 \? strategy\.long : strategy\.short, qty = pQty(, limit = oL)?\)$")
    removed = ["initial_capital        = 10000,", "if not skipRef",
               "strategy.entry(oEid, side == 1 ? strategy.long : strategy.short, limit = oL)",
               "strategy.entry(oEid, side == 1 ? strategy.long : strategy.short)"]
    ch = es.changed_code(S1, S2)                          # removed + added lines (symmetric)
    old = [l for l in removed if l in ch]
    added = list(ch)
    for l in removed:
        if l in added:
            added.remove(l)
    body = [b.strip() for b in code_only(func(S2, "f_stQty(int side, float ref, float sl) =>")).strip().splitlines()[1:]]
    bad = [l for l in added if l and not re.search(allowed, l) and l not in body and not l.startswith("tooltip = ")]
    check("XQ-02 code delta vs 2732772 is only: initial capital 300000 + currency JPY, the five sizing inputs, the budget, "
          "f_stQty, the pQty gate and qty on both entries (no Entry / exit / Track / alert / label / Engine change)",
          not bad and old == removed and len(added) == len(ch) - 4 and len([l for l in added if l]) == 27, str((bad[:4], old, len(added))))
    sv = input_values(S2)
    exp = {"stCapBase": "300000.0", "stRiskPct": "3.0", "stLotOz": "100.0", "stLotMin": "0.01", "stLotStep": "0.01"}
    hd = seg(S2, "strategy(", "import ")
    check("XQ-03 strategy(): initial_capital 300000, currency.JPY; inputs base 300,000 JPY, 3.0 %, 1 lot = 100 oz, minimum "
          "0.01, step 0.01; budget = base x rate / 100 (a constant, no strategy.equity / netprofit / balance link)",
          all(sv.get(k) == v for k, v in exp.items()) and "initial_capital        = 300000," in hd
          and "currency               = currency.JPY," in hd and "float stBudget = stCapBase * stRiskPct / 100.0" in S2
          and not re.search(r"strategy\.(equity|netprofit|openprofit|initial_capital)", re.sub(r'"[^"\n]*"', '""', code_only(S2)))
          and 300000.0 * 3.0 / 100.0 == 9000.0, str({k: sv.get(k) for k in exp}))
    f = code_only(func(S2, "f_stQty(int side, float ref, float sl) =>"))
    check("XQ-04 f_stQty: JPY budget -> symbol currency via strategy.convert_to_symbol (no fixed USDJPY / 150 / request), "
          "syminfo.pointvalue, distance by side, floor to the step, re-check after floor (one step down), minimum lot, "
          "qty = lot x oz / pointvalue; na guards for distance / pointvalue / inputs / conversion",
          "strategy.convert_to_symbol(stBudget)" in f and "syminfo.pointvalue" in f and "dist   = side == 1 ? ref - sl : sl - ref" in f
          and "math.floor(budSym / (dist * stLotOz * stLotStep) + 1e-9)" in f and "if n * stLotStep * stLotOz * dist > budSym" in f
          and "n >= 1 and n * stLotStep >= stLotMin * (1 - 1e-9)" in f and "q := n * stLotStep * stLotOz / pv" in f
          and "not na(budSym) and budSym > 0" in f and "dist > 0" in f and "pv > 0" in f
          and not re.search(r"USDJPY|150|request\.|100000", f) and "math.ceil" not in f and S2.count("f_stQty(") == 2)
    blk = S2[S2.index("float  pQty = f_stQty(side, ref, pSL)"):S2.index("    stPrev := cur")]
    gate = "            if not skipRef and not na(pQty)\n"
    pre = S2[S2.index("[skipRef, tpRef] = f_stTp(side, ref, pSL"):S2.index(gate)]
    check("XQ-05 one shared quantity function; the gate (not skipRef and not na(pQty)) precedes every order-state change "
          "(oSeq / oEid / oState / entry / exit); qty = pQty on the limit (A) and market (B / C / D) entry; no other "
          "strategy.entry; Track use (stUsed) is still written only on fill / close handling, not at order time",
          blk.startswith("float  pQty = f_stQty(side, ref, pSL)\n" + gate) and not re.search(r"oSeq|oState|strategy\.", pre)
          and S2.count("strategy.entry(") == 2 and S2.count("qty = pQty") == 2
          and "qty = pQty, limit = oL)" in blk and "map.put(stUsed" not in blk
          and S2.count("map.put(stUsed") == S1.count("map.put(stUsed") == 2 and "calc_on_every_tick     = false," in S2
          and "alert(" not in code_only(S2))
    req = lambda t: re.findall(r"request\.\w+\(", code_only(t))
    sd, s1d = input_decls(S2), input_decls(S1)
    check("XQ-06 everything else kept: every XA-1 input (Half Width 6, Cluster 5, Break 10, Flip 10, C, Short Only, SL Buffer 3, "
          "RR 1.5, Zone TP OFF, BE OFF) and all other inputs identical; no commission / slippage / margin; Engine import /6; "
          "request list unchanged",
          all(sd[n] == s1d[n] for n in s1d) and set(sd) - set(s1d) == set(exp)
          and all(input_values(S2).get(n) == x for n, x in {**ZONE, **ST}.items())
          and not re.search(r"commission|slippage|margin_", hd) and req(S2) == req(S1)
          and re.findall(r"^import .*$", S2, re.M) == ["import sekine3310/ZoneEnginePractical/6 as zn"])
    mod = git("diff", "--name-only", XA1_REV, "--").split()
    check("XQ-07 vs 2732772: only ZoneStrategyXAU.pine, ZoneVisualPractical.pine (exactly XA-3) and tests/xa_build.py / "
          "tests/xa_sim.py change (no other Pine / Engine)",
          set(mod) <= {xb.STR_PATH, xb.VIS_PATH, "tests/xa_build.py", "tests/xa_sim.py"} and xb.STR_PATH in mod
          and (xb.VIS_PATH not in mod or V == xb.show(XA1_REV, xb.VIS_PATH)), str(mod))
    hdr = S2[:S2.index("//@version=5")]
    check("XQ-08 comments: 9,000 JPY described as the planned loss at the reference price, not an actual-loss cap",
          "毎回 9,000 円の予定損失予算・単利" in hdr and "約定ずれ・スプレッド・手数料を含む実損失の上限ではない" in S2
          and not re.search(r"最大損失は 9,000|損失上限 9,000|実損失.{0,6}9,000", S2))

    # ---- model (USDJPY 150 is a test assumption only -> 9,000 JPY = 60 USD) ----
    def eq(r, q, lot, loss):
        return r is not None and abs(r[0] - q) < 1e-9 and abs(r[1] - lot) < 1e-9 and abs(r[2] - loss) < 1e-9
    check("XQ-09 SL 20 USD: 0.03 lot, qty 3, planned loss 60 USD (Short: ref 2000, SL 2020; Long: ref 2000, SL 1980)",
          eq(st_qty(-1, 2000.0, 2020.0), 3, 0.03, 60) and eq(st_qty(1, 2000.0, 1980.0), 3, 0.03, 60))
    r = st_qty(-1, 2000.0, 2025.0)
    check("XQ-10 SL 25 USD: 0.02 lot, qty 2, planned loss 50 USD (0.03 lot would be 75 > 60)",
          eq(r, 2, 0.02, 50) and 0.03 * 100 * 25 > 60, str(r))
    check("XQ-11 minimum 0.01 lot over budget -> no order (SL 60.01 / 100); exactly 60 -> 0.01 lot qty 1 loss 60",
          st_qty(-1, 2000.0, 2060.01) is None and st_qty(1, 2000.0, 1900.0) is None and eq(st_qty(-1, 2000.0, 2060.0), 1, 0.01, 60))
    check("XQ-12 pointvalue 10: 0.03 lot -> qty 0.3 with the same 60 USD loss; pointvalue 100 -> qty 0.03; no double x100 "
          "(qty 3 at pointvalue 1 is 3 oz, never 300 / 300,000)",
          eq(st_qty(-1, 2000.0, 2020.0, pv=10.0), 0.3, 0.03, 60) and eq(st_qty(1, 2000.0, 1980.0, pv=100.0), 0.03, 0.03, 60))
    inv = [st_qty(-1, 2000.0, 1990.0), st_qty(1, 2000.0, 2010.0), st_qty(1, 2000.0, 2000.0), st_qty(1, None, 1990.0),
           st_qty(1, 2000.0, 1990.0, usdjpy=None), st_qty(1, 2000.0, 1990.0, pv=0.0), st_qty(1, 2000.0, 1990.0, pv=None),
           st_qty(1, 2000.0, 1990.0, bud_jpy=0.0), st_qty(1, 2000.0, 1990.0, lot_oz=0.0), st_qty(1, 2000.0, 1990.0, lot_step=0.0),
           st_qty(1, 2000.0, 1990.0, lot_min=0.0)]
    check("XQ-13 no order: wrong SL side (Long / Short), zero distance, na price, conversion na, pointvalue 0 / na, budget 0, "
          "invalid oz / step / minimum", all(x is None for x in inv), str(inv))
    bd = [st_qty(1, 2000.0, 2000.0 - 60 / 4), st_qty(1, 2000.0, 2000.0 - 60 / 4 - 1e-6), st_qty(1, 2000.0, 1999.0),
          st_qty(1, 2000.0, 1990.0, lot_min=0.05), st_qty(1, 2000.0, 1990.0, lot_min=0.07)]
    check("XQ-14 step boundaries: SL 15 -> exactly 0.04 lot (loss 60); just over 15 -> 0.03; SL 1 -> 0.6 lot; minimum lot "
          "0.05 with 0.06 possible -> 0.06, minimum 0.07 -> no order",
          eq(bd[0], 4, 0.04, 60) and eq(bd[1], 3, 0.03, bd[1][2] if bd[1] else -1) and eq(bd[2], 60, 0.6, 60)
          and eq(bd[3], 6, 0.06, 60) and bd[4] is None, str(bd))
    import random
    rnd, bad = random.Random(20261021), []
    for _ in range(20000):
        side, ref = rnd.choice((1, -1)), rnd.uniform(1500, 3500)
        d, pv, fx = rnd.choice((rnd.uniform(0.01, 80), round(rnd.uniform(0.1, 80), 2))), rnd.choice((1.0, 10.0, 100.0, 0.5)), rnd.uniform(100, 170)
        r = st_qty(side, ref, ref - side * d, usdjpy=fx, pv=pv)
        bud = 9000.0 / fx
        if r is None:
            if 0.01 * 100 * d <= bud * (1 - 1e-6):
                bad.append(("skip", d, fx))
            continue
        lot = r[1]
        if r[2] > bud * (1 + 1e-9) or (lot + 0.01) * 100 * d <= bud * (1 - 1e-6) or abs(r[0] * pv - lot * 100) > 1e-6 \
                or abs(round(lot / 0.01) * 0.01 - lot) > 1e-9 or lot < 0.01 - 1e-12:
            bad.append((side, d, pv, fx, r))
    check("XQ-15 random property (20,000 cases, USDJPY 100-170, pointvalue 0.5 / 1 / 10 / 100): planned loss <= budget, "
          "one more 0.01 step would exceed it, lot on the 0.01 grid >= 0.01, qty x pointvalue = lot x 100 oz; no order only "
          "when 0.01 lot exceeds the budget", not bad, str(bad[:3]))
    m = S2.replace("qty = pQty)", ")")
    check("XQ-16 mutation: a market entry without qty, or a fixed 150 rate, is detected by the exact strip",
          xb.strip_strategy2(m) is None
          and xb.strip_strategy2(S2.replace("strategy.convert_to_symbol(stBudget)", "stBudget / 150.0")) is None)


XA3_ZONE = {"zoneHalfWidth": "6.0", "clusterDist": "5.0", "breakBuffer": "10.0", "flipConfirmDist": "5.0",
            "thrMedium": "5.0", "thrStrong": "10.0", "thrVStrong": "15.0", "scoreMa1": "3.0", "scoreMa2": "3.0",
            "slopeThrMod": "1.0", "slopeThrStrong": "3.0", "slopeBonusFlat": "0.0", "slopeBonusMod": "1.0",
            "slopeBonusStr": "2.0", "slopeBonusMode": '"Max"', "scoreDayHL": "3.0", "scoreAcc1": "3.0", "scoreAcc2": "4.0",
            "scoreAcc3": "5.0", "scoreHz1": "1.0", "scoreHz2": "2.0", "scoreHz3": "3.0", "confBonus2": "1.0",
            "confBonus3": "2.0", "confBonus4": "3.0", "enableRn": "true"}
XA3_ST = {"stMode": '"C: Candle Pattern"', "stDir": '"Short Only"', "stBuffer": "1.5", "stRR": "1.5", "stTpZone": "false",
          "stBE": "false"}
XA3_V = {"flipConfirmDist", "scoreMa1", "scoreMa2", "slopeBonusMode"}
XA3_S = XA3_V | {"stBuffer"}


def gate_xa3():
    V2 = xb.show(XA2_REV, xb.VIS_PATH)
    check("XT-01 both files == the 69e6f0c files + the XA-3 edits (rebuild identical) and strip back to 69e6f0c byte for byte; "
          "the full chain strips to f253890", xb.build_visual() == VF and xb.build_strategy() == SF and V2 and S2
          and V == V2 and S2 == xb.show(XA2_REV, xb.STR_PATH) and xb.strip_visual(VF) == V0 and xb.strip_strategy(SF) == S0
          and all(k in ("header", "default") for k, _, _ in xb.VISUAL_EDITS3 + xb.STRATEGY_EDITS3))
    bad = [l for old, new, names in ((V2, VF, XA3_V), (S2, SF, XA3_S)) for l in es.changed_code(old, new)
           if not re.match(r"^(" + "|".join(sorted(names)) + r")\s*=\s*input\.\w+\(", l)]
    cv, cs = es.changed_code(V2, VF), es.changed_code(S2, SF)
    check("XT-02 the code delta is only the changed defaults (Visual: Flip, MA #1 / #2 base, Slope aggregation; Strategy: those "
          "+ SL Buffer); options / ranges / labels / tooltips unchanged", not bad and len(cv) == 8 and len(cs) == 10
          and all(input_decls(VF)[n].replace(input_values(VF)[n], "X", 1) == input_decls(V2)[n].replace(input_values(V2)[n], "X", 1)
                  for n in XA3_V), str(bad[:4]))
    vv, vs = input_values(VF), input_values(SF)
    zb = [n for n, x in XA3_ZONE.items() if vv.get(n) != x or vs.get(n) != x]
    sb = [n for n, x in XA3_ST.items() if vs.get(n) != x]
    check("XT-03 every table value: Half Width 6, Cluster 5, Break 10, Flip 5, thresholds 5 / 10 / 15, MA base 3 / 3, Slope "
          "threshold 1 / 3, bonus 0 / 1 / 2, aggregation Max, Day H/L 3, Accum 3 / 4 / 5, Swing 1 / 2 / 3, Confluence 1 / 2 / 3, RN "
          "ON (both files); Strategy C, Short Only, SL Buffer 1.5, RR 1.5, Zone TP OFF, BE OFF", not zb and not sb, str((zb, sb)))
    zone_names = set(input_decls(SF[:SF.index("// ==== ZONE Strategy · Zone evaluation (begin)")]))
    vd, sd = input_decls(VF), input_decls(SF)
    check("XT-04 Visual / Strategy share every Zone input declaration and ZoneCfg assignment; the Visual has no Strategy "
          "trading input (no st* input, no strategy())",
          zone_names and all(vd.get(n) == sd[n] for n in zone_names) and set(vd) == set(input_decls(V2))
          and not [n for n in vd if n.startswith("st")] and "strategy(" not in code_only(VF)
          and re.findall(r"^zoneCfg\.\w+\s*:=.*$", VF, re.M) == re.findall(r"^zoneCfg\.\w+\s*:=.*$", SF, re.M),
          str([n for n in zone_names if vd.get(n) != sd.get(n)]))
    s2d, v2d = input_decls(S2), input_decls(V2)
    req = lambda x: re.findall(r"request\.\w+\(", code_only(x))
    q = "f_stQty(int side, float ref, float sl) =>"
    check("XT-05 everything else unchanged: all other inputs (incl. Breakeven Trigger 10 while BE is OFF, Accum detection, "
          "Swing TF / pivot, MA TF / type / length / slope lookback, FVG, RN step / score), sizing (300,000 JPY / JPY, "
          "base 300,000 x 3 %, 100 oz, 0.01 / 0.01, f_stQty, qty on both entries), strategy(), Engine import /6, request lists",
          not [n for n in s2d if n not in XA3_S and s2d[n] != sd.get(n)] and set(s2d) == set(sd)
          and not [n for n in v2d if n not in XA3_V and v2d[n] != vd.get(n)]
          and vs.get("stBEDist") == "10.0" and es.func(SF, q) == es.func(S2, q) and SF.count("qty = pQty") == 2
          and seg(SF, "strategy(", "import ") == seg(S2, "strategy(", "import ")
          and code_only(SF[SF.index("var string G_STS ="):]) == code_only(S2[S2.index("var string G_STS ="):])
          and req(SF) == req(S2) and req(VF) == req(V2)
          and re.findall(r"^import .*$", VF + SF, re.M) == ["import sekine3310/ZoneEnginePractical/6 as zn"] * 2)
    hdr = VF[:VF.index("//@version=5")] + SF[:SF.index("//@version=5")]
    check("XT-06 header: 'Gold Short の比較から採用した、検証継続中の初期値' in both files; no optimisation / Long / future claim; "
          "no old Flip 10 / SL Buffer 3 default left in the header",
          hdr.count(xb.NOTE3) == 2 and not re.search(r"最適値です|最適化済み|検証完了|将来も有効|Long でも検証済み", hdr.replace(xb.NOTE3, ""))
          and "Flip 10 USD" not in hdr and "SL Buffer 3、" not in hdr and "Cluster 5 / Flip 10 は従来どおり" not in hdr
          and "Flip 5 USD" in hdr and "SL Buffer 1.5" in SF[:SF.index("//@version=5")])
    mod = git("diff", "--name-only", XA2_REV, "--").split()
    check("XT-07 vs 69e6f0c: only the two Gold Pine files (exactly XA-3) and tests/xa_build.py / xa_sim.py change; other "
          "symbols' Pine files and Engines untouched", set(mod) <= {xb.VIS_PATH, xb.STR_PATH, "tests/xa_build.py", "tests/xa_sim.py"}
          and set(xb.XA_FILES) <= set(mod), str(mod))
    m = SF.replace('flipConfirmDist = input.float(5.0', 'flipConfirmDist = input.float(10.0')
    m2 = VF.replace('slopeBonusMode = input.string("Max"', 'slopeBonusMode = input.string("Sum (per MA)"')
    check("XT-08 mutation: a Strategy with Flip still 10 / a Visual with Sum aggregation is detected",
          xb.strip_strategy3(m) is None and xb.strip_visual3(m2) is None and input_values(m)["flipConfirmDist"] != vv["flipConfirmDist"])


def main():
    try:
        gate_static()
        gate_qty()
        gate_xa3()
    except Exception:
        import traceback
        check("gate_static completed without error", False, traceback.format_exc()[-900:])
    fails = 0
    for n, ok, d in RESULTS:
        fails += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {n[:150].ljust(150)}  {'' if ok else d}")
    print(f"\n{len(RESULTS) - fails}/{len(RESULTS)} passed  [PINE_NOT_VERIFIED: exact build / static]")
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
