"""ZCS-1 checks — ZoneConfluenceStrategyXAU.pine.   PYTHONDONTWRITEBYTECODE=1 python3 tests/zcs_sim.py [random-seeds]

Runs the "ZCS Logic" section of the strategy itself (and the generated selection code + the "ZCS Select" section), translated
mechanically to Python by tests/acc_pine.py (unchanged), on synthetic confirmed 5m bars, against a small broker model below
(TVBroker: TradingView's default fill assumptions as assumed here). Everything request.* / input.source would deliver is given per
5m bar (the feeds of tests/zcr_sim.py: ZA f{k}*, ZC s{k}*, ZD zd*{k}, ZF g{k}*, ZG zgPk*, ZE ze*), plus the EMA at the bar's close
(m1 / m5 -> zbMa1 / zbMa2) and the higher-TF band (fb -> fbBand). A feed is delivered only when the strategy's own need flag for it
is true (as the `if need` around each request).

  S. static: copies == ZCR-9 / Lab byte for byte, the generated section == tests/zcs_build.py, requests (count, the flag around
     each, the same expressions as ZCR, lookahead, tuple total), strategy() settings, plots, input defaults == ZCR, git status
  Z. the zones of the strategy == the zones of ZCR-9 (tests/zcr_sim.py's Runner on the same feeds with the same kinds ON), every bar
  C. random paths vs an independent oracle written from the spec (brute force over all zone pairs, its own contact / departure /
     order state, its own broker instance): working orders after every bar, contact flags, trades
  F. fixed cases of the instruction (order side / price, no order inside / on the wrong side / without an overlap, no narrowing,
     no fill in the past, cancels, MA move, SL / TP from the fill price incl. gaps, one position / OCA / no reversal, re-entry only
     after a departure, touches while holding, the higher-TF filter, start / warm-up, comment)
  N. need: only the kinds / timeframes of the selected pairs are registered; all feeds given vs only the needed ones -> same result
  K. causality: a run on the first half == the first half of the full run
  X. mutations of the logic that the checks must catch

Evidence class: PINE_NOT_VERIFIED (no TradingView compiler / broker here; request.* semantics are not reproduced).
"""
import copy
import math
import os
import random
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import acc_pine as ap      # noqa: E402
import zcr_sim as zr       # noqa: E402
import zcs_build as zb     # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PINE = os.path.join(ROOT, "ZoneConfluenceStrategyXAU.pine")
ZCR = os.path.join(ROOT, "ZoneConfluenceReactionStatsXAU.pine")
LAB = os.path.join(ROOT, "ZoneComboLabXAU.pine")
DOC = os.path.join(ROOT, "ZONE_CONFLUENCE_STRATEGY_XAU_ja.md")
LB, LE = "// ==== ZCS Logic (begin) ", "// ==== ZCS Logic (end) "
SB, SE = "// ==== ZCS Select (begin) ", "// ==== ZCS Select (end) "
M1, M5 = 60_000, 300_000
T0 = zr.T0
MT = 0.01
GN = zb.GN
GI = {n: i for i, n in enumerate(GN)}
PAIRS = zb.pairs()
PIX = {(a, b): p for p, a, b in PAIRS}
RESULTS = []
COVER = {}


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


def read(p):
    return open(p, encoding="utf-8").read()


def tk(x):
    return math.floor(x / MT + 0.5)


def ticks(usd):
    return max(1, math.ceil(usd / MT - 1e-9))


def between(t, a, b):
    i = t.index(a)
    return t[t.index("\n", i) + 1:t.index(b, i)]


def prog(src):
    """the Python of: the generated selection code (f_zsSel and zsN..) + the Select section + the Logic section"""
    g0 = src.index("f_zsSel() =>")
    gen = src[g0:src.index(zb.END)]
    return ap.Translator().translate(ap.logical_lines(gen + "\n" + between(src, SB, SE) + "\n" + between(src, LB, LE)))


def sel_code(src):
    g0 = src.index("f_zsSel() =>")
    return ap.Translator().translate(ap.logical_lines(src[g0:src.index(zb.END)] + "\n" + between(src, SB, SE)))


# ----------------------------------------------------------------------------------------------------------------
# broker model
class TVBroker:
    """A small model of TradingView's broker emulator, as assumed here (NOT TradingView itself). All prices in ticks.
      * orders sent at a bar's close work from the next bar (process_orders_on_close = false). A limit fills when the price touches it
        (backtest_fill_limits_assumption = 0).
      * bar path: open -> high -> low -> close when the high is nearer the open (|h - o| < |l - o|), else open -> low -> high -> close.
      * a buy limit fills at the open when the open <= the limit (gap: at the open = a better price), else where the path comes down
        to the limit (at the limit). Sell limit mirrored. Several reachable entries: the one the path reaches first; at the open,
        the one placed first.
      * OCA (oca_type cancel): a fill cancels the other working orders of the same oca_name. Without OCA an opposite entry reverses
        the position; a same-direction entry is not filled while in a position (pyramiding 0).
      * strategy.exit(profit / loss in ticks): TP / SL from the actual fill price, working from the fill point on the same bar's
        path; at an open beyond the TP / SL the exit fills at the open. TP and SL can't be at one point (X > 0), the path decides.
      * no commission / slippage."""

    def __init__(self):
        self.orders = {}
        self.exits = {}
        self.trade = None
        self.closed = []
        self.log = []
        self.seq = 0
        self.bar = -1

    # ---- strategy.* -----------------------------------------------------------
    def entry(self, id, direction, limit=None, oca_name=None, oca_type=None, comment=None):
        if limit is None:
            raise ap.PineRuntimeError("market entry is not expected")
        self.seq += 1
        old = self.orders.get(id)
        self.orders[id] = dict(d=direction, px=tk(limit), oca=oca_name if oca_type == "cancel" else None, comment=comment,
                               seq=old["seq"] if old else self.seq)
        self.log.append(("entry", self.bar, id, direction, tk(limit), comment, oca_name, oca_type))

    def exit(self, id, from_entry=None, profit=None, loss=None, comment_profit=None, comment_loss=None):
        if profit is None or loss is None:
            raise ap.PineRuntimeError("exit without profit / loss")
        self.exits[from_entry] = dict(xid=id, prof=int(profit), loss=int(loss))
        self.log.append(("exit", self.bar, id, from_entry, profit, loss))

    def cancel(self, id):
        if id in self.orders:
            del self.orders[id]
        self.log.append(("cancel", self.bar, id))

    @property
    def position_size(self):
        return 0 if self.trade is None else self.trade["d"]

    def trades_all(self):
        return self.closed + ([self.trade] if self.trade else [])

    # ---- fills ----------------------------------------------------------------
    def _levels(self):
        t = self.trade
        x = self.exits.get(t["id"])
        if x is None:
            return None, None
        return t["px"] + t["d"] * x["prof"], t["px"] - t["d"] * x["loss"]

    def _close(self, px, why):
        t = self.trade
        self.closed.append(dict(t, xpx=px, xbar=self.bar, why=why))
        self.trade = None
        self.log.append(("close", self.bar, t["id"], px, why))

    def _fill(self, oid, px, gap):
        od = self.orders[oid]
        if self.trade is not None:
            if self.trade["d"] == od["d"]:
                return False
            self._close(px, "REV")
        del self.orders[oid]
        self.trade = dict(id=oid, d=od["d"], px=px, bar=self.bar, lim=od["px"], gap=gap, xpx=None, xbar=None, why=None)
        self.log.append(("fill", self.bar, oid, od["d"], px))
        if od["oca"] is not None:
            for k in [k for k, v in self.orders.items() if v["oca"] == od["oca"]]:
                del self.orders[k]
                self.log.append(("oca_cancel", self.bar, k))
        return True

    def _open(self, o):
        if self.trade is not None:
            tp, sl = self._levels()
            if tp is not None:
                d = self.trade["d"]
                if (o >= tp) if d == 1 else (o <= tp):
                    self._close(o, "TP")
                elif (o <= sl) if d == 1 else (o >= sl):
                    self._close(o, "SL")
        for oid in sorted([k for k, v in self.orders.items() if (o <= v["px"] if v["d"] == 1 else o >= v["px"])], key=lambda k: self.orders[k]["seq"]):
            if oid in self.orders:
                self._fill(oid, o, True)

    def _seg(self, p, q):
        cur, skip = p, set()
        while cur != q:
            up = q > cur
            ev = []
            if self.trade is not None:
                tp, sl = self._levels()
                if tp is not None:
                    for x, why in ((tp, "TP"), (sl, "SL")):
                        if (up and cur < x <= q) or (not up and q <= x < cur):
                            ev.append((abs(x - cur), 0, 0, x, why))
            for oid, od in self.orders.items():
                if oid in skip:
                    continue
                x = od["px"]
                if (od["d"] == 1 and not up and q <= x < cur) or (od["d"] == -1 and up and cur < x <= q):
                    ev.append((abs(x - cur), 1, od["seq"], x, oid))
            if not ev:
                break
            ev.sort()
            _, kind, _, x, w = ev[0]
            if kind == 0:
                self._close(x, w)
            elif not self._fill(w, x, False):
                skip.add(w)
                continue
            cur = x

    def run_bar(self, bi, o, h, l, c):
        self.bar = bi
        self._open(o)
        path = [o, h, l, c] if abs(h - o) < abs(l - o) else [o, l, h, c]
        for p, q in zip(path, path[1:]):
            self._seg(p, q)


# ----------------------------------------------------------------------------------------------------------------
# the strategy (Logic section) runner
GATE = {"zaUse1": ["f1u", "f1l", "f1i", "f1a"], "zaUse2": ["f2u", "f2l", "f2i", "f2a"], "zaUse3": ["f3u", "f3l", "f3i", "f3a"],
        "zbUse1": ["zbMa1"]}
for _k in (1, 2, 3, 4):
    GATE[f"zcUse{_k}"] = [f"s{_k}h", f"s{_k}ht", f"s{_k}l", f"s{_k}lt"]
    GATE[f"zdUse{_k}"] = [f"zdL{_k}", f"zdU{_k}", f"zdT{_k}"]
    GATE[f"zfUse{_k}"] = [f"g{_k}{x}" for x in ("k", "kc", "c", "d", "t", "b")]
GATE.update(zgUse1=["zgPk1"], zgUse4=["zgPk4"], zgUseD=["zgPkD"])
ZE_SRC = zr.ZE_KEYS
SEL_DEFAULT = []


