"""SX-2 — the final Gold XA-16 .. XA-19 SATS timing features rolled out to the BTCUSD / USDJPY / GBPJPY / EURUSD / GBPUSD
Strategies (after SX-1; Strategy only; Gold / Engines / Visuals / imports unchanged).

Each Strategy == its file at BASE_REV (= the SX-1 files of b59d621) + EDITS(cur) (exact replacements). Ported from the Gold
XA-19 Strategy of GOLD_REV (the history block and the immediate block are taken from that pinned file, so they are the
final XA-19 code, not the XA-16 / XA-17 intermediates):
  - inputs: immediate entry (OFF), immediate contact -> rebound Nc (1), immediate rebound -> Zone Nz (1), pull-side contact
    expiry (OFF), pull-side contact -> rebound N (1); all counts min 0 / step 1 / independent;
  - the rebound history (contact record by Nc with the XA-18 first-q origin, candidates (q, e, line) by Nz, latest e with
    0 <= t - e <= Nz and 0 <= e - q <= Nc, LINE1 -> LINE2 -> STB), the immediate market order at the SATS prep point
    (P0 / SL0 / TP0 of the prep, f_stQty(side, close, SL0), this bar's filter / SL-TP side), the pull-side contact expiry
    (touch record + held line only; the wait / its clock unchanged) and the per-prep touch count;
  - per-symbol differences (stated): the near distance is the symbol's stSatsNearPx (pips x unit / USD for BTC); the history
    state (records, candidates) is written only on confirmed bars (calc_on_every_tick = true: forming ticks only read it;
    a rebound of the forming bar is taken first in the pick, the same result as Gold's push-then-pick on the confirmed bar);
    the immediate order sends the existing confirmed alert / label (stConfBar guard); the read-only provisional evaluation
    covers the pull-side contact expiry while waiting and, with the immediate entry ON, an immediate order of the forming bar
    before a wait (f_stProvEval's signal + the same immediate conditions + both size checks). A plain wait prep sends nothing.
strip(path, text) reverses the edits exactly (None when not exact); unapply() leaves a text without them unchanged.
"""
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_REV = "32cc570"
GOLD_REV = "32cc570"
GOLD_PATH = "ZoneStrategyXAU.pine"
PATHS = {"BTCUSD": "ZoneStrategyBTCUSD.pine", "USDJPY": "ZoneStrategyUSDJPY.pine", "GBPJPY": "ZoneStrategyGBPJPY.pine",
         "EURUSD": "ZoneStrategyEURUSD.pine", "GBPUSD": "ZoneStrategyGBPUSD.pine"}
FILES = tuple(PATHS.values())
BY_PATH = {v: k for k, v in PATHS.items()}


def show(rev, path):
    return subprocess.run(["git", "-C", ROOT, "show", f"{rev}:{path}"], capture_output=True, text=True).stdout


_GOLD = None


def gold():
    global _GOLD
    if _GOLD is None:
        _GOLD = show(GOLD_REV, GOLD_PATH)
    return _GOLD


def _seg(text, start, end_incl):
    i = text.index(start)
    j = text.index(end_incl, i) + len(end_incl)
    return text[i:j]


def _inputs():
    g = _seg(gold(), "stSatsNow = input.bool(false,", '"反発した足で発注条件を確認する (反発後にさらに待つことはしない)。即時側の本数とは独立。")\n')
    return g.replace("XA-16 比較用 (初期 OFF)。", "SX-2 比較用 (初期 OFF・ゴールド XA-16〜XA-19 と同じ意味)。").replace(
        "XA-17 比較用 (初期 OFF = 従来の引きつけ待機)。", "SX-2 比較用 (初期 OFF = 従来の引きつけ待機)。")


