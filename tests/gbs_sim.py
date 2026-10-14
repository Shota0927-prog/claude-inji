"""GBS-1 fixtures — ZoneStrategyGBPJPY.pine (OANDA:GBPJPY 5M comparison strategy: A / B / C / D, provisional / confirmed
alerts; Zone calculation of ZONE-GBPJPY, order / alert logic of ZONE-ST-JPY).

  GB : static — deterministic, idempotent build (ZONE-GBPJPY -> ST-1 -> ST-2 -> ST-3 -> USDJPY strategy edits) and
       exact inverse; Zone computation part byte-identical to ZONE-GBPJPY; against ZONE-ST-JPY the only code differences
       are the title and input texts / defaults, the input values differ only in the GBPJPY base-setting defaults
       (Half Width 0.05, SL Buffer 0.08, RR 1.2); order / alert code after the strategy marker identical to
       ZONE-ST-JPY; requests 10 + 1 (1M, D); GBPJPY base-setting defaults (GBS-2); lightweight
       (no drawing, Engine / zone loop on confirmed bars, message strings only inside alert()); the ZONE-ST-JPY alert /
       tick-separation static checks re-run on this file; protected files unchanged vs 140a6c9
  GM : models — Zone parity mirror with the GBPJPY yen parameters; the ZONE-ST-JPY order / alert mirrors re-run (same
       code); GBPJPY-scale (~190 円) scenarios: Long / Short / Both, SL fixed at entry, TP from the actual fill price,
       one order / Track once, alerts ON / OFF same orders, provisional does not suppress confirmed, D wait carried
       over a 5M bar, forming 1M bar excluded

Evidence class: PINE_NOT_VERIFIED. TradingView compile, broker emulator, P/L currency external.
"""
import copy
import difflib
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gbs_build as gs          # noqa: E402
import gbe_build as ge          # noqa: E402
import gbj_build as gb          # noqa: E402
import stj_build as sj          # noqa: E402
import st1_build as tb          # noqa: E402
import st2_build as s2          # noqa: E402
import st3_build as s3          # noqa: E402
import fvg_re10045_sim as fr    # noqa: E402

ROOT = gs.ROOT
BASE = "140a6c9"
rd = lambda p: open(os.path.join(ROOT, p), encoding="utf-8").read() if os.path.exists(os.path.join(ROOT, p)) else ""
GBS_FULL = rd(gs.GBS_PATH)
GBS = gs.strip_qty(GBS_FULL) or ""     # GBS-4 position size reverted: these checks pin GBS-3 (gbq_sim pins GBS-4)
GBV = rd(gb.GBJ_PATH)
STJ = rd(sj.STJ_PATH)


def strip_gbj2_in_strategy(text):
    """revert the GBJ-2 edits that reach the Strategy (all but the Visual header and the Visual-only FVG box display)."""
    out = text
    for kind, a, b in list(reversed(gb.EDITS7)) + list(reversed(gb.EDITS6)) + list(reversed(gb.EDITS5)) + list(reversed(gb.EDITS4)):     # GBJ-4 Accum Score Mode / GBPJPY Engine import (pinned in gbe_sim)
        if kind != "header":
            out = out.replace(b, a) if out is not None and out.count(b) == 1 else None
    for kind, a, b in reversed(gb.EDITS2):
        if kind != "header" and "fd   = array.get(gFvgDir, slot)" not in b:
            out = out.replace(b, a) if out is not None and out.count(b) == 1 else None
    return out


GBS1 = strip_gbj2_in_strategy(GBS) or ""     # GBS-2 text: GB-03 / GB-04 pin the order / alert code against ZONE-ST-JPY
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


def code_only(src):
    return "\n".join(l for l in src.split("\n") if not l.lstrip().startswith("//"))


def inputs(src):
    return dict(re.findall(r"^(\w+)\s*=\s*input\.\w+\(([^,]+),", src, re.M))


def inp(src, n):
    m = re.search(r"^" + n + r"\s*=\s*input\.\w+\((.*)$", src, re.M)
    return m.group(1) if m else ""


def allowed_line(s):
    s = s.strip()
    return (re.match(r"^\w+\s*=\s*input\.\w+\(", s) is not None or re.match(r'^(tooltip = )?".*"\)?( \+)?$', s) is not None
            or re.match(r'^(title|shorttitle)\s*=\s*"[^"]*",$', s) is not None)


