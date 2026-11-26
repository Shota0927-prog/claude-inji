"""ZCR-9 frozen checks — tests/zcr9_reference.pine (= ZoneConfluenceReactionStatsXAU.pine at 1f0469e).   python3 tests/zcr9_sim.py

The ZCR-9 version of tests/zcr_sim.py, kept for tests/zcs_sim.py (which imports it and compares its copies with ZCR-9).
Only the file it reads changed.


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
  D. the table numbers / texts of the "ZCR Display calc" section == the old table calculation of 47ebe23 (taken from git, same translator)
  R. the table drawing code itself run on a mock table API (bounds, vertical merges only, rows, columns, short cells)

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
PINE = os.path.join(ROOT, "tests", "zcr9_reference.pine")     # ZCR-9 frozen copy (ZCR-10 rewrote the indicator)
LAB = os.path.join(ROOT, "ZoneComboLabXAU.pine")
FEED = os.path.join(ROOT, "MtfPocFeedXAU.pine")
BEGIN, END = "// ==== ZCR Logic (begin) ", "// ==== ZCR Logic (end) "
M1, M5 = 60_000, 300_000
T0 = 1_767_574_800_000          # 2026-01-05 01:00 UTC
MT = 0.01
NS, NF, NFT = 24, 50, 6
EDGE, CLOSE = "接触側の帯端", "タッチ足終値"
START0 = 1_577_836_800_000      # 2020-01-01 00:00 UTC (the default of the start input)
ZE_KEYS = ["zeProto"] + [f"ze{k}{x}" for k in ("4", "D") for x in "OEDIST"]
FEEDS = ([f"f{k}{x}" for k in (1, 2, 3) for x in "ulia"] + [f"s{k}{x}" for k in (1, 2, 3, 4) for x in ("h", "ht", "l", "lt")]
         + [f"zd{x}{k}" for k in (1, 2, 3, 4) for x in "LUT"] + [f"g{k}{x}" for k in (1, 2, 3, 4) for x in ("k", "kc", "c", "d", "t", "b")]
         + ["zgPk1", "zgPk4", "zgPkD"] + ZE_KEYS)
GN = ["ZA-1H", "ZA-4H", "ZA-D", "ZB-1m", "ZB-5m", "ZC-1H", "ZC-4H", "ZC-D", "ZC-W", "ZD-1H", "ZD-4H", "ZD-D", "ZD-W",
      "ZE-4H", "ZE-D", "ZF-FVG-1H", "ZF-FVG-4H", "ZF-FVG-D", "ZF-FVG-W", "ZG-1H", "ZG-4H", "ZG-D", "ZF-iFVG-1H", "ZF-iFVG-4H", "ZF-iFVG-D", "ZF-iFVG-W"]
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
OFF = {"zcP0Mode": CLOSE, "zaUse2": False, "zaUse3": False, "zbUse1": False, "zbUse2": False, "zcUse3": False, "zcUse4": False, "zdUse2": False, "zdUse3": False,
       "zdUse4": False, "zeUse": False, "zgUse1": False, "zgUse4": False, "zgUseD": False,
       "zfUse1": False, "zfUse2": False, "zfUse3": False, "zfUse4": False}
ONLY_ZC = dict(OFF, zcUse1=True, zcUse2=True, zcUse3=True, zcUse4=True)


class Runner:
    """bars: dicts t (5m open time), tc (default t + 5m), o, h, l, c, p1 / p5 (EMA of the previous confirmed bar), feeds by name
    (missing = na), conf (False = an unconfirmed realtime update)."""

    def __init__(self, overrides=None, source=None, run=True, maxrow=1_000_000, maxpend=1_000_000_000):
        s = source if source is not None else read(PINE)
        cap = "int   ZC_MAXROW = 300 "          # the row cap of the indicator; the tests lift it unless a case is about the cap
        assert s.count(cap) == 1, "ZC_MAXROW declaration changed"
        s = s.replace(cap, f"int   ZC_MAXROW = {maxrow} ")
        cap2 = "int   ZC_MAXPEND = 2000 "       # ZCR-8: the cap of the tracked observations; lifted unless a case is about it
        if cap2 in s:
            s = s.replace(cap2, f"int   ZC_MAXPEND = {maxpend} ")
        ov0 = dict(overrides or {})
        if "zcP0Mode" in ov0 and "zcP0Mode = input" not in s:      # an older source (before ZCR-8): always the close
            assert ov0.pop("zcP0Mode") == CLOSE
        overrides = ov0
        self.code = compile(ap.Translator().translate(ap.logical_lines(logic(s))), "<ZCR logic>", "exec")
        inp = ap.inputs(s)
        inp.setdefault("zcStart", START0)        # input.time is not parsed by ap.inputs
        for k in (overrides or {}):
            if k not in inp:
                raise KeyError(k)
        for k in ("zcWarm", "zbWarm1"):          # the tests count from the first bar unless a case sets the warm-ups
            if k not in (overrides or {}):
                inp[k] = 0
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
        """output + queue, and (ZCR-8) the records of the events whose 30-minute windows are done but whose first-touch is still open
        (not output by the indicator; made here by the indicator's own f_zcFinal on a scratch queue / state, nothing changed)"""
        e = self.env
        extra = []
        pend = [o for o in e["zcPend"] if all(w != 0 for w in o.wSt)]
        if pend:
            q0, st0 = e["zcQ"], e["st"]
            e["zcQ"], e["st"] = [], copy.copy(st0)
            try:
                for o in pend:
                    e["f_zcFinal"](o)
                extra = [list(q.v) for q in e["zcQ"]]
            finally:
                e["zcQ"], e["st"] = q0, st0
        return [r for _, r in self.out] + [list(q.v) for q in e["zcQ"]] + extra

    def fsys(self, k):
        """ZCR-8 first-touch arrays of system k (1..4): {set mask: list} and the 5 summary rows"""
        e = self.env
        a = ("fc", "fc2", "fc3", "fc4")[k - 1]
        return ({m: list(getattr(r, a)) for m, r in zip(e["zrMask"], e["zrRow"])}, [list(getattr(r, a)) for r in e["zrSum"]])

    def pending(self):
        return [dict(id=o.id, t0=o.t0, p0=o.p0, d=o.d, mask=o.mask, nEv=o.nEv, nRaw=o.nRaw, rTop=o.rTop, rBot=o.rBot, edge=o.edge,
                     cPos=o.cPos, nPl=o.nPl, aux=o.aux, flags=o.flags, onMask=o.onMask, side=o.side, rmin=list(o.rMin), alo=list(o.aLo), ahi=list(o.aHi),
                     wst=list(o.wSt), wmfe=list(o.wMfe), wmae=list(o.wMae), wnb=list(o.wNb), p0c=getattr(o, "p0c", None), p0e=getattr(o, "p0e", None),
                     fst=list(getattr(o, "fSt", None) or []), fmin=list(getattr(o, "fMin", None) or []), th=getattr(o, "th", None), tl=getattr(o, "tl", None),
                     tbj=None if getattr(o, "tbJ", None) is None else list(o.tbJ)) for o in self.env["zcPend"]]

    def rows(self):
        e = self.env
        return {m: (list(r.c), list(r.hist), list(r.ev)) for m, r in zip(e["zrMask"], e["zrRow"])}

    def sums(self):
        return [(list(r.c), list(r.hist), list(r.ev)) for r in self.env["zrSum"]]

    def rows2(self):
        """the second system: only the events that had an evidence already in contact"""
        e = self.env
        return {m: (list(r.c2), list(r.hist2), list(r.ev2)) for m, r in zip(e["zrMask"], e["zrRow"])}

    def sums2(self):
        return [(list(r.c2), list(r.hist2), list(r.ev2)) for r in self.env["zrSum"]]

    def sysrows(self, k):
        """system k (1 all / 2 had an evidence in contact / 3 one place on the bar / 4 both) of every set row and of the 4 summary rows"""
        f = {1: lambda r: (r.c, r.hist, r.ev), 2: lambda r: (r.c2, r.hist2, r.ev2), 3: lambda r: (r.c3, r.hist3, r.ev3), 4: lambda r: (r.c4, r.hist4, r.ev4)}[k]
        e = self.env
        return ({m: tuple(list(x) for x in f(r)) for m, r in zip(e["zrMask"], e["zrRow"])}, [tuple(list(x) for x in f(r)) for r in e["zrSum"]])

    def zones(self):
        return sorted((q.gid, q.sub, q.tb, q.tt, q.inv) for q in self.env["zxZ"])

    def state(self):
        e = self.env
        z = e["st"]
        return dict(nEv=z.nEv, nUnk=z.nUnk, nCont=z.nCont, nDone=z.nDone, nOut=z.nOut, nBad=z.nBad, nMa1Ev=z.nMa1Ev, nMa5Ev=z.nMa5Ev, nZeEv=z.nZeEv,
                    nEvOn=z.nEvOn, nMultiBar=z.nMultiBar, nPre=z.nPre,
                    nIfvg=z.nIfvg, nFvgDead=z.nFvgDead, nFxK1=getattr(z, "nFxK1", 0), nFxK2=getattr(z, "nFxK2", 0), nFxEmpty=getattr(z, "nFxEmpty", 0), nFtCut=getattr(z, "nFtCut", 0), nTa=[getattr(z, "nTa5", 0), getattr(z, "nTa10", 0), getattr(z, "nTa15", 0)],
                    nTb=[getattr(z, "nTbR", 0), getattr(z, "nTbA", 0), getattr(z, "nTbU", 0), getattr(z, "nTbMay", 0)], maUnk=list(e["zcMaUnk"]), nZone=list(e["zcNZone"]), why=list(e["zcWhy"][:2]),
                    on=sorted((q.gid, q.tb, q.tt) for q in e["zcOn"]), act=self.zones(), zeBad=list(e["zcZeBad"]), zdBad=list(e["zcZdBad"]),
                    zeStat=list(e["lbZeStat"]), zdStat=list(e["lbZdStat"]))

    def snapshot(self):
        return copy.deepcopy(dict(rec=self.records(), pend=self.pending(), rows=self.rows(), sums=self.sums(), rows2=self.rows2(), sums2=self.sums2(), sys3=self.sysrows(3), sys4=self.sysrows(4), st=self.state(),
                                  f=[self.fsys(k) for k in (1, 2, 3, 4)] if self.env["zrSum"] and "fc" in self.env["zrSum"][0]._fields else None, out=[(i, r) for i, r in self.out], created=list(self.created)))


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


# side-mask bits by evidence ID and side: ZA upper 0-2 / lower 3-5, ZC high 6-9 / low 10-13, ZG top 14-16 / bottom 17-19
SIDE0 = {}
for _k in range(3):
    SIDE0[_k] = (lambda k: lambda sub: 1 << ((0 if sub == 1 else 3) + k))(_k)
    SIDE0[19 + _k] = (lambda k: lambda sub: 1 << ((14 if sub == 1 else 17) + k))(_k)
for _k in range(4):
    SIDE0[5 + _k] = (lambda k: lambda sub: 1 << ((6 if sub == 1 else 10) + k))(_k)


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
                 on=False, outT=None, inv=False, aux=0, side=SIDE0.get(gid, lambda s_: 0)(sub), ma=False)
        z.update(kw)
        return z
    ma = [mk(3, 0, None, None, ma=True, ok=False), mk(4, 0, None, None, ma=True, ok=False)]
    n_zone = [0] * 26

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
    ma1_n = 0

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
                                z["aux"] |= (1 << (8 + k)) if cnt == 3 else 0
        body_hi, body_lo = max(b["o"], b["c"]), min(b["o"], b["c"])
        for z in [z for z in zones if 19 <= z["gid"] <= 21]:
            if (body_hi > z["ctr"] + P["zgRev"] + EPS) if z["sub"] == 1 else (body_lo < z["ctr"] - P["zgRev"] - EPS):
                drop(z)

    events, unk, unk_cnt, cont, n_pre, n_multi = [], 0, {}, 0, 0, 0
    edge_mode = P["zcP0Mode"] == EDGE
    n_k1, n_k2, n_empty = 0, 0, 0
    fx_bars = set()                 # bars on which a ZF zone (FVG or iFVG) was touched: the only bars the direction condition can change
                                    # (directly, or through the contact state an FVG carries into its iFVG)
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
        v1 = b.get("p1")
        if v1 is not None:               # ZB-1m warm-up: the first zbWarm1 valid values are still unknown
            ma1_n += 1
            if ma1_n <= P["zbWarm1"]:
                v1 = None
        for k, v in ((0, v1), (1, b.get("p5"))):
            ma[k]["ok"] = bool(zb_use[k] and v is not None)
            if ma[k]["ok"]:
                ma[k]["lo"], ma[k]["hi"] = tk(v - zh), tk(v + zh)
            elif zb_use[k]:
                ma_unk[k] += 1
        touched = [z for z in zones + [m for m in ma if m["ok"]] if z["hi"] >= l and z["lo"] <= h]
        live = tc >= P["zcStart"] and bi >= P["zcWarm"]

        def fvg(z):
            """a normal FVG (not inverted): only these carry the direction condition"""
            return 15 <= z["gid"] <= 18 and not z["inv"]

        def own_dir(z):
            """K1: the approach to the FVG's own band (open outside: that side; open inside: the previous close; else unknown)"""
            if o > z["hi"]:
                return 1
            if o < z["lo"]:
                return -1
            if pc is None:
                return 0
            return 1 if pc > z["hi"] else -1 if pc < z["lo"] else 0
        k1_out = [z for z in touched if fvg(z) and own_dir(z) != z["sub"]]
        if any(15 <= z["gid"] <= 18 for z in touched):
            fx_bars.add(bi)
        n_k1 += len(k1_out)
        touched = [z for z in touched if z not in k1_out]          # as if they did not exist on this bar

        def direction(mem, c_lo, c_hi):
            """by the open against C; an open inside C: by the previous close against the members' own common band U (not clipped)"""
            if o > c_hi:
                return 1
            if o < c_lo:
                return -1
            if pc is None:
                return 0
            u_lo, u_hi = max(z["lo"] for z in mem), min(z["hi"] for z in mem)
            return 1 if pc > u_hi else -1 if pc < u_lo else 0
        pl = [(mem, c_lo, c_hi, direction(mem, c_lo, c_hi)) for mem, c_lo, c_hi in places_of(touched, l, h)]
        n_pl = 0
        new = []
        def egid(z):
            """evidence ID at the touch: a ZF zone is an FVG (15..18) or, once inverted, an iFVG (22..25) — never both"""
            return z["gid"] + 7 if 15 <= z["gid"] <= 18 and z["inv"] else z["gid"]
        used, k2_out = set(), set()
        for mem0, c_lo, c_hi, d in pl:                # by price, low to high; no order of contact inside the bar
            # K2: with a direction, a normal FVG facing the other way leaves this place's evidence (C and d are kept)
            xs = [z for z in mem0 if d != 0 and fvg(z) and z["sub"] != d]
            mem = [z for z in mem0 if z not in xs]
            n_k2 += len(xs)
            k2_out |= {z["id"] for z in xs}
            used |= {z["id"] for z in mem}
            if not mem:
                n_empty += 1
                continue
            gids = sorted(set(egid(z) for z in mem))
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
                aux |= z["aux"]
            on_mask = side = 0
            for z in mem:
                on_mask |= (1 << egid(z)) if z["on"] else 0
                side |= z["side"]
            by_pc = c_lo <= o <= c_hi
            # ZCR-8: the band edge = the touched side of UA, the common band of the adopted members themselves (not clipped)
            ua_lo, ua_hi = max(z["lo"] for z in mem), min(z["hi"] for z in mem)
            p0e = ua_hi if d == 1 else ua_lo
            p0 = p0e if edge_mode else c
            u1, u5 = zb_use[0] and not ma[0]["ok"], zb_use[1] and not ma[1]["ok"]
            edge = o if by_pc else c_hi if d == 1 else c_lo
            if d == 1:
                cpos = 0 if c > c_hi else 1 if c >= c_lo else 2
            else:
                cpos = 0 if c < c_lo else 1 if c <= c_hi else 2
            tb = touch_bar(d, p0, h, l, c) if edge_mode else None
            ev = dict(id=len(events) + 1, t0=tc, p0=p0, p0c=c, p0e=p0e, mode=P["zcP0Mode"], th=h, tl=l, tb=tb, tbj=None if tb is None else list(tb["code"]), d=d, mask=mask, nEv=len(gids), nRaw=len(mem), rTop=c_hi, rBot=c_lo,
                      edge=edge, cPos=cpos, aux=aux, bar=bi, onMask=on_mask, side=side,
                      flags=(512 if u1 else 0) + (1024 if u5 else 0) + (2048 if 9 in ze_stat else 0) + (4096 if on_mask else 0) + (8192 if by_pc else 0) + (16384 if xs else 0))
            events.append(ev)
            new.append(ev)
        for ev in new:
            ev["nPl"] = n_pl
        if live and n_pl >= 2:
            n_multi += 1
        for z in touched:
            if z["id"] in k2_out and z["id"] not in used:      # K3: no contact mark from a touch that was left out
                continue
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
    n_tb = [0, 0, 0, 0]               # ZCR-9: decided on the touch bar rebound / adverse / unknown; unconfirmed rebound turned unknown
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
        mfe0 = 0
        tb = ev["tb"]
        if tb is not None:                  # ZCR-9 band edge: what the touch bar shows for certain (after the contact)
            mae, mfe0 = tb["adv"], tb["fav_close"]
            for q in range(3):
                if tb["conf"][q]:           # the close confirmed the reach: 0 minutes; adverse before it unknown in order -> 0 .. touch adverse
                    rmin[q], alo[q], ahi[q] = 0, 0, tb["adv"]
        mae0 = mae
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
                    wmfe[hh] = max([mfe0] + [(x[3] - p0 if d == 1 else p0 - x[4]) for x in inw])
                    wmae[hh] = max([mae0] + [(p0 - x[4] if d == 1 else x[3] - p0) for x in inw])
                else:
                    wst[hh] = 2                       # no bar inside the window: unmeasurable
                    why[0] += 1
            else:
                wnb[hh] = 0 if last_tc is None else wnb[hh]
        # ZCR-8 first-touch: every width alone, from the next bar, no time limit; the open first, then the bar's range
        fst, fmin, fbar = [0] * 3, [None] * 3, [None] * 3
        maybe = [False] * 3
        if tb is not None:
            for q in range(3):
                if tb["res"][q]:
                    fst[q], fbar[q], fmin[q] = tb["res"][q], ev["bar"], 0
                    n_tb[tb["res"][q] - 1] += 1
                maybe[q] = tb["code"][q] == 4
        for i, (tc, bad, o, h, l) in later:
            if all(fst):
                break
            for q in range(3):
                if fst[q]:
                    continue
                if bad:
                    res = 4
                else:
                    on_ = d * (o - p0)
                    fav = h - p0 if d == 1 else p0 - l
                    adv = p0 - l if d == 1 else h - p0
                    w = W[q]
                    if on_ >= w:
                        res = 1
                    elif -on_ >= w:
                        res = 2
                    elif fav >= w and adv >= w:
                        res = 3
                    elif fav >= w:
                        res = 1
                    elif adv >= w:
                        res = 2
                    else:
                        res = 0
                if res == 2 and maybe[q]:          # an unconfirmed rebound in the touch bar: not a sure adverse-first
                    res = 3
                    n_tb[3] += 1
                    ev["flags"] |= 32768
                if res:
                    fst[q], fbar[q] = res, i
                    fmin[q] = math.floor((tc - t0) / M1 + 0.5) if res <= 3 else None
        ffin = max(fbar) if all(fst) else None
        # the record goes out when the 30-minute windows are done AND every width is decided
        ev.update(rmin=rmin, alo=alo, ahi=ahi, wst=wst, wmfe=wmfe, wmae=wmae, wnb=wnb, wfin=fin, fst=fst, fmin=fmin,
                  fin=None if fin is None or ffin is None else max(fin, ffin))
    return dict(events=events, unk=unk, unk_cnt=unk_cnt, cont=cont, nPre=n_pre, nMulti=n_multi, nBad=n_bad, maUnk=ma_unk, nZone=n_zone, why=why,
                on=sorted((z["gid"], z["lo"], z["hi"]) for z in zones + ma if z["on"]),
                act=sorted((z["gid"], z["sub"], z["lo"], z["hi"], z["inv"]) for z in zones), nbars=len(bars),
                zeBad=ze_bad, zdBad=zd_bad, zeStat=ze_stat, zdStat=zd_stat, nIfvg=n_ifvg[0], nFvgDead=n_fdead[0],
                nFxK1=n_k1, nFxK2=n_k2, nFxEmpty=n_empty, fxBars=fx_bars, nTb=n_tb)


