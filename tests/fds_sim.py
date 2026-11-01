"""FDS-1 — FVGDepthStats.pine: local checks of the statistics logic.

What runs: the text between "// ==== FDS Logic (begin)" and "// ==== FDS Logic (end)" of FVGDepthStats.pine, translated
mechanically by tests/acc_pine.py (Translator / logical_lines; that file is imported, not changed). Bars are fed as
confirmed chart bars; the series values the logic reads from outside the section (fdsRun / fdsValid / fdsFormOk /
fdsH2 / fdsL2 / fdsPrevTc / fdsMt) are set by the runner the way the Pine lines above the section define them.

Independent oracle: ref_model() below, a naive O(bars x FVGs) re-statement of the spec (no sorted waiting lists, exact
Fraction percentages), compared with the translated Pine on hand-made cases and random series.

Evidence class: PINE_NOT_VERIFIED. TradingView's compiler, chart.is_standard / timeframe gate, barstate / timenow,
drawing (boxes) and the table are NOT executed here; only static text checks cover them.
"""
import copy
import os
import random
import re
import sys
from fractions import Fraction

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import acc_pine as ap  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PINE = os.path.join(ROOT, "FVGDepthStats.pine")
BEGIN, END = "// ==== FDS Logic (begin)", "// ==== FDS Logic (end)"
H4 = 4 * 3600_000
T0 = 1_600_000_000_000
FIELDS = ["FORM", "TFVG", "N", "R", "B", "X", "UGAP", "UDAT", "MULT", "GSPN"] + [f"BK{i}" for i in range(10)] + ["OVER", "U"]

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


def src():
    return open(PINE, encoding="utf-8").read()


def logic(text):
    i, j = text.index(BEGIN), text.index(END)
    return text[text.index("\n", i) + 1:j]


# ============================================================================
# runner: the translated Pine logic
# ============================================================================
class Run:
    def __init__(self, overrides=None, mt=0.1, text=None):
        text = text if text is not None else src()
        self.code = compile(ap.Translator().translate(ap.logical_lines(logic(text))), "<FDS logic>", "exec")
        self.inp = ap.inputs(text)
        for k in overrides or {}:
            if k not in self.inp:
                raise KeyError(k)
        self.inp.update(overrides or {})
        env = ap.make_env(ap.Broker(), [])
        env.update(self.inp)

        def a_insert(arr, i, v):
            if i < 0 or i > len(arr):
                raise ap.PineRuntimeError("insert out of bounds")
            arr.insert(i, v)

        def a_pop(arr):
            if not arr:
                raise ap.PineRuntimeError("pop on empty")
            return arr.pop()

        env.update(array__insert=a_insert, array__pop=a_pop,
                   math__round_to_mintick=lambda x: None if x is None else ap._pine_round(x / mt) * mt)
        env["_VARS"], env["_VARIPS"], env["__first__"] = set(), set(), True
        self.env, self.mt = env, mt
        self.hist = []          # (valid, h, l, tclose) of executed bars

    def _exec(self):
        exec(self.code, self.env)
        self.env["__first__"] = False

    def bar(self, b, confirmed=True, supported=True):
        """b = dict(t, o, h, l, c, dur?) ; a bar with o/h/l/c None or inconsistent is invalid data."""
        e = self.env
        # Pine: an unconfirmed (realtime) execution is rolled back before the next one -> snapshot / restore around it
        snap = None if confirmed or e["__first__"] else {k: copy.deepcopy(e[k]) for k in e["_VARS"]}
        o, h, l, c = b["o"], b["h"], b["l"], b["c"]
        valid = None not in (o, h, l, c) and h >= l and h >= max(o, c) and l <= min(o, c)
        v1 = self.hist[-1][0] if len(self.hist) >= 1 else False
        v2 = self.hist[-2][0] if len(self.hist) >= 2 else False
        e.update(open=o, high=h, low=l, close=c, time=b["t"], fdsRun=supported and confirmed, fdsValid=valid,
                 fdsFormOk=valid and v1 and v2, fdsMt=self.mt,
                 fdsH2=self.hist[-2][1] if len(self.hist) >= 2 else None,
                 fdsL2=self.hist[-2][2] if len(self.hist) >= 2 else None,
                 fdsPrevTc=self.hist[-1][3] if self.hist else None)
        self._exec()
        if snap is not None:
            for k, v in snap.items():
                e[k] = v
        if confirmed:
            self.hist.append((valid, h, l, b["t"] + b.get("dur", H4)))
        return self

    def run(self, bars):
        for b in bars:
            self.bar(b)
        return self

    def st(self, d):
        a = self.env["fdsSt"]
        return dict(zip(FIELDS, a[0:22] if d == 1 else a[22:44]))

    def __getitem__(self, k):
        return self.env[k]


