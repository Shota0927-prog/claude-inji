"""BTL-1 — BTCUSD Long adopted defaults: ZoneStrategyBTCUSD.pine (the BTCUSD Strategy, Direction default Long Only; the repo has
no separate BTCUSD Short Strategy).

ZoneStrategyBTCUSD.pine == its file at BASE_REV + EDITS (exact replacements, each old once): the input defaults of the user's
adopted BTCUSD Long setting (Last 365 days comparison; other periods not yet verified) that differ from BASE_REV, their
tooltip text and a header block. Every changed input is already passed to the Engine config / Strategy code (no wiring
change needed); trading code, the Engine import (ZoneEnginePracticalBTCUSD/1), the Visual ZoneVisualBTCUSD.pine, other
symbols and the shared Engines are unchanged. SL Buffer is NOT changed (no adopted value found in the repo: it stays 50 USD).
strip() reverses the edits exactly; unapply() leaves a text without them unchanged.
"""
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = "ZoneStrategyBTCUSD.pine"
BASE_REV = "7705907"
NOTE = "BTCUSD Long の直近365日の検証から採用した初期値 (別期間での検証は未完了・将来の有効性は未確認)"

# (input, before, after) — the defaults that differ from BASE_REV
CHANGES = [("clusterDist", "100.0", "50.0"), ("thrStrong", "9.0", "8.0"), ("accEdgeMode", '"Separate"', '"Once per TF"'),
           ("flipConfirmDist", "150.0", "100.0"), ("trackStaleBars", "500", "1000"), ("fvgDirMatch", "false", "true"),
           ("stRR", "1.2", "1.5"), ("stBE", "false", "true"), ("stBEDist", "150.0", "300.0"), ("stBER", "1.0", "0.5")]

HDR_OLD = "//  Zone Strategy BTCUSD  —  ZONE-BTCUSD (ZoneVisualBTCUSD) の Zone 判定を使う CRYPTO:BTCUSD 5分足 Strategy\n"
HDR_NEW = (HDR_OLD +
           "//  BTL-1: " + NOTE + " (生成: tests/btl_build.py)。\n"
           "//  Entry D・Current、Long Only (従来どおり)。変更した初期値: Cluster Distance 100→50 USD、Strong 閾値 9→8、Accum Edge Mode\n"
           "//  Separate→Once per TF、Flip Confirm Distance 150→100 USD、Zone State Retention 500→1000、FVG Direction Match OFF→ON、\n"
           "//  TP 固定 RR 1.2→1.5、建値移動 OFF→ON・Fixed Distance 300 USD (150→300)、非選択の Risk Multiple R 1.0→0.5。他の入力は従来値のまま\n"
           "//  (表に一致済み)。SL Buffer 50 USD は採用値が未確定のため変更していない。売買処理・Engine・Visual は変えない。\n"
           "//  下の「SL Buffer 50 / Breakeven 150 USD は未検証の検証開始値」は BTL-1 前の説明 (Breakeven は BTL-1 で 300 USD)。\n")