def record_of(ev):
    """the event record as the spec's table defines it (35 values)"""
    v = [None] * NF
    v[0:14] = [ev["id"], ev["t0"] / 1000.0, ev["p0"] * MT, ev["d"], ev["mask"], ev["nEv"], ev["nRaw"], ev["rTop"] * MT, ev["rBot"] * MT,
               ev["edge"] * MT, ev["d"] * (ev["p0c"] - ev["edge"]) * MT, ev["cPos"], ev["nPl"], ev["aux"]]
    v[35:44] = [1 if ev["mode"] == EDGE else 0, ev["p0c"] * MT, ev["p0e"] * MT] + list(ev["fst"]) + list(ev["fmin"])
    v[44:47] = [touch_adv(ev) * MT, ev["th"] * MT, ev["tl"] * MT]
    v[47:50] = list(ev["tb"]["code"]) if ev["tb"] is not None else [None] * 3
    fl = ev["flags"]
    for j in range(3):
        if ev["rmin"][j] is None:
            v[14 + j] = 0 if ev["wst"][2] == 1 else -1
        else:
            v[14 + j] = -2 if ev["rmin"][j] == 0 else ev["rmin"][j]
            v[17 + 2 * j], v[18 + 2 * j] = ev["alo"][j] * MT, ev["ahi"][j] * MT
            if ev["alo"][j] != ev["ahi"][j]:
                fl += 64 << j
    for h in range(3):
        v[29 + h] = ev["wnb"][h]
        if ev["wst"][h] == 1:
            v[23 + 2 * h], v[24 + 2 * h] = ev["wmfe"][h] * MT, ev["wmae"][h] * MT
            fl += 1 << h
            if ev["wnb"][h] < (1, 3, 6)[h]:
                fl += 8 << h
    v[32] = fl
    v[33] = ev["onMask"]
    v[34] = ev["side"]
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
                        if rm == 0:
                            c[base + 21 + j] += 1       # ZCR-9: reached by the touch bar's close (0 minutes)
                        else:
                            hist[(dh * 3 + j) * 30 + rm - 1] += 1
    return out


def touch_bar(d, p0, h, l, c):
    """ZCR-9 (band-edge start only): per width, what the touch bar shows for certain. The adverse extreme is after the contact; the close
    is after it; the favourable extreme may be before it unless the close confirms it."""
    clo = d * (c - p0)
    fav = h - p0 if d == 1 else p0 - l
    adv = p0 - l if d == 1 else h - p0
    conf, code, res = [], [], []
    for w in (ticks(5.0), ticks(10.0), ticks(15.0)):
        cf, ah = clo >= w, adv >= w
        fm = fav >= w and not cf
        conf.append(cf)
        code.append(3 if cf and ah else 1 if cf else 5 if ah and fm else 2 if ah else 4 if fm else 0)
        res.append(3 if cf and ah else 1 if cf else 3 if ah and fm else 2 if ah else 0)
    return dict(conf=conf, code=code, res=res, adv=max(0, adv), fav_close=max(0, clo))


def touch_adv(ev):
    """ZCR-8b: the touch bar's move from the measuring P0 to its adverse extreme (ticks, 0 or more)"""
    return max(0, ev["p0"] - ev["tl"] if ev["d"] == 1 else ev["th"] - ev["p0"])


def frows_of(events, key=lambda ev: ev["mask"]):
    """ZCR-8 first-touch arrays: ((direction * 3 + width) * NFT + result), result 0 rebound / 1 adverse / 2 unknown order / 3 tracking /
    4 unmeasurable / 5 cut by the cap"""
    out = {}
    for ev in events:
        f = out.setdefault(key(ev), [0] * (6 * NFT))
        di = 0 if ev["d"] == 1 else 1
        for j in range(3):
            f[(di * 3 + j) * NFT + {0: 3, 1: 0, 2: 1, 3: 2, 4: 4, 5: 5}[ev["fst"][j]]] += 1
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
    for a, b in (("nEv", len(ev)), ("nUnk", orc["unk"]), ("nCont", orc["cont"]), ("nBad", orc["nBad"]),
                 ("maUnk", orc["maUnk"]), ("nZone", orc["nZone"]), ("on", orc["on"]), ("act", orc["act"]), ("zeBad", orc["zeBad"]),
                 ("zdBad", orc["zdBad"]), ("zeStat", orc["zeStat"]), ("zdStat", orc["zdStat"]), ("nIfvg", orc["nIfvg"]), ("nFvgDead", orc["nFvgDead"]),
                 ("nMa1Ev", sum(1 for e in ev if e["flags"] & 512)), ("nMa5Ev", sum(1 for e in ev if e["flags"] & 1024)),
                 ("nEvOn", sum(1 for e in ev if e["onMask"])), ("nMultiBar", orc["nMulti"]), ("nPre", orc["nPre"]), ("nZeEv", sum(1 for e in ev if e["flags"] & 2048)), ("why", orc["why"]),
                 ("nFxK1", orc["nFxK1"]), ("nFxK2", orc["nFxK2"]), ("nFxEmpty", orc["nFxEmpty"]),
                 ("nTa", [sum(1 for e in ev if e["fin"] is not None and touch_adv(e) >= w) for w in (ticks(5.0), ticks(10.0), ticks(15.0))]), ("nTb", orc["nTb"])):
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
    keys = ("id", "t0", "p0", "d", "mask", "nEv", "nRaw", "rTop", "rBot", "edge", "cPos", "nPl", "aux", "flags", "onMask", "side", "rmin", "alo", "ahi",
            "wst", "wmfe", "wmae", "p0c", "p0e", "fst", "fmin", "th", "tl", "tbj")
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
    # systems 3 / 4: the events of bars with exactly one place, and those of them that had an evidence already in contact
    for k, sel in ((3, [e for e in ev if e["nPl"] == 1]), (4, [e for e in ev if e["nPl"] == 1 and e["onMask"]])):
        gr, gs = r.sysrows(k)
        if {m: v for m, v in gr.items() if any(v[0]) or any(v[1]) or any(v[2])} != {m: tuple(v) for m, v in rows_of(sel).items()}:
            det.append(f"system {k} rows differ")
        so = rows_of(sel, key=lambda e: min(e["nEv"], 3))
        for g in (1, 2, 3):
            if gs and tuple(gs[g - 1]) != tuple(so.get(g, empty)):
                det.append(f"system {k} summary row {g} differs")
        if gs and tuple(gs[3]) != tuple(rows_of(sel, key=lambda e: 0).get(0, empty)):
            det.append(f"system {k} summary row all differs")
    # second system: the same aggregation over the events that had an evidence already in contact
    ev2 = [e for e in ev if e["onMask"]]
    rows2_o = rows_of(ev2)
    got2 = {m: v for m, v in r.rows2().items() if any(v[0]) or any(v[1]) or any(v[2])}
    if got2 != rows2_o:
        det.append("second-system rows differ")
    s2o = rows_of(ev2, key=lambda e: min(e["nEv"], 3))
    s2i = r.sums2()
    for g in (1, 2, 3):
        if s2i and tuple(s2i[g - 1]) != tuple(s2o.get(g, empty)):
            det.append(f"second-system summary row {g} differs")
    if s2i and tuple(s2i[3]) != tuple(rows_of(ev2, key=lambda e: 0).get(0, empty)):
        det.append("second-system summary row all differs")
    # ZCR-8 first-touch: the 4 systems, set rows and summary rows (1 / 2 / 3+ evidences, all)
    zf = [0] * (6 * NFT)
    for k, sel in ((1, ev), (2, [e for e in ev if e["onMask"]]), (3, [e for e in ev if e["nPl"] == 1]), (4, [e for e in ev if e["nPl"] == 1 and e["onMask"]])):
        gr, gs = r.fsys(k)
        if {m: v for m, v in gr.items() if any(v)} != frows_of(sel):
            det.append(f"first-touch system {k} rows differ")
        so = frows_of(sel, key=lambda e: min(e["nEv"], 3))
        if gs and ([gs[g - 1] for g in (1, 2, 3)] != [so.get(g, zf) for g in (1, 2, 3)] or gs[3] != frows_of(sel, key=lambda e: 0).get(0, zf)):
            det.append(f"first-touch system {k} summary rows differ")
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
    dict(ALL_ON, zHalf=1.0, zcMax=3, zcDepMin=20, zgExp1=False, zbWarm1=400),
    dict(ALL_ON, zHalf=0.0, zcDepW=0.5, zcDepMin=5, zgHalf=0.0, zcWarm=200),
    dict(zHalf=3.0, zcWarm=300, zcStart=T0 + 500 * M5),
]


