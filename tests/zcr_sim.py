"""ZCR-2 checks — ZoneConfluenceReactionStatsXAU.pine.   python3 tests/zcr_sim.py [random-seeds]

Runs the "ZCR Logic" section of the indicator itself (mechanical Pine-subset -> Python translation by tests/acc_pine.py,
unchanged) on synthetic confirmed 5m bars. Everything request.* / input.source would deliver is given per 5m bar: the EMA of
the previous bar (zbP1 / zbP5), the higher-TF feeds of ZA (f{k}u/l/i/a), ZC (s{k}h/ht/l/lt), ZD (zd{L,U,T}{k}), ZF
(g{k}k/kc/c/d/t/b), ZG (zgPk1 / zgPk4 / zgPkD strings) and the LongFibWave connection outputs of ZE (zeProto, ze4*, zeD*).

  S. static: copied detection code and the Lab's whole registration block (ZA / ZC / ZD / ZE / ZF / ZG) == their source byte for
     byte (the block only re-indented), requests (count, lookahead, tuple total <= 127), plots <= 64, zone input defaults == the
     Lab's, no strategy / alert, no lower-TF request, continuation indents, only new files in git status
  A. fixed cases of the instruction (S8 on 5m bars + R1 / R4 / R5), T. each of the 7 zone kinds: registration -> touch -> event
  C. random paths vs an independent oracle written from the spec (its own registration of all 7 kinds, places by the R4 rule,
     per-zone contact state, every event evaluated afterwards from the later bars): events, evidence sets, direction,
     suppression / departure / re-contact, 9 conditions and times, MFE / MAE, pre-reach adverse range, short / unmeasurable /
     pending windows, exact-match rows, summary rows, FIFO output
  K. causality: a run on the first half == the first half of the full run, also when the second half is replaced
  X. mutations of the logic that the oracle comparison must catch

Evidence class: PINE_NOT_VERIFIED (no TradingView compiler / replay here; request.* semantics are not reproduced).
"""
import copy
import math
import os
import random
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import acc_pine as ap     # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PINE = os.path.join(ROOT, "ZoneConfluenceReactionStatsXAU.pine")
LAB = os.path.join(ROOT, "ZoneComboLabXAU.pine")
FEED = os.path.join(ROOT, "MtfPocFeedXAU.pine")
BEGIN, END = "// ==== ZCR Logic (begin) ", "// ==== ZCR Logic (end) "
M1, M5 = 60_000, 300_000
T0 = 1_767_574_800_000          # 2026-01-05 01:00 UTC
MT = 0.01
NS, NF = 21, 36
START0 = 1_577_836_800_000      # 2020-01-01 00:00 UTC (the default of the start input)
ZE_KEYS = ["zeProto"] + [f"ze{k}{x}" for k in ("4", "D") for x in "OEDIST"]
FEEDS = ([f"f{k}{x}" for k in (1, 2, 3) for x in "ulia"] + [f"s{k}{x}" for k in (1, 2, 3, 4) for x in ("h", "ht", "l", "lt")]
         + [f"zd{x}{k}" for k in (1, 2, 3, 4) for x in "LUT"] + [f"g{k}{x}" for k in (1, 2, 3, 4) for x in ("k", "kc", "c", "d", "t", "b")]
         + ["zgPk1", "zgPk4", "zgPkD"] + ZE_KEYS)
GN = ["ZA-1H", "ZA-4H", "ZA-D", "ZB-1m", "ZB-5m", "ZC-1H", "ZC-4H", "ZC-D", "ZC-W", "ZD-1H", "ZD-4H", "ZD-D", "ZD-W",
      "ZE-4H", "ZE-D", "ZF-1H", "ZF-4H", "ZF-D", "ZF-W", "ZG-1H", "ZG-4H", "ZG-D"]
G = {n: 1 << i for i, n in enumerate(GN)}
RATIOS = (0.236, 0.382, 0.5, 0.618)
EPS = 1e-7
RESULTS = []
COVER = {}


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


def read(p):
    return open(p, encoding="utf-8").read()


def logic(s):
    i = s.index(BEGIN)
    return s[s.index("\n", i) + 1:s.index(END)]


def tk(x):
    return math.floor(x / MT + 0.5)


def ticks(usd):
    return max(1, math.ceil(usd / MT - 1e-9))


