"""UJ-1 — USDJPY dedicated Engine + GBPJPY position sizing (OANDA:USDJPY 5M).

  ZoneEnginePracticalSwingMax.pine (= the source of the published ZoneEnginePractical/6: commit 110e5b0 created it
  (SW-1) and the next commit 67f8fd2 switched the Visual import /5 -> /6 "Swing max-score, SW-1"; the file is unchanged
  since) -> ZoneEnginePracticalUSDJPY.pine: library name and header only (same computation and API).
  ZoneVisualUSDJPY.pine / ZoneStrategyUSDJPY.pine: import ZoneEnginePracticalUSDJPY/1 (to be published) instead of
  ZoneEnginePractical/6; the Visual's Zone Half Width default becomes the Strategy's 0.03 円 (user decision, so the shared
  Zone defaults match; Direction stays Long Only); the Strategy also gets the GBPJPY position sizing (gbs_build QTY_EDITS, the sizing parts only:
  initial capital 300,000 JPY in JPY, 元金基準額 300,000 円 x 3 % fixed (simple), 1 lot = 100,000, step 0.01, f_stQty =
  floor(budget / (distance x syminfo.pointvalue x lot step units)), qty on both the limit and the market entry, no order
  (and no order / Track state) when the quantity is invalid or below one step). The GBPJPY alert-text edits of GBS-4 are
  not taken (alerts / labels are out of scope).
Each strip_*() reverses its edits and must give the source back byte for byte (fixture uj_sim).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gbs_build as gs  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENG_SRC, ENG_PATH = "ZoneEnginePracticalSwingMax.pine", "ZoneEnginePracticalUSDJPY.pine"
VIS_PATH, STR_PATH = "ZoneVisualUSDJPY.pine", "ZoneStrategyUSDJPY.pine"
IMPORT_6 = "import sekine3310/ZoneEnginePractical/6 as zn\n"
IMPORT_UJ = "import sekine3310/ZoneEnginePracticalUSDJPY/1 as zn\n"     # first publish of the new library = version 1
BASE_REV = "3568c05"                                                    # the USDJPY Visual / Strategy before UJ-1

ENGINE_EDITS = [
    ("header",
     "//  ZoneEnginePractical  —  Practical Zone v1 (Support / Resistance Zone Engine)\n",
     "//  ZoneEnginePractical  —  Practical Zone v1 (Support / Resistance Zone Engine)\n"
     "//  ★ USDJPY 専用 (ZoneEnginePracticalUSDJPY、生成: tests/uj_build.py、UJ-1)。公開版 ZoneEnginePractical/6 の\n"
     "//    ソース (ZoneEnginePracticalSwingMax.pine) と同じ処理・公開 API で、違いは Library 名だけ (fixture uj_sim が固定)。\n"),
    ("name",
     'library("ZoneEnginePractical", overlay = true)\n',
     'library("ZoneEnginePracticalUSDJPY", overlay = true)\n'),
]

VISUAL_EDITS = [
    ("header",
     "//  Zone Visual USDJPY (Compare)  —  OANDA:USDJPY 5分足用 Zone 比較 Indicator (Entry なし)\n",
     "//  Zone Visual USDJPY (Compare)  —  OANDA:USDJPY 5分足用 Zone 比較 Indicator (Entry なし)\n"
     "//  UJ-1: Engine を USDJPY 専用 Library ZoneEnginePracticalUSDJPY (公開版 /6 と同じ処理) に分離 (生成: tests/uj_build.py)。\n"),
    ("import", IMPORT_6, IMPORT_UJ),
    # user decision (UJ-1): the shared Zone Half Width is the Strategy's 0.03 円 (the Visual had 0.05) so both files match
    ("default",
     'zoneHalfWidth = input.float(0.05, "Zone Half Width (円)", minval = 0.005, step = 0.005, group = G_ZONE,\n',
     'zoneHalfWidth = input.float(0.03, "Zone Half Width (円)", minval = 0.005, step = 0.005, group = G_ZONE,\n'),
    ("header",
     "//  Cluster Distance 0.05 / 0.08 / 0.12 円 (初期 0.05 / 0.08)。他の円換算値は暫定 ([暫定] 表記)。\n",
     "//  Cluster Distance 0.05 / 0.08 / 0.12 円 (初期 0.05 / 0.08)。他の円換算値は暫定 ([暫定] 表記)。\n"
     "//  UJ-1: Zone Half Width の初期値を Strategy と同じ 0.03 円に統一 (ユーザー指定。上の「初期 0.05」は UJ-1 前の値)。\n"),
]

# GBPJPY sizing block (gbs_build.QTY_INPUTS) with only the unit comment adapted to USDJPY; the code lines are identical
QTY_INPUTS_UJ = gs.QTY_INPUTS.replace(
    "// 数量 (通貨数、GBP): 参照価格 ref と固定 SL の距離から、損失予算を超えない最大の lot 刻みの倍数。\n"
    "//  損失 (円) = qty × 距離 × syminfo.pointvalue (OANDA:GBPJPY は 1)。無効 / 最小 lot 未満は na (発注しない)\n",
    "// 数量 (通貨数、USD): 参照価格 ref と固定 SL の距離から、損失予算を超えない最大の lot 刻みの倍数。\n"
    "//  損失 (円) = qty × 距離 × syminfo.pointvalue (USDJPY の損益は円建てなので為替換算は不要。pointvalue は固定値にしない)。\n"
    "//  無効 / SL の向き不正 / 距離 0 / 最小 lot 未満は na (発注しない)。参照価格 (A: 指値 / B, C, D: 確定足の終値) に対する\n"
    "//  予定損失の計算であり、約定価格のずれ・スプレッド等を含む実損失の上限ではない (GBPJPY 版 f_stQty と同じ式)\n")
assert QTY_INPUTS_UJ != gs.QTY_INPUTS

_Q = {a: b for a, b in gs.QTY_EDITS}
_cap_old = "     initial_capital        = 10000,\n"
_sta_old = 'var string G_STA = "03 · Strategy Alerts"\n'
_ref_old = ("            [skipRef, tpRef] = f_stTp(side, ref, pSL, f_stNearest(side == 1 ? tpUp : tpDn, side, ref))\n"
            "            if not skipRef\n")
_lim_old = "                    strategy.entry(oEid, side == 1 ? strategy.long : strategy.short, limit = oL)\n"
_mkt_old = "                    strategy.entry(oEid, side == 1 ? strategy.long : strategy.short)\n"

STRATEGY_EDITS = [
    ("header",
     "//  Zone Strategy USDJPY  —  ZONE-JPY (ZoneVisualUSDJPY) の Zone 判定をそのまま使う OANDA:USDJPY 5分足 Strategy\n",
     "//  Zone Strategy USDJPY  —  ZONE-JPY (ZoneVisualUSDJPY) の Zone 判定をそのまま使う OANDA:USDJPY 5分足 Strategy\n"
     "//  UJ-1 (生成: tests/uj_build.py): Engine を USDJPY 専用 Library ZoneEnginePracticalUSDJPY (公開版 /6 と同じ処理) に分離し、\n"
     "//  資金管理を GBPJPY 版と同じにした (初期資金 300,000 円・JPY、元金基準額 300,000 円 × 3 % の単利の損失予算、\n"
     "//  1 lot = 100,000 通貨、0.01 lot で切り捨て、指値・成行とも qty を明示)。売買設定・判定・注文タイミングは変えない。\n"),
    ("import", IMPORT_6, IMPORT_UJ),
    ("size", _cap_old, _Q[_cap_old]),
    ("size", _sta_old, QTY_INPUTS_UJ + _sta_old),
    ("size", _ref_old, _Q[_ref_old]),
    ("size", _lim_old, _Q[_lim_old]),
    ("size", _mkt_old, _Q[_mkt_old]),
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


def base(path):
    """the USDJPY file before UJ-1 (commit BASE_REV)."""
    import subprocess
    return subprocess.run(["git", "-C", ROOT, "show", f"{BASE_REV}:{path}"], capture_output=True, text=True).stdout


def build_engine():
    return _apply(_rd(ENG_SRC), ENGINE_EDITS)


def build_visual():
    return _apply(base(VIS_PATH), VISUAL_EDITS)


def build_strategy():
    return _apply(base(STR_PATH), STRATEGY_EDITS)


def strip_engine(t):
    return _revert(t, ENGINE_EDITS)


def strip_visual(t):
    return _revert(t, VISUAL_EDITS)


def strip_strategy(t):
    return _revert(t, STRATEGY_EDITS)


if __name__ == "__main__":
    for path, fn in ((ENG_PATH, build_engine), (VIS_PATH, build_visual), (STR_PATH, build_strategy)):
        open(os.path.join(ROOT, path), "w", encoding="utf-8").write(fn())
        print("written", path)


# ---- helpers for the older fixtures (they pin the USDJPY files as they were before UJ-1) ------------------------------
UJ_FILES = (VIS_PATH, STR_PATH)


def pre_uj(path, text=None):
    """the USDJPY Visual / Strategy text with the UJ-1 edits reverted (unchanged if they are not present)."""
    if text is None:
        text = _rd(path)
    s = (strip_visual if path == VIS_PATH else strip_strategy)(text)
    return text if s is None else s


def uj_ok(path, rev):
    """True when the working-tree file differs from `rev` only by the UJ-1 edits (exact, byte for byte)."""
    import subprocess
    old = subprocess.run(["git", "-C", ROOT, "show", f"{rev}:{path}"], capture_output=True, text=True).stdout
    s = (strip_visual if path == VIS_PATH else strip_strategy)(_rd(path))
    return s is not None and s == old


def drop_uj(names, rev):
    """remove the USDJPY files from a list of changed paths only when they differ from `rev` exactly by UJ-1."""
    return [n for n in names if not (n in UJ_FILES and uj_ok(n, rev))]


# ---- exact adaptations of the older fixtures to UJ-1 (each must occur once; unadapt() reverses them) ---------------
TEST_ADAPT = {'tests/btc_sim.py': [('    check(f"BS-15 existing files unchanged vs base HEAD {BASE}',
                       '    out, out1, out2 = '
                       '(__import__("uj_build").drop_uj_tests(__import__("uj_build").drop_uj(out, BASE)), '
                       '__import__("uj_build").drop_uj_tests(__import__("uj_build").drop_uj(out1, BTC1_COMMIT)),\n'
                       '                       '
                       '__import__("uj_build").drop_uj_tests(__import__("uj_build").drop_uj(out2, BTC2_COMMIT)))     '
                       '# UJ-1: USDJPY Visual / Strategy may differ only by the USDJPY Engine split + sizing (exact, '
                       'see uj_build)\n'
                       '    check(f"BS-15 existing files unchanged vs base HEAD {BASE}')],
 'tests/btcs_sim.py': [('    check(f"SB-17 existing files unchanged vs {BASE}',
                        '    out, out2 = __import__("uj_build").drop_uj_tests(__import__("uj_build").drop_uj(out, '
                        'BASE)), __import__("uj_build").drop_uj_tests(__import__("uj_build").drop_uj(out2, '
                        'BTS1_COMMIT))     # UJ-1: USDJPY Visual / Strategy may differ only by the USDJPY Engine '
                        'split + sizing (exact, see uj_build)\n'
                        '    check(f"SB-17 existing files unchanged vs {BASE}'),
                       ('    return old.count(BTC_SIM_OLD) == 1 and rd("tests/btc_sim.py") == exp\n',
                        '    return old.count(BTC_SIM_OLD) == 1 and '
                        '__import__("uj_build").unadapt("tests/btc_sim.py", rd("tests/btc_sim.py")) == exp\n')],
 'tests/eu_sim.py': [('          set(mod) <= {"tests/btc_sim.py", "tests/btcs_sim.py"} and rd("tests/btc_sim.py") == '
                      'exp_btc\n'
                      '          and rd("tests/btcs_sim.py") == exp_bts and exp_bts != show("tests/btcs_sim.py"), '
                      'str(mod))',
                      '          set(__import__("uj_build").drop_uj_tests(__import__("uj_build").drop_uj(mod, '
                      'BASE))) <= {"tests/btc_sim.py", "tests/btcs_sim.py"}\n'
                      '          and __import__("uj_build").unadapt("tests/btc_sim.py", rd("tests/btc_sim.py")) == '
                      'exp_btc\n'
                      '          and __import__("uj_build").unadapt("tests/btcs_sim.py", rd("tests/btcs_sim.py")) == '
                      'exp_bts and exp_bts != show("tests/btcs_sim.py"), str(mod))'),
                     ('"USDJPY / Gold files untouched)", set(mod) <= {eb.VIS_PATH, eb.STR_PATH, "tests/eu_build.py", '
                      '"tests/eu_sim.py"}',
                      '"USDJPY / Gold files untouched)", '
                      'set(__import__("uj_build").drop_uj_tests(__import__("uj_build").drop_uj(mod, EU1))) <= '
                      '{eb.VIS_PATH, eb.STR_PATH, "tests/eu_build.py", "tests/eu_sim.py"}')],
 'tests/gbd_sim.py': [('d.returncode == 0 and d.stdout.strip() == "" and '
                       'all(re.match(r"^tests/gb[defjsx]_\\w+\\.py$", f) for f in t.split()),',
                       'd.returncode == 0 and __import__("uj_build").drop_uj(d.stdout.split(), PREV) == [] and '
                       'all(re.match(r"^tests/gb[defjsx]_\\w+\\.py$", f) for f in '
                       '__import__("uj_build").drop_uj_tests(t.split())),')],
 'tests/gbe_sim.py': [('d.returncode == 0 and d.stdout.strip() == "" and all(re.match(r"^tests/gb[ejsx]_\\w+\\.py$", '
                       'f) for f in t.split()),',
                       'd.returncode == 0 and __import__("uj_build").drop_uj(d.stdout.split(), PREV) == [] and '
                       'all(re.match(r"^tests/gb[ejsx]_\\w+\\.py$", f) for f in '
                       '__import__("uj_build").drop_uj_tests(t.split())),')],
 'tests/gbf_sim.py': [('d.returncode == 0 and d.stdout.strip() == "" and '
                       'all(re.match(r"^tests/gb[efjsx]_\\w+\\.py$", f) for f in t.split()),',
                       'd.returncode == 0 and __import__("uj_build").drop_uj(d.stdout.split(), PREV) == [] and '
                       'all(re.match(r"^tests/gb[efjsx]_\\w+\\.py$", f) for f in '
                       '__import__("uj_build").drop_uj_tests(t.split())),')],
 'tests/gbj_build.py': [('    return gbj_transform(open(os.path.join(ROOT, SRC_PATH), encoding="utf-8").read())\n',
                         '    return gbj_transform(__import__("uj_build").pre_uj(SRC_PATH))     # UJ-1: USDJPY '
                         'Visual / Strategy may differ only by the USDJPY Engine split + sizing (exact, see '
                         'uj_build)\n')],
 'tests/gbj_sim.py': [('JPY = open(os.path.join(ROOT, gb.SRC_PATH), encoding="utf-8").read()\n',
                       'JPY = __import__("uj_build").pre_uj(gb.SRC_PATH)     # UJ-1: USDJPY Visual / Strategy may '
                       'differ only by the USDJPY Engine split + sizing (exact, see uj_build)\n'),
                      ('"unchanged vs base HEAD " + BASE, d.returncode == 0 and d.stdout.strip() == "", d.stdout + '
                       'd.stderr)',
                       '"unchanged vs base HEAD " + BASE, d.returncode == 0 and '
                       '__import__("uj_build").drop_uj(d.stdout.split(), BASE) == [], d.stdout + d.stderr)'),
                      ('"jpy_build still regenerates ZONE-JPY", j.strip() == "" and jb.build() == JPY, j)',
                       '"jpy_build still regenerates ZONE-JPY", __import__("uj_build").drop_uj_tests(j.split()) == '
                       '[] and jb.build() == JPY, j)')],
 'tests/gbn_sim.py': [('d.returncode == 0 and d.stdout.strip() == "" and re.findall(r"^import .*$", GBS, re.M) == '
                       '[ge.IMPORT_GBE.strip()],',
                       'd.returncode == 0 and __import__("uj_build").drop_uj(d.stdout.split(), PREV) == [] and '
                       're.findall(r"^import .*$", GBS, re.M) == [ge.IMPORT_GBE.strip()],')],
 'tests/gbq_sim.py': [('d.returncode == 0 and d.stdout.strip() == "" and re.findall(r"^import .*$", G4, re.M) == '
                       '[ge.IMPORT_GBE.strip()],',
                       'd.returncode == 0 and __import__("uj_build").drop_uj(d.stdout.split(), PREV) == [] and '
                       're.findall(r"^import .*$", G4, re.M) == [ge.IMPORT_GBE.strip()],')],
 'tests/gbs_sim.py': [('          d.returncode == 0 and d.stdout.strip() == ""\n'
                       '          and all(re.match(r"^tests/gb[jsx]_\\w+\\.py$", f) for f in t.split()), d.stdout + '
                       't)',
                       '          d.returncode == 0 and __import__("uj_build").drop_uj(d.stdout.split(), BASE) == '
                       '[]\n'
                       '          and all(re.match(r"^tests/gb[jsx]_\\w+\\.py$", f) for f in '
                       '__import__("uj_build").drop_uj_tests(t.split())), d.stdout + t)'),
                      ('STJ = rd(sj.STJ_PATH)\n',
                       'STJ = __import__("uj_build").pre_uj(sj.STJ_PATH)     # UJ-1: USDJPY Visual / Strategy may '
                       'differ only by the USDJPY Engine split + sizing (exact, see uj_build)\n')],
 'tests/gbx_sim.py': [('d.returncode == 0 and d.stdout.strip() == "" and all(re.match(r"^tests/gb[jsx]_\\w+\\.py$", '
                       'f) for f in t.split()),',
                       'd.returncode == 0 and __import__("uj_build").drop_uj(d.stdout.split(), BASE) == [] and '
                       'all(re.match(r"^tests/gb[jsx]_\\w+\\.py$", f) for f in '
                       '__import__("uj_build").drop_uj_tests(t.split())),')],
 'tests/gu_sim.py': [('"new GBPUSD files are added", mod == [], str(mod))',
                      '"new GBPUSD files are added", '
                      '__import__("uj_build").drop_uj_tests(__import__("uj_build").drop_uj(mod, BASE)) == [], '
                      'str(mod))')],
 'tests/jpy_sim.py': [('JPY = open(os.path.join(ROOT, jb.JPY_PATH), encoding="utf-8").read() if '
                       'os.path.exists(os.path.join(ROOT, jb.JPY_PATH)) else ""\n',
                       'JPY = __import__("uj_build").pre_uj(jb.JPY_PATH) if os.path.exists(os.path.join(ROOT, '
                       'jb.JPY_PATH)) else ""     # UJ-1: USDJPY Visual / Strategy may differ only by the USDJPY '
                       'Engine split + sizing (exact, see uj_build)\n')],
 'tests/stj_sim.py': [('STJ = open(os.path.join(ROOT, sj.STJ_PATH), encoding="utf-8").read() if '
                       'os.path.exists(os.path.join(ROOT, sj.STJ_PATH)) else ""\n'
                       'JPYV = open(os.path.join(ROOT, jb.JPY_PATH), encoding="utf-8").read()\n',
                       'STJ = __import__("uj_build").pre_uj(sj.STJ_PATH) if os.path.exists(os.path.join(ROOT, '
                       'sj.STJ_PATH)) else ""     # UJ-1: USDJPY Visual / Strategy may differ only by the USDJPY '
                       'Engine split + sizing (exact, see uj_build)\n'
                       'JPYV = __import__("uj_build").pre_uj(jb.JPY_PATH)\n'),
                      ('          d.strip() == "", d)\n',
                       '          __import__("uj_build").drop_uj(d.split(), "5e2459b") == [], d)\n')]}


def unadapt(path, text):
    """a test file with its UJ-1 adaptation reverted (unchanged for files not in TEST_ADAPT)."""
    out = text
    for a, b in reversed(TEST_ADAPT.get(path, [])):
        if out.count(b) != 1:
            return None
        out = out.replace(b, a)
    return out


def test_ok(path):
    """True when the test file differs from BASE_REV only by its exact UJ-1 adaptation."""
    return path in TEST_ADAPT and unadapt(path, _rd(path)) == base(path)


def drop_uj_tests(names):
    """remove adapted test files from a changed-path list only when they differ from BASE_REV exactly by TEST_ADAPT."""
    return [n for n in names if not test_ok(n)]