PROTECTED = ["ZoneVisualUSDJPY.pine", "ZoneStrategyUSDJPY.pine", "ZoneVisualPractical.pine",
             "ZoneStrategyXAU.pine", "ZoneEnginePractical.pine", "ZoneEnginePracticalRN.pine",
             "ZoneEnginePracticalSwingMax.pine", "ZoneEnginePracticalAuthority.pine", "PracticalZoneStrategy_LONG.pine",
             "PracticalZoneStrategy_SHORT.pine", "SignalEnginePractical.pine"]


def gate_static():
    pipe = gs.pipeline()
    check("GB-01 ZoneStrategyGBPJPY.pine == gbs_build.build() (rebuild gives the same bytes); strip_gbs gives the "
          "ZONE-GBPJPY -> ST-3 pipeline text back, and strip_st3 / strip_st2 lead to st_transform(ZONE-GBPJPY)",
          bool(GBS) and gs.build() == GBS_FULL and gs.build() == gs.build() and gs.strip_gbs(GBS_FULL) == pipe
          and s2.strip_st2(s3.strip_st3(pipe)) == tb.st_transform(gs.visual_for_pipeline()))
    v = GBV
    comp = v[v.index(ge.IMPORT_GBE):v.index(tb.DISP_INPUT_HEAD)] + \
        v[v.index(tb.DISP_INPUT_LAST) + len(tb.DISP_INPUT_LAST) + 1:v.index(tb.DISPLAY_HEAD)]
    st_comp = GBS[GBS.index(ge.IMPORT_GBE):GBS.index(tb.ST_BEGIN)]
    upd = next((a, b) for a, b in gs.EDITS if a.startswith("if is5mChart\n    zoneCountNow"))
    zone_exp = comp.replace(gs.GEOM_GBS, "").replace(upd[0], upd[1])
    check("GB-02 Zone computation part byte-identical to ZONE-GBPJPY (all Zone inputs incl. Half Width 0.05 / Cluster "
          "0.08 / FVG 0.05 and the GBJ-3 scoring defaults, Engine config, MA / Swing / Accum / Break feeds, zn.update, "
          "NR-S1, NR-A1, FVG Batch A); only the display inputs and the display-only label helper are left out; the one "
          "edit: zn.update on confirmed bars", comp.count(gs.GEOM_GBS) == 1 and st_comp == zone_exp)
    bad = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, code_only(STJ).split("\n"), code_only(GBS1).split("\n"),
                                                      autojunk=False).get_opcodes():
        if op != "equal":
            bad += [l for l in code_only(STJ).split("\n")[i1:i2] + code_only(GBS1).split("\n")[j1:j2] if not allowed_line(l)]
    vj, vg = inputs(STJ), inputs(GBS1)
    vdiff = {n: (vj.get(n), vg.get(n)) for n in set(vj) | set(vg) if vj.get(n) != vg.get(n)}
    check("GB-03 against ZONE-ST-JPY every differing code line is the title or an input declaration / tooltip; same input "
          "set; input values differ only in the GBPJPY base-setting defaults: Half Width 0.03 -> 0.05, SL Buffer 0.05 -> "
          "0.08, RR 1.3 -> 1.2, Day H/L Score 3 -> 2, Slope Threshold 0.02 / 0.05 -> 0.01 / 0.02, Strong Threshold "
          "10 -> 9 (Direction Long Only as ZONE-ST-JPY)",
          bad == [] and set(vj) == set(vg) and vdiff == {"zoneHalfWidth": ("0.03", "0.05"), "stBuffer": ("0.05", "0.08"),
                                                         "stRR": ("1.3", "1.2"), "scoreDayHL": ("3.0", "2.0"),
                                                         "slopeThrMod": ("0.02", "0.01"), "slopeThrStrong": ("0.05", "0.02"),
                                                         "thrStrong": ("10.0", "9.0")}, str((bad[:5], vdiff)))
    tail = lambda s: code_only(s[s.index(tb.ST_BEGIN):]).replace(
        'stBuffer = input.float(0.08,', 'stBuffer = input.float(0.05,').replace(
        'stRR = input.float(1.2,', 'stRR = input.float(1.3,')
    check("GB-04 strategy part (A / B / C / D, session, SL / TP / breakeven, fill-price TP, cancel, one order / Track once, "
          "D 1M BOS with carried waits, provisional evaluation, provisional / confirmed alerts) code-identical to "
          "ZONE-ST-JPY apart from the SL Buffer / RR defaults (GBJ-2 FVG / RN edits reverted; they are pinned in gbx_sim)",
          bool(GBS1) and tail(GBS1) == tail(STJ))
    req = lambda s: re.findall(r"request\.\w+\(.*$", code_only(s), re.M)
    check("GB-05 requests: the 10 Zone / FVG requests of ZONE-GBPJPY + one request.security_lower_tf (1M, D) = 11, the "
          "same call sites as ZONE-ST-JPY (GBJ-6 Swing tuples reverted; their request count is pinned in gbd_sim)",
          req(GBS1) == req(STJ) and len(req(GBS)) == 11
          and [r for r in req(GBS) if "lower_tf" not in r] == req(GBV)
          and len([r for r in req(GBS) if "lower_tf" in r]) == 1)
    want = {"stMode": '"D: 1M BOS Rebound"', "stDir": '"Long Only"', "zoneHalfWidth": "0.05", "clusterDist": "0.08",
            "fvgMinWidth": "0.05", "stBuffer": "0.08", "stRR": "1.2", "stUseSess": "true", "stSessTz": '"Asia/Tokyo"',
            "stSessStartH": "9", "stSessStartM": "0", "stSessEndH": "2", "stSessEndM": "0", "stTpZone": "false",
            "stBE": "false", "stBEDist": "0.15", "stDWait": "30", "stAlertProv": "true", "stAlertConf": "true",
            "enableRn": "false", "fvgDirMatch": "false",
            # scoring (GBJ-3 changed: scoreDayHL / slopeThrMod / slopeThrStrong / thrStrong; the rest kept)
            "scoreDayHL": "2.0", "slopeThrMod": "0.01", "slopeThrStrong": "0.02", "thrStrong": "9.0",
            "thrMedium": "5.0", "thrVStrong": "15.0", "scoreMa1": "2.0", "scoreMa2": "2.0", "slopeBonusFlat": "0.0",
            "slopeBonusMod": "1.0", "slopeBonusStr": "2.0", "slopeBonusMode": '"Sum (per MA)"', "scoreHz1": "1.0",
            "scoreHz2": "2.0", "scoreHz3": "3.0", "scoreAcc1": "3.0", "scoreAcc2": "4.0", "scoreAcc3": "5.0",
            "confBonus2": "1.0", "confBonus3": "2.0", "confBonus4": "3.0", "useMaSource": "true", "useHzSource": "true",
            "useAccSource": "true", "useDayHL": "true", "carryPrevDayHL": "false",
            # adopted setting (GBJ-8): Accum Max + Separate, Day/Swing Separate (Merge Distance 0.05 kept, unused)
            "accScoreMode": '"Max"', "accEdgeMode": '"Separate"', "dsMode": '"Separate"', "dsDist": "0.05",
            "rnMajorStep": "1.0", "rnMinorStep": "0.5"}
    vg = inputs(GBS)
    got = {k: vg.get(k) for k in want}
    opts = 'options = ["Long Only", "Short Only", "Both"]' in inp(GBS, "stDir")
    check("GB-06 GBPJPY base-setting defaults: D (1M BOS Rebound), Long Only (Short Only / Both selectable), HW 0.05 / "
          "Cluster 0.08 / FVG 0.05 円, SL Buffer 0.08 円, RR 1.2, session ON Asia/Tokyo 09:00-02:00, zone TP OFF, "
          "breakeven OFF (trigger 0.15 円), D wait 30, provisional / confirmed alerts ON, RN / FVG Direction Match OFF; "
          "scoring: Day H/L 2, Slope Threshold 0.01 / 0.02, Strong 9 (Medium 5 / Very Strong 15, MA 2 / 2, Slope Bonus "
          "0 / 1 / 2 Sum, Swing 1 / 2 / 3, Accum 3 / 4 / 5, Confluence 1 / 2 / 3, sources ON, prev-day H/L OFF kept); every "
          "Zone input identical to ZONE-GBPJPY (Half Width 0.05 in both)",
          got == want and opts and inputs(GBV).get("zoneHalfWidth") == "0.05"
          and all(vg.get(n) == x for n, x in inputs(GBV).items() if n in vg)
          and "円" in inp(GBS, "stBuffer") and "円" in inp(GBS, "stBEDist"), str(got))
    co = code_only(GBS)
    decl = GBS[GBS.index("strategy(\n"):GBS.index(")\n", GBS.index("strategy(\n")) + 2]
    calls = [m.start() for m in re.finditer(r"f_stAlertMsg\(", co)]
    in_alert = all(co.rfind("alert(", 0, p) > co.rfind("\n", 0, p) for p in calls[1:])
    check("GB-07 lightweight: no box / label / line / table, plots only to the data window, RE10045 lint clean, one zone "
          "loop (zn.zoneAt / f_stZoneEval once), zn.update only on confirmed 5M bars, message string built only inside "
          "the two alert() calls; strategy() = ZONE-ST-JPY's apart from the title",
          not re.search(r"\b(box|label|line|table)\.(new|set_\w+|delete)\b", co)
          and all("display = display.data_window" in l for l in re.findall(r"^plot\(.*$", co, re.M))
          and fr.lint_eager_guards(co) == [] and co.count("zn.zoneAt(") == 1 and co.count("= f_stZoneEval(z)") == 1
          and "if is5mChart and barstate.isconfirmed\n    zoneCountNow := zn.update(" in co
          and len(calls) == 3 and in_alert and co.count("alert(f_stAlertMsg(") == 2
          and decl.replace("GBPJPY", "USDJPY").replace("ZONE-ST-USDJPY", "ZONE-ST-JPY")
          == STJ[STJ.index("strategy(\n"):STJ.index(")\n", STJ.index("strategy(\n")) + 2])
    # ZONE-ST-JPY's alert / tick-separation static checks, applied to this file
    import stj_sim as tj
    keep = tj.STJ, len(tj.RESULTS)
    try:
        tj.STJ = GBS
        tj.gate_alert_static()
        tj.gate_tick_separation()
    finally:
        tj.STJ = keep[0]
    sub = tj.RESULTS[keep[1]:]
    del tj.RESULTS[keep[1]:]
    mine = [(n[:6], ok) for n, ok, _ in sub if not n.startswith("SA-17")]   # SA-17 is the USDJPY history (feb64b7)
    check("GB-08 ZONE-ST-JPY static alert / tick-separation checks re-run on this file pass: read-only provisional "
          "evaluation, provisional block gating, confirmed alert in the order branch, message, Engine on confirmed bars, "
          "no extra request, every state write / order in the confirmed blocks, 1M closedness expression",
          len(mine) >= 8 and all(ok for _, ok in mine), str(mine))
    prev = "80d6a96"
    chg = {"scoreDayHL": ("3.0", "2.0"), "slopeThrMod": ("0.02", "0.01"), "slopeThrStrong": ("0.05", "0.02"),
           "thrStrong": ("10.0", "9.0")}
    res = []
    gbs3 = GBS
    for kind, a, b in list(reversed(gb.EDITS7)) + list(reversed(gb.EDITS6)) + list(reversed(gb.EDITS5)) + list(reversed(gb.EDITS4)):     # GB-10 pins GBJ-3; GBJ-4 is checked in gbe_sim
        if kind != "header":
            gbs3 = gbs3.replace(b, a) if gbs3 is not None and gbs3.count(b) == 1 else None
    for path, cur, extra in ((gs.GBS_PATH, gbs3 or "", {}),
                             (gb.GBJ_PATH, gb.strip_gbj4(GBV) or "", {"zoneHalfWidth": ("0.03", "0.05")})):
        old = subprocess.run(["git", "-C", ROOT, "show", f"{prev}:{path}"], capture_output=True, text=True).stdout
        lines = []
        for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, code_only(old).split("\n"), code_only(cur).split("\n"),
                                                          autojunk=False).get_opcodes():
            if op != "equal":
                lines += code_only(old).split("\n")[i1:i2] + code_only(cur).split("\n")[j1:j2]
        vo, vc = inputs(old), inputs(cur)
        vd = {n: (vo.get(n), vc.get(n)) for n in set(vo) | set(vc) if vo.get(n) != vc.get(n)}
        res.append((path, bool(old) and all(allowed_line(l) for l in lines) and vd == dict(chg, **extra), vd))
    check("GB-10 against the previous version " + prev + ": every differing code line (Visual and Strategy) is an input "
          "declaration or tooltip; input values changed exactly: Day H/L Score 3 -> 2, Slope Threshold 0.02 / 0.05 -> "
          "0.01 / 0.02, Strong Threshold 10 -> 9, and the Visual Half Width 0.03 -> 0.05 (Strategy already 0.05)",
          all(ok for _, ok, _ in res), str(res))
    prev8 = "8e94720"
    res8 = []
    for path, cur in ((gs.GBS_PATH, GBS), (gb.GBJ_PATH, GBV)):
        old = subprocess.run(["git", "-C", ROOT, "show", f"{prev8}:{path}"], capture_output=True, text=True).stdout
        diff = [(op, code_only(old).split("\n")[i1:i2], code_only(cur).split("\n")[j1:j2]) for op, i1, i2, j1, j2 in
                difflib.SequenceMatcher(None, code_only(old).split("\n"), code_only(cur).split("\n"),
                                        autojunk=False).get_opcodes() if op != "equal"]
        vo, vc = inputs(old), inputs(cur)
        vd = {n: (vo.get(n), vc.get(n)) for n in set(vo) | set(vc) if vo.get(n) != vc.get(n)}
        res8.append((path, bool(old) and vd == {"accScoreMode": ('"Sum"', '"Max"')} and len(diff) == 1
                     and diff[0][1] == [gb.EDITS7[1][1].rstrip("\n")] and diff[0][2] == [gb.EDITS7[1][2].rstrip("\n")],
                     vd))
    check("GB-11 against " + prev8 + ": in both Visual and Strategy the only code change is the Accum Score Mode default "
          "Sum -> Max (Edge Mode Separate, Day/Swing Separate, Merge Distance 0.05 unchanged); Library unchanged",
          all(ok for _, ok, _ in res8) and subprocess.run(["git", "-C", ROOT, "diff", "--name-only", prev8, "--",
                                                          "ZoneEnginePracticalGBPJPY.pine"], capture_output=True,
                                                         text=True).stdout.strip() == "", str(res8))
    d = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", BASE, "--"] + PROTECTED, capture_output=True, text=True)
    t = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", "--diff-filter=MDR", BASE, "--", "tests/"],
                       capture_output=True, text=True).stdout
    check("GB-09 ZONE-JPY, ZONE-ST-JPY, ZONE-P, ZONE-ST (XAU), Engines and old strategies unchanged vs "
          + BASE + "; no existing test / generator script modified or removed except the GBPJPY ones (ZONE-GBPJPY is pinned by "
          "its build in gbj_sim GS-01 / gbx_sim)",
          d.returncode == 0 and d.stdout.strip() == ""
          and all(re.match(r"^tests/gb[jsx]_\w+\.py$", f) for f in t.split()), d.stdout + t)