def tonum(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


ALL_ON = {"zaUse1": True, "zcUse1": True, "zcUse2": True, "zdUse1": True, "zfUse1": True, "zfUse2": True, "zfUse3": True, "zfUse4": True}
OFF = {"zaUse2": False, "zaUse3": False, "zbUse1": False, "zbUse2": False, "zcUse3": False, "zcUse4": False, "zdUse2": False, "zdUse3": False,
       "zdUse4": False, "zeUse": False, "zgUse1": False, "zgUse4": False, "zgUseD": False}
ONLY_ZC = dict(OFF, zcUse1=True, zcUse2=True, zcUse3=True, zcUse4=True)


class Runner:
    """bars: dicts t (5m open time), tc (default t + 5m), o, h, l, c, p1 / p5 (EMA of the previous confirmed bar), feeds by name
    (missing = na), conf (False = an unconfirmed realtime update)."""

    def __init__(self, overrides=None, source=None, run=True, maxrow=1_000_000):
        s = source if source is not None else read(PINE)
        cap = "int   ZC_MAXROW = 300 "          # the row cap of the indicator; the tests lift it unless a case is about the cap
        assert s.count(cap) == 1, "ZC_MAXROW declaration changed"
        s = s.replace(cap, f"int   ZC_MAXROW = {maxrow} ")
        self.code = compile(ap.Translator().translate(ap.logical_lines(logic(s))), "<ZCR logic>", "exec")
        inp = ap.inputs(s)
        inp.setdefault("zcStart", START0)        # input.time is not parsed by ap.inputs
        for k in (overrides or {}):
            if k not in inp:
                raise KeyError(k)
        if "zcWarm" not in (overrides or {}):
            inp["zcWarm"] = 0                    # the tests count from the first bar unless a case sets the warm-up
        inp.update(overrides or {})
        self.inp = inp
        env = ap.make_env(ap.Broker(), [])

        def _insert(arr, i, v):
            if i is None or i < 0 or i > len(arr):
                raise ap.PineRuntimeError("array.insert out of bounds")
            arr.insert(i, v)
        env.update(inp)
        env.update(array__new=lambda n=0, v=None: [v] * n, array__insert=_insert, math__ceil=math.ceil,
                   array__indexof=lambda arr, v: arr.index(v) if v in arr else -1, array__includes=lambda arr, v: v in arr,
                   str__split=lambda s, sep: s.split(sep), str__tonumber=tonum, zdProto=10001,
                   syminfo__mintick=MT, hlRun=run, _VARS=set(), _VARIPS=set(), __first__=True)
        self.env = env
        self.bar_index = -1
        self.out = []          # (bar_index, record) of every bar with an output
        self.created = []      # (bar_index, T0, top, bot, d, n) from the per-bar draw arrays

    def step(self, b):
        conf = b.get("conf", True)
        idx = self.bar_index + 1
        if conf:
            self.bar_index = idx
        e = self.env
        e.update(time=b["t"], time_close=b.get("tc", b["t"] + M5), bar_index=idx, barstate__isconfirmed=conf, open=b["o"], high=b["h"],
                 low=b["l"], close=b["c"], zbP1=b.get("p1"), zbP5=b.get("p5"))
        for f in FEEDS:
            e[f] = b.get(f)
        exec(self.code, e)
        e["__first__"] = False
        if e["zcOut"][0] is not None:
            self.out.append((idx, list(e["zcOut"])))
        for i in range(len(e["zcEvT"])):
            self.created.append((idx, e["zcEvT"][i], e["zcEvTop"][i], e["zcEvBot"][i], e["zcEvD"][i], e["zcEvN"][i]))
        return self

    def run(self, bars):
        for b in bars:
            self.step(b)
        return self

    def __getitem__(self, k):
        return self.env[k]

    def records(self):
        return [r for _, r in self.out] + [list(q.v) for q in self.env["zcQ"]]

    def pending(self):
        return [dict(id=o.id, t0=o.t0, p0=o.p0, d=o.d, mask=o.mask, nEv=o.nEv, nRaw=o.nRaw, og=o.og, rTop=o.rTop, rBot=o.rBot, edge=o.edge,
                     cPos=o.cPos, ord=o.ord, nPl=o.nPl, aux=o.aux, flags=o.flags, onMask=o.onMask, rmin=list(o.rMin), alo=list(o.aLo), ahi=list(o.aHi),
                     wst=list(o.wSt), wmfe=list(o.wMfe), wmae=list(o.wMae), wnb=list(o.wNb)) for o in self.env["zcPend"]]

    def rows(self):
        e = self.env
        return {m: (list(r.c), list(r.hist), list(r.ev)) for m, r in zip(e["zrMask"], e["zrRow"])}

    def sums(self):
        return [(list(r.c), list(r.hist), list(r.ev)) for r in self.env["zrSum"]]

    def zones(self):
        return sorted((q.gid, q.sub, q.tb, q.tt, q.inv) for q in self.env["zxZ"])

    def state(self):
        e = self.env
        z = e["st"]
        return dict(nEv=z.nEv, nEv2=z.nEv2, nUnk=z.nUnk, nCont=z.nCont, nDone=z.nDone, nOut=z.nOut, nBad=z.nBad, nMa1Ev=z.nMa1Ev, nMa5Ev=z.nMa5Ev, nZeEv=z.nZeEv,
                    nEvOn=z.nEvOn, nMultiBar=z.nMultiBar, nPre=z.nPre,
                    nIfvg=z.nIfvg, nFvgDead=z.nFvgDead, maUnk=list(e["zcMaUnk"]), nZone=list(e["zcNZone"]), why=list(e["zcWhy"][:2]),
                    on=sorted((q.gid, q.tb, q.tt) for q in e["zcOn"]), act=self.zones(), zeBad=list(e["zcZeBad"]), zdBad=list(e["zcZdBad"]),
                    zeStat=list(e["lbZeStat"]), zdStat=list(e["lbZdStat"]))

    def snapshot(self):
        return copy.deepcopy(dict(rec=self.records(), pend=self.pending(), rows=self.rows(), sums=self.sums(), st=self.state(),
                                  out=[(i, r) for i, r in self.out], created=list(self.created)))


# ----------------------------------------------------------------------------------------------------------------
# synthetic data
def bar(i, o, h, l, c, **kv):
    assert l <= min(o, c) and h >= max(o, c), (i, o, h, l, c)
    d = dict(t=T0 + i * M5, o=o, h=h, l=l, c=c)
    d.update(kv)
    return d


def bars_from_rows(rows, feeds0=None, start=4350.0, feeds=None, hold=True):
    """5m bar 0 = a flat bar at `start` carrying feeds0 (zones registered there are usable from bar 1); rows = (o, h, l, c) of the
    bars from bar 1 on. feeds = {bar index: feed dict} for later bars. hold: a feed stays as delivered until replaced."""
    cur = dict(feeds0 or {})
    out = [bar(0, start, start, start, start, **cur)]
    for n, r in enumerate(rows, start=1):
        if n in (feeds or {}):
            if hold:
                cur.update(feeds[n])
            else:
                cur = dict(feeds[n])
        out.append(bar(n, *r, **cur))
    return out


def zc(tf, side, price, key=None):
    """ZC pivot feed: tf 0 1H / 1 4H / 2 D / 3 W, side 1 high / -1 low"""
    k = tf + 1
    key = T0 - 86_400_000 * (tf + 1) - (0 if side == 1 else 1) if key is None else key
    return {f"s{k}{'h' if side == 1 else 'l'}": price, f"s{k}{'ht' if side == 1 else 'lt'}": key}


def zd(tf, center, t=None, half=0.5):
    k = tf + 1
    return {f"zdL{k}": round(center - half, 2), f"zdU{k}": round(center + half, 2), f"zdT{k}": float(T0 - 3_600_000 if t is None else t)}


def za(tf, up, lo, aid, forming=0):
    k = tf + 1
    return {f"f{k}u": up, f"f{k}l": lo, f"f{k}i": aid, f"f{k}a": forming}


def ze(tf, o, e, d, wid, state=3, t=None, proto=20001):
    k = "4" if tf == 0 else "D"
    return {"zeProto": proto, f"ze{k}O": o, f"ze{k}E": e, f"ze{k}D": d, f"ze{k}I": wid, f"ze{k}S": state, f"ze{k}T": float(T0 - M5 if t is None else t)}


def zf(tf, key, hc, d=0, top=None, bot=None):
    k = tf + 1
    return {f"g{k}k": key, f"g{k}kc": key + 1, f"g{k}c": hc, f"g{k}d": d, f"g{k}t": top, f"g{k}b": bot}


def zg_blk(t, tc, bi, dets=()):
    """one block of the detector output: "B,time,time_close,prev time,bases,bar_index" + detection events (D: id, side -1 top / 1 bottom,
    count at field 7, zone base price at field 16)"""
    s = f"B,{t},{tc},0,0,{bi}"
    for zid, side, cnt, price in dets:
        s += f";D,{zid},{side},0,0,0,0,{cnt},0,0,0,0,0,0,0,0,{price}"
    return s


def zg(tf, *blks):
    return {("zgPk1", "zgPk4", "zgPkD")[tf]: ";".join(blks)}


def merge(*ds):
    out = {}
    for d in ds:
        out.update(d)
    return out


def flat(p, n):
    return [(p, p, p, p)] * n


# ----------------------------------------------------------------------------------------------------------------
# C. independent oracle (from the spec)
def bar_bad(b):
    v = [b["o"], b["h"], b["l"], b["c"]]
    return any(x is None for x in v) or b["h"] < max(b["o"], b["c"]) or b["l"] > min(b["o"], b["c"])


# auxiliary bits by evidence ID and side: ZA upper 19-21 / lower 22-24, ZC high 25-28 / low 29-32, ZG top 33-35 / bottom 36-38
AUX0 = {}
for _k in range(3):
    AUX0[_k] = (lambda k: lambda sub: 1 << ((19 if sub == 1 else 22) + k))(_k)
    AUX0[19 + _k] = (lambda k: lambda sub: 1 << ((33 if sub == 1 else 36) + k))(_k)
for _k in range(4):
    AUX0[5 + _k] = (lambda k: lambda sub: 1 << ((25 if sub == 1 else 29) + k))(_k)


def places_of(touched, l, h):
    """maximal sets of touched zones sharing a price point inside [l, h] (brute force: the zone sets at every end point of the
    clipped bands, those not contained in another one). Returns [(members, c_lo, c_hi)] by price, low to high."""
    pts = sorted(set([max(z["lo"], l) for z in touched] + [min(z["hi"], h) for z in touched]))
    sets = []
    for x in pts:
        ids = frozenset(z["id"] for z in touched if z["lo"] <= x <= z["hi"])
        if ids and ids not in sets:
            sets.append(ids)
    out = []
    for a in sets:
        if any(a < b for b in sets):
            continue
        mem = [z for z in touched if z["id"] in a]
        out.append((mem, max(max(z["lo"] for z in mem), l), min(min(z["hi"] for z in mem), h)))
    return sorted(out, key=lambda x: x[1])


def oracle(bars, prm):
    P = prm
    W = [ticks(5.0), ticks(10.0), ticks(15.0)]
    dep_t, dep_ms = ticks(P["zcDepW"]), P["zcDepMin"] * M1
    zh = P["zHalf"]
    za_use = [P["zaUse1"], P["zaUse2"], P["zaUse3"]]
    za_keep = [P["zaKeep1"], P["zaKeep2"], P["zaKeep3"]]
    zb_use = [P["zbUse1"], P["zbUse2"]]
    zc_use = [P["zcUse1"], P["zcUse2"], P["zcUse3"], P["zcUse4"]]
    zd_use = [P["zdUse1"], P["zdUse2"], P["zdUse3"], P["zdUse4"]]
    ze_use = [P["zeUse"] and P["zeUse4"], P["zeUse"] and P["zeUseD"]]
    zf_use = [P["zfUse1"], P["zfUse2"], P["zfUse3"], P["zfUse4"]]
    zg_use = [P["zgUse1"], P["zgUse4"], P["zgUseD"]]
    zg_exp = [(P["zgExp1"], P["zgExpN1"]), (P["zgExp4"], P["zgExpN4"]), (P["zgExpD"], P["zgExpND"])]
    seq = [0]
    zones = []

    def mk(gid, sub, lo, hi, **kw):
        seq[0] += 1
        z = dict(id=seq[0], gid=gid, sub=sub, flo=lo, fhi=hi, lo=None if lo is None else tk(lo), hi=None if hi is None else tk(hi),
                 on=False, outT=None, inv=False, aux=AUX0.get(gid, lambda s_: 0)(sub), ma=False)
        z.update(kw)
        return z
    ma = [mk(3, 0, None, None, ma=True, ok=False), mk(4, 0, None, None, ma=True, ok=False)]
    n_zone = [0] * 22

    def add(z, old=None):
        """old = the zone it replaces: the contact state carries over only if that zone was in contact and the bands overlap"""
        zones.append(z)
        n_zone[z["gid"]] += 1
        if old is not None and old["on"] and z["hi"] >= old["lo"] and z["lo"] <= old["hi"]:
            z["on"] = True
        return z

    def drop(z):
        zones[:] = [q for q in zones if q is not z]

    acc_last, forming, acc_boxes = [None] * 3, [], [[], [], []]
    piv_last, sw = {}, [[], [], [], []]
    poc_last, poc_cur = [None] * 4, [None] * 4
    ze_cur = [None, None]            # adopted wave (o, e, d, id) per TF
    ze_zone = [[], []]
    ze_stat, zd_stat = [0, 0], [0] * 4
    fvg_last = [None] * 4
    zg_last, zg_used, n_ifvg, n_fdead = [None] * 3, set(), [0], [0]
    ze_bad, zd_bad = [0, 0], [0] * 4

    def fix(k, box):
        zs_ = [add(mk(k, 1, box["up"] - zh, box["up"] + zh)), add(mk(k, -1, box["lo"] - zh, box["lo"] + zh))]
        acc_boxes[k].append(zs_)
        while len(acc_boxes[k]) > za_keep[k]:
            for z in acc_boxes[k].pop(0):
                drop(z)

    def register(b, bi):
        tc = b.get("tc", b["t"] + M5)
        # ZA: a new id fixes what was still forming on that TF; the same id updates the forming box and fixes it when forming ends
        for k in range(3):
            u, l, aid, a = (b.get(f"f{k + 1}{x}") for x in "ulia")
            if za_use[k] and aid is not None and u is not None and l is not None:
                if acc_last[k] is None or aid != acc_last[k]:
                    acc_last[k] = aid
                    for q in [q for q in reversed(forming) if q["tf"] == k]:
                        fix(k, q)
                        forming.remove(q)
                    box = dict(tf=k, aid=aid, up=u, lo=l)
                    if a == 1:
                        forming.append(box)
                    else:
                        fix(k, box)
                else:
                    for q in [q for q in reversed(forming) if q["tf"] == k and q["aid"] == aid]:
                        q["up"], q["lo"] = u, l
                        if a != 1:
                            fix(k, q)
                            forming.remove(q)
        # ZC: a pivot whose time key differs from the last one of that TF / side is a new line (its own band)
        for k in range(4):
            if zc_use[k]:
                for sd, (pk, kk) in enumerate(((f"s{k + 1}h", f"s{k + 1}ht"), (f"s{k + 1}l", f"s{k + 1}lt"))):
                    pv, pt = b.get(pk), b.get(kk)
                    if pv is not None and pt is not None and piv_last.get((k, sd)) != pt:
                        piv_last[(k, sd)] = pt
                        sw[k].append(add(mk(5 + k, 1 if sd == 0 else -1, pv - zh, pv + zh)))
                        if P["zcMax"] > 0:
                            while len(sw[k]) > P["zcMax"]:
                                drop(sw[k].pop(0))
        # ZD: a normal POC whose centre differs from the last valid one replaces that TF's POC (the successor inherits the contact state)
        for k in range(4):
            stt = 0
            if zd_use[k]:
                lo, up, tt = b.get(f"zdL{k + 1}"), b.get(f"zdU{k + 1}"), b.get(f"zdT{k + 1}")
                if tt is None:
                    stt = 3
                elif tt == 0:
                    stt = 8
                elif abs(tt) < 1e11 or abs(tt) >= b["t"] or tt != round(tt):
                    stt = 9
                elif tt < 0:
                    stt = 2
                elif lo is None or up is None or up <= lo:
                    stt = 9
                else:
                    stt = 1
                    cen = (lo + up) / 2.0
                    if poc_last[k] is None or cen != poc_last[k]:
                        poc_last[k] = cen
                        if poc_cur[k] is not None:
                            drop(poc_cur[k])
                        poc_cur[k] = add(mk(9 + k, 0, cen - zh, cen + zh), old=poc_cur[k])
                if stt != 1:
                    zd_bad[k] += 1
            zd_stat[k] = stt
        # ZE: the newest wave of LongFibWave per TF -> 4 levels; an unconnected / inconsistent feed (9) keeps the zones
        for k, nm in enumerate(("4", "D")):
            stt = 0
            if ze_use[k]:
                fo, fe, fd, fi, fs, ft = (b.get(f"ze{nm}{x}") for x in "OEDIST")
                isint = lambda x: x == round(x)      # noqa: E731
                if b.get("zeProto") != 20001:
                    stt = 9
                elif fs is None or fi is None or ft is None or fd is None:
                    stt = 9
                elif not isint(fs) or fs < 0 or fs > 3 or not isint(fi) or fi < 0:
                    stt = 9
                elif abs(ft) < 1e11 or ft > tc or not isint(ft):
                    stt = 9
                elif fs == 3:
                    stt = 9 if (fo is None or fe is None or fo == fe or fd not in (1, -1)) else 1
                else:
                    stt = 9 if (fo is not None or fe is not None or fd != 0) else {0: 8, 1: 2, 2: 3}[fs]
                if stt == 1:
                    if ze_cur[k] != (fo, fe, fd, fi):
                        was = {z["lv"]: z for z in ze_zone[k]}
                        for z in ze_zone[k]:
                            drop(z)
                        ze_zone[k] = []
                        for j, r in enumerate(RATIOS):
                            p = fe + r * (fo - fe)
                            ze_zone[k].append(add(mk(13 + k, int(fd), p - zh, p + zh, lv=j, aux=1 << (k * 4 + j)), old=was.get(j)))
                        ze_cur[k] = (fo, fe, fd, fi)
                elif stt in (2, 3, 8):
                    for z in ze_zone[k]:
                        drop(z)
                    ze_zone[k] = []
                    ze_cur[k] = None
                if stt == 9:
                    ze_bad[k] += 1
            ze_stat[k] = stt
        # ZF: on a new higher-TF bar (key) the older FVGs of that TF are judged by its confirmed close, then the new FVG is added
        for k in range(4):
            key = b.get(f"g{k + 1}k")
            if zf_use[k] and key is not None and key != fvg_last[k]:
                fvg_last[k] = key
                hc = b.get(f"g{k + 1}c")
                if hc is not None:
                    for z in [z for z in zones if 15 <= z["gid"] <= 18 and z["gid"] == 15 + k and z["key"] < key]:
                        if not z["inv"]:
                            if (z["sub"] == 1 and hc < z["flo"]) or (z["sub"] == -1 and hc > z["fhi"]):
                                z["inv"] = True
                                n_ifvg[0] += 1
                        elif (z["sub"] == 1 and hc > z["fhi"]) or (z["sub"] == -1 and hc < z["flo"]):
                            drop(z)
                            n_fdead[0] += 1
                gd, gt, gb = b.get(f"g{k + 1}d"), b.get(f"g{k + 1}t"), b.get(f"g{k + 1}b")
                if gd is not None and gd != 0 and gt is not None and gb is not None:
                    add(mk(15 + k, gd, gb, gt, key=key))
        # ZG: blocks of confirmed target bars not taken yet; a block first expires zones by the TF bar count, then its detections fire
        for k, nm in enumerate(("zgPk1", "zgPk4", "zgPkD")):
            pk = b.get(nm)
            if pk:
                take, cbi = False, None
                for e in pk.split(";"):
                    if not e:
                        continue
                    f = e.split(",")
                    if f[0] == "B":
                        s_t, s_c = tonum(f[1]), tonum(f[2])
                        take = s_t is not None and (zg_last[k] is None or s_t > zg_last[k]) and s_c is not None and s_c <= tc
                        if take:
                            zg_last[k] = int(s_t)
                            cbi = tonum(f[5])
                            if zg_exp[k][0]:
                                for z in [z for z in zones if z["gid"] == 19 + k and cbi - z["bi"] >= zg_exp[k][1]]:
                                    drop(z)
                    elif take and f[0] == "D" and len(f) > 16:
                        zid, side, cnt, zp = int(tonum(f[1])), int(tonum(f[2])), tonum(f[7]), tonum(f[16])
                        if (zid, k) not in zg_used and zp is not None:
                            zg_used.add((zid, k))
                            if zg_use[k]:
                                z = add(mk(19 + k, 1 if side == -1 else -1, zp - P["zgHalf"], zp + P["zgHalf"], ctr=zp, bi=int(cbi)))
                                z["aux"] |= (1 << (16 + k)) if cnt == 3 else 0
        body_hi, body_lo = max(b["o"], b["c"]), min(b["o"], b["c"])
        for z in [z for z in zones if 19 <= z["gid"] <= 21]:
            if (body_hi > z["ctr"] + P["zgRev"] + EPS) if z["sub"] == 1 else (body_lo < z["ctr"] - P["zgRev"] - EPS):
                drop(z)

    events, unk, unk_cnt, cont, n_pre, n_multi = [], 0, {}, 0, 0, 0
    ma_unk = [0, 0]
    n_bad = 0
    pc = None
    info = []                       # per bar: (tc, bad, o, h, l)
    for bi, b in enumerate(bars):
        tc = b.get("tc", b["t"] + M5)
        if bar_bad(b):
            n_bad += 1
            for z in zones + ma:
                z["outT"] = None
            pc = None
            info.append((tc, True, None, None, None))
            continue
        o, h, l, c = tk(b["o"]), tk(b["h"]), tk(b["l"]), tk(b["c"])
        info.append((tc, False, o, h, l))
        for k, v in ((0, b.get("p1")), (1, b.get("p5"))):
            ma[k]["ok"] = bool(zb_use[k] and v is not None)
            if ma[k]["ok"]:
                ma[k]["lo"], ma[k]["hi"] = tk(v - zh), tk(v + zh)
            elif zb_use[k]:
                ma_unk[k] += 1
        touched = [z for z in zones + [m for m in ma if m["ok"]] if z["hi"] >= l and z["lo"] <= h]
        live = tc >= P["zcStart"] and bi >= P["zcWarm"]

        def direction(c_lo, c_hi):
            if o > c_hi:
                return 1
            if o < c_lo:
                return -1
            if pc is None:
                return 0
            return 1 if pc > c_hi else -1 if pc < c_lo else 0
        pl = [(mem, c_lo, c_hi, direction(c_lo, c_hi)) for mem, c_lo, c_hi in places_of(touched, l, h)]
        order = (sorted([x for x in pl if x[3] == 1], key=lambda x: -x[2]) + sorted([x for x in pl if x[3] == -1], key=lambda x: x[1])
                 + sorted([x for x in pl if x[3] == 0], key=lambda x: -x[2]))
        n_pl = 0
        new = []
        for mem, c_lo, c_hi, d in order:
            gids = sorted(set(z["gid"] for z in mem))
            mask = sum(1 << g for g in gids)
            if d != 0:
                n_pl += 1
            if all(z["on"] for z in mem):          # contact state as it was before this bar
                cont += 1
                continue
            if not live:
                n_pre += 1
                continue
            if d == 0:
                unk += 1
                unk_cnt[min(len(gids), 3)] = unk_cnt.get(min(len(gids), 3), 0) + 1
                continue
            aux = 0
            for z in mem:
                aux |= (1 << ((8 if z["inv"] else 12) + z["gid"] - 15)) if 15 <= z["gid"] <= 18 else z["aux"]
            on_mask = 0
            for z in mem:
                on_mask |= (1 << z["gid"]) if z["on"] else 0
            u1, u5 = zb_use[0] and not ma[0]["ok"], zb_use[1] and not ma[1]["ok"]
            em = min(mem, key=lambda z: (z["hi"], z["id"])) if d == 1 else min(mem, key=lambda z: (-z["lo"], z["id"]))
            edge = c_hi if d == 1 else c_lo
            if d == 1:
                cpos = 0 if c > c_hi else 1 if c >= c_lo else 2
            else:
                cpos = 0 if c < c_lo else 1 if c <= c_hi else 2
            ev = dict(id=len(events) + 1, t0=tc, p0=c, d=d, mask=mask, nEv=len(gids), nRaw=len(mem), og=em["gid"], rTop=c_hi, rBot=c_lo,
                      edge=edge, cPos=cpos, ord=n_pl, aux=aux, bar=bi, onMask=on_mask,
                      flags=(512 if u1 else 0) + (1024 if u5 else 0) + (2048 if 9 in ze_stat else 0) + (4096 if on_mask else 0))
            events.append(ev)
            new.append(ev)
        for ev in new:
            ev["nPl"] = n_pl
        if live and n_pl >= 2:
            n_multi += 1
        for z in touched:
            z["on"], z["outT"] = True, None
        for z in zones + ma:
            if not z["on"]:
                continue
            if z["ma"] and not z["ok"]:
                z["outT"] = None
            elif z["hi"] >= l and z["lo"] <= h:
                z["outT"] = None
            else:
                dist = l - z["hi"] if l > z["hi"] else z["lo"] - h
                if z["outT"] is None:
                    z["outT"] = b["t"]
                if dist >= dep_t or tc - z["outT"] >= dep_ms:
                    z["on"], z["outT"] = False, None
        pc = c
        register(b, bi)

    # every event afterwards, from the bars after its touch bar
    why = [0, 0]
    for ev in events:
        t0, p0, d = ev["t0"], ev["p0"], ev["d"]
        lim = [t0 + n * M1 for n in (5, 15, 30)]
        later = list(enumerate(info))[ev["bar"] + 1:]
        fin = next((i for i, (tc, bad, *_r) in later if bad or tc >= lim[2]), None)
        stop = None if fin is None else info[fin]
        used = [(i, x) for i, x in later if (fin is None or i <= fin) and not x[1] and x[0] <= lim[2]]     # valid bars observed
        rmin, alo, ahi = [None] * 3, [None] * 3, [None] * 3
        mae = 0
        for i, (tc, bad, o, h, l) in used:
            fav = h - p0 if d == 1 else p0 - l
            adv = p0 - l if d == 1 else h - p0
            ofav = o - p0 if d == 1 else p0 - o
            for q in range(3):
                if rmin[q] is None and fav >= W[q]:
                    rmin[q] = max(1, min(30, math.floor((tc - t0) / M1 + 0.5)))
                    if ofav >= W[q]:
                        alo[q] = ahi[q] = mae
                    else:
                        alo[q] = max(mae, -ofav)
                        ahi[q] = max(alo[q], adv)
            mae = max(mae, adv)
        wst, wmfe, wmae, wnb = [0] * 3, [None] * 3, [None] * 3, [0] * 3
        last_tc = info[-1][0] if len(info) > ev["bar"] + 1 else None
        for hh in range(3):
            inw = [x for i, x in used if x[0] <= lim[hh]]
            wnb[hh] = len(inw)
            closed = any(tc >= lim[hh] for i, (tc, *_r) in later if fin is None or i <= fin)
            if stop is not None and stop[1] and stop[0] <= lim[hh]:
                wst[hh] = 2                           # an invalid bar inside the window: unmeasurable
                why[1] += 1
            elif closed:
                if inw:
                    wst[hh] = 1
                    wmfe[hh] = max([0] + [(x[3] - p0 if d == 1 else p0 - x[4]) for x in inw])
                    wmae[hh] = max([0] + [(p0 - x[4] if d == 1 else x[3] - p0) for x in inw])
                else:
                    wst[hh] = 2                       # no bar inside the window: unmeasurable
                    why[0] += 1
            else:
                wnb[hh] = 0 if last_tc is None else wnb[hh]
        # a reach is recorded only while a window is still open
        ev.update(rmin=rmin, alo=alo, ahi=ahi, wst=wst, wmfe=wmfe, wmae=wmae, wnb=wnb, fin=fin)
    return dict(events=events, unk=unk, unk_cnt=unk_cnt, cont=cont, nPre=n_pre, nMulti=n_multi, nBad=n_bad, maUnk=ma_unk, nZone=n_zone, why=why,
                on=sorted((z["gid"], z["lo"], z["hi"]) for z in zones + ma if z["on"]),
                act=sorted((z["gid"], z["sub"], z["lo"], z["hi"], z["inv"]) for z in zones), nbars=len(bars),
                zeBad=ze_bad, zdBad=zd_bad, zeStat=ze_stat, zdStat=zd_stat, nIfvg=n_ifvg[0], nFvgDead=n_fdead[0])


def record_of(ev):
    """the event record as the spec's table defines it (35 values)"""
    v = [None] * NF
    v[0:16] = [ev["id"], ev["t0"] / 1000.0, ev["p0"] * MT, ev["d"], ev["mask"], ev["nEv"], ev["nRaw"], ev["og"], ev["rTop"] * MT, ev["rBot"] * MT,
               ev["edge"] * MT, ev["d"] * (ev["p0"] - ev["edge"]) * MT, ev["cPos"], ev["ord"], ev["nPl"], ev["aux"]]
    fl = ev["flags"]
    for j in range(3):
        if ev["rmin"][j] is None:
            v[16 + j] = 0 if ev["wst"][2] == 1 else -1
        else:
            v[16 + j] = ev["rmin"][j]
            v[19 + 2 * j], v[20 + 2 * j] = ev["alo"][j] * MT, ev["ahi"][j] * MT
            if ev["alo"][j] != ev["ahi"][j]:
                fl += 64 << j
    for h in range(3):
        v[31 + h] = ev["wnb"][h]
        if ev["wst"][h] == 1:
            v[25 + 2 * h], v[26 + 2 * h] = ev["wmfe"][h] * MT, ev["wmae"][h] * MT
            fl += 1 << h
            if ev["wnb"][h] < (1, 3, 6)[h]:
                fl += 8 << h
    v[34] = fl
    v[35] = ev["onMask"]
    return v


def rows_of(events, key=lambda ev: ev["mask"]):
    out = {}

    def row(m):
        return out.setdefault(m, ([0] * (6 * NS), [0] * 540, [0, 0, 0]))
    for ev in events:
        c, hist, evn = row(key(ev))
        di = 0 if ev["d"] == 1 else 1
        evn[di] += 1
        for h in range(3):
            dh = di * 3 + h
            base = dh * NS
            if ev["wst"][h] == 0:
                c[base + 19] += 1
            elif ev["wst"][h] == 2:
                c[base + 1] += 1
            else:
                c[base] += 1
                c[base + 20] += 1 if ev["wnb"][h] < (1, 3, 6)[h] else 0
                c[base + 8] += ev["wmfe"][h]
                c[base + 9] += ev["wmae"][h]
                for j in range(3):
                    rm = ev["rmin"][j]
                    if rm is not None and rm <= (5, 15, 30)[h]:
                        c[base + 2 + j] += 1
                        c[base + 5 + j] += rm
                        c[base + 10 + j] += ev["alo"][j]
                        c[base + 13 + j] += ev["ahi"][j]
                        c[base + 16 + j] += 1 if ev["alo"][j] != ev["ahi"][j] else 0
                        hist[(dh * 3 + j) * 30 + rm - 1] += 1
    return out


def near(a, b):
    if a is None or b is None:
        return a is None and b is None
    return abs(a - b) < 1e-6


def same_rec(a, b):
    return len(a) == len(b) and all(near(x, y) for x, y in zip(a, b))


def expected_fifo(orc):
    """(bar index, record) of every output: finalized events queue up in finalization order, one leaves per confirmed bar"""
    fins = sorted((ev for ev in orc["events"] if ev["fin"] is not None), key=lambda ev: (ev["fin"], ev["id"]))
    out, q, i = [], [], 0
    for bi in range(orc["nbars"]):
        while i < len(fins) and fins[i]["fin"] == bi:
            q.append(fins[i])
            i += 1
        if q:
            out.append((bi, record_of(q.pop(0))))
    return out, [record_of(ev) for ev in q], fins


def compare(r, orc, label=""):
    """indicator run r vs oracle result; returns (ok, detail)"""
    det = []
    st = r.state()
    ev = orc["events"]
    for a, b in (("nEv", len(ev)), ("nEv2", sum(1 for e in ev if e["ord"] > 1)), ("nUnk", orc["unk"]), ("nCont", orc["cont"]), ("nBad", orc["nBad"]),
                 ("maUnk", orc["maUnk"]), ("nZone", orc["nZone"]), ("on", orc["on"]), ("act", orc["act"]), ("zeBad", orc["zeBad"]),
                 ("zdBad", orc["zdBad"]), ("zeStat", orc["zeStat"]), ("zdStat", orc["zdStat"]), ("nIfvg", orc["nIfvg"]), ("nFvgDead", orc["nFvgDead"]),
                 ("nMa1Ev", sum(1 for e in ev if e["flags"] & 512)), ("nMa5Ev", sum(1 for e in ev if e["flags"] & 1024)),
                 ("nEvOn", sum(1 for e in ev if e["onMask"])), ("nMultiBar", orc["nMulti"]), ("nPre", orc["nPre"]), ("nZeEv", sum(1 for e in ev if e["flags"] & 2048)), ("why", orc["why"])):
        if st[a] != b:
            det.append(f"{a}: {st[a]} != {b}")
    exp_out, exp_q, fins = expected_fifo(orc)
    got_out = r.out
    if len(got_out) != len(exp_out) or any(a[0] != b[0] or not same_rec(a[1], b[1]) for a, b in zip(got_out, exp_out)):
        bad = next((n for n, (a, b) in enumerate(zip(got_out, exp_out)) if a[0] != b[0] or not same_rec(a[1], b[1])), None)
        det.append(f"output: {len(got_out)} vs {len(exp_out)} first diff #{bad}" + ("" if bad is None else f" got {got_out[bad]} want {exp_out[bad]}"))
    got_q = [list(q.v) for q in r["zcQ"]]
    if len(got_q) != len(exp_q) or any(not same_rec(a, b) for a, b in zip(got_q, exp_q)):
        det.append(f"queue: {len(got_q)} vs {len(exp_q)}")
    pend_o = [e for e in ev if e["fin"] is None]
    pend_i = r.pending()
    keys = ("id", "t0", "p0", "d", "mask", "nEv", "nRaw", "og", "rTop", "rBot", "edge", "cPos", "ord", "nPl", "aux", "flags", "onMask", "rmin", "alo", "ahi",
            "wst", "wmfe", "wmae")
    if [[p[k] for k in keys] for p in pend_i] != [[p[k] for k in keys] for p in pend_o]:
        bad = next((n for n, (a, b) in enumerate(zip(pend_i, pend_o)) if [a[k] for k in keys] != [b[k] for k in keys]), None)
        det.append(f"pending: {len(pend_i)} vs {len(pend_o)}" + ("" if bad is None else f" got {pend_i[bad]} want {pend_o[bad]}"))
    rows_o = rows_of(ev)
    cnts = {m: q.cnt for m, q in zip(r["zrMask"], r["zrRow"])}
    if any(bin(m).count("1") != n for m, n in cnts.items()) or r["zrMask"] != list(dict.fromkeys(r["zrMask"])):
        det.append("row evidence count / duplicate rows")
    if r.rows() != rows_o:
        dm = [m for m in set(rows_o) | set(r.rows()) if rows_o.get(m) != r.rows().get(m)]
        det.append(f"rows differ for masks {dm[:4]}")
    sums_o = rows_of(ev, key=lambda e: min(e["nEv"], 3))
    cnt_unk = orc["unk_cnt"]
    empty = ([0] * (6 * NS), [0] * 540, [0, 0, 0])
    sums_i = r.sums()
    for g in (1, 2, 3):
        want = copy.deepcopy(sums_o.get(g, empty))
        want[2][2] += cnt_unk.get(g, 0)
        if sums_i and tuple(sums_i[g - 1]) != tuple(want):
            det.append(f"summary row {g} differs")
    all_o = copy.deepcopy(rows_of(ev, key=lambda e: 0).get(0, empty))
    all_o[2][2] += orc["unk"]
    if sums_i and tuple(sums_i[3]) != tuple(all_o):
        det.append("summary row all differs")
    if st["nDone"] != len(fins) or st["nOut"] != len(exp_out) or st["nDone"] != st["nOut"] + len(got_q):
        det.append(f"done/out: {st['nDone']} {st['nOut']} vs {len(fins)} {len(exp_out)}")
    return not det, "; ".join(det)


def params(r):
    return dict(r.inp)


# ----------------------------------------------------------------------------------------------------------------
def random_bars(seed, n5=2500):
    rnd = random.Random(seed)
    dens = (0.02, 0.006, 0.012, 0.004)[seed % 4]      # how often a feed brings a new zone
    wide = (14, 30, 20, 40)[seed % 4]
    grid = (0.01, 0.5, 0.25)[seed % 3]
    rd = lambda x: round(round(x / grid) * grid, 2)       # noqa: E731
    vol = (1.4, 2.4, 1.0)[seed % 3] * (1.0, 1.5, 1.2, 2.0)[seed % 4]
    p = 4300.0
    bars = []
    e1, e5, ne = None, None, 0
    t = T0
    cur = {}
    aid = [0, 0, 0]
    box = [None, None, None]
    zgid = 0
    zgblk = {1: [], 2: [], 3: []}
    per = {1: 6, 2: 12, 3: 24}          # 5m bars per synthetic "higher-TF" bar of ZG / ZF
    wave = [0, 0]
    for bi in range(n5):
        if rnd.random() < 0.01:          # chart gap (missing bars / market break)
            t += M5 * rnd.choice([1, 1, 2, 3, 5, 6, 12, 600])
        o = rd(p + (rnd.choice([-1, 1]) * rnd.uniform(0, 7) if rnd.random() < 0.04 else 0))
        c = rd(o + rnd.gauss(0, vol))
        h = rd(max(o, c) + abs(rnd.gauss(0, vol * 0.6)))
        l = rd(min(o, c) - abs(rnd.gauss(0, vol * 0.6)))
        h, l = max(h, o, c), min(l, o, c)
        b = dict(t=t, o=o, h=h, l=l, c=c, p1=None if ne < 20 or rnd.random() < 0.01 else round(e1, 4), p5=None if ne < 35 or rnd.random() < 0.01 else round(e5, 4))
        if rnd.random() < 0.003:
            b["tc"] = t + M5 - rnd.choice([M1, 2 * M1])      # a short session bar
        e1 = c if e1 is None else e1 + (c - e1) * 2 / 9
        e5 = c if e5 is None else e5 + (c - e5) * 2 / 31
        ne += 1
        p = c
        f = rnd.random()
        if f < 0.004:
            b[rnd.choice("ohlc")] = None
        elif f < 0.008:
            b["h"] = round(max(o, c) - rnd.choice([0.01, 1.0]), 2)
        near_p = lambda w: rd(p + rnd.uniform(-w, w))       # noqa: E731
        for k in (1, 2, 3, 4):
            if rnd.random() < dens:
                cur[f"s{k}h"], cur[f"s{k}ht"] = near_p(wide), t - k * 1000
            if rnd.random() < dens:
                cur[f"s{k}l"], cur[f"s{k}lt"] = near_p(wide), t - k * 1000 - 1
            if rnd.random() < 0.004:
                cur[f"s{k}h"], cur[f"s{k}ht"] = None, None
            if rnd.random() < dens:
                q = rnd.random()
                cen = near_p(wide) + rnd.choice([0, 0.003])
                if q < 0.75:
                    cur.update({f"zdL{k}": cen - 0.4, f"zdU{k}": cen + 0.4, f"zdT{k}": float(t - M5 * k)})
                elif q < 0.85:
                    cur[f"zdT{k}"] = float(t - M5 * k)
                elif q < 0.90:
                    cur.update({f"zdL{k}": None, f"zdU{k}": None, f"zdT{k}": -float(t - M5)})
                elif q < 0.94:
                    cur[f"zdT{k}"] = None
                elif q < 0.97:
                    cur.update({f"zdL{k}": cen + 1, f"zdU{k}": cen, f"zdT{k}": float(t - M5)})
                else:
                    cur[f"zdT{k}"] = rnd.choice([0.0, 12345.0, float(t + M5), float(t - M5) + 0.5])
            # ZF: a new key per synthetic higher-TF bar with its confirmed close; sometimes a new FVG
            if bi % (6 * k) == 0:
                d = rnd.choice([1, -1]) if rnd.random() < dens * 8 else 0
                lo = near_p(wide)
                cur.update(zf(k - 1, t - 6 * k * M5, p if rnd.random() > 0.02 else None, d, rd(lo + rnd.uniform(0.5, 8)) if d else None, lo if d else None))
        for k in (1, 2, 3):
            q = rnd.random()
            if box[k - 1] is None:
                if q < dens:
                    aid[k - 1] += 1
                    lo = near_p(wide)
                    box[k - 1] = [rd(lo + rnd.uniform(0.5, 9)), lo, rnd.random() < 0.8]
                    cur.update({f"f{k}u": box[k - 1][0], f"f{k}l": box[k - 1][1], f"f{k}i": t + aid[k - 1], f"f{k}a": 1 if box[k - 1][2] else 0})
                    if not box[k - 1][2]:
                        box[k - 1] = None
            else:
                if q < 0.15:
                    box[k - 1][0] = rd(box[k - 1][0] + rnd.uniform(0, 1.5))
                    box[k - 1][1] = rd(box[k - 1][1] - rnd.uniform(0, 1.5))
                    cur.update({f"f{k}u": box[k - 1][0], f"f{k}l": box[k - 1][1]})
                elif q < 0.25:
                    cur[f"f{k}a"] = 0
                    box[k - 1] = None
                elif q < 0.28:
                    box[k - 1] = None
            # ZG: one block per synthetic higher-TF bar; the request delivers the two blocks before the current one
            if bi % per[k] == 0:
                m = bi // per[k]
                dets = []
                if rnd.random() < dens * 6:
                    zgid += 1
                    dets.append((zgid, rnd.choice([-1, 1]), rnd.choice([2, 2, 3]), near_p(wide)))
                    if rnd.random() < 0.3:
                        dets.append((zgid, dets[0][1], 3, near_p(wide)))          # the same base again: ignored
                zgblk[k].append(zg_blk(t - per[k] * M5, t, m, dets))
                bl = zgblk[k]
                cur[("zgPk1", "zgPk4", "zgPkD")[k - 1]] = ";".join(bl[-3:-1]) if len(bl) >= 3 else (bl[-2] if len(bl) == 2 else "")
        # ZE: the LongFibWave connection outputs
        for kk, nm in enumerate(("4", "D")):
            q = rnd.random()
            if q < dens * 1.5:
                wave[kk] += 1
                e_ = near_p(wide)
                o_ = rd(e_ + rnd.choice([-1, 1]) * rnd.uniform(8, 40))
                cur.update({f"ze{nm}O": o_, f"ze{nm}E": e_, f"ze{nm}D": 1 if e_ > o_ else -1, f"ze{nm}I": float(wave[kk]), f"ze{nm}S": 3.0, f"ze{nm}T": float(t)})
            elif q < dens * 1.8:
                cur.update({f"ze{nm}O": None, f"ze{nm}E": None, f"ze{nm}D": 0, f"ze{nm}I": float(wave[kk]), f"ze{nm}S": float(rnd.choice([0, 1, 2])), f"ze{nm}T": float(t)})
            elif q < dens * 2.0:
                cur[f"ze{nm}{rnd.choice('OEDIST')}"] = rnd.choice([None, 0.5, 7.0, float(t + 10 * M5)])     # inconsistent feed
        if rnd.random() < 0.002 or bi < 3:
            cur["zeProto"] = rnd.choice([None, 4300.0])
        elif rnd.random() < 0.05 or bi == 3:
            cur["zeProto"] = 20001
        b.update(cur)
        bars.append(b)
        t += M5
    return bars


RANDOM_PRM = [
    dict(ALL_ON),
    dict(ALL_ON, zcDepW=3.0, zcDepMin=15),
    dict(ALL_ON, zHalf=0.5, zcDepW=1.5, zcDepMin=10, zaKeep1=2, zaKeep2=3, zgHalf=1.0, zgRev=3.0, zgExpN1=3, zgExpN4=2),
    dict(ALL_ON, zHalf=1.0, zcMax=3, zcDepMin=20, zgExp1=False),
    dict(ALL_ON, zHalf=0.0, zcDepW=0.5, zcDepMin=5, zgHalf=0.0, zcWarm=200),
    dict(zHalf=3.0, zcWarm=300, zcStart=T0 + 500 * M5),
]


def random_vs_oracle(seeds):
    last = None
    for seed in seeds:
        ov = RANDOM_PRM[seed % len(RANDOM_PRM)]
        bars = random_bars(seed)
        r = Runner(ov).run(bars)
        orc = oracle(bars, params(r))
        ok, det = compare(r, orc, f"seed {seed}")
        ev = orc["events"]
        for k_, v_ in (("ev", len(ev)), ("multi", sum(1 for e in ev if e["nEv"] >= 2)), ("unmeas", sum(1 for e in ev if 2 in e["wst"])),
                       ("short", sum(1 for e in ev for h in range(3) if e["wst"][h] == 1 and e["wnb"][h] < (1, 3, 6)[h])),
                       ("amb", sum(1 for e in ev for j in range(3) if e["rmin"][j] is not None and e["alo"][j] != e["ahi"][j])),
                       ("unk", orc["unk"]), ("cont", orc["cont"]), ("r15", sum(1 for e in ev if e["rmin"][2] is not None)), ("bad", orc["nBad"]),
                       ("pend", len(r["zcPend"])), ("queue", len(r["zcQ"])), ("sell", sum(1 for e in ev if e["d"] == -1)),
                       ("second", sum(1 for e in ev if e["ord"] > 1)), ("maunk", sum(1 for e in ev if e["flags"] & 1536)), ("evon", sum(1 for e in ev if e["onMask"])), ("npre", orc["nPre"]),
                       ("side", sum(1 for e in ev if e["aux"] >> 19)),
                       ("zeunk", sum(1 for e in ev if e["flags"] & 2048)), ("ifvg", sum(1 for e in ev if e["aux"] & 0xF00)),
                       ("triple", sum(1 for e in ev if e["aux"] & 0x70000)), ("why0", orc["why"][0]), ("why1", orc["why"][1]),
                       ("pos0", sum(1 for e in ev if e["cPos"] == 0)), ("pos2", sum(1 for e in ev if e["cPos"] == 2))) \
                + tuple((n[:2], sum(1 for e in ev if e["mask"] & G[n])) for n in ("ZA-4H", "ZB-1m", "ZC-D", "ZD-4H", "ZE-4H", "ZF-4H", "ZG-4H")):
            COVER[k_] = COVER.get(k_, 0) + v_
        rich = len(ev) > 20 and len(set(e["mask"] for e in ev)) > 3
        check(f"C random seed {seed} == oracle ({ov})", ok and rich,
              f"events={len(ev)} sets={len(set(e['mask'] for e in ev))} unk={orc['unk']} cont={orc['cont']} bad={orc['nBad']} out={len(r.out)} "
              f"queue={len(r['zcQ'])} pend={len(r['zcPend'])} | {det}")
        inv = True
        for c, hist, evn in list(r.rows().values()) + r.sums()[:4]:
            for di in range(2):
                for h in range(3):
                    base = (di * 3 + h) * NS
                    inv &= evn[di] == c[base] + c[base + 1] + c[base + 19] and c[base + 20] <= c[base]
                    for j in range(3):
                        inv &= c[base + 2 + j] <= c[base] and sum(hist[((di * 3 + h) * 3 + j) * 30:][:30]) == c[base + 2 + j]
                        inv &= c[base + 10 + j] <= c[base + 13 + j] and sum(hist[((di * 3 + h) * 3 + j) * 30 + (5, 15, 30)[h]:][:30 - (5, 15, 30)[h]]) == 0
                    inv &= c[base + 2] >= c[base + 3] >= c[base + 4]
        tot = r.sums()[3]
        inv &= sum(v[2][0] + v[2][1] for v in r.rows().values()) == tot[2][0] + tot[2][1] == len(ev)
        check(f"B seed {seed}: 行ごとに イベント = 計測可能 + 計測不能 + 待ち、本数不足 <= 計測可能、到達 <= 計測可能、$5 >= $10 >= $15、度数の合計 = 到達、集合行の合計 = 全体", inv)
        last = (bars, ov)
    need = dict(evon=200, npre=50, side=500, ev=3000, multi=500, unmeas=20, short=20, amb=100, unk=20, cont=2000, r15=100, bad=50, pend=1, queue=1, sell=1000, second=20, maunk=1,
                zeunk=1, ifvg=5, triple=5, why0=10, why1=10, pos0=200, pos2=200, ZA=50, ZB=200, ZC=200, ZD=50, ZE=50, ZF=50, ZG=20)
    check("C 乱数系列の合計で各機能・全 7 種類が使われている (複数根拠・本数不足・計測不能・順序不明・方向不明・同じ足の 2 か所目・未出力 ほか)",
          all(COVER.get(k, 0) >= v for k, v in need.items()), str({k: (COVER.get(k, 0), v) for k, v in need.items() if COVER.get(k, 0) < v}) + str(COVER))
    return last


# ----------------------------------------------------------------------------------------------------------------
def run_case(rows, feeds0, ov=None, base=ONLY_ZC, **kw):
    bars = rows if isinstance(rows, list) and rows and isinstance(rows[0], dict) else bars_from_rows(rows, feeds0, **kw)
    o = dict(base)
    o.update(ov or {})
    r = Runner(o).run(bars)
    orc = oracle(bars, params(r))
    ok, det = compare(r, orc)
    return r, orc, ok, det


def fixed_cases():
    D = zc(2, 1, 4300.0)                      # ZC-D line at 4300 -> band 4298..4302 (half width 2)
    ZCD, ZCW, ZC4, ZC1 = G["ZC-D"], G["ZC-W"], G["ZC-4H"], G["ZC-1H"]

    def case(name, rows, feeds0, cond, ov=None, **kw):
        r, orc, ok, det = run_case(rows, feeds0, ov, **kw)
        ev = orc["events"]
        c = False
        try:
            c = cond(r, ev, orc)
        except Exception as ex:        # noqa: BLE001
            det += f" cond raised {ex!r}"
        check(name, ok and c, f"events={[(e['bar'], e['d'], e['mask'], e['rmin'], e['wst'], e['wnb']) for e in ev]} unk={orc['unk']} cont={orc['cont']} | {det}")
        return r, ev, orc

    case("A 1 帯を飛び越えるギャップはタッチにしない (次の足が下から届いて 1 件)",
         [(4305, 4306, 4303, 4304), (4296, 4297, 4295, 4296), (4296, 4298, 4295.5, 4297.5)], D,
         lambda r, ev, o: len(ev) == 1 and ev[0]["d"] == -1 and ev[0]["bar"] == 3 and ev[0]["p0"] == 429750 and ev[0]["t0"] == T0 + 4 * M5)
    case("A 2 始値が帯内・直前終値も帯内 = 方向不明 (反発集計に入れない・接触中にはする)",
         [(4300, 4301, 4299, 4300), (4300, 4301, 4299, 4300.5)], D,
         lambda r, ev, o: len(ev) == 0 and o["unk"] == 1 and o["cont"] == 1 and len(r["zcOn"]) == 1 and r.rows() == {} and r.sums()[0][2] == [0, 0, 1]
         and r.sums()[3][2] == [0, 0, 1], start=4300.0)
    case("A 2b 始値が帯内・直前終値が帯の上 = 上から (LONG)",
         [(4305, 4305, 4305, 4305), (4301, 4301.5, 4300, 4301)], D, lambda r, ev, o: len(ev) == 1 and ev[0]["d"] == 1 and o["unk"] == 0)
    case("A 3 触れ続ける足は 1 件 (1 本ごとに増えない)",
         [(4304, 4304, 4301, 4301.5)] + [(4301.5, 4302.5, 4300.5, 4301.5)] * 14, D, lambda r, ev, o: len(ev) == 1 and o["cont"] == 14)
    trip = [(4301.5, 4303, 4301, 4303), (4303, 4306.9, 4303, 4306.5), (4306.5, 4306.9, 4302.5, 4303), (4303, 4303, 4301.5, 4301.5)]
    case("A 4 離脱幅未満の往復では増えない", [(4304, 4304, 4301, 4301.5)] + trip * 5, D, lambda r, ev, o: len(ev) == 1 and o["cont"] == 10)
    case("A 5 離脱幅以上離れた後の再接触は 2 件",
         [(4304, 4304, 4301, 4301.5), (4307, 4308, 4307, 4307.5), (4307.5, 4307.5, 4301.9, 4302.5)], D,
         lambda r, ev, o: len(ev) == 2 and [e["d"] for e in ev] == [1, 1] and ev[1]["bar"] == 3)
    case("A 5b 離脱幅まで 1 ティック不足 (安値 = 上端 + $4.99) では離脱しない",
         [(4304, 4304, 4301, 4301.5), (4307, 4308, 4306.99, 4307.5), (4307.5, 4307.5, 4301.9, 4302.5)], D, lambda r, ev, o: len(ev) == 1 and o["cont"] == 1)
    out5 = [(4304, 4304, 4301, 4301.5)] + [(4303, 4304, 4302.5, 4303)] * 5 + [(4303, 4303, 4301.5, 4302)]
    out6 = [(4304, 4304, 4301, 4301.5)] + [(4303, 4304, 4302.5, 4303)] * 6 + [(4303, 4303, 4301.5, 4302)]
    case("A 5c 離脱幅未満で外側 25 分 → 再接触は増えない", out5, D, lambda r, ev, o: len(ev) == 1)
    case("A 5d 離脱幅未満でも外側 30 分 (離脱時間) → 再接触は 2 件", out6, D, lambda r, ev, o: len(ev) == 2)
    b5e = bars_from_rows(out5, D)
    for b in b5e[4:]:
        b["t"] += M5                         # one missing bar while outside: 5 bars but 30 minutes of real time
    case("A 5e 離脱時間は実際の経過時間 (欠損 1 本をはさむ外側 5 本 = 30 分で離脱)", b5e, D, lambda r, ev, o: len(ev) == 2)
    # 6 the touch bar's own move is not a reaction: P0 = its close, observation from the next 5m bar
    r, ev, o = case("A 6 タッチ足の中の見かけの反発は数えない (P0 = 終値・観察は次の足から)",
                    [(4310, 4310, 4301, 4309)] + flat(4309, 7), D,
                    lambda r, ev, o: len(ev) == 1 and ev[0]["p0"] == 430900 and ev[0]["rmin"] == [None] * 3 and ev[0]["wmfe"] == [0, 0, 0]
                    and ev[0]["wmae"] == [0, 0, 0] and ev[0]["wst"] == [1, 1, 1] and ev[0]["wnb"] == [1, 3, 6])
    rec = r.records()[0] if r.records() else [None] * NF
    check("A 6 記録: 接触端 4302、終値 − 接触端 = +7 (帯の手前へ戻って確定)、未到達 = 0、MFE / MAE = 0、期間内の足 1 / 3 / 6、状態フラグ = 7",
          near(rec[1], (T0 + 2 * M5) / 1000.0) and near(rec[2], 4309.0) and rec[3] == 1 and rec[4] == ZCD and rec[5] == 1 and rec[7] == 7
          and near(rec[8], 4302.0) and near(rec[9], 4301.0) and near(rec[10], 4302.0) and near(rec[11], 7.0) and rec[12] == 0 and rec[13:15] == [1, 1]
          and rec[16:19] == [0, 0, 0] and rec[19:25] == [None] * 6 and rec[25:31] == [0.0] * 6 and rec[31:34] == [1, 3, 6] and rec[34] == 7, str(rec))
    case("A 6b タッチ足の終値の位置: 帯内で確定 = 1 (P0 は終値)", [(4310, 4310, 4299, 4300)], D,
         lambda r, ev, o: [(e["cPos"], e["edge"], e["p0"]) for e in ev] == [(1, 430200, 430000)])
    case("A 6c タッチ足の終値の位置: 帯の向こう側へ抜けて確定 = 2 (P0 は終値。終値 − 接触端 = −11)", [(4310, 4310, 4290, 4291)] + flat(4291, 7), D,
         lambda r, ev, o: [(e["cPos"], e["edge"], e["p0"]) for e in ev] == [(2, 430200, 429100)] and near(r.records()[0][11], -11.0))
    # 7 end of history
    r, ev, o = case("A 7 履歴末尾: 5 分は計測可能、15 分・30 分は観測未完了 (分母に入れない)",
                    [(4304, 4304, 4301, 4303)] + flat(4303, 2), D,
                    lambda r, ev, o: ev[0]["wst"] == [1, 0, 0] and ev[0]["fin"] is None and len(r["zcPend"]) == 1 and len(r.records()) == 0)
    c = r.rows().get(ZCD, ([0] * 126,))[0]
    check("A 7 集計: LONG 5 分 計測可能 1、15 / 30 分 は 待ち 1・計測可能 0", (c[0], c[19], c[NS], c[NS + 19], c[2 * NS], c[2 * NS + 19]) == (1, 0, 0, 1, 0, 1), str(c[:63]))
    # 8 gaps: real elapsed time. touch bar closes at T0 + 10m. Next bars close at +35m and +40m (a 20 minute hole)
    b8 = bars_from_rows([(4304, 4304, 4301, 4303), (4303, 4309, 4303, 4308), (4308, 4320, 4308, 4320), (4320, 4320, 4320, 4320)], D)
    for b in b8[2:]:
        b["t"] += 4 * M5
    for b in b8[3:]:
        b["t"] += M5
    r, o, ok, det = run_case(b8, None)
    e8 = o["events"][0]
    rec = r.records()[0] if r.records() else [None] * NF
    c = r.rows().get(ZCD, ([0] * 126,))[0]
    check("A 8 欠損・休場またぎ: 5 分・15 分は期間内の足が 0 本 = 計測不能 (未到達にしない)、30 分は 1 本で判定 = 計測可能 (本数不足)。期間後の足 ($17 上) は数えない",
          ok and e8["wst"] == [2, 2, 1] and e8["wnb"] == [0, 0, 1] and e8["rmin"] == [25, None, None] and e8["wmfe"][2] == 600
          and (c[1], c[NS + 1], c[2 * NS], c[2 * NS + 20], c[2 * NS + 2], c[2 * NS + 3]) == (1, 1, 1, 1, 1, 0) and rec[16:19] == [25, 0, 0]
          and rec[34] == 4 + 32 and rec[31:34] == [0, 0, 1] and r["zcWhy"][0] == 2 and e8["fin"] == 3, f"{e8} rec={rec} | {det}")
    b8b = bars_from_rows([(4304, 4304, 4301, 4303), (4303, 4309, 4303, 4308), (4308, 4320, 4308, 4320)], D)
    for b in b8b[2:]:
        b["t"] += 600 * M5                   # a weekend: the first bar after it closes far beyond T0 + 30m
    r, o, ok, det = run_case(b8b, None)
    check("A 8b 期間内に足が 1 本も無い (休場明けの足は T0 + 30 分より後) → 3 期間とも計測不能で確定し、分母に入らない",
          ok and o["events"][0]["wst"] == [2, 2, 2] and o["events"][0]["rmin"] == [None] * 3 and r.records()[0][16:19] == [-1, -1, -1]
          and r.records()[0][34] == 0, f"{o['events'][0]} | {det}")
    b8c = bars_from_rows([(4304, 4304, 4301, 4303), (4303, 4304, 4303, 4303), (4303, 4304, 4303, 4303), (4303, 4320, 4303, 4320)] + flat(4320, 5), D)
    b8c[4]["h"] = 4302.0                      # an invalid bar (high < max(open, close)) 15 minutes after the touch
    r, o, ok, det = run_case(b8c, None)
    check("A 8c 不正足が期間の中に来たら、その期間は計測不能 (それまでに終わった 5 分・10 分… は残る)。不正足の後は追跡しない",
          ok and o["events"][0]["wst"] == [1, 2, 2] and o["events"][0]["wnb"][0] == 1 and r["st"].nBad == 1 and r["zcWhy"][1] == 2
          and o["events"][0]["rmin"] == [None] * 3, f"{o['events'][0]} | {det}")
    # 9 exact match
    f9 = merge(zc(2, 1, 4300.0), zc(3, 1, 4301.0), zd(1, 4302.0), zc(2, -1, 4250.0), zc(3, -1, 4251.0))
    case("A 9 完全一致: ZC-D+ZC-W+ZD-4H の接触は ZC-D+ZC-W の行に入らない",
         [(4310, 4310, 4301.5, 4306), (4306, 4320, 4306, 4320), (4260, 4260, 4252, 4256)], f9,
         lambda r, ev, o: [e["mask"] for e in ev] == [ZCD + ZCW + G["ZD-4H"], ZCD + ZCW] and [e["nEv"] for e in ev] == [3, 2]
         and r.rows()[ZCD + ZCW][2] == [1, 0, 0] and r.rows()[ZCD + ZCW + G["ZD-4H"]][2] == [1, 0, 0] and r.sums()[1][2][0] == 1 and r.sums()[2][2][0] == 1,
         ov={"zdUse2": True})
    # 10 one big bar touching two places far apart: two events, each with its own set
    f10 = merge(zc(2, 1, 4300.0), zc(3, -1, 4280.0))
    r, ev, o = case("A 10 1 本の大きな足が離れた 2 か所に触れる: 別々のイベント (合算しない)。上からの Zone を上端の高い順に見る",
                    [(4310, 4310, 4279, 4290)], f10,
                    lambda r, ev, o: [(e["mask"], e["nEv"], e["nRaw"], e["d"], e["ord"], e["nPl"]) for e in ev] == [(ZCD, 1, 1, 1, 1, 2), (ZCW, 1, 1, 1, 2, 2)]
                    and sorted(r.rows()) == [ZCD, ZCW] and r["st"].nEv2 == 1 and ev[0]["p0"] == ev[1]["p0"] and ev[0]["t0"] == ev[1]["t0"])
    case("A 10b 始値が 2 か所の間: 上の場所は下から (SHORT)、下の場所は上から (LONG)。上からの場所が先",
         [(4290, 4299, 4281.5, 4290)], f10,
         lambda r, ev, o: [(e["mask"], e["d"], e["ord"]) for e in ev] == [(ZCW, 1, 1), (ZCD, -1, 2)])
    case("A 10c 離れた 2 か所を別の足でタッチ: 別々のイベント、後から合算しない",
         [(4304, 4304, 4301, 4303), (4303, 4303, 4281, 4282)], f10,
         lambda r, ev, o: [(e["mask"], e["nEv"]) for e in ev] == [(ZCD, 1), (ZCW, 1)])
    # 11 chain A-B-C where A and C do not overlap: never one set of three
    f11 = merge(zc(2, 1, 4300.0), zc(3, 1, 4303.5), zc(1, 1, 4307.0))     # bands 4298..4302 / 4301.5..4305.5 / 4305..4309
    case("A 11 連鎖 A–B–C (A と C は重ならない) を 1 本で全部タッチ: {C, B} と {A, B} の 2 イベント。3 つを 1 つの集合にしない。共通区間 C = 全員の帯の重なり",
         [(4312, 4312, 4297, 4300)], f11,
         lambda r, ev, o: [(e["mask"], e["og"], e["rTop"], e["rBot"], e["ord"]) for e in ev] == [(ZC4 + ZCW, 8, 430550, 430500, 1), (ZCD + ZCW, 7, 430200, 430150, 2)]
         and ZCD + ZCW + ZC4 not in r.rows())
    case("A 11b 連鎖の端だけをタッチ: タッチしていない帯は集合に入らない (C だけ)。R = 起点帯 ∩ 足の高安",
         [(4312, 4312, 4308.5, 4310)], f11,
         lambda r, ev, o: (ev[0]["mask"], ev[0]["nRaw"], ev[0]["rTop"], ev[0]["rBot"]) == (ZC4, 1, 430900, 430850) and len(ev) == 1)
    case("A 11c タッチしていても R と重ならない帯は入らない: 足は C と B に掛かるが、R = C ∩ 足 (4305.2..4309) に B (上端 4305.5) は重なる / A は入らない",
         [(4312, 4312, 4305.2, 4306)], f11,
         lambda r, ev, o: len(ev) == 1 and (ev[0]["mask"], ev[0]["nRaw"]) == (ZC4 + ZCW, 2))
    case("A 11d R と重ならない B は別の場所: 足は C (4305..4309) の上側だけ → {C}。次の足で B だけ (4301.5..4305.5) → B は未接触なので別イベント",
         [(4312, 4312, 4308, 4310), (4304, 4304.5, 4303, 4303.5)], merge(zc(3, 1, 4303.5), zc(1, 1, 4307.0)),
         lambda r, ev, o: [(e["mask"], e["d"]) for e in ev] == [(ZC4, 1), (ZCW, 1)])
    case("A 11e 接する帯 (上端 = 下端) は R と重なる。1 ティック離れると別",
         [(4310, 4310, 4305.5, 4306)], merge(zc(2, 1, 4300.0), zc(3, 1, 4304.0), zc(1, 1, 4308.01)),
         lambda r, ev, o: [(e["mask"], e["ord"]) for e in ev] == [(ZC4, 1), (ZCW, 2)] and ev[1]["rBot"] == 430550)
    # F1: places = maximal sets of touched zones sharing a price point (every member overlaps every other), same sets from both sides
    f4 = merge(zc(0, 1, 4312.0), zc(1, 1, 4309.0), zc(2, 1, 4306.0), zc(3, 1, 4303.0))      # bands 4310..4314 / 4307..4311 / 4304..4308 / 4301..4305
    want4 = sorted([ZC1 + ZC4, ZC4 + ZCD, ZCD + ZCW])
    ra_, oa, oka, _d = run_case([(4320, 4320, 4300, 4300.5)], f4)
    rb_, ob, okb, _d = run_case([(4295, 4315, 4295, 4314.5)], f4, start=4295.0)
    sa, sb = [e["mask"] for e in oa["events"]], [e["mask"] for e in ob["events"]]
    check("A F1 幅 $4 の線 4 本 (4312 / 4309 / 4306 / 4303) を 1 本でタッチ: 上からでも下からでも同じ 3 集合 {1H+4H} {4H+D} {D+W} (メンバーは全員が相互に重なる)",
          oka and okb and sorted(sa) == want4 and sorted(sb) == want4 and sa == [ZC1 + ZC4, ZC4 + ZCD, ZCD + ZCW] and sb == [ZCD + ZCW, ZC4 + ZCD, ZC1 + ZC4]
          and [e["ord"] for e in oa["events"]] == [1, 2, 3] and [e["d"] for e in ob["events"]] == [-1, -1, -1]
          and [(e["rBot"], e["rTop"]) for e in oa["events"]] == [(431000, 431100), (430700, 430800), (430400, 430500)], f"{sa} {sb}")
    fw = merge(zf(1, T0 - 3_600_000, 4350.0, 1, 4320.0, 4280.0), zc(2, 1, 4290.0), zc(3, 1, 4310.0))
    case("A F1b 広い帯 (FVG 4280..4320) の中に離れた 2 本の線: {広+線1} と {広+線2}。{広+線1+線2} にはしない", [(4330, 4330, 4270, 4275)], fw,
         lambda r, ev, o: [e["mask"] for e in ev] == [G["ZF-4H"] + ZCW, G["ZF-4H"] + ZCD] and sorted(r.rows()) == sorted([G["ZF-4H"] + ZCW, G["ZF-4H"] + ZCD])
         and [e["ord"] for e in ev] == [1, 2] and r["st"].nMultiBar == 1, ov={"zfUse2": True})
    case("A F1c 上からの場所と下からの場所が同じ足にある: 上から (C の上端が高い順) → 下から (C の下端が低い順)", [(4300, 4315, 4285, 4300)],
         merge(zc(0, 1, 4312.0), zc(1, 1, 4306.0), zc(2, 1, 4294.0), zc(3, 1, 4288.0)),
         lambda r, ev, o: [(e["mask"], e["d"], e["ord"]) for e in ev] == [(ZCD, 1, 1), (ZCW, 1, 2), (ZC4, -1, 3), (ZC1, -1, 4)], start=4300.0)
    # F2: suppressed only when every member was already in contact
    b = bars_from_rows([(4310, 4310, 4305, 4306), (4306, 4306, 4303, 4304), (4304, 4304, 4301.5, 4303), (4303, 4303, 4301.5, 4302.5)], D)
    for x in b[1:]:
        x["p1"] = 4306.0                         # ZB-1m band 4304..4308, the D line band is 4298..4302
    b[3]["p1"] = b[4]["p1"] = 4303.5             # the MA band moves to 4301.5..4305.5 and overlaps the line band
    r, o, ok, det = run_case(b, None, {"zbUse1": True})
    e = o["events"]
    check("A F2 MA 帯に接触したまま日足線へ初めて到達: 新規イベント (集合は ZB-1m+ZC-D、接触中だった根拠 = ZB-1m を記録・フラグ 4096)。同じ構成で触れ続ける次の足は 0 件",
          ok and [(x["bar"], x["mask"], x["onMask"], x["flags"]) for x in e] == [(1, G["ZB-1m"], 0, 0), (3, G["ZB-1m"] + ZCD, G["ZB-1m"], 4096)]
          and o["cont"] == 2 and r["st"].nEvOn == 1, f"{[(x['bar'], x['mask'], x['onMask'], x['flags']) for x in e]} cont={o['cont']} | {det}")
    case("A F2b 広い FVG の中を動いて線へ初めて到達: 新規 (接触中だった根拠 = ZF)。FVG の中だけの足・同じ構成の足は増えない",
         [(4330, 4330, 4318, 4319), (4319, 4319, 4315, 4316), (4316, 4316, 4311, 4313), (4313, 4313, 4310, 4311.5), (4311.5, 4312, 4309, 4310)],
         merge(zf(1, T0 - 3_600_000, 4350.0, 1, 4320.0, 4280.0), zc(3, 1, 4310.0)),
         lambda r, ev, o: [(e["bar"], e["mask"], e["onMask"]) for e in ev] == [(1, G["ZF-4H"], 0), (3, G["ZF-4H"] + ZCW, G["ZF-4H"])] and o["cont"] == 3,
         ov={"zfUse2": True})
    # F3: start date / warm-up bars: zones and contact states are kept as usual, only the events are not made
    rows_w = [(4304, 4304, 4301, 4303), (4303, 4303, 4301, 4302.5), (4302.5, 4309, 4302.5, 4308), (4308, 4308, 4308, 4308), (4308, 4308, 4301, 4302)]
    case("A F3 助走本数 3: 先頭 3 本の間のタッチはイベントにしない (件数だけ)。接触中は立つので直後の足は継続中。離脱後の再接触からイベント", rows_w, D,
         lambda r, ev, o: [e["bar"] for e in ev] == [5] and o["nPre"] == 1 and o["cont"] == 1 and ev[0]["id"] == 1, ov={"zcWarm": 3})
    case("A F3b 集計開始日時 (タッチ足の確定時刻で判定): 開始前のタッチはイベントにしない", rows_w, D,
         lambda r, ev, o: [e["bar"] for e in ev] == [5] and o["nPre"] == 1, ov={"zcStart": T0 + 5 * M5 + 1})
    case("A F3c 集計開始日時ちょうどに確定した足は集計する", rows_w, D, lambda r, ev, o: [e["bar"] for e in ev] == [1, 5] and o["nPre"] == 0, ov={"zcStart": T0 + 2 * M5})
    # F5 / row cap
    r = Runner(dict(ONLY_ZC), maxrow=1).run(bars_from_rows([(4310, 4310, 4279, 4290)], f10))
    check("A 行数上限: 上限を超えた集合は「上限超過」行へ入り、件数を別に数える (全体・根拠数別の行は全件)",
          list(r.rows()) == [ZCD] and r["st"].rowOver == 1 and r.sums()[4][2] == [1, 0, 0] and r.sums()[3][2] == [2, 0, 0] and "int   ZC_MAXROW = 300 " in read(PINE))
    # 12 after $5 the same event keeps being tracked for $10 / $15 up to 30 minutes
    p = 4303.0
    rows12 = [(4304, 4304, 4301, p), (p, p + 2, p, p + 1), (p + 1, p + 5.5, p + 1, p + 5), (p + 5, p + 6, p + 5, p + 5), (p + 5, p + 10.2, p + 5, p + 10),
              (p + 10, p + 11, p + 10, p + 10), (p + 10, p + 15, p + 10, p + 15), (p + 15, p + 30, p + 15, p + 30)]
    r, ev, o = case("A 12 $5 到達後も $10 / $15 を 30 分まで追跡 (初回到達 10 / 20 / 30 分)。30 分を過ぎた足は数えない", rows12, D,
                    lambda r, ev, o: len(ev) == 1 and ev[0]["rmin"] == [10, 20, 30] and ev[0]["wst"] == [1, 1, 1] and ev[0]["wmfe"] == [200, 600, 1500])
    c = r.rows().get(ZCD, ([0] * 126,))[0]
    nine = [c[h * NS + 2 + j] for h in range(3) for j in range(3)]
    check("A 12 9 条件: 5 分 = なし、15 分 = $5、30 分 = $5・$10・$15", nine == [0, 0, 0, 1, 0, 0, 1, 1, 1], str(nine))
    rows13 = [(4304, 4304, 4301, p), (p, p + 1, p - 1.5, p), (p, p + 6, p - 2.5, p + 5), (p + 5, p + 11, p + 5, p + 10.5),
              (p + 15.5, p + 16, p + 9, p + 15)] + flat(p + 15, 3)
    case("A 13 到達前の最大逆行: $5 = 1.5～2.5 (到達足の中は順序不明)、$10 = 2.5 (単一)、$15 = 始値で到達済み → 2.5 (その足の安値は入れない)",
         rows13, D, lambda r, ev, o: (ev[0]["alo"], ev[0]["ahi"]) == ([150, 250, 250], [250, 250, 250]) and ev[0]["rmin"] == [10, 15, 20]
         and r.records()[0][34] == 7 + 64)
    case("A 14 同じ根拠 ID の Zone が 2 本でも根拠数は 1 (生の本数は 2)",
         [(4310, 4310, 4301.5, 4304)], merge(zc(2, 1, 4300.0), zc(2, -1, 4301.0)),
         lambda r, ev, o: (ev[0]["mask"], ev[0]["nEv"], ev[0]["nRaw"]) == (ZCD, 1, 2))
    # 15 causality
    b15 = bars_from_rows([(4301, 4301.5, 4300, 4301), (4301, 4301.5, 4300, 4301), (4301, 4301.5, 4300, 4301)], None, start=4310.0, feeds={1: D})
    r, o, ok, det = run_case(b15, None)
    check("K 登録した 5 分足ではタッチにしない (次の 5 分足から。価格の位置に現れた Zone は方向不明)",
          ok and r["st"].nEv == 0 and r["st"].nUnk == 1 and r["st"].nCont == 1 and r["zcNZone"][7] == 1, f"{r.state()} | {det}")
    # 17 FIFO
    r, ev, o = case("A 17 同じ 5 分足で 2 件確定 → 1 足 1 件ずつ出力 (FIFO)", [(4310, 4310, 4279, 4290)] + flat(4290, 9), f10,
                    lambda r, ev, o: len(r.out) == 2 and r.out[1][0] == r.out[0][0] + 1 and [x[1][0] for x in r.out] == [1, 2] and r["st"].nOut == 2)
    r2 = Runner(ONLY_ZC).run(bars_from_rows([(4310, 4310, 4279, 4290)] + flat(4290, 6), f10))
    check("A 17b 出力し切れない分は未出力として残る", len(r2.out) == 1 and len(r2["zcQ"]) == 1 and r2["st"].nDone == 2)
    b18 = bars_from_rows([(4304, 4304, 4301, 4303)], D)
    b18[1]["conf"] = False
    r = Runner(ONLY_ZC).run(b18)
    r2 = Runner(ONLY_ZC, run=False).run(bars_from_rows([(4304, 4304, 4301, 4303)], D))
    check("A 18 未確定の足・対象外のチャートでは集計しない", r["st"].nEv == 0 and r["st"].nBars == 1 and r2["st"].nBars == 0 and len(r2["zxZ"]) == 0)
    for name, rows, f in (("12", rows12, D), ("13", rows13, D), ("4", [(4304, 4304, 4301, 4301.5)] + trip * 5, D)):
        ax = 4300.0
        mrows = [(2 * ax - o_, 2 * ax - l_, 2 * ax - h_, 2 * ax - c_) for o_, h_, l_, c_ in rows]
        a = run_case(rows, f)
        b = run_case(mrows, f, start=4250.0)
        ka = [(e["t0"], e["d"], e["rmin"], e["alo"], e["ahi"], e["wmfe"], e["wmae"], e["cPos"]) for e in a[1]["events"]]
        kb = [(e["t0"], -e["d"], e["rmin"], e["alo"], e["ahi"], e["wmfe"], e["wmae"], e["cPos"]) for e in b[1]["events"]]
        check(f"A {name} 上下を反転した系列は方向だけ逆で同じ結果", a[2] and b[2] and ka == kb and len(ka) >= 1, f"{ka} {kb}")


def kinds():
    """each of the 7 zone kinds: registration -> touch -> event (the zone is registered on bar 0 or later and touched from above)"""
    touch = [(4310, 4310, 4301, 4305)]

    def one(name, ov, feeds0, cond, rows=touch, feeds=None, **kw):
        r, orc, ok, det = run_case(rows, feeds0, ov, base=OFF, feeds=feeds, **kw)
        ev = orc["events"]
        c = False
        try:
            c = cond(r, ev, orc)
        except Exception as ex:        # noqa: BLE001
            det += f" cond raised {ex!r}"
        check("T " + name, ok and c, f"events={[(e['bar'], e['d'], e['mask'], e['og'], e['rTop'], e['rBot'], e['aux']) for e in ev]} zones={r.zones()} {r.state()['zeStat']} | {det}")
        return r, ev, orc
    one("ZA: 形成終了で箱の上辺・下辺を登録 (4H 箱 4290..4300 → 上辺の帯 4298..4302 にタッチ)", {"zaUse2": True}, za(1, 4300.0, 4290.0, 111, 0),
        lambda r, ev, o: len(ev) == 1 and (ev[0]["mask"], ev[0]["og"], ev[0]["rTop"]) == (G["ZA-4H"], 1, 430200) and r["zcNZone"][1] == 2)
    b = bars_from_rows(flat(4350, 4), za(1, 4310.0, 4300.0, 111, 1),
                       feeds={1: za(1, 4311.0, 4299.0, 111, 1), 2: za(1, 4311.0, 4299.0, 111, 0), 3: za(1, 4330.0, 4320.0, 222, 0)})
    acts = []
    r = Runner(dict(OFF, zaUse2=True))
    for x in b:
        r.step(x)
        acts.append([(q[0], q[1], q[2]) for q in r.zones()])
    ok = compare(r, oracle(b, params(r)))[0]
    check("T ZA: 形成中は登録しない・形成終了で固定・最新 1 箱だけ残す (Lab の規則)",
          ok and acts == [[], [], [(1, -1, 429700), (1, 1, 430900)], [(1, -1, 431800), (1, 1, 432800)], [(1, -1, 431800), (1, 1, 432800)]], str(acts))
    b = bars_from_rows(touch + [(4305, 4325, 4305, 4321)], None)
    b[1]["p1"], b[2]["p1"] = 4300.0, 4320.0
    r, o, ok, det = run_case(b, None, {"zbUse1": True}, base=OFF)
    check("T ZB-1m: 帯 = 直前の足が確定した時点の 1 分 EMA ± 共通幅。EMA が na の足は不明として数える。帯が動いても同じ Zone (接触中を引き継ぐ)",
          ok and [(e["mask"], e["rTop"]) for e in o["events"]] == [(G["ZB-1m"], 430200)] and r["zcMaUnk"] == [1, 0] and o["cont"] == 1, f"{o['events']} {r['zcMaUnk']} | {det}")
    b = bars_from_rows(touch, None)
    b[1]["p5"] = 4300.0
    r, o, ok, det = run_case(b, None, {"zbUse2": True}, base=OFF)
    check("T ZB-5m: 帯 = 直前の足が確定した時点の 5 分 EMA ± 共通幅", ok and [(e["mask"], e["og"]) for e in o["events"]] == [(G["ZB-5m"], 4)], f"{o['events']} | {det}")
    one("ZC: Pivot の時刻キーが変わるたびに線ごとの帯 (W 高値 4300)", {"zcUse4": True}, zc(3, 1, 4300.0),
        lambda r, ev, o: len(ev) == 1 and ev[0]["mask"] == G["ZC-W"] and ev[0]["og"] == 8)
    one("ZD: 正常な POC (中心 4300) を登録", {"zdUse3": True}, zd(2, 4300.0), lambda r, ev, o: len(ev) == 1 and ev[0]["mask"] == G["ZD-D"])
    one("ZD: 置き換わった POC は接触中を引き継ぐ (旧 POC にタッチ中に中心が 4300 → 4301 へ: 次のタッチは継続中で新規イベントにしない)", {"zdUse3": True}, zd(2, 4300.0),
        lambda r, ev, o: len(ev) == 1 and o["cont"] == 1 and r["zcNZone"][11] == 2 and len(r.zones()) == 1,
        rows=touch + [(4305, 4305, 4302, 4304)], feeds={1: zd(2, 4301.0, T0)})
    one("ZD: 離れた価格へ置き換わった POC は接触中を引き継がない (4300 → 4320: 新しい POC への初回タッチは新規イベント)", {"zdUse3": True}, zd(2, 4300.0),
        lambda r, ev, o: [e["bar"] for e in ev] == [1, 3] and o["cont"] == 0,
        rows=touch + [(4305, 4305, 4305, 4305), (4305, 4319, 4305, 4318.5)], feeds={1: zd(2, 4320.0, T0)})
    one("ZD: 計算不能 (時刻 < 0)・履歴不足 (na)・異常 (上限 <= 下限) は直前の有効 POC を保つ", {"zdUse3": True}, zd(2, 4300.0),
        lambda r, ev, o: len(ev) == 1 and r["zcZdBad"][2] == 4 and len(r.zones()) == 1 and r["lbZdStat"][2] == 9,
        rows=flat(4350, 3) + touch, feeds={1: {"zdL3": None, "zdU3": None, "zdT3": -float(T0)}, 2: {"zdT3": None}, 3: {"zdL3": 5.0, "zdU3": 4.0, "zdT3": float(T0)}})
    # ZE: wave 4H origin 4250 -> end 4350 (up): levels 4350 + r * (4250 - 4350) = 4326.4 / 4311.8 / 4300 / 4288.2
    fe = ze(0, 4250.0, 4350.0, 1, 5)
    one("ZE: 最新の波の 4 水準 (0.236 / 0.382 / 0.5 / 0.618) を登録。0.5 の帯 4298..4302 にタッチ → 補助マスクに水準", {"zeUse": True}, fe,
        lambda r, ev, o: len(ev) == 1 and (ev[0]["mask"], ev[0]["og"], ev[0]["aux"]) == (G["ZE-4H"], 13, 4) and r["zcNZone"][13] == 4
        and [q[2] for q in r.zones()] == [428620, 429800, 430980, 432440] and r["lbZeStat"] == [1, 9], start=4340.0, rows=[(4306, 4306, 4301, 4305)])
    one("ZE: 未接続 (protocol が 20001 でない) は受信不正。Zone を作らず、その間のイベントに印を付けて別計上", {"zeUse": True, "zcUse3": True},
        merge(dict(fe, zeProto=4350.0), zc(2, 1, 4300.0)),
        lambda r, ev, o: len(ev) == 1 and ev[0]["mask"] == G["ZC-D"] and ev[0]["flags"] == 2048 and r["zcZeBad"] == [2, 2] and r["st"].nZeEv == 1 and r["zcNZone"][13] == 0)
    one("ZE: 波が変わったら旧 4 水準を外して新しい 4 水準 (同じ水準は接触中を引き継ぐ)。波なし (状態 1) で外す", {"zeUse": True}, fe,
        lambda r, ev, o: len(ev) == 1 and r["zcNZone"][13] == 8 and r.zones() == [] and r["lbZeStat"][0] == 2 and o["cont"] == 2,
        start=4340.0, rows=[(4306, 4306, 4301, 4305), (4305, 4305, 4302.5, 4304), (4304, 4304, 4304, 4304)],
        feeds={1: ze(0, 4252.0, 4352.0, 1, 6), 3: {"ze4O": None, "ze4E": None, "ze4D": 0, "ze4S": 1.0}})
    # ZF: FVG with its own top / bottom (4296..4303), key = forming bar time
    k1 = T0 - 3_600_000
    one("ZF: FVG は本来の上下限 (4296..4303) の帯。共通幅は使わない", {"zfUse2": True}, zf(1, k1, 4350.0, 1, 4303.0, 4296.0),
        lambda r, ev, o: len(ev) == 1 and (ev[0]["mask"], ev[0]["rTop"], ev[0]["rBot"], ev[0]["aux"]) == (G["ZF-4H"], 430300, 430100, 1 << 13))
    one("ZF: 上昇 FVG の下端を確定終値が下抜け → iFVG (補助マスクに iFVG)。iFVG の上端を確定終値が上抜け → 無効", {"zfUse2": True}, zf(1, k1, 4350.0, 1, 4303.0, 4296.0),
        lambda r, ev, o: [(e["bar"], e["aux"]) for e in ev] == [(3, 1 << 9)] and r["st"].nIfvg == 1 and r["st"].nFvgDead == 1 and r.zones() == [],
        start=4290.0, rows=[(4290, 4290, 4290, 4290), (4290, 4290, 4290, 4290), (4290, 4297, 4290, 4291), (4291, 4291, 4291, 4291), (4291, 4291, 4291, 4291)],
        feeds={1: zf(1, k1 + 1, 4295.0), 4: zf(1, k1 + 2, 4304.0)})
    # ZG: a detection (base 7, top, double, zone base price 4300) in the block of target bar 100
    blk = zg_blk(T0 - 7200_000, T0 - 3600_000, 100, [(7, -1, 2, 4300.0)])
    one("ZG: 検知イベントで発動 (トップ・基準価格 4300 ± ZG 幅)。同じ基準の再検知では作らない", {"zgUse1": True}, zg(0, blk),
        lambda r, ev, o: len(ev) == 1 and (ev[0]["mask"], ev[0]["og"], ev[0]["aux"], ev[0]["d"]) == (G["ZG-1H"], 19, 1 << 33, -1) and r["zcNZone"][19] == 1,
        start=4296.0, rows=[(4296, 4299, 4296, 4297)], feeds={1: zg(0, blk, zg_blk(T0 - 3600_000, T0, 101, [(7, -1, 3, 4310.0)]))})
    one("ZG: トリプルは補助マスクに残る。期限 (検知足から 24 本目の 1 時間足の確定) で消える", {"zgUse1": True}, zg(0, zg_blk(T0 - 7200_000, T0 - 3600_000, 100, [(8, 1, 3, 4300.0)])),
        lambda r, ev, o: len(ev) == 1 and ev[0]["aux"] == (1 << 16) + (1 << 36) and r.zones() == [],
        start=4296.0, rows=[(4296, 4299, 4296, 4297)] + flat(4297, 2), feeds={2: zg(0, zg_blk(T0 - 3600_000, T0, 123)), 3: zg(0, zg_blk(T0, T0 + 3 * M5, 124))})
    one("ZG: 逆行 (トップ: 実体上端 > 基準価格 + $5) の足で消える。その足のタッチ判定は消える前の Zone で行う (次の足から無い)", {"zgUse1": True}, zg(0, blk),
        lambda r, ev, o: [e["bar"] for e in ev] == [1] and r.zones() == [] and o["cont"] == 0,
        start=4296.0, rows=[(4296, 4306, 4296, 4305.5), (4305.5, 4305.5, 4301, 4301)])
    # all 7 kinds on one place
    allf = merge(za(1, 4300.0, 4280.0, 111, 0), zc(2, 1, 4300.5), zd(1, 4299.5), ze(0, 4250.0, 4350.0, 1, 5), zf(1, k1, 4350.0, -1, 4301.0, 4299.0),
                 zg(1, zg_blk(T0 - 7200_000, T0 - 3600_000, 100, [(7, 1, 2, 4300.0)])))
    b = bars_from_rows([(4306, 4306, 4301, 4305)], allf, start=4340.0)
    b[1]["p1"], b[1]["p5"] = 4300.2, 4299.8
    r, o, ok, det = run_case(b, None, {"zaUse2": True, "zbUse1": True, "zbUse2": True, "zcUse3": True, "zdUse2": True, "zeUse": True, "zeUseD": False, "zfUse2": True, "zgUse4": True}, base=OFF)
    want = sum(G[n] for n in ("ZA-4H", "ZB-1m", "ZB-5m", "ZC-D", "ZD-4H", "ZE-4H", "ZF-4H", "ZG-4H"))
    check("T 全 7 種類が同じ場所に重なる: 1 イベント・根拠数 8 (ZA ZB×2 ZC ZD ZE ZF ZG)", ok and len(o["events"]) == 1 and o["events"][0]["mask"] == want
          and o["events"][0]["nEv"] == 8, f"{o['events']} | {det}")


# ----------------------------------------------------------------------------------------------------------------
def causality(bars, ov):
    half = len(bars) // 2
    full = Runner(ov)
    for b in bars[:half]:
        full.step(b)
    at_half = full.snapshot()
    for b in bars[half:]:
        full.step(b)
    a = Runner(ov).run(bars[:half]).snapshot()
    check("K 前半だけの実行 == 全体実行の前半 (集計・記録・出力・追跡中の状態)", a == at_half and len(at_half["out"]) > 5)
    other = random_bars(987, len(bars) - half)
    shift = bars[half]["t"] - other[0]["t"]
    alt = []
    for b in other:
        nb = copy.deepcopy(b)
        nb["t"] += shift
        if "tc" in nb:
            nb["tc"] += shift
        alt.append(nb)
    c = Runner(ov)
    for b in bars[:half]:
        c.step(b)
    snap = c.snapshot()
    for b in alt:
        c.step(b)
    check("K 後半を別の系列に差し替えても前半の結果は同じ", snap == at_half)
    n_half = len([x for x in full.created if x[0] < half])
    check("K 全体実行で前半に発生したイベントの生成情報 == 前半だけの実行", full.created[:n_half] == a["created"] and n_half > 10)
    tcs = [b.get("tc", b["t"] + M5) for b in bars]
    late = all(tcs[i] > rec[1] * 1000 for i, rec in full.out)
    check("K 記録の出力はタッチ足より後 (観察した足の確定後)", late and len(full.out) > 10)
    check("B 同じ系列の再実行で結果一致", Runner(ov).run(bars).snapshot() == full.snapshot())
    disp = dict(ov, zcView="件数内訳", zcKind="根拠数別", zcDirMode="LONGのみ", zcHzMode="5分", zcTopN=1, zcShowBox=False, zcShowLbl=True, zcDrawMax=1)
    check("B 表示の設定を変えても集計・記録は同じ", Runner(disp).run(bars).snapshot() == full.snapshot())
    off = Runner(dict(ov, zcUse3=False, zbUse1=False, zgUse1=False, zfUse2=False, zeUse4=False)).run(bars)
    bits = G["ZC-D"] + G["ZB-1m"] + G["ZG-1H"] + G["ZF-4H"] + G["ZE-4H"]
    check("B 根拠 ID を OFF にするとその根拠は登録も集合にも現れない", [off["zcNZone"][g] for g in (7, 19, 16, 13)] == [0, 0, 0, 0]
          and all(not (m & bits) for m in off.rows()) and len(off.rows()) > 2)


MUTATIONS = [
    ("到達を「以上」から「超」へ", "                    if fav >= w\n", "                    if fav > w\n"),
    ("離脱幅を「以上」から「超」へ", "if dist >= zcDepT or", "if dist > zcDepT or"),
    ("離脱時間を使わない", " or time_close - z.outT >= zcDepMs", ""),
    ("継続中の抑制を外す", "    if allOn\n        st.nCont += 1\n", "    if false\n        st.nCont += 1\n"),
    ("継続中を「1 つでも接触中」に戻す", "    if allOn\n        st.nCont += 1\n", "    if onMask > 0\n        st.nCont += 1\n"),
    ("接近方向を始値でなく終値で決める", "if f_zcDir(pLo, pHi, o) == dp", "if f_zcDir(pLo, pHi, c) == dp"),
    ("接する帯 (端点一致) を別の場所にする", "                if not fn2 or mh < p2\n", "                if not fn2 or mh <= p2\n"),
    ("極大でない集合も場所にする", "                if not fn2 or mh < p2\n", "                if true\n"),
    ("同じ足の後の場所を前の場所の接触で抑制する (印をその場で付ける)", "            allOn := allOn and z.isOn\n            nRaw += 1\n", "            allOn := allOn and z.isOn\n            nRaw += 1\n            f_zcSetOn(z)\n"),
    ("期間の終わりを time_close < T0 + N 分にする (ちょうどの足を外す)", "            if tc > ob.t0 + array.get(zcWin, hh) * ZC_M1\n", "            if tc >= ob.t0 + array.get(zcWin, hh) * ZC_M1\n"),
    ("期間内の足が 0 本でも計測可能 (未到達) にする", "                f_zcWinDone(ob, hh, ob.nb > 0)", "                f_zcWinDone(ob, hh, true)"),
    ("基準時刻をタッチ足の開始にする", "        ZcObs ob = ZcObs.new(st.oSeq, time_close, c, dp,", "        ZcObs ob = ZcObs.new(st.oSeq, time, c, dp,"),
    ("始値で到達済みでも足の逆行を上限に入れる", "int hi = oFav >= w ? ob.mae : math.max(lo, adv)", "int hi = math.max(oFav >= w ? ob.mae : lo, adv)"),
    ("置き換わった POC / フィボが接触中を引き継がない", "            if z.tt >= array.get(zcInhB, sl) and z.tb <= array.get(zcInhT, sl)\n", "            if false\n"),
    ("離れた価格へ移った後継も接触中を引き継ぐ", "            if z.tt >= array.get(zcInhB, sl) and z.tb <= array.get(zcInhT, sl)\n", "            if true\n"),
    ("根拠数を Zone 本数にする", "        ZcRow row = f_zcRow(mask, nG)\n        st.oSeq += 1", "        ZcRow row = f_zcRow(mask, nRaw)\n        st.oSeq += 1"),
    ("場所の順番を価格の低い順だけにする", "int q   = dp == -1 ? k : nP - 1 - k", "int q   = k"),
    ("助走中もイベントにする", "    else if not live\n        st.nPre += 1\n", "    else if false\n        st.nPre += 1\n"),
]


def mutations(bars, ov):
    s = read(PINE)
    for name, old, new in MUTATIONS:
        if s.count(old) != 1:
            check(f"X {name}", False, f"mutation target found {s.count(old)} times")
            continue
        caught = False
        try:
            r = Runner(ov, source=s.replace(old, new)).run(bars)
            caught = not compare(r, oracle(bars, params(r)))[0]
        except Exception:      # noqa: BLE001
            caught = True
        check(f"X 変異を検出: {name}", caught)


# ----------------------------------------------------------------------------------------------------------------
def static():
    s = read(PINE)
    lab, feed = read(LAB), read(FEED)
    code = "\n".join(ap.strip_comment(x) for x in s.split("\n"))
    check("S indicator() 単体・strategy / alert / 注文なし", len(re.findall(r"^indicator\(", code, re.M)) == 1
          and not re.search(r"\b(strategy|alert|alertcondition)\s*[.(]", code) and s.startswith("//@version=6\n"))

    def between(t, a, b, incl=True):
        i = t.index(a)
        j = t.index(b, i)
        return t[i:j + (len(b) if incl else 0)]

    def func(t, sig):
        i = t.index("\n" + sig) + 1
        return t[i:t.index("\n\n", i)]

    def same(name, a, b, extra=True):
        check("S 写し: " + name, a(s) == b(lab) and len(str(b(lab))) > 200 and extra)
    same("ZA 検出関数 (f_acAccumBoxCore / f_acAccumBoxState / f_acConfirmed) は Lab と同一",
         lambda t: between(t, "// ==== LAB Accum copy (begin)", "    [_u[1], _l[1], _i[1], _a[1]]"), lambda t: between(t, "// ==== LAB Accum copy (begin)", "    [_u[1], _l[1], _i[1], _a[1]]"))
    same("ZC Pivot 関数 f_lbPivotConfirmed は Lab と同一",
         lambda t: between(t, "f_lbPivotConfirmed(simple int len) =>", "[_ph[1], _pt[1], _pl[1], _lt[1]]"), lambda t: between(t, "f_lbPivotConfirmed(simple int len) =>", "[_ph[1], _pt[1], _pl[1], _lt[1]]"))
    same("ZF f_fvgConfirmed は Lab と同一", lambda t: between(t, "// ==== LAB FVG copy (begin)", "// ==== LAB FVG copy (end)"), lambda t: between(t, "// ==== LAB FVG copy (begin)", "// ==== LAB FVG copy (end)"))
    same("ZG 検知器 (LTB の写し。LtB1 / LtH / ltNew1 / ltStep1 ほか) と f_zgCore は Lab と同一",
         lambda t: between(t, "// ==== ZG LTB copy (begin)", "// ==== ZG LTB copy (end)") + between(t, "f_zgCore(int k, bool on) =>", "    out[1]"),
         lambda t: between(t, "// ==== ZG LTB copy (begin)", "// ==== ZG LTB copy (end)") + between(t, "f_zgCore(int k, bool on) =>", "    out[1]"))
    fl = ["f_lbNew(int typ, int tf, int sub, float ctr, float bot, float top, float a, float b, int key) =>", "f_zgKill(int i) =>", "f_zeClear(int k) =>",
          "f_zeSet(int k, float o, float e, float d, float id, float t) =>", "f_zeSame(int k, float o, float e, float d, float id) =>", "f_lbAccFix(LbAcc q) =>",
          "f_zgParse(string pk, int lastT, int tcNow) =>", "f_zfUse(int k) =>", "f_zgUse(int k) =>", "f_zgExpOn(int k) =>", "f_zgExpN(int k) =>", "f_zeUse(int k) =>"]
    same("登録・失効の関数 12 個 (f_lbNew / f_lbAccFix / f_zeSet / f_zeClear / f_zeSame / f_zgKill / f_zgParse / 採用の関数) は Lab と同一",
         lambda t: [func(t, x) for x in fl], lambda t: [func(t, x) for x in fl])
    reg_lab = between(lab, "    // ZA: 新しい ID", "    // ZB: EMA ± 共通幅", False).rstrip("\n")
    reg_mine = between(s, "        // ==== LAB register (begin)", "        // ==== LAB register (end)", False).split("\n", 1)[1].rstrip("\n")
    dedent = "\n".join(ln[4:] if ln.startswith("    ") else ln for ln in reg_mine.split("\n"))
    check("S 写し: 登録ブロック全体 (ZA / ZC / ZD / ZE / ZF / ZG の登録・更新・期限・逆行消滅、Lab (B1) の 230 行) は Lab と同一 (字下げ 4 桁だけ違う)",
          dedent == reg_lab and len(reg_lab.split("\n")) > 200 and all(x in reg_lab for x in ("// ZA:", "// ZC:", "// ZD:", "// ZE:", "// ZF:", "// ZG:", "f_zgKill(i)")),
          f"{len(reg_lab.split(chr(10)))} lines")
    tl = [ln.split("//")[0].rstrip() for ln in between(lab, "type LbZone\n", "\n\n").split("\n")[1:13]]
    tm = [ln.split("//")[0].rstrip() for ln in between(s, "type LbZone\n", "\n\n").split("\n")[1:13]]
    check("S LbZone の先頭 12 項目 (f_lbNew が埋める項目) は Lab と同じ並び・型", tl == tm and len(tm) == 12, f"{tl} {tm}")

    def pocblk(t):
        a = t[t.index("// ==== FEED POC core (begin)"):t.index("// ==== FEED POC core (end)")]
        b = t[t.index("f_feed(bool enabled, int lookback, int bins) =>"):]
        return a, b[:b.index("\n\n")]
    check("S 写し: ZD f_pocCore / f_feed は MtfPocFeedXAU.pine と同一 (off = 1)", pocblk(s) == pocblk(feed))
    check("S 写し: ZE / ZF の入力と ZG 検知の入力 33 個は Lab と同一",
          between(lab, 'var string G_ZE = ', '\nvar string G_ZG = ', False) in s and between(lab, 'var string G_ZG1 = ', '\nvar string G_TA = ', False).rstrip("\n") in s)
    acc_req = re.findall(r'\[f(\d)u, f\1l, f\1i, f\1a\] = request\.security\(syminfo\.tickerid, "(\w+)", f_acConfirmed\(accumRangeLen, accumBaseLen, accumAtrLen,\s+'
                         r'accumMinUpperCloses, accumMinLowerCloses, accumMaxSameColorRun, accumAtrMult, accumBarRatioMax, accumDriftMax\),\s+lookahead = barmerge\.lookahead_on\)', code)
    piv_req = re.findall(r'\[s(\d)h, s\1ht, s\1l, s\1lt\] = request\.security\(syminfo\.tickerid, "(\w+)",\s+f_lbPivotConfirmed\(zcPiv\1\), lookahead = barmerge\.lookahead_on\)', code)
    poc_req = re.findall(r'\[zdL(\d), zdU\1, zdT\1\] = request\.security\(syminfo\.tickerid, "(\w+)",\s+f_feed\(zdUse\1, zdLen\1, vpBins\), lookahead = barmerge\.lookahead_on\)', code)
    fvg_req = re.findall(r'\[g(\d)k, g\1kc, g\1c, g\1d, g\1t, g\1b\] = request\.security\(syminfo\.tickerid, "(\w+)",\s+f_fvgConfirmed\(zfMinW\), lookahead = barmerge\.lookahead_on\)', code)
    zg_req = re.findall(r'string zgPk(\w) = request\.security\(syminfo\.tickerid, "(\w+)",\s+f_zgCore\((\d), zgUse\1\), lookahead = barmerge\.lookahead_on\)', code)
    tfs4 = [("1", "60"), ("2", "240"), ("3", "D"), ("4", "W")]
    check("S 上位足の取得: ZA 60 / 240 / D、ZC・ZD・ZF 60 / 240 / D / W、ZG 60 / 240 / D。すべて式の中で 1 本ずらし・lookahead_on (Lab と同じ形)",
          acc_req == tfs4[:3] and piv_req == tfs4 and poc_req == tfs4 and fvg_req == tfs4 and zg_req == [("1", "60", "0"), ("4", "240", "1"), ("D", "D", "2")],
          f"{acc_req} {piv_req} {poc_req} {fvg_req} {zg_req}")
    n_sec = len(re.findall(r"request\.security\(", code))
    n_req = len(re.findall(r"request\.\w+\(", code))
    tuples = [len(m.split(",")) for m in re.findall(r"^\[([\w, ]+)\] = request\.", code, re.M)]
    look = re.findall(r"lookahead = barmerge\.(\w+)", code)
    check("S request: security 19 件だけ (上限 40。lower_tf なし)、タプル要素 64 + 単独の戻り値 4 = 68 (上限 127)、lookahead_off は 1 分 EMA の 1 件だけ",
          (n_sec, n_req) == (19, 19) and sum(tuples) == 64 and len(tuples) == 15 and sorted(look) == ["lookahead_off"] + ["lookahead_on"] * 18
          and "request.security_lower_tf" not in code, f"{n_sec} {n_req} {sum(tuples)} {len(tuples)} {look}")
    check("S ZB: 1 分 EMA は Lab と同じ request.security(\"1\", ta.ema, lookahead_off)。判定には両方とも [1] (直前の足が確定した時点の値)",
          'float zbMa1 = request.security(syminfo.tickerid, "1", ta.ema(close, zbLen1), lookahead = barmerge.lookahead_off)' in code and 'float zbMa1 = request.security(syminfo.tickerid, "1", ta.ema(close, zbLen1), lookahead = barmerge.lookahead_off)' in lab
          and "float zbMa2 = ta.ema(close, zbLen2)\nfloat zbP1  = zbMa1[1]\nfloat zbP5  = zbMa2[1]" in code and "f_zcMaSet(0, zbUse1, zbP1)" in code and "f_zcMaSet(1, zbUse2, zbP5)" in code)
    lg = "\n".join(ap.strip_comment(x) for x in logic(s).split("\n"))
    check("S Logic 区間に request / ta. / 履歴参照なし。基準切替 (帯の接触端を P0 にする) の入力なし。「EMA が na (本数不足)」の記述なし",
          not re.search(r"\brequest\.|\bta\.", lg) and not re.search(r"\w\[", lg) and "zcBase" not in s and "本数不足) の間は" not in s and "ZcObs.new(st.oSeq, time_close, c, dp," in lg)
    plots = re.findall(r'^plot\((.+?),\s+"([^"]+)"', code, re.M)
    ev = [p for p in plots if p[1].startswith("EV ")]
    check("S plot 41 本 (上限 64)。EV 記録 36 本が zcOut の 0..35 の順", len(plots) == 41 and len(re.findall(r"\bplot\(", code)) == 41
          and [p[0] for p in ev] == [f"array.get(zcOut, {i})" for i in range(NF)] and f"int   ZC_NF     = {NF}" in code, f"{len(plots)} {len(ev)}")
    li, mi = ap.inputs(lab), ap.inputs(s)
    shared = [k for k in mi if k in li and re.match(r"(zHalf|zaUse|zaKeep|accum|zbUse|zbLen|zcUse|zcPiv|zdUse|zeUse|zfUse|zfMinW|zgUse|zgExp|zgHalf|zgRev|zg(Piv|Wave|Buf|Dist|Gap|Body|Ratio|Wait|Max|Dir|Sep))", k)]
    check("S Zone の入力の初期値は ZoneComboLabXAU と同じ (共通幅 2・ZA 4H/D・ZB 両方・ZC D/W・ZD 4H/D/W・ZE 4H/D・ZF 全 OFF・ZG 1H/4H/D ほか 84 個)",
          len(shared) == 84 and all(mi[k] == li[k] for k in shared) and mi["zcMax"] == 0 and mi["zcDepW"] == 5.0 and mi["zcDepMin"] == 30
          and mi["vpBins"] == 75 and mi["zcWarm"] == 6000
          and 'zcStart = input.time(timestamp("01 Jan 2020 00:00 +0000"), "集計開始日時 (タッチ足の確定時刻)"' in code
          and 'input.time(timestamp("01 Jan 2020 00:00 +0000"), "集計開始日時 (判定足の確定時刻)"' in read(os.path.join(ROOT, "PointMasterVerifierV2.pine")) and all(mi[f"zdLen{k}"] == 120 for k in (1, 2, 3, 4)), f"{len(shared)} {[k for k in shared if mi[k] != li[k]]}")
    check("S ZE は LongFibWave の接続出力 13 系列を input.source で受信 (名前は LongFibWave の plot と同じ)",
          all(f'input.source(close, "{n}"' in code and f'"{n}"' in read(os.path.join(ROOT, "LongFibWave.pine"))
              for n in ["FIB protocol"] + [f"FIB {k} {x}" for k in ("4H", "日足") for x in ("起点", "終点", "方向", "波ID", "状態", "更新確定時刻")]))
    check("S 方向・観察期間の選択肢は PointMasterVerifierV2 と同じ",
          'options = ["LONG / SHORT 別", "LONG＋SHORT合算", "LONGのみ", "SHORTのみ"]' in code and 'options = ["全期間", "5分", "15分", "30分"]' in code
          and all(x in read(os.path.join(ROOT, "PointMasterVerifierV2.pine")) for x in ('options = ["LONG / SHORT 別", "LONG＋SHORT合算", "LONGのみ", "SHORTのみ"]', 'options = ["全期間", "5分", "15分", "30分"]')))
    check("S 表・ラベル・冒頭に「タッチ足確定後の反応」の明記", s.count("タッチ足確定後の反応") >= 5 and "タッチ足確定後の反応" in read(os.path.join(ROOT, "ZONE_CONFLUENCE_REACTION_XAU_ja.md")))
    ind = [ln for ln in s.split("\n") if ln.strip() and not ln.lstrip().startswith("//")]
    bad = [ln for ln in ind if (len(ln) - len(ln.lstrip(" "))) % 4 not in (0, 1)]
    check("S 継続行以外のインデントは 4 の倍数、タブなし", not bad and "\t" not in s, str(bad[:3]))
    check("S 冒頭と仕様書に未検証 (PINE_NOT_VERIFIED) の明記", "PINE_NOT_VERIFIED" in s.split("indicator(")[0]
          and "PINE_NOT_VERIFIED" in read(os.path.join(ROOT, "ZONE_CONFLUENCE_REACTION_XAU_ja.md")))
    mine = {"ZoneConfluenceReactionStatsXAU.pine", "tests/zcr_sim.py", "ZONE_CONFLUENCE_REACTION_XAU_ja.md"}
    try:
        stt = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
        lines = [x for x in stt.split("\n") if x.strip() and "__pycache__" not in x]
        other = [x for x in lines if x[3:] not in mine]
        check("S git status: この 3 ファイル以外は未変更", not other, str(other[:5]))
    except Exception as ex:        # noqa: BLE001
        check("S git status: この 3 ファイル以外は未変更", False, repr(ex))


def main():
    seeds = [int(x) for x in sys.argv[1:]] or [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
    static()
    fixed_cases()
    kinds()
    bars, ov = random_vs_oracle(seeds)
    causality(bars, ov)
    mutations(random_bars(10), RANDOM_PRM[10 % len(RANDOM_PRM)])
    bad = 0
    for name, ok, det in RESULTS:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok and not det.startswith("events=") else "  " + det))
        bad += 0 if ok else 1
    print(f"{len(RESULTS) - bad}/{len(RESULTS)} passed")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
