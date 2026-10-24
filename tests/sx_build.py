"""SX-1 — the Gold SATS / filter / breakeven features (XA-7 .. XA-15) rolled out to the BTCUSD / USDJPY / GBPJPY / EURUSD /
GBPUSD Strategies (Strategy only; Engine / Visual / Gold / imports unchanged, no Library re-publish).

Each Strategy == its file at BASE_REV + EDITS(cur) (exact (old, new) replacements, each old once). The edits are added to the
current Strategy of each symbol (not a copy of the Gold file): Entry Timing Current / SATS Pullback (prep at the shared order
point of Entry A-D: A = the limit price, B / C / D = the confirmed close; no order), the XA-9 wait (limit / SL0 cancels only,
touch record, line kind fixed and followed, rebound A / B), the XA-11 body / near switches (near distance in pips for FX:
JPY 0.01 / USD pairs 0.0001, USD for BTC), the XA-13 all-selected-timeframes opposite-band filter (D / 240 / 60 / 15 via
request.security(f_satTfState() = state[1], lookahead_on), 5m = satBand), the XA-15 breakeven trigger mode, the XA-8 actual
RR (both fill paths), the data window and markers, and SATS provisional / confirmed alerts and labels (provisional: a
read-only f_satProvEval on the forming 5M bar instead of the Current provisional evaluation; confirmed: at the SATS
strategy.entry, with the existing once-per-bar guards). Every new input defaults to the neutral / Current value, so the
default (Current + Fixed Distance + all OFF) keeps each symbol's orders, quantity and alerts.
strip(path, text) reverses the edits exactly (None when not exact); unapply() leaves a text without them unchanged.
"""
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_REV = "443c139"
CUR = {
    "BTCUSD": dict(path="ZoneStrategyBTCUSD.pine", unit="1.0", lbl="USD", step="1.0",
                   note="BTCUSD: USD の価格差 (pips 換算なし)"),
    "USDJPY": dict(path="ZoneStrategyUSDJPY.pine", unit="0.01", lbl="pips", step="0.5", note="USDJPY: 1 pip = 0.01 円"),
    "GBPJPY": dict(path="ZoneStrategyGBPJPY.pine", unit="0.01", lbl="pips", step="0.5", note="GBPJPY: 1 pip = 0.01 円"),
    "EURUSD": dict(path="ZoneStrategyEURUSD.pine", unit="0.0001", lbl="pips", step="0.5", note="EURUSD: 1 pip = 0.0001"),
    "GBPUSD": dict(path="ZoneStrategyGBPUSD.pine", unit="0.0001", lbl="pips", step="0.5", note="GBPUSD: 1 pip = 0.0001"),
}
FILES = tuple(v["path"] for v in CUR.values())
BY_PATH = {v["path"]: k for k, v in CUR.items()}
# every file SX-1 touches: the five Strategies, its new generator / fixture, and the older fixtures / generators whose file
# reads now revert SX-1 first (their edits are recorded exactly in cad_adapt.LATER; cad_adapt.ok accepts them only then)
TOUCHED = FILES + ("tests/sx_build.py", "tests/sxs_sim.py", "tests/cad_build.py", "tests/cad_adapt.py", "tests/uj_build.py",
                   "tests/uj_sim.py", "tests/ujl_sim.py", "tests/ujt_sim.py", "tests/bte_build.py", "tests/xa_sim.py",
                   "tests/xae_sim.py", "tests/xas_sim.py", "tests/cad_sim.py", "tests/uj3_adapt.py", "tests/btc_sim.py",
                   "tests/sx2_build.py", "tests/sx2s_sim.py")     # + the later SX-2 layer (new files)
SATS_FN = open(os.path.join(ROOT, "tests", "sats_src", "f_satBand.txt"), encoding="utf-8").read()


def _hdr(c):
    return (
        "// ============================================================================\n"
        "//  SX-1: ゴールド版 (XA-7 〜 XA-15) の SATS Pullback / 逆方向一致フィルター / 建値 Trigger 方式をこの Strategy に追加\n"
        "//  (生成: tests/sx_build.py)。初期値は Current・Fixed Distance・全 OFF (近接 0) = 変更前の売買・通知のまま (比較用。\n"
        "//  最適値ではない)。SATS Pullback: 各 Entry Mode (A〜D) が発注する地点で待機を準備し (A = 指値価格・指値注文なし /\n"
        "//  B・C・D = 確定足の終値)、次の 5分足以降に SATS 線 (足 t-1 の確定値) への接触 / 近接と終値の戻り (反発 A / B) で成行。\n"
        "//  取消は期限 (実時間) と SL0 到達だけ。SL0 / TP0 は準備時に固定。仮アラート / ラベルは待機中の形成中 5分足の読取専用評価、\n"
        "//  確定は SATS の strategy.entry で 1 回 (待機開始・見送りでは出さない)。" + c["note"] + "。成績への影響は未確認。\n")


