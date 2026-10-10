"""NR-S1 fixtures — non-repainting Swing 15M / 1H in ZoneVisualPractical.pine.

  S  static : exact transform of 5758a61; only Swing #2 / #3 changed; Swing #1 / Accum / MA / Break / FVG / Engine untouched;
              wrapper returns every pivotPack field at [1]; HTF branch lookahead_on; same/lower TF keeps the original request
  T  timing : model of HTF bars built from 5M sub-bars, the Pine request semantics and the Engine edge rule
              (ZoneEnginePractical.pine 1251-1256: register when the pivot time key changes and is not na)
              old lookahead_off : historical = HTF bar with close <= chart-bar close (final values)
                                  realtime   = HTF bar containing the chart bar, developed so far   [TradingView docs]
              new S1 ([1] + lookahead_on) : historical and realtime = the HTF bar BEFORE the one containing the chart
                                  bar's open (final values)                                         [TradingView docs]

Evidence class: PINE_NOT_VERIFIED (exact transform + static + timing model; TradingView realtime is external).
"""
import os
import random
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nr_s1_build as nb              # noqa: E402
import fvg_re10045_sim as fr          # noqa: E402
import nr_a1_build as na              # noqa: E402
import zp_overlap_build as zp         # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CUR = open(os.path.join(ROOT, "ZoneVisualPractical.pine"), encoding="utf-8").read()
CUR = zp.strip_zpo(CUR) or CUR  # ZONE-P overlap display stripped -> 11b2b4e text (delta pinned by zp_overlap_sim)
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


def git_show(rev, path="ZoneVisualPractical.pine"):
    return subprocess.run(["git", "-C", ROOT, "show", f"{rev}:{path}"], capture_output=True, text=True).stdout


def code_only(src):
    return "\n".join(l for l in src.split("\n") if not l.lstrip().startswith("//"))


BASE = git_show(nb.NRS_BASE_REV)
BLK = CUR[CUR.index(nb.NRS_BEGIN):CUR.index("\n", CUR.index(nb.NRS_END)) + 1] if CUR.count(nb.NRS_BEGIN) == 1 else ""
BC = code_only(BLK)


