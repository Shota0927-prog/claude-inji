"""BTS-1 / BTS-2 fixtures — ZoneStrategyBTCUSD.pine (CRYPTO:BTCUSD 5M Strategy, provisional / confirmed alerts and labels).

  SB : static — exact, idempotent build from ZONE-ST-GBPJPY; strip_bts(file) == ZONE-ST-GBPJPY byte for byte; every
       changed code line is a Zone input / RN line (the BTC Visual's own edits), SL Buffer / Breakeven inputs, the
       position-size block, the alert SL-distance text or the title; Zone calculation identical to ZoneVisualBTCUSD
       (f9d9440): inputs, ZoneCfg, feeds / requests, confirmed-only Engine update, FVG Batch A, FVG scoring / boost
       functions, RN gate; Entry independent of display filters; defaults (D, Long Only, 30, 09:00-02:00 JST, no weekday
       filter, RR 1.2, Zone TP / BE off, 50 / 150 USD, 300,000 JPY, 3 %, step / min 0.01 [未検証]); Entry / order / alert
       / label code identical to ZONE-ST-GBPJPY; no extra request (conversion via strategy.convert_to_symbol);
       provisional evaluation read-only; data from syminfo.tickerid only; existing files unchanged vs f9d9440
  SM : models (Pine ports, not TradingView runs) — position size (JPY -> USD, floor, re-check, minimum, invalid), session
       boundaries 09:00 / 02:00 JST incl. weekends, alert / label text (USD), provisional / confirmed alert and label
       paths (provisional -> confirmed, provisional only, confirmed without provisional)
  (SB / SM checks pin BTS-1 on BTS = strip_bts2(file) == commit 88488dc.)
  SW : BTS-2 weekend exclusion — static delta (independent input default ON, session start day via hour / minute /
       dayofweek on time_close, folded into stSessOK so new entries, provisional / confirmed alerts and labels and the
       limit cancellation follow it; SL / TP / breakeven and Zone / FVG / BOS updates not gated; no request) and a model
       over whole weeks: the specified examples, Fri -> Sat and Sun -> Mon boundaries, session limit x weekend ON / OFF,
       changed session inputs (wrapping, non-wrapping, 24 h)

The A / B / C / D logic, Long / Short / Both, previous-confirmed candidate reference and the confirmed-1M-only D
processing are byte-identical to ZONE-ST-GBPJPY (SB-07); their models live in the existing st2 / st3 / stj / gbs / gbq /
gbn fixtures, which keep running on ZONE-ST-GBPJPY.

Evidence class: PINE_NOT_VERIFIED (TradingView compile / backtest / alerts / labels external).
"""
import datetime as dt
import difflib
import math
import os
import random
import re
import subprocess
import sys
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import btcs_build as sb          # noqa: E402
import btc_build as bb           # noqa: E402
import fvg_re10045_sim as fr     # noqa: E402

ROOT = sb.ROOT
BASE = "f9d9440"
rd = lambda p: open(os.path.join(ROOT, p), encoding="utf-8").read() if os.path.exists(os.path.join(ROOT, p)) else ""
GBS = rd(sb.SRC_PATH)
FULL = rd(sb.BTS_PATH)
BTS1_COMMIT = "88488dc"
BTS = sb.strip_bts2(FULL) or ""          # the BTS-1 file (BTS-2 weekend edits reverted)
VIS = rd(bb.BTC_PATH)
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


def code_only(src):
    return "\n".join(l for l in src.split("\n") if not l.lstrip().startswith("//"))


def func(src, head):
    """top-level function text from its header to the next non-indented line."""
    i = src.index("\n" + head) + 1
    m = re.search(r"\n(?=\S)", src[i + len(head):])
    return src[i:i + len(head) + m.start() + 1]


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


def seg(src, b, e):
    return src[src.index(b):src.index(e)]


DISPLAY_INPUTS = {"showZones", "showMaLines", "showLabels", "showDetailLbl", "maxZonesDraw", "zoneLeftBars", "zoneRightBars",
                  "colSupport", "colResistance", "colActive", "colBroken", "trWeak", "trMedium", "trStrong", "trVStrong",
                  "showScore", "showGeom", "showStats", "showWeak", "showMedium", "showStrong", "showVStrong", "showSupport",
                  "showResistance", "showBroken", "showActive"}
ZONE_FNS = ["f_fvcConf(int catCount) =>", "f_fvcStrengthOf(float score, bool hasHtf) =>", "f_fvcBase(int slot) =>",
            "f_fvcOverlap(float aTop, float aBot, float bTop, float bBot) =>", "f_fvcZoneDisplay(zn.Zone z) =>",
            "f_zpoBestFvg(zn.Zone z) =>"]
UPDATE = "if is5mChart and barstate.isconfirmed\n    zoneCountNow := zn.update(zoneEng, zoneCfg, zoneFeed)\n"
OLD_SL_LINE = '     "\\nSL距離：" + (okR ? str.tostring(risk / ST_PIP, "0.0") + " pips" : "-") +'
NEW_SL_LINE = '     "\\nSL距離：" + (okR ? str.tostring(risk, format.mintick) + " USD" : "-") +'


