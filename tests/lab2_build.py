"""LAB-2 — registration of the external POC feed (MtfPocFeedXAU.pine) in the older fixtures, as a layer above LFW-1
(same method as acc_build / lab_build / fds_build / lfw_build: exact edits + an unadapt chain).

New files: MtfPocFeedXAU.pine and tests/lab2_build.py (this file). ZoneComboLabXAU.pine / ZONE_COMBO_LAB_XAU_ja.md / tests/lab_*.py
are LAB-1 files already accounted for by lab_build.
  * tests/lfw_build.py (the previous top layer): ok() also asks lab2_build.ok() and unadapt() reverts the LAB-2 edits first, so every
    older fixture (acc_build -> lab_build -> fds_build -> lfw_build -> lab2_build) accepts the LAB-2 files exactly
  * tests/cad_adapt.py: LATER_NEW gets the LAB-2 files as a separate statement placed before the LFW-1 statement (the LAB-1 line and the
    LFW-1 / FDS-1 edit texts stay byte for byte)
unadapt(path, text) reverts these edits exactly (all or nothing).
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NEW_FILES = ("MtfPocFeedXAU.pine", "tests/lab2_build.py")


def ok(path):
    """LAB-2 accounts for this path exactly: one of its new files."""
    return path in NEW_FILES or __import__("lbs_build").ok(path)     # the later LBS-1 files: exact


L2 = '__import__("lab2_build")'
LFW_LINE = ('LATER_NEW = LATER_NEW + ("LongFibWave.pine", "LONG_FIB_WAVE_ja.md", "tests/lfw_sim.py", "tests/lfw_build.py")'
            '  # new in the later layer LFW-1\n')

TEST_EDITS = {
    "tests/lfw_build.py": [
        ('    """LFW-1 accounts for this path exactly: one of its new files."""\n    return path in NEW_FILES\n',
         '    """LFW-1 accounts for this path exactly: one of its new files."""\n'
         f'    return path in NEW_FILES or {L2}.ok(path)     # the later LAB-2 files: exact\n', 1),
        ('    """a test file with its LFW-1 edits reverted (all or nothing; unchanged without them; None with only part of them)."""\n',
         '    """a test file with its LFW-1 edits reverted (all or nothing; unchanged without them; None with only part of them)."""\n'
         f'    text = {L2}.unadapt(path, text)     # the later LAB-2 test edits are reverted first, exactly\n', 1)],
    "tests/cad_adapt.py": [
        (LFW_LINE,
         'LATER_NEW = LATER_NEW + ("MtfPocFeedXAU.pine", "tests/lab2_build.py")  # new in the later layer LAB-2 (external POC feed)\n'
         + LFW_LINE, 1)],
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
    """a test file with its LAB-2 edits reverted (all or nothing; unchanged without them; None with only part of them)."""
    text = __import__("lbs_build").unadapt(path, text)     # the later LBS-1 test edits are reverted first, exactly
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
