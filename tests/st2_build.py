"""ST-2 — ZoneStrategyXAU.pine: A / B / C rebound entries on the ZONE-P zones, Zone-based SL, fill-price TP.

Deterministic transform of the ST-1 text (st1_build.build()):
  1. the header's ST-1 line ("no orders yet") is replaced by the ST-2 summary
  2. the ST-1 evaluation loop (data-window counters only) is replaced by the ST-2 block, which keeps the same single
     zone loop / the same f_stZoneEval call / the same three counters and adds inputs, the candidate list, the order
     state and the orders
strip_st2() is the exact inverse (used by st1_sim, so every ST-1 check keeps running on the ST-1 text).
Everything above the evaluation loop (ZONE-P computation, Batch C copies, f_stZoneEval) is untouched.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import st1_build as tb      # noqa: E402

ROOT = tb.ROOT
ST_PATH = tb.ST_PATH

HDR_OLD = "//  ・ST-1: Entry / SL / TP 注文はまだ無い (評価ループは Profiler 計測用の最小構造)。\n"
HDR_NEW = """//  ・ST-2: A / B / C 反発 Entry (選択した 1 方式だけ実行)、Zone 基準の固定 SL、実約定価格基準の TP。
//    TP は約定を確認した足の確定時に初めて発注するため、約定した足の中では TP が無い (結果の解釈に注意)。
"""

LOOP_OLD = """// ---- 確定 5分足の評価ループ (ST-1: 注文なし。Profiler で Zone 評価の負荷を測るための最小構造) ----
int stZones   = 0
int stFvgZone = 0
int stBoosted = 0
if is5mChart and barstate.isconfirmed
    int n = zn.zoneCount(zoneEng)
    stZones := n
    if n > 0
        for i = 0 to n - 1
            zn.Zone z = zn.zoneAt(zoneEng, i)
            [eScore, eStr, eBest, eBoost, eBTop, eBBot, eVTop, eVBot] = f_stZoneEval(z)
            if eBest >= 0
                stFvgZone += 1
            if eBoost
                stBoosted += 1

plot(stZones,   "ST · Zones",             display = display.data_window)
plot(stFvgZone, "ST · Zones with FVG",    display = display.data_window)
plot(stBoosted, "ST · FVG boosted zones", display = display.data_window)
"""

LOOP_NEW = """// ---- ST-2 · 反発 Entry (A / B / C)、Zone 基準 SL、実約定価格基準 TP ---------------------------------
//  ・選択した Entry Mode だけを実行する。同時に持つ注文 (保留 / 保有) は 1 件、同じ Track は 1 回まで (約定時に記録)。
//  ・候補 Zone: SUPPORT (Long) / RESIST (Short) で、元 Strength >= Strong、または FVG 昇格範囲の Strength >= Strong。
//  ・A: 足 t の更新後の候補で、終値が Zone の外にあるとき指値 L を置く (元 Strong = Zone 端、昇格範囲だけ Strong =
//       昇格範囲の端)。期限・差し替えなし。未約定の間は毎確定足で「同じ Track が live、State 有効、L が Zone 内で
//       L での Strength (元 / 昇格) >= Strong」を確認し、外れたら取り消す (足の途中で先に約定したものは取り消せない)。
//  ・B / C: 足 t−1 の確定時に保存した候補に足 t の高値安値が接触し、終値が Zone の外で確定 (Long は > top)。
//       C はさらに包み足またはピンバー。足 t の更新後も Track が live で同じ State のときだけ次足成行。
//  ・SL = 元 Zone の反対端 ∓ Buffer。Entry と同時に発注し、以後動かさない。
//  ・TP = 約定価格 ± (約定価格 − SL) × RR。約定を確認した足の確定時に初めて発注する (約定した足の中では TP は無い)。
//    リスク <= 0 (約定価格が SL の不適切な側) なら TP を置かず、成行決済を試みる。
var string G_ST = "03 · Strategy Entry (ST-2)"
stMode = input.string("B: Confirmed Rejection", "Entry Mode",
     options = ["A: Touch Limit", "B: Confirmed Rejection", "C: Candle Pattern"], group = G_ST)
stDir = input.string("Both", "Direction", options = ["Long Only", "Short Only", "Both"], group = G_ST)
stBuffer = input.float(3.0, "SL Buffer ($)", minval = 0.0, step = 0.5, group = G_ST)
stRR = input.float(1.5, "TP Risk Reward", minval = 0.1, step = 0.1, group = G_ST)
stPinRatio = input.float(2.0, "C · Pin Bar Wick / Body", minval = 0.5, step = 0.5, group = G_ST)

bool stModeA   = stMode == "A: Touch Limit"
bool stModeC   = stMode == "C: Candle Pattern"
bool stLongOK  = stDir != "Short Only"
bool stShortOK = stDir != "Long Only"

