"""v4_mtf_transform(visual @ a251a0a) -> MTF Authority Visual.  Used by the fixtures (exact-transform proof)."""
from visual_mtf import (pine_auth_pack, pine_auth_pack_prev, pine_feed_new, direct_segment, PACK_RETURN)

B = "// ==== V4 MTF Authority (begin) " + "=" * 46 + "\n"
E = "// ==== V4 MTF Authority (end) " + "=" * 48 + "\n"

GATE_ANCHOR = "bool is5mChart = timeframe.isminutes and timeframe.multiplier == 5\n"

INPUTS = B + """//  Zone Engine の時間軸は常に 5分足 (AUTH_TF)。他の時間足は「5分Zoneを見るための表示画面」。
//    Chart TF = 5m : 現行 direct path (チャート自身の 5分足) をそのまま使う
//    Chart TF < 5m : request.security(AUTH_TF, f_authPackPrev, lookahead_on) = 直前の確定5分足。
//                    同じ5分足が複数の下位足バーで返っても zn.update は1回だけ (Duplicate Guard)
//    Chart TF > 5m : request.security_lower_tf(AUTH_TF, f_authPack) = チャートバー内部の5分足を
//                    古い順 -> 新しい順に全件 replay (形成中の5分足は処理しない)
//  Engine Start Time : 全時間足で「同じ開始5分足」から Engine を開始する (bootstrap 開始点の統一のみ。
//                      Zone ロジック / Source 式 / 既定値は不変)。
//  開始5分足から現在までの5分足を1本も欠けず古い順に取得できない時間足では Zone を一切表示しない
//  (INSUFFICIENT 5M HISTORY / AUTHORITY GAP)。途中開始・間引き・近似はしない。
//  MTF Parity Mode OFF (既定) : 5分足は従来どおり全履歴から direct path。5分足以外は Engine を動かさない。
var string G_AUTH = "00 · MTF Authority (5m)"
useEngineStart = input.bool(false, "MTF Parity Mode (Engine Start Time を使用)", group = G_AUTH,
     tooltip = "ON: 5分足を含む全時間足で Engine Start Time 以降の5分足だけを、同じ順序で Engine に流す。\\n" +
     "開始5分足まで遡れない時間足では Zone を表示しない (Debug: Engine Stats で理由を表示)。")
engineStartTime = input.time(timestamp("01 Oct 2026 00:00 +0000"), "Engine Start Time", group = G_AUTH,
     tooltip = "全時間足で共通の Engine 開始時刻。この時刻以降の最初の5分足が Authority index 0。\\n" +
     "各時間足のチャート履歴 (下位足チャート) / intrabar 上限 (上位足チャート) の範囲内に置くこと。")
string AUTH_TF    = "5"
int    authTfSec  = timeframe.in_seconds(AUTH_TF)
int    chartTfSec = timeframe.in_seconds()
""" + E


