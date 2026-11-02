"""LAB-1 fixture — ZoneComboLabXAU.pine (Zone Combo Lab XAU).

  python3 tests/lab_sim.py

Static checks compare the copied detection code byte for byte with its sources; scenario checks run the Pine LOGIC section
itself through tests/lab_pine.py (mechanical translation + broker emulator). Evidence class: PINE_NOT_VERIFIED (TradingView's
compiler, request.security and broker are not reproduced).
"""
import os
import random
import re
import subprocess
import sys
import time as _time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lab_pine as lp     # noqa: E402
lp.LEGACY = dict(zHalf=6.0, zcMerge=-1.0)     # LAB-3e: the scenarios below were written for these (new scenarios override them)

ROOT = lp.ROOT
SRC = lp.read_source()
RESULTS = []
M5 = lp.M5
# 2026-01-05 (Mon) 10:00 JST = 01:00 UTC: inside the 09:00-02:00 JST entry window
T0 = int(datetime(2026, 1, 5, 1, 0, tzinfo=timezone.utc).timestamp() * 1000)


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


def raw(path):
    return open(os.path.join(ROOT, path), encoding="utf-8").read()


def git(*a):
    return subprocess.run(["git", "-C", ROOT] + list(a), capture_output=True, text=True).stdout


def func_text(src, name):
    """a top-level Pine function: its header line and every following line until the next unindented line."""
    i = src.index("\n" + name + "(") + 1
    lines = src[i:].split("\n")
    out = [lines[0]]
    for ln in lines[1:]:
        if ln and not ln.startswith(" "):
            break
        out.append(ln)
    while out and not out[-1].strip():
        out.pop()
    return "\n".join(out)


# ============================================================================
# scenario builder
# ============================================================================
class Sc:
    """5m bars from (o, h, l, c) rows; feed values set per bar (set) or held over a bar range (hold)."""

    def __init__(self, rows, t0=T0):
        self.bars = [dict(t=t0 + i * M5, o=float(o), h=float(h), l=float(l), c=float(c)) for i, (o, h, l, c) in enumerate(rows)]

    def set(self, i, **kv):
        self.bars[i].update(kv)
        return self

    def hold(self, i0, i1=None, **kv):
        for i in range(i0, len(self.bars) if i1 is None else i1):
            self.bars[i].update(kv)
        return self

    def run(self, **ov):
        return lp.Runner(overrides=ov).run(self.bars)


def flat(n, p=1990.0, w=1.0):
    """n quiet bars around p (bullish doji-like, no FVG): o = p, h = p + w, l = p - w, c = p + 0.1"""
    return [(p, p + w, p - w, p + 0.1) for _ in range(n)]


T_HTF = T0 - 86_400_000     # a plausible confirmed higher-TF bar time (before every test bar)


def pocv(k, lo, up, t=T_HTF):
    """the values the bar receives for POC slot k (1..4): LAB-2 external series (zdL / zdU / zdT) and, for running the LAB-1
    source in comparisons, the old internal feed (d*c = (lo + up) / 2 as f_pocCore computes it)."""
    return {f"zdL{k}": lo, f"zdU{k}": up, f"zdT{k}": t, f"d{k}c": (lo + up) / 2.0, f"d{k}u": up, f"d{k}l": lo}


def poc(sc, i0, c, k=1, i1=None):
    """ZD POC zone feed (time frame k = 1..4) with centre c from bar i0."""
    return sc.hold(i0, i1, **pocv(k, c - 0.5, c + 0.5))


def tc_short(L):
    """a bar that is a TC SHORT rebound off line L (needs the previous close below L): high touches L, bearish close below L."""
    return (L - 0.5, L + 0.5, L - 3.0, L - 2.5)


def tc_long(L):
    return (L + 0.5, L + 3.0, L - 0.5, L + 2.5)


ONLY_TC = dict(cTA=False, cTC=True)
ONLY_ZD = dict(cZA=False, cZB=False, cZC=False, cZD=True, cZF=False)
QUIET = dict(zbUse1=False, zbUse2=False, dsZone=False, dsEnt=False)


def entries(r):
    """[(bar, id, side, qty)] of the strategy.entry orders"""
    return [(e[1], e[2], e[3], e[4]) for e in r.broker.log if e[0] == "order_entry"]


# ============================================================================
# static checks
# ============================================================================
def static():
    acc = raw("AccumStrategyXAU.pine")
    a_lab = lp.block(SRC, "// ==== LAB Accum copy (begin)", "// ==== LAB Accum copy (end)")
    a_acc = lp.block(acc, "// ==== ACC Accum copy (begin)", "// ==== ACC Accum copy (end)")
    a_acc = a_acc[a_acc.index("f_acAccumBoxCore("):]
    check("LS-01 ZA: f_acAccumBoxCore / f_acAccumBoxState byte-identical to AccumStrategyXAU (ACC Accum copy) and f_acConfirmed "
          "identical; the three requests are the ACC requests (60 / 240 / D, lookahead_on)",
          a_lab == a_acc and func_text(SRC, "f_acConfirmed") == func_text(acc, "f_acConfirmed")
          and all(SRC.count(f'request.security(syminfo.tickerid, "{tf}", f_acConfirmed(') == 1 for tf in ("60", "240", "D")))
    mtf = raw("MtfPocDetector.pine")
    feed = raw("MtfPocFeedXAU.pine")
    f_new = func_text(feed, "f_pocCore")
    f_old = func_text(mtf, "f_pocCore")
    old_loop = ("                else\n"
                "                    for bi = 0 to bins - 1\n")
    new_loop = ("                else\n"
                "                    int b0 = math.max(0, math.floor((cl - lo) / bs) - 1)\n"
                "                    int b1 = math.min(bins - 1, math.floor((ch - lo) / bs) + 1)\n"
                "                    for bi = b0 to b1\n")
    reqs = re.findall(r'request\.security\(syminfo\.tickerid, "(\w+)",\s*f_feed\((use\d), (len\d), vpBins\), lookahead = barmerge\.lookahead_on\)', feed)
    names = re.findall(r'^plot\(is5m \? [^,]+, "([^"]+)",\s+display = display\.none\)$', feed, re.M)
    want = [f"POC {tf} {it}" for tf in ("1H", "4H", "日足", "週足") for it in ("区画下限", "区画上限", "対象足時刻")] + ["POC protocol"]
    check("LS-02 ZD split (LAB-2): MtfPocFeedXAU f_pocCore == MtfPocDetector f_pocCore except the per-candle bin range (only the loop "
          "header replaced by the b0 / b1 range); 4 requests 1H / 4H / D / W with offset 1 + lookahead_on; 13 plots (display.none, names "
          "= the lab's 13 input.source titles); 120 bars / 75 bins defaults; the lab has no POC calculation / POC request / fallback",
          f_old.count(old_loop) == 1 and f_new == f_old.replace(old_loop, new_loop) and [r[0] for r in reqs] == ["60", "240", "D", "W"]
          and "f_pocCore(enabled, 1, lookback, bins)" in feed and names == want and 'plot(is5m ? 10001 : na, "POC protocol"' in feed
          and all(f'len{k} = input.int(120,' in feed for k in (1, 2, 3, 4)) and 'vpBins = input.int(75,' in feed
          and "f_pocCore" not in re.sub(r"//.*", "", SRC) and "f_lbPocHtf" not in SRC
          and all(f'input.source(close, "{n}"' in SRC for n in want[:-1]) and 'input.source(close, "POC protocol (10001)"' in SRC,
          f"{names} {reqs}")
    zs = raw("ZoneStrategyXAU.pine")
    check("LS-03 ZF: f_fvgConfirmed byte-identical to ZoneStrategyXAU FVG Batch A; FVG min width default 3.0",
          func_text(SRC, "f_fvgConfirmed") == func_text(zs, "f_fvgConfirmed") and 'zfMinW = input.float(3.0,' in SRC)
    sats = raw("tests/sats_src/f_satBand.txt").rstrip("\n")
    check("LS-04 TC: f_satBand byte-identical to tests/sats_src/f_satBand.txt (= ZoneStrategyXAU) and f_satTfState identical",
          func_text(SRC, "f_satBand") == sats and func_text(SRC, "f_satTfState") == func_text(zs, "f_satTfState"))
    h_lab = func_text(SRC, "f_satHist")
    h_zs = func_text(zs, "f_satHist")
    h_zs_c = re.sub(r"//.*", "", h_zs).replace("close[1]", "labC1")
    h_lab_c = re.sub(r"//.*", "", h_lab)
    norm = lambda t: "\n".join(l.rstrip() for l in t.split("\n"))
    check("LS-05 TC: f_satHist == ZoneStrategyXAU f_satHist with close[1] -> labC1 (= close[1] taken outside the logic section) "
          "and comments dropped; internal inputs keep the existing names / defaults (near ON 1.0, body ON, Nc 1)",
          norm(h_lab_c) == norm(h_zs_c) and "float labC1 = close[1]" in SRC
          and 'stSatsNear  = input.bool(true,' in SRC and 'stSatsNearD = input.float(1.0,' in SRC
          and 'stSatsBody  = input.bool(true,' in SRC and 'stSatsNowC  = input.int(1,' in SRC)
    check("LS-06 money / session: f_qty and f_inSession byte-identical to AccumStrategyXAU (= ZoneStrategyXAU f_stQty formula); "
          "300,000 JPY x 3 %, 100 oz, 0.01 / 0.01 lot",
          func_text(SRC, "f_qty") == func_text(acc, "f_qty") and func_text(SRC, "f_inSession") == func_text(acc, "f_inSession")
          and "mmCapBase = input.float(300000.0," in SRC and "mmRiskPct = input.float(3.0," in SRC)
    ta_lab = [l.strip() for l in lp.logic_section(SRC).split("\n") if "low > labH2" in l or "high < labL2" in l or "bool absd" in l]
    ta_acc = [l.strip().replace("acH2", "labH2").replace("acL2", "labL2").replace("acO1", "labO1").replace("acC1", "labC1")
              for l in acc.split("\n") if "low > acH2" in l or "high < acL2" in l or "bool absd" in l]
    check("LS-07 TA: FVG formation (up: low > high[2] + bullish middle bar / down: high < low[2] + bearish middle) and absorption "
          "(bearish close <= lo / bullish close >= hi) lines == ACC-5A with the renamed history values; min width 1.0, life 10, "
          "validity after absorption 12 (was 5)",
          ta_lab == ta_acc and len(ta_lab) == 3 and 'fvMinW    = input.float(1.0,' in SRC and 'fvLife    = input.int(10,' in SRC
          and 'fvAbsLife = input.int(12,' in SRC)
    base = git("log", "--format=%H", "-1", "--", "MtfPocDetector.pine").strip()
    normal = ["ZoneStrategyXAU.pine", "ZoneStrategyXAULong.pine", "ZoneEnginePracticalXAUUSD.pine", "AccumStrategyXAU.pine",
              "MtfPocDetector.pine", "tests/acc_pine.py"]     # tests/acc_sim.py: only the recorded LAB-1 edit (LS-11)
    changed = git("diff", "--name-only", "HEAD", "--", *normal).split() + git("diff", "--name-only", "--cached", "--", *normal).split()
    check("LS-08 the normal Strategy / Engine / Accum / POC detector files and the ACC harness are not modified (working tree == HEAD; "
          "the older fixtures change only by the LAB-1 registration edits, LS-11)",
          not changed and base != "", str(changed))
    code = re.sub(r"//.*", "", SRC)
    n_plot = len(re.findall(r"(?<![\w.])plot\(", code))
    n_req = len(re.findall(r"request\.security\(", code))
    n_src = len(re.findall(r"input\.source\(", code))
    check("LS-09 limits: plot() calls <= 64 (14), request.security calls 14 (Accum 3 + 1m EMA 1 + Swing 4 + FVG 4 + SATS filter 2; the 4 "
          "POC requests moved to MtfPocFeedXAU), 13 input.source, no request.security_lower_tf",
          n_plot <= 64 and n_req == 14 and n_src == 13 and "security_lower_tf" not in code, f"plot {n_plot} request {n_req} source {n_src}")
    logic = lp.logic_section(SRC)
    lc = re.sub(r"//.*", "", logic).split("\n")
    in_ds, draw_ok, fn = False, True, None
    for k, ln in enumerate(lc):
        m = re.match(r"^(\w+)\(.*\)\s*=>", ln)
        if m or (ln and not ln.startswith(" ")):
            fn = m.group(1) if m else None
        if "box." in ln and not (fn or "").startswith("f_ds"):
            draw_ok = False
        if re.search(r"(?<!\w)f_ds(Add|Del|Rename|Ma)\(", ln) and not (fn or "").startswith("f_ds") and not lc[k - 1].strip() == "if dsZone":
            draw_ok = False
    check("LS-10 the logic section has no history reference / request / ta.* call (transpiles; series values come from the feed "
          "section), no expiry / generation pruning of valid Zones except the accum box count (zaKeep); Zone drawing (box.*) only in "
          "the f_ds* display functions, each call guarded by 'if dsZone' (as in LAB-2)",
          lp.transpile() and not re.search(r"\w\[\d", re.sub(r"//.*", "", logic).replace("[]", "")) and "request." not in logic
          and "ta." not in re.sub(r"//.*", "", logic) and "Keep" not in logic.replace("zaKeep", "") and "expTime" not in logic
          and draw_ok and "barstate.islast" not in logic)


REG_BASE = "444e61f"     # the last commit before the LAB-1 registration edits


def registration():
    import lab_build as lb
    bad = []
    for path, eds in lb.TEST_EDITS.items():
        cur = raw(path)
        try:     # later layers (e.g. FDS-1 via fds_build) stack their exact edits on top: revert them first, as the unadapt chain does
            cur = __import__("fds_build").unadapt(path, cur)
        except ImportError:
            pass
        if not all(cur.count(new) == cnt for _, new, cnt in eds):
            bad.append((path, "edit not applied exactly"))
        elif lb.unadapt(path, cur) != git("show", f"{REG_BASE}:{path}"):
            bad.append((path, "unadapt != the text before the edits"))
    missing = [f for f in lb.NEW_FILES if not os.path.exists(os.path.join(ROOT, f))]
    check("LS-11 registration in the older fixtures (tests/lab_build.py, same method as acc_build): every recorded edit is present "
          "exactly and lab_build.unadapt() gives the file before the edits byte for byte; acc_build.ok() accepts exactly the LAB-1 new "
          "files on top of the ACC files; every LAB-1 new file exists",
          not bad and not missing and all(__import__("acc_build").ok(f) for f in lb.NEW_FILES)
          and not __import__("acc_build").ok("ZoneStrategyXAU.pine"), f"{bad} {missing}")


REG2_BASE = "36087d3"     # the last commit before the LAB-2 registration edits


def registration2():
    import lab2_build as l2
    bad = []
    for path, eds in l2.TEST_EDITS.items():
        cur = raw(path)
        if not all(cur.count(new) == cnt for _, new, cnt in eds):
            bad.append((path, "edit not applied exactly"))
        elif l2.unadapt(path, cur) != git("show", f"{REG2_BASE}:{path}"):
            bad.append((path, "unadapt != the text before the edits"))
    check("LS-12 LAB-2 registration (tests/lab2_build.py, a layer above LFW-1): every recorded edit is present exactly and "
          "lab2_build.unadapt() gives the file before the edits byte for byte; acc_build.ok() (through lab / fds / lfw) accepts "
          "MtfPocFeedXAU.pine and lab2_build.py",
          not bad and all(__import__("acc_build").ok(f) for f in l2.NEW_FILES) and os.path.exists(os.path.join(ROOT, "MtfPocFeedXAU.pine")),
          str(bad))


# ============================================================================
# scenarios
# ============================================================================
def sc_basic():
    # bar 1: POC 2000 (band 1994-2006) arrives; bar 3 touches from below (high 1995) -> SHORT rebound wait
    rows = flat(3) + [(1990, 1995, 1989, 1991)] + [tc_short(1993)] + flat(6, 1985)
    sc = Sc(rows)
    poc(sc, 1, 2000.0)
    sc.hold(4, 5, labS1=1993.0)
    r = sc.run(**ONLY_TC, **QUIET)
    ev = entries(r)
    w = r.trace[3]["waits"]
    o = r["o"]
    check("LB-01 SHORT rebound: POC Zone (2000 +-6) registered on bar 1, wick contact from below on bar 3 = SHORT wait (cat 反発); "
          "TC SHORT rebound on bar 4 -> entry order on bar 4 (fill at bar 5 open), SL = band top 2006 + 5 = 2011",
          w and w[0][1] == -1 and w[0][2] == 1 and w[0][3] == 3 and ev and ev[0][0] == 4 and ev[0][2] == -1 and o.sl == 2011.0
          and r.trace[5]["fill"] == rows[5][0], f"{w} {ev} sl {o.sl}")
    # fixed RR (no zone below): TP = fill - 1.5 x (SL - fill) after the fill is confirmed
    fill = rows[5][0]
    exp_tp = fill - 1.5 * (2011.0 - fill)
    check("LB-02 no Zone in the profit direction -> fixed RR 1.5: provisional TP from the decision close, corrected to the actual fill "
          "on the fill bar (1 leg = 100 %)", abs(r.trace[5]["legPx"][0] - exp_tp) < 1e-9 and r.trace[5]["legLots"][0] == r["o"].lotN
          and abs(r.trace[4]["legPx"][0] - (rows[4][3] - 1.5 * (2011.0 - rows[4][3]))) < 1e-9, str(r.trace[5]["legPx"]))
    # quantity: 9000 JPY / 150 = 60 USD; SL distance from the decision close
    dist = 2011.0 - rows[4][3]
    lots = int(60.0 / (dist * 100 * 0.01) + 1e-9)
    check("LB-03 quantity = floor(60 USD / (SL distance x 100 oz x 0.01)) lots (ACC f_qty), qty = lots x 1 oz",
          o.lotN == lots and abs(ev[0][3] - lots * 1.0) < 1e-9,
          f"lots {o.lotN} exp {lots}")


