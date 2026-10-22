"""XA-7 fixtures — ZoneStrategyXAU Entry Timing = SATS Pullback (Entry C prepared, SATS line pullback entry).

  XW : static on the delivered Strategy — == xa_build.build_strategy(); strip_strategy7 gives 0c6cd71 byte for byte; the
       Current path keeps the previous code (the new branches are `if stSats` / `if fillNow and stSats` with the previous
       bodies byte-identical under `else if`); f_satBand == the SATS source function (tests/sats_src/f_satBand.txt) byte for
       byte and is called once at global scope (every bar; no request / colour / band state in the entry logic); inputs
       (Current default, 240 min, Entry C only with runtime.error); the waiting code (t-1 lines and previous close, cancel
       before the rebound, contact + close-back, qty f_stQty(close, SL0), TP0 at the fill, no TP recomputation); Engine,
       Visual, other Pine files, requests, f_stQty / f_stTp, strategy(), Role Reversal default unchanged
  XP : models — a Python port of f_satBand (VWMA / RMA ATR / Donchian) and of the waiting state machine: every-bar vs
       wait-only computation differs (so the global call matters); colour / band independence; nearest-line choice, ties,
       na, none; no order on the prep bar; t-1 lines only; Long / Short symmetric rebound and price windows; cancel priority
       (SL0 / Track / eligibility / expiry); 240-minute boundary by wall clock across gaps; duplicate signals do not extend;
       fixed SL0 / TP0; actual RR on a gap; used Track only on the fill; session; single wait / no double order
  XQ : mutations of the mirror and of the source

Evidence class: PINE_NOT_VERIFIED (TradingView compile, SATS line values vs the source indicator, Strategy Tester external).
"""
import math
import os
import random
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xa_build as xb            # noqa: E402
import eu_sim as es              # noqa: E402

ROOT = xb.ROOT
B = "0c6cd71"
rd = lambda p: open(os.path.join(ROOT, p), encoding="utf-8").read()
git = lambda *a: subprocess.run(["git", "-C", ROOT] + list(a), capture_output=True, text=True).stdout
code_only, input_decls, input_values, func, seg = es.code_only, es.input_decls, es.input_values, es.func, es.seg
S, S0 = rd(xb.STR_PATH), xb.show(B, xb.STR_PATH)
SRC = rd("tests/sats_src/f_satBand.txt")
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


def block(t, start, end):
    i = t.index(start)
    return t[i:t.index(end, i)]


