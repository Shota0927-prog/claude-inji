"""XA-4 fixtures — Gold settings parity: ZoneEnginePracticalXAUUSD (new) + ZoneVisualPractical / ZoneStrategyXAU.

  XE : static — the Engine == gbe_build.build() (/6 + GBE-1 Accum Score Mode, GBE-2 Accum Edge Mode, GBE-4 Day/Swing
       Overlap Mode + Merge Distance) with only the library name / one header comment changed; strip gives the GBPJPY
       source and then ZoneEnginePracticalSwingMax.pine (the /6 source) byte for byte; /6 source evidence; both scripts
       rebuild from xa_build and strip back to 17d1ca2; the code delta is only the import, the new inputs / config, the
       RN step check, the FVG Min Width input, the FVG direction filter and (Visual) the width label; defaults Sum /
       Separate / Separate / 0 / 3.0 / OFF / 100 +3 / 50 +2 / width ON; Visual / Strategy parity; every other input, the
       XA-3 defaults, the sizing, the orders / timings, requests, alerts unchanged; other Pine files / Engines untouched
  XM : models — Python ports of the Engine scoring (f_finalizeCluster), FVG selection, RN (f_rnLevelIn) and the width
       label, with the Gold settings (Accum 3 / 4 / 5, Swing 1 / 2 / 3, Day H/L 3, mintick 0.001): defaults equal the /6
       scoring (random clusters, bit-identical); Accum Sum / Max x Separate / Once examples; Day/Swing distance boundary,
       High / Low, independent Swing, categories, order invariance; FVG Direction Match filters before the best-of choice
       and OFF equals the old selection; RN defaults, boundary, major priority, once per zone; RN step check; width
  XU : mutations — mirror and source mutations are caught

Evidence class: PINE_NOT_VERIFIED (TradingView compile, Library publish, display and Strategy Tester are external; the
user's TradingView reference result is not reproduced locally).
"""
import itertools
import math
import os
import random
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xa_build as xb            # noqa: E402
import gbe_build as ge           # noqa: E402
import eu_sim as es              # noqa: E402
import fvg_re10045_sim as fr     # noqa: E402

ROOT = xb.ROOT
PREV = "17d1ca2"
rd = lambda p: open(os.path.join(ROOT, p), encoding="utf-8").read()
git = lambda *a: subprocess.run(["git", "-C", ROOT] + list(a), capture_output=True, text=True).stdout
code_only, input_decls, input_values, func, seg = es.code_only, es.input_decls, es.input_values, es.func, es.seg
E, GBE, SW6 = rd(xb.ENG_PATH), rd(ge.GBE_PATH), rd(ge.SRC_PATH)
V, S = rd(xb.VIS_PATH), rd(xb.STR_PATH)
V0, S0 = xb.show(PREV, xb.VIS_PATH), xb.show(PREV, xb.STR_PATH)
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


NEW_ZONE = {"dsMode": '"Separate"', "dsDist": "0.0", "accScoreMode": '"Sum"', "accEdgeMode": '"Separate"',
            "rnMajorStep": "100.0", "rnMajorScore": "3.0", "rnMinorStep": "50.0", "rnMinorScore": "2.0",
            "fvgMinWidth": "3.0", "fvgDirMatch": "false"}
XA3 = {"zoneHalfWidth": "6.0", "clusterDist": "5.0", "breakBuffer": "10.0", "flipConfirmDist": "5.0", "thrMedium": "5.0",
       "thrStrong": "10.0", "thrVStrong": "15.0", "scoreMa1": "3.0", "scoreMa2": "3.0", "slopeThrMod": "1.0",
       "slopeThrStrong": "3.0", "slopeBonusFlat": "0.0", "slopeBonusMod": "1.0", "slopeBonusStr": "2.0",
       "slopeBonusMode": '"Max"', "scoreDayHL": "3.0", "scoreAcc1": "3.0", "scoreAcc2": "4.0", "scoreAcc3": "5.0",
       "scoreHz1": "1.0", "scoreHz2": "2.0", "scoreHz3": "3.0", "confBonus2": "1.0", "confBonus3": "2.0",
       "confBonus4": "3.0", "enableRn": "true"}
XA3_ST = {"stMode": '"C: Candle Pattern"', "stDir": '"Short Only"', "stBuffer": "1.5", "stRR": "1.5", "stTpZone": "false",
          "stBE": "false", "stBEDist": "10.0", "stCapBase": "300000.0", "stRiskPct": "3.0", "stLotOz": "100.0",
          "stLotMin": "0.01", "stLotStep": "0.01"}
QTY_FN = "f_stQty(int side, float ref, float sl) =>"


def zcfg_defaults(t):
    body = t[t.index("export type ZoneCfg"):]
    body = body[:body.index("\n\n")]
    return dict(re.findall(r"^\s+\w+\s+(\w+)\s+=\s+([^\s/]+)", body, re.M))


