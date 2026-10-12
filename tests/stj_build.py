"""STJ-1 — ZoneStrategyUSDJPY.pine: OANDA:USDJPY 5M entry strategy (A / B / C / D of ZoneStrategyXAU).

Deterministic build, same pipeline as ZoneStrategyXAU but starting from the USDJPY Visual:
  ZoneVisualUSDJPY text (jpy_build.build())
    -> st1_build.st_transform   (computation part kept byte for byte, display removed, Zone evaluation block)
    -> st2_build.st2_transform  (A / B / C orders)
    -> st3_build.st3_transform  (D 1M BOS, session, opposite-zone TP, breakeven; current XAU defaults)
    -> EDITS                    (identity / header, yen SL Buffer and Breakeven Trigger, drop the display-only
                                 label helper f_jpyGeom)
strip_stj() reverses EDITS exactly (fixture stj_sim). Zone calculation = ZONE-JPY, order logic = ZONE-ST.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jpy_build as jb     # noqa: E402
import st1_build as tb     # noqa: E402
import st2_build as s2     # noqa: E402
import st3_build as s3     # noqa: E402

ROOT = jb.ROOT
STJ_PATH = "ZoneStrategyUSDJPY.pine"

EDITS = [
    ("//  Zone Strategy XAU  —  ZONE-P (ZoneVisualPractical) の Zone 判定をそのまま使う XAUUSD 5分足 Strategy\n",
     "//  Zone Strategy USDJPY  —  ZONE-JPY (ZoneVisualUSDJPY) の Zone 判定をそのまま使う OANDA:USDJPY 5分足 Strategy\n"
     "//  (生成: tests/stj_build.py。Zone 計算は ZONE-JPY、注文処理は ZONE-ST (ZoneStrategyXAU) と同じ式。価格差は円)\n"),
    ('     title                  = "Zone Strategy XAU",\n     shorttitle             = "ZONE-ST",\n',
     '     title                  = "Zone Strategy USDJPY",\n     shorttitle             = "ZONE-ST-JPY",\n'),
    ('\n// Zone の上下限と最終的な幅 (円、小数 3 桁)\n'
     'f_jpyGeom(zn.Zone z) =>\n'
     '    f_num(z.top, "#.000") + " - " + f_num(z.bottom, "#.000") + " | W " + f_num(z.top - z.bottom, "0.000")\n',
     ''),
    ('stBuffer = input.float(3.0, "SL Buffer ($)", minval = 0.0, step = 0.5, group = G_ST)\n',
     'stBuffer = input.float(0.05, "[暫定] SL Buffer (円)", minval = 0.0, step = 0.005, group = G_ST)\n'),
    ('stBEDist = input.float(10.0, "Breakeven Trigger ($)", minval = 0.0, step = 0.5, group = G_STT)\n',
     'stBEDist = input.float(0.15, "[暫定] Breakeven Trigger (円)", minval = 0.0, step = 0.005, group = G_STT)\n'),
]


PROV_FUNCS = """var array<float> stTpUpPrev = array.new_float()     // 直前の確定時の TP 用 Zone 端 (仮評価の RR 事前判定用)
var array<float> stTpDnPrev = array.new_float()

// ---- 仮 / 確定アラート (USDJPY) ----------------------------------------------------------------
//  ゴールド版 PracticalZoneStrategy_LONG.pine (P10) と同じ意味:
//  ・確定: 実際に strategy.entry を出した branch (5分足確定時の発注成立) で 1 回。約定通知ではない。alert.freq_all。
//  ・仮  : 確定 Entry 条件から「確定足であること」だけを外した判定。形成中の 5分足 (未確定 tick) だけで評価し、
//          1 本の 5分足につき最大 1 回 (varip)。確定時に不成立になることがある。alert.freq_once_per_bar。
//          仮の送信済み状態 (varip) と確定の発注は互いに参照しない (仮を出しても確定は止まらない)。
//  本文は送信するときだけ組み立てる。
f_stAlertMsg(string kind, int side, float ePx, float sl) =>
    "【" + kind + " " + (side == 1 ? "LONG" : "SHORT") + "】" +
     "\\n" + syminfo.tickerid +
     "\\nMode: " + stMode +
     "\\nE: " + f_num(ePx, "#.000") + (stModeA ? " (指値)" : " (参考。次足始値で成行)") +
     "\\nSL: " + f_num(sl, "#.000") +
     (kind == "仮" ? "\\n※未確定: 5分足の確定時に不成立になる場合あり" : "\\nTP: 約定確認後に設定")

