"""ACC-1 / ACC-2 — the new Accum Strategy XAU files and their exact registration in the older fixtures.

ACC-1 / ACC-2 add files only (no existing Strategy / Engine / Visual / harness changes):
  AccumStrategyXAU.pine, ACCUM_STRATEGY_XAU_ja.md, tests/acc_pine.py, tests/acc_sim.py, tests/acc_build.py (this file) and
  tests/.gitignore (`__pycache__/`, same rule as automation/xau_short/receiver/.gitignore and bridge/.gitignore).
The older fixtures' "every other file unchanged" checks accept these files only through ok() / NEW_FILES (TEST_EDITS below:
one clause per check, nothing else). The heads of the older unadapt() chains (eua_build.unadapt, cad_adapt.later_unadapt) revert these
edits first, exactly, so every older "test file changed by exactly its recorded edit" check still compares the old text.
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PINE_PATH = "AccumStrategyXAU.pine"
NEW_FILES = ("AccumStrategyXAU.pine", "ACCUM_STRATEGY_XAU_ja.md", "tests/acc_pine.py", "tests/acc_sim.py", "tests/acc_build.py",
             "tests/.gitignore")
NEW_TESTS = NEW_FILES


def ok(path):
    """ACC-1 / ACC-2 account for this path exactly: one of their new files."""
    return path in NEW_FILES


A = '__import__("acc_build")'
P_OK = f'p.endswith(".pine") and not {A}.ok(p)'
XAS_OLD = '          and not [p for p in os.listdir(ROOT) if p.endswith(".pine") and p != xb.STR_PATH and not __import__("xal_build").ok(p)\n'

# the exact edits ACC-1 / ACC-2 make to older fixtures / generators: path -> [(old, new, count)] (count = occurrences of old)
TEST_EDITS = {
    "tests/au_sim.py": [
        ('    others = [p for p in os.listdir(ROOT) if p.endswith(".pine") and p != ab.SRC_PATH]\n',
         f'    others = [p for p in os.listdir(ROOT) if {P_OK} and p != ab.SRC_PATH]     # ACC-1 new files: exact\n', 1)],
    "tests/bel_sim.py": [
        ('    others = [p for p in os.listdir(ROOT) if p.endswith(".pine") and p not in bb.FILES and p != "ZoneStrategyUSDJPY_Diagnostic.pine"]',
         f'    others = [p for p in os.listdir(ROOT) if {P_OK} and p not in bb.FILES and p != "ZoneStrategyUSDJPY_Diagnostic.pine"]', 1),
        ('                 and m not in __import__("uja_build").NEW_TESTS and m not in __import__("eua_build").NEW_TESTS\n',
         '                 and m not in __import__("uja_build").NEW_TESTS and m not in __import__("eua_build").NEW_TESTS\n'
         f'                 and m not in {A}.NEW_FILES     # ACC-1 new files\n', 1),
        ('                 and not (m in bb.TEST_EDITS and bb.unadapt(m, raw(m)) == bb.show(B, m) and bb.unadapt(m, raw(m)) != raw(m)))\n',
         '                 and not (m in bb.TEST_EDITS and bb.unadapt(m, raw(m)) == bb.show(B, m) and bb.unadapt(m, raw(m)) != raw(m))\n'
         f'                 and not (m in {A}.TEST_EDITS and {A}.unadapt(m, raw(m)) == bb.show(B, m) and {A}.unadapt(m, raw(m)) != raw(m)))     # ACC-1 test edits: exact\n', 1)],
    "tests/btl_sim.py": [
        ('    others = [p for p in os.listdir(ROOT) if p.endswith(".pine") and p != bl.PATH]\n',
         f'    others = [p for p in os.listdir(ROOT) if {P_OK} and p != bl.PATH]     # ACC-1 new files: exact\n', 1)],
    "tests/cad_sim.py": [
        ('    others = [p for p in os.listdir(ROOT) if p.endswith(".pine") and p not in cb.FILES and not __import__("xal_build").ok(p)]',
         f'    others = [p for p in os.listdir(ROOT) if {P_OK} and p not in cb.FILES and not __import__("xal_build").ok(p)]', 1),
        ('    mod = {m for m in mod if not __import__("xal_build").ok(m) and not __import__("au_build").ok(m)}',
         f'    mod = {{m for m in mod if not __import__("xal_build").ok(m) and not __import__("au_build").ok(m) and not {A}.ok(m)}}', 1),
        ('rec.unadapt(m, rd(m))', f'rec.unadapt(m, {A}.unadapt(m, rd(m)))', 2)],
    "tests/eua_sim.py": [
        ('    others = [p for p in git("ls-files", "*.pine").split() if p != gb.PATH]\n',
         f'    others = [p for p in git("ls-files", "*.pine").split() if p != gb.PATH and not {A}.ok(p)]     # ACC-1 new files: exact\n', 1),
        ('    bad = sorted(m for m in mod if m != gb.PATH and m not in gb.NEW_TESTS\n',
         f'    bad = sorted(m for m in mod if m != gb.PATH and m not in gb.NEW_TESTS and m not in {A}.NEW_FILES     # ACC-1 new files\n', 1),
        ('                 and not (m in gb.TEST_EDITS and gb.unadapt(m, raw(m)) == gb.show(B, m) and gb.unadapt(m, raw(m)) != raw(m)))\n',
         '                 and not (m in gb.TEST_EDITS and gb.unadapt(m, raw(m)) == gb.show(B, m) and gb.unadapt(m, raw(m)) != raw(m))\n'
         f'                 and not (m in {A}.TEST_EDITS and {A}.unadapt(m, raw(m)) == gb.show(B, m) and {A}.unadapt(m, raw(m)) != raw(m)))     # ACC-1 test edits: exact\n', 1)],
    "tests/gja_sim.py": [
        ('    others = [p for p in git("ls-files", "*.pine").split() if p != gb.PATH]\n',
         f'    others = [p for p in git("ls-files", "*.pine").split() if p != gb.PATH and not {A}.ok(p)]     # ACC-1 new files: exact\n', 1),
        ('                 and m not in __import__("eua_build").NEW_TESTS\n',
         f'                 and m not in __import__("eua_build").NEW_TESTS and m not in {A}.NEW_FILES     # ACC-1 new files\n', 1),
        ('__import__("uja_build").unapply(m, raw(m)) == gb.show(B, m)))     # later UJA-1 / EUA-1: exact\n',
         '__import__("uja_build").unapply(m, raw(m)) == gb.show(B, m))     # later UJA-1 / EUA-1: exact\n'
         f'                 and not (m in {A}.TEST_EDITS and {A}.unadapt(m, raw(m)) == gb.show(B, m) and {A}.unadapt(m, raw(m)) != raw(m)))     # ACC-1 test edits: exact\n', 1)],
    "tests/msl_sim.py": [
        ('    others = [p for p in os.listdir(ROOT) if p.endswith(".pine") and p not in mb.FILES]\n',
         f'    others = [p for p in os.listdir(ROOT) if {P_OK} and p not in mb.FILES]     # ACC-1 new files: exact\n', 1),
        ('                 and m not in __import__("eua_build").NEW_TESTS\n',
         f'                 and m not in __import__("eua_build").NEW_TESTS and m not in {A}.NEW_FILES     # ACC-1 new files\n', 1),
        ('                 and not (m in TEST_EDITS and revert(__import__("bel_build").unadapt(m, raw(m)), TEST_EDITS[m]) == mb.show(B, m)))\n',
         '                 and not (m in TEST_EDITS and revert(__import__("bel_build").unadapt(m, raw(m)), TEST_EDITS[m]) == mb.show(B, m))\n'
         f'                 and not (m in {A}.TEST_EDITS and {A}.unadapt(m, raw(m)) == mb.show(B, m) and {A}.unadapt(m, raw(m)) != raw(m)))     # ACC-1 test edits: exact\n', 1)],
    "tests/sx2s_sim.py": [
        ('    others = [p for p in os.listdir(ROOT) if p.endswith(".pine") and p not in s2.FILES and not __import__("xal_build").ok(p)]',
         f'    others = [p for p in os.listdir(ROOT) if {P_OK} and p not in s2.FILES and not __import__("xal_build").ok(p)]', 1)],
    "tests/sxs_sim.py": [
        ('    others = [p for p in os.listdir(ROOT) if p.endswith(".pine") and p not in sx.FILES and not __import__("xal_build").ok(p)]',
         f'    others = [p for p in os.listdir(ROOT) if {P_OK} and p not in sx.FILES and not __import__("xal_build").ok(p)]', 1)],
    "tests/uja_sim.py": [
        ('    others = [p for p in git("ls-files", "*.pine").split() if p != gb.PATH]\n',
         f'    others = [p for p in git("ls-files", "*.pine").split() if p != gb.PATH and not {A}.ok(p)]     # ACC-1 new files: exact\n', 1),
        ('    bad = sorted(m for m in mod if m != gb.PATH and m not in gb.NEW_TESTS and m not in __import__("eua_build").NEW_TESTS\n',
         '    bad = sorted(m for m in mod if m != gb.PATH and m not in gb.NEW_TESTS and m not in __import__("eua_build").NEW_TESTS\n'
         f'                 and m not in {A}.NEW_FILES     # ACC-1 new files\n', 1),
        ('                 and not (m == __import__("eua_build").PATH and __import__("eua_build").unapply(m, raw(m)) == gb.show(B, m)))     # later EUA-1: exact\n',
         '                 and not (m == __import__("eua_build").PATH and __import__("eua_build").unapply(m, raw(m)) == gb.show(B, m))     # later EUA-1: exact\n'
         f'                 and not (m in {A}.TEST_EDITS and {A}.unadapt(m, raw(m)) == gb.show(B, m) and {A}.unadapt(m, raw(m)) != raw(m)))     # ACC-1 test edits: exact\n', 1)],
    "tests/ujl_sim.py": [
        ('    mod = {m for m in mod if not __import__("cad_adapt").ok(m, PREV) and not __import__("xal_build").ok(m)}',
         f'    mod = {{m for m in mod if not __import__("cad_adapt").ok(m, PREV) and not __import__("xal_build").ok(m) and not {A}.ok(m)}}', 1),
        ('    others = [p for p in os.listdir(ROOT) if p.endswith(".pine") and p != ub.STR_PATH and not __import__("xal_build").ok(p)]\n',
         f'    others = [p for p in os.listdir(ROOT) if {P_OK} and p != ub.STR_PATH and not __import__("xal_build").ok(p)]\n', 1)],
    "tests/ujt_sim.py": [
        ('    mod = {m for m in mod if not __import__("cad_adapt").ok(m, UJ3) and not __import__("xal_build").ok(m)}',
         f'    mod = {{m for m in mod if not __import__("cad_adapt").ok(m, UJ3) and not __import__("xal_build").ok(m) and not {A}.ok(m)}}', 1),
        ('    others = [p for p in os.listdir(ROOT) if p.endswith(".pine") and p != ub.STR_PATH and not __import__("xal_build").ok(p)]\n',
         f'    others = [p for p in os.listdir(ROOT) if {P_OK} and p != ub.STR_PATH and not __import__("xal_build").ok(p)]\n', 1)],
    "tests/xaa_sim.py": [
        ('    others = [p for p in os.listdir(ROOT) if p.endswith(".pine") and p not in (xb.STR_PATH, xl.LONG_PATH)]\n',
         f'    others = [p for p in os.listdir(ROOT) if {P_OK} and p not in (xb.STR_PATH, xl.LONG_PATH)]     # ACC-1 new files: exact\n', 1)],
    "tests/xab_sim.py": [
        ('    others = [p for p in os.listdir(ROOT) if p.endswith(".pine") and p not in (xb.STR_PATH, xl.LONG_PATH)]\n',
         f'    others = [p for p in os.listdir(ROOT) if {P_OK} and p not in (xb.STR_PATH, xl.LONG_PATH)]     # ACC-1 new files: exact\n', 1)],
    "tests/xac_sim.py": [
        ('    others = [p for p in os.listdir(ROOT) if p.endswith(".pine") and p not in (xb.STR_PATH, xl.LONG_PATH)]\n',
         f'    others = [p for p in os.listdir(ROOT) if {P_OK} and p not in (xb.STR_PATH, xl.LONG_PATH)]     # ACC-1 new files: exact\n', 1)],
    "tests/xae_sim.py": [
        ('    mod = {m for m in mod if not __import__("uj3_adapt").ok(m, PREV) and not __import__("cad_adapt").ok(m, PREV) and not __import__("xal_build").ok(m)}',
         f'    mod = {{m for m in mod if not __import__("uj3_adapt").ok(m, PREV) and not __import__("cad_adapt").ok(m, PREV) and not __import__("xal_build").ok(m) and not {A}.ok(m)}}', 1),
        ('    others = [p for p in os.listdir(ROOT) if p.endswith(".pine") and p not in (xb.VIS_PATH, xb.STR_PATH, xb.ENG_PATH) and not __import__("xal_build").ok(p)]',
         f'    others = [p for p in os.listdir(ROOT) if {P_OK} and p not in (xb.VIS_PATH, xb.STR_PATH, xb.ENG_PATH) and not __import__("xal_build").ok(p)]', 1),
        ('    mod = {m for m in mod if not __import__("xal_build").ok(m) and m not in __import__("btl_build").NEW_TESTS and not __import__("au_build").ok(m)}',
         f'    mod = {{m for m in mod if not __import__("xal_build").ok(m) and m not in __import__("btl_build").NEW_TESTS and not __import__("au_build").ok(m) and not {A}.ok(m)}}', 1),
        ('    others = [p for p in os.listdir(ROOT) if p.endswith(".pine") and p not in (xb.VIS_PATH, xb.STR_PATH) and not __import__("xal_build").ok(p)]',
         f'    others = [p for p in os.listdir(ROOT) if {P_OK} and p not in (xb.VIS_PATH, xb.STR_PATH) and not __import__("xal_build").ok(p)]', 1)],
    "tests/xal_sim.py": [
        ('    others = [p for p in os.listdir(ROOT) if p.endswith(".pine") and p not in (xl.LONG_PATH,)]\n',
         f'    others = [p for p in os.listdir(ROOT) if {P_OK} and p not in (xl.LONG_PATH,)]     # ACC-1 new files: exact\n', 1)],
    "tests/xas_sim.py": [
        ('    others = [p for p in os.listdir(ROOT) if p.endswith(".pine") and p != xb.STR_PATH and not __import__("xal_build").ok(p)]\n',
         f'    others = [p for p in os.listdir(ROOT) if {P_OK} and p != xb.STR_PATH and not __import__("xal_build").ok(p)]\n', 1),
        ('if p.endswith(".pine") and p != xb.STR_PATH and not __import__("xal_build").ok(p) and rd(p) != xb.show(',
         f'if {P_OK} and p != xb.STR_PATH and not __import__("xal_build").ok(p) and rd(p) != xb.show(', 3),
        (XAS_OLD, XAS_OLD.replace('p.endswith(".pine")', P_OK), 5)],
    # heads of the older unadapt() chains: revert the ACC edits first (exact), then their own
    "tests/pf_sim.py": [
        ("              if p not in (xb.ENG_PATH, xb.STR_PATH, xl.LONG_PATH, ab.AUTO_PATH)]\n",
         f"              if p not in (xb.ENG_PATH, xb.STR_PATH, xl.LONG_PATH, ab.AUTO_PATH) and not {A}.ok(p)]     # ACC-1 new files: exact\n", 1)],
    "tests/cad_adapt.py": [
        ('             "tests/eua_build.py", "tests/eua_sim.py")                                       # new in the later layer EUA-1 (EURUSD adopted defaults)\n',
         '             "tests/eua_build.py", "tests/eua_sim.py",                                       # new in the later layer EUA-1 (EURUSD adopted defaults)\n'
         '             "AccumStrategyXAU.pine", "ACCUM_STRATEGY_XAU_ja.md", "tests/acc_pine.py",       # new in the later layers ACC-1 / ACC-2 (Accum Strategy XAU)\n'
         '             "tests/acc_sim.py", "tests/acc_build.py", "tests/.gitignore")\n', 1),
        ('    """the text with the edits of the layers after CAD-1 (LATER: XA-5) reverted, all or nothing per file."""\n',
         '    """the text with the edits of the layers after CAD-1 (LATER: XA-5) reverted, all or nothing per file."""\n'
         f'    text = {A}.unadapt(path, text)     # the later ACC-1 test edits are reverted first, exactly\n', 1)],
    "tests/eua_build.py": [
        ('    """a test file with its EUA-1 edits reverted (all or nothing; unchanged without them)."""\n',
         '    """a test file with its EUA-1 edits reverted (all or nothing; unchanged without them)."""\n'
         f'    text = {A}.unadapt(path, text)     # the later ACC-1 test edits are reverted first, exactly\n', 1)],
}


def _sub(text, old, new, count):
    if text is None or text.count(old) != count:
        return None
    return text.replace(old, new)


def apply_edits(path, text):
    for old, new, count in TEST_EDITS[path]:
        text = _sub(text, old, new, count)
    return text


def unadapt(path, text):
    """a test file with its ACC edits reverted (all or nothing; unchanged without them; None with only part of them)."""
    eds = TEST_EDITS.get(path, [])
    if text is None or not eds or all(text.count(new) == 0 for _, new, _ in eds):
        return text
    for old, new, count in reversed(eds):
        text = _sub(text, new, old, count)
    return text


if __name__ == "__main__":
    for p in TEST_EDITS:
        f = os.path.join(ROOT, p)
        t = open(f, encoding="utf-8").read()
        if all(t.count(new) == 0 for _, new, _ in TEST_EDITS[p]):
            t2 = apply_edits(p, t)
            assert t2 is not None, p
            assert unadapt(p, t2) == t, p
            open(f, "w", encoding="utf-8").write(t2)
            print("adapted", p)
