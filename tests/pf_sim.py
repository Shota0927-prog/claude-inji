"""XA-24 fixtures — run-time reduction of the Gold Strategies (ZoneEnginePracticalXAUUSD library version 3 + the Strategy FVG
selection), tests/xa_build.py ENGINE_EDITS7 / STRATEGY_EDITS24, tests/xal_build.py, tests/au_build.py.

  PS : static — exact build / strip of the Engine (-> version 2 of 0c6cd71), the Short / Long (-> 7705907) and the automation
       copy; every other Pine file unchanged; inputs / strategy() settings unchanged; import /2 -> /3 in the three Strategies;
       f_finalizeCluster compares no strings; f_findTrack binary-searches the sorted Track centers (no full Track scan); the
       Track uid copy is conditional; f_fvcZoneDisplay / f_zpoBestFvg unchanged and selecting with the same code; the Python
       port (tests/pf_model.py) mirrors the Pine code tables (source codes, mask sums)
  PM : models — version 2 and version 3 ports bar by bar on SYNTHETIC Gold feeds (Short and Long defaults, >= 7875 bars and
       longer, high volatility, configuration variants): every Zone (bounds, scores, strength, state, flip, track id, members,
       masks, RN), every Track (id, state, break / retest / flip / touch fields, uids, order), the events and the Raw Zones are
       equal; random fuzz of the Track search (ties, matched Tracks, continuity) and of f_finalizeCluster (all source kinds,
       odd timeframe settings, Day/Swing merge, accum modes); the Strategy FVG selection old (two passes) = new (one pass);
       the work counts fall (Track search iterations, uid copies, string compares)
  PU : mutations — model mutations of the version 3 rules are caught by the fuzz; source mutations do not strip back

Evidence class: PINE_NOT_VERIFIED (TradingView compile, run time, Strategy Tester results and the published library number are
not verified here; the feeds are synthetic, not XAUUSD data).
"""
import os
import random
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xa_build as xb            # noqa: E402
import xal_build as xl           # noqa: E402
import au_build as ab            # noqa: E402
import pf_model as pm            # noqa: E402

ROOT = xb.ROOT
PREV = "7705907"                 # XA-23 (Strategies); the Engine of 0c6cd71 (version 2) is unchanged since
ENG_PREV = "0c6cd71"
AU_PREV = "dcbb1a2"              # the automation copy before XA-24 (AU-5; it did not exist at 7705907)
raw = lambda p: open(os.path.join(ROOT, p), encoding="utf-8").read()
E, S, L, A = raw(xb.ENG_PATH), raw(xb.STR_PATH), raw(xl.LONG_PATH), raw(ab.AUTO_PATH)
E0 = xb.show(ENG_PREV, xb.ENG_PATH)
S0, L0, A0 = xb.show(PREV, xb.STR_PATH), xb.show(PREV, xl.LONG_PATH), xb.show(AU_PREV, ab.AUTO_PATH)
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


def func(t, name):
    """the text of a top-level Pine function (from its header to the next top-level line)."""
    i = t.index("\n" + name + "(") + 1
    m = re.search(r"\n(?=[^ \n])", t[i + 1:])
    return t[i:i + 1 + m.start()] if m else t[i:]


def title(t):
    """the automation copy's title line names the Short layer it copies (XA-24 now, XA-23 before)."""
    return None if t is None else t.replace("(ZoneStrategyXAU.pine XA-24) の自動化用コピー", "(ZoneStrategyXAU.pine XA-23) の自動化用コピー")


def inputs(t):
    return [ln for ln in t.splitlines() if re.match(r"^\w+\s*=\s*input\.", ln)]


