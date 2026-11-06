"""LBS-1 — the five symbol versions of the Zone Combo Lab (BTCUSD / GBPJPY / USDJPY / EURUSD / GBPUSD), built from the gold
version ZoneComboLabXAU.pine as of LAB-5 (3be168d) by an exact list of edits (each old text must occur exactly `count` times).

  python3 tests/lbs_build.py              # (re)writes the five files (and the gold version with the ZG layer) from the pinned gold source
  python3 tests/lbs_build.py --register   # the registration edits in the older fixtures (tests/lab2_build.py, tests/cad_adapt.py)

What the edits change (nothing else; tests/lbs_sim.py LBS-01 rebuilds every file and compares byte for byte):
  * names: strategy title / shorttitle, the header line and a header block for the symbol version
  * the 9 price-distance inputs: unit pips (FX) / dollars (BTCUSD), symbol defaults, labels; the inputs get an `In` suffix and an
    `LBS Unit` block (before the feeds) converts each of them ONCE into a price difference with the fixed pip size of the symbol
    (GBPJPY / USDJPY 0.01, EURUSD / GBPUSD 0.0001, BTCUSD 1 dollar = 1). The rest of the script (the FVG feeds, the logic) keeps
    using the converted names (zHalf, zcMerge, zfMinW, fvMinW, stSatsNearD, slBuf, maxSl, beDist, tpNtf) unchanged
  * defaults: swing 1H / 4H OFF (D / W ON), POC 1H OFF (4H / D / W ON), ZE fib detection ON (4H / D adopted), Zone touch alert ON
  * lot: `mmLotOz` (1 lot = 100 oz) -> `mmLotSize` (1 lot = 100,000 units for FX / 1 BTC), name and default only (same formula)
  * price text (alerts, entry labels, TP text, touch alert lines): "#.##" -> format.mintick (lots / RR / % / yen keep their formats)
"""
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOLD_PATH = "ZoneComboLabXAU.pine"
GOLD_REV = "3be168d"           # LAB-5 (Zone touch alert): the gold version these files are built from
SYMBOLS = ("BTCUSD", "GBPJPY", "USDJPY", "EURUSD", "GBPUSD")
DOC_PATH = "ZONE_COMBO_LAB_SYMBOLS_ja.md"
NEW_FILES = tuple(f"ZoneComboLab{s}.pine" for s in SYMBOLS) + (DOC_PATH, "tests/lbs_build.py", "tests/lbs_sim.py")

# the 9 distance inputs, in the order of the specification table
DIST = ("zHalf", "zcMerge", "zfMinW", "fvMinW", "stSatsNearD", "slBuf", "maxSl", "beDist", "tpNtf")
SPEC = {   # pip (price difference of 1 input unit), unit, lot size, defaults in DIST order
    "BTCUSD": dict(pip=1.0, pipText="1.0", unit="$", unitJa="ドル", unitDef="1 ドル = 価格差 1", lot=1.0, lotText="1.0",
                   lotName="1 lot の BTC 数量", lotStep="0.01", vals=(100, 250, 150, 50, 50, 250, 2000, 750, 250)),
    "GBPJPY": dict(pip=0.01, pipText="0.01", unit="pips", unitJa="pips", unitDef="1 pip = 0.01", lot=100000.0, lotText="100000.0",
                   lotName="1 lot の通貨数量", lotStep="1000.0", vals=(4, 10, 6, 2, 2, 10, 80, 30, 10)),
    "USDJPY": dict(pip=0.01, pipText="0.01", unit="pips", unitJa="pips", unitDef="1 pip = 0.01", lot=100000.0, lotText="100000.0",
                   lotName="1 lot の通貨数量", lotStep="1000.0", vals=(3, 8, 5, 1.5, 1.5, 8, 60, 20, 8)),
    "EURUSD": dict(pip=0.0001, pipText="0.0001", unit="pips", unitJa="pips", unitDef="1 pip = 0.0001", lot=100000.0,
                   lotText="100000.0", lotName="1 lot の通貨数量", lotStep="1000.0", vals=(2, 5, 3, 1, 1, 5, 40, 15, 5)),
    "GBPUSD": dict(pip=0.0001, pipText="0.0001", unit="pips", unitJa="pips", unitDef="1 pip = 0.0001", lot=100000.0,
                   lotText="100000.0", lotName="1 lot の通貨数量", lotStep="1000.0", vals=(3, 8, 5, 1.5, 1.5, 8, 60, 20, 8)),
}
UNIT_BEGIN = "// ==== LBS Unit (begin) "
UNIT_END = "// ==== LBS Unit (end) "


def git(*a):
    return subprocess.run(["git", "-C", ROOT] + list(a), capture_output=True, text=True).stdout


def gold_source():
    """the gold version at GOLD_REV (the files are built from this text, not from the working tree)."""
    return git("show", f"{GOLD_REV}:{GOLD_PATH}")


def fnum(v):
    """a Pine float literal: 100 -> 100.0, 1.5 -> 1.5"""
    return repr(float(v))


def _steps(sym):
    if sym == "BTCUSD":
        return ("10.0", "10.0", "10.0", "10.0", "10.0", "10.0", "50.0", "50.0", "10.0")
    return ("0.5", "0.5", "0.5", "0.1", "0.5", "0.5", "0.5", "0.5", "0.5")


