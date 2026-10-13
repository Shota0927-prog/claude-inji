"""GBE-3 / GBJ-6 fixtures — Day/Swing Overlap Mode (Separate / Deduplicate) for GBPJPY.

  GD : static — Library = gbe_build.build(); strip_gbe3 gives Library version 2 (3205d03) byte for byte, strip_gbe the
       shared /6; new origin fields (Day High / Low first 5M bar, trading-day start, Swing pivot bar open time / length /
       price) are state only; every scoring change is gated by dsDedup; the match predicate and the adjustment are
       pinned; Visual / Strategy import version 3, carry the same input (default Separate), pass the pivot bar time
       (time[len], never the confirmation time) from the existing Swing requests (10 / 11 requests, same timeframes and
       lookahead), and revert byte for byte to 3205d03 without GBJ-6; FVG reads the Engine baseSum / catCount; Gold,
       USDJPY and shared /6 unchanged
  GM : models — Pine ports of the Day-origin tracking, the pivot-origin time, the match predicate and the scoring part
       of f_finalizeCluster (Swing max, Day H/L, Deduplicate, categories, FVG boost): same 5M bar, later equal high,
       near price, previous day, high / low kind, HTF window, HTF window before the day start, unknown origin; mixed
       cases with independent Swings / Day H/L, ties, HTF; Separate equal to the previous scoring on random clusters
  GU : mutations — time ignored, nearness instead of identity, confirmation time instead of pivot bar time, unknown HTF
       origin treated as a match, Confluence still double, Day subtracted uniformly, independent top Swing not blocking

Evidence class: PINE_NOT_VERIFIED. TradingView compile, Library version 3 publish, Strategy Tester external.
"""
import os
import random
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gbe_build as ge          # noqa: E402
import gbj_build as gb          # noqa: E402
import gbs_build as gs          # noqa: E402
import st1_build as tb          # noqa: E402
import fvg_re10045_sim as fr    # noqa: E402

ROOT = ge.ROOT
PREV = "3205d03"
rd = lambda p: open(os.path.join(ROOT, p), encoding="utf-8").read() if os.path.exists(os.path.join(ROOT, p)) else ""
show = lambda p, rev=PREV: subprocess.run(["git", "-C", ROOT, "show", f"{rev}:{p}"], capture_output=True, text=True).stdout
ENG6, GBE, GBE2 = rd(ge.SRC_PATH), rd(ge.GBE_PATH), show(ge.GBE_PATH)
GBV, GBS = rd(gb.GBJ_PATH), rd(gs.GBS_PATH)
GBV0, GBS0 = show(gb.GBJ_PATH), show(gs.GBS_PATH)
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


def code_only(src):
    return "\n".join(l for l in src.split("\n") if not l.lstrip().startswith("//"))


def revert6(text, skip_header=True):
    out = text
    for kind, a, b in reversed(gb.EDITS6):
        if kind == "header" and skip_header:
            continue
        out = out.replace(b, a) if out is not None and out.count(b) == 1 else None
    return out


PROTECTED = ["ZoneEnginePracticalSwingMax.pine", "ZoneEnginePractical.pine", "ZoneEnginePracticalRN.pine",
             "ZoneEnginePracticalAuthority.pine", "ZoneVisualPractical.pine", "ZoneStrategyXAU.pine",
             "ZoneVisualUSDJPY.pine", "ZoneStrategyUSDJPY.pine", "PracticalZoneStrategy_LONG.pine",
             "PracticalZoneStrategy_SHORT.pine", "SignalEnginePractical.pine"]
MATCH_H = ('bool mH = dsOn and m.srcId == "SWING_H" and not na(dHt) and not na(m.oT) and not na(m.oMs) and m.oPx == dHpx '
           'and m.oT >= dH0 and m.oT <= dHt and dHt < m.oT + m.oMs')
MATCH_L = MATCH_H.replace("mH", "mL").replace("SWING_H", "SWING_L").replace("dHt", "dLt").replace("dHpx", "dLpx") \
    .replace("dH0", "dL0")


