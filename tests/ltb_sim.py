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
  LT-K context   : (LTB-2) a resolver applies Pine's request.security rule — the expression AND every calculation it depends on
                   are evaluated in the requested context — to the source: each call's arguments and the globals they / the core
                   body / the logic functions reach are evaluated with that TF's built-ins (timeframe.in_seconds() = 14400 inside
                   "240"); the chart side with the chart's. The chart emulation is driven by those resolved values (not by
                   constants chosen here). Checks: no chart-dependent dependency, 1H never taken early on 5M / 15M, 1H chart on
                   the bar's close, 4H / D detectors update, no forming bar taken, common-range events identical; the same
                   checks run on the previous version (db654f5) must flag its defect
                   Limit: the rule is applied as documented, to global declarations and the core's arguments; TradingView's own
                   evaluation is not run
  LT-B body      : (LTB-4, 4H / D) wicks changed / removed with the same open / close -> identical events; every detection bar has
                   the reversal colour (never a doji); approach / label prices are body ends
  LT-A attrib    : the difference to the old wick version split into its causes by reducing the current file: wick -> body (equal
                   to d78ebf3 on bars without wicks), the upper band edge (only on bars with an opening gap), the pivot ties
  LT-H 1H (LTB-7): the new 1H method on hand-made 1H bars with the DEFAULT inputs, tops and mirrored bottoms, each also == the
                   independent reference Ref1: reference series / first wave (no opposite pivot, 9.99 / 10, no fallback, same-side
                   update / ignore, fixed bases), continuous data, contacts before the registration, contact counting (merged, wick
                   only, ineligible 2nd -> triple), gap 7 / 8 (3rd from the 2nd), separation 29.99 / 30 (away bars only), reversal
                   strength (body 3 / ratio 30 % / colour / body end in the band), waiting (start / later / last bar / wait end /
                   contact end), one signal per contact, nothing after the 3rd, limit / close first, 4H / D == 34db07f, only the two
                   files changed, 1H drawings (markers incl. ineligible with reasons, labels, restore after the cap)
                   (LTB-3 / LTB-6 1H gates were removed with the 1H rules they tested; LT-C / LT-B / LT-A / LT-D1 now cover 4H / D)
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

# chart.* / ticker.* built-ins (read by the request.security context resolver) translate like the other namespaces
ap.NAMESPACES.update({"chart", "ticker"})

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
               str__contains=lambda s, x: x in s, str__length=len, str__substring=lambda s, a, b=None: s[a:b],
               label__set_tooltip=lambda obj, v: setattr(obj, "tooltip", v),
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
        buf, dist = ([("h1Buf", "h1Dist"), ("dvB4", "dvD4"), ("dvBD", "dvDD")][k])
        m = re.search(r'request\.security\(ltTk, "(?:60|240|D)",\s*f_ltCore\(%d, (\w+), (\w+),' % k, self.src)
        if m:                                             # the inputs the request.security call of this TF passes
            buf, dist = m.group(1), m.group(2)
        # the detector is made as f_ltCore makes it: the arguments of its `var LtTf S = ltNew(...)` evaluated with this call's
        # k / buf / dist and the inputs (LTB-3: the 1H-only maximum-bars arguments come from this line too)
        loc = dict(k=k, buf=e[buf], dist=e[dist])
        lines = [x for _, x in ap.logical_lines(self.src)]
        # LTB-7: the 1H call (k 0) runs the 1H detector built from `var LtH S1 = ltNew1(...)` (when the source has one)
        h1 = [x for x in lines if re.match(r"var LtH\s+S1 = ltNew1\(", x)]
        self.h1 = k == 0 and bool(h1)
        if self.h1:
            m = re.search(r"ltNew1\((.*)\)", h1[0])
            self.S = e["ltNew1"](*[eval(ap.expr(a), e, loc) for a in ap.split_top(m.group(1))])
        else:
            line = next(x for x in lines if re.match(r"var LtTf\s+S\s+= ltNew\(", x))
            m = re.search(r"ltNew\((.*)\)", line)
            self.S = e["ltNew"](*[eval(ap.expr(a), e, loc) for a in ap.split_top(m.group(1))])
        self.k, self.n = k, 0
        self.blocks = []

    def step(self, b, commit=True):
        S = self.S if commit else copy.deepcopy(self.S)
        blk = self.env["ltStep1" if self.h1 else "ltStep"](S, b["o"], b["h"], b["l"], b["c"], b["T"], b["C"], self.n)
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
    if ty in ("V", "T"):
        return (ty, int(f[1]), int(f[2])) + ((f[3],) if len(f) > 3 else ())
    if ty == "C":
        return ("C", int(f[1]), int(f[2]), float(f[3]), int(f[4]), int(f[7]), int(f[8]), float(f[10]), int(f[11]),
                f[12] if len(f) > 12 else "")
    if ty == "Y":
        return ("Y", int(f[1]), f[2])
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
    """independent reference (LTB-4 body rules): every price judgement on the target bar's body top max(open, close) /
    body bottom min(open, close); invalidation on the close; reversal = the bar's colour (doji never)."""

    def __init__(self, piv, wait, buf, dist, max_on=False, max_n=0, frm=None, gap=None):
        self.N, self.wait, self.buf, self.dist = piv, wait, buf, dist
        self.max_on, self.max_n = max_on, max_n          # LTB-3 (1H): age = bars since the pivot bar (pivot = 0)
        self.frm = frm                                   # LTB-6 (1H): (bars M before the pivot, minimum width) or None
        self.gap = gap                                   # LTB-6 (1H): minimum bars from the pivot to an approach, or None
        self.bars, self.bases, self.next_id = [], [], 1
        self.events, self.act = [], []
        self.cov = {}

    def c(self, key):
        self.cov[key] = self.cov.get(key, 0) + 1

    @staticmethod
    def btop(x):
        return max(x["o"], x["c"])

    @staticmethod
    def bbot(x):
        return min(x["o"], x["c"])

    def step(self, b):
        i = len(self.bars)
        self.bars.append(b)
        out = []
        N = self.N
        bt, bb = self.btop, self.bbot
        if i >= 2 * N:
            ctr = i - N
            cb = self.bars[ctr]
            right = self.bars[ctr + 1:i + 1]
            left = self.bars[ctr - N:ctr]
            others = left + right
            skip = self.max_on and N > self.max_n          # LTB-3: limit below the pivot's right bars -> id used, not monitored
            # LTB-5: ties allowed on the left, strict on the right (the last of equal bodies is the pivot)
            is_top = all(bt(cb) >= bt(x) for x in left) and all(bt(cb) > bt(x) for x in right)
            is_bot = all(bb(cb) <= bb(x) for x in left) and all(bb(cb) < bb(x) for x in right)
            if (is_top and any(bt(cb) == bt(x) for x in left)) or (is_bot and any(bb(cb) == bb(x) for x in left)):
                self.c("left_tie_pivot")
            if is_top and not all(cb["h"] > x["h"] for x in others):  # noqa: E501
                self.c("body_pivot_not_wick_pivot")
            for side, ok_side in ((-1, is_top), (1, is_bot)):
                if not ok_side:
                    continue
                if self.frm is not None:
                    M, Wd = self.frm
                    lb = self.bars[ctr - M:ctr] if ctr - M >= 0 else None          # the M bars just before the pivot bar
                    if lb is None:
                        width_ok = False
                        self.c("frm_short_history")
                    elif side == -1:
                        width_ok = bt(cb) - min(bb(x) for x in lb) >= Wd - EPS
                    else:
                        width_ok = max(bt(x) for x in lb) - bb(cb) >= Wd - EPS
                    if not width_ok:
                        self.next_id += 1
                        self.c("frm_rejected")
                        continue
                if skip:
                    self.next_id += 1
                    self.c("max_reg_skip")
                    continue
                lvl = bt(cb) if side == -1 else bb(cb)
                move = lvl - min(bb(x) for x in right) if side == -1 else max(bt(x) for x in right) - lvl
                wick_move = lvl - min(x["l"] for x in right) if side == -1 else max(x["h"] for x in right) - lvl
                if move < self.dist - EPS <= wick_move:
                    self.c("wick_only_initial_distance")
                g = dict(id=self.next_id, side=side, lvl=lvl, pvT=cb["T"], cfT=b["T"], cfTc=b["C"], reg=i,
                         away=move >= self.dist - EPS, cnt=1, wait=False, app=None, pv=ctr)
                self.next_id += 1
                self.bases.append(g)
                out.append(("R", g["id"], side, lvl, g["pvT"], g["cfT"], g["cfTc"]))
        for g in sorted(self.bases, key=lambda x: -x["id"]):     # newest first
            if g["reg"] == i:
                self.c("skip_registration_bar")
                continue
            top = g["side"] == -1
            if self.max_on and i - g["pv"] > self.max_n:
                out.append(("T", g["id"], 1 if g["wait"] else 0))
                self.c("max_end_waiting" if g["wait"] else "max_end")
                if g["wait"] and ((b["c"] < b["o"]) if top else (b["c"] > b["o"])):
                    self.c("max_end_over_reversal")
                self.bases.remove(g)
                out.append(("E", g["id"]))
                continue
            L, buf, dist = g["lvl"], self.buf, self.dist
            edge = bt(b) if top else bb(b)                         # the body end judged for an approach
            far = bb(b) if top else bt(b)                          # the body end judged for the separation
            wick = b["h"] if top else b["l"]
            closed_beyond = b["c"] > L + buf + EPS if top else b["c"] < L - buf - EPS
            reversal = b["c"] < b["o"] if top else b["c"] > b["o"]
            in_band = L - buf - EPS <= edge <= L + buf + EPS
            end = False
            if closed_beyond:
                out.append(("V", g["id"], 1 if g["wait"] else 0))
                self.c("invalidated_waiting" if g["wait"] else "invalidated")
                if reversal:
                    self.c("invalidation_beats_reversal")
                end = True
            else:
                if (wick > L + buf + EPS) if top else (wick < L - buf - EPS):
                    self.c("wick_beyond_not_invalid")
                detect = False
                if g["wait"]:
                    if b["c"] == b["o"]:
                        self.c("doji_while_waiting")
                    if reversal:
                        detect = True
                        g["wait"] = False
                        self.c("det_later")
                        if i - g["app"] == self.wait:
                            self.c("det_last_wait_bar")
                    elif i - g["app"] >= self.wait:
                        g["wait"] = False
                        out.append(("X", g["id"]))
                        self.c(f"expired_x{g['cnt']}")
                    end = not g["wait"] and g["cnt"] >= 3
                elif g["cnt"] < 3 and in_band:
                    if not g["away"]:
                        self.c("touch_without_separation")
                    elif self.gap is not None and i - g["pv"] < self.gap:
                        g["away"] = False                         # too early: no count / wait / event, separation cleared
                        g["early"] = i
                        self.c("early_approach")
                    else:
                        g["cnt"] += 1
                        g["away"] = False
                        g["app"], g["appT"], g["appP"] = i, b["T"], edge
                        st = 1 if reversal else (0 if self.wait > 0 else 2)
                        g["wait"] = st == 0
                        if b["c"] == b["o"]:
                            self.c("doji_at_approach")
                        if reversal:
                            detect = True
                            self.c("det_app")
                        if st == 2:
                            self.c(f"expired_x{g['cnt']}")
                        out.append(("A", g["id"], g["side"], L, g["pvT"], g["cnt"], g["appT"], g["appP"], st))
                        end = not g["wait"] and g["cnt"] >= 3
                elif g["cnt"] < 3 and g["away"]:
                    if (L - buf - EPS <= wick <= L + buf + EPS) or ((wick > L + buf) if top else (wick < L - buf)):
                        self.c("wick_only_touch")
                    if (edge > L + buf + EPS) if top else (edge < L - buf - EPS):
                        self.c("body_beyond_band_no_approach")
                if detect:
                    out.append(("D", g["id"], g["side"], L, g["pvT"], g["cnt"], g["appT"], b["T"], i - g["app"]))
                    self.c(("top" if top else "bot") + f"_x{g['cnt']}")
                separated = far <= L - dist + EPS if top else far >= L + dist - EPS
                wick_sep = b["l"] <= L - dist + EPS if top else b["h"] >= L + dist - EPS
                if not end and g["app"] != i and g.get("early") != i and separated:
                    g["away"] = True
                    if g.get("early") is not None:
                        self.c("re_separated_after_early")
                elif not end and g.get("early") == i and separated:
                    self.c("early_bar_range_not_separation")
                elif not end and g["app"] != i and wick_sep and not g["away"]:
                    self.c("wick_only_separation")
                if not end and g["app"] == i and separated:
                    self.c("approach_bar_range_not_separation")
            if end:
                self.bases.remove(g)
                out.append(("E", g["id"]))
                if g["cnt"] >= 3:
                    self.c("ended_after_3rd")
        if len([e for e in out if e[0] == "D"]) >= 2:
            self.c("multi_det_same_bar")
        self.events += [(i, e) for e in out]
        self.act.append(len(self.bases))
        return out

    def run(self, bars):
        for b in bars:
            self.step(b)
        return self


PARAMS = {0: ("h1Buf", "h1Dist"), 1: ("dvB4", "dvD4"), 2: ("dvBD", "dvDD")}


def ref_for(k, ov=None):
    inp = ap.inputs(SRC)
    inp.update(ov or {})
    if k == 0:
        return Ref1(inp["h1Piv"], inp["h1Wave"], inp["h1Buf"], inp["h1Dist"], inp["h1Gap"], inp["h1Body"], inp["h1Ratio"] / 100.0,
                    inp["h1Wait"], inp["h1Max"])
    b, d = PARAMS[k]
    return Ref(inp["dvPiv"], inp["dvWait"], inp[b], inp[d])