def sel_inputs(sel):
    """sel: [(name a, name b, "L" / "S")] -> {pL### / pS###: bool}"""
    out = {f"p{x}{p:03d}": False for p, _, _ in PAIRS for x in "LS"}
    for a, b, s in sel:
        ia, ib = sorted((GI[a], GI[b]))
        out[f"p{s}{PIX[(ia, ib)]:03d}"] = True
    return out


def pd_id(a, b, s):
    ia, ib = sorted((GI[a], GI[b]))
    return ("L|" if s == "L" else "S|") + GN[ia] + "|" + GN[ib]


class Runner:
    """bars: dicts t, tc (default t + 5m), o, h, l, c, feeds by name, m1 / m5 (EMA at the bar's close), fb (higher-TF band)."""

    def __init__(self, sel, ov=None, src=None, feeds_all=False, track_zones=False):
        s = src if src is not None else read(PINE)
        self.code = compile(prog(s), "<ZCS>", "exec")
        inp = ap.inputs(s)
        inp.setdefault("zcStart", zr.START0)
        ov = dict(ov or {})
        for k in ("zcWarm", "zbWarm1"):
            if k not in ov:
                inp[k] = 0
        inp.update(sel_inputs(sel))
        for k in ov:
            if k not in inp:
                raise KeyError(k)
        inp.update(ov)
        self.inp = inp
        self.broker = TVBroker()
        env = ap.make_env(ap.Broker(), [])

        def _insert(arr, i, v):
            if i is None or i < 0 or i > len(arr):
                raise ap.PineRuntimeError("array.insert out of bounds")
            arr.insert(i, v)

        def _concat(a, b):
            a.extend(b)
            return a
        br = self.broker
        env.update(inp)
        env.update(array__new=lambda n=0, v=None: [v] * n, array__insert=_insert, math__ceil=math.ceil, array__copy=lambda a: list(a), array__concat=_concat,
                   array__indexof=lambda arr, v: arr.index(v) if v in arr else -1, array__includes=lambda arr, v: v in arr,
                   str__split=lambda s_, sep: s_.split(sep), str__tonumber=zr.tonum, zdProto=10001, math__round_to_mintick=lambda x: round(x / MT) * MT,
                   syminfo__mintick=MT, hlRun=True, _VARS=set(), _VARIPS=set(), __first__=True,
                   strategy__entry=br.entry, strategy__exit=br.exit, strategy__cancel=br.cancel, strategy__oca__cancel="cancel",
                   strategy__opentrades__entry_id=lambda i: br.trade["id"], strategy__opentrades__entry_bar_index=lambda i: br.trade["bar"],
                   strategy__closedtrades__entry_id=lambda i: br.closed[i]["id"], strategy__closedtrades__entry_bar_index=lambda i: br.closed[i]["bar"],
                   fbFlatBoth=inp["fbFlat"] == "両方向を許可", fbBand=None)
        scratch = dict(env)
        exec(compile(sel_code(s), "<ZCS select>", "exec"), scratch)
        self.need = {k: scratch[k] for k in GATE}
        self.need.update({k: scratch[k] for k in ("zeUse", "zeUse4", "zeUseD")})
        self.needed = [g for g in range(26) if scratch[f"zsN{g:02d}"]]
        self.env = env
        self.feeds_all = feeds_all
        self.track_zones = track_zones
        self.zone_hist = []
        self.bi = -1
        self.ord_hist = []     # working orders after each bar
        self.on_hist = []

    def step(self, b):
        self.bi += 1
        e, br = self.env, self.broker
        o, h, l, c = b["o"], b["h"], b["l"], b["c"]
        if not (o is None or h is None or l is None or c is None or h < max(o, c) or l > min(o, c)):
            br.run_bar(self.bi, tk(o), tk(h), tk(l), tk(c))
        e.update(time=b["t"], time_close=b.get("tc", b["t"] + M5), bar_index=self.bi, barstate__isconfirmed=True, open=o, high=h, low=l, close=c,
                 zbMa1=b.get("m1"), zbMa2=b.get("m5"), fbBand=b.get("fb"),
                 strategy__position_size=br.position_size, strategy__opentrades=0 if br.trade is None else 1, strategy__closedtrades=len(br.closed))
        for f in zr.FEEDS:
            if f not in ZE_SRC:
                e[f] = None if not f.startswith("zgPk") else ""
        for flag, names in GATE.items():
            if self.need[flag] or self.feeds_all:
                for f in names:
                    if f != "zbMa1":
                        e[f] = b.get(f) if not f.startswith("zgPk") else b.get(f, "")
            elif flag == "zbUse1":
                e["zbMa1"] = None
        for f in ZE_SRC:
            e[f] = b.get(f)
        br.bar = self.bi
        exec(self.code, e)
        e["__first__"] = False
        self.ord_hist.append({k: v["px"] for k, v in br.orders.items()})
        self.on_hist.append({p.id: p.on for p in e["zsPd"]})
        if self.track_zones:
            self.zone_hist.append(self.zones())
        return self

    def run(self, bars):
        for b in bars:
            self.step(b)
        return self

    def __getitem__(self, k):
        return self.env[k]

    def zones(self):
        out = []
        for g, ix in enumerate(self.env["zsIx"]):
            if g in (3, 4):
                continue
            for z in ix.z:
                out.append((z.id, z.gid, z.sub, z.tb, z.tt, z.inv))
        return sorted(out)

    def trades(self):
        return [(t["id"], t["d"], t["px"], t["bar"], t["xpx"], t["xbar"], t["why"]) for t in self.broker.trades_all()]

    def pd(self, i):
        return next(p for p in self.env["zsPd"] if p.id == i)


# ----------------------------------------------------------------------------------------------------------------
# ZCR-9 zone snapshots (the reference for the zones and the oracle's zone set)
def zcr_snaps(bars, need, prm):
    ov = {k: v for k, v in need.items() if k in GATE or k in ("zeUse", "zeUse4", "zeUseD")}
    ov.pop("zbUse1", None)
    ov.update(zbUse1=False, zbUse2=False)
    zi = ap.inputs(read(ZCR))
    ov.update({k: v for k, v in prm.items() if k in zi and k not in ov and k not in ("zcStart", "zcWarm", "zbWarm1")})
    r = zr.Runner(ov)
    snaps = []
    for b in bars:
        r.step(b)
        snaps.append(sorted((q.id, q.gid, q.sub, q.tb, q.tt, q.inv, q.typ, q.tf) for q in r.env["zxZ"]))
    return snaps


# ----------------------------------------------------------------------------------------------------------------
# independent oracle (from the spec)
def qgid(z):
    return 22 + z["tf"] if z["typ"] == 4 and z["inv"] else z["gid"]


def elig(z, g, d):
    return qgid(z) == g and (g < 15 or g > 18 or z["sub"] == d)


