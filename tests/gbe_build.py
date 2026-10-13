"""GBE-1 — ZoneEnginePracticalGBPJPY.pine: GBPJPY-only derivative of ZoneEnginePractical/6 (ZoneEnginePracticalSwingMax.pine)
with an Accum score mode across timeframes (Sum / Max).

Deterministic transform of ZoneEnginePracticalSwingMax.pine by exact, unique text replacements (EDITS); strip_gbe() reverts
them and must give the /6 source back byte for byte (fixture gbe_sim). The shared /6 file itself is not modified.
  - library name ZoneEnginePracticalGBPJPY (a separate library: Gold / USDJPY keep importing ZoneEnginePractical/6)
  - ZoneCfg.accScoreMax (default false = Sum = /6 behaviour)
  - f_finalizeCluster: inside the existing Accum branch each timeframe's contribution (a1 / a2 / a3, with the unchanged
    high / low once-per-cluster rule) is accumulated; Sum keeps adding to baseSum exactly as /6 (same additions in the
    same order: bit-identical), Max adds max(a1, a2, a3) once after the member loop. Category / HTF / srcMask unchanged.
Everything downstream of baseSum (score, Strength, Track, Touch, Break / Flip, FVG boost in the scripts) follows.
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_PATH = "ZoneEnginePracticalSwingMax.pine"
GBE_PATH = "ZoneEnginePracticalGBPJPY.pine"
LIB_NAME = "ZoneEnginePracticalGBPJPY"
IMPORT_6 = "import sekine3310/ZoneEnginePractical/6 as zn\n"
# Library versions are assigned by TradingView on publish. GBE-1 (Accum Score Mode) = version 1; GBE-2 (+ Accum Edge
# Mode) is expected to become version 2. If TradingView assigns another number, change IMPORT_GBE and rebuild
# (python3 tests/gbj_build.py && python3 tests/gbs_build.py).
IMPORT_GBE1 = "import sekine3310/ZoneEnginePracticalGBPJPY/1 as zn\n"
IMPORT_GBE2 = "import sekine3310/ZoneEnginePracticalGBPJPY/2 as zn\n"
# Version 3 = the time-based Day/Swing Deduplicate of 23fd5e0 (superseded, its origin-time data removed). The
# price-based Day/Swing Merge Nearby below is expected to become version 4.
IMPORT_GBE3 = "import sekine3310/ZoneEnginePracticalGBPJPY/3 as zn\n"
IMPORT_GBE = "import sekine3310/ZoneEnginePracticalGBPJPY/4 as zn\n"

ACC_OLD = """        else if m.srcCat == CAT_ACC
            if m.srcTf == c.accTf1
                srcM := f_setBit(srcM, SRC_ACC1)
                if isAccHi and not accHi1
                    accHi1  := true
                    baseSum += m.baseScore
                else if not isAccHi and not accLo1
                    accLo1  := true
                    baseSum += m.baseScore
            else if m.srcTf == c.accTf2
                srcM := f_setBit(srcM, SRC_ACC2)
                if isAccHi and not accHi2
                    accHi2  := true
                    baseSum += m.baseScore
                else if not isAccHi and not accLo2
                    accLo2  := true
                    baseSum += m.baseScore
            else if m.srcTf == c.accTf3
                srcM := f_setBit(srcM, SRC_ACC3)
                if isAccHi and not accHi3
                    accHi3  := true
                    baseSum += m.baseScore
                else if not isAccHi and not accLo3
                    accLo3  := true
                    baseSum += m.baseScore
