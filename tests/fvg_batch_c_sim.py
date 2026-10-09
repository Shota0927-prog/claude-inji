"""FVG Batch C fixtures — display-only mutual bonus between FVGs and the existing Zones.

Spec: FVG実装仕様書 v1.0 + A01 + A02, Batch C.

  C0  structure : current == c_transform(90f29a7) exactly; A block content unchanged (only moved); C block in A < C < B
                  order; production part == d240ec0 + exactly the draw-loop edits
  C1  score     : no FVG -> Engine values; 15M / 1H / 4H bonus; max-1; ties; width 0; baseSum transfer; Broken rules
  C2  confl/HTF : Confluence replaced not added; 2 / 3 / 4+ categories; HTF kept / inherited; Very Strong; no bonus transfer
  C3  display   : filters never change scores; display Strength drives filter / transparency / width / name / score;
                  Touch label by the Engine Strength; no write to Zone / FVG / Engine state
  C4  perf      : no request, no allocation, no recursion, only at barstate.islast, eager-evaluation lint

Evidence class: PINE_NOT_VERIFIED (exact transform + static checks + Python mirror; TradingView rendering is external).
"""
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fvg_batch_a_sim as fa          # noqa: E402
import fvg_batch_b_sim as fb          # noqa: E402
import fvg_batch_c_build as cb        # noqa: E402
import fvg_re10045_sim as fr          # noqa: E402

ROOT = fa.ROOT
CUR = fa.CUR
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


def git_show(rev, path="ZoneVisualPractical.pine"):
    return subprocess.run(["git", "-C", ROOT, "show", f"{rev}:{path}"], capture_output=True, text=True).stdout


BASE_C = git_show(cb.C_BASE_REV)
code_only = fa.code_only


def blk(src, b, e):
    if src.count(b) != 1 or src.count(e) != 1:
        return ""
    return src[src.index(b):src.index("\n", src.index(e)) + 1]


CBLK = blk(CUR, cb.C_BEGIN, cb.C_END)
CC = code_only(CBLK)


