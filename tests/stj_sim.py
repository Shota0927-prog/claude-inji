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
STJ = __import__("uj_build").pre_uj(sj.STJ_PATH) if os.path.exists(os.path.join(ROOT, sj.STJ_PATH)) else ""     # UJ-1: USDJPY Visual / Strategy may differ only by the USDJPY Engine split + sizing (exact, see uj_build)
JPYV = __import__("uj_build").pre_uj(jb.JPY_PATH)
XST = __import__("xa_build").pre_xa("ZoneStrategyXAU.pine", open(os.path.join(ROOT, "ZoneStrategyXAU.pine"), encoding="utf-8").read())  # XA-1 Gold defaults stripped -> f253890 text (delta pinned by xa_sim)
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


def code_only(src):
    return "\n".join(l for l in src.split("\n") if not l.lstrip().startswith("//"))


GEOM = next(a for a, b in sj.EDITS if b == "")


def zone_edited(comp):
    """the USDJPY edits that fall inside the Zone computation part (Half Width default, zn.update gating)."""
    out = comp
    for a, b in sj.EDITS:
        if b and out.count(a) == 1:
            out = out.replace(a, b)
    return out


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
          "the display-only label helper are left out; USDJPY edits only: Half Width default 0.03 and zn.update on "
          "confirmed bars", st_comp == zone_edited(comp.replace(GEOM, "")) and comp.count(GEOM) == 1
          and zone_edited(comp) != comp)
    ev = STJ[STJ.index(tb.ST_BEGIN):]
    copies = [h for h in tb.COPIED_FUNCS if ev.count(tb.func(JPYV, h)) != 1]
    fe_x, fe_j = tb.func(XST, "f_stZoneEval("), tb.func(STJ, "f_stZoneEval(")
    check("SJ-03 FVG scoring (Batch C) / best-FVG selection are byte copies of ZONE-JPY; f_stZoneEval (boost = higher "
          "strength, range = [max bottom, min top]) identical to ZONE-ST", copies == [] and fe_x == fe_j, str(copies))
    xo = XST[XST.index(s3.LOOP_NEW[:60]):]
    jo = STJ[STJ.index(s3.LOOP_NEW[:60]):]
    for a, b in reversed(sj.EDITS):
        if b and jo.count(b) == 1:
            jo = jo.replace(b, a)
    check("SJ-04 order block (A / B / C / D, session, opposite-zone TP, breakeven, fill-price TP model, cancel, one "
          "order / Track once) identical to ZONE-ST apart from the USDJPY edits (yen Buffer / BE Trigger, defaults, alert "
          "inputs / functions / confirmed alert / provisional block, saved TP edges): reverting them gives ZONE-ST", xo == jo)
    req = lambda s: re.findall(r"request\.\w+\(.*$", code_only(s), re.M)
    check("SJ-05 requests = ZONE-ST's structure: the 10 Zone / FVG requests of ZONE-JPY + one request.security_lower_tf "
          "(1M, only in mode D); nothing else", req(STJ) == req(XST) and len(req(STJ)) == 11
          and [r for r in req(STJ) if "lower_tf" not in r] == req(JPYV))
    inp = lambda n: (re.search(r"^" + n + r"\s*=\s*input\.\w+\((.*)$", STJ, re.M) or [None, ""])[1]
    want = {"stMode": '"D: 1M BOS Rebound",', "stDir": '"Long Only",', "zoneHalfWidth": "0.03,", "clusterDist": "0.08,",
            "fvgMinWidth": "0.05,", "enableRn": "false,", "stUseSess": "true,", "stSessTz": '"Asia/Tokyo",',
            "stSessStartH": "9,", "stSessStartM": "0,", "stSessEndH": "2,", "stSessEndM": "0,", "stTpZone": "false,",
            "stTpMinRR": "1.0,", "stTpMaxRR": "3.0,", "stRR": "1.3,", "stBE": "false,", "stBEDist": "0.15,",
            "stBuffer": "0.05,", "stDWait": "30,", "stAlertProv": "true,", "stAlertConf": "true,"}
    bad = {k: inp(k) for k, v in want.items() if not inp(k).startswith(v)}
    zin_j = [x for x in re.findall(r"^(\w+)\s*=\s*(input\..*)$", JPYV, re.M)]
    zin_s = dict(re.findall(r"^(\w+)\s*=\s*(input\..*)$", STJ, re.M))
    zdiff = [n for n, a in zin_j if n in zin_s and zin_s[n] != a and n != "zoneHalfWidth"]
    decl = STJ[STJ.index("strategy(\n"):STJ.index(")\n", STJ.index("strategy(\n")) + 2]
    decl_x = XST[XST.index("strategy(\n"):XST.index(")\n", XST.index("strategy(\n")) + 2]
    check("SJ-06 defaults (USDJPY validation setting): Entry Mode D, Long Only, Half Width 0.03 / Cluster 0.08 / FVG 0.05, "
          "SL Buffer 0.05, fixed RR 1.3, session ON JST 09:00-02:00, zone TP OFF (RR 1.0 / 3.0 kept), breakeven OFF "
          "(0.15), D wait 30, Round Number OFF, provisional / confirmed alerts ON; every other Zone input identical to "
          "ZONE-JPY; strategy() = ZONE-ST apart from the title and calc_on_every_tick = true (fixed qty 1, pyramiding 0, "
          "no close / fill recalculation, no Bar Magnifier)",
          bad == {} and zdiff == [] and decl.replace("USDJPY", "XAU").replace("ZONE-ST-JPY", "ZONE-ST").replace(
              "calc_on_every_tick     = true", "calc_on_every_tick     = false") == decl_x
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
          __import__("uj_build").drop_uj(d.split(), "5e2459b") == [], d)


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

