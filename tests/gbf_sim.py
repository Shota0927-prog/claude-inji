"""GBE-2 / GBJ-5 fixtures — Accum Edge Mode (Separate / Once per TF) for GBPJPY, combined with Accum Score Mode.

  GF : static — ZoneEnginePracticalGBPJPY.pine == gbe_build.build(); strip_gbe2 gives the Library version 1 source
       (60cc26f) byte for byte and strip_gbe the shared /6; the GBE-2 diff is one ZoneCfg field and the six per-edge
       additions (value = accEdgeOnce and other edge already counted ? 0 : score); Visual / Strategy import version 2,
       carry the same input (default Separate) and config line, and revert byte for byte to 60cc26f without GBJ-5;
       FVG boost reads the Engine baseSum; requests / loops / drawing unchanged; shared /6, Gold, USDJPY unchanged
  GM : models — a line-by-line port of the version 2 aggregation (per-edge flags, per-timeframe contribution, then
       Sum / Max) vs the spec: the listed examples in all four combinations, no source, timeframe without Accum,
       edges of different boxes, ties, edge order, category / HTF kept; Separate bit-identical to version 1 (random
       clusters, non-dyadic scores, Sum and Max); Score / Strength / FVG boost / eligibility in the four combinations
  GU : mutations — double counting kept under Once, one contribution for all timeframes, Sum / Max applied to edges
       before the per-timeframe contribution, Once ignored, Sum / Max swapped; source mutations rejected

Evidence class: PINE_NOT_VERIFIED. TradingView compile, Library version 2 publish, Strategy Tester external.
"""
import os
import random
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gbe_build as ge          # noqa: E402
import gbj_build as gb          # noqa: E402
import gbs_build as gs          # noqa: E402
import st1_build as tb          # noqa: E402
import fvg_re10045_sim as fr    # noqa: E402

ROOT = ge.ROOT
PREV = "60cc26f"
rd = lambda p: __import__("cad_build").pre_cad(p, open(os.path.join(ROOT, p), encoding="utf-8").read() if os.path.exists(os.path.join(ROOT, p)) else "")   # CAD-1 reverted (pinned in cad_sim)
show = lambda p, rev=PREV: subprocess.run(["git", "-C", ROOT, "show", f"{rev}:{p}"], capture_output=True, text=True).stdout
ENG6, GBE1 = rd(ge.SRC_PATH), show(ge.GBE_PATH)
GBE = ge.strip_gbe3(rd(ge.GBE_PATH)) or ""     # GBE-2 (Library v2) checks; GBE-3 (Day/Swing Overlap) is pinned in gbd_sim
GBV, GBS = rd(gb.GBJ_PATH), gs.strip_qty(rd(gs.GBS_PATH)) or ""   # GBS-4 position size reverted (pinned in gbq_sim)
GBV0, GBS0 = show(gb.GBJ_PATH), show(gs.GBS_PATH)
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


def code_only(src):
    return "\n".join(l for l in src.split("\n") if not l.lstrip().startswith("//"))


def revert6(text):
    """GBJ-6 (Day/Swing Overlap, pinned in gbd_sim) reverted in the Strategy (its header edit is Visual-only)."""
    out = text
    for kind, a, b in list(reversed(gb.EDITS7)) + list(reversed(gb.EDITS6)):
        if kind != "header":
            out = out.replace(b, a) if out is not None and out.count(b) == 1 else None
    return out


def revert5(text, skip_header=True):
    out = text
    for kind, a, b in list(reversed(gb.EDITS7)) + list(reversed(gb.EDITS6)) + list(reversed(gb.EDITS5)):
        if kind == "header" and skip_header:
            continue
        out = out.replace(b, a) if out is not None and out.count(b) == 1 else None
    return out


PROTECTED = ["ZoneEnginePracticalSwingMax.pine", "ZoneEnginePractical.pine", "ZoneEnginePracticalRN.pine",
             "ZoneEnginePracticalAuthority.pine", "ZoneVisualPractical.pine", "ZoneStrategyXAU.pine",
             "ZoneVisualUSDJPY.pine", "ZoneStrategyUSDJPY.pine", "PracticalZoneStrategy_LONG.pine",
             "PracticalZoneStrategy_SHORT.pine", "SignalEnginePractical.pine"]