# contact bar from below for the POC 2000 Zone (band 1994-2006) with price around 1985
TOUCH_A = (1988.0, 1995.0, 1987.0, 1989.0)
TC_AFTER = (1990.0, 1991.0, 1987.5, 1988.0)     # TC SHORT off line 1990.5 right after TOUCH_A (previous close 1989 < 1990.5)
L_AFTER = 1990.5


def short_setup(n_after=20, tc_at=4, touch_at=3, L=1987.0):
    """POC 2000 from bar 1, price 1985, contact from below at touch_at, TC SHORT (line L) at tc_at (None = no TC)."""
    rows = flat(25 + n_after, 1985)
    rows[touch_at] = TOUCH_A
    sc = Sc(rows)
    poc(sc, 1, 2000.0)
    if tc_at is not None:
        prev_c = rows[tc_at - 1][3]
        L = max(L, prev_c + 1.5)          # fresh: the previous close must be below the line
        sc.bars[tc_at].update(o=L - 0.5, h=L + 0.5, l=L - 3.0, c=L - 2.5)
        sc.set(tc_at, labS1=L)
    return sc


def sc_windows():
    # LB-04 wait expiry: contact at 3, TC at 15 (= 3 + 12) -> entry; TC at 16 -> none
    r15 = short_setup(tc_at=15).run(**ONLY_TC, **QUIET)
    r16 = short_setup(tc_at=16).run(**ONLY_TC, **QUIET)
    check("LB-04 wait = last contact + 12 bars: TC on bar 15 (contact 3) enters, TC on bar 16 does not (the wait expired on bar 16)",
          [e[0] for e in entries(r15)] == [15] and entries(r16) == [], f"{entries(r15)} {entries(r16)}")
    # LB-05 re-contact refreshes: contacts 3 and 10 -> TC 22 enters, 23 does not
    def rc(tc):
        sc = short_setup(tc_at=tc)
        sc.bars[10].update(o=1988.0, h=1995.0, l=1987.0, c=1989.0)
        return sc.run(**ONLY_TC, **QUIET)
    r22, r23 = rc(22), rc(23)
    w = r22.trace[10]["waits"]
    check("LB-05 re-contact on bar 10 renews the wait (same wait: start bar 3, last contact 10): TC on bar 22 enters, on bar 23 not",
          [e[0] for e in entries(r22)] == [22] and entries(r23) == [] and w == [("1", -1, 1, 3, 10)], f"{entries(r22)} {entries(r23)} {w}")
    # LB-06 timing before the contact is not used; same bar is used
    sc = short_setup(tc_at=2)
    r = sc.run(**ONLY_TC, **QUIET)
    sc2 = short_setup(tc_at=None)
    sc2.bars[3].update(o=1992.5, h=1995.0, l=1990.0, c=1990.5)
    sc2.bars[2].update(c=1985.1)
    sc2.set(3, labS1=1993.0)
    r2 = sc2.run(**ONLY_TC, **QUIET)
    check("LB-06 a TC rebound before the contact (bar 2, contact 3) is not used (no entry while it is still within 12 bars); a TC on "
          "the contact bar itself is used (entry on bar 3)",
          entries(r) == [] and len(r.trace[3]["tevs"]) == 1 and [e[0] for e in entries(r2)] == [3], f"{entries(r)} {entries(r2)}")
    # LB-07 timing validity 12 bars: contact 3 (+ re-contacts 8, 14 keep the wait), TC 4, entries blocked until bar 16 / 17
    def tv(open_at):
        sc = short_setup(tc_at=4)
        for b in (8, 14):
            sc.bars[b].update(o=1988.0, h=1995.0, l=1987.0, c=1989.0)
        sc.hold(0, open_at, labRangeOK=False)
        return sc.run(**ONLY_TC, **QUIET)
    a, b = tv(16), tv(17)
    check("LB-07 timing = its bar + 12: TC on bar 4 is usable on bar 16 (entry when the test period opens on 16) and not on bar 17 "
          "(no entry); the wait was kept alive by re-contacts", [e[0] for e in entries(a)] == [16] and entries(b) == []
          and a["skipN"][5] > 0, f"{entries(a)} {entries(b)}")


def sc_carry():
    # LONG from support POC 1960 (k=2), TP = the 2nd target (B 2030 k=3), resistance A = POC 2000 (k=1)
    def build(crash_at, extra_flat=0):
        rows = flat(4, 1972)
        rows.append((1970.0, 1971.0, 1965.0, 1969.0))           # 4: contact S from above
        rows.append((1967.5, 1970.0, 1966.5, 1969.5))           # 5: TC LONG (line 1967)
        rows += [(1970 + 4 * i, 1974 + 4 * i, 1969 + 4 * i, 1973 + 4 * i) for i in range(5)]  # 6-10 rising to ~1989
        rows.append((1989.0, 1995.0, 1988.0, 1992.0))           # 11: contact A from below (holding LONG)
        rows.append((1992.5, 1993.5, 1990.0, 1990.5))           # 12: TC SHORT (line 1993)
        rows += flat(extra_flat, 1985)
        rows += [(1985.0, 1986.0, 1974.0, 1975.0), (1975.0, 1976.0, 1960.0, 1961.0)]
        rows.append((1961.0, 1961.5, 1948.0, 1952.0))           # crash: LONG SL 1949
        rows += flat(6, 1950)
        sc = Sc(rows)
        poc(sc, 1, 1960.0, k=2)
        poc(sc, 1, 2000.0, k=1)
        poc(sc, 1, 2030.0, k=3)
        sc.set(5, labS1=1967.0)
        sc.set(12, labS1=1993.0)
        r = sc.run(**ONLY_TC, **QUIET, tpMode="選択した TP で全決済", tpSel=2, beOn=False)
        return r, len(rows) - 7
    r, crash = build(0)
    ev = entries(r)
    held = r["st"].nHoldSkip
    check("LB-08 carry-over: LONG entered on bar 5 (TP = 2nd target 2024); while holding, contact of A (bar 11) + TC SHORT (bar 12) "
          "form a SHORT candidate (counted as 'holding'); the LONG stops out on bar " + str(crash) + " and the SHORT is entered on that "
          "bar (wait 11 / timing 12 still valid)", [(e[0], e[2]) for e in ev] == [(5, 1), (crash, -1)] and held >= 1
          and r.trace[5]["legPx"][0] == 2024.0, f"{ev} held {held} legs {r.trace[6]['legPx']}")
    r2, crash2 = build(0, extra_flat=10)
    ev2 = entries(r2)
    check("LB-09 carry-over ends with the windows: the same path with the stop-out on bar " + str(crash2) + " (> contact 11 + 12) gives "
          "no SHORT (the expired candidate is not revived; the clock ran while holding)", [(e[0], e[2]) for e in ev2] == [(5, 1)], str(ev2))


def sc_conflict():
    # S = POC 1960 (k=2), A = POC 2000 (k=1); one big bar touches both (LONG + SHORT waits), body requirement OFF for a 2-sided TC
    rows = flat(3, 1980)
    rows.append((1980.0, 1995.0, 1965.0, 1980.0))               # 3: contacts both
    rows.append((1980.0, 1983.0, 1977.0, 1980.0))               # 4: TC LONG (1978) and TC SHORT (1982)
    rows.append((1980.5, 2008.0, 1980.0, 2007.0))               # 5: closes above A -> SHORT wait cancelled
    rows += flat(5, 2008)
    sc = Sc(rows)
    poc(sc, 1, 2000.0, k=1)
    poc(sc, 1, 1960.0, k=2)
    sc.set(4, labS1=1978.0, labS2=1982.0)
    r = sc.run(**ONLY_TC, **QUIET, stSatsBody=False, minRR1=0.0)
    ev = entries(r)
    check("LB-10 LONG and SHORT candidates on the same bar (4) -> no entry (conflict counted), both kept; on bar 5 the close above A "
          "cancels the SHORT wait and the LONG (wait 3 + TC 4) is entered", [(e[0], e[2]) for e in ev] == [(5, 1)]
          and r["st"].nConflict == 1 and len(r.trace[4]["waits"]) == 2, f"{ev} {r['st'].nConflict} {r.trace[4]['waits']}")


def sc_roles():
    base = flat(30, 1985)
    # contact 3 (SHORT), break up on 4, back to the Zone from above on 6 -> LONG サポレジ; TC LONG on 7
    def mk(rows_upd, **ov):
        rows = list(base)
        for i, row in rows_upd.items():
            rows[i] = row
        sc = Sc(rows)
        poc(sc, 1, 2000.0)
        return sc
    up = {3: TOUCH_A, 4: (1990.0, 2009.0, 1989.0, 2008.0), 5: (2008.0, 2012.0, 2007.5, 2011.0), 6: (2011.0, 2012.0, 2005.0, 2009.0)}
    for i in range(7, 30):
        up[i] = (2010.0, 2011.0, 2009.0, 2010.1)
    sc = mk({**up, 7: (2008.5, 2011.0, 2007.5, 2010.5)})
    sc.set(7, labS1=2008.0)
    r = sc.run(**ONLY_TC, **QUIET)
    w3, w4, w6 = r.trace[3]["waits"], r.trace[4]["waits"], r.trace[6]["waits"]
    check("LB-11 break: SHORT wait from bar 3 is cancelled by the close above the band (bar 4, Zone kept); the wick back into the band "
          "from above on bar 6 starts a LONG wait = サポレジ転換 (cat 3); TC LONG on bar 7 -> LONG entry",
          w3 and w3[0][1] == -1 and w4 == [] and w6 and w6[0][1] == 1 and w6[0][2] == 3
          and [(e[0], e[2]) for e in entries(r)] == [(7, 1)] and r["lbNZone"][3] == 1, f"{w3} {w4} {w6} {entries(r)}")
    r_off = mk({**up, 7: (2008.5, 2011.0, 2007.5, 2010.5)})
    r_off.set(7, labS1=2008.0)
    r_off = r_off.run(**ONLY_TC, **QUIET, catRole=False)
    check("LB-12 category OFF: サポレジ転換 OFF -> the same LONG candidate is not entered (skip reason 'category'); the wait is still "
          "tracked", entries(r_off) == [] and r_off["skipN"][0] >= 1 and r_off.trace[7]["waits"], f"{entries(r_off)}")
    # fake: after the up-break (bar 4), close back below the band (bar 6) within 24 bars -> SHORT ダマシ wait; TC SHORT bar 7
    fk = {3: TOUCH_A, 4: (1990.0, 2009.0, 1989.0, 2008.0), 5: (2008.0, 2009.0, 2004.0, 2005.0), 6: (2005.0, 2006.0, 1990.0, 1991.0),
          7: (1992.5, 1993.5, 1990.0, 1990.5)}
    sc = mk(fk)
    sc.set(7, labS1=1993.0)
    r = sc.run(**ONLY_TC, **QUIET)
    w6 = r.trace[6]["waits"]
    check("LB-13 ダマシ: up-break on bar 4, close back below the band on bar 6 (no window by default) -> SHORT wait cat 2 starting on "
          "bar 6 (no wick contact needed beyond the crossing bar); TC SHORT on bar 7 -> SHORT entry",
          w6 and w6[0][1] == -1 and w6[0][2] == 2 and w6[0][3] == 6 and [(e[0], e[2]) for e in entries(r)] == [(7, -1)], f"{w6} {entries(r)}")
    sc = mk(fk)
    sc.set(7, labS1=1993.0)
    r = sc.run(**ONLY_TC, **QUIET, fakeWin=1)
    w6 = r.trace[6]["waits"]
    far = {3: TOUCH_A, 4: (1990.0, 2009.0, 1989.0, 2008.0)}
    for i in range(5, 45):
        far[i] = (2010.0, 2011.0, 2009.0, 2010.1)
    far[45] = (2010.0, 2010.5, 1990.0, 1991.0)
    rows = flat(50, 1985)
    for i, row in far.items():
        rows[i] = row
    scf = Sc(rows)
    poc(scf, 1, 2000.0)
    rf = scf.run(**ONLY_TC, **QUIET)
    wf = rf.trace[45]["waits"]
    check("LB-13b ダマシ has no window by default (fakeWin 0): the close back below 41 bars after the up-break is still a fake (cat 2), "
          "independent of the 12-bar wait", wf and wf[0][2] == 2 and wf[0][3] == 45, str(wf))
    sc = mk(fk)
    sc.set(7, labS1=1993.0)
    rb = sc.run(**ONLY_TC, **QUIET, fakeWin=2)
    wb = rb.trace[6]["waits"]
    check("LB-14b ダマシ window boundary (fakeWin 2): the close back below exactly 2 bars after the break is still a fake (cat 2)",
          wb and wb[0][2] == 2, str(wb))
    check("LB-14 ダマシ window (fakeWin 1): the same close back below 2 bars after the break is a new down-break (no wait on that bar, "
          "brk = -1); no entry from the TC on bar 7 (no wait)", w6 == [] and entries(r) == [] and r["lbZs"][0].brk == -1, f"{w6} {entries(r)}")
    # gap across the band without a wick contact still cancels (range from the previous close)
    gp = {3: TOUCH_A, 4: (2010.0, 2012.0, 2008.0, 2011.0)}
    for i in range(5, 30):
        gp[i] = (2011.0, 2012.0, 2010.0, 2011.1)
    r = mk(gp).run(**ONLY_TC, **QUIET)
    check("LB-15 a gap over the band (bar 4 low 2008 > top 2006) is still a close above it: the SHORT wait is cancelled and the Zone "
          "is now below price (pos 1, brk 1)", r.trace[3]["waits"] and r.trace[4]["waits"] == [] and r["lbZs"][0].pos == 1
          and r["lbZs"][0].brk == 1)


def sc_combo():
    # POC 2000 (1994-2006) and Swing High 2008 (k=1, 2002-2014): overlap 2002-2006
    def mk(touch_hi, **ov):
        rows = flat(20, 1985)
        rows[3] = (1988.0, touch_hi, 1987.0, 1989.0)
        rows[4] = TC_AFTER
        sc = Sc(rows)
        poc(sc, 1, 2000.0)
        sc.hold(1, None, s1h=2008.0, s1ht=T0 - 3600_000)
        sc.set(4, labS1=L_AFTER)
        return sc.run(**ONLY_TC, **QUIET, **ov)
    AND = dict(cZA=False, cZB=False, cZC=True, cZD=True, cZF=False, cComb="AND")
    r1 = mk(1997.0, **AND)
    r2 = mk(2003.0, **AND)
    r3 = mk(1997.0, cZA=False, cZB=False, cZC=True, cZD=True, cZF=False, cComb="OR")
    w2 = r2.trace[3]["waits"]
    check("LB-16 AND (POC + Swing): a contact of the POC band only (high 1997 < overlap 2002) makes no AND wait / no entry; a contact "
          "of the overlap (high 2003) makes one wait for the pair and the entry's SL is outside the whole selected bands (2014 + 5 = 2019)",
          entries(r1) == [] and r1.trace[3]["waits"] == [] and len(w2) == 1 and "|" in w2[0][0] and [e[0] for e in entries(r2)] == [4]
          and r2["o"].sl == 2019.0, f"{r1.trace[3]['waits']} {w2} {entries(r2)} sl {r2['o'].sl}")
    rows = flat(20, 1985)
    rows[3] = (1990.0, 2015.0, 1989.0, 1991.0)
    rows[4] = (1992.5, 1993.5, 1990.0, 1990.5)
    scn = Sc(rows)
    poc(scn, 1, 2000.0)
    scn.hold(1, None, s1h=2020.0, s1ht=T0 - 3600_000)
    scn.set(4, labS1=1993.0)
    rn = scn.run(**ONLY_TC, **QUIET, **AND)
    check("LB-16b AND needs a real overlap: POC 1994-2006 and Swing 2014-2026 both touched by one bar (high 2015) but not overlapping "
          "-> no AND wait, no entry", rn.trace[3]["waits"] == [] and entries(rn) == [], f"{rn.trace[3]['waits']} {entries(rn)}")
    rows = [(2003.0, 2004.0, 2002.5, 2003.1), (2003.0, 2004.0, 2002.5, 2003.0), (2003.0, 2003.5, 1989.5, 1990.0),
            (1990.0, 1995.0, 1989.5, 1991.0)] + flat(6, 1991)
    scm = Sc(rows)
    scm.hold(1, None, s1h=1996.0, s1ht=T0 - 3600_000)        # Swing 1990-2002 registered with the close above it (LONG side)
    poc(scm, 2, 2000.0)                                      # POC 1994-2006 registered with the close below it (SHORT side)
    rm = scm.run(**ONLY_TC, **QUIET, **AND)
    wm = rm.trace[3]["waits"]
    check("LB-16c AND needs one direction: the Swing (price came from above, LONG) and the POC (price below, SHORT) overlap and bar 3 "
          "touches the overlap, but the directions differ -> no AND wait", wm == [], str(wm))
    check("LB-17 OR with the same two types: the POC-only contact (high 1997) is a wait / entry (SL 2006 + 5)",
          [e[0] for e in entries(r3)] == [4] and r3["o"].sl == 2011.0, f"{entries(r3)}")
    # only vs includes: MA 2000 (1994-2006) alone vs MA + overlapping POC 2009 (2003-2015)
    def mk2(scope, poc_c):
        rows = flat(20, 1985)
        rows[3] = (1988.0, 1995.0, 1987.0, 1989.0)
        rows[4] = TC_AFTER
        sc = Sc(rows)
        sc.hold(0, None, zbMa1=2000.0)
        if poc_c is not None:
            poc(sc, 1, poc_c)
        sc.set(4, labS1=L_AFTER)
        return sc.run(**ONLY_TC, dsZone=False, dsEnt=False, zbUse2=False, cZA=False, cZB=True, cZC=False, cZD=False, cZF=False, cScope=scope)
    a, b, c = mk2("だけ", 2009.0), mk2("含む", 2009.0), mk2("だけ", 2025.0)
    check("LB-18 'MA だけ' excludes the MA wait when another type's Zone overlaps the MA band at all (POC 2003-2015 vs MA 1994-2006): "
          "no entry (skip 'only'); 'MA を含む' enters; 'MA だけ' with the POC away (2019-2031) enters",
          entries(a) == [] and a["skipN"][1] >= 1 and [e[0] for e in entries(b)] == [4] and [e[0] for e in entries(c)] == [4]
          and b["o"].omask == 8 and c["o"].omask == 0, f"{entries(a)} {entries(b)} {entries(c)}")