# =============================================================================
# SA : provisional / confirmed alerts
# =============================================================================
def gate_alert_static():
    co = code_only(STJ)
    fn = tb.func(STJ, "f_stProvEval(")
    fnc = code_only(fn)
    glob_vars = ["stPrev", "stUsed", "stWaits", "m1LastT", "m1PrevC", "oState", "oSeq", "oEid", "oXid", "oLimit",
                 "oSide", "oTrack", "oL", "oSL", "oTP", "oFill", "oStop", "oBE", "oClosed", "stTpUpPrev", "stTpDnPrev",
                 "stProvBar", "zoneEng", "gFvgTop", "gFvgBot", "gFvgAlive"]
    writes = [v for v in glob_vars if re.search(r"\b" + v + r"\s*(:=|\+=)", fnc)]
    muts = re.findall(r"\b(array\.(?:push|set|remove|clear|insert|shift|pop|unshift)|map\.(?:put|remove|clear)|"
                      r"strategy\.\w+|zn\.\w+|f_stZoneEval|f_fvc\w+|f_zpoBestFvg|request\.\w+|alert)\(", fnc)
    xmut = re.findall(r"\bx\.\w+\s*:=", fnc)
    check("SA-01 provisional evaluation f_stProvEval is read-only: no assignment to any global / var state (candidates, "
          "Track use, BOS waits, processed 1M time, order state, Engine, FVG), no array / map mutation, no order / Engine / "
          "Zone scan / FVG scan / request / alert call; wait values are copied to locals",
          writes == [] and muts == [] and xmut == [] and "ext   := x.ext" in fn, str((writes, muts, xmut)))
    pb = STJ[STJ.index("varip int stProvBar = na"):STJ.index("// ==== ZONE Strategy · Zone evaluation (end)")]
    check("SA-02 provisional block: only when the provisional alert is ON, on the 5M chart, on an unconfirmed tick, with no "
          "pending order / position (oState == 0) and inside the session; at most once per 5M bar via its own varip "
          "(stProvBar); message built only when sending; alert.freq_once_per_bar",
          "if stAlertProv and is5mChart and not barstate.isconfirmed and oState == 0 and stSessOK\n" in pb
          and "    if na(stProvBar) or stProvBar != bar_index\n" in pb and "stProvBar := bar_index" in pb
          and 'alert(f_stAlertMsg("仮", pSide, pPx, pSL), alert.freq_once_per_bar)' in pb
          and co.count("stProvBar") == 4)
    conf = '                if stAlertConf\n                    alert(f_stAlertMsg("確定", side, stModeA ? oL : close, oSL), alert.freq_all)\n'
    i = STJ.index(conf) if STJ.count(conf) == 1 else -1
    gi = STJ.index("if is5mChart and barstate.isconfirmed\n    // (1)")
    check("SA-03 confirmed alert: inside the confirmed-bar order branch right after strategy.entry / strategy.exit (the "
          "order event, not the fill), alert.freq_all, independent of the provisional state (no stProvBar there)",
          i > gi and STJ[STJ.rindex("strategy.exit(oXid, oEid, stop = oSL)\n", 0, i):i].count("\n") == 1
          and "stProvBar" not in code_only(STJ[gi:STJ.index("varip int stProvBar")])
          and len(re.findall(r"\balert\(f_stAlertMsg", co)) == 2)
    msg = tb.func(STJ, "f_stAlertMsg(")
    check("SA-04 message: kind (仮 / 確定), direction, symbol (syminfo.tickerid), Entry Mode, reference price and SL; the "
          "provisional one states it may not be confirmed; built only inside the two alert() calls; no string literal "
          "spans a line (\\n escapes only)",
          all(k in msg for k in ('"【" + kind', '"LONG" : "SHORT"', "syminfo.tickerid", '"\\nMode: " + stMode', '"\\nSL: "',
                                 "不成立になる場合あり"))
          and len(re.findall(r"f_stAlertMsg\(", co)) == 3
          and [l for l in co.split("\n") if l.count('"') % 2 == 1] == [])
    lines = STJ.split("\n")
    gstart = next(k for k in range(len(lines) - 1)
                  if lines[k] == "if is5mChart and barstate.isconfirmed" and lines[k + 1].startswith("    // (1)"))
    gend = next(k for k in range(gstart + 1, len(lines)) if lines[k] and not lines[k].startswith(" "))
    state_w = [k for k, l in enumerate(lines) if re.match(r"\s*(oState|oSeq|oEid|oL|oSL|oTP|oFill|oStop|oBE|oTrack|"
                                                          r"stPrev|m1LastT|m1PrevC|stTpUpPrev|stTpDnPrev)\s*(:=|\+=)", l)]
    upd = STJ.count("if is5mChart and barstate.isconfirmed\n    zoneCountNow := zn.update(zoneEng, zoneCfg, zoneFeed)\n")
    check("SA-05 calc_on_every_tick = true only for the provisional alert: zn.update runs on confirmed bars only, every "
          "order / candidate / BOS-wait / processed-1M state write sits inside the confirmed-5M block, the zone loop "
          "(zn.zoneAt) and FVG storage updates stay confirmed-only (no Engine update / Zone scan / FVG scan per tick)",
          "calc_on_every_tick     = true," in STJ and upd == 1 and code_only(STJ).count("zn.update(") == 1
          and all(gstart < k < gend for k in state_w) and len(state_w) > 15
          and "    if barstate.isconfirmed\n        int nowClose = time_close" in STJ, str(state_w[:3]))
    req = lambda t: re.findall(r"request\.\w+\(", code_only(t))
    check("SA-06 request increase for the alerts = 0 (11 = ZONE-ST; the provisional D check reuses the existing 1M "
          "lower-TF arrays)", len(req(STJ)) == len(req(XST)) == 11)


