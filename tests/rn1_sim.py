"""RN-1 Gate L1 fixtures — ZoneEnginePracticalRN.pine (Round Number score-only confluence source).

  RS : static — exact transform of the old Engine, old Engine / Visual / Strategy untouched, bits, gating, defaults
  RM : mirror of f_finalizeCluster + RN (levels, points, boundaries, ties, categories, HTF, OFF parity, FVG base)
  RX : RN-2 restoration (RN-free score / strength rebuilt exactly, incl. flip, 0.1 steps, threshold boundaries)
  RT : Touch scenario (MEDIUM -> STRONG by RN, RN leaves / re-enters, reset, STRONG -> VERY STRONG, OFF = old)
  RY : time-series Engine model RN ON / OFF (geometry, Track, Break / Flip, events unchanged; only score / Touch)

Evidence class: PINE_NOT_VERIFIED (exact transform / static / Python mirror; TradingView compile / publish external).
"""
import math
import os
import random
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rn1_build as rb                # noqa: E402
import practical_zone_sim as pz       # noqa: E402
import fvg_re10045_sim as fr          # noqa: E402

ROOT = rb.ROOT
RN_TXT = open(os.path.join(ROOT, rb.RN_PATH), encoding="utf-8").read() if os.path.exists(os.path.join(ROOT, rb.RN_PATH)) else ""
OLD_TXT = open(os.path.join(ROOT, rb.OLD_PATH), encoding="utf-8").read()
BASE_OLD = rb.git_show(rb.RN_BASE_REV, rb.OLD_PATH)
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


def code_only(src):
    return "\n".join(l for l in src.split("\n") if not l.lstrip().startswith("//"))


def func(src, head):
    """top-level Pine function text: from its header to the next top-level line."""
    i = src.index(head)
    m = re.search(r"\n(?=\S)", src[i + len(head):])
    return src[i:i + len(head) + (m.start() + 1 if m else len(src))]