def _inputs(c):
    return (
        'var string G_STW = "03 · Strategy Entry Timing (SATS)"\n'
        'stTiming = input.string("Current", "Entry Timing", options = ["Current", "SATS Pullback"], group = G_STW,\n'
        '     tooltip = "Current (初期): 変更前の発注方式。\\n" +\n'
        '     "SATS Pullback: 選択した Entry Mode (A〜D) が発注する条件を満たした足で発注せず待機を始め、次の 5分足以降に SATS 線\\n" +\n'
        '     "(LINE1 / LINE2 / STB、足 t-1 の確定値) への接触と終値での戻りを確認してから成行で発注する。SL0 / TP0 は準備時に固定。\\n" +\n'
        '     "P0: A は元の指値価格 (指値注文は出さない) / B・C・D はその確定足の終値。D は既存の 1分足 BOS 確認後に待機を始める。")\n'
        'stSatsWait = input.int(240, "SATS · 待機期限 (分)", minval = 1, group = G_STW,\n'
        '     tooltip = "準備した 5分足の終了時刻からの実時間。この分数以上になった確定評価時点で取消 (週末・欠損・時間帯外も時計は止めない)。\\n" +\n'
        '     "取消は期限と SL0 到達だけ (準備後は Zone の Strong 資格・Track を再審査しない)。")\n'
        'stSatsShow = input.bool(false, "SATS · 線を表示", group = G_STW)\n'
        'stSatsBody = input.bool(false, "SATS · 反発確認足の陽線／陰線を要求", group = G_STW,\n'
        '     tooltip = "比較用 (初期 OFF)。ON: 発注を判断する 5分足自身が Long は close > open / Short は close < open (同値足は不成立)。\\n" +\n'
        '     "その足で反発 A または B と同時に成立したときだけ発注する。不成立でも待機と接触記録は残す (過去の反発は保存しない)。")\n'
        'stSatsNear = input.bool(false, "SATS · 近接を接触扱い", group = G_STW,\n'
        '     tooltip = "比較用 (初期 OFF)。ON: 実接触 (low <= L <= high) に加え、線 L (足 t-1 の確定値) の手前までの接近も接触とする。\\n" +\n'
        '     "Short: high < L かつ L − high <= 許容距離 / Long: low > L かつ low − L <= 許容距離。終値の戻りは元の線 L で判定する。")\n'
        'stSatsNearD = input.float(0.0, "SATS · 近接許容距離 (' + c["lbl"] + ')", minval = 0.0, step = ' + c["step"] + ', group = G_STW,\n'
        '     tooltip = "' + c["note"] + '。初期 0 = 中立な比較開始値 (実接触だけと同じ結果。最適値ではない)。")\n'
        "float SX_NEAR_UNIT = " + c["unit"] + "     // 近接許容距離の 1 単位の価格差\n"
        "float stSatsNearPx = stSatsNearD * SX_NEAR_UNIT\n"
        'stSatsFD  = input.bool(false, "SATS 逆方向一致 · 日足を判定に使用", group = G_STW,\n'
        '     tooltip = "比較用 (5 項目とも初期 OFF。全て OFF = フィルターなし)。SATS 反発後の最終発注判定で、ON にした時間足が\\n" +\n'
        '     "すべて逆方向のバンド (Short: 全て青 / Long: 全て赤) のときだけ見送る。無点灯・反対色・計算未成立が 1 つでもあれば見送らない。\\n" +\n'
        '     "バンド = その時間足の終値が LINE1 / LINE2 / STB の 3 本すべてより上 (青) / 下 (赤)。上位足は直近の確定足の状態だけを使う。")\n'
        'stSatsF4  = input.bool(false, "SATS 逆方向一致 · 4時間足を判定に使用", group = G_STW)\n'
        'stSatsF1  = input.bool(false, "SATS 逆方向一致 · 1時間足を判定に使用", group = G_STW)\n'
        'stSatsF15 = input.bool(false, "SATS 逆方向一致 · 15分足を判定に使用", group = G_STW)\n'
        'stSatsF5  = input.bool(false, "SATS 逆方向一致 · 5分足を判定に使用", group = G_STW,\n'
        '     tooltip = "5分足は発注を判断するその 5分足の SATS バンド (この Strategy の SATS 計算をそのまま使う)。")\n')


BE_INPUTS = (
    'stBEMode = input.string("Fixed Distance", "Breakeven Trigger Mode", options = ["Fixed Distance", "Risk Multiple", "TP Progress"], group = G_STT,\n'
    '     tooltip = "比較用 (初期 Fixed Distance = 従来の固定幅 Breakeven Trigger)。選択した方式の入力だけを使う。\\n" +\n'
    '     "Risk Multiple: 1R = 実約定価格から初期 SL までの距離。含み益が 1R × 倍率に届いたら建値へ。\\n" +\n'
    '     "TP Progress: 実約定価格から実際に設定した TP までの距離 × 比率 (0.5TP = TP までの半分進んだ)。TP 価格や TP Fixed RR に掛けない。\\n" +\n'
    '     "RR 方式 / TP 比率方式でも判断・注文更新は従来の確定 5分足処理 (Long は high / Short は low、等値で成立、次の足から有効)。")\n'
    'stBER = input.float(1.0, "Breakeven Trigger (R)", minval = 0.1, step = 0.1, group = G_STT)\n'
    'stBETp = input.float(0.5, "Breakeven Trigger (TP Ratio)", minval = 0.05, maxval = 1.0, step = 0.05, group = G_STT)\n')