def gate_static():
    ev6 = git("log", "--format=%h", "--", ge.SRC_PATH).split()
    swv = rd("tests/swv_build.py")
    check("XE-01 /6 source evidence: ZoneEnginePracticalSwingMax.pine (library name ZoneEnginePractical) was created in "
          "110e5b0 (SW-1) and never changed since; swv_build switched the Gold Visual import /5 -> /6 naming it the published "
          "/6; the Gold files of 17d1ca2 import ZoneEnginePractical/6; gbe_build derives the GBPJPY Engine from this file",
          ev6 == ["110e5b0"] and 'library("ZoneEnginePractical", overlay = true)' in SW6
          and "/6 = the published ZoneEnginePracticalSwingMax.pine" in swv and xb.IMPORT_6.strip() in swv
          and re.findall(r"^import .*$", V0 + S0, re.M) == [xb.IMPORT_6.strip()] * 2 and ge.SRC_PATH == "ZoneEnginePracticalSwingMax.pine")
    exports = lambda t: re.findall(r"^export .*$", t, re.M)
    check("XE-02 Engine == xa_build.build_engine() = gbe_build.build() + the XA-4 edits; strip -> ZoneEnginePracticalGBPJPY.pine "
          "-> (strip_gbe) the /6 source byte for byte; code identical to the GBPJPY Engine except the library name; same "
          "exports / types; ZoneCfg defaults of the three modes = off (Sum / Separate / Separate)",
          xb.build_engine() == E and xb.strip_engine(E) == GBE and ge.build() == GBE and ge.strip_gbe(xb.strip_engine(E)) == SW6
          and code_only(E).replace('library("ZoneEnginePracticalXAUUSD"', 'library("ZoneEnginePracticalGBPJPY"') == code_only(GBE)
          and exports(E) == exports(GBE) and len(exports(E)) > 30
          and [k for k, _, _ in xb.ENGINE_EDITS] == ["header", "name"]
          and {k: zcfg_defaults(E).get(k) for k in ("accScoreMax", "accEdgeOnce", "dsMerge", "useRnSource")}
          == {"accScoreMax": "false", "accEdgeOnce": "false", "dsMerge": "false", "useRnSource": "false"})
    d6 = es.changed_code(SW6, E)
    ids = (r"accScoreMax|accEdgeOnce|accA[123]|e[HL][123]|dsOn|dsTk|dsMerge|dsDist|d[HL]px|d[HL]m|hasD[HL]|hzInd|swInd|"
           r"px[01]|\bm[HL]\b|\bsl\b|top[123]|blocked|dhlInd|dsCatAdj|dhz|dlz|q\.srcId|RawZone q|library\(|"
           r"^for j = 0 to n - 1$|^baseSum [+-]= (m\.baseScore|math\.min\(c\.scoreDayHL, swMax\))$")
    stray = [l for l in d6 if l and not re.search(ids, l)]
    check("XE-03 Engine vs /6: every changed code line belongs to the three ported features (Accum Score / Edge, Day/Swing "
          "Merge price data and scoring) or the library name; Accum detection, Zone width, Swing max, Break / Flip, Track, "
          "Touch, lifetime, RN functions identical",
          not stray and all(func(E, h) == func(SW6, h) for h in ("f_rnLevelIn(float zBot, float zTop, float step) =>",
                                                                  "f_swingMaxStep(float swMax, float s) =>"))
          and all(seg(E, a, b) == seg(SW6, a, b) for a, b in (("export update(", "\nexport "),)), str(stray[:4]))
    check("XE-04 Visual / Strategy == 17d1ca2 + the XA-4 edits (rebuild identical) and strip back to 17d1ca2 byte for byte; "
          "the full chain strips to f253890", xb.build_visual() == V and xb.build_strategy() == S
          and xb.strip_visual4(V) == V0 and xb.strip_strategy4(S) == S0
          and xb.strip_visual(V) == xb.show(xb.BASE_REV, xb.VIS_PATH) and xb.strip_strategy(S) == xb.show(xb.BASE_REV, xb.STR_PATH)
          and {k for k, _, _ in xb.VISUAL_EDITS4} == {"header", "import", "dsmode", "accmode", "rn", "fvg", "fvgdir", "display"}
          and {k for k, _, _ in xb.STRATEGY_EDITS4} == {"header", "import", "dsmode", "accmode", "rn", "fvg", "fvgdir"})
    removed_v = sorted([xb.IMPORT_6.strip(), 'zoneCfg.useRnSource          := enableRn and syminfo.ticker == "XAUUSD"',
                        "float  FVG_MIN_WIDTH    = 3.0", "if array.get(gFvgAlive, s)", "if array.get(gFvgAlive, s)",
                        "if z.state != ST_BROKEN",
                        'tooltip = "XAUUSD (ticker 完全一致) のみ。Zone 範囲に 100ドル節目があれば +3、無ければ 50ドル節目で +2。\\n" +',
                        '"Confluence の独立カテゴリとして Zone ごとに1回だけ。Zone の幅・位置は変えない。")'])
    removed_s = sorted([l for l in removed_v if l != "if z.state != ST_BROKEN"])
    new_names = set(NEW_ZONE)
    ok_add = (r"^(" + "|".join(sorted(new_names | {"showGeom"})) + r")\s*=\s*input\.\w+\(|^tooltip = |^\"|^zoneCfg\."
              r"(accScoreMax|accEdgeOnce|dsMerge|dsDist|rnStepMajor|rnScoreMajor|rnStepMinor|rnScoreMinor|useRnSource)\s+:= "
              r"|^float rnM(aj|in)T   = |^int   rnM(aj|in)I   = |^bool  rnStepOK = |^and rnMinI > 0 |^if enableRn and not rnStepOK$"
              r"|^runtime\.error\(\"Round Number: |^float  FVG_MIN_WIDTH    = fvgMinWidth$|^import sekine3310/ZoneEnginePracticalXAUUSD/1 as zn$"
              r"|^int want = fvgDirMatch \? |^if array\.get\(gFvgAlive, s\) and \(want == 0 or array\.get\(gFvgDir, s\) == want\)$")
    ok_add_v = ok_add + (r"|^int   fd   = array\.get\(gFvgDir, slot\)|^if z\.state != ST_BROKEN and \(not fvgDirMatch or "
                         r"|^f_usdGeom\(zn\.Zone z\) =>$|^f_num\(z\.top, format\.mintick\) |^if showGeom$|^txt := txt \+ \"\\n\" \+ f_usdGeom\(z\)$")
    res = {}
    for name, old, new, rem, pat in (("V", V0, V, removed_v, ok_add_v), ("S", S0, S, removed_s, ok_add)):
        ch = list(es.changed_code(old, new))
        got_rem = [l for l in rem if l in ch]
        for l in rem:
            if l in ch:
                ch.remove(l)
        res[name] = (sorted(got_rem) == sorted(rem), [l for l in ch if l and not re.search(pat, l)])
    check("XE-05 code delta vs 17d1ca2 only: import, new inputs + config, RN step check, FVG Min Width input, FVG direction "
          "filter (2 selections in both; + the FVG-only display in the Visual), Visual width label; removed lines exactly the "
          "/6 import, the RN gate line, the FVG constant, the candidate conditions and the RN tooltip text",
          all(r[0] and not r[1] for r in res.values()), str({k: v[1][:3] for k, v in res.items()}))
    vv, vs = input_values(V), input_values(S)
    bad = [n for n, x in NEW_ZONE.items() if vv.get(n) != x or vs.get(n) != x]
    vd, sd = input_decls(V), input_decls(S)
    check("XE-06 new inputs in both files with the specified defaults: Accum Score Sum (Sum / Max), Accum Edge Separate "
          "(Separate / Once per TF), Day/Swing Separate (Separate / Merge Nearby), Merge Distance 0 USD (min 0; tooltip: not "
          "an adopted Merge value, inert under Separate), FVG Min Width 3.0, FVG Direction Match OFF, RN 100 +3 / 50 +2; "
          "Visual width label ON; Strategy has no display input",
          not bad and 'options = ["Sum", "Max"]' in vd["accScoreMode"] and 'options = ["Separate", "Once per TF"]' in vd["accEdgeMode"]
          and 'options = ["Separate", "Merge Nearby"]' in vd["dsMode"] and "minval = 0.0" in vd["dsDist"]
          and "Merge Nearby の採用値ではない" in vd["dsDist"] and "作用しない" in vd["dsDist"]
          and "MA Slope Bonus の集計 (Max) とは別" in vd["accScoreMode"]
          and vv.get("showGeom") == "true" and "showGeom" not in sd and "showScore" not in sd, str(bad))
    zone_names = set(input_decls(S[:S.index("// ==== ZONE Strategy · Zone evaluation (begin)")])) | {"fvgMinWidth", "fvgDirMatch"}
    fns = ("f_fvcZoneDisplay(zn.Zone z) =>", "f_zpoBestFvg(zn.Zone z) =>", "f_fvgConfirmed(float minWidth) =>")
    rnchk = lambda t: seg(t, "// 刻みの検証 (最小価格刻みの整数で比べる)", "// ---- 2.8 Cluster")
    check("XE-07 Visual / Strategy parity: every Zone / FVG input declaration (incl. the new ones), every ZoneCfg assignment, "
          "the RN step check, the FVG detection / selection functions (direction filter) and the FVG Batch A block identical",
          zone_names >= new_names and all(vd.get(n) == sd.get(n) for n in zone_names)
          and re.findall(r"^zoneCfg\.\w+\s*:=.*$", V, re.M) == re.findall(r"^zoneCfg\.\w+\s*:=.*$", S, re.M)
          and rnchk(V) == rnchk(S) and rnchk(V)
          and all(code_only(func(V, h)).rstrip() == code_only(func(S, h)).rstrip() for h in fns)
          and code_only(seg(V, "// ==== FVG Batch A (begin)", "// ==== FVG Batch A (end)"))
          == code_only(seg(S, "// ==== FVG Batch A (begin)", "// ==== FVG Batch A (end)")),
          str([n for n in zone_names if vd.get(n) != sd.get(n)]))
    cfg_new = re.findall(r"^zoneCfg\.(accScoreMax|accEdgeOnce|dsMerge|dsDist|rnStepMajor|rnScoreMajor|rnStepMinor|rnScoreMinor|useRnSource)\s*:= (.*)$", V, re.M)
    zd = zcfg_defaults(E)
    check("XE-08 defaults reproduce the current Engine input: accScoreMax false (Sum), accEdgeOnce false (Separate), dsMerge "
          "false (Separate, dsDist unread), RN 100 / 3 / 50 / 2 = the Engine ZoneCfg defaults the old scripts relied on, "
          "useRnSource = enableRn and rnStepOK (true for 100 / 50) and ticker XAUUSD; FVG_MIN_WIDTH = fvgMinWidth (3.0 = old "
          "constant); fvgDirMatch false -> want = 0 / fd test skipped",
          dict(cfg_new) == {"accScoreMax": 'accScoreMode == "Max"', "accEdgeOnce": 'accEdgeMode == "Once per TF"',
                            "dsMerge": 'dsMode == "Merge Nearby"', "dsDist": "dsDist", "rnStepMajor": "rnMajorStep",
                            "rnScoreMajor": "rnMajorScore", "rnStepMinor": "rnMinorStep", "rnScoreMinor": "rnMinorScore",
                            "useRnSource": 'enableRn and rnStepOK and syminfo.ticker == "XAUUSD"'}
          and (zd["rnStepMajor"], zd["rnScoreMajor"], zd["rnStepMinor"], zd["rnScoreMinor"]) == ("100.0", "3.0", "50.0", "2.0")
          and rn_step_ok(100.0, 50.0, 0.001) and rn_step_ok(100.0, 50.0, 0.01)
          and "f_fvgConfirmed(FVG_MIN_WIDTH)" in V and "float  FVG_MIN_WIDTH    = 3.0" in V0 and vv["fvgMinWidth"] == "3.0")
    vd0, sd0 = input_decls(V0), input_decls(S0)
    req = lambda t: re.findall(r"request\.\w+\(", code_only(t))
    check("XE-09 everything else unchanged: every other input declaration (except the RN tooltip text), all XA-3 adopted "
          "defaults, the sizing (f_stQty, qty = pQty on both entries, strategy() 300,000 JPY), the order / cancel / SL / TP / "
          "breakeven code after the FVG functions, calc_on_every_tick false, no alert / weekend code, request lists, Engine "
          "detection inputs (Accum / Swing / MA / session)",
          not [n for n in vd0 if n != "enableRn" and vd0[n] != vd.get(n)] and not [n for n in sd0 if n != "enableRn" and sd0[n] != sd.get(n)]
          and set(vd) - set(vd0) == new_names | {"showGeom"} and set(sd) - set(sd0) == new_names
          and all(vv.get(n) == x and vs.get(n) == x for n, x in XA3.items()) and all(vs.get(n) == x for n, x in XA3_ST.items())
          and func(S, QTY_FN) == func(S0, QTY_FN) and S.count("qty = pQty") == 2
          and seg(S, "strategy(", "import ") == seg(S0, "strategy(", "import ")
          and S.index("var string G_ST =") > S.index("f_zpoBestFvg(zn.Zone z) =>")
          and code_only(S[S.index("var string G_ST ="):]) == code_only(S0[S0.index("var string G_ST ="):])
          and "calc_on_every_tick     = false," in S and "alert(" not in code_only(S) and "dayofweek" not in code_only(S)
          and req(V) == req(V0) and req(S) == req(S0)
          and all(fr.lint_eager_guards(code_only(t)) == [] for t in (E, V, S)))
    st = git("status", "--porcelain").split("\n")
    mod = set(git("diff", "--name-only", PREV, "--").split()) | {l[3:] for l in st if l.startswith("??")}
    mod -= {"tests/__pycache__/"}
    mod = {m for m in mod if not __import__("uj3_adapt").ok(m, PREV)}     # UJ-3 (USDJPY labels): exact
    allowed = {xb.VIS_PATH, xb.STR_PATH, xb.ENG_PATH, "tests/xa_build.py", "tests/xa_sim.py", "tests/xae_sim.py"}
    others = [p for p in os.listdir(ROOT) if p.endswith(".pine") and p not in (xb.VIS_PATH, xb.STR_PATH, xb.ENG_PATH)]
    check("XE-10 vs 17d1ca2 only the Gold Visual / Strategy, the new XAUUSD Engine and xa_build / xa_sim / xae_sim change; "
          "every other Pine file (shared /6, GBPJPY / EURUSD / BTC / USDJPY / GBPUSD Engines, other symbols) byte-identical",
          mod <= allowed and {xb.VIS_PATH, xb.STR_PATH, xb.ENG_PATH} <= mod
          and not [p for p in others if rd(p) != xb.show(PREV, p) and not __import__("uj3_adapt").pine_ok(p, PREV)], str(sorted(mod - allowed)))
    hdr = V[:V.index("//@version=5")] + S[:S.index("//@version=5")]
    check("XE-11 header: XA-4 described as settings parity (initial values give the current Gold computation, not a new "
          "adopted value) in both files; Merge Distance 0 inert; no optimisation / completion claim",
          hdr.count(xb.NOTE4) == 2 and hdr.count("Merge Distance 0 は Separate では作用しない") == 2
          and not re.search(r"最適値です|最適化済み|検証完了|将来も有効|成績一致を確認", hdr))
    geom = func(V, "f_usdGeom(zn.Zone z) =>")
    lab = [m.start() for m in re.finditer(r"    if showGeom\n        txt := txt \+ \"\\n\" \+ f_usdGeom\(z\)\n", V)]
    check("XE-12 width label (Visual): top / bottom with format.mintick, width = z.top - z.bottom (format.mintick, USD), no "
          "Half Width; added to the normal and the FVG-boosted label after the Score text; showGeom read only there "
          "(display only: no Zone / score / order input)",
          "f_num(z.top, format.mintick)" in geom and "f_num(z.bottom, format.mintick)" in geom
          and "f_num(z.top - z.bottom, format.mintick)" in geom and '" USD"' in geom and "zoneHalfWidth" not in geom
          and len(lab) == 2 and V.count("showGeom") == 3 and V.count("f_usdGeom(") == 3
          and func(V, "f_fvcLabelText(zn.Zone z, int dStr, float dScore) =>").count("f_usdGeom(z)") == 1)