# =============================================================================
# RS : static
# =============================================================================
def gate_static():
    check("RS-01 ZoneEnginePracticalRN.pine == rn_transform(ZoneEnginePractical.pine @ f4b881b) exactly (8 RN edits)",
          bool(RN_TXT) and rb.rn_transform(BASE_OLD) == RN_TXT)
    check("RS-02 strip_rn(RN file) == old Engine byte-for-byte (nothing else differs)", rb.strip_rn(RN_TXT) == BASE_OLD)
    prod = ["ZoneEnginePractical.pine", "ZoneVisualPractical.pine", "ZoneEnginePracticalAuthority.pine", "ZoneEngine.pine",
            "SignalEnginePractical.pine", "SignalEngine.pine", "PracticalZoneStrategy_LONG.pine",
            "PracticalZoneStrategy_SHORT.pine", "FvgZoneStrategy.pine", "PracticalZoneFeedHarness.pine",
            "PracticalAlertHarness.pine", "PracticalTradeHarness.pine", "PracticalBreakEvenHarness.pine",
            "PracticalEntryDispatchHarness.pine"]
    d = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", rb.RN_BASE_REV, "--"] + prod, capture_output=True, text=True).stdout
    check("RS-03 old Engine (/2 reference), Visual, Strategy, SignalEngine, Harness unchanged vs f4b881b",
          d.strip() == "" and OLD_TXT == BASE_OLD, d)
    lib = re.findall(r'^library\("([^"]+)"', RN_TXT, re.M)
    check("RS-04 same library name (new version of ZoneEnginePractical, not a new library)", lib == ["ZoneEnginePractical"], str(lib))
    src_bits = dict((n, int(v)) for n, v in re.findall(r"^int (SRC_\w+)\s*=\s*(\d+)", RN_TXT, re.M))
    vals = list(src_bits.values())
    check("RS-05 srcMask bits: distinct powers of two, SRC_RN = 1024 unused before (old max 512)",
          src_bits.get("SRC_RN") == 1024 and len(set(vals)) == len(vals) and all(v & (v - 1) == 0 for v in vals)
          and "SRC_RN" not in BASE_OLD and max(v for k, v in src_bits.items() if k != "SRC_RN") == 512, str(src_bits))
    htf_old = re.findall(r"^int (HTF_\w+)\s*=\s*(\d+)", BASE_OLD, re.M)
    rn_part = code_only(func(RN_TXT, "f_finalizeCluster("))
    rn_block = rn_part[rn_part.index("float baseSumEx = baseSum"):rn_part.index("float rnD")]
    check("RS-06 HTF untouched: same HTF_* bits, the RN code never touches htfM / HTF_* / hasHtf",
          re.findall(r"^int (HTF_\w+)\s*=\s*(\d+)", RN_TXT, re.M) == htf_old
          and not re.search(r"htfM|HTF_|hasHtf", rn_block), rn_block[:120])
    check("RS-07 Library default OFF: ZoneCfg.useRnSource = false; 100 -> 3 / 50 -> 2",
          "    bool   useRnSource        = false\n" in RN_TXT and "    float  rnStepMajor        = 100.0\n" in RN_TXT
          and "    float  rnScoreMajor       = 3.0\n" in RN_TXT and "    float  rnStepMinor        = 50.0\n" in RN_TXT
          and "    float  rnScoreMinor       = 2.0\n" in RN_TXT)
    # gating: rnB / rnLv assigned only inside `if c.useRnSource`; baseSum / srcM changed only inside `if hasRN`
    fz = func(RN_TXT, "f_finalizeCluster(")
    has_gate = fz.count("    if c.useRnSource\n") == 1 and fz.count("    bool hasRN = rnB > 0\n") == 1
    inside = fz[fz.index("    if c.useRnSource\n"):fz.index("    bool hasRN = rnB > 0\n")] if has_gate else ""
    outside = fz.replace(inside, "") if has_gate else fz
    check("RS-08 OFF parity by construction: RN level / points set only inside `if c.useRnSource`; hasRN = rnB > 0; "
          "baseSum += rnB and the SRC_RN bit only inside `if hasRN`; category term (hasRN ? 1 : 0); rnD 0 when no RN",
          has_gate and outside.count("rnB  :=") == 0 and inside.count("rnB  :=") == 2
          and fz.count("    if hasRN\n        baseSum += rnB\n        srcM := f_setBit(srcM, SRC_RN)\n") == 1
          and fz.count("baseSum += rnB") == 1 and fz.count("(hasRN ? 1 : 0)") == 1
          and "    float rnD   = hasRN ? rnB + (confB - f_confluenceBonus(cat - 1, c)) : 0.0\n" in fz
          and "    float baseSumEx = baseSum\n" in fz and fz.index("float baseSumEx = baseSum") < fz.index("baseSum += rnB"))
    check("RS-09 Zone.new carries rnLevel / rnBase / rnScoreDelta / rnBaseSumExRn (= baseSum before RN); Zone type "
          "defaults na / 0 / 0 / 0",
          "rnLevel = rnLv, rnBase = rnB, rnScoreDelta = rnD, rnBaseSumExRn = baseSumEx)" in fz
          and all(s in RN_TXT for s in ("    float  rnLevel       = na", "    float  rnBase        = 0.0",
                                         "    float  rnScoreDelta  = 0.0", "    float  rnBaseSumExRn = 0.0")))
    lv = func(RN_TXT, "f_rnLevelIn(")
    check("RS-10 f_rnLevelIn: boundaries included (ceil(bottom / step) .. floor(top / step)), nearest the centre, strict `<` "
          "(equal distance -> lower), major before minor",
          "int k1 = math.ceil(zBot / step)" in lv and "int k2 = math.floor(zTop / step)" in lv
          and "if (kc + 1) * step - ctr < ctr - lv" in lv
          and fz.count("float lvMaj = f_rnLevelIn(zBot, zTop, c.rnStepMajor)") == 1
          and fz.count("float lvMin = f_rnLevelIn(zBot, zTop, c.rnStepMinor)") == 1
          and fz.index("float lvMaj = f_rnLevelIn(zBot, zTop, c.rnStepMajor)") < fz.index("float lvMin = f_rnLevelIn(zBot, zTop, c.rnStepMinor)"))
    old_new = func(BASE_OLD, "f_finalizeCluster(")
    geo = lambda t: t[t.index("    Zone.new(\n"):t.index("         srcMask = srcM, htfMask = htfM")]
    check("RS-13 zone geometry untouched by RN: the Zone.new centre / top / bottom / members / counts arguments are the old "
          "text; zBot / zTop are never reassigned", "    Zone.new(\n" in fz and geo(fz) == geo(old_new)
          and not re.search(r"\bz(Bot|Top)\s*:=", fz))
    same = ["f_updateTouch(", "f_updateTrack(", "f_findTrack(", "f_trackContinuous(", "f_buildClusters(", "f_applyStrength(",
            "export update(", "f_registerStatic(", "f_registerAccumZone(", "f_pruneAccumGenerations(", "f_prunePersist(",
            "f_strengthOf(", "f_confluenceBonus(", "export accumPack(", "export pivotPack(", "export maPack(", "export drawOrder(",
            "export getLongStructuralSL(", "export buildPlan("]
    diff = [h for h in same if func(RN_TXT, h) != func(BASE_OLD, h)]
    check("RS-11 Touch / Track / Break / Flip / Cluster / strength / registration / source packs / SL-TP API functions "
          "byte-identical to the old Engine", diff == [], str(diff))
    check("RS-12 RN code lint: no request / barstate / var; RE10045 pattern clean",
          not re.search(r"request\.|barstate|\bvar\b", code_only(lv + rn_block)) and fr.lint_eager_guards(code_only(lv + rn_block)) == [])