def gate_static():
    check("GF-01 Library = gbe_build.build() (rebuild identical); reverting GBE-2 gives the Library version 1 source ("
          + PREV + ") byte for byte, reverting GBE-2 + GBE-1 the shared ZoneEnginePractical/6",
          bool(GBE) and ge.strip_gbe3(ge.build()) == GBE and ge.strip_gbe2(GBE) == GBE1 and bool(GBE1) and ge.strip_gbe(GBE) == ENG6)
    fc = lambda s: tb.func(s, "f_finalizeCluster(")
    edge = [f"float e{h}{n} = c.accEdgeOnce and acc{o}{n} ? 0.0 : m.baseScore"
            for n in (1, 2, 3) for h, o in (("H", "Lo"), ("L", "Hi"))]
    adds = [f"acc{x}{n}  := true\n                    accA{n}   += e{y}{n}\n                    baseSum += c.accScoreMax ? 0.0 : e{y}{n}\n"
            for n in (1, 2, 3) for x, y in (("Hi", "H"), ("Lo", "L"))]
    rest = lambda s: code_only(s.replace(fc(s), ""))
    check("GF-02 GBE-2 diff: ZoneCfg.accEdgeOnce (default false = Separate) and, in each of the six per-edge branches, "
          "value = accEdgeOnce and the other edge of the timeframe already counted ? 0 : score, added to the timeframe "
          "contribution and (Sum) to baseSum; the per-edge flags, the Max step after the loop and everything outside "
          "f_finalizeCluster unchanged",
          all(fc(GBE).count(e) == 1 for e in edge) and all(fc(GBE).count(a) == 1 for a in adds)
          and fc(GBE).count("    if c.accScoreMax\n        baseSum += math.max(accA1, math.max(accA2, accA3))\n") == 1
          and rest(GBE).replace("    bool   accEdgeOnce        = false", "", 1).count("accEdgeOnce") == 0
          and "    bool   accEdgeOnce        = false" in GBE
          and re.sub(r"\n    bool   accEdgeOnce .*\n", "\n", rest(GBE)) == rest(GBE1))
    inp = lambda s: re.search(r"^accEdgeMode = input\.string\((.*)$", s, re.M)
    cfgl = 'zoneCfg.accEdgeOnce          := accEdgeMode == "Once per TF"\n'
    check("GF-03 Visual and Strategy import Library version 2 (" + ge.IMPORT_GBE.strip() + "), same input Accum Edge "
          "Mode (default Separate, options Separate / Once per TF) after Accum Score Mode (default Sum kept), same config "
          "line; without the GBJ-5 edits both files are the " + PREV + " files byte for byte",
          all(re.findall(r"^import .*$", s, re.M) == [ge.IMPORT_GBE.strip()] for s in (GBV, GBS))
          and inp(GBV) and inp(GBS) and inp(GBV).group(1) == inp(GBS).group(1)
          and inp(GBV).group(1).startswith('"Separate", "Accum Edge Mode", options = ["Separate", "Once per TF"]')
          and all(re.search(r'^accScoreMode = input\.string\("(Sum|Max)",', s, re.M) for s in (GBV, GBS))   # Max since GBJ-8
          and GBV.count(cfgl) == 1 and GBS.count(cfgl) == 1
          and revert5(GBV, skip_header=False) == GBV0 and bool(GBV0) and revert5(GBS) == GBS0 and bool(GBS0))
    dline = "        dScore := z.baseSum + f_fvcBase(best) + z.slopeBonus + z.maBonus + z.flipBonus + f_fvcConf(z.catCount + 1)\n"
    req = lambda s: re.findall(r"request\.\w+\(.*$", code_only(s), re.M)
    cnt = lambda s, p: len(re.findall(p, code_only(s)))
    check("GF-04 FVG boost reads the Engine baseSum in both files; requests (10 / 11), zone loops, drawing, str.*, plot "
          "and loops unchanged in the scripts and the Library (aggregation inside the existing member loop); lint clean",
          GBV.count(dline) == 1 and GBS.count(dline) == 1 and req(gb.strip_gbj6(GBV) or "") == req(GBV0)
          and req(revert6(GBS) or "") == req(GBS0)
          and all(cnt(n, p) == cnt(o, p) for n, o in ((GBV, GBV0), (GBS, GBS0), (GBE, GBE1))
                  for p in (r"zn\.zoneAt\(", r"\b(box|label|table|line)\.new\(", r"\bstr\.\w+\(", r"\bplot\w*\(",
                            r"\bfor\b", r"\bwhile\b", r"request\."))
          and fr.lint_eager_guards(code_only(GBV)) == [] and fr.lint_eager_guards(code_only(GBS)) == [])
    d = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", PREV, "--"] + PROTECTED, capture_output=True, text=True)
    t = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", "--diff-filter=MDR", PREV, "--", "tests/"],
                       capture_output=True, text=True).stdout
    check("GF-05 shared Engine /6 (and /2, /5, Authority), Gold, USDJPY and old strategies unchanged vs " + PREV
          + "; only GBPJPY tests / generators changed",
          d.returncode == 0 and __import__("uj_build").drop_uj(d.stdout.split(), PREV) == [] and all(re.match(r"^tests/gb[efjsx]_\w+\.py$", f) for f in __import__("uj_build").drop_uj_tests(t.split())),
          d.stdout + t)