SATS_BLOCK = (
    "\n"
    "// ---- SX-1 · SATS (SAT BAND LINE1 / LINE2 / STB) -----------------------------------------------------------------------\n"
    "//  f_satBand() は SATS 移植元 (SAT BAND Reconstruction Test) の関数を一字一句そのまま使う (tests/sats_src/f_satBand.txt、\n"
    "//  ゴールド版と同じ)。待機の有無にかかわらず毎バー グローバルで計算する。色・バンド状態は逆方向一致フィルター以外に使わない。\n"
    'bool stSats = stTiming == "SATS Pullback"\n'
    "\n" + SATS_FN + "\n"
    "[satL1, satL2, satStb, satD1, satD2, satSD, satBand, satBasis, satCommon, satAtr, satA1, satA2] = f_satBand()\n"
    "\n"
    "// 時間足ごとの SATS バンド状態 (1 青 / -1 赤 / 0 無点灯 / na 計算未成立 = LINE1 / LINE2 / STB のどれかが na)。\n"
    "//  日足 / 4H / 1H / 15分 は各時間足の履歴上で f_satBand 全体を計算し、request 内で [1] + lookahead_on = 直近の確定足の状態だけ\n"
    "//  (形成途中の上位足・未来の値は使わない)。毎足・無条件に取得する。5分足は既存の satBand (この足の値)。\n"
    "f_satTfState() =>\n"
    "    [l1, l2, sb, d1, d2, sd, st, b, cm, at, a1, a2] = f_satBand()\n"
    "    int s = (na(l1) or na(l2) or na(sb)) ? na : st\n"
    "    s[1]\n"
    'int satTfD  = request.security(syminfo.tickerid, "D",   f_satTfState(), lookahead = barmerge.lookahead_on)\n'
    'int satTf4  = request.security(syminfo.tickerid, "240", f_satTfState(), lookahead = barmerge.lookahead_on)\n'
    'int satTf1  = request.security(syminfo.tickerid, "60",  f_satTfState(), lookahead = barmerge.lookahead_on)\n'
    'int satTf15 = request.security(syminfo.tickerid, "15",  f_satTfState(), lookahead = barmerge.lookahead_on)\n'
    "int satTf5  = (na(satL1) or na(satL2) or na(satStb)) ? na : satBand\n"
    "\n"
    "// 選択した時間足 (1 つ以上) がすべて want の状態なら true。未選択は影響しない。選択した足に 0 / 反対色 / na が 1 つでもあれば false\n"
    "f_satAllAgainst(int want) =>\n"
    "    bool anySel = false\n"
    "    bool allHit = true\n"
    "    if stSatsFD\n"
    "        anySel := true\n"
    "        allHit := allHit and not na(satTfD) and satTfD == want\n"
    "    if stSatsF4\n"
    "        anySel := true\n"
    "        allHit := allHit and not na(satTf4) and satTf4 == want\n"
    "    if stSatsF1\n"
    "        anySel := true\n"
    "        allHit := allHit and not na(satTf1) and satTf1 == want\n"
    "    if stSatsF15\n"
    "        anySel := true\n"
    "        allHit := allHit and not na(satTf15) and satTf15 == want\n"
    "    if stSatsF5\n"
    "        anySel := true\n"
    "        allHit := allHit and not na(satTf5) and satTf5 == want\n"
    "    anySel and allHit\n"
    "bool satSkipS = f_satAllAgainst(1)      // Short を見送る: 選択した時間足がすべて青\n"
    "bool satSkipL = f_satAllAgainst(-1)     // Long を見送る: 選択した時間足がすべて赤\n"
    "\n"
    "// 足 t の判定に使う線: 足 t-1 で確定した 3 本の値と前足終値だけで選ぶ (足 t の値は使わない)。\n"
    "//  Long: SL0 < L < P0 かつ L < 前足終値 / Short: SL0 > L > P0 かつ L > 前足終値。前足終値に最も近い線、同距離は LINE1 -> LINE2 -> STB。\n"
    "//  戻り値 [線の種類 (1 / 2 / 3、無ければ 0), 線の価格 (無ければ na)]。na の線は候補にしない。\n"
    "f_satPick(int side, float p0, float sl0, float pc, float l1, float l2, float l3) =>\n"
    "    int   bk = 0\n"
    "    float bp = na\n"
    "    float bd = na\n"
    "    for k = 1 to 3\n"
    "        float v = k == 1 ? l1 : k == 2 ? l2 : l3\n"
    "        bool ok = not na(v) and not na(pc) and (side == 1 ? (v > sl0 and v < p0 and v < pc) : (v < sl0 and v > p0 and v > pc))\n"
    "        if ok\n"
    "            float d = math.abs(pc - v)\n"
    "            if bk == 0 or d < bd\n"
    "                bk := k\n"
    "                bp := v\n"
    "                bd := d\n"
    "    [bk, bp]\n"
    "\n"
    "// 実 RR = side × (TP0 − 実約定) ÷ side × (実約定 − SL0) (実現損益の R 倍率ではない)。戻り値 [RR, 理由] (0 = 計算可 /\n"
    "//  1 = 約定が SL0 以遠 (risk <= 0) / 2 = TP0 が約定価格の先にない (reward <= 0) / 3 = 価格が na)。理由 0 以外の RR は na\n"
    "f_satRR(int side, float fillPx, float sl0, float tp0) =>\n"
    "    float rr  = na\n"
    "    int   why = 0\n"
    "    if na(fillPx) or na(sl0) or na(tp0)\n"
    "        why := 3\n"
    "    else\n"
    "        float risk = side * (fillPx - sl0)\n"
    "        float rew  = side * (tp0 - fillPx)\n"
    "        if risk <= 0\n"
    "            why := 1\n"
    "        else if rew <= 0\n"
    "            why := 2\n"
    "        else\n"
    "            rr := rew / risk\n"
    "    [rr, why]\n")

BE_FN = (
    "\n"
    "// SX-1: 建値移動に必要な含み益幅。Fixed Distance = stBEDist (従来どおり、距離検査を追加しない) / Risk Multiple = 初期リスク距離\n"
    "//  side × (実約定価格 − 初期 SL) × R / TP Progress = side × (TP − 実約定価格) × 比率。新方式は基準距離が na / 0 以下なら na (移動しない)\n"
    "f_beTrig(int side, float fillPx, float sl, float tp) =>\n"
    "    float r  = side * (fillPx - sl)\n"
    "    float tg = side * (tp - fillPx)\n"
    '    stBEMode == "Risk Multiple" ? (not na(r) and r > 0 ? r * stBER : na) :\n'
    '     stBEMode == "TP Progress" ? (not na(tg) and tg > 0 ? tg * stBETp : na) : stBEDist\n')