class Ref1:
    """LTB-7 1H reference, written from the specification (not from the Pine text):
    alternating reference series of confirmed body pivots, first-wave width, contact history (wicks) from the pivot bar,
    rejection of pivots with a second contact before registration, contact count / eligibility (gap, separation by bodies),
    reversal bar strength (colour, body, ratio, body end in the band), wait window inside the contact, limit -> close -> contact."""

    def __init__(self, N, wave, buf, dist, gap, body, ratio, wait, maxn):
        self.N, self.wave, self.buf, self.dist, self.gap = N, wave, buf, dist, gap
        self.body, self.ratio, self.wait, self.maxn = body, ratio, wait, maxn
        self.bars, self.bases, self.next_id, self.series = [], [], 1, []
        self.events, self.act, self.cov = [], [], {}

    def c(self, key):
        self.cov[key] = self.cov.get(key, 0) + 1

    def touch(self, x, P):
        return x["h"] >= P - self.buf - EPS and x["l"] <= P + self.buf + EPS

    @staticmethod
    def add(s, letters):
        for ch in letters:
            if ch not in s:
                s += ch
        return s

    def reversal_fail(self, b, top, P):
        edge = max(b["o"], b["c"]) if top else min(b["o"], b["c"])
        body = abs(b["c"] - b["o"])
        rng = b["h"] - b["l"]
        out = ""
        if not (P - self.buf - EPS <= edge <= P + self.buf + EPS):
            out += "Z"
        if not ((b["c"] < b["o"]) if top else (b["c"] > b["o"])):
            out += "C"
        if body < self.body - EPS:
            out += "B"
        if rng <= 0 or body < rng * self.ratio - EPS:
            out += "R"
        return out

    def step(self, b):
        i = len(self.bars)
        self.bars.append(b)
        out = []
        N = self.N
        bt = lambda x: max(x["o"], x["c"])                                      # noqa: E731
        bb = lambda x: min(x["o"], x["c"])                                      # noqa: E731
        if i >= 2 * N:
            ctr = i - N
            cb, left, right = self.bars[ctr], self.bars[ctr - N:ctr], self.bars[ctr + 1:i + 1]
            peak = all(bt(cb) >= bt(x) for x in left) and all(bt(cb) > bt(x) for x in right)
            trough = all(bb(cb) <= bb(x) for x in left) and all(bb(cb) < bb(x) for x in right)
            for side, ok in ((-1, peak), (1, trough)):
                if not ok:
                    continue
                gid = self.next_id
                self.next_id += 1
                P = bt(cb) if side == -1 else bb(cb)
                if self.series and self.series[-1][0] == side:
                    if (P >= self.series[-1][1]) if side == -1 else (P <= self.series[-1][1]):
                        self.series[-1] = (side, P)
                        self.c("series_same_side_update")
                    else:
                        self.c("series_same_side_ignored")
                        continue
                else:
                    self.series.append((side, P))
                if len(self.series) < 2:
                    self.c("no_opposite_pivot")
                    continue
                prev = self.series[-2][1]
                width = P - prev if side == -1 else prev - P
                if width < self.wave - EPS:
                    self.c("wave_short")
                    continue
                if self.maxn < N:
                    continue
                in_c, second, sep_n, sep_x = True, False, 0, None
                for x in right:
                    if self.touch(x, P):
                        second = second or not in_c
                        in_c = True
                    else:
                        in_c = False
                        sep_n += 1
                        v = bb(x) if side == -1 else bt(x)
                        sep_x = v if sep_x is None else (min(sep_x, v) if side == -1 else max(sep_x, v))
                if second:
                    self.c("second_contact_before_registration")
                    continue
                if not in_c:
                    self.c("registered_after_leaving")
                g = dict(id=gid, side=side, P=P, pvT=cb["T"], cfT=b["T"], cfTc=b["C"], reg=i, pv=ctr, cnt=1, in_c=in_c,
                         last=ctr, sep_n=sep_n, sep_x=sep_x, elig=False, wait=False, wend=None, st=None, why="")
                self.bases.append(g)
                out.append(("R", gid, side, P, cb["T"], b["T"], b["C"]))
        for g in sorted(self.bases, key=lambda x: -x["id"]):
            if g["reg"] == i:
                continue
            top, P = g["side"] == -1, g["P"]
            end = False
            if i - g["pv"] > self.maxn:
                out.append(("T", g["id"], 1 if g["wait"] else 0, self.add(g["why"], "T")))
                self.c("limit_end_waiting" if g["wait"] else "limit_end")
                if g["wait"] and not self.reversal_fail(b, top, P) and self.touch(b, P):
                    self.c("limit_beats_reversal")
                end = True
            elif (b["c"] > P + self.buf + EPS) if top else (b["c"] < P - self.buf - EPS):
                out.append(("V", g["id"], 1 if g["wait"] else 0, self.add(g["why"], "V")))
                self.c("invalid_waiting" if g["wait"] else "invalid")
                if g["wait"] and not self.reversal_fail(b, top, P) and self.touch(b, P):
                    self.c("invalid_beats_reversal")
                end = True
            elif self.touch(b, P):
                if not g["in_c"]:
                    g["cnt"] += 1
                    g["in_c"] = True
                    gap_ok = i - g["last"] >= self.gap
                    sep_ok = g["sep_n"] > 0 and ((P - g["sep_x"] >= self.dist - EPS) if top else (g["sep_x"] - P >= self.dist - EPS))
                    why = ("" if gap_ok else "G") + ("" if sep_ok else "S")
                    g.update(elig=gap_ok and sep_ok and g["cnt"] <= 3, why=why, last=i, st=i, stT=b["T"], stP=b["h"] if top else b["l"],
                             sep_n=0, sep_x=None)
                    g["wait"] = g["elig"]
                    g["wend"] = i + self.wait
                    out.append(("C", g["id"], g["side"], P, g["pvT"], g["cnt"], b["T"], g["stP"], 1 if g["elig"] else 0, why))
                    self.c(f"contact{g['cnt']}_{'eligible' if g['elig'] else 'ineligible'}")
                    if not gap_ok:
                        self.c("gap_short")
                    if not sep_ok:
                        self.c("separation_short")
                    if g["cnt"] == 3 and not g["elig"]:
                        self.c("third_ineligible_end")
                        end = True
                    if g["cnt"] == 3 and g["elig"] and "D2" not in g:
                        self.c("third_eligible_without_double")
                if g["wait"]:
                    fail = self.reversal_fail(b, top, P)
                    if not fail:
                        g["wait"] = False
                        lag = i - g["st"]
                        out.append(("D", g["id"], g["side"], P, g["pvT"], g["cnt"], g["stT"], b["T"], lag))
                        self.c(("top" if top else "bottom") + f"_x{g['cnt']}")
                        self.c("det_on_start" if lag == 0 else ("det_last_wait_bar" if lag == self.wait else "det_later"))
                        if g["cnt"] == 2:
                            g["D2"] = True
                        if g["cnt"] >= 3:
                            end = True
                    else:
                        for ch in fail:
                            self.c("fail_" + ch)
                        if fail == "Z" or "Z" not in fail:
                            pass
                        if "Z" in fail and self.touch(b, P):
                            self.c("wick_contact_body_outside")
                        if fail in ("B", "R", "BR") and "C" not in fail:
                            self.c("right_colour_but_weak")
                        g["why"] = self.add(g["why"], fail)
                        if i >= g["wend"]:
                            g["wait"] = False
                            g["why"] = self.add(g["why"], "W")
                            out.append(("Y", g["id"], g["why"]))
                            self.c("wait_end")
                            if g["cnt"] >= 3:
                                end = True
                elif g["in_c"] and g["st"] is not None and i > g["st"]:
                    self.c("contact_continues")
            else:
                if g["in_c"]:
                    g["in_c"] = False
                    if g["wait"]:
                        g["wait"] = False
                        g["why"] = self.add(g["why"], "E")
                        out.append(("Y", g["id"], g["why"]))
                        self.c("contact_end_while_waiting")
                        if g["cnt"] >= 3:
                            end = True
                g["sep_n"] += 1
                v = min(b["o"], b["c"]) if top else max(b["o"], b["c"])
                g["sep_x"] = v if g["sep_x"] is None else (min(g["sep_x"], v) if top else max(g["sep_x"], v))
            if end:
                self.bases.remove(g)
                out.append(("E", g["id"]))
        if len([e for e in out if e[0] == "D"]) >= 2:
            self.c("multi_det_same_bar")
        self.events += [(i, e) for e in out]
        self.act.append(len(self.bases))
        return out

    def run(self, bars):
        for b in bars:
            self.step(b)
        return self


# ============================================================================
# series
# ============================================================================
def rand_tf(seed, n, tf_ms, scale, grid=None, t0=1_790_000_000_000, gaps=True, gap_p=0.05):
    rnd = random.Random(seed)
    p, out = 2000.0, []
    reg, left = 0.0, 0
    for i in range(n):
        if left <= 0:
            reg, left = rnd.choice([0.0, 0.0, 0.35, -0.35]) * scale, rnd.randint(10, 80)
        left -= 1
        jump = rnd.gauss(0, 3 * scale) if rnd.random() < gap_p else 0.0
        o = p + (jump if gaps else 0.0)                                         # occasional opening gap (gaps=False: open == close)
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
    # 1H (LTB-7): the defaults and variations of every 1H input; 4H / D: the existing settings
    s1 = [{}, dict(h1Dist=10.0), dict(h1Dist=10.0, h1Gap=4), dict(h1Dist=10.0, h1Gap=1, h1Wait=0), dict(h1Dist=5.0, h1Wait=5),
          dict(h1Dist=10.0, h1Body=0.0, h1Ratio=0.0), dict(h1Dist=10.0, h1Body=6.0, h1Ratio=60.0), dict(h1Dist=0.0, h1Gap=1),
          dict(h1Dist=10.0, h1Buf=2.0), dict(h1Dist=10.0, h1Buf=10.0), dict(h1Wave=0.0, h1Dist=10.0), dict(h1Wave=25.0, h1Dist=10.0),
          dict(h1Piv=2, h1Dist=10.0), dict(h1Piv=6, h1Dist=10.0), dict(h1Max=4, h1Dist=5.0), dict(h1Max=3), dict(h1Max=100, h1Dist=10.0),
          dict(h1Dist=10.0, h1Gap=12, h1Max=60), dict(h1Piv=1, h1Max=1, h1Dist=2.0, h1Gap=1)]
    s4 = [{}, dict(dvWait=0), dict(dvWait=1), dict(dvWait=5), dict(dvPiv=2), dict(dvPiv=6), dict(dvD4=0.0, dvDD=0.0),
          dict(dvB4=0.0, dvBD=0.0), dict(dvPiv=2, dvWait=2)]
    for k, (tf, scale) in enumerate(zip(TF_MS, (4.0, 8.0, 16.0))):
        for si, ov in enumerate(s1 if k == 0 else s4):
            for seed in range(3):
                for grid, gp in ((None, True), (0.5 if k == 0 else 1.0, True), (None, False)):
                    bars = rand_tf(1000 * k + 10 * si + seed, 900, tf, scale, grid, gaps=gp)
                    ok, why, r, d = compare(k, bars, ov)
                    n_ev += len(r.events)
                    n_det += sum(1 for _, e in r.events if e[0] == "D")
                    for kk, v in r.cov.items():
                        cov[("1H " if k == 0 else "") + kk] = cov.get(("1H " if k == 0 else "") + kk, 0) + v
                    if not ok:
                        bad.append((k, ov, seed, grid, why))
    print(f"  [LT-R] events compared {n_ev}, detections {n_det}, mismatches {len(bad)}")
    print("  [LT-R] coverage: " + ", ".join(f"{k}={v}" for k, v in sorted(cov.items())))
    check(f"LT-R1 translated Pine detectors == independent references on every event and every bar's active-base count: 1H new method "
          f"(Ref1; {len(s1)} settings incl. the defaults) and 4H / D ({len(s4)} settings) x 3 seeds x float / grid prices with opening "
          f"gaps + continuous (open == previous close)", not bad and n_det > 0, str(bad[:3]))
    need = ["top_x2", "top_x3", "bot_x2", "bot_x3", "det_app", "det_later", "det_last_wait_bar", "expired_x2", "expired_x3",
            "invalidated", "invalidated_waiting", "invalidation_beats_reversal", "skip_registration_bar", "left_tie_pivot"]
    need1 = ["top_x2", "top_x3", "bottom_x2", "bottom_x3", "det_on_start", "det_later", "det_last_wait_bar", "no_opposite_pivot",
             "wave_short", "series_same_side_update", "series_same_side_ignored", "second_contact_before_registration",
             "registered_after_leaving", "contact2_eligible", "contact2_ineligible", "contact3_eligible", "contact3_ineligible",
             "gap_short", "separation_short", "third_ineligible_end", "third_eligible_without_double", "fail_Z", "fail_C", "fail_B",
             "fail_R", "wick_contact_body_outside", "right_colour_but_weak", "wait_end", "contact_end_while_waiting", "contact_continues",
             "limit_end", "limit_end_waiting", "invalid", "invalid_waiting", "multi_det_same_bar"]
    miss = [x for x in need if cov.get(x, 0) == 0] + ["1H " + x for x in need1 if cov.get("1H " + x, 0) == 0]
    check("LT-R2 coverage on the random series: every rule occurred (1H: " + ", ".join(need1) + "; 4H / D: " + ", ".join(need) + ")",
          not miss, str(miss))
    return n_ev


# ============================================================================
# hand-made scenarios
# ============================================================================
def mk(rows, tf_ms, t0=1_790_006_400_000):
    return [dict(T=t0 + i * tf_ms, C=t0 + (i + 1) * tf_ms, o=o, h=h, l=l, c=c) for i, (o, h, l, c) in enumerate(rows)]


def mirror(rows):
    return [(4000 - o, 4000 - l, 4000 - h, 4000 - c) for o, h, l, c in rows]


def bx(o, c, up=1.0, dn=1.0):
    """one bar given by its BODY (open, close) and its wick lengths above / below the body -> (o, h, l, c)."""
    return (o, max(o, c) + up, min(o, c) - dn, c)


def top_base(H, dist, n=4):
    """LTB-4 (bodies): n bars whose body tops are below H, the peak bar (body top H, bullish, wick 3 above it), n bars whose body
    bottoms fall to H - dist - 10 (last right bar = registration bar). -> rows"""
    rows = [bx(H - 30 + i, H - 27 + i) for i in range(n)]
    rows.append(bx(H - 5, H, up=3))
    for j in range(n):
        lo = H - 6 - (dist + 4) * (j + 1) / n
        rows.append(bx(lo + 2, lo))
    return rows