def guard_and_pack(direct):
    s = B
    s += """//  Authority guard (main context, var = Realtime ではバー確定までロールバック)
//    status 0 = 5分足未取得 / 1 = OK / 2 = INSUFFICIENT 5M HISTORY / 3 = AUTHORITY GAP (missing / 逆順)
type AuthGuard
    int   status    = 0
    int   firstTime = na
    int   firstIdx  = na
    int   lastIdx   = na
    int   lastTime  = na
    int   count     = 0
    int   dupSkip   = 0
    int   missing   = 0
    int   inversion = 0
    int   idxBase   = 0
    float ma1       = na
    float ma2       = na

var AuthGuard authG = AuthGuard.new()

// 5分 context の開始キー: Engine Start Time 以降の最初の5分足 = index 0。
// startOk = その5分足の前にも5分足がある (= 開始5分足が context の先頭で切れていない)。
f_authKey(int startT) =>
    var int  startIdx = na
    var bool startOk  = false
    if na(startIdx) and time >= startT
        startIdx := bar_index
        startOk  := bar_index > 0
    [na(startIdx) ? int(na) : bar_index - startIdx, startOk]

// 5分 Authority Feed Pack (5分 context で評価)。中身は 5分足 direct path の Source / Break / 取引日ID と
// 同一の式 (fixture V4-MTF-PACK が direct path からの機械変換との完全一致を検査する)。
// 戻り値 36 primitive = ZoneFeed 35 field (barIndex = 開始相対5分index) + startOk。
"""
    s += pine_auth_pack(direct) + "\n"
    s += "// <5m 用: 直前の確定5分足 (lookahead_on と組で使う非リペイント形)\n"
    s += pine_auth_pack_prev() + "\n"
    s += """// Duplicate Guard / 開始一致 / 欠損・逆順検出。true のときだけ zn.update を1回呼ぶ。
f_authAccept(AuthGuard g, int rel, bool startOk, int t) =>
    bool acc = false
    if g.status <= 1 and not na(rel) and rel >= 0
        if na(g.lastIdx)
            if rel == 0 and startOk
                acc := true
                g.firstTime := t
                g.firstIdx  := rel
                g.status    := 1
            else
                g.status := 2
        else if rel == g.lastIdx
            g.dupSkip := g.dupSkip + 1
        else if rel == g.lastIdx + 1
            acc := true
        else if rel < g.lastIdx
            g.inversion := g.inversion + 1
            g.status := 3
        else
            g.missing := g.missing + rel - g.lastIdx - 1
            g.status := 3
        if acc
            g.lastIdx  := rel
            g.lastTime := t
            g.count := g.count + 1
    acc
""" + E + "\n"
    return s


UPDATE_OLD = """//  ★ 5分足専用: 5分足以外では zn.update を呼ばない (空データを入れるのではなく状態遷移自体を行わない)。
int zoneCountNow = 0

if is5mChart
    zoneCountNow := zn.update(zoneEng, zoneCfg, zoneFeed)
"""


def update_new():
    s_names = ["s%d" % k for k in range(len(PACK_RETURN))]
    l_names = ["l%d" % k for k in range(len(PACK_RETURN))]
    s = """//  ★ Engine update: Parity Mode OFF の 5分足 = 従来の direct path。Parity Mode OFF の他の時間足では
//    zn.update を呼ばない。Parity Mode ON では全時間足が Authority guard を通った5分足だけを update する。
int zoneCountNow = 0

""" + B + """if is5mChart and not useEngineStart
    zoneCountNow := zn.update(zoneEng, zoneCfg, zoneFeed)
else if is5mChart
    // =5m (MTF Parity Mode): direct path の zoneFeed をそのまま使い、開始5分足以降だけ update
    [d5Idx, d5Ok] = f_authKey(engineStartTime)
    if f_authAccept(authG, d5Idx, d5Ok, time)
        if authG.count == 1
            authG.idxBase := bar_index - d5Idx
        zoneCountNow := zn.update(zoneEng, zoneCfg, zoneFeed)
else if useEngineStart and chartTfSec < authTfSec
    // <5m: 直前の確定5分足 (Authority index で重複 update を防ぐ)
    [""" + ", ".join(s_names) + """] = request.security(syminfo.tickerid, AUTH_TF,
         f_authPackPrev(engineStartTime), lookahead = barmerge.lookahead_on)
    if f_authAccept(authG, s34, s35, s33)
        zn.update(zoneEng, zoneCfg, """ + pine_feed_new(s_names[:35], 8) + """)
        authG.ma1 := s0
        authG.ma2 := s2
    zoneCountNow := zn.zoneCount(zoneEng)
else if useEngineStart and chartTfSec > authTfSec
    // >5m: チャートバー内部の5分足を古い順に全件 replay。未確定チャートバーの最後の intrabar (形成中5分足) は処理しない
    [""" + ", ".join(l_names) + """] = request.security_lower_tf(syminfo.tickerid, AUTH_TF,
         f_authPack(engineStartTime))
    int nAuth = array.size(l34)
    if nAuth > 0
        for i = 0 to nAuth - 1
            if i < nAuth - 1 or barstate.isconfirmed
                if f_authAccept(authG, array.get(l34, i), array.get(l35, i), array.get(l33, i))
                    zn.update(zoneEng, zoneCfg, """ + pine_feed_new(["array.get(%s, i)" % n for n in l_names[:35]], 20) + """)
                    authG.ma1 := array.get(l0, i)
                    authG.ma2 := array.get(l2, i)
    zoneCountNow := zn.zoneCount(zoneEng)

// Zone を表示してよいのは: Parity Mode OFF の 5分足 (従来どおり) / Parity Mode ON で開始5分足から欠損なく処理中
bool authDisplayOk = useEngineStart ? authG.status == 1 : is5mChart
""" + E
    return s