def random_vs_oracle(seeds):
    last = None
    for seed in seeds:
        ov = dict(RANDOM_PRM[seed % len(RANDOM_PRM)], zcP0Mode=CLOSE if seed % 2 == 0 else EDGE)     # ZCR-8: both start points
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
                       ("second", sum(1 for e in ev if e["nPl"] > 1)), ("maunk", sum(1 for e in ev if e["flags"] & 1536)), ("evon", sum(1 for e in ev if e["onMask"])), ("npre", orc["nPre"]),
                       ("side", sum(1 for e in ev if e["side"])), ("bypc", sum(1 for e in ev if e["flags"] & 8192)),
                       ("zeunk", sum(1 for e in ev if e["flags"] & 2048)), ("ifvg", sum(1 for e in ev if e["mask"] >> 22)), ("one", sum(1 for e in ev if e["nPl"] == 1)),
                       ("triple", sum(1 for e in ev if e["aux"] & 0x700)), ("why0", orc["why"][0]), ("why1", orc["why"][1]),
                       ("pos0", sum(1 for e in ev if e["cPos"] == 0)), ("pos2", sum(1 for e in ev if e["cPos"] == 2)),
                       ("fxk1", orc["nFxK1"]), ("fxk2", orc["nFxK2"]), ("fx16384", sum(1 for e in ev if e["flags"] & 16384)),
                       ("ft_reb", sum(1 for e in ev for j in range(3) if e["fst"][j] == 1)), ("ft_adv", sum(1 for e in ev for j in range(3) if e["fst"][j] == 2)),
                       ("ft_unk", sum(1 for e in ev for j in range(3) if e["fst"][j] == 3)), ("ft_trk", sum(1 for e in ev for j in range(3) if e["fst"][j] == 0)),
                       ("ft_bad", sum(1 for e in ev for j in range(3) if e["fst"][j] == 4)), ("ft_late", sum(1 for e in ev for j in range(3) if (e["fmin"][j] or 0) > 30)),
                       ("edge_ne_close", sum(1 for e in ev if e["p0e"] != e["p0c"])), ("ta5_edge", sum(1 for e in ev if e["mode"] == EDGE and touch_adv(e) >= ticks(5.0))), ("tb1", sum(1 for e in ev if e["tb"] for q in range(3) if e["tb"]["code"][q] == 1)),
                       ("tb2", sum(1 for e in ev if e["tb"] for q in range(3) if e["tb"]["code"][q] == 2)), ("tb3", sum(1 for e in ev if e["tb"] for q in range(3) if e["tb"]["code"][q] == 3)),
                       ("tb4", sum(1 for e in ev if e["tb"] for q in range(3) if e["tb"]["code"][q] == 4)), ("tb5", sum(1 for e in ev if e["tb"] for q in range(3) if e["tb"]["code"][q] == 5)),
                       ("tb32768", sum(1 for e in ev if e["flags"] & 32768)), ("wait_ft", sum(1 for e in ev if e["wfin"] is not None and e["fin"] is None))) \
                + tuple((n[:2], sum(1 for e in ev if e["mask"] & G[n])) for n in ("ZA-4H", "ZB-1m", "ZC-D", "ZD-4H", "ZE-4H", "ZF-FVG-4H", "ZG-4H")) + (("ZI", sum(1 for e in ev if e["mask"] & G["ZF-iFVG-4H"])),):
            COVER[k_] = COVER.get(k_, 0) + v_
        rich = len(ev) > 20 and len(set(e["mask"] for e in ev)) > 3
        check(f"C random seed {seed} == oracle ({ov})", ok and rich,
              f"events={len(ev)} sets={len(set(e['mask'] for e in ev))} unk={orc['unk']} cont={orc['cont']} bad={orc['nBad']} out={len(r.out)} "
              f"queue={len(r['zcQ'])} pend={len(r['zcPend'])} | {det}")
        inv = True
        sysv = {k: list(r.sysrows(k)[0].values()) + r.sysrows(k)[1][:4] for k in (1, 2, 3, 4)}

        def minus(x, y):
            return ([a - b for a, b in zip(x[0], y[0])], [a - b for a, b in zip(x[1], y[1])], [a - b for a, b in zip(x[2][:2], y[2][:2])] + [x[2][2]])
        # the 2 x 3 display combinations: places {all, one} x {include = base, only = with-contact, exclude = base - with-contact}
        combos = [sysv[1], sysv[2], [minus(x, y) for x, y in zip(sysv[1], sysv[2])], sysv[3], sysv[4], [minus(x, y) for x, y in zip(sysv[3], sysv[4])]]
        nonneg = lambda d: min(d[0][i] for i in range(len(d[0])) if i % NS not in (8, 9, 10, 11, 12, 13, 14, 15)) >= 0 and min(d[1]) >= 0 and min(d[2]) >= 0   # noqa: E731
        inv &= all(nonneg(d) for cmb in combos for d in cmb)
        inv &= all(nonneg(minus(x, y)) for x, y in zip(sysv[1], sysv[3])) and all(nonneg(minus(x, y)) for x, y in zip(sysv[2], sysv[4]))
        for c, hist, evn in [d for cmb in combos for d in cmb]:
            for di in range(2):
                for h in range(3):
                    base = (di * 3 + h) * NS
                    inv &= evn[di] == c[base] + c[base + 1] + c[base + 19] and c[base + 20] <= c[base]
                    for j in range(3):
                        inv &= c[base + 2 + j] <= c[base] and sum(hist[((di * 3 + h) * 3 + j) * 30:][:30]) + c[base + 21 + j] == c[base + 2 + j]
                        inv &= c[base + 10 + j] <= c[base + 13 + j] and sum(hist[((di * 3 + h) * 3 + j) * 30 + (5, 15, 30)[h]:][:30 - (5, 15, 30)[h]]) == 0
                    inv &= c[base + 2] >= c[base + 3] >= c[base + 4]
        # ZCR-8 first-touch: rebound + adverse + unknown order + tracking + unmeasurable + cut = events, in every system and the 2 "exclude" differences
        fs = {k: list(r.fsys(k)[0].values()) + r.fsys(k)[1][:4] for k in (1, 2, 3, 4)}
        evs = {k: [x[2] for x in sysv[k]] for k in (1, 2, 3, 4)}
        for k in (1, 2, 3, 4):
            for f, evn in zip(fs[k], evs[k]):
                inv &= all(sum(f[(di * 3 + j) * NFT:(di * 3 + j + 1) * NFT]) == evn[di] and min(f) >= 0 for di in range(2) for j in range(3))
        for a_, b_ in ((1, 2), (3, 4)):
            for fa, fb, ea, eb in zip(fs[a_], fs[b_], evs[a_], evs[b_]):
                inv &= all(sum(fa[(di * 3 + j) * NFT:(di * 3 + j + 1) * NFT]) - sum(fb[(di * 3 + j) * NFT:(di * 3 + j + 1) * NFT]) == ea[di] - eb[di]
                           and min(x - y for x, y in zip(fa, fb)) >= 0 for di in range(2) for j in range(3))
        tot = r.sums()[3]
        inv &= sum(v[2][0] + v[2][1] for v in r.rows().values()) == tot[2][0] + tot[2][1] == len(ev)
        check(f"B seed {seed}: 表示の全組合せ 2 × 3 (場所数 全件 / 1 のみ × 含める / のみ / 除く) の行ごとに イベント = 計測可能 + 計測不能 + 待ち、本数不足 <= 計測可能、到達 <= 計測可能、$5 >= $10 >= $15、度数の合計 = 到達、集合行の合計 = 全体", inv)
        last = (bars, ov)
    need = dict(one=500, ZI=5, evon=200, npre=50, side=500, bypc=20, ev=3000, multi=500, unmeas=20, short=20, amb=100, unk=20, cont=2000, r15=100, bad=50, pend=1, queue=1, sell=1000, second=20, maunk=1,
                zeunk=1, ifvg=5, triple=5, fxk1=100, fxk2=5, fx16384=3, ft_reb=3000, ft_adv=3000, ft_unk=50, ft_trk=10, ft_bad=20, ft_late=500, edge_ne_close=1000, ta5_edge=10, tb1=50, tb2=50, tb3=5, tb4=20, tb5=5, tb32768=5, wait_ft=1, why0=10, why1=10, pos0=200, pos2=200, ZA=50, ZB=200, ZC=200, ZD=50, ZE=50, ZF=50, ZG=20)
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
          near(rec[1], (T0 + 2 * M5) / 1000.0) and near(rec[2], 4309.0) and rec[3] == 1 and rec[4] == ZCD and rec[5] == 1 and rec[6] == 1
          and near(rec[7], 4302.0) and near(rec[8], 4301.0) and near(rec[9], 4302.0) and near(rec[10], 7.0) and rec[11] == 0 and rec[12] == 1
          and rec[14:17] == [0, 0, 0] and rec[17:23] == [None] * 6 and rec[23:29] == [0.0] * 6 and rec[29:32] == [1, 3, 6] and rec[32] == 7
          and rec[33:35] == [0, 1 << 8], str(rec))
    case("A 6b タッチ足の終値の位置: 帯内で確定 = 1 (P0 は終値)", [(4310, 4310, 4299, 4300)], D,
         lambda r, ev, o: [(e["cPos"], e["edge"], e["p0"]) for e in ev] == [(1, 430200, 430000)])
    case("A 6c タッチ足の終値の位置: 帯の向こう側へ抜けて確定 = 2 (P0 は終値。終値 − 接触端 = −11)", [(4310, 4310, 4290, 4291)] + flat(4291, 7), D,
         lambda r, ev, o: [(e["cPos"], e["edge"], e["p0"]) for e in ev] == [(2, 430200, 429100)] and near(r.records()[0][10], -11.0))
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
          and (c[1], c[NS + 1], c[2 * NS], c[2 * NS + 20], c[2 * NS + 2], c[2 * NS + 3]) == (1, 1, 1, 1, 1, 0) and rec[14:17] == [25, 0, 0]
          and rec[32] == 4 + 32 and rec[29:32] == [0, 0, 1] and r["zcWhy"][0] == 2 and e8["fin"] == 3, f"{e8} rec={rec} | {det}")
    b8b = bars_from_rows([(4304, 4304, 4301, 4303), (4303, 4309, 4303, 4308), (4308, 4320, 4308, 4320)], D)
    for b in b8b[2:]:
        b["t"] += 600 * M5                   # a weekend: the first bar after it closes far beyond T0 + 30m
    r, o, ok, det = run_case(b8b, None)
    check("A 8b 期間内に足が 1 本も無い (休場明けの足は T0 + 30 分より後) → 3 期間とも計測不能で確定し、分母に入らない",
          ok and o["events"][0]["wst"] == [2, 2, 2] and o["events"][0]["rmin"] == [None] * 3 and r.records()[0][14:17] == [-1, -1, -1]
          and r.records()[0][32] == 0, f"{o['events'][0]} | {det}")
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
    r, ev, o = case("A 10 1 本の大きな足が離れた 2 か所に触れる: 別々のイベント (合算しない。場所数 2 を両方に記録)",
                    [(4310, 4310, 4279, 4290)], f10,
                    lambda r, ev, o: [(e["mask"], e["nEv"], e["nRaw"], e["d"], e["nPl"]) for e in ev] == [(ZCW, 1, 1, 1, 2), (ZCD, 1, 1, 1, 2)]
                    and sorted(r.rows()) == [ZCD, ZCW] and r["st"].nMultiBar == 1 and ev[0]["p0"] == ev[1]["p0"] and ev[0]["t0"] == ev[1]["t0"])
    case("A 10b 始値が 2 か所の間: 上の場所は下から (SHORT)、下の場所は上から (LONG)",
         [(4290, 4299, 4281.5, 4290)], f10,
         lambda r, ev, o: [(e["mask"], e["d"], e["nPl"]) for e in ev] == [(ZCW, 1, 2), (ZCD, -1, 2)])
    case("A 10c 離れた 2 か所を別の足でタッチ: 別々のイベント、後から合算しない",
         [(4304, 4304, 4301, 4303), (4303, 4303, 4281, 4282)], f10,
         lambda r, ev, o: [(e["mask"], e["nEv"]) for e in ev] == [(ZCD, 1), (ZCW, 1)])
    # 11 chain A-B-C where A and C do not overlap: never one set of three
    f11 = merge(zc(2, 1, 4300.0), zc(3, 1, 4303.5), zc(1, 1, 4307.0))     # bands 4298..4302 / 4301.5..4305.5 / 4305..4309
    case("A 11 連鎖 A–B–C (A と C は重ならない) を 1 本で全部タッチ: {C, B} と {A, B} の 2 イベント。3 つを 1 つの集合にしない。共通区間 C = 全員の帯の重なり",
         [(4312, 4312, 4297, 4300)], f11,
         lambda r, ev, o: [(e["mask"], e["rTop"], e["rBot"], e["nPl"]) for e in ev] == [(ZCD + ZCW, 430200, 430150, 2), (ZC4 + ZCW, 430550, 430500, 2)]
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
         lambda r, ev, o: [e["mask"] for e in ev] == [ZCW, ZC4] and ev[0]["rBot"] == 430550)
    # F1: places = maximal sets of touched zones sharing a price point (every member overlaps every other), same sets from both sides
    f4 = merge(zc(0, 1, 4312.0), zc(1, 1, 4309.0), zc(2, 1, 4306.0), zc(3, 1, 4303.0))      # bands 4310..4314 / 4307..4311 / 4304..4308 / 4301..4305
    want4 = sorted([ZC1 + ZC4, ZC4 + ZCD, ZCD + ZCW])
    ra_, oa, oka, _d = run_case([(4320, 4320, 4300, 4300.5)], f4)
    rb_, ob, okb, _d = run_case([(4295, 4315, 4295, 4314.5)], f4, start=4295.0)
    sa, sb = [e["mask"] for e in oa["events"]], [e["mask"] for e in ob["events"]]
    check("A F1 幅 $4 の線 4 本 (4312 / 4309 / 4306 / 4303) を 1 本でタッチ: 上からでも下からでも同じ 3 集合 {1H+4H} {4H+D} {D+W} (メンバーは全員が相互に重なる)",
          oka and okb and sorted(sa) == want4 and sorted(sb) == want4 and sa == sb == [ZCD + ZCW, ZC4 + ZCD, ZC1 + ZC4]
          and [e["nPl"] for e in oa["events"]] == [3, 3, 3] and [e["d"] for e in oa["events"]] == [1, 1, 1] and [e["d"] for e in ob["events"]] == [-1, -1, -1]
          and [(e["rBot"], e["rTop"]) for e in oa["events"]] == [(430400, 430500), (430700, 430800), (431000, 431100)], f"{sa} {sb}")
    fw = merge(zf(1, T0 - 3_600_000, 4350.0, 1, 4320.0, 4280.0), zc(2, 1, 4290.0), zc(3, 1, 4310.0))
    case("A F1b 広い帯 (FVG 4280..4320) の中に離れた 2 本の線: {広+線1} と {広+線2}。{広+線1+線2} にはしない", [(4330, 4330, 4270, 4275)], fw,
         lambda r, ev, o: [e["mask"] for e in ev] == [G["ZF-FVG-4H"] + ZCD, G["ZF-FVG-4H"] + ZCW] and sorted(r.rows()) == sorted([G["ZF-FVG-4H"] + ZCW, G["ZF-FVG-4H"] + ZCD])
         and [e["nPl"] for e in ev] == [2, 2] and r["st"].nMultiBar == 1, ov={"zfUse2": True})
    case("A F1c 上からの場所と下からの場所が同じ足にある: 場所ごとに方向を決め、全部をイベントにする (場所数 4)", [(4300, 4315, 4285, 4300)],
         merge(zc(0, 1, 4312.0), zc(1, 1, 4306.0), zc(2, 1, 4294.0), zc(3, 1, 4288.0)),
         lambda r, ev, o: [(e["mask"], e["d"], e["nPl"]) for e in ev] == [(ZCW, 1, 4), (ZCD, 1, 4), (ZC4, -1, 4), (ZC1, -1, 4)], start=4300.0)
    # G1: an open inside C is judged by the previous close against the members' own common band, not against the clipped C
    case("A G1 帯 4298..4302 の中に居続けた価格の小さなギャップ (直前終値 4301.8 → 始値 4300 / 高値 4300.5 / 安値 4299.5) は方向不明 (LONG にしない)",
         [(4305, 4305, 4305, 4305), (4305, 4305, 4301.8, 4301.8), (4300, 4300.5, 4299.5, 4300)], None,
         lambda r, ev, o: len(ev) == 0 and o["unk"] == 1 and o["cont"] == 0, feeds={2: D})
    g1b = bars_from_rows([(4305, 4305, 4305, 4305), (4305, 4305, 4301.8, 4301.8), (4300, 4300.5, 4299.5, 4300)], None, feeds={2: D})
    old_dir = "int dp  = f_zcDir(pLo, pHi, array.get(zcUL, k), array.get(zcUH, k), o)"
    src0 = read(PINE)
    rm = Runner(ONLY_ZC, source=src0.replace(old_dir, "int dp  = f_zcDir(pLo, pHi, pLo, pHi, o)")).run(g1b)
    check("X 変異を検出: 直前終値を切り詰めた C と比べる (旧定義) と、上の例は LONG のイベントになる", src0.count(old_dir) == 1 and rm["st"].nEv == 1 and rm["st"].nUnk == 0)
    r, ev, o = case("A G1b 直前終値で方向が決まった場合 (始値が既に C の中): 接触端 = 始値、状態フラグ 8192。始値で決まった場合は C の端・フラグなし",
                    [(4305, 4305, 4305, 4305), (4301, 4301.5, 4300, 4301)] + flat(4301, 7), D,
                    lambda r, ev, o: len(ev) == 1 and (ev[0]["d"], ev[0]["edge"], ev[0]["flags"], ev[0]["rTop"], ev[0]["rBot"]) == (1, 430100, 8192, 430150, 430000)
                    and near(r.records()[0][9], 4301.0) and near(r.records()[0][10], 0.0))
    # G3: ZB-1m warm-up
    b = bars_from_rows([(4310, 4310, 4310, 4310), (4310, 4310, 4310, 4310), (4310, 4310, 4301, 4305), (4320, 4320, 4320, 4320), (4320, 4320, 4301, 4305)], None)
    for x in b[1:]:
        x["p1"] = 4300.0
    r, o, ok, det = run_case(b, None, {"zbUse1": True, "zbWarm1": 3}, base=OFF)
    check("A G3 ZB-1m の助走 3 本: 有効値を受け取り始めてから 3 本の間は不明 (帯なし・不明の足に数える)。4 本目から根拠になる",
          ok and [e["bar"] for e in o["events"]] == [5] and r["zcMaUnk"] == [4, 0] and r["st"].ma1N == 5, f"{[e['bar'] for e in o['events']]} {r['zcMaUnk']} | {det}")
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
    case("A F2b 広い上昇 FVG の中を動いて線へ初めて到達 (ZCR-7): FVG の中で始まる足は FVG 自身の方向が不明なので FVG を根拠から外し (K1)、線だけの新規イベント。同じ構成の足は増えない",
         [(4330, 4330, 4318, 4319), (4319, 4319, 4315, 4316), (4316, 4316, 4311, 4313), (4313, 4313, 4310, 4311.5), (4311.5, 4312, 4309, 4310)],
         merge(zf(1, T0 - 3_600_000, 4350.0, 1, 4320.0, 4280.0), zc(3, 1, 4310.0)),
         lambda r, ev, o: [(e["bar"], e["mask"], e["onMask"]) for e in ev] == [(1, G["ZF-FVG-4H"], 0), (3, ZCW, 0)] and o["cont"] == 2 and r["st"].nFxK1 == 4,
         ov={"zfUse2": True})
    # J3: the "one place on the bar" systems are filled after the bar's places are all judged; later sums go to the same systems
    bj = bars_from_rows([(4310, 4310, 4279, 4290), (4290, 4290, 4270, 4272), (4272, 4272, 4265, 4266), (4266, 4279, 4266, 4278.5)] + flat(4278.5, 8), f10)
    rj = Runner(dict(ONLY_ZC)).run(bj)
    g3, s3 = rj.sysrows(3)
    g1, s1 = rj.sysrows(1)
    check("A J3 場所数 1 の系統: 2 か所に触れた足のイベント (場所数 2) は入らず、1 か所だけの足のイベントだけが入る。観察期間の集計も同じ系統へ入る",
          g1[ZCD][2] == [1, 0, 0] and g1[ZCW][2] == [1, 1, 0] and g3[ZCD][2] == [0, 0, 0] and g3[ZCW][2] == [0, 1, 0] and sum(g3[ZCD][0]) == 0
          and s3[3][2] == [0, 1, 0] and s1[3][2] == [2, 1, 0] and g3[ZCW][0][5 * NS] == 1 and g1[ZCW][0][5 * NS] == 1 and g1[ZCW][0][2 * NS] == 1 and g3[ZCW][0][2 * NS] == 0
          and compare(rj, oracle(bj, params(rj)))[0], f"{g1[ZCD][2]} {g1[ZCW][2]} {g3[ZCD][2]} {g3[ZCW][2]} {compare(rj, oracle(bj, params(rj)))[1]}")
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
          list(r.rows()) == [ZCW] and r["st"].rowOver == 1 and r.sums()[4][2] == [1, 0, 0] and r.sums()[3][2] == [2, 0, 0] and "int   ZC_MAXROW = 300 " in read(PINE))
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
         and r.records()[0][32] == 7 + 64)
    case("A 14 同じ根拠 ID の Zone が 2 本でも根拠数は 1 (生の本数は 2)",
         [(4310, 4310, 4301.5, 4304)], merge(zc(2, 1, 4300.0), zc(2, -1, 4301.0)),
         lambda r, ev, o: (ev[0]["mask"], ev[0]["nEv"], ev[0]["nRaw"]) == (ZCD, 1, 2))
    # 15 causality
    b15 = bars_from_rows([(4301, 4301.5, 4300, 4301), (4301, 4301.5, 4300, 4301), (4301, 4301.5, 4300, 4301)], None, start=4310.0, feeds={1: D})
    r, o, ok, det = run_case(b15, None)
    check("K 登録した 5 分足ではタッチにしない (次の 5 分足から。価格の位置に現れた Zone は方向不明)",
          ok and r["st"].nEv == 0 and r["st"].nUnk == 1 and r["st"].nCont == 1 and r["zcNZone"][7] == 1, f"{r.state()} | {det}")
    # 17 FIFO
    # ZCR-8: the 30-minute bar also decides every first-touch (open $16 above P0), so the two events are finalized on that bar
    r, ev, o = case("A 17 同じ 5 分足で 2 件確定 → 1 足 1 件ずつ出力 (FIFO)", [(4310, 4310, 4279, 4290)] + flat(4290, 5) + flat(4306, 4), f10,
                    lambda r, ev, o: len(r.out) == 2 and r.out[1][0] == r.out[0][0] + 1 and [x[1][0] for x in r.out] == [1, 2] and r["st"].nOut == 2)
    r2 = Runner(ONLY_ZC).run(bars_from_rows([(4310, 4310, 4279, 4290)] + flat(4290, 5) + flat(4306, 1), f10))
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
        check("T " + name, ok and c, f"events={[(e['bar'], e['d'], e['mask'], e['rTop'], e['rBot'], e['aux']) for e in ev]} zones={r.zones()} {r.state()['zeStat']} | {det}")
        return r, ev, orc
    one("ZA: 形成終了で箱の上辺・下辺を登録 (4H 箱 4290..4300 → 上辺の帯 4298..4302 にタッチ)", {"zaUse2": True}, za(1, 4300.0, 4290.0, 111, 0),
        lambda r, ev, o: len(ev) == 1 and (ev[0]["mask"], ev[0]["side"], ev[0]["rTop"]) == (G["ZA-4H"], 1 << 1, 430200) and r["zcNZone"][1] == 2)
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
    check("T ZB-5m: 帯 = 直前の足が確定した時点の 5 分 EMA ± 共通幅", ok and [(e["mask"], e["nRaw"]) for e in o["events"]] == [(G["ZB-5m"], 1)], f"{o['events']} | {det}")
    one("ZC: Pivot の時刻キーが変わるたびに線ごとの帯 (W 高値 4300)", {"zcUse4": True}, zc(3, 1, 4300.0),
        lambda r, ev, o: len(ev) == 1 and ev[0]["mask"] == G["ZC-W"] and ev[0]["side"] == 1 << 9)
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
        lambda r, ev, o: len(ev) == 1 and (ev[0]["mask"], ev[0]["aux"]) == (G["ZE-4H"], 4) and r["zcNZone"][13] == 4
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
        lambda r, ev, o: len(ev) == 1 and (ev[0]["mask"], ev[0]["rTop"], ev[0]["rBot"], ev[0]["aux"]) == (G["ZF-FVG-4H"], 430300, 430100, 0))
    one("ZF: 上昇 FVG の下端を確定終値が下抜け → iFVG (根拠 ID が ZF-iFVG-4H になる)。iFVG の上端を確定終値が上抜け → 無効", {"zfUse2": True}, zf(1, k1, 4350.0, 1, 4303.0, 4296.0),
        lambda r, ev, o: [(e["bar"], e["mask"], e["aux"]) for e in ev] == [(3, G["ZF-iFVG-4H"], 0)] and r["st"].nIfvg == 1 and r["st"].nFvgDead == 1 and r.zones() == [],
        start=4290.0, rows=[(4290, 4290, 4290, 4290), (4290, 4290, 4290, 4290), (4290, 4297, 4290, 4291), (4291, 4291, 4291, 4291), (4291, 4291, 4291, 4291)],
        feeds={1: zf(1, k1 + 1, 4295.0), 4: zf(1, k1 + 2, 4304.0)})
    # J1: the same zone object keeps its contact state through FVG -> iFVG; the change of state alone is not a new event
    one("ZF: 接触中の FVG が iFVG に転換しても同じ Zone (接触中を引き継ぐ)。転換した次の足で触れても 0 件。1 つの Zone は FVG か iFVG のどちらか 1 つの根拠だけ"
        " (ZCR-7: 帯の中で始まる 2 本目は FVG 自身の方向が不明で根拠から外す。3 本目は iFVG なので方向条件なしで継続中)",
        {"zfUse2": True}, zf(1, k1, 4350.0, 1, 4303.0, 4296.0),
        lambda r, ev, o: [(e["bar"], e["mask"], e["nEv"], e["nRaw"]) for e in ev] == [(1, G["ZF-FVG-4H"], 1, 1)] and o["cont"] == 1 and r["st"].nFxK1 == 1 and r["st"].nIfvg == 1
        and r.zones() == [(16, 1, 429600, 430300, True)] and sorted(r.rows()) == [G["ZF-FVG-4H"]],
        rows=[(4310, 4310, 4301, 4302), (4302, 4302, 4294, 4295), (4295, 4297, 4294, 4296)], feeds={2: zf(1, k1 + 1, 4295.0)})
    one("ZF: 離脱した後に iFVG へ再接触すると ZF-iFVG の集合で 1 件 (FVG の集合とは別の行。同じ場所で両方に数えない)",
        {"zfUse2": True}, zf(1, k1, 4350.0, 1, 4303.0, 4296.0),
        lambda r, ev, o: [(e["bar"], e["mask"], e["nEv"]) for e in ev] == [(1, G["ZF-FVG-4H"], 1), (4, G["ZF-iFVG-4H"], 1)] and sorted(r.rows()) == sorted([G["ZF-FVG-4H"], G["ZF-iFVG-4H"]]),
        rows=[(4310, 4310, 4301, 4302), (4302, 4302, 4289, 4290), (4290, 4290, 4289, 4290), (4290, 4297, 4290, 4296.5)], feeds={2: zf(1, k1 + 1, 4290.0)})
    # ZG: a detection (base 7, top, double, zone base price 4300) in the block of target bar 100
    blk = zg_blk(T0 - 7200_000, T0 - 3600_000, 100, [(7, -1, 2, 4300.0)])
    one("ZG: 検知イベントで発動 (トップ・基準価格 4300 ± ZG 幅)。同じ基準の再検知では作らない", {"zgUse1": True}, zg(0, blk),
        lambda r, ev, o: len(ev) == 1 and (ev[0]["mask"], ev[0]["aux"], ev[0]["d"]) == (G["ZG-1H"], 0, -1) and ev[0]["side"] == 1 << 14 and r["zcNZone"][19] == 1,
        start=4296.0, rows=[(4296, 4299, 4296, 4297)], feeds={1: zg(0, blk, zg_blk(T0 - 3600_000, T0, 101, [(7, -1, 3, 4310.0)]))})
    one("ZG: トリプルは補助マスクに残る。期限 (検知足から 24 本目の 1 時間足の確定) で消える", {"zgUse1": True}, zg(0, zg_blk(T0 - 7200_000, T0 - 3600_000, 100, [(8, 1, 3, 4300.0)])),
        lambda r, ev, o: len(ev) == 1 and ev[0]["aux"] == 1 << 8 and ev[0]["side"] == 1 << 17 and r.zones() == [],
        start=4296.0, rows=[(4296, 4299, 4296, 4297)] + flat(4297, 2), feeds={2: zg(0, zg_blk(T0 - 3600_000, T0, 123)), 3: zg(0, zg_blk(T0, T0 + 3 * M5, 124))})
    one("ZG: 逆行 (トップ: 実体上端 > 基準価格 + $5) の足で消える。その足のタッチ判定は消える前の Zone で行う (次の足から無い)", {"zgUse1": True}, zg(0, blk),
        lambda r, ev, o: [e["bar"] for e in ev] == [1] and r.zones() == [] and o["cont"] == 0,
        start=4296.0, rows=[(4296, 4306, 4296, 4305.5), (4305.5, 4305.5, 4301, 4301)])
    # all 7 kinds on one place
    allf = merge(za(1, 4300.0, 4280.0, 111, 0), zc(2, 1, 4300.5), zd(1, 4299.5), ze(0, 4250.0, 4350.0, 1, 5), zf(1, k1, 4350.0, 1, 4301.0, 4299.0),
                 zg(1, zg_blk(T0 - 7200_000, T0 - 3600_000, 100, [(7, 1, 2, 4300.0)])))
    b = bars_from_rows([(4306, 4306, 4301, 4305)], allf, start=4340.0)
    b[1]["p1"], b[1]["p5"] = 4300.2, 4299.8
    r, o, ok, det = run_case(b, None, {"zaUse2": True, "zbUse1": True, "zbUse2": True, "zcUse3": True, "zdUse2": True, "zeUse": True, "zeUseD": False, "zfUse2": True, "zgUse4": True}, base=OFF)
    want = sum(G[n] for n in ("ZA-4H", "ZB-1m", "ZB-5m", "ZC-D", "ZD-4H", "ZE-4H", "ZF-FVG-4H", "ZG-4H"))
    check("T 全 7 種類が同じ場所に重なる: 1 イベント・根拠数 8 (ZA ZB×2 ZC ZD ZE ZF ZG)", ok and len(o["events"]) == 1 and o["events"][0]["mask"] == want
          and o["events"][0]["nEv"] == 8, f"{o['events']} | {det}")


