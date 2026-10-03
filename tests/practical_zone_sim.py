#!/usr/bin/env python3
"""
Practical Zone v1 — logic fixtures (Python port, NOT a Pine compile).

Ports the relevant parts of ZoneEngine.pine (legacy) and
ZoneEnginePractical.pine (practical) line by line and checks:

  G1-G3   Variable Zone Geometry
  S1      Base Strength independent of Touch Count
  T1-T3   Strong Touch Count (Strong / Medium / Broken)
  C1      Cluster parity: membership, baseSum, slope/ma/conf bonus, HTF,
          Strength (reaction bonus = 0) on random inputs
  P1      Persist expiry gate == legacy every-bar scan
  K1      Track stale gate == legacy every-bar scan

Run:  python3 tests/practical_zone_sim.py
"""
import math
import random

# ---- constants (same values as the Pine libraries) -------------------------
ST_ACTIVE, ST_SUPPORT, ST_RESIST, ST_BROKEN = 0, 1, 2, 3
SR_WEAK, SR_MEDIUM, SR_STRONG, SR_VSTRONG = 1, 2, 3, 4
CAT_MA, CAT_HZ, CAT_DHL, CAT_ACC = "MA", "Horizontal", "DayHL", "Accum"


class Cfg:
    zoneHalfWidth = 5.0
    hzTf1, hzTf2, hzTf3 = "5", "15", "60"
    accTf1, accTf2, accTf3 = "60", "240", "D"
    scoreHz1, scoreHz2, scoreHz3 = 1.0, 2.0, 3.0
    clusterDist = 20.0
    thrMedium, thrStrong, thrVStrong = 5.0, 10.0, 15.0
    confBonus2, confBonus3, confBonus4 = 1.0, 2.0, 3.0
    flipBonus = 2.0
    slopeBonusMax = False
    requireHtfForVStrong = True
    htfSwing1H = htfAccum1H = htfAccum4H = htfAccumD = True
    htfSwing15M = htfMa1 = htfMa2 = htfDayHL = False
    reactionBonus1, reactionBonus2, reactionBonus3 = 1.0, 2.0, 3.0
    touchRearmDist = 10.0
    trackStaleBars = 500
    maxPersistZones = 200


class Raw:
    def __init__(self, uid, srcId, srcCat, srcTf, center, baseScore, c,
                 slopeBonus=0.0, maClusterBonus=0.0, reactionBonus=0.0, reactionCnt=0):
        self.uid, self.srcId, self.srcCat, self.srcTf = uid, srcId, srcCat, srcTf
        self.center = center
        self.top = center + c.zoneHalfWidth
        self.bottom = center - c.zoneHalfWidth
        self.baseScore = baseScore
        self.slopeBonus = slopeBonus
        self.maClusterBonus = maClusterBonus
        self.reactionBonus = reactionBonus
        self.reactionCnt = reactionCnt


def weight(z):
    return max(z.baseScore, 0.01)


def strength_of(score, hasHtf, c):
    t = SR_WEAK if score < c.thrMedium else SR_MEDIUM if score < c.thrStrong else \
        SR_STRONG if score < c.thrVStrong else SR_VSTRONG
    if t == SR_VSTRONG and c.requireHtfForVStrong and not hasHtf:
        t = SR_STRONG
    return t


def conf_bonus(cat, c):
    return c.confBonus4 if cat >= 4 else c.confBonus3 if cat == 3 else c.confBonus2 if cat == 2 else 0.0


