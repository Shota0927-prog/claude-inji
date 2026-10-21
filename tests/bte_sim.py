"""BTE-1 fixtures — dedicated BTCUSD Engine (ZoneEnginePracticalBTCUSD) and the BTC Visual / Strategy import switch.

  BE : static — the Engine == ZoneEnginePracticalGBPJPY.pine (the published ZoneEnginePracticalGBPJPY/3 source) except the
       library name, same exports; the BTC Visual / Strategy rebuild from their generators and strip back to e1c3cea byte for
       byte; their only code change is the import line (both ZoneEnginePracticalBTCUSD/1); every input, the sizing, the
       Entry / order / alert / label code and the request list unchanged; Visual / Strategy Zone parity kept; vs e1c3cea
       only the BTC Pine files (exactly), the new files and the exactly-recorded test / generator edits change

Evidence class: PINE_NOT_VERIFIED (library publish, TradingView compile / backtest external).
"""
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bte_build as be           # noqa: E402
import btc_build as bb           # noqa: E402
import btcs_build as sb          # noqa: E402
import gbe_build as ge           # noqa: E402
import eu_sim as es              # noqa: E402
import fvg_re10045_sim as fr     # noqa: E402

ROOT = be.ROOT
rd = lambda p: open(os.path.join(ROOT, p), encoding="utf-8").read()
git = lambda *a: subprocess.run(["git", "-C", ROOT] + list(a), capture_output=True, text=True).stdout
code_only, input_decls, input_values, func, seg = es.code_only, es.input_decls, es.input_values, es.func, es.seg
GE, BE = rd(be.ENG_SRC), rd(be.ENG_PATH)
V, S = rd(bb.BTC_PATH), rd(sb.BTS_PATH)
V0, S0 = git("show", f"{be.BASE_REV}:{bb.BTC_PATH}"), git("show", f"{be.BASE_REV}:{sb.BTS_PATH}")
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


