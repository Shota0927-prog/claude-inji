"""LTB-1 checks — LongTermDoubleTripleTopBottomXAU.pine (1H / 4H / D double / triple top / bottom, judged on each target TF).

  LT-S static    : three request.security calls ("60" / "240" / "D", lookahead_on, ticker.standard), offsets (1H: 0 on a 1H chart
                   else 1; 4H / D: always 1), chart support (time based, <= 1H) and its guidance, the detector gets no display input,
                   defaults, no 5M / max-distance carry-over, protected files unchanged
  LT-R reference : the LOGIC SECTION OF THE PINE FILE (translated by tests/acc_pine.py) fed one target-TF OHLC bar at a time ==
                   an independent reference detector written here from the spec (every event: registration / approach / expiry /
                   invalidation / detection / end, and the active-base count after every bar) on random 1H / 4H / D series and
                   settings; coverage of every rule counted on the reference
  LT-C scenarios : hand-made target-TF bars per TF (1H / 4H / D, top / bottom mirrored): detection on the approach bar / later bar,
                   wait 0 / last wait bar / expiry, invalidation vs reversal, wick break, registration bar, no re-separation by the
                   approach bar itself, consecutive touches, 2nd expired then 3rd, several bases detected on the same bar
  LT-X chart     : 5M data -> 15M / 1H / 4H / D; the core emulated as request.security delivers it (each target bar computed in its
                   own history; lower chart: out[1] + lookahead_on, 1H chart for 1H: out[0] on the confirmed bar); the CHART SECTION
                   OF THE PINE FILE (translated) receives it on 5M / 15M / 1H charts with different history starts: original
                   events identical on the common range and equal to the detector, received once, never before the source bar
                   closed, realtime ticks / the forming target bar change nothing, display ON / OFF and the drawing cap leave the
                   received events unchanged, gaps counted, drawings restored after the cap removed them
  LT-M mutation  : mutations of the Pine file are caught by at least one check

Evidence class: PINE_NOT_VERIFIED (TradingView compile / request.security / drawing limits / rendering not reproduced).
"""
import copy
import os
import random
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import acc_pine as ap        # noqa: E402

ROOT = ap.ROOT
PINE = os.path.join(ROOT, "LongTermDoubleTripleTopBottomXAU.pine")
SRC = open(PINE, encoding="utf-8").read()
LB, LE = "// ==== LTB Logic (begin) ", "// ==== LTB Logic (end) "
CB, CE = "// ==== LTB Chart (begin) ", "// ==== LTB Chart (end) "
RESULTS = []
M5, M15, H1, H4, DAY = 300_000, 900_000, 3_600_000, 14_400_000, 86_400_000
TF_MS = [H1, H4, DAY]
TFJA = ["1時間", "4時間", "日足"]
EPS = 1e-7
BASE_COMMIT = "2633c84"          # branch tip before LTB-1 (protected files compared with it)

# drawings are chart objects referenced by var state: the snapshot / rollback keeps the reference
ap.Drawing.__deepcopy__ = lambda self, memo: self


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


def section(src, b, e):
    i, j = src.index(b), src.index(e)
    return src[src.index("\n", i) + 1:j]


def tonumber(s):
    try:
        v = float(s)
    except (TypeError, ValueError):
        return None
    return None if v != v else v


def make_env(src, overrides=None):
    inp = ap.inputs(src)
    for k in (overrides or {}):
        if k not in inp:
            raise KeyError("unknown input " + k)
    inp.update(overrides or {})
    draws = []
    env = ap.make_env(ap.Broker(), draws)
    env.update(inp)
    env.update(_VARS=set(), _VARIPS=set(), __first__=True, _draws=draws,
               str__split=lambda s, sep: s.split(sep), str__tonumber=tonumber,
               array__new_string=lambda n=0, v=None: [v] * n,
               label__style_diamond="diamond", label__style_label_left="left", line__style_dashed="dashed",
               line__style_dotted="dotted")
    return env


# ============================================================================
# detector (the translated LOGIC section) — one target TF, its own bars in order
# ============================================================================
class Det:
    """what f_ltCore does inside request.security: one LtTf, ltStep on every target-TF bar (bar_index = its own index)."""

    def __init__(self, k, ov=None, src=None):
        self.src = src or SRC
        self.env = make_env(self.src, ov)
        exec(compile(ap.Translator().translate(ap.logical_lines(section(self.src, LB, LE))), "<LTB logic>", "exec"), self.env)
        e = self.env
        buf, dist = ([("dvB1", "dvD1"), ("dvB4", "dvD4"), ("dvBD", "dvDD")][k])
        m = re.search(r'request\.security\(ltTk, "(?:60|240|D)",\s*f_ltCore\(%d, (\w+), (\w+),' % k, self.src)
        if m:                                             # the inputs the request.security call of this TF passes
            buf, dist = m.group(1), m.group(2)
        self.S = e["ltNew"](k, e["dvPiv"], e["dvWait"], e[buf], e[dist])
        self.k, self.n = k, 0
        self.blocks = []

    def step(self, b, commit=True):
        S = self.S if commit else copy.deepcopy(self.S)
        blk = self.env["ltStep"](S, b["o"], b["h"], b["l"], b["c"], b["T"], b["C"], self.n)
        if commit:
            self.blocks.append(blk)
            self.n += 1
        return blk

    def run(self, bars):
        for b in bars:
            self.step(b)
        return self


def parse_block(blk):
    """-> (header dict, [event tuples]) in the normalised form shared with the reference."""
    parts = blk.split(";")
    h = parts[0].split(",")
    assert h[0] == "B", blk
    hd = dict(T=int(h[1]), C=int(h[2]), prevT=None if h[3] == "NaN" else int(h[3]), nAct=int(h[4]), bi=int(h[5]))
    return hd, [norm(e.split(",")) for e in parts[1:] if e]


def norm(f):
    ty = f[0]
    if ty == "R":
        return ("R", int(f[1]), int(f[2]), float(f[3]), int(f[4]), int(f[5]), int(f[6]))
    if ty == "A":
        return ("A", int(f[1]), int(f[2]), float(f[3]), int(f[4]), int(f[7]), int(f[8]), float(f[10]), int(f[11]))
    if ty == "D":
        return ("D", int(f[1]), int(f[2]), float(f[3]), int(f[4]), int(f[7]), int(f[8]), int(f[11]), int(f[13]))
    if ty == "V":
        return ("V", int(f[1]), int(f[2]))
    return (ty, int(f[1]))


def det_events(d):
    """[(bar index, event)] + per-bar active counts."""
    ev, act = [], []
    for i, blk in enumerate(d.blocks):
        hd, es = parse_block(blk)
        act.append(hd["nAct"])
        ev += [(i, e) for e in es]
    return ev, act


