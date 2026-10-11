"""ST-1 fixtures — ZoneStrategyXAU.pine (ZONE-P Zone logic reused verbatim, no drawing, no orders yet).

  TS : static — deterministic build from ZONE-P, strategy() settings, computation part byte-identical to ZONE-P (inputs,
       config, feed, NR-S1, NR-A1, RN, Break, zn.update, FVG Batch A), Batch C / f_zpoBestFvg byte copies, boost / overlap
       expressions identical to the overlap-only display, no drawing / orders, requests, FVG always on, nothing else
       in the repo changed
  TM : model parity — Engine time-series model + the ZONE-P draw mirror vs a port of f_stZoneEval: same zones, Score /
       Strength, Touch, Track, adopted FVG, boost range, FVG overlap range and boosted Score / Strength

Evidence class: PINE_NOT_VERIFIED (exact build / static / model; TradingView compile / Profiler external).
"""
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import st1_build as tb                # noqa: E402
import nr_s1_build as nb              # noqa: E402
import nr_a1_build as na              # noqa: E402
import fvg_batch_c_build as cb        # noqa: E402
import zp_overlap_build as zp         # noqa: E402
import rnv_build as vb                # noqa: E402
import fvg_re10045_sim as fr          # noqa: E402

ROOT = tb.ROOT
ST = open(os.path.join(ROOT, tb.ST_PATH), encoding="utf-8").read() if os.path.exists(os.path.join(ROOT, tb.ST_PATH)) else ""
VIS = open(os.path.join(ROOT, "ZoneVisualPractical.pine"), encoding="utf-8").read()
BASE = tb.git_show(tb.ST_BASE_REV)
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


def code_only(src):
    return "\n".join(l for l in src.split("\n") if not l.lstrip().startswith("//"))


def block(src, b, e):
    if src.count(b) != 1 or src.count(e) != 1:
        return None
    i = src.index(b)
    return src[i:src.index("\n", src.index(e)) + 1]


def inputs(src):
    return re.findall(r"^\s*(\w+)\s*=\s*(input\.\w+\(.*)$", src, re.M)