def gate_static():
    check("GD-01 Library = gbe_build.build() (rebuild identical); reverting GBE-3 gives Library version 2 (" + PREV + ") "
          "byte for byte, reverting GBE-3 / 2 / 1 the shared ZoneEnginePractical/6",
          bool(GBE) and ge.build() == GBE and ge.strip_gbe3(GBE) == GBE2 and bool(GBE2) and ge.strip_gbe(GBE) == ENG6)
    fc = tb.func(GBE, "f_finalizeCluster(")
    upd = tb.func(GBE, "update(") if "\nupdate(" in GBE else GBE[GBE.index("export update("):]
    gated = ["    if dsOn\n        for j = 0 to n - 1\n", "    if dsOn and (dHm or dLm)\n"]
    check("GD-02 Library: origin data is state only (Day High / Low time set on the bar that first reaches the extreme: "
          "strict > / <, the trading-day start; pivot bar time / length / price on the Swing raw); every scoring change "
          "is gated by dsDedup (pre-scan, match flags false when off, adjustment and category block); the match "
          "predicate requires identical price, same high / low kind, pivot bar inside the trading day and the Day bar "
          "inside the pivot bar; no tolerance distance",
          all(fc.count(g) == 1 for g in gated) and fc.count(MATCH_H) == 1 and fc.count(MATCH_L) == 1
          and "        if na(e.dayHigh) or high > e.dayHigh     // GBE-3" in upd and "        if na(e.dayLow) or low < e.dayLow\n" in upd
          and "            baseSum -= math.min(c.scoreDayHL, swMax)\n" in fc
          and "- dsCatAdj\n" in fc and "bool   dsDedup            = false" in GBE
          and not re.search(r"zoneHalfWidth|clusterDist|math\.abs", fc[fc.index("bool mH"):fc.index("int  sl")]))
    inp = lambda s: re.search(r"^dsMode = input\.string\((.*)$", s, re.M)
    cfg = ['zoneCfg.dsDedup              := dsMode == "Deduplicate"\n'] + \
        [f"zoneCfg.hzMs{k}                := timeframe.in_seconds(hzTf{k}) * 1000\n" for k in (1, 2, 3)]
    check("GD-03 Visual and Strategy import Library version 3, same input Day/Swing Overlap Mode (default Separate) and "
          "config lines (dsDedup, Swing timeframe lengths); without the GBJ-6 edits both files are the " + PREV
          + " files byte for byte",
          all(re.findall(r"^import .*$", s, re.M) == [ge.IMPORT_GBE.strip()] for s in (GBV, GBS))
          and inp(GBV) and inp(GBS) and inp(GBV).group(1) == inp(GBS).group(1)
          and inp(GBV).group(1).startswith('"Separate", "Day/Swing Overlap Mode", options = ["Separate", "Deduplicate"]')
          and all(GBV.count(c) == 1 and GBS.count(c) == 1 for c in cfg)
          and revert6(GBV, skip_header=False) == GBV0 and bool(GBV0) and revert6(GBS) == GBS0 and bool(GBS0))
    req = lambda s: re.findall(r"request\.\w+\(.*$", code_only(s), re.M)
    tfs = lambda s: [re.sub(r"^.*request\.(\w+)\(syminfo\.tickerid, (\w+),.*?(lookahead = \S+)?\)?$", r"\1 \2 \3", r)
                     for r in req(s)]
    nrs, swp = tb.func(GBV, "f_nrsPivotConfirmed("), tb.func(GBV, "f_swPack(")
    check("GD-04 pivot origin = time[len] in the requested timeframe (the pivot bar), returned next to the unchanged "
          "pivotPack values; HTF via [1] / lookahead_on as before (confirmed HTF bar only); the confirmation time "
          "(_pt / _lt) is not used as the origin; requests 10 / 11 with the same timeframes and lookahead as " + PREV,
          "int _po = na(_ph) ? int(na) : time[len]" in nrs and "_po[1], _lo[1]]" in nrs
          and "int _po = na(_ph) ? int(na) : time[len]" in swp and "[_ph, _pt, _pl, _lt, _po, _lo]" in swp
          and "_po = na(_ph) ? int(na) : _pt" not in GBV
          and len(req(GBV)) == len(req(GBV0)) == 10 and len(req(GBS)) == len(req(GBS0)) == 11
          and tfs(GBV) == tfs(GBV0) and tfs(GBS) == tfs(GBS0)
          and "ph1o = ph1O, pl1o = pl1O, ph2o = ph2O, pl2o = pl2O, ph3o = ph3O, pl3o = pl3O," in GBV,
          str((tfs(GBV)[:3], tfs(GBV0)[:3])))
    cnt = lambda s, p: len(re.findall(p, code_only(s)))
    dline = "        dScore := z.baseSum + f_fvcBase(best) + z.slopeBonus + z.maBonus + z.flipBonus + f_fvcConf(z.catCount + 1)\n"
    check("GD-05 lightweight: zone loops, drawing, str.*, plot and loops unchanged in the scripts; the Library gains one "
          "loop, the Deduplicate-only scan of the cluster's own members (no history / zone-wide search); FVG boost reads "
          "the Engine baseSum and catCount; lint clean",
          all(cnt(n, p) == cnt(o, p) for n, o in ((GBV, GBV0), (GBS, GBS0))
              for p in (r"zn\.zoneAt\(", r"\b(box|label|table|line)\.new\(", r"\bstr\.\w+\(", r"\bplot\w*\(", r"\bfor\b",
                        r"\bwhile\b"))
          and cnt(GBE, r"\bfor\b") == cnt(GBE2, r"\bfor\b") + 1 and cnt(GBE, r"request\.") == 0
          and GBV.count(dline) == 1 and GBS.count(dline) == 1
          and fr.lint_eager_guards(code_only(GBV)) == [] and fr.lint_eager_guards(code_only(GBS)) == [])
    d = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", PREV, "--"] + PROTECTED, capture_output=True, text=True)
    t = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", "--diff-filter=MDR", PREV, "--", "tests/"],
                       capture_output=True, text=True).stdout
    check("GD-06 shared Engine /6 (and /2, /5, Authority), Gold, USDJPY and old strategies unchanged vs " + PREV
          + "; only GBPJPY tests / generators changed",
          d.returncode == 0 and d.stdout.strip() == "" and all(re.match(r"^tests/gb[defjsx]_\w+\.py$", f) for f in t.split()),
          d.stdout + t)


