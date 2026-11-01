"""LFW-1 — registration of the Long Fib Wave files in the older fixtures (same method as tests/fds_build.py / lab_build.py).

New files (no existing Strategy / Engine / Visual / Library / harness behaviour changes):
  LongFibWave.pine, LONG_FIB_WAVE_ja.md, tests/lfw_sim.py and tests/lfw_build.py (this file).
The older fixtures' "every other file unchanged" checks accept these files only through ok() (TEST_EDITS below):
  * tests/fds_build.py: ok() also asks lfw_build.ok() and unadapt() reverts the LFW-1 edits first; lab_build.ok() / unadapt()
    already ask fds_build, acc_build.ok() / unadapt() ask lab_build, and every older fixture asks acc_build (directly or through
    the unadapt() chain heads), so this one place covers them
  * cad_adapt LATER_NEW (the list of files new in later layers) gets the LFW-1 files, as a separate statement placed before the
    FDS-1 statement, so the LAB-1 line and the FDS-1 edit text (FDS statement + NEW_FILES line) stay exactly as lab_sim LS-11 /
    fds_sim FS-07 expect
unadapt(path, text) reverts these edits exactly (all or nothing), so every older "test file changed by exactly its recorded edit"
check (including lab_sim LS-11 and fds_sim FS-07) still compares the old text.
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NEW_FILES = ("LongFibWave.pine", "LONG_FIB_WAVE_ja.md", "tests/lfw_sim.py", "tests/lfw_build.py")
REG_BASE = "b7cab93"     # the last commit before the LFW-1 registration edits


def ok(path):
    """LFW-1 accounts for this path exactly: one of its new files."""
    return path in NEW_FILES


F = '__import__("lfw_build")'

TEST_EDITS = {
    "tests/fds_build.py": [
        ('    return path in NEW_FILES\n',
         f'    return path in NEW_FILES or {F}.ok(path)     # the later LFW-1 files: exact\n', 1),
        ('    """a test file with its FDS-1 edits reverted (all or nothing; unchanged without them; None with only part of them)."""\n',
         '    """a test file with its FDS-1 edits reverted (all or nothing; unchanged without them; None with only part of them)."""\n'
         f'    text = {F}.unadapt(path, text)     # the later LFW-1 test edits are reverted first, exactly\n', 1)],
    # a separate statement BEFORE the FDS-1 statement: the LAB-1 line and the FDS-1 edit text (its statement followed by the
    # NEW_FILES line, checked by fds_sim FS-07 on the current file) stay byte for byte and contiguous
    "tests/cad_adapt.py": [
        ('LATER_NEW = LATER_NEW + ("FVGDepthStats.pine", "FVG_DEPTH_STATS_ja.md", "tests/fds_sim.py", "tests/fds_build.py")  # new in the later layer FDS-1\n',
         'LATER_NEW = LATER_NEW + ("LongFibWave.pine", "LONG_FIB_WAVE_ja.md", "tests/lfw_sim.py", "tests/lfw_build.py")  # new in the later layer LFW-1\n'
         'LATER_NEW = LATER_NEW + ("FVGDepthStats.pine", "FVG_DEPTH_STATS_ja.md", "tests/fds_sim.py", "tests/fds_build.py")  # new in the later layer FDS-1\n', 1)],
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
    """a test file with its LFW-1 edits reverted (all or nothing; unchanged without them; None with only part of them)."""
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
