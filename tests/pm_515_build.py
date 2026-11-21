"""POINT MASTER B 5分・15分専用版の Source A / B / C（PointMasterSource{A,B,C}5M15M.pine）を生成する。
1 分足あり版（tests/pm_split_build.py → PointMasterSource{A,B,C}V2.pine）とは出力先が別で、上書きしない。

検知モジュール（入力・PRM 束・ロジック関数・Engine 関数）は PointMasterFvgAbsReboundV2.pine から
行範囲でそのまま移す（書き直さない）。基盤部分（1M/5M/15M 取得・V2 有効根拠・準備判定・BUS）は
テンプレートから生成する。使い方: python3 -I tests/pm_split_build.py <repo_root>
"""
import re
import sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else '.'
SRC = open(f'{ROOT}/PointMasterFvgAbsReboundV2.pine', encoding='utf-8').read().split('\n')


def lines(a, b):
    """1 始まり・両端含む"""
    return '\n'.join(SRC[a - 1:b])


def find(pat, start=1):
    for i in range(start - 1, len(SRC)):
        if re.search(pat, SRC[i]):
            return i + 1
    raise SystemExit('not found: ' + pat)


# ---- 検知モジュールの行範囲（V2 ファイル上の位置を見出しから求める）----
L01 = find(r'^// SIGNAL MODULE : Logic01 ') - 1
L13 = find(r'^// SIGNAL MODULE : Logic13 ') - 1
L19 = find(r'^// SIGNAL MODULE : Logic19 ') - 1
PACK = find(r'^// LONG / SHORT の bool 配列 → ビットマスク') - 1
ENGA = find(r'^// Engine A : Logic01') - 1
ENGB = find(r'^// Engine B : Logic13') - 1
L24 = find(r'^// SIGNAL MODULE : Logic24 ') - 1
ENGC = find(r'^// Engine C : Logic19') - 1
BITON = find(r'^// ビットマスクから「ロジック番号 idx」')
SEC5 = find(r'^// §5\. MTF 取得') - 1

MOD_A = lines(L01, L13 - 1)
MOD_B = lines(L13, L19 - 1)
MOD_C1 = lines(L19, PACK - 1)
PACKF = lines(PACK, ENGA - 1)
ENG_A = lines(ENGA, ENGB - 1)
ENG_B = lines(ENGB, L24 - 1)
MOD_C2 = lines(L24, ENGC - 1)
ENG_C = lines(ENGC, BITON - 1)
BITONF = lines(BITON, BITON + 2)

# Source A（5分・15分版のみ）: 時刻照合用に、同じ Engine 実行で得た値を UDT の末尾へ追加する（判定には使わない）
#   time_close / close[1] / EMA A の前足値 / EMA 許容幅用 ATR / EMA 対象 TF フラグ
old_a = '    float xC  = close\n'
assert ENG_A.count(old_a) == 1
ENG_A = ENG_A.replace(old_a, old_a + """    float xTc  = time_close              // ★時刻照合 : この TF 足の確定時刻
    float xCp  = close[1]                // ★時刻照合 : f_emaEvents が使う前足 close
    float xEaP = _emaA[1]                // ★時刻照合 : f_emaEvents へ渡した EMA A の前足値
    float xAtr = _emaAtr                 // ★時刻照合 : f_emaEvents へ渡した ATR（接触許容幅）
    float xOn  = _emaTfOk ? 1.0 : 0.0    // ★時刻照合 : EMA ロジックの対象 TF か
""")
old_ret = '    [lmA, smA, xC, xH, xL, xEa, xEb, xEc, xEd, x01L, x01S, x02L, x02S, x03L, x03S, x04L, x04S]'
assert ENG_A.count(old_ret) == 1
ENG_A = ENG_A.replace(old_ret, old_ret[:-1] + ', xTc, xCp, xEaP, xAtr, xOn]')

# Engine B / C の V2 追加出力の先頭に、この TF 足の close（C は high / low も）を加える（判定には使わない）
old_b = '    [lmB, smB, preLmB, preSmB, x13L,'
assert ENG_B.count(old_b) == 1
ENG_B = ENG_B.replace(old_b, '    [lmB, smB, preLmB, preSmB, close, x13L,')
# 時刻修正版 : 元足の確定時刻（time_close）を UDT の末尾へ追加（15M の確定境界ゲートと照合用。判定には使わない）
_rb = [l for l in ENG_B.split('\n') if l.startswith('    [lmB, smB, preLmB, preSmB, close, x13L,')]
assert len(_rb) == 1
ENG_B = ENG_B.replace(_rb[0], _rb[0][:-1] + ', time_close]')
old_c = '    [lmC, smC, imC, preLmC, preSmC, satPreSigned, x19L, x19S, x20L, x20S]'
assert ENG_C.count(old_c) == 1
ENG_C = ENG_C.replace(old_c, '    [lmC, smC, imC, preLmC, preSmC, satPreSigned, close, high, low, x19L, x19S, x20L, x20S, time_close]')


def holds(nums):
    """保持本数 input（1M / 5M / 15M だけ残す。1H / 4H / 1D の input は持たない）"""
    out = []
    i = find(r'^// §3\. 保持本数設定') + 3
    end = find(r'^// ロジック別の保持本数リスト')
    blk = SRC[i - 1:end - 1]
    # Logic25 のブロックは HOLD 配列の後ろにある
    j = find(r'^grpH25 = ')
    blk += SRC[j - 1:j + 7]
    for n in nums:
        tag = f'{n:02d}'
        g = [l for l in blk if re.match(rf'^grpH{n}\s+= ', l)]
        if not g:
            continue
        out.append(g[0])
        for l in blk:
            m = re.match(rf'^h{tag}([bc]) = ', l)          # 5M / 15M の input だけ（1M の input は持たない）
            if m:
                out.append(l)
    return '\n'.join(out)


def hold_arrays(nums, ema=(), sat=()):
    rows = []
    for n in nums:
        t = f'{n:02d}'
        if n in sat:
            rows.append(f'HOLD{t} = array.from(0, 0)             // 状態型（保持本数を使わない）')
        elif n in ema:
            rows.append(f'HOLD{t} = array.from(h{t}b, 1)    // EMA は 5M のみ（元版でも 15M は対象外。15M はイベントが出ないダミー値）')
        else:
            rows.append(f'HOLD{t} = array.from(h{t}b, h{t}c)')
    rows.append('var HOLD_ALL = array.new_int(0)')
    rows.append('if array.size(HOLD_ALL) == 0')
    for n in nums:
        rows.append(f'    array.concat(HOLD_ALL, HOLD{n:02d})')
    return '\n'.join(rows)


