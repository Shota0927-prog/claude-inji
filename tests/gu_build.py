"""GU-1 — GBPUSD port of the EURUSD trio (OANDA:GBPUSD 5M): Engine library, Zone Visual, Strategy.

Deterministic transforms of the EURUSD files (commit 47aeb8b) by exact, unique whole-line replacements; each strip_*()
reverses them and must give the EURUSD source back byte for byte (fixture gu_sim).
  header    new GBPUSD header block (the EURUSD lineage comments below it are kept as the source's history)
  name      library name, indicator / strategy title and shorttitle, import ZoneEnginePracticalGBPUSD/1
  symbol    every code line naming EURUSD (RN ticker gate, RN / FVG groups and labels, input tooltips) -> GBPUSD; input
            labels / tooltips: "[採用初期値]" (EURUSD adopted) -> "[比較開始値]" (comparison starting value, not verified
            on GBPUSD); comments describing this file's RN / size / pip handling
  default   Direction default Both (EURUSD: Short Only); the option list is unchanged
Every other default is the EURUSD adopted value, carried over as a comparison starting value (not verified on GBPUSD,
not optimised). Logic, Engine computation and API, quantity method (JPY budget -> strategy.convert_to_symbol -> USD),
RN tick-integer search / validation and the Visual update timing are the EURUSD files'. Existing files are not modified.
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENG_SRC, VIS_SRC, STR_SRC = "ZoneEnginePracticalEURUSD.pine", "ZoneVisualEURUSD.pine", "ZoneStrategyEURUSD.pine"
ENG_PATH, VIS_PATH, STR_PATH = "ZoneEnginePracticalGBPUSD.pine", "ZoneVisualGBPUSD.pine", "ZoneStrategyGBPUSD.pine"
IMPORT_EU = "import sekine3310/ZoneEnginePracticalEURUSD/1 as zn\n"
IMPORT_GU = "import sekine3310/ZoneEnginePracticalGBPUSD/1 as zn\n"     # first publish of the new library = version 1

ADOPT_EU = "EURUSD 検証後の採用初期値 (最適値・将来の有効性を保証するものではない)"
START_GU = "EURUSD 確定版から引き継いだ比較開始用初期値・GBPUSD では未検証 (最適値ではない)"

HDR_COMMON = (
    "//  価格差は USD (1 pip = 0.0001)。初期値は EURUSD 確定版 (47aeb8b) から引き継いだ比較開始用初期値で、GBPUSD では\n"
    "//  未検証 (検証済み・最適化済みの値ではない。EURUSD の成績は GBPUSD の実績ではない)。\n"
    "//  RN (初期 OFF): ticker GBPUSD のとき大刻み 0.0100 +3 / 小刻み 0.0050 +2 (tick 整数での包含判定・刻み検証は EURUSD 版と同じ)。\n"
    "//  以下は移植元 EURUSD 版の説明 (EURUSD の経緯・数値):\n")

ENGINE_EDITS = [
    ("header",
     "//  ★ EURUSD 派生 (ZoneEnginePracticalEURUSD、生成: tests/eu_build.py)。ZoneEnginePracticalGBPJPY (/3) と同じ処理で、\n",
     "//  ★ GBPUSD 派生 (ZoneEnginePracticalGBPUSD、生成: tests/gu_build.py、GU-1)。ZoneEnginePracticalEURUSD と同じ処理で、\n"
     "//    違いは Library 名だけ (RN の tick 整数判定を含め計算・公開 API は同一。fixture gu_sim が固定)。\n"
     "//  以下は移植元 EURUSD 版の説明:\n"
     "//  ★ EURUSD 派生 (ZoneEnginePracticalEURUSD、生成: tests/eu_build.py)。ZoneEnginePracticalGBPJPY (/3) と同じ処理で、\n"),
    ("name",
     'library("ZoneEnginePracticalEURUSD", overlay = true)\n',
     'library("ZoneEnginePracticalGBPUSD", overlay = true)\n'),
]


def _symbol_line(line):
    """GBPUSD form of a code (non-comment) line that names EURUSD or the EURUSD adopted wording."""
    out = line.replace("[採用初期値]", "[比較開始値]").replace("EURUSD", "GBPUSD")
    return out.replace(ADOPT_EU.replace("EURUSD", "GBPUSD"), START_GU)        # wording last: it names EURUSD on purpose


def _symbol_edits(src, skip):
    out = []
    for line in src.split("\n"):
        if line.lstrip().startswith("//") or line + "\n" in skip:
            continue
        if "EURUSD" in line or "採用初期値" in line:
            out.append(("symbol", line + "\n", _symbol_line(line) + "\n"))
    return out


COMMENT_EDITS = [   # comments that describe this file's own RN / size / pip handling
    ("symbol",
     "// ---- 2.7c Round Number (EURUSD) ------------------------------------------\n"
     "//  Engine (ZoneEnginePracticalEURUSD) の Round Number 加点を USD の刻みで使う。\n"
     "//  判定式 (EURUSD Engine f_rnLevelIn、最小価格刻みの整数で比較): 節目の tick 数が [ceil(bottom), floor(top)] に入れば Cluster の最終範囲 [bottom, top]\n",
     "// ---- 2.7c Round Number (GBPUSD) ------------------------------------------\n"
     "//  Engine (ZoneEnginePracticalGBPUSD) の Round Number 加点を USD の刻みで使う。\n"
     "//  判定式 (GBPUSD Engine f_rnLevelIn、最小価格刻みの整数で比較): 節目の tick 数が [ceil(bottom), floor(top)] に入れば Cluster の最終範囲 [bottom, top]\n"),
    ("symbol",
     "//  ticker が EURUSD のときだけ有効。刻みは最小価格刻みの整数倍 (tick 整数で比較するので 0.0100 / 0.0050 も境界で漏れない。\n"
     "//  tests/eu_sim で確認)。不正な刻みは停止して表示。\n",
     "//  ticker が GBPUSD のときだけ有効。刻みは最小価格刻みの整数倍 (tick 整数で比較するので 0.0100 / 0.0050 も境界で漏れない。\n"
     "//  tests/eu_sim で確認、GBPUSD は同じ式)。不正な刻みは停止して表示。\n"),
]

VISUAL_FIXED = [
    ("header",
     "//  Zone Visual EURUSD (Compare)  —  OANDA:EURUSD 5分足用 Zone 比較 Indicator (Entry / Alert なし)\n",
     "//  Zone Visual GBPUSD (Compare)  —  OANDA:GBPUSD 5分足用 Zone 比較 Indicator (Entry / Alert なし)\n"
     "//  GU-1: ZONE-EURUSD (ZoneVisualEURUSD) からの移植 (生成: tests/gu_build.py、差分は fixture gu_sim が固定)。\n"
     "//  Engine は GBPUSD 専用 Library ZoneEnginePracticalGBPUSD (EURUSD Engine と同じ処理・API、Library 名だけ異なる)。\n"
     "//  Zone の計算・更新タイミング・表示 (format.mintick、幅は pips) は EURUSD 版と同じ。Zone 初期値は Strategy と共通。\n"
     + HDR_COMMON +
     "//  Zone Visual EURUSD (Compare)  —  OANDA:EURUSD 5分足用 Zone 比較 Indicator (Entry / Alert なし)\n"),
    ("name",
     '     title            = "Zone Visual EURUSD (Compare)",\n',
     '     title            = "Zone Visual GBPUSD (Compare)",\n'),
    ("name",
     '     shorttitle       = "ZONE-EURUSD",\n',
     '     shorttitle       = "ZONE-GBPUSD",\n'),
    ("name", IMPORT_EU, IMPORT_GU),
] + COMMENT_EDITS

STRATEGY_FIXED = [
    ("header",
     "//  Zone Strategy EURUSD  —  ZONE-EURUSD (ZoneVisualEURUSD) の Zone 判定を使う OANDA:EURUSD 5分足 Strategy\n",
     "//  Zone Strategy GBPUSD  —  ZONE-GBPUSD (ZoneVisualGBPUSD) の Zone 判定を使う OANDA:GBPUSD 5分足 Strategy\n"
     "//  GU-1: ZONE-ST-EURUSD (ZoneStrategyEURUSD) からの移植 (生成: tests/gu_build.py、差分は fixture gu_sim が固定)。\n"
     "//  Entry A / B / C / D・1分足 BOS・取消・優先順位・同一 Track の再 Entry 制限・注文 / SL / TP / 建値の処理順と\n"
     "//  タイミング・数量計算 (円の損失予算 → strategy.convert_to_symbol → USD、SL 距離 × syminfo.pointvalue、lot 刻みで\n"
     "//  切り捨て。数量の単位は GBP)・仮 / 確定アラート・ラベルは EURUSD 版と同じ式。Zone 初期値は ZONE-GBPUSD と共通。\n"
     "//  初期設定: Entry B: Confirmed Rejection、Direction Both (Long Only / Short Only・A〜D は選択可)、固定 RR 1.5、\n"
     "//  SL Buffer 3 pips、Zone TP / 建値移動 OFF、新規 Entry 09:00〜翌 02:00 (Asia/Tokyo)、300,000 円・3 %・単利。\n"
     + HDR_COMMON +
     "//  Zone Strategy EURUSD  —  ZONE-EURUSD (ZoneVisualEURUSD) の Zone 判定を使う OANDA:EURUSD 5分足 Strategy\n"),
    ("name",
     '     title                  = "Zone Strategy EURUSD",\n',
     '     title                  = "Zone Strategy GBPUSD",\n'),
    ("name",
     '     shorttitle             = "ZONE-ST-EURUSD",\n',
     '     shorttitle             = "ZONE-ST-GBPUSD",\n'),
    ("name", IMPORT_EU, IMPORT_GU),
] + COMMENT_EDITS + [
    ("default",
     'stDir = input.string("Short Only", "Direction", options = ["Long Only", "Short Only", "Both"], group = G_ST)\n',
     'stDir = input.string("Both", "Direction", options = ["Long Only", "Short Only", "Both"], group = G_ST)\n'),
    ("symbol",
     "// 数量 (通貨数、EUR): 参照価格 ref と固定 SL の距離から、損失予算を超えない最大の lot 刻みの倍数。\n",
     "// 数量 (通貨数、GBP): 参照価格 ref と固定 SL の距離から、損失予算を超えない最大の lot 刻みの倍数。\n"),
    ("symbol",
     "//  EURUSD: 0.0001 = 1 pip。Entry / SL / TP は最小価格刻みの桁。TP は発注前の RR 判定 (f_stTp) と同じ結果を受け取る\n",
     "//  GBPUSD: 0.0001 = 1 pip。Entry / SL / TP は最小価格刻みの桁。TP は発注前の RR 判定 (f_stTp) と同じ結果を受け取る\n"),
]


_rd = lambda p: open(os.path.join(ROOT, p), encoding="utf-8").read()


def _edits(src_path, fixed):
    skip = {a for _, a, _ in fixed}
    return fixed + _symbol_edits(_rd(src_path), skip)


def visual_edits():
    return _edits(VIS_SRC, VISUAL_FIXED)


def strategy_edits():
    return _edits(STR_SRC, STRATEGY_FIXED)


def engine_edits():
    return _edits(ENG_SRC, ENGINE_EDITS)


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


def build_engine():
    return _apply(_rd(ENG_SRC), engine_edits())


def build_visual():
    return _apply(_rd(VIS_SRC), visual_edits())


def build_strategy():
    return _apply(_rd(STR_SRC), strategy_edits())


def strip_engine(t):
    return _revert(t, engine_edits())


def strip_visual(t):
    return _revert(t, visual_edits())


def strip_strategy(t):
    return _revert(t, strategy_edits())


if __name__ == "__main__":
    for path, fn in ((ENG_PATH, build_engine), (VIS_PATH, build_visual), (STR_PATH, build_strategy)):
        open(os.path.join(ROOT, path), "w", encoding="utf-8").write(fn())
        print("written", path)
