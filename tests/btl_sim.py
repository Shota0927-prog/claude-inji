"""BTL-1 fixtures — BTCUSD Long adopted defaults on ZoneStrategyBTCUSD.pine (tests/btl_build.py).

  BL : static on the delivered file — == btl_build.build(); strip gives the 7705907 file byte for byte; every other Pine file
       (the BTC Visual / Engine, shared Engines, other symbols, Gold) unchanged; every value of the request table on the delivered
       file; the defaults that differ from 7705907 are exactly the ten listed; SL Buffer (no adopted value) unchanged; only input
       declarations / their tooltips / the header change; every changed input is already wired (Engine config / Strategy code);
       with the old defaults put back the code is identical (the same inputs give the same trading); no performance figure is
       claimed in the file
  BU : mutations do not strip back to 7705907

Evidence class: PINE_NOT_VERIFIED (TradingView compile / Strategy Tester figures are not reproduced here).
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import btl_build as bl           # noqa: E402
import eu_sim as es              # noqa: E402

ROOT = bl.ROOT
raw = lambda p: open(os.path.join(ROOT, p), encoding="utf-8").read()
code_only, input_values, input_decls = es.code_only, es.input_values, es.input_decls
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


# the request table (every listed item; values in the Pine literal form)
TABLE = {"stMode": '"D: 1M BOS Rebound"', "stTiming": '"Current"', "zoneHalfWidth": "50.0", "clusterDist": "50.0", "fvgMinWidth": "50.0",
         "fvgDirMatch": "true", "thrStrong": "8.0",
         "maTf": '"1"', "maType": '"EMA"', "ma1Len": "2000", "ma2Len": "3000", "scoreMa1": "2.0", "scoreMa2": "2.0", "slopeLookback": "60",
         "slopeThrMod": "10.0", "slopeThrStrong": "30.0", "slopeBonusFlat": "0.0", "slopeBonusMod": "1.0", "slopeBonusStr": "2.0",
         "slopeBonusMode": '"Sum (per MA)"', "maClusterDist": "300.0", "maClusterBonus": "0.0", "maClusterDirBonus": "0.0",
         "hzTf1": '"5"', "hzTf2": '"15"', "hzTf3": '"60"', "pivLen1": "10", "pivLen2": "8", "pivLen3": "6", "scoreHz1": "1.0", "scoreHz2": "2.0",
         "scoreHz3": "3.0", "useDayHL": "true", "scoreDayHL": "2.0", "dayTz": '"Asia/Tokyo"', "dayResetHour": "5", "carryPrevDayHL": "false",
         "dsMode": '"Separate"',
         "accTf1": '"60"', "accTf2": '"240"', "accTf3": '"D"', "scoreAcc1": "3.0", "scoreAcc2": "4.0", "scoreAcc3": "5.0", "accKeep1": "3",
         "accKeep2": "2", "accKeep3": "1", "accScoreMode": '"Max"', "accEdgeMode": '"Once per TF"',
         "enableRn": "false", "confBonus2": "1.0", "confBonus3": "2.0", "confBonus4": "3.0",
         "breakTf": '"5"', "breakBuffer": "50.0", "flipConfirmDist": "100.0", "resetOnReclaim": "true", "trackStaleBars": "1000",
         "trackContinuity": "0.5",
         "stTpZone": "false", "stRR": "1.5", "stBE": "true", "stBEMode": '"Fixed Distance"', "stBEDist": "300.0", "stBER": "0.5", "stBETp": "0.5"}
WIRED = ["zoneCfg.clusterDist          := clusterDist", "zoneCfg.thrStrong            := thrStrong",
         'zoneCfg.accEdgeOnce          := accEdgeMode == "Once per TF"', "zoneCfg.flipConfirmDist      := flipConfirmDist",
         "zoneCfg.trackStaleBars       := trackStaleBars", "int want = fvgDirMatch ?", "float tp   = fillPx + side * stRR * risk",
         "if stBE and oState == 2 and not oBE", ": stBEDist", "r * stBER"]


def gate_static():
    T, T0 = raw(bl.PATH), bl.show(bl.BASE_REV, bl.PATH)
    others = [p for p in os.listdir(ROOT) if p.endswith(".pine") and p != bl.PATH]
    check("BL-01 ZoneStrategyBTCUSD.pine == btl_build.build() and strips back to the 7705907 file byte for byte (unapply too); the BTC "
          "Visual / Engine, the shared Engines, the other symbols' and Gold files unchanged (no Library re-publish)",
          T == bl.build() and bl.strip(T) == T0 and bl.unapply(bl.PATH, T) == T0 and bl.unapply(bl.PATH, T0) == T0
          and not [p for p in others if raw(p) != bl.show(bl.BASE_REV, p)])
    iv, i0 = input_values(T), input_values(T0)
    bad = {k: (iv.get(k), v) for k, v in TABLE.items() if iv.get(k) != v}
    diff = {k: (i0[k], iv[k]) for k in i0 if i0[k] != iv.get(k)}
    check("BL-02 every item of the adopted table on the delivered file (Entry D / Current, Zone Half Width 50, Cluster 50, FVG 50 / "
          "direction ON, Strong 8, MA 1m EMA 2000 / 3000 ..., Swing 5 / 15 / 60, Day H/L ON 2 / Tokyo 05:00 / no carry / Separate, Accum "
          "60 / 240 / D, 3 / 4 / 5, keep 3 / 2 / 1, Max, Once per TF, RN OFF, confluence 1 / 2 / 3, Break 5m / 50 / Flip 100 / reclaim ON / "
          "1000 / 0.5, TP zone OFF, RR 1.5, BE ON Fixed 300, R 0.5, TP ratio 0.5); the defaults changed vs 7705907 are exactly the ten "
          "listed; Long Only kept; SL Buffer 50 unchanged (no adopted value found); same input set",
          not bad and diff == {k: (a, b) for k, a, b in bl.CHANGES} and set(iv) == set(i0) and iv["stDir"] == '"Long Only"'
          and iv["stBuffer"] == i0["stBuffer"] == "50.0", str((bad, diff)))
    gone = sorted(set(l.strip() for l in code_only(T0).split("\n")) - set(l.strip() for l in code_only(T).split("\n")))
    new = sorted(set(l.strip() for l in code_only(T).split("\n")) - set(l.strip() for l in code_only(T0).split("\n")))
    decl = lambda l: re.match(r"^\w+ = input\.", l) or l.startswith("tooltip")
    check("BL-03 only the ten input declarations (and two tooltip strings) change; strategy() settings, the Engine import and every "
          "other code line identical; each changed input is already passed on (Engine config: Cluster / Strong / Accum edge / Flip / "
          "retention; FVG direction, fixed RR, breakeven ON / distance / R in the Strategy code) — no wiring change needed",
          all(decl(l) for l in gone + new) and len([l for l in new if re.match(r"^\w+ = input\.", l)]) == 10
          and es.seg(T, "strategy(", "import ") == es.seg(T0, "strategy(", "import ")
          and re.findall(r"^import .*$", T, re.M) == re.findall(r"^import .*$", T0, re.M) and all(w in T for w in WIRED)
          and code_only(T).count("\n") == code_only(T0).count("\n"), str([l for l in gone + new if not decl(l)]))
    back = T
    for k, a, b in bl.CHANGES:
        d = input_decls(back)[k]
        back = back.replace(d, d.replace(b, a, 1), 1)
    norm = lambda t: re.sub(r'tooltip = "[^"]*"', "tooltip", code_only(t))
    check("BL-04 the same inputs give the same trading: with the old defaults put back, the code (tooltips aside) equals the 7705907 file "
          "line for line (trading, Zone, SATS, size, order, breakeven, alerts, labels untouched)", norm(back) == norm(T0))
    hdr = T[:T.index("//@version=5")]
    blk = hdr[hdr.index("//  BTL-1:"):hdr.index("//  BTS-3:")]
    check("BL-05 header: 'BTCUSD Long の直近365日の検証から採用した初期値 (別期間での検証は未完了・将来の有効性は未確認)', the changed values, "
          "SL Buffer not changed (adopted value unconfirmed); no performance figure (円 / PF / DD / 回数) claimed in the file",
          bl.NOTE in blk and "SL Buffer 50 USD は採用値が未確定のため変更していない" in blk and not re.search(r"円|PF|DD|取引数|回", blk))


def gate_mutation():
    T, T0 = raw(bl.PATH), bl.show(bl.BASE_REV, bl.PATH)
    muts = [T.replace('stBuffer = input.float(50.0,', 'stBuffer = input.float(80.0,'),
            T.replace('breakBuffer = input.float(50.0,', 'breakBuffer = input.float(80.0,'),
            T.replace('stBER = input.float(0.5,', 'stBER = input.float(1.0,'),
            T.replace("zoneCfg.trackStaleBars       := trackStaleBars", "zoneCfg.trackStaleBars       := 500")]
    check("BU-01 mutations (SL Buffer changed, Break Buffer changed, R back to 1.0, a wiring change) do not strip back to 7705907",
          all(m != T and bl.strip(m) != T0 for m in muts))


def main():
    for g in (gate_static, gate_mutation):
        try:
            g()
        except Exception:
            import traceback
            check(f"{g.__name__} completed without error", False, traceback.format_exc()[-900:])
    fails = 0
    for nm, ok, d in RESULTS:
        fails += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {nm[:150].ljust(150)}  {'' if ok else d}")
    print(f"\n{len(RESULTS) - fails}/{len(RESULTS)} passed  [PINE_NOT_VERIFIED: exact build / static]")
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