# =============================================================================
# TS : static
# =============================================================================
def gate_static():
    check("TS-01 ZoneStrategyXAU.pine == st_transform(ZONE-P @ beca989) and == st_transform(current ZONE-P) (in sync)",
          bool(ST) and tb.st_transform(BASE) == ST and tb.st_transform(VIS) == ST)
    decl = ST[ST.index("strategy(\n"):ST.index(")\n", ST.index("strategy(\n")) + 2]
    check("TS-02 strategy(): calc_on_every_tick = false, process_orders_on_close = false, dynamic_requests = true, "
          "overlay; no indicator(); single import ZoneEnginePractical/6",
          "calc_on_every_tick     = false" in decl and "process_orders_on_close = false" in decl
          and "dynamic_requests       = true" in decl and "indicator(" not in code_only(ST)
          and re.findall(r"^import .*$", ST, re.M) == ["import sekine3310/ZoneEnginePractical/6 as zn"], decl)
    # computation part: ZONE-P from the import to the DISPLAY section, minus the display-input group
    v = VIS
    comp = v[v.index(tb.IMPORT_LINE):v.index(tb.DISP_INPUT_HEAD)] + \
        v[v.index(tb.DISP_INPUT_LAST) + len(tb.DISP_INPUT_LAST) + 1:v.index(tb.DISPLAY_HEAD)]
    st_comp = ST[ST.index(tb.IMPORT_LINE):ST.index(tb.ST_BEGIN)]
    check("TS-03 computation part byte-identical to ZONE-P: inputs, Engine config, MA / Swing / Accum / Break feeds, "
          "trading day, zn.update, FVG Batch A (only the display-input group left out)", st_comp == comp)
    for name, b, e in (("NR-S1", nb.NRS_BEGIN, nb.NRS_END), ("NR-A1", na.NRA_BEGIN, na.NRA_END), ("FVG Batch A", cb.A_BEGIN, cb.A_END)):
        check(f"TS-04 {name} block byte-identical to ZONE-P", block(ST, b, e) is not None and block(ST, b, e) == block(VIS, b, e))
    cfg = lambda s: re.findall(r"^zoneCfg\.\w+\s*:=.*$", s, re.M)
    check("TS-05 every zoneCfg assignment identical to ZONE-P (Swing / Accum / MA bonuses 0 / Flip 0 / RN for XAUUSD ...)",
          cfg(ST) == cfg(VIS) and ST.count(vb.RN_CFG_LINE) == 1, str(len(cfg(ST))))
    vi, si = inputs(VIS), inputs(ST)
    disp = {"showZones", "showMaLines", "showLabels", "showDetailLbl", "maxZonesDraw", "zoneLeftBars", "zoneRightBars",
            "colSupport", "colResistance", "colActive", "colBroken", "trWeak", "trMedium", "trStrong", "trVStrong",
            "showScore", "showStats", "showWeak", "showMedium", "showStrong", "showVStrong", "showSupport",
            "showResistance", "showBroken", "showActive"}
    check("TS-06 inputs = ZONE-P inputs minus the display-only ones (same order, same defaults); no FVG on / off input "
          "(FVG always on)", si == [x for x in vi if x[0] not in disp] and not re.search(r"(?i)fvg", " ".join(n for n, _ in si)),
          str([n for n, _ in si if n not in dict(vi)]))
    ev = block(ST, tb.ST_BEGIN, tb.ST_END) or ""
    copies = [h for h in tb.COPIED_FUNCS if ev.count(tb.func(VIS, h)) != 1 or ST.count("\n" + h) != 1]
    check("TS-07 Batch C scoring (f_fvcConf / f_fvcStrengthOf / f_fvcBase / f_fvcOverlap / f_fvcZoneDisplay) and "
          "f_zpoBestFvg are byte copies of ZONE-P, defined once", copies == [], str(copies))
    zpo = block(VIS, zp.ZPO_BEGIN, zp.ZPO_END)
    lines = ["[dScore, dStr] = f_fvcZoneDisplay(z)", "int  best    = f_zpoBestFvg(z)",
             "bool boosted = best >= 0 and dStr > z.strength",
             "oTop := math.min(z.top, array.get(gFvgTop, best))", "oBot := math.max(z.bottom, array.get(gFvgBot, best))"]
    fe = tb.func(ST, "f_stZoneEval(")
    check("TS-08 f_stZoneEval uses the overlap-only display's exact expressions (Batch C score, adopted FVG, boost = higher "
          "strength, range = [max bottom, min top]); FVG overlap range from the same adopted FVG",
          all(zpo.count(l) == 1 and fe.count(l) == 1 for l in lines)
          and "vTop := math.min(z.top, array.get(gFvgTop, best))" in fe and "vBot := math.max(z.bottom, array.get(gFvgBot, best))" in fe
          and "    if best >= 0\n        vTop" in fe and "    if boosted\n        oTop" in fe)
    co = code_only(ST)
    check("TS-09 no drawing and no orders: no box / label / line / table / barstate.islast, plots only to the data "
          "window, no strategy.entry / exit / order / close",
          not re.search(r"\b(box|label|line|table)\.(new|set_\w+|delete)\b|barstate\.islast", co)
          and all("display = display.data_window" in l for l in re.findall(r"^plot\(.*$", co, re.M))
          and len(re.findall(r"^plot\(", co, re.M)) == 3 and not re.search(r"strategy\.(entry|exit|order|close|cancel)", co))
    check("TS-10 evaluation runs only on confirmed 5M bars; RE10045 lint clean; no request / var in the evaluation block",
          "if is5mChart and barstate.isconfirmed\n" in ev and fr.lint_eager_guards(code_only(ev)) == []
          and not re.search(r"request\.|\bvar\b", code_only(ev)))
    req = lambda s: re.findall(r"request\.\w+\(.*$", code_only(s), re.M)
    check("TS-11 request.security call sites identical to ZONE-P (10)", req(ST) == req(VIS) and len(req(ST)) == 10)
    names = ["ZoneVisualPractical.pine", "ZoneEnginePractical.pine", "ZoneEnginePracticalRN.pine",
             "ZoneEnginePracticalSwingMax.pine", "PracticalZoneStrategy_LONG.pine", "PracticalZoneStrategy_SHORT.pine",
             "SignalEnginePractical.pine"]
    d = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", tb.ST_BASE_REV, "--"] + names, capture_output=True, text=True).stdout
    check("TS-12 ZONE-P, Engines (/2, /5, /6), Strategy LONG / SHORT, SignalEngine unchanged vs beca989", d.strip() == "", d)


# =============================================================================
# TM : model parity (ZONE-P draw mirror vs f_stZoneEval port)
# =============================================================================
def st_zone_eval(c, z, S, zs):
    """port of f_stZoneEval."""
    dScore, dStr = zs.zone_display(c, z, S)
    best = zs.best_fvg(z, S)
    boosted = best >= 0 and dStr > z["strength"]
    oTop, oBot = z["top"], z["bottom"]
    if boosted:
        oTop, oBot = min(z["top"], S.get("top", best)), max(z["bottom"], S.get("bot", best))
    bTop, bBot = (oTop, oBot) if boosted else (None, None)
    vTop = vBot = None
    if best >= 0:
        vTop, vBot = min(z["top"], S.get("top", best)), max(z["bottom"], S.get("bot", best))
    return dScore, dStr, best, boosted, bTop, bBot, vTop, vBot


