"""ZONE-P bonus defaults fixtures — MA Cluster Bonus / Same Slope 1 -> 0, Flip Bonus 2 -> 0 (ZoneVisualPractical.pine).

  BS : static — exactly three input defaults change, everything else (inputs, config assignments, MA slope settings,
       Sum aggregation, import /6, protected blocks, Engines) identical; Engine keeps max(maClusterBonus) and the Flip
       state independent of the Flip Bonus
  BM : scoring — cluster score components with the old and new defaults (none / proximity / same slope / flip / all)
  BY : time-series Engine model (Swing max, RN OFF and ON), old vs new defaults on the same series

Evidence class: PINE_NOT_VERIFIED (exact transform / static / port / model; TradingView compile / display external).
"""
import difflib
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bon_build as bb                # noqa: E402
import nr_s1_build as nb              # noqa: E402
import nr_a1_build as na              # noqa: E402
import fvg_batch_c_build as cb        # noqa: E402
import zp_overlap_build as zp         # noqa: E402
import practical_zone_sim as pz       # noqa: E402

ROOT = bb.ROOT
CUR = open(os.path.join(ROOT, "ZoneVisualPractical.pine"), encoding="utf-8").read()
BASE = bb.git_show(bb.BON_BASE_REV)
LIB6 = open(os.path.join(ROOT, "ZoneEnginePracticalSwingMax.pine"), encoding="utf-8").read()
RESULTS = []
REPORT = {}


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


def code_only(src):
    return "\n".join(l for l in src.split("\n") if not l.lstrip().startswith("//"))


def block(src, b, e):
    if src.count(b) != 1 or src.count(e) != 1:
        return None
    i = src.index(b)
    return src[i:src.index("\n", src.index(e)) + 1]


def func(src, head):
    i = src.index(head)
    m = re.search(r"\n(?=\S)", src[i + len(head):])
    return src[i:i + len(head) + (m.start() + 1 if m else len(src))]


def inputs(src):
    return re.findall(r"^\s*(\w+)\s*=\s*(input\.\w+\(.*)$", src, re.M)


