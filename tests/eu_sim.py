"""EU-1 / EU-2 fixtures — EURUSD port (ZoneEnginePracticalEURUSD / ZoneVisualEURUSD / ZoneStrategyEURUSD, OANDA:EURUSD 5M).

  ES : static — each file == its eu_build transform of the GBPJPY source and strips back byte for byte; every changed code
       line is a name / import, a USD price input, an RN line, the Zone geometry text, the position-size block or the pip
       constant; the Engine differs only by its library name and the tick-integer f_rnLevelIn (same exports); Visual and
       Strategy share the Zone inputs, ZoneCfg, feeds / requests, FVG Batch A and FVG scoring functions and import the
       same EURUSD library; the specified defaults (pips -> price) and every other default as in the GBPJPY files; RN
       0.0100 / 0.0050, no 0.125 / x8 rule, mintick-integer validation, ticker EURUSD, OFF; Entry / order / alert / label
       code identical to ZONE-ST-GBPJPY except the pip constant; no extra request; existing files unchanged except the two
       BTC fixtures' git-diff filters
  EM : models (Python ports, not TradingView runs) — pip conversions, JPY -> USD budget and lot floor (incl. the 9,000 JPY /
       USDJPY 150 / 10 pips -> 0.60 lot example), invalid / below-minimum, RN tick-integer search vs exact decimals at
       0.0100 / 0.0050 boundaries (and the old float search missing them), major-first, out of range, OFF, step validation,
       alert and label text

  (ES / EM pin EU-1 on the files with the EU-2 defaults reverted, == commit d3b68b7.)
  ED : EU-2 adopted defaults — strip_*2 gives d3b68b7 back; the only code delta is the specified default literals and
       their labels / tooltips; Visual and Strategy Zone defaults identical; the specified table values; every other
       input (MA / Swing / Accum detection and keep, Touch, Day/Swing distance, MA cluster, TP-zone RR, lots ...)
       unchanged; Engine / import / logic unchanged; only the EURUSD Visual / Strategy and their build / test changed

Evidence class: PINE_NOT_VERIFIED (library publish, TradingView compile / backtest / alerts / labels external).
"""
import difflib
import math
import os
import random
import re
import subprocess
import sys
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import eu_build as eb            # noqa: E402
import fvg_re10045_sim as fr     # noqa: E402

ROOT = eb.ROOT
BASE = "4c53b87"
rd = lambda p: open(os.path.join(ROOT, p), encoding="utf-8").read() if os.path.exists(os.path.join(ROOT, p)) else ""
show = lambda p, rev=BASE: subprocess.run(["git", "-C", ROOT, "show", f"{rev}:{p}"], capture_output=True, text=True).stdout
GE, GV, GS = rd(eb.ENG_SRC), rd(eb.VIS_SRC), rd(eb.STR_SRC)
EE, FV, FS = rd(eb.ENG_PATH), rd(eb.VIS_PATH), rd(eb.STR_PATH)
EU1 = "d3b68b7"
EV, ES = eb.strip_visual2(FV) or "", eb.strip_strategy2(FS) or ""     # EU-1 layer (EU-2 defaults reverted)
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


def code_only(src):
    return "\n".join(l for l in src.split("\n") if not l.lstrip().startswith("//"))


def func(src, head):
    i = src.index("\n" + head) + 1
    m = re.search(r"\n(?=\S)", src[i + len(head):])
    return src[i:i + len(head) + m.start() + 1]


def seg(src, b, e):
    return src[src.index(b):src.index(e)]


def input_decls(src):
    out, lines = {}, src.split("\n")
    for i, l in enumerate(lines):
        m = re.match(r"^(\w+)\s*=\s*input\.\w+\(", l)
        if m:
            j, txt = i + 1, l
            while j < len(lines) and lines[j].startswith("     ") and not re.match(r"^\w", lines[j]):
                txt += "\n" + lines[j]
                j += 1
            out[m.group(1)] = txt
    return out


def input_values(src):
    return {n: v.strip() for n, v in re.findall(r"^(\w+)\s*=\s*input\.\w+\(([^,]+),", src, re.M)}


def kw(decl, key):
    m = re.search(r"\b" + key + r"\s*=\s*([-\d.]+)", decl)
    return m.group(1) if m else None


def changed_code(a, b):
    ga, ba = code_only(a).split("\n"), code_only(b).split("\n")
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, ga, ba, autojunk=False).get_opcodes():
        if op != "equal":
            out += [l.strip() for l in ga[i1:i2] + ba[j1:j2]]
    return out


PIPS = {   # name: (pips, price default) — the specified EURUSD verification starting values
    "zoneHalfWidth": (2, "0.00020"), "clusterDist": (3, "0.00030"), "fvgMinWidth": (2, "0.00020"),
    "breakBuffer": (3, "0.00030"), "touchRearmDist": (6, "0.00060"), "flipConfirmDist": (6, "0.00060"),
    "dsDist": (2, "0.00020"), "maClusterDist": (12, "0.00120"), "slopeThrMod": (0.4, "0.00004"),
    "slopeThrStrong": (0.8, "0.00008")}
ST_PIPS = {"stBuffer": (3, "0.00030"), "stBEDist": (6, "0.00060")}
RN_INPUTS = {"rnMajorStep": "0.0100", "rnMinorStep": "0.0050", "rnMajorScore": "3.0", "rnMinorScore": "2.0", "enableRn": "false"}
DISPLAY_INPUTS = {"showZones", "showMaLines", "showLabels", "showDetailLbl", "maxZonesDraw", "zoneLeftBars", "zoneRightBars",
                  "colSupport", "colResistance", "colActive", "colBroken", "trWeak", "trMedium", "trStrong", "trVStrong",
                  "showScore", "showGeom", "showStats", "showWeak", "showMedium", "showStrong", "showVStrong", "showSupport",
                  "showResistance", "showBroken", "showActive"}