def gate_static():
    ev = git("show", "8e94720", "--", "ZoneVisualGBPJPY.pine", "ZoneStrategyGBPJPY.pine")
    check("BE-01 /3 source evidence: ZoneEnginePracticalGBPJPY.pine last changed in 73fce49 (GBE-4 Merge Nearby) and not "
          "since; the later commit 8e94720 'import the published Merge Nearby Library as version 3' switched the imports to "
          "/3; gbe_build records IMPORT_GBE = /3; the BTC files imported exactly that before the split",
          git("log", "-1", "--format=%h", "--", be.ENG_SRC).strip() == "73fce49"
          and subprocess.run(["git", "-C", ROOT, "merge-base", "--is-ancestor", "73fce49", "8e94720"]).returncode == 0
          and subprocess.run(["git", "-C", ROOT, "merge-base", "--is-ancestor", "8e94720", "73fce49"]).returncode != 0 and "+import sekine3310/ZoneEnginePracticalGBPJPY/3 as zn" in ev
          and ge.IMPORT_GBE == bb.IMPORT_GBE and re.findall(r"^import .*$", V0 + S0, re.M) == [bb.IMPORT_GBE.strip()] * 2)
    exports = lambda t: re.findall(r"^export .*$", t, re.M)
    types = lambda t: re.findall(r"^export type \w+\n(?:    .*\n)+", t, re.M)
    check("BE-02 Engine: ZoneEnginePracticalBTCUSD.pine == build from the GBPJPY/3 source; code identical except the library "
          "name (Zone generation, scoring, Accum Sum / Max and edges, Day/Swing merge, RN, Break / Flip, Track unchanged); "
          "every export, type field and default identical",
          be.build_engine() == BE and be.strip_engine(BE) == GE
          and code_only(BE).replace('library("ZoneEnginePracticalBTCUSD", overlay = true)', 'library("ZoneEnginePracticalGBPJPY", overlay = true)') == code_only(GE)
          and exports(BE) == exports(GE) and len(exports(BE)) > 30 and types(BE) == types(GE) and len(types(BE)) >= 5)
    check("BE-03 BTC Visual / Strategy rebuild from btc_build / btcs_build and strip the new layer (BTC-4 / BTS-3) back to "
          "e1c3cea byte for byte", bb.build() == V and sb.build() == S and bb.strip_btc4(V) == V0 and sb.strip_bts3(S) == S0
          and bb.btc3_transform(rd(bb.SRC_PATH)) == V0 and sb.bts2_transform(rd(sb.SRC_PATH)) == S0)
    cv, cs = es.changed_code(V0, V), es.changed_code(S0, S)
    imp = sorted([bb.IMPORT_GBE.strip(), bb.IMPORT_BTE.strip()])
    check("BE-04 the only code change in each file is the import line (GBPJPY/3 -> ZoneEnginePracticalBTCUSD/1); every other "
          "change is a comment", sorted(cv) == imp and sorted(cs) == imp, str((cv, cs)))
    check("BE-05 both files import sekine3310/ZoneEnginePracticalBTCUSD/1; Visual / Strategy Zone parity kept (Zone input "
          "declarations, ZoneCfg, feeds, FVG Batch A, FVG scoring functions identical)",
          re.findall(r"^import .*$", V + S, re.M) == ["import sekine3310/ZoneEnginePracticalBTCUSD/1 as zn"] * 2
          and re.findall(r"^zoneCfg\.\w+\s*:=.*$", V, re.M) == re.findall(r"^zoneCfg\.\w+\s*:=.*$", S, re.M)
          and code_only(seg(V, "// ==== FVG Batch A (begin)", "// ==== FVG Batch A (end)"))
          == code_only(seg(S, "// ==== FVG Batch A (begin)", "// ==== FVG Batch A (end)"))
          and all(code_only(func(V, h)).rstrip() == code_only(func(S, h)).rstrip() for h in es.ZONE_FNS)
          and all(input_decls(V)[n] == input_decls(S)[n] for n in input_decls(S[:S.index("// ==== ZONE Strategy · Zone evaluation (begin)")])))
    req = lambda t: re.findall(r"request\.\w+\(", code_only(t))
    check("BE-06 unchanged: every input declaration (defaults, ranges, tooltips), the size function (convert_to_symbol, "
          "pointvalue, step floor, budget re-check, minimum), Entry / order / weekend / alert / label code, "
          "calc_on_every_tick, the Visual confirmed-bar update; request lists equal (Visual 10, Strategy 11)",
          input_decls(V) == input_decls(V0) and input_decls(S) == input_decls(S0)
          and func(S, "f_stQty(int side, float ref, float sl) =>") == func(S0, "f_stQty(int side, float ref, float sl) =>")
          and code_only(S[S.index("var string G_ST ="):]) == code_only(S0[S0.index("var string G_ST ="):])
          and "calc_on_every_tick     = true," in S and "if is5mChart and barstate.isconfirmed\n    zoneCountNow := zn.update(" in V
          and req(V) == req(V0) and len(req(V)) == 10 and req(S) == req(S0) and len(req(S)) == 11
          and all(fr.lint_eager_guards(code_only(t)) == [] for t in (BE, V, S)))
    mod = git("diff", "--name-only", "--diff-filter=MDR", be.BASE_REV, "--").split()
    rest = [m for m in mod if not (be.bte_pine_ok(m, be.BASE_REV) or be.test_ok(m) or __import__("xa_build").xa_ok(m, be.BASE_REV)
                                   or __import__("uj3_adapt").pine_ok(m, be.BASE_REV))]   # XA-1 / UJ-3: exact
    check("BE-07 vs e1c3cea: the BTC Visual / Strategy differ exactly by the new layer, every other changed file is a test / "
          "generator whose edits are recorded exactly in bte_build.TEST_ADAPT; GBPJPY Engine, shared Engines and other "
          "symbols' Pine files untouched", set(mod) >= {bb.BTC_PATH, sb.BTS_PATH} and not rest
          and not [m for m in mod if m.endswith(".pine") and m not in (bb.BTC_PATH, sb.BTS_PATH)
                   and not __import__("xa_build").xa_ok(m, be.BASE_REV) and not __import__("uj3_adapt").pine_ok(m, be.BASE_REV)], str(rest))
    m = S.replace("import sekine3310/ZoneEnginePracticalBTCUSD/1 as zn", "import sekine3310/ZoneEnginePracticalGBPJPY/3 as zn")
    check("BE-08 mutation: a Strategy still importing GBPJPY/3 (Visual / Strategy mismatch) is detected",
          re.findall(r"^import .*$", V + m, re.M) != ["import sekine3310/ZoneEnginePracticalBTCUSD/1 as zn"] * 2
          and sb.strip_bts3(m) is None)


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