"""
ACC_NEW = """        else if m.srcCat == CAT_ACC
            // GBE-1: 時間足ごとの寄与 (上限 / 下限はそれぞれ Cluster 内 1 回のまま) を accA1 / accA2 / accA3 に集計。
            //   Sum (既定) は /6 と同じ加算を同じ順序で baseSum へ行う (Max のときだけ 0 を足す = baseSum 不変)。
            if m.srcTf == c.accTf1
                srcM := f_setBit(srcM, SRC_ACC1)
                if isAccHi and not accHi1
                    accHi1  := true
                    accA1   += m.baseScore
                    baseSum += c.accScoreMax ? 0.0 : m.baseScore
                else if not isAccHi and not accLo1
                    accLo1  := true
                    accA1   += m.baseScore
                    baseSum += c.accScoreMax ? 0.0 : m.baseScore
            else if m.srcTf == c.accTf2
                srcM := f_setBit(srcM, SRC_ACC2)
                if isAccHi and not accHi2
                    accHi2  := true
                    accA2   += m.baseScore
                    baseSum += c.accScoreMax ? 0.0 : m.baseScore
                else if not isAccHi and not accLo2
                    accLo2  := true
                    accA2   += m.baseScore
                    baseSum += c.accScoreMax ? 0.0 : m.baseScore
            else if m.srcTf == c.accTf3
                srcM := f_setBit(srcM, SRC_ACC3)
                if isAccHi and not accHi3
                    accHi3  := true
                    accA3   += m.baseScore
                    baseSum += c.accScoreMax ? 0.0 : m.baseScore
                else if not isAccHi and not accLo3
                    accLo3  := true
                    accA3   += m.baseScore
                    baseSum += c.accScoreMax ? 0.0 : m.baseScore