def prov_eval(S, bar, m1_now, prevC=None, now=None):
    """mirror of f_stProvEval (read-only). m1_now = 1M bars of the forming 5M bar incl. the developing last one."""
    o, h, l, c = bar
    modeA, modeC, modeD = S.mode == "A", S.mode == "C", S.mode == "D"
    # closed 1M bars: every element followed by a newer one, and the last one only when its minute has ended
    # (time + 1 <= now, times in minutes here; Pine: time + 60000 <= timenow). now=None -> the last one is forming.
    m1_now = list(m1_now or [])
    if now is None:
        now = m1_now[-1][0] + 0.5 if m1_now else 0
    closed = [x for j, x in enumerate(m1_now) if j < len(m1_now) - 1 or x[0] + 1 <= now]
    best = {1: None, -1: None}
    for k, cd in enumerate(S.prev):
        dirOK = S.longOK if cd["side"] == 1 else S.shortOK
        if not dirOK or cd["track"] in S.used:
            continue
        px, aS, aSc = None, 0, None
        if modeA:
            px = (cd["top"] if cd["sZ"] >= 3 else cd["bTop"]) if cd["side"] == 1 else (cd["bot"] if cd["sZ"] >= 3 else cd["bBot"])
            aS, aSc = S.adopt(cd, px, px)
            d = abs(c - px)
            ok = (c > cd["top"] if cd["side"] == 1 else c < cd["bot"]) and aS >= 3
        elif modeD:
            w = next((x for x in S.waits if x["c"]["track"] == cd["track"]), None)
            armed = w is not None
            ext, run, lvl, cnt = (w["ext"], w["run"], w["lvl"], w["cnt"]) if w else (None, None, None, 0)
            if w:
                aS, aSc = w["aS"], w["aSc"]
            bos, pc, s_ = False, S.m1PrevC, cd["side"]
            for (tj, hh, ll, cl) in closed:
                if bos or not (S.m1LastT is None or tj > S.m1LastT):
                    continue
                if armed:
                    cnt += 1
                    if (cl > lvl) if s_ == 1 else (cl < lvl):
                        bos = True
                    else:
                        run = max(run, hh) if s_ == 1 else min(run, ll)
                        if (ll < ext) if s_ == 1 else (hh > ext):
                            ext, lvl = (ll if s_ == 1 else hh), run
                        if cnt >= S.dwait:
                            armed = False
                frm = pc is not None and (pc > cd["top"] if s_ == 1 else pc < cd["bot"])
                if not armed and not bos and ll <= cd["top"] and hh >= cd["bot"] and frm:
                    wS, wSc = S.adopt(cd, max(ll, cd["bot"]), min(hh, cd["top"]))
                    if wS >= 3:
                        armed, cnt, aS, aSc = True, 0, wS, wSc
                        ext, run = (ll, hh) if s_ == 1 else (hh, ll)
                        lvl = run
                pc = cl
            d = abs(c - (cd["top"] if s_ == 1 else cd["bot"]))
            ok = bos and (c > cd["top"] if s_ == 1 else c < cd["bot"])
        else:
            aS, aSc = S.adopt(cd, max(l, cd["bot"]), min(h, cd["top"]))
            d = abs(c - (cd["top"] if cd["side"] == 1 else cd["bot"]))
            ok = l <= cd["top"] and h >= cd["bot"] and (c > cd["top"] if cd["side"] == 1 else c < cd["bot"]) and aS >= 3 \
                and (not modeC or S.pat(cd["side"], bar, prevC or bar))
        if ok:
            key = (aS, aSc, d, cd["track"])
            b = best[cd["side"]]
            if b is None or S.better(modeA, key, b[1]):
                best[cd["side"]] = (k, key, px)
    side = 0
    if best[1] and best[-1]:
        if modeA and best[1][1][2] != best[-1][1][2]:
            side = 1 if best[1][1][2] < best[-1][1][2] else -1
    elif best[1]:
        side = 1
    elif best[-1]:
        side = -1
    if side == 0:
        return 0, None, None
    cd = S.prev[best[side][0]]
    ePx = best[side][2] if modeA else c
    sl = cd["bot"] - S.buffer if side == 1 else cd["top"] + S.buffer
    edges = getattr(S, "tpUpPrev" if side == 1 else "tpDnPrev", [])
    if S.tp(side, ePx, sl, S.nearest(edges, side, ePx))[0]:
        return 0, None, None
    return side, ePx, sl


