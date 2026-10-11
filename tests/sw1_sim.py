"""SW-1 Gate SW-L1 fixtures — ZoneEnginePracticalSwingMax.pine (Swing max-score, plan B).

  WS : static — exact transform of the /5 source, /2 / /5 / Visual / Strategy untouched, only f_finalizeCluster's Swing
       branches change, helper semantics (no clamp)
  WM : port of f_finalizeCluster (member loop order) — A1..A10 scoring cases, negative / zero scores, ≤1 Swing timeframe
       bit-identical, other sources / confluence / HTF / srcMask / RN unchanged, RN-free score restoration
  WY : time-series Engine model, additive (/5) vs max (SW-1), RN OFF and ON — protections and the impact report

Evidence class: PINE_NOT_VERIFIED (exact transform / static / Python port / model; TradingView compile / publish external).
"""
import os
import random
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sw1_build as sb                # noqa: E402
import practical_zone_sim as pz       # noqa: E402
import fvg_re10045_sim as fr          # noqa: E402

ROOT = sb.ROOT
SW_TXT = open(os.path.join(ROOT, sb.SW_PATH), encoding="utf-8").read() if os.path.exists(os.path.join(ROOT, sb.SW_PATH)) else ""
BASE5 = sb.git_show(sb.SW_BASE_REV, sb.SRC_PATH)
RESULTS = []
REPORT = {}


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


def code_only(src):
    return "\n".join(l for l in src.split("\n") if not l.lstrip().startswith("//"))


def func(src, head):
    i = src.index(head)
    m = re.search(r"\n(?=\S)", src[i + len(head):])
    return src[i:i + len(head) + (m.start() + 1 if m else len(src))]


def heads(src):
    return re.findall(r"^((?:export )?(?:method )?\w+\()", src, re.M)


