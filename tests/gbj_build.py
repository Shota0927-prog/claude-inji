"""GBJ-1 — ZoneVisualGBPJPY.pine: OANDA:GBPJPY 5M Zone comparison indicator (no entries, no alerts).

Deterministic transform of ZoneVisualUSDJPY.pine (ZONE-JPY) by exact, unique text replacements (EDITS);
strip_gbj() applies them in reverse and must give ZONE-JPY back byte for byte (fixture gbj_sim), so the Engine /6,
Zone generation / scoring, FVG, update order, requests and non-repaint blocks are provably ZONE-JPY's.
Only these kinds of change are allowed (each EDIT is tagged and gbj_sim checks the code lines it touches):
  header    comment header
  title     indicator title / shorttitle
  input     input default / label / tooltip / group text (price inputs stay in 円)
  display   label text (unit 円 after the width)
Price-difference defaults (all [暫定]): Zone Half Width 0.03 (USDJPY verified value), Cluster Distance 0.08,
FVG Min Width 0.05; every other yen threshold is inherited unchanged from ZONE-JPY.
ZONE-JPY, ZONE-P, the Strategies and the Engines are not modified.
"""
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_PATH = "ZoneVisualUSDJPY.pine"
GBJ_PATH = "ZoneVisualGBPJPY.pine"