# ---- static ------------------------------------------------------------------------------------------------------------
def gate_static():
    check("PS-01 Engine == xa_build.build_engine() (version 3) and strip_engine7() gives the version 2 Engine of %s byte for byte; "
          "strip_engine6() still gives version 1" % ENG_PREV,
          E == xb.build_engine() and xb.strip_engine7(E) == E0 and xb.strip_engine6(E) == xb.build_engine1())
    check("PS-02 Short == xa_build.build_strategy(), Long == xal_build.build(), automation copy == au_build.build(); strip_strategy24 / "
          "strip24 / au strip + strip_strategy24 give the files of %s (the copy: of %s) byte for byte" % (PREV, AU_PREV),
          S == xb.build_strategy() and L == xl.build() and A == ab.build() and xb.strip_strategy24(S) == S0
          and xl.strip24(L) == L0 and ab.strip(A) == S and title(xb.unapply24(ab.AUTO_PATH, A)) == A0)
    others = [p for p in os.popen(f"git -C {ROOT} ls-files '*.pine'").read().split()
              if p not in (xb.ENG_PATH, xb.STR_PATH, xl.LONG_PATH, ab.AUTO_PATH)]
    changed = [p for p in others if __import__("btl_build").unapply(p, raw(p)) != xb.show(PREV, p)]
    check("PS-03 every other Pine file (Visual, other Engines / Strategies) unchanged vs %s (BTL-1 reverted exactly)" % PREV,
          not changed, str(changed))
    check("PS-04 inputs and strategy() settings unchanged on the Short / Long / automation copy (same input lines; calc_on_every_tick "
          "stays true); Max Persistent Raw Zones 200, Zone State Retention 500, lifetimes kept",
          inputs(S) == inputs(S0) and inputs(L) == inputs(L0) and inputs(A) == inputs(A0)
          and S.split("strategy(", 1)[1].split(")\n", 1)[0] == S0.split("strategy(", 1)[1].split(")\n", 1)[0]
          and "calc_on_every_tick     = true" in S and 'maxPersistZones = input.int(200,' in S and 'trackStaleBars = input.int(500,' in L)
    imp = [re.findall(r"^import .*$", t, re.M) for t in (S, L, A)]
    check("PS-05 the three Strategies import ZoneEnginePracticalXAUUSD/3 (the only import; /2 is not assumed to update itself)",
          imp == [[xb.IMPORT_XAE3.strip()]] * 3, str(imp))
    fin = re.sub(r"//.*", "", func(E, "f_finalizeCluster"))     # code only
    check("PS-06 f_finalizeCluster: no string compare (srcId / srcCat / srcTf), no f_setBit in the member loop (the mask is summed "
          "once after it), no Day H/L pre-scan; the Day H/L price comes from f_buildClusters (dH0 / dL0)",
          not re.search(r"\.(srcId|srcCat|srcTf)\b", fin) and fin.count("f_setBit") == 1 and "for j = 0 to n - 1" in fin
          and fin.count("for j = ") == 1 and "dsOn ? dH0 : na" in fin
          and func(E, "f_buildClusters").count("f_finalizeCluster(cur, c, minB, maxT, cDH, cDL)") == 2)
    ft = func(E, "f_findTrack")
    upd = func(E, "export update")
    check("PS-07 f_findTrack binary-searches the sorted centers (while lo < hi, break past +clusterDist) and never loops over all "
          "Tracks; update() sorts the Track centers once per bar before the Zone loop; the uid copy is conditional (f_sameUids)",
          "while lo < hi" in ft and "break" in ft and "array.size(e.tracks)" not in ft and "d < bestD or (d == bestD and i < best)" in ft
          and upd.count("array.sort_indices(trkC, order.ascending)") == 1
          and upd.index("trkOrd := array.sort_indices") < upd.index("int ti = f_findTrack(")
          and "if not f_sameUids(t.memberUids, z.memberUids)\n                t.memberUids := array.copy(z.memberUids)" in upd)
    # the Python port mirrors the Pine source codes and the mask sums
    kind = func(E, "f_kind")
    cat = dict((v, int(k)) for v, k in re.findall(r"z\.srcCat == (CAT_\w+) \? (\d)", kind))
    ids = dict((v, int(k)) for v, k in re.findall(r'z\.srcId == "(\w+)" \? (\d)', kind))
    const = dict(re.findall(r'^string (CAT_\w+) *= "(\w+)"', E, re.M))
    src_sum = re.findall(r"\(b\w+ \? (SRC_\w+) : 0\)", fin)
    htf_sum = re.findall(r"\(h\w+ \? (HTF_\w+) : 0\)", fin)
    check("PS-08 the port's source codes (K_CAT / K_ID) and mask terms are the Pine f_kind / f_finalizeCluster ones",
          {const[k]: v for k, v in cat.items()} == pm.K_CAT and ids == pm.K_ID
          and sorted(src_sum) == sorted(["SRC_SW1", "SRC_SW2", "SRC_SW3", "SRC_HZX", "SRC_ACC1", "SRC_ACC2", "SRC_ACC3", "SRC_MA1", "SRC_MA2", "SRC_DHL"])
          and sorted(htf_sum) == sorted(["HTF_SW1H", "HTF_ACC1", "HTF_ACC2", "HTF_ACC3", "HTF_SW15", "HTF_MA1", "HTF_MA2", "HTF_DAY"]),
          f"{cat} {ids} {src_sum} {htf_sum}")
    for nm, t, t0 in (("Short", S, S0), ("Long", L, L0)):
        same = func(t, "f_fvcZoneDisplay") == func(t0, "f_fvcZoneDisplay") and func(t, "f_zpoBestFvg") == func(t0, "f_zpoBestFvg")
        sel = lambda f: f.split("    for s = 0", 1)[1].split("    float dScore", 1)[0].split("    best\n", 1)[0]
        ev = func(t, "f_stZoneEval")
        check(f"PS-09 {nm}: f_fvcZoneDisplay / f_zpoBestFvg unchanged and select with the same loop text; f_stZoneEval calls only "
              "f_zpoBestFvg and computes dScore / dStr with the f_fvcZoneDisplay expression; the rest of f_stZoneEval unchanged",
              same and sel(func(t, "f_fvcZoneDisplay")) == sel(func(t, "f_zpoBestFvg")) and "f_fvcZoneDisplay" not in ev
              and ev.count("f_zpoBestFvg(z)") == 1
              and "        dScore := z.baseSum + f_fvcBase(best) + z.slopeBonus + z.maBonus + z.flipBonus + f_fvcConf(z.catCount + 1)\n"
                  "        dStr   := f_fvcStrengthOf(dScore, z.hasHtf)\n" in ev and "        dScore := z.baseSum + f_fvcBase(best) + z.slopeBonus + z.maBonus + z.flipBonus + f_fvcConf(z.catCount + 1)\n" in func(t, "f_fvcZoneDisplay")
              and ev.split("    bool boosted", 1)[1] == func(t0, "f_stZoneEval").split("    bool boosted", 1)[1])
    names = [n for n, _, _ in xb.STRATEGY_EDITS24]
    fvg_old, fvg_new = xb.STRATEGY_EDITS24[2][1], xb.STRATEGY_EDITS24[2][2]
    ev0 = func(S0, "f_stZoneEval")
    check("PS-10 the Strategy layer touches only the header lines, the import and f_stZoneEval (with its comment lines): reverting it "
          "gives the Short / Long / automation copy back (the copy's title names XA-24); trading, alerts, labels, SATS, size, orders, "
          "breakeven and JSON lines unchanged",
          names == ["header", "import", "fvg"] and fvg_old.split("\n", 1)[1] in S0 and ev0.startswith(fvg_old.split("\n", 1)[1])
          and fvg_new.endswith("        dStr   := f_fvcStrengthOf(dScore, z.hasHtf)\n")
          and xb.unapply24(xb.STR_PATH, S) == S0 and xb.unapply24(xl.LONG_PATH, L) == L0 and title(xb.unapply24(ab.AUTO_PATH, A)) == A0)


