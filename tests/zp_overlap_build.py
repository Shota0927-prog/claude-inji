"""ZONE-P FVG overlap-only boost display: exact transform of ZoneVisualPractical.pine @ 11b2b4e.

  1. the existing-Zone draw pass (`if barstate.islast and is5mChart` ... surplus hide) is replaced by one marked
     block (ZPO_BEGIN / ZPO_END):
       - original Zone  : whole [z.bottom, z.top] with the Engine strength / score (label = f_labelText)
       - FVG boost      : only the intersection with the Batch C best FVG, drawn with the boosted strength, and only
                          when the boosted strength > the Engine strength (label = f_fvcLabelText)
       - both visible   : the original Zone is drawn as the parts outside the intersection (= the intersection is
                          overwritten by the boost, no semi-transparent stacking)
  2. the FVG Batch B block (independent FVG boxes / labels) is removed (the FVG is drawn by another indicator).
Engine / Library, FVG Batch A (detection / storage / fill / expiry), Batch C (score formula / selection), NR-S1, NR-A1,
MA, Break, Track / Touch / Break / Flip and the zone geometry are untouched.
"""
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZPO_BASE_REV = "11b2b4e"
ZPO_BEGIN, ZPO_END = "// ==== Zone FVG Overlap Display (begin) ", "// ==== Zone FVG Overlap Display (end) "
B_BEGIN, B_END = "// ==== FVG Batch B (begin) ", "// ==== FVG Batch B (end) "
DRAW_HEAD = "if barstate.islast and is5mChart\n    int nBox = 0\n    int nLbl = 0\n"
DRAW_TAIL_ANCHOR = "\n\n// ---- MA Source の可視化"

ZPO_BLOCK = """// ==== Zone FVG Overlap Display (begin) ========================================
//  既存 Zone の FVG 昇格を「FVG と重なっている価格帯だけ」に表示する (表示専用)。
//  ・Engine の Zone (z.top / z.bottom / score / strength / Touch / Track) と FVG 保存状態 (gFvg*) は読むだけ。
//  ・元 Zone   : Engine の Strength / Score で Zone 全体 [z.bottom, z.top]。
//  ・昇格領域  : Batch C の最良 FVG 1件 (f_fvcZoneDisplay と同じ選択) と Zone の交差範囲
//                [max(z.bottom, fvg.bottom), min(z.top, fvg.top)] を、加点後 Strength > 元 Strength のときだけ
//                加点後 Strength で描く。加点式 / 選択順は Batch C のまま (f_fvcZoneDisplay)。
//  ・両方表示するときは元 Zone を交差範囲の外側 (上 / 下) に分けて描く = 交差範囲は昇格表示で上書き。
//  ・Strength フィルターは元 / 昇格それぞれに適用 (元が非表示でも昇格が表示対象なら昇格だけ描く)。
//    State フィルターは Zone 単位。Max Zones Drawn は元 Zone 単位 (昇格は付随表示、何も描かない Zone は数えない)。
//  ・Label : 元 = Engine Strength / Score (f_labelText、Touch は Engine Strength 基準)、
//            昇格 = 加点後 Strength / Score (f_fvcLabelText)。1 Zone につき元 1 個・昇格 1 個まで。
//            同じ位置 (交差上端 = Zone 上端) に重なるときは昇格 Label だけ。
//  ・box / label は gBoxes / gLabels の1プールを描画順に再利用 (1 Zone 最大 box 3 / label 2)。
//  ・Pine v5 は and / or の両辺を評価するため、-1 判定と array.get を同じ式に書かない。

// Batch C f_fvcZoneDisplay と同じ最良 FVG の slot (重なり無しは -1)
f_zpoBestFvg(zn.Zone z) =>
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
    best

// pool の idx 番目の box を設定 (足りなければ new)。戻り値 = 次の idx
f_zpoBox(int idx, int xL, int xR, float top, float bot, color bg, color bd, int bw, string bs) =>
    if idx < array.size(gBoxes)
        box b = array.get(gBoxes, idx)
        box.set_lefttop(b, xL, top)
        box.set_rightbottom(b, xR, bot)
        box.set_bgcolor(b, bg)
        box.set_border_color(b, bd)
        box.set_border_width(b, bw)
        box.set_border_style(b, bs)
    else
        array.push(gBoxes, box.new(left = xL, top = top, right = xR, bottom = bot,
             bgcolor = bg, border_color = bd, border_width = bw, border_style = bs,
             xloc = xloc.bar_index))
    idx + 1

// pool の idx 番目の label を設定 (足りなければ new)。戻り値 = 次の idx
f_zpoLabel(int idx, int x, float y, string txt, color lc) =>
    if idx < array.size(gLabels)
        label lb = array.get(gLabels, idx)
        label.set_xy(lb, x, y)
        label.set_text(lb, txt)
        label.set_color(lb, lc)
        label.set_textcolor(lb, color.white)
    else
        array.push(gLabels, label.new(x = x, y = y, text = txt, xloc = xloc.bar_index,
             style = label.style_label_left, color = lc, textcolor = color.white, size = size.small))
    idx + 1

if barstate.islast and is5mChart
    int nBox  = 0
    int nLbl  = 0
    int nZone = 0
    if showZones and zn.zoneCount(zoneEng) > 0
        // 全Zoneを距離順で取得し、何かを描く Zone だけを maxZonesDraw 件まで描く
        array<int> ord = zn.drawOrder(zoneEng, zn.zoneCount(zoneEng))
        int xL = bar_index - zoneLeftBars
        int xR = bar_index + zoneRightBars
        if array.size(ord) > 0
            for k = 0 to array.size(ord) - 1
                if nZone >= maxZonesDraw
                    break
                zn.Zone z = zn.zoneAt(zoneEng, array.get(ord, k))
                if not f_showByState(z)
                    continue
                [dScore, dStr] = f_fvcZoneDisplay(z)
                int  best    = f_zpoBestFvg(z)
                bool boosted = best >= 0 and dStr > z.strength
                float oTop = z.top
                float oBot = z.bottom
                if boosted
                    oTop := math.min(z.top, array.get(gFvgTop, best))
                    oBot := math.max(z.bottom, array.get(gFvgBot, best))
                bool showBase  = f_showByStrength(z)
                bool showBoost = boosted and f_fvcShowByStrength(dStr)
                if not (showBase or showBoost)
                    continue
                color  bc = f_zoneColor(z.state)
                string bs = z.state == ST_BROKEN ? line.style_dashed : line.style_solid
                if showBase
                    int   trB = f_zoneTransp(z.strength)
                    color bgB = color.new(bc, trB)
                    color bdB = color.new(bc, math.max(trB - 30, 0))
                    int   bwB = z.strength >= SR_STRONG ? 2 : 1
                    if showBoost
                        // 交差範囲の外側だけ (交差範囲は下の昇格 box が受け持つ)
                        if z.top > oTop
                            nBox := f_zpoBox(nBox, xL, xR, z.top, oTop, bgB, bdB, bwB, bs)
                        if oBot > z.bottom
                            nBox := f_zpoBox(nBox, xL, xR, oBot, z.bottom, bgB, bdB, bwB, bs)
                    else
                        nBox := f_zpoBox(nBox, xL, xR, z.top, z.bottom, bgB, bdB, bwB, bs)
                if showBoost
                    int   trU = f_zoneTransp(dStr)
                    color bgU = color.new(bc, trU)
                    color bdU = color.new(bc, math.max(trU - 30, 0))
                    int   bwU = dStr >= SR_STRONG ? 2 : 1
                    nBox := f_zpoBox(nBox, xL, xR, oTop, oBot, bgU, bdU, bwU, bs)
                nZone += 1

                if showLabels
                    color lc = color.new(bc, 20)
                    if showBoost
                        nLbl := f_zpoLabel(nLbl, xR, oTop, f_fvcLabelText(z, dStr, dScore), lc)
                    if showBase and not (showBoost and oTop == z.top)
                        nLbl := f_zpoLabel(nLbl, xR, z.top, f_labelText(z), lc)

    // 余剰 object は delete せず非表示化 (次回 Zone数が増えた時に再利用する)
    if nBox < array.size(gBoxes)
        for k = nBox to array.size(gBoxes) - 1
            box b = array.get(gBoxes, k)
            box.set_bgcolor(b, C_HIDDEN)
            box.set_border_color(b, C_HIDDEN)
    if nLbl < array.size(gLabels)
        for k = nLbl to array.size(gLabels) - 1
            label lb = array.get(gLabels, k)
            label.set_text(lb, "")
            label.set_color(lb, C_HIDDEN)
            label.set_textcolor(lb, C_HIDDEN)
// ==== Zone FVG Overlap Display (end) ==========================================
"""


