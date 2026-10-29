"""UJA-1 — USDJPY adopted defaults: ZoneStrategyUSDJPY.pine (TP / Breakeven, breakeven lock, Max SL Distance). Same method as GJA-1.

ZoneStrategyUSDJPY.pine == its file at BASE_REV + EDITS (exact replacements, each old once): the defaults of the user's adopted
USDJPY setting (TradingView, OANDA:USDJPY 5m, last 365 days) that differ from BASE_REV, the two tooltip phrases that state the old
default, and a header note. Requested 12 items: TP Nearest Opposite Zone OFF, TP Zone Min RR 1.0, Max RR 3.0, TP Fixed RR 1.5,
Breakeven Trigger (R) 1.0, Max SL Distance 40.0 pips already had these defaults (unchanged); changed: Breakeven Stop OFF -> ON,
Breakeven Trigger (円) 0.15 -> 0.30, Breakeven Trigger Mode Fixed Distance -> TP Progress, Breakeven Trigger (TP Ratio) 0.5 -> 0.7,
Lock New Entries After BE Until Original TP/SL OFF -> ON, Enable Max SL Distance OFF -> ON. Input names / titles, every other
input, trading code, the Engine import, the other Strategies (GBPJPY GJA-1 included), the USDJPY diagnostic copy, Visuals and
Engines are unchanged. strip() reverses the edits exactly; unapply() leaves a text without them unchanged.
"""
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = "ZoneStrategyUSDJPY.pine"
BASE_REV = "6b15093"
NEW_TESTS = ("tests/uja_build.py", "tests/uja_sim.py")

# (input, before, after): the requested defaults that differ from BASE_REV
CHANGES = [("stBE", "false", "true"), ("stBEDist", "0.15", "0.30"), ("stBEMode", '"Fixed Distance"', '"TP Progress"'),
           ("stBETp", "0.5", "0.7"), ("stBeLock", "false", "true"), ("stMaxSlOn", "false", "true")]
# the requested items that already had the requested default (kept)
KEPT = [("stTpZone", "false"), ("stTpMinRR", "1.0"), ("stTpMaxRR", "3.0"), ("stRR", "1.5"), ("stBER", "1.0"), ("stMaxSl", "40.0")]

HDR_OLD = "//  Zone Strategy USDJPY  —  ZONE-JPY (ZoneVisualUSDJPY) の Zone 判定をそのまま使う OANDA:USDJPY 5分足 Strategy\n"
HDR_NEW = (HDR_OLD +
           "//  UJA-1: USDJPY の採用設定を初期値に反映 (生成: tests/uja_build.py。TradingView OANDA:USDJPY 5分足・過去365日の検証で採用。\n"
           "//  その成績が他の期間・データ条件で再現される保証はない)。変更した初期値: Breakeven Stop OFF→ON、Breakeven Trigger (円)\n"
           "//  0.15→0.30、Breakeven Trigger Mode Fixed Distance→TP Progress、TP Ratio 0.5→0.7、建値決済後の新規 Entry ロック OFF→ON、\n"
           "//  Max SL Distance OFF→ON (40 pips は従来値のまま)。売買処理・計算式・他の入力は変えない。\n")

EDITS = [
    ("header", HDR_OLD, HDR_NEW),
    ("default", 'stBE = input.bool(false, "Breakeven Stop",', 'stBE = input.bool(true, "Breakeven Stop",'),
    ("default", 'stBEDist = input.float(0.15, "[暫定] Breakeven Trigger (円)",', 'stBEDist = input.float(0.30, "[暫定] Breakeven Trigger (円)",'),
    ("default", 'stBEMode = input.string("Fixed Distance", "Breakeven Trigger Mode",', 'stBEMode = input.string("TP Progress", "Breakeven Trigger Mode",'),
    ("tooltip", '     tooltip = "比較用 (初期 Fixed Distance = 従来の固定幅 Breakeven Trigger)。選択した方式の入力だけを使う。\\n" +\n',
                '     tooltip = "初期 TP Progress (USDJPY 採用値)。Fixed Distance = 従来の固定幅 Breakeven Trigger。選択した方式の入力だけを使う。\\n" +\n'),
    ("default", 'stBETp = input.float(0.5, "Breakeven Trigger (TP Ratio)",', 'stBETp = input.float(0.7, "Breakeven Trigger (TP Ratio)",'),
    ("default", 'stBeLock = input.bool(false, "Lock New Entries After BE Until Original TP/SL",', 'stBeLock = input.bool(true, "Lock New Entries After BE Until Original TP/SL",'),
    ("default", 'stMaxSlOn = input.bool(false, "Enable Max SL Distance",', 'stMaxSlOn = input.bool(true, "Enable Max SL Distance",'),
    ("tooltip", "初期 40.0 pips は暫定値 (検証前・適正値ではない)。", "初期 40.0 pips = USDJPY 採用値 (過去365日の検証から採用。他の期間での有効性は未確認)。"),
]


def show(rev, path):
    return subprocess.run(["git", "-C", ROOT, "show", f"{rev}:{path}"], capture_output=True, text=True).stdout


def _apply(src, eds):
    out = src
    for _, a, b in eds:
        assert out.count(a) == 1, a[:80]
        out = out.replace(a, b)
    return out


