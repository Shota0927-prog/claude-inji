"""AU-1 / AU-2 — automation output copy of the Gold Short Strategy (stage 2: notification receive / record only, no orders).

automation/xau_short/pine/ZoneStrategyXAU_Auto.pine == ZoneStrategyXAU.pine (the XA-24 Gold Short Strategy = xa_build.build_strategy()
= the XA-23 file of SRC_REV + the XA-24 run-time reduction (Engine /3, single FVG selection; same trading)) + edits() (exact replacements, each old once). The normal Strategy, the Gold Long, the Engines
and the existing generators are not touched. The copy only ADDS machine-readable JSON alert() calls at the points where the
Strategy already decides something (no trading / order / state line is changed):
  PROV        provisional (forming 5m bar; the XA-22 dedup, same spot as the human provisional alert)
  ENTRY       confirmed order intent (the three strategy.entry branches: SATS pull / SATS immediate / Current)
  CANCEL      the Strategy cancels its pending entry (market entry not filled / limit invalid or out of session)
  TV_FILL     the Strategy sees its (virtual) entry filled on the confirmed bar
  TP_SET      the Strategy places its TP after the fill (confirmed bar, as the code does)
  BE_MOVE     the Strategy moves its stop to the (virtual) fill price (confirmed bar, as the code does)
  CLOSE_REQ   the Strategy closes the position at market (bad fill side / RR below min / risk <= 0)
  TV_CLOSED   filled and closed inside the fill bar (virtual)
  TV_FLAT     the virtual position is gone (stop / TP / breakeven hit on the TradingView side)
  WAIT_START / WAIT_END   SATS wait prepared / ended (expiry or SL0), informational
  BAR         (AU-2) every confirmed 5m bar: OHLC + the TradingView virtual position (state / stop / TP) after the bar, so a later
              stage can replay the breakeven rule from the real MT5 fill price (independent of the TradingView virtual fill)
Inputs "自動化 JSON 出力" (default ON: these JSON alerts, no human-text alerts from the copy; OFF = the normal text alerts) and
"BAR 通知" (default ON). Labels unchanged.
AU-2: schema xau-auto/2 — every event carries the event bar's OHLC (o / h / l / c); prices with 8 decimals (not rounded to the
mintick); every string value JSON-escaped (f_auEsc); cfg = every input that can change trading / waiting / cancelling /
management / signal suppression / provisional output, generated from the source declarations (cfg_fields(); display-only
inputs excluded with the reason in EXCLUDED), so the receiver's settings ID (SHA-256 of cfg) covers them.
Idempotency key = SID|ev|tid|bar_close (deterministic from bar times, not a counter), varip-dedup in Pine.
AU-5 (TradingView RE10110 load): the notification-only work (key, duplicate search, JSON, the sent-key array, the argument
strings of the emit calls) runs only on realtime bars with the JSON output ON, inside explicit if blocks (`if auLive` at every
call site, `if auJson and barstate.isrealtime` inside f_auEmit; no reliance on and / or short-circuiting); historical bars skip
it entirely. The trade state (auTid) is still computed on every bar. The cfg strings are `var` (built once per run). The JSON
content, keys, cfg and event meanings are unchanged.
XA-24: the copy follows the normal Short Strategy (Engine import ZoneEnginePracticalXAUUSD/3, f_stZoneEval with one FVG
selection; the AU edits, JSON, cfg, keys and the SID are unchanged: the trading and the notifications are the same).
strip() reverses the edits exactly (-> the normal Short Strategy).
"""
import json
import os
import re
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_PATH = "ZoneStrategyXAU.pine"
AUTO_PATH = "automation/xau_short/pine/ZoneStrategyXAU_Auto.pine"
CFG_FIELDS_PATH = "automation/xau_short/cfg_fields.json"
SRC_REV = "7705907"                     # XA-23
SCHEMA = "xau-auto/2"
SID = "XAU-SHORT|XA-23|AU-2"
CFG_VERSION = "c2"
KEEP = 400
# inputs that only change what is drawn (never trading, waiting, cancelling, management, signal suppression or the JSON output)
EXCLUDED = {"stSatsShow": "SATS 線の表示 (plot) だけに使われる",
            "stLblConf": "確定ラベルの表示 (label) だけに使われる"}