def edits(sym):
    """[(old, new, count)] for one symbol (applied in order)."""
    s = SPEC[sym]
    u = s["unit"]
    v = [f"{x:g}" for x in s["vals"]]          # header / comment text
    d = [fnum(x) for x in s["vals"]]           # input defaults
    stp = _steps(sym)
    E = []
    # ---- names / header ----
    E.append(("//  Zone Combo Lab XAU (LAB-1)  —  XAUUSD 5分足・「Zone 種類 × エントリータイミング」検証用 Strategy\n",
              f"//  Zone Combo Lab {sym} (LBS-1)  —  {sym} 5分足・「Zone 種類 × エントリータイミング」検証用 Strategy\n"
              f"//  ZoneComboLabXAU (LAB-5) の銘柄版。検知式・処理順・売買条件・表示・集計・通知はゴールド版と同じで、変えたのは下の「■ 銘柄版」だけ。\n", 1))
    E.append(("//  ★ TradingView 実機でのコンパイル・バックテスト・再読み込み比較は未実施 (tests/lab_sim.py はロジック区間の変換実行)。\n",
              f"//  ■ 銘柄版 (LBS-1・{sym})\n"
              f"//    計算対象はこの Strategy を追加したチャートの銘柄 (syminfo.tickerid)。5分足専用・確定足処理・calc_on_every_tick = false はそのまま。\n"
              f"//    価格幅の入力は {s['unitJa']} ({s['unitDef']} の固定定義)。下の「LBS Unit」区間で 9 項目を価格差へ一度だけ換算し、FVG 検知関数へ渡す最小幅を含め\n"
              f"//    以降は換算後の値だけを使う (ATR 倍率・割合・本数・金額・lot には掛けない)。初期値: 共通半幅 {v[0]} / 水平線の統合距離 {v[1]} /\n"
              f"//    長期 FVG 最小幅 {v[2]} / 5分足 FVG 最小幅 {v[3]} / SATS 近接 {v[4]} / SL 余白 {v[5]} / 最大 SL 距離 {v[6]} (使う / 使わないは原版どおり OFF) /\n"
              f"//    固定幅の建値 {v[7]} / TP 変更通知の幅 {v[8]} ({s['unitJa']})。\n"
              f"//    数量: 1 lot = {'1 BTC' if sym == 'BTCUSD' else '100,000 通貨'} (入力で変更可)。最小 lot・lot 刻み 0.01"
              f"{' (暫定の初期値。XS の実口座仕様は未確認)' if sym == 'BTCUSD' else ''}。損失予算 → lot → qty は原版と同じ式\n"
              f"//    (strategy.convert_to_symbol / convert_to_account と syminfo.pointvalue)。円口座・30 万円 × 3 % の単利・日本時間 09:00〜翌 02:00 は原版どおり。\n"
              f"//    初期 ON / OFF: 水平線 1H・4H OFF / 日足・週足 ON、出来高POC 1H OFF / 4H・日足・週足 ON、ZE フィボ検知 ON (4H・日足を採用)、\n"
              f"//    Zoneタッチ通知 ON。エントリー条件の「ZE フィボ」は原版どおり OFF (検知とは別の設定)。\n"
              f"//    価格の表示 (通知・エントリーラベル・TP・タッチ通知の価格帯) は format.mintick。外部 POC (MtfPocFeedXAU)・LongFibWave は共用 (同じチャートに追加)。\n"
              "//  ★ TradingView 実機でのコンパイル・バックテスト・再読み込み比較は未実施 (tests/lbs_sim.py はロジック区間の変換実行)。\n", 1))
    E.append(("//    共通幅 (初期 中心から上下 2 ドル。LAB-3e で 6 → 2) は ZA / ZB / ZC / ZD / ZE。",
              f"//    共通幅 (初期 中心から上下 {v[0]} {s['unitJa']}。■ 銘柄版) は ZA / ZB / ZC / ZD / ZE。", 1))
    E.append(("//    初期 SL = 接触時の Zone 全体の外側 + 5 ドル (AND は選んだ帯全体の外側)。",
              f"//    初期 SL = 接触時の Zone 全体の外側 + {v[5]} {s['unitJa']} (AND は選んだ帯全体の外側)。", 1))
    E.append(("//    建値: 固定幅 15 ドル / TP1 (エントリー時点) までの値幅の割合 50 %。",
              f"//    建値: 固定幅 {v[7]} {s['unitJa']} / TP1 (エントリー時点) までの値幅の割合 50 %。", 1))
    E.append(('     title                   = "Zone Combo Lab XAU",\n     shorttitle              = "ZCL-XAU",\n',
              f'     title                   = "Zone Combo Lab {sym}",\n     shorttitle              = "ZCL-{sym}",\n', 1))
    # ---- the 9 distance inputs (unit, default, step, name; variable + In) ----
    E.append(('zHalf = input.float(2.0, "共通の価格帯幅 (中心から上下 $)", minval = 0.0, step = 0.5, group = G_ZW,\n',
              f'zHalfIn = input.float({d[0]}, "共通の価格帯幅 (中心から上下 {u})", minval = 0.0, step = {stp[0]}, group = G_ZW,\n', 1))
    E.append(('zcMerge = input.float(5.0, "水平線の統合距離 ($)", minval = 0.0, step = 0.5, group = G_ZC,\n',
              f'zcMergeIn = input.float({d[1]}, "水平線の統合距離 ({u})", minval = 0.0, step = {stp[1]}, group = G_ZC,\n', 1))
    E.append(('zfMinW = input.float(3.0, "FVG 最小幅 ($)", minval = 0.0, step = 0.5, group = G_ZF,\n',
              f'zfMinWIn = input.float({d[2]}, "FVG 最小幅 ({u})", minval = 0.0, step = {stp[2]}, group = G_ZF,\n', 1))
    E.append(('fvMinW    = input.float(1.0, "FVG 最小幅 ($)", minval = 0.0, step = 0.1, group = G_TA)\n',
              f'fvMinWIn  = input.float({d[3]}, "FVG 最小幅 ({u})", minval = 0.0, step = {stp[3]}, group = G_TA)\n', 1))
    E.append(('stSatsNearD = input.float(1.0, "SATS · 近接許容距離 ($)", minval = 0.0, step = 0.5, group = G_TC)\n',
              f'stSatsNearDIn = input.float({d[4]}, "SATS · 近接許容距離 ({u})", minval = 0.0, step = {stp[4]}, group = G_TC)\n', 1))
    E.append(('slBuf   = input.float(5.0, "SL · Zone の外側 + ($)", minval = 0.0, step = 0.5, group = G_RK)\n',
              f'slBufIn = input.float({d[5]}, "SL · Zone の外側 + ({u})", minval = 0.0, step = {stp[5]}, group = G_RK)\n', 1))
    E.append(('maxSl   = input.float(40.0, "最大 SL 距離 ($、以上は見送り)", minval = 0.0, step = 0.5, group = G_RK)\n',
              f'maxSlIn = input.float({d[6]}, "最大 SL 距離 ({u}、以上は見送り)", minval = 0.0, step = {stp[6]}, group = G_RK)\n', 1))
    E.append(('tpNtf   = input.float(5.0, "TP 変更通知の幅 ($)", minval = 0.0, step = 0.5, group = G_RK,\n',
              f'tpNtfIn = input.float({d[8]}, "TP 変更通知の幅 ({u})", minval = 0.0, step = {stp[8]}, group = G_RK,\n', 1))
    E.append(('beDist  = input.float(15.0, "固定幅 ($)", minval = 0.0, step = 0.5, group = G_BE)\n',
              f'beDistIn = input.float({d[7]}, "固定幅 ({u})", minval = 0.0, step = {stp[7]}, group = G_BE)\n', 1))
    # ---- defaults (gold as actually used) ----
    E.append(('zcUse1 = input.bool(true, "1H Swing", group = G_ZC)\n', 'zcUse1 = input.bool(false, "1H Swing", group = G_ZC)\n', 1))
    E.append(('zcUse2 = input.bool(true, "4H Swing", group = G_ZC)\n', 'zcUse2 = input.bool(false, "4H Swing", group = G_ZC)\n', 1))
    E.append(('zdUse1 = input.bool(true, "1H POC", group = G_ZD)\n', 'zdUse1 = input.bool(false, "1H POC", group = G_ZD)\n', 1))
    E.append(('zeUse  = input.bool(false, "ZE フィボを検知", group = G_ZE,\n', 'zeUse  = input.bool(true, "ZE フィボを検知", group = G_ZE,\n', 1))
    E.append(('ntfTouch  = input.bool(false, "Zoneタッチ通知", group = G_DS,\n', 'ntfTouch  = input.bool(true, "Zoneタッチ通知", group = G_DS,\n', 1))
    # ---- lot ----
    E.append(('mmLotOz   = input.float(100.0, "1 lot のオンス数", minval = 0.0001, step = 1.0, group = G_MM)\n',
              f'mmLotSize = input.float({s["lotText"]}, "{s["lotName"]}", minval = 0.0001, step = {s["lotStep"]}, group = G_MM)\n', 1))
    if sym == "BTCUSD":
        E.append(('mmLotStep = input.float(0.01, "lot 刻み", minval = 0.0001, step = 0.01, group = G_MM)\n',
                  'mmLotStep = input.float(0.01, "lot 刻み", minval = 0.0001, step = 0.01, group = G_MM,\n'
                  '     tooltip = "最小 lot・lot 刻みの 0.01 は暫定の初期値 (XS の実口座の仕様は未確認)。口座の仕様に合わせて変更する。")\n', 1))
    E.append(("mmLotOz", "mmLotSize", 5))
    # ---- unit conversion (once, before the feeds) ----
    conv = "\n".join(f"float {n:<11} = {n + 'In':<13} * LBS_PIP" for n in DIST)
    E.append(("// ============================================================================\n// 02. FEEDS",
              "// ============================================================================\n"
              "// 01b. 価格幅の換算 (LBS-1)\n"
              "// ============================================================================\n"
              "// ==== LBS Unit (begin) =======================================================\n"
              f"//  入力 ({s['unitJa']}) を価格差へここで一度だけ換算する。以降 (FVG 検知関数へ渡す最小幅・ロジック区間) は換算後の値だけを使う。\n"
              f"float LBS_PIP = {s['pipText']}          // {sym}: {s['unitDef']} (固定定義。syminfo.mintick からは求めない)\n"
              + conv + "\n"
              "// ==== LBS Unit (end) =========================================================\n\n"
              "// ============================================================================\n// 02. FEEDS", 1))
    # ---- price text: format.mintick (lots / RR / yen / % unchanged) ----
    E.append(('str.tostring(array.get(o.legPx, k - 1), "#.##")', 'str.tostring(array.get(o.legPx, k - 1), format.mintick)', 1))
    E.append(('" / SL " + str.tostring(o.stop, "#.##")', '" / SL " + str.tostring(o.stop, format.mintick)', 1))
    E.append(('xid + " " + str.tostring(px, "#.##")', 'xid + " " + str.tostring(px, format.mintick)', 1))
    E.append(('str.tostring(z.bot, "#.##") + "〜" + str.tostring(z.top, "#.##")',
              'str.tostring(z.bot, format.mintick) + "〜" + str.tostring(z.top, format.mintick)', 1))
    E.append(('"\\n判断 " + str.tostring(close, "#.##") + "  SL " + str.tostring(pick.sl, "#.##")',
              '"\\n判断 " + str.tostring(close, format.mintick) + "  SL " + str.tostring(pick.sl, format.mintick)', 1))
    return E


