"""GBE-4 / GBJ-7 fixtures — Day/Swing Overlap Mode = Separate / Merge Nearby (price distance) for GBPJPY.
(Replaces the time-based GBE-3 / GBJ-6 fixtures; the origin-time data is removed.)

  GD : static — Library = gbe_build.build(); strip_gbe3 gives Library version 2 (3205d03) byte for byte, strip_gbe the
       shared /6; no origin-time field / request change remains; price data (actual pivot / day prices) is state only;
       every scoring change is gated by dsMerge; the predicate (High with High, Low with Low, tick-rounded |day - pivot|
       <= distance, first or latest pivot price, no time) and the adjustment are pinned; Visual / Strategy import
       version 3, carry the same inputs (Separate, 0.05 円 / min 0 / step 0.001) and revert byte for byte to 3205d03
       without GBJ-7; requests / loops / drawing unchanged; FVG reads the Engine baseSum / catCount; Gold, USDJPY and
       shared /6 unchanged
  GM : models — Pine ports of the predicate and of the scoring part of f_finalizeCluster (Swing max, Day H/L, Merge
       Nearby, categories, FVG boost): distance 0, boundary (incl. a float boundary 190.15 - 190.10), inside / outside,
       other dates, High vs Low, previous-day H/L, latest pivot price; mixed cases, ties, HTF, member order invariance;
       Separate equal to the previous scoring; Merge never raises the score / categories
  GU : mutations — High / Low crossed, strict boundary, naive float compare, raw centre / first price only, Confluence
       still double, Day subtracted uniformly, independent top Swing not blocking, previous-day H/L merged

Evidence class: PINE_NOT_VERIFIED. TradingView compile, Library version 3 publish, Strategy Tester external.
"""
import itertools
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
rd = lambda p: __import__("cad_build").pre_cad(p, open(os.path.join(ROOT, p), encoding="utf-8").read() if os.path.exists(os.path.join(ROOT, p)) else "")   # CAD-1 reverted (pinned in cad_sim)
show = lambda p, rev=PREV: subprocess.run(["git", "-C", ROOT, "show", f"{rev}:{p}"], capture_output=True, text=True).stdout
ENG6, GBE, GBE2 = rd(ge.SRC_PATH), rd(ge.GBE_PATH), show(ge.GBE_PATH)
GBV, GBS = rd(gb.GBJ_PATH), gs.strip_qty(rd(gs.GBS_PATH)) or ""   # GBS-4 position size reverted (pinned in gbq_sim)
GBV0, GBS0 = show(gb.GBJ_PATH), show(gs.GBS_PATH)
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


def code_only(src):
    return "\n".join(l for l in src.split("\n") if not l.lstrip().startswith("//"))


def revert7(text, skip_header=True):
    out = text
    for kind, a, b in list(reversed(gb.EDITS7)) + list(reversed(gb.EDITS6)):
        if kind == "header" and skip_header:
            continue
        out = out.replace(b, a) if out is not None and out.count(b) == 1 else None
    return out


PROTECTED = ["ZoneEnginePracticalSwingMax.pine", "ZoneEnginePractical.pine", "ZoneEnginePracticalRN.pine",
             "ZoneEnginePracticalAuthority.pine", "ZoneVisualPractical.pine", "ZoneStrategyXAU.pine",
             "ZoneVisualUSDJPY.pine", "ZoneStrategyUSDJPY.pine", "PracticalZoneStrategy_LONG.pine",
             "PracticalZoneStrategy_SHORT.pine", "SignalEnginePractical.pine"]
MATCH_H = ('bool mH = dsOn and m.srcId == "SWING_H" and not na(dHpx) and (math.round(math.abs(dHpx - m.px0) / syminfo.mintick) '
           '<= dsTk or math.round(math.abs(dHpx - m.px1) / syminfo.mintick) <= dsTk)')
MATCH_L = MATCH_H.replace("mH", "mL").replace("SWING_H", "SWING_L").replace("dHpx", "dLpx")


