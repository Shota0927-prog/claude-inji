"""GBJ-1 — ZoneVisualGBPJPY.pine: OANDA:GBPJPY 5M Zone comparison indicator (no entries, no alerts).

Deterministic transform of ZoneVisualUSDJPY.pine (ZONE-JPY) by exact, unique text replacements (EDITS);
strip_gbj() applies them in reverse and must give ZONE-JPY back byte for byte (fixture gbj_sim), so the Engine /6,
Zone generation / scoring, FVG, update order, requests and non-repaint blocks are provably ZONE-JPY's.
Only these kinds of change are allowed (each EDIT is tagged and gbj_sim checks the code lines it touches):
  header    comment header
  title     indicator title / shorttitle
  input     input default / label / tooltip / group text (price inputs stay in 円)
  display   label text (unit 円 after the width)
Price-difference defaults (all [暫定]): Zone Half Width 0.03 (USDJPY verified value), Cluster Distance 0.08,
FVG Min Width 0.05; every other yen threshold is inherited unchanged from ZONE-JPY.
ZONE-JPY, ZONE-P, the Strategies and the Engines are not modified.
"""
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_PATH = "ZoneVisualUSDJPY.pine"
GBJ_PATH = "ZoneVisualGBPJPY.pine"

EDITS = [
    # ---- header / identity ---------------------------------------------------------------------------------------
    ("header",
     "//  Zone Visual USDJPY (Compare)  —  OANDA:USDJPY 5分足用 Zone 比較 Indicator (Entry なし)\n"
     "//  ZONE-P (ZoneVisualPractical, XAUUSD) と同じ Engine /6・採点式・更新順・非リペイント条件で、\n"
     "//  価格差の入力だけを円に置き換えた比較版 (生成: tests/jpy_build.py、ZONE-P との差分は fixture jpy_sim が固定)。\n"
     "//  目的: ドル円の Zone Half Width / Cluster Distance の確定。比較候補 Half Width 0.03 / 0.05 / 0.08 円、\n"
     "//  Cluster Distance 0.05 / 0.08 / 0.12 円 (初期 0.05 / 0.08)。他の円換算値は暫定 ([暫定] 表記)。\n",
     "//  Zone Visual GBPJPY (Compare)  —  OANDA:GBPJPY 5分足用 Zone 比較 Indicator (Entry / Alert なし)\n"
     "//  ZONE-JPY (ZoneVisualUSDJPY) と同じ Engine /6・Zone 生成・採点式・FVG・更新順・非リペイント条件で、\n"
     "//  表示名と円建て入力の初期値 / 説明だけを変えた比較版 (生成: tests/gbj_build.py、ZONE-JPY との差分は\n"
     "//  fixture gbj_sim が固定)。価格差の入力はすべて円 (1 pip = 0.01 円、0.05 円 = 5 pips)。\n"
     "//  初期値はすべて暫定: Half Width 0.03 / Cluster Distance 0.08 / FVG Min Width 0.05 円 (ドル円検証値)、\n"
     "//  他の円建て閾値は ZONE-JPY と同じ値。比較候補 Half Width 0.03 / 0.05 / 0.08、Cluster 0.08 / 0.12 / 0.16、\n"
     "//  FVG Min Width 0.05 / 0.08 / 0.10 円 (検証候補であり適正値ではない)。Round Number (XAUUSD 専用) は OFF。\n"),
    ("title",
     '     title            = "Zone Visual USDJPY (Compare)",\n     shorttitle       = "ZONE-JPY",\n',
     '     title            = "Zone Visual GBPJPY (Compare)",\n     shorttitle       = "ZONE-GBPJPY",\n'),
    # ---- label: width unit -----------------------------------------------------------------------------------------
    ("display",
     '// Zone の上下限と最終的な幅 (円、小数 3 桁)\n'
     'f_jpyGeom(zn.Zone z) =>\n'
     '    f_num(z.top, "#.000") + " - " + f_num(z.bottom, "#.000") + " | W " + f_num(z.top - z.bottom, "0.000")\n',
     '// Zone の上下限と最終的な幅 (円、小数 3 桁 = OANDA:GBPJPY の最小刻み 0.001。pips ではない)\n'
     'f_jpyGeom(zn.Zone z) =>\n'
     '    f_num(z.top, "#.000") + " - " + f_num(z.bottom, "#.000") + " | W " + f_num(z.top - z.bottom, "0.000") + "円"\n'),
    # ---- price-difference inputs: compared now (all [暫定]) ---------------------------------------------------------
    ("input",
     'zoneHalfWidth = input.float(0.05, "Zone Half Width (円)", minval = 0.005, step = 0.005, group = G_ZONE,\n',
     'zoneHalfWidth = input.float(0.03, "[暫定] Zone Half Width (円)", minval = 0.005, step = 0.005, group = G_ZONE,\n'),
    ("input",
     '     "USDJPY 比較候補: 0.03 / 0.05 / 0.08 円。")\n',
     '     "GBPJPY 比較候補 (検証用・適正値ではない): 0.03 / 0.05 / 0.08 円 (= 3 / 5 / 8 pips)。初期 0.03 = ドル円検証値。")\n'),
    ("input",
     'clusterDist = input.float(0.08, "Cluster Distance (円)", minval = 0.0, step = 0.005, group = G_CLU,\n'
     '     tooltip = "USDJPY 比較候補: 0.05 / 0.08 / 0.12 円。")\n',
     'clusterDist = input.float(0.08, "[暫定] Cluster Distance (円)", minval = 0.0, step = 0.005, group = G_CLU,\n'
     '     tooltip = "GBPJPY 比較候補 (検証用・適正値ではない): 0.08 / 0.12 / 0.16 円。初期 0.08 = ドル円検証値。")\n'),
    ("input",
     'enableRn = input.bool(false, "Enable Round Number (XAUUSD 専用 · USDJPY は OFF)", group = G_RN,\n',
     'enableRn = input.bool(false, "Enable Round Number (XAUUSD 専用 · GBPJPY は OFF)", group = G_RN,\n'),
    ("input",
     'fvgMinWidth = input.float(0.05, "[暫定] FVG Min Width (円)", minval = 0.0, step = 0.005, group = "02 · FVG (USDJPY)",\n'
     '     tooltip = "15M / 1H / 4H FVG の最小幅 (mintick 正規化後に以上)。XAUUSD は固定 3.0 ドル。\\n" +\n'
     '     "比較候補: 0.03 / 0.05 / 0.08 円 (暫定 0.05 = 既定 Zone Half Width と同じ比率)。")\n',
     'fvgMinWidth = input.float(0.05, "[暫定] FVG Min Width (円)", minval = 0.0, step = 0.005, group = "02 · FVG (GBPJPY)",\n'
     '     tooltip = "15M / 1H / 4H FVG の最小幅 (mintick 正規化後に以上)。XAUUSD は固定 3.0 ドル。\\n" +\n'
     '     "GBPJPY 比較候補 (検証用・適正値ではない): 0.05 / 0.08 / 0.10 円。初期 0.05 = ドル円検証値。")\n'),
]


