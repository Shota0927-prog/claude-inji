"""AU-1 — automation output copy of the Gold Short Strategy (stage 2: notification receive / record only, no orders).

automation/xau_short/pine/ZoneStrategyXAU_Auto.pine == ZoneStrategyXAU.pine (the XA-23 Gold Short Strategy, = the file of
SRC_REV = xa_build.build_strategy()) + EDITS (exact replacements, each old once). The normal Strategy, the Gold Long, the Engines
and the existing generators are not touched. The copy only ADDS machine-readable JSON alert() calls at the points where the
Strategy already decides something (no trading / order / state line is changed):
  PROV        provisional (forming 5m bar; the XA-22 dedup, same spot as the human provisional alert)
  ENTRY       confirmed order intent (the three strategy.entry branches: SATS pull / SATS immediate / Current)
  CANCEL      the Strategy cancels its pending entry (market entry not filled / limit invalid or out of session)
  TV_FILL     the Strategy sees its (virtual) entry filled on the confirmed bar
  TP_SET      the Strategy places its TP after the fill (confirmed bar, as the code does)
  BE_MOVE     the Strategy moves its stop to the fill price (confirmed bar, as the code does)
  CLOSE_REQ   the Strategy closes the position at market (bad fill side / RR below min / risk <= 0)
  TV_CLOSED   filled and closed inside the fill bar (virtual)
  TV_FLAT     the virtual position is gone (stop / TP / breakeven hit on the TradingView side)
  WAIT_START / WAIT_END   SATS wait prepared / ended (expiry or SL0), informational
One input "自動化 JSON 出力" (default ON): ON = these JSON alerts are sent and the copy's human-text alerts are not (one webhook
alert receives only JSON); OFF = the copy alerts exactly like the normal Strategy. Labels unchanged.
Idempotency key = SID|ev|tid|bar_close (deterministic from the decision bar's close time, not a counter), varip-dedup in Pine.
strip() reverses the edits exactly (-> the normal Short Strategy).
"""
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_PATH = "ZoneStrategyXAU.pine"
AUTO_PATH = "automation/xau_short/pine/ZoneStrategyXAU_Auto.pine"
SRC_REV = "7705907"                     # XA-23
SCHEMA = "xau-auto/1"
SID = "XAU-SHORT|XA-23|AU-1"
KEEP = 300

HDR_OLD = "//  Zone Strategy XAU  —  ZONE-P (ZoneVisualPractical) の Zone 判定をそのまま使う XAUUSD 5分足 Strategy\n"
HDR_NEW = (
    "//  Zone Strategy XAU Auto (AU-1)  —  ゴールドショート (ZoneStrategyXAU.pine XA-23) の自動化用コピー (生成: tests/au_build.py)。\n"
    "//  売買判定・注文処理・状態は通常版と同一。追加は機械可読 JSON の alert() だけ (第2段階: 受信・記録のみ。実注文はしない)。\n"
    "//  イベント: PROV / ENTRY (確定した注文意図。約定通知ではない) / CANCEL / TV_FILL / TP_SET / BE_MOVE / CLOSE_REQ / TV_CLOSED / TV_FLAT /\n"
    "//  WAIT_START / WAIT_END。TP_SET・BE_MOVE は通常版どおり確定5分足で出る (約定直後・ティック到達直後ではない)。TV_* は TradingView\n"
    "//  内の疑似建玉の状態で、MT5 の実建玉とは別。「自動化 JSON 出力」ON (初期) ではこのコピーの人間向け文章アラートは出さない。\n"
    + HDR_OLD)

AU_INPUTS = (
    'var string G_AU = "04 · Automation Output (AU-1)"\n'
    'auJson = input.bool(true, "自動化 JSON 出力 (Webhook 用)", group = G_AU,\n'
    '     tooltip = "AU-1: ON = 機械可読 JSON (PROV / ENTRY / CANCEL / TV_FILL / TP_SET / BE_MOVE / CLOSE_REQ / TV_CLOSED / TV_FLAT / WAIT_*) を\\n" +\n'
    '     "alert() で送り、このコピーの人間向け文章アラートは送らない。OFF = 通常版と同じ文章アラート。売買・ラベルは同じ。\\n" +\n'
    '     "TradingView の Alert は「alert() function calls only」、Webhook URL に受信処理の URL を設定する。")\n')