def score_parts(members, c):
    """Common body of f_finalizeCluster (baseSum / bonuses / HTF / categories)."""
    baseSum = slopeB = maB = reactB = 0.0
    hits = set()
    htf = False
    cats = set()
    for m in members:
        isSwing = m.srcCat == CAT_HZ and m.srcId in ("SWING_H", "SWING_L")
        isAccHi = m.srcId == "ACC_HI"
        if isSwing:
            if m.srcTf == c.hzTf1:
                if "sw1" not in hits:
                    hits.add("sw1"); baseSum += c.scoreHz1
            elif m.srcTf == c.hzTf2:
                if "sw2" not in hits:
                    hits.add("sw2"); baseSum += c.scoreHz2
            elif m.srcTf == c.hzTf3:
                if "sw3" not in hits:
                    hits.add("sw3"); baseSum += c.scoreHz3
            else:
                baseSum += m.baseScore
        elif m.srcCat == CAT_ACC:
            slot = 1 if m.srcTf == c.accTf1 else 2 if m.srcTf == c.accTf2 else 3 if m.srcTf == c.accTf3 else 0
            if slot == 0:
                baseSum += m.baseScore
            else:
                key = ("hi" if isAccHi else "lo") + str(slot)
                if key not in hits:
                    hits.add(key); baseSum += m.baseScore
        else:
            baseSum += m.baseScore
        slopeB = max(slopeB, m.slopeBonus) if c.slopeBonusMax else slopeB + m.slopeBonus
        maB = max(maB, m.maClusterBonus)
        reactB = max(reactB, m.reactionBonus)
        if isSwing and m.srcTf == c.hzTf3 and c.htfSwing1H: htf = True
        if isSwing and m.srcTf == c.hzTf2 and c.htfSwing15M: htf = True
        if m.srcCat == CAT_ACC and m.srcTf == c.accTf1 and c.htfAccum1H: htf = True
        if m.srcCat == CAT_ACC and m.srcTf == c.accTf2 and c.htfAccum4H: htf = True
        if m.srcCat == CAT_ACC and m.srcTf == c.accTf3 and c.htfAccumD: htf = True
        if m.srcId == "MA1" and c.htfMa1: htf = True
        if m.srcId == "MA2" and c.htfMa2: htf = True
        if m.srcCat == CAT_DHL and c.htfDayHL: htf = True
        cats.add(m.srcCat)
    return baseSum, slopeB, maB, reactB, conf_bonus(len(cats), c), htf


# ---- legacy f_buildClusters / f_finalizeCluster ----------------------------
def legacy_finalize(members, c):
    tw = ts = 0.0
    for m in members:
        w = weight(m); tw += w; ts += m.center * w
    ctr = ts / tw
    baseSum, slopeB, maB, reactB, confB, htf = score_parts(members, c)
    score = baseSum + slopeB + maB + reactB + 0.0 + confB   # f_applyStrength order
    return dict(uids=[m.uid for m in members], center=ctr,
                top=ctr + c.zoneHalfWidth, bottom=ctr - c.zoneHalfWidth,
                baseSum=baseSum, slopeB=slopeB, maB=maB, reactB=reactB, confB=confB,
                hasHtf=htf, score=score, strength=strength_of(score, htf, c))


def legacy_build(src, c):
    out = []
    if not src:
        return out
    ord_ = sorted(range(len(src)), key=lambda i: (src[i].center, i))
    cur = []
    for k in ord_:
        z = src[k]
        if not cur:
            cur.append(z); continue
        tw = ts = 0.0
        for m in cur:
            w = weight(m); tw += w; ts += m.center * w
        wz = weight(z)
        nc = (ts + z.center * wz) / (tw + wz)
        ok = abs(z.center - nc) <= c.clusterDist
        if ok:
            for m in cur:
                if abs(m.center - nc) > c.clusterDist:
                    ok = False; break
        if ok:
            cur.append(z)
        else:
            out.append(legacy_finalize(cur, c)); cur = [z]
    if cur:
        out.append(legacy_finalize(cur, c))
    return out


# ---- practical f_buildClusters / f_finalizeCluster -------------------------
def practical_finalize(members, c, zBot, zTop):
    baseSum, slopeB, maB, _reactB, confB, htf = score_parts(members, c)
    score = baseSum + slopeB + maB + 0.0 + confB            # no reaction term
    return dict(uids=[m.uid for m in members], center=(zTop + zBot) / 2,
                top=zTop, bottom=zBot, baseSum=baseSum, slopeB=slopeB, maB=maB,
                confB=confB, hasHtf=htf, score=score, strength=strength_of(score, htf, c))


