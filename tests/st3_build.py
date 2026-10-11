"""ST-3 — ZoneStrategyXAU.pine: D (1M BOS rebound), entry session, opposite-zone TP, breakeven stop.

Deterministic transform of the ST-2 text (st2_build.build()):
  1. the header's ST-2 lines are replaced by the ST-3 summary
  2. the ST-2 block (LOOP_NEW) is replaced by the ST-3 block. A / B / C keep their ST-2 expressions; with
     Session / Zone TP / Breakeven switched off the orders are the ST-2 orders (fixture st3_sim TE)
strip_st3() is the exact inverse (st1_sim / st2_sim load through it).
Zone generation, Strength, FVG Batch A / C, f_stZoneEval and everything above the block are untouched.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import st2_build as s2      # noqa: E402

ROOT = s2.ROOT
ST_PATH = s2.ST_PATH

HDR_OLD = s2.HDR_NEW
HDR_NEW = """//  ・ST-3: A / B / C / D 反発 Entry (選択した 1 方式だけ実行)、新規 Entry の時間帯、反対側 Zone の TP、建値移動。
//    Zone 基準の SL は Entry と同時に固定。TP は約定を確認した足の確定時に初めて決めて発注するため、
//    約定した足の中では TP が無い (結果の解釈に注意)。建値 stop は到達を確認した確定足の次の足から有効。
"""

LOOP_OLD = s2.LOOP_NEW

LOOP_NEW = """// ---- ST-3 · 反発 Entry (A / B / C / D)、時間帯、反対側 Zone の TP、建値移動 ------------------------------
//  ・選択した Entry Mode だけを実行する。同時に持つ注文 (保留 / 保有) は 1 件、同じ Track は 1 回まで (約定時に記録)。
//  ・候補 Zone: SUPPORT (Long) / RESIST (Short) で、元 Strength >= Strong、または FVG 昇格範囲の Strength >= Strong。
//  ・A: 足 t の更新後の候補で、終値が Zone の外にあるとき指値 L を置く (元 Strong = Zone 端、昇格範囲だけ Strong =
//       昇格範囲の端)。期限・差し替えなし。未約定の間は毎確定足で「同じ Track が live、State 有効、L が Zone 内で
//       L での Strength (元 / 昇格) >= Strong、時間帯内」を確認し、外れたら取り消す (足の途中の約定は取り消せない)。
//  ・B / C / D: 足 t−1 の確定時に保存した候補に足 t の高値安値が接触し、終値が Zone の外で確定 (Long は > top)。
//       C はさらに包み足またはピンバー。D はさらに、足 t の 1分足で「Zone の外から接触 → 反発 → 確定 1分足の BOS」
//       がこの順に起きたこと。足 t の更新後も Track が live で同じ State のときだけ、足 t の確定時に次足成行で発注する
//       (1分足の BOS 時点では約定させない)。
//  ・新規 Entry (発注と保留中の指値) は時間帯の中だけ。保有中の SL / TP / 建値管理は時間外も続ける。
//  ・SL = 元 Zone の反対端 ∓ Buffer。Entry と同時に発注し、建値移動以外では動かさない。
//  ・TP: 約定を確認した足の確定時に、実約定価格から決める (約定した足の中では TP は無い)。
//       利益方向で最も手前の反対側 Zone (Medium 以上) の RR が Min 未満 → TP を置かず成行決済 (見送り)、
//       Min 以上 Max 未満 → その Zone を TP、Max 以上または該当 Zone なし → 固定 RR。
//       発注前にも参照価格 (A: 指値 / B, C, D: 足 t の終値) で同じ判定をし、Min 未満なら発注しない。
//       リスク <= 0 (約定価格が SL の不適切な側) なら TP を置かず成行決済を試みる。
//  ・建値移動: 確定足の高値 (Long) / 安値 (Short) が約定価格 ± Trigger に届いたら、stop を約定価格へ移す。
//       移した stop は次の足から有効。足の途中で約定した指値の約定足は終値だけで判定する。
var string G_ST = "03 · Strategy Entry"
stMode = input.string("B: Confirmed Rejection", "Entry Mode",
     options = ["A: Touch Limit", "B: Confirmed Rejection", "C: Candle Pattern", "D: 1M BOS Rebound"], group = G_ST)