# =============================================================================
# RM : mirror of f_finalizeCluster + RN
# =============================================================================
class Cfg(pz.Cfg):
    zoneHalfWidth = 3.0
    clusterDist = 5.0


def conf(c, n):
    return c.confBonus4 if n >= 4 else c.confBonus3 if n == 3 else c.confBonus2 if n == 2 else 0.0


def rn_level_in(zBot, zTop, step):
    k1, k2 = math.ceil(zBot / step), math.floor(zTop / step)
    if k1 > k2:
        return None
    ctr = (zTop + zBot) / 2
    kc = max(k1, min(k2, math.floor(ctr / step)))
    lv = kc * step
    if kc + 1 <= k2 and (kc + 1) * step - ctr < ctr - lv:
        lv = (kc + 1) * step
    return float(lv)


def finalize(members, c, zBot, zTop, use_rn, major=(100.0, 3.0), minor=(50.0, 2.0)):
    """f_finalizeCluster (old body via pz.score_parts, member order) + the RN-1 part."""
    baseSum, slopeB, maB, _r, _cf, htf = pz.score_parts(members, c)
    cats = {m.srcCat for m in members}
    baseSumEx, rnLv, rnB = baseSum, None, 0.0
    if use_rn:
        lv = rn_level_in(zBot, zTop, major[0])
        if lv is not None:
            rnLv, rnB = lv, major[1]
        else:
            lv = rn_level_in(zBot, zTop, minor[0])
            if lv is not None:
                rnLv, rnB = lv, minor[1]
    hasRN = rnB > 0
    if hasRN:
        baseSum += rnB
    cat = len(cats) + (1 if hasRN else 0)
    confB = conf(c, cat)
    rnD = rnB + (confB - conf(c, cat - 1)) if hasRN else 0.0
    return dict(top=zTop, bottom=zBot, baseSum=baseSum, slopeB=slopeB, maB=maB, confB=confB, catCount=cat, hasHtf=htf,
                score=baseSum + slopeB + maB + confB, rnLevel=rnLv, rnBase=rnB, rnScoreDelta=rnD, rnBaseSumExRn=baseSumEx,
                srcRN=hasRN, uids=[m.uid for m in members])


def apply_strength(z, c, flip):
    """f_applyStrength order: baseSum + slopeBonus + maBonus + flipBonus + confBonus."""
    s = z["baseSum"] + z["slopeB"] + z["maB"] + flip + z["confB"]
    return s, pz.strength_of(s, z["hasHtf"], c)


def restore(z, c, flip):
    """RN-2: RN-free score rebuilt in the old f_applyStrength order."""
    s = z["rnBaseSumExRn"] + z["slopeB"] + z["maB"] + flip + conf(c, z["catCount"] - (1 if z["rnBase"] > 0 else 0))
    return s, pz.strength_of(s, z["hasHtf"], c)


def raw(uid, sid, cat, tf, ctr, bs, c, slope=0.0, mcb=0.0):
    return pz.Raw(uid, sid, cat, tf, ctr, bs, c, slopeBonus=slope, maClusterBonus=mcb)


def cl1(members, c, use_rn):
    zb = min(m.bottom for m in members)
    zt = max(m.top for m in members)
    return finalize(members, c, zb, zt, use_rn)