def practical_build(persist, dyn, c):
    out = []
    src = persist + dyn
    if not src:
        return out
    ord_ = sorted(range(len(src)), key=lambda i: (src[i].center, i))
    cur = []
    wSum = wcSum = 0.0
    minC = maxC = minB = maxT = None
    for k in ord_:
        z = src[k]
        wz = weight(z)
        if cur:
            nc = (wcSum + z.center * wz) / (wSum + wz)
            ok = (abs(z.center - nc) <= c.clusterDist and abs(minC - nc) <= c.clusterDist
                  and abs(maxC - nc) <= c.clusterDist)
            if not ok:
                out.append(practical_finalize(cur, c, minB, maxT))
                cur = []
                wSum = wcSum = 0.0
                minC = maxC = minB = maxT = None
        cur.append(z)
        wSum += wz
        wcSum += z.center * wz
        minC = z.center if minC is None else min(minC, z.center)
        maxC = z.center if maxC is None else max(maxC, z.center)
        minB = z.bottom if minB is None else min(minB, z.bottom)
        maxT = z.top if maxT is None else max(maxT, z.top)
    if cur:
        out.append(practical_finalize(cur, c, minB, maxT))
    return out


# ---- Strong Touch Count (f_updateTouch) ------------------------------------
class Track:
    def __init__(self, top, bottom):
        self.top, self.bottom = top, bottom
        self.state = ST_ACTIVE
        self.touchCount, self.touchArmed, self.touchActive, self.lastTouchBar = 0, True, False, None


def update_touch(t, strength, hi, lo, bar, c):
    if t.touchArmed:
        eligible = strength >= SR_STRONG and t.state in (ST_SUPPORT, ST_RESIST)
        if eligible and lo <= t.top and hi >= t.bottom:
            t.touchCount += 1
            t.touchArmed, t.touchActive, t.lastTouchBar = False, True, bar
    else:
        if lo >= t.top + c.touchRearmDist or hi <= t.bottom - c.touchRearmDist:
            t.touchArmed, t.touchActive = True, False
    return t.touchCount


# ---- tiny test harness -----------------------------------------------------
RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))


def fixtures_geometry():
    c = Cfg()
    a = Raw(1, "SWING_H", CAT_HZ, "60", 4050.0, 3.0, c)
    z = practical_build([a], [], c)
    check("G1 single root 4050±5 -> 4045~4055",
          len(z) == 1 and z[0]["bottom"] == 4045 and z[0]["top"] == 4055 and z[0]["center"] == 4050,
          f"{z[0]['bottom']}~{z[0]['top']} c={z[0]['center']}")

    a = Raw(1, "SWING_H", CAT_HZ, "60", 4050.0, 3.0, c)
    b = Raw(2, "SWING_L", CAT_HZ, "15", 4060.0, 2.0, c)
    z = practical_build([a, b], [], c)
    check("G2 4050±5 + 4060±5 same cluster -> 4045~4065 center 4055",
          len(z) == 1 and z[0]["bottom"] == 4045 and z[0]["top"] == 4065 and z[0]["center"] == 4055,
          f"n={len(z)} {z[0]['bottom']}~{z[0]['top']} c={z[0]['center']}")
    lz = legacy_build([a, b], c)
    check("G2 legacy reference: same grouping, fixed width ±5",
          len(lz) == 1 and lz[0]["uids"] == z[0]["uids"] and abs(lz[0]["top"] - lz[0]["bottom"] - 10) < 1e-9,
          f"legacy {lz[0]['bottom']:.2f}~{lz[0]['top']:.2f}")

    a = Raw(1, "SWING_H", CAT_HZ, "60", 4050.0, 3.0, c)
    b = Raw(2, "SWING_L", CAT_HZ, "15", 4100.0, 2.0, c)
    z = practical_build([a, b], [], c)
    check("G3 different clusters (4050 / 4100) are not merged",
          len(z) == 2 and z[0]["top"] == 4055 and z[1]["bottom"] == 4095,
          f"n={len(z)}")

    # G3b: wide union must NOT cause an extra merge (membership is clusterDist only)
    #       weighted newCenter = (4050*3 + 4095*2)/5 = 4068 -> |4095-4068| = 27 > 20
    c2 = Cfg(); c2.zoneHalfWidth = 25.0
    a = Raw(1, "SWING_H", CAT_HZ, "60", 4050.0, 3.0, c2)
    b = Raw(2, "SWING_L", CAT_HZ, "15", 4095.0, 2.0, c2)   # boxes overlap (4075 > 4070)
    z = practical_build([a, b], [], c2)
    lz = legacy_build([a, b], c2)
    check("G3b overlapping boxes but clusterDist fails -> still 2 zones (no overlap-merge)",
          len(z) == 2 and [x["uids"] for x in z] == [x["uids"] for x in lz], f"n={len(z)}")