# ---- models -----------------------------------------------------------------------------------------------------------
TICK = 0.001
GOLD = dict(acc={"60": 3.0, "240": 4.0, "D": 5.0}, sw={"5": 1.0, "15": 2.0, "60": 3.0}, day=3.0)
conf = lambda c: 3.0 if c >= 4 else {2: 1.0, 3: 2.0}.get(c, 0.0)


def strength(s, htf, thr=(5.0, 10.0, 15.0)):
    t = 1 if s < thr[0] else 2 if s < thr[1] else 3 if s < thr[2] else 4
    return 3 if t == 4 and not htf else t


def finalize(members, acc_max=False, once=False, merge=False, dist=0.0, p=GOLD, variant=None):
    """port of f_finalizeCluster (scoring part). members: dict(cat, sid, tf, base, px0, px1)."""
    base, sw_max, hit = 0.0, None, set()
    hi, lo, acc = {}, {}, {"60": 0.0, "240": 0.0, "D": 0.0}
    dtk = round(dist / TICK) if merge else 0
    dh = next((m["px0"] for m in members if m["sid"] == "DAY_HIGH"), None) if merge else None
    dl = next((m["px0"] for m in members if m["sid"] == "DAY_LOW"), None) if merge else None
    near = lambda a, b: (abs(a - b) <= dist) if variant == "naive" else round(abs(a - b) / TICK) <= dtk
    dhm = dlm = has_dh = has_dl = hz_ind = False
    sw_ind, cats, htf = set(), set(), False
    for m in members:
        cat, sid, tf = m["cat"], m["sid"], m["tf"]
        if cat == "HZ" and sid in ("SWING_H", "SWING_L"):
            mh = merge and sid == "SWING_H" and dh is not None and (near(dh, m["px0"]) or near(dh, m["px1"]))
            ml = merge and sid == "SWING_L" and dl is not None and (near(dl, m["px0"]) or near(dl, m["px1"]))
            if variant == "crossed" and merge:
                mh = sid == "SWING_L" and dh is not None and near(dh, m["px0"])
            dhm, dlm = dhm or mh, dlm or ml
            if not mh and not ml:
                hz_ind = True
                sw_ind.add(tf)
            if tf not in hit:
                hit.add(tf)
                s = p["sw"][tf]
                base += s if sw_max is None else max(0.0, s - sw_max)
                sw_max = s if sw_max is None else max(sw_max, s)
            cats.add("HZ")
            htf |= tf == "60"
        elif cat == "ACC":
            s = p["acc"][tf]
            side = hi if sid == "ACC_HI" else lo
            other = lo if sid == "ACC_HI" else hi
            if not side.get(tf):
                e = 0.0 if (once and other.get(tf) and variant != "once_ignored") else s
                side[tf] = True
                acc[tf] += e
                base += 0.0 if acc_max else e
            cats.add("ACC")
            htf = True
        else:
            base += m["base"]
            cats.add(cat)
            if cat == "HZ":
                hz_ind = True
            if cat == "DHL":
                has_dh |= sid == "DAY_HIGH"
                has_dl |= sid == "DAY_LOW"
    if acc_max:
        base += max(acc.values()) if variant != "max_sum_swapped" else sum(acc.values())
    adj = 0
    if merge and (dhm or dlm):
        tops = [tf for tf in hit if p["sw"][tf] == sw_max]
        blocked = any(tf in sw_ind for tf in tops) and variant != "no_block"
        if variant == "uniform":
            base -= p["day"]
        elif not blocked and tops:
            base -= min(p["day"], sw_max)
        dhl_ind = (has_dh and not dhm) or (has_dl and not dlm)
        if not hz_ind and not dhl_ind and not (dhm and dlm):
            adj = 1
    cat = len(cats) - adj
    sc = base + conf(cat)
    return dict(base=base, cat=cat, score=sc, str=strength(sc, htf))


