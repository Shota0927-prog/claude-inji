"""XL-1 fixtures — Gold Long Strategy ZoneStrategyXAULong.pine (tests/xal_build.py).

  XLL : static on the delivered Long file — == xal_build.build() (XL-1 + the XA-21 alert layer); strip gives the Short
        Strategy (ZoneStrategyXAU.pine of 2550d27 = the current Short file with XA-21 reverted exactly) byte for byte; the Short file, Engines, Visuals and other symbols are
        unchanged; every adopted Long default of the request table; every other input default equal to the Short file; the
        only changed code lines are the title / shorttitle and the default declarations (no trading / size / order code
        change); strategy() calculation / fill settings, the shared Engine import, the size function and capital kept; the
        header text; the Short adopted values / results are not claimed for Long.

Evidence class: PINE_NOT_VERIFIED (TradingView compile and the user's Last 365 days figures are not reproduced here).
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xal_build as xl           # noqa: E402
import eu_sim as es              # noqa: E402

ROOT = xl.ROOT
raw = lambda p: open(os.path.join(ROOT, p), encoding="utf-8").read()
code_only, input_values, input_decls, func = es.code_only, es.input_values, es.input_decls, es.func
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


TABLE = {"stDir": '"Long Only"', "stMode": '"D: 1M BOS Rebound"', "stTiming": '"SATS Pullback"', "roleMode": '"Retest Confirmed"',
         "thrStrong": "9.0", "stBuffer": "3.0", "stRR": "1.5", "stTpZone": "false", "stBE": "true", "stBEMode": '"Fixed Distance"',
         "stBEDist": "15.0", "stBER": "1.0", "stBETp": "0.5", "stSatsWait": "480", "stSatsShow": "true", "stSatsBody": "true",
         "stSatsNear": "false", "stSatsNearD": "1.0", "stSatsFD": "true", "stSatsF4": "false", "stSatsF1": "false", "stSatsF15": "false",
         "stSatsF5": "false", "stSatsNow": "false", "stSatsNowC": "1", "stSatsNowN": "1", "stSatsTq": "true", "stSatsTqN": "1"}
CHANGED = {"thrStrong", "stMode", "stDir", "stBuffer", "stSatsWait", "stSatsNear", "stSatsFD", "stSatsF4", "stSatsF1", "stSatsNow", "stSatsTq"}


def main_checks():
    L, S = raw(xl.LONG_PATH), raw(xl.SRC_PATH)
    S0 = xl.show(xl.SRC_REV, xl.SRC_PATH)
    others = [p for p in os.listdir(ROOT) if p.endswith(".pine") and p not in (xl.LONG_PATH,)]
    check("XLL-01 the delivered ZoneStrategyXAULong.pine == xal_build.build() and strips back to the Short Strategy of 2550d27 byte for "
          "byte (XA-21 reverted: the XL-1 Long file of d67941f); the Short file ZoneStrategyXAU.pine is that same file plus exactly XA-21; "
          "Engines, Visuals and every other Pine file unchanged",
          L == xl.build() and xl.strip(L) == S0 and xl.strip21(L) == xl.show("d67941f", xl.LONG_PATH) == xl.build1()
          and __import__("xa_build").strip_strategy21(S) == S0
          and not [p for p in others if __import__("btl_build").unapply(p, raw(p)) != xl.show(xl.SRC_REV, p) and p != xl.SRC_PATH])   # later BTL-1 reverted exactly
    iv, isrc = input_values(L), input_values(S)
    bad = {k: (iv.get(k), v) for k, v in TABLE.items() if iv.get(k) != v}
    diff = {k for k in isrc if isrc[k] != iv[k]}
    check("XLL-02 adopted Long table on the delivered file (Long Only, D, SATS Pullback, Retest Confirmed, Strong 9, SL Buffer 3.0, RR 1.5, "
          "opposite TP OFF, BE ON / Fixed 15 / R 1.0 / TP 0.5, wait 480, line ON, body ON, near OFF / 1.0, filter D ON only, immediate OFF / "
          "Nc 1 / Nz 1, pull expiry ON / 1); the defaults that differ from the Short file are exactly these %d; every other input equal "
          "(all options kept)" % len(CHANGED),
          not bad and diff == CHANGED and set(iv) == set(isrc)
          and all(re.sub(r"input\.\w+\([^,]+,", "", input_decls(L)[k].split("\n")[0]) == re.sub(r"input\.\w+\([^,]+,", "", input_decls(S)[k].split("\n")[0])
                  for k in CHANGED), str((bad, diff ^ CHANGED)))
    sl = [x.strip() for x in code_only(S).split("\n")]
    ll = [x.strip() for x in code_only(L).split("\n")]
    gone = sorted(set(sl) - set(ll))
    new = sorted(set(ll) - set(sl))
    allowed = lambda l: l.startswith(("title ", "shorttitle ", '"', "tooltip")) or re.match(r"^(\w+)\s*=\s*input\.", l)
    check("XLL-03 only the name and defaults: every changed code line is the title / shorttitle, an input declaration line (the %d defaults) "
          "or a tooltip string; trading, Zone, SATS, size, order, breakeven and alert-free code identical" % len(CHANGED),
          all(allowed(l) for l in gone + new) and len([l for l in new if re.match(r"^\w+\s*=\s*input\.", l)]) == len(CHANGED)
          and code_only(L).count("\n") == code_only(S).count("\n"), str([l for l in gone + new if not allowed(l)]))
    st = lambda t: re.sub(r'\s+title\s+= "[^"]*",\n\s+shorttitle\s+= "[^"]*",\n', "", es.seg(t, "strategy(", "import "))
    check("XLL-04 strategy(): title 'Zone Strategy XAU Long' / shorttitle 'ZONE-ST-L' (Short: 'Zone Strategy XAU' / 'ZONE-ST'); every "
          "calculation / fill / capital setting identical (initial capital 300,000 JPY, calc_on_every_tick true (XA-21), process_orders_on_close "
          "false, pyramiding 0); the shared Engine import ZoneEnginePracticalXAUUSD/2; f_stQty / f_stTp / f_satBand / f_satHist / f_beTrig "
          "identical; budget 300,000 x 3 %",
          '     title                  = "Zone Strategy XAU Long",\n' in L and '     shorttitle             = "ZONE-ST-L",\n' in L
          and st(L) == st(S) and "initial_capital        = 300000," in L and "currency.JPY" in L and "calc_on_every_tick     = true," in L
          and "import sekine3310/ZoneEnginePracticalXAUUSD/2 as zn" in __import__("xal_build").strip24(L)     # /3 from XA-24 (pinned in pf_sim)
          and all(func(L, h) == func(S, h) for h in ("f_stQty(int side, float ref, float sl) =>", "f_stTp(", "f_satBand() =>",
                                                    "f_satHist(int side, float L, int q) =>", "f_beTrig(", "f_hPick(", "f_satPick("))
          and iv["stCapBase"] == "300000.0" and iv["stRiskPct"] == "3.0")
    hdr = L[:L.index("//@version=5")]
    long_hdr = hdr[:hdr.index("//  XA-3:")]
    check("XLL-05 header: 'Gold Long の直近365日の比較から採用した初期値。今回の組み合わせでの2年間の成績・将来の有効性は未確認' with the "
          "adopted Long values; the XA-* lines are marked as the Short history; no Short result / Short adoption is stated as a Long result "
          "(no 円 / PF / 取引数 figures in the Long block); tooltips of the changed defaults name the Long values",
          xl.NOTE in long_hdr and "Strong 閾値 9" in long_hdr and "SATS 待機期限 480分" in long_hdr and "即時エントリー OFF" in long_hdr
          and "下の XA-* 行はゴールド (Short 版) の変更履歴" in long_hdr and not re.search(r"円|PF|取引数|勝率|DD", long_hdr)
          and "Long 版の初期 OFF" in input_decls(L)["stSatsNow"] and "Long 版の初期 ON・1本" in input_decls(L)["stSatsTq"]
          and "Long 版の初期: 日足だけ ON" in input_decls(L)["stSatsFD"] and "Long 版の初期 OFF" in input_decls(L)["stSatsNear"])
    muts = [L.replace('stSatsNow = input.bool(false,', 'stSatsNow = input.bool(true,'),
            L.replace("thrStrong = input.float(9.0,", "thrStrong = input.float(10.0,"),
            L.replace("    int  qUse  = live ? q : bar_index", "    int  qUse  = rA ? bar_index : q")]
    check("XLL-06 mutations (Short's immediate ON carried over, Strong 10, a logic change) do not strip back to the Short Strategy",
          all(m != L and xl.strip(m) != S0 for m in muts))


def main():
    try:
        main_checks()
    except Exception:
        import traceback
        check("main_checks completed without error", False, traceback.format_exc()[-900:])
    fails = 0
    for nm, ok, d in RESULTS:
        fails += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {nm[:150].ljust(150)}  {'' if ok else d}")
    print(f"\n{len(RESULTS) - fails}/{len(RESULTS)} passed  [PINE_NOT_VERIFIED: exact build / static]")
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
