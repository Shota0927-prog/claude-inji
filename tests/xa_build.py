"""XA-1 — Gold (XAUUSD 5M) comparison defaults: ZoneStrategyXAU.pine (ZONE-ST) and ZoneVisualPractical.pine (ZONE-P).

Defaults only (the user's current TradingView comparison setting, still under comparison — not optimised, future validity
not confirmed). Shared Zone inputs in both files: Zone Half Width 3 -> 6, Break Buffer 5 -> 10 (Cluster Distance 5 and Flip
Confirm Distance 10 already match). Strategy only: Entry Mode D -> C: Candle Pattern, Direction Both -> Short Only, opposite-
zone TP ON -> OFF (SL Buffer 3, fixed RR 1.5, breakeven OFF already match). Capital 10,000, currency, fixed qty 1, Engine /
import, logic, alerts and every other input are unchanged.
XA-2 (Strategy only, applied after XA-1; strip_strategy2() reverses only XA-2 -> the XA-1 Strategy of 2732772): position
size. Initial capital 300,000 JPY in JPY; fixed (simple) loss budget 元金基準額 300,000 x 3 % = 9,000 JPY, converted to the
symbol currency (USD) with strategy.convert_to_symbol; lot = USD budget / (SL distance x ounces per lot) floored to the lot
step (1 lot = 100 oz, min / step 0.01), one step less if the floored loss exceeds the budget; qty = lot x ounces per lot /
syminfo.pointvalue (so SL distance x qty x pointvalue = the planned USD loss); invalid / below the minimum -> no order (and
no order / Track state written). qty is passed on both the limit (A) and the market (B / C / D) entry.
XA-3 (applied after XA-1 on ZONE-P and after XA-2 on ZONE-ST; strip_visual3() / strip_strategy3() reverse only XA-3 ->
the files of 69e6f0c): the Gold Short adopted defaults (検証継続中の初期値). Shared Zone inputs in both files: Flip Confirm
Distance 10 -> 5, Base Score MA #1 / #2 2 -> 3, Slope Bonus Aggregation Sum (per MA) -> Max (every other table value already
matches). Strategy only: SL Buffer 3 -> 1.5. The header comments that described the XA-1 values are rewritten to the current
values. Sizing (XA-2), Engine / import, logic, alerts, breakeven trigger and every other input unchanged.
Each strip_*() reverses the edits and must give the files of BASE_REV back byte for byte (fixture xa_sim). The older
fixtures that pin ZONE-P / ZONE-ST read them through pre_xa() (the XA-1 edits reverted) and accept them in their "unchanged"
checks only when they differ exactly by XA-1.
"""
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIS_PATH, STR_PATH = "ZoneVisualPractical.pine", "ZoneStrategyXAU.pine"
XA_FILES = (VIS_PATH, STR_PATH)
BASE_REV = "f253890"
NOTE = "比較継続中の初期値 (ユーザーの XAUUSD 5分足比較設定。最適化完了・将来の有効性確認済みではない)"

ZONE_EDITS = [
    ("default",
     'zoneHalfWidth = input.float(3.0, "Zone Half Width ($)", minval = 0.1, step = 0.5, group = G_ZONE,\n',
     'zoneHalfWidth = input.float(6.0, "Zone Half Width ($)", minval = 0.1, step = 0.5, group = G_ZONE,\n'),
    ("default",
     'breakBuffer = input.float(5.0,  "Break Buffer ($)",         step = 0.5, group = G_BF)\n',
     'breakBuffer = input.float(10.0,  "Break Buffer ($)",         step = 0.5, group = G_BF)\n'),
]
VISUAL_EDITS = [
    ("header",
     "//  Zone Visual (Practical)  —  ZoneEnginePractical 表示専用 Indicator\n",
     "//  Zone Visual (Practical)  —  ZoneEnginePractical 表示専用 Indicator\n"
     "//  XA-1: Zone Half Width 6 / Break Buffer 10 USD (Cluster 5 / Flip 10 は従来どおり) = " + NOTE + "。\n"),
] + ZONE_EDITS
STRATEGY_EDITS = [
    ("header",
     "//  Zone Strategy XAU  —  ZONE-P (ZoneVisualPractical) の Zone 判定をそのまま使う XAUUSD 5分足 Strategy\n",
     "//  Zone Strategy XAU  —  ZONE-P (ZoneVisualPractical) の Zone 判定をそのまま使う XAUUSD 5分足 Strategy\n"
     "//  XA-1: " + NOTE + ": Zone Half Width 6 / Cluster 5 / Break Buffer 10 /\n"
     "//  Flip 10 USD (Zone は ZONE-P と共通)、Entry C: Candle Pattern、Short Only、SL Buffer 3、固定 RR 1.5、反対側 Zone TP OFF、\n"
     "//  建値移動 OFF。初期資金 10,000・数量 1 固定は従来どおり (資金管理は未追加)。\n"),
] + ZONE_EDITS + [
    ("default",
     'stMode = input.string("D: 1M BOS Rebound", "Entry Mode",\n',
     'stMode = input.string("C: Candle Pattern", "Entry Mode",\n'),
    ("default",
     'stDir = input.string("Both", "Direction", options = ["Long Only", "Short Only", "Both"], group = G_ST)\n',
     'stDir = input.string("Short Only", "Direction", options = ["Long Only", "Short Only", "Both"], group = G_ST)\n'),
    ("default",
     'stTpZone = input.bool(true, "TP · Nearest Opposite Zone (Medium+)", group = G_STT)\n',
     'stTpZone = input.bool(false, "TP · Nearest Opposite Zone (Medium+)", group = G_STT)\n'),
]


# ---- XA-3: Gold Short adopted defaults (ZONE-P after XA-1, ZONE-ST after XA-2) ---------------------------------------
NOTE3 = "Gold Short の比較から採用した、検証継続中の初期値 (最適化完了・Long での検証・将来の有効性確認済みではない)"
VALUES3 = ("Zone Half Width 6 / Cluster 5 / Break Buffer 10 / Flip 5 USD、Score 閾値 5 / 10 / 15、MA Base 3 / 3、\n"
           "//  Slope 閾値 1 / 3・Bonus 0 / 1 / 2・集計 Max、Day H/L 3、Accum 3 / 4 / 5、Swing 1 / 2 / 3、Confluence 1 / 2 / 3、RN ON")
ZONE_EDITS3 = [
    ("default",
     'scoreMa1 = input.float(2.0, "Base Score · MA #1", step = 0.5, group = G_MA)\n',
     'scoreMa1 = input.float(3.0, "Base Score · MA #1", step = 0.5, group = G_MA)\n'),
    ("default",
     'scoreMa2 = input.float(2.0, "Base Score · MA #2", step = 0.5, group = G_MA)\n',
     'scoreMa2 = input.float(3.0, "Base Score · MA #2", step = 0.5, group = G_MA)\n'),
    ("default",
     'slopeBonusMode = input.string("Sum (per MA)", "Slope Bonus Aggregation in Cluster",\n',
     'slopeBonusMode = input.string("Max", "Slope Bonus Aggregation in Cluster",\n'),
    ("default",
     'flipConfirmDist = input.float(10.0, "Flip Confirm Distance ($)", step = 0.5, group = G_BF)\n',
     'flipConfirmDist = input.float(5.0, "Flip Confirm Distance ($)", step = 0.5, group = G_BF)\n'),
]
VISUAL_EDITS3 = [
    ("header",
     "//  XA-1: Zone Half Width 6 / Break Buffer 10 USD (Cluster 5 / Flip 10 は従来どおり) = 比較継続中の初期値 (ユーザーの XAUUSD 5分足比較設定。最適化完了・将来の有効性確認済みではない)。\n",
     "//  XA-3: " + NOTE3 + ":\n//  " + VALUES3 + "\n"
     "//  (Strategy の Zone 入力と共通。売買設定は Strategy 側のみ。XA-1 からの変更: Flip 10→5、MA Base 2→3、Slope 集計 Sum→Max)。\n"),
] + ZONE_EDITS3
STRATEGY_EDITS3 = [
    ("header",
     "//  XA-1: 比較継続中の初期値 (ユーザーの XAUUSD 5分足比較設定。最適化完了・将来の有効性確認済みではない): Zone Half Width 6 / Cluster 5 / Break Buffer 10 /\n"
     "//  Flip 10 USD (Zone は ZONE-P と共通)、Entry C: Candle Pattern、Short Only、SL Buffer 3、固定 RR 1.5、反対側 Zone TP OFF、\n"
     "//  建値移動 OFF。初期資金 10,000・数量 1 固定は従来どおり (資金管理は未追加)。\n",
     "//  XA-3: " + NOTE3 + ":\n//  " + VALUES3 + " (Zone は ZONE-P と共通)、\n"
     "//  Entry C: Candle Pattern、Short Only、SL Buffer 1.5、固定 RR 1.5、反対側 Zone TP OFF、建値移動 OFF (Trigger は現行値のまま)。\n"
     "//  (XA-1 からの変更: Flip 10→5、MA Base 2→3、Slope 集計 Sum→Max、SL Buffer 3→1.5)\n"),
] + ZONE_EDITS3 + [
    ("default",
     'stBuffer = input.float(3.0, "SL Buffer ($)", minval = 0.0, step = 0.5, group = G_ST)\n',
     'stBuffer = input.float(1.5, "SL Buffer ($)", minval = 0.0, step = 0.5, group = G_ST)\n'),
]


# ---- XA-4: settings parity with the other symbols (Engine ZoneEnginePracticalXAUUSD; applied after XA-3) -------------
#  Engine: ZoneEnginePracticalXAUUSD.pine = ZoneEnginePractical/6 (ZoneEnginePracticalSwingMax.pine) + the three GBPJPY
#  derivative layers of tests/gbe_build.py (GBE-1 Accum Score Mode, GBE-2 Accum Edge Mode, GBE-4 Day/Swing Overlap Mode +
#  Merge Distance) — i.e. gbe_build.build() — with only the library name and one header comment changed.
#  Visual / Strategy (shared): import /1 of the new library; inputs + config for the three modes (defaults Sum / Separate /
#  Separate, Merge Distance 0 = inert under Separate); FVG Min Width input (3.0 = the former constant); FVG Direction Match
#  (OFF) in the candidate condition of every FVG selection; RN steps / scores as inputs (100 +3 / 50 +2 = the former Engine
#  defaults) with a step check. Visual only: Zone top / bottom / width label (display only). strip_*4() -> the 17d1ca2 files.
import gbe_build as _ge   # noqa: E402
import gbj_build as _gbj  # noqa: E402

ENG_PATH = "ZoneEnginePracticalXAUUSD.pine"
ENG_LIB = "ZoneEnginePracticalXAUUSD"
IMPORT_6 = "import sekine3310/ZoneEnginePractical/6 as zn\n"
# first publish of the new library = version 1. If TradingView assigns another number, change IMPORT_XAE and rebuild
# (python3 tests/xa_build.py).
IMPORT_XAE = "import sekine3310/ZoneEnginePracticalXAUUSD/1 as zn\n"
ENGINE_EDITS = [
    ("header",
     "//  ZoneEnginePractical  —  Practical Zone v1 (Support / Resistance Zone Engine)\n",
     "//  ZoneEnginePractical  —  Practical Zone v1 (Support / Resistance Zone Engine)\n"
     "//  ★ XAUUSD 専用 (ZoneEnginePracticalXAUUSD、生成: tests/xa_build.py、XA-4)。ZoneEnginePractical/6 のソース\n"
     "//    (ZoneEnginePracticalSwingMax.pine) に、GBPJPY 派生で実装済みの Accum Score Mode (GBE-1) / Accum Edge Mode (GBE-2) /\n"
     "//    Day/Swing Overlap Mode + Merge Distance (GBE-4) を同じ式で加えたもの (= ZoneEnginePracticalGBPJPY.pine と同じ処理・\n"
     "//    公開 API で、違いは Library 名だけ)。既定 (Sum / Separate / Separate) では /6 と同じ加算を同じ順序で行う。\n"
     "//    以下の「GBPJPY 派生」等は移植元の説明 (履歴)。\n"),
    ("name",
     'library("' + _ge.LIB_NAME + '", overlay = true)\n',
     'library("' + ENG_LIB + '", overlay = true)\n'),
]

NOTE4 = "比較用の設定を他銘柄版と揃えたもの (初期値は現行ゴールドと同じ計算になる値。新しい採用値ではない)"
HEADER4 = (
    "//  XA-4: " + NOTE4 + "。\n"
    "//  Engine は ZoneEnginePracticalXAUUSD (/6 + Accum Score Mode / Accum Edge Mode / Day/Swing Overlap Mode、生成: tests/xa_build.py)。\n"
    "//  追加入力: Accum Score Sum・Accum Edge Separate・Day/Swing Separate (Merge Distance 0 は Separate では作用しない)・\n"
    "//  FVG Min Width 3.0 USD・FVG Direction Match OFF・RN 大刻み 100 (+3) / 小刻み 50 (+2)。\n")
RN4_OLD = (
    "// ---- 2.7c Round Number (XAUUSD) ------------------------------------------\n"
    "//  Engine (ZoneEnginePractical/5) の Round Number 加点。Cluster の最終範囲 [bottom, top] (境界を含む) に\n"
    "//  100 の倍数があれば 3 点、無ければ 50 の倍数で 2 点を Cluster ごとに1回、Confluence の独立1カテゴリ。\n"
    "//  Zone の上下限 / Cluster / Raw Zone / Track は変わらない。HTF 根拠にはならない。\n"
    "//  syminfo.ticker == \"XAUUSD\" の完全一致のときだけ有効 (他の表記・他銘柄では常に無効)。\n"
    "var string G_RN = \"02 · Round Number (XAUUSD)\"\n"
    "enableRn = input.bool(true, \"Enable Round Number\", group = G_RN,\n"
    "     tooltip = \"XAUUSD (ticker 完全一致) のみ。Zone 範囲に 100ドル節目があれば +3、無ければ 50ドル節目で +2。\\n\" +\n"
    "     \"Confluence の独立カテゴリとして Zone ごとに1回だけ。Zone の幅・位置は変えない。\")\n")