# ---- registration in the older fixtures (a layer above LAB-2; same method as lab2_build: exact edits + the unadapt chain) ----
#  * tests/lab2_build.py (the previous top layer): ok() also asks lbs_build.ok() and unadapt() reverts the LBS-1 edits first, so every
#    older fixture (acc_build -> lab_build -> fds_build -> lfw_build -> lab2_build -> lbs_build) accepts exactly the LBS-1 files
#  * tests/cad_adapt.py: LATER_NEW gets the LBS-1 files as a separate statement before the LAB-2 statement (the LAB-2 / LFW-1 / FDS-1 /
#    LAB-1 edit texts stay byte for byte)
def ok(p):
    """LBS-1 accounts for this path exactly: one of its new files."""
    return p in NEW_FILES or __import__("zsy_build").ok(p)     # the later ZSY files: exact


L3 = '__import__("lbs_build")'
LAB2_LINE = 'LATER_NEW = LATER_NEW + ("MtfPocFeedXAU.pine", "tests/lab2_build.py")  # new in the later layer LAB-2 (external POC feed)\n'
TEST_EDITS = {
    "tests/lab2_build.py": [
        ('    """LAB-2 accounts for this path exactly: one of its new files."""\n    return path in NEW_FILES\n',
         '    """LAB-2 accounts for this path exactly: one of its new files."""\n'
         f'    return path in NEW_FILES or {L3}.ok(path)     # the later LBS-1 files: exact\n', 1),
        ('    """a test file with its LAB-2 edits reverted (all or nothing; unchanged without them; None with only part of them)."""\n',
         '    """a test file with its LAB-2 edits reverted (all or nothing; unchanged without them; None with only part of them)."""\n'
         f'    text = {L3}.unadapt(path, text)     # the later LBS-1 test edits are reverted first, exactly\n', 1)],
    "tests/cad_adapt.py": [
        (LAB2_LINE,
         'LATER_NEW = LATER_NEW + ("ZoneComboLabBTCUSD.pine", "ZoneComboLabGBPJPY.pine", "ZoneComboLabUSDJPY.pine", "ZoneComboLabEURUSD.pine",\n'
         '                         "ZoneComboLabGBPUSD.pine", "ZONE_COMBO_LAB_SYMBOLS_ja.md", "tests/lbs_build.py", "tests/lbs_sim.py")'
         '  # new in the later layer LBS-1 (symbol versions)\n' + LAB2_LINE, 1)],
}


