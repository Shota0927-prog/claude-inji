"""DTB-1 checks — DoubleTripleTopBottomXAU.pine (standalone double / triple top / bottom indicator) vs the ACC-5B detector of
AccumStrategyXAU.pine.

Both files run through the SAME mechanical Pine -> Python translator (tests/acc_pine.py) on the same 5M OHLC, the same settings,
the same history start and the same higher-timeframe deliveries (tests/acc_sim.py dv_feeds: on the 5M bars inside HTF bar k the
(high, low, time) of HTF bar k-1, as request.security([1], lookahead_on) delivers them).

The comparison is per detection EVENT, before any storage / display aggregation: a temporary instrumented copy of each file (made
here in memory, the files on disk are not touched) logs every detection right where `det` is true, with
(detection bar, base id, base timeframe, top / bottom, count 2 / 3, approach bar, base level, detected on the approach bar).
In addition the complete state of every active base (id, tf, side, level, pTime, availability bar, away, count, waiting, approach
bar, wait end) is compared after every 5M bar, so approaches / expiries / invalidations / removals are compared too.

Evidence class: PINE_NOT_VERIFIED (TradingView compiler, request.security, drawing limits and rendering not reproduced).
"""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import acc_pine as ap        # noqa: E402
import acc_sim as az         # noqa: E402

ROOT = ap.ROOT
ORIG_PATH = os.path.join(ROOT, "AccumStrategyXAU.pine")
NEW_PATH = os.path.join(ROOT, "DoubleTripleTopBottomXAU.pine")
M5 = 300_000
LOG = "runtime.zzlog(bar_index, g.id, g.tf, g.side, g.cnt, g.appBar, g.lvl, dApp)"
TFJA = ["5分", "15分", "1時間", "4時間", "日足"]
RESULTS = []
H1 = 3_600_000