AU_FNS = (
    "\n"
    "// ---- AU-1 自動化出力 (JSON) ------------------------------------------------------------------------------\n"
    "//  1 イベント = 1 alert()。キー = SID|ev|tid|判断足の終了時刻 (連番ではない。再読込しても同じ足は同じキー)。varip で同じキーを\n"
    "//  再送しない (確定足の再計算対策)。tid: 注文意図 = \"T\" + ENTRY 判断足の終了時刻 (以後の CANCEL / TV_* / TP_SET / BE_MOVE /\n"
    "//  CLOSE_REQ も同じ tid)、SATS 待機 = \"W\" + 準備足の終了時刻、仮 = \"P\" + 足の開始時刻。cfg = 主要入力の値 (受信側で設定 ID を作る)\n"
    'string AU_SCHEMA = "' + SCHEMA + '"\n'
    'string AU_SID    = "' + SID + '"\n'
    'string auCfg = "dir=" + stDir + ";mode=" + stMode + ";tim=" + stTiming + ";now=" + (stSatsNow ? "1" : "0") +\n'
    '     ";nc=" + str.tostring(stSatsNowC) + ";nz=" + str.tostring(stSatsNowN) + ";tq=" + (stSatsTq ? "1" : "0") + ";tqn=" + str.tostring(stSatsTqN) +\n'
    '     ";wait=" + str.tostring(stSatsWait) + ";body=" + (stSatsBody ? "1" : "0") + ";near=" + (stSatsNear ? "1" : "0") + ";neard=" + str.tostring(stSatsNearD) +\n'
    '     ";f=" + (stSatsFD ? "D" : "") + (stSatsF4 ? "4" : "") + (stSatsF1 ? "1" : "") + (stSatsF15 ? "q" : "") + (stSatsF5 ? "5" : "") +\n'
    '     ";buf=" + str.tostring(stBuffer) + ";rr=" + str.tostring(stRR) + ";tpz=" + (stTpZone ? "1" : "0") + ";be=" + (stBE ? "1" : "0") +\n'
    '     ";bem=" + stBEMode + ";bed=" + str.tostring(stBEDist) + ";ber=" + str.tostring(stBER) + ";betp=" + str.tostring(stBETp) +\n'
    '     ";sess=" + (stUseSess ? "1" : "0") + "," + stSessTz + "," + str.tostring(stSessStartH) + ":" + str.tostring(stSessStartM) + "-" +\n'
    '     str.tostring(stSessEndH) + ":" + str.tostring(stSessEndM) + ";cap=" + str.tostring(stCapBase) + ";risk=" + str.tostring(stRiskPct) +\n'
    '     ";strong=" + str.tostring(thrStrong) + ";zhw=" + str.tostring(zoneHalfWidth) + ";role=" + roleMode\n'
    "varip array<string> auSent = array.new_string()     // AU-1: 送信した JSON イベントのキー (最大 " + str(KEEP) + " 件、古い順に削除)\n"
    'var string auTid = ""     // AU-1: 直近の注文意図の取引 ID (var = 売買状態と同じく確定足で確定)\n'
    "\n"
    "f_auNum(float v) =>\n"
    '    na(v) ? "null" : str.tostring(v, format.mintick)\n'
    "\n"
    "f_auJson(string ev, string tid, int rank, int side, string ot, float px, float sl, float tp, string info, string key) =>\n"
    '    "{\\"schema\\":\\"" + AU_SCHEMA + "\\",\\"sid\\":\\"" + AU_SID + "\\",\\"cfg\\":\\"" + auCfg + "\\",\\"ev\\":\\"" + ev + "\\",\\"key\\":\\"" + key +\n'
    '     "\\",\\"tid\\":\\"" + tid + "\\",\\"rank\\":" + str.tostring(rank) + ",\\"sym\\":\\"" + syminfo.tickerid + "\\",\\"tf\\":\\"" + timeframe.period +\n'
    '     "\\",\\"bar_open\\":" + str.tostring(time) + ",\\"bar_close\\":" + str.tostring(time_close) + ",\\"sent\\":" + str.tostring(timenow) +\n'
    '     ",\\"side\\":\\"" + (side == 1 ? "LONG" : side == -1 ? "SHORT" : "") + "\\",\\"otype\\":\\"" + ot + "\\",\\"px\\":" + f_auNum(px) +\n'
    '     ",\\"sl\\":" + f_auNum(sl) + ",\\"tp\\":" + f_auNum(tp) + ",\\"info\\":\\"" + info + "\\"}"\n'
    "\n"
    "// AU-1: JSON イベントを 1 回だけ送る (自動化出力 ON のとき)。表示・売買・状態には触れない。戻り値 = 送信したか\n"
    "f_auEmit(string ev, string tid, int rank, int side, string ot, float px, float sl, float tp, string info) =>\n"
    '    string key  = AU_SID + "|" + ev + "|" + tid + "|" + str.tostring(time_close)\n'
    "    bool   send = auJson and not array.includes(auSent, key)\n"
    "    if send\n"
    "        array.push(auSent, key)\n"
    "        if array.size(auSent) > " + str(KEEP) + "\n"
    "            array.shift(auSent)\n"
    "        alert(f_auJson(ev, tid, rank, side, ot, px, sl, tp, info, key), alert.freq_all)\n"
    "    send\n")