def run_ticks(bars, zones, m1s, ticks, tmins=None, prov=True, conf=True, **kw):
    """bars / zones / m1s as run3; ticks[t] = list of (partial OHLC, 1M bars so far incl. the developing one) evaluated
    before the confirmed step of bar t. Returns (S, B, alerts, mutated)."""
    import copy
    import st3_sim as t3
    S, B = t3.Script3(**kw), t3.Broker()
    alerts, provBar, mutated = [], None, False
    for t in range(len(bars)):
        if t > 0:
            B.process(t, bars[t])
        tm = tmins[t] if tmins else 12 * 60
        for tick in (ticks[t] if t < len(ticks) else []):
            pbar, pm1, pnow = tick if len(tick) == 3 else (tick[0], tick[1], None)
            snap = copy.deepcopy((S.prev, S.waits, S.used, S.m1LastT, S.m1PrevC, S.oState, S.oSL, S.oL, S.log))
            sessOK = (not S.sess) or S.in_sess(tm)
            if prov and S.oState == 0 and sessOK and provBar != t:
                side, px, sl = prov_eval(S, pbar, pm1, bars[t - 1] if t else pbar, pnow)
                if side != 0:
                    provBar = t
                    alerts.append(("仮", t, side))
            mutated |= copy.deepcopy((S.prev, S.waits, S.used, S.m1LastT, S.m1PrevC, S.oState, S.oSL, S.oL, S.log)) != snap
        S.step(t, bars[t], bars[t - 1] if t > 0 else bars[t], zones[t], B, tmin=tm, m1=(m1s[t] if m1s else ()))
        if conf and "order" in S.log[-1]:
            alerts.append(("確定", t, S.log[-1]["order"]["side"]))
    return S, B, alerts, mutated