PW_VARS = (
    "// SX-1 SATS Pullback の待機 (全体で 1 件) と確認用の記録\n"
    "var int   pwState  = 0       // 0 = 待機なし / 1 = 待機中\n"
    "var int   pwSide   = 0\n"
    "var int   pwTrack  = -1\n"
    "var int   pwBar    = na\n"
    "var int   pwEndT   = na      // 準備した 5分足の終了時刻 (期限の起点)\n"
    "var float pwP0     = na\n"
    "var float pwSL0    = na\n"
    "var float pwTP0    = na\n"
    "var float oTP0     = na      // SATS で発注した注文の TP0 (約定確認時の TP)\n"
    "var float pwRRPrep = na\n"
    "var float pwRRPlan = na\n"
    "var float pwRRFill = na\n"
    "var int   pwNPrep  = 0\n"
    "var int   pwNOrder = 0\n"
    "var int   pwNExp   = 0\n"
    "var bool  pwTouched  = false   // 接触済み (反発待ち)\n"
    "var int   pwTouchK   = 0       // 接触した線の種類 (1 LINE1 / 2 LINE2 / 3 STB)\n"
    "var int   pwTouchBar = na      // 接触した足\n"
    "var int   pwNTouchPrep = 0     // 接触を経験した準備の件数 (同じ準備で何度触れても 1 件)\n"
    "var int   pwNOrdSame   = 0     // 同じ足の接触・反発 (A) で発注した件数 (近接 ON では近接を接触扱いにした同一足反発を含む)\n"
    "var int   pwNOrdLater  = 0     // 接触後の別の足の戻り (B) で発注した件数\n"
    "var int   pwNSL    = 0\n"
    "var int   pwNBad   = 0\n"
    "var int   pwRRWhy  = na      // 実 RR の理由 (0 計算可 / 1 risk <= 0 / 2 reward <= 0 / 3 na)\n"
    "var int   pwNFill  = 0       // 実 RR を記録した SATS 約定の件数 (1 約定 1 回)\n"
    "var int   pwFillPath = 0     // 直近の記録経路 (1 = 約定後も保有中 / 2 = 約定足内で決済済み)\n"
    "int   pwEv    = 0          // この足のイベント: 1 = 準備 / 2 = 発注 / -1 期限 / -4 SL0 到達\n"
    "int   pwLineK = 0          // この足の判定に使った線 (1 = LINE1 / 2 = LINE2 / 3 = STB / 0 = なし)\n"
    "float pwLineP = na         // その線の価格 (足 t-1 の確定値)\n")

PROV_FN = (
    "// SX-1 SATS 仮評価 (読み取り専用)。待機中 (直前の確定時の状態) の SATS について、形成中の 5分足がこのまま確定したら発注するかを\n"
    "//  確定時の (3b) と同じ式で試算する: 期限 / SL0 到達 (取消) → 線の選択 (接触前は足 t-1 の線と前足終値で選び直し、接触後は\n"
    "//  記録した種類) → 接触 / 近接 (この足の値はローカルだけで、接触記録は書かない) → 反発 A / B → 陽線陰線 / 逆方向一致 (上位足は\n"
    "//  確定値) / 価格範囲 / 数量。待機・接触記録・件数・Track・注文状態は一切書き換えない。形成中の条件は確定までに消えることがある。\n"
    "//  戻り値: [方向 (0 = なし), 参照価格 (形成中の終値), SL0, TP0]\n"
    "f_satProvEval(float pc, float l1p, float l2p, float stbp) =>\n"
    "    int   side = 0\n"
    "    float ePx  = na\n"
    "    float sl   = na\n"
    "    float tp   = na\n"
    "    if stSats and pwState == 1 and bar_index > pwBar\n"
    "        bool cancel = time_close - pwEndT >= stSatsWait * 60000 or (pwSide == 1 ? low <= pwSL0 : high >= pwSL0)\n"
    "        if not cancel\n"
    "            int   lk = 0\n"
    "            float lp = na\n"
    "            if not pwTouched\n"
    "                [k0, v0] = f_satPick(pwSide, pwP0, pwSL0, pc, l1p, l2p, stbp)\n"
    "                lk := k0\n"
    "                lp := v0\n"
    "            else\n"
    "                lk := pwTouchK\n"
    "                lp := pwTouchK == 1 ? l1p : pwTouchK == 2 ? l2p : stbp\n"
    "            bool inRange   = lk != 0 and not na(lp) and (pwSide == 1 ? (lp > pwSL0 and lp < pwP0) : (lp < pwSL0 and lp > pwP0))\n"
    "            bool touchHit  = inRange and low <= lp and lp <= high\n"
    "            bool touchNear = stSatsNear and inRange and (pwSide == 1 ? (low > lp and low - lp <= stSatsNearPx) : (high < lp and lp - high <= stSatsNearPx))\n"
    "            bool touchNow  = touchHit or touchNear\n"
    "            bool rebA      = touchNow and (pwSide == 1 ? close > lp : close < lp)\n"
    "            bool rebB      = pwTouched and inRange and (pwSide == 1 ? (pc <= lp and close > lp) : (pc >= lp and close < lp))\n"
    "            bool priceOK   = pwSide == 1 ? (close > pwSL0 and close < pwP0) : (close < pwSL0 and close > pwP0)\n"
    "            bool bodyOK    = not stSatsBody or (pwSide == 1 ? close > open : close < open)\n"
    "            bool mtfOK     = not (pwSide == 1 ? satSkipL : satSkipS)\n"
    "            if (rebA or rebB) and bodyOK and mtfOK and priceOK and not na(f_stQty(pwSide, close, pwSL0))\n"
    "                side := pwSide\n"
    "                ePx  := close\n"
    "                sl   := pwSL0\n"
    "                tp   := pwTP0\n"
    "    [side, ePx, sl, tp]\n"
    "\n")

