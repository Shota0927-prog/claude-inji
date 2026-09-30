#!/usr/bin/env python3
# W09 B07-R3B1 static conformance (outside Production): the scratch-format contract constants of W08Touch (EI_*, EF_*, PI_*,
# PF_*) must equal the producer layout of W09State (/22: PLAN_*, EP_* constants, the episodePlan ei / ef rows, the
# episodeApply mark write) and the Main TouchStart markAppend wiring. Any mismatch -> FAIL (exit 1).
# Usage: python3 tests/r3b1_scratch_contract_check.py [W09State] [W08Touch] [Main]
import re, sys, os
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W9 = sys.argv[1] if len(sys.argv) > 1 else os.path.join(R, 'ZoneEngineV2_W09State_Worker.pine')
W8 = sys.argv[2] if len(sys.argv) > 2 else os.path.join(R, 'ZoneEngineV2_W08Runtime_Worker.pine')  # TC-A: W08Touch body lives in W08Runtime /20
MN = sys.argv[3] if len(sys.argv) > 3 else os.path.join(R, 'ZoneEngineV2_Rebuild.pine')
def consts(path):
    return {m.group(1): int(m.group(2)) for m in re.finditer(r'^const int ([A-Z0-9_]+)\s*=\s*(-?\d+)', open(path).read(), re.M)}
def body(src, name):
    i = src.index('\nexport %s(' % name) + 1; j = src.find('\nexport ', i + 1)
    return src[i:j if j > 0 else len(src)]
def args(call):
    out, d, cur = [], 0, ''
    for ch in call:
        if ch == '(': d += 1
        if ch == ')': d -= 1
        if d == 0 and ch == ',': out.append(cur.strip()); cur = ''
        else: cur += ch
    out.append(cur.strip()); return out
w9s, w8s, mns = open(W9).read(), open(W8).read(), open(MN).read()
A, T = consts(W9), consts(W8)
F = []
def eq(label, a, b):
    if a != b: F.append('%s: W08Touch %r != W09State / Main %r' % (label, a, b))
ep = body(w9s, 'episodePlan'); ap = body(w9s, 'episodeApply')
eiRow = args(re.search(r'array\.concat\(ei, array\.from\((.*)\)\)\s*$', ep, re.M).group(1))
efRow = args(re.search(r'array\.concat\(ef, array\.from\((.*)\)\)\s*$', ep, re.M).group(1))
# ei
eq('EI_STRIDE', T['EI_STRIDE'], A['EP_INT_STRIDE']); eq('EI_STRIDE (row width)', T['EI_STRIDE'], len(eiRow))
eq('EI_SIDE_SLOT', eiRow[T['EI_SIDE_SLOT']], 's')
for k, a, v in (('EI_TOUCH_NO', 'EP_I_TOUCH_NO', 'no'), ('EI_CORE_ID', 'EP_I_CORE_ID', 'id'), ('EI_GENERATION_ID', 'EP_I_GENERATION_ID', 'gn'),
                ('EI_PLAN_ROW', 'EP_I_ROW', 'row'), ('EI_MARK_ROW', 'EP_I_MARK', 'mk')):
    eq(k, T[k], A[a]); eq(k + ' (row value)', eiRow[T[k]], v)