# ---- GBJ-2: FVG Direction Match + GBPJPY Round Number (both default OFF; applied after EDITS) ----------------------
#  kinds: header (comment), fvgdir (FVG direction filter: input + candidate filter in the three FVG selections),
#         rn (GBPJPY RN inputs, step validation, Engine RN config). strip_gbj2() reverses only these -> GBJ-1 text.
RN_OLD = (
    "// ---- 2.7c Round Number (XAUUSD) ------------------------------------------\n"
    "//  Engine (ZoneEnginePractical/5) の Round Number 加点。Cluster の最終範囲 [bottom, top] (境界を含む) に\n"
    "//  100 の倍数があれば 3 点、無ければ 50 の倍数で 2 点を Cluster ごとに1回、Confluence の独立1カテゴリ。\n"
    "//  Zone の上下限 / Cluster / Raw Zone / Track は変わらない。HTF 根拠にはならない。\n"
    "//  syminfo.ticker == \"XAUUSD\" の完全一致のときだけ有効 (他の表記・他銘柄では常に無効)。\n"
    "var string G_RN = \"02 · Round Number (XAUUSD)\"\n"
    "enableRn = input.bool(false, \"Enable Round Number (XAUUSD 専用 · GBPJPY は OFF)\", group = G_RN,\n"
    "     tooltip = \"XAUUSD (ticker 完全一致) のみ。Zone 範囲に 100ドル節目があれば +3、無ければ 50ドル節目で +2。\\n\" +\n"
    "     \"Confluence の独立カテゴリとして Zone ごとに1回だけ。Zone の幅・位置は変えない。\")\n")