def gate_model():
    import rn1_engine_model as em
    import zp_overlap_sim as zs
    C = em.C
    keep = (C.maClusterBonus, C.maClusterDirBonus, C.flipBonus)
    C.maClusterBonus, C.maClusterDirBonus, C.flipBonus = 0.0, 0.0, 0.0           # ZONE-P defaults (bon)
    rep = dict(snaps=0, zones=0, fvg=0, boosted=0, bad=0, bad_engine=0)
    try:
        for rn in (False, True):
            for seed in (4, 5):
                b1, chart, htf = em.build(seed, 12)
                F = em.Feeds(b1, chart, htf, "nr")
                V, S_ = em.Engine(), em.Engine()                 # ZONE-P and Strategy run the same Engine / feeds
                for E in (V, S_):
                    E.rn_attach, E.swing_max = rn, True
                for i in range(len(chart)):
                    f = F.feed(i, len(chart[i]["subs"]) - 1, "hist")
                    V.update(f, i)
                    S_.update(f, i)
                    snap = lambda E: ([(z["top"], z["bottom"], z["score"], z["strength"], z["touch"], z["trackId"], z["state"])
                                       for z in E.live], [(s, E.fTop[s], E.fBot[s], E.fClose[s]) for s in range(15) if E.fAlive[s]])
                    rep["bad_engine"] += snap(V) != snap(S_)
                    if i % 30 != 29:
                        continue
                    rep["snaps"] += 1
                    cfg = zs.Cfg(show={1: True, 2: True, 3: True, 4: True}, showState={0: True, 1: True, 2: True, 3: True},
                                 maxZonesDraw=10 ** 6)
                    zones = [dict(top=z["top"], bottom=z["bottom"], baseSum=z["baseSum"], catCount=z["catCount"],
                                  hasHtf=z["hasHtf"], state=z["state"], touch=z["touch"], slopeBonus=z["slopeB"],
                                  maBonus=z["maB"], flipBonus=z["flipBonus"], score=z["score"], strength=z["strength"])
                             for z in V.live]
                    S = zs.Slots([zs.fvg(s, V.fTop[s], V.fBot[s], V.fClose[s], True) for s in range(15) if V.fAlive[s]])
                    boxes, labels = zs.draw_new(cfg, zones, S)
                    for k, z in enumerate(zones):
                        rep["zones"] += 1
                        dS, dSt, best, boosted, bT, bB, vT, vB = st_zone_eval(cfg, z, S, zs)
                        rep["fvg"] += best >= 0
                        rep["boosted"] += boosted
                        boost_box = [(x[3], x[4], x[5]) for x in boxes if x[2] == k and x[1] == "boost"]
                        exp_box = [(bT, bB, dSt)] if boosted else []
                        disp = zs.zone_display(cfg, z, S)
                        rep["bad"] += boost_box != exp_box or (dS, dSt) != disp \
                            or (best >= 0) != (vT is not None) or (vT is not None and not (z["bottom"] <= vB < vT <= z["top"]))
    finally:
        C.maClusterBonus, C.maClusterDirBonus, C.flipBonus = keep
    check("TM-01 same Engine / feeds: Strategy and ZONE-P zone count, top / bottom, Score / Strength, Touch, Track id, "
          "State and FVG storage identical on every bar (RN OFF / ON, Swing max, bonus defaults 0)",
          rep["bad_engine"] == 0 and rep["snaps"] > 0, str(rep))
    check("TM-02 f_stZoneEval == ZONE-P display: boosted Score / Strength, adopted FVG, boost range == ZONE-P boost box "
          "(all strengths / states shown), FVG overlap range inside the zone for every zone with an FVG",
          rep["bad"] == 0 and rep["fvg"] > 0 and rep["boosted"] > 0, str(rep))


def main():
    for g in (gate_static, gate_model):
        try:
            g()
        except Exception:
            import traceback
            check(f"{g.__name__} completed without error", False, traceback.format_exc()[-500:])
    w = max(len(n) for n, _, _ in RESULTS)
    fails = 0
    for n, ok, d in RESULTS:
        fails += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {n.ljust(w)}  {'' if ok else d}")
    print(f"\n{len(RESULTS) - fails}/{len(RESULTS)} passed  [PINE_NOT_VERIFIED: exact build / static / model]")
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