RN4_NEW = (
    "// ---- 2.7c Round Number (XAUUSD) ------------------------------------------\n"
    "//  Engine (ZoneEnginePracticalXAUUSD、/6 の RN-1 と同じ処理) の Round Number 加点。Cluster の最終範囲 [bottom, top]\n"
    "//  (境界を含む) に大刻みの倍数があれば大刻みの加点、無ければ小刻みの倍数で小刻みの加点を Cluster ごとに1回、\n"
    "//  Confluence の独立1カテゴリ。Zone の上下限 / Cluster / Raw Zone / Track は変わらない。RN 単独の Zone は作らない。\n"
    "//  HTF 根拠にはならない。syminfo.ticker == \"XAUUSD\" の完全一致のときだけ有効 (他の表記・他銘柄では常に無効)。\n"
    "//  XA-4: 刻み・加点を入力化 (初期 100 / +3、50 / +2 = 従来の Engine 既定値)。包含判定は従来どおり Engine f_rnLevelIn\n"
    "//  (価格の浮動小数の割り算。100 / 50 は 2 進で正確に表せる)。不正な刻みは停止して表示。\n"
    "var string G_RN = \"02 · Round Number (XAUUSD)\"\n"
    "enableRn = input.bool(true, \"Enable Round Number\", group = G_RN,\n"
    "     tooltip = \"XAUUSD (ticker 完全一致) のみ。Zone 範囲に大刻みの節目があれば大刻みの加点、無ければ小刻みの節目で小刻みの加点\\n\" +\n"
    "     \"(初期 100ドル +3 / 50ドル +2)。Confluence の独立カテゴリとして Zone ごとに1回だけ。Zone の幅・位置は変えない。\")\n"
    "rnMajorStep = input.float(100.0, \"RN 大刻み ($)\", minval = 0.01, step = 10.0, group = G_RN,\n"
    "     tooltip = \"USD の価格間隔。例: 100 → 2,700.000。最小価格刻みの整数倍、かつ小刻みの整数倍 (2 倍以上)。\")\n"
    "rnMajorScore = input.float(3.0, \"RN 大刻み 加点\", minval = 0.0, step = 0.5, group = G_RN)\n"
    "rnMinorStep = input.float(50.0, \"RN 小刻み ($)\", minval = 0.01, step = 10.0, group = G_RN,\n"
    "     tooltip = \"USD の価格間隔。例: 50 → 2,750.000。最小価格刻みの整数倍。\")\n"
    "rnMinorScore = input.float(2.0, \"RN 小刻み 加点\", minval = 0.0, step = 0.5, group = G_RN)\n"
    "// 刻みの検証 (最小価格刻みの整数で比べる)。RN ON で不正なら runtime.error で明示する (OFF のときは何もしない)\n"
    "//  小刻み > 0、大刻み = 小刻みの 2 倍以上の整数倍、どちらも最小価格刻みの整数倍 (1e-6 tick は計算誤差の吸収だけ)\n"
    "float rnMajT   = rnMajorStep / syminfo.mintick\n"
    "float rnMinT   = rnMinorStep / syminfo.mintick\n"
    "int   rnMajI   = math.round(rnMajT)\n"
    "int   rnMinI   = math.round(rnMinT)\n"
    "bool  rnStepOK = rnMinorStep > 0 and math.abs(rnMajT - rnMajI) < 1e-6 and math.abs(rnMinT - rnMinI) < 1e-6\n"
    "     and rnMinI > 0 and rnMajI >= 2 * rnMinI and rnMajI % math.max(rnMinI, 1) == 0\n"
    "if enableRn and not rnStepOK\n"
    "    runtime.error(\"Round Number: 刻みが不正です (小刻み > 0、大刻み = 小刻みの 2 倍以上の整数倍、どちらも最小価格刻みの整数倍)\")\n")
FVG4_OLD = "float  FVG_MIN_WIDTH    = 3.0\n"
FVG4_NEW = (
    "fvgMinWidth = input.float(3.0, \"FVG Min Width ($)\", minval = 0.0, step = 0.5, group = \"02 · FVG (XAUUSD)\",\n"
    "     tooltip = \"15M / 1H / 4H FVG の最小幅 (USD、mintick 正規化後に以上)。初期 3.0 = 従来の固定値。\\n\" +\n"
    "     \"検知・保存・完全埋め・寿命の処理は同じ。\")\n"
    "fvgDirMatch = input.bool(false, \"FVG Direction Match\", group = \"02 · FVG (XAUUSD)\",\n"
    "     tooltip = \"OFF: 従来どおり (向きを問わず重なる FVG から最良 1 個)。\\n\" +\n"
    "     \"ON: SUPPORT の Zone は上昇 FVG だけ、RESIST の Zone は下降 FVG だけを候補にしてから、上位 TF 優先・同 TF は新しい方で 1 個選ぶ。\\n\" +\n"
    "     \"その他の State は従来どおり。FVG の保存・寿命・埋め・幅・点数・Confluence・昇格範囲の式は同じ。\")\n"
    "float  FVG_MIN_WIDTH    = fvgMinWidth\n")
ZONE_EDITS4 = [
    ("import", IMPORT_6, IMPORT_XAE),
    ("dsmode",
     'lifePrevDayHL = input.float(5.0, "Lifetime · Carried Prev Day H/L (days)", step = 1.0, group = G_DHL)\n',
     'lifePrevDayHL = input.float(5.0, "Lifetime · Carried Prev Day H/L (days)", step = 1.0, group = G_DHL)\n'
     'dsMode = input.string("Separate", "Day/Swing Overlap Mode", options = ["Separate", "Merge Nearby"], group = G_DHL,\n'
     '     tooltip = "Separate: 従来どおり Day H/L と Swing を別々に採点。\\n" +\n'
     '     "Merge Nearby: 同じ Zone 内で、当日高値と Swing High (安値と Swing Low) の価格差が Merge Distance 以内なら\\n" +\n'
     '     "1 つの根拠として、高い方の点数・1 カテゴリで数える。時刻・日付は問わない。前日 H/L は対象外。")\n'
     'dsDist = input.float(0.0, "Day/Swing Merge Distance ($)", minval = 0.0, step = 0.5, group = G_DHL,\n'
     '     tooltip = "Merge Nearby の価格差 (USD、Cluster Distance とは別)。0 = 完全に同じ価格だけ。\\n" +\n'
     '     "初期 0 は Merge Nearby の採用値ではない: 初期の Separate では使われず、結果に作用しない。")\n'),
    ("accmode",
     'accKeep3 = input.int(1, "Keep Count · TF #3 Accum (instances)", minval = 1, group = G_ACC)\n',
     'accKeep3 = input.int(1, "Keep Count · TF #3 Accum (instances)", minval = 1, group = G_ACC)\n'
     'accScoreMode = input.string("Sum", "Accum Score Mode", options = ["Sum", "Max"], group = G_ACC,\n'
     '     tooltip = "時間足 (TF #1 / #2 / #3) ごとの Accum 寄与 (上限・下限はそれぞれ Zone 内 1 回のまま) をどう合わせるか。\\n" +\n'
     '     "Sum: 合計 (従来)。Max: 最大の 1 つだけ。例: 3 / 4 / 5 → Sum 12・Max 5、6 / 4 / 0 → Sum 10・Max 6。\\n" +\n'
     '     "Engine の Score / Strength / Touch / FVG 加点後 Score / Entry 資格すべてに反映。MA Slope Bonus の集計 (Max) とは別の設定。")\n'
     'accEdgeMode = input.string("Separate", "Accum Edge Mode", options = ["Separate", "Once per TF"], group = G_ACC,\n'
     '     tooltip = "同じ時間足の Accum 上限・下限の数え方。Separate: 上限・下限をそれぞれ 1 回 (従来)。\\n" +\n'
     '     "Once per TF: その時間足の境界が Zone に 1 つ以上あれば、時間足の点数を 1 回だけ (同じ箱・別の箱を問わない)。\\n" +\n'
     '     "時間足ごとの寄与を出してから Accum Score Mode (Sum / Max) を適用。例 1H 上下限 + 4H 片側 (3 / 4): Separate 10 / 6、Once 7 / 4。")\n'),
    ("accmode",
     "zoneCfg.accKeep3             := accKeep3\n",
     "zoneCfg.accKeep3             := accKeep3\n"
     "zoneCfg.accScoreMax          := accScoreMode == \"Max\"\n"
     "zoneCfg.accEdgeOnce          := accEdgeMode == \"Once per TF\"\n"
     "zoneCfg.dsMerge              := dsMode == \"Merge Nearby\"\n"
     "zoneCfg.dsDist               := dsDist\n"),
    ("rn", RN4_OLD, RN4_NEW),
    ("rn",
     'zoneCfg.useRnSource          := enableRn and syminfo.ticker == "XAUUSD"\n',
     'zoneCfg.rnStepMajor          := rnMajorStep\n'
     'zoneCfg.rnScoreMajor         := rnMajorScore\n'
     'zoneCfg.rnStepMinor          := rnMinorStep\n'
     'zoneCfg.rnScoreMinor         := rnMinorScore\n'
     'zoneCfg.useRnSource          := enableRn and rnStepOK and syminfo.ticker == "XAUUSD"\n'),
    ("fvg", FVG4_OLD, FVG4_NEW),
    ("fvgdir", "f_fvcZoneDisplay(zn.Zone z) =>\n" + _gbj.SEL_OLD, "f_fvcZoneDisplay(zn.Zone z) =>\n" + _gbj.SEL_NEW),
    ("fvgdir", "f_zpoBestFvg(zn.Zone z) =>\n" + _gbj.SEL_OLD, "f_zpoBestFvg(zn.Zone z) =>\n" + _gbj.SEL_NEW),
]
GEOM4 = (
    "\n// XA-4: 統合後の Zone の上下限 (format.mintick の桁) と実際の幅 top - bottom (USD)。Half Width × 2 ではない\n"
    "f_usdGeom(zn.Zone z) =>\n"
    "    f_num(z.top, format.mintick) + \" - \" + f_num(z.bottom, format.mintick) + \" | W \" + f_num(z.top - z.bottom, format.mintick) + \" USD\"\n")
VISUAL_EDITS4 = [
    ("header",
     "//  (Strategy の Zone 入力と共通。売買設定は Strategy 側のみ。XA-1 からの変更: Flip 10→5、MA Base 2→3、Slope 集計 Sum→Max)。\n",
     "//  (Strategy の Zone 入力と共通。売買設定は Strategy 側のみ。XA-1 からの変更: Flip 10→5、MA Base 2→3、Slope 集計 Sum→Max)。\n"
     + HEADER4 + "//  Visual のみ: Label に統合後 Zone の上下限 / 幅 (USD) を表示 (初期 ON、表示だけ)。\n"),
] + ZONE_EDITS4 + [
    ("fvgdir",
     "    int   best = -1\n    if n > 0\n        for i = 0 to n - 1\n            zn.Zone z = zn.zoneAt(zoneEng, i)\n"
     "            if z.state != ST_BROKEN\n",
     "    int   best = -1\n"
     "    int   fd   = array.get(gFvgDir, slot)     // FVG Direction Match: 向きの合わない SUPPORT / RESIST の Zone は使わない\n"
     "    if n > 0\n        for i = 0 to n - 1\n            zn.Zone z = zn.zoneAt(zoneEng, i)\n"
     "            if z.state != ST_BROKEN and (not fvgDirMatch or ((z.state != ST_SUPPORT or fd == 1) and (z.state != ST_RESIST or fd == -1)))\n"),
    ("display",
     'f_num(float v, string fmt) =>\n    na(v) ? "-" : str.tostring(v, fmt)\n',
     'f_num(float v, string fmt) =>\n    na(v) ? "-" : str.tostring(v, fmt)\n' + GEOM4),
    ("display",
     'showScore  = input.bool(false, "Label: Score を表示",   group = G_LBL)\n',
     'showScore  = input.bool(false, "Label: Score を表示",   group = G_LBL)\n'
     'showGeom   = input.bool(true,  "Label: Zone 上下限 / 幅 (USD) を表示", group = G_LBL)\n'),
    ("display",
     '    if showScore\n        txt := txt + " | " + f_num(z.score, "#.#")\n',
     '    if showScore\n        txt := txt + " | " + f_num(z.score, "#.#")\n    if showGeom\n        txt := txt + "\\n" + f_usdGeom(z)\n'),
    ("display",
     '    if showScore\n        txt := txt + " | " + f_num(dScore, "#.#")\n',
     '    if showScore\n        txt := txt + " | " + f_num(dScore, "#.#")\n    if showGeom\n        txt := txt + "\\n" + f_usdGeom(z)\n'),
]
STRATEGY_EDITS4 = [
    ("header",
     "//  1 lot = 100 oz、最小 / 刻み 0.01 lot で切り捨て、qty = lot × 100 ÷ pointvalue)。数量以外の設定・処理は XA-1 のまま。\n",
     "//  1 lot = 100 oz、最小 / 刻み 0.01 lot で切り捨て、qty = lot × 100 ÷ pointvalue)。数量以外の設定・処理は XA-1 のまま。\n"
     + HEADER4 + "//  資金管理 (XA-2)・売買 / 取消 / TP / 建値の処理とタイミング・XA-3 の採用初期値は変更なし。\n"),
] + ZONE_EDITS4 + [
    ("header",
     "//  ・Zone 判定は ZONE-P と同一: ZoneEnginePractical/6 (Swing 最大点) / 入力 / Source 取得 / NR-S1 / NR-A1 /\n",
     "//  ・Zone 判定は ZONE-P と同一: ZoneEnginePracticalXAUUSD/1 (= /6 の Swing 最大点 + XA-4 の比較用モード) / 入力 / Source 取得 / NR-S1 / NR-A1 /\n"),
]


# ---- XA-5: Gold Short adopted defaults (Day/Swing Merge Nearby, breakeven ON / 15; after XA-4) ---------------------------
#  Defaults and the matching descriptions only: Day/Swing Overlap Mode Separate -> Merge Nearby (both files; Merge Distance
#  stays 0 = only an identical day high / low and Swing price merge, by the existing Engine condition); Strategy Breakeven
#  Stop OFF -> ON, Trigger 10 -> 15 USD. The dsDist tooltip and the header lines that described the old defaults are updated.
#  Engine / import, logic, sizing, every other input unchanged. strip_*5() -> the a33d2b0 (= 7363ef1) files byte for byte.
NOTE5 = "Gold Short の比較から採用した初期値・検証継続中 (年別確認・Long での検証・将来の有効性は未確認)"
HDR5 = ("//  XA-5: " + NOTE5 + ":\n"
        "//  Day/Swing Overlap Mode Merge Nearby・Merge Distance 0 USD (同じ価格の当日高値 / 安値と Swing High / Low を、既存の統合条件で\n"
        "//  1 つの根拠として数える)")
