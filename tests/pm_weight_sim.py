"""PM-DEC-515 の系統 Weight の Python モデル確認。Pine 上の実行確認ではない。"""
import io, contextlib, math, random, sys
sys.path.insert(0, 'tests')
with contextlib.redirect_stdout(io.StringIO()):
    import pmv2_split_sim as SP
    from pm515_sim import ModeB515

ok = 0
def check(name, cond):
    global ok
    assert cond, name
    ok += 1
    print('OK ', name)

def bit(p, b): return math.floor(p / 2 ** b) % 2

def merge_w(pa, pb, pc, w):
    """PM-DEC-515 の f_merge（2 枠 + 系統 Weight）。w = (P, M, G, F, S, K)"""
    wP, wM, wG, wF, wS, wK = w
    onA, onB, onC = wP > 0 or wM > 0, wG > 0, wP > 0 or wF > 0 or wS > 0 or wK > 0
    mixA = (wP > 0) != (wM > 0)
    mixC = not ((wP > 0) == (wF > 0) == (wS > 0) == (wK > 0))
    cur, intg, fam, negs = [], [], [], []
    for x in range(4):
        ti, d = x // 2, x % 2
        o = d * 2
        a, b, c = pa[ti], pb[ti], pc[ti]
        cP = max(bit(a, 3 + o), bit(c, 3 + o)); iP = max(bit(a, 4 + o), bit(c, 4 + o))
        cM, iM = bit(a, 7 + o), bit(a, 8 + o)
        cG, iG = bit(b, 3 + o), bit(b, 4 + o)
        cF, iF = bit(c, 7 + o), bit(c, 8 + o)
        cS = bit(c, 11 + d * 3); iS = (math.floor(c / 2 ** (12 + d * 3)) % 4) / 3.0
        cK, iK = bit(c, 17 + o), bit(c, 18 + o)
        cur.append(wP * cP + wM * cM + wG * cG + wF * cF + wS * cS + wK * cK)
        intg.append(wP * iP + wM * iM + wG * iG + wF * iF + wS * iS + wK * iK)
        fam.append(sum(1 for ww, v in ((wP, iP), (wM, iM), (wG, iG), (wF, iF), (wS, iS), (wK, iK)) if ww > 0 and v > 0))
        ngA, ngB, ngC = onA and bit(a, d) > 0, onB and bit(b, d) > 0, onC and bit(c, d) > 0
        negs.append(2 if (ngA and mixA) or (ngC and mixC) else 1 if (ngA or ngB or ngC) else 0)
    return cur, intg, fam, negs

rng = random.Random(8)
t0 = SP.BASE + 300000 * 800000
same = True
for i in range(3000):
    st = SP.rand_state(rng)
    negs0 = {(s, ti, d): rng.random() < 0.1 for s in 'ABC' for ti in range(3) for d in (0, 1)}
    pa = [SP.payload(st, 'A', t, negs0) for t in (1, 2)]
    pb = [SP.payload(st, 'B', t, negs0) for t in (1, 2)]
    pc = [SP.payload(st, 'C', t, negs0) for t in (1, 2)]
    oc, oi, of_, on, _ = SP.merge(pa + [0], pb + [0], pc + [0])     # 比較元（Weight なし）
    nc, ni, nf, nn = merge_w(pa, pb, pc, (1.0,) * 6)
    same = same and oc[:4] == nc and oi[:4] == ni and of_[:4] == nf and on[:4] == nn
check('all Weights 1 -> identical points / families / neg flags as before (3000 random states, exact floats)', same)

st = {(g, ti, d): (False, True, 0.0) for g in range(25) for ti in range(3) for d in (0, 1)}
st[(0, 1, 0)] = (True, True, 0.0); st[(18, 1, 0)] = (True, True, 0.0)      # 価格帯 A + C
st[(4, 1, 0)] = (True, True, 0.0)                                            # MA
st[(23, 1, 0)] = (False, True, 2 / 3.0)                                      # SAT PRE 2/3
P = lambda s: [SP.payload(st, s, t, {}) for t in (1, 2)]
c, i, f, _ = merge_w(P('A'), P('B'), P('C'), (1.5, 1, 1, 1, 1, 1))
check('price band A/C merged by max BEFORE weighting (1.5, not 3)', c[0] == 1.5 + 1.0 and f[0] == 3)
c, i, f, _ = merge_w(P('A'), P('B'), P('C'), (1, 0, 1, 1, 1, 1))
check('Weight 0 family removed from points and from the family count', c[0] == 1.0 and f[0] == 2)
c, i, f, _ = merge_w(P('A'), P('B'), P('C'), (1, 1, 1, 1, 0.5, 1))
check('SAT 2/3 kept fractional then weighted (2/3 x 0.5)', abs(i[0] - (1 + 1 + 1 / 3.0)) < 1e-12 and f[0] == 3)
c, i, f, _ = merge_w(P('A'), P('B'), P('C'), (1, 1, 1, 1, 3, 1))
check('weighted totals can exceed per-family 1 (displayed as weighted)', i[0] > 3)
negd = {('B', 1, 0): True}
n = merge_w([SP.payload(st, 'A', t, {}) for t in (1, 2)], [SP.payload(st, 'B', t, negd) for t in (1, 2)], [SP.payload(st, 'C', t, {}) for t in (1, 2)], (1, 1, 0, 1, 1, 1))[3]
check('negation from a Source whose only family has Weight 0 is not shown as a reason', n[0] == 0)
negd = {('A', 1, 0): True}
n = merge_w([SP.payload(st, 'A', t, negd) for t in (1, 2)], P('B'), P('C'), (1, 0, 1, 1, 1, 1))[3]
check('negation from a Source mixing Weight 0 and > 0 families is flagged as "possibly Weight 0"', n[0] == 2)

# B 判定（Weight 1 では変更前と同じ）: ModeB515 にそのまま入れて同じコード
rng = random.Random(12)
b0, b1 = ModeB515(), ModeB515()
same = True
for t in range(1, 2000):
    st = SP.rand_state(rng)
    pa, pb, pc = ([SP.payload(st, s, ti, {}) for ti in (1, 2)] for s in 'ABC')
    oc, oi, of_, _, _ = SP.merge(pa + [0], pb + [0], pc + [0])
    nc, ni, nf, _ = merge_w(pa, pb, pc, (1.0,) * 6)
    to = lambda v: {(x // 2, x % 2): v[x] for x in range(4)}
    cl = round(2000 + 20 * math.sin(t / 25) + rng.uniform(-3, 3), 2)
    npl = round(cl - rng.uniform(0.5, 6), 2) if rng.random() < 0.15 else None
    r0 = b0.bar(t, cl, to(oc), to(oi), to(of_), newPL=npl)
    r1 = b1.bar(t, cl, to(nc), to(ni), to(nf), newPL=npl)
    same = same and r0 == r1 and [s['basis'] for s in b0.st] == [s['basis'] for s in b1.st]
check('all Weights 1 -> identical B codes and basis (2000 bars)', same)
print(f'{ok} checks passed (model only; not a Pine run)')
