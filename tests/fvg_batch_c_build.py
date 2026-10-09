"""FVG Batch C — exact transform of ZoneVisualPractical.pine @ 90f29a7 (Batch A + B + RE10045 fix).

Batch C (display-only mutual bonus) needs the FVG state inside the EXISTING Zone draw loop. Pine only lets code
reference declarations above it, so:

  1. the Batch A block is MOVED (byte-identical content) from the end of the file to just before the DISPLAY
     section banner (after zn.update; Batch A never reads anything from the display section),
  2. a new Batch C block (score / strength functions) is inserted just before the existing Zone draw loop,
  3. the existing Zone draw loop gets exactly C_PROD_EDITS (display Strength / Score instead of the Engine values;
     identical output when no FVG overlaps the Zone),
  4. the Batch B block gets exactly C_B_EDITS (FVG score / strength from Batch C; detail label breakdown).

Everything else is unchanged. v4 -> exact text; fixtures assert current == c_transform(90f29a7) and the inverse.
"""
C_BASE_REV = "90f29a7"

A_BEGIN, A_END = "// ==== FVG Batch A (begin) ", "// ==== FVG Batch A (end) "
B_BEGIN, B_END = "// ==== FVG Batch B (begin) ", "// ==== FVG Batch B (end) "
C_BEGIN, C_END = "// ==== FVG Batch C (begin) ", "// ==== FVG Batch C (end) "

DISPLAY_BANNER = "// ============================================================================\n// DISPLAY\n"
DRAW_ANCHOR = "if barstate.islast and is5mChart\n    int nBox = 0\n"