FILL_CLOSED_OLD = (
    "            // 約定した足の中で SL まで成立した\n"
    "            map.put(stUsed, oTrack, true)\n"
    "            oState := 0\n")
FILL_CLOSED_NEW = FILL_CLOSED_OLD + (
    "            if stSats     // SX-1: 決済済みの SATS 約定も実 RR を記録する (TP / 決済の注文は出さない)\n"
    "                [rrC, whyC] = f_satRR(oSide, strategy.closedtrades.entry_price(ct - 1), oSL, oTP0)\n"
    "                pwRRFill   := rrC\n"
    "                pwRRWhy    := whyC\n"
    "                pwNFill    += 1\n"
    "                pwFillPath := 2\n")

FILL_OLD = (
    "    // (2b) 約定を確認した足: 実約定価格から RR と TP を決める (約定した足の中では TP は無い)\n"
    "    if fillNow\n")
FILL_NEW = (
    "    // (2b) 約定を確認した足: 実約定価格から RR と TP を決める (約定した足の中では TP は無い)\n"
    "    // (2b') SX-1 SATS Pullback: TP は準備時の TP0 のまま (実約定価格から作り直さない)。設定は既存どおり約定確認時。\n"
    "    //   実約定が SL0 / TP0 の不適切な側 (risk <= 0 または TP0 までの距離 <= 0) なら TP を置かず成行決済 (正常約定として扱わない)\n"
    "    if fillNow and stSats\n"
    "        float riskS = oSide * (oFill - oSL)\n"
    "        float rewS  = oSide * (oTP0 - oFill)\n"
    "        [rrH, whyH] = f_satRR(oSide, oFill, oSL, oTP0)     // 実 RR の記録だけ (下の注文処理はゴールド版と同じ)\n"
    "        pwRRFill   := rrH\n"
    "        pwRRWhy    := whyH\n"
    "        pwNFill    += 1\n"
    "        pwFillPath := 1\n"
    "        if riskS > 0 and rewS > 0\n"
    "            oTP   := oTP0\n"
    "            oStop := oSL\n"
    "            strategy.exit(oXid, oEid, stop = oStop, limit = oTP)\n"
    "        else\n"
    "            strategy.close(oEid)\n"
    "            oState := 3\n"
    "            pwNBad += 1\n"
    "    else if fillNow\n")

BE_OLD = "        if oSide * (fav - oFill) >= stBEDist\n"
BE_NEW = (
    "        float beTrig = f_beTrig(oSide, oFill, oSL, oTP)     // SX-1: 選択した方式の Trigger 幅 (oFill / 初期 oSL / 設定した oTP)\n"
    "        if not na(beTrig) and oSide * (fav - oFill) >= beTrig\n")

