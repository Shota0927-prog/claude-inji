"""MSL-1 — Max SL Distance filter on every Zone Strategy (Gold Short / Long / automation copy, USDJPY, EURUSD, GBPJPY, GBPUSD,
BTCUSD). Default OFF: with the filter OFF every Strategy trades, alerts and labels exactly as before (f_stSlOK is constant true).

Each Strategy == its file at BASE_REV + edits(path) (exact replacements, each old once):
  - inputs (own group, before "03 · Strategy Alerts"): Enable Max SL Distance (OFF) and Max SL Distance (per symbol: XAUUSD $ 40.0;
    BTCUSD USD [暫定]; USDJPY / EURUSD / GBPJPY / GBPUSD pips [暫定], 1 pip = 0.01 (JPY pairs) / 0.0001), the unit and f_stSlOK(ref, sl);
  - SL distance = |ref - sl| with the reference each order point already uses (A: limit price; B / C / D, SATS pull-side and
    immediate: the close of the deciding bar); ON: allowed only when distance < limit (the limit itself is blocked; a 1e-6 unit
    tolerance so a float like 39.9999999 for an exact 40.00 is still blocked); ref / sl na -> blocked;
  - four gates (one line each, nothing else changed): the SATS pull-side order (`not na(q)`), the SATS immediate order (`not na(nQty)`),
    the Current order (`not skipRef and not na(pQty)`), and the provisional output (stPvOK / the Gold provisional alert condition).
    A blocked order point behaves exactly like the existing "quantity invalid" case at that point: no strategy.entry, no confirmed
    alert / label (they live inside the order branch), no other candidate is taken; a blocked immediate order falls through to the
    normal SATS wait preparation as before; the wait preparation itself is not filtered (it sends nothing).
Existing positions (SL / TP / breakeven / exits), Zone / FVG / MA / Accum code, candidate priority, sizes, alert texts / JSON and
the duplicate guards are not touched. strip(path, text) reverses the edits exactly (None when not exact); unapply() leaves a text
without them unchanged.
"""
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_REV = "a31e934"
GOLD = ("ZoneStrategyXAU.pine", "ZoneStrategyXAULong.pine", "automation/xau_short/pine/ZoneStrategyXAU_Auto.pine")
# path -> (symbol, unit price per input unit, default limit, input unit label, step, provisional)
CFG = {
    "ZoneStrategyXAU.pine":                                ("XAUUSD", "1.0",    "40.0",   "$",    "0.5",  False),
    "ZoneStrategyXAULong.pine":                            ("XAUUSD", "1.0",    "40.0",   "$",    "0.5",  False),
    "automation/xau_short/pine/ZoneStrategyXAU_Auto.pine": ("XAUUSD", "1.0",    "40.0",   "$",    "0.5",  False),
    "ZoneStrategyUSDJPY.pine":                             ("USDJPY", "0.01",   "40.0",   "pips", "0.5",  True),
    "ZoneStrategyEURUSD.pine":                             ("EURUSD", "0.0001", "25.0",   "pips", "0.5",  True),
    "ZoneStrategyGBPJPY.pine":                             ("GBPJPY", "0.01",   "60.0",   "pips", "0.5",  True),
    "ZoneStrategyGBPUSD.pine":                             ("GBPUSD", "0.0001", "30.0",   "pips", "0.5",  True),
    "ZoneStrategyBTCUSD.pine":                             ("BTCUSD", "1.0",    "1000.0", "USD",  "10.0", True),
}
FILES = tuple(CFG)
NEW_TESTS = ("tests/msl_build.py", "tests/msl_sim.py")
MARK = "// ---- MSL-1 最大SL距離フィルター"


# the one edit MSL-1 makes to tests/xa_build.py (appended after its last line; recorded in cad_adapt.LATER so the older fixtures
# keep accepting xa_build.py exactly): wherever the older checks revert XA-24 (unapply24, the innermost link of their layer chain;
# strip_strategy23, the head of the Gold Strategy strip chain), MSL-1 is reverted first, exactly.
XA_TAIL = ("CUR = __import__(\"bon_build\").strip_bon(CUR) or CUR  # bonus defaults stripped -> '\n"
           "                              '9270c50 text (delta pinned by bon_sim)\\n')]}\n")
XA_HOOK = (XA_TAIL, XA_TAIL + (
    "\n"
    "\n"
    "# ---- MSL-1 (later layer, tests/msl_build.py: Max SL Distance filter on every Strategy) ----------------------------------------\n"
    "#  the older fixtures' revert points also revert MSL-1 first (exactly; a text without it is unchanged): unapply24 (the innermost\n"
    "#  link of their layer chain) and strip_strategy23 (the head of the Gold Strategy strip chain; the MSL-1 edits are the same on\n"
    "#  the Gold Short / Long / automation copy). The functions above are unchanged.\n"
    "_unapply24_xa, _strip_strategy23_xa = unapply24, strip_strategy23\n"
    "\n"
    "\n"
    "def unapply24(path, text):\n"
    "    return _unapply24_xa(path, __import__(\"msl_build\").unapply(path, text))\n"
    "\n"
    "\n"
    "def strip_strategy23(t):\n"
    "    return _strip_strategy23_xa(__import__(\"msl_build\").unapply(STR_PATH, t))\n"))


def show(rev, path):
    return subprocess.run(["git", "-C", ROOT, "show", f"{rev}:{path}"], capture_output=True, text=True).stdout