def _revert(text, eds):
    out = text
    for _, a, b in reversed(eds):
        if out is None or out.count(b) != 1:
            return None
        out = out.replace(b, a)
    return out


def build():
    return _apply(show(BASE_REV, PATH), EDITS)


def strip(text):
    """reverse UJA-1 exactly (-> the USDJPY Strategy of BASE_REV); None when not exact."""
    return _revert(text, EDITS)


def unapply(path, text):
    """reverse UJA-1 when present (all or nothing): unchanged without it (or for other paths), None with only part of it."""
    text = __import__("eua_build").unapply(path, text)     # the later EUA-1 layer (EURUSD adopted defaults) is reverted first, exactly
    if text is None or path != PATH or HDR_NEW.split("\n")[1] not in text:
        return text
    return strip(text)


# the exact edits UJA-1 makes to older generators / fixtures (unadapt() reverts them)
TEST_EDITS = {
    "tests/gja_build.py": [
        ('    """reverse GJA-1 when present (all or nothing): unchanged without it (or for other paths), None with only part of it."""\n'
         '    if text is None or path != PATH',
         '    """reverse GJA-1 when present (all or nothing): unchanged without it (or for other paths), None with only part of it."""\n'
         '    text = __import__("uja_build").unapply(path, text)     # the later UJA-1 layer (USDJPY adopted defaults) is reverted first, exactly\n'
         '    if text is None or path != PATH'),
        ('    """a test file with its GJA-1 edits reverted (all or nothing; unchanged without them)."""\n',
         '    """a test file with its GJA-1 edits reverted (all or nothing; unchanged without them)."""\n'
         '    text = __import__("uja_build").unadapt(path, text)     # the later UJA-1 test edits are reverted first, exactly\n')],
    "tests/gja_sim.py": [
        ('          and not [p for p in others if raw(p) != gb.show(B, p)])\n',
         '          and not [p for p in others if __import__("uja_build").unapply(p, raw(p)) != gb.show(B, p)])     # later UJA-1 reverted exactly\n'),
        ('    bad = sorted(m for m in mod if m != gb.PATH and m not in gb.NEW_TESTS\n',
         '    bad = sorted(m for m in mod if m != gb.PATH and m not in gb.NEW_TESTS and m not in __import__("uja_build").NEW_TESTS\n'),
        ('                 and not (m in gb.TEST_EDITS and gb.unadapt(m, raw(m)) == gb.show(B, m) and gb.unadapt(m, raw(m)) != raw(m)))\n',
         '                 and not (m in gb.TEST_EDITS and gb.unadapt(m, raw(m)) == gb.show(B, m) and gb.unadapt(m, raw(m)) != raw(m))\n                 and not (m == __import__("uja_build").PATH and __import__("uja_build").unapply(m, raw(m)) == gb.show(B, m)))     # later UJA-1: exact\n')],
    "tests/bel_sim.py": [('    bad = sorted(m for m in mod if m not in bb.FILES and m not in bb.NEW_TESTS and m not in __import__("gja_build").NEW_TESTS\n',
                          '    bad = sorted(m for m in mod if m not in bb.FILES and m not in bb.NEW_TESTS and m not in __import__("gja_build").NEW_TESTS\n                 and m not in __import__("uja_build").NEW_TESTS\n')],
    "tests/msl_sim.py": [('                 and m not in __import__("gja_build").NEW_TESTS\n',
                          '                 and m not in __import__("gja_build").NEW_TESTS and m not in __import__("uja_build").NEW_TESTS\n')],
    "tests/cad_adapt.py": [
        ('             "tests/gja_build.py", "tests/gja_sim.py")                                       # new in the later layer GJA-1 (GBPJPY adopted defaults)\n',
         '             "tests/gja_build.py", "tests/gja_sim.py",                                       # new in the later layer GJA-1 (GBPJPY adopted defaults)\n'
         '             "tests/uja_build.py", "tests/uja_sim.py")                                       # new in the later layer UJA-1 (USDJPY adopted defaults)\n')],
    "tests/au_build.py": [
        ('             "tests/gja_build.py", "tests/gja_sim.py")\n',
         '             "tests/gja_build.py", "tests/gja_sim.py",\n'
         '             # later layer UJA-1 (USDJPY adopted defaults): its generator / fixture (the Pine file through uja_build.unapply)\n'
         '             "tests/uja_build.py", "tests/uja_sim.py")\n')],
}


def unadapt(path, text):
    """a test file with its UJA-1 edits reverted (all or nothing; unchanged without them)."""
    text = __import__("eua_build").unadapt(path, text)     # the later EUA-1 test edits are reverted first, exactly
    pairs = TEST_EDITS.get(path, [])
    if text is None or not pairs or all(text.count(b) == 0 for _, b in pairs):
        return text
    return _revert(text, [("", a, b) for a, b in pairs])


if __name__ == "__main__":
    open(os.path.join(ROOT, PATH), "w", encoding="utf-8").write(build())
    print("written", PATH)
    for p, pairs in TEST_EDITS.items():
        t = open(os.path.join(ROOT, p), encoding="utf-8").read()
        if all(t.count(b) == 0 for _, b in pairs):
            for a, b in pairs:
                assert t.count(a) == 1, (p, a[:60])
                t = t.replace(a, b)
            open(os.path.join(ROOT, p), "w", encoding="utf-8").write(t)
            print("adapted", p)
