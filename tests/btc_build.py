"""BTC-1 — ZoneVisualBTCUSD.pine: BINANCE:BTCUSD 5M Zone display indicator (no entries, no alerts).

Deterministic transform of ZoneVisualGBPJPY.pine (ZONE-GBPJPY) by exact, unique text replacements (EDITS);
strip_btc() applies them in reverse and must give ZONE-GBPJPY back byte for byte (fixture btc_sim), so the Engine
import (ZoneEnginePracticalGBPJPY/3, symbol independent), Zone generation / scoring, FVG, update order, requests,
5M gate and non-repaint blocks are provably ZONE-GBPJPY's.
Only these kinds of change are allowed (each EDIT is tagged and btc_sim checks the code lines it touches):
  header    comment header / comments
  title     indicator title / shorttitle
  input     price-difference input default / label / minval / step / tooltip / group text (USD)
  rn        Round Number symbol gate (ticker BTCUSD) and its error text
  display   Zone top / bottom / width text (format.mintick, USD)
Price-difference defaults are unverified starting values for display checks (not adopted / optimised values, not a
scaled copy of the GBPJPY values). Dimensionless inputs (scores, ATR multiples, lengths, bars) are not changed.
ZONE-GBPJPY, the other Visuals / Strategies and the Engines are not modified.
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_PATH = "ZoneVisualGBPJPY.pine"
BTC_PATH = "ZoneVisualBTCUSD.pine"

EDITS = [
    # ---- header / identity ---------------------------------------------------------------------------------------
    ("header",
     "//  Zone Visual GBPJPY (Compare)  —  OANDA:GBPJPY 5分足用 Zone 比較 Indicator (Entry / Alert なし)\n"
     "//  ZONE-JPY (ZoneVisualUSDJPY) と同じ Engine /6・Zone 生成・採点式・FVG・更新順・非リペイント条件で、\n"
     "//  表示名と円建て入力の初期値 / 説明だけを変えた比較版 (生成: tests/gbj_build.py、ZONE-JPY との差分は\n"
     "//  fixture gbj_sim が固定)。価格差の入力はすべて円 (1 pip = 0.01 円、0.05 円 = 5 pips)。\n"
     "//  初期値はすべて暫定: Half Width 0.03 / Cluster Distance 0.08 / FVG Min Width 0.05 円 (ドル円検証値)、\n"
     "//  他の円建て閾値は ZONE-JPY と同じ値。比較候補 Half Width 0.03 / 0.05 / 0.08、Cluster 0.08 / 0.12 / 0.16、\n"
     "//  FVG Min Width 0.05 / 0.08 / 0.10 円 (検証候補であり適正値ではない)。\n"
     "//  GBJ-2 (比較用、どちらも初期 OFF = 従来と同じ結果): FVG Direction Match (SUPPORT は上昇 FVG、RESIST は下降 FVG\n"
     "//  だけを加点候補にする) と GBPJPY Round Number (大刻み 1.00 円 +3 / 小刻み 0.50 円 +2、Engine の既存 RN 加点)。\n"
     "//  GBJ-3 (GBPJPY 基準設定、初期値だけ): Half Width 0.05 円 (Strategy と共通)、Day H/L Score 2、Slope Threshold\n"
     "//  Moderate 0.01 / Strong 0.02 円、Strong Threshold 9。ある比較期間の TradingView 結果から決めた値 (最適値・別期間は未確認)。\n"
     "//  GBJ-4: Accum Score Mode (Sum = 従来 / Max)。Engine は GBPJPY 派生 ZoneEnginePracticalGBPJPY (/6 + Accum 時間足間\n"
     "//  の合算方式だけ、生成: tests/gbe_build.py)。TradingView で Library を publish してから使う。\n"
     "//  GBJ-5: Accum Edge Mode (Separate = 従来 / Once per TF = 同じ時間足の上限・下限を合わせて 1 回)。Library v2 が必要。\n"
     "//  GBJ-7: Day/Swing Overlap Mode (Separate = 従来 / Merge Nearby = 価格が近い Day H/L と Swing を 1 つの根拠に)。Library v3。\n"
     "//  GBJ-8: 採用設定の初期値 Accum Score Mode = Max (Edge Mode Separate / Day/Swing Separate / Merge Distance 0.05 円は維持)。\n",
     "//  Zone Visual BTCUSD (Compare)  —  BINANCE:BTCUSD 5分足用 Zone 表示 Indicator (Entry / Alert なし)\n"
     "//  ZONE-GBPJPY (ZoneVisualGBPJPY) と同じ Engine (ZoneEnginePracticalGBPJPY/3、処理は銘柄非依存)・Zone 生成・採点式・\n"
     "//  FVG・更新順・5分足 Gate・非リペイント条件で、表示名・価格差入力 (USD)・Round Number の銘柄判定・Zone 上下限 / 幅の\n"
     "//  表示書式だけを変えた派生版 (生成: tests/btc_build.py、ZONE-GBPJPY との差分は fixture btc_sim が固定)。\n"
     "//  価格と価格差の単位はすべて USD。点数・ATR 倍率・期間・本数などの無次元入力は ZONE-GBPJPY と同じ。\n"
     "//  価格差の初期値はすべて表示確認用の未検証値 (BTC の適正値・採用値・最適化結果ではない。GBPJPY 値の換算でもない):\n"
     "//  Half Width 50 / Cluster Distance 100 / FVG Min Width 50 / Slope Moderate 10・Strong 30 (/lookback) /\n"
     "//  MA Cluster Distance 300 / Touch Re-arm 150 / Day/Swing Merge 50 / Break Buffer 50 / Flip Confirm 150 USD。\n"
     "//  比較候補 (手動で入力を変えて比較): Half Width 25 / 50 / 100、Cluster Distance 50 / 100 / 150、FVG Min Width 25 / 50 / 100 USD。\n"
     "//  採点の初期値は ZONE-GBPJPY と同じ: Accum Score Mode Max / Accum Edge Mode Separate / Day/Swing Separate、\n"
     "//  Day H/L Score 2、Strong 9 / Medium 5 / Very Strong 15、Day Session Asia/Tokyo・Reset 5 時 (土日も通常どおり処理)。\n"
     "//  Round Number (初期 OFF): ticker BTCUSD のときだけ大刻み 1,000 USD +3 / 小刻み 500 USD +2 (Engine の既存 RN 加点)。\n"),
    ("title",
     '     title            = "Zone Visual GBPJPY (Compare)",\n     shorttitle       = "ZONE-GBPJPY",\n',
     '     title            = "Zone Visual BTCUSD (Compare)",\n     shorttitle       = "ZONE-BTCUSD",\n'),
    # ---- display: Zone top / bottom / width in USD ---------------------------------------------------------------
    ("display",
     '// Zone の上下限と最終的な幅 (円、小数 3 桁 = OANDA:GBPJPY の最小刻み 0.001。pips ではない)\n'
     'f_jpyGeom(zn.Zone z) =>\n'
     '    f_num(z.top, "#.000") + " - " + f_num(z.bottom, "#.000") + " | W " + f_num(z.top - z.bottom, "0.000") + "円"\n',
     '// Zone の上下限と最終的な幅 (USD。桁数は銘柄の最小価格刻み format.mintick に従う)\n'
     'f_usdGeom(zn.Zone z) =>\n'
     '    f_num(z.top, format.mintick) + " - " + f_num(z.bottom, format.mintick) + "\\nW " + f_num(z.top - z.bottom, format.mintick) + " USD"\n'),
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
     'showGeom   = input.bool(true,  "Label: Zone 上下限 / 幅 (USD) を表示", group = G_LBL)\n'),
    # ---- price-difference inputs (USD, all [未検証]) ------------------------------------------------------------
    ("input",
     'zoneHalfWidth = input.float(0.05, "[暫定] Zone Half Width (円)", minval = 0.005, step = 0.005, group = G_ZONE,\n',
     'zoneHalfWidth = input.float(50.0, "[未検証] Zone Half Width (USD)", minval = 1.0, step = 5.0, group = G_ZONE,\n'),
    ("input",
     '     "GBPJPY 比較候補 (検証用・適正値ではない): 0.03 / 0.05 / 0.08 円 (= 3 / 5 / 8 pips)。初期 0.05 = GBPJPY 基準設定 (Visual / Strategy 共通)。")\n',
     '     "Half Width の BTCUSD 比較候補 (表示確認用・適正値ではない): 25 / 50 / 100 USD。初期 50 USD は未検証の開始値。")\n'),
    ("input",
     'slopeThrMod = input.float(0.01, "[暫定] Slope Threshold · Moderate (円/lookback)", minval = 0.0, step = 0.005, group = G_SLOPE)\n'
     'slopeThrStrong = input.float(0.02, "[暫定] Slope Threshold · Strong (円/lookback)",   minval = 0.0, step = 0.005, group = G_SLOPE)\n',
     'slopeThrMod = input.float(10.0, "[未検証] Slope Threshold · Moderate (USD/lookback)", minval = 0.0, step = 1.0, group = G_SLOPE)\n'
     'slopeThrStrong = input.float(30.0, "[未検証] Slope Threshold · Strong (USD/lookback)",   minval = 0.0, step = 1.0, group = G_SLOPE)\n'),
    ("input",
     'maClusterDist = input.float(0.30, "[暫定] MA Cluster Distance (円)", minval = 0.0, step = 0.01, group = G_SLOPE)\n',
     'maClusterDist = input.float(300.0, "[未検証] MA Cluster Distance (USD)", minval = 0.0, step = 10.0, group = G_SLOPE)\n'),
    ("input",
     'touchRearmDist = input.float(0.15, "[暫定] Touch Re-arm Distance (円)", minval = 0.0, step = 0.01, group = G_TOUCH,\n',
     'touchRearmDist = input.float(150.0, "[未検証] Touch Re-arm Distance (USD)", minval = 0.0, step = 10.0, group = G_TOUCH,\n'),
    ("input",
     'dsDist = input.float(0.05, "[暫定] Day/Swing Merge Distance (円)", minval = 0.0, step = 0.001, group = G_DHL,\n'
     '     tooltip = "Merge Nearby の価格差 (Cluster Distance とは別)。0 = 完全に同じ価格だけ。0.05 円は比較開始用の暫定値。")\n',
     'dsDist = input.float(50.0, "[未検証] Day/Swing Merge Distance (USD)", minval = 0.0, step = 1.0, group = G_DHL,\n'
     '     tooltip = "Merge Nearby の価格差 (Cluster Distance とは別)。0 = 完全に同じ価格だけ。50 USD は未検証の開始値。")\n'),
    ("input",
     'clusterDist = input.float(0.08, "[暫定] Cluster Distance (円)", minval = 0.0, step = 0.005, group = G_CLU,\n'
     '     tooltip = "GBPJPY 比較候補 (検証用・適正値ではない): 0.08 / 0.12 / 0.16 円。初期 0.08 = ドル円検証値。")\n',
     'clusterDist = input.float(100.0, "[未検証] Cluster Distance (USD)", minval = 0.0, step = 5.0, group = G_CLU,\n'
     '     tooltip = "BTCUSD 比較候補 (表示確認用・適正値ではない): 50 / 100 / 150 USD。初期 100 USD は未検証の開始値。")\n'),
    ("input",
     'breakBuffer = input.float(0.08,  "[暫定] Break Buffer (円)",         minval = 0.0, step = 0.005, group = G_BF)\n'
     'flipConfirmDist = input.float(0.15, "[暫定] Flip Confirm Distance (円)", minval = 0.0, step = 0.01, group = G_BF)\n',
     'breakBuffer = input.float(50.0,  "[未検証] Break Buffer (USD)",         minval = 0.0, step = 5.0, group = G_BF)\n'
     'flipConfirmDist = input.float(150.0, "[未検証] Flip Confirm Distance (USD)", minval = 0.0, step = 10.0, group = G_BF)\n'),
    ("input",
     'fvgMinWidth = input.float(0.05, "[暫定] FVG Min Width (円)", minval = 0.0, step = 0.005, group = "02 · FVG (GBPJPY)",\n'
     '     tooltip = "15M / 1H / 4H FVG の最小幅 (mintick 正規化後に以上)。XAUUSD は固定 3.0 ドル。\\n" +\n'
     '     "GBPJPY 比較候補 (検証用・適正値ではない): 0.05 / 0.08 / 0.10 円。初期 0.05 = ドル円検証値。")\n'
     'fvgDirMatch = input.bool(false, "FVG Direction Match", group = "02 · FVG (GBPJPY)",\n',
     'fvgMinWidth = input.float(50.0, "[未検証] FVG Min Width (USD)", minval = 0.0, step = 5.0, group = "02 · FVG (BTCUSD)",\n'
     '     tooltip = "15M / 1H / 4H FVG の最小幅 (mintick 正規化後に以上)。\\n" +\n'
     '     "BTCUSD 比較候補 (表示確認用・適正値ではない): 25 / 50 / 100 USD。初期 50 USD は未検証の開始値。")\n'
     'fvgDirMatch = input.bool(false, "FVG Direction Match", group = "02 · FVG (BTCUSD)",\n'),
    # ---- Round Number: USD steps, BTCUSD symbol gate ---------------------------------------------------------------
    ("rn",
     "// ---- 2.7c Round Number (GBPJPY) ------------------------------------------\n"
     "//  Engine (ZoneEnginePractical/6) の既存 Round Number 加点を円の刻みで使う (Engine は変更しない)。\n",
     "// ---- 2.7c Round Number (BTCUSD) ------------------------------------------\n"
     "//  Engine (ZoneEnginePracticalGBPJPY/3) の既存 Round Number 加点を USD の刻みで使う (Engine は変更しない)。\n"),
    ("rn",
     "//  ticker が GBPJPY のときだけ有効。刻みは 0.125 円の倍数 (2 進で正確に表せる値) に限る: 判定式は浮動小数の\n"
     "//  割り算なので、0.1 / 0.2 円などは境界ちょうどの価格で誤判定し得る (tests/gbx_sim で確認)。不正な刻みは停止して表示。\n"
     'var string G_RN = "02 · Round Number (GBPJPY)"\n'
     'enableRn = input.bool(false, "Enable Round Number (GBPJPY)", group = G_RN,\n',
     "//  ticker が BTCUSD (BTC / USD) のときだけ有効 (BTCJPY / BTCUSDT などは別 ticker のため対象外)。銘柄が違っても\n"
     "//  停止はせず RN を加点しないだけ。刻みは 0.125 USD の倍数 (2 進で正確に表せる値) に限る: 判定式は浮動小数の\n"
     "//  割り算なので、境界ちょうどの価格で誤判定しない刻みだけを許す (1,000 / 500 USD は整数で該当。tests/btc_sim で確認)。\n"
     'var string G_RN = "02 · Round Number (BTCUSD)"\n'
     'enableRn = input.bool(false, "Enable Round Number (BTCUSD)", group = G_RN,\n'),
    ("rn",
     'rnMajorStep = input.float(1.0, "[暫定] RN 大刻み (円)", minval = 0.125, step = 0.125, group = G_RN,\n'
     '     tooltip = "例: 1.00 円 → 210.000。0.125 円の倍数、かつ小刻みの整数倍 (2 倍以上)。")\n',
     'rnMajorStep = input.float(1000.0, "[未検証] RN 大刻み (USD)", minval = 1.0, step = 100.0, group = G_RN,\n'
     '     tooltip = "例: 1,000 USD → 65000。最小価格刻みと 0.125 USD の倍数、かつ小刻みの整数倍 (2 倍以上)。")\n'),
    ("rn",
     'rnMinorStep = input.float(0.5, "[暫定] RN 小刻み (円)", minval = 0.125, step = 0.125, group = G_RN,\n'
     '     tooltip = "例: 0.50 円 → 210.500。0.125 円の倍数。")\n',
     'rnMinorStep = input.float(500.0, "[未検証] RN 小刻み (USD)", minval = 1.0, step = 50.0, group = G_RN,\n'
     '     tooltip = "例: 500 USD → 65500。最小価格刻みと 0.125 USD の倍数。")\n'),
    ("rn",
     '    runtime.error("Round Number: 刻みが不正です (小刻み > 0、大刻み = 小刻みの 2 倍以上の整数倍、どちらも最小価格刻みと 0.125 円の倍数)")\n',
     '    runtime.error("Round Number: 刻みが不正です (小刻み > 0、大刻み = 小刻みの 2 倍以上の整数倍、どちらも最小価格刻みと 0.125 USD の倍数)")\n'),
    ("rn",
     'zoneCfg.useRnSource          := enableRn and rnStepOK and syminfo.ticker == "GBPJPY"\n',
     'zoneCfg.useRnSource          := enableRn and rnStepOK and syminfo.ticker == "BTCUSD"\n'),
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


def btc_transform(src):
    return _apply(src, EDITS)


def strip_btc(btc):
    """reverse every BTC-1 edit (-> ZoneVisualGBPJPY.pine byte for byte)."""
    return _revert(btc, EDITS)


def build():
    return btc_transform(open(os.path.join(ROOT, SRC_PATH), encoding="utf-8").read())


if __name__ == "__main__":
    open(os.path.join(ROOT, BTC_PATH), "w", encoding="utf-8").write(build())
    print("written", BTC_PATH)