def allowed_code_line(line):
    s = line.strip()
    zone_inputs = ("zoneHalfWidth", "clusterDist", "fvgMinWidth", "slopeThrMod", "slopeThrStrong", "maClusterDist",
                   "touchRearmDist", "dsDist", "breakBuffer", "flipConfirmDist", "rnMajorStep", "rnMinorStep",
                   "enableRn", "fvgDirMatch", "stBuffer", "stBEDist", "stLotUnits", "stLotStep", "stQtyStep", "stQtyMin")
    size_block = code_only(seg(BTS, "float stBudget", "var string G_STA")) + "\n" + \
        code_only(seg(GBS, "float stBudget", "var string G_STA"))
    return (re.match(r"^(" + "|".join(zone_inputs) + r")\s*=\s*input\.\w+\(", s) is not None
            or re.match(r'^(tooltip = )?".*"\)?( \+)?$', s) is not None
            or re.match(r'^(title|shorttitle)\s*=\s*"[^"]*",$', s) is not None
            or s in ('var string G_RN = "02 · Round Number (GBPJPY)"', 'var string G_RN = "02 · Round Number (BTCUSD)"',
                     'zoneCfg.useRnSource          := enableRn and rnStepOK and syminfo.ticker == "GBPJPY"',
                     'zoneCfg.useRnSource          := enableRn and rnStepOK and syminfo.ticker == "BTCUSD"',
                     "float ST_PIP = 0.01", OLD_SL_LINE.strip(), NEW_SL_LINE.strip())
            or s.startswith('runtime.error("Round Number: 刻みが不正です')
            or (s and s in [x.strip() for x in size_block.split("\n")]))


BTC_SIM_OLD = '    new_ok = {bb.BTC_PATH, "tests/btc_build.py", "tests/btc_sim.py"}\n'
BTC_SIM_NEW = ('    new_ok = {bb.BTC_PATH, "tests/btc_build.py", "tests/btc_sim.py",\n'
               '              "ZoneStrategyBTCUSD.pine", "tests/btcs_build.py", "tests/btcs_sim.py"}   '
               '# BTC Strategy (BTS-1 / BTS-2, own fixture btcs_sim)\n')


def btc_sim_only_allowlist():
    """tests/btc_sim.py may differ from f9d9440 only by its BS-15 allow-list admitting the BTC Strategy files."""
    old = subprocess.run(["git", "-C", ROOT, "show", BASE + ":tests/btc_sim.py"], capture_output=True, text=True).stdout
    return old.count(BTC_SIM_OLD) == 1 and rd("tests/btc_sim.py") == old.replace(BTC_SIM_OLD, BTC_SIM_NEW)


