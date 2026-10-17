"""GU-1 fixtures — GBPUSD port (ZoneEnginePracticalGBPUSD / ZoneVisualGBPUSD / ZoneStrategyGBPUSD, OANDA:GBPUSD 5M).

  GS : static — each file == its gu_build transform of the EURUSD source (47aeb8b) and strips back byte for byte; after
       mapping the symbol / wording back, the code equals the EURUSD code except the Direction default (Both), so the
       Zone / Engine / Entry / order / size / alert / label logic and the Visual update timing are the EURUSD files';
       Engine differs only by its library name (same exports, same tick-integer RN); Visual and Strategy share every
       Zone input, ZoneCfg, feeds / requests, FVG block and FVG scoring functions and import ZoneEnginePracticalGBPUSD/1;
       the specified defaults; RN ticker GBPUSD; comparison-start wording "GBPUSD では未検証", no EURUSD results quoted;
       no existing file modified (EURUSD / GBPJPY / BTC / others)
  GM : models (Python ports, not TradingView runs) — size (JPY -> USD -> GBP units, 0.60 lot example), RN tick-integer
       search at GBPUSD round levels, alert text with the GBPUSD ticker

Evidence class: PINE_NOT_VERIFIED (library publish, TradingView compile / backtest / alerts / labels external).
"""
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gu_build as gb            # noqa: E402
import eu_sim as es              # noqa: E402
import fvg_re10045_sim as fr     # noqa: E402

ROOT = gb.ROOT
BASE = "47aeb8b"
rd = lambda p: open(os.path.join(ROOT, p), encoding="utf-8").read() if os.path.exists(os.path.join(ROOT, p)) else ""
show = lambda p, rev=BASE: subprocess.run(["git", "-C", ROOT, "show", f"{rev}:{p}"], capture_output=True, text=True).stdout
EE, EV, ES = rd(gb.ENG_SRC), rd(gb.VIS_SRC), rd(gb.STR_SRC)
GE, GV, GS = rd(gb.ENG_PATH), rd(gb.VIS_PATH), rd(gb.STR_PATH)
code_only, input_decls, input_values, func, seg = es.code_only, es.input_decls, es.input_values, es.func, es.seg
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


def back(code):
    """map a GBPUSD code text back to the EURUSD wording (inverse of gu_build._symbol_line on code lines)."""
    return (code.replace(gb.START_GU, gb.ADOPT_EU.replace("EURUSD", "GBPUSD")).replace("GBPUSD", "EURUSD")
            .replace("[比較開始値]", "[採用初期値]"))


TABLE = {"zoneHalfWidth": "0.00020", "clusterDist": "0.00030", "breakBuffer": "0.00050", "flipConfirmDist": "0.00060",
         "slopeThrMod": "0.00002", "slopeThrStrong": "0.00004", "slopeBonusMode": '"Max"', "scoreMa1": "2.0", "scoreMa2": "2.0",
         "scoreHz1": "1.0", "scoreHz2": "2.0", "scoreHz3": "3.0", "scoreDayHL": "1.0", "scoreAcc1": "2.0", "scoreAcc2": "3.0",
         "scoreAcc3": "4.0", "accScoreMode": '"Max"', "accEdgeMode": '"Separate"', "dsMode": '"Separate"', "thrMedium": "5.0",
         "thrStrong": "9.0", "thrVStrong": "15.0", "fvgMinWidth": "0.00020", "fvgDirMatch": "false", "enableRn": "false",
         "rnMajorStep": "0.0100", "rnMinorStep": "0.0050", "hzTf1": '"5"', "hzTf2": '"15"', "hzTf3": '"60"',
         "accTf1": '"60"', "accTf2": '"240"', "accTf3": '"D"'}
ST_TABLE = {"stDir": '"Both"', "stMode": '"B: Confirmed Rejection"', "stRR": "1.5", "stBuffer": "0.00030", "stBE": "false",
            "stTpZone": "false", "stUseSess": "true", "stSessTz": '"Asia/Tokyo"', "stSessStartH": "9", "stSessStartM": "0",
            "stSessEndH": "2", "stSessEndM": "0", "stCapBase": "300000.0", "stRiskPct": "3.0", "stLotUnits": "100000.0",
            "stLotStep": "0.01"}


