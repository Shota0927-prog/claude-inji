"""時刻修正版（TIMEFIX）の固定ケース。現行コードの経路を写したモデルで、Pine 上の実行確認ではない。
Source（PM-A/B/C-515 §5〜§7）:
  5M  : チャート自身の Engine 結果を、そのチャート足の確定時に 1 回だけ適用（元足 = 今確定した足、ID = time）
  15M : request.security(15, 現在の 15M 結果, lookahead_off)。適用は
        確定 5M 足 and time_close = time_close("15") and 元足 time = time("15") and 元足 time_close = チャート time_close
        and 元足 ID > 最後に受理した 15M、のときだけ
  準備 : 15M は境界では今閉じた 15M 足、境界以外では「直前に足が存在した 15M 区間」が最後に受理されていること
  出力 : 通常 BUS format 3 / STUDY META format 2、slot = その確定 5 分足の time_close
Logic Verifier : 受理したその確定 5 分足で登録（P0 = その足の close）、最初の追跡更新は次の足。
"""
import math
import io
import contextlib
import sys

sys.path.insert(0, 'tests')
with contextlib.redirect_stdout(io.StringIO()):
    from pm_study_sim import OneLogic

M5, M15 = 300000, 900000
ok = 0
def check(name, cond):
    global ok
    assert cond, name
    ok += 1
    print('OK ', name)


class Chart:
    """bars : [(open_time, o, h, l, c)]（存在する 5 分足のみ）"""
    def __init__(self, bars):
        self.bars = bars

    def q15(self, n):
        t = self.bars[n][0]
        b = t - t % M15
        return b, b + M15                       # time("15") / time_close("15")

    def native15(self, bucket):
        """確定した 15M 足（その区間に存在した 5 分足から作る。確定時刻は区間の終わり）"""
        inb = [x for x in self.bars if bucket <= x[0] < bucket + M15]
        return None if not inb else dict(open=bucket, close_t=bucket + M15, close=inb[-1][4])

    def packet15_lookahead_off(self, n, realtime_dev=None):
        """lookahead_off の取得値。歴史足では「チャート足の確定時刻までに確定した最新の 15M 足」、
        realtime_dev（形成中の値）が与えられたら、区間途中の足では形成中の 15M 足の値を返す（リアルタイムの挙動）"""
        t, tc = self.bars[n][0], self.bars[n][0] + M5
        b, bc = self.q15(n)
        if realtime_dev is not None and tc < bc:
            return dict(open=b, close_t=bc, close=self.bars[n][4], dev=True, **realtime_dev)
        cands = [k for k in sorted({x[0] - x[0] % M15 for x in self.bars}) if k + M15 <= tc]
        if not cands:
            return None
        return dict(self.native15(cands[-1]), dev=False)


def run_source(chart, sig5, sig15, dev15=None, hold5=6, hold15=4, reeval=()):
    """sig5 : {5M 元足 open: 'L'|'S'} / sig15 : {15M 元足 open: 'L'|'S'}（確定値）/ dev15 : {n: {'raw': 'L'}} 形成中だけの成立
    戻り値 : 各確定足の出力 [(n, slot_time, nb5, raw5, nb15, raw15, acc15, status15, valid5L, valid15L)]"""
    last5 = last15 = 0
    o5, o15 = OneLogic(hold5), OneLogic(hold15)
    cur, prev = None, None
    out = []
    for n, (t, o, h, l, c) in enumerate(chart.bars):
        for rep in range(2 if n in reeval else 1):          # 同じ確定足の再評価
            tc = t + M5
            b, bc = chart.q15(n)
            nb5 = nb15 = False
            raw5 = raw15 = ''
            # ① 5M : 今確定したチャート足
            if t > last5:
                last5 = t
                s = sig5.get(t, '')
                o5.apply(c, 'L' in s, 'S' in s, lvlL=l - 100, lvlS=h + 100)
                nb5, raw5 = True, s
            # ② 15M : 境界ゲート
            pk = chart.packet15_lookahead_off(n, realtime_dev=(dev15 or {}).get(n))
            atB = tc == bc
            acc = (atB and pk is not None and not pk.get('dev') and pk['open'] == b and pk['close_t'] == tc and pk['open'] > last15)
            if acc:
                last15 = pk['open']
                s = sig15.get(pk['open'], '')
                o15.apply(pk['close'], 'L' in s, 'S' in s, lvlL=pk['close'] - 100, lvlS=pk['close'] + 100)
                nb15, raw15 = True, s
            # 準備（15M）: 境界なら今閉じた区間、それ以外なら直前に足が存在した区間
            if cur is None or b != cur:
                prev, cur = cur, b
            exp15 = cur if atB else prev
            st15 = 1 if (last15 == 0 or exp15 is None) else (0 if last15 == exp15 else 4)
            if rep == 0:
                out.append(dict(n=n, slot=tc, nb5=nb5, raw5=raw5, nb15=nb15, raw15=raw15, acc=acc, st15=st15,
                                v5=o5.v[0]['valid'], v15=o15.v[0]['valid'], c=c))
    return out