def oracle(bars, sel, prm, snaps):
    """returns dict(orders=[{id: px} per bar], on=[{id: on} per bar], trades=[...], stat={...})"""
    br = TVBroker()
    half, warm1 = prm["zHalf"], prm["zbWarm1"]
    dep_t, dep_ms, xt = ticks(prm["zcDepW"]), prm["zcDepMin"] * M1, ticks(prm["zsX"])
    need_g = set()
    for a, b_, s in sel:
        need_g |= {GI[a], GI[b_]}
    use_ma = (3 in need_g, 4 in need_g)
    pds = []
    for p, a, b_ in PAIRS:
        for s, d in (("L", 1), ("S", -1)):
            if any(sorted((GI[x], GI[y])) == [a, b_] and ss == s for x, y, ss in sel):
                pds.append(dict(a=a, b=b_, d=d, id=("L|" if d == 1 else "S|") + GN[a] + "|" + GN[b_], on=False, hb=None, ht=None, outT=None,
                                keys=[], act=False, px=None, oband=None, okey=None, fb=-1))
    ma = [None, None]           # (tb, tt) of the ZB bands valid now
    ma1n = 0
    zprev = []
    out = dict(orders=[], on=[], stat=dict(depd=0, dept=0, blocked_on=0, fbblock=0, modify=0, cancel=0, place=0, fills=0, ma_fill=0, fvg_fill=0, ifvg_fill=0, hull_keep=0, hull_move=0))
    st = out["stat"]
    nbars = 0

    def zset(snap):
        zs = [dict(id=x[0], gid=x[1], sub=x[2], tb=x[3], tt=x[4], inv=x[5], typ=x[6], tf=x[7]) for x in snap]
        for k in (0, 1):
            if ma[k] is not None:
                zs.append(dict(id=k + 1, gid=3 + k, sub=0, tb=ma[k][0], tt=ma[k][1], inv=False, typ=1, tf=k))
        return zs

    def cands(zs, pd):
        A = [z for z in zs if elig(z, pd["a"], pd["d"])]
        B = [z for z in zs if elig(z, pd["b"], pd["d"])]
        return [(max(x["tb"], y["tb"]), min(x["tt"], y["tt"]), x["id"], y["id"]) for x in A for y in B if max(x["tb"], y["tb"]) <= min(x["tt"], y["tt"])]

    for k, bar in enumerate(bars):
        o, h, l, c = bar["o"], bar["h"], bar["l"], bar["c"]
        bad = o is None or h is None or l is None or c is None or h < max(o, c) or l > min(o, c)
        if not bad:
            br.run_bar(k, tk(o), tk(h), tk(l), tk(c))
        br.bar = k
        t, tc = bar["t"], bar.get("tc", bar["t"] + M5)
        # (1) fills
        fid = None
        for tr in br.trades_all():
            if tr["bar"] == k:
                fid = tr["id"]
        if fid is not None:
            st["fills"] += 1
            for pd in pds:
                if pd["act"]:
                    br.cancel(pd["id"])
                    pd["act"] = False
                if pd["id"] == fid:
                    pd.update(on=True, fb=k, outT=None, hb=pd["oband"][0], ht=pd["oband"][1], keys=[pd["okey"]])
                    st["ma_fill"] += 1 if pd["a"] in (3, 4) or pd["b"] in (3, 4) else 0
                    st["fvg_fill"] += 1 if 15 <= pd["b"] <= 18 or 15 <= pd["a"] <= 18 else 0
                    st["ifvg_fill"] += 1 if pd["b"] >= 22 else 0
        # (2) contact / departure with the zones valid during this bar
        zp = zset(zprev)
        byid = {z["id"]: z for z in zp}
        for pd in pds:
            if bad:
                pd["outT"] = None
                continue
            if pd["fb"] == k:
                continue
            unk = False
            if pd["on"]:
                hull = None
                for ia, ib in pd["keys"]:
                    if ia in (1, 2) and ma[ia - 1] is None or ib in (1, 2) and ma[ib - 1] is None:
                        unk = True
                        continue
                    za, zb_ = byid.get(ia), byid.get(ib)
                    if za and zb_ and elig(za, pd["a"], pd["d"]) and elig(zb_, pd["b"], pd["d"]):
                        cl, ct = max(za["tb"], zb_["tb"]), min(za["tt"], zb_["tt"])
                        if cl <= ct:
                            hull = (cl, ct) if hull is None else (min(hull[0], cl), max(hull[1], ct))
                if hull is not None:
                    st["hull_move"] += 1 if hull != (pd["hb"], pd["ht"]) else 0
                    pd["hb"], pd["ht"] = hull
                else:
                    st["hull_keep"] += 1
            hT, lT = tk(h), tk(l)
            touched = [x for x in cands(zp, pd) if x[0] <= hT and x[1] >= lT]
            if touched:
                pd.update(on=True, outT=None, hb=min(x[0] for x in touched), ht=max(x[1] for x in touched), keys=[(x[2], x[3]) for x in touched])
            elif pd["on"]:
                if unk or (pd["ht"] >= lT and pd["hb"] <= hT):
                    pd["outT"] = None
                else:
                    dist = lT - pd["ht"] if lT > pd["ht"] else pd["hb"] - hT
                    if pd["outT"] is None:
                        pd["outT"] = t
                    if dist >= dep_t or tc - pd["outT"] >= dep_ms:
                        st["depd" if dist >= dep_t else "dept"] += 1
                        pd.update(on=False, outT=None)
        # (3) zones after this bar + ZB bands at this bar's close
        if not bad:
            zprev = snaps[k]
            m1 = bar.get("m1") if use_ma[0] else None
            v1 = None
            if m1 is not None:
                ma1n += 1
                if ma1n > warm1:
                    v1 = m1
            if use_ma[0]:
                ma[0] = None if v1 is None else (tk(v1 - half), tk(v1 + half))
            if use_ma[1]:
                m5 = bar.get("m5")
                ma[1] = None if m5 is None else (tk(m5 - half), tk(m5 + half))
        # (4) orders
        live = not bad and tc >= prm["zcStart"] and nbars >= prm["zcWarm"]
        flat = br.trade is None
        zc_ = zset(zprev)
        fbv = bar.get("fb")
        for pd in pds:
            want = None
            if live and flat and not pd["on"]:
                ok = not prm["fbUse"] or (fbv is not None and (fbv == pd["d"] or (fbv == 0 and prm["fbFlat"] == "両方向を許可")))
                if ok:
                    cT = tk(c)
                    byc = {z["id"]: z for z in zc_}

                    def side_ok(zid, g):
                        z = byc[zid]
                        return not (15 <= g <= 18) or (cT > z["tt"] if pd["d"] == 1 else cT < z["tb"])
                    cs = [x for x in cands(zc_, pd) if side_ok(x[2], pd["a"]) and side_ok(x[3], pd["b"])]
                    if pd["d"] == 1:
                        cs = [x for x in cs if x[1] < cT]
                        want = max(cs, key=lambda x: (x[1], x[0], -x[2], -x[3])) if cs else None
                    else:
                        cs = [x for x in cs if x[0] > cT]
                        want = min(cs, key=lambda x: (x[0], x[1], x[2], x[3])) if cs else None
                elif cands(zc_, pd):
                    st["fbblock"] += 1
            elif live and flat and pd["on"]:
                st["blocked_on"] += 1
            if want is not None:
                px = want[1] if pd["d"] == 1 else want[0]
                if not pd["act"] or px != pd["px"]:
                    st["modify" if pd["act"] else "place"] += 1
                    br.entry(pd["id"], pd["d"], limit=px * MT, oca_name="ZCS", oca_type="cancel", comment=pd["id"])
                    br.exit("X" + pd["id"], from_entry=pd["id"], profit=xt, loss=xt)
                pd.update(act=True, px=px, oband=(want[0], want[1]), okey=(want[2], want[3]))
            elif pd["act"]:
                br.cancel(pd["id"])
                st["cancel"] += 1
                pd["act"] = False
        nbars += 1
        out["orders"].append({kk: v["px"] for kk, v in br.orders.items()})
        out["on"].append({pd["id"]: pd["on"] for pd in pds})
    out["trades"] = [(t_["id"], t_["d"], t_["px"], t_["bar"], t_["xpx"], t_["xbar"], t_["why"]) for t_ in br.trades_all()]
    out["broker"] = br
    return out


# ----------------------------------------------------------------------------------------------------------------
# random data
def zcs_bars(seed, n5=2500):
    """tests/zcr_sim.py's random paths (all 7 kinds' feeds) + the EMA at the close (= the next bar's p1 / p5) + a higher-TF band"""
    bars = zr.random_bars(seed, n5)
    rnd = random.Random(seed * 7 + 1)
    fb = 1
    for i, b in enumerate(bars):
        nx = bars[i + 1] if i + 1 < len(bars) else {}
        b["m1"], b["m5"] = nx.get("p1"), nx.get("p5")
        if rnd.random() < 0.02:
            fb = rnd.choice([1, -1, 0, None])
        b["fb"] = fb
    return bars


FREQ = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 15, 16, 17, 22, 23]


def random_sel(seed, n=22):
    rnd = random.Random(seed * 31 + 5)
    out = set()
    while len(out) < n:
        if len(out) < n - 6:
            a, b = sorted(rnd.sample(FREQ, 2))
        else:
            a, b = sorted(rnd.sample(range(26), 2))
        out.add((GN[a], GN[b], rnd.choice("LS")))
    return sorted(out)


RANDOM_PRM = [
    dict(),
    dict(zsX=5, zcDepW=3.0, zcDepMin=15),
    dict(zsX=10, zHalf=1.0, fbUse=True),
    dict(zHalf=3.0, zcDepMin=20, fbUse=True, fbFlat="両方向を許可", zbWarm1=200),
    dict(zsX=5, zHalf=0.5, zcDepW=1.5, zcDepMin=10, zcWarm=300),
    dict(zsX=10, zcMax=3, zgHalf=1.0, zgRev=3.0, zcStart=T0 + 400 * M5),
]


def prm_of(r):
    p = dict(r.inp)
    return p


SNAP_CACHE = {}


def random_case(seed, src=None, n5=2500):
    bars = zcs_bars(seed, n5)
    sel = random_sel(seed)
    ov = RANDOM_PRM[seed % len(RANDOM_PRM)]
    r = Runner(sel, ov, src=src, track_zones=src is None).run(bars)
    key = (seed, n5)
    if key not in SNAP_CACHE:
        SNAP_CACHE[key] = zcr_snaps(bars, r.need, prm_of(r))
    snaps = SNAP_CACHE[key]
    orc = oracle(bars, sel, prm_of(r), snaps)
    return bars, sel, ov, r, snaps, orc


def compare(r, orc, snaps=None):
    bad = []
    for k, (a, b) in enumerate(zip(r.ord_hist, orc["orders"])):
        if a != b:
            bad.append(f"orders bar {k}: {a} vs {b}")
            break
    for k, (a, b) in enumerate(zip(r.on_hist, orc["on"])):
        if a != b:
            bad.append(f"on bar {k}: {a} vs {b}")
            break
    if r.trades() != orc["trades"]:
        bad.append(f"trades {r.trades()[:5]} vs {orc['trades'][:5]}")
    return not bad, "; ".join(bad)


def random_vs_oracle(seeds):
    for seed in seeds:
        bars, sel, ov, r, snaps, orc = random_case(seed)
        ok, det = compare(r, orc)
        tr = r.trades()
        st = orc["stat"]
        lg = r.broker.log
        for k_, v_ in (("trades", len(tr)), ("tp", sum(1 for t in tr if t[6] == "TP")), ("sl", sum(1 for t in tr if t[6] == "SL")),
                       ("gap", sum(1 for t in r.broker.trades_all() if t["gap"] and t["px"] != t["lim"])),
                       ("long", sum(1 for t in tr if t[1] == 1)), ("short", sum(1 for t in tr if t[1] == -1)),
                       ("oca", sum(1 for x in lg if x[0] == "oca_cancel")), ("rev", sum(1 for t in tr if t[6] == "REV")),
                       ("place", st["place"]), ("modify", st["modify"]), ("cancel", st["cancel"]), ("depd", st["depd"]), ("dept", st["dept"]),
                       ("blocked_on", st["blocked_on"]), ("fbblock", st["fbblock"]), ("ma_fill", st["ma_fill"]), ("fvg_fill", st["fvg_fill"]),
                       ("ifvg_fill", st["ifvg_fill"]), ("hull_keep", st["hull_keep"]), ("hull_move", st["hull_move"])):
            COVER[k_] = COVER.get(k_, 0) + v_
        check(f"C random seed {seed} == oracle (選択 {len(sel)} ペア・方向, {ov})", ok and len(tr) >= 5, f"trades={len(tr)} stat={st} | {det}")
        zs_ok, zdet = True, ""
        # Z: the strategy's zones == ZCR-9's zones after every bar
        for k, mine in enumerate(r.zone_hist):
            ref = [(x[0], x[1], x[2], x[3], x[4], x[5]) for x in snaps[k]]
            if mine != ref:
                zs_ok, zdet = False, f"bar {k}: {mine[:4]} vs {ref[:4]}"
                break
        nz = len(snaps[-1])
        gids = sorted(set(x[1] for s_ in snaps for x in s_))
        check(f"Z seed {seed}: 毎足の有効 Zone (ID・根拠 ID・向き・帯・iFVG) が ZCR-9 (同じ取得値・同じ種類 ON) と一致、必要な根拠 ID だけ",
              zs_ok and len(r.zone_hist) == len(bars) and nz > 5 and set(gids) <= set(g if g < 22 else g - 7 for g in r.needed), f"zones={nz} gids={gids} needed={r.needed} {zdet}")
    need = dict(trades=150, tp=40, sl=40, gap=3, long=40, short=40, oca=30, place=200, modify=20, cancel=100, depd=50, dept=20, blocked_on=200,
                fbblock=20, ma_fill=5, fvg_fill=5, ifvg_fill=1, hull_keep=10, hull_move=10)
    check("C 乱数系列の合計で各機能が使われている (TP / SL・ギャップ約定・OCA 取消・指値の変更・取消・距離 / 時間の離脱・接触中で見送り・フィルターで見送り・MA / FVG / iFVG のペア ほか)",
          all(COVER.get(k, 0) >= v for k, v in need.items()) and COVER.get("rev", 0) == 0,
          str({k: (COVER.get(k, 0), v) for k, v in need.items() if COVER.get(k, 0) < v}) + " " + str(COVER))