# =============================================================================
# WS : static
# =============================================================================
def gate_static():
    check("WS-01 ZoneEnginePracticalSwingMax.pine == sw_transform(ZoneEnginePracticalRN.pine @ 3c29718) exactly (6 edits)",
          bool(SW_TXT) and sb.sw_transform(BASE5) == SW_TXT)
    check("WS-02 strip_sw(SwingMax) == the /5 source byte-for-byte", sb.strip_sw(SW_TXT) == BASE5)
    names = ["ZoneEnginePractical.pine", "ZoneEnginePracticalRN.pine", "ZoneVisualPractical.pine", "ZoneEnginePracticalAuthority.pine",
             "ZoneEngine.pine", "SignalEnginePractical.pine", "SignalEngine.pine", "PracticalZoneStrategy_LONG.pine",
             "PracticalZoneStrategy_SHORT.pine", "FvgZoneStrategy.pine", "PracticalZoneFeedHarness.pine",
             "PracticalAlertHarness.pine", "PracticalTradeHarness.pine", "PracticalBreakEvenHarness.pine",
             "PracticalEntryDispatchHarness.pine"]
    d = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", sb.SW_BASE_REV, "--"] + names, capture_output=True, text=True).stdout
    check("WS-03 /2 and /5 Engine sources, Visual, Strategy, SignalEngine, Harness unchanged vs 3c29718", d.strip() == "", d)
    check("WS-04 same library name (next version of ZoneEnginePractical)",
          re.findall(r'^library\("([^"]+)"', SW_TXT, re.M) == ["ZoneEnginePractical"])
    h5, hs = heads(BASE5), heads(SW_TXT)
    other = [h for h in h5 if h != "f_finalizeCluster("]
    diff = [h for h in other if func(SW_TXT, h) != func(BASE5, h)]
    check("WS-05 every function except f_finalizeCluster byte-identical to /5 (pivot detection, NR-related packs, Raw Zone "
          "registration / life, clustering, Track, Touch, Break / Flip, strength, RN picker, SL / TP API); only "
          "f_swingMaxStep added", diff == [] and [h for h in hs if h not in h5] == ["f_swingMaxStep("], str(diff))
    f5, fs = func(BASE5, "f_finalizeCluster("), func(SW_TXT, "f_finalizeCluster(")
    keep = lambda t: [l for l in t.split("\n") if re.search(r"srcM|htfM|\bcat\b|confB|hasHZ|hasMA|hasDHL|hasACC|rnB|rnLv|rnD|"
                                                             r"baseSumEx|Zone\.new|uids|accHi|accLo|slopeB|maB|isSwing|isAccHi", l)]
    check("WS-06 inside f_finalizeCluster only the three Swing score additions change: srcMask / HTF bits, category flags, "
          "confluence, Accum / other / MA / Day H/L scoring, RN block and Zone.new lines identical to /5",
          keep(fs) == keep(f5) and fs.count("baseSum += m.baseScore") == f5.count("baseSum += m.baseScore")
          and all(f"baseSum += c.scoreHz{n}" not in fs for n in (1, 2, 3)) and fs.count("f_swingMaxStep(swMax, c.scoreHz") == 3)
    back = fs
    for old, new in sb.SW_EDITS[2:]:
        back = back.replace(new, old)
    check("WS-06b f_finalizeCluster with the Swing max edits reverted == /5 f_finalizeCluster byte-for-byte (no other line "
          "of the function changed: Accum / other / MA / Day H/L scoring, geometry, RN, Zone.new)", back == f5)
    tb = lambda t: {m.group(1): m.group(0) for m in re.finditer(r"^export type (\w+)\n(?:.*\n)*?\n", t, re.M)}
    consts = lambda t: re.findall(r"^(?:int|float|string|bool) \w+\s*=.*$", t, re.M)
    check("WS-08 every exported type (ZoneCfg defaults incl. Swing / RN points, Zone / RN fields, Track) and every global "
          "constant byte-identical to /5", tb(SW_TXT) == tb(BASE5) and len(tb(SW_TXT)) >= 7 and consts(SW_TXT) == consts(BASE5))
    hp = func(SW_TXT, "f_swingMaxStep(")
    check("WS-07 f_swingMaxStep: first Swing adds its score unchanged, later ones only the rise of the maximum; no clamp to 0",
          "    float add = na(swMax) ? s : s > swMax ? s - swMax : 0.0\n" in hp
          and "    float mx  = na(swMax) ? s : math.max(swMax, s)\n" in hp and not re.search(r"math\.max\([^)]*0\.0\)|math\.max\(0", hp)
          and fr.lint_eager_guards(code_only(hp + fs)) == [])


# =============================================================================
# WM : port of f_finalizeCluster
# =============================================================================
class Cfg(pz.Cfg):
    zoneHalfWidth = 3.0
    clusterDist = 5.0


def conf(c, n):
    return c.confBonus4 if n >= 4 else c.confBonus3 if n == 3 else c.confBonus2 if n == 2 else 0.0


def swing_step(swMax, s):
    add = s if swMax is None else (s - swMax if s > swMax else 0.0)
    mx = s if swMax is None else max(swMax, s)
    return add, mx


def rn_level_in(zBot, zTop, step):
    import math
    k1, k2 = math.ceil(zBot / step), math.floor(zTop / step)
    if k1 > k2:
        return None
    ctr = (zTop + zBot) / 2
    kc = max(k1, min(k2, math.floor(ctr / step)))
    lv = kc * step
    if kc + 1 <= k2 and (kc + 1) * step - ctr < ctr - lv:
        lv = (kc + 1) * step
    return float(lv)