RN_NEW = (
    "// ---- 2.7c Round Number (GBPJPY) ------------------------------------------\n"
    "//  Engine (ZoneEnginePractical/6) の既存 Round Number 加点を円の刻みで使う (Engine は変更しない)。\n"
    "//  判定式 (Engine f_rnLevelIn): ceil(bottom / 刻み) <= floor(top / 刻み) なら Cluster の最終範囲 [bottom, top]\n"
    "//  (境界を含む) に刻みの倍数がある。許容距離は無い。大刻みを先に調べ、無いときだけ小刻み (両方該当は大刻みだけ)。\n"
    "//  Cluster ごとに最大 1 回、baseSum へ加点し Confluence の独立 1 カテゴリ。RN 単独の Zone は作らない。HTF 根拠にならない。\n"
    "//  ticker が GBPJPY のときだけ有効。刻みは 0.125 円の倍数 (2 進で正確に表せる値) に限る: 判定式は浮動小数の\n"
    "//  割り算なので、0.1 / 0.2 円などは境界ちょうどの価格で誤判定し得る (tests/gbx_sim で確認)。不正な刻みは停止して表示。\n"
    "var string G_RN = \"02 · Round Number (GBPJPY)\"\n"
    "enableRn = input.bool(false, \"Enable Round Number (GBPJPY)\", group = G_RN,\n"
    "     tooltip = \"Zone の範囲 [bottom, top] (境界を含む) に大刻みの倍数があれば大刻みの加点、無ければ小刻みの倍数で小刻みの加点。\\n\" +\n"
    "     \"Zone ごとに 1 回 (両方該当は大刻みだけ)、Confluence の独立カテゴリ。RN 単独の Zone は作らない。許容距離なし。\")\n"
    "rnMajorStep = input.float(1.0, \"[暫定] RN 大刻み (円)\", minval = 0.125, step = 0.125, group = G_RN,\n"
    "     tooltip = \"例: 1.00 円 → 210.000。0.125 円の倍数、かつ小刻みの整数倍 (2 倍以上)。\")\n"
    "rnMajorScore = input.float(3.0, \"[暫定] RN 大刻み 加点\", minval = 0.0, step = 0.5, group = G_RN)\n"
    "rnMinorStep = input.float(0.5, \"[暫定] RN 小刻み (円)\", minval = 0.125, step = 0.125, group = G_RN,\n"
    "     tooltip = \"例: 0.50 円 → 210.500。0.125 円の倍数。\")\n"
    "rnMinorScore = input.float(2.0, \"[暫定] RN 小刻み 加点\", minval = 0.0, step = 0.5, group = G_RN)\n"
    "// 刻みの検証 (価格の算術だけ)。RN ON で不正なら runtime.error で明示する (OFF のときは何もしない)\n"
    "float rnRatio  = rnMinorStep > 0 ? rnMajorStep / rnMinorStep : 0.0\n"
    "float rnMajT   = rnMajorStep / syminfo.mintick\n"
    "float rnMinT   = rnMinorStep / syminfo.mintick\n"
    "bool  rnStepOK = rnMinorStep > 0 and rnMajorStep > rnMinorStep and math.abs(rnRatio - math.round(rnRatio)) < 1e-9\n"
    "     and math.abs(rnMajT - math.round(rnMajT)) < 1e-6 and math.abs(rnMinT - math.round(rnMinT)) < 1e-6\n"
    "     and rnMajorStep * 8 == math.round(rnMajorStep * 8) and rnMinorStep * 8 == math.round(rnMinorStep * 8)\n"
    "if enableRn and not rnStepOK\n"
    "    runtime.error(\"Round Number: 刻みが不正です (小刻み > 0、大刻み = 小刻みの 2 倍以上の整数倍、どちらも最小価格刻みと 0.125 円の倍数)\")\n")
FVGDIR_INPUT_ANCHOR = '     "GBPJPY 比較候補 (検証用・適正値ではない): 0.05 / 0.08 / 0.10 円。初期 0.05 = ドル円検証値。")\n'
FVGDIR_INPUT = (
    'fvgDirMatch = input.bool(false, "FVG Direction Match", group = "02 · FVG (GBPJPY)",\n'
    '     tooltip = "OFF: 従来どおり (向きを問わず重なる FVG から最良 1 個)。\\n" +\n'
    '     "ON: SUPPORT の Zone は上昇 FVG だけ、RESIST の Zone は下降 FVG だけを候補にしてから、上位 TF 優先・同 TF は新しい方で 1 個選ぶ。\\n" +\n'
    '     "その他の State は従来どおり。FVG の保存・寿命・埋め・幅・点数・Confluence・昇格範囲の式は同じ。")\n')