# ----------------------------------------------------------------------------------------------------------------
# fixed cases
def rows_bars(rows, feeds0, start=4310.0, feeds=None, extra=None):
    bars = zr.bars_from_rows(rows, feeds0, start=start, feeds=feeds)
    for i, b in enumerate(bars):
        for k, v in ((extra or {}).get(i, {})).items():
            b[k] = v
    return bars


LP = ("ZC-D", "ZC-W", "L")
SP = ("ZC-D", "ZC-W", "S")
LID, SID = pd_id(*LP), pd_id(*SP)
BASE = zr.merge(zr.zc(2, 1, 4300.0), zr.zc(3, -1, 4301.0))      # ZC-D 4298..4302, ZC-W 4299..4303 -> common 4299..4302


def fixed_suite(src=None, record=True):
    res = []

    def ck(name, ok, det=""):
        res.append((name, bool(ok), det))

    def run(sel, bars, ov=None, **kw):
        return Runner(sel, ov, src=src, **kw).run(bars)

    def orc_ok(r, bars, sel):
        snaps = zcr_snaps(bars, r.need, prm_of(r))
        o = oracle(bars, sel, prm_of(r), snaps)
        return compare(r, o)

    P02, P99 = tk(4302), tk(4299)
    # F1 LONG above the band: buy limit at the top; SHORT none. Fill on a later bar at the top, TP / SL = fill +- X
    rows = [(4310, 4312, 4306, 4308), (4308, 4309, 4301, 4305), (4305, 4318, 4304, 4317)]
    b1 = rows_bars(rows, BASE)
    r = run([LP, SP], b1)
    ok, det = orc_ok(r, b1, [LP, SP])
    ck("F1 価格が帯より上 → 帯の上端 (共通区間 4299〜4302 の 4302) に買い指値、SHORT は置かない。次の足以降に上端で約定、TP = 約定価格 + 15 で決済。オラクルと一致",
       r.ord_hist[0] == {LID: P02} and r.ord_hist[1] == {LID: P02} and r.trades() == [(LID, 1, P02, 2, tk(4317), 3, "TP")] and r.ord_hist[2] == {} and ok,
       f"{r.ord_hist[:4]} {r.trades()} {det}")
    lg = [x for x in r.broker.log if x[0] == "entry"]
    ck("F1 注文: ID = コメントの先頭 = 採用ペアと方向 (L|ZC-D|ZC-W)、帯をコメントに残す、OCA グループ ZCS (cancel)。SL / TP は profit = loss = 1500 ティック ($15)",
       lg and lg[0][2] == LID and lg[0][5] == LID + " 4299-4302" and lg[0][6] == "ZCS" and lg[0][7] == "cancel"
       and [x for x in r.broker.log if x[0] == "exit"][0][4:6] == (1500, 1500), str(r.broker.log[:3]))
    # F2 SHORT below the band
    b2 = rows_bars([(4290, 4292, 4288, 4291), (4291, 4300, 4290, 4295), (4295, 4296, 4283, 4284)], BASE, start=4290.0)
    r = run([LP, SP], b2)
    ck("F2 価格が帯より下 → 帯の下端 4299 に売り指値 (LONG は置かない)。上がってきて約定、TP = 約定 − 15 = 4284",
       r.ord_hist[0] == {SID: P99} and r.trades() == [(SID, -1, P99, 2, tk(4284), 3, "TP")], f"{r.ord_hist[:3]} {r.trades()}")
    # F3 close inside the band / exactly at the top: nothing
    r = run([LP, SP], rows_bars([(4300, 4300.5, 4299.5, 4300)], BASE, start=4300.0))
    r2 = run([LP, SP], rows_bars([(4302, 4302, 4302, 4302)], BASE, start=4302.0))
    ck("F3 終値が帯の中 → LONG も SHORT も置かない。終値 = 上端ちょうど (4302) も LONG は置かない (終値 > 上端のときだけ)",
       r.ord_hist == [{}, {}] and r2.ord_hist[0] == {} and r2.ord_hist[1] == {}, f"{r.ord_hist} {r2.ord_hist}")
    # F4 no overlap / end point overlap
    nov = zr.merge(zr.zc(2, 1, 4300.0), zr.zc(3, -1, 4306.01))
    touch = zr.merge(zr.zc(2, 1, 4300.0), zr.zc(3, -1, 4304.0))
    r = run([LP], rows_bars([(4320, 4320, 4320, 4320)], nov, start=4320.0))
    r2 = run([LP], rows_bars([(4320, 4320, 4320, 4320)], touch, start=4320.0))
    ck("F4 共通区間が無い (4298〜4302 と 4304.01〜4308.01) → 発注しない。端点一致 (4302 と 4302〜4306) は重なり → 4302 に買い指値",
       r.ord_hist == [{}, {}] and r2.ord_hist[0] == {LID: P02}, f"{r.ord_hist} {r2.ord_hist}")
    # F5 an extra evidence overlapping the pair's band does not narrow it (ZD-D needed by another selected pair)
    ex = zr.merge(BASE, zr.zd(2, 4300.5, half=0.5))
    sel5 = [LP, SP, ("ZD-D", "ZG-D", "L")]
    r = run(sel5, rows_bars([(4310, 4310, 4310, 4310)], zr.merge(ex, {"zdL3": 4299.4, "zdU3": 4299.6, "zdT3": float(T0 - 3_600_000)}), start=4310.0))
    r2 = run(sel5, rows_bars([(4290, 4290, 4290, 4290)], zr.merge(ex, {"zdL3": 4301.4, "zdU3": 4301.6, "zdT3": float(T0 - 3_600_000)}), start=4290.0))
    zd_in = [z for z in r.zones() if z[1] == 11]
    ck("F5 別の根拠 (ZD-D 4297.5〜4301.5 / 4299.5〜4303.5) が重なっても帯を狭めない: LONG 4302・SHORT 4299 のまま (ZD-D の Zone は登録されている)",
       r.ord_hist[0] == {LID: P02} and r2.ord_hist[0] == {SID: P99} and len(zd_in) == 1, f"{r.ord_hist} {r2.ord_hist} {r.zones()}")
    # F6 a zone registered on a bar that already went through it: no fill in the past, fill only when the price comes back
    b6 = rows_bars([(4310, 4310, 4310, 4310), (4310, 4310, 4310, 4310), (4304, 4309, 4300, 4306), (4306, 4308, 4303, 4307), (4307, 4308, 4302, 4305)],
                   {}, feeds={3: BASE})
    r = run([LP], b6)
    ck("F6 タッチ足 (安値 4300) の確定で Zone が登録された場合: その足の帯端では約定させない。注文はその足の終わりから (4302)、"
       "次の足 (安値 4303) は約定なし、価格が戻った足 (安値 4302) で 4302 に約定",
       r.ord_hist[2] == {} and r.ord_hist[3] == {LID: P02} and r.trades() and r.trades()[0][2:4] == (P02, 5) and len(r.trades()) == 1, f"{r.ord_hist} {r.trades()}")
    # F7 cancels: the FVG becomes an iFVG / the POC moves away (the overlap disappears)
    fv = zr.merge(zr.zf(0, T0 - 12 * M5, 4310.0, d=1, top=4303.0, bot=4296.0), zr.zc(2, 1, 4300.0))
    fl = ("ZC-D", "ZF-FVG-1H", "L")
    fid = pd_id(*fl)
    b7 = rows_bars([(4310, 4310, 4310, 4310)] * 3, fv, feeds={2: zr.zf(0, T0 - 6 * M5, 4290.0)})
    r = run([fl], b7)
    ck("F7a 上昇 FVG × ZC-D の LONG: 4302 に買い指値 → FVG が iFVG に転換した足で取消 (FVG のペアの候補が消える)",
       r.ord_hist[0] == {fid: P02} and r.ord_hist[1] == {fid: P02} and r.ord_hist[2] == {} and r["st"].nIfvg == 1, f"{r.ord_hist}")
    pd7 = zr.merge(zr.zc(2, 1, 4300.0), zr.zd(2, 4300.5))
    dl = ("ZC-D", "ZD-D", "L")
    did = pd_id(*dl)
    b7b = rows_bars([(4310, 4310, 4310, 4310)] * 3, pd7, feeds={2: zr.zd(2, 4330.0, t=T0 - 1_800_000)})
    r = run([dl], b7b)
    ck("F7b ZC-D × ZD-D: 重なり (4298.5〜4302) の上端に買い指値 → POC が 4330 へ移って重なりが消えた足で取消",
       r.ord_hist[0] == {did: P02} and r.ord_hist[2] == {}, f"{r.ord_hist}")
    zg7 = zr.merge(zr.zc(2, 1, 4300.0), zr.zg(2, zr.zg_blk(T0 - 288 * M5, T0, 3, [(7, 1, 2, 4301.0)])))
    gl = ("ZC-D", "ZG-D", "L")
    gid_ = pd_id(*gl)
    b7c = rows_bars([(4310, 4310, 4310, 4310)] * 2, zg7, feeds={2: zr.zg(2, zr.zg_blk(T0 - 100 * M5, T0 + M5, 8))})
    r = run([gl], b7c)
    ck("F7c ZC-D × ZG-D (ボトム 4301 ± 2 → 共通 4299〜4302): 4302 に買い指値 → ZG の期限 (日足 5 本) で Zone が消えた足で取消",
       r.ord_hist[0] == {gid_: P02} and r.ord_hist[1] == {gid_: P02} and r.ord_hist[2] == {} and all(z[1] != 21 for z in r.zones()), f"{r.ord_hist} {r.zones()}")
    # F8 FVG direction: a falling FVG is only for SHORT
    ff = zr.merge(zr.zf(0, T0 - 12 * M5, 4310.0, d=-1, top=4303.0, bot=4296.0), zr.zc(2, 1, 4300.0))
    fs = ("ZC-D", "ZF-FVG-1H", "S")
    r = run([fl], rows_bars([(4310, 4310, 4310, 4310)], ff))
    r2 = run([fs], rows_bars([(4290, 4290, 4290, 4290)], ff, start=4290.0))
    ri = run([("ZC-D", "ZF-iFVG-1H", "L"), ("ZC-D", "ZF-iFVG-1H", "S")], rows_bars([(4310, 4310, 4310, 4310), (4310, 4310, 4310, 4310)], ff,
                                                                         feeds={1: zr.zf(0, T0 - 6 * M5, 4310.0)}))
    ck("F8 通常 FVG の向き: 下降 FVG は LONG のペアでは候補にしない (注文なし)、SHORT のペアでは 4298 (下端) に売り指値。iFVG (下降 FVG が転換) は LONG でも使える",
       r.ord_hist[0] == {} and r2.ord_hist[0] == {pd_id(*fs): tk(4298)} and ri.ord_hist[1] == {pd_id("ZC-D", "ZF-iFVG-1H", "L"): P02},
       f"{r.ord_hist} {r2.ord_hist} {ri.ord_hist}")
    # F9 the MA band moves: the limit follows the EMA at each close; EMA unknown -> cancel
    ml = ("ZB-5m", "ZC-D", "L")
    mid = pd_id(*ml)
    b9 = rows_bars([(4310, 4310, 4310, 4310)] * 3, zr.zc(2, 1, 4300.0),
                   extra={0: {"m5": 4300.0}, 1: {"m5": 4299.0}, 2: {"m5": 4298.5}, 3: {"m5": None}})
    r = run([ml], b9)
    ck("F9 ZB-5m × ZC-D: 指値は毎足の確定 EMA の帯で更新 (4302 → 4301 → 4300.5)、EMA が不明の足で取消",
       [x.get(mid) for x in r.ord_hist] == [P02, tk(4301), tk(4300.5), None], f"{r.ord_hist}")
    # F10 SL / TP from the actual fill price; a gap below the limit fills at the open (not faked to the band edge)
    b10 = rows_bars([(4295, 4298, 4294, 4297), (4297, 4311, 4296, 4309)], BASE)
    r = run([LP], b10)
    b10b = rows_bars([(4308, 4308, 4301, 4303), (4270, 4272, 4268, 4271)], BASE)
    r2 = run([LP], b10b)
    b10c = rows_bars([(4308, 4308, 4301, 4303), (4303, 4304, 4286, 4290)], BASE)
    r3 = run([LP], b10c)
    ck("F10 ギャップで帯より下に寄り付いた足は始値 4295 で約定 (帯端に偽装しない)、TP = 4295 + 15 = 4310 で決済。"
       "SL は約定 4302 − 15 = 4287 (足の中) / ギャップで 4270 に寄り付いたら始値で決済",
       r.trades() == [(LID, 1, tk(4295), 1, tk(4310), 2, "TP")] and r3.trades() == [(LID, 1, P02, 1, tk(4287), 2, "SL")]
       and r2.trades() == [(LID, 1, P02, 1, tk(4270), 2, "SL")], f"{r.trades()} {r2.trades()} {r3.trades()}")
    # F11 several candidates: the first fill cancels the others (OCA), no orders while holding
    two = zr.merge(BASE, zr.zc(0, 1, 4305.0), zr.zc(1, -1, 4306.0))       # ZC-1H 4303..4307, ZC-4H 4304..4308 -> 4304..4307
    p2 = ("ZC-1H", "ZC-4H", "L")
    b11 = rows_bars([(4320, 4320, 4300, 4301), (4301, 4303, 4300, 4302), (4302, 4318, 4301, 4317)], two, start=4320.0)
    r = run([LP, p2], b11)
    lg = r.broker.log
    ck("F11 LONG 候補 2 つ (4302 / 4307): 価格が先に届く 4307 だけ約定し、4302 の注文は OCA で取消 (同じ足で 4302 も通過したが約定しない)。保有中は注文なし",
       r.ord_hist[0] == {LID: P02, pd_id(*p2): tk(4307)} and len(r.trades()) == 1 and r.trades()[0][:4] == (pd_id(*p2), 1, tk(4307), 1) and ("oca_cancel", 1, LID) in lg and r.ord_hist[1] == {} and r.ord_hist[2] == {},
       f"{r.ord_hist} {r.trades()} {lg}")
    # F12 LONG and SHORT touched on one bar: no reversal
    up = zr.merge(BASE, zr.zc(0, 1, 4320.0), zr.zc(1, -1, 4321.0))        # 4318..4322 / 4319..4323 -> 4319..4322
    s2 = ("ZC-1H", "ZC-4H", "S")
    b12 = rows_bars([(4310, 4325, 4295, 4300)], up)
    r = run([LP, s2], b12)
    ck("F12 LONG (4302) と SHORT (4319) の両方に同じ足で触れても反転しない: 先に届いた LONG だけ約定 (SHORT は OCA で取消)、LONG は TP 4317 で決済",
       r.ord_hist[0] == {LID: P02, pd_id(*s2): tk(4319)} and r.trades() == [(LID, 1, P02, 1, tk(4317), 1, "TP")], f"{r.ord_hist} {r.trades()}")
    # F13 re-entry needs a departure: after the TP the price stays 2-4 above the band (< $5) -> no order until 30 minutes outside
    rows13 = [(4308, 4309, 4301, 4305), (4305, 4318, 4301.5, 4317)] + [(4306, 4306.5, 4304, 4305)] * 6 + [(4305, 4305, 4301.5, 4304)]
    r = run([LP], rows_bars(rows13, BASE))
    oh = [LID in x for x in r.ord_hist]
    ck("F13 決済後、離脱 (5 ドル / 30 分) なしでは再エントリーしない: TP の足は帯に掛かり、その後 2〜4 ドル上で 25 分は注文なし、"
       "外側 30 分で離脱 → 注文 → 再接触で 2 回目の約定",
       r.trades()[0][5] == 2 and oh[2:8] == [False] * 6 and oh[8] is True and len(r.trades()) == 2 and r.trades()[1][3] == 9, f"{oh} {r.trades()}")
    rows13b = [(4308, 4309, 4301, 4305), (4305, 4318, 4301.5, 4317), (4317, 4318, 4307, 4310), (4310, 4310, 4301, 4305)]
    r = run([LP], rows_bars(rows13b, BASE))
    ck("F13b 帯の端から 5 ドル以上離れた足 (安値 4307) で離脱 → その足の終わりに注文 → 再接触で約定",
       [LID in x for x in r.ord_hist][:4] == [True, False, False, True] and len(r.trades()) == 2 and r.trades()[1][3] == 4, f"{r.ord_hist} {r.trades()}")
    # F14 a touch while holding another pair: that pair is in contact, no late entry after the exit
    hold = zr.merge(BASE, zr.zc(0, 1, 4310.0), zr.zc(1, -1, 4311.0))      # 4308..4312 / 4309..4313 -> 4309..4312
    p14 = ("ZC-1H", "ZC-4H", "L")
    rows14 = [(4305, 4306, 4301, 4304), (4304, 4312, 4303, 4311), (4311, 4318, 4310, 4316)] + [(4316, 4316, 4314, 4315)] * 4
    r = run([LP, p14], rows_bars(rows14, hold, start=4305.0))
    pid14 = pd_id(*p14)
    ck("F14 保有中 (4302 で LONG) に別のペアの帯 (4309〜4312) に触れる → そのペアは接触中。決済 (TP 4317) の後、離脱までそのペアの注文は置かない",
       r.ord_hist[0] == {LID: P02} and r.trades()[0][:4] == (LID, 1, P02, 1) and r.trades()[0][6] == "TP" and r.pd(pid14).on
       and all(pid14 not in x for x in r.ord_hist[2:]), f"{r.ord_hist} {r.trades()}")
    # F15 the higher-TF filter
    both = zr.merge(zr.zc(2, 1, 4300.0), zr.zc(2, -1, 4330.0), zr.zc(3, 1, 4301.0), zr.zc(3, -1, 4331.0))
    exp = {}
    for nm, ov_, fbv in (("赤", dict(fbUse=True), -1), ("青", dict(fbUse=True), 1), ("フラット・見送り", dict(fbUse=True), 0),
                         ("フラット・両方向", dict(fbUse=True, fbFlat="両方向を許可"), 0), ("na", dict(fbUse=True), None), ("OFF", {}, None)):
        rr = run([LP, SP], rows_bars([(4310, 4310, 4310, 4310)], both, extra={0: {"fb": fbv}, 1: {"fb": fbv}}), ov_)
        exp[nm] = sorted(rr.ord_hist[0])
    ck("F15 上位足フィルター: 赤 → SHORT だけ、青 → LONG だけ、フラット (見送り) → どちらも置かない、フラット (両方向を許可) → 両方、na → 置かない、OFF → 両方",
       exp == {"赤": [SID], "青": [LID], "フラット・見送り": [], "フラット・両方向": [LID, SID], "na": [], "OFF": [LID, SID]}, str(exp))
    b15 = rows_bars([(4310, 4310, 4310, 4310)] * 2, both, extra={0: {"fb": 1}, 1: {"fb": -1}, 2: {"fb": None}})
    r = run([LP, SP], b15, dict(fbUse=True))
    ck("F15b 帯色が変わった足で許可されなくなった注文は取消 (青 → 赤 → na)",
       [sorted(x) for x in r.ord_hist] == [[LID], [SID], []], f"{r.ord_hist}")
    # F16 start inside the band: in contact from the first touch, no order until a departure
    r = run([LP, SP], rows_bars([(4300, 4301, 4299.5, 4300.5), (4300.5, 4304.5, 4300.5, 4304), (4304, 4305, 4303.5, 4304.5)], BASE, start=4300.0))
    ck("F16 チャート開始時に帯の中 → 最初に触れた足から接触中。帯の 2 ドル上へ出ても離脱前は LONG を置かない",
       r.ord_hist == [{}, {}, {}, {}] and r.pd(LID).on and r.pd(SID).on, f"{r.ord_hist}")
    # F17 start date / warm-up
    r = run([LP], rows_bars([(4310, 4310, 4310, 4310)] * 4, BASE), dict(zcWarm=3))
    r2 = run([LP], rows_bars([(4310, 4310, 4310, 4310)] * 4, BASE), dict(zcStart=T0 + 3 * M5))
    ck("F17 助走本数 3 → 4 本目 (bar 3) の終わりから発注。発注開始日時 = bar 2 の確定時刻 → bar 2 から発注",
       [LID in x for x in r.ord_hist] == [False, False, False, True, True] and [LID in x for x in r2.ord_hist] == [False, False, True, True, True],
       f"{r.ord_hist} {r2.ord_hist}")
    # F18 SL inside the band area: re-entry only after a departure
    rows18 = [(4308, 4309, 4301, 4305), (4305, 4305, 4286, 4300), (4300, 4304, 4299.5, 4303.5), (4303.5, 4305, 4303, 4304), (4304, 4307.5, 4304, 4307)]
    r = run([LP, SP], rows_bars(rows18, BASE))
    ck("F18 SL 4287 で決済した足 (帯の中で確定) は接触中 (SHORT もこの足で帯に触れたので接触中)。その後 帯の 1〜2 ドル上に出ても離脱前は LONG を置かない",
       r.trades()[0] == (LID, 1, P02, 1, tk(4287), 2, "SL") and [LID in x for x in r.ord_hist] == [True, False, False, False, False, False]
       and r.pd(SID).on, f"{r.ord_hist} {r.trades()}")
    # F19 the best candidate with bands of different widths (a wide FVG): the search must not stop at the first lower zone
    w19 = zr.merge(zr.zf(0, T0 - 12 * M5, 4310.0, d=1, top=4305.0, bot=4290.0), zr.zc(2, 1, 4303.0), zr.zc(2, -1, 4297.0))
    f19 = ("ZC-D", "ZF-FVG-1H", "L")
    b19 = rows_bars([(4310, 4310, 4310, 4310)] * 2, w19, feeds={1: zr.merge(zr.zf(0, T0 - 6 * M5, 4310.0, d=1, top=4299.0, bot=4296.0),
                                                                    zr.zc(2, 1, 4400.0, key=T0 - 5_000_000))})
    r = run([f19], b19)
    ck("F19 幅の違う帯 (FVG 4290〜4305 と 4296〜4299、ZC-D 4301〜4305 / 4295〜4299 / 4398〜4402): LONG は上端が最も高い候補 4301〜4305 の 4305 "
       "(少ない方の FVG を外側にたどり、下端の高い FVG の候補 4299 で探索を止めない)",
       r.ord_hist[0] == {pd_id(*f19): tk(4305)} and r.ord_hist[1] == {pd_id(*f19): tk(4305)} and r.ord_hist[2] == {pd_id(*f19): tk(4305)}
       and orc_ok(r, b19, [f19])[0], f"{r.ord_hist}")
    # F20 the normal FVG must be approached from outside it (ZCR-9: from above for LONG): close inside the FVG -> no LONG order
    f20 = ("ZC-D", "ZF-FVG-1H", "L")
    i20 = pd_id(*f20)
    wide = zr.merge(zr.zf(0, T0 - 12 * M5, 4310.0, d=1, top=4320.0, bot=4290.0), zr.zc(2, 1, 4300.0))
    r = run([f20], rows_bars([(4310, 4310, 4310, 4310)] * 2, wide))
    ck("F20a 上昇 FVG 4290〜4320 × ZC-D 4298〜4302、終値 4310 (FVG の帯の中) → LONG 指値を置かない (ZCR-9 では FVG へ上から触れていない)",
       r.ord_hist == [{}, {}, {}] and orc_ok(r, rows_bars([(4310, 4310, 4310, 4310)] * 2, wide), [f20])[0], f"{r.ord_hist}")
    abv = zr.merge(zr.zf(0, T0 - 12 * M5, 4310.0, d=1, top=4305.0, bot=4290.0), zr.zc(2, 1, 4300.0))
    b20 = rows_bars([(4310, 4310, 4308, 4309), (4309, 4309, 4303, 4304), (4304, 4310, 4304, 4309)], abv)
    r = run([f20], b20)
    ck("F20b 上昇 FVG 4290〜4305 の上 (終値 4310) から → 共通帯 4298〜4302 の 4302 に買い指値。終値が FVG の中 (4304) で確定した足で取消、FVG の上 (4309) へ戻れば再び置く",
       [x.get(i20) for x in r.ord_hist] == [tk(4302), tk(4302), None, tk(4302)] and orc_ok(r, b20, [f20])[0], f"{r.ord_hist}")
    s20 = ("ZC-D", "ZF-FVG-1H", "S")
    dn = zr.merge(zr.zf(0, T0 - 12 * M5, 4290.0, d=-1, top=4310.0, bot=4295.0), zr.zc(2, 1, 4300.0))
    r = run([s20], rows_bars([(4290, 4290, 4290, 4290), (4297, 4297, 4297, 4297)], dn, start=4290.0))
    ck("F20c SHORT の鏡像: 下降 FVG 4295〜4310 の下 (終値 4290) → 4298 に売り指値、終値が FVG の中 (4297) で取消",
       [x.get(pd_id(*s20)) for x in r.ord_hist] == [tk(4298), tk(4298), None], f"{r.ord_hist}")
    ri = run([("ZC-D", "ZF-iFVG-1H", "L")], rows_bars([(4310, 4310, 4310, 4310)] * 2, wide, feeds={1: zr.zf(0, T0 - 6 * M5, 4280.0)}))
    ck("F20d iFVG (4290〜4320 の上昇 FVG が転換) は条件なし: 終値 4310 が帯の中でも 4302 に買い指値",
       ri.ord_hist[1] == {pd_id("ZC-D", "ZF-iFVG-1H", "L"): tk(4302)}, f"{ri.ord_hist}")
    if record:
        for x in res:
            check(*x)
    return res


