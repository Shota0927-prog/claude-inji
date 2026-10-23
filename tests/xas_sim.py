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
  XV : XA-8 on the delivered Strategy — the actual RR is also recorded for a SATS fill closed in its fill bar (closed trade's
       entry price, stored SL0 / TP0, no order), reasons for invalid distances, one record per fill on either path
  XN : XA-9 on the delivered Strategy — no zone re-check after the prep (cancel = limit / SL0 only), touch recorded with the
       line kind, rebound A (touch bar) or B (later bar: previous close and close across the same t-1 line value)
  XZ : XA-10 on the delivered Strategy — SATS Pullback with Entry Mode A / B / C / D (C-only stop removed; one shared prep in
       the order block with each mode's ref: A the limit price, B / C / D the close; D after its BOS)
  XY : XA-11 on the delivered Strategy — two independent comparison inputs (default OFF): (1) the order bar itself bullish /
       bearish together with rebound A or B of that bar; (2) a near approach (USD distance, t-1 line L) counts as the touch,
       the close-back keeps the original L; both OFF = the XA-10 path
  XK : XA-12 on the delivered Strategy / Visual — Gold adopted defaults (Entry Timing SATS Pullback, Role Reversal Retest
       Confirmed in both files, SATS body ON, near ON, near distance 1.0) and the tooltips / comments naming them; nothing else
  XH : XA-13 on the delivered Strategy — SATS all-selected-timeframes opposite-band filter (D / 4H / 1H / 15m / 5m, default OFF):
       AND over the selected timeframes only, each timeframe on its own history (last confirmed HTF bar), applied at the final
       SATS order test only, a skip changes nothing
  XJ : XA-14 on the delivered Strategy — adopted defaults of the XA-13 filter (4H / 1H ON, D / 15m / 5m OFF) and the text naming
       them; nothing else
  XB : XA-15 on the delivered Strategy — Breakeven Trigger Mode (Fixed Distance default = the old test / Risk Multiple from the
       fill and the initial SL / TP Progress from the fill and the TP actually set); only the trigger distance changes
  (XW / XP / XQ run on the XA-7 layer, XV on XA-8, XN on XA-9, XZ on XA-10, XY on XA-11, XK on XA-12, XH on XA-13, XJ on XA-14:
  the Strategy with exactly the later edits reverted; the Visual through strip_visual7)

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
S, S0 = xb.strip_strategy8(rd(xb.STR_PATH)) or "", xb.show(B, xb.STR_PATH)   # XA-7 layer (XA-8 reverted exactly; pinned by XV)
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
          xb.build_strategy7() == S and xb.strip_strategy7(S) == S0 and xb.build_strategy6() == S0
          and rd(xb.ENG_PATH) == xb.show(B, xb.ENG_PATH) and xb.strip_visual7(rd(xb.VIS_PATH)) == xb.show(B, xb.VIS_PATH)
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
          and not [p for p in others if (xb.strip_visual7(rd(p)) if p == xb.VIS_PATH else rd(p)) != xb.show(B, p)])


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


# ---- XA-8: actual RR for a SATS fill closed in its fill bar -------------------------------------------------------------
def sat_rr(side, fill_px, sl0, tp0):
    """port of f_satRR: (rr, reason)."""
    if fill_px is None or sl0 is None or tp0 is None:
        return None, 3
    risk, rew = side * (fill_px - sl0), side * (tp0 - fill_px)
    if risk <= 0:
        return None, 1
    if rew <= 0:
        return None, 2
    return rew / risk, 0


def confirm(sats, filled_open, filled_closed, fill_px, sl0, tp0, side, rec):
    """port of step (1) + (2b') for one order: exclusive branches; returns the orders placed on this confirmation."""
    orders = []
    if filled_open:
        if sats:
            rr, why = sat_rr(side, fill_px, sl0, tp0)
            rec.append(("hold", rr, why))
            risk, rew = side * (fill_px - sl0), side * (tp0 - fill_px)
            orders.append("exit" if risk > 0 and rew > 0 else "close")
        else:
            orders.append("exit")
    elif filled_closed:
        if sats:
            rr, why = sat_rr(side, fill_px, sl0, tp0)
            rec.append(("closed", rr, why))
    return orders


def gate_xa8():
    S8, S7 = xb.strip_strategy9(rd(xb.STR_PATH)) or "", xb.show("6b9458d", xb.STR_PATH)   # XA-8 layer (XA-9 reverted exactly)
    check("XV-01 XA-8: Strategy == xa_build.build_strategy() (XA-1 .. XA-8); strip_strategy8 gives 6b9458d byte for byte; edit "
          "kinds header / rr", xb.build_strategy8() == S8 and xb.strip_strategy8(S8) == S7 and xb.build_strategy7() == S7
          and {k for k, _, _ in xb.STRATEGY_EDITS8} == {"header", "rr"})
    ch = [l for l in es.changed_code(S7, S8) if l]
    stray = [l for l in ch if re.search(r"strategy\.(entry|exit|close|cancel)\(|map\.put|oState\s*:=|oTP\s*:=|oStop\s*:=", l)]
    cl = block(S8, "        else if filledClosed\n", "        else if not oLimit\n")
    hold = block(S8, "    if fillNow and stSats\n", "    else if fillNow\n")
    hold7 = block(S7, "    if fillNow and stSats\n", "    else if fillNow\n")
    norm = lambda t: [l for l in t.split("\n") if "pwRR" not in l and "pwNFill" not in l and "pwFillPath" not in l and "f_satRR" not in l]
    check("XV-02 record only: no added order / state / TP / stop / stUsed line; the closed-in-fill-bar branch keeps stUsed and "
          "oState := 0 and adds the record only under `if stSats` (no TP / close order); the holding path's order handling "
          "(riskS / rewS, exit or market close, bad-fill count) is unchanged apart from the record lines; Current unchanged",
          not stray and "map.put(stUsed, oTrack, true)\n            oState := 0\n            if stSats     // XA-8" in cl
          and not re.search(r"strategy\.(entry|exit|close|cancel)\(", cl.split("if stSats")[1]) and norm(hold) == norm(hold7)
          and "strategy.closedtrades.entry_price(ct - 1), oSL, oTP0)" in cl and "f_satRR(oSide, oFill, oSL, oTP0)" in hold,
          str(stray[:3]))
    check("XV-03 f_satRR: RR = side x (TP0 - fill) / side x (fill - SL0); reason 1 when the fill is at / beyond SL0, 2 when TP0 "
          "is not beyond the fill, 3 when a price is na; RR na unless reason 0; both paths set pwNFill += 1 once and the path "
          "code (1 holding / 2 closed in the fill bar); the order resets RR and reason",
          "float risk = side * (fillPx - sl0)" in S8 and "float rew  = side * (tp0 - fillPx)" in S8
          and code_only(S8).count("pwNFill    += 1") == 2 and "pwFillPath := 1" in hold and "pwFillPath := 2" in cl
          and "                    pwRRFill := na\n                    pwRRWhy  := na\n" in S8)
    rec = []
    o1 = confirm(True, True, False, 2602.0, 2620.0, 2570.0, -1, rec)
    o2 = confirm(True, False, True, 2603.0, 2620.0, 2570.0, -1, rec)
    o3 = confirm(False, False, True, 2603.0, 2620.0, 2570.0, -1, rec)
    check("XV-04 model: SATS fill still holding -> RR 32 / 18 = 1.778 recorded once with an exit order; SATS fill closed in its "
          "fill bar at SL -> RR 33 / 17 = 1.941 recorded once, no order; Current closed fill -> no record; 2 fills -> 2 records "
          "(the branches are exclusive, no double count)",
          o1 == ["exit"] and o2 == [] and o3 == [] and len(rec) == 2 and rec[0][0] == "hold" and abs(rec[0][1] - 32 / 18) < 1e-12
          and rec[1][0] == "closed" and abs(rec[1][1] - 33 / 17) < 1e-12 and rec[1][2] == 0)
    check("XV-05 invalid distances -> na with distinct reasons: Short fill 2621 at / beyond SL0 2620 -> (na, 1); fill 2569 beyond "
          "TP0 2570 -> (na, 2); fill na -> (na, 3); Long mirror (fill 2579 below SL0 2580 -> 1, fill 2631 above TP0 2630 -> 2)",
          sat_rr(-1, 2621.0, 2620.0, 2570.0) == (None, 1) and sat_rr(-1, 2569.0, 2620.0, 2570.0) == (None, 2)
          and sat_rr(-1, None, 2620.0, 2570.0) == (None, 3) and sat_rr(-1, 2620.0, 2620.0, 2570.0) == (None, 1)
          and sat_rr(1, 2579.0, 2580.0, 2630.0) == (None, 1) and sat_rr(1, 2631.0, 2580.0, 2630.0) == (None, 2)
          and abs(sat_rr(1, 2590.0, 2580.0, 2630.0)[0] - 4.0) < 1e-12)
    m = S8.replace("                pwNFill    += 1\n                pwFillPath := 2\n", "                pwFillPath := 2\n")
    m2 = S8.replace("            if stSats     // XA-8", "            if true     // XA-8")
    check("XV-06 source mutations rejected by the exact strip: closed path not counted, record for Current too",
          m != S8 and m2 != S8 and xb.strip_strategy8(m) is None and xb.strip_strategy8(m2) is None)


# ---- XA-9: no zone re-check, touch recorded, rebound on the touch bar or a later bar ----------------------------------------
class Wait9:
    """port of the XA-9 waiting step. bars feed (bar, t_close, high, low, close, prev_close, lines_t1 (L1, L2, STB))."""

    def __init__(self, side, p0, sl0, tp0, prep_bar=10, t_end=T0 + 10 * M5, limit=240, variant=None):
        self.state, self.side, self.p0, self.sl0, self.tp0 = 1, side, p0, sl0, tp0
        self.bar, self.t_end, self.limit, self.variant = prep_bar, t_end, limit, variant
        self.touched, self.tk, self.tbar = False, 0, None
        self.n_touch_prep = self.n_same = self.n_later = self.n_exp = self.n_sl = 0
        self.orders, self.log = [], []

    def step(self, bar, t_close, h, l, c, pc, lines, sess=True, qty_ok=True, o_state=0, cands=None, tracks=None):
        if self.state != 1 or bar <= self.bar:
            return None
        why = 0
        if t_close - self.t_end >= self.limit * 60000:
            why = -1
        elif (l <= self.sl0) if self.side == 1 else (h >= self.sl0):
            why = -4
        elif self.variant == "zone_recheck" and cands is not None and (7, self.side) not in cands:
            why = -3
        if why:
            self.state = 0
            self.n_exp += why == -1
            self.n_sl += why == -4
            self.touched, self.tk, self.tbar = False, 0, None
            return why
        if not self.touched or self.variant == "repick_after_touch":
            k, L = pick(self.side, self.p0, self.sl0, pc, lines)
        else:
            k, L = self.tk, lines[self.tk - 1]
        in_range = k != 0 and L is not None and ((self.sl0 < L < self.p0) if self.side == 1 else (self.p0 < L < self.sl0))
        touch = in_range and l <= L <= h
        reb_a = touch and ((c > L) if self.side == 1 else (c < L))
        if self.variant == "line_moved":
            reb_b = self.touched and in_range and ((c > L) if self.side == 1 else (c < L))
        else:
            reb_b = self.touched and in_range and ((pc <= L and c > L) if self.side == 1 else (pc >= L and c < L))
        if touch and not self.touched:
            self.touched, self.tk, self.tbar = True, k, bar
            self.n_touch_prep += 1
        price_ok = (self.sl0 < c < self.p0) if self.side == 1 else (self.p0 < c < self.sl0)
        if (reb_a or reb_b) and price_ok and sess and o_state == 0 and qty_ok:
            self.state = 0
            self.orders.append(dict(bar=bar, ref=c, kind="A" if reb_a else "B", line=k, L=L))
            self.n_same += reb_a
            self.n_later += not reb_a
            self.touched, self.tk, self.tbar = False, 0, None
            return 2
        return 0


def tb(i):
    return T0 + (10 + i) * M5


