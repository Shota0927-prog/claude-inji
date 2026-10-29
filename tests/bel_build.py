"""BEL-1 — new-entry lock after a breakeven exit, until the original TP or SL is reached, on every Zone Strategy (Gold Short /
Long / automation copy, USDJPY, EURUSD, GBPJPY, GBPUSD, BTCUSD). Default OFF: with the lock OFF every Strategy trades, alerts
and labels exactly as before (stLkOn never becomes true, so every added `not stLkBlk` / `not stLkOn` is true).

Each Strategy == its file at BASE_REV + EDITS (exact replacements, each old once; the same text in all eight files):
  - input 'Lock New Entries After BE Until Original TP/SL' (OFF; group 03 · Strategy TP / Breakeven, after the Breakeven inputs,
    independent of Breakeven Stop) and the lock state (var: on, side, original SL, original TP, start bar);
  - release (top of the confirmed 5m block, before (1)): a lock started on an EARLIER confirmed bar is released when this bar's
    high / low reaches the original TP or SL (Long: high >= TP or low <= SL; Short: low <= TP or high >= SL; both on one bar =
    released, no order guessed). The bar of the release is still blocked (stLkBlk); entries are allowed from the next bar;
  - start (inside the existing "position became flat" branch of (1), before its oState := 0): only when the input is ON, the
    breakeven move was in force (oBE, oState 2), the original SL / TP are known, and the last closed trade is this entry closed by
    its own SL/TP order (exit_id == oXid, not strategy.close) on the stop leg (exit price short of the TP: the TP limit fills only
    at the TP or better; a gapped stop fill is still short of the TP). Profit / loss size is not used. Original SL = oSL (the
    breakeven move changes oStop only), original TP = oTP (set once at the fill check), copied into the lock state. The start bar
    itself is blocked and is never used for the release;
  - gates: (4) new entries (Current orders, SATS immediate orders and SATS wait preparation: no wait / pending limit is created
    while locked), the SATS pull-side order (no wait can exist while a position is open, so none exists at the lock start), and
    the provisional gate (provisional alert / label; the Gold / automation provisional alert incl. its PROV JSON).
Existing positions, SL / TP / breakeven, Zone / FVG / MA / Accum code, candidate priority, MSL-1, sizes, alert texts, Auto JSON
(cfg / events) are not touched. strip(text) reverses the edits exactly (None when not exact); unapply() leaves a text without them
unchanged.
"""
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_REV = "7f74b04"
FILES = ("ZoneStrategyXAU.pine", "ZoneStrategyXAULong.pine", "automation/xau_short/pine/ZoneStrategyXAU_Auto.pine",
         "ZoneStrategyUSDJPY.pine", "ZoneStrategyEURUSD.pine", "ZoneStrategyGBPJPY.pine", "ZoneStrategyGBPUSD.pine",
         "ZoneStrategyBTCUSD.pine")
GOLD = FILES[:3]
NEW_TESTS = ("tests/bel_build.py", "tests/bel_sim.py")
MARK = "// ---- BEL-1 建値決済後の新規 Entry ロック"

_BETP = 'stBETp = input.float(0.5, "Breakeven Trigger (TP Ratio)", minval = 0.05, maxval = 1.0, step = 0.05, group = G_STT)\n'
_HEAD = "if is5mChart and barstate.isconfirmed\n    // (1) 発注済み Entry の約定 / 決済を確認する\n"
_FLAT = "    else if oState >= 2 and strategy.opentrades == 0\n        oState := 0\n"
_NEW = "    if oState == 0 and not cancelBar and stSessOK\n"
_PULL = "            if (rebA or rebB) and bodyOK and mtfOK and priceOK and stSessOK and oState == 0\n"
_PV_FX = "bool  stPvGate = is5mChart and not barstate.isconfirmed and oState == 0 and stSessOK\n"
_PV_AU = ("bool  stPvA    = stAlertProv and is5mChart and not barstate.isconfirmed and oState == 0 and stPvSess and "
          "array.get(gProvAlertBar, 0) != time\n")