# =============================================================================
# BS : static
# =============================================================================
def gate_static():
    check("BS-01 current Visual == bon_transform(Visual @ 9270c50) exactly", bool(BASE) and bb.bon_transform(BASE) == CUR)
    check("BS-02 strip_bon(current) == Visual @ 9270c50 byte-for-byte", bb.strip_bon(CUR) == BASE)
    dl = [l for l in difflib.unified_diff(BASE.split("\n"), CUR.split("\n"), lineterm="", n=0)
          if l[:1] in "+-" and not l.startswith(("+++", "---"))]
    exp = ["-" + a.rstrip("\n") for a, _ in bb.BON_EDITS[:2]] + ["+" + b.rstrip("\n") for _, b in bb.BON_EDITS[:2]] + \
          ["-" + bb.BON_EDITS[2][0].rstrip("\n"), "+" + bb.BON_EDITS[2][1].rstrip("\n")]
    check("BS-03 the Production diff is exactly the three input defaults (1.0 -> 0.0, 1.0 -> 0.0, 2.0 -> 0.0)", dl == exp, str(dl))
    ic, ib = dict(inputs(CUR)), dict(inputs(BASE))
    changed = sorted(k for k in ic if ic[k] != ib.get(k))
    check("BS-04 every other input identical (names, defaults, options); the three inputs still exist (user can set them)",
          changed == ["flipBonus", "maClusterBonus", "maClusterDirBonus"] and set(ic) == set(ib)
          and ic["maClusterBonus"].startswith("input.float(0.0,") and ic["maClusterDirBonus"].startswith("input.float(0.0,")
          and ic["flipBonus"].startswith("input.float(0.0,"), str(changed))
    must = ['slopeThrMod = input.float(1.0, "Slope Threshold · Moderate ($/lookback)"',
            'slopeThrStrong = input.float(3.0, "Slope Threshold · Strong ($/lookback)"',
            'slopeBonusFlat = input.float(0.0, "Slope Bonus · Flat"', 'slopeBonusMod = input.float(1.0, "Slope Bonus · Moderate"',
            'slopeBonusStr = input.float(2.0, "Slope Bonus · Strong"', 'slopeLookback = input.int(60, "Slope Lookback (MA TF bars)"',
            'slopeBonusMode = input.string("Sum (per MA)", "Slope Bonus Aggregation in Cluster",',
            'scoreMa1 = input.float(2.0, "Base Score · MA #1"', 'scoreMa2 = input.float(2.0, "Base Score · MA #2"',
            'thrMedium = input.float(5.0,', 'thrStrong = input.float(10.0,', 'thrVStrong = input.float(15.0,']
    check("BS-05 MA slope (1 / 3 $, bonuses 0 / 1 / 2, lookback 60, Sum per MA), MA base 2 / 2 and Strength thresholds "
          "5 / 10 / 15 unchanged", all(CUR.count(m) == 1 for m in must), str([m for m in must if CUR.count(m) != 1]))
    cfgs = re.findall(r"^zoneCfg\.\w+\s*:=.*$", CUR, re.M)
    check("BS-06 all zoneCfg assignments identical (incl. maClusterBonus / maClusterDirBonus / flipBonus / slopeBonusMax / "
          "useRnSource)", cfgs == re.findall(r"^zoneCfg\.\w+\s*:=.*$", BASE, re.M)
          and all(any(c.startswith(f"zoneCfg.{k} ") for c in cfgs) for k in ("maClusterBonus", "maClusterDirBonus", "flipBonus")))
    check("BS-07 import stays ZoneEnginePractical/6", re.findall(r"^import .*$", CUR, re.M) == ["import sekine3310/ZoneEnginePractical/6 as zn"])
    for name, b, e in (("NR-S1", nb.NRS_BEGIN, nb.NRS_END), ("NR-A1", na.NRA_BEGIN, na.NRA_END),
                       ("FVG Batch A", cb.A_BEGIN, cb.A_END), ("FVG Batch C", cb.C_BEGIN, cb.C_END),
                       ("overlap-only display + FVG labels", zp.ZPO_BEGIN, zp.ZPO_END)):
        check(f"BS-08 {name} block byte-identical to 9270c50", block(CUR, b, e) is not None and block(CUR, b, e) == block(BASE, b, e))
    names = ["ZoneEnginePractical.pine", "ZoneEnginePracticalRN.pine", "ZoneEnginePracticalSwingMax.pine",
             "SignalEnginePractical.pine", "PracticalZoneStrategy_LONG.pine", "PracticalZoneStrategy_SHORT.pine"]
    d = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", bb.BON_BASE_REV, "--"] + names, capture_output=True, text=True).stdout
    check("BS-09 Engines (/2, /5, /6), Strategy, SignalEngine unchanged", d.strip() == "", d)
    up = func(LIB6, "f_updateTrack(")
    fz = func(LIB6, "f_finalizeCluster(")
    check("BS-10 Engine /6 semantics the change relies on: cluster MA bonus = max(member maClusterBonus); flipBonus only "
          "scores a flipped track (z.flipBonus := t.flipped ? c.flipBonus : 0.0); Flip detection / state (f_updateTrack) "
          "never reads flipBonus",
          "maB      := math.max(maB, m.maClusterBonus)" in fz and "z.flipBonus := t.flipped ? c.flipBonus : 0.0" in LIB6
          and "flipBonus" not in up)


# =============================================================================
# BM : scoring with old / new defaults
# =============================================================================
class Cfg(pz.Cfg):
    zoneHalfWidth = 3.0
    clusterDist = 5.0
    slopeBonusMax = False


def ma_cluster_bonus(ma1, ma2, d1, d2, cb_, db_, dist=20.0):
    """Engine update 6.2: both MAs within maClusterDist -> maClusterBonus (+ Same Slope when directions match)."""
    sdir = lambda d: 1 if d > 0 else -1 if d < 0 else 0
    if abs(ma1 - ma2) <= dist:
        return cb_ + (db_ if sdir(d1) != 0 and sdir(d1) == sdir(d2) else 0.0)
    return 0.0


