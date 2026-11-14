"""LAB-18 checks — ZoneComboLabXAU.pine TC サッツバンド転換 (the SATS detection of SatsShortSignal.pine @ bea7105 inside the 5m strategy).

  python3 tests/tcs_sim.py

  * static: the copied start-of-bar functions are byte-identical to SatsShortSignal.pine @ bea7105, f_satBand is unchanged
    (tests/sats_src/f_satBand.txt), every TC input and default equals the standalone version (2 patterns, timeframes, wait,
    band-return clears, HTF switch and its 48 columns), the old TC SATS 反発 inputs / filter / lifetime are gone, kind 2 lives only
    on its own 5m bar, and every request tuple stays within 127 elements (also the total)
  * behaviour: the LOGIC section itself (tests/lab_pine.py translator) is fed, per confirmed 5m bar, the arrays that
    request.security_lower_tf returns for 15s / 30s / 1m (start-of-bar data + the 15s bars' confirmed high / low / close / time_close),
    the chart bar's start data for 5m and the HTF request. Its LbTev (kind 2) per 5m bar is compared with the independent models of the
    standalone indicator (tests/sss_sim.py: mid_model for 帯→フラット, model_b for フラット→帯) on the same data: one TC per bar and
    direction, pattern names and each pattern's latest completion time in the reason, completions at exactly the bar's close belong to
    the next bar, completions found only after their bar was evaluated are not carried, HTF switch / segments as in the indicator

Evidence class: PINE_NOT_VERIFIED (translated Pine logic; TradingView's compiler, request.security_lower_tf delivery of seconds
timeframes and the strategy emulator are not reproduced). tests/lab_sim.py itself was already failing before LAB-18 (missing ZG / TD /
TE feeds, chart.is_standard, and its LAB-1 scenarios no longer match the current logic); this file feeds those as na.
"""
import os
import re
import subprocess
import sys
import types
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lab_pine as lp       # noqa: E402
import sss_sim as ss        # noqa: E402

ROOT = lp.ROOT
SRC = lp.read_source()
RESULTS = []
M5 = lp.M5
M = 60_000
S15 = 15_000

F15 = ["tq15t", "tq15ms", "tq15mb", "tq15o", "tq15sp", "tq15dp", "tq15l1", "tq15l2", "tq15h20", "tq15w20", "tq15h9", "tq15w9",
       "tq15tc", "tq15ss", "tq15ma", "tq15mz", "tq15H", "tq15L", "tq15C", "tq15TC"]
F30 = [n.replace("15", "30") for n in F15[:16]]
F60 = [n.replace("15", "60") for n in F15[:16]]
F5 = [n.replace("tq15", "tq5") for n in F15[:16]]
FH = ["tcH1t", "tcH1b", "tcH1n", "tcH2t", "tcH2b", "tcH2n", "tcHc", "tcHcn"]
for n in F15 + F30 + F60 + F5 + FH + ["zgPk1", "zgPk4", "zgPkD", "labTdDir", "labTdTc", "labTe15T", "labTe15B", "labTe15t"]:
    lp.FEED_DEFAULT.setdefault(n, None)
_init0 = lp.Runner.__init__


def _init(self, *a, **k):
    _init0(self, *a, **k)
    self.env.update(chart=types.SimpleNamespace(is_standard=True), array__copy=lambda a: list(a),
                    label__set_tooltip=lambda *a: None, label__set_y=lambda *a: None,
                    str__format_time=lambda t, f, tz: datetime.fromtimestamp(t / 1000, tz=timezone.utc).strftime(
                        f.replace("HH", "%H").replace("mm", "%M").replace("ss", "%S").replace("yyyy", "%Y").replace("MM", "%m")
                        .replace("dd", "%d")))


lp.Runner.__init__ = _init


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name + (("  -- " + detail) if (detail and not ok) else ""))


def func_text(src, name):
    i = src.index("\n" + name + "(") + 1
    return src[i:src.index("\n\n", i)]


# ---- feeds from 15s data ---------------------------------------------------------------------------------------------------------
def pack16(p):
    """sss_sim pack (t, ms, mb, o, stP, sdP, l1s, l2s, hh20, ll20, hh9, ll9, tcP, stS, ma, mz) -> 16 values (na masks as 0)"""
    p = tuple(p) + (None, 0, 0)[len(p) - 13:] if len(p) < 16 else tuple(p)
    return [p[0], p[1] or 0, p[2] or 0, p[3], p[4], p[5], p[6], p[7], p[8], p[9], p[10], p[11], p[12], p[13], p[14] or 0, p[15] or 0]