def gate_static():
    check("XW-01 Strategy == xa_build.build_strategy() (XA-1 .. XA-7); strip_strategy7 gives 0c6cd71 byte for byte; the Engine and "
          "the Visual are byte-identical to 0c6cd71 (no Library re-publish)",
          xb.build_strategy() == S and xb.strip_strategy7(S) == S0 and xb.build_strategy6() == S0
          and rd(xb.ENG_PATH) == xb.show(B, xb.ENG_PATH) and rd(xb.VIS_PATH) == xb.show(B, xb.VIS_PATH)
          and {k for k, _, _ in xb.STRATEGY_EDITS7} == {"header", "input", "sats"})
    fill_old = block(S0, "    if fillNow\n", "    // (2c)")
    fill_new = block(S, "    else if fillNow\n", "    // (2c)")
    ord_old = block(S0, "            if not skipRef and not na(pQty)\n", "    stPrev := cur")
    ord_new = block(S, "            else if not skipRef and not na(pQty)\n", "    stPrev := cur")
    check("XW-02 Current keeps the previous order path: the fill-confirmation TP block and the Entry order block are byte-identical "
          "under `else if` of the new `if fillNow and stSats` / `if stSats` branches; stSats = (Entry Timing == SATS Pullback); "
          "Entry Timing default Current",
          fill_new[len("    else "):] == fill_old[len("    "):] and ord_new[len("            else "):] == ord_old[len("            "):]
          and "    if fillNow and stSats\n" in S and "            if stSats\n                // XA-7" in S
          and 'bool stSats = stTiming == "SATS Pullback"' in S and input_values(S)["stTiming"] == '"Current"')
    fn = func(S, "f_satBand() =>")
    glob = [l for l in S.split("\n") if "f_satBand()" in l and not l.lstrip().startswith("//")]
    check("XW-03 f_satBand() == the SATS source function byte for byte (VWMA(hlc3, 5) x 0.5, ta.atr(50)[1], close / high / low [1] "
          "x 0.5, LINE1 k 5 / LINE2 k 2.5 with the source's init and update order, STB Donchian 10 / 20 with the upper breakout "
          "first); called exactly once, at global scope (every bar, not only while waiting)",
          fn.rstrip("\n") + "\n" == SRC and glob == ["f_satBand() =>", "[satL1, satL2, satStb, satD1, satD2, satSD, satBand, satBasis, satCommon, satAtr, satA1, satA2] = f_satBand()"]
          and "ta.vwma(hlc3, 5)" in SRC and "ta.atr(50)[1]" in SRC and "float k1V = 5.0" in SRC and "float k2V = 2.5" in SRC
          and "ta.highest(high, 20)[1]" in SRC)
    co = code_only(S)
    check("XW-04 no colour / band-state rule and no extra request: satBand / satD1 / satD2 / satSD (colour directions, band state) are "
          "never read; no request.* added (no MTF / 9 timeframe requests), no bgcolor, no new alert()",
          not [v for v in ("satBand", "satD1", "satD2", "satSD") if len(re.findall(r"\b" + v + r"\b", co)) != 1]
          and re.findall(r"request\.\w+\(", co) == re.findall(r"request\.\w+\(", code_only(S0)) and "bgcolor(" not in co
          and co.count("alert(") == code_only(S0).count("alert("))
    vd, vd0 = input_decls(S), input_decls(S0)
    check("XW-05 inputs: Entry Timing Current / SATS Pullback (default Current), waiting limit 240 min, line display; SATS Pullback "
          "with an Entry Mode other than C stops with runtime.error (no silent behaviour); every previous input identical (Entry C, "
          "Short Only, SL 1.5, RR 1.5, BE ON 15, Role Reversal default Confirmed Break, sizing)",
          set(vd) - set(vd0) == {"stTiming", "stSatsWait", "stSatsShow"} and all(vd[n] == vd0[n] for n in vd0)
          and 'options = ["Current", "SATS Pullback"]' in vd["stTiming"] and input_values(S)["stSatsWait"] == "240"
          and "if stSats and not stModeC\n    runtime.error(" in S and input_values(S)["roleMode"] == '"Confirmed Break"'
          and input_values(S)["stDir"] == '"Short Only"' and input_values(S)["stMode"] == '"C: Candle Pattern"')
    w = block(S, "    // (3b) XA-7 SATS Pullback", "    // (4) 新規 Entry")
    order = [w.index(x) for x in ("time_close - pwEndT >= stSatsWait * 60000", "array.indexof(curTrk, pwTrack) < 0", "not zOK",
                                   "pwSide == 1 ? low <= pwSL0 : high >= pwSL0", "f_satPick(", "bool hit", "f_stQty(pwSide, close, pwSL0)",
                                   "strategy.entry(")]
    check("XW-06 waiting code: from the bar after the prep bar; cancel (wall-clock limit from the prep bar's end, Track gone, not a "
          "same-side Strong-eligible candidate, SL0 reached) is decided before the line / rebound; the line comes from "
          "f_satPick(side, P0, SL0, close[1], LINE1[1], LINE2[1], STB[1]); hit = low <= L <= high and close back with the P0 / SL0 "
          "window; market order only with the session / no order state; qty = f_stQty(side, close, SL0); a cancel never touches "
          "stUsed",
          order == sorted(order) and "bar_index > pwBar" in w and "f_satPick(pwSide, pwP0, pwSL0, close[1], satL1[1], satL2[1], satStb[1])" in w
          and "low <= lp and lp <= high" in w and "(close > lp and close > pwSL0 and close < pwP0)" in w
          and "(close < lp and close < pwSL0 and close > pwP0)" in w and "if hit and stSessOK and oState == 0" in w
          and "stUsed" not in w and "limit =" not in w)
    f = block(S, "    if fillNow and stSats\n", "    else if fillNow\n")
    p = block(S, "            if stSats\n                // XA-7", "            else if not skipRef and not na(pQty)\n")
    check("XW-07 SL0 / TP0 fixed: prepared once (only without an active wait and not on a cancel bar) from the existing ref / pSL / "
          "tpRef of the Entry C order path; at the fill TP = TP0 (no f_stTp / RR recomputation from the fill), set at the existing "
          "fill-confirmation time; a fill with risk <= 0 or TP0 not beyond it is closed at market and counted (no TP)",
          "pwState == 0 and not pwCancelBar" in p and "pwP0     := ref" in p and "pwSL0    := pSL" in p and "pwTP0    := tpRef" in p
          and "pwEndT   := time_close" in p and "f_stTp" not in f and "oTP   := oTP0" in f and "strategy.close(oEid)" in f
          and "riskS > 0 and rewS > 0" in f and code_only(S).count("map.put(stUsed") == code_only(S0).count("map.put(stUsed"))
    keep = ("f_stQty(int side, float ref, float sl) =>", "f_stTp(", "f_stZoneEval(zn.Zone z) =>", "f_stAdopt(")
    others = [p for p in os.listdir(ROOT) if p.endswith(".pine") and p != xb.STR_PATH]
    check("XW-08 unchanged: f_stQty / f_stTp / zone evaluation / adoption functions, strategy() options, the Zone / FVG / Break "
          "feed code before the Strategy part, every other Pine file (Engine, Visual, other symbols)",
          all(func(S, h) == func(S0, h) for h in keep) and seg(S, "strategy(", "import ") == seg(S0, "strategy(", "import ")
          and S[S.index("import "):S.index("var string G_ST =")] == S0[S0.index("import "):S0.index("var string G_ST =")]
          and not [p for p in others if rd(p) != xb.show(B, p)])