def cluster_score(c, ma, flipped, cb_, db_, fb_, slopes=(1.0, 2.0)):
    """score = baseSum + slope (Sum per MA) + max(maClusterBonus) + flip + confluence, for a zone holding MA1 / MA2
    (when ma is given) and a 1H Swing."""
    mem = [pz.Raw(1, "SWING_H", pz.CAT_HZ, "60", 4200.0, 3.0, c)]
    if ma is not None:
        m1, m2, d1, d2 = ma
        mcb = ma_cluster_bonus(m1, m2, d1, d2, cb_, db_)
        mem.append(pz.Raw(-1, "MA1", pz.CAT_MA, "1", m1, 2.0, c, slopeBonus=slopes[0], maClusterBonus=mcb))
        if abs(m2 - 4200.0) <= 5:
            mem.append(pz.Raw(-2, "MA2", pz.CAT_MA, "1", m2, 2.0, c, slopeBonus=slopes[1], maClusterBonus=mcb))
    base, slope, maB, _r, conf, htf = pz.score_parts(mem, c)
    flip = fb_ if flipped else 0.0
    s = base + slope + maB + flip + conf
    return s, pz.strength_of(s, htf, c), dict(base=base, slope=slope, maB=maB, flip=flip, conf=conf)


def gate_scoring():
    c = Cfg()
    OLD, NEW = (1.0, 1.0, 2.0), (0.0, 0.0, 0.0)
    cases = [("no bonus (MAs far apart, not flipped)", (4200.5, 4260.0, 1.0, -1.0), False, 0.0),
             ("MA proximity only (directions differ)", (4200.5, 4201.5, 1.0, -1.0), False, -1.0),
             ("MA proximity + same slope", (4200.5, 4201.5, 1.0, 2.0), False, -2.0),
             ("Flip only (no MA)", None, True, -2.0),
             ("all three (proximity + same slope + flip)", (4200.5, 4201.5, 1.0, 2.0), True, -4.0)]
    rows = []
    for name, ma, fl, exp in cases:
        so, _, po = cluster_score(c, ma, fl, *OLD)
        sn, _, pn = cluster_score(c, ma, fl, *NEW)
        rows.append((name, so, sn))
        ok = sn - so == exp and pn["base"] == po["base"] and pn["slope"] == po["slope"] and pn["conf"] == po["conf"]
        check(f"BM-{len(rows):02d} {name}: score change {exp:+g}; base / MA slope (Sum) / confluence unchanged", ok, str(rows[-1]))
    # each default on its own (the Same Slope bonus only exists together with proximity)
    ma = (4200.5, 4201.5, 1.0, 2.0)
    s_old, _, _ = cluster_score(c, ma, True, *OLD)
    one = [cluster_score(c, ma, True, 0.0, 1.0, 2.0)[0] - s_old, cluster_score(c, ma, True, 1.0, 0.0, 2.0)[0] - s_old,
           cluster_score(c, ma, True, 1.0, 1.0, 0.0)[0] - s_old]
    check("BM-06 each default alone: MA Cluster Bonus -1, Same Slope -1, Flip Bonus -2 (sum -4)", one == [-1.0, -1.0, -2.0], str(one))
    _, _, p = cluster_score(c, ma, False, *NEW, slopes=(1.0, 2.0))
    check("BM-07 MA slope bonuses still summed per MA (1 + 2 = 3) with the new defaults; MA base 2 + 2",
          p["slope"] == 3.0 and p["base"] == 3.0 + 2.0 + 2.0, str(p))
    cmax = Cfg()
    cmax.slopeBonusMax = True
    _, _, pm = cluster_score(cmax, ma, False, *NEW)
    check("BM-08 (control) the Max aggregation would give 2 - the Visual default stays Sum", pm["slope"] == 2.0)


