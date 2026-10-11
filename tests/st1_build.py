"""ST-1 — ZoneStrategyXAU.pine: deterministic build from ZoneVisualPractical.pine @ beca989 (ZONE-P).

  1. header + indicator(...) -> strategy(...) (calc_on_every_tick = false, process_orders_on_close = false)
  2. the display-only input group "2.11 Zone Display" is removed
  3. everything from the DISPLAY section to the end (display inputs / filters, box / label pools, colour / label
     helpers, Batch C, overlap-only display, MA plot, stats table) is replaced by one evaluation block holding
       - byte copies of the Batch C scoring functions (f_fvcConf, f_fvcStrengthOf, f_fvcBase, f_fvcOverlap,
         f_fvcZoneDisplay) and of f_zpoBestFvg
       - f_stZoneEval(z): the overlap-only display's boost decision / range with the same expressions
       - a confirmed-bar evaluation loop over the Engine zones (Profiler hook; no orders yet)
Everything above the DISPLAY section except (2) — inputs, Engine config, feed, NR-S1, NR-A1, RN, Break, trading day,
zn.update, FVG Batch A — is byte-identical to ZONE-P.
"""
import os
import re
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ST_BASE_REV = "beca989"
ST_PATH = "ZoneStrategyXAU.pine"
ST_BEGIN, ST_END = "// ==== ZONE Strategy · Zone evaluation (begin) ", "// ==== ZONE Strategy · Zone evaluation (end) "
DISPLAY_HEAD = "// ============================================================================\n// DISPLAY\n"
DISP_INPUT_HEAD = "// ---- 2.11 Zone Display -----------------------------------------------------\n"
DISP_INPUT_LAST = 'trVStrong     = input.int(55, "Transparency · Very Strong", minval = 0, maxval = 100, group = G_DISP)\n'
IMPORT_LINE = "import sekine3310/ZoneEnginePractical/6 as zn\n"
COPIED_FUNCS = ["f_fvcConf(", "f_fvcStrengthOf(", "f_fvcBase(", "f_fvcOverlap(", "f_fvcZoneDisplay(", "f_zpoBestFvg("]

HEADER = """// This Pine Script® code is subject to the terms of the Mozilla Public License 2.0
// © shota0927-prog
//
// ============================================================================
//  Zone Strategy XAU  —  ZONE-P (ZoneVisualPractical) の Zone 判定をそのまま使う XAUUSD 5分足 Strategy
// ============================================================================
//  ・Zone 判定は ZONE-P と同一: ZoneEnginePractical/6 (Swing 最大点) / 入力 / Source 取得 / NR-S1 / NR-A1 /
//    RN / Break / zn.update / FVG Batch A (検知・保存・完全埋め・期限) は ZONE-P の本文をそのまま使う
//    (fixture st1_sim が ZONE-P との byte 一致で固定)。FVG は常に有効 (無効化入力なし)。
//  ・FVG 加点 (Batch C) と重複範囲限定昇格の判定は ZONE-P と同じ関数 / 同じ式 (f_stZoneEval)。
//  ・描画 (box / label / MA plot / Stats) は持たない。判定は確定 5分足でだけ。
//  ・ST-1: Entry / SL / TP 注文はまだ無い (評価ループは Profiler 計測用の最小構造)。
// ============================================================================

//@version=5
strategy(
     title                  = "Zone Strategy XAU",
     shorttitle             = "ZONE-ST",
     overlay                = true,
     dynamic_requests       = true,
     calc_on_every_tick     = false,
     process_orders_on_close = false,
     pyramiding             = 0,
     initial_capital        = 10000,
     default_qty_type       = strategy.fixed,
     default_qty_value      = 1)

"""