ZONE_FNS = ["f_fvcConf(int catCount) =>", "f_fvcStrengthOf(float score, bool hasHtf) =>", "f_fvcBase(int slot) =>",
            "f_fvcOverlap(float aTop, float aBot, float bTop, float bBot) =>", "f_fvcZoneDisplay(zn.Zone z) =>",
            "f_zpoBestFvg(zn.Zone z) =>"]


BTS_DOC_OLD = '''"""tests/btc_sim.py may differ from f9d9440 only by its BS-15 allow-list admitting the BTC Strategy files."""'''
BTS_DOC_NEW = '''"""tests/btc_sim.py may differ from f9d9440 only by its BS-15 allow-list admitting the BTC Strategy files and the
    --diff-filter=MDR on its git-diff checks."""'''
BTS_HELPER_OLD = '''    return old.count(BTC_SIM_OLD) == 1 and rd("tests/btc_sim.py") == old.replace(BTC_SIM_OLD, BTC_SIM_NEW)'''
BTS_HELPER_NEW = '''    # EU-1: its git-diff checks also gained --diff-filter=MDR (new files elsewhere are allowed; modified / deleted
    # existing files still fail), as in the other fixtures
    exp = old.replace(BTC_SIM_OLD, BTC_SIM_NEW)
    for c in ("BASE", "BTC2_COMMIT", "BTC1_COMMIT"):
        exp = exp.replace(f'["git", "-C", ROOT, "diff", "--name-only", {c}, "--"]',
                          f'["git", "-C", ROOT, "diff", "--name-only", "--diff-filter=MDR", {c}, "--"]')
    return old.count(BTC_SIM_OLD) == 1 and rd("tests/btc_sim.py") == exp'''


def allowed_zone_line(s):
    names = list(PIPS) + list(RN_INPUTS) + ["fvgDirMatch"]
    rn_new = code_only(seg(EV, "// 刻みの検証 (最小価格刻みの整数で比べる)", "// ---- 2.8 Cluster"))
    rn_old = code_only(seg(GV, "// 刻みの検証 (価格の算術だけ)", "// ---- 2.8 Cluster"))
    return (re.match(r"^(" + "|".join(names) + r")\s*=\s*input\.\w+\(", s) is not None
            or re.match(r'^(tooltip = )?".*"\)?( \+)?$', s) is not None
            or s in ('var string G_RN = "02 · Round Number (GBPJPY)"', 'var string G_RN = "02 · Round Number (EURUSD)"',
                     'zoneCfg.useRnSource          := enableRn and rnStepOK and syminfo.ticker == "GBPJPY"',
                     'zoneCfg.useRnSource          := enableRn and rnStepOK and syminfo.ticker == "EURUSD"',
                     eb.IMPORT_GBE.strip(), eb.IMPORT_EU.strip())
            or (s and (s in [x.strip() for x in rn_new.split("\n")] or s in [x.strip() for x in rn_old.split("\n")])))