def _hist():
    g = gold()
    head = _seg(g, "// XA-16 / XA-17: 準備前の SATS 反発の履歴", "[hS3, qS3, nS3] = f_satHist(-1, satStb[1], hTqS3)\n")
    assert head.count("stSatsNearD") == 2
    head = head.replace("stSatsNearD", "stSatsNearPx")
    fns = _seg(g, "// 反発の候補 (方向ごと): 起点 q / 成立足 e / 線の種類。", "    [bq, be, bk]\n")
    gated = (
        "// SX-2: 履歴の状態 (接触記録・反発候補) は確定足でだけ書き換える (calc_on_every_tick = true の形成中 tick は読むだけ)。\n"
        "//  採用は、この足の反発 (e = 現在足。t − e = 0、e − q <= Nc は記録の寿命で保証) を先に、無ければ確定済み候補から最新の e\n"
        "//  (ゴールドの「この足の候補を追加してから選ぶ」と確定足で同じ結果。形成中 tick では仮評価用の読取値)\n"
        "if barstate.isconfirmed\n"
        "    hTqL1 := nL1\n    hTqL2 := nL2\n    hTqL3 := nL3\n    hTqS1 := nS1\n    hTqS2 := nS2\n    hTqS3 := nS3\n"
        "    int hNL = f_hPrune(hQsL, hEsL, hKsL)\n    int hNS = f_hPrune(hQsS, hEsS, hKsS)\n"
        "    if hL1\n        array.push(hQsL, qL1)\n        array.push(hEsL, bar_index)\n        array.push(hKsL, 1)\n"
        "    if hL2\n        array.push(hQsL, qL2)\n        array.push(hEsL, bar_index)\n        array.push(hKsL, 2)\n"
        "    if hL3\n        array.push(hQsL, qL3)\n        array.push(hEsL, bar_index)\n        array.push(hKsL, 3)\n"
        "    if hS1\n        array.push(hQsS, qS1)\n        array.push(hEsS, bar_index)\n        array.push(hKsS, 1)\n"
        "    if hS2\n        array.push(hQsS, qS2)\n        array.push(hEsS, bar_index)\n        array.push(hKsS, 2)\n"
        "    if hS3\n        array.push(hQsS, qS3)\n        array.push(hEsS, bar_index)\n        array.push(hKsS, 3)\n"
        "[pQL, pEL, pKL] = f_hPick(hQsL, hEsL, hKsL)\n"
        "[pQS, pES, pKS] = f_hPick(hQsS, hEsS, hKsS)\n"
        "bool hNowL = hL1 or hL2 or hL3\n"
        "bool hNowS = hS1 or hS2 or hS3\n"
        "int  hQL = hNowL ? (hL1 ? qL1 : hL2 ? qL2 : qL3) : pQL     // 即時側で使える Long の反発: 起点 q / 成立足 e / 線 (無ければ na / na / 0)\n"
        "int  hEL = hNowL ? bar_index : pEL\n"
        "int  hKL = hNowL ? (hL1 ? 1 : hL2 ? 2 : 3) : pKL\n"
        "int  hQS = hNowS ? (hS1 ? qS1 : hS2 ? qS2 : qS3) : pQS\n"
        "int  hES = hNowS ? bar_index : pES\n"
        "int  hKS = hNowS ? (hS1 ? 1 : hS2 ? 2 : 3) : pKS\n")
    return "\n" + head + fns + gated


def _now_block():
    g = _seg(gold(), "                // XA-16: 直近の反発で即時エントリー", "                        nowGo    := true\n")
    alert_lines = (
        "                        if stAlertConf and (na(stConfBar) or stConfBar != time)     // SX-2: 即時発注の確定通知 (既存の 1 バー 1 回ガード)\n"
        "                            stConfBar := time\n"
        "                            alert(f_stAlertMsg(\"確定\", side, close, pSL, tpRef), alert.freq_all)\n"
        "                        if stLblConf     // 確定ラベル: 確定通知と同じ値 (発注判断足の終値 / SL0 / TP0。約定通知ではない)\n"
        "                            array.push(stConfLbls, label.new(bar_index, side == 1 ? low : high, f_stAlertMsg(\"確定\", side, close, pSL, tpRef),\n"
        "                                 yloc = side == 1 ? yloc.belowbar : yloc.abovebar, color = side == 1 ? ST_LBL_LONG : ST_LBL_SHORT,\n"
        "                                 textcolor = color.white, style = side == 1 ? label.style_label_up : label.style_label_down, size = size.small))\n"
        "                            if array.size(stConfLbls) > stLblKeep\n"
        "                                label.delete(array.shift(stConfLbls))\n")
    a = "                        strategy.exit(oXid, oEid, stop = oSL)\n"
    assert g.count(a) == 1
    return g.replace(a, a + alert_lines)


def _hdr():
    return (
        "//  SX-2: ゴールド XA-16〜XA-19 の最終形 (即時エントリー: 接触→反発 Nc / 反発→Zone Nz、引きつけ側の接触期限) をこの Strategy に\n"
        "//  追加 (生成: tests/sx2_build.py)。新機能は初期 OFF (本数 1) = 展開前の Current / SATS の売買・数量・通知のまま。近接は銘柄の\n"
        "//  価格幅、反発履歴の状態更新は確定足だけ。即時発注も既存の確定通知 / ラベルへ接続、仮評価は読取専用。成績への影響は未確認。\n")


PROV_TOUCH_OLD = (
    "        if not cancel\n"
    "            int   lk = 0\n"
    "            float lp = na\n"
    "            if not pwTouched\n"
    "                [k0, v0] = f_satPick(pwSide, pwP0, pwSL0, pc, l1p, l2p, stbp)\n")