stDir = input.string("Both", "Direction", options = ["Long Only", "Short Only", "Both"], group = G_ST)
stBuffer = input.float(3.0, "SL Buffer ($)", minval = 0.0, step = 0.5, group = G_ST)
stPinRatio = input.float(2.0, "C · Pin Bar Wick / Body", minval = 0.5, step = 0.5, group = G_ST)
var string G_STS = "03 · Strategy Session (新規 Entry のみ)"
stUseSess = input.bool(true, "Limit New Entries to Session", group = G_STS)
stSessTz = input.string("Asia/Tokyo", "Session Timezone", group = G_STS)
stSessStartH = input.int(9, "Session Start Hour", minval = 0, maxval = 23, group = G_STS)
stSessStartM = input.int(0, "Session Start Minute", minval = 0, maxval = 59, group = G_STS)
stSessEndH = input.int(3, "Session End Hour", minval = 0, maxval = 23, group = G_STS)
stSessEndM = input.int(0, "Session End Minute", minval = 0, maxval = 59, group = G_STS)
var string G_STT = "03 · Strategy TP / Breakeven"
stTpZone = input.bool(true, "TP · Nearest Opposite Zone (Medium+)", group = G_STT)
stTpMinRR = input.float(1.0, "TP Zone · Min RR (未満は見送り)", minval = 0.0, step = 0.1, group = G_STT)
stTpMaxRR = input.float(3.0, "TP Zone · Max RR (以上は固定 RR)", minval = 0.1, step = 0.1, group = G_STT)
stRR = input.float(1.5, "TP Fixed RR", minval = 0.1, step = 0.1, group = G_STT)
stBE = input.bool(true, "Breakeven Stop", group = G_STT)
stBEDist = input.float(10.0, "Breakeven Trigger ($)", minval = 0.0, step = 0.5, group = G_STT)

bool stModeA   = stMode == "A: Touch Limit"
bool stModeC   = stMode == "C: Candle Pattern"
bool stModeD   = stMode == "D: 1M BOS Rebound"
bool stLongOK  = stDir != "Short Only"
bool stShortOK = stDir != "Long Only"

// C のパターン (5分足ローカル): 実体の包み足、またはヒゲ / 実体 >= stPinRatio のピンバー
float stBody   = math.abs(close - open)
float stWickLo = math.min(open, close) - low
float stWickHi = high - math.max(open, close)
bool  stPatL   = (close > open and close[1] < open[1] and open <= close[1] and close >= open[1]) or (stWickLo > 0 and stWickLo >= stPinRatio * stBody and stWickLo > stWickHi)
bool  stPatS   = (close < open and close[1] > open[1] and open >= close[1] and close <= open[1]) or (stWickHi > 0 and stWickHi >= stPinRatio * stBody and stWickHi > stWickLo)

// D の 1分足 (下位足データ: 足 t の中の確定 1分足の配列)。D のときだけ取得する
array<float> m1h = na
array<float> m1l = na
array<float> m1c = na
if stModeD and is5mChart
    [rh, rl, rc] = request.security_lower_tf(syminfo.tickerid, "1", [high, low, close])
    m1h := rh
    m1l := rl
    m1c := rc

// 新規 Entry の時間帯: 判定足の終了時刻 (= 次足始値の約定時刻) が [開始, 終了) に入るか。開始 > 終了 は日付またぎ
f_stInSession(int t) =>
    int mins = hour(t, stSessTz) * 60 + minute(t, stSessTz)
    int s    = stSessStartH * 60 + stSessStartM
    int e    = stSessEndH * 60 + stSessEndM
    s == e ? true : s < e ? (mins >= s and mins < e) : (mins >= s or mins < e)
bool stSessOK = not stUseSess or f_stInSession(time_close)

// 候補 Zone (確定時の値を保存する。B / C / D は 1 本前の確定時の一覧を使う)
type StCand
    int   side
    int   track
    float top
    float bot
    float bTop
    float bBot
    int   sZ
    int   sB
    float score
    float dScore