def gate_static():
    check("SB-01 ZoneStrategyBTCUSD.pine == bts_transform(ZoneStrategyGBPJPY.pine); rebuild identical; strip_bts gives "
          "ZONE-ST-GBPJPY back byte for byte; strip_bts2 gives the BTS-1 file of commit 88488dc byte for byte",
          bool(BTS) and sb.build() == FULL and sb.build() == sb.build() and sb.strip_bts(FULL) == GBS
          and sb.bts_transform(sb.strip_bts(FULL)) == FULL and sb.bts1_transform(GBS) == BTS
          and BTS == subprocess.run(["git", "-C", ROOT, "show", BTS1_COMMIT + ":" + sb.BTS_PATH],
                                    capture_output=True, text=True).stdout)
    check("SB-02 edits tagged header / title / input / rn / entry / size / alert, each unique; the Zone edits are the BTC "
          "Visual's own btc_build.EDITS objects (kinds input / rn, all of them, same order)",
          all(k in ("header", "title", "input", "rn", "entry", "size", "alert") for k, _, _ in sb.EDITS)
          and all(BTS.count(b) == 1 for _, _, b in sb.EDITS)
          and sb.ZONE_EDITS == [e for e in bb.EDITS if e[0] in ("input", "rn")] and len(sb.ZONE_EDITS) == 15
          and all(any(x is e for x in sb.EDITS) for e in sb.ZONE_EDITS))
    ga, ba = code_only(GBS).split("\n"), code_only(BTS).split("\n")
    changed = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, ga, ba, autojunk=False).get_opcodes():
        if op != "equal":
            changed += ga[i1:i2] + ba[j1:j2]
    bad = [l for l in changed if not allowed_code_line(l)]
    check("SB-03 diff scope vs ZONE-ST-GBPJPY: every changed code line is a Zone input / RN line, SL Buffer / Breakeven, the "
          "position-size block, the alert SL-distance text or the title", changed and not bad, str(bad[:4]))
    vd, sd = input_decls(VIS), input_decls(BTS)
    zone_names = set(input_decls(BTS[:BTS.index("// ==== ZONE Strategy · Zone evaluation (begin)")]))
    diffs = [n for n in zone_names if vd.get(n) != sd.get(n)]
    check("SB-04 every Zone-related input declaration (default / label / minval / step / tooltip / group) is identical to "
          "ZoneVisualBTCUSD; the Strategy has exactly the Visual's non-display inputs before the Zone evaluation",
          not diffs and zone_names == set(vd) - DISPLAY_INPUTS, str((diffs, zone_names ^ (set(vd) - DISPLAY_INPUTS))))
    cfg = lambda t: re.findall(r"^zoneCfg\.\w+\s*:=.*$", t, re.M)
    feed = lambda t: code_only(seg(t, "// ---- 3.2 Zone Engine Feed", "//  ★ 5分足専用: 5分足以外では zn.update"))
    fvg = lambda t: code_only(seg(t, "// ==== FVG Batch A (begin)", "// ==== FVG Batch A (end)"))
    head = lambda t: code_only(seg(t, "bool is5mChart", "// ============================================================================\n// 01-2."))
    rn = lambda t: code_only(seg(t, "float rnRatio", "// ---- 2.8 Cluster"))
    check("SB-05 Zone calculation identical to ZoneVisualBTCUSD: import, 5M gate / constants, every zoneCfg assignment (incl. "
          "RN gate ticker BTCUSD), Source / Break / day-ID feeds and their 10 request.security calls, the confirmed-only "
          "zn.update, FVG Batch A (fetch / store / fill / expiry), RN step validation",
          re.findall(r"^import .*$", BTS, re.M) == re.findall(r"^import .*$", VIS, re.M)
          and cfg(BTS) == cfg(VIS) and len(cfg(BTS)) > 60 and feed(BTS) == feed(VIS) and fvg(BTS) == fvg(VIS)
          and UPDATE in BTS and UPDATE in VIS and rn(BTS) == rn(VIS)
          and head(BTS).replace("\n//", "") == head(VIS)[:len(head(BTS))].replace("\n//", "")
          and len(re.findall(r"request\.security\(", feed(BTS) + fvg(BTS))) == 10)
    check("SB-06 FVG scoring and overlap-limited boost: f_fvcConf / f_fvcStrengthOf / f_fvcBase / f_fvcOverlap / "
          "f_fvcZoneDisplay / f_zpoBestFvg are code-identical to ZoneVisualBTCUSD; f_stZoneEval builds candidates from them",
          all(code_only(func(BTS, h)).rstrip() == code_only(func(VIS, h)).rstrip() for h in ZONE_FNS)
          and "[dScore, dStr] = f_fvcZoneDisplay(z)\n    int  best    = f_zpoBestFvg(z)" in BTS)
    co = code_only(BTS)
    check("SB-07 Entry eligibility independent of display filters: no show* / maxZonesDraw / colour input in the Strategy",
          not re.search(r"\b(" + "|".join(sorted(DISPLAY_INPUTS)) + r")\b", co))
    v = input_values(BTS)
    sess = func(BTS, "f_stInSession(int t) =>")
    check("SB-08 Entry defaults: D: 1M BOS Rebound, Long Only, BOS wait 30 confirmed 1M bars, session ON Asia/Tokyo 09:00 - "
          "02:00 (no weekday filter anywhere -> weekends included), RR 1.2, Zone TP OFF, Breakeven OFF, SL Buffer 50 / "
          "Breakeven 150 USD [未検証]",
          v["stMode"] == '"D: 1M BOS Rebound"' and v["stDir"] == '"Long Only"' and v["stDWait"] == "30"
          and v["stUseSess"] == "true" and v["stSessTz"] == '"Asia/Tokyo"' and (v["stSessStartH"], v["stSessStartM"],
                                                                               v["stSessEndH"], v["stSessEndM"]) == ("9", "0", "2", "0")
          and v["stRR"] == "1.2" and v["stTpZone"] == "false" and v["stBE"] == "false" and v["stBuffer"] == "50.0"
          and v["stBEDist"] == "150.0" and "[未検証] SL Buffer (USD)" in BTS and "[未検証] Breakeven Trigger (USD)" in BTS
          and not re.search(r"dayofweek|input\.session|session\.", co) and "hour(t, stSessTz)" in sess)
    check("SB-09 capital / size defaults: strategy(initial_capital 300000, currency JPY, calc_on_every_tick true, "
          "process_orders_on_close false, pyramiding 0); 元金基準額 300,000 円, 損失予算 3 %, 数量刻み / 最小数量 0.01 [未検証]; "
          "no margin setting added (same strategy() options as ZONE-ST-GBPJPY)",
          "initial_capital        = 300000," in BTS and "currency               = currency.JPY," in BTS
          and "calc_on_every_tick     = true," in BTS and "process_orders_on_close = false," in BTS
          and v["stCapBase"] == "300000.0" and v["stRiskPct"] == "3.0" and v["stQtyStep"] == "0.01" and v["stQtyMin"] == "0.01"
          and "[未検証] 数量刻み (BTC)" in BTS and "[未検証] 最小数量 (BTC)" in BTS and "margin" not in co
          and seg(BTS, "strategy(", "import ").replace("BTCUSD", "GBPJPY") == seg(GBS, "strategy(", "import "))
    tail_b = code_only(seg(BTS, "var string G_STA", "\n// ==== ZONE Strategy · Zone evaluation (end)"))
    tail_g = code_only(seg(GBS, "var string G_STA", "\n// ==== ZONE Strategy · Zone evaluation (end)"))
    st_b = code_only(seg(BTS, "var string G_ST =", "var string G_STQ"))
    st_g = code_only(seg(GBS, "var string G_ST =", "var string G_STQ"))
    norm_st = lambda t: re.sub(r"^(stBuffer|stBEDist) = .*(\n     tooltip = .*)?$", r"\1", t, flags=re.M)
    check("SB-10 Entry / order / alert / label code identical to ZONE-ST-GBPJPY: from the alert inputs to the end (modes A / "
          "B / C / D, 1M BOS, cancellation, priorities, re-entry, order sequence, TP after fill, breakeven, provisional / "
          "confirmed alerts, labels) only the SL-distance text and the removed ST_PIP differ; the Entry input block differs "
          "only in SL Buffer / Breakeven",
          tail_b == tail_g.replace("float ST_PIP = 0.01\n", "").replace(OLD_SL_LINE, NEW_SL_LINE)
          and norm_st(st_b) == norm_st(st_g) and "ST_PIP" not in co)
    req = lambda t: re.findall(r"request\.\w+\(", code_only(t))
    qf = func(BTS, "f_stQty(int side, float ref, float sl) =>")
    check("SB-11 no additional request: request.* calls identical to ZONE-ST-GBPJPY (10 security + 1 security_lower_tf for "
          "D); the JPY -> USD conversion is strategy.convert_to_symbol inside f_stQty only (called on an order / "
          "provisional evaluation), no request.currency_rate",
          req(BTS) == req(GBS) and len(req(BTS)) == 11 and co.count("strategy.convert_to_symbol(") == 1
          and "strategy.convert_to_symbol(stBudget)" in qf and "currency_rate" not in co and co.count("f_stQty(") == 3)
    check("SB-12 size formula: budget (JPY) -> convert_to_symbol; loss per unit = distance x syminfo.pointvalue; floor to the "
          "step with 1e-9 slack; re-check n x step x loss <= budget (else one step less); >= minimum; any invalid input -> na",
          "float lossU = dist * syminfo.pointvalue" in qf and "math.floor(budSym / (lossU * stQtyStep) + 1e-9)" in qf
          and "if n * stQtyStep * lossU > budSym" in qf and "n := n - 1" in qf
          and "if n >= 1 and n * stQtyStep >= stQtyMin * (1 - 1e-9)" in qf
          and "not na(dist) and dist > 0 and syminfo.pointvalue > 0 and stQtyStep > 0 and not na(budSym) and budSym > 0" in qf
          and "if not skipRef and not na(pQty)" in BTS and "stLot" not in co)
    fn = func(BTS, "f_stAlertMsg(string kind, int side, float ePx, float sl, float tp) =>")
    lits = " ".join(re.findall(r'"([^"]*)"', fn))
    check("SB-13 alert / label text: 【kind】ticker｜LONG/SHORT, Entry / SL / TP via format.mintick, SL距離 = price difference "
          "with format.mintick + ' USD', RR 1:x (0.##), provisional note; no quantity / lot / loss % / Entry Mode; the "
          "confirmed alert and label use the same arguments",
          NEW_SL_LINE.strip() in fn and "str.tostring(v, format.mintick)" in BTS and '"1:" + str.tostring(rr, "0.##")' in fn
          and "※未確定：5分足確定時に不成立になる場合あり" in fn
          and not re.search(r"数量|lot|%|Mode|pips|qty", lits)
          and co.count('f_stAlertMsg("確定", side, stModeA ? oL : close, oSL, tpRef)') == 2
          and co.count('f_stAlertMsg("仮", pSide, pPx, pSL, pTP)') == 2)
    pe = code_only(func(BTS, "f_stProvEval() =>"))
    globals_ = re.findall(r"^var(?:ip)?\s+(?:[\w.<>, ]+\s+)?(\w+)\s*=", co, re.M)
    pv = code_only(BTS[BTS.index("varip int stProvBar = na\n"):])
    check("SB-14 provisional evaluation read-only: f_stProvEval writes no global var (only locals), no strategy.* / "
          "map.put / array.push / set / remove; the provisional alert / label block writes only stProvBar and the label; "
          "it reads the previous confirmed candidates (stPrev), wait copies and TP edges",
          not re.search(r"\b(" + "|".join(globals_) + r")\s*:=", pe) and "strategy." not in pe
          and not re.search(r"map\.put|array\.(push|set|remove|clear|shift|insert)\(", pe)
          and "strategy." not in pv and not re.search(r"\b(" + "|".join(g for g in globals_ if g != "stProvBar") + r")\s*:=", pv)
          and "int   m   = array.size(stPrev)" in pe and fr.lint_eager_guards(co) == [])
    conf = code_only(seg(BTS, "if is5mChart and barstate.isconfirmed\n    // (1)", "plot(stZones"))
    check("SB-15 candidates from the previous confirmed state: B / C use stPrev, D registers waits from stPrev on confirmed "
          "1M bars (processed once, m1LastT), A uses this bar's updated list; stPrev / TP edges are replaced at the end of "
          "the confirmed block only; the D 1M data is request.security_lower_tf (closed 1M bars inside the 5M bar)",
          "array<StCand> src = stModeA ? cur : stModeD ? dSrc : stPrev" in conf and "StCand c = array.get(stPrev, k)" in conf
          and "if na(m1LastT) or tj > m1LastT" in conf and conf.rstrip().endswith("stTpDnPrev := tpDn")
          and co.count("stPrev := cur") == 1 and 'request.security_lower_tf(syminfo.tickerid, "1", [time, high, low, close])' in co)
    X = "BIN" + "ANCE"
    reqs = re.findall(r"request\.(\w+)\(([^,]+),", co)
    check("SB-16 data only from syminfo.tickerid (11 requests), no exchange-prefixed literal, no " + X + " text",
          len(reqs) == 11 and all(a.strip() == "syminfo.tickerid" for _, a in reqs)
          and not re.search(r'"[A-Z0-9_]+:[A-Z0-9_.!]+"', co) and X not in BTS and "CRYPTO:BTCUSD" in BTS)
    out = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", BASE, "--"], capture_output=True, text=True).stdout.split()
    new_ok = {sb.BTS_PATH, "tests/btcs_build.py", "tests/btcs_sim.py"}
    out2 = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", BTS1_COMMIT, "--"], capture_output=True,
                          text=True).stdout.split()
    check(f"SB-17 existing files unchanged vs {BASE} (GBPJPY / USDJPY / Gold, Engines, BTC Visual and its build / sim, tests); "
          "only the BTC Strategy files differ (also vs 88488dc for BTS-2); tests/btc_sim.py differs only by its BS-15 allow-list "
          "line admitting the BTC Strategy files", subprocess.run(["git", "-C", ROOT, "cat-file", "-e", BASE]).returncode == 0
          and not [f for f in out if f not in new_ok | {"tests/btc_sim.py"}]
          and not [f for f in out2 if f not in new_ok | {"tests/btc_sim.py"}] and btc_sim_only_allowlist(), str((out, out2)))
    m1 = BTS.replace("if n * stQtyStep * lossU > budSym", "if false")
    m2 = BTS.replace('stDir = input.string("Long Only"', 'stDir = input.string("Both"')
    m3 = BTS.replace("zoneHalfWidth = input.float(50.0", "zoneHalfWidth = input.float(0.05")
    check("SB-18 mutation: removing the budget re-check, a different default direction and a Zone input that no longer "
          "matches the Visual are each detected", "if n * stQtyStep * lossU > budSym" not in m1
          and input_values(m2)["stDir"] != '"Long Only"' and input_decls(m3)["zoneHalfWidth"] != vd["zoneHalfWidth"]
          and sb.strip_bts(m3) is None)


