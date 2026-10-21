"""UJ-3 / UJ-4 adaptation record — the exact edits UJ-3 (USDJPY labels / SL distance) and UJ-4 (TP / RR display) made to
older generators / fixtures.

ADAPT maps each file to the (before, after) text pairs of its UJ-3 edit, generated from the diff against 7363ef1 (the commit
before UJ-3). unadapt() reverses them all-or-nothing (a text without any UJ-3 edit is returned unchanged); xa_build.unadapt()
- the innermost link of the older fixtures' adaptation chain (uj -> bte -> xa) - calls it first, so the older "unchanged
since <rev>" checks accept these files only when they differ by exactly these edits. pine_ok() accepts the USDJPY Strategy
only when stripping UJ-4 / UJ-3 gives the file of the given revision byte for byte. This file and tests/ujl_sim.py are new
in UJ-3, tests/ujt_sim.py in UJ-4.
"""
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NEW_FILES = ("tests/uj3_adapt.py", "tests/ujl_sim.py", "tests/ujt_sim.py")
_rd = lambda p: open(os.path.join(ROOT, p), encoding="utf-8").read()


def _show(rev, path):
    return subprocess.run(["git", "-C", ROOT, "show", f"{rev}:{path}"], capture_output=True, text=True).stdout


def unadapt(path, text):
    """the text with its UJ-3 edits reverted; unchanged when none is present; None when only some are present."""
    pairs = ADAPT.get(path, [])
    if text is None or not pairs:
        return text
    hits = [text.count(b) for _, b in pairs]
    if all(h == 0 for h in hits):
        return text
    out = text
    for a, b in reversed(pairs):
        if out.count(b) != 1:
            return None
        out = out.replace(b, a)
    return out


def pine_ok(path, rev):
    """True for the USDJPY Strategy when it differs from `rev` exactly by the UJ-3 (+ UJ-4) layer."""
    import uj_build as ub
    if path != ub.STR_PATH:
        return False
    s = ub.strip_strategy3(_rd(path))
    return s is not None and s == _show(rev, path)


def ok(path, rev):
    """UJ-3 accounts for this path vs `rev` exactly: the USDJPY Strategy layer, a recorded generator / fixture edit, or a
    file new in UJ-3."""
    if path in NEW_FILES:
        return True
    if pine_ok(path, rev):
        return True
    if path in ADAPT and os.path.exists(os.path.join(ROOT, path)):
        u = unadapt(path, _rd(path))
        return u is not None and u != _rd(path) and u == _show(rev, path)
    return False