def fixtures_strength():
    c = Cfg()
    # 1H swing (3) + 4H accum (4) + 2000MA (2) -> base 9, 3 categories conf +2 = 11 -> STRONG
    members = [Raw(1, "SWING_H", CAT_HZ, "60", 4050.0, 3.0, c),
               Raw(2, "ACC_HI", CAT_ACC, "240", 4052.0, 4.0, c),
               Raw(-1, "MA1", CAT_MA, "1", 4048.0, 2.0, c)]
    base = practical_build(members, [], c)[0]
    strengths = []
    for touches in (0, 1, 5):
        t = Track(base["top"], base["bottom"]); t.state = ST_SUPPORT
        bar = 0
        for _ in range(touches):
            update_touch(t, base["strength"], base["top"] + 1, base["bottom"] + 1, bar, c); bar += 1
            update_touch(t, base["strength"], base["top"] + 50, base["top"] + 20, bar, c); bar += 1
        # Strength is recomputed from the same sources; touchCount is not an input
        again = practical_build(members, [], c)[0]
        strengths.append((t.touchCount, again["score"], again["strength"]))
    ok = all(s[2] == SR_STRONG and s[1] == base["score"] for s in strengths) and \
        [s[0] for s in strengths] == [0, 1, 5]
    check("S1 Touch 0 / 1 / 5 -> STRONG / STRONG / STRONG, score unchanged", ok, str(strengths))

    # legacy would have promoted it via reaction bonus: show the removed path differs
    m2 = [Raw(1, "SWING_H", CAT_HZ, "60", 4050.0, 3.0, c, reactionBonus=c.reactionBonus3, reactionCnt=5),
          Raw(2, "ACC_HI", CAT_ACC, "240", 4052.0, 4.0, c),
          Raw(-1, "MA1", CAT_MA, "1", 4048.0, 2.0, c)]
    lz = legacy_build(m2, c)[0]
    pz = practical_build(m2, [], c)[0]
    check("S2 reaction-heavy input: legacy score +3 (reaction), practical unchanged",
          lz["score"] == base["score"] + 3 and pz["score"] == base["score"],
          f"legacy={lz['score']} practical={pz['score']}")


def fixtures_touch():
    c = Cfg()
    t = Track(4065.0, 4045.0); t.state = ST_SUPPORT
    seq = []
    bar = 0

    def step(hi, lo, strength=SR_STRONG):
        nonlocal bar
        n = update_touch(t, strength, hi, lo, bar, c); bar += 1
        return n

    seq.append(("start", t.touchCount))
    seq.append(("first overlap", step(4070, 4060)))
    for i in range(5):
        seq.append((f"inside {i+1}", step(4064, 4050)))
    seq.append(("partially away (not enough)", step(4080, 4070)))
    seq.append(("still disarmed", t.touchArmed))
    seq.append(("fully away low>=top+10", step(4090, 4075)))
    seq.append(("rearmed", t.touchArmed))
    seq.append(("re-touch", step(4080, 4064)))
    counts = [s[1] for s in seq]
    expect = [0, 1, 1, 1, 1, 1, 1, 1, False, 1, True, 2]
    check("T1 Strong: 0 -> overlap 1 -> 5 bars inside 1 -> away rearm -> re-touch 2",
          counts == expect, str(seq))

    m = Track(4065.0, 4045.0); m.state = ST_SUPPORT
    for b in range(6):
        update_touch(m, SR_MEDIUM, 4070, 4050, b, c)
        update_touch(m, SR_MEDIUM, 4120, 4090, b, c)
    check("T2 Medium: contacts never counted", m.touchCount == 0, f"count={m.touchCount}")

    k = Track(4065.0, 4045.0); k.state = ST_BROKEN
    for b in range(6):
        update_touch(k, SR_VSTRONG, 4070, 4050, b, c)
        update_touch(k, SR_VSTRONG, 4120, 4090, b, c)
    check("T3 Broken: contacts never counted", k.touchCount == 0, f"count={k.touchCount}")

    # T4: Strong -> Medium -> Strong keeps the count and resumes counting
    s = Track(4065.0, 4045.0); s.state = ST_RESIST
    update_touch(s, SR_STRONG, 4070, 4050, 0, c)          # 1
    update_touch(s, SR_STRONG, 4030, 4000, 1, c)          # away below -> rearm
    update_touch(s, SR_MEDIUM, 4070, 4050, 2, c)          # medium: not counted
    c1 = s.touchCount
    update_touch(s, SR_STRONG, 4070, 4050, 3, c)          # strong again: 2
    check("T4 Strong->Medium->Strong keeps count (1 -> 1 -> 2)", (c1, s.touchCount) == (1, 2),
          f"{c1},{s.touchCount}")

    # T5: Broken -> Flip (same track) keeps count
    f = Track(4065.0, 4045.0); f.state = ST_SUPPORT
    update_touch(f, SR_STRONG, 4070, 4050, 0, c)          # 1
    f.state = ST_BROKEN
    update_touch(f, SR_STRONG, 4030, 4000, 1, c)          # away -> rearm (no count)
    update_touch(f, SR_STRONG, 4060, 4050, 2, c)          # broken contact: no count
    f.state = ST_RESIST                                    # flip confirmed
    update_touch(f, SR_STRONG, 4060, 4050, 3, c)          # counted: 2
    check("T5 Broken -> Flip keeps count (1 -> 2)", f.touchCount == 2, f"count={f.touchCount}")