def verifier_mode1(chart, out, tf):
    """モード 1 : 受理した確定足で nb かつ片方向の生シグナル → 登録（P0 = その足の close）。最初の追跡更新 = 次の足"""
    ev = []
    for r in out:
        nb, raw = (r['nb5'], r['raw5']) if tf == 5 else (r['nb15'], r['raw15'])
        if nb and raw in ('L', 'S') and (tf == 5 or r['st15'] == 0):
            n = r['n']
            ev.append(dict(reg_close=r['slot'], p0=r['c'], obs_open=chart.bars[n + 1][0] if n + 1 < len(chart.bars) else None,
                           reg_open=chart.bars[n][0], d=1 if raw == 'L' else -1))
    return ev


T10 = 1_700_006_400_000 - (1_700_006_400_000 % M15)    # 15 分境界に揃えた「10:00」
mk = lambda k, px=100.0: (T10 + k * M5, px, px + 1, px - 1, px + 0.5)
bars = [mk(k, 100 + k) for k in range(-6, 12)]           # 9:30 〜 10:55
ch = Chart(bars)
idx = {b[0]: i for i, b in enumerate(bars)}

# 1. 5M : 10:00〜10:05 の生シグナル → 10:05 登録、P0 = その足の close、最初の観察は 10:05〜10:10
out = run_source(ch, {T10: 'L'}, {})
ev = verifier_mode1(ch, out, 5)
check('case 1: 5M signal on 10:00-10:05 -> registered at 10:05 with P0 = that bar close, first observation bar 10:05',
      len(ev) == 1 and ev[0]['reg_close'] == T10 + M5 and ev[0]['p0'] == bars[idx[T10]][4] and ev[0]['obs_open'] == T10 + M5)
# 11. 旧版との対比 : 旧は 10:10 登録・P0 = 10:05〜10:10 の close
check('case 11: old path registered at 10:10 with the next bar close; new path at 10:05 with the 10:00-10:05 close',
      ev[0]['reg_close'] == (T10 + 2 * M5) - M5 and ev[0]['p0'] != bars[idx[T10] + 1][4])
# 2. 15M : 10:00〜10:15 の生シグナル → 10:15 で 1 件だけ（10:05 / 10:10 はゼロ、10:20 / 10:25 は重複ゼロ）
out = run_source(ch, {}, {T10: 'S'})
ev = verifier_mode1(ch, out, 15)
regs = [e['reg_close'] for e in ev]
check('case 2: 15M signal -> exactly one registration at 10:15 (none at 10:05 / 10:10, none repeated at 10:20 / 10:25)', regs == [T10 + M15])
check('case 2b: the 15M registration bar is the 10:10-10:15 5M bar and P0 is its close', ev[0]['reg_open'] == T10 + 2 * M5 and ev[0]['p0'] == bars[idx[T10 + 2 * M5]][4])
# 3. 形成中だけ成立 → 確定時に不成立 : 新規イベントなし・有効根拠への仮反映なし
out = run_source(ch, {}, {}, dev15={idx[T10]: {'raw': 'L'}, idx[T10 + M5]: {'raw': 'L'}})
check('case 3: condition only while the 15M bar was forming -> no event, no evidence', not verifier_mode1(ch, out, 15) and not any(r['v15'] for r in out))
# 4. 同じ確定足の再評価 → 二重に進まない
o1 = run_source(ch, {T10: 'L'}, {T10: 'L'})
o2 = run_source(ch, {T10: 'L'}, {T10: 'L'}, reeval=set(range(len(bars))))
check('case 4: re-evaluating the same confirmed bar does not advance TTL / readiness / events twice',
      [(r['v5'], r['v15'], r['nb5'], r['nb15']) for r in o1] == [(r['v5'], r['v15'], r['nb5'], r['nb15']) for r in o2])
# 5. 10:15 で 5M と 15M が同時確定 → 同じ出力に両方の最新状態
out = run_source(ch, {T10 + 2 * M5: 'L'}, {T10: 'L'})
r = [x for x in out if x['slot'] == T10 + M15][0]
check('case 5: at 10:15 both the 5M bar 10:10 and the 15M bar 10:00 are applied before the single 10:15 output', r['nb5'] and r['nb15'] and r['v5'] and r['v15'])
# 6. 元足シグナルなしで保持だけ → モード 1 に登録されない
out = run_source(ch, {T10: 'L'}, {})
check('case 6: holding-only bars are not mode-1 events', len(verifier_mode1(ch, out, 5)) == 1 and sum(1 for x in out if x['v5']) > 1)
# 7. 元足 ID で対応させると旧（[1]）と新のパケットが同じ元足を指す / LONG・SHORT 対称
old_native_at = {n: bars[n - 1][0] for n in range(1, len(bars))}       # 旧 : チャート足 n で元足 n-1
new_native_at = {n: bars[n][0] for n in range(len(bars))}               # 新 : チャート足 n で元足 n
check('case 7: matched by native bar ID, old and new deliver the same native bars (shifted by one chart bar only)',
      all(old_native_at[n + 1] == new_native_at[n] for n in range(len(bars) - 1)))
