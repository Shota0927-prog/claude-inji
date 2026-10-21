"""CAD-1 adaptation record — the exact edits CAD-1 (confirmed-alert dedup rolled out to the GBPJPY-lineage Strategies) made
to older generators / fixtures.

ADAPT maps each file to the (before, after) text pairs of its CAD-1 edit, generated from the diff against 867ff7e (the commit
before CAD-1). unadapt() reverses them all-or-nothing (a text without any CAD-1 edit is returned unchanged); xa_build.unadapt()
- the innermost link of the older fixtures' adaptation chain - calls it first (then the UJ-3 record), so the older "unchanged
since <rev>" checks accept these files only when they differ by exactly these edits. ok(path, rev) accepts a path vs `rev`
only when CAD-1 accounts for it exactly: one of the four Strategies with exactly the CAD-1 layer (cad_build.strip; the BTC
Strategy may also carry its earlier BTE-1 layer, stripped exactly), a
recorded file whose CAD-1 edits (and, when also present, the UJ-3 / UJ-4 / UJ-5 record) revert to `rev` byte for byte, or a
file new in CAD-1.
"""
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NEW_FILES = ("tests/cad_build.py", "tests/cad_adapt.py", "tests/cad_sim.py")
_rd = lambda p: open(os.path.join(ROOT, p), encoding="utf-8").read()


def _show(rev, path):
    return subprocess.run(["git", "-C", ROOT, "show", f"{rev}:{path}"], capture_output=True, text=True).stdout


def unadapt(path, text):
    """the text with its CAD-1 edits reverted; unchanged when none is present; None when only some are present."""
    pairs = ADAPT.get(path, [])
    if text is None or not pairs:
        return text
    if all(text.count(b) == 0 for _, b in pairs):
        return text
    out = text
    for a, b in reversed(pairs):
        if out.count(b) != 1:
            return None
        out = out.replace(b, a)
    return out


def pine_ok(path, rev):
    """True for one of the four GBPJPY-lineage Strategies when it differs from `rev` exactly by the CAD-1 layer."""
    import cad_build as cb
    if path not in cb.FILES or not os.path.exists(os.path.join(ROOT, path)):
        return False
    s = cb.strip(_rd(path))
    if s is None:
        return False
    old = _show(rev, path)
    if s == old:
        return True
    import btcs_build as sb     # the BTC Strategy may also carry the earlier BTE-1 layer (BTS-3), exactly
    return path == sb.BTS_PATH and sb.strip_bts3(s) == old


def ok(path, rev):
    """CAD-1 accounts for this path vs `rev` exactly (see the module doc)."""
    if path in NEW_FILES:
        return True
    if pine_ok(path, rev):
        return True
    if path in ADAPT and os.path.exists(os.path.join(ROOT, path)):
        cur = _rd(path)
        u = unadapt(path, cur)
        if u is None or u == cur:
            return False
        old = _show(rev, path)
        if u == old:
            return True
        u2 = __import__("uj3_adapt").unadapt(path, u)     # the file may also carry the earlier UJ-3 .. UJ-5 record
        return u2 is not None and u2 != u and u2 == old
    return False