# ---- models ------------------------------------------------------------------------------------------------------------
def same_run(c, F):
    e2, e3 = pm.Engine(c), pm.EngineV3(c)
    tot2, tot3 = {}, {}
    for bar, f in F:
        e2.update(bar, f)
        e3.update(bar, f)
        if e2.snap() != e3.snap():
            return bar.i, tot2, tot3, e2
        for k, v in e2.n.items():
            tot2[k] = tot2.get(k, 0) + v
        for k, v in e3.n.items():
            tot3[k] = tot3.get(k, 0) + v
    return None, tot2, tot3, e2


STATS = {}


def gate_model():
    runs = [("Short defaults, 8200 bars (incl. bar 7875)", pm.Cfg(), 1, 42, 0.8),
            ("Long defaults (Strong 9), 8200 bars", pm.Cfg(thrStrong=9.0), 2, 42, 0.8),
            ("Short defaults, high volatility, 6000 bars", pm.Cfg(), 3, 30, 1.6),
            ("Long defaults, calm, 6000 bars", pm.Cfg(thrStrong=9.0), 4, 30, 0.45)]
    for nm, c, seed, days, vol in runs:
        F = pm.build_feed(pm.market1m(seed, days, vol=vol), c)
        F = F[:8200] if "8200" in nm else F[:6000]
        bad, t2, t3, e2 = same_run(c, F)
        STATS[nm] = (len(F), t2, t3, len(e2.tracks), len(e2.live), len(e2.persist))
        check(f"PM-01 {nm}: version 2 and version 3 equal on every bar (Zones / Tracks / events / Raw Zones; synthetic feed, "
              f"{len(F)} bars, last: {len(e2.persist)} Raw Zones, {len(e2.live)} Zones, {len(e2.tracks)} Tracks)",
              bad is None and len(F) >= 6000, f"first difference at bar {bad}")
    VARS = [dict(roleOnBreak=True), dict(dsMerge=False), dict(dsDist=3.0), dict(accScoreMax=True, accEdgeOnce=True),
            dict(hzTf1="60", hzTf2="60", accTf2="60", accTf3="60"), dict(hzTf3="5", accTf1="15"),
            dict(slopeBonusMax=False, maClusterBonus=1.0, maClusterDirBonus=1.0), dict(clusterDist=2.0), dict(clusterDist=12.0),
            dict(trackContinuity=0.01), dict(trackContinuity=1.0), dict(carryPrevDayHL=True), dict(useRnSource=False),
            dict(maxPersistZones=20), dict(trackStaleBars=10), dict(htfSwing15M=True, htfMa1=True, htfMa2=True, htfDayHL=True),
            dict(useMaSource=False, useDayHL=False), dict(useHzSource=False), dict(zoneHalfWidth=0.5, resetOnReclaim=False)]
    bad = []
    for vi, kw in enumerate(VARS):
        c = pm.Cfg(**kw)
        F = pm.build_feed(pm.market1m(100 + vi, 8, vol=0.9), c)[:1500]
        if same_run(c, F)[0] is not None:
            bad.append(kw)
    c = pm.Cfg(clusterDist=-1.0)          # nothing ever merges / matches: every Zone makes a new Track
    F = pm.build_feed(pm.market1m(7, 3, vol=0.8), c)[:300]
    if same_run(c, F)[0] is not None:
        bad.append("clusterDist -1")
    c = pm.Cfg()
    F = pm.build_feed(pm.market1m(8, 6, vol=0.8), c)[:1100]
    e2, e3 = pm.Engine(c), pm.EngineV3(c)
    for bar, f in F:                      # configured timeframes changed during the run: version 3 rebuilds its codes
        if bar.i == 500:
            c.hzTf1, c.accTf2 = "15", "5"
        if bar.i == 800:
            c.hzTf1, c.accTf2 = "5", "240"
        e2.update(bar, f)
        e3.update(bar, f)
        if e2.snap() != e3.snap():
            bad.append("timeframe change")
            break
    check("PM-02 %d configuration variants (Role Reversal, Day/Swing Separate / distance 3, Accum Max / Once, equal / swapped "
          "timeframes, slope Sum + MA cluster bonus, cluster 2 / 12 / -1, continuity 0.01 / 1, carried Prev Day H/L, RN OFF, cap 20, "
          "retention 10, all HTF flags, sources OFF, half width 0.5) and a timeframe change during the run: equal on every bar"
          % (len(VARS) + 2), not bad, str(bad))
    check("PM-03 fuzz: the version 3 Track search (sorted centers + binary search + (distance, index) choice) returns the version 2 "
          "full-scan Track on 30000 random states (grid centers -> many distance ties, matched Tracks, random uid sets)",
          fuzz_track(30000) == 0)
    check("PM-04 fuzz: version 3 f_finalizeCluster (codes, mask sums, Day H/L from the running aggregate) == version 2 on 20000 "
          "random clusters (every source kind, unknown ids / timeframes, equal timeframe settings, Day/Swing merge distances, "
          "accum Sum / Max / Once, HTF flags, RN)", fuzz_finalize(20000) == 0)
    check("PM-05 fuzz: the Strategy FVG evaluation with one selection (XA-24 f_stZoneEval) == the two-pass version (f_fvcZoneDisplay + "
          "f_zpoBestFvg) on 20000 random Zones / FVG slot states (direction match ON / OFF, base / close-time ties)",
          fuzz_fvg(20000) == 0)
    n, t2, t3 = STATS["Short defaults, 8200 bars (incl. bar 7875)"][:3]
    check("PM-06 work counts (Short defaults, %d bars): Track search iterations %d -> %d, uid copies %d -> %d, Day H/L pre-scan "
          "iterations %d -> 0; Zones built / finalize member iterations unchanged (%d / %d): every per-bar update still runs"
          % (n, t2["it_findTrack"], t3["it_findTrack"], t2["alloc_copy"], t3["alloc_copy"], t2.get("it_finalize_ds", 0),
             t2["call_finalize"], t2["it_finalize"]),
          t3["it_findTrack"] * 3 < t2["it_findTrack"] and t3["alloc_copy"] * 10 < t2["alloc_copy"] and t3.get("it_finalize_ds", 0) == 0
          and t3["call_finalize"] == t2["call_finalize"] and t3["it_finalize"] == t2["it_finalize"])