def lab_bars(T, b15, tfs, htf=None, htf_at=None):
    """5m bars with the feeds the strategy receives on each confirmed 5m bar. htf: sorted [(close, band)] (sss_sim format);
    htf_at(bar_start) -> the 8-value HTF delivery (default: sss_sim.htf_deliver at the bar start = lookahead_on)."""
    ks5 = tfs[3][0]
    out = []
    for q, t5 in enumerate(ks5):
        e5 = t5 + M5
        bar = dict(t=t5)
        idx = [i for i, t in enumerate(T) if t5 <= t < e5]
        bar.update(o=b15[idx[0]]["o"], h=max(b15[i]["h"] for i in idx), l=min(b15[i]["l"] for i in idx), c=b15[idx[-1]]["c"])
        cols = list(zip(*[pack16(tfs[0][1][i]) for i in idx])) if idx else [()] * 16
        for n, col in zip(F15[:16], cols):
            bar[n] = list(col)
        bar["tq15H"] = [b15[i]["h"] for i in idx]
        bar["tq15L"] = [b15[i]["l"] for i in idx]
        bar["tq15C"] = [b15[i]["c"] for i in idx]
        bar["tq15TC"] = [T[i] + S15 for i in idx]
        for rank, names in ((1, F30), (2, F60)):
            ks, packs = tfs[rank]
            jj = [j for j, k in enumerate(ks) if t5 <= k < e5]
            cols = list(zip(*[pack16(packs[j]) for j in jj])) if jj else [()] * 16
            for n, col in zip(names, cols):
                bar[n] = list(col)
        for n, v in zip(F5, pack16(tfs[3][1][q])):
            bar[n] = v
        if htf is not None:
            hv = htf_at(t5) if htf_at else ss.htf_deliver(htf, t5)
            for n, v in zip(FH, hv):
                bar[n] = v
        out.append(bar)
    return out


QUIET = dict(cTA=False, cTE=False, cTD=False, cTC=True, cZA=False, cZB=False, cZC=False, cZD=False, cZF=False, cZE=False, cZG=False)


def run_tc(bars, **ov):
    """run the logic; returns {(bar start, side): desc} of the LbTev kind 2 issued on each bar"""
    r = lp.Runner(overrides=dict(QUIET, **ov))
    out = {}
    for b in bars:
        r.step(b)
        for e in r.env["lbTevs"]:
            if e.kind == 2 and e.eBar == r.bar_index:
                out[(b["t"], e.side)] = e.desc
    return out, r


def hms(t):
    return datetime.fromtimestamp(t / 1000, tz=timezone.utc).strftime("%H:%M:%S")


def expected(sigA, sigB):
    """model signals [(x, dir, times)] per pattern -> {(bar start, side): desc} with the latest completion per pattern"""
    per = {}
    for p, sig in ((0, sigA), (1, sigB)):
        for (_x, d, times) in sig:
            t = max(times)
            key = (t - t % M5, -1 if d == "SELL" else 1)
            per.setdefault(key, {})
            per[key][p] = max(per[key].get(p, t), t)
    out = {}
    for key, pp in per.items():
        names = ["帯→フラット", "フラット→帯＋端の線転換"]
        tx = " / ".join(f"{names[p]} {hms(pp[p])}" for p in (0, 1) if p in pp)
        out[key] = "TC サッツバンド転換 " + ("SELL " if key[1] == -1 else "BUY ") + tx
    return out


