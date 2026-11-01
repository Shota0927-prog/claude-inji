"""LFW-1 fixtures — LongFibWave.pine (long-term Fibonacci wave indicator, D / 4H).

  LS static   : inputs (switch 0.782, start 0.10, display levels with 0.79 / no 0.786), exactly two request.security calls
                ("D" / "240", every output [1] + lookahead_on), processing gated by barstate.isconfirmed and a new confirmed
                HTF time, no strategy / entry / alert, the logic section inside the translated subset
  LW waves    : the LOGIC SECTION OF THE PINE FILE (translated by tests/acc_pine.py) on hand-made confirmed HTF bars:
                extension, 78.2 % candidate + break = same-direction switch (>= 0.782, 0.781 does not), origin touch vs
                strict break, initialisation (ATR x 3, waits for ATR, never from one bar's high and low)
  LH hold     : no intrabar-order assumption: a bar whose two orders give different waves puts the wave on hold (no
                direction chosen, the open is irrelevant), the candidates advance by the same rules, the hold ends when they
                agree; no observation during the hold, none created afterwards from it, no double count; up / down symmetric
  LO obs      : start at 10 %, fixed denominator, resume / full / switch-end / order-unknown / live, repeated observations,
                resume saved before the same-direction switch (no double count), no observation carried across a switch
  LR random   : translated Pine == an independent reference model written from the spec (records, counters, wave state) on
                random HTF series; mirror symmetry (prices negated -> up / down swapped); counters == records
  LC chart    : 1H chart bars -> 4H bars delivered like request.security([1], lookahead_on): each confirmed 4H bar processed
                once, in order, never before it closed; unconfirmed (realtime) executions change nothing; prefix runs
  LM mutation : mutations of the Pine logic are caught by at least one check

Evidence class: PINE_NOT_VERIFIED (TradingView compile / request.security / drawing not reproduced).
"""
import copy
import os
import random
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import acc_pine as ap        # noqa: E402

# Pine's built-in UDT method `obj.copy()` (shallow copy), used by the logic section; acc_pine's _UDT has no copy()
ap._UDT.copy = lambda self: copy.copy(self)

ROOT = ap.ROOT
PINE = os.path.join(ROOT, "LongFibWave.pine")
SRC = open(PINE, encoding="utf-8").read()
BEGIN, END = "// ==== LFW Logic (begin)", "// ==== LFW Logic (end)"
RESULTS = []
SRC_OVERRIDE = None
H1, H4 = 3_600_000, 14_400_000
T0 = 1_767_225_600_000          # 2026-01-01 00:00 UTC


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


def logic(src):
    i, j = src.index(BEGIN), src.index(END)
    return src[src.index("\n", i) + 1:j]


def transpile(src):
    return ap.Translator().translate(ap.logical_lines(logic(src)))


# ============================================================================
# runner : executes the translated logic section once per chart execution
# ============================================================================
class Run:
    def __init__(self, overrides=None, src=None):
        self.src = src if src is not None else (SRC_OVERRIDE or SRC)
        self.code = compile(transpile(self.src), "<LongFibWave logic>", "exec")
        inp = ap.inputs(self.src)
        for k in (overrides or {}):
            if k not in inp:
                raise KeyError("unknown input " + k)
        inp.update(overrides or {})
        self.env = ap.make_env(ap.Broker(), [])
        self.env.update(inp)
        self.env.update(_VARS=set(), _VARIPS=set(), __first__=True)

    def exec(self, avail, d=None, h4=None):
        """one confirmed chart execution; d / h4 = (h, l, t, atr) of a newly delivered confirmed HTF bar or None."""
        e = self.env
        e["time_close"] = avail
        e["lfwNewD"], e["lfwNew4"] = d is not None, h4 is not None
        for k, v in (("D", d), ("4", h4)):
            hh, ll, tt, aa = v if v is not None else (None,) * 4
            e[f"lfw{k}h"], e[f"lfw{k}l"], e[f"lfw{k}t"], e[f"lfw{k}atr"] = hh, ll, tt, aa
        exec(self.code, e)
        e["__first__"] = False

    def feed4(self, bars, start=0):
        for i, b in enumerate(bars, start):
            t = T0 + i * H4
            self.exec(t + H4 + H1, h4=(b["h"], b["l"], t, b.get("atr", 10.0)))
        return self

    @property
    def S(self):
        return self.env["lfw4"]

    @property
    def W(self):
        return self.env["lfw4"].w

    def recs(self):
        return [r for r in self.S.recs]


def B(h, l, o=None, atr=10.0):
    d = dict(h=h, l=l, atr=atr)
    if o is not None:
        d["o"] = o
    return d


# base : a NON-initialisation down wave O = 1000, E = 0 (retracement ratio of a high h = h / 1000)
BASE = [B(1001, 995, atr=None), B(998, 990, atr=3.0), B(1000, 992), B(995, 0)]


def base_run(extra, overrides=None):
    return Run(overrides).feed4(BASE + extra)


def rec_t(r):
    return (r.dir, r.outcome, r.bin, round(r.rMax, 9), None if r.rAlt is None else round(r.rAlt, 9), r.refO, r.refE, r.seq)


def cnt(S, d, b, o):
    return S.cnt[((0 if d == 1 else 1) * 12 + b) * 5 + o]