EDITS = [
    ("header", HDR_OLD, HDR_NEW),
    ("default",
     'accEdgeMode = input.string("Separate", "Accum Edge Mode", options = ["Separate", "Once per TF"], group = G_ACC,\n',
     'accEdgeMode = input.string("Once per TF", "Accum Edge Mode", options = ["Separate", "Once per TF"], group = G_ACC,\n'),
    ("default",
     'clusterDist = input.float(100.0, "[未検証] Cluster Distance (USD)", minval = 0.0, step = 5.0, group = G_CLU,\n'
     '     tooltip = "BTCUSD 比較候補 (表示確認用・適正値ではない): 50 / 100 / 150 USD。初期 100 USD は未検証の開始値。")\n',
     'clusterDist = input.float(50.0, "[未検証] Cluster Distance (USD)", minval = 0.0, step = 5.0, group = G_CLU,\n'
     '     tooltip = "BTCUSD 比較候補: 50 / 100 / 150 USD。初期 50 USD = BTL-1 (' + NOTE + ')。")\n'),
    ("default", 'thrStrong = input.float(9.0, "Strong Score Threshold",       step = 0.5, group = G_SCORE)\n',
     'thrStrong = input.float(8.0, "Strong Score Threshold",       step = 0.5, group = G_SCORE)\n'),
    ("default", 'flipConfirmDist = input.float(150.0, "[未検証] Flip Confirm Distance (USD)", minval = 0.0, step = 10.0, group = G_BF)\n',
     'flipConfirmDist = input.float(100.0, "[未検証] Flip Confirm Distance (USD)", minval = 0.0, step = 10.0, group = G_BF)\n'),
    ("default", 'trackStaleBars = input.int(500, "Zone State Retention (bars without match)", minval = 10, group = G_BF)\n',
     'trackStaleBars = input.int(1000, "Zone State Retention (bars without match)", minval = 10, group = G_BF)\n'),
    ("default", 'fvgDirMatch = input.bool(false, "FVG Direction Match", group = "02 · FVG (BTCUSD)",\n',
     'fvgDirMatch = input.bool(true, "FVG Direction Match", group = "02 · FVG (BTCUSD)",\n'),
    ("default", 'stRR = input.float(1.2, "TP Fixed RR", minval = 0.1, step = 0.1, group = G_STT)\n',
     'stRR = input.float(1.5, "TP Fixed RR", minval = 0.1, step = 0.1, group = G_STT)\n'),
    ("default", 'stBE = input.bool(false, "Breakeven Stop", group = G_STT)\n', 'stBE = input.bool(true, "Breakeven Stop", group = G_STT)\n'),
    ("default",
     'stBEDist = input.float(150.0, "[未検証] Breakeven Trigger (USD)", minval = 0.0, step = 10.0, group = G_STT,\n'
     '     tooltip = "建値移動の発動距離 (Breakeven Stop が ON のときだけ)。150 USD は未検証の検証開始値。")\n',
     'stBEDist = input.float(300.0, "[未検証] Breakeven Trigger (USD)", minval = 0.0, step = 10.0, group = G_STT,\n'
     '     tooltip = "建値移動の発動距離 (Breakeven Stop が ON のときだけ)。初期 300 USD = BTL-1 (' + NOTE + ')。")\n'),
    ("default", 'stBER = input.float(1.0, "Breakeven Trigger (R)", minval = 0.1, step = 0.1, group = G_STT)\n',
     'stBER = input.float(0.5, "Breakeven Trigger (R)", minval = 0.1, step = 0.1, group = G_STT)\n'),
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
    """reverse BTL-1 exactly (-> the BTCUSD Strategy of BASE_REV); None when not exact."""
    return _revert(text, EDITS)


def unapply(path, text):
    """reverse BTL-1 when present (all or nothing): unchanged without it (or for other paths), None with only part of it."""
    if text is None or path != PATH or HDR_NEW.split("\n")[1] not in text:
        return text
    return strip(text)


NEW_TESTS = ("tests/btl_build.py", "tests/btl_sim.py")


def ok(path, rev=None):
    """BTL-1 accounts for this path exactly vs `rev` (default BASE_REV): one of its new test files, or the BTCUSD Strategy whose
    BTL-1 edits revert to the file of `rev` (the older fixtures' 'other files unchanged' checks accept it only through this)."""
    if path in NEW_TESTS:
        return True
    if path != PATH or not os.path.exists(os.path.join(ROOT, PATH)):
        return False
    s = strip(open(os.path.join(ROOT, PATH), encoding="utf-8").read())
    return s is not None and s == show(rev or BASE_REV, PATH)


if __name__ == "__main__":
    open(os.path.join(ROOT, PATH), "w", encoding="utf-8").write(build())
    print("written", PATH)