// 価格帯 [lo, hi] で採用する Strength / Score: 昇格範囲と交差 (閉区間) すれば FVG 加点後、しなければ元 Zone
f_stAdopt(StCand c, float lo, float hi) =>
    bool inB = not na(c.bTop) and math.max(lo, c.bBot) <= math.min(hi, c.bTop)
    [inB ? c.sB : c.sZ, inB ? c.dScore : c.score]

// a が b より優先なら true。B / C / D: Strength 高 → Score 高 → 距離 小 → trackId 小。A (distFirst): 距離 小 を最初に比べる
f_stBetter(bool distFirst, int aS, float aSc, float aD, int aT, int bS, float bSc, float bD, int bT) =>
    distFirst and aD != bD ? aD < bD : aS != bS ? aS > bS : aSc != bSc ? aSc > bSc : aD != bD ? aD < bD : aT < bT

// D: 足 t の 1分足で「Zone の外 (Long は上) から接触 → 反発 → 確定 1分足の BOS」がこの順に起きたか。
//    接触 = 直前の終値が Zone の外で、その 1分足が Zone に触れた。BOS 水準 = 接触から最安値 (Short は最高値) までの
//    1分足の高値の最大 (Short は安値の最小)。接触した 1分足より後の 1分足の終値がその水準を越えたら BOS。
//    接触より前の BOS は数えない。直前の終値は、最初の 1分足では前の 5分足の終値。
f_stBos(int side, float top, float bot, float prevC, array<float> hh, array<float> hl, array<float> hc) =>
    int   nb  = na(hh) ? 0 : array.size(hh)
    bool  bos = false
    bool  tch = false
    float ext = na
    float run = na
    float lvl = na
    float pc  = prevC
    if nb > 0
        for j = 0 to nb - 1
            float h  = array.get(hh, j)
            float l  = array.get(hl, j)
            float cl = array.get(hc, j)
            if not bos
                if not tch
                    if l <= top and h >= bot and (side == 1 ? pc > top : pc < bot)
                        tch := true
                        ext := side == 1 ? l : h
                        run := side == 1 ? h : l
                        lvl := run
                else if side == 1 ? cl > lvl : cl < lvl
                    bos := true
                else
                    run := side == 1 ? math.max(run, h) : math.min(run, l)
                    if side == 1 ? l < ext : h > ext
                        ext := side == 1 ? l : h
                        lvl := run
            pc := cl
    bos

// TP 価格の候補: 利益方向で最も手前の反対側 Zone 端 (Long は ref より上で最も低い、Short は ref より下で最も高い)
f_stNearest(array<float> edges, int side, float ref) =>
    float best = na
    int   ne   = array.size(edges)
    if ne > 0
        for k = 0 to ne - 1
            float e = array.get(edges, k)
            if side == 1 ? e > ref : e < ref
                if na(best) or (side == 1 ? e < best : e > best)
                    best := e
    best

// RR 判定 (risk > 0 のときだけ呼ぶ): [見送り, TP]。Zone の RR < Min → 見送り、Min <= RR < Max → Zone 端、それ以外 → 固定 RR
f_stTp(int side, float fillPx, float sl, float edge) =>
    float risk = side * (fillPx - sl)
    float tp   = fillPx + side * stRR * risk
    bool  skip = false
    if stTpZone and not na(edge)
        float rrZ = side * (edge - fillPx) / risk
        if rrZ < stTpMinRR
            skip := true
        else if rrZ < stTpMaxRR
            tp := edge
    [skip, tp]

var array<StCand>  stPrev = array.new<StCand>()
var map<int, bool> stUsed = map.new<int, bool>()
var int    oState  = 0       // 0 = なし / 1 = Entry 発注済み (未約定) / 2 = 保有中 / 3 = 成行決済を発注済み
var int    oSeq    = 0
var string oEid    = ""
var string oXid    = ""
var bool   oLimit  = false
var int    oSide   = 0
var int    oTrack  = -1
var float  oL      = na
var float  oSL     = na
var float  oTP     = na
var float  oFill   = na
var float  oStop   = na
var bool   oBE     = false
var int    oClosed = 0