I16, I12, I8, I20, I24 = " " * 16, " " * 12, " " * 8, " " * 20, " " * 24
EDITS = [
    ("header", HDR_OLD, HDR_NEW),
    ("name", '     title                  = "Zone Strategy XAU",\n', '     title                  = "Zone Strategy XAU Auto",\n'),
    ("name", '     shorttitle             = "ZONE-ST",\n', '     shorttitle             = "ZONE-ST-AU",\n'),
    ("input", '     "アラートの ON / OFF とは独立。約定通知ではない。過去足にも表示し、最新 50 個を保持 (古い順に削除)。")\n',
     '     "アラートの ON / OFF とは独立。約定通知ではない。過去足にも表示し、最新 50 個を保持 (古い順に削除)。")\n' + AU_INPUTS),
    ("fns", "            label.delete(array.shift(stConfLbls))\n    mk\n", "            label.delete(array.shift(stConfLbls))\n    mk\n" + AU_FNS),
    ("human", '        alert(f_stAlertMsg("確定", side, ePx, sl, tp, isLim, isSats), alert.freq_all)\n    send\n',
     '        if not auJson     // AU-1: JSON 出力 ON ではこのコピーの文章アラートを送らない (JSON の ENTRY は発注分岐で送る)\n'
     '            alert(f_stAlertMsg("確定", side, ePx, sl, tp, isLim, isSats), alert.freq_all)\n    send\n'),
    ("human", '    alert(f_stAlertMsg("仮", pSide, pPx, pSL, pTP, not stSats and stModeA, stSats), alert.freq_once_per_bar)\n',
     '    if auJson     // AU-1: 仮は JSON (同じ判定・同じ重複防止)。OFF なら通常版と同じ文章\n'
     '        f_auEmit("PROV", "P" + str.tostring(time), 1, pSide, pPath == 3 and stModeA ? "LIMIT" : "MARKET", pPx, pSL, pTP,\n'
     '             pPath == 1 ? "SATS_PULL" : pPath == 2 ? "SATS_NOW" : "CURRENT")\n'
     '    else\n'
     '        alert(f_stAlertMsg("仮", pSide, pPx, pSL, pTP, not stSats and stModeA, stSats), alert.freq_once_per_bar)\n'),
    ("event", I12 + "oState  := 2\n" + I12 + "fillNow := true\n",
     I12 + "oState  := 2\n" + I12 + "fillNow := true\n"
     + I12 + 'f_auEmit("TV_FILL", auTid, 30, oSide, "", oFill, oSL, na, "virtual_fill")     // AU-1\n'),
    ("event", I12 + "// 約定した足の中で SL まで成立した\n" + I12 + "map.put(stUsed, oTrack, true)\n" + I12 + "oState := 0\n",
     I12 + "// 約定した足の中で SL まで成立した\n" + I12 + "map.put(stUsed, oTrack, true)\n" + I12 + "oState := 0\n"
     + I12 + 'f_auEmit("TV_CLOSED", auTid, 70, oSide, "", strategy.closedtrades.exit_price(ct - 1), oSL, oTP0, "filled_and_closed_in_bar")     // AU-1\n'),
    ("event", I8 + "else if not oLimit\n" + I12 + "strategy.cancel(oEid)\n" + I12 + "strategy.cancel(oXid)\n" + I12 + "oState := 0\n",
     I8 + "else if not oLimit\n" + I12 + "strategy.cancel(oEid)\n" + I12 + "strategy.cancel(oXid)\n" + I12 + "oState := 0\n"
     + I12 + 'f_auEmit("CANCEL", auTid, 20, oSide, "MARKET", na, oSL, na, "market_entry_not_filled")     // AU-1\n'),
    ("event", "    else if oState >= 2 and strategy.opentrades == 0\n" + I8 + "oState := 0\n",
     "    else if oState >= 2 and strategy.opentrades == 0\n" + I8 + "oState := 0\n"
     + I8 + 'f_auEmit("TV_FLAT", auTid, 90, oSide, "", strategy.closedtrades > 0 ? strategy.closedtrades.exit_price(strategy.closedtrades - 1) : na, oStop, oTP, "virtual_position_closed")     // AU-1\n'),
    ("event", I12 + "oTP   := oTP0\n" + I12 + "oStop := oSL\n" + I12 + "strategy.exit(oXid, oEid, stop = oStop, limit = oTP)\n",
     I12 + "oTP   := oTP0\n" + I12 + "oStop := oSL\n" + I12 + "strategy.exit(oXid, oEid, stop = oStop, limit = oTP)\n"
     + I12 + 'f_auEmit("TP_SET", auTid, 40, oSide, "", oFill, oStop, oTP, "sats_tp0")     // AU-1\n'),
    ("event", I12 + "strategy.close(oEid)\n" + I12 + "oState := 3\n" + I12 + "pwNBad += 1\n",
     I12 + "strategy.close(oEid)\n" + I12 + "oState := 3\n" + I12 + "pwNBad += 1\n"
     + I12 + 'f_auEmit("CLOSE_REQ", auTid, 60, oSide, "MARKET", oFill, oSL, oTP0, "bad_fill_side")     // AU-1\n'),
    ("event", I12 + "if skipRR\n" + I16 + "strategy.close(oEid)\n" + I16 + "oState := 3\n",
     I12 + "if skipRR\n" + I16 + "strategy.close(oEid)\n" + I16 + "oState := 3\n"
     + I16 + 'f_auEmit("CLOSE_REQ", auTid, 60, oSide, "MARKET", oFill, oSL, tp, "rr_below_min")     // AU-1\n'),
    ("event", I16 + "oTP   := tp\n" + I16 + "oStop := oSL\n" + I16 + "strategy.exit(oXid, oEid, stop = oStop, limit = oTP)\n",
     I16 + "oTP   := tp\n" + I16 + "oStop := oSL\n" + I16 + "strategy.exit(oXid, oEid, stop = oStop, limit = oTP)\n"
     + I16 + 'f_auEmit("TP_SET", auTid, 40, oSide, "", oFill, oStop, oTP, "fill_rr")     // AU-1\n'),
    ("event", I8 + "else\n" + I12 + "strategy.close(oEid)\n" + I12 + "oState := 3\n\n    // (2c)",
     I8 + "else\n" + I12 + "strategy.close(oEid)\n" + I12 + "oState := 3\n"
     + I12 + 'f_auEmit("CLOSE_REQ", auTid, 60, oSide, "MARKET", oFill, oSL, na, "risk_le_0")     // AU-1\n\n    // (2c)'),
    ("event", I12 + "oBE   := true\n" + I12 + "oStop := oFill\n" + I12 + "strategy.exit(oXid, oEid, stop = oStop, limit = oTP)\n",
     I12 + "oBE   := true\n" + I12 + "oStop := oFill\n" + I12 + "strategy.exit(oXid, oEid, stop = oStop, limit = oTP)\n"
     + I12 + 'f_auEmit("BE_MOVE", auTid, 50, oSide, "", oFill, oStop, oTP, "breakeven")     // AU-1\n'),
    ("event", I8 + "oState    := 0\n" + I8 + "cancelBar := true\n",
     I8 + "oState    := 0\n" + I8 + "cancelBar := true\n"
     + I8 + 'f_auEmit("CANCEL", auTid, 20, oSide, oLimit ? "LIMIT" : "MARKET", oL, oSL, na, not stSessOK ? "out_of_session" : "limit_zone_invalid")     // AU-1\n'),
    ("event", I12 + "pwEv        := why\n",
     I12 + "pwEv        := why\n"
     + I12 + 'f_auEmit("WAIT_END", "W" + str.tostring(pwEndT), 95, pwSide, "", pwP0, pwSL0, pwTP0, why == -1 ? "expired" : "sl0_reached")     // AU-1\n'),
    ("event", I20 + "f_stConfLabel(pwSide, close, pwSL0, pwTP0, false, true)     // XA-23 確定ラベル: 確定アラートと同じ値\n",
     I20 + "f_stConfLabel(pwSide, close, pwSL0, pwTP0, false, true)     // XA-23 確定ラベル: 確定アラートと同じ値\n"
     + I20 + 'auTid := "T" + str.tostring(time_close)     // AU-1: 注文意図の取引 ID (判断足の終了時刻)\n'
     + I20 + 'f_auEmit("ENTRY", auTid, 10, pwSide, "MARKET", close, pwSL0, pwTP0, "SATS_PULL;wid=W" + str.tostring(pwEndT))     // AU-1\n'),
    ("event", I24 + "f_stConfLabel(side, close, pSL, tpRef, false, true)     // XA-23 確定ラベル: 確定アラートと同じ値\n",
     I24 + "f_stConfLabel(side, close, pSL, tpRef, false, true)     // XA-23 確定ラベル: 確定アラートと同じ値\n"
     + I24 + 'auTid := "T" + str.tostring(time_close)     // AU-1\n'
     + I24 + 'f_auEmit("ENTRY", auTid, 10, side, "MARKET", close, pSL, tpRef, "SATS_NOW")     // AU-1\n'),
    ("event", I20 + "f_stPvRelease(c.track)     // XA-22: 正式な待機準備 -> この Track の仮通知キーを解除 (新しい待機は初回を通知)\n",
     I20 + "f_stPvRelease(c.track)     // XA-22: 正式な待機準備 -> この Track の仮通知キーを解除 (新しい待機は初回を通知)\n"
     + I20 + 'f_auEmit("WAIT_START", "W" + str.tostring(time_close), 5, side, "", ref, pSL, tpRef, "sats_wait")     // AU-1\n'),
    ("event", I16 + "f_stConfLabel(side, stModeA ? oL : close, pSL, tpRef, stModeA, false)     // XA-23 確定ラベル: 確定アラートと同じ値\n",
     I16 + "f_stConfLabel(side, stModeA ? oL : close, pSL, tpRef, stModeA, false)     // XA-23 確定ラベル: 確定アラートと同じ値\n"
     + I16 + 'auTid := "T" + str.tostring(time_close)     // AU-1\n'
     + I16 + 'f_auEmit("ENTRY", auTid, 10, side, stModeA ? "LIMIT" : "MARKET", stModeA ? oL : close, pSL, tpRef, "CURRENT")     // AU-1\n'),
]