ZONE_EDITS5 = [
    ("default",
     'dsMode = input.string("Separate", "Day/Swing Overlap Mode", options = ["Separate", "Merge Nearby"], group = G_DHL,\n',
     'dsMode = input.string("Merge Nearby", "Day/Swing Overlap Mode", options = ["Separate", "Merge Nearby"], group = G_DHL,\n'),
    ("text",
     '     "初期 0 は Merge Nearby の採用値ではない: 初期の Separate では使われず、結果に作用しない。")\n',
     '     "初期 0 (Gold Short の比較から採用した初期値・検証継続中): 初期の Merge Nearby で、同じ価格の当日高値と Swing High\\n" +\n'
     '     "(安値と Swing Low) だけを 1 つの根拠にする。")\n'),
    ("text",
     "//  追加入力: Accum Score Sum・Accum Edge Separate・Day/Swing Separate (Merge Distance 0 は Separate では作用しない)・\n",
     "//  追加入力: Accum Score Sum・Accum Edge Separate・Day/Swing (XA-5 で Merge Nearby・Merge Distance 0 に変更)・\n"),
]
VISUAL_EDITS5 = [
    ("header",
     "//  Visual のみ: Label に統合後 Zone の上下限 / 幅 (USD) を表示 (初期 ON、表示だけ)。\n",
     "//  Visual のみ: Label に統合後 Zone の上下限 / 幅 (USD) を表示 (初期 ON、表示だけ)。\n" + HDR5 + "。\n"),
] + ZONE_EDITS5
STRATEGY_EDITS5 = [
    ("header",
     "//  資金管理 (XA-2)・売買 / 取消 / TP / 建値の処理とタイミング・XA-3 の採用初期値は変更なし。\n",
     "//  資金管理 (XA-2)・売買 / 取消 / TP / 建値の処理とタイミング・XA-3 の採用初期値は変更なし。\n" + HDR5 + "、\n"
     "//  建値移動 ON・Trigger 15 USD。Zone 生成・採点・統合条件・Entry・数量・注文 / 取消 / TP / 建値の判定と処理順は変えない。\n"),
    ("text",
     "//  Entry C: Candle Pattern、Short Only、SL Buffer 1.5、固定 RR 1.5、反対側 Zone TP OFF、建値移動 OFF (Trigger は現行値のまま)。\n",
     "//  Entry C: Candle Pattern、Short Only、SL Buffer 1.5、固定 RR 1.5、反対側 Zone TP OFF、建値移動 (XA-5 で ON・Trigger 15 に変更)。\n"),
] + ZONE_EDITS5 + [
    ("default",
     'stBE = input.bool(false, "Breakeven Stop", group = G_STT)\n',
     'stBE = input.bool(true, "Breakeven Stop", group = G_STT)\n'),
    ("default",
     'stBEDist = input.float(10.0, "Breakeven Trigger ($)", minval = 0.0, step = 0.5, group = G_STT)\n',
     'stBEDist = input.float(15.0, "Breakeven Trigger ($)", minval = 0.0, step = 0.5, group = G_STT)\n'),
]


# ---- XA-6: Role Reversal Mode (Engine library version 2; Visual / Strategy after XA-5) ----------------------------------
#  Separates "role change" from "retest reversal confirmation". ZoneCfg.roleOnBreak (Engine default false = the previous
#  Retest Confirmed behaviour; the previous f_updateTrack branch stays byte-identical under `else if evalBar`).
#  Confirmed Break (roleOnBreak = true, the scripts' new default): on a confirmed Break-feed bar, RESIST with close > top +
#  breakBuffer becomes SUPPORT (SUPPORT with close < bottom - breakBuffer becomes RESIST) at once (strict compare, no BROKEN
#  wait); breakDir / retested keep the reversal confirmation pending separately (flipped stays false). The Break bar is not a
#  retest; a later confirmed bar overlapping the zone records the retest; a still later bar beyond flipConfirmDist confirms
#  (flipped, Flip event, Flip Bonus) once. An opposite clear Break while pending discards the pending confirmation and starts
#  the new direction (resetOnReclaim is not used in this mode). No natural role reversal, no Track re-creation.
#  strip_engine6 / strip_*6 reverse only these.
IMPORT_XAE2 = "import sekine3310/ZoneEnginePracticalXAUUSD/2 as zn\n"
# Library version 2 of ZoneEnginePracticalXAUUSD (/1 stays published). If TradingView assigns another number, change
# IMPORT_XAE2 and rebuild (python3 tests/xa_build.py).
ROLE_NEW = (
    "    //  XA-6 Confirmed Break (c.roleOnBreak): 明確な Break (確定 Break 評価足の終値、strict) のその足で新しい役割にする\n"
    "    //    (BROKEN では待たせない)。Retest → Flip Confirm の反転確認は breakDir / retested で別に保持し、flipped は確認成立まで\n"
    "    //    false。Break 足自身は Retest にせず、Retest を記録した足では確認しない。確認待ち中に反対方向の明確な Break が\n"
    "    //    成立したら前の確認待ちを破棄して新しい方向へ切り替える (resetOnReclaim はこの方式では使わない)。\n"
    "    if evalBar and c.roleOnBreak\n"
    "        if evalState == ST_RESIST and bc > t.top + c.breakBuffer\n"
    "            t.state    := ST_SUPPORT\n"
    "            t.breakDir := 1\n"
    "            t.breakBar := bar_index\n"
    "            t.retested := false\n"
    "            t.flipped  := false\n"
    "            t.flipDir  := 0\n"
    "            handled    := true\n"
    "            ev := 1\n"
    "        else if evalState == ST_SUPPORT and bc < t.bottom - c.breakBuffer\n"
    "            t.state    := ST_RESIST\n"
    "            t.breakDir := -1\n"
    "            t.breakBar := bar_index\n"
    "            t.retested := false\n"
    "            t.flipped  := false\n"
    "            t.flipDir  := 0\n"
    "            handled    := true\n"
    "            ev := -1\n"
    "        else if t.breakDir == 1\n"
    "            handled := true\n"
    "            if not t.retested\n"
    "                if bl <= t.top and bh >= t.bottom\n"
    "                    t.retested := true\n"
    "            else if bc >= t.top + c.flipConfirmDist\n"
    "                t.flipped  := true\n"
    "                t.flipDir  := 1\n"
    "                t.breakDir := 0\n"
    "                t.retested := false\n"
    "                ev := 2\n"
    "        else if t.breakDir == -1\n"
    "            handled := true\n"
    "            if not t.retested\n"
    "                if bh >= t.bottom and bl <= t.top\n"
    "                    t.retested := true\n"
    "            else if bc <= t.bottom - c.flipConfirmDist\n"
    "                t.flipped  := true\n"
    "                t.flipDir  := -1\n"
    "                t.breakDir := 0\n"
    "                t.retested := false\n"
    "                ev := -2\n"
    "    else if evalBar\n")
ENGINE_EDITS6 = [
    ("header",
     "//    以下の「GBPJPY 派生」等は移植元の説明 (履歴)。\n",
     "//  ★ XA-6 (Library version 2): Role Reversal Mode (ZoneCfg.roleOnBreak)。false (既定) = Retest Confirmed = version 1 と\n"
     "//    同じ処理 (Break → BROKEN → Retest → Flip Confirm で新しい役割)。true = Confirmed Break = 明確な Break の足で新しい役割にし、\n"
     "//    Retest → Flip Confirm の反転確認 (flipped / Flip イベント / Flip Bonus) は別に継続する。\n"
     "//    以下の「GBPJPY 派生」等は移植元の説明 (履歴)。\n"),
    ("cfg",
     "    bool   resetOnReclaim     = true\n",
     "    bool   resetOnReclaim     = true\n"
     "    bool   roleOnBreak        = false   // XA-6: false = Retest Confirmed (version 1 と同じ) / true = Confirmed Break\n"),
    ("role",
     "    if evalBar\n        if evalState == ST_RESIST and bc > t.top + c.breakBuffer\n",
     ROLE_NEW + "        if evalState == ST_RESIST and bc > t.top + c.breakBuffer\n"),
]
HDR6 = ("//  XA-6: Role Reversal Mode (初期 Confirmed Break。Engine ZoneEnginePracticalXAUUSD version 2): 確定した Break 評価足の終値が\n"
        "//  top + Break Buffer より上 / bottom - Break Buffer より下でその足から Support / Resistance 候補 (BROKEN で待たない)。\n"
        "//  Retest → Flip Confirm の反転確認 (Flip イベント・Flip Bonus) は別に継続。Retest Confirmed = 変更前の方式 (比較・切り戻し用)。\n"
        "//  成績への影響は未確認。数値・Zone 生成 / 採点・上位足取得・Break feed は変えない。\n")
ZONE_EDITS6 = [
    ("import", IMPORT_XAE, IMPORT_XAE2),
    ("input",
     'resetOnReclaim = input.bool(true,  "Reset Broken on Reclaim", group = G_BF)\n',
     'resetOnReclaim = input.bool(true,  "Reset Broken on Reclaim", group = G_BF,\n'
     '     tooltip = "Role Reversal Mode = Retest Confirmed のときだけ使う (BROKEN 中に反対側へ明確に戻ったら役割を初期判定に戻す)。\\n" +\n'
     '     "Confirmed Break では使わない (反対方向の明確な Break がそのまま役割を切り替え、確認待ちを破棄する)。")\n'
     'roleMode = input.string("Confirmed Break", "Role Reversal Mode", options = ["Retest Confirmed", "Confirmed Break"], group = G_BF,\n'
     '     tooltip = "Confirmed Break (初期): Break 評価足の確定終値が top + Break Buffer より上なら Support 候補、bottom - Break Buffer\\n" +\n'
     '     "より下なら Resistance 候補にその足で切り替える (等値は不成立。BROKEN で待たない)。Retest → Flip Confirm の反転確認は別に継続し、\\n" +\n'
     '     "Flip イベント・Flip Bonus は確認成立時だけ。Retest Confirmed: 変更前の方式 (Break → BROKEN → Retest → Flip Confirm)。比較・切り戻し用。")\n'),
    ("cfg",
     "zoneCfg.resetOnReclaim       := resetOnReclaim\n",
     "zoneCfg.resetOnReclaim       := resetOnReclaim\n"
     "zoneCfg.roleOnBreak          := roleMode == \"Confirmed Break\"\n"),
]
VISUAL_EDITS6 = [
    ("header", "//  1 つの根拠として数える)。\n", "//  1 つの根拠として数える)。\n" + HDR6),
] + ZONE_EDITS6
STRATEGY_EDITS6 = [
    ("header",
     "//  建値移動 ON・Trigger 15 USD。Zone 生成・採点・統合条件・Entry・数量・注文 / 取消 / TP / 建値の判定と処理順は変えない。\n",
     "//  建値移動 ON・Trigger 15 USD。Zone 生成・採点・統合条件・Entry・数量・注文 / 取消 / TP / 建値の判定と処理順は変えない。\n"
     + HDR6 + "//  Strategy: 新しい役割の Zone を Retest 前から候補評価できる (発注は従来どおり Entry A〜D の条件が必要)。\n"),
] + ZONE_EDITS6


# ---- XA-7: Entry Timing = SATS Pullback (Strategy only; after XA-6) ---------------------------------------------------
#  Current (default) keeps the previous order path byte for byte (the new branches are `if stSats ... else if <old>`).
#  SATS Pullback (Entry C only; other Entry Modes stop with runtime.error): when Entry C would place its market order, a single
#  wait is prepared instead (Track, side, prep bar / bar end time, P0 = that close, SL0 = the existing SL, TP0 = the existing
#  f_stTp result at P0). From the next confirmed 5M bar: cancel first (wait >= limit minutes of wall clock from the prep bar's
#  end / Track gone / no longer a same-side candidate with Strong eligibility / SL0 reached), then the SATS line nearest to the
#  previous close among LINE1 / LINE2 / STB of the previous bar (Long: SL0 < L < P0 and L < prev close; Short mirrored; ties
#  LINE1 -> LINE2 -> STB), touched (low <= L <= high) and closed back (Long close > L, SL0 < close < P0; Short mirrored) on that
#  bar -> market order, qty = f_stQty(side, close, SL0). On the fill TP = TP0 (fixed; set at the existing fill-confirmation
#  time); a fill on the wrong side of SL0 / TP0 is closed at market (no TP), never treated as a normal entry.
#  f_satBand() is the SATS source function byte for byte (tests/sats_src/f_satBand.txt), computed on every bar at global scope.
SATS_FN = open(os.path.join(ROOT, "tests", "sats_src", "f_satBand.txt"), encoding="utf-8").read()
SATS_INPUTS = (
    'var string G_STW = "03 · Strategy Entry Timing (SATS)"\n'
    'stTiming = input.string("Current", "Entry Timing", options = ["Current", "SATS Pullback"], group = G_STW,\n'
    '     tooltip = "Current (初期): 変更前の発注方式。\\n" +\n'
    '     "SATS Pullback: Entry C が発注する条件を満たした足で発注せず待機を始め、次の 5分足以降に SATS 線 (LINE1 / LINE2 / STB) への\\n" +\n'
    '     "接触と終値での戻りを確認してから成行で発注する。SL0 / TP0 は準備時に固定 (約定後に TP を作り直さない)。\\n" +\n'
    '     "Entry C 専用: 他の Entry Mode と組み合わせると停止して表示する (黙って別動作にしない)。")\n'
    'stSatsWait = input.int(240, "SATS · 待機期限 (分)", minval = 1, group = G_STW,\n'
    '     tooltip = "準備した 5分足の終了時刻からの実時間。この分数以上になった確定評価時点で取消 (週末・欠損・時間帯外も時計は止めない)。")\n'
    'stSatsShow = input.bool(true, "SATS · 線を表示", group = G_STW)\n')