# ============================================================================
# static
# ============================================================================
def gate_static():
    inp = ap.inputs(SRC)
    check("LS-01 inputs: switch ratio 0.782, observation start 0.10, ATR 14 x 3.0, init-wave exclusion on",
          inp["lfwSwitchRatio"] == 0.782 and inp["lfwStartRatio"] == 0.10 and inp["lfwAtrLen"] == 14
          and inp["lfwInitAtrMult"] == 3.0 and inp["lfwExclInit"] is True, str(inp))
    check("LS-02 display levels are 0 / 0.236 / 0.382 / 0.5 / 0.618 / 0.79 / 1 and 0.786 appears nowhere",
          inp["lfwLevelsStr"] == "0,0.236,0.382,0.5,0.618,0.79,1" and "0.786" not in SRC, inp["lfwLevelsStr"])
    sec = re.findall(r"^\[[^\n]*= request\.security\(([^\n]+)\)$", SRC, re.M)
    good = len(sec) == 2 and '"D"' in sec[0] and '"240"' in sec[1] and all(
        "lookahead = barmerge.lookahead_on" in s and s.count("[1]") == 4 and "open" not in s for s in sec)
    check("LS-03 exactly two request.security calls (D / 240), each output [1] with lookahead_on (confirmed bars only); "
          "high / low / time / ATR only (the open is not requested)",
          good and "request.security_lower_tf" not in SRC, str(sec))
    gate = all(re.search(rf"lfwNew{k} = lfwOk{k} and barstate\.isconfirmed and not na\(lfw{k}t\) and \(lfwSame{k} or "
                         rf"lfw{k}tS != nz\(lfw{k}tS\[1\], -1\)\)", SRC) for k in ("D", "4"))
    sel = all(f"lfw{k}{f}{' ' * (4 - len(f))}= lfwSame{k} ? {v}{' ' * (9 - len(v))}: lfw{k}{f}S" in SRC
              for k in ("D", "4") for f, v in (("h", "high"), ("l", "low"), ("t", "time"), ("atr", "lfwAtrC")))
    check("LS-04 a confirmed HTF bar is processed once, on a confirmed chart execution, only when the chart TF <= the target TF; "
          "chart TF == target TF uses the chart bar itself at its close, otherwise the [1] delivery",
          gate and sel and "lfwOkD = lfwOnD and lfwChartSec <= timeframe.in_seconds(\"D\")" in SRC
          and "lfwOk4 = lfwOn4 and lfwChartSec <= timeframe.in_seconds(\"240\")" in SRC
          and 'lfwSameD = lfwChartSec == timeframe.in_seconds("D")' in SRC and 'lfwSame4 = lfwChartSec == timeframe.in_seconds("240")' in SRC)
    check("LS-05 indicator only: no strategy / order / alert calls, no Zone / Engine import",
          SRC.count("indicator(") == 1 and not re.search(r"strategy\.|alertcondition|alert\(|^import ", SRC, re.M))
    try:
        transpile(SRC)
        ok, why = True, ""
    except Exception as ex:      # noqa: BLE001
        ok, why = False, repr(ex)
    check("LS-06 the whole logic section is inside the translated Pine subset (no history reference)", ok, why)
    lg = logic(SRC)
    check("LS-07 no intrabar-order assumption in the logic: the open is not used, every bar is processed in both orders "
          "(high -> low and low -> high) and a difference is kept as a hold, never resolved by a choice",
          not re.search(r"\bopen\b|\bop\b|hiFirst|retFirst", lg)
          and "bool ca = lfwPoint(a, h, t, availT, false)\n    lfwPoint(a, l, t, availT, ca)" in lg
          and "bool cb = lfwPoint(b, l, t, availT, false)\n    lfwPoint(b, h, t, availT, cb)" in lg
          and "    if not lfwSame(a, b)\n        array.push(out, b)" in lg)
    import subprocess
    import lfw_build as lb
    bad = []
    for path, eds in lb.TEST_EDITS.items():
        cur = open(os.path.join(ROOT, path), encoding="utf-8").read()
        if not all(cur.count(new) == cnt for _, new, cnt in eds):
            bad.append((path, "edit not applied exactly"))
        elif lb.unadapt(path, cur) != subprocess.run(["git", "-C", ROOT, "show", f"{lb.REG_BASE}:{path}"], capture_output=True,
                                                     text=True).stdout:
            bad.append((path, "unadapt != the text before the edits"))
    acc = __import__("acc_build")
    stray = ("LongFibWave.pine.bak", "tests/lfw_other.py", "LONG_FIB_WAVE.md", "tests/lfw_build.pyc")
    check("LS-08 registration in the older fixtures (tests/lfw_build.py, same method as fds_build / lab_build): every recorded edit "
          "present exactly, unadapt() gives the pre-edit text byte for byte, acc_build.ok() accepts exactly the 4 LFW-1 files "
          "(and no similarly named stray file)",
          not bad and set(lb.NEW_FILES) == {"LongFibWave.pine", "LONG_FIB_WAVE_ja.md", "tests/lfw_sim.py", "tests/lfw_build.py"}
          and all(acc.ok(f) and os.path.exists(os.path.join(ROOT, f)) for f in lb.NEW_FILES)
          and not any(acc.ok(f) for f in stray), str(bad))