COMMON_HEAD = '''// This Pine Script® code is subject to the terms of the Mozilla Public License 2.0
// © point_master

//@version=5
'''

BUS_DOC = '''// 【BUS 仕様（Decision への受け渡し）】plot の値 1 本 = 1 TF ぶんの集約結果（非負整数 < 2^49）
//   bus = 1(format) + 4 × SourceID + 16 × TFID + 64 × slot + 2^28 × payload
//     bit 0-1   : format = 3（時刻修正版。旧 5分・15分版 = 2、1 分足あり版 = 1。Decision 5M15M は 3 だけ受け付ける）
//     bit 2-3   : SourceID（1 = A / 2 = B / 3 = C）
//     bit 4-5   : TFID（1 = 5M / 2 = 15M。この版は 1M を出さない）
//     bit 6-27  : slot = (集約結果を確定した 5 分足の確定時刻 time_close − 2020-01-01 00:00 UTC) / 5 分
//                 0〜4,194,303（2020-01-01 00:05 〜 2059-11-23 頃の 5 分足）。範囲外は折り返さず na
//     bit 28-48 : payload（21 bit）
//       bit 0 : LONG 方向の根拠がこの 5 分足の処理中に価格否定された / bit 1 : SHORT 方向
//       bit 2 : 価格基準なし（未対応）の有効根拠がある
//       bit 3- : 系統ごとに [LONG 確認済み 1bit, LONG 統合, SHORT 確認済み 1bit, SHORT 統合]
//                統合は SAT だけ 2bit（0〜3 = 強度 0 / 1/3 / 2/3 / 1）、他の系統は 1bit（強度 0 / 1 しか取らない）
//   最大値 < 2^49 = 562,949,953,421,312 ≤ 2^53 − 1。各フィールドは重ならず、境界値まで可逆。
//   未準備・不整合の 5 分足では na（根拠ゼロを有効値として送らない）。
//   値は 5 分足の確定時点で確定し、足の途中では最後に確定した値を出し続ける。
'''


def adopt_block(cfg):
    """採用設定の input と V2_ADOPT（f_idx(li, ti) = li × 2 + ti の順）"""
    g = '"⑧ 採用設定（実験用。初期値 = 全て採用）"'
    out = [f'adoptModeStr = input.string("全て採用", "B の系統点へ採用するロジック", options = ["全て採用", "カスタム（下のチェック）"], group = {g},',
           '     tooltip = "全て採用 = 変更前と同じ。カスタムでは下のチェックを外したロジック × 時間足を、B の確認済み点・統合点・寄与系統数・価格否定・価格基準なしから外します（検知と保持は変えません）。")',
           'bool adoptAll = adoptModeStr == "全て採用"']
    vals = []
    for i, lab in enumerate(cfg['labels']):
        only5 = cfg['id'] == 'A' and i >= 4
        out.append(f'ad{i}m5  = input.bool(true, "{lab} 5M", group = {g}, inline = "ad{i}")')
        if not only5:
            out.append(f'ad{i}m15 = input.bool(true, "15M", group = {g}, inline = "ad{i}")')
        vals.append(f'adoptAll or ad{i}m5')
        vals.append('true' if only5 else f'adoptAll or ad{i}m15')
    out.append('V2_ADOPT = array.from(' + ', '.join(vals) + ')')
    return '\n'.join(out)