// C のパターン (5分足ローカル): 実体の包み足、またはヒゲ / 実体 >= stPinRatio のピンバー
float stBody   = math.abs(close - open)
float stWickLo = math.min(open, close) - low
float stWickHi = high - math.max(open, close)
bool  stPatL   = (close > open and close[1] < open[1] and open <= close[1] and close >= open[1]) or (stWickLo > 0 and stWickLo >= stPinRatio * stBody and stWickLo > stWickHi)
bool  stPatS   = (close < open and close[1] > open[1] and open >= close[1] and close <= open[1]) or (stWickHi > 0 and stWickHi >= stPinRatio * stBody and stWickHi > stWickLo)

// 候補 Zone (確定時の値を保存する。B / C は 1 本前の確定時の一覧を使う)
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

// a が b より優先なら true。B / C: Strength 高 → Score 高 → 距離 小 → trackId 小。A (distFirst): 距離 小 を最初に比べる
f_stBetter(bool distFirst, int aS, float aSc, float aD, int aT, int bS, float bSc, float bD, int bT) =>
    distFirst and aD != bD ? aD < bD : aS != bS ? aS > bS : aSc != bSc ? aSc > bSc : aD != bD ? aD < bD : aT < bT

var array<StCand>  stPrev = array.new<StCand>()
var map<int, bool> stUsed = map.new<int, bool>()
var int    oState  = 0       // 0 = なし / 1 = Entry 発注済み (未約定) / 2 = 保有中
var int    oSeq    = 0
var string oEid    = ""
var string oXid    = ""
var bool   oLimit  = false
var int    oSide   = 0
var int    oTrack  = -1
var float  oL      = na
var float  oSL     = na
var float  oTP     = na
var int    oClosed = 0

int stZones   = 0
int stFvgZone = 0
int stBoosted = 0
if is5mChart and barstate.isconfirmed
    // (1) 発注済み Entry の約定 / 決済を確認する
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
            float fillPx = strategy.opentrades.entry_price(ot - 1)
            float risk   = oSide * (fillPx - oSL)
            if risk > 0
                oTP := fillPx + oSide * stRR * risk
                strategy.exit(oXid, oEid, stop = oSL, limit = oTP)
            else
                strategy.close(oEid)
            oState := 2
        else if filledClosed
            // 約定した足の中で SL まで成立した
            map.put(stUsed, oTrack, true)
            oState := 0
        else if not oLimit
            strategy.cancel(oEid)
            strategy.cancel(oXid)
            oState := 0
    else if oState == 2 and strategy.opentrades == 0
        oState := 0

    // (2) Zone の走査 (1 回): 候補一覧、Track の State、保留中の指値の有効性
    int n = zn.zoneCount(zoneEng)
    stZones := n
    array<StCand> cur    = array.new<StCand>()
    array<int>    curTrk = array.new_int()
    array<int>    curSt  = array.new_int()
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

    // (3) 保留中の指値 (A) の取消: Track 消失 / State 無効 / L で Strong 以上の資格を失った
    bool cancelBar = false
    if oState == 1 and not pendOK
        strategy.cancel(oEid)
        strategy.cancel(oXid)
        oState    := 0
        cancelBar := true

    // (4) 新規 Entry (注文が無く、取消をした足でないときだけ)
    if oState == 0 and not cancelBar
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
        // Both で Long / Short が同じ足に成立: B / C は見送り。A は指値が終値に近い方 (同じ距離なら見送り)
        int side = 0
        if bkL >= 0 and bkS >= 0
            if stModeA and bdL != bdS
                side := bdL < bdS ? 1 : -1
        else if bkL >= 0
            side := 1
        else if bkS >= 0
            side := -1
        if side != 0
            StCand c = array.get(src, side == 1 ? bkL : bkS)
            oSeq    += 1
            oEid    := (side == 1 ? "L" : "S") + str.tostring(oSeq)
            oXid    := oEid + " SL/TP"
            oSide   := side
            oTrack  := c.track
            oLimit  := stModeA
            oL      := stModeA ? (side == 1 ? bpL : bpS) : na
            oSL     := side == 1 ? c.bot - stBuffer : c.top + stBuffer
            oTP     := na
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
plot(oState == 1 and oLimit ? oL : na, "ST · Pending Limit", display = display.data_window)
plot(oState >= 1 ? oSL : na,           "ST · SL",            display = display.data_window)
plot(oState == 2 ? oTP : na,           "ST · TP",            display = display.data_window)
"""


def st2_transform(st1):
    assert st1.count(HDR_OLD) == 1 and st1.count(LOOP_OLD) == 1
    return st1.replace(HDR_OLD, HDR_NEW).replace(LOOP_OLD, LOOP_NEW)


def strip_st2(st2):
    """exact inverse of st2_transform (text that is not an ST-2 build is returned unchanged)."""
    if st2.count(HDR_NEW) != 1 or st2.count(LOOP_NEW) != 1:
        return st2
    return st2.replace(HDR_NEW, HDR_OLD).replace(LOOP_NEW, LOOP_OLD)


def build():
    return st2_transform(tb.build())


if __name__ == "__main__":
    open(os.path.join(ROOT, ST_PATH), "w", encoding="utf-8").write(build())
    print("written", ST_PATH)