def _rsub(text, old, new, count):
    if text is None or text.count(old) != count:
        return None
    return text.replace(old, new)


def apply_edits(p, text):
    for old, new, count in TEST_EDITS[p]:
        text = _rsub(text, old, new, count)
    return text


def unadapt(p, text):
    """a test file with its LBS-1 edits reverted (all or nothing; unchanged without them; None with only part of them)."""
    text = __import__("zsy_build").unadapt(p, text)     # the later ZSY test edits are reverted first, exactly
    eds = TEST_EDITS.get(p, [])
    if text is None or not eds or all(text.count(new) == 0 for _, new, _ in eds):
        return text
    for old, new, count in reversed(eds):
        text = _rsub(text, new, old, count)
    return text


def _sub(text, old, new, count):
    n = text.count(old)
    if n != count:
        raise ValueError(f"edit pattern found {n} times (expected {count}): {old[:80]!r}")
    return text.replace(old, new)


def build(sym, gold=None):
    t = gold if gold is not None else gold_source()
    for old, new, count in edits(sym):
        t = _sub(t, old, new, count)
    for old, new, count in zg_edits(sym):     # the ZG layer (ZG-1 / ZG-2) on top of the symbol edits
        t = _sub(t, old, new, count)
    return t


# ==== ZG layer (ZG-1 / ZG-2): double / triple top / bottom Zone ==========================================================================
#  The ZG edits are applied after the LBS-1 edits (symbol versions) and to the pinned gold source for the gold version (build_gold).
#  The detector is the LongTermDoubleTripleTopBottomXAU detector at ZG_LTB_REV (copied by zg_core with the marked ZG additions).
#  ZG-2: the reversal is judged from the receiving 5m bar (no next-bar wait); the ZG condition counts only when a ZG "use" is ON
#  (cZG and (zgUse1 or zgUse4 or zgUseD)) in f_condTyp, nSel and the AND list; cZG default ON for gold / OFF for the symbols.
import re as _re

ZG_LTB_PATH = "LongTermDoubleTripleTopBottomXAU.pine"
ZG_LTB_REV = "9e92c02"     # LTB-15


def zg_core():
    """the ZG copy of the LTB detector (LtB1 / LtH / ltNew1 / ltCand1 / ltStep1 / ltRevWhy) with the marked ZG additions"""
    src = git("show", f"{ZG_LTB_REV}:{ZG_LTB_PATH}")
    i = src.index("// 監視基準 1 個")
    j = src.index("// ==== LTB Logic (end)")
    body = src[i:j].rstrip("\n")
    body = _re.sub(r"\bEPS\b", "ZG_EPS", body)
    def rep(a, b):
        nonlocal body
        assert body.count(a) == 1, a
        body = body.replace(a, b)
    rep("""                              //   C 反転方向の色ではない / B 実体幅不足 / R 実体比率不足 / E 接触終了 / W 反転待ち終了 / V 基準無効化 / T 監視期限終了)
""", """                              //   C 反転方向の色ではない / B 実体幅不足 / R 実体比率不足 / E 接触終了 / W 反転待ち終了 / V 基準無効化 / T 監視期限終了)
    float  gx                 // 【ZG 追加】2 回目以後の接触群の実体極値 (トップ = 実体上端の最高 / ボトム = 実体下端の最安。接触開始から検知足まで)
""")
    rep("""                        // 反転待ち (接触開始足 = 0 本目〜反転待ちの本数目。接触が続いている足だけ)
""", """                        // 【ZG 追加】2 回目以後の接触群の実体極値 (検知の判定には使わない)
                        if g.cnt >= 2
                            g.gx := na(g.gx) ? (top ? bu : bd) : top ? math.max(g.gx, bu) : math.min(g.gx, bd)
                        // 反転待ち (接触開始足 = 0 本目〜反転待ちの本数目。接触が続いている足だけ)
""")
    rep("""                                     str.tostring(bu, "#.########") + "," + str.tostring(bd, "#.########")
""", """                                     str.tostring(bu, "#.########") + "," + str.tostring(bd, "#.########") + "," +
                                     str.tostring(top ? math.max(P, g.gx) : math.min(P, g.gx), "#.########")     // 【ZG 追加】Zone の基準価格
""")
    head = """// ==== ZG LTB copy (begin) ===================================================
//  LongTermDoubleTripleTopBottomXAU.pine (LTB-15, 9e92c02) の検知処理 (LtB1 / LtH / ltNew1 / ltCand1 / ltStep1 / ltRevWhy) の写し。
//  【変更】EPS → ZG_EPS (この位置で使うため)、基準ごとに 2 回目以後の接触群の実体極値 gx を保持し、検知イベント D の末尾 (16 番目) に
//  Zone の基準価格 (トップ = max(1 回目の山, gx) / ボトム = min(1 回目の谷, gx)) を加える。検知の判定・接触の数え方は変えない
float ZG_EPS = 1e-7
"""
    return head + body + "\n// ==== ZG LTB copy (end) =====================================================\n"


# gold values per TF: piv, wave, buf, dist, gap, body, ratio, wait, max, dir, sep
GOLD = [
    (4, 10, 5, 30, 8, 3, 30, 3, 24),
    (4, 60, 20, 80, 8, 6, 30, 3, 48),
    (4, 40, 20, 120, 8, 12, 30, 3, 24),
]
EXP = [24, 12, 5]
TFN = ["1時間足", "4時間足", "日足"]
TFS = ["1", "4", "D"]

def num(x):
    s = ('%.6f' % x).rstrip('0')
    return s + '0' if s.endswith('.') else s