def rnd_track_state(r):
    n = r.randint(0, 40)
    tr = []
    for i in range(n):
        uids = r.sample(range(1, 12), r.randint(1, 5))
        tr.append(pm.Track(id=i + 1, center=2600.0 + r.randint(-20, 20) * 0.5, memberUids=uids,
                           matchedBar=r.choice((None, 5, 7, 7))))
    z = pm.Zone(center=2600.0 + r.randint(-20, 20) * 0.5 + r.choice((0.0, 0.0, 0.25, 1e-9)),
                memberUids=r.sample(range(1, 12), r.randint(1, 5)))
    c = pm.Cfg(clusterDist=r.choice((0.0, 0.5, 2.0, 5.0, 10.0)), trackContinuity=r.choice((0.01, 0.34, 0.5, 1.0)))
    return tr, z, c


def find_both(tr, z, c, mut=None):
    e2, e3 = pm.Engine(c), pm.EngineV3(c)
    e2.b = e3.b = pm.Bar(7, 0, 0, 0, 0, 0)
    e2.tracks = e3.tracks = tr
    e3.tC = [t.center for t in tr]
    e3.tOrd = sorted(range(len(tr)), key=lambda i: e3.tC[i])
    if mut == "tie":
        e3.tOrd = sorted(range(len(tr)), key=lambda i: (e3.tC[i], -i))
        return e2.f_findTrack(z), MutV3.find_tie_last(e3, z)
    if mut == "bound":
        return e2.f_findTrack(z), MutV3.find_bound(e3, z)
    return e2.f_findTrack(z), e3.f_findTrack(z)