# ============================================================================
# independent reference (written from the spec, not from the Pine text)
# ============================================================================
class Ref:
    def __init__(self, piv, wait, buf, dist):
        self.N, self.wait, self.buf, self.dist = piv, wait, buf, dist
        self.bars, self.bases, self.next_id = [], [], 1
        self.events, self.act = [], []
        self.cov = {}

    def c(self, key):
        self.cov[key] = self.cov.get(key, 0) + 1

    def step(self, b):
        i = len(self.bars)
        self.bars.append(b)
        out = []
        N = self.N
        if i >= 2 * N:
            ctr = i - N
            win = self.bars[ctr - N:i + 1]
            cb = self.bars[ctr]
            right = self.bars[ctr + 1:i + 1]
            others = [x for j, x in enumerate(win) if j != N]
            if all(cb["h"] > x["h"] for x in others):
                g = dict(id=self.next_id, side=-1, lvl=cb["h"], pvT=cb["T"], cfT=b["T"], cfTc=b["C"], reg=i,
                         away=cb["h"] - min(x["l"] for x in right) >= self.dist - EPS, cnt=1, wait=False, app=None)
                self.next_id += 1
                self.bases.append(g)
                out.append(("R", g["id"], -1, g["lvl"], g["pvT"], g["cfT"], g["cfTc"]))
            if all(cb["l"] < x["l"] for x in others):
                g = dict(id=self.next_id, side=1, lvl=cb["l"], pvT=cb["T"], cfT=b["T"], cfTc=b["C"], reg=i,
                         away=max(x["h"] for x in right) - cb["l"] >= self.dist - EPS, cnt=1, wait=False, app=None)
                self.next_id += 1
                self.bases.append(g)
                out.append(("R", g["id"], 1, g["lvl"], g["pvT"], g["cfT"], g["cfTc"]))
        for g in sorted(self.bases, key=lambda x: -x["id"]):     # newest first
            if g["reg"] == i:
                self.c("skip_registration_bar")
                continue
            top = g["side"] == -1
            # mirror to a "top" view: s = +1 top, prices compared as s * x
            s = 1 if top else -1
            hi, lo = (b["h"], b["l"]) if top else (b["l"], b["h"])     # the extreme toward / away from the level
            towards = lambda x: s * x                                  # noqa: E731
            closed_beyond = towards(b["c"]) > towards(g["lvl"]) + self.buf + EPS
            reversal = towards(b["c"]) < towards(b["o"])
            end = False
            if closed_beyond:
                out.append(("V", g["id"], 1 if g["wait"] else 0))
                self.c("invalidated_waiting" if g["wait"] else "invalidated")
                if reversal:
                    self.c("invalidation_beats_reversal")
                if towards(hi) > towards(g["lvl"]) + self.buf + EPS:
                    pass
                end = True
            else:
                if not closed_beyond and towards(hi) > towards(g["lvl"]) + self.buf + EPS:
                    self.c("wick_beyond_not_invalid")
                detect = False
                if g["wait"]:
                    if reversal:
                        detect = True
                        g["wait"] = False
                        lag = i - g["app"]
                        self.c("det_later")
                        if lag == self.wait:
                            self.c("det_last_wait_bar")
                    elif i - g["app"] >= self.wait:
                        g["wait"] = False
                        out.append(("X", g["id"]))
                        self.c(f"expired_x{g['cnt']}")
                    end = not g["wait"] and g["cnt"] >= 3
                elif g["cnt"] < 3 and towards(hi) >= towards(g["lvl"]) - self.buf - EPS:
                    if not g["away"]:
                        self.c("touch_without_separation")
                    else:
                        g["cnt"] += 1
                        g["away"] = False
                        g["app"], g["appT"], g["appP"] = i, b["T"], b["h"] if top else b["l"]
                        st = 1 if reversal else (0 if self.wait > 0 else 2)
                        g["wait"] = st == 0
                        if reversal:
                            detect = True
                            self.c("det_app")
                        if st == 2:
                            self.c(f"expired_x{g['cnt']}")
                        out.append(("A", g["id"], g["side"], g["lvl"], g["pvT"], g["cnt"], g["appT"], g["appP"], st))
                        end = not g["wait"] and g["cnt"] >= 3
                if detect:
                    out.append(("D", g["id"], g["side"], g["lvl"], g["pvT"], g["cnt"], g["appT"], b["T"], i - g["app"]))
                    self.c(("top" if top else "bot") + f"_x{g['cnt']}")
                if not end and g["app"] != i and towards(lo) <= towards(g["lvl"]) - self.dist + EPS:
                    g["away"] = True
                if not end and g["app"] == i and towards(lo) <= towards(g["lvl"]) - self.dist + EPS:
                    self.c("approach_bar_range_not_separation")
            if end:
                self.bases.remove(g)
                out.append(("E", g["id"]))
                if g["cnt"] >= 3:
                    self.c("ended_after_3rd")
        dets = [e for e in out if e[0] == "D"]
        if len(dets) >= 2:
            self.c("multi_det_same_bar")
        self.events += [(i, e) for e in out]
        self.act.append(len(self.bases))
        return out

    def run(self, bars):
        for b in bars:
            self.step(b)
        return self


PARAMS = {0: ("dvB1", "dvD1"), 1: ("dvB4", "dvD4"), 2: ("dvBD", "dvDD")}


def ref_for(k, ov=None):
    inp = ap.inputs(SRC)
    inp.update(ov or {})
    b, d = PARAMS[k]
    return Ref(inp["dvPiv"], inp["dvWait"], inp[b], inp[d])


# ============================================================================
# series
# ============================================================================
def rand_tf(seed, n, tf_ms, scale, grid=None, t0=1_790_000_000_000):
    rnd = random.Random(seed)
    p, out = 2000.0, []
    reg, left = 0.0, 0
    for i in range(n):
        if left <= 0:
            reg, left = rnd.choice([0.0, 0.0, 0.35, -0.35]) * scale, rnd.randint(10, 80)
        left -= 1
        o = p + (rnd.gauss(0, 3 * scale) if rnd.random() < 0.05 else 0.0)      # occasional opening gap
        c = o + reg + rnd.gauss(0, scale)
        h = max(o, c) + abs(rnd.gauss(0, 0.5 * scale))
        l = min(o, c) - abs(rnd.gauss(0, 0.5 * scale))
        if grid:
            o, h, l, c = (round(x / grid) * grid for x in (o, h, l, c))
            h, l = max(h, o, c), min(l, o, c)
        T = t0 + i * tf_ms
        out.append(dict(T=T, C=T + tf_ms, o=o, h=h, l=l, c=c))
        p = c
    return out


def compare(k, bars, ov=None):
    d = Det(k, ov).run(bars)
    r = ref_for(k, ov).run(bars)
    ev, act = det_events(d)
    if ev != r.events or act != r.act:
        for x, (a, b) in enumerate(zip(ev, r.events)):
            if a != b:
                return False, f"first diff #{x}: pine {a} ref {b}", r, d
        return False, f"lengths {len(ev)} / {len(r.events)} act equal {act == r.act}", r, d
    return True, "", r, d


def gate_reference():
    cov = {}
    n_ev = n_det = 0
    bad = []
    settings = [{}, dict(dvWait=0), dict(dvWait=1), dict(dvWait=5), dict(dvPiv=2), dict(dvPiv=6),
                dict(dvD1=0.0, dvD4=0.0, dvDD=0.0), dict(dvB1=0.0, dvB4=0.0, dvBD=0.0), dict(dvPiv=2, dvWait=2)]
    for k, (tf, scale) in enumerate(zip(TF_MS, (4.0, 8.0, 16.0))):
        for si, ov in enumerate(settings):
            for seed in range(3):
                for grid in (None, 0.5 if k == 0 else 1.0):
                    bars = rand_tf(1000 * k + 10 * si + seed, 900, tf, scale, grid)
                    ok, why, r, d = compare(k, bars, ov)
                    n_ev += len(r.events)
                    n_det += sum(1 for _, e in r.events if e[0] == "D")
                    for kk, v in r.cov.items():
                        cov[kk] = cov.get(kk, 0) + v
                    if not ok:
                        bad.append((k, ov, seed, grid, why))
    print(f"  [LT-R] events compared {n_ev}, detections {n_det}, mismatches {len(bad)}")
    print("  [LT-R] coverage: " + ", ".join(f"{k}={v}" for k, v in sorted(cov.items())))
    check("LT-R1 1H / 4H / D: translated Pine detector == independent reference on every event and every bar's active-base count "
          "(9 settings x 3 seeds x float / grid prices x 3 TFs)", not bad and n_det > 0, str(bad[:3]))
    need = ["top_x2", "top_x3", "bot_x2", "bot_x3", "det_app", "det_later", "det_last_wait_bar", "expired_x2", "expired_x3",
            "invalidated", "invalidated_waiting", "invalidation_beats_reversal", "wick_beyond_not_invalid", "skip_registration_bar",
            "touch_without_separation", "approach_bar_range_not_separation", "ended_after_3rd", "multi_det_same_bar"]
    miss = [x for x in need if cov.get(x, 0) == 0]
    check("LT-R2 coverage on the random series: every rule occurred (" + ", ".join(need) + ")", not miss, str(miss))
    return n_ev