# ============================================================================
# independent reference model of the spec
# ============================================================================
def ref_model(bars, min_width=3.0, repeat=False, mt=0.1, gap_days=3.0):
    tk = lambda p: round(p / mt)
    S = {1: {f: 0 for f in FIELDS}, -1: {f: 0 for f in FIELDS}}
    fv = []         # dict(dir, top, bot, state 'wait'|'touch'|'end', ext, nc, gsp, rearm_bar)
    hist = []
    for bi, b in enumerate(bars):
        o, h, l, c = b["o"], b["h"], b["l"], b["c"]
        valid = None not in (o, h, l, c) and h >= l and h >= max(o, c) and l <= min(o, c)
        gap = bool(hist) and b["t"] - hist[-1]["tc"] > gap_days * 86400000
        if not valid:
            for f in fv:
                if f["state"] == "touch":
                    S[f["dir"]]["X"] += 1
                    f["state"] = "end"
                elif f["state"] == "wait":
                    S[f["dir"]]["UDAT"] += 1
                    f["state"] = "end"
        else:
            new = {1: 0, -1: 0}
            for f in fv:
                d, top, bot = f["dir"], f["top"], f["bot"]
                if f["state"] == "end":
                    continue
                if f["state"] == "wait":
                    touched = l <= top if d == 1 else h >= bot
                    if not touched:
                        continue
                    if (d == 1 and o < bot) or (d == -1 and o > top):
                        S[d]["UGAP"] += 1
                        f["state"] = "end"
                        continue
                    if f["nc"] == 0:
                        S[d]["TFVG"] += 1
                    f["nc"] += 1
                    S[d]["N"] += 1
                    new[d] += 1
                    f["state"], f["ext"], f["gsp"] = "touch", (l if d == 1 else h), False
                else:
                    if gap and not f["gsp"]:
                        f["gsp"] = True
                        S[d]["GSPN"] += 1
                    f["ext"] = min(f["ext"], l) if d == 1 else max(f["ext"], h)
                rebound = c > top if d == 1 else c < bot
                broke = c < bot if d == 1 else c > top
                if rebound:
                    pen = Fraction(tk(top - f["ext"]) if d == 1 else tk(f["ext"] - bot), tk(top - bot)) * 100
                    S[d]["R"] += 1
                    if pen > 100:
                        S[d]["OVER"] += 1
                    elif pen == 100:
                        S[d]["BK9"] += 1
                    else:
                        S[d][f"BK{int(pen // 10)}"] += 1
                    if repeat:
                        f["state"] = "wait"
                    else:
                        f["state"] = "end"
                elif broke:
                    S[d]["B"] += 1
                    f["state"] = "end"
            for d in (1, -1):
                if new[d] >= 2:
                    S[d]["MULT"] += 1
            if len(hist) >= 2 and hist[-1]["valid"] and hist[-2]["valid"]:
                h2, l2 = hist[-2]["h"], hist[-2]["l"]
                bull, bear = l > h2, h < l2
                if bull or bear:
                    top, bot = (l, h2) if bull else (l2, h)
                    if round((top - bot) / mt) * mt >= min_width and tk(top - bot) >= 1:
                        d = 1 if bull else -1
                        fv.append(dict(dir=d, top=top, bot=bot, state="wait", ext=None, nc=0, gsp=False))
                        S[d]["FORM"] += 1
        for d in (1, -1):
            S[d]["U"] = sum(1 for f in fv if f["state"] == "touch" and f["dir"] == d)
        hist.append(dict(valid=valid, h=h, l=l, tc=b["t"] + b.get("dur", H4)))
    return S