def sc_fvg():
    K1, K2, K3, K4 = T0 - 7200_000, T0 + 3600_000, T0 + 7200_000, T0 + 10800_000
    rows = flat(14, 2005)
    rows[3] = (2003.0, 2004.0, 1995.0, 2002.0)      # touches the bullish FVG 1990-1996 from above -> LONG wait
    sc = Sc(rows)
    sc.hold(1, 5, g1k=K1, g1c=2006.0, g1d=1, g1t=1996.0, g1b=1990.0)
    sc.hold(5, 9, g1k=K2, g1c=1993.0, g1d=0)         # 1H close inside the gap: still an FVG
    sc.hold(9, 11, g1k=K3, g1c=1985.0, g1d=0)        # 1H close below the bottom -> iFVG
    sc.hold(11, None, g1k=K4, g1c=1998.0, g1d=0)     # 1H close above the top of the iFVG -> invalid
    r = sc.run(**ONLY_TC, **QUIET)
    z = r.trace and r["lbFvgs"]
    w3 = r.trace[3]["waits"]
    check("LB-19 ZF: the 1H FVG is a Zone with its own bounds (1990-1996, no common width); contact from above = LONG wait",
          w3 and w3[0][1] == 1 and r["st"].nIfvg == 1, f"{w3}")
    r8 = lp.Runner(overrides=dict(**ONLY_TC, **QUIET)).run(sc.bars[:9])
    r10 = lp.Runner(overrides=dict(**ONLY_TC, **QUIET)).run(sc.bars[:11])
    z8 = r8["lbFvgs"][0]
    z10 = r10["lbFvgs"][0]
    check("LB-20 iFVG: a 1H close inside the gap (bar 5, 1993) keeps the FVG; the new 1H bar on bar 9 closing below the bottom "
          "(1985) turns it into an iFVG (counted once: the same key on bar 10 is not re-evaluated); the new 1H bar on bar 11 closing "
          "above the top (1998) invalidates it: removed from the Zone lists (0 ZF held) and its waits are cancelled",
          not z8.inv and z10.inv and not z10.dead and r10["st"].nIfvg == 1 and r10["st"].nFvgDead == 0 and len(r10["lbFvgs"]) == 1
          and r["st"].nIfvg == 1 and r["st"].nFvgDead == 1 and r["lbFvgs"] == [] and r["lbZs"] == [] and r["lbNZone"][4] == 0
          and r.trace[10]["waits"] != [] and r.trace[11]["waits"] == [],
          f"inv8 {z8.inv} inv10 {z10.inv} ifvg {r['st'].nIfvg} dead {r['st'].nFvgDead} w10 {r.trace[10]['waits']} w11 {r.trace[11]['waits']}")


def sc_fvg_display():
    # the LB-19/20 FVG with an overlapping 1H POC (1991-2003): one band; iFVG renamed in place; invalid -> it leaves the band (the POC
    # band is redrawn alone) and stays as a grey ended band (LAB-2 look); trading identical with the display OFF
    K1, K2, K3, K4 = T0 - 7200_000, T0 + 3600_000, T0 + 7200_000, T0 + 10800_000
    sc = Sc(flat(14, 2005))
    sc.hold(1, 5, g1k=K1, g1c=2006.0, g1d=1, g1t=1996.0, g1b=1990.0)
    sc.hold(5, 9, g1k=K2, g1c=1993.0, g1d=0)
    sc.hold(9, 11, g1k=K3, g1c=1985.0, g1d=0)
    sc.hold(11, None, g1k=K4, g1c=1998.0, g1d=0)
    poc(sc, 1, 1997.0)
    run = lambda n, ds: lp.Runner(overrides=dict(**ONLY_TC, **dict(QUIET, dsZone=ds))).run(sc.bars[:n])
    r8, r10, r = run(9, True), run(11, True), run(14, True)
    off = run(14, False)
    txt = lambda rr: [g.lb.text for g in rr["lbDsG"] if not g.gone]
    gone = [g for g in r["lbDsG"] if g.gone]
    check("LB-20b display of FVG changes: FVG 1990-1996 overlapping a 1H POC 1991-2003 is not merged (FVG on its own band with its own "
          "bounds); after the iFVG flip its band is renamed ('1時間足｜iFVG'); after the invalidation it stays as a grey ended "
          "band (extend none, its name in the ended band) and the POC band is unchanged; display OFF gives the same trading",
          sorted(txt(r8)) == ["1時間足｜FVG", "1時間足｜出来高POC"] and ds_groups(r8.env) == [(1990.0, 1996.0, [ds_groups(r8.env)[0][2][0]]), (1991.0, 2003.0, ds_groups(r8.env)[1][2])]
          and sorted(txt(r10)) == ["1時間足｜iFVG", "1時間足｜出来高POC"] and txt(r) == ["1時間足｜出来高POC"]
          and ds_groups(r.env)[0][:2] == (1991.0, 2003.0) and len(gone) == 1 and gone[0].bx.kw.get("extend") == "none"
          and r.trace == off.trace and r.broker.log == off.broker.log, f"{txt(r8)} {txt(r10)} {txt(r)} {len(gone)}")


def partial_setup(zones, rows_after, **ov):
    """SHORT from POC 2000: contact 3 (close inside 1999), TC 4 (line 2001) -> close 1998.5, SL 2011, slw 12.5 -> 4 lots.
    zones: list of (k, centre) POC Zones below (TP targets)."""
    rows = flat(3, 1985) + [(1990.0, 1999.5, 1989.0, 1999.0), (2000.5, 2001.5, 1998.0, 1998.5)] + rows_after
    sc = Sc(rows)
    poc(sc, 1, 2000.0)
    for k, c in zones:
        poc(sc, 1, c, k=k)
    sc.set(4, labS1=2001.0)
    return sc.run(**ONLY_TC, **QUIET, **ov)


def sc_partial():
    after = [(1998.0, 1999.0, 1985.0, 1986.0), (1986.0, 1987.0, 1964.0, 1965.0), (1965.0, 1966.0, 1944.0, 1945.0),
             (1945.0, 1946.0, 1924.0, 1925.0)] + flat(4, 1925)
    r = partial_setup([(2, 1960.0), (3, 1940.0), (4, 1920.0)], after)
    t4 = r.trace[4]
    cl = [c for c in r.broker.closed if c["id"] == "S1"]
    led = r["bkN"][0]
    check("LB-21 3 targets (POC tops 1966 / 1946 / 1926), 4 lots: legs 60 / 20 / 20 % -> cumulative floor 2 / 3 / 4 = 2 + 1 + 1 lots, "
          "placed with the entry (same stop 2011)", t4["legPx"] == [1966.0, 1946.0, 1926.0] and t4["legLots"] == [2, 1, 1]
          and [l for l in r.broker.log if l[0] == "order_exit" and l[1] == 4][0][4] == 2.0, f"{t4['legPx']} {t4['legLots']}")
    check("LB-22 the three partial exits fill at 1966 / 1946 / 1926 (2 + 1 + 1 lots) and are one trade in the ledger "
          "(1 entry -> 3 closed records; ledger count 1; net = sum of the 3 profits); the completed stage is never re-planned",
          [(c["exit_price"], c["qty"]) for c in cl] == [(1966.0, 2.0), (1946.0, 1.0), (1926.0, 1.0)] and led == 1
          and abs(r["bkNet"][0] - sum(c["profit"] for c in cl)) < 1e-6 and r["st"].nTrades == 1
          and r.trace[6]["legLots"] == [0, 1, 1] and r.trace[7]["legLots"] == [0, 0, 1], f"{[(c['exit_price'], c['qty']) for c in cl]} {led}")
    rows3 = flat(3, 1985) + [(1990.0, 1999.5, 1989.0, 1992.0), (1993.0, 1994.0, 1990.5, 1991.0)] + flat(4, 1991)
    sc3 = Sc(rows3)
    poc(sc3, 1, 2000.0)
    for k, c in [(2, 1960.0), (3, 1940.0), (4, 1920.0)]:
        poc(sc3, 1, c, k=k)
    sc3.set(4, labS1=1993.5)
    r3 = sc3.run(**ONLY_TC, **QUIET)
    check("LB-21b 3 lots (SL distance 20): cumulative round(1.8) = 2, round(2.4) = 2, 3 -> legs 2 / 0 / 1 (the 0 stage has no order; "
          "total unchanged, the last stage closes the rest)", r3.trace[4]["legLots"] == [2, 0, 1] and r3["o"].lotN == 3,
          f"{r3.trace[4]['legLots']} {r3['o'].lotN}")
    r2 = partial_setup([(2, 1960.0), (3, 1940.0)], after)
    r1 = partial_setup([(2, 1960.0)], after)
    r0 = partial_setup([], after)
    fill = r0.trace[5]["fill"]
    check("LB-23 2 targets -> 60 % / rest (2 + 2 lots); 1 target -> 100 % (4 lots); 0 targets -> fixed RR 1.5 from the actual fill",
          r2.trace[4]["legLots"] == [2, 2, 0] and r1.trace[4]["legLots"] == [4, 0, 0]
          and abs(r0.trace[5]["legPx"][0] - (fill - 1.5 * (2011.0 - fill))) < 1e-9 and r0.trace[5]["legLots"] == [4, 0, 0],
          f"{r2.trace[4]['legLots']} {r1.trace[4]['legLots']} {r0.trace[5]['legPx']}")
    # min RR to TP1: a target at 1996 (POC 1990) -> RR (1998.5 - 1996) / 12.5 = 0.2
    rr = partial_setup([(2, 1990.0)], flat(8, 1998.5))
    rr0 = partial_setup([(2, 1990.0)], flat(8, 1998.5), minRR1=0.0)
    check("LB-24 TP1 RR below 1.0 is skipped (skip 'RR') on every bar while price stays there, and entered with min RR 0",
          entries(rr) == [] and rr["skipN"][3] >= 1 and [e[0] for e in entries(rr0)] == [4], f"{entries(rr)} {entries(rr0)}")
    # dynamic TP + notification: a nearer Zone appears while holding (POC 1975 -> top 1981): TP1 moves 1966 -> 1981 (>= 5 -> notify)
    hold_rows = [(1998.0, 1999.0, 1990.0, 1991.0)] + flat(3, 1990) + flat(6, 1990)
    rows = flat(3, 1985) + [(1990.0, 1999.5, 1989.0, 1999.0), (2000.5, 2001.5, 1998.0, 1998.5)] + hold_rows
    sc = Sc(rows)
    poc(sc, 1, 2000.0)
    poc(sc, 1, 1960.0, k=2)
    sc.hold(7, None, **pocv(3, 1974.5, 1975.5))
    sc.hold(10, None, **pocv(4, 1976.5, 1977.5))
    sc.set(4, labS1=2001.0)
    r = sc.run(**ONLY_TC, **QUIET)
    ntf = [a for a in r.alerts if "TP 変更" in a[1]]
    check("LB-25 TP is re-planned on every confirmed bar while holding: a new POC Zone (1969-1981) on bar 7 becomes TP1 (1981, TP2 1966, "
          "2 targets -> 60 / 40); one change notification (moved 15 >= 5); the POC 1977 (1971-1983) on bar 10 overlaps it -> one band, "
          "its upper edge 1983 is TP1 (moved 2 < 5 -> no second notification)",
          r.trace[6]["legPx"][0] == 1966.0 and r.trace[7]["legPx"][:2] == [1981.0, 1966.0] and r.trace[10]["legPx"][:2] == [1983.0, 1966.0]
          and len(ntf) == 1 and ntf[0][0] == 7, f"{[t['legPx'] for t in r.trace[5:12]]} {ntf}")


def sc_qty_table():
    """the Pine f_lbPlan itself (targets stubbed): legs for N = 1..10 lots with 3 / 2 / 1 targets (documented table, 5A)."""
    import math
    r = lp.Runner(overrides=dict(QUIET)).run(Sc(flat(1, 1985)).bars)
    e = r.env
    got3, got2, got1, exp3, exp2 = [], [], [], [], []
    for n in range(1, 11):
        for tps, out in (([1980.0, 1970.0, 1960.0], got3), ([1980.0, 1970.0], got2), ([1980.0], got1)):
            o = e["o"]
            o.side, o.sl, o.lotN, o.closedLots, o.stage = -1, 2000.0, n, 0, 0
            e["f_lbTargets"] = lambda side, ref, tps=tps: list(tps)
            e["f_lbPlan"](1990.0, 1990.0)
            out.append(list(o.legLots))
        c1, c2 = math.floor(0.6 * n + 0.5), math.floor(0.8 * n + 0.5)
        exp3.append([c1, c2 - c1, n - c2])
        exp2.append([c1, n - c1, 0])
    o = e["o"]
    o.side, o.sl, o.lotN, o.closedLots, o.stage = -1, 2000.0, 10, 0, 0
    e.update(tpW1=50.0, tpW2=30.0, tpW3=20.0)
    e["f_lbTargets"] = lambda side, ref: [1980.0, 1970.0, 1960.0]
    e["f_lbPlan"](1990.0, 1990.0)
    alt = list(o.legLots)
    check("LB-40b the ratios stay inputs: 50 / 30 / 20 with 10 lots -> 5 / 3 / 2", alt == [5, 3, 2], str(alt))
    check("LB-40 partial quantities (plan A, f_lbPlan): legs = differences of the cumulative round(0.6N) / round(0.8N) / N for 3 "
          "targets, round(0.6N) / rest for 2, N for 1 - e.g. N=1 -> 1/0/0, 2 -> 1/1/0, 3 -> 2/0/1, 6 -> 4/1/1, 10 -> 6/2/2; the sum is "
          "always N", got3 == exp3 and got2 == exp2 and got1 == [[n, 0, 0] for n in range(1, 11)]
          and all(sum(g) == n + 1 for n, g in enumerate(got3))
          and got3[0] == [1, 0, 0] and got3[1] == [1, 1, 0] and got3[2] == [2, 0, 1] and got3[5] == [4, 1, 1], f"{got3} {got2}")


def sc_tp_mixed():
    # SHORT targets: a wide 1H bearish FVG 1940-1975 overlapping POC 1960 (1954-1966) = one band (upper edge 1975), POC 1920 (top 1926)
    after = flat(6, 1998.5)
    rows = flat(3, 1985) + [(1990.0, 1999.5, 1989.0, 1999.0), (2000.5, 2001.5, 1998.0, 1998.5)] + after
    sc = Sc(rows)
    poc(sc, 1, 2000.0)
    poc(sc, 1, 1960.0, k=2)
    poc(sc, 1, 1920.0, k=3)
    sc.hold(1, None, g1k=T0 - 7200_000, g1c=1930.0, g1d=-1, g1t=1975.0, g1b=1940.0)
    sc.set(4, labS1=2001.0)
    r = sc.run(**ONLY_TC, **QUIET, **ONLY_ZD)
    check("LB-25b TP bands across both Zone lists: a wide FVG (1940-1975) overlapping the POC band 1954-1966 is one band (TP1 = its "
          "upper edge 1975), the POC 1914-1926 is TP2 (1926); 2 targets -> 60 / 40; the FVG is a target although ZF is not chosen "
          "for the entry condition", r.trace[4]["legPx"][:2] == [1975.0, 1926.0] and r.trace[4]["legLots"] == [2, 2, 0],
          f"{r.trace[4]['legPx']} {r.trace[4]['legLots']}")


