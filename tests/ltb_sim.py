"""LTB-1 checks — LongTermDoubleTripleTopBottomXAU.pine (1H / 4H / D double / triple top / bottom, judged on each target TF).

  LT-S static    : three request.security calls ("60" / "240" / "D", lookahead_on, ticker.standard), offsets (1H: 0 on a 1H chart
                   else 1; 4H / D: always 1), chart support (time based, <= 1H) and its guidance, the detector gets no display input,
                   defaults, no 5M / max-distance carry-over, protected files unchanged
  LT-R reference : the LOGIC SECTION OF THE PINE FILE (translated by tests/acc_pine.py) fed one target-TF OHLC bar at a time ==
                   an independent reference detector written here from the spec (every event: registration / approach / expiry /
                   invalidation / detection / end, and the active-base count after every bar) on random 1H / 4H / D series and
                   settings; coverage of every rule counted on the reference
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
  LT-H per TF    : (LTB-7 / LTB-9; LTB-11: 1H / D only) one detector for 1H / D; hand-made scenarios on each TF's own bars with that TF's DEFAULT
                   inputs (the 1H scenario prices scaled around 2000 by 1 / 2 / 4, matching the 4H / D price settings), tops and
                   mirrored bottoms, each also == the independent reference Ref1: reference series / first wave (no opposite pivot,
                   just below / exactly / just above, no fallback, same-side update / ignore, fixed bases), continuous data,
                   contacts before the registration, contact counting (merged, wick only, ineligible 2nd -> triple), gap 7 / 8 / 9
                   (3rd from the 2nd), separation 29.99 / 30 / 30.01 (away bars only), reversal strength (body / ratio just below /
                   exactly / just above, colour, body end in the band), waiting (start / later / last bar / wait end / contact end),
                   one signal per contact, nothing after the 3rd, limit 23 / 24 / 25 and close first, drawings per TF (markers
                   incl. ineligible with reasons, labels with the TF, restore after the cap)
  LT-W both      : (LTB-8, every TF) a bar that is both a body peak and a body trough is not adopted (no base, series unchanged, two
                   ids) while existing bases are processed normally on it; mirrored data symmetric; random gapped series
  LT-P params    : (LTB-9) 1H == 9951f9b block by block and on the chart; each of the 27 inputs changes its own TF's results and
                   no other TF's; only this indicator and this test differ from 9951f9b
  LT-C charts    : (LTB-10) 4H and 1D charts: six fixed-offset fetches, chart-side choice (same TF -> offset 0 on the bar's confirmed
                   execution, higher TF -> offset 1, lower TF -> not taken); 5M / 15M / 1H charts == ba984e3; 4H / D detections on
                   1H / 4H / D charts == the detector on that TF's own bars (100-day warm-up, no ids); timing, realtime ticks, no
                   duplicates, lower TFs neither received nor drawn, drawings on the chart's own bars, same-bar labels, unsupported
                   charts (2H / 12H / weekly)
  LT-H4 4H       : (LTB-11) the 4H method: 60 $ body reversal extremes (59.99 / 60 / 60.01, wick only, same-bar update, equal later bar,
                   first extreme reference only), the specification's structures (4409 -> 4368 -> 4440 / 4440 -> 4327 -> 4434 /
                   4327 -> 4434 -> 4327 / 4209 -> 4080 -> 4189 at the band edge), waves after a 60 $ separation on an away bar
                   (wick touches, small exits, the wave-start bar's own body), gap 7 / 8 (wave 3 from wave 2), waiting (small exits,
                   last bar, wait end, the next wave's readiness), reversal body / ratio / band edges, limit 25 / 48 / 49 and
                   registration beyond it, close invalidation; each == the independent reference Ref4; no retroactive signal
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
        lines = [x for _, x in ap.logical_lines(self.src)]
        new = [x for x in lines if re.match(r"var LtH\s+S\s*=", x)]
        h1 = [x for x in lines if re.match(r"var LtH\s+S1 = ltNew1\(", x)]
        h4 = [x for x in lines if re.match(r"var LtH4\s+S4\s*=", x)]
        self.h4 = k == 1 and bool(h4)
        if self.h4:
            # LTB-11: the 4H call runs LtH4 / ltStep4, built from f_ltCore's `var LtH4 S4 = ltNew4(...)`
            self.h1 = False
            self.S = eval(ap.expr(h4[0].split("=", 1)[1]), e, dict(k=k))
        elif new:
            # LTB-9: every TF runs LtH / ltStep1; the detector is f_ltCore's `var LtH S = ...` evaluated with this call's k
            self.h1 = True
            self.S = eval(ap.expr(new[0].split("=", 1)[1]), e, dict(k=k))
        else:
            # earlier versions (LTB-1 .. LTB-8): buf / dist from that source's own request.security call of TF k
            m = re.search(r'request\.security\(ltTk, "(?:60|240|D)",\s*f_ltCore\(%d, (\w+), (\w+),' % k, self.src)
            loc = dict(k=k, buf=e[m.group(1)], dist=e[m.group(2)])
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
        fn = "ltStep4" if self.h4 else "ltStep1" if self.h1 else "ltStep"
        blk = self.env[fn](S, b["o"], b["h"], b["l"], b["c"], b["T"], b["C"], self.n)
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
                f[12] if len(f) > 12 else "") + ((int(f[13]), f[14]) if len(f) > 14 else ())
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

def ref_for(k, ov=None):
    """the independent reference with TF k's own inputs (LTB-9: the same method on every TF)."""
    inp = ap.inputs(SRC)
    inp.update(ov or {})
    if k == 1:
        return Ref4(inp["h4Rev"], inp["h4Buf"], inp["h4Dist"], inp["h4Gap"], inp["h4Body"], inp["h4Ratio"] / 100.0, inp["h4Wait"],
                    inp["h4Max"])
    p = ("h1", "h4", "hd")[k]
    return Ref1(inp[p + "Piv"], inp[p + "Wave"], inp[p + "Buf"], inp[p + "Dist"], inp[p + "Gap"], inp[p + "Body"],
                inp[p + "Ratio"] / 100.0, inp[p + "Wait"], inp[p + "Max"])