# ============================================================================
# waves
# ============================================================================
def gate_waves():
    # LW-01 the 4H sample shape: 4,890.388 -> 3,938.849, 79.7 % rally to 4,697.322, break -> 4,697.322 -> 3,871.867
    bars = [B(4895, 4880, atr=None), B(4885, 4860), B(4890.388, 4870), B(4880, 4800), B(4795, 3938.849),
            B(4300, 4000), B(4697.322, 4400), B(4500, 4100), B(4200, 3871.867)]
    r = Run().feed4(bars)
    S, W = r.S, r.W
    recs = r.recs()
    check("LW-01 sample shape: previous wave 4890.388 -> 3938.849, 79.7 % rally, break of 3938.849 -> latest wave "
          "4697.322 -> 3871.867 (down); one observation: resume, bin 70-80 %, denominator 4890.388 / 3938.849",
          W.dir == -1 and W.O == 4697.322 and W.E == 3871.867 and W.oT == T0 + 6 * H4 and W.eT == T0 + 8 * H4
          and len(recs) == 1 and recs[0].outcome == 0 and recs[0].bin == 7 and recs[0].refO == 4890.388
          and recs[0].refE == 3938.849 and S.nExclInit == 1 and not W.init and not S.hold, f"{W} {recs}")
    a = base_run([B(782, 500), B(600, -10)]).W
    b = base_run([B(781, 500), B(600, -10)]).W
    check("LW-02 retracement exactly 0.782 then a new low: the retracement high becomes the new origin (same direction)",
          a.dir == -1 and a.O == 782 and a.E == -10 and a.oT == T0 + 4 * H4, str(a))
    check("LW-03 retracement 0.781 then a new low: same wave extended (origin kept)", b.dir == -1 and b.O == 1000 and b.E == -10, str(b))
    c = base_run([B(900, 500), B(850, 400)]).W
    check("LW-04 reaching 0.782 alone does not switch: wave unchanged, candidate = highest retracement high",
          c.dir == -1 and c.O == 1000 and c.E == 0 and c.rx == 900 and c.rxT == T0 + 4 * H4, str(c))
    c2 = base_run([B(900, 500), B(950, 400), B(700, -1)]).W
    check("LW-05 the candidate follows the highest retracement high (900 -> 950) and that high becomes the origin",
          c2.O == 950 and c2.oT == T0 + 5 * H4 and c2.E == -1, str(c2))
    f = base_run([B(300, 100), B(1000.5, 200)]).W
    check("LW-06 strict break of the origin: direction reversal, the old end (0) becomes the up wave's origin",
          f.dir == 1 and f.O == 0 and f.oT == T0 + 3 * H4 and f.E == 1000.5, str(f))
    t = base_run([B(1000, 500), B(900, 400)]).W
    check("LW-07 exact touch of the origin is not a reversal (down wave kept, origin 1000)", t.dir == -1 and t.O == 1000, str(t))
    up = base_run([B(300, 100), B(1001, 200), B(1500, 900), B(1200, 800), B(1600, 1100)]).W
    check("LW-08 up wave extends on higher highs (origin = the low 0 kept)", up.dir == 1 and up.O == 0 and up.E == 1600, str(up))
    r0 = Run().feed4([B(110, 100, atr=None), B(105, 60, atr=None), B(104, 70, atr=None)])
    r1 = copy.deepcopy(r0)
    r1.feed4([B(103, 95, atr=15.0)], start=3)
    check("LW-09 initialisation waits for the HTF ATR; the first wave is fixed on the bar where the high-low range (50) >= ATR x 3.0 "
          "(45): down 110 -> 60, flagged as init wave, ATR / time stored",
          r0.W.dir == 0 and r1.W.dir == -1 and r1.W.O == 110 and r1.W.E == 60 and r1.W.init and r1.S.initAtr == 15.0
          and r1.S.initAvail == T0 + 3 * H4 + H4 + H1, f"{r0.W} {r1.W}")
    r2 = Run().feed4([B(110, 100, atr=None), B(105, 60, atr=20.0)])
    check("LW-10 range below ATR x 3.0 (50 < 60): no wave yet", r2.W.dir == 0, str(r2.W))
    r3 = Run().feed4([B(150, 100, o=145, atr=10.0), B(140, 120)])
    r4 = Run().feed4([B(150, 100, o=105, atr=10.0), B(140, 120)])
    r5 = Run().feed4([B(150, 100, atr=10.0), B(140, 120), B(160, 130)])
    r6 = Run().feed4([B(150, 100, atr=10.0), B(140, 120), B(145, 90)])
    check("LW-11 initialisation never chooses an order inside one bar: while the highest high and the lowest low are on the same "
          "bar there is no wave (whatever the open); a later new high -> up 100 -> 160, a later new low -> down 150 -> 90",
          r3.W.dir == 0 and r4.W.dir == 0 and (r5.W.dir, r5.W.O, r5.W.E) == (1, 100, 160)
          and (r6.W.dir, r6.W.O, r6.W.E) == (-1, 150, 90), f"{r3.W} {r5.W} {r6.W}")


# ============================================================================
# hold (no intrabar-order assumption)
# ============================================================================
def hyps(S):
    return sorted((h.dir, h.O, h.oT, h.E, h.eT) for h in S.hyps)