# ---- models -----------------------------------------------------------------------------------------------------------
def rerun(gate, prefixes):
    import stj_sim as tj
    n0 = len(tj.RESULTS)
    gate()
    sub = tj.RESULTS[n0:]
    del tj.RESULTS[n0:]
    return [(n[:6], ok, d) for n, ok, d in sub if n.startswith(prefixes)]


def gate_mirrors():
    import stj_sim as tj
    keep = dict(tj.YEN)
    try:
        tj.YEN.update(zoneHalfWidth=0.05, slopeThrMod=0.01, slopeThrStrong=0.02, scoreDayHL=2.0, thrStrong=9.0)
        # GBPJPY base setting (GBJ-3); Cluster 0.08 / FVG 0.05 equal as well
        r = rerun(tj.gate_zone_parity, ("SM-01",))
    finally:
        tj.YEN.clear()
        tj.YEN.update(keep)
    # read SM-01's report and check its width floor against the Half Width used here
    m = re.match(r"\{'snaps': (\d+), 'zones': (\d+), 'fvg': (\d+), 'boosted': (\d+), 'bad': (\d+)\} median width "
                 r"[0-9.]+ min ([0-9.]+)$", r[0][2] if r else "")
    ok01 = m is not None and int(m.group(5)) == 0 and min(int(m.group(i)) for i in (2, 3, 4)) > 0 \
        and float(m.group(6)) >= 2 * 0.05 - 1e-9
    check("GM-01 Zone parity with the GBPJPY base setting (HW 0.05, Cluster 0.08, FVG 0.05, Slope 0.01 / 0.02, Day H/L 2, "
          "Strong 9): on the same yen OHLC the "
          "Strategy zone evaluation (top / bottom / Score / Strength / FVG boost) equals the Visual display mirror on "
          "every sampled bar (0 mismatches; zones, FVGs and boosts occur; min width >= 2 x 0.05)",
          ok01, str(r))
    r = rerun(tj.gate_orders_yen, ("SM-",)) + rerun(tj.gate_alert_model, ("SA-",))
    check("GM-02 the ZONE-ST-JPY order / alert mirrors (same code, GB-04) pass: D timing, SL, fill-price TP, opposite-zone "
          "TP, breakeven, A cancel, one order, alerts ON / OFF, read-only provisional, forming 1M excluded, closedness by "
          "time, provisional-only case, entry limits, carried D wait and expiry", len(r) >= 15 and all(ok for _, ok, _ in r),
          str([x[:2] for x in r if not x[1]]))