# ----------------------------------------------------------------------------------------------------------------
OLD_REV = "79be329"          # ZCR-3: the last version with the ordering of places (ord, 3 passes) and the edge-member column


def before_after(seeds=(1, 2, 3, 4)):
    """H1: without the ordering the set of events and every value of each event is unchanged. The ZCR-3 source (from git) and the
    current one run on the same bars; records are compared without the ID (creation order), and without the removed columns
    (ZCR-3 #7 edge-side member, #13 ord). The order of creation inside a bar may differ, so the records are compared as sorted lists."""
    try:
        old = subprocess.run(["git", "show", OLD_REV + ":ZoneConfluenceReactionStatsXAU.pine"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    except Exception as ex:        # noqa: BLE001
        check("H 変更前 (ZCR-3 79be329) の本体を git から取得", False, repr(ex))
        return
    key = lambda v: tuple(-1e18 if x is None else round(x, 6) for x in v)       # noqa: E731
    for seed in seeds:
        ov = RANDOM_PRM[seed % len(RANDOM_PRM)]
        bars = random_bars(seed, 1500)
        ov = dict(ov, zfUse1=False, zfUse2=False, zfUse3=False, zfUse4=False)      # ZF evidence IDs differ since ZCR-5 (FVG / iFVG split)
        a = Runner(ov, source=old).run(bars)
        b = Runner(dict(ov, zcP0Mode=CLOSE)).run(bars)         # ZCR-8: the close as P0 = the old way
        oaux = lambda x: (x & 0xFF) + (((x >> 16) & 7) << 8)        # noqa: E731   ZCR-3 aux -> current (ZG triple bits 16-18 -> 8-10)
        ra = sorted(key([oaux(int(x)) if i == 15 else x for i, x in enumerate(v) if i not in (0, 7, 13)]) for v in a.records())
        rb = sorted(key(v[1:35]) for v in b.records())
        pa = sorted((p["t0"], p["mask"], p["d"], p["rTop"], p["rBot"], p["edge"], p["nPl"], oaux(p["aux"]), p["flags"], p["onMask"], p["side"], tuple(p["wst"])) for p in a.pending())
        pb = sorted((p["t0"], p["mask"], p["d"], p["rTop"], p["rBot"], p["edge"], p["nPl"], p["aux"], p["flags"], p["onMask"], p["side"], tuple(p["wst"])) for p in b.pending() if 0 in p["wst"])
        sa, sb = a.state(), b.state()
        sa["nZone"] = sa["nZone"] + [0] * 4
        same_st = all(sa[k] == sb[k] for k in sb if k not in ("nDone", "nOut", "nTa", "nTb"))
        multi = sum(1 for v in b.records() if v[12] > 1)
        check(f"H 変更前後 (ZCR-3 79be329 → 現在) で記録が一致 (ID・順番・接触端側メンバーの列を除く全列。seed {seed})",
              ra == rb and pa == pb and same_st and a.rows() == c21(b.rows()) and a.sums() == c21(b.sums()) and a.rows2() == c21(b.rows2()) and len(rb) > 60 and multi > 10,
              f"records {len(ra)} / {len(rb)} pending {len(pa)} / {len(pb)} state={same_st} multi-place records={multi} "
              f"first diff={next(((x, y) for x, y in zip(ra, rb) if x != y), None)}")


def c21(t):
    """the time-window arrays in the layout before ZCR-9 (21 items per direction x window; ZCR-9 added 21-23 = reached by the touch bar's
    close, always 0 with the close as P0)"""
    def cv(c):
        return [c[b * 24 + i] for b in range(6) for i in range(21)] if len(c) == 6 * 24 else list(c)
    if isinstance(t, dict):
        return {k: c21(v) for k, v in t.items()}
    if isinstance(t, list):
        return [c21(v) for v in t]
    if isinstance(t, tuple) and len(t) == 2 and isinstance(t[0], dict):
        return (c21(t[0]), c21(t[1]))
    return (cv(t[0]),) + tuple(t[1:])


LEGACY_ST = ("nDone", "nOut", "nFxK1", "nFxK2", "nFxEmpty", "nFtCut", "nTa", "nTb")


def legacy(r):
    """the content an older version (before ZCR-8, the close as P0) can be compared on: every record by ID with its first 35 columns
    (records() includes the events whose windows are done but whose first-touch is open: the old version had output them), the
    pending observations whose windows are open, the time-window aggregation (4 systems), the counters (without nDone / nOut — the
    output timing changed — and the newer counters), the creation info. The output order and the count of not-yet-output records are left out."""
    key = lambda v: tuple(None if x is None else round(x, 6) for x in v)       # noqa: E731
    lk = ("id", "t0", "p0", "d", "mask", "nEv", "nRaw", "rTop", "rBot", "edge", "cPos", "nPl", "aux", "flags", "onMask", "side", "rmin", "alo", "ahi", "wst", "wmfe", "wmae", "wnb")
    st = {k: v for k, v in r.state().items() if k not in LEGACY_ST}
    recs = r.records()
    return copy.deepcopy(dict(rec={int(v[0]): key(v[:35]) for v in recs}, nrec=len(recs), pend=[{k: p[k] for k in lk} for p in r.pending() if 0 in p["wst"]],
                              rows=c21(r.rows()), sums=c21(r.sums()), rows2=c21(r.rows2()), sums2=c21(r.sums2()), sys3=c21(r.sysrows(3)), sys4=c21(r.sysrows(4)), st=st, created=list(r.created),
                              done=r.state()["nDone"] + sum(1 for p in r.pending() if 0 not in p["wst"])))


def ft_cases():
    """E: ZCR-8 fixed cases — the start point (band edge / close) and the first-touch (open first, unknown order, tracking, unmeasurable,
    no time limit, widths alone). ZC-D 4300 = band 4298..4302, ZC-W 4301 = band 4299..4303."""
    D, Wl = zc(2, 1, 4300.0), zc(3, 1, 4301.0)
    ZCD, ZCW = G["ZC-D"], G["ZC-W"]

    def ec(name, rows, feeds0, cond, ov=None, start=4310.0, base=ONLY_ZC, edit=None, **kw):
        bars = bars_from_rows(rows, feeds0, start=start)
        if edit:
            edit(bars)
        o = dict(base, zcP0Mode=EDGE)
        o.update(ov or {})
        FT_SCEN.append((bars, o))
        r = Runner(o, **kw).run(bars)
        orc = oracle(bars, params(r))
        ok, det = compare(r, orc)
        ev = orc["events"]
        c = False
        try:
            c = cond(r, ev, orc)
        except Exception as ex:        # noqa: BLE001
            det += f" cond raised {ex!r}"
        check("E " + name, ok and c, f"events={[(e['bar'], e['d'], e['mask'], e['p0'], e['p0c'], e['p0e'], e['fst'], e['fmin'], e['fin']) for e in ev]} "
              f"out={len(r.out)} pend={len(r['zcPend'])} | {det}")
        return r, ev, orc
    ec("帯端 LONG = 採用根拠の帯 (UA) の上端 4302 (終値 4305 ではない)。記録に起点方式 1・P0 終値・P0 帯端", [(4310, 4310, 4301, 4305)] + flat(4320, 8), D,
       lambda r, ev, o: [(e["d"], e["p0"], e["p0c"], e["p0e"]) for e in ev] == [(1, 430200, 430500, 430200)] and r.records()[0][35:38] == [1, 4305.0, 4302.0]
       and near(r.records()[0][2], 4302.0) and near(r.records()[0][10], 3.0))
    ec("帯端 SHORT = UA の下端 4298", [(4290, 4299, 4289, 4297)] + flat(4280, 2), D,
       lambda r, ev, o: [(e["d"], e["p0"], e["p0c"]) for e in ev] == [(-1, 429800, 429700)], start=4290.0)
    ec("複数根拠: 共通帯 UA = [4299, 4302] の端 (LONG 4302 / 次の SHORT 4299)", [(4310, 4310, 4301, 4305), (4305, 4320, 4305, 4320)] + flat(4320, 8) + [(4290, 4290, 4290, 4290)] + flat(4290, 7) + [(4290, 4300, 4289, 4295)],
       merge(D, Wl), lambda r, ev, o: [(e["d"], e["mask"], e["p0"]) for e in ev] == [(1, ZCD + ZCW, 430200), (-1, ZCD + ZCW, 429900)])
    ec("切り詰めない: 始値が帯の中で直前終値が上 (高安 4299〜4301 は帯の内側) → P0 = 帯の上端 4302 (C の上端 4301 ではない)", [(4300, 4301, 4299, 4300.5)], D,
       lambda r, ev, o: [(e["d"], e["rTop"], e["p0"], e["flags"] & 8192) for e in ev] == [(1, 430100, 430200, 8192)])
    k1 = T0 - 3_600_000
    ec("K2 で外した FVG は帯端に使わない (場所 {上昇 FVG, 線 4302} が下から → 線の帯 4300〜4304 の下端 4300)", [(4298, 4302, 4297, 4301)],
       merge(zf(1, k1, 4350.0, 1, 4303.0, 4296.0), zc(2, 1, 4302.0)),
       lambda r, ev, o: [(e["d"], e["mask"], e["p0"], e["flags"] & 16384) for e in ev] == [(-1, ZCD, 430000, 16384)], ov={"zfUse2": True})

    def ma_move(bars):
        for i, b in enumerate(bars):
            b["p5"] = 4300.0 if i <= 1 else 4330.0
    ec("ZB の帯が後で動いても P0 は発生時の帯端のまま (ZB-5m 4300 → 4330)", [(4306, 4306, 4301, 4305)] + flat(4310, 3), {},
       lambda r, ev, o: [(e["mask"], e["p0"]) for e in ev] == [(G["ZB-5m"], 430200)] and r.pending()[0]["p0"] == 430200,
       base=OFF, ov={"zbUse2": True}, edit=ma_move)
    ec("帯端起点 (ZCR-9): タッチ足の安値 4296 は逆行側目標 4297 を越えた (接触後で確実) → $5 逆行先 (タッチ足で決着・0 分・判定 2)",
       [(4306, 4306, 4296, 4303)] + [(4303, 4307, 4303, 4306)], D, lambda r, ev, o: [e["fst"][0] for e in ev] == [2] and ev[0]["fmin"][0] == 0 and ev[0]["tbj"] == [2, 0, 0])
    ec("終値起点: タッチ足の高安は先着に含めない (安値 4296 は P0 4303 から $7 下だが数えない。次の足で $5 反発先)",
       [(4306, 4306, 4296, 4303)] + [(4303, 4308, 4303, 4306)], D, lambda r, ev, o: [e["fst"][0] for e in ev] == [1] and ev[0]["fmin"][0] == 5 and ev[0]["tbj"] is None,
       ov={"zcP0Mode": CLOSE})
    ec("始値優先: 始値が反発側目標以上なら、同じ足の安値が逆行側目標に届いても反発先", [(4310, 4310, 4301, 4305), (4308, 4308, 4296, 4300)], D,
       lambda r, ev, o: ev[0]["fst"][0] == 1)
    ec("始値優先: 始値が逆行側目標以下なら逆行先 (同じ足の高値が反発側目標に届いても)", [(4306, 4306, 4301, 4305), (4296, 4308, 4296, 4300)], D,
       lambda r, ev, o: ev[0]["fst"][0] == 2)
    ec("始値が両目標の間で高安が両方に届く → 順序不明", [(4310, 4310, 4301, 4305), (4302, 4308, 4296, 4300)], D,
       lambda r, ev, o: ev[0]["fst"][0] == 3 and ev[0]["fst"][1:] == [0, 0])
    ec("履歴末尾で未決着 → 追跡中。30 分の観察が終わっていても記録は出さない (先着待ちで未出力)", [(4310, 4310, 4301, 4305)] + flat(4303, 8), D,
       lambda r, ev, o: ev[0]["fst"] == [0, 0, 0] and ev[0]["wst"] == [1, 1, 1] and r.out == [] and len(r["zcQ"]) == 0 and len(r["zcPend"]) == 1)

    def bad_at(k):
        def f(bars):
            bars[k]["h"] = bars[k]["o"] - 1.0
        return f
    ec("不正足 → 未決着の幅は計測不能 (4)。決着済みの幅はそのまま", [(4310, 4310, 4301, 4305), (4305, 4307.5, 4304, 4306)] + flat(4306, 2), D,
       lambda r, ev, o: ev[0]["fst"] == [1, 4, 4] and ev[0]["fmin"] == [5, None, None] and len(r.out) == 1, edit=bad_at(3))
    ec("時間制限なし: 30 分を超えて決着 (55 分後に 3 幅とも反発先。記録は 30 分ではなく決着した足で確定し、その足で出る)",
       [(4310, 4310, 4301, 4305)] + flat(4304, 10) + [(4304, 4317, 4304, 4316)] + flat(4316, 2), D,
       lambda r, ev, o: ev[0]["fst"] == [1, 1, 1] and ev[0]["fmin"] == [55, 55, 55] and ev[0]["wfin"] == 7 and ev[0]["fin"] == 12 and [i for i, _ in r.out] == [12])
    ec("幅ごとに独立: $5 は逆行先、$10・$15 は反発先", [(4306, 4306, 4301, 4305), (4300, 4300, 4296.5, 4299), (4299, 4318, 4299, 4317)], D,
       lambda r, ev, o: ev[0]["fst"] == [2, 1, 1] and ev[0]["fmin"] == [5, 10, 10])
    ec("閾値は ceil のティック (目標ちょうど 4307.00 は到達、4306.99 は未到達)", [(4310, 4310, 4301, 4305), (4305, 4306.99, 4305, 4306), (4306, 4307, 4306, 4306)], D,
       lambda r, ev, o: ev[0]["fst"][0] == 1 and ev[0]["fmin"][0] == 10)
    ec("起点 = タッチ足終値: P0 = 4305、記録の起点方式 0", [(4310, 4310, 4301, 4305), (4305, 4321, 4305, 4320)] + flat(4320, 6), D,
       lambda r, ev, o: [(e["p0"], e["p0e"]) for e in ev] == [(430500, 430200)] and ev[0]["fst"][0] == 1 and r.records()[0][35] == 0, ov={"zcP0Mode": CLOSE})
    # the cap of the tracked observations (2): touches of one line re-made by the time departure, the price never $5 away
    rows = []
    for _ in range(4):
        rows += [(4304.5, 4304.5, 4301, 4304.5)] + flat(4304.5, 7)
    bars = bars_from_rows(rows, D, start=4310.0)
    r = Runner(dict(ONLY_ZC, zcP0Mode=EDGE), maxpend=2).run(bars)
    ev_n = r["st"].nEv
    recs = r.records()
    cut = [v for v in recs if v[38:41] == [5, 5, 5]]
    f = r.fsys(1)[1][3]
    check("E 追跡中の上限 (テストでは 2): 超えたら古い順に先着の未決着を「打ち切り」(5) にして確定・出力。計測不能とは別に数え、集計の合計は崩れない",
          ev_n == 4 and r["st"].nFtCut == 2 and len(r["zcPend"]) == 2 and len(cut) == 2 and f[5] == 2 and f[3] == 2 and f[4] == 0 and sum(f[:NFT]) == 4,
          f"events={ev_n} cut={r['st'].nFtCut} pend={len(r['zcPend'])} f={f[:NFT]}")


def ua_k2_equiv(seeds=(2, 4, 6)):
    """E: the UA of the members before K2 gives the same touched-side edge (an FVG removed by K2 never sets that edge: for a SHORT place
    the open is below the C low set by another member and inside the FVG, so the FVG bottom is lower; LONG the mirror). Checked by running
    the source with UA over all members (K2 included) — the records must not change."""
    s0 = read(PINE)
    ua = ("            uaLo := na(uaLo) ? z.tb : math.max(uaLo, z.tb)\n            uaHi := na(uaHi) ? z.tt : math.min(uaHi, z.tt)\n")
    assert s0.count(ua) == 1 and s0.count("        if xz\n            nX += 1\n") == 1
    s1 = s0.replace(ua, "").replace("        if xz\n            nX += 1\n", "        if isM\n" + ua.replace("            ", "            ", 2) + "        if xz\n            nX += 1\n")
    same, k2 = True, 0
    for seed in seeds:
        ov = dict(RANDOM_PRM[seed % len(RANDOM_PRM)], zcP0Mode=EDGE)
        bars = random_bars(seed, 1500)
        a, b = Runner(ov).run(bars), Runner(ov, source=s1).run(bars)
        same &= a.snapshot() == b.snapshot()
        k2 += a["st"].nFxK2
    check("E K2 前のメンバーで UA を作っても接触側の帯端は変わらない (K2 で外す FVG は接触側の端を決めない。乱数 3 系列で記録・集計が同一)", same and k2 > 0, f"K2 {k2}")


def touch_adv_cases():
    """E (ZCR-8b): the touch bar's adverse move from the measuring P0 (column 44) and its high / low (45 / 46); the measurement itself unchanged"""
    D = zc(2, 1, 4300.0)
    rows = [(4306, 4306, 4290, 4303)] + flat(4303, 5) + flat(4320, 2)
    out = {}
    for mode in (EDGE, CLOSE):
        bars = bars_from_rows(rows, D, start=4310.0)
        r = Runner(dict(ONLY_ZC, zcP0Mode=mode)).run(bars)
        ok, det = compare(r, oracle(bars, params(r)))
        out[mode] = (ok, det, r.records(), r.state()["nTa"])
    ok_e, det_e, re_, ta_e = out[EDGE]
    ok_c, det_c, rc_, ta_c = out[CLOSE]
    check("E タッチ足の起点からの逆行幅 (列 44): 帯 4298〜4302・LONG・帯端起点 4302・タッチ足 始値 4306 / 安値 4290 / 終値 4303 → $12.0。ZCR-9: 帯端起点では $5 / $10 は"
          "タッチ足で逆行先 (判定 2)、$15 は後で反発先 (ZCR-8b の指摘の解消)。"
          "終値起点 (4303) では $13.0。列 45 / 46 = タッチ足の高値・安値。状態・注記の件数 ($5 / $10 / $15 以上) は確定したイベントだけ",
          ok_e and ok_c and len(re_) == 1 and near(re_[0][44], 12.0) and re_[0][38:41] == [2, 2, 1] and re_[0][47:50] == [2, 2, 0] and rc_[0][38:41] == [1, 1, 1] and near(re_[0][45], 4306.0) and near(re_[0][46], 4290.0)
          and near(rc_[0][44], 13.0) and ta_e == [1, 1, 0] and ta_c == [1, 1, 0], f"{det_e} {det_c} {[x[44:47] for x in re_ + rc_]} {ta_e} {ta_c}")
    bars = bars_from_rows([(4294, 4310, 4294, 4297)] + flat(4297, 5) + flat(4280, 2), D, start=4290.0)
    r = Runner(dict(ONLY_ZC, zcP0Mode=EDGE)).run(bars)
    ok, det = compare(r, oracle(bars, params(r)))
    rec = r.records()
    check("E 列 44 SHORT: 帯端起点 4298・タッチ足の高値 4310 → $12.0 (high − P0)。逆行していなければ 0 (負にしない)",
          ok and len(rec) == 1 and rec[0][3] == -1 and near(rec[0][44], 12.0) and near(rec[0][45], 4310.0), f"{det} {[x[44:47] for x in rec]}")
    bars = bars_from_rows([(4310, 4310, 4302, 4305)] + flat(4320, 8), D, start=4310.0)
    r = Runner(dict(ONLY_ZC, zcP0Mode=EDGE)).run(bars)
    check("E 列 44: タッチ足の安値 = 起点 4302 なら 0", near(r.records()[0][44], 0.0) and r.state()["nTa"] == [0, 0, 0])


TA_REV = "3ae50fa"           # ZCR-8: the last version without the touch-bar columns


def strip_new(r, ncol):
    """a snapshot without what came after a version: record columns from ncol on, the new pending fields, the new counters,
    and the time-window arrays in the 21-item layout"""
    sn = r.snapshot()
    sn["rec"] = [v[:ncol] for v in sn["rec"]]
    sn["out"] = [(i, v[:ncol]) for i, v in sn["out"]]
    sn["pend"] = [{k: v for k, v in p.items() if k not in ("th", "tl", "tbj")} for p in sn["pend"]]
    for k in ("nTa", "nTb"):
        sn["st"].pop(k, None)
    for k in ("rows", "sums", "rows2", "sums2", "sys3", "sys4"):
        sn[k] = c21(sn[k])
    return sn


def ta_before_after(seeds=(1, 2)):
    """P (ZCR-8b / ZCR-9): with the close as P0, everything but the newer record columns == 3ae50fa (ZCR-8) and == a06230d (ZCR-8b):
    records, output bars and order, queue, tracked observations, aggregation (time windows and first-touch, 4 systems), counters.
    With the band edge (ZCR-9 changed only that mode): the event set and its identity columns == a06230d, and the first-touch results of
    the events on whose touch bar nothing is judged (touch codes 0 0 0) == a06230d."""
    olds = {}
    for rev in (TA_REV, Z9_REV):
        try:
            olds[rev] = subprocess.run(["git", "show", rev + ":ZoneConfluenceReactionStatsXAU.pine"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
        except Exception as ex:        # noqa: BLE001
            check(f"P 変更前 ({rev}) の本体を git から取得", False, repr(ex))
            return
    for seed in seeds:
        bars = random_bars(seed, 1500)
        ov = dict(RANDOM_PRM[seed % len(RANDOM_PRM)], zcP0Mode=CLOSE)
        b = Runner(ov).run(bars)
        for rev, ncol in ((TA_REV, 44), (Z9_REV, 47)):
            a = Runner(ov, source=olds[rev]).run(bars)
            sa, sb = strip_new(a, ncol), strip_new(b, ncol)
            diff = [k for k in sa if sa[k] != sb[k]]
            check(f"P seed {seed} (タッチ足終値): 列 {ncol} 以降 (新しい列) を除き、記録・出力の足と順番・出力待ち・追跡中・集計 (時間内・先着の 4 系統)・件数が {rev} と完全一致",
                  not diff and len(sb["out"]) > 300 and all(v[47:50] == [None] * 3 for v in b.records()), f"differs: {diff}; out {len(sb['out'])}")
        ov = dict(ov, zcP0Mode=EDGE)
        a, b = Runner(ov, source=olds[Z9_REV]).run(bars), Runner(ov).run(bars)
        ra, rb = {v[0]: v for v in a.records()}, {v[0]: v for v in b.records()}
        ident = lambda v: [v[i] for i in list(range(0, 14)) + list(range(33, 38)) + [44, 45, 46]]     # noqa: E731
        none_ = [i for i in rb if rb[i][47:50] == [0, 0, 0]]
        some = [i for i in rb if rb[i][47:50] != [0, 0, 0]]
        same_ft = all(ra[i][38:44] == rb[i][38:44] for i in none_)
        changed = sum(1 for i in some if ra[i][38:44] != rb[i][38:44])
        check(f"P seed {seed} (接触側の帯端): イベントの集合と識別の列 (時刻・P0・方向・根拠・C・接触端・終値の位置・マスク・P0 終値 / 帯端・タッチ足の列) は a06230d と同じ。"
              "タッチ足で何も判定されないイベント (判定 0 0 0) の先着結果・決着分は a06230d と一致",
              sorted(ra) == sorted(rb) and all(ident(ra[i]) == ident(rb[i]) for i in ra) and same_ft and len(none_) > 50 and changed > 0,
              f"events {len(rb)}; touch judged {len(some)} (first-touch changed {changed}); not judged {len(none_)}")


Z9_TABLE = []


def z9_cases():
    """Z: ZCR-9 band-edge start, the touch bar (the cases of the instruction). LONG: ZC-D 4298 = band 4296..4300 -> P0 = 4300.
    SHORT: ZC-D 4302 = band 4300..4304 -> P0 = 4300. (4) uses ZC-D 4300 = band 4298..4302 -> P0 = 4302."""
    L, S, M = zc(2, 1, 4298.0), zc(2, 1, 4302.0), zc(2, 1, 4300.0)

    def zcase(name, rows, feeds0, start, want, ov=None):
        bars = bars_from_rows(rows, feeds0, start=start)
        o = dict(ONLY_ZC, zcP0Mode=EDGE)
        o.update(ov or {})
        FT_SCEN.append((bars, o))
        r = Runner(o).run(bars)
        orc = oracle(bars, params(r))
        ok, det = compare(r, orc)
        recs = r.records()
        rec = recs[0] if recs else None
        got = None
        if rec is not None:
            got = dict(P0=rec[2], d=rec[3], ft=rec[38:41], ftmin=rec[41:44], reach=rec[14:17], tb=rec[47:50], f32768=int(rec[32]) & 32768 > 0,
                       adv=[None if x is None else round(x, 2) for x in rec[17:23]], mfe30=rec[27], mae30=rec[28], ta=rec[44])
        Z9_TABLE.append((name, got))
        good = got is not None and all(got[k] == v for k, v in want.items())
        check("Z " + name, ok and good, f"got={got} want={want} | {det}")
    # (1) the user's example
    zcase("(1) LONG 起点 4300、タッチ足 始値 4303 / 高値 4306 / 安値 4299 / 終値 4305、次の足で 4310、その次で 4315 → $5 反発先 0 分 (終値で確認)・$10 反発先 5 分・$15 反発先 10 分。時間内到達も同じ",
          [(4303, 4306, 4299, 4305), (4305, 4310, 4304, 4309), (4309, 4315, 4308, 4314)] + flat(4314, 6), L, 4310.0,
          dict(P0=4300.0, d=1, ft=[1, 1, 1], ftmin=[0, 5, 10], reach=[-2, 5, 10], tb=[1, 0, 0], f32768=False))
    zcase("(2) LONG 起点 4300、タッチ足 始値 4303 / 高値 4306 / 安値 4294 / 終値 4306 → $5 順序不明 (タッチ足で両側)。$10 は安値 4294 > 4290・終値 < 4310 → 次の足から (後で 4310 → 反発先)",
          [(4303, 4306, 4294, 4306), (4306, 4310, 4305, 4309)] + flat(4309, 3) + [(4309, 4316, 4309, 4315)] + flat(4315, 4), L, 4310.0,
          dict(ft=[3, 1, 1], ftmin=[0, 5, 25], reach=[-2, 5, 25], tb=[3, 0, 0]))
    zcase("(3a) LONG 起点 4300、タッチ足 始値 4307 / 高値 4307 / 安値 4299 / 終値 4302 → $5 は未確認の反発の可能性 (判定 4)。後で 4295 に先に届く → 順序不明 (フラグ 32768)",
          [(4307, 4307, 4299, 4302), (4302, 4302, 4295, 4296), (4296, 4296, 4285, 4286)] + flat(4286, 6), L, 4310.0,
          dict(ft=[3, 2, 2], ftmin=[5, 10, 10], reach=[0, 0, 0], tb=[4, 0, 0], f32768=True))
    zcase("(3b) 同じタッチ足で、後で 4305 に先に届く → 反発先 (印はそのまま反発先)",
          [(4307, 4307, 4299, 4302), (4302, 4305, 4301, 4304), (4304, 4316, 4304, 4315)] + flat(4315, 6), L, 4310.0,
          dict(ft=[1, 1, 1], ftmin=[5, 10, 10], reach=[5, 10, 10], tb=[4, 0, 0], f32768=False))
    zcase("(4) 始値が帯の中 (直前終値で LONG、起点 4302)、タッチ足 始値 4302 / 高値 4303 / 安値 4294 / 終値 4298 → $5 逆行先 (タッチ足で決着 0 分・判定 2)。高値 4303 < 4307",
          [(4302, 4303, 4294, 4298), (4298, 4298, 4285, 4286)] + flat(4286, 7), M, 4310.0,
          dict(P0=4302.0, d=1, ft=[2, 2, 2], ftmin=[0, 5, 5], tb=[2, 0, 0]))
    # (5) SHORT mirrors
    zcase("(5-1) SHORT 起点 4300、タッチ足 始値 4297 / 高値 4301 / 安値 4294 / 終値 4295 → $5 反発先 0 分・$10 5 分・$15 10 分",
          [(4297, 4301, 4294, 4295), (4295, 4296, 4290, 4291), (4291, 4292, 4285, 4286)] + flat(4286, 6), S, 4290.0,
          dict(P0=4300.0, d=-1, ft=[1, 1, 1], ftmin=[0, 5, 10], reach=[-2, 5, 10], tb=[1, 0, 0]))
    zcase("(5-2) SHORT 起点 4300、タッチ足 始値 4297 / 高値 4306 / 安値 4294 / 終値 4294 → $5 順序不明 (タッチ足で両側)",
          [(4297, 4306, 4294, 4294), (4294, 4295, 4290, 4291)] + flat(4291, 3) + [(4291, 4291, 4284, 4285)] + flat(4285, 4), S, 4290.0,
          dict(d=-1, ft=[3, 1, 1], ftmin=[0, 5, 25], tb=[3, 0, 0]))
    zcase("(5-3) SHORT 起点 4300、タッチ足 始値 4293 / 高値 4301 / 安値 4293 / 終値 4298 → $5 未確認の反発の可能性。後で 4305 に先に届く → 順序不明 (フラグ 32768)",
          [(4293, 4301, 4293, 4298), (4298, 4305, 4298, 4304), (4304, 4315, 4304, 4314)] + flat(4314, 6), S, 4290.0,
          dict(d=-1, ft=[3, 2, 2], tb=[4, 0, 0], f32768=True))
    zcase("(参考) 逆行到達と未確認の反発の可能性 (判定 5): LONG 起点 4300、タッチ足 始値 4307 / 高値 4307 / 安値 4294 / 終値 4301 → $5 順序不明 (タッチ足で決着)",
          [(4307, 4307, 4294, 4301)] + flat(4301, 8) + [(4301, 4320, 4301, 4319)] + flat(4319, 2), L, 4310.0,
          dict(ft=[3, 1, 1], ftmin=[0, 45, 45], tb=[5, 0, 0]))


Z9_REV = "a06230d"           # ZCR-8b: the last version without the touch-bar judgement of the band-edge start


FT_SCEN = []                 # the bars of the E cases (the mutation check X also runs them)
P_REV = "08c2410"            # ZCR-7 (+ doc): the last version with the close as the only P0 and no first-touch


def p0_before_after(seeds=(1, 2, 3, 4)):
    """P: with 計測起点 = タッチ足終値 every old record column (35), the time-window aggregation of the 4 systems and the counters ==
    08c2410 (ZF on, the random parameters as they are). With the band edge the P0 column differs and nothing else of the event set."""
    try:
        old = subprocess.run(["git", "show", P_REV + ":ZoneConfluenceReactionStatsXAU.pine"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    except Exception as ex:        # noqa: BLE001
        check("P 変更前 (ZCR-7 08c2410) の本体を git から取得", False, repr(ex))
        return
    for seed in seeds:
        ov = RANDOM_PRM[seed % len(RANDOM_PRM)]
        bars = random_bars(seed, 1500)
        a = Runner(ov, source=old).run(bars)
        b = Runner(dict(ov, zcP0Mode=CLOSE)).run(bars)
        la, lb = legacy(a), legacy(b)
        diff = [k for k in la if la[k] != lb[k]]
        wait = sum(1 for p in b.pending() if 0 not in p["wst"])
        check(f"P seed {seed}: 計測起点 = タッチ足終値 のとき、記録の既存 35 列 (ID ごと)・観察期間の追跡中・時間内集計 (4 系統)・件数が 08c2410 と一致 "
              "(出力の順番・未出力件数は比較外: 先着の決着を待つため)",
              not diff and la["nrec"] > 300, f"differs: {diff}; records {la['nrec']}; waiting for the first-touch {wait}")
        e = Runner(dict(ov, zcP0Mode=EDGE)).run(bars)
        ea, eb = {v[0]: v for v in e.records()}, {v[0]: v for v in b.records()}
        same_ev = sorted(ea) == sorted(eb) and all(ea[i][1] == eb[i][1] and ea[i][3:10] == eb[i][3:10] and ea[i][11:14] == eb[i][11:14] and near(ea[i][36], eb[i][36]) and near(ea[i][37], eb[i][37]) for i in ea)
        moved = sum(1 for i in ea if not near(ea[i][2], eb[i][2]))
        check(f"P seed {seed}: 計測起点 = 接触側の帯端 でもイベントの集合・時刻・方向・根拠・C・接触端・P0 終値 / 帯端の列は同じ。計測に使う P0 (列 2) だけが帯端になる",
              same_ev and moved > 0 and all(near(ea[i][2], ea[i][37]) and ea[i][35] == 1 for i in ea) and all(near(eb[i][2], eb[i][36]) and eb[i][35] == 0 for i in eb),
              f"events {len(ea)} / {len(eb)}; P0 moved {moved}")


# ----------------------------------------------------------------------------------------------------------------
# ZCR-7: direction condition of the normal FVG
FX_REV = "d093c03"           # ZCR-6b: the last version without the direction condition of the normal FVG
FX_SCEN = []                 # the bars of the F cases (the mutation check X also runs them)
FX_OFF = [("        if f_zcFvgOk(array.get(zcT, qx), o)\n", "        if true\n"),
          ("        bool   xz  = isM and dp != 0 and", "        bool   xz  = false and dp != 0 and")]


def fvg_cases():
    """F: fixed cases of the direction condition (bullish FVG 4296..4303 / bearish the same band; ZC lines as other evidence)"""
    k1 = T0 - 3_600_000
    bull, bear = zf(1, k1, 4350.0, 1, 4303.0, 4296.0), zf(1, k1, 4350.0, -1, 4303.0, 4296.0)
    F4, ZCD = G["ZF-FVG-4H"], G["ZC-D"]

    def fc(name, rows, feeds0, cond, start=4350.0, feeds=None):
        FX_SCEN.append((bars_from_rows(rows, feeds0, start=start, feeds=feeds), dict(ONLY_ZC, zfUse2=True)))
        r, orc, ok, det = run_case(rows, feeds0, {"zfUse2": True}, start=start, feeds=feeds)
        ev = orc["events"]
        c = False
        try:
            c = cond(r, ev, orc, r["st"])
        except Exception as ex:        # noqa: BLE001
            det += f" cond raised {ex!r}"
        check("F " + name, ok and c, f"events={[(e['bar'], e['d'], e['mask'], e['nRaw'], e['flags'], e['rBot'], e['rTop'], e['onMask']) for e in ev]} unk={orc['unk']} cont={orc['cont']} "
              f"K1={r['st'].nFxK1} K2={r['st'].nFxK2} empty={r['st'].nFxEmpty} on={sorted(q.gid for q in r['zcOn'])} | {det}")
    fc("上昇 FVG に上から (始値 > 上端) → 採用 (LONG)", [(4310, 4310, 4301, 4302)], bull,
       lambda r, ev, o, st: [(e["d"], e["mask"]) for e in ev] == [(1, F4)] and st.nFxK1 == 0 and len(r["zcOn"]) == 1)
    fc("上昇 FVG に下から (始値 < 下端) → 除外: 他の根拠が無ければイベントなし・方向不明にも継続中にも数えない・接触中にしない", [(4290, 4298, 4289, 4297)], bull,
       lambda r, ev, o, st: ev == [] and o["unk"] == 0 and o["cont"] == 0 and o["nPre"] == 0 and st.nFxK1 == 1 and len(r["zcOn"]) == 0, start=4290.0)
    fc("上昇 FVG に下から + 線 (ZC-D 4297) → その線だけのイベント (SHORT、根拠数 1、フラグ 16384 なし)", [(4290, 4298, 4289, 4297)], merge(bull, zc(2, 1, 4297.0)),
       lambda r, ev, o, st: [(e["d"], e["mask"], e["nRaw"], e["flags"] & 16384) for e in ev] == [(-1, ZCD, 1, 0)] and st.nFxK1 == 1
       and [q.gid for q in r["zcOn"]] == [7], start=4290.0)
    fc("下降 FVG に下から → 採用 (SHORT)", [(4290, 4298, 4289, 4297)], bear,
       lambda r, ev, o, st: [(e["d"], e["mask"]) for e in ev] == [(-1, F4)] and st.nFxK1 == 0, start=4290.0)
    fc("下降 FVG に上から → 除外 (イベントなし)", [(4310, 4310, 4301, 4302)], bear,
       lambda r, ev, o, st: ev == [] and o["unk"] == 0 and st.nFxK1 == 1 and len(r["zcOn"]) == 0)
    fc("始値が FVG の帯の中・直前終値が帯の上 → 上から: 上昇 FVG を採用 (LONG、フラグ 8192)", [(4302, 4304, 4300, 4303)], bull,
       lambda r, ev, o, st: [(e["d"], e["mask"], e["flags"]) for e in ev] == [(1, F4, 8192)] and st.nFxK1 == 0, start=4310.0)
    fc("始値が FVG の帯の中・直前終値が帯の下 → 下から: 上昇 FVG は除外", [(4302, 4304, 4300, 4303)], bull,
       lambda r, ev, o, st: ev == [] and o["unk"] == 0 and st.nFxK1 == 1, start=4290.0)
    fc("始値も直前終値も帯の中 (方向不明) → 上昇 FVG を除外 (方向不明の件数にも入れない)", [(4300, 4301, 4299, 4300)], bull,
       lambda r, ev, o, st: ev == [] and o["unk"] == 0 and o["cont"] == 0 and st.nFxK1 == 1 and len(r["zcOn"]) == 0, start=4300.0)
    fc("始値も直前終値も帯の中 → 下降 FVG も除外", [(4300, 4301, 4299, 4300)], bear,
       lambda r, ev, o, st: ev == [] and o["unk"] == 0 and st.nFxK1 == 1, start=4300.0)
    # K2: the FVG itself is approached from above (open inside its band, previous close above), the place (FVG ∩ ZC 4300..4304) from below
    fc("K2: 上昇 FVG (自身は上から) と線 4302 の場所が下から (始値 4298 < C) → FVG だけ外して線のイベント (SHORT・フラグ 16384・C は 4300..4302 のまま)。FVG は接触中にしない (K3)",
       [(4298, 4302, 4297, 4301)], merge(bull, zc(2, 1, 4302.0)),
       lambda r, ev, o, st: [(e["d"], e["mask"], e["nEv"], e["nRaw"], e["flags"] & 16384, e["rBot"], e["rTop"]) for e in ev] == [(-1, ZCD, 1, 1, 16384, 430000, 430200)]
       and st.nFxK1 == 0 and st.nFxK2 == 1 and st.nFxEmpty == 0 and [q.gid for q in r["zcOn"]] == [7], start=4310.0)
    fc("K3 (K2 の後): 次の足で FVG に上から触れると、線は接触中・FVG は接触中でないので新規イベント (FVG+線、接触中だった根拠 = 線)",
       [(4298, 4302, 4297, 4301), (4305, 4305, 4302, 4303)], merge(bull, zc(2, 1, 4302.0)),
       lambda r, ev, o, st: [(e["bar"], e["d"], e["mask"], e["onMask"]) for e in ev] == [(1, -1, ZCD, 0), (2, 1, F4 + ZCD, ZCD)] and o["cont"] == 0, start=4310.0)
    fc("K3: 上昇 FVG に下から触れた後 (印を付けない)、離脱せずに上から触れる → 新規イベント (継続中にしない)",
       [(4290, 4298, 4289, 4297), (4305, 4306, 4304, 4305), (4305, 4305, 4302, 4303)], bull,
       lambda r, ev, o, st: [(e["bar"], e["d"], e["mask"]) for e in ev] == [(3, 1, F4)] and o["cont"] == 0 and st.nFxK1 == 1, start=4290.0)
    fc("既に接触中 (正しい側のタッチ由来) の上昇 FVG は、方向が合わないタッチの足 (帯の中で始まる足・下からの足) でも接触中のまま (離脱判定は従来どおり)",
       [(4310, 4310, 4301, 4302), (4302, 4302, 4294, 4294.5), (4294.5, 4297, 4294, 4295)], bull,
       lambda r, ev, o, st: [(e["bar"], e["mask"]) for e in ev] == [(1, F4)] and st.nFxK1 == 2 and len(r["zcOn"]) == 1)
    # iFVG: no direction condition (bullish FVG -> iFVG on bar 1's higher-TF close, then touched from below and from above)
    fc("iFVG は方向によらず従来どおり (上昇 FVG 由来の iFVG に下から 1 件、離脱後に上から 1 件)",
       [(4290, 4290, 4290, 4290), (4290, 4297, 4290, 4291), (4291, 4291, 4280, 4281), (4281, 4281, 4281, 4281)] + flat(4281, 6) + [(4310, 4310, 4310, 4310), (4310, 4310, 4302, 4305)],
       bull, lambda r, ev, o, st: [(e["bar"], e["d"], e["mask"]) for e in ev] == [(2, -1, G["ZF-iFVG-4H"]), (12, 1, G["ZF-iFVG-4H"])] and st.nFxK1 == 0,
       start=4290.0, feeds={1: zf(1, k1 + 1, 4295.0)})
    # the empty place (K2 removes every member): impossible through f_zcTouch (shown in the spec §7), so the branch is called directly
    r = Runner(dict(ONLY_ZC, zfUse2=True)).run(bars_from_rows([(4310, 4310, 4301, 4302)], bull))
    e = r.env
    z = e["zcT"][0] if e["zcT"] else None
    ok = z is not None and z.typ == 4 and not z.inv and z.sub == 1
    if ok:
        e["zcT"], e["zcTx"] = [z], [0]
        n_ev, n_unk, n_cont = e["st"].nEv, e["st"].nUnk, e["st"].nCont
        kept = e["f_zcPlace"](z.tb, z.tt, -1, z.tb - 10, z.tb, True)
        ok = kept is False and e["st"].nFxEmpty == 1 and e["st"].nFxK2 == 1 and (e["st"].nEv, e["st"].nUnk, e["st"].nCont) == (n_ev, n_unk, n_cont) and e["zcTx"] == [2]
    check("F メンバーが全員外れた場所 (f_zcPlace を直接呼ぶ): イベント・方向不明・継続中にせず「除外で空の場所」だけ数え、戻り値 false (場所数に入れない)", ok)


def fvg_before_after(seeds=(1, 2, 3, 4)):
    """V: (1) ZF OFF: records / pending / aggregation / state == d093c03 exactly. (2) ZF ON with the direction condition switched off in the
    current source (K1 / K2 lines replaced): == d093c03 exactly, so the condition is the only change. (3) ZF ON as is: every event on a bar
    without a touched ZF zone is unchanged (all columns but the ID); the changed events are all on bars with a touched ZF zone (a normal
    FVG, or an iFVG whose contact state came from its FVG time, K3)."""
    try:
        old = subprocess.run(["git", "show", FX_REV + ":ZoneConfluenceReactionStatsXAU.pine"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    except Exception as ex:        # noqa: BLE001
        check("V 変更前 (ZCR-6b d093c03) の本体を git から取得", False, repr(ex))
        return
    cur = read(PINE)
    off = cur
    for a, b in FX_OFF:
        assert off.count(a) == 1, a
        off = off.replace(a, b)
    snap = legacy
    tot_changed = tot_ev = tot_k = 0
    for seed in seeds:
        ov = RANDOM_PRM[seed % len(RANDOM_PRM)]
        bars = random_bars(seed, 1500)
        ovo = dict(ov, zfUse1=False, zfUse2=False, zfUse3=False, zfUse4=False, zcP0Mode=CLOSE)
        a, b = Runner(ovo, source=old).run(bars), Runner(ovo).run(bars)
        check(f"V seed {seed}: ZF OFF では記録・追跡中・集計 (4 系統)・件数が変更前 (d093c03) と完全一致 (ID 含む。ZCR-8 以後は起点 = 終値で、出力の順番・未出力件数を除く)",
              snap(a) == snap(b) and len(b.records()) > 60 and b["st"].nFxK1 == 0)
        ovn = dict(ov, zfUse1=True, zfUse2=True, zfUse3=True, zfUse4=True, zcP0Mode=CLOSE)
        a = Runner(ovn, source=old).run(bars)
        c = Runner(ovn, source=off).run(bars)
        b = Runner(ovn).run(bars)
        orc = oracle(bars, params(b))
        tc_bar = {bb.get("tc", bb["t"] + M5): i for i, bb in enumerate(bars)}
        key = lambda v: tuple(-1e18 if x is None else round(x, 6) for x in v[1:35])     # noqa: E731
        fx = orc["fxBars"]

        def split(recs):
            ins, outs = [], []
            for v in recs:
                (ins if tc_bar[int(round(v[1] * 1000))] in fx else outs).append(key(v))
            return sorted(ins), sorted(outs)
        ai, ao = split(a.records())
        bi_, bo = split(b.records())
        pa = sorted((p["t0"], p["mask"], p["d"], p["rTop"], p["rBot"], p["flags"]) for p in a.pending() if tc_bar[p["t0"]] not in fx)
        pb = sorted((p["t0"], p["mask"], p["d"], p["rTop"], p["rBot"], p["flags"]) for p in b.pending() if tc_bar[p["t0"]] not in fx and 0 in p["wst"])
        changed = len(set(ai) ^ set(bi_))
        tot_changed += changed
        tot_ev += len(b.records())
        tot_k += b["st"].nFxK1 + b["st"].nFxK2
        check(f"V seed {seed}: ZF ON・方向条件だけを外した現在の本体 == 変更前 (d093c03) で完全一致。方向条件ありでは、ZF に触れていない足のイベントは全列 (ID 以外) 不変、"
              "変わったイベントはすべて ZF (通常 FVG、または FVG から転換した iFVG。接触中の状態を引き継ぐため) に触れた足にある",
              snap(a) == snap(c) and ao == bo and pa == pb and changed > 0 and b["st"].nFxK1 > 0 and len(ao) > 50,
              f"records old {len(a.records())} new {len(b.records())}; on FVG bars old {len(ai)} new {len(bi_)} (symmetric difference {changed}); "
              f"other bars {len(ao)} / {len(bo)}; K1 {b['st'].nFxK1} K2 {b['st'].nFxK2} empty {b['st'].nFxEmpty}")
    COVER["fx_changed"] = tot_changed


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
    disp = dict(ov, zcView="詳細: 件数内訳", zcKind="根拠数別", zcDirMode="LONGのみ", zcHzMode="5分", zcPerPage=1, zcPage=3, zcTxtSize="large", zcPos="bottom_left",
                zcShowBox=False, zcShowLbl=True, zcDrawMax=1)
    check("B 表示の設定を変えても集計・記録は同じ", Runner(disp).run(bars).snapshot() == full.snapshot())
    off = Runner(dict(ov, zcUse3=False, zbUse1=False, zgUse1=False, zfUse2=False, zeUse4=False)).run(bars)
    bits = G["ZC-D"] + G["ZB-1m"] + G["ZG-1H"] + G["ZF-FVG-4H"] + G["ZE-4H"]
    check("B 根拠 ID を OFF にするとその根拠は登録も集合にも現れない", [off["zcNZone"][g] for g in (7, 19, 16, 13)] == [0, 0, 0, 0]
          and all(not (m & bits) for m in off.rows()) and len(off.rows()) > 2)


DISP_REV = "47ebe23"         # ZCR-5: the last version with the old table (f_pick / f_v / f_med, top N + その他, merged note cells)
DBEGIN, DEND = "// ==== ZCR Display calc (begin) ", "// ==== ZCR Display calc (end) "
DMS = ["LONGのみ", "SHORTのみ", "LONG＋SHORT合算"]
SEL = [(one, on) for one in (False, True) for on in ("含める", "のみ", "除く")]


def pine_tostring(x, fmt=None):
    """str.tostring with the "0.0" / "0.00" formats (half away from zero); the same function serves the old and the new code"""
    if x is None:
        return "NaN"
    if fmt in ("0.0", "0.00"):
        nd = len(fmt) - 2
        v = math.floor(abs(x) * 10 ** nd + 0.5 + 1e-9) / 10 ** nd
        return ("-" if x < 0 and v != 0 else "") + f"{v:.{nd}f}"
    if isinstance(x, float) and x.is_integer():
        return str(int(x))
    return str(x)


def display_ns(r, src):
    """the new "ZCR Display calc" section translated and run in the environment of a finished run r"""
    ns = r.env
    ns.update(str__tostring=pine_tostring, order=type("order", (), {"descending": "desc", "ascending": "asc"}),
              array__sort_indices=lambda a, o: sorted(range(len(a)), key=lambda i: a[i], reverse=(o == "desc")))
    code = src[src.index("\n", src.index(DBEGIN)) + 1:src.index(DEND)]
    exec(compile(ap.Translator(known_types={"ZcRow"}).translate(ap.logical_lines(code)), "<ZCR display calc>", "exec"), ns)
    return ns


def old_display_ns(r, old):
    """the old (47ebe23) table calculation, translated from its own text: ZC_GN + f_setName, and f_arr .. f_avgUsd
    (f_arr / f_pick / f_v / f_hv / f_ev / f_med / f_addArr / f_rowMerge / f_pct / f_avgUsd). f_pick reads the globals zcPlMode / zcOnMode."""
    ns = dict(r.env)
    a = old[old.index("array<string> ZC_GN = "):old.index("f_gUse(int g) =>")]
    b = old[old.index("f_arr(ZcRow r, int kind, bool one, bool onOnly) =>"):old.index("f_tm(int t) =>")]
    exec(compile(ap.Translator(known_types={"ZcRow"}).translate(ap.logical_lines(a + "\n" + b)), "<ZCR old display>", "exec"), ns)
    return ns


def old_rows(o, topn):
    """the old row list of the set view (the block under barstate.islast in 47ebe23, re-stated): top N by events, the rest + the
    over-cap row merged into "その他"."""
    e = o
    n = len(e["zrRow"])
    keyv = [(e["f_ev"](rr, 0) + e["f_ev"](rr, 1)) * (e["ZC_MAXROW"] + 1) + (e["ZC_MAXROW"] - i) for i, rr in enumerate(e["zrRow"])]
    ordv = sorted(range(n), key=lambda i: -keyv[i])
    shown = [e["zrRow"][i] for i in ordv[:topn]]
    rest = e["f_zcRowNew"](0, 0)
    nrest = 0
    for i in ordv[topn:]:
        e["f_rowMerge"](rest, e["zrRow"][i])
        nrest += 1
    over = e["zrSum"][4]
    if over.ev[0] + over.ev[1] + over.ev[2] > 0:
        e["f_rowMerge"](rest, over)
        nrest += 1
    return shown, (rest if nrest > 0 else None), nrest


def display_before_after(seeds=(1, 2, 3)):
    """D: the numbers the new tables show == the numbers of the old table (47ebe23) for every row x direction x window x item x
    selection (場所数 全件 / 1 のみ × 含める / のみ / 除く); the old cell texts re-formatted == the new cell texts; row order, names,
    "その他" (= the rows of the later pages) and the pages."""
    try:
        old = subprocess.run(["git", "show", DISP_REV + ":ZoneConfluenceReactionStatsXAU.pine"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    except Exception as ex:        # noqa: BLE001
        check("D 変更前 (ZCR-5 47ebe23) の本体を git から取得", False, repr(ex))
        return
    src = read(PINE)
    for k, seed in enumerate(seeds):
        ov = RANDOM_PRM[seed % len(RANDOM_PRM)]
        bars = random_bars(seed, 1500)
        r = Runner(dict(ov, zcP0Mode=CLOSE), maxrow=(1_000_000 if k == 0 else 6)).run(bars)        # later seeds: a low row cap so the over-cap row has events
        # (ZCR-9: the close as P0 — the old table has no bucket for the reaches on the touch bar's close of the band-edge start)
        ns = display_ns(r, src)
        o = old_display_ns(r, old)
        rows = list(ns["zrRow"]) + list(ns["zrSum"])
        nval = nstr = nbad = 0
        first_bad = None
        for one, on in SEL:
            o["zcPlMode"] = "場所数 1 のみ" if one else "全件"
            o["zcOnMode"] = on
            for rr in rows:
                for dm in DMS:
                    a = (ns["f_dsEv"](rr, dm, one, on), ns["f_dsRaw"](rr.ev2, dm), ns["f_dsRaw"](rr.ev3, dm))
                    b = (sum(o["f_ev"](rr, di) for di in (0, 1) if dm != ("SHORTのみ", "LONGのみ")[di]),
                         sum(rr.ev2[di] for di in (0, 1) if dm != ("SHORTのみ", "LONGのみ")[di]), sum(rr.ev3[di] for di in (0, 1) if dm != ("SHORTのみ", "LONGのみ")[di]))
                    nval += 3
                    if a != b:
                        nbad += 1
                        first_bad = first_bad or ("ev", dm, a, b)
                    for h in range(3):
                        vn = [ns["f_dsV"](rr, dm, h, x, one, on) for x in range(NS)]
                        vo = [o["f_v"](rr, dm, h, x) for x in range(NS)]
                        nval += NS
                        if vn != vo:
                            nbad += 1
                            first_bad = first_bad or ("v", dm, h, vn, vo)
                        n = vo[0]
                        for j in range(3):
                            hn = [ns["f_dsHv"](rr, dm, h, j, m, one, on) for m in range(1, 31)]
                            ho = [o["f_hv"](rr, dm, h, j, m) for m in range(1, 31)]
                            mn, mo = ns["f_dsMed"](rr, dm, h, j, one, on), o["f_med"](rr, dm, h, j)
                            rc = vo[2 + j]
                            # the old cell texts (f_line of 47ebe23), re-formatted to the new layout
                            old_rate = str(rc) + " (" + o["f_pct"](rc, n) + ")"
                            exp_rate = "—" if n == 0 else old_rate
                            exp_time = "—" if rc == 0 else pine_tostring(vo[5 + j] / (rc * 1.0), "0.0") + "/" + pine_tostring(mo, "0.0") + " (" + str(rc) + ")"
                            old_adv = "—" if rc == 0 else o["f_avgUsd"](vo[10 + j], rc) + "～" + o["f_avgUsd"](vo[13 + j], rc) + " (順序不明 " + str(vo[16 + j]) + "/" + str(rc) + ")"
                            new_adv = ns["f_dsAdv"](rr, dm, h, j, one, on)
                            got = (hn, mn, ns["f_dsRate"](ns["f_dsV"](rr, dm, h, 2 + j, one, on), ns["f_dsV"](rr, dm, h, 0, one, on)),
                                   ns["f_dsTime"](rr, dm, h, j, one, on), new_adv.replace("\n不明 ", " (順序不明 ") + ("" if rc == 0 else ")"))
                            exp = (ho, mo, exp_rate, exp_time, old_adv)
                            nval += 32
                            nstr += 3
                            if got != exp:
                                nbad += 1
                                first_bad = first_bad or ("h", dm, h, j, got[1:], exp[1:])
                        for x, y in ((8, 8), (9, 9)):
                            nstr += 1
                            if ns["f_dsUsd"](ns["f_dsV"](rr, dm, h, x, one, on), n) != o["f_avgUsd"](vo[y], n):
                                nbad += 1
                                first_bad = first_bad or ("mfe", dm, h, x)
            # rows: order and "その他"
            new = ns["f_dsRows"](False, one, on)
            allr, rest, _ = old_rows(o, 10 ** 9)
            over_on = rest is not None
            ok_order = [x.mask for x in new] == [x.mask for x in allr] + ([0] if over_on else []) and (not over_on or new[-1] is ns["zrSum"][4])
            top, rest6, nrest6 = old_rows(o, 6)
            ok_rest = [x.mask for x in new[:6]] == [x.mask for x in top] and nrest6 == max(0, len(new) - 6)
            if rest6 is not None:
                for dm in DMS:
                    for h in range(3):
                        ok_rest &= [o["f_v"](rest6, dm, h, x) for x in range(NS)] == [sum(ns["f_dsV"](q, dm, h, x, one, on) for q in new[6:]) for x in range(NS)]
            ok_cnt = ns["f_dsRows"](True, one, on) == ns["zrSum"][:4]
            if not (ok_order and ok_rest and ok_cnt):
                nbad += 1
                first_bad = first_bad or ("rows", one, on, ok_order, ok_rest, ok_cnt)
        names_ok = all(ns["f_dsName"](m, sp).replace("\n", "") == o["f_setName"](m) for m in ns["zrMask"] for sp in range(1, 7))
        lines_ok = all(len(ln.split("+")) - (1 if ln.startswith("+") else 0) <= (1 if bin(m).count("1") <= sp else 2)
                       for m in ns["zrMask"] for sp in (1, 3, 6) for ln in ns["f_dsName"](m, sp).split("\n"))
        nsets = len(ns["zrRow"])
        over_rows = sum(1 for x in ns["f_dsRows"](False, False, "含める") if x.mask == 0)
        check(f"D seed {seed}: 表の数値 (対象件数・到達件数・計測不能・待ち・本数不足・到達分・MFE/MAE・逆行・順序不明・発生・初回到達分の度数と中央値) と表示文字列は変更前 (47ebe23 の f_pick / f_v / f_hv / f_med / f_ev / f_pct / f_avgUsd) と一致。"
              "全行 × 方向 3 × 期間 3 × 項目 × 絞り込み 6 通り。行の並びも一致し、旧「その他」= 7 行目以降の合計",
              nbad == 0 and nval > 50_000 and nsets >= 6 and (k == 0 or over_rows == 1),
              f"values={nval} strings={nstr} sets={nsets} over-row={over_rows} mismatches={nbad} first={first_bad}")
        check(f"D seed {seed}: 組合せ名は旧集合名と同じ (改行を除く)。1 行は 根拠数 <= 縦の行数なら 1 根拠、超えれば 2 根拠まで", names_ok and lines_ok and len(ns["zrMask"]) >= 6)
        cells = []
        for one, on in SEL:
            for rr in rows:
                for dm in DMS:
                    for h in range(3):
                        n = ns["f_dsV"](rr, dm, h, 0, one, on)
                        for j in range(3):
                            cells += [ns["f_dsRate"](ns["f_dsV"](rr, dm, h, 2 + j, one, on), n), ns["f_dsTime"](rr, dm, h, j, one, on), ns["f_dsAdv"](rr, dm, h, j, one, on)]
                        cells += [ns["f_dsUsd"](ns["f_dsV"](rr, dm, h, 8, one, on), n), ns["f_dsUsd"](ns["f_dsV"](rr, dm, h, 9, one, on), n)]
        longest = max((ln for c in cells for ln in c.split("\n")), key=dwidth)
        check(f"D seed {seed}: 数値セルの 1 行は半角 24 桁 (全角 12 文字) 以内 (最長 {longest!r})", dwidth(longest) <= 24)
    pg = display_ns(Runner(RANDOM_PRM[0]).run(random_bars(1, 50)), src)
    ok = all(pg["f_dsPages"](n, per) == max(1, -(-n // per)) for n in range(0, 80) for per in range(1, 11))
    ok &= [pg["f_dsPage"](w, 4) for w in (-1, 0, 1, 3, 4, 5, 99)] == [1, 1, 1, 3, 4, 4, 4]
    ok &= all(sorted(i for p in range(1, pg["f_dsPages"](n, per) + 1) for i in range((p - 1) * per, min(n, (p - 1) * per + per))) == list(range(n))
              for n in range(0, 40) for per in range(1, 11))
    check("D ページ: 総ページ = ceil(件数 / 1 ページの数) (最低 1)、指定ページは 1..総ページに丸める、全ページで各行がちょうど 1 回", ok)


def dwidth(t):
    """display width in half-width columns (full-width / wide characters = 2)"""
    import unicodedata
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F", "A") else 1 for ch in t)


class MockTable:
    """table.* as far as the drawing code uses it; out-of-range cells / merges and overlapping merges raise (TradingView: runtime error)"""
    def __init__(self, pos, cols, rows, **kw):
        if cols < 1 or rows < 1:
            raise ap.PineRuntimeError("table.new with no cells")
        self.pos, self.cols, self.rows, self.cells, self.merges, self.deleted = pos, cols, rows, {}, [], False

    def _in(self, c, r):
        if not (0 <= c < self.cols and 0 <= r < self.rows):
            raise ap.PineRuntimeError(f"cell ({c}, {r}) outside the table {self.cols} x {self.rows}")

    def cell(self, c, r, text="", **kw):
        self._in(c, r)
        self.cells[(c, r)] = dict(kw, text=text)

    def merge(self, c0, r0, c1, r1):
        self._in(c0, r0)
        self._in(c1, r1)
        for m in self.merges:
            if not (c1 < m[0] or c0 > m[2] or r1 < m[1] or r0 > m[3]):
                raise ap.PineRuntimeError(f"merge {(c0, r0, c1, r1)} overlaps {m}")
        self.merges.append((c0, r0, c1, r1))

    def covered(self, c, r):
        return any(m[0] <= c <= m[2] and m[1] <= r <= m[3] and (c, r) != (m[0], m[1]) for m in self.merges)


def render(r, src, **sel):
    """run the drawing code of the table (everything between "// ---- 表" and the record output, the Display calc included) on the
    last bar of the finished run r, with the display inputs sel; returns the table made"""
    from types import SimpleNamespace as NS_
    ns = r.env
    tbls = []

    def tnew(pos, c, rws, **kw):
        t = MockTable(pos, c, rws, **kw)
        tbls.append(t)
        return t
    pos = {k: k for k in ("top_left", "top_center", "top_right", "middle_left", "middle_center", "middle_right", "bottom_left", "bottom_center", "bottom_right")}
    ns["position"] = NS_(**pos)
    ns.update({f"size__{k}": k for k in ("tiny", "small", "normal", "large")})

    def tostr(x, fmt=None):
        return pine_tostring(x, "0.00" if fmt == "mintick" else fmt)
    ns.update(str__tostring=tostr, str__replace_all=lambda a, b, c: a.replace(b, c), color__black="black", barstate__islast=True,
              array__new_string=lambda n=0, v=None: [v] * n,
              order=NS_(descending="desc", ascending="asc"), array__sort_indices=lambda a, o: sorted(range(len(a)), key=lambda i: a[i], reverse=(o == "desc")),
              table=NS_(new=tnew, cell=lambda t, c, rr, s="", **kw: t.cell(c, rr, s, **kw), merge_cells=lambda t, *a: t.merge(*a),
                        delete=lambda t: setattr(t, "deleted", True)), text=NS_(align_left="left"), format=NS_(mintick="mintick"),
              syminfo__tickerid="OANDA:XAUUSD", timeframe__period="5", chart=NS_(is_standard=True), zcTbl=None)
    inp = dict(zcView="主表: 先着", zcKind="根拠集合 (完全一致)", zcDirMode="LONG / SHORT 別", zcHzMode="全期間", zcOnMode="含める", zcPlMode="全件",
               zcPerPage=5, zcPage=1, zcTxtSize="small", zcPos="top_right")
    inp.update(sel)
    ns.update(inp)
    code = src[src.index("// ---- 表 (集計値には影響しない"):src.index("// ---- イベント記録の出力")]
    assert code.count("var table zcTbl = na") == 1
    code = code.replace("var table zcTbl = na", "zcTbl = na")
    exec(compile(ap.Translator(known_types={"ZcRow", "ZcObs"}).translate(ap.logical_lines(code)), "<ZCR table>", "exec"), ns)
    assert len(tbls) == 1
    return tbls[0]


def table_text(t):
    """the table as text (merged cells: the text in the top-left cell, the covered cells blank)"""
    out = []
    for rr in range(t.rows):
        out.append(" | ".join("" if t.covered(c, rr) else t.cells.get((c, rr), {}).get("text", "").replace("\n", " / ") for c in range(t.cols)))
    return "\n".join(out)


def table_render_checks(seed=1):
    """R: the drawing code itself run on a finished run (mock table API) for every view × direction × window × row kind × selection
    and several pages: no cell / merge outside the table, merges only vertical and not overlapping, every row of the table used, the
    main table has 7 columns and 3 rows (5 / 15 / 30 分) per combination × direction, the text of every cell short (the combination name:
    at most 2 evidences per line), size / position from the inputs, and the main table's numbers == the Display calc functions."""
    src = read(PINE)
    bars = random_bars(seed, 1500)
    r = Runner(RANDOM_PRM[seed % len(RANDOM_PRM)]).run(bars)
    views = ["主表: 先着", "主表: 時間内到達", "詳細: 件数内訳", "詳細: 初回到達時間", "詳細: MFE・MAE", "詳細: 到達前逆行", "詳細: 状態・注記"]
    ncols = {"主表: 先着": 9, "主表: 時間内到達": 7, "詳細: 件数内訳": 11, "詳細: 状態・注記": 2}
    bad, n_tab, longest = [], 0, ("", "")
    for v in views:
        for dmode in ("LONG / SHORT 別", "LONG＋SHORT合算", "LONGのみ", "SHORTのみ"):
            for hz in ("全期間", "5分", "30分"):
                for kind in ("根拠集合 (完全一致)", "根拠数別"):
                    for one, on in (SEL if v.startswith("主表") and dmode == "LONG / SHORT 別" and hz == "全期間" else SEL[:1]):
                        for per, page in ((5, 1), (5, 2), (3, 999), (10, 1)):
                            sel = dict(zcView=v, zcDirMode=dmode, zcHzMode=hz, zcKind=kind, zcPlMode="場所数 1 のみ" if one else "全件", zcOnMode=on,
                                       zcPerPage=per, zcPage=page, zcTxtSize=("tiny", "small", "normal", "large")[n_tab % 4], zcPos="bottom_left" if n_tab % 2 else "top_right")
                            try:
                                t = render(r, src, **sel)
                            except Exception as ex:        # noqa: BLE001
                                bad.append((sel, repr(ex)))
                                continue
                            n_tab += 1
                            nDir = 2 if dmode == "LONG / SHORT 別" else 1
                            nHz = 3 if hz == "全期間" or v == "主表: 先着" else 1
                            err = []
                            if any(m[0] != m[2] for m in t.merges):
                                err.append("horizontal merge")
                            if any(not any((c, rr) in t.cells for c in range(t.cols)) and not any(t.covered(c, rr) for c in range(t.cols)) for rr in range(t.rows)):
                                err.append("unused row")
                            if t.cols != ncols.get(v, 6) or t.pos != sel["zcPos"] or any(x.get("text_size") != sel["zcTxtSize"] for x in t.cells.values()):
                                err.append(("cols / pos / size", t.cols, t.pos))
                            if v != "詳細: 状態・注記":
                                ns = r.env
                                rows = ns["f_dsRows"](kind == "根拠数別", one, on)
                                pages = max(1, -(-len(rows) // per))
                                pg = min(max(page, 1), pages)
                                shown = rows[(pg - 1) * per:pg * per]
                                if t.rows != 2 + len(shown) * nDir * nHz or t.cells[(1, 0)]["text"] != f"{pg}/{pages}頁":
                                    err.append(("rows / page", t.rows, len(shown), t.cells[(1, 0)]["text"]))
                                if not v.startswith("主表") and any(m for m in t.merges if m[2] == 0 and m[3] - m[1] + 1 != nDir * nHz):
                                    err.append("combination merge")
                                if v == "主表: 先着":
                                    rr = 2
                                    for q in shown:
                                        if (0, rr, 0, rr + nDir * 3 - 1) not in t.merges:
                                            err.append(("name merge", rr))
                                        for dm in (["LONGのみ", "SHORTのみ"] if nDir == 2 else [dmode]):
                                            for j in range(3):
                                                f = [ns["f_dsF"](q, dm, j, k, one, on) for k in range(NFT)]
                                                exp = [str(f[0]), str(f[1]), ns["f_dsFRate"](f[0], f[1]), str(f[2]), str(f[3]), str(f[4]) + (f" (+{f[5]})" if f[5] else "")]
                                                got = [t.cells[(c, rr)]["text"] for c in range(3, 9)]
                                                if got != exp or t.cells[(2, rr)]["text"] != ("$5", "$10", "$15")[j] or sum(f) != ns["f_dsEv"](q, dm, one, on):
                                                    err.append(("first-touch values", rr, got, exp))
                                                rr += 1
                                if v == "主表: 時間内到達":
                                    rr = 2
                                    for q in shown:
                                        if nDir * nHz > 1 and (0, rr, 0, rr + nDir * nHz - 1) not in t.merges:
                                            err.append(("name merge", rr))
                                        for dm in (["LONGのみ", "SHORTのみ"] if nDir == 2 else [dmode]):
                                            for h in ([0, 1, 2] if nHz == 3 else [{"5分": 0, "30分": 2}[hz]]):
                                                n = ns["f_dsV"](q, dm, h, 0, one, on)
                                                exp = [str(n)] + [ns["f_dsRate"](ns["f_dsV"](q, dm, h, 2 + j, one, on), n) for j in range(3)]
                                                got = [t.cells[(c, rr)]["text"] for c in range(3, 7)]
                                                if got != exp or t.cells[(2, rr)]["text"] != ("5分", "15分", "30分")[h]:
                                                    err.append(("values", rr, got, exp))
                                                rr += 1
                            for (c, rr), x in t.cells.items():
                                for ln in x["text"].split("\n"):
                                    is_name = c == 0 and rr >= 2 and v != "詳細: 状態・注記"
                                    lim_ok = dwidth(ln) <= 24 and (not is_name or ln.lstrip("+").count("+") <= 1)
                                    if not lim_ok:
                                        err.append(("long", c, rr, ln))
                                    if not is_name and dwidth(ln) > dwidth(longest[1]):
                                        longest = (v, ln)
                            if err:
                                bad.append((sel, err[:3]))
    try:
        r0 = Runner(RANDOM_PRM[0]).run(bars[:3])
        r0.env["zrSum"] = []              # the state before the first confirmed 5m bar
        t0 = render(r0, src)
        t1 = render(Runner(RANDOM_PRM[0], run=False).run(bars[:3]), src)
        ok0 = (t0.cols, t0.rows, t0.cells[(0, 0)]["text"]) == (1, 1, "ZCR-XAU: 確定足なし") and (t1.cols, t1.rows, t1.cells[(0, 0)]["text"]) == (1, 3, "ZCR-XAU: 集計停止")
    except Exception as ex:        # noqa: BLE001
        ok0 = False
        bad.append(("empty / stopped", repr(ex)))
    check("R 確定足なし・集計停止 (5分の標準チャート以外) の表も範囲内で描ける", ok0)
    check(f"R 表の描画コードそのものを模擬 table で実行 ({n_tab} 表: 表示切替 7 × 方向 4 × 観察期間 3 × 表の行 2 × ページ 4、主表 2 種は絞り込み 6 通り): 範囲外のセル・結合なし、結合は縦だけで重ならない、"
          "全行使用、主表: 先着 9 列・1 組合せ × 1 方向 = 幅 3 行 (反発先 + 逆行先 + 順序不明 + 追跡中 + 計測不能 + 打ち切り = 発生)、主表: 時間内到達 7 列・3 行・組合せ名は縦結合、行数とページ表示、主表の数値 = Display calc、文字サイズ・位置は入力どおり、"
          "セルの 1 行は半角 24 桁 (全角 12 文字) 以内 (組合せ名は 1 行 2 根拠まで)",
          not bad and n_tab > 600, f"bad={len(bad)} first={bad[:2]} longest(組合せ名以外)={longest}")
    return r


MUTATIONS = [
    ("到達を「以上」から「超」へ", "                    if fav >= w\n", "                    if fav > w\n"),
    ("離脱幅を「以上」から「超」へ", "if dist >= zcDepT or", "if dist > zcDepT or"),
    ("離脱時間を使わない", " or time_close - z.outT >= zcDepMs", ""),
    ("継続中の抑制を外す", "    else if allOn\n        st.nCont += 1\n", "    else if false\n        st.nCont += 1\n"),
    ("継続中を「1 つでも接触中」に戻す", "    else if allOn\n        st.nCont += 1\n", "    else if onMask > 0\n        st.nCont += 1\n"),
    ("接近方向を始値でなく終値で決める", "array.get(zcUH, k), o)\n", "array.get(zcUH, k), c)\n"),
    ("直前終値で決まった場合も接触端を C の端にする", "        int  edge = byPc ? o : dp == 1 ? pHi : pLo\n", "        int  edge = dp == 1 ? pHi : pLo\n"),
    ("ZB-1m の助走を使わない", "            if st.ma1N > zbWarm1\n", "            if true\n"),
    ("2 系統目に全イベントを入れる", "    if ob.onMask > 0\n        f_zcAgg(r.c2, r.hist2, ob, h, ok)\n", "    if true\n        f_zcAgg(r.c2, r.hist2, ob, h, ok)\n"),
    ("接する帯 (端点一致) を別の場所にする", "                if not fn2 or mh < p2\n", "                if not fn2 or mh <= p2\n"),
    ("極大でない集合も場所にする", "                if not fn2 or mh < p2\n", "                if true\n"),
    ("同じ足の後の場所を前の場所の接触で抑制する (印をその場で付ける)", "            allOn := allOn and z.isOn\n            nRaw += 1\n", "            allOn := allOn and z.isOn\n            nRaw += 1\n            f_zcSetOn(z)\n"),
    ("期間の終わりを time_close < T0 + N 分にする (ちょうどの足を外す)", "            if tc > ob.t0 + array.get(zcWin, hh) * ZC_M1\n", "            if tc >= ob.t0 + array.get(zcWin, hh) * ZC_M1\n"),
    ("期間内の足が 0 本でも計測可能 (未到達) にする", "                f_zcWinDone(ob, hh, ob.nb > 0)", "                f_zcWinDone(ob, hh, true)"),
    ("基準時刻をタッチ足の開始にする", "        ZcObs ob = ZcObs.new(st.oSeq, time_close, c, dp,", "        ZcObs ob = ZcObs.new(st.oSeq, time, c, dp,"),
    ("始値で到達済みでも足の逆行を上限に入れる", "int hi = oFav >= w ? ob.mae : math.max(lo, adv)", "int hi = math.max(oFav >= w ? ob.mae : lo, adv)"),
    ("置き換わった POC / フィボが接触中を引き継がない", "            if z.tt >= array.get(zcInhB, sl) and z.tb <= array.get(zcInhT, sl)\n", "            if false\n"),
    ("離れた価格へ移った後継も接触中を引き継ぐ", "            if z.tt >= array.get(zcInhB, sl) and z.tb <= array.get(zcInhT, sl)\n", "            if true\n"),
    ("iFVG を FVG と同じ根拠 ID にする (分けない)", "    z.typ == 4 and z.inv ? 22 + z.tf : z.gid\n", "    z.gid\n"),
    ("場所数 1 の系統へ、場所数によらず発生を入れる", "            if nPl == 1\n", "            if true\n"),
    ("場所数 1 の系統へ、場所数によらず観察期間の集計を入れる", "    if ob.nPl == 1\n        f_zcAgg(r.c3, r.hist3, ob, h, ok)\n", "    if true\n        f_zcAgg(r.c3, r.hist3, ob, h, ok)\n"),
    ("場所数 1 かつ接触中の系統へ、接触中でないイベントも入れる", "        if ob.onMask > 0\n            f_zcAgg(r.c4, r.hist4, ob, h, ok)\n", "        if true\n            f_zcAgg(r.c4, r.hist4, ob, h, ok)\n"),
    ("根拠数を Zone 本数にする", "        ZcRow row = f_zcRow(mask, nG)\n        st.oSeq += 1", "        ZcRow row = f_zcRow(mask, nRaw)\n        st.oSeq += 1"),
    ("助走中もイベントにする", "    else if not live\n        st.nPre += 1\n", "    else if false\n        st.nPre += 1\n"),
    # ZCR-7: the direction condition of the normal FVG
    ("K1: 上昇 / 下降を逆にする", "f_zcFvgDir(z, o) == z.sub\n", "f_zcFvgDir(z, o) == -z.sub\n"),
    ("K2: 上昇 / 下降を逆にする", "and z.typ == 4 and not z.inv and z.sub != dp\n", "and z.typ == 4 and not z.inv and z.sub == dp\n"),
    ("K1 を省く", "        if f_zcFvgOk(array.get(zcT, qx), o)\n", "        if true\n"),
    ("K2 を省く", "        bool   xz  = isM and dp != 0 and", "        bool   xz  = false and dp != 0 and"),
    ("K3: K1 で外した FVG に接触中の印を付ける", "            array.remove(zcT, qx)\n", "            f_zcSetOn(array.get(zcT, qx))\n            array.remove(zcT, qx)\n"),
    ("K3: K2 で外した FVG に接触中の印を付ける", "            if array.get(zcTx, q) != 2\n", "            if true\n"),
    ("iFVG にも方向条件を掛ける", "    not (z.typ == 4 and not z.inv) or f_zcFvgDir", "    not (z.typ == 4) or f_zcFvgDir"),
    ("方向不明の FVG を外さない", "f_zcFvgDir(z, o) == z.sub\n", "f_zcFvgDir(z, o) != -z.sub\n"),
    ("K2 のフラグ 16384 を付けない", " + (nX > 0 ? 16384 : 0)", ""),
    # ZCR-8: start point and first-touch
    ("先着: 始値優先を外す", "int res = fOn >= w ? 1 : -fOn >= w ? 2 : fFv >= w", "int res = fFv >= w"),
    ("先着: 到達を「以上」から「超」へ (閾値の丸め)", "fFv >= w and fAd >= w ? 3 : fFv >= w ? 1 : fAd >= w ? 2 : 0", "fFv > w and fAd > w ? 3 : fFv > w ? 1 : fAd > w ? 2 : 0"),
    ("帯端に足の高安で切り詰めた C を使う", "p0e = dp == 1 ? uaHi : uaLo", "p0e = dp == 1 ? pHi : pLo"),
    ("先着に時間制限 (30 分) を残す", "            if array.get(ob.fSt, j) == 0\n                int w   =", "            if array.get(ob.fSt, j) == 0 and tc <= ob.t0 + 30 * ZC_M1\n                int w   ="),
    ("帯端の起点を使わない (常に終値)", "        if zcEdgeP0\n            ob.p0 := ob.p0e\n", "        if false\n            ob.p0 := ob.p0e\n"),
    ("先着の決着を待たずに記録を出す", "    bool done = left == 0 and not f_zcFtOpen(ob)\n", "    bool done = left == 0\n"),
    ("不正足で未決着を計測不能にしない", "                f_zcFtSet(ob, j, 4, tc)\n", "                f_zcFtSet(ob, j, 3, tc)\n"),
    # ZCR-9: the touch bar of the band-edge start
    ("タッチ足: 未確認の反発の可能性を反発先にする", "ah and fm ? 3 : ah ? 2 : 0\n", "ah and fm ? 3 : ah ? 2 : fm ? 1 : 0\n"),
    ("タッチ足: 高値で到達を認める", "        bool fc = cN >= w\n", "        bool fc = fx >= w\n"),
    ("タッチ足: 両側を反発先にする", "        int res = fc and ah ? 3 : fc ? 1", "        int res = fc and ah ? 1 : fc ? 1"),
    ("タッチ足: 後の逆行先を順序不明にしない", "                    if array.get(ob.tbJ, j) == 4\n", "                    if false\n"),
    ("タッチ足の判定を終値起点にも適用する", "            if zcEdgeP0\n                f_zcTouchBar(ob, h, l, c)", "            if true\n                f_zcTouchBar(ob, h, l, c)"),
    ("タッチ足: 逆行到達を見ない", "        bool ah = ad >= w\n", "        bool ah = false\n"),
    ("タッチ足: MAE にタッチ足の逆行を入れない", "    ob.mae := math.max(0, ad)\n", "    ob.mae := 0\n"),
]


def mutations(bars, ov):
    s = read(PINE)
    for name, old, new in MUTATIONS:
        if s.count(old) != 1:
            check(f"X {name}", False, f"mutation target found {s.count(old)} times")
            continue
        caught = False
        try:
            for bb, oo in [(bars, ov)] + FX_SCEN + FT_SCEN:          # random bars, then the fixed FVG cases (F) and first-touch cases (E)
                r = Runner(oo, source=s.replace(old, new)).run(bb)
                if not compare(r, oracle(bb, params(r)))[0]:
                    caught = True
                    break
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
    check("S 写し: ZE / ZF の入力と ZG 検知の入力 33 個は Lab と同一 (例外: ZF の 4 つの ON / OFF の初期値だけ ON。Lab は OFF)",
          between(lab, 'var string G_ZE = ', '\nvar string G_ZG = ', False) in re.sub(r'(zfUse\d = input\.bool\()true,', r'\1false,', s) and len(re.findall(r'zfUse\d = input\.bool\(true,', s)) == 4 and between(lab, 'var string G_ZG1 = ', '\nvar string G_TA = ', False).rstrip("\n") in s)
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
          and "float zbMa2 = ta.ema(close, zbLen2)\nfloat zbP1  = zbMa1[1]\nfloat zbP5  = zbMa2[1]" in code and "        float v1 = na\n        if not na(zbP1)\n            st.ma1N += 1\n            if st.ma1N > zbWarm1\n                v1 := zbP1\n        f_zcMaSet(0, zbUse1, v1)" in code and "f_zcMaSet(1, zbUse2, zbP5)" in code)
    lg = "\n".join(ap.strip_comment(x) for x in logic(s).split("\n"))
    check("S Logic 区間に request / ta. / 履歴参照なし。基準切替 (帯の接触端を P0 にする) の入力なし。「EMA が na (本数不足)」の記述なし",
          not re.search(r"\brequest\.|\bta\.", lg) and not re.search(r"\w\[", lg) and "zcBase" not in s and "本数不足) の間は" not in s and "ZcObs.new(st.oSeq, time_close, c, dp," in lg)
    plots = re.findall(r'^plot\((.+?),\s+"([^"]+)"', code, re.M)
    ev = [p for p in plots if p[1].startswith("EV ")]
    check("S plot 55 本 (上限 64)。EV 記録 50 本が zcOut の 0..49 の順 (順番・接触端側メンバーの列なし)。マスク: 根拠 26 ビット (< 2^26)・補助 11 ビット・辺 20 ビット",
          "f_zcAux" in code and "z.typ == 6 ? (z.sub == 1 ? 14 : 17) + z.tf : -1" in code and "array.get(zcPow, 8 + z.tf)" in code and code.count("33554432)") == 1 and "int   ZC_NG     = 26" in code and "z.typ == 4 and z.inv ? 22 + z.tf : z.gid" in code
          and len(plots) == 55 and len(re.findall(r"\bplot\(", code)) == 55 and "ob.ord" not in code and "nEv2" not in code and "場所の順番" not in code
          and [p[0] for p in ev] == [f"array.get(zcOut, {i})" for i in range(NF)] and f"int   ZC_NF     = {NF}" in code, f"{len(plots)} {len(ev)}")
    li, mi = ap.inputs(lab), ap.inputs(s)
    shared = [k for k in mi if k in li and re.match(r"(zHalf|zaUse|zaKeep|accum|zbUse|zbLen|zcUse|zcPiv|zdUse|zeUse|zfUse|zfMinW|zgUse|zgExp|zgHalf|zgRev|zg(Piv|Wave|Buf|Dist|Gap|Body|Ratio|Wait|Max|Dir|Sep))", k)]
    check("S Zone の入力の初期値は ZoneComboLabXAU と同じ (共通幅 2・ZA 4H/D・ZB 両方・ZC D/W・ZD 4H/D/W・ZE 4H/D・ZG 1H/4H/D ほか 84 個。例外は ZF だけ: ここは全 ON、Lab は全 OFF)",
          len(shared) == 84 and all(mi[k] == li[k] for k in shared if not k.startswith("zfUse")) and all(mi[f"zfUse{k}"] is True and li[f"zfUse{k}"] is False for k in (1, 2, 3, 4))
          and mi["zcPlMode"] == "全件" and mi["zcMax"] == 0 and mi["zcDepW"] == 5.0 and mi["zcDepMin"] == 30
          and mi["vpBins"] == 75 and mi["zcWarm"] == 6000 and mi["zbWarm1"] == 1800 and mi["zcOnMode"] == "含める"
          and 'zcStart = input.time(timestamp("01 Jan 2020 00:00 +0000"), "集計開始日時 (タッチ足の確定時刻)"' in code
          and 'input.time(timestamp("01 Jan 2020 00:00 +0000"), "集計開始日時 (判定足の確定時刻)"' in read(os.path.join(ROOT, "PointMasterVerifierV2.pine")) and all(mi[f"zdLen{k}"] == 120 for k in (1, 2, 3, 4)), f"{len(shared)} {[k for k in shared if mi[k] != li[k]]}")
    lfw = read(os.path.join(ROOT, "LongFibWave.pine"))
    lfw_titles = re.findall(r'^plot\(.+?, "(FIB [^"]+)", display = display\.none\)', lfw, re.M)        # the connection outputs, in order
    src_titles = re.findall(r'^ze\w+ = input\.source\(close, "([^"]+)"', code, re.M)
    doc = read(os.path.join(ROOT, "ZONE_CONFLUENCE_REACTION_XAU_ja.md"))
    doc_rows = re.findall(r'^\| \d+ \| `([^`]+)` \| `([^`]+)` \|', doc, re.M)
    check("S ZE は LongFibWave の接続出力 13 系列を input.source で受信。入力名 = LongFibWave の plot タイトル (LongFibWave.pine から取り出して照合、並びも同じ)。仕様書の対応表も同じ 13 行",
          len(lfw_titles) == 13 and src_titles == lfw_titles and doc_rows == [(t, t) for t in lfw_titles]
          and 'plot(lfwIs5m ? 20001 : na, "FIB protocol", display = display.none)' in lfw, f"{lfw_titles} {src_titles} {doc_rows}")
    check("S 方向・観察期間の選択肢は PointMasterVerifierV2 と同じ",
          'options = ["LONG / SHORT 別", "LONG＋SHORT合算", "LONGのみ", "SHORTのみ"]' in code and 'options = ["全期間", "5分", "15分", "30分"]' in code
          and all(x in read(os.path.join(ROOT, "PointMasterVerifierV2.pine")) for x in ('options = ["LONG / SHORT 別", "LONG＋SHORT合算", "LONGのみ", "SHORTのみ"]', 'options = ["全期間", "5分", "15分", "30分"]')))
    check("S 表・ラベル・冒頭に「タッチ足確定後の反応」の明記", s.count("タッチ足確定後の反応") >= 5 and "タッチ足確定後の反応" in read(os.path.join(ROOT, "ZONE_CONFLUENCE_REACTION_XAU_ja.md")))
    ind = [ln for ln in s.split("\n") if ln.strip() and not ln.lstrip().startswith("//")]
    bad = [ln for ln in ind if (len(ln) - len(ln.lstrip(" "))) % 4 not in (0, 1)]
    check("S 継続行以外のインデントは 4 の倍数、タブなし", not bad and "\t" not in s, str(bad[:3]))
    check("S 冒頭と仕様書に未検証 (PINE_NOT_VERIFIED) の明記", "PINE_NOT_VERIFIED" in s.split("indicator(")[0]
          and "PINE_NOT_VERIFIED" in read(os.path.join(ROOT, "ZONE_CONFLUENCE_REACTION_XAU_ja.md")))
    try:
        o = subprocess.run(["git", "show", DISP_REV + ":ZoneConfluenceReactionStatsXAU.pine"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    except Exception as ex:        # noqa: BLE001
        o = ""
        check("S 変更前 (47ebe23) の本体を git から取得", False, repr(ex))
    if o:
        def parts(t):
            g = t.index("var string G_DS = ")
            za = t.index("\n// ---- ZA: Accum 検出")
            dr = t.index("// ---- 描画 (集計値には影響しない)")
            tb = t.index("// ---- 表 (集計値には影響しない")
            ev = t.index("// ---- イベント記録の出力")
            head = "\n".join(ln for ln in t[:g].split("\n") if not ln.startswith("//"))
            hl, skip = [], False
            for ln in head.split("\n"):                   # ZCR-8: the new input (and the header comments) are left out
                skip = ln.startswith("zcP0Mode = ") or (skip and ln.startswith("     "))
                if not skip:
                    hl.append(ln)
            head = "\n".join(hl)
            out = "\n".join(ln for ln in t[ev:].split("\n") if not re.search(r"zcOut, (2|3[5-9]|4[0-9])\)", ln))   # ZCR-8: the new columns and the P0 title
            return dict(head=head, body=t[za:t.index(BEGIN)], draw=t[dr:tb], out=out)
        po, pn = parts(o), parts(s)
        same_parts = {k: po[k] == pn[k] for k in po}
        check("S 表示以外は変更前 (47ebe23) と byte 一致: 冒頭〜表示の入力の前 (ZCR-8: 冒頭のコメントと入力「計測起点」を除く) / Zone 検知・登録 (ZCR Logic 区間の前まで) / 描画 (枠・印) / "
              "イベント記録の出力 (plot 40 本。ZCR-8: 追加 9 本と列 2 の名前を除く) 〜末尾。"
              "ZCR Logic 区間は ZCR-7 (通常 FVG の方向条件) だけ変更 (オラクル照合と変更前後比較 V で確認)",
              all(same_parts.values()) and len(pn["out"]) > 2000 and pn["out"].count("plot(") == 39, str(same_parts))
        gd_o = o[o.index("var string G_DS = "):o.index("\n// ---- ZA: Accum 検出")].split("\n")
        gd_n = s[s.index("var string G_DS = "):s.index("\n// ---- ZA: Accum 検出")].split("\n")
        kept = [ln for ln in gd_o if not ln.startswith(("zcView ", "zcTopN "))]
        check("S 表示の入力: 表示切替を 主表 / 詳細 5 種にし、zcTopN を外して 1 ページの組合せ数 (5)・ページ (1)・文字サイズ (small)・表示位置 (top_right) を追加。他の表示の入力は同じ行のまま",
              all(ln in gd_n for ln in kept) and "zcTopN" not in s and mi["zcView"] == "主表: 先着" and mi["zcPerPage"] == 5 and mi["zcPage"] == 1 and mi["zcTxtSize"] == "small" and mi["zcPos"] == "top_right")
    disp = s[s.index("// ---- 表 (集計値には影響しない"):s.index("// ---- イベント記録の出力")]
    dcode = "\n".join(ap.strip_comment(x) for x in disp.split("\n"))
    merges = re.findall(r"table\.merge_cells\(([^)]*)\)", dcode)
    vert = all((lambda a: a[1] == a[3])([x.strip() for x in m.split(",")]) for m in merges)
    check("S 表: 結合は縦だけ (table.merge_cells の開始列 = 終了列)。表の位置・文字サイズは入力から (全表で同じ ZC_POS / ZC_TS)",
          merges and vert and dcode.count("table.new(ZC_POS,") == 4 and "table.new(position." not in dcode and "text_size = ZC_TS" in dcode and "text_size = size." not in dcode, str(merges))
    items = re.findall(r'f_item\(ks, vs, ts, ws, "([^"]+)", ', dcode)
    check("S 詳細: 状態・注記 は 1 項目 1 行 (項目名 12 文字以内)。旧欄外注記の項目 (登録数・イベント内訳・方向不明・抑制・MA / ZE / ZD 不明・接続状態・FVG→iFVG・助走・不正足・計測不能・EV 出力・上限超過・銘柄・期間・共通幅・離脱) を含む",
          len(items) >= 40 and all(len(x) <= 12 for x in items) and all(any(k in x for x in items) for k in ("登録 ZA", "登録 ZF", "方向不明", "継続中", "MA 不明", "ZE 受信不正", "ZD 正常でない", "ZE 接続 4H", "ZD POC", "FVG → iFVG", "iFVG 無効", "助走", "不正足", "計測不能", "EV 出力済み", "EV 未出力", "行数上限超過", "銘柄", "期間", "共通幅", "離脱", "注意")),
          str([x for x in items if len(x) > 12]))
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
    before_after()
    display_before_after()
    table_render_checks()
    fvg_cases()
    fvg_before_after()
    ft_cases()
    touch_adv_cases()
    z9_cases()
    ta_before_after()
    ua_k2_equiv()
    p0_before_after()
    causality(bars, ov)
    mutations(random_bars(10), dict(RANDOM_PRM[10 % len(RANDOM_PRM)], zbWarm1=300))
    bad = 0
    for name, ok, det in RESULTS:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok and not det.startswith("events=") else "  " + det))
        bad += 0 if ok else 1
    print(f"{len(RESULTS) - bad}/{len(RESULTS)} passed")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