int stZones   = 0
int stFvgZone = 0
int stBoosted = 0
if is5mChart and barstate.isconfirmed
    // (1) 発注済み Entry の約定 / 決済を確認する
    bool fillNow = false
    if oState == 1
        int  ot           = strategy.opentrades
        int  ct           = strategy.closedtrades
        bool filledOpen   = false
        bool filledClosed = false
        if ot > 0
            filledOpen := strategy.opentrades.entry_id(ot - 1) == oEid
        if not filledOpen and ct > oClosed
            filledClosed := strategy.closedtrades.entry_id(ct - 1) == oEid
        if filledOpen
            map.put(stUsed, oTrack, true)
            oFill   := strategy.opentrades.entry_price(ot - 1)
            oState  := 2
            fillNow := true
        else if filledClosed
            // 約定した足の中で SL まで成立した
            map.put(stUsed, oTrack, true)
            oState := 0
        else if not oLimit
            strategy.cancel(oEid)
            strategy.cancel(oXid)
            oState := 0
    else if oState >= 2 and strategy.opentrades == 0
        oState := 0

    // (2) Zone の走査 (1 回): 候補一覧、Track の State、保留中の指値の有効性、TP 用の反対側 Zone 端
    int n = zn.zoneCount(zoneEng)
    stZones := n
    array<StCand> cur    = array.new<StCand>()
    array<int>    curTrk = array.new_int()
    array<int>    curSt  = array.new_int()
    array<float>  tpUp   = array.new_float()
    array<float>  tpDn   = array.new_float()
    bool pendOK = false
    if n > 0
        for i = 0 to n - 1
            zn.Zone z = zn.zoneAt(zoneEng, i)
            [eScore, eStr, eBest, eBoost, eBTop, eBBot, eVTop, eVBot] = f_stZoneEval(z)
            if eBest >= 0
                stFvgZone += 1
            if eBoost
                stBoosted += 1
            array.push(curTrk, z.trackId)
            array.push(curSt, z.state)
            int zSide = z.state == ST_SUPPORT ? 1 : z.state == ST_RESIST ? -1 : 0
            if zSide != 0 and (z.strength >= SR_STRONG or (eBoost and eStr >= SR_STRONG))
                array.push(cur, StCand.new(zSide, z.trackId, z.top, z.bottom, eBTop, eBBot, z.strength, eStr, z.score, eScore))
            if oState == 1 and z.trackId == oTrack
                pendOK := zSide == oSide and z.bottom <= oL and oL <= z.top and (z.strength >= SR_STRONG or (eBoost and eStr >= SR_STRONG and eBBot <= oL and oL <= eBTop))
            if zSide != 0
                float edge = na
                if z.strength >= SR_MEDIUM
                    edge := zSide == -1 ? z.bottom : z.top
                else if eBoost and eStr >= SR_MEDIUM
                    edge := zSide == -1 ? eBBot : eBTop
                if not na(edge)
                    array.push(zSide == -1 ? tpUp : tpDn, edge)

    // (2b) 約定を確認した足: 実約定価格から RR と TP を決める (約定した足の中では TP は無い)
    if fillNow
        float risk = oSide * (oFill - oSL)
        if risk > 0
            [skipRR, tp] = f_stTp(oSide, oFill, oSL, f_stNearest(oSide == 1 ? tpUp : tpDn, oSide, oFill))
            if skipRR
                strategy.close(oEid)
                oState := 3
            else
                oTP   := tp
                oStop := oSL
                strategy.exit(oXid, oEid, stop = oStop, limit = oTP)
        else
            strategy.close(oEid)
            oState := 3

    // (2c) 建値移動: この確定足で含み益が Trigger に届いたら stop を約定価格へ (次の足から有効)
    if stBE and oState == 2 and not oBE
        float fav = oSide == 1 ? high : low
        if fillNow and oLimit and oFill != open
            fav := close
        if oSide * (fav - oFill) >= stBEDist
            oBE   := true
            oStop := oFill
            strategy.exit(oXid, oEid, stop = oStop, limit = oTP)

    // (3) 保留中の指値 (A) の取消: Track 消失 / State 無効 / L で Strong 以上の資格を失った / 時間帯の外
    bool cancelBar = false
    if oState == 1 and (not pendOK or not stSessOK)
        strategy.cancel(oEid)
        strategy.cancel(oXid)
        oState    := 0
        cancelBar := true

    // (4) 新規 Entry (注文が無く、取消をした足でなく、時間帯の中のときだけ)
    if oState == 0 and not cancelBar and stSessOK
        array<StCand> src = stModeA ? cur : stPrev
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
        int m = array.size(src)
        if m > 0
            for k = 0 to m - 1
                StCand c = array.get(src, k)
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
                    else
                        [s2, sc2] = f_stAdopt(c, math.max(low, c.bot), math.min(high, c.top))
                        aS  := s2
                        aSc := sc2
                        d   := math.abs(close - (c.side == 1 ? c.top : c.bot))
                        bool trkOK = false
                        int  idx   = array.indexof(curTrk, c.track)
                        if idx >= 0
                            trkOK := array.get(curSt, idx) == (c.side == 1 ? ST_SUPPORT : ST_RESIST)
                        ok := low <= c.top and high >= c.bot and (c.side == 1 ? close > c.top : close < c.bot) and aS >= SR_STRONG and trkOK and (not stModeC or (c.side == 1 ? stPatL : stPatS))
                        if ok and stModeD
                            ok := f_stBos(c.side, c.top, c.bot, close[1], m1h, m1l, m1c)
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
        // Both で Long / Short が同じ足に成立: B / C / D は見送り。A は指値が終値に近い方 (同じ距離なら見送り)
        int side = 0
        if bkL >= 0 and bkS >= 0
            if stModeA and bdL != bdS
                side := bdL < bdS ? 1 : -1
        else if bkL >= 0
            side := 1
        else if bkS >= 0
            side := -1
        if side != 0
            StCand c   = array.get(src, side == 1 ? bkL : bkS)
            float  pL  = stModeA ? (side == 1 ? bpL : bpS) : na
            float  pSL = side == 1 ? c.bot - stBuffer : c.top + stBuffer
            float  ref = stModeA ? pL : close
            // 発注前の RR 判定 (参照価格)。約定後に実約定価格で同じ判定をやり直す
            [skipRef, tpRef] = f_stTp(side, ref, pSL, f_stNearest(side == 1 ? tpUp : tpDn, side, ref))
            if not skipRef
                oSeq    += 1
                oEid    := (side == 1 ? "L" : "S") + str.tostring(oSeq)
                oXid    := oEid + " SL/TP"
                oSide   := side
                oTrack  := c.track
                oLimit  := stModeA
                oL      := pL
                oSL     := pSL
                oStop   := pSL
                oTP     := na
                oFill   := na
                oBE     := false
                oClosed := strategy.closedtrades
                oState  := 1
                if stModeA
                    strategy.entry(oEid, side == 1 ? strategy.long : strategy.short, limit = oL)
                else
                    strategy.entry(oEid, side == 1 ? strategy.long : strategy.short)
                strategy.exit(oXid, oEid, stop = oSL)
    stPrev := cur