def gate_hold():
    t4, t5 = T0 + 4 * H4, T0 + 5 * H4
    r = base_run([B(300, 100), B(1100, -100)])
    rc = r.recs()
    check("LH-01 one bar makes a new low AND breaks the origin: the wave is on hold with both candidates (down 1100 -> -100 and "
          "up -100 -> 1100 on that bar), no direction chosen; the live observation is closed once as order unknown",
          r.S.hold and hyps(r.S) == [(-1, 1100, t5, -100, t5), (1, -100, t5, 1100, t5)] and r.S.nHold == 1
          and len(rc) == 1 and rc[0].outcome == 4 and rc[0].refO == 1000 and not r.S.obsOn, f"{hyps(r.S)} {rc}")
    variants = [base_run([B(300, 100), B(1100, -100, o=o)]) for o in (1090, 500, -90)]
    check("LH-02 moving only the open (near the high / middle / near the low) changes nothing: same hold, same candidates, "
          "same records", all(pine_tuple(v.S) == pine_tuple(variants[0].S) for v in variants), str([hyps(v.S) for v in variants]))
    rd = base_run([B(300, 100), B(1100, -100), B(600, 200), B(500, -150)])
    ru = base_run([B(300, 100), B(1100, -100), B(600, 200), B(1150, 300)])
    av = T0 + 7 * H4 + H4 + H1
    check("LH-03 hold released by a later bar breaking one side: below -100 -> down 1100 -> -150 (both candidates give it), "
          "available from the release bar (not the hold bar)",
          not rd.S.hold and (rd.W.dir, rd.W.O, rd.W.oT, rd.W.E) == (-1, 1100, t5, -150) and rd.W.oAvail == av and rd.W.eAvail == av,
          str(rd.W))
    check("LH-04 symmetric: above 1100 -> up -100 -> 1150", not ru.S.hold and (ru.W.dir, ru.W.O, ru.W.oT, ru.W.E) == (1, -100, t5, 1150),
          str(ru.W))
    mbase = [B(-995, -1001, atr=None), B(-990, -998, atr=3.0), B(-992, -1000), B(0, -995)]      # mirrored BASE: up -1000 -> 0
    m = Run().feed4(mbase + [B(-100, -300), B(100, -1100), B(-200, -600), B(150, -500)])
    check("LH-05 mirror of LH-01 / LH-03 (every price negated): hold, then above 100 -> up -1100 -> 150",
          m.S.nHold == 1 and not m.S.hold and (m.W.dir, m.W.O, m.W.E) == (1, -1100, 150), str(m.W))
    k = base_run([B(300, 100), B(1100, -100), B(1000, 500), B(400, -150)])
    check("LH-06 the candidates still disagree after the break (78 %+ rally inside: down candidate switches to origin 1000, up "
          "candidate reverses from 1100) -> still on hold, no wave chosen",
          k.S.hold and hyps(k.S) == [(-1, 1000, T0 + 6 * H4, -150, T0 + 7 * H4), (-1, 1100, t5, -150, T0 + 7 * H4)], str(hyps(k.S)))
    k2 = copy.deepcopy(k)
    k2.feed4([B(1200, 0)], start=8)
    check("LH-07 ... until they agree: a bar above both origins reverses both -> up -150 -> 1200",
          not k2.S.hold and (k2.W.dir, k2.W.O, k2.W.E) == (1, -150, 1200), str(k2.W))
    c = base_run([B(300, 100), B(900, -10)])
    check("LH-08 a new low on the bar whose high would first create a switch candidate (90 %): order decides between extension "
          "(origin 1000) and switch (origin 900) -> hold, no candidate chosen; the observation closes as order unknown",
          c.S.hold and hyps(c.S) == [(-1, 900, t5, -10, t5), (-1, 1000, T0 + 2 * H4, -10, t5)] and len(c.recs()) == 1
          and c.recs()[0].outcome == 4, str(hyps(c.S)))
    c3 = base_run([B(300, 100), B(1000, -1)])
    check("LH-09 a new low on the bar that touches the origin: hold (the touched high may or may not precede the low)",
          c3.S.hold and len(c3.recs()) == 1 and c3.recs()[0].outcome == 4 and c3.recs()[0].rAlt == 1.0, str(hyps(c3.S)))
    # no observation during the hold, none created afterwards from it, no double count
    seq = [B(300, 100), B(1100, -100), B(600, 0), B(500, -50), B(700, 100), B(500, -150), B(-120, -140), B(20, -145), B(0, -300)]
    rr = base_run(seq)
    rc = rr.recs()
    rel = T0 + 9 * H4 + H4 + H1           # release bar = the 6th extra bar (index 9)
    during = [x for x in rc if T0 + 5 * H4 + H4 + H1 <= x.startAvail < rel]
    check("LH-10 hold -> release: only one record before the hold (order unknown); retracements during the hold (67 % / 96 % "
          "of the two candidates) "
          "make no observation; after the release a new observation starts from the release end (-150) only after the "
          "release (startAvail > release) and resumes once",
          len(rc) == 2 and rc[0].outcome == 4 and rc[0].refE == 0 and not during
          and rc[1].refE == -150 and rc[1].refO == 1100 and rc[1].startAvail > rel and rc[1].outcome == 0 and rc[1].seq == 1
          and sum(rr.S.cnt) == 2 and rr.S.waveId == base_run([]).S.waveId + 1, str(rc))
    check("LH-11 the counters equal the records after a hold (no double count) and no record starts inside the hold",
          all(cnt(rr.S, x.dir, x.bin, x.outcome) == sum(1 for y in rc if (y.dir, y.bin, y.outcome) == (x.dir, x.bin, x.outcome))
              for x in rc), str(rr.S.cnt))
    st = base_run([B(300, 100), B(1100, -100), B(600, 200)])
    check("LH-12 while on hold no observation is live even after a large retracement", st.S.hold and not st.S.obsOn and len(st.recs()) == 1)