HDR_OLD = "//  Zone Strategy XAU  —  ZONE-P (ZoneVisualPractical) の Zone 判定をそのまま使う XAUUSD 5分足 Strategy\n"
HDR_NEW = (
    "//  Zone Strategy XAU Auto (AU-2)  —  ゴールドショート (ZoneStrategyXAU.pine XA-24) の自動化用コピー (生成: tests/au_build.py)。\n"
    "//  売買判定・注文処理・状態は通常版と同一。追加は機械可読 JSON の alert() だけ (第2段階: 受信・記録のみ。実注文はしない)。\n"
    "//  イベント: PROV / ENTRY (確定した注文意図。約定通知ではない) / CANCEL / TV_FILL / TP_SET / BE_MOVE / CLOSE_REQ / TV_CLOSED / TV_FLAT /\n"
    "//  WAIT_START / WAIT_END / BAR。TP_SET・BE_MOVE は通常版どおり確定5分足で出る (約定直後・ティック到達直後ではない)。TV_* と BE_MOVE の\n"
    "//  価格は TradingView 内の疑似建玉 (疑似約定価格) 基準で、MT5 の実建玉とは別。BAR は確定5分足ごとの OHLC と疑似建玉の状態。\n"
    "//  「自動化 JSON 出力」ON (初期) ではこのコピーの人間向け文章アラートは出さない。\n"
    "//  AU-5 (負荷対策): 通知だけの処理 (キー・重複検索・JSON・送信済み配列・通知用の引数文字列) はリアルタイムの送信時だけ。過去足では\n"
    "//  行わない (売買・取引 ID などの状態は従来どおり全足で計算)。cfg 文字列は var で 1 回だけ構築。通知の内容・キー・cfg は AU-2 と同じ。\n"
    + HDR_OLD)

AU_INPUTS = (
    'var string G_AU = "04 · Automation Output (AU-2)"\n'
    'auJson = input.bool(true, "自動化 JSON 出力 (Webhook 用)", group = G_AU,\n'
    '     tooltip = "ON = 機械可読 JSON (PROV / ENTRY / CANCEL / TV_FILL / TP_SET / BE_MOVE / CLOSE_REQ / TV_CLOSED / TV_FLAT / WAIT_* / BAR) を\\n" +\n'
    '     "alert() で送り、このコピーの人間向け文章アラートは送らない。OFF = 通常版と同じ文章アラート。売買・ラベルは同じ。\\n" +\n'
    '     "TradingView の Alert は「alert() function calls only」、Webhook URL に受信処理の URL を設定する。")\n'
    'auBar = input.bool(true, "BAR 通知 (確定5分足ごとの OHLC)", group = G_AU,\n'
    '     tooltip = "ON = 確定5分足ごとに BAR (OHLC・疑似建玉の状態) を送る (後段で MT5 実約定価格から建値判定を再現するための材料)。売買は変えない。")\n')

I16, I12, I8, I20, I24 = " " * 16, " " * 12, " " * 8, " " * 20, " " * 24


def show(rev, path):
    return subprocess.run(["git", "-C", ROOT, "show", f"{rev}:{path}"], capture_output=True, text=True).stdout


def source():
    """the normal Gold Short Strategy this copy is built from (XA-24 = the committed XA-23 file of SRC_REV + xa_build.STRATEGY_EDITS24)."""
    return __import__("xa_build").build_strategy()


def cfg_fields(src=None):
    """every input of the source, in declaration order: (name, type, group, included, reason)."""
    import eu_sim as es
    src = source() if src is None else src
    out = []
    vals = es.input_values(src)
    for name, decl in es.input_decls(src).items():
        ty = re.search(r"input\.(\w+)\(", decl).group(1)
        g = re.search(r"group\s*=\s*([^,)\n]+)", decl)
        grp = g.group(1).strip() if g else ""
        m = re.search(r'var string ' + re.escape(grp) + r' = "([^"]*)"', src) if grp.startswith("G_") else None
        out.append({"name": name, "type": ty, "default": vals.get(name), "group": m.group(1) if m else grp.strip('"'), "included": name not in EXCLUDED,
                    "reason": EXCLUDED.get(name, "売買・待機・取消・管理・シグナル抑制・仮通知のいずれかに影響")})
    return out


def _cfg_term(f):
    n, ty = f["name"], f["type"]
    return {"bool": f'({n} ? "1" : "0")', "int": f"str.tostring({n})", "float": f'str.tostring({n}, "#.##########")'}.get(ty, n)


