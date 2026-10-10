"""RN-1 Gate L1 — ZoneEnginePracticalRN.pine: exact transform of ZoneEnginePractical.pine @ f4b881b.

Round Number (XAUUSD psychological levels) as an Engine score-only confluence source:
  * a cluster whose final [bottom, top] contains (boundaries included) a 100-multiple gets 3 points, otherwise a
    50-multiple 2 points; one level per cluster (100 before 50; same rank -> nearest to the zone centre, tie -> lower)
  * the level is one more confluence category; srcMask bit SRC_RN = 1024; htfMask / hasHtf untouched
  * Raw Zones, clustering, zone geometry, members, Track / Touch / Break / Flip code are not touched
  * ZoneCfg.useRnSource defaults to false -> every pre-existing output is identical to the old Engine
  * Zone gets rnLevel / rnBase / rnScoreDelta / rnBaseSumExRn (RN-2: the RN-free score is rebuilt exactly as
    rnBaseSumExRn + slopeBonus + maBonus + flipBonus + confluence(catCount - 1), the old f_applyStrength order)
The old ZoneEnginePractical.pine stays byte-identical (published /2 reference).
"""
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RN_BASE_REV = "f4b881b"
OLD_PATH = "ZoneEnginePractical.pine"
RN_PATH = "ZoneEnginePracticalRN.pine"