SATS_GLOBAL = (
    "\n// ---- XA-7 · SATS (SAT BAND LINE1 / LINE2 / STB) ---------------------------------------------------------------------\n"
    "//  f_satBand() は SATS 移植元 (SAT BAND Reconstruction Test) の関数を一字一句そのまま使う (tests/sats_src/f_satBand.txt)。\n"
    "//  待機の有無にかかわらず毎バー グローバルで計算する。色・バンド状態は Entry 判定に使わない。\n"
    "bool stSats = stTiming == \"SATS Pullback\"\n"
    "if stSats and not stModeC\n"
    "    runtime.error(\"Entry Timing = SATS Pullback は Entry Mode C: Candle Pattern 専用です (他の Entry Mode は対象外)。\")\n"
    "\n" + SATS_FN + "\n"
    "[satL1, satL2, satStb, satD1, satD2, satSD, satBand, satBasis, satCommon, satAtr, satA1, satA2] = f_satBand()\n"
    "\n"
    "// 足 t の判定に使う線: 足 t-1 で確定した 3 本の値と前足終値だけで選ぶ (足 t の値は使わない)。\n"
    "//  Long: SL0 < L < P0 かつ L < 前足終値 / Short: SL0 > L > P0 かつ L > 前足終値。前足終値に最も近い線、同距離は LINE1 -> LINE2 -> STB。\n"
    "//  戻り値 [線の種類 (1 / 2 / 3、無ければ 0), 線の価格 (無ければ na)]。na の線は候補にしない。\n"
    "f_satPick(int side, float p0, float sl0, float pc, float l1, float l2, float l3) =>\n"
    "    int   bk = 0\n"
    "    float bp = na\n"
    "    float bd = na\n"
    "    for k = 1 to 3\n"
    "        float v = k == 1 ? l1 : k == 2 ? l2 : l3\n"
    "        bool ok = not na(v) and not na(pc) and (side == 1 ? (v > sl0 and v < p0 and v < pc) : (v < sl0 and v > p0 and v > pc))\n"
    "        if ok\n"
    "            float d = math.abs(pc - v)\n"
    "            if bk == 0 or d < bd\n"
    "                bk := k\n"
    "                bp := v\n"
    "                bd := d\n"
    "    [bk, bp]\n")
SATS_VARS = (
    "// XA-7 SATS Pullback の待機 (全体で 1 件) と確認用の記録\n"
    "var int   pwState  = 0       // 0 = 待機なし / 1 = 待機中\n"
    "var int   pwSide   = 0\n"
    "var int   pwTrack  = -1\n"
    "var int   pwBar    = na\n"
    "var int   pwEndT   = na      // 準備した 5分足の終了時刻 (期限の起点)\n"
    "var float pwP0     = na\n"
    "var float pwSL0    = na\n"
    "var float pwTP0    = na\n"
    "var float oTP0     = na      // SATS で発注した注文の TP0 (約定確認時の TP)\n"
    "var float pwRRPrep = na\n"
    "var float pwRRPlan = na\n"
    "var float pwRRFill = na\n"
    "var int   pwNPrep  = 0\n"
    "var int   pwNOrder = 0\n"
    "var int   pwNExp   = 0\n"
    "var int   pwNTrk   = 0\n"
    "var int   pwNZone  = 0\n"
    "var int   pwNSL    = 0\n"
    "var int   pwNBad   = 0\n"
    "int   pwEv    = 0          // この足のイベント: 1 = 準備 / 2 = 発注 / -1 期限 / -2 Track 消失 / -3 候補・Strong 資格なし / -4 SL0 到達\n"
    "int   pwLineK = 0          // この足の判定に使った線 (1 = LINE1 / 2 = LINE2 / 3 = STB / 0 = なし)\n"
    "float pwLineP = na         // その線の価格 (足 t-1 の確定値)\n")
SATS_FILL = (
    "    // (2b') XA-7 SATS Pullback: TP は準備時の TP0 のまま (実約定価格から作り直さない)。設定は既存どおり約定確認時。\n"
    "    //   実約定が SL0 / TP0 の不適切な側 (risk <= 0 または TP0 までの距離 <= 0) なら TP を置かず成行決済 (正常約定として扱わない)\n"
    "    if fillNow and stSats\n"
    "        float riskS = oSide * (oFill - oSL)\n"
    "        float rewS  = oSide * (oTP0 - oFill)\n"
    "        pwRRFill := riskS > 0 ? rewS / riskS : na\n"
    "        if riskS > 0 and rewS > 0\n"
    "            oTP   := oTP0\n"
    "            oStop := oSL\n"
    "            strategy.exit(oXid, oEid, stop = oStop, limit = oTP)\n"
    "        else\n"
    "            strategy.close(oEid)\n"
    "            oState := 3\n"
    "            pwNBad += 1\n"
    "    else if fillNow\n")
SATS_WAIT = (
    "    // (3b) XA-7 SATS Pullback の待機判定 (準備足の次の足から)。取消を反発より優先する\n"
    "    //   取消: 期限 (準備足の終了時刻からの実時間) / Track 消失 / 同方向の候補 (Strong 資格) でない / SL0 到達。使用済み Track にはしない\n"
    "    //   判定: 足 t-1 の確定線から選んだ L に足 t が接触し (low <= L <= high)、終値が戻る (Long: close > L、SL0 < close < P0)\n"
    "    bool  pwCancelBar = false\n"
    "    if stSats and pwState == 1 and bar_index > pwBar\n"
    "        bool zOK = false\n"
    "        int  nc  = array.size(cur)\n"
    "        if nc > 0\n"
    "            for k = 0 to nc - 1\n"
    "                StCand x = array.get(cur, k)\n"
    "                if x.track == pwTrack and x.side == pwSide\n"
    "                    zOK := true\n"
    "        int why = 0\n"
    "        if time_close - pwEndT >= stSatsWait * 60000\n"
    "            why := -1\n"
    "        else if array.indexof(curTrk, pwTrack) < 0\n"
    "            why := -2\n"
    "        else if not zOK\n"
    "            why := -3\n"
    "        else if pwSide == 1 ? low <= pwSL0 : high >= pwSL0\n"
    "            why := -4\n"
    "        if why != 0\n"
    "            pwState     := 0\n"
    "            pwCancelBar := true\n"
    "            pwEv        := why\n"
    "            pwNExp  += why == -1 ? 1 : 0\n"
    "            pwNTrk  += why == -2 ? 1 : 0\n"
    "            pwNZone += why == -3 ? 1 : 0\n"
    "            pwNSL   += why == -4 ? 1 : 0\n"
    "        else\n"
    "            [lk, lp] = f_satPick(pwSide, pwP0, pwSL0, close[1], satL1[1], satL2[1], satStb[1])\n"
    "            pwLineK := lk\n"
    "            pwLineP := lp\n"
    "            bool hit = lk != 0 and low <= lp and lp <= high and (pwSide == 1 ? (close > lp and close > pwSL0 and close < pwP0) : (close < lp and close < pwSL0 and close > pwP0))\n"
    "            if hit and stSessOK and oState == 0\n"
    "                float q = f_stQty(pwSide, close, pwSL0)\n"
    "                if not na(q)\n"
    "                    oSeq    += 1\n"
    "                    oEid    := (pwSide == 1 ? \"L\" : \"S\") + str.tostring(oSeq)\n"
    "                    oXid    := oEid + \" SL/TP\"\n"
    "                    oSide   := pwSide\n"
    "                    oTrack  := pwTrack\n"
    "                    oLimit  := false\n"
    "                    oL      := na\n"
    "                    oSL     := pwSL0\n"
    "                    oStop   := pwSL0\n"
    "                    oTP     := na\n"
    "                    oTP0    := pwTP0\n"
    "                    oFill   := na\n"
    "                    oBE     := false\n"
    "                    oClosed := strategy.closedtrades\n"
    "                    oState  := 1\n"
    "                    strategy.entry(oEid, pwSide == 1 ? strategy.long : strategy.short, qty = q)\n"
    "                    strategy.exit(oXid, oEid, stop = oSL)\n"
    "                    pwRRPlan := pwSide * (pwTP0 - close) / (pwSide * (close - pwSL0))\n"
    "                    pwRRFill := na\n"
    "                    pwState  := 0\n"
    "                    pwEv     := 2\n"
    "                    pwNOrder += 1\n"
    "\n")
SATS_PREP = (
    "            if stSats\n"
    "                // XA-7: Entry C が発注する条件を満たした → 発注せず待機を準備する (待機中・取消した足では何もしない)\n"
    "                if not skipRef and not na(pQty) and pwState == 0 and not pwCancelBar\n"
    "                    pwState  := 1\n"
    "                    pwSide   := side\n"
    "                    pwTrack  := c.track\n"
    "                    pwBar    := bar_index\n"
    "                    pwEndT   := time_close\n"
    "                    pwP0     := ref\n"
    "                    pwSL0    := pSL\n"
    "                    pwTP0    := tpRef\n"
    "                    pwRRPrep := side * (tpRef - ref) / (side * (ref - pSL))\n"
    "                    pwEv     := 1\n"
    "                    pwNPrep  += 1\n"
    "            else if not skipRef and not na(pQty)\n")
SATS_PLOTS = (
    "// XA-7 SATS Pullback の確認表示 (データウィンドウ + 小さな印。永続ラベル・独自アラートは追加しない)\n"
    "plot(stSats and stSatsShow ? satL1 : na,  \"SATS · LINE1\", color = color.new(color.teal, 0))\n"
    "plot(stSats and stSatsShow ? satL2 : na,  \"SATS · LINE2\", color = color.new(color.orange, 0))\n"
    "plot(stSats and stSatsShow ? satStb : na, \"SATS · STB\",   color = color.new(color.purple, 0))\n"
    "plot(stSats ? pwState : na,                \"SATS · 待機中\",          display = display.data_window)\n"
    "plot(stSats ? pwEv : na,                   \"SATS · イベント (1 準備 / 2 発注 / -1 期限 / -2 Track / -3 資格 / -4 SL0)\", display = display.data_window)\n"
    "plot(stSats ? pwLineK : na,                \"SATS · 対象線 (1 L1 / 2 L2 / 3 STB)\", display = display.data_window)\n"
    "plot(stSats ? pwLineP : na,                \"SATS · 対象線の価格 (足 t-1 確定値)\", display = display.data_window)\n"
    "plot(stSats ? pwP0 : na,                   \"SATS · P0\",              display = display.data_window)\n"
    "plot(stSats ? pwSL0 : na,                  \"SATS · SL0\",             display = display.data_window)\n"
    "plot(stSats ? pwTP0 : na,                  \"SATS · TP0\",             display = display.data_window)\n"
    "plot(stSats ? pwRRPrep : na,               \"SATS · 準備 RR\",          display = display.data_window)\n"
    "plot(stSats ? pwRRPlan : na,               \"SATS · 発注時の予定 RR\",   display = display.data_window)\n"
    "plot(stSats ? pwRRFill : na,               \"SATS · 実 RR (実約定価格)\", display = display.data_window)\n"
    "plot(stSats ? pwNPrep : na,                \"SATS · 準備件数\",          display = display.data_window)\n"
    "plot(stSats ? pwNOrder : na,               \"SATS · 発注件数\",          display = display.data_window)\n"
    "plot(stSats ? pwNExp : na,                 \"SATS · 期限切れ件数\",      display = display.data_window)\n"
    "plot(stSats ? pwNTrk + pwNZone : na,       \"SATS · Track / 資格の取消件数\", display = display.data_window)\n"
    "plot(stSats ? pwNSL : na,                  \"SATS · SL0 到達の取消件数\", display = display.data_window)\n"
    "plot(stSats ? pwNBad : na,                 \"SATS · 不適切な約定の決済件数\", display = display.data_window)\n"
    "plotshape(stSats and pwEv == 1, \"SATS · 準備\", style = shape.circle, location = location.abovebar, color = color.gray, size = size.tiny)\n"
    "plotshape(stSats and pwEv == 2, \"SATS · 発注\", style = shape.triangledown, location = location.abovebar, color = color.red, size = size.tiny)\n"
    "plotshape(stSats and pwEv < 0,  \"SATS · 取消\", style = shape.xcross, location = location.abovebar, color = color.silver, size = size.tiny)\n")
STRATEGY_EDITS7 = [
    ("header",
     "//  Strategy: 新しい役割の Zone を Retest 前から候補評価できる (発注は従来どおり Entry A〜D の条件が必要)。\n",
     "//  Strategy: 新しい役割の Zone を Retest 前から候補評価できる (発注は従来どおり Entry A〜D の条件が必要)。\n"
     "//  XA-7: Entry Timing (初期 Current = 変更前の発注方式)。SATS Pullback = Entry C の発注条件で待機を準備し、次の 5分足以降に\n"
     "//  SATS 線 (LINE1 / LINE2 / STB、足 t-1 の確定値) への接触と終値での戻りで成行発注。SL0 / TP0 は準備時に固定。成績への影響は未確認。\n"),
    ("input",
     'stDWait = input.int(30, "D · BOS Wait (confirmed 1M bars)", minval = 1, group = G_ST)\n',
     'stDWait = input.int(30, "D · BOS Wait (confirmed 1M bars)", minval = 1, group = G_ST)\n' + SATS_INPUTS),
    ("sats", 'bool stShortOK = stDir != "Long Only"\n', 'bool stShortOK = stDir != "Long Only"\n' + SATS_GLOBAL),
    ("sats", "var int    oClosed = 0\n", "var int    oClosed = 0\n" + SATS_VARS),
    ("sats", "    if fillNow\n", SATS_FILL),
    ("sats", "    // (4) 新規 Entry (注文が無く、取消をした足でなく、時間帯の中のときだけ)\n",
     SATS_WAIT + "    // (4) 新規 Entry (注文が無く、取消をした足でなく、時間帯の中のときだけ)\n"),
    ("sats", "            if not skipRef and not na(pQty)\n", SATS_PREP),
    ("sats",
     'plot(stSessOK ? 1 : 0,                 "ST · Entry Session",     display = display.data_window)\n',
     'plot(stSessOK ? 1 : 0,                 "ST · Entry Session",     display = display.data_window)\n' + SATS_PLOTS),
]