def gate_static():
    check("GD-01 Library = gbe_build.build() (rebuild identical); reverting GBE-4 gives Library version 2 (" + PREV + ") "
          "byte for byte, reverting GBE-4 / 2 / 1 the shared ZoneEnginePractical/6; no origin-time data left (dayHighT / "
          "oT / oMs / oDay0 / pivot-time feed fields removed)",
          bool(GBE) and ge.build() == GBE and ge.strip_gbe3(GBE) == GBE2 and bool(GBE2) and ge.strip_gbe(GBE) == ENG6
          and not re.search(r"\b(dayHighT|dayLowT|dayStartT|oT|oMs|oDay0|ph1o|pl1o|dsDedup|hzMs1)\b", GBE))
    fc = tb.func(GBE, "f_finalizeCluster(")
    gated = ["    if dsOn\n        for j = 0 to n - 1\n", "    if dsOn and (dHm or dLm)\n"]
    seg = fc[fc.index("bool mH"):fc.index("int  sl")]
    check("GD-02 Library: price data is state only (static raws keep the actual registered price px0 and the latest merged "
          "event price px1; Day raws carry the actual day extreme); every scoring change is gated by dsMerge; predicate: "
          "Day High with Swing High / Day Low with Swing Low only, tick-rounded |day - pivot| <= round(distance / "
          "mintick) for the first or latest pivot price, no time, no raw centre",
          all(fc.count(g) == 1 for g in gated) and fc.count(MATCH_H) == 1 and fc.count(MATCH_L) == 1
          and "int   dsTk   = dsOn ? math.round(c.dsDist / syminfo.mintick) : 0" in fc
          and not re.search(r"center|time|zoneHalfWidth|clusterDist", seg)
          and "                    z.px1 := price" in GBE and "            rz.px0 := price\n            rz.px1 := price\n" in GBE
          and "        dhz.px0 := e.dayHigh\n" in GBE and "        dlz.px0 := e.dayLow\n" in GBE
          and "            baseSum -= math.min(c.scoreDayHL, swMax)\n" in fc and "- dsCatAdj\n" in fc
          and "bool   dsMerge            = false" in GBE and "float  dsDist             = 0.05" in GBE)
    inp = lambda s, n: re.search(r"^" + n + r" = input\.\w+\((.*)$", s, re.M)
    cfg = ['zoneCfg.dsMerge              := dsMode == "Merge Nearby"\n', "zoneCfg.dsDist               := dsDist\n"]
    check("GD-03 Visual and Strategy import Library version 3, same inputs Day/Swing Overlap Mode (default Separate, "
          "Separate / Merge Nearby) and Merge Distance (0.05 円, minval 0, step 0.001, separate from Cluster Distance), "
          "same config lines; without the GBJ-7 edits both files are the " + PREV + " files byte for byte (no Swing "
          "request / tuple change, no pivot-time data)",
          all(re.findall(r"^import .*$", s, re.M) == [ge.IMPORT_GBE.strip()] for s in (GBV, GBS))
          and all(inp(s, "dsMode") and inp(s, "dsDist") for s in (GBV, GBS))
          and inp(GBV, "dsMode").group(1) == inp(GBS, "dsMode").group(1)
          and inp(GBV, "dsMode").group(1).startswith('"Separate", "Day/Swing Overlap Mode", options = ["Separate", "Merge Nearby"]')
          and inp(GBV, "dsDist").group(1) == inp(GBS, "dsDist").group(1)
          and inp(GBV, "dsDist").group(1).startswith('0.05, "[暫定] Day/Swing Merge Distance (円)", minval = 0.0, step = 0.001')
          and all(GBV.count(c) == 1 and GBS.count(c) == 1 for c in cfg)
          and "time[len]" not in GBV and "ph1o" not in GBV and "time[len]" not in GBS
          and revert7(GBV, skip_header=False) == GBV0 and bool(GBV0) and revert7(GBS) == GBS0 and bool(GBS0))
    req = lambda s: re.findall(r"request\.\w+\(.*$", code_only(s), re.M)
    cnt = lambda s, p: len(re.findall(p, code_only(s)))
    dline = "        dScore := z.baseSum + f_fvcBase(best) + z.slopeBonus + z.maBonus + z.flipBonus + f_fvcConf(z.catCount + 1)\n"
    check("GD-04 lightweight: requests identical to " + PREV + " (10 / 11), zone loops, drawing, str.*, plot and loops "
          "unchanged in the scripts; the Library gains one loop, the Merge-only scan of the cluster's own members (no "
          "history / zone-wide search, no request); FVG boost reads the Engine baseSum and catCount; lint clean",
          req(GBV) == req(GBV0) and req(GBS) == req(GBS0) and len(req(GBV)) == 10 and len(req(GBS)) == 11
          and all(cnt(n, p) == cnt(o, p) for n, o in ((GBV, GBV0), (GBS, GBS0))
                  for p in (r"zn\.zoneAt\(", r"\b(box|label|table|line)\.new\(", r"\bstr\.\w+\(", r"\bplot\w*\(",
                            r"\bfor\b", r"\bwhile\b"))
          and cnt(GBE, r"\bfor\b") == cnt(GBE2, r"\bfor\b") + 1 and cnt(GBE, r"request\.") == 0
          and GBV.count(dline) == 1 and GBS.count(dline) == 1
          and fr.lint_eager_guards(code_only(GBV)) == [] and fr.lint_eager_guards(code_only(GBS)) == [])
    d = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", PREV, "--"] + PROTECTED, capture_output=True, text=True)
    t = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", "--diff-filter=MDR", PREV, "--", "tests/"],
                       capture_output=True, text=True).stdout
    check("GD-05 shared Engine /6 (and /2, /5, Authority), Gold, USDJPY and old strategies unchanged vs " + PREV
          + "; only GBPJPY tests / generators changed",
          d.returncode == 0 and __import__("uj_build").drop_uj(d.stdout.split(), PREV) == [] and all(re.match(r"^tests/gb[defjsx]_\w+\.py$", f) for f in __import__("uj_build").drop_uj_tests(t.split())),
          d.stdout + t)