# ---- models -------------------------------------------------------------------------------------------------------------
def qty(side, ref, sl, usdjpy, pv=1.0, step=0.01, qmin=0.01, cap=300000.0, pct=3.0):
    """port of f_stQty; convert_to_symbol(JPY budget) modelled as budget / USDJPY (None = no rate)."""
    budget = cap * pct / 100.0
    dist = (ref - sl) if side == 1 else (sl - ref)
    bud = None if (usdjpy is None or usdjpy <= 0 or budget <= 0) else budget / usdjpy
    if dist is None or dist <= 0 or pv is None or pv <= 0 or step <= 0 or bud is None or bud <= 0:
        return None
    loss = dist * pv
    n = math.floor(bud / (loss * step) + 1e-9)
    if n * step * loss > bud:
        n -= 1
    return n * step if n >= 1 and n * step >= qmin * (1 - 1e-9) else None


def in_session(t_close, sh=9, sm=0, eh=2, em=0, tz="Asia/Tokyo"):
    """port of f_stInSession(time_close)."""
    lt = t_close.astimezone(ZoneInfo(tz))
    mins, s, e = lt.hour * 60 + lt.minute, sh * 60 + sm, eh * 60 + em
    return True if s == e else (s <= mins < e) if s < e else (mins >= s or mins < e)