def finalize6(members, p=GOLD):
    """port of the /6 f_finalizeCluster scoring: each new Accum edge adds its score in member order, no Merge."""
    base, sw_max, hit, seen, cats = 0.0, None, set(), set(), set()
    for m in members:
        cat, sid, tf = m["cat"], m["sid"], m["tf"]
        if cat == "HZ" and sid in ("SWING_H", "SWING_L"):
            if tf not in hit:
                hit.add(tf)
                s = p["sw"][tf]
                base += s if sw_max is None else max(0.0, s - sw_max)
                sw_max = s if sw_max is None else max(sw_max, s)
            cats.add("HZ")
        elif cat == "ACC":
            if (sid, tf) not in seen:
                seen.add((sid, tf))
                base += p["acc"][tf]
            cats.add("ACC")
        else:
            base += m["base"]
            cats.add(cat)
    return base, len(cats)


A = lambda sid, tf: dict(cat="ACC", sid=sid, tf=tf, base=0.0, px0=None, px1=None)
SWH = lambda tf, px, px1=None: dict(cat="HZ", sid="SWING_H", tf=tf, base=0.0, px0=px, px1=px if px1 is None else px1)
SWL = lambda tf, px, px1=None: dict(cat="HZ", sid="SWING_L", tf=tf, base=0.0, px0=px, px1=px if px1 is None else px1)
DH = lambda px: dict(cat="DHL", sid="DAY_HIGH", tf="D", base=3.0, px0=px, px1=px)
DL = lambda px: dict(cat="DHL", sid="DAY_LOW", tf="D", base=3.0, px0=px, px1=px)
PDH = lambda px: dict(cat="HZ", sid="PREV_DH", tf="D", base=2.0, px0=px, px1=px)
MA = lambda: dict(cat="MA", sid="MA1", tf="1", base=3.0, px0=None, px1=None)
COMBOS = [(False, False), (True, False), (False, True), (True, True)]     # (Max, Once)