# ---- mirrors ------------------------------------------------------------------------------------------------------------
TFS = ("60", "240", "D")
SC = {"60": 3.0, "240": 4.0, "D": 5.0}
conf = lambda c: 3.0 if c >= 4 else {2: 1.0, 3: 2.0}.get(c, 0.0)


def strength(s, htf, thr=(5.0, 9.0, 15.0)):
    t = 1 if s < thr[0] else 2 if s < thr[1] else 3 if s < thr[2] else 4
    return 3 if t == 4 and not htf else t


def port(members, acc_max, once, scores=SC, variant=None):
    """line-by-line port of the version 2 f_finalizeCluster scoring (Accum part + other sources added)."""
    base = 0.0
    hi = {tf: False for tf in TFS}
    lo = {tf: False for tf in TFS}
    acc = {tf: 0.0 for tf in TFS}
    edges = []
    cats, htf = set(), False
    for m in members:
        cat, sid, tf, sc = m[0], m[1], m[2], m[3]
        if cat == "ACC":
            cats.add("ACC")
            htf = True
            s = scores[tf]
            if sid == "ACC_HI" and not hi[tf]:
                e = 0.0 if (once and variant != "once_ignored" and lo[tf]) else s
                if variant == "one_for_all_tfs" and once and (any(hi.values()) or any(lo.values())):
                    e = 0.0
                hi[tf] = True
                acc[tf] += e
                edges.append(e)
                base += 0.0 if acc_max else e
            elif sid == "ACC_LO" and not lo[tf]:
                e = 0.0 if (once and variant != "once_ignored" and hi[tf]) else s
                if variant == "one_for_all_tfs" and once and (any(hi.values()) or any(lo.values())):
                    e = 0.0
                lo[tf] = True
                acc[tf] += e
                edges.append(e)
                base += 0.0 if acc_max else e
        elif cat == "SW":
            cats.add("HZ")
            htf |= tf == "60"
            base += sc
        else:
            base += sc
            cats.add(cat)
    if variant == "double_count" and once:          # mutation: Once selected but both edges still counted
        return port(members, acc_max, False, scores)[0], len(cats), htf
    if acc_max:
        if variant == "max_over_edges":
            base += max(edges or [0.0])
        else:
            base += max(acc["60"], max(acc["240"], acc["D"]))
    return base, len(cats), htf


def port_v1(members, acc_max, scores=SC):
    """version 1 (GBE-1) addition order: each new edge adds its score; Max after the loop."""
    base = 0.0
    seen = set()
    acc = {tf: 0.0 for tf in TFS}
    for m in members:
        cat, sid, tf, sc = m[0], m[1], m[2], m[3]
        if cat == "ACC":
            if (sid, tf) not in seen:
                seen.add((sid, tf))
                acc[tf] += scores[tf]
                base += 0.0 if acc_max else scores[tf]
        else:
            base += sc
    if acc_max:
        base += max(acc["60"], max(acc["240"], acc["D"]))
    return base


def spec(members, acc_max, once, scores=SC):
    a = []
    for tf in TFS:
        edges = {m[1] for m in members if m[0] == "ACC" and m[2] == tf}
        a.append(scores[tf] * (min(len(edges), 1) if once else len(edges)))
    return max(a) if acc_max else sum(a)