SEL_OLD = ("    int best = -1\n    for s = 0 to 3 * FVG_SLOTS_PER_TF - 1\n        if array.get(gFvgAlive, s)\n"
           "            if f_fvcOverlap(z.top, z.bottom, array.get(gFvgTop, s), array.get(gFvgBot, s))\n")
SEL_NEW = ("    int best = -1\n"
           "    // FVG Direction Match: 方向で候補を絞ってから選ぶ (選んだ後に除外しない)。OFF / SUPPORT・RESIST 以外は want = 0\n"
           "    int want = fvgDirMatch ? (z.state == ST_SUPPORT ? 1 : z.state == ST_RESIST ? -1 : 0) : 0\n"
           "    for s = 0 to 3 * FVG_SLOTS_PER_TF - 1\n"
           "        if array.get(gFvgAlive, s) and (want == 0 or array.get(gFvgDir, s) == want)\n"
           "            if f_fvcOverlap(z.top, z.bottom, array.get(gFvgTop, s), array.get(gFvgBot, s))\n")

EDITS2 = [
    ("header",
     "//  FVG Min Width 0.05 / 0.08 / 0.10 円 (検証候補であり適正値ではない)。Round Number (XAUUSD 専用) は OFF。\n",
     "//  FVG Min Width 0.05 / 0.08 / 0.10 円 (検証候補であり適正値ではない)。\n"
     "//  GBJ-2 (比較用、どちらも初期 OFF = 従来と同じ結果): FVG Direction Match (SUPPORT は上昇 FVG、RESIST は下降 FVG\n"
     "//  だけを加点候補にする) と GBPJPY Round Number (大刻み 1.00 円 +3 / 小刻み 0.50 円 +2、Engine の既存 RN 加点)。\n"),
    ("rn", RN_OLD, RN_NEW),
    ("rn",
     'zoneCfg.useRnSource          := enableRn and syminfo.ticker == "XAUUSD"\n',
     'zoneCfg.rnStepMajor          := rnMajorStep\n'
     'zoneCfg.rnScoreMajor         := rnMajorScore\n'
     'zoneCfg.rnStepMinor          := rnMinorStep\n'
     'zoneCfg.rnScoreMinor         := rnMinorScore\n'
     'zoneCfg.useRnSource          := enableRn and rnStepOK and syminfo.ticker == "GBPJPY"\n'),
    ("fvgdir", FVGDIR_INPUT_ANCHOR, FVGDIR_INPUT_ANCHOR + FVGDIR_INPUT),
    ("fvgdir", "f_fvcZoneDisplay(zn.Zone z) =>\n" + SEL_OLD, "f_fvcZoneDisplay(zn.Zone z) =>\n" + SEL_NEW),
    ("fvgdir", "f_zpoBestFvg(zn.Zone z) =>\n" + SEL_OLD, "f_zpoBestFvg(zn.Zone z) =>\n" + SEL_NEW),
    ("fvgdir",
     "    int   best = -1\n    if n > 0\n        for i = 0 to n - 1\n            zn.Zone z = zn.zoneAt(zoneEng, i)\n"
     "            if z.state != ST_BROKEN\n",
     "    int   best = -1\n"
     "    int   fd   = array.get(gFvgDir, slot)     // FVG Direction Match: 向きの合わない SUPPORT / RESIST の Zone は使わない\n"
     "    if n > 0\n        for i = 0 to n - 1\n            zn.Zone z = zn.zoneAt(zoneEng, i)\n"
     "            if z.state != ST_BROKEN and (not fvgDirMatch or ((z.state != ST_SUPPORT or fd == 1) and (z.state != ST_RESIST or fd == -1)))\n"),
]