def accum_fixtures(fin=finalize):
    out = []
    pts = lambda mem: {c: fin(mem, *c)["base"] - sum(m["base"] for m in mem if m["cat"] != "ACC") for c in COMBOS}
    ex = [("1H high + low", [A("ACC_HI", "60"), A("ACC_LO", "60")], [6, 6, 3, 3]),
          ("1H high + low + 4H one side", [A("ACC_HI", "60"), A("ACC_LO", "60"), A("ACC_HI", "240")], [10, 6, 7, 4]),
          ("1H / 4H / D one side each (3 / 4 / 5)", [A("ACC_HI", "60"), A("ACC_HI", "240"), A("ACC_LO", "D")], [12, 5, 12, 5]),
          ("D high + low + 1H high", [A("ACC_HI", "D"), A("ACC_LO", "D"), A("ACC_HI", "60")], [13, 10, 8, 5]),
          ("edge order: low first", [A("ACC_LO", "60"), A("ACC_HI", "60"), A("ACC_HI", "240")], [10, 6, 7, 4]),
          ("1H high twice (duplicate edges removed as now)", [A("ACC_HI", "60"), A("ACC_HI", "60")], [3, 3, 3, 3]),
          ("no Accum", [MA()], [0, 0, 0, 0])]
    for name, mem, exp in ex:
        got = pts(mem)
        out.append((f"Accum {name}: Sum/Separate {exp[0]}, Max/Separate {exp[1]}, Sum/Once {exp[2]}, Max/Once {exp[3]}",
                    [got[c] for c in COMBOS] == exp))
    mem = [A("ACC_HI", "60"), A("ACC_LO", "60"), A("ACC_HI", "240")]
    out.append(("Accum category / HTF unchanged across the four combinations (1 category)",
                len({(fin(mem, *c)["cat"]) for c in COMBOS}) == 1 and fin(mem)["cat"] == 1))
    return out