# ---- mirrors ------------------------------------------------------------------------------------------------------------
TICK = 0.001
SW = {"5": 1.0, "15": 2.0, "60": 3.0}
DAY = 2.0
conf = lambda c: 3.0 if c >= 4 else {2: 1.0, 3: 2.0}.get(c, 0.0)


def strength(s, htf, thr=(5.0, 9.0, 15.0)):
    t = 1 if s < thr[0] else 2 if s < thr[1] else 3 if s < thr[2] else 4
    return 3 if t == 4 and not htf else t


def near(day_px, px, dist, variant=None):
    if variant == "naive":
        return abs(day_px - px) <= dist
    if variant == "strict":
        return round(abs(day_px - px) / TICK) < round(dist / TICK)
    return round(abs(day_px - px) / TICK) <= round(dist / TICK)


def matched(sw, day_px, dist, variant=None):
    """sw = (kind, px0, px1); the Library predicate for one Swing against the same-kind Day price."""
    if day_px is None:
        return False
    if variant in ("center_only", "first_only"):
        return near(day_px, sw[1], dist)
    return near(day_px, sw[1], dist, variant) or near(day_px, sw[2], dist, variant)


def score(members, merge, dist=0.05, variant=None, fvg=None, sw_scores=SW):
    """members: ("SW", tf, kind, px0, px1) / ("DAY", kind, px) / ("PDH", kind, px) / ("MA",)."""
    day = {m[1]: m[2] for m in members if m[0] == "DAY"}
    base, sw_max, hits = 0.0, None, set()
    dm = {"H": False, "L": False}
    hz_ind, sw_ind, cats, htf = False, set(), set(), False
    for m in members:
        if m[0] == "SW":
            tf, kind = m[1], m[2]
            other = "L" if kind == "H" else "H"
            dp = day.get(other if variant == "crossed" else kind)
            mt = merge and matched((kind, m[3], m[4]), dp, dist, variant)
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
            if variant == "pdh_merged" and merge and m[1] in day and near(day[m[1]], m[2], dist):
                base -= min(DAY, 2.0)
            else:
                hz_ind = True
        elif m[0] == "MA":
            base += 2.0
            cats.add("MA")
    cat_adj = 0
    if merge and (dm["H"] or dm["L"]):
        tops = [tf for tf in hits if sw_scores[tf] == sw_max]
        blocked = any(tf in sw_ind for tf in tops) and variant != "no_block"
        if variant == "uniform":
            base -= DAY
        elif not blocked and tops:
            base -= min(DAY, sw_max)
        dhl_ind = ("H" in day and not dm["H"]) or ("L" in day and not dm["L"])
        if not hz_ind and not dhl_ind and not (dm["H"] and dm["L"]) and variant != "conf_double":
            cat_adj = 1
    cat = len(cats) - cat_adj
    sc = base + conf(cat)
    out = dict(base=base, cat=cat, score=sc, str=strength(sc, htf), htf=htf)
    if fvg:
        ds = base + {"15": 1.0, "60": 2.0, "240": 3.0}[fvg] + conf(cat + 1)
        out.update(dScore=ds, dStr=strength(ds, htf), eligible=out["str"] >= 3 or strength(ds, htf) >= 3)
    return out


DH = lambda px=210.300: ("DAY", "H", px)
DL = lambda px=209.700: ("DAY", "L", px)
SWH = lambda tf, px=210.300, px1=None: ("SW", tf, "H", px, px if px1 is None else px1)
SWL = lambda tf, px=209.700, px1=None: ("SW", tf, "L", px, px if px1 is None else px1)