eq('EI_FLAGS', T['EI_FLAGS'], A['EP_I_FLAGS']); eq('EI_OVERRIDE', T['EI_OVERRIDE'], A['EP_I_OVERRIDE'])
eq('EI_FLAG_MARK_WEAK (plan flag term)', '(mw or hit ? %d : 0)' % T['EI_FLAG_MARK_WEAK'] in eiRow[T['EI_FLAGS']], True)
eq('EI_FLAG_MARK_WEAK (apply mark write)', 'array.set(tv.ringWeakByDepthFlags, mk, fl %% %d >= %d)' % (2 * T['EI_FLAG_MARK_WEAK'], T['EI_FLAG_MARK_WEAK']) in ap, True)
# ef
eq('EF_STRIDE', T['EF_STRIDE'], A['EP_FLOAT_STRIDE']); eq('EF_STRIDE (row width)', T['EF_STRIDE'], len(efRow))
eq('EF_RANGE_BOTTOM (row value)', efRow[T['EF_RANGE_BOTTOM']], 'b'); eq('EF_RANGE_TOP (row value)', efRow[T['EF_RANGE_TOP']], 't')
eq('EF_EPISODE_MAX', T['EF_EPISODE_MAX'], A['EP_F_EPISODE_MAX']); eq('EF_EPISODE_MAX (row value)', efRow[T['EF_EPISODE_MAX']], 'mx')
eq('EF_EPISODE_MAX (apply mark write)', 'array.set(tv.ringMaxDepthPcts, mk, array.get(ef, f + EP_F_EPISODE_MAX))' in ap, True)
# TouchStart plan
eq('PI_STRIDE', T['PI_STRIDE'], A['PLAN_INT_STRIDE']); eq('PF_STRIDE', T['PF_STRIDE'], A['PLAN_FLOAT_STRIDE'])
for k, a in (('PI_CORE_SLOT', 'PLAN_I_CORE_SLOT'), ('PI_CORE_ID', 'PLAN_I_CORE_ID'), ('PI_GENERATION_ID', 'PLAN_I_GENERATION_ID'), ('PI_SIDE', 'PLAN_I_SIDE'), ('PI_TOUCH_NO', 'PLAN_I_TOUCH_NO'),
             ('PI_BASE_SEQ', 'PLAN_I_START_SEQ'), ('PI_TIME', 'PLAN_I_START_TIME'), ('PI_IS_NORMAL', 'PLAN_I_MARK_IS_NORMAL'),
             ('PF_CONTACT_BOTTOM', 'PLAN_F_CONTACT_BOTTOM'), ('PF_CONTACT_TOP', 'PLAN_F_CONTACT_TOP'), ('PF_CLOSE', 'PLAN_F_CLOSE_AT_TOUCH')):
    eq(k, T[k], A[a])
# Main TouchStart markAppend wiring (the persistent mark the projection must equal)
m = re.search(r'W08(?:Touch|Runtime)\.markAppend\((.*)\)\s*$', mns, re.M); ma = args(m.group(1))
eq('Main plan int stride', re.search(r'int r = %d \* [ix]\b' % T['PI_STRIDE'], mns) is not None, True); eq('Main plan float stride', re.search(r'int f = %d \* [ix]\b' % T['PF_STRIDE'], mns) is not None, True)  # B09: the plan row index is x (D1 order)
sig = re.search(r'^export markAppend\((.*)\) =>', w8s, re.M).group(1)
pn = [p.split('=')[0].strip().split()[-1] for p in re.split(r',\s*(?![^<]*>)', sig)]
want = {'coreSlot': 'array.get(ti, r + %d)' % T['PI_CORE_SLOT'], 'baseSeq': 'array.get(ti, r + %d)' % T['PI_BASE_SEQ'], 'touchTime': 'array.get(ti, r + %d)' % T['PI_TIME'],
        'side': 'array.get(ti, r + %d)' % T['PI_SIDE'], 'contactBottom': 'array.get(tf, f + %d)' % T['PF_CONTACT_BOTTOM'], 'contactTop': 'array.get(tf, f + %d)' % T['PF_CONTACT_TOP'],
        'closeAtTouch': 'array.get(tf, f + %d)' % T['PF_CLOSE'], 'generationId': 'array.get(ti, r + %d)' % T['PI_GENERATION_ID'],
        'isNormalTouch': 'array.get(ti, r + %d) == 1' % T['PI_IS_NORMAL'], 'touchNo': 'array.get(ti, r + %d)' % T['PI_TOUCH_NO'], 'weakByDepth': 'false', 'maxDepthPct': '0.0'}
for k, v in want.items(): eq('Main markAppend ' + k, ma[pn.index(k)], v)
print('R3-B1 scratch contract: %s (%d checks failed)' % ('PASS' if not F else 'FAIL', len(F)))
for x in F: print('  ' + x)
sys.exit(1 if F else 0)