H = lambda tf, box=0: ("ACC", "ACC_HI", tf, 0.0, box)
L = lambda tf, box=0: ("ACC", "ACC_LO", tf, 0.0, box)
COMBOS = [(False, False), (True, False), (False, True), (True, True)]     # (Max, Once)


def zone(members, acc_max, once, fvg=None, fin=port, **kw):
    base, cat, htf = fin(members, acc_max, once, **kw)
    sc = base + conf(cat)
    st = strength(sc, htf)
    d_s, d_st = sc, st
    if fvg:
        d_s = base + {"15": 1.0, "60": 2.0, "240": 3.0}[fvg] + conf(cat + 1)
        d_st = strength(d_s, htf)
    boosted = d_st > st
    return (sc, st, d_s, d_st, boosted, st >= 3 or (boosted and d_st >= 3))


def fixtures(fin=port):
    out = []
    ex = [  # name, members, {(Max, Once): expected Accum points}
        ("1H high + low", [H("60"), L("60")], {(False, False): 6, (True, False): 6, (False, True): 3, (True, True): 3}),
        ("1H high twice (duplicates removed as now)", [H("60", 1), H("60", 2)], {c: 3 for c in COMBOS}),
        ("1H high + low + 4H one side", [H("60"), L("60"), H("240")],
         {(False, False): 10, (True, False): 6, (False, True): 7, (True, True): 4}),
        ("1H / 4H / D one side each", [H("60"), H("240"), L("D")],
         {(False, False): 12, (True, False): 5, (False, True): 12, (True, True): 5}),
        ("no Accum", [("MA", "MA1", "1", 2.0)], {c: 0 for c in COMBOS}),
        ("timeframe without Accum (only 4H low)", [L("240")], {c: 4 for c in COMBOS}),
        ("1H high of box A + 1H low of box B (different boxes)", [H("60", 1), L("60", 2)],
         {(False, False): 6, (True, False): 6, (False, True): 3, (True, True): 3}),
        ("edge order: low first, then high", [L("60"), H("60"), H("240")],
         {(False, False): 10, (True, False): 6, (False, True): 7, (True, True): 4}),
    ]
    for name, mem, exp in ex:
        other = sum(m[3] for m in mem if m[0] != "ACC")
        got = {c: fin(mem, *c)[0] - other for c in COMBOS}
        sp = {c: spec(mem, *c) for c in COMBOS}
        out.append((f"{name}: Sum/Sep {exp[(False, False)]:g}, Max/Sep {exp[(True, False)]:g}, Sum/Once "
                    f"{exp[(False, True)]:g}, Max/Once {exp[(True, True)]:g}", got == exp == sp))
    tie_sc = {"60": 4.0, "240": 4.0, "D": 5.0}
    mem = [H("60"), L("60"), L("240")]
    out.append(("tie (inputs 4 / 4 / 5): Once -> 4 / 4 / 0 -> Max 4 (once), Sum 8; Separate -> 8 / 4 -> Max 8, Sum 12",
                [fin(mem, mx, on, scores=tie_sc)[0] for mx, on in COMBOS] == [12.0, 8.0, 8.0, 4.0]))
    both = [H("60"), L("60"), H("240"), ("DHL", "DAY_HIGH", "D", 2.0)]
    out.append(("category / HTF unchanged in all four combinations",
                len({fin(both, *c)[1:] for c in COMBOS}) == 1 and fin(both, False, False)[1:] == (2, True)))
    mem = [H("60"), L("60"), L("240"), ("SW", "SWING_H", "60", 3.0)]
    r = {c: zone(mem, *c, fvg="60", fin=fin) for c in COMBOS}
    out.append(("1H Swing + 1H high/low + 4H low (+ 1H FVG): Sum/Sep 14 Strong, Max/Sep 10 Strong, Sum/Once 11 Strong, "
                "Max/Once 8 Medium -> FVG 3 + 4 + 2 + 2 = 11 Strong boost -> eligible via the boost range",
                [r[c][:2] for c in COMBOS] == [(14.0, 3), (10.0, 3), (11.0, 3), (8.0, 2)]
                and r[(True, True)][2:] == (11.0, 3, True, True)))
    return out