plot(stZones,   "ST · Zones",             display = display.data_window)
plot(stFvgZone, "ST · Zones with FVG",    display = display.data_window)
plot(stBoosted, "ST · FVG boosted zones", display = display.data_window)
plot(oState == 1 and oLimit ? oL : na, "ST · Pending Limit",     display = display.data_window)
plot(oState >= 1 ? oStop : na,         "ST · Stop (SL / BE)",    display = display.data_window)
plot(oState == 2 ? oTP : na,           "ST · TP",                display = display.data_window)
plot(stSessOK ? 1 : 0,                 "ST · Entry Session",     display = display.data_window)
"""


def st3_transform(st2):
    assert st2.count(HDR_OLD) == 1 and st2.count(LOOP_OLD) == 1
    return st2.replace(HDR_OLD, HDR_NEW).replace(LOOP_OLD, LOOP_NEW)


def strip_st3(st3):
    """exact inverse of st3_transform (text that is not an ST-3 build is returned unchanged)."""
    if st3.count(HDR_NEW) != 1 or st3.count(LOOP_NEW) != 1:
        return st3
    return st3.replace(HDR_NEW, HDR_OLD).replace(LOOP_NEW, LOOP_OLD)


def build():
    return st3_transform(s2.build())


if __name__ == "__main__":
    open(os.path.join(ROOT, ST_PATH), "w", encoding="utf-8").write(build())
    print("written", ST_PATH)
