"""XA-1 — Gold (XAUUSD 5M) comparison defaults: ZoneStrategyXAU.pine (ZONE-ST) and ZoneVisualPractical.pine (ZONE-P).

Defaults only (the user's current TradingView comparison setting, still under comparison — not optimised, future validity
not confirmed). Shared Zone inputs in both files: Zone Half Width 3 -> 6, Break Buffer 5 -> 10 (Cluster Distance 5 and Flip
Confirm Distance 10 already match). Strategy only: Entry Mode D -> C: Candle Pattern, Direction Both -> Short Only, opposite-
zone TP ON -> OFF (SL Buffer 3, fixed RR 1.5, breakeven OFF already match). Capital 10,000, currency, fixed qty 1, Engine /
import, logic, alerts and every other input are unchanged.
Each strip_*() reverses the edits and must give the files of BASE_REV back byte for byte (fixture xa_sim). The older
fixtures that pin ZONE-P / ZONE-ST read them through pre_xa() (the XA-1 edits reverted) and accept them in their "unchanged"
checks only when they differ exactly by XA-1.
"""
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIS_PATH, STR_PATH = "ZoneVisualPractical.pine", "ZoneStrategyXAU.pine"
XA_FILES = (VIS_PATH, STR_PATH)
BASE_REV = "f253890"
NOTE = "比較継続中の初期値 (ユーザーの XAUUSD 5分足比較設定。最適化完了・将来の有効性確認済みではない)"

ZONE_EDITS = [
    ("default",
     'zoneHalfWidth = input.float(3.0, "Zone Half Width ($)", minval = 0.1, step = 0.5, group = G_ZONE,\n',
     'zoneHalfWidth = input.float(6.0, "Zone Half Width ($)", minval = 0.1, step = 0.5, group = G_ZONE,\n'),
    ("default",
     'breakBuffer = input.float(5.0,  "Break Buffer ($)",         step = 0.5, group = G_BF)\n',
     'breakBuffer = input.float(10.0,  "Break Buffer ($)",         step = 0.5, group = G_BF)\n'),
]
VISUAL_EDITS = [
    ("header",
     "//  Zone Visual (Practical)  —  ZoneEnginePractical 表示専用 Indicator\n",
     "//  Zone Visual (Practical)  —  ZoneEnginePractical 表示専用 Indicator\n"
     "//  XA-1: Zone Half Width 6 / Break Buffer 10 USD (Cluster 5 / Flip 10 は従来どおり) = " + NOTE + "。\n"),
] + ZONE_EDITS
STRATEGY_EDITS = [
    ("header",
     "//  Zone Strategy XAU  —  ZONE-P (ZoneVisualPractical) の Zone 判定をそのまま使う XAUUSD 5分足 Strategy\n",
     "//  Zone Strategy XAU  —  ZONE-P (ZoneVisualPractical) の Zone 判定をそのまま使う XAUUSD 5分足 Strategy\n"
     "//  XA-1: " + NOTE + ": Zone Half Width 6 / Cluster 5 / Break Buffer 10 /\n"
     "//  Flip 10 USD (Zone は ZONE-P と共通)、Entry C: Candle Pattern、Short Only、SL Buffer 3、固定 RR 1.5、反対側 Zone TP OFF、\n"
     "//  建値移動 OFF。初期資金 10,000・数量 1 固定は従来どおり (資金管理は未追加)。\n"),
] + ZONE_EDITS + [
    ("default",
     'stMode = input.string("D: 1M BOS Rebound", "Entry Mode",\n',
     'stMode = input.string("C: Candle Pattern", "Entry Mode",\n'),
    ("default",
     'stDir = input.string("Both", "Direction", options = ["Long Only", "Short Only", "Both"], group = G_ST)\n',
     'stDir = input.string("Short Only", "Direction", options = ["Long Only", "Short Only", "Both"], group = G_ST)\n'),
    ("default",
     'stTpZone = input.bool(true, "TP · Nearest Opposite Zone (Medium+)", group = G_STT)\n',
     'stTpZone = input.bool(false, "TP · Nearest Opposite Zone (Medium+)", group = G_STT)\n'),
]