# a rebound in repeat mode must not re-touch on the rebound bar: the loop above visits each FVG once per bar, so the
# rebound bar cannot re-arm-and-touch (state 'wait' is set after this bar's visit). Next bar it is visited again.


# ============================================================================
# bar helpers (mt = 0.1 unless stated)
# ============================================================================
def B(o, h, l, c, i=None):
    return dict(o=o, h=h, l=l, c=c)


def timed(seq, t0=T0, step=H4):
    out = []
    t = t0
    for b in seq:
        b = dict(b)
        t = b.pop("t", t)
        b["t"] = t
        out.append(b)
        t += step
    return out


# bull FVG: bar0 high 100, bar2 low 104 -> top 104, bottom 100 (width 4.0 = 40 ticks), registered at bar2's close
BULL = [B(98, 100, 95, 99), B(99, 106, 98.5, 105.5), B(105.5, 108, 104, 107)]
# bear FVG (mirror around 200): bar0 low 100, bar2 high 96 -> top 100, bottom 96
BEAR = [B(102, 105, 100, 101), B(101, 101.5, 94, 94.5), B(94.5, 96, 92, 93)]


def mirror(seq, k=200.0):
    return [dict(b, o=None if b["o"] is None else round(k - b["o"], 6), h=None if b["l"] is None else round(k - b["l"], 6),
                 l=None if b["h"] is None else round(k - b["h"], 6), c=None if b["c"] is None else round(k - b["c"], 6))
            for b in seq]


def run(seq, **ov):
    mt = ov.pop("mt", 0.1)
    return Run(ov, mt=mt).run(timed(seq))


def ref(seq, **ov):
    return ref_model(timed(seq), min_width=ov.get("minWidth", 3.0), repeat=ov.get("repeatMode", False), mt=ov.get("mt", 0.1))


def nz_fields(s):
    return {k: v for k, v in s.items() if v}


# ============================================================================
# gates
# ============================================================================
def gate_static():
    t = src()
    zx = open(os.path.join(ROOT, "ZoneStrategyXAU.pine"), encoding="utf-8").read()
    ref_fn = zx[zx.index("f_fvgConfirmed(float minWidth) =>"):]
    ref_fn = ref_fn[:ref_fn.index("\n\n")]
    want = ["bool  _bull = low > high[2]", "bool  _bear = high < low[2]", "float _top  = _bull ? low : _bear ? low[2] : na",
            "float _bot  = _bull ? high[2] : _bear ? high : na",
            "int   _dir  = (_bull or _bear) and math.round_to_mintick(_top - _bot) >= minWidth ? (_bull ? 1 : -1) : 0",
            "[time[1], time_close[1], close[1], _dir[1], _top[1], _bot[1]]"]
    check("FS-01 reference: ZoneStrategyXAU.pine f_fvgConfirmed has exactly the spec formula (+ the [1] HTF delivery)",
          all(w in ref_fn for w in want))
    lg = logic(t)
    mine = ["bool _bull = low > fdsH2", "bool _bear = high < fdsL2", "float _top = _bull ? low : _bear ? fdsL2 : na",
            "float _bot = _bull ? fdsH2 : _bear ? high : na",
            "int _dir = (_bull or _bear) and math.round_to_mintick(_top - _bot) >= minWidth ? (_bull ? 1 : -1) : 0"]
    check("FS-02 this file: the same formula on the chart bar (high[2] / low[2] passed as fdsH2 / fdsL2, no [1] delay)",
          all(m in lg for m in mine) and "float fdsH2     = high[2]" in t and "float fdsL2     = low[2]" in t
          and not re.search(r"\w\[\d\]", lg))
    code = "\n".join(ap.strip_comment(x) for x in t.split("\n"))
    bad = [w for w in ("strategy.", "strategy(", "alert", "request.", "import ", "plotshape", "plotchar") if w in code]
    check("FS-03 indicator only: no strategy / alert / request / import / signal plots", not bad and "indicator(" in code, str(bad))
    check("FS-04 gate: 240-minute / 1D / 1W standard candles only; unconfirmed / unfinished last bar not counted",
          "(timeframe.isminutes and timeframe.multiplier == 240) or (timeframe.isdaily and timeframe.multiplier == 1)" in code
          and "(timeframe.isweekly and timeframe.multiplier == 1)" in code and "chart.is_standard" in code
          and "barstate.isconfirmed and (barstate.isrealtime or na(time_close) or time_close <= timenow)" in code
          and "bool fdsRun     = fdsSupported and fdsConfirmed" in code)
    check("FS-05 defaults: minWidth 3.0, first contact only, gap 3 days, 50 drawn boxes",
          ap.inputs(t) == dict(minWidth=3.0, repeatMode=False, gapDays=3.0, showTable=True, tablePos="右上", drawBoxes=True,
                               drawMax=50), str(ap.inputs(t)))
    others = [p for p in os.listdir(ROOT) if p.endswith(".pine") and p != "FVGDepthStats.pine"]
    import subprocess
    diff = subprocess.run(["git", "-C", ROOT, "status", "--porcelain", "--"] + others, capture_output=True, text=True).stdout
    check("FS-06 no other Pine file changed", diff.strip() == "", diff)


