"""XL-1 — Gold Long Strategy ZoneStrategyXAULong.pine, generated from the Gold (Short) Strategy ZoneStrategyXAU.pine.

ZoneStrategyXAULong.pine == the ZoneStrategyXAU.pine of SRC_REV + EDITS (exact replacements, each old once): the name (title /
shorttitle), the Gold Long adopted defaults (from the user's Gold Long comparison over the last 365 days) and the text that
names those defaults. Trading code, Zone / SATS / size / order / breakeven logic, strategy() calculation settings and the shared
Engine import (ZoneEnginePracticalXAUUSD/2; /3 from XA-24) are byte-identical to the Short Strategy. strip() reverses the edits exactly.
XA-21 (alerts): the Long Strategy == build1() (= XL-1) + xa_build.STRATEGY_EDITS21 (the same exact alert layer as the Short
Strategy), so the Long file stays the Short file of SRC_REV + XL-1 + XA-21; strip21() reverses only XA-21 (-> the XL-1 Long file
of d67941f), strip() reverses both (-> the Short Strategy of SRC_REV).
XA-22 (provisional once per candidate / wait): build() = build21() (XL-1 + XA-21, the Long file of 61c48fb) +
xa_build.STRATEGY_EDITS22; strip22() reverses only XA-22, strip21() reverses XA-22 and XA-21 (-> d67941f).
XA-23 (confirmed labels): build() = build22() (the Long file of d05f8c9) + xa_build.STRATEGY_EDITS23; strip23() reverses only
XA-23; strip22() / strip21() / strip() also reverse XA-23 first when present.
XA-24 (run-time reduction: Engine import ZoneEnginePracticalXAUUSD/3, single FVG selection in f_stZoneEval): build() = build23()
(the Long file of 7705907) + xa_build.STRATEGY_EDITS24; strip24() reverses only XA-24; strip23() and the others also reverse
XA-24 first when present.
"""
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_PATH = "ZoneStrategyXAU.pine"
LONG_PATH = "ZoneStrategyXAULong.pine"
SRC_REV = "2550d27"
NOTE = "Gold Long の直近365日の比較から採用した初期値。今回の組み合わせでの2年間の成績・将来の有効性は未確認"