DRAW_OLD = "if barstate.islast and is5mChart\n    int nBox = 0\n"
DRAW_NEW = "if barstate.islast and authDisplayOk\n    int nBox = 0\n"
PLOT1_OLD = "plot(is5mChart and showMaLines and useMaSource ? ma1Val : na,"
PLOT1_NEW = "plot(authDisplayOk and showMaLines and useMaSource ? (is5mChart ? ma1Val : authG.ma1) : na,"
PLOT2_OLD = "plot(is5mChart and showMaLines and useMaSource ? ma2Val : na,"
PLOT2_NEW = "plot(authDisplayOk and showMaLines and useMaSource ? (is5mChart ? ma2Val : authG.ma2) : na,"
STATS_OLD = "if barstate.islast and is5mChart and showStats\n"
STATS_NEW = "if barstate.islast and authDisplayOk and showStats\n"

DEBUG = "\n" + B + """// ---- Authority Debug (showStats のときだけ) -----------------------------------
//  INSUFFICIENT の理由と、時間足間で比較する Parity fingerprint (同じ最終5分足で比較する)。
//  bar 系 field は Authority index 0 基準に正規化 (5分 direct path は bar_index を渡しているため)。
var table gAuth = na
f_authRow(int r, string k, string v) =>
    table.cell(gAuth, 0, r, k, text_color = color.white, bgcolor = color.new(color.gray, 70), text_size = size.small)
    table.cell(gAuth, 1, r, v, text_color = color.white, bgcolor = color.new(color.gray, 85), text_size = size.small)

f_tm(int t) =>
    na(t) ? "-" : str.format_time(t, "yyyy-MM-dd HH:mm", "UTC")

if barstate.islast and showStats
    if na(gAuth)
        gAuth := table.new(position.bottom_right, 2, 24, border_width = 1, frame_width = 1, frame_color = color.new(color.gray, 40))
    string path = chartTfSec == authTfSec ? "=5m direct" : chartTfSec < authTfSec ? "<5m security[1]" : ">5m lower_tf replay"
    string st = not useEngineStart ? (is5mChart ? "MODE OFF (5m production)" : "MODE OFF (no Engine on this TF)") :
         authG.status == 1 ? "OK" : authG.status == 2 ? "INSUFFICIENT 5M HISTORY" :
         authG.status == 3 ? "AUTHORITY GAP" : "NO 5M AUTHORITY BAR"
    f_authRow(0, "Authority", st)
    f_authRow(1, "Path", path)
    f_authRow(2, "Engine Start", useEngineStart ? f_tm(engineStartTime) : "-")
    f_authRow(3, "firstAuthorityTime", f_tm(authG.firstTime))
    f_authRow(4, "firstAuthorityIndex", na(authG.firstIdx) ? "-" : str.tostring(authG.firstIdx))
    f_authRow(5, "lastAuthorityTime", f_tm(authG.lastTime))
    f_authRow(6, "processed 5m bars", str.tostring(authG.count))
    f_authRow(7, "duplicate skipped", str.tostring(authG.dupSkip))
    f_authRow(8, "missing", str.tostring(authG.missing))
    f_authRow(9, "order inversion", str.tostring(authG.inversion))
    if authDisplayOk
        int   base = useEngineStart ? authG.idxBase : 0
        int   zc   = zn.zoneCount(zoneEng)
        float sTop = 0.0
        float sBot = 0.0
        float sScr = 0.0
        int   sStr = 0
        int   sSt  = 0
        int   sTch = 0
        int   sSrc = 0
        int   sFlp = 0
        int   sTid = 0
        if zc > 0
            for k = 0 to zc - 1
                zn.Zone z = zn.zoneAt(zoneEng, k)
                sTop += z.top
                sBot += z.bottom
                sScr += z.score
                sStr += z.strength
                sSt  += z.state
                sTch += z.touchCount
                sSrc += z.srcMask
                sFlp += z.flipped ? 1 : 0
                sTid += z.trackId
        int tn = array.size(zoneEng.tracks)
        int tSt = 0
        int tBrk = 0
        int tFlp = 0
        int tSeen = 0
        if tn > 0
            for k = 0 to tn - 1
                zn.ZoneTrack t = array.get(zoneEng.tracks, k)
                tSt   += t.state
                tBrk  += t.breakDir != 0 ? t.breakDir * (t.breakBar - base + 1) : 0
                tFlp  += t.flipped ? t.flipDir : 0
                tSeen += t.lastSeenBar - base
        int pn = array.size(zoneEng.persist)
        int pExp = 0
        int pUid = 0
        if pn > 0
            for k = 0 to pn - 1
                zn.RawZone rz = array.get(zoneEng.persist, k)
                pExp += rz.expireTime
                pUid += rz.uid
        f_authRow(10, "Zones", str.tostring(zc))
        f_authRow(11, "Σ top / bottom", str.tostring(sTop, "#.#####") + " / " + str.tostring(sBot, "#.#####"))
        f_authRow(12, "Σ score", str.tostring(sScr, "#.#####"))
        f_authRow(13, "Σ strength / state", str.tostring(sStr) + " / " + str.tostring(sSt))
        f_authRow(14, "Σ touch / srcMask", str.tostring(sTch) + " / " + str.tostring(sSrc))
        f_authRow(15, "Σ flipped / trackId", str.tostring(sFlp) + " / " + str.tostring(sTid))
        f_authRow(16, "Tracks", str.tostring(tn))
        f_authRow(17, "Track Σ state / break", str.tostring(tSt) + " / " + str.tostring(tBrk))
        f_authRow(18, "Track Σ flip / lastSeen", str.tostring(tFlp) + " / " + str.tostring(tSeen))
        f_authRow(19, "Persist (Lifetime)", str.tostring(pn))
        f_authRow(20, "Persist Σ expire / uid", str.tostring(pExp) + " / " + str.tostring(pUid))
""" + E


