"""ZONE-P bonus defaults — ZoneVisualPractical.pine: exact transform of the Visual @ 9270c50.

Only three input defaults change (inputs kept, user can set them back):
  MA Cluster Bonus 1.0 -> 0.0, MA Cluster Bonus · Same Slope 1.0 -> 0.0, Flip Bonus 2.0 -> 0.0
MA slope scoring (thresholds, bonuses, lookback, Sum aggregation), Flip detection / state and every other input,
config assignment, block and the Engine (/6) are unchanged.
"""
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BON_BASE_REV = "9270c50"
BON_EDITS = [
    ('maClusterBonus = input.float(1.0, "MA Cluster Bonus",              step = 0.5, group = G_SLOPE)\n',
     'maClusterBonus = input.float(0.0, "MA Cluster Bonus",              step = 0.5, group = G_SLOPE)\n'),
    ('maClusterDirBonus = input.float(1.0, "MA Cluster Bonus · Same Slope", step = 0.5, group = G_SLOPE)\n',
     'maClusterDirBonus = input.float(0.0, "MA Cluster Bonus · Same Slope", step = 0.5, group = G_SLOPE)\n'),
    ('flipBonus = input.float(2.0, "Flip Bonus", step = 0.5, group = G_SCORE)\n',
     'flipBonus = input.float(0.0, "Flip Bonus", step = 0.5, group = G_SCORE)\n'),
]


def git_show(rev, path="ZoneVisualPractical.pine"):
    return subprocess.run(["git", "-C", ROOT, "show", f"{rev}:{path}"], capture_output=True, text=True).stdout


def bon_transform(src):
    t = src
    for a, b in BON_EDITS:
        assert t.count(a) == 1, ("BON anchor not unique", a[:60], t.count(a))
        t = t.replace(a, b)
    return t


def strip_bon(src):
    if src is None:
        return None
    t = src
    for a, b in reversed(BON_EDITS):
        if t.count(b) != 1:
            return None
        t = t.replace(b, a)
    return t
