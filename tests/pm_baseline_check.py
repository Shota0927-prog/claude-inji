"""比較元コミット（BASELINE）と現行 5分・15分版の一致確認。Pine 上の実行確認ではない。
  静的 : 現行 Source / Decision の差分が「通常 BUS・判定の経路に触れない追加」と、
         既定値で元と同じ値になる式変更（採用設定・系統 Weight）に限られることを確認する。
  モデル : 採用 = 全て、保持 = 元、Weight = 全て 1 のとき、通常 BUS の payload・系統点・B 判定コード・基準が
          比較元と一致することを確認する（tests/pm_baseline_model.py）。
使い方 : python3 -I tests/pm_baseline_check.py
"""
import subprocess
import difflib
import sys

BASELINE = '0e56963'
FILES = ['PointMasterSourceA5M15M.pine', 'PointMasterSourceB5M15M.pine', 'PointMasterSourceC5M15M.pine', 'PointMasterDecision5M15M.pine']
UNTOUCHED = ['PointMasterFvgAbsRebound.pine', 'PointMasterVerifier.pine', 'PointMasterVerifierV2.pine', 'PointMasterModeAV2.pine',
             'PointMasterSourceAV2.pine', 'PointMasterSourceBV2.pine', 'PointMasterSourceCV2.pine', 'PointMasterDecisionV2.pine',
             'PointMasterFvgAbsReboundV2.pine']

# 既定値で元と同じ値になるよう置き換えた行（採用設定・系統 Weight）。ここに無い行の削除・変更は許さない。
ALLOWED_CHANGED = [
    # Stage 3（採用設定）
    'bool vL = array.get(V2_VALID, j)     and array.get(V2_PRICE, j)',
    'bool vS = array.get(V2_VALID, j + 1) and array.get(V2_PRICE, j + 1)',
    'iL := math.max(iL, math.max(vL ? 1.0 : 0.0, array.get(V2_PRE, j)))',
    'iS := math.max(iS, math.max(vS ? 1.0 : 0.0, array.get(V2_PRE, j + 1)))',
    "u := u or (array.get(V2_VALID, j) and not array.get(V2_PRICE, j)) or (array.get(V2_VALID, j + 1) and not array.get(V2_PRICE, j + 1))",
    'array.set(V2_NEG,   ti * 2 + d, array.get(V2_NEG, ti * 2 + d) + (negd ? 1 : 0))',
    # Stage 5（系統 Weight）
    'array.set(bCurT, x, cP + cM + cG + cF + cS + cK)',
    'array.set(bIntT, x, iP + iM + iG + iF + iS + iK)',
    'array.set(bFamT, x, (iP > 0 ? 1 : 0) + (iM > 0 ? 1 : 0) + (iG > 0 ? 1 : 0) + (iF > 0 ? 1 : 0) + (iS > 0 ? 1 : 0) + (iK > 0 ? 1 : 0))',
    'array.set(negs, x, f_bit(a, d) + f_bit(b, d) + f_bit(c, d) > 0 ? 1 : 0)',
    'bool  negHit  = array.get(V2_NEG, 0 * 2 + di) > 0 or array.get(V2_NEG, 1 * 2 + di) > 0',
    'string s4     = negHit ? "根拠の価格否定" : ""',
    'r := f_v2Row(r, "5M 確認済み点（自 vs 逆）", colTxt,',
    'r := f_v2Row(r, "15M 確認済み点（自 vs 逆）", colTxt,',
    'r := f_v2Row(r, "5M 逆方向 統合点（系統数）", colTxt,',
    # Stage 5 表示のみ（Weight 後の小数表示・注記。判定には使わない）
    'str.tostring(array.get(V2B_DIAG, 0), "0") + " vs " + str.tostring(array.get(V2B_DIAG, 1), "0"), colTxt,',
    'str.tostring(array.get(V2B_DIAG, 6), "0") + " vs " + str.tostring(array.get(V2B_DIAG, 7), "0"), colTxt)',
    'str.tostring(array.get(V2B_DIAG, 2), "0") + " vs " + str.tostring(array.get(V2B_DIAG, 3), "0"), colTxt,',
    'str.tostring(array.get(V2B_DIAG, 8), "0") + " vs " + str.tostring(array.get(V2B_DIAG, 9), "0"), colTxt)',
    'f_v2Cell(0, r + 1, "※点数 = 系統×TF×方向で最大1点（Weight不使用）。基準は確定ピボット基準", color.gray)',
    # 時刻照合（Source A のみ）: UDT の末尾へフィールドを追加しただけ（既存フィールドの順序・値・request 本数・タプル要素数は同じ）
    '[lmA, smA, xC, xH, xL, xEa, xEb, xEc, xEd, x01L, x01S, x02L, x02S, x03L, x03S, x04L, x04S]',
    'array.from(q.f0, q.f1, q.f2, q.f3, q.f4, q.f5, q.f6, q.f7, q.f8, q.f9, q.f10, q.f11, q.f12, q.f13, q.f14)',
    '[lmRaw, smRaw, xC, xH, xL, xEa, xEb, xEc, xEd, x01L, x01S, x02L, x02S, x03L, x03S, x04L, x04S] = f_signalMasksA()',
    '[lm[1], sm[1], tt[1], SRCAX.new(xC[1], xH[1], xL[1], xEa[1], xEb[1], xEc[1], xEd[1], x01L[1], x01S[1], x02L[1], x02S[1], x03L[1], x03S[1], x04L[1], x04S[1])]   // ★[1] は必須（外すと未来参照）',
]

