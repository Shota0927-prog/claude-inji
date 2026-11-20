"""採用設定（Source の V2_ADOPT）の Python モデル確認。Pine 上の実行確認ではない。
  - 全て採用 = 変更前（比較元 0e56963 の payload）と完全一致
  - 採用 OFF は確認済み点・統合点（PRE 含む）・寄与系統数・価格否定フラグ・価格基準なしから一貫して外れる
  - 採用ゼロの Source も準備できれば有効な根拠ゼロ BUS（na で止めない）
  - 価格帯 A / C の統合は最大値のまま
"""
import io
import contextlib
import math
import random
import sys

sys.path.insert(0, 'tests')
with contextlib.redirect_stdout(io.StringIO()):
    import pmv2_split_sim as SP

ok = 0
def check(name, cond):
    global ok
    assert cond, name
    ok += 1
    print('OK ', name)


def fam_pts_ad(st, src, ti, l0, l1, adopt):
    cL = cS = False; iL = iS = 0.0
    for g, (s, li) in SP.SRC_OF.items():
        if s != src or not (l0 <= li <= l1):
            continue
        ad = adopt.get((g, ti), True)
        vL = ad and st[(g, ti, 0)][0] and st[(g, ti, 0)][1]
        vS = ad and st[(g, ti, 1)][0] and st[(g, ti, 1)][1]
        cL = cL or vL; cS = cS or vS
        iL = max(iL, max(1.0 if vL else 0.0, st[(g, ti, 0)][2] if ad else 0.0))
        iS = max(iS, max(1.0 if vS else 0.0, st[(g, ti, 1)][2] if ad else 0.0))
    return int(cL), int(round(iL * 3)), int(cS), int(round(iS * 3))


def payload_ad(st, src, ti, negd, adopt):
    """negd[(g, ti, d)] = その TF 足で価格否定が起きた（採用中のものだけ V2_NEG に入る）"""
    f1 = lambda l0, l1, off: (lambda c: (c[0] + 2 * (1 if c[1] >= 3 else 0) + 4 * c[2] + 8 * (1 if c[3] >= 3 else 0)) * 2 ** off)(fam_pts_ad(st, src, ti, l0, l1, adopt))
    gs = [g for g, (s, _) in SP.SRC_OF.items() if s == src]
    unp = any(adopt.get((g, ti), True) and st[(g, ti, d)][0] and not st[(g, ti, d)][1] for g in gs for d in (0, 1))
    nL = any(negd.get((g, ti, 0)) and adopt.get((g, ti), True) for g in gs)
    nS = any(negd.get((g, ti, 1)) and adopt.get((g, ti), True) for g in gs)
    base = (1 if nL else 0) + (2 if nS else 0) + (4 if unp else 0)
    if src == 'A':
        return base + f1(0, 3, 3) + f1(4, 11, 7)
    if src == 'B':
        return base + f1(0, 5, 3)
    c = fam_pts_ad(st, 'C', ti, 5, 5, adopt)
    return base + f1(0, 1, 3) + f1(2, 4, 7) + (c[0] + 2 * c[1] + 8 * c[2] + 16 * c[3]) * 2 ** 11 + f1(6, 6, 17)


rng = random.Random(21)
same = True
for _ in range(3000):
    st = SP.rand_state(rng)
    negd = {(g, ti, d): rng.random() < 0.05 for g in range(25) for ti in range(3) for d in (0, 1)}
    # 比較元の payload は Source 単位の価格否定フラグ（採用の概念なし）
    negs = {(s, ti, d): any(negd[(g, ti, d)] for g, (ss, _) in SP.SRC_OF.items() if ss == s) for s in 'ABC' for ti in range(3) for d in (0, 1)}
    for s in 'ABC':
        for ti in (1, 2):
            same = same and payload_ad(st, s, ti, negd, {}) == SP.payload(st, s, ti, negs)
check('adopt all == baseline payload (3000 random states, every Source, 5M / 15M)', same)

# 採用 OFF の一貫性
st = {(g, ti, d): (False, True, 0.0) for g in range(25) for ti in range(3) for d in (0, 1)}
st[(14, 1, 0)] = (True, True, 0.0)        # Logic15 H&S LONG 5M CURRENT
st[(15, 1, 0)] = (False, True, 1.0)       # Logic16 DT/DB LONG 5M PRE
st[(16, 1, 0)] = (True, False, 0.0)       # Logic17 Wedge 価格基準なし
negd = {(17, 1, 0): True}                 # Logic18 の価格否定
off = {(14, 1): False, (15, 1): False, (16, 1): False, (17, 1): False}
p_on = payload_ad(st, 'B', 1, negd, {})
p_off = payload_ad(st, 'B', 1, negd, off)
check('adopted: cur + int + neg + unpriced bits present', p_on == 1 + 4 + 8 + 16)
check('adoption OFF removes CURRENT, PRE-carried int, neg flag and unpriced flag', p_off == 0)
p_part = payload_ad(st, 'B', 1, negd, {(14, 1): False})
check('turning off only Logic15 keeps Logic16 PRE in the integrated point', p_part == 1 + 4 + 16)

# 採用ゼロの Source : 準備できれば有効な根拠ゼロ BUS
all_off = {(g, ti): False for g in range(25) for ti in range(3)}
t0 = SP.BASE + 300000 * 700000
v = SP.bus(2, 1, payload_ad(st, 'B', 1, negd, all_off), t0)
check('Source with nothing adopted still emits a valid zero-evidence BUS', v is not None and SP.dec(v, 2, 1, 128, t0) == (0, 0))

# 価格帯 A / C は採用後も最大値統合
st = {(g, ti, d): (False, True, 0.0) for g in range(25) for ti in range(3) for d in (0, 1)}
st[(0, 1, 0)] = (True, True, 0.0)
st[(18, 1, 0)] = (True, True, 0.0)
pa = [0, payload_ad(st, 'A', 1, {}, {}), 0]
pc = [0, payload_ad(st, 'C', 1, {}, {}), 0]
c, i, f, _, _ = SP.merge(pa, [0, 0, 0], pc)
check('price band A + C both adopted -> 1 point / 1 family', c[2] == 1.0 and f[2] == 1)
pa = [0, payload_ad(st, 'A', 1, {}, {(0, 1): False}), 0]
c, i, f, _, _ = SP.merge(pa, [0, 0, 0], pc)
check('price band with A side OFF -> C alone still 1 point', c[2] == 1.0 and f[2] == 1)
print(f'{ok} checks passed (model only; not a Pine run)')