# ============================================================================
# C0 / C4 : static
# ============================================================================
def gate_static():
    check("C0-01 current Visual == c_transform(90f29a7) exactly (A moved unchanged, C inserted, 4 draw-loop edits, 7 Batch B edits)",
          bool(BASE_C) and cb.c_transform(BASE_C) == CUR)
    check("C0-02 Batch A block content byte-identical to 90f29a7 (only its position changed: before the DISPLAY banner)",
          blk(CUR, cb.A_BEGIN, cb.A_END) == blk(BASE_C, cb.A_BEGIN, cb.A_END) != ""
          and (blk(CUR, cb.A_BEGIN, cb.A_END) + "\n" + cb.DISPLAY_BANNER) in CUR)
    marks = [cb.A_BEGIN, cb.A_END, cb.C_BEGIN, cb.C_END, cb.B_BEGIN, cb.B_END]
    check("C0-03 markers: exactly one A / C / B block, order A < C < B; C block immediately before the existing draw loop",
          [CUR.count(m) for m in marks] == [1] * 6 and [CUR.index(m) for m in marks] == sorted(CUR.index(m) for m in marks)
          and (CBLK + "\n" + cb.DRAW_ANCHOR) in CUR)
    prod, _, _, ok = fb.split(CUR)
    check("C0-04 production part (A / C / B removed) == d240ec0 + exactly the 4 draw-loop edits; reverting them gives d240ec0",
          ok and prod == cb.apply_prod_edits(fa.BASE) and cb.revert_prod_edits(prod) == fa.BASE)
    eng = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", cb.C_BASE_REV, "--",
                          "ZoneEnginePractical.pine", "ZoneEnginePracticalAuthority.pine", "SignalEnginePractical.pine",
                          "PracticalZoneStrategy_LONG.pine", "PracticalZoneStrategy_SHORT.pine"]
                         + [f for f in os.listdir(ROOT) if f.startswith("Practical") and f.endswith("Harness.pine")],
                         capture_output=True, text=True).stdout.strip()
    check("C0-05 Engine / SignalEngine / Strategy / Harness / Authority unchanged vs 90f29a7", eng == "", eng)
    # engine formula equality
    eng_src = open(os.path.join(ROOT, "ZoneEnginePractical.pine"), encoding="utf-8").read()

    def body(src, head):
        t = src[src.index(head):]
        return t[:t.index("\n\n")].split("\n", 1)[1]
    check("C2-00 f_fvcConf body == Engine f_confluenceBonus body (cfg -> the same Visual inputs)",
          body(eng_src, "f_confluenceBonus(int catCount, ZoneCfg c) =>").replace("c.", "") == body(CC, "f_fvcConf(int catCount) =>"))
    check("C2-00b f_fvcStrengthOf body == Engine f_strengthOf body",
          body(eng_src, "f_strengthOf(float score, bool hasHtf, ZoneCfg c) =>").replace("c.", "") == body(CC, "f_fvcStrengthOf(float score, bool hasHtf) =>"))
    check("C1-00 Pine formulas: Zone = baseSum + FVG base + slope + maBonus + flipBonus + Conf(catCount + 1) with z.hasHtf; "
          "FVG = base + baseSum + Conf(1 + catCount) with that Zone's hasHtf; overlap width > 0; Broken excluded for the FVG side",
          all(re.search(r"^\s*" + re.escape(x) + r"$", CC, re.M) for x in (
              "dScore := z.baseSum + f_fvcBase(best) + z.slopeBonus + z.maBonus + z.flipBonus + f_fvcConf(z.catCount + 1)",
              "dStr   := f_fvcStrengthOf(dScore, z.hasHtf)", "float dScore = z.score", "int   dStr   = z.strength",
              "cf  := f_fvcConf(1 + sz.catCount)", "sc  := fb + sz.baseSum + cf", "htf := sz.hasHtf", "bool  htf = false",
              "math.min(aTop, bTop) > math.max(aBot, bBot)", "if z.state != ST_BROKEN", "math.floor(slot / FVG_SLOTS_PER_TF) + 1.0",
              "[sc, f_fvcStrengthOf(sc, htf), zb, cf]", "[dScore, dStr]")))
    check("C1-00b Pine tie-breaks: Zone side base desc -> newer close time; FVG side baseSum -> catCount -> hasHtf -> lower index",
          all(x in CC for x in ("else if f_fvcBase(s) > f_fvcBase(best)", "else if f_fvcBase(s) == f_fvcBase(best)",
                                 "if array.get(gFvgCloseT, s) > array.get(gFvgCloseT, best)",
                                 "if z.baseSum > bz.baseSum", "else if z.baseSum == bz.baseSum", "if z.catCount > bz.catCount",
                                 "else if z.catCount == bz.catCount", "if z.hasHtf and not bz.hasHtf")))
    # C3 / C4
    check("C3-00 no write to Engine Zones / FVG state / Engine: no field assignment on z / bz / sz, no array.set / push, no zn.update",
          not re.search(r"\b(z|bz|sz)\.\w+\s*:=", CC) and "array.set" not in CC and "array.push" not in CC
          and "zn.update" not in CC and set(re.findall(r"\bzn\.(\w+)", CC)) <= {"zoneAt", "zoneCount", "strengthName", "sourceText", "Zone"})
    check("C3-01 score functions never read display filters (only f_fvcShowByStrength / labels do)",
          not re.search(r"show(Weak|Medium|Strong|VStrong|Support|Resistance|Active|Broken)",
                        CC[CC.index("f_fvcBase(int slot)"):CC.index("f_fvcLabelText(")]))
    check("C3-02 Touch label shown by the Engine Strength (z.strength >= SR_STRONG); name / score from display values",
          "if z.strength >= SR_STRONG\n        txt := txt + \" | Touch \" + str.tostring(z.touchCount)" in CC
          and "string txt = zn.strengthName(dStr)" in CC and "f_num(dScore, \"#.#\")" in CC)
    prodc = code_only(fb.split(CUR)[0])
    check("C3-03 existing draw loop: filter / transparency / width / label use the display Strength / Score; colour, border "
          "style (Broken dashed), box top / bottom stay Engine values",
          all(x in prodc for x in ("[dScore, dStr] = f_fvcZoneDisplay(z)", "if not (f_fvcShowByStrength(dStr) and f_showByState(z))",
                                    "int   tr  = f_zoneTransp(dStr)", "int   bw  = dStr >= SR_STRONG ? 2 : 1",
                                    "string txt = f_fvcLabelText(z, dStr, dScore)", "color bc  = f_zoneColor(z.state)",
                                    "string bs = z.state == ST_BROKEN ? line.style_dashed : line.style_solid",
                                    "box.set_lefttop(b, xL, z.top)", "box.set_rightbottom(b, xR, z.bottom)")))
    allc = code_only(CUR)
    check("C4-01 no new request (same request.* count as 90f29a7) and none in the C block",
          len(re.findall(r"request\.\w+\(", allc)) == len(re.findall(r"request\.\w+\(", code_only(BASE_C)))
          and not re.search(r"request\.\w+\(", CC))
    check("C4-02 no allocation / sort / loop over history in C (no array.new / sort / copy, no [n] history)",
          not re.search(r"array\.(new|sort|copy)|sort_indices", CC) and not re.search(r"\w\[\d+\]", CC))
    check("C4-03 non-recursive: f_fvcZoneDisplay and f_fvcFvgDisplay never call each other or themselves",
          "f_fvcFvgDisplay(" not in CC[CC.index("f_fvcZoneDisplay(zn.Zone z) =>"):CC.index("f_fvcFvgDisplay(int slot) =>")]
          and "f_fvcZoneDisplay(" not in CC[CC.index("f_fvcFvgDisplay(int slot) =>"):])
    calls = [m.start() for m in re.finditer(r"f_fvc(ZoneDisplay|FvgDisplay)\(", allc)]
    islast = [m.start() for m in re.finditer(r"^if barstate\.islast and is5mChart\n", allc, re.M)]
    check("C4-04 display functions called only inside the barstate.islast draw paths (existing loop + Batch B loop)",
          len(calls) == 4 and all(any(st < c for st in islast) for c in calls[2:])
          and all(c > islast[0] for c in calls[2:]) and allc.count("f_fvcZoneDisplay(z)") == 1
          and allc.count("f_fvcFvgDisplay(pick)") == 1)
    check("C4-05 RE10045 lint over the C block: no and / or that mixes a -1 / na guard with array access on that index",
          fr.lint_eager_guards(CC) == [])
    check("C4-06 Engine update count unchanged (zn.update appears once)", allc.count("zn.update(") == 1)