def gate_basic():
    # formation bar not a contact (its low == top by definition)
    r = run(BULL + [B(107, 109, 106, 108)])
    s = r.st(1)
    check("FS-10 bull FVG registered at the formation bar's close with top = low, bottom = high[2]; formation bar not a contact",
          s["FORM"] == 1 and s["N"] == 0 and r["fTop"] == [104] and r["fBot"] == [100] and r["fState"] == [0])
    r = run(BULL[:2] + [B(105.5, 108, 104, 107)])
    check("FS-11 registration on the third bar itself (no extra 1-bar delay): fdsNewId = 0 on that bar", r["fdsNewId"] == 0)
    # same-bar contact -> rebound
    s = run(BULL + [B(107, 107.5, 102.5, 105)]).st(1)
    check("FS-12 same-bar contact and close back above top = 1 rebound (35 % -> 30-40 %)",
          s["N"] == 1 and s["R"] == 1 and s["BK3"] == 1 and s["TFVG"] == 1 and s["U"] == 0)
    # multi-bar max penetration
    s = run(BULL + [B(107, 107, 103, 103.5), B(103.5, 104, 102, 103), B(103, 105.5, 102.5, 105)]).st(1)
    check("FS-13 max penetration across bars (25 % -> 50 % -> 37.5 %, rebound) = 50 % -> 50-60 %",
          s["N"] == 1 and s["R"] == 1 and s["BK5"] == 1 and sum(s[f"BK{i}"] for i in range(10)) == 1)
    # boundary closes
    s = run(BULL + [B(107, 107, 103, 104)]).st(1)
    check("FS-14 close == top: not a rebound (contact continues, U = 1)", s["N"] == 1 and s["R"] == 0 and s["U"] == 1)
    s = run(BULL + [B(107, 107, 99, 100)]).st(1)
    check("FS-15 close == bottom: not a break (U = 1)", s["N"] == 1 and s["B"] == 0 and s["U"] == 1)
    s = run(BULL + [B(107, 107, 103, 104.1)]).st(1)
    check("FS-16 close one tick above top: rebound", s["R"] == 1 and s["U"] == 0)
    s = run(BULL + [B(107, 107, 99, 99.9)]).st(1)
    r = run(BULL + [B(107, 107, 99, 99.9), B(99.9, 104.5, 99, 104.5)])
    check("FS-17 close one tick below bottom: break B, observation ends (no later contact)",
          s["B"] == 1 and s["R"] == 0 and r.st(1)["N"] == 1 and r["fState"] == [2] and r["fEndWhy"] == [2])
    # symmetry, bear
    s = run(BEAR + [B(93, 97.5, 92.5, 95)]).st(-1)
    check("FS-18 bear: touch from below, (high - bottom) / width: 37.5 % -> 30-40 %, close < bottom = rebound",
          s["N"] == 1 and s["R"] == 1 and s["BK3"] == 1)
    seq = BULL + [B(107, 107, 103, 103.5), B(103.5, 104, 102, 103), B(103, 105.5, 102.5, 105), B(105, 106, 99.5, 99.8)]
    a, m = run(seq), run(mirror(seq))
    check("FS-19 mirrored series: bull stats == bear stats of the mirror and vice versa", a.st(1) == m.st(-1) and a.st(-1) == m.st(1),
          f"{nz_fields(a.st(1))} {nz_fields(m.st(-1))}")