"""

EDITS = [
    ("//  ZoneEnginePractical  —  Practical Zone v1 (Support / Resistance Zone Engine)\n",
     "//  ZoneEnginePractical  —  Practical Zone v1 (Support / Resistance Zone Engine)\n"
     "//  ★ GBPJPY 派生 (ZoneEnginePracticalGBPJPY、生成: tests/gbe_build.py)。ZoneEnginePractical/6 (SW-1 / RN-1) に\n"
     "//    Accum の時間足間の合算方式 (ZoneCfg.accScoreMax: false = Sum = /6 と同一 / true = Max) だけを加えたもの。\n"
     "//    同じ時間足の上限 / 下限の数え方、カテゴリ、HTF、他 Source、Confluence、Strength 閾値は /6 のまま。\n"),
    ('library("ZoneEnginePractical", overlay = true)\n', 'library("' + LIB_NAME + '", overlay = true)\n'),
    ("    int    accKeep3           = 1\n",
     "    int    accKeep3           = 1\n"
     "    bool   accScoreMax        = false   // GBE-1: Accum 時間足間 false = Sum (各時間足の寄与の合計) / true = Max (最大)\n"),
    ("    bool accHi3 = false\n    bool accLo3 = false\n",
     "    bool accHi3 = false\n    bool accLo3 = false\n"
     "    float accA1 = 0.0    // GBE-1: 時間足ごとの Accum 寄与 (accTf1 / accTf2 / accTf3)\n"
     "    float accA2 = 0.0\n"
     "    float accA3 = 0.0\n"),
    (ACC_OLD, ACC_NEW),
    ("    // ---- Round Number (RN-1): 1 Cluster につき最大1回。100 の倍数 (3点) を優先、無ければ 50 の倍数 (2点)\n"
     "    float baseSumEx = baseSum\n",
     "    // GBE-1: Max のときだけ、時間足ごとの寄与の最大値を 1 回加える (Sum は上のループで加算済み)\n"
     "    if c.accScoreMax\n"
     "        baseSum += math.max(accA1, math.max(accA2, accA3))\n\n"
     "    // ---- Round Number (RN-1): 1 Cluster につき最大1回。100 の倍数 (3点) を優先、無ければ 50 の倍数 (2点)\n"
     "    float baseSumEx = baseSum\n"),
]


# ---- GBE-2: Accum Edge Mode (Separate = current / Once per TF), applied after EDITS (GBE-1) --------------------------
#  Once per TF: the second edge (high after low, or low after high) of the same timeframe adds 0, so a timeframe
#  contributes its score at most once per cluster. Separate: the added value is m.baseScore exactly as in GBE-1 (the
#  same additions in the same order = bit-identical). The per-edge flags (accHi / accLo) and their duplicate removal are
#  unchanged; Sum / Max is applied afterwards to the per-timeframe contributions. strip_gbe2() -> the GBE-1 source.
EDITS2 = [
    ("//    同じ時間足の上限 / 下限の数え方、カテゴリ、HTF、他 Source、Confluence、Strength 閾値は /6 のまま。\n",
     "//    同じ時間足の上限 / 下限の数え方、カテゴリ、HTF、他 Source、Confluence、Strength 閾値は /6 のまま。\n"
     "//  ★ GBE-2: Accum Edge Mode (ZoneCfg.accEdgeOnce: false = Separate = 上限 / 下限をそれぞれ 1 回 (GBE-1 と同一) /\n"
     "//    true = Once per TF = 同じ時間足は上限・下限を合わせて最大 1 回)。時間足ごとの寄与を出してから Sum / Max。\n"),
    ("    bool   accScoreMax        = false   // GBE-1: Accum 時間足間 false = Sum (各時間足の寄与の合計) / true = Max (最大)\n",
     "    bool   accScoreMax        = false   // GBE-1: Accum 時間足間 false = Sum (各時間足の寄与の合計) / true = Max (最大)\n"
     "    bool   accEdgeOnce        = false   // GBE-2: Accum 同じ時間足 false = Separate (上限 / 下限を別々) / true = Once per TF\n"),
    ('                if isAccHi and not accHi1\n                    accHi1  := true\n                    accA1   += m.baseScore\n                    baseSum += c.accScoreMax ? 0.0 : m.baseScore\n                else if not isAccHi and not accLo1\n                    accLo1  := true\n                    accA1   += m.baseScore\n                    baseSum += c.accScoreMax ? 0.0 : m.baseScore\n',
     '                if isAccHi and not accHi1\n                    float eH1 = c.accEdgeOnce and accLo1 ? 0.0 : m.baseScore\n                    accHi1  := true\n                    accA1   += eH1\n                    baseSum += c.accScoreMax ? 0.0 : eH1\n                else if not isAccHi and not accLo1\n                    float eL1 = c.accEdgeOnce and accHi1 ? 0.0 : m.baseScore\n                    accLo1  := true\n                    accA1   += eL1\n                    baseSum += c.accScoreMax ? 0.0 : eL1\n'),
    ('                if isAccHi and not accHi2\n                    accHi2  := true\n                    accA2   += m.baseScore\n                    baseSum += c.accScoreMax ? 0.0 : m.baseScore\n                else if not isAccHi and not accLo2\n                    accLo2  := true\n                    accA2   += m.baseScore\n                    baseSum += c.accScoreMax ? 0.0 : m.baseScore\n',
     '                if isAccHi and not accHi2\n                    float eH2 = c.accEdgeOnce and accLo2 ? 0.0 : m.baseScore\n                    accHi2  := true\n                    accA2   += eH2\n                    baseSum += c.accScoreMax ? 0.0 : eH2\n                else if not isAccHi and not accLo2\n                    float eL2 = c.accEdgeOnce and accHi2 ? 0.0 : m.baseScore\n                    accLo2  := true\n                    accA2   += eL2\n                    baseSum += c.accScoreMax ? 0.0 : eL2\n'),
    ('                if isAccHi and not accHi3\n                    accHi3  := true\n                    accA3   += m.baseScore\n                    baseSum += c.accScoreMax ? 0.0 : m.baseScore\n                else if not isAccHi and not accLo3\n                    accLo3  := true\n                    accA3   += m.baseScore\n                    baseSum += c.accScoreMax ? 0.0 : m.baseScore\n',
     '                if isAccHi and not accHi3\n                    float eH3 = c.accEdgeOnce and accLo3 ? 0.0 : m.baseScore\n                    accHi3  := true\n                    accA3   += eH3\n                    baseSum += c.accScoreMax ? 0.0 : eH3\n                else if not isAccHi and not accLo3\n                    float eL3 = c.accEdgeOnce and accHi3 ? 0.0 : m.baseScore\n                    accLo3  := true\n                    accA3   += eL3\n                    baseSum += c.accScoreMax ? 0.0 : eL3\n'),
]


# ---- GBE-4 (replaces the time-based GBE-3): Day/Swing Overlap Mode = Separate / Merge Nearby, applied after EDITS2 ---
#  Price data (state only; Separate never reads it): every static Raw Zone keeps the actual registered price (px0) and the
#  price of the latest event merged into it (px1; for a Swing raw these are its pivot prices); the Day High / Low raws
#  carry the actual day extreme (px0). No time / origin information is kept.
#  Merge Nearby (f_finalizeCluster): within a cluster, a Swing High is merged with the Day High (Low with Low) when
#  round(|day - pivot| / mintick) <= round(dsDist / mintick) for its first or latest pivot price (0 = identical price).
#  If every Swing timeframe that earns the Swing max (ties included) has only merged Swings, the pair counts
#  max(Day, Swing max) (= Separate - min(Day, Swing max)); an independent Swing at the top score blocks it. HZ + DHL count
#  as one category only when exactly one merged Day side and no independent Horizontal / Day H/L source is in the
#  cluster. Flags are ORs and min / max are symmetric, so member order does not matter. strip_gbe3() -> version 2.
EDITS3 = [
    ("//    true = Once per TF = 同じ時間足は上限・下限を合わせて最大 1 回)。時間足ごとの寄与を出してから Sum / Max。\n",
     "//    true = Once per TF = 同じ時間足は上限・下限を合わせて最大 1 回)。時間足ごとの寄与を出してから Sum / Max。\n"
     "//  ★ GBE-4: Day/Swing Overlap Mode (ZoneCfg.dsMerge: false = Separate (GBE-2 と同一) / true = Merge Nearby)。\n"
     "//    同じ Cluster 内で、価格が dsDist 以内の Day High と Swing High (Low と Low) を 1 つの根拠として数える。\n"),
    ("    bool   accEdgeOnce        = false   // GBE-2: Accum 同じ時間足 false = Separate (上限 / 下限を別々) / true = Once per TF\n",
     "    bool   accEdgeOnce        = false   // GBE-2: Accum 同じ時間足 false = Separate (上限 / 下限を別々) / true = Once per TF\n"
     "    bool   dsMerge            = false   // GBE-4: Day/Swing Overlap false = Separate / true = Merge Nearby\n"
     "    float  dsDist             = 0.05    // GBE-4: Merge Distance (価格差、0 = 同じ価格だけ)\n"),
    ("    bool   dynamic        = false\n",
     "    bool   dynamic        = false\n"
     "    float  px0            = na      // GBE-4: 登録時の実際の価格 (Swing: pivot 価格 / Day H/L: その日の高安)\n"
     "    float  px1            = na      // GBE-4: この Raw Zone に統合された最新のイベントの価格 (Swing: 最新の pivot 価格)\n"),
    ("                    dup := true\n                    if life > 0\n",
     "                    dup := true\n"
     "                    z.px1 := price     // GBE-4: 統合された最新のイベント (pivot) の実際の価格\n"
     "                    if life > 0\n"),
    ("            rz.expireTime := life > 0 ? time + life : 0\n            array.push(e.persist, rz)\n",
     "            rz.expireTime := life > 0 ? time + life : 0\n"
     "            rz.px0 := price\n"
     "            rz.px1 := price\n"
     "            array.push(e.persist, rz)\n"),
    ('        f_pushDyn(e, c, 2, e.dayHighUid, "DAY_HIGH", CAT_DHL, "D", e.dayHigh, c.scoreDayHL, 0, 0, 0.0, 0.0)\n',
     '        f_pushDyn(e, c, 2, e.dayHighUid, "DAY_HIGH", CAT_DHL, "D", e.dayHigh, c.scoreDayHL, 0, 0, 0.0, 0.0)\n'
     '        RawZone dhz = array.get(e.sDynPool, 2)     // GBE-4: 実際の当日高値\n'
     '        dhz.px0 := e.dayHigh\n'),
    ('        f_pushDyn(e, c, 3, e.dayLowUid, "DAY_LOW", CAT_DHL, "D", e.dayLow, c.scoreDayHL, 0, 0, 0.0, 0.0)\n',
     '        f_pushDyn(e, c, 3, e.dayLowUid, "DAY_LOW", CAT_DHL, "D", e.dayLow, c.scoreDayHL, 0, 0, 0.0, 0.0)\n'
     '        RawZone dlz = array.get(e.sDynPool, 3)     // GBE-4: 実際の当日安値\n'
     '        dlz.px0 := e.dayLow\n'),
    ("    float accA3 = 0.0\n",
     "    float accA3 = 0.0\n"
     "    // GBE-4: Day/Swing Merge Nearby (dsMerge のときだけ使う)\n"
     "    bool  dsOn   = c.dsMerge\n"
     "    int   dsTk   = dsOn ? math.round(c.dsDist / syminfo.mintick) : 0   // 距離を最小価格刻みの整数で比べる (境界の浮動小数誤差を避ける)\n"
     "    float dHpx   = na\n"
     "    float dLpx   = na\n"
     "    bool  dHm    = false   // Day High とまとまる Swing High がある\n"
     "    bool  dLm    = false   // Day Low とまとまる Swing Low がある\n"
     "    bool  hasDH  = false\n    bool  hasDL  = false\n"
     "    bool  hzInd  = false   // まとまらない Horizontal (Swing / 前日高安など) がある\n"
     "    bool  swInd1 = false   // 時間足ごと: まとまらない Swing がある\n"
     "    bool  swInd2 = false\n    bool  swInd3 = false\n"),
    ("    int n = array.size(members)\n    for j = 0 to n - 1\n",
     "    int n = array.size(members)\n"
     "    // GBE-4: Merge Nearby のときだけ、この Cluster の Day High / Low の実際の価格を先に読む (Cluster のメンバーだけ)\n"
     "    if dsOn\n"
     "        for j = 0 to n - 1\n"
     "            RawZone q = array.get(members, j)\n"
     "            if q.srcId == \"DAY_HIGH\"\n"
     "                dHpx := q.px0\n"
     "            else if q.srcId == \"DAY_LOW\"\n"
     "                dLpx := q.px0\n"
     "    for j = 0 to n - 1\n"),
    ("        if isSwing\n            if m.srcTf == c.hzTf1\n",
     "        if isSwing\n"
     "            // GBE-4: Day High と Swing High / Day Low と Swing Low だけを比べる。pivot 価格 (最初 / 最新) のどちらかが距離以内\n"
     "            bool mH = dsOn and m.srcId == \"SWING_H\" and not na(dHpx) and (math.round(math.abs(dHpx - m.px0) / syminfo.mintick) <= dsTk or math.round(math.abs(dHpx - m.px1) / syminfo.mintick) <= dsTk)\n"
     "            bool mL = dsOn and m.srcId == \"SWING_L\" and not na(dLpx) and (math.round(math.abs(dLpx - m.px0) / syminfo.mintick) <= dsTk or math.round(math.abs(dLpx - m.px1) / syminfo.mintick) <= dsTk)\n"
     "            int  sl = m.srcTf == c.hzTf1 ? 1 : m.srcTf == c.hzTf2 ? 2 : m.srcTf == c.hzTf3 ? 3 : 0\n"
     "            dHm := dHm or mH\n"
     "            dLm := dLm or mL\n"
     "            if not mH and not mL\n"
     "                hzInd  := true\n"
     "                swInd1 := swInd1 or sl == 1\n"
     "                swInd2 := swInd2 or sl == 2\n"
     "                swInd3 := swInd3 or sl == 3\n"
     "            if m.srcTf == c.hzTf1\n"),
    ("            if m.srcCat == CAT_HZ\n                srcM := f_setBit(srcM, SRC_HZX)\n            else if m.srcId == \"MA1\"\n",
     "            if m.srcCat == CAT_HZ\n                srcM := f_setBit(srcM, SRC_HZX)\n                hzInd := true\n            else if m.srcId == \"MA1\"\n"),
    ("            else if m.srcCat == CAT_DHL\n                srcM := f_setBit(srcM, SRC_DHL)\n",
     "            else if m.srcCat == CAT_DHL\n                srcM := f_setBit(srcM, SRC_DHL)\n"
     "                hasDH := hasDH or m.srcId == \"DAY_HIGH\"\n"
     "                hasDL := hasDL or m.srcId == \"DAY_LOW\"\n"),
    ("        baseSum += math.max(accA1, math.max(accA2, accA3))\n\n",
     "        baseSum += math.max(accA1, math.max(accA2, accA3))\n\n"
     "    // GBE-4: Merge Nearby — 近い価格の Day H/L と Swing を 1 つの根拠にする\n"
     "    //   Swing 最大点 (swMax) を得ている時間足 (同点を含む) の Swing がすべて Day とまとまるなら、その根拠は max(Day 点, swMax)。\n"
     "    //   同じ点数の時間足にまとまらない Swing があれば調整しない (独立した Swing が最大点を得ている)。\n"
     "    int dsCatAdj = 0\n"
     "    if dsOn and (dHm or dLm)\n"
     "        bool top1 = swHit1 and c.scoreHz1 == swMax\n"
     "        bool top2 = swHit2 and c.scoreHz2 == swMax\n"
     "        bool top3 = swHit3 and c.scoreHz3 == swMax\n"
     "        bool blocked = (top1 and swInd1) or (top2 and swInd2) or (top3 and swInd3)\n"
     "        if not blocked and (top1 or top2 or top3)\n"
     "            baseSum -= math.min(c.scoreDayHL, swMax)\n"
     "        bool dhlInd = (hasDH and not dHm) or (hasDL and not dLm)\n"
     "        // カテゴリ: まとまった Day 側が 1 つだけで、独立した Horizontal / Day H/L が無いときだけ HZ + DHL を 1 つにする\n"
     "        if not hzInd and not dhlInd and not (dHm and dLm)\n"
     "            dsCatAdj := 1\n\n"),
    ("    int   cat = (hasMA ? 1 : 0) + (hasHZ ? 1 : 0) + (hasDHL ? 1 : 0) + (hasACC ? 1 : 0) + (hasRN ? 1 : 0)\n",
     "    int   cat = (hasMA ? 1 : 0) + (hasHZ ? 1 : 0) + (hasDHL ? 1 : 0) + (hasACC ? 1 : 0) + (hasRN ? 1 : 0) - dsCatAdj\n"),
]


def gbe_transform(src):
    out = src
    for a, b in EDITS:
        assert out.count(a) == 1, a[:80]
        out = out.replace(a, b)
    return out


def strip_gbe(text):
    """GBE-4 + GBE-2 + GBE-1 reverted -> ZoneEnginePractical/6 source."""
    out = strip_gbe3(text) if text is not None and "dsMerge" in text else text
    out = strip_gbe2(out) if out is not None and "accEdgeOnce" in out else out
    if out is None:
        return None
    for a, b in reversed(EDITS):
        if out.count(b) != 1:
            return None
        out = out.replace(b, a)
    return out


def gbe1_transform(src):
    """GBE-1 only (Library version 1)."""
    return gbe_transform(src)


def strip_gbe2(text):
    """reverse only the GBE-2 edits (-> the GBE-1 source, Library version 1, byte for byte)."""
    out = text
    for a, b in reversed(EDITS2):
        if out is None or out.count(b) != 1:
            return None
        out = out.replace(b, a)
    return out


def strip_gbe3(text):
    """reverse only the GBE-4 edits (EDITS3) (-> the GBE-2 source, Library version 2, byte for byte)."""
    out = text
    for a, b in reversed(EDITS3):
        if out is None or out.count(b) != 1:
            return None
        out = out.replace(b, a)
    return out


def build():
    out = gbe1_transform(open(os.path.join(ROOT, SRC_PATH), encoding="utf-8").read())
    for a, b in EDITS2 + EDITS3:
        assert out.count(a) == 1, a[:80]
        out = out.replace(a, b)
    return out


if __name__ == "__main__":
    open(os.path.join(ROOT, GBE_PATH), "w", encoding="utf-8").write(build())
    print("written", GBE_PATH)