class MutV3:
    @staticmethod
    def find_tie_last(e, z):        # mutation: a later index wins a distance tie
        best, bestD = -1, 1e20
        for k in range(len(e.tOrd)):
            i = e.tOrd[k]
            t = e.tracks[i]
            if (t.matchedBar is None or t.matchedBar != e.b.i):
                d = abs(t.center - z.center)
                if d <= e.c.clusterDist and (d < bestD or (d == bestD and i > best)) and e.f_trackContinuous(t, z):
                    best, bestD = i, d
        return best

    @staticmethod
    def find_bound(e, z):           # mutation: the window starts one place too late
        D = e.c.clusterDist
        lo, hi = 0, len(e.tOrd)
        while lo < hi:
            mid = (lo + hi) // 2
            if e.tC[e.tOrd[mid]] - z.center <= -D:
                lo = mid + 1
            else:
                hi = mid
        best, bestD = -1, 1e20
        k = lo
        while k < len(e.tOrd) and e.tC[e.tOrd[k]] - z.center <= D:
            i = e.tOrd[k]
            t = e.tracks[i]
            if t.matchedBar is None or t.matchedBar != e.b.i:
                d = abs(t.center - z.center)
                if d <= D and (d < bestD or (d == bestD and i < best)) and e.f_trackContinuous(t, z):
                    best, bestD = i, d
            k += 1
        return best


