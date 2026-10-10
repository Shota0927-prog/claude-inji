"""Integrated ZONE-P Engine model (Python port of ZoneEnginePractical.update + Visual FVG Batch A / C) used by rn1_sim.
Origin: NR-Final audit model. RN-1: `rn_attach` = ZoneEnginePracticalRN f_finalizeCluster Round Number part.
1M path -> 5M chart bars (ticks = 1M closes inside the 5M bar) -> 15M / 1H / 4H / D HTF bars.
Feeds per 5M bar computed by two INDEPENDENT paths:
  hist : TradingView historical semantics (bars complete; lookahead_on [1] -> HTF k-1; lookahead_off -> last HTF with C <= chart close)
  rt   : realtime semantics (data visible at the tick: partial 5M / partial 1M / developing HTF; final tick = confirm)
Engine port of ZoneEnginePractical.update (Practical) + Visual FVG Batch A storage + Batch C display bonus.
Realtime: every non-final tick runs update on a throw-away copy (rollback), the confirm tick commits.
"""
import copy, random, sys, math
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
import practical_zone_sim as pz
import nr_a1_sim as na1

M1, M5, M15, H1, H4, DAY = 60_000, 300_000, 900_000, 3_600_000, 14_400_000, 86_400_000
NA = None

class C(pz.Cfg):
    zoneHalfWidth = 3.0; clusterDist = 5.0
    scoreMa1 = scoreMa2 = 2.0
    slopeThrMod, slopeThrStrong = 1.0, 3.0
    slopeBonusFlat, slopeBonusMod, slopeBonusStr = 0.0, 1.0, 2.0
    maClusterDist, maClusterBonus, maClusterDirBonus = 20.0, 1.0, 1.0
    scoreDayHL = 3.0
    scoreAcc1, scoreAcc2, scoreAcc3 = 3.0, 4.0, 5.0
    accKeep1, accKeep2, accKeep3 = 3, 2, 1
    breakBuffer, flipConfirmDist, resetOnReclaim = 5.0, 10.0, True
    trackStaleBars, trackContinuity = 500, 0.5
    lifeHz1, lifeHz2, lifeHz3 = 5.0, 10.0, 30.0
    maxPersistZones = 200
    touchRearmDist = 10.0
    MA1, MA2, SLB = 300, 450, 60          # scaled MA lengths (1M bars) for the model
    PIV = {"5": 10, "15": 8, "60": 6}

# ---------------------------------------------------------------- data
def market1m(seed, days=14, miss5=0.0):
    rnd = random.Random(seed)
    p, out = 2000.0, []
    t0 = 1_790_000_000_000 // DAY * DAY
    regime, left = 0.0, 0
    for d in range(days):
        if d % 7 in (5, 6):
            continue
        for s5 in range(23 * 12):
            if miss5 and rnd.random() < miss5:
                continue
            for s1 in range(5):
                t = t0 + d * DAY - H1 + s5 * M5 + s1 * M1
                if left <= 0:
                    regime, left = rnd.choice([0.0, 0.0, 0.0, 0.15, -0.15]), rnd.randint(60, 900)
                left -= 1
                q = p + regime + rnd.gauss(0, 0.45)
                out.append((t, p, max(p, q) + abs(rnd.gauss(0, .2)), min(p, q) - abs(rnd.gauss(0, .2)), q))
                p = q
    return out

def agg(bars, key):
    g = {}
    for b in bars:
        g.setdefault(key(b[0]), []).append(b)
    return g