def gate_buckets():
    # width 40 ticks; low = top - k ticks -> k / 40
    cases = [(0, "BK0"), (3, "BK0"), (4, "BK1"), (8, "BK2"), (36, "BK9"), (39, "BK9"), (40, "BK9"), (41, "OVER"), (80, "OVER")]
    bad = []
    for k, want in cases:
        lo = round(104 - k * 0.1, 1)
        s = run(BULL + [B(107, 107, lo, 105)]).st(1)
        got = [f for f in FIELDS if f.startswith(("BK", "OVER")) and s[f]]
        if got != [want] or s["R"] != 1:
            bad.append((k, got))
    check("FS-20 bucket edges: 0 % / 7.5 % -> 0-10, exactly 10 % -> 10-20, 20 % -> 20-30, 90 % / 97.5 % / exactly 100 % -> 90-100, "
          "102.5 % / 200 % -> over-100 (rebound by close, not a break)", not bad, str(bad))
    # floating point: mintick 0.01, width 3.10 (310 ticks), penetration 0.93 = exactly 30 % (0.93 / 3.1 in floats = 0.3000000004)
    bars = [B(2000, 2000.00, 1995, 1999), B(1999, 2005, 1998, 2004.5), B(2004.5, 2006, 2003.10, 2005)]
    bad = []
    for pen_t in (31, 93, 155, 217, 279, 310, 92, 94):
        lo = round(2003.10 - pen_t * 0.01, 2)
        s = run(bars + [B(2005, 2005, lo, 2004)], mt=0.01).st(1)
        want = "OVER" if pen_t > 310 else "BK9" if pen_t == 310 else f"BK{(10 * pen_t) // 310}"
        got = [f for f in FIELDS if f.startswith(("BK", "OVER")) and s[f]]
        if got != [want]:
            bad.append((pen_t, got, want))
    check("FS-21 float-safe bucket: mintick 0.01, width 3.10, penetration 10 / 30 / 50 / 70 / 90 / 100 % exactly and ±1 tick "
          "land in the integer-tick bucket", not bad, str(bad))
    # break vs over-100 rebound
    s1 = run(BULL + [B(107, 107, 98, 104.5)]).st(1)
    s2 = run(BULL + [B(107, 107, 98, 99.5)]).st(1)
    s3 = run(BULL + [B(107, 107, 98, 101), B(101, 105, 100.5, 104.5)]).st(1)
    check("FS-22 wick beyond the far side + close back above top = over-100 rebound; close below bottom = break; wick beyond then "
          "close inside then rebound next bar = over-100 rebound (max penetration kept)",
          s1["OVER"] == 1 and s1["B"] == 0 and s2["B"] == 1 and s2["R"] == 0 and s3["OVER"] == 1 and s3["B"] == 0)