def gate_static():
    check("ES-01 the three EURUSD files == eu_build transforms of the GBPJPY sources (rebuild identical) and strip back to "
          "ZoneEnginePracticalGBPJPY / ZoneVisualGBPJPY / ZoneStrategyGBPJPY byte for byte",
          all([EE, EV, ES]) and eb.build_engine() == EE and eb.build_visual() == FV and eb.build_strategy() == FS
          and eb.build_visual1() == EV and eb.build_strategy1() == ES
          and eb.strip_engine(EE) == GE and eb.strip_visual(FV) == GV and eb.strip_strategy(FS) == GS)
    kinds = ("header", "name", "input", "rn", "display", "size", "alert")
    check("ES-02 every edit is tagged (header / name / input / rn / display / size / alert) and unique; the Zone edits are the "
          "same objects in the Visual and the Strategy lists",
          all(k in kinds for k, _, _ in eb.ENGINE_EDITS + eb.VISUAL_EDITS + eb.STRATEGY_EDITS)
          and all(EE.count(b) == 1 for _, _, b in eb.ENGINE_EDITS) and all(EV.count(b) == 1 for _, _, b in eb.VISUAL_EDITS)
          and all(ES.count(b) == 1 for _, _, b in eb.STRATEGY_EDITS)
          and all(any(x is e for x in eb.VISUAL_EDITS) and any(x is e for x in eb.STRATEGY_EDITS) for e in eb.ZONE_EDITS))
    ce = changed_code(GE, EE)
    rn_old, rn_new = code_only(func(GE, "f_rnLevelIn(float zBot, float zTop, float step) =>")), \
        code_only(func(EE, "f_rnLevelIn(float zBot, float zTop, float step) =>"))
    exports = lambda t: re.findall(r"^export .*$", t, re.M)
    check("ES-03 Engine: the only code changes are the library name and the f_rnLevelIn body; every export (types, "
          "functions, signatures) is identical to ZoneEnginePracticalGBPJPY",
          all(l in ('library("ZoneEnginePracticalGBPJPY", overlay = true)', 'library("ZoneEnginePracticalEURUSD", overlay = true)')
              or l in [x.strip() for x in (rn_old + "\n" + rn_new).split("\n")] for l in ce)
          and exports(EE) == exports(GE) and len(exports(EE)) > 30
          and code_only(EE.replace(rn_new, rn_old)).replace("EURUSD", "GBPJPY") == code_only(GE), str(ce[:4]))
    geo = {'f_jpyGeom(zn.Zone z) =>', 'f_usdGeom(zn.Zone z) =>', 'txt := txt + "\\n" + f_jpyGeom(z)',
           'txt := txt + "\\n" + f_usdGeom(z)',
           'f_num(z.top, "#.000") + " - " + f_num(z.bottom, "#.000") + " | W " + f_num(z.top - z.bottom, "0.000") + "円"',
           'f_num(z.top, format.mintick) + " - " + f_num(z.bottom, format.mintick) + " | W " + f_num((z.top - z.bottom) / 0.0001, "0.0") + " pips"',
           'showGeom   = input.bool(true,  "Label: Zone 上下限 / 幅 (円) を表示", group = G_LBL)',
           'showGeom   = input.bool(true,  "Label: Zone 上下限 / 幅 (pips) を表示", group = G_LBL)'}
    cv = changed_code(GV, EV)
    bad_v = [l for l in cv if not (allowed_zone_line(l) or l in geo or re.match(r'^(title|shorttitle)\s*=\s*"[^"]*",$', l))]
    check("ES-04 Visual diff scope vs ZoneVisualGBPJPY: title / import, USD price inputs, RN lines, Zone geometry text only",
          cv and not bad_v, str(bad_v[:4]))
    size_new = code_only(func(ES, "f_stQty(int side, float ref, float sl) =>"))
    size_old = code_only(func(GS, "f_stQty(int side, float ref, float sl) =>"))
    cs = changed_code(GS, ES)
    bad_s = [l for l in cs if not (allowed_zone_line(l) or re.match(r'^(title|shorttitle)\s*=\s*"[^"]*",$', l)
                                   or re.match(r"^(stBuffer|stBEDist)\s*=\s*input\.float\(", l)
                                   or l in [x.strip() for x in (size_new + "\n" + size_old).split("\n")]
                                   or l in ("float ST_PIP = 0.01", "float ST_PIP = 0.0001"))]
    check("ES-05 Strategy diff scope vs ZoneStrategyGBPJPY: title / import, USD price inputs (Zone + SL Buffer / Breakeven), RN "
          "lines, f_stQty (JPY -> USD budget), pip constant only", cs and not bad_s, str(bad_s[:4]))
    vd, sd = input_decls(EV), input_decls(ES)
    zone_names = set(input_decls(ES[:ES.index("// ==== ZONE Strategy · Zone evaluation (begin)")]))
    cfg = lambda t: re.findall(r"^zoneCfg\.\w+\s*:=.*$", t, re.M)
    feed = lambda t: code_only(seg(t, "// ---- 3.2 Zone Engine Feed", "//  ★ 5分足専用: 5分足以外では zn.update"))
    fvg = lambda t: code_only(seg(t, "// ==== FVG Batch A (begin)", "// ==== FVG Batch A (end)"))
    rnv = lambda t: code_only(seg(t, "float rnMajT", "// ---- 2.8 Cluster"))
    check("ES-06 Visual / Strategy parity: identical Zone input declarations (all non-display inputs), every zoneCfg "
          "assignment, Source / Break / day-ID feeds with their 10 request.security calls, FVG Batch A, RN validation, the "
          "FVG scoring / boost functions; both import the same EURUSD library",
          zone_names == set(vd) - DISPLAY_INPUTS and all(vd[n] == sd[n] for n in zone_names)
          and cfg(EV) == cfg(ES) and len(cfg(ES)) > 60 and feed(EV) == feed(ES) and fvg(EV) == fvg(ES) and rnv(EV) == rnv(ES)
          and len(re.findall(r"request\.security\(", feed(ES) + fvg(ES))) == 10
          and all(code_only(func(EV, h)).rstrip() == code_only(func(ES, h)).rstrip() for h in ZONE_FNS)
          and re.findall(r"^import .*$", EV, re.M) == re.findall(r"^import .*$", ES, re.M) == [eb.IMPORT_EU.strip()])
    bad = []
    for src in (EV, ES):
        v, d = input_values(src), input_decls(src)
        for n, (_, price) in PIPS.items():
            mn, st = kw(d[n], "minval"), kw(d[n], "step")
            if not (v[n] == price and "(USD" in d[n] and "円" not in d[n] and float(mn) <= float(price)
                    and float(st) <= max(float(price), 0.00001) and 0 < float(st) <= 0.0001):
                bad.append(n)
    vs = input_values(ES)
    for n, (_, price) in ST_PIPS.items():
        if vs[n] != price:
            bad.append(n)
    check("ES-07 specified defaults in both files (USD, 1 pip = 0.0001): HW 0.00020, Cluster 0.00030, FVG 0.00020, Break "
          "0.00030, Touch 0.00060, Flip 0.00060, Day/Swing 0.00020, MA Cluster 0.00120, Slope 0.00004 / 0.00008; Strategy SL "
          "Buffer 0.00030, Breakeven 0.00060, Breakeven Stop OFF; minval / step on the EURUSD digits",
          not bad and vs["stBE"] == "false", str(bad))
    gv, gs_ = input_values(GV), input_values(GS)
    keep_v = [n for n in gv if n not in PIPS and n not in RN_INPUTS and input_decls(GV)[n] != input_decls(EV).get(n)
              and n not in ("fvgDirMatch", "showGeom")]
    keep_s = [n for n in gs_ if n not in PIPS and n not in RN_INPUTS and n not in ST_PIPS
              and input_decls(GS)[n] != input_decls(ES).get(n) and n != "fvgDirMatch"]
    check("ES-08 every other default as in the GBPJPY files (scores, ratios, days, bars, lengths, timeframes, modes): Accum "
          "Max / Edge Separate / Day/Swing Separate, FVG Direction Match OFF, Strong 9, Entry D, Long Only (switch kept), RR "
          "1.2, Zone TP OFF, 09:00-02:00 JST, 300,000 JPY / 3 % / 1 lot = 100,000 / step 0.01; strategy() options equal",
          not keep_v and not keep_s and set(gv) == set(input_values(EV)) and set(gs_) == set(vs)
          and (vs["accScoreMode"], vs["accEdgeMode"], vs["dsMode"], vs["fvgDirMatch"], vs["thrStrong"]) == ('"Max"', '"Separate"', '"Separate"', "false", "9.0")
          and (vs["stMode"], vs["stDir"], vs["stRR"], vs["stTpZone"]) == ('"D: 1M BOS Rebound"', '"Long Only"', "1.2", "false")
          and (vs["stSessTz"], vs["stSessStartH"], vs["stSessStartM"], vs["stSessEndH"], vs["stSessEndM"]) == ('"Asia/Tokyo"', "9", "0", "2", "0")
          and (vs["stCapBase"], vs["stRiskPct"], vs["stLotUnits"], vs["stLotStep"]) == ("300000.0", "3.0", "100000.0", "0.01")
          and 'options = ["Long Only", "Short Only", "Both"]' in ES
          and seg(ES, "strategy(", "import ").replace("EURUSD", "GBPJPY") == seg(GS, "strategy(", "import "),
          str((keep_v, keep_s)))
    cv_, cs_ = code_only(EV), code_only(ES)
    check("ES-09 RN: OFF; major 0.0100 (+3) / minor 0.0050 (+2); validation on mintick integers (minor > 0, major = integer "
          ">= 2 x minor, both mintick multiples), no 0.125 / x8 rule; ticker gate EURUSD; RN only adds to existing Zones "
          "(Engine RN block unchanged)",
          all(input_values(s)[n] == v for s in (EV, ES) for n, v in RN_INPUTS.items())
          and all("0.125" not in c and "* 8" not in c for c in (cv_, cs_))
          and "rnMinI > 0 and rnMajI >= 2 * rnMinI and rnMajI % math.max(rnMinI, 1) == 0" in cv_
          and 'syminfo.ticker == "EURUSD"' in cv_ and 'syminfo.ticker == "EURUSD"' in cs_
          and seg(code_only(EE), "    if c.useRnSource", "    int   cat") == seg(code_only(GE), "    if c.useRnSource", "    int   cat"))
    tail_e = code_only(seg(ES, "var string G_STA", "\n// ==== ZONE Strategy · Zone evaluation (end)"))
    tail_g = code_only(seg(GS, "var string G_STA", "\n// ==== ZONE Strategy · Zone evaluation (end)"))
    st_e, st_g = code_only(seg(ES, "var string G_ST =", "var string G_STQ")), code_only(seg(GS, "var string G_ST =", "var string G_STQ"))
    norm = lambda t: re.sub(r"^(stBuffer|stBEDist) = .*(\n     (tooltip = )?\".*)*$", r"\1", t, flags=re.M)
    check("ES-10 Entry / order / alert / label code identical to ZONE-ST-GBPJPY: modes A-D, candidates, 1M BOS wait / expiry / "
          "cancel, Track reuse, confirmed-bar processing, TP after fill, breakeven timing, provisional / confirmed alerts and "
          "labels differ only in the pip constant; the Entry input block only in SL Buffer / Breakeven; f_stQty is used by "
          "both the provisional evaluation and the order",
          tail_e == tail_g.replace("float ST_PIP = 0.01\n", "float ST_PIP = 0.0001\n") and norm(st_e) == norm(st_g)
          and cs_.count("f_stQty(") == 3 and "pvQty := pSide != 0 ? f_stQty(pSide, pPx, pSL) : na" in cs_
          and "float  pQty = f_stQty(side, ref, pSL)" in cs_
          and "if is5mChart and barstate.isconfirmed\n    zoneCountNow := zn.update(zoneEng, zoneCfg, zoneFeed)" in cs_)
    q = func(ES, "f_stQty(int side, float ref, float sl) =>")
    check("ES-11 size: budget (JPY) -> strategy.convert_to_symbol (no fixed USDJPY, no request); n = floor(budget USD / "
          "(distance x pointvalue x lot units x lot step) + 1e-9); na conversion / invalid distance / below one step -> na",
          "float budSym = stBudget > 0 ? strategy.convert_to_symbol(stBudget) : na" in q
          and "math.floor(budSym / (dist * syminfo.pointvalue * stepU) + 1e-9)" in q
          and "not na(dist) and dist > 0 and syminfo.pointvalue > 0 and stepU > 0 and not na(budSym) and budSym > 0" in q
          and "if n >= 1" in q and not re.search(r"\b1[45]0(\.0)?\b|usdjpy", q.lower()) and "currency_rate" not in cs_)
    fn = func(ES, "f_stAlertMsg(string kind, int side, float ePx, float sl, float tp) =>")
    lits = " ".join(re.findall(r'"([^"]*)"', fn))
    check("ES-12 alert / label text: ticker | side, Entry / SL / TP via format.mintick, SL距離 in pips with 1 pip = 0.0001, "
          "TP, RR, provisional note; no Entry Mode / quantity; Zone label geometry via format.mintick and pips (no 3-decimal "
          "format left)", "float ST_PIP = 0.0001" in cs_ and "str.tostring(risk / ST_PIP, \"0.0\") + \" pips\"" in fn
          and "str.tostring(v, format.mintick)" in ES and not re.search(r"Mode|数量|lot|qty", lits)
          and "※未確定：5分足確定時に不成立になる場合あり" in fn and "#.000" not in EV + ES and "0.000\"" not in cv_
          and "f_usdGeom(z)" in cv_ and cv_.count("f_usdGeom(z)") == 2)
    req = lambda t: re.findall(r"request\.\w+\(", code_only(t))
    check("ES-13 no extra request / loop / drawing: request.* lists equal to the GBPJPY files (Visual 10, Strategy 11), loops "
          "and plots equal; RE10045 eager-guard lint clean",
          req(EV) == req(GV) and len(req(EV)) == 10 and req(ES) == req(GS) and len(req(ES)) == 11
          and all(len(re.findall(p, cv_)) == len(re.findall(p, code_only(GV))) for p in (r"\bfor\b", r"\bwhile\b", r"plot\(", r"box\.new\("))
          and all(len(re.findall(p, cs_)) == len(re.findall(p, code_only(GS))) for p in (r"\bfor\b", r"\bwhile\b", r"plot\("))
          and fr.lint_eager_guards(cv_) == [] and fr.lint_eager_guards(cs_) == [] and fr.lint_eager_guards(code_only(EE)) == [])
    mod = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", "--diff-filter=MDR", BASE, "--"], capture_output=True,
                         text=True).stdout.split()
    exp_btc = show("tests/btc_sim.py")
    for c in ("BASE", "BTC2_COMMIT", "BTC1_COMMIT"):
        exp_btc = exp_btc.replace(f'["git", "-C", ROOT, "diff", "--name-only", {c}, "--"]',
                                  f'["git", "-C", ROOT, "diff", "--name-only", "--diff-filter=MDR", {c}, "--"]')
    exp_bts = show("tests/btcs_sim.py")
    for c in ("BASE", "BTS1_COMMIT"):
        exp_bts = exp_bts.replace(f'["git", "-C", ROOT, "diff", "--name-only", {c}, "--"]',
                                  f'["git", "-C", ROOT, "diff", "--name-only", "--diff-filter=MDR", {c}, "--"]')
    exp_bts = exp_bts.replace(BTS_HELPER_OLD, BTS_HELPER_NEW).replace(BTS_DOC_OLD, BTS_DOC_NEW)
    check(f"ES-14 existing files unchanged vs {BASE} (GBPJPY trio, BTC / USDJPY / Gold files, Engines, tests) except the two BTC "
          "fixtures, whose only change is --diff-filter=MDR on their git-diff checks (new files no longer fail them)",
          set(__import__("uj_build").drop_uj_tests(__import__("uj_build").drop_uj(mod, BASE))) <= {"tests/btc_sim.py", "tests/btcs_sim.py"}
          and __import__("uj_build").unadapt("tests/btc_sim.py", rd("tests/btc_sim.py")) == exp_btc
          and __import__("uj_build").unadapt("tests/btcs_sim.py", rd("tests/btcs_sim.py")) == exp_bts and exp_bts != show("tests/btcs_sim.py"), str(mod))


