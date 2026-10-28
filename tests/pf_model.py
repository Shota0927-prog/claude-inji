"""PF-1 performance model: an instrumented Python port of ZoneEnginePracticalXAUUSD update() (library version 2 = the
committed ZoneEnginePracticalXAUUSD.pine of XA-6) and of its version 3 (PF-1: the same results with less work), plus a
SYNTHETIC Gold 1M feed (random walk with sessions / weekends; NOT TradingView data, NOT real XAUUSD prices).

Purpose: count, per 5M bar, the work the Engine does (Raw Zones, clusters, members, tracks, loop iterations, allocations)
and compare version 2 with version 3 bar by bar (Zones, Tracks, Scores, states, events). Pine run time itself cannot be
measured here (no TradingView); the counts are operation counts of this port, not milliseconds.

Port rules: same statement order, same float expressions in the same order (Python float = IEEE double like Pine), na =
None, Pine `math.round` of a non-negative value = floor(x + 0.5), `int()` truncates, array.sort_indices = stable sort
(ties: index order; both versions share the same sort input, so the tie rule cannot make them differ).
"""
import math
import random

NA = None
ST_ACTIVE, ST_SUPPORT, ST_RESIST, ST_BROKEN = 0, 1, 2, 3
SR_WEAK, SR_MEDIUM, SR_STRONG, SR_VSTRONG = 1, 2, 3, 4
CAT_MA, CAT_HZ, CAT_DHL, CAT_ACC = "MA", "Horizontal", "DayHL", "Accum"
MS_PER_DAY = 86400000
SRC_SW1, SRC_SW2, SRC_SW3, SRC_HZX, SRC_ACC1, SRC_ACC2, SRC_ACC3, SRC_MA1, SRC_MA2, SRC_DHL, SRC_RN = (
    1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024)
HTF_SW1H, HTF_ACC1, HTF_ACC2, HTF_ACC3, HTF_SW15, HTF_MA1, HTF_MA2, HTF_DAY = 1, 2, 4, 8, 16, 32, 64, 128
MINTICK = 0.01
M1 = 60_000


def p_round(x):
    return math.floor(x + 0.5)


class Cfg:
    """ZoneCfg as the Gold Short Strategy sets it (its input defaults; the Long differs only by thrStrong 9.0)."""
    def __init__(self, **kw):
        self.zoneHalfWidth = 6.0
        self.useMaSource = True
        self.maTfName = "1"
        self.scoreMa1 = 3.0
        self.scoreMa2 = 3.0
        self.slopeThrMod, self.slopeThrStrong = 1.0, 3.0
        self.slopeBonusFlat, self.slopeBonusMod, self.slopeBonusStr = 0.0, 1.0, 2.0
        self.slopeBonusMax = True
        self.maClusterDist, self.maClusterBonus, self.maClusterDirBonus = 20.0, 0.0, 0.0
        self.useHzSource = True
        self.hzTf1, self.hzTf2, self.hzTf3 = "5", "15", "60"
        self.scoreHz1, self.scoreHz2, self.scoreHz3 = 1.0, 2.0, 3.0
        self.touchRearmDist = 10.0
        self.useDayHL = True
        self.scoreDayHL = 3.0
        self.carryPrevDayHL = False
        self.scorePrevDayHL = 2.0
        self.lifePrevDayHL = 5.0
        self.useAccSource = True
        self.accTf1, self.accTf2, self.accTf3 = "60", "240", "D"
        self.scoreAcc1, self.scoreAcc2, self.scoreAcc3 = 3.0, 4.0, 5.0
        self.accKeep1, self.accKeep2, self.accKeep3 = 3, 2, 1
        self.accScoreMax = False
        self.accEdgeOnce = False
        self.dsMerge = True
        self.dsDist = 0.0
        self.clusterDist = 5.0
        self.thrMedium, self.thrStrong, self.thrVStrong = 5.0, 10.0, 15.0
        self.confBonus2, self.confBonus3, self.confBonus4 = 1.0, 2.0, 3.0
        self.flipBonus = 0.0
        self.requireHtfForVStrong = True
        self.htfSwing1H = self.htfAccum1H = self.htfAccum4H = self.htfAccumD = True
        self.htfSwing15M = self.htfMa1 = self.htfMa2 = self.htfDayHL = False
        self.breakBuffer = 10.0
        self.flipConfirmDist = 5.0
        self.resetOnReclaim = True
        self.roleOnBreak = False
        self.trackStaleBars = 500
        self.trackContinuity = 0.5
        self.lifeHz1, self.lifeHz2, self.lifeHz3 = 5.0, 10.0, 30.0
        self.maxPersistZones = 200
        self.useRnSource = True
        self.rnStepMajor, self.rnScoreMajor, self.rnStepMinor, self.rnScoreMinor = 100.0, 3.0, 50.0, 2.0
        for k, v in kw.items():
            assert hasattr(self, k), k
            setattr(self, k, v)


class Raw:
    __slots__ = ("uid", "instId", "srcId", "srcCat", "srcTf", "center", "top", "bottom", "baseScore", "slopeState",
                 "slopeDir", "slopeBonus", "maClusterBonus", "flipped", "flipBonus", "createdBar", "createdTime",
                 "expireTime", "dynamic", "px0", "px1", "kind")

    def __init__(self, **kw):
        self.uid = 0; self.instId = 0; self.srcId = ""; self.srcCat = ""; self.srcTf = ""
        self.center = 0.0; self.top = 0.0; self.bottom = 0.0; self.baseScore = 0.0
        self.slopeState = 0; self.slopeDir = 0; self.slopeBonus = 0.0; self.maClusterBonus = 0.0
        self.flipped = False; self.flipBonus = 0.0; self.createdBar = 0; self.createdTime = 0; self.expireTime = 0
        self.dynamic = False; self.px0 = NA; self.px1 = NA; self.kind = 0
        for k, v in kw.items():
            setattr(self, k, v)


class Zone:
    def __init__(self, **kw):
        self.center = 0.0; self.top = 0.0; self.bottom = 0.0; self.score = 0.0; self.baseSum = 0.0
        self.slopeBonus = 0.0; self.maBonus = 0.0; self.flipBonus = 0.0; self.confBonus = 0.0
        self.strength = 1; self.state = 0; self.flipped = False; self.flipDir = 0; self.catCount = 0
        self.memberCount = 0; self.trackId = -1; self.memberUids = NA; self.hasHtf = False
        self.srcMask = 0; self.htfMask = 0; self.touchCount = 0
        self.rnLevel = NA; self.rnBase = 0.0; self.rnScoreDelta = 0.0; self.rnBaseSumExRn = 0.0
        for k, v in kw.items():
            setattr(self, k, v)

    KEYS = ("center", "top", "bottom", "score", "baseSum", "slopeBonus", "maBonus", "flipBonus", "confBonus", "strength",
            "state", "flipped", "flipDir", "catCount", "memberCount", "trackId", "hasHtf", "srcMask", "htfMask",
            "touchCount", "rnLevel", "rnBase", "rnScoreDelta", "rnBaseSumExRn")

    def snap(self):
        return tuple(getattr(self, k) for k in self.KEYS) + (tuple(self.memberUids),)


class Track:
    KEYS = ("id", "center", "top", "bottom", "state", "lastRole", "breakDir", "breakBar", "retested", "flipped", "flipDir",
            "lastSeenBar", "matchedBar", "touchCount", "touchArmed", "touchActive", "lastTouchBar", "wasStrong")

    def __init__(self, **kw):
        self.id = 0; self.center = 0.0; self.top = 0.0; self.bottom = 0.0; self.state = 0; self.lastRole = 0
        self.breakDir = 0; self.breakBar = 0; self.retested = False; self.flipped = False; self.flipDir = 0
        self.lastSeenBar = 0; self.matchedBar = NA; self.memberUids = NA
        self.touchCount = 0; self.touchArmed = True; self.touchActive = False; self.lastTouchBar = NA
        self.wasStrong = False
        self.uidSet = NA     # version 3 only (lookup set of memberUids)
        for k, v in kw.items():
            setattr(self, k, v)

    def snap(self):
        return tuple(getattr(self, k) for k in self.KEYS) + (tuple(self.memberUids),)


class Bar:
    """the chart-bar values the Engine reads (bar_index / time / OHLC)."""
    __slots__ = ("i", "time", "open", "high", "low", "close")

    def __init__(self, i, t, o, h, l, c):
        self.i, self.time, self.open, self.high, self.low, self.close = i, t, o, h, l, c


class Feed:
    __slots__ = ("ma1", "ma1d", "ma2", "ma2d", "ph1", "ph1t", "pl1", "pl1t", "ph2", "ph2t", "pl2", "pl2t", "ph3", "ph3t",
                 "pl3", "pl3t", "acc1Hi", "acc1Lo", "acc1Id", "acc2Hi", "acc2Lo", "acc2Id", "acc3Hi", "acc3Lo", "acc3Id",
                 "dayId", "brClose", "brHigh", "brLow", "brEval")

    def __init__(self):
        for k in self.__slots__:
            setattr(self, k, NA)
        self.brEval = False


class Counters(dict):
    def add(self, k, v=1):
        self[k] = self.get(k, 0) + v