def gate_repeat():
    seq = BULL + [B(107, 107, 103, 105), B(105, 106, 104.5, 105.5), B(105.5, 106, 102, 104.5), B(104.5, 105, 101, 103)]
    s1, s2 = run(seq).st(1), run(seq, repeatMode=True).st(1)
    check("FS-30 first only (default): 1 contact; repeat ON: 2 contacts, 2nd max penetration reset (25 % then 50 %), "
          "then a 3rd still open (U)",
          s1["N"] == 1 and s1["R"] == 1 and s1["BK2"] == 1 and s1["TFVG"] == 1
          and s2["N"] == 3 and s2["R"] == 2 and s2["BK2"] == 1 and s2["BK5"] == 1 and s2["U"] == 1 and s2["TFVG"] == 1,
          f"{nz_fields(s1)} {nz_fields(s2)}")
    # rebound bar: low in zone, close above -> must not re-arm and re-touch inside the same bar
    seq = BULL + [B(107, 107, 103, 105), B(105, 106, 105, 105.5)]
    s = run(seq, repeatMode=True).st(1)
    check("FS-31 repeat ON: the rebound bar itself is 1 contact (no re-arm inside it); a later bar not touching adds nothing",
          s["N"] == 1 and s["R"] == 1 and s["U"] == 0)
    s = run(BULL + [B(107, 107, 103, 105), B(105, 106, 104, 105)], repeatMode=True).st(1)
    check("FS-32 repeat ON: the bar after the rebound touching top (0 %) = next contact", s["N"] == 2 and s["R"] == 2 and s["BK0"] == 1)
    s = run(BULL + [B(107, 107, 103, 103.5), B(103.5, 104.5, 103, 104.5), B(104.5, 105, 103.8, 104)], repeatMode=True).st(1)
    check("FS-33 inside one contact a bar closing exactly at top is not an exit (still the same contact)",
          s["N"] == 2 and s["R"] == 1 and s["U"] == 1, str(nz_fields(s)))


def gate_unknown():
    # gap: bar opens below bottom (jumped over the whole FVG)
    s = run(BULL + [B(107.5, 108, 107, 107.5), B(98, 99, 97, 98.5)]).st(1)
    check("FS-40 gap over the whole FVG (open below bottom): not a contact (N = 0), unknown FVG (gap) = 1, observation ends",
          s["N"] == 0 and s["UGAP"] == 1 and s["TFVG"] == 0 and s["R"] + s["B"] + s["U"] + s["X"] == 0)
    s = run(BULL + [B(107.5, 108, 107, 107.5), B(102, 105, 101, 104.5)]).st(1)
    check("FS-41 gap INTO the zone (open inside, from the entry side): a normal contact (penetration from the low)",
          s["N"] == 1 and s["R"] == 1 and s["BK7"] == 1 and s["UGAP"] == 0)
    s = run(BULL + [B(107, 107, 103, 103.5), B(None, None, None, None)]).st(1)
    check("FS-42 invalid data bar during a contact: undecidable X (not R / B), N = R + B + U + X",
          s["N"] == 1 and s["X"] == 1 and s["R"] == 0 and s["U"] == 0)
    r = run(BULL + [B(107, 108, 106, 107), B(107, 106, 108, 107), B(107, 107.5, 103, 105)])
    s = r.st(1)
    check("FS-43 invalid data bar while waiting (high < low): unknown FVG (data), no contact counted later, no FVG formed using it",
          s["UDAT"] == 1 and s["N"] == 0 and s["FORM"] == 1 and r["fdsBadN"] == 1)
    # two FVGs touched by one bar
    seq = [B(98, 100, 95, 99), B(99, 106, 98.5, 105.5), B(105.5, 108, 104, 107), B(107, 112, 106.5, 111.5), B(111.5, 115, 111, 114),
           B(114, 114.5, 102, 112)]
    s = run(seq).st(1)
    check("FS-44 one bar touching 2 bull FVGs: one contact per FVG (N = 2, TFVG = 2) and MULT = 1",
          s["FORM"] == 2 and s["N"] == 2 and s["TFVG"] == 2 and s["MULT"] == 1 and s["R"] == 2, str(nz_fields(s)))
    # tail unresolved
    s = run(BULL + [B(107, 107, 103, 103.5)]).st(1)
    check("FS-45 contact unresolved at the data end: U = 1, N = R + B + U + X", s["U"] == 1 and s["N"] == 1)
    # gap-span (informational)
    seq = timed(BULL + [B(107, 107, 103, 103.5)])
    seq.append(dict(o=103.5, h=105, l=102, c=104.5, t=seq[-1]["t"] + 5 * 86400000))
    r = Run().run(seq)
    check("FS-46 time gap > 3 days: counted (fdsGapN), contact spanning it flagged (GSPN) but still classified normally",
          r["fdsGapN"] == 1 and r.st(1)["GSPN"] == 1 and r.st(1)["R"] == 1)