def gate_model():
    for n, ok in fixtures():
        check("GM " + n, ok)
    rng = random.Random(11)
    bad, n = 0, 0
    for _ in range(4000):
        sc = {"60": rng.choice([3.0, 3.3, 0.1]), "240": rng.choice([4.0, 4.7, 1.1]), "D": rng.choice([5.0, 5.3, 0.3])}
        mem = []
        for _ in range(rng.randint(1, 9)):
            k = rng.random()
            if k < 0.6:
                mem.append(("ACC", rng.choice(["ACC_HI", "ACC_LO"]), rng.choice(TFS), 0.0))
            elif k < 0.85:
                mem.append(("MA", "MA1", "1", rng.choice([2.0, 2.2, 0.7])))
            else:
                mem.append(("DHL", "DAY_HIGH", "D", rng.choice([2.0, 1.3])))
        for mx in (False, True):
            n += 1
            bad += port(mem, mx, False, sc)[0] != port_v1(mem, mx, sc)
    check(f"GM Separate is bit-identical to Library version 1 on {n} random cluster / mode cases (Sum and Max, non-dyadic "
          "scores; same additions, same order)", bad == 0, str(bad))


def gate_mutation():
    muts = {
        "double counting kept under Once": lambda m, mx, on, **k: port(m, mx, on, variant="double_count", **k),
        "one contribution for all timeframes": lambda m, mx, on, **k: port(m, mx, on, variant="one_for_all_tfs", **k),
        "Sum / Max applied to edges before the per-timeframe contribution":
            lambda m, mx, on, **k: port(m, mx, on, variant="max_over_edges", **k),
        "Once ignored": lambda m, mx, on, **k: port(m, mx, on, variant="once_ignored", **k),
        "Sum / Max swapped": lambda m, mx, on, **k: port(m, not mx, on, **k),
    }
    caught = {k: not all(ok for _, ok in fixtures(f)) for k, f in muts.items()}
    check("GU-01 mirror mutations caught (" + str(len(caught)) + "): " + ", ".join(caught), all(caught.values()), str(caught))
    src = {
        "Library: second edge still adds (Once ignored)": ("GBE", "float eL1 = c.accEdgeOnce and accHi1 ? 0.0 : m.baseScore",
                                                          "float eL1 = m.baseScore"),
        "Library: Once across timeframes": ("GBE", "float eH2 = c.accEdgeOnce and accLo2 ?", "float eH2 = c.accEdgeOnce and accLo1 ?"),
        "Library: Max over edges": ("GBE", "baseSum += math.max(accA1, math.max(accA2, accA3))", "baseSum += math.max(eH1, eL1)"),
        "Scripts: Edge Mode mapped inverted": ("BOTH", 'accEdgeMode == "Once per TF"', 'accEdgeMode == "Separate"'),
        "Scripts: still importing version 1": ("BOTH", ge.IMPORT_GBE, ge.IMPORT_GBE1),
    }
    global GBE, GBV, GBS
    keep = (GBE, GBV, GBS, list(RESULTS))
    rej = {}
    for name, (where, a, b) in src.items():
        GBE = keep[0].replace(a, b, 1) if where == "GBE" else keep[0]
        GBV = keep[1].replace(a, b, 1) if where == "BOTH" else keep[1]
        GBS = keep[2].replace(a, b, 1) if where == "BOTH" else keep[2]
        del RESULTS[:]
        try:
            gate_static()
            rej[name] = not all(ok for _, ok, _ in RESULTS)
        except Exception:
            rej[name] = True
    GBE, GBV, GBS = keep[0], keep[1], keep[2]
    RESULTS[:] = keep[3]
    check("GU-02 source mutations rejected by the static gates (" + str(len(rej)) + "): " + ", ".join(rej),
          all(rej.values()), str(rej))


def main():
    for g in (gate_static, gate_model, gate_mutation):
        try:
            g()
        except Exception:
            import traceback
            check(f"{g.__name__} completed without error", False, traceback.format_exc()[-900:])
    fails = 0
    for n, ok, d in RESULTS:
        fails += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {n[:150].ljust(150)}  {'' if ok else d}")
    print(f"\n{len(RESULTS) - fails}/{len(RESULTS)} passed  [PINE_NOT_VERIFIED: exact build / static / mirror model]")
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