# ---- XA-8: SATS actual RR also for a fill closed within its fill bar (Strategy only; after XA-7) -------------------------
#  Record only. f_satRR(side, fill, SL0, TP0) -> [RR, reason] (0 = ok, 1 = risk <= 0: fill at / beyond SL0, 2 = TP0 not beyond
#  the fill, 3 = a price is na; RR na unless 0). Holding path (2b'): same order handling, the record comes from f_satRR.
#  Closed-in-fill-bar path (filledClosed): SATS Pullback only, the entry price of that closed trade with the stored SL0 / TP0;
#  no TP / close order (the trade is already closed). One record per fill (the two paths are exclusive branches of (1)):
#  pwNFill counts it, pwFillPath shows the path (1 = holding / 2 = closed in the fill bar). Current is unchanged.
SATS_RR_FN = (
    "\n// XA-8: 実 RR = side × (TP0 − 実約定) ÷ side × (実約定 − SL0)。戻り値 [RR, 理由] (0 = 計算可 / 1 = 約定が SL0 以遠 (risk <= 0) /\n"
    "//  2 = TP0 が約定価格の先にない (reward <= 0) / 3 = 価格が na)。理由 0 以外の RR は na\n"
    "f_satRR(int side, float fillPx, float sl0, float tp0) =>\n"
    "    float rr  = na\n"
    "    int   why = 0\n"
    "    if na(fillPx) or na(sl0) or na(tp0)\n"
    "        why := 3\n"
    "    else\n"
    "        float risk = side * (fillPx - sl0)\n"
    "        float rew  = side * (tp0 - fillPx)\n"
    "        if risk <= 0\n"
    "            why := 1\n"
    "        else if rew <= 0\n"
    "            why := 2\n"
    "        else\n"
    "            rr := rew / risk\n"
    "    [rr, why]\n")
STRATEGY_EDITS8 = [
    ("header",
     "//  SATS 線 (LINE1 / LINE2 / STB、足 t-1 の確定値) への接触と終値での戻りで成行発注。SL0 / TP0 は準備時に固定。成績への影響は未確認。\n",
     "//  SATS 線 (LINE1 / LINE2 / STB、足 t-1 の確定値) への接触と終値での戻りで成行発注。SL0 / TP0 は準備時に固定。成績への影響は未確認。\n"
     "//  XA-8: SATS の実 RR を約定足内で SL 決済まで終わった約定でも記録 (closed trade の実約定価格 + SL0 / TP0。注文は出さない)。\n"),
    ("rr", "    [bk, bp]\n", "    [bk, bp]\n" + SATS_RR_FN),
    ("rr", "var int   pwNBad   = 0\n",
     "var int   pwNBad   = 0\n"
     "var int   pwRRWhy  = na      // XA-8: 実 RR の理由 (0 計算可 / 1 risk <= 0 / 2 reward <= 0 / 3 na)\n"
     "var int   pwNFill  = 0       // XA-8: 実 RR を記録した SATS 約定の件数 (1 約定 1 回)\n"
     "var int   pwFillPath = 0     // XA-8: 直近の記録経路 (1 = 約定後も保有中 / 2 = 約定足内で決済済み)\n"),
    ("rr",
     "            // 約定した足の中で SL まで成立した\n            map.put(stUsed, oTrack, true)\n            oState := 0\n",
     "            // 約定した足の中で SL まで成立した\n            map.put(stUsed, oTrack, true)\n            oState := 0\n"
     "            if stSats     // XA-8: 決済済みの SATS 約定も実 RR を記録する (TP / 決済の注文は出さない)\n"
     "                [rrC, whyC] = f_satRR(oSide, strategy.closedtrades.entry_price(ct - 1), oSL, oTP0)\n"
     "                pwRRFill   := rrC\n"
     "                pwRRWhy    := whyC\n"
     "                pwNFill    += 1\n"
     "                pwFillPath := 2\n"),
    ("rr", "        pwRRFill := riskS > 0 ? rewS / riskS : na\n",
     "        [rrH, whyH] = f_satRR(oSide, oFill, oSL, oTP0)     // XA-8: 記録だけ (下の注文処理は従来どおり)\n"
     "        pwRRFill   := rrH\n"
     "        pwRRWhy    := whyH\n"
     "        pwNFill    += 1\n"
     "        pwFillPath := 1\n"),
    ("rr", "                    pwRRFill := na\n", "                    pwRRFill := na\n                    pwRRWhy  := na\n"),
    ("rr",
     'plot(stSats ? pwRRFill : na,               "SATS · 実 RR (実約定価格)", display = display.data_window)\n',
     'plot(stSats ? pwRRFill : na,               "SATS · 実 RR (実約定価格)", display = display.data_window)\n'
     'plot(stSats ? pwRRWhy : na,                "SATS · 実 RR の理由 (0 可 / 1 risk<=0 / 2 reward<=0 / 3 na)", display = display.data_window)\n'
     'plot(stSats ? pwNFill : na,                "SATS · 実 RR 記録件数", display = display.data_window)\n'
     'plot(stSats ? pwFillPath : na,             "SATS · 記録経路 (1 保有中 / 2 約定足内で決済済み)", display = display.data_window)\n'),
]


# ---- XA-9: SATS Pullback — no zone re-check after the prep; touch recorded, rebound on the touch bar or later (after XA-8) ---
#  SATS Pullback only (Current unchanged). Cancels: the wall-clock limit and SL0 only (before any rebound); the Track /
#  Strong-candidate re-checks of XA-7 are removed. Before the touch the line is re-picked every bar (t-1 lines, previous close,
#  SL0 < L < P0 and beyond the previous close, ties L1 -> L2 -> STB); a touch (low <= L <= high, L in range) records the line
#  kind. After the touch that kind is kept (its t-1 value every bar, no "beyond the previous close" requirement; na / out of
#  range -> no order but the record stays). Rebound A: touch and close back on the bar; B: touched before, previous close at or
#  beyond L and close back beyond L (both against the same L). Plus SL0 < close < P0 (mirrored), session, no order, valid qty.
#  The touch state is reset on prep / cancel / order. strip_strategy9() -> the Strategy of a32bd85.
SATS_WAIT8 = SATS_WAIT.replace("                    pwRRFill := na\n", "                    pwRRFill := na\n                    pwRRWhy  := na\n")
SATS_WAIT9 = (
    "    // (3b) XA-7 / XA-9 SATS Pullback の待機判定 (準備足の次の足から)。取消を反発より優先する\n"
    "    //   取消 (XA-9): 期限 (準備足の終了時刻からの実時間) / 固定 SL0 到達 だけ。元 Zone の Strong 資格・Track の存続 / 一致・候補一覧\n"
    "    //   からの脱落では取り消さない (保存した方向 / P0 / SL0 / TP0 を使い続ける)。取消だけでは使用済み Track にしない\n"
    "    //   接触前: 毎足、足 t-1 の確定線と前足終値から最寄りの適格線を選び直す。low <= L <= high で接触 → 線の種類を記録\n"
    "    //   接触後: 記録した種類の線の足 t-1 確定値を毎足使う (別の線へ選び替えない。前足終値との位置関係は再要求しない)。\n"
    "    //           na / SL0〜P0 の範囲外の足は発注しないが、接触記録は消さない\n"
    "    //   反発: A = その足で接触して終値が戻る / B = 接触済みで、前足終値 <= L (Short は >=) かつ当足終値 > L (Short は <)\n"
    "    bool  pwCancelBar = false\n"
    "    if stSats and pwState == 1 and bar_index > pwBar\n"
    "        int why = 0\n"
    "        if time_close - pwEndT >= stSatsWait * 60000\n"
    "            why := -1\n"
    "        else if pwSide == 1 ? low <= pwSL0 : high >= pwSL0\n"
    "            why := -4\n"
    "        if why != 0\n"
    "            pwState     := 0\n"
    "            pwCancelBar := true\n"
    "            pwEv        := why\n"
    "            pwNExp  += why == -1 ? 1 : 0\n"
    "            pwNSL   += why == -4 ? 1 : 0\n"
    "            pwTouched  := false\n"
    "            pwTouchK   := 0\n"
    "            pwTouchBar := na\n"
    "        else\n"
    "            int   lk = 0\n"
    "            float lp = na\n"
    "            if not pwTouched\n"
    "                [k0, v0] = f_satPick(pwSide, pwP0, pwSL0, close[1], satL1[1], satL2[1], satStb[1])\n"
    "                lk := k0\n"
    "                lp := v0\n"
    "            else\n"
    "                lk := pwTouchK\n"
    "                lp := pwTouchK == 1 ? satL1[1] : pwTouchK == 2 ? satL2[1] : satStb[1]\n"
    "            pwLineK := lk\n"
    "            pwLineP := lp\n"
    "            bool inRange  = lk != 0 and not na(lp) and (pwSide == 1 ? (lp > pwSL0 and lp < pwP0) : (lp < pwSL0 and lp > pwP0))\n"
    "            bool touchNow = inRange and low <= lp and lp <= high\n"
    "            bool rebA     = touchNow and (pwSide == 1 ? close > lp : close < lp)\n"
    "            bool rebB     = pwTouched and inRange and (pwSide == 1 ? (close[1] <= lp and close > lp) : (close[1] >= lp and close < lp))\n"
    "            if touchNow and not pwTouched\n"
    "                pwTouched    := true\n"
    "                pwTouchK     := lk\n"
    "                pwTouchBar   := bar_index\n"
    "                pwNTouchPrep += 1\n"
    "            bool priceOK = pwSide == 1 ? (close > pwSL0 and close < pwP0) : (close < pwSL0 and close > pwP0)\n"
    "            if (rebA or rebB) and priceOK and stSessOK and oState == 0\n"
    "                float q = f_stQty(pwSide, close, pwSL0)\n"
    "                if not na(q)\n"
    "                    oSeq    += 1\n"
    "                    oEid    := (pwSide == 1 ? \"L\" : \"S\") + str.tostring(oSeq)\n"
    "                    oXid    := oEid + \" SL/TP\"\n"
    "                    oSide   := pwSide\n"
    "                    oTrack  := pwTrack\n"
    "                    oLimit  := false\n"
    "                    oL      := na\n"
    "                    oSL     := pwSL0\n"
    "                    oStop   := pwSL0\n"
    "                    oTP     := na\n"
    "                    oTP0    := pwTP0\n"
    "                    oFill   := na\n"
    "                    oBE     := false\n"
    "                    oClosed := strategy.closedtrades\n"
    "                    oState  := 1\n"
    "                    strategy.entry(oEid, pwSide == 1 ? strategy.long : strategy.short, qty = q)\n"
    "                    strategy.exit(oXid, oEid, stop = oSL)\n"
    "                    pwRRPlan := pwSide * (pwTP0 - close) / (pwSide * (close - pwSL0))\n"
    "                    pwRRFill := na\n"
    "                    pwRRWhy  := na\n"
    "                    pwState  := 0\n"
    "                    pwEv     := 2\n"
    "                    pwNOrder += 1\n"
    "                    pwNOrdSame  += rebA ? 1 : 0\n"
    "                    pwNOrdLater += rebA ? 0 : 1\n"
    "                    pwTouched  := false\n"
    "                    pwTouchK   := 0\n"
    "                    pwTouchBar := na\n"
    "\n")
STRATEGY_EDITS9 = [
    ("header",
     "//  XA-8: SATS の実 RR を約定足内で SL 決済まで終わった約定でも記録 (closed trade の実約定価格 + SL0 / TP0。注文は出さない)。\n",
     "//  XA-8: SATS の実 RR を約定足内で SL 決済まで終わった約定でも記録 (closed trade の実約定価格 + SL0 / TP0。注文は出さない)。\n"
     "//  XA-9: SATS Pullback の準備後は元 Zone の Strong 資格・Track を再審査しない (取消は期限と SL0 到達だけ)。SATS 線への接触を記録し、\n"
     "//  接触足で戻る場合 (A) と、接触後の別の足で前足終値 → 当足終値が同じ線 L を越えて戻る場合 (B) を反発とする。成績への影響は未確認。\n"),
    ("touch",
     "var int   pwNTrk   = 0\nvar int   pwNZone  = 0\n",
     "var bool  pwTouched  = false   // XA-9: 接触済み (反発待ち)\n"
     "var int   pwTouchK   = 0       // XA-9: 接触した線の種類 (1 LINE1 / 2 LINE2 / 3 STB)\n"
     "var int   pwTouchBar = na      // XA-9: 接触した足\n"
     "var int   pwNTouchPrep = 0     // XA-9: 接触を経験した準備の件数 (同じ準備で何度触れても 1 件)\n"
     "var int   pwNOrdSame   = 0     // XA-9: 同じ足の接触・反発 (A) で発注した件数\n"
     "var int   pwNOrdLater  = 0     // XA-9: 接触後の別の足の戻り (B) で発注した件数\n"),
    ("touch", SATS_WAIT8, SATS_WAIT9),
    ("touch",
     "                    pwNPrep  += 1\n",
     "                    pwNPrep  += 1\n"
     "                    pwTouched  := false     // XA-9: 新しい準備は接触待ちから\n"
     "                    pwTouchK   := 0\n"
     "                    pwTouchBar := na\n"),
    ("touch",
     'plot(stSats ? pwNTrk + pwNZone : na,       "SATS · Track / 資格の取消件数", display = display.data_window)\n',
     'plot(stSats ? (pwTouched ? 1 : 0) : na,    "SATS · 接触 (0 接触待ち / 1 接触済み・反発待ち)", display = display.data_window)\n'
     'plot(stSats ? pwTouchK : na,               "SATS · 保持している線 (1 L1 / 2 L2 / 3 STB / 0 未接触)", display = display.data_window)\n'
     'plot(stSats ? pwNTouchPrep : na,           "SATS · 接触を経験した準備件数", display = display.data_window)\n'
     'plot(stSats ? pwNOrdSame : na,             "SATS · 発注 (同じ足の接触・反発)", display = display.data_window)\n'
     'plot(stSats ? pwNOrdLater : na,            "SATS · 発注 (接触後の別の足の戻り)", display = display.data_window)\n'),
]