class Bars:
    """the body-defined bars of the top scenarios (bottoms are their mirror): level H, buffer B, distance D."""

    def __init__(self, H, B, D):
        self.Ab = bx(H - B + 1, H - B - 2, up=B + 4)     # body top in the band, bearish (wick far above)
        self.Au = bx(H - B - 3, H - B + 0.5)             # body top in the band, bullish -> waiting
        self.Wu = bx(H - B - 3, H - B - 1.5, up=B + 3)   # body below the band (wick into it), bullish
        self.Wd = bx(H - B - 1.5, H - B - 4)             # body below the band, bearish
        self.Dj = bx(H - B + 1, H - B + 1)               # doji, body in the band
        self.Sep = bx(H - D - 8, H - D - 10)             # body bottom at H - D - 10 (re-separation), no touch
        self.Wk = bx(H - B - 2, H - B - 4, up=B + 3)     # wick only into the band, bearish
        self.Ub = bx(H + B + 1, H + B - 1)               # body top above the band, close inside (no invalidation), bearish
        self.WkSep = bx(H - 12, H - 14, dn=D)            # wick only below H - D (body bottom H - 14)


# LTB-6: the hand-made scenarios of the earlier rules (4 left bars before the pivot, approaches a few bars after it) run with the
# two 1H filters OFF; the filters have their own scenarios (gate_filters) with them ON
FOFF = dict(dvFrmOn1=False, dvGapOn1=False)


def legacy(ov=None, src=None):
    inp = ap.inputs(src or SRC)
    out = {k: v for k, v in FOFF.items() if k in inp}
    out.update(ov or {})
    return out


def evs_of(k, rows, ov=None):
    ov = legacy(ov)
    d = Det(k, ov).run(mk(rows, TF_MS[k]))
    r = ref_for(k, ov).run(mk(rows, TF_MS[k]))
    ev, _ = det_events(d)
    return ev, ev == r.events


def dets(ev, gid=1):
    return [(i, e[5], e[8]) for i, e in ev if e[0] == "D" and e[1] == gid]       # (bar, count, lag) of base gid


def kinds(ev, ty, gid=1):
    return [i for i, e in ev if e[0] == ty and e[1] == gid]


def multi_rows(H, B, D):
    """two tops (H, then H2 = H - B - 2 whose body top stays below H - buffer) both approached by one bearish body top in both bands
    and detected on the last bar."""
    H2 = H - B - 2
    rows = top_base(H, D) + [bx(H - D - 8, H - D - 10)] * 2
    rows += [bx(H - D - 8, H2 - 6), bx(H2 - 5, H2, up=2)]
    for j in range(4):
        lo = H2 - 6 - (D + 4) * (j + 1) / 4
        rows.append(bx(lo + 2, lo))
    rows += [bx(H - B + 1, H - B - 2, up=2)]
    return rows


def gate_scenarios():
    allok, det = True, []
    n = 0
    for k in (1, 2):                              # LTB-7: these are the 4H / D rules (1H: gate_h1)
        inp = ap.inputs(SRC)
        B, D = inp[PARAMS[k][0]], inp[PARAMS[k][1]]
        H = 2000.0
        base = top_base(H, D)
        R = len(base) - 1                      # registration bar index
        x = Bars(H, B, D)
        A_cnt = lambda ev: [e[5] for _, e in ev if e[0] == "A" and e[1] == 1]          # noqa: E731
        A_at = lambda ev: [i for i, e in ev if e[0] == "A" and e[1] == 1]              # noqa: E731
        R_lvl = lambda ev: [e[3] for _, e in ev if e[0] == "R" and e[1] == 1]          # noqa: E731

        def cases():
            # (name, rows, expectation(ev) -> bool); bottoms are the mirror (lvl 4000 - H)
            yield ("bearish body top in the band -> detected on the approach bar (lag 0)", base + [x.Ab],
                   lambda ev: dets(ev) == [(R + 1, 2, 0)])
            yield ("bullish approach, bearish 2 bars later -> detected there (lag 2)", base + [x.Au, x.Wu, x.Wd],
                   lambda ev: dets(ev) == [(R + 3, 2, 2)])
            yield ("bearish on the last wait bar (3rd) -> detected (lag 3)", base + [x.Au, x.Wu, x.Wu, x.Wd],
                   lambda ev: dets(ev) == [(R + 4, 2, 3)])
            yield ("no bearish through the 3rd wait bar -> expired on it, no detection (bullish bars never detect a top)",
                   base + [x.Au, x.Wu, x.Wu, x.Wu, x.Wd],
                   lambda ev: not dets(ev) and kinds(ev, "X") == [R + 4])
            yield ("wait 0: bullish approach bar -> expired at once; a later bearish bar is not a detection", base + [x.Au, x.Wd],
                   lambda ev: not dets(ev) and [e[8] for _, e in ev if e[0] == "A" and e[1] == 1] == [2])
            yield ("close above H + buffer on a bearish bar while waiting -> invalidated, not detected",
                   base + [x.Au, bx(H + B + 3, H + B + 1)],
                   lambda ev: not dets(ev) and [e for _, e in ev if e[0] == "V" and e[1] == 1] == [("V", 1, 1)])
            yield ("waiting; bearish bar closing exactly at H + buffer with a wick far above -> not invalidated, detected",
                   base + [x.Au, bx(H + B + 2, H + B, up=6)],
                   lambda ev: dets(ev) == [(R + 2, 2, 1)] and not kinds(ev, "V"))
            yield ("registration bar's body top in the band (distance met by its body) -> not an approach; next bar is",
                   base[:-1] + [bx(H - B + 1, H - D - 10)] + [x.Ab],
                   lambda ev: dets(ev) == [(R + 1, 2, 0)] and R not in A_at(ev))
            yield ("approach bar's own body reaching H - distance does not re-separate; the next touch is not a 3rd approach",
                   base + [bx(H - D - 10, H - B + 0.5), x.Wd, x.Ab, x.Ab],
                   lambda ev: A_cnt(ev) == [2] and dets(ev) == [(R + 2, 2, 1)])
            yield ("consecutive body touches without re-separation count once", base + [x.Au] * 6,
                   lambda ev: A_cnt(ev) == [2])
            yield ("2nd approach expires, re-separation, 3rd approach bearish -> triple, base ended",
                   base + [x.Au, x.Wu, x.Wu, x.Wu, x.Sep, x.Ab],
                   lambda ev: dets(ev) == [(R + 6, 3, 0)] and kinds(ev, "X") == [R + 4] and kinds(ev, "E") == [R + 6])
            yield ("double detected, re-separation, triple detected -> both, base ended on the triple", base + [x.Ab, x.Sep, x.Ab],
                   lambda ev: dets(ev) == [(R + 1, 2, 0), (R + 3, 3, 0)] and kinds(ev, "E") == [R + 3])
            T_of = lambda i: 1_790_006_400_000 + i * TF_MS[k]                                # noqa: E731
            R_H = lambda ev: [(i, e[4]) for i, e in ev if e[0] == "R" and e[3] == H]             # noqa: E731
            yield ("LTB-5 left tie (a left bar's body top equals the peak's) -> base at H, pivot bar 4, registered on bar 8",
                   [r if j != 2 else bx(H - 3, H) for j, r in enumerate(base)] + [x.Ab],
                   lambda ev: R_H(ev) == [(R, T_of(4))] and dets(ev) == [(R + 1, 2, 0)])
            yield ("LTB-5 right tie (a right bar's body top equals the peak's) -> the later bar (6) is the pivot, registered on bar 10",
                   [r if j != 6 else bx(H - 3, H) for j, r in enumerate(base)] + [x.Sep, x.Sep, x.Ab],
                   lambda ev: R_H(ev) == [(10, T_of(6))] and [i for i, e in ev if e[0] == "D" and e[3] == H] == [11])
            yield ("initial distance reached by the right bars' wicks only (bodies shallow) -> no approach",
                   base[:5] + [bx(H - 10, H - 12, dn=D + 10)] * 4 + [x.Ab] * 2,
                   lambda ev: not kinds(ev, "A") and not dets(ev))
            yield ("the pivot bar's own body (top H down to H - distance - 5) is not part of the initial distance; right bodies "
                   "shallow -> no approach",
                   base[:4] + [bx(H, H - D - 5, up=3)] + [bx(H - 10, H - 12)] * 4 + [x.Ab] * 2,
                   lambda ev: [e for _, e in ev if e[0] == "R" and e[3] == H] and not [e for _, e in ev if e[0] in ("A", "D") and e[3] == H])
            # LTB-4 body rules
            yield ("pivot by the body top: a left bar's wick above H does not prevent the base; level = body top H (not the wick)",
                   [r if j != 2 else bx(H - 27, H - 25, up=40) for j, r in enumerate(base)] + [x.Ab],
                   lambda ev: R_lvl(ev) in ([H], [4000 - H]) and dets(ev) == [(R + 1, 2, 0)])
            yield ("wick-only touches (body below the band) are no approach; the body touch after them is the 2nd",
                   base + [x.Wk, x.Wk, x.Ab],
                   lambda ev: A_at(ev) == [R + 3] and dets(ev) == [(R + 3, 2, 0)])
            yield ("body top above the band with the close inside -> no approach, no invalidation", base + [x.Ub, x.Ab],
                   lambda ev: A_at(ev) == [R + 2] and dets(ev) == [(R + 2, 2, 0)] and not kinds(ev, "V"))
            yield ("lower band edge exactly (body top = H - buffer) -> approach", base + [bx(H - B, H - B - 3)],
                   lambda ev: dets(ev) == [(R + 1, 2, 0)])
            yield ("upper band edge exactly (body top = H + buffer) -> approach", base + [bx(H + B, H - 1)],
                   lambda ev: dets(ev) == [(R + 1, 2, 0)])
            yield ("just below the lower edge (H - buffer - 0.01) -> no approach", base + [bx(H - B - 0.01, H - B - 3)],
                   lambda ev: not A_at(ev))
            yield ("just above the upper edge (H + buffer + 0.01, close inside) -> no approach, no invalidation",
                   base + [bx(H + B + 0.01, H - 1)],
                   lambda ev: not A_at(ev) and not kinds(ev, "V"))
            yield ("doji approach -> waiting (no detection on it), bearish next bar detects (lag 1)", base + [x.Dj, x.Wd],
                   lambda ev: [e[8] for _, e in ev if e[0] == "A" and e[1] == 1] == [0] and dets(ev) == [(R + 2, 2, 1)])
            yield ("doji while waiting is no reversal; bearish after it detects (lag 2)", base + [x.Au, bx(H - B - 2, H - B - 2), x.Wd],
                   lambda ev: dets(ev) == [(R + 3, 2, 2)])
            yield ("re-separation by a wick only (body bottom above H - distance) -> the next body touch is no 3rd approach",
                   base + [x.Ab, x.WkSep, x.Ab],
                   lambda ev: dets(ev) == [(R + 1, 2, 0)] and A_cnt(ev) == [2])

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
    check("LT-C1 4H / D body-rule scenarios (top and mirrored bottom, " + str(n) + " runs): lag 0 / lag 2 / last wait bar / "
          "expiry / wait 0 / invalidation beats reversal / close at the edge with a wick far beyond / registration bar skipped / "
          "approach bar body is no re-separation / consecutive touches once / 2nd expired then 3rd / double then triple / tie / "
          "wick-only initial distance / pivot by body / wick-only touch / body above the band / band edges exact and +-0.01 / "
          "doji at approach and while waiting / wick-only re-separation / several bases on one bar; each also == the reference",
          allok, str(det[:3]))


# ============================================================================
# chart simulation (request.security emulation + the translated CHART section)
# ============================================================================
def market5(seed, days, scale=1.0, gap=0.0):
    """5M bars; by default continuous: every bar opens exactly at the previous close (LTB-5: no opening gap is added to make pivots
    possible; the pivot tie rule handles it). gap > 0 adds a random opening gap (gauss, gap x scale)."""
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
            o = p + (rnd.gauss(0, gap * scale) if gap else 0.0)
            q = o + reg * scale + rnd.gauss(0, 0.9 * scale)
            out.append(dict(T=t, C=t + M5, o=o, h=max(o, q) + abs(rnd.gauss(0, .4 * scale)),
                            l=min(o, q) - abs(rnd.gauss(0, .4 * scale)), c=q))
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
    """f_ltCore inside request.security for one call: its bars in its own history order (its own instance / var state).
    on: the value the call's `on` argument takes IN THE TARGET CONTEXT (LTB-1 had one; LTB-2 has none = always computed).
    packet = the non-empty blocks of (previous bar, this bar) joined by ';' (both versions' `out` lines reduce to this; a
    changed line falls back to one block)."""

    def __init__(self, k, htf, ov=None, src=None, on=True):
        self.k, self.htf, self.ov, self.on = k, htf, ov, on
        self.det = Det(k, ov, src)
        self.outs = []
        self.pair = bool(re.search(r'string out = prevBlk == "" \? blk : (?:blk == "" \? prevBlk : )?prevBlk \+ ";" \+ blk',
                                   self.det.src))
        prev = ""
        for b in htf:
            blk = self.det.step(b) if on else ""
            self.outs.append(self._join(prev, blk))
            prev = blk
        self.starts = [b["T"] for b in htf]

    def _join(self, prev, blk):
        if not self.pair:
            return blk
        return ";".join(x for x in (prev, blk) if x != "")

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
        """request.security(lookahead_on) on a HISTORICAL chart bar starting at t: the target bar containing t (its final
        value — the lookahead), `off` bars back."""
        j = self.idx(t) - off
        return self.outs[j] if j >= 0 else None

    def partial_value(self, t, partial_bar, off):
        """realtime: off 0 -> the forming target bar computed from the partial OHLC on a copy of the state; off >= 1 -> final."""
        if off >= 1:
            return self.value(t, off)
        j = self.idx(t)
        prev = (self.det.blocks[j - 1] if j >= 1 else "") if self.on else ""
        blk = self.det.env["ltStep1" if self.det.h1 else "ltStep"](copy.deepcopy(self._state_before(j)), partial_bar["o"],
                                                                 partial_bar["h"], partial_bar["l"],
                                     partial_bar["c"], partial_bar["T"], partial_bar["C"], j) if self.on else ""
        return self._join(prev, blk)

    def _state_before(self, j):
        if not hasattr(self, "_snaps"):
            d = Det(self.k, self.ov, self.det.src)
            self._snaps = []
            for b in self.htf:
                self._snaps.append(copy.deepcopy(d.S))
                d.step(b)
        return self._snaps[j]