WAIT_ANCHOR = "    // (4) 新規 Entry (注文が無く、取消をした足でなく、時間帯の中のときだけ)\n"
WAIT_BLOCK = (
    "    // (3b) SX-1 SATS Pullback の待機判定 (準備足の次の足から)。取消を反発より優先する\n"
    "    //   取消: 期限 (準備足の終了時刻からの実時間) / 固定 SL0 到達 だけ。元 Zone の Strong 資格・Track の存続 / 一致・候補一覧\n"
    "    //   からの脱落では取り消さない (保存した方向 / P0 / SL0 / TP0 を使い続ける)。取消だけでは使用済み Track にしない\n"
    "    //   接触前: 毎足、足 t-1 の確定線と前足終値から最寄りの適格線を選び直す。接触 (実接触 low <= L <= high、近接 ON なら線の手前\n"
    "    //   までの接近も) → 線の種類を記録。接触後: 記録した種類の線の足 t-1 確定値を毎足使う (選び替えない)。na / 範囲外の足は発注しない\n"
    "    //   反発: A = その足で接触して終値が戻る / B = 接触済みで、前足終値 <= L (Short は >=) かつ当足終値 > L (Short は <)\n"
    "    //   発注: 反発 A / B + 陽線陰線 (ON 時) + 逆方向一致で見送らない + SL0〜P0 の価格範囲 + 時間帯 + 注文なし + 数量 (この足の終値と SL0)\n"
    "    //   不成立・見送りでも待機と接触記録は残す (反発は保存しない)。確定アラート / ラベルは実際に発注したときだけ\n"
    "    bool  pwCancelBar = false\n"
    "    if stSats and pwState == 1 and bar_index > pwBar\n"
    "        int why = 0\n"
    "        if time_close - pwEndT >= stSatsWait * 60000\n"
    "            why := -1\n"
    "        else if pwSide == 1 ? low <= pwSL0 : high >= pwSL0\n"
    "            why := -4\n"
    "        if why != 0\n"
    "            pwState     := 0\n"
    "            pwCancelBar := true\n"
    "            pwEv        := why\n"
    "            pwNExp  += why == -1 ? 1 : 0\n"
    "            pwNSL   += why == -4 ? 1 : 0\n"
    "            pwTouched  := false\n"
    "            pwTouchK   := 0\n"
    "            pwTouchBar := na\n"
    "        else\n"
    "            int   lk = 0\n"
    "            float lp = na\n"
    "            if not pwTouched\n"
    "                [k0, v0] = f_satPick(pwSide, pwP0, pwSL0, close[1], satL1[1], satL2[1], satStb[1])\n"
    "                lk := k0\n"
    "                lp := v0\n"
    "            else\n"
    "                lk := pwTouchK\n"
    "                lp := pwTouchK == 1 ? satL1[1] : pwTouchK == 2 ? satL2[1] : satStb[1]\n"
    "            pwLineK := lk\n"
    "            pwLineP := lp\n"
    "            bool inRange   = lk != 0 and not na(lp) and (pwSide == 1 ? (lp > pwSL0 and lp < pwP0) : (lp < pwSL0 and lp > pwP0))\n"
    "            bool touchHit  = inRange and low <= lp and lp <= high\n"
    "            bool touchNear = stSatsNear and inRange and (pwSide == 1 ? (low > lp and low - lp <= stSatsNearPx) : (high < lp and lp - high <= stSatsNearPx))\n"
    "            bool touchNow  = touchHit or touchNear\n"
    "            bool rebA      = touchNow and (pwSide == 1 ? close > lp : close < lp)\n"
    "            bool rebB      = pwTouched and inRange and (pwSide == 1 ? (close[1] <= lp and close > lp) : (close[1] >= lp and close < lp))\n"
    "            if touchNow and not pwTouched\n"
    "                pwTouched    := true\n"
    "                pwTouchK     := lk\n"
    "                pwTouchBar   := bar_index\n"
    "                pwNTouchPrep += 1\n"
    "            bool priceOK = pwSide == 1 ? (close > pwSL0 and close < pwP0) : (close < pwSL0 and close > pwP0)\n"
    "            bool bodyOK  = not stSatsBody or (pwSide == 1 ? close > open : close < open)\n"
    "            bool mtfOK   = not (pwSide == 1 ? satSkipL : satSkipS)\n"
    "            if (rebA or rebB) and bodyOK and mtfOK and priceOK and stSessOK and oState == 0\n"
    "                float q = f_stQty(pwSide, close, pwSL0)\n"
    "                if not na(q)\n"
    "                    oSeq    += 1\n"
    "                    oEid    := (pwSide == 1 ? \"L\" : \"S\") + str.tostring(oSeq)\n"
    "                    oXid    := oEid + \" SL/TP\"\n"
    "                    oSide   := pwSide\n"
    "                    oTrack  := pwTrack\n"
    "                    oLimit  := false\n"
    "                    oL      := na\n"
    "                    oSL     := pwSL0\n"
    "                    oStop   := pwSL0\n"
    "                    oTP     := na\n"
    "                    oTP0    := pwTP0\n"
    "                    oFill   := na\n"
    "                    oBE     := false\n"
    "                    oClosed := strategy.closedtrades\n"
    "                    oState  := 1\n"
    "                    strategy.entry(oEid, pwSide == 1 ? strategy.long : strategy.short, qty = q)\n"
    "                    strategy.exit(oXid, oEid, stop = oSL)\n"
    "                    if stAlertConf and (na(stConfBar) or stConfBar != time)     // 確定: 発注した足で 1 回 (既存の 1 バー 1 回ガード)\n"
    "                        stConfBar := time\n"
    "                        alert(f_stAlertMsg(\"確定\", pwSide, close, pwSL0, pwTP0), alert.freq_all)\n"
    "                    if stLblConf     // 確定ラベル: 確定アラートと同じ値 (発注判断足の終値 / SL0 / TP0。約定通知ではない)\n"
    "                        array.push(stConfLbls, label.new(bar_index, pwSide == 1 ? low : high, f_stAlertMsg(\"確定\", pwSide, close, pwSL0, pwTP0),\n"
    "                             yloc = pwSide == 1 ? yloc.belowbar : yloc.abovebar, color = pwSide == 1 ? ST_LBL_LONG : ST_LBL_SHORT,\n"
    "                             textcolor = color.white, style = pwSide == 1 ? label.style_label_up : label.style_label_down, size = size.small))\n"
    "                        if array.size(stConfLbls) > stLblKeep\n"
    "                            label.delete(array.shift(stConfLbls))\n"
    "                    pwRRPlan := pwSide * (pwTP0 - close) / (pwSide * (close - pwSL0))\n"
    "                    pwRRFill := na\n"
    "                    pwRRWhy  := na\n"
    "                    pwState  := 0\n"
    "                    pwEv     := 2\n"
    "                    pwNOrder += 1\n"
    "                    pwNOrdSame  += rebA ? 1 : 0\n"
    "                    pwNOrdLater += rebA ? 0 : 1\n"
    "                    pwTouched  := false\n"
    "                    pwTouchK   := 0\n"
    "                    pwTouchBar := na\n"
    "\n")

PREP_OLD = "            if not skipRef and not na(pQty)\n                oSeq    += 1\n"
PREP_NEW = (
    "            if stSats\n"
    "                // SX-1: 選択した Entry Mode (A〜D) が発注する条件を満たした → 発注せず待機を準備する (通知・ラベルは出さない)\n"
    "                //   (P0 = ref: A は指値価格 pL / B・C・D は確定足の終値。待機中・取消した足では何もしない)\n"
    "                if not skipRef and not na(pQty) and pwState == 0 and not pwCancelBar\n"
    "                    pwState  := 1\n"
    "                    pwSide   := side\n"
    "                    pwTrack  := c.track\n"
    "                    pwBar    := bar_index\n"
    "                    pwEndT   := time_close\n"
    "                    pwP0     := ref\n"
    "                    pwSL0    := pSL\n"
    "                    pwTP0    := tpRef\n"
    "                    pwRRPrep := side * (tpRef - ref) / (side * (ref - pSL))\n"
    "                    pwEv     := 1\n"
    "                    pwNPrep  += 1\n"
    "                    pwTouched  := false     // 新しい準備は接触待ちから\n"
    "                    pwTouchK   := 0\n"
    "                    pwTouchBar := na\n"
    "            else if not skipRef and not na(pQty)\n"
    "                oSeq    += 1\n")