def inputs(sym, mul, unit):
    """sym: True = symbol version (price inputs are XxxIn, converted in LBS Unit)"""
    sfx = 'In' if sym else ''
    use = 'false' if sym else 'true'
    L = []
    L.append('var string G_ZG = "02g · ZG ダブル / トリプル トップ・ボトム (1H / 4H / D)"')
    for k in range(3):
        n = TFN[k]; s = TFS[k]
        L.append(f'zgUse{s}  = input.bool({use}, "{n}: Strategy で利用", group = G_ZG, inline = "zgu{s}",')
        L.append(f'     tooltip = "ON: この時間足のダブル / トリプルを Zone の一覧に入れ、エントリー条件・SL・TP 候補・「だけ」の判定・タッチ通知に使う。" +')
        L.append(f'     "OFF: 使わない (表示 ON なら帯だけ表示)。")')
        L.append(f'zgShow{s} = input.bool({use}, "表示", group = G_ZG, inline = "zgu{s}",')
        L.append(f'     tooltip = "ON: 帯を表示 (既存の統合表示に入る)。OFF: 表示しない (利用の判定には影響しない)。")')
        L.append(f'zgExp{s}  = input.bool(true, "{n}: 時間で消す", group = G_ZG, inline = "zge{s}")')
        L.append(f'zgExpN{s} = input.int({EXP[k]}, "本数", minval = 1, group = G_ZG, inline = "zge{s}",')
        L.append(f'     tooltip = "検知足 = 0 本目。この本数の{n}が確定した時点で Zone を消す (経過時間ではなく{n}の本数。検知器の最大監視本数とは別)。")')
    L.append(f'zgHalf{sfx} = input.float({num(2 * mul)}, "ZG 帯の幅 (基準価格から上下 {unit})", minval = 0.0, step = {num(0.5 * mul)}, group = G_ZG,')
    L.append(f'     tooltip = "基準価格 = トップは 1 回目の山と 2 回目 (トリプルで初めて発動した場合は 2・3 回目) の接触群の実体上端の高い方、" +')
    L.append(f'     "ボトムは実体下端の低い方 (ヒゲは使わない。接触群は接触開始から検知足まで)。検知時点で固定。帯 = 基準価格 ± この値。")')
    L.append(f'zgRev{sfx}  = input.float({num(5 * mul)}, "ZG 逆行で消す幅 ({unit})", minval = 0.0, step = {num(0.5 * mul)}, group = G_ZG,')
    L.append(f'     tooltip = "検知結果を受け取った確定 5分足 (発動した足) から、トップは max(open, close) > 基準価格 + この値、ボトムは min(open, close) < 基準価格 − この値で消す。" +')
    L.append(f'     "ヒゲだけの突破・ちょうどの値では消さない。")')
    for k in range(3):
        n = TFN[k]; s = TFS[k]
        piv, wave, buf, dist, gap, body, ratio, wait, mx = GOLD[k]
        g = f'G_ZG{s}'
        L.append(f'var string {g} = "02g-{k + 1} · ZG {n}の検知 (LongTermDoubleTripleTopBottomXAU と同じ処理)"')
        L.append(f'zgPiv{s}   = input.int({piv}, "{n}: Pivot 前後の本数", minval = 1, group = {g})')
        L.append(f'zgWave{s}{sfx}  = input.float({num(wave * mul)}, "{n}: 最初の波の最低値幅 ({unit})", minval = 0.0, step = {num(0.5 * mul)}, group = {g})')
        L.append(f'zgBuf{s}{sfx}   = input.float({num(buf * mul)}, "{n}: 接近許容幅 ({unit})", minval = 0.0, step = {num(0.5 * mul)}, group = {g})')
        L.append(f'zgDist{s}{sfx}  = input.float({num(dist * mul)}, "{n}: 接触間の最低離れ幅 ({unit})", minval = 0.0, step = {num(0.5 * mul)}, group = {g})')
        L.append(f'zgGap{s}   = input.int({gap}, "{n}: 接触開始足どうしの最低間隔", minval = 1, group = {g})')
        L.append(f'zgBody{s}{sfx}  = input.float({num(body * mul)}, "{n}: 反転足の最低実体幅 ({unit})", minval = 0.0, step = {num(0.5 * mul)}, group = {g})')
        L.append(f'zgRatio{s} = input.float({ratio}.0, "{n}: 反転足の最低実体比率 (%)", minval = 0.0, maxval = 100.0, step = 1.0, group = {g})')
        L.append(f'zgWait{s}  = input.int({wait}, "{n}: 反転待ち (接触足の後の最大本数)", minval = 0, group = {g})')
        L.append(f'zgMax{s}   = input.int({mx}, "{n}: 基準の最大監視本数", minval = 1, group = {g})')
        L.append(f'zgDir{s}   = input.bool(false, "{n}: 最初の山・谷の方向フィルターを使う", group = {g})')
        L.append(f'zgSep{s}   = input.bool(true, "{n}: 最低離れ幅フィルターを使う", group = {g},')
        L.append(f'     tooltip = "各項目の意味・判定は LongTermDoubleTripleTopBottomXAU と同じ (本数は{n}の bar_index)。検知イベント (反転足の確定) で Zone を発動する。")')
    return '\n'.join(L) + '\n\n'

def unit_lines():
    L = ['float zgHalf      = zgHalfIn      * LBS_PIP     // ZG (ダブル / トリプル) の価格設定']
    L.append('float zgRev       = zgRevIn       * LBS_PIP')
    for s in TFS:
        for nm in ('Wave', 'Buf', 'Dist', 'Body'):
            v = f'zg{nm}{s}'
            L.append(f'float {v.ljust(11)} = {(v + "In").ljust(13)} * LBS_PIP')
    return '\n'.join(L) + '\n'

def zg_feed():
    return '''
// ---- ZG: ダブル / トリプル トップ・ボトム (LTB 検知器を 1H / 4H / D の中で 1 本ずつ。確定した足の結果だけ: 1 本ずらし・lookahead_on) ----
''' + zg_core() + '''
// 対象時間足の中の計算。返すのは確定済みの直前 2 本 (k − 1、k − 2) のブロック (LongTermDoubleTripleTopBottomXAU の f_ltCore のオフセット 1 と同じ)。
//  on = false (利用・表示とも OFF) なら計算しない
f_zgCore(int k, bool on) =>
    var LtH S = k == 0 ? ltNew1(zgPiv1, zgWave1, zgBuf1, zgDist1, zgGap1, zgBody1, zgRatio1 / 100.0, zgWait1, zgMax1, zgDir1, zgSep1) :
         k == 1 ? ltNew1(zgPiv4, zgWave4, zgBuf4, zgDist4, zgGap4, zgBody4, zgRatio4 / 100.0, zgWait4, zgMax4, zgDir4, zgSep4) :
         ltNew1(zgPivD, zgWaveD, zgBufD, zgDistD, zgGapD, zgBodyD, zgRatioD / 100.0, zgWaitD, zgMaxD, zgDirD, zgSepD)
    var string prevBlk = ""
    string blk = on ? ltStep1(S, open, high, low, close, time, time_close, bar_index) : ""
    string out = prevBlk == "" ? blk : prevBlk + ";" + blk
    prevBlk := blk
    out[1]
string zgPk1 = request.security(syminfo.tickerid, "60",  f_zgCore(0, zgUse1 or zgShow1), lookahead = barmerge.lookahead_on)
string zgPk4 = request.security(syminfo.tickerid, "240", f_zgCore(1, zgUse4 or zgShow4), lookahead = barmerge.lookahead_on)
string zgPkD = request.security(syminfo.tickerid, "D",   f_zgCore(2, zgUseD or zgShowD), lookahead = barmerge.lookahead_on)
'''

