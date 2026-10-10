"""RN-1 Gate V1 — ZoneVisualPractical.pine: exact transform of the Visual @ 6e554b2.

  1. import ZoneEnginePractical/2 -> /5 (the published RN-1 version = ZoneEnginePracticalRN.pine)
  2. input "Enable Round Number" (default ON) in its own group after the Accum groups
  3. zoneCfg.useRnSource := enableRn and syminfo.ticker == "XAUUSD"  (exact ticker; 100 / 3, 50 / 2 = Library defaults)
Nothing else: NR-S1, NR-A1, FVG A / C, the overlap-only display, MA / Break and the draw pass are byte-identical.
"""
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RNV_BASE_REV = "6e554b2"
IMPORT_OLD = "import sekine3310/ZoneEnginePractical/2 as zn\n"
IMPORT_NEW = "import sekine3310/ZoneEnginePractical/5 as zn\n"
RN_CFG_LINE = 'zoneCfg.useRnSource          := enableRn and syminfo.ticker == "XAUUSD"\n'

RNV_EDITS = [
    (IMPORT_OLD, IMPORT_NEW),
    ('accMult = input.float(1.2, "[暫定] Accum Max Range / ATR", step = 0.1, minval = 0.1, group = G_ACCQ)\n',
     'accMult = input.float(1.2, "[暫定] Accum Max Range / ATR", step = 0.1, minval = 0.1, group = G_ACCQ)\n'
     '\n'
     '// ---- 2.7c Round Number (XAUUSD) ------------------------------------------\n'
     '//  Engine (ZoneEnginePractical/5) の Round Number 加点。Cluster の最終範囲 [bottom, top] (境界を含む) に\n'
     '//  100 の倍数があれば 3 点、無ければ 50 の倍数で 2 点を Cluster ごとに1回、Confluence の独立1カテゴリ。\n'
     '//  Zone の上下限 / Cluster / Raw Zone / Track は変わらない。HTF 根拠にはならない。\n'
     '//  syminfo.ticker == "XAUUSD" の完全一致のときだけ有効 (他の表記・他銘柄では常に無効)。\n'
     'var string G_RN = "02 · Round Number (XAUUSD)"\n'
     'enableRn = input.bool(true, "Enable Round Number", group = G_RN,\n'
     '     tooltip = "XAUUSD (ticker 完全一致) のみ。Zone 範囲に 100ドル節目があれば +3、無ければ 50ドル節目で +2。\\n" +\n'
     '     "Confluence の独立カテゴリとして Zone ごとに1回だけ。Zone の幅・位置は変えない。")\n'),
    ("zoneCfg.maxPersistZones      := maxPersistZones\n",
     "zoneCfg.maxPersistZones      := maxPersistZones\n" + RN_CFG_LINE),
]


def git_show(rev, path="ZoneVisualPractical.pine"):
    return subprocess.run(["git", "-C", ROOT, "show", f"{rev}:{path}"], capture_output=True, text=True).stdout


def rnv_transform(src):
    t = src
    for a, b in RNV_EDITS:
        assert t.count(a) == 1, ("RN V1 anchor not unique", a[:70], t.count(a))
        t = t.replace(a, b)
    return t


def strip_rnv(src):
    """V1 Visual -> the 6e554b2 Visual text (None if any V1 edit is missing / duplicated)."""
    if src is None:
        return None
    t = src
    for a, b in reversed(RNV_EDITS):
        if t.count(b) != 1:
            return None
        t = t.replace(b, a)
    return t