def gate_static():
    check("GS-01 the three GBPUSD files == gu_build transforms of the EURUSD files (rebuild identical) and strip back to them "
          "byte for byte; the EURUSD sources are the 47aeb8b files",
          all([GE, GV, GS]) and gb.build_engine() == GE and gb.build_visual() == GV and gb.build_strategy() == GS
          and gb.strip_engine(GE) == EE and gb.strip_visual(GV) == EV and gb.strip_strategy(GS) == ES
          and (EE, EV, ES) == (show(gb.ENG_SRC), show(gb.VIS_SRC), show(gb.STR_SRC))
          and all(k in ("header", "name", "symbol", "default") for k, _, _ in gb.engine_edits() + gb.visual_edits() + gb.strategy_edits()))
    exports = lambda t: re.findall(r"^export .*$", t, re.M)
    check("GS-02 Engine: code identical to ZoneEnginePracticalEURUSD except the library name; same exports; same tick-integer "
          "f_rnLevelIn",
          code_only(GE).replace("ZoneEnginePracticalGBPUSD", "ZoneEnginePracticalEURUSD") == code_only(EE)
          and exports(GE) == exports(EE) and len(exports(GE)) > 30 and 'library("ZoneEnginePracticalGBPUSD", overlay = true)' in GE
          and func(GE, "f_rnLevelIn(float zBot, float zTop, float step) =>") == func(EE, "f_rnLevelIn(float zBot, float zTop, float step) =>"))
    sv = back(code_only(GV))
    ss = back(code_only(GS)).replace('stDir = input.string("Both"', 'stDir = input.string("Short Only"')
    check("GS-03 Visual / Strategy code == EURUSD code after mapping back the symbol name and the comparison-start wording "
          "(and, for the Strategy, the Direction default); no EURUSD left in code except the fixed 'EURUSD 確定版から引き継いだ' wording: Zone / Engine calls / requests / update timing / Entry A-D / BOS / "
          "cancel / priority / Track reuse / orders / SL / TP / breakeven / size / alerts / labels unchanged",
          sv == code_only(EV) and ss == code_only(ES) and "EURUSD" not in (code_only(GV) + code_only(GS) + code_only(GE)).replace(gb.START_GU, "")
          and "採用初期値" not in code_only(GV) + code_only(GS))
    vd, sd = input_decls(GV), input_decls(GS)
    zone_names = set(input_decls(GS[:GS.index("// ==== ZONE Strategy · Zone evaluation (begin)")]))
    cfg = lambda t: re.findall(r"^zoneCfg\.\w+\s*:=.*$", t, re.M)
    feed = lambda t: code_only(seg(t, "// ---- 3.2 Zone Engine Feed", "//  ★ 5分足専用: 5分足以外では zn.update"))
    fvg = lambda t: code_only(seg(t, "// ==== FVG Batch A (begin)", "// ==== FVG Batch A (end)"))
    rnv = lambda t: code_only(seg(t, "float rnMajT", "// ---- 2.8 Cluster"))
    check("GS-04 Visual / Strategy parity: identical Zone input declarations, every zoneCfg assignment (RN ticker GBPUSD), "
          "feeds with their 10 request.security calls, FVG Batch A, RN validation, FVG scoring / boost functions; both "
          "import ZoneEnginePracticalGBPUSD/1",
          zone_names == set(vd) - es.DISPLAY_INPUTS and all(vd[n] == sd[n] for n in zone_names)
          and cfg(GV) == cfg(GS) and 'zoneCfg.useRnSource          := enableRn and rnStepOK and syminfo.ticker == "GBPUSD"' in cfg(GS)
          and feed(GV) == feed(GS) and fvg(GV) == fvg(GS) and rnv(GV) == rnv(GS)
          and len(re.findall(r"request\.security\(", feed(GS) + fvg(GS))) == 10
          and all(code_only(func(GV, h)).rstrip() == code_only(func(GS, h)).rstrip() for h in es.ZONE_FNS)
          and re.findall(r"^import .*$", GV + GS, re.M) == [gb.IMPORT_GU.strip()] * 2)
    vv, vs = input_values(GV), input_values(GS)
    bad = [n for n, v in TABLE.items() if vv.get(n) != v or vs.get(n) != v] + [n for n, v in ST_TABLE.items() if vs.get(n) != v]
    ev, esv = input_values(EV), input_values(ES)
    other = [n for n in ev if vv.get(n) != ev[n]] + [n for n in esv if n != "stDir" and vs.get(n) != esv[n]]
    check("GS-05 defaults: the specified table (Both, B, RR 1.5, SL Buffer 0.00030, BE / Zone TP OFF, 09:00-02:00 JST, 300,000 "
          "/ 3 % / 100,000 / 0.01, HW 0.00020, Cluster 0.00030, Break 0.00050, Flip 0.00060, Slope 0.00002 / 0.00004 Max, "
          "MA 2 / 2, Swing 1 / 2 / 3 (5 / 15 / 60), Day H/L 1, Accum 2 / 3 / 4 (60 / 240 / D), Max / Separate / Separate, "
          "5 / 9 / 15, FVG 0.00020 OFF, RN OFF 0.0100 / 0.0050); every other input value equals EURUSD; strategy() options "
          "equal; Long Only / Short Only / Both and A-D options kept",
          not bad and not other and set(vv) == set(ev) and set(vs) == set(esv)
          and seg(GS, "strategy(", "import ").replace("GBPUSD", "EURUSD") == seg(ES, "strategy(", "import ")
          and 'options = ["Long Only", "Short Only", "Both"]' in GS and '"D: 1M BOS Rebound"], group = G_ST)' in GS,
          str((bad, other)))
    hdr = GV[:GV.index("//@version=5")] + GS[:GS.index("//@version=5")]
    check("GS-06 wording: inputs say 比較開始値 / 'GBPUSD では未検証 (最適値ではない)'; headers say the defaults are carried over from "
          "EURUSD and not verified on GBPUSD and that EURUSD results are not GBPUSD results; no EURUSD performance figures; "
          "size comment in GBP units",
          code_only(GV).count("GBPUSD では未検証") >= 5 and code_only(GS).count("GBPUSD では未検証") >= 6
          and "[比較開始値] Zone Half Width (USD)" in GV and hdr.count("GBPUSD では") >= 2
          and "EURUSD の成績は GBPUSD の実績ではない" in hdr and not re.search(r"668,886|906,698|PF ?1\.\d|純利益", GV + GS)
          and "// 数量 (通貨数、GBP)" in GS and "通貨数、EUR" not in GS)
    req = lambda t: re.findall(r"request\.\w+\(", code_only(t))
    check("GS-07 no extra request (Visual 10, Strategy 11, as EURUSD); Visual still updates the Engine as EURUSD does; Strategy "
          "confirmed-bar update; size = JPY budget -> strategy.convert_to_symbol (no fixed USDJPY, no GBP conversion); "
          "RE10045 lint clean",
          req(GV) == req(EV) and len(req(GV)) == 10 and req(GS) == req(ES) and len(req(GS)) == 11
          and "if is5mChart\n    zoneCountNow := zn.update(zoneEng, zoneCfg, zoneFeed)" in GV
          and "if is5mChart and barstate.isconfirmed\n    zoneCountNow := zn.update(zoneEng, zoneCfg, zoneFeed)" in GS
          and func(GS, "f_stQty(int side, float ref, float sl) =>") == func(ES, "f_stQty(int side, float ref, float sl) =>").replace("通貨数、EUR", "通貨数、GBP")
          and "strategy.convert_to_symbol(stBudget)" in GS and code_only(GS).count("convert_to_symbol") == 1
          and all(fr.lint_eager_guards(code_only(t)) == [] for t in (GE, GV, GS)))
    mod = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", "--diff-filter=MDR", BASE, "--"], capture_output=True,
                         text=True).stdout.split()
    check(f"GS-08 no existing file modified vs {BASE} (EURUSD / GBPJPY / BTC / USDJPY / Gold Pine files, Engines, tests); only "
          "new GBPUSD files are added", mod == [], str(mod))
    m = GS.replace('stDir = input.string("Both"', 'stDir = input.string("Long Only"')
    check("GS-09 mutation: a different Direction default and a mismatching Zone input are detected",
          input_values(m)["stDir"] != '"Both"' and gb.strip_strategy(m) is None
          and input_decls(GS.replace("breakBuffer = input.float(0.00050", "breakBuffer = input.float(0.00030"))["breakBuffer"] != vd["breakBuffer"])