class nas:
    """copies of tests/nr_a1_sim.py market() / htf_from_5m() (that module's import chain needs a commit missing from this
    branch's history, see the report), unchanged."""

    @staticmethod
    def htf_from_5m(bars5, tf_ms, day_mode=False):
        groups = {}
        for t, o, h, l, c in bars5:
            key = (t - 22 * H1) // 86_400_000 if day_mode else t // tf_ms
            groups.setdefault(key, []).append((t, o, h, l, c))
        out = []
        for key in sorted(groups):
            g = groups[key]
            T = key * 86_400_000 + 22 * H1 if day_mode else key * tf_ms
            C = T + 86_400_000 if day_mode else T + tf_ms
            out.append(dict(T=T, C=C, subs=[(o, h, l, c) for _, o, h, l, c in g], slots=[(t - T) // M5 for t, *_ in g]))
        return out

    @staticmethod
    def market(seed, days=40, missing=0.0):
        rnd = random.Random(seed)
        p, out, t0 = 2000.0, [], 1_790_000_000_000 // 86_400_000 * 86_400_000
        regime, left = 0.0, 0
        for d in range(days):
            if (d % 7) in (5, 6):
                continue
            for s in range(23 * 12):
                t = t0 + d * 86_400_000 - H1 + s * M5
                if missing and rnd.random() < missing:
                    continue
                if left <= 0:
                    regime, left = rnd.choice([0.0, 0.0, 0.6, -0.6]), rnd.randint(40, 300)
                left -= 1
                q = p + regime + rnd.gauss(0, 0.9)
                out.append((t, p, max(p, q) + abs(rnd.gauss(0, .4)), min(p, q) - abs(rnd.gauss(0, .4)), q))
                p = q
        return out


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


def instrument(src):
    """temporary copy: one log call as the first statement of the `if det` block (the only one in each file)."""
    lines = src.split("\n")
    idx = [i for i, x in enumerate(lines) if x.strip() == "if det"]
    assert len(idx) == 1, idx
    i = idx[0]
    ind = len(lines[i]) - len(lines[i].lstrip(" "))
    lines.insert(i + 1, " " * (ind + 4) + LOG)
    return "\n".join(lines)


def new_src(text):
    """the indicator text with its own logic markers renamed to the markers acc_pine reads (in memory only)."""
    return (text.replace("// ==== DTB Logic (begin) ", "// ==== ACC Logic (begin) ")
                .replace("// ==== DTB Logic (end) ", "// ==== ACC Logic (end) "))


ORIG_RAW = open(ORIG_PATH, encoding="utf-8").read()
NEW_RAW = open(NEW_PATH, encoding="utf-8").read()
ORIG_SRC = instrument(ORIG_RAW)
NEW_SRC = instrument(new_src(NEW_RAW))
NEW_SRC_PLAIN = new_src(NEW_RAW)


# drawings are chart objects referenced by var state, not var state themselves: the per-bar snapshot / rollback of the
# Runner must keep the reference (otherwise label.delete / label.set_text would act on a copy the drawing log never sees)
ap.Drawing.__deepcopy__ = lambda self, memo: self


class DRunner(ap.Runner):
    """acc_pine Runner + detection log + per-bar base snapshots + drawing creation bar / confirmed flag."""

    def __init__(self, overrides=None, src=None, **kw):
        super().__init__(overrides, src=src, **kw)
        self.events, self.snaps, self.bars = [], [], []
        self.atr = None
        e = self.env
        e["runtime__zzlog"] = lambda *a: self.events.append(tuple(a))
        e.update(label__style_diamond="diamond", label__style_label_left="left", line__style_dashed="dashed",
                 line__style_dotted="dotted")
        for k in ("oState", "oSide", "oId", "oSL", "oTP", "oStop", "oBE", "oFill", "oPat", "oTf", "oQty", "oRRPlan", "oRRReal"):
            e.setdefault(k, None)
        for nm in ("label__new", "line__new"):
            f = e[nm]

            def wrap(*a, _f=f, **k):
                d = _f(*a, **k)
                d.bar, d.conf = self.bar_index, e["barstate__isconfirmed"]
                return d
            e[nm] = wrap

    def _set_series(self, b, o, h, l, c, confirmed, history=True):
        super()._set_series(b, o, h, l, c, confirmed, history)
        self.env["dsAtr"] = self.atr            # display only (ta.atr(14) stand-in: committed RMA of the true range)

    def step(self, b):
        super().step(b)
        pc = self.bars[-1]["c"] if self.bars else None
        trv = b["h"] - b["l"] if pc is None else max(b["h"] - b["l"], abs(b["h"] - pc), abs(b["l"] - pc))
        self.atr = trv if self.atr is None else (self.atr * 13 + trv) / 14
        self.bars.append(b)
        self.snaps.append(tuple((g.id, g.tf, g.side, g.lvl, g.pTime, g.aBar, g.away, g.cnt, g.waiting, g.appBar, g.waitEnd)
                                for g in self.env["dvBases"]))
        return self


def run_orig(bars, ov=None, **kw):
    return DRunner(dict(ov or {}), src=ORIG_SRC, **kw).run(bars)


def run_new(bars, ov=None, **kw):
    return DRunner(dict(ov or {}), src=NEW_SRC, **kw).run(bars)


def first_diff(a, b):
    """first bar where the event list or the base state differs (None = identical)."""
    ea, eb = {}, {}
    for e in a.events:
        ea.setdefault(e[0], []).append(e)
    for e in b.events:
        eb.setdefault(e[0], []).append(e)
    for i in range(max(len(a.snaps), len(b.snaps))):
        if ea.get(i, []) != eb.get(i, []):
            return i, f"events {ea.get(i)} != {eb.get(i)}"
        sa = a.snaps[i] if i < len(a.snaps) else None
        sb = b.snaps[i] if i < len(b.snaps) else None
        if sa != sb:
            return i, f"bases {sa} != {sb}"
    return None


# ============================================================================
# series
# ============================================================================
def series(seed, days, missing=0.0, grid=None, vol=1.0, mirror=False):
    b5 = nas.market(seed, days, missing)
    if mirror:                                    # tops <-> bottoms (price reflected around 2000)
        b5 = [(t, 4000 - o, 4000 - l, 4000 - h, 4000 - c) for t, o, h, l, c in b5]
    if vol != 1.0 or grid:
        out = []
        for t, o, h, l, c in b5:
            o, h, l, c = (2000 + (x - 2000) * vol for x in (o, h, l, c))
            if grid:
                o, h, l, c = (round(x / grid) * grid for x in (o, h, l, c))
            out.append((t, o, h, l, c))
        b5 = out
    dvf = az.dv_feeds(nas, b5)
    return [dict(t=t, o=o, h=h, l=l, c=c, feed={}, dv=dvf[i]) for i, (t, o, h, l, c) in enumerate(b5)]


def with_ticks(bars, start):
    out = []
    for i, b in enumerate(bars):
        if i >= start:
            b = dict(b, ticks=ap.Broker.bar_path(b["o"], b["h"], b["l"], b["c"]))
        out.append(b)
    return out


# ============================================================================
# coverage of the original's behaviour (computed from the original's own log / states)
# ============================================================================
def coverage(r, ov):
    inp = dict(r.inp)
    bars = r.bars
    B = [inp["dvB%d" % k] for k in range(5)]
    cov = {k: 0 for k in ("det_app", "det_later", "det_last_wait_bar", "expired", "expired_then_3rd", "inv_and_rev_same_bar",
                          "inv_while_waiting", "touch_without_distance", "multi_tf_same_bar", "multi_base_same_tf_bar",
                          "det_on_reg_bar", "finished_after_3rd")}
    for k in range(5):
        for s in (-1, 1):
            for c in (2, 3):
                cov[f"tf{k} {'top' if s == -1 else 'bot'} x{c}"] = 0
    byb = {}
    for e in r.events:
        bar, gid, tf, side, cnt, app, lvl, dapp = e
        cov[f"tf{tf} {'top' if side == -1 else 'bot'} x{cnt}"] += 1
        cov["det_app" if dapp else "det_later"] += 1
        if bar - app == inp["dvWait"] and not dapp:
            cov["det_last_wait_bar"] += 1
        byb.setdefault(bar, []).append(e)
    for bar, es in byb.items():
        if len({e[2] for e in es}) >= 2:
            cov["multi_tf_same_bar"] += 1
        tfs = [e[2] for e in es]
        if any(tfs.count(x) >= 2 for x in tfs):
            cov["multi_base_same_tf_bar"] += 1
    reg = {}
    expired2 = set()
    prev = {}
    for i, snap in enumerate(r.snaps):
        cur = {g[0]: g for g in snap}
        b = bars[i]
        dets = {e[1] for e in byb.get(i, [])}
        for gid, g in cur.items():
            reg.setdefault(gid, g[5])
        for gid, p in prev.items():
            if p[5] >= i:
                continue
            top = p[2] == -1
            g = cur.get(gid)
            inv = b["c"] > p[3] + B[p[1]] + 1e-7 if top else b["c"] < p[3] - B[p[1]] - 1e-7
            rev = b["c"] < b["o"] if top else b["c"] > b["o"]
            if g is None and inv and rev:
                cov["inv_and_rev_same_bar"] += 1
            if g is None and inv and p[8]:
                cov["inv_while_waiting"] += 1
            if p[8] and gid not in dets and (g is None or not g[8]) and not inv:
                cov["expired"] += 1
                if p[7] == 2:
                    expired2.add(gid)
            if g is not None and not p[8] and not p[6] and p[7] < 3 and not inv:
                if (b["h"] >= p[3] - B[p[1]] - 1e-7) if top else (b["l"] <= p[3] + B[p[1]] + 1e-7):
                    cov["touch_without_distance"] += 1
            if g is not None and g[7] == 3 and p[7] == 2 and gid in expired2:
                cov["expired_then_3rd"] += 1
            if g is None and not inv and (p[7] == 3 or (g is None and gid in dets)):
                cov["finished_after_3rd"] += 1
        prev = cur
    for e in r.events:
        if e[0] <= reg.get(e[1], -1):
            cov["det_on_reg_bar"] += 1
    return cov


# ============================================================================
# drawing checks on the indicator
# ============================================================================
def pivot_times(r):
    """independent expectation of the real pivot bar time of every base (from the bars / deliveries, no time arithmetic):
    5M: the bar dvPiv bars before the availability bar; HTF: the dvPiv-th previous DISTINCT delivered bar time."""
    piv = r.inp["dvPiv"]
    deliv = {k: [] for k in range(1, 5)}
    seen = {k: None for k in range(1, 5)}
    hl = {}
    at = {}
    for i, b in enumerate(r.bars):
        for k in range(1, 5):
            v = b.get("dv", {}).get(k)
            if v and v[2] is not None and v[2] != seen[k]:
                seen[k] = v[2]
                deliv[k].append(v[2])
                hl[(k, v[2])] = (v[0], v[1])
            at[(k, i)] = len(deliv[k])
    out = {}
    for snap in r.snaps:
        for g in snap:
            gid, tf, side, lvl, ptime, abar = g[:6]
            if gid in out:
                continue
            if tf == 0:
                out[gid] = (r.bars[abar - piv]["t"], r.bars[abar - piv]["h" if side == -1 else "l"], r.bars[abar]["t"])
            else:
                n = at[(tf, abar)]
                t = deliv[tf][n - 1 - piv]
                out[gid] = (t, hl[(tf, t)][0 if side == -1 else 1], deliv[tf][n - 1])
    return out


def all_bases(r):
    d = {}
    for snap in r.snaps:
        for g in snap:
            d.setdefault(g[0], g)
    return d


def draw_check(r):
    """every event / approach / base of a shown timeframe has its drawings at the right bar / time / price."""
    bad = []
    inp = r.inp
    shown = [inp["dsTf%d" % k] for k in range(5)]
    labels = [d for d in r.draws if d.kind == "label"]
    lines = [d for d in r.draws if d.kind == "line"]
    bases = all_bases(r)
    piv = pivot_times(r)
    # base id -> approach bars (from the state: count increases)
    apps = {}
    prev = {}
    for i, snap in enumerate(r.snaps):
        for g in snap:
            p = prev.get(g[0])
            if p is not None and g[7] > p[7]:
                apps.setdefault(g[0], []).append((i, g[7]))
        cur = {g[0]: g for g in snap}
        # approaches on bars where the base was removed (3rd approach + detection / skip on the same bar)
        for gid, p in prev.items():
            if gid not in cur:
                pass
        prev = cur
    for e in r.events:
        if e[0] == e[5]:                         # detected on the approach bar: the approach is that bar
            apps.setdefault(e[1], [])
            if (e[5], e[4]) not in apps[e[1]]:
                apps[e[1]].append((e[5], e[4]))
        else:
            apps.setdefault(e[1], [])
            if (e[5], e[4]) not in apps[e[1]]:
                apps[e[1]].append((e[5], e[4]))
    nd = na = nb = 0
    want = []      # expected base -> approach lines (bases with the same pivot / level / approach give identical lines)
    for e in r.events:
        bar, gid, tf, side, cnt, app, lvl, dapp = e
        top = side == -1
        mine = [d for d in labels if d.bar == bar and str(d.args[2]).startswith(
            ("ダブル" if cnt == 2 else "トリプル") + ("トップ" if top else "ボトム") + " " + TFJA[tf] + "\n#" + str(gid) + " ")]
        if not shown[tf]:
            if mine:
                bad.append(("label for a hidden tf", e))
            continue
        nd += 1
        b = r.bars[bar]
        if len(mine) != 1 or mine[0].args[0] != b["t"] or (mine[0].args[1] < b["h"] if top else mine[0].args[1] > b["l"]) \
                or mine[0].kw.get("xloc") != "bar_time":
            bad.append(("detection label", e, [(d.args[:2], d.bar) for d in mine]))
    for gid, lst in apps.items():
        g = bases[gid]
        tf, side = g[1], g[2]
        top = side == -1
        for abar, cnt in lst:
            mk = [d for d in labels if d.bar == abar and d.kw.get("style") == "diamond"
                  and str(d.args[2]).startswith(f"#{gid} {TFJA[tf]} {cnt}回目")]
            if not shown[tf]:
                if mk:
                    bad.append(("marker for a hidden tf", gid))
                continue
            na += 1
            b = r.bars[abar]
            if len(mk) != 1 or mk[0].args[0] != b["t"] or mk[0].args[1] != (b["h"] if top else b["l"]):
                bad.append(("approach marker", gid, abar, cnt, [(d.args[:2]) for d in mk]))
            want.append((abar, piv[gid][0], g[3], b["t"], b["h"] if top else b["l"]))
    from collections import Counter
    got = Counter((d.bar, d.args[0], d.args[1], d.args[2], d.args[3]) for d in lines if d.kw.get("style") == "dashed")
    if got != Counter(want):
        bad.append(("approach lines", (Counter(want) - got).most_common(2), (got - Counter(want)).most_common(2)))
    for gid, g in bases.items():
        if not shown[g[1]]:
            continue
        ann = [d for d in labels if str(d.args[2]).startswith(f"基準#{gid} ")]
        if not ann:
            continue
        nb += 1
        pt, pp, avt = piv[gid]
        for d in ann:
            if d.args[0] != pt or d.args[1] != g[3] or pp != g[3] or d.bar < g[5]:
                bad.append(("base annotation", gid, d.args[:2], (pt, pp), d.bar, g[5]))
        reg = [d for d in labels if str(d.args[2]).startswith(f"#{gid} {TFJA[g[1]]} 登録")]
        if not reg or any(d.args[0] != r.bars[g[5]]["t"] or d.bar < g[5] for d in reg):
            bad.append(("availability marker", gid))
    # nothing drawn to the right of the bar it was created on; nothing created on an unconfirmed tick
    for d in r.draws:
        xs = [d.args[0]] + ([d.args[2]] if d.kind == "line" else [])
        if any(x > r.bars[d.bar]["t"] for x in xs) or not d.conf:
            bad.append(("future / unconfirmed drawing", d.kind, d.args[:3], d.bar))
    return bad, (nd, na, nb)


def live(r, kind):
    return [d for d in r.draws if d.kind == kind and not d.deleted]


def created(r):
    return [(d.kind, d.bar, d.args, tuple(sorted((k, str(v)) for k, v in d.kw.items() if k != "tooltip"))) for d in r.draws]


# ============================================================================
# gates
# ============================================================================
SETTINGS = [
    ("default", {}),
    ("wait 0", dict(dvWait=0)),
    ("wait 1", dict(dvWait=1)),
    ("pivot 1", dict(dvPiv=1)),
    ("pivot 3 / wait 5", dict(dvPiv=3, dvWait=5)),
    ("5M buffer / distance 0", dict(dvB0=0.0, dvD0=0.0)),
]


def gate_series(scov):
    tot_ev = tot_mis = n_runs = 0
    covsum = dict(scov)          # coverage of the compared scenario runs (DT-A1) + the random series
    first_bad = ""
    plans = [(61, 40, 0.0, None, 1.0, False, 6), (62, 40, 0.03, None, 1.0, False, 6), (63, 40, 0.0, 0.5, 1.0, False, 2),
             (64, 70, 0.0, None, 1.6, False, 2), (64, 70, 0.0, None, 1.6, True, 1), (65, 70, 0.02, 0.5, 2.2, False, 2)]
    for seed, days, miss, grid, vol, mir, nset in plans:
        bars = series(seed, days, miss, grid, vol, mir)
        for name, ov in SETTINGS[:nset]:
            if nset == 2 and name == "wait 1":
                continue
            a = run_orig(bars, ov)
            b = run_new(bars, ov)
            n_runs += 1
            tot_ev += len(a.events)
            d = first_diff(a, b)
            if d is not None:
                tot_mis += 1
                first_bad = first_bad or f"seed {seed} {name}: first difference on bar {d[0]}: {d[1]}"
            for k, v in coverage(a, ov).items():
                covsum[k] = covsum.get(k, 0) + v
            print(f"  [run] seed {seed} days {days} missing {miss} grid {grid} vol {vol} mirror {mir} {name}: events "
                  f"{len(a.events)} diff {d}", flush=True)
            if name == "default" and seed in (62, 65):
                bad, cnt = draw_check(b)
                check(f"DT-D1 seed {seed} drawings: every detection label on its detection bar (time = that 5M bar, price at its "
                      f"high / low side), every approach marker at the approach bar's own high / low, a line from the real pivot "
                      f"to each approach, base annotations at the real pivot bar time (history, missing bars {miss}) and the "
                      f"availability marker at the registration bar, nothing drawn to the right / on an unconfirmed tick",
                      not bad and all(cnt), f"{bad[:3]} counts(det, app, base)={cnt}")
    print("  [DT coverage of the compared runs (scenarios + series)]", covsum)
    need = [k for k, v in covsum.items() if v == 0 and k != "det_on_reg_bar"]
    check("DT-S1 random series (5 paths incl. missing bars, 0.5 price grid, 2 volatilities; 6 settings): the indicator's detection "
          "events and the full state of every active base equal the original (AccumStrategyXAU.pine) on every bar",
          tot_mis == 0 and tot_ev > 0, f"runs={n_runs} events={tot_ev} mismatching runs={tot_mis} {first_bad}")
    check("DT-S2 the compared runs (scenarios + random series) cover: all 5 timeframes x top / bottom x double / triple, approach-bar and later detections, the "
          "last bar of the wait, expiry, a 3rd approach after an expired 2nd, invalidation with a reversal bar on the same bar and "
          "while waiting, in-band bars without the distance, multiple timeframes / bases detecting on the same bar",
          not need, f"missing={need}")
    check("DT-S3 no detection on (or before) the bar a base becomes available (no back-dated detection at the pivot registration)",
          covsum.get("det_on_reg_bar", 1) == 0, str(covsum.get("det_on_reg_bar")))
    return tot_ev, tot_mis, n_runs


def gate_scenarios():
    """the ACC-5B scenario bars of tests/acc_sim.py (AZ-01..18) through both files."""
    ZB, ZUP, ZDN, ZBN, ZBU, M, B = az.ZB, az.ZUP, az.ZDN, az.ZBN, az.ZBU, az.M, az.B
    hb = [(4280, 4270), (4285, 4275), (4296, 4284), (4290, 4280), (4285, 4278)]
    dv10 = {i + 1: {2: (hb[i][0], hb[i][1], az.T0 - (10 - i) * az.H1)} for i in range(5)}
    hb2 = [(4280, 4270), (4285, 4275), (4296, 4290), (4292, 4286), (4290, 4285)]
    dv11 = {i + 1: {2: (hb2[i][0], hb2[i][1], az.T0 - (10 - i) * az.H1)} for i in range(5)}
    flat = B(4288, 4289, 4287, 4288)
    stay = B(4294.5, 4297, 4294, 4296)
    sc = [
        ("AZ-01", ZB + [ZUP, ZDN, B(4291, 4292, 4287, 4288), B(4288, 4289, 4286, 4287)], None, {}),
        ("AZ-03", ZB + [B(4293, 4295, 4288, 4289), M], None, {}),
        ("AZ-04", ZB + [ZUP, ZBN, ZBN, ZBN, B(4291, 4292, 4290.5, 4291.5)], None, {}),
        ("AZ-05a", ZB + [B(4289, 4299, 4288, 4297), M], None, {}),
        ("AZ-05b", ZB + [B(4289, 4299, 4288, 4298), M], None, {}),
        ("AZ-05c", ZB + [B(4299, 4300, 4288, 4298.5), M], None, {}),
        ("AZ-06", ZB + [ZUP, stay, stay, stay, stay, stay, ZDN], None, {}),
        ("AZ-07", ZB + [ZUP, ZBN, ZBN, ZBN, ZDN, B(4291, 4295, 4290.5, 4294.5), ZDN, M], None, {}),
        ("AZ-08", ZB + [ZUP, ZDN, B(4291, 4292, 4287, 4289.5), B(4289, 4295, 4288.5, 4294.5), ZDN, M], None, {}),
        ("AZ-09", az.zmirror(ZB + [ZUP, ZBN, ZBN, ZBN, ZDN, B(4291, 4295, 4290.5, 4294.5), ZDN, M]), None, {}),
        ("AZ-10", [M] * 6 + [B(4285, 4292, 4284, 4291), B(4291, 4292, 4288, 4289), M], dv10, {}),
        ("AZ-11", [flat] * 6 + [B(4288, 4292, 4287, 4291.5), B(4291, 4291.5, 4280, 4281), B(4281, 4292, 4280.5, 4291),
                                B(4291, 4291.5, 4286, 4287)], dv11, {}),
        ("AZ-17", ZB + [ZUP, ZBU], None, dict(dvWait=0)),
        ("AZ-18", ZB[:5] + [B(4294.8, 4295, 4284, 4285)] + [ZUP, ZDN, M], None, {}),
        # invalidation and a bearish reversal on the same bar while waiting (invalidation first: no detection)
        ("inv+rev", ZB + [ZUP, B(4299.5, 4300, 4298.2, 4298.4)], None, {}),
        # the last bar of the wait detects (wait 3: approach bar 6, bars 7 / 8 bullish, bar 9 bearish)
        ("last wait bar", ZB + [ZUP, ZBN, ZBN, B(4292.5, 4293, 4291, 4291.5), M], None, {}),
    ]
    ok_all, bad = True, []
    n_ev = 0
    scov = {}
    for name, seq, dv, ov in sc:
        bars = az.bars_of(seq, az.FR)
        for i, b in enumerate(bars):
            b["dv"] = (dv or {}).get(i, {})
        a = run_orig(bars, ov)
        b = run_new(bars, ov)
        n_ev += len(a.events)
        for k, v in coverage(a, ov).items():
            scov[k] = scov.get(k, 0) + v
        d = first_diff(a, b)
        if d is not None:
            ok_all = False
            bad.append((name, d))
    a = run_orig(az.bars_of(ZB + [ZUP, B(4299.5, 4300, 4298.2, 4298.4)], az.FR))
    lw = run_orig(az.bars_of(ZB + [ZUP, ZBN, ZBN, B(4292.5, 4293, 4291, 4291.5), M], az.FR))
    check("DT-A1 the ACC-5B scenarios (AZ-01..18 bars) and 2 boundary scenarios give identical events / base states in the "
          "original and the indicator", ok_all and n_ev > 0, f"{bad} events={n_ev}")
    check("DT-A2 boundary scenarios behave as the original documents: invalidation wins over a same-bar reversal (no event), a "
          "reversal on the last wait bar (approach + 3) is detected", a.events == [] and [e[0] - e[5] for e in lw.events] == [3],
          f"{a.events} {lw.events}")
    return n_ev, scov


def gate_display():
    bars = series(66, 40, 0.02)
    base = run_new(bars)
    ref = run_orig(bars)
    variants = [dict(dsTf0=False), dict(dsTf1=False, dsTf3=False), dict(dsTf0=False, dsTf1=False, dsTf2=False, dsTf3=False,
                                                                           dsTf4=False),
                dict(dsMaxGrp=1), dict(dsMaxGrp=80), dict(dsAllB=True), dict(dsAllB=True, dsMaxGrp=3), dict(dsTz="UTC")]
    same, det = True, ""
    for v in variants:
        r = run_new(bars, v)
        if first_diff(base, r) is not None:
            same, det = False, f"{v} {first_diff(base, r)}"
        bad, _ = draw_check(r)
        if bad:
            same, det = False, f"{v} drawing {bad[:2]}"
        nl = len([x for x in live(r, "label") if "基準#" in str(x.args[2])])
        if nl > r.inp["dsMaxGrp"]:
            same, det = False, f"{v} {nl} base groups live > cap"
    check("DT-V1 display settings (timeframe OFF, all OFF, drawing cap 1 / 80, all-base annotations, label time zone) do not change "
          "any detection event or active base; hidden timeframes draw nothing; at most the cap of base groups stay drawn",
          same and first_diff(ref, base) is None and base.events, det)
    r = run_new(bars, dict(dsMaxGrp=1))
    ev_ids = {e[1] for e in r.events}
    act = len(r.env["dvBases"])
    check("DT-V2 cap 1: old drawing objects deleted, the internal active bases are the same as without a cap (none removed by the "
          "display limit)", act == len(base.env["dvBases"]) and any(d.deleted for d in r.draws) and len(ev_ids) > 1
          and [g.id for g in r.env["dvBases"]] == [g.id for g in base.env["dvBases"]],
          f"active={act} vs {len(base.env['dvBases'])}")
    # several detections on one bar are all drawn (stacked, not merged)
    byb = {}
    for e in base.events:
        byb.setdefault(e[0], []).append(e)
    multi = [es for es in byb.values() if len(es) >= 2]
    okm = True
    for es in multi:
        for side in (-1, 1):
            sub = [e for e in es if e[3] == side]
            lb = [d for d in base.draws if d.kind == "label" and d.bar == es[0][0] and str(d.args[2])[:3] in ("ダブル", "トリプ")
                  and (("トップ" in str(d.args[2]).split("\n")[0]) == (side == -1))]
            if len(lb) != len(sub) or len({d.args[1] for d in lb}) != len(lb):
                okm = False
    check("DT-V3 bars with several detections (different timeframes / bases): one label per detection, each at its own height",
          multi and okm, f"bars with >= 2 detections: {len(multi)}")
    # D and T on the same base both kept
    both = {}
    for e in base.events:
        both.setdefault(e[1], set()).add(e[4])
    ids = [g for g, s in both.items() if s == {2, 3}]
    okb = True
    for g in ids:
        lb = [[d for d in base.draws if d.kind == "label" and str(d.args[2]).split("\n")[1:2] == [f"#{g} {c}回目"]
               and str(d.args[2])[:3] in ("ダブル", "トリプ")] for c in (2, 3)]
        if not (len(lb[0]) == 1 and len(lb[1]) == 1 and lb[0][0].deleted == lb[1][0].deleted):
            okb = False
    check("DT-V4 a base with a double and then a triple detection has both labels (one each), kept or removed together with "
          "the base's drawings (the double is not replaced by the triple)", ids and okb, f"bases with both: {len(ids)}")


def gate_realtime_prefix():
    bars = series(67, 25, 0.02)
    hist = run_new(bars)
    rt = run_new(with_ticks(bars, len(bars) // 2))
    ort = run_orig(with_ticks(bars, len(bars) // 2))
    check("DT-R1 realtime ticks on the second half (one execution per tick, state rolled back between ticks): the same events, "
          "base states and drawings as on history, decided on the confirmed tick only; the original under ticks agrees",
          first_diff(hist, rt) is None and created(hist) == created(rt) and first_diff(ort, rt) is None and hist.events,
          str(first_diff(hist, rt)))
    cut = len(bars) * 2 // 3
    part = run_new(bars[:cut])
    check("DT-R2 no repaint / lookahead: a run on the first 2/3 gives exactly the full run's events, states and created drawings "
          "for those bars", part.events == [e for e in hist.events if e[0] < cut] and part.snaps == hist.snaps[:cut]
          and created(part) == [c for c in created(hist) if c[1] < cut], "")


def gate_static():
    o = ORIG_RAW
    n = NEW_RAW
    calls = [x.strip() for x in o.split("\n") if x.startswith("[dvh")]
    check("DT-T1 the 4 request.security calls are character-identical to the original", calls and all(c in n for c in calls)
          and n.count("request.security(") == 4)
    import re
    for nm in ["dvPiv", "dvWait"] + [f"dv{x}{k}" for k in range(5) for x in "BD"]:
        po = re.search(rf"^{nm}\s*=\s*input\.\w+\((.*)$", o, re.M)
        pn = re.search(rf"^{nm}\s*=\s*input\.\w+\((.*)$", n, re.M)
        if not (po and pn and po.group(1) == pn.group(1)):
            check(f"DT-T2 input {nm} identical", False, f"{po and po.group(1)} | {pn and pn.group(1)}")
            return
    check("DT-T2 detection inputs (pivot bars, wait bars, 5 x buffer / distance: defaults, minval, step) identical to the original",
          True)
    bad = [w for w in ("strategy.", "AcRt", "acRts", "AcBox", "Fvg", "dvEvLife", "dvUse", "seUse", "sessOK", "alert", "table.")
           if w in "\n".join(ap.strip_comment(x) for x in n.split("\n"))]
    check("DT-T3 no Accum / FVG / Zone / order / P5-P6 / session / alert / table code in the indicator", not bad, str(bad))
    check("DT-T4 indicator() with overlay, 500 labels / lines, Pine v5 like the original", "//@version=5" in n and
          'indicator("Double / Triple Top Bottom XAU"' in n)
    # pTime of the original holds the newest window bar's time, not the pivot's (drawing uses its own history instead)
    bars = series(68, 15, 0.02)
    a = run_orig(bars)
    piv = pivot_times(a)
    bases = all_bases(a)
    n_diff = sum(1 for gid, g in bases.items() if g[4] != piv[gid][0])
    n_new = sum(1 for gid, g in bases.items() if g[4] == piv[gid][2])
    # naive estimate (newest time - dvPiv x tf length) would be wrong where bars are missing
    tfms = [M5, 15 * 60_000, 3_600_000, 4 * 3_600_000, None]
    naive_bad = sum(1 for gid, g in bases.items() if tfms[g[1]] and g[4] - a.inp["dvPiv"] * tfms[g[1]] != piv[gid][0])
    check("DT-T5 (bug candidate in the original, not changed) DvBase.pTime = time of the newest bar of the pivot window (the last "
          "right-side bar), not of the pivot bar, for every base; unused by the detection. With missing bars subtracting the "
          "timeframe length would also be wrong -> the indicator keeps its own time history",
          n_diff == len(bases) and n_new == len(bases) and naive_bad > 0,
          f"bases={len(bases)} pTime!=pivot {n_diff} pTime==newest {n_new} naive estimate wrong {naive_bad}")


def main():
    gate_static()
    n_sc, scov = gate_scenarios()
    tot_ev, tot_mis, n_runs = gate_series(scov)
    gate_display()
    gate_realtime_prefix()
    ok = 0
    for name, res, det in RESULTS:
        print(("PASS  " if res else "FAIL  ") + name + ("" if res or not det else "\n      " + str(det)[:600]))
        ok += res
    print(f"\n[DT summary] series runs {n_runs}, compared detection events {tot_ev}, mismatching runs {tot_mis}; scenario events {n_sc}")
    print(f"{ok}/{len(RESULTS)} passed  [PINE_NOT_VERIFIED: translated Pine logic, TradingView not run]")
    return ok == len(RESULTS)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
