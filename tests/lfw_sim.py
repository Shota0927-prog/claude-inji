"""LFW-1 fixtures — LongFibWave.pine (long-term Fibonacci wave indicator, D / 4H).

  LS static   : inputs (switch 0.782, start 0.10, display levels with 0.79 / no 0.786), exactly two request.security calls
                ("D" / "240", every output [1] + lookahead_on), processing gated by barstate.isconfirmed and a new confirmed
                HTF time, no strategy / entry / alert, the logic section inside the translated subset
  LW waves    : the LOGIC SECTION OF THE PINE FILE (translated by tests/acc_pine.py) on hand-made confirmed HTF bars:
                extension, 78.2 % candidate + break = same-direction switch (>= 0.782, 0.781 does not), origin touch vs
                strict break, outside bars, initialisation (ATR x 3, waits for ATR, init-wave observations excluded)
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
        """one confirmed chart execution; d / h4 = (h, l, o, t, atr) of a newly delivered confirmed HTF bar or None."""
        e = self.env
        e["time_close"] = avail
        e["lfwNewD"], e["lfwNew4"] = d is not None, h4 is not None
        for k, v in (("D", d), ("4", h4)):
            hh, ll, oo, tt, aa = v if v is not None else (None,) * 5
            e[f"lfw{k}h"], e[f"lfw{k}l"], e[f"lfw{k}o"], e[f"lfw{k}t"], e[f"lfw{k}atr"] = hh, ll, oo, tt, aa
        exec(self.code, e)
        e["__first__"] = False

    def feed4(self, bars, start=0):
        for i, b in enumerate(bars, start):
            t = T0 + i * H4
            self.exec(t + H4 + H1, h4=(b["h"], b["l"], b.get("o", (b["h"] + b["l"]) / 2), t, b.get("atr", 10.0)))
        return self

    @property
    def S(self):
        return self.env["lfw4"]

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
        "lookahead = barmerge.lookahead_on" in s and s.count("[1]") == 5 for s in sec)
    check("LS-03 exactly two request.security calls (D / 240), each output [1] with lookahead_on (confirmed bars only)",
          good and "request.security_lower_tf" not in SRC, str(sec))
    gate = all(re.search(rf"lfwNew{k} = lfwOk{k} and barstate\.isconfirmed and not na\(lfw{k}t\) and \(lfwSame{k} or "
                         rf"lfw{k}tS != nz\(lfw{k}tS\[1\], -1\)\)", SRC) for k in ("D", "4"))
    sel = all(f"lfw{k}{f}{' ' * (4 - len(f))}= lfwSame{k} ? {v}{' ' * (9 - len(v))}: lfw{k}{f}S" in SRC
              for k in ("D", "4") for f, v in (("h", "high"), ("l", "low"), ("o", "open"), ("t", "time"), ("atr", "lfwAtrC")))
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


# ============================================================================
# waves
# ============================================================================
def gate_waves():
    # LW-01 the 4H sample shape: 4,890.388 -> 3,938.849, 79.7 % rally to 4,697.322, break -> 4,697.322 -> 3,871.867
    bars = [B(4895, 4880, atr=None), B(4885, 4860), B(4890.388, 4870), B(4880, 4800), B(4795, 3938.849),
            B(4300, 4000), B(4697.322, 4400), B(4500, 4100), B(4200, 3871.867)]
    bars[1]["atr"] = 10.0
    r = Run().feed4(bars)
    S = r.S
    recs = r.recs()
    check("LW-01 sample shape: previous wave 4890.388 -> 3938.849, 79.7 % rally, break of 3938.849 -> latest wave "
          "4697.322 -> 3871.867 (down); one observation: resume, bin 70-80 %, denominator 4890.388 / 3938.849",
          S.dir == -1 and S.O == 4697.322 and S.E == 3871.867 and S.oT == T0 + 6 * H4 and S.eT == T0 + 8 * H4
          and len(recs) == 1 and recs[0].outcome == 0 and recs[0].bin == 7 and recs[0].refO == 4890.388
          and recs[0].refE == 3938.849 and S.nExclInit == 1 and not S.isInit, f"{S} {recs}")
    # LW-02 / 03 switch threshold
    a = base_run([B(782, 500), B(600, -10)]).S
    b = base_run([B(781, 500), B(600, -10)]).S
    check("LW-02 retracement exactly 0.782 then a new low: the retracement high becomes the new origin (same direction)",
          a.dir == -1 and a.O == 782 and a.E == -10 and a.oT == T0 + 4 * H4, str(a))
    check("LW-03 retracement 0.781 then a new low: same wave extended (origin kept)", b.dir == -1 and b.O == 1000 and b.E == -10, str(b))
    c = base_run([B(900, 500), B(850, 400)])
    check("LW-04 reaching 0.782 alone does not switch: wave unchanged, candidate = highest retracement high",
          c.S.dir == -1 and c.S.O == 1000 and c.S.E == 0 and c.S.rx == 900 and c.S.rxT == T0 + 4 * H4, str(c.S))
    c2 = base_run([B(900, 500), B(950, 400), B(700, -1)]).S
    check("LW-05 the candidate follows the highest retracement high (900 -> 950) and that high becomes the origin",
          c2.O == 950 and c2.oT == T0 + 5 * H4 and c2.E == -1, str(c2))
    f = base_run([B(300, 100), B(1000.5, 200)])
    check("LW-06 strict break of the origin: direction reversal, the old end (0) becomes the up wave's origin",
          f.S.dir == 1 and f.S.O == 0 and f.S.oT == T0 + 3 * H4 and f.S.E == 1000.5, str(f.S))
    t = base_run([B(1000, 500), B(900, 400)])
    check("LW-07 exact touch of the origin is not a reversal (down wave kept, origin 1000)", t.S.dir == -1 and t.S.O == 1000, str(t.S))
    o1 = base_run([B(300, 100), B(1100, -100, o=1050)]).S
    o2 = base_run([B(300, 100), B(1100, -100, o=-50)]).S
    check("LW-08 outside bar breaking both the end and the origin: path assumption (the extreme nearer the open first), the later "
          "extreme is the end (open near high -> down 1100 -> -100; open near low -> up -100 -> 1100); counted as order-unknown wave",
          (o1.dir, o1.O, o1.E, o1.nWaveAmb) == (-1, 1100, -100, 1) and (o2.dir, o2.O, o2.E, o2.nWaveAmb) == (1, -100, 1100, 1),
          f"{o1} {o2}")
    up = base_run([B(300, 100), B(1001, 200), B(1500, 900), B(1200, 800), B(1600, 1100)]).S
    check("LW-09 up wave extends on higher highs (origin = the low 0 kept)", up.dir == 1 and up.O == 0 and up.E == 1600, str(up))
    # initialisation
    r0 = Run().feed4([B(110, 100, atr=None), B(105, 60, atr=None), B(104, 70, atr=None)])
    r1 = copy.deepcopy(r0)
    r1.feed4([B(103, 95, atr=15.0)], start=3)
    check("LW-10 initialisation waits for the HTF ATR; the first wave is fixed on the bar where high-low range >= ATR x 3.0 "
          "(range 50 < 45? no: 50 >= 45 -> down 110 -> 60, flagged as init wave, ATR / time stored)",
          r0.S.dir == 0 and r1.S.dir == -1 and r1.S.O == 110 and r1.S.E == 60 and r1.S.isInit and r1.S.initAtr == 15.0
          and r1.S.initAvail == T0 + 3 * H4 + H4 + H1, f"{r0.S} {r1.S}")
    r2 = Run().feed4([B(110, 100, atr=None), B(105, 60, atr=20.0)])
    check("LW-11 range below ATR x 3.0 (50 < 60): no wave yet", r2.S.dir == 0, str(r2.S))
    r3 = Run().feed4([B(150, 100, o=145, atr=10.0)])
    r4 = Run().feed4([B(150, 100, o=105, atr=10.0)])
    check("LW-12 init high and low on the same bar: open near the high -> high first -> down wave; near the low -> up wave",
          (r3.S.dir, r3.S.O, r3.S.E) == (-1, 150, 100) and (r4.S.dir, r4.S.O, r4.S.E) == (1, 100, 150), f"{r3.S} {r4.S}")


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
          and r.S.E == -1 and r.S.O == 1000 and cnt(r.S, -1, 1, 0) == 0 and cnt(r.S, -1, 1, 4) == 1, str(rc))
    r = base_run([B(1000, 500), B(900, 400), B(800, -5)])
    rc = r.recs()
    check("LO-04 exact touch of the origin: observation ends as full retracement (bin 100 %), no new observation for the same end; "
          "then the new low switches the wave from the touched high (origin 1000 at the touch bar), no resume recorded",
          len(rc) == 1 and rec_t(rc[0]) == (-1, 1, 10, 1.0, None, 1000, 0, 1) and r.S.O == 1000 and r.S.oT == T0 + 4 * H4
          and r.S.E == -5 and r.S.nStartAmb == 0, str(rc) + str(r.S))
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
    r = base_run([B(300, 100), B(1000, -1)])
    rc = r.recs()
    check("LO-08 new low and origin touch on the same bar: order unknown (alt 100 %), wave extended, candidate ambiguity counted",
          len(rc) == 1 and rc[0].outcome == 4 and rc[0].rAlt == 1.0 and r.S.E == -1 and r.S.O == 1000 and r.S.nCandAmb == 1, str(rc))
    r = base_run([B(300, 100), B(1100, -100, o=1050)])
    rc = r.recs()
    check("LO-09 outside bar through both ends: the live observation is order unknown", len(rc) == 1 and rc[0].outcome == 4, str(rc))
    r = base_run([B(300, 100), B(200, -100), B(10, -50), B(0, -200)])
    rc = r.recs()
    check("LO-10 repeated observation: after the resume (new end -100) a 10 % retracement of 1000 -> -100 starts #2 with the NEW "
          "fixed denominator; same wave id",
          len(rc) == 2 and rec_t(rc[0]) == (-1, 0, 3, 0.3, None, 1000, 0, 1) and rec_t(rc[1]) == (-1, 0, 1, 0.1, None, 1000, -100, 2)
          and rc[0].waveId == rc[1].waveId, str(rc))
    r = base_run([B(782, 500), B(600, -10), B(100, -5), B(-5, -20)])
    rc = r.recs()
    check("LO-11 resume and same-direction switch on one bar: the old observation's resume is saved first (once, old denominator "
          "1000 / 0), then the new wave 782 -> -10 starts its own observations (#1, new wave id)",
          len(rc) == 2 and rec_t(rc[0]) == (-1, 0, 7, 0.782, None, 1000, 0, 1) and rec_t(rc[1])[5:] == (782, -10, 1)
          and rc[1].waveId == rc[0].waveId + 1 and sum(r.S.cnt) == 2, str(rc))
    r = base_run([B(300, 100), B(1000.5, 200), B(900, 700)])
    check("LO-12 no observation carried across a direction reversal (old one closed as switch-end; up wave 0 -> 1000.5 starts "
          "its own when it retraces 10 %)", len(r.recs()) == 1 and r.S.obsOn and r.S.obsO == 0 and r.S.obsE == 1000.5
          and r.S.obsDir == 1, str(r.S))
    r = base_run([B(50, -10), B(150, -20)])
    check("LO-13 a bar making a new low whose high reaches 10 % of the old wave: no observation (order unknown start, counted)",
          not r.recs() and r.S.nStartAmb == 1, str(r.S))
    r = base_run([B(300, 100), B(350, 150), B(320, 120), B(400, 200)])
    check("LO-14 no expiry: the observation stays live while neither end nor origin is reached (max 40 %)",
          r.S.obsOn and abs((r.S.E - r.S.rx) / (r.S.E - r.S.O) - 0.4) < 1e-12 and not r.recs(), str(r.S))
    # init exclusion
    r = Run().feed4([B(1001, 995, atr=None), B(998, 990, atr=3.0), B(1000, 992), B(995, 0)])
    q = Run({"lfwExclInit": False}).feed4([B(1001, 995, atr=None), B(998, 990, atr=3.0), B(1000, 992), B(995, 0)])
    check("LO-15 observations of the initialisation wave are excluded (counted separately) by default; included when the input is off",
          not r.recs() and r.S.nExclInit == 1 and len(q.recs()) == 1 and q.S.nExclInit == 0 and q.recs()[0].outcome == 0, str(q.recs()))
    r = Run({"lfwStartRatio": 0.3}).feed4(BASE + [B(250, 100), B(299, 100)])
    s2 = Run({"lfwSwitchRatio": 0.5}).feed4(BASE + [B(500, 100), B(300, -1)])
    check("LO-16 the start ratio and the switch ratio are inputs (start 0.3: 29.9 % no observation; switch 0.5: 50 % + new low switches)",
          not r.S.obsOn and s2.S.O == 500, f"{r.S} {s2.S}")


# ============================================================================
# reference model (written from the spec, independent of the Pine text)
# ============================================================================
class Ref:
    def __init__(self, sw=0.782, st=0.10, mult=3.0, excl=True):
        self.sw, self.st, self.mult, self.excl = sw, st, mult, excl
        self.dir = 0
        self.init = False
        self.wid = 0
        self.O = self.E = self.oT = self.eT = None
        self.ret = self.retT = None          # most retraced price since the end (down: highest high, up: lowest low)
        self.obs = None                      # dict(dir, O, E, seq, init, start)
        self.done = False                    # full retracement already recorded for this end
        self.seq = 0
        self.hi = self.lo = self.hiT = self.loT = self.iop = None
        self.recs, self.excl_n, self.start_amb, self.cand_amb, self.wave_amb = [], 0, 0, 0, 0

    def ratio(self, p):
        return (p - self.E) / (self.O - self.E) if self.dir == -1 else (self.E - p) / (self.E - self.O)

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
        self.obs = dict(dir=self.dir, O=self.O, E=self.E, seq=self.seq, init=self.init and self.excl, start=av)

    def wave(self, d, O, oT, E, eT):
        self.dir, self.O, self.oT, self.E, self.eT = d, O, oT, E, eT
        self.ret = self.retT = None
        self.obs, self.done, self.seq = None, False, 0
        self.wid += 1
        self.init = False

    def bar(self, h, l, o, t, atr, av):
        if self.dir == 0:
            if self.hi is None or h > self.hi:
                self.hi, self.hiT, self.iop = h, t, o
            if self.lo is None or l < self.lo:
                self.lo, self.loT, self.iop = l, t, o
            if atr is not None and atr > 0 and self.hi - self.lo >= self.mult * atr:
                if self.hiT != self.loT:
                    down = self.hiT < self.loT
                else:
                    down = abs(self.hi - self.iop) < abs(self.lo - self.iop)
                if down:
                    self.wave(-1, self.hi, self.hiT, self.lo, self.loT)
                else:
                    self.wave(1, self.lo, self.loT, self.hi, self.hiT)
                self.init = True
            return
        down = self.dir == -1
        new_ext = l < self.E if down else h > self.E
        rp = h if down else l                      # retracement-side wick
        ep = l if down else h                      # extension-side wick
        brk = rp > self.O if down else rp < self.O
        touch = rp == self.O
        r_prior = 0.0 if self.ret is None else self.ratio(self.ret)
        r_bar = self.ratio(rp)
        if new_ext and brk:
            if self.obs:
                self.close(4, r_prior, r_bar, av)
            self.wave_amb += 1
            high_first = abs(h - o) < abs(l - o)
            if high_first:      # H then L : the later extreme is the low
                self.wave(-1, h, t, l, t)
            else:
                self.wave(1, l, t, h, t)
            return
        if new_ext:
            if self.obs:
                if r_bar > r_prior and (r_bar >= 1 or self.bin(r_bar) != self.bin(r_prior)):
                    self.close(4, r_prior, r_bar, av)
                else:
                    self.close(0, r_prior, None, av)
            elif not self.done and r_bar >= self.st:
                self.start_amb += 1
            if r_bar > r_prior and r_bar >= self.sw:
                self.cand_amb += 1
            if self.ret is not None and r_prior >= self.sw:
                self.wave(self.dir, self.ret, self.retT, ep, t)
            else:
                self.E, self.eT = ep, t
                self.ret = self.retT = None
                self.done = False
            return
        if brk:
            if not self.obs and not self.done:
                self.open(av)
            if self.obs:
                self.close(2, r_bar, None, av)
            self.wave(-self.dir, self.E, self.eT, rp, t)
            return
        if self.ret is None or r_bar > r_prior:
            self.ret, self.retT = rp, t
        if not self.obs and not self.done and self.ratio(self.ret) >= self.st:
            self.open(av)
        if self.obs and touch:
            self.close(1, 1.0, None, av)
            self.done = True


def pine_tuple(S):
    recs = [(r.dir, r.waveId, r.seq, r.refO, r.refE, r.startAvail, r.endAvail, r.outcome, r.rMax, r.rAlt, r.bin) for r in S.recs]
    return (S.dir, S.O, S.oT, S.E, S.eT, S.waveId, S.rx, recs, S.nExclInit, S.nStartAmb, S.nCandAmb, S.nWaveAmb,
            S.obsOn, S.obsO if S.obsOn else None, S.obsE if S.obsOn else None)


def ref_tuple(R):
    return (R.dir, R.O, R.oT, R.E, R.eT, R.wid, R.ret, R.recs, R.excl_n, R.start_amb, R.cand_amb, R.wave_amb,
            R.obs is not None, R.obs["O"] if R.obs else None, R.obs["E"] if R.obs else None)


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
        h = max(h, o)
        out.append(dict(h=h, l=min(l, o), o=o, atr=None if i < 14 else atr))
        atr = atr * 13 / 14 + (h - l) / 14
        p = c
    return out


def run_ref(bars, **kw):
    R = Ref(**kw)
    for i, b in enumerate(bars):
        t = T0 + i * H4
        R.bar(b["h"], b["l"], b.get("o", (b["h"] + b["l"]) / 2), t, b.get("atr", 10.0), t + H4 + H1)
    return R


def gate_random():
    bad = []
    n_rec = 0
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
            kinds |= {x[7] for x in R.recs}
    check(f"LR-01 translated Pine == independent reference model on 36 random HTF series ({n_rec} observations, outcomes "
          f"{sorted(kinds)}): wave state, candidate, records, counters", not bad and kinds == {0, 1, 2, 4}, str(bad))
    bad = []
    for seed in range(8):
        bars = rand_series(100 + seed)
        mir = [dict(h=-b["l"], l=-b["h"], o=-b["o"], atr=b["atr"]) for b in bars]
        A = Run({"lfwMaxRecs": 100000}).feed4(bars).S
        M = Run({"lfwMaxRecs": 100000}).feed4(mir).S
        ra = [(r.dir, r.outcome, r.bin, r.refO, r.refE, r.seq) for r in A.recs]
        rm = [(-r.dir, r.outcome, r.bin, -r.refO, -r.refE, r.seq) for r in M.recs]
        if not (A.dir == -M.dir and A.O == -M.O and A.E == -M.E and ra == rm):
            bad.append(seed)
    check("LR-02 up / down symmetry: negating every price swaps the directions and gives the same observations and waves", not bad, str(bad))
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
            fe = (b["h"], b["l"], b["o"], T0 + (k - 1) * H4, b["atr"])
        new = fe is not None and fe[3] != (prev_t if prev_t is not None else -1)
        if ticks and i > 0:      # realtime-like unconfirmed executions first: lfwNew4 is false (barstate.isconfirmed false)
            snap = copy.deepcopy(pine_tuple(r.S))
            r.exec(cb["t"] + H1)
            if pine_tuple(r.S) != snap:
                log.append(("changed_unconfirmed", i))
        r.exec(cb["t"] + H1, h4=fe if new else None)
        if new:
            log.append((fe[3], cb["t"] + H1))
        prev_t = fe[3] if fe is not None else prev_t
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
        direct.exec(t + H4 + H1, h4=(b["h"], b["l"], b["o"], t, b["atr"]))
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
            ref.exec(t + H4 + H1, h4=(b["h"], b["l"], b["o"], t, b["atr"]))
        if pine_tuple(p.S) != pine_tuple(ref.S) or pine_tuple(full_at.S) != pine_tuple(p.S):
            bad.append(cut)
    check("LC-04 prefix runs (chart cut inside a forming 4H bar) use only the 4H bars closed before the cut", not bad, str(bad))


# ============================================================================
# mutation
# ============================================================================
MUTATIONS = [
    ("switch >= -> >", "bool candOn = not na(S.rx) and rPrior >= lfwSwitchRatio", "bool candOn = not na(S.rx) and rPrior > lfwSwitchRatio"),
    ("start >= -> >", "if not S.obsOn and not S.obsDone and r >= lfwStartRatio", "if not S.obsOn and not S.obsDone and r > lfwStartRatio"),
    ("touch = 99.9 %", "if S.obsOn and T\n", "if S.obsOn and rBar >= 0.999\n"),
    ("origin break >=", "bool B = s * (S.O - retP) > 0", "bool B = s * (S.O - retP) >= 0"),
    ("resume uses bar high", "lfwRecord(S, 0, rPrior, na, availT)", "lfwRecord(S, 0, math.max(rPrior, rBar), na, availT)"),
    ("switch origin = old origin", "lfwNewWave(S, s, S.rx, S.rxT, extP, t, availT)", "lfwNewWave(S, s, S.O, S.oT, extP, t, availT)"),
    ("unknown on any higher high", "lfwBin(rBar) != lfwBin(rPrior))", "rBar != rPrior)"),
    ("no start on reversal bar", "                lfwStartObs(S, availT)\n                lfwRecord(S, 2, rBar, na, availT)\n",
     "                S.nStartAmb := S.nStartAmb\n"),
    ("path inverted", "bool retFirst = s == 1 ? not hiFirst : hiFirst", "bool retFirst = s == 1 ? hiFirst : not hiFirst"),
    ("init not excluded", "S.obsInit := S.isInit and lfwExclInit", "S.obsInit := false"),
    ("full keeps observing", "                S.obsDone := true\n", "                S.obsDone := false\n"),
    ("switch before saving", "            if S.obsOn\n                if rBar > rPrior and (rBar >= 1.0",
     "            if candOn0\n                S.obsOn := false\n            if S.obsOn\n                if rBar > rPrior and (rBar >= 1.0"),
    ("reversal origin = bar", "lfwNewWave(S, -s, S.E, S.eT, retP, t, availT)", "lfwNewWave(S, -s, extP, t, retP, t, availT)"),
    ("init ATR mult ignored", "S.iHi - S.iLo >= lfwInitAtrMult * atr", "S.iHi - S.iLo >= atr"),
    ("seq not reset", "    S.obsSeq := 0\n", ""),
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
            m = SRC.replace(old, new)
            if name == "switch before saving":
                m = m.replace("        else if X\n", "        else if X\n            bool candOn0 = not na(S.rx) and rPrior >= lfwSwitchRatio\n", 1)
            SRC_OVERRIDE = m
            RESULTS = []
            for g in (gate_waves, gate_obs):
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
    check(f"LM-01 every one of {len(MUTATIONS)} mutations of the Pine logic makes at least one LW / LO check fail",
          caught == len(MUTATIONS) and not missed, str(missed))


def main():
    for g in (gate_static, gate_waves, gate_obs, gate_random, gate_chart, gate_mutation):
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