def ds_fixtures(fin=finalize):
    out = []
    g = lambda mem, d=0.5: (fin(mem, merge=True, dist=d)["score"], fin(mem, merge=True, dist=d)["cat"])
    sep = lambda mem: (fin(mem)["score"], fin(mem)["cat"])
    out.append(("Day/Swing distance 0: identical price merges (Day 3 + 1H Swing 3 -> 3, 1 cat), 0.001 apart does not (6 + 1)",
                g([DH(2700.0), SWH("60", 2700.0)], 0.0) == (3.0, 1) and g([DH(2700.0), SWH("60", 2700.001)], 0.0) == (7.0, 2)))
    out.append(("Day/Swing boundary 0.5 USD: 0.500 apart merges, 0.501 does not; float boundary at 0.3 USD: 2600.0 / 2599.7 "
                "(|diff| = 0.30000000000018 in floats) merges on the tick-integer compare",
                g([DH(2700.5), SWH("60", 2700.0)]) == (3.0, 1) and g([DH(2700.501), SWH("60", 2700.0)]) == (7.0, 2)
                and g([DH(2600.0), SWH("60", 2599.7)], 0.3) == (3.0, 1) and abs(2600.0 - 2599.7) > 0.3))
    out.append(("Day/Swing High with High / Low with Low only: Swing Low at the Day High price is not merged",
                g([DH(2700.0), SWL("60", 2700.0)]) == sep([DH(2700.0), SWL("60", 2700.0)]) == (7.0, 2)))
    out.append(("Day/Swing latest pivot price within the distance merges (first outside)",
                g([DH(2700.0), SWH("60", 2705.0, 2700.2)]) == (3.0, 1)))
    out.append(("Day/Swing independent top Swing blocks the adjustment: Day + 5M Swing merged + 1H Swing 3 USD away -> "
                "Separate 7 (2 cat) = Merge 7 (2 cat)",
                g([DH(2700.0), SWH("5", 2700.2), SWH("60", 2703.0)]) == sep([DH(2700.0), SWH("5", 2700.2), SWH("60", 2703.0)]) == (7.0, 2)))
    out.append(("Day/Swing merged top Swing with an independent lower Swing: Day + 1H merged + 5M away -> 3 + 0 (Swing max) "
                "-> 3 points, categories stay 2 (independent Horizontal) -> 4",
                sep([DH(2700.0), SWH("60", 2700.2), SWH("5", 2706.0)]) == (7.0, 2)
                and g([DH(2700.0), SWH("60", 2700.2), SWH("5", 2706.0)]) == (4.0, 2)))
    out.append(("Day/Swing category adjustment: Day High + Day Low both merged keeps 2 categories; with MA 3 categories -> 2",
                g([DH(2700.0), DL(2690.0), SWH("60", 2700.1), SWL("15", 2690.1)])[1] == 2
                and g([DH(2700.0), SWH("60", 2700.1), MA()]) == (7.0, 2) and sep([DH(2700.0), SWH("60", 2700.1), MA()]) == (11.0, 3)))
    out.append(("Day/Swing previous-day high (independent Horizontal) is not merged and keeps the categories",
                g([DH(2700.0), SWH("60", 2700.1), PDH(2700.0)]) == (6.0, 2)))
    perm = [SWH("60", 2700.1), SWL("15", 2690.2), SWH("5", 2709.0), DH(2700.0), DL(2690.0), MA()]
    res = {tuple(sorted(fin(list(q), merge=True, dist=0.5).items())) for q in itertools.permutations(perm)}
    out.append(("Day/Swing member order invariance (720 orders of a mixed cluster)", len(res) == 1))
    out.append(("Day/Swing Separate never reads the distance (dist 0 / 0.5 / 50 identical under Separate)",
                len({tuple(sorted(fin(perm, dist=d).items())) for d in (0.0, 0.5, 50.0)}) == 1))
    return out


# FVG selection port (f_zpoBestFvg / f_fvcZoneDisplay): slots = list of (alive, dir, top, bot, base, closeT)
ST_ACTIVE, ST_SUPPORT, ST_RESIST, ST_BROKEN = 0, 1, 2, 3


def fvg_select(state, ztop, zbot, slots, dirmatch, variant=None):
    want = (1 if state == ST_SUPPORT else -1 if state == ST_RESIST else 0) if dirmatch else 0
    best = -1
    for s, (alive, d, t, b, base, ct) in enumerate(slots):
        if alive and (want == 0 or d == want or variant == "post_filter"):
            if not (t < zbot or b > ztop):
                if best < 0 or base > slots[best][4] or (base == slots[best][4] and ct > slots[best][5]):
                    best = s
    if variant == "post_filter" and best >= 0 and want != 0 and slots[best][1] != want:
        best = -1
    return best


def fvg_old(ztop, zbot, slots):
    """the 17d1ca2 selection (no direction term)."""
    best = -1
    for s, (alive, d, t, b, base, ct) in enumerate(slots):
        if alive:
            if not (t < zbot or b > ztop):
                if best < 0 or base > slots[best][4] or (base == slots[best][4] and ct > slots[best][5]):
                    best = s
    return best