// 仮評価 (読み取り専用)。確定時の新規 Entry 判定 (4) から「確定足であること」だけを外したもの。
//  ・候補 Zone: 直前の確定時の一覧 (stPrev)。足 t の更新後の Zone / Track は未確定なので使わない
//  ・終値 / 高値 / 安値: 形成中の現在値。C のパターンも形成中の足で判定
//  ・D: 待機 (stWaits) の値をローカルに写し、この 5分足の未処理の確定 1分足 (期間が終わっていない最後の 1分足は除く) で
//       接触 / BOS を試算する。待機・候補・注文状態・処理済み時刻は一切書き換えない
//  ・RR 事前判定: 直前の確定時の TP 用 Zone 端と、参照価格 (A: 指値 / B, C, D: 現在値)
//  戻り値: [方向 (0 = なし), 参照価格, SL]
f_stProvEval() =>
    int   bkL = -1
    int   bkS = -1
    float bpL = na
    float bpS = na
    int   bsL = 0
    int   bsS = 0
    float bcL = na
    float bcS = na
    float bdL = na
    float bdS = na
    int   btL = -1
    int   btS = -1
    int   m   = array.size(stPrev)
    // 確定済みの 1分足だけ: 後ろに次の 1分足がある要素は確定。最後の要素は 1分の期間が終わっていれば確定
    // (time + 60000 <= timenow)。終わっていなければ形成中として除く (追加 request なし、既存の time 配列を使う)
    int   nb  = 0
    if not na(m1t)
        int sz = array.size(m1t)
        nb := sz
        if sz > 0
            if array.get(m1t, sz - 1) + 60000 > timenow
                nb := sz - 1
    if m > 0
        for k = 0 to m - 1
            StCand c = array.get(stPrev, k)
            bool dirOK = c.side == 1 ? stLongOK : stShortOK
            if dirOK and not map.contains(stUsed, c.track)
                bool  ok  = false
                float px  = na
                int   aS  = 0
                float aSc = na
                float d   = na
                if stModeA
                    px := c.side == 1 ? (c.sZ >= SR_STRONG ? c.top : c.bTop) : (c.sZ >= SR_STRONG ? c.bot : c.bBot)
                    [s1, sc1] = f_stAdopt(c, px, px)
                    aS  := s1
                    aSc := sc1
                    d   := math.abs(close - px)
                    ok  := (c.side == 1 ? close > c.top : close < c.bot) and aS >= SR_STRONG
                else if stModeD
                    bool  armed = false
                    float ext   = na
                    float run   = na
                    float lvl   = na
                    int   cnt   = 0
                    int   nw    = array.size(stWaits)
                    if nw > 0
                        for w = 0 to nw - 1
                            StWait x = array.get(stWaits, w)
                            if x.c.track == c.track
                                armed := true
                                ext   := x.ext
                                run   := x.run
                                lvl   := x.lvl
                                cnt   := x.cnt
                                aS    := x.aS
                                aSc   := x.aSc
                    bool  bos = false
                    float pc  = m1PrevC
                    if nb > 0
                        for j = 0 to nb - 1
                            int tj = array.get(m1t, j)
                            if not bos and (na(m1LastT) or tj > m1LastT)
                                float h  = array.get(m1h, j)
                                float l  = array.get(m1l, j)
                                float cl = array.get(m1c, j)
                                if armed
                                    cnt := cnt + 1
                                    if c.side == 1 ? cl > lvl : cl < lvl
                                        bos := true
                                    else
                                        run := c.side == 1 ? math.max(run, h) : math.min(run, l)
                                        if c.side == 1 ? l < ext : h > ext
                                            ext := c.side == 1 ? l : h
                                            lvl := run
                                        if cnt >= stDWait
                                            armed := false
                                if not armed and not bos and l <= c.top and h >= c.bot and (c.side == 1 ? pc > c.top : pc < c.bot)
                                    [wS, wSc] = f_stAdopt(c, math.max(l, c.bot), math.min(h, c.top))
                                    if wS >= SR_STRONG
                                        armed := true
                                        ext   := c.side == 1 ? l : h
                                        run   := c.side == 1 ? h : l
                                        lvl   := run
                                        cnt   := 0
                                        aS    := wS
                                        aSc   := wSc
                                pc := cl
                    d  := math.abs(close - (c.side == 1 ? c.top : c.bot))
                    ok := bos and (c.side == 1 ? close > c.top : close < c.bot)
                else
                    [s2, sc2] = f_stAdopt(c, math.max(low, c.bot), math.min(high, c.top))
                    aS  := s2
                    aSc := sc2
                    d   := math.abs(close - (c.side == 1 ? c.top : c.bot))
                    ok  := low <= c.top and high >= c.bot and (c.side == 1 ? close > c.top : close < c.bot) and aS >= SR_STRONG and (not stModeC or (c.side == 1 ? stPatL : stPatS))
                if ok and c.side == 1
                    bool take = bkL < 0
                    if not take
                        take := f_stBetter(stModeA, aS, aSc, d, c.track, bsL, bcL, bdL, btL)
                    if take
                        bkL := k
                        bpL := px
                        bsL := aS
                        bcL := aSc
                        bdL := d
                        btL := c.track
                if ok and c.side == -1
                    bool take = bkS < 0
                    if not take
                        take := f_stBetter(stModeA, aS, aSc, d, c.track, bsS, bcS, bdS, btS)
                    if take
                        bkS := k
                        bpS := px
                        bsS := aS
                        bcS := aSc
                        bdS := d
                        btS := c.track
    int side = 0
    if bkL >= 0 and bkS >= 0
        if stModeA and bdL != bdS
            side := bdL < bdS ? 1 : -1
    else if bkL >= 0
        side := 1
    else if bkS >= 0
        side := -1
    float ePx = na
    float sl  = na
    if side != 0
        StCand c = array.get(stPrev, side == 1 ? bkL : bkS)
        ePx := stModeA ? (side == 1 ? bpL : bpS) : close
        sl  := side == 1 ? c.bot - stBuffer : c.top + stBuffer
        [skipRef, tpRef] = f_stTp(side, ePx, sl, f_stNearest(side == 1 ? stTpUpPrev : stTpDnPrev, side, ePx))
        if skipRef
            side := 0
    [side, ePx, sl]

