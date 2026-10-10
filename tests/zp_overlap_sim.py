"""ZONE-P FVG overlap-only boost display fixtures (ZoneVisualPractical.pine @ 11b2b4e -> zp_overlap_build).

  ZS : static — exact transform, block protection, Batch B removal, selection = Batch C, object budget, lint
  ZM : Python mirror of the new draw pass (and of the 11b2b4e draw pass for regression) — Strength cases, filters,
       labels, multiple FVGs, expiry, pool reuse, Max Zones Drawn, eager-evaluation safety

Evidence class: PINE_NOT_VERIFIED (static checks and a Python mirror; TradingView compile / display is external).
"""
import itertools
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import zp_overlap_build as zp         # noqa: E402
import fvg_re10045_sim as fr          # noqa: E402
import nr_s1_build as nb              # noqa: E402
import nr_a1_build as na              # noqa: E402
import fvg_batch_c_build as cb        # noqa: E402

ROOT = zp.ROOT
CUR = open(os.path.join(ROOT, "ZoneVisualPractical.pine"), encoding="utf-8").read()
CUR = __import__("rnv_build").strip_rnv(CUR) or CUR  # RN-1 V1 stripped -> 6e554b2 text (delta pinned by rnv_sim)
BASE = zp.git_show(zp.ZPO_BASE_REV)
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


def code_only(src):
    return "\n".join(l for l in src.split("\n") if not l.lstrip().startswith("//"))


def block(src, begin, end):
    if src.count(begin) != 1 or src.count(end) != 1:
        return None
    i = src.index(begin)
    return src[i:src.index("\n", src.index(end)) + 1]


def func_body(src, head):
    """text of a top-level Pine function from its header line to the next blank line."""
    i = src.index(head)
    j = src.index("\n\n", i)
    return src[i:j + 1]


