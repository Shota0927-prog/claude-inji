"""ZSY — the copied regions of ZoneSyncProbe.pine, and the registration of the ZSY files in the older fixtures.

  python3 tests/zsy_build.py              # (re)write the "ZSY copy" regions of ZoneSyncProbe.pine from the source files
  python3 tests/zsy_build.py --register   # the registration edits in the older fixtures (once; idempotent)

Copied regions (byte for byte from the unchanged sources; tests/zsy_sim.py compares them again):
  LAB_ACCUM / LAB_ACCUM_CONF / LAB_PIVOT / LAB_FVG  <- ZoneComboLabXAU.pine
  FEED_POC / FEED_FEED                              <- MtfPocFeedXAU.pine (a version 6 script; the copied lines are also valid version 5)
  LFW_INPUTS / LFW_LOGIC / LFW_CORE / LFW_FIBSTATE / LFW_FIBFEED <- LongFibWave.pine
Registration (same method as tests/lbs_build.py): the previous top layer tests/lbs_build.py accepts the ZSY files through ok()
and its unadapt() reverts the ZSY edits first; tests/cad_adapt.py LATER_NEW gets the ZSY files as a separate statement before the
LBS-1 statement. unadapt() reverts these edits exactly (all or nothing).
"""
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROBE = "ZoneSyncProbe.pine"
NEW_FILES = (PROBE, "ZONE_SYNC_FEASIBILITY_ja.md", "tests/zsy_build.py", "tests/zsy_sim.py", "tests/zsy_exp.py")
BASE_REV = "146f68f"     # the branch before any ZSY file (SMT-1)
SOURCES = ("ZoneComboLabXAU.pine", "MtfPocFeedXAU.pine", "LongFibWave.pine")
LFW_INPUT_NAMES = ("lfwSwitchRatioD", "lfwSwitchRatio4", "lfwStartRatio", "lfwExclInit", "lfwAtrLen", "lfwPivLD", "lfwPivRD",
                   "lfwPivMD", "lfwPivL4", "lfwPivR4", "lfwPivM4", "lfwMaxRecs")


def raw(p):
    return open(os.path.join(ROOT, p), encoding="utf-8").read()


def git(*a):
    return subprocess.run(["git", "-C", ROOT] + list(a), capture_output=True, text=True).stdout


def marked(src, begin, end):
    """the lines from the one starting with `begin` to the one starting with `end` (both included)"""
    i = src.index("\n" + begin) + 1
    j = src.index("\n" + end, i) + 1
    k = src.find("\n", j)
    return src[i:k if k >= 0 else len(src)]


def func_text(src, name):
    """a top-level Pine function: its header line and every following line until the next unindented line (trailing blanks dropped)"""
    i = src.index("\n" + name + "(") + 1
    lines = src[i:].split("\n")
    out = [lines[0]]
    for ln in lines[1:]:
        if ln and not ln.startswith(" "):
            break
        out.append(ln)
    while out and not out[-1].strip():
        out.pop()
    return "\n".join(out)


def blocks():
    lab, feed, lfw = (raw(p) for p in SOURCES)
    inputs = [ln for ln in lfw.split("\n") if re.match(r"(%s)\s*=\s*input\." % "|".join(LFW_INPUT_NAMES), ln)]
    assert len(inputs) == len(LFW_INPUT_NAMES), inputs
    return {
        "LFW_INPUTS":     ("LongFibWave.pine", "\n".join(inputs)),
        "LAB_ACCUM":      ("ZoneComboLabXAU.pine", marked(lab, "// ==== LAB Accum copy (begin)", "// ==== LAB Accum copy (end)")),
        "LAB_ACCUM_CONF": ("ZoneComboLabXAU.pine", func_text(lab, "f_acConfirmed")),
        "LAB_PIVOT":      ("ZoneComboLabXAU.pine", func_text(lab, "f_lbPivotConfirmed")),
        "LAB_FVG":        ("ZoneComboLabXAU.pine", marked(lab, "// ==== LAB FVG copy (begin)", "// ==== LAB FVG copy (end)")),
        "FEED_POC":       ("MtfPocFeedXAU.pine", marked(feed, "// ==== FEED POC core (begin)", "// ==== FEED POC core (end)")),
        "FEED_FEED":      ("MtfPocFeedXAU.pine", func_text(feed, "f_feed")),
        "LFW_LOGIC":      ("LongFibWave.pine", marked(lfw, "// ==== LFW Logic (begin)", "// ==== LFW Transfer (end)")),
        "LFW_CORE":       ("LongFibWave.pine", func_text(lfw, "f_lfwCore")),
        "LFW_FIBSTATE":   ("LongFibWave.pine", func_text(lfw, "f_fibState")),
        "LFW_FIBFEED":    ("LongFibWave.pine", func_text(lfw, "f_fibFeed")),
    }