def _apply(src, edits):
    out = src
    for _, a, b in edits:
        assert out.count(a) == 1, a[:80]
        out = out.replace(a, b)
    return out


def _revert(text, edits):
    out = text
    for _, a, b in reversed(edits):
        if out is None or out.count(b) != 1:
            return None
        out = out.replace(b, a)
    return out


_rd = lambda p: open(os.path.join(ROOT, p), encoding="utf-8").read()


def show(rev, path):
    return subprocess.run(["git", "-C", ROOT, "show", f"{rev}:{path}"], capture_output=True, text=True).stdout


def build_visual():
    return _apply(show(BASE_REV, VIS_PATH), VISUAL_EDITS)


def build_strategy():
    return _apply(show(BASE_REV, STR_PATH), STRATEGY_EDITS)


def strip_visual(t):
    return _revert(t, VISUAL_EDITS)


def strip_strategy(t):
    return _revert(t, STRATEGY_EDITS)


# ---- helpers for the older fixtures ------------------------------------------------------------------------------------
def pre_xa(path, text=None):
    """ZONE-P / ZONE-ST text with the XA-1 edits reverted (unchanged if they are not present)."""
    if text is None:
        text = _rd(path)
    s = (strip_visual if path == VIS_PATH else strip_strategy)(text)
    return text if s is None else s


def xa_ok(path, rev):
    """True when the working-tree file differs from `rev` only by the XA-1 edits (exact, byte for byte)."""
    if path not in XA_FILES:
        return False
    s = (strip_visual if path == VIS_PATH else strip_strategy)(_rd(path))
    return s is not None and s == show(rev, path)


if __name__ == "__main__":
    for path, fn in ((VIS_PATH, build_visual), (STR_PATH, build_strategy)):
        open(os.path.join(ROOT, path), "w", encoding="utf-8").write(fn())
        print("written", path)


def drop_xa(names, rev):
    """remove ZONE-P / ZONE-ST from a changed-path list only when they differ from `rev` exactly by XA-1."""
    return [n for n in names if not xa_ok(n, rev)]


def unadapt(path, text):
    """a test / generator file with its XA-1 edits reverted (unchanged for files not in TEST_ADAPT)."""
    out = text
    for a, b in reversed(TEST_ADAPT.get(path, [])):
        if out is None or out.count(b) != 1:
            return None
        out = out.replace(b, a)
    return out


def test_ok(path):
    """True when the file differs from BASE_REV only by its exact XA-1 edits."""
    return path in TEST_ADAPT and unadapt(path, _rd(path)) == show(BASE_REV, path)