def finalize(members, c, zBot, zTop, use_rn=False, swing_max=True):
    """line-by-line port of f_finalizeCluster (member loop order); swing_max=False = the /5 additive version."""
    baseSum = slopeB = maB = 0.0
    has = dict(MA=False, HZ=False, DHL=False, ACC=False)
    swHit, swMax, accHit, srcM, htfM = [False] * 3, None, set(), set(), set()
    for m in members:
        isSwing = m.srcCat == pz.CAT_HZ and m.srcId in ("SWING_H", "SWING_L")
        isAccHi = m.srcId == "ACC_HI"
        if isSwing:
            for i, (tf, sc) in enumerate(((c.hzTf1, c.scoreHz1), (c.hzTf2, c.scoreHz2), (c.hzTf3, c.scoreHz3))):
                if m.srcTf == tf:
                    srcM.add(f"SW{i + 1}")
                    if not swHit[i]:
                        swHit[i] = True
                        if swing_max:
                            a, swMax = swing_step(swMax, sc)
                            baseSum += a
                        else:
                            baseSum += sc
                    break
            else:
                srcM.add("HZX")
                baseSum += m.baseScore
        elif m.srcCat == pz.CAT_ACC:
            slot = 1 if m.srcTf == c.accTf1 else 2 if m.srcTf == c.accTf2 else 3 if m.srcTf == c.accTf3 else 0
            if slot == 0:
                baseSum += m.baseScore
            else:
                srcM.add(f"ACC{slot}")
                k = ("hi" if isAccHi else "lo", slot)
                if k not in accHit:
                    accHit.add(k)
                    baseSum += m.baseScore
        else:
            baseSum += m.baseScore
            srcM.add(m.srcId if m.srcId in ("MA1", "MA2") else ("DHL" if m.srcCat == pz.CAT_DHL else "HZX"))
        slopeB = max(slopeB, m.slopeBonus) if c.slopeBonusMax else slopeB + m.slopeBonus
        maB = max(maB, m.maClusterBonus)
        if isSwing and m.srcTf == c.hzTf3 and c.htfSwing1H: htfM.add("SW1H")
        if isSwing and m.srcTf == c.hzTf2 and c.htfSwing15M: htfM.add("SW15")
        if m.srcCat == pz.CAT_ACC and m.srcTf == c.accTf1 and c.htfAccum1H: htfM.add("ACC1")
        if m.srcCat == pz.CAT_ACC and m.srcTf == c.accTf2 and c.htfAccum4H: htfM.add("ACC2")
        if m.srcCat == pz.CAT_ACC and m.srcTf == c.accTf3 and c.htfAccumD: htfM.add("ACC3")
        if m.srcId == "MA1" and c.htfMa1: htfM.add("MA1")
        if m.srcId == "MA2" and c.htfMa2: htfM.add("MA2")
        if m.srcCat == pz.CAT_DHL and c.htfDayHL: htfM.add("DAY")
        has["MA"] |= m.srcCat == pz.CAT_MA
        has["HZ"] |= m.srcCat == pz.CAT_HZ
        has["DHL"] |= m.srcCat == pz.CAT_DHL
        has["ACC"] |= m.srcCat == pz.CAT_ACC
    baseSumEx, rnLv, rnB = baseSum, None, 0.0
    if use_rn:
        for step, sc in ((100.0, 3.0), (50.0, 2.0)):
            lv = rn_level_in(zBot, zTop, step)
            if lv is not None:
                rnLv, rnB = lv, sc
                break
    if rnB > 0:
        baseSum += rnB
        srcM.add("RN")
    cat = sum(has.values()) + (1 if rnB > 0 else 0)
    confB = conf(c, cat)
    return dict(baseSum=baseSum, slopeB=slopeB, maB=maB, confB=confB, catCount=cat, hasHtf=bool(htfM), srcM=frozenset(srcM),
                htfM=frozenset(htfM), rnLevel=rnLv, rnBase=rnB, rnBaseSumExRn=baseSumEx,
                score=baseSum + slopeB + maB + confB, swingTfs=sum(swHit))


def apply_strength(z, c, flip=0.0):
    s = z["baseSum"] + z["slopeB"] + z["maB"] + flip + z["confB"]
    return s, pz.strength_of(s, z["hasHtf"], c)