# ---- GBJ-3: GBPJPY base-setting defaults (defaults / descriptions only; applied after EDITS2) -----------------------
#  Day H/L Score 3 -> 2, Slope Threshold Moderate 0.02 -> 0.01 円 / Strong 0.05 -> 0.02 円, Strong Threshold 10 -> 9,
#  Zone Half Width 0.03 -> 0.05 円 (= the Strategy default: display and trading zones share the default setting).
#  strip_gbj3() reverses only these -> the GBJ-2 file (80d6a96) byte for byte.
EDITS3 = [
    ("header",
     "//  だけを加点候補にする) と GBPJPY Round Number (大刻み 1.00 円 +3 / 小刻み 0.50 円 +2、Engine の既存 RN 加点)。\n",
     "//  だけを加点候補にする) と GBPJPY Round Number (大刻み 1.00 円 +3 / 小刻み 0.50 円 +2、Engine の既存 RN 加点)。\n"
     "//  GBJ-3 (GBPJPY 基準設定、初期値だけ): Half Width 0.05 円 (Strategy と共通)、Day H/L Score 2、Slope Threshold\n"
     "//  Moderate 0.01 / Strong 0.02 円、Strong Threshold 9。ある比較期間の TradingView 結果から決めた値 (最適値・別期間は未確認)。\n"),
    ("default",
     'zoneHalfWidth = input.float(0.03, "[暫定] Zone Half Width (円)",',
     'zoneHalfWidth = input.float(0.05, "[暫定] Zone Half Width (円)",'),
    ("default",
     "(= 3 / 5 / 8 pips)。初期 0.03 = ドル円検証値。\")\n",
     "(= 3 / 5 / 8 pips)。初期 0.05 = GBPJPY 基準設定 (Visual / Strategy 共通)。\")\n"),
    ("default",
     'slopeThrMod = input.float(0.02, "[暫定] Slope Threshold · Moderate (円/lookback)",',
     'slopeThrMod = input.float(0.01, "[暫定] Slope Threshold · Moderate (円/lookback)",'),
    ("default",
     'slopeThrStrong = input.float(0.05, "[暫定] Slope Threshold · Strong (円/lookback)",',
     'slopeThrStrong = input.float(0.02, "[暫定] Slope Threshold · Strong (円/lookback)",'),
    ("default",
     'scoreDayHL = input.float(3.0, "Base Score · Day High / Low",',
     'scoreDayHL = input.float(2.0, "Base Score · Day High / Low",'),
    ("default",
     'thrStrong = input.float(10.0, "Strong Score Threshold",',
     'thrStrong = input.float(9.0, "Strong Score Threshold", '),
]


# ---- GBJ-4: Accum Score Mode (Sum / Max across timeframes), via the GBPJPY Engine derivative (tests/gbe_build.py) -----
#  Sum (default) = the current scoring. The import switches to ZoneEnginePracticalGBPJPY (must be published on
#  TradingView first; until then the GBPJPY scripts do not compile). strip_gbj4() reverses only these -> GBJ-3 file.
import gbe_build as _ge   # noqa: E402

EDITS4 = [
    ("header",
     "//  Moderate 0.01 / Strong 0.02 円、Strong Threshold 9。ある比較期間の TradingView 結果から決めた値 (最適値・別期間は未確認)。\n",
     "//  Moderate 0.01 / Strong 0.02 円、Strong Threshold 9。ある比較期間の TradingView 結果から決めた値 (最適値・別期間は未確認)。\n"
     "//  GBJ-4: Accum Score Mode (Sum = 従来 / Max)。Engine は GBPJPY 派生 ZoneEnginePracticalGBPJPY (/6 + Accum 時間足間\n"
     "//  の合算方式だけ、生成: tests/gbe_build.py)。TradingView で Library を publish してから使う。\n"),
    ("import", _ge.IMPORT_6, _ge.IMPORT_GBE1),
    ("accmode",
     'accKeep3 = input.int(1, "Keep Count · TF #3 Accum (instances)", minval = 1, group = G_ACC)\n',
     'accKeep3 = input.int(1, "Keep Count · TF #3 Accum (instances)", minval = 1, group = G_ACC)\n'
     'accScoreMode = input.string("Sum", "Accum Score Mode", options = ["Sum", "Max"], group = G_ACC,\n'
     '     tooltip = "時間足 (TF #1 / #2 / #3) ごとの Accum 寄与 (上限・下限はそれぞれ Zone 内 1 回のまま) をどう合わせるか。\\n" +\n'
     '     "Sum: 合計 (従来)。Max: 最大の 1 つだけ。例: 3 / 4 / 5 → Sum 12・Max 5、6 / 4 / 0 → Sum 10・Max 6。\\n" +\n'
     '     "Engine の Score / Strength / Touch / FVG 加点後 Score / Entry 資格すべてに反映 (表示だけの差し替えではない)。")\n'),
    ("accmode",
     "zoneCfg.accKeep3             := accKeep3\n",
     "zoneCfg.accKeep3             := accKeep3\n"
     "zoneCfg.accScoreMax          := accScoreMode == \"Max\"\n"),
]