def _block(path):
    sym, unit, dflt, ul, step, prov = CFG[path]
    tag = "[暫定] " if prov else ""
    if ul == "pips":
        unit_txt = f"{sym}: 1 pip = {unit}。"
    elif sym == "XAUUSD":
        unit_txt = "XAUUSD の価格差 (ドル)。"
    else:
        unit_txt = "BTCUSD の価格差 (USD、pips 換算なし)。"
    note = (f"初期 {dflt} {ul} は暫定値 (検証前・適正値ではない)。" if prov else f"初期 {dflt} ドル。")
    return (
        f"{MARK} (初期 OFF = 従来どおり。生成: tests/msl_build.py) ----\n"
        "//  SL距離 = |Entry 参照価格 − SL|。ON のときだけ SL距離 >= 上限 の新規 Entry を見送る (上限ちょうども見送り)。参照価格は各発注の\n"
        "//  既存の値 (A: 指値価格 / B・C・D・SATS: 発注判断足の終値。次足始値の実約定とはずれる)。発注・確定アラート・確定ラベル・\n"
        "//  仮アラート・仮ラベルが対象。保有中の SL / TP / 建値移動 / 決済は変えない。見送った候補の代わりに別の候補は選ばない\n"
        'var string G_STX = "03 · Strategy Max SL Distance"\n'
        'stMaxSlOn = input.bool(false, "Enable Max SL Distance", group = G_STX,\n'
        '     tooltip = "ON: SL距離 (|Entry 参照価格 − SL|) が上限以上の新規 Entry を発注しない (仮 / 確定アラート・ラベルも出さない)。\\n" +\n'
        '     "OFF: 従来どおり (結果は変わらない)。保有中のポジションには使わない。")\n'
        f'stMaxSl = input.float({dflt}, "{tag}Max SL Distance ({ul})", minval = 0.0, step = {step}, group = G_STX,\n'
        f'     tooltip = "{unit_txt}SL距離がこの値未満なら許可、この値以上 (ちょうどを含む) は見送り。{note}")\n'
        f"float ST_MAXSL_UNIT = {unit}     // 上限 1 単位の価格差\n"
        "// 許可 = OFF、または参照価格・SL が有効で SL距離 (上限の単位) < 上限。1e-6 単位は浮動小数の誤差だけ吸収 (ちょうど上限は見送り)\n"
        "f_stSlOK(float ref, float sl) =>\n"
        "    not stMaxSlOn or (not na(ref) and not na(sl) and math.abs(ref - sl) / ST_MAXSL_UNIT < stMaxSl - 1e-6)\n"
        "\n")


def edits(path):
    ga = 'var string G_STA = "03 · Strategy Alerts"\n'
    eds = [
        ("inputs", ga, _block(path) + ga),
        ("pull", "                float q = f_stQty(pwSide, close, pwSL0)\n                if not na(q)\n",
                 "                float q = f_stQty(pwSide, close, pwSL0)\n                if not na(q) and f_stSlOK(close, pwSL0)     // MSL-1\n"),
        ("now", "and nMtf and nDir and not na(nQty)\n",
                "and nMtf and nDir and not na(nQty) and f_stSlOK(close, pSL)     // MSL-1\n"),
        ("cur", "            else if not skipRef and not na(pQty)\n",
                "            else if not skipRef and not na(pQty) and f_stSlOK(ref, pSL)     // MSL-1\n"),
    ]
    if path in GOLD:
        eds.append(("prov", "if stPvA and pSide != 0 and not na(pvQty) and not array.includes(gProvKeys, pvKey)\n",
                            "if stPvA and pSide != 0 and not na(pvQty) and f_stSlOK(pPx, pSL) and not array.includes(gProvKeys, pvKey)     // MSL-1\n"))
    elif path == "ZoneStrategyUSDJPY.pine":
        eds.append(("prov", "bool  stPvOK   = pSide != 0\n", "bool  stPvOK   = pSide != 0 and f_stSlOK(pPx, pSL)     // MSL-1\n"))
    else:
        eds.append(("prov", "bool  stPvOK   = pSide != 0 and not na(pvQty)\n",
                            "bool  stPvOK   = pSide != 0 and not na(pvQty) and f_stSlOK(pPx, pSL)     // MSL-1\n"))
    return eds


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
    """reverse MSL-1 exactly (-> the Strategy of BASE_REV); None when not exact."""
    return _revert(text, edits(path))


def unapply(path, text):
    """reverse MSL-1 when present (all or nothing): unchanged without it (or for other paths), None with only part of it."""
    text = __import__("bel_build").unapply(path, text)     # the later BEL-1 layer is reverted first, exactly
    if text is None or path not in CFG or (MARK not in text and "f_stSlOK(" not in text):
        return text
    return strip(path, text)


def ok(path, rev=None):
    """MSL-1 accounts for this path exactly vs `rev` (default BASE_REV): one of its new test files, or a Strategy whose MSL-1 edits
    revert to the file of `rev`."""
    if path in NEW_TESTS:
        return True
    if path not in CFG or not os.path.exists(os.path.join(ROOT, path)):
        return False
    s = strip(path, open(os.path.join(ROOT, path), encoding="utf-8").read())
    return s is not None and s == show(rev or BASE_REV, path)


if __name__ == "__main__":
    for p in FILES:
        open(os.path.join(ROOT, p), "w", encoding="utf-8").write(build(p))
        print("written", p)
