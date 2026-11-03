"""LBS-1 — the five symbol versions of the Zone Combo Lab (BTCUSD / GBPJPY / USDJPY / EURUSD / GBPUSD), built from the gold
version ZoneComboLabXAU.pine as of LAB-5 (3be168d) by an exact list of edits (each old text must occur exactly `count` times).

  python3 tests/lbs_build.py              # (re)writes the five files from the pinned gold source
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
    return p in NEW_FILES


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
        for s in SYMBOLS:
            open(os.path.join(ROOT, path(s)), "w", encoding="utf-8").write(build(s, g))
            print("wrote", path(s))