def match_fixtures(mf=matched, sc=score):
    out = []
    out.append(("distance 0: identical price merges, 0.001 apart does not",
                mf(("H", 210.300, 210.300), 210.300, 0.0) and not mf(("H", 210.301, 210.301), 210.300, 0.0)))
    out.append(("boundary 0.050 with distance 0.05: 210.35 / 210.30 and the float case 190.15 / 190.10 "
                "(|diff| = 0.05000000000001 in floats) both merge",
                mf(("H", 210.350, 210.350), 210.300, 0.05) and mf(("H", 190.150, 190.150), 190.100, 0.05)))
    out.append(("inside 0.049 merges, outside 0.051 does not",
                mf(("H", 210.349, 210.349), 210.300, 0.05) and not mf(("H", 210.351, 210.351), 210.300, 0.05)))
    out.append(("latest merged pivot price within the distance (first one outside) merges; first within / latest outside "
                "merges too", mf(("H", 210.400, 210.320), 210.300, 0.05) and mf(("H", 210.320, 210.400), 210.300, 0.05)))
    a = sc([SWH("5", 210.320), DH(210.300)], True)
    out.append(("no time / date condition: a Swing from another day at a near price merges (the mirror has no time input)",
                (a["score"], a["cat"]) == (2.0, 1)))
    b = sc([SWL("5", 210.300), DH(210.300)], True)
    out.append(("Swing Low at the Day High price is not merged (High with High, Low with Low only)",
                (b["score"], b["cat"]) == (sc([SWL("5", 210.300), DH(210.300)], False)["score"], 2)))
    c = sc([SWH("5", 210.400), DH(210.300)], True)
    out.append(("outside the distance (0.10 apart) -> Separate scoring", (c["score"], c["cat"]) == (4.0, 2)))
    d = sc([("PDH", "H", 210.300), DH(210.300)], True)
    out.append(("previous-day H/L at the same price is not merged (out of scope; stays an independent Horizontal)",
                (d["score"], d["cat"]) == (5.0, 2) == (sc([("PDH", "H", 210.300), DH(210.300)], False)["score"], 2)))
    return out


def score_fixtures(sc=score):
    out = []
    cases = [  # name, members, (Separate score, cat), (Merge score, cat)
        ("A Day High 210.300 + 5M Swing High 210.320", [SWH("5", 210.320), DH()], (4.0, 2), (2.0, 1)),
        ("B Day High + 1H Swing High 210.280", [SWH("60", 210.280), DH()], (6.0, 2), (3.0, 1)),
        ("C A + 1H Swing High 210.360 (0.06 away, independent)", [SWH("5", 210.320), SWH("60", 210.360), DH()],
         (6.0, 2), (6.0, 2)),
        ("D B + 15M Swing High 210.360 (independent)", [SWH("60", 210.280), SWH("15", 210.360), DH()], (6.0, 2), (4.0, 2)),
        ("E Day High + 5M / 15M / 1H Swing Highs all within 0.05",
         [SWH("5", 210.320), SWH("15", 210.290), SWH("60", 210.310), DH()], (6.0, 2), (3.0, 1)),
        ("F A + Day Low not merged", [SWH("5", 210.320), DH(), DL()], (6.0, 2), (5.0, 2)),
        ("G Day High + 1H Swing High, Day Low + 1H Swing Low (both merged)",
         [SWH("60", 210.280), SWL("60", 209.720), DH(), DL()], (8.0, 2), (6.0, 2)),
        ("H Day High + 5M Swing High 0.10 away", [SWH("5", 210.400), DH()], (4.0, 2), (4.0, 2)),
        ("I B + MA #1", [SWH("60", 210.280), DH(), ("MA",)], (9.0, 3), (6.0, 2)),
        ("J A + previous-day high (independent Horizontal)", [SWH("5", 210.320), DH(), ("PDH", "H", 210.300)],
         (6.0, 2), (5.0, 2)),
    ]
    for name, mem, sep, mer in cases:
        a, b = sc(mem, False), sc(mem, True)
        out.append((f"{name}: Separate {sep[0]:g} ({sep[1]} cat), Merge {mer[0]:g} ({mer[1]} cat)",
                    (a["score"], a["cat"]) == sep and (b["score"], b["cat"]) == mer))
    tie = dict(SW, **{"15": 3.0})
    mem = [SWH("60", 210.280), SWH("15", 210.360), DH()]
    r = sc(mem, True, sw_scores=tie)
    out.append(("tie (15M input 3 = 1H 3): the independent 15M Swing also earns the top -> no adjustment, 6 (2 cat)",
                (r["score"], r["cat"]) == (6.0, 2)))
    out.append(("HTF kept from the actual 1H Swing under Merge; none without it",
                sc([SWH("60", 210.280), DH()], True)["htf"] and sc([SWH("5", 210.320), DH()], True)["htf"] is False))
    i_s = sc([SWH("60", 210.280), DH(), ("MA",)], False, fvg="60")
    i_m = sc([SWH("60", 210.280), DH(), ("MA",)], True, fvg="60")
    out.append(("FVG follows: I + 1H FVG: Separate 9 Strong -> 12; Merge 6 Medium -> 5 + 2 + 2 = 9 Strong boost "
                "(eligible via the boost range)", (i_s["str"], i_s["dScore"]) == (3, 12.0)
                and (i_m["score"], i_m["str"], i_m["dScore"], i_m["dStr"], i_m["eligible"]) == (6.0, 2, 9.0, 3, True)))
    perm = [SWH("60", 210.280), SWL("15", 209.720), SWH("5", 210.400), DH(), DL(), ("MA",)]
    res = {tuple(sorted(sc(list(p), True).items())) for p in itertools.permutations(perm)}
    out.append((f"member order invariance: all {len(list(itertools.permutations(perm)))} orders of a mixed cluster give "
                "the same Merge result", len(res) == 1))
    return out