def gate_alert_model():
    import st3_sim as t3
    Z, SUP, RES = t3.Z, t3.SUP, t3.RES
    J = dict(mode="D", dir="Long", buffer=0.05, rr=1.3, tpzone=False, be=False, e=2 * 60)
    zl = Z(1, SUP, 150.100, 150.000)
    flat = (150.300, 150.320, 150.280, 150.300)
    m1b = [(5, 150.26, 150.20, 150.22), (6, 150.21, 150.05, 150.08), (7, 150.12, 150.06, 150.11),
           (8, 150.24, 150.10, 150.23), (9, 150.24, 150.13, 150.15)]
    m1s = [[(0, 150.32, 150.28, 150.30)], m1b, [], []]
    bt = (150.250, 150.260, 150.050, 150.150)
    nxt = (150.150, 150.160, 150.120, 150.150)
    # ticks inside bar 1: after each 1M bar closes (the next one is developing)
    tk = [[], [((150.25, 150.26, 150.05, 150.08), m1b[:2] + [(7, 150.10, 150.06, 150.09)]),
               ((150.25, 150.26, 150.05, 150.11), m1b[:3] + [(8, 150.12, 150.10, 150.11)]),
               ((150.25, 150.26, 150.05, 150.23), m1b[:4] + [(9, 150.24, 150.20, 150.23)]),
               ((150.25, 150.26, 150.05, 150.20), m1b[:4] + [(9, 150.24, 150.18, 150.20)]),
               ((150.25, 150.26, 150.05, 150.16), m1b[:4] + [(9, 150.24, 150.13, 150.16)])]]
    bars = [flat, bt, nxt, nxt]
    S0, B0 = t3.run3(bars, [[zl]] * 4, m1s=m1s, **J)
    S1, B1, al1, mut1 = run_ticks(bars, [[zl]] * 4, m1s, tk, **J)
    S2, B2, al2, mut2 = run_ticks(bars, [[zl]] * 4, m1s, tk, prov=False, conf=False, **J)
    check("SA-07 alerts ON / OFF do not change the orders: same orders, fills and exits as the strategy run without "
          "ticks (provisional evaluation on 5 ticks of the signal bar)",
          t3.orders(S0) == t3.orders(S1) == t3.orders(S2) and B0.fills == B1.fills == B2.fills and B0.closed == B1.closed)
    check("SA-08 provisional evaluation never changes Zone candidates, Track use, BOS waits, processed 1M time / close or "
          "the order state (deep snapshot before / after every tick)", not mut1 and not mut2)
    check("SA-09 D: the BOS on the closed 1M bar (close 150.23 > 150.21) gives one provisional LONG on the forming bar "
          "(5 ticks -> sent once), then the confirmed LONG at that 5M close (the provisional did not suppress it)",
          al1 == [("仮", 1, 1), ("確定", 1, 1)], str(al1))
    tk_dev = [[], [((150.25, 150.26, 150.05, 150.23), m1b[:3] + [(8, 150.24, 150.10, 150.23)])]]
    _, _, al3, _ = run_ticks(bars, [[zl]] * 4, m1s, tk_dev, **J)
    check("SA-10 the forming 1M bar is not used: a BOS seen only on the last 1M element whose minute has not ended "
          "(time + 1 min > now) gives no provisional (the confirmed alert still comes at the 5M close)",
          al3 == [("確定", 1, 1)], str(al3))
    # same last element, but its minute has ended (no newer 1M bar yet) -> it is closed and counts
    tk_end = [[], [((150.25, 150.26, 150.05, 150.23), m1b[:3] + [(8, 150.24, 150.10, 150.23)], 9.0)]]
    _, _, al3b, _ = run_ticks(bars, [[zl]] * 4, m1s, tk_end, **J)
    # array without a forming element (all returned bars closed) -> the last one counts
    tk_all = [[], [((150.25, 150.26, 150.05, 150.23), m1b[:4], 9.2)]]
    _, _, al3c, _ = run_ticks(bars, [[zl]] * 4, m1s, tk_all, **J)
    tk_all_early = [[], [((150.25, 150.26, 150.05, 150.23), m1b[:4], 8.99)]]
    _, _, al3d, _ = run_ticks(bars, [[zl]] * 4, m1s, tk_all_early, **J)
    check("SA-10b closedness by time, not by position: the last 1M element counts when its minute has ended (now >= time "
          "+ 1 min) even without a newer element (two variants: element equal to a forming one, and an array of only "
          "closed bars); one tick before its minute ends (now = time + 0.99 min) the same element is still excluded",
          al3b == [("仮", 1, 1), ("確定", 1, 1)] and al3d == [("確定", 1, 1)]
          and al3c == [("仮", 1, 1), ("確定", 1, 1)], str((al3b, al3c, al3d)))
    bt_fail = (150.250, 150.260, 150.050, 150.090)
    m1f = m1b[:4] + [(9, 150.24, 150.08, 150.09)]
    _, _, al4, _ = run_ticks([flat, bt_fail, nxt, nxt], [[zl]] * 4, [m1s[0], m1f, [], []], tk, **J)
    check("SA-11 provisional only: the provisional LONG was sent, but the 5M bar closes back inside the zone (150.09 < "
          "top 150.10) -> no order and no confirmed alert", al4 == [("仮", 1, 1)], str(al4))
    blocked = {}
    _, _, a_, _ = run_ticks(bars, [[zl]] * 4, m1s, tk, tmins=[2 * 60, 2 * 60, 2 * 60, 2 * 60], **J)
    blocked["out of session (02:00)"] = a_
    zs = Z(5, RES, 150.300, 150.200)
    m1s_s = [[(0, 150.12, 150.08, 150.10)], [(5, 150.15, 150.10, 150.12), (6, 150.30, 150.21, 150.28),
                                              (7, 150.27, 150.22, 150.24), (8, 150.20, 150.16, 150.17), (9, 150.19, 150.14, 150.15)], [], []]
    tks = [[], [((150.12, 150.30, 150.10, 150.17), m1s_s[1][:4] + [(9, 150.19, 150.16, 150.17)])]]
    _, _, a_, _ = run_ticks([(150.10, 150.12, 150.08, 150.10), (150.12, 150.30, 150.10, 150.15), nxt, nxt], [[zs]] * 4,
                            m1s_s, tks, **J)
    blocked["Short setup with Long Only"] = a_
    _, _, a_short, _ = run_ticks([(150.10, 150.12, 150.08, 150.10), (150.12, 150.30, 150.10, 150.15), nxt, nxt], [[zs]] * 4,
                                 m1s_s, tks, **dict(J, dir="Both"))
    zl2 = Z(2, SUP, 150.110, 150.020)
    tk_hold = [[], [], [], [((150.15, 150.16, 150.05, 150.12), m1b[:4] + [(9, 150.24, 150.13, 150.15)])]]
    _, _, a_, _ = run_ticks([flat, bt, nxt, (150.15, 150.16, 150.05, 150.12)], [[zl, zl2]] * 4, [m1s[0], m1b, [], []],
                            tk_hold, **J)
    blocked["position held"] = [x for x in a_ if x[1] == 3]
    check("SA-12 provisional follows the entry limits: none outside the session (decision close 02:00), none for a Short "
          "setup under Long Only (the same setup with Both gives provisional + confirmed SHORT), none while a position "
          "is held", all(v == [] for v in blocked.values()) and a_short == [("仮", 1, -1), ("確定", 1, -1)],
          str((blocked, a_short)))
    # consistency: with all 1M bars of the bar closed, the provisional decision equals the confirmed one (B and D)
    bad = []
    for mode in ("B", "D"):
        S, B = t3.run3(bars[:1], [[zl]], m1s=m1s[:1], **dict(J, mode=mode))
        side, _, _ = prov_eval(S, bt, m1b, flat, now=10.0)
        S2, _ = t3.run3(bars[:2], [[zl]] * 2, m1s=m1s[:2], **dict(J, mode=mode))
        conf_side = t3.orders(S2)[0][1]["side"] if t3.orders(S2) else 0
        if side != conf_side or side == 0:
            bad.append((mode, side, conf_side))
    check("SA-13 consistency: when every 1M bar of the 5M bar has closed and the zone is unchanged by the update, the "
          "provisional decision equals the confirmed decision (B, D)", bad == [], str(bad))
    # ---- D wait carried over from an earlier 5M bar ------------------------------------------------------------------
    t1 = [(150.26, 150.20, 150.22), (150.21, 150.05, 150.08), (150.12, 150.06, 150.11), (150.14, 150.07, 150.12),
          (150.15, 150.08, 150.12)]
    t2 = [(150.16, 150.10, 150.15), (150.18, 150.12, 150.16), (150.24, 150.15, 150.23), (150.25, 150.20, 150.24),
          (150.26, 150.21, 150.25)]
    mk = lambda b0, lst: [(b0 * 5 + j, h, l, c) for j, (h, l, c) in enumerate(lst)]
    m1c = [m1s[0], mk(1, t1), mk(2, t2), []]
    barsC = [flat, (150.25, 150.26, 150.05, 150.12), (150.15, 150.26, 150.10, 150.25), nxt]
    tkC = [[], [], [((150.15, 150.18, 150.10, 150.17), mk(2, t2[:2]) + [(12, 150.18, 150.15, 150.17)]),
                    ((150.15, 150.24, 150.10, 150.23), mk(2, t2[:3]) + [(13, 150.24, 150.21, 150.23)]),
                    ((150.15, 150.25, 150.10, 150.24), mk(2, t2[:4]) + [(14, 150.25, 150.22, 150.24)])]]
    import copy
    S0, _ = t3.run3(barsC[:2], [[zl]] * 2, m1s=m1c[:2], **J)
    waits_before = copy.deepcopy(S0.waits)
    Sx, Bx, alC, mutC = run_ticks(barsC, [[zl]] * 4, m1c, tkC, **J)
    Sn, Bn = t3.run3(barsC, [[zl]] * 4, m1s=m1c, **J)
    check("SA-14 D wait carried over: touch in bar 1 (no BOS there, the wait is saved at the bar-1 close: level 150.21, "
          "count 3); in bar 2 the closed 1M close 150.23 is the BOS -> one provisional on the forming bar 2, then the "
          "confirmed LONG at the bar-2 close; the saved wait is never modified by the provisional ticks and the orders "
          "equal the run without ticks",
          len(waits_before) == 1 and waits_before[0]["lvl"] == 150.21 and waits_before[0]["cnt"] == 3
          and alC == [("仮", 2, 1), ("確定", 2, 1)] and not mutC and t3.orders(Sx) == t3.orders(Sn)
          and Bx.fills == Bn.fills, str((waits_before, alC, mutC)))
    res = []
    for wait in (6, 5):
        Jw = dict(J, dwait=wait)
        _, _, alW, mutW = run_ticks(barsC, [[zl]] * 4, m1c, tkC, **Jw)
        res.append((wait, alW, mutW))
    check("SA-15 carried wait at the expiry limit: the BOS is the 6th confirmed 1M bar after the touch -> with D wait 6 the "
          "provisional and the confirmed alert come; with D wait 5 the wait expires first -> neither (provisional and "
          "confirmed agree); no state change by the provisional evaluation",
          res[0][1] == [("仮", 2, 1), ("確定", 2, 1)] and res[1][1] == [] and not res[0][2] and not res[1][2], str(res))