# ---- models ------------------------------------------------------------------------------------------------------------
def nz(v):
    return v is not None and not (isinstance(v, float) and math.isnan(v))


def sat_series(bars):
    """Python port of f_satBand on a list of (open, high, low, close, volume). Returns per-bar (line1, line2, stb, dir1, dir2, stbDir)."""
    out, tr, atr = [], [], None
    a1 = a2 = None
    d1 = d2 = 1
    sd = 1
    atr_hist = []
    for i, (o, h, l, c, v) in enumerate(bars):
        # ta.vwma(hlc3, 5)
        basis = None
        if i >= 4:
            w = bars[i - 4:i + 1]
            sv = sum(x[4] for x in w)
            basis = sum((x[1] + x[2] + x[3]) / 3 * x[4] for x in w) / sv if sv else None
        # ta.atr(50) = rma(tr, 50) seeded with the sma of the first 50 tr
        trv = h - l if i == 0 else max(h - l, abs(h - bars[i - 1][3]), abs(l - bars[i - 1][3]))
        tr.append(trv)
        if i == 49:
            atr = sum(tr) / 50
        elif i > 49:
            atr = (atr * 49 + trv) / 50
        atr_hist.append(atr)
        atr50 = atr_hist[i - 1] if i >= 1 else None
        src = bars[i - 1][3] * 0.5 if i >= 1 else None
        tl = bars[i - 1][2] * 0.5 if i >= 1 else None
        th = bars[i - 1][1] * 0.5 if i >= 1 else None
        ready = nz(atr50) and nz(src)
        for k, idx in ((5.0, 1), (2.5, 2)):
            a, d = (a1, d1) if idx == 1 else (a2, d2)
            pa, pd = a, d
            if ready:
                if pa is None:
                    a, d = src - k * atr50, 1
                elif pd == 1:
                    if tl < pa:
                        a, d = src + k * atr50, -1
                    else:
                        a, d = max(pa, src - k * atr50), 1
                else:
                    if th > pa:
                        a, d = src - k * atr50, 1
                    else:
                        a, d = min(pa, src + k * atr50), -1
            if idx == 1:
                a1, d1 = a, d
            else:
                a2, d2 = a, d
        common = basis * 0.5 if basis is not None else None
        l1 = common + a1 if common is not None and a1 is not None else None
        l2 = common + a2 if common is not None and a2 is not None else None
        up10 = max(x[1] for x in bars[i - 9:i + 1]) if i >= 9 else None
        lo10 = min(x[2] for x in bars[i - 9:i + 1]) if i >= 9 else None
        p20h = max(x[1] for x in bars[i - 20:i]) if i >= 20 else None
        p20l = min(x[2] for x in bars[i - 20:i]) if i >= 20 else None
        if p20h is not None and p20l is not None:
            if h > p20h:
                sd = 1
            elif l < p20l:
                sd = -1
        stb = (lo10 if sd == 1 else up10)
        out.append((l1, l2, stb, d1, d2, sd))
    return out