def _cfg_pine(src):
    inc = [f for f in cfg_fields(src) if f["included"]]
    lines, parts = [], []
    for i in range(0, len(inc), 12):
        chunk = inc[i:i + 12]
        nm = f"auCfg{i // 12}"
        parts.append(nm)
        lines.append(f"var string {nm} = " + ' + "|" + '.join(_cfg_term(f) for f in chunk) + "\n")
    lines.append(f'var string auCfgRaw = "{CFG_VERSION}|" + ' + ' + "|" + '.join(parts) + "\n")
    lines.append("var string auCfg    = f_auEsc(auCfgRaw)     // JSON 用にエスケープ済み (受信側は SHA-256 を設定 ID にする)\n")
    return "".join(lines)


def _au_fns(src):
    return (
        "\n"
        "// ---- AU-2 自動化出力 (JSON) ------------------------------------------------------------------------------\n"
        "//  1 イベント = 1 alert()。キー = SID|ev|tid|判断足の終了時刻 (連番ではない。再読込しても同じ足は同じキー)。varip で同じキーを\n"
        "//  再送しない (確定足の再計算対策)。tid: 注文意図 = \"T\" + ENTRY 判断足の終了時刻 (以後の CANCEL / TV_* / TP_SET / BE_MOVE /\n"
        "//  CLOSE_REQ も同じ tid)、SATS 待機 = \"W\" + 準備足の終了時刻、仮 = \"P\" + 足の開始時刻、BAR = \"B\" + 足の終了時刻。\n"
        "//  cfg = 表示専用 (SATS 線表示・確定ラベル表示) を除く全入力の値 (宣言順、tests/au_build.py が生成、項目一覧は cfg_fields.json)。\n"
        "//  価格は小数 8 桁 (最小刻みへ丸めない)、文字列は JSON エスケープ。o / h / l / c はイベントの足の OHLC (PROV は形成中の値)\n"
        f'string AU_SCHEMA = "{SCHEMA}"\n'
        f'string AU_SID    = "{SID}"\n'
        "f_auEsc(string s) =>\n"
        '    str.replace_all(str.replace_all(s, "\\\\", "\\\\\\\\"), "\\"", "\\\\\\"")\n'
        + _cfg_pine(src) +
        f"varip array<string> auSent = array.new_string()     // 送信した JSON イベントのキー (最大 {KEEP} 件、古い順に削除)\n"
        'var string auTid = ""     // 直近の注文意図の取引 ID (var = 売買状態と同じく確定足で確定)\n'
        "\n"
        "f_auNum(float v) =>\n"
        '    na(v) ? "null" : str.tostring(v, "#.########")\n'
        "\n"
        "f_auJson(string ev, string tid, int rank, int side, string ot, float px, float sl, float tp, string info, string key) =>\n"
        '    "{\\"schema\\":\\"" + AU_SCHEMA + "\\",\\"sid\\":\\"" + f_auEsc(AU_SID) + "\\",\\"cfg\\":\\"" + auCfg + "\\",\\"ev\\":\\"" + ev +\n'
        '     "\\",\\"key\\":\\"" + f_auEsc(key) + "\\",\\"tid\\":\\"" + tid + "\\",\\"rank\\":" + str.tostring(rank) + ",\\"sym\\":\\"" + f_auEsc(syminfo.tickerid) +\n'
        '     "\\",\\"tf\\":\\"" + f_auEsc(timeframe.period) + "\\",\\"bar_open\\":" + str.tostring(time) + ",\\"bar_close\\":" + str.tostring(time_close) +\n'
        '     ",\\"sent\\":" + str.tostring(timenow) + ",\\"side\\":\\"" + (side == 1 ? "LONG" : side == -1 ? "SHORT" : "") + "\\",\\"otype\\":\\"" + ot +\n'
        '     "\\",\\"px\\":" + f_auNum(px) + ",\\"sl\\":" + f_auNum(sl) + ",\\"tp\\":" + f_auNum(tp) + ",\\"o\\":" + f_auNum(open) +\n'
        '     ",\\"h\\":" + f_auNum(high) + ",\\"l\\":" + f_auNum(low) + ",\\"c\\":" + f_auNum(close) + ",\\"info\\":\\"" + f_auEsc(info) + "\\"}"\n'
        "\n"
        "// JSON イベントを 1 回だけ送る (自動化出力 ON のとき)。表示・売買・状態には触れない。戻り値 = 送信したか\n"
        "//  AU-5: キー生成・重複検索・JSON 生成・配列更新は、明示的な if の内側 (リアルタイムかつ出力 ON) だけで行う (and の短絡評価に頼らない)。\n"
        "//  過去足では何もしない (外部通知は過去足では発火しないため。売買・取引 ID の状態計算は呼び出し側で従来どおり行う)\n"
        "f_auEmit(string ev, string tid, int rank, int side, string ot, float px, float sl, float tp, string info) =>\n"
        "    bool sent = false\n"
        "    if auJson and barstate.isrealtime\n"
        '        string key = AU_SID + "|" + ev + "|" + tid + "|" + str.tostring(time_close)\n'
        "        if not array.includes(auSent, key)\n"
        "            array.push(auSent, key)\n"
        f"            if array.size(auSent) > {KEEP}\n"
        "                array.shift(auSent)\n"
        "            alert(f_auJson(ev, tid, rank, side, ot, px, sl, tp, info, key), alert.freq_all)\n"
        "            sent := true\n"
        "    sent\n"
        "\n"
        "// AU-5: 通知だけに必要な処理 (呼び出し引数の文字列生成を含む) を行う足か。過去足・出力 OFF では false (毎足の真偽値 1 個だけ)\n"
        "bool auLive = auJson and barstate.isrealtime\n")


