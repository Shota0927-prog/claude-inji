"""GBS-1 — ZoneStrategyGBPJPY.pine: OANDA:GBPJPY 5M comparison strategy (A / B / C / D + provisional / confirmed alerts).

Deterministic build, the same pipeline as ZoneStrategyUSDJPY (stj_build) but starting from the GBPJPY Visual:
  ZoneVisualGBPJPY text (gbj_build.build())
    -> st1_build.st_transform   (computation part kept byte for byte, display removed, Zone evaluation block)
    -> st2_build.st2_transform  (A / B / C orders)
    -> st3_build.st3_transform  (D 1M BOS, session, opposite-zone TP, breakeven)
    -> EDITS                    (= stj_build.EDITS, the USDJPY order / alert edits, with only these differences:
                                 identity / header / comments name GBPJPY, the display-only label helper removed is the
                                 GBPJPY one)
    -> import                   (GBJ-4: ZoneEnginePracticalGBPJPY, as the Visual; ST-1 runs on the /6 import line)
    -> BASE_EDITS               (GBPJPY base-setting strategy defaults: SL Buffer 0.08, RR 1.2; the Zone defaults incl.
                                 Half Width 0.05 come from ZONE-GBPJPY since GBJ-3)
strip_gbs() reverses EDITS exactly (fixture gbs_sim). Zone calculation = ZONE-GBPJPY, order / alert logic = ZONE-ST-JPY.
GBPJPY base setting (GBS-2 / GBJ-3, from one comparison period; not proven optimal): D, Long Only, HW 0.05 (= Visual) /
Cluster 0.08 / FVG 0.05, SL Buffer 0.08, RR 1.2, session JST 09:00-02:00, zone TP OFF, breakeven OFF (0.15), D wait 30,
provisional / confirmed alerts ON, RN OFF.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gbj_build as gb     # noqa: E402
import st1_build as tb     # noqa: E402
import st2_build as s2     # noqa: E402
import st3_build as s3     # noqa: E402
import stj_build as sj     # noqa: E402
import gbe_build as ge     # noqa: E402

ROOT = gb.ROOT
GBS_PATH = "ZoneStrategyGBPJPY.pine"

HEADER_JPY = sj.EDITS[0][1]
HEADER_GBS = ("//  Zone Strategy GBPJPY  —  ZONE-GBPJPY (ZoneVisualGBPJPY) の Zone 判定をそのまま使う OANDA:GBPJPY 5分足 Strategy\n"
              "//  (生成: tests/gbs_build.py。Zone 計算は ZONE-GBPJPY、注文処理・仮 / 確定アラートは ZONE-ST-JPY\n"
              "//   (ZoneStrategyUSDJPY) と同じ式。価格差は円。初期値は GBPJPY 基準設定 (ある比較期間の TradingView 結果から\n"
              "//   決めたもの。最適値・別期間での有効性は未確認)。Zone 関連の初期値 (Half Width 0.05 円を含む) は表示用\n"
              "//   ZONE-GBPJPY と同じ)\n")
TITLE_JPY = sj.EDITS[1][1]
TITLE_GBS = '     title                  = "Zone Strategy GBPJPY",\n     shorttitle             = "ZONE-ST-GBPJPY",\n'
GEOM_GBS = ('\n// Zone の上下限と最終的な幅 (円、小数 3 桁 = OANDA:GBPJPY の最小刻み 0.001。pips ではない)\n'
            'f_jpyGeom(zn.Zone z) =>\n'
            '    f_num(z.top, "#.000") + " - " + f_num(z.bottom, "#.000") + " | W " + f_num(z.top - z.bottom, "0.000") + "円"\n')
# USDJPY edit not needed here: the Half Width default (0.05) comes from ZONE-GBPJPY itself (GBJ-3).
SKIP_PREFIX = ('zoneHalfWidth = input.float(0.05,',)
# GBPJPY base setting (GBS-2): defaults only, applied after the USDJPY strategy edits (Direction Long Only comes from
# those edits). Values not listed here (Entry Mode D, Cluster 0.08, FVG 0.05, session JST 09:00-02:00, zone TP OFF,
# breakeven OFF / 0.15, D wait 30, both alerts ON, RN OFF) are already the base setting.
BASE_EDITS = [
    ('stBuffer = input.float(0.05, "[暫定] SL Buffer (円)",', 'stBuffer = input.float(0.08, "[暫定] SL Buffer (円)",'),
    ('stRR = input.float(1.3, "TP Fixed RR",', 'stRR = input.float(1.2, "TP Fixed RR",'),
]


# ---- GBS-4: position size from a fixed (simple-interest) loss budget and the fixed SL (Strategy only) ----------------
#  qty unit = units of the base currency (GBP). syminfo.pointvalue (OANDA:GBPJPY = 1) converts a 1.0 price move of one
#  unit into JPY, so loss = qty * distance * pointvalue; lots are only a display (qty / units per lot).
#  budget = capital base * loss % (never equity: losses / profits do not change it). qty = floor(budget / (distance *
#  pointvalue * step units) + 1e-9) * step units (the 1e-9 only absorbs float noise); below one step / invalid
#  distance -> no order. The reference price is the one already used for the pre-order RR check (A: the limit, B / C / D:
#  the confirmed 5M close); the actual fill is not looked ahead and the quantity is never changed after the fill.
#  strip_qty() reverses these -> the GBS-3 Strategy (dedfbbc) byte for byte.
QTY_INPUTS = (
    'var string G_STQ = "03 · Strategy Position Size (単利・損失予算)"\n'
    'stCapBase = input.float(300000.0, "元金基準額 (円)", minval = 0.0, step = 10000.0, group = G_STQ,\n'
    '     tooltip = "単利: 損失予算はこの基準額 × 損失率で固定 (損益で増減しない)。strategy の初期資金とは別の入力。")\n'
    'stRiskPct = input.float(3.0, "損失予算 (%)", minval = 0.0, step = 0.1, group = G_STQ)\n'
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
    '    q\n'
    '\n')
QTY_EDITS = [
    ("     initial_capital        = 10000,\n",
     "     initial_capital        = 300000,\n     currency               = currency.JPY,\n"),
    ('var string G_STA = "03 · Strategy Alerts"\n', QTY_INPUTS + 'var string G_STA = "03 · Strategy Alerts"\n'),
    ("f_stAlertMsg(string kind, int side, float ePx, float sl) =>\n",
     "f_stAlertMsg(string kind, int side, float ePx, float sl, float qty) =>\n"),
    ('     "\\nSL: " + f_num(sl, "#.000") +\n',
     '     "\\nSL: " + f_num(sl, "#.000") +\n'
     '     "\\nLot: " + f_num(qty / stLotUnits, "0.00") + " (" + f_num(qty, "#") + " 通貨)" +\n'
     '     (kind == "仮" ? " 参考値・確定時の終値で再計算" : "") +\n'),
    ("            [skipRef, tpRef] = f_stTp(side, ref, pSL, f_stNearest(side == 1 ? tpUp : tpDn, side, ref))\n"
     "            if not skipRef\n",
     "            [skipRef, tpRef] = f_stTp(side, ref, pSL, f_stNearest(side == 1 ? tpUp : tpDn, side, ref))\n"
     "            // 数量: 同じ参照価格 (A: 指値 / B, C, D: この確定足の終値) と固定 SL から。無効 / 最小 lot 未満は発注しない\n"
     "            float  pQty = f_stQty(side, ref, pSL)\n"
     "            if not skipRef and not na(pQty)\n"),
    ("                    strategy.entry(oEid, side == 1 ? strategy.long : strategy.short, limit = oL)\n",
     "                    strategy.entry(oEid, side == 1 ? strategy.long : strategy.short, qty = pQty, limit = oL)\n"),
    ("                    strategy.entry(oEid, side == 1 ? strategy.long : strategy.short)\n",
     "                    strategy.entry(oEid, side == 1 ? strategy.long : strategy.short, qty = pQty)\n"),
    ('                    alert(f_stAlertMsg("確定", side, stModeA ? oL : close, oSL), alert.freq_all)\n',
     '                    alert(f_stAlertMsg("確定", side, stModeA ? oL : close, oSL, pQty), alert.freq_all)\n'),
    ("        [pSide, pPx, pSL] = f_stProvEval()\n"
     "        if pSide != 0\n"
     "            stProvBar := bar_index\n"
     "            alert(f_stAlertMsg(\"仮\", pSide, pPx, pSL), alert.freq_once_per_bar)\n",
     "        [pSide, pPx, pSL] = f_stProvEval()\n"
     "        float pvQty = pSide != 0 ? f_stQty(pSide, pPx, pSL) : na     // 参考値 (確定時の終値で再計算される)\n"
     "        if pSide != 0 and not na(pvQty)\n"
     "            stProvBar := bar_index\n"
     "            alert(f_stAlertMsg(\"仮\", pSide, pPx, pSL, pvQty), alert.freq_once_per_bar)\n"),
]


def strip_qty(text):
    """reverse the GBS-6 / GBS-5 and the GBS-4 position-size edits (-> the GBS-3 Strategy text)."""
    out = strip_msg(text) if text is not None and "f_stPx(" in text else text
    for a, b in reversed(QTY_EDITS):
        if out is None or out.count(b) != 1:
            return None
        out = out.replace(b, a)
    return out


# ---- GBS-5: alert text (replaces the earlier text requests) — applied after QTY_EDITS ----------------------------------
#  【確定】GBPJPY｜LONG / Entry / SL / SL距離 (pips, 0.01 円 = 1 pip) / TP / RR (1:x, up to 2 decimals); 仮 adds the note.
#  Entry = the existing notification price (A limit / B, C, D confirmed 5M close); TP = the result of the existing
#  pre-order f_stTp call for that price (fixed RR / zone TP / fallback) - the confirmed alert reuses tpRef, the provisional
#  alert the tp f_stProvEval already computes. The TP order itself is still set from the actual fill after the fill.
#  Prices with format.mintick; no lot / qty / Entry Mode / loss %. Invalid risk / TP -> "-". Built only when sent.
MSG_OLD_FN = (
    'f_stAlertMsg(string kind, int side, float ePx, float sl, float qty) =>\n'
    '    "【" + kind + " " + (side == 1 ? "LONG" : "SHORT") + "】" +\n'
    '     "\\n" + syminfo.tickerid +\n'
    '     "\\nMode: " + stMode +\n'
    '     "\\nE: " + f_num(ePx, "#.000") + (stModeA ? " (指値)" : " (参考。次足始値で成行)") +\n'
    '     "\\nSL: " + f_num(sl, "#.000") +\n'
    '     "\\nLot: " + f_num(qty / stLotUnits, "0.00") + " (" + f_num(qty, "#") + " 通貨)" +\n'
    '     (kind == "仮" ? " 参考値・確定時の終値で再計算" : "") +\n'
    '     (kind == "仮" ? "\\n※未確定: 5分足の確定時に不成立になる場合あり" : "\\nTP: 約定確認後に設定")\n')
MSG_NEW_FN = (
    '//  GBPJPY: 0.01 円 = 1 pip。Entry / SL / TP は最小価格刻みの桁。TP は発注前の RR 判定 (f_stTp) と同じ結果を受け取る\n'
    '//  (通知用の値。実際の TP 注文は約定確認後に実約定価格から決める)。risk <= 0 / TP na の数値は "-"\n'
    'float ST_PIP = 0.01\n'
    'f_stPx(float v) =>\n'
    '    na(v) ? "-" : str.tostring(v, format.mintick)\n'
    '\n'
    'f_stAlertMsg(string kind, int side, float ePx, float sl, float tp) =>\n'
    '    float risk = side == 1 ? ePx - sl : sl - ePx\n'
    '    bool  okR  = not na(risk) and risk > 0\n'
    '    float rr   = okR and not na(tp) ? (side == 1 ? tp - ePx : ePx - tp) / risk : na\n'
    '    "【" + kind + "】" + syminfo.ticker + "｜" + (side == 1 ? "LONG" : "SHORT") +\n'
    '     "\\nEntry：" + f_stPx(ePx) +\n'
    '     "\\nSL：" + f_stPx(sl) +\n'
    '     "\\nSL距離：" + (okR ? str.tostring(risk / ST_PIP, "0.0") + " pips" : "-") +\n'
    '     "\\nTP：" + (okR ? f_stPx(tp) : "-") +\n'
    '     "\\nRR：" + (na(rr) ? "-" : "1:" + str.tostring(rr, "0.##")) +\n'
    '     (kind == "仮" ? "\\n※未確定：5分足確定時に不成立になる場合あり" : "")\n')
MSG_EDITS = [
    (MSG_OLD_FN, MSG_NEW_FN),
    ("    float ePx = na\n    float sl  = na\n    if side != 0\n",
     "    float ePx = na\n    float sl  = na\n    float tpP = na     // 通知 TP: 下の RR 事前判定と同じ f_stTp の結果\n    if side != 0\n"),
    ("        if skipRef\n            side := 0\n    [side, ePx, sl]\n",
     "        tpP := tpRef\n        if skipRef\n            side := 0\n    [side, ePx, sl, tpP]\n"),
    ('                    alert(f_stAlertMsg("確定", side, stModeA ? oL : close, oSL, pQty), alert.freq_all)\n',
     '                    alert(f_stAlertMsg("確定", side, stModeA ? oL : close, oSL, tpRef), alert.freq_all)\n'),
    ("        [pSide, pPx, pSL] = f_stProvEval()\n", "        [pSide, pPx, pSL, pTP] = f_stProvEval()\n"),
    ('            alert(f_stAlertMsg("仮", pSide, pPx, pSL, pvQty), alert.freq_once_per_bar)\n',
     '            alert(f_stAlertMsg("仮", pSide, pPx, pSL, pTP), alert.freq_once_per_bar)\n'),
]

# ---- GBS-6: provisional / confirmed labels (same values as the alerts) — applied after MSG_EDITS -------------------------
#  Provisional: one label made once (var) and re-set on every realtime tick from the existing provisional evaluation
#  (shown while valid, hidden when not / on the confirmed tick / when OFF; nothing on historical bars; the provisional
#  alert's sent state is not used). Confirmed: made in the order branch next to the confirmed alert (once per order,
#  not on the fill), oldest deleted beyond the keep count. Inputs independent of the alert switches.
LBL_INPUTS = (
    'var string G_STL = "03 · Strategy Labels"\n'
    'stLblProv = input.bool(true, "仮ラベル表示 (リアルタイムの形成中5分足)", group = G_STL,\n'
    '     tooltip = "仮アラートと同じ判定・値。成立中は Entry / SL / TP / RR を更新し、不成立・確定時は消す。過去足には出さない。")\n'
    'stLblConf = input.bool(true, "確定ラベル表示 (新規 Entry を発注した確定足)", group = G_STL)\n'
    'stLblKeep = input.int(50, "確定ラベル保持数", minval = 1, maxval = 200, group = G_STL)\n'
    'color ST_LBL_PROV  = color.new(color.orange, 0)\n'
    'color ST_LBL_LONG  = color.new(color.teal, 0)\n'
    'color ST_LBL_SHORT = color.new(color.maroon, 0)\n'
    'var array<label> stConfLbls = array.new<label>()\n'
    'var label stProvLbl = label.new(bar_index, close, "", style = label.style_none, color = color(na))\n')
PROV_OLD = (
    "varip int stProvBar = na\n"
    "if stAlertProv and is5mChart and not barstate.isconfirmed and oState == 0 and stSessOK\n"
    "    if na(stProvBar) or stProvBar != bar_index\n"
    "        [pSide, pPx, pSL, pTP] = f_stProvEval()\n"
    "        float pvQty = pSide != 0 ? f_stQty(pSide, pPx, pSL) : na     // 参考値 (確定時の終値で再計算される)\n"
    "        if pSide != 0 and not na(pvQty)\n"
    "            stProvBar := bar_index\n"
    "            alert(f_stAlertMsg(\"仮\", pSide, pPx, pSL, pTP), alert.freq_once_per_bar)\n")
PROV_NEW = (
    "varip int stProvBar = na\n"
    "//  仮評価は仮アラート (未送信の足だけ) か仮ラベルが要るときに 1 回。アラートの条件・頻度・重複防止は従来どおり\n"
    "bool  stPvGate = is5mChart and not barstate.isconfirmed and oState == 0 and stSessOK\n"
    "bool  stPvA    = stAlertProv and stPvGate and (na(stProvBar) or stProvBar != bar_index)\n"
    "bool  stPvL    = stLblProv and stPvGate\n"
    "int   pSide    = 0\n"
    "float pPx      = na\n"
    "float pSL      = na\n"
    "float pTP      = na\n"
    "float pvQty    = na\n"
    "if stPvA or stPvL\n"
    "    [s0, e0, l0, t0] = f_stProvEval()\n"
    "    pSide := s0\n"
    "    pPx   := e0\n"
    "    pSL   := l0\n"
    "    pTP   := t0\n"
    "    pvQty := pSide != 0 ? f_stQty(pSide, pPx, pSL) : na     // 参考値 (確定時の終値で再計算される)\n"
    "bool  stPvOK   = pSide != 0 and not na(pvQty)\n"
    "if stPvA and stPvOK\n"
    "    stProvBar := bar_index\n"
    "    alert(f_stAlertMsg(\"仮\", pSide, pPx, pSL, pTP), alert.freq_once_per_bar)\n"
    "// 仮ラベル: リアルタイムだけ。1 個のラベルを毎 tick 設定し直す (rollback でも重複・消失しない)。仮通知の送信済み状態は使わない。\n"
    "//  不成立 / 確定 tick / 表示 OFF は非表示。履歴足では何もしない\n"
    "if barstate.isrealtime\n"
    "    if stPvL and stPvOK\n"
    "        label.set_xy(stProvLbl, bar_index, pSide == 1 ? low : high)\n"
    "        label.set_yloc(stProvLbl, pSide == 1 ? yloc.belowbar : yloc.abovebar)\n"
    "        label.set_style(stProvLbl, pSide == 1 ? label.style_label_up : label.style_label_down)\n"
    "        label.set_color(stProvLbl, ST_LBL_PROV)\n"
    "        label.set_textcolor(stProvLbl, color.black)\n"
    "        label.set_text(stProvLbl, f_stAlertMsg(\"仮\", pSide, pPx, pSL, pTP))\n"
    "    else\n"
    "        label.set_text(stProvLbl, \"\")\n"
    "        label.set_style(stProvLbl, label.style_none)\n"
    "        label.set_color(stProvLbl, color(na))\n")
LBL_EDITS = [
    ("     default_qty_value      = 1)\n", "     default_qty_value      = 1,\n     max_labels_count       = 500)\n"),
    ('     tooltip = "5分足の確定時に strategy.entry を出したときだけ (約定通知ではない)。")\n',
     '     tooltip = "5分足の確定時に strategy.entry を出したときだけ (約定通知ではない)。")\n' + LBL_INPUTS),
    ('                    alert(f_stAlertMsg("確定", side, stModeA ? oL : close, oSL, tpRef), alert.freq_all)\n',
     '                    alert(f_stAlertMsg("確定", side, stModeA ? oL : close, oSL, tpRef), alert.freq_all)\n'
     '                if stLblConf     // 確定ラベル: 発注した分岐で 1 回 (約定ではない)。確定アラートと同じ値\n'
     '                    array.push(stConfLbls, label.new(bar_index, side == 1 ? low : high, f_stAlertMsg("確定", side, stModeA ? oL : close, oSL, tpRef),\n'
     '                         yloc = side == 1 ? yloc.belowbar : yloc.abovebar, color = side == 1 ? ST_LBL_LONG : ST_LBL_SHORT,\n'
     '                         textcolor = color.white, style = side == 1 ? label.style_label_up : label.style_label_down, size = size.small))\n'
     '                    if array.size(stConfLbls) > stLblKeep\n'
     '                        label.delete(array.shift(stConfLbls))\n'),
    (PROV_OLD, PROV_NEW),
]


def _revert(text, edits):
    out = text
    for a, b in reversed(edits):
        if out is None or out.count(b) != 1:
            return None
        out = out.replace(b, a)
    return out


def strip_lbl(text):
    """reverse the GBS-6 label edits (-> the GBS-5 Strategy)."""
    return _revert(text, LBL_EDITS)


def strip_msg(text):
    """reverse the GBS-6 and GBS-5 edits (-> the GBS-4 Strategy, c07a97a)."""
    return _revert(strip_lbl(text), MSG_EDITS)


def _gbs_edits():
    out = []
    for a, b in sj.EDITS:
        if a.startswith(SKIP_PREFIX):
            continue
        if b == "":                                   # display-only label helper (removed)
            out.append((GEOM_GBS, ""))
        elif b == HEADER_JPY:
            out.append((a, HEADER_GBS))
        elif b == TITLE_JPY:
            out.append((a, TITLE_GBS))
        else:                                         # USDJPY only appears in comments of these edits
            out.append((a, b.replace("USDJPY", "GBPJPY")))
    return out + BASE_EDITS + [(ge.IMPORT_6, ge.IMPORT_GBE)] + QTY_EDITS + MSG_EDITS + LBL_EDITS   # GBS-4 size, -5 text, -6 labels


EDITS = _gbs_edits()


def visual_for_pipeline():
    """ZONE-GBPJPY with the /6 import line the shared ST-1 transform anchors on (GBJ-4 imports the GBPJPY derivative;
    the import is switched back on the Strategy by the last EDIT)."""
    v = gb.build()
    assert v.count(ge.IMPORT_GBE) == 1 and v.count(ge.IMPORT_6) == 0
    return v.replace(ge.IMPORT_GBE, ge.IMPORT_6)


def pipeline():
    """ZONE-GBPJPY -> ST-1 -> ST-2 -> ST-3 (before the strategy edits)."""
    return s3.st3_transform(s2.st2_transform(tb.st_transform(visual_for_pipeline())))


def gbs_transform(st3_text):
    out = st3_text
    for a, b in EDITS:
        assert out.count(a) == 1, a[:80]
        out = out.replace(a, b) if b else out.replace(a, "")
    return out


def strip_gbs(text):
    """exact inverse of gbs_transform (None when the text is not a GBPJPY build)."""
    out = text
    for a, b in reversed(EDITS):
        if b:
            if out.count(b) != 1:
                return None
            out = out.replace(b, a)
        else:      # removed block: it sat right after f_num
            anchor = 'f_num(float v, string fmt) =>\n    na(v) ? "-" : str.tostring(v, fmt)\n'
            if out.count(anchor) != 1:
                return None
            out = out.replace(anchor, anchor + a)
    return out


def build():
    return gbs_transform(pipeline())


if __name__ == "__main__":
    open(os.path.join(ROOT, GBS_PATH), "w", encoding="utf-8").write(__import__("cad_build").apply(build()))   # CAD-1: last layer
    print("written", GBS_PATH)