def gate_mirror():
    c = Cfg()
    sw = lambda u, x, tf="60", bs=3.0: raw(u, "SWING_H", pz.CAT_HZ, tf, x, bs, c)
    acc = lambda u, x, tf="240", bs=4.0: raw(u, "ACC_HI", pz.CAT_ACC, tf, x, bs, c)
    dhl = lambda u, x: raw(u, "DAY_HIGH", pz.CAT_DHL, "D", x, 3.0, c)
    ma = lambda u, x: raw(u, "MA1", pz.CAT_MA, "1", x, 2.0, c)
    cases = [((4197, 4203), (4200.0, 3.0)), ((4147, 4153), (4150.0, 2.0)), ((4140, 4205), (4200.0, 3.0)),
             ((4201, 4249), (None, 0.0)), ((4203, 4209), (None, 0.0)),
             ((4200, 4206), (4200.0, 3.0)), ((4194, 4200), (4200.0, 3.0)), ((4150, 4156), (4150.0, 2.0)),
             ((4144, 4150), (4150.0, 2.0)), ((4200.01, 4206), (None, 0.0)), ((4193.5, 4199.99), (None, 0.0))]
    got = [(b, finalize([], c, b[0], b[1], True)["rnLevel"], finalize([], c, b[0], b[1], True)["rnBase"]) for b, _ in cases]
    check("RM-01 levels / points: 100-multiple 3, else 50-multiple 2, 100 wins when both inside, none outside; boundary "
          "(level == bottom / top) included, just outside excluded",
          all((g[1], g[2]) == e for g, (_, e) in zip(got, cases)), str(got))
    multi = [((4090, 4310), 4200.0), ((4100, 4300), 4200.0), ((4100, 4200), 4100.0), ((4150, 4350), 4200.0),
             ((4060, 4290), 4200.0), ((4110, 4295), 4200.0), ((4130, 4380), 4300.0)]
    gm = [(b, finalize([], c, b[0], b[1], True)["rnLevel"]) for b, _ in multi]
    check("RM-02 several same-rank levels (wide non-default zones): nearest the zone centre, equal distance -> lower price",
          all(g[1] == e for g, (_, e) in zip(gm, multi)), str(gm))
    # categories / confluence / HTF / delta
    rows = []
    for name, mem, exp in (
            ("Swing 1H at 4200", [sw(1, 4200)], dict(cat=(1, 2), conf=(0.0, 1.0), base=(3.0, 6.0), delta=4.0)),
            ("Swing + Accum + DayHL", [sw(1, 4200), acc(2, 4201), dhl(3, 4199)], dict(cat=(3, 4), conf=(2.0, 3.0), base=(10.0, 13.0), delta=4.0)),
            ("4 categories + RN (cap)", [sw(1, 4200), acc(2, 4201), dhl(3, 4199), ma(4, 4200.5)], dict(cat=(4, 5), conf=(3.0, 3.0), base=(12.0, 15.0), delta=3.0)),
            ("two Swings same TF (one hit) + RN", [sw(1, 4199), sw(2, 4201)], dict(cat=(1, 2), conf=(0.0, 1.0), base=(3.0, 6.0), delta=4.0))):
        off, on = cl1(mem, c, False), cl1(mem, c, True)
        ok = (off["catCount"], on["catCount"]) == exp["cat"] and (off["confB"], on["confB"]) == exp["conf"] \
            and (off["baseSum"], on["baseSum"]) == exp["base"] and on["rnScoreDelta"] == exp["delta"] \
            and on["score"] - off["score"] == exp["delta"] and on["hasHtf"] == off["hasHtf"] \
            and on["rnBaseSumExRn"] == off["baseSum"] and (on["top"], on["bottom"], on["uids"]) == (off["top"], off["bottom"], off["uids"])
        rows.append((name, ok))
    check("RM-03 RN = one independent confluence category (cap at 4+ kept); base +3 once; rnScoreDelta = base + confluence "
          "step; hasHtf, geometry and members identical ON / OFF", all(ok for _, ok in rows), str(rows))
    # RN alone never makes a zone; RN never sets HTF
    nohtf = cl1([raw(1, "SWING_H", pz.CAT_HZ, "5", 4200, 1.0, c)], c, True)
    check("RM-04 RN gives no HTF: a non-HTF cluster with RN stays hasHtf = false; there is no RN-only zone (no member, no "
          "cluster)", nohtf["hasHtf"] is False and pz.practical_build([], [], c) == [])
    # OFF parity: random clusters, OFF finalize == old score_parts based finalize, fields default
    rnd, ok_off = random.Random(3), True
    for _ in range(3000):
        mem = []
        for u in range(rnd.randint(1, 5)):
            kind = rnd.choice(("sw", "acc", "dhl", "ma"))
            x = 4180 + rnd.uniform(0, 40)
            mem.append({"sw": lambda: sw(u, x, rnd.choice(("5", "15", "60"))), "acc": lambda: acc(u, x, rnd.choice(("60", "240", "D"))),
                        "dhl": lambda: dhl(u, x), "ma": lambda: ma(u, x)}[kind]())
        for z in pz.practical_build(mem, [], c):
            ms = [m for m in mem if m.uid in z["uids"]]
            off = finalize(ms, c, z["bottom"], z["top"], False)
            ok_off &= off["score"] == z["score"] and off["baseSum"] == z["baseSum"] and off["confB"] == z["confB"] \
                and off["hasHtf"] == z["hasHtf"] and off["rnLevel"] is None and off["rnBase"] == 0.0 \
                and off["rnScoreDelta"] == 0.0 and off["rnBaseSumExRn"] == off["baseSum"] and not off["srcRN"]
    check("RM-05 OFF: 3000 random clusters, every old field equal to the old finalize; rnLevel na / rnBase 0 / "
          "rnScoreDelta 0 / rnBaseSumExRn = baseSum; no SRC_RN bit", ok_off)
    # FVG Batch C base values: RN counted once
    z0, z1 = cl1([sw(1, 4200), acc(2, 4201)], c, False), cl1([sw(1, 4200), acc(2, 4201)], c, True)
    fv = lambda z, b: z["baseSum"] + b + z["slopeB"] + z["maB"] + 0.0 + conf(c, z["catCount"] + 1)
    check("RM-06 FVG Batch C display base: (baseSum + FVG + ... + conf(catCount + 1)) includes RN exactly once "
          "(ON - OFF = rnBase + confluence step at catCount + 1, never 2 x rnBase)",
          fv(z1, 3.0) - fv(z0, 3.0) == z1["rnBase"] + (conf(c, z1["catCount"] + 1) - conf(c, z0["catCount"] + 1)),
          f"{fv(z0, 3.0)} -> {fv(z1, 3.0)}")