# exact XA-1 edits of existing test / generator files vs BASE_REV (generated from the diff; unadapt() reverses them)
TEST_ADAPT = {'tests/bon_sim.py': [('ROOT = bb.ROOT\n'
                       'CUR = open(os.path.join(ROOT, "ZoneVisualPractical.pine"), encoding="utf-8").read()\n'
                       'BASE = bb.git_show(bb.BON_BASE_REV)\n',
                       'ROOT = bb.ROOT\n'
                       'CUR = __import__("xa_build").pre_xa("ZoneVisualPractical.pine", open(os.path.join(ROOT, '
                       '"ZoneVisualPractical.pine"), encoding="utf-8").read())  # XA-1 Gold defaults stripped -> '
                       'f253890 text (delta pinned by xa_sim)\n'
                       'BASE = bb.git_show(bb.BON_BASE_REV)\n')],
 'tests/bte_build.py': [('    """a test / generator file with its BTE-1 edits reverted (unchanged for files not in '
                         'TEST_ADAPT)."""\n'
                         '    out = text\n'
                         '    for a, b in reversed(TEST_ADAPT.get(path, [])):\n',
                         '    """a test / generator file with its BTE-1 edits reverted (unchanged for files not in '
                         'TEST_ADAPT)."""\n'
                         '    out = __import__("xa_build").unadapt(path, text)     # XA-1 edits (later) are reverted '
                         'first\n'
                         '    for a, b in reversed(TEST_ADAPT.get(path, [])):\n'),
                        ('    """True when the file differs from BASE_REV only by its exact BTE-1 edits."""\n'
                         '    return path in TEST_ADAPT and unadapt(path, _rd(path)) == _show(BASE_REV, path)\n'
                         '\n',
                         '    """True when the file differs from BASE_REV only by its exact BTE-1 edits."""\n'
                         '    return (path in TEST_ADAPT or path in __import__("xa_build").TEST_ADAPT) and '
                         'unadapt(path, _rd(path)) == _show(BASE_REV, path)\n'
                         '\n')],
 'tests/bte_sim.py': [('    mod = git("diff", "--name-only", "--diff-filter=MDR", be.BASE_REV, "--").split()\n'
                       '    rest = [m for m in mod if not (be.bte_pine_ok(m, be.BASE_REV) or be.test_ok(m))]\n'
                       '    check("BE-07 vs e1c3cea: the BTC Visual / Strategy differ exactly by the new layer, '
                       'every other changed file is a test / "\n',
                       '    mod = git("diff", "--name-only", "--diff-filter=MDR", be.BASE_REV, "--").split()\n'
                       '    rest = [m for m in mod if not (be.bte_pine_ok(m, be.BASE_REV) or be.test_ok(m) or '
                       '__import__("xa_build").xa_ok(m, be.BASE_REV))]   # XA-1: exact\n'
                       '    check("BE-07 vs e1c3cea: the BTC Visual / Strategy differ exactly by the new layer, '
                       'every other changed file is a test / "\n'),
                      ('          "symbols\' Pine files untouched", set(mod) >= {bb.BTC_PATH, sb.BTS_PATH} and not '
                       'rest\n'
                       '          and not [m for m in mod if m.endswith(".pine") and m not in (bb.BTC_PATH, '
                       'sb.BTS_PATH)], str(rest))\n'
                       '    m = S.replace("import sekine3310/ZoneEnginePracticalBTCUSD/1 as zn", "import '
                       'sekine3310/ZoneEnginePracticalGBPJPY/3 as zn")\n',
                       '          "symbols\' Pine files untouched", set(mod) >= {bb.BTC_PATH, sb.BTS_PATH} and not '
                       'rest\n'
                       '          and not [m for m in mod if m.endswith(".pine") and m not in (bb.BTC_PATH, '
                       'sb.BTS_PATH)\n'
                       '                   and not __import__("xa_build").xa_ok(m, be.BASE_REV)], str(rest))\n'
                       '    m = S.replace("import sekine3310/ZoneEnginePracticalBTCUSD/1 as zn", "import '
                       'sekine3310/ZoneEnginePracticalGBPJPY/3 as zn")\n')],
 'tests/fvg_batch_a_sim.py': [('_RAW = open(VIS_PATH, encoding="utf-8").read()\n'
                               '_RAW = __import__("bon_build").strip_bon(_RAW) or _RAW  # bonus defaults stripped -> '
                               '9270c50 text (delta pinned by bon_sim)\n',
                               '_RAW = open(VIS_PATH, encoding="utf-8").read()\n'
                               '_RAW = __import__("xa_build").pre_xa("ZoneVisualPractical.pine", _RAW)  # XA-1 Gold '
                               'defaults stripped -> f253890 text (delta pinned by xa_sim)\n'
                               '_RAW = __import__("bon_build").strip_bon(_RAW) or _RAW  # bonus defaults stripped -> '
                               '9270c50 text (delta pinned by bon_sim)\n')],
 'tests/fvg_re10045_sim.py': [('def main():\n'
                               '    cur = open(os.path.join(ROOT, "ZoneVisualPractical.pine"), '
                               'encoding="utf-8").read()\n'
                               '    cur = __import__("bon_build").strip_bon(cur) or cur  # bonus defaults stripped '
                               '-> 9270c50 text (delta pinned by bon_sim)\n',
                               'def main():\n'
                               '    cur = __import__("xa_build").pre_xa("ZoneVisualPractical.pine", '
                               'open(os.path.join(ROOT, "ZoneVisualPractical.pine"), encoding="utf-8").read())  # '
                               'XA-1 Gold defaults stripped -> f253890 text (delta pinned by xa_sim)\n'
                               '    cur = __import__("bon_build").strip_bon(cur) or cur  # bonus defaults stripped '
                               '-> 9270c50 text (delta pinned by bon_sim)\n')],
 'tests/fvl_sim.py': [('ROOT = lb.ROOT\n'
                       'CUR = open(os.path.join(ROOT, "ZoneVisualPractical.pine"), encoding="utf-8").read()\n'
                       'CUR = __import__("bon_build").strip_bon(CUR) or CUR  # bonus defaults stripped -> 9270c50 '
                       'text (delta pinned by bon_sim)\n',
                       'ROOT = lb.ROOT\n'
                       'CUR = __import__("xa_build").pre_xa("ZoneVisualPractical.pine", open(os.path.join(ROOT, '
                       '"ZoneVisualPractical.pine"), encoding="utf-8").read())  # XA-1 Gold defaults stripped -> '
                       'f253890 text (delta pinned by xa_sim)\n'
                       'CUR = __import__("bon_build").strip_bon(CUR) or CUR  # bonus defaults stripped -> 9270c50 '
                       'text (delta pinned by bon_sim)\n')],
 'tests/jpy_build.py': [('def build():\n'
                         '    return jpy_transform(open(os.path.join(ROOT, SRC_PATH), encoding="utf-8").read())\n'
                         '\n',
                         'def build():\n'
                         '    return jpy_transform(__import__("xa_build").pre_xa(SRC_PATH, open(os.path.join(ROOT, '
                         'SRC_PATH), encoding="utf-8").read()))  # XA-1 Gold defaults stripped -> f253890 text '
                         '(delta pinned by xa_sim)\n'
                         '\n')],
 'tests/jpy_sim.py': [('ROOT = jb.ROOT\n'
                       'VIS = open(os.path.join(ROOT, jb.SRC_PATH), encoding="utf-8").read()\n'
                       'JPY = __import__("uj_build").pre_uj(jb.JPY_PATH) if os.path.exists(os.path.join(ROOT, '
                       'jb.JPY_PATH)) else ""     # UJ-1: USDJPY Visual / Strategy may differ only by the USDJPY '
                       'Engine split + sizing (exact, see uj_build)\n',
                       'ROOT = jb.ROOT\n'
                       'VIS = __import__("xa_build").pre_xa(jb.SRC_PATH, open(os.path.join(ROOT, jb.SRC_PATH), '
                       'encoding="utf-8").read())  # XA-1 Gold defaults stripped -> f253890 text (delta pinned by '
                       'xa_sim)\n'
                       'JPY = __import__("uj_build").pre_uj(jb.JPY_PATH) if os.path.exists(os.path.join(ROOT, '
                       'jb.JPY_PATH)) else ""     # UJ-1: USDJPY Visual / Strategy may differ only by the USDJPY '
                       'Engine split + sizing (exact, see uj_build)\n'),
                      ('    check("JS-10 XAUUSD Visual (ZONE-P), Strategy (ZONE-ST), Engines (/2, /5, /6) and the '
                       'old strategies unchanged vs 25af623",\n'
                       '          d.strip() == "", d)\n'
                       '\n',
                       '    check("JS-10 XAUUSD Visual (ZONE-P), Strategy (ZONE-ST), Engines (/2, /5, /6) and the '
                       'old strategies unchanged vs 25af623",\n'
                       '          __import__("xa_build").drop_xa(d.split(), "25af623") == [], d)\n'
                       '\n')],
 'tests/nr_a1_sim.py': [('ROOT = na.ROOT\n'
                         'CUR = open(os.path.join(ROOT, "ZoneVisualPractical.pine"), encoding="utf-8").read()\n'
                         'CUR = __import__("bon_build").strip_bon(CUR) or CUR  # bonus defaults stripped -> 9270c50 '
                         'text (delta pinned by bon_sim)\n',
                         'ROOT = na.ROOT\n'
                         'CUR = __import__("xa_build").pre_xa("ZoneVisualPractical.pine", open(os.path.join(ROOT, '
                         '"ZoneVisualPractical.pine"), encoding="utf-8").read())  # XA-1 Gold defaults stripped -> '
                         'f253890 text (delta pinned by xa_sim)\n'
                         'CUR = __import__("bon_build").strip_bon(CUR) or CUR  # bonus defaults stripped -> 9270c50 '
                         'text (delta pinned by bon_sim)\n')],
 'tests/nr_s1_sim.py': [('ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))\n'
                         'CUR = open(os.path.join(ROOT, "ZoneVisualPractical.pine"), encoding="utf-8").read()\n'
                         'CUR = __import__("bon_build").strip_bon(CUR) or CUR  # bonus defaults stripped -> 9270c50 '
                         'text (delta pinned by bon_sim)\n',
                         'ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))\n'
                         'CUR = __import__("xa_build").pre_xa("ZoneVisualPractical.pine", open(os.path.join(ROOT, '
                         '"ZoneVisualPractical.pine"), encoding="utf-8").read())  # XA-1 Gold defaults stripped -> '
                         'f253890 text (delta pinned by xa_sim)\n'
                         'CUR = __import__("bon_build").strip_bon(CUR) or CUR  # bonus defaults stripped -> 9270c50 '
                         'text (delta pinned by bon_sim)\n')],
 'tests/practical_strategy_sim.py': [('VIS_PRE_GATE_REV = "b3b69ae"\n'
                                      'VIS_CUR = open(os.path.join(ROOT, "ZoneVisualPractical.pine"), '
                                      'encoding="utf-8").read()\n'
                                      'VIS_CUR = __import__("bon_build").strip_bon(VIS_CUR) or VIS_CUR  # bonus '
                                      'defaults stripped -> 9270c50 text (delta pinned by bon_sim)\n',
                                      'VIS_PRE_GATE_REV = "b3b69ae"\n'
                                      'VIS_CUR = __import__("xa_build").pre_xa("ZoneVisualPractical.pine", '
                                      'open(os.path.join(ROOT, "ZoneVisualPractical.pine"), '
                                      'encoding="utf-8").read())  # XA-1 Gold defaults stripped -> f253890 text '
                                      '(delta pinned by xa_sim)\n'
                                      'VIS_CUR = __import__("bon_build").strip_bon(VIS_CUR) or VIS_CUR  # bonus '
                                      'defaults stripped -> 9270c50 text (delta pinned by bon_sim)\n')],
 'tests/rn1_sim.py': [('    d = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", rb.RN_BASE_REV, "--"] + '
                       'prod, capture_output=True, text=True).stdout\n'
                       '    vis = open(os.path.join(ROOT, "ZoneVisualPractical.pine"), encoding="utf-8").read()\n'
                       '    vis = __import__("bon_build").strip_bon(vis) or vis  # bonus defaults stripped -> '
                       '9270c50 text (delta pinned by bon_sim)\n',
                       '    d = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", rb.RN_BASE_REV, "--"] + '
                       'prod, capture_output=True, text=True).stdout\n'
                       '    vis = __import__("xa_build").pre_xa("ZoneVisualPractical.pine", open(os.path.join(ROOT, '
                       '"ZoneVisualPractical.pine"), encoding="utf-8").read())  # XA-1 Gold defaults stripped -> '
                       'f253890 text (delta pinned by xa_sim)\n'
                       '    vis = __import__("bon_build").strip_bon(vis) or vis  # bonus defaults stripped -> '
                       '9270c50 text (delta pinned by bon_sim)\n')],
 'tests/rnv_sim.py': [('ROOT = vb.ROOT\n'
                       'CUR = open(os.path.join(ROOT, "ZoneVisualPractical.pine"), encoding="utf-8").read()\n'
                       'CUR = __import__("bon_build").strip_bon(CUR) or CUR  # bonus defaults stripped -> 9270c50 '
                       'text (delta pinned by bon_sim)\n',
                       'ROOT = vb.ROOT\n'
                       'CUR = __import__("xa_build").pre_xa("ZoneVisualPractical.pine", open(os.path.join(ROOT, '
                       '"ZoneVisualPractical.pine"), encoding="utf-8").read())  # XA-1 Gold defaults stripped -> '
                       'f253890 text (delta pinned by xa_sim)\n'
                       'CUR = __import__("bon_build").strip_bon(CUR) or CUR  # bonus defaults stripped -> 9270c50 '
                       'text (delta pinned by bon_sim)\n')],
 'tests/st1_sim.py': [('ROOT = tb.ROOT\n'
                       'ST = s2.strip_st2(s3.strip_st3(open(os.path.join(ROOT, tb.ST_PATH), '
                       'encoding="utf-8").read())) if os.path.exists(os.path.join(ROOT, tb.ST_PATH)) else ""\n'
                       'VIS = open(os.path.join(ROOT, "ZoneVisualPractical.pine"), encoding="utf-8").read()\n'
                       'BASE = tb.git_show(tb.ST_BASE_REV)\n',
                       'ROOT = tb.ROOT\n'
                       'ST = s2.strip_st2(s3.strip_st3(__import__("xa_build").pre_xa("ZoneStrategyXAU.pine", '
                       'open(os.path.join(ROOT, tb.ST_PATH), encoding="utf-8").read()))) if '
                       'os.path.exists(os.path.join(ROOT, tb.ST_PATH)) else ""\n'
                       'VIS = __import__("xa_build").pre_xa("ZoneVisualPractical.pine", open(os.path.join(ROOT, '
                       '"ZoneVisualPractical.pine"), encoding="utf-8").read())  # XA-1 Gold defaults stripped -> '
                       'f253890 text (delta pinned by xa_sim)\n'
                       'BASE = tb.git_show(tb.ST_BASE_REV)\n'),
                      ('    d = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", tb.ST_BASE_REV, "--"] + '
                       'names, capture_output=True, text=True).stdout\n'
                       '    check("TS-12 ZONE-P, Engines (/2, /5, /6), Strategy LONG / SHORT, SignalEngine unchanged '
                       'vs beca989", d.strip() == "", d)\n'
                       '\n',
                       '    d = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", tb.ST_BASE_REV, "--"] + '
                       'names, capture_output=True, text=True).stdout\n'
                       '    check("TS-12 ZONE-P, Engines (/2, /5, /6), Strategy LONG / SHORT, SignalEngine unchanged '
                       'vs beca989", __import__("xa_build").drop_xa(d.split(), tb.ST_BASE_REV) == [], d)\n'
                       '\n')],
 'tests/st2_sim.py': [('ROOT = tb.ROOT\n'
                       'ST = s3.strip_st3(open(os.path.join(ROOT, s2.ST_PATH), encoding="utf-8").read())\n'
                       'RESULTS = []\n',
                       'ROOT = tb.ROOT\n'
                       'ST = s3.strip_st3(__import__("xa_build").pre_xa("ZoneStrategyXAU.pine", '
                       'open(os.path.join(ROOT, s2.ST_PATH), encoding="utf-8").read()))  # XA-1 Gold defaults '
                       'stripped -> f253890 text (delta pinned by xa_sim)\n'
                       'RESULTS = []\n'),
                      ('    d = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", "f1d54bf", "--"] + names, '
                       'capture_output=True, text=True).stdout\n'
                       '    check("TS-11 ZONE-P, Engines (/2, /5, /6), Strategy LONG / SHORT, SignalEngine unchanged '
                       'vs f1d54bf", d.strip() == "", d)\n'
                       '\n',
                       '    d = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", "f1d54bf", "--"] + names, '
                       'capture_output=True, text=True).stdout\n'
                       '    check("TS-11 ZONE-P, Engines (/2, /5, /6), Strategy LONG / SHORT, SignalEngine unchanged '
                       'vs f1d54bf", __import__("xa_build").drop_xa(d.split(), "f1d54bf") == [], d)\n'
                       '\n')],
 'tests/st3_sim.py': [('ROOT = s3.ROOT\n'
                       'ST = open(os.path.join(ROOT, s3.ST_PATH), encoding="utf-8").read()\n'
                       'RESULTS = []\n',
                       'ROOT = s3.ROOT\n'
                       'ST = __import__("xa_build").pre_xa("ZoneStrategyXAU.pine", open(os.path.join(ROOT, '
                       's3.ST_PATH), encoding="utf-8").read())  # XA-1 Gold defaults stripped -> f253890 text (delta '
                       'pinned by xa_sim)\n'
                       'RESULTS = []\n'),
                      ('    d = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", "f1d54bf", "--"] + names, '
                       'capture_output=True, text=True).stdout\n'
                       '    check("TS-09 ZONE-P, Engines (/2, /5, /6), Strategy LONG / SHORT, SignalEngine '
                       'unchanged", d.strip() == "", d)\n'
                       '\n',
                       '    d = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", "f1d54bf", "--"] + names, '
                       'capture_output=True, text=True).stdout\n'
                       '    check("TS-09 ZONE-P, Engines (/2, /5, /6), Strategy LONG / SHORT, SignalEngine '
                       'unchanged", __import__("xa_build").drop_xa(d.split(), "f1d54bf") == [], d)\n'
                       '\n')],
 'tests/stj_sim.py': [('JPYV = __import__("uj_build").pre_uj(jb.JPY_PATH)\n'
                       'XST = open(os.path.join(ROOT, "ZoneStrategyXAU.pine"), encoding="utf-8").read()\n'
                       'RESULTS = []\n',
                       'JPYV = __import__("uj_build").pre_uj(jb.JPY_PATH)\n'
                       'XST = __import__("xa_build").pre_xa("ZoneStrategyXAU.pine", open(os.path.join(ROOT, '
                       '"ZoneStrategyXAU.pine"), encoding="utf-8").read())  # XA-1 Gold defaults stripped -> f253890 '
                       'text (delta pinned by xa_sim)\n'
                       'RESULTS = []\n')],
 'tests/sw1_sim.py': [('    d = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", sb.SW_BASE_REV, "--"] + '
                       'names, capture_output=True, text=True).stdout\n'
                       '    vis = open(os.path.join(ROOT, "ZoneVisualPractical.pine"), encoding="utf-8").read()\n'
                       '    vis = __import__("bon_build").strip_bon(vis) or vis  # bonus defaults stripped -> '
                       '9270c50 text (delta pinned by bon_sim)\n',
                       '    d = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", sb.SW_BASE_REV, "--"] + '
                       'names, capture_output=True, text=True).stdout\n'
                       '    vis = __import__("xa_build").pre_xa("ZoneVisualPractical.pine", open(os.path.join(ROOT, '
                       '"ZoneVisualPractical.pine"), encoding="utf-8").read())  # XA-1 Gold defaults stripped -> '
                       'f253890 text (delta pinned by xa_sim)\n'
                       '    vis = __import__("bon_build").strip_bon(vis) or vis  # bonus defaults stripped -> '
                       '9270c50 text (delta pinned by bon_sim)\n')],
 'tests/swv_sim.py': [('ROOT = wb.ROOT\n'
                       'CUR = open(os.path.join(ROOT, "ZoneVisualPractical.pine"), encoding="utf-8").read()\n'
                       'CUR = __import__("bon_build").strip_bon(CUR) or CUR  # bonus defaults stripped -> 9270c50 '
                       'text (delta pinned by bon_sim)\n',
                       'ROOT = wb.ROOT\n'
                       'CUR = __import__("xa_build").pre_xa("ZoneVisualPractical.pine", open(os.path.join(ROOT, '
                       '"ZoneVisualPractical.pine"), encoding="utf-8").read())  # XA-1 Gold defaults stripped -> '
                       'f253890 text (delta pinned by xa_sim)\n'
                       'CUR = __import__("bon_build").strip_bon(CUR) or CUR  # bonus defaults stripped -> 9270c50 '
                       'text (delta pinned by bon_sim)\n')],
 'tests/uj_build.py': [('    # BTE-1 (later split of the BTC Engine): the BTC Visual / Strategy may also differ, '
                        'exactly by that layer\n'
                        '    return [n for n in names if not ((n in UJ_FILES and uj_ok(n, rev)) or '
                        '__import__("bte_build").bte_pine_ok(n, rev))]\n'
                        '\n',
                        '    # BTE-1 (later split of the BTC Engine): the BTC Visual / Strategy may also differ, '
                        'exactly by that layer\n'
                        '    # XA-1 (Gold defaults): ZONE-P / ZONE-ST may also differ, exactly by that layer\n'
                        '    return [n for n in names if not ((n in UJ_FILES and uj_ok(n, rev)) or '
                        '__import__("bte_build").bte_pine_ok(n, rev)\n'
                        '                                     or __import__("xa_build").xa_ok(n, rev))]\n'
                        '\n'),
                       ('    """True when the test file differs from BASE_REV only by its exact UJ-1 adaptation."""\n'
                        '    return (path in TEST_ADAPT or path in __import__("bte_build").TEST_ADAPT) and '
                        'unadapt(path, _rd(path)) == base(path)\n'
                        '\n',
                        '    """True when the test file differs from BASE_REV only by its exact UJ-1 adaptation."""\n'
                        '    return (path in TEST_ADAPT or path in __import__("bte_build").TEST_ADAPT or path in '
                        '__import__("xa_build").TEST_ADAPT) \\\n'
                        '        and unadapt(path, _rd(path)) == base(path)\n'
                        '\n')],
 'tests/uj_sim.py': [('    mod = git("diff", "--name-only", "--diff-filter=MDR", ub.BASE_REV, "--").split()\n'
                      '    mod = [m for m in mod if not __import__("bte_build").bte_pine_ok(m, ub.BASE_REV)]     # '
                      'BTE-1 BTC split: exact\n'
                      '    rest = [m for m in mod if m not in ub.UJ_FILES and not ub.test_ok(m)]\n',
                      '    mod = git("diff", "--name-only", "--diff-filter=MDR", ub.BASE_REV, "--").split()\n'
                      '    mod = [m for m in mod if not (__import__("bte_build").bte_pine_ok(m, ub.BASE_REV) or '
                      '__import__("xa_build").xa_ok(m, ub.BASE_REV))]     # BTE-1 / XA-1: exact\n'
                      '    rest = [m for m in mod if m not in ub.UJ_FILES and not ub.test_ok(m)]\n'),
                     ('    mod = git("diff", "--name-only", "--diff-filter=MDR", UJ1, "--").split()\n'
                      '    mod = [m for m in mod if not (__import__("bte_build").bte_pine_ok(m, UJ1) or '
                      '__import__("bte_build").test_ok(m))]   # BTE-1: exact\n'
                      '    check("UD-07 vs a6a275c only the USDJPY Visual / Strategy and their build / test change '
                      '(Engine, other symbols, shared "\n',
                      '    mod = git("diff", "--name-only", "--diff-filter=MDR", UJ1, "--").split()\n'
                      '    mod = [m for m in mod if not (__import__("bte_build").bte_pine_ok(m, UJ1) or '
                      '__import__("bte_build").test_ok(m)\n'
                      '                                  or __import__("xa_build").xa_ok(m, UJ1) or '
                      '__import__("xa_build").test_ok(m))]   # BTE-1 / XA-1: exact\n'
                      '    check("UD-07 vs a6a275c only the USDJPY Visual / Strategy and their build / test change '
                      '(Engine, other symbols, shared "\n')],
 'tests/zp_overlap_sim.py': [('ROOT = zp.ROOT\n'
                              'CUR = open(os.path.join(ROOT, "ZoneVisualPractical.pine"), encoding="utf-8").read()\n'
                              'CUR = __import__("bon_build").strip_bon(CUR) or CUR  # bonus defaults stripped -> '
                              '9270c50 text (delta pinned by bon_sim)\n',
                              'ROOT = zp.ROOT\n'
                              'CUR = __import__("xa_build").pre_xa("ZoneVisualPractical.pine", '
                              'open(os.path.join(ROOT, "ZoneVisualPractical.pine"), encoding="utf-8").read())  # '
                              'XA-1 Gold defaults stripped -> f253890 text (delta pinned by xa_sim)\n'
                              'CUR = __import__("bon_build").strip_bon(CUR) or CUR  # bonus defaults stripped -> '
                              '9270c50 text (delta pinned by bon_sim)\n')]}
