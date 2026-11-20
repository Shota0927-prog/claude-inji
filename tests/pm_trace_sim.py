"""時刻照合（Source A の TRACE 出力 → Logic Verifier の照合）の固定ケース。Pine 上の実行確認ではない。
現行コードの経路を写したもの:
  Source A : request.security(tfStr2="5", f_htfPacket() の [1], lookahead_on)  → チャート 5 分足 n で「直前に確定した 5M 足 n-1」が届く
             新しい元足（tt5 > LAST_TFTIME[0]）なら f_v2ApplyTf(0) で処理、チャート足 n の確定時に STUDY / TRACE を出力（slot = n の time_close）
  Verifier : 同じ足 n の確定時に STUDY を読み（[1] なし）、f_vfPush で P0 = 足 n の close・ET0 = 足 n の time を登録。
             価格追跡の最初の更新は ET0 + 5 分に始まる足 n+1（判定足 n の高安は入らない）。
"""
ok = 0
def check(name, cond):
    global ok
    assert cond, name
    ok += 1
    print('OK ', name)

M5 = 300000
def run(bars, signals):
    """bars : [(open_time, o, h, l, c)]（存在する 5 分足のみ。ギャップ可）/ signals : {元足 index: +1 / -1}
    戻り値 : 登録イベント [(id, 元足開始, 元足確定, 元足close, 出力確定, 登録確定, 登録開始, P0, 観察開始, 観察確定)]"""
    last_native = 0
    events, pending = [], []
    for n, (t, o, h, l, c) in enumerate(bars):
        tclose = t + M5
        # ① Verifier の追跡更新（既存の登録より先）: 次の足で最初の更新
        for e in pending:
            if e['obs'] is None and t == e['reg_open'] + M5:
                e['obs'] = (t, tclose, h, l)
        # ② Source : [1] + lookahead_on で届く元足 = 直前に存在した 5M 足
        if n == 0:
            continue
        nt, _, nh, nl, nc = bars[n - 1]
        nb = nt > last_native
        if nb:
            last_native = nt
        raw = signals.get(n - 1, 0) if nb else 0
        # ③ Verifier : 同じ足の確定時に登録（モード 1 は新しい元足 nb かつ生シグナル）
        if raw:
            e = dict(id=len(events) + 1, d=raw, n_open=nt, n_close=nt + M5, n_close_px=nc, src_out=tclose,
                     reg_close=tclose, reg_open=t, p0=c, obs=None)
            events.append(e)
            pending.append(e)
    return events

t0 = 1_700_000_000_000 - (1_700_000_000_000 % M5)
bars = [(t0 + i * M5, 100 + i, 101 + i, 99 + i, 100.5 + i) for i in range(12)]
ev = run(bars, {2: 1})
e = ev[0]
check('fixed case: native 10:00-10:05 -> Source output confirmed 10:10 (native close + 5 min)', e['src_out'] - e['n_close'] == 5 * 60000)
check('fixed case: Verifier registers on the same bar as the output (output -> registration 0 min)', e['reg_close'] - e['src_out'] == 0)
check('fixed case: P0 = close of the registration bar, not the native close (price shift = d x (P0 - native close))', e['p0'] == bars[3][4] and e['d'] * (e['p0'] - e['n_close_px']) == 1.0)
check('fixed case: first tracking update is the bar after registration (registration-bar wick excluded)', e['obs'][0] == e['reg_open'] + M5)
ev = run(bars, {2: 1, 5: 1, 6: -1})
check('separate native bars with same-direction signals are separate events', [x['n_open'] for x in ev] == [bars[2][0], bars[5][0], bars[6][0]])
check('LONG / SHORT direction carried to the event', [x['d'] for x in ev] == [1, 1, -1])
# 同じ元足を繰り返し受信（データ欠けで新しい元足が来ない足）は登録しない
dup = bars[:4] + [(bars[3][0], *bars[3][1:])] + bars[5:]
check('same native bar received again (no new 5M bar) -> not registered twice', len(run(dup, {2: 1})) == 1)
# セッション跨ぎ：元足は存在した最後の足、遅延は実際の時刻差（5 分に丸めない）
gap = bars[:6] + [(bars[5][0] + 2 * 24 * 3600 * 1000 + i * M5, 200, 201, 199, 200.5) for i in range(1, 5)]
ev = run(gap, {5: -1})
exp = (gap[6][0] + M5) - (bars[5][0] + M5)      # 出力確定（ギャップ後の最初の足の確定）− 元足確定
check('across a weekend: native = last existing bar, delay = real time gap (not rounded to 5 min)', ev[0]['n_open'] == bars[5][0] and ev[0]['src_out'] - ev[0]['n_close'] == exp and exp > 24 * 3600 * 1000)
print(f'{ok} checks passed (model of the code path; not a Pine run)')