PROV_TOUCH_NEW = (
    "        if not cancel\n"
    "            // SX-2: 引きつけ側の接触期限 (ON) を確定時と同じ順で反映 (ローカルだけ。接触記録は書き換えない)\n"
    "            bool tchd = pwTouched and not (stSatsTq and bar_index - pwTouchBar > stSatsTqN)\n"
    "            int   lk = 0\n"
    "            float lp = na\n"
    "            if not tchd\n"
    "                [k0, v0] = f_satPick(pwSide, pwP0, pwSL0, pc, l1p, l2p, stbp)\n")
PROV_B_OLD = "            bool rebB      = pwTouched and inRange and (pwSide == 1 ? (pc <= lp and close > lp) : (pc >= lp and close < lp))\n"
PROV_B_NEW = "            bool rebB      = tchd and inRange and (pwSide == 1 ? (pc <= lp and close > lp) : (pc >= lp and close < lp))\n"
PROV_NOW_OLD = "                tp   := pwTP0\n    [side, ePx, sl, tp]\n"
PROV_NOW_NEW = (
    "                tp   := pwTP0\n"
    "    else if stSats and stSatsNow and pwState == 0\n"
    "        // SX-2: 待機前で即時エントリー ON: 形成中の足の Zone シグナル (Current の仮評価と同じ読取専用の判定) が、このまま確定したら\n"
    "        //   即時発注になるか (有効な反発 t − e <= Nz・e − q <= Nc、逆方向一致、SL / TP の向き、P0 と終値の両方の数量)。\n"
    "        //   通常の待機準備になるだけのときは何も返さない (エントリーの仮通知・仮ラベルを出さない)\n"
    "        [s0, e0, l0, t0] = f_stProvEval()\n"
    "        if s0 != 0\n"
    "            int  hBar = s0 == 1 ? hEL : hES\n"
    "            bool nMtf = not (s0 == 1 ? satSkipL : satSkipS)\n"
    "            bool nDir = s0 * (close - l0) > 0 and s0 * (t0 - close) > 0\n"
    "            if not na(hBar) and bar_index - hBar >= 0 and bar_index - hBar <= stSatsNowN and nMtf and nDir\n"
    "                 and not na(f_stQty(s0, e0, l0)) and not na(f_stQty(s0, close, l0))\n"
    "                side := s0\n"
    "                ePx  := close\n"
    "                sl   := l0\n"
    "                tp   := t0\n"
    "    [side, ePx, sl, tp]\n")

PLOTS_NEW = (
    'plot(stSats ? oPath : na,                  "SATS · 直近発注の経路 (1 引きつけ / 2 即時)", display = display.data_window)\n'
    'plot(stSats ? pwNNow : na,                 "SATS · 即時エントリーの発注件数 (引きつけは「発注件数」)", display = display.data_window)\n'
    'plot(stSats ? pwNowK : na,                 "SATS · 即時で採用した反発の線 (1 L1 / 2 L2 / 3 STB)", display = display.data_window)\n'
    'plot(stSats ? pwNowCq : na,                "SATS · 即時で採用した反発の 接触→反発 本数 (e − q)", display = display.data_window)\n'
    'plot(stSats ? pwNowAge : na,               "SATS · 即時で採用した反発の 反発→Zone 本数 (t − e)", display = display.data_window)\n'
    'plot(stSats and oPath == 1 ? pwRRPlan : na, "SATS · 引きつけ 予定 RR", display = display.data_window)\n'
    'plot(stSats and oPath == 1 ? pwRRFill : na, "SATS · 引きつけ 実 RR", display = display.data_window)\n'
    'plot(stSats and oPath == 2 ? pwRRPlan : na, "SATS · 即時 予定 RR", display = display.data_window)\n'
    'plot(stSats and oPath == 2 ? pwRRFill : na, "SATS · 即時 実 RR", display = display.data_window)\n'
    'plot(na(hEL) ? na : bar_index - hEL,      "SATS · Long 即時候補 (期限内で最新の反発) の 反発→現在 本数", display = display.data_window)\n'
    'plot(na(hES) ? na : bar_index - hES,      "SATS · Short 即時候補 (期限内で最新の反発) の 反発→現在 本数", display = display.data_window)\n'
    'plot(stSats and pwTouched ? bar_index - pwTouchBar : na, "SATS · 引きつけ側 接触からの本数 (現在 − q)", display = display.data_window)\n'
    'plot(stSats ? pwNTqExp : na,               "SATS · 引きつけ側 接触期限切れ件数 (待機は継続)", display = display.data_window)\n')