EVAL_TAIL = """//  ZONE-P と同じ値を Entry 判定用に返す (表示はしない)。
//  ・元 Zone      : zn.zoneAt の z.score / z.strength (Engine 内部値、Zone 全体 [z.bottom, z.top])。
//                   Touch / Track / Break / Flip もこの値に基づく (ZONE-P と同一)。
//  ・FVG 加点後   : f_fvcZoneDisplay (Batch C) の dScore / dStr。採用 FVG = f_zpoBestFvg (同じ選択)。
//  ・昇格範囲     : boosted (dStr > z.strength) のときだけ [max(z.bottom, fvgBot), min(z.top, fvgTop)]
//                   (ZONE-P の重複範囲限定表示と同じ式)。昇格しないときは na。
//  ・FVG 重複範囲 : 採用 FVG があれば昇格の有無に関係なく同じ交差範囲 (無ければ na)。
//  ・Pine v5 は and / or の両辺を評価するため、-1 判定と array.get を同じ式に書かない。
f_stZoneEval(zn.Zone z) =>
    [dScore, dStr] = f_fvcZoneDisplay(z)
    int  best    = f_zpoBestFvg(z)
    bool boosted = best >= 0 and dStr > z.strength
    float oTop = z.top
    float oBot = z.bottom
    if boosted
        oTop := math.min(z.top, array.get(gFvgTop, best))
        oBot := math.max(z.bottom, array.get(gFvgBot, best))
    float bTop = boosted ? oTop : na
    float bBot = boosted ? oBot : na
    float vTop = na
    float vBot = na
    if best >= 0
        vTop := math.min(z.top, array.get(gFvgTop, best))
        vBot := math.max(z.bottom, array.get(gFvgBot, best))
    [dScore, dStr, best, boosted, bTop, bBot, vTop, vBot]

// ---- 確定 5分足の評価ループ (ST-1: 注文なし。Profiler で Zone 評価の負荷を測るための最小構造) ----
int stZones   = 0
int stFvgZone = 0
int stBoosted = 0
if is5mChart and barstate.isconfirmed
    int n = zn.zoneCount(zoneEng)
    stZones := n
    if n > 0
        for i = 0 to n - 1
            zn.Zone z = zn.zoneAt(zoneEng, i)
            [eScore, eStr, eBest, eBoost, eBTop, eBBot, eVTop, eVBot] = f_stZoneEval(z)
            if eBest >= 0
                stFvgZone += 1
            if eBoost
                stBoosted += 1

plot(stZones,   "ST · Zones",             display = display.data_window)
plot(stFvgZone, "ST · Zones with FVG",    display = display.data_window)
plot(stBoosted, "ST · FVG boosted zones", display = display.data_window)
"""


def git_show(rev, path="ZoneVisualPractical.pine"):
    return subprocess.run(["git", "-C", ROOT, "show", f"{rev}:{path}"], capture_output=True, text=True).stdout


def func(src, head):
    """top-level Pine function text (header line to the line before the next top-level line), incl. trailing newline."""
    i = src.index("\n" + head) + 1
    m = re.search(r"\n(?=\S)", src[i + len(head):])
    return src[i:i + len(head) + m.start() + 1]


def eval_block(visual):
    copies = "".join(func(visual, h) + "\n" for h in COPIED_FUNCS)
    return (ST_BEGIN + "=========================================\n"
            "//  ZONE-P の FVG 加点 (Batch C) と重複範囲限定昇格の判定を、同じ関数 / 同じ式で Strategy に持つ。\n"
            "//  下の 6 関数は ZoneVisualPractical.pine の同名関数の byte コピー (fixture st1_sim が固定)。\n"
            + copies + EVAL_TAIL +
            ST_END + "===========================================\n")


def st_transform(visual):
    v = visual
    i = v.index("//@version=5\nindicator(")
    j = v.index(IMPORT_LINE)
    head_old = v[:j]
    assert v.count(IMPORT_LINE) == 1 and i < j
    a = v.index(DISP_INPUT_HEAD)
    b = v.index(DISP_INPUT_LAST) + len(DISP_INPUT_LAST)
    assert v[b:b + 1] == "\n"
    d = v.index(DISPLAY_HEAD)
    assert a < b < d and v.count(DISPLAY_HEAD) == 1
    body = v[j:a] + v[b + 1:d]
    return HEADER + body + eval_block(v)


def build():
    return st_transform(git_show(ST_BASE_REV))
