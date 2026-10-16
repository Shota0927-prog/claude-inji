"""EU-1 — EURUSD port of the GBPJPY trio (OANDA:EURUSD 5M): Engine library, Zone Visual, Strategy.

Deterministic transforms by exact, unique text replacements; each strip_*() applies its edits in reverse and must give
the GBPJPY source back byte for byte (fixture eu_sim):
  ZoneEnginePracticalGBPJPY.pine -> ZoneEnginePracticalEURUSD.pine   (ENGINE_EDITS)
  ZoneVisualGBPJPY.pine          -> ZoneVisualEURUSD.pine            (VISUAL_EDITS = shared ZONE_EDITS + visual-only)
  ZoneStrategyGBPJPY.pine        -> ZoneStrategyEURUSD.pine          (STRATEGY_EDITS = shared ZONE_EDITS + strategy-only)
Kinds (eu_sim checks the code lines each kind touches):
  header    comments
  name      library name / indicator / strategy title and shorttitle / import of the EURUSD library
  input     price-difference inputs in USD (1 pip = 0.0001): default / label / minval / step / tooltip / group
  rn        Round Number: EURUSD steps 0.0100 / 0.0050, step validation on mintick integers (no 0.125 / x8 rule),
            ticker gate EURUSD; Engine f_rnLevelIn compares on mintick integers (EURUSD library only)
  display   Zone top / bottom via format.mintick, width in pips
  size      JPY loss budget -> strategy.convert_to_symbol (chart currency USD) before dividing (1 lot = 100,000, 0.01)
  alert     1 pip = 0.0001 for the SL distance in pips
Price-difference defaults are verification starting values set from a daily-volatility comparison (not validated with
5M ATR, not optimised). Scores, ratios, days, bar counts, lengths and timeframes are unchanged. The GBPJPY files and
every other file are not modified.
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENG_SRC, VIS_SRC, STR_SRC = "ZoneEnginePracticalGBPJPY.pine", "ZoneVisualGBPJPY.pine", "ZoneStrategyGBPJPY.pine"
ENG_PATH, VIS_PATH, STR_PATH = "ZoneEnginePracticalEURUSD.pine", "ZoneVisualEURUSD.pine", "ZoneStrategyEURUSD.pine"
IMPORT_GBE = "import sekine3310/ZoneEnginePracticalGBPJPY/3 as zn\n"
IMPORT_EU = "import sekine3310/ZoneEnginePracticalEURUSD/1 as zn\n"     # first publish of the new library = version 1

# ---- Engine -----------------------------------------------------------------------------------------------------------
ENGINE_EDITS = [
    ("header",
     "//  ★ GBPJPY 派生 (ZoneEnginePracticalGBPJPY、生成: tests/gbe_build.py)。ZoneEnginePractical/6 (SW-1 / RN-1) に\n",
     "//  ★ EURUSD 派生 (ZoneEnginePracticalEURUSD、生成: tests/eu_build.py)。ZoneEnginePracticalGBPJPY (/3) と同じ処理で、\n"
     "//    違いは Library 名と Round Number の包含判定 (f_rnLevelIn) を最小価格刻みの整数で比べることだけ (EU-1)。\n"
     "//    0.0100 / 0.0050 のような 2 進で正確に表せない刻みでも、境界ちょうどの価格で判定が漏れない。\n"
     "//  ★ 以下は GBPJPY 派生 (ZoneEnginePracticalGBPJPY、生成: tests/gbe_build.py) の説明。ZoneEnginePractical/6 (SW-1 / RN-1) に\n"),
    ("name",
     'library("ZoneEnginePracticalGBPJPY", overlay = true)\n',
     'library("ZoneEnginePracticalEURUSD", overlay = true)\n'),
    ("rn",
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
     "    lv\n",
     "// Round Number: [zBot, zTop] (境界を含む) 内の step の倍数のうち中心に最も近いもの (同距離は低い方)。無ければ na\n"
     "//  EU-1: 最小価格刻み (syminfo.mintick) の整数で比べる。節目は刻みの整数倍なので\n"
     "//    節目 >= zBot  <=>  節目の tick 数 >= ceil(zBot / mintick)、節目 <= zTop  <=>  節目の tick 数 <= floor(zTop / mintick)。\n"
     "//    1e-6 tick は計算誤差の吸収だけ (格子上の値が 109999.99999999999 tick になっても 110000 として扱う)。\n"
     "//    整数どうしの割り算 (tick / 刻み tick) は商が整数なら正確なので、0.0100 / 0.0050 の境界でも漏れない。\n"
     "f_rnLevelIn(float zBot, float zTop, float step) =>\n"
     "    float lv = na\n"
     "    int   sT = math.round(step / syminfo.mintick)\n"
     "    if sT > 0\n"
     "        float sF = sT                                          // 割り算は float で (int / int の切り捨てに依存しない)\n"
     "        int bT = math.ceil(zBot / syminfo.mintick - 1e-6)\n"
     "        int tT = math.floor(zTop / syminfo.mintick + 1e-6)\n"
     "        int k1 = math.ceil(bT / sF)\n"
     "        int k2 = math.floor(tT / sF)\n"
     "        if k1 <= k2\n"
     "            float ctrT = (bT + tT) / 2.0\n"
     "            int kc = math.max(k1, math.min(k2, math.floor(ctrT / sF)))\n"
     "            int lvT = kc * sT\n"
     "            if kc + 1 <= k2\n"
     "                if (kc + 1) * sT - ctrT < ctrT - lvT\n"
     "                    lvT := (kc + 1) * sT\n"
     "            lv := lvT * syminfo.mintick\n"
     "    lv\n"),
]

# ---- shared Zone edits (Visual and Strategy carry the same Zone input block) -----------------------------------------
ZONE_EDITS = [
    ("input",
     'zoneHalfWidth = input.float(0.05, "[暫定] Zone Half Width (円)", minval = 0.005, step = 0.005, group = G_ZONE,\n',
     'zoneHalfWidth = input.float(0.00020, "[検証開始値] Zone Half Width (USD)", minval = 0.00001, step = 0.00005, group = G_ZONE,\n'),
    ("input",
     '     "GBPJPY 比較候補 (検証用・適正値ではない): 0.03 / 0.05 / 0.08 円 (= 3 / 5 / 8 pips)。初期 0.05 = GBPJPY 基準設定 (Visual / Strategy 共通)。")\n',
     '     "EURUSD: 1 pip = 0.0001。初期 0.00020 = 2 pips (Visual / Strategy 共通)。日次ボラの比較から決めた検証開始値で、5分足 ATR で検証した値・最適値ではない。")\n'),
    ("input",
     'slopeThrMod = input.float(0.01, "[暫定] Slope Threshold · Moderate (円/lookback)", minval = 0.0, step = 0.005, group = G_SLOPE)\n'
     'slopeThrStrong = input.float(0.02, "[暫定] Slope Threshold · Strong (円/lookback)",   minval = 0.0, step = 0.005, group = G_SLOPE)\n',
     'slopeThrMod = input.float(0.00004, "[検証開始値] Slope Threshold · Moderate (USD/lookback)", minval = 0.0, step = 0.00001, group = G_SLOPE,\n'
     '     tooltip = "Slope Lookback 本数の間の MA の価格差。初期 0.00004 = 0.4 pips (検証開始値)。lookback 本数・計算式は変えない。")\n'
     'slopeThrStrong = input.float(0.00008, "[検証開始値] Slope Threshold · Strong (USD/lookback)",   minval = 0.0, step = 0.00001, group = G_SLOPE,\n'
     '     tooltip = "Slope Lookback 本数の間の MA の価格差。初期 0.00008 = 0.8 pips (検証開始値)。")\n'),
    ("input",
     'maClusterDist = input.float(0.30, "[暫定] MA Cluster Distance (円)", minval = 0.0, step = 0.01, group = G_SLOPE)\n',
     'maClusterDist = input.float(0.00120, "[検証開始値] MA Cluster Distance (USD)", minval = 0.0, step = 0.0001, group = G_SLOPE,\n'
     '     tooltip = "初期 0.00120 = 12 pips (検証開始値)。")\n'),
    ("input",
     'touchRearmDist = input.float(0.15, "[暫定] Touch Re-arm Distance (円)", minval = 0.0, step = 0.01, group = G_TOUCH,\n',
     'touchRearmDist = input.float(0.00060, "[検証開始値] Touch Re-arm Distance (USD・初期 6 pips)", minval = 0.0, step = 0.0001, group = G_TOUCH,\n'),
    ("input",
     'dsDist = input.float(0.05, "[暫定] Day/Swing Merge Distance (円)", minval = 0.0, step = 0.001, group = G_DHL,\n'
     '     tooltip = "Merge Nearby の価格差 (Cluster Distance とは別)。0 = 完全に同じ価格だけ。0.05 円は比較開始用の暫定値。")\n',
     'dsDist = input.float(0.00020, "[検証開始値] Day/Swing Merge Distance (USD)", minval = 0.0, step = 0.00001, group = G_DHL,\n'
     '     tooltip = "Merge Nearby の価格差 (Cluster Distance とは別)。0 = 完全に同じ価格だけ。初期 0.00020 = 2 pips (検証開始値)。")\n'),
    ("input",
     'clusterDist = input.float(0.08, "[暫定] Cluster Distance (円)", minval = 0.0, step = 0.005, group = G_CLU,\n'
     '     tooltip = "GBPJPY 比較候補 (検証用・適正値ではない): 0.08 / 0.12 / 0.16 円。初期 0.08 = ドル円検証値。")\n',
     'clusterDist = input.float(0.00030, "[検証開始値] Cluster Distance (USD)", minval = 0.0, step = 0.00005, group = G_CLU,\n'
     '     tooltip = "EURUSD: 初期 0.00030 = 3 pips (日次ボラ比較からの検証開始値、最適値ではない)。")\n'),
    ("input",
     'breakBuffer = input.float(0.08,  "[暫定] Break Buffer (円)",         minval = 0.0, step = 0.005, group = G_BF)\n'
     'flipConfirmDist = input.float(0.15, "[暫定] Flip Confirm Distance (円)", minval = 0.0, step = 0.01, group = G_BF)\n',
     'breakBuffer = input.float(0.00030,  "[検証開始値] Break Buffer (USD・初期 3 pips)",         minval = 0.0, step = 0.00005, group = G_BF)\n'
     'flipConfirmDist = input.float(0.00060, "[検証開始値] Flip Confirm Distance (USD・初期 6 pips)", minval = 0.0, step = 0.0001, group = G_BF)\n'),
    ("input",
     'fvgMinWidth = input.float(0.05, "[暫定] FVG Min Width (円)", minval = 0.0, step = 0.005, group = "02 · FVG (GBPJPY)",\n'
     '     tooltip = "15M / 1H / 4H FVG の最小幅 (mintick 正規化後に以上)。XAUUSD は固定 3.0 ドル。\\n" +\n'
     '     "GBPJPY 比較候補 (検証用・適正値ではない): 0.05 / 0.08 / 0.10 円。初期 0.05 = ドル円検証値。")\n'
     'fvgDirMatch = input.bool(false, "FVG Direction Match", group = "02 · FVG (GBPJPY)",\n',
     'fvgMinWidth = input.float(0.00020, "[検証開始値] FVG Min Width (USD)", minval = 0.0, step = 0.00005, group = "02 · FVG (EURUSD)",\n'
     '     tooltip = "15M / 1H / 4H FVG の最小幅 (mintick 正規化後に以上)。\\n" +\n'
     '     "EURUSD: 初期 0.00020 = 2 pips (日次ボラ比較からの検証開始値、最適値ではない)。")\n'
     'fvgDirMatch = input.bool(false, "FVG Direction Match", group = "02 · FVG (EURUSD)",\n'),
    # ---- Round Number ------------------------------------------------------------------------------------------------
    ("rn",
     "// ---- 2.7c Round Number (GBPJPY) ------------------------------------------\n"
     "//  Engine (ZoneEnginePractical/6) の既存 Round Number 加点を円の刻みで使う (Engine は変更しない)。\n"
     "//  判定式 (Engine f_rnLevelIn): ceil(bottom / 刻み) <= floor(top / 刻み) なら Cluster の最終範囲 [bottom, top]\n",
     "// ---- 2.7c Round Number (EURUSD) ------------------------------------------\n"
     "//  Engine (ZoneEnginePracticalEURUSD) の Round Number 加点を USD の刻みで使う。\n"
     "//  判定式 (EURUSD Engine f_rnLevelIn、最小価格刻みの整数で比較): 節目の tick 数が [ceil(bottom), floor(top)] に入れば Cluster の最終範囲 [bottom, top]\n"),
    ("rn",
     "//  ticker が GBPJPY のときだけ有効。刻みは 0.125 円の倍数 (2 進で正確に表せる値) に限る: 判定式は浮動小数の\n"
     "//  割り算なので、0.1 / 0.2 円などは境界ちょうどの価格で誤判定し得る (tests/gbx_sim で確認)。不正な刻みは停止して表示。\n"
     'var string G_RN = "02 · Round Number (GBPJPY)"\n'
     'enableRn = input.bool(false, "Enable Round Number (GBPJPY)", group = G_RN,\n',
     "//  ticker が EURUSD のときだけ有効。刻みは最小価格刻みの整数倍 (tick 整数で比較するので 0.0100 / 0.0050 も境界で漏れない。\n"
     "//  tests/eu_sim で確認)。不正な刻みは停止して表示。\n"
     'var string G_RN = "02 · Round Number (EURUSD)"\n'
     'enableRn = input.bool(false, "Enable Round Number (EURUSD)", group = G_RN,\n'),
    ("rn",
     'rnMajorStep = input.float(1.0, "[暫定] RN 大刻み (円)", minval = 0.125, step = 0.125, group = G_RN,\n'
     '     tooltip = "例: 1.00 円 → 210.000。0.125 円の倍数、かつ小刻みの整数倍 (2 倍以上)。")\n',
     'rnMajorStep = input.float(0.0100, "[暫定] RN 大刻み (USD)", minval = 0.0001, step = 0.0010, group = G_RN,\n'
     '     tooltip = "例: 0.0100 (100 pips) → 1.1000。最小価格刻みの整数倍、かつ小刻みの整数倍 (2 倍以上)。")\n'),
    ("rn",
     'rnMinorStep = input.float(0.5, "[暫定] RN 小刻み (円)", minval = 0.125, step = 0.125, group = G_RN,\n'
     '     tooltip = "例: 0.50 円 → 210.500。0.125 円の倍数。")\n',
     'rnMinorStep = input.float(0.0050, "[暫定] RN 小刻み (USD)", minval = 0.0001, step = 0.0005, group = G_RN,\n'
     '     tooltip = "例: 0.0050 (50 pips) → 1.1050。最小価格刻みの整数倍。")\n'),
    ("rn",
     "// 刻みの検証 (価格の算術だけ)。RN ON で不正なら runtime.error で明示する (OFF のときは何もしない)\n"
     "float rnRatio  = rnMinorStep > 0 ? rnMajorStep / rnMinorStep : 0.0\n"
     "float rnMajT   = rnMajorStep / syminfo.mintick\n"
     "float rnMinT   = rnMinorStep / syminfo.mintick\n"
     "bool  rnStepOK = rnMinorStep > 0 and rnMajorStep > rnMinorStep and math.abs(rnRatio - math.round(rnRatio)) < 1e-9\n"
     "     and math.abs(rnMajT - math.round(rnMajT)) < 1e-6 and math.abs(rnMinT - math.round(rnMinT)) < 1e-6\n"
     "     and rnMajorStep * 8 == math.round(rnMajorStep * 8) and rnMinorStep * 8 == math.round(rnMinorStep * 8)\n"
     "if enableRn and not rnStepOK\n"
     '    runtime.error("Round Number: 刻みが不正です (小刻み > 0、大刻み = 小刻みの 2 倍以上の整数倍、どちらも最小価格刻みと 0.125 円の倍数)")\n',
     "// 刻みの検証 (最小価格刻みの整数で比べる)。RN ON で不正なら runtime.error で明示する (OFF のときは何もしない)\n"
     "//  小刻み > 0、大刻み = 小刻みの 2 倍以上の整数倍、どちらも最小価格刻みの整数倍 (1e-6 tick は計算誤差の吸収だけ)\n"
     "float rnMajT   = rnMajorStep / syminfo.mintick\n"
     "float rnMinT   = rnMinorStep / syminfo.mintick\n"
     "int   rnMajI   = math.round(rnMajT)\n"
     "int   rnMinI   = math.round(rnMinT)\n"
     "bool  rnStepOK = rnMinorStep > 0 and math.abs(rnMajT - rnMajI) < 1e-6 and math.abs(rnMinT - rnMinI) < 1e-6\n"
     "     and rnMinI > 0 and rnMajI >= 2 * rnMinI and rnMajI % math.max(rnMinI, 1) == 0\n"
     "if enableRn and not rnStepOK\n"
     '    runtime.error("Round Number: 刻みが不正です (小刻み > 0、大刻み = 小刻みの 2 倍以上の整数倍、どちらも最小価格刻みの整数倍)")\n'),
    ("rn",
     'zoneCfg.useRnSource          := enableRn and rnStepOK and syminfo.ticker == "GBPJPY"\n',
     'zoneCfg.useRnSource          := enableRn and rnStepOK and syminfo.ticker == "EURUSD"\n'),
]

# ---- Visual -------------------------------------------------------------------------------------------------------------
VISUAL_EDITS = [
    ("header",
     "//  Zone Visual GBPJPY (Compare)  —  OANDA:GBPJPY 5分足用 Zone 比較 Indicator (Entry / Alert なし)\n",
     "//  Zone Visual EURUSD (Compare)  —  OANDA:EURUSD 5分足用 Zone 比較 Indicator (Entry / Alert なし)\n"
     "//  EU-1: ZONE-GBPJPY (ZoneVisualGBPJPY) からの移植 (生成: tests/eu_build.py、差分は fixture eu_sim が固定)。\n"
     "//  Engine は EURUSD 専用 Library ZoneEnginePracticalEURUSD (/3 と同じ処理 + RN 包含判定を最小価格刻みの整数で比較)。\n"
     "//  価格差の入力は USD (1 pip = 0.0001)。初期値は日次ボラの比較から決めた検証開始値 (5分足 ATR で検証した値・\n"
     "//  最適値ではない): Half Width 2 / Cluster 3 / FVG Min Width 2 / Break Buffer 3 / Touch Re-arm 6 / Flip Confirm 6 /\n"
     "//  Day/Swing Merge 2 / MA Cluster 12 / Slope 0.4・0.8 pips。点数・比率・日数・本数・時間足は ZONE-GBPJPY と同じ。\n"
     "//  Round Number (初期 OFF): ticker EURUSD のとき大刻み 0.0100 +3 / 小刻み 0.0050 +2。\n"
     "//  以下は ZONE-GBPJPY の説明 (円・pips の数値は GBPJPY 版のもの):\n"),
    ("name",
     '     title            = "Zone Visual GBPJPY (Compare)",\n     shorttitle       = "ZONE-GBPJPY",\n',
     '     title            = "Zone Visual EURUSD (Compare)",\n     shorttitle       = "ZONE-EURUSD",\n'),
    ("name", IMPORT_GBE, IMPORT_EU),
    ("display",
     '// Zone の上下限と最終的な幅 (円、小数 3 桁 = OANDA:GBPJPY の最小刻み 0.001。pips ではない)\n'
     'f_jpyGeom(zn.Zone z) =>\n'
     '    f_num(z.top, "#.000") + " - " + f_num(z.bottom, "#.000") + " | W " + f_num(z.top - z.bottom, "0.000") + "円"\n',
     '// Zone の上下限 (format.mintick の桁) と最終的な幅 (pips、1 pip = 0.0001)\n'
     'f_usdGeom(zn.Zone z) =>\n'
     '    f_num(z.top, format.mintick) + " - " + f_num(z.bottom, format.mintick) + " | W " + f_num((z.top - z.bottom) / 0.0001, "0.0") + " pips"\n'),
    ("display",
     '        txt := txt + "\\n" + f_jpyGeom(z)\n'
     '    if showDetailLbl\n'
     '        txt := txt + "\\n" + zn.sourceText(z.srcMask, zoneCfg)\n'
     '    txt\n'
     '\n'
     '// ==== FVG Batch C (begin)',
     '        txt := txt + "\\n" + f_usdGeom(z)\n'
     '    if showDetailLbl\n'
     '        txt := txt + "\\n" + zn.sourceText(z.srcMask, zoneCfg)\n'
     '    txt\n'
     '\n'
     '// ==== FVG Batch C (begin)'),
    ("display",
     '        txt := txt + "\\n" + f_jpyGeom(z)\n'
     '    if showDetailLbl\n'
     '        txt := txt + "\\n" + zn.sourceText(z.srcMask, zoneCfg)\n'
     '    txt\n'
     '// ==== FVG Batch C (end)',
     '        txt := txt + "\\n" + f_usdGeom(z)\n'
     '    if showDetailLbl\n'
     '        txt := txt + "\\n" + zn.sourceText(z.srcMask, zoneCfg)\n'
     '    txt\n'
     '// ==== FVG Batch C (end)'),
    ("display",
     'showGeom   = input.bool(true,  "Label: Zone 上下限 / 幅 (円) を表示", group = G_LBL)\n',
     'showGeom   = input.bool(true,  "Label: Zone 上下限 / 幅 (pips) を表示", group = G_LBL)\n'),
] + ZONE_EDITS

# ---- Strategy -----------------------------------------------------------------------------------------------------------
STRATEGY_EDITS = [
    ("header",
     "//  Zone Strategy GBPJPY  —  ZONE-GBPJPY (ZoneVisualGBPJPY) の Zone 判定をそのまま使う OANDA:GBPJPY 5分足 Strategy\n",
     "//  Zone Strategy EURUSD  —  ZONE-EURUSD (ZoneVisualEURUSD) の Zone 判定を使う OANDA:EURUSD 5分足 Strategy\n"
     "//  EU-1: ZONE-ST-GBPJPY (ZoneStrategyGBPJPY) からの移植 (生成: tests/eu_build.py、差分は fixture eu_sim が固定)。\n"
     "//  Entry A / B / C / D・1分足 BOS・取消・優先順位・再 Entry 制御・注文処理順・TP / 建値のタイミング・仮 / 確定\n"
     "//  アラート・ラベルは ZONE-ST-GBPJPY と同じ式。Zone 関連の入力と初期値は ZONE-EURUSD と同じ。価格差は USD\n"
     "//  (1 pip = 0.0001)。SL Buffer 0.00030 (3 pips、Zone 反対端からの追加幅) / Breakeven Trigger 0.00060 (6 pips) は\n"
     "//  日次ボラ比較からの検証開始値。数量は円の損失予算を strategy.convert_to_symbol で USD に換算してから計算する\n"
     "//  (固定 USDJPY なし)。次足成行・ギャップ・スリッページがあるため、実損失が必ず予算内とは限らない。\n"
     "//  以下は ZONE-ST-GBPJPY の説明 (円・pips の数値は GBPJPY 版のもの):\n"
     "//  Zone Strategy GBPJPY  —  ZONE-GBPJPY (ZoneVisualGBPJPY) の Zone 判定をそのまま使う OANDA:GBPJPY 5分足 Strategy\n"),
    ("name",
     '     title                  = "Zone Strategy GBPJPY",\n     shorttitle             = "ZONE-ST-GBPJPY",\n',
     '     title                  = "Zone Strategy EURUSD",\n     shorttitle             = "ZONE-ST-EURUSD",\n'),
    ("name", IMPORT_GBE, IMPORT_EU),
] + ZONE_EDITS + [
    ("input",
     'stBuffer = input.float(0.08, "[暫定] SL Buffer (円)", minval = 0.0, step = 0.005, group = G_ST)\n',
     'stBuffer = input.float(0.00030, "[検証開始値] SL Buffer (USD)", minval = 0.0, step = 0.00005, group = G_ST,\n'
     '     tooltip = "SL = Zone の反対端 ∓ この値 (Zone 反対端からの追加幅。Entry からの SL 距離を固定するものではない)。\\n" +\n'
     '     "初期 0.00030 = 3 pips (日次ボラ比較からの検証開始値)。")\n'),
    ("input",
     'stBEDist = input.float(0.15, "[暫定] Breakeven Trigger (円)", minval = 0.0, step = 0.005, group = G_STT)\n',
     'stBEDist = input.float(0.00060, "[検証開始値] Breakeven Trigger (USD)", minval = 0.0, step = 0.00005, group = G_STT,\n'
     '     tooltip = "Breakeven Stop が ON のときの発動距離。初期 0.00060 = 6 pips (検証開始値)。")\n'),
    ("size",
     '// 数量 (通貨数、GBP): 参照価格 ref と固定 SL の距離から、損失予算を超えない最大の lot 刻みの倍数。\n'
     '//  損失 (円) = qty × 距離 × syminfo.pointvalue (OANDA:GBPJPY は 1)。無効 / 最小 lot 未満は na (発注しない)\n'
     'f_stQty(int side, float ref, float sl) =>\n'
     '    float dist  = side == 1 ? ref - sl : sl - ref\n'
     '    float stepU = stLotUnits * stLotStep\n'
     '    float q     = na\n'
     '    if not na(dist) and dist > 0 and syminfo.pointvalue > 0 and stepU > 0 and stBudget > 0\n'
     '        float n = math.floor(stBudget / (dist * syminfo.pointvalue * stepU) + 1e-9)     // 1e-9: 浮動小数の誤差だけ吸収 (切り上げない)\n',
     '// 数量 (通貨数、EUR): 参照価格 ref と固定 SL の距離から、損失予算を超えない最大の lot 刻みの倍数。\n'
     '//  損失 (USD) = qty × 距離 × syminfo.pointvalue。円の損失予算は strategy.convert_to_symbol でチャートの通貨 (USD) へ\n'
     '//  換算してから割る (固定 USDJPY なし、request 追加なし)。換算 na / 無効な距離 / 最小 lot 未満は na (発注しない)。\n'
     '//  発注時点の想定 SL 損失の制御であり、次足成行・ギャップ・スリッページを含む実損失の上限ではない。\n'
     'f_stQty(int side, float ref, float sl) =>\n'
     '    float dist   = side == 1 ? ref - sl : sl - ref\n'
     '    float stepU  = stLotUnits * stLotStep\n'
     '    float budSym = stBudget > 0 ? strategy.convert_to_symbol(stBudget) : na     // 損失予算 (USD)\n'
     '    float q      = na\n'
     '    if not na(dist) and dist > 0 and syminfo.pointvalue > 0 and stepU > 0 and not na(budSym) and budSym > 0\n'
     '        float n = math.floor(budSym / (dist * syminfo.pointvalue * stepU) + 1e-9)     // 1e-9: 浮動小数の誤差だけ吸収 (切り上げない)\n'),
    ("alert",
     "//  GBPJPY: 0.01 円 = 1 pip。Entry / SL / TP は最小価格刻みの桁。TP は発注前の RR 判定 (f_stTp) と同じ結果を受け取る\n"
     "//  (通知用の値。実際の TP 注文は約定確認後に実約定価格から決める)。risk <= 0 / TP na の数値は \"-\"\n"
     "float ST_PIP = 0.01\n",
     "//  EURUSD: 0.0001 = 1 pip。Entry / SL / TP は最小価格刻みの桁。TP は発注前の RR 判定 (f_stTp) と同じ結果を受け取る\n"
     "//  (通知用の値。実際の TP 注文は約定確認後に実約定価格から決める)。risk <= 0 / TP na の数値は \"-\"\n"
     "float ST_PIP = 0.0001\n"),
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


def build_engine():
    return _apply(_rd(ENG_SRC), ENGINE_EDITS)


def build_visual():
    return _apply(_rd(VIS_SRC), VISUAL_EDITS)


def build_strategy():
    return _apply(_rd(STR_SRC), STRATEGY_EDITS)


def strip_engine(t):
    return _revert(t, ENGINE_EDITS)


def strip_visual(t):
    return _revert(t, VISUAL_EDITS)


def strip_strategy(t):
    return _revert(t, STRATEGY_EDITS)


if __name__ == "__main__":
    for path, fn in ((ENG_PATH, build_engine), (VIS_PATH, build_visual), (STR_PATH, build_strategy)):
        open(os.path.join(ROOT, path), "w", encoding="utf-8").write(fn())
        print("written", path)