# ---- EU-2: adopted defaults -------------------------------------------------------------------------------------------
EU2_ZONE = {"zoneHalfWidth": "0.00020", "clusterDist": "0.00030", "breakBuffer": "0.00050", "flipConfirmDist": "0.00060",
            "slopeThrMod": "0.00002", "slopeThrStrong": "0.00004", "slopeBonusMode": '"Max"', "scoreMa1": "2.0",
            "scoreMa2": "2.0", "scoreHz1": "1.0", "scoreHz2": "2.0", "scoreHz3": "3.0", "scoreDayHL": "1.0",
            "scoreAcc1": "2.0", "scoreAcc2": "3.0", "scoreAcc3": "4.0", "accScoreMode": '"Max"', "accEdgeMode": '"Separate"',
            "dsMode": '"Separate"', "thrMedium": "5.0", "thrStrong": "9.0", "thrVStrong": "15.0", "fvgMinWidth": "0.00020",
            "fvgDirMatch": "false", "enableRn": "false"}
EU2_ST = {"stMode": '"B: Confirmed Rejection"', "stDir": '"Short Only"', "stRR": "1.5", "stBuffer": "0.00030",
          "stTpZone": "false", "stBE": "false", "stBEDist": "0.00060", "stUseSess": "true", "stSessTz": '"Asia/Tokyo"',
          "stSessStartH": "9", "stSessStartM": "0", "stSessEndH": "2", "stSessEndM": "0", "stCapBase": "300000.0",
          "stRiskPct": "3.0", "stLotUnits": "100000.0", "stLotStep": "0.01"}
