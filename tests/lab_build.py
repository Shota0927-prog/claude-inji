"""LAB-1 — registration of the files added after ACC-5B in the older fixtures (same method as tests/acc_build.py).

New files (no existing Strategy / Engine / Visual / harness behaviour changes):
  MtfPocDetector.pine (the MTF POC Detector indicator, added before LAB-1 and not registered then), ZoneComboLabXAU.pine,
  ZONE_COMBO_LAB_XAU_ja.md, tests/lab_pine.py, tests/lab_sim.py, tests/lab_load.py and tests/lab_build.py (this file).
The older fixtures' "every other file unchanged" checks accept these files only through ok() (TEST_EDITS below: one clause per check,
nothing else):
  * tests/acc_build.py: ok() also asks lab_build.ok() and unadapt() reverts the LAB-1 edits first; every older fixture already asks
    acc_build.ok() / acc_build.unadapt() (directly or through the unadapt() chain heads eua_build / cad_adapt), so this one place
    covers them
  * the five fixtures that test `m not in acc_build.NEW_FILES` ask acc_build.ok(m) instead (same answer for the ACC files)
  * acc_sim AS-10 (the only Pine changes since 890498e are the two ACC files) leaves the LAB-1 files out
  * cad_adapt LATER_NEW (the list of files new in later layers) gets the LAB-1 files
unadapt(path, text) reverts these edits exactly (all or nothing), so every older "test file changed by exactly its recorded edit"
check still compares the old text.
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NEW_FILES = ("MtfPocDetector.pine", "ZoneComboLabXAU.pine", "ZONE_COMBO_LAB_XAU_ja.md", "tests/lab_pine.py", "tests/lab_sim.py",
             "tests/lab_load.py", "tests/lab_build.py")


def ok(path):
    """LAB-1 accounts for this path exactly: one of its new files."""
    return path in NEW_FILES or __import__("fds_build").ok(path)     # the later FDS-1 files: exact


L = '__import__("lab_build")'
A = '__import__("acc_build")'
NF_OLD = f'm not in {A}.NEW_FILES     # ACC-1 new files'
NF_NEW = f'not {A}.ok(m)     # ACC-1 new files (+ later LAB-1 files through acc_build.ok)'

TEST_EDITS = {
    "tests/acc_build.py": [
        ('    return path in NEW_FILES\n',
         f'    return path in NEW_FILES or {L}.ok(path)     # the later LAB-1 files: exact\n', 1),
        ('    """a test file with its ACC edits reverted (all or nothing; unchanged without them; None with only part of them)."""\n',
         '    """a test file with its ACC edits reverted (all or nothing; unchanged without them; None with only part of them)."""\n'
         f'    text = {L}.unadapt(path, text)     # the later LAB-1 test edits are reverted first, exactly\n', 1)],
    "tests/bel_sim.py": [(NF_OLD, NF_NEW, 1)],
    "tests/eua_sim.py": [(NF_OLD, NF_NEW, 1)],
    "tests/gja_sim.py": [(NF_OLD, NF_NEW, 1)],
    "tests/msl_sim.py": [(NF_OLD, NF_NEW, 1)],
    "tests/uja_sim.py": [(NF_OLD, NF_NEW, 1)],
    "tests/acc_sim.py": [
        ('    pine = sorted(m for m in mod if m.endswith(".pine"))     # ACC-3: + the TradingView probe\n',
         f'    pine = sorted(m for m in mod if m.endswith(".pine") and not {L}.ok(m))     # ACC-3: + the TradingView probe (LAB-1 files: exact)\n', 1)],
    "tests/cad_adapt.py": [
        ('             "AccHistTickProbe.pine", "tests/acc3_exp.py")                                   # new in the later layer ACC-3 (probe / experiment)\n',
         '             "AccHistTickProbe.pine", "tests/acc3_exp.py",                                   # new in the later layer ACC-3 (probe / experiment)\n'
         '             "MtfPocDetector.pine", "ZoneComboLabXAU.pine", "ZONE_COMBO_LAB_XAU_ja.md",       # new in the later layer LAB-1\n'
         '             "tests/lab_pine.py", "tests/lab_sim.py", "tests/lab_load.py", "tests/lab_build.py")  # new in the later layer LAB-1\n', 1)],
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
    """a test file with its LAB-1 edits reverted (all or nothing; unchanged without them; None with only part of them)."""
    text = __import__("fds_build").unadapt(path, text)     # the later FDS-1 test edits are reverted first, exactly
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