C_BLOCK = """// ==== FVG Batch C (begin) =====================================================
//  FVG と既存 Zone の表示専用 相互加点 (FVG実装仕様書 v1.0 + A01 + A02 / Batch C)。
//  ・Engine の Zone (zn.zoneAt) と Batch A の保存 FVG (gFvg*) を読むだけ。どちらにも書き込まない。
//    z.score / z.strength / Touch / Break / Flip / Track / 上下限 は不変。
//  ・既存 Zone : 重なる有効 FVG のうち基本点 (15M 1 / 1H 2 / 4H 3) 最大の1件だけ。同点は形成確定時刻が新しい方。
//      重なり無し -> z.score / z.strength そのまま
//      重なり有り -> baseSum + FVG基本点 + slope + maBonus + flipBonus + Confluence(catCount + 1)、HTF = z.hasHtf
//  ・FVG      : 重なる SUPPORT / RESISTANCE / ACTIVE Zone (BROKEN 除外) のうち baseSum 最大の1件だけ。
//      同点: baseSum -> catCount -> hasHtf -> Zone index の小さい方
//      重なり無し -> 基本点、HTF = false / 有り -> 基本点 + baseSum + Confluence(1 + catCount)、HTF = その Zone の hasHtf
//  ・表示フィルターは計算に使わない (全 Zone / 全有効 FVG が対象)。結果の再転送・再帰なし。
//  ・Pine v5 は and / or の両辺を評価するため、-1 判定と array.get / zoneAt を同じ式に書かない。
// Engine f_confluenceBonus (ZoneEnginePractical.pine 486-487) と同じ式・同じ入力
f_fvcConf(int catCount) =>
    catCount >= 4 ? confBonus4 : catCount == 3 ? confBonus3 : catCount == 2 ? confBonus2 : 0.0

// Engine f_strengthOf (ZoneEnginePractical.pine 470-474) と同じ閾値・HTF 要件・降格規則
f_fvcStrengthOf(float score, bool hasHtf) =>
    int t = score < thrMedium ? SR_WEAK : score < thrStrong ? SR_MEDIUM : score < thrVStrong ? SR_STRONG : SR_VSTRONG
    if t == SR_VSTRONG and requireHtfForVStrong and not hasHtf
        t := SR_STRONG
    t

f_fvcShowByStrength(int s) =>
    s == SR_VSTRONG ? showVStrong : s == SR_STRONG ? showStrong : s == SR_MEDIUM ? showMedium : showWeak

// FVG 基本点: 15M (slot 0-4) = 1 / 1H (5-9) = 2 / 4H (10-14) = 3
f_fvcBase(int slot) =>
    math.floor(slot / FVG_SLOTS_PER_TF) + 1.0

// 重複幅 > 0 のときだけ重なりとする (境界接触 = 0 は加点しない)
f_fvcOverlap(float aTop, float aBot, float bTop, float bBot) =>
    math.min(aTop, bTop) > math.max(aBot, bBot)

// 既存 Zone の表示 Score / Strength
f_fvcZoneDisplay(zn.Zone z) =>
    int best = -1
    for s = 0 to 3 * FVG_SLOTS_PER_TF - 1
        if array.get(gFvgAlive, s)
            if f_fvcOverlap(z.top, z.bottom, array.get(gFvgTop, s), array.get(gFvgBot, s))
                if best < 0
                    best := s
                else if f_fvcBase(s) > f_fvcBase(best)
                    best := s
                else if f_fvcBase(s) == f_fvcBase(best)
                    if array.get(gFvgCloseT, s) > array.get(gFvgCloseT, best)
                        best := s
    float dScore = z.score
    int   dStr   = z.strength
    if best >= 0
        dScore := z.baseSum + f_fvcBase(best) + z.slopeBonus + z.maBonus + z.flipBonus + f_fvcConf(z.catCount + 1)
        dStr   := f_fvcStrengthOf(dScore, z.hasHtf)
    [dScore, dStr]

// FVG 独立 Zone の表示 Score / Strength / 採用 Zone の baseSum / Confluence Bonus
f_fvcFvgDisplay(int slot) =>
    float fb  = f_fvcBase(slot)
    float top = array.get(gFvgTop, slot)
    float bot = array.get(gFvgBot, slot)
    int   n   = zn.zoneCount(zoneEng)
    int   best = -1
    if n > 0
        for i = 0 to n - 1
            zn.Zone z = zn.zoneAt(zoneEng, i)
            if z.state != ST_BROKEN
                if f_fvcOverlap(z.top, z.bottom, top, bot)
                    if best < 0
                        best := i
                    else
                        zn.Zone bz = zn.zoneAt(zoneEng, best)
                        if z.baseSum > bz.baseSum
                            best := i
                        else if z.baseSum == bz.baseSum
                            if z.catCount > bz.catCount
                                best := i
                            else if z.catCount == bz.catCount
                                if z.hasHtf and not bz.hasHtf
                                    best := i
    float sc  = fb
    bool  htf = false
    float zb  = na
    float cf  = 0.0
    if best >= 0
        zn.Zone sz = zn.zoneAt(zoneEng, best)
        zb  := sz.baseSum
        cf  := f_fvcConf(1 + sz.catCount)
        sc  := fb + sz.baseSum + cf
        htf := sz.hasHtf
    [sc, f_fvcStrengthOf(sc, htf), zb, cf]

// 既存 Zone ラベル: Strength 名と Score は表示値、Touch の表示可否は Engine の元 Strength
f_fvcLabelText(zn.Zone z, int dStr, float dScore) =>
    string txt = zn.strengthName(dStr)
    if z.strength >= SR_STRONG
        txt := txt + " | Touch " + str.tostring(z.touchCount)
    if showScore
        txt := txt + " | " + f_num(dScore, "#.#")
    if showDetailLbl
        txt := txt + "\\n" + zn.sourceText(z.srcMask, zoneCfg)
    txt
// ==== FVG Batch C (end) =======================================================
"""

# existing Zone draw loop: display Strength / Score (identical to the Engine values when no FVG overlaps)
C_PROD_EDITS = [
    ("                zn.Zone z = zn.zoneAt(zoneEng, array.get(ord, k))\n"
     "                if not f_showZone(z)\n"
     "                    continue\n",
     "                zn.Zone z = zn.zoneAt(zoneEng, array.get(ord, k))\n"
     "                [dScore, dStr] = f_fvcZoneDisplay(z)\n"
     "                if not (f_fvcShowByStrength(dStr) and f_showByState(z))\n"
     "                    continue\n"),
    ("                int   tr  = f_zoneTransp(z.strength)\n",
     "                int   tr  = f_zoneTransp(dStr)\n"),
    ("                int   bw  = z.strength >= SR_STRONG ? 2 : 1\n",
     "                int   bw  = dStr >= SR_STRONG ? 2 : 1\n"),
    ("                    string txt = f_labelText(z)\n",
     "                    string txt = f_fvcLabelText(z, dStr, dScore)\n"),
]