MINTICK = 0.01


def fpx(v):
    return "-" if v is None else f"{round(v / MINTICK) * MINTICK:.2f}"


def frr(v):
    return f"{round(v, 2):.2f}".rstrip("0").rstrip(".")


def msg(kind, side, e, sl, tp, ticker="BTCUSD"):
    """port of f_stAlertMsg (BTC: SL距離 = price difference, format.mintick + ' USD')."""
    risk = (e - sl) if side == 1 else (sl - e)
    ok = risk is not None and risk > 0
    rr = ((tp - e) if side == 1 else (e - tp)) / risk if ok and tp is not None else None
    return (f"【{kind}】{ticker}｜{'LONG' if side == 1 else 'SHORT'}"
            f"\nEntry：{fpx(e)}\nSL：{fpx(sl)}"
            f"\nSL距離：{(fpx(risk) + ' USD') if ok else '-'}"
            f"\nTP：{fpx(tp) if ok else '-'}"
            f"\nRR：{('1:' + frr(rr)) if rr is not None else '-'}"
            + ("\n※未確定：5分足確定時に不成立になる場合あり" if kind == "仮" else ""))


def gate_model():
    ex = [qty(1, 65100.00, 64950.00, 150.0), qty(1, 65100.00, 64700.00, 150.0), qty(1, 65100.00, 58100.00, 150.0),
          qty(-1, 65000.00, 65180.00, 145.0)]
    check("SM-01 [model] size examples (budget 9,000 JPY): USDJPY 150 -> 60 USD; SL distance 150 -> 0.40 BTC (loss 60.00 USD); "
          "400 -> 0.15 BTC (60.00); 7,000 -> 0.0086 < 0.01 -> no order; Short, USDJPY 145 -> 62.07 USD, distance 180 -> 0.34 "
          "BTC (61.20 USD)", [None if q is None else round(q, 8) for q in ex] == [0.40, 0.15, None, 0.34], str(ex))
    inval = [qty(1, 65100.0, 64950.0, None), qty(1, 65100.0, 64950.0, 0.0), qty(1, 65000.0, 65000.0, 150.0),
             qty(1, 64900.0, 65000.0, 150.0), qty(1, 65100.0, 64950.0, 150.0, pv=0.0), qty(1, 65100.0, 64950.0, 150.0, pv=None),
             qty(1, 65100.0, 64950.0, 150.0, step=0.0)]
    check("SM-02 [model] invalid -> no order: conversion na / 0, distance 0 / wrong side, pointvalue 0 / na, step 0",
          all(q is None for q in inval), str(inval))
    rng, bad = random.Random(11), []
    for _ in range(100000):
        rate = rng.uniform(80, 220)
        dist = round(rng.uniform(1, 3000), 2)
        step = rng.choice([0.01, 0.001, 0.1, 0.0001])
        qmin = rng.choice([step, step * 2, 0.01])
        pv = rng.choice([1.0, 1.0, 0.1, 10.0])
        q = qty(1, 65000.0, 65000.0 - dist, rate, pv, step, qmin)
        bud = 9000.0 / rate
        n_max = math.floor(bud / (dist * pv * step))
        if q is not None:
            if q * dist * pv > bud * (1 + 1e-12) or q < qmin * (1 - 1e-9) or abs(q / step - round(q / step)) > 1e-6:
                bad.append(("over/grid", rate, dist, step, q))
            if (round(q / step) + 1) * step * dist * pv <= bud * (1 - 1e-9):
                bad.append(("not max", rate, dist, step, q))
        elif n_max >= 1 and n_max * step >= qmin * (1 + 1e-9) and n_max * step * dist * pv < bud * (1 - 1e-9):
            bad.append(("missed", rate, dist, step, qmin))
    check("SM-03 [model] 100k random cases: quantity is on the step grid, >= minimum, expected SL loss <= budget (re-check), "
          "and the largest such quantity (floor, never rounded up); below minimum -> no order", not bad, str(bad[:3]))
    J = ZoneInfo("Asia/Tokyo")
    t = lambda y, mo, d, h, mi: dt.datetime(y, mo, d, h, mi, tzinfo=J)
    cases = {"08:55": (t(2026, 10, 10, 8, 55), False), "09:00": (t(2026, 10, 10, 9, 0), True),
             "09:05": (t(2026, 10, 10, 9, 5), True), "23:55 Sat": (t(2026, 10, 10, 23, 55), True),
             "00:00 Sun": (t(2026, 10, 11, 0, 0), True), "01:55 Sun": (t(2026, 10, 11, 1, 55), True),
             "02:00 Sun": (t(2026, 10, 11, 2, 0), False), "02:05": (t(2026, 10, 11, 2, 5), False),
             "05:00 Mon": (t(2026, 10, 12, 5, 0), False), "12:00 Sun": (t(2026, 10, 11, 12, 0), True)}
    got = {k: in_session(v[0]) for k, v in cases.items()}
    check("SM-04 [model] session (bar close time, JST): 08:55 out, 09:00 in, 01:55 in, 02:00 out (end exclusive), 02:05 / "
          "05:00 out; Saturday / Sunday treated like weekdays (no weekday filter)",
          all(got[k] == v[1] for k, v in cases.items()), str({k: v for k, v in got.items() if v != cases[k][1]}))
    m = msg("確定", 1, 65100.00, 64950.00, 65100.00 + 1.2 * 150.00)
    check("SM-05 [model] confirmed Long text: Entry 65100.00, SL 64950.00, SL距離 150.00 USD, TP 65280.00, RR 1:1.2 (no qty / "
          "loss % / mode)", m == "【確定】BTCUSD｜LONG\nEntry：65100.00\nSL：64950.00\nSL距離：150.00 USD\nTP：65280.00\nRR：1:1.2", m)
    ms = msg("仮", -1, 65000.00, 65180.00, 65000.00 - 1.2 * 180.00)
    check("SM-06 [model] provisional Short text: risk = SL - Entry = 180.00 USD, TP 64784.00, RR 1:1.2 + the 未確定 note",
          ms == "【仮】BTCUSD｜SHORT\nEntry：65000.00\nSL：65180.00\nSL距離：180.00 USD\nTP：64784.00\nRR：1:1.2"
          "\n※未確定：5分足確定時に不成立になる場合あり", ms)
    bad = msg("確定", 1, 65000.0, 65000.0, 65180.0) + msg("確定", 1, 65000.0, 64900.0, None)
    check("SM-07 [model] invalid values shown as '-' (risk <= 0, TP na)", "SL距離：-" in bad and "TP：-" in bad
          and "RR：-" in bad and "nan" not in bad)

    def run(bars, alert_on=True, label_on=True):
        """port of the provisional / confirmed alert and label gating (one bar = list of (confirmed, prov, conf))."""
        prov_bar, sent_p, sent_c, frames, conf_lbls = None, [], [], [], []
        for b, ticks in enumerate(bars):
            for confirmed, prov, conf in ticks:
                if confirmed:
                    if conf is not None:                      # order branch: alert + label, independent of prov_bar
                        sent_c.append((b, msg("確定", *conf)))
                        conf_lbls.append((b, msg("確定", *conf)))
                    frames.append((b, ""))                    # provisional label hidden on the confirmed tick
                    continue
                need_a = alert_on and (prov_bar is None or prov_bar != b)
                need_l = label_on
                ok = (need_a or need_l) and prov is not None
                if need_a and ok:
                    prov_bar = b
                    sent_p.append((b, msg("仮", *prov)))
                frames.append((b, msg("仮", *prov) if (need_l and ok) else ""))
        return sent_p, sent_c, frames, conf_lbls
    P1, P2, C1 = (1, 65100.0, 64950.0, 65280.0), (1, 65120.0, 64950.0, 65324.0), (1, 65110.0, 64950.0, 65302.0)
    bars = [[(False, None, None), (False, P1, None), (False, P2, None), (True, None, C1)],     # provisional -> confirmed
            [(False, P1, None), (False, None, None), (True, None, None)],                     # provisional only
            [(False, None, None), (True, None, C1)]]                                          # confirmed without provisional
    sp, sc, fr_, cl = run(bars)
    check("SM-08 [model] paths: provisional -> confirmed (one provisional alert, label updated then hidden at close, "
          "confirmed alert + label), provisional only (alert, label hidden when invalid and at close, no confirmed), "
          "confirmed without provisional (confirmed alert + label); the provisional sent state never suppresses the "
          "confirmed alert",
          [b for b, _ in sp] == [0, 1] and [b for b, _ in sc] == [0, 2] and [b for b, _ in cl] == [0, 2]
          and [f for b, f in fr_ if b == 0][1:3] == [msg("仮", *P1), msg("仮", *P2)] and [f for b, f in fr_ if b == 0][3] == ""
          and [f for b, f in fr_ if b == 1] == [msg("仮", *P1), "", ""] and sc[0][1] == cl[0][1], str(fr_))
    sp0, sc0, fr0, _ = run(bars, alert_on=False)
    sp1, sc1, fr1, _ = run(bars, label_on=False)
    check("SM-09 [model] provisional alert OFF -> labels unchanged, confirmed unchanged; label OFF -> alerts unchanged, no "
          "provisional label", sp0 == [] and fr0 == fr_ and sc0 == sc and sp1 == sp and all(f == "" for _, f in fr1))


