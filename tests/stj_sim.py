"""STJ-1 fixtures — ZoneStrategyUSDJPY.pine (OANDA:USDJPY 5M, A / B / C / D of ZONE-ST on the ZONE-JPY zones).

  SJ : static — deterministic build (ZONE-JPY -> ST-1 -> ST-2 -> ST-3 -> yen edits) and exact inverse; computation
       part byte-identical to ZONE-JPY (Zone inputs, Engine config, feeds, NR-S1 / NR-A1, FVG Batch A with the yen min
       width), Batch C / overlap copies identical; order block identical to ZONE-ST except the yen SL Buffer / BE
       Trigger; requests = ZONE-ST's (10 + D's 1M); defaults; yen values on the 0.001 mintick grid; no drawing
  SM : models — (1) Engine model on yen-scale synthetic data with the ZONE-JPY yen parameters: Strategy zones / Score /
       Strength / FVG boost range == the ZONE-JPY display mirror on every sampled bar; (2) the ZONE-ST order mirror at
       yen scale: D timing, SL = zone edge -/+ 0.05, TP from the fill (zone / fixed 1.5R), RR skip, BE 0.15, cancel,
       one order at a time

Evidence class: PINE_NOT_VERIFIED. TradingView compile, broker emulator, P/L currency external.
"""
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stj_build as sj          # noqa: E402
import jpy_build as jb          # noqa: E402
import st1_build as tb          # noqa: E402
import st2_build as s2          # noqa: E402
import st3_build as s3          # noqa: E402
import fvg_re10045_sim as fr    # noqa: E402

ROOT = sj.ROOT
STJ = open(os.path.join(ROOT, sj.STJ_PATH), encoding="utf-8").read() if os.path.exists(os.path.join(ROOT, sj.STJ_PATH)) else ""
JPYV = open(os.path.join(ROOT, jb.JPY_PATH), encoding="utf-8").read()
XST = open(os.path.join(ROOT, "ZoneStrategyXAU.pine"), encoding="utf-8").read()
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


def code_only(src):
    return "\n".join(l for l in src.split("\n") if not l.lstrip().startswith("//"))


GEOM = next(a for a, b in sj.EDITS if b == "")


