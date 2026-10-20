"""XA-1 fixtures — Gold comparison defaults in ZoneStrategyXAU.pine (ZONE-ST) and ZoneVisualPractical.pine (ZONE-P).

  XS : static — both files rebuild from f253890 + the XA-1 edits and strip back byte for byte; the code delta is only the
       specified input defaults; the table (Zone Half Width 6, Cluster 5, Break 10, Flip 10 in both; Strategy Entry C, Short
       Only, SL Buffer 3, RR 1.5, opposite-zone TP OFF, breakeven OFF); Visual / Strategy shared Zone inputs and ZoneCfg
       identical; every other input, strategy() (capital 10,000, fixed qty 1, no commission / slippage / margin added),
       Engine import /6, logic unchanged; vs f253890 only these two Pine files (exactly) and exactly-recorded test edits

Evidence class: PINE_NOT_VERIFIED (TradingView backtest not reproduced locally).
"""
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xa_build as xb            # noqa: E402
import eu_sim as es              # noqa: E402

ROOT = xb.ROOT
rd = lambda p: open(os.path.join(ROOT, p), encoding="utf-8").read()
git = lambda *a: subprocess.run(["git", "-C", ROOT] + list(a), capture_output=True, text=True).stdout
code_only, input_decls, input_values, seg = es.code_only, es.input_decls, es.input_values, es.seg
V, S = rd(xb.VIS_PATH), rd(xb.STR_PATH)
V0, S0 = xb.show(xb.BASE_REV, xb.VIS_PATH), xb.show(xb.BASE_REV, xb.STR_PATH)
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


ZONE = {"zoneHalfWidth": "6.0", "clusterDist": "5.0", "breakBuffer": "10.0", "flipConfirmDist": "10.0"}
ST = {"stMode": '"C: Candle Pattern"', "stDir": '"Short Only"', "stBuffer": "3.0", "stRR": "1.5", "stTpZone": "false",
      "stBE": "false"}
CHANGED_V = {"zoneHalfWidth", "breakBuffer"}
CHANGED_S = CHANGED_V | {"stMode", "stDir", "stTpZone"}


def gate_static():
    check("XS-01 both files == f253890 + the XA-1 edits (rebuild identical) and strip back byte for byte",
          xb.build_visual() == V and xb.build_strategy() == S and xb.strip_visual(V) == V0 and xb.strip_strategy(S) == S0
          and all(k in ("header", "default") for k, _, _ in xb.VISUAL_EDITS + xb.STRATEGY_EDITS))
    bad = [l for old, new, names in ((V0, V, CHANGED_V), (S0, S, CHANGED_S)) for l in es.changed_code(old, new)
           if not re.match(r"^(" + "|".join(sorted(names)) + r")\s*=\s*input\.\w+\(", l)]
    check("XS-02 the code delta is only the specified input defaults (Visual: Half Width, Break Buffer; Strategy: those + "
          "Entry Mode, Direction, opposite-zone TP); no logic / order / alert / label / Engine change", not bad, str(bad[:4]))
    vv, vs = input_values(V), input_values(S)
    zb = [n for n, x in ZONE.items() if vv.get(n) != x or vs.get(n) != x]
    sb = [n for n, x in ST.items() if vs.get(n) != x]
    check("XS-03 table values: Zone Half Width 6, Cluster 5, Break 10, Flip 10 (both files); Strategy Entry C: Candle Pattern, "
          "Short Only, SL Buffer 3, fixed RR 1.5, opposite-zone TP OFF, breakeven OFF", not zb and not sb, str((zb, sb)))
    vd, sd = input_decls(V), input_decls(S)
    zone_names = set(input_decls(S[:S.index("// ==== ZONE Strategy · Zone evaluation (begin)")]))
    check("XS-04 Visual / Strategy share every Zone input declaration and ZoneCfg assignment",
          zone_names and all(vd.get(n) == sd[n] for n in zone_names)
          and re.findall(r"^zoneCfg\.\w+\s*:=.*$", V, re.M) == re.findall(r"^zoneCfg\.\w+\s*:=.*$", S, re.M),
          str([n for n in zone_names if vd.get(n) != sd.get(n)]))
    same_v = [n for n in input_decls(V0) if n not in CHANGED_V and input_decls(V0)[n] != vd.get(n)]
    same_s = [n for n in input_decls(S0) if n not in CHANGED_S and input_decls(S0)[n] != sd.get(n)]
    check("XS-05 everything else unchanged: all other inputs (Accum detection, MA / Swing / FVG / RN / session / BE trigger / "
          "TP-zone RR ...), strategy() options (initial capital 10,000, fixed qty 1, no currency / commission / slippage / "
          "margin added), Engine import ZoneEnginePractical/6, Entry / Direction option lists",
          not same_v and not same_s and set(input_decls(V0)) == set(vd) and set(input_decls(S0)) == set(sd)
          and seg(S, "strategy(", "import ") == seg(S0, "strategy(", "import ")
          and "initial_capital        = 10000," in S and "default_qty_type       = strategy.fixed," in S
          and "default_qty_value      = 1)" in S and not re.search(r"commission|slippage|margin_|currency\s*=", seg(S, "strategy(", "import "))
          and re.findall(r"^import .*$", V + S, re.M) == ["import sekine3310/ZoneEnginePractical/6 as zn"] * 2
          and 'options = ["Long Only", "Short Only", "Both"]' in S and '"D: 1M BOS Rebound"], group = G_ST)' in S,
          str((same_v, same_s)))
    hdr = V[:V.index("//@version=5")] + S[:S.index("//@version=5")]
    check("XS-06 header: 比較継続中の初期値 (not optimised / future validity not confirmed) in both files; no completion claim",
          hdr.count(xb.NOTE) == 2 and not re.search(r"最適値です|最適化済み|検証完了|将来も有効", hdr.replace(xb.NOTE, "")))
    mod = git("diff", "--name-only", "--diff-filter=MDR", xb.BASE_REV, "--").split()
    rest = [m for m in mod if not (xb.xa_ok(m, xb.BASE_REV) or xb.test_ok(m))]
    check("XS-07 vs f253890: ZONE-P / ZONE-ST differ exactly by XA-1; every other changed file is a test / generator whose edits "
          "are recorded exactly in xa_build.TEST_ADAPT; other Pine files and Engines untouched",
          set(xb.XA_FILES) <= set(mod) and not rest and not [m for m in mod if m.endswith(".pine") and m not in xb.XA_FILES],
          str(rest))
    m = S.replace('stTpZone = input.bool(false', 'stTpZone = input.bool(true')
    check("XS-08 mutation: a Strategy with opposite-zone TP still ON is detected", input_values(m)["stTpZone"] == "true"
          and xb.strip_strategy(m) is None)


def main():
    try:
        gate_static()
    except Exception:
        import traceback
        check("gate_static completed without error", False, traceback.format_exc()[-900:])
    fails = 0
    for n, ok, d in RESULTS:
        fails += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {n[:150].ljust(150)}  {'' if ok else d}")
    print(f"\n{len(RESULTS) - fails}/{len(RESULTS)} passed  [PINE_NOT_VERIFIED: exact build / static]")
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