# ---- mirrors ------------------------------------------------------------------------------------------------------------
M5, M15, M60 = 300000, 900000, 3600000
SW = {"5": 1.0, "15": 2.0, "60": 3.0}
MS = {"5": M5, "15": M15, "60": M60}
DAY = 2.0                                   # GBJ-3 Day H/L score
conf = lambda c: 3.0 if c >= 4 else {2: 1.0, 3: 2.0}.get(c, 0.0)


def strength(s, htf, thr=(5.0, 9.0, 15.0)):
    t = 1 if s < thr[0] else 2 if s < thr[1] else 3 if s < thr[2] else 4
    return 3 if t == 4 and not htf else t


def day_track(bars):
    """Engine update day part: returns (dayHigh, dayHighT, dayLow, dayLowT, dayStartT); bars = (t, high, low), one day."""
    dh = dl = dht = dlt = d0 = None
    for t, h, l in bars:
        if d0 is None:
            d0, dh, dl, dht, dlt = t, h, l, t, t
        else:
            if h > dh:
                dht = t
            if l < dl:
                dlt = t
            dh, dl = max(dh, h), min(dl, l)
    return dh, dht, dl, dlt, d0


def pivot_origin(times, confirm_idx, length, use_confirm=False):
    """pivotPack on bar confirm_idx reports the pivot of bar confirm_idx - len; origin = time[len] there."""
    return times[confirm_idx] if use_confirm else times[confirm_idx - length]


def match(sw, day, variant=None):
    """the Library predicate. sw = dict(kind, px, oT, oMs); day = dict(kind, px, t, d0)."""
    if sw["kind"] != day["kind"]:
        return False
    if variant == "ignore_time":
        return sw["px"] == day["px"]
    if variant == "nearness":
        return abs(sw["px"] - day["px"]) <= 0.05
    if sw["oT"] is None or sw["oMs"] is None or day["t"] is None:
        return variant == "unknown_matches"
    return sw["px"] == day["px"] and sw["oT"] >= day["d0"] and sw["oT"] <= day["t"] < sw["oT"] + sw["oMs"]