# ----------------------------------------------------------------------------------------------------------------
def need_cases():
    bars = zcs_bars(3, 1200)
    sel = [("ZC-D", "ZF-FVG-1H", "L"), ("ZC-D", "ZF-iFVG-1H", "S")]
    r = Runner(sel).run(bars)
    ra = Runner(sel, feeds_all=True).run(bars)
    flags = {k: v for k, v in r.need.items()}
    on = sorted(k for k, v in flags.items() if v)
    gids = sorted(set(z[1] for z in r.zones()))
    check("N 必要: ZC-D × FVG-1H / iFVG-1H だけを選ぶと、計算するのは zcUse3 (ZC-D) と zfUse1 (ZF 1H) だけ (他の request は呼ばない)",
          on == ["zcUse3", "zfUse1"] and r.needed == [7, 15, 22], f"{on} {r.needed}")
    check("N 必要: 登録された Zone は ZC-D (7) と ZF 1H (15) だけ。ZE / ZD / ZA / ZG の状態は 0 (OFF) のまま。MA の帯は作らない",
          gids == [7, 15] and list(r["lbZeStat"]) == [0, 0] and list(r["lbZdStat"]) == [0, 0, 0, 0] and not any(r["zcMaOk"])
          and sum(r["zcNZone"][g] for g in range(26) if g not in (7, 15)) == 0, f"{gids} {list(r['zcNZone'])}")
    check("N 不要な種類の取得値を全部与えても (request を呼んだ場合と同じ値) 結果は同じ (Logic は必要な種類の値だけを読む)",
          ra.ord_hist == r.ord_hist and ra.trades() == r.trades() and ra.zones() == r.zones() and len(r.trades()) > 0, f"{len(r.trades())}")
    r0 = Runner([]).run(bars[:50])
    check("N ペアを 1 つも選ばない (初期状態) → 計算する根拠なし・注文なし", not any(r0.need.values()) and r0.needed == [] and all(x == {} for x in r0.ord_hist))
    # every single pair -> exactly its two evidence IDs
    ok = True
    s = read(PINE)
    code = compile(sel_code(s), "<sel>", "exec")
    base = ap.inputs(s)
    for p, a, b in PAIRS[::7] + PAIRS[-3:]:
        env = dict(base)
        env.update(sel_inputs([(GN[a], GN[b], "S")]))
        env.update(array__new_bool=lambda n=0, v=None: [v] * n, array__concat=lambda x, y: x.extend(y) or x, array__from=lambda *q: list(q),
                   array__get=lambda arr, i: arr[i], _VARS=set(), _VARIPS=set(), __first__=True)
        exec(code, env)
        ok &= [g for g in range(26) if env[f"zsN{g:02d}"]] == [a, b] and env["zsSel"] == [i == 2 * p + 1 for i in range(650)]
    check("N 生成した選択: ペア p の SHORT だけを ON にすると、配列の 2p + 1 だけが true、必要な根拠 ID はその 2 つだけ (47 ペアで確認)", ok)