# ============================================================================
# hand-made scenarios
# ============================================================================
def mk(rows, tf_ms, t0=1_790_006_400_000):
    return [dict(T=t0 + i * tf_ms, C=t0 + (i + 1) * tf_ms, o=o, h=h, l=l, c=c) for i, (o, h, l, c) in enumerate(rows)]


def mirror(rows):
    return [(4000 - o, 4000 - l, 4000 - h, 4000 - c) for o, h, l, c in rows]


def top_base(H, dist, n=4):
    """n lower bars, the peak H, n bars falling at least dist below H (last right bar = registration bar). -> rows"""
    rows = [(H - 30 + i, H - 25 + i, H - 33 + i, H - 28 + i) for i in range(n)]
    rows.append((H - 6, H, H - 8, H - 4))
    for j in range(n):
        lo = H - 8 - (dist + 4) * (j + 1) / n
        rows.append((lo + 3, lo + 5, lo, lo + 1))
    return rows


def evs_of(k, rows, ov=None):
    d = Det(k, ov).run(mk(rows, TF_MS[k]))
    r = ref_for(k, ov).run(mk(rows, TF_MS[k]))
    ev, _ = det_events(d)
    return ev, ev == r.events


def dets(ev, gid=1):
    return [(i, e[5], e[8]) for i, e in ev if e[0] == "D" and e[1] == gid]       # (bar, count, lag) of base gid


def kinds(ev, ty, gid=1):
    return [i for i, e in ev if e[0] == ty and e[1] == gid]


def multi_rows(H, B, D):
    """two tops (H, then H - B - 2 below H - buffer) both approached and detected on the last bar."""
    H2 = H - B - 2
    rows = top_base(H, D) + [(H - D - 6, H - D - 2, H - D - 9, H - D - 8)] * 2
    rows += [(H - D - 8, H2 - 6, H - D - 9, H2 - 7), (H2 - 6, H2, H2 - 8, H2 - 3)]
    for j in range(4):
        lo = H2 - 8 - (D + 4) * (j + 1) / 4
        rows.append((lo + 3, lo + 5, lo, lo + 1))
    rows += [(H - B - 1, H - B + 1.5, H - B - 3, H - B - 2)]
    return rows


def gate_scenarios():
    allok, det = True, []
    n = 0
    for k in range(3):
        inp = ap.inputs(SRC)
        B, D = inp[PARAMS[k][0]], inp[PARAMS[k][1]]
        H = 2000.0
        base = top_base(H, D)
        R = len(base) - 1                      # registration bar index
        lowp = H - D - 10

        def cases():
            # (name, rows, expectation(ev) -> bool)
            yield ("approach bar bearish -> detected on the approach bar (lag 0)",
                   base + [(H - B - 1, H - B + 1, H - B - 3, H - B - 2)],
                   lambda ev: dets(ev) == [(R + 1, 2, 0)])
            yield ("approach bar bullish, bearish 2 bars later -> detected there (lag 2)",
                   base + [(H - B - 3, H - B + 0.5, H - B - 4, H - B - 1), (H - B - 1, H - B, H - B - 2, H - B - 0.5),
                           (H - B - 0.5, H - B, H - B - 3, H - B - 2)],
                   lambda ev: dets(ev) == [(R + 3, 2, 2)])
            yield ("bearish on the last wait bar (3rd) -> detected (lag 3)",
                   base + [(H - B - 3, H - B, H - B - 4, H - B - 1)] + [(H - B - 2, H - B - 1, H - B - 3, H - B - 1.5)] * 2
                   + [(H - B - 1, H - B - 0.5, H - B - 4, H - B - 3)],
                   lambda ev: dets(ev) == [(R + 4, 2, 3)])
            yield ("no bearish through the 3rd wait bar -> expired on it, no detection, counted as the 2nd approach",
                   base + [(H - B - 3, H - B, H - B - 4, H - B - 1)] + [(H - B - 2, H - B - 1, H - B - 3, H - B - 1.5)] * 3
                   + [(H - B - 1, H - B - 0.5, H - B - 4, H - B - 3)],
                   lambda ev: not dets(ev) and kinds(ev, "X") == [R + 4])
            yield ("wait 0: bullish approach bar -> expired at once; a later bearish bar is not a detection",
                   base + [(H - B - 3, H - B, H - B - 4, H - B - 1), (H - B - 1, H - B - 0.5, H - B - 4, H - B - 3)],
                   lambda ev: not dets(ev) and [e[8] for _, e in ev if e[0] == "A" and e[1] == 1] == [2])
            yield ("close above H + buffer on a bearish bar while waiting -> invalidated, not detected",
                   base + [(H - B - 3, H - B, H - B - 4, H - B - 1), (H + B + 3, H + B + 4, H - 2, H + B + 1)],
                   lambda ev: not dets(ev) and [e for _, e in ev if e[0] == "V" and e[1] == 1] == [("V", 1, 1)])
            yield ("wick above H + buffer, close exactly H + buffer, bearish -> not invalidated, detected",
                   base + [(H + B + 2, H + B + 6, H - B - 2, H + B)],
                   lambda ev: dets(ev) == [(R + 1, 2, 0)] and not kinds(ev, "V"))
            yield ("registration bar touches H - buffer (separation already met) -> not an approach; next bar is",
                   base[:-1] + [(H - B - 5, H - B + 1, lowp, H - B - 4)] + [(H - B - 1, H - B + 1, H - B - 3, H - B - 2)],
                   lambda ev: dets(ev) == [(R + 1, 2, 0)] and not [i for i, e in ev if e[0] == "A" and i == R])
            yield ("approach bar's own range reaching H - distance does not re-separate; the next touch is not a 3rd approach",
                   base + [(H - B - 3, H - B, lowp, H - B - 1), (H - B - 1, H - B, H - B - 3, H - B - 2),
                           (H - B - 3, H - B, H - B - 5, H - B - 4), (H - B - 4, H - B + 1, H - B - 6, H - B - 5)],
                   lambda ev: [e[5] for _, e in ev if e[0] == "A" and e[1] == 1] == [2])
            yield ("consecutive touches without re-separation count once",
                   base + [(H - B - 3, H - B, H - B - 4, H - B - 1)] * 3 + [(H - B - 1, H - B + 1, H - B - 3, H - B - 0.5)] * 3,
                   lambda ev: [e[5] for _, e in ev if e[0] == "A" and e[1] == 1] == [2])
            yield ("2nd approach expires, re-separation, 3rd approach bearish -> triple, base ended",
                   base + [(H - B - 3, H - B, H - B - 4, H - B - 1)] + [(H - B - 2, H - B - 1, H - B - 3, H - B - 1.5)] * 3
                   + [(H - B - 2, H - B - 1, lowp, lowp + 1)] + [(H - B - 1, H - B + 1, H - B - 3, H - B - 2)],
                   lambda ev: dets(ev) == [(R + 6, 3, 0)] and kinds(ev, "X") == [R + 4] and kinds(ev, "E") == [R + 6])
            yield ("double detected, re-separation, triple detected -> both, base ended on the triple",
                   base + [(H - B - 1, H - B + 1, H - B - 3, H - B - 2), (H - B - 2, H - B - 1, lowp, lowp + 1),
                           (H - B - 1, H - B + 1, H - B - 3, H - B - 2)],
                   lambda ev: dets(ev) == [(R + 1, 2, 0), (R + 3, 3, 0)] and kinds(ev, "E") == [R + 3])
            yield ("a left bar with the same high as the peak (tie) -> no base at H, nothing approached / detected",
                   [r if j != 2 else (H - 6, H, H - 9, H - 7) for j, r in enumerate(base)]
                   + [(H - B - 1, H - B + 1, H - B - 3, H - B - 2)],
                   lambda ev: not [e for _, e in ev if e[0] == "R" and e[3] == (H if e[2] == -1 else 4000 - H)]
                   and not [e for _, e in ev if e[0] == "D"])
            yield ("touch before the minimum distance is reached is not an approach",
                   base[:5] + [(H - 8, H - 6, H - 10, H - 9)] * 4 + [(H - B - 1, H - B + 1, H - B - 3, H - B - 2)] * 2,
                   lambda ev: not kinds(ev, "A") and not dets(ev))

        for name, rows, exp in cases():
            ov = dict(dvWait=0) if name.startswith("wait 0") else None
            for mir in (False, True):
                rr = mirror(rows) if mir else rows
                ev, same = evs_of(k, rr, ov)
                ok = same and exp(ev)
                n += 1
                if not ok:
                    allok = False
                    det.append((TFJA[k], "bottom" if mir else "top", name, ev[:12], same))
        # several bases detected on the same bar (two tops of nearly equal level)
        rows = multi_rows(H, B, D)
        for mir in (False, True):
            ev, same = evs_of(k, mirror(rows) if mir else rows)
            last = len(rows) - 1
            ds = [e for i, e in ev if e[0] == "D" and i == last]
            n += 1
            if not (same and len(ds) >= 2 and len({e[1] for e in ds}) == len(ds)):
                allok = False
                det.append((TFJA[k], "multi", mir, ev[-8:], same))
    check("LT-C1 1H / 4H / D scenarios (top and mirrored bottom, " + str(n) + " runs): lag 0 / lag 2 / last wait bar / expiry / "
          "wait 0 / invalidation beats reversal / wick break kept / registration bar skipped / approach bar range is no "
          "re-separation / consecutive touches once / 2nd expired then 3rd / double then triple / touch before the distance / "
          "several bases detected on the same bar; each also == the reference", allok, str(det[:3]))