def score(members, dedup, variant=None, fvg=None, sw_scores=SW):
    """f_finalizeCluster scoring part. members: ("SW", tf, kind, px, oT) / ("DAY", kind, px, t, d0) / ("MA",) / ("PDH",)."""
    days = {m[1]: dict(kind=m[1], px=m[2], t=m[3], d0=m[4]) for m in members if m[0] == "DAY"}
    base, sw_max, hits = 0.0, None, set()
    dm = {"H": False, "L": False}
    hz_ind = False
    sw_ind = set()
    cats, htf = set(), False
    for m in members:
        if m[0] == "SW":
            tf, kind, px, oT = m[1], m[2], m[3], m[4]
            d = days.get(kind)
            mt = dedup and d is not None and match(dict(kind=kind, px=px, oT=oT, oMs=MS[tf]), d, variant)
            dm[kind] |= mt
            if not mt:
                hz_ind = True
                sw_ind.add(tf)
            if tf not in hits:
                hits.add(tf)
                s = sw_scores[tf]
                base += s if sw_max is None else max(0.0, s - sw_max)
                sw_max = s if sw_max is None else max(sw_max, s)
            cats.add("HZ")
            htf |= tf == "60"
        elif m[0] == "DAY":
            base += DAY
            cats.add("DHL")
        elif m[0] == "PDH":
            base += 2.0
            cats.add("HZ")
            hz_ind = True
        elif m[0] == "MA":
            base += 2.0
            cats.add("MA")
    cat_adj = 0
    if dedup and (dm["H"] or dm["L"]):
        tops = [tf for tf in hits if sw_scores[tf] == sw_max]
        blocked = any(tf in sw_ind for tf in tops) and variant != "no_block"
        if variant == "uniform":
            base -= DAY
        elif not blocked and tops:
            base -= min(DAY, sw_max)
        dhl_ind = ("H" in days and not dm["H"]) or ("L" in days and not dm["L"])
        if not hz_ind and not dhl_ind and not (dm["H"] and dm["L"]) and variant != "conf_double":
            cat_adj = 1
    cat = len(cats) - cat_adj
    sc = base + conf(cat)
    st = strength(sc, htf)
    out = dict(base=base, cat=cat, score=sc, str=st, htf=htf)
    if fvg:
        ds = base + {"15": 1.0, "60": 2.0, "240": 3.0}[fvg] + conf(cat + 1)
        out.update(dScore=ds, dStr=strength(ds, htf), eligible=st >= 3 or strength(ds, htf) >= 3)
    return out


T0 = 1_700_000_000_000                       # trading-day start (first 5M bar), ms
t5 = lambda k: T0 + k * M5                  # k-th 5M bar of the day
DH = lambda px=210.300, k=10: ("DAY", "H", px, t5(k), T0)
DL = lambda px=209.700, k=30: ("DAY", "L", px, t5(k), T0)
SWH = lambda tf, px=210.300, oT=None: ("SW", tf, "H", px, t5(10) if oT is None else oT)
SWL = lambda tf, px=209.700, oT=None: ("SW", tf, "L", px, t5(30) if oT is None else oT)


def match_fixtures(mt=match, po=pivot_origin):
    out = []
    day = dict(kind="H", px=210.300, t=t5(10), d0=T0)
    sw = lambda **k: dict(dict(kind="H", px=210.300, oT=t5(10), oMs=M5), **k)
    out.append(("same 5M bar, same price, high -> same origin", mt(sw(), day)))
    out.append(("equal high on a later bar (the day high keeps its first bar) -> different origin", not mt(sw(oT=t5(14)), day)))
    out.append(("near price 210.299 on the same bar -> different", not mt(sw(px=210.299), day)))
    out.append(("previous day's Swing at the same price -> different", not mt(sw(oT=T0 - 20 * M5), day)))
    out.append(("Swing Low vs Day High -> different", not mt(sw(kind="L"), day)))
    out.append(("15M pivot bar [t9, t12) containing the Day bar t10, same price -> same origin",
                mt(sw(oT=t5(9), oMs=M15), day)))
    out.append(("15M pivot bar [t11, t14) not containing t10 -> different", not mt(sw(oT=t5(11), oMs=M15), day)))
    out.append(("1H pivot bar starting before the trading day's first 5M bar -> not treated as the same",
                not mt(sw(oT=T0 - M5, oMs=M60), dict(day, t=t5(2)))))
    out.append(("unknown origin (na pivot time / length or Day time) -> not treated as the same",
                not mt(sw(oT=None), day) and not mt(sw(oMs=None), day) and not mt(sw(), dict(day, t=None))))
    times = [t5(k) for k in range(40)]
    o = po(times, 20, 10)
    out.append(("pivot origin = time[len] (bar 10 for len 10 confirmed on bar 20), not the confirmation time (bar 20)",
                o == t5(10) and mt(sw(oT=o), day) and not (o == times[20])))
    dh, dht, dl, dlt, d0 = day_track([(t5(0), 210.0, 209.9), (t5(1), 210.2, 209.8), (t5(2), 210.2, 209.85), (t5(3), 210.1, 209.8)])
    out.append(("Day origin tracking: highs 210.0 / 210.2 / 210.2 / 210.1 -> first 210.2 bar (t1); lows 209.9 / 209.8 / "
                "209.85 / 209.8 -> first 209.8 bar (t1); day start t0", (dht, dlt, d0, dh, dl) == (t5(1), t5(1), t5(0), 210.2, 209.8)))
    return out