def gate_mirror():
    c = Cfg()
    raw = lambda u, sid, cat, tf, x, bs: pz.Raw(u, sid, cat, tf, x, bs, c)
    sw = lambda u, tf, x=4205.0: raw(u, "SWING_H" if u % 2 else "SWING_L", pz.CAT_HZ, tf, x, {"5": 1.0, "15": 2.0, "60": 3.0}.get(tf, 1.0))
    acc = lambda u, x=4206.0: raw(u, "ACC_HI", pz.CAT_ACC, "240", x, 4.0)
    # sanity: the port with swing_max=False reproduces the old score_parts (additive) on random clusters
    rnd, ok_port = random.Random(5), True
    for _ in range(2000):
        mem = []
        for u in range(rnd.randint(1, 6)):
            kind = rnd.choice(("sw", "acc", "dhl", "ma"))
            x = 4190 + rnd.uniform(0, 20)
            mem.append({"sw": lambda: sw(u, rnd.choice(("5", "15", "60")), x),
                        "acc": lambda: raw(u, rnd.choice(("ACC_HI", "ACC_LO")), pz.CAT_ACC, rnd.choice(("60", "240", "D")), x, 3.0),
                        "dhl": lambda: raw(u, "DAY_HIGH", pz.CAT_DHL, "D", x, 3.0),
                        "ma": lambda: pz.Raw(u, "MA1", pz.CAT_MA, "1", x, 2.0, c, slopeBonus=1.0, maClusterBonus=1.0)}[kind]())
        old = pz.score_parts(mem, c)
        p = finalize(mem, c, 0, 0, False, False)
        ok_port &= (p["baseSum"], p["slopeB"], p["maB"], p["confB"], p["hasHtf"]) == (old[0], old[1], old[2], old[4], old[5])
    check("WM-00 the port with additive Swing (= /5) reproduces the existing Engine mirror (score_parts) on 2000 clusters",
          ok_port)
    cases = [("A1 no Swing (Accum 4H only)", [acc(9)], 4.0, 4.0, 0),
             ("A2 5M only", [sw(1, "5")], 1.0, 1.0, 1), ("A3 15M only", [sw(1, "15")], 2.0, 2.0, 1),
             ("A4 1H only", [sw(1, "60")], 3.0, 3.0, 1),
             ("A5 5M + 15M", [sw(1, "5"), sw(2, "15")], 2.0, 3.0, 2), ("A6 5M + 1H", [sw(1, "5"), sw(2, "60")], 3.0, 4.0, 2),
             ("A7 15M + 1H", [sw(1, "15"), sw(2, "60")], 3.0, 5.0, 2),
             ("A8 5M + 15M + 1H", [sw(1, "5"), sw(2, "15"), sw(3, "60")], 3.0, 6.0, 3),
             ("A8b 1H + 15M + 5M (order)", [sw(3, "60"), sw(2, "15"), sw(1, "5")], 3.0, 6.0, 3),
             ("A9 same TF twice (two 15M)", [sw(1, "15"), sw(2, "15")], 2.0, 2.0, 1),
             ("A9b 5M + 15M + 1H + Accum 4H", [sw(1, "5"), acc(9), sw(2, "15"), sw(3, "60")], 7.0, 10.0, 3)]
    rows = []
    for name, mem, exp_new, exp_old, ntf in cases:
        n, o = finalize(mem, c, 4200, 4210), finalize(mem, c, 4200, 4210, swing_max=False)
        rows.append((name, n["baseSum"], o["baseSum"]))
        ok = n["baseSum"] == exp_new and o["baseSum"] == exp_old and n["swingTfs"] == ntf \
            and (n["catCount"], n["hasHtf"], n["srcM"], n["htfM"]) == (o["catCount"], o["hasHtf"], o["srcM"], o["htfM"])
        check(f"WM-{name}: Swing contributes {exp_new:g} (additive {exp_old:g}); confluence category / HTF / srcMask bits "
              "unchanged", ok, str(rows[-1]))
    # A10 non-default scores (max by configured score, not by timeframe), ties, zero / negative (no clamp)
    nd = [((5.0, 2.0, 3.0), ["5", "15", "60"], 5.0, 10.0), ((2.0, 2.0, 1.0), ["5", "15"], 2.0, 4.0),
          ((-1.0, 2.0, 3.0), ["5"], -1.0, -1.0), ((-1.0, 2.0, 3.0), ["5", "15"], 2.0, 1.0),
          ((0.0, -2.0, 3.0), ["5", "15"], 0.0, -2.0), ((-3.0, -1.0, -2.0), ["5", "15", "60"], -1.0, -6.0),
          ((0.0, 0.0, 0.0), ["5", "15", "60"], 0.0, 0.0), ((1.5, 0.7, 2.3), ["15", "5"], 1.5, 2.2)]
    res = []
    for (s1, s2, s3), tfs, exp_new, exp_old in nd:
        c2 = Cfg()
        c2.scoreHz1, c2.scoreHz2, c2.scoreHz3 = s1, s2, s3
        mem = [pz.Raw(i + 1, "SWING_H", pz.CAT_HZ, tf, 4205.0, 1.0, c2) for i, tf in enumerate(tfs)]
        n, o = finalize(mem, c2, 4200, 4210), finalize(mem, c2, 4200, 4210, swing_max=False)
        res.append(((s1, s2, s3), tfs, n["baseSum"], o["baseSum"]))
        if not (abs(n["baseSum"] - exp_new) < 1e-12 and abs(o["baseSum"] - exp_old) < 1e-12):
            break
    check("WM-A10 non-default scores: maximum of the configured scores present (5M = 5 beats 1H = 3), equal maxima counted "
          "once, zero / negative not clamped (only -1 -> -1; -1 & 2 -> 2; 0 & -2 -> 0; all negative -> the largest)",
          len(res) == len(nd) and all(abs(r[2] - e[2]) < 1e-12 and abs(r[3] - e[3]) < 1e-12 for r, e in zip(res, nd)), str(res))
    # ≤1 Swing timeframe: bit-identical to /5, random 0.1-step scores; ≥2: new <= old with defaults
    rnd, ok_same, ok_le, n1, n2 = random.Random(9), True, True, 0, 0
    for _ in range(20000):
        c3 = Cfg()
        q = lambda: round(rnd.randint(0, 50) * 0.1, 1)
        c3.scoreHz1, c3.scoreHz2, c3.scoreHz3 = q(), q(), q()
        mem = []
        for u in range(rnd.randint(1, 6)):
            kind = rnd.choice(("sw", "acc", "dhl"))
            x = 4190 + rnd.uniform(0, 20)
            if kind == "sw":
                mem.append(pz.Raw(u, "SWING_H", pz.CAT_HZ, rnd.choice(("5", "15", "60")), x, 1.0, c3))
            elif kind == "acc":
                mem.append(pz.Raw(u, rnd.choice(("ACC_HI", "ACC_LO")), pz.CAT_ACC, rnd.choice(("60", "240", "D")), x, q(), c3))
            else:
                mem.append(pz.Raw(u, "DAY_HIGH", pz.CAT_DHL, "D", x, q(), c3))
        for rn in (False, True):
            n, o = finalize(mem, c3, 4198, 4203, rn), finalize(mem, c3, 4198, 4203, rn, False)
            if n["swingTfs"] <= 1:
                n1 += 1
                ok_same &= n == o
            else:
                n2 += 1
                ok_le &= n["baseSum"] <= o["baseSum"] + 1e-9 and (n["catCount"], n["hasHtf"], n["srcM"], n["rnBase"]) == \
                    (o["catCount"], o["hasHtf"], o["srcM"], o["rnBase"])
    check("WM-11 clusters with at most one Swing timeframe: every field bit-identical to /5 (20000 random clusters, 0.1-step "
          "scores, RN off / on)", ok_same and n1 > 0, f"{n1} clusters")
    check("WM-12 clusters with 2+ Swing timeframes (non-negative scores): baseSum never above /5; confluence / HTF / srcMask "
          "/ RN unchanged", ok_le and n2 > 0, f"{n2} clusters")
    # RN interplay and restoration
    mem = [sw(1, "5", 4199.0), sw(2, "15", 4201.0), sw(3, "60", 4200.0)]
    n_on, n_off = finalize(mem, c, 4196, 4204, True), finalize(mem, c, 4196, 4204, False)
    o_on = finalize(mem, c, 4196, 4204, True, False)
    check("WM-13 RN with Swing max: Swing 3 + RN 3 = 6 (additive /5: 6 + 3 = 9); rnBase / rnLevel / category unchanged; "
          "rnBaseSumExRn = the Swing-max pre-RN baseSum (3)",
          n_on["baseSum"] == 6.0 and o_on["baseSum"] == 9.0 and n_on["rnBase"] == o_on["rnBase"] == 3.0
          and n_on["rnLevel"] == o_on["rnLevel"] == 4200.0 and n_on["catCount"] == o_on["catCount"] == 2
          and n_on["rnBaseSumExRn"] == n_off["baseSum"] == 3.0)
    rnd, ok_rs, cnt = random.Random(13), True, 0
    for _ in range(30000):
        c4 = Cfg()
        q = lambda: round(rnd.randint(0, 40) * rnd.choice((0.1, 0.5, 0.01)), 2)
        c4.scoreHz1, c4.scoreHz2, c4.scoreHz3 = q(), q(), q()
        c4.confBonus2, c4.confBonus3, c4.confBonus4 = q(), q(), q()
        mem = [pz.Raw(u, "SWING_H", pz.CAT_HZ, rnd.choice(("5", "15", "60")), 4195 + rnd.uniform(0, 10), 1.0, c4)
               for u in range(rnd.randint(1, 4))]
        if rnd.random() < .5:
            mem.append(pz.Raw(9, "ACC_HI", pz.CAT_ACC, "240", 4200, q(), c4))
        fl = rnd.choice((0.0, q()))
        on, off = finalize(mem, c4, 4196, 4204, True), finalize(mem, c4, 4196, 4204, False)
        so, sto = apply_strength(off, c4, fl)
        ex = on["rnBaseSumExRn"] + on["slopeB"] + on["maB"] + fl + conf(c4, on["catCount"] - (1 if on["rnBase"] > 0 else 0))
        ok_rs &= ex == so and pz.strength_of(ex, on["hasHtf"], c4) == sto
        cnt += 1
    check("WM-14 RN-free score restoration with Swing max (30000 random, 0.5 / 0.1 / 0.01 steps, flip): bit-identical score "
          "and strength", ok_rs, f"{cnt}")