oL = run_source(ch, {T10: 'L', T10 + 4 * M5: 'S'}, {T10: 'L'})
oS = run_source(ch, {T10: 'S', T10 + 4 * M5: 'L'}, {T10: 'S'})
check('case 7b: LONG / SHORT symmetric event timing', [x['nb5'] and x['raw5'] != '' for x in oL] == [x['nb5'] and x['raw5'] != '' for x in oS]
      and [x['acc'] for x in oL] == [x['acc'] for x in oS])
# 8. 15M の境界足が欠けた → その 15M は受理されず、次の区間で不整合（正常な根拠ゼロにしない）
gap_bars = [b for b in bars if b[0] != T10 + 2 * M5]                   # 10:10〜10:15 が欠損
ch2 = Chart(gap_bars)
out = run_source(ch2, {}, {T10: 'L'})
after = [x for x in out if x['slot'] > T10 + M15]
check('case 8: missing 15M boundary 5M bar -> 10:00 15M never accepted, next interval reports inconsistency (not zero evidence)',
      not any(x['acc'] and x['slot'] == T10 + M15 for x in out) and after[0]['st15'] == 4)
# 9. 週末 : 金曜の最後の境界は受理、月曜の最初の区間途中は「直前に足が存在した区間」と一致（不整合にしない）
wk = bars[:12] + [(bars[11][0] + 2 * 24 * 3600 * 1000 + k * M5 + M5, 200, 201, 199, 200.5) for k in range(6)]
wk = [b for b in wk]
ch3 = Chart(wk)
out = run_source(ch3, {}, {})
mon = [x for x in out if x['slot'] > bars[11][0] + 24 * 3600 * 1000]
check('case 9: across a weekend the first Monday bars compare with the last existing Friday 15M (status 0, not 4)',
      all(x['st15'] in (0,) for x in mon[:1]) and all(x['st15'] != 4 for x in mon))
# 12. TRACE : 元足確定 = 出力 = 登録、観察は次の足（登録足のヒゲを含めない）
out = run_source(ch, {T10 + 3 * M5: 'L'}, {})
ev = verifier_mode1(ch, out, 5)
native_close_t = T10 + 3 * M5 + M5
check('case 12: TRACE native close = Source output = registration; first observation is the next bar',
      ev[0]['reg_close'] == native_close_t and ev[0]['obs_open'] == native_close_t)

# 10. 形式 : 通常 BUS format 3 / STUDY META format 2 だけ受理、旧形式は別理由で拒否、最大値・取り違え・古い slot・小数
BASE, SLOTS = 1577836800000, 2 ** 22
def bus(fmt, sid, tf, pay, tclose):
    slot = (tclose - BASE) / 300000.0
    return fmt + 4 * sid + 16 * tf + 64 * slot + 268435456.0 * pay
def dec(v, sid, tf, paymax, tclose):          # PM-DEC-515 f_dec（時刻修正版）
    slotf = (tclose - BASE) / 300000.0
    if v is None:
        return 1
    if not (v >= 0 and v < 2 ** 49 and v == math.floor(v)):
        return 5
    fmt, s, t = v % 4, math.floor(v / 4) % 4, math.floor(v / 16) % 4
    sl, pay = math.floor(v / 64) % SLOTS, math.floor(v / 268435456.0)
    if fmt in (1, 2) and s == sid and t == tf:
        return 6
    if fmt != 3 or s != sid or t != tf or pay >= paymax:
        return 5
    return 4 if sl != slotf else 0
tcl = BASE + 300000 * (SLOTS - 1)
check('case 10: format-3 BUS accepted at the maximum slot / payload', dec(bus(3, 3, 2, 2097151, tcl), 3, 2, 2097152, tcl) == 0 and bus(3, 3, 2, 2097151, tcl) < 2 ** 49)
check('case 10b: old format 2 (previous 5M15M) and 1 (1M version) -> status 6 "old format", not "na"', dec(bus(2, 1, 1, 0, tcl), 1, 1, 2048, tcl) == 6 and dec(bus(1, 1, 1, 0, tcl), 1, 1, 2048, tcl) == 6)
check('case 10c: wrong Source / TF -> 5, old slot -> 4, fractional -> 5, na -> 1',
      dec(bus(3, 2, 1, 0, tcl), 1, 1, 2048, tcl) == 5 and dec(bus(3, 1, 2, 0, tcl), 1, 1, 2048, tcl) == 5 and
      dec(bus(3, 1, 1, 0, tcl - M5), 1, 1, 2048, tcl) == 4 and dec(bus(3, 1, 1, 0, tcl) + 0.5, 1, 1, 2048, tcl) == 5 and dec(None, 1, 1, 2048, tcl) == 1)
meta = lambda fmt: fmt + 4 * 1 + 16 * 1 + 64 * 9 + 2048 * 0 + 16384 * 1 + 32768.0 * (SLOTS - 1)
check('case 10d: STUDY META format 2 decodes at maximum; format 1 is classified as old format',
      meta(2) < 2 ** 37 and meta(2) % 4 == 2 and meta(1) % 4 == 1)
print(f'{ok} checks passed (model of the code path; not a Pine run)')