def state_writes(src):
    """top-level blocks that write persistent state (var / varip := / +=, var array / map mutation, UDT field :=) or
    send orders. Returns {header: (writes, mutated, field_writes, orders)} and the var / varip names."""
    lines = src.split("\n")
    code = [l if not l.lstrip().startswith("//") else "" for l in lines]
    allc = "\n".join(code)
    vars_ = set(re.findall(r"^\s*var(?:ip)?\s+(?:[\w.]+(?:<[^>]*>)?\s+)?(\w+)\s*=", allc, re.M))
    varip = set(re.findall(r"^\s*varip\s+(?:[\w.]+(?:<[^>]*>)?\s+)?(\w+)\s*=", allc, re.M))
    blocks, cur = [], None
    for l in code:
        if l and not l.startswith(" "):
            cur = [l, []]
            blocks.append(cur)
        elif cur:
            cur[1].append(l)
    out = {}
    for h, body in blocks:
        txt = "\n".join(body)
        w = set(re.findall(r"\b(\w+)\s*(?::=|\+=)", txt)) & vars_
        mv = set(re.findall(r"(?:array\.(?:set|push|remove|clear|insert|shift|pop|unshift)|map\.put)\(\s*(\w+)", txt)) & vars_
        fw = len(re.findall(r"\b\w+\.\w+\s*:=", txt))
        o = len(re.findall(r"strategy\.(?:entry|exit|close|cancel|order)\(", txt))
        if w or mv or fw or o:
            out[h] = (w, mv, fw, o, txt)
    return out, vars_, varip