def edits(cur):
    nb_anchor = "                if not skipRef and not na(pQty) and pwState == 0 and not pwCancelBar\n"
    return [
        ("header", "//  確定は SATS の strategy.entry で 1 回 (待機開始・見送りでは出さない)。",
         _hdr() + "//  確定は SATS の strategy.entry で 1 回 (待機開始・見送りでは出さない)。"),
        ("input",
         '     tooltip = "5分足は発注を判断するその 5分足の SATS バンド (この Strategy の SATS 計算をそのまま使う)。")\n',
         '     tooltip = "5分足は発注を判断するその 5分足の SATS バンド (この Strategy の SATS 計算をそのまま使う)。")\n' + _inputs()),
        ("hist", "bool satSkipL = f_satAllAgainst(-1)     // Long を見送る: 選択した時間足がすべて赤\n",
         "bool satSkipL = f_satAllAgainst(-1)     // Long を見送る: 選択した時間足がすべて赤\n" + _hist()),
        ("state", "var float oTP0     = na      // SATS で発注した注文の TP0 (約定確認時の TP)\n",
         "var float oTP0     = na      // SATS で発注した注文の TP0 (約定確認時の TP)\n"
         + _seg(gold(), "var int   oPath    = 0", "(接触期限切れ後の再接触を二重に数えない)\n")),
        ("alert", PROV_TOUCH_OLD, PROV_TOUCH_NEW),
        ("alert", PROV_B_OLD, PROV_B_NEW),
        ("alert", PROV_NOW_OLD, PROV_NOW_NEW),
        ("pull",
         "        else\n            int   lk = 0\n            float lp = na\n            if not pwTouched\n",
         "        else\n"
         + _seg(gold(), "            // XA-17: 引きつけ側の接触期限 (ON のとき)。", "                pwNTqExp   += 1\n")
         + "            int   lk = 0\n            float lp = na\n            if not pwTouched\n"),
        ("pull", "                pwNTouchPrep += 1\n", "                pwNTouchPrep += pwTouchSeen ? 0 : 1\n                pwTouchSeen  := true\n"),
        ("path", "                    oTP0    := pwTP0\n", "                    oTP0    := pwTP0\n                    oPath   := 1\n"),
        ("now", nb_anchor, _now_block() + "                if not skipRef and not na(pQty) and pwState == 0 and not pwCancelBar and not nowGo\n"),
        ("pull", "                    pwTouched  := false     // 新しい準備は接触待ちから\n",
         "                    pwTouched  := false     // 新しい準備は接触待ちから\n                    pwTouchSeen := false\n"),
        ("plot", 'plot(stSats ? pwEv : na,                   "SATS · イベント (1 準備 / 2 発注 / -1 期限 / -4 SL0)", display = display.data_window)\n',
         'plot(stSats ? pwEv : na,                   "SATS · イベント (1 準備 / 2 発注 / 3 即時発注 / -1 期限 / -4 SL0)", display = display.data_window)\n'),
        ("plot", 'plot(stSats ? pwNBad : na,                 "SATS · 不適切な約定の決済件数", display = display.data_window)\n',
         'plot(stSats ? pwNBad : na,                 "SATS · 不適切な約定の決済件数", display = display.data_window)\n' + PLOTS_NEW),
        ("plot",
         'plotshape(stSats and pwEv == 2, "SATS · 発注", style = shape.triangledown, location = location.abovebar, color = color.red, size = size.tiny)\n',
         'plotshape(stSats and pwEv == 2, "SATS · 発注", style = shape.triangledown, location = location.abovebar, color = color.red, size = size.tiny)\n'
         'plotshape(stSats and pwEv == 3, "SATS · 即時発注", style = shape.diamond, location = location.abovebar, color = color.blue, size = size.tiny)\n'),
    ]


def _apply(src, eds):
    out = src
    for _, a, b in eds:
        assert out.count(a) == 1, a[:80]
        out = out.replace(a, b)
    return out


def _revert(text, eds):
    out = text
    for _, a, b in reversed(eds):
        if out is None or out.count(b) != 1:
            return None
        out = out.replace(b, a)
    return out


def build(path):
    return _apply(show(BASE_REV, path), edits(BY_PATH[path]))


def strip(path, text):
    """reverse SX-2 exactly (-> the file of BASE_REV); None when not exact."""
    return _revert(text, edits(BY_PATH[path]))


def unapply(path, text):
    """reverse SX-2 when present (all or nothing): unchanged without it (or for other paths), None with only part of it."""
    if text is None or path not in BY_PATH:
        return text
    if _hdr() not in text and "stSatsNowC" not in text:
        return text
    return strip(path, text)


if __name__ == "__main__":
    for p in FILES:
        open(os.path.join(ROOT, p), "w", encoding="utf-8").write(build(p))
        print("written", p)
