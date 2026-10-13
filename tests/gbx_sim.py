"""GBJ-2 / GBS-3 fixtures — FVG Direction Match and GBPJPY Round Number in ZoneVisualGBPJPY / ZoneStrategyGBPJPY.

  GX : static — both files rebuilt from the generators; reverting the GBJ-2 edits gives the previous files (65b1fb3)
       byte for byte (both features OFF = the old code paths); defaults OFF / 1.00 円 +3 / 0.50 円 +2; the direction
       filter sits in the candidate condition of every FVG selection (before the best-of choice), byte-identical in the
       Visual and the Strategy; FVG storage / lifetime / fill / width / points / Confluence / boost range / candidate
       condition unchanged; RN uses the existing Engine /6 RN (config only: steps, scores, GBPJPY gate, step check);
       requests, zone loops, FVG slots, drawing and string building unchanged; Engines / XAU / USDJPY files unchanged
  GM : models — Pine mirrors of the FVG selection (direction-first) and of the Engine RN (f_rnLevelIn / f_finalizeCluster
       RN part): direction cases, same-direction fallback, no candidate, other states, boost range, base-Strong
       eligibility; RN integer / half yen / outside / boundary / both levels -> major only / OFF / changed inputs /
       Confluence; float exactness of the RN formula for the allowed steps and the step validation
  GU : mutations — mirror and source mutations are caught

Evidence class: PINE_NOT_VERIFIED (TradingView compile / runtime / display / Strategy Tester external).
"""
import math
import os
import re
import subprocess
import sys
from decimal import Decimal as Dec

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gbj_build as gb          # noqa: E402
import gbs_build as gs          # noqa: E402
import st1_build as tb          # noqa: E402
import fvg_re10045_sim as fr    # noqa: E402

ROOT = gb.ROOT
BASE = "65b1fb3"
rd = lambda p: open(os.path.join(ROOT, p), encoding="utf-8").read() if os.path.exists(os.path.join(ROOT, p)) else ""
show = lambda p, rev=BASE: subprocess.run(["git", "-C", ROOT, "show", f"{rev}:{p}"], capture_output=True, text=True).stdout
GBV, GBS = rd(gb.GBJ_PATH), rd(gs.GBS_PATH)
GBV0, GBS0 = show(gb.GBJ_PATH), show(gs.GBS_PATH)
ENGINE = rd("ZoneEnginePracticalSwingMax.pine")
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


def code_only(src):
    return "\n".join(l for l in src.split("\n") if not l.lstrip().startswith("//"))


def inputs(src):
    return dict(re.findall(r"^(\w+)\s*=\s*input\.\w+\(([^,]+),", src, re.M))


GBS3_PREV = [   # the GBS-2 (65b1fb3) texts the GBJ-3 base setting replaced in the Strategy
    (gs.HEADER_GBS,
     "//  Zone Strategy GBPJPY  —  ZONE-GBPJPY (ZoneVisualGBPJPY) の Zone 判定をそのまま使う OANDA:GBPJPY 5分足 Strategy\n"
     "//  (生成: tests/gbs_build.py。Zone 計算は ZONE-GBPJPY、注文処理・仮 / 確定アラートは ZONE-ST-JPY\n"
     "//   (ZoneStrategyUSDJPY) と同じ式。価格差は円。初期値は GBPJPY 基準設定 (ある比較期間の TradingView 結果から\n"
     "//   決めたもの。最適値・別期間での有効性は未確認)。Zone Half Width は 0.05 (表示用 ZONE-GBPJPY の初期 0.03\n"
     "//   とは異なる: 表示と照合するときは Visual 側を 0.05 に合わせる)\n"),
    ("(= 3 / 5 / 8 pips)。初期 0.05 = GBPJPY 基準設定 (Visual / Strategy 共通)。\")\n",
     "(= 3 / 5 / 8 pips)。Strategy 初期 0.05 = GBPJPY 基準設定 (表示用 ZONE-GBPJPY は 0.03)。\")\n"),
] + [(b, a) for k, a, b in gb.EDITS3 if k == "default" and not a.startswith("zoneHalfWidth") and "初期 0.03" not in a]