# ============================================================================
# Python mirror
# ============================================================================
class Z:
    def __init__(self, top, bottom, baseSum, slope=0.0, ma=0.0, flip=0.0, cat=1, htf=False, state=1, touch=0, st=None):
        self.top, self.bottom, self.baseSum = top, bottom, baseSum
        self.slopeBonus, self.maBonus, self.flipBonus = slope, ma, flip
        self.catCount, self.hasHtf, self.state, self.touchCount = cat, htf, state, touch
        self.confBonus = conf(cat)
        self.score = baseSum + slope + ma + flip + self.confBonus
        self.strength = strength_of(self.score, htf) if st is None else st


CFG = dict(thrMedium=5.0, thrStrong=10.0, thrVStrong=15.0, requireHtf=True, conf2=1.0, conf3=2.0, conf4=3.0)
ST_BROKEN = 3


def conf(n, c=CFG):
    return c["conf4"] if n >= 4 else c["conf3"] if n == 3 else c["conf2"] if n == 2 else 0.0


def strength_of(score, htf, c=CFG):
    t = 1 if score < c["thrMedium"] else 2 if score < c["thrStrong"] else 3 if score < c["thrVStrong"] else 4
    if t == 4 and c["requireHtf"] and not htf:
        t = 3
    return t


def overlap(aT, aB, bT, bB):
    return min(aT, bT) > max(aB, bB)


def base_of(slot):
    return slot // 5 + 1.0


class FV:
    """minimal FVG store: 15 slots (top, bot, closeT, alive)."""
    def __init__(self):
        self.top, self.bot, self.closeT, self.alive = [None] * 15, [None] * 15, [None] * 15, [False] * 15

    def put(self, slot, top, bot, closeT=0):
        self.top[slot], self.bot[slot], self.closeT[slot], self.alive[slot] = top, bot, closeT, True
        return self


def zone_display(z, fv):
    best = -1
    for s in range(15):
        if fv.alive[s] and overlap(z.top, z.bottom, fv.top[s], fv.bot[s]):
            if best < 0:
                best = s
            elif base_of(s) > base_of(best):
                best = s
            elif base_of(s) == base_of(best) and fv.closeT[s] > fv.closeT[best]:
                best = s
    if best < 0:
        return z.score, z.strength, best
    sc = z.baseSum + base_of(best) + z.slopeBonus + z.maBonus + z.flipBonus + conf(z.catCount + 1)
    return sc, strength_of(sc, z.hasHtf), best


