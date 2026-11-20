"""POINT MASTER V2-B 分割版の Source A / B / C を生成する。

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

# Engine B / C の V2 追加出力の先頭に、この TF 足の close（C は high / low も）を加える（判定には使わない）
old_b = '    [lmB, smB, preLmB, preSmB, x13L,'
assert ENG_B.count(old_b) == 1
ENG_B = ENG_B.replace(old_b, '    [lmB, smB, preLmB, preSmB, close, x13L,')
old_c = '    [lmC, smC, imC, preLmC, preSmC, satPreSigned, x19L, x19S, x20L, x20S]'
assert ENG_C.count(old_c) == 1
ENG_C = ENG_C.replace(old_c, '    [lmC, smC, imC, preLmC, preSmC, satPreSigned, close, high, low, x19L, x19S, x20L, x20S]')


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
            m = re.match(rf'^h{tag}([abc]) = ', l)
            if m:
                out.append(l)
    return '\n'.join(out)


def hold_arrays(nums, ema=(), sat=()):
    rows = []
    for n in nums:
        t = f'{n:02d}'
        if n in sat:
            rows.append(f'HOLD{t} = array.from(0, 0, 0)          // 状態型（保持本数を使わない）')
        elif n in ema:
            rows.append(f'HOLD{t} = array.from(h{t}a, h{t}b, 1)    // EMA は 1M / 5M のみ対象（15M はイベントが出ないダミー値。元版と同じ）')
        else:
            rows.append(f'HOLD{t} = array.from(h{t}a, h{t}b, h{t}c)')
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
//     bit 0-1   : format = 1
//     bit 2-3   : SourceID（1 = A / 2 = B / 3 = C）
//     bit 4-5   : TFID（0 = 1M / 1 = 5M / 2 = 15M）
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


def infra(cfg):
    """Source 共通の基盤（1M/5M/15M 取得・V2 有効根拠・準備判定・BUS）"""
    S = cfg['id']          # 'A' / 'B' / 'C'
    sid = cfg['sid']
    nx = cfg['nx']
    xs = cfg['xs']         # Engine 関数の V2 追加出力の変数名
    pre = cfg['pre']       # PRE を持つか
    eng = cfg['eng']       # Engine 関数名
    o = []
    # ---- UDT / パケット / 取得 ----
    o.append(f'''// =====================================================================================
// §5. 1M / 5M / 15M 取得（元版の非リペイント方式のまま）
// =====================================================================================
// 5M / 15M : request.security(..., <式>[1], lookahead = barmerge.lookahead_on)（直近の確定足。[1] は必須）
// 1M       : request.security_lower_tf() で、その 5 分足に含まれる確定 1 分足を配列で受け取り、時刻順に 1 本ずつ処理
//            （OR 集約にしない。前の 5 分足で配列に含まれなかった 1 分足を後追いで処理する実装は無い）
// V2 用の追加出力（この TF 足の close 等・否定ライン）は 1 個の UDT にまとめて返す。
// request 呼び出し 3 本、タプル要素 {cfg['tuple']} × 3 = {cfg['tuple'] * 3} 個。
type SRC{S}X
''' + ''.join(f'    float f{i} = na\n' for i in range(nx)) + f'''
f_srcArr(SRC{S}X o) =>
    SRC{S}X q = na(o) ? SRC{S}X.new() : o
    array.from(''' + ', '.join(f'q.f{i}' for i in range(nx)) + ''')
''')
    if S == 'A':
        o.append(f'''f_htfPacket() =>
    [lmRaw, smRaw, {', '.join(xs)}] = {eng}()
    float lm = nz(lmRaw)
    float sm = nz(smRaw)
    int   tt = time
    [lm[1], sm[1], tt[1], SRC{S}X.new({', '.join(v + '[1]' for v in xs)})]   // ★[1] は必須（外すと未来参照）

f_ltfPacket() =>
    [lmRaw, smRaw, {', '.join(xs)}] = {eng}()
    [nz(lmRaw), nz(smRaw), time, SRC{S}X.new({', '.join(xs)})]

ltfStr1 = timeframe.in_seconds(tfStr1) <= timeframe.in_seconds() ? tfStr1 : timeframe.period
[LTF_LM, LTF_SM, LTF_TIME, LTF_X] = request.security_lower_tf(syminfo.tickerid, ltfStr1, f_ltfPacket())
[lm2, sm2, tt2, ox2] = request.security(syminfo.tickerid, tfStr2, f_htfPacket(), lookahead = barmerge.lookahead_on)
[lm3, sm3, tt3, ox3] = request.security(syminfo.tickerid, tfStr3, f_htfPacket(), lookahead = barmerge.lookahead_on)
float plm2 = 0.0
float psm2 = 0.0
float plm3 = 0.0
float psm3 = 0.0
float im2  = 0.0
float im3  = 0.0
float sp2  = 0.0
float sp3  = 0.0
''')
    elif S == 'B':
        o.append(f'''f_htfPacket() =>
    [lmRaw, smRaw, plmRaw, psmRaw, {', '.join(xs)}] = {eng}()
    float lm  = nz(lmRaw)
    float sm  = nz(smRaw)
    float plm = nz(plmRaw)
    float psm = nz(psmRaw)
    int   tt  = time
    [lm[1], sm[1], plm[1], psm[1], tt[1], SRC{S}X.new({', '.join(v + '[1]' for v in xs)})]   // ★[1] は必須

f_ltfPacket() =>
    [lmRaw, smRaw, plmRaw, psmRaw, {', '.join(xs)}] = {eng}()
    [nz(lmRaw), nz(smRaw), nz(plmRaw), nz(psmRaw), time, SRC{S}X.new({', '.join(xs)})]

ltfStr1 = timeframe.in_seconds(tfStr1) <= timeframe.in_seconds() ? tfStr1 : timeframe.period
[LTF_LM, LTF_SM, LTF_PLM, LTF_PSM, LTF_TIME, LTF_X] = request.security_lower_tf(syminfo.tickerid, ltfStr1, f_ltfPacket())
[lm2, sm2, plm2, psm2, tt2, ox2] = request.security(syminfo.tickerid, tfStr2, f_htfPacket(), lookahead = barmerge.lookahead_on)
[lm3, sm3, plm3, psm3, tt3, ox3] = request.security(syminfo.tickerid, tfStr3, f_htfPacket(), lookahead = barmerge.lookahead_on)
float im2  = 0.0
float im3  = 0.0
float sp2  = 0.0
float sp3  = 0.0
''')
    else:
        o.append(f'''f_htfPacket() =>
    [lmRaw, smRaw, imRaw, plmRaw, psmRaw, spRaw, {', '.join(xs)}] = {eng}()
    float lm  = nz(lmRaw)
    float sm  = nz(smRaw)
    float im  = nz(imRaw)
    float plm = nz(plmRaw)
    float psm = nz(psmRaw)
    float sp  = nz(spRaw)
    int   tt  = time
    [lm[1], sm[1], im[1], plm[1], psm[1], sp[1], tt[1], SRC{S}X.new({', '.join(v + '[1]' for v in xs)})]   // ★[1] は必須

f_ltfPacket() =>
    [lmRaw, smRaw, imRaw, plmRaw, psmRaw, spRaw, {', '.join(xs)}] = {eng}()
    [nz(lmRaw), nz(smRaw), nz(imRaw), nz(plmRaw), nz(psmRaw), nz(spRaw), time, SRC{S}X.new({', '.join(xs)})]

ltfStr1 = timeframe.in_seconds(tfStr1) <= timeframe.in_seconds() ? tfStr1 : timeframe.period
[LTF_LM, LTF_SM, LTF_IM, LTF_PLM, LTF_PSM, LTF_SP, LTF_TIME, LTF_X] = request.security_lower_tf(syminfo.tickerid, ltfStr1, f_ltfPacket())
[lm2, sm2, im2, plm2, psm2, sp2, tt2, ox2] = request.security(syminfo.tickerid, tfStr2, f_htfPacket(), lookahead = barmerge.lookahead_on)
[lm3, sm3, im3, plm3, psm3, sp3, tt3, ox3] = request.security(syminfo.tickerid, tfStr3, f_htfPacket(), lookahead = barmerge.lookahead_on)
''')
    # ---- V2 有効根拠 ----
    o.append(f'''
// =====================================================================================
// §6. V2 有効根拠（ロジック × TF × 方向）と抑止前 PRE（最新 V2 と同じ扱い）
// =====================================================================================
// 生シグナル成立時に登録し、元版の保持本数（期限）と価格否定（その TF の確定終値）の早い方で解除。
// 同方向の新シグナルで再登録、同じロジック × TF で反対方向の新シグナルが出たら切替で解除。
// 同一足で両方向が出た場合の裁定は元版の「状態管理ルール」と同じ。元版の ST_STATE / スコアは持たない。
// 否定ルール（V2_RULE）: 0 ライン（成立時の値 + 傾き × 経過本数）/ 1 EMA 現在値 / 2 Fib 継承（価格ラインなし）/
//                         3 状態型（SAT）/ 4 成立足の安値・高値（Stoch）
// PRE は抑止前の State Factor（0 / 1、SAT のみ 0 / 1/3 / 2/3）を、その TF の確定足ごとに上書き（保持なし）。
var LAST_TFTIME = array.new_int(N_TF, 0)
var V2_RULE  = array.from({cfg['rules']})
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

f_v2ApplyTf(int ti, float lm, float sm, float plm, float psm, float im, float sp, array<float> x) =>
    float tc = array.get(x, 0)
    array.set(V2_WARM, ti, array.get(V2_WARM, ti) + 1)
    array.set(V2_BADX, ti, array.get(V2_BADX, ti) or na(tc))
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
            array.set(V2_NEG,   ti * 2 + d, array.get(V2_NEG, ti * 2 + d) + (negd ? 1 : 0))
            // 抑止前 PRE（その TF の確定足1本ぶんの現在値で上書き）
            array.set(V2_PRE, j, {cfg['pre']})
    N_LOGIC

// ① 1M : この 5 分足に含まれる確定 1 分足を時刻順に 1 本ずつ処理（同じ 1 分足は二度処理しない）
int _ltfN = array.size(LTF_TIME)
if _ltfN > 0
    for _i = 0 to _ltfN - 1
        int _t = array.get(LTF_TIME, _i)
        if not na(_t) and _t > array.get(LAST_TFTIME, 0) and _i < array.size(LTF_LM)
            array.set(LAST_TFTIME, 0, _t)
            f_v2ApplyTf(0, nz(array.get(LTF_LM, _i)), nz(array.get(LTF_SM, _i)), {cfg['ltfpre']}, f_srcArr(array.get(LTF_X, _i)))

// ② 5M / 15M : その TF の確定足が新しくなった瞬間だけ更新
TF_TIME = array.from(0, nz(tt2), nz(tt3))
if array.get(TF_TIME, 1) > array.get(LAST_TFTIME, 1)
    array.set(LAST_TFTIME, 1, array.get(TF_TIME, 1))
    f_v2ApplyTf(1, nz(lm2), nz(sm2), nz(plm2), nz(psm2), nz(im2), nz(sp2), f_srcArr(ox2))
if array.get(TF_TIME, 2) > array.get(LAST_TFTIME, 2)
    array.set(LAST_TFTIME, 2, array.get(TF_TIME, 2))
    f_v2ApplyTf(2, nz(lm3), nz(sm3), nz(plm3), nz(psm3), nz(im3), nz(sp3), f_srcArr(ox3))
''')
    # ---- 準備判定・BUS ----
    o.append(f'''
// =====================================================================================
// §7. データ準備 / 更新整合（最新 V2 と同じ確認）と BUS 出力
// =====================================================================================
//   1M  : 配列が空 = 未準備。この 5 分足の範囲外・逆順の時刻 = 不整合。最後に処理した 1 分足が配列末尾と一致すること。
//         （これは「受け取った配列を末尾まで処理したか」の確認で、その 5 分間の全確定 1 分足の取得保証ではない。
//           配列に無かった 1 分足は自動補完されず、取りこぼしが起きるかは未確認）
//   5M / 15M : 受信した確定足の開始時刻（tt[1]）が「この足の TF 区間の直前に足が存在した区間」と一致すること
//              （休場・週末は直前に足が存在した区間と比べるので不整合にしない）
//   値 : 処理した TF 足の確定終値が na なら不整合 / 準備 : 不整合なしで各 TF の処理本数 >= その TF の最大保持本数
bool isChart5M = timeframe.isminutes and timeframe.multiplier == 5
var int bk5Cur   = na
var int bk5Prev  = na
var int bk15Cur  = na
var int bk15Prev = na
int bk5  = time - time % 300000
int bk15 = time - time % 900000
bk5Prev  := na(bk5Cur)  or bk5  != bk5Cur  ? bk5Cur  : bk5Prev
bk5Cur   := bk5
bk15Prev := na(bk15Cur) or bk15 != bk15Cur ? bk15Cur : bk15Prev
bk15Cur  := bk15

f_ltf1Bad() =>
    int  n   = array.size(LTF_TIME)
    bool bad = false
    if n > 0
        int prevT = na
        for _k = 0 to n - 1
            int t1 = array.get(LTF_TIME, _k)
            bad   := bad or na(t1) or t1 < time or t1 >= time_close or (not na(prevT) and t1 <= prevT)
            prevT := t1
        bad := bad or array.get(LAST_TFTIME, 0) != array.get(LTF_TIME, n - 1)
    bad

f_maxHold(int ti) =>
    int mx = 1
    for li = 0 to N_LOGIC - 1
        mx := math.max(mx, array.get(HOLD_ALL, f_idx(li, ti)))
    mx

bool t1Miss  = _ltfN == 0
bool t1Bad   = f_ltf1Bad()
bool t5Miss  = array.get(TF_TIME, 1) == 0 or na(bk5Prev)
bool t15Miss = array.get(TF_TIME, 2) == 0 or na(bk15Prev)
bool t5Bad   = not t5Miss  and array.get(TF_TIME, 1) != bk5Prev
bool t15Bad  = not t15Miss and array.get(TF_TIME, 2) != bk15Prev
bool valBad  = array.get(V2_BADX, 0) or array.get(V2_BADX, 1) or array.get(V2_BADX, 2)
var int need1  = f_maxHold(0)
var int need5  = f_maxHold(1)
var int need15 = f_maxHold(2)
bool srcBad  = t1Bad or t5Bad or t15Bad or valBad
bool srcWarm = array.get(V2_WARM, 0) >= need1 and array.get(V2_WARM, 1) >= need5 and array.get(V2_WARM, 2) >= need15
// STATUS : 0 出力中 / 1 データ準備中 / 3 5分足以外 / 4 更新不整合
int srcStatusNow = not isChart5M ? 3 : srcBad ? 4 : (t1Miss or t5Miss or t15Miss or not srcWarm) ? 1 : 0

// 系統ごとの点（TF ti）: [LONG 確認済み 0/1, LONG 統合 ×3（0〜3）, SHORT 確認済み, SHORT 統合 ×3]
//   確認済み = 系統内に価格基準つきの有効 CURRENT がある / 統合 = 系統内の max(有効 CURRENT 1, 抑止前 PRE)
//   同じロジック × TF × 方向の PRE と CURRENT は max（足し算しない）
f_famPts(int ti, int li0, int li1) =>
    bool  cL = false
    bool  cS = false
    float iL = 0.0
    float iS = 0.0
    for li = li0 to li1
        int  j  = f_idx(li, ti) * 2
        bool vL = array.get(V2_VALID, j)     and array.get(V2_PRICE, j)
        bool vS = array.get(V2_VALID, j + 1) and array.get(V2_PRICE, j + 1)
        cL := cL or vL
        cS := cS or vS
        iL := math.max(iL, math.max(vL ? 1.0 : 0.0, array.get(V2_PRE, j)))
        iS := math.max(iS, math.max(vS ? 1.0 : 0.0, array.get(V2_PRE, j + 1)))
    [cL ? 1 : 0, int(math.round(iL * 3)), cS ? 1 : 0, int(math.round(iS * 3))]

// 1bit 系統（統合強度は 0 / 1 しか取らない）を offset bit から 4bit で詰める
f_fam1(int ti, int li0, int li1, int off) =>
    [cL, qL, cS, qS] = f_famPts(ti, li0, li1)
    (cL + 2 * (qL >= 3 ? 1 : 0) + 4 * cS + 8 * (qS >= 3 ? 1 : 0)) * math.pow(2, off)

f_unpriced(int ti) =>
    bool u = false
    for j = f_idx(0, ti) * 2 to f_idx(0, ti) * 2 + 1
        u := u
    for li = 0 to N_LOGIC - 1
        int j = f_idx(li, ti) * 2
        u := u or (array.get(V2_VALID, j) and not array.get(V2_PRICE, j)) or (array.get(V2_VALID, j + 1) and not array.get(V2_PRICE, j + 1))
    u

f_payload(int ti) =>
    float base = (array.get(V2_NEG, ti * 2) > 0 ? 1 : 0) + (array.get(V2_NEG, ti * 2 + 1) > 0 ? 2 : 0) + (f_unpriced(ti) ? 4 : 0)
    base + {cfg['payload']}

int   BUS_BASE  = 1577836800000          // 2020-01-01 00:00 UTC
float BUS_SLOTS = 4194304.0              // 2^22
f_bus(int tfId, float payload, int tclose) =>
    float slot = (tclose - BUS_BASE) / 300000.0
    bool  ok   = slot >= 0 and slot < BUS_SLOTS and slot == math.floor(slot) and payload >= 0 and payload < 2097152
    ok ? 1 + 4 * {sid} + 16 * tfId + 64 * slot + 268435456.0 * payload : na

var float bus1  = na
var float bus5  = na
var float bus15 = na
var int   srcLastBar = 0
var int   srcStatus  = 1
if isChart5M and barstate.isconfirmed and time > srcLastBar
    srcLastBar := time
    srcStatus  := srcStatusNow
    // 不整合・未受信の TF は準備本数を数え直す
    array.set(V2_WARM, 0, t1Bad  or t1Miss  or array.get(V2_BADX, 0) ? 0 : array.get(V2_WARM, 0))
    array.set(V2_WARM, 1, t5Bad  or t5Miss  or array.get(V2_BADX, 1) ? 0 : array.get(V2_WARM, 1))
    array.set(V2_WARM, 2, t15Bad or t15Miss or array.get(V2_BADX, 2) ? 0 : array.get(V2_WARM, 2))
    bus1  := srcStatusNow == 0 ? f_bus(0, f_payload(0), time_close) : na
    bus5  := srcStatusNow == 0 ? f_bus(1, f_payload(1), time_close) : na
    bus15 := srcStatusNow == 0 ? f_bus(2, f_payload(2), time_close) : na
    array.fill(V2_NEG, 0)
    array.fill(V2_BADX, false)

plot(isChart5M ? bus1  : na, "{S} 1M BUS",  display = display.data_window)
plot(isChart5M ? bus5  : na, "{S} 5M BUS",  display = display.data_window)
plot(isChart5M ? bus15 : na, "{S} 15M BUS", display = display.data_window)
plot(isChart5M ? srcStatus : 3, "{S} STATUS", display = display.data_window)
''')
    return '\n'.join(o)


def build(cfg):
    out = [COMMON_HEAD]
    out.append(f'''// =====================================================================================
// {cfg['title']}  ―  POINT MASTER V2-B 分割版 Source {cfg['id']}（{cfg['desc']}）
// =====================================================================================
// PointMasterFvgAbsReboundV2.pine の V2-B から、担当ロジックの検知・抑止前 PRE・V2 有効根拠
// （否定ライン / 価格否定 / 期限 / Fib 解除）・系統点・データ準備確認だけを取り出したもの。
// 検知モジュール（入力・PRM 束・ロジック関数・Engine 関数）は V2 版からそのまま移している（条件の変更なし）。
// 取り除いたもの : 他 Source のロジック / 1H・4H・1D の取得 / ロジック名・Weight / 元版の ST_STATE・スコア・PRE スコア・
//                  PHASE・VALID TP / 旧テーブル・旧アラート・LOT ADJUST / モード A / 判定（Decision が担当）
// 使い方 : 5 分足チャートに追加し、PointMasterDecisionV2（PM-DEC-V2）の入力
//          「{cfg['id']} 1M BUS / {cfg['id']} 5M BUS / {cfg['id']} 15M BUS」へ、この Source の同名出力を接続する。
//          TF は 1M / 5M / 15M 固定（V2-B の構成）。
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
int N_TF    = 3            // 0 = 1M / 1 = 5M / 2 = 15M
int CONF_IGNORE = 0
int CONF_LONG   = 1
int CONF_SHORT  = 2
f_idx(li, ti) => li * N_TF + ti
// V2-B の時間足構成（1M / 5M / 15M 固定）
tfStr1 = "1"
tfStr2 = "5"
tfStr3 = "15"

// =====================================================================================
// §3. 保持本数（元版と同じ input・初期値。1M / 5M / 15M のみ）＝ V2 有効根拠の期限
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


XA = ['xC', 'xH', 'xL', 'xEa', 'xEb', 'xEc', 'xEd', 'x01L', 'x01S', 'x02L', 'x02S', 'x03L', 'x03S', 'x04L', 'x04S']
XB = ['xC'] + [f'x{n}{d}' for n in range(13, 19) for d in 'LS'] + [f's{n}{d}' for n in range(13, 19) for d in 'LS']
XC = ['xC', 'xH', 'xL', 'x19L', 'x19S', 'x20L', 'x20S']

CFG = [
    dict(id='A', sid=1, n=12, nums=list(range(1, 13)), ema=tuple(range(5, 13)), nx=15, xs=XA, tuple=4, eng='f_signalMasksA',
         title='POINT MASTER SOURCE A V2', short='PM-SRC-A-V2', desc='Logic01〜12 : FVG / Accum / EMA',
         map='0〜3 = Logic01〜04 / 4〜11 = Logic05〜12',
         layout='価格帯（Logic01〜04）= bit 3-6 / MA（Logic05〜12）= bit 7-10',
         rules='0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1', ei='rule == 1 ? 3 + math.max(li - 4, 0) % 4 : 3', fibinv='false',
         lvN='li <= 3 ? array.get(x, 7 + math.min(math.max(li, 0), 3) * 2 + d) : float(na)', slN='0.0',
         pre='0.0', ltfpre='0.0, 0.0, 0.0, 0.0',
         payload='f_fam1(ti, 0, 3, 3) + f_fam1(ti, 4, 11, 7)',
         modules='\n'.join([MOD_A, PACKF, ENG_A, BITONF])),
    dict(id='B', sid=2, n=6, nums=list(range(13, 19)), nx=25, xs=XB, tuple=6, eng='f_signalMasksB',
         title='POINT MASTER SOURCE B V2', short='PM-SRC-B-V2', desc='Logic13〜18 : TL / 三尊 / DTB / ウェッジ / 三角形',
         map='0〜5 = Logic13〜18',
         layout='形状（Logic13〜18）= bit 3-6',
         rules='0, 0, 0, 0, 0, 0', ei='0', fibinv='false',
         lvN='array.get(x, 1 + math.min(math.max(li, 0), 5) * 2 + d)', slN='nz(array.get(x, 13 + math.min(math.max(li, 0), 5) * 2 + d))',
         pre='d == 0 ? (f_bitOn(plm, li) ? 1.0 : 0.0) : (f_bitOn(psm, li) ? 1.0 : 0.0)',
         ltfpre='nz(array.get(LTF_PLM, _i)), nz(array.get(LTF_PSM, _i)), 0.0, 0.0',
         payload='f_fam1(ti, 0, 5, 3)',
         modules='\n'.join([MOD_B, PACKF, ENG_B, BITONF])),
    dict(id='C', sid=3, n=7, nums=list(range(19, 26)), sat=(24,), nx=7, xs=XC, tuple=8, eng='f_signalMasksC',
         title='POINT MASTER SOURCE C V2', short='PM-SRC-C-V2', desc='Logic19〜25 : 水平線 / Fib / SAT / ストキャス',
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

for cfg in CFG:
    txt = build(cfg)
    if cfg['id'] == 'C':
        txt = txt.replace('f_payload(int ti) =>', SAT_BITS.strip('\n') + '\n\nf_payload(int ti) =>')
    # f_unpriced の不要な空ループを除去（生成テンプレートの名残）
    txt = txt.replace('''    for j = f_idx(0, ti) * 2 to f_idx(0, ti) * 2 + 1
        u := u
''', '')
    open(f'{ROOT}/PointMasterSource{cfg["id"]}V2.pine', 'w', encoding='utf-8').write(txt)
    print('wrote', cfg['id'], len(txt.split('\n')), 'lines')