def revert_in_strategy(text):
    out = text
    for kind, a, b in reversed(gb.EDITS4):     # GBJ-4 (Accum Score Mode, GBPJPY Engine import): pinned in gbe_sim
        if kind != "header":
            out = out.replace(b, a) if out is not None and out.count(b) == 1 else None
    for b, a in GBS3_PREV:
        out = out.replace(b, a) if out is not None and out.count(b) == 1 else None
    for kind, a, b in reversed(gb.EDITS2):
        if kind != "header" and "fd   = array.get(gFvgDir, slot)" not in b:
            out = out.replace(b, a) if out is not None and out.count(b) == 1 else None
    return out


NEW_INPUTS = {"fvgDirMatch": "false", "enableRn": "false", "rnMajorStep": "1.0", "rnMajorScore": "3.0",
              "rnMinorStep": "0.5", "rnMinorScore": "2.0"}
PROTECTED = ["ZoneVisualUSDJPY.pine", "ZoneStrategyUSDJPY.pine", "ZoneVisualPractical.pine", "ZoneStrategyXAU.pine",
             "ZoneEnginePractical.pine", "ZoneEnginePracticalRN.pine", "ZoneEnginePracticalSwingMax.pine",
             "ZoneEnginePracticalAuthority.pine", "PracticalZoneStrategy_LONG.pine", "PracticalZoneStrategy_SHORT.pine",
             "SignalEnginePractical.pine"]