def infra(cfg):
    """Source 共通の基盤（5M / 15M 取得・V2 有効根拠・準備判定・BUS）。内部 index 0 = 5M / 1 = 15M"""
    S = cfg['id']
    sid = cfg['sid']
    nx = cfg['nx']
    xs = cfg['xs']
    eng = cfg['eng']
    o = []
    pre5 = {'A': '', 'B': 'g5plm, g5psm, ', 'C': 'g5im, g5plm, g5psm, g5sp, '}[S]
    gxs = ', '.join('g5_' + v for v in xs)
    o.append(f"""// =====================================================================================
// §5. 取得（時刻修正版）: 5M = チャート自身で Engine を評価 / 15M = 現在の 15M 結果（lookahead_off・[1] なし）
// =====================================================================================
// 5M : 5 分足チャート自身のコンテキストで担当 Engine をグローバルで毎バー 1 回評価する（request なし・[1] シフトなし）。
//      マスク・PRE・解除・SAT 強度・否定ライン・EMA / TL 値・OHLC・time / time_close はすべて同じ現在の 5M 足の値。
//      状態への適用は §6 で、チャート足の確定時（barstate.isconfirmed）に 1 回だけ行う。
// 15M : request.security(tfStr3, 現在の 15M Engine 結果, lookahead = barmerge.lookahead_off)。[1] なし。
//      形成中の値が動くことはあるが、§6 の確定境界ゲート（15M 区間の最後の 5M 足が確定し、元足の time / time_close が
//      一致した時だけ）以外では一切使わない。lookahead_on のまま [1] を外す方式は未来の値が漏れるので使わない。
// V2 用の追加出力は 1 個の UDT。request 呼び出し 1 本（15M）、タプル要素 {cfg['tuple']} 個。
type SRC{S}X
""" + ''.join(f'    float f{i} = na\n' for i in range(nx)) + f"""
f_srcArr(SRC{S}X o) =>
    SRC{S}X q = na(o) ? SRC{S}X.new() : o
    array.from(""" + ', '.join(f'q.f{i}' for i in range(nx)) + f""")

// ---- 5M : チャート自身の Engine 結果（毎バー 1 回。診断・通常出力はこの 1 回の結果を共用）----
[g5lm, g5sm, {pre5}{gxs}] = {eng}()
x5Obj = SRC{S}X.new({gxs})
""")
    if S == 'A':
        o.append(f"""float lm5   = nz(g5lm)
float sm5   = nz(g5sm)
float plm5  = 0.0
float psm5  = 0.0
float im5   = 0.0
float sp5   = 0.0

// ---- 15M : 現在の 15M Engine 結果（[1] なし・lookahead_off）----
f_htfPacket() =>
    [lmRaw, smRaw, {', '.join(xs)}] = {eng}()
    [nz(lmRaw), nz(smRaw), time, SRC{S}X.new({', '.join(xs)})]

[lm15, sm15, tt15, ox15] = request.security(syminfo.tickerid, tfStr3, f_htfPacket(), lookahead = barmerge.lookahead_off)
float plm15 = 0.0
float psm15 = 0.0
float im15  = 0.0
float sp15  = 0.0
""")
    elif S == 'B':
        o.append(f"""float lm5   = nz(g5lm)
float sm5   = nz(g5sm)
float plm5  = nz(g5plm)
float psm5  = nz(g5psm)
float im5   = 0.0
float sp5   = 0.0

// ---- 15M : 現在の 15M Engine 結果（[1] なし・lookahead_off）----
f_htfPacket() =>
    [lmRaw, smRaw, plmRaw, psmRaw, {', '.join(xs)}] = {eng}()
    [nz(lmRaw), nz(smRaw), nz(plmRaw), nz(psmRaw), time, SRC{S}X.new({', '.join(xs)})]

[lm15, sm15, plm15, psm15, tt15, ox15] = request.security(syminfo.tickerid, tfStr3, f_htfPacket(), lookahead = barmerge.lookahead_off)
float im15  = 0.0
float sp15  = 0.0
""")
    else:
        o.append(f"""float lm5   = nz(g5lm)
float sm5   = nz(g5sm)
float im5   = nz(g5im)
float plm5  = nz(g5plm)
float psm5  = nz(g5psm)
float sp5   = nz(g5sp)

// ---- 15M : 現在の 15M Engine 結果（[1] なし・lookahead_off）----
f_htfPacket() =>
    [lmRaw, smRaw, imRaw, plmRaw, psmRaw, spRaw, {', '.join(xs)}] = {eng}()
    [nz(lmRaw), nz(smRaw), nz(imRaw), nz(plmRaw), nz(psmRaw), nz(spRaw), time, SRC{S}X.new({', '.join(xs)})]

[lm15, sm15, im15, plm15, psm15, sp15, tt15, ox15] = request.security(syminfo.tickerid, tfStr3, f_htfPacket(), lookahead = barmerge.lookahead_off)
""")
    o.append(f"""
// =====================================================================================
// §6. V2 有効根拠（ロジック × TF × 方向）と抑止前 PRE（1 分足あり版と同じ扱い。TF は 5M / 15M の 2 枠）
// =====================================================================================
// 生シグナル成立時に登録し、元版の保持本数（期限）と価格否定（その TF の確定終値）の早い方で解除。
// 同方向の新シグナルで再登録、同じロジック × TF で反対方向の新シグナルが出たら切替で解除。
// 同一足で両方向が出た場合の裁定は元版の「状態管理ルール」と同じ。
// 否定ルール（V2_RULE）: 0 ライン（成立時の値 + 傾き × 経過本数）/ 1 EMA 現在値 / 2 Fib 継承（価格ラインなし）/
//                         3 状態型（SAT）/ 4 成立足の安値・高値（Stoch）
// PRE は抑止前の State Factor（0 / 1、SAT のみ 0 / 1/3 / 2/3）を、その TF の確定足ごとに上書き（保持なし）。
// 内部 index : ti 0 = 5M / 1 = 15M（BUS の TF ID は 5M = 1 / 15M = 2 で別物）
var LAST_TFTIME = array.new_int(N_TF, 0)
var V2_RULE  = array.from({cfg['rules']})
// B の系統点へ採用するか（ロジック × TF。index = f_idx(li, ti)）。採用 OFF は確認済み点・統合点（PRE 含む）・寄与系統数・
// 価格否定フラグ・価格基準なしから外す。検知・保持・価格否定の計算そのものは変えない（単体診断の生シグナルは採用前）。
""" + adopt_block(cfg) + f"""
var V2_VALID = array.new_bool(N_LOGIC * N_TF * 2, false)   // index = f_idx(li, ti) × 2 + (0 LONG / 1 SHORT)
var V2_PRICE = array.new_bool(N_LOGIC * N_TF * 2, false)
var V2_REM   = array.new_int(N_LOGIC * N_TF * 2, 0)
var V2_AGE   = array.new_int(N_LOGIC * N_TF * 2, 0)
var V2_LVL   = array.new_float(N_LOGIC * N_TF * 2, na)
var V2_SLP   = array.new_float(N_LOGIC * N_TF * 2, 0.0)
var V2_PRE   = array.new_float(N_LOGIC * N_TF * 2, 0.0)     // 抑止前 PRE State Factor
var V2_NEG   = array.new_int(N_TF * 2, 0)
var V2_WARM  = array.new_int(N_TF, 0)
var V2_BADX  = array.new_bool(N_TF, false)
// 単体診断（Logic Verifier 用。通常 BUS・判定には使わない。下の f_v2ApplyTf の中で既存の値を記録するだけ）
var V2_RAW    = array.new_bool(N_LOGIC * N_TF * 2, false)   // その TF 足の生シグナル（裁定・採用設定の前）
var V2_NEGF   = array.new_bool(N_LOGIC * N_TF * 2, false)   // その TF 足で価格否定により解除
var V2_EXPF   = array.new_bool(N_LOGIC * N_TF * 2, false)   // その TF 足で期限切れにより解除
var V2_SINCE  = array.new_int(N_LOGIC * N_TF * 2, -1)       // 最後の生シグナルからのその TF の本数（-1 = 未発生）
var V2_NEWBAR = array.new_bool(N_TF, false)                 // この 5 分足の間にその TF の新しい確定足を処理した

f_v2ApplyTf(int ti, float lm, float sm, float plm, float psm, float im, float sp, array<float> x) =>
    float tc = array.get(x, 0)
    array.set(V2_WARM, ti, array.get(V2_WARM, ti) + 1)
    array.set(V2_BADX, ti, array.get(V2_BADX, ti) or na(tc))
    array.set(V2_NEWBAR, ti, true)
    for li = 0 to N_LOGIC - 1
        int  k      = f_idx(li, ti)
        int  rule   = array.get(V2_RULE, li)
        bool isSt   = rule == 3
        int  ei     = {cfg['ei']}
        bool rawL   = f_bitOn(lm, li)
        bool rawS   = f_bitOn(sm, li)
        bool both   = rawL and rawS
        bool sigL   = both ? conflictMode == CONF_LONG  : rawL
        bool sigS   = both ? conflictMode == CONF_SHORT : rawS
        bool fibInv = {cfg['fibinv']}
        float emaNow = array.get(x, ei)
        for d = 0 to 1
            int   j     = k * 2 + d
            bool  reg   = d == 0 ? sigL : sigS
            bool  opp   = d == 0 ? sigS : sigL
            bool  vld   = array.get(V2_VALID, j)
            bool  aging = vld and not isSt
            int   age1  = array.get(V2_AGE, j) + (aging ? 1 : 0)
            int   rem1  = array.get(V2_REM, j) - (aging ? 1 : 0)
            float lv    = rule == 1 ? emaNow : array.get(V2_LVL, j) + array.get(V2_SLP, j) * age1
            bool  negd  = aging and rem1 > 0 and rule != 2 and array.get(V2_PRICE, j) and not na(lv) and not na(tc) and (d == 0 ? tc < lv : tc > lv)
            bool  alive = vld and rem1 > 0 and not negd
            float lvN   = {cfg['lvN']}
            float slN   = {cfg['slN']}
            bool  pOk   = rule == 2 or (rule == 1 ? not na(emaNow) : not na(lvN))
            bool  regNew = reg and not isSt
            array.set(V2_VALID, j, (isSt ? reg : (reg ? true : opp ? false : alive)) and not fibInv)
            array.set(V2_PRICE, j, isSt ? true : regNew ? pOk : array.get(V2_PRICE, j))
            array.set(V2_REM,   j, regNew ? array.get(HOLD_ALL, k) : rem1)
            array.set(V2_AGE,   j, regNew ? 0 : age1)
            array.set(V2_LVL,   j, regNew ? lvN : array.get(V2_LVL, j))
            array.set(V2_SLP,   j, regNew ? slN : array.get(V2_SLP, j))
            array.set(V2_NEG,   ti * 2 + d, array.get(V2_NEG, ti * 2 + d) + (negd and array.get(V2_ADOPT, k) ? 1 : 0))
            // 抑止前 PRE（その TF の確定足1本ぶんの現在値で上書き）
            array.set(V2_PRE, j, {cfg['pre']})
            // 単体診断（上で計算済みの値を記録するだけ）
            bool  raw   = d == 0 ? rawL : rawS
            int   since = array.get(V2_SINCE, j)
            array.set(V2_RAW,   j, raw)
            array.set(V2_NEGF,  j, negd)
            array.set(V2_EXPF,  j, aging and rem1 <= 0 and not reg)
            array.set(V2_SINCE, j, raw ? 0 : since < 0 ? -1 : since + 1)
    N_LOGIC

// ---- 確定 5 分足での適用（時刻修正版）。同じ確定足の中で ① 5M → ② 15M（境界のときだけ）の順に 1 回ずつ ----
bool isChart5M = timeframe.isminutes and timeframe.multiplier == 5
// ① 5M : 今確定したチャート足そのもの（元足 ID = チャートの time）。確定前は状態へ反映しない
int  t5  = time
x5 = f_srcArr(x5Obj)
if isChart5M and barstate.isconfirmed and t5 > array.get(LAST_TFTIME, 0)
    array.set(LAST_TFTIME, 0, t5)
    f_v2ApplyTf(0, lm5, sm5, plm5, psm5, im5, sp5, x5)
// ② 15M : 15M 区間の最後の 5M 足が確定した時だけ、今閉じた 15M 足の結果を受理する（AND 条件）
//    ・チャート足の time_close = その 15M 区間の time_close(15)（例 10:00〜10:15 は 10:10〜10:15 の 5M 足の確定時だけ）
//    ・取得した元足の time = その区間の time(15)、元足の time_close = チャート足の time_close
//    ・元足 ID が最後に受理した 15M 足より新しい / close・時刻が na でない
//    境界以外の 5M 足では、最後に受理した確定 15M 状態をそのまま維持（形成中の取得値へ差し替えない）。
//    保持本数・経過本数は受理した確定 15M 足 1 本につき 1 回だけ進む。request 式の中で barstate.isconfirmed は使わない。
int  t15      = nz(tt15)
int  q15Open  = time(tfStr3)
int  q15Close = time_close(tfStr3)
bool atB15    = not na(q15Close) and time_close == q15Close
x15 = f_srcArr(ox15)
bool acc15 = isChart5M and barstate.isconfirmed and atB15 and not na(tt15) and t15 == q15Open and array.get(x15, {cfg['tcidx']}) == time_close and t15 > array.get(LAST_TFTIME, 1) and not na(array.get(x15, 0))
if acc15
    array.set(LAST_TFTIME, 1, t15)
    f_v2ApplyTf(1, nz(lm15), nz(sm15), nz(plm15), nz(psm15), nz(im15), nz(sp15), x15)
""")
    o.append(f"""
// =====================================================================================
// §7. データ準備 / 更新整合（5M / 15M のみ）と BUS 出力
// =====================================================================================
//   5M  : 今確定したチャート足そのものを処理済みであること（元足 = チャート足）
//   15M : 15M 区間の最後の 5M 足（境界）では「今閉じた 15M 足」、それ以外の足では「直前に足が存在した 15M 区間」の
//         確定足が最後に受理されていること。休場・週末は実際に足が存在した区間で比べる（一律 +15 分にしない）。
//         期待する境界でパケットが無い / 一致しない場合は、前の 15M を新しい足の代わりにせず不整合（準備本数は数え直し）
//   値 : 処理した TF 足の確定終値が na なら不整合 / 準備 : 不整合なしで各 TF の処理本数 >= その TF の最大保持本数
var int bk15Cur  = na
var int bk15Prev = na
bk15Prev := na(bk15Cur) or q15Open != bk15Cur ? bk15Cur : bk15Prev
bk15Cur  := q15Open
int exp15 = atB15 ? bk15Cur : bk15Prev

f_maxHold(int ti) =>
    int mx = 1
    for li = 0 to N_LOGIC - 1
        mx := math.max(mx, array.get(HOLD_ALL, f_idx(li, ti)))
    mx

bool t5Miss  = array.get(LAST_TFTIME, 0) == 0
bool t15Miss = array.get(LAST_TFTIME, 1) == 0 or na(exp15)
bool t5Bad   = isChart5M and barstate.isconfirmed and array.get(LAST_TFTIME, 0) != t5
bool t15Bad  = not t15Miss and array.get(LAST_TFTIME, 1) != exp15
bool valBad  = array.get(V2_BADX, 0) or array.get(V2_BADX, 1)
var int need5  = f_maxHold(0)
var int need15 = f_maxHold(1)
bool srcBad  = t5Bad or t15Bad or valBad
bool srcWarm = array.get(V2_WARM, 0) >= need5 and array.get(V2_WARM, 1) >= need15
// STATUS : 0 出力中 / 1 データ準備中 / 3 5分足以外 / 4 更新不整合
int srcStatusNow = not isChart5M ? 3 : srcBad ? 4 : (t5Miss or t15Miss or not srcWarm) ? 1 : 0

// 系統ごとの点（TF ti）: [LONG 確認済み 0/1, LONG 統合 ×3（0〜3）, SHORT 確認済み, SHORT 統合 ×3]
f_famPts(int ti, int li0, int li1) =>
    bool  cL = false
    bool  cS = false
    float iL = 0.0
    float iS = 0.0
    for li = li0 to li1
        int  j  = f_idx(li, ti) * 2
        bool ad = array.get(V2_ADOPT, f_idx(li, ti))      // 採用 OFF は CURRENT も PRE も入れない
        bool vL = ad and array.get(V2_VALID, j)     and array.get(V2_PRICE, j)
        bool vS = ad and array.get(V2_VALID, j + 1) and array.get(V2_PRICE, j + 1)
        cL := cL or vL
        cS := cS or vS
        iL := math.max(iL, math.max(vL ? 1.0 : 0.0, ad ? array.get(V2_PRE, j)     : 0.0))
        iS := math.max(iS, math.max(vS ? 1.0 : 0.0, ad ? array.get(V2_PRE, j + 1) : 0.0))
    [cL ? 1 : 0, int(math.round(iL * 3)), cS ? 1 : 0, int(math.round(iS * 3))]

f_fam1(int ti, int li0, int li1, int off) =>
    [cL, qL, cS, qS] = f_famPts(ti, li0, li1)
    (cL + 2 * (qL >= 3 ? 1 : 0) + 4 * cS + 8 * (qS >= 3 ? 1 : 0)) * math.pow(2, off)

f_unpriced(int ti) =>
    bool u = false
    for li = 0 to N_LOGIC - 1
        int j = f_idx(li, ti) * 2
        u := u or (array.get(V2_ADOPT, f_idx(li, ti)) and ((array.get(V2_VALID, j) and not array.get(V2_PRICE, j)) or (array.get(V2_VALID, j + 1) and not array.get(V2_PRICE, j + 1))))
    u

f_payload(int ti) =>
    float base = (array.get(V2_NEG, ti * 2) > 0 ? 1 : 0) + (array.get(V2_NEG, ti * 2 + 1) > 0 ? 2 : 0) + (f_unpriced(ti) ? 4 : 0)
    base + {cfg['payload']}

int   BUS_BASE   = 1577836800000          // 2020-01-01 00:00 UTC
float BUS_SLOTS  = 4194304.0              // 2^22
int   BUS_FORMAT = 3                      // 時刻修正版（旧 5分・15分版 = 2 / 1 分足あり版 = 1）
f_bus(int tfId, float payload, int tclose) =>
    float slot = (tclose - BUS_BASE) / 300000.0
    bool  ok   = slot >= 0 and slot < BUS_SLOTS and slot == math.floor(slot) and payload >= 0 and payload < 2097152
    ok ? BUS_FORMAT + 4 * {sid} + 16 * tfId + 64 * slot + 268435456.0 * payload : na

// ---- 単体診断 BUS（STUDY DATA BUS / STUDY META BUS）-------------------------------------
// 選んだ 1 ロジック × 1 TF の、既に計算済みの値を 5 分足の確定時点で整数へ詰める（検知関数・request は呼び直さない）。
// STUDY META BUS（非負整数 < 2^37）
//   bit 0-1 format = 2（時刻修正版。旧 = 1）/ bit 2-3 SourceID（1 A / 2 B / 3 C）/ bit 4-5 TFID（1 = 5M / 2 = 15M）/
//   bit 6-10 ロジック番号（1〜25。元版の Logic 番号）/ bit 11-13 状態（0 出力中 / 1 データ準備中 / 4 更新不整合 / 6 対象外）/
//   bit 14 採用（1 = B の系統点へ採用中）/ bit 15-36 slot（= 通常 BUS と同じ。2020-01-01 00:05〜2059-11-23 頃の 5 分足）
//   slot が範囲外の足、5 分足以外のチャートでは na。状態が 0 以外でも META は出す（DATA は na）。
// STUDY DATA BUS（非負整数 < 2^51。META の状態 0 の足だけ出す）
//   bit 0 / 1  : 生シグナル LONG / SHORT（その TF の新しい確定足で検知関数が発火。裁定・採用の前）
//   bit 2 / 3  : 有効な CURRENT LONG / SHORT（価格否定・期限・裁定・採用設定を適用した後）
//   bit 4-5 / 6-7 : 抑止前 PRE 強度 LONG / SHORT（0〜3 = 0 / 1/3 / 2/3 / 1。丸めなし）
//   bit 8 / 9  : 価格否定による解除 LONG / SHORT（その TF 足）
//   bit 10 / 11: 期限切れによる解除 LONG / SHORT（その TF 足。同じ足で同方向に再登録された場合は含めない）
//   bit 12-17 / 18-23 : 最後の生シグナルからのその TF の本数 LONG / SHORT（0〜61、62 = 62 本以上、63 = 未発生）
//   bit 24-29 / 30-35 : 有効根拠の経過本数 LONG / SHORT（最後の登録 = 同方向の新シグナルによる期限更新から数え直し。
//                       0〜61、62 = 62 本以上、63 = 有効根拠なし。状態型 SAT は生シグナルからの本数）
//   bit 36     : この 5 分足の間に、その TF の新しい確定足を処理した（0 のときは bit 0/1/8〜11 は 0）
//   bit 37-50  : slot の下位 14 bit（META と同じ 5 分足であることの照合用）
studyLogicStr = input.string("{cfg['labels'][0]}", "診断対象ロジック", options = [{', '.join('"' + l + '"' for l in cfg['labels'])}], group = "⑨ 単体診断（Logic Verifier 用。通常 BUS・判定には影響しない）")
studyTfStr    = input.string("5M", "診断対象の時間足", options = ["5M", "15M"], group = "⑨ 単体診断（Logic Verifier 用。通常 BUS・判定には影響しない）")
var LABELS = array.from({', '.join('"' + l + '"' for l in cfg['labels'])})
int  STUDY_LI = array.indexof(LABELS, studyLogicStr)
int  STUDY_TI = studyTfStr == "5M" ? 0 : 1
// 元々その TF が対象外の組合せ（EMA ロジックの 15M など）は「対象外」。検知対象は増やさない
bool STUDY_NA = {cfg['studyna']}

f_cap6(int v) =>
    v < 0 ? 63 : v >= 62 ? 62 : v

f_study(int status, int tclose) =>
    float slot = (tclose - BUS_BASE) / 300000.0
    bool  sOk  = slot >= 0 and slot < BUS_SLOTS and slot == math.floor(slot)
    int   st   = STUDY_NA ? 6 : status
    int   j    = f_idx(STUDY_LI, STUDY_TI) * 2
    bool  nb   = array.get(V2_NEWBAR, STUDY_TI)
    bool  ad   = array.get(V2_ADOPT, f_idx(STUDY_LI, STUDY_TI))
    bool  cL   = ad and array.get(V2_VALID, j)     and array.get(V2_PRICE, j)
    bool  cS   = ad and array.get(V2_VALID, j + 1) and array.get(V2_PRICE, j + 1)
    bool  isSt = array.get(V2_RULE, STUDY_LI) == 3
    int   ageL = cL ? (isSt ? array.get(V2_SINCE, j)     : array.get(V2_AGE, j))     : -1
    int   ageS = cS ? (isSt ? array.get(V2_SINCE, j + 1) : array.get(V2_AGE, j + 1)) : -1
    float data = (nb and array.get(V2_RAW, j) ? 1 : 0) + (nb and array.get(V2_RAW, j + 1) ? 2 : 0) + (cL ? 4 : 0) + (cS ? 8 : 0) +
         16 * math.round(array.get(V2_PRE, j) * 3) + 64 * math.round(array.get(V2_PRE, j + 1) * 3) +
         (nb and array.get(V2_NEGF, j) ? 256 : 0) + (nb and array.get(V2_NEGF, j + 1) ? 512 : 0) +
         (nb and array.get(V2_EXPF, j) ? 1024 : 0) + (nb and array.get(V2_EXPF, j + 1) ? 2048 : 0) +
         4096.0 * f_cap6(array.get(V2_SINCE, j)) + 262144.0 * f_cap6(array.get(V2_SINCE, j + 1)) +
         16777216.0 * f_cap6(ageL) + 1073741824.0 * f_cap6(ageS) + (nb ? 68719476736.0 : 0) +
         137438953472.0 * (slot % 16384)
    float meta = 2 + 4 * {sid} + 16 * (STUDY_TI + 1) + 64 * ({cfg['goff']} + STUDY_LI + 1) + 2048 * st + 16384 * (ad ? 1 : 0) + 32768.0 * slot
    [sOk and st == 0 ? data : na, sOk ? meta : na]

var float studyData = na
var float studyMeta = na
var float bus5  = na
var float bus15 = na
var int   srcLastBar = 0
var int   srcStatus  = 1
if isChart5M and barstate.isconfirmed and time > srcLastBar
    srcLastBar := time
    srcStatus  := srcStatusNow
    array.set(V2_WARM, 0, t5Bad  or t5Miss  or array.get(V2_BADX, 0) ? 0 : array.get(V2_WARM, 0))
    array.set(V2_WARM, 1, t15Bad or t15Miss or array.get(V2_BADX, 1) ? 0 : array.get(V2_WARM, 1))
    // BUS の TF ID は 5M = 1 / 15M = 2（内部 index 0 / 1 とは別）
    bus5  := srcStatusNow == 0 ? f_bus(1, f_payload(0), time_close) : na
    bus15 := srcStatusNow == 0 ? f_bus(2, f_payload(1), time_close) : na
    [sData, sMeta] = f_study(srcStatusNow, time_close)
    studyData := sData
    studyMeta := sMeta
    array.fill(V2_NEG, 0)
    array.fill(V2_BADX, false)
    array.fill(V2_NEWBAR, false)

plot(isChart5M ? bus5  : na, "{S} 5M BUS",  display = display.data_window)
plot(isChart5M ? bus15 : na, "{S} 15M BUS", display = display.data_window)
plot(isChart5M ? srcStatus : 3, "{S} STATUS", display = display.data_window)
plot(isChart5M ? studyData : na, "STUDY DATA BUS", display = display.data_window)
plot(isChart5M ? studyMeta : na, "STUDY META BUS", display = display.data_window)

// ---- 設定の記録（採用 / 保持本数の比較結果と一緒に控える用。計算には影響しない）-------------------
// 保持本数の比較は既存の「③ 保持本数」input を 1 ロジック × 1 TF ずつ変えて、履歴再計算で 1 設定ずつ行う
// （複数候補を同時に計算しない）。本数はその TF 自身の本数（5M の 3 本と 15M の 3 本は同じ経過時間ではない）。
// 保持本数を変えると準備本数（最大保持本数）も変わる場合があるので、比較は同じ集計期間に揃える。
recShow = input.bool(false, "設定の記録を表示", group = "⑩ 設定の記録（結果と一緒に控える用）")
recPos  = input.string(position.top_left, "表示位置", options = [position.top_left, position.middle_left, position.bottom_left, position.top_center, position.bottom_center], group = "⑩ 設定の記録（結果と一緒に控える用）")
var recTbl = table.new(recPos, 1, 4, border_width = 1)
if barstate.islast
    table.clear(recTbl, 0, 0, 0, 3)
    if recShow
        string offTxt  = ""
        string holdTxt = ""
        for li = 0 to N_LOGIC - 1
            for ti = 0 to N_TF - 1
                int  k   = f_idx(li, ti)
                bool app = not ({cfg['naexpr']})
                string nm = array.get(LABELS, li) + (ti == 0 ? " 5M" : " 15M")
                offTxt  += app and not array.get(V2_ADOPT, k) ? (offTxt == "" ? "" : ", ") + nm : ""
                holdTxt += app and array.get(V2_RULE, li) != 3 and array.get(HOLD_ALL, k) != (ti == 0 ? 6 : 4) ? (holdTxt == "" ? "" : ", ") + nm + "=" + str.tostring(array.get(HOLD_ALL, k)) : ""
        table.cell(recTbl, 0, 0, "{cfg['short']} 設定（比較元 0e56963 の既定 : 全て採用 / 保持 5M 6・15M 4）", text_color = color.white, bgcolor = color.new(#1e222d, 20), text_size = size.small)
        table.cell(recTbl, 0, 1, "採用 : " + (adoptAll ? "全て採用" : "カスタム / OFF = " + (offTxt == "" ? "なし" : offTxt)), text_color = color.white, bgcolor = color.new(#1e222d, 20), text_size = size.small)
        table.cell(recTbl, 0, 2, "保持本数（既定と異なるもの）: " + (holdTxt == "" ? "なし" : holdTxt), text_color = color.white, bgcolor = color.new(#1e222d, 20), text_size = size.small)
        table.cell(recTbl, 0, 3, "単体診断 : " + studyLogicStr + " " + studyTfStr + "（状態型 SAT は保持本数を使わない）", text_color = color.white, bgcolor = color.new(#1e222d, 20), text_size = size.small)
""")
    return '\n'.join(o)


