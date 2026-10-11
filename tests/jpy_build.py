"""JPY-1 — ZoneVisualUSDJPY.pine: OANDA:USDJPY 5M Zone comparison indicator (no entries).

Deterministic transform of ZoneVisualPractical.pine (ZONE-P, XAUUSD) by exact, unique text replacements (EDITS);
strip_jpy() applies them in reverse and must give ZONE-P back byte for byte (fixture jpy_sim), so the Zone scoring,
update order, requests and non-repaint blocks are provably ZONE-P's.
  - every price-difference input is re-based from $ (XAUUSD) to yen (USDJPY), with yen minval / step
    (compared now: Zone Half Width 0.05, Cluster Distance 0.08; unit-converted placeholders: the rest)
  - FVG minimum width: the fixed 3.0 becomes an input (yen, default 0.05)
  - Round Number (XAUUSD only): default OFF
  - labels: zone top / bottom / width (yen, 3 decimals), Score and Sources shown by default
Engine /6, ZONE-P, ZONE-ST are not modified.
"""
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_PATH = "ZoneVisualPractical.pine"
JPY_PATH = "ZoneVisualUSDJPY.pine"

EDITS = [
    # ---- header / identity ---------------------------------------------------------------------------------------
    ("//  Zone Visual (Practical)  —  ZoneEnginePractical 表示専用 Indicator\n",
     "//  Zone Visual USDJPY (Compare)  —  OANDA:USDJPY 5分足用 Zone 比較 Indicator (Entry なし)\n"
     "//  ZONE-P (ZoneVisualPractical, XAUUSD) と同じ Engine /6・採点式・更新順・非リペイント条件で、\n"
     "//  価格差の入力だけを円に置き換えた比較版 (生成: tests/jpy_build.py、ZONE-P との差分は fixture jpy_sim が固定)。\n"
     "//  目的: ドル円の Zone Half Width / Cluster Distance の確定。比較候補 Half Width 0.03 / 0.05 / 0.08 円、\n"
     "//  Cluster Distance 0.05 / 0.08 / 0.12 円 (初期 0.05 / 0.08)。他の円換算値は暫定 ([暫定] 表記)。\n"),
    ('     title            = "Zone Visual (Practical)",\n     shorttitle       = "ZONE-P",\n',
     '     title            = "Zone Visual USDJPY (Compare)",\n     shorttitle       = "ZONE-JPY",\n'),
    # ---- label helper (price format for yen) ---------------------------------------------------------------------
    ('f_num(float v, string fmt) =>\n    na(v) ? "-" : str.tostring(v, fmt)\n',
     'f_num(float v, string fmt) =>\n    na(v) ? "-" : str.tostring(v, fmt)\n\n'
     '// Zone の上下限と最終的な幅 (円、小数 3 桁)\n'
     'f_jpyGeom(zn.Zone z) =>\n'
     '    f_num(z.top, "#.000") + " - " + f_num(z.bottom, "#.000") + " | W " + f_num(z.top - z.bottom, "0.000")\n'),
    # ---- price-difference inputs: compared now -------------------------------------------------------------------
    ('zoneHalfWidth = input.float(3.0, "Zone Half Width ($)", minval = 0.1, step = 0.5, group = G_ZONE,\n',
     'zoneHalfWidth = input.float(0.05, "Zone Half Width (円)", minval = 0.005, step = 0.005, group = G_ZONE,\n'),
    ('     "最終Zoneは Cluster内の全RawZoneを包む範囲 (min bottom ～ max top)。最大幅capなし。")\n',
     '     "最終Zoneは Cluster内の全RawZoneを包む範囲 (min bottom ～ max top)。最大幅capなし。\\n" +\n'
     '     "USDJPY 比較候補: 0.03 / 0.05 / 0.08 円。")\n'),
    ('clusterDist = input.float(5.0, "Cluster Distance ($)", step = 1.0, group = G_CLU)\n',
     'clusterDist = input.float(0.08, "Cluster Distance (円)", minval = 0.0, step = 0.005, group = G_CLU,\n'
     '     tooltip = "USDJPY 比較候補: 0.05 / 0.08 / 0.12 円。")\n'),
    # ---- price-difference inputs: unit-converted placeholders (x 1/60 of the XAUUSD $ value, adjust later) -------
    ('slopeThrMod = input.float(1.0, "Slope Threshold · Moderate ($/lookback)", step = 0.1, group = G_SLOPE)\n'
     'slopeThrStrong = input.float(3.0, "Slope Threshold · Strong ($/lookback)",   step = 0.1, group = G_SLOPE)\n',
     'slopeThrMod = input.float(0.02, "[暫定] Slope Threshold · Moderate (円/lookback)", minval = 0.0, step = 0.005, group = G_SLOPE)\n'
     'slopeThrStrong = input.float(0.05, "[暫定] Slope Threshold · Strong (円/lookback)",   minval = 0.0, step = 0.005, group = G_SLOPE)\n'),
    ('maClusterDist = input.float(20.0, "MA Cluster Distance ($)", step = 1.0, group = G_SLOPE)\n',
     'maClusterDist = input.float(0.30, "[暫定] MA Cluster Distance (円)", minval = 0.0, step = 0.01, group = G_SLOPE)\n'),
    ('touchRearmDist = input.float(10.0, "Touch Re-arm Distance ($)", minval = 0.0, step = 0.5, group = G_TOUCH,\n',
     'touchRearmDist = input.float(0.15, "[暫定] Touch Re-arm Distance (円)", minval = 0.0, step = 0.01, group = G_TOUCH,\n'),
    ('breakBuffer = input.float(5.0,  "Break Buffer ($)",         step = 0.5, group = G_BF)\n'
     'flipConfirmDist = input.float(10.0, "Flip Confirm Distance ($)", step = 0.5, group = G_BF)\n',
     'breakBuffer = input.float(0.08,  "[暫定] Break Buffer (円)",         minval = 0.0, step = 0.005, group = G_BF)\n'
     'flipConfirmDist = input.float(0.15, "[暫定] Flip Confirm Distance (円)", minval = 0.0, step = 0.01, group = G_BF)\n'),
    # ---- Round Number: XAUUSD only, OFF ----------------------------------------------------------------------------
    ('enableRn = input.bool(true, "Enable Round Number", group = G_RN,\n',
     'enableRn = input.bool(false, "Enable Round Number (XAUUSD 専用 · USDJPY は OFF)", group = G_RN,\n'),
    # ---- FVG minimum width: fixed 3.0 -> input ---------------------------------------------------------------------
    ('float  FVG_MIN_WIDTH    = 3.0\n',
     'fvgMinWidth = input.float(0.05, "[暫定] FVG Min Width (円)", minval = 0.0, step = 0.005, group = "02 · FVG (USDJPY)",\n'
     '     tooltip = "15M / 1H / 4H FVG の最小幅 (mintick 正規化後に以上)。XAUUSD は固定 3.0 ドル。\\n" +\n'
     '     "比較候補: 0.03 / 0.05 / 0.08 円 (暫定 0.05 = 既定 Zone Half Width と同じ比率)。")\n'
     'float  FVG_MIN_WIDTH    = fvgMinWidth\n'),
    # ---- labels: geometry / Score / Sources on by default ----------------------------------------------------------
    ('showDetailLbl = input.bool(false, "Detailed Labels (sources)", group = G_DISP)\n',
     'showDetailLbl = input.bool(true,  "Detailed Labels (sources)", group = G_DISP)\n'),
    ('showScore  = input.bool(false, "Label: Score を表示",   group = G_LBL)\n',
     'showScore  = input.bool(true,  "Label: Score を表示",   group = G_LBL)\n'
     'showGeom   = input.bool(true,  "Label: Zone 上下限 / 幅 (円) を表示", group = G_LBL)\n'),
    ('    if showScore\n        txt := txt + " | " + f_num(z.score, "#.#")\n',
     '    if showScore\n        txt := txt + " | " + f_num(z.score, "#.#")\n    if showGeom\n        txt := txt + "\\n" + f_jpyGeom(z)\n'),
    ('    if showScore\n        txt := txt + " | " + f_num(dScore, "#.#")\n',
     '    if showScore\n        txt := txt + " | " + f_num(dScore, "#.#")\n    if showGeom\n        txt := txt + "\\n" + f_jpyGeom(z)\n'),
]


def git_show(rev, path=SRC_PATH):
    return subprocess.run(["git", "-C", ROOT, "show", f"{rev}:{path}"], capture_output=True, text=True).stdout


def jpy_transform(src):
    out = src
    for a, b in EDITS:
        assert out.count(a) == 1, a[:80]
        out = out.replace(a, b)
    return out


def strip_jpy(jpy):
    out = jpy
    for a, b in reversed(EDITS):
        if out.count(b) != 1:
            return None
        out = out.replace(b, a)
    return out


def build():
    return jpy_transform(open(os.path.join(ROOT, SRC_PATH), encoding="utf-8").read())


if __name__ == "__main__":
    open(os.path.join(ROOT, JPY_PATH), "w", encoding="utf-8").write(build())
    print("written", JPY_PATH)