def score_fixtures(sc=score):
    out = []
    cases = [  # name, members, (Separate score, cat), (Deduplicate score, cat)
        ("A Day High = 5M Swing High (same bar)", [SWH("5"), DH()], (4.0, 2), (2.0, 1)),
        ("B Day High = 1H Swing High", [SWH("60", oT=t5(0)), DH()], (6.0, 2), (3.0, 1)),
        ("C Day High = 5M Swing + independent 1H Swing (other origin)", [SWH("5"), SWH("60", 210.330, t5(24)), DH()],
         (6.0, 2), (6.0, 2)),
        ("D Day High = 1H Swing + independent 15M Swing", [SWH("60", oT=t5(0)), SWH("15", 210.320, t5(21)), DH()],
         (6.0, 2), (4.0, 2)),
        ("E Day High = 5M, 15M and 1H pivots of the same bar", [SWH("5"), SWH("15", oT=t5(9)), SWH("60", oT=t5(0)), DH()],
         (6.0, 2), (3.0, 1)),
        ("F Day High = 5M Swing + Day Low unmatched in the cluster", [SWH("5"), DH(), DL()], (6.0, 2), (5.0, 2)),
        ("G Day High = 1H Swing High and Day Low = 1H Swing Low", [SWH("60", oT=t5(0)), SWL("60", oT=t5(24)), DH(), DL()],
         (8.0, 2), (6.0, 2)),
        ("H equal price on another bar (no same origin)", [SWH("5", oT=t5(14)), DH()], (4.0, 2), (4.0, 2)),
        ("I Day High = 1H Swing + MA #1", [SWH("60", oT=t5(0)), DH(), ("MA",)], (9.0, 3), (6.0, 2)),
        ("J Day High = 5M Swing + carried previous-day high (independent Horizontal)", [SWH("5"), DH(), ("PDH",)],
         (6.0, 2), (5.0, 2)),
    ]
    for name, mem, sep, ded in cases:
        a, b = sc(mem, False), sc(mem, True)
        out.append((f"{name}: Separate {sep[0]:g} ({sep[1]} cat), Deduplicate {ded[0]:g} ({ded[1]} cat)",
                    (a["score"], a["cat"]) == sep and (b["score"], b["cat"]) == ded))
    tie = dict(SW, **{"15": 3.0})
    mem = [SWH("60", oT=t5(0)), SWH("15", 210.320, t5(21)), DH()]
    out.append(("tie (15M input 3 = 1H 3): the independent 15M Swing earns the top too -> no adjustment, 6 (2 cat)",
                (sc(mem, True, sw_scores=tie)["score"], sc(mem, True, sw_scores=tie)["cat"]) == (6.0, 2)))
    b = sc([SWH("60", oT=t5(0)), DH()], True)
    out.append(("HTF kept from the actual 1H Swing under Deduplicate", b["htf"] and sc([SWH("5"), DH()], True)["htf"] is False))
    i_s = sc([SWH("60", oT=t5(0)), DH(), ("MA",)], False, fvg="60")
    i_d = sc([SWH("60", oT=t5(0)), DH(), ("MA",)], True, fvg="60")
    out.append(("FVG follows: I + 1H FVG: Separate 9 Strong -> 7 + 2 + 3 = 12; Deduplicate 6 Medium -> 5 + 2 + 2 = 9 "
                "Strong boost (eligible via the boost range)",
                (i_s["str"], i_s["dScore"]) == (3, 12.0) and (i_d["score"], i_d["str"], i_d["dScore"], i_d["dStr"],
                                                            i_d["eligible"]) == (6.0, 2, 9.0, 3, True)))
    return out


def prev_score(members):
    """previous (Library version 2) scoring of the same members: Swing max + Day + others, categories as sets."""
    base, sw_max, hits, cats = 0.0, None, set(), set()
    for m in members:
        if m[0] == "SW":
            if m[1] not in hits:
                hits.add(m[1])
                s = SW[m[1]]
                base += s if sw_max is None else max(0.0, s - sw_max)
                sw_max = s if sw_max is None else max(sw_max, s)
            cats.add("HZ")
        elif m[0] == "DAY":
            base += DAY
            cats.add("DHL")
        elif m[0] == "PDH":
            base += 2.0
            cats.add("HZ")
        else:
            base += 2.0
            cats.add("MA")
    return base + conf(len(cats)), len(cats)