def v4_mtf_transform(src):
    t = src

    def R(a, b):
        nonlocal t
        assert t.count(a) == 1, a[:80]
        t = t.replace(a, b)
    R(GATE_ANCHOR, GATE_ANCHOR + "\n" + INPUTS)
    direct = direct_segment(src)
    feed_banner = "// ============================================================================\n// EXTERNAL DATA FEED\n"
    R(feed_banner, guard_and_pack(direct) + feed_banner)
    R(UPDATE_OLD, update_new())
    R(DRAW_OLD, DRAW_NEW)
    R(PLOT1_OLD, PLOT1_NEW)
    R(PLOT2_OLD, PLOT2_NEW)
    R(STATS_OLD, STATS_NEW)
    t = t.rstrip("\n") + "\n" + DEBUG
    return t


def v4_mtf_eval_off(cur):
    """Partial evaluation of the MTF Visual with useEngineStart = false on a 5M chart:
    every V4 block is inert (inputs / guard / pack are declarations; the update chain takes the first branch;
    authDisplayOk == is5mChart; the Authority Debug table only adds a debug view). Result == a251a0a."""
    t = cur
    t = t.replace("\n" + DEBUG, "\n")
    t = t.replace(update_new(), UPDATE_OLD)
    for a, b in ((DRAW_OLD, DRAW_NEW), (PLOT1_OLD, PLOT1_NEW), (PLOT2_OLD, PLOT2_NEW), (STATS_OLD, STATS_NEW)):
        t = t.replace(b, a)
    t = t.replace(GATE_ANCHOR + "\n" + INPUTS, GATE_ANCHOR)
    i = t.find(B + "//  Authority guard")
    if i >= 0:
        j = t.index(E, i) + len(E) + 1
        t = t[:i] + t[j:]
    return t