# ============================================================================
# chart simulation (request.security emulation + the translated CHART section)
# ============================================================================
def market5(seed, days, scale=1.0):
    rnd = random.Random(seed)
    p, out, t0 = 2000.0, [], 1_790_000_000_000 // DAY * DAY
    reg, left = 0.0, 0
    for d in range(days):
        if (d % 7) in (5, 6):
            continue
        for s in range(23 * 12):
            t = t0 + d * DAY - H1 + s * M5
            if left <= 0:
                reg, left = rnd.choice([0.0, 0.0, 0.25, -0.25]), rnd.randint(40, 400)
            left -= 1
            q = p + reg * scale + rnd.gauss(0, 0.9 * scale)
            out.append(dict(T=t, C=t + M5, o=p, h=max(p, q) + abs(rnd.gauss(0, .4 * scale)),
                            l=min(p, q) - abs(rnd.gauss(0, .4 * scale)), c=q))
            p = q
    return out


def agg(b5, tf_ms, day=False):
    groups = {}
    for b in b5:
        key = (b["T"] - 22 * H1) // DAY if day else b["T"] // tf_ms
        groups.setdefault(key, []).append(b)
    out = []
    for key in sorted(groups):
        g = groups[key]
        T = key * DAY + 22 * H1 if day else key * tf_ms
        out.append(dict(T=T, C=T + (DAY if day else tf_ms), o=g[0]["o"], h=max(x["h"] for x in g), l=min(x["l"] for x in g),
                        c=g[-1]["c"], subs=g))
    return out


class Core:
    """f_ltCore inside request.security for one TF: its bars in its own history order; out = prevBlk ; blk."""

    def __init__(self, k, htf, ov=None, src=None):
        self.k, self.htf = k, htf
        self.det = Det(k, ov, src)
        self.outs = []
        # the packet = previous block ; this block (as the Pine line reads; a single block if the line was changed)
        self.pair = 'string out = prevBlk == "" ? blk : blk == "" ? prevBlk : prevBlk + ";" + blk' in self.det.src
        prev = ""
        for b in htf:
            blk = self.det.step(b)
            self.outs.append(blk if (prev == "" or not self.pair) else prev + ";" + blk)
            prev = blk
        self.starts = [b["T"] for b in htf]

    def idx(self, t):
        lo, hi = 0, len(self.starts) - 1
        if t < self.starts[0]:
            return -1
        while lo < hi:
            m = (lo + hi + 1) // 2
            if self.starts[m] <= t:
                lo = m
            else:
                hi = m - 1
        return lo

    def value(self, t, off):
        """request.security(lookahead_on) on a chart bar starting at t: the target bar containing t, `off` bars back."""
        j = self.idx(t) - off
        return self.outs[j] if j >= 0 else None

    def partial_value(self, t, partial_bar):
        """the forming target bar (realtime): its value computed on a copy of the state from the partial OHLC (off 0)."""
        j = self.idx(t)
        prev = self.det.blocks[j - 1] if j >= 1 else ""
        blk = self.det.env["ltStep"](copy.deepcopy(self._state_before(j)), partial_bar["o"], partial_bar["h"], partial_bar["l"],
                                     partial_bar["c"], partial_bar["T"], partial_bar["C"], j)
        return blk if (prev == "" or not self.pair) else prev + ";" + blk

    def _state_before(self, j):
        if not hasattr(self, "_snaps"):
            d = Det(self.k, None, self.det.src)
            self._snaps = []
            for b in self.htf:
                self._snaps.append(copy.deepcopy(d.S))
                d.step(b)
        return self._snaps[j]


def chart_instrument(src):
    """in-memory copy of the CHART section with two log calls: every taken block and every taken event."""
    sec = section(src, CB, CE)
    lines = sec.split("\n")
    out = []
    for x in lines:
        out.append(x)
        if x.strip() == "nNew += 1":
            ind = len(x) - len(x.lstrip(" "))
            out.append(" " * ind + "runtime.zzblk(k, sT)")
        if x.strip() == 'string ty = array.get(f, 0)':
            ind = len(x) - len(x.lstrip(" "))
            out.append(" " * ind + "runtime.zzev(k, f)")
    return "\n".join(out)