# ---- BTS-2: weekend exclusion -------------------------------------------------------------------------------------------
def gate_weekend():
    ga, ba = code_only(BTS).split("\n"), code_only(FULL).split("\n")
    rem, add = [], []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, ga, ba, autojunk=False).get_opcodes():
        if op != "equal":
            rem += [l.strip() for l in ga[i1:i2]]
            add += [l.strip() for l in ba[j1:j2]]
    exp_add = ['stNoWkend = input.bool(true, "Exclude Weekend New Entries (セッション開始日が土日)", group = G_STS,',
               "f_stSessDow(int t) =>", "int mins = hour(t, stSessTz) * 60 + minute(t, stSessTz)",
               "int s    = stSessStartH * 60 + stSessStartM", "int e    = stSessEndH * 60 + stSessEndM",
               "dayofweek(s >= e and mins < e ? t - 86400000 : t, stSessTz)", "int  stSessDow = f_stSessDow(time_close)",
               "bool stWkdOK   = not stNoWkend or (stSessDow != dayofweek.saturday and stSessDow != dayofweek.sunday)",
               "bool stSessOK  = (not stUseSess or f_stInSession(time_close)) and stWkdOK"]
    tips = [l for l in add if l.startswith(("tooltip = ", '"'))]
    check("SW-01 BTS-2 code delta vs BTS-1 (88488dc): the weekend input (+ tooltip), f_stSessDow, stSessDow / stWkdOK and "
          "stSessOK now AND-ed with stWkdOK; the old stSessOK line is the only removed line; f_stInSession unchanged",
          rem == ["bool stSessOK = not stUseSess or f_stInSession(time_close)"]
          and sorted(l for l in add if l not in tips) == sorted(exp_add) and len(tips) == 3
          and func(FULL, "f_stInSession(int t) =>") == func(BTS, "f_stInSession(int t) =>"), str((rem, add)))
    co, co1 = code_only(FULL), code_only(BTS)
    uses = lambda t: re.findall(r"^.*\bstSessOK\b.*$", t, re.M)
    check("SW-02 scope: stSessOK is used exactly where it was (limit cancellation `not pendOK or not stSessOK`, new-entry "
          "gate (4) whose order branch sends the confirmed alert / label, provisional gate stPvGate, data-window plot), so "
          "the weekend rule reaches all of them; SL / TP / breakeven ((1) fill check, (2b), (2c)) and the Zone / FVG / D 1M "
          "processing do not read stSessOK / stWkdOK",
          uses(co)[1:] == uses(co1)[1:] and len(uses(co)) == 5
          and "    if oState == 1 and (not pendOK or not stSessOK)" in co and "    if oState == 0 and not cancelBar and stSessOK" in co
          and "bool  stPvGate = is5mChart and not barstate.isconfirmed and oState == 0 and stSessOK" in co
          and co.count("stWkdOK") == 2 and co.count("stNoWkend") == 2
          and not re.search(r"stSessOK|stWkdOK", code_only(seg(FULL, "    // (1) 発注済み Entry", "    // (2d) D:")))
          and not re.search(r"stSessOK|stWkdOK", code_only(seg(FULL, "    // (2d) D:", "    // (3) 保留中の指値")))
          and "strategy.exit(oXid, oEid, stop = oStop, limit = oTP)" in seg(FULL, "    // (1) 発注済み Entry", "    // (2d) D:"))
    v = input_values(FULL)
    req = lambda t: re.findall(r"request\.\w+\(", code_only(t))
    check("SW-03 independent input, default ON (not derived from Limit New Entries to Session); date logic uses only "
          "time_close with hour / minute / dayofweek in the session timezone (Asia/Tokyo) — no request added, no timenow",
          v["stNoWkend"] == "true" and v["stUseSess"] == "true" and req(FULL) == req(BTS) and len(req(FULL)) == 11
          and "stNoWkend" not in func(FULL, "f_stInSession(int t) =>") and "timenow" not in func(FULL, "f_stSessDow(int t) =>"))
    m = FULL.replace("bool stSessOK  = (not stUseSess or f_stInSession(time_close)) and stWkdOK",
                     "bool stSessOK  = not stUseSess or (f_stInSession(time_close) and stWkdOK)")
    check("SW-04 mutation: tying the weekend rule to the session limit (OFF would silently drop it) is detected",
          "bool stSessOK  = (not stUseSess or f_stInSession(time_close)) and stWkdOK" not in m and sb.strip_bts2(m) is None)