FUNCS = '''
// ZG: 時間足 0 = 1H / 1 = 4H / 2 = D の設定
f_zgUse(int k) =>
    k == 0 ? zgUse1 : k == 1 ? zgUse4 : zgUseD

f_zgShow(int k) =>
    k == 0 ? zgShow1 : k == 1 ? zgShow4 : zgShowD

f_zgExpOn(int k) =>
    k == 0 ? zgExp1 : k == 1 ? zgExp4 : zgExpD

f_zgExpN(int k) =>
    k == 0 ? zgExpN1 : k == 1 ? zgExpN4 : zgExpND

// ZG: 受信した検知器の出力 (「B,対象足 time,time_close,前の time,基準数,bar_index」+ イベント) から、まだ取り込んでいない確定済みの対象足だけを読む
//  (LongTermDoubleTripleTopBottomXAU の受信と同じ: 対象足の time が前回より新しく、その time_close がこの足の確定までのもの)。
//  戻り値 [取り込んだ最後の time, 記録]: 記録は 6 個ずつ [0 = 対象足 / 1 = 検知, 対象足の bar_index, 基準 ID, 方向 (-1 トップ / 1 ボトム), 回数, 基準価格]
f_zgParse(string pk, int lastT, int tcNow) =>
    array<float> out = array.new_float()
    int lt = lastT
    if not na(pk) and pk != ""
        array<string> evs = str.split(pk, ";")
        bool take = false
        float cbi = na
        for i = 0 to array.size(evs) - 1
            string e = array.get(evs, i)
            if e != ""
                array<string> f = str.split(e, ",")
                string ty = array.get(f, 0)
                if ty == "B"
                    int sT = int(str.tonumber(array.get(f, 1)))
                    int sC = int(str.tonumber(array.get(f, 2)))
                    take := not na(sT) and (na(lt) or sT > lt) and not na(sC) and sC <= tcNow
                    if take
                        lt  := sT
                        cbi := str.tonumber(array.get(f, 5))
                        array.push(out, 0)
                        array.push(out, cbi)
                        array.push(out, na)
                        array.push(out, na)
                        array.push(out, na)
                        array.push(out, na)
                else if take and ty == "D" and array.size(f) > 16
                    array.push(out, 1)
                    array.push(out, cbi)
                    array.push(out, str.tonumber(array.get(f, 1)))
                    array.push(out, str.tonumber(array.get(f, 2)))
                    array.push(out, str.tonumber(array.get(f, 7)))
                    array.push(out, str.tonumber(array.get(f, 16)))
    [lt, out]
'''

KILL = '''
// ZG: Zone を消す (逆行・期限)。利用中なら Zone の一覧・TP 候補から除き、lbDeadNow へ入れて (B3) で待機を解除。表示から外す。
//  同じ帯の他の根拠 (アキュム・水平線など) は消さない。消した根拠は lbZgUsed に残すので復活しない
f_zgKill(int i) =>
    LbZone z = array.remove(lbZgZ, i)
    if z.zgUse
        f_lbRemoveS(z)
        array.push(lbDeadNow, z.id)
    if dsZone and z.zgShow
        f_dsDel(z, false)
    z.dead := true
    true

'''

B1 = '''    // ZG: ダブル / トリプル トップ・ボトム (1H / 4H / D の検知器の検知イベント = 反転足の確定で発動。接触・Pivot の登録だけでは作らない)。
    //  根拠 = 時間足 + 基準 ID で 1 回だけ (ダブルで発動した基準のトリプル・消えた基準の後の検知では作らない)。基準価格・幅・期限は発動時に固定。
    //  期限: 検知足 = 0 本目、その時間足の確定足の bar_index − 検知足 ≥ 本数で消す。逆行: 検知結果を受け取った確定 5分足 (発動した足) から実体端で判定
    //  (処理順: ZG の登録・期限 → 逆行による消滅 → (B2) 接触・(B3) 待機・(B6) 候補。発動した足で消えた Zone は接触・SL / TP 候補に残らない)
    array<string> zgPk = array.from(zgPk1, zgPk4, zgPkD)
    for k = 0 to 2
        [zlt, zrec] = f_zgParse(array.get(zgPk, k), array.get(lbZgLast, k), time_close)
        array.set(lbZgLast, k, zlt)
        int nr = int(array.size(zrec) / 6)
        if nr > 0
            for r = 0 to nr - 1
                int ro  = r * 6
                int rbi = int(array.get(zrec, ro + 1))
                if array.get(zrec, ro) == 0
                    int nzg = array.size(lbZgZ)
                    if f_zgExpOn(k) and nzg > 0
                        for i = nzg - 1 to 0
                            LbZone z = array.get(lbZgZ, i)
                            if z.tf == k and rbi - int(z.infoB) >= f_zgExpN(k)
                                f_zgKill(i)
                else
                    int   zid  = int(array.get(zrec, ro + 2))
                    int   zsd  = int(array.get(zrec, ro + 3))
                    float zcnt = array.get(zrec, ro + 4)
                    float zp   = array.get(zrec, ro + 5)
                    int   ukey = zid * 3 + k
                    if not array.includes(lbZgUsed, ukey) and not na(zp)
                        array.push(lbZgUsed, ukey)
                        if f_zgUse(k) or f_zgShow(k)
                            // sub: 1 トップ (抵抗) / -1 ボトム (支持)。infoA = 回数 (2 ダブル / 3 トリプル)、infoB = 検知足の bar_index、key = 基準 ID
                            LbZone zz = f_lbNew(6, k, zsd == -1 ? 1 : -1, zp, zp - zgHalf, zp + zgHalf, zcnt, rbi, zid)
                            zz.zgUse  := f_zgUse(k)
                            zz.zgShow := f_zgShow(k)
                            if zz.zgUse
                                f_lbAdd(zz)
                            else if dsZone and zz.zgShow
                                f_dsAdd(zz)
                            array.push(lbZgZ, zz)
    int nzg2 = array.size(lbZgZ)
    if nzg2 > 0
        for i = nzg2 - 1 to 0
            LbZone z = array.get(lbZgZ, i)
            if z.sub == 1 ? math.max(open, close) > z.ctr + zgRev + EPS : math.min(open, close) < z.ctr - zgRev - EPS
                f_zgKill(i)
'''