def sc_be():
    # SHORT fill 1998 (bar 5 open), BE fixed 15 -> trigger 1983 (low 1982 on bar 6) -> stop to the fill from bar 7
    after = [(1998.0, 1999.0, 1990.0, 1991.0), (1991.0, 1992.0, 1982.0, 1984.0), (1984.0, 1999.0, 1983.0, 1998.5)] + flat(12, 1999)
    r = partial_setup([(2, 1960.0)], after)
    fill = r.trace[5]["fill"]
    cl = [c for c in r.broker.closed if c["id"] == "S1"]
    check("LB-26 breakeven (fixed 15): low reaches fill - 15 on bar 6 -> stop = fill from the next bar; bar 7 returns to the fill -> "
          "exit at the fill (1 trade, profit 0 = 建値 bucket, not in the win-rate denominator)",
          r.trace[6]["be"] and r.trace[6]["stop"] == fill and cl and cl[0]["exit_price"] == fill and r["bkBE"][0] == 1
          and r["bkW"][0] == 0 and r["bkL"][0] == 0, f"{r.trace[6]['stop']} {cl}")
    # BE ratio on TP1 at entry (1966): trigger = fill - 0.5 x (fill - 1966) = 1982; later TP updates do not move it
    rr = partial_setup([(2, 1960.0)], [(1998.0, 1999.0, 1990.0, 1991.0), (1991.0, 1992.0, 1983.0, 1984.0)] + flat(8, 1990),
                       beMode="TP1 割合")
    check("LB-27 breakeven 'TP1 割合' 50 %: base = TP1 at entry (1966) -> trigger 1982; low 1983 does not trigger",
          not any(t["be"] for t in rr.trace) and rr["o"].tp1E == 1966.0)
    # lock after a BE exit (beLock ON): new contact + TC inside the lock -> no entry, waits cleared; release when the last TP (1966)
    # or the initial SL (2011) is reached (release bar still blocked)
    lk_after = after[:3] + [(1998.5, 1999.0, 1990.0, 1991.0), (1991.0, 1999.5, 1990.0, 1999.0), (2000.5, 2001.5, 1998.0, 1998.5),
                            (1998.5, 1999.0, 1990.0, 1991.0), (1991.0, 2012.0, 1990.0, 1999.0), (1999.0, 1999.5, 1990.0, 1999.0),
                            (2000.5, 2001.5, 1998.0, 1998.5)] + flat(5, 1999)
    rows = flat(3, 1985) + [(1990.0, 1999.5, 1989.0, 1999.0), (2000.5, 2001.5, 1998.0, 1998.5)] + lk_after
    sc = Sc(rows)
    poc(sc, 1, 2000.0)
    poc(sc, 1, 1960.0, k=2)
    for b in (4, 10, 14):
        sc.set(b, labS1=2001.0)
    r = sc.run(**ONLY_TC, **QUIET, beLock=True)
    ev = [e[0] for e in entries(r)]
    r0 = sc.run(**ONLY_TC, **QUIET, beLock=False)
    check("LB-28 BE lock: after the BE exit on bar 7 the contact 9 + TC 10 are not entered and the waits are cleared on the blocked bars; "
          "bar 12 reaches the initial SL 2011 -> released (still blocked on 12); the contact 13 + TC 14 enter (the TC of bar 10 is "
          "before that wait and is not used). Lock OFF: bar 10 enters",
          ev == [4, 14] and r["st"].nLockClr >= 1 and r.trace[12]["waits"] == [] and r.trace[13]["waits"]
          and [e[0] for e in entries(r0)][:2] == [4, 10], f"{ev} clr {r['st'].nLockClr} off {entries(r0)}")


def sc_lock_far():
    # SHORT 4 lots, targets 1966 / 1946 / 1926 (legs 2 / 1 / 1). Bar 6: TP1 filled and BE triggered; bar 7: the 2 remaining lots exit at
    # the fill (BE) -> lock; the target is the farthest open TP (1926, fixed at the lock start), not the nearest (1946)
    after = [(1998.0, 1999.0, 1985.0, 1986.0), (1986.0, 1987.0, 1964.0, 1965.0), (1965.0, 1999.0, 1964.0, 1998.5),
             (1998.5, 1999.0, 1990.0, 1995.0), (1995.0, 1996.0, 1990.0, 1991.0), (1991.0, 1992.0, 1945.0, 1946.0),
             (1946.0, 1947.0, 1925.0, 1926.0)] + flat(4, 1926)
    r = partial_setup([(2, 1960.0), (3, 1940.0), (4, 1920.0)], after, beLock=True)
    lk = [(t["bar"], t["state"]) for t in r.trace]
    r10 = lp.Runner(overrides=dict(**ONLY_TC, **QUIET, beLock=True))
    rows = flat(3, 1985) + [(1990.0, 1999.5, 1989.0, 1999.0), (2000.5, 2001.5, 1998.0, 1998.5)] + after
    sc = Sc(rows)
    poc(sc, 1, 2000.0)
    for k, c in [(2, 1960.0), (3, 1940.0), (4, 1920.0)]:
        poc(sc, 1, c, k=k)
    sc.set(4, labS1=2001.0)
    r10.run(sc.bars[:11])
    r11 = lp.Runner(overrides=dict(**ONLY_TC, **QUIET, beLock=True)).run(sc.bars[:12])
    cl = [(c["exit_price"], c["qty"]) for c in r.broker.closed]
    check("LB-28b BE lock target = the final TP (farthest open leg) fixed at the lock start: after TP1 (2 lots at 1966) and the BE exit of "
          "the other 2 lots (bar 7), lkTP = 1926 (not the nearest open leg 1946); reaching 1946 (bar 10) keeps the lock, reaching 1926 "
          "(bar 11) releases it", cl == [(1966.0, 2.0), (1998.0, 1.0), (1998.0, 1.0)] and r10["lkTP"] == 1926.0 and r10["lkOn"]
          and not r11["lkOn"] and r10["lkSL"] == 2011.0, f"{cl} lkTP {r10['lkTP']} on10 {r10['lkOn']} on11 {r11['lkOn']}")


def sc_and_only_sel():
    # #6: AND (POC + Swing) + "だけ": the selected types overlapping each other are not excluded; another type (a 1H FVG 2010-2018)
    # overlapping the whole selected span 1994-2014 excludes it
    def mk(fvg):
        rows = flat(20, 1985)
        rows[3] = (1988.0, 2003.0, 1987.0, 1989.0)
        rows[4] = TC_AFTER
        sc = Sc(rows)
        poc(sc, 1, 2000.0)
        sc.hold(1, None, s1h=2008.0, s1ht=T0 - 3600_000)
        if fvg:
            sc.hold(1, None, g1k=T0 - 7200_000, g1c=2030.0, g1d=1, g1t=2018.0, g1b=2010.0)
        sc.set(4, labS1=L_AFTER)
        return sc.run(**ONLY_TC, **QUIET, cZA=False, cZB=False, cZC=True, cZD=True, cZF=False, cComb="AND", cScope="だけ")
    a, b = mk(False), mk(True)
    check("LB-18b AND + 'だけ': POC and Swing (both selected) overlapping each other enter; a non-selected FVG (2010-2018) touching the "
          "whole selected span (1994-2014, outside the POC / Swing overlap 2002-2006) excludes the wait (skip 'only')",
          [e[0] for e in entries(a)] == [4] and entries(b) == [] and b["skipN"][1] >= 1, f"{entries(a)} {entries(b)}")


def sc_sel_tp():
    # #12: 'close all at the chosen TP' with TP 3 chosen: 2 targets -> the farthest existing (1946); none -> fixed RR from the fill
    after = flat(6, 1998.5)
    r2 = partial_setup([(2, 1960.0), (3, 1940.0)], after, tpMode="選択した TP で全決済", tpSel=3)
    r0 = partial_setup([], after, tpMode="選択した TP で全決済", tpSel=3)
    fill = r0.trace[5]["fill"]
    check("LB-23b chosen TP 3 with only 2 targets -> full exit at the farthest existing target (1946, all 4 lots); no target -> fixed RR "
          "1.5 from the actual fill", r2.trace[5]["legPx"][0] == 1946.0 and r2.trace[5]["legLots"] == [4, 0, 0]
          and abs(r0.trace[5]["legPx"][0] - (fill - 1.5 * (2011.0 - fill))) < 1e-9, f"{r2.trace[5]['legPx']} {r0.trace[5]['legPx']}")


def sc_consume():
    # two Zones on top of each other: Swing High 2001 (k=1, id 1) and POC 2000 (k=1, id 2); OR -> two waits; one TC -> one entry
    # (the nearer Zone = POC); TP = POC 1960 (k=2) top 1966 (RR 0.96 -> min RR 0.5 for this test) hit on bar 5
    rows = flat(3, 1985) + [TOUCH_A, TC_AFTER, (1988.0, 1988.5, 1964.0, 1965.0)] + flat(3, 1975)
    rows += [(1980.0, 1995.0, 1979.0, 1989.0), TC_AFTER] + flat(6, 1988)
    sc = Sc(rows)
    poc(sc, 1, 2000.0)
    poc(sc, 1, 1960.0, k=2)
    sc.hold(1, None, s1h=2001.0, s1ht=T0 - 3600_000)
    sc.set(4, labS1=L_AFTER)
    sc.set(10, labS1=L_AFTER)
    r = sc.run(**ONLY_TC, **QUIET, cZC=True, minRR1=0.5)
    ev = entries(r)
    t4 = r.trace[4]
    check("LB-29 consumption: on the entry bar (4) the used TC is marked used and the traded wait (POC, the nearer Zone) is removed; "
          "the Swing wait stays but cannot use the same TC (no entry after the TP exit on bar 5 while it is still valid); a new contact "
          "(bar 9) and a new TC (bar 10) enter again on the traded Zone",
          [e[0] for e in ev] == [4, 10] and [w[0] for w in t4["waits"]] == ["1"] and t4["tevs"] == [(2, -1, 4, True)]
          and r.trace[5]["state"] == 0 and r["bkN"][0] >= 1 and r["o"].tmask == 8, f"{ev} {t4['waits']} {t4['tevs']}")


def sc_dup_swing():
    # two 1H Swing Highs at the same price (two pivots) -> two Zones, one contact -> two waits; one TC -> one order, one ledger trade
    rows = flat(3, 1985) + [TOUCH_A, TC_AFTER] + flat(10, 1988)
    sc = Sc(rows)
    sc.hold(1, 2, s1h=2000.0, s1ht=T0 - 7200_000)
    sc.hold(2, None, s1h=2000.0, s1ht=T0 - 3600_000)
    sc.set(4, labS1=L_AFTER)
    r = sc.run(**ONLY_TC, **QUIET)
    zc = [z for z in r["lbZs"] if z.typ == 2]
    ev = entries(r)
    check("LB-41 duplicates: two Swing Zones at the same price both get waits from one contact, but one TC gives one order (bar 4), "
          "the TC is consumed so the other wait cannot place a second order, and the trade is one ledger entry",
          len(zc) == 2 and len(r.trace[3]["waits"]) == 2 and [e[0] for e in ev] == [4] and len(r.trace[4]["waits"]) == 1
          and r.trace[4]["tevs"] == [(2, -1, 4, True)], f"{len(zc)} {r.trace[3]['waits']} {ev}")


NEW = dict(zHalf=2.0, zcMerge=5.0)     # LAB-3e defaults (common width +-2, swing merge distance 5)


def sw_feed(sc, i, tf, hi, price, k_off):
    """one new swing pivot of TF tf (1..4), high (hi=True) or low, registered on bar i (time key = T_HTF - k_off hours)"""
    s = "h" if hi else "l"
    sc.set(i, **{f"s{tf}{s}": price, f"s{tf}{s}t": T_HTF - k_off * 3600_000})
    return sc


def swz(r):
    return [z for z in r["lbZs"] if z.typ == 2]


def sc_swing_merge():
    # distance boundary / chain / bridge (zHalf 2, distance 5): 4300 / 4304 / 4308 -> one Zone 4298-4310
    def run(pivots, n=8, **ov):
        sc = Sc(flat(n, 4250))
        for i, tf, hi, p, ko in pivots:
            sw_feed(sc, i, tf, hi, p, ko)
        return sc.run(**ONLY_TC, **{**QUIET, **NEW, **ov})
    r1 = run([(1, 1, True, 4300.0, 1), (2, 2, False, 4304.0, 2), (3, 3, True, 4308.0, 3)])
    z1 = swz(r1)
    r2 = run([(1, 1, True, 4300.0, 1), (2, 2, True, 4305.0, 2)])
    r3 = run([(1, 1, True, 4300.0, 1), (2, 2, True, 4305.5, 2)])
    r4 = run([(1, 1, True, 4300.0, 1), (2, 2, True, 4309.0, 2), (4, 3, False, 4304.5, 3)])
    z4 = swz(r4)
    r5 = run([(1, 1, True, 4300.0, 1), (2, 2, True, 4304.0, 2), (3, 3, True, 4308.0, 3)], zHalf=6.0, zcMerge=-1.0)
    check("LB-53 swing merge (common width 2, distance 5): 4300 (1H high) / 4304 (4H low) / 4308 (D high) chain into one Zone "
          "4298-4310 that keeps the members' TF / price / pivot time / ID; distance exactly 5 merges, 5.5 does not; a new 4304.5 "
          "between 4300 and 4309 bridges both into the older Zone (one Zone 4298-4311, the other dead); negative distance = no merge",
          len(z1) == 1 and (z1[0].bot, z1[0].top) == (4298.0, 4310.0) and list(z1[0].mP) == [4300.0, 4304.0, 4308.0]
          and list(z1[0].mTf) == [0, 1, 2] and len(set(z1[0].mId)) == 3 and list(z1[0].mT) == [T_HTF - 3600_000, T_HTF - 7200_000, T_HTF - 10800_000]
          and r1["lbNZone"][2] == 1 and r1["st"].nSwMerge == 2
          and len(swz(r2)) == 1 and len(swz(r3)) == 2
          and len(z4) == 1 and (z4[0].bot, z4[0].top) == (4298.0, 4311.0) and sorted(z4[0].mP) == [4300.0, 4304.5, 4309.0]
          and z4[0].id == min(z.id for z in swz(run([(1, 1, True, 4300.0, 1), (2, 2, True, 4309.0, 2)]))) and r4["lbNZone"][2] == 1
          and len(swz(r5)) == 3 and [z.id for z in r4["lbZs"]] == [z.id for z in r4["lbZsT"]],
          f"{[(z.bot, z.top, list(z.mP)) for z in z1]} {len(swz(r2))} {len(swz(r3))} {[(z.bot, z.top) for z in z4]} {len(swz(r5))}")
    # contact / SL with the merged width: 1992 / 1996.5 / 2001 -> one Zone 1990-2003; TOUCH_A (high 1995) from below -> one SHORT
    # wait (the members are not separate candidates); TC -> entry, SL = merged top 2003 + 5. Unmerged (distance off): two waits
    def touch(**ov):
        rows = flat(3, 1985) + [TOUCH_A, TC_AFTER] + flat(10, 1988)
        sc = Sc(rows)
        sw_feed(sc, 1, 1, True, 1992.0, 1)
        sw_feed(sc, 1, 2, True, 1996.5, 2)
        sw_feed(sc, 2, 3, False, 2001.0, 3)
        sc.set(4, labS1=L_AFTER)
        return sc.run(**ONLY_TC, **{**QUIET, **NEW, **ov})
    rm, ru = touch(), touch(zcMerge=-1.0)
    zm = swz(rm)
    check("LB-54 the merged swing Zone is the trading Zone: 1992 / 1996.5 / 2001 -> 1990-2003; one contact from below -> one SHORT wait "
          "keyed by the merged Zone (members never used as separate candidates), TC -> one order with SL = 2003 + 5 = 2008 (variable "
          "width); with merging off the same bars give two waits (1990-1994 and 1994.5-1998.5)",
          len(zm) == 1 and (zm[0].bot, zm[0].top) == (1990.0, 2003.0) and [w[0] for w in rm.trace[3]["waits"]] == [str(zm[0].id)]
          and [e[0] for e in entries(rm)] == [4] and rm["o"].sl == 2008.0 and len(ru.trace[3]["waits"]) == 2,
          f"{[(z.bot, z.top) for z in zm]} {rm.trace[3]['waits']} {entries(rm)} {rm['o'].sl} {ru.trace[3]['waits']}")
    # the merged Zone is used from the merge bar like any Zone (no old-band exception): price above, Zone 1998-2002; on bar 3 a 2004
    # pivot widens it to 1998-2006 and the bar's low 2005 touches the merged band -> LONG wait on bar 3 (snapshot 1998-2006);
    # the same merge with a bar whose low (2007) stays above the merged band -> no contact (merging alone is no contact)
    def merge_bar(low3):
        rows = flat(3, 2012) + [(2010.0, 2011.0, low3, 2009.0)] + flat(4, 2012)
        sc = Sc(rows)
        sw_feed(sc, 1, 1, False, 2000.0, 1)
        sw_feed(sc, 3, 2, False, 2004.0, 2)
        return sc.run(**ONLY_TC, **dict(QUIET, **NEW))
    r, rn = merge_bar(2005.0), merge_bar(2007.0)
    z = swz(r)[0]
    w3 = r.trace[3]["waits"]
    # bridge on the merge bar: A 2000 / B 2009, the 2004.5 pivot on bar 3 bridges them; the bar's low 2010.5 touches only B's former
    # part -> one LONG wait on the merged Zone (keyed by A, the survivor), not two
    rows = flat(3, 2020) + [(2020.0, 2021.0, 2010.5, 2019.0)] + flat(4, 2020)
    sc = Sc(rows)
    sw_feed(sc, 1, 1, True, 2000.0, 1)
    sw_feed(sc, 1, 2, True, 2009.0, 2)
    sw_feed(sc, 3, 3, True, 2004.5, 3)
    rb = sc.run(**ONLY_TC, **dict(QUIET, **NEW))
    zb_ = swz(rb)
    wb = rb.trace[3]["waits"]
    check("LB-55 the merged swing Zone is judged from the merge bar with its merged band, like any Zone: low 2005 vs 1998-2006 on the "
          "merge bar -> LONG wait (first / last contact = that bar, snapshot 1998-2006); low 2007 (above the band) -> no contact "
          "(merging alone is no contact); a bridge on the contact bar gives one wait on the merged Zone 1998-2011 (not one per old Zone)",
          len(w3) == 1 and w3[0][1] == 1 and w3[0][3] == 3 and w3[0][4] == 3 and (z.bot, z.top) == (1998.0, 2006.0)
          and r["lbWaits"][0].eBot == 1998.0 and r["lbWaits"][0].eTop == 2006.0 and rn.trace[3]["waits"] == []
          and len(zb_) == 1 and (zb_[0].bot, zb_[0].top) == (1998.0, 2011.0) and [w[0] for w in wb] == [str(zb_[0].id)] and wb[0][1] == 1,
          f"{w3} {rn.trace[3]['waits']} {wb} {[(q.bot, q.top) for q in zb_]}")
    # bridge with a pending wait: A 2000 (1998-2002), B 2009 (2007-2011); price above, B touched on bar 3 -> LONG wait (B); on bar 4
    # a 2004.5 pivot bridges A and B -> A absorbs B, the wait is re-keyed to A with its last contact / snapshot / expiry unchanged
    rows = flat(3, 2020) + [(2020.0, 2021.0, 2010.5, 2019.0)] + flat(4, 2020)
    sc = Sc(rows)
    sw_feed(sc, 1, 1, True, 2000.0, 1)
    sw_feed(sc, 1, 2, True, 2009.0, 2)
    sw_feed(sc, 4, 3, True, 2004.5, 3)
    r = sc.run(**ONLY_TC, **dict(QUIET, **NEW))
    za = swz(r)
    w3, w4 = r.trace[3]["waits"], r.trace[4]["waits"]
    check("LB-56 bridging two swing Zones keeps the pending wait: the wait from B's contact (bar 3) is re-keyed to the surviving Zone "
          "(same side / first and last contact / band snapshot), the waits map follows, nothing is cancelled",
          len(za) == 1 and len(w3) == 1 and len(w4) == 1 and w4[0][0] == str(za[0].id) and w3[0][0] != w4[0][0]
          and w4[0][1:] == w3[0][1:] and list(r["lbWaitMap"].keys()) == ["1#" + str(za[0].id)]
          and r["lbWaits"][0].eBot == 2007.0 and r["lbWaits"][0].eTop == 2011.0, f"{w3} {w4} {[(z.bot, z.top) for z in za]}")
    # TP with variable widths (SHORT reads the Zones by their tops): swing lows 1952..1978 (step 4) -> one Zone 1950-1980, POC 1955
    # (1953-1957) inside it, POC 1930 below; SHORT targets from 2000: [1980, 1932] (by bottoms the POC would come first: 1957)
    sc = Sc(flat(12, 2050))
    for i, p in enumerate([1952.0, 1956.0, 1960.0, 1964.0, 1968.0, 1972.0, 1976.0, 1978.0]):
        sw_feed(sc, 1 + i, 1, False, p, 20 - i)
    poc(sc, 1, 1955.0)
    poc(sc, 1, 1930.0, k=2)
    r = sc.run(**ONLY_TC, **dict(QUIET, **NEW))
    tps = r.env["f_lbTargets"](-1, 2000.0)
    tpl = r.env["f_lbTargets"](1, 1900.0)
    check("LB-57 TP search with variable widths: SHORT reads the static Zones by their tops (lbZsT): targets from 2000 = [1980, 1932] "
          "(merged swing 1950-1980 with the POC 1953-1957 inside = one band); LONG from 1900 = [1928, 1950]",
          [z.bot for z in swz(r)] == [1950.0] and tps == [1980.0, 1932.0] and tpl == [1928.0, 1950.0], f"{tps} {tpl}")
    # display ON / OFF with the new defaults on a random path with swing merges
    sc = rand_bars(5, n=400)
    a = lp.Runner(overrides=dict(NEW, zbUse2=False, dsZone=True, dsEnt=True)).run(sc.bars)
    b = lp.Runner(overrides=dict(NEW, zbUse2=False, dsZone=False, dsEnt=False)).run(sc.bars)
    check("LB-58 new defaults (width 2, distance 5) on a 400-bar random path with swing merges: display ON / OFF gives identical orders, "
          "fills, waits and ledger",
          a.broker.log == b.broker.log and a.trace == b.trace and list(a["bkNet"]) == list(b["bkNet"]) and a["st"].nSwMerge > 0
          and len(entries(a)) > 0, f"{a['st'].nSwMerge} {len(entries(a))}")