def pick(side, p0, sl0, pc, lines, variant=None):
    bk, bp, bd = 0, None, None
    for k, v in enumerate(lines, start=1):
        if v is None or pc is None:
            continue
        ok = (v > sl0 and v < p0 and v < pc) if side == 1 else (v < sl0 and v > p0 and v > pc)
        if ok:
            d = abs(pc - v)
            if bk == 0 or d < bd or (variant == "last_tie" and d == bd):
                bk, bp, bd = k, v, d
    return bk, bp


class Wait:
    """port of the XA-7 waiting machine (one confirmed 5M bar per step)."""

    def __init__(self, limit_min=240, variant=None):
        self.state, self.limit, self.variant = 0, limit_min, variant
        self.log, self.used = [], set()
        self.order = None

    def prepare(self, bar, t_end, side, track, p0, sl0, tp0, cancel_bar=False):
        if self.state == 0 and not cancel_bar or self.variant == "re_prepare":
            if self.variant == "re_prepare" and self.state == 1:
                self.t_end = t_end                       # mutation: a duplicate signal extends the expiry
                return
            self.state, self.bar, self.t_end, self.side, self.track = 1, bar, t_end, side, track
            self.p0, self.sl0, self.tp0 = p0, sl0, tp0
            self.log.append(("prep", bar))

    def step(self, bar, t_close, o, h, l, c, prev_c, prev_lines, cands, tracks, sess=True, o_state=0):
        """cands: set of (track, side) Strong-eligible candidates; tracks: set of live track ids. Returns (event, cancel_bar)."""
        if self.state != 1 or (bar <= self.bar and self.variant != "order_on_prep"):
            return None, False
        why = 0
        if t_close - self.t_end >= self.limit * 60000 and self.variant != "bars_not_time":
            why = -1
        elif self.variant == "bars_not_time" and bar - self.bar >= self.limit // 5:
            why = -1
        elif self.track not in tracks:
            why = -2
        elif (self.track, self.side) not in cands:
            why = -3
        elif (l <= self.sl0 if self.side == 1 else h >= self.sl0) and self.variant != "rebound_first":
            why = -4
        if why:
            self.state = 0
            self.log.append(("cancel", bar, why))
            return why, True
        k, L = pick(self.side, self.p0, self.sl0, prev_c, prev_lines)
        if k and l <= L <= h and ((c > L and self.sl0 < c < self.p0) if self.side == 1 else (c < L and self.p0 < c < self.sl0)) \
                and sess and o_state == 0:
            self.state = 0
            self.order = dict(bar=bar, ref=c, side=self.side, sl0=self.sl0, tp0=self.tp0, track=self.track, line=k, L=L)
            self.log.append(("order", bar, k))
            return 2, False
        return 0, False


def fill(order, fill_px):
    s = order["side"]
    risk, rew = s * (fill_px - order["sl0"]), s * (order["tp0"] - fill_px)
    rr = rew / risk if risk > 0 else None
    return ("tp", order["tp0"], rr) if risk > 0 and rew > 0 else ("close", None, rr)


T0 = 1_700_000_000_000
M5 = 300_000