def build(cfg):
    out = [COMMON_HEAD]
    out.append(f'''// =====================================================================================
// {cfg['title']}  ―  POINT MASTER B 5分・15分専用版 Source {cfg['id']}（{cfg['desc']}）
// =====================================================================================
// 1 分足あり版 Source（PM-SRC-{cfg['id']}-V2）から 1 分足の取得・状態・準備確認・保持設定・BUS を取り除き、
// 5 分足と 15 分足だけで、担当ロジックの検知・抑止前 PRE・V2 有効根拠（否定ライン / 価格否定 / 期限 / Fib 解除）・
// 系統点・データ準備確認を行う版（時刻修正版）。5M はチャート自身の Engine 結果をその足の確定時に適用し、
// 15M は lookahead_off の現在値を 15M 区間の最後の 5M 足の確定時だけ受理する。根拠の計算内容は 1 分足あり版と同じ。
// 検知モジュール（入力・PRM 束・ロジック関数・Engine 関数）は V2 版からそのまま移している（条件の変更なし）。
// 取り除いたもの : 他 Source のロジック / 1H・4H・1D の取得 / ロジック名・Weight / 元版の ST_STATE・スコア・PRE スコア・
//                  PHASE・VALID TP / 旧テーブル・旧アラート・LOT ADJUST / モード A / 判定（Decision が担当）
// 使い方 : 5 分足チャートに追加し、PointMasterDecision5M15M（PM-DEC-515）の入力
//          「{cfg['id']} 5M BUS / {cfg['id']} 15M BUS」へ、この Source の同名出力を接続する。TF は 5M / 15M 固定。
{BUS_DOC}//   payload の系統配置（この Source）: {cfg['layout']}
// =====================================================================================
indicator(
     title         = "{cfg['title']}",
     shorttitle    = "{cfg['short']}",
     overlay       = true,
     max_bars_back = 500
 )

// =====================================================================================
// §0. 定数（この Source 内のロジック番号は 0 始まりのローカル番号。{cfg['map']}）
// =====================================================================================
int N_LOGIC = {cfg['n']}
int N_TF    = 2            // 内部 index 0 = 5M / 1 = 15M（1M は持たない）
int CONF_IGNORE = 0
int CONF_LONG   = 1
int CONF_SHORT  = 2
f_idx(li, ti) => li * N_TF + ti
// 時間足（5M / 15M 固定）。tfStr1 は Engine A の EMA 対象 TF 判定（元版は 1M / 5M のみ対象）で参照されるだけで、
// 1M のデータ取得には使わない（この版は 1M を取得しない。15M へ EMA ロジックを新たに適用しない）
tfStr1 = "1"
tfStr2 = "5"
tfStr3 = "15"

// =====================================================================================
// §3. 保持本数（元版と同じ input・初期値。5M / 15M のみ）＝ V2 有効根拠の期限
// =====================================================================================
{holds(cfg['nums'])}
{hold_arrays(cfg['nums'], cfg.get('ema', ()), cfg.get('sat', ()))}

grpRule = "⑤ 状態管理ルール"
conflictStr = input.string("無視 (現状維持)", "同一ロジック・同一TFで両方向が同時発生した時",
     options = ["無視 (現状維持)", "LONG優先", "SHORT優先"], group = grpRule)
conflictMode = conflictStr == "LONG優先" ? CONF_LONG : conflictStr == "SHORT優先" ? CONF_SHORT : CONF_IGNORE

// =====================================================================================
// §4. 検知モジュール（V2 版からそのまま移したもの）
// =====================================================================================
''')
    out.append(cfg['modules'])
    out.append(infra(cfg))
    return '\n'.join(out) + '\n'