def fvg_fixtures(sel=fvg_select):
    out = []
    slots = [(True, 1, 2702.0, 2698.0, 1.0, 10), (True, -1, 2703.0, 2699.0, 3.0, 5), (True, -1, 2701.0, 2697.0, 2.0, 7)]
    out.append(("FVG OFF: best by TF score regardless of direction (4H bear chosen) for every state",
                all(sel(stt, 2700.0, 2696.0, slots, False) == 1 for stt in (ST_SUPPORT, ST_RESIST, ST_ACTIVE))))
    out.append(("FVG ON, SUPPORT: only bull FVGs are candidates -> the 15M bull FVG (not 'pick 4H then drop it')",
                sel(ST_SUPPORT, 2700.0, 2696.0, slots, True) == 0))
    out.append(("FVG ON, RESIST: only bear FVGs -> 4H bear; other states (ACTIVE) unchanged",
                sel(ST_RESIST, 2700.0, 2696.0, slots, True) == 1 and sel(ST_ACTIVE, 2700.0, 2696.0, slots, True) == 1))
    only_bear = [s for s in slots if s[1] == -1]
    out.append(("FVG ON, SUPPORT with only bear FVGs: no FVG (no fallback to the opposite direction)",
                sel(ST_SUPPORT, 2700.0, 2696.0, only_bear, True) == -1))
    tie = [(True, 1, 2702.0, 2698.0, 2.0, 5), (True, 1, 2701.0, 2699.0, 2.0, 9), (True, -1, 2702.0, 2698.0, 2.0, 12)]
    out.append(("FVG ON, same TF: the newest same-direction FVG (close time 9), the newer bear one ignored",
                sel(ST_SUPPORT, 2700.0, 2696.0, tie, True) == 1 and sel(ST_SUPPORT, 2700.0, 2696.0, tie, False) == 2))
    random.seed(7)
    eq = True
    for _ in range(3000):
        sl = [(random.random() < 0.8, random.choice((1, -1)), 2700 + random.uniform(-5, 5), 0, random.choice((1.0, 2.0, 3.0)),
               random.randint(0, 50)) for _ in range(random.randint(0, 15))]
        sl = [(a, d, t, t - random.uniform(0.5, 4), b, c) for a, d, t, _, b, c in sl]
        stt = random.choice((0, 1, 2, 3))
        if sel(stt, 2701.0, 2697.0, sl, False) != fvg_old(2701.0, 2697.0, sl):
            eq = False
    out.append(("FVG OFF equals the previous selection on 3,000 random slot sets", eq))
    return out


def rn_level_in(zb, zt, step):
    k1, k2 = math.ceil(zb / step), math.floor(zt / step)
    if k1 > k2:
        return None
    ctr = (zt + zb) / 2
    kc = max(k1, min(k2, math.floor(ctr / step)))
    lv = kc * step
    if kc + 1 <= k2 and (kc + 1) * step - ctr < ctr - lv:
        lv = (kc + 1) * step
    return lv


def rn_pick(zb, zt, on=True, major=(100.0, 3.0), minor=(50.0, 2.0), ticker="XAUUSD", step_ok=True):
    if not (on and step_ok and ticker == "XAUUSD"):
        return None, 0.0
    lv = rn_level_in(zb, zt, major[0])
    if lv is not None:
        return lv, major[1]
    lv = rn_level_in(zb, zt, minor[0])
    return (lv, minor[1]) if lv is not None else (None, 0.0)


def rn_step_ok(major, minor, mintick=0.001):
    mj, mn = major / mintick, minor / mintick
    mji, mni = round(mj), round(mn)
    return (minor > 0 and abs(mj - mji) < 1e-6 and abs(mn - mni) < 1e-6 and mni > 0 and mji >= 2 * mni
            and mji % max(mni, 1) == 0)


def rn_fixtures(pick=rn_pick, ok=rn_step_ok):
    out = []
    out.append(("RN defaults: [2695, 2706] -> 2700 +3; [2744, 2752] -> 2750 +2; [2701, 2749] none; boundary inclusive "
                "(top = 2700.000 / bottom = 2750.000)",
                pick(2695.0, 2706.0) == (2700.0, 3.0) and pick(2744.0, 2752.0) == (2750.0, 2.0) and pick(2701.0, 2749.0) == (None, 0.0)
                and pick(2690.0, 2700.0) == (2700.0, 3.0) and pick(2750.0, 2760.0) == (2750.0, 2.0)))
    out.append(("RN major priority / once per zone: a zone holding 2650 and 2700 gets only the major +3 (one level)",
                pick(2645.0, 2705.0) == (2700.0, 3.0)))
    out.append(("RN gate: OFF, other ticker, invalid steps -> no points; changed inputs (200 +4 / 25 +1) used as given",
                pick(2695.0, 2706.0, on=False) == (None, 0.0) and pick(2695.0, 2706.0, ticker="XAUUSD.x") == (None, 0.0)
                and pick(2695.0, 2706.0, step_ok=False) == (None, 0.0)
                and pick(2795.0, 2806.0, major=(200.0, 4.0), minor=(25.0, 1.0)) == (2800.0, 4.0)
                and pick(2720.0, 2730.0, major=(200.0, 4.0), minor=(25.0, 1.0)) == (2725.0, 1.0)))
    out.append(("RN step check: 100 / 50 OK (mintick 0.001 and 0.01); 75 / 25 OK; 100 / 60 (not a multiple), 50 / 50 "
                "(< 2x), 100 / 0, 100.0005 / 50 (not on the 0.001 tick), 0.005 / 0.002 on tick 0.01 -> invalid",
                ok(100.0, 50.0) and ok(100.0, 50.0, 0.01) and ok(75.0, 25.0) and not ok(100.0, 60.0) and not ok(50.0, 50.0)
                and not ok(100.0, 0.0) and not ok(100.0005, 50.0) and not ok(0.005, 0.002, 0.01)))
    return out


def geom_text(top, bot, mintick=0.001):
    dec = max(0, -int(round(math.log10(mintick))))
    f = lambda v: f"{v:.{dec}f}"
    return f"{f(top)} - {f(bot)} | W {f(top - bot)} USD"