def prev_score(members):
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
    rng = random.Random(9)
    bad = 0
    pxs = [210.300, 210.320, 210.350, 210.351, 210.400, 209.700, 209.720, 209.751]
    for _ in range(3000):
        mem = []
        for _ in range(rng.randint(1, 7)):
            k = rng.random()
            if k < 0.5:
                mem.append(rng.choice([SWH, SWL])(rng.choice(list(SW)), rng.choice(pxs), rng.choice(pxs)))
            elif k < 0.7:
                mem.append(rng.choice([DH(), DL()]))
            elif k < 0.85:
                mem.append(("MA",))
            else:
                mem.append(("PDH", rng.choice("HL"), rng.choice(pxs)))
        r = score(mem, False)
        bad += (r["score"], r["cat"]) != prev_score(mem)
        dist = rng.choice([0.0, 0.02, 0.05, 0.1])
        m2 = score(mem, True, dist)
        bad += m2["score"] > r["score"] + 1e-12 or m2["cat"] > r["cat"] or m2["htf"] != r["htf"]
        sh = list(mem)
        rng.shuffle(sh)
        bad += score(sh, True, dist) != m2
    check("GM Separate equals the previous scoring on 3000 random clusters; Merge never raises the score or the category "
          "count, keeps HTF and is invariant to member order (random distances 0 / 0.02 / 0.05 / 0.1)", bad == 0, str(bad))


def gate_mutation():
    mm = {
        "strict boundary (<)": lambda s, d, x, v=None: matched(s, d, x, "strict"),
        "naive float compare": lambda s, d, x, v=None: matched(s, d, x, "naive"),
        "raw centre / first pivot price only": lambda s, d, x, v=None: matched(s, d, x, "center_only"),
    }
    caught = {k: not all(ok for _, ok in match_fixtures(mf=f)) for k, f in mm.items()}
    sm = {
        "High / Low crossed": "crossed", "Confluence still double": "conf_double", "Day subtracted uniformly": "uniform",
        "independent top Swing not blocking": "no_block", "previous-day H/L merged": "pdh_merged",
    }
    for k, v in sm.items():
        f = lambda m, mg, dist=0.05, v=v, **kw: score(m, mg, dist, variant=v, **kw)
        caught[k] = not (all(ok for _, ok in score_fixtures(f)) and all(ok for _, ok in match_fixtures(sc=f)))
    check("GU-01 mirror mutations caught (" + str(len(caught)) + "): " + ", ".join(caught), all(caught.values()), str(caught))
    src = {
        "Library: High compared with the Day Low": ("GBE", 'm.srcId == "SWING_H" and not na(dHpx)', 'm.srcId == "SWING_H" and not na(dLpx)'),
        "Library: strict boundary": ("GBE", "/ syminfo.mintick) <= dsTk or", "/ syminfo.mintick) < dsTk or"),
        "Library: raw centre instead of the pivot price": ("GBE", "math.abs(dHpx - m.px0)", "math.abs(dHpx - m.center)"),
        "Library: category not merged": ("GBE", "+ (hasRN ? 1 : 0) - dsCatAdj\n", "+ (hasRN ? 1 : 0)\n"),
        "Scripts: mode mapped inverted": ("BOTH", 'dsMode == "Merge Nearby"', 'dsMode == "Separate"'),
        "Scripts: distance not passed": ("BOTH", "zoneCfg.dsDist               := dsDist\n", ""),
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
