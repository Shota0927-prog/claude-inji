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
    # ---- declaration order: every f_* / UDT must be declared before first use --
    decl_line = {}
    for n, ln in enumerate(lines, 1):
        m = re.match(r'^(f_\w+)\s*\(', ln)
        if m and m.group(1) not in decl_line:
            decl_line[m.group(1)] = n
        m = re.match(r'^(?:export\s+)?type\s+(\w+)', ln)
        if m and m.group(1) not in decl_line:
            decl_line[m.group(1)] = n
    for n, ln in enumerate(lines, 1):
        code = ln.split('//')[0]
        if re.match(r'^f_\w+\s*\(', code):      # the declaration line itself
            code = code.split('=>')[0].split('(', 1)[-1]
        for nm in set(re.findall(r'\bf_\w+\b', code)):
            if nm in decl_line and decl_line[nm] > n:
                problems.append((n, '-', 'used before declaration: %s (declared L%d)'
                                 % (nm, decl_line[nm]), ln.strip()[:60]))
        for nm in set(re.findall(r'\b([A-Z]\w*)\.new\b', code)):
            if nm in decl_line and decl_line[nm] > n:
                problems.append((n, '-', 'type used before declaration: %s (declared L%d)'
                                 % (nm, decl_line[nm]), ln.strip()[:60]))

    # ---- `for v = A + 1 to N - 1` with a reachable A == N - 1 ----------------
    # Pine runs `for b = n to n - 1` DESCENDING, so the body executes with
    # b == n and array.get(arr, n) reads out of bounds. Require an explicit
    # guard: either `A < N - 1` in an enclosing line, or the outer loop that
    # declares A bounded by `to N - 2` under an `N >= 2` test.
    for n0, ln in enumerate(lines, 1):
        code = ln.split('//')[0]
        m = re.search(r'\bfor\s+\w+\s*=\s*(\w+)\s*\+\s*1\s+to\s+(\w+)\s*-\s*1\b', code)
        if not m:
            continue
        A, N = m.group(1), m.group(2)
        ind = len(code) - len(code.lstrip(' '))
        guarded = False
        for j2 in range(n0 - 2, -1, -1):
            prev = lines[j2].split('//')[0]
            if not prev.strip():
                continue
            pind = len(prev) - len(prev.lstrip(' '))
            if pind >= ind:
                continue
            if re.search(r'\b%s\s*<\s*%s\s*-\s*1\b' % (re.escape(A), re.escape(N)), prev):
                guarded = True
                break
            if re.search(r'\bfor\s+%s\s*=.*\bto\s+%s\s*-\s*2\b' % (re.escape(A), re.escape(N)), prev):
                guarded = True
                break
            if pind == 0:
                break
        if not guarded:
            problems.append((n0, '-', 'for %s+1 to %s-1 without a %s < %s-1 guard'
                             % (A, N, A, N), ln.strip()[:60]))

    # ---- display calls must sit behind a last-bar gate (harness only) --------
    # Drawing, tables and display string building must never run on history bars.
    # A call qualifies if some enclosing `if` (any level) names a last-bar gate,
    # or it is the one-time `var t = na` / `if na(t)` object creation.
    helper_display = set()
    DRAW = re.compile(r'\b(?:box|line|label|table)\.(?:new|set_\w+|cell|clear|delete)\b'
                      r'|\bstr\.format_time\b')
    GATE = re.compile(r'barstate\.islast|barstate\.islastconfirmedhistory|needRedraw'
                      r'|wantProjection|lastWantEvents|na\(')
    if 'indicator(' in src or 'strategy(' in src:
        for n0, ln in enumerate(lines, 1):
            code = ln.split('//')[0]
            if not DRAW.search(code):
                continue
            ind = len(code) - len(code.lstrip(' '))
            gated = False
            cur = ind
            for j2 in range(n0 - 2, -1, -1):
                prev = lines[j2].split('//')[0]
                if not prev.strip():
                    continue
                pind = len(prev) - len(prev.lstrip(' '))
                if pind >= cur:
                    continue
                cur = pind
                if GATE.search(prev):
                    gated = True
                    break
                if pind == 0:
                    break
            if gated:
                continue
            # The call may sit inside a display HELPER (f_boxAt, f_dbgRow, ...).
            # Then the requirement moves to every call site of that helper.
            owner = None
            for j2 in range(n0 - 1, -1, -1):
                m2 = re.match(r'^(f_\w+)\s*\(', lines[j2])
                if m2:
                    owner = m2.group(1)
                    break
                if lines[j2].strip() and not lines[j2].startswith((' ', '\t')) \
                        and not lines[j2].lstrip().startswith('//'):
                    break
            if owner is None:
                problems.append((n0, '-', 'display call not behind a last-bar gate',
                                 ln.strip()[:60]))
                continue
            helper_display.add(owner)

        # every call site of a display helper must itself be gated
        for nm in sorted(helper_display):
            for n0, ln in enumerate(lines, 1):
                code = ln.split('//')[0]
                if re.match(r'^(?:\s*)' + re.escape(nm) + r'\s*\(', code):
                    continue                      # its own declaration
                if not re.search(r'\b' + re.escape(nm) + r'\s*\(', code):
                    continue
                ind = len(code) - len(code.lstrip(' '))
                if ind == 0:
                    problems.append((n0, '-', 'display helper %s called unconditionally' % nm,
                                     ln.strip()[:60]))
                    continue
                gated = False
                cur = ind
                for j2 in range(n0 - 2, -1, -1):
                    prev = lines[j2].split('//')[0]
                    if not prev.strip():
                        continue
                    pind = len(prev) - len(prev.lstrip(' '))
                    if pind >= cur:
                        continue
                    cur = pind
                    if GATE.search(prev) or re.match(r'^f_\w+\s*\(', prev):
                        gated = True
                        break
                    if pind == 0:
                        break
                if not gated:
                    problems.append((n0, '-', 'display helper %s call not gated' % nm,
                                     ln.strip()[:60]))

    # ---- request.* tuple budget (Pine caps the script total at 127) ----------
    # Counted over EVERY source branch, not just the executed one. A UDT return
    # counts as 1 element; a [a, b, c] destructuring counts as its arity.
    def owner_of(i):
        # walk back to the statement start: a line is a continuation when the
        # previous code line ends with '=', ',' or '(' (Pine line wrapping).
        while i > 0:
            prev = lines[i - 1].split('//')[0].rstrip()
            if prev.endswith(('=', ',', '(')) and not prev.endswith('=>'):
                i -= 1
            else:
                break
        return i
    total = 0
    seen_owner = set()
    for n, ln in enumerate(lines, 1):
        code = ln.split('//')[0]
        if 'request.security' not in code and 'request.' not in code:
            continue
        if 'request.' not in code:
            continue
        o = owner_of(n - 1)
        if o in seen_owner:
            continue
        seen_owner.add(o)
        own = lines[o].split('//')[0]
        m = re.match(r'\s*\[([^\]]*)\]\s*=', own)
        total += len([x for x in m.group(1).split(',') if x.strip()]) if m else 1
    if total > 127:
        problems.append((0, '-', 'request.* tuple elements %d > 127' % total, ''))
    elif total:
        print('   (info) %s : request.* tuple elements = %d / 127' % (path, total))

    return problems

bad = 0
for path in sys.argv[1:]:
    pr = check(path)
    print('=== %s : %d problem(s)' % (path, len(pr)))
    for lineno, fn, msg, txt in pr[:60]:
        print('   %5s  %-26s %-34s |%s' % (lineno, fn, msg, txt))
    bad += len(pr)
sys.exit(1 if bad else 0)
