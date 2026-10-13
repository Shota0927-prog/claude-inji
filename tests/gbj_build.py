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


# ---- GBJ-2: FVG Direction Match + GBPJPY Round Number (both default OFF; applied after EDITS) ----------------------
#  kinds: header (comment), fvgdir (FVG direction filter: input + candidate filter in the three FVG selections),
#         rn (GBPJPY RN inputs, step validation, Engine RN config). strip_gbj2() reverses only these -> GBJ-1 text.
RN_OLD = (
    "// ---- 2.7c Round Number (XAUUSD) ------------------------------------------\n"
    "//  Engine (ZoneEnginePractical/5) の Round Number 加点。Cluster の最終範囲 [bottom, top] (境界を含む) に\n"
    "//  100 の倍数があれば 3 点、無ければ 50 の倍数で 2 点を Cluster ごとに1回、Confluence の独立1カテゴリ。\n"
    "//  Zone の上下限 / Cluster / Raw Zone / Track は変わらない。HTF 根拠にはならない。\n"
    "//  syminfo.ticker == \"XAUUSD\" の完全一致のときだけ有効 (他の表記・他銘柄では常に無効)。\n"
    "var string G_RN = \"02 · Round Number (XAUUSD)\"\n"
    "enableRn = input.bool(false, \"Enable Round Number (XAUUSD 専用 · GBPJPY は OFF)\", group = G_RN,\n"
    "     tooltip = \"XAUUSD (ticker 完全一致) のみ。Zone 範囲に 100ドル節目があれば +3、無ければ 50ドル節目で +2。\\n\" +\n"
    "     \"Confluence の独立カテゴリとして Zone ごとに1回だけ。Zone の幅・位置は変えない。\")\n")
RN_NEW = (
    "// ---- 2.7c Round Number (GBPJPY) ------------------------------------------\n"
    "//  Engine (ZoneEnginePractical/6) の既存 Round Number 加点を円の刻みで使う (Engine は変更しない)。\n"
    "//  判定式 (Engine f_rnLevelIn): ceil(bottom / 刻み) <= floor(top / 刻み) なら Cluster の最終範囲 [bottom, top]\n"
    "//  (境界を含む) に刻みの倍数がある。許容距離は無い。大刻みを先に調べ、無いときだけ小刻み (両方該当は大刻みだけ)。\n"
    "//  Cluster ごとに最大 1 回、baseSum へ加点し Confluence の独立 1 カテゴリ。RN 単独の Zone は作らない。HTF 根拠にならない。\n"
    "//  ticker が GBPJPY のときだけ有効。刻みは 0.125 円の倍数 (2 進で正確に表せる値) に限る: 判定式は浮動小数の\n"
    "//  割り算なので、0.1 / 0.2 円などは境界ちょうどの価格で誤判定し得る (tests/gbx_sim で確認)。不正な刻みは停止して表示。\n"
    "var string G_RN = \"02 · Round Number (GBPJPY)\"\n"
    "enableRn = input.bool(false, \"Enable Round Number (GBPJPY)\", group = G_RN,\n"
    "     tooltip = \"Zone の範囲 [bottom, top] (境界を含む) に大刻みの倍数があれば大刻みの加点、無ければ小刻みの倍数で小刻みの加点。\\n\" +\n"
    "     \"Zone ごとに 1 回 (両方該当は大刻みだけ)、Confluence の独立カテゴリ。RN 単独の Zone は作らない。許容距離なし。\")\n"
    "rnMajorStep = input.float(1.0, \"[暫定] RN 大刻み (円)\", minval = 0.125, step = 0.125, group = G_RN,\n"
    "     tooltip = \"例: 1.00 円 → 210.000。0.125 円の倍数、かつ小刻みの整数倍 (2 倍以上)。\")\n"
    "rnMajorScore = input.float(3.0, \"[暫定] RN 大刻み 加点\", minval = 0.0, step = 0.5, group = G_RN)\n"
    "rnMinorStep = input.float(0.5, \"[暫定] RN 小刻み (円)\", minval = 0.125, step = 0.125, group = G_RN,\n"
    "     tooltip = \"例: 0.50 円 → 210.500。0.125 円の倍数。\")\n"
    "rnMinorScore = input.float(2.0, \"[暫定] RN 小刻み 加点\", minval = 0.0, step = 0.5, group = G_RN)\n"
    "// 刻みの検証 (価格の算術だけ)。RN ON で不正なら runtime.error で明示する (OFF のときは何もしない)\n"
    "float rnRatio  = rnMinorStep > 0 ? rnMajorStep / rnMinorStep : 0.0\n"
    "float rnMajT   = rnMajorStep / syminfo.mintick\n"
    "float rnMinT   = rnMinorStep / syminfo.mintick\n"
    "bool  rnStepOK = rnMinorStep > 0 and rnMajorStep > rnMinorStep and math.abs(rnRatio - math.round(rnRatio)) < 1e-9\n"
    "     and math.abs(rnMajT - math.round(rnMajT)) < 1e-6 and math.abs(rnMinT - math.round(rnMinT)) < 1e-6\n"
    "     and rnMajorStep * 8 == math.round(rnMajorStep * 8) and rnMinorStep * 8 == math.round(rnMinorStep * 8)\n"
    "if enableRn and not rnStepOK\n"
    "    runtime.error(\"Round Number: 刻みが不正です (小刻み > 0、大刻み = 小刻みの 2 倍以上の整数倍、どちらも最小価格刻みと 0.125 円の倍数)\")\n")
