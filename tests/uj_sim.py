"""UJ-1 / UJ-2 fixtures — USDJPY dedicated Engine (ZoneEnginePracticalUSDJPY) and GBPJPY position sizing in ZoneStrategyUSDJPY.

  US : static — the Engine == ZoneEnginePracticalSwingMax.pine (the published ZoneEnginePractical/6 source) except the
       library name, same exports; Visual / Strategy rebuild from their pre-UJ-1 text (3568c05) and strip back byte for
       byte; Visual delta = import + Zone Half Width 0.03 (user decision), Strategy delta = import + sizing; both import
       ZoneEnginePracticalUSDJPY/1 and share every Zone input / ZoneCfg / feed / FVG block; the sizing code equals the
       GBPJPY f_stQty and is used for both the limit and the market entry, before any order / Track state is written;
       every other Strategy setting unchanged (D, Long Only, SL Buffer, Zone TP, RR, BE, session, calc_on_every_tick);
       RN stays OFF; only the USDJPY files and the exactly-adapted older fixtures change vs 3568c05
  UM : model (Python port, not a TradingView run) — quantity: 9,000 JPY budget, pointvalue 1: 0.10 -> 90,000 (0.90 lot),
       0.13 -> 69,000 (0.69 lot, planned loss 8,970); Long / Short, floor, invalid, below one lot step

  (US checks pin UJ-1 on the files with the UJ-2 defaults reverted, == commit a6a275c.)
  UD : UJ-2 adopted defaults — strip_*2 gives a6a275c back; the code delta is only the specified input defaults (and the
       Cluster tooltip); the specified table in both files, Visual / Strategy Zone inputs identical; every other input,
       the sizing, the Engine and the logic unchanged; header wording (Long comparison, per-year / Short not done)

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
rd = lambda p: __import__("sx_build").unapply(p, open(os.path.join(ROOT, p), encoding="utf-8").read())   # SX-1 reverted (pinned in sxs_sim)
git = lambda *a: subprocess.run(["git", "-C", ROOT] + list(a), capture_output=True, text=True).stdout
code_only, input_decls, input_values, func, seg = es.code_only, es.input_decls, es.input_values, es.func, es.seg
E6, EU = rd(ub.ENG_SRC), rd(ub.ENG_PATH)
V0, S0 = ub.base(ub.VIS_PATH), ub.base(ub.STR_PATH)
FV, FS3 = rd(ub.VIS_PATH), rd(ub.STR_PATH)
FS = ub.strip_strategy3(FS3) or ""     # UJ-3: labels / SL distance reverted exactly (pinned in ujl_sim)
UJ1 = "a6a275c"
V, S = ub.strip_visual2(FV) or "", ub.strip_strategy2(FS) or ""     # UJ-1 layer (UJ-2 defaults reverted)
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
          ub.build_visual1() == V and ub.build_strategy1() == S and ub.build_visual() == FV and ub.build_strategy2() == FS
          and ub.strip_visual(FV) == V0 and ub.strip_strategy(FS3) == S0
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
    mod = [m for m in mod if not (__import__("bte_build").bte_pine_ok(m, ub.BASE_REV) or __import__("xa_build").xa_ok(m, ub.BASE_REV)
                                  or __import__("cad_adapt").ok(m, ub.BASE_REV))]     # BTE-1 / XA-1 / CAD-1: exact
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


# ---- UJ-2: adopted defaults ---------------------------------------------------------------------------------------------
UJ2_ZONE = {"zoneHalfWidth": "0.03", "clusterDist": "0.12", "breakBuffer": "0.12", "flipConfirmDist": "0.10",
            "thrMedium": "5.0", "thrStrong": "8.0", "thrVStrong": "15.0", "scoreMa1": "1.0", "scoreMa2": "1.0",
            "slopeThrMod": "0.01", "slopeThrStrong": "0.02", "slopeBonusFlat": "0.0", "slopeBonusMod": "0.5",
            "slopeBonusStr": "1.0", "slopeBonusMode": '"Sum (per MA)"', "scoreHz1": "1.0", "scoreHz2": "2.0",
            "scoreHz3": "3.0", "scoreDayHL": "1.0", "scoreAcc1": "4.0", "scoreAcc2": "5.0", "scoreAcc3": "6.0",
            "confBonus2": "0.5", "confBonus3": "1.0", "confBonus4": "1.5", "fvgMinWidth": "0.05"}
UJ2_ST = {"stMode": '"D: 1M BOS Rebound"', "stDir": '"Long Only"', "stBuffer": "0.05", "stRR": "1.5", "stTpZone": "false",
          "stBE": "false"}
UJ2_CHANGED = {"clusterDist", "breakBuffer", "flipConfirmDist", "thrStrong", "scoreMa1", "scoreMa2", "slopeThrMod",
               "slopeThrStrong", "slopeBonusMod", "slopeBonusStr", "scoreDayHL", "scoreAcc1", "scoreAcc2", "scoreAcc3",
               "confBonus2", "confBonus3", "confBonus4", "stRR"}


def gate_defaults():
    check("UD-01 UJ-2: strip_visual2 / strip_strategy2 give the UJ-1 files of a6a275c byte for byte; Engine byte-identical to "
          "a6a275c; rebuilding gives the submitted files",
          V == git("show", f"{UJ1}:{ub.VIS_PATH}") and S == git("show", f"{UJ1}:{ub.STR_PATH}")
          and EU == git("show", f"{UJ1}:{ub.ENG_PATH}") and ub.build_visual() == FV and ub.build_strategy2() == FS
          and all(k in ("header", "default") for k, _, _ in ub.VISUAL_EDITS2 + ub.STRATEGY_EDITS2)
          and all(any(x is e for x in ub.VISUAL_EDITS2) and any(x is e for x in ub.STRATEGY_EDITS2) for e in ub.ZONE_DEFAULT_EDITS))
    bad = [l for old, new in ((V, FV), (S, FS)) for l in es.changed_code(old, new)
           if not (re.match(r"^(" + "|".join(sorted(UJ2_CHANGED)) + r")\s*=\s*input\.\w+\(", l) or re.match(r'^tooltip = ".*"\)$', l))]
    check("UD-02 the code delta UJ-1 -> UJ-2 is only the specified input defaults (+ the Cluster Distance tooltip); no logic, "
          "Engine call, sizing, order, alert or label change", not bad, str(bad[:4]))
    vv, vs = input_values(FV), input_values(FS)
    zb = [n for n, x in UJ2_ZONE.items() if vv.get(n) != x or vs.get(n) != x]
    sb = [n for n, x in UJ2_ST.items() if vs.get(n) != x]
    check("UD-03 adopted values in both files: HW 0.03, Cluster 0.12, Break 0.12, Flip 0.10, 5 / 8 / 15, MA 1 / 1, Slope 0.01 / "
          "0.02, bonus 0 / 0.5 / 1 Sum (per MA), Swing 1 / 2 / 3, Day H/L 1, Accum 4 / 5 / 6, Confluence 0.5 / 1 / 1.5, FVG "
          "0.05; Strategy D, Long Only, SL Buffer 0.05, RR 1.5, Zone TP OFF, BE OFF", not zb and not sb, str((zb, sb)))
    vd, sd = input_decls(FV), input_decls(FS)
    zone_names = set(input_decls(FS[:FS.index("// ==== ZONE Strategy · Zone evaluation (begin)")]))
    check("UD-04 Visual / Strategy share every Zone input declaration and ZoneCfg assignment after UJ-2",
          zone_names == set(vd) - es.DISPLAY_INPUTS and all(vd[n] == sd[n] for n in zone_names)
          and re.findall(r"^zoneCfg\.\w+\s*:=.*$", FV, re.M) == re.findall(r"^zoneCfg\.\w+\s*:=.*$", FS, re.M))
    e1v, e1s = input_decls(V), input_decls(S)
    same = [n for n in set(e1v) | set(e1s) if n not in UJ2_CHANGED and (e1v.get(n) != vd.get(n) or e1s.get(n) != sd.get(n))]
    check("UD-05 everything else unchanged: MA 1-minute EMA 2000 / 3000, lookback 60, MA cluster distance and bonuses, Swing / "
          "Accum detection / TFs / keep counts, FVG, session, Touch, lifetimes, Track, HTF, RN, BE trigger 0.15, TP-zone Min / "
          "Max RR 1.0 / 3.0, sizing (300,000 / 3 % / 100,000 / 0.01, f_stQty), Entry / Direction option lists",
          not same and (vs["maTf"], vs["maType"], vs["ma1Len"], vs["ma2Len"], vs["slopeLookback"]) == ('"1"', '"EMA"', "2000", "3000", "60")
          and (vs["stBEDist"], vs["stTpMinRR"], vs["stTpMaxRR"]) == ("0.15", "1.0", "3.0")
          and (vs["stCapBase"], vs["stRiskPct"], vs["stLotUnits"], vs["stLotStep"]) == ("300000.0", "3.0", "100000.0", "0.01")
          and func(FS, "f_stQty(int side, float ref, float sl) =>") == func(S, "f_stQty(int side, float ref, float sl) =>")
          and 'options = ["Long Only", "Short Only", "Both"]' in FS and '"D: 1M BOS Rebound"], group = G_ST)' in FS, str(same))
    hdr = FV[:FV.index("//@version=5")] + FS[:FS.index("//@version=5")]
    check("UD-06 header: 'USDJPY Long の比較から採用した初期値。年別確認・Short での検証は未完了' in both files; no 最適値 / 検証完了 / "
          "将来も有効 claim", hdr.count(ub.UJ2_NOTE) == 2 and "最適値・検証完了ではない" in hdr
          and not re.search(r"最適値です|最適値で|検証完了済|検証完了。|将来も有効", hdr))
    mod = git("diff", "--name-only", "--diff-filter=MDR", UJ1, "--").split()
    mod = [m for m in mod if not (__import__("bte_build").bte_pine_ok(m, UJ1) or __import__("bte_build").test_ok(m)
                                  or __import__("xa_build").xa_ok(m, UJ1) or __import__("xa_build").test_ok(m)
                                  or __import__("cad_adapt").ok(m, UJ1))]   # BTE-1 / XA-1 / CAD-1: exact
    check("UD-07 vs a6a275c only the USDJPY Visual / Strategy and their build / test change (Engine, other symbols, shared "
          "Engines untouched)", set(mod) <= {ub.VIS_PATH, ub.STR_PATH, "tests/uj_build.py", "tests/uj_sim.py"}, str(mod))


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
    for g in (gate_static, gate_model, gate_defaults):
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