# =============================================================================
# ZS : static
# =============================================================================
def gate_static():
    check("ZS-01 current Visual == zpo_transform(11b2b4e) exactly (draw pass -> ZPO block, Batch B block removed)",
          bool(BASE) and zp.zpo_transform(BASE) == CUR)
    check("ZS-02 strip_zpo(current) == 11b2b4e byte-for-byte (the only differences are the ZPO block and the Batch B removal)",
          zp.strip_zpo(CUR, BASE) == BASE)
    for name, b, e in (("NR-S1", nb.NRS_BEGIN, nb.NRS_END), ("NR-A1", na.NRA_BEGIN, na.NRA_END),
                       ("FVG Batch A", cb.A_BEGIN, cb.A_END), ("FVG Batch C", cb.C_BEGIN, cb.C_END)):
        check(f"ZS-03 {name} block byte-identical to 11b2b4e", block(CUR, b, e) is not None and block(CUR, b, e) == block(BASE, b, e))
    blk = block(CUR, zp.ZPO_BEGIN, zp.ZPO_END) or ""
    check("ZS-04 exactly one ZPO block, preceded by a blank line, right after Batch C and before the MA plot section",
          bool(blk) and CUR[CUR.index(zp.ZPO_BEGIN) - 2:CUR.index(zp.ZPO_BEGIN)] == "\n\n"
          and CUR.index(cb.C_END) < CUR.index(zp.ZPO_BEGIN) < CUR.index("// ---- MA Source の可視化"))
    gone = ["gFvgBoxes", "gFvgLabels", "f_fvgShowByStrength", "f_fvgTfName", "f_fvgLabelText", "FVG_DRAW_MAX", zp.B_BEGIN, zp.B_END]
    check("ZS-05 FVG independent display removed: no Batch B block, pools, functions or FVG box / label left anywhere",
          not any(g in CUR for g in gone), str([g for g in gone if g in CUR]))
    co = code_only(CUR)
    check("ZS-06 box.new / label.new only inside the ZPO pool helpers (one each); no other drawing pool in the file",
          co.count("box.new(") == 1 and co.count("label.new(") == 1
          and code_only(func_body(CUR, "f_zpoBox(")).count("box.new(") == 1
          and code_only(func_body(CUR, "f_zpoLabel(")).count("label.new(") == 1
          and re.findall(r"var array<(?:box|label)>\s+(\w+)", co) == ["gBoxes", "gLabels"])
    # best-FVG selection: the loop of f_zpoBestFvg is the selection loop of Batch C f_fvcZoneDisplay, line for line
    sel_c = CUR[CUR.index("f_fvcZoneDisplay(zn.Zone z) =>\n") + len("f_fvcZoneDisplay(zn.Zone z) =>\n"):CUR.index("    float dScore = z.score\n")]
    sel_z = func_body(CUR, "f_zpoBestFvg(zn.Zone z) =>\n")[len("f_zpoBestFvg(zn.Zone z) =>\n"):]
    check("ZS-07 f_zpoBestFvg = Batch C f_fvcZoneDisplay selection (same loop text: alive, overlap > 0, max base, newer close)"
          " + `best` as the result", sel_z == sel_c + "    best\n", sel_z[:80])
    must = ["[dScore, dStr] = f_fvcZoneDisplay(z)\n",
            "bool boosted = best >= 0 and dStr > z.strength\n",
            "oTop := math.min(z.top, array.get(gFvgTop, best))\n",
            "oBot := math.max(z.bottom, array.get(gFvgBot, best))\n",
            "bool showBase  = f_showByStrength(z)\n",
            "bool showBoost = boosted and f_fvcShowByStrength(dStr)\n",
            "if nZone >= maxZonesDraw\n",
            "if not f_showByState(z)\n",
            "nLbl := f_zpoLabel(nLbl, xR, oTop, f_fvcLabelText(z, dStr, dScore), lc)\n",
            "if showBase and not (showBoost and oTop == z.top)\n",
            "nLbl := f_zpoLabel(nLbl, xR, z.top, f_labelText(z), lc)\n",
            "int   trB = f_zoneTransp(z.strength)\n", "int   trU = f_zoneTransp(dStr)\n"]
    check("ZS-08 draw rules in the block: Batch C score / strength, boost only when strength rises, intersection = "
          "[max bottom, min top], base / boost filters, Max Zones per Zone, label sources and collision rule",
          all(blk.count(m) == 1 for m in must), str([m for m in must if blk.count(m) != 1]))
    check("ZS-09 the oTop / oBot array reads happen only inside `if boosted` (best >= 0); RE10045 lint clean for the block",
          fr.lint_eager_guards(code_only(blk)) == [] and "                if boosted\n                    oTop := math.min" in blk)
    check("ZS-10 block is display-only: no request / barstate.isconfirmed / var; no write to gFvg* or to Engine Zone fields",
          not re.search(r"request\.\w+\(|barstate\.isconfirmed|\bvar\b", code_only(blk))
          and not re.search(r"array\.(set|push|remove|clear|insert)\(\s*gFvg", blk)
          and not re.search(r"\bz\.\w+\s*:=", blk) and "if barstate.islast and is5mChart\n" in blk)
    req = lambda s: len(re.findall(r"request\.\w+\(", code_only(s)))
    inp = lambda s: re.findall(r"^\s*\w+\s*=\s*input\.\w+\(.*$", s, re.M)
    check("ZS-11 request call sites and inputs unchanged vs 11b2b4e (no new input / request)",
          req(CUR) == req(BASE) == 10 and inp(CUR) == inp(BASE), f"{req(CUR)} / {req(BASE)}")
    names = ["ZoneEnginePractical.pine", "ZoneEnginePracticalAuthority.pine", "SignalEnginePractical.pine", "SignalEngine.pine",
             "ZoneEngine.pine", "PracticalZoneStrategy_LONG.pine", "PracticalZoneStrategy_SHORT.pine", "FvgZoneStrategy.pine",
             "PracticalZoneFeedHarness.pine", "PracticalAlertHarness.pine", "PracticalTradeHarness.pine",
             "PracticalBreakEvenHarness.pine", "PracticalEntryDispatchHarness.pine"]
    d = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", zp.ZPO_BASE_REV, "--"] + names, capture_output=True, text=True).stdout
    check("ZS-12 Engine / Library / SignalEngine / Strategy / Harness unchanged vs 11b2b4e", d.strip() == "", d)
    mz = re.search(r'maxZonesDraw\s*=\s*input\.int\(30, "Max Zones Drawn", minval = 1, maxval = (\d+)', CUR)
    mb = re.search(r"max_boxes_count\s*=\s*(\d+)", CUR)
    ml = re.search(r"max_labels_count\s*=\s*(\d+)", CUR)
    calls_b = blk.count("nBox := f_zpoBox(")
    check("ZS-13 object budget: per Zone at most 3 boxes (2 base parts or 1 whole + 1 boost) and 2 labels; "
          "maxZonesDraw max x 3 <= max_boxes_count and x 2 <= max_labels_count",
          bool(mz and mb and ml) and calls_b == 4 and blk.count("nLbl := f_zpoLabel(") == 2
          and int(mz.group(1)) * 3 <= int(mb.group(1)) and int(mz.group(1)) * 2 <= int(ml.group(1)),
          f"maxZones {mz and mz.group(1)} boxes {mb and mb.group(1)} labels {ml and ml.group(1)}")