"""

PROV_BLOCK = """
// ---- 仮アラート: 形成中の 5分足 (未確定 tick) だけ。Engine / Zone / FVG / BOS 待機 / 注文の状態は変えない ----
//  ・新規 Entry と同じ制限: 注文・保有なし (直前の確定時の状態)、時間帯、Direction、同一 Track 1 回、Zone 資格
//  ・1 本の 5分足につき最大 1 回 (varip stProvBar。確定アラートとは別の状態)。送信後は同じ足で再評価しない
varip int stProvBar = na
if stAlertProv and is5mChart and not barstate.isconfirmed and oState == 0 and stSessOK
    if na(stProvBar) or stProvBar != bar_index
        [pSide, pPx, pSL] = f_stProvEval()
        if pSide != 0
            stProvBar := bar_index
            alert(f_stAlertMsg("仮", pSide, pPx, pSL), alert.freq_once_per_bar)
"""

EDITS += [
    ("//  ・描画 (box / label / MA plot / Stats) は持たない。判定は確定 5分足でだけ。\n",
     "//  ・描画 (box / label / MA plot / Stats) は持たない。Zone / BOS 待機 / 注文の判定と状態更新は確定 5分足でだけ。\n"
     "//  ・USDJPY: 仮 / 確定アラート (ゴールド版 PracticalZoneStrategy_LONG.pine P10 と同じ意味)。仮アラートのため\n"
     "//    calc_on_every_tick = true。未確定 tick では zn.update / Zone 走査 / FVG 走査 / 注文を行わず、\n"
     "//    確定時に保存した状態を読むだけ (ヒストリカル = 全足確定なのでバックテストは変わらない)。\n"),
    ("     calc_on_every_tick     = false,\n", "     calc_on_every_tick     = true,\n"),
    ("if is5mChart\n    zoneCountNow := zn.update(zoneEng, zoneCfg, zoneFeed)\n",
     "//  ★ USDJPY: calc_on_every_tick = true でも Engine 更新は確定足だけ (未確定 tick の更新は巻き戻されるだけで、\n"
     "//    確定時の結果は同じ)。毎 tick の Engine 更新・Zone 走査をしない。\n"
     "if is5mChart and barstate.isconfirmed\n    zoneCountNow := zn.update(zoneEng, zoneCfg, zoneFeed)\n"),
    ('zoneHalfWidth = input.float(0.05, "Zone Half Width (円)", minval = 0.005, step = 0.005, group = G_ZONE,\n',
     'zoneHalfWidth = input.float(0.03, "Zone Half Width (円)", minval = 0.005, step = 0.005, group = G_ZONE,\n'),
    ('stDir = input.string("Both", "Direction",', 'stDir = input.string("Long Only", "Direction",'),
    ('stTpZone = input.bool(true, "TP · Nearest Opposite Zone (Medium+)", group = G_STT)\n',
     'stTpZone = input.bool(false, "TP · Nearest Opposite Zone (Medium+)", group = G_STT)\n'),
    ('stRR = input.float(1.5, "TP Fixed RR",', 'stRR = input.float(1.3, "TP Fixed RR",'),
    ('stBEDist = input.float(0.15, "[暫定] Breakeven Trigger (円)", minval = 0.0, step = 0.005, group = G_STT)\n',
     'stBEDist = input.float(0.15, "[暫定] Breakeven Trigger (円)", minval = 0.0, step = 0.005, group = G_STT)\n'
     'var string G_STA = "03 · Strategy Alerts"\n'
     'stAlertProv = input.bool(true, "仮アラート (形成中の5分足・未確定)", group = G_STA,\n'
     '     tooltip = "確定 Entry 条件から「確定足であること」だけを外した予告。5分足の確定時に不成立になる場合あり。\\n" +\n'
     '     "1 本の 5分足につき最大 1 回。TradingView の Alert は「alert() function calls only」で作成。")\n'
     'stAlertConf = input.bool(true, "確定アラート (5分足確定時の発注成立)", group = G_STA,\n'
     '     tooltip = "5分足の確定時に strategy.entry を出したときだけ (約定通知ではない)。")\n'),
    ("int stZones   = 0\n", PROV_FUNCS + "int stZones   = 0\n"),
    ("                strategy.exit(oXid, oEid, stop = oSL)\n    stPrev := cur\n",
     "                strategy.exit(oXid, oEid, stop = oSL)\n"
     "                if stAlertConf\n"
     "                    alert(f_stAlertMsg(\"確定\", side, stModeA ? oL : close, oSL), alert.freq_all)\n"
     "    stPrev := cur\n    stTpUpPrev := tpUp\n    stTpDnPrev := tpDn\n"),
    ('plot(stSessOK ? 1 : 0,                 "ST · Entry Session",     display = display.data_window)\n',
     'plot(stSessOK ? 1 : 0,                 "ST · Entry Session",     display = display.data_window)\n' + PROV_BLOCK),
]


def pipeline():
    """ZONE-JPY -> ST-1 -> ST-2 -> ST-3 (before the USDJPY edits)."""
    return s3.st3_transform(s2.st2_transform(tb.st_transform(jb.build())))


def stj_transform(st3_text):
    out = st3_text
    for a, b in EDITS:
        assert out.count(a) == 1, a[:80]
        out = out.replace(a, b) if b else out.replace(a, "")
    return out


def strip_stj(text):
    """exact inverse of stj_transform (None when the text is not a USDJPY build)."""
    out = text
    for a, b in reversed(EDITS):
        if b:
            if out.count(b) != 1:
                return None
            out = out.replace(b, a)
        else:      # removed block: it sat right after f_num
            anchor = 'f_num(float v, string fmt) =>\n    na(v) ? "-" : str.tostring(v, fmt)\n'
            if out.count(anchor) != 1:
                return None
            out = out.replace(anchor, anchor + a)
    return out


def build():
    return stj_transform(pipeline())


if __name__ == "__main__":
    open(os.path.join(ROOT, STJ_PATH), "w", encoding="utf-8").write(build())
    print("written", STJ_PATH)