# ================================================================== the Engine (version 2 = committed source, exact port)
def f_days2ms(d):
    return int(d * MS_PER_DAY)


def f_hasBit(m, b):
    return math.floor(m / b) % 2 == 1


def f_setBit(m, b):
    return m if f_hasBit(m, b) else m + b


def f_weightOf(z):
    return max(z.baseScore, 0.01)


def f_strengthOf(score, hasHtf, c):
    t = SR_WEAK if score < c.thrMedium else SR_MEDIUM if score < c.thrStrong else SR_STRONG if score < c.thrVStrong else SR_VSTRONG
    if t == SR_VSTRONG and c.requireHtfForVStrong and not hasHtf:
        t = SR_STRONG
    return t


def nz(x, d=0.0):
    return d if x is None else x


def f_slopeState(delta, c):
    a = abs(nz(delta))
    return 2 if a >= c.slopeThrStrong else 1 if a >= c.slopeThrMod else 0


def f_slopeDir(delta):
    return 1 if nz(delta) > 0 else -1 if nz(delta) < 0 else 0


def f_slopeBonusValue(st, c):
    return c.slopeBonusStr if st == 2 else c.slopeBonusMod if st == 1 else c.slopeBonusFlat


def f_confluenceBonus(cat, c):
    return c.confBonus4 if cat >= 4 else c.confBonus3 if cat == 3 else c.confBonus2 if cat == 2 else 0.0


def f_rnLevelIn(zBot, zTop, step):
    lv = NA
    k1 = math.ceil(zBot / step)
    k2 = math.floor(zTop / step)
    if k1 <= k2:
        ctr = (zTop + zBot) / 2
        kc = max(k1, min(k2, math.floor(ctr / step)))
        lv = kc * step
        if kc + 1 <= k2:
            if (kc + 1) * step - ctr < ctr - lv:
                lv = (kc + 1) * step
    return lv


def f_swingMaxStep(swMax, s):
    add = s if swMax is None else (s - swMax if s > swMax else 0.0)
    mx = s if swMax is None else max(swMax, s)
    return add, mx


def f_naturalState(close, top, bottom):
    return ST_SUPPORT if close > top else ST_RESIST if close < bottom else ST_ACTIVE