def fuzz_track(n, mut=None, seed=1):
    r = random.Random(seed)
    bad = 0
    for _ in range(n):
        tr, z, c = rnd_track_state(r)
        a, b = find_both(tr, z, c, mut)
        bad += a != b
    return bad


IDS = [("SWING_H", pm.CAT_HZ), ("SWING_L", pm.CAT_HZ), ("PDH", pm.CAT_HZ), ("PDL", pm.CAT_HZ), ("ACC_HI", pm.CAT_ACC),
       ("ACC_LO", pm.CAT_ACC), ("MA1", pm.CAT_MA), ("MA2", pm.CAT_MA), ("DAY_HIGH", pm.CAT_DHL), ("DAY_LOW", pm.CAT_DHL),
       ("SWING_H", "Other"), ("XYZ", pm.CAT_HZ), ("ACC_HI", pm.CAT_HZ), ("MA1", pm.CAT_DHL)]
TFS = ["5", "15", "60", "240", "D", "PD", "1", "3"]


def rnd_cluster(r):
    c = pm.Cfg(hzTf1=r.choice(TFS[:4]), hzTf2=r.choice(TFS[:4]), hzTf3=r.choice(TFS[:4]), accTf1=r.choice(TFS[1:5]),
               accTf2=r.choice(TFS[1:5]), accTf3=r.choice(TFS[1:5]), dsMerge=r.random() < 0.7,
               dsDist=r.choice((0.0, 0.0, 0.5, 3.0)), accScoreMax=r.random() < 0.3, accEdgeOnce=r.random() < 0.3,
               slopeBonusMax=r.random() < 0.5, htfSwing1H=r.random() < 0.7, htfSwing15M=r.random() < 0.3,
               htfAccum1H=r.random() < 0.7, htfAccum4H=r.random() < 0.7, htfAccumD=r.random() < 0.7, htfMa1=r.random() < 0.3,
               htfMa2=r.random() < 0.3, htfDayHL=r.random() < 0.3, useRnSource=r.random() < 0.6,
               scoreHz1=r.choice((1.0, 2.0, 3.0)), scoreHz2=r.choice((1.0, 2.0, 3.0)), scoreHz3=r.choice((2.0, 3.0, 5.0)))
    base = 2600.0 + r.randint(0, 400) * 0.25
    mem = []
    for k in range(r.randint(1, 12)):
        sid, cat = r.choice(IDS)
        px = base + r.randint(-8, 8) * 0.5
        z = pm.Raw(uid=k + 1, srcId=sid, srcCat=cat, srcTf=r.choice(TFS), center=px, top=px + 6.0, bottom=px - 6.0,
                   baseScore=r.choice((1.0, 2.0, 3.0, 4.0, 5.0)), slopeBonus=r.choice((0.0, 1.0, 2.0)),
                   maClusterBonus=r.choice((0.0, 1.0)), px0=px if r.random() < 0.9 else px + 0.5,
                   px1=px + r.choice((0.0, 0.0, 0.5, -3.0)))
        mem.append(z)
    return c, mem


def fin_both(c, mem):
    e2, e3 = pm.Engine(c), pm.EngineV3(c)
    zBot, zTop = min(m.bottom for m in mem), max(m.top for m in mem)
    a = e2.f_finalizeCluster(mem, zBot, zTop)
    cDH = cDL = pm.NA
    for m in mem:
        e3.f_kind(m)
        if m.kind[1] == 6:
            cDH = m.px0
        elif m.kind[1] == 7:
            cDL = m.px0
    b = e3.f_finalizeCluster(mem, zBot, zTop, cDH, cDL)
    return a.snap(), b.snap()