class Chart:
    """one chart: its bars (any TF <= 1H) receive the three packets and run the translated CHART section."""

    def __init__(self, cores, chart_ms, ov=None, src=None):
        self.src = src or SRC
        self.env = make_env(self.src, ov)
        self.cores, self.chart_ms = cores, chart_ms
        self.code = compile(ap.Translator().translate(ap.logical_lines(chart_instrument(self.src))), "<LTB chart>", "exec")
        self.blocks, self.events = [], []
        e = self.env
        e["runtime__zzblk"] = lambda k, sT: self.blocks.append((k, sT, e["time"], e["time_close"]))
        e["runtime__zzev"] = lambda k, f: self.events.append((k, tuple(f), e["time"], e["time_close"]))
        self.committed = None
        # the offsets each request.security call passes (evaluated from the source for this chart's TF)
        m = re.search(r"int  ltOff1 = ltChSec == 3600 \? (\d) : (\d)", self.src)
        off1 = {"ltOff1": int(m.group(1)) if chart_ms == H1 else int(m.group(2))}
        self.offs = []
        for k, (nm, tf) in enumerate((("ltPk1", "60"), ("ltPk4", "240"), ("ltPkD", "D"))):
            m = re.search(nm + r' = request\.security\(ltTk, "' + tf + r'",\s*f_ltCore\(%d, \w+, \w+, ltChartOk, (\w+)\)' % k, self.src)
            a = m.group(1)
            self.offs.append(off1[a] if a in off1 else int(a))

    def _exec(self, b, confirmed, pks):
        e = self.env
        if self.committed is not None:
            e.update(copy.deepcopy(self.committed))
        e.update(time=b["T"], time_close=b["C"], high=b["h"], low=b["l"], open=b["o"], close=b["c"], dsAtr=2.0,
                 barstate__isconfirmed=confirmed, ltChartOk=True, ltPk1=pks[0], ltPk4=pks[1], ltPkD=pks[2])
        exec(self.code, e)
        e["__first__"] = False
        if confirmed:
            self.committed = copy.deepcopy({k: e[k] for k in e["_VARS"]})

    def run(self, bars, ticks_from=None):
        for i, b in enumerate(bars):
            pks = [self.cores[k].value(b["T"], self.offs[k]) for k in range(3)]
            if ticks_from is not None and i >= ticks_from:
                # realtime: unconfirmed executions (the 1H packet of a 1H chart = the forming 1H bar computed from partial OHLC)
                nd = len(self.env["_draws"])
                nb, ne = len(self.blocks), len(self.events)
                for frac in (0.3, 0.7):
                    pb = dict(b, h=b["o"] + (b["h"] - b["o"]) * frac, l=b["o"] - (b["o"] - b["l"]) * frac,
                              c=b["o"] + (b["c"] - b["o"]) * frac)
                    tp = list(pks)
                    if self.offs[0] == 0:
                        tp[0] = self.cores[0].partial_value(b["T"], pb)
                    self._exec(pb, False, tp)
                if len(self.env["_draws"]) != nd or len(self.blocks) != nb or len(self.events) != ne:
                    self.rt_changed = True
            self._exec(b, True, pks)
        return self

    def received(self):
        """original detection events received: (tf, pivot time, side, count, approach bar, detection bar) -> chart bar."""
        out = []
        for k, f, t, tc in self.events:
            if f[0] == "D":
                out.append(((k, int(float(f[4])), int(f[2]), int(f[7]), int(float(f[8])), int(float(f[11])), int(float(f[12]))), t, tc))
        return out


def det_set(core):
    out = []
    for i, blk in enumerate(core.det.blocks):
        _, es = parse_block(blk)
        b = core.htf[i]
        for e in es:
            if e[0] == "D":
                out.append((core.k, e[4], e[2], e[5], e[6], e[7], b["C"]))
    return out


def build(seed, days=70, scale=1.0, ov=None, src=None):
    b5 = market5(seed, days, scale)
    htf = [agg(b5, H1), agg(b5, H4), agg(b5, DAY, day=True)]
    cores = [Core(k, htf[k], ov, src) for k in range(3)]
    return b5, htf, cores


def gate_chart():
    ok_eq, ok_det, ok_once, ok_time, ok_rt, ok_disp, ok_tf, ok_gap = True, True, True, True, True, True, True, True
    det = []
    n_cmp = 0
    for seed in (11, 12, 13):
        b5, htf, cores = build(seed, days=70, scale=1.2)
        full = {k: det_set(cores[k]) for k in range(3)}
        # history starts: 1H chart from the first bar, 15M chart 20 days later, 5M chart 40 days later (shorter histories)
        t15 = b5[0]["T"] + 20 * DAY
        t5 = b5[0]["T"] + 40 * DAY
        c1 = [b for b in agg(b5, H1)]
        c15 = [b for b in agg(b5, M15) if b["T"] >= t15]
        c5 = [b for b in b5 if b["T"] >= t5]
        charts = {"1H": Chart(cores, H1).run(c1, ticks_from=len(c1) - 30),
                  "15M": Chart(cores, M15).run(c15, ticks_from=len(c15) - 50),
                  "5M": Chart(cores, M5).run(c5, ticks_from=len(c5) - 80)}
        common = t5
        sets = {}
        for nm, ch in charts.items():
            rec = ch.received()
            keys = [x[0] for x in rec]
            if len(keys) != len(set(keys)):
                ok_once = False
                det.append((seed, nm, "duplicate detection received"))
            blks = [(k, sT) for k, sT, _, _ in ch.blocks]
            if len(blks) != len(set(blks)):
                ok_once = False
                det.append((seed, nm, "duplicate block"))
            for key, t, tc in rec:
                k, dT, dTc = key[0], key[5], key[6]
                same = ch.chart_ms == TF_MS[k]
                # never before the source bar closed: lower chart -> the chart bar starts at / after dTc;
                # same TF -> the source bar itself, processed on its confirmed (closing) execution
                if (same and not (t == dT and tc == dTc)) or (not same and t < dTc):
                    ok_time = False
                    det.append((seed, nm, "early / wrong bar", key, t, tc))
            sets[nm] = sorted(x for x in keys if x[5] >= common and x[6] <= c5[-1]["T"])
            if getattr(ch, "rt_changed", False):
                ok_rt = False
                det.append((seed, nm, "unconfirmed execution changed state / drawings"))
            if ch.env["ltNGap"] != [0, 0, 0]:
                ok_gap = False
                det.append((seed, nm, "gap counted on complete data", ch.env["ltNGap"]))
        end = c5[-1]["T"]
        ref = sorted(x[:6] for kk in range(3) for x in full[kk] if x[5] >= common and x[6] <= end)
        for nm, s in sets.items():
            n_cmp += len(s)
            if [x[:6] for x in s] != ref:
                ok_eq = False
                det.append((seed, nm, "common-range events differ", len(s), len(ref)))
        # every detection of the detector with dTc inside the chart history was received by that chart
        for nm, ch in charts.items():
            got = {x[0][:6] for x in ch.received()}
            cb = c1 if nm == "1H" else c15 if nm == "15M" else c5
            want = {x[:6] for kk in range(3) for x in full[kk] if x[5] >= cb[0]["T"] and x[6] <= cb[-1]["T"]}
            if not want <= got:
                ok_det = False
                det.append((seed, nm, "missing", sorted(want - got)[:3]))
        # display OFF / cap 1 / all bases: identical received events and counters
        for ov in (dict(dsTf1=False, dsTf4=False, dsTfD=False), dict(dsTf4=True, dsTfD=True, dsMaxGrp=1),
                   dict(dsTf4=True, dsTfD=True, dsAllB=True, dsMaxGrp=3)):
            ch = Chart(cores, M15, ov).run(c15)
            if ch.events != charts["15M"].events or ch.env["ltNDet"] != charts["15M"].env["ltNDet"]:
                ok_disp = False
                det.append((seed, ov, "display setting changed the received events"))
            if ov.get("dsTf1") is False and any(not d.deleted for d in ch.env["_draws"] if d.kind != "table"):
                ok_disp = False
                det.append((seed, ov, "drawings with every TF hidden"))
        # display settings never reach the detector: the cores take no display input (static) and give the same blocks
        cores_off = [Core(k, htf[k], dict(dsTf1=False, dsMaxGrp=1)) for k in range(3)]
        if any(cores_off[k].outs != cores[k].outs for k in range(3)):
            ok_disp = False
            det.append((seed, "core outputs changed by display inputs"))
        # TF state isolation: each TF's events depend only on its own bars (1H series alone == 1H inside the 3-TF run;
        # a different 4H / D series leaves the 1H blocks unchanged) and the 1H / 4H / D id sequences are independent
        alone = Det(0).run(htf[0])
        if alone.blocks != cores[0].det.blocks:
            ok_tf = False
            det.append((seed, "1H changed by other TFs"))
        ids = {k: sorted({e[1] for _, e in det_events(cores[k].det)[0] if e[0] == "R"}) for k in range(3)}
        if any(ids[k] and ids[k][0] != 1 for k in range(3)):
            ok_tf = False
            det.append((seed, "id sequence not per TF"))
        print(f"  [LT-X] seed {seed}: detections 1H {len(full[0])} / 4H {len(full[1])} / D {len(full[2])}; common-range events "
              + ", ".join(f"{nm} {len(s)}" for nm, s in sets.items()), flush=True)
    check("LT-X1 5M / 15M / 1H charts with different history starts: the original detection events (TF, pivot time, side, count, "
          "approach bar, detection bar) on the common range are identical and equal the detector's", ok_eq and n_cmp > 0, str(det[:3]))
    check("LT-X2 every detection whose source bar lies in a chart's history is received by that chart", ok_det, str(det[:3]))
    check("LT-X3 each target bar's block and each detection received once although the same packet arrives on many chart bars",
          ok_once, str(det[:3]))
    check("LT-X4 received never before the source target bar closed (lower chart: chart bar time >= source close; 1H chart for 1H: "
          "the source bar's own confirmed execution)", ok_time, str(det[:3]))
    check("LT-X5 realtime: unconfirmed chart executions (incl. the forming 1H bar's partial result on a 1H chart) change no state, "
          "no counter, no drawing", ok_rt, str(det[:3]))
    check("LT-X6 display OFF (all TFs), cap 1, all-bases + cap 3: received events and counters unchanged; the detector outputs are "
          "unchanged by display inputs; nothing drawn when every TF is hidden", ok_disp, str(det[:3]))
    check("LT-X7 TF states not mixed: the 1H detector alone == the 1H detector next to 4H / D; ids per TF start at 1", ok_tf,
          str(det[:3]))
    check("LT-X8 complete data: no gap counted", ok_gap, str(det[:3]))