def gate_static():
    check("GX-01 Visual == gbj_build.build(), Strategy == gbs_build.build() (rebuilds identical); reverting the GBJ-2 edits "
          "gives the previous Visual and Strategy (" + BASE + ") byte for byte: with both features OFF only the listed "
          "edits differ (GBJ-3 base-setting defaults reverted as well: they are pinned by gbs_sim GB-06 / GB-10)",
          gb.build() == GBV and gs.build() == GBS and gb.strip_gbj2(GBV) == GBV0 and bool(GBV0)
          and revert_in_strategy(GBS) == GBS0 and bool(GBS0))
    gbj3 = {"scoreDayHL", "slopeThrMod", "slopeThrStrong", "thrStrong", "zoneHalfWidth",   # GBJ-3 (gbs_sim GB-06 / GB-10)
            "accScoreMode"}                                                                  # GBJ-4 (gbe_sim)
    vv = {k: v for k, v in inputs(GBV).items() if k not in gbj3}
    vs = {k: v for k, v in inputs(GBS).items() if k not in gbj3}
    v0 = {k: v for k, v in inputs(GBV0).items() if k not in gbj3}
    s0 = {k: v for k, v in inputs(GBS0).items() if k not in gbj3}
    check("GX-02 new inputs and defaults, same in Visual and Strategy: FVG Direction Match OFF, RN OFF, major 1.00 円 / +3, "
          "minor 0.50 円 / +2 (all changeable inputs); every other input value unchanged from " + BASE + " (GBJ-3 "
          "base-setting defaults aside)",
          all(vv.get(k) == v and vs.get(k) == v for k, v in NEW_INPUTS.items())
          and {k: v for k, v in vv.items() if k not in NEW_INPUTS or k == "enableRn"} == v0
          and {k: v for k, v in vs.items() if k not in NEW_INPUTS or k == "enableRn"} == s0,
          str((set(vv) ^ set(v0), vs.get("enableRn"))))
    sel = gb.SEL_NEW
    fz = lambda s: tb.func(s, "f_fvcZoneDisplay(").rstrip()      # trailing blank lines differ by layout only
    fb = lambda s: tb.func(s, "f_zpoBestFvg(").rstrip()
    ok_pos = all(f.count(sel) == 1 and f.index("want == 0 or array.get(gFvgDir, s) == want") < f.index("if best < 0")
                 for f in (fz(GBV), fb(GBV)))
    check("GX-03 direction filter in the candidate condition (before overlap and best-of comparison) of f_fvcZoneDisplay "
          "and f_zpoBestFvg; both functions byte-identical in Visual and Strategy; Visual FVG box display uses the same "
          "rule; want = 0 when OFF or the state is neither SUPPORT nor RESIST",
          ok_pos and fz(GBV) == fz(GBS) and fb(GBV) == fb(GBS)
          and "int want = fvgDirMatch ? (z.state == ST_SUPPORT ? 1 : z.state == ST_RESIST ? -1 : 0) : 0" in sel
          and "(not fvgDirMatch or ((z.state != ST_SUPPORT or fd == 1) and (z.state != ST_RESIST or fd == -1)))" in GBV)
    same = []
    for h in ("f_fvgConfirmed(", "f_fvgExpire(", "f_fvgOnEvent(", "f_fvcConf(", "f_fvcStrengthOf(", "f_fvcBase(",
              "f_fvcOverlap(", "f_stZoneEval("):
        for new, old in ((GBV, GBV0), (GBS, GBS0)):
            if h in old:
                same.append((h, tb.func(new, h) == tb.func(old, h)))
    dline = "        dScore := z.baseSum + f_fvcBase(best) + z.slopeBonus + z.maBonus + z.flipBonus + f_fvcConf(z.catCount + 1)\n"
    cand = "            if zSide != 0 and (z.strength >= SR_STRONG or (eBoost and eStr >= SR_STRONG))\n"
    slots = lambda s: re.findall(r"^var array<\w+>\s+gFvg\w+\s*=.*$", s, re.M)
    check("GX-04 FVG storage / lifetime / fill / width (f_fvgConfirmed / Expire / OnEvent, 5 slots per TF), points "
          "(f_fvcBase), Confluence, Strength, boost range (f_stZoneEval) and the candidate rule (base Strong stays "
          "eligible whatever the FVG direction) unchanged",
          all(o for _, o in same) and len(same) >= 14 and GBV.count(dline) == GBS.count(dline) == 1
          and GBS.count(cand) == 1 and GBS0.count(cand) == 1 and slots(GBV) == slots(GBV0) and slots(GBS) == slots(GBS0)
          and "int    FVG_SLOTS_PER_TF = 5" in GBS, str([x for x in same if not x[1]]))
    cfg = lambda s: re.findall(r"^zoneCfg\.(rn\w+|useRnSource)\s*:=\s*(.*)$", s, re.M)
    rn_cfg = [("rnStepMajor", "rnMajorStep"), ("rnScoreMajor", "rnMajorScore"), ("rnStepMinor", "rnMinorStep"),
              ("rnScoreMinor", "rnMinorScore"), ("useRnSource", 'enableRn and rnStepOK and syminfo.ticker == "GBPJPY"')]
    ticks = lambda s: re.findall(r"syminfo\.ticker\s*==\s*\"(\w+)\"", code_only(s))
    errs = lambda s: re.findall(r"^(.*)\n\s+runtime\.error\(", code_only(s), re.M)
    check("GX-05 RN = the existing Engine /6 RN with yen config only: steps / scores passed to the Engine config, gate "
          "enableRn and rnStepOK and ticker GBPJPY (no XAUUSD gate left), one runtime.error only when RN is ON with "
          "invalid steps; no RN zone registered outside the Engine (RN is scored in f_finalizeCluster only)",
          cfg(GBV) == rn_cfg and cfg(GBS) == rn_cfg and ticks(GBV) == ticks(GBS) == ["GBPJPY"]
          and errs(GBV) == errs(GBS) == ["if enableRn and not rnStepOK"]
          and "rnLevel" not in code_only(GBV) and "f_registerStatic" not in GBV, str((cfg(GBV), ticks(GBV), errs(GBV))))
    req = lambda s: re.findall(r"request\.\w+\(.*$", code_only(s), re.M)
    cnt = lambda s, p: len(re.findall(p, code_only(s)))
    rnblk = GBV[GBV.index("float rnRatio"):GBV.index("runtime.error(")]
    check("GX-06 lightweight: requests unchanged (Visual 10, Strategy 11), zone loops (zn.zoneAt) unchanged, FVG slots "
          "unchanged, no new box / label / table / line, str.* or plot calls; the RN check is arithmetic only (no loop / "
          "request); RE10045 lint clean",
          req(GBV) == req(GBV0) and req(GBS) == req(GBS0) and len(req(GBV)) == 10 and len(req(GBS)) == 11
          and all(cnt(n, p) == cnt(o, p) for n, o in ((GBV, GBV0), (GBS, GBS0))
                  for p in (r"zn\.zoneAt\(", r"\b(box|label|table|line)\.new\(", r"\bstr\.\w+\(", r"\bplot\w*\(",
                            r"\bfor\b", r"\bwhile\b"))
          and not re.search(r"\b(for|while|request)\b", rnblk)
          and fr.lint_eager_guards(code_only(GBV)) == [] and fr.lint_eager_guards(code_only(GBS)) == [])
    d = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", BASE, "--"] + PROTECTED, capture_output=True, text=True)
    t = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", "--diff-filter=MDR", BASE, "--", "tests/"],
                       capture_output=True, text=True).stdout
    check("GX-07 Gold (ZONE-P / ZONE-ST), USDJPY (Visual / Strategy), Engines (/2, /5, /6, Authority), old strategies "
          "unchanged vs " + BASE + "; only GBPJPY tests / generators changed",
          d.returncode == 0 and d.stdout.strip() == "" and all(re.match(r"^tests/gb[jsx]_\w+\.py$", f) for f in t.split()),
          d.stdout + t)
    pin = ["    int k1 = math.ceil(zBot / step)\n    int k2 = math.floor(zTop / step)\n    if k1 <= k2\n",
           "        float lvMaj = f_rnLevelIn(zBot, zTop, c.rnStepMajor)\n        if not na(lvMaj)\n",
           "    int   cat = (hasMA ? 1 : 0) + (hasHZ ? 1 : 0) + (hasDHL ? 1 : 0) + (hasACC ? 1 : 0) + (hasRN ? 1 : 0)\n"]
    check("GX-08 the Engine RN formula the mirror models is pinned (ceil(bottom / step) <= floor(top / step), major first, "
          "RN as its own Confluence category; no tolerance distance)", all(ENGINE.count(p) == 1 for p in pin))