# =============================================================================
# ZM : Python mirror
# =============================================================================
SR_WEAK, SR_MEDIUM, SR_STRONG, SR_VSTRONG = 1, 2, 3, 4
ST_ACTIVE, ST_SUPPORT, ST_RESIST, ST_BROKEN = 0, 1, 2, 3
NAMES = {1: "WEAK", 2: "MEDIUM", 3: "STRONG", 4: "VERY STRONG"}


class Cfg:
    def __init__(self, **kw):
        self.thrMedium, self.thrStrong, self.thrVStrong = 5.0, 10.0, 15.0
        self.confBonus2, self.confBonus3, self.confBonus4 = 1.0, 2.0, 3.0
        self.requireHtfForVStrong = True
        self.show = {1: False, 2: False, 3: True, 4: True}
        self.showState = {ST_SUPPORT: True, ST_RESIST: True, ST_BROKEN: False, ST_ACTIVE: False}
        self.showZones, self.showLabels, self.showScore, self.maxZonesDraw = True, True, False, 30
        self.trans = {1: 90, 2: 80, 3: 68, 4: 55}
        self.__dict__.update(kw)


def conf(c, n):
    return c.confBonus4 if n >= 4 else c.confBonus3 if n == 3 else c.confBonus2 if n == 2 else 0.0


def strength_of(c, score, htf):
    t = SR_WEAK if score < c.thrMedium else SR_MEDIUM if score < c.thrStrong else SR_STRONG if score < c.thrVStrong else SR_VSTRONG
    return SR_STRONG if t == SR_VSTRONG and c.requireHtfForVStrong and not htf else t


def zone(c, top, bot, baseSum, cat=1, htf=False, state=ST_SUPPORT, touch=0, slope=0.0, ma=0.0, flip=0.0):
    score = baseSum + slope + ma + flip + conf(c, cat)
    return dict(top=top, bottom=bot, baseSum=baseSum, catCount=cat, hasHtf=htf, state=state, touch=touch,
                slopeBonus=slope, maBonus=ma, flipBonus=flip, score=score, strength=strength_of(c, score, htf))


def fvg(slot, top, bot, closeT, alive=True):
    return dict(slot=slot, top=top, bot=bot, closeT=closeT, alive=alive)


class Slots:
    """15 FVG slots; get() raises on a negative index (Pine array.get(-1) = RE10045, Python would wrap)."""
    def __init__(self, fvgs):
        self.alive, self.top, self.bot, self.closeT = [False] * 15, [None] * 15, [None] * 15, [None] * 15
        for f in fvgs:
            s = f["slot"]
            self.alive[s], self.top[s], self.bot[s], self.closeT[s] = f["alive"], f["top"], f["bot"], f["closeT"]

    def get(self, arr, i):
        if i < 0 or i >= 15:
            raise IndexError(f"array.get({i})")
        return getattr(self, arr)[i]


def base_pts(s):
    return s // 5 + 1.0


def overlap(aT, aB, bT, bB):
    return min(aT, bT) > max(aB, bB)


def best_fvg(z, S):
    best = -1
    for s in range(15):
        if S.get("alive", s):
            if overlap(z["top"], z["bottom"], S.get("top", s), S.get("bot", s)):
                if best < 0:
                    best = s
                elif base_pts(s) > base_pts(best):
                    best = s
                elif base_pts(s) == base_pts(best):
                    if S.get("closeT", s) > S.get("closeT", best):
                        best = s
    return best