def gate_forming():
    """the forming target bar never yields a detection to a lower chart; on its own TF chart only the confirmed execution counts."""
    ok, det = True, []
    b5, htf, cores = build(21, days=40, scale=1.2)
    # find a 1H bar with a detection; replay its 5M bars as the realtime bars of a 5M chart
    hits = [i for i, blk in enumerate(cores[0].det.blocks) if ";D," in blk]
    for j in hits[:15]:
        hb = htf[0][j]
        subs = hb["subs"]
        # 5M chart bars inside hb: the 1H packet is out[j - 1] — never the block of j
        for s in subs:
            v = cores[0].value(s["T"], 1)
            if v is not None and ("B," + str(hb["T"]) + ",") in v:
                ok = False
                det.append(("forming 1H block visible", j))
        # the forming bar's partial result (what out[0] would give mid-bar) differs from / precedes the close: a detection there
        # would have been premature — the chart never receives it before the first 5M bar of the next 1H bar
        if j + 1 >= len(htf[0]):
            continue
        nxt = cores[0].value(htf[0][j + 1]["T"], 1)
        if nxt is None or ("B," + str(hb["T"]) + ",") not in nxt:
            ok = False
            det.append(("not delivered on the next bar", j))
    check("LT-F1 a lower chart never sees the forming 1H bar's block; it is delivered on the first chart bar after the 1H bar "
          "closed (" + str(len(hits[:15])) + " detection bars)", ok and hits, str(det[:3]))