SH = 40.0                                    # USDJPY ~150 scenario moved to the GBPJPY ~190 price level
P = lambda x: round(x + SH, 3)
bar = lambda b: tuple(P(x) for x in b)
m1 = lambda lst: [(t, P(h), P(l), P(c)) for t, h, l, c in lst]
M = 380.4                                    # mirror (for Short): x -> M - x, high <-> low
mb = lambda b: (round(M - b[0], 3), round(M - b[2], 3), round(M - b[1], 3), round(M - b[3], 3))
mm = lambda lst: [(t, round(M - l, 3), round(M - h, 3), round(M - c, 3)) for t, h, l, c in lst]


def scenario():
    import st3_sim as t3
    zl = t3.Z(1, t3.SUP, P(150.100), P(150.000))
    flat, bt, nxt = bar((150.300, 150.320, 150.280, 150.300)), bar((150.250, 150.260, 150.050, 150.150)), \
        bar((150.150, 150.160, 150.120, 150.150))
    m1b = m1([(5, 150.26, 150.20, 150.22), (6, 150.21, 150.05, 150.08), (7, 150.12, 150.06, 150.11),
              (8, 150.24, 150.10, 150.23), (9, 150.24, 150.13, 150.15)])
    return t3, zl, flat, bt, nxt, m1b