_EDITS = None


def edits():
    global _EDITS
    if _EDITS is not None:
        return _EDITS
    src = source()
    _EDITS = [
        ("header", HDR_OLD, HDR_NEW),
        ("name", '     title                  = "Zone Strategy XAU",\n', '     title                  = "Zone Strategy XAU Auto",\n'),
        ("name", '     shorttitle             = "ZONE-ST",\n', '     shorttitle             = "ZONE-ST-AU",\n'),
        ("input", '     "アラートの ON / OFF とは独立。約定通知ではない。過去足にも表示し、最新 50 個を保持 (古い順に削除)。")\n',
         '     "アラートの ON / OFF とは独立。約定通知ではない。過去足にも表示し、最新 50 個を保持 (古い順に削除)。")\n' + AU_INPUTS),
        ("fns", "            label.delete(array.shift(stConfLbls))\n    mk\n", "            label.delete(array.shift(stConfLbls))\n    mk\n" + _au_fns(src)),
        ("human", '        alert(f_stAlertMsg("確定", side, ePx, sl, tp, isLim, isSats), alert.freq_all)\n    send\n',
         '        if not auJson     // AU: JSON 出力 ON ではこのコピーの文章アラートを送らない (JSON の ENTRY は発注分岐で送る)\n'
         '            alert(f_stAlertMsg("確定", side, ePx, sl, tp, isLim, isSats), alert.freq_all)\n    send\n'),
        ("human", '    alert(f_stAlertMsg("仮", pSide, pPx, pSL, pTP, not stSats and stModeA, stSats), alert.freq_once_per_bar)\n',
         '    if auJson     // AU: 仮は JSON (同じ判定・同じ重複防止)。OFF なら通常版と同じ文章\n'
         '        f_auEmit("PROV", "P" + str.tostring(time), 1, pSide, pPath == 3 and stModeA ? "LIMIT" : "MARKET", pPx, pSL, pTP,\n'
         '             pPath == 1 ? "SATS_PULL" : pPath == 2 ? "SATS_NOW" : "CURRENT")\n'
         '    else\n'
         '        alert(f_stAlertMsg("仮", pSide, pPx, pSL, pTP, not stSats and stModeA, stSats), alert.freq_once_per_bar)\n'),
        ("event", I12 + "oState  := 2\n" + I12 + "fillNow := true\n",
         I12 + "oState  := 2\n" + I12 + "fillNow := true\n"
         + I12 + 'f_auEmit("TV_FILL", auTid, 30, oSide, "", oFill, oSL, na, "virtual_fill")     // AU\n'),
        ("event", I12 + "// 約定した足の中で SL まで成立した\n" + I12 + "map.put(stUsed, oTrack, true)\n" + I12 + "oState := 0\n",
         I12 + "// 約定した足の中で SL まで成立した\n" + I12 + "map.put(stUsed, oTrack, true)\n" + I12 + "oState := 0\n"
         + I12 + 'f_auEmit("TV_CLOSED", auTid, 70, oSide, "", strategy.closedtrades.exit_price(ct - 1), oSL, oTP0, "filled_and_closed_in_bar")     // AU\n'),
        ("event", I8 + "else if not oLimit\n" + I12 + "strategy.cancel(oEid)\n" + I12 + "strategy.cancel(oXid)\n" + I12 + "oState := 0\n",
         I8 + "else if not oLimit\n" + I12 + "strategy.cancel(oEid)\n" + I12 + "strategy.cancel(oXid)\n" + I12 + "oState := 0\n"
         + I12 + 'f_auEmit("CANCEL", auTid, 20, oSide, "MARKET", na, oSL, na, "market_entry_not_filled")     // AU\n'),
        ("event", "    else if oState >= 2 and strategy.opentrades == 0\n" + I8 + "oState := 0\n",
         "    else if oState >= 2 and strategy.opentrades == 0\n" + I8 + "oState := 0\n"
         + I8 + 'f_auEmit("TV_FLAT", auTid, 90, oSide, "", strategy.closedtrades > 0 ? strategy.closedtrades.exit_price(strategy.closedtrades - 1) : na, oStop, oTP, "virtual_position_closed")     // AU\n'),
        ("event", I12 + "oTP   := oTP0\n" + I12 + "oStop := oSL\n" + I12 + "strategy.exit(oXid, oEid, stop = oStop, limit = oTP)\n",
         I12 + "oTP   := oTP0\n" + I12 + "oStop := oSL\n" + I12 + "strategy.exit(oXid, oEid, stop = oStop, limit = oTP)\n"
         + I12 + 'f_auEmit("TP_SET", auTid, 40, oSide, "", oFill, oStop, oTP, "sats_tp0")     // AU\n'),
        ("event", I12 + "strategy.close(oEid)\n" + I12 + "oState := 3\n" + I12 + "pwNBad += 1\n",
         I12 + "strategy.close(oEid)\n" + I12 + "oState := 3\n" + I12 + "pwNBad += 1\n"
         + I12 + 'f_auEmit("CLOSE_REQ", auTid, 60, oSide, "MARKET", oFill, oSL, oTP0, "bad_fill_side")     // AU\n'),
        ("event", I12 + "if skipRR\n" + I16 + "strategy.close(oEid)\n" + I16 + "oState := 3\n",
         I12 + "if skipRR\n" + I16 + "strategy.close(oEid)\n" + I16 + "oState := 3\n"
         + I16 + 'f_auEmit("CLOSE_REQ", auTid, 60, oSide, "MARKET", oFill, oSL, tp, "rr_below_min")     // AU\n'),
        ("event", I16 + "oTP   := tp\n" + I16 + "oStop := oSL\n" + I16 + "strategy.exit(oXid, oEid, stop = oStop, limit = oTP)\n",
         I16 + "oTP   := tp\n" + I16 + "oStop := oSL\n" + I16 + "strategy.exit(oXid, oEid, stop = oStop, limit = oTP)\n"
         + I16 + 'f_auEmit("TP_SET", auTid, 40, oSide, "", oFill, oStop, oTP, "fill_rr")     // AU\n'),
        ("event", I8 + "else\n" + I12 + "strategy.close(oEid)\n" + I12 + "oState := 3\n\n    // (2c)",
         I8 + "else\n" + I12 + "strategy.close(oEid)\n" + I12 + "oState := 3\n"
         + I12 + 'f_auEmit("CLOSE_REQ", auTid, 60, oSide, "MARKET", oFill, oSL, na, "risk_le_0")     // AU\n\n    // (2c)'),
        ("event", I12 + "oBE   := true\n" + I12 + "oStop := oFill\n" + I12 + "strategy.exit(oXid, oEid, stop = oStop, limit = oTP)\n",
         I12 + "oBE   := true\n" + I12 + "oStop := oFill\n" + I12 + "strategy.exit(oXid, oEid, stop = oStop, limit = oTP)\n"
         + I12 + 'f_auEmit("BE_MOVE", auTid, 50, oSide, "", oFill, oStop, oTP, "breakeven_tv_fill_based")     // AU\n'),
        ("event", I8 + "oState    := 0\n" + I8 + "cancelBar := true\n",
         I8 + "oState    := 0\n" + I8 + "cancelBar := true\n"
         + I8 + 'f_auEmit("CANCEL", auTid, 20, oSide, oLimit ? "LIMIT" : "MARKET", oL, oSL, na, not stSessOK ? "out_of_session" : "limit_zone_invalid")     // AU\n'),
        ("event", I12 + "pwEv        := why\n",
         I12 + "pwEv        := why\n"
         + I12 + 'f_auEmit("WAIT_END", "W" + str.tostring(pwEndT), 95, pwSide, "", pwP0, pwSL0, pwTP0, why == -1 ? "expired" : "sl0_reached")     // AU\n'),
        ("event", I20 + "f_stConfLabel(pwSide, close, pwSL0, pwTP0, false, true)     // XA-23 確定ラベル: 確定アラートと同じ値\n",
         I20 + "f_stConfLabel(pwSide, close, pwSL0, pwTP0, false, true)     // XA-23 確定ラベル: 確定アラートと同じ値\n"
         + I20 + 'auTid := "T" + str.tostring(time_close)     // AU: 注文意図の取引 ID (判断足の終了時刻)\n'
         + I20 + 'f_auEmit("ENTRY", auTid, 10, pwSide, "MARKET", close, pwSL0, pwTP0, "SATS_PULL;wid=W" + str.tostring(pwEndT))     // AU\n'),
        ("event", I24 + "f_stConfLabel(side, close, pSL, tpRef, false, true)     // XA-23 確定ラベル: 確定アラートと同じ値\n",
         I24 + "f_stConfLabel(side, close, pSL, tpRef, false, true)     // XA-23 確定ラベル: 確定アラートと同じ値\n"
         + I24 + 'auTid := "T" + str.tostring(time_close)     // AU\n'
         + I24 + 'f_auEmit("ENTRY", auTid, 10, side, "MARKET", close, pSL, tpRef, "SATS_NOW")     // AU\n'),
        ("event", I20 + "f_stPvRelease(c.track)     // XA-22: 正式な待機準備 -> この Track の仮通知キーを解除 (新しい待機は初回を通知)\n",
         I20 + "f_stPvRelease(c.track)     // XA-22: 正式な待機準備 -> この Track の仮通知キーを解除 (新しい待機は初回を通知)\n"
         + I20 + 'f_auEmit("WAIT_START", "W" + str.tostring(time_close), 5, side, "", ref, pSL, tpRef, "sats_wait")     // AU\n'),
        ("event", I16 + "f_stConfLabel(side, stModeA ? oL : close, pSL, tpRef, stModeA, false)     // XA-23 確定ラベル: 確定アラートと同じ値\n",
         I16 + "f_stConfLabel(side, stModeA ? oL : close, pSL, tpRef, stModeA, false)     // XA-23 確定ラベル: 確定アラートと同じ値\n"
         + I16 + 'auTid := "T" + str.tostring(time_close)     // AU\n'
         + I16 + 'f_auEmit("ENTRY", auTid, 10, side, stModeA ? "LIMIT" : "MARKET", stModeA ? oL : close, pSL, tpRef, "CURRENT")     // AU\n'),
        ("event", "    stTpUpPrev := tpUp\n    stTpDnPrev := tpDn\n",
         "    stTpUpPrev := tpUp\n    stTpDnPrev := tpDn\n"
         "    if auBar and auLive     // AU-2: 確定5分足ごとの OHLC と、この足の処理後の疑似建玉 (状態 / 停止値 / TP)。売買は変えない (AU-5: リアルタイムだけ)\n"
         '        f_auEmit("BAR", "B" + str.tostring(time_close), 98, oState >= 1 ? oSide : 0, "", close, oState >= 1 ? oStop : na, oState == 2 ? oTP : na,\n'
         '             "tv_state=" + str.tostring(oState) + ";tv_tid=" + auTid + ";tv_be=" + (oBE ? "1" : "0") + ";tv_fill=" + f_auNum(oState >= 2 ? oFill : na))\n'),
    ]
    _EDITS = [(k, a, _guard_calls(b) if k == "event" else b) for k, a, b in _EDITS]
    return _EDITS