def fuzz_finalize(n, seed=2, mut=None):
    r = random.Random(seed)
    bad = 0
    for _ in range(n):
        c, mem = rnd_cluster(r)
        if mut == "first_dh":       # mutation: the first DAY_HIGH instead of the last (needs two in the cluster)
            mem = mem + [pm.Raw(uid=90, srcId="DAY_HIGH", srcCat=pm.CAT_DHL, srcTf="D", center=mem[0].center, top=mem[0].top,
                                bottom=mem[0].bottom, baseScore=3.0, px0=mem[0].center + 1.0, px1=pm.NA),
                         pm.Raw(uid=91, srcId="DAY_HIGH", srcCat=pm.CAT_DHL, srcTf="D", center=mem[0].center, top=mem[0].top,
                                bottom=mem[0].bottom, baseScore=3.0, px0=mem[0].center, px1=pm.NA)]
        a, b = fin_both(c, mem)
        if mut == "first_dh":
            e3 = pm.EngineV3(c)
            for m in mem:
                e3.f_kind(m)
            dh = [m.px0 for m in mem if m.kind[1] == 6]
            dl = [m.px0 for m in mem if m.kind[1] == 7]
            b = e3.f_finalizeCluster(mem, min(m.bottom for m in mem), max(m.top for m in mem), dh[0] if dh else pm.NA,
                                     dl[0] if dl else pm.NA).snap()
        if mut == "hz3_slot":       # mutation: the HTF Swing 1H bit from the first-match slot (sl == 3) instead of srcTf == hzTf3
            e3 = MutFin(c)
            for m in mem:
                e3.f_kind(m)
            dh = [m.px0 for m in mem if m.kind[1] == 6]
            dl = [m.px0 for m in mem if m.kind[1] == 7]
            b = e3.f_finalizeCluster(mem, min(m.bottom for m in mem), max(m.top for m in mem), dh[-1] if dh else pm.NA,
                                     dl[-1] if dl else pm.NA).snap()
        bad += a != b
    return bad


class MutFin(pm.EngineV3):
    def f_kind(self, z):
        super().f_kind(z)
        k = list(z.kind)
        if k[2] and k[4]:           # srcTf equal to hzTf1 and hzTf3: the mutated code keeps only the first match
            k[4] = False
        z.kind = tuple(k)


# Strategy FVG evaluation (f_fvcZoneDisplay / f_zpoBestFvg / f_stZoneEval of the Gold Strategies)
SLOTS = 5


def fvg_best(z, slots, dirmatch):
    best = -1
    want = (1 if z["state"] == 1 else -1 if z["state"] == 2 else 0) if dirmatch else 0
    base = lambda s: s // SLOTS + 1.0
    for s in range(3 * SLOTS):
        al, dr, top, bot, ct = slots[s]
        if al and (want == 0 or dr == want):
            if min(z["top"], top) > max(z["bottom"], bot):
                if best < 0:
                    best = s
                elif base(s) > base(best):
                    best = s
                elif base(s) == base(best):
                    if ct > slots[best][4]:
                        best = s
    return best


def conf(cat):
    return 3.0 if cat >= 4 else 2.0 if cat == 3 else 1.0 if cat == 2 else 0.0


def strength(score, htf):
    t = 1 if score < 5.0 else 2 if score < 10.0 else 3 if score < 15.0 else 4
    return 3 if t == 4 and not htf else t