# ============================================================================
# observations
# ============================================================================
def gate_obs():
    r = base_run([B(99, 50)])
    check("LO-01 9.9 % retracement: no observation", not r.S.obsOn and not r.recs(), str(r.S))
    r = base_run([B(99, 50), B(100, 50), B(150, -1)])
    rc = r.recs()
    check("LO-02 10 % starts an observation (fixed 1000 / 0); a later high of 15 % in the SAME bin on the resume bar -> resume, "
          "max = 10 % (the resume bar's own high is not used)",
          len(rc) == 1 and rec_t(rc[0]) == (-1, 0, 1, 0.1, None, 1000, 0, 1) and rc[0].startAvail == T0 + 5 * H4 + H4 + H1,
          str(rc))
    r = base_run([B(150, 50), B(250, -1)])
    rc = r.recs()
    check("LO-03 resume bar whose high would raise the bin (15 % -> 25 %): order unknown (bin of the certain 15 %, alt 25 %), "
          "not a resume; the wave still extends", len(rc) == 1 and rec_t(rc[0]) == (-1, 4, 1, 0.15, 0.25, 1000, 0, 1)
          and r.W.E == -1 and r.W.O == 1000 and cnt(r.S, -1, 1, 0) == 0 and cnt(r.S, -1, 1, 4) == 1, str(rc))
    r = base_run([B(1000, 500), B(900, 400), B(800, -5)])
    rc = r.recs()
    check("LO-04 exact touch of the origin: observation ends as full retracement (bin 100 %), no new observation for the same end; "
          "then the new low switches the wave from the touched high (origin 1000 at the touch bar), no resume recorded",
          len(rc) == 1 and rec_t(rc[0]) == (-1, 1, 10, 1.0, None, 1000, 0, 1) and r.W.O == 1000 and r.W.oT == T0 + 4 * H4
          and r.W.E == -5 and r.S.nStartAmb == 0, str(rc) + str(r.W))
    r = base_run([B(999.5, 500)])
    check("LO-05 99.95 % is not a full retracement (observation still live)", r.S.obsOn and not r.recs(), str(r.S))
    r = base_run([B(300, 100), B(1000.5, 200)])
    rc = r.recs()
    check("LO-06 strict break of the origin: observation ends as switch-end (bin > 100 %), not as full retracement",
          len(rc) == 1 and rc[0].outcome == 2 and rc[0].bin == 11 and abs(rc[0].rMax - 1.0005) < 1e-12 and not r.S.obsOn, str(rc))
    r = base_run([B(50, 10), B(1200, 40)])
    rc = r.recs()
    check("LO-07 a bar going from < 10 % straight through the origin: the observation starts and ends as switch-end on that bar",
          len(rc) == 1 and rc[0].outcome == 2 and rc[0].refO == 1000 and rc[0].refE == 0, str(rc))
    r = base_run([B(300, 100), B(200, -100), B(10, -50), B(0, -200)])
    rc = r.recs()
    check("LO-08 repeated observation: after the resume (new end -100) a 10 % retracement of 1000 -> -100 starts #2 with the NEW "
          "fixed denominator; same wave id",
          len(rc) == 2 and rec_t(rc[0]) == (-1, 0, 3, 0.3, None, 1000, 0, 1) and rec_t(rc[1]) == (-1, 0, 1, 0.1, None, 1000, -100, 2)
          and rc[0].waveId == rc[1].waveId, str(rc))
    r = base_run([B(782, 500), B(600, -10), B(100, -5), B(-5, -20)])
    rc = r.recs()
    check("LO-09 resume and same-direction switch on one bar: the old observation's resume is saved first (once, old denominator "
          "1000 / 0), then the new wave 782 -> -10 starts its own observations (#1, new wave id)",
          len(rc) == 2 and rec_t(rc[0]) == (-1, 0, 7, 0.782, None, 1000, 0, 1) and rec_t(rc[1])[5:] == (782, -10, 1)
          and rc[1].waveId == rc[0].waveId + 1 and sum(r.S.cnt) == 2, str(rc))
    r = base_run([B(300, 100), B(1000.5, 200), B(900, 700)])
    check("LO-10 no observation carried across a direction reversal (old one closed as switch-end; up wave 0 -> 1000.5 starts "
          "its own when it retraces 10 %)", len(r.recs()) == 1 and r.S.obsOn and r.S.obsO == 0 and r.S.obsE == 1000.5
          and r.S.obsDir == 1, str(r.S))
    r = base_run([B(50, -10), B(150, -20)])
    check("LO-11 a bar making a new low whose high reaches 10 % of the old wave: no observation (order unknown start, counted)",
          not r.recs() and r.S.nStartAmb == 1, str(r.S))
    r = base_run([B(300, 100), B(350, 150), B(320, 120), B(400, 200)])
    check("LO-12 no expiry: the observation stays live while neither end nor origin is reached (max 40 %)",
          r.S.obsOn and abs((r.W.E - r.W.rx) / (r.W.E - r.W.O) - 0.4) < 1e-12 and not r.recs(), str(r.S))
    r = Run().feed4(BASE)
    q = Run({"lfwExclInit": False}).feed4(BASE)
    check("LO-13 observations of the initialisation wave are excluded (counted separately) by default; included when the input is off",
          not r.recs() and r.S.nExclInit == 1 and len(q.recs()) == 1 and q.S.nExclInit == 0 and q.recs()[0].outcome == 0, str(q.recs()))
    r = Run({"lfwStartRatio": 0.3}).feed4(BASE + [B(250, 100), B(299, 100)])
    s2 = Run({"lfwSwitchRatio": 0.5}).feed4(BASE + [B(500, 100), B(300, -1)])
    check("LO-14 the start ratio and the switch ratio are inputs (start 0.3: 29.9 % no observation; switch 0.5: 50 % + new low switches)",
          not r.S.obsOn and s2.W.O == 500, f"{r.S} {s2.W}")


