"""UJ-3 adaptation record — the exact edits UJ-3 (USDJPY Strategy labels / SL distance) made to older generators / fixtures.

ADAPT maps each file to the (before, after) text pairs of its UJ-3 edit, generated from the diff against 7363ef1 (the commit
before UJ-3). unadapt() reverses them all-or-nothing (a text without any UJ-3 edit is returned unchanged); xa_build.unadapt()
- the innermost link of the older fixtures' adaptation chain (uj -> bte -> xa) - calls it first, so the older "unchanged
since <rev>" checks accept these files only when they differ by exactly these edits. pine_ok() accepts the USDJPY Strategy
only when stripping UJ-3 gives the file of the given revision byte for byte. This file and tests/ujl_sim.py are new in UJ-3.
"""
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NEW_FILES = ("tests/uj3_adapt.py", "tests/ujl_sim.py")
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
    """True for the USDJPY Strategy when it differs from `rev` exactly by the UJ-3 layer."""
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
                        'def _apply(src, edits):\n'),
                       ('\ndef build_strategy():\n',
                        '\n'
                        'def build_strategy2():\n'
                        '    """UJ-1 + UJ-2 (commit e1c3cea)."""\n'
                        '    return _apply(build_strategy1(), STRATEGY_EDITS2)\n'
                        '\n'
                        '\n'
                        'def build_strategy():\n'),
                       ('def build_strategy():\n    return _apply(build_strategy1(), STRATEGY_EDITS2)\n\n',
                        'def build_strategy():\n    return _apply(build_strategy2(), STRATEGY_EDITS3)\n\n'),
                       ('\ndef strip_strategy(t):\n',
                        '\n'
                        'def strip_strategy3(t):\n'
                        '    """reverse only the UJ-3 labels / SL distance (-> the UJ-2 Strategy byte for byte)."""\n'
                        '    return _revert(t, STRATEGY_EDITS3)\n'
                        '\n'
                        '\n'
                        'def strip_strategy(t):\n'),
                       ('def strip_strategy(t):\n'
                        '    """reverse UJ-2 and UJ-1 (-> the pre-UJ Strategy of 3568c05)."""\n'
                        '    return _revert(strip_strategy2(t), STRATEGY_EDITS)\n'
                        '\n',
                        'def strip_strategy(t):\n'
                        '    """reverse UJ-3, UJ-2 and UJ-1 (-> the pre-UJ Strategy of 3568c05)."""\n'
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