ok = 0
def check(name, cond):
    global ok
    if not cond:
        print('NG ', name)
        sys.exit(1)
    ok += 1
    print('OK ', name)


def git_show(rev, path):
    return subprocess.run(['git', 'show', f'{rev}:{path}'], capture_output=True, text=True, check=True).stdout


for f in UNTOUCHED:
    check(f'{f} unchanged since baseline', git_show(BASELINE, f) == open(f, encoding='utf-8').read() if f != 'PointMasterFvgAbsRebound.pine' and f != 'PointMasterVerifier.pine' else git_show('b6f4abe', f) == open(f, encoding='utf-8').read())

for f in FILES:
    old = git_show(BASELINE, f).split('\n')
    new = open(f, encoding='utf-8').read().split('\n')
    removed = [l[2:].strip() for l in difflib.ndiff(old, new) if l.startswith('- ')]
    bad = [l for l in removed if l and not l.startswith('//') and l not in ALLOWED_CHANGED]
    check(f'{f}: no baseline code line removed except documented default-equivalent replacements ({len(removed)} removed lines checked)', not bad)
    if bad:
        print('\n'.join(bad))
    # 既存 plot の名前と順序が保たれている（追加分は末尾）
    import re
    po = re.findall(r'^\s*plot\([^"]*"([^"]+)"', '\n'.join(old), re.M)
    pn = re.findall(r'^\s*plot\([^"]*"([^"]+)"', '\n'.join(new), re.M)
    check(f'{f}: existing plots keep names and order (new plots appended)', pn[:len(po)] == po)
    io = re.findall(r'input\.\w+\(([^,]+),\s*"([^"]+)"', '\n'.join(old))
    inn = re.findall(r'input\.\w+\(([^,]+),\s*"([^"]+)"', '\n'.join(new))
    check(f'{f}: existing inputs keep titles and defaults', all(x in inn for x in io))
    check(f'{f}: title / shorttitle unchanged', re.findall(r'title\s*=\s*"[^"]+"', '\n'.join(old)) == re.findall(r'title\s*=\s*"[^"]+"', '\n'.join(new)))

print(f'{ok} static checks passed (static only; not a Pine run)')