def gate_static():
    pipe = sj.pipeline()
    check("SJ-01 ZoneStrategyUSDJPY.pine == stj_build.build(); strip_stj gives the ZONE-JPY -> ST-3 pipeline text back, "
          "and strip_st3 / strip_st2 lead to st_transform(ZONE-JPY)",
          bool(STJ) and sj.build() == STJ and sj.strip_stj(STJ) == pipe
          and s2.strip_st2(s3.strip_st3(pipe)) == tb.st_transform(JPYV))
    v = JPYV
    comp = v[v.index(tb.IMPORT_LINE):v.index(tb.DISP_INPUT_HEAD)] + \
        v[v.index(tb.DISP_INPUT_LAST) + len(tb.DISP_INPUT_LAST) + 1:v.index(tb.DISPLAY_HEAD)]
    st_comp = STJ[STJ.index(tb.IMPORT_LINE):STJ.index(tb.ST_BEGIN)]
    check("SJ-02 Zone computation part byte-identical to ZONE-JPY (inputs, Engine config, MA / Swing / Accum / Break feeds, "
          "trading day, zn.update, NR-S1, NR-A1, FVG Batch A with the yen FVG Min Width); only the display inputs and "
          "the display-only label helper are left out", st_comp == comp.replace(GEOM, "") and comp.count(GEOM) == 1)
    ev = STJ[STJ.index(tb.ST_BEGIN):]
    copies = [h for h in tb.COPIED_FUNCS if ev.count(tb.func(JPYV, h)) != 1]
    fe_x, fe_j = tb.func(XST, "f_stZoneEval("), tb.func(STJ, "f_stZoneEval(")
    check("SJ-03 FVG scoring (Batch C) / best-FVG selection are byte copies of ZONE-JPY; f_stZoneEval (boost = higher "
          "strength, range = [max bottom, min top]) identical to ZONE-ST", copies == [] and fe_x == fe_j, str(copies))
    xo = XST[XST.index(s3.LOOP_NEW[:60]):]
    jo = STJ[STJ.index(s3.LOOP_NEW[:60]):]
    for a, b in sj.EDITS[3:]:
        jo = jo.replace(b, a)
    check("SJ-04 order block (A / B / C / D, session, opposite-zone TP, breakeven, fill-price TP model, cancel, one "
          "order / Track once) identical to ZONE-ST except the yen SL Buffer and Breakeven Trigger inputs", xo == jo)
    req = lambda s: re.findall(r"request\.\w+\(.*$", code_only(s), re.M)
    check("SJ-05 requests = ZONE-ST's structure: the 10 Zone / FVG requests of ZONE-JPY + one request.security_lower_tf "
          "(1M, only in mode D); nothing else", req(STJ) == req(XST) and len(req(STJ)) == 11
          and [r for r in req(STJ) if "lower_tf" not in r] == req(JPYV))
    inp = lambda n: (re.search(r"^" + n + r"\s*=\s*input\.\w+\((.*)$", STJ, re.M) or [None, ""])[1]
    want = {"stMode": '"D: 1M BOS Rebound",', "stDir": '"Both",', "zoneHalfWidth": "0.05,", "clusterDist": "0.08,",
            "fvgMinWidth": "0.05,", "enableRn": "false,", "stUseSess": "true,", "stSessTz": '"Asia/Tokyo",',
            "stSessStartH": "9,", "stSessStartM": "0,", "stSessEndH": "2,", "stSessEndM": "0,", "stTpZone": "true,",
            "stTpMinRR": "1.0,", "stTpMaxRR": "3.0,", "stRR": "1.5,", "stBE": "false,", "stBEDist": "0.15,",
            "stBuffer": "0.05,", "stDWait": "30,"}
    bad = {k: inp(k) for k, v in want.items() if not inp(k).startswith(v)}
    zin_j = [x for x in re.findall(r"^(\w+)\s*=\s*(input\..*)$", JPYV, re.M)]
    zin_s = dict(re.findall(r"^(\w+)\s*=\s*(input\..*)$", STJ, re.M))
    zdiff = [n for n, a in zin_j if n in zin_s and zin_s[n] != a]
    decl = STJ[STJ.index("strategy(\n"):STJ.index(")\n", STJ.index("strategy(\n")) + 2]
    decl_x = XST[XST.index("strategy(\n"):XST.index(")\n", XST.index("strategy(\n")) + 2]
    check("SJ-06 defaults: Entry Mode D, Both, Half Width 0.05 / Cluster 0.08 / FVG 0.05 yen, Round Number OFF, session ON "
          "JST 09:00-02:00, zone TP ON (RR 1.0 / 3.0, fixed 1.5R), breakeven OFF (trigger 0.15), SL Buffer 0.05, D wait "
          "30; every Zone input identical to ZONE-JPY; strategy() = ZONE-ST (fixed qty 1, pyramiding 0, no tick / close "
          "/ fill recalculation, no Bar Magnifier) apart from the title",
          bad == {} and zdiff == [] and decl.replace("USDJPY", "XAU").replace("ZONE-ST-JPY", "ZONE-ST") == decl_x
          and "default_qty_value      = 1)" in decl and "use_bar_magnifier" not in STJ, str((bad, zdiff)))
    yen = {}
    for n in ("zoneHalfWidth", "clusterDist", "fvgMinWidth", "stBuffer", "stBEDist", "breakBuffer", "flipConfirmDist",
              "touchRearmDist", "maClusterDist", "slopeThrMod", "slopeThrStrong"):
        a = inp(n)
        nums = [float(a.split(",")[0])] + [float(x) for x in re.findall(r"(?:minval|step) = ([0-9.]+)", a)]
        yen[n] = all(abs(x * 1000 - round(x * 1000)) < 1e-6 for x in nums) and "円" in a
    check("SJ-07 every yen price-difference input (default, minval, step) is on the OANDA USDJPY 0.001 price grid and "
          "labelled in 円; no $ input left", all(yen.values())
          and not [n for n, a in re.findall(r"^(\w+)\s*=\s*input\.float\((.*)$", code_only(STJ), re.M) if "$" in a],
          str(yen))
    co = code_only(STJ)
    check("SJ-08 no drawing (box / label / line / table), plots only to the data window (ZONE-ST's 7), RE10045 lint clean, "
          "one zone loop (zn.zoneAt / f_stZoneEval once)",
          not re.search(r"\b(box|label|line|table)\.(new|set_\w+|delete)\b", co)
          and len(re.findall(r"^plot\(", co, re.M)) == 7
          and all("display = display.data_window" in l for l in re.findall(r"^plot\(.*$", co, re.M))
          and fr.lint_eager_guards(co) == [] and co.count("zn.zoneAt(") == 1 and co.count("= f_stZoneEval(z)") == 1)
    names = ["ZoneVisualPractical.pine", "ZoneVisualUSDJPY.pine", "ZoneStrategyXAU.pine", "ZoneEnginePractical.pine",
             "ZoneEnginePracticalRN.pine", "ZoneEnginePracticalSwingMax.pine", "PracticalZoneStrategy_LONG.pine",
             "PracticalZoneStrategy_SHORT.pine", "SignalEnginePractical.pine"]
    d = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", "5e2459b", "--"] + names, capture_output=True, text=True).stdout
    check("SJ-09 ZONE-P, ZONE-JPY, ZONE-ST (XAU), Engines (/2, /5, /6) and the old strategies unchanged vs 5e2459b",
          d.strip() == "", d)