def random_raws(rng, c, n, base=4000.0, span=300.0, ties=True):
    kinds = [("SWING_H", CAT_HZ, "5", 1.0), ("SWING_L", CAT_HZ, "15", 2.0), ("SWING_H", CAT_HZ, "60", 3.0),
             ("PDH", CAT_HZ, "PD", 2.0), ("ACC_HI", CAT_ACC, "60", 3.0), ("ACC_LO", CAT_ACC, "240", 4.0),
             ("ACC_HI", CAT_ACC, "D", 5.0)]
    out = []
    for i in range(n):
        sid, cat, tf, bs = rng.choice(kinds)
        ctr = base + rng.random() * span
        if ties and out and rng.random() < 0.15:
            ctr = rng.choice(out).center
        ctr = round(ctr, rng.choice([0, 1, 2, 3]))
        out.append(Raw(i + 1, sid, cat, tf, ctr, bs if rng.random() > 0.05 else 0.0, c))
    return out


def random_dyn(rng, c):
    out = []
    if rng.random() < 0.8:
        out.append(Raw(-1, "MA1", CAT_MA, "1", 4000 + rng.random() * 300, 2.0, c,
                       slopeBonus=rng.choice([0.0, 1.0, 2.0]), maClusterBonus=rng.choice([0.0, 1.0, 2.0])))
    if rng.random() < 0.8:
        out.append(Raw(-2, "MA2", CAT_MA, "1", 4000 + rng.random() * 300, 2.0, c,
                       slopeBonus=rng.choice([0.0, 1.0, 2.0]), maClusterBonus=rng.choice([0.0, 1.0, 2.0])))
    out.append(Raw(1000001, "DAY_HIGH", CAT_DHL, "D", 4000 + rng.random() * 300, 3.0, c))
    out.append(Raw(1000002, "DAY_LOW", CAT_DHL, "D", 4000 + rng.random() * 300, 3.0, c))
    return out


def fixture_cluster_parity():
    rng = random.Random(20261003)
    c = Cfg()
    trials = 3000
    bad = 0
    detail = ""
    for t in range(trials):
        c.clusterDist = rng.choice([5.0, 10.0, 20.0, 35.0])
        c.slopeBonusMax = rng.random() < 0.5
        persist = random_raws(rng, c, rng.randint(0, 120))
        dyn = random_dyn(rng, c)
        L = legacy_build(persist + dyn, c)
        P = practical_build(persist, dyn, c)
        same = len(L) == len(P)
        if same:
            for a, b in zip(L, P):
                if (a["uids"] != b["uids"] or a["baseSum"] != b["baseSum"] or a["slopeB"] != b["slopeB"]
                        or a["maB"] != b["maB"] or a["confB"] != b["confB"] or a["hasHtf"] != b["hasHtf"]
                        or a["score"] != b["score"] or a["strength"] != b["strength"]):
                    same = False; break
        if not same:
            bad += 1
            detail = f"trial {t}"
    check(f"C1 cluster parity on {trials} random inputs (grouping / baseSum / bonuses / HTF / score / strength)",
          bad == 0, detail or "0 mismatches")