def gate_tick_separation():
    sw, vars_, varip = state_writes(STJ)
    heads = sorted(h[:40] for h in sw)
    exp = sorted(["f_nraAccumBoxState(simple int rangeLen, ", "f_nraAccumPack(simple bool usePorted, si",
                  "f_fvgExpire(int nowClose) =>", "f_fvgOnEvent(int tfIdx, int key, int clo", "if is5mChart",
                  "if is5mChart and barstate.isconfirmed", "if stAlertProv and is5mChart and not bar"])
    co = code_only(STJ)
    # NR-A1: f_nraAccumBoxState <- f_nraAccumPack <- f_nraAccumConfirmed <- only inside request.security (HTF context)
    cl = co.split("\n")
    calls = lambda f: [l.strip() for l in cl if re.search(r"\b" + f + r"\(", l) and not l.startswith(f + "(")]
    nra_ok = calls("f_nraAccumBoxState") == ["[pSid, pTop, pBot] = f_nraAccumBoxState(rangeLen, baseLen, atrLen, minUpper, minLower, maxRun, atrMult, barRatioMax, driftMax)"] \
        and len(calls("f_nraAccumPack")) == 1 and calls("f_nraAccumPack")[0].startswith("[_u, _l, _i] = f_nraAccumPack(") \
        and all("request.security(" in l for l in calls("f_nraAccumConfirmed"))
    nra_calls = calls("f_nraAccumConfirmed")
    fvg_calls = [l for l in co.split("\n") if re.search(r"\bf_fvg(?:Expire|OnEvent)\(", l) and "=>" not in l]
    fvg_blk = sw.get("if is5mChart", (set(), set(), 0, 0, ""))[4]
    fvg_writes_ok = all(l.startswith("        ") for l in fvg_blk.split("\n") if re.search(r"gFvgNextExpire\s*:=", l)) \
        and "    if barstate.isconfirmed\n        int nowClose = time_close" in fvg_blk
    prov = next((v for h, v in sw.items() if h.startswith("if stAlertProv")), None)
    main = sw.get("if is5mChart and barstate.isconfirmed")
    check("SA-16 tick separation in code: every top-level block that writes persistent state or sends orders is (a) the "
          "confirmed-5M order block (all orders, candidates, BOS waits, processed 1M time, Track use), (b) the FVG block "
          "whose writes sit under `if barstate.isconfirmed`, (c) FVG storage functions called only there, (d) NR-A1 "
          "Accum functions evaluated inside request.security (own HTF context), or (e) the provisional block, which writes "
          "only the varip stProvBar; zn.update (Engine state) runs only under `is5mChart and barstate.isconfirmed`; "
          "the only varip is stProvBar",
          heads == exp and varip == {"stProvBar"} and prov is not None and prov[0] == {"stProvBar"} and prov[1] == set()
          and prov[2] == 0 and prov[3] == 0 and main is not None and main[3] == 11 and fvg_writes_ok
          and nra_ok and len(nra_calls) >= 1
          and len(fvg_calls) == 4 and all(l.startswith("            gFvgNextExpire :=") or l.startswith("        gFvgNextExpire :=")
                                          for l in fvg_calls)
          and co.count("if is5mChart and barstate.isconfirmed\n    zoneCountNow := zn.update(") == 1,
          str((heads, varip, nra_calls)))
    # exact difference to the version before the alerts (feb64b7)
    old = subprocess.run(["git", "-C", ROOT, "show", "feb64b7:" + sj.STJ_PATH], capture_output=True, text=True).stdout
    v1 = sj.EDITS[:5]
    o = old
    for a, b in reversed(v1):
        if b:
            o = o.replace(b, a)
        else:
            anchor = 'f_num(float v, string fmt) =>\n    na(v) ? "-" : str.tostring(v, fmt)\n'
            o = o.replace(anchor, anchor + a)
    alert_names = ["stAlertProv", "stAlertConf", "stProvBar", "stTpUpPrev", "stTpDnPrev", "f_stProvEval", "f_stAlertMsg"]
    mtxt = main[4] if main else ""
    refs = [l.strip() for l in mtxt.split("\n") if any(re.search(r"\b" + n + r"\b", l) for n in alert_names)]
    check("SA-17 against the version before the alerts (feb64b7): stripping the old STJ-1 edits and the current edits gives "
          "the same ZONE-JPY -> ST-3 pipeline text, so the only changes are the STJ-2 edits (header, calc_on_every_tick, "
          "zn.update gate, defaults, alert inputs / functions / confirmed alert / saved TP edges / provisional block); "
          "inside the confirmed order block the alert names appear only on the alert call and the TP-edge save lines "
          "(no order condition reads them)",
          bool(old) and o == sj.pipeline() and sj.strip_stj(STJ) == sj.pipeline()
          and refs == ["if stAlertConf", 'alert(f_stAlertMsg("確定", side, stModeA ? oL : close, oSL), alert.freq_all)',
                       "stTpUpPrev := tpUp", "stTpDnPrev := tpDn"], str(refs))
    fn = tb.func(STJ, "f_stProvEval(")
    check("SA-18 provisional 1M closedness in Pine: an element is used when a newer one follows or its minute has ended "
          "(time + 60000 <= timenow); the existing time array is reused (no new request)",
          "            if array.get(m1t, sz - 1) + 60000 > timenow\n                nb := sz - 1\n" in fn
          and "nb := sz\n" in fn and "array.size(m1t) - 1" not in fn
          and STJ.count('request.security_lower_tf(syminfo.tickerid, "1", [time, high, low, close])') == 1)


def main():
    for g in (gate_static, gate_zone_parity, gate_orders_yen, gate_alert_static, gate_alert_model, gate_tick_separation):
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
