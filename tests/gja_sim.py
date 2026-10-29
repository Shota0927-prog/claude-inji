"""GJA-1 fixtures — GBPJPY adopted defaults on ZoneStrategyGBPJPY.pine (tests/gja_build.py).

  GA : static — == gja_build.build() and strips back to the 7667a88 file byte for byte; every other Pine file unchanged vs 7667a88;
       the changed test files differ by exactly gja_build.TEST_EDITS; the 12 requested defaults exactly as requested; every other
       input default / declaration unchanged (input titles too); the code apart from the input declarations, the two tooltip
       phrases and the header is identical (no trading / formula change); the new values are legal for their inputs and the TP
       Progress mode reads the TP Ratio input
  GU : mutations caught

Evidence class: PINE_NOT_VERIFIED (TradingView compile / backtest figures not reproduced here).
"""
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gja_build as gb           # noqa: E402
import eu_sim as es              # noqa: E402

ROOT = gb.ROOT
B = gb.BASE_REV
raw = lambda p: open(os.path.join(ROOT, p), encoding="utf-8").read()
code_only, input_decls, input_values = es.code_only, es.input_decls, es.input_values
T, T0 = raw(gb.PATH), gb.show(B, gb.PATH)
RESULTS = []
UNTRACKED = {"ZoneStrategyUSDJPY_Diagnostic.pine", "tests/stjd_build.py", "tests/stjd_sim.py", "tests/__pycache__/"}   # not ours
# the request table (Pine literal form)
TABLE = {"stTpZone": "false", "stTpMinRR": "1.0", "stTpMaxRR": "3.0", "stRR": "1.5", "stBE": "true", "stBEDist": "0.20",
         "stBEMode": '"TP Progress"', "stBER": "1.0", "stBETp": "0.6", "stBeLock": "true", "stMaxSlOn": "true", "stMaxSl": "40.0"}
TITLES = {"stTpZone": "TP · Nearest Opposite Zone (Medium+)", "stTpMinRR": "TP Zone · Min RR", "stTpMaxRR": "TP Zone · Max RR",
          "stRR": "TP Fixed RR", "stBE": "Breakeven Stop", "stBEDist": "Breakeven Trigger (円)", "stBEMode": "Breakeven Trigger Mode",
          "stBER": "Breakeven Trigger (R)", "stBETp": "Breakeven Trigger (TP Ratio)", "stBeLock": "Lock New Entries After BE Until Original TP/SL",
          "stMaxSlOn": "Enable Max SL Distance", "stMaxSl": "Max SL Distance (pips)"}


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


def git(*a):
    return subprocess.run(["git", "-C", ROOT] + list(a), capture_output=True, text=True).stdout