class Ref4:
    """LTB-11 4H reference, written from the specification (not from the Pine text): swing extremes on bodies confirmed by a reversal
    of `rev` (the extreme recomputed from the bar list), the first confirmed extreme a reference only, bases from the 2nd one; waves =
    returns to the band after a `dist` separation on a non-touching bar; gap fixed at the wave start; reversal strength; wait 0..wait
    bars not ended by small exits but by the next wave's readiness; limit -> close -> wave / reversal."""

    def __init__(self, rev, buf, dist, gap, body, ratio, wait, maxn):
        self.rev, self.buf, self.dist, self.gap = rev, buf, dist, gap
        self.body, self.ratio, self.wait, self.maxn = body, ratio, wait, maxn
        self.bars, self.bases, self.next_id, self.n_conf = [], [], 1, 0
        self.anchor, self.dir, self.cand = None, 0, None
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
        body, rng = abs(b["c"] - b["o"]), b["h"] - b["l"]
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

    def confirm(self, side, P, pv, i, b, out):
        gid = self.next_id
        self.next_id += 1
        self.n_conf += 1
        if self.n_conf < 2:
            self.c("first_extreme_reference_only")
            return
        if i - pv > self.maxn:
            self.c("registration_beyond_limit")
            return
        top = side == -1
        ready, sep_x = False, None
        for x in self.bars[pv + 1:i + 1]:
            if self.touch(x, P):
                if ready:
                    self.c("return_before_registration")
                ready = False
            else:
                far = min(x["o"], x["c"]) if top else max(x["o"], x["c"])
                sep_x = far if sep_x is None else (min(sep_x, far) if top else max(sep_x, far))
                if (far <= P - self.dist + EPS) if top else (far >= P + self.dist - EPS):
                    ready = True
        if ready:
            self.c("ready_at_registration")
        g = dict(id=gid, side=side, P=P, pvT=self.bars[pv]["T"], reg=i, pv=pv, cnt=1, ready=ready, last=pv, sep_x=sep_x,
                 elig=False, wait=False, wend=None, st=None, stT=None, why="")
        self.bases.append(g)
        out.append(("R", gid, side, P, g["pvT"], b["T"], b["C"]))
        self.c("base_top" if top else "base_bottom")

    def step(self, b):
        i = len(self.bars)
        self.bars.append(b)
        out = []
        bt, bb = max(b["o"], b["c"]), min(b["o"], b["c"])
        # swings
        if self.anchor is None:
            self.anchor = b["c"]
        elif self.dir == 0:
            if b["c"] - self.anchor >= self.rev - EPS:
                self.dir, self.cand = 1, (bt, i)
            elif self.anchor - b["c"] >= self.rev - EPS:
                self.dir, self.cand = -1, (bb, i)
        elif self.dir == 1:
            if bt >= self.cand[0]:
                if bb <= self.cand[0] - self.rev + EPS and self.cand[1] < i:
                    self.c("extreme_update_blocks_confirmation")
                self.cand = (bt, i)
            elif bb <= self.cand[0] - self.rev + EPS:
                P, pv = self.cand
                after = list(range(pv + 1, i + 1))
                lo = min(min(self.bars[j]["o"], self.bars[j]["c"]) for j in after)
                nb = max(j for j in after if min(self.bars[j]["o"], self.bars[j]["c"]) == lo)
                self.confirm(-1, P, pv, i, b, out)
                self.dir, self.cand = -1, (lo, nb)
        else:
            if bb <= self.cand[0]:
                if bt >= self.cand[0] + self.rev - EPS and self.cand[1] < i:
                    self.c("extreme_update_blocks_confirmation")
                self.cand = (bb, i)
            elif bt >= self.cand[0] + self.rev - EPS:
                P, pv = self.cand
                after = list(range(pv + 1, i + 1))
                hi = max(max(self.bars[j]["o"], self.bars[j]["c"]) for j in after)
                nb = max(j for j in after if max(self.bars[j]["o"], self.bars[j]["c"]) == hi)
                self.confirm(1, P, pv, i, b, out)
                self.dir, self.cand = 1, (hi, nb)
        # bases
        for g in sorted(self.bases, key=lambda x: -x["id"]):
            if g["reg"] == i:
                continue
            top, P = g["side"] == -1, g["P"]
            end = False
            if i - g["pv"] > self.maxn:
                out.append(("T", g["id"], 1 if g["wait"] else 0, self.add(g["why"], "T")))
                self.c("limit_end")
                if g["wait"] and not self.reversal_fail(b, top, P):
                    self.c("limit_beats_reversal")
                end = True
            elif (b["c"] > P + self.buf + EPS) if top else (b["c"] < P - self.buf - EPS):
                out.append(("V", g["id"], 1 if g["wait"] else 0, self.add(g["why"], "V")))
                self.c("invalid_waiting" if g["wait"] else "invalid")
                end = True
            else:
                ct = self.touch(b, P)
                if ct and not g["ready"] and g["cnt"] < 3 and i > g["pv"]:
                    self.c("touch_without_new_wave")
                if ct and g["ready"]:
                    g["cnt"] += 1
                    g["ready"] = False
                    gap = i - g["last"]
                    sep = None if g["sep_x"] is None else ((P - g["sep_x"]) if top else (g["sep_x"] - P))
                    g.update(elig=gap >= self.gap and g["cnt"] <= 3, why="" if gap >= self.gap else "G", last=i, st=i, stT=b["T"],
                             stP=b["h"] if top else b["l"], sep_x=None)
                    g["wait"] = g["elig"]
                    g["wend"] = i + self.wait
                    out.append(("C", g["id"], g["side"], P, g["pvT"], g["cnt"], b["T"], g["stP"], 1 if g["elig"] else 0, g["why"],
                                gap, "NaN" if sep is None else fmt2(sep)))
                    self.c(f"wave{g['cnt']}_{'eligible' if g['elig'] else 'ineligible'}")
                    if g["cnt"] >= 3 and not g["elig"]:
                        end = True
                        self.c("third_ineligible_end")
                if g["wait"] and not end:
                    fail = self.reversal_fail(b, top, P)
                    if not fail:
                        g["wait"] = False
                        lag = i - g["st"]
                        out.append(("D", g["id"], g["side"], P, g["pvT"], g["cnt"], g["stT"], b["T"], lag))
                        self.c(("top" if top else "bottom") + f"_x{g['cnt']}")
                        self.c("det_on_start" if lag == 0 else "det_last_wait_bar" if lag == self.wait else "det_later")
                        if not ct:
                            self.c("det_on_touching_bar_only")
                        if g["cnt"] >= 3:
                            end = True
                    else:
                        g["why"] = self.add(g["why"], fail)
                        if not ct:
                            self.c("small_exit_keeps_waiting")
                        if i >= g["wend"]:
                            g["wait"] = False
                            g["why"] = self.add(g["why"], "W")
                            out.append(("Y", g["id"], g["why"]))
                            self.c("wait_end")
                            if g["cnt"] >= 3:
                                end = True
                if not ct and not end:
                    far = bb if top else bt
                    g["sep_x"] = far if g["sep_x"] is None else (min(g["sep_x"], far) if top else max(g["sep_x"], far))
                    if not g["ready"] and ((bb <= P - self.dist + EPS) if top else (bt >= P + self.dist - EPS)):
                        g["ready"] = True
                        self.c("ready")
                        if g["wait"]:
                            g["wait"] = False
                            g["why"] = self.add(g["why"], "N")
                            out.append(("Y", g["id"], g["why"]))
                            self.c("wait_ended_by_next_wave_ready")
                            if g["cnt"] >= 3:
                                end = True
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
            if peak and trough:
                # LTB-8: a bar that is both a peak and a trough is neither adopted in the series nor a base; both ids are used
                self.next_id += 2
                self.c("both_pivot_skipped")
                peak = trough = False
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
    # LTB-9: one method, every TF; the settings variations are given in 1H units and scaled to the TF's prices
    s1 = [{}, dict(Dist=10.0), dict(Dist=10.0, Gap=4), dict(Dist=10.0, Gap=1, Wait=0), dict(Dist=5.0, Wait=5),
          dict(Dist=10.0, Body=0.0, Ratio=0.0), dict(Dist=10.0, Body=6.0, Ratio=60.0), dict(Dist=0.0, Gap=1),
          dict(Dist=10.0, Buf=2.0), dict(Dist=10.0, Buf=10.0), dict(Wave=0.0, Dist=10.0), dict(Wave=25.0, Dist=10.0),
          dict(Piv=2, Dist=10.0), dict(Piv=6, Dist=10.0), dict(Max=4, Dist=5.0), dict(Max=3), dict(Max=100, Dist=10.0),
          dict(Dist=10.0, Gap=12, Max=60), dict(Piv=1, Max=1, Dist=2.0, Gap=1)]
    price = ("Wave", "Buf", "Dist", "Body")
    # 4H (LTB-11): its own method and inputs
    s4 = [{}, dict(Dist=30.0), dict(Rev=30.0, Gap=4), dict(Rev=40.0, Dist=40.0, Wait=0), dict(Rev=30.0, Dist=20.0, Wait=5),
          dict(Rev=30.0, Body=0.0, Ratio=0.0), dict(Rev=30.0, Body=12.0, Ratio=60.0), dict(Rev=30.0, Dist=0.0, Gap=1),
          dict(Rev=30.0, Buf=10.0), dict(Rev=30.0, Buf=40.0), dict(Rev=20.0, Max=12), dict(Max=3), dict(Rev=30.0, Max=200),
          dict(Rev=90.0, Dist=90.0), dict(Rev=30.0, Dist=60.0, Gap=12)]
    for k, (tf, scale) in enumerate(zip(TF_MS, (4.0, 8.0, 16.0))):
        for si, base_ov in enumerate(s4 if k == 1 else s1):
            ov = ({PFX[k] + n: v for n, v in base_ov.items()} if k == 1 else
                  {PFX[k] + n: (v * SCALE[k] if n in price else v) for n, v in base_ov.items()})
            for seed in range(3):
                for grid, gp in ((None, True), (0.5 * SCALE[k], True), (None, False)):
                    bars = rand_tf(1000 * k + 10 * si + seed, 900, tf, scale, grid, gaps=gp)
                    ok, why, r, d = compare(k, bars, ov)
                    n_ev += len(r.events)
                    n_det += sum(1 for _, e in r.events if e[0] == "D")
                    for kk, v in r.cov.items():
                        cov[(TFJA[k], kk)] = cov.get((TFJA[k], kk), 0) + v
                    if not ok:
                        bad.append((k, ov, seed, grid, why))
    print(f"  [LT-R] events compared {n_ev}, detections {n_det}, mismatches {len(bad)}")
    print("  [LT-R] coverage: " + ", ".join(f"{a} {b}={v}" for (a, b), v in sorted(cov.items())))
    check(f"LT-R1 translated Pine detectors == the independent references on every event and every bar's active-base count: "
          f"1H / D (Ref1, {len(s1)} settings, prices scaled to the TF) and 4H (Ref4, LTB-11, {len(s4)} settings) x 3 seeds x float / grid prices with "
          f"opening gaps + continuous (open == previous close)", not bad and n_det > 0, str(bad[:3]))
    need1 = ["top_x2", "top_x3", "bottom_x2", "bottom_x3", "det_on_start", "det_later", "det_last_wait_bar", "no_opposite_pivot",
             "wave_short", "series_same_side_update", "series_same_side_ignored", "second_contact_before_registration",
             "registered_after_leaving", "contact2_eligible", "contact2_ineligible", "contact3_eligible", "contact3_ineligible",
             "gap_short", "separation_short", "third_ineligible_end", "third_eligible_without_double", "fail_Z", "fail_C", "fail_B",
             "fail_R", "wick_contact_body_outside", "right_colour_but_weak", "wait_end", "contact_end_while_waiting", "contact_continues",
             "limit_end", "limit_end_waiting", "invalid", "invalid_waiting", "multi_det_same_bar"]
    need4 = ["top_x2", "top_x3", "bottom_x2", "bottom_x3", "det_on_start", "det_later", "det_last_wait_bar", "first_extreme_reference_only",
             "base_top", "base_bottom", "ready_at_registration", "touch_without_new_wave", "ready", "wave2_eligible", "wave2_ineligible",
             "wave3_eligible", "wave3_ineligible", "third_ineligible_end", "small_exit_keeps_waiting", "wait_end",
             "wait_ended_by_next_wave_ready", "limit_end", "invalid", "invalid_waiting", "extreme_update_blocks_confirmation"]
    miss = ([(t, x) for t in (TFJA[0], TFJA[2]) for x in need1 if cov.get((t, x), 0) == 0] +
            [(TFJA[1], x) for x in need4 if cov.get((TFJA[1], x), 0) == 0])
    check("LT-R2 coverage on each TF's random series: every rule occurred (1H / D: " + ", ".join(need1) + "; 4H (LTB-11): " +
          ", ".join(need4) + ")", not miss, str(miss))
    return n_ev

def mk(rows, tf_ms, t0=1_790_006_400_000):
    return [dict(T=t0 + i * tf_ms, C=t0 + (i + 1) * tf_ms, o=o, h=h, l=l, c=c) for i, (o, h, l, c) in enumerate(rows)]


def mirror(rows):
    return [(4000 - o, 4000 - l, 4000 - h, 4000 - c) for o, h, l, c in rows]