EDITS = [
    ("header",
     "//  Zone Strategy XAU  —  ZONE-P (ZoneVisualPractical) の Zone 判定をそのまま使う XAUUSD 5分足 Strategy\n",
     "//  Zone Strategy XAU Long  —  Gold Long 専用 (ゴールド Strategy ZoneStrategyXAU.pine = Short 版から生成: tests/xal_build.py)。\n"
     "//  ZONE-P (ZoneVisualPractical) の Zone 判定をそのまま使う XAUUSD 5分足 Strategy。売買処理・Engine は Short 版と同じで、名称・初期値・説明だけが異なる。\n"
     "//  XL-1: " + NOTE + ":\n"
     "//  Direction Long Only、Entry Mode D: 1M BOS Rebound、Entry Timing SATS Pullback、Role Reversal Mode Retest Confirmed、Strong 閾値 9、\n"
     "//  SL Buffer 3.0 USD、TP 固定 RR 1.5、反対側 Zone TP OFF、建値移動 ON・Fixed Distance 15 USD、SATS 待機期限 480分、SATS 線表示 ON、\n"
     "//  陽線 / 陰線要求 ON、近接 OFF (許容距離 1.0 は作用しない)、逆方向一致は日足だけ ON、即時エントリー OFF (Short 版の ON は引き継がない)、\n"
     "//  引きつけ側の接触期限 ON・1本。各選択肢 (Short Only / Both、他の Entry Mode、即時 ON 等) は比較用に残す。\n"
     "//  下の XA-* 行はゴールド (Short 版) の変更履歴で、そこに書かれた「初期」は Short 版の値 (この Long 版の初期値は上と各入力のとおり)。\n"),
    ("name", '     title                  = "Zone Strategy XAU",\n', '     title                  = "Zone Strategy XAU Long",\n'),
    ("name", '     shorttitle             = "ZONE-ST",\n', '     shorttitle             = "ZONE-ST-L",\n'),
    ("default", 'thrStrong = input.float(10.0, "Strong Score Threshold",      step = 0.5, group = G_SCORE)\n',
     'thrStrong = input.float(9.0, "Strong Score Threshold",      step = 0.5, group = G_SCORE)\n'),
    ("default", 'stMode = input.string("C: Candle Pattern", "Entry Mode",\n', 'stMode = input.string("D: 1M BOS Rebound", "Entry Mode",\n'),
    ("default", 'stDir = input.string("Short Only", "Direction", options = ["Long Only", "Short Only", "Both"], group = G_ST)\n',
     'stDir = input.string("Long Only", "Direction", options = ["Long Only", "Short Only", "Both"], group = G_ST)\n'),
    ("default", 'stBuffer = input.float(1.5, "SL Buffer ($)", minval = 0.0, step = 0.5, group = G_ST)\n',
     'stBuffer = input.float(3.0, "SL Buffer ($)", minval = 0.0, step = 0.5, group = G_ST)\n'),
    ("default", 'stSatsWait = input.int(240, "SATS · 待機期限 (分)", minval = 1, group = G_STW,\n',
     'stSatsWait = input.int(480, "SATS · 待機期限 (分)", minval = 1, group = G_STW,\n'),
    ("text",
     'tooltip = "XA-11 (初期 ON = Gold Short の比較から採用した初期値。検証継続中で、最適値・将来の有効性は未確認。OFF は比較・切り戻し用)。ON: 発注を判断する 5分足自身が',
     'tooltip = "XA-11 (Long 版も初期 ON = ' + NOTE + '。OFF は比較用)。ON: 発注を判断する 5分足自身が'),
    ("default",
     'stSatsNear = input.bool(true, "SATS · 近接を接触扱い", group = G_STW,\n'
     '     tooltip = "XA-11 (初期 ON = Gold Short の比較から採用した初期値。検証継続中で、最適値・将来の有効性は未確認。OFF は比較・切り戻し用)。',
     'stSatsNear = input.bool(false, "SATS · 近接を接触扱い", group = G_STW,\n'
     '     tooltip = "XA-11 (Long 版の初期 OFF = ' + NOTE + '。ON は比較用)。'),
    ("text",
     '     "初期 1.0 (Gold Short の比較から採用した初期値。検証継続中で、最適値・将来の有効性は未確認)。")\n',
     '     "初期 1.0 (Long 版は近接 OFF が初期なので作用しない。近接 ON で比較するときの距離)。")\n'),
    ("default",
     'stSatsFD  = input.bool(false, "SATS 逆方向一致 · 日足を判定に使用", group = G_STW,\n'
     '     tooltip = "XA-13 (初期: 4H・1H ON / 日足・15分・5分 OFF = Gold Short の比較から採用した初期値・検証継続中。全て OFF = フィルターなし)。\\n" +\n',
     'stSatsFD  = input.bool(true, "SATS 逆方向一致 · 日足を判定に使用", group = G_STW,\n'
     '     tooltip = "XA-13 (Long 版の初期: 日足だけ ON / 4H・1H・15分・5分 OFF = ' + NOTE + '。全て OFF = フィルターなし)。\\n" +\n'),
    ("default", 'stSatsF4  = input.bool(true, "SATS 逆方向一致 · 4時間足を判定に使用", group = G_STW)\n',
     'stSatsF4  = input.bool(false, "SATS 逆方向一致 · 4時間足を判定に使用", group = G_STW)\n'),
    ("default", 'stSatsF1  = input.bool(true, "SATS 逆方向一致 · 1時間足を判定に使用", group = G_STW)\n',
     'stSatsF1  = input.bool(false, "SATS 逆方向一致 · 1時間足を判定に使用", group = G_STW)\n'),
    ("default",
     'stSatsNow = input.bool(true, "SATS · 直近の反発で即時エントリー", group = G_STW,\n'
     '     tooltip = "XA-16 (初期 ON = Gold Short の比較から採用した初期値。Long・将来の有効性は未確認。OFF は比較・切り戻し用)。',
     'stSatsNow = input.bool(false, "SATS · 直近の反発で即時エントリー", group = G_STW,\n'
     '     tooltip = "XA-16 (Long 版の初期 OFF = ' + NOTE + '。Short 版の初期 ON は引き継がない。ON は比較用)。'),
    ("default",
     'stSatsTq = input.bool(false, "SATS · 引きつけ側：接触期限を使う", group = G_STW,\n'
     '     tooltip = "XA-17 比較用 (初期 OFF = 従来の引きつけ待機)。',
     'stSatsTq = input.bool(true, "SATS · 引きつけ側：接触期限を使う", group = G_STW,\n'
     '     tooltip = "XA-17 (Long 版の初期 ON・1本 = ' + NOTE + '。OFF = 従来の引きつけ待機)。'),
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


NEW_TESTS = ("tests/xal_build.py", "tests/xal_sim.py", "tests/xaa_sim.py", "tests/xab_sim.py", "tests/xac_sim.py")     # XL-1 / XA-21 .. XA-23 (alerts / labels)


def ok(path):
    """XL-1 / XA-21 account for this path exactly: the Long Strategy equal to build(), or one of their new test files. The older
    fixtures' 'other files unchanged' checks accept the new Long file (and these new tests) only through this."""
    if path in NEW_TESTS:
        return True
    if path != LONG_PATH or not os.path.exists(os.path.join(ROOT, LONG_PATH)):
        return False
    return open(os.path.join(ROOT, LONG_PATH), encoding="utf-8").read() == build()


def _xa21():
    return __import__("xa_build").STRATEGY_EDITS21


def build1():
    """XL-1 only (the Long Strategy of d67941f)."""
    return _apply(show(SRC_REV, SRC_PATH), EDITS)


def _xa22():
    return __import__("xa_build").STRATEGY_EDITS22


def build21():
    """XL-1 + XA-21 (the Long Strategy of 61c48fb)."""
    return _apply(build1(), _xa21())


def _xa23():
    return __import__("xa_build").STRATEGY_EDITS23


def build22():
    """XL-1 + XA-21 + XA-22 (the Long Strategy of d05f8c9)."""
    return _apply(build21(), _xa22())


def _xa24():
    return __import__("xa_build").STRATEGY_EDITS24


def build23():
    """XL-1 + XA-21 + XA-22 + XA-23 (the Long Strategy of 7705907)."""
    return _apply(build22(), _xa23())


def build():
    return _apply(build23(), _xa24())


def strip24(text):
    """reverse only XA-24 (-> the Long Strategy of 7705907); None when not exact."""
    return _revert(text, _xa24())


def strip23(text):
    """reverse XA-24 when present (all or nothing) and XA-23 (-> the Long Strategy of d05f8c9); None when not exact."""
    if text is not None and _xa24()[0][2] in text:
        text = strip24(text)
    return _revert(text, _xa23())


def strip22(text):
    """reverse XA-23 when present (all or nothing) and XA-22 (-> the Long Strategy of 61c48fb); None when not exact."""
    if text is not None and _xa23()[0][2] in text:
        text = strip23(text)
    return _revert(text, _xa22())


def strip21(text):
    """reverse XA-22 and XA-21 (-> the XL-1 Long Strategy of d67941f); None when not exact."""
    return _revert(strip22(text), _xa21())


def strip(text):
    """reverse XA-21 and XL-1 exactly (-> the Short Strategy of SRC_REV); None when not exact."""
    return _revert(strip21(text), EDITS)


if __name__ == "__main__":
    open(os.path.join(ROOT, LONG_PATH), "w", encoding="utf-8").write(build())
    print("written", LONG_PATH)