def gate_xa9():
    S9, S8 = xb.strip_strategy10(rd(xb.STR_PATH)) or "", xb.show("a32bd85", xb.STR_PATH)   # XA-9 layer (XA-10 reverted exactly)
    check("XN-01 XA-9: Strategy == xa_build.build_strategy() (XA-1 .. XA-9); strip_strategy9 gives a32bd85 byte for byte; kinds "
          "header / touch; Engine / Visual / SATS formula (f_satBand == the source record) unchanged",
          xb.build_strategy9() == S9 and xb.strip_strategy9(S9) == S8 and xb.build_strategy8() == S8
          and {k for k, _, _ in xb.STRATEGY_EDITS9} == {"header", "touch"} and func(S9, "f_satBand() =>").rstrip("\n") + "\n" == SRC
          and rd(xb.ENG_PATH) == xb.show(B, xb.ENG_PATH) and xb.strip_visual7(rd(xb.VIS_PATH)) == xb.show(B, xb.VIS_PATH))
    w = block(S9, "    // (3b) XA-7 / XA-9 SATS Pullback", "    // (4) 新規 Entry")
    ord_old = block(S8, "            else if not skipRef and not na(pQty)\n", "    stPrev := cur")
    ord_new = block(S9, "            else if not skipRef and not na(pQty)\n", "    stPrev := cur")
    fill8 = block(S8, "    if fillNow and stSats\n", "    // (2c)")
    fill9 = block(S9, "    if fillNow and stSats\n", "    // (2c)")
    cl8 = block(S8, "        else if filledClosed\n", "        else if not oLimit\n")
    cl9 = block(S9, "        else if filledClosed\n", "        else if not oLimit\n")
    prep = block(S9, "            if stSats\n                // XA-7", "            else if not skipRef and not na(pQty)\n")
    check("XN-02 Current and the fill / RR paths unchanged: the Entry order block, the fill-confirmation blocks (SATS TP0 and "
          "Current), the closed-in-fill-bar record (XA-8) byte-identical to a32bd85; the prep keeps the Entry C order "
          "conditions and stored values and now also resets the touch state",
          ord_new == ord_old and fill9 == fill8 and cl9 == cl8 and "pwState == 0 and not pwCancelBar" in prep
          and "pwTouched  := false     // XA-9" in prep and "pwP0     := ref" in prep and "pwTP0    := tpRef" in prep)
    check("XN-03 cancels are only the wall-clock limit and SL0 (no Track / Strong-candidate re-check: no curTrk / cur / zOK in the "
          "waiting code), decided before the rebound; the Track / qualification counters are removed",
          "time_close - pwEndT >= stSatsWait * 60000" in w and "pwSide == 1 ? low <= pwSL0 : high >= pwSL0" in w
          and not re.search(r"curTrk|\bcur\b|zOK|pwNTrk|pwNZone", w) and "pwNTrk" not in S9 and "pwNZone" not in S9
          and w.index("why := -4") < w.index("bool rebA"))
    check("XN-04 line handling: before the touch f_satPick(side, P0, SL0, close[1], LINE1[1], LINE2[1], STB[1]); after the touch the "
          "recorded kind's t-1 value (no re-pick, no previous-close side rule); in range = SL0 < L < P0 (mirrored); touch = in "
          "range and low <= L <= high; A = touch and close back; B = touched and previous close <= L < close (Short >= / >) with "
          "the same L; order needs A or B, SL0 < close < P0, session, no order, valid qty; touch state reset on cancel / order",
          "lp := pwTouchK == 1 ? satL1[1] : pwTouchK == 2 ? satL2[1] : satStb[1]" in w
          and "(close[1] <= lp and close > lp)" in w and "(close[1] >= lp and close < lp)" in w
          and "bool rebB     = pwTouched and inRange" in w and "if (rebA or rebB) and priceOK and stSessOK and oState == 0" in w
          and w.count("pwTouched  := false") == 2 and "f_stQty(pwSide, close, pwSL0)" in w)
    # models: Short P0 2600, SL0 2620, TP0 2570; Long mirror P0 2600, SL0 2580, TP0 2630
    s = Wait9(-1, 2600.0, 2620.0, 2570.0)
    r1 = s.step(11, tb(1), 2611, 2600, 2606, 2601.0, (2610.0, None, None), cands=set(), tracks=set())
    check("XN-05 no zone re-check: the Track gone and no Strong candidate do not cancel; A on the touch bar orders (Short: touch "
          "2610, close 2606 < 2610, P0 < close < SL0)", r1 == 2 and s.orders[0]["kind"] == "A" and s.n_same == 1)
    s = Wait9(-1, 2600.0, 2620.0, 2570.0)
    a = s.step(11, tb(1), 2612, 2604, 2611, 2603.0, (2610.0, None, None))
    tk_after_touch = s.tk
    b = s.step(12, tb(2), 2610, 2605, 2606, 2611.0, (2611.0, 2606.0, None))
    check("XN-06 touch then the next bar: bar 11 touches LINE1 2610 and closes 2611 above it (no A, touch recorded, kind LINE1); bar "
          "12 (gap, high 2610) uses LINE1's t-1 value 2611 (LINE2 2606 nearer is not used): prev close 2611 >= 2611 and close 2606 "
          "< 2611 -> B order",
          a == 0 and tk_after_touch == 1 and b == 2 and s.orders[0]["kind"] == "B" and s.orders[0]["line"] == 1 and s.n_later == 1
          and s.n_touch_prep == 1)
    s = Wait9(-1, 2600.0, 2620.0, 2570.0)
    seq = [s.step(11, tb(1), 2612, 2604, 2611, 2603.0, (2610.0, None, None)),
           s.step(12, tb(2), 2614, 2609, 2613, 2611.0, (2610.5, None, None)),
           s.step(13, tb(3), 2615, 2610, 2612, 2613.0, (2610.4, None, None)),
           s.step(14, tb(4), 2609.5, 2607, 2608, 2612.0, (2610.2, None, None))]
    check("XN-07 later bar: touched at bar 11, two bars above the line (no rebound, record kept, touched once = 1 prep), bar 14 "
          "prev close 2612 >= 2610.2 and close 2608 < 2610.2 -> B order",
          seq == [0, 0, 0, 2] and s.n_touch_prep == 1 and s.orders[0]["kind"] == "B")
    s = Wait9(-1, 2600.0, 2620.0, 2570.0)
    x1 = s.step(11, tb(1), 2609, 2601, 2604, 2611.0, (2610.0, None, None))
    check("XN-08 crossing without a touch is not an order: prev close 2611 above LINE1 2610, the bar never reaches it (high 2609) "
          "and closes 2604 below -> no touch, no order (B needs a recorded touch)", x1 == 0 and not s.touched)
    s = Wait9(-1, 2600.0, 2620.0, 2570.0)
    s.step(11, tb(1), 2612, 2604, 2611, 2603.0, (2610.0, None, None))
    mv = s.step(12, tb(2), 2611.5, 2606, 2609, 2611.0, (2612.0, None, None))
    check("XN-09 a line move alone is not a later rebound: touched LINE1, next bar LINE1 moves up to 2612 above both the previous "
          "close 2611 and the close 2609 (no touch) -> no order (a mirror that only requires the close beyond L would order)",
          mv == 0 and Wait9_variant_moves() == 2)
    s = Wait9(-1, 2600.0, 2620.0, 2570.0)
    s.step(11, tb(1), 2612, 2604, 2611, 2603.0, (2610.0, None, None))
    na_ = s.step(12, tb(2), 2612, 2605, 2606, 2611.0, (None, None, None))
    out = s.step(13, tb(3), 2625 - 6, 2605, 2606, 2611.0, (2621.0, None, None))
    back = s.step(14, tb(4), 2612, 2605, 2606, 2611.0, (2610.0, None, None))
    check("XN-10 after the touch: LINE1 na -> no decision, record kept; LINE1 2621 outside SL0 2620 -> no order, record kept; back in "
          "range (2610) -> B order on the same line", na_ == 0 and out == 0 and back == 2 and s.orders[0]["line"] == 1)
    s = Wait9(-1, 2600.0, 2620.0, 2570.0)
    s.step(11, tb(1), 2612, 2604, 2611, 2603.0, (2610.0, None, None))
    side = s.step(12, tb(2), 2611, 2603, 2604, 2605.0, (2610.0, None, None))
    check("XN-11 after the touch the previous-close side rule is not required: the held LINE1 2610 is above the previous close 2605 "
          "(before the touch it would not be eligible); the bar re-touches it from below and closes 2604 < 2610 -> A order on LINE1",
          side == 2 and s.orders[0]["line"] == 1 and s.orders[0]["kind"] == "A")
    res = []
    for kw, why in ((dict(sess=False), 0), (dict(qty_ok=False), 0), (dict(o_state=1), 0)):
        s = Wait9(-1, 2600.0, 2620.0, 2570.0)
        res.append(s.step(11, tb(1), 2611, 2600, 2606, 2601.0, (2610.0, None, None), **kw) == why and s.touched)
    s = Wait9(-1, 2600.0, 2620.0, 2570.0)
    s.step(11, tb(1), 2611, 2600, 2606, 2601.0, (2610.0, None, None), sess=False)
    noauto = s.step(12, tb(2), 2607, 2603, 2605, 2606.0, (2610.0, None, None))
    worse = Wait9(-1, 2600.0, 2620.0, 2570.0)
    w1 = worse.step(11, tb(1), 2611, 2598, 2599, 2601.0, (2610.0, None, None))
    check("XN-12 outside the session / no qty / an order present -> no order, the touch record kept; the next bar with only prices "
          "in range but no new rebound does not order (no stored rebound); close 2599 not better than P0 2600 -> no order",
          all(res) and noauto == 0 and w1 == 0)
    pri = []
    s = Wait9(-1, 2600.0, 2620.0, 2570.0)
    s.step(11, tb(1), 2612, 2604, 2611, 2603.0, (2610.0, None, None))
    pri.append(s.step(12, tb(2), 2621, 2605, 2606, 2611.0, (2610.0, None, None)) == -4 and not s.touched and s.n_sl == 1)
    s = Wait9(-1, 2600.0, 2620.0, 2570.0)
    pri.append(s.step(58, T0 + 10 * M5 + 240 * 60000, 2611, 2600, 2606, 2601.0, (2610.0, None, None)) == -1 and s.n_exp == 1)
    s = Wait9(-1, 2600.0, 2620.0, 2570.0)
    pri.append(s.step(57, T0 + 10 * M5 + 239 * 60000, 2611, 2600, 2606, 2601.0, (2610.0, None, None)) == 2)
    check("XN-13 cancels keep priority and reset the touch: SL0 reached on a rebound bar -> cancel (no order, touch cleared); 240 "
          "minutes -> expired; 239 minutes -> rebound still orders", all(pri), str(pri))
    l = Wait9(1, 2600.0, 2580.0, 2630.0)
    la = l.step(11, tb(1), 2595, 2588, 2589, 2597.0, (2590.0, None, None))
    lb = l.step(12, tb(2), 2593, 2591, 2592, 2589.0, (2590.5, None, None))
    check("XN-14 Long mirror: touch LINE1 2590 closing 2589 below (record), next bar prev close 2589 <= 2590.5 and close 2592 > 2590.5 "
          "with SL0 < close < P0 -> B order", la == 0 and lb == 2 and l.orders[0]["kind"] == "B")
    s = Wait9(-1, 2600.0, 2620.0, 2570.0)
    s.step(11, tb(1), 2611, 2600, 2606, 2601.0, (2610.0, None, None))
    again = s.step(12, tb(2), 2611, 2600, 2606, 2601.0, (2610.0, None, None))
    check("XN-15 no double order: after the order the wait is cleared (state 0, touch reset), later bars do nothing; a new prep "
          "starts untouched", again is None and s.state == 0 and not s.touched and s.tk == 0
          and Wait9(-1, 2600.0, 2620.0, 2570.0).touched is False)
    bad = []
    v = Wait9(-1, 2600.0, 2620.0, 2570.0, variant="zone_recheck")
    bad.append(v.step(11, tb(1), 2611, 2600, 2606, 2601.0, (2610.0, None, None), cands=set()) == -3)
    v = Wait9(-1, 2600.0, 2620.0, 2570.0, variant="repick_after_touch")
    v.step(11, tb(1), 2612, 2604, 2611, 2603.0, (2610.0, None, None))
    bad.append(v.step(12, tb(2), 2610, 2605, 2606, 2611.0, (2611.0, 2606.0, None)) != 2 or v.orders == [] or v.orders[0]["line"] != 1)
    m = S9.replace("(close[1] >= lp and close < lp)", "(close < lp)")
    m2 = S9.replace("        else if pwSide == 1 ? low <= pwSL0 : high >= pwSL0\n            why := -4\n", "")
    check("XN-16 mutations caught: zone re-check cancelling, re-picking another line after the touch; source mutations (B without "
          "the previous close, SL0 cancel removed) rejected by the exact strip",
          bad[0] and bad[1] and m != S9 and m2 != S9 and xb.strip_strategy9(m) is None and xb.strip_strategy9(m2) is None, str(bad))