def gate_gap():
    ok, det = True, []
    b5, htf, cores = build(31, days=30, scale=1.2)
    c5 = [b for b in b5 if b["T"] >= b5[0]["T"] + 10 * DAY]
    hours = sorted({b["T"] // H1 for b in c5})
    h_one = hours[100]
    one = [b for b in c5 if b["T"] // H1 != h_one]
    ch1 = Chart(cores, M5).run(one)
    blk1 = {sT for k, sT, _, _ in ch1.blocks if k == 0}
    want = {b["T"] for b in htf[0] if c5[0]["T"] - 2 * H1 <= b["T"] < c5[-1]["T"] // H1 * H1 - H1}
    if ch1.env["ltNGap"][0] != 0 or not want <= blk1:
        ok = False
        det.append(("one missing hour", ch1.env["ltNGap"], len(want - blk1)))
    two = [b for b in c5 if b["T"] // H1 not in (hours[200], hours[201], hours[202])]
    ch2 = Chart(cores, M5).run(two)
    if ch2.env["ltNGap"][0] < 1:
        ok = False
        det.append(("three missing hours not counted", ch2.env["ltNGap"]))
    check("LT-X9 a chart missing one whole 1H bar still takes every 1H block (2 blocks per packet), no gap; three missing hours "
          "-> gap counted in the table", ok, str(det))


# ---- drawings ------------------------------------------------------------------------------------------------
def gate_draw():
    ok, det = True, []
    k = 0
    inp = ap.inputs(SRC)
    B, D = inp["dvB1"], inp["dvD1"]
    H = 2000.0
    # base A (top 2000) approaches and waits; base B (bottom far below) approaches -> with cap 1 A's drawings are removed;
    # A then detects -> A's base note, its confirmation note, approach marker and dashed line come back
    rowsA = top_base(H, D)                                                   # A: top 2000, registered on bar 8
    L = 1958.0
    rows = rowsA + [(1974, 1975, 1968, 1969), (1969, 1970, 1964, 1965), (1965, 1966, 1962, 1963), (1963, 1964, L, 1962),
                    (1962, 1967, 1962.5, 1966), (1966, 1971, 1966, 1970), (1970, 1975, 1970, 1974), (1974, 1980, 1975, 1979)]
    rows += [(1980, 1988, 1978, 1986), (1986, 1992, 1984, 1990)]
    rows += [(1990, 1995.5, 1989, 1994)]                                     # A: 2nd approach, bullish -> waiting
    rows += [(1993, 1994, L + B - 0.5, 1993.5)]                              # B (bottom 1958): approach, bullish -> detected
    rows += [(1994, 1995, 1990, 1991)]                                       # A: bearish -> detected (lag 2)
    rows += [(1991, 1992, 1989, 1990)] * 2
    htf = [mk(rows, H1), mk([(2000, 2001, 1999, 2000)] * 3, H4), mk([(2000, 2001, 1999, 2000)] * 2, DAY)]
    cores = [Core(i, htf[i]) for i in range(3)]
    ev = det_events(cores[0].det)[0]
    chart_bars = []
    for b in htf[0]:
        for s in range(4):
            T = b["T"] + s * M15
            chart_bars.append(dict(T=T, C=T + M15, o=b["o"], h=b["h"], l=b["l"], c=b["c"]))
    chart_bars.append(dict(T=htf[0][-1]["C"], C=htf[0][-1]["C"] + M15, o=2000, h=2000, l=2000, c=2000))
    ch = Chart(cores, M15, dict(dsMaxGrp=1)).run(chart_bars)
    apps = [(i, e) for i, e in ev if e[0] == "A"]
    dts = [(i, e) for i, e in ev if e[0] == "D"]
    dts = [(i, e) for i, e in dts if e[1] == 1]
    if not (len(apps) >= 2 and dts and dts[-1][1][8] == 2 and apps[1][1][1] != 1 and apps[1][0] == dts[-1][0] - 1):
        ok = False
        det.append(("scenario shape", apps, dts))
    else:
        gid = dts[-1][1][1]
        tag = f"1時間#{gid} "
        live = [d for d in ch.env["_draws"] if not d.deleted]
        dl = [d for d in ch.env["_draws"] if d.deleted]
        has = lambda pred: any(pred(d) for d in live)                     # noqa: E731
        A_pv, A_cf = rowsA[4], None
        if not has(lambda d: d.kind == "label" and d.text.startswith("基準 1時間#%d " % gid)):
            ok = False
            det.append("base note not restored")
        if not has(lambda d: d.kind == "label" and d.text.startswith(tag) and "確定" in d.text):
            ok = False
            det.append("confirmation note not restored")
        if not has(lambda d: d.kind == "label" and d.text.startswith(tag + "2回目") and d.kw.get("style") == "diamond"):
            ok = False
            det.append("approach marker not restored")
        apT = apps[0][1][6]
        if not has(lambda d: d.kind == "line" and d.args[2] == apT and d.kw.get("style") == "dashed"):
            ok = False
            det.append("approach line not restored")
        if not has(lambda d: d.kind == "label" and d.text.startswith("ダブルトップ 1時間") and "#%d 2回目" % gid in d.text
                   and "接近から 2 本目" in d.text):
            ok = False
            det.append("detection label")
        if not any(d.kind == "label" and d.text.startswith(tag + "2回目") for d in dl):
            ok = False
            det.append("the cap never removed A's first marker (scenario does not test the restore)")
        # one marker per approach alive (no double creation)
        if sum(1 for d in live if d.kind == "label" and d.text.startswith(tag + "2回目")) != 1:
            ok = False
            det.append("approach marker count")
        # the detection label sits on the chart bar that received it (first 15M bar after the source bar closed)
        dsrc = htf[0][dts[-1][0]]
        lab = [d for d in live if d.kind == "label" and d.text.startswith("ダブルトップ 1時間")]
        if not lab or lab[0].args[0] != dsrc["C"] or "反転の判定足 (1時間足) " not in lab[0].kw.get("tooltip", ""):
            ok = False
            det.append(("detection label position / tooltip", lab[0].args[0] if lab else None, dsrc["C"]))
    check("LT-D1 drawing cap 1: a base whose drawings were removed while waiting gets its base note, confirmation note, approach "
          "marker and dashed line back on the late detection (one marker, not two); the label sits on the receiving chart bar "
          "with the source bar's times in the tooltip", ok, str(det))

    # several detections on the same chart bar: all labels kept, stacked
    ok2, det2 = True, []
    b5, htf2, cores2 = build(13, days=70, scale=1.2)
    c15 = agg(b5, M15)
    ch = Chart(cores2, M15, dict(dsTf4=True, dsTfD=True, dsMaxGrp=80)).run(c15)
    byt = {}
    for key, t, tc in ch.received():
        byt.setdefault(t, []).append(key)
    multi = [t for t, ks in byt.items() if len(ks) >= 2]
    labs = {}
    for d in ch.env["_draws"]:
        if d.kind == "label" and re.match(r"^(ダブル|トリプル)(トップ|ボトム) ", d.text):
            labs.setdefault(d.args[0], []).append(d)
    for t in multi:
        if len(labs.get(t, [])) != len(byt[t]) or len({(d.args[1]) for d in labs[t]}) != len(labs[t]):
            ok2 = False
            det2.append((t, len(byt[t]), len(labs.get(t, []))))
    # 1H and 4H detections received on the same chart bar (constructed: the 1H detection bar closes when the 4H one does)
    inp = ap.inputs(SRC)
    r4 = multi_rows(2000.0, inp["dvB4"], inp["dvD4"])
    r1 = multi_rows(2000.0, inp["dvB1"], inp["dvD1"])
    pad = 4 * len(r4) - len(r1)
    r1 = [(1950.0, 1950.0, 1950.0, 1950.0)] * pad + r1
    t0 = 1_790_006_400_000 // H4 * H4
    hx = [mk(r1 + [(1990, 1991, 1989, 1990)] * 4, H1, t0), mk(r4 + [(1990, 1991, 1989, 1990)], H4, t0),
          mk([(1950, 1951, 1949, 1950)] * 3, DAY, t0 - 22 * H1)]
    cx = [Core(k, hx[k]) for k in range(3)]
    cb = []
    for b in hx[1]:
        for s15 in range(16):
            T = b["T"] + s15 * M15
            cb.append(dict(T=T, C=T + M15, o=b["o"], h=b["h"], l=b["l"], c=b["c"]))
    chx = Chart(cx, M15, dict(dsTf4=True, dsMaxGrp=80)).run(cb)
    byx = {}
    for key, t, tc in chx.received():
        byx.setdefault(t, []).append(key)
    cross = [t for t, ks in byx.items() if len({x[0] for x in ks}) >= 2 and len(ks) >= 4]
    labx = {}
    for d in chx.env["_draws"]:
        if d.kind == "label" and re.match(r"^(ダブル|トリプル)(トップ|ボトム) ", d.text):
            labx.setdefault(d.args[0], []).append(d)
    for t in cross:
        if len(labx.get(t, [])) != len(byx[t]) or len({d.args[1] for d in labx[t]}) != len(labx[t]):
            ok2 = False
            det2.append(("cross", t, len(byx[t]), len(labx.get(t, []))))
    check("LT-D2 several detections received on the same chart bar: random series " + str(len(multi)) + " bars; constructed 1H x 2 + "
          "4H x 2 on one bar " + str(len(cross)) + ": one label each (all kept), stacked at different prices",
          ok2 and multi and cross, str(det2[:3]))

    # label texts / tooltips are Japanese and carry id + TF; pivot note at the real pivot bar time
    ok3, det3 = True, []
    names = {d.text.split("\n")[0] for d in ch.env["_draws"] if d.kind == "label" and re.match(r"^(ダブル|トリプル)", d.text)}
    for nm in names:
        if not re.match(r"^(ダブル|トリプル)(トップ|ボトム) (1時間|4時間|日足)$", nm):
            ok3 = False
            det3.append(nm)
    pv = {}
    for k in range(3):
        for b in htf2[k]:
            pv[(k, b["T"])] = b
    for d in ch.env["_draws"]:
        m = re.match(r"^基準 (1時間|4時間|日足)#(\d+) (山|谷) ", d.text) if d.kind == "label" else None
        if m:
            k = TFJA.index(m.group(1))
            b = pv.get((k, d.args[0]))
            if b is None or abs((b["h"] if m.group(3) == "山" else b["l"]) - d.args[1]) > 1e-6:
                ok3 = False
                det3.append(("pivot note not on the real pivot bar", d.text))
    check("LT-D3 label names 'ダブルトップ 1時間' etc. only; every base note sits on the real pivot bar's open time at its high / low",
          ok3 and names, str(det3[:3]))


# ============================================================================
# static
# ============================================================================
def code_only(src):
    return "\n".join(ap.strip_comment(x) for x in src.split("\n"))


def gate_static():
    s = code_only(SRC)
    calls = re.findall(r'request\.security\((\w+), "(\w+)",\s*f_ltCore\((\d), (\w+), (\w+), (\w+), (\w+)\), lookahead = barmerge\.lookahead_on\)', s)
    ok = (len(re.findall(r"request\.security\(", s)) == 3 and [c[1] for c in calls] == ["60", "240", "D"]
          and all(c[0] == "ltTk" and c[5] == "ltChartOk" for c in calls)
          and calls[0][6] == "ltOff1" and calls[1][6] == "1" and calls[2][6] == "1"
          and [c[3:5] for c in calls] == [("dvB1", "dvD1"), ("dvB4", "dvD4"), ("dvBD", "dvDD")]
          and "ltOff1 = ltChSec == 3600 ? 0 : 1" in s and "ticker.standard(syminfo.tickerid)" in s)
    check("LT-S1 three request.security calls (60 / 240 / D) of f_ltCore with each TF's own inputs, lookahead_on, ticker.standard; "
          "offset 0 only for 1H on a 1H chart, else 1", ok)
    core = s[s.index("f_ltCore(int k"):s.index("string ltPk1")]
    logic = code_only(section(SRC, LB, LE))
    ok2 = ("var LtTf S = ltNew(k, dvPiv, dvWait, buf, dist)" in core and "out[off]" in core and
           "ltStep(S, open, high, low, close, time, time_close, bar_index)" in core and
           not re.search(r"\bds\w+", core + logic) and "request.security" not in logic and "ltChartOk" not in logic)
    check("LT-S2 the detector runs inside request.security on the target TF's own open / high / low / close / time / bar_index "
          "(var state per call); no display input reaches it", ok2)
    ok3 = ("bool ltChartOk = ltTimeBar and ltChSec <= 3600" in s and "not timeframe.isticks" in s and "chart.is_renko" in s
           and "if barstate.isconfirmed and ltChartOk" in s and "このチャートには対応していません" in s and "1時間足以下" in s)
    check("LT-S3 chart support: time-based charts <= 1H only; otherwise nothing is computed and the table asks to switch", ok3)
    inp = ap.inputs(s)
    want = dict(dvPiv=4, dvWait=3, dvB1=5.0, dvD1=15.0, dvB4=10.0, dvD4=30.0, dvBD=20.0, dvDD=60.0, dsTf1=True, dsTf4=False,
                dsTfD=False)
    check("LT-S4 defaults: pivot 4, wait 3, 1H 5 / 15, 4H 10 / 30, D 20 / 60; display 1H ON, 4H OFF, D OFF",
          all(inp.get(k) == v for k, v in want.items()), str({k: inp.get(k) for k in want}))
    ok5 = (not re.search(r"dvMx|dvB0|dvD0|最大離れ幅制限|\b15分", s) and "rMin := math.min(rMin, low)" not in s
           and "is5mChart" not in s and "dvh1" not in s)
    check("LT-S5 not carried over: 5M base / 15M base / 5M max distance / the chart-bar high-low added to the initial distance / "
          "chart-side accumulation of delivered HTF values", ok5)
    try:
        diff = subprocess.run(["git", "diff", "--name-only", BASE_COMMIT, "--", "DoubleTripleTopBottomXAU.pine",
                               "AccumStrategyXAU.pine", "ZoneComboLabXAU.pine"], cwd=ROOT, capture_output=True, text=True)
        ok6 = diff.returncode == 0 and diff.stdout.strip() == ""
        why = diff.stdout + diff.stderr
    except OSError as ex:
        ok6, why = False, str(ex)
    check("LT-S6 DoubleTripleTopBottomXAU.pine / AccumStrategyXAU.pine / ZoneComboLabXAU.pine unchanged since " + BASE_COMMIT, ok6, why)


# ============================================================================
# mutations
# ============================================================================
MUTATIONS = [
    ("pivot ties accepted", "isH := isH and mh > array.get(S.hs, j)", "isH := isH and mh >= array.get(S.hs, j)"),
    ("registration bar not skipped", "if g.aBar < bi", "if g.aBar <= bi"),
    ("approach bar range re-separates", "(na(g.appBar) or g.appBar != bi) and", "true and"),
    ("reversal before invalidation", "if top ? c > g.lvl + S.buf + EPS : c < g.lvl - S.buf - EPS",
     "if (top ? c > g.lvl + S.buf + EPS : c < g.lvl - S.buf - EPS) and not (g.waiting and (top ? c < o : c > o))"),
    ("wick invalidates", "if top ? c > g.lvl + S.buf + EPS : c < g.lvl - S.buf - EPS",
     "if top ? h > g.lvl + S.buf + EPS : l < g.lvl - S.buf - EPS"),
    ("expiry one bar late", "else if bi >= g.waitEnd", "else if bi > g.waitEnd"),
    ("expiry not counted", "                        g.cnt    += 1\n", "                        g.cnt    += (S.wait > 0 and not rev ? 0 : 1)\n"),
    ("initial distance from the pivot bar too", "if j > S.piv\n", "if j >= S.piv\n"),
    ("lower chart gets the forming bar", 'f_ltCore(1, dvB4, dvD4, ltChartOk, 1)', 'f_ltCore(1, dvB4, dvD4, ltChartOk, 0)'),
    ("1H chart delayed / lower chart early for 1H", "ltOff1 = ltChSec == 3600 ? 0 : 1", "ltOff1 = ltChSec == 3600 ? 1 : 1"),
    ("no dedupe of received blocks", "take := na(lT) or sT > lT", "take := true"),
    ("chart processes unconfirmed executions", "if barstate.isconfirmed and ltChartOk\n", "if ltChartOk\n"),
    ("one block per packet", 'string out = prevBlk == "" ? blk : blk == "" ? prevBlk : prevBlk + ";" + blk', "string out = blk"),
    ("cap drops the late approach marker", "    if lost\n        ltAppMk(r, \"検知\")\n", ""),
    ("only one detection per bar per side", "    if top\n        array.set(ltStk, 0, sk + 1)\n    else\n        array.set(ltStk, 1, sk + 1)\n", ""),
]


def run_quick(src):
    """a reduced set of the checks on a mutated source; True = all pass."""
    global SRC
    saved, saved_res = SRC, list(RESULTS)
    SRC = src
    try:
        RESULTS.clear()
        try:
            gate_static()
            for k, (tf, scale) in enumerate(zip(TF_MS, (4.0, 8.0, 16.0))):
                for seed in range(2):
                    ok, why, _, _ = compare(k, rand_tf(5000 + seed + 10 * k, 700, tf, scale))
                    check("m-ref", ok, why)
            gate_scenarios()
            gate_draw()
            gate_gap()
            gate_chart_quick()
        except Exception as ex:          # a mutation that breaks execution is caught too
            check("m-exc", False, repr(ex))
        return all(r[1] for r in RESULTS)
    finally:
        SRC = saved
        RESULTS.clear()
        RESULTS.extend(saved_res)


def gate_chart_quick():
    b5, htf, cores = build(11, days=30, scale=1.2, src=SRC)
    c15 = [b for b in agg(b5, M15) if b["T"] >= b5[0]["T"] + 10 * DAY]
    c1 = agg(b5, H1)
    for chart_ms, bars in ((M15, c15), (H1, c1)):
        ch = Chart(cores, chart_ms, src=SRC).run(bars, ticks_from=len(bars) - 40)
        rec = ch.received()
        keys = [x[0] for x in rec]
        check("m-once", len(keys) == len(set(keys)))
        for key, t, tc in rec:
            same = chart_ms == TF_MS[key[0]]
            if (same and not (t == key[5] and tc == key[6])) or (not same and t < key[6]):
                check("m-time", False, str(key))
                break
        want = {x[:6] for k in range(3) for x in det_set(cores[k]) if x[5] >= bars[0]["T"] and x[6] <= bars[-1]["T"]}
        check("m-recv", want <= {x[0][:6] for x in rec})
        check("m-rt", not getattr(ch, "rt_changed", False))


def gate_mutation():
    caught, missed = 0, []
    for name, a, b in MUTATIONS:
        if a not in SRC:
            missed.append(name + " (pattern absent)")
            continue
        if run_quick(SRC.replace(a, b, 1)):
            missed.append(name)
        else:
            caught += 1
    check(f"LT-M1 mutations caught {caught}/{len(MUTATIONS)}", not missed, str(missed))


def main():
    gate_static()
    n_ev = gate_reference()
    gate_scenarios()
    gate_chart()
    gate_forming()
    gate_gap()
    gate_draw()
    if "--no-mutation" not in sys.argv:
        gate_mutation()
    ok = 0
    for name, res, det in RESULTS:
        print(("PASS  " if res else "FAIL  ") + name + ("" if res or not det else "\n      " + str(det)[:700]))
        ok += res
    print(f"\n[LT summary] reference-compared events {n_ev}")
    print(f"{ok}/{len(RESULTS)} passed  [PINE_NOT_VERIFIED: translated Pine logic, TradingView not run]")
    return ok == len(RESULTS)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