# ---- GBJ-5: Accum Edge Mode (Separate = current / Once per TF), Engine derivative GBE-2 (Library version 2) ----------
#  strip_gbj5() reverses only these -> the GBJ-4 file (60cc26f) byte for byte.
EDITS5 = [
    ("header",
     "//  の合算方式だけ、生成: tests/gbe_build.py)。TradingView で Library を publish してから使う。\n",
     "//  の合算方式だけ、生成: tests/gbe_build.py)。TradingView で Library を publish してから使う。\n"
     "//  GBJ-5: Accum Edge Mode (Separate = 従来 / Once per TF = 同じ時間足の上限・下限を合わせて 1 回)。Library v2 が必要。\n"),
    ("import", _ge.IMPORT_GBE1, _ge.IMPORT_GBE2),
    ("accedge",
     '     "Engine の Score / Strength / Touch / FVG 加点後 Score / Entry 資格すべてに反映 (表示だけの差し替えではない)。")\n',
     '     "Engine の Score / Strength / Touch / FVG 加点後 Score / Entry 資格すべてに反映 (表示だけの差し替えではない)。")\n'
     'accEdgeMode = input.string("Separate", "Accum Edge Mode", options = ["Separate", "Once per TF"], group = G_ACC,\n'
     '     tooltip = "同じ時間足の Accum 上限・下限の数え方。Separate: 上限・下限をそれぞれ 1 回 (従来)。\\n" +\n'
     '     "Once per TF: その時間足の境界が Zone に 1 つ以上あれば、時間足の点数を 1 回だけ (同じ箱・別の箱を問わない)。\\n" +\n'
     '     "時間足ごとの寄与を出してから Accum Score Mode (Sum / Max) を適用。例 1H 上下限 + 4H 片側: Separate 10 / 6、Once 7 / 4。")\n'),
    ("accedge",
     'zoneCfg.accScoreMax          := accScoreMode == "Max"\n',
     'zoneCfg.accScoreMax          := accScoreMode == "Max"\n'
     'zoneCfg.accEdgeOnce          := accEdgeMode == "Once per TF"\n'),
]


# ---- GBJ-6: Day/Swing Overlap Mode (Separate = current / Deduplicate), Engine derivative GBE-3 (Library version 3) ----
#  The existing Swing requests also return the pivot bar's open time (time[len] in the requested timeframe, distinct from
#  the confirmation time); the Engine gets it through new ZoneFeed fields. No request is added. strip_gbj6() -> GBJ-5.
NRS_OLD = ("f_nrsPivotConfirmed(simple int len) =>\n"
           "    [_ph, _pt, _pl, _lt] = zn.pivotPack(len)\n"
           "    [_ph[1], _pt[1], _pl[1], _lt[1]]\n")
NRS_NEW = ("f_nrsPivotConfirmed(simple int len) =>\n"
           "    [_ph, _pt, _pl, _lt] = zn.pivotPack(len)\n"
           "    // GBJ-6: pivot 元の足の開始時刻 = time[len] (確認した足の時刻 _pt / _lt とは別)。確定 HTF 足の値 ([1]) だけ\n"
           "    int _po = na(_ph) ? int(na) : time[len]\n"
           "    int _lo = na(_pl) ? int(na) : time[len]\n"
           "    [_ph[1], _pt[1], _pl[1], _lt[1], _po[1], _lo[1]]\n\n"
           "// GBJ-6: チャート足と同じ / 下位の Swing TF 用 (zn.pivotPack の値はそのまま + pivot 元の足の開始時刻)\n"
           "f_swPack(simple int len) =>\n"
           "    [_ph, _pt, _pl, _lt] = zn.pivotPack(len)\n"
           "    int _po = na(_ph) ? int(na) : time[len]\n"
           "    int _lo = na(_pl) ? int(na) : time[len]\n"
           "    [_ph, _pt, _pl, _lt, _po, _lo]\n")