def short_of(zl, bars, m1s):
    import st3_sim as t3
    zs = t3.Z(1, t3.RES, round(M - zl["bot"], 3), round(M - zl["top"], 3))
    return zs, [mb(b) for b in bars], [mm(x) for x in m1s]


def gate_gbpjpy():
    import stj_sim as tj
    t3, zl, flat, bt, nxt, m1b = scenario()
    J = dict(mode="D", dir="Long", buffer=0.08, rr=1.2, tpzone=False, be=False, e=2 * 60)   # GBPJPY base setting
    Jnd = {k: v for k, v in J.items() if k != "dir"}
    bars = [flat, bt, nxt, nxt]
    m1s = [m1([(0, 150.32, 150.28, 150.30)]), m1b, [], []]
    zs, bars_s, m1s_s = short_of(zl, bars, m1s)
    res = {}
    for d in ("Long", "Short", "Both"):
        SL_, _ = t3.run3(bars, [[zl]] * 4, m1s=m1s, dir=d, **Jnd)
        SS_, _ = t3.run3(bars_s, [[zs]] * 4, m1s=m1s_s, dir=d, **Jnd)
        res[d] = ([o["side"] for _, o in t3.orders(SL_)], [o["side"] for _, o in t3.orders(SS_)])
    check("GM-03 Direction at GBPJPY scale (~190 円): the Long setup orders only under Long Only / Both, its mirrored Short "
          "setup only under Short Only / Both", res == {"Long": ([1], []), "Short": ([], [-1]), "Both": ([1], [-1])}, str(res))
    S, B = t3.run3(bars, [[zl]] * 4, m1s=m1s, **J)
    o = t3.orders(S)[0][1]
    fill = B.fills[0]["price"]
    tp = S.log[2].get("tp")
    check("GM-04 Long at GBPJPY scale (Long Only default): SL = zone bottom 190.000 - 0.08 = 189.920 set with the entry; "
          "filled at the next open 190.150; TP = fill + 1.2 x (fill - SL) = 190.426 (from the actual fill, set at the "
          "fill-bar close)",
          abs(o["SL"] - 189.920) < 1e-9 and fill == 190.150 and tp is not None and abs(tp - 190.426) < 1e-9,
          str((o, fill, tp)))
    gap = bar((150.170, 150.180, 150.140, 150.150))
    S2, B2 = t3.run3([flat, bt, gap, nxt], [[zl]] * 4, m1s=m1s, **J)
    tp2 = S2.log[2].get("tp")
    check("GM-05 TP follows the actual fill price, SL does not: fill 190.170 (gap) -> TP 190.170 + 1.2 x 0.250 = 190.470; "
          "SL stays 189.920", B2.fills[0]["price"] == 190.170 and abs(tp2 - 190.470) < 1e-9
          and abs(t3.orders(S2)[0][1]["SL"] - 189.920) < 1e-9, str((B2.fills, tp2)))
    down = [flat, bt, nxt, bar((150.150, 150.160, 150.040, 150.060)), bar((150.060, 150.070, 149.900, 149.920))]
    S3, B3 = t3.run3(down, [[zl]] * 5, m1s=m1s + [[]], **J)
    check("GM-06 SL fixed at entry (breakeven OFF): the price falls through the zone and the trade exits at 189.920 "
          "(the stop set with the entry, not moved)", B3.closed and abs(B3.closed[0]["exit"] - 189.920) < 1e-9,
          str(B3.closed))
    S4, B4 = t3.run3(bars, [[zl, t3.Z(2, t3.SUP, P(150.110), P(150.020))]] * 4, m1s=m1s, **J)
    again = [flat, bt, nxt, bar((150.150, 150.700, 150.140, 150.650)), bar((150.300, 150.320, 150.280, 150.300)), bt,
             nxt, nxt]
    m1a = m1s[:3] + [[], m1([(20, 150.32, 150.28, 150.30)]), [(t + 20, h, l, c) for t, h, l, c in m1b], [], []]
    S5, B5 = t3.run3(again, [[zl]] * 8, m1s=m1a, **J)
    check("GM-07 one order at a time / same Track once: two zones touched with the same BOS -> one order; after the TP "
          "exit, the same Track touched again with a BOS -> no second order",
          len(t3.orders(S4)) == 1 and len(B4.fills) == 1 and len(B5.closed) == 1 and len(t3.orders(S5)) == 1,
          str((t3.orders(S4), B5.closed, t3.orders(S5))))
    tk = [[], [(bar((150.25, 150.26, 150.05, 150.08)), m1b[:2] + [(7, P(150.10), P(150.06), P(150.09))]),
               (bar((150.25, 150.26, 150.05, 150.23)), m1b[:4] + [(9, P(150.24), P(150.20), P(150.23))]),
               (bar((150.25, 150.26, 150.05, 150.16)), m1b[:4] + [(9, P(150.24), P(150.13), P(150.16))])]]
    S0, B0 = t3.run3(bars, [[zl]] * 4, m1s=m1s, **J)
    out = {}
    for prov, conf in ((True, True), (True, False), (False, True), (False, False)):
        S_, B_, al, mut = tj.run_ticks(bars, [[zl]] * 4, m1s, tk, prov=prov, conf=conf, **J)
        out[(prov, conf)] = (t3.orders(S_) == t3.orders(S0) and B_.fills == B0.fills and B_.closed == B0.closed, al, mut)
    check("GM-08 alerts ON / OFF (4 combinations) give the same orders / fills / exits as the run without ticks; the "
          "provisional evaluation changes no state", all(v[0] and not v[2] for v in out.values()), str(out))
    check("GM-09 provisional does not suppress confirmed: with both ON, one provisional LONG on the forming bar (3 ticks "
          "-> once) and the confirmed LONG at that 5M close", out[(True, True)][1] == [("仮", 1, 1), ("確定", 1, 1)],
          str(out[(True, True)][1]))
    tk_dev = [[], [(bar((150.25, 150.26, 150.05, 150.23)), m1b[:3] + [(8, P(150.24), P(150.10), P(150.23))])]]
    _, _, al_dev, _ = tj.run_ticks(bars, [[zl]] * 4, m1s, tk_dev, **J)
    check("GM-10 forming 1M bar excluded: a BOS only on the last 1M element whose minute has not ended gives no "
          "provisional; the confirmed alert still comes", al_dev == [("確定", 1, 1)], str(al_dev))
    t1 = [(150.26, 150.20, 150.22), (150.21, 150.05, 150.08), (150.12, 150.06, 150.11), (150.14, 150.07, 150.12),
          (150.15, 150.08, 150.12)]
    t2 = [(150.16, 150.10, 150.15), (150.18, 150.12, 150.16), (150.24, 150.15, 150.23), (150.25, 150.20, 150.24),
          (150.26, 150.21, 150.25)]
    mk = lambda b0, lst: [(b0 * 5 + j, P(h), P(l), P(c)) for j, (h, l, c) in enumerate(lst)]
    m1c = [m1s[0], mk(1, t1), mk(2, t2), []]
    barsC = [flat, bar((150.25, 150.26, 150.05, 150.12)), bar((150.15, 150.26, 150.10, 150.25)), nxt]
    tkC = [[], [], [(bar((150.15, 150.18, 150.10, 150.17)), mk(2, t2[:2]) + [(12, P(150.18), P(150.15), P(150.17))]),
                    (bar((150.15, 150.24, 150.10, 150.23)), mk(2, t2[:3]) + [(13, P(150.24), P(150.21), P(150.23))])]]
    Sw, _ = t3.run3(barsC[:2], [[zl]] * 2, m1s=m1c[:2], **J)
    w = copy.deepcopy(Sw.waits)
    Sx, Bx, alC, mutC = tj.run_ticks(barsC, [[zl]] * 4, m1c, tkC, **J)
    Sn, Bn = t3.run3(barsC, [[zl]] * 4, m1s=m1c, **J)
    resw = [tj.run_ticks(barsC, [[zl]] * 4, m1c, tkC, **dict(J, dwait=k))[2] for k in (6, 5)]
    check("GM-11 D wait carried over a 5M bar at GBPJPY scale: touch in bar 1 without BOS (wait saved: level 190.210); "
          "the closed 1M close 190.230 in bar 2 is the BOS -> provisional then confirmed LONG at the bar-2 close; the "
          "saved wait is not modified by ticks; D wait 6 vs 5 at the expiry limit: alerts / orders agree (6 -> both, "
          "5 -> neither)", len(w) == 1 and abs(w[0]["lvl"] - 190.21) < 1e-9 and alC == [("仮", 2, 1), ("確定", 2, 1)]
          and not mutC and t3.orders(Sx) == t3.orders(Sn) and Bx.fills == Bn.fills
          and resw == [[("仮", 2, 1), ("確定", 2, 1)], []], str((w, alC, mutC, resw)))
    Ssh, Bsh = t3.run3(bars_s, [[zs]] * 4, m1s=m1s_s, dir="Short", **Jnd)
    os_ = t3.orders(Ssh)[0][1]
    fs = Bsh.fills[0]["price"]
    tps = Ssh.log[2].get("tp")
    check("GM-12 Short at GBPJPY scale (mirror, Short Only selected): SL = zone top + 0.08, TP = fill - 1.2 x (SL - fill) "
          "from the actual fill", abs(os_["SL"] - (zs["top"] + 0.08)) < 1e-9 and tps is not None
          and abs(tps - (fs - 1.2 * (os_["SL"] - fs))) < 1e-9,
          str((os_, fs, tps, zs)))


def main():
    for g in (gate_static, gate_mirrors, gate_gbpjpy):
        try:
            g()
        except Exception:
            import traceback
            check(f"{g.__name__} completed without error", False, traceback.format_exc()[-900:])
    fails = 0
    for n, ok, d in RESULTS:
        fails += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {n[:150].ljust(150)}  {'' if ok else d}")
    print(f"\n{len(RESULTS) - fails}/{len(RESULTS)} passed  [PINE_NOT_VERIFIED: exact build / static / mirror model]")
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