def git_show(rev, path="ZoneVisualPractical.pine"):
    return subprocess.run(["git", "-C", ROOT, "show", f"{rev}:{path}"], capture_output=True, text=True).stdout


def base_parts(base):
    """(old draw pass text, Batch B section text incl. its leading newline) taken from the base file."""
    assert base.count(DRAW_HEAD) == 1 and base.count(DRAW_TAIL_ANCHOR) == 1
    i = base.index(DRAW_HEAD)
    j = base.index(DRAW_TAIL_ANCHOR) + 1
    assert i < j and base[i - 2:i] == "\n\n"
    old_draw = base[i:j]
    assert base.count(B_BEGIN) == 1 and base.count(B_END) == 1
    b = base.index(B_BEGIN)
    assert base[b - 2:b] == "\n\n"
    e = base.index("\n", base.index(B_END)) + 1
    assert e == len(base), "Batch B must be the last block of the file"
    return old_draw, base[b - 1:]


def zpo_transform(base):
    """11b2b4e -> ZONE-P overlap-only boost display."""
    old_draw, b_sec = base_parts(base)
    t = base.replace(old_draw, ZPO_BLOCK)
    assert t.endswith(b_sec)
    return t[:-len(b_sec)]


def strip_zpo(src, base=None):
    """current file -> 11b2b4e text (the ZPO block back to the original draw pass, Batch B re-appended).
    None when the ZPO block is not exactly one well-formed ZPO_BLOCK or Batch B is still present."""
    if src is None:
        return None
    base = base if base is not None else git_show(ZPO_BASE_REV)
    old_draw, b_sec = base_parts(base)
    if src.count(ZPO_BLOCK) != 1 or src.count(ZPO_BEGIN) != 1 or src.count(ZPO_END) != 1 or B_BEGIN in src or B_END in src:
        return None
    return src.replace(ZPO_BLOCK, old_draw) + b_sec