SWG_OLD = ("f_nrsSwing(simple string tf, simple int len) =>\n"
           "    float h  = na\n    int   ht = na\n    float l  = na\n    int   lt = na\n"
           "    if timeframe.in_seconds(tf) > timeframe.in_seconds()\n"
           "        [_a, _at, _b, _bt] = request.security(syminfo.tickerid, tf, f_nrsPivotConfirmed(len), lookahead = barmerge.lookahead_on)\n"
           "        h  := _a\n        ht := _at\n        l  := _b\n        lt := _bt\n"
           "    else\n"
           "        [_a, _at, _b, _bt] = request.security(syminfo.tickerid, tf, zn.pivotPack(len), lookahead = barmerge.lookahead_off)\n"
           "        h  := _a\n        ht := _at\n        l  := _b\n        lt := _bt\n"
           "    [h, ht, l, lt]\n")
SWG_NEW = ("f_nrsSwing(simple string tf, simple int len) =>\n"
           "    float h  = na\n    int   ht = na\n    float l  = na\n    int   lt = na\n"
           "    int   ho = na\n    int   lo = na\n"
           "    if timeframe.in_seconds(tf) > timeframe.in_seconds()\n"
           "        [_a, _at, _b, _bt, _ao, _bo] = request.security(syminfo.tickerid, tf, f_nrsPivotConfirmed(len), lookahead = barmerge.lookahead_on)\n"
           "        h  := _a\n        ht := _at\n        l  := _b\n        lt := _bt\n        ho := _ao\n        lo := _bo\n"
           "    else\n"
           "        [_a, _at, _b, _bt, _ao, _bo] = request.security(syminfo.tickerid, tf, f_swPack(len), lookahead = barmerge.lookahead_off)\n"
           "        h  := _a\n        ht := _at\n        l  := _b\n        lt := _bt\n        ho := _ao\n        lo := _bo\n"
           "    [h, ht, l, lt, ho, lo]\n")
FEED_OLD = ("int   pl3T = na\nif is5mChart and useHzSource\n"
            "    [_h1, _h1t, _l1, _l1t] = request.security(syminfo.tickerid, hzTf1, zn.pivotPack(pivLen1), lookahead = barmerge.lookahead_off)\n"
            "    [_h2, _h2t, _l2, _l2t] = f_nrsSwing(hzTf2, pivLen2)\n"
            "    [_h3, _h3t, _l3, _l3t] = f_nrsSwing(hzTf3, pivLen3)\n")
FEED_NEW = ("int   pl3T = na\n"
            "int   ph1O = na     // GBJ-6: pivot 元の足の開始時刻 (TF #1 / #2 / #3)\n"
            "int   pl1O = na\nint   ph2O = na\nint   pl2O = na\nint   ph3O = na\nint   pl3O = na\n"
            "if is5mChart and useHzSource\n"
            "    [_h1, _h1t, _l1, _l1t, _h1o, _l1o] = request.security(syminfo.tickerid, hzTf1, f_swPack(pivLen1), lookahead = barmerge.lookahead_off)\n"
            "    [_h2, _h2t, _l2, _l2t, _h2o, _l2o] = f_nrsSwing(hzTf2, pivLen2)\n"
            "    [_h3, _h3t, _l3, _l3t, _h3o, _l3o] = f_nrsSwing(hzTf3, pivLen3)\n"
            "    ph1O := _h1o\n    pl1O := _l1o\n    ph2O := _h2o\n    pl2O := _l2o\n    ph3O := _h3o\n    pl3O := _l3o\n")