def gate_model():
    random.seed(20261021)
    kinds = [lambda: A(random.choice(("ACC_HI", "ACC_LO")), random.choice(("60", "240", "D"))),
             lambda: SWH(random.choice(("5", "15", "60")), 2700 + random.uniform(-4, 4)),
             lambda: SWL(random.choice(("5", "15", "60")), 2690 + random.uniform(-4, 4)),
             lambda: DH(2700 + random.uniform(-2, 2)), lambda: DL(2690 + random.uniform(-2, 2)), MA, lambda: PDH(2700.0)]
    p = dict(GOLD, acc={"60": 0.7, "240": 1.3, "D": 2.9})     # non-dyadic scores: bit-identity test of the addition order
    bad = 0
    for _ in range(5000):
        mem = [random.choice(kinds)() for _ in range(random.randint(0, 8))]
        r, (b6, c6) = finalize(mem, p=p), finalize6(mem, p=p)
        if r["base"] != b6 or r["cat"] != c6:
            bad += 1
    check("XM-01 defaults (Sum / Separate / Separate, any Merge Distance) == the /6 scoring bit for bit on 5,000 random "
          "clusters (non-dyadic Accum scores 0.7 / 1.3 / 2.9, Day, Swing, MA, previous-day H/L)", bad == 0, str(bad))
    for name, ok in accum_fixtures() + ds_fixtures() + fvg_fixtures() + rn_fixtures():
        check("XM " + name, ok)
    zb, zt = 2693.250, 2710.750      # an integrated zone of three raws (Half Width 6 each) spanning 17.5 USD
    check("XM width label: integrated zone 2710.750 - 2693.250 -> 'W 17.500 USD' (top - bottom, not Half Width x 2 = 12); "
          "mintick 0.01 -> 2 decimals", geom_text(zt, zb) == "2710.750 - 2693.250 | W 17.500 USD"
          and geom_text(zt, zb, 0.01) == "2710.75 - 2693.25 | W 17.50 USD" and abs((zt - zb) - 2 * 6.0) > 1)
    mem = [A("ACC_HI", "60"), A("ACC_LO", "60"), A("ACC_HI", "240"), SWH("60", 2700.1), DH(2700.0)]
    rs = {c: finalize(mem, *c) for c in COMBOS}
    check("XM Score / Strength follow the modes (1H Accum hi/lo + 4H hi + 1H Swing + Day High, 3 categories +2): Sum/Sep "
          "18 Very Strong, Max/Sep 14 Strong, Sum/Once 15 Very Strong, Max/Once 12 Strong; + Merge 0.5 (Sum/Sep) -> 13 + 1 "
          "= 14 Strong (Day + 1H Swing one evidence, 2 categories)",
          [(rs[c]["score"], rs[c]["str"]) for c in COMBOS] == [(18.0, 4), (14.0, 3), (15.0, 4), (12.0, 3)]
          and (finalize(mem, merge=True, dist=0.5)["score"], finalize(mem, merge=True, dist=0.5)["cat"]) == (14.0, 2))


def gate_mutation():
    caught = []
    for v in ("once_ignored", "max_sum_swapped"):
        fx = accum_fixtures(lambda mem, a=False, o=False, v=v, **k: finalize(mem, a, o, variant=v, **k))
        caught.append(not all(ok for _, ok in fx))
    for v in ("naive", "crossed", "no_block", "uniform"):
        fx = ds_fixtures(lambda mem, a=False, o=False, v=v, **k: finalize(mem, a, o, variant=v, **k))
        caught.append(not all(ok for _, ok in fx))
    caught.append(not all(ok for _, ok in fvg_fixtures(lambda *a: fvg_select(*a, variant="post_filter"))))
    caught.append(not all(ok for _, ok in rn_fixtures(ok=lambda a, b, m=0.001: b > 0)))
    check("XU-01 mirror mutations caught: Once ignored, Sum / Max swapped, naive float distance, High / Low crossed, "
          "independent top Swing not blocking, Day subtracted uniformly, direction filter after the choice, no step check",
          all(caught), str(caught))
    muts = [V.replace('accScoreMode = input.string("Sum"', 'accScoreMode = input.string("Max"'),
            S.replace('dsDist = input.float(0.0,', 'dsDist = input.float(0.5,'),
            V.replace("float  FVG_MIN_WIDTH    = fvgMinWidth", "float  FVG_MIN_WIDTH    = 3.0"),
            S.replace("(want == 0 or array.get(gFvgDir, s) == want)", "(want == 0)", 1),
            V.replace(" + \" | W \" + f_num(z.top - z.bottom, format.mintick)", " + \" | W \" + f_num(2 * zoneHalfWidth, format.mintick)"),
            S.replace("import sekine3310/ZoneEnginePracticalXAUUSD/1 as zn", "import sekine3310/ZoneEnginePractical/6 as zn")]
    strip = [xb.strip_visual4, xb.strip_strategy4, xb.strip_visual4, xb.strip_strategy4, xb.strip_visual4, xb.strip_strategy4]
    em = E.replace("float eH1 = c.accEdgeOnce and accLo1 ? 0.0 : m.baseScore", "float eH1 = m.baseScore")
    check("XU-02 source mutations rejected by the exact strip: Accum default Max, Merge Distance 0.5, FVG constant kept, "
          "one selection without the filter, width = 2 x Half Width, Strategy still on /6, Engine edge rule removed",
          all(m != t and f(m) is None for m, t, f in zip(muts, [V, S, V, S, V, S], strip)) and xb.strip_engine(em) != GBE)


def main():
    for g in (gate_static, gate_model, gate_mutation):
        try:
            g()
        except Exception:
            import traceback
            check(f"{g.__name__} completed without error", False, traceback.format_exc()[-900:])
    fails = 0
    for n, ok, d in RESULTS:
        fails += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {n[:150].ljust(150)}  {'' if ok else d}")
    print(f"\n{len(RESULTS) - fails}/{len(RESULTS)} passed  [PINE_NOT_VERIFIED: exact build / static / Python models]")
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