def Wait9_variant_moves():
    v = Wait9(-1, 2600.0, 2620.0, 2570.0, variant="line_moved")
    v.step(11, tb(1), 2612, 2604, 2611, 2603.0, (2610.0, None, None))
    return v.step(12, tb(2), 2611.5, 2606, 2609, 2611.0, (2612.0, None, None))


# ---- XA-10: SATS Pullback with Entry Mode A / B / C / D ------------------------------------------------------------------
def prep_model(mode, side, close_px, limit_px, zone_top, zone_bot, buf=1.5, rr=1.5, pattern_ok=True, bos_done=True, sess=True):
    """port of the shared order block (4) for one selected candidate: Current -> order kind, SATS -> prep values."""
    if mode == "C" and not pattern_ok:
        return None
    if mode == "D" and not bos_done:          # D candidates exist only in dSrc after the 1M BOS
        return None
    if not sess:
        return None
    ref = limit_px if mode == "A" else close_px
    sl = zone_bot - buf if side == 1 else zone_top + buf
    risk = side * (ref - sl)
    tp = ref + side * rr * risk
    return dict(ref=ref, sl0=sl, tp0=tp, current_order="limit" if mode == "A" else "market")


def gate_xa10():
    S10, S9 = xb.strip_strategy11(rd(xb.STR_PATH)) or "", xb.show("3ca1837", xb.STR_PATH)   # XA-10 layer (XA-11 reverted exactly)
    ch = sorted(l for l in es.changed_code(S9, S10) if l)
    code_rm = [l for l in ch if not l.startswith('"') and not l.startswith("tooltip")]
    check("XZ-01 XA-10: Strategy == xa_build.build_strategy() (XA-1 .. XA-10); strip_strategy10 gives 3ca1837 byte for byte; the "
          "only code change is the removal of the C-only runtime.error (2 lines), the rest are tooltip strings / comments; "
          "Entry Mode default C, Entry Timing default Current, Role Reversal default unchanged",
          xb.build_strategy10() == S10 and xb.strip_strategy10(S10) == S9 and xb.build_strategy9() == S9
          and code_rm == sorted(["if stSats and not stModeC",
                                 'runtime.error("Entry Timing = SATS Pullback は Entry Mode C: Candle Pattern 専用です (他の Entry Mode は対象外)。")'])
          and input_values(S10)["stMode"] == '"C: Candle Pattern"' and input_values(S10)["stTiming"] == '"Current"'
          and input_values(S10)["roleMode"] == '"Confirmed Break"' and "C: Candle Pattern 専用" not in S10, str(code_rm))
    blk4 = block(S10, "    if oState == 0 and not cancelBar and stSessOK\n", "    stPrev := cur")
    prep = block(S10, "            if stSats\n                // XA-7", "            else if not skipRef and not na(pQty)\n")
    cur_ord = block(S10, "            else if not skipRef and not na(pQty)\n", "    stPrev := cur")
    check("XZ-02 one shared prep for every mode: block (4) takes each mode's own source (A: cur / D: dSrc / B, C: stPrev), scoring, "
          "priority, used-Track and Both handling; ref = stModeA ? pL : close; skipRef / tpRef / pQty are computed from that ref "
          "before the branch; the SATS prep stores P0 = ref, SL0 = pSL, TP0 = tpRef and places no order (the A limit order exists "
          "only in the Current branch); no stModeC / mode test in the SATS prep or waiting code",
          "array<StCand> src = stModeA ? cur : stModeD ? dSrc : stPrev" in blk4 and "float  ref = stModeA ? pL : close" in blk4
          and "[skipRef, tpRef] = f_stTp(side, ref, pSL" in blk4 and "float  pQty = f_stQty(side, ref, pSL)" in blk4
          and blk4.index("float  pQty") < blk4.index("            if stSats\n") and "strategy." not in prep
          and "pwP0     := ref" in prep and "limit = oL" in cur_ord and not re.search(r"stMode[ABCD]", prep)
          and not re.search(r"stMode[ABCD]", block(S10, "    // (3b) XA-7 / XA-9 SATS Pullback", "    // (4) 新規 Entry")))
    d = block(S10, "    // (2d) D:", "    // (3) 保留中の指値")
    check("XZ-03 D: dSrc (the D candidates of block (4)) is filled only by the existing 1M BOS step (2d), so the SATS prep for D "
          "happens only after the BOS; B: the candle pattern term applies only to C ((not stModeC or pattern)), so B gets no C "
          "condition; Current A-D code unchanged (strip exact)",
          "array.push(dSrc, x.c)" in d and S10.count("array.push(dSrc,") == 1
          and "(not stModeC or (c.side == 1 ? stPatL : stPatS))" in blk4)
    a_s = prep_model("A", -1, 2604.0, 2600.0, 2600.0, 2590.0)
    a_l = prep_model("A", 1, 2611.0, 2610.0, 2610.0, 2600.0)
    b_s = prep_model("B", -1, 2588.0, None, 2600.0, 2590.0, pattern_ok=False)
    c_s = prep_model("C", -1, 2588.0, None, 2600.0, 2590.0, pattern_ok=False)
    d_s0 = prep_model("D", -1, 2588.0, None, 2600.0, 2590.0, bos_done=False)
    d_s1 = prep_model("D", 1, 2612.0, None, 2610.0, 2600.0, bos_done=True)
    check("XZ-04 model: A prepares with P0 = the limit price (Short 2600, Long 2610; Current would place a limit, SATS places none); "
          "B prepares without a candle pattern (C would not); D prepares only after the BOS; SL0 = zone far edge +/- 1.5, TP0 = "
          "P0 +/- 1.5 x risk; Long and Short",
          a_s["ref"] == 2600.0 and a_s["sl0"] == 2601.5 and abs(a_s["tp0"] - (2600.0 - 1.5 * 1.5)) < 1e-9 and a_s["current_order"] == "limit"
          and a_l["ref"] == 2610.0 and a_l["sl0"] == 2598.5 and b_s is not None and b_s["ref"] == 2588.0 and c_s is None
          and d_s0 is None and d_s1["ref"] == 2612.0)
    seqs = []
    for p in (a_s, b_s, d_s1):
        side = -1 if p["sl0"] > p["ref"] else 1
        w = Wait9(side, p["ref"], p["sl0"], p["tp0"])
        seqs.append(type(w).__name__ == "Wait9" and w.state == 1 and w.touched is False)
    check("XZ-05 every mode hands the same waiting machine (XA-9: single wait, limit / SL0 cancels only, touch / rebound A or B, "
          "t-1 lines, no order on the prep bar, P0 / SL0 / TP0 fixed) its P0 / SL0 / TP0; one waiting / rebound / cancel / RR code "
          "path (no per-mode copy)", all(seqs) and S10.count("    if stSats and pwState == 1 and bar_index > pwBar\n") == 1
          and S10.count("pwState  := 1") == 1 and S10.count("f_satRR(") == 3)
    m = S10.replace("                    pwP0     := ref\n", "                    pwP0     := close\n")
    check("XZ-06 mutation: P0 = close for every mode (A losing its limit price) does not strip back to 3ca1837",
          m != S10 and xb.strip_strategy10(m) != S9)


# ---- XA-11: SATS comparison switches (order-bar body / near approach as the touch) --------------------------------------
class Wait11(Wait9):
    """port of the XA-11 waiting step: XA-9 plus body (1) and near (2). o = the bar's open. variants mirror wrong builds."""

    def __init__(self, side, p0, sl0, tp0, body=False, near=False, dist=3.0, **kw):
        super().__init__(side, p0, sl0, tp0, **kw)
        self.body, self.near, self.dist = body, near, dist

    def step(self, bar, t_close, h, l, c, pc, lines, o=None, sess=True, qty_ok=True, o_state=0):
        if self.state != 1 or bar <= self.bar:
            return None
        why = 0
        if t_close - self.t_end >= self.limit * 60000:
            why = -1
        elif (l <= self.sl0) if self.side == 1 else (h >= self.sl0):
            why = -4
        if why:
            self.state = 0
            self.n_exp += why == -1
            self.n_sl += why == -4
            self.touched, self.tk, self.tbar = False, 0, None
            return why
        if not self.touched:
            k, L = pick(self.side, self.p0, self.sl0, pc, lines)
        else:
            k, L = self.tk, lines[self.tk - 1]
        in_range = k != 0 and L is not None and ((self.sl0 < L < self.p0) if self.side == 1 else (self.p0 < L < self.sl0))
        hit = in_range and l <= L <= h
        d = self.dist
        if self.variant == "near_strict":
            near = self.near and in_range and ((l > L and l - L < d) if self.side == 1 else (h < L and L - h < d))
        elif self.variant == "near_close":
            near = self.near and in_range and ((c > L and c - L <= d) if self.side == 1 else (c < L and L - c <= d))
        else:
            near = self.near and in_range and ((l > L and l - L <= d) if self.side == 1 else (h < L and L - h <= d))
        touch = hit or near
        Lc = L
        if self.variant == "shift_close" and self.near and in_range:
            Lc = L + d if self.side == 1 else L - d
        reb_a = touch and ((c > Lc) if self.side == 1 else (c < Lc))
        reb_b = self.touched and in_range and ((pc <= Lc and c > Lc) if self.side == 1 else (pc >= Lc and c < Lc))
        body_ok = (not self.body) or ((c > o) if self.side == 1 else (c < o))
        if self.variant == "body_on_touch" and not body_ok:
            touch = False
        if touch and not self.touched:
            self.touched, self.tk, self.tbar = True, k, bar
            self.n_touch_prep += 1
        if self.variant == "stored_rebound":
            self.seen_reb = getattr(self, "seen_reb", False) or reb_a or reb_b
            reb_a, reb_b = reb_a or self.seen_reb, reb_b
        price_ok = (self.sl0 < c < self.p0) if self.side == 1 else (self.p0 < c < self.sl0)
        if (reb_a or reb_b) and body_ok and price_ok and sess and o_state == 0 and qty_ok:
            self.state = 0
            self.orders.append(dict(bar=bar, ref=c, kind="A" if reb_a else "B", line=k, L=L))
            self.n_same += reb_a
            self.n_later += not reb_a
            self.touched, self.tk, self.tbar = False, 0, None
            return 2
        return 0