def zone_display(c, z, S):
    best = best_fvg(z, S)
    if best < 0:
        return z["score"], z["strength"]
    sc = z["baseSum"] + base_pts(best) + z["slopeBonus"] + z["maBonus"] + z["flipBonus"] + conf(c, z["catCount"] + 1)
    return sc, strength_of(c, sc, z["hasHtf"])


def fmt(v):
    return f"{v:.1f}".rstrip("0").rstrip(".")


def label_base(c, z):
    t = NAMES[z["strength"]]
    if z["strength"] >= SR_STRONG:
        t += f" | Touch {z['touch']}"
    if c.showScore:
        t += " | " + fmt(z["score"])
    return t


def label_boost(c, z, dStr, dScore):
    t = NAMES[dStr]
    if z["strength"] >= SR_STRONG:
        t += f" | Touch {z['touch']}"
    if c.showScore:
        t += " | " + fmt(dScore)
    return t


def draw_new(c, zones, S):
    """mirror of the ZPO block: [('box', kind, zoneIdx, top, bot, strength)], [('lbl', kind, zoneIdx, y, text)]."""
    boxes, labels, nZone = [], [], 0
    if c.showZones and zones:
        for k, z in enumerate(zones):
            if nZone >= c.maxZonesDraw:
                break
            if not c.showState[z["state"]]:
                continue
            dScore, dStr = zone_display(c, z, S)
            best = best_fvg(z, S)
            boosted = best >= 0 and dStr > z["strength"]
            oTop, oBot = z["top"], z["bottom"]
            if boosted:
                oTop, oBot = min(z["top"], S.get("top", best)), max(z["bottom"], S.get("bot", best))
            showBase = c.show[z["strength"]]
            showBoost = boosted and c.show[dStr]
            if not (showBase or showBoost):
                continue
            if showBase:
                if showBoost:
                    if z["top"] > oTop:
                        boxes.append(("box", "base", k, z["top"], oTop, z["strength"]))
                    if oBot > z["bottom"]:
                        boxes.append(("box", "base", k, oBot, z["bottom"], z["strength"]))
                else:
                    boxes.append(("box", "base", k, z["top"], z["bottom"], z["strength"]))
            if showBoost:
                boxes.append(("box", "boost", k, oTop, oBot, dStr))
            nZone += 1
            if c.showLabels:
                if showBoost:
                    labels.append(("lbl", "boost", k, oTop, label_boost(c, z, dStr, dScore)))
                if showBase and not (showBoost and oTop == z["top"]):
                    labels.append(("lbl", "base", k, z["top"], label_base(c, z)))
    return boxes, labels


def draw_old(c, zones, S):
    """mirror of the 11b2b4e draw pass (whole Zone at the Batch C display strength)."""
    boxes, labels = [], []
    if c.showZones and zones:
        for k, z in enumerate(zones):
            if len(boxes) >= c.maxZonesDraw:
                break
            dScore, dStr = zone_display(c, z, S)
            if not (c.show[dStr] and c.showState[z["state"]]):
                continue
            boxes.append(("box", "base", k, z["top"], z["bottom"], dStr))
            if c.showLabels:
                labels.append(("lbl", "base", k, z["top"], label_boost(c, z, dStr, dScore)))
    return boxes, labels


class Pool:
    """gBoxes / gLabels reuse: objects are set in order, new only past the end, surplus hidden."""
    def __init__(self):
        self.boxes, self.labels, self.created = [], [], 0

    def apply(self, boxes, labels):
        for i, b in enumerate(boxes):
            if i < len(self.boxes):
                self.boxes[i] = dict(v=b, hidden=False)
            else:
                self.boxes.append(dict(v=b, hidden=False)); self.created += 1
        for i in range(len(boxes), len(self.boxes)):
            self.boxes[i]["hidden"] = True
        for i, l in enumerate(labels):
            if i < len(self.labels):
                self.labels[i] = dict(v=l, hidden=False)
            else:
                self.labels.append(dict(v=l, hidden=False)); self.created += 1
        for i in range(len(labels), len(self.labels)):
            self.labels[i]["hidden"] = True

    def visible(self):
        return [b["v"] for b in self.boxes if not b["hidden"]], [l["v"] for l in self.labels if not l["hidden"]]