# ---- XA-10: SATS Pullback with Entry Mode A / B / C / D (Strategy only; after XA-9) -------------------------------------
#  The prep already sits in the shared order block (4) of every mode: it runs exactly where Current places the order, with
#  that mode's ref (A: the limit price pL / B, C, D: the confirmed close), pSL, tpRef and pQty; D reaches it only through dSrc
#  (after its 1M BOS). XA-10 removes the "Entry C only" runtime.error and updates the tooltip / header / comment. No logic
#  line changes (SATS + C is the same code path). strip_strategy10() -> the Strategy of 3ca1837.
STRATEGY_EDITS10 = [
    ("header",
     "//  接触足で戻る場合 (A) と、接触後の別の足で前足終値 → 当足終値が同じ線 L を越えて戻る場合 (B) を反発とする。成績への影響は未確認。\n",
     "//  接触足で戻る場合 (A) と、接触後の別の足で前足終値 → 当足終値が同じ線 L を越えて戻る場合 (B) を反発とする。成績への影響は未確認。\n"
     "//  XA-10: SATS Pullback を Entry Mode A〜D すべてで使える (各モードの既存の発注条件が成立した足で、注文の代わりに待機を準備。\n"
     "//  P0 = A は元の指値価格 pL (指値注文は出さない) / B・C・D はその確定足の終値。D は既存の 1分足 BOS 確認後)。待機・反発・取消は共通。\n"),
    ("text",
     '     "SATS Pullback: Entry C が発注する条件を満たした足で発注せず待機を始め、次の 5分足以降に SATS 線 (LINE1 / LINE2 / STB) への\\n" +\n',
     '     "SATS Pullback: 選択した Entry Mode (A〜D) が発注する条件を満たした足で発注せず待機を始め、次の 5分足以降に SATS 線\\n" +\n'
     '     "(LINE1 / LINE2 / STB) への\\n" +\n'),
    ("text",
     '     "Entry C 専用: 他の Entry Mode と組み合わせると停止して表示する (黙って別動作にしない)。")\n',
     '     "P0: A は元の指値価格 (指値注文は出さない) / B・C・D はその確定足の終値。D は既存の 1分足 BOS 確認後に待機を始める。")\n'),
    ("gate",
     'if stSats and not stModeC\n'
     '    runtime.error("Entry Timing = SATS Pullback は Entry Mode C: Candle Pattern 専用です (他の Entry Mode は対象外)。")\n',
     '//  XA-10: SATS Pullback は Entry Mode A〜D すべてで使える (C 専用の停止は廃止)。\n'),
    ("text",
     "                // XA-7: Entry C が発注する条件を満たした → 発注せず待機を準備する (待機中・取消した足では何もしない)\n",
     "                // XA-7 / XA-10: 選択した Entry Mode (A〜D) が発注する条件を満たした → 発注せず待機を準備する\n"
     "                //   (P0 = ref: A は指値価格 pL / B・C・D は確定足の終値。待機中・取消した足では何もしない)\n"),
]


# ---- XA-2: position size (Strategy only; applied after XA-1) -----------------------------------------------------------
QTY_BLOCK = (
    'var string G_STQ = "03 · Strategy Position Size (単利・損失予算)"\n'
    'stCapBase = input.float(300000.0, "元金基準額 (円)", minval = 0.0, step = 10000.0, group = G_STQ,\n'
    '     tooltip = "単利: 予定損失予算はこの基準額 × 損失率で固定 (strategy.equity・残高に連動しない)。strategy の初期資金とは別の入力。")\n'
    'stRiskPct = input.float(3.0, "損失率 (%)", minval = 0.0, step = 0.1, group = G_STQ)\n'
    'stLotOz = input.float(100.0, "1 lot のオンス数", minval = 0.0001, step = 1.0, group = G_STQ)\n'
    'stLotMin = input.float(0.01, "最小 lot", minval = 0.0001, step = 0.01, group = G_STQ)\n'
    'stLotStep = input.float(0.01, "lot 刻み", minval = 0.0001, step = 0.01, group = G_STQ,\n'
    '     tooltip = "lot はこの刻みで切り捨て。最小 lot 未満なら発注しない (切り上げない)。")\n'
    'float stBudget = stCapBase * stRiskPct / 100.0     // 予定損失予算 (円、毎回固定)\n'
    '\n'
    '// 数量: 円の予算を strategy.convert_to_symbol で銘柄通貨 (USD) へ換算 (固定 USDJPY なし)。\n'
    '//  lot = 予算 USD ÷ (SL 距離 × 1 lot のオンス数) を lot 刻みで切り捨て、切り捨て後の予定損失が予算を超えれば 1 刻み下げる。\n'
    '//  qty (TradingView の数量) = lot × 1 lot のオンス数 ÷ syminfo.pointvalue → SL 距離 × qty × pointvalue = 予定損失 USD\n'
    '//  (pointvalue = 1 なら 0.03 lot = 3 oz = qty 3)。換算 na / 無効な入力・価格・pointvalue / SL の向き不正 / 距離 0 /\n'
    '//  最小 lot 未満は na (発注しない)。参照価格 (A: 指値 / B, C, D: 確定足の終値) に対する予定損失であり、\n'
    '//  約定ずれ・スプレッド・手数料を含む実損失の上限ではない。\n'
    'f_stQty(int side, float ref, float sl) =>\n'
    '    float dist   = side == 1 ? ref - sl : sl - ref\n'
    '    float budSym = stBudget > 0 ? strategy.convert_to_symbol(stBudget) : na     // 予定損失予算 (USD)\n'
    '    float pv     = syminfo.pointvalue\n'
    '    float q      = na\n'
    '    if not na(dist) and dist > 0 and not na(pv) and pv > 0 and stLotOz > 0 and stLotStep > 0 and stLotMin > 0 and not na(budSym) and budSym > 0\n'
    '        float n = math.floor(budSym / (dist * stLotOz * stLotStep) + 1e-9)     // lot 刻みの個数 (1e-9: 浮動小数の誤差だけ吸収)\n'
    '        if n * stLotStep * stLotOz * dist > budSym                              // 再確認: 予算超過なら 1 刻み下げる\n'
    '            n := n - 1\n'
    '        if n >= 1 and n * stLotStep >= stLotMin * (1 - 1e-9)\n'
    '            q := n * stLotStep * stLotOz / pv\n'
    '    q\n')
STRATEGY_EDITS2 = [
    ("header",
     "//  建値移動 OFF。初期資金 10,000・数量 1 固定は従来どおり (資金管理は未追加)。\n",
     "//  建値移動 OFF。初期資金 10,000・数量 1 固定は従来どおり (資金管理は未追加)。\n"
     "//  XA-2: 資金管理 (初期資金 300,000 円・JPY、元金基準額 300,000 円 × 3 % = 毎回 9,000 円の予定損失予算・単利、\n"
     "//  1 lot = 100 oz、最小 / 刻み 0.01 lot で切り捨て、qty = lot × 100 ÷ pointvalue)。数量以外の設定・処理は XA-1 のまま。\n"),
    ("size",
     "     initial_capital        = 10000,\n",
     "     initial_capital        = 300000,\n     currency               = currency.JPY,\n"),
    ("size",
     'stBEDist = input.float(10.0, "Breakeven Trigger ($)", minval = 0.0, step = 0.5, group = G_STT)\n',
     'stBEDist = input.float(10.0, "Breakeven Trigger ($)", minval = 0.0, step = 0.5, group = G_STT)\n' + QTY_BLOCK),
    ("size",
     "            [skipRef, tpRef] = f_stTp(side, ref, pSL, f_stNearest(side == 1 ? tpUp : tpDn, side, ref))\n"
     "            if not skipRef\n",
     "            [skipRef, tpRef] = f_stTp(side, ref, pSL, f_stNearest(side == 1 ? tpUp : tpDn, side, ref))\n"
     "            // 数量: 同じ参照価格 (A: 指値 / B, C, D: この確定足の終値) と固定 SL から。無効 / 最小 lot 未満は発注しない\n"
     "            float  pQty = f_stQty(side, ref, pSL)\n"
     "            if not skipRef and not na(pQty)\n"),
    ("size",
     "                    strategy.entry(oEid, side == 1 ? strategy.long : strategy.short, limit = oL)\n",
     "                    strategy.entry(oEid, side == 1 ? strategy.long : strategy.short, qty = pQty, limit = oL)\n"),
    ("size",
     "                    strategy.entry(oEid, side == 1 ? strategy.long : strategy.short)\n",
     "                    strategy.entry(oEid, side == 1 ? strategy.long : strategy.short, qty = pQty)\n"),
]


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


_rd = lambda p: open(os.path.join(ROOT, p), encoding="utf-8").read()


def show(rev, path):
    return subprocess.run(["git", "-C", ROOT, "show", f"{rev}:{path}"], capture_output=True, text=True).stdout


def build_visual1():
    """XA-1 only (commits 2732772 / 69e6f0c)."""
    return _apply(show(BASE_REV, VIS_PATH), VISUAL_EDITS)


def build_visual3():
    """XA-1 + XA-3 (commit 17d1ca2)."""
    return _apply(build_visual1(), VISUAL_EDITS3)


def build_visual4():
    """XA-1 + XA-3 + XA-4 (commit 7363ef1)."""
    return _apply(build_visual3(), VISUAL_EDITS4)


def build_visual5():
    """XA-1 .. XA-5 (commit cbb996d)."""
    return _apply(build_visual4(), VISUAL_EDITS5)


def build_visual():
    return _apply(build_visual5(), VISUAL_EDITS6)


def build_engine1():
    """ZoneEnginePracticalXAUUSD version 1 = gbe_build.build() (/6 + GBE-1 / GBE-2 / GBE-4) with the XA-4 engine edits."""
    return _apply(_ge.build(), ENGINE_EDITS)


def build_engine():
    """version 2 = version 1 + the XA-6 Role Reversal Mode."""
    return _apply(build_engine1(), ENGINE_EDITS6)


def strip_engine6(t):
    """reverse only XA-6 (-> the version 1 source of 7363ef1 byte for byte)."""
    return _revert(t, ENGINE_EDITS6)


def strip_engine(t):
    """reverse XA-6 when present (all or nothing) and the XA-4 engine edits (-> the ZoneEnginePracticalGBPJPY source)."""
    if t is not None and ENGINE_EDITS6[0][2] in t:
        t = strip_engine6(t)
    return _revert(t, ENGINE_EDITS)


def build_strategy1():
    """XA-1 only (commit 2732772)."""
    return _apply(show(BASE_REV, STR_PATH), STRATEGY_EDITS)


def build_strategy2():
    """XA-1 + XA-2 (commit 69e6f0c)."""
    return _apply(build_strategy1(), STRATEGY_EDITS2)


def build_strategy3():
    """XA-1 + XA-2 + XA-3 (commit 17d1ca2)."""
    return _apply(build_strategy2(), STRATEGY_EDITS3)


def build_strategy4():
    """XA-1 .. XA-4 (commit 7363ef1)."""
    return _apply(build_strategy3(), STRATEGY_EDITS4)


def build_strategy5():
    """XA-1 .. XA-5 (commit cbb996d)."""
    return _apply(build_strategy4(), STRATEGY_EDITS5)


def build_strategy6():
    """XA-1 .. XA-6 (commit 0c6cd71)."""
    return _apply(build_strategy5(), STRATEGY_EDITS6)


def build_strategy7():
    """XA-1 .. XA-7 (commit 6b9458d)."""
    return _apply(build_strategy6(), STRATEGY_EDITS7)


def build_strategy8():
    """XA-1 .. XA-8 (commit a32bd85)."""
    return _apply(build_strategy7(), STRATEGY_EDITS8)


def build_strategy9():
    """XA-1 .. XA-9 (commit 3ca1837)."""
    return _apply(build_strategy8(), STRATEGY_EDITS9)


def build_strategy():
    return _apply(build_strategy9(), STRATEGY_EDITS10)


def strip_visual3(t):
    """reverse only XA-3 (-> the Visual of 69e6f0c byte for byte)."""
    return _revert(t, VISUAL_EDITS3)


def strip_visual6(t):
    """reverse only XA-6 (-> the Visual of cbb996d byte for byte)."""
    return _revert(t, VISUAL_EDITS6)


def strip_strategy10(t):
    """reverse only XA-10 (-> the Strategy of 3ca1837 byte for byte)."""
    return _revert(t, STRATEGY_EDITS10)


def strip_strategy9(t):
    """reverse XA-10 when present (all or nothing) and XA-9 (-> the Strategy of a32bd85 byte for byte)."""
    if t is not None and STRATEGY_EDITS10[0][2] in t:
        t = strip_strategy10(t)
    return _revert(t, STRATEGY_EDITS9)


def strip_strategy8(t):
    """reverse XA-9 when present (all or nothing) and XA-8 (-> the Strategy of 6b9458d byte for byte)."""
    if t is not None and STRATEGY_EDITS9[0][2] in t:
        t = strip_strategy9(t)
    return _revert(t, STRATEGY_EDITS8)


def strip_strategy7(t):
    """reverse XA-8 when present (all or nothing) and XA-7 (-> the Strategy of 0c6cd71 byte for byte)."""
    if t is not None and STRATEGY_EDITS8[0][2] in t:
        t = strip_strategy8(t)
    return _revert(t, STRATEGY_EDITS7)


def strip_strategy6(t):
    """reverse XA-7 when present (all or nothing) and XA-6 (-> the Strategy of cbb996d byte for byte)."""
    if t is not None and STRATEGY_EDITS7[0][2] in t:
        t = strip_strategy7(t)
    return _revert(t, STRATEGY_EDITS6)


def strip_visual5(t):
    """reverse XA-6 when present (all or nothing) and XA-5 (-> the Visual of 7363ef1 / a33d2b0 byte for byte)."""
    if t is not None and VISUAL_EDITS6[0][2] in t:
        t = strip_visual6(t)
    return _revert(t, VISUAL_EDITS5)


def strip_strategy5(t):
    """reverse XA-6 when present (all or nothing) and XA-5 (-> the Strategy of 7363ef1 / a33d2b0 byte for byte)."""
    if t is not None and STRATEGY_EDITS6[0][2] in t:
        t = strip_strategy6(t)
    return _revert(t, STRATEGY_EDITS5)


def strip_visual4(t):
    """reverse XA-5 when present (all or nothing) and XA-4 (-> the Visual of 17d1ca2 byte for byte)."""
    if t is not None and VISUAL_EDITS5[0][2] in t:
        t = strip_visual5(t)
    return _revert(t, VISUAL_EDITS4)