EU2_CHANGED = {"breakBuffer", "slopeThrMod", "slopeThrStrong", "slopeBonusMode", "scoreDayHL", "scoreAcc1", "scoreAcc2",
               "scoreAcc3", "stMode", "stDir", "stRR"}
EU2_RELABEL = {"zoneHalfWidth", "clusterDist", "flipConfirmDist", "fvgMinWidth", "stBuffer"}


def gate_defaults():
    check("ED-01 EU-2: strip_visual2 / strip_strategy2 give the EU-1 files of commit d3b68b7 byte for byte; the Engine is "
          "byte-identical to d3b68b7; rebuilding gives the submitted files",
          EV == show(eb.VIS_PATH, EU1) and ES == show(eb.STR_PATH, EU1) and EE == show(eb.ENG_PATH, EU1)
          and eb.build_visual() == FV and eb.build_strategy() == FS
          and all(k in ("header", "default") for k, _, _ in eb.VISUAL_EDITS2 + eb.STRATEGY_EDITS2)
          and all(any(x is e for x in eb.VISUAL_EDITS2) and any(x is e for x in eb.STRATEGY_EDITS2) for e in eb.ZONE_DEFAULT_EDITS))
    bad = []
    for old, new, names in ((EV, FV, EU2_CHANGED | EU2_RELABEL), (ES, FS, EU2_CHANGED | EU2_RELABEL)):
        for l in changed_code(old, new):
            if not (re.match(r"^(" + "|".join(sorted(names)) + r")\s*=\s*input\.\w+\(", l)
                    or re.match(r'^(tooltip = )?".*"\)?( \+)?$', l)):
                bad.append(l)
    check("ED-02 the only code delta EU-1 -> EU-2 is the specified input declarations (default literal / label) and their "
          "tooltips; no logic, order, size, alert, label, Engine call, request or import change", not bad, str(bad[:4]))
    vv, vs = input_values(FV), input_values(FS)
    zb = [n for n, v in EU2_ZONE.items() if vv.get(n) != v or vs.get(n) != v]
    sb = [n for n, v in EU2_ST.items() if vs.get(n) != v]
    check("ED-03 table values in both files: HW 0.00020, Cluster 0.00030, Break 0.00050, Flip 0.00060, Slope 0.00002 / 0.00004, "
          "Slope aggregation Max, MA 2 / 2, Swing 1 / 2 / 3, Day H/L 1, Accum 2 / 3 / 4, Accum Max / Separate, Day/Swing "
          "Separate, 5 / 9 / 15, FVG 0.00020, FVG direction OFF, RN OFF; Strategy B, Short Only, RR 1.5, SL Buffer 0.00030, "
          "Zone TP OFF, BE OFF (0.00060), session ON Asia/Tokyo 09:00-02:00, 300,000 JPY / 3 % / 100,000 / 0.01",
          not zb and not sb and "initial_capital        = 300000," in FS and "currency               = currency.JPY," in FS,
          str((zb, sb)))
    vd, sd = input_decls(FV), input_decls(FS)
    zone_names = set(input_decls(FS[:FS.index("// ==== ZONE Strategy · Zone evaluation (begin)")]))
    check("ED-04 Visual / Strategy share every Zone input declaration (default, label, tooltip) after EU-2",
          zone_names == set(vd) - DISPLAY_INPUTS and all(vd[n] == sd[n] for n in zone_names))
    e1v, e1s = input_decls(EV), input_decls(ES)
    same = [n for n in set(e1v) | set(e1s) if n not in EU2_CHANGED | EU2_RELABEL
            and (e1v.get(n) != vd.get(n) or e1s.get(n) != sd.get(n))]
    keep_rel = [n for n in EU2_RELABEL if input_values(EV if n in e1v else ES).get(n) != (vv.get(n) if n in vv else vs.get(n))]
    opts = ['options = ["A: Touch Limit", "B: Confirmed Rejection", "C: Candle Pattern", "D: 1M BOS Rebound"]',
            'options = ["Long Only", "Short Only", "Both"]', 'options = ["Sum (per MA)", "Max"]']
    check("ED-05 everything else unchanged: MA TF / type / lengths / lookback / slope bonuses, Swing TFs / pivots, Accum "
          "TFs / keep counts / detection inputs, Touch / Day-Swing / MA-cluster distances, TP-zone Min / Max RR, BE trigger, "
          "lots ...; relabelled inputs keep their values; the Entry Mode / Direction / aggregation option lists are kept",
          not same and not keep_rel and all(o in FS for o in opts) and opts[2] in FV
          and vs["stTpMinRR"] == input_values(ES)["stTpMinRR"] and vs["stTpMaxRR"] == input_values(ES)["stTpMaxRR"],
          str((same, keep_rel)))
    co = code_only(FV) + code_only(FS)
    check("ED-06 tooltips / labels follow the values: Break 'USD・初期 5 pips', Slope '0.2 pips' / '0.4 pips', no stale "
          "'初期 3 pips' on Break or '0.8 pips'; adopted wording without an optimality claim",
          co.count("Break Buffer (USD・初期 5 pips)") == 2 and "Break Buffer (USD・初期 3 pips)" not in co
          and co.count("初期 0.00002 = 0.2 pips") == 2 and co.count("初期 0.00004 = 0.4 pips") == 2 and "0.8 pips" not in co
          and "最適値・将来の有効性を保証するものではない" in co and not re.search(r"最適値で|最適化済み|保証する。", co))
    mod = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", "--diff-filter=MDR", EU1, "--"], capture_output=True,
                         text=True).stdout.split()
    check("ED-07 vs d3b68b7 only the EURUSD Visual / Strategy and their build / test change (Engine, import, GBPJPY / BTC / "
          "USDJPY / Gold files untouched)", set(__import__("uj_build").drop_uj_tests(__import__("uj_build").drop_uj(mod, EU1))) <= {eb.VIS_PATH, eb.STR_PATH, "tests/eu_build.py", "tests/eu_sim.py"}
          and re.findall(r"^import .*$", FV + FS, re.M) == [eb.IMPORT_EU.strip()] * 2, str(mod))
    m = FS.replace('breakBuffer = input.float(0.00050', 'breakBuffer = input.float(0.00030')
    check("ED-08 mutation: a Strategy Break Buffer that no longer matches the Visual is detected",
          input_decls(m)["breakBuffer"] != vd["breakBuffer"] and eb.strip_strategy2(m) is None)