def gate_model():
    for n, ok in match_fixtures():
        check("GM-M " + n, ok)
    for n, ok in score_fixtures():
        check("GM-S " + n, ok)
    rng = random.Random(5)
    bad = 0
    for _ in range(3000):
        mem = []
        for _ in range(rng.randint(1, 7)):
            k = rng.random()
            if k < 0.5:
                mem.append(rng.choice([SWH, SWL])(rng.choice(list(SW)), rng.choice([210.300, 209.700, 210.31]),
                                                  rng.choice([t5(10), t5(30), t5(9), t5(0), None])))
            elif k < 0.7:
                mem.append(rng.choice([DH(), DL()]))
            elif k < 0.85:
                mem.append(("MA",))
            else:
                mem.append(("PDH",))
        r = score(mem, False)
        bad += (r["score"], r["cat"]) != prev_score(mem)
        d = score(mem, True)
        bad += d["score"] > r["score"] + 1e-12 or d["cat"] > r["cat"] or d["htf"] != r["htf"]
    check("GM Separate equals the previous scoring on 3000 random clusters; Deduplicate never raises the score or the "
          "category count and keeps HTF", bad == 0, str(bad))


def gate_mutation():
    mm = {
        "time ignored (price + kind only)": dict(mt=lambda s, d: match(s, d, "ignore_time")),
        "nearness instead of identity": dict(mt=lambda s, d: match(s, d, "nearness")),
        "confirmation time used as the origin": dict(po=lambda t, i, n: pivot_origin(t, i, n, use_confirm=True)),
        "unknown origin treated as the same": dict(mt=lambda s, d: match(s, d, "unknown_matches")),
    }
    caught = {k: not all(ok for _, ok in match_fixtures(**v)) for k, v in mm.items()}
    sm = {
        "time ignored in scoring": lambda m, d, **k: score(m, d, variant="ignore_time", **k),
        "nearness in scoring": lambda m, d, **k: score(m, d, variant="nearness", **k),
        "Confluence still double": lambda m, d, **k: score(m, d, variant="conf_double", **k),
        "Day subtracted uniformly": lambda m, d, **k: score(m, d, variant="uniform", **k),
        "independent top Swing not blocking": lambda m, d, **k: score(m, d, variant="no_block", **k),
    }
    caught.update({k: not all(ok for _, ok in score_fixtures(f)) for k, f in sm.items()})
    check("GU-01 mirror mutations caught (" + str(len(caught)) + "): " + ", ".join(caught), all(caught.values()), str(caught))
    src = {
        "Library: price tolerance": ("GBE", "m.oPx == dHpx", "math.abs(m.oPx - dHpx) <= c.zoneHalfWidth"),
        "Library: Day time not checked": ("GBE", "and m.oT <= dHt and dHt < m.oT + m.oMs", ""),
        "Library: equal high moves the Day origin": ("GBE", "or high > e.dayHigh     // GBE-3", "or high >= e.dayHigh     // GBE-3"),
        "Library: category not merged": ("GBE", "+ (hasRN ? 1 : 0) - dsCatAdj\n", "+ (hasRN ? 1 : 0)\n"),
        "Scripts: confirmation time as origin": ("BOTH", "int _po = na(_ph) ? int(na) : time[len]", "int _po = na(_ph) ? int(na) : _pt"),
        "Scripts: mode mapped inverted": ("BOTH", 'dsMode == "Deduplicate"', 'dsMode == "Separate"'),
    }
    global GBE, GBV, GBS
    keep = (GBE, GBV, GBS, list(RESULTS))
    rej = {}
    for name, (where, a, b) in src.items():
        GBE = keep[0].replace(a, b, 1) if where == "GBE" else keep[0]
        GBV = keep[1].replace(a, b) if where == "BOTH" else keep[1]
        GBS = keep[2].replace(a, b) if where == "BOTH" else keep[2]
        del RESULTS[:]
        try:
            gate_static()
            rej[name] = not all(ok for _, ok, _ in RESULTS)
        except Exception:
            rej[name] = True
    GBE, GBV, GBS = keep[0], keep[1], keep[2]
    RESULTS[:] = keep[3]
    check("GU-02 source mutations rejected by the static gates (" + str(len(rej)) + "): " + ", ".join(rej),
          all(rej.values()), str(rej))


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
    print(f"\n{len(RESULTS) - fails}/{len(RESULTS)} passed  [PINE_NOT_VERIFIED: exact build / static / mirror model]")
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