INPUT = (
    f"{MARK} (初期 OFF = 従来どおり。生成: tests/bel_build.py) ----\n"
    "//  ON: 建値ストップで決済されたら、元のトレードの元 TP / 元 SL のどちらかに価格が届くまで新規 Entry (発注・待機準備・指値・\n"
    "//  仮 / 確定アラート / ラベル・Auto の ENTRY / PROV) を出さない。仮想ポジションは注文を出さず、保有中の管理には関与しない\n"
    'stBeLock = input.bool(false, "Lock New Entries After BE Until Original TP/SL", group = G_STT,\n'
    '     tooltip = "ON: 建値移動後のストップで決済されたとき、その元トレードの元 TP または元 SL に価格が届くまで新規 Entry を禁止する。\\n" +\n'
    '     "建値移動前の決済・通常の TP / SL 決済ではロックしない。Breakeven Stop が OFF なら建値決済がないためロックしない。\\n" +\n'
    '     "解除の判定は建値決済を確認した次の確定 5分足から (Long: 高値 >= 元 TP / 安値 <= 元 SL、Short: 安値 <= 元 TP / 高値 >= 元 SL)。\\n" +\n'
    '     "解除した足はまだ禁止、その次の足から許可。日・週をまたいでも届くまで継続。OFF: 従来どおり。")\n'
    "var bool  stLkOn   = false     // BEL-1 ロック中 (ポジションがなくても維持)\n"
    "var int   stLkSide = 0         // 建値決済した元トレードの方向\n"
    "var float stLkSL   = na        // 元 SL (建値移動前の oSL。建値移動では変わらない値をコピー)\n"
    "var float stLkTP   = na        // 元 TP (約定確認時に確定した oTP)\n"
    "var int   stLkBar  = na        // 建値決済を確認した確定足 (この足の高値・安値は解除に使わない)\n")

RELEASE = (
    "    // BEL-1: 前の確定足までに始まったロックは、この足の高値・安値が元 TP / 元 SL に届いたら解除 (同じ足で両方でも解除のみ。\n"
    "    //   到達順は推測しない)。解除した足はまだ禁止 (stLkBlk)、次の足から新規 Entry 可。OFF では stLkOn が true にならない\n"
    "    bool stLkBlk = stLkOn\n"
    "    if stLkOn and bar_index > stLkBar and (stLkSide == 1 ? (high >= stLkTP or low <= stLkSL) : (low <= stLkTP or high >= stLkSL))\n"
    "        stLkOn := false\n")

START = (
    "        // BEL-1: 建値ストップによる決済だけロックを始める (この足から禁止)。建値移動済み (oBE) の保有が、この Entry の SL/TP 注文\n"
    "        //   (exit_id = oXid。strategy.close ではない) で、TP の手前 (= stop 側。TP の指値は TP 以上でしか約定しない) で決済されたこと\n"
    "        //   で識別する (損益の大きさでは判定しない)。元 SL / 元 TP が不明なら監視できないためロックしない\n"
    "        if stBeLock and oBE and oState == 2 and not na(oSL) and not na(oTP) and strategy.closedtrades > oClosed\n"
    "            int lkC = strategy.closedtrades - 1\n"
    "            if strategy.closedtrades.entry_id(lkC) == oEid and strategy.closedtrades.exit_id(lkC) == oXid and oSide * (strategy.closedtrades.exit_price(lkC) - oTP) < 0\n"
    "                stLkOn   := true\n"
    "                stLkSide := oSide\n"
    "                stLkSL   := oSL\n"
    "                stLkTP   := oTP\n"
    "                stLkBar  := bar_index\n"
    "                stLkBlk  := true\n")


def edits(path):
    eds = [
        ("input", _BETP, _BETP + INPUT),
        ("release", _HEAD, "if is5mChart and barstate.isconfirmed\n" + RELEASE + "    // (1) 発注済み Entry の約定 / 決済を確認する\n"),
        ("start", _FLAT, "    else if oState >= 2 and strategy.opentrades == 0\n" + START + "        oState := 0\n"),
        ("pull", _PULL, _PULL[:-1] + " and not stLkBlk     // BEL-1\n"),
        ("new", _NEW, _NEW[:-1] + " and not stLkBlk     // BEL-1\n"),
    ]
    pv = _PV_AU if path in GOLD else _PV_FX
    eds.append(("prov", pv, pv[:-1] + " and not stLkOn     // BEL-1\n"))
    return eds


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