def sc_names_labels():
    # names (short) and the right-side labels; POC received normally; MA added / removed on confirmed bars
    sc = Sc(flat(10, 2050))
    sw_feed(sc, 1, 1, True, 2000.0, 1)
    sw_feed(sc, 1, 2, False, 2003.0, 2)          # 1H + 4H swing merged (1998-2005)
    poc(sc, 1, 2004.0)                            # 1H POC (received normally) 2002-2006: overlaps the swing band
    poc(sc, 1, 2100.0, k=2)                       # 4H POC alone
    sc.hold(2, None, g2k=T_HTF, g2c=2061.0, g2d=1, g2t=2040.0, g2b=2030.0)      # 4H bullish FVG 2030-2040
    zb = {3: 2020.0, 4: 2007.0, 5: 2020.0}
    for i in range(10):
        sc.set(i, zbMa1=zb.get(i, 2020.0))
    run = lp.Runner(overrides=dict(**ONLY_TC, **dict(QUIET, **NEW, zbUse1=True, dsZone=True)))
    texts = []
    for i, bar in enumerate(sc.bars):
        run.step(bar)
        texts.append(sorted(g.lb.text for g in run.env["lbDsG"] if not g.gone))
    e = run.env
    st = e["st"]
    swing_poc = "4時間足｜水平線\n1時間足｜水平線＋出来高POC"
    gs = [g for g in e["lbDsG"] if not g.gone]
    pos_ok = all(g.lb.args[0] == g.lb.x if hasattr(g.lb, "x") else True for g in gs)
    created = {id(g.lb): g.lb.args[0] for g in gs}
    e["bar_index"] = 500
    e["f_dsLblX"]()
    moved = all(g.lb.x == 503 and g.lb.args[1] == (g.bot + g.top) / 2.0 and g.bx.kw.get("text") is None for g in gs)
    # (per-bar state is deep-copied by the harness, so label deletion sync is checked on direct calls in LB-47; here: one label per band)
    one_lb = all(g.lb is not None and not g.lb.deleted for g in gs) and all(g.lb is None for g in e["lbDsG"] if g.gone)
    check("LB-59 names: '4時間足｜水平線' / '1時間足｜水平線＋出来高POC' (merged 1H + 4H swing lines with the normally received 1H POC), "
          "'4時間足｜出来高POC' alone, '4時間足｜FVG'; the 1m MA joins the overlapping band on the confirmed bar where its band overlaps "
          "(bar 4: '…\n1分足｜MA EMA3000') and leaves on the next confirmed bar it does not (bar 5); one name label per shown band "
          "(no text in the box) at bar + 3 / mid height, moved to the latest bar + 3 by f_dsLblX, labels of merged / removed bands deleted",
          texts[3] == sorted([swing_poc, "4時間足｜出来高POC", "4時間足｜FVG"])
          and texts[4] == sorted([swing_poc + "\n1分足｜MA EMA3000", "4時間足｜出来高POC", "4時間足｜FVG"])
          and texts[5] == texts[3] and moved and one_lb and len(gs) == 3,
          f"{texts[3]} {texts[4]} {texts[5]} {moved} {one_lb} {len(gs)}")
    # iFVG name
    zf = [z for g in gs for z in g.mem if z.typ == 4][0]
    zf.inv = True
    e["f_dsRename"](zf)
    check("LB-59b iFVG name '4時間足｜iFVG' (renamed in place on its own band)",
          sorted(g.lb.text for g in e["lbDsG"] if not g.gone) == sorted([swing_poc, "4時間足｜出来高POC", "4時間足｜iFVG"]))


def pocs(r, k=None):
    """the POC Zones in the static index (optionally of TF k = 0..3)"""
    return [z for z in r["lbZs"] if z.typ == 3 and (k is None or z.tf == k)]


def sc_poc_latest():
    # LAB-3g: one valid POC per TF (latest confirmed). 1H: A 2000 (bars 1-4, time-only update on bar 3), B 2010 (bars 5-8), A again
    # (bars 9-); 4H POC 2100 alongside. Price below (1985): contact with A on bar 2 -> SHORT wait; kept through the time-only update
    # (bar 3) ; cancelled when B arrives (bar 5); touching B on its arrival bar is no contact, the next bar's touch is a new wait
    rows = flat(14, 1985)
    rows[2] = (1988.0, 1999.0, 1987.0, 1989.0)          # wick into A (1998-2002) from below -> SHORT wait
    rows[5] = (1990.0, 2009.0, 1989.0, 1990.0)          # wick into B (2008-2012) on B's arrival bar -> no contact (new Zone)
    rows[6] = (1990.0, 2009.0, 1989.0, 1990.0)          # the same wick on the next bar -> SHORT wait on B
    sc = Sc(rows)
    sc.hold(1, 3, **pocv(1, 1999.5, 2000.5, T_HTF))
    sc.hold(3, 5, **pocv(1, 1999.5, 2000.5, T_HTF + 3600_000))     # time-only update: nothing changes
    sc.hold(5, 9, **pocv(1, 2009.5, 2010.5, T_HTF + 7200_000))
    sc.hold(9, None, **pocv(1, 1999.5, 2000.5, T_HTF + 10800_000))  # back to the price of A: adopted as the latest POC
    sc.hold(1, None, **pocv(2, 2099.5, 2100.5, T_HTF))
    run = lp.Runner(overrides=dict(**ONLY_TC, **{**QUIET, **NEW, "dsZone": True}))
    per = []
    for bar in sc.bars:
        run.step(bar)
        per.append([(z.tf, z.ctr, z.id) for z in pocs(run.env)])
    r = run
    t = r.trace
    ids = [p[0][2] for p in per[1:] if p]
    one = all(len([q for q in p if q[0] == k]) <= 1 for p in per for k in range(4))
    a1, b, a2 = per[2][0], per[6][0], per[10][0]
    dsp = [z.id for g in r["lbDsG"] if not g.gone for z in g.mem if z.typ == 3]
    check("LB-60 POC = latest confirmed per TF: at every bar at most one valid POC per TF (1H and 4H each one); A 2000 -> B 2010 -> "
          "back to 2000 gives three successive Zones (A again adopted as a new latest POC); the replaced POC leaves the Zone index "
          "(bot / top orders), the display and is marked dead; a time-only update (bar 3) keeps the same Zone",
          one and per[2] == per[4] and a1[1] == 2000.0 and b[1] == 2010.0 and a2[1] == 2000.0 and len({a1[2], b[2], a2[2]}) == 3
          and sorted(q[1] for q in per[-1]) == [2000.0, 2100.0] and len(r["lbZsT"]) == len(r["lbZs"])
          and sorted(dsp) == sorted(q[2] for q in per[-1]), f"{per[2]} {per[4]} {per[6]} {per[10]} {per[-1]} {dsp}")
    check("LB-61 waits on a replaced POC: the SHORT wait from the contact with A (bar 2) is kept through the time-only update (bars 3-4) "
          "and cancelled on bar 5 when B replaces A (nothing carried over to B); B's arrival bar touch is no contact, the next bar's "
          "touch makes a new wait on B (first contact = bar 6)",
          len(t[2]["waits"]) == 1 and t[4]["waits"] == t[2]["waits"] and t[5]["waits"] == []
          and len(t[6]["waits"]) == 1 and t[6]["waits"][0][0] == str(b[2]) and t[6]["waits"][0][3] == 6,
          f"{t[2]['waits']} {t[4]['waits']} {t[5]['waits']} {t[6]['waits']}")
    # display: swing 2001 (1999-2003) merged with POC A (1998-2002) -> one band; after B the swing band stays alone and B is apart
    sc2 = Sc(flat(8, 2050))
    sw_feed(sc2, 1, 1, True, 2001.0, 1)
    sc2.hold(1, 4, **pocv(1, 1999.5, 2000.5, T_HTF))
    sc2.hold(4, None, **pocv(1, 2019.5, 2020.5, T_HTF + 3600_000))
    run2 = lp.Runner(overrides=dict(**ONLY_TC, **{**QUIET, **NEW, "dsZone": True}))
    tx = []
    for bar in sc2.bars:
        run2.step(bar)
        tx.append(sorted((g.lb.text, g.bot, g.top) for g in run2.env["lbDsG"] if not g.gone))
    check("LB-62 display: the replaced POC leaves the merged band and only it (the swing line stays as its own band '1時間足｜水平線'; "
          "the new POC is its own band)",
          tx[2] == [("1時間足｜水平線＋出来高POC", 1998.0, 2003.0)]
          and tx[5] == sorted([("1時間足｜水平線", 1999.0, 2003.0), ("1時間足｜出来高POC", 2018.0, 2022.0)]), f"{tx[2]} {tx[5]}")
    # holding: SHORT from a swing line 1996 (1994-1998, TOUCH_A high 1995) with TP1 = POC 1960 (1958-1962); the POC is replaced by
    # 1940 while holding -> no forced close, SL unchanged, TP1 re-planned to the new POC top 1942
    rows = flat(3, 1985) + [TOUCH_A, TC_AFTER] + flat(8, 1986)
    sc3 = Sc(rows)
    sw_feed(sc3, 1, 1, True, 1996.0, 1)
    sc3.hold(1, 7, **pocv(1, 1959.5, 1960.5, T_HTF))
    sc3.hold(7, None, **pocv(1, 1939.5, 1940.5, T_HTF + 3600_000))
    sc3.set(4, labS1=L_AFTER)
    r3 = sc3.run(**ONLY_TC, **{**QUIET, **NEW})
    t3 = r3.trace
    check("LB-63 holding when the POC is replaced: no forced close, the initial SL (swing top 1998 + 5 = 2003) unchanged, TP1 moves from "
          "the old POC top 1962 to the new POC top 1942 by the normal TP update",
          [e[0] for e in entries(r3)] == [4] and t3[6]["legPx"][0] == 1962.0 and t3[7]["legPx"][0] == 1942.0 and t3[7]["pos"] != 0
          and r3["o"].sl == 2003.0 and t3[7]["stop"] == t3[6]["stop"], f"{[x['legPx'] for x in t3[5:9]]} {entries(r3)} {r3['o'].sl}")
    # causality: the run on the first 7 bars == the first 7 bars of the full run (a later POC never reaches back)
    rp = lp.Runner(overrides=dict(**ONLY_TC, **{**QUIET, **NEW, "dsZone": True})).run(sc.bars[:7])
    check("LB-64 causality: the run over bars 0-6 is identical to the first 7 bars of the full run (waits, timings, legs, Zones at bar 6), "
          "so each bar uses only the latest POC received by then",
          rp.trace == t[:7] and [(z.tf, z.ctr, z.id) for z in pocs(rp)] == per[6], f"{[(z.tf, z.ctr) for z in pocs(rp)]} {per[6]}")


def acc_feed(sc, k, boxes):
    """accum feed for TF k (1..3): boxes = [(i0, i1, u, l, id, forming)] held on bars i0..i1-1"""
    for i0, i1, u, l, aid, a in boxes:
        sc.hold(i0, i1, **{f"f{k}u": u, f"f{k}l": l, f"f{k}i": aid, f"f{k}a": a})
    return sc


def sc_acc_keep():
    # 1H: A (2010 / 1995) fixed on bar 3; B forming on bars 5-6, fixed on bar 7 -> A retired on bar 7 (keep 1).
    # 4H: C fixed on bar 2, D fixed on bar 6 -> both kept with keep 2 and independent of the 1H rotation
    def mk(**ov):
        rows = flat(20, 1985)
        rows[4] = (1986.0, 1990.0, 1985.0, 1986.0)                  # wick into A's lower edge band (1989-2001) from below -> SHORT wait
        rows[8] = tc_short(1987.0)
        sc = Sc(rows)
        acc_feed(sc, 1, [(1, 3, 2010.0, 1995.0, 100, 1), (3, 5, 2010.0, 1995.0, 100, 0), (5, 7, 2100.0, 2090.0, 200, 1), (7, None, 2100.0, 2090.0, 200, 0)])
        acc_feed(sc, 2, [(1, 2, 2300.0, 2290.0, 300, 1), (2, 5, 2300.0, 2290.0, 300, 0), (5, 6, 2400.0, 2390.0, 400, 1), (6, None, 2400.0, 2390.0, 400, 0)])
        sc.set(8, labS1=1987.0)
        return sc.run(**ONLY_TC, **dict(QUIET, **ov), zaKeep2=2)
    r1, r2 = mk(), mk(zaKeep1=2)
    def keys(r, bar=None):
        return sorted((z.tf, z.key, z.sub) for z in r["lbZs"] if z.typ == 0)
    p6 = lp.Runner(overrides=dict(**ONLY_TC, **QUIET, zaKeep2=2))
    rows = None
    check("LB-46 accum boxes kept per TF (initial 1): the 1H box A is used while B is forming (bars 5-6 not counted) and is retired "
          "with both edges when B is fixed (bar 7); its SHORT wait from bar 4 is cancelled, so the TC on bar 8 gives no entry (with 2 boxes "
          "kept: entry on bar 8); the 4H boxes (keep 2) stay independent of the 1H rotation",
          keys(r1) == [(0, 200, -1), (0, 200, 1), (1, 300, -1), (1, 300, 1), (1, 400, -1), (1, 400, 1)] and r1["st"].nAccOut == 2
          and r1.trace[6]["waits"] and not r1.trace[7]["waits"] and entries(r1) == [] and [e[0] for e in entries(r2)] == [8]
          and len(keys(r2)) == 8, f"{keys(r1)} {r1.trace[6]['waits']} {r1.trace[7]['waits']} {entries(r1)} {entries(r2)}")
    r1d, r2d = mk(dsZone=True), mk(zaKeep1=2, dsZone=True)
    shown = lambda r: sorted((z.tf, z.key, z.sub) for g in r["lbDsG"] if not g.gone for z in g.mem)
    check("LB-46c display of the accum box count: only the kept boxes are shown (1H keep 1: A's two edges leave the bands when B is "
          "fixed, nothing grey is left for them; 1H keep 2: A still shown; 4H keep 2 both shown); with the same box counts and trading "
          "settings the display ON gives the same orders / waits / trace as display OFF",
          shown(r1d) == keys(r1) and shown(r2d) == keys(r2) and (0, 100, 1) in shown(r2d) and (0, 100, 1) not in shown(r1d)
          and not any(g.gone for g in r1d["lbDsG"]) and r1d.trace == r1.trace and r2d.trace == r2.trace and r1d.broker.log == r1.broker.log
          and r2d.broker.log == r2.broker.log, f"{shown(r1d)} {shown(r2d)}")
    # TP: SHORT from POC 2000 with the 1H box A (1975 / 1965 -> edges 1969-1981 and 1959-1971, one band, TP1 1981) as the only target;
    # A is retired by B on bar 9 while holding -> the TP moves to the fixed RR from the fill; the SL and the position stay
    after = flat(10, 1998.5)
    rows = flat(3, 1985) + [(1990.0, 1999.5, 1989.0, 1999.0), (2000.5, 2001.5, 1998.0, 1998.5)] + after
    sc = Sc(rows)
    poc(sc, 1, 2000.0)
    acc_feed(sc, 1, [(0, 1, 1975.0, 1965.0, 100, 1), (1, 8, 1975.0, 1965.0, 100, 0), (8, 9, 2100.0, 2090.0, 200, 1), (9, None, 2100.0, 2090.0, 200, 0)])
    sc.set(4, labS1=2001.0)
    r = sc.run(**ONLY_TC, **QUIET)
    fill = r.trace[5]["fill"]
    check("LB-46b a retired box leaves the TP candidates: while holding, TP1 = the box's band edge 1981 (bar 8); after the box is "
          "replaced on bar 9 the TP is re-planned without it (fixed RR from the fill); the initial SL 2011 and the position are unchanged",
          r.trace[8]["legPx"][0] == 1981.0 and abs(r.trace[9]["legPx"][0] - (fill - 1.5 * (2011.0 - fill))) < 1e-9
          and r["o"].sl == 2011.0 and r.trace[9]["pos"] != 0 and r.trace[9]["stop"] == r.trace[8]["stop"], f"{[t['legPx'] for t in r.trace[7:10]]}")


