"""UJ-1 — USDJPY dedicated Engine + GBPJPY position sizing (OANDA:USDJPY 5M).

  ZoneEnginePracticalSwingMax.pine (= the source of the published ZoneEnginePractical/6: commit 110e5b0 created it
  (SW-1) and the next commit 67f8fd2 switched the Visual import /5 -> /6 "Swing max-score, SW-1"; the file is unchanged
  since) -> ZoneEnginePracticalUSDJPY.pine: library name and header only (same computation and API).
  ZoneVisualUSDJPY.pine / ZoneStrategyUSDJPY.pine: import ZoneEnginePracticalUSDJPY/1 (to be published) instead of
  ZoneEnginePractical/6; the Visual's Zone Half Width default becomes the Strategy's 0.03 円 (user decision, so the shared
  Zone defaults match; Direction stays Long Only); the Strategy also gets the GBPJPY position sizing (gbs_build QTY_EDITS, the sizing parts only:
  initial capital 300,000 JPY in JPY, 元金基準額 300,000 円 x 3 % fixed (simple), 1 lot = 100,000, step 0.01, f_stQty =
  floor(budget / (distance x syminfo.pointvalue x lot step units)), qty on both the limit and the market entry, no order
  (and no order / Track state) when the quantity is invalid or below one step). The GBPJPY alert-text edits of GBS-4 are
  not taken (alerts / labels are out of scope).
Each strip_*() reverses its edits and must give the source back byte for byte (fixture uj_sim).
UJ-3 (Strategy only, applied after UJ-2; strip_strategy3() -> the UJ-2 Strategy of e1c3cea): display / notification only -
provisional / confirmed Entry labels ported from the GBPJPY Strategy (GBS-6) and the SL distance (pips) in both alert texts.
UJ-4 (Strategy only, applied after UJ-3; strip_strategy4() -> the UJ-3 Strategy of ab9820f): TP / RR in the provisional /
confirmed labels and alert texts, the GBPJPY method (the existing pre-order f_stTp result), display / notification only.
UJ-5 (Strategy only, applied after UJ-4; strip_strategy5() -> the UJ-4 Strategy of 89bc82b): the confirmed alert at most once
per 5M bar (varip bar key), notification only.
UJ-2 (applied after UJ-1; strip_*2() reverses only UJ-2 -> the UJ-1 files of commit a6a275c byte for byte): defaults
adopted from the user's USDJPY Long comparison (shared Zone inputs in Visual and Strategy, Strategy RR 1.5). Defaults
and the matching comments only: no logic, Engine, sizing, timing, alert or other-symbol change. Not optimal values; the
per-year check and the Short verification are not done.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gbs_build as gs  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENG_SRC, ENG_PATH = "ZoneEnginePracticalSwingMax.pine", "ZoneEnginePracticalUSDJPY.pine"
VIS_PATH, STR_PATH = "ZoneVisualUSDJPY.pine", "ZoneStrategyUSDJPY.pine"
IMPORT_6 = "import sekine3310/ZoneEnginePractical/6 as zn\n"
IMPORT_UJ = "import sekine3310/ZoneEnginePracticalUSDJPY/1 as zn\n"     # first publish of the new library = version 1
BASE_REV = "3568c05"                                                    # the USDJPY Visual / Strategy before UJ-1

ENGINE_EDITS = [
    ("header",
     "//  ZoneEnginePractical  —  Practical Zone v1 (Support / Resistance Zone Engine)\n",
     "//  ZoneEnginePractical  —  Practical Zone v1 (Support / Resistance Zone Engine)\n"
     "//  ★ USDJPY 専用 (ZoneEnginePracticalUSDJPY、生成: tests/uj_build.py、UJ-1)。公開版 ZoneEnginePractical/6 の\n"
     "//    ソース (ZoneEnginePracticalSwingMax.pine) と同じ処理・公開 API で、違いは Library 名だけ (fixture uj_sim が固定)。\n"),
    ("name",
     'library("ZoneEnginePractical", overlay = true)\n',
     'library("ZoneEnginePracticalUSDJPY", overlay = true)\n'),
]

VISUAL_EDITS = [
    ("header",
     "//  Zone Visual USDJPY (Compare)  —  OANDA:USDJPY 5分足用 Zone 比較 Indicator (Entry なし)\n",
     "//  Zone Visual USDJPY (Compare)  —  OANDA:USDJPY 5分足用 Zone 比較 Indicator (Entry なし)\n"
     "//  UJ-1: Engine を USDJPY 専用 Library ZoneEnginePracticalUSDJPY (公開版 /6 と同じ処理) に分離 (生成: tests/uj_build.py)。\n"),
    ("import", IMPORT_6, IMPORT_UJ),
    # user decision (UJ-1): the shared Zone Half Width is the Strategy's 0.03 円 (the Visual had 0.05) so both files match
    ("default",
     'zoneHalfWidth = input.float(0.05, "Zone Half Width (円)", minval = 0.005, step = 0.005, group = G_ZONE,\n',
     'zoneHalfWidth = input.float(0.03, "Zone Half Width (円)", minval = 0.005, step = 0.005, group = G_ZONE,\n'),
    ("header",
     "//  Cluster Distance 0.05 / 0.08 / 0.12 円 (初期 0.05 / 0.08)。他の円換算値は暫定 ([暫定] 表記)。\n",
     "//  Cluster Distance 0.05 / 0.08 / 0.12 円 (初期 0.05 / 0.08)。他の円換算値は暫定 ([暫定] 表記)。\n"
     "//  UJ-1: Zone Half Width の初期値を Strategy と同じ 0.03 円に統一 (ユーザー指定。上の「初期 0.05」は UJ-1 前の値)。\n"),
]

# GBPJPY sizing block (gbs_build.QTY_INPUTS) with only the unit comment adapted to USDJPY; the code lines are identical
QTY_INPUTS_UJ = gs.QTY_INPUTS.replace(
    "// 数量 (通貨数、GBP): 参照価格 ref と固定 SL の距離から、損失予算を超えない最大の lot 刻みの倍数。\n"
    "//  損失 (円) = qty × 距離 × syminfo.pointvalue (OANDA:GBPJPY は 1)。無効 / 最小 lot 未満は na (発注しない)\n",
    "// 数量 (通貨数、USD): 参照価格 ref と固定 SL の距離から、損失予算を超えない最大の lot 刻みの倍数。\n"
    "//  損失 (円) = qty × 距離 × syminfo.pointvalue (USDJPY の損益は円建てなので為替換算は不要。pointvalue は固定値にしない)。\n"
    "//  無効 / SL の向き不正 / 距離 0 / 最小 lot 未満は na (発注しない)。参照価格 (A: 指値 / B, C, D: 確定足の終値) に対する\n"
    "//  予定損失の計算であり、約定価格のずれ・スプレッド等を含む実損失の上限ではない (GBPJPY 版 f_stQty と同じ式)\n")
assert QTY_INPUTS_UJ != gs.QTY_INPUTS

_Q = {a: b for a, b in gs.QTY_EDITS}
_cap_old = "     initial_capital        = 10000,\n"
_sta_old = 'var string G_STA = "03 · Strategy Alerts"\n'
_ref_old = ("            [skipRef, tpRef] = f_stTp(side, ref, pSL, f_stNearest(side == 1 ? tpUp : tpDn, side, ref))\n"
            "            if not skipRef\n")
_lim_old = "                    strategy.entry(oEid, side == 1 ? strategy.long : strategy.short, limit = oL)\n"
_mkt_old = "                    strategy.entry(oEid, side == 1 ? strategy.long : strategy.short)\n"

STRATEGY_EDITS = [
    ("header",
     "//  Zone Strategy USDJPY  —  ZONE-JPY (ZoneVisualUSDJPY) の Zone 判定をそのまま使う OANDA:USDJPY 5分足 Strategy\n",
     "//  Zone Strategy USDJPY  —  ZONE-JPY (ZoneVisualUSDJPY) の Zone 判定をそのまま使う OANDA:USDJPY 5分足 Strategy\n"
     "//  UJ-1 (生成: tests/uj_build.py): Engine を USDJPY 専用 Library ZoneEnginePracticalUSDJPY (公開版 /6 と同じ処理) に分離し、\n"
     "//  資金管理を GBPJPY 版と同じにした (初期資金 300,000 円・JPY、元金基準額 300,000 円 × 3 % の単利の損失予算、\n"
     "//  1 lot = 100,000 通貨、0.01 lot で切り捨て、指値・成行とも qty を明示)。売買設定・判定・注文タイミングは変えない。\n"),
    ("import", IMPORT_6, IMPORT_UJ),
    ("size", _cap_old, _Q[_cap_old]),
    ("size", _sta_old, QTY_INPUTS_UJ + _sta_old),
    ("size", _ref_old, _Q[_ref_old]),
    ("size", _lim_old, _Q[_lim_old]),
    ("size", _mkt_old, _Q[_mkt_old]),
]


# ---- UJ-2: adopted defaults from the USDJPY Long comparison (applied after UJ-1) ---------------------------------------
UJ2_NOTE = "USDJPY Long の比較から採用した初期値。年別確認・Short での検証は未完了"
ZONE_DEFAULT_EDITS = [
    ("default",
     'scoreMa1 = input.float(2.0, "Base Score · MA #1", step = 0.5, group = G_MA)\n'
     'scoreMa2 = input.float(2.0, "Base Score · MA #2", step = 0.5, group = G_MA)\n',
     'scoreMa1 = input.float(1.0, "Base Score · MA #1", step = 0.5, group = G_MA)\n'
     'scoreMa2 = input.float(1.0, "Base Score · MA #2", step = 0.5, group = G_MA)\n'),
    ("default",
     'slopeThrMod = input.float(0.02, "[暫定] Slope Threshold · Moderate (円/lookback)", minval = 0.0, step = 0.005, group = G_SLOPE)\n'
     'slopeThrStrong = input.float(0.05, "[暫定] Slope Threshold · Strong (円/lookback)",   minval = 0.0, step = 0.005, group = G_SLOPE)\n',
     'slopeThrMod = input.float(0.01, "[暫定] Slope Threshold · Moderate (円/lookback)", minval = 0.0, step = 0.005, group = G_SLOPE)\n'
     'slopeThrStrong = input.float(0.02, "[暫定] Slope Threshold · Strong (円/lookback)",   minval = 0.0, step = 0.005, group = G_SLOPE)\n'),
    ("default",
     'slopeBonusMod = input.float(1.0, "Slope Bonus · Moderate", step = 0.5, group = G_SLOPE)\n'
     'slopeBonusStr = input.float(2.0, "Slope Bonus · Strong",   step = 0.5, group = G_SLOPE)\n',
     'slopeBonusMod = input.float(0.5, "Slope Bonus · Moderate", step = 0.5, group = G_SLOPE)\n'
     'slopeBonusStr = input.float(1.0, "Slope Bonus · Strong",   step = 0.5, group = G_SLOPE)\n'),
    ("default",
     'scoreDayHL = input.float(3.0, "Base Score · Day High / Low", step = 0.5, group = G_DHL)\n',
     'scoreDayHL = input.float(1.0, "Base Score · Day High / Low", step = 0.5, group = G_DHL)\n'),
    ("default",
     'scoreAcc1 = input.float(3.0, "Base Score · TF #1 Accum", step = 0.5, group = G_ACC)\n'
     'scoreAcc2 = input.float(4.0, "Base Score · TF #2 Accum", step = 0.5, group = G_ACC)\n'
     'scoreAcc3 = input.float(5.0, "Base Score · TF #3 Accum", step = 0.5, group = G_ACC)\n',
     'scoreAcc1 = input.float(4.0, "Base Score · TF #1 Accum", step = 0.5, group = G_ACC)\n'
     'scoreAcc2 = input.float(5.0, "Base Score · TF #2 Accum", step = 0.5, group = G_ACC)\n'
     'scoreAcc3 = input.float(6.0, "Base Score · TF #3 Accum", step = 0.5, group = G_ACC)\n'),
    ("default",
     'clusterDist = input.float(0.08, "Cluster Distance (円)", minval = 0.0, step = 0.005, group = G_CLU,\n'
     '     tooltip = "USDJPY 比較候補: 0.05 / 0.08 / 0.12 円。")\n',
     'clusterDist = input.float(0.12, "Cluster Distance (円)", minval = 0.0, step = 0.005, group = G_CLU,\n'
     '     tooltip = "USDJPY 比較候補: 0.05 / 0.08 / 0.12 円。初期 0.12 円 (12 pips) = ' + UJ2_NOTE + '。")\n'),
    ("default",
     'thrStrong = input.float(10.0, "Strong Score Threshold",      step = 0.5, group = G_SCORE)\n',
     'thrStrong = input.float(8.0, "Strong Score Threshold",      step = 0.5, group = G_SCORE)\n'),
    ("default",
     'confBonus2 = input.float(1.0, "Confluence Bonus · 2 categories",  step = 0.5, group = G_SCORE)\n'
     'confBonus3 = input.float(2.0, "Confluence Bonus · 3 categories",  step = 0.5, group = G_SCORE)\n'
     'confBonus4 = input.float(3.0, "Confluence Bonus · 4+ categories", step = 0.5, group = G_SCORE)\n',
     'confBonus2 = input.float(0.5, "Confluence Bonus · 2 categories",  step = 0.5, group = G_SCORE)\n'
     'confBonus3 = input.float(1.0, "Confluence Bonus · 3 categories",  step = 0.5, group = G_SCORE)\n'
     'confBonus4 = input.float(1.5, "Confluence Bonus · 4+ categories", step = 0.5, group = G_SCORE)\n'),
    ("default",
     'breakBuffer = input.float(0.08,  "[暫定] Break Buffer (円)",         minval = 0.0, step = 0.005, group = G_BF)\n'
     'flipConfirmDist = input.float(0.15, "[暫定] Flip Confirm Distance (円)", minval = 0.0, step = 0.01, group = G_BF)\n',
     'breakBuffer = input.float(0.12,  "[暫定] Break Buffer (円)",         minval = 0.0, step = 0.005, group = G_BF)\n'
     'flipConfirmDist = input.float(0.10, "[暫定] Flip Confirm Distance (円)", minval = 0.0, step = 0.01, group = G_BF)\n'),
]
UJ2_HDR = (
    "//  UJ-2: " + UJ2_NOTE + " (最適値・検証完了ではない): Half Width 0.03 / Cluster 0.12 / Break 0.12 /\n"
    "//  Flip 0.10 円、Medium / Strong / Very Strong 5 / 8 / 15、MA 1 / 1、Slope 閾値 0.01 / 0.02 円・加点 0 / 0.5 / 1 (Sum)、\n"
    "//  Swing 1 / 2 / 3、Day H/L 1、Accum 4 / 5 / 6、Confluence 0.5 / 1 / 1.5、FVG Min Width 0.05 円 (Visual / Strategy 共通)。\n")
VISUAL_EDITS2 = [
    ("header",
     "//  UJ-1: Zone Half Width の初期値を Strategy と同じ 0.03 円に統一 (ユーザー指定。上の「初期 0.05」は UJ-1 前の値)。\n",
     "//  UJ-1: Zone Half Width の初期値を Strategy と同じ 0.03 円に統一 (ユーザー指定。上の「初期 0.05」は UJ-1 前の値)。\n"
     + UJ2_HDR),
] + ZONE_DEFAULT_EDITS
STRATEGY_EDITS2 = [
    ("header",
     "//  1 lot = 100,000 通貨、0.01 lot で切り捨て、指値・成行とも qty を明示)。売買設定・判定・注文タイミングは変えない。\n",
     "//  1 lot = 100,000 通貨、0.01 lot で切り捨て、指値・成行とも qty を明示)。売買設定・判定・注文タイミングは変えない。\n"
     + UJ2_HDR +
     "//  Strategy: Entry D: 1M BOS Rebound、Long Only (Short Only / Both・A〜D は選択可)、SL Buffer 0.05 円、固定 RR 1.5、\n"
     "//  反対 Zone TP OFF、建値移動 OFF (Trigger 値は OFF 時のまま)。\n"),
] + ZONE_DEFAULT_EDITS + [
    ("default",
     'stRR = input.float(1.3, "TP Fixed RR", minval = 0.1, step = 0.1, group = G_STT)\n',
     'stRR = input.float(1.5, "TP Fixed RR", minval = 0.1, step = 0.1, group = G_STT)\n'),
]


# ---- UJ-3: Entry labels (provisional / confirmed) + SL distance in the alert text (Strategy only; after UJ-2) ------------
#  Display / notification only. The label layer is the GBPJPY one (gbs_build LBL_EDITS / GBS-6: same inputs, colours,
#  positions, one provisional label re-set per realtime tick, confirmed labels made in the order branch with the keep
#  limit, max_labels_count 500), adapted to the USDJPY text (4 arguments, no TP) and to the USDJPY provisional validity
#  (pSide != 0: the provisional alert condition is unchanged). The alert text gets one line, SL距離 = |Entry - SL| / 0.01
#  (pips, 0.0); the provisional text uses the reference Entry of the forming bar, the confirmed text the existing order
#  reference (A limit / B, C, D close). Alert conditions / frequencies, orders, SL / TP, sizing unchanged.
#  strip_strategy3() reverses only these -> the UJ-2 Strategy (e1c3cea) byte for byte.
MSG3_OLD = (
    'f_stAlertMsg(string kind, int side, float ePx, float sl) =>\n'
    '    "【" + kind + " " + (side == 1 ? "LONG" : "SHORT") + "】" +\n'
    '     "\\n" + syminfo.tickerid +\n'
    '     "\\nMode: " + stMode +\n'
    '     "\\nE: " + f_num(ePx, "#.000") + (stModeA ? " (指値)" : " (参考。次足始値で成行)") +\n'
    '     "\\nSL: " + f_num(sl, "#.000") +\n')
MSG3_NEW = (
    '//  UJ-3: SL距離 (pips) = |Entry - SL| ÷ 0.01 (USDJPY: 0.01 円 = 1 pip、小数 1 桁)。仮は形成中の足の参考 Entry、\n'
    '//  確定は発注時の参照価格 (A: 指値 / B, C, D: 確定足の終値) から。Entry / SL が na なら "-"\n'
    'float ST_PIP = 0.01\n'
    'f_stAlertMsg(string kind, int side, float ePx, float sl) =>\n'
    '    float slPips = na(ePx) or na(sl) ? na : math.abs(ePx - sl) / ST_PIP\n'
    '    "【" + kind + " " + (side == 1 ? "LONG" : "SHORT") + "】" +\n'
    '     "\\n" + syminfo.tickerid +\n'
    '     "\\nMode: " + stMode +\n'
    '     "\\nE: " + f_num(ePx, "#.000") + (stModeA ? " (指値)" : " (参考。次足始値で成行)") +\n'
    '     "\\nSL: " + f_num(sl, "#.000") +\n'
    '     "\\nSL距離: " + (na(slPips) ? "-" : str.tostring(slPips, "0.0") + " pips") +\n')
PROV3_OLD = (
    "varip int stProvBar = na\n"
    "if stAlertProv and is5mChart and not barstate.isconfirmed and oState == 0 and stSessOK\n"
    "    if na(stProvBar) or stProvBar != bar_index\n"
    "        [pSide, pPx, pSL] = f_stProvEval()\n"
    "        if pSide != 0\n"
    "            stProvBar := bar_index\n"
    "            alert(f_stAlertMsg(\"仮\", pSide, pPx, pSL), alert.freq_once_per_bar)\n")
PROV3_NEW = (
    "varip int stProvBar = na\n"
    "//  UJ-3: 仮評価は仮アラート (未送信の足だけ) か仮ラベルが要るときに 1 回。アラートの条件・頻度・重複防止は従来どおり\n"
    "bool  stPvGate = is5mChart and not barstate.isconfirmed and oState == 0 and stSessOK\n"
    "bool  stPvA    = stAlertProv and stPvGate and (na(stProvBar) or stProvBar != bar_index)\n"
    "bool  stPvL    = stLblProv and stPvGate\n"
    "int   pSide    = 0\n"
    "float pPx      = na\n"
    "float pSL      = na\n"
    "if stPvA or stPvL\n"
    "    [s0, e0, l0] = f_stProvEval()\n"
    "    pSide := s0\n"
    "    pPx   := e0\n"
    "    pSL   := l0\n"
    "bool  stPvOK   = pSide != 0\n"
    "if stPvA and stPvOK\n"
    "    stProvBar := bar_index\n"
    "    alert(f_stAlertMsg(\"仮\", pSide, pPx, pSL), alert.freq_once_per_bar)\n"
    "// 仮ラベル: リアルタイムだけ。1 個のラベルを毎 tick 設定し直す (rollback でも重複・消失しない)。仮通知の送信済み状態は使わない。\n"
    "//  不成立 / 確定 tick / 表示 OFF は非表示。履歴足では何もしない\n"
    "if barstate.isrealtime\n"
    "    if stPvL and stPvOK\n"
    "        label.set_xy(stProvLbl, bar_index, pSide == 1 ? low : high)\n"
    "        label.set_yloc(stProvLbl, pSide == 1 ? yloc.belowbar : yloc.abovebar)\n"
    "        label.set_style(stProvLbl, pSide == 1 ? label.style_label_up : label.style_label_down)\n"
    "        label.set_color(stProvLbl, ST_LBL_PROV)\n"
    "        label.set_textcolor(stProvLbl, color.black)\n"
    "        label.set_text(stProvLbl, f_stAlertMsg(\"仮\", pSide, pPx, pSL))\n"
    "    else\n"
    "        label.set_text(stProvLbl, \"\")\n"
    "        label.set_style(stProvLbl, label.style_none)\n"
    "        label.set_color(stProvLbl, color(na))\n")
LBL_INPUTS_UJ = gs.LBL_INPUTS.replace("成立中は Entry / SL / TP / RR を更新し", "成立中は Entry / SL / SL距離を更新し")
CONF3_OLD = '                    alert(f_stAlertMsg("確定", side, stModeA ? oL : close, oSL), alert.freq_all)\n'
CONF3_NEW = (
    CONF3_OLD +
    '                if stLblConf     // 確定ラベル: 発注した分岐で 1 回 (約定ではない)。確定アラートと同じ値\n'
    '                    array.push(stConfLbls, label.new(bar_index, side == 1 ? low : high, f_stAlertMsg("確定", side, stModeA ? oL : close, oSL),\n'
    '                         yloc = side == 1 ? yloc.belowbar : yloc.abovebar, color = side == 1 ? ST_LBL_LONG : ST_LBL_SHORT,\n'
    '                         textcolor = color.white, style = side == 1 ? label.style_label_up : label.style_label_down, size = size.small))\n'
    '                    if array.size(stConfLbls) > stLblKeep\n'
    '                        label.delete(array.shift(stConfLbls))\n')
STRATEGY_EDITS3 = [
    ("header",
     "//  反対 Zone TP OFF、建値移動 OFF (Trigger 値は OFF 時のまま)。\n",
     "//  反対 Zone TP OFF、建値移動 OFF (Trigger 値は OFF 時のまま)。\n"
     "//  UJ-3 (表示・通知のみ): 仮 / 確定 Entry ラベル (GBPJPY 版と同じ仕様) と、仮 / 確定アラートの SL距離 (pips = |Entry - SL| ÷ 0.01)。\n"
     "//  アラートの発火条件・頻度、Entry / SL / TP / 数量 / 注文・約定の処理は変えない。\n"),
    ("label", "     default_qty_value      = 1)\n", "     default_qty_value      = 1,\n     max_labels_count       = 500)\n"),
    ("label",
     '     tooltip = "5分足の確定時に strategy.entry を出したときだけ (約定通知ではない)。")\n',
     '     tooltip = "5分足の確定時に strategy.entry を出したときだけ (約定通知ではない)。")\n' + LBL_INPUTS_UJ),
    ("msg", MSG3_OLD, MSG3_NEW),
    ("label", CONF3_OLD, CONF3_NEW),
    ("label", PROV3_OLD, PROV3_NEW),
]


# ---- UJ-4: TP / RR in the labels and alert texts (Strategy only; after UJ-3) ---------------------------------------------
#  Display / notification only, the GBPJPY method (gbs_build MSG_EDITS / GBS-5): TP = the result of the existing pre-order
#  f_stTp call for the same reference price (fixed RR / opposite-zone TP / its fallback) - the confirmed text reuses tpRef of
#  the order branch, the provisional text the tp f_stProvEval already computes (returned as a 4th value); RR = profit-side
#  TP distance / |Entry - SL| ("1:x", up to 2 decimals); invalid risk / TP -> "-". The USDJPY lines (Mode, E, SL, SL距離)
#  stay; TP / RR follow SL距離 in the GBPJPY order. The confirmed TP is the planned value at the order reference (the TP
#  order is still set from the actual fill after the fill), so the confirmed line keeps the former "約定確認後に設定" meaning.
#  No order / alert / label condition changes. strip_strategy4() reverses only these -> the UJ-3 Strategy (ab9820f).
MSG4_OLD = (
    'f_stAlertMsg(string kind, int side, float ePx, float sl) =>\n'
    '    float slPips = na(ePx) or na(sl) ? na : math.abs(ePx - sl) / ST_PIP\n')
MSG4_NEW = (
    '//  UJ-4: TP は発注前の RR 判定 (f_stTp) と同じ結果を受け取る (通知用の値。実際の TP 注文は約定確認後に実約定価格から決める)。\n'
    '//  RR = 利益方向の TP 距離 ÷ Entry から SL までの距離 (1:x、小数 2 桁まで)。risk <= 0 / TP na は "-"\n'
    'f_stAlertMsg(string kind, int side, float ePx, float sl, float tp) =>\n'
    '    float slPips = na(ePx) or na(sl) ? na : math.abs(ePx - sl) / ST_PIP\n'
    '    float risk   = side == 1 ? ePx - sl : sl - ePx\n'
    '    bool  okR    = not na(risk) and risk > 0\n'
    '    float rr     = okR and not na(tp) ? (side == 1 ? tp - ePx : ePx - tp) / risk : na\n')
TAIL4_OLD = '     (kind == "仮" ? "\\n※未確定: 5分足の確定時に不成立になる場合あり" : "\\nTP: 約定確認後に設定")\n'
TAIL4_NEW = (
    '     "\\nTP: " + (okR ? f_num(tp, "#.000") : "-") + (kind == "仮" ? "" : " (発注時の予定値。最終 TP は約定確認後に実約定価格から設定)") +\n'
    '     "\\nRR: " + (na(rr) ? "-" : "1:" + str.tostring(rr, "0.##")) +\n'
    '     (kind == "仮" ? "\\n※未確定: 5分足の確定時に不成立になる場合あり" : "")\n')
STRATEGY_EDITS4 = [
    ("header",
     "//  アラートの発火条件・頻度、Entry / SL / TP / 数量 / 注文・約定の処理は変えない。\n",
     "//  アラートの発火条件・頻度、Entry / SL / TP / 数量 / 注文・約定の処理は変えない。\n"
     "//  UJ-4 (表示・通知のみ): ラベル / アラートに TP・RR (GBPJPY 版と同じ方式: 発注前の f_stTp の結果、RR 1:x)。確定の TP は\n"
     "//  発注時の予定値 (最終 TP は約定確認後に実約定価格から設定)。売買・発注・アラート / ラベルの条件は変えない。\n"),
    ("msg", MSG4_OLD, MSG4_NEW),
    ("msg", TAIL4_OLD, TAIL4_NEW),
    ("prov",
     "    float ePx = na\n    float sl  = na\n    if side != 0\n",
     "    float ePx = na\n    float sl  = na\n    float tpP = na     // 通知 TP: 下の RR 事前判定と同じ f_stTp の結果\n    if side != 0\n"),
    ("prov",
     "        if skipRef\n            side := 0\n    [side, ePx, sl]\n",
     "        tpP := tpRef\n        if skipRef\n            side := 0\n    [side, ePx, sl, tpP]\n"),
    ("conf",
     '                    alert(f_stAlertMsg("確定", side, stModeA ? oL : close, oSL), alert.freq_all)\n',
     '                    alert(f_stAlertMsg("確定", side, stModeA ? oL : close, oSL, tpRef), alert.freq_all)\n'),
    ("conf",
     '                    array.push(stConfLbls, label.new(bar_index, side == 1 ? low : high, f_stAlertMsg("確定", side, stModeA ? oL : close, oSL),\n',
     '                    array.push(stConfLbls, label.new(bar_index, side == 1 ? low : high, f_stAlertMsg("確定", side, stModeA ? oL : close, oSL, tpRef),\n'),
    ("prov", "float pSL      = na\n", "float pSL      = na\nfloat pTP      = na\n"),
    ("prov", "    [s0, e0, l0] = f_stProvEval()\n", "    [s0, e0, l0, t0] = f_stProvEval()\n"),
    ("prov", "    pSL   := l0\n", "    pSL   := l0\n    pTP   := t0\n"),
    ("prov",
     '    alert(f_stAlertMsg("仮", pSide, pPx, pSL), alert.freq_once_per_bar)\n',
     '    alert(f_stAlertMsg("仮", pSide, pPx, pSL, pTP), alert.freq_once_per_bar)\n'),
    ("prov",
     '        label.set_text(stProvLbl, f_stAlertMsg("仮", pSide, pPx, pSL))\n',
     '        label.set_text(stProvLbl, f_stAlertMsg("仮", pSide, pPx, pSL, pTP))\n'),
    ("label",
     "成立中は Entry / SL / SL距離を更新し",
     "成立中は Entry / SL / SL距離 / TP / RR を更新し"),
]


# ---- UJ-5: confirmed alert at most once per 5M bar (Strategy only; after UJ-4) ------------------------------------------
#  Notification only. The confirmed alert() sits in the order branch of the confirmed-bar block (one call per execution). If
#  TradingView executes the same bar's confirmed update again in realtime, var state (oState, oSeq ...) is rolled back to the
#  previous bar's committed values, so the order branch runs again and alert() - a side effect that is never rolled back -
#  is sent a second time with the same text. A varip bar key (time of the 5M bar) survives the rollback: the confirmed alert
#  is sent only when it was not yet sent for this bar. Its own state (independent of the provisional stProvBar); a new entry
#  on another bar has another time and is not suppressed. The order, the label (rolled back / re-made with the execution)
#  and alert.freq_all are unchanged (freq_once_per_bar is not used: it would also count the provisional alert of the same
#  bar). strip_strategy5() reverses only these -> the UJ-4 Strategy (89bc82b).
STRATEGY_EDITS5 = [
    ("header",
     "//  発注時の予定値 (最終 TP は約定確認後に実約定価格から設定)。売買・発注・アラート / ラベルの条件は変えない。\n",
     "//  発注時の予定値 (最終 TP は約定確認後に実約定価格から設定)。売買・発注・アラート / ラベルの条件は変えない。\n"
     "//  UJ-5 (通知のみ): 確定アラートは同じ 5分足で最大 1 回 (varip の足キー stConfBar。同じ足の確定更新が再計算されても\n"
     "//  再送しない)。別の足の新規 Entry は抑制しない。仮アラートの stProvBar とは独立。発注・ラベル・freq_all は変えない。\n"),
    ("dedup",
     "var int    oClosed = 0\n",
     "var int    oClosed = 0\n"
     "varip int  stConfBar = na     // UJ-5: 確定アラートを送った 5分足の time。varip = 同じ足の再計算 (rollback) でも残る\n"),
    ("dedup",
     "                if stAlertConf\n"
     "                    alert(f_stAlertMsg(\"確定\", side, stModeA ? oL : close, oSL, tpRef), alert.freq_all)\n",
     "                if stAlertConf and (na(stConfBar) or stConfBar != time)     // UJ-5: 同じ 5分足では最大 1 回\n"
     "                    stConfBar := time\n"
     "                    alert(f_stAlertMsg(\"確定\", side, stModeA ? oL : close, oSL, tpRef), alert.freq_all)\n"),
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


def base(path):
    """the USDJPY file before UJ-1 (commit BASE_REV)."""
    import subprocess
    return subprocess.run(["git", "-C", ROOT, "show", f"{BASE_REV}:{path}"], capture_output=True, text=True).stdout


def build_engine():
    return _apply(_rd(ENG_SRC), ENGINE_EDITS)


def build_visual1():
    """UJ-1 only (commit a6a275c)."""
    return _apply(base(VIS_PATH), VISUAL_EDITS)


def build_strategy1():
    """UJ-1 only (commit a6a275c)."""
    return _apply(base(STR_PATH), STRATEGY_EDITS)


def build_visual():
    return _apply(build_visual1(), VISUAL_EDITS2)


def build_strategy2():
    """UJ-1 + UJ-2 (commit e1c3cea)."""
    return _apply(build_strategy1(), STRATEGY_EDITS2)


def build_strategy3():
    """UJ-1 + UJ-2 + UJ-3 (commit ab9820f)."""
    return _apply(build_strategy2(), STRATEGY_EDITS3)


def build_strategy4():
    """UJ-1 .. UJ-4 (commit 89bc82b)."""
    return _apply(build_strategy3(), STRATEGY_EDITS4)


def build_strategy():
    return _apply(build_strategy4(), STRATEGY_EDITS5)


def strip_engine(t):
    return _revert(t, ENGINE_EDITS)


def strip_visual2(t):
    """reverse only the UJ-2 defaults (-> the UJ-1 Visual byte for byte)."""
    return _revert(t, VISUAL_EDITS2)


def strip_strategy2(t):
    """reverse only the UJ-2 defaults (-> the UJ-1 Strategy byte for byte)."""
    return _revert(t, STRATEGY_EDITS2)


def strip_visual(t):
    """reverse UJ-2 and UJ-1 (-> the pre-UJ Visual of 3568c05)."""
    return _revert(strip_visual2(t), VISUAL_EDITS)


def strip_strategy5(t):
    """reverse only the UJ-5 confirmed-alert dedup (-> the UJ-4 Strategy of 89bc82b byte for byte)."""
    return _revert(t, STRATEGY_EDITS5)


def strip_strategy4(t):
    """reverse the UJ-5 dedup when present (all or nothing) and the UJ-4 TP / RR display (-> the UJ-3 Strategy of ab9820f
    byte for byte)."""
    if t is not None and STRATEGY_EDITS5[0][2] in t:     # UJ-5 header present -> the whole UJ-5 layer must revert
        t = strip_strategy5(t)
    return _revert(t, STRATEGY_EDITS4)


def strip_strategy3(t):
    """reverse the UJ-4 TP / RR display when present (all or nothing) and the UJ-3 labels / SL distance (-> the UJ-2
    Strategy byte for byte). A text with only part of the UJ-4 edits gives None."""
    if t is not None and STRATEGY_EDITS4[0][2] in t:     # UJ-4 header present -> the whole UJ-4 layer must revert
        t = strip_strategy4(t)
    return _revert(t, STRATEGY_EDITS3)


def strip_strategy(t):
    """reverse UJ-5, UJ-4, UJ-3, UJ-2 and UJ-1 (-> the pre-UJ Strategy of 3568c05)."""
    return _revert(strip_strategy2(strip_strategy3(t)), STRATEGY_EDITS)


if __name__ == "__main__":
    for path, fn in ((ENG_PATH, build_engine), (VIS_PATH, build_visual), (STR_PATH, build_strategy)):
        open(os.path.join(ROOT, path), "w", encoding="utf-8").write(fn())
        print("written", path)


# ---- helpers for the older fixtures (they pin the USDJPY files as they were before UJ-1) ------------------------------
UJ_FILES = (VIS_PATH, STR_PATH)


def pre_uj(path, text=None):
    """the USDJPY Visual / Strategy text with the UJ-1 edits reverted (unchanged if they are not present)."""
    if text is None:
        text = _rd(path)
    s = (strip_visual if path == VIS_PATH else strip_strategy)(text)
    return text if s is None else s


def uj_ok(path, rev):
    """True when the working-tree file differs from `rev` only by the UJ-1 edits (exact, byte for byte)."""
    import subprocess
    old = subprocess.run(["git", "-C", ROOT, "show", f"{rev}:{path}"], capture_output=True, text=True).stdout
    s = (strip_visual if path == VIS_PATH else strip_strategy)(_rd(path))
    return s is not None and s == old


def drop_uj(names, rev):
    """remove the USDJPY files from a list of changed paths only when they differ from `rev` exactly by UJ-1."""
    # BTE-1 (later split of the BTC Engine): the BTC Visual / Strategy may also differ, exactly by that layer
    # XA-1 (Gold defaults): ZONE-P / ZONE-ST may also differ, exactly by that layer
    # CAD-1 (confirmed-alert dedup): the four GBPJPY-lineage Strategies / adapted fixtures may also differ, exactly by it
    return [n for n in names if not ((n in UJ_FILES and uj_ok(n, rev)) or __import__("bte_build").bte_pine_ok(n, rev)
                                     or __import__("xa_build").xa_ok(n, rev) or __import__("cad_adapt").ok(n, rev))]


# ---- exact adaptations of the older fixtures to UJ-1 (each must occur once; unadapt() reverses them) ---------------
TEST_ADAPT = {'tests/btc_sim.py': [('    check(f"BS-15 existing files unchanged vs base HEAD {BASE}',
                       '    out, out1, out2 = '
                       '(__import__("uj_build").drop_uj_tests(__import__("uj_build").drop_uj(out, BASE)), '
                       '__import__("uj_build").drop_uj_tests(__import__("uj_build").drop_uj(out1, BTC1_COMMIT)),\n'
                       '                       '
                       '__import__("uj_build").drop_uj_tests(__import__("uj_build").drop_uj(out2, BTC2_COMMIT)))     '
                       '# UJ-1: USDJPY Visual / Strategy may differ only by the USDJPY Engine split + sizing (exact, '
                       'see uj_build)\n'
                       '    check(f"BS-15 existing files unchanged vs base HEAD {BASE}')],
 'tests/btcs_sim.py': [('    check(f"SB-17 existing files unchanged vs {BASE}',
                        '    out, out2 = __import__("uj_build").drop_uj_tests(__import__("uj_build").drop_uj(out, '
                        'BASE)), __import__("uj_build").drop_uj_tests(__import__("uj_build").drop_uj(out2, '
                        'BTS1_COMMIT))     # UJ-1: USDJPY Visual / Strategy may differ only by the USDJPY Engine '
                        'split + sizing (exact, see uj_build)\n'
                        '    check(f"SB-17 existing files unchanged vs {BASE}'),
                       ('    return old.count(BTC_SIM_OLD) == 1 and rd("tests/btc_sim.py") == exp\n',
                        '    return old.count(BTC_SIM_OLD) == 1 and '
                        '__import__("uj_build").unadapt("tests/btc_sim.py", rd("tests/btc_sim.py")) == exp\n')],
 'tests/eu_sim.py': [('          set(mod) <= {"tests/btc_sim.py", "tests/btcs_sim.py"} and rd("tests/btc_sim.py") == '
                      'exp_btc\n'
                      '          and rd("tests/btcs_sim.py") == exp_bts and exp_bts != show("tests/btcs_sim.py"), '
                      'str(mod))',
                      '          set(__import__("uj_build").drop_uj_tests(__import__("uj_build").drop_uj(mod, '
                      'BASE))) <= {"tests/btc_sim.py", "tests/btcs_sim.py"}\n'
                      '          and __import__("uj_build").unadapt("tests/btc_sim.py", rd("tests/btc_sim.py")) == '
                      'exp_btc\n'
                      '          and __import__("uj_build").unadapt("tests/btcs_sim.py", rd("tests/btcs_sim.py")) == '
                      'exp_bts and exp_bts != show("tests/btcs_sim.py"), str(mod))'),
                     ('"USDJPY / Gold files untouched)", set(mod) <= {eb.VIS_PATH, eb.STR_PATH, "tests/eu_build.py", '
                      '"tests/eu_sim.py"}',
                      '"USDJPY / Gold files untouched)", '
                      'set(__import__("uj_build").drop_uj_tests(__import__("uj_build").drop_uj(mod, EU1))) <= '
                      '{eb.VIS_PATH, eb.STR_PATH, "tests/eu_build.py", "tests/eu_sim.py"}')],
 'tests/gbd_sim.py': [('d.returncode == 0 and d.stdout.strip() == "" and '
                       'all(re.match(r"^tests/gb[defjsx]_\\w+\\.py$", f) for f in t.split()),',
                       'd.returncode == 0 and __import__("uj_build").drop_uj(d.stdout.split(), PREV) == [] and '
                       'all(re.match(r"^tests/gb[defjsx]_\\w+\\.py$", f) for f in '
                       '__import__("uj_build").drop_uj_tests(t.split())),')],
 'tests/gbe_sim.py': [('d.returncode == 0 and d.stdout.strip() == "" and all(re.match(r"^tests/gb[ejsx]_\\w+\\.py$", '
                       'f) for f in t.split()),',
                       'd.returncode == 0 and __import__("uj_build").drop_uj(d.stdout.split(), PREV) == [] and '
                       'all(re.match(r"^tests/gb[ejsx]_\\w+\\.py$", f) for f in '
                       '__import__("uj_build").drop_uj_tests(t.split())),')],
 'tests/gbf_sim.py': [('d.returncode == 0 and d.stdout.strip() == "" and '
                       'all(re.match(r"^tests/gb[efjsx]_\\w+\\.py$", f) for f in t.split()),',
                       'd.returncode == 0 and __import__("uj_build").drop_uj(d.stdout.split(), PREV) == [] and '
                       'all(re.match(r"^tests/gb[efjsx]_\\w+\\.py$", f) for f in '
                       '__import__("uj_build").drop_uj_tests(t.split())),')],
 'tests/gbj_build.py': [('    return gbj_transform(open(os.path.join(ROOT, SRC_PATH), encoding="utf-8").read())\n',
                         '    return gbj_transform(__import__("uj_build").pre_uj(SRC_PATH))     # UJ-1: USDJPY '
                         'Visual / Strategy may differ only by the USDJPY Engine split + sizing (exact, see '
                         'uj_build)\n')],
 'tests/gbj_sim.py': [('JPY = open(os.path.join(ROOT, gb.SRC_PATH), encoding="utf-8").read()\n',
                       'JPY = __import__("uj_build").pre_uj(gb.SRC_PATH)     # UJ-1: USDJPY Visual / Strategy may '
                       'differ only by the USDJPY Engine split + sizing (exact, see uj_build)\n'),
                      ('"unchanged vs base HEAD " + BASE, d.returncode == 0 and d.stdout.strip() == "", d.stdout + '
                       'd.stderr)',
                       '"unchanged vs base HEAD " + BASE, d.returncode == 0 and '
                       '__import__("uj_build").drop_uj(d.stdout.split(), BASE) == [], d.stdout + d.stderr)'),
                      ('"jpy_build still regenerates ZONE-JPY", j.strip() == "" and jb.build() == JPY, j)',
                       '"jpy_build still regenerates ZONE-JPY", __import__("uj_build").drop_uj_tests(j.split()) == '
                       '[] and jb.build() == JPY, j)')],
 'tests/gbn_sim.py': [('d.returncode == 0 and d.stdout.strip() == "" and re.findall(r"^import .*$", GBS, re.M) == '
                       '[ge.IMPORT_GBE.strip()],',
                       'd.returncode == 0 and __import__("uj_build").drop_uj(d.stdout.split(), PREV) == [] and '
                       're.findall(r"^import .*$", GBS, re.M) == [ge.IMPORT_GBE.strip()],')],
 'tests/gbq_sim.py': [('d.returncode == 0 and d.stdout.strip() == "" and re.findall(r"^import .*$", G4, re.M) == '
                       '[ge.IMPORT_GBE.strip()],',
                       'd.returncode == 0 and __import__("uj_build").drop_uj(d.stdout.split(), PREV) == [] and '
                       're.findall(r"^import .*$", G4, re.M) == [ge.IMPORT_GBE.strip()],')],
 'tests/gbs_sim.py': [('          d.returncode == 0 and d.stdout.strip() == ""\n'
                       '          and all(re.match(r"^tests/gb[jsx]_\\w+\\.py$", f) for f in t.split()), d.stdout + '
                       't)',
                       '          d.returncode == 0 and __import__("uj_build").drop_uj(d.stdout.split(), BASE) == '
                       '[]\n'
                       '          and all(re.match(r"^tests/gb[jsx]_\\w+\\.py$", f) for f in '
                       '__import__("uj_build").drop_uj_tests(t.split())), d.stdout + t)'),
                      ('STJ = rd(sj.STJ_PATH)\n',
                       'STJ = __import__("uj_build").pre_uj(sj.STJ_PATH)     # UJ-1: USDJPY Visual / Strategy may '
                       'differ only by the USDJPY Engine split + sizing (exact, see uj_build)\n')],
 'tests/gbx_sim.py': [('d.returncode == 0 and d.stdout.strip() == "" and all(re.match(r"^tests/gb[jsx]_\\w+\\.py$", '
                       'f) for f in t.split()),',
                       'd.returncode == 0 and __import__("uj_build").drop_uj(d.stdout.split(), BASE) == [] and '
                       'all(re.match(r"^tests/gb[jsx]_\\w+\\.py$", f) for f in '
                       '__import__("uj_build").drop_uj_tests(t.split())),')],
 'tests/gu_sim.py': [('"new GBPUSD files are added", mod == [], str(mod))',
                      '"new GBPUSD files are added", '
                      '__import__("uj_build").drop_uj_tests(__import__("uj_build").drop_uj(mod, BASE)) == [], '
                      'str(mod))')],
 'tests/jpy_sim.py': [('JPY = open(os.path.join(ROOT, jb.JPY_PATH), encoding="utf-8").read() if '
                       'os.path.exists(os.path.join(ROOT, jb.JPY_PATH)) else ""\n',
                       'JPY = __import__("uj_build").pre_uj(jb.JPY_PATH) if os.path.exists(os.path.join(ROOT, '
                       'jb.JPY_PATH)) else ""     # UJ-1: USDJPY Visual / Strategy may differ only by the USDJPY '
                       'Engine split + sizing (exact, see uj_build)\n')],
 'tests/stj_sim.py': [('STJ = open(os.path.join(ROOT, sj.STJ_PATH), encoding="utf-8").read() if '
                       'os.path.exists(os.path.join(ROOT, sj.STJ_PATH)) else ""\n'
                       'JPYV = open(os.path.join(ROOT, jb.JPY_PATH), encoding="utf-8").read()\n',
                       'STJ = __import__("uj_build").pre_uj(sj.STJ_PATH) if os.path.exists(os.path.join(ROOT, '
                       'sj.STJ_PATH)) else ""     # UJ-1: USDJPY Visual / Strategy may differ only by the USDJPY '
                       'Engine split + sizing (exact, see uj_build)\n'
                       'JPYV = __import__("uj_build").pre_uj(jb.JPY_PATH)\n'),
                      ('          d.strip() == "", d)\n',
                       '          __import__("uj_build").drop_uj(d.split(), "5e2459b") == [], d)\n')]}


def unadapt(path, text):
    """a test file with its UJ-1 adaptation reverted (unchanged for files not in TEST_ADAPT)."""
    out = __import__("bte_build").unadapt(path, text)     # BTE-1 adaptations (later) are reverted first
    for a, b in reversed(TEST_ADAPT.get(path, [])):
        if out is None:
            return None
        if out.count(b) != 1:
            return None
        out = out.replace(b, a)
    return out


def test_ok(path):
    """True when the test file differs from BASE_REV only by its exact UJ-1 adaptation."""
    return (path in TEST_ADAPT or path in __import__("bte_build").TEST_ADAPT or path in __import__("xa_build").TEST_ADAPT) \
        and unadapt(path, _rd(path)) == base(path)


def drop_uj_tests(names):
    """remove adapted test files from a changed-path list only when they differ from BASE_REV exactly by TEST_ADAPT."""
    return [n for n in names if not test_ok(n)]