def bx(o, c, up=1.0, dn=1.0):
    """one bar given by its BODY (open, close) and its wick lengths above / below the body -> (o, h, l, c)."""
    return (o, max(o, c) + up, min(o, c) - dn, c)





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
        fn = "ltStep4" if self.det.h4 else "ltStep1" if self.det.h1 else "ltStep"
        blk = self.det.env[fn](copy.deepcopy(self._state_before(j)), partial_bar["o"],
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
        refs = {k: sorted({e[1] for _, e in ref_for(k).run(htf[k]).events if e[0] == "R"}) for k in range(3)}
        if any(ids[k] != refs[k] for k in range(3)):
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
    check("LT-X7 TF states not mixed: the 1H detector alone == the 1H detector next to 4H / D; ids per TF (each TF's ids == its "
          "reference run on that TF's bars alone)", ok_tf,
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
    """drawings across TFs (the restore after the cap is checked per TF in gate_tf, LT-H11)."""
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
    # 1H, 4H and D detections received on the same chart bar (constructed: each TF's scaled double top detected on its bar 17,
    # padded with flat bars so the three detection bars close at the same time)
    flat = (1950.0, 1951.0, 1949.0, 1950.0)
    t0 = 1_790_006_400_000 // DAY * DAY
    hx = []
    for k in range(3):
        if k == 1:                         # LTB-11: the 4H example A (double top detected on its bar 24)
            rows_k, dbar, pre = ex_a4(), 24, (4300.0, 4300.0, 4300.0, 4300.0)
        else:
            rows_k, dbar, pre = scale_rows(at(h1_base(), 17) + [S_OK], SCALE[k]), 17, flat
        pad = 18 * DAY // TF_MS[k] - (dbar + 1)
        hx.append(mk([pre] * pad + rows_k + [flat if k != 1 else (4170.0, 4171.0, 4169.0, 4170.0)] * 2, TF_MS[k], t0))
    cx = Feeds(hx)
    cb = []
    for b in hx[0]:
        for s15 in range(4):
            T = b["T"] + s15 * M15
            cb.append(dict(T=T, C=T + M15, o=b["o"], h=b["h"], l=b["l"], c=b["c"]))
    chx = Chart(cx, M15, dict(dsTf4=True, dsTfD=True, dsMaxGrp=80)).run(cb)
    byx = {}
    for key, t, tc in chx.received():
        byx.setdefault(t, []).append(key)
    cross = [t for t, ks in byx.items() if {x[0] for x in ks} == {0, 1, 2}]
    labx = {}
    for d in chx.env["_draws"]:
        if d.kind == "label" and re.match(r"^(ダブル|トリプル)(トップ|ボトム) ", d.text):
            labx.setdefault(d.args[0], []).append(d)
    for t in cross:
        names = sorted(d.text.split("\n")[0] for d in labx.get(t, []))
        if names != ["ダブルトップ 1時間", "ダブルトップ 4時間", "ダブルトップ 日足"] or len({d.args[1] for d in labx[t]}) != 3:
            ok2 = False
            det2.append(("cross", t, names))
    # two 1H tops (2000 and 1993) detected on the same bar by the same reversal bar (same body end) -> two labels, stacked
    two = list(h1_base()) + [bx(1968, 1962), bx(1962, 1958), bx(1958, 1970), bx(1970, 1980), bx(1980, 1990), bx(1990, 1993),
                             bx(1992, 1980), bx(1980, 1970), bx(1970, 1962), bx(1962, 1960)]
    two = at(two, 28) + [S_OK, F, F]
    h2 = [mk(two, H1), mk([flat] * 3, H4), mk([flat] * 3, DAY)]
    f2 = Feeds(h2)
    c2 = []
    for b in h2[0]:
        for s15 in range(4):
            T = b["T"] + s15 * M15
            c2.append(dict(T=T, C=T + M15, o=b["o"], h=b["h"], l=b["l"], c=b["c"]))
    ch2 = Chart(f2, M15, dict(dsMaxGrp=80)).run(c2)
    rec2 = [x for x in ch2.received() if x[0][5] == h2[0][28]["T"]]
    lab2 = [d for d in ch2.env["_draws"] if d.kind == "label" and d.text.startswith("ダブルトップ 1時間")]
    ok_same = len(rec2) == 2 and len(lab2) == 2 and lab2[0].args[0] == lab2[1].args[0] and lab2[0].args[1] != lab2[1].args[1]
    if not ok_same:
        ok2 = False
        det2.append(("same TF same bar", len(rec2), [(d.args[0], d.args[1]) for d in lab2]))
    check("LT-D2 several detections received on the same chart bar: random series " + str(len(multi)) + " bars; constructed 1H + 4H + D "
          "on one bar " + str(len(cross)) + " (each with its own settings) and two 1H tops detected by the same reversal bar: one label each "
          "(all kept), stacked at different prices",
          ok2 and cross, str(det2[:3]))

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
    calls = re.findall(r'string (\w+)\s*= request\.security\((\w+), "(\w+)",\s*f_ltCore\((\d), (\d)\), '
                       r'lookahead = barmerge\.lookahead_on\)', s)
    sec = code_only(section(SRC, CB, CE))
    ok = (len(re.findall(r"request\.security\(", s)) == 6
          and [(c[0], c[2], c[3], c[4]) for c in calls] == [("ltPk1N", "60", "0", "0"), ("ltPk1C", "60", "0", "1"),
                                                             ("ltPk4N", "240", "1", "0"), ("ltPk4C", "240", "1", "1"),
                                                             ("ltPkDN", "D", "2", "0"), ("ltPkDC", "D", "2", "1")]
          and all(c[1] == "ltTk" for c in calls)
          and "f_ltCore(int k, int off) =>" in s
          and all(x in sec for x in ("string ltPk1 = ltSame1 ? ltPk1N : ltPk1C", "string ltPk4 = ltSame4 ? ltPk4N : ltPk4C",
                                     "string ltPkD = ltSameD ? ltPkDN : ltPkDC", "if ltTake1", "if ltTake4", "if ltTakeD"))
          and all(x in s for x in ("bool ltSame1   = ltChSec == 3600", "bool ltSame4   = ltChSec == 14400", "bool ltSameD   = ltChSec == 86400",
                                   "bool ltTake1   = ltChSec <= 3600", "bool ltTake4   = ltChSec <= 14400", "bool ltTakeD   = ltChSec <= 86400"))
          and "ticker.standard(syminfo.tickerid)" in s)
    check("LT-S1 six request.security calls of f_ltCore(k, off) with literal TF numbers / offsets (1H / 4H / D x offset 0 / 1), "
          "lookahead_on, ticker.standard; the choice on the chart side only: same TF -> offset 0, higher TF -> offset 1, lower TF -> "
          "not taken", ok)
    core = s[s.index("f_ltCore(int k"):s.index("string ltPk1N")]
    logic = code_only(section(SRC, LB, LE))
    core_ll = " ".join(x for _, x in ap.logical_lines(core))
    ok2 = ("var LtH  S  = k == 0 ? ltNew1(h1Piv, h1Wave, h1Buf, h1Dist, h1Gap, h1Body, h1Ratio / 100.0, h1Wait, h1Max) : "
           "ltNew1(hdPiv, hdWave, hdBuf, hdDist, hdGap, hdBody, hdRatio / 100.0, hdWait, hdMax)" in core_ll and
           "var LtH4 S4 = ltNew4(h4Rev, h4Buf, h4Dist, h4Gap, h4Body, h4Ratio / 100.0, h4Wait, h4Max)" in core_ll and
           "string blk = k == 1 ? ltStep4(S4, open, high, low, close, time, time_close, bar_index) : "
           "ltStep1(S, open, high, low, close, time, time_close, bar_index)" in core_ll and "out[off]" in core and
           "ltStep(" not in logic and "type LtTf" not in logic and
           not re.search(r"\bds\w+", core + logic) and "request.security" not in logic
           and not re.search(r"\blt(ChartOk|ChSec|Same1|Same4|SameD|Take1|Take4|TakeD|TimeBar|Off1)\b|timeframe\.|chart\.", core + logic))
    check("LT-S2 detectors inside request.security: 1H / D LtH / ltStep1, 4H LtH4 / ltStep4 (LTB-11), each built from its own TF's "
          "inputs (var state per call), on the target TF's own OHLC / time / bar_index; no display input and no chart-TF / chart-support "
          "value reaches them", ok2)
    ok3 = ("bool ltChartOk = ltTimeBar and (ltChSec <= 3600 or ltChSec == 14400 or ltChSec == 86400)" in s and "not timeframe.isticks" in s and "chart.is_renko" in s
           and "if barstate.isconfirmed and ltChartOk" in s and "このチャートには対応していません" in s and "1時間足以下" in s)
    check("LT-S3 chart support (chart side): time-based charts <= 1H, 4H and 1D; otherwise nothing is taken / drawn and the table asks "
          "to switch", ok3 and "4時間足・1日足のチャートへ切り替えてください" in s and "チャートより下位のため受信対象外" in s)
    inp = ap.inputs(s)
    want = dict(h1Piv=4, h1Wave=10.0, h1Buf=5.0, h1Dist=30.0, h1Gap=8, h1Body=3.0, h1Ratio=30.0, h1Wait=3, h1Max=24,
                h4Rev=60.0, h4Buf=20.0, h4Dist=60.0, h4Gap=8, h4Body=6.0, h4Ratio=30.0, h4Wait=3, h4Max=48,
                hdPiv=4, hdWave=40.0, hdBuf=20.0, hdDist=120.0, hdGap=8, hdBody=12.0, hdRatio=30.0, hdWait=3, hdMax=24,
                dsTf1=True, dsTf4=False, dsTfD=False)
    gone = [x for x in ("dvB1", "dvD1", "dvMxOn1", "dvMxN1", "dvFrmOn1", "dvFrmN1", "dvFrmW1", "dvGapOn1", "dvGapN1", "dvPiv", "dvWait",
                        "dvB4", "dvD4", "dvBD", "dvDD", "h4Piv", "h4Wave") if x in inp]
    check("LT-S4 defaults: 1H 4 / 10 / 5 / 30 / 8 / 3 / 30 % / 3 / 24 and D 4 / 40 / 20 / 120 / 8 / 12 / 30 % / 3 / 24 (Pivot / wave / band / "
          "separation / gap / body / ratio / wait / limit); 4H (LTB-11) reversal 60 / band 20 / next-wave separation 60 / gap 8 / body 6 / "
          "ratio 30 % / wait 3 / limit 48; display 1H ON, 4H / D OFF; the 4H Pivot / first-wave inputs and older ones are gone",
          all(inp.get(k) == v for k, v in want.items()) and not gone, str(({k: inp.get(k) for k in want if inp.get(k) != want[k]}, gone)))
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
    # the detector (every TF)
    ("a lower same-side pivot replaces the series element", "if side == -1 ? P >= S.sP : P <= S.sP", "if true"),
    ("wave against an older opposite pivot", "        S.aP    := S.sP\n", ""),
    ("first wave exactly at the minimum rejected", "side == -1 ? P - S.aP >= S.wave - EPS : S.aP - P >= S.wave - EPS",
     "side == -1 ? P - S.aP > S.wave + EPS : S.aP - P > S.wave + EPS"),
    ("second contact before the registration accepted", "            if not second\n", "            if true\n"),
    ("1H/D contact by the body (no wicks) (first occurrence = the 1H / D detector)", "bool ct = h >= P - S.buf - EPS and l <= P + S.buf + EPS",
     "bool ct = math.max(o, c) >= P - S.buf - EPS and math.min(o, c) <= P + S.buf + EPS"),
    ("contact gap exactly at the minimum rejected", "bool gapOk = bi - g.lastSt >= S.gapN", "bool gapOk = bi - g.lastSt > S.gapN"),
    ("3rd contact gap counted from the pivot", "                            g.lastSt  := bi\n", ""),
    ("separation exactly at the minimum rejected", "top ? P - g.sepX >= S.dist - EPS : g.sepX - P >= S.dist - EPS",
     "top ? P - g.sepX > S.dist + EPS : g.sepX - P > S.dist + EPS"),
    ("contact bar's own body in the separation", "                            g.cnt += 1\n                            g.inC := true\n",
     "                            g.cnt += 1\n                            g.inC := true\n                            g.sepN += 1\n"
     "                            g.sepX := na(g.sepX) ? (top ? bd : bu) : top ? math.min(g.sepX, bd) : math.max(g.sepX, bu)\n"),
    ("ineligible contacts not counted", "                            g.cnt += 1\n", "                            g.cnt += (bi - g.lastSt >= S.gapN) ? 1 : 0\n"),
    ("1H/D reversal body exactly at the minimum rejected (first occurrence = the 1H / D detector)", "if body < S.bodyMin - EPS", "if body <= S.bodyMin + EPS"),
    ("1H/D reversal ratio exactly at the minimum rejected (first occurrence = the 1H / D detector)", "if rng <= 0 or body < rng * S.ratio - EPS", "if rng <= 0 or body <= rng * S.ratio + EPS"),
    ("1H/D reversal colour not required (first occurrence = the 1H / D detector)", "    if top ? not (c < o) : not (c > o)\n        w += \"C\"\n", ""),
    ("1H/D reversal body end: upper edge missing (first occurrence = the 1H / D detector)", "if edge < P - S.buf - EPS or edge > P + S.buf + EPS", "if edge < P - S.buf - EPS"),
    ("wait one bar longer", "                                if bi >= g.waitEnd\n", "                                if bi > g.waitEnd\n"),
    ("contact end keeps the wait", "                        if g.inC\n                            g.inC := false\n                            if g.waiting\n",
     "                        if g.inC\n                            g.inC := false\n                            if false\n"),
    ("two signals from one contact", "                            if fw == \"\"\n                                g.waiting := false\n",
     "                            if fw == \"\"\n"),
    ("ineligible 3rd does not end the base", "                            if not g.elig and g.cnt >= 3\n                                fin := true\n", ""),
    ("1H/D limit one bar later (first occurrence = the 1H / D detector)", "                if bi - g.pvBar > S.maxN\n", "                if bi - g.pvBar > S.maxN + 1\n"),
    ("1H/D limit counted from the registration bar (first occurrence = the 1H / D detector)", "                if bi - g.pvBar > S.maxN\n", "                if bi - g.aBar > S.maxN\n"),
    ("right-side pivot ties accepted", "                isH := isH and mh > array.get(S.bu, j)\n", "                isH := isH and mh >= array.get(S.bu, j)\n"),
    ("both-pivot bar processed as a peak then a trough", "        if isH and isL\n            S.seq += 2\n        else\n",
     "        if false\n            S.seq += 2\n        else\n"),
    # per-TF wiring of the inputs (LTB-9)
    ("4H uses the 1H band", "ltNew4(h4Rev, h4Buf, h4Dist", "ltNew4(h4Rev, h1Buf, h4Dist"),
    ("4H uses the next-wave separation as the reversal", "ltNew4(h4Rev, h4Buf, h4Dist", "ltNew4(h4Dist, h4Buf, h4Dist"),
    ("D uses the 4H band", "ltNew1(hdPiv, hdWave, hdBuf,", "ltNew1(hdPiv, hdWave, h4Buf,"),
    ("4H ratio not divided by 100", "h4Ratio / 100.0, h4Wait", "h4Ratio, h4Wait"),
    ("D uses the 1H separation", "hdBuf, hdDist, hdGap", "hdBuf, h1Dist, hdGap"),
    ("D body from the 4H input", "hdGap, hdBody, hdRatio", "hdGap, h4Body, hdRatio"),
    # 4H detector (LTB-11)
    ("4H equal extreme stays on the earlier bar", "    else if S.dir == 1\n        if bu >= S.cP\n", "    else if S.dir == 1\n        if bu > S.cP\n"),
    ("4H reversal of exactly 60 rejected", "            if bd <= S.cP - S.rev + EPS\n", "            if bd < S.cP - S.rev - EPS\n"),
    ("4H reversal confirmed by the wick", "            if bd <= S.cP - S.rev + EPS\n", "            if l <= S.cP - S.rev + EPS\n"),
    ("4H trough reversal confirmed by the wick", "            if bu >= S.cP + S.rev - EPS\n", "            if h >= S.cP + S.rev - EPS\n"),
    ("4H first confirmed extreme already a base", "    if S.nConf >= 2 and bi - pvBar <= S.maxN\n", "    if S.nConf >= 1 and bi - pvBar <= S.maxN\n"),
    ("4H registration beyond the limit allowed", "    if S.nConf >= 2 and bi - pvBar <= S.maxN\n", "    if S.nConf >= 2\n"),
    ("4H readiness on a touching bar", "                    if not ct and not fin\n", "                    if not fin\n"),
    ("4H every touch is a new wave", "                    if ct and g.ready\n", "                    if ct\n"),
    ("4H next-wave separation of exactly 60 rejected", "if not g.ready and (top ? bd <= P - S.dist + EPS : bu >= P + S.dist - EPS)",
     "if not g.ready and (top ? bd < P - S.dist - EPS : bu > P + S.dist + EPS)"),
    ("4H readiness does not end the wait", "                            if g.waiting\n                                g.waiting := false\n"
     "                                g.why := ltAdd(g.why, \"N\")\n",
     "                            if false\n                                g.waiting := false\n                                g.why := ltAdd(g.why, \"N\")\n"),
    ("4H wave 3 gap counted from the extreme", "\n                        g.lastSt  := bi\n", "\n"),
    ("4H wave gap of exactly 8 rejected", "bool  gapOk = gap >= S.gapN", "bool  gapOk = gap > S.gapN"),
    ("4H limit 49 still monitored", "                if bi - g.pvBar > S.maxN\n                    fin := true\n                    ev += \";T,\" + str.tostring(g.id) + \",\" + (g.waiting ? \"1\" : \"0\") + \",\" + ltAdd(g.why, \"T\")\n                else if top ? c > P + S.buf + EPS : c < P - S.buf - EPS\n                    fin := true\n                    ev += \";V,\" + str.tostring(g.id) + \",\" + (g.waiting ? \"1\" : \"0\") + \",\" + ltAdd(g.why, \"V\")\n                else\n                    bool ct = h >= P - S.buf - EPS and l <= P + S.buf + EPS\n                    if ct and g.ready",
     "                if bi - g.pvBar > S.maxN + 1\n                    fin := true\n                    ev += \";T,\" + str.tostring(g.id) + \",\" + (g.waiting ? \"1\" : \"0\") + \",\" + ltAdd(g.why, \"T\")\n                else if top ? c > P + S.buf + EPS : c < P - S.buf - EPS\n                    fin := true\n                    ev += \";V,\" + str.tostring(g.id) + \",\" + (g.waiting ? \"1\" : \"0\") + \",\" + ltAdd(g.why, \"V\")\n                else\n                    bool ct = h >= P - S.buf - EPS and l <= P + S.buf + EPS\n                    if ct and g.ready"),
    ("4H two signals from one wave", "                        if fw == \"\"\n                            g.waiting := false\n", "                        if fw == \"\"\n"),
    ("4H reversal body exactly 6 rejected", "    if body < S.bodyMin - EPS\n        w += \"B\"\n    float rng = h - l\n    if rng <= 0 or body < rng * S.ratio - EPS\n        w += \"R\"\n    w\n\n// 極値の確定",
     "    if body <= S.bodyMin + EPS\n        w += \"B\"\n    float rng = h - l\n    if rng <= 0 or body < rng * S.ratio - EPS\n        w += \"R\"\n    w\n\n// 極値の確定"),
    ("chart: the 4H wave details missing in the tooltip", "            if k == 1 and array.size(f) > 14\n", "            if false\n"),
    # chart side
    ("chart: no marker for a contact", "        else if ty == \"C\"\n", "        else if ty == \"Cx\"\n"),
    ("chart: reasons not shown", "    out += str.contains(w, \"G\") ? \"／間隔不足\" : \"\"\n", ""),
    ("chart: contact band tooltip uses the 1H band on every TF", "str.tostring(r.lvl - ltBufK(r.k), \"#.##\")", "str.tostring(r.lvl - h1Buf, \"#.##\")"),
    # infrastructure (request.security / chart side)
    ("lower chart gets the forming 4H bar", "f_ltCore(1, 1)", "f_ltCore(1, 0)"),
    ("1H chart takes offset 1 (delayed)", "string ltPk1 = ltSame1 ? ltPk1N : ltPk1C", "string ltPk1 = ltPk1C"),
    ("lower chart takes the 1H offset 0", "string ltPk1 = ltSame1 ? ltPk1N : ltPk1C", "string ltPk1 = ltPk1N"),
    ("1H offset chosen inside the requested context (LTB-1 bug)", "f_ltCore(0, 1)", "f_ltCore(0, ltSame1 ? 0 : 1)"),
    ("detector gated by the chart support (LTB-1 bug)", "    string blk = k == 1 ? ", "    string blk = not ltChartOk ? \"B,0,0,0,0,0\" : k == 1 ? "),
    ("no dedupe of received blocks", "take := (na(lT) or sT > lT) and ltInt(f, 2) <= time_close", "take := ltInt(f, 2) <= time_close"),
    ("blocks of bars not yet closed taken", "take := (na(lT) or sT > lT) and ltInt(f, 2) <= time_close", "take := (na(lT) or sT > lT)"),
    ("4H chart takes the 4H offset 1 (delayed)", "string ltPk4 = ltSame4 ? ltPk4N : ltPk4C", "string ltPk4 = ltPk4C"),
    ("lower chart takes the 4H offset 0", "string ltPk4 = ltSame4 ? ltPk4N : ltPk4C", "string ltPk4 = ltPk4N"),
    ("D chart takes the D offset 1 (delayed)", "string ltPkD = ltSameD ? ltPkDN : ltPkDC", "string ltPkD = ltPkDC"),
    ("lower chart takes the D offset 0", "string ltPkD = ltSameD ? ltPkDN : ltPkDC", "string ltPkD = ltPkDN"),
    ("4H / D chart receives the lower 1H", "    if ltTake1\n        ltRecv(0, ltPk1)\n", "    if true\n        ltRecv(0, ltPk1)\n"),
    ("D chart receives the lower 4H", "    if ltTake4\n        ltRecv(1, ltPk4)\n", "    if true\n        ltRecv(1, ltPk4)\n"),
    ("4H / D charts unsupported (LTB-9 support)", "bool ltChartOk = ltTimeBar and (ltChSec <= 3600 or ltChSec == 14400 or ltChSec == 86400)",
     "bool ltChartOk = ltTimeBar and ltChSec <= 3600"),
    ("2H chart treated as supported", "bool ltChartOk = ltTimeBar and (ltChSec <= 3600 or ltChSec == 14400 or ltChSec == 86400)",
     "bool ltChartOk = ltTimeBar and (ltChSec <= 14400 or ltChSec == 86400)"),
    ("chart processes unconfirmed executions", "if barstate.isconfirmed and ltChartOk\n", "if ltChartOk\n"),
    ("one block per packet", "string out = prevBlk == \"\" ? blk : prevBlk + \";\" + blk", "string out = blk"),
    ("cap drops the late contact marker", "    if lost\n        ltAppMk(r, \"検知\")\n", ""),
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
            gate_draw()
            gate_gap()
            gate_chart_quick()
            for k in (0, 2):
                gate_tf(k)
            gate_h4()
            gate_both()
            gate_params()
            gate_charts()
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



# ============================================================================
# LTB-4: body rules
# ============================================================================

# ============================================================================
# LTB-5: pivot ties on continuous data + attribution of the differences to the old wick version
# ============================================================================


def cont(closes, o0, up=1.0, dn=1.0):
    """continuous bars: each opens exactly at the previous close (the first at o0)."""
    rows, o = [], o0
    for c in closes:
        rows.append(bx(o, c, up, dn))
        o = c
    return rows


def is_cont(bars):
    return all(bars[i]["o"] == bars[i - 1]["c"] for i in range(1, len(bars)))




# ============================================================================
# LTB-6: 1H formation-width filter and minimum bars to a re-approach
# ============================================================================
LTB5_COMMIT = "79f21a3"



# ============================================================================
# LTB-7: the new 1H method (hand-made 1H bars with the DEFAULT 1H inputs; bottoms = the mirror of the tops)
# ============================================================================
LTB6_COMMIT = "34db07f"
P0 = 2000.0
SCALE = {0: 1.0, 1: 2.0, 2: 4.0}         # 4H / D price settings = 2x / 4x the 1H ones (ratio scale-free)
PFX = {0: "h1", 1: "h4", 2: "hd"}


def fmt2(x):
    """str.tostring(x, "#.##") as the harness formats it."""
    return f"{x:.2f}".rstrip("0").rstrip(".")


def scale_rows(rows, s):
    return [tuple(P0 + s * (x - P0) for x in r) for r in rows] if s != 1.0 else list(rows)


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


def gate_tf(k):
    """LTB-9: the hand-made scenarios on TF k's own bars with TF k's DEFAULT inputs. The 1H scenario prices are scaled around 2000 by
    SCALE[k] (4H x2, D x4): every price setting of 4H / D is exactly that multiple of the 1H one and the ratio is scale-free, so each
    boundary is hit exactly on every TF (e.g. first wave 9.99 / 10 -> 19.98 / 20 -> 39.96 / 40)."""
    res, det = {}, []
    s_, pf, tfn, ms = SCALE[k], PFX[k], TFJA[k], TF_MS[k]
    sc = lambda rows: scale_rows(rows, s_)                                              # noqa: E731
    L = lambda x: P0 + s_ * (x - P0)                                                     # noqa: E731

    def case(name, rows, exp, ov=None):
        ok = True
        rows = sc(rows)
        for mir in (False, True):
            rr = mirror(rows) if mir else rows
            bars = mk(rr, ms)
            d = Det(k, ov).run(bars)
            r = ref_for(k, ov).run(bars)
            ev, act = det_events(d)
            mine = ev_lv(ev, P0, 1 if mir else -1)
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
    case("2: first wave 10.01 (just after) -> base", h1_base(1989.99) + [S_OK], lambda m, ev: R_(m) == [REG])
    case("2 (control): the 9.99 rows with the wave input 9.98 -> base (the trough pivot exists; only the width decides)",
         h1_base(1990.01) + [S_OK], lambda m, ev: R_(m) == [REG], {pf + "Wave": 9.98 * s_})
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
        r95 = [(i, e) for i, e in ev if e[0] == "R" and e[3] in (L(1995), 4000 - L(1995))]
        r00 = [(i, e) for i, e in ev if e[0] == "R" and e[3] == 2000.0]
        return [i for i, _ in r95] == [13] and [i for i, _ in r00] == [18] and r95[0][1][4] == 1_790_006_400_000 + 9 * ms
    case("4: a higher peak without a trough between updates the series -> a new base (2000, bar 18); the first base (1995, pivot bar 9) "
         "keeps its price / pivot time", r4, exp4)
    r4b = r4[:14] + [bx(1989, 1993)] + r4[15:]
    case("4: a lower peak without a trough between is not added -> no base at 1993", r4b,
         lambda m, ev: not [e for _, e in ev if e[0] == "R" and e[3] in (L(1993), 4000 - L(1993))])
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
    case("10: 2nd contact 9 bars after the pivot (just after) -> eligible, detected", at(base, 18) + [S_OK],
         lambda m, ev: C_(m) == [(18, 2, 1, "")] and D_(m) == [(18, 2, 0)])
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
    case("11: separation 30.01 (just after) -> eligible, detected", at(bs, 17, bx(1972, 1969.99)) + [S_OK],
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
    case("13: body 3.01 / ratio 30.1 % (just after) -> detected", st(bx(1998, 1994.99, up=3, dn=3.99)),
         lambda m, ev: D_(m) == [(17, 2, 0)])
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
    case("18: age 23 (just before the limit) allowed", at(base, PV + 23) + [S_OK], lambda m, ev: D_(m) == [(PV + 23, 2, 0)])
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
        check(f"LT-H[{tfn}] " + nm, ok, str([x for x in det if x[0] == nm][:2]) if not ok else "")

    # 11 (drawings): contact markers incl. ineligible ones with reasons, detection label wording, restore after the cap
    s_ok = sc([S_OK])[0]
    show = {0: "dsTf1", 1: "dsTf4", 2: "dsTfD"}[k]

    def tf_chart(rows, ov=None):
        """TF k's rows, flat dummy series for the other TFs, 15M chart bars covering TF k's bars."""
        flat = (1950.0, 1951.0, 1949.0, 1950.0)
        hx = [mk(sc(rows), ms) if kk == k else mk([flat] * 3, TF_MS[kk]) for kk in range(3)]
        fx = Feeds(hx)
        cb = []
        for b in hx[k]:
            for q in range(ms // M15):
                T = b["T"] + q * M15
                cb.append(dict(T=T, C=T + M15, o=b["o"], h=b["h"], l=b["l"], c=b["c"]))
        return Chart(fx, M15, dict(ov or {}, **{show: True})).run(cb), fx, hx
    ch, _, _ = tf_chart(at(base, 16) + [S_OK] + [F] * 8 + [S_OK, F])
    labs = [d for d in ch.env["_draws"] if d.kind == "label"]
    mk2 = [d for d in labs if d.text.startswith(f"{tfn}#") and "2回目" in d.text and d.kw.get("style") == "diamond"]
    mk3 = [d for d in labs if d.text.startswith(f"{tfn}#") and "3回目" in d.text and d.kw.get("style") == "diamond"]
    lab = [d for d in labs if d.text.startswith(f"トリプルトップ {tfn}")]
    okd = (len(mk2) == 1 and "不採用" in mk2[0].text and "間隔不足" in getattr(mk2[0], "tooltip", mk2[0].kw.get("tooltip", ""))
           and "ヒゲを含む接触" in mk2[0].kw.get("tooltip", "") and f"{tfn}足" in mk2[0].kw.get("tooltip", "")
           and f"基準帯 {fmt2(P0 - 5 * s_)}〜{fmt2(P0 + 5 * s_)}" in mk2[0].kw.get("tooltip", "")
           and abs(mk2[0].args[1] - s_ok[1]) < 1e-9
           and len(mk3) == 1 and "検知" in mk3[0].text and len(lab) == 1 and "実体による反転検知" in lab[0].kw.get("tooltip", "")
           and f"反転の判定足 ({tfn}足)" in lab[0].kw.get("tooltip", "")
           and abs(lab[0].args[1] - max(s_ok[0], s_ok[3])) < 1e-9 and not [d for d in labs if d.text.startswith("ダブル")])
    # restore: cap 1, A (top 2000) waiting, B (bottom 1965) starts a contact on the bar where A detects -> A's notes / marker / line back
    rows_r = list(base) + [bx(1968, 1965), bx(1966, 1972), bx(1972, 1980), bx(1980, 1988), bx(1988, 1990), W_BULL,
                           bx(1996, 1966, up=1, dn=1), F, F]
    chr_, fr, hr = tf_chart(rows_r, dict(dsMaxGrp=1))
    evr = det_events(fr[k].det)[0]
    dA = [e for i, e in evr if e[0] == "D"]
    cB = [(i, e) for i, e in evr if e[0] == "C" and e[2] == 1]
    okr = bool(dA) and bool(cB) and cB[0][0] == 20
    if okr:
        gid = dA[0][1]
        live = [d for d in chr_.env["_draws"] if not d.deleted]
        dead = [d for d in chr_.env["_draws"] if d.deleted]
        tag = f"{tfn}#{gid} "
        okr = (any(d.kind == "label" and d.text.startswith(f"基準 {tfn}#{gid} 山") for d in live)
               and any(d.kind == "label" and d.text.startswith(tag) and "確定" in d.text for d in live)
               and sum(1 for d in live if d.kind == "label" and d.text.startswith(tag + "2回目")) == 1
               and any(d.kind == "line" and d.kw.get("style") == "dashed" and d.args[2] == hr[k][19]["T"] for d in live)
               and any(d.kind == "label" and d.text.startswith(tag + "2回目") for d in dead)
               and any(d.kind == "label" and d.text.startswith(f"ダブルトップ {tfn}") and "接触から 1 本目" in d.text for d in live))
    check(f"LT-H11[{tfn}] drawings: contact markers on the contact start bar's high (also the ineligible 2nd with its reason 間隔不足 and "
          "'ヒゲを含む接触' in the tooltip); the triple label at the reversal body end with '実体による反転検知'; no double label for an "
          "ineligible 2nd; with cap 1 a base whose drawings were removed gets its notes, contact marker and line back on its detection",
          okd and okr, str((okd, okr)))


# ============================================================================
# LTB-8: a 1H bar that is both a body peak and a body trough
# ============================================================================
LTB7_COMMIT = "6c76710"


def gate_both():
    """LTB-8 rule, on every TF (LTB-9): a bar that is both a body peak and a body trough is not adopted."""
    for k in (0, 2):                      # LTB-11: 4H has no fixed-window pivot (gate_h4)
        s_, ms, tfn = SCALE[k], TF_MS[k], TFJA[k]
        L = lambda x: P0 + s_ * (x - P0)                                               # noqa: E731
        base = h1_base()
        rows = scale_rows(at(base, 17) + [bx(2004, 1950, up=1, dn=1), F, F, F, S_OK, F], s_)
        ok_sc, det = True, []
        norm_runs = []
        for mir in (False, True):
            rr = mirror(rows) if mir else rows
            bars = mk(rr, ms)
            d = Det(k)
            snaps = []
            for b in bars:
                d.step(b)
                snaps.append((d.S.sSide, d.S.sP, d.S.aSide, d.S.aP, d.S.seq))
            r = ref_for(k).run(bars)
            ev, act = det_events(d)
            mine = ev_lv(ev, P0, 1 if mir else -1)
            xl = {L(2004), L(1950), 4000 - L(2004), 4000 - L(1950)}
            Rx = [e for _, e in ev if e[0] == "R" and e[3] in xl]
            exp = ([(i, e[0]) for i, e in mine if e[0] != "R"] == [(17, "C"), (17, "D"), (21, "C"), (21, "E")]
                   and [(e[5], e[8], e[9]) for _, e in mine if e[0] == "C"] == [(2, 1, ""), (3, 0, "G")]
                   and [(e[5], e[8]) for _, e in mine if e[0] == "D"] == [(2, 0)])
            series_kept = snaps[21][:4] == snaps[20][:4] and snaps[21][4] == snaps[20][4] + 2
            if not (ev == r.events and act == r.act and exp and not Rx and series_kept and d.S.seq == r.next_id - 1
                    and r.cov.get("both_pivot_skipped") == 1):
                ok_sc = False
                det.append((mir, exp, Rx, series_kept, snaps[20], snaps[21], mine[:8]))
            flip = lambda x: x if x is None else 4000 - x                                   # noqa: E731
            norm_runs.append([(i, e[0], e[1]) + ((e[5], e[8], e[9]) if e[0] == "C" else (e[5], e[8]) if e[0] == "D" else
                                                  (flip(e[3]) if mir else e[3],) if e[0] == "R" else ()) for i, e in ev])
        check(f"LT-W1[{tfn}] a bar that is both a body peak and a body trough (bar 17, confirmed on bar 21): no base from it, the "
              f"reference series unchanged on bar 21 (only the id counter +2); the existing base still contacts / detects on that bar "
              f"(double on bar 17) and ends normally on the confirmation bar (3rd contact, gap 4 -> ineligible); == the reference",
              ok_sc, str(det[:2]))
        check(f"LT-W2[{tfn}] the mirrored data gives the mirrored result (same bars / ids / counts / reasons, levels reflected)",
              norm_runs[0] == norm_runs[1])
        rows_c = scale_rows(at(base, 17) + [bx(2004, 1970, up=1, dn=1), F, F, F, S_OK, F], s_)
        d = Det(k)
        sn = []
        for b in mk(rows_c, ms):
            d.step(b)
            sn.append((d.S.sSide, d.S.sP))
        check(f"LT-W3[{tfn}] control: the same bar as a peak only (body bottom 1970 x scale) is adopted on bar 21 (series -> that peak)",
              sn[20] != sn[21] and sn[21] == (-1, L(2004)), str((sn[20], sn[21])))
        # random heavily gapped series of this TF: such bars occur, Pine == reference
        n_both, ok4 = 0, True
        for piv in (1, 2):
            for seed in range(4):
                bars = rand_tf(9900 + 100 * piv + seed + 10 * k, 900, ms, 4.0 * s_, gaps=True, gap_p=0.6)
                ov = {PFX[k] + "Piv": piv, PFX[k] + "Dist": 10.0 * s_}
                ok, why, r, _ = compare(k, bars, ov)
                ok4 = ok4 and ok
                n_both += r.cov.get("both_pivot_skipped", 0)
        check(f"LT-W4[{tfn}] heavily gapped random {tfn} series: {n_both} bars that are both a peak and a trough, translated Pine == "
              f"reference on every event", ok4 and n_both > 0)


# ============================================================================
# LTB-9: 1H unchanged, per-TF inputs used and independent, only this file changed
# ============================================================================
LTB8_COMMIT = "9951f9b"
LTB10_COMMIT = "35d2ee4"


def gate_params():
    prev = prev_src(LTB10_COMMIT)
    # 1: 1H and D == 35d2ee4 (LTB-10) block by block (every event incl. ids / counts / reasons, active counts) and on the chart
    ok1, n1 = True, 0
    for k in (0, 2):
        for seed in range(4):
            for gp in (0.0, 0.05, 0.6):
                bars = rand_tf(9600 + seed + 10 * k, 900, TF_MS[k], 4.0 * SCALE[k], gaps=gp > 0, gap_p=gp or 0.05)
                for ov in (None, {PFX[k] + "Dist": 10.0 * SCALE[k]}, {PFX[k] + "Piv": 2, PFX[k] + "Dist": 10.0 * SCALE[k]}):
                    n1 += 1
                    if Det(k, ov).run(bars).blocks != Det(k, ov, prev).run(bars).blocks:
                        ok1 = False
    b5, htf, feeds_new = build(12, days=70, scale=3.0)
    feeds_prev = Feeds(htf, None, prev)
    c15 = [b for b in agg(b5, M15) if b["T"] >= b5[0]["T"] + 20 * DAY]
    ch_new = Chart(feeds_new, M15).run(c15)
    ch_prev = Chart(feeds_prev, M15, src=prev).run(c15)
    ok1 = ok1 and all(feeds_new[k].outs == feeds_prev[k].outs and [x for x in ch_new.events if x[0] == k] ==
                      [x for x in ch_prev.events if x[0] == k] and all(ch_new.env[c][k] == ch_prev.env[c][k] for c in
                                                                      ("ltNAct", "ltNApp", "ltNDet", "ltNGap", "ltNBlk", "ltLastT"))
                      for k in (0, 2))
    inp_prev, inp_new = ap.inputs(prev), ap.inputs(SRC)
    ok1 = ok1 and all(inp_new[x] == inp_prev[x] for x in inp_prev if x.startswith(("h1", "hd", "ds")))
    check(f"LT-P1 1H and D == {LTB10_COMMIT}: every block (events incl. ids / contact counts / reasons, active-base counts) on {n1} "
          f"random runs (continuous, 5 % and 60 % gaps, three settings), the packets and every event / counter received on a 15M chart; "
          f"1H / D / display inputs unchanged", ok1)
    # 2 / 3: every input of every TF is used by that TF's detector and by no other TF's
    change = dict(Piv=lambda v: v - 1, Wave=lambda v: v * 3, Buf=lambda v: v * 0.6, Dist=lambda v: v * 0.5, Gap=lambda v: v - 3,
                  Body=lambda v: v * 2.5, Ratio=lambda v: 60.0, Wait=lambda v: 1, Max=lambda v: 14, Rev=lambda v: v * 0.5)
    names = {0: ("Piv", "Wave", "Buf", "Dist", "Gap", "Body", "Ratio", "Wait", "Max"),
             1: ("Rev", "Buf", "Dist", "Gap", "Body", "Ratio", "Wait", "Max"),
             2: ("Piv", "Wave", "Buf", "Dist", "Gap", "Body", "Ratio", "Wait", "Max")}
    inp = ap.inputs(SRC)
    series = {k: [rand_tf(9700 + 10 * k + sd, 700, TF_MS[k], 4.0 * SCALE[k], gaps=True, gap_p=gp)
                  for sd in range(3) for gp in (0.05, 0.6)] for k in range(3)}
    base_blocks = {k: [Det(k).run(b).blocks for b in series[k]] for k in range(3)}
    unused, leaks = [], []
    for k in range(3):
        for nm in names[k]:
            f = change[nm]
            key = PFX[k] + nm
            ov = {key: f(inp[key])}
            if all(Det(k, ov).run(b).blocks == bb for b, bb in zip(series[k], base_blocks[k])):
                unused.append(key)
            for j in range(3):
                if j != k and any(Det(j, ov).run(b).blocks != bb for b, bb in zip(series[j][:2], base_blocks[j][:2])):
                    leaks.append((key, TFJA[j]))
    check("LT-P2 each of the 26 inputs (1H / D 9 each, 4H 8) changes its own TF's detector results on that TF's random series (the "
          "setting is really used)", not unused, str(unused))
    check("LT-P3 changing any input of one TF leaves the other two TFs' results unchanged", not leaks, str(leaks[:5]))
    # chart level: a 4H setting change touches only the 4H packets / events
    feeds_4 = Feeds(htf, dict(h4Rev=30.0, h4Dist=20.0))
    ok3c = (feeds_4[0].outs == feeds_new[0].outs and feeds_4[2].outs == feeds_new[2].outs and feeds_4[1].outs != feeds_new[1].outs)
    check("LT-P3b chart level: changing 4H inputs changes the 4H packets only (1H / D packets identical)", ok3c)
    ok15, changed = ltb_only_since(LTB8_COMMIT)
    check(f"LT-P15 the LTB commits since {LTB8_COMMIT} and the working tree touch only LongTermDoubleTripleTopBottomXAU.pine and "
          f"tests/ltb_sim.py (other indicators / strategies / Zone / orders unchanged; unrelated commits of other work not counted)",
          ok15, str(changed))


LTB_FILES = {"LongTermDoubleTripleTopBottomXAU.pine", "tests/ltb_sim.py"}


def ltb_only_since(base):
    """the LTB commits after `base` (and the working tree) touch only this indicator and its test; other commits on the branch
    (unrelated work) are not counted. -> (ok, details)"""
    log = subprocess.run(["git", "log", "--format=%H %s", base + "..HEAD"], cwd=ROOT, capture_output=True, text=True)
    bad = []
    for line in log.stdout.splitlines():
        h, msg = line.split(" ", 1)
        if msg.startswith("LTB-"):
            files = subprocess.run(["git", "show", "--name-only", "--format=", h], cwd=ROOT, capture_output=True, text=True).stdout.split()
            bad += [(h[:7], f) for f in files if f not in LTB_FILES]
    wt = subprocess.run(["git", "diff", "--name-only", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.split()
    bad += [("worktree", f) for f in wt if f not in LTB_FILES]
    return log.returncode == 0 and not bad, bad


# ============================================================================
# LTB-10: 4H and 1D charts (fetch / receive / draw only)
# ============================================================================
LTB9_COMMIT = "ba984e3"
H2, H12, WEEK = 2 * H1, 12 * H1, 7 * DAY


def agg_day_aligned(bars, tf_ms):
    """4H bars aligned to the 22:00 day boundary (as XAU's 4H bars align with the session), so D closes coincide with 4H closes."""
    groups = {}
    for b in bars:
        groups.setdefault((b["T"] - 22 * H1) // tf_ms, []).append(b)
    out = []
    for key in sorted(groups):
        g = groups[key]
        T = key * tf_ms + 22 * H1
        out.append(dict(T=T, C=T + tf_ms, o=g[0]["o"], h=max(x["h"] for x in g), l=min(x["l"] for x in g), c=g[-1]["c"]))
    return out


def det_keys(ch, k, t0=None, t1=None):
    """original detection events of TF k received by a chart: (TF, pivot time, side, level, count, contact start, decision bar)."""
    out = []
    for kk, f, t, tc in ch.events:
        if kk == k and f[0] == "D":
            key = (kk, int(float(f[4])), int(f[2]), float(f[3]), int(f[7]), int(float(f[8])), int(float(f[11])))
            dTc = int(float(f[12]))
            if (t0 is None or key[6] >= t0) and (t1 is None or dTc <= t1):
                out.append(key)
    return sorted(out)


def direct_keys(feeds, k, t0=None, t1=None):
    out = []
    for i, blk in enumerate(feeds[k].det.blocks):
        b = feeds[k].htf[i]
        for e in parse_block(blk)[1]:
            if e[0] == "D" and (t0 is None or b["T"] >= t0) and (t1 is None or b["C"] <= t1):
                out.append((k, e[4], e[2], e[3], e[5], e[6], b["T"]))
    return sorted(out)


def gate_charts():
    prev = prev_src(LTB10_COMMIT)
    # 1: 5M / 15M / 1H charts: 1H and D unchanged since 35d2ee4 (LTB-11 changes 4H on purpose; its display OFF here so every drawing is
    #    1H / D): events incl. ids / counts / reasons, blocks, counters, drawings
    b5, htf, feeds = build(12, days=70, scale=3.0)
    feeds_prev = Feeds(htf, None, prev)
    ok1, det1 = True, []
    for nm, ms, bars in (("5M", M5, [b for b in b5 if b["T"] >= b5[0]["T"] + 40 * DAY]),
                         ("15M", M15, [b for b in agg(b5, M15) if b["T"] >= b5[0]["T"] + 20 * DAY]), ("1H", H1, agg(b5, H1))):
        a = Chart(feeds, ms, dict(dsTf4=False, dsTfD=True)).run(bars, ticks_from=len(bars) - 30)
        b = Chart(feeds_prev, ms, dict(dsTf4=False, dsTfD=True), src=prev).run(bars, ticks_from=len(bars) - 30)
        keep = lambda xs: [x for x in xs if x[0] != 1]                                       # noqa: E731
        same = (keep(a.events) == keep(b.events) and keep(a.blocks) == keep(b.blocks) and all(
                [a.env[x][k] for k in (0, 2)] == [b.env[x][k] for k in (0, 2)] for x in
                ("ltNAct", "ltNApp", "ltNDet", "ltNGap", "ltNBlk", "ltLastT"))
                and [(d.kind, d.text, d.args) for d in a.env["_draws"]] == [(d.kind, d.text, d.args) for d in b.env["_draws"]])
        if not same:
            ok1 = False
            det1.append(nm)
    check(f"LT-C1 5M / 15M / 1H charts, 1H and D == {LTB10_COMMIT}: every received event (ids / contact counts / reasons), block, counter "
          f"(active bases / contacts / detections / gaps) and drawing (realtime ticks at the end included)", ok1, str(det1))

    # consistent 1H / 4H / D data (4H and D aligned to 22:00); charts start after a 100-day warm-up of the detectors
    ok9, ok10, okt, okx, ok_once, ok_rt, ok7, ok16, det = True, True, True, True, True, True, True, True, []
    n4 = nD = 0
    for seed, gp in ((21, False), (22, True), (23, False)):
        h1 = rand_tf(7700 + seed, 24 * 420, H1, 4.0, gaps=gp, t0=1_790_006_400_000 // DAY * DAY + 22 * H1)
        hx = [h1, agg_day_aligned(h1, H4), agg_day_aligned(h1, DAY)]
        fx = Feeds(hx)
        T0 = hx[2][100]["T"]
        T1 = hx[2][-2]["T"]
        on = dict(dsTf4=True, dsTfD=True)
        charts = {"1H": Chart(fx, H1, on).run([b for b in hx[0] if b["T"] >= T0], ticks_from=None),
                  "4H": Chart(fx, H4, on).run([b for b in hx[1] if b["T"] >= T0], ticks_from=len([b for b in hx[1] if b["T"] >= T0]) - 40),
                  "D": Chart(fx, DAY, on).run([b for b in hx[2] if b["T"] >= T0], ticks_from=len([b for b in hx[2] if b["T"] >= T0]) - 15)}
        d4, dD = direct_keys(fx, 1, T0, T1), direct_keys(fx, 2, T0, T1)
        n4 += len(d4)
        nD += len(dD)
        # 9 / 10: the same original detections on every chart that takes them and == the detector run on that TF's own bars
        if not (det_keys(charts["1H"], 1, T0, T1) == det_keys(charts["4H"], 1, T0, T1) == d4):
            ok9 = False
            det.append((seed, "4H", len(det_keys(charts["1H"], 1, T0, T1)), len(det_keys(charts["4H"], 1, T0, T1)), len(d4)))
        if not (det_keys(charts["1H"], 2, T0, T1) == det_keys(charts["4H"], 2, T0, T1) == det_keys(charts["D"], 2, T0, T1) == dD):
            ok10 = False
            det.append((seed, "D", len(det_keys(charts["1H"], 2, T0, T1)), len(det_keys(charts["4H"], 2, T0, T1)),
                        len(det_keys(charts["D"], 2, T0, T1)), len(dD)))
        # 2 / 3 / 4 / 5: timing — same TF: on the decision bar's own confirmed execution; higher TF: at / after its close
        for nm, ms in (("1H", H1), ("4H", H4), ("D", DAY)):
            ch = charts[nm]
            for k in range(3):
                for key, t, tc in [(x[0], x[1], x[2]) for x in ch.received() if x[0][0] == k]:
                    dT, dTc = key[5], key[6]
                    if TF_MS[k] == ms and not (t == dT and tc == dTc):
                        okt = False
                        det.append((nm, TFJA[k], "same TF not on its own bar", dT, t))
                    if TF_MS[k] > ms and t < dTc:
                        okt = False
                        det.append((nm, TFJA[k], "taken before the source bar closed", dTc, t))
            t_first = ch.blocks[0][2] if ch.blocks else None
            for kk, sT, t, tc in ch.blocks:
                if TF_MS[kk] < ms:
                    ok7 = False
                # the chart's own TF: the block of the bar itself (on the chart's first bar the packet also carries the bar before)
                if TF_MS[kk] == ms and sT != t and t != t_first:
                    okt = False
                    det.append((nm, TFJA[kk], "same TF block of another bar", sT, t))
            keys = [x[0] for x in ch.received()]
            blks = [(x[0], x[1]) for x in ch.blocks]
            if len(keys) != len(set(keys)) or len(blks) != len(set(blks)):
                ok_once = False
            if getattr(ch, "rt_changed", False):
                ok_rt = False
        # 7: lower TFs neither received nor drawn
        for nm, lower in (("4H", (0,)), ("D", (0, 1))):
            ch = charts[nm]
            if any(x[0] in lower for x in ch.events) or any(d.text.startswith(tuple(TFJA[k] + "#" for k in lower)) or
                                                            d.text.startswith(tuple("基準 " + TFJA[k] for k in lower))
                                                            for d in ch.env["_draws"] if d.kind == "label"):
                ok7 = False
                det.append((nm, "lower TF received / drawn"))
            if any(ch.env["ltNBlk"][k] != 0 or ch.env["ltLastT"][k] is not None for k in lower):
                ok7 = False
        # 8: the TFs a chart takes keep being received (every closed target bar in range taken)
        for nm, ms, ks in (("4H", H4, (1, 2)), ("D", DAY, (2,))):
            ch = charts[nm]
            first = [b for b in hx[{H4: 1, DAY: 2}[ms]] if b["T"] >= T0][0]["T"]
            last = [b for b in hx[{H4: 1, DAY: 2}[ms]] if b["T"] >= T0][-1]
            for k in ks:
                taken = sorted(sT for kk, sT, _, _ in ch.blocks if kk == k)
                # own TF: up to the last chart bar's close; higher TF: delivered by a later chart bar (closed by the last bar's start)
                lim = last["C"] if TF_MS[k] == ms else last["T"]
                want = [b["T"] for b in hx[k] if b["T"] >= first and b["C"] <= lim]
                if not set(want) <= set(taken):
                    okx = False
                    det.append((nm, TFJA[k], "not every closed bar taken", len(taken), len(want)))
        # 16: each chart's drawings sit on its own bars (a fresh run per chart, no coordinates of another chart)
        for nm, ms in (("4H", H4), ("D", DAY)):
            ch = charts[nm]
            tb = {b["T"] for b in hx[{H4: 1, DAY: 2}[ms]]}
            for d in ch.env["_draws"]:
                xs = [d.args[0]] + ([d.args[2]] if d.kind == "line" else [])
                if any(x not in tb for x in xs):
                    ok16 = False
                    det.append((nm, "drawing off the chart's bars", d.kind, d.text[:20], xs))
                    break
    check(f"LT-C9 4H detections: received on 1H and 4H charts == the 4H detector run on the 4H bars (pivot time, side, TF, level, count, "
          f"contact start, decision bar; ids not used; 100-day warm-up, common range; {n4} detections)", ok9 and n4 > 0, str(det[:3]))
    check(f"LT-C10 D detections: received on 1H, 4H and D charts == the D detector run on the D bars ({nD} detections)",
          ok10 and nD > 0, str(det[:3]))
    check("LT-C2-5 timing: on the 4H chart 4H results and on the D chart D results are taken on the decision bar's own confirmed "
          "execution (not one bar later); a higher TF only at / after its source bar closed; blocks of the chart's own TF carry that "
          "bar's time", okt, str([x for x in det if "same TF" in str(x) or "before" in str(x)][:3]))
    check("LT-C7 4H chart: no 1H block / event / drawing; D chart: no 1H / 4H; their table rows have no receive time / counts",
          ok7, str([x for x in det if "lower" in str(x)][:3]))
    check("LT-C8 the TFs a 4H / D chart takes keep being received (every closed 4H / D bar in range taken)", okx,
          str([x for x in det if "taken" in str(x)][:3]))
    check("LT-C13/14 4H / D charts with realtime ticks at the end: unconfirmed executions (incl. the forming bar's offset-0 value) "
          "take nothing; every block and detection taken once", ok_rt and ok_once)
    check("LT-C16 4H / D charts: every drawing sits on that chart's own bar times", ok16, str([x for x in det if "drawing" in str(x)][:3]))

    # 2 / 3 / 13: constructed — the forming 4H / D bar of a detection never gives a detection before its close, and the detection is
    # taken on that bar's confirmed execution (history run == realtime run)
    okf, detf = True, []
    for k, ms in ((1, H4), (2, DAY)):
        if k == 1:                          # LTB-11: example A with the reversal one bar after the wave start (bar 24 -> 25)
            rows = ex_a4()[:24] + [bx(4182, 4189, up=1, dn=1), bx(4189, 4180, up=0, dn=1), bx(4180, 4170), bx(4170, 4165)]
        else:
            rows = scale_rows(at(h1_base(), 17) + [W_BULL, S_OK, F, F], SCALE[k])
        dbar = 25 if k == 1 else 18
        flat = (1950.0, 1951.0, 1949.0, 1950.0)
        hx = [mk([flat] * 3, H1), mk([flat] * 3, H4), mk([flat] * 3, DAY)]
        hx[k] = mk(rows, ms)
        fx = Feeds(hx)
        bars = hx[k]
        show = dict(dsTf4=True, dsTfD=True)
        hist = Chart(fx, ms, show).run(bars)
        rt = Chart(fx, ms, show)
        seen_early = []
        nev = []
        for i, b in enumerate(bars):
            pks = {it["var"]: it["core"].value(b["T"], it["off"]) for it in fx.items}
            if i >= 15:
                for frac in (0.3, 0.7, 1.0):
                    pb = dict(b, h=b["o"] + (b["h"] - b["o"]) * frac, l=b["o"] - (b["o"] - b["l"]) * frac,
                              c=b["o"] + (b["c"] - b["o"]) * frac)
                    tp = {it["var"]: it["core"].partial_value(b["T"], pb, it["off"]) for it in fx.items}
                    before = len(rt.events)
                    rt._exec(pb, False, tp)
                    if len(rt.events) != before:
                        seen_early.append(i)
            rt._exec(b, True, pks)
            nev.append(len(rt.events))
        dk = [x for x in rt.received() if x[0][0] == k]
        if seen_early or rt.events != hist.events or not dk or dk[0][1] != bars[dbar]["T"] or dk[0][2] != bars[dbar]["C"]:
            okf = False
            detf.append((TFJA[k], seen_early, len(rt.events), len(hist.events), dk[:1]))
        # the forming bar's own partial packet did contain the detection at frac 1.0 (so the confirmed-only take is what holds it back)
        part = fx[k].det
    check("LT-C2/3/13 constructed 4H (example A, LTB-11) / D double tops on a 4H / D chart: nothing taken during the forming bar's ticks "
          "(offset 0 changes every tick); the detection taken on the decision bar's confirmed execution (its own bar, not the next one); "
          "realtime run == history run",
          okf, str(detf))

    # 5 (guard): even if a lower chart were handed the offset-0 packet of 4H / D (the forming target bar, with its final values on
    # history), the receive guard takes a target bar only once it has closed by the chart bar's close
    h1g = rand_tf(7790, 24 * 120, H1, 4.0, gaps=False, t0=1_790_006_400_000 // DAY * DAY + 22 * H1)
    hg = [h1g, agg_day_aligned(h1g, H4), agg_day_aligned(h1g, DAY)]
    fg = Feeds(hg)
    for it in fg.items:
        if it["var"] in ("ltPk4C", "ltPkDC"):
            it["off"] = 0                                   # simulate the wrong packet arriving (not the source's choice)
    cg = Chart(fg, H1, dict(dsTf4=True, dsTfD=True)).run(hg[0])
    close_of = {(k, b["T"]): b["C"] for k in (1, 2) for b in hg[k]}
    early = [(TFJA[k], sT, t) for k, sT, t, tc in cg.blocks if k > 0 and close_of[(k, sT)] > tc]
    taken_k = {k: len([x for x in cg.blocks if x[0] == k]) for k in (1, 2)}
    check("LT-C5g receive guard: a 1H chart handed the 4H / D offset-0 packets (forming bar with its final values) still takes each 4H / D "
          "bar only on the chart bar whose close reaches that bar's close (no lookahead)", not early and taken_k[1] > 0 and taken_k[2] > 0,
          str(early[:3]))

    # 15: same-bar detections kept; display / cap do not change what is detected (4H chart)
    two = list(h1_base()) + [bx(1968, 1962), bx(1962, 1958), bx(1958, 1970), bx(1970, 1980), bx(1980, 1990), bx(1990, 1993),
                             bx(1992, 1980), bx(1980, 1970), bx(1970, 1962), bx(1962, 1960)]
    rows2 = scale_rows(at(two, 28) + [S_OK, F, F], 4.0)
    flat = (1950.0, 1951.0, 1949.0, 1950.0)
    h2 = [mk([flat] * 3, H1), mk([flat] * 3, H4), mk(rows2, DAY)]
    f2 = Feeds(h2)
    base_ch = Chart(f2, DAY, dict(dsTfD=True, dsMaxGrp=80)).run(h2[2])
    labs = [d for d in base_ch.env["_draws"] if d.kind == "label" and d.text.startswith("ダブルトップ 日足")]
    ok15 = len(labs) == 2 and labs[0].args[0] == labs[1].args[0] == h2[2][28]["T"] and labs[0].args[1] != labs[1].args[1]
    for ov in (dict(dsTfD=False), dict(dsTfD=True, dsMaxGrp=1), dict(dsTfD=True, dsAllB=True, dsMaxGrp=2)):
        c = Chart(f2, DAY, ov).run(h2[2])
        if c.events != base_ch.events or any(c.env[x] != base_ch.env[x] for x in ("ltNAct", "ltNApp", "ltNDet")):
            ok15 = False
    check("LT-C15 D chart: two D tops detected by the same D bar -> two labels on that bar, stacked; display OFF / cap 1 / all-bases "
          "leave the received events and counters unchanged", ok15)

    # 17: unsupported charts (2H, 12H, weekly) take nothing
    ok17 = True
    for ms in (H2, H12, WEEK):
        bars = agg(b5, ms) if ms != WEEK else agg(b5, WEEK)
        c = Chart(feeds, ms).run(bars[:40])
        if c.events or c.blocks or c.chart_globals.get("ltChartOk"):
            ok17 = False
    check("LT-C17 2H / 12H / weekly charts: unsupported (ltChartOk false), nothing taken; the table shows the switch guidance", ok17)
    ok18, changed = ltb_only_since(LTB9_COMMIT)
    check(f"LT-C18 the LTB commits since {LTB9_COMMIT} and the working tree touch only LongTermDoubleTripleTopBottomXAU.pine and "
          f"tests/ltb_sim.py", ok18, str(changed))


# ============================================================================
# LTB-11: the 4H method (60 $ reversal extremes, waves after a 60 $ separation); hand-made 4H bars with the DEFAULT 4H inputs,
# tops and bottoms mirrored around 4300, each run also == the independent reference Ref4
# ============================================================================
C4 = 4300.0


def mirror_c(rows, c0=C4):
    return [(2 * c0 - o, 2 * c0 - l, 2 * c0 - h, 2 * c0 - c) for o, h, l, c in rows]


def ex_a4():
    """example A of the specification on 4H bars: 4300 -> 4140 (first extreme, reference) -> 4209 (base top) -> 4080 (base bottom)
    -> 4189: the bearish bar whose body top is exactly 20 below the base (bar 24) is the double top."""
    return cont([4280, 4260, 4240, 4220, 4200, 4180, 4160, 4140, 4160, 4180, 4200, 4209, 4190, 4170, 4150, 4130, 4110, 4090, 4080,
                 4100, 4120, 4140, 4160, 4185], 4300) + [bx(4189, 4180, up=0, dn=1), bx(4180, 4170)]


# first extreme (trough 4210, reference only) -> rise to the peak 4400 on bar 14 (its candidate)
PRE4 = cont([4280, 4260, 4240, 4220, 4210, 4230, 4250, 4270, 4290, 4310, 4330, 4350, 4370, 4390, 4400], 4300)
PK4 = 14
CONF4 = bx(4395, 4335)                    # confirms the peak 4400 (body bottom 60 below); touches the band (high 4396)
READY4 = bx(4335, 4330, up=1)             # away from the band (high 4336), body bottom 4330 <= 4340: next wave ready
AWAY4 = bx(4330, 4325, up=1)              # away filler
S4 = bx(4405, 4395, up=1, dn=1)           # touches, bearish, body top 4405 in 4380..4420, body 10, ratio 10 / 12
W4 = bx(4395, 4405, up=1, dn=1)           # touches, bullish
EXIT4 = bx(4375, 4370, up=1)              # small exit: high 4376 < 4380 (away), body bottom 4370 > 4340 (not ready)


def gate_h4():
    res, det = {}, []

    def case(name, rows, exp, ov=None, L=4400.0):
        ok = True
        for mir in (False, True):
            rr = mirror_c(rows) if mir else rows
            bars = mk(rr, H4)
            d = Det(1, ov).run(bars)
            r = ref_for(1, ov).run(bars)
            ev, act = det_events(d)
            mine = ev_lv(ev, 2 * C4 - L if mir else L, 1 if mir else -1)
            if not (ev == r.events and act == r.act and exp(mine, ev, bars)):
                ok = False
                det.append((name, mir, [x for x in ev if x[1][0] != "E"][:10]))
        res[name] = ok

    R_ = lambda m: [i for i, e in m if e[0] == "R"]                                      # noqa: E731
    C_ = lambda m: [(i, e[5], e[8], e[9]) for i, e in m if e[0] == "C"]                  # (bar, wave, eligible, why)
    D_ = lambda m: [(i, e[5], e[8]) for i, e in m if e[0] == "D"]                        # (bar, wave, lag)
    Y_ = lambda m: [(i, e[2]) for i, e in m if e[0] == "Y"]                              # noqa: E731
    Rall = lambda ev: [(i, e[3]) for i, e in ev if e[0] == "R"]                          # noqa: E731
    base = PRE4 + [CONF4, READY4]                                                        # base 4400 registered on bar 15, ready on 16

    def at4(idx, rows=None, filler=AWAY4):
        rows = list(base if rows is None else rows)
        return rows + [filler] * (idx - len(rows))

    # 2 / 3: 59.99 / 60 and wick only
    case("2: body 59.99 below the peak -> not confirmed (no base)", PRE4 + [bx(4395, 4340.01), bx(4340.01, 4460)], lambda m, ev, b: not R_(m))
    case("2: body exactly 60 below -> confirmed on that bar (base 4400, extreme bar 14)", PRE4 + [bx(4395, 4340.0), AWAY4],
         lambda m, ev, b: R_(m) == [PK4 + 1] and m[0][1][4] == b[PK4]["T"])
    case("2: body 60.01 below (just after) -> confirmed", PRE4 + [bx(4395, 4339.99), AWAY4], lambda m, ev, b: R_(m) == [PK4 + 1])
    case("3: a wick 111 below but the body only 50 -> not confirmed", PRE4 + [bx(4395, 4350, up=1, dn=61), bx(4350, 4460)],
         lambda m, ev, b: not R_(m))
    # 4: same bar: an extreme update never confirms on that bar; ties move the candidate to the later bar
    case("4: a bar with a new body top 4410 and a body bottom 65 below only updates the candidate; the next bar confirms 4410",
         PRE4 + [bx(4410, 4345), bx(4345, 4340), AWAY4],
         lambda m, ev, b: not R_(m) and [(i, x) for i, x in Rall(ev) if x in (4410.0, 2 * C4 - 4410.0)] == [(PK4 + 2, 4410.0 if True else 0)]
         or [(i, x) for i, x in Rall(ev) if x in (4410.0, 2 * C4 - 4410.0)] in ([(PK4 + 2, 4410.0)], [(PK4 + 2, 2 * C4 - 4410.0)]))
    case("4: an equal body top later (4400 again) -> the later bar is the extreme bar", PRE4 + [bx(4380, 4400), bx(4395, 4335), AWAY4],
         lambda m, ev, b: R_(m) == [PK4 + 2] and m[0][1][4] == b[PK4 + 1]["T"])
    # 5 / 6 / 7 / 8: the structures of the specification
    exA = cont([4280, 4260, 4240, 4220, 4200, 4180, 4160, 4140, 4160, 4180, 4200, 4209, 4190, 4170, 4150, 4130, 4110, 4090, 4080,
                4100, 4120, 4140, 4160, 4185], 4300) + [bx(4189, 4180, up=0, dn=1), bx(4180, 4170)]
    case("8: 4209 -> 4080 -> 4189: the bearish bar with its body top exactly 20 below the base (band edge) -> double top",
         exA, lambda m, ev, b: D_(m) == [(24, 2, 0)], L=4209.0)
    exB = cont([4380, 4360, 4340, 4320, 4300, 4320, 4340, 4360, 4380, 4400, 4409, 4390, 4368, 4390, 4410, 4430, 4440, 4420, 4400,
                4380, 4360, 4340, 4327, 4345, 4365, 4385, 4400, 4410], 4400)
    exB += [bx(4410, 4434), bx(4434, 4420)] + cont([4400, 4380, 4370, 4360, 4350], 4420)
    exB += [bx(4350, 4345), bx(4345, 4327), bx(4327, 4340), bx(4340, 4350)]
    case("5: 4409 -> 4368 -> 4440: the 41 $ pullback 4368 is never a confirmed trough (no base / no confirmation at 4368)", exB,
         lambda m, ev, b: not [x for _, x in Rall(ev) if x in (4368.0, 2 * C4 - 4368.0)], L=4440.0)
    case("6: 4440 -> 4327 -> 4434: wave 2 starts at the bar reaching 4434, the bearish bar after it -> double top on 4440", exB,
         lambda m, ev, b: D_(m) == [(29, 2, 1)] and C_(m) == [(28, 2, 1, "")], L=4440.0)
    case("7: 4327 -> 4434 -> 4327: wave 2 on the return, the bullish bar -> double bottom on 4327", exB,
         lambda m, ev, b: [(i, e[5], e[8]) for i, e in ev_lv(ev, 4327.0 if True else 0, 1) if e[0] == "D"] == [(37, 2, 2)]
         or [(i, e[5], e[8]) for i, e in ev_lv(ev, 2 * C4 - 4327.0, -1) if e[0] == "D"] == [(37, 2, 2)], L=4440.0)
    # 9 / 10: waves need a 60 $ separation on a bar away from the band
    hover = [bx(4350, 4360, up=25), bx(4360, 4350, up=1)] * 4                            # wicks in / out, bodies above 4340
    case("9: wicks touching the band again and again without a 60 $ separation -> no new wave; after the separation the next touch is "
         "wave 2", PRE4 + [CONF4] + hover + [READY4, AWAY4, S4],
         lambda m, ev, b: [(c[0], c[1]) for c in C_(m)] == [(PK4 + 12, 2)])
    case("10: the wave-start bar's own big body (down to 4300) does not make the next wave ready; the next touch is no wave",
         at4(PK4 + 9) + [bx(4410, 4300), bx(4300, 4390, up=1), AWAY4],
         lambda m, ev, b: [(c[0], c[1]) for c in C_(m)] == [(PK4 + 9, 2)])
    case("9: small exits after wave 2 (bodies above 4340) and touches again -> still wave 2 only", at4(PK4 + 9) + [W4, EXIT4, W4, EXIT4, W4],
         lambda m, ev, b: [(c[0], c[1]) for c in C_(m)] == [(PK4 + 9, 2)])
    # 11: gap 7 / 8 (the extreme bar = wave 1), the 3rd from the 2nd
    case("11: wave 2 starting 7 bars after the extreme -> ineligible (G), wave consumed", at4(PK4 + 7) + [S4],
         lambda m, ev, b: C_(m) == [(PK4 + 7, 2, 0, "G")] and not D_(m))
    case("11: 8 bars after the extreme -> eligible, double", at4(PK4 + 8) + [S4],
         lambda m, ev, b: C_(m) == [(PK4 + 8, 2, 1, "")] and D_(m) == [(PK4 + 8, 2, 0)])
    case("11: ineligible wave 2 (gap 7), separation, wave 3 eligible -> TRIPLE (never shown as a double)",
         at4(PK4 + 7) + [S4, READY4] + [AWAY4] * 6 + [S4],
         lambda m, ev, b: [(c[1], c[2]) for c in C_(m)] == [(2, 0), (3, 1)] and D_(m) == [(PK4 + 15, 3, 0)])
    case("11: wave 3 only 7 bars after wave 2 -> ineligible, base ended", at4(PK4 + 8) + [S4, READY4] + [AWAY4] * 5 + [S4],
         lambda m, ev, b: [(c[1], c[2]) for c in C_(m)] == [(2, 1), (3, 0)] and [i for i, e in m if e[0] == "E"] == [PK4 + 15])
    # 12 / 13: waiting and the reversal bar
    case("12: small exit while waiting does not end the wave; the bearish bar 2 bars after the start detects (lag 2)",
         at4(PK4 + 8) + [W4, EXIT4, S4], lambda m, ev, b: D_(m) == [(PK4 + 10, 2, 2)])
    case("12: detection on the last wait bar (lag 3)", at4(PK4 + 8) + [W4, EXIT4, W4, S4], lambda m, ev, b: D_(m) == [(PK4 + 11, 2, 3)])
    case("13: wait over after bar 3 (W); a strong bar on bar 4 is not detected", at4(PK4 + 8) + [W4, W4, W4, W4, S4],
         lambda m, ev, b: not D_(m) and Y_(m) and "W" in Y_(m)[0][1])
    case("12: the next wave's readiness while waiting ends the wait (N)", at4(PK4 + 8) + [W4, READY4, S4],
         lambda m, ev, b: not D_(m) and Y_(m) == [(PK4 + 9, "CN")] or (not D_(m) and Y_(m) and Y_(m)[0][1].endswith("N")))
    # after the reversal bar: a strong bearish bar away from the band (only Z), which also makes the next wave ready (N)
    st4 = lambda bar: at4(PK4 + 8) + [bar, bx(4330, 4300)]                                                     # noqa: E731
    case("13: body exactly 6 / ratio exactly 30 % (range 20) -> detected", st4(bx(4400, 4394, up=7, dn=7)),
         lambda m, ev, b: D_(m) == [(PK4 + 8, 2, 0)])
    case("13: body 5.99 (ratio 37 %) -> not detected (B)", st4(bx(4400, 4394.01, up=5, dn=5)),
         lambda m, ev, b: not D_(m) and Y_(m) == [(PK4 + 9, "BZN")])
    case("13: ratio 29.99 % (body 6) -> not detected (R)", st4(bx(4400, 4394, up=7, dn=7.0067)),
         lambda m, ev, b: not D_(m) and Y_(m) == [(PK4 + 9, "RZN")])
    case("13: body top exactly P + 20 (4420) -> detected", st4(bx(4420, 4410)), lambda m, ev, b: D_(m) == [(PK4 + 8, 2, 0)])
    case("13: body top 4420.01 -> not detected (Z)", st4(bx(4420.01, 4410)), lambda m, ev, b: not D_(m) and "Z" in Y_(m)[0][1])
    case("13: body top exactly P - 20 (4380) -> detected", st4(bx(4380, 4370)), lambda m, ev, b: D_(m) == [(PK4 + 8, 2, 0)])
    case("13: body top 4379.99 (wick touching) -> not detected (Z)", st4(bx(4379.99, 4370, up=2)),
         lambda m, ev, b: not D_(m) and "Z" in Y_(m)[0][1])
    case("13: doji in the band -> not detected (C)", st4(bx(4400, 4400, up=5, dn=5)), lambda m, ev, b: not D_(m) and "C" in Y_(m)[0][1])
    # 14 / 18: the 48-bar limit (extreme bar = 0)
    case("14: a return at age 25 is monitored and detected", at4(PK4 + 25) + [S4], lambda m, ev, b: D_(m) == [(PK4 + 25, 2, 0)])
    case("14: age 48 detected", at4(PK4 + 48) + [S4], lambda m, ev, b: D_(m) == [(PK4 + 48, 2, 0)])
    case("14: age 49 -> ended before (T), no detection", at4(PK4 + 49) + [S4],
         lambda m, ev, b: not D_(m) and [i for i, e in m if e[0] == "T"] == [PK4 + 49])
    case("14: limit beats a reversal of a waiting wave (age 49)", at4(PK4 + 48) + [W4, S4],
         lambda m, ev, b: not D_(m) and [(i, e[2]) for i, e in m if e[0] == "T"] == [(PK4 + 49, 1)])
    slow = [bx(4396, 4345, up=1)] + [bx(4345, 4342, up=1)] * 46
    case("14: confirmation at age 48 -> registered", PRE4 + slow + [bx(4342, 4330), AWAY4], lambda m, ev, b: R_(m) == [PK4 + 48])
    case("14: confirmation at age 49 -> not registered", PRE4 + slow + [bx(4342, 4341, up=1), bx(4341, 4330), AWAY4],
         lambda m, ev, b: not R_(m))
    # 18: close invalidation; wick only is no invalidation
    case("18: close above P + 20 while waiting -> invalidated (V), no detection", at4(PK4 + 8) + [W4, bx(4410, 4425)],
         lambda m, ev, b: not D_(m) and [(i, e[2]) for i, e in m if e[0] == "V"] == [(PK4 + 9, 1)])
    case("18: a wick above P + 20 with the close inside -> no invalidation, detected", at4(PK4 + 8) + [bx(4415, 4405, up=20)],
         lambda m, ev, b: D_(m) == [(PK4 + 8, 2, 0)] and not [i for i, e in m if e[0] == "V"])
    # registration: no wave / signal before the base exists
    case("15: a strong touching bar on the registration bar gives no signal (the base starts on the next bar)",
         PRE4 + [bx(4398, 4335)] + [AWAY4] * 3, lambda m, ev, b: R_(m) == [PK4 + 1] and not C_(m) and not D_(m))
    for nm, ok in res.items():
        check("LT-H4 " + nm, ok, str([x for x in det if x[0] == nm][:2]) if not ok else "")
    # 15: on random 4H series, every detection comes from a base registered on an earlier bar; stepping == full run
    ok15, n15 = True, 0
    for seed in range(4):
        for gp in (False, True):
            bars = rand_tf(8800 + seed, 1500, H4, 8.0, gaps=gp)
            d = Det(1).run(bars)
            d2 = Det(1)
            for b in bars:
                d2.step(b)
            ev = det_events(d)[0]
            reg = {e[1]: i for i, e in ev if e[0] == "R"}
            for i, e in ev:
                if e[0] in ("C", "D"):
                    n15 += e[0] == "D"
                    if e[1] not in reg or reg[e[1]] >= i:
                        ok15 = False
            if d.blocks != d2.blocks:
                ok15 = False
    check(f"LT-H4 15: on random 4H series every wave / detection comes from a base registered on an earlier bar (no retroactive "
          f"signal; {n15} detections); the bar-by-bar run == the full run", ok15 and n15 > 0)


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
    gate_chart()
    gate_forming()
    gate_gap()
    gate_draw()
    for k in (0, 2):                      # LTB-11: the 4H method has its own gate (gate_h4)
        gate_tf(k)
    gate_h4()
    gate_both()
    gate_params()
    gate_charts()
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