TFN = ("週足", "日足", "4時間足", "1時間足", "5分足", "1分足")


def ds_rank(z):
    return (5 if z.tf == 0 else 4) if z.typ == 1 else ((3, 2, 1)[z.tf] if z.typ == 0 else (3, 2, 1, 0)[z.tf])


def ds_name_ref(e, zs):
    """reference band name: one line per TF (higher TF first), TF x item once"""
    out = []
    for r in range(6):
        its = []
        for z in sorted(zs, key=lambda z: z.typ):     # stable: member order within a type
            if ds_rank(z) == r and e["f_zItem"](z) not in its:
                its.append(e["f_zItem"](z))
        if its:
            out.append(TFN[r] + "｜" + "＋".join(its))
    return "\n".join(out)


def ds_ref_groups(zs):
    """reference grouping: accum / MA / swing / POC merged only when really overlapping (EPS), chained; groups of MAs only are not
    drawn (line only); FVG / iFVG each on its own band (never merged, never bridging) -> (bot, top, ids)"""
    ref = []
    for z in sorted((z for z in zs if z.typ != 4), key=lambda z: z.bot):
        if ref and z.bot <= ref[-1][1] + 1e-7:
            ref[-1] = (ref[-1][0], max(ref[-1][1], z.top), ref[-1][2] + [z])
        else:
            ref.append((z.bot, z.top, [z]))
    out = [(b, t, sorted(q.id for q in m)) for b, t, m in ref if any(q.typ != 1 for q in m)]
    out += [(z.bot, z.top, [z.id]) for z in zs if z.typ == 4]
    return sorted(out)


def ds_groups(e):
    return sorted((g.bot, g.top, sorted(z.id for z in g.mem)) for g in e["lbDsG"] if not g.gone)


def sc_display():
    # LAB-3 display (drawn when a Zone is registered / changed, as in LAB-2): overlapping Zones as one band, Japanese names
    r = lp.Runner(overrides=dict(QUIET, zbUse1=True, zbUse2=True, dsZone=True, dsZoneMax=400)).run(Sc(flat(2, 2000)).bars)
    e = r.env
    LbZone = e["LbZone"]
    rnd = random.Random(9)
    bad, nmerge, nsplit, nma = [], 0, 0, 0
    for case in range(150):
        e["lbDsG"] = []
        n0 = len(r.draws)
        act, sid = [], 0
        mas = [None, None]
        e["lbMa1"], e["lbMa2"] = None, None
        for step in range(rnd.randint(1, 40)):
            e["bar_index"] = 1000 + step
            for k in (0, 1):     # the MA bands move (or appear) like EMA bands each bar
                if rnd.random() < 0.6:
                    if mas[k] is None:
                        mas[k] = LbZone.new(500 + k, 1, k, 0, 2000.0, 1994.0, 2006.0, None, None, None, 900, 0)
                    c = round(2000 + rnd.uniform(-40, 40), rnd.choice([0, 1]))
                    mas[k].ctr, mas[k].bot, mas[k].top = c, c - 6.0, c + 6.0
            e["lbMa1"], e["lbMa2"] = mas
            if act and rnd.random() < 0.3:
                z = act.pop(rnd.randrange(len(act)))
                e["f_dsDel"](z, z.typ == 4)
            else:
                sid += 1
                t = rnd.choice([0, 2, 3, 4])
                c = round(2000 + rnd.uniform(-40, 40), rnd.choice([0, 1]))
                w = 6.0 if t != 4 else rnd.choice([1.5, 6.0, 20.0])
                z = LbZone.new(sid, t, rnd.randint(0, 2 if t == 0 else 3), rnd.choice([1, -1]), c, c - w, c + w, c - 0.5, c + 0.5, sid,
                               1000 + step, 0)
                ng = len([g for g in e["lbDsG"] if not g.gone])
                e["f_dsAdd"](z)
                act.append(z)
                nmerge += len([g for g in e["lbDsG"] if not g.gone]) < ng
            e["f_dsMa"]()     # end of the bar's registrations (as in (B1))
            nma += any(z.typ == 1 for g in e["lbDsG"] if not g.gone for z in g.mem)
            groups = [g for g in e["lbDsG"] if not g.gone]
            alive = {id(d) for d in r.draws[n0:] if d.kind == "box" and not d.deleted}
            alive_l = {id(d) for d in r.draws[n0:] if d.kind == "label" and not d.deleted}
            ok = (ds_groups(e) == ds_ref_groups(act + [m for m in mas if m is not None]) and alive == {id(g.bx) for g in e["lbDsG"]}
                  and alive_l == {id(g.lb) for g in groups}
                  and all(g.lb.text == ds_name_ref(e, g.mem) and g.bx.args[1] == g.top and g.bx.args[3] == g.bot
                          and g.lb.args[1] == (g.bot + g.top) / 2.0 for g in groups))
            if not ok:
                bad.append((case, step))
                break
        nsplit += len(ds_ref_groups(act)) > 1
    e["lbMa1"], e["lbMa2"] = None, None
    # names: 4H accum lower + 4H swing high + two 1H POCs overlapping -> one band; weekly swing low apart; MA name
    zs = [LbZone.new(1, 0, 1, -1, 2000.0, 1994.0, 2006.0), LbZone.new(2, 2, 1, 1, 2004.0, 1998.0, 2010.0),
          LbZone.new(3, 3, 0, 0, 2008.0, 2002.0, 2014.0, 2007.5, 2008.5), LbZone.new(4, 3, 0, 0, 2009.0, 2003.0, 2015.0, 2008.5, 2009.5),
          LbZone.new(5, 2, 3, -1, 2040.0, 2034.0, 2046.0)]
    e["lbDsG"] = []
    for z in zs:
        z.aBar = 1000
        e["f_dsAdd"](z)
    txt = sorted(g.lb.text for g in e["lbDsG"])
    fv = LbZone.new(6, 4, 1, 1, 2001.0, 1999.0, 2003.0, None, None, 6, 1000, 0)
    e["f_dsAdd"](fv)
    fv.inv = True
    e["f_dsRename"](fv)
    t_inv = [(g.lb.text, g.bot, g.top) for g in e["lbDsG"] if any(z.id == 6 for z in g.mem)]
    txt_f = sorted(g.lb.text for g in e["lbDsG"])
    ma = LbZone.new(201, 1, 0, 0, 2012.0, 2006.0, 2018.0, None, None, None, 0, 0)
    e["lbMa1"] = ma
    e["f_dsMa"]()
    t_ma = sorted((g.lb.text, g.bot, g.top) for g in e["lbDsG"] if not g.gone)
    ma.ctr, ma.bot, ma.top = 2080.0, 2074.0, 2086.0     # the MA moves away: back to the band without it, no MA-only band
    e["bar_index"] += 1
    e["f_dsMa"]()
    t_ma2 = sorted((g.lb.text, g.bot, g.top) for g in e["lbDsG"] if not g.gone)
    e["lbMa1"] = None
    check("LB-47 display grouping: Zones are merged into one band only when their ranges really overlap (EPS, chained, incl. a new Zone "
          "bridging two bands), from the lowest low to the highest high; bands that are only close stay apart; removing a Zone "
          "re-splits the rest; merged bands' boxes are deleted (one box per band, no duplicate box / text); FVG / iFVG never merged "
          "(own bounds, no bridging); MA bands (moving each bar) merged with overlapping accum / swing / POC bands, MA alone = no band; "
          "150 random add / remove / MA-move sequences == reference after every bar. Names: one line per TF, higher TF first, accum / MA / swing / POC / FVG order in a line, same TF x item once: '4時間足｜アキュム下辺"
          "＋水平線' / '1時間足｜出来高POC' (two POCs once), iFVG renamed in place, MA '1分足｜MA EMA3000'",
          not bad and nmerge > 50 and nsplit > 50
          and txt == ["4時間足｜アキュム下辺＋水平線\n1時間足｜出来高POC", "週足｜水平線"]
          and t_inv == [("4時間足｜iFVG", 1999.0, 2003.0)]
          and txt_f == sorted(["4時間足｜iFVG", "4時間足｜アキュム下辺＋水平線\n1時間足｜出来高POC", "週足｜水平線"])
          and t_ma == sorted([("4時間足｜アキュム下辺＋水平線\n1時間足｜出来高POC\n1分足｜MA EMA3000", 1994.0, 2018.0),
                              ("4時間足｜iFVG", 1999.0, 2003.0), ("週足｜水平線", 2034.0, 2046.0)])
          and t_ma2 == sorted([("4時間足｜アキュム下辺＋水平線\n1時間足｜出来高POC", 1994.0, 2015.0),
                               ("4時間足｜iFVG", 1999.0, 2003.0), ("週足｜水平線", 2034.0, 2046.0)])
          and nma > 100, f"{bad[:3]} {nmerge} {nsplit} {nma} {txt} {t_inv} {txt_f} {t_ma} {t_ma2}")
    e["lbDsG"], e["dsZoneMax"] = [], 3
    sep = [LbZone.new(300 + k, 2, 0, 1, 2000.0 + 20 * k, 1994.0 + 20 * k, 2006.0 + 20 * k, None, None, k, 1000, 0) for k in range(5)]
    for z in sep:
        e["f_dsAdd"](z)
    capped = [g.mem[0].id for g in e["lbDsG"]]
    e["dsZoneMax"] = 400
    check("LB-47c band count limit (as LAB-2): beyond 'max bands' the oldest band is deleted (the Zones stay internal)",
          capped == [302, 303, 304] and len(sep) == 5, str(capped))
    # a real run: the bands on the last bar == grouping of the valid Zones (FVGs that died are grey history bands, not merged)
    sc = rand_bars(3, n=400)
    a = lp.Runner(overrides=dict(zbUse2=False, dsZone=True, dsEnt=True, dsZoneMax=400)).run(sc.bars)
    b = lp.Runner(overrides=dict(zbUse2=False, dsZone=False, dsEnt=False)).run(sc.bars)
    valid = list(a["lbZs"]) + list(a["lbFvgs"]) + [a["lbMa1"]]
    ngone = len([g for g in a["lbDsG"] if g.gone])
    check("LB-47b real run (400 bars): the bands at the end == the reference grouping of the valid Zones (registered bar by bar, merged "
          "as they come; the 1m MA band merged where it overlaps on the last bar)", 
          ds_groups(a.env) == ds_ref_groups(valid) and len(valid) > 20 and len(a["lbDsG"]) < 400,
          f"{len(valid)} {len(a['lbDsG'])} gone {ngone}")
    check("LB-48 display ON / OFF (Zone bands and entry labels) gives identical orders, fills, waits and ledger (drawing only under "
          "dsZone / dsEnt, never read by the trading logic)",
          a.broker.log == b.broker.log and a.trace == b.trace and list(a["bkNet"]) == list(b["bkNet"]) and len(entries(a)) > 0,
          f"{len(entries(a))} {len(entries(b))}")


OLD2_REV = "57b7b76"     # LAB-2 (before the display grouping / accum box count)


def sc_old2_new():
    old_src = git("show", f"{OLD2_REV}:ZoneComboLabXAU.pine")
    bad = []
    n_ent = 0
    for seed in range(2):
        sc = rand_bars(seed + 20, n=350)
        for k, base in ((1, 0), (2, 1), (3, 2)):
            boxes = []
            for j in range(6):
                i0 = 20 + j * 50 + base * 7
                u = round(sc.bars[i0]["c"] + 4, 1)
                boxes += [(i0, i0 + 10, u, round(u - 8, 1), 1000 * k + j, 1), (i0 + 10, i0 + 50, u, round(u - 8, 1), 1000 * k + j, 0)]
            acc_feed(sc, k, boxes)
        for cf in (dict(), dict(cComb="AND", cZA=True, cZB=False, cZC=True, cZD=True, cZF=False)):
            ov = dict(zbUse2=False, dsZone=False, dsEnt=False, **cf)
            a = lp.Runner(overrides=ov, src=old_src).run(sc.bars)
            b = lp.Runner(overrides=dict(ov, zaKeep1=999, zaKeep2=999, zaKeep3=999)).run(sc.bars)
            if not (a.broker.log == b.broker.log and a.trace == b.trace and list(a["bkNet"]) == list(b["bkNet"])):
                bad.append((seed, cf))
            n_ent += len(entries(b))
    check("LB-49 with every accum box kept (999), the new version == LAB-2 (57b7b76) on 2 random paths x 350 bars with 1H / 4H / D accum "
          "feeds (OR and AND): identical orders, fills, waits and ledger (only the box count and the display changed)",
          not bad and n_ent > 0, f"{bad} {n_ent}")


def sc_zones():
    # ZA: forming -> fixed; no Keep Count (4 Accums on 1H all kept = 8 Zones)
    rows = flat(14, 1900)
    sc = Sc(rows)
    sc.hold(1, 3, f1u=2005.0, f1l=1995.0, f1i=100, f1a=1)
    sc.hold(3, 5, f1u=2006.0, f1l=1994.0, f1i=100, f1a=0)
    for j, (i0, i1) in enumerate(((5, 7), (7, 9), (9, 11), (11, None))):
        sc.hold(i0, i1, f1u=2100.0 + 30 * j, f1l=2090.0 + 30 * j, f1i=200 + j, f1a=1 if j < 3 else 0)
    r = sc.run(**QUIET, zaKeep1=99)
    za = [z for z in r["lbZs"] if z.typ == 0]
    check("LB-30 ZA: a forming Accum is not a Zone; it is fixed when the forming flag turns 0 (bar 3, last bounds 2006 / 1994) -> two "
          "Zones (upper 2006 +-6, lower 1994 +-6); a new ID fixes the previous unfixed one; with 99 boxes kept, 5 Accums on 1H -> 10 "
          "Zones (no expiry)", r.trace[2] and len([z for z in r["lbZs"] if z.key == 100]) == 2 and len(za) == 10
          and sorted(z.ctr for z in za if z.key == 100) == [1994.0, 2006.0], f"{len(za)}")
    # ZC dedupe (Library rule) / ZD exact-value registration
    sc = Sc(flat(10, 1900))
    sc.hold(1, 3, s1h=2000.0, s1ht=1000)
    sc.hold(3, 5, s1h=2004.0, s1ht=2000)          # within 6 of 2000 on the same TF / high -> also added (no suppression)
    sc.hold(5, 7, s1h=2000.0, s1ht=3000)          # the same price again (a new pivot) -> added as its own Zone
    sc.hold(1, None, s2h=2000.0, s2ht=1000, s1l=2000.0, s1lt=1000)
    sc.hold(1, 2, **pocv(1, 1999.5, 2000.5))
    sc.hold(2, 3, **pocv(1, 1999.5, 2000.5, T_HTF + 3600_000))     # same centre, new target time: not registered again
    sc.hold(3, 4, **pocv(1, 2000.75, 2001.75))
    sc.hold(4, 5, **pocv(1, 1999.5, 2000.5))
    r = sc.run(**QUIET)
    zc = sorted((z.tf, z.sub, z.ctr) for z in r["lbZs"] if z.typ == 2)
    zd = sorted((z.ctr, z.infoA, z.infoB) for z in r["lbZs"] if z.typ == 3)
    check("LB-31 ZC: every new Swing pivot (new time key) is its own Zone: a 1H high 4 away from an existing one and a new pivot at the "
          "same price are added (old Zones kept, not overwritten, no suppression by distance); the same pivot delivered on several bars "
          "is added once; other TF / Swing Low separate",
          zc == [(0, -1, 2000.0), (0, 1, 2000.0), (0, 1, 2000.0), (0, 1, 2004.0), (1, 1, 2000.0)], str(zc))
    check("LB-32 ZD: each new POC value is a new Zone (2000, 2001.25; centre = (bin low + bin high) / 2 from the external feed), the old band is kept; a value equal to an existing POC Zone of the "
          "same TF (2000 again) is not added twice; na adds nothing; the original bin bounds are kept as info",
          zd == [(2000.0, 1999.5, 2000.5), (2001.25, 2000.75, 2001.75)], str(zd))
    # MA: moving band, snapshot renewed on re-contact (SL from the latest contact)
    rows = flat(12, 1985)
    rows[3] = (1988.0, 1995.0, 1987.0, 1989.0)
    rows[6] = (1988.0, 1998.0, 1987.0, 1989.0)
    rows[7] = TC_AFTER
    sc = Sc(rows)
    sc.hold(0, 5, zbMa1=2000.0)
    sc.hold(5, None, zbMa1=2003.0)
    sc.set(7, labS1=L_AFTER)
    r = sc.run(**ONLY_TC, dsZone=False, dsEnt=False, zbUse2=False, cZA=False, cZB=True, cZC=False, cZD=False, cZF=False)
    check("LB-33 ZB: the EMA band moves every bar; the re-contact on bar 6 (band 1997-2009) renews the SL snapshot -> SL = 2009 + 5",
          [e[0] for e in entries(r)] == [7] and r["o"].sl == 2014.0, f"{entries(r)} {r['o'].sl}")