def begin_line(name, src):
    return f"// ==== ZSY copy {name} begin (from {src}, byte for byte) ===="


def end_line(name):
    return f"// ==== ZSY copy {name} end ===="


def regions(text):
    """name -> copied text between the begin / end lines of the probe"""
    out = {}
    for m in re.finditer(r"^// ==== ZSY copy (\w+) begin \(from [^)]*\) ====\n(.*?)\n// ==== ZSY copy \1 end ====$", text, re.S | re.M):
        out[m.group(1)] = m.group(2)
    return out


def build(text):
    for name, (src, body) in blocks().items():
        new = begin_line(name, src) + "\n" + body + "\n" + end_line(name)
        ph = f"// @@COPY {name}"
        if ph in text:
            text = text.replace(ph, new, 1)
        else:
            pat = re.compile(r"^// ==== ZSY copy %s begin .*?^// ==== ZSY copy %s end ====$" % (name, name), re.S | re.M)
            text, k = pat.subn(lambda _m: new, text)
            assert k == 1, name
    return text


# ---- registration in the older fixtures (a layer above LBS-1; same method as tests/lbs_build.py) ----
def ok(p):
    """ZSY accounts for this path exactly: one of its new files."""
    return p in NEW_FILES


Z = '__import__("zsy_build")'
LBS_LINE_HEAD = 'LATER_NEW = LATER_NEW + ("ZoneComboLabBTCUSD.pine", '
TEST_EDITS = {
    "tests/lbs_build.py": [
        ('    """LBS-1 accounts for this path exactly: one of its new files."""\n    return p in NEW_FILES\n',
         '    """LBS-1 accounts for this path exactly: one of its new files."""\n'
         f'    return p in NEW_FILES or {Z}.ok(p)     # the later ZSY files: exact\n', 1),
        ('    """a test file with its LBS-1 edits reverted (all or nothing; unchanged without them; None with only part of them)."""\n',
         '    """a test file with its LBS-1 edits reverted (all or nothing; unchanged without them; None with only part of them)."""\n'
         f'    text = {Z}.unadapt(p, text)     # the later ZSY test edits are reverted first, exactly\n', 1)],
    "tests/cad_adapt.py": [
        (LBS_LINE_HEAD,
         'LATER_NEW = LATER_NEW + ("ZoneSyncProbe.pine", "ZONE_SYNC_FEASIBILITY_ja.md", "tests/zsy_build.py", "tests/zsy_sim.py",\n'
         '                         "tests/zsy_exp.py")  # new in the later layer ZSY (all-timeframe Zone display, probe)\n' + LBS_LINE_HEAD, 1)],
}


def _rsub(text, old, new, count):
    if text is None or text.count(old) != count:
        return None
    return text.replace(old, new)


def apply_edits(p, text):
    for old, new, count in TEST_EDITS[p]:
        text = _rsub(text, old, new, count)
    return text


def unadapt(p, text):
    """a test file with its ZSY edits reverted (all or nothing; unchanged without them; None with only part of them)."""
    eds = TEST_EDITS.get(p, [])
    if text is None or not eds or all(text.count(new) == 0 for _, new, _ in eds):
        return text
    for old, new, count in reversed(eds):
        text = _rsub(text, new, old, count)
    return text


if __name__ == "__main__":
    if "--register" in sys.argv:
        for p in TEST_EDITS:
            f = os.path.join(ROOT, p)
            t = open(f, encoding="utf-8").read()
            if all(t.count(new) == 0 for _, new, _ in TEST_EDITS[p]):
                t2 = apply_edits(p, t)
                assert t2 is not None, p
                assert unadapt(p, t2) == t, p
                open(f, "w", encoding="utf-8").write(t2)
                print("adapted", p)
    else:
        f = os.path.join(ROOT, PROBE)
        t = open(f, encoding="utf-8").read()
        open(f, "w", encoding="utf-8").write(build(t))
        print("wrote", PROBE)