# ---- models -------------------------------------------------------------------------------------------------------------
PIP, MINTICK = 0.0001, 0.00001


def qty(side, ref, sl, usdjpy, pv=1.0, units=100000.0, step=0.01, cap=300000.0, pct=3.0):
    """port of the EURUSD f_stQty; convert_to_symbol(JPY budget) modelled as budget / USDJPY (None = na)."""
    budget = cap * pct / 100.0
    dist = (ref - sl) if side == 1 else (sl - ref)
    step_u = units * step
    bud = None if (usdjpy is None or usdjpy <= 0 or budget <= 0) else budget / usdjpy
    if dist is None or dist <= 0 or pv is None or pv <= 0 or step_u <= 0 or bud is None or bud <= 0:
        return None
    n = math.floor(bud / (dist * pv * step_u) + 1e-9)
    return n * step_u if n >= 1 else None


def rn_ticks(zbot, ztop, step, mintick=MINTICK):
    """port of the EURUSD f_rnLevelIn (tick integers)."""
    s_t = round(step / mintick)
    if s_t <= 0:
        return None
    b_t, t_t = math.ceil(zbot / mintick - 1e-6), math.floor(ztop / mintick + 1e-6)
    k1, k2 = math.ceil(b_t / s_t), math.floor(t_t / s_t)
    if k1 > k2:
        return None
    ctr = (b_t + t_t) / 2.0
    kc = max(k1, min(k2, math.floor(ctr / s_t)))
    lv = kc * s_t
    if kc + 1 <= k2 and (kc + 1) * s_t - ctr < ctr - lv:
        lv = (kc + 1) * s_t
    return lv * mintick