def gate_xa11():
    S11, S10 = xb.strip_strategy12(rd(xb.STR_PATH)) or "", xb.show("ae2c2e8", xb.STR_PATH)   # XA-11 layer (XA-12 reverted exactly)
    ch = es.changed_code(S10, S11)
    code = sorted(l for l in ch if l and not l.startswith('"') and not l.startswith("tooltip"))
    iv = input_values(S11)
    check("XY-01 XA-11: Strategy == xa_build.build_strategy() (XA-1 .. XA-11); strip_strategy11 gives ae2c2e8 byte for byte "
          "(strip_strategy10 gives 3ca1837); code changes = 3 inputs, touchNow -> touchHit or touchNear, bodyOK in the order "
          "condition, the A-counter plot title; new inputs default OFF / OFF / 3.0 (min 0, step 0.5); every older default kept",
          xb.build_strategy11() == S11 and xb.strip_strategy11(S11) == S10 and xb.build_strategy10() == S10
          and xb.strip_strategy10(S11) == xb.show("3ca1837", xb.STR_PATH)
          and code == sorted([
              "bool touchNow = inRange and low <= lp and lp <= high",
              "bool touchHit  = inRange and low <= lp and lp <= high",
              "bool touchNear = stSatsNear and inRange and (pwSide == 1 ? (low > lp and low - lp <= stSatsNearD) : (high < lp and lp - high <= stSatsNearD))",
              "bool touchNow  = touchHit or touchNear",
              "if (rebA or rebB) and priceOK and stSessOK and oState == 0",
              "bool bodyOK  = not stSatsBody or (pwSide == 1 ? close > open : close < open)",
              "if (rebA or rebB) and bodyOK and priceOK and stSessOK and oState == 0",
              'stSatsBody = input.bool(false, "SATS · 反発確認足の陽線／陰線を要求", group = G_STW,',
              'stSatsNear = input.bool(false, "SATS · 近接を接触扱い", group = G_STW,',
              'stSatsNearD = input.float(3.0, "SATS · 近接許容距離 ($)", minval = 0.0, step = 0.5, group = G_STW,',
              'plot(stSats ? pwNOrdSame : na,             "SATS · 発注 (同じ足の接触・反発)", display = display.data_window)',
              'plot(stSats ? pwNOrdSame : na,             "SATS · 発注 (同じ足の接触・反発。近接 ON は近接の同一足反発を含む)", display = display.data_window)',
              "var int   pwNOrdSame   = 0     // XA-9: 同じ足の接触・反発 (A) で発注した件数",
              "var int   pwNOrdSame   = 0     // XA-9: 同じ足の接触・反発 (A) で発注した件数 (XA-11: 近接 ON では近接を接触扱いにした同一足反発を含む)"])
          and iv["stSatsBody"] == "false" and iv["stSatsNear"] == "false" and iv["stSatsNearD"] == "3.0"
          and all(iv[k] == v for k, v in input_values(S10).items()), "\n".join(code))
    wb = block(S11, "    // (3b) XA-7 / XA-9 SATS Pullback", "    // (4) 新規 Entry")
    outside = S11.replace(wb, "")
    rec = block(S11, "            if touchNow and not pwTouched\n", "            bool priceOK")
    check("XY-02 scope: stSatsBody / stSatsNear / stSatsNearD are read only inside the SATS waiting block (3b) (Current A-D, the "
          "shared prep (4), fills, TP / BE untouched); both OFF: touchNear needs stSatsNear, bodyOK = not stSatsBody or ... -> the "
          "XA-10 conditions; one touch flag (touchNow) feeds rebound A and the single touch record; bodyOK is not in the touch "
          "record and is ANDed in the same if as this bar's rebA / rebB (no var / stored rebound); no mode test in the block; "
          "the A counter comment states that it includes the near same-bar rebound",
          all(outside.count(k) == 1 for k in ("stSatsBody =", "stSatsNear =", "stSatsNearD ="))
          and "stSatsBody" not in outside.replace("stSatsBody =", "") and "stSatsNear" not in outside.replace("stSatsNear =", "").replace("stSatsNearD =", "")
          and wb.count("stSatsBody") == 1 and wb.count("stSatsNear ") == 1 and wb.count("stSatsNearD") == 2
          and "bool rebA     = touchNow and" in wb and "bodyOK" not in rec and "touchNear" not in rec
          and "if touchNow and not pwTouched" in wb and not re.search(r"\bvar\b|varip", wb) and not re.search(r"stMode[ABCD]", wb)
          and "if (rebA or rebB) and bodyOK and priceOK and stSessOK and oState == 0" in wb
          and "近接 ON では近接を接触扱いにした同一足反発を含む" in S11)

    # both OFF == XA-9 / XA-10 machine on random paths (Long and Short)
    random.seed(1101)
    same = True
    for side in (1, -1):
        for _ in range(300):
            p0, sl0 = (2600.0, 2580.0) if side == 1 else (2600.0, 2620.0)
            a, b = Wait9(side, p0, sl0, 0.0), Wait11(side, p0, sl0, 0.0)
            pc = p0
            for i in range(1, 40):
                c = round(pc + random.uniform(-4, 4), 1)
                h, l = c + round(random.uniform(0, 3), 1), c - round(random.uniform(0, 3), 1)
                lines = tuple(None if random.random() < 0.1 else round(c + random.uniform(-6, 6), 1) for _ in range(3))
                ra = a.step(10 + i, tb(i), h, l, c, pc, lines)
                rb = b.step(10 + i, tb(i), h, l, c, pc, lines, o=round(c + random.uniform(-2, 2), 1))
                same &= ra == rb and a.touched == b.touched and a.tk == b.tk
                pc = c
            same &= a.orders == b.orders and (a.n_same, a.n_later, a.n_touch_prep) == (b.n_same, b.n_later, b.n_touch_prep)
    check("XY-03 model: both OFF gives the XA-9 / XA-10 waiting result bar for bar (events, touch record, orders, A / B counters) "
          "on 600 random Long / Short paths", same)

    # (1) body: Short (P0 2600, SL0 2620, line 2610)
    w = Wait11(-1, 2600.0, 2620.0, 2570.0, body=True)
    r1 = w.step(11, tb(1), 2611, 2607, 2605, 2606.0, (2610.0, None, None), o=2604)     # touch + close back, bullish -> no
    t1 = (w.state, w.touched, w.tk)
    r2 = w.step(12, tb(2), 2609, 2604, 2605, 2605.0, (2610.0, None, None), o=2605)     # doji, no new A / B -> no
    r3 = w.step(13, tb(3), 2608, 2603, 2604, 2605.0, (2610.0, None, None), o=2607)     # bearish, but no new A / B -> no
    r4 = w.step(14, tb(4), 2612, 2606, 2609, 2604.0, (2610.0, None, None), o=2608)     # touch + close back (A), bullish -> no
    r5 = w.step(15, tb(5), 2612, 2606, 2609, 2609.0, (2610.0, None, None), o=2611)     # A again with a bearish bar -> order
    wd = Wait11(-1, 2600.0, 2620.0, 2570.0, body=True)
    d1 = wd.step(11, tb(1), 2611, 2607, 2605, 2606.0, (2610.0, None, None), o=2605)    # doji on rebound A -> no
    dt = wd.touched
    d2 = wd.step(12, tb(2), 2611, 2606, 2611, 2605.0, (2610.0, None, None), o=2606)    # back above
    d3 = wd.step(13, tb(3), 2609.8, 2607, 2608, 2611.0, (2610.0, None, None), o=2609.5)  # gap: B (2611 >= L, 2608 < L) + bearish -> order
    wl = Wait11(1, 2600.0, 2580.0, 2630.0, body=True)
    l1 = wl.step(11, tb(1), 2593, 2589, 2591, 2594.0, (2590.0, None, None), o=2592)    # Long touch + close back, bearish -> no
    lt = wl.touched
    l2 = wl.step(12, tb(2), 2593, 2591, 2591, 2591.0, (2590.0, None, None), o=2590.5)  # bullish but no new A / B -> no
    l3 = wl.step(13, tb(3), 2592, 2588, 2592, 2591.0, (2590.0, None, None), o=2591)    # touch + close back + bullish -> order
    check("XY-04 model (1) ON: rebound A with an opposite or doji bar places no order, the wait and the touch record stay; later "
          "bars that only have the right body colour (no new A / B) do not order; a later bar with A or B and the right body "
          "orders (Short A, Short B, Long A); the touch record itself is not limited by the body",
          r1 == 0 and t1 == (1, True, 1) and r2 == 0 and r3 == 0 and r4 == 0 and r5 == 2 and w.orders[0]["kind"] == "A"
          and d1 == 0 and dt and d2 == 0 and d3 == 2 and wd.orders[0]["kind"] == "B"
          and l1 == 0 and lt and l2 == 0 and l3 == 2, str((r1, t1, r2, r3, r4, r5, d1, d2, d3, l1, l2, l3)))

    # (2) near: Short line 2610, high 2607 -> L - high = 3.0
    def near_case(h, l, c, near=True, dist=3.0, side=-1, L=2610.0):
        if side == -1:
            x = Wait11(-1, 2600.0, 2620.0, 2570.0, near=near, dist=dist)
        else:
            x = Wait11(1, 2600.0, 2580.0, 2630.0, near=near, dist=dist)
        r = x.step(11, tb(1), h, l, c, 2605.0 if side == -1 else 2595.0, (L, None, None))
        return r, x.touched
    s_in, s_eq, s_out = near_case(2608.0, 2604, 2605), near_case(2607.0, 2604, 2605), near_case(2606.5, 2604, 2605)
    s_hit, s_d0, s_off = near_case(2611.0, 2604, 2605), near_case(2607.0, 2604, 2605, dist=0.0), near_case(2608.0, 2604, 2605, near=False)
    s_d0hit = near_case(2610.0, 2604, 2605, dist=0.0)
    l_in = near_case(2596, 2592.0, 2595, side=1, L=2590.0)
    l_eq = near_case(2596, 2593.0, 2595, side=1, L=2590.0)
    l_out = near_case(2596, 2593.5, 2595, side=1, L=2590.0)
    l_off = near_case(2596, 2592.0, 2595, side=1, L=2590.0, near=False)
    check("XY-05 model (2): Short / Long within the distance, at the boundary (== 3.0) touch and rebound on the same bar; beyond "
          "it no touch; a real touch still counts; distance 0 = real touch only (high == L still a real touch); OFF: a near "
          "approach alone is not a touch",
          s_in == (2, False) and s_eq == (2, False) and s_out == (0, False) and s_hit == (2, False) and s_d0 == (0, False)
          and s_d0hit == (2, False) and s_off == (0, False) and l_in == (2, False) and l_eq == (2, False) and l_out == (0, False)
          and l_off == (0, False), str((s_in, s_eq, s_out, s_hit, s_d0, s_d0hit, l_in, l_eq, l_out, l_off)))

    # near touch with price window failing (close <= P0), then a later bar B; the line kind is fixed and follows
    v = Wait11(-1, 2600.0, 2620.0, 2570.0, near=True)
    v1 = v.step(11, tb(1), 2608.0, 2598, 2599, 2605.0, (2610.0, 2604.0, None))        # near on L1? nearest is L2 2604 (hit) -> real
    v = Wait11(-1, 2600.0, 2620.0, 2570.0, near=True)
    n1 = v.step(11, tb(1), 2608.0, 2598, 2599, 2605.0, (2610.0, None, None))          # near L1, close 2599 <= P0 -> no order
    k1 = (v.touched, v.tk)
    n2 = v.step(12, tb(2), 2614, 2601, 2613, 2599.0, (2612.0, 2605.0, None))          # back above; keeps L1 (now 2612)
    n3 = v.step(13, tb(3), 2608.8, 2606, 2607, 2613.0, (2612.0, 2606.0, None))        # gap, 3.2 $ under L: B (2613 >= 2612, 2607 < 2612)
    lm = Wait11(-1, 2600.0, 2620.0, 2570.0, near=True)
    lm.step(11, tb(1), 2608.0, 2598, 2599, 2605.0, (2610.0, None, None))
    m2 = lm.step(12, tb(2), 2612, 2611, 2611.5, 2599.0, (2610.0, None, None))         # gap above L: no touch, no rebound
    m3 = lm.step(13, tb(3), 2612.5, 2610.5, 2611, 2611.5, (2616.5, None, None))       # line moved above both closes (4 $ away): not B
    na_ = Wait11(-1, 2600.0, 2620.0, 2570.0, near=True)
    na_.step(11, tb(1), 2608.0, 2598, 2599, 2605.0, (2610.0, None, None))
    q1 = na_.step(12, tb(2), 2611, 2602, 2611, 2599.0, (None, None, None))            # L1 na -> no order, touch kept
    q2 = na_.step(13, tb(3), 2611, 2602, 2605, 2611.0, (2621.0, None, None))          # out of range -> no order, touch kept
    qt = na_.touched
    q3 = na_.step(14, tb(4), 2611, 2602, 2605, 2611.0, (2610.0, None, None))          # B -> order
    c1 = Wait11(-1, 2600.0, 2620.0, 2570.0, near=True)
    cc = c1.step(11, tb(1), 2620.0, 2604, 2605, 2605.0, (2618.0, None, None))         # SL0 reached on a near / touch bar -> cancel
    check("XY-06 model (2): a near approach on the same bar with the close back orders (A, counted in the A counter); a near "
          "touch that cannot order yet is recorded (kind fixed), a later bar orders only by B (previous close and close across "
          "the same followed t-1 line), not by the line moving; na / out-of-range bars keep the touch; SL0 cancel before the "
          "rebound; one order and one touch count per wait",
          s_in[0] == 2 and n1 == 0 and k1 == (True, 1) and n2 == 0 and n3 == 2 and v.orders[0]["kind"] == "B"
          and v.orders[0]["L"] == 2612.0 and v.n_touch_prep == 1 and v.n_later == 1 and v.state == 0
          and m2 == 0 and m3 == 0 and lm.state == 1 and q1 == 0 and q2 == 0 and qt and q3 == 2
          and cc == -4 and not c1.orders and v1 == 0, str((v1, n1, k1, n2, n3, m2, m3, q1, q2, q3, cc)))

    bo = Wait11(-1, 2600.0, 2620.0, 2570.0, body=True, near=True)
    b1 = bo.step(11, tb(1), 2608.0, 2604, 2605, 2605.0, (2610.0, None, None), o=2604)   # near + close back, bullish -> no
    b2 = bo.step(12, tb(2), 2608.0, 2604, 2599.5, 2605.0, (2610.0, None, None), o=2606) # bearish, close <= P0 -> no
    b3 = bo.step(13, tb(3), 2606.5, 2601, 2602, 2599.5, (2610.0, None, None), o=2603)   # touched already, no B (pc < L) -> no
    b4 = bo.step(14, tb(4), 2612, 2604, 2611, 2602.0, (2610.0, None, None), o=2605)     # above L
    b5 = bo.step(15, tb(5), 2612, 2604, 2606, 2611.0, (2610.0, None, None), o=2606)     # B, doji -> no
    b6 = bo.step(16, tb(6), 2607.5, 2603, 2604, 2606.0, (2610.0, None, None), o=2606)   # near + A + bearish -> order
    check("XY-07 model (1) + (2) both ON: every condition is still needed (near touch, close back to the original L, the body, "
          "P0 window); the touch recorded on a failing bar does not order later without a new A / B of the order bar",
          (b1, b2, b3, b4, b5, b6) == (0, 0, 0, 0, 0, 2) and bo.orders[0]["kind"] == "A", str((b1, b2, b3, b4, b5, b6)))

    def scen(var):
        res = []
        x = Wait11(-1, 2600.0, 2620.0, 2570.0, near=True, variant=var)
        res.append(x.step(11, tb(1), 2607.0, 2604, 2605, 2605.0, (2610.0, None, None)))   # boundary
        x = Wait11(-1, 2600.0, 2620.0, 2570.0, near=True, variant=var)
        res.append(x.step(11, tb(1), 2605.5, 2601, 2608.5, 2605.0, (2610.0, None, None)))  # far high, close near L
        x = Wait11(-1, 2600.0, 2620.0, 2570.0, near=True, body=True, variant=var)
        res.append(x.step(11, tb(1), 2611, 2607, 2605, 2606.0, (2610.0, None, None), o=2604))
        res.append(x.touched)
        res.append(x.step(12, tb(2), 2606, 2604, 2605, 2605.0, (2610.0, None, None), o=2606))   # right body, no new A / B
        x = Wait11(-1, 2600.0, 2620.0, 2570.0, near=True, variant=var)
        res.append(x.step(11, tb(1), 2612, 2606, 2608, 2605.0, (2610.0, None, None)))      # real touch, close 2608 < L
        return res
    base = scen(None)
    vs = {v_: scen(v_) for v_ in ("near_strict", "near_close", "shift_close", "body_on_touch", "stored_rebound")}
    pm = [S11.replace("low - lp <= stSatsNearD", "low - lp < stSatsNearD"),
          S11.replace("lp - high <= stSatsNearD", "lp - close <= stSatsNearD"),
          S11.replace("bool touchNow  = touchHit or touchNear", "bool touchNow  = touchHit or touchNear and bodyOK"),
          S11.replace("            bool bodyOK  = not stSatsBody or (pwSide == 1 ? close > open : close < open)\n", "")
                .replace("if (rebA or rebB) and bodyOK and", "if (rebA or rebB) and"),
          S11.replace("bool touchNear = stSatsNear and inRange and", "bool touchNear = inRange and"),
          S11.replace("close > open : close < open", "close >= open : close <= open")]
    check("XY-08 mutations: strict boundary, near measured from the close, rebound level shifted by the distance, the body "
          "limiting the touch record, a stored rebound are each caught by the model scenarios; the matching Pine edits (and "
          "near without its switch, a doji allowed, body removed) do not strip back to ae2c2e8",
          all(vs[k] != base for k in vs) and all(m != S11 and xb.strip_strategy11(m) is None for m in pm),
          str((base, vs)))