FVGDIR_INPUT_ANCHOR = '     "GBPJPY 比較候補 (検証用・適正値ではない): 0.05 / 0.08 / 0.10 円。初期 0.05 = ドル円検証値。")\n'
FVGDIR_INPUT = (
    'fvgDirMatch = input.bool(false, "FVG Direction Match", group = "02 · FVG (GBPJPY)",\n'
    '     tooltip = "OFF: 従来どおり (向きを問わず重なる FVG から最良 1 個)。\\n" +\n'
    '     "ON: SUPPORT の Zone は上昇 FVG だけ、RESIST の Zone は下降 FVG だけを候補にしてから、上位 TF 優先・同 TF は新しい方で 1 個選ぶ。\\n" +\n'
    '     "その他の State は従来どおり。FVG の保存・寿命・埋め・幅・点数・Confluence・昇格範囲の式は同じ。")\n')
SEL_OLD = ("    int best = -1\n    for s = 0 to 3 * FVG_SLOTS_PER_TF - 1\n        if array.get(gFvgAlive, s)\n"
           "            if f_fvcOverlap(z.top, z.bottom, array.get(gFvgTop, s), array.get(gFvgBot, s))\n")
SEL_NEW = ("    int best = -1\n"
           "    // FVG Direction Match: 方向で候補を絞ってから選ぶ (選んだ後に除外しない)。OFF / SUPPORT・RESIST 以外は want = 0\n"
           "    int want = fvgDirMatch ? (z.state == ST_SUPPORT ? 1 : z.state == ST_RESIST ? -1 : 0) : 0\n"
           "    for s = 0 to 3 * FVG_SLOTS_PER_TF - 1\n"
           "        if array.get(gFvgAlive, s) and (want == 0 or array.get(gFvgDir, s) == want)\n"
           "            if f_fvcOverlap(z.top, z.bottom, array.get(gFvgTop, s), array.get(gFvgBot, s))\n")

EDITS2 = [
    ("header",
     "//  FVG Min Width 0.05 / 0.08 / 0.10 円 (検証候補であり適正値ではない)。Round Number (XAUUSD 専用) は OFF。\n",
     "//  FVG Min Width 0.05 / 0.08 / 0.10 円 (検証候補であり適正値ではない)。\n"
     "//  GBJ-2 (比較用、どちらも初期 OFF = 従来と同じ結果): FVG Direction Match (SUPPORT は上昇 FVG、RESIST は下降 FVG\n"
     "//  だけを加点候補にする) と GBPJPY Round Number (大刻み 1.00 円 +3 / 小刻み 0.50 円 +2、Engine の既存 RN 加点)。\n"),
    ("rn", RN_OLD, RN_NEW),
    ("rn",
     'zoneCfg.useRnSource          := enableRn and syminfo.ticker == "XAUUSD"\n',
     'zoneCfg.rnStepMajor          := rnMajorStep\n'
     'zoneCfg.rnScoreMajor         := rnMajorScore\n'
     'zoneCfg.rnStepMinor          := rnMinorStep\n'
     'zoneCfg.rnScoreMinor         := rnMinorScore\n'
     'zoneCfg.useRnSource          := enableRn and rnStepOK and syminfo.ticker == "GBPJPY"\n'),
    ("fvgdir", FVGDIR_INPUT_ANCHOR, FVGDIR_INPUT_ANCHOR + FVGDIR_INPUT),
    ("fvgdir", "f_fvcZoneDisplay(zn.Zone z) =>\n" + SEL_OLD, "f_fvcZoneDisplay(zn.Zone z) =>\n" + SEL_NEW),
    ("fvgdir", "f_zpoBestFvg(zn.Zone z) =>\n" + SEL_OLD, "f_zpoBestFvg(zn.Zone z) =>\n" + SEL_NEW),
    ("fvgdir",
     "    int   best = -1\n    if n > 0\n        for i = 0 to n - 1\n            zn.Zone z = zn.zoneAt(zoneEng, i)\n"
     "            if z.state != ST_BROKEN\n",
     "    int   best = -1\n"
     "    int   fd   = array.get(gFvgDir, slot)     // FVG Direction Match: 向きの合わない SUPPORT / RESIST の Zone は使わない\n"
     "    if n > 0\n        for i = 0 to n - 1\n            zn.Zone z = zn.zoneAt(zoneEng, i)\n"
     "            if z.state != ST_BROKEN and (not fvgDirMatch or ((z.state != ST_SUPPORT or fd == 1) and (z.state != ST_RESIST or fd == -1)))\n"),
]


def git_show(rev, path=SRC_PATH):
    return subprocess.run(["git", "-C", ROOT, "show", f"{rev}:{path}"], capture_output=True, text=True).stdout


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


def gbj1_transform(src):
    """GBJ-1 only (the version before GBJ-2)."""
    return _apply(src, EDITS)


def gbj_transform(src):
    return _apply(gbj1_transform(src), EDITS2)


def strip_gbj2(gbj):
    """reverse only the GBJ-2 edits (-> the GBJ-1 file byte for byte)."""
    return _revert(gbj, EDITS2)


def strip_gbj(gbj):
    return _revert(strip_gbj2(gbj), EDITS)


def build():
    return gbj_transform(open(os.path.join(ROOT, SRC_PATH), encoding="utf-8").read())


if __name__ == "__main__":
    open(os.path.join(ROOT, GBJ_PATH), "w", encoding="utf-8").write(build())
    print("written", GBJ_PATH)