# =============================================================================
# RX : RN-2 restoration
# =============================================================================
def gate_restore():
    rnd = random.Random(11)
    exact = naive_bad = n = thr_cases = 0
    bad_exact = []
    for trial in range(60000):
        c = Cfg()
        dec = trial % 3                                   # 0: 0.5 steps, 1: 0.1 steps, 2: 0.01 steps
        q = (0.5, 0.1, 0.01)[dec]
        rv = lambda lo, hi: round(rnd.randint(int(lo / q), int(hi / q)) * q, 2)
        c.scoreHz1, c.scoreHz2, c.scoreHz3 = rv(0, 3), rv(0, 4), rv(0, 5)
        c.confBonus2, c.confBonus3, c.confBonus4 = rv(0, 2), rv(0, 3), rv(0, 4)
        c.thrMedium, c.thrStrong, c.thrVStrong = rv(2, 6), rv(7, 11), rv(12, 16)
        major, minor = (100.0, rv(1, 4)), (50.0, rv(1, 3))
        mem = []
        for u in range(rnd.randint(1, 5)):
            x = 4190 + rnd.uniform(0, 20)
            cat = rnd.choice((pz.CAT_HZ, pz.CAT_ACC, pz.CAT_DHL, pz.CAT_MA))
            sid = {pz.CAT_HZ: "SWING_H", pz.CAT_ACC: "ACC_HI", pz.CAT_DHL: "DAY_HIGH", pz.CAT_MA: "MA1"}[cat]
            tf = {pz.CAT_HZ: rnd.choice(("5", "15", "60")), pz.CAT_ACC: rnd.choice(("60", "240", "D")), pz.CAT_DHL: "D", pz.CAT_MA: "1"}[cat]
            mem.append(raw(u, sid, cat, tf, x, rv(0, 5), c, slope=rv(0, 2) if cat == pz.CAT_MA else 0.0,
                           mcb=rv(0, 2) if cat == pz.CAT_MA else 0.0))
        zb, zt = min(m.bottom for m in mem), max(m.top for m in mem)
        flip = rnd.choice((0.0, rv(0, 3)))
        # force threshold boundaries: shift a member score so the OFF score hits a threshold exactly when possible
        off = finalize(mem, c, zb, zt, False, major, minor)
        on = finalize(mem, c, zb, zt, True, major, minor)
        s_off, st_off = apply_strength(off, c, flip)
        s_rs, st_rs = restore(on, c, flip)
        s_on, _ = apply_strength(on, c, flip)
        n += 1
        thr_cases += s_off in (c.thrMedium, c.thrStrong, c.thrVStrong)
        if s_rs == s_off and st_rs == st_off:
            exact += 1
        else:
            bad_exact.append((dec, s_off, s_rs))
        naive = s_on - on["rnScoreDelta"]
        naive_bad += naive != s_off
    # explicit threshold-boundary cases (0.1 steps, flip): the threshold is set to the exact RN-OFF score
    edge_ok, naive_flip = True, 0
    for parts, fl in (((2.7, 3.3, 1.0), 2.0), ((6.2, 1.8), 0.0), ((0.6, 0.2, 2.5), 0.0), ((4.9, 4.1), 0.3),
                      ((0.1, 0.2, 0.3), 0.7), ((1.1, 2.2, 3.3), 0.1)):
        c = Cfg()
        mem = [raw(i + 1, "PDH", pz.CAT_HZ, "PD", 4198 + i, p, c) for i, p in enumerate(parts)]   # each adds its base
        zb, zt = min(m.bottom for m in mem), max(m.top for m in mem)
        off = finalize(mem, c, zb, zt, False)
        so, _ = apply_strength(off, c, fl)
        c.thrMedium, c.thrStrong, c.thrVStrong = so - 1.0, so, so + 100.0
        so, sto = apply_strength(off, c, fl)
        on = finalize(mem, c, zb, zt, True)
        sr, str_ = restore(on, c, fl)
        edge_ok &= so == sr and sto == str_ == pz.SR_STRONG
        sn, _ = apply_strength(on, c, fl)
        naive_flip += pz.strength_of(sn - on["rnScoreDelta"], on["hasHtf"], c) != sto
    check("RX-01 RN-2 restoration rnBaseSumExRn + slope + ma + flip + conf(catCount - 1) == the RN-OFF score bit-for-bit "
          "and the same strength: 60000 random clusters (0.5 / 0.1 / 0.01 steps, random thresholds, confluence bonuses, "
          "RN points, flip on / off)", exact == n and not bad_exact, f"{exact}/{n} {bad_exact[:3]}")
    check("RX-02 threshold-boundary cases (0.1 steps, flip; Strong threshold == the exact RN-OFF score): restored strength "
          "is STRONG exactly like OFF (the naive route flips the strength in some of them)", edge_ok and naive_flip > 0,
          f"naive strength flips {naive_flip}/6")
    check("RX-03 documented: the naive route score - rnScoreDelta is NOT exact for non-dyadic inputs (why rnBaseSumExRn "
          "exists); restoration never uses it", naive_bad > 0, f"naive mismatches {naive_bad}/{n}")