def rand_series(rng, n, mt=0.1, start=2000.0, vol=6.0, bad_p=0.0, gap_p=0.0):
    out, p, t = [], start, T0
    for _ in range(n):
        o = p + (rng.choice([0, 0, 0, rng.uniform(-3 * vol, 3 * vol)]) if rng.random() < 0.1 else 0)
        c = o + rng.gauss(0, vol)
        h = max(o, c) + abs(rng.gauss(0, vol * 0.6))
        l = min(o, c) - abs(rng.gauss(0, vol * 0.6))
        q = lambda x: round(round(x / mt) * mt, 6)
        b = dict(o=q(o), h=q(h), l=q(l), c=q(c), t=t)
        if rng.random() < bad_p:
            b.update(rng.choice([dict(o=None, h=None, l=None, c=None), dict(h=b["l"] - mt)]))
        out.append(b)
        t += H4 + (rng.randint(2, 6) * 86400000 if rng.random() < gap_p else 0)
        p = c
    return out


def consistent(s):
    return s["N"] == s["R"] + s["B"] + s["U"] + s["X"] and sum(s[f"BK{i}"] for i in range(10)) + s["OVER"] == s["R"] \
        and s["TFVG"] <= s["N"] and s["TFVG"] <= s["FORM"]


def gate_fuzz():
    rng = random.Random(20261101)
    bad, n_cmp, tot = [], 0, {f: 0 for f in FIELDS}
    for it in range(60):
        rep = it % 2 == 1
        mw = rng.choice([1.0, 3.0, 5.0])
        seq = rand_series(rng, rng.randint(80, 260), bad_p=0.01 if it % 3 == 0 else 0.0, gap_p=0.02 if it % 4 == 0 else 0.0)
        r = Run(dict(repeatMode=rep, minWidth=mw)).run(seq)
        m = ref_model(seq, min_width=mw, repeat=rep)
        for d in (1, -1):
            n_cmp += 1
            if r.st(d) != m[d] or not consistent(r.st(d)):
                bad.append((it, d, nz_fields(r.st(d)), nz_fields(m[d])))
            for f in FIELDS:
                tot[f] += r.st(d)[f]
        mm = Run(dict(repeatMode=rep, minWidth=mw)).run([dict(b, **{k: v for k, v in mirror([b])[0].items() if k in "ohlc"})
                                                          for b in seq])
        if mm.st(1) != r.st(-1) or mm.st(-1) != r.st(1):
            bad.append((it, "mirror"))
    check(f"FS-50 60 random series (both modes, min width 1 / 3 / 5, invalid bars and time gaps): translated Pine == "
          f"independent reference model in all {n_cmp} direction tallies, N = R + B + U + X and bucket sum = R every time, "
          f"mirror symmetry holds", not bad, str(bad[:3]))
    check("FS-51 the random series exercised every outcome (R, B, U, X, UGAP, UDAT, MULT, OVER, BK0, BK9)",
          all(tot[f] > 0 for f in ("R", "B", "U", "X", "UGAP", "UDAT", "MULT", "OVER", "BK0", "BK9")), str(tot))


def gate_recalc():
    rng = random.Random(7)
    seq = rand_series(rng, 200)
    a = Run(dict(repeatMode=True)).run(seq)
    b = Run(dict(repeatMode=True)).run(seq)
    c = Run(dict(repeatMode=True))
    for bar in seq:       # realtime-like: unconfirmed executions (fdsRun false) before the confirmed one, var state rolled back
        c.bar(dict(bar, c=bar["o"], h=bar["o"], l=bar["o"]), confirmed=False)
        c.bar(dict(bar, c=bar["h"], l=bar["o"]), confirmed=False)
        c.bar(bar)
    st = lambda r: (r.st(1), r.st(-1), r["fdsBars"], len(r["fTop"]))
    check("FS-60 recalculation: a full rerun gives the same tallies; unconfirmed executions add nothing (each bar counted once)",
          st(a) == st(b) == st(c) and a["fdsBars"] == 200, f"{st(a)} {st(c)}")
    d = Run(dict(repeatMode=True)).run(seq[:-1])
    d.bar(seq[-1], confirmed=False)
    check("FS-61 an unconfirmed last bar is not counted (fdsBars / tallies == the run without it)",
          d["fdsBars"] == 199 and d.st(1) == Run(dict(repeatMode=True)).run(seq[:-1]).st(1))
    e = Run(dict(repeatMode=True)).run(seq[:50])
    e.bar(seq[50], supported=False)
    check("FS-62 unsupported chart (gate false): nothing counted", e["fdsBars"] == 50)