# =============================================================================
# WY : time-series model, additive (/5) vs max (SW-1), RN OFF and ON
# =============================================================================
def gate_series():
    import rn1_engine_model as em
    import zp_overlap_sim as zs
    rep = dict(bars=0, zones=0, multi=0, drop_sum=0.0, drop_max=0.0, geo=0, trk=0, ev=0, raw=0, fvg=0, keep=0, bad_restore=0,
               touch_bars=0, boost_changes=0, snaps=0)
    trans = {}
    for rn in (False, True):
        for seed in (0, 1):
            b1, chart, htf = em.build(seed, 12)
            F = em.Feeds(b1, chart, htf, "nr")
            A, B = em.Engine(), em.Engine()
            A.rn_attach = B.rn_attach = rn
            B.swing_max = True
            for i in range(len(chart)):
                f = F.feed(i, len(chart[i]["subs"]) - 1, "hist")
                A.update(f, i)
                B.update(f, i)
                rep["bars"] += 1
                g = lambda E: [(z["top"], z["bottom"], tuple(z["uids"]), z["trackId"], z["state"], z["flipBonus"]) for z in E.live]
                rep["geo"] += g(A) != g(B)
                tk = lambda E: [(t.id, t.state, t.breakDir, t.retested, t.flipped, t.lastSeenBar, tuple(t.memberUids)) for t in E.tracks]
                rep["trk"] += tk(A) != tk(B)
                rep["ev"] += A.events != B.events
                rw = lambda E: sorted((r.uid, r.srcId, r.srcTf, r.center, r.instId, r.expireTime) for r in E.persist)
                rep["raw"] += rw(A) != rw(B)
                fv = lambda E: [(s, E.fTop[s], E.fBot[s]) for s in range(15) if E.fAlive[s]]
                rep["fvg"] += fv(A) != fv(B)
                for za, zb in zip(A.live, B.live):
                    rep["zones"] += 1
                    rep["keep"] += (za["catCount"], za["hasHtf"], za["rnBase"], za["rnLevel"]) != \
                        (zb["catCount"], zb["hasHtf"], zb["rnBase"], zb["rnLevel"])
                    if zb["swingTfs"] >= 2:
                        rep["multi"] += 1
                        d = za["score"] - zb["score"]
                        rep["drop_sum"] += d
                        rep["drop_max"] = max(rep["drop_max"], d)
                    elif za["score"] != zb["score"]:
                        rep["keep"] += 1
                    key = (rn, za["strength"], zb["strength"])
                    if za["strength"] != zb["strength"]:
                        trans[key] = trans.get(key, 0) + 1
                    ex = zb["rnBaseSumExRn"] + zb["slopeB"] + zb["maB"] + zb["flipBonus"] + em.conf(zb["catCount"] - (1 if zb["rnBase"] > 0 else 0))
                    base_score = zb["score"] - (zb["rnScoreDelta"] if zb["rnBase"] > 0 else 0.0)
                    rep["bad_restore"] += abs(ex - base_score) > 1e-9
                ta = {t.id: t.touchCount for t in A.tracks}
                rep["touch_bars"] += any(t.touchCount != ta.get(t.id) for t in B.tracks)
                if i % 40 == 39:
                    rep["snaps"] += 1
                    cfg = zs.Cfg()

                    def dr(E):
                        zones = [dict(top=z["top"], bottom=z["bottom"], baseSum=z["baseSum"], catCount=z["catCount"],
                                      hasHtf=z["hasHtf"], state=z["state"], touch=z["touch"], slopeBonus=z["slopeB"],
                                      maBonus=z["maB"], flipBonus=z["flipBonus"], score=z["score"], strength=z["strength"])
                                 for z in E.live]
                        S = zs.Slots([zs.fvg(s, E.fTop[s], E.fBot[s], E.fClose[s], True) for s in range(15) if E.fAlive[s]])
                        return [x for x in zs.draw_new(cfg, zones, S)[0] if x[1] == "boost"]
                    rep["boost_changes"] += dr(A) != dr(B)
    REPORT.update(rep)
    REPORT["strength_transitions"] = trans
    check("WY-01 additive vs max on the same series (RN OFF and ON, 2 markets each): Raw Zones, zone geometry / members / "
          "track id / state / flip, Track id / state / break / retest / flip, events, FVG storage identical every bar",
          rep["bars"] > 0 and all(rep[k] == 0 for k in ("geo", "trk", "ev", "raw", "fvg")), str(rep))
    check("WY-02 only clusters with 2+ Swing timeframes change score; confluence category count, HTF, RN level / points "
          "identical everywhere", rep["keep"] == 0 and rep["multi"] > 0, str(rep))
    check("WY-03 RN-free score restoration with Swing max holds on the time series (RN ON)", rep["bad_restore"] == 0, str(rep))


def main():
    for g in (gate_static, gate_mirror, gate_series):
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
    if REPORT:
        r = REPORT
        print(f"\nREPORT  zones {r['zones']}, with 2+ Swing TFs {r['multi']}, score drop mean "
              f"{(r['drop_sum'] / r['multi']) if r['multi'] else 0:.3f} max {r['drop_max']:g}, Touch-changed bars {r['touch_bars']}, "
              f"FVG boost display changed {r['boost_changes']}/{r['snaps']} snapshots")
        print(f"REPORT  strength (rnOn, additive -> max): {dict(sorted(r['strength_transitions'].items()))}")
    print(f"\n{len(RESULTS) - fails}/{len(RESULTS)} passed  [PINE_NOT_VERIFIED: exact transform / static / port / model]")
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