# ---- XA-12: Gold adopted defaults ------------------------------------------------------------------------------------------
def gate_xa12():
    P = "d64258b"
    S12, V12 = xb.strip_strategy13(rd(xb.STR_PATH)) or "", rd(xb.VIS_PATH)   # Strategy: XA-12 layer (XA-13 reverted exactly)
    S11, V11 = xb.show(P, xb.STR_PATH), xb.show(P, xb.VIS_PATH)
    check("XK-01 XA-12: Strategy / Visual == xa_build.build_strategy() / build_visual(); strip_strategy12 / strip_visual7 give the "
          "d64258b files byte for byte; the Engine (and its import) unchanged",
          xb.build_strategy12() == S12 and xb.build_visual() == V12 and xb.strip_strategy12(S12) == S11
          and xb.strip_visual7(V12) == V11 and xb.build_strategy11() == S11 and xb.build_visual6() == V11
          and rd(xb.ENG_PATH) == xb.show(P, xb.ENG_PATH)
          and "import sekine3310/ZoneEnginePracticalXAUUSD/2 as zn" in S12 and "import sekine3310/ZoneEnginePracticalXAUUSD/2 as zn" in V12)
    s12, s11, v12, v11 = input_values(S12), input_values(S11), input_values(V12), input_values(V11)
    ds = {k: (s11.get(k), s12.get(k)) for k in set(s11) | set(s12) if s11.get(k) != s12.get(k)}
    dv = {k: (v11.get(k), v12.get(k)) for k in set(v11) | set(v12) if v11.get(k) != v12.get(k)}
    check("XK-02 defaults: Strategy changes exactly Entry Timing Current -> SATS Pullback, Role Reversal Confirmed Break -> "
          "Retest Confirmed, SATS body false -> true, SATS near false -> true, near distance 3.0 -> 1.0; Visual exactly Role "
          "Reversal (no SATS input added to the Visual); every shared Zone input equal in both files",
          ds == {"stTiming": ('"Current"', '"SATS Pullback"'), "roleMode": ('"Confirmed Break"', '"Retest Confirmed"'),
                 "stSatsBody": ("false", "true"), "stSatsNear": ("false", "true"), "stSatsNearD": ("3.0", "1.0")}
          and dv == {"roleMode": ('"Confirmed Break"', '"Retest Confirmed"')} and not any(k.startswith("stSats") for k in v12)
          and all(s12[k] == v12[k] for k in s12 if k in v12) and len([k for k in s12 if k in v12]) > 50, str((ds, dv)))
    cs = sorted(l for l in es.changed_code(S11, S12) if l and not l.startswith('"') and not l.startswith("tooltip"))
    cv = sorted(l for l in es.changed_code(V11, V12) if l and not l.startswith('"') and not l.startswith("tooltip"))
    role = ['roleMode = input.string("Confirmed Break", "Role Reversal Mode", options = ["Retest Confirmed", "Confirmed Break"], group = G_BF,',
            'roleMode = input.string("Retest Confirmed", "Role Reversal Mode", options = ["Retest Confirmed", "Confirmed Break"], group = G_BF,']
    check("XK-03 only defaults and text: the changed code lines are the five input declarations' first lines (the rest are "
          "tooltip strings / comments); no calculation, order path, SATS formula, quantity, TP / BE or alert line changes; every "
          "option kept (Current / Confirmed Break / OFF selectable)",
          cs == sorted(role + [
              'stTiming = input.string("Current", "Entry Timing", options = ["Current", "SATS Pullback"], group = G_STW,',
              'stTiming = input.string("SATS Pullback", "Entry Timing", options = ["Current", "SATS Pullback"], group = G_STW,',
              'stSatsBody = input.bool(false, "SATS · 反発確認足の陽線／陰線を要求", group = G_STW,',
              'stSatsBody = input.bool(true, "SATS · 反発確認足の陽線／陰線を要求", group = G_STW,',
              'stSatsNear = input.bool(false, "SATS · 近接を接触扱い", group = G_STW,',
              'stSatsNear = input.bool(true, "SATS · 近接を接触扱い", group = G_STW,',
              'stSatsNearD = input.float(3.0, "SATS · 近接許容距離 ($)", minval = 0.0, step = 0.5, group = G_STW,',
              'stSatsNearD = input.float(1.0, "SATS · 近接許容距離 ($)", minval = 0.0, step = 0.5, group = G_STW,'])
          and cv == sorted(role) and {k for k, _, _ in xb.STRATEGY_EDITS12} == {"header", "text", "default"}
          and {k for k, _, _ in xb.VISUAL_EDITS7} == {"header", "text", "default"}, "\n".join(cs + ["--"] + cv))
    keep = {"stMode": '"C: Candle Pattern"', "stDir": '"Short Only"', "stSatsWait": "240", "stBuffer": "1.5", "stTpZone": "false",
            "stRR": "1.5", "stBE": "true", "stBEDist": "15.0", "stCapBase": "300000.0", "stRiskPct": "3.0"}
    check("XK-04 kept: Entry C, Short Only, SATS wait 240, SL Buffer 1.5, opposite-zone TP OFF, RR 1.5, BE ON / 15, 300,000 JPY "
          "capital / 300,000 x 3 % budget; the tooltips no longer call Current / Confirmed Break / OFF / 3 the default and say "
          "'Gold Short の比較から採用した初期値。検証継続中'",
          all(s12[k] == v for k, v in keep.items()) and "initial_capital        = 300000," in S12 and "currency.JPY" in S12
          and all(x not in S12 + V12 for x in ("Current (初期)", "Confirmed Break (初期)", "比較用 (初期 OFF)", "(初期 Confirmed Break。",
                                               "(初期 Current ="))
          and S12.count("Gold Short の比較から採用した初期値。検証継続中") == 6 and V12.count("Gold Short の比較から採用した初期値。検証継続中") == 2
          and "Retest Confirmed (初期)" in S12 and "Retest Confirmed (初期)" in V12)


# ---- XA-13: SATS all-selected-timeframes opposite-band filter ------------------------------------------------------------
TFS13 = ("D", "4", "1", "15", "5")


def skip13(sel, states, want):
    """port of f_satAllAgainst: sel / states keyed by TFS13; states 1 / -1 / 0 / None (na)."""
    any_sel, all_hit = False, True
    for k in TFS13:
        if sel.get(k):
            any_sel = True
            all_hit = all_hit and states.get(k) is not None and states[k] == want
    return any_sel and all_hit


def spec13(sel, states, side):
    """the request: skip only when >= 1 timeframe is selected and every selected one shows the opposite band."""
    chosen = [k for k in TFS13 if sel.get(k)]
    opp = 1 if side == -1 else -1
    return bool(chosen) and all(states.get(k) == opp for k in chosen)


def sat_state(bars):
    """f_satBand stateV per bar (None = a line not computed), from the sat_series port."""
    out = []
    for (o, h, l, c, v), (l1, l2, sb, *_r) in zip(bars, sat_series(bars)):
        if l1 is None or l2 is None or sb is None:
            out.append(None)
        else:
            out.append(1 if (c > l1 and c > l2 and c > sb) else -1 if (c < l1 and c < l2 and c < sb) else 0)
    return out


def agg(bars, n):
    return [(g[0][0], max(x[1] for x in g), min(x[2] for x in g), g[-1][3], sum(x[4] for x in g))
            for g in (bars[i:i + n] for i in range(0, len(bars) - len(bars) % n, n))]