# ============================================================================
# reference model (written from the spec, independent of the Pine text)
# ============================================================================
# wave = (dir, init, O, oT, E, eT, ret, retT); ret = most retraced price since the end (down: highest high, up: lowest low)
class Ref:
    def __init__(self, sw=0.782, st=0.10, mult=3.0, excl=True):
        self.sw, self.st, self.mult, self.excl = sw, st, mult, excl
        self.wave = None
        self.hold = None                     # list of candidate waves while on hold
        self.wid = 0
        self.obs = None                      # dict(dir, O, E, seq, init, start)
        self.done = False
        self.seq = 0
        self.hi = self.lo = self.hiT = self.loT = None
        self.recs, self.excl_n, self.start_amb, self.n_hold = [], 0, 0, 0

    @staticmethod
    def rt(w, p):
        d, _, O, _, E, _, _, _ = w
        return (p - E) / (O - E) if d == -1 else (E - p) / (E - O)

    def point(self, w, p, t, after_end_change):
        d, init, O, oT, E, eT, ret, retT = w
        beyond_end = p < E if d == -1 else p > E
        beyond_origin = p > O if d == -1 else p < O
        if beyond_end:
            if ret is not None and self.rt(w, ret) >= self.sw:
                return (d, False, ret, retT, p, t, None, None), True
            return (d, init, O, oT, p, t, None, None), True
        if beyond_origin:
            return (-d, False, E, eT, p, t, None, None), True
        if not after_end_change and (ret is None or self.rt(w, p) > self.rt(w, ret)):
            return (d, init, O, oT, E, eT, p, t), False
        return w, False

    def outcomes(self, w, h, l, t):
        res = []
        for first, second in ((h, l), (l, h)):
            x, ch = self.point(w, first, t, False)
            x, _ = self.point(x, second, t, ch)
            if x not in res:
                res.append(x)
        return res

    @staticmethod
    def bin(r):
        if r > 1:
            return 11
        if r >= 1:
            return 10
        return max(0, min(9, int((r * 10.0 + 1e-9) // 1)))

    def close(self, outcome, r, alt, av):
        o = self.obs
        b = 10 if outcome == 1 else 11 if outcome == 2 else self.bin(r)
        if o["init"]:
            self.excl_n += 1
        else:
            self.recs.append((o["dir"], self.wid, o["seq"], o["O"], o["E"], o["start"], av, outcome, r, alt, b))
        self.obs = None

    def open(self, av):
        self.seq += 1
        w = self.wave
        self.obs = dict(dir=w[0], O=w[2], E=w[4], seq=self.seq, init=w[1] and self.excl, start=av)

    def new_wave(self, w):
        self.wave = w
        self.wid += 1
        self.obs, self.done, self.seq = None, False, 0

    def bar(self, h, l, t, atr, av):
        if self.hold is not None:
            nxt = []
            for c in self.hold:
                for x in self.outcomes(c, h, l, t):
                    if x not in nxt:
                        nxt.append(x)
            if len(nxt) == 1:
                self.hold = None
                self.new_wave(nxt[0])
                if nxt[0][6] is not None and self.rt(nxt[0], nxt[0][6]) >= self.st:
                    self.done = True
            elif len(nxt) > 16:
                raise AssertionError("more than 16 candidates")
            else:
                self.hold = nxt
            return
        if self.wave is None:
            if self.hi is None or h > self.hi:
                self.hi, self.hiT = h, t
            if self.lo is None or l < self.lo:
                self.lo, self.loT = l, t
            if atr is not None and atr > 0 and self.hi - self.lo >= self.mult * atr and self.hiT != self.loT:
                if self.hiT < self.loT:
                    self.new_wave((-1, True, self.hi, self.hiT, self.lo, self.loT, None, None))
                else:
                    self.new_wave((1, True, self.lo, self.loT, self.hi, self.hiT, None, None))
            return
        w = self.wave
        d, _, O, oT, E, _, ret, _ = w
        rp, ep = (h, l) if d == -1 else (l, h)
        new_end = ep < E if d == -1 else ep > E
        brk = rp > O if d == -1 else rp < O
        r_prior = 0.0 if ret is None else self.rt(w, ret)
        r_bar = self.rt(w, rp)
        outs = self.outcomes(w, h, l, t)
        if len(outs) > 1:
            if self.obs:
                self.close(4, r_prior, r_bar, av)
            self.hold = outs
            self.n_hold += 1
            return
        nw = outs[0]
        if new_end:
            if self.obs:
                if r_bar > r_prior and (r_bar >= 1 or self.bin(r_bar) != self.bin(r_prior)):
                    self.close(4, r_prior, r_bar, av)
                else:
                    self.close(0, r_prior, None, av)
            elif not self.done and r_bar >= self.st:
                self.start_amb += 1
            self.done = False
        elif brk:
            if not self.obs and not self.done:
                self.open(av)
            if self.obs:
                self.close(2, r_bar, None, av)
        if (nw[0], nw[2], nw[3]) != (d, O, oT):
            self.new_wave(nw)
            return
        self.wave = nw
        if not new_end and not brk:
            if not self.obs and not self.done and self.rt(nw, nw[6]) >= self.st:
                self.open(av)
            if self.obs and rp == O:
                self.close(1, 1.0, None, av)
                self.done = True


def wtuple(w):
    return (w.dir, w.init, w.O, w.oT, w.E, w.eT, w.rx, w.rxT) if w.dir != 0 else None


def pine_tuple(S):
    recs = [(r.dir, r.waveId, r.seq, r.refO, r.refE, r.startAvail, r.endAvail, r.outcome, r.rMax, r.rAlt, r.bin) for r in S.recs]
    return (None if S.hold else wtuple(S.w), sorted(wtuple(h) for h in S.hyps) if S.hold else None, S.waveId, recs,
            S.nExclInit, S.nStartAmb, S.nHold, S.obsOn, S.obsO if S.obsOn else None, S.obsE if S.obsOn else None)


def ref_tuple(R):
    return (None if R.hold is not None else R.wave, sorted(R.hold) if R.hold is not None else None, R.wid, R.recs,
            R.excl_n, R.start_amb, R.n_hold, R.obs is not None, R.obs["O"] if R.obs else None, R.obs["E"] if R.obs else None)


def rand_series(seed, n=1500, scale=1.0, big=0.03):
    rng = random.Random(seed)
    p, out, atr = 1000.0 * scale, [], 8.0 * scale
    drift = 0.0
    for i in range(n):
        if rng.random() < 0.02:
            drift = rng.uniform(-3, 3) * scale
        rngw = rng.uniform(2, 14) * scale * (6 if rng.random() < big else 1)
        o = p
        c = o + drift + rng.gauss(0, 6 * scale)
        h = max(o, c) + rng.uniform(0, rngw)
        l = min(o, c) - rng.uniform(0, rngw)
        h, l, o = round(h, 3), round(l, 3), round(o, 3)
        if rng.random() < 0.03 and len(out) > 5:      # exact equalities: touch an earlier high / low (origin touches)
            k = rng.randint(2, min(120, len(out)))
            if rng.random() < 0.5:
                h = max(x["h"] for x in out[-k:])
            else:
                l = min(x["l"] for x in out[-k:])
        if rng.random() < 0.004 and len(out) > 5:     # occasional huge outside bar (both ends of the wave in one bar)
            k = rng.randint(5, min(200, len(out)))
            h = max(x["h"] for x in out[-k:]) + rng.uniform(0, 20) * scale
            l = min(x["l"] for x in out[-k:]) - rng.uniform(0, 20) * scale
        h = max(h, o)
        out.append(dict(h=h, l=min(l, o), o=o, atr=None if i < 14 else atr))
        atr = atr * 13 / 14 + (h - l) / 14
        p = c
    return out


def run_ref(bars, **kw):
    R = Ref(**kw)
    for i, b in enumerate(bars):
        t = T0 + i * H4
        R.bar(b["h"], b["l"], t, b.get("atr", 10.0), t + H4 + H1)
    return R


def gate_random():
    bad = []
    n_rec = n_hold = 0
    kinds = set()
    for seed in range(12):
        for kw in ({}, {"sw": 0.5, "st": 0.2}, {"excl": False}):
            bars = rand_series(seed, scale=1.0 + seed % 3)
            ov = {}
            if "sw" in kw:
                ov.update(lfwSwitchRatio=kw["sw"], lfwStartRatio=kw["st"])
            if "excl" in kw:
                ov.update(lfwExclInit=kw["excl"])
            ov["lfwMaxRecs"] = 100000
            P = Run(ov).feed4(bars).S
            R = run_ref(bars, **kw)
            if pine_tuple(P) != ref_tuple(R):
                bad.append((seed, kw))
            n_rec += len(R.recs)
            n_hold += R.n_hold
            kinds |= {x[7] for x in R.recs}
    check(f"LR-01 translated Pine == independent reference model on 36 random HTF series ({n_rec} observations, outcomes "
          f"{sorted(kinds)}, {n_hold} holds): wave state, hold candidates, records, counters",
          not bad and kinds == {0, 1, 2, 4} and n_hold > 20, str(bad))
    bad = []
    for seed in range(8):
        bars = rand_series(100 + seed)
        mir = [dict(h=-b["l"], l=-b["h"], o=-b["o"], atr=b["atr"]) for b in bars]
        A = Run({"lfwMaxRecs": 100000}).feed4(bars).S
        M = Run({"lfwMaxRecs": 100000}).feed4(mir).S
        ra = [(r.dir, r.outcome, r.bin, r.refO, r.refE, r.seq, r.startAvail) for r in A.recs]
        rm = [(-r.dir, r.outcome, r.bin, -r.refO, -r.refE, r.seq, r.startAvail) for r in M.recs]
        ha = sorted((h.dir, h.O, h.E) for h in A.hyps) if A.hold else None
        hm = sorted((-h.dir, -h.O, -h.E) for h in M.hyps) if M.hold else None
        if not (A.hold == M.hold and ha == hm and A.w.dir == -M.w.dir and A.w.O == -M.w.O and A.w.E == -M.w.E and ra == rm
                and A.nHold == M.nHold):
            bad.append(seed)
    check("LR-02 up / down symmetry (including holds and their release): negating every price swaps the directions and gives the "
          "same observations, holds and waves", not bad, str(bad))
    bad = []
    for seed in range(6):
        S = Run({"lfwMaxRecs": 100000}).feed4(rand_series(200 + seed)).S
        for d in (1, -1):
            for b in range(12):
                for o in range(5):
                    want = sum(1 for r in S.recs if r.dir == d and r.bin == b and r.outcome == o)
                    if cnt(S, d, b, o) != want:
                        bad.append((seed, d, b, o))
        if any(r.outcome == 0 and not (0.1 <= r.rMax < 1) for r in S.recs) or any(r.outcome == 3 for r in S.recs):
            bad.append((seed, "range"))
        if any(r.endAvail < r.startAvail for r in S.recs):
            bad.append((seed, "time"))
    check("LR-03 counters (time frame x direction x 10 % bin x outcome) == the observation records; resume ratios in [10 %, 100 %); "
          "no record ends before it starts", not bad, str(bad[:5]))
    S = Run({"lfwMaxRecs": 10}).feed4(rand_series(7)).S
    check("LR-04 the record list is capped by the input, the counters are not", len(S.recs) == 10 and sum(S.cnt) > 10, str(sum(S.cnt)))
    # holds on random data: no observation is live or starts inside a hold interval, no candidate count above 16
    bad = []
    for seed in range(10):
        bars = rand_series(300 + seed)
        r = Run({"lfwMaxRecs": 100000})
        spans, cur, maxc = [], None, 0
        for i, b in enumerate(bars):
            t = T0 + i * H4
            r.exec(t + H4 + H1, h4=(b["h"], b["l"], t, b["atr"]))
            S = r.S
            if S.hold:
                maxc = max(maxc, len(S.hyps))
                if S.obsOn:
                    bad.append((seed, i, "live obs in hold"))
                if cur is None:
                    cur = t + H4 + H1
            elif cur is not None:
                spans.append((cur, t + H4 + H1))
                cur = None
        for x in r.S.recs:
            if any(a < x.startAvail <= b for a, b in spans):
                bad.append((seed, "start inside hold"))
        if maxc > 16 or r.S.nReinit:
            bad.append((seed, "candidates", maxc))
    check("LR-05 random series with holds: no observation live during a hold and none started inside one (only after the release "
          "bar); candidates stay <= 16, no re-initialisation", not bad, str(bad[:5]))


# ============================================================================
# chart-level delivery (1H chart, 4H target)
# ============================================================================
def chart_bars(seed, n_h4=500):
    h4 = rand_series(seed, n=n_h4)
    rng = random.Random(seed + 9)
    out = []
    for k, b in enumerate(h4):
        # 4 x 1H bars whose aggregate is exactly the 4H bar (o, h, l)
        pts = [b["o"], b["h"], b["l"], rng.uniform(b["l"], b["h"])]
        rng.shuffle(pts[1:])
        hs = []
        for j in range(4):
            a, c = pts[j], pts[j + 1] if j < 3 else pts[3]
            hs.append(dict(t=T0 + k * H4 + j * H1, o=a, h=max(a, c), l=min(a, c)))
        hs[0]["o"] = b["o"]
        out.extend(hs)
    return h4, out


def run_chart(h4, hbars, upto=None, ticks=False):
    """request.security(…, "240", [high[1], low[1], open[1], time[1], atr[1]], lookahead_on) on a 1H chart."""
    r = Run({"lfwMaxRecs": 100000})
    prev_t = None
    log = []
    for i, cb in enumerate(hbars[:upto]):
        k = (cb["t"] - T0) // H4
        fe = None
        if k >= 1:
            b = h4[k - 1]
            fe = (b["h"], b["l"], T0 + (k - 1) * H4, b["atr"])
        new = fe is not None and fe[2] != (prev_t if prev_t is not None else -1)
        if ticks and i > 0:      # realtime-like unconfirmed executions first: lfwNew4 is false (barstate.isconfirmed false)
            snap = copy.deepcopy(pine_tuple(r.S))
            r.exec(cb["t"] + H1)
            if pine_tuple(r.S) != snap:
                log.append(("changed_unconfirmed", i))
        r.exec(cb["t"] + H1, h4=fe if new else None)
        if new:
            log.append((fe[2], cb["t"] + H1))
        prev_t = fe[2] if fe is not None else prev_t
    return r, log


def gate_chart():
    h4, hb = chart_bars(34, 700)
    r, log = run_chart(h4, hb, ticks=True)
    proc = [x for x in log if x[0] != "changed_unconfirmed"]
    order = [x[0] for x in proc] == [T0 + k * H4 for k in range(len(h4) - 1)]
    never_early = all(av >= t + H4 for t, av in proc)
    check("LC-01 1H chart: every confirmed 4H bar processed exactly once, in order, at the first confirmed 1H execution after it "
          "closed (availability >= 4H close)", order and never_early and len(proc) == len(h4) - 1, str(proc[:3]))
    check("LC-02 unconfirmed (realtime tick) executions change nothing", not [x for x in log if x[0] == "changed_unconfirmed"])
    direct = Run({"lfwMaxRecs": 100000})
    for k, b in enumerate(h4[:-1]):
        t = T0 + k * H4
        direct.exec(t + H4 + H1, h4=(b["h"], b["l"], t, b["atr"]))
    check("LC-03 chart-level run == running the confirmed 4H bars directly (waves and observations identical, availability "
          "= the 1H bar after the 4H close)", pine_tuple(r.S) == pine_tuple(direct.S) and len(r.S.recs) > 5, str(len(r.S.recs)))
    bad = []
    for cut in (37, 301, 802, 1203, 1777):
        p, _ = run_chart(h4, hb, upto=cut)
        full_at = run_chart(h4, hb, upto=cut)[0]
        k_done = (hb[cut - 1]["t"] - T0) // H4          # 4H bars delivered so far = k_done
        ref = Run({"lfwMaxRecs": 100000})
        for k in range(k_done):
            t = T0 + k * H4
            b = h4[k]
            ref.exec(t + H4 + H1, h4=(b["h"], b["l"], t, b["atr"]))
        if pine_tuple(p.S) != pine_tuple(ref.S) or pine_tuple(full_at.S) != pine_tuple(p.S):
            bad.append(cut)
    check("LC-04 prefix runs (chart cut inside a forming 4H bar) use only the 4H bars closed before the cut", not bad, str(bad))


# ============================================================================
# mutation
# ============================================================================
MUTATIONS = [
    ("switch >= -> >", "if not na(w.rx) and lfwRatio(w, w.rx) >= lfwSwitchRatio", "if not na(w.rx) and lfwRatio(w, w.rx) > lfwSwitchRatio"),
    ("start >= -> >", "if not S.obsOn and not S.obsDone and r >= lfwStartRatio", "if not S.obsOn and not S.obsDone and r > lfwStartRatio"),
    ("touch = 99.9 %", "                if S.obsOn and T\n", "                if S.obsOn and rBar >= 0.999\n"),
    ("origin break >=", "    else if s * (w.O - p) > 0\n", "    else if s * (w.O - p) >= 0\n"),
    ("resume uses bar high", "lfwRecord(S, 0, rPrior, na, availT)", "lfwRecord(S, 0, math.max(rPrior, rBar), na, availT)"),
    ("switch origin = old origin", "            w.O := w.rx\n            w.oT := w.rxT\n", "            w.O := w.O\n            w.oT := w.oT\n"),
    ("unknown on any higher high", "lfwBin(rBar) != lfwBin(rPrior))", "rBar != rPrior)"),
    ("no start on reversal bar", "                    lfwStartObs(S, availT)\n                    lfwRecord(S, 2, rBar, na, availT)\n",
     "                    S.nStartAmb := S.nStartAmb\n"),
    ("order assumed (high first)", "    if not lfwSame(a, b)\n        array.push(out, b)\n", "    if false\n        array.push(out, b)\n"),
    ("order assumed (low first)", "    array.push(out, a)\n    if not lfwSame(a, b)\n        array.push(out, b)\n",
     "    array.push(out, b)\n    if false\n        array.push(out, a)\n"),
    ("retracement after an end change used", "    lfwPoint(a, l, t, availT, ca)\n", "    lfwPoint(a, l, t, availT, false)\n"),
    ("init not excluded", "S.obsInit := S.w.init and lfwExclInit", "S.obsInit := false"),
    ("full keeps observing", "                    S.obsDone := true\n", "                    S.obsDone := false\n"),
    ("hold entry not recorded", "            if S.obsOn\n                lfwRecord(S, 4, rPrior, rBar, availT)\n            S.hold := true\n",
     "            S.hold := true\n"),
    ("release on any candidate", "    if array.size(nxt) == 1\n", "    if array.size(nxt) >= 1\n"),
    ("no dedupe", "                        dup := true\n", "                        dup := false\n"),
    ("release keeps hold-bar availability", "        nw.oAvail := availT\n", ""),
    ("init from one bar", " and S.iHiT != S.iLoT\n", "\n"),
    ("reversal origin = bar", "        w.O := w.E\n        w.oT := w.eT\n", "        w.O := p\n        w.oT := t\n"),
    ("seq not reset", "    S.obsSeq := 0\n", ""),
    ("hold: observation started", "    if S.hold\n        lfwHoldStep(S, h, l, t, atr, availT)\n",
     "    if S.hold\n        lfwHoldStep(S, h, l, t, atr, availT)\n        if S.hold and not S.obsOn\n            S.obsOn := true\n"),
]


def gate_mutation():
    global SRC_OVERRIDE, RESULTS
    keep = RESULTS
    caught, missed = 0, []
    try:
        for name, old, new in MUTATIONS:
            if SRC.count(old) != 1:
                missed.append(name + " (pattern not found once)")
                continue
            SRC_OVERRIDE = SRC.replace(old, new)
            RESULTS = []
            for g in (gate_waves, gate_hold, gate_obs):
                try:
                    g()
                except Exception:      # noqa: BLE001
                    RESULTS.append(("crash", False, ""))
            if any(not ok for _, ok, _ in RESULTS):
                caught += 1
            else:
                missed.append(name)
    finally:
        SRC_OVERRIDE, RESULTS = None, keep
    check(f"LM-01 every one of {len(MUTATIONS)} mutations of the Pine logic makes at least one LW / LH / LO check fail",
          caught == len(MUTATIONS) and not missed, str(missed))


def main():
    for g in (gate_static, gate_waves, gate_hold, gate_obs, gate_random, gate_chart, gate_mutation):
        try:
            g()
        except Exception:      # noqa: BLE001
            import traceback
            check(f"{g.__name__} completed without error", False, traceback.format_exc()[-1500:])
    w = max(len(n) for n, _, _ in RESULTS)
    fails = 0
    for n, ok, d in RESULTS:
        fails += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {n.ljust(w)[:170]}  {'' if ok else d[:600]}")
    print(f"\n{len(RESULTS) - fails}/{len(RESULTS)} passed  [PINE_NOT_VERIFIED: static / translated Pine logic]")
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