def gate_model():
    random.seed(11)
    bars, px = [], 2600.0
    for _ in range(400):
        o = px
        c = o + random.uniform(-6, 6)
        h, l = max(o, c) + random.uniform(0, 4), min(o, c) - random.uniform(0, 4)
        bars.append((o, h, l, c, random.uniform(100, 1000)))
        px = c
    full = sat_series(bars)
    late = sat_series(bars[200:])
    check("XP-01 SATS lines must run on every bar: computing them only from a later start (as if started at a wait) gives different "
          "LINE1 / LINE2 values on the same bars (the anchors depend on the whole history) -> the Strategy calls f_satBand at "
          "global scope every bar", any(full[200 + i][0] != late[i][0] for i in range(60, 120) if late[i][0] is not None))
    lines = full[300][:3]
    recol = [(l1, l2, st, -d1, -d2, -sd) for (l1, l2, st, d1, d2, sd) in full]
    check("XP-02 colour / direction independence: the line choice uses only prices (flipping every direction / colour leaves the "
          "pick unchanged)", pick(-1, 2600.0, 2620.0, 2605.0, lines) == pick(-1, 2600.0, 2620.0, 2605.0, recol[300][:3]))
    check("XP-03 nearest line to the previous close among the eligible: Short P0 2600 / SL0 2620, prev close 2605: L1 2612, L2 2608, "
          "STB 2615 -> LINE2; L2 below prev close -> L1; ties -> LINE1 then LINE2 then STB; na skipped; none eligible -> (0, na)",
          pick(-1, 2600.0, 2620.0, 2605.0, (2612.0, 2608.0, 2615.0)) == (2, 2608.0)
          and pick(-1, 2600.0, 2620.0, 2605.0, (2612.0, 2604.0, 2615.0)) == (1, 2612.0)
          and pick(-1, 2600.0, 2620.0, 2605.0, (2610.0, 2610.0, 2610.0)) == (1, 2610.0)
          and pick(-1, 2600.0, 2620.0, 2605.0, (None, 2610.0, 2610.0)) == (2, 2610.0)
          and pick(-1, 2600.0, 2620.0, 2605.0, (2625.0, 2599.0, None)) == (0, None)
          and pick(1, 2600.0, 2580.0, 2595.0, (2588.0, 2592.0, 2570.0)) == (2, 2592.0))
    w = Wait()
    w.prepare(10, T0 + 10 * M5, -1, 7, 2600.0, 2620.0, 2570.0)
    ev_prep, _ = w.step(10, T0 + 10 * M5, 2600, 2611, 2598, 2601, 2600.0, (2610.0, None, None), {(7, -1)}, {7})
    ev1, _ = w.step(11, T0 + 11 * M5, 2601, 2611, 2600, 2606, 2601.0, (2610.0, None, None), {(7, -1)}, {7})
    check("XP-04 no order on the prep bar; Short rebound on a later bar: L1 2610 (from bar t-1) touched (low 2600 <= 2610 <= high "
          "2611) and close 2606 < 2610 with P0 2600 < close < SL0 2620 -> market order at the next bar, ref = 2606",
          ev_prep is None and ev1 == 2 and w.order["ref"] == 2606 and w.order["line"] == 1)
    w = Wait()
    w.prepare(10, T0 + 10 * M5, 1, 5, 2600.0, 2580.0, 2630.0)
    a = w.step(11, T0 + 11 * M5, 2598, 2599, 2589, 2591, 2597.0, (2590.0, None, None), {(5, 1)}, {5})
    check("XP-05 Long mirror: L 2590 below the prev close 2597, touched (low 2589) and close 2591 > 2590 with SL0 2580 < close < P0 "
          "2600 -> order; close 2589 (not back above L) or close 2601 (not better than P0) -> no order",
          a[0] == 2 and Wait_step_once(1, 2589.0) == 0 and Wait_step_once(1, 2601.0) == 0)
    w = Wait()
    w.prepare(10, T0 + 10 * M5, -1, 7, 2600.0, 2620.0, 2570.0)
    lines_t1 = (2610.0, None, None)
    ev, _ = w.step(11, T0 + 11 * M5, 2601, 2609.5, 2600, 2606, 2601.0, lines_t1, {(7, -1)}, {7})
    check("XP-06 bar t uses only the bar t-1 line: the high 2609.5 does not reach the t-1 line 2610 -> no order, even if the line "
          "computed at the close of bar t were lower (that value is not used for bar t)", ev == 0)
    pri = []
    for cands, tracks, hi, why in (({(7, -1)}, {7}, 2621, -4), ({(7, -1)}, set(), 2611, -2), (set(), {7}, 2611, -3)):
        w = Wait()
        w.prepare(10, T0 + 10 * M5, -1, 7, 2600.0, 2620.0, 2570.0)
        ev, cb = w.step(11, T0 + 11 * M5, 2601, hi, 2600, 2606, 2601.0, (2610.0, None, None), cands, tracks)
        pri.append(ev == why and cb and w.order is None)
    check("XP-07 cancels win over the rebound on the same bar: SL0 reached (Short high 2621 >= 2620), Track gone, no longer a "
          "same-side Strong-eligible candidate -> cancel, no order; the cancel bar does not prepare again", all(pri), str(pri))
    w = Wait()
    w.prepare(10, T0 + 10 * M5, -1, 7, 2600.0, 2620.0, 2570.0)
    a = w.step(57, T0 + 10 * M5 + 239 * 60000, 2601, 2603, 2600, 2601, 2601.0, (None, None, None), {(7, -1)}, {7})
    b = w.step(58, T0 + 10 * M5 + 240 * 60000, 2601, 2603, 2600, 2601, 2601.0, (None, None, None), {(7, -1)}, {7})
    w2 = Wait()
    w2.prepare(10, T0 + 10 * M5, -1, 7, 2600.0, 2620.0, 2570.0)
    gap = w2.step(11, T0 + 10 * M5 + 48 * 3600000, 2601, 2603, 2600, 2601, 2601.0, (None, None, None), {(7, -1)}, {7})
    check("XP-08 240-minute limit by wall clock from the prep bar's end: 239 min -> still waiting (no eligible line is not a "
          "cancel), 240 min -> expired; across a 48 h weekend gap the very next bar expires (not a bar count)",
          a[0] == 0 and b[0] == -1 and gap[0] == -1)
    w = Wait()
    w.prepare(10, T0 + 10 * M5, -1, 7, 2600.0, 2620.0, 2570.0)
    w.prepare(20, T0 + 20 * M5, -1, 8, 2590.0, 2615.0, 2550.0)
    keep = (w.track, w.p0, w.sl0, w.tp0, w.t_end) == (7, 2600.0, 2620.0, 2570.0, T0 + 10 * M5)
    exp = w.step(58, T0 + 10 * M5 + 240 * 60000, 2601, 2603, 2600, 2601, 2601.0, (None, None, None), {(7, -1), (8, -1)}, {7, 8})
    check("XP-09 one wait in total: a new Entry C signal while waiting neither replaces the stored values nor extends the limit",
          keep and exp[0] == -1)
    o = dict(side=-1, sl0=2620.0, tp0=2570.0, ref=2606.0)
    f1, f2, f3 = fill(o, 2607.0), fill(o, 2595.0), fill(o, 2565.0)
    check("XP-10 SL0 / TP0 fixed; actual RR from the fill: planned RR at 2606 = 36 / 14 = 2.571; gap fill 2595 (worse than P0 2600 "
          "is kept) -> TP 2570 stays, RR 25 / 25 = 1.0; fill 2565 beyond TP0 -> no TP, closed at market (not a normal entry)",
          f1[0] == "tp" and f1[1] == 2570.0 and abs(-1 * (2570 - 2606) / (-1 * (2606 - 2620)) - 36 / 14) < 1e-12
          and f2 == ("tp", 2570.0, 1.0) and f3[0] == "close")
    w = Wait()
    w.prepare(10, T0 + 10 * M5, -1, 7, 2600.0, 2620.0, 2570.0)
    out_sess = w.step(11, T0 + 11 * M5, 2601, 2611, 2600, 2606, 2601.0, (2610.0, None, None), {(7, -1)}, {7}, sess=False)
    in_sess = w.step(12, T0 + 12 * M5, 2601, 2611, 2600, 2606, 2601.0, (2610.0, None, None), {(7, -1)}, {7})
    check("XP-11 outside the session: no order, the wait continues (the clock keeps running); inside the session on a later bar the "
          "same rebound orders", out_sess[0] == 0 and in_sess[0] == 2)
    w = Wait()
    w.prepare(10, T0 + 10 * M5, -1, 7, 2600.0, 2620.0, 2570.0)
    w.step(11, T0 + 11 * M5, 2601, 2621, 2600, 2606, 2601.0, (2610.0, None, None), {(7, -1)}, {7})
    check("XP-12 a cancel does not mark the Track used (stUsed is written only by the existing fill code); after a cancel no order "
          "exists (no double order: the wait is cleared at the order, the order path needs oState 0)",
          w.used == set() and w.order is None and w.state == 0)


