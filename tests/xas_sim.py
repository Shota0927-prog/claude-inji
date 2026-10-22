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
  (XW / XP / XQ run on the XA-7 layer, XV on the XA-8 layer: the Strategy with exactly the later edits reverted)

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
    S9, S8 = rd(xb.STR_PATH), xb.show("a32bd85", xb.STR_PATH)
    check("XN-01 XA-9: Strategy == xa_build.build_strategy() (XA-1 .. XA-9); strip_strategy9 gives a32bd85 byte for byte; kinds "
          "header / touch; Engine / Visual / SATS formula (f_satBand == the source record) unchanged",
          xb.build_strategy() == S9 and xb.strip_strategy9(S9) == S8 and xb.build_strategy8() == S8
          and {k for k, _, _ in xb.STRATEGY_EDITS9} == {"header", "touch"} and func(S9, "f_satBand() =>").rstrip("\n") + "\n" == SRC
          and rd(xb.ENG_PATH) == xb.show(B, xb.ENG_PATH) and rd(xb.VIS_PATH) == xb.show(B, xb.VIS_PATH))
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


def main():
    for g in (gate_static, gate_model, gate_mutation, gate_xa8, gate_xa9):
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
