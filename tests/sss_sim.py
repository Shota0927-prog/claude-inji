"""SSS-1 checks — SatsShortSignal.pine (15S SATS short-timing detector).

1. f_satBand() in SatsShortSignal.pine is byte-identical to tests/sats_src/f_satBand.txt (the SAT BAND Reconstruction Test source).
2. f_evt() and the realtime isnew sequencing block (15s -> 30s -> 1m, wait window, pair update, reset, expiry, skip when the
   requested 30s/1m value has not switched yet) are mirrored here line by line and run against the cases of the instruction's
   section 5 table.

Each simulated step is ONE first update (barstate.isrealtime and barstate.isnew) of a 15s chart bar. The per-timeframe input is
what the Pine tuple delivers on that update: (time, open, l1, l2, stb, d1, d2, sd, st, l1[1], l2[1], stb[1], d1[1], d2[1], sd[1], st[1]).
Later updates inside the bar never re-evaluate (they cannot change a recorded event), so they are not modelled.

Evidence class: PINE_NOT_VERIFIED (TradingView compiler, request.security realtime delivery, varip rollback and drawing not run).
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S = 15_000
M = 60_000


def f_evt(o, l1, l2, sb, d1, d2, sd, st, l1p, l2p, sbp, d1p, d2p, sdp, stp):
    m = 0
    ok = None not in (o, l1, l2, sb, l1p, l2p, sbp, st, stp)
    if ok and stp == 1 and st == 0:
        if d1p == 1 and d1 == -1 and l1 > o:
            m += 1
        if d2p == 1 and d2 == -1 and l2 > o:
            m += 2
        if sdp == 1 and sd == -1 and sb > o:
            m += 4
    return m


class Det:
    def __init__(self, wait_min=5):
        self.waitMs = wait_min * M
        self.w15T = self.p15T = self.p30T = None
        self.signals = []
        self.events = []

    def step(self, now, d15, d30, d60):
        """d* = delivered tuple (time first) or None (no data)."""
        if self.w15T is not None and now - self.w15T > self.waitMs:
            self.w15T = None
        if self.p15T is not None and now - self.p15T > self.waitMs:
            self.p15T = self.p30T = None
        m15 = f_evt(*d15[1:]) if d15 and d15[0] == now else 0
        if m15:
            self.w15T = now
            self.events.append(("15s", now, m15))
        m30 = f_evt(*d30[1:]) if d30 and d30[0] == now else 0
        if m30:
            self.events.append(("30s", now, m30))
            if self.w15T is not None and self.w15T <= now and now - self.w15T <= self.waitMs:
                self.p15T, self.p30T = self.w15T, now
        m60 = f_evt(*d60[1:]) if d60 and d60[0] == now else 0
        if m60:
            self.events.append(("1m", now, m60))
            if self.p15T is not None and self.p15T <= self.p30T <= now and now - self.p15T <= self.waitMs:
                self.signals.append((now, self.p15T, self.p30T))
                self.w15T = self.p15T = self.p30T = None


# ---- tuple builders --------------------------------------------------------------------------------------------------------
O = 100.0


def tup(t, *, st=0, stp=1, flips=("L2",), above=None, o=O):
    """flips: lines that go +1 -> -1 at this update. above: lines whose price is > open (default = flips)."""
    above = flips if above is None else above
    d = {}
    for n in ("L1", "L2", "STB"):
        dp = 1
        dn = -1 if n in flips else 1
        price = o + 1 if n in above else o - 1
        d[n] = (price, dn, dp)
    return (t, o, d["L1"][0], d["L2"][0], d["STB"][0], d["L1"][1], d["L2"][1], d["STB"][1], st,
            o - 2, o - 2, o - 2, d["L1"][2], d["L2"][2], d["STB"][2], stp)


NOEVT = lambda t: tup(t, flips=())   # noqa: E731


def run(seq, wait_min=5):
    """seq: {time: {"15": tuple|None, "30": ..., "60": ...}} over consecutive 15s bars."""
    det = Det(wait_min)
    ts = sorted(seq)
    for now in range(ts[0], ts[-1] + S, S):
        e = seq.get(now, {})
        last30 = now - now % (30_000)
        last60 = now - now % M
        d15 = e.get("15", NOEVT(now))
        d30 = e.get("30", NOEVT(last30))
        d60 = e.get("60", NOEVT(last60))
        det.step(now, d15, d30, d60)
    return det


RESULTS = []


def check(name, cond):
    RESULTS.append((name, cond))
    print(("PASS " if cond else "FAIL ") + name)


def main():
    src = open(os.path.join(ROOT, "tests", "sats_src", "f_satBand.txt"), encoding="utf-8").read()
    pine = open(os.path.join(ROOT, "SatsShortSignal.pine"), encoding="utf-8").read()
    check("f_satBand() byte-identical to the SAT BAND Reconstruction Test source", src in pine)

    # --- single-timeframe event conditions -------------------------------------------------------------------------------
    check("prev blue, new no-band, only LINE2 blue->red and above open -> event", f_evt(*tup(0, flips=("L2",))[1:]) == 2)
    check("LINE2 blue->red but only another line above open -> no event",
          f_evt(*tup(0, flips=("L2",), above=("L1", "STB"))[1:]) == 0)
    check("only STB blue->red and above open -> event", f_evt(*tup(0, flips=("STB",))[1:]) == 4)
    check("new bar starts red band (-1) -> no event", f_evt(*tup(0, st=-1)[1:]) == 0)
    check("prev bar not blue -> no event", f_evt(*tup(0, stp=0)[1:]) == 0)
    t = list(tup(0)[1:])
    t[2] = t[0]  # LINE2 price == open
    check("line price == open -> no event", f_evt(*t) == 0)
    t = list(tup(0)[1:])
    t[10] = None  # line2[1] na
    check("previous bar line na -> no event", f_evt(*t) == 0)
    check("several lines at once -> one event (mask)", f_evt(*tup(0, flips=("L1", "L2", "STB"))[1:]) == 7)
    # mid-bar flips are never evaluated: only the first update counts (an update after the first is not fed to step()).

    T0 = 10 * M
    # --- same start time for all three ------------------------------------------------------------------------------------
    d = run({T0: {"15": tup(T0), "30": tup(T0), "60": tup(T0)}})
    check("15s/30s/1m at the same start time -> one signal on that update", d.signals == [(T0, T0, T0)])

    # --- 30s before 15s, no later 30s -------------------------------------------------------------------------------------
    d = run({T0: {"30": tup(T0)}, T0 + S: {"15": tup(T0 + S)}, T0 + M: {"60": tup(T0 + M)}})
    check("30s before 15s, no new 30s -> no signal", d.signals == [])

    # --- exactly 5 minutes ------------------------------------------------------------------------------------------------
    t15, t30, t60 = T0, T0 + 2 * M, T0 + 5 * M
    d = run({t15: {"15": tup(t15)}, t30: {"30": tup(t30)}, t60: {"60": tup(t60)}})
    check("1m start exactly 5 min after 15s (30s in between) -> signal", d.signals == [(t60, t15, t30)])
    t15 = T0 + S
    t60 = T0 + 6 * M  # 5m45s
    d = run({t15: {"15": tup(t15)}, t30: {"30": tup(t30)}, t60: {"60": tup(t60)}})
    check("1m start beyond the window -> no signal", d.signals == [])
    d = run({t15: {"15": tup(t15)}, t30: {"30": tup(t30)}, T0 + 6 * M: {"60": tup(T0 + 6 * M)}}, wait_min=6)
    check("same, with wait 6 min -> signal", len(d.signals) == 1)

    # --- line goes back to blue after the 15s event: history still valid ---------------------------------------------------
    seq = {T0: {"15": tup(T0)}, T0 + 30_000: {"30": tup(T0 + 30_000)}, T0 + 2 * M: {"60": tup(T0 + 2 * M)}}
    for k in range(1, 8):  # intermediate 15s bars where all lines are blue again / band relit: no new events
        tt = T0 + k * S
        if tt not in seq:
            seq[tt] = {"15": tup(tt, st=1, stp=1, flips=())}
    d = run(seq)
    check("red line returning to blue after the event keeps the recorded event -> signal", d.signals == [(T0 + 2 * M, T0, T0 + 30_000)])

    # --- pair keeps its start when a newer 15s comes; a new 30s with a valid 15s updates it --------------------------------
    a, b, c = T0, T0 + 30_000, T0 + M + S
    d = run({a: {"15": tup(a)}, b: {"30": tup(b)}, c: {"15": tup(c)}, T0 + 5 * M + M: {"60": tup(T0 + 6 * M)}})
    check("newer 15s after the pair does not move the pair's start/deadline (expires)", d.signals == [])
    c30 = T0 + 2 * M
    d = run({a: {"15": tup(a)}, b: {"30": tup(b)}, c: {"15": tup(c)}, c30: {"30": tup(c30)}, T0 + 6 * M: {"60": tup(T0 + 6 * M)}})
    check("new 30s with a newer valid 15s updates the pair -> signal", d.signals == [(T0 + 6 * M, c, c30)])
    d = run({a: {"15": tup(a)}, b: {"30": tup(b)}, T0 + 2 * M: {"30": tup(T0 + 2 * M)}, T0 + 3 * M: {"60": tup(T0 + 3 * M)}})
    check("new 30s with the same 15s still pairs (15s still valid) -> signal", d.signals == [(T0 + 3 * M, a, T0 + 2 * M)])

    # --- reset after a signal --------------------------------------------------------------------------------------------
    d = run({a: {"15": tup(a)}, b: {"30": tup(b)}, T0 + M: {"60": tup(T0 + M)}, T0 + 2 * M: {"60": tup(T0 + 2 * M)}})
    check("after a signal, the next 1m needs new 15s/30s -> one signal only", len(d.signals) == 1)

    # --- requested value not switched yet on the first update -> that start event is skipped -------------------------------
    d = run({a: {"15": tup(a)}, b: {"30": tup(b - 30_000)}, T0 + M: {"60": tup(T0 + M)}})
    check("30s value not yet switched on the first update -> 30s start skipped -> no signal", d.signals == [])

    # --- the attached-chart case: 15s + 30s first, signal on the first update of the bar after the arrowed 1m bar ----------
    arrow = T0 + 3 * M
    d = run({T0 + M + S: {"15": tup(T0 + M + S)}, T0 + 2 * M: {"30": tup(T0 + 2 * M)}, arrow + M: {"60": tup(arrow + M)}})
    check("15s/30s first, 1m event at the start of the bar right of the arrowed 1m bar -> signal there",
          d.signals == [(arrow + M, T0 + M + S, T0 + 2 * M)])

    bad = [n for n, ok in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(bad)}/{len(RESULTS)} passed")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