ADAPT = {'tests/btcs_build.py': [('def build():\n'
                          '    return bts_transform(open(os.path.join(ROOT, SRC_PATH), encoding="utf-8").read())\n'
                          '\n',
                          'def build():\n'
                          '    return bts_transform(__import__("cad_build").pre_cad(SRC_PATH, '
                          'open(os.path.join(ROOT, SRC_PATH), encoding="utf-8").read()))   # CAD-1 reverted\n'
                          '\n'),
                         ('if __name__ == "__main__":\n'
                          '    open(os.path.join(ROOT, BTS_PATH), "w", encoding="utf-8").write(build())\n'
                          '    print("written", BTS_PATH)\n',
                          'if __name__ == "__main__":\n'
                          '    open(os.path.join(ROOT, BTS_PATH), "w", '
                          'encoding="utf-8").write(__import__("cad_build").apply(build()))   # CAD-1: last layer\n'
                          '    print("written", BTS_PATH)\n')],
 'tests/btcs_sim.py': [('BASE = "f9d9440"\n'
                        'rd = lambda p: open(os.path.join(ROOT, p), encoding="utf-8").read() if '
                        'os.path.exists(os.path.join(ROOT, p)) else ""\n'
                        'GBS = rd(sb.SRC_PATH)\n',
                        'BASE = "f9d9440"\n'
                        'rd = lambda p: __import__("cad_build").pre_cad(p, open(os.path.join(ROOT, p), '
                        'encoding="utf-8").read() if os.path.exists(os.path.join(ROOT, p)) else "")   # CAD-1 '
                        'reverted (pinned in cad_sim)\n'
                        'GBS = rd(sb.SRC_PATH)\n')],
 'tests/bte_sim.py': [('ROOT = be.ROOT\n'
                       'rd = lambda p: open(os.path.join(ROOT, p), encoding="utf-8").read()\n'
                       'git = lambda *a: subprocess.run(["git", "-C", ROOT] + list(a), capture_output=True, '
                       'text=True).stdout\n',
                       'ROOT = be.ROOT\n'
                       'rd = lambda p: __import__("cad_build").pre_cad(p, open(os.path.join(ROOT, p), '
                       'encoding="utf-8").read())   # CAD-1 reverted (pinned in cad_sim)\n'
                       'git = lambda *a: subprocess.run(["git", "-C", ROOT] + list(a), capture_output=True, '
                       'text=True).stdout\n'),
                      ('    rest = [m for m in mod if not (be.bte_pine_ok(m, be.BASE_REV) or be.test_ok(m) or '
                       '__import__("xa_build").xa_ok(m, be.BASE_REV)\n'
                       '                                   or __import__("uj3_adapt").pine_ok(m, be.BASE_REV))]   # '
                       'XA-1 / UJ-3: exact\n'
                       '    check("BE-07 vs e1c3cea: the BTC Visual / Strategy differ exactly by the new layer, '
                       'every other changed file is a test / "\n',
                       '    rest = [m for m in mod if not (be.bte_pine_ok(m, be.BASE_REV) or be.test_ok(m) or '
                       '__import__("xa_build").xa_ok(m, be.BASE_REV)\n'
                       '                                   or __import__("uj3_adapt").pine_ok(m, be.BASE_REV) or '
                       '__import__("cad_adapt").ok(m, be.BASE_REV))]   # XA-1 / UJ-3 / CAD-1: exact\n'
                       '    check("BE-07 vs e1c3cea: the BTC Visual / Strategy differ exactly by the new layer, '
                       'every other changed file is a test / "\n'),
                      ('          and not [m for m in mod if m.endswith(".pine") and m not in (bb.BTC_PATH, '
                       'sb.BTS_PATH)\n'
                       '                   and not __import__("xa_build").xa_ok(m, be.BASE_REV) and not '
                       '__import__("uj3_adapt").pine_ok(m, be.BASE_REV)], str(rest))\n'
                       '    m = S.replace("import sekine3310/ZoneEnginePracticalBTCUSD/1 as zn", "import '
                       'sekine3310/ZoneEnginePracticalGBPJPY/3 as zn")\n',
                       '          and not [m for m in mod if m.endswith(".pine") and m not in (bb.BTC_PATH, '
                       'sb.BTS_PATH)\n'
                       '                   and not __import__("xa_build").xa_ok(m, be.BASE_REV) and not '
                       '__import__("uj3_adapt").pine_ok(m, be.BASE_REV) and not __import__("cad_adapt").ok(m, '
                       'be.BASE_REV)], str(rest))\n'
                       '    m = S.replace("import sekine3310/ZoneEnginePracticalBTCUSD/1 as zn", "import '
                       'sekine3310/ZoneEnginePracticalGBPJPY/3 as zn")\n')],
 'tests/eu_build.py': [('\n_rd = lambda p: open(os.path.join(ROOT, p), encoding="utf-8").read()\n\n',
                        '\n'
                        '_rd = lambda p: __import__("cad_build").pre_cad(p, open(os.path.join(ROOT, p), '
                        'encoding="utf-8").read())   # CAD-1 reverted (re-applied on write)\n'
                        '\n'),
                       ('    for path, fn in ((ENG_PATH, build_engine), (VIS_PATH, build_visual), (STR_PATH, '
                        'build_strategy)):\n'
                        '        open(os.path.join(ROOT, path), "w", encoding="utf-8").write(fn())\n'
                        '        print("written", path)\n',
                        '    for path, fn in ((ENG_PATH, build_engine), (VIS_PATH, build_visual), (STR_PATH, '
                        'build_strategy)):\n'
                        '        open(os.path.join(ROOT, path), "w", '
                        'encoding="utf-8").write(__import__("cad_build").apply(fn()) if path == STR_PATH else fn())\n'
                        '        print("written", path)\n')],
 'tests/eu_sim.py': [('BASE = "4c53b87"\n'
                      'rd = lambda p: open(os.path.join(ROOT, p), encoding="utf-8").read() if '
                      'os.path.exists(os.path.join(ROOT, p)) else ""\n'
                      'show = lambda p, rev=BASE: subprocess.run(["git", "-C", ROOT, "show", f"{rev}:{p}"], '
                      'capture_output=True, text=True).stdout\n',
                      'BASE = "4c53b87"\n'
                      'rd = lambda p: __import__("cad_build").pre_cad(p, open(os.path.join(ROOT, p), '
                      'encoding="utf-8").read() if os.path.exists(os.path.join(ROOT, p)) else "")   # CAD-1 reverted '
                      '(pinned in cad_sim)\n'
                      'show = lambda p, rev=BASE: subprocess.run(["git", "-C", ROOT, "show", f"{rev}:{p}"], '
                      'capture_output=True, text=True).stdout\n')],
 'tests/gbd_sim.py': [('PREV = "3205d03"\n'
                       'rd = lambda p: open(os.path.join(ROOT, p), encoding="utf-8").read() if '
                       'os.path.exists(os.path.join(ROOT, p)) else ""\n'
                       'show = lambda p, rev=PREV: subprocess.run(["git", "-C", ROOT, "show", f"{rev}:{p}"], '
                       'capture_output=True, text=True).stdout\n',
                       'PREV = "3205d03"\n'
                       'rd = lambda p: __import__("cad_build").pre_cad(p, open(os.path.join(ROOT, p), '
                       'encoding="utf-8").read() if os.path.exists(os.path.join(ROOT, p)) else "")   # CAD-1 '
                       'reverted (pinned in cad_sim)\n'
                       'show = lambda p, rev=PREV: subprocess.run(["git", "-C", ROOT, "show", f"{rev}:{p}"], '
                       'capture_output=True, text=True).stdout\n')],
 'tests/gbe_sim.py': [('PREV = "91036ec"\n'
                       'rd = lambda p: open(os.path.join(ROOT, p), encoding="utf-8").read() if '
                       'os.path.exists(os.path.join(ROOT, p)) else ""\n'
                       'show = lambda p, rev=PREV: subprocess.run(["git", "-C", ROOT, "show", f"{rev}:{p}"], '
                       'capture_output=True, text=True).stdout\n',
                       'PREV = "91036ec"\n'
                       'rd = lambda p: __import__("cad_build").pre_cad(p, open(os.path.join(ROOT, p), '
                       'encoding="utf-8").read() if os.path.exists(os.path.join(ROOT, p)) else "")   # CAD-1 '
                       'reverted (pinned in cad_sim)\n'
                       'show = lambda p, rev=PREV: subprocess.run(["git", "-C", ROOT, "show", f"{rev}:{p}"], '
                       'capture_output=True, text=True).stdout\n')],
 'tests/gbf_sim.py': [('PREV = "60cc26f"\n'
                       'rd = lambda p: open(os.path.join(ROOT, p), encoding="utf-8").read() if '
                       'os.path.exists(os.path.join(ROOT, p)) else ""\n'
                       'show = lambda p, rev=PREV: subprocess.run(["git", "-C", ROOT, "show", f"{rev}:{p}"], '
                       'capture_output=True, text=True).stdout\n',
                       'PREV = "60cc26f"\n'
                       'rd = lambda p: __import__("cad_build").pre_cad(p, open(os.path.join(ROOT, p), '
                       'encoding="utf-8").read() if os.path.exists(os.path.join(ROOT, p)) else "")   # CAD-1 '
                       'reverted (pinned in cad_sim)\n'
                       'show = lambda p, rev=PREV: subprocess.run(["git", "-C", ROOT, "show", f"{rev}:{p}"], '
                       'capture_output=True, text=True).stdout\n')],
 'tests/gbn_sim.py': [('PREV = "c07a97a"\n'
                       'rd = lambda p: open(os.path.join(ROOT, p), encoding="utf-8").read() if '
                       'os.path.exists(os.path.join(ROOT, p)) else ""\n'
                       'show = lambda p, rev=PREV: subprocess.run(["git", "-C", ROOT, "show", f"{rev}:{p}"], '
                       'capture_output=True, text=True).stdout\n',
                       'PREV = "c07a97a"\n'
                       'rd = lambda p: __import__("cad_build").pre_cad(p, open(os.path.join(ROOT, p), '
                       'encoding="utf-8").read() if os.path.exists(os.path.join(ROOT, p)) else "")   # CAD-1 '
                       'reverted (pinned in cad_sim)\n'
                       'show = lambda p, rev=PREV: subprocess.run(["git", "-C", ROOT, "show", f"{rev}:{p}"], '
                       'capture_output=True, text=True).stdout\n')],
 'tests/gbq_sim.py': [('PREV = "dedfbbc"\n'
                       'rd = lambda p: open(os.path.join(ROOT, p), encoding="utf-8").read() if '
                       'os.path.exists(os.path.join(ROOT, p)) else ""\n'
                       'show = lambda p, rev=PREV: subprocess.run(["git", "-C", ROOT, "show", f"{rev}:{p}"], '
                       'capture_output=True, text=True).stdout\n',
                       'PREV = "dedfbbc"\n'
                       'rd = lambda p: __import__("cad_build").pre_cad(p, open(os.path.join(ROOT, p), '
                       'encoding="utf-8").read() if os.path.exists(os.path.join(ROOT, p)) else "")   # CAD-1 '
                       'reverted (pinned in cad_sim)\n'
                       'show = lambda p, rev=PREV: subprocess.run(["git", "-C", ROOT, "show", f"{rev}:{p}"], '
                       'capture_output=True, text=True).stdout\n')],
 'tests/gbs_build.py': [('if __name__ == "__main__":\n'
                         '    open(os.path.join(ROOT, GBS_PATH), "w", encoding="utf-8").write(build())\n'
                         '    print("written", GBS_PATH)\n',
                         'if __name__ == "__main__":\n'
                         '    open(os.path.join(ROOT, GBS_PATH), "w", '
                         'encoding="utf-8").write(__import__("cad_build").apply(build()))   # CAD-1: last layer\n'
                         '    print("written", GBS_PATH)\n')],
 'tests/gbs_sim.py': [('BASE = "140a6c9"\n'
                       'rd = lambda p: open(os.path.join(ROOT, p), encoding="utf-8").read() if '
                       'os.path.exists(os.path.join(ROOT, p)) else ""\n'
                       'GBS_FULL = rd(gs.GBS_PATH)\n',
                       'BASE = "140a6c9"\n'
                       'rd = lambda p: __import__("cad_build").pre_cad(p, open(os.path.join(ROOT, p), '
                       'encoding="utf-8").read() if os.path.exists(os.path.join(ROOT, p)) else "")   # CAD-1 '
                       'reverted (pinned in cad_sim)\n'
                       'GBS_FULL = rd(gs.GBS_PATH)\n')],
 'tests/gbx_sim.py': [('BASE = "65b1fb3"\n'
                       'rd = lambda p: open(os.path.join(ROOT, p), encoding="utf-8").read() if '
                       'os.path.exists(os.path.join(ROOT, p)) else ""\n'
                       'show = lambda p, rev=BASE: subprocess.run(["git", "-C", ROOT, "show", f"{rev}:{p}"], '
                       'capture_output=True, text=True).stdout\n',
                       'BASE = "65b1fb3"\n'
                       'rd = lambda p: __import__("cad_build").pre_cad(p, open(os.path.join(ROOT, p), '
                       'encoding="utf-8").read() if os.path.exists(os.path.join(ROOT, p)) else "")   # CAD-1 '
                       'reverted (pinned in cad_sim)\n'
                       'show = lambda p, rev=BASE: subprocess.run(["git", "-C", ROOT, "show", f"{rev}:{p}"], '
                       'capture_output=True, text=True).stdout\n')],
 'tests/gu_build.py': [('\n_rd = lambda p: open(os.path.join(ROOT, p), encoding="utf-8").read()\n\n',
                        '\n'
                        '_rd = lambda p: __import__("cad_build").pre_cad(p, open(os.path.join(ROOT, p), '
                        'encoding="utf-8").read())   # CAD-1 reverted (re-applied on write)\n'
                        '\n'),
                       ('    for path, fn in ((ENG_PATH, build_engine), (VIS_PATH, build_visual), (STR_PATH, '
                        'build_strategy)):\n'
                        '        open(os.path.join(ROOT, path), "w", encoding="utf-8").write(fn())\n'
                        '        print("written", path)\n',
                        '    for path, fn in ((ENG_PATH, build_engine), (VIS_PATH, build_visual), (STR_PATH, '
                        'build_strategy)):\n'
                        '        open(os.path.join(ROOT, path), "w", '
                        'encoding="utf-8").write(__import__("cad_build").apply(fn()) if path == STR_PATH else fn())\n'
                        '        print("written", path)\n')],
 'tests/gu_sim.py': [('BASE = "47aeb8b"\n'
                      'rd = lambda p: open(os.path.join(ROOT, p), encoding="utf-8").read() if '
                      'os.path.exists(os.path.join(ROOT, p)) else ""\n'
                      'show = lambda p, rev=BASE: subprocess.run(["git", "-C", ROOT, "show", f"{rev}:{p}"], '
                      'capture_output=True, text=True).stdout\n',
                      'BASE = "47aeb8b"\n'
                      'rd = lambda p: __import__("cad_build").pre_cad(p, open(os.path.join(ROOT, p), '
                      'encoding="utf-8").read() if os.path.exists(os.path.join(ROOT, p)) else "")   # CAD-1 reverted '
                      '(pinned in cad_sim)\n'
                      'show = lambda p, rev=BASE: subprocess.run(["git", "-C", ROOT, "show", f"{rev}:{p}"], '
                      'capture_output=True, text=True).stdout\n')],
 'tests/uj_build.py': [('    # XA-1 (Gold defaults): ZONE-P / ZONE-ST may also differ, exactly by that layer\n'
                        '    return [n for n in names if not ((n in UJ_FILES and uj_ok(n, rev)) or '
                        '__import__("bte_build").bte_pine_ok(n, rev)\n',
                        '    # XA-1 (Gold defaults): ZONE-P / ZONE-ST may also differ, exactly by that layer\n'
                        '    # CAD-1 (confirmed-alert dedup): the four GBPJPY-lineage Strategies / adapted fixtures '
                        'may also differ, exactly by it\n'
                        '    return [n for n in names if not ((n in UJ_FILES and uj_ok(n, rev)) or '
                        '__import__("bte_build").bte_pine_ok(n, rev)\n'),
                       ('    return [n for n in names if not ((n in UJ_FILES and uj_ok(n, rev)) or '
                        '__import__("bte_build").bte_pine_ok(n, rev)\n'
                        '                                     or __import__("xa_build").xa_ok(n, rev))]\n'
                        '\n',
                        '    return [n for n in names if not ((n in UJ_FILES and uj_ok(n, rev)) or '
                        '__import__("bte_build").bte_pine_ok(n, rev)\n'
                        '                                     or __import__("xa_build").xa_ok(n, rev) or '
                        '__import__("cad_adapt").ok(n, rev))]\n'
                        '\n')],
 'tests/uj_sim.py': [('    mod = git("diff", "--name-only", "--diff-filter=MDR", ub.BASE_REV, "--").split()\n'
                      '    mod = [m for m in mod if not (__import__("bte_build").bte_pine_ok(m, ub.BASE_REV) or '
                      '__import__("xa_build").xa_ok(m, ub.BASE_REV))]     # BTE-1 / XA-1: exact\n'
                      '    rest = [m for m in mod if m not in ub.UJ_FILES and not ub.test_ok(m)]\n',
                      '    mod = git("diff", "--name-only", "--diff-filter=MDR", ub.BASE_REV, "--").split()\n'
                      '    mod = [m for m in mod if not (__import__("bte_build").bte_pine_ok(m, ub.BASE_REV) or '
                      '__import__("xa_build").xa_ok(m, ub.BASE_REV)\n'
                      '                                  or __import__("cad_adapt").ok(m, ub.BASE_REV))]     # BTE-1 '
                      '/ XA-1 / CAD-1: exact\n'
                      '    rest = [m for m in mod if m not in ub.UJ_FILES and not ub.test_ok(m)]\n'),
                     ('    mod = [m for m in mod if not (__import__("bte_build").bte_pine_ok(m, UJ1) or '
                      '__import__("bte_build").test_ok(m)\n'
                      '                                  or __import__("xa_build").xa_ok(m, UJ1) or '
                      '__import__("xa_build").test_ok(m))]   # BTE-1 / XA-1: exact\n'
                      '    check("UD-07 vs a6a275c only the USDJPY Visual / Strategy and their build / test change '
                      '(Engine, other symbols, shared "\n',
                      '    mod = [m for m in mod if not (__import__("bte_build").bte_pine_ok(m, UJ1) or '
                      '__import__("bte_build").test_ok(m)\n'
                      '                                  or __import__("xa_build").xa_ok(m, UJ1) or '
                      '__import__("xa_build").test_ok(m)\n'
                      '                                  or __import__("cad_adapt").ok(m, UJ1))]   # BTE-1 / XA-1 / '
                      'CAD-1: exact\n'
                      '    check("UD-07 vs a6a275c only the USDJPY Visual / Strategy and their build / test change '
                      '(Engine, other symbols, shared "\n')],
 'tests/ujl_sim.py': [('    mod -= {"tests/__pycache__/"}\n'
                       '    allowed = {ub.STR_PATH, "tests/uj_build.py", "tests/uj_sim.py", "tests/ujl_sim.py", '
                       '"tests/uj3_adapt.py", "tests/bte_sim.py",\n',
                       '    mod -= {"tests/__pycache__/"}\n'
                       '    mod = {m for m in mod if not __import__("cad_adapt").ok(m, PREV)}     # CAD-1 '
                       '(confirmed-alert dedup): exact\n'
                       '    allowed = {ub.STR_PATH, "tests/uj_build.py", "tests/uj_sim.py", "tests/ujl_sim.py", '
                       '"tests/uj3_adapt.py", "tests/bte_sim.py",\n'),
                      ('          "fixtures) change; the USDJPY Visual / Engine and every other Pine file '
                       'byte-identical",\n'
                       '          mod <= allowed and ub.STR_PATH in mod and not [p for p in others if rd(p) != '
                       'git("show", f"{PREV}:{p}")],\n'
                       '          str(sorted(mod - allowed)))\n',
                       '          "fixtures) change; the USDJPY Visual / Engine and every other Pine file '
                       'byte-identical",\n'
                       '          mod <= allowed and ub.STR_PATH in mod and not [p for p in others if rd(p) != '
                       'git("show", f"{PREV}:{p}") and not __import__("cad_adapt").ok(p, PREV)],\n'
                       '          str(sorted(mod - allowed)))\n')],
 'tests/ujt_sim.py': [('    mod -= {"tests/__pycache__/"}\n    recs_ok = []\n',
                       '    mod -= {"tests/__pycache__/"}\n'
                       '    mod = {m for m in mod if not __import__("cad_adapt").ok(m, UJ3)}     # CAD-1 '
                       '(confirmed-alert dedup): exact\n'
                       '    recs_ok = []\n'),
                      ('        path = key.split(" ")[0]\n'
                       '        old, new = git("show", f"{UJ3}:{path}"), rd(path)\n'
                       '        if "(code before ADAPT)" in key:\n',
                       '        path = key.split(" ")[0]\n'
                       '        old, new = git("show", f"{UJ3}:{path}"), __import__("cad_adapt").unadapt(path, '
                       'rd(path))   # CAD-1 edits reverted first\n'
                       '        if "(code before ADAPT)" in key:\n'),
                      ('          "file byte-identical", mod <= {ub.STR_PATH, "tests/uj_build.py", '
                       '"tests/uj3_adapt.py", "tests/ujl_sim.py", "tests/ujt_sim.py"}\n'
                       '          and ub.STR_PATH in mod and all(recs_ok) and not [p for p in others if rd(p) != '
                       'git("show", f"{UJ3}:{p}")],\n'
                       '          str((sorted(mod), recs_ok)))\n',
                       '          "file byte-identical", mod <= {ub.STR_PATH, "tests/uj_build.py", '
                       '"tests/uj3_adapt.py", "tests/ujl_sim.py", "tests/ujt_sim.py"}\n'
                       '          and ub.STR_PATH in mod and all(recs_ok) and not [p for p in others if rd(p) != '
                       'git("show", f"{UJ3}:{p}") and not __import__("cad_adapt").ok(p, UJ3)],\n'
                       '          str((sorted(mod), recs_ok)))\n')],
 'tests/xa_build.py': [('    """a test / generator file with its XA-1 edits reverted (unchanged for files not in '
                        'TEST_ADAPT)."""\n'
                        '    out = __import__("uj3_adapt").unadapt(path, text)     # UJ-3 edits (later) are reverted '
                        'first\n'
                        '    for a, b in reversed(TEST_ADAPT.get(path, [])):\n',
                        '    """a test / generator file with its XA-1 edits reverted (unchanged for files not in '
                        'TEST_ADAPT)."""\n'
                        '    out = __import__("uj3_adapt").unadapt(path, __import__("cad_adapt").unadapt(path, '
                        'text))     # CAD-1, then UJ-3 edits (later) are reverted first\n'
                        '    for a, b in reversed(TEST_ADAPT.get(path, [])):\n')],
 'tests/xa_sim.py': [('    mod = git("diff", "--name-only", "--diff-filter=MDR", xb.BASE_REV, "--").split()\n'
                      '    rest = [m for m in mod if not (xb.xa_ok(m, xb.BASE_REV) or xb.test_ok(m) or '
                      '__import__("uj3_adapt").pine_ok(m, xb.BASE_REV))]   # UJ-3: exact\n'
                      '    check("XS-07 vs f253890: ZONE-P / ZONE-ST differ exactly by XA-1 (+ XA-2 on ZONE-ST); '
                      'every other changed file is a test / generator whose edits "\n',
                      '    mod = git("diff", "--name-only", "--diff-filter=MDR", xb.BASE_REV, "--").split()\n'
                      '    rest = [m for m in mod if not (xb.xa_ok(m, xb.BASE_REV) or xb.test_ok(m) or '
                      '__import__("uj3_adapt").pine_ok(m, xb.BASE_REV)\n'
                      '                                   or __import__("cad_adapt").ok(m, xb.BASE_REV))]   # UJ-3 / '
                      'CAD-1: exact\n'
                      '    check("XS-07 vs f253890: ZONE-P / ZONE-ST differ exactly by XA-1 (+ XA-2 on ZONE-ST); '
                      'every other changed file is a test / generator whose edits "\n'),
                     ('          set(xb.XA_FILES) <= set(mod) and not rest and not [m for m in mod if '
                      'm.endswith(".pine") and m not in xb.XA_FILES\n'
                      '                                                           and not '
                      '__import__("uj3_adapt").pine_ok(m, xb.BASE_REV)],\n'
                      '          str(rest))\n',
                      '          set(xb.XA_FILES) <= set(mod) and not rest and not [m for m in mod if '
                      'm.endswith(".pine") and m not in xb.XA_FILES\n'
                      '                                                           and not '
                      '__import__("uj3_adapt").pine_ok(m, xb.BASE_REV)\n'
                      '                                                           and not '
                      '__import__("cad_adapt").ok(m, xb.BASE_REV)],\n'
                      '          str(rest))\n'),
                     ('          and re.findall(r"^import .*$", S2, re.M) == ["import '
                      'sekine3310/ZoneEnginePractical/6 as zn"])\n'
                      '    mod = [m for m in git("diff", "--name-only", XA1_REV, "--").split() if not '
                      '__import__("uj3_adapt").ok(m, XA1_REV)]   # UJ-3: exact\n'
                      '    check("XQ-07 vs 2732772: only ZoneStrategyXAU.pine, ZoneVisualPractical.pine (exactly '
                      'XA-3) and tests/xa_build.py / "\n',
                      '          and re.findall(r"^import .*$", S2, re.M) == ["import '
                      'sekine3310/ZoneEnginePractical/6 as zn"])\n'
                      '    mod = [m for m in git("diff", "--name-only", XA1_REV, "--").split() if not '
                      '__import__("uj3_adapt").ok(m, XA1_REV)\n'
                      '           and not __import__("cad_adapt").ok(m, XA1_REV)]   # UJ-3 / CAD-1: exact\n'
                      '    check("XQ-07 vs 2732772: only ZoneStrategyXAU.pine, ZoneVisualPractical.pine (exactly '
                      'XA-3) and tests/xa_build.py / "\n'),
                     ('          and "Flip 5 USD" in hdr and "SL Buffer 1.5" in SF[:SF.index("//@version=5")])\n'
                      '    mod = [m for m in git("diff", "--name-only", XA2_REV, "--").split() if not '
                      '__import__("uj3_adapt").ok(m, XA2_REV)]   # UJ-3: exact\n'
                      '    check("XT-07 vs 69e6f0c: only the two Gold Pine files (exactly XA-3) and '
                      'tests/xa_build.py / xa_sim.py change; other "\n',
                      '          and "Flip 5 USD" in hdr and "SL Buffer 1.5" in SF[:SF.index("//@version=5")])\n'
                      '    mod = [m for m in git("diff", "--name-only", XA2_REV, "--").split() if not '
                      '__import__("uj3_adapt").ok(m, XA2_REV)\n'
                      '           and not __import__("cad_adapt").ok(m, XA2_REV)]   # UJ-3 / CAD-1: exact\n'
                      '    check("XT-07 vs 69e6f0c: only the two Gold Pine files (exactly XA-3) and '
                      'tests/xa_build.py / xa_sim.py change; other "\n')],
 'tests/xae_sim.py': [('    mod -= {"tests/__pycache__/"}\n'
                       '    mod = {m for m in mod if not __import__("uj3_adapt").ok(m, PREV)}     # UJ-3 (USDJPY '
                       'labels): exact\n'
                       '    allowed = {xb.VIS_PATH, xb.STR_PATH, xb.ENG_PATH, "tests/xa_build.py", '
                       '"tests/xa_sim.py", "tests/xae_sim.py"}\n',
                       '    mod -= {"tests/__pycache__/"}\n'
                       '    mod = {m for m in mod if not __import__("uj3_adapt").ok(m, PREV) and not '
                       '__import__("cad_adapt").ok(m, PREV)}     # UJ-3 / CAD-1: exact\n'
                       '    allowed = {xb.VIS_PATH, xb.STR_PATH, xb.ENG_PATH, "tests/xa_build.py", '
                       '"tests/xa_sim.py", "tests/xae_sim.py"}\n'),
                      ('          mod <= allowed and {xb.VIS_PATH, xb.STR_PATH, xb.ENG_PATH} <= mod\n'
                       '          and not [p for p in others if rd(p) != xb.show(PREV, p) and not '
                       '__import__("uj3_adapt").pine_ok(p, PREV)], str(sorted(mod - allowed)))\n'
                       '    hdr = V[:V.index("//@version=5")] + S[:S.index("//@version=5")]\n',
                       '          mod <= allowed and {xb.VIS_PATH, xb.STR_PATH, xb.ENG_PATH} <= mod\n'
                       '          and not [p for p in others if rd(p) != xb.show(PREV, p) and not '
                       '__import__("uj3_adapt").pine_ok(p, PREV) and not __import__("cad_adapt").ok(p, PREV)], '
                       'str(sorted(mod - allowed)))\n'
                       '    hdr = V[:V.index("//@version=5")] + S[:S.index("//@version=5")]\n')]}