# =============================================================================
# SM-1 : Zone parity on yen-scale synthetic data
# =============================================================================
YEN = dict(zoneHalfWidth=0.05, clusterDist=0.08, slopeThrMod=0.02, slopeThrStrong=0.05, maClusterDist=0.30,
           touchRearmDist=0.15, breakBuffer=0.08, flipConfirmDist=0.15, maClusterBonus=0.0, maClusterDirBonus=0.0,
           flipBonus=0.0)
FVG_MIN = 0.05


def gate_zone_parity():
    import rn1_engine_model as em
    import zp_overlap_sim as zs
    import st1_sim as t1
    C = em.C
    keep = {k: getattr(C, k) for k in YEN}
    orig_market, orig_fvg = em.market1m, em.fvg_at

    def market_yen(seed, days=14, miss5=0.0):
        return [(t, round(150 + (o - 2000) / 60, 3), round(150 + (h - 2000) / 60, 3), round(150 + (l - 2000) / 60, 3),
                 round(150 + (c - 2000) / 60, 3)) for t, o, h, l, c in orig_market(seed, days, miss5)]

    def fvg_yen(H, j):
        if j < 2:
            return (H[j]["T"], H[j]["C"], None, 0, None, None)
        hi = lambda k: max(s[1] for s in H[k]["subs"])
        lo = lambda k: min(s[2] for s in H[k]["subs"])
        bull, bear = lo(j) > hi(j - 2), hi(j) < lo(j - 2)
        top = lo(j) if bull else lo(j - 2) if bear else None
        bot = hi(j - 2) if bull else hi(j) if bear else None
        d = (1 if bull else -1) if (bull or bear) and round(top - bot, 3) >= FVG_MIN else 0
        return (H[j]["T"], H[j]["C"], H[j]["subs"][-1][3], d, top, bot)

    rep = dict(snaps=0, zones=0, fvg=0, boosted=0, bad=0, widths=[])
    try:
        for k, v in YEN.items():
            setattr(C, k, v)
        em.market1m, em.fvg_at = market_yen, fvg_yen
        for seed in (4, 5):
            b1, chart, htf = em.build(seed, 12)
            F = em.Feeds(b1, chart, htf, "nr")
            E = em.Engine()
            E.rn_attach, E.swing_max = False, True
            cfg = zs.Cfg(show={1: True, 2: True, 3: True, 4: True}, showState={0: True, 1: True, 2: True, 3: True},
                         maxZonesDraw=10 ** 6)
            for i in range(len(chart)):
                E.update(F.feed(i, len(chart[i]["subs"]) - 1, "hist"), i)
                if i % 30 != 29:
                    continue
                rep["snaps"] += 1
                zones = [dict(top=z["top"], bottom=z["bottom"], baseSum=z["baseSum"], catCount=z["catCount"],
                              hasHtf=z["hasHtf"], state=z["state"], touch=z["touch"], slopeBonus=z["slopeB"],
                              maBonus=z["maB"], flipBonus=z["flipBonus"], score=z["score"], strength=z["strength"])
                         for z in E.live]
                S = zs.Slots([zs.fvg(s, E.fTop[s], E.fBot[s], E.fClose[s], True) for s in range(15) if E.fAlive[s]])
                boxes, _ = zs.draw_new(cfg, zones, S)
                for kz, z in enumerate(zones):
                    rep["zones"] += 1
                    rep["widths"].append(round(z["top"] - z["bottom"], 3))
                    dS, dSt, best, boosted, bT, bB, vT, vB = t1.st_zone_eval(cfg, z, S, zs)
                    rep["fvg"] += best >= 0
                    rep["boosted"] += boosted
                    boost_box = [(x[3], x[4], x[5]) for x in boxes if x[2] == kz and x[1] == "boost"]
                    rep["bad"] += boost_box != ([(bT, bB, dSt)] if boosted else []) or (dS, dSt) != zs.zone_display(cfg, z, S)
    finally:
        for k, v in keep.items():
            setattr(C, k, v)
        em.market1m, em.fvg_at = orig_market, orig_fvg
    w = sorted(rep.pop("widths"))
    med = w[len(w) // 2] if w else None
    check("SM-01 yen-scale synthetic USDJPY (~150, 0.001 grid) with the ZONE-JPY yen parameters: Strategy f_stZoneEval == "
          "ZONE-JPY display (Score / Strength / adopted FVG / boost range) for every zone on every sampled bar; zones, "
          "FVGs (min 0.05) and boosts occur", rep["bad"] == 0 and rep["zones"] > 0 and rep["fvg"] > 0 and rep["boosted"] > 0
          and w[0] >= 2 * 0.05 - 1e-9, f"{rep} median width {med} min {w[0] if w else None}")
    return med


# =============================================================================
# SM-2 : order mirror at yen scale
# =============================================================================
def gate_orders_yen():
    import st3_sim as t3
    Z, run3 = t3.Z, t3.run3
    SUP, RES = t3.SUP, t3.RES
    J = dict(buffer=0.05, bedist=0.15, e=2 * 60)
    zl = Z(1, SUP, 150.100, 150.000)
    flat = (150.300, 150.320, 150.280, 150.300)
    bt = (150.250, 150.260, 150.050, 150.130)          # decision close = next open (pre-check reference = fill)
    m1 = [[(0, 150.32, 150.28, 150.30)],
          [(5, 150.26, 150.20, 150.22), (6, 150.21, 150.05, 150.08), (7, 150.12, 150.06, 150.11),
           (8, 150.24, 150.10, 150.23), (9, 150.24, 150.13, 150.15)], [], []]
    nxt = (150.130, 150.160, 150.120, 150.150)
    S, B = run3([flat, bt, nxt, (150.15, 150.20, 150.10, 150.18)], [[zl]] * 4, m1s=m1, mode="D", tpzone=False, be=False, **J)
    o = t3.orders(S)
    tp = S.log[2].get("tp")
    ok1 = o and o[0][0] == 1 and abs(o[0][1]["SL"] - 149.950) < 1e-9 and B.fills and B.fills[0]["price"] == 150.130 \
        and tp is not None and abs(tp - (150.130 + 1.5 * 0.180)) < 1e-9
    check("SM-02 D at yen scale: touch from above -> 1M BOS (close 150.23 > 150.21) -> order at the 5M close, filled at the "
          "next open 150.130; SL = zone bottom 150.000 - 0.05 = 149.950 fixed with the entry; TP 150.400 (= fill + 1.5 x "
          "0.180) first set at the fill-bar close", ok1, str((o, B.fills, S.log[2])))
    res = []
    for rr, exp in ((0.95, "skip"), (1.05, "zone"), (2.95, "zone"), (3.05, "fixed")):
        edge = round(150.130 + rr * 0.180, 3)
        S, B = run3([flat, bt, nxt, (150.15, 150.20, 150.10, 150.18)], [[zl, Z(9, RES, edge + 0.05, edge, sZ=2)]] * 4,
                    m1s=m1, mode="D", be=False, **J)
        lg = S.log[2] if len(t3.orders(S)) else {}
        got = "skip" if (not t3.orders(S) or lg.get("rr_skip")) else ("zone" if lg.get("tp") == edge else "fixed")
        res.append((rr, got, exp))
    check("SM-03 opposite-zone TP at yen scale (fill 150.130, risk 0.180): zone RR 0.95 -> skipped, 1.05 / 2.95 -> zone "
          "edge, 3.05 -> fixed 1.5R", all(g == e for _, g, e in res), str(res))
    S, B = run3([flat, bt, nxt, (150.15, 150.281, 150.14, 150.20), (150.12, 150.13, 150.10, 150.11)], [[zl]] * 5,
                m1s=m1 + [[]], mode="D", tpzone=False, be=True, **J)
    S2, _ = run3([flat, bt, nxt, (150.15, 150.279, 150.14, 150.20)], [[zl]] * 4, m1s=m1, mode="D", tpzone=False, be=True, **J)
    check("SM-04 breakeven trigger 0.15 yen (when switched ON): high 150.281 (>= 150.130 + 0.15) moves the stop to the fill "
          "from the next bar (stopped at the next open 150.12 in the emulator); 150.279 does not",
          S.log[3].get("be") and B.closed and B.closed[0]["exit_bar"] == 4 and not S2.log[3].get("be"),
          str((S.log[3], B.closed, S2.log[3])))
    za = Z(1, SUP, 150.100, 150.000)
    S, B = run3([flat, (150.30, 150.32, 150.12, 150.30), (150.30, 150.32, 150.05, 150.10)], [[za], [dict(za, state=0)], [za]],
                mode="A", tpzone=False, be=False, **J)
    check("SM-05 A at yen scale: limit at the zone top 150.100 with SL 149.950; cancelled at the confirmed bar where the "
          "Track is no longer SUPPORT; the later cross of 150.100 does not fill",
          t3.orders(S)[:1] and t3.orders(S)[0][1]["L"] == 150.100 and abs(t3.orders(S)[0][1]["SL"] - 149.950) < 1e-9
          and "cancel" in S.log[1] and not B.fills, str((S.log, B.fills)))
    S, B = run3([flat, bt, nxt, (150.15, 150.20, 150.10, 150.18)], [[zl, Z(2, SUP, 150.110, 150.020)]] * 4, m1s=m1,
                mode="D", tpzone=False, be=False, **J)
    check("SM-06 one order at a time / Track once at yen scale: two zones touched with the same BOS -> one order",
          len(t3.orders(S)) == 1 and len(B.fills) == 1, str(t3.orders(S)))


def main():
    for g in (gate_static, gate_zone_parity, gate_orders_yen):
        try:
            r = g()
            if g is gate_zone_parity:
                print(f"[info] yen-scale synthetic median zone width: {r}")
        except Exception:
            import traceback
            check(f"{g.__name__} completed without error", False, traceback.format_exc()[-800:])
    fails = 0
    for n, ok, d in RESULTS:
        fails += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {n[:150].ljust(150)}  {'' if ok else d}")
    print(f"\n{len(RESULTS) - fails}/{len(RESULTS)} passed  [PINE_NOT_VERIFIED: static / model / mirror + emulator]")
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