def Wait_step_once(side, close_px):
    w = Wait()
    w.prepare(10, T0 + 10 * M5, side, 5, 2600.0, 2580.0, 2630.0)
    return w.step(11, T0 + 11 * M5, 2598, 2599, 2589, close_px, 2597.0, (2590.0, None, None), {(5, side)}, {5})[0]


def gate_mutation():
    bad = []
    w = Wait(variant="order_on_prep")
    w.prepare(10, T0 + 10 * M5, -1, 7, 2600.0, 2620.0, 2570.0)
    bad.append(w.step(10, T0 + 10 * M5, 2600, 2611, 2598, 2601, 2600.0, (2610.0, None, None), {(7, -1)}, {7})[0] == 2)
    w = Wait(variant="rebound_first")
    w.prepare(10, T0 + 10 * M5, -1, 7, 2600.0, 2620.0, 2570.0)
    bad.append(w.step(11, T0 + 11 * M5, 2601, 2621, 2600, 2606, 2601.0, (2610.0, None, None), {(7, -1)}, {7})[0] == 2)
    w = Wait(variant="bars_not_time")
    w.prepare(10, T0 + 10 * M5, -1, 7, 2600.0, 2620.0, 2570.0)
    bad.append(w.step(11, T0 + 10 * M5 + 48 * 3600000, 2601, 2603, 2600, 2601, 2601.0, (None, None, None), {(7, -1)}, {7})[0] != -1)
    w = Wait(variant="re_prepare")
    w.prepare(10, T0 + 10 * M5, -1, 7, 2600.0, 2620.0, 2570.0)
    w.prepare(20, T0 + 20 * M5, -1, 8, 2590.0, 2615.0, 2550.0)
    bad.append(w.step(58, T0 + 10 * M5 + 240 * 60000, 2601, 2603, 2600, 2601, 2601.0, (None, None, None), {(7, -1)}, {7})[0] != -1)
    bad.append(pick(-1, 2600.0, 2620.0, 2605.0, (2610.0, 2610.0, 2610.0), variant="last_tie") != (1, 2610.0))
    check("XQ-01 mirror mutations caught: order on the prep bar, rebound before the SL0 cancel, bar count instead of wall clock, "
          "duplicate signal extending the limit, last-wins ties", all(bad), str(bad))
    muts = [S.replace("satL1[1], satL2[1], satStb[1])", "satL1, satL2, satStb)"),
            S.replace("            why := -4\n", "            why := 0\n"),
            S.replace("            oTP   := oTP0\n", "            oTP   := oFill + oSide * stRR * riskS\n"),
            S.replace("time_close - pwEndT >= stSatsWait * 60000", "bar_index - pwBar >= stSatsWait / 5"),
            S.replace("    float atr50V = ta.atr(50)[1]\n", "    float atr50V = ta.atr(50)\n")]
    check("XQ-02 source mutations rejected by the exact strip: bar-t lines, SL0 cancel removed, TP rebuilt from the fill, bar-count "
          "expiry, ATR without [1]", all(m != S and xb.strip_strategy7(m) is None for m in muts))


def main():
    for g in (gate_static, gate_model, gate_mutation):
        try:
            g()
        except Exception:
            import traceback
            check(f"{g.__name__} completed without error", False, traceback.format_exc()[-900:])
    fails = 0
    for n, ok, d in RESULTS:
        fails += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {n[:150].ljust(150)}  {'' if ok else d}")
    print(f"\n{len(RESULTS) - fails}/{len(RESULTS)} passed  [PINE_NOT_VERIFIED: exact build / static / Python models]")
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