def rn_float(zbot, ztop, step):
    """the GBPJPY f_rnLevelIn (plain float division) — only to show why EURUSD needs the tick version."""
    k1, k2 = math.ceil(zbot / step), math.floor(ztop / step)
    return None if k1 > k2 else k1


def rn_exact(zbot, ztop, step):
    b, t, s = Decimal(zbot), Decimal(ztop), Decimal(step)
    return (b / s).to_integral_value(ROUND_CEILING) <= (t / s).to_integral_value(ROUND_FLOOR)


def rn_pick(zbot, ztop, enable=True, maj=0.0100, mnr=0.0050):
    if not enable:
        return None, 0.0
    lv = rn_ticks(zbot, ztop, maj)
    if lv is not None:
        return round(lv, 5), 3.0
    lv = rn_ticks(zbot, ztop, mnr)
    return (round(lv, 5), 2.0) if lv is not None else (None, 0.0)


def rn_step_ok(maj, mnr, mintick=MINTICK):
    maj_t, min_t = maj / mintick, mnr / mintick
    mj, mn = round(maj_t), round(min_t)
    return (mnr > 0 and abs(maj_t - mj) < 1e-6 and abs(min_t - mn) < 1e-6 and mn > 0 and mj >= 2 * mn
            and mj % max(mn, 1) == 0)


def fpx(v):
    return "-" if v is None else f"{round(v / MINTICK) * MINTICK:.5f}"


def frr(v):
    return f"{round(v, 2):.2f}".rstrip("0").rstrip(".")


def msg(kind, side, e, sl, tp, ticker="EURUSD"):
    risk = (e - sl) if side == 1 else (sl - e)
    ok = risk is not None and risk > 0
    rr = ((tp - e) if side == 1 else (e - tp)) / risk if ok and tp is not None else None
    return (f"【{kind}】{ticker}｜{'LONG' if side == 1 else 'SHORT'}"
            f"\nEntry：{fpx(e)}\nSL：{fpx(sl)}"
            f"\nSL距離：{(f'{risk / PIP:.1f} pips') if ok else '-'}"
            f"\nTP：{fpx(tp) if ok else '-'}"
            f"\nRR：{('1:' + frr(rr)) if rr is not None else '-'}"
            + ("\n※未確定：5分足確定時に不成立になる場合あり" if kind == "仮" else ""))