def sess_dow(t, sh=9, sm=0, eh=2, em=0, tz="Asia/Tokyo"):
    """port of f_stSessDow: ISO weekday (Mon = 1 ... Sun = 7) of the session start day."""
    lt = t.astimezone(ZoneInfo(tz))
    mins, s, e = lt.hour * 60 + lt.minute, sh * 60 + sm, eh * 60 + em
    return (lt - dt.timedelta(days=1)).isoweekday() if (s >= e and mins < e) else lt.isoweekday()


def sess_ok(t, use_sess=True, no_wkend=True, **kw):
    """port of stSessOK (BTS-2)."""
    return (not use_sess or in_session(t, **kw)) and (not no_wkend or sess_dow(t, **kw) not in (6, 7))


def expected_by_starts(t, sh, sm, eh, em, tz="Asia/Tokyo"):
    """independent reference for limit ON + weekend ON: enumerate the session windows by their start day D
    ([D + start, D + start + length), length = (end - start) mod 24 h, 24 h if equal) and allow t when it lies in the
    window of a Mon-Fri start day."""
    lt = t.astimezone(ZoneInfo(tz))
    length = ((eh * 60 + em) - (sh * 60 + sm)) % 1440 or 1440
    for back in (0, 1):
        d = (lt - dt.timedelta(days=back)).date()
        st = dt.datetime(d.year, d.month, d.day, sh, sm, tzinfo=ZoneInfo(tz))
        if st <= lt < st + dt.timedelta(minutes=length):
            return d.isoweekday() <= 5
    return False


