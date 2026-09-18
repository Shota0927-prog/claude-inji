# -*- coding: utf-8 -*-
import re, sys, collections

path = sys.argv[1]
lines = open(path, encoding='utf-8').read().split('\n')

# map each line -> enclosing top-level function
func_of = [None]*(len(lines)+1)
cur = '<top>'
for i, ln in enumerate(lines, 1):
    code = ln.split('//')[0]
    m = re.match(r'^(?:export\s+)?([A-Za-z_]\w*)\s*\(', code)
    if m and not code.startswith(' '):
        cur = m.group(1)
    elif code.strip() and not code.startswith((' ', '\t')) and not code.startswith(('//','type','export type','import','indicator','library','if ','else','for ','while ','plot','var ','varip ')):
        pass
    func_of[i] = cur

# loop nesting depth at each line
depth = [0]*(len(lines)+1)
stack = []
for i, ln in enumerate(lines, 1):
    code = ln.split('//')[0]
    if not code.strip():
        depth[i] = len(stack); continue
    ind = len(code) - len(code.lstrip(' '))
    while stack and ind <= stack[-1]:
        stack.pop()
    depth[i] = len(stack)
    if re.match(r'^\s*(for|while)\b', code):
        stack.append(ind)

PAT = [
 ('for/while',      r'^\s*(for|while)\b'),
 ('array.new',      r'array\.new'),
 ('array.copy',     r'array\.copy\('),
 ('array.insert',   r'array\.insert\('),
 ('array.sort',     r'array\.sort'),
 ('array.includes', r'array\.includes\('),
 ('map.new',        r'map\.new'),
 ('f_rootIdxById',  r'f_rootIdxById\('),
 ('request.*',      r'request\.'),
 ('draw obj',       r'\b(label|line|box|table)\.(new|set_|cell|clear)'),
 ('string build',   r'str\.(tostring|format|format_time)'),
 ('cand/core new',  r'(ZoneCand|CoreCand|ZoneCore|ZoneView|ZoneEvent|Root)\.new\('),
 ('roots full scan',r'array\.size\(e\.roots\)'),
]

rows = collections.defaultdict(list)
for i, ln in enumerate(lines, 1):
    code = ln.split('//')[0]
    if not code.strip():
        continue
    for name, rx in PAT:
        if re.search(rx, code):
            rows[name].append((i, func_of[i], depth[i], code.strip()[:78]))

print('==== %s : %d lines ====' % (path, len(lines)))
for name, _ in PAT:
    r = rows[name]
    print('\n---- %-16s total=%d' % (name, len(r)))
    byfunc = collections.Counter(x[1] for x in r)
    for fn, cnt in byfunc.most_common():
        mx = max(x[2] for x in r if x[1] == fn)
        print('      %-28s x%-3d  maxLoopDepth=%d' % (fn, cnt, mx))