# =============================================================================
# RT : Touch scenario (Touch function = old f_updateTouch, mirrored by practical_zone_sim.update_touch)
# =============================================================================
def gate_touch():
    c = Cfg()
    sw = raw(1, "SWING_H", pz.CAT_HZ, "60", 4206.0, 3.0, c)
    acc_out = raw(2, "ACC_HI", pz.CAT_ACC, "240", 4206.0, 4.0, c)        # zone 4203 - 4209: 4200 outside
    acc_in = raw(2, "ACC_HI", pz.CAT_ACC, "240", 4202.0, 4.0, c)         # zone 4199 - 4209: 4200 inside
    dh = raw(3, "DAY_HIGH", pz.CAT_DHL, "D", 4204.0, 3.0, c)
    # bar: (members, low, high) — price above the zone (top 4209, re-arm at low >= 4219)
    script = [([sw, acc_out], 4230, 4240),       # 0  no RN: MEDIUM
              ([sw, acc_in], 4230, 4240),        # 1  RN enters: STRONG starts (reset, wait for re-arm); far -> re-arm
              ([sw, acc_in], 4207, 4215),        # 2  touch -> 1
              ([sw, acc_in], 4225, 4235),        # 3  away -> re-arm
              ([sw, acc_out], 4206, 4215),       # 4  RN leaves: MEDIUM, touch not counted (count stays 1)
              ([sw, acc_in], 4205, 4215),        # 5  RN re-enters: new STRONG period -> reset 0, inside but not counted
              ([sw, acc_in], 4225, 4235),        # 6  away -> re-arm
              ([sw, acc_in], 4208, 4215),        # 7  touch -> 1
              ([sw, acc_in, dh], 4225, 4235),    # 8  + DayHL: VERY STRONG (with RN) - same Strong period; re-arm
              ([sw, acc_in, dh], 4208, 4215)]    # 9  touch -> 2 (no reset at STRONG -> VERY STRONG)
    out = {}
    for use_rn in (False, True):
        t = pz.Track(0, 0, wasStrong=False)
        t.state = pz.ST_SUPPORT
        rows = []
        for i, (mem, lo, hi) in enumerate(script):
            z = cl1(mem, c, use_rn)
            t.top, t.bottom = z["top"], z["bottom"]
            _, st = apply_strength(z, c, 0.0)
            cnt = pz.update_touch(t, st, hi, lo, i, c)
            rows.append((st, cnt, t.touchArmed))
        out[use_rn] = rows
    on, off = out[True], out[False]
    S, M, V = pz.SR_STRONG, pz.SR_MEDIUM, pz.SR_VSTRONG
    exp_on = [(M, 0, True), (S, 0, True), (S, 1, False), (S, 1, True), (M, 1, True), (S, 0, False), (S, 0, True),
              (S, 1, False), (V, 1, True), (V, 2, False)]
    check("RT-01 RN absent: MEDIUM (Swing 1H 3 + Accum 4H 4 + confluence 1 = 8)", on[0][0] == M and off[0][0] == M, str(on[0]))
    check("RT-02 RN 4200 enters the zone: STRONG (3 + 4 + 3 + confluence 2 = 12)", on[1][0] == S, str(on[1]))
    check("RT-03 Strong period start: Touch reset to 0, waits for re-arm, then counts (bar 2 -> 1)", on[1][1:] == (0, True)
          and on[2][1] == 1, str(on[1:3]))
    check("RT-04 RN leaves the zone (Accum moves, bottom 4203): back to MEDIUM, touches not counted", on[4][0] == M and on[4][1] == 1,
          str(on[4]))
    check("RT-05 RN re-enters: STRONG again", on[5][0] == S, str(on[5]))
    check("RT-06 re-entry starts a new Strong period: Touch reset to 0 (contact on that bar not counted)",
          on[5][1:] == (0, False), str(on[5]))
    check("RT-07 STRONG -> VERY STRONG (+ Day H/L, HTF from Swing 1H) keeps the Strong period: count goes 1 -> 2, no reset",
          on[8][0] == V and on[9][1] == 2, str(on[8:]))
    check("RT-08 full expected sequence with RN ON", on == exp_on, str(on))
    exp_off = []
    t = pz.Track(0, 0, wasStrong=False)
    t.state = pz.ST_SUPPORT
    for i, (mem, lo, hi) in enumerate(script):
        zb, zt = min(m.bottom for m in mem), max(m.top for m in mem)
        old = pz.practical_finalize(mem, c, zb, zt)                  # the old Engine finalize (no RN at all)
        t.top, t.bottom = zt, zb
        exp_off.append((old["strength"], pz.update_touch(t, old["strength"], hi, lo, i, c), t.touchArmed))
    check("RT-09 RN OFF: Touch sequence identical to the old Engine (old finalize, same Touch function)", off == exp_off,
          f"{off} vs {exp_off}")