def gate_weekend_model():
    J = ZoneInfo("Asia/Tokyo")
    t = lambda d, h, mi: dt.datetime(2026, 10, d, h, mi, tzinfo=J)      # 2026-10-09 = Friday, 10 Sat, 11 Sun, 12 Mon
    spec = {"Fri 09:00": (t(9, 9, 0), True), "Sat 01:55": (t(10, 1, 55), True), "Sat 02:00": (t(10, 2, 0), False),
            "Sat 09:00": (t(10, 9, 0), False), "Mon 01:55": (t(12, 1, 55), False), "Mon 09:00": (t(12, 9, 0), True)}
    got = {k: sess_ok(v[0]) for k, v in spec.items()}
    sun = all(not sess_ok(t(11, h, mi)) for h in range(24) for mi in range(0, 60, 5))
    check("SW-05 [model] the specified examples (defaults, bar close time JST): Fri 09:00 allowed, Sat 01:55 allowed (Friday "
          "session), Sat 02:00 / Sat 09:00 blocked, Sunday blocked all day (every 5 min), Mon 01:55 blocked (Sunday "
          "session), Mon 09:00 allowed", all(got[k] == v[1] for k, v in spec.items()) and sun,
          str({k: v for k, v in got.items() if v != spec[k][1]}))
    edges = {"Fri 08:55": (t(9, 8, 55), False), "Fri 23:55": (t(9, 23, 55), True), "Sat 00:00": (t(10, 0, 0), True),
             "Sat 01:59": (t(10, 1, 59), True), "Sun 00:00": (t(11, 0, 0), False), "Sun 23:55": (t(11, 23, 55), False),
             "Mon 00:00": (t(12, 0, 0), False), "Mon 02:00": (t(12, 2, 0), False), "Mon 08:55": (t(12, 8, 55), False),
             "Tue 01:55": (t(13, 1, 55), True), "Thu 01:55": (t(15, 1, 55), True)}
    g2 = {k: sess_ok(v[0]) for k, v in edges.items()}
    check("SW-06 [model] boundaries Fri -> Sat and Sun -> Mon: Fri 08:55 out, Fri 23:55 / Sat 00:00 / Sat 01:59 in, Sun 00:00 "
          "- 23:55 out, Mon 00:00 / 02:00 / 08:55 out, Tue 01:55 (Monday session) in, Thu 01:55 in",
          all(g2[k] == v[1] for k, v in edges.items()), str({k: v for k, v in g2.items() if v != edges[k][1]}))
    week = [dt.datetime(2026, 10, 5, 0, 0, tzinfo=J) + dt.timedelta(minutes=5 * i) for i in range(7 * 288 + 288)]
    on_on = all(sess_ok(x) == expected_by_starts(x, 9, 0, 2, 0) for x in week)
    on_off = all(sess_ok(x, no_wkend=False) == in_session(x) for x in week)
    rule = lambda x: (x.isoweekday() <= 5 and not (x.isoweekday() == 1 and x.hour < 2)) or (x.isoweekday() == 6 and x.hour < 2)
    off_on = all(sess_ok(x, use_sess=False) == rule(x) for x in week)
    off_off = all(sess_ok(x, use_sess=False, no_wkend=False) for x in week)
    check("SW-07 [model] combinations over 8 days at 5-min steps: limit ON + weekend ON == the independent window "
          "enumeration (Mon-Fri start days only); limit ON + weekend OFF == the previous session rule unchanged; limit "
          "OFF + weekend ON still excludes the weekend (Sat 00:00-01:59 belongs to Friday, Sat 02:00 - Mon 01:59 blocked); "
          "both OFF -> always allowed", on_on and on_off and off_on and off_off, str((on_on, on_off, off_on, off_off)))
    alt = []
    for (sh, sm, eh, em) in ((22, 0, 6, 0), (9, 0, 17, 0), (9, 0, 9, 0), (0, 0, 0, 0), (20, 30, 0, 30), (8, 15, 1, 45)):
        alt.append(((sh, sm, eh, em), all(sess_ok(x, sh=sh, sm=sm, eh=eh, em=em) == expected_by_starts(x, sh, sm, eh, em)
                                          for x in week)))
    s22 = [sess_ok(t(10, 5, 55), sh=22, eh=6), sess_ok(t(10, 6, 0), sh=22, eh=6), sess_ok(t(12, 5, 55), sh=22, eh=6),
           sess_ok(t(12, 22, 0), sh=22, eh=6)]
    check("SW-08 [model] changed session inputs keep the start-day rule (== window enumeration): 22:00-06:00 (Sat 05:55 in as "
          "Friday's, Sat 06:00 out, Mon 05:55 out as Sunday's, Mon 22:00 in), 09:00-17:00 (no wrap), 24 h 09:00-09:00, "
          "00:00-00:00, 20:30-00:30, 08:15-01:45", all(ok for _, ok in alt) and s22 == [True, False, False, True], str((alt, s22)))


def main():
    for g in (gate_static, gate_model, gate_weekend, gate_weekend_model):
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