def fvg_display(slot, fv, zones):
    fbp = base_of(slot)
    best = -1
    for i, z in enumerate(zones):
        if z.state != ST_BROKEN and overlap(z.top, z.bottom, fv.top[slot], fv.bot[slot]):
            if best < 0:
                best = i
            else:
                bz = zones[best]
                if z.baseSum > bz.baseSum or (z.baseSum == bz.baseSum and (z.catCount > bz.catCount or
                                              (z.catCount == bz.catCount and z.hasHtf and not bz.hasHtf))):
                    best = i
    if best < 0:
        return fbp, strength_of(fbp, False), None, 0.0, best
    sz = zones[best]
    cf = conf(1 + sz.catCount)
    sc = fbp + sz.baseSum + cf
    return sc, strength_of(sc, sz.hasHtf), sz.baseSum, cf, best


def gate_mirror():
    # C1 -------------------------------------------------------------------
    z = Z(2010, 2000, 6.0, cat=2, htf=True)             # score 7 MEDIUM
    empty = FV()
    check("C1-01 no FVG -> display Score / Strength == z.score / z.strength exactly", zone_display(z, empty)[:2] == (z.score, z.strength))
    for slot, b in ((0, 1.0), (5, 2.0), (10, 3.0)):
        sc, st, _ = zone_display(z, FV().put(slot, 2008, 2003))
        check(f"C1-02 {['15M', '1H', '4H'][slot // 5]} FVG overlapping -> + base {b:g} and Conf(2+1): {6 + b + 2:g}",
              sc == 6.0 + b + 2.0, str(sc))
    fv = FV().put(0, 2008, 2003).put(5, 2009, 2004).put(10, 2007, 2002)
    check("C1-03 15M + 1H + 4H all overlapping -> only the max base (3) is added", zone_display(z, fv)[0] == 6 + 3 + 2)
    fv2 = FV().put(5, 2008, 2003, closeT=100).put(6, 2009, 2004, closeT=200)
    check("C1-04 equal base -> the newer formation close time is selected (score identical either way)",
          zone_display(z, fv2)[2] == 6 and zone_display(z, fv2)[0] == 6 + 2 + 2)
    check("C1-05 overlap width 0 (touching edge) -> no bonus; width > 0 -> bonus",
          zone_display(z, FV().put(10, 2015, 2010))[0] == z.score and zone_display(z, FV().put(10, 2015, 2009.99))[0] == 6 + 3 + 2)
    check("C1-06 FVGs never score each other: two overlapping FVGs with no Zone -> each keeps base only",
          fvg_display(0, FV().put(0, 2008, 2003).put(5, 2009, 2004), [])[0] == 1.0
          and fvg_display(5, FV().put(0, 2008, 2003).put(5, 2009, 2004), [])[0] == 2.0)
    zs = [Z(2010, 2000, 6.0, cat=2, htf=True), Z(2012, 2004, 9.0, cat=3, htf=False)]
    sc, st, zb, cf, bi = fvg_display(5, FV().put(5, 2008, 2005), zs)
    check("C1-07 FVG receives the max-baseSum overlapping Zone's baseSum only (9) + Conf(1 + 3) = 2 + 9 + 3",
          (sc, zb, cf, bi) == (14.0, 9.0, 3.0, 1), str((sc, zb, cf, bi)))
    zs_b = [Z(2010, 2000, 6.0, cat=2, htf=True), Z(2012, 2004, 9.0, cat=3, state=ST_BROKEN)]
    check("C1-08 BROKEN Zone is excluded as a source for the FVG (falls back to the next Zone)",
          fvg_display(5, FV().put(5, 2008, 2005), zs_b)[4] == 0)
    check("C1-09 BROKEN Zone itself still receives the FVG bonus",
          zone_display(Z(2012, 2004, 9.0, cat=3, state=ST_BROKEN), FV().put(5, 2008, 2005))[0] == 9 + 2 + 3)
    ties = [Z(2010, 2000, 6.0, cat=2, htf=False), Z(2011, 2001, 6.0, cat=3, htf=False),
            Z(2012, 2002, 6.0, cat=3, htf=True), Z(2013, 2003, 6.0, cat=3, htf=True)]
    check("C1-10 FVG tie-break: baseSum -> catCount -> hasHtf -> lower Zone index",
          fvg_display(0, FV().put(0, 2008, 2005), ties)[4] == 2
          and fvg_display(0, FV().put(0, 2008, 2005), ties[:2])[4] == 1
          and fvg_display(0, FV().put(0, 2008, 2005), [ties[2], ties[3]])[4] == 0)
    # C2 -------------------------------------------------------------------
    zc = Z(2010, 2000, 4.0, slope=1.0, ma=1.0, cat=2)      # conf 1 -> score 7
    sc, _, _ = zone_display(zc, FV().put(5, 2008, 2003))
    check("C2-01 Confluence replaced, not added: 4 + 2 + 1 + 1 + Conf(3)=2 = 10 (not + old conf 1)", sc == 10.0, str(sc))
    vals = [zone_display(Z(2010, 2000, 4.0, cat=n), FV().put(0, 2008, 2003))[0] - 4.0 - 1.0 for n in (1, 2, 3, 4)]
    check("C2-02 categories +1: 1->2 (1.0), 2->3 (2.0), 3->4 (3.0), 4->5 (3.0, 4+ capped)", vals == [1.0, 2.0, 3.0, 3.0], str(vals))
    zv = Z(2010, 2000, 10.0, cat=3, htf=True)               # 10 + conf 2 = 12 STRONG
    zv_n = Z(2010, 2000, 10.0, cat=3, htf=False)
    check("C2-03 Very Strong needs HTF: 10 + 3 + Conf(4)=3 = 16 -> VERY STRONG with hasHtf, STRONG without",
          zone_display(zv, FV().put(10, 2008, 2003))[:2] == (16.0, 4) and zone_display(zv_n, FV().put(10, 2008, 2003))[:2] == (16.0, 3))
    zf = [Z(2010, 2000, 10.0, slope=2.0, ma=2.0, flip=2.0, cat=3, htf=True)]
    sc, st, zb, cf, _ = fvg_display(10, FV().put(10, 2008, 2003), zf)
    check("C2-04 FVG gets baseSum only (no slope / maBonus / flip / old conf transfer): 3 + 10 + Conf(4)=3 = 16, "
          "HTF inherited -> VERY STRONG", (sc, st) == (16.0, 4), str((sc, st)))
    check("C2-05 FVG with no Zone: HTF false -> never VERY STRONG even with low thresholds",
          strength_of(3.0, False, dict(CFG, thrMedium=1, thrStrong=2, thrVStrong=3)) == 3)
    # C3 -------------------------------------------------------------------
    st_store, _ = fb.store_with(n15=2, n60=1, n240=1)
    zones = [Z(2010, 1998, 6.0, cat=2, htf=True), Z(2030, 2018, 8.0, cat=3, state=ST_BROKEN)]
    snap = (list(st_store.alive), list(st_store.top), list(st_store.bot))
    zsnap = [(z.top, z.bottom, z.score, z.strength, z.state, z.touchCount) for z in zones]
    fvv = FV()
    for s_ in range(15):
        if st_store.alive[s_]:
            fvv.put(s_, st_store.top[s_], st_store.bot[s_], st_store.closeT[s_])
    res = [zone_display(z, fvv)[:2] for z in zones] + [fvg_display(s_, fvv, zones)[:2] for s_ in range(15) if fvv.alive[s_]]
    check("C3-01 scores from the real Batch A store do not depend on display filters (computed without any filter) and "
          "leave the store / Zones untouched", snap == (list(st_store.alive), list(st_store.top), list(st_store.bot))
          and zsnap == [(z.top, z.bottom, z.score, z.strength, z.state, z.touchCount) for z in zones] and len(res) == 6)
    zm = Z(2010, 2000, 6.0, cat=2, htf=True, touch=3)          # Engine MEDIUM (7)
    sc, st, _ = zone_display(zm, FV().put(10, 2008, 2003))     # 6 + 3 + 2 = 11 STRONG
    show_default = {1: False, 2: False, 3: True, 4: True}
    check("C3-02 display Strength promotes a MEDIUM Zone to STRONG: now passes the default filter, STRONG transparency / width",
          zm.strength == 2 and st == 3 and show_default[st] and not show_default[zm.strength])
    check("C3-03 Touch label uses the Engine Strength: promoted MEDIUM -> no Touch; Engine STRONG -> Touch kept",
          not (zm.strength >= 3) and (Z(2010, 2000, 9.0, cat=2, touch=2).strength >= 3))


def main():
    for g in (gate_static, gate_mirror):
        try:
            g()
        except Exception as ex:
            check(f"{g.__name__} completed without error", False, repr(ex))
    w = max(len(n) for n, _, _ in RESULTS)
    fails = 0
    for n, ok, d in RESULTS:
        fails += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {n.ljust(w)}  {'' if ok else d}")
    print(f"\n{len(RESULTS) - fails}/{len(RESULTS)} passed  [PINE_NOT_VERIFIED: exact transform / static / mirror]")
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