XA = ['xC', 'xH', 'xL', 'xEa', 'xEb', 'xEc', 'xEd', 'x01L', 'x01S', 'x02L', 'x02S', 'x03L', 'x03S', 'x04L', 'x04S', 'xTc', 'xCp', 'xEaP', 'xAtr', 'xOn']
XB = ['xC'] + [f'x{n}{d}' for n in range(13, 19) for d in 'LS'] + [f's{n}{d}' for n in range(13, 19) for d in 'LS'] + ['xTc']
XC = ['xC', 'xH', 'xL', 'x19L', 'x19S', 'x20L', 'x20S', 'xTc']

CFG = [
    dict(id='A', sid=1, n=12, naexpr='ti == 1 and li >= 4', trace=True, labels=['Logic01 FVG Abs', 'Logic02 FVG Reb', 'Logic03 Accum Reb', 'Logic04 Accum Brk', 'Logic05 EMA200 Reb', 'Logic06 EMA1000 Reb', 'Logic07 EMA2000 Reb', 'Logic08 EMA3000 Reb', 'Logic09 EMA200 Brk', 'Logic10 EMA1000 Brk', 'Logic11 EMA2000 Brk', 'Logic12 EMA3000 Brk'], goff=0, studyna='STUDY_TI == 1 and STUDY_LI >= 4', nums=list(range(1, 13)), ema=tuple(range(5, 13)), nx=20, xs=XA, tuple=4, tcidx=15, eng='f_signalMasksA',
         title='POINT MASTER SOURCE A 5M15M', short='PM-A-515', desc='Logic01〜12 : FVG / Accum / EMA',
         map='0〜3 = Logic01〜04 / 4〜11 = Logic05〜12',
         layout='価格帯（Logic01〜04）= bit 3-6 / MA（Logic05〜12）= bit 7-10',
         rules='0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1', ei='rule == 1 ? 3 + math.max(li - 4, 0) % 4 : 3', fibinv='false',
         lvN='li <= 3 ? array.get(x, 7 + math.min(math.max(li, 0), 3) * 2 + d) : float(na)', slN='0.0',
         pre='0.0', ltfpre='0.0, 0.0, 0.0, 0.0',
         payload='f_fam1(ti, 0, 3, 3) + f_fam1(ti, 4, 11, 7)',
         modules='\n'.join([MOD_A, PACKF, ENG_A, BITONF])),
    dict(id='B', sid=2, n=6, naexpr='false', labels=['Logic13 TL Reb', 'Logic14 TL Brk', 'Logic15 H&S', 'Logic16 DT/DB', 'Logic17 Wedge', 'Logic18 Triangle'], goff=12, studyna='false', nums=list(range(13, 19)), nx=26, xs=XB, tuple=6, tcidx=25, eng='f_signalMasksB',
         title='POINT MASTER SOURCE B 5M15M', short='PM-B-515', desc='Logic13〜18 : TL / 三尊 / DTB / ウェッジ / 三角形',
         map='0〜5 = Logic13〜18',
         layout='形状（Logic13〜18）= bit 3-6',
         rules='0, 0, 0, 0, 0, 0', ei='0', fibinv='false',
         lvN='array.get(x, 1 + math.min(math.max(li, 0), 5) * 2 + d)', slN='nz(array.get(x, 13 + math.min(math.max(li, 0), 5) * 2 + d))',
         pre='d == 0 ? (f_bitOn(plm, li) ? 1.0 : 0.0) : (f_bitOn(psm, li) ? 1.0 : 0.0)',
         ltfpre='nz(array.get(LTF_PLM, _i)), nz(array.get(LTF_PSM, _i)), 0.0, 0.0',
         payload='f_fam1(ti, 0, 5, 3)',
         modules='\n'.join([MOD_B, PACKF, ENG_B, BITONF])),
    dict(id='C', sid=3, n=7, naexpr='false', labels=['Logic19 Horiz Reb', 'Logic20 Horiz Brk', 'Logic21 Fib382', 'Logic22 Fib500', 'Logic23 Fib618', 'Logic24 SAT', 'Logic25 Stoch'], goff=18, studyna='false', nums=list(range(19, 26)), sat=(24,), nx=8, xs=XC, tuple=8, tcidx=7, eng='f_signalMasksC',
         title='POINT MASTER SOURCE C 5M15M', short='PM-C-515', desc='Logic19〜25 : 水平線 / Fib / SAT / ストキャス',
         map='0〜1 = Logic19〜20 / 2〜4 = Logic21〜23 / 5 = Logic24 / 6 = Logic25',
         layout='価格帯（Logic19〜20）= bit 3-6 / Fib = bit 7-10 / SAT = bit 11-16（LONG 確認 11・統合 12-13、SHORT 確認 14・統合 15-16）/ ストキャス = bit 17-20',
         rules='0, 0, 2, 2, 2, 3, 4', ei='0', fibinv='li >= 2 and li <= 4 and f_bitOn(im, li)',
         lvN='li <= 1 ? array.get(x, 3 + math.min(math.max(li, 0), 1) * 2 + d) : li == 6 ? (d == 0 ? array.get(x, 2) : array.get(x, 1)) : float(na)',
         slN='0.0',
         pre='li == 5 ? (d == 0 ? math.max(sp, 0.0) : math.max(-sp, 0.0)) : d == 0 ? (f_bitOn(plm, li) ? 1.0 : 0.0) : (f_bitOn(psm, li) ? 1.0 : 0.0)',
         ltfpre='nz(array.get(LTF_PLM, _i)), nz(array.get(LTF_PSM, _i)), nz(array.get(LTF_IM, _i)), nz(array.get(LTF_SP, _i))',
         payload='f_fam1(ti, 0, 1, 3) + f_fam1(ti, 2, 4, 7) + f_satBits(ti) + f_fam1(ti, 6, 6, 17)',
         modules='\n'.join([MOD_C1, PACKF, MOD_C2, ENG_C, BITONF])),
]