class Wait13(Wait11):
    """XA-11 waiting step plus the XA-13 skip: skip = this bar's all-selected opposite-band flag for the wait's side, ANDed
    (negated) into the final order condition only; everything before it (cancel, line, touch record) is the XA-11 step."""

    def step(self, bar, t_close, h, l, c, pc, lines, o=None, sess=True, qty_ok=True, o_state=0, skip=False):
        if self.state != 1 or bar <= self.bar:
            return None
        why = 0
        if t_close - self.t_end >= self.limit * 60000:
            why = -1
        elif (l <= self.sl0) if self.side == 1 else (h >= self.sl0):
            why = -4
        if why:
            self.state = 0
            self.n_exp += why == -1
            self.n_sl += why == -4
            self.touched, self.tk, self.tbar = False, 0, None
            return why
        if not self.touched:
            k, L = pick(self.side, self.p0, self.sl0, pc, lines)
        else:
            k, L = self.tk, lines[self.tk - 1]
        in_range = k != 0 and L is not None and ((self.sl0 < L < self.p0) if self.side == 1 else (self.p0 < L < self.sl0))
        hit = in_range and l <= L <= h
        near = self.near and in_range and ((l > L and l - L <= self.dist) if self.side == 1 else (h < L and L - h <= self.dist))
        touch = hit or near
        reb_a = touch and ((c > L) if self.side == 1 else (c < L))
        reb_b = self.touched and in_range and ((pc <= L and c > L) if self.side == 1 else (pc >= L and c < L))
        body_ok = (not self.body) or ((c > o) if self.side == 1 else (c < o))
        if touch and not self.touched:
            self.touched, self.tk, self.tbar = True, k, bar
            self.n_touch_prep += 1
        price_ok = (self.sl0 < c < self.p0) if self.side == 1 else (self.p0 < c < self.sl0)
        if (reb_a or reb_b) and body_ok and not skip and price_ok and sess and o_state == 0 and qty_ok:
            self.state = 0
            self.orders.append(dict(bar=bar, ref=c, kind="A" if reb_a else "B", line=k, L=L))
            self.n_same += reb_a
            self.n_later += not reb_a
            self.touched, self.tk, self.tbar = False, 0, None
            return 2
        return 0