# every file AU-1 adds (the older fixtures' "other files unchanged" checks accept exactly these through ok())
NEW_FILES = ("tests/au_build.py", "tests/au_sim.py", "tests/aur_sim.py", AUTO_PATH, "automation/xau_short/README_ja.md",
             "automation/xau_short/receiver/.gitignore", "automation/xau_short/receiver/config.example.json",
             "automation/xau_short/receiver/samples/bad_cases.jsonl", "automation/xau_short/receiver/samples/make_samples.py",
             "automation/xau_short/receiver/samples/normal_flow.jsonl", "automation/xau_short/receiver/show_log.ps1",
             "automation/xau_short/receiver/start_receiver.ps1", "automation/xau_short/receiver/stop_receiver.ps1",
             "automation/xau_short/receiver/xau_receiver.py")


def ok(path):
    """AU-1 accounts for this path exactly: one of its new files, or the untracked directory entry 'automation/' while every file in
    it is one of them (git status lists a new directory as one entry before it is committed)."""
    if path in NEW_FILES:
        return True
    if path == "automation/":
        found = []
        for d, dirs, files in os.walk(os.path.join(ROOT, "automation")):
            dirs[:] = [x for x in dirs if x not in ("__pycache__", "data")]
            found += [os.path.relpath(os.path.join(d, f), ROOT).replace(os.sep, "/") for f in files]
        return bool(found) and all(f in NEW_FILES for f in found)
    return False


def show(rev, path):
    return subprocess.run(["git", "-C", ROOT, "show", f"{rev}:{path}"], capture_output=True, text=True).stdout


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


def source():
    """the normal Gold Short Strategy this copy is built from (XA-23, = the committed file of SRC_REV)."""
    return __import__("xa_build").build_strategy()


def build():
    return _apply(source(), EDITS)


def strip(text):
    """reverse AU-1 exactly (-> the normal Short Strategy); None when not exact."""
    return _revert(text, EDITS)


if __name__ == "__main__":
    p = os.path.join(ROOT, AUTO_PATH)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w", encoding="utf-8").write(build())
    print("written", AUTO_PATH)