def build(seed, days=14, miss5=0.0):
    b1 = market1m(seed, days, miss5)
    g5 = agg(b1, lambda t: t // M5)
    chart = []
    for k in sorted(g5):
        s = g5[k]
        chart.append(dict(t=k * M5, c_t=k * M5 + M5, subs=s, o=s[0][1], h=max(x[2] for x in s), l=min(x[3] for x in s), c=s[-1][4]))
    b5 = [(c["t"], c["o"], c["h"], c["l"], c["c"]) for c in chart]
    htf = {"15": na1.htf_from_5m(b5, M15), "60": na1.htf_from_5m(b5, H1), "240": na1.htf_from_5m(b5, H4),
           "D": na1.htf_from_5m(b5, None, True)}
    return b1, chart, htf

# ---------------------------------------------------------------- source formulas
def pivot_at(hs, ls, ts, j, n):
    """zn.pivotPack evaluated at bar j of a series (lists include bar j). strict-left / non-strict-right model."""
    ph = pl = pt = lt = NA
    if j - 2 * n >= 0:
        c = j - n
        win = range(j - 2 * n, j + 1)
        if all(hs[c] > hs[i] for i in win if i < c) and all(hs[c] >= hs[i] for i in win if i > c):
            ph, pt = hs[c], ts[j]
        if all(ls[c] < ls[i] for i in win if i < c) and all(ls[c] <= ls[i] for i in win if i > c):
            pl, lt = ls[c], ts[j]
    return ph, pt, pl, lt

def fvg_at(H, j):
    """f_fvgConfirmed body evaluated at HTF bar j (without the [1])."""
    if j < 2:
        return (H[j]["T"], H[j]["C"], NA, 0, NA, NA)
    hi = lambda k: max(s[1] for s in H[k]["subs"]); lo = lambda k: min(s[2] for s in H[k]["subs"])
    bull, bear = lo(j) > hi(j - 2), hi(j) < lo(j - 2)
    top = lo(j) if bull else lo(j - 2) if bear else NA
    bot = hi(j - 2) if bull else hi(j) if bear else NA
    d = (1 if bull else -1) if (bull or bear) and round(top - bot, 2) >= 3.0 else 0
    return (H[j]["T"], H[j]["C"], H[j]["subs"][-1][3], d, top, bot)

def ema_series(xs, n):
    a, out, e = 2 / (n + 1), [], None
    for x in xs:
        e = x if e is None else a * x + (1 - a) * e
        out.append(e)
    return out

# ---------------------------------------------------------------- feeds
class Feeds:
    def __init__(self, b1, chart, htf, swing="nr", start5=0, htf_start=None):
        self.b1, self.chart, self.htf, self.swing = b1, chart, htf, swing
        self.i1 = {}                                   # 5M index -> list of 1M indices
        pos = {b[0]: i for i, b in enumerate(b1)}
        for i, c in enumerate(chart):
            self.i1[i] = [pos[s[0]] for s in c["subs"]]
        self.start5 = start5
        t0 = chart[start5]["t"]
        # reload model: the 1M / HTF contexts also start at the reload point when htf_start == "same"
        b1s = [b for b in b1 if b[0] >= t0] if htf_start == "same" else b1
        self.off1 = len(b1) - len(b1s)
        cl = [b[4] for b in b1s]
        self.ma1, self.ma2 = ema_series(cl, C.MA1), ema_series(cl, C.MA2)
        self.H = {}
        for tf, H in htf.items():
            self.H[tf] = [b for b in H if b["T"] >= t0] if htf_start == "same" else H
        self.acc = {}
        for tf in ("60", "240", "D"):
            com, _ = na1.run_ctx(self.H[tf], "nogate", na1.P)
            self.acc[tf] = com
        self.hidx = {tf: self._index(tf) for tf in self.H}

    def _index(self, tf):
        H, out, k = self.H[tf], [], 0
        for c in self.chart:
            while k + 1 < len(H) and H[k + 1]["T"] <= c["t"]:
                k += 1
            out.append(k if H and H[k]["T"] <= c["t"] < H[k]["C"] else (k if H and H[k]["T"] <= c["t"] else -1))
        return out

    def ma(self, i, j):
        """MA via request(1, lookahead_off): value of the 1M bar that is current at tick j of 5M bar i."""
        k = self.i1[i][j] - self.off1
        if k < 0:
            return NA, NA, NA, NA
        m1, m2 = self.ma1[k], self.ma2[k]
        d1 = m1 - self.ma1[k - C.SLB] if k - C.SLB >= 0 else NA
        d2 = m2 - self.ma2[k - C.SLB] if k - C.SLB >= 0 else NA
        return m1, d1, m2, d2

    def partial5(self, i, j):
        subs = self.chart[i]["subs"][:j + 1]
        return subs[0][1], max(s[2] for s in subs), min(s[3] for s in subs), subs[-1][4]

    def sw1(self, i, j):
        lo = max(self.start5, i - 2 * C.PIV["5"])
        hs = {k: self.chart[k]["h"] for k in range(lo, i)}; ls = {k: self.chart[k]["l"] for k in range(lo, i)}
        _, h, l, _ = self.partial5(i, j)
        hs[i], ls[i] = h, l
        if i - 2 * C.PIV["5"] < self.start5:
            return NA, NA, NA, NA
        H = [hs[k] for k in range(i - 2 * C.PIV["5"], i + 1)]; L = [ls[k] for k in range(i - 2 * C.PIV["5"], i + 1)]
        T = [self.chart[k]["t"] for k in range(i - 2 * C.PIV["5"], i + 1)]
        return pivot_at(H, L, T, len(H) - 1, C.PIV["5"])

    def htf_pivot(self, tf, k, upto_tick=None, i=None, j=None):
        H = self.H[tf]
        if k < 0:
            return NA, NA, NA, NA
        hs = [max(s[1] for s in b["subs"]) for b in H[:k + 1]]
        ls = [min(s[2] for s in b["subs"]) for b in H[:k + 1]]
        ts = [b["T"] for b in H[:k + 1]]
        if upto_tick is not None:                    # developing HTF bar k: only sub-bars up to chart bar i tick j
            sub5 = [s for s in self.chart if H[k]["T"] <= s["t"] <= self.chart[i]["t"]]
            hh = [s["h"] for s in sub5[:-1]] + [self.partial5(i, j)[1]]
            ll = [s["l"] for s in sub5[:-1]] + [self.partial5(i, j)[2]]
            hs[-1], ls[-1] = max(hh), min(ll)
        return pivot_at(hs, ls, ts, k, C.PIV[tf])

    def feed(self, i, j, mode):
        """mode hist: complete bars.  mode rt: tick j of bar i (j = last -> confirm tick)."""
        last = j == len(self.chart[i]["subs"]) - 1
        f = {}
        f["ma"] = self.ma(i, j)
        f["sw1"] = self.sw1(i, j)
        for n, tf in ((2, "15"), (3, "60")):
            k = self.hidx[tf][i]
            if self.swing == "nr":                    # [1] + lookahead_on: HTF k-1, same in hist and rt
                f[f"sw{n}"] = self.htf_pivot(tf, k - 1)
            elif mode == "hist":                      # old lookahead_off, historical: last HTF with C <= chart close
                kk = k if self.H[tf][k]["C"] <= self.chart[i]["c_t"] else k - 1
                f[f"sw{n}"] = self.htf_pivot(tf, kk)
            else:                                     # old lookahead_off, realtime: developing HTF k
                f[f"sw{n}"] = self.htf_pivot(tf, k, True, i, j)
        for n, tf in ((1, "60"), (2, "240"), (3, "D")):
            k = self.hidx[tf][i]
            sid, top, bot = self.acc[tf][k - 1][0] if k >= 1 else (NA, NA, NA)
            f[f"acc{n}"] = (top, bot, sid)
        for n, tf in ((0, "15"), (1, "60"), (2, "240")):
            k = self.hidx[tf][i]
            f[f"fvg{n}"] = fvg_at(self.H[tf], k - 1) if k >= 1 else (NA, NA, NA, 0, NA, NA)
        o, h, l, c = self.partial5(i, j) if mode == "rt" else (self.chart[i]["o"], self.chart[i]["h"], self.chart[i]["l"], self.chart[i]["c"])
        f["ohlc"] = (o, h, l, c)
        conf = last if mode == "rt" else True
        f["br"] = (c, h, l, conf)
        t = self.chart[i]["t"]
        f["day"] = (t + 9 * H1 - 5 * H1) // DAY
        f["time"], f["tclose"], f["conf"] = t, self.chart[i]["c_t"], conf
        return f

def conf(n):
    return C.confBonus4 if n >= 4 else C.confBonus3 if n == 3 else C.confBonus2 if n == 2 else 0.0


def rn_level_in(zBot, zTop, step):
    """port of f_rnLevelIn: multiple of step in [zBot, zTop] nearest the centre, tie -> lower; None if none."""
    k1, k2 = math.ceil(zBot / step), math.floor(zTop / step)
    if k1 > k2:
        return None
    ctr = (zTop + zBot) / 2
    kc = max(k1, min(k2, math.floor(ctr / step)))
    lv = kc * step
    if kc + 1 <= k2 and (kc + 1) * step - ctr < ctr - lv:
        lv = (kc + 1) * step
    return float(lv)


def rn_pick(zBot, zTop, major=(100.0, 3.0), minor=(50.0, 2.0)):
    lv = rn_level_in(zBot, zTop, major[0])
    if lv is not None:
        return lv, major[1]
    lv = rn_level_in(zBot, zTop, minor[0])
    if lv is not None:
        return lv, minor[1]
    return None, 0.0


# ---------------------------------------------------------------- engine (port of update + Visual FVG A / C)
class Raw:
    def __init__(self, uid, srcId, cat, tf, ctr, bs, bar, t):
        self.uid, self.srcId, self.srcCat, self.srcTf = uid, srcId, cat, tf
        self.center, self.top, self.bottom = ctr, ctr + C.zoneHalfWidth, ctr - C.zoneHalfWidth
        self.baseScore, self.slopeBonus, self.maClusterBonus, self.reactionBonus = bs, 0.0, 0.0, 0.0
        self.createdBar, self.createdTime, self.instId, self.expireTime = bar, t, NA, 0

class Track:
    def __init__(self, id_, z, state, bar):
        self.id, self.center, self.top, self.bottom = id_, z["center"], z["top"], z["bottom"]
        self.state, self.lastRole, self.breakDir, self.retested, self.flipped = state, 0, 0, False, False
        self.lastSeenBar, self.matchedBar, self.memberUids = bar, NA, list(z["uids"])
        self.touchCount, self.touchArmed, self.touchActive, self.lastTouchBar, self.wasStrong = 0, True, False, NA, False

def slope_state(d): a = abs(d or 0.0); return 2 if a >= C.slopeThrStrong else 1 if a >= C.slopeThrMod else 0
def slope_dir(d): d = d or 0.0; return 1 if d > 0 else -1 if d < 0 else 0
def slope_val(st): return C.slopeBonusStr if st == 2 else C.slopeBonusMod if st == 1 else C.slopeBonusFlat

class Engine:
    def __init__(self):
        self.persist, self.tracks, self.uid, self.trackSeq = [], [], 0, 0
        self.dayHigh = self.dayLow = self.prevDayHigh = self.prevDayLow = self.prevDayId = NA
        self.dayHighUid = self.dayLowUid = 0
        self.nextPersistExp, self.persistAdded, self.nextTrackExp = NA, False, NA
        self.prev = {}
        self.live = []
        # Visual FVG Batch A storage
        self.fTop, self.fBot, self.fDir = [NA] * 15, [NA] * 15, [0] * 15
        self.fOpen, self.fClose, self.fExp, self.fAlive = [NA] * 15, [NA] * 15, [NA] * 15, [False] * 15
        self.fLast, self.fNext = [NA] * 3, NA
        self.events = []

    def nuid(self):
        self.uid += 1
        return self.uid

    def reg_static(self, trig, price, id_, cat, tf, bs, life, bar, t):
        if trig and price is not NA:
            lm = int(life * DAY)
            for z in self.persist:
                if z.srcId == id_ and z.srcTf == tf and abs(z.center - price) <= C.zoneHalfWidth:
                    if lm > 0:
                        z.expireTime = t + lm
                        self.nextPersistExp = z.expireTime if self.nextPersistExp is NA else min(self.nextPersistExp, z.expireTime)
                    self.events.append(("refresh", id_, tf, price))
                    return
            rz = Raw(self.nuid(), id_, cat, tf, price, bs, bar, t)
            rz.expireTime = t + lm if lm > 0 else 0
            self.persist.append(rz); self.persistAdded = True
            if rz.expireTime > 0:
                self.nextPersistExp = rz.expireTime if self.nextPersistExp is NA else min(self.nextPersistExp, rz.expireTime)
            self.events.append(("new", id_, tf, price))

    def reg_acc(self, trig, price, inst, id_, tf, bs, bar, t):
        if trig and price is not NA and inst is not NA:
            for z in self.persist:
                if z.srcCat == pz.CAT_ACC and z.srcId == id_ and z.srcTf == tf and z.instId == inst:
                    z.center, z.top, z.bottom = price, price + C.zoneHalfWidth, price - C.zoneHalfWidth
                    self.events.append(("accupd", id_, tf, inst, price))
                    return
            rz = Raw(self.nuid(), id_, pz.CAT_ACC, tf, price, bs, bar, t)
            rz.instId = inst
            self.persist.append(rz); self.persistAdded = True
            self.events.append(("accnew", id_, tf, inst, price))

    def prune_gen(self, trig, tf, keep):
        if trig and keep >= 1:
            ids = []
            for z in self.persist:
                if z.srcCat == pz.CAT_ACC and z.srcTf == tf and z.instId not in ids:
                    ids.append(z.instId)
            while len(ids) > keep:
                oldest = min(ids); ids.remove(oldest)
                self.persist = [z for z in self.persist if not (z.srcCat == pz.CAT_ACC and z.srcTf == tf and z.instId == oldest)]
                self.events.append(("accprune", tf, oldest))

    def prune_persist(self, t):
        if self.nextPersistExp is not NA and t > self.nextPersistExp:
            nxt, keep = NA, []
            for z in self.persist:
                if z.expireTime > 0 and t > z.expireTime:
                    self.events.append(("expire", z.srcId, z.srcTf, z.center))
                    continue
                keep.append(z)
                if z.expireTime > 0:
                    nxt = z.expireTime if nxt is NA else min(nxt, z.expireTime)
            self.persist, self.nextPersistExp = keep, nxt
        if self.persistAdded:
            while len(self.persist) > C.maxPersistZones:
                z0 = self.persist[0]
                if z0.srcCat == pz.CAT_ACC:
                    self.persist = [z for z in self.persist if not (z.srcCat == pz.CAT_ACC and z.srcTf == z0.srcTf and z.instId == z0.instId)]
                else:
                    self.persist.pop(0)
        self.persistAdded = False

    def update(self, f, bar):
        self.events = []
        t = f["time"]; o, h, l, c = f["ohlc"]
        new_day = self.prevDayId is NA or f["day"] != self.prevDayId
        if new_day:
            self.prevDayHigh, self.prevDayLow, self.dayHigh, self.dayLow = self.dayHigh, self.dayLow, h, l
        else:
            self.dayHigh = h if self.dayHigh is NA else max(self.dayHigh, h)
            self.dayLow = l if self.dayLow is NA else min(self.dayLow, l)
        if new_day or self.dayHighUid == 0:
            self.dayHighUid, self.dayLowUid = self.nuid(), self.nuid()
        m1, d1, m2, d2 = f["ma"]
        md1, md2, ms1, ms2 = slope_dir(d1), slope_dir(d2), slope_state(d1), slope_state(d2)
        sb = lambda m, dr, st: (slope_val(st) if ((dr > 0 and c > m) or (dr < 0 and c < m)) else 0.0)
        sb1 = 0.0 if m1 is NA else sb(m1, md1, ms1)
        sb2 = 0.0 if m2 is NA else sb(m2, md2, ms2)
        mcb = 0.0
        if m1 is not NA and m2 is not NA and abs(m1 - m2) <= C.maClusterDist:
            mcb = C.maClusterBonus + (C.maClusterDirBonus if md1 != 0 and md1 == md2 else 0.0)
        P = self.prev
        def edge(key, v):
            return v is not NA and (P.get(key) is NA or v != P.get(key))
        n = {}
        for s in (1, 2, 3):
            ph, pt, pl, lt = f[f"sw{s}"]
            n[f"ph{s}"], n[f"pl{s}"] = edge(f"pt{s}", pt), edge(f"lt{s}", lt)
        for s in (1, 2, 3):
            hi, lo, idv = f[f"acc{s}"]
            n[f"ac{s}"] = edge(f"ai{s}", idv) or edge(f"ah{s}", hi) or edge(f"al{s}", lo)
        tfs = {1: "5", 2: "15", 3: "60"}; sc = {1: C.scoreHz1, 2: C.scoreHz2, 3: C.scoreHz3}; lf = {1: C.lifeHz1, 2: C.lifeHz2, 3: C.lifeHz3}
        for s in (1, 2, 3):
            ph, pt, pl, lt = f[f"sw{s}"]
            self.reg_static(n[f"ph{s}"], ph, "SWING_H", pz.CAT_HZ, tfs[s], sc[s], lf[s], bar, t)
            self.reg_static(n[f"pl{s}"], pl, "SWING_L", pz.CAT_HZ, tfs[s], sc[s], lf[s], bar, t)
        atf = {1: "60", 2: "240", 3: "D"}; asc = {1: C.scoreAcc1, 2: C.scoreAcc2, 3: C.scoreAcc3}; kp = {1: C.accKeep1, 2: C.accKeep2, 3: C.accKeep3}
        for s in (1, 2, 3):
            hi, lo, idv = f[f"acc{s}"]
            self.reg_acc(n[f"ac{s}"], hi, idv, "ACC_HI", atf[s], asc[s], bar, t)
            self.reg_acc(n[f"ac{s}"], lo, idv, "ACC_LO", atf[s], asc[s], bar, t)
        for s in (1, 2, 3):
            self.prune_gen(n[f"ac{s}"], atf[s], kp[s])
        self.prune_persist(t)
        dyn = []
        def pdyn(uid, id_, cat, tf, ctr, bs, slB, mcB):
            r = Raw(uid, id_, cat, tf, ctr, bs, bar, t); r.slopeBonus, r.maClusterBonus = slB, mcB; dyn.append(r)
        if m1 is not NA: pdyn(-1, "MA1", pz.CAT_MA, "1", m1, C.scoreMa1, sb1, mcb)
        if m2 is not NA: pdyn(-2, "MA2", pz.CAT_MA, "1", m2, C.scoreMa2, sb2, mcb)
        if self.dayHigh is not NA: pdyn(self.dayHighUid, "DAY_HIGH", pz.CAT_DHL, "D", self.dayHigh, C.scoreDayHL, 0.0, 0.0)
        if self.dayLow is not NA: pdyn(self.dayLowUid, "DAY_LOW", pz.CAT_DHL, "D", self.dayLow, C.scoreDayHL, 0.0, 0.0)
        cl = pz.practical_build(self.persist, dyn, C)
        allr = {r.uid: r for r in self.persist + dyn}
        for z in cl:
            z["catCount"] = len({allr[u].srcCat for u in z["uids"]})
            z["rnLevel"], z["rnBase"], z["rnScoreDelta"], z["rnBaseSumExRn"] = None, 0.0, 0.0, z["baseSum"]
            if getattr(self, "rn_attach", False):          # RN-1 (ZoneEnginePracticalRN f_finalizeCluster)
                lv, b = rn_pick(z["bottom"], z["top"])
                if b > 0:
                    z["rnLevel"], z["rnBase"] = lv, b
                    z["baseSum"] += b
                    c0 = conf(z["catCount"])
                    z["catCount"] += 1
                    z["confB"] = conf(z["catCount"])
                    z["rnScoreDelta"] = b + (z["confB"] - c0)
        bc, bh, bl, ev = f["br"]
        for z in cl:
            best, bestD = -1, 1e20
            for ti, tr in enumerate(self.tracks):
                if tr.matchedBar is NA or tr.matchedBar != bar:
                    d = abs(tr.center - z["center"])
                    if d <= C.clusterDist and d < bestD:
                        ov = len([u for u in z["uids"] if u in tr.memberUids]); mx = max(len(z["uids"]), len(tr.memberUids))
                        if ov >= 1 and mx > 0 and ov / mx >= C.trackContinuity:
                            best, bestD = ti, d
            if best >= 0:
                tr = self.tracks[best]
            else:
                self.trackSeq += 1
                tr = Track(self.trackSeq, z, pz.natural_state(z["top"], z["bottom"], c), bar)
                self.tracks.append(tr)
                eb = bar + C.trackStaleBars + 1
                self.nextTrackExp = eb if self.nextTrackExp is NA else min(self.nextTrackExp, eb)
            tr.matchedBar, tr.center, tr.top, tr.bottom, tr.lastSeenBar, tr.memberUids = bar, z["center"], z["top"], z["bottom"], bar, list(z["uids"])
            e = pz.update_track(tr, C, ev, bc, bh, bl, c, bar)
            if e:
                self.events.append(("trk", tr.id, e))
            z["state"], z["flipBonus"], z["trackId"] = tr.state, (C.flipBonus if tr.flipped else 0.0), tr.id
            z["score"] = z["baseSum"] + z["slopeB"] + z["maB"] + z["flipBonus"] + z["confB"]
            z["strength"] = pz.strength_of(z["score"], z["hasHtf"], C)
            z["touch"] = pz.update_touch(tr, z["strength"], h, l, bar, C)
        if self.nextTrackExp is not NA and bar >= self.nextTrackExp:
            nxt, keep = NA, []
            for tr in self.tracks:
                if bar - tr.lastSeenBar > C.trackStaleBars:
                    continue
                keep.append(tr); eb = tr.lastSeenBar + C.trackStaleBars + 1
                nxt = eb if nxt is NA else min(nxt, eb)
            self.tracks, self.nextTrackExp = keep, nxt
        self.prevDayId = f["day"]
        for s in (1, 2, 3):
            ph, pt, pl, lt = f[f"sw{s}"]; P[f"pt{s}"], P[f"lt{s}"] = pt, lt
            hi, lo, idv = f[f"acc{s}"]; P[f"ai{s}"], P[f"ah{s}"], P[f"al{s}"] = idv, hi, lo
        self.live = cl
        # ---- Visual FVG Batch A (confirmed 5M bars only)
        if f["conf"]:
            now = f["tclose"]
            if self.fNext is not NA and now >= self.fNext:
                nx = NA
                for s in range(15):
                    if self.fAlive[s]:
                        if now >= self.fExp[s]:
                            self.fAlive[s] = False; self.events.append(("fvgexp", s))
                        else:
                            nx = self.fExp[s] if nx is NA else min(nx, self.fExp[s])
                self.fNext = nx
            for ti, life in ((0, 72), (1, 168), (2, 336)):
                key, closeT, hc, dr, top, bot = f[f"fvg{ti}"]
                r = self.fvg_event(ti, key, closeT, hc, dr, top, bot, life * H1, now)
                self.fNext = self.fNext if r is NA else (r if self.fNext is NA else min(self.fNext, r))
        return len(cl)

    def fvg_event(self, ti, key, closeT, hc, dr, top, bot, life, now):
        reg = NA
        last = self.fLast[ti]
        if key is not NA and (last is NA or key != last):
            base = ti * 5
            for s in range(base, base + 5):
                if self.fAlive[s] and self.fOpen[s] < key:
                    d = self.fDir[s]
                    if (d == 1 and hc is not NA and hc < self.fBot[s]) or (d == -1 and hc is not NA and hc > self.fTop[s]):
                        self.fAlive[s] = False; self.events.append(("fvgfill", s))
            if dr != 0 and closeT is not NA and now < closeT + life:
                slot = oldest = -1
                for s in range(base, base + 5):
                    if not self.fAlive[s]:
                        if slot < 0: slot = s
                    elif oldest < 0: oldest = s
                    elif self.fOpen[s] < self.fOpen[oldest]: oldest = s
                if slot < 0: slot = oldest
                self.fTop[slot], self.fBot[slot], self.fDir[slot], self.fOpen[slot], self.fClose[slot] = top, bot, dr, key, closeT
                self.fExp[slot], self.fAlive[slot] = closeT + life, True
                reg = closeT + life
                self.events.append(("fvgnew", ti, key))
            self.fLast[ti] = key
        return reg

    # Batch C display (read-only)
    def display(self):
        out = []
        for z in self.live:
            best = -1
            for s in range(15):
                if self.fAlive[s] and min(z["top"], self.fTop[s]) > max(z["bottom"], self.fBot[s]):
                    if best < 0 or s // 5 > best // 5 or (s // 5 == best // 5 and self.fClose[s] > self.fClose[best]):
                        best = s
            ds, dst = z["score"], z["strength"]
            if best >= 0:
                cb = lambda n: C.confBonus4 if n >= 4 else C.confBonus3 if n == 3 else C.confBonus2 if n == 2 else 0.0
                ds = z["baseSum"] + (best // 5 + 1.0) + z["slopeB"] + z["maB"] + z["flipBonus"] + cb(z["catCount"] + 1)
                dst = pz.strength_of(ds, z["hasHtf"], C)
            out.append((round(ds, 9), dst))
        return out

    def snap(self, with_ids=True):
        rz = sorted((r.srcId, r.srcTf, round(r.center, 9), r.instId, r.expireTime) + ((r.uid,) if with_ids else ()) for r in self.persist)
        zs = [(round(z["top"], 9), round(z["bottom"], 9), z["state"], round(z["score"], 9), z["strength"], z["touch"])
              + ((z["trackId"], tuple(z["uids"])) if with_ids else ()) for z in self.live]
        trk = sorted((t.state, t.breakDir, t.retested, t.flipped, t.touchCount) + ((t.id,) if with_ids else ()) for t in self.tracks)
        fv = tuple(sorted((s // 5, self.fTop[s], self.fBot[s], self.fOpen[s]) for s in range(15) if self.fAlive[s]))
        ev = [e for e in self.events if with_ids or e[0] not in ("trk",)]
        return dict(raw=rz, zones=zs, n=len(zs), tracks=trk, fvg=fv, disp=self.display(), ev=ev)

def run(F, mode, start5=0, intrabar=False, with_ids=True):
    E, snaps, var = Engine(), {}, 0
    for i in range(start5, len(F.chart)):
        bar = i - start5
        nt = len(F.chart[i]["subs"])
        if mode == "hist":
            f = F.feed(i, nt - 1, "hist")
        else:
            if intrabar:
                for j in range(nt - 1):           # unconfirmed ticks: rollback (throw-away copy)
                    E2 = copy.deepcopy(E); E2.update(F.feed(i, j, "rt"), bar)
                    s2 = E2.snap(with_ids); var += s2["zones"] != None
            f = F.feed(i, nt - 1, "rt")
        E.update(f, bar)
        snaps[i] = (E.snap(with_ids), f)
    return snaps