EDITS = [
    # ---- header / identity ---------------------------------------------------------------------------------------
    ("header",
     "//  Zone Visual USDJPY (Compare)  —  OANDA:USDJPY 5分足用 Zone 比較 Indicator (Entry なし)\n"
     "//  ZONE-P (ZoneVisualPractical, XAUUSD) と同じ Engine /6・採点式・更新順・非リペイント条件で、\n"
     "//  価格差の入力だけを円に置き換えた比較版 (生成: tests/jpy_build.py、ZONE-P との差分は fixture jpy_sim が固定)。\n"
     "//  目的: ドル円の Zone Half Width / Cluster Distance の確定。比較候補 Half Width 0.03 / 0.05 / 0.08 円、\n"
     "//  Cluster Distance 0.05 / 0.08 / 0.12 円 (初期 0.05 / 0.08)。他の円換算値は暫定 ([暫定] 表記)。\n",
     "//  Zone Visual GBPJPY (Compare)  —  OANDA:GBPJPY 5分足用 Zone 比較 Indicator (Entry / Alert なし)\n"
     "//  ZONE-JPY (ZoneVisualUSDJPY) と同じ Engine /6・Zone 生成・採点式・FVG・更新順・非リペイント条件で、\n"
     "//  表示名と円建て入力の初期値 / 説明だけを変えた比較版 (生成: tests/gbj_build.py、ZONE-JPY との差分は\n"
     "//  fixture gbj_sim が固定)。価格差の入力はすべて円 (1 pip = 0.01 円、0.05 円 = 5 pips)。\n"
     "//  初期値はすべて暫定: Half Width 0.03 / Cluster Distance 0.08 / FVG Min Width 0.05 円 (ドル円検証値)、\n"
     "//  他の円建て閾値は ZONE-JPY と同じ値。比較候補 Half Width 0.03 / 0.05 / 0.08、Cluster 0.08 / 0.12 / 0.16、\n"
     "//  FVG Min Width 0.05 / 0.08 / 0.10 円 (検証候補であり適正値ではない)。Round Number (XAUUSD 専用) は OFF。\n"),
    ("title",
     '     title            = "Zone Visual USDJPY (Compare)",\n     shorttitle       = "ZONE-JPY",\n',
     '     title            = "Zone Visual GBPJPY (Compare)",\n     shorttitle       = "ZONE-GBPJPY",\n'),
    # ---- label: width unit -----------------------------------------------------------------------------------------
    ("display",
     '// Zone の上下限と最終的な幅 (円、小数 3 桁)\n'
     'f_jpyGeom(zn.Zone z) =>\n'
     '    f_num(z.top, "#.000") + " - " + f_num(z.bottom, "#.000") + " | W " + f_num(z.top - z.bottom, "0.000")\n',
     '// Zone の上下限と最終的な幅 (円、小数 3 桁 = OANDA:GBPJPY の最小刻み 0.001。pips ではない)\n'
     'f_jpyGeom(zn.Zone z) =>\n'
     '    f_num(z.top, "#.000") + " - " + f_num(z.bottom, "#.000") + " | W " + f_num(z.top - z.bottom, "0.000") + "円"\n'),
    # ---- price-difference inputs: compared now (all [暫定]) ---------------------------------------------------------
    ("input",
     'zoneHalfWidth = input.float(0.05, "Zone Half Width (円)", minval = 0.005, step = 0.005, group = G_ZONE,\n',
     'zoneHalfWidth = input.float(0.03, "[暫定] Zone Half Width (円)", minval = 0.005, step = 0.005, group = G_ZONE,\n'),
    ("input",
     '     "USDJPY 比較候補: 0.03 / 0.05 / 0.08 円。")\n',
     '     "GBPJPY 比較候補 (検証用・適正値ではない): 0.03 / 0.05 / 0.08 円 (= 3 / 5 / 8 pips)。初期 0.03 = ドル円検証値。")\n'),
    ("input",
     'clusterDist = input.float(0.08, "Cluster Distance (円)", minval = 0.0, step = 0.005, group = G_CLU,\n'
     '     tooltip = "USDJPY 比較候補: 0.05 / 0.08 / 0.12 円。")\n',
     'clusterDist = input.float(0.08, "[暫定] Cluster Distance (円)", minval = 0.0, step = 0.005, group = G_CLU,\n'
     '     tooltip = "GBPJPY 比較候補 (検証用・適正値ではない): 0.08 / 0.12 / 0.16 円。初期 0.08 = ドル円検証値。")\n'),
    ("input",
     'enableRn = input.bool(false, "Enable Round Number (XAUUSD 専用 · USDJPY は OFF)", group = G_RN,\n',
     'enableRn = input.bool(false, "Enable Round Number (XAUUSD 専用 · GBPJPY は OFF)", group = G_RN,\n'),
    ("input",
     'fvgMinWidth = input.float(0.05, "[暫定] FVG Min Width (円)", minval = 0.0, step = 0.005, group = "02 · FVG (USDJPY)",\n'
     '     tooltip = "15M / 1H / 4H FVG の最小幅 (mintick 正規化後に以上)。XAUUSD は固定 3.0 ドル。\\n" +\n'
     '     "比較候補: 0.03 / 0.05 / 0.08 円 (暫定 0.05 = 既定 Zone Half Width と同じ比率)。")\n',
     'fvgMinWidth = input.float(0.05, "[暫定] FVG Min Width (円)", minval = 0.0, step = 0.005, group = "02 · FVG (GBPJPY)",\n'
     '     tooltip = "15M / 1H / 4H FVG の最小幅 (mintick 正規化後に以上)。XAUUSD は固定 3.0 ドル。\\n" +\n'
     '     "GBPJPY 比較候補 (検証用・適正値ではない): 0.05 / 0.08 / 0.10 円。初期 0.05 = ドル円検証値。")\n'),
]


def git_show(rev, path=SRC_PATH):
    return subprocess.run(["git", "-C", ROOT, "show", f"{rev}:{path}"], capture_output=True, text=True).stdout


def gbj_transform(src):
    out = src
    for _, a, b in EDITS:
        assert out.count(a) == 1, a[:80]
        out = out.replace(a, b)
    return out


def strip_gbj(gbj):
    out = gbj
    for _, a, b in reversed(EDITS):
        if out.count(b) != 1:
            return None
        out = out.replace(b, a)
    return out


def build():
    return gbj_transform(open(os.path.join(ROOT, SRC_PATH), encoding="utf-8").read())


if __name__ == "__main__":
    open(os.path.join(ROOT, GBJ_PATH), "w", encoding="utf-8").write(build())
    print("written", GBJ_PATH)