class Engine:
    """version 2 (the committed ZoneEnginePracticalXAUUSD.pine)."""
    V3 = False

    def __init__(self, c):
        self.c = c
        self.persist, self.live, self.tracks = [], [], []
        self.uidSeq = self.trackSeq = self.rawCount = 0
        self.dayHighUid = self.dayLowUid = 0
        self.dayHigh = self.dayLow = self.prevDayHigh = self.prevDayLow = self.prevDayId = NA
        for k in ("pPh1t", "pPl1t", "pPh2t", "pPl2t", "pPh3t", "pPl3t", "pAcc1Id", "pAcc1Hi", "pAcc1Lo", "pAcc2Id",
                  "pAcc2Hi", "pAcc2Lo", "pAcc3Id", "pAcc3Hi", "pAcc3Lo"):
            setattr(self, k, NA)
        self.evUpBreak = self.evDownBreak = self.evFlipSup = self.evFlipRes = False
        self.ma1Dir = self.ma2Dir = 0
        self.maClusterBonus = 0.0
        self.nextPersistExpireTime = NA
        self.nextTrackExpireBar = NA
        self.persistAdded = False
        self.sDynPool = [Raw(dynamic=True) for _ in range(4)]
        self.sDyn, self.sCenters, self.sCur, self.sIds = [], [], [], []
        self.n = Counters()
        self.b = None

    # ---- 3.5 registration
    def f_nextUid(self):
        self.uidSeq += 1
        return self.uidSeq

    def f_makeRaw(self, uid, id_, cat, tf, ctr, bs, dyn):
        c, b = self.c, self.b
        self.n.add("alloc_raw")
        return Raw(uid=uid, srcId=id_, srcCat=cat, srcTf=tf, center=ctr, top=ctr + c.zoneHalfWidth,
                   bottom=ctr - c.zoneHalfWidth, baseScore=bs, createdBar=b.i, createdTime=b.time, dynamic=dyn)

    def f_onPersistPush(self, expireTime):
        self.persistAdded = True
        if expireTime > 0:
            self.nextPersistExpireTime = expireTime if self.nextPersistExpireTime is None else min(self.nextPersistExpireTime, expireTime)

    def f_registerStatic(self, trig, price, id_, cat, tf, bs, lifeDays):
        c, b = self.c, self.b
        if trig and price is not None:
            life = f_days2ms(lifeDays)
            dup = False
            for z in self.persist:
                self.n.add("it_regStatic")
                if z.srcId == id_ and z.srcTf == tf and abs(z.center - price) <= c.zoneHalfWidth:
                    dup = True
                    z.px1 = price
                    if life > 0:
                        z.expireTime = b.time + life
                        self.nextPersistExpireTime = z.expireTime if self.nextPersistExpireTime is None else min(self.nextPersistExpireTime, z.expireTime)
                    self.touch_persist(z)
                    break
            if not dup:
                rz = self.f_makeRaw(self.f_nextUid(), id_, cat, tf, price, bs, False)
                rz.expireTime = b.time + life if life > 0 else 0
                rz.px0 = price
                rz.px1 = price
                self.push_persist(rz)
                self.f_onPersistPush(rz.expireTime)

    def f_registerAccumZone(self, trig, price, instId, id_, tf, bs):
        c = self.c
        if trig and price is not None and instId is not None:
            found = False
            for z in self.persist:
                self.n.add("it_regAcc")
                if z.srcCat == CAT_ACC and z.srcId == id_ and z.srcTf == tf and z.instId == instId:
                    found = True
                    z.center = price
                    z.top = price + c.zoneHalfWidth
                    z.bottom = price - c.zoneHalfWidth
                    self.touch_persist(z)
                    break
            if not found:
                rz = self.f_makeRaw(self.f_nextUid(), id_, CAT_ACC, tf, price, bs, False)
                rz.instId = instId
                rz.expireTime = 0
                self.push_persist(rz)
                self.f_onPersistPush(rz.expireTime)

    def f_pruneAccumGenerations(self, trig, tf, keepCount):
        if trig and keepCount >= 1:
            ids = self.sIds
            ids.clear()
            for z in self.persist:
                self.n.add("it_pruneAcc")
                if z.srcCat == CAT_ACC and z.srcTf == tf and z.instId not in ids:
                    ids.append(z.instId)
            while len(ids) > keepCount:
                oldest = ids[0]
                oi = 0
                for k in range(1, len(ids)):
                    if ids[k] < oldest:
                        oldest = ids[k]
                        oi = k
                ids.pop(oi)
                for i in range(len(self.persist) - 1, -1, -1):
                    self.n.add("it_pruneAcc")
                    if i < len(self.persist):
                        z = self.persist[i]
                        if z.srcCat == CAT_ACC and z.srcTf == tf and z.instId == oldest:
                            self.remove_persist(i)

    def f_prunePersist(self):
        c, b = self.c, self.b
        if self.nextPersistExpireTime is not None and b.time > self.nextPersistExpireTime:
            nextExp = NA
            for i in range(len(self.persist) - 1, -1, -1):
                self.n.add("it_expire")
                if i < len(self.persist):
                    z = self.persist[i]
                    if z.expireTime > 0 and b.time > z.expireTime:
                        self.remove_persist(i)
                    elif z.expireTime > 0:
                        nextExp = z.expireTime if nextExp is None else min(nextExp, z.expireTime)
            self.nextPersistExpireTime = nextExp
        if self.persistAdded:
            while len(self.persist) > c.maxPersistZones:
                z0 = self.persist[0]
                if z0.srcCat == CAT_ACC:
                    tf0, id0 = z0.srcTf, z0.instId
                    for i in range(len(self.persist) - 1, -1, -1):
                        self.n.add("it_cap")
                        if i < len(self.persist):
                            z = self.persist[i]
                            if z.srcCat == CAT_ACC and z.srcTf == tf0 and z.instId == id0:
                                self.remove_persist(i)
                else:
                    self.remove_persist(0)
        self.persistAdded = False

    # persist mutation hooks (version 2: plain array operations; version 3 also keeps its cluster cache key)
    def push_persist(self, rz):
        self.persist.append(rz)

    def remove_persist(self, i):
        self.persist.pop(i)

    def touch_persist(self, z):
        pass

    # ---- 04 cluster / score
    def f_finalizeCluster(self, members, zBot, zTop):
        c = self.c
        self.n.add("call_finalize")
        self.n.add("alloc_zone")
        self.n.add("alloc_uids")
        baseSum = 0.0; slopeB = 0.0; maB = 0.0
        hasMA = hasHZ = hasDHL = hasACC = False
        swHit1 = swHit2 = swHit3 = False
        swMax = NA
        accHi1 = accLo1 = accHi2 = accLo2 = accHi3 = accLo3 = False
        accA1 = accA2 = accA3 = 0.0
        dsOn = c.dsMerge
        dsTk = p_round(c.dsDist / MINTICK) if dsOn else 0
        dHpx = dLpx = NA
        dHm = dLm = hasDH = hasDL = hzInd = swInd1 = swInd2 = swInd3 = False
        srcM = 0
        htfM = 0
        uids = []
        n = len(members)
        if dsOn:
            for j in range(n):
                self.n.add("it_finalize_ds")
                q = members[j]
                if q.srcId == "DAY_HIGH":
                    dHpx = q.px0
                elif q.srcId == "DAY_LOW":
                    dLpx = q.px0
        for j in range(n):
            self.n.add("it_finalize")
            m = members[j]
            isSwing = m.srcCat == CAT_HZ and (m.srcId == "SWING_H" or m.srcId == "SWING_L")
            isAccHi = m.srcId == "ACC_HI"
            if isSwing:
                mH = dsOn and m.srcId == "SWING_H" and dHpx is not None and (p_round(abs(dHpx - m.px0) / MINTICK) <= dsTk or p_round(abs(dHpx - m.px1) / MINTICK) <= dsTk)
                mL = dsOn and m.srcId == "SWING_L" and dLpx is not None and (p_round(abs(dLpx - m.px0) / MINTICK) <= dsTk or p_round(abs(dLpx - m.px1) / MINTICK) <= dsTk)
                sl = 1 if m.srcTf == c.hzTf1 else 2 if m.srcTf == c.hzTf2 else 3 if m.srcTf == c.hzTf3 else 0
                dHm = dHm or mH
                dLm = dLm or mL
                if not mH and not mL:
                    hzInd = True
                    swInd1 = swInd1 or sl == 1
                    swInd2 = swInd2 or sl == 2
                    swInd3 = swInd3 or sl == 3
                if m.srcTf == c.hzTf1:
                    srcM = f_setBit(srcM, SRC_SW1)
                    if not swHit1:
                        swHit1 = True
                        a, swMax = f_swingMaxStep(swMax, c.scoreHz1)
                        baseSum += a
                elif m.srcTf == c.hzTf2:
                    srcM = f_setBit(srcM, SRC_SW2)
                    if not swHit2:
                        swHit2 = True
                        a, swMax = f_swingMaxStep(swMax, c.scoreHz2)
                        baseSum += a
                elif m.srcTf == c.hzTf3:
                    srcM = f_setBit(srcM, SRC_SW3)
                    if not swHit3:
                        swHit3 = True
                        a, swMax = f_swingMaxStep(swMax, c.scoreHz3)
                        baseSum += a
                else:
                    srcM = f_setBit(srcM, SRC_HZX)
                    baseSum += m.baseScore
            elif m.srcCat == CAT_ACC:
                if m.srcTf == c.accTf1:
                    srcM = f_setBit(srcM, SRC_ACC1)
                    if isAccHi and not accHi1:
                        e = 0.0 if c.accEdgeOnce and accLo1 else m.baseScore
                        accHi1 = True; accA1 += e; baseSum += 0.0 if c.accScoreMax else e
                    elif not isAccHi and not accLo1:
                        e = 0.0 if c.accEdgeOnce and accHi1 else m.baseScore
                        accLo1 = True; accA1 += e; baseSum += 0.0 if c.accScoreMax else e
                elif m.srcTf == c.accTf2:
                    srcM = f_setBit(srcM, SRC_ACC2)
                    if isAccHi and not accHi2:
                        e = 0.0 if c.accEdgeOnce and accLo2 else m.baseScore
                        accHi2 = True; accA2 += e; baseSum += 0.0 if c.accScoreMax else e
                    elif not isAccHi and not accLo2:
                        e = 0.0 if c.accEdgeOnce and accHi2 else m.baseScore
                        accLo2 = True; accA2 += e; baseSum += 0.0 if c.accScoreMax else e
                elif m.srcTf == c.accTf3:
                    srcM = f_setBit(srcM, SRC_ACC3)
                    if isAccHi and not accHi3:
                        e = 0.0 if c.accEdgeOnce and accLo3 else m.baseScore
                        accHi3 = True; accA3 += e; baseSum += 0.0 if c.accScoreMax else e
                    elif not isAccHi and not accLo3:
                        e = 0.0 if c.accEdgeOnce and accHi3 else m.baseScore
                        accLo3 = True; accA3 += e; baseSum += 0.0 if c.accScoreMax else e
                else:
                    baseSum += m.baseScore
            else:
                baseSum += m.baseScore
                if m.srcCat == CAT_HZ:
                    srcM = f_setBit(srcM, SRC_HZX)
                    hzInd = True
                elif m.srcId == "MA1":
                    srcM = f_setBit(srcM, SRC_MA1)
                elif m.srcId == "MA2":
                    srcM = f_setBit(srcM, SRC_MA2)
                elif m.srcCat == CAT_DHL:
                    srcM = f_setBit(srcM, SRC_DHL)
                    hasDH = hasDH or m.srcId == "DAY_HIGH"
                    hasDL = hasDL or m.srcId == "DAY_LOW"
            slopeB = max(slopeB, m.slopeBonus) if c.slopeBonusMax else slopeB + m.slopeBonus
            maB = max(maB, m.maClusterBonus)
            if isSwing and m.srcTf == c.hzTf3 and c.htfSwing1H:
                htfM = f_setBit(htfM, HTF_SW1H)
            if isSwing and m.srcTf == c.hzTf2 and c.htfSwing15M:
                htfM = f_setBit(htfM, HTF_SW15)
            if m.srcCat == CAT_ACC and m.srcTf == c.accTf1 and c.htfAccum1H:
                htfM = f_setBit(htfM, HTF_ACC1)
            if m.srcCat == CAT_ACC and m.srcTf == c.accTf2 and c.htfAccum4H:
                htfM = f_setBit(htfM, HTF_ACC2)
            if m.srcCat == CAT_ACC and m.srcTf == c.accTf3 and c.htfAccumD:
                htfM = f_setBit(htfM, HTF_ACC3)
            if m.srcId == "MA1" and c.htfMa1:
                htfM = f_setBit(htfM, HTF_MA1)
            if m.srcId == "MA2" and c.htfMa2:
                htfM = f_setBit(htfM, HTF_MA2)
            if m.srcCat == CAT_DHL and c.htfDayHL:
                htfM = f_setBit(htfM, HTF_DAY)
            uids.append(m.uid)
            hasMA = hasMA or m.srcCat == CAT_MA
            hasHZ = hasHZ or m.srcCat == CAT_HZ
            hasDHL = hasDHL or m.srcCat == CAT_DHL
            hasACC = hasACC or m.srcCat == CAT_ACC
        return self.f_finalizeTail(n, uids, baseSum, slopeB, maB, hasMA, hasHZ, hasDHL, hasACC, swHit1, swHit2, swHit3,
                                   swMax, accA1, accA2, accA3, dsOn, dHm, dLm, hasDH, hasDL, hzInd, swInd1, swInd2,
                                   swInd3, srcM, htfM, zBot, zTop)

    def f_finalizeTail(self, n, uids, baseSum, slopeB, maB, hasMA, hasHZ, hasDHL, hasACC, swHit1, swHit2, swHit3, swMax,
                       accA1, accA2, accA3, dsOn, dHm, dLm, hasDH, hasDL, hzInd, swInd1, swInd2, swInd3, srcM, htfM,
                       zBot, zTop):
        c = self.c
        if c.accScoreMax:
            baseSum += max(accA1, max(accA2, accA3))
        dsCatAdj = 0
        if dsOn and (dHm or dLm):
            top1 = swHit1 and c.scoreHz1 == swMax
            top2 = swHit2 and c.scoreHz2 == swMax
            top3 = swHit3 and c.scoreHz3 == swMax
            blocked = (top1 and swInd1) or (top2 and swInd2) or (top3 and swInd3)
            if not blocked and (top1 or top2 or top3):
                baseSum -= min(c.scoreDayHL, swMax)
            dhlInd = (hasDH and not dHm) or (hasDL and not dLm)
            if not hzInd and not dhlInd and not (dHm and dLm):
                dsCatAdj = 1
        baseSumEx = baseSum
        rnLv = NA
        rnB = 0.0
        if c.useRnSource:
            lvMaj = f_rnLevelIn(zBot, zTop, c.rnStepMajor)
            if lvMaj is not None:
                rnLv = lvMaj; rnB = c.rnScoreMajor
            else:
                lvMin = f_rnLevelIn(zBot, zTop, c.rnStepMinor)
                if lvMin is not None:
                    rnLv = lvMin; rnB = c.rnScoreMinor
        hasRN = rnB > 0
        if hasRN:
            baseSum += rnB
            srcM = f_setBit(srcM, SRC_RN)
        cat = (1 if hasMA else 0) + (1 if hasHZ else 0) + (1 if hasDHL else 0) + (1 if hasACC else 0) + (1 if hasRN else 0) - dsCatAdj
        confB = f_confluenceBonus(cat, c)
        rnD = rnB + (confB - f_confluenceBonus(cat - 1, c)) if hasRN else 0.0
        ctr = (zTop + zBot) / 2
        return Zone(center=ctr, top=zTop, bottom=zBot, score=baseSum + slopeB + maB + confB, baseSum=baseSum,
                    slopeBonus=slopeB, maBonus=maB, flipBonus=0.0, confBonus=confB, strength=SR_WEAK, state=ST_ACTIVE,
                    flipped=False, flipDir=0, catCount=cat, memberCount=n, trackId=-1, memberUids=uids,
                    hasHtf=htfM != 0, srcMask=srcM, htfMask=htfM, rnLevel=rnLv, rnBase=rnB, rnScoreDelta=rnD,
                    rnBaseSumExRn=baseSumEx)

    def f_buildClusters(self):
        c = self.c
        self.live.clear()
        nP, nD = len(self.persist), len(self.sDyn)
        n = nP + nD
        if n > 0:
            centers = self.sCenters
            centers.clear()
            for z in self.persist:
                centers.append(z.center)
            for z in self.sDyn:
                centers.append(z.center)
            ord_ = sorted(range(n), key=lambda i: centers[i])
            self.n.add("it_sort", n)
            cur = self.sCur
            cur.clear()
            wSum = wcSum = 0.0
            minC = maxC = minB = maxT = NA
            cDH = cDL = NA      # version 3: Day High / Low price of the cluster being built (last one, as the pre-scan)
            for k in range(n):
                self.n.add("it_cluster")
                oi = ord_[k]
                z = self.persist[oi] if oi < nP else self.sDyn[oi - nP]
                wz = f_weightOf(z)
                if len(cur) > 0:
                    newCenter = (wcSum + z.center * wz) / (wSum + wz)
                    ok = abs(z.center - newCenter) <= c.clusterDist and abs(minC - newCenter) <= c.clusterDist and abs(maxC - newCenter) <= c.clusterDist
                    if not ok:
                        self.live.append(self.f_finalizeCluster(cur, minB, maxT) if not self.V3 else self.f_finalizeCluster(cur, minB, maxT, cDH, cDL))
                        self.n.add("max_members", 0)
                        self.n["max_members"] = max(self.n["max_members"], len(cur))
                        cur.clear()
                        wSum = wcSum = 0.0
                        minC = maxC = minB = maxT = NA
                        cDH = cDL = NA
                cur.append(z)
                if self.V3:
                    if z.kind[1] == 6:
                        cDH = z.px0
                    elif z.kind[1] == 7:
                        cDL = z.px0
                wSum += wz
                wcSum += z.center * wz
                minC = z.center if minC is None else min(minC, z.center)
                maxC = z.center if maxC is None else max(maxC, z.center)
                minB = z.bottom if minB is None else min(minB, z.bottom)
                maxT = z.top if maxT is None else max(maxT, z.top)
            if len(cur) > 0:
                self.live.append(self.f_finalizeCluster(cur, minB, maxT) if not self.V3 else self.f_finalizeCluster(cur, minB, maxT, cDH, cDL))
                self.n.add("max_members", 0)
                self.n["max_members"] = max(self.n["max_members"], len(cur))
                cur.clear()
        return len(self.live)

    def f_applyStrength(self, z):
        c = self.c
        z.score = z.baseSum + z.slopeBonus + z.maBonus + z.flipBonus + z.confBonus
        z.strength = f_strengthOf(z.score, z.hasHtf, c)
        return z.strength

    # ---- 05 state / break / flip
    def f_uidOverlap(self, a, b):
        cnt = 0
        if a is not None and b is not None and len(a) > 0 and len(b) > 0:
            for x in a:
                self.n.add("it_overlap_outer")
                self.n.add("it_includes", len(b))       # array.includes = linear scan
                if x in b:
                    cnt += 1
        return cnt

    def f_trackContinuous(self, t, z):
        self.n.add("call_continuity")
        ov = self.f_uidOverlap(z.memberUids, t.memberUids)
        sz = 0 if z.memberUids is None else len(z.memberUids)
        st = 0 if t.memberUids is None else len(t.memberUids)
        mx = max(sz, st)
        return ov >= 1 and mx > 0 and (float(ov) / float(mx)) >= self.c.trackContinuity

    def f_findTrack(self, z):
        c, b = self.c, self.b
        best = -1
        bestD = 1e20
        for i, t in enumerate(self.tracks):
            self.n.add("it_findTrack")
            if t.matchedBar is None or t.matchedBar != b.i:
                d = abs(t.center - z.center)
                if d <= c.clusterDist and d < bestD:
                    if self.f_trackContinuous(t, z):
                        bestD = d
                        best = i
        return best

    def f_updateTrack(self, t, evalBar, bc, bh, bl):
        c, b = self.c, self.b
        ev = 0
        prevState = t.state
        handled = False
        evalState = (ST_SUPPORT if t.lastRole > 0 else ST_RESIST if t.lastRole < 0 else ST_ACTIVE) if prevState == ST_ACTIVE else prevState
        if evalBar and c.roleOnBreak:
            if evalState == ST_RESIST and bc > t.top + c.breakBuffer:
                t.state = ST_SUPPORT; t.breakDir = 1; t.breakBar = b.i; t.retested = False; t.flipped = False; t.flipDir = 0
                handled = True; ev = 1
            elif evalState == ST_SUPPORT and bc < t.bottom - c.breakBuffer:
                t.state = ST_RESIST; t.breakDir = -1; t.breakBar = b.i; t.retested = False; t.flipped = False; t.flipDir = 0
                handled = True; ev = -1
            elif t.breakDir == 1:
                handled = True
                if not t.retested:
                    if bl <= t.top and bh >= t.bottom:
                        t.retested = True
                elif bc >= t.top + c.flipConfirmDist:
                    t.flipped = True; t.flipDir = 1; t.breakDir = 0; t.retested = False; ev = 2
            elif t.breakDir == -1:
                handled = True
                if not t.retested:
                    if bh >= t.bottom and bl <= t.top:
                        t.retested = True
                elif bc <= t.bottom - c.flipConfirmDist:
                    t.flipped = True; t.flipDir = -1; t.breakDir = 0; t.retested = False; ev = -2
        elif evalBar:
            if evalState == ST_RESIST and bc > t.top + c.breakBuffer:
                t.state = ST_BROKEN; t.breakDir = 1; t.breakBar = b.i; t.retested = False; t.flipped = False; t.flipDir = 0
                handled = True; ev = 1
            elif evalState == ST_SUPPORT and bc < t.bottom - c.breakBuffer:
                t.state = ST_BROKEN; t.breakDir = -1; t.breakBar = b.i; t.retested = False; t.flipped = False; t.flipDir = 0
                handled = True; ev = -1
            elif prevState == ST_BROKEN and t.breakDir == 1:
                handled = True
                if bc < t.bottom - c.breakBuffer:
                    t.breakDir = 0; t.retested = False
                    if c.resetOnReclaim:
                        t.state = f_naturalState(b.close, t.top, t.bottom)
                elif not t.retested:
                    if bl <= t.top and bh >= t.bottom:
                        t.retested = True
                elif bc >= t.top + c.flipConfirmDist:
                    t.flipped = True; t.flipDir = 1; t.state = ST_SUPPORT; t.breakDir = 0; t.retested = False; ev = 2
            elif prevState == ST_BROKEN and t.breakDir == -1:
                handled = True
                if bc > t.top + c.breakBuffer:
                    t.breakDir = 0; t.retested = False
                    if c.resetOnReclaim:
                        t.state = f_naturalState(b.close, t.top, t.bottom)
                elif not t.retested:
                    if bh >= t.bottom and bl <= t.top:
                        t.retested = True
                elif bc <= t.bottom - c.flipConfirmDist:
                    t.flipped = True; t.flipDir = -1; t.state = ST_RESIST; t.breakDir = 0; t.retested = False; ev = -2
        if not handled and t.state == ST_ACTIVE:
            t.state = f_naturalState(b.close, t.top, t.bottom)
        if t.state == ST_SUPPORT:
            t.lastRole = 1
        elif t.state == ST_RESIST:
            t.lastRole = -1
        return ev

    def f_updateTouch(self, t, z):
        c, b = self.c, self.b
        isStrong = z.strength >= SR_STRONG
        if isStrong and not t.wasStrong:
            t.touchCount = 0; t.touchArmed = False; t.touchActive = False; t.lastTouchBar = NA
        t.wasStrong = isStrong
        if t.touchArmed:
            eligible = z.strength >= SR_STRONG and (t.state == ST_SUPPORT or t.state == ST_RESIST)
            if eligible and b.low <= t.top and b.high >= t.bottom:
                t.touchCount += 1; t.touchArmed = False; t.touchActive = True; t.lastTouchBar = b.i
        else:
            awayUp = b.low >= t.top + c.touchRearmDist
            awayDown = b.high <= t.bottom - c.touchRearmDist
            if awayUp or awayDown:
                t.touchArmed = True; t.touchActive = False
        return t.touchCount

    def f_maSlopeBonus(self, maVal, d, st):
        b = self.b
        aligned = (d > 0 and b.close > maVal) or (d < 0 and b.close < maVal)
        return f_slopeBonusValue(st, self.c) if aligned else 0.0

    def f_pushDyn(self, slot, uid, id_, cat, tf, ctr, bs, slopeSt, slopeDr, slopeB, maClB):
        c, b = self.c, self.b
        rz = self.sDynPool[slot]
        rz.uid = uid; rz.srcId = id_; rz.srcCat = cat; rz.srcTf = tf; rz.center = ctr
        rz.top = ctr + c.zoneHalfWidth; rz.bottom = ctr - c.zoneHalfWidth; rz.baseScore = bs
        rz.slopeState = slopeSt; rz.slopeDir = slopeDr; rz.slopeBonus = slopeB; rz.maClusterBonus = maClB
        rz.createdBar = b.i; rz.createdTime = b.time
        self.sDyn.append(rz)

    def new_track(self, z):
        b = self.b
        self.trackSeq += 1
        self.n.add("alloc_track")
        self.n.add("alloc_copy")
        return Track(id=self.trackSeq, center=z.center, top=z.top, bottom=z.bottom,
                     state=f_naturalState(b.close, z.top, z.bottom), lastSeenBar=b.i, memberUids=list(z.memberUids))

    def set_track_uids(self, t, z):
        self.n.add("alloc_copy")
        t.memberUids = list(z.memberUids)

    def update(self, b, f):
        c = self.c
        self.b = b
        self.n = Counters()
        tradingDayId = f.dayId
        isNewDay = self.prevDayId is None or tradingDayId != self.prevDayId
        if isNewDay:
            self.prevDayHigh = self.dayHigh; self.prevDayLow = self.dayLow
            self.dayHigh = b.high; self.dayLow = b.low
        else:
            self.dayHigh = b.high if self.dayHigh is None else max(self.dayHigh, b.high)
            self.dayLow = b.low if self.dayLow is None else min(self.dayLow, b.low)
        if isNewDay or self.dayHighUid == 0:
            self.dayHighUid = self.f_nextUid()
            self.dayLowUid = self.f_nextUid()
        ma1Dir, ma2Dir = f_slopeDir(f.ma1d), f_slopeDir(f.ma2d)
        ma1State, ma2State = f_slopeState(f.ma1d, c), f_slopeState(f.ma2d, c)
        ma1SB = 0.0 if f.ma1 is None else self.f_maSlopeBonus(f.ma1, ma1Dir, ma1State)
        ma2SB = 0.0 if f.ma2 is None else self.f_maSlopeBonus(f.ma2, ma2Dir, ma2State)
        maCB = 0.0
        if f.ma1 is not None and f.ma2 is not None and abs(f.ma1 - f.ma2) <= c.maClusterDist:
            maCB = c.maClusterBonus
            if ma1Dir != 0 and ma1Dir == ma2Dir:
                maCB += c.maClusterDirBonus
        self.ma1Dir, self.ma2Dir, self.maClusterBonus = ma1Dir, ma2Dir, maCB

        def edge(v, p):
            return v is not None and (p is None or v != p)
        nPh1, nPl1 = edge(f.ph1t, self.pPh1t), edge(f.pl1t, self.pPl1t)
        nPh2, nPl2 = edge(f.ph2t, self.pPh2t), edge(f.pl2t, self.pPl2t)
        nPh3, nPl3 = edge(f.ph3t, self.pPh3t), edge(f.pl3t, self.pPl3t)
        nAc1 = edge(f.acc1Id, self.pAcc1Id) or edge(f.acc1Hi, self.pAcc1Hi) or edge(f.acc1Lo, self.pAcc1Lo)
        nAc2 = edge(f.acc2Id, self.pAcc2Id) or edge(f.acc2Hi, self.pAcc2Hi) or edge(f.acc2Lo, self.pAcc2Lo)
        nAc3 = edge(f.acc3Id, self.pAcc3Id) or edge(f.acc3Hi, self.pAcc3Hi) or edge(f.acc3Lo, self.pAcc3Lo)

        u = c.useHzSource
        self.f_registerStatic(u and nPh1, f.ph1, "SWING_H", CAT_HZ, c.hzTf1, c.scoreHz1, c.lifeHz1)
        self.f_registerStatic(u and nPl1, f.pl1, "SWING_L", CAT_HZ, c.hzTf1, c.scoreHz1, c.lifeHz1)
        self.f_registerStatic(u and nPh2, f.ph2, "SWING_H", CAT_HZ, c.hzTf2, c.scoreHz2, c.lifeHz2)
        self.f_registerStatic(u and nPl2, f.pl2, "SWING_L", CAT_HZ, c.hzTf2, c.scoreHz2, c.lifeHz2)
        self.f_registerStatic(u and nPh3, f.ph3, "SWING_H", CAT_HZ, c.hzTf3, c.scoreHz3, c.lifeHz3)
        self.f_registerStatic(u and nPl3, f.pl3, "SWING_L", CAT_HZ, c.hzTf3, c.scoreHz3, c.lifeHz3)
        a = c.useAccSource
        self.f_registerAccumZone(a and nAc1, f.acc1Hi, f.acc1Id, "ACC_HI", c.accTf1, c.scoreAcc1)
        self.f_registerAccumZone(a and nAc1, f.acc1Lo, f.acc1Id, "ACC_LO", c.accTf1, c.scoreAcc1)
        self.f_registerAccumZone(a and nAc2, f.acc2Hi, f.acc2Id, "ACC_HI", c.accTf2, c.scoreAcc2)
        self.f_registerAccumZone(a and nAc2, f.acc2Lo, f.acc2Id, "ACC_LO", c.accTf2, c.scoreAcc2)
        self.f_registerAccumZone(a and nAc3, f.acc3Hi, f.acc3Id, "ACC_HI", c.accTf3, c.scoreAcc3)
        self.f_registerAccumZone(a and nAc3, f.acc3Lo, f.acc3Id, "ACC_LO", c.accTf3, c.scoreAcc3)
        self.f_pruneAccumGenerations(a and nAc1, c.accTf1, c.accKeep1)
        self.f_pruneAccumGenerations(a and nAc2, c.accTf2, c.accKeep2)
        self.f_pruneAccumGenerations(a and nAc3, c.accTf3, c.accKeep3)
        pd = c.useDayHL and c.carryPrevDayHL and isNewDay
        self.f_registerStatic(pd, self.prevDayHigh, "PDH", CAT_HZ, "PD", c.scorePrevDayHL, c.lifePrevDayHL)
        self.f_registerStatic(pd, self.prevDayLow, "PDL", CAT_HZ, "PD", c.scorePrevDayHL, c.lifePrevDayHL)
        self.f_prunePersist()

        self.sDyn.clear()
        if c.useMaSource and f.ma1 is not None:
            self.f_pushDyn(0, -1, "MA1", CAT_MA, c.maTfName, f.ma1, c.scoreMa1, ma1State, ma1Dir, ma1SB, maCB)
        if c.useMaSource and f.ma2 is not None:
            self.f_pushDyn(1, -2, "MA2", CAT_MA, c.maTfName, f.ma2, c.scoreMa2, ma2State, ma2Dir, ma2SB, maCB)
        if c.useDayHL and self.dayHigh is not None:
            self.f_pushDyn(2, self.dayHighUid, "DAY_HIGH", CAT_DHL, "D", self.dayHigh, c.scoreDayHL, 0, 0, 0.0, 0.0)
            self.sDynPool[2].px0 = self.dayHigh
        if c.useDayHL and self.dayLow is not None:
            self.f_pushDyn(3, self.dayLowUid, "DAY_LOW", CAT_DHL, "D", self.dayLow, c.scoreDayHL, 0, 0, 0.0, 0.0)
            self.sDynPool[3].px0 = self.dayLow
        self.rawCount = len(self.persist) + len(self.sDyn)

        nZ = self.f_buildClusters()
        for z in self.live:
            self.f_applyStrength(z)
        self.evUpBreak = self.evDownBreak = self.evFlipSup = self.evFlipRes = False
        self.match_tracks(f)

        if self.nextTrackExpireBar is not None and b.i >= self.nextTrackExpireBar:
            nextExp = NA
            for i in range(len(self.tracks) - 1, -1, -1):
                self.n.add("it_trackExpire")
                if i < len(self.tracks):
                    t = self.tracks[i]
                    if b.i - t.lastSeenBar > c.trackStaleBars:
                        self.remove_track(i)
                    else:
                        expBar = t.lastSeenBar + c.trackStaleBars + 1
                        nextExp = expBar if nextExp is None else min(nextExp, expBar)
            self.nextTrackExpireBar = nextExp

        self.prevDayId = tradingDayId
        self.pPh1t, self.pPl1t, self.pPh2t, self.pPl2t, self.pPh3t, self.pPl3t = f.ph1t, f.pl1t, f.ph2t, f.pl2t, f.ph3t, f.pl3t
        self.pAcc1Id, self.pAcc1Hi, self.pAcc1Lo = f.acc1Id, f.acc1Hi, f.acc1Lo
        self.pAcc2Id, self.pAcc2Hi, self.pAcc2Lo = f.acc2Id, f.acc2Hi, f.acc2Lo
        self.pAcc3Id, self.pAcc3Hi, self.pAcc3Lo = f.acc3Id, f.acc3Hi, f.acc3Lo
        self.n["persist"] = len(self.persist)
        self.n["raw"] = self.rawCount
        self.n["zones"] = nZ
        self.n["tracks"] = len(self.tracks)
        return len(self.live)

    def remove_track(self, i):
        self.tracks.pop(i)

    def match_tracks(self, f):
        c, b = self.c, self.b
        for z in self.live:
            ti = self.f_findTrack(z)
            if ti >= 0:
                t = self.tracks[ti]
            else:
                t = self.new_track(z)
                self.tracks.append(t)
                expBar = b.i + c.trackStaleBars + 1
                self.nextTrackExpireBar = expBar if self.nextTrackExpireBar is None else min(self.nextTrackExpireBar, expBar)
            t.matchedBar = b.i
            t.center = z.center; t.top = z.top; t.bottom = z.bottom; t.lastSeenBar = b.i
            self.set_track_uids(t, z)
            ev = self.f_updateTrack(t, f.brEval, f.brClose, f.brHigh, f.brLow)
            self.evUpBreak = self.evUpBreak or ev == 1
            self.evDownBreak = self.evDownBreak or ev == -1
            self.evFlipSup = self.evFlipSup or ev == 2
            self.evFlipRes = self.evFlipRes or ev == -2
            z.state = t.state; z.flipped = t.flipped; z.flipDir = t.flipDir
            z.flipBonus = c.flipBonus if t.flipped else 0.0
            z.trackId = t.id
            self.f_applyStrength(z)
            z.touchCount = self.f_updateTouch(t, z)

    def snap(self):
        """everything observable after update(): live Zones, Tracks (order kept), events, persist Raw Zones, counters."""
        return (tuple(z.snap() for z in self.live), tuple(t.snap() for t in self.tracks),
                (self.evUpBreak, self.evDownBreak, self.evFlipSup, self.evFlipRes, self.ma1Dir, self.ma2Dir,
                 self.maClusterBonus, self.rawCount, self.uidSeq, self.trackSeq, self.dayHigh, self.dayLow,
                 self.nextPersistExpireTime, self.nextTrackExpireBar),
                tuple((r.uid, r.instId, r.srcId, r.srcCat, r.srcTf, r.center, r.top, r.bottom, r.baseScore,
                       r.expireTime, r.px0, r.px1, r.createdBar, r.createdTime) for r in self.persist))