GUARD = "if auLive     // AU-5: 通知だけの処理 (引数の文字列生成を含む) はリアルタイムで送るときだけ\n"


def _guard_calls(text):
    """AU-5: put every single-line event emit of an inserted block under `if auLive` (the arguments are built only there);
    the auTid assignments (trade state) stay outside, unchanged."""
    out = []
    for line in text.splitlines(keepends=True):
        body = line.lstrip(" ")
        if body.startswith("f_auEmit(") and line.rstrip("\n").endswith("// AU"):
            ind = line[:len(line) - len(body)]
            out.append(ind + GUARD)
            out.append(ind + "    " + body)
        else:
            out.append(line)
    return "".join(out)


# every file AU-1 / AU-2 add (the older fixtures' "other files unchanged" checks accept exactly these through ok())
NEW_FILES = ("tests/au_build.py", "tests/au_sim.py", "tests/aur_sim.py", AUTO_PATH, CFG_FIELDS_PATH, "automation/xau_short/README_ja.md",
             "automation/xau_short/receiver/.gitignore", "automation/xau_short/receiver/config.example.json",
             "automation/xau_short/receiver/samples/bad_cases.jsonl", "automation/xau_short/receiver/samples/make_samples.py",
             "automation/xau_short/receiver/samples/normal_flow.jsonl", "automation/xau_short/receiver/show_log.ps1",
             "automation/xau_short/receiver/start_receiver.ps1", "automation/xau_short/receiver/stop_receiver.ps1",
             "automation/xau_short/receiver/test_samples.ps1", "automation/xau_short/receiver/xau_receiver.py",
             # stage 3 (demo EA): bridge, EA, design note and their fixtures
             "automation/xau_short/STAGE3_ja.md", "automation/xau_short/bridge/.gitignore", "automation/xau_short/bridge/ea_bridge.py",
             "automation/xau_short/bridge/bridge_config.example.json", "automation/xau_short/bridge/make_test_entry.py",
             "automation/xau_short/ea/XauShortDemoEA.mq5", "tests/ea_model.py", "tests/eab_sim.py", "tests/eam_sim.py",
             # later layer XA-24 (Gold run-time reduction): its new port / fixture (the Pine files are accepted through xa_build.unapply24)
             "tests/pf_model.py", "tests/pf_sim.py", "XAU_PERF_XA24_ja.md",
             # later layer MSL-1 (Max SL Distance filter): its generator / fixture (the Pine files are accepted through msl_build.unapply)
             "tests/msl_build.py", "tests/msl_sim.py",
             # later layer BEL-1 (breakeven exit lock): its generator / fixture (the Pine files through bel_build.unapply)
             "tests/bel_build.py", "tests/bel_sim.py",
             # later layer GJA-1 (GBPJPY adopted defaults): its generator / fixture (the Pine file through gja_build.unapply)
             "tests/gja_build.py", "tests/gja_sim.py",
             # later layer UJA-1 (USDJPY adopted defaults): its generator / fixture (the Pine file through uja_build.unapply)
             "tests/uja_build.py", "tests/uja_sim.py",
             # later layer EUA-1 (EURUSD adopted defaults): its generator / fixture (the Pine file through eua_build.unapply)
             "tests/eua_build.py", "tests/eua_sim.py")