EDITS6 = [
    ("header",
     "//  GBJ-5: Accum Edge Mode (Separate = 従来 / Once per TF = 同じ時間足の上限・下限を合わせて 1 回)。Library v2 が必要。\n",
     "//  GBJ-5: Accum Edge Mode (Separate = 従来 / Once per TF = 同じ時間足の上限・下限を合わせて 1 回)。Library v2 が必要。\n"
     "//  GBJ-6: Day/Swing Overlap Mode (Separate = 従来 / Deduplicate = 当日高安と同じ元の確定 Swing を 1 つの根拠に)。Library v3。\n"),
    ("import", _ge.IMPORT_GBE2, _ge.IMPORT_GBE),
    ("dsmode",
     'lifePrevDayHL = input.float(5.0, "Lifetime · Carried Prev Day H/L (days)", step = 1.0, group = G_DHL)\n',
     'lifePrevDayHL = input.float(5.0, "Lifetime · Carried Prev Day H/L (days)", step = 1.0, group = G_DHL)\n'
     'dsMode = input.string("Separate", "Day/Swing Overlap Mode", options = ["Separate", "Deduplicate"], group = G_DHL,\n'
     '     tooltip = "Separate: 従来どおり Day H/L と Swing を別々に採点。\\n" +\n'
     '     "Deduplicate: 当日高値 / 安値と、それを元にした確定 Swing (同じ元の足・同じ価格・同じ高安) を 1 つの根拠として、\\n" +\n'
     '     "高い方の点数・1 カテゴリで数える。同価格の別の足・近い価格・別日の Swing は別根拠のまま。")\n'),
    ("dsmode",
     'zoneCfg.accEdgeOnce          := accEdgeMode == "Once per TF"\n',
     'zoneCfg.accEdgeOnce          := accEdgeMode == "Once per TF"\n'
     'zoneCfg.dsDedup              := dsMode == "Deduplicate"\n'
     'zoneCfg.hzMs1                := timeframe.in_seconds(hzTf1) * 1000\n'
     'zoneCfg.hzMs2                := timeframe.in_seconds(hzTf2) * 1000\n'
     'zoneCfg.hzMs3                := timeframe.in_seconds(hzTf3) * 1000\n'),
    ("origin", NRS_OLD, NRS_NEW),
    ("origin", SWG_OLD, SWG_NEW),
    ("origin", FEED_OLD, FEED_NEW),
    ("origin",
     "     ph3 = ph3, ph3t = ph3T, pl3 = pl3, pl3t = pl3T,\n",
     "     ph3 = ph3, ph3t = ph3T, pl3 = pl3, pl3t = pl3T,\n"
     "     ph1o = ph1O, pl1o = pl1O, ph2o = ph2O, pl2o = pl2O, ph3o = ph3O, pl3o = pl3O,\n"),
]


def git_show(rev, path=SRC_PATH):
    return subprocess.run(["git", "-C", ROOT, "show", f"{rev}:{path}"], capture_output=True, text=True).stdout


def _apply(src, edits):
    out = src
    for _, a, b in edits:
        assert out.count(a) == 1, a[:80]
        out = out.replace(a, b)
    return out


def _revert(text, edits):
    out = text
    for _, a, b in reversed(edits):
        if out is None or out.count(b) != 1:
            return None
        out = out.replace(b, a)
    return out


def gbj1_transform(src):
    """GBJ-1 only (the version before GBJ-2)."""
    return _apply(src, EDITS)


def gbj_transform(src):
    return _apply(_apply(_apply(_apply(_apply(gbj1_transform(src), EDITS2), EDITS3), EDITS4), EDITS5), EDITS6)


def strip_gbj6(gbj):
    """reverse only the GBJ-6 Day/Swing Overlap edits (-> the GBJ-5 file byte for byte)."""
    return _revert(gbj, EDITS6)


def strip_gbj5(gbj):
    """reverse the GBJ-6 and GBJ-5 edits (-> the GBJ-4 file byte for byte)."""
    return _revert(strip_gbj6(gbj), EDITS5)


def strip_gbj4(gbj):
    """reverse the GBJ-5 and GBJ-4 edits (-> the GBJ-3 file byte for byte)."""
    return _revert(strip_gbj5(gbj), EDITS4)


def strip_gbj3(gbj):
    """reverse the GBJ-4 and GBJ-3 edits (-> the GBJ-2 file byte for byte)."""
    return _revert(strip_gbj4(gbj), EDITS3)


def strip_gbj2(gbj):
    """reverse the GBJ-3 and GBJ-2 edits (-> the GBJ-1 file byte for byte)."""
    return _revert(strip_gbj3(gbj), EDITS2)


def strip_gbj(gbj):
    return _revert(strip_gbj2(gbj), EDITS)


def build():
    return gbj_transform(open(os.path.join(ROOT, SRC_PATH), encoding="utf-8").read())


if __name__ == "__main__":
    open(os.path.join(ROOT, GBJ_PATH), "w", encoding="utf-8").write(build())
    print("written", GBJ_PATH)
