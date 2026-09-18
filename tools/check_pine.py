#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pine v6 static checks, including FUNCTION-SCOPE undefined-variable detection.

The undefined-variable check is the one that matters: a previous bulk edit left
`idx` referenced inside f_catPricesMedianSc() although that function has no such
parameter and no local of that name. The old checker only looked for undefined
FUNCTIONS, so it passed. This walks each top-level function body and collects
every name that is in scope (parameters, locals declared with a type, tuple
declarations, loop variables, assignments) before reporting reads of anything
else that is not a file-level global, a UDT field access or a known built-in.

Usage: python3 tools/check_pine.py <file.pine> [...]
Exit code is non-zero when any check fails.
"""
import re, sys

BUILTIN = set("""
open high low close time time_close volume bar_index hl2 hlc3 ohlc4 hlcc4
na nz math array map matrix str color line box label table plot plotshape plotchar
input request ta timeframe syminfo strategy alert barstate session ticker
dayofweek dayofmonth weekofyear month year hour minute second timestamp
last_bar_index last_bar_time first_bar_time timenow chart currency
order display size shape location extend xloc yloc scale format position text
barmerge adjustment settlement_as_close backadjustment fixnan
bool int float string true false if else for while switch var varip type
export import library indicator method and or not to by in continue break
""".split())

TYPE = r'(?:bool|int|float|string|color|line|label|box|table|array<[^>]*>|map<[^>]*>|matrix<[^>]*>|[A-Z]\w*(?:\.[A-Z]\w*)?)'

def check(path):
    src = open(path, encoding='utf-8').read()
    lines = src.split('\n')
    problems = []

    # ---- file-level globals -------------------------------------------------
    globals_ = set()
    for ln in lines:
        code = ln.split('//')[0]
        if not code.strip() or code.startswith((' ', '\t')):
            continue
        m = re.match(r'^(?:var |varip )?' + TYPE + r'\s+([A-Za-z_]\w*)\s*(?:=|:=)', code)
        if m: globals_.add(m.group(1))
        m = re.match(r'^([A-Za-z_]\w*)\s*=(?!=)', code)
        if m: globals_.add(m.group(1))
        for t in re.findall(r'^\[([^\]]*)\]\s*=', code):
            for x in t.split(','): globals_.add(x.strip())
        m = re.match(r'^(?:export\s+)?([A-Za-z_]\w*)\s*\(', code)
        if m: globals_.add(m.group(1))
        m = re.match(r'^(?:export\s+)?type\s+([A-Za-z_]\w*)', code)
        if m: globals_.add(m.group(1))
        m = re.match(r'^import\s+\S+\s+as\s+([A-Za-z_]\w*)', code)
        if m: globals_.add(m.group(1))

    # ---- UDT field names (they appear as obj.field, but also bare in .new()) -
    udt_fields = set()
    cur = None
    for ln in lines:
        code = ln.split('//')[0].rstrip()
        m = re.match(r'^(?:export\s+)?type\s+([A-Za-z_]\w*)', code)
        if m: cur = m.group(1); continue
        if cur:
            if not code.strip(): continue
            if not code.startswith('    '): cur = None; continue
            m2 = re.match(r'^\s+' + TYPE + r'\s+([A-Za-z_]\w*)', code)
            if m2: udt_fields.add(m2.group(1))

    # ---- per-function scope -------------------------------------------------
    i = 0
    while i < len(lines):
        code = lines[i].split('//')[0]
        m = re.match(r'^(?:export\s+)?([A-Za-z_]\w*)\s*\(', code)
        if not m or code.startswith((' ', '\t')):
            i += 1; continue
        fname = m.group(1)
        if fname in ('library', 'indicator', 'strategy', 'import', 'plot', 'plotshape',
                     'plotchar', 'fill', 'bgcolor', 'barcolor', 'hline', 'alertcondition'):
            i += 1; continue
        # gather the signature: keep appending only while brackets are still open
        sig = code; j = i
        dep = sig.count('(') - sig.count(')')
        while dep > 0 and j + 1 < len(lines):
            j += 1
            nxt = lines[j].split('//')[0]
            sig += ' ' + nxt
            dep += nxt.count('(') - nxt.count(')')
        if not sig.rstrip().endswith('=>'):
            i += 1; continue
        params = set()
        inner = sig[sig.index('(') + 1: sig.rindex(')')] if ')' in sig else ''
        for pdecl in re.split(r',(?![^<]*>)', inner):
            pdecl = pdecl.strip()
            if not pdecl: continue
            nm = pdecl.split('=')[0].strip().split()[-1]
            params.add(nm)
        # body
        body = []
        k = j + 1
        while k < len(lines):
            l = lines[k]
            if l.strip() and not l.startswith((' ', '\t')): break
            body.append((k + 1, l)); k += 1
        scope = set(params)
        for _, l in body:
            c = l.split('//')[0]
            for mm in re.finditer(r'\b' + TYPE + r'\s+([A-Za-z_]\w*)\s*(?:=|:=)', c):
                scope.add(mm.group(1))
            for t in re.findall(r'\[([^\]]*)\]\s*=', c):
                for x in t.split(','):
                    x = x.strip()
                    if re.match(r'^[A-Za-z_]\w*$', x): scope.add(x)
            mm = re.match(r'^\s*for\s+([A-Za-z_]\w*)', c)
            if mm: scope.add(mm.group(1))
            mm = re.match(r'^\s*for\s+\[?([A-Za-z_]\w*)\s*,\s*([A-Za-z_]\w*)\]?\s+in\b', c)
            if mm: scope.add(mm.group(1)); scope.add(mm.group(2))
            for mm2 in re.finditer(r'\b([A-Za-z_]\w*)\s*:=', c):
                scope.add(mm2.group(1))
        # now look for reads of unknown names
        for lineno, l in body:
            c = l.split('//')[0]
            c = re.sub(r'"[^"]*"', '""', c)
            c = re.sub(r'\b[A-Za-z_]\w*\s*\(', '(', c)          # drop call targets
            c = re.sub(r'\.\s*[A-Za-z_]\w*', '', c)             # drop .field / .method
            c = re.sub(r'\b[A-Za-z_]\w*\s*=(?!=)', '', c)       # drop named args
            for mm in re.finditer(r'\b([A-Za-z_][A-Za-z0-9_]*)\b', c):
                nm = mm.group(1)
                if nm in scope or nm in globals_ or nm in BUILTIN or nm in udt_fields:
                    continue
                if re.match(r'^(RID_|CAT_|SUB_|TF_|PH_|GR_|DEN_|WEAK_|EV_|SIDE_|SESS_|PER_|FVG_|ROOT_|ACCUM_)', nm):
                    continue
                problems.append((lineno, fname, 'undefined name: %s' % nm, l.strip()[:70]))
        i = k

    # ---- structural checks --------------------------------------------------
    d = 0
    for ln in lines:
        c = re.sub(r'"[^"]*"', '""', ln.split('//')[0])
        d += c.count('(') + c.count('[') - c.count(')') - c.count(']')
    if d: problems.append((0, '-', 'bracket imbalance %d' % d, ''))
    for n, ln in enumerate(lines, 1):
        if ln.lstrip().startswith('//'): continue
        if len(re.findall(r'(?<!\\)"', ln)) % 2: problems.append((n, '-', 'unterminated string literal', ln.strip()[:70]))
    for n, ln in enumerate(lines, 1):
        if not ln.strip() or ln.strip().startswith('//'): continue
        prev = None
        for j2 in range(n - 2, -1, -1):
            if lines[j2].strip() and not lines[j2].strip().startswith('//'):
                prev = lines[j2]; break
        if prev is None: continue
        pc = prev.split('//')[0].rstrip()
        if not pc or pc.endswith('=>'): continue
        if pc.endswith((',', '(', '[', '+', '-', '*', '/', '?', ':', '=')) or re.search(r'\b(and|or)$', pc):
            ind = len(ln) - len(ln.lstrip(' '))
            if ind % 4 == 0: problems.append((n, '-', 'continuation indent %%4==0 (%d)' % ind, ln.strip()[:60]))
    return problems

bad = 0
for path in sys.argv[1:]:
    pr = check(path)
    print('=== %s : %d problem(s)' % (path, len(pr)))
    for lineno, fn, msg, txt in pr[:60]:
        print('   %5s  %-26s %-34s |%s' % (lineno, fn, msg, txt))
    bad += len(pr)
sys.exit(1 if bad else 0)