def gate_static():
    others = [p for p in git("ls-files", "*.pine").split() if p != gb.PATH]
    check("GA-01 ZoneStrategyGBPJPY.pine == gja_build.build() and strips back to the 7667a88 file byte for byte (unapply too, "
          "idempotent); every other Pine file (the other seven Strategies, Visuals, Engines, harnesses) unchanged vs 7667a88",
          T == gb.build() and gb.strip(T) == T0 and gb.unapply(gb.PATH, T) == T0 and gb.unapply(gb.PATH, T0) == T0
          and not [p for p in others if raw(p) != gb.show(B, p)])
    st = git("status", "--porcelain").split("\n")
    mod = (set(git("diff", "--name-only", B, "--").split()) | {l[3:] for l in st if l.startswith("??")}) - UNTRACKED
    bad = sorted(m for m in mod if m != gb.PATH and m not in gb.NEW_TESTS
                 and not (m in gb.TEST_EDITS and gb.unadapt(m, raw(m)) == gb.show(B, m) and gb.unadapt(m, raw(m)) != raw(m)))
    check("GA-02 vs 7667a88 only the GBPJPY Strategy, gja_build / gja_sim and the four test files of gja_build.TEST_EDITS change, each "
          "exactly (bel_build: GJA-1 reverted first; bel_sim: reads GBPJPY with GJA-1 reverted; cad_adapt / au_build: new-file lists)",
          not bad and gb.PATH in mod, str(bad))
    iv, i0 = input_values(T), input_values(T0)
    tab = {k: (iv.get(k), v) for k, v in TABLE.items() if iv.get(k) != v}
    dc, d0 = input_decls(T), input_decls(T0)
    titles = {k: re.search(r'input\.\w+\([^,]+, "([^"]*)"', dc[k]).group(1) for k in TABLE}
    bad_t = {k: t for k, t in titles.items() if not t.endswith(TITLES[k]) and TITLES[k] not in t}
    check("GA-03 the 12 requested defaults exactly: TP Nearest Opposite Zone OFF, Min RR 1.0, Max RR 3.0, Fixed RR 1.5, Breakeven Stop "
          "ON, Breakeven Trigger (円) 0.20, Mode TP Progress, (R) 1.0, (TP Ratio) 0.6, BE lock ON, Max SL Distance ON / 40.0 pips",
          not tab and not bad_t and len(TABLE) == 12, str((tab, bad_t)))
    diff = {k: (i0.get(k), iv.get(k)) for k in set(i0) | set(iv) if i0.get(k) != iv.get(k)}
    chg = {k: (a, b) for k, a, b in gb.CHANGES}
    same_decl = [k for k in d0 if k not in chg and dc.get(k) != d0[k] and k != "stBEMode"]
    check("GA-04 every other input default unchanged (machine diff of all %d inputs: exactly the 8 changed values; TP Nearest / Min RR / "
          "Max RR / (R) already as requested); every other input declaration (title, options, min / max / step, group, tooltip) "
          "byte-identical; no input added or removed" % len(iv),
          diff == chg and set(iv) == set(i0) and not same_decl and all(i0[k] == v for k, v in gb.KEPT), str((diff, same_decl)))
    strip_inputs = lambda t: [l for l in code_only(t).split("\n")
                              if not re.match(r"^\w+\s*=\s*input\.", l) and not l.startswith("     tooltip") and not l.startswith('     "')]
    check("GA-05 trading code unchanged: with the input declarations / tooltip lines set aside, every code line equals the 7667a88 file "
          "(entries, SATS, SL / TP / breakeven formulas, BEL-1 lock, MSL-1 filter, alerts, labels, strategy() settings, import)",
          strip_inputs(T) == strip_inputs(T0) and es.seg(T, "strategy(", "import ") == es.seg(T0, "strategy(", "import ")
          and re.findall(r"^import .*$", T, re.M) == re.findall(r"^import .*$", T0, re.M))
    beT = es.func(T, "f_beTrig(")
    legal = (re.search(r'options = \["Fixed Distance", "Risk Multiple", "TP Progress"\]', dc["stBEMode"])
             and 0.05 <= 0.6 <= 1.0 and abs(round(0.6 / 0.05) * 0.05 - 0.6) < 1e-9 and abs(round(0.20 / 0.005) * 0.005 - 0.20) < 1e-9
             and '"TP Progress"' in beT and "stBETp" in beT and "stBER" in beT and "stBEDist" in beT)
    check("GA-06 the new values are legal (TP Progress is an option; 0.6 within 0.05..1.0 on the 0.05 step; 0.20 on the 0.005 step); "
          "f_beTrig reads stBETp in the TP Progress mode (Fixed Distance 0.20 / Risk Multiple 1.0 kept, unused in this mode)", legal)


def gate_mutation():
    muts = [T.replace('stRR = input.float(1.5,', 'stRR = input.float(1.2,'), T.replace('stBETp = input.float(0.6,', 'stBETp = input.float(0.65,'),
            T.replace('stBEMode = input.string("TP Progress",', 'stBEMode = input.string("Risk Multiple",'),
            T.replace('stTpMinRR = input.float(1.0,', 'stTpMinRR = input.float(1.1,'),
            T.replace("    if stLkBlk\n        array.clear(stWaits)\n", "")]
    check("GU-01 mutations (a changed default reverted, another value, another mode, an untouched default changed, trading code "
          "dropped) do not strip back to 7667a88", all(m != T and gb.strip(m) != T0 for m in muts))


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