def sc_ta():
    # up FVG (SHORT absorption): bars 5-7, H2 = 1986 (bar 5 high), bar 6 bullish, bar 7 low 1987.5 -> FVG 1986-1987.5
    def mk(abs_at):
        rows = flat(30, 1985)
        rows[3] = TOUCH_A
        rows[5] = (1985.0, 1986.0, 1984.0, 1985.5)
        rows[6] = (1985.5, 1989.0, 1985.0, 1988.5)
        rows[7] = (1988.5, 1990.0, 1987.5, 1989.5)
        for i in range(8, 30):
            rows[i] = (1989.0, 1989.6, 1988.0, 1989.1)
        rows[abs_at] = (1989.0, 1989.5, 1985.0, 1985.5)
        for i in range(abs_at + 1, 30):
            rows[i] = (1985.5, 1986.0, 1985.0, 1985.6)
        for b in range(8, 30, 6):
            if b < abs_at:
                rows[b] = (1989.0, 1995.0, 1988.0, 1989.1)
        sc = Sc(rows)
        poc(sc, 1, 2000.0)
        return sc.run(**QUIET, cTA=True, cTC=False)
    a, b = mk(17), mk(18)
    check("LB-34 TA (ACC-5A): up FVG on bar 7 (middle bar bullish, width 1.5 >= 1) is absorbable through bar 17 (formation + 10): "
          "a bearish close <= 1986 on bar 17 is a SHORT timing -> entry with the SHORT wait (kept by re-contacts); on bar 18 the FVG "
          "has left the monitor -> no timing / no entry",
          [e[0] for e in entries(a)] == [17] and entries(b) == [] and a["st"].nTA == 1 and b["st"].nTA == 0,
          f"{entries(a)} {entries(b)}")


def sc_session():
    t_night = int(datetime(2026, 1, 5, 16, 30, tzinfo=timezone.utc).timestamp() * 1000)  # 01:30 JST
    sc = short_setup(tc_at=None)
    sc = Sc([(b["o"], b["h"], b["l"], b["c"]) for b in sc.bars], t0=t_night)
    poc(sc, 1, 2000.0)
    sc.bars[4].update(o=1990.0, h=1991.0, l=1987.5, c=1988.0)
    sc.set(4, labS1=L_AFTER)
    r = sc.run(**ONLY_TC, **QUIET)
    # bar 4 opens 01:50 JST -> time_close 01:55 inside; bar 5 time_close 02:00 -> outside
    sc2 = Sc([(b["o"], b["h"], b["l"], b["c"]) for b in sc.bars], t0=t_night + 2 * M5)
    poc(sc2, 1, 2000.0)
    sc2.bars[4].update(o=1990.0, h=1991.0, l=1987.5, c=1988.0)
    sc2.set(4, labS1=L_AFTER)
    r2 = sc2.run(**ONLY_TC, **QUIET)
    check("LB-35 entry window JST 09:00-02:00 by the decision bar's time_close: decision closing 01:55 enters, closing 02:05 is skipped "
          "(skip 'time')", [e[0] for e in entries(r)] == [4] and entries(r2) == [] and r2["skipN"][4] >= 1, f"{entries(r)} {entries(r2)}")


def sc_and_timing():
    def mk(ta_bar, tc_bar):
        rows = flat(30, 1985)
        rows[3] = TOUCH_A
        rows[5] = (1985.0, 1986.0, 1984.0, 1985.5)
        rows[6] = (1985.5, 1989.0, 1985.0, 1988.5)
        rows[7] = (1988.5, 1990.0, 1987.5, 1989.5)
        for i in range(8, 30):
            rows[i] = (1989.0, 1989.6, 1988.0, 1989.1)
        rows[ta_bar] = (1989.0, 1989.5, 1985.0, 1985.5)
        for i in range(ta_bar + 1, 30):
            rows[i] = (1985.5, 1986.0, 1985.0, 1985.6)
        rows[tc_bar] = (1986.5, 1987.5, 1984.0, 1984.5)
        sc = Sc(rows)
        poc(sc, 1, 2000.0)
        sc.set(tc_bar, labS1=1987.0)
        for b in (9, 13):
            if b < ta_bar:
                sc.bars[b].update(h=1995.0)
        return sc.run(**QUIET, cTA=True, cTC=True, cTim="AND")
    a = mk(10, 14)
    check("LB-36 timing AND: TA on bar 10 and TC on bar 14 (each still within its 12 bars, not the same bar) -> entry on bar 14 "
          "(the second one completes the set); both marked used", [e[0] for e in entries(a)] == [14] and a["o"].tim == 3,
          f"{entries(a)} tim {a['o'].tim}")


def sc_ledger():
    # a loss: SHORT, price runs to the SL 2011 -> full SL loss; R = -1 (from the actual fill / initial SL / quantity)
    after = [(1998.0, 2003.0, 1997.0, 2002.0), (2002.0, 2012.0, 2001.0, 2010.0)] + flat(4, 2012)
    r = partial_setup([(2, 1960.0)], after, beOn=False)
    cl = [c for c in r.broker.closed if c["id"] == "S1"]
    fill = r.trace[5]["fill"]
    rj = (2011.0 - fill) * 4 * 150.0
    check("LB-37 ledger: a stop-out is one loss (bucket 0 / ZD含む / ZDだけ / TC / 反発 / SHORT each 1); R = pnl / (|fill - SL| x qty x "
          "USDJPY) = -1; max DD (equity incl. the open loss at the bar's adverse extreme) >= the realised loss",
          cl and r["bkL"][0] == 1 and r["bkN"][4] == 1 and r["bkN"][9] == 1 and r["bkN"][12] == 1 and r["bkN"][13] == 1
          and r["bkN"][17] == 1 and abs(r["bkR"][0] + 1.0) < 1e-9 and r["st"].maxDD >= rj - 1e-6, f"R {r['bkR'][0]} dd {r['st'].maxDD} rj {rj}")


# ============================================================================
# randomized: invariants and causality (prefix runs give the same past)
# ============================================================================
def rand_bars(seed, n=900):
    rnd = random.Random(seed)
    p = 2000.0
    rows = []
    for i in range(n):
        o = p
        c = o + rnd.gauss(0, 2.2)
        h = max(o, c) + abs(rnd.gauss(0, 1.2))
        l = min(o, c) - abs(rnd.gauss(0, 1.2))
        rows.append((round(o, 2), round(h, 2), round(l, 2), round(c, 2)))
        p = c
    sc = Sc(rows)
    # feeds built causally from completed blocks of 12 bars ("1H") and 48 ("4H"): value of the previous completed block only
    for i in range(n):
        hb = i // 12
        if hb >= 2:
            seg = rows[(hb - 1) * 12: hb * 12]
            hi, lo = max(r[1] for r in seg), min(r[2] for r in seg)
            cc = round((hi + lo) / 2, 2)
            sc.bars[i].update(**pocv(1, round(cc - 0.3, 2), round(cc + 0.3, 2), T0 + (hb - 1) * 3600_000))
            prev = rows[(hb - 2) * 12: (hb - 1) * 12]
            if min(r[2] for r in seg) > max(r[1] for r in prev) + 3:
                sc.bars[i].update(g1k=T0 + (hb - 1) * 3600_000, g1c=seg[-1][3], g1d=1, g1t=min(r[2] for r in seg), g1b=max(r[1] for r in prev))
            elif max(r[1] for r in seg) < min(r[2] for r in prev) - 3:
                sc.bars[i].update(g1k=T0 + (hb - 1) * 3600_000, g1c=seg[-1][3], g1d=-1, g1t=min(r[2] for r in prev), g1b=max(r[1] for r in seg))
            else:
                sc.bars[i].update(g1k=T0 + (hb - 1) * 3600_000, g1c=seg[-1][3], g1d=0)
            sc.bars[i].update(s1h=hi, s1ht=T0 + (hb - 1) * 3600_000 if hb % 3 == 0 else None)
            if hb % 3 != 0:
                sc.bars[i].update(s1h=None)
        if i >= 1:
            sc.bars[i].update(labS1=round(rows[i - 1][3] + rnd.choice([-1.5, 1.5]), 2), zbMa1=round(sum(r[3] for r in rows[max(0, i - 50):i + 1]) / min(i + 1, 51), 2))
    return sc