def causality():
    bars = zcs_bars(5, 1600)
    sel = random_sel(5)
    ov = RANDOM_PRM[5 % len(RANDOM_PRM)]
    full = Runner(sel, ov).run(bars)
    half = Runner(sel, ov).run(bars[:800])
    check("K 前半だけの実行 == 全体実行の前半 (注文・接触中・約定)", full.ord_hist[:800] == half.ord_hist and full.on_hist[:800] == half.on_hist
          and [t for t in full.trades() if t[3] < 799] == [t for t in half.trades() if t[3] < 799] and len(half.trades()) > 3)
    check("K 同じ系列の再実行で結果一致", Runner(sel, ov).run(bars).trades() == full.trades())


# ----------------------------------------------------------------------------------------------------------------
MUTATIONS = [
    ("LONG の指値を下端にする", "int px = p.d == 1 ? p.cT : p.cL", "int px = p.d == 1 ? p.cL : p.cL"),
    ("接触中でも注文を置く", "if live and flat and not p.on and f_zsFbOk(p.d)", "if live and flat and f_zsFbOk(p.d)"),
    ("保有中も注文を置く", "if live and flat and not p.on and f_zsFbOk(p.d)", "if live and not p.on and f_zsFbOk(p.d)"),
    ("約定した足を接触中にしない", "                p.on    := true\n", "                p.on    := p.on\n"),
    ("FVG の接近条件 (終値が FVG の外) を外す", "    g < 15 or g > 18 or (d == 1 ? c > z.tt : c < z.tb)", "    true"),
    ("FVG の向きの条件を外す", "(g < 15 or g > 18 or z.sub == d)", "(g < 15 or g > 18 or true)"),
    ("離脱幅を「超」にする", "if dist >= zcDepT or time_close - p.outT >= zcDepMs", "if dist > zcDepT or time_close - p.outT >= zcDepMs"),
    ("離脱時間を外す", "if dist >= zcDepT or time_close - p.outT >= zcDepMs", "if dist >= zcDepT"),
    ("LONG で上端が最も低い候補を選ぶ", "r := ct > p.cT or (ct == p.cT and cl > p.cL) or (same and lowId)", "r := ct < p.cT or (ct == p.cT and cl > p.cL) or (same and lowId)"),
    ("終値 = 上端でも LONG を置く", "if (p.d == 1 ? ct < c : cl > c) and f_zsBetter(p, fnd, cl, ct, za, zb)", "if (p.d == 1 ? ct <= c : cl > c) and f_zsBetter(p, fnd, cl, ct, za, zb)"),
    ("条件を満たさない注文を取り消さない", "                strategy.cancel(p.id)\n                st.nCancel += 1\n", "                st.nCancel += 1\n"),
    ("OCA を使わない", "oca_name = ZS_OCA, oca_type = strategy.oca.cancel,", "oca_name = ZS_OCA,"),
    ("フラットを常に両方向にする", "(fbBand == 0 and fbFlatBoth)", "(fbBand == 0)"),
    ("フィルターの na を許可にする", "not fbUse or (not na(fbBand) and (fbBand == d or (fbBand == 0 and fbFlatBoth)))", "not fbUse or na(fbBand) or (fbBand == d or (fbBand == 0 and fbFlatBoth))"),
    ("接触の帯を引き継がない (前の帯のまま)", "        if kept\n            p.hb := hb\n            p.ht := ht\n", "        if kept and false\n            p.hb := hb\n            p.ht := ht\n"),
    ("触れた候補の範囲でなく最初の候補だけを接触の帯にする", "            hb2 := i == 0 ? cl : math.min(hb2, cl)\n            ht2 := i == 0 ? ct : math.max(ht2, ct)\n",
     "            hb2 := i == 0 ? cl : hb2\n            ht2 := i == 0 ? ct : ht2\n"),
    ("SL / TP の値幅を 2 倍にする", "profit = zsXT, loss = zsXT", "profit = zsXT * 2, loss = zsXT"),
    ("SHORT で下端が最も高い候補を選ぶ", "r := cl < p.cL or (cl == p.cL and ct < p.cT) or (same and lowId)", "r := cl > p.cL or (cl == p.cL and ct < p.cT) or (same and lowId)"),
    ("索引の打ち切りを早める (幅の最大を使わない)", "if fnd and (p.d == 1 ? zo.tb + io.maxW < p.cT : zo.tb > p.cL)", "if fnd and (p.d == 1 ? zo.tb < p.cT : zo.tb > p.cL)"),
]