# ============================================================================
# S : static
# ============================================================================
def gate_static():
    check("S-01 current Visual == nra_transform(nrs_transform(5758a61)) exactly (one NR-S1 block + the 2 Swing #2 / #3 "
          "request lines; then the NR-A1 Accum transform)",
          bool(BASE) and na.nra_transform(nb.nrs_transform(BASE)) == CUR)
    rest = nb.cut_block(na.strip_nra(CUR), nb.NRS_BEGIN, nb.NRS_END)
    check("S-02 removing the NR-A1 and NR-S1 blocks and reverting their edits gives 5758a61 byte-for-byte (nothing else changed: Swing #1, "
          "Accum, MA, Break, ZoneFeed, zn.update, FVG A / B / C, drawing)",
          rest is not None and nb.revert_nrs_edits(rest) == BASE)
    check("S-03 NR-S1 block placed immediately before the Swing source declarations",
          (BLK + "\n" + nb.NRS_ANCHOR) in CUR)
    check("S-04 wrapper returns every zn.pivotPack field of the previous HTF bar ([1]); detection formula / length untouched",
          "[_ph, _pt, _pl, _lt] = zn.pivotPack(len)\n    [_ph[1], _pt[1], _pl[1], _lt[1]]" in BC
          and "ta.pivot" not in BC)
    check("S-05 HTF branch (TF > chart TF) uses the wrapper with lookahead_on; same / lower TF keeps the original "
          "zn.pivotPack + lookahead_off request",
          "if timeframe.in_seconds(tf) > timeframe.in_seconds()\n        [_a, _at, _b, _bt] = request.security(syminfo.tickerid, tf, "
          "f_nrsPivotConfirmed(len), lookahead = barmerge.lookahead_on)" in BC
          and "    else\n        [_a, _at, _b, _bt] = request.security(syminfo.tickerid, tf, zn.pivotPack(len), "
          "lookahead = barmerge.lookahead_off)" in BC and BC.count("request.security(") == 2)
    cc = code_only(CUR)
    check("S-06 only Swing #2 / #3 use f_nrsSwing (with their own TF / length inputs); Swing #1 (5M) request unchanged",
          cc.count("f_nrsSwing(hzTf2, pivLen2)") == 1 and cc.count("f_nrsSwing(hzTf3, pivLen3)") == 1
          and cc.count("f_nrsSwing(") == 3
          and "    [_h1, _h1t, _l1, _l1t] = request.security(syminfo.tickerid, hzTf1, zn.pivotPack(pivLen1), lookahead = barmerge.lookahead_off)" in cc)
    check("S-07 no barstate in the NR-S1 block (nothing depends on barstate.isconfirmed inside a request)", "barstate" not in BC)
    check("S-08 RE10045 lint clean for the NR-S1 block; no array access", fr.lint_eager_guards(BC) == [] and "array." not in BC)
    check("S-09 request call sites: 2 Swing lines moved into the NR-S1 block (11 at 5758a61); NR-A1 then turns the 3 Accum "
          "requests into 2 call sites in its block (10 total)",
          len(re.findall(r"request\.\w+\(", code_only(BASE))) == 11
          and len(re.findall(r"request\.\w+\(", code_only(na.strip_nra(CUR) or ""))) == 11
          and len(re.findall(r"request\.\w+\(", cc)) == 10)
    check("S-10 inputs / defaults unchanged (no input added / modified)",
          re.findall(r"^\w+\s*=\s*input\..*$", CUR, re.M) == re.findall(r"^\w+\s*=\s*input\..*$", BASE, re.M))
    eng = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", nb.NRS_BASE_REV, "--",
                          "ZoneEnginePractical.pine", "ZoneEnginePracticalAuthority.pine", "SignalEnginePractical.pine",
                          "PracticalZoneStrategy_LONG.pine", "PracticalZoneStrategy_SHORT.pine"]
                         + [f for f in os.listdir(ROOT) if f.startswith("Practical") and f.endswith("Harness.pine")],
                         capture_output=True, text=True).stdout.strip()
    check("S-11 Engine / SignalEngine / Strategy / Harness / Authority unchanged vs 5758a61; import still /2",
          eng == "" and re.findall(r"^import .*$", cc, re.M) == ["import sekine3310/ZoneEnginePractical/2 as zn"], eng)
    for b, e in (("// ==== FVG Batch A (begin) ", "// ==== FVG Batch A (end) "),
                 ("// ==== FVG Batch B (begin) ", "// ==== FVG Batch B (end) "),
                 ("// ==== FVG Batch C (begin) ", "// ==== FVG Batch C (end) ")):
        blk = lambda s: s[s.index(b):s.index("\n", s.index(e)) + 1]
        check(f"S-12 {b.strip()[8:-8]} block byte-identical to 5758a61 (FVG results unchanged)", blk(CUR) == blk(BASE))


# ============================================================================
# T : timing model
# ============================================================================
M5 = 300_000