def sc_random():
    bad = []
    t0 = _time.time()
    for seed in range(3):
        sc = rand_bars(seed)
        r = sc.run(zbUse2=False, dsZone=False, dsEnt=False)
        n = len(sc.bars)
        # invariants
        if r.broker.max_abs_pos > max([e[3] for e in entries(r)] + [0]) + 1e-9:
            bad.append((seed, "pos"))
        for t in r.trace:
            if t["state"] == 2 and t["pos"] != 0 and abs(sum(t["legLots"]) - abs(t["pos"])) > 1e-9:
                bad.append((seed, "legs", t["bar"]))
                break
        led = r["bkN"][0]
        closed_ids = sorted({c["id"] for c in r.broker.closed})
        if r["o"].state == 0 and led != len(closed_ids):
            bad.append((seed, "ledger", led, len(closed_ids)))
        tot = sum(c["profit"] for c in r.broker.closed)
        if r["o"].state == 0 and abs(r["bkNet"][0] - tot) > 1e-6:
            bad.append((seed, "net"))
        # causality: a run on the first m bars has the same orders / fills / state as the full run up to bar m - 1
        for m in (n // 3, 2 * n // 3):
            rp = lp.Runner(overrides=dict(zbUse2=False, dsZone=False, dsEnt=False)).run(sc.bars[:m])
            full = [e for e in r.broker.log if e[1] < m]
            if full != rp.broker.log or r.trace[:m] != rp.trace:
                bad.append((seed, "prefix", m))
        RANDOM_STATS.append((seed, len(entries(r)), led, r["st"].maxIter, r["st"].maxWaits, len(r["lbZs"])))
    check("LB-38 random paths (3 x 900 bars, all Zone feeds built from completed blocks only): position never above one entry, the "
          "partial legs always sum to the open quantity, ledger trades = distinct closed entry IDs, ledger net = broker profits; runs on "
          "the first 1/3 and 2/3 of the bars reproduce the same orders, fills and state for those bars (no future value is used)",
          not bad, f"{bad} {RANDOM_STATS} {_time.time() - t0:.1f}s")


RANDOM_STATS = []


# ============================================================================
# LAB-2: POC split / optimisations
# ============================================================================
def poc_ref(H, L, V, off, lookback, bins, ranged=False):
    """Python port of f_pocCore (MtfPocDetector, ranged=False) and of the MtfPocFeedXAU version (ranged=True), statement by statement.
    H / L / V: lists indexed by the Pine history offset (H[k] = high[k]); None = na."""
    import math as m
    bar_index = len(H) - 1
    poc = pUp = pLo = None
    if lookback > 0 and bins > 0 and bar_index - off >= lookback:
        hi = lo = None
        ok = True
        for k in range(off, off + lookback):
            h, l, v = H[k], L[k], V[k]
            if h is None or l is None or v is None:
                ok = False
                break
            hi = h if hi is None else max(hi, h)
            lo = l if lo is None else min(lo, l)
        rangeAll = hi - lo if ok else None
        if ok and rangeAll > 0:
            bv = [0.0] * bins
            bs = rangeAll / bins
            total = 0.0
            for k in range(off, off + lookback):
                ch, cl, cv = H[k], L[k], V[k]
                total += cv
                crange = ch - cl
                if crange <= 0:
                    bidx = max(0, min(bins - 1, int((cl - lo) / bs)))
                    bv[bidx] = bv[bidx] + cv
                else:
                    rng_ = range(max(0, m.floor((cl - lo) / bs) - 1), min(bins - 1, m.floor((ch - lo) / bs) + 1) + 1) if ranged else range(bins)
                    for bi in rng_:
                        binBot = lo + bi * bs
                        binTop = binBot + bs
                        ov = min(binTop, ch) - max(binBot, cl)
                        if ov > 0:
                            bv[bi] = bv[bi] + cv * ov / crange
            if total > 0:
                best, bestI = -1.0, 0
                for bi in range(bins):
                    if bv[bi] > best:
                        best, bestI = bv[bi], bi
                pLo = lo + bestI * bs
                pUp = pLo + bs
                poc = (pUp + pLo) / 2.0
    return poc, pUp, pLo


def sc_poc_opt():
    rnd = random.Random(11)
    n = bad = 0
    for case in range(400):
        nb = rnd.choice([30, 125, 200])
        p = 2000.0
        H, L, V = [], [], []
        for i in range(nb):
            o = p
            c = round(o + rnd.gauss(0, 3), rnd.choice([1, 2]))
            h = max(o, c) + abs(round(rnd.gauss(0, 1.5), 1))
            l = min(o, c) - abs(round(rnd.gauss(0, 1.5), 1))
            r = rnd.random()
            if r < 0.06:
                h = l = c                       # zero-range candle
            elif r < 0.10:
                h, l = round(h), round(l)       # integer edges (bin-boundary hits)
            vol = rnd.choice([0, rnd.randint(1, 5000), 1.0])
            if rnd.random() < 0.01:
                vol = None
            H.append(h)
            L.append(l)
            V.append(vol)
            p = c
        if case % 50 == 0:
            V = [0] * nb                        # total volume 0 -> na
        if case % 37 == 0:
            H = [2000.0] * nb
            L = [2000.0] * nb                   # range 0 -> na
        for lb, bins in ((120, 75), (20, 75), (120, 20), (30, 100)):
            a = poc_ref(H, L, V, 1, lb, bins, ranged=False)
            b = poc_ref(H, L, V, 1, lb, bins, ranged=True)
            n += 1
            if a != b:
                bad += 1
    # grid-aligned case: candle edges exactly on bin edges (lo 2000, range 75 -> bin width 1)
    H = [2075.0] + [2000.0 + (i % 75) + 1 for i in range(130)]
    L = [2000.0] + [2000.0 + (i % 75) for i in range(130)]
    V = [100.0] * 131
    g1, g2 = poc_ref(H, L, V, 1, 120, 75), poc_ref(H, L, V, 1, 120, 75, ranged=True)
    check("LB-42 POC optimisation: the per-candle bin range (floor-1 .. floor+1) gives exactly the same bin low / high / centre as the "
          "full 75-bin scan (Python port of both, statement by statement) on 1,600 windows incl. zero-range candles, integer edges, "
          "volume 0 / na, range 0, 20 / 75 / 100 bins, and candles exactly on bin edges",
          bad == 0 and g1 == g2 and g1[0] is not None, f"{bad}/{n} {g1} {g2}")


def zd_bars(n=12, **feed):
    sc = Sc(flat(n, 1985))
    for i in range(n):
        sc.bars[i].update(feed)
    return sc


def sc_zd_recv():
    # states and registration from the 13 external series
    sc = Sc(flat(16, 1985))
    seq = [None, None, (1999.5, 2000.5, T_HTF), (1999.5, 2000.5, T_HTF), (1999.5, 2000.5, T_HTF + 3600_000), (None, None, None),
           (1999.5, 2000.5, T_HTF + 7200_000), (None, None, -(T_HTF + 10800_000)), (2009.5, 2010.5, T_HTF + 14400_000),
           (1999.5, 2000.5, T_HTF + 18000_000)] + [(1999.5, 2000.5, T_HTF + 18000_000)] * 6
    stats = []
    for i, v in enumerate(seq):
        if v is not None:
            sc.bars[i].update(zdL1=v[0], zdU1=v[1], zdT1=v[2])
    r = lp.Runner(overrides=dict(QUIET))
    for b in sc.bars:
        r.step(b)
        stats.append(r["lbZdStat"][0])
    zd = sorted((z.ctr, z.infoA, z.infoB, z.key, z.aTime) for z in r["lbZs"] if z.typ == 3)
    check("LB-43 ZD reception: history na -> state 3 (no Zone); a value registers once (centre 2000, bin 1999.5-2000.5 kept, target "
          "time and the 5m availability time kept); the same centre on later bars or with a new target time is not registered again; na "
          "(state 3) and a calculation failure (negative time, state 2) keep the last valid centre, so the return of 2000 adds nothing; "
          "2010 is added; 2000 again (already registered) adds nothing; none of these stop entries",
          stats[:10] == [3, 3, 1, 1, 1, 3, 1, 2, 1, 1] and zd == [(2000.0, 1999.5, 2000.5, T_HTF, sc.bars[2]["t"]),
                                                                     (2010.0, 2009.5, 2010.5, T_HTF + 14400_000, sc.bars[8]["t"])]
          and r["skipN"][7] == 0, f"{stats} {zd}")
    # connection errors: stop new entries only while the lab's ZD detection is ON
    def run_basic(**ov):
        rows = flat(3) + [(1990, 1995, 1989, 1991)] + [tc_short(1993)] + flat(6, 1985)
        s2 = Sc(rows)
        poc(s2, 1, 2000.0)
        s2.hold(1, None, s1h=2000.0, s1ht=T0 - 3600_000)     # a Swing Zone on the same price: candidates exist without the POC
        s2.hold(4, 5, labS1=1993.0)
        for b in s2.bars:
            b.update({k: v for k, v in ov.items() if k in lp.FEED_DEFAULT})
        return s2.run(**ONLY_TC, **QUIET, **{k: v for k, v in ov.items() if k not in lp.FEED_DEFAULT})
    ok_run = run_basic()
    no_proto = run_basic(zdProto=1991.0)                                     # unconnected: input.source left at close
    t_close = run_basic(zdT2=1985.1, zdL2=1985.1, zdU2=1985.1)               # one slot left at close
    ext_off = run_basic(zdT3=0.0)                                            # feed side OFF while the lab slot is ON
    lab_off = run_basic(zdProto=1991.0, zdUse1=False, zdUse2=False, zdUse3=False, zdUse4=False, cZD=False, cZC=True)
    t_only = run_basic(zdT1=1985.1)                                          # only the time series of a valid slot left at close
    t_future = run_basic(zdT1=float(T0 + 10 * 86_400_000))                   # a "time" after the current 5m bar
    neg = run_basic(zdT4=-(T_HTF + 1.0))                                     # calculation failure (normal connection)
    hist = run_basic(zdT4=None)                                              # history not yet available
    check("LB-43b ZD connection: protocol != 10001 (input left at close), a time series left at close, or the feed's slot OFF (time 0) "
          "while the lab slot is ON -> state 9 / 8, new entries stopped (skip 'ZD 接続'), never replaced by close; with the lab's ZD "
          "detection OFF an unconnected feed does not stop entries; a calculation failure / missing history does not stop entries",
          len(entries(ok_run)) == 1 and entries(no_proto) == [] and no_proto["skipN"][7] >= 1 and list(no_proto["lbZdStat"]) == [9, 9, 9, 9]
          and entries(t_close) == [] and t_close["lbZdStat"][1] == 9 and entries(ext_off) == [] and ext_off["lbZdStat"][2] == 8
          and entries(t_only) == [] and t_only["lbZdStat"][0] == 9 and entries(t_future) == [] and t_future["lbZdStat"][0] == 9
          and list(lab_off["lbZdStat"]) == [0, 0, 0, 0] and lab_off["skipN"][7] == 0 and len(entries(lab_off)) == 1
          and len(entries(neg)) == 1 and neg["lbZdStat"][3] == 2 and len(entries(hist)) == 1 and hist["lbZdStat"][3] == 3
          and not any(z.typ == 3 for z in no_proto["lbZs"]),
          f"{entries(no_proto)} {list(no_proto['lbZdStat'])} {list(t_close['lbZdStat'])} {list(ext_off['lbZdStat'])} {list(lab_off['lbZdStat'])} "
          f"{list(neg['lbZdStat'])} {list(hist['lbZdStat'])}")


OLD_REV = "bc68da2"     # LAB-1 last version (internal POC, linear wait search, full AND odometer, iterative TP clustering)


def sc_old_new():
    old_src = git("show", f"{OLD_REV}:ZoneComboLabXAU.pine")
    cfgs = [dict(), dict(cComb="AND", cZA=False, cZB=True, cZC=False, cZD=True, cZF=True), dict(tpMode="選択した TP で全決済", tpSel=3),
            dict(tpMode="固定 RR"), dict(cScope="だけ"), dict(beLock=True, beMode="TP1 割合")]
    bad = []
    for seed in range(2):
        sc = rand_bars(seed + 10, n=350)
        # more POC / MA traffic: a second POC slot every 6 bars, two MAs
        for i, b in enumerate(sc.bars):
            if i >= 30:
                c = round(sum(x["c"] for x in sc.bars[i - 30:i - 24]) / 6, 2)
                b.update(**pocv(2, round(c - 0.4, 2), round(c + 0.4, 2), T0 + (i // 6) * 1000))
                b.update(zbMa2=round(sum(x["c"] for x in sc.bars[max(0, i - 120):i + 1]) / min(i + 1, 121), 2))
        for cf in cfgs:
            ov = dict(dsZone=False, dsEnt=False, **cf)
            a = lp.Runner(overrides=ov, src=old_src).run(sc.bars)
            b = lp.Runner(overrides=dict(ov, zaKeep1=999, zaKeep2=999, zaKeep3=999)).run(sc.bars)
            same = (a.broker.log == b.broker.log and a.broker.closed == b.broker.closed and a.trace == b.trace
                    and [list(a[k]) for k in ("bkN", "bkW", "bkL", "bkBE", "bkNet", "bkR")] == [list(b[k]) for k in ("bkN", "bkW", "bkL", "bkBE", "bkNet", "bkR")]
                    and sorted((z.typ, z.tf, z.ctr, z.bot, z.top) for z in a["lbZs"]) == sorted((z.typ, z.tf, z.ctr, z.bot, z.top) for z in b["lbZs"]))
            if not same:
                bad.append((seed, cf))
            OLD_NEW_STATS.append(len(entries(b)))
    check("LB-44 before / after (LAB-1 bc68da2 with the internal POC vs LAB-2 with the same POC values as external series): 2 random "
          "paths x 350 bars x 6 settings (OR / AND, chosen TP, fixed RR, only, BE lock + TP1 ratio) give identical waits / timings / legs per bar, "
          "orders and fills (incl. partial exits), closed trades, ledger buckets and registered Zones",
          not bad and sum(OLD_NEW_STATS) > 0, f"{bad} entries {OLD_NEW_STATS}")


OLD_NEW_STATS = []


def sc_tp_ref():
    """f_lbTargets (one pass over the three ordered streams) vs a reference: every eligible interval, sorted, merged with the same EPS
    rule, first 3 bands. Random Zone sets with chained overlaps, wide FVGs, both MAs, LONG / SHORT, 0..3+ targets."""
    r = lp.Runner(overrides=dict(QUIET, zbUse1=True, zbUse2=True)).run(Sc(flat(2, 2000)).bars)
    e = r.env
    LbZone = e["LbZone"]
    rnd = random.Random(5)
    EPS = 1e-7
    bad, counts = [], [0, 0, 0, 0]
    for case in range(500):
        zs, fv = [], []
        for _ in range(rnd.randint(0, 14)):
            c = round(2000 + rnd.uniform(-60, 60), rnd.choice([0, 1, 2]))
            hw = 6.0 if rnd.random() < 0.6 else rnd.choice([2.0, 9.0, 15.0])     # LAB-3e: merged swing Zones have other widths
            zs.append(LbZone.new(len(zs) + 1, rnd.choice([0, 2, 3]), 0, 0, c, c - hw, c + hw))
        for _ in range(rnd.randint(0, 5)):
            b = round(2000 + rnd.uniform(-70, 60), 1)
            w = rnd.choice([3.0, 8.5, 25.0, 60.0])
            fv.append(LbZone.new(100 + len(fv), 4, 0, 1, b + w / 2, b, b + w))
        if case % 7 == 0 and zs:          # exact touching edges / exact equal bands (EPS rule)
            z0 = zs[0]
            zs.append(LbZone.new(99, 2, 0, 0, z0.ctr + 12.0, z0.ctr + 6.0, z0.ctr + 18.0))
            zs.append(LbZone.new(98, 3, 0, 0, z0.ctr, z0.bot, z0.top))
        e["lbZs"] = sorted(zs, key=lambda z: z.bot)
        e["lbZsT"] = sorted(zs, key=lambda z: z.top)
        e["lbFvgs"] = sorted(fv, key=lambda z: z.bot)
        e["lbFvgsT"] = sorted(fv, key=lambda z: z.top)
        e["st"].maxW, e["st"].maxWF = max([z.top - z.bot for z in zs] + [0.0]), max([z.top - z.bot for z in fv] + [0.0])
        mas = [round(2000 + rnd.uniform(-50, 50), 2) if rnd.random() < 0.6 else None for _ in range(2)]
        e["zbMa1"], e["zbMa2"] = mas
        e["lbMa1"] = LbZone.new(201, 1, 0, 0, mas[0], mas[0] - 6.0, mas[0] + 6.0) if mas[0] is not None else None
        e["lbMa2"] = LbZone.new(202, 1, 1, 0, mas[1], mas[1] - 6.0, mas[1] + 6.0) if mas[1] is not None else None
        ref = round(2000 + rnd.uniform(-20, 20), rnd.choice([0, 1]))
        for side in (1, -1):
            iv = [(z.bot, z.top) for z in zs + fv if (z.bot > ref + EPS if side == 1 else z.top < ref - EPS)]
            iv += [(m - 6.0, m + 6.0) for m in mas if m is not None and ((m - 6.0) > ref + EPS if side == 1 else (m + 6.0) < ref - EPS)]
            iv.sort(key=lambda x: x[0] if side == 1 else -x[1])
            out, cn, cf = [], None, None
            for b, t in iv:
                if cn is None:
                    cn, cf = (b, t) if side == 1 else (t, b)
                elif (b <= cf + EPS) if side == 1 else (t >= cf - EPS):
                    cf = max(cf, t) if side == 1 else min(cf, b)
                else:
                    out.append(cn)
                    cn, cf = (b, t) if side == 1 else (t, b)
            if cn is not None:
                out.append(cn)
            want = out[:3]
            got = e["f_lbTargets"](side, ref)
            counts[min(3, len(want))] += 1
            if got != want:
                bad.append((case, side, ref, got, want))
    check("LB-45 TP search (one pass, LONG by low ascending / SHORT by high descending over the common-width index, the FVG low / high "
          "indexes and both MAs, stop at the 3rd band) == the reference (all eligible intervals sorted and merged with the same EPS "
          f"rule) on 1,000 random cases incl. chained overlaps, wide FVGs (up to 60), common Zones of mixed widths (SHORT by tops: lbZsT), touching edges; targets 0 / 1 / 2 / 3: {counts}",
          not bad and all(c > 0 for c in counts), str(bad[:3]))

SCENARIOS = None
MUTANTS = [
    ("bar_index - w.lBar > waitBars", "bar_index - w.lBar >= waitBars", "wait expiry boundary"),
    ("e.eBar >= sBar and", "e.eBar >= sBar - 1 and", "timing before the contact"),
    ("tcLife = input.int(12,", "tcLife = input.int(13,", "timing validity boundary (12)"),
    ("ec.used := true", "ec.used := false", "used timing reuse"),
    ("        w.lBar := bar_index\n", "", "re-contact renewal"),
    ("(fakeWin == 0 or bar_index - z.brkBar <= fakeWin)", "(fakeWin == 0 or bar_index - z.brkBar < fakeWin - 1)", "fake window"),
    ("cc := (cs == -1 and z.brk == -1) or (cs == 1 and z.brk == 1) ? 3 : 1", "cc := 1", "role-reversal category"),
    ("okp := okp and ob <= ot2 + EPS and low <= ot2 + EPS and high >= ob - EPS", "okp := okp", "AND overlap contact (pruning)"),
    ("okp := array.get(cSide, jz) == array.get(cSide, j0)", "okp := true", "AND same side (pruning)"),
    ("    LbWait w = array.remove(lbWaits, i)\n    map.remove(lbWaitMap, f_wKey(w.side, w.key))\n", "    LbWait w = array.remove(lbWaits, i)\n",
     "waits map kept in sync"),
    ("                if zdBad\n                    why := 7\n                else if", "                if false\n                    why := 7\n                else if", "ZD misconnection stops entries"),
    ("            else if math.abs(tt) < 1e11 or math.abs(tt) >= time or tt != math.round(tt)", "            else if false", "ZD time plausibility"),
    ("else if cScope == \"だけ\" and om != 0", "else if false", "only-scope exclusion"),
    ("if (z.sub == 1 and hc < z.bot) or (z.sub == -1 and hc > z.top)", "if (z.sub == 1 and hc < z.top) or (z.sub == -1 and hc > z.bot)", "iFVG edge"),
    ("math.floor(cumW / 100.0 * o.lotN + 0.5)", "math.floor(cumW / 100.0 * o.lotN + 1e-9)", "partial lot rounding (round, not floor)"),
    ("o.fill + beRatio / 100.0 * (o.tp1E - o.fill)", "o.fill + o.side * beRatio / 100.0 * (o.tp1E - o.fill)", "BE ratio sign"),
    ("if not na(bestL) and not na(bestS)\n        st.nConflict += 1\n    else if not na(bestL)", "if not na(bestL)", "LONG / SHORT conflict"),
    ("    array.size(tps) >= 3\n", "    array.size(tps) >= 2\n", "TP scan stops after the 3rd band"),
    ("array<LbZone> fArr = side == 1 ? lbFvgs : lbFvgsT", "array<LbZone> fArr = lbFvgs", "SHORT reads FVGs in high order"),
    ("else if side == 1 ? b <= cf + EPS : t >= cf - EPS", "else if false", "overlapping TP Zones merged"),
    ("not f_lbDup(3, k, 0, pc)", "true", "POC exact duplicate"),
    ("    while nk > 2 * f_zaKeep(q.tf)\n", "    while nk > 2 * f_zaKeep(q.tf) + 2\n", "accum box count"),
    ("        array.push(lbDeadNow, zo.id)\n", "", "retired box cancels its waits"),
    ("if not na(pt) and not na(pv) and (na(lt) or pt != lt)", "if not na(pt) and not na(pv)", "a Swing pivot is registered once"),
    ("fakeWin = input.int(0,", "fakeWin = input.int(3,", "fake window default unlimited"),
    ("        if array.get(o.legLots, k - 1) > 0\n            r := array.get(o.legPx, k - 1)\n    r\n\nf_lbTpText",
     "        if na(r) and array.get(o.legLots, k - 1) > 0\n            r := array.get(o.legPx, k - 1)\n    r\n\nf_lbTpText", "BE lock target = farthest TP"),
    ("if lkBlk and array.size(lbWaits) > 0", "if false", "waits cleared while locked"),
    ("if xs != 0\n                    array.push(xId, z.id)", "if false\n                    array.push(xId, z.id)", "break cancels the wait"),
    ("                    hit := g.bot <= ng.top + EPS and ng.bot <= g.top + EPS", "                    hit := g.bot < ng.top and ng.bot < g.top",
     "display: merge bands that touch (EPS)"),
    ("f_dsMerge(LbZone z) =>\n    z.typ != 4", "f_dsMerge(LbZone z) =>\n    true", "display: FVG not merged"),
    ("        st.nSwMerge += 1", "        a.aBar := bar_index\n        st.nSwMerge += 1", "merged swing Zone judged from the merge bar"),
    ("    array<LbZone> aArr = side == 1 ? lbZs : lbZsT\n    int ia = side == 1 ? f_lbLower(lbZs, ref + EPS) : f_lbLowerT(lbZsT, ref - EPS) - 1",
     "    array<LbZone> aArr = lbZs\n    int ia = side == 1 ? f_lbLower(lbZs, ref + EPS) : f_lbLower(lbZs, ref) - 1", "SHORT TP by tops (variable width)"),
    ("pv <= array.max(q.mP) + zcMerge + EPS", "pv < array.max(q.mP) + zcMerge - EPS", "swing merge distance boundary"),
    ("                f_waitMove(b.id, a.id)\n", "", "bridged swing Zone's waits re-keyed"),
    ("                        oz.dead := true\n                        array.push(lbDeadNow, oz.id)", "                        oz.dead := true",
     "replaced POC's waits cancelled"),
    ("    if not na(lbMa1) and not p1 and p2\n        f_dsPut(lbMa1, true)", "    if false\n        f_dsPut(lbMa1, true)", "display: MA chained through the other MA"),
    ("            if q.bot <= stp + EPS\n                    array.push(sm, q)", "            if q.bot < stp - EPS\n                    array.push(sm, q)",
     "display: regroup after removal (touching bands)"),
]


def mutation():
    scen = [sc_basic, sc_windows, sc_carry, sc_conflict, sc_roles, sc_combo, sc_fvg, sc_partial, sc_tp_mixed, sc_qty_table, sc_be, sc_lock_far, sc_and_only_sel, sc_sel_tp, sc_consume, sc_zones, sc_acc_keep, sc_dup_swing, sc_ta,
            sc_session, sc_and_timing, sc_ledger, sc_zd_recv, sc_tp_ref, sc_display, sc_fvg_display, sc_swing_merge, sc_names_labels, sc_poc_latest]
    survived = []
    for old, new, what in MUTANTS:
        if SRC.count(old) != 1:
            survived.append((what, "pattern count " + str(SRC.count(old))))
            continue
        lp.SRC_OVERRIDE = SRC.replace(old, new)
        n0 = len(RESULTS)
        try:
            for f in scen:
                f()
            killed = not all(ok for _, ok, _ in RESULTS[n0:])
        except Exception:
            killed = True
        del RESULTS[n0:]
        lp.SRC_OVERRIDE = None
        if not killed:
            survived.append(what)
    check(f"LB-39 mutation: {len(MUTANTS)} single changes to the Pine logic (expiry / timing / reuse / renewal / fake / role / AND / "
          "only / iFVG / partial lots / BE ratio / conflict / lock / TP clusters / duplicates / break cancel) each make a scenario fail",
          not survived, str(survived))

def main():
    t = _time.time()
    static()
    registration()
    registration2()
    sc_basic()
    sc_windows()
    sc_carry()
    sc_conflict()
    sc_roles()
    sc_combo()
    sc_fvg()
    sc_fvg_display()
    sc_partial()
    sc_tp_mixed()
    sc_qty_table()
    sc_be()
    sc_lock_far()
    sc_and_only_sel()
    sc_sel_tp()
    sc_consume()
    sc_zones()
    sc_acc_keep()
    sc_display()
    sc_old2_new()
    sc_dup_swing()
    sc_swing_merge()
    sc_names_labels()
    sc_poc_latest()
    sc_ta()
    sc_session()
    sc_and_timing()
    sc_ledger()
    sc_random()
    sc_poc_opt()
    sc_zd_recv()
    sc_tp_ref()
    sc_old_new()
    mutation()
    npass = sum(1 for _, ok, _ in RESULTS if ok)
    for name, ok, detail in RESULTS:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else "  -- " + detail))
    print(f"{npass}/{len(RESULTS)} passed  [PINE_NOT_VERIFIED: static / translated Pine logic + emulator]  {(_time.time() - t):.1f}s")


if __name__ == "__main__":
    main()