def gate_model():
    v = input_values(ES)
    conv = {n: round(float(v[n]) / PIP, 4) for n in list(PIPS) + list(ST_PIPS)}
    exp = {n: float(p) for n, (p, _) in {**PIPS, **ST_PIPS}.items()}
    check("EM-01 [model] pip conversion of the coded defaults (price / 0.0001) reproduces the table (2 / 3 / 2 / 3 / 6 / 6 / 2 / "
          "12 / 0.4 / 0.8 pips; SL Buffer 3, Breakeven 6)", conv == exp, str(conv))
    ex = qty(1, 1.10000, 1.09900, 150.0)
    check("EM-02 [model] 9,000 JPY / USDJPY 150 (test assumption) = 60 USD; SL 10 pips, pointvalue 1 -> 60 / (0.0010 x 1,000) "
          "= 60 steps = 60,000 units = 0.60 lot", ex is not None and round(ex) == 60000 and round(ex / 100000, 2) == 0.60, str(ex))
    inval = [qty(1, 1.1, 1.099, None), qty(1, 1.1, 1.099, 0.0), qty(1, 1.1, 1.1, 150.0), qty(1, 1.099, 1.1, 150.0),
             qty(1, 1.1, 1.099, 150.0, pv=0.0), qty(1, 1.1, 1.099, 150.0, step=0.0), qty(1, 1.10000, 1.00000, 150.0)]
    check("EM-03 [model] no order: conversion na / 0, distance 0 / wrong side, pointvalue 0, step 0, and below one lot step "
          "(SL 1,000 pips -> 0.6 steps)", all(q is None for q in inval), str(inval))
    rng, bad = random.Random(5), []
    for _ in range(100000):
        rate, dist = rng.uniform(80, 220), round(rng.uniform(0.00001, 0.0300), 5)
        q = qty(-1, 1.08000, 1.08000 + dist, rate)
        bud = 9000.0 / rate
        if q is not None:
            n = round(q / 1000)
            if abs(q / 1000 - n) > 1e-9 or q * dist > bud * (1 + 1e-9) or (n + 1) * 1000 * dist <= bud * (1 - 1e-9):
                bad.append((rate, dist, q))
        elif math.floor(bud / (dist * 1000)) >= 1 and math.floor(bud / (dist * 1000)) * 1000 * dist < bud * (1 - 1e-9):
            bad.append(("missed", rate, dist))
    check("EM-04 [model] 100k random Short cases: quantity on the 1,000-unit grid, expected SL loss <= budget (1e-9 slack of "
          "the floor), largest such quantity (floored, never rounded up)", not bad, str(bad[:3]))
    cases = {
        "major inside": (1.09980, 1.10020, (1.1, 3.0)), "bottom on major": (1.10000, 1.10040, (1.1, 3.0)),
        "top on major": (1.09960, 1.10000, (1.1, 3.0)), "minor only": (1.10480, 1.10520, (1.105, 2.0)),
        "top on minor": (1.10460, 1.10500, (1.105, 2.0)), "bottom on minor": (1.10500, 1.10540, (1.105, 2.0)),
        "1 tick below major": (1.09960, 1.09999, (None, 0.0)), "1 tick above minor": (1.10501, 1.10540, (None, 0.0)),
        "major beats minor": (1.09460, 1.10010, (1.1, 3.0)), "none": (1.10100, 1.10300, (None, 0.0)),
    }
    got = {k: rn_pick(b, t) for k, (b, t, _) in cases.items()}
    off = all(rn_pick(b, t, enable=False) == (None, 0.0) for b, t, _ in cases.values())
    check("EM-05 [model] RN (0.0100 +3 / 0.0050 +2): boundary inclusive on both edges, nothing 1 tick outside, major first "
          "when both qualify, one level per Zone; OFF -> nothing", all(got[k] == e for k, (_, _, e) in cases.items()) and off,
          str({k: v for k, v in got.items() if v != cases[k][2]}))
    rng, bad, old_miss = random.Random(9), [], 0
    for _ in range(200000):
        k = rng.randint(180, 260)
        lvl = round(k * 0.005, 5)
        hw = rng.choice([0.00020, 0.00030, 0.00045, 0.0010])
        ctr = round(lvl + rng.choice([-hw, hw, 0.0, rng.randint(-60, 60) * MINTICK]), 5)
        b, t = ctr - hw, ctr + hw                                  # float arithmetic like the Engine (center ± half width)
        for st in (0.0100, 0.0050):
            ex_ok = rn_exact(repr(round(b, 5)), repr(round(t, 5)), repr(st))
            if (rn_ticks(b, t, st) is not None) != ex_ok:
                bad.append((b, t, st))
            old_miss += (rn_float(b, t, st) is not None) != ex_ok
    check("EM-06 [model] tick-integer RN search == exact decimal search on the 0.00001 grid (200k zones built as center ± HW "
          "in float, levels at / near 0.0100 / 0.0050 multiples); the GBPJPY float search would misjudge some of them "
          "(non-vacuous)", not bad and old_miss > 0, str((bad[:3], old_miss)))
    okc = [rn_step_ok(0.0100, 0.0050), rn_step_ok(0.0100, 0.0050, 0.0001), rn_step_ok(0.0100, 0.0025), rn_step_ok(0.0050, 0.0010)]
    badc = [rn_step_ok(0.0100, 0.0), rn_step_ok(0.0050, 0.0050), rn_step_ok(0.0075, 0.0050), rn_step_ok(0.0100, 0.000015),
            rn_step_ok(0.0050, 0.0100)]
    check("EM-07 [model] RN step validation: 0.0100 / 0.0050 valid (mintick 0.00001 and 0.0001), 0.0100 / 0.0025 and 0.0050 / "
          "0.0010 valid; minor 0, major = minor, 1.5 x, off-mintick 0.000015 and minor > major rejected",
          all(okc) and not any(badc), str((okc, badc)))
    m = msg("確定", 1, 1.10000, 1.09900, 1.10000 + 1.2 * 0.00100)
    ms = msg("仮", -1, 1.08500, 1.08560, 1.08500 - 1.2 * 0.00060)
    check("EM-08 [model] alert / label text: Long Entry 1.10000 / SL 1.09900 -> 10.0 pips, TP 1.10120, RR 1:1.2; provisional "
          "Short 6.0 pips, TP 1.08428 + the 未確定 note; no mode / quantity",
          m == "【確定】EURUSD｜LONG\nEntry：1.10000\nSL：1.09900\nSL距離：10.0 pips\nTP：1.10120\nRR：1:1.2"
          and ms == "【仮】EURUSD｜SHORT\nEntry：1.08500\nSL：1.08560\nSL距離：6.0 pips\nTP：1.08428\nRR：1:1.2"
          "\n※未確定：5分足確定時に不成立になる場合あり", m + "\n" + ms)
    geo = fpx(1.10020) + " - " + fpx(1.09980) + " | W " + f"{(1.10020 - 1.09980) / PIP:.1f}" + " pips"
    check("EM-09 [model] Zone label geometry: 1.10020 - 1.09980 | W 4.0 pips (format.mintick 5 digits, width in pips)",
          geo == "1.10020 - 1.09980 | W 4.0 pips", geo)


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