HDR = '''//  ■ ZG ダブル / トリプル トップ・ボトム (ZG-1)
//    LongTermDoubleTripleTopBottomXAU (LTB-15) と同じ検知処理を 1H / 4H / D の中で動かし (時間足ごとの設定・状態)、確定した検知イベントで
//    Zone を発動 (接触・Pivot の登録だけでは作らない。ダブル・トリプルとも)。トップ = 抵抗 / ボトム = 支持。基準価格 = 1 回目の山 (谷) と
//    2 回目 (トリプルで初めて発動ならば 2・3 回目) の接触群の実体上端の高い方 (実体下端の低い方)、検知時点で固定。帯 = 基準価格 ± ZG 幅。
//    消滅: 確定 5分足の実体端が基準価格 + 逆行幅を超えた (ボトムは − 逆行幅を下回った) / 検知足から期限の本数の対象時間足が確定した。
//    根拠 (時間足 + 基準 ID) は 1 回だけ (トリプルで追加・復活しない)。「Strategy で利用」OFF は一覧・条件・SL・TP 候補に入れず表示だけ。
'''


def zg_edits(sym=None):
    """[(old, new, count)] of the ZG layer. sym = None: the gold version / a symbol: applied after edits(sym)"""
    isSym = sym is not None
    mul = 10 if sym == "BTCUSD" else 1
    unit = "$" if (not isSym or sym == "BTCUSD") else "pips"
    E = []
    E.append(("//  ★ TradingView 実機でのコンパイル", HDR + "//  ★ TradingView 実機でのコンパイル", 1))
    E.append(('var string G_TA = "03a · TA 5分足 FVG 吸収 (ACC-5A)"', inputs(isSym, mul, unit) + 'var string G_TA = "03a · TA 5分足 FVG 吸収 (ACC-5A)"', 1))
    E.append(('cZE = input.bool(false, "ZE フィボ", group = G_EN, inline = "cz2")\n',
              'cZE = input.bool(false, "ZE フィボ", group = G_EN, inline = "cz2")\n'
              f'cZG = input.bool({"false" if isSym else "true"}, "ZG ダブル/トリプル", group = G_EN, inline = "cz2",\n'
              '     tooltip = "条件として使うのは、この設定が ON で、時間足ごとの「Strategy で利用」がどれか ON のときだけ (全 OFF なら OR / AND とも ZG を条件に含めない)。" +\n'
              '     "対象は利用 ON の Zone だけ (表示 ON は代わりにならない)。OFF でも利用 ON の Zone は SL・TP 候補に使う。")\n', 1))
    if isSym:
        E.append(("// ==== LBS Unit (end) =", unit_lines() + "// ==== LBS Unit (end) =", 1))
    anchor = 'int satTf1 = request.security(syminfo.tickerid, "60",  f_satTfState(), lookahead = barmerge.lookahead_on)\n'
    E.append((anchor, anchor + zg_feed(), 1))
    E.append(("""    array<int>   mT
    array<int>   mId

// 形成中の Accum""", """    array<int>   mT
    array<int>   mId
    bool  zgUse    = true     // ZG: Strategy で利用 (false = 表示だけ。Zone の一覧・接触・条件・SL・TP 候補に入れない)
    bool  zgShow   = true     // ZG: 表示

// 形成中の Accum""", 1))
    E.append(("// Zone 1 個。typ: 0 ZA / 1 ZB / 2 ZC / 3 ZD / 4 ZF / 5 ZE。", "// Zone 1 個。typ: 0 ZA / 1 ZB / 2 ZC / 3 ZD / 4 ZF / 5 ZE / 6 ZG (tf 0 1H / 1 4H / 2 D)。", 1))
    E.append(("var array<int>    lbNZone    = array.new_int(6, 0)   // 種類ごとの保持数 (ZB は 0〜2、ZE は 0〜8)",
              "var array<int>    lbNZone    = array.new_int(7, 0)   // 種類ごとの保持数 (ZB は 0〜2、ZE は 0〜8、ZG は利用中のものだけ)", 1))
    E.append(("var array<LbZone> lbZeZ      = array.new<LbZone>()      // ZE: 有効なフィボ Zone (時間足ごとに最大 4)\n",
              "var array<LbZone> lbZeZ      = array.new<LbZone>()      // ZE: 有効なフィボ Zone (時間足ごとに最大 4)\n"
              "var array<LbZone> lbZgZ      = array.new<LbZone>()      // ZG: 有効なダブル / トリプル Zone (利用 OFF の表示だけのものを含む)\n"
              "var array<int>    lbZgUsed   = array.new_int()          // ZG: 発動済みの根拠 (基準 ID × 3 + 時間足)。消えた根拠も残して再登録しない\n"
              "var array<int>    lbZgLast   = array.new_int(3, na)     // ZG: 時間足ごとに取り込んだ最後の対象足の time\n", 1))
    E.append(("//  18 含む ZE / 19 だけ ZE)", "//  18 含む ZE / 19 だけ ZE / 20 含む ZG / 21 だけ ZG)", 1))
    E.append(("array.new_int(20, 0)", "array.new_int(22, 0)", 4))
    E.append(("array.new_float(20, 0.0)", "array.new_float(22, 0.0)", 4))
    E.append(("    b == 0 ? 1 : b == 1 ? 2 : b == 2 ? 4 : b == 3 ? 8 : b == 4 ? 16 : 32     // ZE = 5 → 32 (FVG の 16 は変えない)",
              "    b == 0 ? 1 : b == 1 ? 2 : b == 2 ? 4 : b == 3 ? 8 : b == 4 ? 16 : b == 5 ? 32 : 64     // ZE = 5 → 32 (FVG の 16 は変えない)、ZG = 6 → 64", 1))
    E.append(('    t == 0 ? "アキュム" : t == 1 ? "MA" : t == 2 ? "水平線" : t == 3 ? "出来高POC" : t == 5 ? "フィボ" : "FVG"',
              '    t == 0 ? "アキュム" : t == 1 ? "MA" : t == 2 ? "水平線" : t == 3 ? "出来高POC" : t == 5 ? "フィボ" : t == 6 ? "ダブル/トリプル" : "FVG"', 1))
    E.append(('    t == 0 ? (k == 0 ? "1時間足" : k == 1 ? "4時間足" : "日足") : t == 1 ?',
              '    t == 0 or t == 6 ? (k == 0 ? "1時間足" : k == 1 ? "4時間足" : "日足") : t == 1 ?', 1))
    E.append(("    z.typ == 1 ? (z.tf == 0 ? 5 : 4) : z.typ == 0 ? (z.tf == 0 ? 3 : z.tf == 1 ? 2 : 1) : z.typ == 5 ? (z.tf == 0 ? 2 : 1) :",
              "    z.typ == 1 ? (z.tf == 0 ? 5 : 4) : z.typ == 0 or z.typ == 6 ? (z.tf == 0 ? 3 : z.tf == 1 ? 2 : 1) : z.typ == 5 ? (z.tf == 0 ? 2 : 1) :", 1))
    E.append(('     z.typ == 2 ? "水平線" : z.typ == 3 ? "出来高POC" : z.typ == 5 ? "フィボ " + str.tostring(z.infoA) : z.inv ? "iFVG" : "FVG"',
              '     z.typ == 2 ? "水平線" : z.typ == 3 ? "出来高POC" : z.typ == 5 ? "フィボ " + str.tostring(z.infoA) :\n'
              '     z.typ == 6 ? (z.infoA == 3 ? "トリプル" : "ダブル") + (z.sub == 1 ? "トップ" : "ボトム") : z.inv ? "iFVG" : "FVG"', 1))
    # ZG-2: the ZG condition counts only with a ZG "use" ON (f_condTyp → also the AND list; nSel)
    E.append(("    t == 0 ? cZA : t == 1 ? cZB : t == 2 ? cZC : t == 3 ? cZD : t == 4 ? cZF : cZE\n",
              "    t == 0 ? cZA : t == 1 ? cZB : t == 2 ? cZC : t == 3 ? cZD : t == 4 ? cZF : t == 5 ? cZE : cZG and (zgUse1 or zgUse4 or zgUseD)\n" + FUNCS, 1))
    E.append(("    t < 5 ? 1 + t : 18\n", "    t < 5 ? 1 + t : t == 5 ? 18 : 20\n", 1))
    E.append(("    t < 5 ? 6 + t : 19\n", "    t < 5 ? 6 + t : t == 5 ? 19 : 21\n", 1))
    E.append(("            for t = 0 to 5\n                for i = 0 to n - 1", "            for t = 0 to 6\n                for i = 0 to n - 1", 1))
    E.append(("    for t = 0 to 5\n        if f_bit(o.tmask, t)", "    for t = 0 to 6\n        if f_bit(o.tmask, t)", 1))
    E.append(("        for t = 0 to 5\n            if f_condTyp(t)", "        for t = 0 to 6\n            if f_condTyp(t)", 1))
    E.append(("(cZF ? 1 : 0) + (cZE ? 1 : 0)", "(cZF ? 1 : 0) + (cZE ? 1 : 0) + (cZG and (zgUse1 or zgUse4 or zgUseD) ? 1 : 0)", 1))
    E.append(("         z0.typ == 5 ? color.maroon : color.green", "         z0.typ == 5 ? color.maroon : z0.typ == 6 ? color.olive : color.green", 1))
    E.append(("    array.set(lbNZone, z.typ, array.get(lbNZone, z.typ) + 1)\n    if dsZone\n        f_dsAdd(z)",
              "    array.set(lbNZone, z.typ, array.get(lbNZone, z.typ) + 1)\n    if dsZone and z.zgShow\n        f_dsAdd(z)", 1))
    E.append(("// 静的 Zone で [a, b] と重なるものの中に", KILL.lstrip("\n") + "// 静的 Zone で [a, b] と重なるものの中に", 1))
    E.append(("    // ZB: EMA ± 共通幅 (毎足動く)。最初に値が出た足で作り、次の足から接触", B1 + "    // ZB: EMA ± 共通幅 (毎足動く)。最初に値が出た足で作り、次の足から接触", 1))
    # table: two ledger rows (ZG) and the rows below them moved down by 2 (from the bottom so that nothing is moved twice)
    E.append(('"LONG", "SHORT", "フィボ含む", "フィボだけ")', '"LONG", "SHORT", "フィボ含む", "フィボだけ",\n         "ダブル/トリプル含む", "ダブル/トリプルだけ")', 1))
    E.append(("var table lbTbl = table.new(position.bottom_right, 8, 28,", "var table lbTbl = table.new(position.bottom_right, 8, 30,", 1))
    E.append(("    for b = 0 to 19\n", "    for b = 0 to 21\n", 1))
    for n in range(27, 20, -1):
        for c in ((0, 1, 2) if n == 21 else (0, 1)):
            E.append((f"table.cell(lbTbl, {c}, {n},", f"table.cell(lbTbl, {c}, {n + 2},", 1))
    E.append(('"保持 アキュム/MA/水平線/POC/FVG/フィボ"', '"保持 アキュム/MA/水平線/POC/FVG/フィボ/ダブル・トリプル"', 1))
    E.append(('"/" + str.tostring(array.get(lbNZone, 5)), text_size = size.tiny)',
              '"/" + str.tostring(array.get(lbNZone, 5)) + "/" + str.tostring(array.get(lbNZone, 6)), text_size = size.tiny)', 1))
    return E


def build_gold(gold=None):
    """the gold version: the pinned gold source + the ZG layer"""
    t = gold if gold is not None else gold_source()
    for old, new, count in zg_edits(None):
        t = _sub(t, old, new, count)
    return t


def path(sym):
    return f"ZoneComboLab{sym}.pine"


if __name__ == "__main__":
    import sys
    if "--register" in sys.argv:     # the registration edits (once; idempotent)
        for p in TEST_EDITS:
            f = os.path.join(ROOT, p)
            t = open(f, encoding="utf-8").read()
            if all(t.count(new) == 0 for _, new, _ in TEST_EDITS[p]):
                t2 = apply_edits(p, t)
                assert t2 is not None, p
                assert unadapt(p, t2) == t, p
                open(f, "w", encoding="utf-8").write(t2)
                print("adapted", p)
    else:
        g = gold_source()
        assert g, "gold source not found (full history needed: git fetch --unshallow)"
        open(os.path.join(ROOT, GOLD_PATH), "w", encoding="utf-8").write(build_gold(g))     # the gold version with the ZG layer
        print("wrote", GOLD_PATH)
        for s in SYMBOLS:
            open(os.path.join(ROOT, path(s)), "w", encoding="utf-8").write(build(s, g))
            print("wrote", path(s))
