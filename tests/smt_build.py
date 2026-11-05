"""SMT-2 — registration of the Stoch MTF Signal (1M) files in the older fixtures, as a layer above ZSY
(same method as acc_build / lab_build / fds_build / lfw_build / lab2_build / lbs_build / zsy_build: exact edits + an unadapt chain).

New files (no existing Strategy / Engine / Visual / Library / Zone Combo Lab / harness / order behaviour changes):
  StochMtfSignal.pine, STOCH_MTF_SIGNAL_ja.md, tests/smt_sim.py and tests/smt_build.py (this file).
The older fixtures' "every other file unchanged" checks accept these files only through ok() (TEST_EDITS below):
  * tests/zsy_build.py (the previous top layer): ok() also asks smt_build.ok() and unadapt() reverts the SMT edits first, so every
    older fixture (acc_build -> lab_build -> fds_build -> lfw_build -> lab2_build -> lbs_build -> zsy_build -> smt_build) accepts
    exactly these 4 files (not any other new file)
  * tests/cad_adapt.py: LATER_NEW gets the SMT files as a separate statement before the ZSY statement (the ZSY / LBS-1 / LAB-2 /
    LFW-1 / FDS-1 / LAB-1 edit texts stay byte for byte and contiguous)
  * tests/zsy_sim.py ZS-02 pins StochMtfSignal.pine to its SMT-1 text (146f68f). SMT-2 changes that file (f_pick: the containing
    higher-timeframe bar only on the confirmed 1M execution); PINE_EDITS records exactly those edits and ZS-02 compares the file
    with them reverted (pine_unapply), so it still detects any other change to it.
unadapt(path, text) reverts these edits exactly (all or nothing).

Run once to apply (idempotent):  python3 tests/smt_build.py --register
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NEW_FILES = ("StochMtfSignal.pine", "STOCH_MTF_SIGNAL_ja.md", "tests/smt_sim.py", "tests/smt_build.py")
REG_BASE = "3988fb4"     # the last commit before the SMT-2 registration edits


def ok(path):
    """SMT-1 accounts for this path exactly: one of its new files."""
    return path in NEW_FILES


S = '__import__("smt_build")'
ZSY_HEAD = 'LATER_NEW = LATER_NEW + ("ZoneSyncProbe.pine", '
ZS02_OLD = ('    src_same = all(zb.raw(p) == git("show", f"{zb.BASE_REV}:{p}").stdout for p in zb.SOURCES + ("StochMtfSignal.pine",))\n')
ZS02_NEW = ('    src_same = all(__import__("smt_build").pine_unapply(p, zb.raw(p)) == git("show", f"{zb.BASE_REV}:{p}").stdout\n'
            '                   for p in zb.SOURCES + ("StochMtfSignal.pine",))     # SMT-2 Pine edits reverted exactly first\n')
TEST_EDITS = {
    "tests/zsy_build.py": [
        ('    """ZSY accounts for this path exactly: one of its new files."""\n    return p in NEW_FILES\n',
         '    """ZSY accounts for this path exactly: one of its new files."""\n'
         f'    return p in NEW_FILES or {S}.ok(p)     # the later SMT files: exact\n', 1),
        ('    """a test file with its ZSY edits reverted (all or nothing; unchanged without them; None with only part of them)."""\n',
         '    """a test file with its ZSY edits reverted (all or nothing; unchanged without them; None with only part of them)."""\n'
         f'    text = {S}.unadapt(p, text)     # the later SMT test edits are reverted first, exactly\n', 1)],
    "tests/cad_adapt.py": [
        (ZSY_HEAD,
         'LATER_NEW = LATER_NEW + ("StochMtfSignal.pine", "STOCH_MTF_SIGNAL_ja.md", "tests/smt_sim.py", "tests/smt_build.py")'
         '  # new in the later layer SMT (Stoch MTF Signal)\n' + ZSY_HEAD, 1)],
    "tests/zsy_sim.py": [(ZS02_OLD, ZS02_NEW, 1)],
}

# SMT-2 edits of StochMtfSignal.pine (vs its SMT-1 text, 146f68f): (old, new, count)
PINE_PATH = "StochMtfSignal.pine"
PINE_EDITS = [
    ("//    ・1分足の time_close >= 含む上位足の time_close (= 同時に確定) のときだけ、含む上位足の K を最新確定値に使う。\n",
     "//    ・1分足の確定実行 (barstate.isconfirmed) で、かつ 1分足の time_close >= 含む上位足の time_close (= 同時に確定) のときだけ、\n"
     "//      含む上位足の K を最新確定値に使う (リアルタイムの途中 tick では使わない: 表・データウィンドウにも形成中の値を出さない)。\n", 1),
    ("// 判定時刻 t (1分足の time_close) で使う上位足の値: [K0 (最新確定), K1 (その1本前), K2 (2本前), 確定時刻]\n"
     "f_pick(float t, float c0, float c1, float c2, float c3, float hOpen, float hClose, float hClosePrev) =>\n",
     "// 判定時刻 t (1分足の time_close) で使う上位足の値: [K0 (最新確定), K1 (その1本前), K2 (2本前), 確定時刻]\n"
     "// conf = この実行が 1分足の確定実行か。確定前の実行 (リアルタイムの途中 tick) では、含む上位足は t 時点でまだ確定していない。\n"
     "f_pick(float t, bool conf, float c0, float c1, float c2, float c3, float hOpen, float hClose, float hClosePrev) =>\n", 1),
    ("        if t >= hClose                               // 含む上位足が T に確定 (同時確定)\n",
     "        if conf and t >= hClose                      // 1分足の確定時に、含む上位足も T に確定 (同時確定)\n", 1),
    ("        else                                         // 含む上位足は形成中 → 1本前の確定足\n",
     "        else                                         // 含む上位足は形成中 → 1本前の確定足 (time_close[1] <= 含む足の time)\n", 1),
    ("[k5, k5p, k5pp, t5ref]      = f_pick(tNow, a5c0",
     "[k5, k5p, k5pp, t5ref]      = f_pick(tNow, barstate.isconfirmed, a5c0", 1),
    ("[k15, k15p, k15pp, t15ref]  = f_pick(tNow, a15c0",
     "[k15, k15p, k15pp, t15ref]  = f_pick(tNow, barstate.isconfirmed, a15c0", 1),
]


def pine_unapply(path, text):
    """StochMtfSignal.pine with the SMT-2 edits reverted exactly (None when any is missing / ambiguous); other paths unchanged."""
    if path != PINE_PATH or text is None:
        return text
    for old, new, count in reversed(PINE_EDITS):
        if text.count(new) != count:
            return None
        text = text.replace(new, old)
    return text


def _sub(text, old, new, count):
    if text is None or text.count(old) != count:
        return None
    return text.replace(old, new)


def apply_edits(path, text):
    for old, new, count in TEST_EDITS[path]:
        text = _sub(text, old, new, count)
    return text


def unadapt(path, text):
    """a test file with its SMT-1 edits reverted (all or nothing; unchanged without them; None with only part of them)."""
    eds = TEST_EDITS.get(path, [])
    if text is None or not eds or all(text.count(new) == 0 for _, new, _ in eds):
        return text
    for old, new, count in reversed(eds):
        text = _sub(text, new, old, count)
    return text


if __name__ == "__main__":
    import sys
    if "--register" in sys.argv:
        for p in TEST_EDITS:
            f = os.path.join(ROOT, p)
            t = open(f, encoding="utf-8").read()
            if all(t.count(new) == 0 for _, new, _ in TEST_EDITS[p]):
                t2 = apply_edits(p, t)
                assert t2 is not None, p
                assert unadapt(p, t2) == t, p
                open(f, "w", encoding="utf-8", newline="").write(t2)
                print("adapted", p)