ALL = {1: True, 2: True, 3: True, 4: True}


def kinds(boxes):
    return [(b[1], b[3], b[4], NAMES[b[5]]) for b in boxes]


def gate_mirror():
    # thresholds where one FVG can lift WEAK -> STRONG / MEDIUM -> VERY STRONG (default thresholds cannot: max lift = 3 + 1)
    wide = dict(thrMedium=5.0, thrStrong=7.0, thrVStrong=9.0)
    cases = []
    # 1. WEAK -> STRONG (4H FVG overlaps the lower half)
    c = Cfg(show=dict(ALL), **wide)
    z = zone(c, 2010, 2000, 4.0)                                 # 4.0 WEAK -> 4 + 3 + conf2 1 = 8 STRONG
    S = Slots([fvg(10, 2004, 1990, 100)])
    b, l = draw_new(c, [z], S)
    cases.append(("ZM-01 WEAK -> STRONG: Zone stays WEAK, only [2000, 2004] is STRONG (base drawn outside the overlap)",
                  kinds(b) == [("base", 2010, 2004, "WEAK"), ("boost", 2004, 2000, "STRONG")]
                  and [x[1] for x in l] == ["boost", "base"], kinds(b)))
    # 2. MEDIUM -> STRONG (default thresholds)
    c = Cfg(show=dict(ALL))
    z = zone(c, 2010, 2000, 7.0)                                 # 7 MEDIUM -> 11 STRONG
    S = Slots([fvg(12, 2015, 2006, 100)])
    b, l = draw_new(c, [z], S)
    cases.append(("ZM-02 MEDIUM -> STRONG: overlap [2006, 2010] STRONG at the top, rest MEDIUM; labels at the same y -> "
                  "boost label only", kinds(b) == [("base", 2006, 2000, "MEDIUM"), ("boost", 2010, 2006, "STRONG")]
                  and [x[1] for x in l] == ["boost"], f"{kinds(b)} {l}"))
    # 3. STRONG -> VERY STRONG (default, HTF)
    c = Cfg(show=dict(ALL))
    z = zone(c, 2010, 2000, 12.0, htf=True)                      # 12 STRONG -> 16 VERY STRONG
    S = Slots([fvg(13, 2007, 2003, 100)])
    b, l = draw_new(c, [z], S)
    cases.append(("ZM-03 STRONG -> VERY STRONG: STRONG kept above and below, only [2003, 2007] VERY STRONG",
                  kinds(b) == [("base", 2010, 2007, "STRONG"), ("base", 2003, 2000, "STRONG"), ("boost", 2007, 2003, "VERY STRONG")]
                  and len(l) == 2, kinds(b)))
    # 4. MEDIUM -> VERY STRONG (wide thresholds, HTF)
    c = Cfg(show=dict(ALL), **wide)
    z = zone(c, 2010, 2000, 5.5, htf=True)                       # 5.5 MEDIUM -> 9.5 VERY STRONG
    S = Slots([fvg(14, 2008, 2002, 100)])
    b, l = draw_new(c, [z], S)
    cases.append(("ZM-04 MEDIUM -> VERY STRONG: overlap [2002, 2008] VERY STRONG, MEDIUM outside",
                  [k[3] for k in kinds(b)] == ["MEDIUM", "MEDIUM", "VERY STRONG"], kinds(b)))
    # 5. already STRONG / VERY STRONG; STRONG -> VS capped (no HTF)
    c = Cfg(show=dict(ALL))
    for nm, z, S in (("STRONG -> STRONG (15M +1)", zone(c, 2010, 2000, 10.0), Slots([fvg(0, 2005, 1995, 100)])),
                     ("VERY STRONG -> VERY STRONG", zone(c, 2010, 2000, 16.0, htf=True), Slots([fvg(10, 2005, 1995, 100)])),
                     ("STRONG -> VERY STRONG capped without HTF", zone(c, 2010, 2000, 12.0), Slots([fvg(10, 2005, 1995, 100)]))):
        b, l = draw_new(c, [z], S)
        cases.append((f"ZM-05 {nm}: whole Zone at its Engine strength, no boost box / label",
                      kinds(b) == [("base", 2010, 2000, NAMES[z["strength"]])] and [x[1] for x in l] == ["base"], kinds(b)))
    # 6 / 7. no overlap; edge contact only
    c = Cfg(show=dict(ALL))
    z = zone(c, 2010, 2000, 7.0)
    for nm, S in (("no FVG overlap", Slots([fvg(10, 2030, 2020, 100)])), ("edge contact only (FVG bottom = Zone top)",
                                                                           Slots([fvg(10, 2020, 2010, 100)]))):
        b, l = draw_new(c, [z], S)
        cases.append((f"ZM-06 {nm}: no boost, Zone as is", kinds(b) == [("base", 2010, 2000, "MEDIUM")], kinds(b)))
    # 8. multiple FVGs: 15M covers the top, 4H the bottom -> the 4H one only (no union); equal base -> newer close
    c = Cfg(show=dict(ALL))
    z = zone(c, 2010, 2000, 7.0)
    S = Slots([fvg(0, 2012, 2007, 300), fvg(10, 2003, 1995, 100)])
    b, l = draw_new(c, [z], S)
    S2 = Slots([fvg(10, 2003, 1995, 100), fvg(11, 2009, 2006, 200)])
    b2, _ = draw_new(c, [z], S2)
    cases.append(("ZM-07 multiple FVGs: one FVG only (max base 4H over 15M; same base -> newer close), its intersection "
                  "only, no union",
                  kinds(b) == [("base", 2010, 2003, "MEDIUM"), ("boost", 2003, 2000, "STRONG")]
                  and kinds(b2) == [("base", 2010, 2009, "MEDIUM"), ("base", 2006, 2000, "MEDIUM"), ("boost", 2009, 2006, "STRONG")],
                  f"{kinds(b)} {kinds(b2)}"))
    # 9. FVG filled / expired (alive false) -> boost disappears
    S = Slots([fvg(10, 2003, 1995, 100, alive=False)])
    b, l = draw_new(c, [z], S)
    cases.append(("ZM-08 FVG filled / expired (not alive): boost removed, Zone back to its Engine strength",
                  kinds(b) == [("base", 2010, 2000, "MEDIUM")], kinds(b)))
    # 10 / 12. all 16 Show Weak / Medium / Strong / Very Strong combinations
    ok_all, bad = True, []
    for flags in itertools.product((False, True), repeat=4):
        c = Cfg(show={1: flags[0], 2: flags[1], 3: flags[2], 4: flags[3]}, **wide)
        zs = [zone(c, 2010, 2000, 4.0), zone(c, 2040, 2030, 6.0, htf=True), zone(c, 2070, 2060, 7.5, htf=True),
              zone(c, 2100, 2090, 6.0)]
        S = Slots([fvg(10, 2005, 1990, 1), fvg(11, 2035, 2025, 2), fvg(12, 2066, 2064, 3)])
        b, l = draw_new(c, zs, S)
        for k, z in enumerate(zs):
            dScore, dStr = zone_display(c, z, S)
            boosted = best_fvg(z, S) >= 0 and dStr > z["strength"]
            exp_base = c.show[z["strength"]]
            exp_boost = boosted and c.show[dStr]
            got_base = any(x[1] == "base" and x[2] == k for x in b)
            got_boost = any(x[1] == "boost" and x[2] == k for x in b)
            whole = [x for x in b if x[1] == "base" and x[2] == k and x[3] == z["top"] and x[4] == z["bottom"]]
            if got_boost != exp_boost or (got_base != (exp_base and not (exp_boost and boosted and
                                                                          [x for x in b if x[1] == "boost" and x[2] == k][0][3:5] == (z["top"], z["bottom"])))) \
                    or (exp_base and not exp_boost and len(whole) != 1):
                ok_all = False
                bad.append((flags, k))
    cases.append(("ZM-09 all 16 Show Weak / Medium / Strong / Very Strong combinations: base drawn iff its Engine strength is "
                  "shown, boost iff boosted and the boosted strength is shown (also when the base is hidden), whole Zone when "
                  "no boost is drawn", ok_all, str(bad[:4])))
    c = Cfg(show={1: False, 2: False, 3: True, 4: True}, **wide)
    z = zone(c, 2010, 2000, 4.0)
    b, l = draw_new(c, [z], Slots([fvg(10, 2004, 1990, 1)]))
    cases.append(("ZM-10 Show Weak OFF: WEAK Zone hidden, its STRONG overlap still drawn (boost box + boost label only)",
                  kinds(b) == [("boost", 2004, 2000, "STRONG")] and [x[1] for x in l] == ["boost"], kinds(b)))
    # 11. Show Zones / Labels / Score
    c = Cfg(show=dict(ALL), showZones=False)
    b, l = draw_new(c, [zone(c, 2010, 2000, 7.0)], Slots([fvg(12, 2005, 1995, 1)]))
    c2 = Cfg(show=dict(ALL), showLabels=False)
    b2, l2 = draw_new(c2, [zone(c2, 2010, 2000, 7.0)], Slots([fvg(12, 2005, 1995, 1)]))
    c3 = Cfg(show=dict(ALL), showScore=True)
    z3 = zone(c3, 2010, 2000, 12.0, htf=True, touch=2)
    b3, l3 = draw_new(c3, [z3], Slots([fvg(12, 2005, 1995, 1)]))
    cases.append(("ZM-11 Show Zones OFF -> nothing; Show Labels OFF -> boxes only; Show Score ON -> base label = Engine "
                  "score, boost label = boosted score; Touch from the Engine strength on both",
                  b == [] and l == [] and len(b2) == 2 and l2 == []
                  and [x[4] for x in l3] == ["VERY STRONG | Touch 2 | 16", "STRONG | Touch 2 | 12"], str([x[4] for x in l3])))
    c = Cfg(show=dict(ALL), **wide)
    zw = zone(c, 2010, 2000, 4.0, touch=5)
    _, lw = draw_new(c, [zw], Slots([fvg(10, 2004, 1990, 1)]))
    cases.append(("ZM-12 WEAK -> STRONG boost label shows no Touch (Engine strength WEAK; FVG never adds Touch)",
                  [x[4] for x in lw] == ["STRONG", "WEAK"], str(lw)))
    # 13 / 14. pool reuse, Max Zones Drawn, priority, object bounds
    c = Cfg(show=dict(ALL), maxZonesDraw=3)
    zs = [zone(c, 2010 + 30 * i, 2000 + 30 * i, 12.0, htf=True) for i in range(6)]
    S = Slots([fvg(10 + i, 2007 + 30 * i, 2003 + 30 * i, i) for i in range(5)])
    b, l = draw_new(c, zs, S)
    cases.append(("ZM-13 Max Zones Drawn counts original Zones in draw order (boost rides with its Zone); <= 3 boxes and "
                  "<= 2 labels per Zone", sorted({x[2] for x in b}) == [0, 1, 2] and len(b) == 9 and len(l) == 6, str(len(b))))
    c = Cfg(maxZonesDraw=2)
    zs2 = [zone(c, 2010, 2000, 3.0), zone(c, 2040, 2030, 12.0), zone(c, 2070, 2060, 3.0), zone(c, 2100, 2090, 12.0)]
    b, l = draw_new(c, zs2, Slots([]))
    cases.append(("ZM-14 hidden Zones (nothing drawn) do not consume Max Zones Drawn", sorted({x[2] for x in b}) == [1, 3], str(b)))
    pool, ok_pool = Pool(), True
    c = Cfg(show=dict(ALL))
    seq = [(3, True), (6, True), (2, False), (6, True), (0, False)]
    for n, withF in seq:
        zs = [zone(c, 2010 + 30 * i, 2000 + 30 * i, 12.0, htf=True) for i in range(n)]
        S = Slots([fvg(10 + i, 2007 + 30 * i, 2003 + 30 * i, i) for i in range(min(n, 5))] if withF else [])
        b, l = draw_new(c, zs, S)
        pool.apply(b, l)
        ok_pool &= pool.visible() == (b, l)
    max_b = max(len(draw_new(c, [zone(c, 2010 + 30 * i, 2000 + 30 * i, 12.0, htf=True) for i in range(n)],
                             Slots([fvg(10 + i, 2007 + 30 * i, 2003 + 30 * i, i) for i in range(min(n, 5))] if f else []))[0])
                for n, f in seq)
    cases.append(("ZM-15 one gBoxes / gLabels pool reused across redraws: visible objects == this draw, surplus hidden, "
                  "boxes created == the largest draw (no growth on redraw)", ok_pool and len(pool.boxes) == max_b, str(len(pool.boxes))))
    c = Cfg(show=dict(ALL), maxZonesDraw=120)
    zs = [zone(c, 2010 + 30 * i, 2000 + 30 * i, 12.0, htf=True) for i in range(150)]
    S = Slots([fvg(10 + (i % 5), 2007 + 30 * i, 2003 + 30 * i, i) for i in range(5)])
    b, l = draw_new(c, zs, S)
    cases.append(("ZM-16 worst case maxZonesDraw = 120: boxes <= 360 <= 500, labels <= 240 <= 500",
                  len(b) <= 360 and len(l) <= 240 and len({x[2] for x in b}) == 120, f"{len(b)} {len(l)}"))
    # 15. reload / determinism and regression vs 11b2b4e
    c = Cfg(show=dict(ALL), **wide)
    zs = [zone(c, 2010 + 25 * i, 2000 + 25 * i, 3.0 + 2.5 * i, htf=i % 2 == 0) for i in range(6)]
    S = Slots([fvg(0, 2012, 2006, 1), fvg(10, 2033, 2020, 2), fvg(6, 2080, 2050, 3)])
    cases.append(("ZM-17 the draw is a pure function of (Engine Zones, FVG slots, inputs): same state -> identical objects "
                  "(reload gives the same picture for the same Engine / FVG state)", draw_new(c, zs, S) == draw_new(c, zs, S), ""))
    c = Cfg(show=dict(ALL))
    zs = [zone(c, 2010 + 25 * i, 2000 + 25 * i, 3.0 + 2.5 * i, htf=True, state=ST_SUPPORT if i % 2 else ST_RESIST) for i in range(7)]
    bn, ln = draw_new(c, zs, Slots([]))
    bo, lo = draw_old(c, zs, Slots([]))
    cases.append(("ZM-18 regression: without any FVG overlap the new draw == the 11b2b4e draw (boxes and labels)",
                  bn == bo and ln == lo, ""))
    # 17. eager evaluation: random states never index -1
    import random
    rnd, ok_idx = random.Random(7), True
    for _ in range(400):
        c = Cfg(show={s: rnd.random() < .5 for s in (1, 2, 3, 4)}, **(wide if rnd.random() < .5 else {}))
        zs = [zone(c, 2000 + 20 * i + 10, 2000 + 20 * i, rnd.uniform(0, 17), htf=rnd.random() < .5) for i in range(5)]
        fv = [fvg(s, 2000 + rnd.uniform(0, 100), 1990 + rnd.uniform(0, 100), rnd.randint(1, 9), rnd.random() < .7)
              for s in rnd.sample(range(15), rnd.randint(0, 15))]
        fv = [dict(f, top=max(f["top"], f["bot"]), bot=min(f["top"], f["bot"])) for f in fv]
        try:
            b, l = draw_new(c, zs, Slots(fv))
            for x in b:
                ok_idx &= x[3] > x[4] or x[1] == "base" and x[3] >= x[4]
        except IndexError:
            ok_idx = False
    cases.append(("ZM-19 400 random states (Pine eager evaluation, array.get(-1) raises): no invalid index, every box has "
                  "top > bottom", ok_idx, ""))
    for n, ok, d in cases:
        check(n, ok, d)


def main():
    for g in (gate_static, gate_mirror):
        try:
            g()
        except Exception as ex:
            import traceback
            check(f"{g.__name__} completed without error", False, traceback.format_exc()[-400:])
    w = max(len(n) for n, _, _ in RESULTS)
    fails = 0
    for n, ok, d in RESULTS:
        fails += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {n.ljust(w)}  {'' if ok else d}")
    print(f"\n{len(RESULTS) - fails}/{len(RESULTS)} passed  [PINE_NOT_VERIFIED: exact transform / static / draw mirror]")
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