# ============================================================================
# request.security context resolver (LTB-2)
# ============================================================================
#  Pine evaluates a request.security expression AND every calculation it depends on in the requested context: a global
#  `x = timeframe.in_seconds()` referenced by the expression is 14400 inside "240", whatever the chart is. The resolver
#  reads the source, finds each call, and evaluates its arguments and the globals they (and the core's body / the
#  logic functions) depend on, transitively, with the context's built-ins. The chart side is evaluated with the
#  chart's built-ins. Nothing here is a constant chosen by the test.
TF_SECS = {"60": 3600, "240": 14400, "D": 86400, "15": 900, "5": 300}
CHART_BUILTINS = re.compile(r"\b(timeframe\.\w+|chart\.\w+|barstate\.\w+|syminfo\.\w+|time\b|bar_index\b)")
SEC_RE = re.compile(r'^string (\w+)\s*=\s*request\.security\((\w+), "(\w+)",\s*f_ltCore\((.*)\), lookahead = barmerge\.(\w+)\)$')


def globals_of(src):
    """level-0 declarations (name -> expression) outside types / functions; request.security results excluded."""
    out = {}
    for lvl, x in ap.logical_lines(src):
        if lvl != 0 or x.startswith(("var ", "if ", "for ", "type ", "//", "indicator(", "plot")) or "=>" in x:
            continue
        m = re.match(r"^(?:(?:int|float|bool|string|color)\s+)?([A-Za-z_]\w*)\s*=(?!=)\s*(.+)$", x)
        if m and "input." not in m.group(2) and "request.security" not in m.group(2):
            out[m.group(1)] = m.group(2)
    return out


def sec_calls(src):
    out = []
    for lvl, x in ap.logical_lines(src):
        m = SEC_RE.match(x) if lvl == 0 else None
        if m:
            out.append(dict(var=m.group(1), tick=m.group(2), tf=m.group(3), args=ap.split_top(m.group(4)), look=m.group(5)))
    return out


def core_params(src):
    m = re.search(r"^f_ltCore\(([^)]*)\) =>", src, re.M)
    return ap.param_names(m.group(1))


def core_body(src):
    i = src.index("\nf_ltCore(")
    j = src.index("\nstring ", i)
    return src[i:j]


class Ctx:
    """evaluation of source globals in one context (secs = timeframe.in_seconds() there; a standard time-based chart)."""

    def __init__(self, src, secs, inp):
        self.src, self.secs, self.inp = src, secs, inp
        self.decls = globals_of(src)
        self.cache, self.deps = {}, {}

    def env(self):
        secs = self.secs
        return dict(timeframe__in_seconds=lambda tf=None: secs if tf is None else TF_SECS[tf], timeframe__isticks=False,
                    chart__is_renko=False, chart__is_kagi=False, chart__is_pnf=False, chart__is_linebreak=False,
                    chart__is_range=False, chart__is_standard=True, _na=lambda x: x is None, _int=lambda x: None if x is None else int(x))

    def value(self, name):
        if name in self.inp:
            return self.inp[name]
        if name not in self.cache:
            e = self.decls[name]
            self.cache[name] = eval(ap.expr(e), self.env(), _Lazy(self))
        return self.cache[name]

    def eval_expr(self, e):
        try:
            return eval(ap.expr(e), self.env(), _Lazy(self))
        except Exception:
            return e                                    # not evaluable here (e.g. a ticker string) -> kept as text

    def builtins_used(self, e, seen=None):
        """chart-dependent built-ins used by an expression, transitively through the globals it references."""
        seen = set() if seen is None else seen
        out = set(CHART_BUILTINS.findall(e))
        for nm in set(re.findall(r"\b[A-Za-z_]\w*\b", e)):
            if nm in self.decls and nm not in seen:
                seen.add(nm)
                out |= self.builtins_used(self.decls[nm], seen)
        return out


class _Lazy(dict):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx

    def __getitem__(self, k):
        if k in self.ctx.inp or k in self.ctx.decls:
            return self.ctx.value(k)
        raise KeyError(k)

    def __contains__(self, k):
        return k in self.ctx.inp or k in self.ctx.decls


def resolve_calls(src, ov=None):
    """every request.security call -> its core arguments evaluated in ITS context + the chart-dependent built-ins they and the
    core body / logic functions reach (transitively)."""
    inp = ap.inputs(src)
    inp.update(ov or {})
    params = core_params(src)
    body = core_body(src) + section(src, LB, LE)
    out = []
    for c in sec_calls(src):
        cx = Ctx(src, TF_SECS[c["tf"]], inp)
        vals = {p: cx.eval_expr(a) for p, a in zip(params, c["args"])}
        used = set()
        for a in c["args"]:
            used |= cx.builtins_used(a)
        for nm in set(re.findall(r"\b[A-Za-z_]\w*\b", code_only(body))):
            if nm in cx.decls:
                used |= cx.builtins_used(cx.decls[nm])
        out.append(dict(c, vals=vals, used=sorted(used)))
    return out