# =============================================================================
# BY : time series, old vs new defaults
# =============================================================================
def gate_series():
    import rn1_engine_model as em
    import zp_overlap_sim as zs
    C = em.C
    keep = (C.maClusterBonus, C.maClusterDirBonus, C.flipBonus)
    rep = dict(bars=0, geo=0, trk=0, ev=0, raw=0, fvg=0, flips=0, zones=0, changed=0, bad_diff=0, drop_sum=0.0, drop_max=0.0,
               ma_drop=0, flip_drop=0, touch_bars=0, boost_changes=0, snaps=0)
    trans, hist = {}, {}

    def setp(v):
        C.maClusterBonus, C.maClusterDirBonus, C.flipBonus = v

    try:
        for rn in (False, True):
            for seed in (0, 1):
                b1, chart, htf = em.build(seed, 12)
                F = em.Feeds(b1, chart, htf, "nr")
                A, B = em.Engine(), em.Engine()
                A.rn_attach = B.rn_attach = rn
                A.swing_max = B.swing_max = True
                for i in range(len(chart)):
                    f = F.feed(i, len(chart[i]["subs"]) - 1, "hist")
                    setp((1.0, 1.0, 2.0))
                    A.update(f, i)
                    da = A.display()
                    setp((0.0, 0.0, 0.0))
                    B.update(f, i)
                    db = B.display()
                    rep["bars"] += 1
                    g = lambda E: [(z["top"], z["bottom"], tuple(z["uids"]), z["trackId"], z["state"]) for z in E.live]
                    rep["geo"] += g(A) != g(B)
                    tk = lambda E: [(t.id, t.state, t.breakDir, t.retested, t.flipped, t.lastSeenBar, tuple(t.memberUids)) for t in E.tracks]
                    rep["trk"] += tk(A) != tk(B)
                    rep["ev"] += A.events != B.events
                    rw = lambda E: sorted((r.uid, r.srcId, r.srcTf, r.center, r.instId, r.expireTime) for r in E.persist)
                    rep["raw"] += rw(A) != rw(B)
                    fv = lambda E: [(s, E.fTop[s], E.fBot[s]) for s in range(15) if E.fAlive[s]]
                    rep["fvg"] += fv(A) != fv(B)
                    rep["flips"] += sum(1 for t in A.tracks if t.flipped)
                    for za, zb in zip(A.live, B.live):
                        rep["zones"] += 1
                        d = za["score"] - zb["score"]
                        exp = (za["maB"] - zb["maB"]) + (za["flipBonus"] - zb["flipBonus"])
                        rep["bad_diff"] += abs(d - exp) > 1e-9 or zb["maB"] != 0.0 or zb["flipBonus"] != 0.0 \
                            or (za["baseSum"], za["slopeB"], za["confB"], za["catCount"]) != (zb["baseSum"], zb["slopeB"], zb["confB"], zb["catCount"])
                        if d > 0:
                            rep["changed"] += 1
                            rep["drop_sum"] += d
                            rep["drop_max"] = max(rep["drop_max"], d)
                            rep["ma_drop"] += za["maB"] > 0
                            rep["flip_drop"] += za["flipBonus"] > 0
                            hist[round(d)] = hist.get(round(d), 0) + 1
                        if za["strength"] != zb["strength"]:
                            k = (za["strength"], zb["strength"])
                            trans[k] = trans.get(k, 0) + 1
                    ta = {t.id: t.touchCount for t in A.tracks}
                    rep["touch_bars"] += any(t.touchCount != ta.get(t.id) for t in B.tracks)
                    if i % 40 == 39:
                        rep["snaps"] += 1
                        rep["boost_changes"] += da != db
    finally:
        setp(keep)
    REPORT.update(rep)
    REPORT["hist"], REPORT["trans"] = hist, trans
    check("BY-01 old vs new defaults on the same series (Swing max, RN OFF and ON): Raw Zones, zone geometry / members / "
          "track id / state, Track id / state / break / retest / flipped, events, FVG storage identical every bar",
          rep["bars"] > 0 and all(rep[k] == 0 for k in ("geo", "trk", "ev", "raw", "fvg")), str(rep))
    check("BY-02 every score difference is exactly (old max MA cluster bonus) + (old flip bonus); new zones carry 0 for "
          "both; base / slope / confluence / categories identical", rep["bad_diff"] == 0 and rep["changed"] > 0, str(rep))
    check("BY-03 Flip states exist in the series and stay (only their bonus is 0); both causes occur",
          rep["flips"] > 0 and rep["ma_drop"] > 0 and rep["flip_drop"] > 0 and rep["drop_max"] <= 4.0, str(rep))


def main():
    for g in (gate_static, gate_scoring, gate_series):
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
    if REPORT:
        r = REPORT
        print(f"\nREPORT  zones {r['zones']}, score lowered {r['changed']} (MA {r['ma_drop']}, Flip {r['flip_drop']}), mean "
              f"{(r['drop_sum'] / r['changed']) if r['changed'] else 0:.3f}, max {r['drop_max']:g}, drop histogram "
              f"{dict(sorted(r['hist'].items()))}")
        print(f"REPORT  strength old -> new: {dict(sorted(r['trans'].items()))}; Touch-changed bars {r['touch_bars']}; "
              f"FVG display changed {r['boost_changes']}/{r['snaps']} snapshots")
    print(f"\n{len(RESULTS) - fails}/{len(RESULTS)} passed  [PINE_NOT_VERIFIED: exact transform / static / port / model]")
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
