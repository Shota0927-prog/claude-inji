"""SW-1 Gate SW-V1 — ZoneVisualPractical.pine: exact one-line transform of the Visual @ 110e5b0.

  import sekine3310/ZoneEnginePractical/5 as zn  ->  import sekine3310/ZoneEnginePractical/6 as zn
/6 = the published ZoneEnginePracticalSwingMax.pine (Swing max-score). Nothing else in the Visual changes.
"""
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SWV_BASE_REV = "110e5b0"
IMPORT_OLD = "import sekine3310/ZoneEnginePractical/5 as zn\n"
IMPORT_NEW = "import sekine3310/ZoneEnginePractical/6 as zn\n"
SWV_EDITS = [(IMPORT_OLD, IMPORT_NEW)]


def git_show(rev, path="ZoneVisualPractical.pine"):
    return subprocess.run(["git", "-C", ROOT, "show", f"{rev}:{path}"], capture_output=True, text=True).stdout


def swv_transform(src):
    t = src
    for a, b in SWV_EDITS:
        assert t.count(a) == 1, ("SW-V1 anchor not unique", a, t.count(a))
        t = t.replace(a, b)
    return t


def strip_swv(src):
    """SW-V1 Visual -> the 110e5b0 Visual text (None if the /6 import is not exactly once)."""
    if src is None:
        return None
    t = src
    for a, b in reversed(SWV_EDITS):
        if t.count(b) != 1:
            return None
        t = t.replace(b, a)
    return t