def strip_strategy4(t):
    """reverse XA-5 when present (all or nothing) and XA-4 (-> the Strategy of 17d1ca2 byte for byte)."""
    if t is not None and STRATEGY_EDITS5[0][2] in t:
        t = strip_strategy5(t)
    return _revert(t, STRATEGY_EDITS4)


def strip_visual(t):
    """reverse XA-4, XA-3 and XA-1 (-> the Visual of BASE_REV byte for byte)."""
    return _revert(strip_visual3(strip_visual4(t)), VISUAL_EDITS)


def strip_strategy3(t):
    """reverse only XA-3 (-> the Strategy of 69e6f0c byte for byte)."""
    return _revert(t, STRATEGY_EDITS3)


def strip_strategy2(t):
    """reverse only XA-2 (-> the XA-1 Strategy of 2732772 byte for byte)."""
    return _revert(t, STRATEGY_EDITS2)


def strip_strategy(t):
    """reverse XA-4, XA-3, XA-2 and XA-1 (-> the Strategy of BASE_REV byte for byte)."""
    return _revert(strip_strategy2(strip_strategy3(strip_strategy4(t))), STRATEGY_EDITS)


# ---- helpers for the older fixtures ------------------------------------------------------------------------------------
def pre_xa(path, text=None):
    """ZONE-P / ZONE-ST text with the XA-1 / XA-3 / XA-4 (and on ZONE-ST XA-2) edits reverted (unchanged if they are not present)."""
    if text is None:
        text = _rd(path)
    s = (strip_visual if path == VIS_PATH else strip_strategy)(text)
    return text if s is None else s


def xa_ok(path, rev):
    """True when the working-tree file differs from `rev` only by the XA-1 (+ XA-2) + XA-3 + XA-4 edits (exact, byte for byte)."""
    if path not in XA_FILES:
        return False
    s = (strip_visual if path == VIS_PATH else strip_strategy)(_rd(path))
    return s is not None and s == show(rev, path)


if __name__ == "__main__":
    for path, fn in ((ENG_PATH, build_engine), (VIS_PATH, build_visual), (STR_PATH, build_strategy)):
        open(os.path.join(ROOT, path), "w", encoding="utf-8").write(fn())
        print("written", path)


def drop_xa(names, rev):
    """remove ZONE-P / ZONE-ST from a changed-path list only when they differ from `rev` exactly by XA-1."""
    return [n for n in names if not xa_ok(n, rev)]


def unadapt(path, text):
    """a test / generator file with its XA-1 edits reverted (unchanged for files not in TEST_ADAPT)."""
    out = __import__("uj3_adapt").unadapt(path, __import__("cad_adapt").unadapt(path, text))     # CAD-1, then UJ-3 edits (later) are reverted first
    for a, b in reversed(TEST_ADAPT.get(path, [])):
        if out is None or out.count(b) != 1:
            return None
        out = out.replace(b, a)
    return out


def test_ok(path):
    """True when the file differs from BASE_REV only by its exact XA-1 edits."""
    return path in TEST_ADAPT and unadapt(path, _rd(path)) == show(BASE_REV, path)