def eval_old(z, slots, dm):
    b = fvg_best(z, slots, dm)          # f_fvcZoneDisplay's own selection
    dScore, dStr = z["score"], z["strength"]
    if b >= 0:
        dScore = z["baseSum"] + (b // SLOTS + 1.0) + z["slopeBonus"] + z["maBonus"] + z["flipBonus"] + conf(z["catCount"] + 1)
        dStr = strength(dScore, z["hasHtf"])
    best = fvg_best(z, slots, dm)       # f_zpoBestFvg
    return tail(z, slots, dScore, dStr, best)


def eval_new(z, slots, dm, mut=None):
    best = fvg_best(z, slots, dm)
    dScore, dStr = z["score"], z["strength"]
    if best >= 0:
        dScore = z["baseSum"] + (best // SLOTS + 1.0) + z["slopeBonus"] + z["maBonus"] + z["flipBonus"] + conf(z["catCount"] + (1 if mut != "conf" else 0))
        dStr = strength(dScore, z["hasHtf"])
    return tail(z, slots, dScore, dStr, best)


def tail(z, slots, dScore, dStr, best):
    boosted = best >= 0 and dStr > z["strength"]
    bT = bB = vT = vB = None
    if boosted:
        bT, bB = min(z["top"], slots[best][2]), max(z["bottom"], slots[best][3])
    if best >= 0:
        vT, vB = min(z["top"], slots[best][2]), max(z["bottom"], slots[best][3])
    return (dScore, dStr, best, boosted, bT, bB, vT, vB)


def fuzz_fvg(n, seed=3, mut=None):
    r = random.Random(seed)
    bad = 0
    for _ in range(n):
        ctr = 2600.0 + r.randint(-10, 10)
        z = dict(top=ctr + r.choice((3.0, 6.0)), bottom=ctr - r.choice((3.0, 6.0)), state=r.choice((0, 1, 2, 3)),
                 baseSum=r.choice((3.0, 6.0, 9.0)), slopeBonus=r.choice((0.0, 1.0)), maBonus=0.0, flipBonus=0.0,
                 catCount=r.randint(1, 4), hasHtf=r.random() < 0.5)
        z["score"] = z["baseSum"] + z["slopeBonus"] + conf(z["catCount"])
        z["strength"] = strength(z["score"], z["hasHtf"])
        slots = [(r.random() < 0.5, r.choice((1, -1)), 2600.0 + r.randint(-12, 12), 0.0, r.choice((1, 2, 3))) for _ in range(3 * SLOTS)]
        slots = [(a, d, t, t - r.choice((1.0, 3.0, 5.0)), ct) for a, d, t, _, ct in slots]
        dm = r.random() < 0.5
        bad += eval_old(z, slots, dm) != eval_new(z, slots, dm, mut)
    return bad


# ---- mutations ---------------------------------------------------------------------------------------------------------
def gate_mutation():
    m = {"tie -> later index": fuzz_track(4000, "tie"), "window start too late": fuzz_track(4000, "bound"),
         "first Day High instead of last": fuzz_finalize(3000, mut="first_dh"),
         "HTF 1H bit from the first-match slot": fuzz_finalize(3000, mut="hz3_slot"), "FVG confluence +0": fuzz_fvg(3000, mut="conf")}
    check("PU-01 model mutations are caught by the fuzz (tie to the later Track, binary-search start one place late, first Day "
          "High of the cluster, HTF 1H Swing bit from the first-match timeframe slot, FVG confluence without the FVG category)",
          all(v > 0 for v in m.values()), str(m))
    fin = func(E, "f_findTrack")
    muts = {"tie": E.replace("(d < bestD or (d == bestD and i < best))", "(d < bestD or (d == bestD and i > best))"),
            "always copy": E.replace("            if not f_sameUids(t.memberUids, z.memberUids)\n                t.memberUids := array.copy(z.memberUids)\n",
                                     "            t.memberUids := array.copy(z.memberUids)\n"),
            "bound": E.replace("        if array.get(tc, array.get(ord, mid)) - z.center < -dist\n", "        if array.get(tc, array.get(ord, mid)) - z.center <= -dist\n"),
            "no refresh": E.replace("                f_kind(array.get(e.persist, i), c)\n", ""),
            "dyn codes": E.replace("    f_kind(rz, c)     // XA-24\n", "")}
    bad = [k for k, t in muts.items() if t == E or xb.strip_engine7(t) == E0]
    smut = {"two passes": S.replace("    int   best   = f_zpoBestFvg(z)\n    float dScore = z.score\n", "    [dScore0, dStr0] = f_fvcZoneDisplay(z)\n    int   best   = f_zpoBestFvg(z)\n    float dScore = z.score\n"),
            "import /2": S.replace(xb.IMPORT_XAE3, xb.IMPORT_XAE2)}
    bad += [k for k, t in smut.items() if t == S or xb.strip_strategy24(t) == S0]
    check("PU-02 source mutations (tie rule, unconditional copy, binary-search bound, no code refresh, no dynamic-slot codes, the "
          "second FVG pass, import /2) do not strip back to the version 2 Engine / the %s Strategy" % PREV, not bad and fin, str(bad))


def main():
    for g in (gate_static, gate_model, gate_mutation):
        try:
            g()
        except Exception:
            import traceback
            check(f"{g.__name__} completed without error", False, traceback.format_exc()[-900:])
    fails = 0
    for nm, ok, d in RESULTS:
        fails += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {nm[:150].ljust(150)}  {'' if ok else d}")
    print(f"\n{len(RESULTS) - fails}/{len(RESULTS)} passed  [PINE_NOT_VERIFIED: exact build / static / Python ports on synthetic feeds]")
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