def build(htf_ms, subs, start=0, gaps=None, missing=None):
    """subs: list of HTF periods, each a list of (high, low) for its existing 5M bars in order (missing slots: shorter list
    with explicit slot offsets via `missing`). Returns (chart bars, htf bars).
    chart bar: dict(open, close, k=htf index, j=position in its HTF bar); htf bar: dict(T, C, subs)."""
    gaps = gaps or {}
    missing = missing or {}
    chart, htf, t = [], [], start
    for k, s in enumerate(subs):
        t += gaps.get(k, 0)
        T = t
        slots = [i for i in range(htf_ms // M5) if i not in missing.get(k, ())][:len(s)]
        htf.append(dict(T=T, C=T + htf_ms, subs=s))
        for j, (h, l) in enumerate(s):
            o = T + slots[j] * M5
            chart.append(dict(open=o, close=o + M5, k=k, j=j))
        t = T + htf_ms
    return chart, htf


def pivots(hl, i, n):
    """zn.pivotPack at HTF index i over the (high, low) list hl: [ph, pt_index, pl, lt_index] (pt = detection bar)."""
    if i < 2 * n:
        return None, None, None, None
    ch, cl = hl[i - n]
    win = [hl[x] for x in range(i - 2 * n, i + 1) if x != i - n]
    ph = ch if all(ch > w[0] for w in win) else None
    pl = cl if all(cl < w[1] for w in win) else None
    return ph, (i if ph is not None else None), pl, (i if pl is not None else None)


def final_hl(htf):
    return [(max(h for h, _ in b["subs"]), min(l for _, l in b["subs"])) for b in htf]


def value(mode, c, htf, n):
    """the (ph, pt) the Engine receives on chart bar c."""
    fin = final_hl(htf)
    if mode == "old_hist":
        ks = [k for k, b in enumerate(htf) if b["C"] <= c["close"]]
        if not ks:
            return None, None
        k = ks[-1]
        ph, pt, _, _ = pivots(fin[:k + 1], k, n)
    elif mode == "old_rt":
        k = c["k"]
        dev = fin[:k] + [(max(h for h, _ in htf[k]["subs"][:c["j"] + 1]), min(l for _, l in htf[k]["subs"][:c["j"] + 1]))]
        ph, pt, _, _ = pivots(dev, k, n)
    else:   # new_hist / new_rt : [1] of the HTF bar containing the chart bar's open (k-1 is complete in both modes)
        k = c["k"] - 1
        if k < 0:
            return None, None
        dev = fin[:k + 1]
        if mode == "new_rt":            # the developing bar k+1 exists in the context but [1] never reads it
            dev = fin[:k + 1] + [(max(h for h, _ in htf[c["k"]]["subs"][:c["j"] + 1]), 0.0)]
        ph, pt, _, _ = pivots(dev, k, n)
    return ph, (None if pt is None else htf[pt]["T"])


def engine_regs(mode, chart, htf, n):
    """Engine edge rule: register (price, chart bar index, chart bar close) when pt is not na and differs from the previous bar."""
    regs, prev = [], None
    for i, c in enumerate(chart):
        ph, pt = value(mode, c, htf, n)
        if pt is not None and (prev is None or pt != prev):
            regs.append((ph, pt, i, c["close"]))
        prev = pt
    return regs


def gate_timing():
    n = 2
    # T-01 phantom pivot (15M): HTF4's first 5M bars stay low, its 3rd breaks above the candidate
    subs = [[(100, 95), (101, 96), (102, 97)], [(103, 98), (104, 99), (105, 100)], [(108, 103), (110, 105), (109, 104)],
            [(106, 101), (105, 100), (104, 99)], [(107, 102), (108, 103), (115, 110)], [(100, 95)] * 3]
    chart, htf = build(15 * 60_000, subs)
    oh, ort = engine_regs("old_hist", chart, htf, n), engine_regs("old_rt", chart, htf, n)
    nh, nrt = engine_regs("new_hist", chart, htf, n), engine_regs("new_rt", chart, htf, n)
    check("T-01 pivot invalidated later inside the HTF bar: old realtime registers it (phantom), old historical does not; "
          "NR-S1 registers it in neither", [r[0] for r in ort if r[0] == 110] == [110] and not [r for r in oh if r[0] == 110]
          and not [r for r in nh + nrt if r[0] == 110], f"old_rt={ort} old_hist={oh} new={nh}")
    # T-02 / T-03 valid pivot: 15M and 1H, continuous trading
    for name, tf_min in (("15M", 15), ("1H", 60)):
        per = tf_min // 5
        hs = [100, 104, 110, 106, 103, 101, 100]
        subs = [[(h - 2, h - 7)] * (per - 1) + [(h, h - 5)] for h in hs]
        chart, htf = build(tf_min * 60_000, subs)
        oh, nh, nrt = engine_regs("old_hist", chart, htf, n), engine_regs("new_hist", chart, htf, n), engine_regs("new_rt", chart, htf, n)
        ok = len(oh) == 1 and nh == nrt and len(nh) == 1 and nh[0][:2] == oh[0][:2] and nh[0][3] - oh[0][3] == M5
        check(f"T-02 {name} valid pivot: same price and pivot time key; NR-S1 historical == realtime; registered at the first 5M "
              "bar after the HTF close: delay = +5 min (one bar) vs old historical", ok, f"old={oh} new={nh}")
        hc = htf[[b["T"] for b in htf].index(nh[0][1])]["C"]          # close of the HTF bar that confirmed the pivot
        check(f"T-03 {name} event only after the HTF bar that confirms the pivot has closed (registration bar open >= its close)",
              chart[nh[0][2]]["open"] >= hc and chart[oh[0][2]]["close"] == hc)
    # T-04 session break right after the confirming HTF bar
    hs = [100, 104, 110, 106, 103, 101]
    subs = [[(h - 1, h - 6), (h - 2, h - 7), (h, h - 5)] for h in hs]
    gap = 60 * 60_000
    chart, htf = build(15 * 60_000, subs, gaps={5: gap})        # HTF4 confirms the pivot (centre bar 2 + 2); break before HTF5
    oh, nh, nrt = engine_regs("old_hist", chart, htf, n), engine_regs("new_hist", chart, htf, n), engine_regs("new_rt", chart, htf, n)
    check("T-04 confirming HTF bar ends at a session break: NR-S1 registers at the first 5M bar after the break; "
          "delay = break + 5 min; historical == realtime", len(oh) == len(nh) == 1 and nh == nrt and nh[0][3] - oh[0][3] == gap + M5,
          f"old={oh} new={nh}")
    # T-05 the last 5M slot of the confirming HTF bar is missing -> old historical already registers on the next HTF bar
    subs_m = [s if k != 4 else s[:2] for k, s in enumerate(subs)]       # HTF4 (confirming bar) has no 3rd 5M bar
    chart, htf = build(15 * 60_000, subs_m, missing={4: (2,)})
    oh, nh, nrt = engine_regs("old_hist", chart, htf, n), engine_regs("new_hist", chart, htf, n), engine_regs("new_rt", chart, htf, n)
    check("T-05 last 5M slot of the confirming HTF bar missing: old historical and NR-S1 register on the same 5M bar (delay 0)",
          len(oh) == len(nh) == 1 and nh == nrt and nh[0][2:] == oh[0][2:], f"old={oh} new={nh}")
    # T-06 duplicate guard: the same confirmed pivot is seen on every 5M bar of the next HTF period -> one registration
    chart, htf = build(60 * 60_000, [[(h - 1, h - 6)] * 11 + [(h, h - 5)] for h in hs])
    nh = engine_regs("new_hist", chart, htf, n)
    seen = sum(1 for c in chart if value("new_hist", c, htf, n)[1] is not None)
    check("T-06 1H: the confirmed pivot key is delivered on all 12 5M bars of the next HTF period but registered once",
          len(nh) == 1 and seen == 12, f"regs={len(nh)} bars_with_key={seen}")
    # T-07 property: random series with breaks / missing slots -> NR-S1 historical == realtime; old differs somewhere
    rnd = random.Random(20261009)
    diff_old, all_eq = 0, True
    for _ in range(300):
        per = rnd.choice([3, 12])
        k_n = rnd.randint(8, 20)
        subs = []
        base = 100.0
        for k in range(k_n):
            cnt = per if rnd.random() > 0.15 else rnd.randint(1, per)
            row = []
            for j in range(cnt):
                base += rnd.uniform(-3, 3)
                row.append((round(base + rnd.uniform(0, 2), 2), round(base - rnd.uniform(0, 2), 2)))
            subs.append(row)
        gaps = {k: rnd.choice([0, 0, 0, 3_600_000]) for k in range(k_n)}
        chart, htf = build(per * M5, subs, gaps=gaps)
        nh, nrt = engine_regs("new_hist", chart, htf, n), engine_regs("new_rt", chart, htf, n)
        all_eq = all_eq and nh == nrt
        diff_old += engine_regs("old_hist", chart, htf, n) != engine_regs("old_rt", chart, htf, n)
    check("T-07 300 random 15M / 1H series (sessions breaks, partial HTF bars): NR-S1 historical == realtime in every case; "
          "the old path differs in some (repaint reproduced)", all_eq and diff_old > 0, f"old diffs={diff_old}")


def main():
    for g in (gate_static, gate_timing):
        try:
            g()
        except Exception as ex:
            check(f"{g.__name__} completed without error", False, repr(ex))
    w = max(len(n) for n, _, _ in RESULTS)
    fails = 0
    for n, ok, d in RESULTS:
        fails += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {n.ljust(w)}  {'' if ok else d}")
    print(f"\n{len(RESULTS) - fails}/{len(RESULTS)} passed  [PINE_NOT_VERIFIED: exact transform / static / timing model]")
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