def gate_cap():
    t = src().replace("int FDS_CAP = 90000", "int FDS_CAP = 2")
    rng = random.Random(3)
    seq = rand_series(rng, 300, vol=8)
    r = Run(dict(minWidth=1.0), text=t).run(seq)
    full = Run(dict(minWidth=1.0)).run(seq)
    check("FS-70 registration cap reached: new FVGs stop being registered and fdsHalted = true (shown in the table); the FVGs "
          "already registered keep being observed (none dropped)",
          r["fdsHalted"] and len(r["fTop"]) == 2 and len(full["fTop"]) > 2 and not full["fdsHalted"]
          and r.st(1)["FORM"] + r.st(-1)["FORM"] == 2)


def gate_mutation():
    """the checks above must fail when the logic is changed in plausible wrong ways"""
    t = src()
    muts = [
        ("rebound >= top", "d == 1 ? (c > top ? 1 : c < bot ? 2 : 0)", "d == 1 ? (c >= top ? 1 : c < bot ? 2 : 0)"),
        ("break <= bottom", "c < bot ? 2 : 0) : (c < bot", "c <= bot ? 2 : 0) : (c < bot"),
        ("bucket >", "10 * penT >= (b + 1) * widT", "10 * penT > (b + 1) * widT"),
        ("100 % to over", "if penT <= widT", "if penT < widT"),
        ("touch strict", "array.get(wUpKey, array.size(wUpKey) - 1) >= low", "array.get(wUpKey, array.size(wUpKey) - 1) > low"),
        ("no gap check", "if open < array.get(fBot, id)", "if false"),
        ("re-arm same bar", "            array.set(fState, id, 0)\n            array.push(fdsRearm, id)",
         "            f_wait(id)"),
    ]
    caught = []
    for name, a, b in muts:
        if t.count(a) < 1:
            caught.append((name, "pattern missing"))
            continue
        mt = t.replace(a, b, 1)
        before = len(RESULTS)
        ok = True
        try:
            _src_backup = globals()["src"]
            globals()["src"] = lambda: mt
            for g in (gate_basic, gate_buckets, gate_repeat, gate_unknown, gate_fuzz):
                try:
                    g()
                except Exception:      # noqa: BLE001
                    ok = False
            ok = ok and all(r[1] for r in RESULTS[before:])
        finally:
            globals()["src"] = _src_backup
            del RESULTS[before:]
        caught.append((name, "caught" if not ok else "MISSED"))
    check("FS-80 mutations of the logic (rebound / break strictness, bucket edges, 100 %, touch equality, gap check, re-arm on the "
          "rebound bar) are each caught by the checks", all(c[1] == "caught" for c in caught),
          str(caught))


def main():
    for g in (gate_static, gate_basic, gate_buckets, gate_repeat, gate_unknown, gate_fuzz, gate_recalc, gate_cap, gate_mutation):
        try:
            g()
        except Exception:      # noqa: BLE001
            import traceback
            check(f"{g.__name__} completed without error", False, traceback.format_exc()[-2000:])
    w = max(len(n) for n, _, _ in RESULTS)
    fails = 0
    for n, ok, d in RESULTS:
        fails += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {n.ljust(w)[:170]}  {'' if ok else d}")
    print(f"\n{len(RESULTS) - fails}/{len(RESULTS)} passed  [PINE_NOT_VERIFIED: translated Pine logic section + reference model]")
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