PLOT_ANCHOR = 'plot(stSessOK ? 1 : 0,                 "ST · Entry Session",     display = display.data_window)\n'
PLOTS = PLOT_ANCHOR + (
    'plot(oState == 2 ? oSide * (oFill - oSL) : na, "ST · BE 1R (実約定価格〜初期 SL)", display = display.data_window)\n'
    'plot(oState == 2 ? oSide * (oTP - oFill) : na, "ST · BE 実約定価格〜TP の距離", display = display.data_window)\n'
    'plot(oState == 2 ? f_beTrig(oSide, oFill, oSL, oTP) : na, "ST · BE Trigger 幅 (選択方式)", display = display.data_window)\n'
    'plot(oState == 2 ? oFill + oSide * f_beTrig(oSide, oFill, oSL, oTP) : na, "ST · BE Trigger 価格", display = display.data_window)\n'
    "// SX-1 SATS Pullback の確認表示 (データウィンドウ + 小さな印)\n"
    'plot(stSats and stSatsShow ? satL1 : na,  "SATS · LINE1", color = color.new(color.teal, 0))\n'
    'plot(stSats and stSatsShow ? satL2 : na,  "SATS · LINE2", color = color.new(color.orange, 0))\n'
    'plot(stSats and stSatsShow ? satStb : na, "SATS · STB",   color = color.new(color.purple, 0))\n'
    'plot(stSats ? pwState : na,                "SATS · 待機中",          display = display.data_window)\n'
    'plot(stSats ? pwEv : na,                   "SATS · イベント (1 準備 / 2 発注 / -1 期限 / -4 SL0)", display = display.data_window)\n'
    'plot(stSats ? pwLineK : na,                "SATS · 対象線 (1 L1 / 2 L2 / 3 STB)", display = display.data_window)\n'
    'plot(stSats ? pwLineP : na,                "SATS · 対象線の価格 (足 t-1 確定値)", display = display.data_window)\n'
    'plot(stSats ? pwP0 : na,                   "SATS · P0",              display = display.data_window)\n'
    'plot(stSats ? pwSL0 : na,                  "SATS · SL0",             display = display.data_window)\n'
    'plot(stSats ? pwTP0 : na,                  "SATS · TP0",             display = display.data_window)\n'
    'plot(stSats ? pwRRPrep : na,               "SATS · 準備 RR",          display = display.data_window)\n'
    'plot(stSats ? pwRRPlan : na,               "SATS · 発注時の予定 RR",   display = display.data_window)\n'
    'plot(stSats ? pwRRFill : na,               "SATS · 実 RR (実約定価格。実現損益の R ではない)", display = display.data_window)\n'
    'plot(stSats ? pwRRWhy : na,                "SATS · 実 RR の理由 (0 可 / 1 risk<=0 / 2 reward<=0 / 3 na)", display = display.data_window)\n'
    'plot(stSats ? pwNFill : na,                "SATS · 実 RR 記録件数", display = display.data_window)\n'
    'plot(stSats ? pwFillPath : na,             "SATS · 記録経路 (1 保有中 / 2 約定足内で決済済み)", display = display.data_window)\n'
    'plot(stSats ? pwNPrep : na,                "SATS · 準備件数",          display = display.data_window)\n'
    'plot(stSats ? pwNOrder : na,               "SATS · 発注件数",          display = display.data_window)\n'
    'plot(stSats ? pwNExp : na,                 "SATS · 期限切れ件数",      display = display.data_window)\n'
    'plot(stSats ? (pwTouched ? 1 : 0) : na,    "SATS · 接触 (0 接触待ち / 1 接触済み・反発待ち)", display = display.data_window)\n'
    'plot(stSats ? pwTouchK : na,               "SATS · 保持している線 (1 L1 / 2 L2 / 3 STB / 0 未接触)", display = display.data_window)\n'
    'plot(stSats ? pwNTouchPrep : na,           "SATS · 接触を経験した準備件数", display = display.data_window)\n'
    'plot(stSats ? pwNOrdSame : na,             "SATS · 発注 (同じ足の接触・反発。近接 ON は近接の同一足反発を含む)", display = display.data_window)\n'
    'plot(stSats ? pwNOrdLater : na,            "SATS · 発注 (接触後の別の足の戻り)", display = display.data_window)\n'
    'plot(stSats ? pwNSL : na,                  "SATS · SL0 到達の取消件数", display = display.data_window)\n'
    'plot(stSats ? pwNBad : na,                 "SATS · 不適切な約定の決済件数", display = display.data_window)\n'
    'plot(satTfD,                               "SATS 逆方向一致 · 日足 (1 青 / -1 赤 / 0 無点灯 / n/a 未成立)", display = display.data_window)\n'
    'plot(satTf4,                               "SATS 逆方向一致 · 4H (1 青 / -1 赤 / 0 無点灯 / n/a 未成立)", display = display.data_window)\n'
    'plot(satTf1,                               "SATS 逆方向一致 · 1H (1 青 / -1 赤 / 0 無点灯 / n/a 未成立)", display = display.data_window)\n'
    'plot(satTf15,                              "SATS 逆方向一致 · 15分 (1 青 / -1 赤 / 0 無点灯 / n/a 未成立)", display = display.data_window)\n'
    'plot(satTf5,                               "SATS 逆方向一致 · 5分 (1 青 / -1 赤 / 0 無点灯 / n/a 未成立)", display = display.data_window)\n'
    'plot(satSkipL ? 1 : 0,                     "SATS 逆方向一致 · Long 見送り判定 (1 見送り / 0 なし)", display = display.data_window)\n'
    'plot(satSkipS ? 1 : 0,                     "SATS 逆方向一致 · Short 見送り判定 (1 見送り / 0 なし)", display = display.data_window)\n'
    'plotshape(stSats and pwEv == 1, "SATS · 準備", style = shape.circle, location = location.abovebar, color = color.gray, size = size.tiny)\n'
    'plotshape(stSats and pwEv == 2, "SATS · 発注", style = shape.triangledown, location = location.abovebar, color = color.red, size = size.tiny)\n'
    'plotshape(stSats and pwEv < 0,  "SATS · 取消", style = shape.xcross, location = location.abovebar, color = color.silver, size = size.tiny)\n')