# exact XA-1 edits of existing test / generator files vs BASE_REV (generated from the diff; unadapt() reverses them)
TEST_ADAPT = {'tests/bon_sim.py': [('ROOT = bb.ROOT\n'
                       'CUR = open(os.path.join(ROOT, "ZoneVisualPractical.pine"), encoding="utf-8").read()\n'
                       'BASE = bb.git_show(bb.BON_BASE_REV)\n',
                       'ROOT = bb.ROOT\n'
                       'CUR = __import__("xa_build").pre_xa("ZoneVisualPractical.pine", open(os.path.join(ROOT, '
                       '"ZoneVisualPractical.pine"), encoding="utf-8").read())  # XA-1 Gold defaults stripped -> '
                       'f253890 text (delta pinned by xa_sim)\n'
                       'BASE = bb.git_show(bb.BON_BASE_REV)\n')],
 'tests/bte_build.py': [('    """a test / generator file with its BTE-1 edits reverted (unchanged for files not in '
                         'TEST_ADAPT)."""\n'
                         '    out = text\n'
                         '    for a, b in reversed(TEST_ADAPT.get(path, [])):\n',
                         '    """a test / generator file with its BTE-1 edits reverted (unchanged for files not in '
                         'TEST_ADAPT)."""\n'
                         '    out = __import__("xa_build").unadapt(path, text)     # XA-1 edits (later) are reverted '
                         'first\n'
                         '    for a, b in reversed(TEST_ADAPT.get(path, [])):\n'),
                        ('    """True when the file differs from BASE_REV only by its exact BTE-1 edits."""\n'
                         '    return path in TEST_ADAPT and unadapt(path, _rd(path)) == _show(BASE_REV, path)\n'
                         '\n',
                         '    """True when the file differs from BASE_REV only by its exact BTE-1 edits."""\n'
                         '    return (path in TEST_ADAPT or path in __import__("xa_build").TEST_ADAPT) and '
                         'unadapt(path, _rd(path)) == _show(BASE_REV, path)\n'
                         '\n')],
 'tests/bte_sim.py': [('    mod = git("diff", "--name-only", "--diff-filter=MDR", be.BASE_REV, "--").split()\n'
                       '    rest = [m for m in mod if not (be.bte_pine_ok(m, be.BASE_REV) or be.test_ok(m))]\n'
                       '    check("BE-07 vs e1c3cea: the BTC Visual / Strategy differ exactly by the new layer, '
                       'every other changed file is a test / "\n',
                       '    mod = git("diff", "--name-only", "--diff-filter=MDR", be.BASE_REV, "--").split()\n'
                       '    rest = [m for m in mod if not (be.bte_pine_ok(m, be.BASE_REV) or be.test_ok(m) or '
                       '__import__("xa_build").xa_ok(m, be.BASE_REV))]   # XA-1: exact\n'
                       '    check("BE-07 vs e1c3cea: the BTC Visual / Strategy differ exactly by the new layer, '
                       'every other changed file is a test / "\n'),
                      ('          "symbols\' Pine files untouched", set(mod) >= {bb.BTC_PATH, sb.BTS_PATH} and not '
                       'rest\n'
                       '          and not [m for m in mod if m.endswith(".pine") and m not in (bb.BTC_PATH, '
                       'sb.BTS_PATH)], str(rest))\n'
                       '    m = S.replace("import sekine3310/ZoneEnginePracticalBTCUSD/1 as zn", "import '
                       'sekine3310/ZoneEnginePracticalGBPJPY/3 as zn")\n',
                       '          "symbols\' Pine files untouched", set(mod) >= {bb.BTC_PATH, sb.BTS_PATH} and not '
                       'rest\n'
                       '          and not [m for m in mod if m.endswith(".pine") and m not in (bb.BTC_PATH, '
                       'sb.BTS_PATH)\n'
                       '                   and not __import__("xa_build").xa_ok(m, be.BASE_REV)], str(rest))\n'
                       '    m = S.replace("import sekine3310/ZoneEnginePracticalBTCUSD/1 as zn", "import '
                       'sekine3310/ZoneEnginePracticalGBPJPY/3 as zn")\n')],
 'tests/fvg_batch_a_sim.py': [('_RAW = open(VIS_PATH, encoding="utf-8").read()\n'
                               '_RAW = __import__("bon_build").strip_bon(_RAW) or _RAW  # bonus defaults stripped -> '
                               '9270c50 text (delta pinned by bon_sim)\n',
                               '_RAW = open(VIS_PATH, encoding="utf-8").read()\n'
                               '_RAW = __import__("xa_build").pre_xa("ZoneVisualPractical.pine", _RAW)  # XA-1 Gold '
                               'defaults stripped -> f253890 text (delta pinned by xa_sim)\n'
                               '_RAW = __import__("bon_build").strip_bon(_RAW) or _RAW  # bonus defaults stripped -> '
                               '9270c50 text (delta pinned by bon_sim)\n')],
 'tests/fvg_re10045_sim.py': [('def main():\n'
                               '    cur = open(os.path.join(ROOT, "ZoneVisualPractical.pine"), '
                               'encoding="utf-8").read()\n'
                               '    cur = __import__("bon_build").strip_bon(cur) or cur  # bonus defaults stripped '
                               '-> 9270c50 text (delta pinned by bon_sim)\n',
                               'def main():\n'
                               '    cur = __import__("xa_build").pre_xa("ZoneVisualPractical.pine", '
                               'open(os.path.join(ROOT, "ZoneVisualPractical.pine"), encoding="utf-8").read())  # '
                               'XA-1 Gold defaults stripped -> f253890 text (delta pinned by xa_sim)\n'
                               '    cur = __import__("bon_build").strip_bon(cur) or cur  # bonus defaults stripped '
                               '-> 9270c50 text (delta pinned by bon_sim)\n')],
 'tests/fvl_sim.py': [('ROOT = lb.ROOT\n'
                       'CUR = open(os.path.join(ROOT, "ZoneVisualPractical.pine"), encoding="utf-8").read()\n'
                       'CUR = __import__("bon_build").strip_bon(CUR) or CUR  # bonus defaults stripped -> 9270c50 '
                       'text (delta pinned by bon_sim)\n',
                       'ROOT = lb.ROOT\n'
                       'CUR = __import__("xa_build").pre_xa("ZoneVisualPractical.pine", open(os.path.join(ROOT, '
                       '"ZoneVisualPractical.pine"), encoding="utf-8").read())  # XA-1 Gold defaults stripped -> '
                       'f253890 text (delta pinned by xa_sim)\n'
                       'CUR = __import__("bon_build").strip_bon(CUR) or CUR  # bonus defaults stripped -> 9270c50 '
                       'text (delta pinned by bon_sim)\n')],
 'tests/jpy_build.py': [('def build():\n'
                         '    return jpy_transform(open(os.path.join(ROOT, SRC_PATH), encoding="utf-8").read())\n'
                         '\n',
                         'def build():\n'
                         '    return jpy_transform(__import__("xa_build").pre_xa(SRC_PATH, open(os.path.join(ROOT, '
                         'SRC_PATH), encoding="utf-8").read()))  # XA-1 Gold defaults stripped -> f253890 text '
                         '(delta pinned by xa_sim)\n'
                         '\n')],
 'tests/jpy_sim.py': [('ROOT = jb.ROOT\n'
                       'VIS = open(os.path.join(ROOT, jb.SRC_PATH), encoding="utf-8").read()\n'
                       'JPY = __import__("uj_build").pre_uj(jb.JPY_PATH) if os.path.exists(os.path.join(ROOT, '
                       'jb.JPY_PATH)) else ""     # UJ-1: USDJPY Visual / Strategy may differ only by the USDJPY '
                       'Engine split + sizing (exact, see uj_build)\n',
                       'ROOT = jb.ROOT\n'
                       'VIS = __import__("xa_build").pre_xa(jb.SRC_PATH, open(os.path.join(ROOT, jb.SRC_PATH), '
                       'encoding="utf-8").read())  # XA-1 Gold defaults stripped -> f253890 text (delta pinned by '
                       'xa_sim)\n'
                       'JPY = __import__("uj_build").pre_uj(jb.JPY_PATH) if os.path.exists(os.path.join(ROOT, '
                       'jb.JPY_PATH)) else ""     # UJ-1: USDJPY Visual / Strategy may differ only by the USDJPY '
                       'Engine split + sizing (exact, see uj_build)\n'),
                      ('    check("JS-10 XAUUSD Visual (ZONE-P), Strategy (ZONE-ST), Engines (/2, /5, /6) and the '
                       'old strategies unchanged vs 25af623",\n'
                       '          d.strip() == "", d)\n'
                       '\n',
                       '    check("JS-10 XAUUSD Visual (ZONE-P), Strategy (ZONE-ST), Engines (/2, /5, /6) and the '
                       'old strategies unchanged vs 25af623",\n'
                       '          __import__("xa_build").drop_xa(d.split(), "25af623") == [], d)\n'
                       '\n')],
 'tests/nr_a1_sim.py': [('ROOT = na.ROOT\n'
                         'CUR = open(os.path.join(ROOT, "ZoneVisualPractical.pine"), encoding="utf-8").read()\n'
                         'CUR = __import__("bon_build").strip_bon(CUR) or CUR  # bonus defaults stripped -> 9270c50 '
                         'text (delta pinned by bon_sim)\n',
                         'ROOT = na.ROOT\n'
                         'CUR = __import__("xa_build").pre_xa("ZoneVisualPractical.pine", open(os.path.join(ROOT, '
                         '"ZoneVisualPractical.pine"), encoding="utf-8").read())  # XA-1 Gold defaults stripped -> '
                         'f253890 text (delta pinned by xa_sim)\n'
                         'CUR = __import__("bon_build").strip_bon(CUR) or CUR  # bonus defaults stripped -> 9270c50 '
                         'text (delta pinned by bon_sim)\n')],
 'tests/nr_s1_sim.py': [('ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))\n'
                         'CUR = open(os.path.join(ROOT, "ZoneVisualPractical.pine"), encoding="utf-8").read()\n'
                         'CUR = __import__("bon_build").strip_bon(CUR) or CUR  # bonus defaults stripped -> 9270c50 '
                         'text (delta pinned by bon_sim)\n',
                         'ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))\n'
                         'CUR = __import__("xa_build").pre_xa("ZoneVisualPractical.pine", open(os.path.join(ROOT, '
                         '"ZoneVisualPractical.pine"), encoding="utf-8").read())  # XA-1 Gold defaults stripped -> '
                         'f253890 text (delta pinned by xa_sim)\n'
                         'CUR = __import__("bon_build").strip_bon(CUR) or CUR  # bonus defaults stripped -> 9270c50 '
                         'text (delta pinned by bon_sim)\n')],
 'tests/practical_strategy_sim.py': [('VIS_PRE_GATE_REV = "b3b69ae"\n'
                                      'VIS_CUR = open(os.path.join(ROOT, "ZoneVisualPractical.pine"), '
                                      'encoding="utf-8").read()\n'
                                      'VIS_CUR = __import__("bon_build").strip_bon(VIS_CUR) or VIS_CUR  # bonus '
                                      'defaults stripped -> 9270c50 text (delta pinned by bon_sim)\n',
                                      'VIS_PRE_GATE_REV = "b3b69ae"\n'
                                      'VIS_CUR = __import__("xa_build").pre_xa("ZoneVisualPractical.pine", '
                                      'open(os.path.join(ROOT, "ZoneVisualPractical.pine"), '
                                      'encoding="utf-8").read())  # XA-1 Gold defaults stripped -> f253890 text '
                                      '(delta pinned by xa_sim)\n'
                                      'VIS_CUR = __import__("bon_build").strip_bon(VIS_CUR) or VIS_CUR  # bonus '
                                      'defaults stripped -> 9270c50 text (delta pinned by bon_sim)\n')],
 'tests/rn1_sim.py': [('    d = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", rb.RN_BASE_REV, "--"] + '
                       'prod, capture_output=True, text=True).stdout\n'
                       '    vis = open(os.path.join(ROOT, "ZoneVisualPractical.pine"), encoding="utf-8").read()\n'
                       '    vis = __import__("bon_build").strip_bon(vis) or vis  # bonus defaults stripped -> '
                       '9270c50 text (delta pinned by bon_sim)\n',
                       '    d = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", rb.RN_BASE_REV, "--"] + '
                       'prod, capture_output=True, text=True).stdout\n'
                       '    vis = __import__("xa_build").pre_xa("ZoneVisualPractical.pine", open(os.path.join(ROOT, '
                       '"ZoneVisualPractical.pine"), encoding="utf-8").read())  # XA-1 Gold defaults stripped -> '
                       'f253890 text (delta pinned by xa_sim)\n'
                       '    vis = __import__("bon_build").strip_bon(vis) or vis  # bonus defaults stripped -> '
                       '9270c50 text (delta pinned by bon_sim)\n')],
 'tests/rnv_sim.py': [('ROOT = vb.ROOT\n'
                       'CUR = open(os.path.join(ROOT, "ZoneVisualPractical.pine"), encoding="utf-8").read()\n'
                       'CUR = __import__("bon_build").strip_bon(CUR) or CUR  # bonus defaults stripped -> 9270c50 '
                       'text (delta pinned by bon_sim)\n',
                       'ROOT = vb.ROOT\n'
                       'CUR = __import__("xa_build").pre_xa("ZoneVisualPractical.pine", open(os.path.join(ROOT, '
                       '"ZoneVisualPractical.pine"), encoding="utf-8").read())  # XA-1 Gold defaults stripped -> '
                       'f253890 text (delta pinned by xa_sim)\n'
                       'CUR = __import__("bon_build").strip_bon(CUR) or CUR  # bonus defaults stripped -> 9270c50 '
                       'text (delta pinned by bon_sim)\n')],
 'tests/st1_sim.py': [('ROOT = tb.ROOT\n'
                       'ST = s2.strip_st2(s3.strip_st3(open(os.path.join(ROOT, tb.ST_PATH), '
                       'encoding="utf-8").read())) if os.path.exists(os.path.join(ROOT, tb.ST_PATH)) else ""\n'
                       'VIS = open(os.path.join(ROOT, "ZoneVisualPractical.pine"), encoding="utf-8").read()\n'
                       'BASE = tb.git_show(tb.ST_BASE_REV)\n',
                       'ROOT = tb.ROOT\n'
                       'ST = s2.strip_st2(s3.strip_st3(__import__("xa_build").pre_xa("ZoneStrategyXAU.pine", '
                       'open(os.path.join(ROOT, tb.ST_PATH), encoding="utf-8").read()))) if '
                       'os.path.exists(os.path.join(ROOT, tb.ST_PATH)) else ""\n'
                       'VIS = __import__("xa_build").pre_xa("ZoneVisualPractical.pine", open(os.path.join(ROOT, '
                       '"ZoneVisualPractical.pine"), encoding="utf-8").read())  # XA-1 Gold defaults stripped -> '
                       'f253890 text (delta pinned by xa_sim)\n'
                       'BASE = tb.git_show(tb.ST_BASE_REV)\n'),
                      ('    d = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", tb.ST_BASE_REV, "--"] + '
                       'names, capture_output=True, text=True).stdout\n'
                       '    check("TS-12 ZONE-P, Engines (/2, /5, /6), Strategy LONG / SHORT, SignalEngine unchanged '
                       'vs beca989", d.strip() == "", d)\n'
                       '\n',
                       '    d = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", tb.ST_BASE_REV, "--"] + '
                       'names, capture_output=True, text=True).stdout\n'
                       '    check("TS-12 ZONE-P, Engines (/2, /5, /6), Strategy LONG / SHORT, SignalEngine unchanged '
                       'vs beca989", __import__("xa_build").drop_xa(d.split(), tb.ST_BASE_REV) == [], d)\n'
                       '\n')],
 'tests/st2_sim.py': [('ROOT = tb.ROOT\n'
                       'ST = s3.strip_st3(open(os.path.join(ROOT, s2.ST_PATH), encoding="utf-8").read())\n'
                       'RESULTS = []\n',
                       'ROOT = tb.ROOT\n'
                       'ST = s3.strip_st3(__import__("xa_build").pre_xa("ZoneStrategyXAU.pine", '
                       'open(os.path.join(ROOT, s2.ST_PATH), encoding="utf-8").read()))  # XA-1 Gold defaults '
                       'stripped -> f253890 text (delta pinned by xa_sim)\n'
                       'RESULTS = []\n'),
                      ('    d = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", "f1d54bf", "--"] + names, '
                       'capture_output=True, text=True).stdout\n'
                       '    check("TS-11 ZONE-P, Engines (/2, /5, /6), Strategy LONG / SHORT, SignalEngine unchanged '
                       'vs f1d54bf", d.strip() == "", d)\n'
                       '\n',
                       '    d = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", "f1d54bf", "--"] + names, '
                       'capture_output=True, text=True).stdout\n'
                       '    check("TS-11 ZONE-P, Engines (/2, /5, /6), Strategy LONG / SHORT, SignalEngine unchanged '
                       'vs f1d54bf", __import__("xa_build").drop_xa(d.split(), "f1d54bf") == [], d)\n'
                       '\n')],
 'tests/st3_sim.py': [('ROOT = s3.ROOT\n'
                       'ST = open(os.path.join(ROOT, s3.ST_PATH), encoding="utf-8").read()\n'
                       'RESULTS = []\n',
                       'ROOT = s3.ROOT\n'
                       'ST = __import__("xa_build").pre_xa("ZoneStrategyXAU.pine", open(os.path.join(ROOT, '
                       's3.ST_PATH), encoding="utf-8").read())  # XA-1 Gold defaults stripped -> f253890 text (delta '
                       'pinned by xa_sim)\n'
                       'RESULTS = []\n'),
                      ('    d = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", "f1d54bf", "--"] + names, '
                       'capture_output=True, text=True).stdout\n'
                       '    check("TS-09 ZONE-P, Engines (/2, /5, /6), Strategy LONG / SHORT, SignalEngine '
                       'unchanged", d.strip() == "", d)\n'
                       '\n',
                       '    d = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", "f1d54bf", "--"] + names, '
                       'capture_output=True, text=True).stdout\n'
                       '    check("TS-09 ZONE-P, Engines (/2, /5, /6), Strategy LONG / SHORT, SignalEngine '
                       'unchanged", __import__("xa_build").drop_xa(d.split(), "f1d54bf") == [], d)\n'
                       '\n')],
 'tests/stj_sim.py': [('JPYV = __import__("uj_build").pre_uj(jb.JPY_PATH)\n'
                       'XST = open(os.path.join(ROOT, "ZoneStrategyXAU.pine"), encoding="utf-8").read()\n'
                       'RESULTS = []\n',
                       'JPYV = __import__("uj_build").pre_uj(jb.JPY_PATH)\n'
                       'XST = __import__("xa_build").pre_xa("ZoneStrategyXAU.pine", open(os.path.join(ROOT, '
                       '"ZoneStrategyXAU.pine"), encoding="utf-8").read())  # XA-1 Gold defaults stripped -> f253890 '
                       'text (delta pinned by xa_sim)\n'
                       'RESULTS = []\n')],
 'tests/sw1_sim.py': [('    d = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", sb.SW_BASE_REV, "--"] + '
                       'names, capture_output=True, text=True).stdout\n'
                       '    vis = open(os.path.join(ROOT, "ZoneVisualPractical.pine"), encoding="utf-8").read()\n'
                       '    vis = __import__("bon_build").strip_bon(vis) or vis  # bonus defaults stripped -> '
                       '9270c50 text (delta pinned by bon_sim)\n',
                       '    d = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", sb.SW_BASE_REV, "--"] + '
                       'names, capture_output=True, text=True).stdout\n'
                       '    vis = __import__("xa_build").pre_xa("ZoneVisualPractical.pine", open(os.path.join(ROOT, '
                       '"ZoneVisualPractical.pine"), encoding="utf-8").read())  # XA-1 Gold defaults stripped -> '
                       'f253890 text (delta pinned by xa_sim)\n'
                       '    vis = __import__("bon_build").strip_bon(vis) or vis  # bonus defaults stripped -> '
                       '9270c50 text (delta pinned by bon_sim)\n')],
 'tests/swv_sim.py': [('ROOT = wb.ROOT\n'
                       'CUR = open(os.path.join(ROOT, "ZoneVisualPractical.pine"), encoding="utf-8").read()\n'
                       'CUR = __import__("bon_build").strip_bon(CUR) or CUR  # bonus defaults stripped -> 9270c50 '
                       'text (delta pinned by bon_sim)\n',
                       'ROOT = wb.ROOT\n'
                       'CUR = __import__("xa_build").pre_xa("ZoneVisualPractical.pine", open(os.path.join(ROOT, '
                       '"ZoneVisualPractical.pine"), encoding="utf-8").read())  # XA-1 Gold defaults stripped -> '
                       'f253890 text (delta pinned by xa_sim)\n'
                       'CUR = __import__("bon_build").strip_bon(CUR) or CUR  # bonus defaults stripped -> 9270c50 '
                       'text (delta pinned by bon_sim)\n')],
 'tests/uj_build.py': [('    # BTE-1 (later split of the BTC Engine): the BTC Visual / Strategy may also differ, '
                        'exactly by that layer\n'
                        '    return [n for n in names if not ((n in UJ_FILES and uj_ok(n, rev)) or '
                        '__import__("bte_build").bte_pine_ok(n, rev))]\n'
                        '\n',
                        '    # BTE-1 (later split of the BTC Engine): the BTC Visual / Strategy may also differ, '
                        'exactly by that layer\n'
                        '    # XA-1 (Gold defaults): ZONE-P / ZONE-ST may also differ, exactly by that layer\n'
                        '    return [n for n in names if not ((n in UJ_FILES and uj_ok(n, rev)) or '
                        '__import__("bte_build").bte_pine_ok(n, rev)\n'
                        '                                     or __import__("xa_build").xa_ok(n, rev))]\n'
                        '\n'),
                       ('    """True when the test file differs from BASE_REV only by its exact UJ-1 adaptation."""\n'
                        '    return (path in TEST_ADAPT or path in __import__("bte_build").TEST_ADAPT) and '
                        'unadapt(path, _rd(path)) == base(path)\n'
                        '\n',
                        '    """True when the test file differs from BASE_REV only by its exact UJ-1 adaptation."""\n'
                        '    return (path in TEST_ADAPT or path in __import__("bte_build").TEST_ADAPT or path in '
                        '__import__("xa_build").TEST_ADAPT) \\\n'
                        '        and unadapt(path, _rd(path)) == base(path)\n'
                        '\n')],
 'tests/uj_sim.py': [('    mod = git("diff", "--name-only", "--diff-filter=MDR", ub.BASE_REV, "--").split()\n'
                      '    mod = [m for m in mod if not __import__("bte_build").bte_pine_ok(m, ub.BASE_REV)]     # '
                      'BTE-1 BTC split: exact\n'
                      '    rest = [m for m in mod if m not in ub.UJ_FILES and not ub.test_ok(m)]\n',
                      '    mod = git("diff", "--name-only", "--diff-filter=MDR", ub.BASE_REV, "--").split()\n'
                      '    mod = [m for m in mod if not (__import__("bte_build").bte_pine_ok(m, ub.BASE_REV) or '
                      '__import__("xa_build").xa_ok(m, ub.BASE_REV))]     # BTE-1 / XA-1: exact\n'
                      '    rest = [m for m in mod if m not in ub.UJ_FILES and not ub.test_ok(m)]\n'),
                     ('    mod = git("diff", "--name-only", "--diff-filter=MDR", UJ1, "--").split()\n'
                      '    mod = [m for m in mod if not (__import__("bte_build").bte_pine_ok(m, UJ1) or '
                      '__import__("bte_build").test_ok(m))]   # BTE-1: exact\n'
                      '    check("UD-07 vs a6a275c only the USDJPY Visual / Strategy and their build / test change '
                      '(Engine, other symbols, shared "\n',
                      '    mod = git("diff", "--name-only", "--diff-filter=MDR", UJ1, "--").split()\n'
                      '    mod = [m for m in mod if not (__import__("bte_build").bte_pine_ok(m, UJ1) or '
                      '__import__("bte_build").test_ok(m)\n'
                      '                                  or __import__("xa_build").xa_ok(m, UJ1) or '
                      '__import__("xa_build").test_ok(m))]   # BTE-1 / XA-1: exact\n'
                      '    check("UD-07 vs a6a275c only the USDJPY Visual / Strategy and their build / test change '
                      '(Engine, other symbols, shared "\n')],
 'tests/zp_overlap_sim.py': [('ROOT = zp.ROOT\n'
                              'CUR = open(os.path.join(ROOT, "ZoneVisualPractical.pine"), encoding="utf-8").read()\n'
                              'CUR = __import__("bon_build").strip_bon(CUR) or CUR  # bonus defaults stripped -> '
                              '9270c50 text (delta pinned by bon_sim)\n',
                              'ROOT = zp.ROOT\n'
                              'CUR = __import__("xa_build").pre_xa("ZoneVisualPractical.pine", '
                              'open(os.path.join(ROOT, "ZoneVisualPractical.pine"), encoding="utf-8").read())  # '
                              'XA-1 Gold defaults stripped -> f253890 text (delta pinned by xa_sim)\n'
                              'CUR = __import__("bon_build").strip_bon(CUR) or CUR  # bonus defaults stripped -> '
                              '9270c50 text (delta pinned by bon_sim)\n')]}