def mutations():
    src = read(PINE)
    for name, a, b in MUTATIONS:
        if src.count(a) < 1:
            check(f"X 変異「{name}」: 対象の文字列が本体にある", False, a)
            continue
        m = src.replace(a, b, 1)
        caught = []
        try:
            fs = fixed_suite(m, record=False)
            if not all(x[1] for x in fs):
                caught.append("F:" + next(x[0] for x in fs if not x[1])[:12])
        except Exception as ex:        # noqa: BLE001
            caught.append("F raised " + repr(ex)[:60])
        if not caught:
            for seed in (1, 2, 3):
                try:
                    _, _, _, r, _, orc = random_case(seed, src=m, n5=1200)
                    ok, _ = compare(r, orc)
                    if not ok:
                        caught.append(f"C seed {seed}")
                        break
                except Exception as ex:        # noqa: BLE001
                    caught.append("C raised " + repr(ex)[:60])
                    break
        check(f"X 変異「{name}」を検出", bool(caught), ", ".join(caught))


# ----------------------------------------------------------------------------------------------------------------
def static():
    s = read(PINE)
    zcr, lab = read(ZCR), read(LAB)
    code = "\n".join(ap.strip_comment(x) for x in s.split("\n"))
    check("S strategy() 単体 (indicator なし)・//@version=6・alert なし", s.startswith("//@version=6\n") and len(re.findall(r"^strategy\(", code, re.M)) == 1
          and "indicator(" not in code and not re.search(r"\balert(condition)?\s*\(", code))
    head = code[code.index("strategy("):code.index("import ")]
    want = ["pyramiding                      = 0", "process_orders_on_close         = false", "calc_on_every_tick              = false",
            "calc_on_order_fills             = false", "backtest_fill_limits_assumption = 0", "commission_value                = 0", "slippage                        = 0",
            "dynamic_requests                = true", "default_qty_type                = strategy.fixed", "default_qty_value               = 1",
            "initial_capital                 = 10000", "margin_long                     = 0", "margin_short                    = 0"]
    check("S strategy() の約定設定: pyramiding 0・確定足で 1 回 (calc_on_every_tick / calc_on_order_fills false)・process_orders_on_close false・"
          "指値は触れたら約定 (backtest_fill_limits_assumption 0)・手数料 0・スリッページ 0・1 単位・初期資金 10000・証拠金 0・dynamic_requests true",
          all(w in head for w in want), str([w for w in want if w not in head]))

    def blk(t, a, b):
        i = t.index(a)
        i = t.rindex("\n", 0, i) + 1
        j = t.index(b, i)
        return t[i:t.index("\n", j)]

    def fn(t, sig):
        i = t.index("\n" + sig) + 1
        return t[i:t.index("\n\n", i)]
    copies = [("ZA Accum 検出 (LAB Accum copy + f_acConfirmed)", "// ==== LAB Accum copy (begin)", "    [_u[1], _l[1], _i[1], _a[1]]"),
              ("ZC f_lbPivotConfirmed", "f_lbPivotConfirmed(simple int len) =>", "[_ph[1], _pt[1], _pl[1], _lt[1]]"),
              ("ZD f_pocCore / f_feed", "// ==== FEED POC core (begin)", "    [enabled ? lo : na, enabled ? up : na, tOut]"),
              ("ZF f_fvgConfirmed", "// ==== LAB FVG copy (begin)", "// ==== LAB FVG copy (end)"),
              ("ZG 検知器 (LTB の写し) と f_zgCore", "// ==== ZG LTB copy (begin)", "    out[1]"),
              ("型 LbZone / LbAcc", "type LbZone", "    float lo"),
              ("根拠の名前 ZC_GN", "array<string> ZC_GN = array.from(", '"ZF-iFVG-W")'),
              ("採用の関数 (f_zaUse〜f_zdUse・LAB copy use・f_zgShow) と f_zgParse", "f_zaUse(int k) =>", "// ==== LAB copy zgParse (end) ===="),
              ("登録・失効の関数 (LAB copy funcs: f_lbNew / f_zgKill / f_zeClear / f_zeSet / f_zeSame / f_lbAccFix)", "// ==== LAB copy funcs (begin)", "// ==== LAB copy funcs (end) ===="),
              ("登録ブロック全体 (ZA / ZC / ZD / ZE / ZF / ZG。字下げも同じ)", "        // ==== LAB register (begin)", "        // ==== LAB register (end) ====")]
    for name, a, b in copies:
        x, y = blk(s, a, b), blk(zcr, a, b)
        check("S 写し (ZCR-9 と byte 一致): " + name, x == y and len(y) > 100, f"{len(x)} {len(y)}")
    check("S 写し (ZCR-9 と byte 一致): f_zcTicks (幅 $x のティック = max(1, ceil(x / mintick − 1e-9)))",
          blk(s, "f_zcTicks(float usd) =>", "1e-9))") == blk(zcr, "f_zcTicks(float usd) =>", "1e-9))"))
    fns = ["f_inc(array<int> a, int ix, int v) =>", "f_dsDel(LbZone z, bool b) =>", "f_dsRename(LbZone z) =>",
           "f_dsAdd(LbZone z) =>", "f_lbRemove(LbZone z) =>", "f_swAdd(int k, int sub, float pv, int pt) =>", "f_zcMaSet(int k, bool use, float v) =>", "f_zcGid(LbZone z) =>"]
    check("S 写し (ZCR-9 と byte 一致): f_inc / f_ds* / f_lbRemove / f_swAdd / f_zcMaSet / f_zcGid",
          [fn(s, x) for x in fns] == [fn(zcr, x) for x in fns], str([x for x in fns if fn(s, x) != fn(zcr, x)]))
    la, lz = fn(s, "f_lbAdd(LbZone z) =>").split("\n"), fn(zcr, "f_lbAdd(LbZone z) =>").split("\n")
    check("S f_lbAdd: 根拠 ID・ZE の水準・帯のティック丸め (先頭 6 行) は ZCR-9 と同じ。違いは索引 (根拠 ID ごと) と接触中の引き継ぎが無いこと",
          la[:6] == lz[:6] and "zsIx" in "\n".join(la) and "zcInhB" not in s and "f_zcSetOn" not in s)
    reg = blk(s, "        // ==== LAB register (begin)", "        // ==== LAB register (end) ====")
    reg_lab = blk(lab, "    // ZA: 新しい ID", "    // ZB: EMA ± 共通幅").rsplit("\n", 1)[0]
    ded = "\n".join(ln[4:] if ln.startswith("    ") else ln for ln in reg.split("\n")[1:-1])
    check("S 登録ブロックは ZoneComboLabXAU (B1) とも同一 (字下げ 4 桁だけ違う)", ded == reg_lab, f"{len(ded)} {len(reg_lab)}")
    for name, a, b in (("type DfBand / f_dfBandReq (ライブラリの別名 lt → ltb だけ違う)", "type DfBand", "    DfBand.new(b0, tc0, bp0, tcp0)"),
                       ("f_dfPick (time_close >= 上位足の time_close ならその足の帯、それ以外は 1 本前)", "f_dfPick(DfBand r) =>", "            v := time_close >= r.tc ? r.b : r.bp")):
        check("S 写し (ZoneComboLabXAU と byte 一致): " + name, blk(s, a, b) == blk(lab, a, b).replace("= lt.htfBandNow()", "= ltb.htfBandNow()"))
    check("S import は Lab と同じライブラリ (sekine3310/LabTimingXAU/2)、別名は ltb (写しのローカル変数 lt と同名にしない)・帯は ltb.htfBandNow()",
          "\nimport sekine3310/LabTimingXAU/2 as ltb " in s and "\nimport sekine3310/LabTimingXAU/2 as lt " in lab and "ltb.htfBandNow()" in code
          and not re.search(r"\blt\.", code) and "int   lt = " in code)
    # generated section
    gen = zb.generate()
    sec = s[s.index(zb.BEGIN):s.index(zb.END) + len(zb.END)]
    ins = re.findall(r'^p([LS])(\d{3}) = input\.bool\((true|false), "([^"]*)", group = G_P(\d\d), inline = "q(\d{3})"\)$', sec, re.M)
    zcr_gn = re.search(r'array<string> ZC_GN = array\.from\((.*?)\)\n', zcr, re.S).group(1)
    check("S 生成区間 == tests/zcs_build.py の生成結果 (--check も一致)。名前は ZCR-9 の ZC_GN と同じ 26 個・同じ順",
          sec == gen and subprocess.run([sys.executable, os.path.join(ROOT, "tests", "zcs_build.py"), "--check"], capture_output=True).returncode == 0
          and re.findall(r'"([^"]+)"', zcr_gn) == GN)
    check("S 生成区間: input.bool 650 個 (325 ペア × LONG / SHORT)・初期値は全 false・1 ペア = 同じ inline (設定の 1 行)・グループは最初の根拠ごと 25 個・"
          "LONG の表示名 = 「根拠 A × 根拠 B  LONG」",
          len(ins) == 650 and all(x[2] == "false" for x in ins) and all(x[1] == x[5] for x in ins)
          and all(ins[2 * p][3] == f"{GN[a]} × {GN[b]}  LONG" and ins[2 * p + 1][3] == "SHORT" and int(ins[2 * p][4]) == a + 1 for p, a, b in PAIRS)
          and len(set(x[4] for x in ins)) == 25 and len(re.findall(r"input\.bool\(", sec)) == 650)
    sel_stmts = re.findall(r"^    array\.concat\(s, array\.from\(", sec, re.M)
    check("S 生成区間: 配列化は最初の根拠ごとに 1 文 (25 文)、根拠 ID ごとの必要は 26 文 (各 50 個の入力の OR)",
          len(sel_stmts) == 25 and len(re.findall(r"^bool zsN\d\d = ", sec, re.M)) == 26)
    # requests
    reqs = re.findall(r"^(\s*)(?:\[([\w, ]+)\] = |(\w+) := )request\.(\w+)\((.*?)\)$", code, re.M)
    n_req = len(re.findall(r"request\.\w+\(", code))
    flags = []
    lines = code.split("\n")
    for i, ln in enumerate(lines):
        if "request.security(" in ln:
            j = i - 1
            while not lines[j].startswith("if "):
                j -= 1
            flags.append(lines[j][3:].strip())
    tup = [len(m.split(",")) for m in re.findall(r"^\s+\[([\w, ]+)\] = request\.security", code, re.M)]
    single = len(re.findall(r"^\s+\w+ := request\.security", code, re.M))
    check("S request.security 20 件 (上限 40。lower_tf なし)、どれも if <必要> の中 (ZA 3 / ZB-1m 1 / ZC 4 / ZD 4 / ZF 4 / ZG 3 / フィルター 1)。"
          "タプル要素 64 + 単独の戻り値 5 = 69 (上限 127)",
          n_req == 20 and flags == ["zaUse1", "zaUse2", "zaUse3", "zbUse1", "zcUse1", "zcUse2", "zcUse3", "zcUse4", "zdUse1", "zdUse2", "zdUse3", "zdUse4",
                                    "zfUse1", "zfUse2", "zfUse3", "zfUse4", "zgUse1", "zgUse4", "zgUseD", "fbUse"]
          and sum(tup) == 64 and single == 5 and "security_lower_tf" not in code, f"{n_req} {flags} {sum(tup)} {single}")
    zexp = re.findall(r"request\.security\((syminfo\.tickerid, \"\w+\",\s+(?:f_acConfirmed|f_lbPivotConfirmed|f_feed|f_fvgConfirmed|f_zgCore|ta\.ema)\(.*?\), lookahead = barmerge\.\w+)\)", re.sub(r"\n\s+", " ", code))
    zcr_code = "\n".join(ap.strip_comment(x) for x in zcr.split("\n"))
    zexp_r = re.findall(r"request\.security\((syminfo\.tickerid, \"\w+\",\s+(?:f_acConfirmed|f_lbPivotConfirmed|f_feed|f_fvgConfirmed|f_zgCore|ta\.ema)\(.*?\), lookahead = barmerge\.\w+)\)", re.sub(r"\n\s+", " ", zcr_code))
    norm = lambda xs: [re.sub(r"\s+", " ", x) for x in xs]        # noqa: E731
    check("S Zone の request 19 件は ZCR-9 と同じ時間足・同じ式・同じ lookahead (1 分 EMA だけ lookahead_off)", norm(zexp) == norm(zexp_r) and len(zexp) == 19,
          f"{len(zexp)} {len(zexp_r)}")
    check("S フィルター: request.security(…, fbTfS, f_dfBandReq(), lookahead_on) を fbUse のときだけ。参照足 日足 = D / 4H = 240 / 1H = 60",
          'fbR := request.security(syminfo.tickerid, fbTfS, f_dfBandReq(), lookahead = barmerge.lookahead_on)' in code
          and 'string fbTfS = fbTf == "日足" ? "D" : fbTf == "1H" ? "60" : "240"' in code)
    lg = "\n".join(ap.strip_comment(x) for x in between(s, LB, LE).split("\n"))
    check("S Logic 区間に request / ta. / 履歴参照なし。strategy.entry は指値 (limit) だけ・strategy.close / 成行なし。strategy.exit は profit / loss (ティック) だけ",
          not re.search(r"\brequest\.|\bta\.", lg) and not re.search(r"\w\[", lg) and not re.search(r"strategy\.close\(|strategy\.close_all", code) and lg.count("strategy.entry(") == 1
          and "limit = math.round_to_mintick(px * syminfo.mintick)" in lg and lg.count("strategy.exit(") == 1 and "profit = zsXT, loss = zsXT" in lg
          and "stop =" not in lg)
    plots = re.findall(r"^plot\(", code, re.M)
    check("S plot 3 本 (Data Window のみ)・描画は状態の表 1 つだけ (box / line / label なし)",
          len(plots) == 3 and not re.search(r"\b(box|line|label)\.new\(", code) and code.count("table.new(") == 1)
    mi, zi = ap.inputs(s), ap.inputs(zcr)
    shared = [k for k in mi if k in zi]
    uses = [k for k in zi if re.match(r"(zaUse|zbUse|zcUse|zdUse|zfUse|zgUse)\w$|zeUse", k)]
    check("S 入力の初期値は ZCR-9 と同じ (共通幅・ZA 箱数・Accum・EMA 本数・ZB-1m 助走・Swing・ZC 保持・POC 本数・VP ビン・FVG 最小幅・ZG 一式・離脱幅 5・離脱時間 30・助走 6000)。"
          "種類・時間足ごとの ON / OFF の入力は無い (選んだペアで決まる)。値幅 X の既定 15・フィルター既定 OFF・参照足 4H・フラット = 見送り",
          len(shared) >= 70 and all(mi[k] == zi[k] for k in shared) and not any(k in mi for k in uses) and len(uses) == 23
          and mi["zsX"] == 15 and mi["fbUse"] is False and mi["fbTf"] == "4H" and mi["fbFlat"] == "見送り" and mi["zcDepW"] == 5.0 and mi["zcDepMin"] == 30
          and mi["zcWarm"] == 6000 and 'zcStart = input.time(timestamp("01 Jan 2020 00:00 +0000")' in code
          and 'zsX = input.int(15, "SL / TP の値幅 X ($)", options = [5, 10, 15]' in code, f"{len(shared)} {[k for k in shared if mi[k] != zi[k]]} {uses}")
    src_titles = re.findall(r'^ze\w+ = input\.source\(close, "([^"]+)"', code, re.M)
    zcr_titles = re.findall(r'^ze\w+ = input\.source\(close, "([^"]+)"', zcr_code, re.M)
    check("S ZE は ZCR-9 と同じ 13 本の input.source (同じ名前・同じ順。LongFibWave の接続出力)", src_titles == zcr_titles and len(src_titles) == 13)
    check("S 5 分の標準チャートだけ (ZCR と同じ条件 hlRun)", "bool hlRun = timeframe.isminutes and timeframe.multiplier == 5 and chart.is_standard" in code
          and "if hlRun and barstate.isconfirmed" in code)
    ind = [ln for ln in s.split("\n") if ln.strip() and not ln.lstrip().startswith("//")]
    badi = [ln for ln in ind if (len(ln) - len(ln.lstrip(" "))) % 4 not in (0, 1)]
    check("S 継続行以外のインデントは 4 の倍数、タブなし", not badi and "\t" not in s, str(badi[:3]))
    check("S 冒頭と仕様書に未検証 (PINE_NOT_VERIFIED) の明記", "PINE_NOT_VERIFIED" in s.split("strategy(")[0] and os.path.exists(DOC)
          and "PINE_NOT_VERIFIED" in read(DOC))
    mine = {"ZoneConfluenceStrategyXAU.pine", "tests/zcs_build.py", "tests/zcs_sim.py", "ZONE_CONFLUENCE_STRATEGY_XAU_ja.md"}
    try:
        stt = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
        lines_ = [x for x in stt.split("\n") if x.strip() and "__pycache__" not in x]
        other = [x for x in lines_ if not (x.startswith("?? ") and x[3:] in mine)]
        check("S git status: 新規 4 ファイルだけ (既存ファイルは未変更)", not other and len(lines_) == 4, str(lines_))
    except Exception as ex:        # noqa: BLE001
        check("S git status: 新規 4 ファイルだけ (既存ファイルは未変更)", False, repr(ex))


def main():
    seeds = [int(x) for x in sys.argv[1:]] or [1, 2, 3, 4, 5, 6, 7, 8]
    static()
    fixed_suite()
    need_cases()
    random_vs_oracle(seeds)
    causality()
    mutations()
    bad = 0
    for name, ok, det in RESULTS:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else "  " + det))
        bad += 0 if ok else 1
    print(f"{len(RESULTS) - bad}/{len(RESULTS)} passed")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