class Feeds:
    """the request.security results of a source: one Core per call (own instance), on / off from the call evaluated in its
    target context. feeds[k] -> a core of TF k (detector checks)."""

    def __init__(self, htf, ov=None, src=None):
        self.src = src or SRC
        self.calls = resolve_calls(self.src, ov)
        self.items = []
        for c in self.calls:
            v = c["vals"]
            k = int(v["k"])
            core = Core(k, htf[k], ov, self.src, on=bool(v.get("on", True)))
            self.items.append(dict(var=c["var"], k=k, off=int(v["off"]), core=core, look=c["look"]))

    def __getitem__(self, k):
        for it in self.items:
            if it["k"] == k and it["core"].on:
                return it["core"]
        return [it for it in self.items if it["k"] == k][0]["core"]


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
    """one chart: its bars receive every request.security result (Feeds) and run the translated CHART section; the chart-side
    globals (ltChSec, ltChartOk, ltSame1, ...) evaluated with THIS chart's built-ins."""

    def __init__(self, feeds, chart_ms, ov=None, src=None):
        self.src = src or SRC
        self.env = make_env(self.src, ov)
        self.feeds, self.chart_ms = feeds, chart_ms
        self.code = compile(ap.Translator().translate(ap.logical_lines(chart_instrument(self.src))), "<LTB chart>", "exec")
        self.blocks, self.events = [], []
        e = self.env
        e["runtime__zzblk"] = lambda k, sT: self.blocks.append((k, sT, e["time"], e["time_close"]))
        e["runtime__zzev"] = lambda k, f: self.events.append((k, tuple(f), e["time"], e["time_close"]))
        self.committed = None
        inp = ap.inputs(self.src)
        inp.update(ov or {})
        cx = Ctx(self.src, chart_ms // 1000, inp)
        sec = code_only(section(self.src, CB, CE))
        self.chart_globals = {}
        for nm in cx.decls:
            if nm not in ("EPS",) and re.search(r"\b" + nm + r"\b", sec) and nm.startswith("lt"):
                v = cx.eval_expr(cx.decls[nm])
                if not isinstance(v, str) or nm == "ltTk":
                    self.chart_globals[nm] = v
        e.update(self.chart_globals)

    def _exec(self, b, confirmed, pks):
        e = self.env
        if self.committed is not None:
            e.update(copy.deepcopy(self.committed))
        e.update(time=b["T"], time_close=b["C"], high=b["h"], low=b["l"], open=b["o"], close=b["c"], dsAtr=2.0,
                 barstate__isconfirmed=confirmed, **pks)
        exec(self.code, e)
        e["__first__"] = False
        if confirmed:
            self.committed = copy.deepcopy({k: e[k] for k in e["_VARS"]})

    def run(self, bars, ticks_from=None):
        for i, b in enumerate(bars):
            pks = {it["var"]: it["core"].value(b["T"], it["off"]) for it in self.feeds.items}
            if ticks_from is not None and i >= ticks_from:
                # realtime: unconfirmed executions; an offset-0 result is the forming target bar computed from partial OHLC
                nd = len(self.env["_draws"])
                nb, ne = len(self.blocks), len(self.events)
                for frac in (0.3, 0.7):
                    pb = dict(b, h=b["o"] + (b["h"] - b["o"]) * frac, l=b["o"] - (b["o"] - b["l"]) * frac,
                              c=b["o"] + (b["c"] - b["o"]) * frac)
                    tp = {it["var"]: it["core"].partial_value(b["T"], pb, it["off"]) for it in self.feeds.items}
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
    return b5, htf, Feeds(htf, ov, src)


def gate_chart():
    ok_eq, ok_det, ok_once, ok_time, ok_rt, ok_disp, ok_tf, ok_gap = True, True, True, True, True, True, True, True
    det = []
    n_cmp = 0
    for seed in (11, 12, 13):
        b5, htf, cores = build(seed, days=70, scale=3.0)
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
        cores_off = Feeds(htf, dict(dsTf1=False, dsMaxGrp=1))
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
        # ids are per TF: 4H / D start at 1; 1H (LTB-7: every confirmed pivot candidate consumes an id) equals the 1H reference
        # run on the 1H bars alone
        ref1 = sorted({e[1] for _, e in ref_for(0).run(htf[0]).events if e[0] == "R"})
        if any(ids[k] and ids[k][0] != 1 for k in (1, 2)) or ids[0] != ref1:
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
    check("LT-X7 TF states not mixed: the 1H detector alone == the 1H detector next to 4H / D; ids per TF (4H / D start at 1, 1H == "
          "its reference on the 1H bars alone)", ok_tf,
          str(det[:3]))
    check("LT-X8 complete data: no gap counted", ok_gap, str(det[:3]))


def gate_forming():
    """the forming target bar never yields a detection to a lower chart; on its own TF chart only the confirmed execution counts."""
    ok, det = True, []
    b5, htf, cores = build(21, days=40, scale=3.0)
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
    k = 1                                          # LTB-7: the restore test of the approach rules runs on 4H (1H: LT-H11)
    inp = ap.inputs(SRC)
    B, D = inp["dvB4"], inp["dvD4"]
    H = 2000.0
    # base A (top 2000) approaches and waits; base B (bottom far below) approaches -> with cap 1 A's drawings are removed;
    # A then detects -> A's base note, its confirmation note, approach marker and dashed line come back
    rowsA = top_base(H, D)                                                   # A: top 2000 (body), registered on bar 8
    L = 1930.0
    rows = rowsA + [bx(1958, 1955), bx(1953, 1950), bx(1948, 1945), bx(1940, L),          # B: bottom body L on bar 12
                    bx(1940, 1945), bx(1950, 1955), bx(1960, 1965), bx(1975, 1980)]       # registered on bar 16
    rows += [bx(1980, 1986), bx(1986, 1988)]
    rows += [bx(H - B - 3, H - B + 0.5)]                                     # A: 2nd approach, bullish -> waiting
    rows += [bx(L + B - 0.5, 1993)]                                          # B: body bottom in its band, bullish -> detected
    rows += [bx(1993.5, 1991)]                                               # A: bearish -> detected (lag 2)
    rows += [bx(1985, 1984)] * 2                                             # below A's 4H band (no further approach)
    t0 = 1_790_006_400_000 // DAY * DAY - 2 * H1
    htf = [mk([(2000, 2001, 1999, 2000)] * (4 * len(rows) + 8), H1, t0), mk(rows + [bx(1984, 1984)], H4, t0),
           mk([(2000, 2001, 1999, 2000)] * 8, DAY, t0)]
    cores = Feeds(htf)
    ev = det_events(cores[1].det)[0]
    chart_bars = []
    for b in htf[1]:
        for s in range(16):
            T = b["T"] + s * M15
            chart_bars.append(dict(T=T, C=T + M15, o=b["o"], h=b["h"], l=b["l"], c=b["c"]))
    ch = Chart(cores, M15, dict(dsMaxGrp=1, dsTf1=False, dsTf4=True)).run(chart_bars)
    apps = [(i, e) for i, e in ev if e[0] == "A"]
    dts = [(i, e) for i, e in ev if e[0] == "D"]
    dts = [(i, e) for i, e in dts if e[1] == 1]
    if not (len(apps) >= 2 and dts and dts[-1][1][8] == 2 and apps[1][1][1] != 1 and apps[1][0] == dts[-1][0] - 1):
        ok = False
        det.append(("scenario shape", apps, dts))
    else:
        gid = dts[-1][1][1]
        tag = f"4時間#{gid} "
        live = [d for d in ch.env["_draws"] if not d.deleted]
        dl = [d for d in ch.env["_draws"] if d.deleted]
        has = lambda pred: any(pred(d) for d in live)                     # noqa: E731
        if not has(lambda d: d.kind == "label" and d.text.startswith("基準 4時間#%d " % gid)):
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
        if not has(lambda d: d.kind == "label" and d.text.startswith("ダブルトップ 4時間") and "#%d 2回目" % gid in d.text
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
        dsrc = htf[1][dts[-1][0]]
        lab = [d for d in live if d.kind == "label" and d.text.startswith("ダブルトップ 4時間")]
        if not lab or lab[0].args[0] != dsrc["C"] or "反転の判定足 (4時間足) " not in lab[0].kw.get("tooltip", ""):
            ok = False
            det.append(("detection label position / tooltip", lab[0].args[0] if lab else None, dsrc["C"]))
    check("LT-D1 (4H) drawing cap 1: a base whose drawings were removed while waiting gets its base note, confirmation note, approach "
          "marker and dashed line back on the late detection (one marker, not two); the label sits on the receiving chart bar "
          "with the source bar's times in the tooltip", ok, str(det))

    # several detections on the same chart bar: all labels kept, stacked
    ok2, det2 = True, []
    b5, htf2, cores2 = build(12, days=70, scale=3.0)
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
    r1 = at(h1_base(), 17) + [S_OK]                # LTB-7 1H double top detected on its last bar (index 17)
    pad = 4 * len(r4) - len(r1)
    r1 = [(1950.0, 1950.0, 1950.0, 1950.0)] * pad + r1
    t0 = 1_790_006_400_000 // H4 * H4
    hx = [mk(r1 + [(1990, 1991, 1989, 1990)] * 4, H1, t0), mk(r4 + [(1990, 1991, 1989, 1990)], H4, t0),
          mk([(1950, 1951, 1949, 1950)] * 3, DAY, t0 - 22 * H1)]
    cx = Feeds(hx)
    cb = []
    for b in hx[1]:
        for s15 in range(16):
            T = b["T"] + s15 * M15
            cb.append(dict(T=T, C=T + M15, o=b["o"], h=b["h"], l=b["l"], c=b["c"]))
    chx = Chart(cx, M15, dict(dsTf4=True, dsMaxGrp=80)).run(cb)
    byx = {}
    for key, t, tc in chx.received():
        byx.setdefault(t, []).append(key)
    cross = [t for t, ks in byx.items() if len({x[0] for x in ks}) >= 2 and len(ks) >= 3]
    labx = {}
    for d in chx.env["_draws"]:
        if d.kind == "label" and re.match(r"^(ダブル|トリプル)(トップ|ボトム) ", d.text):
            labx.setdefault(d.args[0], []).append(d)
    for t in cross:
        if len(labx.get(t, [])) != len(byx[t]) or len({d.args[1] for d in labx[t]}) != len(labx[t]):
            ok2 = False
            det2.append(("cross", t, len(byx[t]), len(labx.get(t, []))))
    check("LT-D2 several detections received on the same chart bar: random series " + str(len(multi)) + " bars; constructed 1H x 1 + "
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
            if b is None or abs((max(b["o"], b["c"]) if m.group(3) == "山" else min(b["o"], b["c"])) - d.args[1]) > 1e-6:
                ok3 = False
                det3.append(("pivot note not on the real pivot bar", d.text))
    check("LT-D3 label names 'ダブルトップ 1時間' etc. only; every base note sits on the real pivot bar's open time at its body top / "
          "bottom (not the wick)",
          ok3 and names, str(det3[:3]))


# ============================================================================
# static
# ============================================================================
def code_only(src):
    return "\n".join(ap.strip_comment(x) for x in src.split("\n"))


def gate_static():
    s = code_only(SRC)
    calls = re.findall(r'string (\w+)\s*= request\.security\((\w+), "(\w+)",\s*f_ltCore\((\d), (\w+), (\w+), (\w+)\), '
                       r'lookahead = barmerge\.lookahead_on\)', s)
    ok = (len(re.findall(r"request\.security\(", s)) == 4
          and [(c[0], c[2], c[3], c[6]) for c in calls] == [("ltPk1N", "60", "0", "0"), ("ltPk1C", "60", "0", "1"),
                                                             ("ltPk4", "240", "1", "1"), ("ltPkD", "D", "2", "1")]
          and all(c[1] == "ltTk" for c in calls)
          and [c[4:6] for c in calls] == [("h1Buf", "h1Dist"), ("h1Buf", "h1Dist"), ("dvB4", "dvD4"), ("dvBD", "dvDD")]
          and "f_ltCore(int k, float buf, float dist, int off) =>" in s
          and "string ltPk1 = ltSame1 ? ltPk1N : ltPk1C" in s and "bool ltSame1   = ltChSec == 3600" in s
          and "ticker.standard(syminfo.tickerid)" in s)
    check("LT-S1 four request.security calls of f_ltCore(k, buf, dist, off) with literal offsets: 1H offset 0 and offset 1 (separate "
          "calls), 4H / D offset 1; each TF's own inputs, lookahead_on, ticker.standard; the 1H result chosen on the chart side "
          "(1H chart -> offset 0, else offset 1)", ok)
    core = s[s.index("f_ltCore(int k"):s.index("string ltPk1N")]
    logic = code_only(section(SRC, LB, LE))
    core_ll = " ".join(x for _, x in ap.logical_lines(core))
    ok2 = ("var LtTf S  = ltNew(k, dvPiv, dvWait, buf, dist)" in core_ll and
           "var LtH  S1 = ltNew1(h1Piv, h1Wave, h1Buf, h1Dist, h1Gap, h1Body, h1Ratio / 100.0, h1Wait, h1Max)" in core_ll and
           "string blk = k == 0 ? ltStep1(S1, open, high, low, close, time, time_close, bar_index) : "
           "ltStep(S, open, high, low, close, time, time_close, bar_index)" in core_ll and "out[off]" in core and
           not re.search(r"\bds\w+", core + logic) and "request.security" not in logic
           and not re.search(r"\blt(ChartOk|ChSec|Same1|TimeBar|Off1)\b|timeframe\.|chart\.", core + logic))
    check("LT-S2 the detector runs inside request.security on the target TF's own open / high / low / close / time / bar_index "
          "(var state per call), unconditionally; no display input and no chart-TF / chart-support value reaches it", ok2)
    ok3 = ("bool ltChartOk = ltTimeBar and ltChSec <= 3600" in s and "not timeframe.isticks" in s and "chart.is_renko" in s
           and "if barstate.isconfirmed and ltChartOk" in s and "このチャートには対応していません" in s and "1時間足以下" in s)
    check("LT-S3 chart support (chart side): time-based charts <= 1H only; otherwise nothing is taken / drawn and the table asks to switch", ok3)
    inp = ap.inputs(s)
    want = dict(h1Piv=4, h1Wave=10.0, h1Buf=5.0, h1Dist=30.0, h1Gap=8, h1Body=3.0, h1Ratio=30.0, h1Wait=3, h1Max=24,
                dvPiv=4, dvWait=3, dvB4=10.0, dvD4=30.0, dvBD=20.0, dvDD=60.0, dsTf1=True, dsTf4=False, dsTfD=False)
    gone = [x for x in ("dvB1", "dvD1", "dvMxOn1", "dvMxN1", "dvFrmOn1", "dvFrmN1", "dvFrmW1", "dvGapOn1", "dvGapN1") if x in inp]
    check("LT-S4 defaults: 1H Pivot 4 / first wave 10 / band +-5 / separation 30 / contact gap 8 / reversal body 3 / ratio 30 % / wait 3 / "
          "limit 24 (all editable); 4H 10 / 30, D 20 / 60, pivot 4, wait 3; display 1H ON, 4H / D OFF; the replaced 1H inputs (buffer / "
          "distance / max-bars switch / formation filter / minimum bars) are gone",
          all(inp.get(k) == v for k, v in want.items()) and not gone, str(({k: inp.get(k) for k in want}, gone)))
    ok5 = (not re.search(r"dvMxUse|dvMx0|dvB0|dvD0|最大離れ幅制限|\b15分", s) and "rMin := math.min(rMin, low)" not in s
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
    # 4H / D (the approach rules kept from LTB-6)
    ("4H/D right-side pivot ties accepted", "isH := isH and mh > array.get(S.hs, j)", "isH := isH and mh >= array.get(S.hs, j)"),
    ("4H/D left-side pivot ties rejected", "isL := isL and ml <= array.get(S.ls, j)", "isL := isL and ml < array.get(S.ls, j)"),
    ("4H/D registration bar not skipped", "            if g.aBar < bi\n                bool top = g.side == -1\n                bool fin = false\n",
     "            if g.aBar <= bi\n                bool top = g.side == -1\n                bool fin = false\n"),
    ("4H/D approach bar range re-separates", "(na(g.appBar) or g.appBar != bi) and", "true and"),
    ("4H/D reversal before invalidation", "if top ? c > g.lvl + S.buf + EPS : c < g.lvl - S.buf - EPS",
     "if (top ? c > g.lvl + S.buf + EPS : c < g.lvl - S.buf - EPS) and not (g.waiting and (top ? c < o : c > o))"),
    ("4H/D wick invalidates", "if top ? c > g.lvl + S.buf + EPS : c < g.lvl - S.buf - EPS",
     "if top ? h > g.lvl + S.buf + EPS : l < g.lvl - S.buf - EPS"),
    ("4H/D expiry one bar late", "else if bi >= g.waitEnd", "else if bi > g.waitEnd"),
    ("4H/D initial distance from the pivot bar too", "            if j > S.piv\n                rMin", "            if j >= S.piv\n                rMin"),
    ("4H/D pivot by the wick", "    array.push(S.hs, bu)\n", "    array.push(S.hs, h)\n"),
    ("4H/D approach upper band edge missing", "bu >= g.lvl - S.buf - EPS and bu <= g.lvl + S.buf + EPS", "bu >= g.lvl - S.buf - EPS"),
    ("4H/D separation by the wick", "(top ? bd <= g.lvl - S.dist + EPS : bu >= g.lvl + S.dist - EPS)",
     "(top ? l <= g.lvl - S.dist + EPS : h >= g.lvl + S.dist - EPS)"),
    ("4H/D doji counted as a reversal", "bool rev = top ? c < o : c > o", "bool rev = top ? c <= o : c >= o"),
    # 1H (LTB-7)
    ("1H a lower same-side pivot replaces the series element", "if side == -1 ? P >= S.sP : P <= S.sP", "if true"),
    ("1H wave against an older opposite pivot", "        S.aP    := S.sP\n", ""),
    ("1H first wave exactly 10 rejected", "side == -1 ? P - S.aP >= S.wave - EPS : S.aP - P >= S.wave - EPS",
     "side == -1 ? P - S.aP > S.wave + EPS : S.aP - P > S.wave + EPS"),
    ("1H second contact before the registration accepted", "            if not second\n", "            if true\n"),
    ("1H contact by the body (no wicks)", "bool ct = h >= P - S.buf - EPS and l <= P + S.buf + EPS",
     "bool ct = math.max(o, c) >= P - S.buf - EPS and math.min(o, c) <= P + S.buf + EPS"),
    ("1H contact gap 8 rejected", "bool gapOk = bi - g.lastSt >= S.gapN", "bool gapOk = bi - g.lastSt > S.gapN"),
    ("1H 3rd contact gap counted from the pivot", "                            g.lastSt  := bi\n", ""),
    ("1H separation exactly 30 rejected", "top ? P - g.sepX >= S.dist - EPS : g.sepX - P >= S.dist - EPS",
     "top ? P - g.sepX > S.dist + EPS : g.sepX - P > S.dist + EPS"),
    ("1H contact bar's own body in the separation", "                            g.cnt += 1\n                            g.inC := true\n",
     "                            g.cnt += 1\n                            g.inC := true\n                            g.sepN += 1\n"
     "                            g.sepX := na(g.sepX) ? (top ? bd : bu) : top ? math.min(g.sepX, bd) : math.max(g.sepX, bu)\n"),
    ("1H ineligible contacts not counted", "                            g.cnt += 1\n",
     "                            g.cnt += (bi - g.lastSt >= S.gapN) ? 1 : 0\n"),
    ("1H reversal body exactly 3 rejected", "if body < S.bodyMin - EPS", "if body <= S.bodyMin + EPS"),
    ("1H reversal ratio exactly 30 % rejected", "if rng <= 0 or body < rng * S.ratio - EPS", "if rng <= 0 or body <= rng * S.ratio + EPS"),
    ("1H reversal colour not required", "    if top ? not (c < o) : not (c > o)\n        w += \"C\"\n", ""),
    ("1H reversal body end: upper edge missing", "if edge < P - S.buf - EPS or edge > P + S.buf + EPS", "if edge < P - S.buf - EPS"),
    ("1H wait one bar longer", "                                if bi >= g.waitEnd\n", "                                if bi > g.waitEnd\n"),
    ("1H contact end keeps the wait", "                        if g.inC\n                            g.inC := false\n                            if g.waiting\n",
     "                        if g.inC\n                            g.inC := false\n                            if false\n"),
    ("1H two signals from one contact", "                            if fw == \"\"\n                                g.waiting := false\n",
     "                            if fw == \"\"\n"),
    ("1H ineligible 3rd does not end the base", "                            if not g.elig and g.cnt >= 3\n                                fin := true\n", ""),
    ("1H limit one bar later", "                if bi - g.pvBar > S.maxN\n", "                if bi - g.pvBar > S.maxN + 1\n"),
    ("1H limit counted from the registration bar", "                if bi - g.pvBar > S.maxN\n", "                if bi - g.aBar > S.maxN\n"),
    ("1H chart: no marker for a contact", "        else if ty == \"C\"\n", "        else if ty == \"Cx\"\n"),
    ("1H chart: reasons not shown", "    out += str.contains(w, \"G\") ? \"／間隔不足\" : \"\"\n", ""),
    # infrastructure (request.security / chart side)
    ("lower chart gets the forming 4H bar", "f_ltCore(1, dvB4, dvD4, 1)", "f_ltCore(1, dvB4, dvD4, 0)"),
    ("1H chart takes offset 1 (delayed)", "string ltPk1 = ltSame1 ? ltPk1N : ltPk1C", "string ltPk1 = ltPk1C"),
    ("lower chart takes the 1H offset 0", "string ltPk1 = ltSame1 ? ltPk1N : ltPk1C", "string ltPk1 = ltPk1N"),
    ("1H offset chosen inside the requested context (LTB-1 bug)", "f_ltCore(0, h1Buf, h1Dist, 1)", "f_ltCore(0, h1Buf, h1Dist, ltSame1 ? 0 : 1)"),
    ("4H / D detector gated by the chart support (LTB-1 bug)", "         ltStep(S, open, high, low, close, time, time_close, bar_index)",
     "         (ltChartOk ? ltStep(S, open, high, low, close, time, time_close, bar_index) : \"B,0,0,0,0,0\")"),
    ("no dedupe of received blocks", "take := na(lT) or sT > lT", "take := true"),
    ("chart processes unconfirmed executions", "if barstate.isconfirmed and ltChartOk\n", "if ltChartOk\n"),
    ("one block per packet", "string out = prevBlk == \"\" ? blk : prevBlk + \";\" + blk", "string out = blk"),
    ("cap drops the late approach / contact marker", "    if lost\n        ltAppMk(r, \"検知\")\n", ""),
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
            gate_body()
            gate_h1()
            cur = context_checks(SRC, "mutation")
            for k, v in cur.items():
                check("m-" + k, v[0], v[1])
        except Exception as ex:          # a mutation that breaks execution is caught too
            check("m-exc", False, repr(ex))
        return all(r[1] for r in RESULTS)
    finally:
        SRC = saved
        RESULTS.clear()
        RESULTS.extend(saved_res)


def gate_chart_quick():
    b5, htf, cores = build(12, days=40, scale=3.0, src=SRC)
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


# ============================================================================
# LTB-3: 1H maximum monitoring bars (from the real pivot bar, 1H bar_index)
# ============================================================================
PREV_COMMIT = "bbea6b1"          # LTB-2 (before the maximum bars; wick rules)
LTB3_COMMIT = "d78ebf3"          # LTB-3 (maximum bars; wick rules)


def prev_src(commit=PREV_COMMIT):
    return subprocess.run(["git", "show", commit + ":LongTermDoubleTripleTopBottomXAU.pine"], cwd=ROOT, capture_output=True,
                          text=True, check=True).stdout


def wickless(bars):
    """the same bars with the wicks removed: high = body top, low = body bottom (a wick rule then equals the body rule)."""
    return [dict(b, h=max(b["o"], b["c"]), l=min(b["o"], b["c"])) for b in bars]


def run_rows(rows, ov=None, k=0, src=None, times=None):
    bars = mk(rows, TF_MS[k]) if times is None else [dict(T=T, C=T + TF_MS[k], o=o, h=h, l=l, c=c)
                                                    for T, (o, h, l, c) in zip(times, rows)]
    ov = legacy(ov, src)
    d = Det(k, ov, src).run(bars)
    r = ref_for(k, ov).run(bars)
    ev, act = det_events(d)
    return ev, (ev == r.events and act == r.act), d



# ============================================================================
# LTB-4: body rules
# ============================================================================
def gate_body():
    inp = ap.inputs(SRC)
    # 6: the same open / close with only the wicks changed -> identical blocks (every event and active count), all TFs
    ok6, n6 = True, 0
    for k, (tf, scale) in ((1, (H4, 8.0)), (2, (DAY, 16.0))):           # LTB-7: 4H / D body rules (1H: gate_h1)
        for seed in range(3):
            for ov in (None, dict(dvWait=0, dvPiv=2), dict(dvWait=1)):
                bars = rand_tf(9100 + 10 * k + seed, 800, tf, scale, grid=0.5 if seed == 2 else None)
                rnd = random.Random(seed + 77 * k)
                alt = [dict(b, h=max(b["o"], b["c"]) + rnd.choice([0.0, rnd.uniform(0, 5 * scale)]),
                            l=min(b["o"], b["c"]) - rnd.choice([0.0, rnd.uniform(0, 5 * scale)])) for b in bars]
                a, b2, c3 = (Det(k, ov).run(x).blocks for x in (bars, alt, wickless(bars)))
                n6 += sum(blk.count(";") for blk in a)
                if not (a == b2 == c3):
                    ok6 = False
    check(f"LT-B6 same open / close, wicks changed at random or removed: identical blocks (every event incl. prices, active counts) on "
          f"4H / D ({n6} events)", ok6 and n6 > 0)
    # 3 / 5: colour on every detection and approach price = body end, on random series (grid prices -> dojis occur)
    ok3, n_det, n_doji, n_doji_bars = True, 0, 0, 0
    for k, (tf, scale) in ((1, (H4, 8.0)), (2, (DAY, 16.0))):           # LTB-7: 4H / D body rules (1H: gate_h1)
        for seed in range(4):
            bars = rand_tf(9300 + 10 * k + seed, 900, tf, scale, grid=0.5)
            d = Det(k).run(bars)
            n_doji_bars += sum(1 for b in bars if b["o"] == b["c"])
            for i, blk in enumerate(d.blocks):
                b = bars[i]
                for f in [x.split(",") for x in blk.split(";")[1:]]:
                    if f[0] in ("A", "D") and int(f[2]) * 0 == 0:
                        side = int(f[2])
                        if f[0] == "A":
                            ap_i = next(j for j, x in enumerate(bars) if x["T"] == int(f[8]))
                            edge = max(bars[ap_i]["o"], bars[ap_i]["c"]) if side == -1 else min(bars[ap_i]["o"], bars[ap_i]["c"])
                            lvl, buf = float(f[3]), inp[PARAMS[k][0]]
                            if float(f[10]) != edge or not (lvl - buf - EPS <= edge <= lvl + buf + EPS):
                                ok3 = False
                            if bars[ap_i]["o"] == bars[ap_i]["c"]:
                                n_doji += 1
                        else:
                            n_det += 1
                            if not ((b["c"] < b["o"]) if side == -1 else (b["c"] > b["o"])):
                                ok3 = False
                            if float(f[14]) != max(b["o"], b["c"]) or float(f[15]) != min(b["o"], b["c"]):
                                ok3 = False
    check(f"LT-B3 every detection bar is bearish for a top / bullish for a bottom (never one of the {n_doji_bars} doji bars; {n_det} "
          f"detections; {n_doji} doji approaches); every approach price = the approach bar's body top / bottom inside level +- buffer; "
          f"detection label prices = the detection bar's body ends (doji approach / waiting also in LT-C1)",
          ok3 and n_det > 0 and n_doji_bars > 0)
# ============================================================================
# LTB-5: pivot ties on continuous data + attribution of the differences to the old wick version
# ============================================================================
STRICT_PIVOT = [("isH := isH and mh >= array.get(S.hs, j)", "isH := isH and mh > array.get(S.hs, j)"),
                ("isL := isL and ml <= array.get(S.ls, j)", "isL := isL and ml < array.get(S.ls, j)")]
ONE_SIDED = [("bu >= g.lvl - S.buf - EPS and bu <= g.lvl + S.buf + EPS", "bu >= g.lvl - S.buf - EPS"),
             ("bd >= g.lvl - S.buf - EPS and bd <= g.lvl + S.buf + EPS)", "bd <= g.lvl + S.buf + EPS)")]


def variants():
    """the current file reduced step by step (text edits of the two rules, in memory):
       strict   = pivots strict on both sides (the LTB-4 rule; no left ties)
       onesided = strict + approach band without the upper edge (top: body top >= H - B only; the wick versions' form)"""
    def edit(src, pairs):
        for a, b in pairs:
            assert src.count(a) == 1, a
            src = src.replace(a, b)
        return src
    strict = edit(SRC, STRICT_PIVOT)
    return dict(current=SRC, strict=strict, onesided=edit(strict, ONE_SIDED))


def cont(closes, o0, up=1.0, dn=1.0):
    """continuous bars: each opens exactly at the previous close (the first at o0)."""
    rows, o = [], o0
    for c in closes:
        rows.append(bx(o, c, up, dn))
        o = c
    return rows


def is_cont(bars):
    return all(bars[i]["o"] == bars[i - 1]["c"] for i in range(1, len(bars)))



def gate_attrib():
    """split the difference between the old wick version (d78ebf3 on bars WITHOUT wicks) and the current file into its causes
    (the LTB-6 1H filters OFF for the current file and its reductions; they are attributed in gate_filters)."""
    V = variants()
    old3 = prev_src(LTB3_COMMIT)
    ltb4 = prev_src("0b5b683")
    rows_out = []
    ok_eq_old, ok_eq_ltb4, ok_upper_explained = True, True, True
    stats = {}
    for gaps, gp in ((True, 0.05), (True, 0.5), (False, 0.0)):
        st = dict(bars=0, d_old=0, d_onesided=0, d_strict=0, d_cur=0, diff_upper=0, diff_tie=0, R_strict=0, R_cur=0)
        for k, (tf, scale) in ((1, (H4, 8.0)), (2, (DAY, 16.0))):       # LTB-7: the 4H / D rules (1H replaced)
            for seed in range(4):
                bars = rand_tf(9500 + 10 * k + seed, 900, tf, scale, gaps=gaps, gap_p=gp or 0.05)
                o = Det(k, None, old3).run(wickless(bars))
                vo = Det(k, None, V["onesided"]).run(bars)
                vs = Det(k, None, V["strict"]).run(bars)
                vc = Det(k, None, V["current"]).run(bars)
                l4 = Det(k, None, ltb4).run(bars)
                st["bars"] += len(bars)
                ev = {nm: det_events(d)[0] for nm, d in (("o", o), ("vo", vo), ("vs", vs), ("vc", vc))}
                st["d_old"] += sum(1 for _, e in ev["o"] if e[0] == "D")
                st["d_onesided"] += sum(1 for _, e in ev["vo"] if e[0] == "D")
                st["d_strict"] += sum(1 for _, e in ev["vs"] if e[0] == "D")
                st["d_cur"] += sum(1 for _, e in ev["vc"] if e[0] == "D")
                st["R_strict"] += sum(1 for _, e in ev["vs"] if e[0] == "R")
                st["R_cur"] += sum(1 for _, e in ev["vc"] if e[0] == "R")
                if o.blocks != vo.blocks:
                    ok_eq_old = False
                if l4.blocks != vs.blocks:
                    ok_eq_ltb4 = False
                # the upper band edge: the first bar where onesided and strict differ must have, for some active separated base
                # not waiting, the judged body end beyond the band while the close stays inside (no invalidation)
                if vo.blocks != vs.blocks:
                    st["diff_upper"] += 1
                    i = next(j for j in range(len(bars)) if vo.blocks[j] != vs.blocks[j])
                    b = bars[i]
                    bt, bb = max(b["o"], b["c"]), min(b["o"], b["c"])
                    B = ap.inputs(SRC)[PARAMS[k][0]]
                    lv = [(e[2], e[3]) for _, e in ev["vs"] if e[0] == "R"]
                    if not any((bt > L + B + EPS and b["c"] <= L + B + EPS) if sd == -1 else (bb < L - B - EPS and b["c"] >= L - B - EPS)
                               for sd, L in lv):
                        ok_upper_explained = False
                if vs.blocks != vc.blocks:
                    st["diff_tie"] += 1
        stats[("gaps %d%%" % round(gp * 100)) if gaps else "continuous"] = st
    for nm, st in stats.items():
        rows_out.append(f"{nm}: {st['bars']} bars, detections old(wickless) {st['d_old']} = onesided {st['d_onesided']} -> "
                        f"+upper edge {st['d_strict']} -> +left ties {st['d_cur']}; bases strict {st['R_strict']} -> ties {st['R_cur']}; "
                        f"series changed by the upper edge {st['diff_upper']}, by the ties {st['diff_tie']}")
    print("  [LT-A] " + "\n  [LT-A] ".join(rows_out))
    check("LT-A1 wick -> body: the old wick version (d78ebf3) on the bars without wicks == the current file reduced to strict pivots + "
          "the one-sided band, block by block (gapped and continuous series, 1H / 4H / D)", ok_eq_old)
    check("LT-A2 the 'strict' reduction == LTB-4 (0b5b683) block by block (the reduction reconstructs the previous version)", ok_eq_ltb4)
    c = stats["continuous"]
    check("LT-A3 upper band edge (a separate change, not part of the body switch): every series it changes first differs on a bar whose "
          "body end passes beyond the band while the close stays inside; on continuous data it changes nothing "
          f"(gaps on 5% of bars: {stats['gaps 5%']['diff_upper']} / 12 series changed, gaps on 50%: {stats['gaps 50%']['diff_upper']} / 12, "
          f"continuous: {c['diff_upper']} / 12)",
          ok_upper_explained and c["diff_upper"] == 0 and stats["gaps 50%"]["diff_upper"] > 0)
    check(f"LT-A4 pivot ties (LTB-5): on continuous data the strict rule finds no base at all ({c['R_strict']}) and the tie rule finds "
          f"{c['R_cur']} with {c['d_cur']} detections", c["R_strict"] == 0 and c["R_cur"] > 0 and c["d_cur"] > 0)
    # constructed: a gapped bearish bar opening above the band and closing inside -> old (one-sided, wickless) detects, current not
    H, B, D = 2000.0, ap.inputs(SRC)["dvB4"], ap.inputs(SRC)["dvD4"]
    rows = top_base(H, D) + [bx(H + B + 1, H + B - 1)]
    ok5 = True
    for mir in (False, True):
        rr = mirror(rows) if mir else rows
        bars = mk(rr, H4)
        e_old = det_events(Det(1, None, old3).run(wickless(bars)))[0]
        e_cur = det_events(Det(1).run(bars))[0]
        if not (dets(e_old) == [(len(rows) - 1, 2, 0)] and not dets(e_cur)):
            ok5 = False
    check("LT-A5 constructed (needs an opening gap): bearish bar opening above H + buffer and closing inside -> the old one-sided rule "
          "(wickless) detects, the current two-sided band does not (top and bottom)", ok5)


# ============================================================================
# LTB-6: 1H formation-width filter and minimum bars to a re-approach
# ============================================================================
LTB5_COMMIT = "79f21a3"



# ============================================================================
# LTB-7: the new 1H method (hand-made 1H bars with the DEFAULT 1H inputs; bottoms = the mirror of the tops)
# ============================================================================
LTB6_COMMIT = "34db07f"
P0 = 2000.0


def h1_base(trough=1960.0, right=None):
    """trough (body bottom `trough`, bar 4) -> rise -> peak (body top 2000, bar 9; high 2001) -> right bars (registration on bar 13).
    default right side: bar 10 still touching the band (high 2000), bars 11-13 away with body bottoms 1982 / 1975 / 1968."""
    t = trough
    rows = [bx(t + 15, t + 12), bx(t + 12, t + 8), bx(t + 8, t + 5), bx(t + 5, t + 2), bx(t + 2, t)]
    rise = [t + (1998 - t) * j / 5 for j in range(1, 5)]                    # strictly above the trough, below 1995
    prev = t
    for x in rise:
        rows.append(bx(prev, x))
        prev = x
    rows.append(bx(prev, 2000))
    rows += right if right is not None else [bx(1999, 1990), bx(1990, 1982), bx(1982, 1975), bx(1975, 1968)]
    return rows


F = bx(1968, 1966)                        # away (high 1969), body bottom 1966
S_OK = bx(1998, 1994, up=3, dn=1)         # contact (high 2001), bearish, body top 1998 in the band, body 4, ratio 4 / 8
W_BULL = bx(1994, 1998, up=3, dn=1)       # contact, bullish (colour fails)
WK = bx(1992, 1988, up=4, dn=1)           # contact by the wick only (high 1996): body top 1992 below the band (Z only)
PV, REG = 9, 13


def at(rows, idx, filler=F):
    """pad rows with `filler` so the next appended bar has index idx."""
    return list(rows) + [filler] * (idx - len(rows))


def ev_lv(ev, L=P0, side=-1):
    gids = {e[1] for _, e in ev if e[0] == "R" and abs(e[3] - L) < 1e-9 and e[2] == side}
    return [(i, e) for i, e in ev if e[1] in gids]


def gate_h1():
    res, det = {}, []

    def case(name, rows, exp, ov=None, L=P0):
        ok = True
        for mir in (False, True):
            rr = mirror(rows) if mir else rows
            bars = mk(rr, H1)
            d = Det(0, ov).run(bars)
            r = ref_for(0, ov).run(bars)
            ev, act = det_events(d)
            mine = ev_lv(ev, 4000 - L if mir else L, 1 if mir else -1)
            if not (ev == r.events and act == r.act and exp(mine, ev)):
                ok = False
                det.append((name, mir, [x for x in mine if x[1][0] != "E"][:8]))
        res[name] = ok

    R_ = lambda m: [i for i, e in m if e[0] == "R"]                                      # noqa: E731
    C_ = lambda m: [(i, e[5], e[8], e[9]) for i, e in m if e[0] == "C"]                  # (bar, count, eligible, why)
    D_ = lambda m: [(i, e[5], e[8]) for i, e in m if e[0] == "D"]                        # (bar, count, lag)
    Y_ = lambda m: [(i, e[2]) for i, e in m if e[0] == "Y"]                              # noqa: E731
    base = h1_base()
    # 1 / 2 / 3 / 4: the reference series and the first wave
    rows1 = [bx(1980 + 2 * j, 1982 + 2 * j) for j in range(4)] + [bx(1988, 1990)] + base[5:]
    case("1: no opposite pivot before the peak -> no base", rows1[:5] + [bx(1990, 1991), bx(1991, 1992), bx(1992, 1993), bx(1993, 1994)] +
         base[9:] + [S_OK], lambda m, ev: not R_(m))
    case("2: first wave 9.99 (trough body bottom 1990.01) -> no base", h1_base(1990.01) + [S_OK], lambda m, ev: not R_(m))
    case("2: first wave exactly 10 (trough 1990) -> base", h1_base(1990.0) + [S_OK], lambda m, ev: R_(m) == [REG])
    case("2 (control): the 9.99 rows with the wave input 9.98 -> base (the trough pivot exists; only the width decides)",
         h1_base(1990.01) + [S_OK], lambda m, ev: R_(m) == [REG], dict(h1Wave=9.98))
    # 3: T1 1960 -> P1 1995 -> T2 1992 -> P2 2000: P2 - T2 = 8 < 10 -> no base at 2000 (no fallback to T1 = 40)
    r3 = [bx(1975, 1972), bx(1972, 1968), bx(1968, 1965), bx(1965, 1962), bx(1962, 1960),
          bx(1960, 1970), bx(1970, 1980), bx(1980, 1988), bx(1988, 1993), bx(1993, 1995),
          bx(1994.5, 1994), bx(1994, 1993.5), bx(1993.5, 1993), bx(1993, 1992.5), bx(1992.5, 1992),
          bx(1992, 1994), bx(1994, 1996), bx(1996, 1997), bx(1997, 1998), bx(1998, 2000),
          bx(1999, 1990), bx(1990, 1982), bx(1982, 1975), bx(1975, 1968), S_OK]
    case("3: P2 - T2 = 8 < 10 -> no base at 2000; no fallback to the older trough (1960, 40 $)", r3, lambda m, ev: not R_(m))
    # 4: same-side update: P1 1995 (bar 9) then P1' 2000 (bar 14) without a trough pivot between -> both bases, the first unchanged
    r4 = [bx(1975, 1972), bx(1972, 1968), bx(1968, 1965), bx(1965, 1962), bx(1962, 1960),
          bx(1960, 1970), bx(1970, 1980), bx(1980, 1988), bx(1988, 1990), bx(1990, 1995),
          bx(1994, 1990), bx(1990, 1988), bx(1988, 1989), bx(1989, 1992), bx(1992, 2000),
          bx(1999, 1990), bx(1990, 1982), bx(1982, 1975), bx(1975, 1968), F]
    def exp4(m, ev):
        r95 = [(i, e) for i, e in ev if e[0] == "R" and e[3] in (1995.0, 2005.0)]
        r00 = [(i, e) for i, e in ev if e[0] == "R" and e[3] == 2000.0]
        return [i for i, _ in r95] == [13] and [i for i, _ in r00] == [18] and r95[0][1][4] == 1_790_006_400_000 + 9 * H1
    case("4: a higher peak without a trough between updates the series -> a new base (2000, bar 18); the first base (1995, pivot bar 9) "
         "keeps its price / pivot time", r4, exp4)
    r4b = r4[:14] + [bx(1989, 1993)] + r4[15:]
    case("4: a lower peak without a trough between is not added -> no base at 1993", r4b,
         lambda m, ev: not [e for _, e in ev if e[0] == "R" and e[3] in (1993.0, 2007.0)])
    # 5: continuous data (open == previous close everywhere): tie at the peak -> pivot on the later bar, base, contact, detection
    cl = [1972, 1968, 1965, 1962, 1960, 1968, 1976, 1984, 1990, 2000, 1990, 1982, 1975, 1968,
          1966, 1965, 1966, 1972, 1980, 1990, 1999, 1995, 1990, 1985]
    rc = cont(cl, 1975)
    case("5: continuous data: peak tie (bars 9 / 10) -> pivot bar 10, base on bar 14, contact on bar 20 (bullish, waiting), bearish bar 21 "
         "detects (lag 1)", rc, lambda m, ev: R_(m) == [14] and C_(m) == [(20, 2, 1, "")] and D_(m) == [(21, 2, 1)])
    # 6: a second contact before the registration -> not adopted; contact still on at registration -> inherited
    r6 = h1_base(right=[bx(1999, 1990), bx(1990, 1985), bx(1985, 1990, up=6), bx(1990, 1975)])
    case("6: contact -> away -> contact again inside the right-side bars -> not adopted", r6 + [S_OK], lambda m, ev: not R_(m))
    r6b = h1_base(right=[bx(1999, 1990), bx(1990, 1991, up=5), bx(1991, 1990, up=5), bx(1990, 1991, up=5)])
    case("6: contact continuing through the registration bar -> base, still in the first contact (the next touching bar is no new contact)",
         at(r6b + [bx(1991, 1992, up=4)] + [bx(1992, 1960)], 18) + [S_OK],
         lambda m, ev: R_(m) == [REG] and [c[1] for c in C_(m)] == [2] and C_(m)[0][0] == 18)
    # 7 / 8 / 9: contact counting
    case("7: consecutive touching bars are one contact; after an away bar the next touch is the next contact",
         at(base, 17) + [W_BULL, W_BULL, W_BULL, W_BULL, F, F, F, F, F, W_BULL],
         lambda m, ev: [(c[0], c[1]) for c in C_(m)] == [(17, 2), (26, 3)])
    case("8: a wick-only touch counts as a contact (2nd) without a signal; the next contact is the 3rd",
         at(base, 17) + [WK, F, F, F, F, F, F, F, F] + [S_OK],
         lambda m, ev: [(c[0], c[1]) for c in C_(m)] == [(17, 2), (26, 3)] and D_(m) == [(26, 3, 0)] and Y_(m) == [(20, "ZEP")[:0] or Y_(m)[0]]
         and "Z" in Y_(m)[0][1])
    case("9: 2nd contact ineligible (gap 7) -> the next eligible contact is a TRIPLE (count 3), never shown as a double",
         at(base, 16) + [S_OK] + [F] * 8 + [S_OK],
         lambda m, ev: C_(m)[0][:3] == (16, 2, 0) and D_(m) == [(25, 3, 0)])
    # 10: gap 7 / 8, the 3rd counted from the 2nd
    case("10: 2nd contact 7 bars after the pivot -> ineligible (G)", at(base, 16) + [S_OK],
         lambda m, ev: C_(m) == [(16, 2, 0, "G")] and not D_(m))
    case("10: 2nd contact 8 bars after the pivot -> eligible, detected", at(base, 17) + [S_OK],
         lambda m, ev: C_(m) == [(17, 2, 1, "")] and D_(m) == [(17, 2, 0)])
    case("10: 3rd contact 7 bars after the 2nd (15 after the pivot) -> ineligible, base ended",
         at(base, 17) + [S_OK] + [F] * 6 + [S_OK],
         lambda m, ev: C_(m)[1] == (24, 3, 0, "G") and D_(m) == [(17, 2, 0)] and [i for i, e in m if e[0] == "E"] == [24])
    case("10: 3rd contact 8 bars after the 2nd -> eligible, triple", at(base, 17) + [S_OK] + [F] * 7 + [S_OK],
         lambda m, ev: D_(m) == [(17, 2, 0), (25, 3, 0)])
    # 11 / 12: separation measured on the away bars' bodies only
    shallow = [bx(1999, 1990), bx(1990, 1985), bx(1985, 1980), bx(1980, 1975)]       # right side, away bodies down to 1975
    bs = h1_base(right=shallow)
    case("11: separation 29.99 (away bodies down to 1970.01) -> ineligible (S)", at(bs, 17, bx(1972, 1970.01)) + [S_OK],
         lambda m, ev: C_(m) == [(17, 2, 0, "S")] and not D_(m))
    case("11: separation exactly 30 (away bodies down to 1970) -> eligible, detected", at(bs, 17, bx(1972, 1970)) + [S_OK],
         lambda m, ev: C_(m) == [(17, 2, 1, "")] and D_(m) == [(17, 2, 0)])
    case("12: the contact bar's own body (down to 1960) does not provide the separation (away bars only reach 1975)",
         at(bs, 17, bx(1980, 1976)) + [bx(1998, 1960, up=3)],
         lambda m, ev: C_(m) == [(17, 2, 0, "S")] and not D_(m))
    case("11: no away bar between the contacts -> ineligible (S)", h1_base(right=[bx(1999, 1990)] + [bx(1990, 1991, up=5)] * 3) +
         [bx(1991, 1992, up=4)] * 4 + [S_OK], lambda m, ev: not C_(m))
    # 13 / 14 / 16: reversal bar strength
    st = lambda bar: at(base, 17) + [bar, F]                                                                      # noqa: E731
    case("13: body exactly 3 and ratio exactly 30 % (range 10) -> detected", st(bx(1998, 1995, up=3, dn=4)),
         lambda m, ev: D_(m) == [(17, 2, 0)])
    case("13: body 2.99 (ratio 33 %) -> not detected (B)", st(bx(1998, 1995.01, up=3, dn=3)),
         lambda m, ev: not D_(m) and Y_(m) and "B" in Y_(m)[0][1] and "R" not in Y_(m)[0][1])
    case("13: ratio 29.99 % (body 3, range 10.004) -> not detected (R)", st(bx(1998, 1995, up=3, dn=4.004)),
         lambda m, ev: not D_(m) and Y_(m) and "R" in Y_(m)[0][1] and "B" not in Y_(m)[0][1])
    case("14: bearish but body 1 / ratio 20 % -> not detected (B, R)", st(bx(1998, 1997, up=2, dn=2)),
         lambda m, ev: not D_(m) and "B" in Y_(m)[0][1] and "R" in Y_(m)[0][1])
    case("14: doji in the band -> not detected (C)", st(bx(1998, 1998, up=3, dn=3)),
         lambda m, ev: not D_(m) and "C" in Y_(m)[0][1])
    case("16: colour / body / ratio fine but the body top below the band (wick-only contact) -> not detected (Z)", st(WK),
         lambda m, ev: not D_(m) and Y_(m)[0][1].startswith("Z"))
    case("16: body top above the band (open 2005.5, close inside) -> not detected (Z)", st(bx(2005.5, 2001, up=1, dn=1)),
         lambda m, ev: not D_(m) and "Z" in Y_(m)[0][1])
    # 15: waiting
    case("15: detection on the contact start bar (lag 0)", at(base, 17) + [S_OK], lambda m, ev: D_(m) == [(17, 2, 0)])
    case("15: detection while waiting (lag 2)", at(base, 17) + [W_BULL, W_BULL, S_OK], lambda m, ev: D_(m) == [(19, 2, 2)])
    case("15: detection on the last wait bar (lag 3)", at(base, 17) + [W_BULL] * 3 + [S_OK], lambda m, ev: D_(m) == [(20, 2, 3)])
    case("15: wait over after bar 3 (W); a strong bar on bar 4 of the same contact is not detected",
         at(base, 17) + [W_BULL] * 4 + [S_OK], lambda m, ev: not D_(m) and Y_(m) == [(20, "CW")])
    case("15: contact ended before the wait is over (E); a strong bar after leaving is not detected",
         at(base, 17) + [W_BULL, F, S_OK], lambda m, ev: Y_(m) == [(18, "CE")] and [(c[0], c[1]) for c in C_(m)] == [(17, 2), (19, 3)])
    # 17: one signal per contact, nothing after the 3rd
    case("17: two strong bars in one contact -> one detection", at(base, 17) + [S_OK, S_OK, F], lambda m, ev: D_(m) == [(17, 2, 0)])
    case("17: after the 3rd contact the base ends; a 4th touch gives nothing",
         at(base, 17) + [S_OK] + [F] * 7 + [S_OK] + [F] * 3 + [S_OK],
         lambda m, ev: D_(m) == [(17, 2, 0), (25, 3, 0)] and max(c[1] for c in C_(m)) == 3 and [i for i, e in m if e[0] == "E"] == [25])
    # 18: limit / close invalidation first
    case("18: monitoring limit (age 25) beats a reversal of a waiting contact", at(base, PV + 24) + [W_BULL, S_OK],
         lambda m, ev: not D_(m) and [(i, e[2]) for i, e in m if e[0] == "T"] == [(PV + 25, 1)])
    case("18: age 24 allowed", at(base, PV + 24) + [S_OK], lambda m, ev: D_(m) == [(PV + 24, 2, 0)])
    case("18: close above P + buffer while waiting -> invalidated (V, waiting), no detection",
         at(base, 17) + [W_BULL, bx(2001, 2006, up=1, dn=1)],
         lambda m, ev: not D_(m) and [(i, e[2], e[3]) for i, e in m if e[0] == "V"] == [(18, 1, "CV")])
    case("18: a touching bar that closes above P + buffer is invalidation, not a contact start", at(base, 17) + [bx(2002, 2006)],
         lambda m, ev: not C_(m) and [i for i, e in m if e[0] == "V"] == [17])
    # registration-related: no signal before the registration bar, monitoring from the next bar
    case("registration: a strong touching bar on the registration bar (still in the first contact) gives no signal",
         h1_base(right=[bx(1999, 1990)] + [bx(1990, 1991, up=5)] * 2 + [bx(1998, 1994, up=3)]) + [F],
         lambda m, ev: R_(m) == [REG] and not C_(m) and not D_(m))
    for nm, ok in res.items():
        check("LT-H " + nm, ok, str([x for x in det if x[0] == nm][:2]) if not ok else "")

    # 21: 4H / D blocks == 34db07f (LTB-6) on random series and on the chart; 22: protected files
    prev = prev_src(LTB6_COMMIT)
    ok21, n21 = True, 0
    for k, (tf, scale) in ((1, (H4, 8.0)), (2, (DAY, 16.0))):
        for seed in range(4):
            for gp in (True, False):
                bars = rand_tf(9800 + 10 * k + seed, 900, tf, scale, gaps=gp)
                n21 += len(bars)
                if Det(k).run(bars).blocks != Det(k, None, prev).run(bars).blocks:
                    ok21 = False
    b5, htf, feeds_new = build(12, days=70, scale=3.0)
    feeds_prev = Feeds(htf, None, prev)
    c15 = [b for b in agg(b5, M15) if b["T"] >= b5[0]["T"] + 20 * DAY]
    ch_new = Chart(feeds_new, M15).run(c15)
    ch_prev = Chart(feeds_prev, M15, src=prev).run(c15)
    rk = lambda ch, ks: [x for x in ch.received() if x[0][0] in ks]                     # noqa: E731
    ok21 = ok21 and rk(ch_new, (1, 2)) == rk(ch_prev, (1, 2)) and [x for x in ch_new.blocks if x[0] > 0] == \
        [x for x in ch_prev.blocks if x[0] > 0] and all(feeds_new[k].outs == feeds_prev[k].outs for k in (1, 2))
    check(f"LT-H21 4H / D: every block (events + active counts) == {LTB6_COMMIT} on {n21} random bars (gapped and continuous), the "
          f"packets and the received 4H / D detections on a 15M chart", ok21)
    try:
        diff = subprocess.run(["git", "diff", "--name-only", LTB6_COMMIT, "--", "."], cwd=ROOT, capture_output=True, text=True)
        changed = sorted(x for x in diff.stdout.split() if x)
        ok22 = diff.returncode == 0 and set(changed) <= {"LongTermDoubleTripleTopBottomXAU.pine", "tests/ltb_sim.py"}
    except OSError as ex:
        ok22, changed = False, [str(ex)]
    check(f"LT-H22 only LongTermDoubleTripleTopBottomXAU.pine and tests/ltb_sim.py differ from {LTB6_COMMIT} (other indicators / "
          f"strategies / Zone / orders unchanged)", ok22, str(changed))

    # 11 (drawings): contact markers incl. ineligible ones with reasons, detection label wording, restore after the cap
    hx = [mk(at(base, 16) + [S_OK] + [F] * 8 + [S_OK, F], H1), mk([(1950, 1951, 1949, 1950)] * 3, H4),
          mk([(1950, 1951, 1949, 1950)] * 2, DAY)]
    fx = Feeds(hx)
    cb = []
    for b in hx[0]:
        for q in range(4):
            T = b["T"] + q * M15
            cb.append(dict(T=T, C=T + M15, o=b["o"], h=b["h"], l=b["l"], c=b["c"]))
    ch = Chart(fx, M15).run(cb)
    labs = [d for d in ch.env["_draws"] if d.kind == "label"]
    mk2 = [d for d in labs if d.text.startswith("1時間#") and "2回目" in d.text and d.kw.get("style") == "diamond"]
    mk3 = [d for d in labs if d.text.startswith("1時間#") and "3回目" in d.text and d.kw.get("style") == "diamond"]
    lab = [d for d in labs if d.text.startswith("トリプルトップ 1時間")]
    okd = (len(mk2) == 1 and "不採用" in mk2[0].text and "間隔不足" in getattr(mk2[0], "tooltip", mk2[0].kw.get("tooltip", ""))
           and "ヒゲを含む接触" in mk2[0].kw.get("tooltip", "") and abs(mk2[0].args[1] - S_OK[1]) < 1e-9
           and len(mk3) == 1 and "検知" in mk3[0].text and len(lab) == 1 and "実体による反転検知" in lab[0].kw.get("tooltip", "")
           and abs(lab[0].args[1] - max(S_OK[0], S_OK[3])) < 1e-9 and not [d for d in labs if d.text.startswith("ダブル")])
    # restore: cap 1, A (top 2000) waiting, B (bottom 1965) starts a contact on the bar where A detects -> A's notes / marker / line back
    rows_r = list(base) + [bx(1968, 1965), bx(1966, 1972), bx(1972, 1980), bx(1980, 1988), bx(1988, 1990), W_BULL,
                           bx(1996, 1966, up=1, dn=1), F, F]
    hr = [mk(rows_r, H1), hx[1], hx[2]]
    fr = Feeds(hr)
    cr = []
    for b in hr[0]:
        for q in range(4):
            T = b["T"] + q * M15
            cr.append(dict(T=T, C=T + M15, o=b["o"], h=b["h"], l=b["l"], c=b["c"]))
    evr = det_events(fr[0].det)[0]
    chr_ = Chart(fr, M15, dict(dsMaxGrp=1)).run(cr)
    dA = [e for i, e in evr if e[0] == "D"]
    cB = [(i, e) for i, e in evr if e[0] == "C" and e[2] == 1]
    okr = bool(dA) and bool(cB) and cB[0][0] == 20
    if okr:
        gid = dA[0][1]
        live = [d for d in chr_.env["_draws"] if not d.deleted]
        dead = [d for d in chr_.env["_draws"] if d.deleted]
        tag = f"1時間#{gid} "
        okr = (any(d.kind == "label" and d.text.startswith(f"基準 1時間#{gid} 山") for d in live)
               and any(d.kind == "label" and d.text.startswith(tag) and "確定" in d.text for d in live)
               and sum(1 for d in live if d.kind == "label" and d.text.startswith(tag + "2回目")) == 1
               and any(d.kind == "line" and d.kw.get("style") == "dashed" and d.args[2] == hr[0][19]["T"] for d in live)
               and any(d.kind == "label" and d.text.startswith(tag + "2回目") for d in dead)
               and any(d.kind == "label" and d.text.startswith("ダブルトップ 1時間") and "接触から 1 本目" in d.text for d in live))
    check("LT-H11 drawings (1H): contact markers on the contact start bar's high (also the ineligible 2nd with its reason 間隔不足 and "
          "'ヒゲを含む接触' in the tooltip); the triple label at the reversal body end with '実体による反転検知'; no double label for an "
          "ineligible 2nd; with cap 1 a base whose drawings were removed gets its notes, contact marker and line back on its detection",
          okd and okr, str((okd, okr)))


def context_checks(src, label):
    """the request.security context rule applied to `src` (resolver: each call's arguments and the globals reached by them /
    the core body / the logic functions evaluated in the requested TF; the chart side with the chart's built-ins), then the
    chart emulation driven by those resolved values. Returns {check: (ok, detail)}."""
    res = {}
    calls = resolve_calls(src)
    inp = ap.inputs(src)
    # K1 no argument / dependency of any call uses a chart-dependent built-in; its values equal in every chart context
    bad = [(c["var"], c["tf"], c["used"]) for c in calls if c["used"]]
    diffv = []
    for c in calls:
        for cs in (300, 900, 3600):
            cx = Ctx(src, cs, inp)
            chart_vals = {p: cx.eval_expr(a) for p, a in zip(core_params(src), c["args"])}
            if chart_vals != c["vals"]:
                diffv.append((c["var"], c["tf"], "chart %ds" % cs, chart_vals, "in context", c["vals"]))
                break
    res["K1"] = (not bad and not diffv, str(bad[:4]) + " " + str(diffv[:3]))
    b5, htf, feeds = build(12, days=70, scale=3.0, src=src)
    t15 = b5[0]["T"] + 10 * DAY
    t5 = b5[0]["T"] + 20 * DAY
    charts = {"1H": (H1, agg(b5, H1)), "15M": (M15, [b for b in agg(b5, M15) if b["T"] >= t15]),
              "5M": (M5, [b for b in b5 if b["T"] >= t5])}
    close_of = {(k, b["T"]): b["C"] for k in range(3) for b in htf[k]}
    k2, k3, k4, k5 = [], [], [], {}
    for nm, (ms, bars) in charts.items():
        ch = Chart(feeds, ms, src=src).run(bars, ticks_from=len(bars) - 40)
        # K2 1H results: lower chart never before the source 1H bar closed; 1H chart on that bar's confirmed execution
        for key, t, tc in ch.received():
            if key[0] != 0:
                continue
            if (ms == H1 and not (t == key[5] and tc == key[6])) or (ms != H1 and t < key[6]):
                k2.append((nm, key, t))
                break
        if not any(x[0] == 0 for x in [r[0] for r in ch.received()]):
            k2.append((nm, "no 1H detection received"))
        # K3 4H / D detectors update: every 4H / D bar that closed inside the chart's range is taken, the last one included
        for k in (1, 2):
            taken = sorted(sT for kk, sT, _, _ in ch.blocks if kk == k)
            want = [b["T"] for b in htf[k] if bars[0]["T"] <= b["C"] <= bars[-1]["T"]]
            if not want or not set(want) <= set(taken) or taken[-1] != want[-1]:
                k3.append((nm, TFJA[k], "taken %d / closed %d" % (len(taken), len(want)), taken[-1:] , want[-1:]))
        # K4 no block taken before its target bar closed (lower charts; the 1H chart takes 1H at the bar's own close)
        for kk, sT, t, tc in ch.blocks:
            C = close_of[(kk, sT)]
            if (ms == TF_MS[kk] and tc != C) or (ms != TF_MS[kk] and t < C):
                k4.append((nm, TFJA[kk], sT, t))
                break
        if getattr(ch, "rt_changed", False):
            k4.append((nm, "unconfirmed execution changed something"))
        k5[nm] = sorted(x[0] for x in ch.received() if x[0][5] >= t5 and x[0][6] <= charts["5M"][1][-1]["T"])
    # reference: each TF's detector run directly on that TF's bars (independent of how the source wires request.security)
    direct = [Core(k, htf[k], None, src) for k in range(3)]
    ref = sorted(x[:6] for k in range(3) for x in det_set(direct[k]) if x[5] >= t5 and x[6] <= charts["5M"][1][-1]["T"])
    res["K2"] = (not k2, str(k2[:3]))
    res["K3"] = (not k3, str(k3[:4]))
    res["K4"] = (not k4, str(k4[:3]))
    res["K5"] = (all([x[:6] for x in v] == ref for v in k5.values()) and len(ref) > 0,
                 str({nm: len(v) for nm, v in k5.items()}) + " ref %d" % len(ref))
    print(f"  [LT-K {label}] " + ", ".join(f"{c['var']}@{c['tf']}: " + ", ".join(f"{p}={v}" for p, v in c["vals"].items()
                                                                                   if p not in ("buf", "dist"))
                                            for c in calls), flush=True)
    return res


def gate_context():
    cur = context_checks(SRC, "current")
    names = {"K1": "every request.security argument, and every global reached from it / the core body / the logic functions, "
                   "uses no chart-dependent built-in; evaluated in the requested context it equals its value on 5M / 15M / 1H charts",
             "K2": "5M / 15M charts take a 1H result only on / after the source 1H bar's close; the 1H chart on that bar's confirmed "
                   "execution",
             "K3": "4H / D detectors update on 5M / 15M / 1H charts: every 4H / D bar that closed in the chart's range is taken, the "
                   "last taken bar = the last closed one",
             "K4": "no block taken before its target bar closed (forming 4H / D / 1H bars never taken; realtime ticks incl. the "
                   "forming bar's offset-0 value change nothing)",
             "K5": "original detection events (TF, pivot time, side, count, approach bar, detection bar) identical on 5M / 15M / 1H "
                   "charts on the common range and equal to the detectors"}
    for k, nm in names.items():
        check(f"LT-{k} (context resolver + chart emulation) {nm}", cur[k][0], cur[k][1])
    # the same checks on the previous version (LTB-1, db654f5) must flag the reported defect
    try:
        old = subprocess.run(["git", "show", "db654f5:LongTermDoubleTripleTopBottomXAU.pine"], cwd=ROOT, capture_output=True,
                             text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError) as ex:
        check("LT-K6 previous version flagged", False, str(ex))
        return
    o = context_checks(old, "LTB-1 db654f5")
    flagged = [k for k in ("K1", "K2", "K3", "K4", "K5") if not o[k][0]]
    print("  [LT-K LTB-1] " + "; ".join(f"{k} {'FAIL' if not o[k][0] else 'pass'}: {o[k][1][:160]}" for k in sorted(o)))
    check("LT-K6 the same checks on the previous version (db654f5) flag the defect: K1 (ltChartOk / ltOff1 evaluated in the requested "
          "context), K2 (1H offset 0 on 5M / 15M -> taken before the 1H close), K3 (4H / D detectors never run)",
          flagged[:3] == ["K1", "K2", "K3"], str(flagged))


def main():
    gate_static()
    gate_context()
    n_ev = gate_reference()
    gate_scenarios()
    gate_chart()
    gate_forming()
    gate_gap()
    gate_draw()
    gate_body()
    gate_attrib()
    gate_h1()
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