# ---- mirrors ------------------------------------------------------------------------------------------------------------
SUP, RES, ACT, BRK = 1, 2, 0, 3
CONF = {2: 1.0, 3: 2.0}
conf = lambda c: 3.0 if c >= 4 else CONF.get(c, 0.0)
strength = lambda s, htf: 1 if s < 5 else 2 if s < 10 else (3 if s < 15 or not htf else 4)


def fvg_select(z, slots, dirmatch, post_filter=False):
    """f_fvcZoneDisplay / f_zpoBestFvg: slots = [(alive, top, bot, dir, closeT)], index = slot (TF = slot // 5)."""
    want = (1 if z["state"] == SUP else -1 if z["state"] == RES else 0) if dirmatch else 0
    best = -1
    for s, (alive, top, bot, d, ct) in enumerate(slots):
        if alive and (post_filter or want == 0 or d == want):
            if min(z["top"], top) > max(z["bot"], bot):
                if best < 0 or s // 5 > best // 5 or (s // 5 == best // 5 and ct > slots[best][4]):
                    best = s
    if post_filter and best >= 0 and want != 0 and slots[best][3] != want:
        best = -1
    return best


def zone_eval(z, slots, dirmatch, post_filter=False):
    """f_stZoneEval (dScore / dStr / boosted / boost range) on the mirror selection."""
    best = fvg_select(z, slots, dirmatch, post_filter)
    dS, dStr = z["score"], z["str"]
    if best >= 0:
        dS = z["baseSum"] + (best // 5 + 1) + z["slope"] + conf(z["cat"] + 1)
        dStr = strength(dS, z["htf"])
    boosted = best >= 0 and dStr > z["str"]
    rng = (max(z["bot"], slots[best][2]), min(z["top"], slots[best][1])) if boosted else None
    return best, dS, dStr, boosted, rng


def mkzone(state, bot, top, baseSum, cat, slope=0.0, htf=True):
    sc = baseSum + slope + conf(cat)
    return dict(state=state, bot=bot, top=top, baseSum=baseSum, cat=cat, slope=slope, htf=htf, score=sc,
                str=strength(sc, htf))


def empty():
    return [(False, None, None, 0, 0)] * 15


def put(slots, s, top, bot, d, ct):
    slots = list(slots)
    slots[s] = (True, top, bot, d, ct)
    return slots


def rn_level_in(zb, zt, step):
    """Engine f_rnLevelIn (existence only): ceil(bottom / step) <= floor(top / step)."""
    return math.ceil(zb / step) <= math.floor(zt / step)


def rn_pick(zb, zt, on, major=(1.0, 3.0), minor=(0.5, 2.0)):
    if not on:
        return 0.0
    if rn_level_in(zb, zt, major[0]):
        return major[1]
    if rn_level_in(zb, zt, minor[0]):
        return minor[1]
    return 0.0


def rn_score(baseSum, cat, zb, zt, on, **kw):
    """f_finalizeCluster RN part: rnB added to baseSum once, RN counted as one more Confluence category."""
    rnB = rn_pick(zb, zt, on, **kw)
    c = cat + (1 if rnB > 0 else 0)
    return baseSum + rnB + conf(c), rnB, c


def rn_step_ok(major, minor, mintick=0.001):
    """mirror of rnStepOK in the Visual / Strategy."""
    if not minor > 0:
        return False
    r, mj, mn = major / minor, major / mintick, minor / mintick
    return (major > minor and abs(r - round(r)) < 1e-9 and abs(mj - round(mj)) < 1e-6 and abs(mn - round(mn)) < 1e-6
            and major * 8 == round(major * 8) and minor * 8 == round(minor * 8))


def fvg_fixtures(sel=fvg_select, ev=zone_eval):
    out = []
    zs = mkzone(SUP, 190.000, 190.100, 8.0, 2)           # Medium 9 (D Accum + 1H Swing)
    sl = put(put(empty(), 10, 190.080, 190.020, -1, 100), 5, 190.070, 190.010, 1, 90)   # 4H bear + 1H bull
    out.append(("SUP: OFF takes the 4H bear FVG (+3); ON takes the 1H bull FVG (+2), not dropped",
                (sel(zs, sl, False), sel(zs, sl, True)) == (10, 5)))
    zr = mkzone(RES, 191.000, 191.100, 8.0, 2)
    sr = put(put(empty(), 12, 191.090, 191.030, 1, 100), 1, 191.060, 191.020, -1, 80)   # 4H bull + 15M bear
    out.append(("RES: ON takes the 15M bear FVG behind a better bull 4H", (sel(zr, sr, False), sel(zr, sr, True)) == (12, 1)))
    so = put(put(empty(), 6, 190.080, 190.020, -1, 100), 11, 190.090, 190.010, -1, 90)
    b, dS, dStr, boosted, rng = ev(zs, so, True)
    out.append(("SUP with only bear FVGs: ON -> no candidate, score / strength = the Engine zone, no boost range",
                b == -1 and dS == zs["score"] and dStr == zs["str"] and not boosted and rng is None
                and ev(zs, so, False)[3]))
    for st in (ACT, BRK):
        z2 = dict(zs, state=st)
        out.append((f"state {st}: ON = OFF", sel(z2, sl, True) == sel(z2, sl, False) == 10))
    tie = put(put(empty(), 5, 190.070, 190.010, 1, 90), 7, 190.060, 190.030, 1, 95)
    out.append(("same TF, same direction: the newer one (higher close time)", sel(zs, tie, True) == 7))
    b, dS, dStr, boosted, rng = ev(zs, sl, True)
    b0, dS0, _, boosted0, rng0 = ev(zs, sl, False)
    out.append(("boost range = zone ∩ chosen FVG: ON 1H bull -> 12.0 Strong over [190.010, 190.070]; OFF 4H "
                "bear -> 13.0 over [190.020, 190.080]", (dS, dStr, rng) == (12.0, 3, (190.010, 190.070)) and boosted
                and (dS0, rng0) == (13.0, (190.020, 190.080)) and boosted0))
    zst = mkzone(SUP, 190.000, 190.100, 9.0, 3)            # 11 Strong already
    b, dS, dStr, boosted, rng = ev(zst, so, True)
    out.append(("base Strong + only mismatched FVGs: no FVG, still Strong -> Strategy candidate (z.strength >= Strong)",
                b == -1 and zst["str"] >= 3 and dStr >= 3))
    zno = mkzone(SUP, 190.000, 190.100, 8.0, 2)
    far = put(empty(), 5, 190.300, 190.200, 1, 90)
    out.append(("no overlap: no candidate ON or OFF", sel(zno, far, True) == sel(zno, far, False) == -1))
    return out


def rn_fixtures(pick=rn_pick, score=rn_score):
    out = []
    out.append(("integer yen 210.000 inside [209.970, 210.030] -> major +3", pick(209.970, 210.030, True) == 3.0))
    out.append(("half yen 210.500 inside [210.470, 210.530] -> minor +2", pick(210.470, 210.530, True) == 2.0))
    out.append(("outside: [210.100, 210.400] -> 0", pick(210.100, 210.400, True) == 0.0))
    out.append(("boundary inclusive: top = 210.000 (209.950 + 0.05) -> +3; bottom = 210.500 (210.550 - 0.05) -> +2",
                pick(209.950 - 0.05, 209.950 + 0.05, True) == 3.0 and pick(210.550 - 0.05, 210.550 + 0.05, True) == 2.0))
    out.append(("just outside: top 209.999 / bottom 210.001 -> 0", pick(209.900, 209.999, True) == 0.0
                and pick(210.001, 210.400, True) == 0.0))
    out.append(("both levels in the zone [209.400, 210.100] (210.000 and 209.500) -> major only, +3 not +5",
                pick(209.400, 210.100, True) == 3.0))
    out.append(("OFF -> 0", pick(209.970, 210.030, False) == 0.0))
    out.append(("changed inputs: major 0.50 / +4, minor 0.25 / +1: 210.500 -> 4, 210.250 -> 1, 210.000 -> 4",
                pick(210.48, 210.52, True, major=(0.5, 4.0), minor=(0.25, 1.0)) == 4.0
                and pick(210.23, 210.27, True, major=(0.5, 4.0), minor=(0.25, 1.0)) == 1.0
                and pick(209.98, 210.02, True, major=(0.5, 4.0), minor=(0.25, 1.0)) == 4.0))
    s2 = score(8.0, 2, 209.970, 210.030, True)
    s1 = score(5.0, 1, 209.970, 210.030, True)
    s4 = score(12.0, 4, 209.970, 210.030, True)
    out.append(("Confluence: 2 categories + RN -> 3 (8 + 3 + 2 = 13 Strong; +4 vs without); 1 + RN -> 2 (5 + 3 + 1 = 9); "
                "4 + RN -> 5 (12 + 3 + 3 = 18, Confluence capped)",
                s2 == (13.0, 3.0, 3) and score(8.0, 2, 209.970, 210.030, False)[0] == 9.0 and s1 == (9.0, 3.0, 2)
                and s4 == (18.0, 3.0, 5)))
    return out


def gate_model():
    for n, ok in fvg_fixtures():
        check("GM-F " + n, ok)
    for n, ok in rn_fixtures():
        check("GM-R " + n, ok)
    # float exactness of the Engine formula on the 0.001 price grid (centres) for Half Width 0.005 .. 0.200
    res = {}
    for step in (1.0, 0.5, 0.25, 0.125, 0.375, 2.0, 0.1, 0.2, 0.3):
        bad = 0
        for h in range(1, 41):
            hw = round(h * 0.005, 3)
            for i in range(180000, 230001, 3):
                c = i / 1000
                f = rn_level_in(c - hw, c + hw, step)
                dc, dh, ds = Dec(i) / 1000, Dec(str(hw)), Dec(str(step))
                bad += f != (math.ceil((dc - dh) / ds) <= math.floor((dc + dh) / ds))
        res[step] = bad
    allowed = [s for s in res if rn_step_ok(max(s, 0.25) * 2 if s < 1 else s * 2, s)]
    check("GM-X RN float check: on the 0.001 grid (180-230 円, HW 0.005-0.200) the Engine formula equals exact decimal "
          "arithmetic for every allowed step (multiples of 0.125: 0.125 / 0.25 / 0.375 / 0.5 / 1 / 2); 0.1 / 0.2 / 0.3 "
          "misjudge at exact boundaries and are rejected by the step check",
          all(res[s] == 0 for s in (1.0, 0.5, 0.25, 0.125, 0.375, 2.0)) and all(res[s] > 0 for s in (0.1, 0.2, 0.3))
          and not rn_step_ok(1.0, 0.2) and not rn_step_ok(0.3, 0.1) and not rn_step_ok(0.2, 0.1), str((res, allowed)))
    v = {(1.0, 0.5): True, (2.0, 0.5): True, (1.0, 0.25): True, (0.375, 0.125): True, (0.5, 0.5): False,
         (0.75, 0.5): False, (1.0, 0.2): False, (0.5, 1.0): False, (1.0005, 0.5): False, (1.0, 0.0): False}
    got = {k: rn_step_ok(*k) for k in v}
    check("GM-V step validation: 1.0 / 0.5, 2.0 / 0.5, 1.0 / 0.25, 0.375 / 0.125 valid; equal steps, non-multiple ratio "
          "(0.75 / 0.5), non-0.125 step (0.2), major < minor, off-mintick (1.0005), zero minor invalid", got == v, str(got))


def gate_mutation():
    # mirror mutations
    post = lambda z, s, d, pf=False: fvg_select(z, s, d, post_filter=True)
    post_ev = lambda z, s, d, pf=False: zone_eval(z, s, d, post_filter=True)
    swap = lambda z, s, d, pf=False: fvg_select(dict(z, state=RES if z["state"] == SUP else SUP if z["state"] == RES else z["state"]), s, d)
    allst = lambda z, s, d, pf=False: fvg_select(dict(z, state=SUP if z["state"] in (ACT, BRK) else z["state"]), s, d)
    caught = {}
    for name, sel, ev in (("post-filter (choose best, then drop wrong direction)", post, post_ev),
                          ("direction sign swapped", swap, zone_eval), ("filter applied to ACTIVE / BROKEN", allst, zone_eval)):
        caught[name] = not all(ok for _, ok in fvg_fixtures(sel, ev))
    double = lambda zb, zt, on, major=(1.0, 3.0), minor=(0.5, 2.0): (
        (major[1] if rn_level_in(zb, zt, major[0]) else 0.0) + (minor[1] if rn_level_in(zb, zt, minor[0]) else 0.0)) if on else 0.0
    nocat = lambda b, c, zb, zt, on, **kw: (b + rn_pick(zb, zt, on, **kw) + conf(c), rn_pick(zb, zt, on, **kw), c)
    tol = lambda zb, zt, on, major=(1.0, 3.0), minor=(0.5, 2.0): rn_pick(zb - 0.002, zt + 0.002, on, major, minor)
    for name, pk, sc in (("RN major + minor both added", double, rn_score), ("RN not counted as a category", rn_pick, nocat),
                         ("RN with an invented 0.002 tolerance", tol, rn_score)):
        caught[name] = not all(ok for _, ok in rn_fixtures(pk, sc))
    check("GU-01 mirror mutations caught (" + str(len(caught)) + "): " + ", ".join(caught), all(caught.values()),
          str(caught))
    # source mutations: the static gates must reject them
    muts = {
        "post-filter in f_zpoBestFvg": (gb.SEL_NEW, gb.SEL_OLD),
        "RN gate without the step check": ("enableRn and rnStepOK and syminfo.ticker", "enableRn and syminfo.ticker"),
        "FVG direction sign swapped": ("z.state == ST_SUPPORT ? 1 : z.state == ST_RESIST ? -1", "z.state == ST_SUPPORT ? -1 : z.state == ST_RESIST ? 1"),
        "FVG points changed": ("math.floor(slot / FVG_SLOTS_PER_TF) + 1.0", "math.floor(slot / FVG_SLOTS_PER_TF) + 2.0"),
    }
    global GBV, GBS
    keep = (GBV, GBS, list(RESULTS))
    rej = {}
    for name, (a, b) in muts.items():
        GBV, GBS = keep[0].replace(a, b, 1), keep[1].replace(a, b, 1)
        del RESULTS[:]
        try:
            gate_static()
            rej[name] = not all(ok for _, ok, _ in RESULTS)
        except Exception:
            rej[name] = True
    GBV, GBS = keep[0], keep[1]
    RESULTS[:] = keep[2]
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