def gate_model():
    ex = es.qty(1, 1.27000, 1.26900, 150.0)
    check("GM-01 [model] size: 9,000 JPY / USDJPY 150 (test assumption) = 60 USD; SL 10 pips, pointvalue 1 -> 60,000 units "
          "(GBP) = 0.60 lot; the same function as EURUSD (no GBP conversion)", ex is not None and round(ex) == 60000, str(ex))
    cases = {"major inside": (1.26980, 1.27020, (1.27, 3.0)), "top on minor": (1.26460, 1.26500, (1.265, 2.0)),
             "1 tick below major": (1.26960, 1.26999, (None, 0.0)), "major beats minor": (1.26460, 1.27010, (1.27, 3.0))}
    got = {k: es.rn_pick(b, t) for k, (b, t, _) in cases.items()}
    check("GM-02 [model] RN at GBPUSD levels (0.0100 / 0.0050, tick integers): inside, boundary, 1 tick outside, major first",
          all(got[k] == e for k, (_, _, e) in cases.items()), str(got))
    m = es.msg("確定", -1, 1.27000, 1.27060, 1.27000 - 1.5 * 0.00060, ticker="GBPUSD")
    check("GM-03 [model] alert text (RR 1.5): 【確定】GBPUSD｜SHORT, SL距離 6.0 pips, TP 1.26910, RR 1:1.5",
          m == "【確定】GBPUSD｜SHORT\nEntry：1.27000\nSL：1.27060\nSL距離：6.0 pips\nTP：1.26910\nRR：1:1.5", m)


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