def build(path):
    return _apply(show(BASE_REV, path), edits(path))


def strip(path, text):
    """reverse BEL-1 exactly (-> the Strategy of BASE_REV); None when not exact."""
    return _revert(text, edits(path))


def unapply(path, text):
    """reverse BEL-1 when present (all or nothing): unchanged without it (or for other paths), None with only part of it."""
    if text is None or path not in FILES or (MARK not in text and "stLkBlk" not in text):
        return text
    return strip(path, text)


# the exact edits BEL-1 makes to older generators / fixtures (unadapt() reverts them; msl_sim pins its own layer through it)
TEST_EDITS = {
    "tests/msl_build.py": [
        ('    if text is None or path not in CFG or (MARK not in text and "f_stSlOK(" not in text):\n',
         '    text = __import__("bel_build").unapply(path, text)     # the later BEL-1 layer is reverted first, exactly\n'
         '    if text is None or path not in CFG or (MARK not in text and "f_stSlOK(" not in text):\n')],
    "tests/cad_adapt.py": [
        ('             "tests/msl_build.py", "tests/msl_sim.py")                                       # new in the later layer MSL-1 (Max SL Distance filter)\n',
         '             "tests/msl_build.py", "tests/msl_sim.py",                                       # new in the later layer MSL-1 (Max SL Distance filter)\n'
         '             "tests/bel_build.py", "tests/bel_sim.py")                                       # new in the later layer BEL-1 (breakeven exit lock)\n')],
    "tests/au_build.py": [
        ('             "tests/msl_build.py", "tests/msl_sim.py")\n',
         '             "tests/msl_build.py", "tests/msl_sim.py",\n'
         '             # later layer BEL-1 (breakeven exit lock): its generator / fixture (the Pine files through bel_build.unapply)\n'
         '             "tests/bel_build.py", "tests/bel_sim.py")\n')],
    "tests/msl_sim.py": [
        ('CUR = {p: raw(p) for p in mb.FILES}\n',
         'CUR = {p: __import__("bel_build").unapply(p, raw(p)) for p in mb.FILES}     # the later BEL-1 layer reverted exactly (pinned in bel_sim)\n'),
        ('    bad = sorted(m for m in mod if m not in mb.FILES and m not in mb.NEW_TESTS\n'
         '                 and not (m in TEST_EDITS and revert(raw(m), TEST_EDITS[m]) == mb.show(B, m)))\n',
         '    bad = sorted(m for m in mod if m not in mb.FILES and m not in mb.NEW_TESTS and m not in __import__("bel_build").NEW_TESTS\n'
         '                 and not (m in TEST_EDITS and revert(__import__("bel_build").unadapt(m, raw(m)), TEST_EDITS[m]) == mb.show(B, m)))\n')],
}


def unadapt(path, text):
    """a test file with its BEL-1 edits reverted (all or nothing; unchanged without them)."""
    pairs = TEST_EDITS.get(path, [])
    if text is None or not pairs or all(text.count(b) == 0 for _, b in pairs):
        return text
    return _revert(text, [("", a, b) for a, b in pairs])


def ok(path, rev=None):
    """BEL-1 accounts for this path exactly vs `rev` (default BASE_REV): a new test file, or a Strategy whose BEL-1 edits revert
    to the file of `rev`."""
    if path in NEW_TESTS:
        return True
    if path not in FILES or not os.path.exists(os.path.join(ROOT, path)):
        return False
    s = strip(path, open(os.path.join(ROOT, path), encoding="utf-8").read())
    return s is not None and s == show(rev or BASE_REV, path)


if __name__ == "__main__":
    for p in FILES:
        open(os.path.join(ROOT, p), "w", encoding="utf-8").write(build(p))
        print("written", p)
    for p, pairs in TEST_EDITS.items():
        t = open(os.path.join(ROOT, p), encoding="utf-8").read()
        if all(t.count(b) == 0 for _, b in pairs):
            for a, b in pairs:
                assert t.count(a) == 1, (p, a[:60])
                t = t.replace(a, b)
            open(os.path.join(ROOT, p), "w", encoding="utf-8").write(t)
            print("adapted", p)
