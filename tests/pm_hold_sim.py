"""保持本数の比較（既存の保持本数 input を 1 ロジック × 1 TF ずつ変える）の Python モデル確認。Pine 上の実行確認ではない。"""
import io, contextlib, sys
sys.path.insert(0, 'tests')
with contextlib.redirect_stdout(io.StringIO()):
    from pm_study_sim import OneLogic

ok = 0
def check(name, cond):
    global ok
    assert cond, name
    ok += 1
    print('OK ', name)

def valid_bars(hold, closes, lvl=90.0):
    o = OneLogic(hold)
    o.apply(100, True, False, lvlL=lvl)
    n = 1
    for c in closes:
        o.apply(c, False, False)
        if not o.v[0]['valid']:
            break
        n += 1
    return n, o

for h in (3, 6, 9):
    n, _ = valid_bars(h, [100] * 20)
    check(f'hold {h}: valid for exactly {h} own-TF bars (signal bar included), then expiry', n == h)
n, o = valid_bars(9, [100, 100, 89, 100, 100])
check('price negation still ends the evidence before a longer hold runs out', n == 3 and o.v[0]['negf'])
a, b = OneLogic(3), OneLogic(6)          # 別ロジック（保持 6 のまま）は影響を受けない
for o in (a, b):
    o.apply(100, True, False, lvlL=90.0)
for _ in range(4):
    a.apply(100, False, False); b.apply(100, False, False)
check('changing one logic hold does not change another logic', (not a.v[0]['valid']) and b.v[0]['valid'])
print(f'{ok} checks passed (model only; not a Pine run)')