ADAPT = {'tests/bte_sim.py': [('    mod = git("diff", "--name-only", "--diff-filter=MDR", be.BASE_REV, "--").split()\n'
                       '    rest = [m for m in mod if not (be.bte_pine_ok(m, be.BASE_REV) or be.test_ok(m) or '
                       '__import__("xa_build").xa_ok(m, be.BASE_REV))]   # XA-1: exact\n'
                       '    check("BE-07 vs e1c3cea: the BTC Visual / Strategy differ exactly by the new layer, '
                       'every other changed file is a test / "\n',
                       '    mod = git("diff", "--name-only", "--diff-filter=MDR", be.BASE_REV, "--").split()\n'
                       '    rest = [m for m in mod if not (be.bte_pine_ok(m, be.BASE_REV) or be.test_ok(m) or '
                       '__import__("xa_build").xa_ok(m, be.BASE_REV)\n'
                       '                                   or __import__("uj3_adapt").pine_ok(m, be.BASE_REV))]   # '
                       'XA-1 / UJ-3: exact\n'
                       '    check("BE-07 vs e1c3cea: the BTC Visual / Strategy differ exactly by the new layer, '
                       'every other changed file is a test / "\n'),
                      ('          and not [m for m in mod if m.endswith(".pine") and m not in (bb.BTC_PATH, '
                       'sb.BTS_PATH)\n'
                       '                   and not __import__("xa_build").xa_ok(m, be.BASE_REV)], str(rest))\n'
                       '    m = S.replace("import sekine3310/ZoneEnginePracticalBTCUSD/1 as zn", "import '
                       'sekine3310/ZoneEnginePracticalGBPJPY/3 as zn")\n',
                       '          and not [m for m in mod if m.endswith(".pine") and m not in (bb.BTC_PATH, '
                       'sb.BTS_PATH)\n'
                       '                   and not __import__("xa_build").xa_ok(m, be.BASE_REV) and not '
                       '__import__("uj3_adapt").pine_ok(m, be.BASE_REV)], str(rest))\n'
                       '    m = S.replace("import sekine3310/ZoneEnginePracticalBTCUSD/1 as zn", "import '
                       'sekine3310/ZoneEnginePracticalGBPJPY/3 as zn")\n')],
 'tests/uj_build.py': [('Each strip_*() reverses its edits and must give the source back byte for byte (fixture '
                        'uj_sim).\n'
                        'UJ-2 (applied after UJ-1; strip_*2() reverses only UJ-2 -> the UJ-1 files of commit a6a275c '
                        'byte for byte): defaults\n',
                        'Each strip_*() reverses its edits and must give the source back byte for byte (fixture '
                        'uj_sim).\n'
                        'UJ-3 (Strategy only, applied after UJ-2; strip_strategy3() -> the UJ-2 Strategy of '
                        'e1c3cea): display / notification only -\n'
                        'provisional / confirmed Entry labels ported from the GBPJPY Strategy (GBS-6) and the SL '
                        'distance (pips) in both alert texts.\n'
                        'UJ-4 (Strategy only, applied after UJ-3; strip_strategy4() -> the UJ-3 Strategy of '
                        'ab9820f): TP / RR in the provisional /\n'
                        'confirmed labels and alert texts, the GBPJPY method (the existing pre-order f_stTp result), '
                        'display / notification only.\n'
                        'UJ-5 (Strategy only, applied after UJ-4; strip_strategy5() -> the UJ-4 Strategy of '
                        '89bc82b): the confirmed alert at most once\n'
                        'per 5M bar (varip bar key), notification only.\n'
                        'UJ-2 (applied after UJ-1; strip_*2() reverses only UJ-2 -> the UJ-1 files of commit a6a275c '
                        'byte for byte): defaults\n'),
                       ('\ndef _apply(src, edits):\n',
                        '\n'
                        '# ---- UJ-3: Entry labels (provisional / confirmed) + SL distance in the alert text '
                        '(Strategy only; after UJ-2) ------------\n'
                        '#  Display / notification only. The label layer is the GBPJPY one (gbs_build LBL_EDITS / '
                        'GBS-6: same inputs, colours,\n'
                        '#  positions, one provisional label re-set per realtime tick, confirmed labels made in the '
                        'order branch with the keep\n'
                        '#  limit, max_labels_count 500), adapted to the USDJPY text (4 arguments, no TP) and to the '
                        'USDJPY provisional validity\n'
                        '#  (pSide != 0: the provisional alert condition is unchanged). The alert text gets one '
                        'line, SL距離 = |Entry - SL| / 0.01\n'
                        '#  (pips, 0.0); the provisional text uses the reference Entry of the forming bar, the '
                        'confirmed text the existing order\n'
                        '#  reference (A limit / B, C, D close). Alert conditions / frequencies, orders, SL / TP, '
                        'sizing unchanged.\n'
                        '#  strip_strategy3() reverses only these -> the UJ-2 Strategy (e1c3cea) byte for byte.\n'
                        'MSG3_OLD = (\n'
                        "    'f_stAlertMsg(string kind, int side, float ePx, float sl) =>\\n'\n"
                        '    \'    "【" + kind + " " + (side == 1 ? "LONG" : "SHORT") + "】" +\\n\'\n'
                        '    \'     "\\\\n" + syminfo.tickerid +\\n\'\n'
                        '    \'     "\\\\nMode: " + stMode +\\n\'\n'
                        '    \'     "\\\\nE: " + f_num(ePx, "#.000") + (stModeA ? " (指値)" : " (参考。次足始値で成行)") +\\n\'\n'
                        '    \'     "\\\\nSL: " + f_num(sl, "#.000") +\\n\')\n'
                        'MSG3_NEW = (\n'
                        "    '//  UJ-3: SL距離 (pips) = |Entry - SL| ÷ 0.01 (USDJPY: 0.01 円 = 1 pip、小数 1 桁)。仮は形成中の足の参考 "
                        "Entry、\\n'\n"
                        '    \'//  確定は発注時の参照価格 (A: 指値 / B, C, D: 確定足の終値) から。Entry / SL が na なら "-"\\n\'\n'
                        "    'float ST_PIP = 0.01\\n'\n"
                        "    'f_stAlertMsg(string kind, int side, float ePx, float sl) =>\\n'\n"
                        "    '    float slPips = na(ePx) or na(sl) ? na : math.abs(ePx - sl) / ST_PIP\\n'\n"
                        '    \'    "【" + kind + " " + (side == 1 ? "LONG" : "SHORT") + "】" +\\n\'\n'
                        '    \'     "\\\\n" + syminfo.tickerid +\\n\'\n'
                        '    \'     "\\\\nMode: " + stMode +\\n\'\n'
                        '    \'     "\\\\nE: " + f_num(ePx, "#.000") + (stModeA ? " (指値)" : " (参考。次足始値で成行)") +\\n\'\n'
                        '    \'     "\\\\nSL: " + f_num(sl, "#.000") +\\n\'\n'
                        '    \'     "\\\\nSL距離: " + (na(slPips) ? "-" : str.tostring(slPips, "0.0") + " pips") '
                        "+\\n')\n"
                        'PROV3_OLD = (\n'
                        '    "varip int stProvBar = na\\n"\n'
                        '    "if stAlertProv and is5mChart and not barstate.isconfirmed and oState == 0 and '
                        'stSessOK\\n"\n'
                        '    "    if na(stProvBar) or stProvBar != bar_index\\n"\n'
                        '    "        [pSide, pPx, pSL] = f_stProvEval()\\n"\n'
                        '    "        if pSide != 0\\n"\n'
                        '    "            stProvBar := bar_index\\n"\n'
                        '    "            alert(f_stAlertMsg(\\"仮\\", pSide, pPx, pSL), '
                        'alert.freq_once_per_bar)\\n")\n'
                        'PROV3_NEW = (\n'
                        '    "varip int stProvBar = na\\n"\n'
                        '    "//  UJ-3: 仮評価は仮アラート (未送信の足だけ) か仮ラベルが要るときに 1 回。アラートの条件・頻度・重複防止は従来どおり\\n"\n'
                        '    "bool  stPvGate = is5mChart and not barstate.isconfirmed and oState == 0 and '
                        'stSessOK\\n"\n'
                        '    "bool  stPvA    = stAlertProv and stPvGate and (na(stProvBar) or stProvBar != '
                        'bar_index)\\n"\n'
                        '    "bool  stPvL    = stLblProv and stPvGate\\n"\n'
                        '    "int   pSide    = 0\\n"\n'
                        '    "float pPx      = na\\n"\n'
                        '    "float pSL      = na\\n"\n'
                        '    "if stPvA or stPvL\\n"\n'
                        '    "    [s0, e0, l0] = f_stProvEval()\\n"\n'
                        '    "    pSide := s0\\n"\n'
                        '    "    pPx   := e0\\n"\n'
                        '    "    pSL   := l0\\n"\n'
                        '    "bool  stPvOK   = pSide != 0\\n"\n'
                        '    "if stPvA and stPvOK\\n"\n'
                        '    "    stProvBar := bar_index\\n"\n'
                        '    "    alert(f_stAlertMsg(\\"仮\\", pSide, pPx, pSL), alert.freq_once_per_bar)\\n"\n'
                        '    "// 仮ラベル: リアルタイムだけ。1 個のラベルを毎 tick 設定し直す (rollback でも重複・消失しない)。仮通知の送信済み状態は使わない。\\n"\n'
                        '    "//  不成立 / 確定 tick / 表示 OFF は非表示。履歴足では何もしない\\n"\n'
                        '    "if barstate.isrealtime\\n"\n'
                        '    "    if stPvL and stPvOK\\n"\n'
                        '    "        label.set_xy(stProvLbl, bar_index, pSide == 1 ? low : high)\\n"\n'
                        '    "        label.set_yloc(stProvLbl, pSide == 1 ? yloc.belowbar : yloc.abovebar)\\n"\n'
                        '    "        label.set_style(stProvLbl, pSide == 1 ? label.style_label_up : '
                        'label.style_label_down)\\n"\n'
                        '    "        label.set_color(stProvLbl, ST_LBL_PROV)\\n"\n'
                        '    "        label.set_textcolor(stProvLbl, color.black)\\n"\n'
                        '    "        label.set_text(stProvLbl, f_stAlertMsg(\\"仮\\", pSide, pPx, pSL))\\n"\n'
                        '    "    else\\n"\n'
                        '    "        label.set_text(stProvLbl, \\"\\")\\n"\n'
                        '    "        label.set_style(stProvLbl, label.style_none)\\n"\n'
                        '    "        label.set_color(stProvLbl, color(na))\\n")\n'
                        'LBL_INPUTS_UJ = gs.LBL_INPUTS.replace("成立中は Entry / SL / TP / RR を更新し", "成立中は Entry / SL / '
                        'SL距離を更新し")\n'
                        'CONF3_OLD = \'                    alert(f_stAlertMsg("確定", side, stModeA ? oL : close, '
                        "oSL), alert.freq_all)\\n'\n"
                        'CONF3_NEW = (\n'
                        '    CONF3_OLD +\n'
                        "    '                if stLblConf     // 確定ラベル: 発注した分岐で 1 回 (約定ではない)。確定アラートと同じ値\\n'\n"
                        "    '                    array.push(stConfLbls, label.new(bar_index, side == 1 ? low : "
                        'high, f_stAlertMsg("確定", side, stModeA ? oL : close, oSL),\\n\'\n'
                        "    '                         yloc = side == 1 ? yloc.belowbar : yloc.abovebar, color = "
                        "side == 1 ? ST_LBL_LONG : ST_LBL_SHORT,\\n'\n"
                        "    '                         textcolor = color.white, style = side == 1 ? "
                        "label.style_label_up : label.style_label_down, size = size.small))\\n'\n"
                        "    '                    if array.size(stConfLbls) > stLblKeep\\n'\n"
                        "    '                        label.delete(array.shift(stConfLbls))\\n')\n"
                        'STRATEGY_EDITS3 = [\n'
                        '    ("header",\n'
                        '     "//  反対 Zone TP OFF、建値移動 OFF (Trigger 値は OFF 時のまま)。\\n",\n'
                        '     "//  反対 Zone TP OFF、建値移動 OFF (Trigger 値は OFF 時のまま)。\\n"\n'
                        '     "//  UJ-3 (表示・通知のみ): 仮 / 確定 Entry ラベル (GBPJPY 版と同じ仕様) と、仮 / 確定アラートの SL距離 (pips = '
                        '|Entry - SL| ÷ 0.01)。\\n"\n'
                        '     "//  アラートの発火条件・頻度、Entry / SL / TP / 数量 / 注文・約定の処理は変えない。\\n"),\n'
                        '    ("label", "     default_qty_value      = 1)\\n", "     default_qty_value      = '
                        '1,\\n     max_labels_count       = 500)\\n"),\n'
                        '    ("label",\n'
                        '     \'     tooltip = "5分足の確定時に strategy.entry を出したときだけ (約定通知ではない)。")\\n\',\n'
                        '     \'     tooltip = "5分足の確定時に strategy.entry を出したときだけ (約定通知ではない)。")\\n\' + '
                        'LBL_INPUTS_UJ),\n'
                        '    ("msg", MSG3_OLD, MSG3_NEW),\n'
                        '    ("label", CONF3_OLD, CONF3_NEW),\n'
                        '    ("label", PROV3_OLD, PROV3_NEW),\n'
                        ']\n'
                        '\n'
                        '\n'
                        '# ---- UJ-4: TP / RR in the labels and alert texts (Strategy only; after UJ-3) '
                        '---------------------------------------------\n'
                        '#  Display / notification only, the GBPJPY method (gbs_build MSG_EDITS / GBS-5): TP = the '
                        'result of the existing pre-order\n'
                        '#  f_stTp call for the same reference price (fixed RR / opposite-zone TP / its fallback) - '
                        'the confirmed text reuses tpRef of\n'
                        '#  the order branch, the provisional text the tp f_stProvEval already computes (returned as '
                        'a 4th value); RR = profit-side\n'
                        '#  TP distance / |Entry - SL| ("1:x", up to 2 decimals); invalid risk / TP -> "-". The '
                        'USDJPY lines (Mode, E, SL, SL距離)\n'
                        '#  stay; TP / RR follow SL距離 in the GBPJPY order. The confirmed TP is the planned value at '
                        'the order reference (the TP\n'
                        '#  order is still set from the actual fill after the fill), so the confirmed line keeps the '
                        'former "約定確認後に設定" meaning.\n'
                        '#  No order / alert / label condition changes. strip_strategy4() reverses only these -> the '
                        'UJ-3 Strategy (ab9820f).\n'
                        'MSG4_OLD = (\n'
                        "    'f_stAlertMsg(string kind, int side, float ePx, float sl) =>\\n'\n"
                        "    '    float slPips = na(ePx) or na(sl) ? na : math.abs(ePx - sl) / ST_PIP\\n')\n"
                        'MSG4_NEW = (\n'
                        "    '//  UJ-4: TP は発注前の RR 判定 (f_stTp) と同じ結果を受け取る (通知用の値。実際の TP 注文は約定確認後に実約定価格から決める)。\\n'\n"
                        '    \'//  RR = 利益方向の TP 距離 ÷ Entry から SL までの距離 (1:x、小数 2 桁まで)。risk <= 0 / TP na は "-"\\n\'\n'
                        "    'f_stAlertMsg(string kind, int side, float ePx, float sl, float tp) =>\\n'\n"
                        "    '    float slPips = na(ePx) or na(sl) ? na : math.abs(ePx - sl) / ST_PIP\\n'\n"
                        "    '    float risk   = side == 1 ? ePx - sl : sl - ePx\\n'\n"
                        "    '    bool  okR    = not na(risk) and risk > 0\\n'\n"
                        "    '    float rr     = okR and not na(tp) ? (side == 1 ? tp - ePx : ePx - tp) / risk : "
                        "na\\n')\n"
                        'TAIL4_OLD = \'     (kind == "仮" ? "\\\\n※未確定: 5分足の確定時に不成立になる場合あり" : "\\\\nTP: '
                        '約定確認後に設定")\\n\'\n'
                        'TAIL4_NEW = (\n'
                        '    \'     "\\\\nTP: " + (okR ? f_num(tp, "#.000") : "-") + (kind == "仮" ? "" : " '
                        '(発注時の予定値。最終 TP は約定確認後に実約定価格から設定)") +\\n\'\n'
                        '    \'     "\\\\nRR: " + (na(rr) ? "-" : "1:" + str.tostring(rr, "0.##")) +\\n\'\n'
                        '    \'     (kind == "仮" ? "\\\\n※未確定: 5分足の確定時に不成立になる場合あり" : "")\\n\')\n'
                        'STRATEGY_EDITS4 = [\n'
                        '    ("header",\n'
                        '     "//  アラートの発火条件・頻度、Entry / SL / TP / 数量 / 注文・約定の処理は変えない。\\n",\n'
                        '     "//  アラートの発火条件・頻度、Entry / SL / TP / 数量 / 注文・約定の処理は変えない。\\n"\n'
                        '     "//  UJ-4 (表示・通知のみ): ラベル / アラートに TP・RR (GBPJPY 版と同じ方式: 発注前の f_stTp の結果、RR 1:x)。確定の TP '
                        'は\\n"\n'
                        '     "//  発注時の予定値 (最終 TP は約定確認後に実約定価格から設定)。売買・発注・アラート / ラベルの条件は変えない。\\n"),\n'
                        '    ("msg", MSG4_OLD, MSG4_NEW),\n'
                        '    ("msg", TAIL4_OLD, TAIL4_NEW),\n'
                        '    ("prov",\n'
                        '     "    float ePx = na\\n    float sl  = na\\n    if side != 0\\n",\n'
                        '     "    float ePx = na\\n    float sl  = na\\n    float tpP = na     // 通知 TP: 下の RR '
                        '事前判定と同じ f_stTp の結果\\n    if side != 0\\n"),\n'
                        '    ("prov",\n'
                        '     "        if skipRef\\n            side := 0\\n    [side, ePx, sl]\\n",\n'
                        '     "        tpP := tpRef\\n        if skipRef\\n            side := 0\\n    [side, ePx, '
                        'sl, tpP]\\n"),\n'
                        '    ("conf",\n'
                        '     \'                    alert(f_stAlertMsg("確定", side, stModeA ? oL : close, oSL), '
                        "alert.freq_all)\\n',\n"
                        '     \'                    alert(f_stAlertMsg("確定", side, stModeA ? oL : close, oSL, '
                        "tpRef), alert.freq_all)\\n'),\n"
                        '    ("conf",\n'
                        "     '                    array.push(stConfLbls, label.new(bar_index, side == 1 ? low : "
                        'high, f_stAlertMsg("確定", side, stModeA ? oL : close, oSL),\\n\',\n'
                        "     '                    array.push(stConfLbls, label.new(bar_index, side == 1 ? low : "
                        'high, f_stAlertMsg("確定", side, stModeA ? oL : close, oSL, tpRef),\\n\'),\n'
                        '    ("prov", "float pSL      = na\\n", "float pSL      = na\\nfloat pTP      = na\\n"),\n'
                        '    ("prov", "    [s0, e0, l0] = f_stProvEval()\\n", "    [s0, e0, l0, t0] = '
                        'f_stProvEval()\\n"),\n'
                        '    ("prov", "    pSL   := l0\\n", "    pSL   := l0\\n    pTP   := t0\\n"),\n'
                        '    ("prov",\n'
                        '     \'    alert(f_stAlertMsg("仮", pSide, pPx, pSL), alert.freq_once_per_bar)\\n\',\n'
                        '     \'    alert(f_stAlertMsg("仮", pSide, pPx, pSL, pTP), alert.freq_once_per_bar)\\n\'),\n'
                        '    ("prov",\n'
                        '     \'        label.set_text(stProvLbl, f_stAlertMsg("仮", pSide, pPx, pSL))\\n\',\n'
                        '     \'        label.set_text(stProvLbl, f_stAlertMsg("仮", pSide, pPx, pSL, pTP))\\n\'),\n'
                        '    ("label",\n'
                        '     "成立中は Entry / SL / SL距離を更新し",\n'
                        '     "成立中は Entry / SL / SL距離 / TP / RR を更新し"),\n'
                        ']\n'
                        '\n'
                        '\n'
                        '# ---- UJ-5: confirmed alert at most once per 5M bar (Strategy only; after UJ-4) '
                        '------------------------------------------\n'
                        '#  Notification only. The confirmed alert() sits in the order branch of the confirmed-bar '
                        'block (one call per execution). If\n'
                        "#  TradingView executes the same bar's confirmed update again in realtime, var state "
                        '(oState, oSeq ...) is rolled back to the\n'
                        "#  previous bar's committed values, so the order branch runs again and alert() - a side "
                        'effect that is never rolled back -\n'
                        '#  is sent a second time with the same text. A varip bar key (time of the 5M bar) survives '
                        'the rollback: the confirmed alert\n'
                        '#  is sent only when it was not yet sent for this bar. Its own state (independent of the '
                        'provisional stProvBar); a new entry\n'
                        '#  on another bar has another time and is not suppressed. The order, the label (rolled back '
                        '/ re-made with the execution)\n'
                        '#  and alert.freq_all are unchanged (freq_once_per_bar is not used: it would also count the '
                        'provisional alert of the same\n'
                        '#  bar). strip_strategy5() reverses only these -> the UJ-4 Strategy (89bc82b).\n'
                        'STRATEGY_EDITS5 = [\n'
                        '    ("header",\n'
                        '     "//  発注時の予定値 (最終 TP は約定確認後に実約定価格から設定)。売買・発注・アラート / ラベルの条件は変えない。\\n",\n'
                        '     "//  発注時の予定値 (最終 TP は約定確認後に実約定価格から設定)。売買・発注・アラート / ラベルの条件は変えない。\\n"\n'
                        '     "//  UJ-5 (通知のみ): 確定アラートは同じ 5分足で最大 1 回 (varip の足キー stConfBar。同じ足の確定更新が再計算されても\\n"\n'
                        '     "//  再送しない)。別の足の新規 Entry は抑制しない。仮アラートの stProvBar とは独立。発注・ラベル・freq_all は変えない。\\n"),\n'
                        '    ("dedup",\n'
                        '     "var int    oClosed = 0\\n",\n'
                        '     "var int    oClosed = 0\\n"\n'
                        '     "varip int  stConfBar = na     // UJ-5: 確定アラートを送った 5分足の time。varip = 同じ足の再計算 '
                        '(rollback) でも残る\\n"),\n'
                        '    ("dedup",\n'
                        '     "                if stAlertConf\\n"\n'
                        '     "                    alert(f_stAlertMsg(\\"確定\\", side, stModeA ? oL : close, oSL, '
                        'tpRef), alert.freq_all)\\n",\n'
                        '     "                if stAlertConf and (na(stConfBar) or stConfBar != time)     // UJ-5: '
                        '同じ 5分足では最大 1 回\\n"\n'
                        '     "                    stConfBar := time\\n"\n'
                        '     "                    alert(f_stAlertMsg(\\"確定\\", side, stModeA ? oL : close, oSL, '
                        'tpRef), alert.freq_all)\\n"),\n'
                        ']\n'
                        '\n'
                        '\n'
                        'def _apply(src, edits):\n'),
                       ('\ndef build_strategy():\n',
                        '\n'
                        'def build_strategy2():\n'
                        '    """UJ-1 + UJ-2 (commit e1c3cea)."""\n'
                        '    return _apply(build_strategy1(), STRATEGY_EDITS2)\n'
                        '\n'
                        '\n'
                        'def build_strategy3():\n'
                        '    """UJ-1 + UJ-2 + UJ-3 (commit ab9820f)."""\n'
                        '    return _apply(build_strategy2(), STRATEGY_EDITS3)\n'
                        '\n'
                        '\n'
                        'def build_strategy4():\n'
                        '    """UJ-1 .. UJ-4 (commit 89bc82b)."""\n'
                        '    return _apply(build_strategy3(), STRATEGY_EDITS4)\n'
                        '\n'
                        '\n'
                        'def build_strategy():\n'),
                       ('def build_strategy():\n    return _apply(build_strategy1(), STRATEGY_EDITS2)\n\n',
                        'def build_strategy():\n    return _apply(build_strategy4(), STRATEGY_EDITS5)\n\n'),
                       ('\ndef strip_strategy(t):\n',
                        '\n'
                        'def strip_strategy5(t):\n'
                        '    """reverse only the UJ-5 confirmed-alert dedup (-> the UJ-4 Strategy of 89bc82b byte '
                        'for byte)."""\n'
                        '    return _revert(t, STRATEGY_EDITS5)\n'
                        '\n'
                        '\n'
                        'def strip_strategy4(t):\n'
                        '    """reverse the UJ-5 dedup when present (all or nothing) and the UJ-4 TP / RR display '
                        '(-> the UJ-3 Strategy of ab9820f\n'
                        '    byte for byte)."""\n'
                        '    if t is not None and STRATEGY_EDITS5[0][2] in t:     # UJ-5 header present -> the whole '
                        'UJ-5 layer must revert\n'
                        '        t = strip_strategy5(t)\n'
                        '    return _revert(t, STRATEGY_EDITS4)\n'
                        '\n'
                        '\n'
                        'def strip_strategy3(t):\n'
                        '    """reverse the UJ-4 TP / RR display when present (all or nothing) and the UJ-3 labels / '
                        'SL distance (-> the UJ-2\n'
                        '    Strategy byte for byte). A text with only part of the UJ-4 edits gives None."""\n'
                        '    if t is not None and STRATEGY_EDITS4[0][2] in t:     # UJ-4 header present -> the whole '
                        'UJ-4 layer must revert\n'
                        '        t = strip_strategy4(t)\n'
                        '    return _revert(t, STRATEGY_EDITS3)\n'
                        '\n'
                        '\n'
                        'def strip_strategy(t):\n'),
                       ('def strip_strategy(t):\n'
                        '    """reverse UJ-2 and UJ-1 (-> the pre-UJ Strategy of 3568c05)."""\n'
                        '    return _revert(strip_strategy2(t), STRATEGY_EDITS)\n'
                        '\n',
                        'def strip_strategy(t):\n'
                        '    """reverse UJ-5, UJ-4, UJ-3, UJ-2 and UJ-1 (-> the pre-UJ Strategy of 3568c05)."""\n'
                        '    return _revert(strip_strategy2(strip_strategy3(t)), STRATEGY_EDITS)\n'
                        '\n')],
 'tests/uj_sim.py': [('V0, S0 = ub.base(ub.VIS_PATH), ub.base(ub.STR_PATH)\n'
                      'FV, FS = rd(ub.VIS_PATH), rd(ub.STR_PATH)\n'
                      'UJ1 = "a6a275c"\n',
                      'V0, S0 = ub.base(ub.VIS_PATH), ub.base(ub.STR_PATH)\n'
                      'FV, FS3 = rd(ub.VIS_PATH), rd(ub.STR_PATH)\n'
                      'FS = ub.strip_strategy3(FS3) or ""     # UJ-3: labels / SL distance reverted exactly (pinned '
                      'in ujl_sim)\n'
                      'UJ1 = "a6a275c"\n'),
                     ('    check("US-03 Visual / Strategy rebuild from their pre-UJ-1 text (3568c05) and strip back '
                      'byte for byte",\n'
                      '          ub.build_visual1() == V and ub.build_strategy1() == S and ub.build_visual() == FV '
                      'and ub.build_strategy() == FS\n'
                      '          and ub.strip_visual(FV) == V0 and ub.strip_strategy(FS) == S0\n'
                      '          and all(k in ("header", "name", "import", "default", "size") for k, _, _ in '
                      'ub.ENGINE_EDITS + ub.VISUAL_EDITS + ub.STRATEGY_EDITS))\n',
                      '    check("US-03 Visual / Strategy rebuild from their pre-UJ-1 text (3568c05) and strip back '
                      'byte for byte",\n'
                      '          ub.build_visual1() == V and ub.build_strategy1() == S and ub.build_visual() == FV '
                      'and ub.build_strategy2() == FS\n'
                      '          and ub.strip_visual(FV) == V0 and ub.strip_strategy(FS3) == S0\n'
                      '          and all(k in ("header", "name", "import", "default", "size") for k, _, _ in '
                      'ub.ENGINE_EDITS + ub.VISUAL_EDITS + ub.STRATEGY_EDITS))\n'),
                     ('          V == git("show", f"{UJ1}:{ub.VIS_PATH}") and S == git("show", '
                      'f"{UJ1}:{ub.STR_PATH}")\n'
                      '          and EU == git("show", f"{UJ1}:{ub.ENG_PATH}") and ub.build_visual() == FV and '
                      'ub.build_strategy() == FS\n'
                      '          and all(k in ("header", "default") for k, _, _ in ub.VISUAL_EDITS2 + '
                      'ub.STRATEGY_EDITS2)\n',
                      '          V == git("show", f"{UJ1}:{ub.VIS_PATH}") and S == git("show", '
                      'f"{UJ1}:{ub.STR_PATH}")\n'
                      '          and EU == git("show", f"{UJ1}:{ub.ENG_PATH}") and ub.build_visual() == FV and '
                      'ub.build_strategy2() == FS\n'
                      '          and all(k in ("header", "default") for k, _, _ in ub.VISUAL_EDITS2 + '
                      'ub.STRATEGY_EDITS2)\n')],
 'tests/xa_sim.py': [('    mod = git("diff", "--name-only", "--diff-filter=MDR", xb.BASE_REV, "--").split()\n'
                      '    rest = [m for m in mod if not (xb.xa_ok(m, xb.BASE_REV) or xb.test_ok(m))]\n'
                      '    check("XS-07 vs f253890: ZONE-P / ZONE-ST differ exactly by XA-1 (+ XA-2 on ZONE-ST); '
                      'every other changed file is a test / generator whose edits "\n',
                      '    mod = git("diff", "--name-only", "--diff-filter=MDR", xb.BASE_REV, "--").split()\n'
                      '    rest = [m for m in mod if not (xb.xa_ok(m, xb.BASE_REV) or xb.test_ok(m) or '
                      '__import__("uj3_adapt").pine_ok(m, xb.BASE_REV))]   # UJ-3: exact\n'
                      '    check("XS-07 vs f253890: ZONE-P / ZONE-ST differ exactly by XA-1 (+ XA-2 on ZONE-ST); '
                      'every other changed file is a test / generator whose edits "\n'),
                     ('          "are recorded exactly in xa_build.TEST_ADAPT; other Pine files and Engines '
                      'untouched",\n'
                      '          set(xb.XA_FILES) <= set(mod) and not rest and not [m for m in mod if '
                      'm.endswith(".pine") and m not in xb.XA_FILES],\n'
                      '          str(rest))\n',
                      '          "are recorded exactly in xa_build.TEST_ADAPT; other Pine files and Engines '
                      'untouched",\n'
                      '          set(xb.XA_FILES) <= set(mod) and not rest and not [m for m in mod if '
                      'm.endswith(".pine") and m not in xb.XA_FILES\n'
                      '                                                           and not '
                      '__import__("uj3_adapt").pine_ok(m, xb.BASE_REV)],\n'
                      '          str(rest))\n'),
                     ('          and re.findall(r"^import .*$", S2, re.M) == ["import '
                      'sekine3310/ZoneEnginePractical/6 as zn"])\n'
                      '    mod = git("diff", "--name-only", XA1_REV, "--").split()\n'
                      '    check("XQ-07 vs 2732772: only ZoneStrategyXAU.pine, ZoneVisualPractical.pine (exactly '
                      'XA-3) and tests/xa_build.py / "\n',
                      '          and re.findall(r"^import .*$", S2, re.M) == ["import '
                      'sekine3310/ZoneEnginePractical/6 as zn"])\n'
                      '    mod = [m for m in git("diff", "--name-only", XA1_REV, "--").split() if not '
                      '__import__("uj3_adapt").ok(m, XA1_REV)]   # UJ-3: exact\n'
                      '    check("XQ-07 vs 2732772: only ZoneStrategyXAU.pine, ZoneVisualPractical.pine (exactly '
                      'XA-3) and tests/xa_build.py / "\n'),
                     ('          and "Flip 5 USD" in hdr and "SL Buffer 1.5" in SF[:SF.index("//@version=5")])\n'
                      '    mod = git("diff", "--name-only", XA2_REV, "--").split()\n'
                      '    check("XT-07 vs 69e6f0c: only the two Gold Pine files (exactly XA-3) and '
                      'tests/xa_build.py / xa_sim.py change; other "\n',
                      '          and "Flip 5 USD" in hdr and "SL Buffer 1.5" in SF[:SF.index("//@version=5")])\n'
                      '    mod = [m for m in git("diff", "--name-only", XA2_REV, "--").split() if not '
                      '__import__("uj3_adapt").ok(m, XA2_REV)]   # UJ-3: exact\n'
                      '    check("XT-07 vs 69e6f0c: only the two Gold Pine files (exactly XA-3) and '
                      'tests/xa_build.py / xa_sim.py change; other "\n')],
 'tests/xae_sim.py': [('    mod -= {"tests/__pycache__/"}\n'
                       '    allowed = {xb.VIS_PATH, xb.STR_PATH, xb.ENG_PATH, "tests/xa_build.py", '
                       '"tests/xa_sim.py", "tests/xae_sim.py"}\n',
                       '    mod -= {"tests/__pycache__/"}\n'
                       '    mod = {m for m in mod if not __import__("uj3_adapt").ok(m, PREV)}     # UJ-3 (USDJPY '
                       'labels): exact\n'
                       '    allowed = {xb.VIS_PATH, xb.STR_PATH, xb.ENG_PATH, "tests/xa_build.py", '
                       '"tests/xa_sim.py", "tests/xae_sim.py"}\n'),
                      ('          mod <= allowed and {xb.VIS_PATH, xb.STR_PATH, xb.ENG_PATH} <= mod\n'
                       '          and not [p for p in others if rd(p) != xb.show(PREV, p)], str(sorted(mod - '
                       'allowed)))\n'
                       '    hdr = V[:V.index("//@version=5")] + S[:S.index("//@version=5")]\n',
                       '          mod <= allowed and {xb.VIS_PATH, xb.STR_PATH, xb.ENG_PATH} <= mod\n'
                       '          and not [p for p in others if rd(p) != xb.show(PREV, p) and not '
                       '__import__("uj3_adapt").pine_ok(p, PREV)], str(sorted(mod - allowed)))\n'
                       '    hdr = V[:V.index("//@version=5")] + S[:S.index("//@version=5")]\n')]}