RN_EDITS = [
    # 1. header note
    ("//  旧 ZoneEngine (Support / Resistance Zone Engine Library) をベースにした\n",
     "//  ★ RN-1 版 (Round Number 加点専用)。ZoneCfg.useRnSource = false (既定) では全出力が旧版と同一。\n"
     "//    true のとき、Cluster の最終範囲 [bottom, top] (境界を含む) に 100 の倍数があれば 3 点、無ければ\n"
     "//    50 の倍数で 2 点を Cluster ごとに1回だけ baseSum へ加え、Confluence の独立1カテゴリとして数える。\n"
     "//    Raw Zone / Cluster 構成 / Zone 上下限 / Track / Touch / Break / Flip の処理は変更しない。HTF は付けない。\n"
     "//  旧 ZoneEngine (Support / Resistance Zone Engine Library) をベースにした\n"),
    # 2. source bit
    ("int SRC_DHL   = 512    // Day High / Low\n",
     "int SRC_DHL   = 512    // Day High / Low\n"
     "int SRC_RN    = 1024   // Round Number (加点専用。Raw Zone / Cluster member ではない)\n"),
    # 3. config (Library default OFF)
    ("    float  fallbackRR         = 2.0\n",
     "    float  fallbackRR         = 2.0\n"
     "    // ---- Round Number (RN-1。加点専用。既定 OFF = 旧版と同一) ----\n"
     "    bool   useRnSource        = false\n"
     "    float  rnStepMajor        = 100.0\n"
     "    float  rnScoreMajor       = 3.0\n"
     "    float  rnStepMinor        = 50.0\n"
     "    float  rnScoreMinor       = 2.0\n"),
    # 4. zone fields
    ("    int    touchCount    = 0\n",
     "    int    touchCount    = 0\n"
     "    // Round Number 内訳 (RN-1。RN なし: rnLevel = na / rnBase = 0 / rnScoreDelta = 0 / rnBaseSumExRn = baseSum)\n"
     "    float  rnLevel       = na    // 採用した節目の価格\n"
     "    float  rnBase        = 0.0   // 加点 (3 / 2 / 0)\n"
     "    float  rnScoreDelta  = 0.0   // rnBase + Confluence 増分\n"
     "    float  rnBaseSumExRn = 0.0   // RN を加える前の baseSum (RN 抜き Score の厳密な再構築用)\n"),
    # 5. level picker
    ("//  zBot / zTop : f_buildClusters の running aggregate (min member.bottom / max member.top)\nf_finalizeCluster(",
     "// Round Number: [zBot, zTop] (境界を含む) 内の step の倍数のうち中心に最も近いもの (同距離は低い方)。無ければ na\n"
     "f_rnLevelIn(float zBot, float zTop, float step) =>\n"
     "    float lv = na\n"
     "    int k1 = math.ceil(zBot / step)\n"
     "    int k2 = math.floor(zTop / step)\n"
     "    if k1 <= k2\n"
     "        float ctr = (zTop + zBot) / 2\n"
     "        int kc = math.max(k1, math.min(k2, math.floor(ctr / step)))\n"
     "        lv := kc * step\n"
     "        if kc + 1 <= k2\n"
     "            if (kc + 1) * step - ctr < ctr - lv\n"
     "                lv := (kc + 1) * step\n"
     "    lv\n"
     "\n"
     "//  zBot / zTop : f_buildClusters の running aggregate (min member.bottom / max member.top)\nf_finalizeCluster("),
    # 6. finalize: score / category
    ("    int   cat = (hasMA ? 1 : 0) + (hasHZ ? 1 : 0) + (hasDHL ? 1 : 0) + (hasACC ? 1 : 0)\n"
     "    float confB = f_confluenceBonus(cat, c)\n",
     "    // ---- Round Number (RN-1): 1 Cluster につき最大1回。100 の倍数 (3点) を優先、無ければ 50 の倍数 (2点)\n"
     "    float baseSumEx = baseSum\n"
     "    float rnLv = na\n"
     "    float rnB  = 0.0\n"
     "    if c.useRnSource\n"
     "        float lvMaj = f_rnLevelIn(zBot, zTop, c.rnStepMajor)\n"
     "        if not na(lvMaj)\n"
     "            rnLv := lvMaj\n"
     "            rnB  := c.rnScoreMajor\n"
     "        else\n"
     "            float lvMin = f_rnLevelIn(zBot, zTop, c.rnStepMinor)\n"
     "            if not na(lvMin)\n"
     "                rnLv := lvMin\n"
     "                rnB  := c.rnScoreMinor\n"
     "    bool hasRN = rnB > 0\n"
     "    if hasRN\n"
     "        baseSum += rnB\n"
     "        srcM := f_setBit(srcM, SRC_RN)\n"
     "\n"
     "    int   cat = (hasMA ? 1 : 0) + (hasHZ ? 1 : 0) + (hasDHL ? 1 : 0) + (hasACC ? 1 : 0) + (hasRN ? 1 : 0)\n"
     "    float confB = f_confluenceBonus(cat, c)\n"
     "    float rnD   = hasRN ? rnB + (confB - f_confluenceBonus(cat - 1, c)) : 0.0\n"),
    # 7. Zone.new extra fields
    ("         srcMask = srcM, htfMask = htfM)\n",
     "         srcMask = srcM, htfMask = htfM,\n"
     "         rnLevel = rnLv, rnBase = rnB, rnScoreDelta = rnD, rnBaseSumExRn = baseSumEx)\n"),
    # 8. sourceText
    ("    s := f_join(s, f_hasBit(m, SRC_DHL), \"Day H/L\")\n    s\n",
     "    s := f_join(s, f_hasBit(m, SRC_DHL), \"Day H/L\")\n    s := f_join(s, f_hasBit(m, SRC_RN), \"Round Number\")\n    s\n"),
]


def git_show(rev, path):
    return subprocess.run(["git", "-C", ROOT, "show", f"{rev}:{path}"], capture_output=True, text=True).stdout


def rn_transform(old):
    t = old
    for a, b in RN_EDITS:
        assert t.count(a) == 1, ("RN-1 anchor not unique", a[:70], t.count(a))
        t = t.replace(a, b)
    return t


def strip_rn(src):
    """RN file -> the old Engine text (None if any RN edit is missing / duplicated)."""
    t = src
    for a, b in reversed(RN_EDITS):
        if t.count(b) != 1:
            return None
        t = t.replace(b, a)
    return t
