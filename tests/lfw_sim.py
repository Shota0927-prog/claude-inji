"""LFW fixtures — LongFibWave.pine (long-term Fibonacci wave indicator, D / 4H; LFW-3: major highs / lows).

  LS static   : inputs (switch 0.782, start 0.10, pivots D 20/3 and 4H 60/3, ATR 14 x 5.0, display levels with 0.79 / no 0.786,
                per-TF display toggles), exactly two request.security calls ("D" / "240", every output [1] + lookahead_on),
                confirmed-bar processing, no strategy / entry / alert, logic inside the translated subset, no intrabar-order
                assumption, no ATR x 3 cumulative initialisation, unadopted candidates never drawn, fixture registration
  LW waves    : the LOGIC SECTION OF THE PINE FILE (translated by tests/acc_pine.py) on hand-made confirmed HTF bars: sample shape
                (both through 0.782 and through major lows / highs), extension, 0.782 candidate + break = same-direction switch,
                origin touch vs strict break, first wave from a confirmed major high / low
  LP major    : spec cases A-K (opposite wave from a confirmed pivot + fixed ATR x 5 without breaking the old origin, symmetric,
                right-side confirmation, ATR boundary / fixed at the extreme bar, own opposite wick not used, same-direction pivot
                ignored, invalidation / replacement / no double adoption / tie at start, unadopted candidate not shown,
                switch-end below 100 % in its real bin, no retroactive observation, holds evaluated on every candidate)
  LH hold     : no intrabar-order assumption: holds, release, symmetric, no observation during / from a hold, no double count
  LO obs      : start at 10 %, fixed denominator, resume / full / switch-end / order-unknown / live, repeated observations,
                equal low is not a new low, conservation (formal = ended + live), observed-wave count vs observation count
  LR random   : translated Pine == an independent reference model written from the spec (pivots, adoption, holds, records,
                counters) on random HTF series; mirror symmetry; counters == records; no observation inside holds
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
BIG = 1000.0                    # default ATR of hand-made bars: 5 x 1000 is never reached, so only marked pivots can be adopted


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


def logic(src):
    i, j = src.index(BEGIN), src.index(END)
    return src[src.index("\n", i) + 1:j]


def transpile(src):
    return ap.Translator().translate(ap.logical_lines(logic(src)))


def tb(i):
    return T0 + i * H4


def av(i):
    return tb(i) + H4 + H1


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
        self.n = 0

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

    def feed4(self, bars):
        for b in bars:
            i = self.n
            self.exec(av(i), h4=(b["h"], b["l"], tb(i), b.get("atr", BIG)))
            self.n += 1
        return self

    def feedD(self, bars):
        for b in bars:
            i = self.n
            self.exec(av(i), d=(b["h"], b["l"], tb(i), b.get("atr", BIG)))
            self.n += 1
        return self

    @property
    def S(self):
        return self.env["lfw4"]

    @property
    def W(self):
        return self.env["lfw4"].w

    def recs(self):
        return list(self.S.recs)

    def fn(self, name):
        return self.env[name]


def B(h, l, o=None, atr=BIG):
    d = dict(h=h, l=l, atr=atr)
    if o is not None:
        d["o"] = o
    return d


def fill(n, h, l):
    return [B(h, l) for _ in range(n)]


def neg(bars):
    return [dict(h=-b["l"], l=-b["h"], atr=b.get("atr", BIG), **({"o": -b["o"]} if "o" in b else {})) for b in bars]


# BASE (default 4H pivots 60 / 3, ATR x 5):
#   60 flat bars (equal highs / lows: never a strict pivot), major low 400 (ATR 10) + 3 rising bars -> first wave up 400 -> 800,
#   major high 1000 (ATR 10) + 3 falling bars down to 0 -> a NON-first down wave 1000 -> 0 adopted from the major high.
#   After BASE the retracement ratio of a high h is h / 1000 (other bars carry ATR 1000, so no further pivot is adopted).
BASE = (fill(60, 510, 500) + [B(505, 400, atr=10.0), B(600, 450), B(700, 550), B(800, 650),
                             B(1000, 900, atr=10.0), B(950, 700), B(750, 450), B(420, 0)])
NB = len(BASE)                  # 68
IP1, IR3, IP2, ID3 = 60, 63, 64, 67


def base_run(extra, overrides=None):
    return Run(overrides).feed4(BASE + extra)


def X(j):
    """index of the j-th bar appended after BASE"""
    return NB + j


def rec_t(r):
    return (r.dir, r.outcome, r.bin, round(r.rMax, 9), None if r.rAlt is None else round(r.rAlt, 9), r.refO, r.refE, r.seq)


def cnt(S, d, b, o):
    return S.cnt[((0 if d == 1 else 1) * 12 + b) * 5 + o]


def live(S, d):
    return 1 if (S.obsOn and not S.obsInit and S.obsDir == d) else 0


def formal(S, d):
    return sum(cnt(S, d, b, o) for b in range(12) for o in (0, 1, 2, 4)) + live(S, d)


# ============================================================================
# static
# ============================================================================
def gate_static():
    inp = ap.inputs(SRC)
    want = dict(lfwSwitchRatio=0.782, lfwStartRatio=0.10, lfwAtrLen=14, lfwExclInit=True, lfwPivLD=20, lfwPivRD=3, lfwPivMD=5.0,
                lfwPivL4=60, lfwPivR4=3, lfwPivM4=5.0, lfwShowD=True, lfwShow4=True, lfwOnD=True, lfwOn4=True)
    check("LS-01 inputs: switch ratio 0.782, observation start 0.10, ATR 14, pivots D 20 / 3 and 4H 60 / 3, ATR x 5.0 for each, "
          "first-wave exclusion on, per-TF calculation and display toggles",
          all(inp.get(k) == v for k, v in want.items()) and "lfwInitAtrMult" not in inp,
          str({k: inp.get(k) for k in want}))
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
    draw = SRC[SRC.index("f_draw(LfwTf S"):SRC.index("var array<line>  lfwLnD")]
    check("LS-08 no ATR x 3 cumulative initialisation left (no running highest / lowest pair); the chart drawing uses only the "
          "confirmed wave or the hold candidates (unadopted major highs / lows are never drawn); drawing objects are pooled",
          not re.search(r"iHi|iLo|lfwInitAtrMult|lfwInitStep", SRC) and "cHi" not in draw and "cLo" not in draw
          and "f_ln(lns, nl)" in draw and "line.new" not in draw and "label.new" not in draw and "extend.right" not in SRC)
    import subprocess
    import lfw_build as lb
    bad = []
    for path, eds in lb.TEST_EDITS.items():
        cur = open(os.path.join(ROOT, path), encoding="utf-8").read()
        if not all(cur.count(new) == cnt_ for _, new, cnt_ in eds):
            bad.append((path, "edit not applied exactly"))
        elif lb.unadapt(path, cur) != subprocess.run(["git", "-C", ROOT, "show", f"{lb.REG_BASE}:{path}"], capture_output=True,
                                                     text=True).stdout:
            bad.append((path, "unadapt != the text before the edits"))
    acc = __import__("acc_build")
    stray = ("LongFibWave.pine.bak", "tests/lfw_other.py", "LONG_FIB_WAVE.md", "tests/lfw_build.pyc")
    check("LS-09 registration in the older fixtures (tests/lfw_build.py, same method as fds_build / lab_build): every recorded edit "
          "present exactly, unadapt() gives the pre-edit text byte for byte, acc_build.ok() accepts exactly the 4 LFW files "
          "(and no similarly named stray file)",
          not bad and set(lb.NEW_FILES) == {"LongFibWave.pine", "LONG_FIB_WAVE_ja.md", "tests/lfw_sim.py", "tests/lfw_build.py"}
          and all(acc.ok(f) and os.path.exists(os.path.join(ROOT, f)) for f in lb.NEW_FILES)
          and not any(acc.ok(f) for f in stray), str(bad))


# ============================================================================
# waves
# ============================================================================
def gate_waves():
    # LW-00 BASE itself
    r = Run().feed4(BASE[:IR3 + 1])
    q = base_run([])
    check("LW-00 BASE: the first wave is adopted from the confirmed major low 400 when its 3rd right bar closes (up 400 -> 800, "
          "first wave, ATR 10 stored); the major high 1000 + a fall of 1000 >= 10 x 5 then gives a NON-first down wave 1000 -> 0",
          (r.W.dir, r.W.O, r.W.oT, r.W.E, r.W.eT, r.W.init) == (1, 400, tb(IP1), 800, tb(IR3), True)
          and r.S.initAvail == av(IR3) and r.S.initAtr == 10.0
          and (q.W.dir, q.W.O, q.W.oT, q.W.E, q.W.eT, q.W.init) == (-1, 1000, tb(IP2), 0, tb(ID3), False)
          and q.W.oAvail == av(ID3) and q.W.rx is None and not q.S.hold and q.S.nAdopt == 2, f"{r.W} {q.W}")
    # LW-01 the 4H sample shape (a): 4,890.388 -> 3,938.849 (major high, the 3,938.849 low is never adopted: its ATR is large),
    # 79.7 % rally to 4,697.322, break of 3,938.849 -> 4,697.322 -> 3,871.867 by the 0.782 rule
    pre = fill(60, 4500, 4490) + [B(4890.388, 4700, atr=30.0), B(4800, 4500), B(4600, 4200), B(4300, 3938.849)]
    post = [B(4300, 4000), B(4697.322, 4400), B(4500, 4100), B(4200, 3871.867)]
    a = Run().feed4(pre)
    a_prev = (a.W.dir, a.W.O, a.W.E)
    a.feed4(post)
    check("LW-01 sample shape through the 0.782 rule: wave 4890.388 -> 3938.849, 79.7 % rally to 4697.322, break of 3938.849 -> "
          "latest wave 4697.322 -> 3871.867 (origin at the rally high, end at the new low)",
          a_prev == (-1, 4890.388, 3938.849) and (a.W.dir, a.W.O, a.W.oT, a.W.E, a.W.eT) == (-1, 4697.322, tb(65), 3871.867, tb(67)),
          f"{a_prev} {a.W}")
    # (b) every bar with ATR 50: the low 3,938.849 is a major low (rise 758 >= 250) -> up wave, the 4,697.322 high is NOT a
    # major high (4,890.388 is inside its 60-bar left side) -> the break of 3,938.849 reverses -> 4,697.322 -> 3,871.867 again
    b = Run().feed4([dict(x, atr=50.0) for x in pre + post])
    check("LW-02 sample shape with ATR 50 everywhere: the 3938.849 low is adopted as an up wave 3938.849 -> 4697.322, the "
          "4697.322 high is not a 60-bar major high, so the break of 3938.849 reverses to the same latest wave 4697.322 -> 3871.867",
          (b.W.dir, b.W.O, b.W.oT, b.W.E, b.W.eT) == (-1, 4697.322, tb(65), 3871.867, tb(67)) and b.S.nAdopt == 2, str(b.W))
    a2 = base_run([B(782, 500), B(600, -10)]).W
    b2 = base_run([B(781, 500), B(600, -10)]).W
    check("LW-03 retracement exactly 0.782 then a new low: the retracement high becomes the new origin (same direction)",
          a2.dir == -1 and a2.O == 782 and a2.E == -10 and a2.oT == tb(X(0)) and a2.oAvail == av(X(1)), str(a2))
    check("LW-04 retracement 0.781 then a new low: same wave extended (origin kept, end and Fibonacci updated)",
          b2.dir == -1 and b2.O == 1000 and b2.oT == tb(IP2) and b2.E == -10 and b2.eT == tb(X(1)), str(b2))
    c = base_run([B(900, 500), B(850, 400)]).W
    check("LW-05 reaching 0.782 alone does not switch: wave unchanged, candidate = highest retracement high",
          c.dir == -1 and c.O == 1000 and c.E == 0 and c.rx == 900 and c.rxT == tb(X(0)), str(c))
    c2 = base_run([B(900, 500), B(950, 400), B(700, -1)]).W
    check("LW-06 the candidate follows the highest retracement high (900 -> 950) and that high becomes the origin",
          c2.O == 950 and c2.oT == tb(X(1)) and c2.E == -1, str(c2))
    f = base_run([B(300, 100), B(1000.5, 200)]).W
    check("LW-07 strict break of the origin: direction reversal, the old end (0) becomes the up wave's origin",
          f.dir == 1 and f.O == 0 and f.oT == tb(ID3) and f.E == 1000.5, str(f))
    t = base_run([B(1000, 500), B(900, 400)]).W
    check("LW-08 exact touch of the origin is not a reversal (down wave kept, origin 1000)", t.dir == -1 and t.O == 1000, str(t))
    up = base_run([B(300, 100), B(1001, 200), B(1500, 900), B(1200, 800), B(1600, 1100)]).W
    check("LW-09 up wave extends on higher highs (origin = the low 0 kept)", up.dir == 1 and up.O == 0 and up.E == 1600, str(up))
    m = Run().feed4(neg(BASE + [B(782, 500), B(600, -10)])).W
    check("LW-10 up / down symmetry of the 0.782 switch (prices negated): up wave -782 -> 10", (m.dir, m.O, m.E) == (1, -782, 10), str(m))
    n = Run().feed4(fill(70, 510, 500) + [B(505, 400), B(600, 450), B(700, 550), B(800, 650), B(900, 300), B(950, 250)])
    check("LW-11 no wave while no confirmed major high / low reaches its ATR x 5 move (ATR 1000): no ATR x 3 fallback",
          n.W.dir == 0 and not n.S.hold and n.S.nAdopt == 0, str(n.W))


# ============================================================================
# major highs / lows (spec cases A-K)
# ============================================================================
# UP: a first up wave 50 -> 140 from the major low 50 (ATR 2), then a rise to 300 without any 60-bar major high
UP = (fill(60, 110, 100) + [B(105, 50, atr=2.0), B(120, 60), B(130, 70), B(140, 80)]
      + [B(150 + 10 * k, 90 + 10 * k) for k in range(16)])          # highs 150 .. 300, lows 90 .. 240
NU = len(UP)                                                          # 80


def up_with(pivot, right):
    """UP + a major high bar + its right bars (index of the pivot = NU)"""
    return UP + [pivot] + right


def gate_major():
    base = Run().feed4(UP)
    check("LP-00 UP fixture: up wave 50 -> 300 (origin far below, never broken in the cases below)",
          (base.W.dir, base.W.O, base.W.E) == (1, 50, 300), str(base.W))
    # A) a confirmed major high + a fall >= its fixed ATR x 5 adopts a down wave although the old origin 50 is not broken
    rA = Run().feed4(up_with(B(310, 280, atr=4.0), [B(305, 295), B(300, 291), B(298, 288)]))
    check("LP-A long rise, then the confirmed major high 310 (ATR 4 -> 20) and a fall to 288 (22 >= 20): new down wave "
          "310 -> 288 adopted on the 3rd right bar (origin 50 never broken); origin / end times = extreme bars, availability = "
          "adoption bar", (rA.W.dir, rA.W.O, rA.W.oT, rA.W.E, rA.W.eT) == (-1, 310, tb(NU), 288, tb(NU + 3))
          and rA.W.oAvail == av(NU + 3) and rA.W.eAvail == av(NU + 3) and not rA.W.init and rA.S.cHi.adopted, str(rA.W))
    rB = Run().feed4(neg(up_with(B(310, 280, atr=4.0), [B(305, 295), B(300, 291), B(298, 288)])))
    check("LP-B symmetric: long fall, confirmed major low -310 and a rise to -288 -> up wave -310 -> -288",
          (rB.W.dir, rB.W.O, rB.W.E) == (1, -310, -288) and rB.S.cLo.adopted, str(rB.W))
    # C) right side: the fall is already enough on the 1st right bar, but the candidate exists only after the 3rd
    seqC = up_with(B(310, 300, atr=4.0), [B(305, 280), B(300, 285), B(298, 286)])
    c1 = Run().feed4(seqC[:NU + 2])
    c2 = Run().feed4(seqC[:NU + 3])
    c3 = Run().feed4(seqC)
    check("LP-C the move alone does not replace the confirmation: after 1 / 2 right bars (fall 30 >= 20 already) still the up "
          "wave and no candidate; adopted on the 3rd right bar with the lowest low after the high (280 on the 1st right bar)",
          c1.W.dir == 1 and c2.W.dir == 1 and c1.S.cHi is None and c2.S.cHi is None
          and (c3.W.dir, c3.W.O, c3.W.E, c3.W.eT, c3.W.oAvail) == (-1, 310, 280, tb(NU + 1), av(NU + 3)), f"{c2.W} {c3.W}")
    # D) ATR boundary and the ATR fixed at the extreme bar
    res = {}
    for name, low in (("below", 290.01), ("equal", 290.0), ("above", 289.99)):
        rr = Run().feed4(up_with(B(310, 300, atr=4.0), [B(305, 296, atr=0.1), B(304, 295, atr=50.0), B(303, low, atr=90.0)]))
        res[name] = (rr.W.dir, rr.S.cHi.thr if rr.S.cHi else None)
    check("LP-D threshold = ATR of the extreme bar x 5 = 20 (fixed: the right bars' ATR 0.1 / 50 / 90 change nothing): a fall of "
          "19.99 keeps the up wave, exactly 20 and 20.01 adopt the down wave", res["below"] == (1, 20.0) and res["equal"][0] == -1
          and res["above"][0] == -1, str(res))
    # E) the extreme bar's own low is not part of the move
    rE = Run().feed4(up_with(B(310, 250, atr=4.0), [B(305, 296), B(304, 295), B(303, 294)]))
    check("LP-E the major high bar's own low (250, 60 below) is not used: only the later lows (294, fall 16 < 20) -> no adoption, "
          "candidate end = 294", rE.W.dir == 1 and rE.S.cHi is not None and rE.S.cHi.ext == 294, str(rE.S.cHi))
    # F) a same-direction major high inside a down wave does not move the origin
    seqF = BASE + fill(60, 90, 50) + [B(300, 60, atr=4.0), B(280, 58), B(200, 55), B(150, 52)]
    rF = Run().feed4(seqF)
    check("LP-F inside the down wave 1000 -> 0, a confirmed major high 300 with a fall of 248 >= 20 is a same-direction pivot: "
          "origin 1000 and end 0 unchanged (only the 0.782 rule moves a down origin)",
          (rF.W.dir, rF.W.O, rF.W.E) == (-1, 1000, 0) and rF.S.cHi is not None and not rF.S.cHi.adopted and rF.S.nAdopt == 2, str(rF.W))
    # G) invalidation, replacement, no double adoption, tie at the start
    rG = Run().feed4(up_with(B(310, 300, atr=4.0), [B(305, 296), B(304, 295), B(303, 294), B(311, 296), B(300, 250)]))
    check("LP-G1 a later high above the unadopted major high (311 > 310) invalidates it: the later fall to 250 adopts nothing "
          "(the up wave just extends to 311 and stays up)", rG.W.dir == 1 and rG.W.E == 311 and rG.S.nCandBroken >= 1
          and rG.S.nAdopt == 1, str(rG.W))
    seqG2 = up_with(B(310, 300, atr=4.0), [B(305, 296), B(304, 295), B(303, 294)])
    seqG2 += fill(60, 300, 292) + [B(309, 300, atr=2.0), B(305, 299), B(304, 298), B(303, 297)]
    rG2 = Run().feed4(seqG2)
    check("LP-G2 a newer confirmed major high (309, ATR 2 -> 10) replaces the older unadopted one (310, still valid, fall 18 < 20): "
          "the adopted down wave starts at 309 (fall 12 >= 10)", (rG2.W.dir, rG2.W.O, rG2.W.oT) == (-1, 309, tb(len(seqG2) - 4)), str(rG2.W))
    adopt = rA.fn("lfwAdopt")
    LW = rA.fn("LfwWave")
    w_up_old = LW.new(1, False, 40, tb(10), 0, 400, tb(NU), 0)
    again = adopt(rA.S, w_up_old, av(999))
    c_hi = rA.S.cHi
    keep = c_hi.adopted
    c_hi.adopted = False
    w_up_new = LW.new(1, False, 40, tb(NU + 1), 0, 400, tb(NU + 2), 0)
    newer = adopt(rA.S, w_up_new, av(999))
    fresh = adopt(rA.S, w_up_old, av(999))
    c_hi.adopted = keep
    check("LP-G3 no double adoption: an adopted candidate is never adopted again; an opposite candidate must be newer than the "
          "current wave's origin bar (same candidate not adopted for an up wave whose origin is after it)",
          again is None and newer is None and fresh is not None and fresh.O == 310, f"{again} {newer} {fresh}")
    tie = fill(60, 510, 500) + [B(600, 400, atr=10.0), B(550, 450), B(560, 440), B(540, 460)]
    rT = Run().feed4(tie)
    rT1 = Run().feed4(tie + [B(530, 300, atr=10.0)])
    rT2 = Run().feed4(tie + [B(530, 300, atr=10.0), B(520, 350), B(560, 360), B(580, 370)])
    check("LP-G4 at the start, a bar that is both a confirmed major high and a confirmed major low (both moves enough) gives no "
          "first wave (direction not chosen); once a later bar breaks the major low, only the major high is usable -> first "
          "wave down 600 -> 300; the newer major low 300 then adopts up 300 -> 580 (not a first wave)",
          rT.W.dir == 0 and rT.S.cHi is not None and rT.S.cLo is not None
          and (rT1.W.dir, rT1.W.O, rT1.W.E, rT1.W.init) == (-1, 600, 300, True)
          and (rT2.W.dir, rT2.W.O, rT2.W.E, rT2.W.init) == (1, 300, 580, False), f"{rT.W} {rT1.W} {rT2.W}")
    eq = UP + [B(310, 300), B(305, 298), B(310, 299, atr=4.0), B(305, 296), B(300, 291), B(298, 280)]
    rQ = Run().feed4(eq)
    check("LP-G5 a high equal to another high in its window is not a major high (strict): 310 twice -> no candidate, no adoption "
          "although the fall to 280 is 30 >= 20", rQ.W.dir == 1 and rQ.S.cHi is None and rQ.S.nAdopt == 1, str(rQ.S.cHi))
    # H) unadopted candidate: not shown, the confirmed wave stays
    check("LP-H while a candidate exists but is not adopted (LP-E), the latest wave stays the confirmed up wave 50 -> 310 "
          "(nothing replaced; the drawing never reads candidates, LS-08)",
          (rE.W.dir, rE.W.O, rE.W.E) == (1, 50, 310) and rE.S.cHi is not None and not rE.S.cHi.adopted, str(rE.W))
    # I / J) switch-end below 100 % in its real bin; nothing retroactive
    seqI = BASE + fill(60, 90, 50) + [B(60, 20, atr=4.0), B(100, 30), B(400, 200), B(350, 250)]
    rI = Run().feed4(seqI)
    rc = rI.recs()
    k0 = len(seqI) - 4
    check("LP-I down wave 1000 -> 0 observed up to 40 % when the major low 20 (+380 >= 20) adopts the up wave 20 -> 400: the "
          "live observation ends ONCE as switch-end in the [40,50) bin with the old denominator 1000 / 0 (not in > 100 %)",
          (rI.W.dir, rI.W.O, rI.W.E) == (1, 20, 400) and len(rc) == 1 and rc[0].outcome == 2 and rc[0].bin == 4
          and abs(rc[0].rMax - 0.4) < 1e-12 and rc[0].refO == 1000 and rc[0].refE == 0 and cnt(rI.S, -1, 11, 2) == 0
          and sum(rI.S.cnt) == 1 and rc[0].endAvail == av(k0 + 3), str(rc))
    rJ = Run().feed4(seqI + [B(380, 260), B(450, 300), B(440, 350)])
    rj = rJ.recs()
    check("LP-J the up wave was adopted with a retracement (250, 39 %) that happened before the adoption: no observation is "
          "created from it (not even after more bars inside it); after the next new high (450) a new observation starts "
          "after the adoption with the new end as its base",
          rI.S.nNoRetro == 1 and not rI.S.obsOn and len(rj) == 1 and rJ.S.obsOn and rJ.S.obsE == 450 and rJ.S.obsO == 20
          and rJ.S.obsStart == av(len(seqI) + 2) and rJ.S.obsStart > rc[0].endAvail, f"{rJ.S.obsE} {rJ.S.obsStart}")
    # K) holds with the new rule: every candidate evaluated, no one-sided adoption, the open is irrelevant
    ov = {"lfwPivL4": 2, "lfwPivR4": 1}
    k = base_run([B(300, 100), B(1100, -100), B(600, 200), B(500, 250), B(650, 300, atr=10.0), B(600, 100)], ov)
    hy = sorted((h.dir, h.O, h.E) for h in k.S.hyps) if k.S.hold else None
    check("LP-K1 on hold (down 1100 -> -100 / up -100 -> 1100), a confirmed major high 650 (+fall 550) is adopted only by the up "
          "candidate (the down candidate ignores a same-direction pivot): the two candidates still differ -> still on hold, "
          "nothing chosen", k.S.hold and hy == [(-1, 650, 100), (-1, 1100, -100)], str(hy))
    vs = [Run().feed4(up_with(B(310, 280, o=o, atr=4.0), [B(305, 295, o=o2), B(300, 291), B(298, 288)]))
          for o, o2 in ((309, 304), (281, 296), (295, 300))]
    check("LP-K2 moving only the opens changes nothing in an adoption", all(pine_tuple(v.S) == pine_tuple(vs[0].S) for v in vs))
    kb0 = base_run([B(300, 100), B(1100, -100), B(600, 200), B(500, 250), B(650, 300, atr=10.0), B(600, 100), B(1200, 150)], ov)
    kb = base_run([B(300, 100), B(1100, -100), B(600, 200), B(500, 250), B(650, 300, atr=10.0), B(600, 100), B(300, -150),
                   B(1200, 0)], ov)
    check("LP-K3 the hold is released only when every candidate gives the same wave: a bar above both origins right away still "
          "differs (up from -100 vs up from 100); after both ends become -150, a bar above both origins gives up -150 -> 1200",
          kb0.S.hold and not kb.S.hold and (kb.W.dir, kb.W.O, kb.W.E) == (1, -150, 1200), f"{hyps(kb0.S)} {kb.W}")


# ============================================================================
# hold (no intrabar-order assumption)
# ============================================================================
def hyps(S):
    return sorted((h.dir, h.O, h.oT, h.E, h.eT) for h in S.hyps)


def gate_hold():
    t4, t5 = tb(X(0)), tb(X(1))
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
    check("LH-03 hold released by a later bar breaking one side: below -100 -> down 1100 -> -150 (both candidates give it), "
          "available from the release bar (not the hold bar)",
          not rd.S.hold and (rd.W.dir, rd.W.O, rd.W.oT, rd.W.E) == (-1, 1100, t5, -150) and rd.W.oAvail == av(X(3))
          and rd.W.eAvail == av(X(3)), str(rd.W))
    check("LH-04 symmetric: above 1100 -> up -100 -> 1150", not ru.S.hold and (ru.W.dir, ru.W.O, ru.W.oT, ru.W.E) == (1, -100, t5, 1150),
          str(ru.W))
    m = Run().feed4(neg(BASE + [B(300, 100), B(1100, -100), B(600, 200), B(500, -150)]))
    check("LH-05 mirror of LH-01 / LH-03 (every price negated): hold, then above 100 -> up -1100 -> 150",
          m.S.nHold == 1 and not m.S.hold and (m.W.dir, m.W.O, m.W.E) == (1, -1100, 150), str(m.W))
    k = base_run([B(300, 100), B(1100, -100), B(1000, 500), B(400, -150)])
    check("LH-06 the candidates still disagree after the break (78 %+ rally inside: down candidate switches to origin 1000, up "
          "candidate reverses from 1100) -> still on hold, no wave chosen",
          k.S.hold and hyps(k.S) == [(-1, 1000, tb(X(2)), -150, tb(X(3))), (-1, 1100, t5, -150, tb(X(3)))], str(hyps(k.S)))
    k2 = Run().feed4(BASE + [B(300, 100), B(1100, -100), B(1000, 500), B(400, -150), B(1200, 0)])
    check("LH-07 ... until they agree: a bar above both origins reverses both -> up -150 -> 1200",
          not k2.S.hold and (k2.W.dir, k2.W.O, k2.W.E) == (1, -150, 1200), str(k2.W))
    c = base_run([B(300, 100), B(900, -10)])
    check("LH-08 a new low on the bar whose high would first create a switch candidate (90 %): order decides between extension "
          "(origin 1000) and switch (origin 900) -> hold, no candidate chosen; the observation closes as order unknown",
          c.S.hold and hyps(c.S) == [(-1, 900, t5, -10, t5), (-1, 1000, tb(IP2), -10, t5)] and len(c.recs()) == 1
          and c.recs()[0].outcome == 4, str(hyps(c.S)))
    c3 = base_run([B(300, 100), B(1000, -1)])
    check("LH-09 a new low on the bar that touches the origin: hold (the touched high may or may not precede the low)",
          c3.S.hold and len(c3.recs()) == 1 and c3.recs()[0].outcome == 4 and c3.recs()[0].rAlt == 1.0, str(hyps(c3.S)))
    seq = [B(300, 100), B(1100, -100), B(600, 0), B(500, -50), B(700, 100), B(500, -150), B(-120, -140), B(20, -145), B(0, -300)]
    rr = base_run(seq)
    rc = rr.recs()
    rel = av(X(5))
    during = [x for x in rc if av(X(1)) <= x.startAvail < rel]
    check("LH-10 hold -> release: only one record before the hold (order unknown); retracements during the hold (67 % / 96 % "
          "of the two candidates) make no observation; after the release a new observation starts from the release end (-150) "
          "only after the release (startAvail > release) and resumes once",
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
    check("LO-02 exactly 10 % starts an observation (fixed 1000 / 0); a later high of 15 % in the SAME bin on the resume bar -> "
          "resume, max = 10 % (the resume bar's own high is not used)",
          len(rc) == 1 and rec_t(rc[0]) == (-1, 0, 1, 0.1, None, 1000, 0, 1) and rc[0].startAvail == av(X(1)), str(rc))
    r = base_run([B(150, 50), B(250, -1)])
    rc = r.recs()
    check("LO-03 resume bar whose high would raise the bin (15 % -> 25 %): order unknown (bin of the certain 15 %, alt 25 %), "
          "not a resume; the wave still extends", len(rc) == 1 and rec_t(rc[0]) == (-1, 4, 1, 0.15, 0.25, 1000, 0, 1)
          and r.W.E == -1 and r.W.O == 1000 and cnt(r.S, -1, 1, 0) == 0 and cnt(r.S, -1, 1, 4) == 1, str(rc))
    r = base_run([B(1000, 500), B(900, 400), B(800, -5)])
    rc = r.recs()
    check("LO-04 exact touch of the origin (100 %): observation ends as full retracement (bin 100 %), no new observation for the "
          "same end; then the new low switches the wave from the touched high (origin 1000 at the touch bar), no resume recorded",
          len(rc) == 1 and rec_t(rc[0]) == (-1, 1, 10, 1.0, None, 1000, 0, 1) and r.W.O == 1000 and r.W.oT == tb(X(0))
          and r.W.E == -5 and r.S.nStartAmb == 0, str(rc) + str(r.W))
    r = base_run([B(999.5, 500)])
    check("LO-05 99.95 % is not a full retracement (observation still live)", r.S.obsOn and not r.recs(), str(r.S))
    r = base_run([B(300, 100), B(1000.5, 200)])
    rc = r.recs()
    check("LO-06 strict break of the origin: observation ends as switch-end in the > 100 % bin, not as full retracement",
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
    check("LO-11 a bar making a new low whose high reaches 10 % of the old wave: no observation (order unknown start, counted "
          "separately from the formal observations)", not r.recs() and r.S.nStartAmb == 1 and formal(r.S, -1) == 0, str(r.S))
    r = base_run([B(300, 100), B(350, 150), B(320, 120), B(400, 200)])
    check("LO-12 no expiry: the observation stays live while neither end nor origin is reached (max 40 %)",
          r.S.obsOn and abs((r.W.E - r.W.rx) / (r.W.E - r.W.O) - 0.4) < 1e-12 and not r.recs(), str(r.S))
    r = base_run([])
    q = Run({"lfwExclInit": False}).feed4(BASE)
    check("LO-13 observations of the first wave are excluded (counted separately) by default; included when the input is off "
          "(the first up wave's observation ended by the adopted down wave: switch-end); later adoptions are not first waves",
          not r.recs() and r.S.nExclInit == 1 and len(q.recs()) == 1 and q.S.nExclInit == 0 and q.recs()[0].outcome == 2
          and q.recs()[0].dir == 1 and not r.W.init, str(q.recs()))
    r = Run({"lfwStartRatio": 0.3}).feed4(BASE + [B(250, 100), B(299, 100)])
    s2 = Run({"lfwSwitchRatio": 0.5}).feed4(BASE + [B(500, 100), B(300, -1)])
    check("LO-14 the start ratio and the switch ratio are inputs (start 0.3: 29.9 % no observation; switch 0.5: 50 % + new low switches)",
          not r.S.obsOn and s2.W.O == 500, f"{r.S} {s2.W}")
    r = base_run([B(300, 100), B(250, 0)])
    check("LO-15 a low equal to the end (0) is not a new low: no resume, the observation stays live, end unchanged",
          r.S.obsOn and not r.recs() and r.W.E == 0 and r.W.eT == tb(ID3), str(r.W))
    r = base_run([B(300, 100), B(200, -100), B(10, -50), B(0, -200), B(400, -150)])
    check("LO-16 conservation and wave count: 2 ended + 1 live observation of the same wave = 3 formal observations, 1 observed "
          "wave (the same wave's retracements are not counted as separate waves)",
          formal(r.S, -1) == 3 and len(r.recs()) == 2 and live(r.S, -1) == 1 and r.S.nWaveObs[1] == 1 and r.S.nWaveObs[0] == 0,
          str(r.S.nWaveObs))


# ============================================================================
# reference model (written from the spec, independent of the Pine text)
# ============================================================================
# wave = (dir, init, O, oT, E, eT, ret, retT); ret = most retraced price since the end (down: highest high, up: lowest low)
# candidate = dict(k, p, t, atr, thr, ext, extT, ret, retT, used)
class Ref:
    def __init__(self, sw=0.782, st=0.10, excl=True, left=60, right=3, mult=5.0):
        self.sw, self.st, self.excl, self.left, self.right, self.mult = sw, st, excl, left, right, mult
        self.wave = None
        self.hold = None
        self.wid = 0
        self.obs = None
        self.done = False
        self.seq = 0
        self.win = []
        self.cand = {1: None, -1: None}
        self.recs, self.excl_n, self.start_amb, self.n_hold, self.n_noretro, self.n_adopt = [], 0, 0, 0, 0, 0
        self.broken = 0
        self.wave_obs = {1: 0, -1: 0}

    # ---- candidates
    @staticmethod
    def cand_step(c, h, l, t):
        """False when the candidate is exceeded (no longer the major extreme)."""
        if c["k"] == 1:
            if h > c["p"]:
                return False
            if c["ext"] is None or l < c["ext"]:
                c.update(ext=l, extT=t, ret=None, retT=None)
            elif c["ret"] is None or h > c["ret"]:
                c.update(ret=h, retT=t)
        else:
            if l < c["p"]:
                return False
            if c["ext"] is None or h > c["ext"]:
                c.update(ext=h, extT=t, ret=None, retT=None)
            elif c["ret"] is None or l < c["ret"]:
                c.update(ret=l, retT=t)
        return True

    def cands(self, h, l, t, atr):
        for k in (1, -1):
            c = self.cand[k]
            if c is not None and not self.cand_step(c, h, l, t):
                self.cand[k] = None
                self.broken += 1
        self.win.append((h, l, t, atr))
        n = self.left + self.right + 1
        self.win = self.win[-n:]
        if len(self.win) < n:
            return
        mid = self.win[self.left]
        others = self.win[:self.left] + self.win[self.left + 1:]
        a = mid[3]
        if a is None or a <= 0:
            return
        for k, is_piv in ((1, all(o[0] < mid[0] for o in others)), (-1, all(o[1] > mid[1] for o in others))):
            if is_piv:
                c = dict(k=k, p=mid[0] if k == 1 else mid[1], t=mid[2], atr=a, thr=a * self.mult, ext=None, extT=None,
                         ret=None, retT=None, used=False)
                for o in self.win[self.left + 1:]:
                    self.cand_step(c, o[0], o[1], o[2])
                self.cand[k] = c

    def usable(self, k):
        c = self.cand[k]
        return c is not None and not c["used"] and c["ext"] is not None and abs(c["p"] - c["ext"]) >= c["thr"]

    def from_cand(self, k, init):
        c = self.cand[k]
        return (-k, init, c["p"], c["t"], c["ext"], c["extT"], c["ret"], c["retT"])

    def adoption(self, w):
        if w is None:
            uh, ul = self.usable(1), self.usable(-1)
            if uh and ul:
                th, tl = self.cand[1]["t"], self.cand[-1]["t"]
                return self.from_cand(1, True) if th > tl else self.from_cand(-1, True) if tl > th else None
            return self.from_cand(1, True) if uh else self.from_cand(-1, True) if ul else None
        k = 1 if w[0] == 1 else -1          # an up wave looks for a major high, a down wave for a major low
        if self.usable(k) and self.cand[k]["t"] > w[3]:
            return self.from_cand(k, False)
        return None

    def mark(self, w):
        k = 1 if w[0] == -1 else -1
        c = self.cand[k]
        if c is not None and c["t"] == w[3] and c["p"] == w[2]:
            c["used"] = True

    # ---- waves
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
        a = self.adoption(w)
        if a is not None:
            return [a]
        res = []
        for first, second in ((h, l), (l, h)):
            x, ch = self.point(w, first, t, False)
            x, _ = self.point(x, second, t, ch)
            if x not in res:
                res.append(x)
        return res

    # ---- observations
    @staticmethod
    def bin(r):
        if r > 1:
            return 11
        if r >= 1:
            return 10
        return max(0, min(9, int((r * 10.0 + 1e-9) // 1)))

    def close(self, outcome, r, alt, av_):
        o = self.obs
        if o["init"]:
            self.excl_n += 1
        else:
            self.recs.append((o["dir"], self.wid, o["seq"], o["O"], o["E"], o["start"], av_, outcome, r, alt, self.bin(r)))
        self.obs = None

    def open(self, av_):
        self.seq += 1
        w = self.wave
        self.obs = dict(dir=w[0], O=w[2], E=w[4], seq=self.seq, init=w[1] and self.excl, start=av_)
        if not self.obs["init"] and self.seq == 1:
            self.wave_obs[w[0]] += 1

    def new_wave(self, w):
        self.wave = w
        self.wid += 1
        self.obs, self.done, self.seq = None, False, 0

    def no_retro(self):
        w = self.wave
        if w[6] is not None and self.rt(w, w[6]) >= self.st:
            self.done = True
            self.n_noretro += 1

    def bar(self, h, l, t, atr, av_):
        self.cands(h, l, t, atr)
        if self.hold is not None:
            nxt = []
            for c in self.hold:
                for x in self.outcomes(c, h, l, t):
                    if x not in nxt:
                        nxt.append(x)
            if len(nxt) == 1:
                self.hold = None
                self.new_wave(nxt[0])
                self.mark(nxt[0])
                self.no_retro()
            elif len(nxt) > 16:
                raise AssertionError("more than 16 candidates")
            else:
                self.hold = nxt
            return
        if self.wave is None:
            a = self.adoption(None)
            if a is not None:
                self.new_wave(a)
                self.mark(a)
                self.n_adopt += 1
                self.no_retro()
            return
        w = self.wave
        d, _, O, oT, E, _, ret, _ = w
        rp, ep = (h, l) if d == -1 else (l, h)
        new_end = ep < E if d == -1 else ep > E
        brk = rp > O if d == -1 else rp < O
        r_prior = 0.0 if ret is None else self.rt(w, ret)
        r_bar = self.rt(w, rp)
        adopted = self.adoption(w)
        outs = [adopted] if adopted is not None else self.outcomes(w, h, l, t)
        if len(outs) > 1:
            if self.obs:
                self.close(4, r_prior, r_bar, av_)
            self.hold = outs
            self.n_hold += 1
            return
        nw = outs[0]
        if new_end:
            if self.obs:
                if r_bar > r_prior and (r_bar >= 1 or self.bin(r_bar) != self.bin(r_prior)):
                    self.close(4, r_prior, r_bar, av_)
                else:
                    self.close(0, r_prior, None, av_)
            elif not self.done and r_bar >= self.st:
                self.start_amb += 1
            self.done = False
        elif brk:
            if not self.obs and not self.done:
                self.open(av_)
            if self.obs:
                self.close(2, r_bar, None, av_)
        else:
            r_now = r_bar if ret is None else max(r_prior, r_bar)
            if not self.obs and not self.done and r_now >= self.st:
                self.open(av_)
            if self.obs and rp == O:
                self.close(1, 1.0, None, av_)
                self.done = True
            if self.obs and adopted is not None:
                self.close(2, r_now, None, av_)
        if (nw[0], nw[2], nw[3]) != (d, O, oT):
            self.new_wave(nw)
        else:
            self.wave = nw
        if adopted is not None:
            self.mark(adopted)
            self.n_adopt += 1
            self.no_retro()


def wtuple(w):
    return (w.dir, w.init, w.O, w.oT, w.E, w.eT, w.rx, w.rxT) if w.dir != 0 else None


def ctuple(c):
    return None if c is None else (c.p, c.t, c.atr, c.thr, c.ext, c.extT, c.rx, c.rxT, c.adopted)


def rctuple(c):
    return None if c is None else (c["p"], c["t"], c["atr"], c["thr"], c["ext"], c["extT"], c["ret"], c["retT"], c["used"])


def pine_tuple(S):
    recs = [(r.dir, r.waveId, r.seq, r.refO, r.refE, r.startAvail, r.endAvail, r.outcome, r.rMax, r.rAlt, r.bin) for r in S.recs]
    return (None if S.hold else wtuple(S.w), sorted(wtuple(h) for h in S.hyps) if S.hold else None, S.waveId, recs,
            S.nExclInit, S.nStartAmb, S.nHold, S.nNoRetro, S.nAdopt, S.nCandBroken, list(S.nWaveObs), ctuple(S.cHi), ctuple(S.cLo),
            S.obsOn, S.obsO if S.obsOn else None, S.obsE if S.obsOn else None)


def ref_tuple(R):
    return (None if R.hold is not None else R.wave, sorted(R.hold) if R.hold is not None else None, R.wid, R.recs,
            R.excl_n, R.start_amb, R.n_hold, R.n_noretro, R.n_adopt, R.broken, [R.wave_obs[1], R.wave_obs[-1]],
            rctuple(R.cand[1]), rctuple(R.cand[-1]),
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
        if rng.random() < 0.004 and len(out) > 5:     # occasional huge outside bar (both ends of the wave in one bar)
            k = rng.randint(5, min(200, len(out)))
            h = max(x["h"] for x in out[-k:]) + rng.uniform(0, 20) * scale
            l = min(x["l"] for x in out[-k:]) - rng.uniform(0, 20) * scale
        h = max(h, o)
        out.append(dict(h=h, l=min(l, o), o=o, atr=None if i < 14 else round(atr, 6)))
        atr = atr * 13 / 14 + (h - l) / 14
        p = c
    return out


def run_ref(bars, **kw):
    R = Ref(**kw)
    for i, b in enumerate(bars):
        R.bar(b["h"], b["l"], tb(i), b.get("atr", BIG), av(i))
    return R


SETS = [({}, {}),
        ({"lfwSwitchRatio": 0.5, "lfwStartRatio": 0.2}, {"sw": 0.5, "st": 0.2}),
        ({"lfwExclInit": False}, {"excl": False}),
        ({"lfwPivL4": 5, "lfwPivR4": 2, "lfwPivM4": 3.0}, {"left": 5, "right": 2, "mult": 3.0}),
        ({"lfwPivL4": 12, "lfwPivR4": 1, "lfwPivM4": 8.0}, {"left": 12, "right": 1, "mult": 8.0})]


def gate_random():
    bad = []
    n_rec = n_hold = n_adopt = 0
    kinds = set()
    for seed in range(8):
        for ov, kw in SETS:
            bars = rand_series(seed, scale=1.0 + seed % 3)
            P = Run(dict(ov, lfwMaxRecs=100000)).feed4(bars).S
            R = run_ref(bars, **kw)
            if pine_tuple(P) != ref_tuple(R):
                bad.append((seed, kw))
            n_rec += len(R.recs)
            n_hold += R.n_hold
            n_adopt += R.n_adopt
            kinds |= {x[7] for x in R.recs}
    sub100 = 0
    for seed in range(8):
        R = run_ref(rand_series(seed, scale=1.0 + seed % 3), left=5, right=2, mult=3.0)
        sub100 += sum(1 for x in R.recs if x[7] == 2 and x[10] < 10)
    check(f"LR-01 translated Pine == independent reference model on {8 * len(SETS)} random HTF series x settings ({n_rec} "
          f"observations, outcomes {sorted(kinds)}, {n_hold} holds, {n_adopt} adoptions, {sub100} switch-ends below 100 %): "
          "waves, hold candidates, major-high / low candidates, records, counters",
          not bad and kinds == {0, 1, 2, 4} and n_hold > 20 and n_adopt > 100 and sub100 > 10, str(bad))
    bad = []
    for seed in range(6):
        for ov in ({}, {"lfwPivL4": 5, "lfwPivR4": 2, "lfwPivM4": 3.0}):
            bars = rand_series(100 + seed)
            mir = [dict(h=-b["l"], l=-b["h"], o=-b["o"], atr=b["atr"]) for b in bars]
            A = Run(dict(ov, lfwMaxRecs=100000)).feed4(bars).S
            M = Run(dict(ov, lfwMaxRecs=100000)).feed4(mir).S
            ra = [(r.dir, r.outcome, r.bin, r.refO, r.refE, r.seq, r.startAvail) for r in A.recs]
            rm = [(-r.dir, r.outcome, r.bin, -r.refO, -r.refE, r.seq, r.startAvail) for r in M.recs]
            ha = sorted((h.dir, h.O, h.E) for h in A.hyps) if A.hold else None
            hm = sorted((-h.dir, -h.O, -h.E) for h in M.hyps) if M.hold else None
            if not (A.hold == M.hold and ha == hm and A.w.dir == -M.w.dir and A.w.O == -M.w.O and A.w.E == -M.w.E and ra == rm
                    and A.nHold == M.nHold and A.nAdopt == M.nAdopt):
                bad.append((seed, ov))
    check("LR-02 up / down symmetry (including major highs / lows, holds and their release): negating every price swaps the "
          "directions and gives the same observations, adoptions, holds and waves", not bad, str(bad))
    bad = []
    for seed in range(6):
        S = Run({"lfwMaxRecs": 100000, "lfwPivL4": 5, "lfwPivR4": 2, "lfwPivM4": 3.0}).feed4(rand_series(200 + seed)).S
        for d in (1, -1):
            for b in range(12):
                for o in range(5):
                    want = sum(1 for r in S.recs if r.dir == d and r.bin == b and r.outcome == o)
                    if cnt(S, d, b, o) != want:
                        bad.append((seed, d, b, o))
            if formal(S, d) != sum(1 for r in S.recs if r.dir == d) + live(S, d):
                bad.append((seed, d, "conservation"))
            if S.nWaveObs[0 if d == 1 else 1] != len({r.waveId for r in S.recs if r.dir == d} |
                                                      ({S.waveId} if live(S, d) else set())):
                bad.append((seed, d, "waves"))
        if any(r.bin == 0 for r in S.recs) or any(r.outcome == 3 for r in S.recs):
            bad.append((seed, "bin 0 / live recorded"))
        if any(r.outcome == 0 and not (0.1 <= r.rMax < 1) for r in S.recs) or any(r.outcome == 1 and r.bin != 10 for r in S.recs):
            bad.append((seed, "range"))
        if any(r.endAvail < r.startAvail for r in S.recs):
            bad.append((seed, "time"))
    check("LR-03 counters (time frame x direction x 10 % bin x outcome) == the observation records; formal = ended + live; observed "
          "waves = distinct wave ids with an observation; no formal observation in [0,10); full only at 100 %; no record ends "
          "before it starts", not bad, str(bad[:5]))
    S = Run({"lfwMaxRecs": 10}).feed4(rand_series(7)).S
    check("LR-04 the record list is capped by the input, the counters are not", len(S.recs) == 10 and sum(S.cnt) > 10, str(sum(S.cnt)))
    bad = []
    for seed in range(8):
        bars = rand_series(300 + seed)
        r = Run({"lfwMaxRecs": 100000, "lfwPivL4": 5, "lfwPivR4": 2, "lfwPivM4": 3.0})
        spans, cur, maxc, adopts = [], None, 0, []
        prev_adopt = 0
        for i, b in enumerate(bars):
            r.exec(av(i), h4=(b["h"], b["l"], tb(i), b["atr"]))
            S = r.S
            if S.nAdopt != prev_adopt:
                adopts.append(av(i))
                prev_adopt = S.nAdopt
                if not S.hold and S.w.dir != 0 and S.obsOn:
                    bad.append((seed, i, "observation live on the adoption bar"))
            if S.hold:
                maxc = max(maxc, len(S.hyps))
                if S.obsOn:
                    bad.append((seed, i, "live obs in hold"))
                if cur is None:
                    cur = av(i)
            elif cur is not None:
                spans.append((cur, av(i)))
                cur = None
        for x in r.S.recs:
            if any(a < x.startAvail <= b for a, b in spans):
                bad.append((seed, "start inside hold"))
            if x.startAvail in adopts and x.endAvail > x.startAvail:
                bad.append((seed, "observation started on an adoption bar and kept after it"))
        if maxc > 16 or r.S.nReinit:
            bad.append((seed, "candidates", maxc))
    if r.S.obsOn and r.S.obsStart in adopts:
        bad.append(("live observation started on an adoption bar",))
    check("LR-05 random series with holds and adoptions: no observation live during a hold or right after an adoption, none "
          "started inside a hold, none started on an adoption bar and kept beyond it (an old-wave observation may start and end "
          "on that bar), candidates stay <= 16, no re-initialisation", not bad, str(bad[:5]))
    rd = Run({"lfwMaxRecs": 100000}).feedD(rand_series(5)[:400])
    check("LR-06 the daily state is independent (D bars only touch lfwD; 4H stays empty)",
          rd.env["lfw4"].nBars == 0 and rd.env["lfwD"].nBars == 400 and rd.env["lfwD"].pL == 20, str(rd.env["lfwD"].nBars))


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
    ("start >= -> >", "if not S.obsOn and not S.obsDone and rNow >= lfwStartRatio", "if not S.obsOn and not S.obsDone and rNow > lfwStartRatio"),
    ("touch = 99.9 %", "                if S.obsOn and T\n", "                if S.obsOn and rBar >= 0.999\n"),
    ("origin break >=", "    else if s * (w.O - p) > 0\n", "    else if s * (w.O - p) >= 0\n"),
    ("resume uses bar high", "lfwRecord(S, 0, rPrior, na, availT)", "lfwRecord(S, 0, math.max(rPrior, rBar), na, availT)"),
    ("switch origin = old origin", "            w.O := w.rx\n            w.oT := w.rxT\n", "            w.O := w.O\n            w.oT := w.oT\n"),
    ("unknown on any higher high", "lfwBin(rBar) != lfwBin(rPrior))", "rBar != rPrior)"),
    ("order assumed (high first)", "    if not lfwSame(a, b)\n        array.push(out, b)\n", "    if false\n        array.push(out, b)\n"),
    ("retracement after an end change used", "    lfwPoint(a, l, t, availT, ca)\n", "    lfwPoint(a, l, t, availT, false)\n"),
    ("init not excluded", "S.obsInit := S.w.init and lfwExclInit", "S.obsInit := false"),
    ("full keeps observing", "                    S.obsDone := true\n", "                    S.obsDone := false\n"),
    ("hold entry not recorded", "            if S.obsOn\n                lfwRecord(S, 4, rPrior, rBar, availT)\n            S.hold := true\n",
     "            S.hold := true\n"),
    ("release on any candidate", "    if array.size(nxt) == 1\n", "    if array.size(nxt) >= 1\n"),
    ("release keeps hold-bar availability", "        nw.oAvail := availT\n", ""),
    ("reversal origin = bar", "        w.O := w.E\n        w.oT := w.eT\n", "        w.O := p\n        w.oT := t\n"),
    ("seq not reset", "    S.obsSeq := 0\n", ""),
    # major highs / lows
    ("no adoption", "        LfwWave aw = lfwAdopt(S, w, availT)\n", "        LfwWave aw = na\n"),
    ("same-direction adoption", "    if w.dir == 1\n        if lfwCandOk(S.cHi)\n            if S.cHi.t > w.oT\n                res := lfwCandWave(S.cHi, false, availT)",
     "    if w.dir == 1\n        if lfwCandOk(S.cLo)\n            if S.cLo.t > w.oT\n                res := lfwCandWave(S.cLo, false, availT)"),
    ("one right bar fewer", "        int c = S.pL\n", "        int c = S.pL + 1\n"),
    ("ATR of the newest bar", "        float a = array.get(S.bA, c)\n", "        float a = array.get(S.bA, n - 1)\n"),
    ("pivot equal allowed", "                if array.get(S.bH, i) >= ph\n", "                if array.get(S.bH, i) > ph\n"),
    ("own wick used", "    for i = c + 1 to array.size(S.bH) - 1\n", "    for i = c to array.size(S.bH) - 1\n"),
    ("no invalidation", "        if h > c.p\n            ok := false\n", "        if false\n            ok := false\n"),
    ("older than origin allowed", "            if S.cHi.t > w.oT\n", "            if true\n"),
    ("adopted flag ignored", "        if not c.adopted and not na(c.ext)\n", "        if not na(c.ext)\n"),
    ("tie picks the high", "            if S.cHi.t > S.cLo.t\n", "            if S.cHi.t >= S.cLo.t\n"),
    ("switch-end forced to > 100 %", "    int b = lfwBin(r)\n", "    int b = outcome == 2 ? 11 : lfwBin(r)\n"),
    ("adoption leaves the observation live", "                if S.obsOn and not na(aw)\n                    lfwRecord(S, 2, rNow, na, availT)\n", ""),
    ("retroactive observation", "            S.obsDone := true\n            S.nNoRetro := S.nNoRetro + 1\n",
     "            S.obsDone := false\n            S.nNoRetro := S.nNoRetro + 1\n"),
    ("threshold > instead of >=", "            ok := math.abs(c.p - c.ext) >= c.thr\n", "            ok := math.abs(c.p - c.ext) > c.thr\n"),
    ("hold ignores adoption", "    LfwWave a = lfwAdopt(S, w, availT)\n    if not na(a)\n        array.push(out, a)\n    else\n        lfwBarStep(w, h, l, t, availT, out)\n",
     "    lfwBarStep(w, h, l, t, availT, out)\n"),
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
            for g in (gate_waves, gate_major, gate_hold, gate_obs):
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
    check(f"LM-01 every one of {len(MUTATIONS)} mutations of the Pine logic makes at least one LW / LP / LH / LO check fail",
          caught == len(MUTATIONS) and not missed, str(missed))


def main():
    only = sys.argv[1:]
    gates = (gate_static, gate_waves, gate_major, gate_hold, gate_obs, gate_random, gate_chart, gate_mutation)
    for g in gates:
        if only and g.__name__ not in only:
            continue
        try:
            g()
        except Exception:      # noqa: BLE001
            import traceback
            check(f"{g.__name__} completed without error", False, traceback.format_exc()[-1500:])
    w = max(len(n) for n, _, _ in RESULTS)
    fails = 0
    for n, ok, d in RESULTS:
        fails += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {n.ljust(w)[:170]}  {'' if ok else d[:700]}")
    print(f"\n{len(RESULTS) - fails}/{len(RESULTS)} passed  [PINE_NOT_VERIFIED: static / translated Pine logic]")
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