def gate_xa13():
    S13, S12 = xb.strip_strategy14(rd(xb.STR_PATH)) or "", xb.show("f9fa0f9", xb.STR_PATH)   # XA-13 layer (XA-14 reverted exactly)
    i13, i12 = input_values(S13), input_values(S12)
    new = {k: v for k, v in i13.items() if k not in i12}
    cs = sorted(l for l in es.changed_code(S12, S13) if l and not l.startswith('"') and not l.startswith("tooltip"))
    check("XH-01 XA-13: Strategy == xa_build.build_strategy() (XA-1 .. XA-13); strip_strategy13 gives f9fa0f9 byte for byte; five "
          "new inputs (D / 4H / 1H / 15m / 5m) all default OFF; every older input default unchanged (adopted defaults kept); "
          "the only changed old line is the SATS order condition (+ mtfOK); Engine / Visual / other files unchanged",
          xb.build_strategy13() == S13 and xb.strip_strategy13(S13) == S12 and xb.build_strategy12() == S12
          and new == {"stSatsFD": "false", "stSatsF4": "false", "stSatsF1": "false", "stSatsF15": "false", "stSatsF5": "false"}
          and all(i13[k] == v for k, v in i12.items())
          and [l for l in cs if l in code_only(S12).split("\n") or l.strip() in [x.strip() for x in code_only(S12).split("\n")]]
              == ["if (rebA or rebB) and bodyOK and priceOK and stSessOK and oState == 0"]
          and not [p for p in os.listdir(ROOT) if p.endswith(".pine") and p != xb.STR_PATH and rd(p) != xb.show("f9fa0f9", p)],
          "\n".join(cs))
    reqs = re.findall(r'^int (satTf\w+)\s*= request\.security\(syminfo\.tickerid, "(\w+)",\s*f_satTfState\(\), lookahead = barmerge\.lookahead_on\)$',
                      S13, re.M)
    fts = func(S13, "f_satTfState() =>")
    fa = func(S13, "f_satAllAgainst(int want) =>")
    wb = block(S13, "    // (3b) XA-7 / XA-9 SATS Pullback", "    // (4) 新規 Entry")
    rec = block(S13, "            if touchNow and not pwTouched\n", "            bool priceOK")
    outside = S13.replace(wb, "")
    check("XH-02 static: D / 240 / 60 / 15 each request f_satTfState() (f_satBand stateV of that timeframe's own history, na when "
          "LINE1 / LINE2 / STB is na, value [1] + lookahead_on = the last confirmed bar) unconditionally at global scope (4 new "
          "requests, no duplicate); 5m = the existing satBand of the bar (lines na -> na); no line direction (dir1 / dir2 / "
          "stbDir) or colour used; f_satAllAgainst = AND over the selected timeframes only; satSkipS = all blue (1), satSkipL = "
          "all red (-1); mtfOK appears only in the SATS order condition (not in the prep / touch record / Current / cancel)",
          reqs == [("satTfD", "D"), ("satTf4", "240"), ("satTf1", "60"), ("satTf15", "15")]
          and S13.count("request.security(") == S12.count("request.security(") + 4 and S13.count("f_satTfState()") == 5
          and "[l1, l2, sb, d1, d2, sd, st, b, cm, at, a1, a2] = f_satBand()" in fts
          and "int s = (na(l1) or na(l2) or na(sb)) ? na : st" in fts and fts.rstrip().endswith("s[1]")
          and "int satTf5  = (na(satL1) or na(satL2) or na(satStb)) ? na : satBand\n" in S13
          and not re.search(r"\b(d1|d2|sd|satD1|satD2|satSD|color)\b", fa)
          and fa.count("anySel := true") == 5 and fa.count("allHit := allHit and not na(") == 5 and fa.rstrip().endswith("anySel and allHit")
          and "bool satSkipS = f_satAllAgainst(1)" in S13 and "bool satSkipL = f_satAllAgainst(-1)" in S13
          and S13.count("mtfOK") == 2 and wb.count("mtfOK") == 2 and "satSkip" not in rec and "mtfOK" not in outside
          and "if (rebA or rebB) and bodyOK and mtfOK and priceOK and stSessOK and oState == 0" in wb
          and not re.search(r"\bvar\b|varip", wb + fa) and code_only(S13).count("pwState  := 1") == 1)

    import itertools
    vals = (1, -1, 0, None)
    ok = True
    n = 0
    for sel_bits in itertools.product((False, True), repeat=5):
        sel = dict(zip(TFS13, sel_bits))
        for st in itertools.product(vals, repeat=5):
            states = dict(zip(TFS13, st))
            for side in (1, -1):
                want = -1 if side == 1 else 1
                ok &= skip13(sel, states, want) == spec13(sel, states, side)
                n += 1
    S, L = -1, 1
    cases = {
        "D+4H both blue -> Short skip": skip13({"D": 1, "4": 1}, {"D": 1, "4": 1, "1": -1, "15": -1, "5": -1}, 1),
        "D+4H one red": not skip13({"D": 1, "4": 1}, {"D": 1, "4": -1}, 1),
        "D+4H one unlit": not skip13({"D": 1, "4": 1}, {"D": 1, "4": 0}, 1),
        "D+4H one na": not skip13({"D": 1, "4": 1}, {"D": None, "4": 1}, 1),
        "all 5 blue": skip13(dict.fromkeys(TFS13, 1), dict.fromkeys(TFS13, 1), 1),
        "all 5, one red": not skip13(dict.fromkeys(TFS13, 1), {**dict.fromkeys(TFS13, 1), "15": -1}, 1),
        "1H alone": skip13({"1": 1}, {"D": -1, "4": 0, "1": 1, "15": None, "5": -1}, 1),
        "none selected": not skip13({}, dict.fromkeys(TFS13, 1), 1) and not skip13({}, dict.fromkeys(TFS13, -1), -1),
        "Long all red": skip13({"D": 1, "4": 1}, {"D": -1, "4": -1}, -1) and not skip13({"D": 1, "4": 1}, {"D": -1, "4": -1}, 1),
        "Long blue does not skip Long": not skip13({"D": 1, "4": 1}, {"D": 1, "4": 1}, -1),
    }
    check("XH-03 model: AND over the selected timeframes only, exhaustively (32 selections x 4^5 states x Long / Short = %d cases) "
          "equal to the request; D+4H both opposite / one mismatch / unlit / na, all five / one off, 1H alone, nothing selected, "
          "Long / Short symmetric" % n, ok and all(cases.values()), str([k for k, v in cases.items() if not v]))

    random.seed(1301)
    bars5, px = [], 2600.0
    for _ in range(3 * 400):
        o = px
        c = round(o + random.gauss(0, 2.0), 2)
        h, l = max(o, c) + abs(random.gauss(0, 1.0)), min(o, c) - abs(random.gauss(0, 1.0))
        bars5.append((o, h, l, c, random.randint(50, 150)))
        px = c
    s15 = sat_state(agg(bars5, 3))
    seen = [s15[i // 3 - 1] if i // 3 >= 1 else None for i in range(len(bars5))]     # [1] + lookahead_on on the 5m chart
    stable, changed = True, 0
    for k in (300, 350, 380):
        alt = list(bars5)
        for j in range(3 * k, 3 * k + 3):          # rewrite the forming 15m bar k
            o, h, l, c, v = alt[j]
            alt[j] = (o, h + 30, l - 30, c + (25 if j % 2 else -25), v)
        s15b = sat_state(agg(alt, 3))
        seen_b = [s15b[i // 3 - 1] if i // 3 >= 1 else None for i in range(len(alt))]
        stable &= all(seen_b[j] == seen[j] for j in range(0, 3 * k + 3))     # nothing seen up to the end of the forming bar changes
        changed += s15b[k] != s15[k] or s15b[k + 1:k + 4] != s15[k + 1:k + 4]   # the rewrite does change the 15m states themselves
    s5 = sat_state(bars5)
    sampled = [s5[3 * k + 2] for k in range(len(s15))]
    check("XH-04 model: a higher timeframe's state comes from SATS on its own bars (15m built from 5m bars differs from sampling "
          "the 5m state on %d of %d bars) and the 5m bars inside a forming 15m bar see only the previous confirmed 15m state "
          "([1] + lookahead_on): rewriting the forming bar changes nothing up to its end" % (sum(a != b for a, b in zip(sampled, s15)), len(s15)),
          stable and changed >= 1 and sum(a != b for a, b in zip(sampled[60:], s15[60:])) > 0 and s15.count(None) < 60, str(changed))

    def short13():
        return Wait13(-1, 2600.0, 2620.0, 2570.0, body=True, near=True, dist=1.0)
    w = short13()
    a1 = w.step(11, tb(1), 2611, 2607, 2605, 2606.0, (2610.0, None, None), o=2607, skip=True)    # A + bearish, but skipped
    snap = (w.state, w.touched, w.tk, w.p0, w.sl0, w.tp0, w.t_end, len(w.orders), w.n_same, w.n_later, w.n_touch_prep)
    a2 = w.step(12, tb(2), 2606, 2603, 2604, 2605.0, (2610.0, None, None), o=2605, skip=False)   # released, no new A / B
    a3 = w.step(13, tb(3), 2612, 2606, 2611, 2604.0, (2610.0, None, None), o=2608, skip=False)   # above L
    a4 = w.step(14, tb(4), 2608.5, 2605, 2606, 2611.0, (2610.0, None, None), o=2608, skip=False)   # gap, 1.5 $ under L: B + bearish -> order
    e = short13()
    e.step(11, tb(1), 2611, 2607, 2605, 2606.0, (2610.0, None, None), o=2607, skip=True)
    ev, i = [], 2
    while e.state == 1 and i < 200:
        ev.append(e.step(10 + i, tb(i), 2611, 2607, 2605, 2611.0 if i % 2 else 2605.0, (2610.0, None, None), o=2607, skip=True))
        i += 1
    ref = Wait11(-1, 2600.0, 2620.0, 2570.0, body=True, near=True, dist=1.0)
    ref.step(11, tb(1), 2611, 2607, 2605, 2606.0, (2610.0, None, None), o=2604)
    rv, j = [], 2
    while ref.state == 1 and j < 200:
        rv.append(ref.step(10 + j, tb(j), 2606, 2603, 2604, 2605.0, (2610.0, None, None), o=2605))
        j += 1
    c = short13()
    c.step(11, tb(1), 2611, 2607, 2605, 2606.0, (2610.0, None, None), o=2607, skip=True)
    cv = c.step(12, tb(2), 2620, 2604, 2605, 2605.0, (2610.0, None, None), o=2607, skip=True)    # SL0 reached -> cancel first
    lw = Wait13(1, 2600.0, 2580.0, 2630.0, body=True, near=True, dist=1.0)
    lv1 = lw.step(11, tb(1), 2593, 2589, 2592, 2594.0, (2590.0, None, None), o=2591, skip=True)
    lt1 = (lw.state, lw.touched, lw.tk)
    lv2 = lw.step(12, tb(2), 2593, 2591.5, 2592.5, 2592.0, (2590.0, None, None), o=2591.6, skip=False)   # 1.5 $ away, no new A / B
    lv3 = lw.step(13, tb(3), 2592, 2589, 2591.5, 2592.5, (2590.0, None, None), o=2590.5, skip=False)
    check("XH-05 model: a skipped bar (rebound A + body + price + session + qty all true) places no order and keeps the wait, the "
          "touch record and line kind, P0 / SL0 / TP0, the prep time and every counter; release alone does not order, a new "
          "rebound (B) does; skipping every bar expires on the same bar as the unfiltered wait (no extension); SL0 cancel "
          "comes first; Long symmetric; one order per wait",
          a1 == 0 and snap == (1, True, 1, 2600.0, 2620.0, 2570.0, T0 + 10 * M5, 0, 0, 0, 1) and a2 == 0 and a3 == 0 and a4 == 2
          and w.orders[0]["kind"] == "B" and len(w.orders) == 1 and ev[-1] == -1 and rv[-1] == -1 and len(ev) == len(rv)
          and not e.orders and cv == -4 and not c.orders and lv1 == 0 and lt1 == (1, True, 1) and lv2 == 0 and lv3 == 2,
          str((a1, snap, a2, a3, a4, len(ev), len(rv), ev[-1:], rv[-1:], cv, lv1, lv2, lv3)))

    random.seed(1302)
    same = True
    for side in (1, -1):
        for _ in range(300):
            p0, sl0 = (2600.0, 2580.0) if side == 1 else (2600.0, 2620.0)
            a, b = Wait11(side, p0, sl0, 0.0, body=True, near=True, dist=1.0), Wait13(side, p0, sl0, 0.0, body=True, near=True, dist=1.0)
            pc = p0
            for i in range(1, 40):
                cc = round(pc + random.uniform(-4, 4), 1)
                h, l = cc + round(random.uniform(0, 3), 1), cc - round(random.uniform(0, 3), 1)
                lines = tuple(None if random.random() < 0.1 else round(cc + random.uniform(-6, 6), 1) for _ in range(3))
                o = round(cc + random.uniform(-2, 2), 1)
                states = {k: random.choice((1, -1, 0, None)) for k in TFS13}
                sk = skip13({}, states, 1 if side == -1 else -1)
                ra = a.step(10 + i, tb(i), h, l, cc, pc, lines, o=o)
                rb = b.step(10 + i, tb(i), h, l, cc, pc, lines, o=o, skip=sk)
                same &= ra == rb and a.touched == b.touched and a.tk == b.tk
                pc = cc
            same &= a.orders == b.orders
    check("XH-06 model: all five OFF = no skip on 600 random Long / Short paths (bar for bar identical to the XA-12 wait, random "
          "timeframe states)", same)

    muts = [S13.replace("    anySel and allHit\n", "    anySel and (allHit or true)\n"),
            S13.replace("allHit := allHit and not na(satTf4) and satTf4 == want", "allHit := allHit or satTf4 == want"),
            S13.replace("allHit := allHit and not na(satTfD) and satTfD == want", "allHit := allHit and (na(satTfD) or satTfD == want)"),
            S13.replace('int satTf15 = request.security(syminfo.tickerid, "15",  f_satTfState(), lookahead = barmerge.lookahead_on)',
                        'int satTf15 = request.security(syminfo.tickerid, "15",  f_satTfState()[0], lookahead = barmerge.lookahead_on)'),
            S13.replace("    s[1]\n", "    s\n"),
            S13.replace("int s = (na(l1) or na(l2) or na(sb)) ? na : st", "int s = (na(l1) or na(l2) or na(sb)) ? na : d1"),
            S13.replace("bool satSkipS = f_satAllAgainst(1)", "bool satSkipS = f_satAllAgainst(-1)"),
            S13.replace("            if (rebA or rebB) and bodyOK and mtfOK and priceOK", "            if (rebA or rebB) and bodyOK and priceOK")]
    or_model = lambda sel, st, want: any(sel.get(k) and st.get(k) == want for k in TFS13)
    check("XH-07 mutations: OR / majority-style, a na counted as a match, the forming HTF bar (no [1]), a line direction instead "
          "of the band, swapped sides, filter dropped do not strip back to f9fa0f9; the OR model disagrees with the request",
          all(m != S13 and xb.strip_strategy13(m) is None for m in muts)
          and or_model({"D": 1, "4": 1}, {"D": 1, "4": -1}, 1) != spec13({"D": 1, "4": 1}, {"D": 1, "4": -1}, -1))


# ---- XA-14: adopted defaults of the XA-13 filter ----------------------------------------------------------------------------
def gate_xa14():
    S14, S13 = xb.strip_strategy15(rd(xb.STR_PATH)) or "", xb.show("e5bba44", xb.STR_PATH)   # XA-14 layer (XA-15 reverted exactly)
    i14, i13 = input_values(S14), input_values(S13)
    d = {k: (i13.get(k), i14.get(k)) for k in set(i13) | set(i14) if i13.get(k) != i14.get(k)}
    cs = sorted(l for l in es.changed_code(S13, S14) if l and not l.startswith('"') and not l.startswith("tooltip"))
    check("XJ-01 XA-14: Strategy == xa_build.build_strategy() (XA-1 .. XA-14); strip_strategy14 gives e5bba44 byte for byte "
          "(strip_strategy13 gives f9fa0f9); Engine / Visual / other Pine files unchanged",
          xb.build_strategy14() == S14 and xb.strip_strategy14(S14) == S13 and xb.build_strategy13() == S13
          and xb.strip_strategy13(S14) == xb.show("f9fa0f9", xb.STR_PATH)
          and not [p for p in os.listdir(ROOT) if p.endswith(".pine") and p != xb.STR_PATH and rd(p) != xb.show("e5bba44", p)])
    check("XJ-02 defaults: exactly 4H false -> true and 1H false -> true (D / 15m / 5m stay false, still inputs); every other "
          "default unchanged (SATS Pullback, Retest Confirmed, Entry C, Short Only, 240, body ON, near ON / 1.0, SL Buffer 1.5, "
          "opposite TP OFF, RR 1.5, BE ON / 15, 300,000 x 3 %)",
          d == {"stSatsF4": ("false", "true"), "stSatsF1": ("false", "true")}
          and (i14["stSatsFD"], i14["stSatsF15"], i14["stSatsF5"]) == ("false", "false", "false")
          and all(i14[k] == v for k, v in {"stTiming": '"SATS Pullback"', "roleMode": '"Retest Confirmed"', "stMode": '"C: Candle Pattern"',
                                            "stDir": '"Short Only"', "stSatsWait": "240", "stSatsBody": "true", "stSatsNear": "true",
                                            "stSatsNearD": "1.0", "stBuffer": "1.5", "stTpZone": "false", "stRR": "1.5", "stBE": "true",
                                            "stBEDist": "15.0", "stCapBase": "300000.0", "stRiskPct": "3.0"}.items())
          and "initial_capital        = 300000," in S14 and "currency.JPY" in S14, str(d))
    check("XJ-03 only defaults and text: the changed code lines are the two input declarations (the rest are the tooltip and "
          "comments); the AND logic, requests, f_satTfState, mtfOK placement and every calculation / order line are identical; "
          "the text says 'Gold Short の比較から採用した初期値・検証継続中' and no longer calls all five OFF the default",
          cs == sorted(['stSatsF4  = input.bool(false, "SATS 逆方向一致 · 4時間足を判定に使用", group = G_STW)',
                        'stSatsF4  = input.bool(true, "SATS 逆方向一致 · 4時間足を判定に使用", group = G_STW)',
                        'stSatsF1  = input.bool(false, "SATS 逆方向一致 · 1時間足を判定に使用", group = G_STW)',
                        'stSatsF1  = input.bool(true, "SATS 逆方向一致 · 1時間足を判定に使用", group = G_STW)'])
          and {k for k, _, _ in xb.STRATEGY_EDITS14} == {"header", "text", "default"}
          and func(S14, "f_satAllAgainst(int want) =>") == func(S13, "f_satAllAgainst(int want) =>")
          and func(S14, "f_satTfState() =>") == func(S13, "f_satTfState() =>")
          and S14.count("Gold Short の比較から採用した初期値・検証継続中") - S13.count("Gold Short の比較から採用した初期値・検証継続中") == 2 and "5 項目とも初期 OFF" not in S14
          and "全て初期 OFF = フィルターなし" not in S14, "\n".join(cs))
    sel = {"D": False, "4": True, "1": True, "15": False, "5": False}
    check("XJ-04 model at the new defaults: Short skipped only when 4H and 1H are both blue (D / 15m / 5m ignored), Long only "
          "when both red; one unlit / na / opposite -> no skip",
          skip13(sel, {"D": -1, "4": 1, "1": 1, "15": -1, "5": -1}, 1) and skip13(sel, {"D": 1, "4": -1, "1": -1, "15": 1, "5": 1}, -1)
          and not skip13(sel, {"4": 1, "1": 0}, 1) and not skip13(sel, {"4": None, "1": 1}, 1) and not skip13(sel, {"4": 1, "1": -1}, 1)
          and not skip13(sel, {"4": 1, "1": 1}, -1))


# ---- XA-15: Breakeven Trigger Mode ----------------------------------------------------------------------------------------
def be_trig(mode, side, fill, sl, tp, dist=15.0, r_mult=1.0, tp_ratio=0.5):
    """port of f_beTrig (None = na)."""
    r = side * (fill - sl) if fill is not None and sl is not None else None
    g = side * (tp - fill) if fill is not None and tp is not None else None
    if mode == "Risk Multiple":
        return r * r_mult if r is not None and r > 0 else None
    if mode == "TP Progress":
        return g * tp_ratio if g is not None and g > 0 else None
    return dist


def be_run(side, fill, sl, tp, bars, mode="Fixed Distance", on=True, limit_fill_bar=False, old=False, **kw):
    """port of block (2c) over the fill bar and later confirmed bars (o, h, l, c); returns (bar index of the move, stop)."""
    stop, moved = sl, None
    for i, (o, h, l, c) in enumerate(bars):
        if not on or moved is not None:
            continue
        fav = h if side == 1 else l
        if i == 0 and limit_fill_bar and fill != o:
            fav = c
        if old:
            hit = side * (fav - fill) >= kw.get("dist", 15.0)
        else:
            tg = be_trig(mode, side, fill, sl, tp, **kw)
            hit = tg is not None and side * (fav - fill) >= tg
        if hit:
            moved, stop = i, fill
    return moved, stop


def gate_xa15():
    S15, S14 = rd(xb.STR_PATH), xb.show("e2cf617", xb.STR_PATH)
    i15, i14 = input_values(S15), input_values(S14)
    new = {k: v for k, v in i15.items() if k not in i14}
    decl = input_decls(S15)
    cs = sorted(l for l in es.changed_code(S14, S15) if l and not l.startswith('"') and not l.startswith("tooltip"))
    check("XB-01 XA-15: Strategy == xa_build.build_strategy() (XA-1 .. XA-15); strip_strategy15 gives e2cf617 byte for byte; new "
          "inputs Breakeven Trigger Mode (Fixed Distance default; options Fixed Distance / Risk Multiple / TP Progress), R 1.0 "
          "(min 0.1, step 0.1), TP Ratio 0.5 (min 0.05, max 1.0, step 0.05); every older default unchanged (BE ON / 15, filter "
          "4H / 1H, SATS / Retest / C / Short Only / 240 / body / near 1.0 / SL 1.5 / opposite TP OFF / RR 1.5 / 300,000 x 3 %); "
          "Engine / Visual / other Pine files unchanged",
          xb.build_strategy() == S15 and xb.strip_strategy15(S15) == S14 and xb.build_strategy14() == S14
          and new == {"stBEMode": '"Fixed Distance"', "stBER": "1.0", "stBETp": "0.5"}
          and 'options = ["Fixed Distance", "Risk Multiple", "TP Progress"]' in decl["stBEMode"]
          and es.kw(decl["stBER"], "minval") == "0.1" and es.kw(decl["stBER"], "step") == "0.1"
          and es.kw(decl["stBETp"], "minval") == "0.05" and es.kw(decl["stBETp"], "maxval") == "1.0" and es.kw(decl["stBETp"], "step") == "0.05"
          and all(i15[k] == v for k, v in i14.items()) and i15["stBE"] == "true" and i15["stBEDist"] == "15.0"
          and not [p for p in os.listdir(ROOT) if p.endswith(".pine") and p != xb.STR_PATH and rd(p) != xb.show("e2cf617", p)])
    be14 = block(S14, "    if stBE and oState == 2 and not oBE\n", "    // (2d)")
    be15 = block(S15, "    if stBE and oState == 2 and not oBE\n", "    // (2d)")
    fb = func(S15, "f_beTrig(int side, float fillPx, float sl, float tp) =>")
    old_lines = [l for l in cs if l in [x.strip() for x in code_only(S14).split("\n")]]
    check("XB-02 static: the only changed old line is the trigger test (>= stBEDist -> not na(beTrig) and >= beTrig with beTrig = "
          "f_beTrig(oSide, oFill, oSL, oTP)); the breakeven block is otherwise identical (fav high / low, fav := close on the "
          "limit-fill bar, oBE once, stop := oFill, the same exit); f_beTrig: Fixed -> stBEDist (no distance check), Risk Multiple "
          "-> side x (fill - SL) x R only when > 0, TP Progress -> side x (TP - fill) x ratio only when > 0 (no stRR / TP price "
          "multiplication, no oStop / P0 / close); no new strategy.* call and no new oSL / oTP / oFill / qty assignment",
          old_lines == ["if oSide * (fav - oFill) >= stBEDist"]
          and be15.replace("        float beTrig = f_beTrig(oSide, oFill, oSL, oTP)\n        if not na(beTrig) and oSide * (fav - oFill) >= beTrig\n",
                           "        if oSide * (fav - oFill) >= stBEDist\n") == be14
          and "    float r  = side * (fillPx - sl)" in fb and "    float tg = side * (tp - fillPx)" in fb
          and '"Risk Multiple" ? (not na(r) and r > 0 ? r * stBER : na)' in fb and '"TP Progress" ? (not na(tg) and tg > 0 ? tg * stBETp : na) : stBEDist' in fb
          and not re.search(r"stRR|oStop|pwP0|close", fb) and fb.count("stBEDist") == 1 and fb.count("stBER") == 1 and fb.count("stBETp") == 1
          and len(re.findall(r"strategy\.(entry|exit|close|cancel)\(", code_only(S15))) == len(re.findall(r"strategy\.(entry|exit|close|cancel)\(", code_only(S14)))
          and all(code_only(S15).count(x) == code_only(S14).count(x) for x in ("oSL     :=", "oTP   :=", "oFill   :=", "oStop :=", "qty = "))
          and S15.count("f_beTrig(") == 4, "\n".join(cs))
    ex = {
        "Short 1R -> 2600": 2610 + -1 * be_trig("Risk Multiple", -1, 2610, 2620, 2570) == 2600,
        "Short 0.5TP -> 2590": 2610 + -1 * be_trig("TP Progress", -1, 2610, 2620, 2570) == 2590,
        "Short fixed 15 -> 2595": 2610 + -1 * be_trig("Fixed Distance", -1, 2610, 2620, 2570) == 2595,
        "Long 1R -> 2610": 2600 + be_trig("Risk Multiple", 1, 2600, 2590, 2630) == 2610,
        "Long 0.5TP -> 2615": 2600 + be_trig("TP Progress", 1, 2600, 2590, 2630) == 2615,
        "Long 1.5R -> 2615": 2600 + be_trig("Risk Multiple", 1, 2600, 2590, 2630, r_mult=1.5) == 2615,
        "Long 0.25TP -> 2607.5": 2600 + be_trig("TP Progress", 1, 2600, 2590, 2630, tp_ratio=0.25) == 2607.5,
        "gap fill (P0 2600, fill 2604 Short): 1R from the fill": be_trig("Risk Multiple", -1, 2604, 2620, 2570) == 16 and be_trig("TP Progress", -1, 2604, 2620, 2570) == 17,
        "na / 0 / negative -> na (new modes)": all(be_trig(m, -1, f, s, tp) is None for m, f, s, tp in
                                                   (("Risk Multiple", None, 2620, 2570), ("Risk Multiple", 2620, 2620, 2570), ("Risk Multiple", 2625, 2620, 2570),
                                                    ("TP Progress", 2610, 2620, None), ("TP Progress", 2570, 2620, 2570), ("TP Progress", 2560, 2620, 2570))),
        "fixed keeps 15 whatever the distances": be_trig("Fixed Distance", -1, 2625, 2620, 2630) == 15.0,
    }
    s_bars = [(2610, 2612, 2604, 2606), (2606, 2607, 2600.5, 2601), (2601, 2602, 2600, 2601), (2601, 2601, 2590, 2592)]
    eq = (be_run(-1, 2610, 2620, 2570, s_bars, "Risk Multiple"), be_run(-1, 2610, 2620, 2570, s_bars[:2], "Risk Multiple"),
          be_run(-1, 2610, 2620, 2570, s_bars, "TP Progress"), be_run(-1, 2610, 2620, 2570, s_bars, "Fixed Distance"))
    check("XB-03 model: the request examples (Short fill 2610 / SL 2620 / TP 2570: 1R 2600, 0.5TP 2590, fixed 2595; Long fill 2600 / "
          "SL 2590 / TP 2630: 1R 2610, 0.5TP 2615), 1.5R, 0.25TP, a gap fill (from the fill, not P0), na / 0 / negative base -> no "
          "move (fixed unchanged); the move happens on the bar that reaches the trigger exactly (low 2600 -> 1R), not before "
          "(2600.5); 0.5TP (2590) and fixed 15 (2595) move on the bar with low 2590; the stop becomes the fill",
          all(ex.values()) and eq[0] == (2, 2610) and eq[1] == (None, 2620) and eq[2] == (3, 2610) and eq[3] == (3, 2610),
          str(([k for k, v in ex.items() if not v], eq)))
    random.seed(1501)
    same_fixed = off_none = unsel = True
    for _ in range(2000):
        side = random.choice((1, -1))
        fill = round(2600 + random.uniform(-5, 5), 1)
        sl = fill - side * round(random.uniform(-2, 20), 1)
        tp = fill + side * round(random.uniform(-5, 50), 1)
        bars, px = [], fill
        for _ in range(12):
            o = px
            c = round(o + random.uniform(-6, 6), 1)
            bars.append((o, max(o, c) + round(random.uniform(0, 4), 1), min(o, c) - round(random.uniform(0, 4), 1), c))
            px = c
        lf = random.random() < 0.3
        dist = random.choice((5.0, 15.0, 0.0))
        same_fixed &= be_run(side, fill, sl, tp, bars, "Fixed Distance", limit_fill_bar=lf, dist=dist) == \
            be_run(side, fill, sl, tp, bars, old=True, limit_fill_bar=lf, dist=dist)
        off_none &= all(be_run(side, fill, sl, tp, bars, m, on=False) == (None, sl) for m in ("Fixed Distance", "Risk Multiple", "TP Progress"))
        unsel &= be_run(side, fill, sl, tp, bars, "Fixed Distance", r_mult=0.1, tp_ratio=0.05) == be_run(side, fill, sl, tp, bars, "Fixed Distance", r_mult=5, tp_ratio=1.0) \
            and be_run(side, fill, sl, tp, bars, "Risk Multiple", dist=0.0, tp_ratio=0.05) == be_run(side, fill, sl, tp, bars, "Risk Multiple", dist=99.0, tp_ratio=1.0) \
            and be_run(side, fill, sl, tp, bars, "TP Progress", dist=0.0, r_mult=0.1) == be_run(side, fill, sl, tp, bars, "TP Progress", dist=99.0, r_mult=5)
    mirror = all(be_run(1, 2600, 2590, 2630, [(o, h, l, c) for o, h, l, c in b], m) ==
                 be_run(-1, 2600, 2610, 2570, [(5200 - o, 5200 - l, 5200 - h, 5200 - c) for o, h, l, c in b], m)[0:1] + (2600,) and True
                 for m in ("Risk Multiple", "TP Progress", "Fixed Distance")
                 for b in ([(2600, 2605, 2598, 2604), (2604, 2610, 2603, 2609), (2609, 2616, 2608, 2615)],))
    check("XB-04 model: Fixed Distance == the previous rule on 2,000 random trades (Long / Short, limit-fill bar fav := close, "
          "distance 0 / 5 / 15, negative or odd base distances); BE OFF -> no mode moves; the inputs of the unselected modes do not "
          "change anything; Long / Short mirror",
          same_fixed and off_none and unsel and mirror, str((same_fixed, off_none, unsel, mirror)))
    zone_tp, rr_tp = 2585.0, 2610 - 1.5 * 10
    muts = [S15.replace("        float beTrig = f_beTrig(oSide, oFill, oSL, oTP)\n", "        float beTrig = f_beTrig(oSide, oFill, oStop, oTP)\n"),
            S15.replace("    float tg = side * (tp - fillPx)\n", "    float tg = side * (fillPx + side * stRR * (side * (fillPx - sl)) - fillPx)\n"),
            S15.replace("(not na(tg) and tg > 0 ? tg * stBETp : na)", "(not na(tp) ? tp * stBETp : na)"),
            S15.replace("if not na(beTrig) and oSide * (fav - oFill) >= beTrig", "if not na(beTrig) and oSide * (fav - oFill) > beTrig"),
            S15.replace("if not na(beTrig) and oSide * (fav - oFill) >= beTrig", "if not na(beTrig) and oSide * (close - oFill) >= beTrig"),
            S15.replace("        float beTrig = f_beTrig(oSide, oFill, oSL, oTP)\n", "        float beTrig = f_beTrig(oSide, pwP0, oSL, oTP)\n"),
            S15.replace('     stBEMode == "TP Progress" ? (not na(tg) and tg > 0 ? tg * stBETp : na) : stBEDist\n',
                        '     stBEMode == "TP Progress" ? (not na(tg) and tg > 0 ? tg * stBETp : na) : (r > 0 ? stBEDist : na)\n')]
    check("XB-05 TP Progress uses the TP actually set (a zone TP 2585 gives 12.5, the fixed-RR TP %.1f would give 7.5 — they differ), "
          "and the initial SL survives the move (after oStop = fill the 1R would be 0); mutations (oStop as the base, TP from stRR, "
          "TP price x ratio, strict >, close instead of high / low, P0 instead of the fill, a distance check on Fixed) do not strip "
          "back to e2cf617" % rr_tp,
          be_trig("TP Progress", -1, 2610, 2620, zone_tp) == 12.5 and be_trig("TP Progress", -1, 2610, 2620, rr_tp) == 7.5
          and be_trig("Risk Multiple", -1, 2610, 2610, 2570) is None and be_trig("Risk Multiple", -1, 2610, 2620, 2570) == 10
          and all(m != S15 and xb.strip_strategy15(m) is None for m in muts))


def main():
    for g in (gate_static, gate_model, gate_mutation, gate_xa8, gate_xa9, gate_xa10, gate_xa11, gate_xa12, gate_xa13, gate_xa14, gate_xa15):
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
