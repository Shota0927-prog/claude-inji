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
LATER records the exact edits of the later XA-5 layer (Gold adopted defaults, against a33d2b0) to these generators /
fixtures; unadapt() reverts them first, and later_pine_ok() accepts the Gold Visual / Strategy when they differ from a
revision exactly by XA-5, so the CAD-1 checks keep pinning their own layer.
"""
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NEW_FILES = ("tests/cad_build.py", "tests/cad_adapt.py", "tests/cad_sim.py")
_rd = lambda p: open(os.path.join(ROOT, p), encoding="utf-8").read()


def _show(rev, path):
    return subprocess.run(["git", "-C", ROOT, "show", f"{rev}:{path}"], capture_output=True, text=True).stdout


def later_unadapt(path, text):
    """the text with the edits of the layers after CAD-1 (LATER: XA-5) reverted, all or nothing per file."""
    pairs = LATER.get(path, [])
    if text is None or not pairs or all(text.count(b) == 0 for _, b in pairs):
        return text
    out = text
    for a, b in reversed(pairs):
        if out.count(b) != 1:
            return None
        out = out.replace(b, a)
    return out


def later_pine_ok(path, rev):
    """True for the Gold Visual / Strategy when they differ from `rev` exactly by XA-5 (xa_build.strip_*5)."""
    import xa_build as xb
    strip = {xb.VIS_PATH: xb.strip_visual5, xb.STR_PATH: xb.strip_strategy5}.get(path)
    if strip is None:
        return False
    s = strip(_rd(path))
    return s is not None and s == _show(rev, path)


def unadapt(path, text):
    """the text with the later layers' (XA-5) and its CAD-1 edits reverted; unchanged when none is present; None when
    only some are present."""
    text = later_unadapt(path, text)
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
    if pine_ok(path, rev) or later_pine_ok(path, rev):
        return True
    if path in LATER and path not in ADAPT and os.path.exists(os.path.join(ROOT, path)):
        u = later_unadapt(path, _rd(path))
        return u is not None and u != _rd(path) and u == _show(rev, path)
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

LATER = {'tests/cad_sim.py': [('    others = [p for p in os.listdir(ROOT) if p.endswith(".pine") and p not in cb.FILES]\n'
                       '    changed = [p for p in others if rd(p) != git("show", f"{PREV}:{p}")]\n'
                       '    cls = {"ZoneStrategyXAU.pine": "alert(" not in code_only(rd("ZoneStrategyXAU.pine")),\n',
                       '    others = [p for p in os.listdir(ROOT) if p.endswith(".pine") and p not in cb.FILES]\n'
                       '    changed = [p for p in others if rd(p) != git("show", f"{PREV}:{p}") and not '
                       '__import__("cad_adapt").later_pine_ok(p, PREV)]   # later layers: exact\n'
                       '    cls = {"ZoneStrategyXAU.pine": "alert(" not in code_only(rd("ZoneStrategyXAU.pine")),\n'),
                      ('          "in CAD-1 or carries exactly its recorded CAD-1 edits (cad_adapt: reverting them '
                       'gives the 867ff7e text)",\n'
                       '          pine == set(cb.FILES) and all(m in rec.NEW_FILES or rec.unadapt(m, rd(m)) == '
                       'git("show", f"{PREV}:{m}") for m in mod - pine),\n'
                       '          str(sorted(m for m in mod - pine if not (m in rec.NEW_FILES or rec.unadapt(m, '
                       'rd(m)) == git("show", f"{PREV}:{m}")))))\n',
                       '          "in CAD-1 or carries exactly its recorded CAD-1 edits (cad_adapt: reverting them '
                       'gives the 867ff7e text)",\n'
                       '          pine - {m for m in pine if __import__("cad_adapt").later_pine_ok(m, PREV)} == '
                       'set(cb.FILES) and all(m in rec.NEW_FILES or rec.unadapt(m, rd(m)) == git("show", '
                       'f"{PREV}:{m}") for m in mod - pine),\n'
                       '          str(sorted(m for m in mod - pine if not (m in rec.NEW_FILES or rec.unadapt(m, '
                       'rd(m)) == git("show", f"{PREV}:{m}")))))\n')],
 'tests/xa_build.py': [('\n'
                        '# ---- XA-2: position size (Strategy only; applied after XA-1) '
                        '-----------------------------------------------------------\n',
                        '\n'
                        '# ---- XA-5: Gold Short adopted defaults (Day/Swing Merge Nearby, breakeven ON / 15; after '
                        'XA-4) ---------------------------\n'
                        '#  Defaults and the matching descriptions only: Day/Swing Overlap Mode Separate -> Merge '
                        'Nearby (both files; Merge Distance\n'
                        '#  stays 0 = only an identical day high / low and Swing price merge, by the existing Engine '
                        'condition); Strategy Breakeven\n'
                        '#  Stop OFF -> ON, Trigger 10 -> 15 USD. The dsDist tooltip and the header lines that '
                        'described the old defaults are updated.\n'
                        '#  Engine / import, logic, sizing, every other input unchanged. strip_*5() -> the a33d2b0 '
                        '(= 7363ef1) files byte for byte.\n'
                        'NOTE5 = "Gold Short の比較から採用した初期値・検証継続中 (年別確認・Long での検証・将来の有効性は未確認)"\n'
                        'HDR5 = ("//  XA-5: " + NOTE5 + ":\\n"\n'
                        '        "//  Day/Swing Overlap Mode Merge Nearby・Merge Distance 0 USD (同じ価格の当日高値 / 安値と '
                        'Swing High / Low を、既存の統合条件で\\n"\n'
                        '        "//  1 つの根拠として数える)")\n'
                        'ZONE_EDITS5 = [\n'
                        '    ("default",\n'
                        '     \'dsMode = input.string("Separate", "Day/Swing Overlap Mode", options = ["Separate", '
                        '"Merge Nearby"], group = G_DHL,\\n\',\n'
                        '     \'dsMode = input.string("Merge Nearby", "Day/Swing Overlap Mode", options = '
                        '["Separate", "Merge Nearby"], group = G_DHL,\\n\'),\n'
                        '    ("text",\n'
                        '     \'     "初期 0 は Merge Nearby の採用値ではない: 初期の Separate では使われず、結果に作用しない。")\\n\',\n'
                        '     \'     "初期 0 (Gold Short の比較から採用した初期値・検証継続中): 初期の Merge Nearby で、同じ価格の当日高値と Swing '
                        'High\\\\n" +\\n\'\n'
                        '     \'     "(安値と Swing Low) だけを 1 つの根拠にする。")\\n\'),\n'
                        '    ("text",\n'
                        '     "//  追加入力: Accum Score Sum・Accum Edge Separate・Day/Swing Separate (Merge Distance 0 は '
                        'Separate では作用しない)・\\n",\n'
                        '     "//  追加入力: Accum Score Sum・Accum Edge Separate・Day/Swing (XA-5 で Merge Nearby・Merge '
                        'Distance 0 に変更)・\\n"),\n'
                        ']\n'
                        'VISUAL_EDITS5 = [\n'
                        '    ("header",\n'
                        '     "//  Visual のみ: Label に統合後 Zone の上下限 / 幅 (USD) を表示 (初期 ON、表示だけ)。\\n",\n'
                        '     "//  Visual のみ: Label に統合後 Zone の上下限 / 幅 (USD) を表示 (初期 ON、表示だけ)。\\n" + HDR5 + '
                        '"。\\n"),\n'
                        '] + ZONE_EDITS5\n'
                        'STRATEGY_EDITS5 = [\n'
                        '    ("header",\n'
                        '     "//  資金管理 (XA-2)・売買 / 取消 / TP / 建値の処理とタイミング・XA-3 の採用初期値は変更なし。\\n",\n'
                        '     "//  資金管理 (XA-2)・売買 / 取消 / TP / 建値の処理とタイミング・XA-3 の採用初期値は変更なし。\\n" + HDR5 + "、\\n"\n'
                        '     "//  建値移動 ON・Trigger 15 USD。Zone 生成・採点・統合条件・Entry・数量・注文 / 取消 / TP / '
                        '建値の判定と処理順は変えない。\\n"),\n'
                        '    ("text",\n'
                        '     "//  Entry C: Candle Pattern、Short Only、SL Buffer 1.5、固定 RR 1.5、反対側 Zone TP OFF、建値移動 '
                        'OFF (Trigger は現行値のまま)。\\n",\n'
                        '     "//  Entry C: Candle Pattern、Short Only、SL Buffer 1.5、固定 RR 1.5、反対側 Zone TP OFF、建値移動 '
                        '(XA-5 で ON・Trigger 15 に変更)。\\n"),\n'
                        '] + ZONE_EDITS5 + [\n'
                        '    ("default",\n'
                        '     \'stBE = input.bool(false, "Breakeven Stop", group = G_STT)\\n\',\n'
                        '     \'stBE = input.bool(true, "Breakeven Stop", group = G_STT)\\n\'),\n'
                        '    ("default",\n'
                        '     \'stBEDist = input.float(10.0, "Breakeven Trigger ($)", minval = 0.0, step = 0.5, '
                        "group = G_STT)\\n',\n"
                        '     \'stBEDist = input.float(15.0, "Breakeven Trigger ($)", minval = 0.0, step = 0.5, '
                        "group = G_STT)\\n'),\n"
                        ']\n'
                        '\n'
                        '\n'
                        '# ---- XA-2: position size (Strategy only; applied after XA-1) '
                        '-----------------------------------------------------------\n'),
                       ('\ndef build_visual():\n',
                        '\n'
                        'def build_visual4():\n'
                        '    """XA-1 + XA-3 + XA-4 (commit 7363ef1)."""\n'
                        '    return _apply(build_visual3(), VISUAL_EDITS4)\n'
                        '\n'
                        '\n'
                        'def build_visual():\n'),
                       ('def build_visual():\n    return _apply(build_visual3(), VISUAL_EDITS4)\n\n',
                        'def build_visual():\n    return _apply(build_visual4(), VISUAL_EDITS5)\n\n'),
                       ('\ndef build_strategy():\n',
                        '\n'
                        'def build_strategy4():\n'
                        '    """XA-1 .. XA-4 (commit 7363ef1)."""\n'
                        '    return _apply(build_strategy3(), STRATEGY_EDITS4)\n'
                        '\n'
                        '\n'
                        'def build_strategy():\n'),
                       ('def build_strategy():\n    return _apply(build_strategy3(), STRATEGY_EDITS4)\n\n',
                        'def build_strategy():\n    return _apply(build_strategy4(), STRATEGY_EDITS5)\n\n'),
                       ('\ndef strip_visual4(t):\n',
                        '\n'
                        'def strip_visual5(t):\n'
                        '    """reverse only XA-5 (-> the Visual of 7363ef1 / a33d2b0 byte for byte)."""\n'
                        '    return _revert(t, VISUAL_EDITS5)\n'
                        '\n'
                        '\n'
                        'def strip_strategy5(t):\n'
                        '    """reverse only XA-5 (-> the Strategy of 7363ef1 / a33d2b0 byte for byte)."""\n'
                        '    return _revert(t, STRATEGY_EDITS5)\n'
                        '\n'
                        '\n'
                        'def strip_visual4(t):\n'),
                       ('def strip_visual4(t):\n'
                        '    """reverse only XA-4 (-> the Visual of 17d1ca2 byte for byte)."""\n'
                        '    return _revert(t, VISUAL_EDITS4)\n',
                        'def strip_visual4(t):\n'
                        '    """reverse XA-5 when present (all or nothing) and XA-4 (-> the Visual of 17d1ca2 byte '
                        'for byte)."""\n'
                        '    if t is not None and VISUAL_EDITS5[0][2] in t:\n'
                        '        t = strip_visual5(t)\n'
                        '    return _revert(t, VISUAL_EDITS4)\n'),
                       ('def strip_strategy4(t):\n'
                        '    """reverse only XA-4 (-> the Strategy of 17d1ca2 byte for byte)."""\n'
                        '    return _revert(t, STRATEGY_EDITS4)\n',
                        'def strip_strategy4(t):\n'
                        '    """reverse XA-5 when present (all or nothing) and XA-4 (-> the Strategy of 17d1ca2 byte '
                        'for byte)."""\n'
                        '    if t is not None and STRATEGY_EDITS5[0][2] in t:\n'
                        '        t = strip_strategy5(t)\n'
                        '    return _revert(t, STRATEGY_EDITS4)\n')],
 'tests/xae_sim.py': [('  XU : mutations — mirror and source mutations are caught\n\n',
                       '  XU : mutations — mirror and source mutations are caught\n'
                       '  XF : XA-5 — Gold Short adopted defaults (Day/Swing Merge Nearby, Merge Distance 0; '
                       'Strategy breakeven ON / Trigger 15) on\n'
                       '       the delivered files; XE / XM / XU run on the XA-4 layer (the files with exactly the '
                       'XA-5 edits reverted == 7363ef1)\n'
                       '\n'),
                      ('E, GBE, SW6 = rd(xb.ENG_PATH), rd(ge.GBE_PATH), rd(ge.SRC_PATH)\n'
                       'V, S = rd(xb.VIS_PATH), rd(xb.STR_PATH)\n'
                       'V0, S0 = xb.show(PREV, xb.VIS_PATH), xb.show(PREV, xb.STR_PATH)\n',
                       'E, GBE, SW6 = rd(xb.ENG_PATH), rd(ge.GBE_PATH), rd(ge.SRC_PATH)\n'
                       'V, S = xb.strip_visual5(rd(xb.VIS_PATH)) or "", xb.strip_strategy5(rd(xb.STR_PATH)) or ""   '
                       '# XA-4 layer (XA-5 reverted exactly; pinned by XF)\n'
                       'V0, S0 = xb.show(PREV, xb.VIS_PATH), xb.show(PREV, xb.STR_PATH)\n'),
                      ('    check("XE-04 Visual / Strategy == 17d1ca2 + the XA-4 edits (rebuild identical) and strip '
                       'back to 17d1ca2 byte for byte; "\n'
                       '          "the full chain strips to f253890", xb.build_visual() == V and xb.build_strategy() '
                       '== S\n'
                       '          and xb.strip_visual4(V) == V0 and xb.strip_strategy4(S) == S0\n',
                       '    check("XE-04 Visual / Strategy == 17d1ca2 + the XA-4 edits (rebuild identical) and strip '
                       'back to 17d1ca2 byte for byte; "\n'
                       '          "the full chain strips to f253890", xb.build_visual4() == V and '
                       'xb.build_strategy4() == S\n'
                       '          and xb.strip_visual4(V) == V0 and xb.strip_strategy4(S) == S0\n'),
                      ('          and xb.strip_visual4(V) == V0 and xb.strip_strategy4(S) == S0\n'
                       '          and xb.strip_visual(V) == xb.show(xb.BASE_REV, xb.VIS_PATH) and '
                       'xb.strip_strategy(S) == xb.show(xb.BASE_REV, xb.STR_PATH)\n'
                       '          and {k for k, _, _ in xb.VISUAL_EDITS4} == {"header", "import", "dsmode", '
                       '"accmode", "rn", "fvg", "fvgdir", "display"}\n',
                       '          and xb.strip_visual4(V) == V0 and xb.strip_strategy4(S) == S0\n'
                       '          and xb.strip_visual(rd(xb.VIS_PATH)) == xb.show(xb.BASE_REV, xb.VIS_PATH) and '
                       'xb.strip_strategy(rd(xb.STR_PATH)) == xb.show(xb.BASE_REV, xb.STR_PATH)\n'
                       '          and {k for k, _, _ in xb.VISUAL_EDITS4} == {"header", "import", "dsmode", '
                       '"accmode", "rn", "fvg", "fvgdir", "display"}\n'),
                      ('\ndef gate_mutation():\n',
                       '\n'
                       'def gate_xa5():\n'
                       '    V5, S5 = rd(xb.VIS_PATH), rd(xb.STR_PATH)\n'
                       '    A = "a33d2b0"\n'
                       '    VA, SA = xb.show(A, xb.VIS_PATH), xb.show(A, xb.STR_PATH)\n'
                       '    check("XF-01 XA-5: Visual / Strategy == the a33d2b0 files (= 7363ef1) + the XA-5 edits '
                       '(rebuild identical) and strip back "\n'
                       '          "byte for byte; edit kinds header / text / default only",\n'
                       '          xb.build_visual() == V5 and xb.build_strategy() == S5 and xb.strip_visual5(V5) == '
                       'VA and xb.strip_strategy5(S5) == SA\n'
                       '          and VA == xb.show("7363ef1", xb.VIS_PATH) and SA == xb.show("7363ef1", '
                       'xb.STR_PATH)\n'
                       '          and {k for k, _, _ in xb.VISUAL_EDITS5 + xb.STRATEGY_EDITS5} <= {"header", "text", '
                       '"default"})\n'
                       '    cv = sorted(l for l in es.changed_code(VA, V5) if l)\n'
                       '    cs = sorted(l for l in es.changed_code(SA, S5) if l)\n'
                       '    ds_old = \'dsMode = input.string("Separate", "Day/Swing Overlap Mode", options = '
                       '["Separate", "Merge Nearby"], group = G_DHL,\'\n'
                       '    ds_new = \'dsMode = input.string("Merge Nearby", "Day/Swing Overlap Mode", options = '
                       '["Separate", "Merge Nearby"], group = G_DHL,\'\n'
                       '    tip = [\'"初期 0 は Merge Nearby の採用値ではない: 初期の Separate では使われず、結果に作用しない。")\',\n'
                       '           \'"初期 0 (Gold Short の比較から採用した初期値・検証継続中): 初期の Merge Nearby で、同じ価格の当日高値と Swing '
                       'High\\\\n" +\',\n'
                       '           \'"(安値と Swing Low) だけを 1 つの根拠にする。")\']\n'
                       '    be = [\'stBE = input.bool(false, "Breakeven Stop", group = G_STT)\', \'stBE = '
                       'input.bool(true, "Breakeven Stop", group = G_STT)\',\n'
                       '          \'stBEDist = input.float(10.0, "Breakeven Trigger ($)", minval = 0.0, step = 0.5, '
                       "group = G_STT)',\n"
                       '          \'stBEDist = input.float(15.0, "Breakeven Trigger ($)", minval = 0.0, step = 0.5, '
                       "group = G_STT)']\n"
                       '    check("XF-02 code delta vs a33d2b0 exactly: Day/Swing Overlap Mode default (both files) '
                       '+ the Merge Distance tooltip text "\n'
                       '          "(both); Strategy Breakeven Stop false -> true and Trigger 10 -> 15; nothing '
                       'else",\n'
                       '          cv == sorted([ds_old, ds_new] + tip) and cs == sorted([ds_old, ds_new] + tip + '
                       'be), str((cv, cs)))\n'
                       '    vv, vs = input_values(V5), input_values(S5)\n'
                       '    zone_exp = dict(XA3, **dict(NEW_ZONE, dsMode=\'"Merge Nearby"\', dsDist="0.0"))\n'
                       '    st_exp = dict(XA3_ST, stBE="true", stBEDist="15.0")\n'
                       '    zb = [n for n, x in zone_exp.items() if vv.get(n) != x or vs.get(n) != x]\n'
                       '    sb = [n for n, x in st_exp.items() if vs.get(n) != x]\n'
                       '    vd, sd = input_decls(V5), input_decls(S5)\n'
                       '    zone_names = set(input_decls(S5[:S5.index("// ==== ZONE Strategy · Zone evaluation '
                       '(begin)")])) | {"fvgMinWidth", "fvgDirMatch"}\n'
                       '    check("XF-03 adopted defaults: Day/Swing Merge Nearby, Merge Distance 0 (both); '
                       'Breakeven ON, Trigger 15 (Strategy); every "\n'
                       '          "kept value (HW 6, Cluster 5, Break 10, Flip 5, 5 / 10 / 15, MA 3 / 3, Slope 1 / '
                       '3, 0 / 1 / 2, Max, Day H/L 3, Accum "\n'
                       '          "3 / 4 / 5 Sum Separate, Swing 1 / 2 / 3, Confluence 1 / 2 / 3, FVG 3.0 / OFF, RN '
                       'ON 100 +3 / 50 +2, C, Short Only, SL "\n'
                       '          "Buffer 1.5, RR 1.5, Zone TP OFF, sizing 300,000 / 3 % / 100 oz / 0.01 / 0.01); '
                       'Visual / Strategy Zone inputs and "\n'
                       '          "ZoneCfg identical; the Visual has no Strategy input",\n'
                       '          not zb and not sb and all(vd.get(n) == sd.get(n) for n in zone_names)\n'
                       '          and re.findall(r"^zoneCfg\\.\\w+\\s*:=.*$", V5, re.M) == '
                       're.findall(r"^zoneCfg\\.\\w+\\s*:=.*$", S5, re.M)\n'
                       '          and not [n for n in vd if n.startswith("st")], str((zb, sb)))\n'
                       '    vda, sda = input_decls(VA), input_decls(SA)\n'
                       '    chg = {"dsMode", "dsDist", "stBE", "stBEDist"}\n'
                       '    req = lambda t: re.findall(r"request\\.\\w+\\(", code_only(t))\n'
                       '    norm = lambda t: code_only(t).replace(ds_new, ds_old).replace(be[1], '
                       'be[0]).replace(be[3], be[2])\n'
                       '    check("XF-04 everything else unchanged vs a33d2b0: every other input declaration, the '
                       'Engine file and import "\n'
                       '          "ZoneEnginePracticalXAUUSD/1, f_stQty and both qty = pQty entries, strategy() '
                       'options, the Zone / FVG / Entry / order "\n'
                       '          "/ cancel / TP / breakeven code (code identical apart from the three default lines '
                       'and the tooltip), requests",\n'
                       '          not [n for n in vda if n not in chg and vda[n] != vd.get(n)] and not [n for n in '
                       'sda if n not in chg and sda[n] != sd.get(n)]\n'
                       '          and set(vda) == set(vd) and set(sda) == set(sd) and rd(xb.ENG_PATH) == xb.show(A, '
                       'xb.ENG_PATH)\n'
                       '          and re.findall(r"^import .*$", V5 + S5, re.M) == [xb.IMPORT_XAE.strip()] * 2\n'
                       '          and func(S5, QTY_FN) == func(SA, QTY_FN) and S5.count("qty = pQty") == 2\n'
                       '          and seg(S5, "strategy(", "import ") == seg(SA, "strategy(", "import ")\n'
                       '          and [l for l in norm(S5).split("\\n") if not l.lstrip().startswith(\'"\')] == [l '
                       'for l in code_only(SA).split("\\n") if not l.lstrip().startswith(\'"\')]\n'
                       '          and [l for l in norm(V5).split("\\n") if not l.lstrip().startswith(\'"\')] == [l '
                       'for l in code_only(VA).split("\\n") if not l.lstrip().startswith(\'"\')]\n'
                       '          and req(V5) == req(VA) and req(S5) == req(SA))\n'
                       '    hdr = V5[:V5.index("//@version=5")] + S5[:S5.index("//@version=5")]\n'
                       '    tipv = vd["dsDist"] + sd["dsDist"]\n'
                       '    check("XF-05 descriptions: \'Gold Short の比較から採用した初期値・検証継続中\' (year-by-year / Long / '
                       'future validity not "\n'
                       '          "confirmed) in both headers; the Merge Distance tooltip no longer says it is inert '
                       '/ not adopted; no \'Day/Swing "\n'
                       '          "Separate\' / \'Merge Distance 0 は Separate では作用しない\' / \'建値移動 OFF\' left; no '
                       'optimisation / completion claim",\n'
                       '          hdr.count(xb.NOTE5) == 2 and "作用しない" not in tipv and "採用値ではない" not in tipv and '
                       '"初期の Merge Nearby" in vd["dsDist"]\n'
                       '          and "Merge Distance 0 は Separate では作用しない" not in hdr and "Day/Swing Separate" not '
                       'in hdr\n'
                       '          and "建値移動 OFF" not in hdr and "建値移動 ON・Trigger 15 USD" in hdr\n'
                       '          and not re.search(r"最適値です|最適化済み|検証完了|将来も有効|年別確認済み|Long でも検証済み", hdr))\n'
                       '    m0 = finalize([DH(2700.0), SWH("60", 2700.0)], merge=True, dist=0.0)\n'
                       '    m1 = finalize([DH(2700.0), SWH("60", 2700.001)], merge=True, dist=0.0)\n'
                       '    check("XF-06 Merge Nearby with distance 0 (model of the unchanged Engine condition): Day '
                       'High 2700.000 + 1H Swing High "\n'
                       '          "2700.000 -> one evidence (3 points, 1 category); 0.001 apart -> both counted (6 + '
                       '1, 2 categories)",\n'
                       '          (m0["score"], m0["cat"]) == (3.0, 1) and (m1["score"], m1["cat"]) == (7.0, 2))\n'
                       '    st = git("status", "--porcelain").split("\\n")\n'
                       '    mod = set(git("diff", "--name-only", A, "--").split()) | {l[3:] for l in st if '
                       'l.startswith("??")}\n'
                       '    mod -= {"tests/__pycache__/"}\n'
                       '    others = [p for p in os.listdir(ROOT) if p.endswith(".pine") and p not in (xb.VIS_PATH, '
                       'xb.STR_PATH)]\n'
                       '    check("XF-07 vs a33d2b0 only the Gold Visual / Strategy, xa_build, xae_sim, cad_sim and '
                       'cad_adapt change; every other Pine "\n'
                       '          "file (Engines incl. ZoneEnginePracticalXAUUSD, other symbols) byte-identical",\n'
                       '          mod <= {xb.VIS_PATH, xb.STR_PATH, "tests/xa_build.py", "tests/xae_sim.py", '
                       '"tests/cad_sim.py", "tests/cad_adapt.py"}\n'
                       '          and {xb.VIS_PATH, xb.STR_PATH} <= mod and not [p for p in others if rd(p) != '
                       'git("show", f"{A}:{p}")], str(sorted(mod)))\n'
                       '    muts = [V5.replace(ds_new, ds_old), S5.replace(be[1], be[0]), S5.replace(be[3], be[2]),\n'
                       "            V5.replace('dsDist = input.float(0.0,', 'dsDist = input.float(0.5,')]\n"
                       '    check("XF-08 mutations do not strip back to a33d2b0: Day/Swing back to Separate, '
                       'Breakeven OFF, Trigger 10, Merge Distance 0.5",\n'
                       '          all(m != t and f(m) != base for m, t, f, base in zip(muts, [V5, S5, S5, V5],\n'
                       '                                                                 [xb.strip_visual5, '
                       'xb.strip_strategy5, xb.strip_strategy5, xb.strip_visual5],\n'
                       '                                                                 [VA, SA, SA, VA])))\n'
                       '\n'
                       '\n'
                       'def gate_mutation():\n'),
                      ('def main():\n    for g in (gate_static, gate_model, gate_mutation):\n        try:\n',
                       'def main():\n'
                       '    for g in (gate_static, gate_model, gate_mutation, gate_xa5):\n'
                       '        try:\n')]}