SAT_BITS = '''
// SAT 系統（Logic24 のみ）: bit 11 LONG 確認 / 12-13 LONG 統合 0〜3 / 14 SHORT 確認 / 15-16 SHORT 統合 0〜3
f_satBits(int ti) =>
    [cL, qL, cS, qS] = f_famPts(ti, 5, 5)
    (cL + 2 * qL + 8 * cS + 16 * qS) * math.pow(2, 11)
'''

TRACE_CAP = """
    // ★時刻照合（Source A のみ）: f_v2ApplyTf(0) に渡したのと同じ 5M 元足の UDT と開始時刻を保持（判定には使わない）
    TR_X5   := x5
    trOpen5 := t5"""

TRACE_NB = """    trNb := array.get(V2_NEWBAR, 0)      // ★時刻照合 : この 5 分足で 5M 元足を処理したか（リセット前に退避）
    array.fill(V2_NEWBAR, false)"""

TRACE_SEC = open(f'{ROOT}/tests/pm_515_trace_a.pine', encoding='utf-8').read()

for cfg in CFG:
    txt = build(cfg)
    if cfg.get('trace'):
        a5 = '    f_v2ApplyTf(0, lm5, sm5, plm5, psm5, im5, sp5, x5)'
        assert txt.count(a5) == 1
        txt = txt.replace(a5, a5 + TRACE_CAP)
        assert txt.count('int  t5  = time') == 1
        txt = txt.replace('int  t5  = time', 'var TR_X5   = array.new_float(20, na)   // ★時刻照合（Source A のみ）\nvar int trOpen5 = na\nvar bool trNb  = false\nint  t5  = time', 1)
        nb0 = '    array.fill(V2_NEWBAR, false)'
        assert txt.count(nb0) == 1
        txt = txt.replace(nb0, TRACE_NB)
        txt = txt.rstrip('\n') + '\n\n' + TRACE_SEC
    if cfg['id'] == 'C':
        txt = txt.replace('f_payload(int ti) =>', SAT_BITS.strip('\n') + '\n\nf_payload(int ti) =>')
    open(f'{ROOT}/PointMasterSource{cfg["id"]}5M15M.pine', 'w', encoding='utf-8').write(txt)
    print('wrote', cfg['id'], len(txt.split('\n')), 'lines')
