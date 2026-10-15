"""BTS-1 — ZoneStrategyBTCUSD.pine: CRYPTO:BTCUSD 5M Strategy with provisional / confirmed alerts and labels.

Deterministic transform of ZoneStrategyGBPJPY.pine (ZONE-ST-GBPJPY) by exact, unique text replacements (EDITS);
strip_bts() applies them in reverse and must give ZONE-ST-GBPJPY back byte for byte (fixture btcs_sim), so the Entry
modes A / B / C / D, the 1M BOS processing, cancellation, priorities, re-entry control, order sequence, provisional /
confirmed alert gating and the labels are provably ZONE-ST-GBPJPY's.
  zone      the Zone input / RN edits of the BTC Visual (btc_build.EDITS kinds input / rn, the same objects), so every
            Zone-related input and the RN gate equal ZoneVisualBTCUSD.pine (f9d9440); the Engine update is already
            confirmed-only in ZONE-ST-GBPJPY (same timing as the BTC Visual's BTC-2)
  header    comment header / comments
  title     strategy title / shorttitle
  entry     SL Buffer 50 USD / Breakeven Trigger 150 USD (unverified starting values)
  size      position size: JPY loss budget converted to the chart currency with strategy.convert_to_symbol (no request),
            loss per unit = SL distance x syminfo.pointvalue, quantity step / minimum inputs (0.01 = unverified assumption,
            not the broker's lot spec), floor, re-check loss <= budget, invalid -> no order
  alert     SL distance shown as a USD price difference (format.mintick) instead of pips
ZONE-ST-GBPJPY, the BTC Visual, the other Visuals / Strategies and the Engines are not modified.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import btc_build as bb  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_PATH = "ZoneStrategyGBPJPY.pine"
BTS_PATH = "ZoneStrategyBTCUSD.pine"

ZONE_EDITS = [e for e in bb.EDITS if e[0] in ("input", "rn")]

EDITS = [
    ("header",
     "//  Zone Strategy GBPJPY  —  ZONE-GBPJPY (ZoneVisualGBPJPY) の Zone 判定をそのまま使う OANDA:GBPJPY 5分足 Strategy\n"
     "//  (生成: tests/gbs_build.py。Zone 計算は ZONE-GBPJPY、注文処理・仮 / 確定アラートは ZONE-ST-JPY\n"
     "//   (ZoneStrategyUSDJPY) と同じ式。価格差は円。初期値は GBPJPY 基準設定 (ある比較期間の TradingView 結果から\n"
     "//   決めたもの。最適値・別期間での有効性は未確認)。Zone 関連の初期値 (Half Width 0.05 円を含む) は表示用\n"
     "//   ZONE-GBPJPY と同じ)\n",
     "//  Zone Strategy BTCUSD  —  ZONE-BTCUSD (ZoneVisualBTCUSD) の Zone 判定を使う CRYPTO:BTCUSD 5分足 Strategy\n"
     "//  (生成: tests/btcs_build.py。ZONE-ST-GBPJPY (ZoneStrategyGBPJPY) からの派生: Entry A / B / C / D・1分足 BOS・\n"
     "//   取消・優先順位・再 Entry 制御・注文処理順・仮 / 確定アラート・ラベルは ZONE-ST-GBPJPY と同じ式。\n"
     "//   Zone 関連の入力・初期値・RN 条件は ZONE-BTCUSD と同じ (fixture btcs_sim が固定)。価格と価格差は USD。\n"
     "//   実データはすべて syminfo.tickerid (取引所・銘柄の固定参照なし)。土日も通常どおり処理する。\n"
     "//   価格差の初期値 (SL Buffer 50 / Breakeven 150 USD、Zone 側の USD 値) はすべて未検証の検証開始値で、最適値ではない)\n"
     "//  ・数量: 損失予算 (円、単利) を strategy.convert_to_symbol でチャートの決済通貨 (USD) へ換算し、\n"
     "//    SL 距離 × syminfo.pointvalue から算出 (request の追加なし)。刻み / 最小数量 0.01 は未検証の仮定 (実口座の\n"
     "//    lot 仕様とは限らない)。発注時点の想定 SL 損失の制御であり、ギャップ・スリッページを含む実損失の上限ではない。\n"
     "//  ・通知の Entry / TP は発注時点の参照価格 (B / C / D: 確定足の終値、A: 指値) による値。B / C / D は次足始値の\n"
     "//    成行で約定するため、実約定価格と実際の TP (約定確認後に実約定価格から決める) は通知と異なる場合がある。\n"),
    ("header",
     "//  ・GBPJPY: 仮 / 確定アラート (ゴールド版 PracticalZoneStrategy_LONG.pine P10 と同じ意味)。仮アラートのため\n",
     "//  ・BTCUSD: 仮 / 確定アラート (ゴールド版 PracticalZoneStrategy_LONG.pine P10 と同じ意味)。仮アラートのため\n"),
    ("title",
     '     title                  = "Zone Strategy GBPJPY",\n     shorttitle             = "ZONE-ST-GBPJPY",\n',
     '     title                  = "Zone Strategy BTCUSD",\n     shorttitle             = "ZONE-ST-BTCUSD",\n'),
] + ZONE_EDITS + [
    ("header",
     "//  ★ GBPJPY: calc_on_every_tick = true でも Engine 更新は確定足だけ",
     "//  ★ BTCUSD: calc_on_every_tick = true でも Engine 更新は確定足だけ"),
    ("entry",
     'stBuffer = input.float(0.08, "[暫定] SL Buffer (円)", minval = 0.0, step = 0.005, group = G_ST)\n',
     'stBuffer = input.float(50.0, "[未検証] SL Buffer (USD)", minval = 0.0, step = 5.0, group = G_ST,\n'
     '     tooltip = "SL = Zone の反対端 ∓ この値。50 USD は未検証の検証開始値 (最適値ではない)。")\n'),
    ("entry",
     'stBEDist = input.float(0.15, "[暫定] Breakeven Trigger (円)", minval = 0.0, step = 0.005, group = G_STT)\n',
     'stBEDist = input.float(150.0, "[未検証] Breakeven Trigger (USD)", minval = 0.0, step = 10.0, group = G_STT,\n'
     '     tooltip = "建値移動の発動距離 (Breakeven Stop が ON のときだけ)。150 USD は未検証の検証開始値。")\n'),
    ("size",
     'stLotUnits = input.float(100000.0, "1 lot の通貨数", minval = 1.0, step = 1000.0, group = G_STQ)\n'
     'stLotStep = input.float(0.01, "最小 lot / lot 刻み", minval = 0.0001, step = 0.01, group = G_STQ,\n'
     '     tooltip = "数量はこの刻みで切り捨て。最小 lot 未満なら発注しない (切り上げない)。")\n'
     'float stBudget = stCapBase * stRiskPct / 100.0     // 損失予算 (円、固定)\n'
     '\n'
     '// 数量 (通貨数、GBP): 参照価格 ref と固定 SL の距離から、損失予算を超えない最大の lot 刻みの倍数。\n'
     '//  損失 (円) = qty × 距離 × syminfo.pointvalue (OANDA:GBPJPY は 1)。無効 / 最小 lot 未満は na (発注しない)\n'
     'f_stQty(int side, float ref, float sl) =>\n'
     '    float dist  = side == 1 ? ref - sl : sl - ref\n'
     '    float stepU = stLotUnits * stLotStep\n'
     '    float q     = na\n'
     '    if not na(dist) and dist > 0 and syminfo.pointvalue > 0 and stepU > 0 and stBudget > 0\n'
     '        float n = math.floor(stBudget / (dist * syminfo.pointvalue * stepU) + 1e-9)     // 1e-9: 浮動小数の誤差だけ吸収 (切り上げない)\n'
     '        if n >= 1\n'
     '            q := n * stepU\n'
     '    q\n',
     'stQtyStep = input.float(0.01, "[未検証] 数量刻み (BTC)", minval = 0.00000001, step = 0.01, group = G_STQ,\n'
     '     tooltip = "Strategy Tester 用の数量刻み。0.01 は未検証の仮定で、実口座の lot 仕様と同じとは限らない。数量はこの刻みで切り捨て。")\n'
     'stQtyMin = input.float(0.01, "[未検証] 最小数量 (BTC)", minval = 0.00000001, step = 0.01, group = G_STQ,\n'
     '     tooltip = "切り捨て後の数量がこれ未満なら発注しない (切り上げない)。0.01 は未検証の仮定。")\n'
     'float stBudget = stCapBase * stRiskPct / 100.0     // 損失予算 (円、固定)\n'
     '\n'
     '// 数量 (BTC): 損失予算 (円) を strategy の通貨 (JPY) からチャートの決済通貨 (syminfo.currency、CRYPTO:BTCUSD は USD) へ\n'
     '//  strategy.convert_to_symbol で換算し (request.* を使わない)、参照価格 ref と固定 SL の距離から、予算を超えない最大の\n'
     '//  刻みの倍数。想定 SL 損失 (決済通貨) = qty × 距離 × syminfo.pointvalue。算出後に想定損失 <= 予算を再確認する。\n'
     '//  換算値 / 距離 / pointvalue / 刻みが無効、または最小数量未満は na (発注しない)。発注時点の想定損失の制御であり、\n'
     '//  ギャップ・スリッページを含む実損失の上限保証ではない。\n'
     'f_stQty(int side, float ref, float sl) =>\n'
     '    float dist   = side == 1 ? ref - sl : sl - ref\n'
     '    float budSym = stBudget > 0 ? strategy.convert_to_symbol(stBudget) : na     // 損失予算 (決済通貨)\n'
     '    float q      = na\n'
     '    if not na(dist) and dist > 0 and syminfo.pointvalue > 0 and stQtyStep > 0 and not na(budSym) and budSym > 0\n'
     '        float lossU = dist * syminfo.pointvalue                                  // 数量 1 あたりの想定 SL 損失\n'
     '        float n     = math.floor(budSym / (lossU * stQtyStep) + 1e-9)            // 1e-9: 浮動小数の誤差だけ吸収\n'
     '        if n * stQtyStep * lossU > budSym                                      // 再確認: 予算超過なら 1 刻み減らす\n'
     '            n := n - 1\n'
     '        if n >= 1 and n * stQtyStep >= stQtyMin * (1 - 1e-9)\n'
     '            q := n * stQtyStep\n'
     '    q\n'),
    ("size",
     "            // 数量: 同じ参照価格 (A: 指値 / B, C, D: この確定足の終値) と固定 SL から。無効 / 最小 lot 未満は発注しない\n",
     "            // 数量: 同じ参照価格 (A: 指値 / B, C, D: この確定足の終値) と固定 SL から。無効 / 最小数量未満は発注しない\n"),
    ("alert",
     "// ---- 仮 / 確定アラート (GBPJPY) ----------------------------------------------------------------\n",
     "// ---- 仮 / 確定アラート (BTCUSD) ----------------------------------------------------------------\n"),
    ("alert",
     "//  GBPJPY: 0.01 円 = 1 pip。Entry / SL / TP は最小価格刻みの桁。TP は発注前の RR 判定 (f_stTp) と同じ結果を受け取る\n"
     "//  (通知用の値。実際の TP 注文は約定確認後に実約定価格から決める)。risk <= 0 / TP na の数値は \"-\"\n"
     "float ST_PIP = 0.01\n",
     "//  BTCUSD: Entry / SL / TP と SL 距離 (USD の価格差) は format.mintick の桁。TP は発注前の RR 判定 (f_stTp) と同じ結果を\n"
     "//  受け取る (通知用の値。実際の TP 注文は約定確認後に実約定価格から決める)。risk <= 0 / TP na の数値は \"-\"\n"),
    ("alert",
     '     "\\nSL距離：" + (okR ? str.tostring(risk / ST_PIP, "0.0") + " pips" : "-") +\n',
     '     "\\nSL距離：" + (okR ? str.tostring(risk, format.mintick) + " USD" : "-") +\n'),
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


def bts_transform(src):
    return _apply(src, EDITS)


def strip_bts(bts):
    """reverse every BTS-1 edit (-> ZoneStrategyGBPJPY.pine byte for byte)."""
    return _revert(bts, EDITS)


def build():
    return bts_transform(open(os.path.join(ROOT, SRC_PATH), encoding="utf-8").read())


if __name__ == "__main__":
    open(os.path.join(ROOT, BTS_PATH), "w", encoding="utf-8").write(build())
    print("written", BTS_PATH)