def fixture_persist_gate():
    """Legacy: every bar remove expireTime>0 and time>expireTime, then while size>max shift.
    Practical: scan only when time > nextExp; max-check only on push bars."""
    rng = random.Random(7)
    mismatches = 0
    scans_legacy = scans_gate = 0
    for trial in range(300):
        maxP = rng.randint(5, 40)
        L, P = [], []
        nextExp = None
        uid = 0
        t = 0
        for bar in range(600):
            t += 300
            added = False
            # registrations (static with life / accum without life), and dup refresh
            for _ in range(rng.choice([0, 0, 0, 1, 2])):
                if L and rng.random() < 0.3:
                    i = rng.randrange(len(L))
                    if L[i]["exp"] > 0:
                        # life may differ per refresh (e.g. hzTf1 == hzTf2 with different
                        # lifetimes), so a refresh can move expireTime earlier as well
                        newexp = t + rng.choice([3000, 9000, 30000])
                        L[i]["exp"] = newexp
                        for z in P:
                            if z["uid"] == L[i]["uid"]:
                                z["exp"] = newexp
                        nextExp = newexp if nextExp is None else min(nextExp, newexp)
                    continue
                uid += 1
                exp = t + rng.choice([0, 3000, 9000, 30000])
                L.append(dict(uid=uid, exp=exp)); P.append(dict(uid=uid, exp=exp))
                added = True
                if exp > 0:
                    nextExp = exp if nextExp is None else min(nextExp, exp)
            # legacy
            scans_legacy += 1
            L = [z for z in L if not (z["exp"] > 0 and t > z["exp"])]
            while len(L) > maxP:
                L.pop(0)
            # practical
            if nextExp is not None and t > nextExp:
                scans_gate += 1
                keep, ne = [], None
                for z in P:
                    if z["exp"] > 0 and t > z["exp"]:
                        continue
                    keep.append(z)
                    if z["exp"] > 0:
                        ne = z["exp"] if ne is None else min(ne, z["exp"])
                P, nextExp = keep, ne
            if added:
                while len(P) > maxP:
                    P.pop(0)
            if [z["uid"] for z in L] != [z["uid"] for z in P]:
                mismatches += 1
    check("P1 persist expiry gate == legacy every-bar scan (300 x 600 bars)", mismatches == 0,
          f"mismatch bars={mismatches}, expiry scans legacy={scans_legacy} gated={scans_gate}")


def fixture_track_gate():
    rng = random.Random(11)
    mismatches = 0
    scans_gate = scans_legacy = 0
    for trial in range(200):
        stale = rng.choice([10, 50, 500])
        L, P = [], []
        nextExp = None
        tid = 0
        for bar in range(2000):
            # match some tracks / create new ones
            for i in range(len(L)):
                if rng.random() < 0.3:
                    L[i]["last"] = bar; P[i]["last"] = bar
            if rng.random() < 0.2:
                tid += 1
                L.append(dict(id=tid, last=bar)); P.append(dict(id=tid, last=bar))
                e = bar + stale + 1
                nextExp = e if nextExp is None else min(nextExp, e)
            scans_legacy += 1
            L = [x for x in L if not (bar - x["last"] > stale)]
            if nextExp is not None and bar >= nextExp:
                scans_gate += 1
                keep, ne = [], None
                for x in P:
                    if bar - x["last"] > stale:
                        continue
                    keep.append(x)
                    e = x["last"] + stale + 1
                    ne = e if ne is None else min(ne, e)
                P, nextExp = keep, ne
            if [x["id"] for x in L] != [x["id"] for x in P]:
                mismatches += 1
    check("K1 track stale gate == legacy every-bar scan (200 x 2000 bars)", mismatches == 0,
          f"mismatch bars={mismatches}, scans legacy={scans_legacy} gated={scans_gate}")


if __name__ == "__main__":
    fixtures_geometry()
    fixtures_strength()
    fixtures_touch()
    fixture_cluster_parity()
    fixture_persist_gate()
    fixture_track_gate()
    width = max(len(n) for n, _, _ in RESULTS)
    fails = 0
    for name, ok, detail in RESULTS:
        fails += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {name.ljust(width)}  {detail}")
    print(f"\n{len(RESULTS) - fails}/{len(RESULTS)} passed")
    raise SystemExit(1 if fails else 0)