PROV_OLD = "if stPvA or stPvL\n    [s0, e0, l0, t0] = f_stProvEval()\n"


def _prov_new(cur):
    """USDJPY has no pvQty (its stPvOK = pSide != 0); the others gate the provisional on pvQty, so the SATS branch sets it
    with the same expression as the Current branch (f_satProvEval already requires a valid quantity)."""
    return (
        "if (stPvA or stPvL) and stSats     // SX-1: SATS は待機中の形成中 5分足だけを評価 (Current の仮評価は使わない)\n"
        "    [sS, eS, lS, tS] = f_satProvEval(close[1], satL1[1], satL2[1], satStb[1])\n"
        "    pSide := sS\n"
        "    pPx   := eS\n"
        "    pSL   := lS\n"
        "    pTP   := tS\n"
        + ("" if cur == "USDJPY" else "    pvQty := pSide != 0 ? f_stQty(pSide, pPx, pSL) : na\n") +
        "if (stPvA or stPvL) and not stSats\n"
        "    [s0, e0, l0, t0] = f_stProvEval()\n")

UJ_MSG = [
    ("text",
     '     "\\nMode: " + stMode +\n',
     '     "\\nMode: " + stMode + (stSats ? " / SATS Pullback" : "") +\n'),
    ("text",
     '(stModeA ? " (指値)" : " (参考。次足始値で成行)")',
     '(stModeA and not stSats ? " (指値)" : " (参考。次足始値で成行)")'),
    ("text",
     '(kind == "仮" ? "" : " (発注時の予定値。最終 TP は約定確認後に実約定価格から設定)")',
     '(kind == "仮" ? "" : stSats ? " (SATS の TP0。約定確認後もこの値)" : " (発注時の予定値。最終 TP は約定確認後に実約定価格から設定)")'),
]


def edits(cur):
    c = CUR[cur]
    out = [
        ("header", "//@version=5\n", _hdr(c) + "//@version=5\n"),
        ("input",
         'stDWait = input.int(30, "D · BOS Wait (confirmed 1M bars)", minval = 1, group = G_ST)\n',
         'stDWait = input.int(30, "D · BOS Wait (confirmed 1M bars)", minval = 1, group = G_ST)\n' + _inputs(c)),
        ("input", 'var string G_STQ = "03 · Strategy Position Size (単利・損失予算)"\n',
         BE_INPUTS + 'var string G_STQ = "03 · Strategy Position Size (単利・損失予算)"\n'),
        ("sats", 'bool stShortOK = stDir != "Long Only"\n', 'bool stShortOK = stDir != "Long Only"\n' + SATS_BLOCK),
        ("be", "    [skip, tp]\n\nvar array<StCand>  stPrev = array.new<StCand>()\n",
         "    [skip, tp]\n" + BE_FN + "\nvar array<StCand>  stPrev = array.new<StCand>()\n"),
        ("sats", "var array<float> stTpUpPrev = array.new_float()", PW_VARS + "var array<float> stTpUpPrev = array.new_float()"),
    ]
    if cur == "USDJPY":
        out += UJ_MSG
    out += [
        ("alert", "int stZones   = 0\n", PROV_FN + "int stZones   = 0\n"),
        ("sats", FILL_CLOSED_OLD, FILL_CLOSED_NEW),
        ("sats", FILL_OLD, FILL_NEW),
        ("be", BE_OLD, BE_NEW),
        ("sats", WAIT_ANCHOR, WAIT_BLOCK + WAIT_ANCHOR),
        ("sats", PREP_OLD, PREP_NEW),
        ("plot", PLOT_ANCHOR, PLOTS),
        ("alert", PROV_OLD, _prov_new(cur)),
    ]
    return out


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


def show(rev, path):
    return subprocess.run(["git", "-C", ROOT, "show", f"{rev}:{path}"], capture_output=True, text=True).stdout


def build(path):
    return _apply(show(BASE_REV, path), edits(BY_PATH[path]))


def strip(path, text):
    """reverse SX-1 exactly (-> the file of BASE_REV); None when not exact."""
    return _revert(text, edits(BY_PATH[path]))


def unapply(path, text):
    """reverse SX-1 when present (all or nothing): unchanged without it (or for other paths), None with only part of it.
    The later SX-2 layer (sx2_build) is reverted first, exactly."""
    text = __import__("sx2_build").unapply(path, text)
    if text is None or path not in BY_PATH:
        return text
    if edits(BY_PATH[path])[0][2] not in text and "bool stSats =" not in text:
        return text
    return strip(path, text)


if __name__ == "__main__":
    for p in FILES:
        open(os.path.join(ROOT, p), "w", encoding="utf-8").write(build(p))
        print("written", p)
