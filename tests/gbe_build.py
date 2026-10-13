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
# The version is assigned by TradingView on the first publish (expected 1). If it differs, change it here and rebuild.
IMPORT_GBE = "import sekine3310/ZoneEnginePracticalGBPJPY/1 as zn\n"

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


def gbe_transform(src):
    out = src
    for a, b in EDITS:
        assert out.count(a) == 1, a[:80]
        out = out.replace(a, b)
    return out


def strip_gbe(text):
    out = text
    for a, b in reversed(EDITS):
        if out.count(b) != 1:
            return None
        out = out.replace(b, a)
    return out


def build():
    return gbe_transform(open(os.path.join(ROOT, SRC_PATH), encoding="utf-8").read())


if __name__ == "__main__":
    open(os.path.join(ROOT, GBE_PATH), "w", encoding="utf-8").write(build())
    print("written", GBE_PATH)