# Batch B block: score / strength per FVG from Batch C; detail label breakdown
C_B_EDITS = [
    ("//  ・相互加点なし (Batch C)。表示 Score = 基本点 (15M 1 / 1H 2 / 4H 3)、HTF 条件 = false。\n",
     "//  ・表示 Score / Strength は Batch C (f_fvcFvgDisplay: 基本点 + 採用 Zone の baseSum + Confluence)。\n"),
    ("// Engine f_strengthOf (ZoneEnginePractical.pine 470-474) と同じ閾値・HTF 要件・降格規則\n"
     "f_fvgStrengthOf(float score, bool hasHtf) =>\n"
     "    int t = score < thrMedium ? SR_WEAK : score < thrStrong ? SR_MEDIUM : score < thrVStrong ? SR_STRONG : SR_VSTRONG\n"
     "    if t == SR_VSTRONG and requireHtfForVStrong and not hasHtf\n"
     "        t := SR_STRONG\n"
     "    t\n"
     "\n", ""),
    ("f_fvgLabelText(int s, int tfIdx, int dir, float score, int closeT, float top, float bot) =>\n",
     "f_fvgLabelText(int s, int tfIdx, int dir, float score, int closeT, float top, float bot, float zoneBase, float conf) =>\n"),
    ("             + \" · base \" + f_num(score, \"#.#\")\n",
     "             + \" · base \" + f_num(tfIdx + 1.0, \"#.#\")\n"
     "             + \" · zone \" + (na(zoneBase) ? \"-\" : f_num(zoneBase, \"#.#\"))\n"
     "             + \" · conf \" + f_num(conf, \"#.#\")\n"),
    ("            float fvgScore = tf + 1.0\n"
     "            int   fs = f_fvgStrengthOf(fvgScore, false)\n", ""),
    ("                int dir = array.get(gFvgDir, pick)\n",
     "                int dir = array.get(gFvgDir, pick)\n"
     "                [fvgScore, fs, fZoneBase, fConf] = f_fvcFvgDisplay(pick)\n"),
    ("f_fvgLabelText(fs, tf, dir, fvgScore, array.get(gFvgCloseT, pick), top, bot)",
     "f_fvgLabelText(fs, tf, dir, fvgScore, array.get(gFvgCloseT, pick), top, bot, fZoneBase, fConf)"),
]


def _rep(t, a, b):
    assert t.count(a) == 1, ("transform anchor not unique", a[:80], t.count(a))
    return t.replace(a, b)


def block(src, begin, end):
    i = src.index(begin)
    k = src.index("\n", src.index(end)) + 1
    return i, k, src[i:k]


def c_transform(src):
    """90f29a7 -> Batch C file."""
    t = src
    # 1. move the Batch A block (content unchanged) before the DISPLAY banner
    i, k, a_blk = block(t, A_BEGIN, A_END)
    assert t[i - 2:i] == "\n\n"
    t = t[:i - 1] + t[k:]
    j = t.index("\n" + DISPLAY_BANNER) + 1
    assert t[j - 2:j] == "\n\n"
    t = t[:j] + a_blk + "\n" + t[j:]
    # 2. Batch C block before the existing Zone draw loop
    j = t.index(DRAW_ANCHOR)
    assert t[j - 2:j] == "\n\n"
    t = t[:j] + C_BLOCK + "\n" + t[j:]
    # 3. existing draw loop edits (outside every FVG block)
    for a, b in C_PROD_EDITS:
        t = _rep(t, a, b)
    # 4. Batch B edits
    bi, bk, b_blk = block(t, B_BEGIN, B_END)
    nb = b_blk
    for a, b in C_B_EDITS:
        nb = _rep(nb, a, b)
    t = t[:bi] + nb + t[bk:]
    return t


def revert_prod_edits(prod):
    """production part (all FVG blocks removed) -> d240ec0 text (inverse of C_PROD_EDITS; each must occur once)."""
    t = prod
    for a, b in C_PROD_EDITS:
        assert t.count(b) == 1, ("prod edit missing / duplicated", b[:80], t.count(b))
        t = t.replace(b, a)
    return t


def apply_prod_edits(base):
    t = base
    for a, b in C_PROD_EDITS:
        t = _rep(t, a, b)
    return t