# ================================================================== synthetic feed
TF_MS = {"1": M1, "5": 5 * M1, "15": 15 * M1, "60": 60 * M1, "240": 240 * M1}


def market1m(seed, days, vol=0.45, start=2650.0):
    """SYNTHETIC Gold-like 1M bars: Sun 23:00 - Fri 21:00 UTC with a daily 21:00 - 22:00 UTC break; random walk with
    volatility regimes and trends (USD). Returns [(t, o, h, l, c)]."""
    rnd = random.Random(seed)
    t0 = 1_735_689_600_000          # 2025-01-01 00:00 UTC (Wednesday)
    p = start
    out = []
    regime, left, drift = 1.0, 0, 0.0
    for m in range(days * 1440):
        t = t0 + m * M1
        wd = ((t // MS_PER_DAY) + 3) % 7          # 0 = Monday
        hr = (t // 3_600_000) % 24
        if wd == 5 or (wd == 6 and hr < 23) or (wd == 4 and hr >= 21) or hr == 21:
            continue
        if left <= 0:
            regime = rnd.choice((0.5, 0.8, 1.0, 1.0, 1.5, 2.5))
            drift = rnd.gauss(0, 0.05)
            left = rnd.randint(60, 900)
        left -= 1
        o = p
        steps = [rnd.gauss(drift, vol * regime) for _ in range(4)]
        path = [o]
        for s in steps:
            path.append(path[-1] + s)
        c = round(path[-1], 2)
        h = round(max(path) + abs(rnd.gauss(0, vol * regime * 0.3)), 2)
        l = round(min(path) - abs(rnd.gauss(0, vol * regime * 0.3)), 2)
        o = round(o, 2)
        out.append((t, o, max(h, o, c), min(l, o, c), c))
        p = c
    return out


def agg(bars, ms, daily=False):
    """bars of a higher timeframe (D: trading day 22:00 UTC .. 21:00 UTC, keyed by the session start)."""
    out = {}
    order = []
    for (t, o, h, l, c) in bars:
        k = ((t + 2 * 3_600_000) // MS_PER_DAY * MS_PER_DAY - 2 * 3_600_000) if daily else t // ms * ms
        if k not in out:
            out[k] = [k, o, h, l, c]
            order.append(k)
        else:
            r = out[k]
            r[2] = max(r[2], h); r[3] = min(r[3], l); r[4] = c
    return [tuple(out[k]) for k in order]


def pivots(bars, n):
    """ta.pivothigh / pivotlow (high / low, n, n) per bar: value on bar j = pivot of bar j - n, time = time of bar j."""
    H = [b[2] for b in bars]
    L = [b[3] for b in bars]
    ph, pl = [NA] * len(bars), [NA] * len(bars)
    for j in range(2 * n, len(bars)):
        p = j - n
        w = H[p - n:p + n + 1]
        if H[p] == max(w) and w.index(H[p]) == n and all(x < H[p] for x in H[p + 1:p + n + 1]):
            ph[j] = H[p]
        w = L[p - n:p + n + 1]
        if L[p] == min(w) and w.index(L[p]) == n and all(x > L[p] for x in L[p + 1:p + n + 1]):
            pl[j] = L[p]
    return ph, pl


def accum_box(bars, rangeLen=10, baseLen=20, atrLen=14, minU=4, minL=4, maxRun=4, atrMult=2.5, barRatio=0.70,
              driftMax=0.30):
    """f_accumBoxState of the ported Accum Box on one timeframe -> per bar (top, bot, sid)."""
    O = [b[1] for b in bars]; H = [b[2] for b in bars]; L = [b[3] for b in bars]; C = [b[4] for b in bars]
    out = []
    atr = NA
    trs = []
    top = bot = sid = NA
    prevAcc = False
    for i in range(len(bars)):
        tr = H[i] - L[i] if i == 0 else max(H[i] - L[i], abs(H[i] - C[i - 1]), abs(L[i] - C[i - 1]))
        trs.append(tr)
        if i == atrLen - 1:
            atr = sum(trs[:atrLen]) / atrLen
        elif i >= atrLen:
            atr = (atr * (atrLen - 1) + tr) / atrLen
        isAcc = False
        if i >= max(rangeLen, baseLen) and atr is not None:
            bt = [max(O[k], C[k]) for k in range(i - baseLen + 1, i + 1)]
            bb = [min(O[k], C[k]) for k in range(i - baseLen + 1, i + 1)]
            rH, rL = max(bt[-rangeLen:]), min(bb[-rangeLen:])
            rNow = rH - rL
            mid = (rH + rL) * 0.5
            up = sum(1 for k in range(rangeLen) if C[i - k] > mid)
            lo = sum(1 for k in range(rangeLen) if C[i - k] < mid)
            br = be = mbr = mbe = 0
            for k in range(rangeLen):
                if C[i - k] > O[i - k]:
                    br += 1; be = 0
                elif C[i - k] < O[i - k]:
                    be += 1; br = 0
                else:
                    br = be = 0
                mbr, mbe = max(mbr, br), max(mbe, be)
            drift = abs((O[i] + C[i]) * 0.5 - (O[i - rangeLen + 1] + C[i - rangeLen + 1]) * 0.5)
            rBase = max(bt) - min(bb)
            isAcc = (atr > 0 and rNow <= atr * atrMult and rBase > 0 and rNow <= rBase * barRatio and up >= minU
                     and lo >= minL and rNow > 0 and drift / rNow <= driftMax and mbr <= maxRun and mbe <= maxRun)
            if isAcc and not prevAcc:
                top, bot, sid = rH, rL, bars[i][0]
            if isAcc:
                top = max(top, max(O[i], C[i])); bot = min(bot, min(O[i], C[i]))
        prevAcc = isAcc
        out.append((top, bot, sid))
    return out


def ema(xs, n):
    a = 2.0 / (n + 1)
    out, e = [], NA
    for i, x in enumerate(xs):
        if i < n - 1:
            out.append(NA)
            continue
        e = sum(xs[:n]) / n if i == n - 1 else a * x + (1 - a) * e
        out.append(e)
    return out


def build_feed(b1, c, ma1Len=2000, ma2Len=3000, slopeLb=60, piv=(10, 8, 6)):
    """[(Bar, Feed)] on the 5M chart. HTF Swing / Accum: the value of the last CONFIRMED HTF bar, delivered from the first
    5M bar of the next HTF period (NR-S1 / NR-A1); 5M Swing: pivot on the bar it confirms. MA: 1M EMA, the last 1M bar
    inside the 5M bar. Day id: Asia/Tokyo with reset hour 5 (= UTC 20:00). Break TF = chart (brEval on every bar)."""
    b5 = agg(b1, TF_MS["5"])
    cl1 = [x[4] for x in b1]
    e1, e2 = ema(cl1, ma1Len), ema(cl1, ma2Len)
    t1 = [x[0] for x in b1]
    htf = {tf: agg(b1, TF_MS[tf]) for tf in ("15", "60", "240")}
    htf["D"] = agg(b1, None, daily=True)
    ph5, pl5 = pivots(b5, piv[0])
    pv = {}
    for tf, n in (("15", piv[1]), ("60", piv[2])):
        pv[tf] = pivots(htf[tf], n)
    acc = {tf: accum_box(htf[tf]) for tf in ("60", "240", "D")}

    def htf_index(tf, t):
        """index of the HTF bar containing chart time t."""
        if tf == "D":
            return ((t + 2 * 3_600_000) // MS_PER_DAY * MS_PER_DAY - 2 * 3_600_000)
        return t // TF_MS[tf] * TF_MS[tf]
    pos = {tf: {bar[0]: i for i, bar in enumerate(htf[tf])} for tf in htf}
    out = []
    j1 = 0
    for i, (t, o, h, l, cl) in enumerate(b5):
        bar = Bar(i, t, o, h, l, cl)
        f = Feed()
        while j1 + 1 < len(t1) and t1[j1 + 1] < t + TF_MS["5"]:
            j1 += 1
        if e1[j1] is not None:
            f.ma1 = e1[j1]
            f.ma1d = e1[j1] - e1[j1 - slopeLb] if j1 - slopeLb >= 0 and e1[j1 - slopeLb] is not None else NA
        if e2[j1] is not None:
            f.ma2 = e2[j1]
            f.ma2d = e2[j1] - e2[j1 - slopeLb] if j1 - slopeLb >= 0 and e2[j1 - slopeLb] is not None else NA
        f.ph1, f.pl1 = ph5[i], pl5[i]
        f.ph1t = t if ph5[i] is not None else NA
        f.pl1t = t if pl5[i] is not None else NA
        for tf, ks in (("15", ("ph2", "ph2t", "pl2", "pl2t")), ("60", ("ph3", "ph3t", "pl3", "pl3t"))):
            k = pos[tf].get(htf_index(tf, t))
            if k is not None and k >= 1:
                p_h, p_l = pv[tf][0][k - 1], pv[tf][1][k - 1]
                setattr(f, ks[0], p_h); setattr(f, ks[1], htf[tf][k - 1][0] if p_h is not None else NA)
                setattr(f, ks[2], p_l); setattr(f, ks[3], htf[tf][k - 1][0] if p_l is not None else NA)
        for tf, ks in (("60", ("acc1Hi", "acc1Lo", "acc1Id")), ("240", ("acc2Hi", "acc2Lo", "acc2Id")),
                       ("D", ("acc3Hi", "acc3Lo", "acc3Id"))):
            k = pos[tf].get(htf_index(tf, t))
            if k is not None and k >= 1:
                tp, bt, sid = acc[tf][k - 1]
                setattr(f, ks[0], tp); setattr(f, ks[1], bt); setattr(f, ks[2], sid)
        f.dayId = (t + 4 * 3_600_000) // MS_PER_DAY      # JST (UTC+9) day with the reset at 05:00 JST = UTC + 4 h
        f.brClose, f.brHigh, f.brLow, f.brEval = cl, h, l, True
        out.append((bar, f))
    return out


# ================================================================== version 3 (PF-1)
K_CAT = {CAT_MA: 1, CAT_HZ: 2, CAT_DHL: 3, CAT_ACC: 4}
K_ID = {"SWING_H": 1, "SWING_L": 2, "ACC_HI": 3, "MA1": 4, "MA2": 5, "DAY_HIGH": 6, "DAY_LOW": 7}


class EngineV3(Engine):
    """version 3 = version 2 with PF-1:
    (1) Source codes: each Raw Zone carries integer codes of srcCat / srcId and its srcTf equalities with the six
        configured timeframes (set when the Raw Zone is made / the dynamic slot is filled; recomputed for all Raw Zones if
        a configured timeframe string differs from the one the codes were made with). f_finalizeCluster compares these
        instead of strings, and the Source / HTF masks are summed once from flags (each bit added at most once, as f_setBit).
    (2) Track search: once per bar, before the Zone loop, the Track centers are sorted (sort_indices); each Zone binary-
        searches the centers with |t.center - z.center| <= clusterDist (fl(a - b) is monotone in a, so the matches are one
        contiguous run of the sorted order) and takes the smallest (distance, Track index) among the unmatched continuous
        Tracks = the result of the old index-order scan (strict d < bestD keeps the first index of a tie).
    (3) Track memberUids: copied only when the contents differ (same values in the same order otherwise: the Track keeps
        its own array, never the Zone's)."""
    V3 = True

    def __init__(self, c):
        super().__init__(c)
        self.kTf = NA

    def f_kind(self, z):
        c = self.c
        z.kind = (K_CAT.get(z.srcCat, 0), K_ID.get(z.srcId, 0), z.srcTf == c.hzTf1, z.srcTf == c.hzTf2, z.srcTf == c.hzTf3,
                  z.srcTf == c.accTf1, z.srcTf == c.accTf2, z.srcTf == c.accTf3)

    def f_makeRaw(self, uid, id_, cat, tf, ctr, bs, dyn):
        rz = super().f_makeRaw(uid, id_, cat, tf, ctr, bs, dyn)
        self.f_kind(rz)
        return rz

    def f_pushDyn(self, slot, *a):
        super().f_pushDyn(slot, *a)
        self.f_kind(self.sDynPool[slot])

    def update(self, b, f):
        c = self.c
        sig = (c.hzTf1, c.hzTf2, c.hzTf3, c.accTf1, c.accTf2, c.accTf3)
        if self.kTf != sig:
            for z in self.persist:
                self.f_kind(z)
            self.kTf = sig
        return super().update(b, f)

    def f_finalizeCluster(self, members, zBot, zTop, cDH, cDL):
        c = self.c
        self.n.add("call_finalize")
        self.n.add("alloc_zone")
        self.n.add("alloc_uids")
        baseSum = 0.0; slopeB = 0.0; maB = 0.0
        hasMA = hasHZ = hasDHL = hasACC = False
        swHit1 = swHit2 = swHit3 = False
        swMax = NA
        accHi1 = accLo1 = accHi2 = accLo2 = accHi3 = accLo3 = False
        accA1 = accA2 = accA3 = 0.0
        dsOn = c.dsMerge
        dsTk = p_round(c.dsDist / MINTICK) if dsOn else 0
        dHpx = cDH if dsOn else NA      # the cluster's Day High / Low price from the running aggregate (no pre-scan)
        dLpx = cDL if dsOn else NA
        dHm = dLm = hasDH = hasDL = hzInd = swInd1 = swInd2 = swInd3 = False
        bS1 = bS2 = bS3 = bHx = bA1 = bA2 = bA3 = bM1 = bM2 = bD = False
        hS1 = hS15 = hA1 = hA2 = hA3 = hM1 = hM2 = hD = False
        uids = []
        n = len(members)
        for j in range(n):
            self.n.add("it_finalize")
            m = members[j]
            kc, ki, eH1, eH2, eH3, eA1, eA2, eA3 = m.kind
            isSwing = kc == 2 and (ki == 1 or ki == 2)
            isAccHi = ki == 3
            if isSwing:
                mH = dsOn and ki == 1 and dHpx is not None and (p_round(abs(dHpx - m.px0) / MINTICK) <= dsTk or p_round(abs(dHpx - m.px1) / MINTICK) <= dsTk)
                mL = dsOn and ki == 2 and dLpx is not None and (p_round(abs(dLpx - m.px0) / MINTICK) <= dsTk or p_round(abs(dLpx - m.px1) / MINTICK) <= dsTk)
                sl = 1 if eH1 else 2 if eH2 else 3 if eH3 else 0
                dHm = dHm or mH
                dLm = dLm or mL
                if not mH and not mL:
                    hzInd = True
                    swInd1 = swInd1 or sl == 1
                    swInd2 = swInd2 or sl == 2
                    swInd3 = swInd3 or sl == 3
                if eH1:
                    bS1 = True
                    if not swHit1:
                        swHit1 = True
                        a, swMax = f_swingMaxStep(swMax, c.scoreHz1)
                        baseSum += a
                elif eH2:
                    bS2 = True
                    if not swHit2:
                        swHit2 = True
                        a, swMax = f_swingMaxStep(swMax, c.scoreHz2)
                        baseSum += a
                elif eH3:
                    bS3 = True
                    if not swHit3:
                        swHit3 = True
                        a, swMax = f_swingMaxStep(swMax, c.scoreHz3)
                        baseSum += a
                else:
                    bHx = True
                    baseSum += m.baseScore
            elif kc == 4:
                if eA1:
                    bA1 = True
                    if isAccHi and not accHi1:
                        e = 0.0 if c.accEdgeOnce and accLo1 else m.baseScore
                        accHi1 = True; accA1 += e; baseSum += 0.0 if c.accScoreMax else e
                    elif not isAccHi and not accLo1:
                        e = 0.0 if c.accEdgeOnce and accHi1 else m.baseScore
                        accLo1 = True; accA1 += e; baseSum += 0.0 if c.accScoreMax else e
                elif eA2:
                    bA2 = True
                    if isAccHi and not accHi2:
                        e = 0.0 if c.accEdgeOnce and accLo2 else m.baseScore
                        accHi2 = True; accA2 += e; baseSum += 0.0 if c.accScoreMax else e
                    elif not isAccHi and not accLo2:
                        e = 0.0 if c.accEdgeOnce and accHi2 else m.baseScore
                        accLo2 = True; accA2 += e; baseSum += 0.0 if c.accScoreMax else e
                elif eA3:
                    bA3 = True
                    if isAccHi and not accHi3:
                        e = 0.0 if c.accEdgeOnce and accLo3 else m.baseScore
                        accHi3 = True; accA3 += e; baseSum += 0.0 if c.accScoreMax else e
                    elif not isAccHi and not accLo3:
                        e = 0.0 if c.accEdgeOnce and accHi3 else m.baseScore
                        accLo3 = True; accA3 += e; baseSum += 0.0 if c.accScoreMax else e
                else:
                    baseSum += m.baseScore
            else:
                baseSum += m.baseScore
                if kc == 2:
                    bHx = True
                    hzInd = True
                elif ki == 4:
                    bM1 = True
                elif ki == 5:
                    bM2 = True
                elif kc == 3:
                    bD = True
                    hasDH = hasDH or ki == 6
                    hasDL = hasDL or ki == 7
            slopeB = max(slopeB, m.slopeBonus) if c.slopeBonusMax else slopeB + m.slopeBonus
            maB = max(maB, m.maClusterBonus)
            hS1 = hS1 or (isSwing and eH3 and c.htfSwing1H)
            hS15 = hS15 or (isSwing and eH2 and c.htfSwing15M)
            hA1 = hA1 or (kc == 4 and eA1 and c.htfAccum1H)
            hA2 = hA2 or (kc == 4 and eA2 and c.htfAccum4H)
            hA3 = hA3 or (kc == 4 and eA3 and c.htfAccumD)
            hM1 = hM1 or (ki == 4 and c.htfMa1)
            hM2 = hM2 or (ki == 5 and c.htfMa2)
            hD = hD or (kc == 3 and c.htfDayHL)
            uids.append(m.uid)
            hasMA = hasMA or kc == 1
            hasHZ = hasHZ or kc == 2
            hasDHL = hasDHL or kc == 3
            hasACC = hasACC or kc == 4
        srcM = ((SRC_SW1 if bS1 else 0) + (SRC_SW2 if bS2 else 0) + (SRC_SW3 if bS3 else 0) + (SRC_HZX if bHx else 0)
                + (SRC_ACC1 if bA1 else 0) + (SRC_ACC2 if bA2 else 0) + (SRC_ACC3 if bA3 else 0) + (SRC_MA1 if bM1 else 0)
                + (SRC_MA2 if bM2 else 0) + (SRC_DHL if bD else 0))
        htfM = ((HTF_SW1H if hS1 else 0) + (HTF_ACC1 if hA1 else 0) + (HTF_ACC2 if hA2 else 0) + (HTF_ACC3 if hA3 else 0)
                + (HTF_SW15 if hS15 else 0) + (HTF_MA1 if hM1 else 0) + (HTF_MA2 if hM2 else 0) + (HTF_DAY if hD else 0))
        return self.f_finalizeTail(n, uids, baseSum, slopeB, maB, hasMA, hasHZ, hasDHL, hasACC, swHit1, swHit2, swHit3,
                                   swMax, accA1, accA2, accA3, dsOn, dHm, dLm, hasDH, hasDL, hzInd, swInd1, swInd2,
                                   swInd3, srcM, htfM, zBot, zTop)

    def match_tracks(self, f):
        # the sorted Track centers of this bar (before any match). Matched Tracks (center moved) are skipped by
        # matchedBar; Tracks made in this loop are not in the index and are matched already (old scan skips them too).
        tc = [t.center for t in self.tracks]
        self.n.add("it_trackSortBuild", len(tc))
        self.tOrd = sorted(range(len(tc)), key=lambda i: tc[i])
        self.tC = tc
        super().match_tracks(f)

    def f_findTrack(self, z):
        c, b = self.c, self.b
        ordr, tc = self.tOrd, self.tC
        D = c.clusterDist
        lo, hi = 0, len(ordr)
        while lo < hi:                       # first k with fl(tc - zc) >= -D (monotone in the sorted order)
            self.n.add("it_findTrack")
            mid = (lo + hi) // 2
            if tc[ordr[mid]] - z.center < -D:
                lo = mid + 1
            else:
                hi = mid
        best = -1
        bestD = 1e20
        k = lo
        while k < len(ordr) and tc[ordr[k]] - z.center <= D:
            self.n.add("it_findTrack")
            i = ordr[k]
            t = self.tracks[i]
            if t.matchedBar is None or t.matchedBar != b.i:
                d = abs(t.center - z.center)
                if d <= D and (d < bestD or (d == bestD and i < best)):
                    if self.f_trackContinuous(t, z):
                        bestD = d
                        best = i
            k += 1
        return best

    def new_track(self, z):
        t = super().new_track(z)
        return t

    def set_track_uids(self, t, z):
        a, b = t.memberUids, z.memberUids
        same = len(a) == len(b)
        if same:
            for x, y in zip(a, b):
                self.n.add("it_uidsEq")
                if x != y:
                    same = False
                    break
        if not same:
            self.n.add("alloc_copy")
            t.memberUids = list(b)


def run(eng_cls, F, c, every=1, on_bar=None):
    """run one Engine over the feed; returns the per-bar snapshots (every `every` bars) and the counters."""
    e = eng_cls(c)
    snaps, cnt = [], []
    for bar, f in F:
        e.update(bar, f)
        if bar.i % every == 0:
            snaps.append(e.snap())
        cnt.append(dict(e.n))
        if on_bar:
            on_bar(e, bar)
    return snaps, cnt


MEASURE_KEYS = ("it_findTrack", "call_continuity", "it_includes", "it_finalize", "it_finalize_ds", "it_cluster", "alloc_copy",
                "alloc_zone", "it_regStatic")


def measure(seed=1, days=120, vol=0.8, window=1000, long_cfg=False, bars=None):
    """per-window table for version 2 and version 3 on one SYNTHETIC feed: max Raw Zones / Zones / cluster members / Tracks and the
    per-bar mean / max of the main loop iterations. Returns (rows, totals2, totals3)."""
    c = Cfg(thrStrong=9.0) if long_cfg else Cfg()
    F = build_feed(market1m(seed, days, vol=vol), c)
    if bars:
        F = F[:bars]
    e2, e3 = Engine(c), EngineV3(c)
    rows, cur = [], None
    tot2, tot3 = {}, {}
    for bar, f in F:
        e2.update(bar, f)
        e3.update(bar, f)
        assert e2.snap() == e3.snap(), f"version 2 / 3 differ at bar {bar.i}"
        w = bar.i // window
        if cur is None or cur["w"] != w:
            cur = {"w": w, "from": bar.i, "n": 0}
            rows.append(cur)
        cur["n"] += 1
        cur["to"] = bar.i
        for k in ("persist", "zones", "max_members", "tracks"):
            cur[k] = max(cur.get(k, 0), e2.n.get(k, 0))
        for tag, e, tot in (("v2", e2, tot2), ("v3", e3, tot3)):
            for k in MEASURE_KEYS:
                v = e.n.get(k, 0)
                cur[f"{tag}_{k}_sum"] = cur.get(f"{tag}_{k}_sum", 0) + v
                cur[f"{tag}_{k}_max"] = max(cur.get(f"{tag}_{k}_max", 0), v)
                tot[k] = tot.get(k, 0) + v
    return rows, tot2, tot3


if __name__ == "__main__":
    import sys
    a = dict(arg.split("=") for arg in sys.argv[1:])
    rows, t2, t3 = measure(seed=int(a.get("seed", 1)), days=int(a.get("days", 120)), vol=float(a.get("vol", 0.8)),
                           window=int(a.get("window", 1000)), long_cfg=a.get("cfg", "short") == "long",
                           bars=int(a["bars"]) if "bars" in a else None)
    print("SYNTHETIC feed (not XAUUSD data). per-bar counts of this Python port, version 2 -> version 3 (results equal on every bar)")
    print(f"{'bars':>13} {'raw':>4} {'zones':>5} {'mem':>3} {'trk':>4} | {'findTrack mean/max':>22} | {'includes mean/max':>20} |"
          f" {'finalize(+pre) mean':>20} | {'uid copies':>11}")
    for r in rows:
        n = r["n"]
        g = lambda t, k, s: r[f"{t}_{k}_{s}"] / (n if s == "sum" else 1)
        print(f"{r['from']:>6}-{r['to']:>6} {r['persist'] + 4:>4} {r['zones']:>5} {r['max_members']:>3} {r['tracks']:>4} | "
              f"{g('v2','it_findTrack','sum'):>5.0f}/{g('v2','it_findTrack','max'):>5.0f} -> {g('v3','it_findTrack','sum'):>3.0f}/{g('v3','it_findTrack','max'):>4.0f} | "
              f"{g('v2','it_includes','sum'):>4.0f}/{g('v2','it_includes','max'):>4.0f} -> {g('v3','it_includes','sum'):>3.0f}/{g('v3','it_includes','max'):>4.0f} | "
              f"{g('v2','it_finalize','sum') + g('v2','it_finalize_ds','sum'):>5.0f} -> {g('v3','it_finalize','sum') + g('v3','it_finalize_ds','sum'):>5.0f}    | "
              f"{g('v2','alloc_copy','sum'):>4.0f} -> {g('v3','alloc_copy','sum'):>3.1f}")
    print("totals v2:", {k: t2.get(k, 0) for k in MEASURE_KEYS})
    print("totals v3:", {k: t3.get(k, 0) for k in MEASURE_KEYS})