def ok(path):
    """AU accounts for this path exactly: one of its new files, or an untracked directory entry 'automation/' or 'automation/.../'
    while every file in it is one of them (git status lists a new directory as one entry before it is committed)."""
    if path in NEW_FILES:
        return True
    if path == "automation/" or (path.startswith("automation/") and path.endswith("/")):
        found = []
        for d, dirs, files in os.walk(os.path.join(ROOT, path.rstrip("/"))):
            dirs[:] = [x for x in dirs if x not in ("__pycache__", "data")]
            found += [os.path.relpath(os.path.join(d, f), ROOT).replace(os.sep, "/") for f in files]
        return bool(found) and all(f in NEW_FILES for f in found)
    return False


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


def build():
    return _apply(source(), edits())


def strip(text):
    """reverse the AU edits exactly (-> the normal Short Strategy); None when not exact."""
    return _revert(text, edits())


def cfg_fields_json():
    inc = [f for f in cfg_fields() if f["included"]]
    return json.dumps({"schema": SCHEMA, "sid": SID, "cfg_version": CFG_VERSION,
                       "format": "cfg = cfg_version + '|' + the included values joined by '|' in this order (bool 1/0, int as is, "
                                 "float with up to 10 decimals, strings as is), then JSON-escaped",
                       "included_order": [f["name"] for f in inc], "fields": cfg_fields()}, ensure_ascii=False, indent=1) + "\n"


if __name__ == "__main__":
    p = os.path.join(ROOT, AUTO_PATH)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w", encoding="utf-8").write(build())
    open(os.path.join(ROOT, CFG_FIELDS_PATH), "w", encoding="utf-8").write(cfg_fields_json())
    print("written", AUTO_PATH, CFG_FIELDS_PATH)