# =============================================================================
# RY : time-series Engine model ON / OFF
# =============================================================================
def gate_series():
    import rn1_engine_model as em
    agg = dict(bars=0, geo=0, trk=0, ev=0, raw=0, fvg=0, ids=0, strength_changed=0, touch_changed=0, rn_zones=0,
               bad_rn=0, bad_restore=0, flips=0)
    for seed in (0, 1):
        b1, chart, htf = em.build(seed, 12)
        F = em.Feeds(b1, chart, htf, "nr")
        E0, E1 = em.Engine(), em.Engine()
        E1.rn_attach = True
        for i in range(len(chart)):
            f = F.feed(i, len(chart[i]["subs"]) - 1, "hist")
            E0.update(f, i)
            E1.update(f, i)
            agg["bars"] += 1
            g0 = [(z["top"], z["bottom"], tuple(z["uids"]), z["trackId"], z["state"], z["flipBonus"]) for z in E0.live]
            g1 = [(z["top"], z["bottom"], tuple(z["uids"]), z["trackId"], z["state"], z["flipBonus"]) for z in E1.live]
            agg["geo"] += g0 != g1
            tk = lambda E: [(t.id, t.state, t.breakDir, t.retested, t.flipped, t.lastSeenBar, tuple(t.memberUids)) for t in E.tracks]
            agg["trk"] += tk(E0) != tk(E1)
            agg["ev"] += E0.events != E1.events
            rw = lambda E: sorted((r.uid, r.srcId, r.srcTf, r.center, r.instId, r.expireTime) for r in E.persist)
            agg["raw"] += rw(E0) != rw(E1)
            fv = lambda E: [(s, E.fTop[s], E.fBot[s]) for s in range(15) if E.fAlive[s]]
            agg["fvg"] += fv(E0) != fv(E1)
            agg["ids"] += (E0.uid, E0.trackSeq) != (E1.uid, E1.trackSeq)
            agg["flips"] += sum(1 for z in E0.live if z["flipBonus"] > 0)
            for z0, z1 in zip(E0.live, E1.live):
                agg["strength_changed"] += z0["strength"] != z1["strength"]
                if z1["rnBase"] > 0:
                    agg["rn_zones"] += 1
                    agg["bad_rn"] += not (z1["bottom"] <= z1["rnLevel"] <= z1["top"]
                                          and z1["baseSum"] == z0["baseSum"] + z1["rnBase"]
                                          and z1["catCount"] == z0["catCount"] + 1 and z1["hasHtf"] == z0["hasHtf"]
                                          and z1["rnBaseSumExRn"] == z0["baseSum"])
                else:
                    agg["bad_rn"] += not (z1["score"] == z0["score"] and z1["strength"] == z0["strength"])
                ex = z1["rnBaseSumExRn"] + z1["slopeB"] + z1["maB"] + z1["flipBonus"] + em.conf(z1["catCount"] - (1 if z1["rnBase"] > 0 else 0))
                agg["bad_restore"] += not (ex == z0["score"] and em.pz.strength_of(ex, z1["hasHtf"], em.C) == z0["strength"])
            t0 = {t.id: t.touchCount for t in E0.tracks}
            agg["touch_changed"] += any(t.touchCount != t0.get(t.id) for t in E1.tracks)
    check("RY-01 time series (2 markets, ON vs OFF every bar): Raw Zones, zone top / bottom / members / track id / state / "
          "flip, Track id / state / break / retest / flip / last seen, events, FVG storage, uid / track sequences identical",
          agg["bars"] > 0 and all(agg[k] == 0 for k in ("geo", "trk", "ev", "raw", "fvg", "ids")), str(agg))
    check("RY-02 ON changes only the score side: zones with RN get base + rnBase, catCount + 1, same hasHtf, rnLevel inside "
          "[bottom, top]; zones without RN identical score / strength; strength and Touch do change somewhere",
          agg["rn_zones"] > 0 and agg["bad_rn"] == 0 and agg["strength_changed"] > 0 and agg["touch_changed"] > 0, str(agg))
    check("RY-03 RN-2 restoration on the time series (incl. flipped zones): RN-free score / strength == OFF exactly",
          agg["bad_restore"] == 0 and agg["flips"] > 0, str(agg))


def main():
    for g in (gate_static, gate_mirror, gate_restore, gate_touch, gate_series):
        try:
            g()
        except Exception:
            import traceback
            check(f"{g.__name__} completed without error", False, traceback.format_exc()[-500:])
    w = max(len(n) for n, _, _ in RESULTS)
    fails = 0
    for n, ok, d in RESULTS:
        fails += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {n.ljust(w)}  {'' if ok else d}")
    print(f"\n{len(RESULTS) - fails}/{len(RESULTS)} passed  [PINE_NOT_VERIFIED: exact transform / static / mirror / model]")
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