def main():
    # ---- static ------------------------------------------------------------------------------------------------------------------
    sss = subprocess.run(["git", "-C", ROOT, "show", "bea7105:SatsShortSignal.pine"], capture_output=True, text=True).stdout
    for fn in ("f_nextAnchor", "f_satsPrep", "f_satsStart", "f_evt", "f_edgeMask"):
        check(f"static: {fn} == SatsShortSignal.pine @ bea7105 (byte for byte)", func_text(SRC, fn) == func_text(sss, fn))
    sats = open(os.path.join(ROOT, "tests", "sats_src", "f_satBand.txt"), encoding="utf-8").read()
    check("static: f_satBand unchanged (tests/sats_src/f_satBand.txt)", sats in SRC)
    ev_s = func_text(sss, "f_satsEvt").split("\n")[1:7]
    ev_l = func_text(SRC, "f_tcEvt").split("\n")[1:7]
    check("static: f_tcEvt computes the current-bar pack with the same lines as SatsShortSignal f_satsEvt", ev_s == ev_l)
    inp = lp.ap.inputs(SRC)
    ok = (inp["tcWait"] == 5 and inp["tcPatA"] is True and inp["tcPatB"] is False
          and [inp[k] for k in ("tcU15", "tcU30", "tcU60", "tcU300")] == [True, True, True, False]
          and [inp[k] for k in ("tcUB15", "tcUB30", "tcUB60", "tcUB300")] == [True, True, True, False]
          and all(inp[k] is True for k in ("tcClr15", "tcClr30", "tcClr60", "tcClr300"))
          and inp["tcHtfOn"] is False and inp["tcHtfTf"] == "60" and 'options = ["60", "240", "D"]' in SRC)
    sel = []
    for pn in "AB":
        for bi in range(3):
            for dd in "SB":
                for i in range(4):
                    sel.append(inp[f"tcx{pn}{bi}{dd}{i}"])
    check("static: TC inputs and defaults equal the standalone version (patterns, timeframes, wait, clears, HTF, 48 columns)",
          ok and sel == ss.DEFAULT_SEL)
    check("static: entry switch renamed 'TC サッツバンド転換' (default OFF); old TC inputs / 4H-1H filter / lifetime removed",
          inp["cTC"] is False and 'cTC = input.bool(false, "TC サッツバンド転換"' in SRC
          and not any(k in inp for k in ("stSatsNear", "stSatsNearD", "stSatsBody", "stSatsNowC", "tcLife", "tcFilt"))
          and "f_satHist" not in SRC and "satTf4" not in SRC)
    check("static: kind 2 (TC) lives only on its own 5m bar (like TE / TD)",
          "bar_index - e.eBar > (e.kind == 1 ? fvAbsLife : 0)" in SRC)
    sizes = []
    for m in re.finditer(r"\n\[([^\]]+)\]\s*=\s*\n?\s*request\.security(?:_lower_tf)?\(", SRC):
        sizes.append(len([x for x in m.group(1).replace("\n", " ").split(",") if x.strip()]))
    singles = len(re.findall(r"\n(?:int|float|string|bool)?\s*\w+\s*=\s*request\.security(?:_lower_tf)?\(", SRC))
    check(f"static: every request tuple <= 127 elements and the total too (tuples {sizes}, single values {singles})",
          max(sizes) <= 127 and sum(sizes) + singles <= 127 and 20 in sizes and sizes.count(16) >= 2 and 8 in sizes)

    # ---- behaviour vs the standalone models ------------------------------------------------------------------------------------
    T0 = int(datetime(2026, 1, 5, 1, 0, tzinfo=timezone.utc).timestamp() * 1000)
    agree = 0
    nsig = 0
    runs = 0
    for seed in (515, 522, 526):
        rng = ss.random.Random(seed)
        b15 = ss.regime_bars(rng, 960, vol=rng.choice([0.3, 0.8]))
        T = [T0 + i * S15 for i in range(len(b15))]
        tfs = ss.series_tfs(T, b15)
        bars = lab_bars(T, b15, tfs)
        for (useA, useB) in (((True, True, True, False), None), (None, (True, True, True, False)),
                             ((True, True, False, False), (True, True, True, True))):
            ov = dict(tcPatA=useA is not None, tcPatB=useB is not None)
            if useA:
                ov.update(tcU15=useA[0], tcU30=useA[1], tcU60=useA[2], tcU300=useA[3])
            if useB:
                ov.update(tcUB15=useB[0], tcUB30=useB[1], tcUB60=useB[2], tcUB300=useB[3])
            got, _ = run_tc(bars, **ov)
            sA = ss.mid_model(T, b15, tfs, use=useA)[0] if useA else []
            sB = ss.model_b(tfs, useB)[0] if useB else []
            exp = expected(sA, sB)
            # the last bar's completions at its close belong to the next bar (not in the run)
            exp = {k: v for k, v in exp.items() if k[0] <= bars[-1]["t"]}
            nsig += len(exp)
            runs += 1
            agree += got == exp
            if got != exp:
                print("   diff", seed, useA, useB, sorted(set(got.items()) ^ set(exp.items()))[:4])
    print(f"   TC per 5m bar (both patterns, 3 series x 3 settings): {nsig}")
    check("behaviour: LbTev kind 2 per 5m bar == the standalone models (A only / B only / both, 3 random series)",
          agree == runs and nsig > 0)
    # HTF switch ON with random bands / columns
    agreeH = 0
    nH = 0
    seedsH = (515, 520, 522, 526, 500, 503)
    for seed in seedsH:
        rng = ss.random.Random(seed)
        b15 = ss.regime_bars(rng, 1440, vol=rng.choice([0.3, 0.8]))
        T = [T0 + i * S15 for i in range(len(b15))]
        tfs = ss.series_tfs(T, b15)
        per = rng.choice([10, 15, 20]) * M     # real 1h / 4h / D boundaries are 5m boundaries
        htf = [(T[0] - T[0] % per + k * per, rng.choice([-1, 0, 1, 1, -1])) for k in range(len(T) * S15 // per + 3)]
        selR = [rng.random() < 0.6 for _ in range(48)]
        bars = lab_bars(T, b15, tfs, htf)
        ov = dict(tcHtfOn=True, tcPatA=True, tcPatB=True)
        k = 0
        for pn in "AB":
            for bi in range(3):
                for dd in "SB":
                    for i in range(4):
                        ov[f"tcx{pn}{bi}{dd}{i}"] = selR[k]
                        k += 1
        got, _ = run_tc(bars, **ov)
        useU = tuple(any(selR[((1 * 3 + bi) * 2 + dd) * 4 + i] for bi in range(3) for dd in range(2)) for i in range(4))
        sA = ss.mid_model(T, b15, tfs, htf=htf, sel=selR)[0]
        sB = ss.model_b(tfs, useU, htf=htf, sel=selR)[0]
        exp = {k2: v for k2, v in expected(sA, sB).items() if k2[0] <= bars[-1]["t"]}
        nH += len(exp)
        agreeH += got == exp
        if got != exp:
            print("   diff HTF", seed, sorted(set(got.items()) ^ set(exp.items()))[:4])
    print(f"   TC per 5m bar with the HTF switch: {nH}")
    check(f"behaviour: HTF switch ON (random bands and 48 random columns, both patterns, {len(seedsH)} series) == the standalone models",
          agreeH == len(seedsH) and nH >= 10)

    # ---- hand-made cases -----------------------------------------------------------------------------------------------------------
    H = 3600_000

    def hm(h, mi, se=0):
        return T0 - T0 % (24 * H) + h * H + mi * M + se * 1000
    # 1. a chain completing exactly at the 5m close (1m start 10:05:00) belongs to the 10:05 bar
    T, b15, tfs = ss.hand_case(hm(1, 0), 60, {}, {}, {(0, hm(1, 4)): (2, 0), (1, hm(1, 4, 30)): (2, 0), (2, hm(1, 5)): (2, 0)})
    got, _ = run_tc(lab_bars(T, b15, tfs))
    check("boundary: 15s 01:04:00 -> 30s 01:04:30 -> 1m 01:05:00 completes at the 01:00 bar's close -> TC on the 01:05 bar only",
          got == {(hm(1, 5), -1): "TC サッツバンド転換 SELL 帯→フラット 01:05:00"})
    # 2. a mid-bar STB at the last 15s close (= the 5m close) also belongs to the next bar
    SELLPK = (0, 0, 0, 100.0, 1, 1, 90.0, 110.0, 120.0, 95.0, 118.0, 96.0)
    T, b15, tfs = ss.hand_case(hm(1, 0), 60, {(2, hm(1, 4)): SELLPK}, {hm(1, 4, 45): (100.2, 94.0, 99.0)},
                               {(0, hm(1, 3)): (2, 0), (1, hm(1, 3, 30)): (2, 0)})
    got, _ = run_tc(lab_bars(T, b15, tfs))
    check("boundary: 1m mid-bar STB confirmed by the 15s bar closing at 01:05:00 -> TC on the 01:05 bar",
          got == {(hm(1, 5), -1): "TC サッツバンド転換 SELL 帯→フラット 01:05:00"})
    # 3. waits carry across 5m bars: 15s 01:04:30 (01:00 bar) -> 30s 01:05:00 -> 1m 01:06:00 (01:05 bar)
    T, b15, tfs = ss.hand_case(hm(1, 0), 60, {}, {}, {(0, hm(1, 4, 30)): (0, 2), (1, hm(1, 5)): (0, 2), (2, hm(1, 6)): (0, 2)})
    got, _ = run_tc(lab_bars(T, b15, tfs))
    check("carry: a BUY chain started in the 01:00 bar completes in the 01:05 bar -> TC BUY on 01:05",
          got == {(hm(1, 5), 1): "TC サッツバンド転換 BUY 帯→フラット 01:06:00"})
    # 4. both patterns in the same bar and direction -> one TC with both names and each latest time
    def BP(k, stP, stS, ma=0, mz=0):
        return (k, 0, 0, 100.0, stP, 1, None, None, None, None, None, None, k, stS, ma, mz)
    packs = {(0, hm(1, 1)): BP(hm(1, 1), 0, -1, ma=2), (1, hm(1, 1, 30)): BP(hm(1, 1, 30), 0, -1, ma=1),
             (2, hm(1, 2)): BP(hm(1, 2), 0, -1, ma=4)}
    T, b15, tfs = ss.hand_case(hm(1, 0), 40, packs, {}, {(0, hm(1, 1)): (2, 0), (1, hm(1, 1, 30)): (2, 0), (2, hm(1, 3)): (2, 0)})
    got, _ = run_tc(lab_bars(T, b15, tfs), tcPatB=True)
    check("merge: 帯→フラット (01:03:00) and フラット→帯 (01:02:00) SELL in the 01:00 bar -> one TC with both names and times",
          got == {(hm(1, 0), -1): "TC サッツバンド転換 SELL 帯→フラット 01:03:00 / フラット→帯＋端の線転換 01:02:00"})
    # 5. a completion found only after its bar was evaluated is not carried: the HTF bar's [2] arrives one 5m bar late
    RED = [(hm(0, 30), -1), (hm(0, 40), -1), (hm(0, 50), -1), (hm(1, 0), -1), (hm(1, 10), -1), (hm(1, 20), -1), (hm(1, 30), -1)]
    st = {(0, hm(1, 11)): (2, 0), (1, hm(1, 11, 30)): (2, 0)}
    T, b15, tfs = ss.hand_case(hm(1, 0), 120, {}, {}, st)

    def htf_late(t5):
        hv = list(ss.htf_deliver(RED, t5))
        # the 01:10 HTF bar starts the 01:10 5m bar; its [1] (the 01:00-01:10 bar = index 4) is missing on that 5m bar only
        if t5 == hm(1, 10):
            hv[0:3] = [None, None, None]
        return tuple(hv)
    sel = list(ss.DEFAULT_SEL)
    ovH = dict(tcHtfOn=True)
    k = 0
    for pn in "AB":
        for bi in range(3):
            for dd in "SB":
                for i in range(4):
                    ovH[f"tcx{pn}{bi}{dd}{i}"] = sel[k]
                    k += 1
    got_ok, _ = run_tc(lab_bars(T, b15, tfs, RED), **ovH)
    got_late, _ = run_tc(lab_bars(T, b15, tfs, RED, htf_late), **ovH)
    check("late: HTF red known in time -> TC SELL on the 01:10 bar (15s -> 30s under red)",
          got_ok == {(hm(1, 10), -1): "TC サッツバンド転換 SELL 帯→フラット 01:11:30"})
    check("late: the HTF band for 01:10-01:20 arrives one 5m bar late -> the chain completes while the 01:15 bar is evaluated, "
          "but its time is in the evaluated 01:10 bar -> no TC (not carried)", got_late == {})
    # 6. end to end: the TC is one item of the existing AND / OR timing; the entry reason carries the pattern and time
    T, b15, tfs = ss.hand_case(hm(1, 0), 60, {}, {}, {(0, hm(1, 6)): (0, 2), (1, hm(1, 6, 30)): (0, 2), (2, hm(1, 7)): (0, 2)})
    barsE = lab_bars(T, b15, tfs)
    for b in barsE:
        b["zbMa1"] = 99.0
    ovE = dict(cZB=True, zdUse2=False, zdUse3=False, zdUse4=False, zeUse=False)

    def entries(**o):
        r = lp.Runner(overrides=dict(QUIET, **ovE, **o))
        for b in barsE:
            r.step(b)
        return [l for l in r.broker.log if l[0] == "order_entry"], r.alerts
    en, al = entries()
    check("entry: TC BUY (01:07:00, in the 01:05 bar) with a ZB zone -> LONG ordered on the 01:05 bar's close; the reason has "
          "'TC サッツバンド転換 BUY 帯→フラット 01:07:00'",
          [(l[1], l[3]) for l in en] == [(1, 1)] and any("TC サッツバンド転換 BUY 帯→フラット 01:07:00 (この足)" in a[1] for a in al))
    en, _ = entries(cTC=False, cTA=True)
    check("entry: TC switch OFF (TA only, no TA) -> no order", en == [])
    en, _ = entries(cTA=True, cTim="AND")
    check("entry: TC AND TA (no TA on that bar) -> no order", en == [])

    # 7. LAB-18b: the 15s bars for a 30s / 1m mid-bar STB are limited to the target bar's own interval
    #    end = min(start + 30 / 60 s, next fetched start of the same timeframe, the 5m close); start in [start, end), close <= end
    prev18 = subprocess.run(["git", "-C", ROOT, "show", "300bf15:ZoneComboLabXAU.pine"], capture_output=True, text=True).stdout

    def drop30(bars, t30):
        """remove the 30s bar starting t30 from the request.security_lower_tf arrays (not delivered)"""
        for b in bars:
            if t30 in (b.get("tq30t") or []):
                j = b["tq30t"].index(t30)
                for n in F30:
                    del b[n][j]
        return bars

    def run_src(src, bars, **ov):
        lp.SRC_OVERRIDE = src
        try:
            return run_tc(bars, **ov)[0]
        finally:
            lp.SRC_OVERRIDE = None
    SP = (0, 0, 0, 100.0, 1, 1, 90.0, 110.0, 120.0, 95.0, 118.0, 96.0)
    st7 = {(0, hm(1, 1)): (2, 0), (2, hm(1, 2)): (2, 0)}
    T, b15, tfs = ss.hand_case(hm(1, 0), 40, {(1, hm(1, 1)): SP}, {hm(1, 1, 30): (100.2, 94.0, 99.0)}, st7)
    bars7 = drop30(lab_bars(T, b15, tfs), hm(1, 1, 30))
    got_new = run_src(SRC, bars7)
    got_old = run_src(prev18, bars7)
    check("15s window: the 30s bar 01:01:30 is not delivered; the STB flip on the 15s bar 01:01:30 is outside the 01:01:00 30s bar "
          "(end = 01:01:30) -> no 30s mid STB, no TC (300bf15 used it up to the next fetched start 01:02:00 and gave a TC)",
          got_new == {} and got_old == {(hm(1, 0), -1): "TC サッツバンド転換 SELL 帯→フラット 01:02:00"})
    T, b15, tfs = ss.hand_case(hm(1, 0), 40, {(1, hm(1, 1)): SP}, {hm(1, 1, 15): (100.2, 94.0, 99.0)}, st7)
    bars7b = drop30(lab_bars(T, b15, tfs), hm(1, 1, 30))
    check("15s window: the flip on the 15s bar 01:01:15 (closing exactly at the 30s bar's end 01:01:30) is used -> TC SELL "
          "01:02:00 (15s 01:01:00 -> 30s mid 01:01:30 -> 1m 01:02:00)",
          run_src(SRC, bars7b) == {(hm(1, 0), -1): "TC サッツバンド転換 SELL 帯→フラット 01:02:00"})
    # a 1m target: the window ends at start + 60 s even when the next 1m bar is missing
    SP1 = SP
    st8 = {(0, hm(1, 1)): (2, 0), (1, hm(1, 1, 30)): (2, 0)}

    def drop60(bars, t60):
        for b in bars:
            if t60 in (b.get("tq60t") or []):
                j = b["tq60t"].index(t60)
                for n in F60:
                    del b[n][j]
        return bars
    T, b15, tfs = ss.hand_case(hm(1, 0), 40, {(2, hm(1, 1)): SP1}, {hm(1, 2, 15): (100.2, 94.0, 99.0)}, st8)
    bars8 = drop60(lab_bars(T, b15, tfs), hm(1, 2))
    got8n = run_src(SRC, bars8)
    got8o = run_src(prev18, bars8)
    check("15s window: the 1m bar 01:02 is not delivered; the flip on 01:02:15 is outside the 01:01 1m bar (end = 01:02:00) -> "
          "no TC (300bf15 extended the 01:01 bar to the 5m close and gave a TC)",
          got8n == {} and got8o == {(hm(1, 0), -1): "TC サッツバンド転換 SELL 帯→フラット 01:02:30"})

    bad = [n for n, ok in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(bad)}/{len(RESULTS)} passed")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
