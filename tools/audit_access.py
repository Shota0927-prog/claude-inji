#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Enumerate every collection access / history reference / request.* in a Pine file
and report the enclosing function plus the nearest guard on the same or an
enclosing line. Output is a table for the audit, not a proof of safety."""
import re, sys
from collections import Counter

PATS = [
    ('array.get',   re.compile(r'\barray\.get\s*\(')),
    ('array.set',   re.compile(r'\barray\.set\s*\(')),
    ('array.remove',re.compile(r'\barray\.remove\s*\(')),
    ('array.insert',re.compile(r'\barray\.insert\s*\(')),
    ('array.pop',   re.compile(r'\barray\.pop\s*\(')),
    ('map.get',     re.compile(r'\bmap\.get\s*\(')),
    ('map.remove',  re.compile(r'\bmap\.remove\s*\(')),
    ('for 0..n-1',  re.compile(r'\bfor\s+\w+\s*=\s*0\s+to\s+\S+\s*-\s*1\b')),
    ('history ref', re.compile(r'\b(?:time|time_close|open|close|high|low|volume)\s*\[')),
    ('request.*',   re.compile(r'\brequest\.\w+\s*\(')),
]
GUARD = re.compile(r'\b(?:if|while)\b.*?('
                   r'>\s*0|>=\s*0|<\s*array\.size|<=\s*array\.size|'
                   r'map\.contains|not\s+na|>\s*1|>=\s*1|>=\s*2|<\s*n\b|Fits\b)')

def run(path):
    lines = open(path, encoding='utf-8').read().split('\n')
    fname, rows, counts = '-', [], Counter()
    for n, ln in enumerate(lines, 1):
        code = ln.split('//')[0]
        m = re.match(r'^([A-Za-z_]\w*)\s*\(', ln)
        if m:
            fname = m.group(1)
        elif ln.strip() and not ln.startswith((' ', '\t')) and not ln.lstrip().startswith('//'):
            fname = '-'
        for label, pat in PATS:
            if not pat.search(code):
                continue
            counts[label] += 1
            ind = len(code) - len(code.lstrip(' '))
            guard, cur = '', ind
            if GUARD.search(code):
                guard = 'same line'
            else:
                for j in range(n - 2, -1, -1):
                    prev = lines[j].split('//')[0]
                    if not prev.strip():
                        continue
                    pind = len(prev) - len(prev.lstrip(' '))
                    if pind >= cur:
                        continue
                    cur = pind
                    if GUARD.search(prev):
                        guard = 'L%d: %s' % (j + 1, prev.strip()[:44])
                        break
                    if pind == 0:
                        break
            rows.append((n, label, fname, guard or 'NONE FOUND'))
    return rows, counts

for path in sys.argv[1:]:
    rows, counts = run(path)
    print('===== %s =====' % path)
    for k, v in sorted(counts.items(), key=lambda x: -x[1]):
        print('  %-14s %4d' % (k, v))
    bad = [r for r in rows if r[3] == 'NONE FOUND']
    print('  -- no guard found on an enclosing line: %d --' % len(bad))
    for n, label, fn, g in bad:
        print('   L%-5d %-12s %-26s %s' % (n, label, fn, g))
