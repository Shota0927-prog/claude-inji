"""GBE-1 / GBJ-4 fixtures — Accum Score Mode (Sum / Max across timeframes) for GBPJPY.

  GE : static — ZoneEnginePracticalGBPJPY.pine == gbe_build.build(); strip_gbe gives ZoneEnginePractical/6
       (ZoneEnginePracticalSwingMax.pine) back byte for byte; only f_finalizeCluster's Accum aggregation, one ZoneCfg
       field, the library name and comments differ; Visual / Strategy import the derivative, carry the same input
       (default Sum) and config line, and revert byte for byte to 91036ec without the GBJ-4 edits; the FVG boost reads
       the Engine's (mode-aware) baseSum; requests / zone loops / drawing unchanged; Gold / USDJPY / shared /6 unchanged
  GM : models — a line-by-line Python port of the derivative's Accum aggregation vs the spec formula: the three spec
       examples, no source, a timeframe without Accum, ties, high / low once per timeframe kept, category / HTF kept;
       Sum bit-identical to /6 (same float additions in the same order) on random clusters with non-dyadic scores;
       Max: Score / Strength / FVG boost / Entry eligibility consistent
  GU : mutations — Sum / Max swapped, high / low collapsed to once, FVG side back to Sum, Max per member, Max over all
       sources; source mutations of the Library / scripts rejected

Evidence class: PINE_NOT_VERIFIED. TradingView compile, Library publish, Strategy Tester external.
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
PREV = "91036ec"
rd = lambda p: open(os.path.join(ROOT, p), encoding="utf-8").read() if os.path.exists(os.path.join(ROOT, p)) else ""
show = lambda p, rev=PREV: subprocess.run(["git", "-C", ROOT, "show", f"{rev}:{p}"], capture_output=True, text=True).stdout
ENG6 = rd(ge.SRC_PATH)
GBE = ge.strip_gbe2(ge.strip_gbe3(rd(ge.GBE_PATH))) or ""     # GBE-1 (Library v1) checks; GBE-2 (Edge Mode) is pinned in gbf_sim
GBV, GBS = rd(gb.GBJ_PATH), gs.strip_qty(rd(gs.GBS_PATH)) or ""   # GBS-4 position size reverted (pinned in gbq_sim)
GBV0, GBS0 = show(gb.GBJ_PATH), show(gs.GBS_PATH)
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


def code_only(src):
    return "\n".join(l for l in src.split("\n") if not l.lstrip().startswith("//"))


def revert4(text, skip_header=True):
    out = text
    for kind, a, b in list(reversed(gb.EDITS7)) + list(reversed(gb.EDITS6)) + list(reversed(gb.EDITS5)) + list(reversed(gb.EDITS4)):
        if kind == "header" and skip_header:
            continue
        out = out.replace(b, a) if out is not None and out.count(b) == 1 else None
    return out


PROTECTED = ["ZoneEnginePracticalSwingMax.pine", "ZoneEnginePractical.pine", "ZoneEnginePracticalRN.pine",
             "ZoneEnginePracticalAuthority.pine", "ZoneVisualPractical.pine", "ZoneStrategyXAU.pine",
             "ZoneVisualUSDJPY.pine", "ZoneStrategyUSDJPY.pine", "PracticalZoneStrategy_LONG.pine",
             "PracticalZoneStrategy_SHORT.pine", "SignalEnginePractical.pine"]


def gate_static():
    check("GE-01 ZoneEnginePracticalGBPJPY.pine == gbe_build.build() (rebuild identical); strip_gbe gives the shared "
          "ZoneEnginePractical/6 source back byte for byte; library name ZoneEnginePracticalGBPJPY",
          bool(GBE) and ge.strip_gbe2(ge.strip_gbe3(ge.build())) == GBE and ge.build() == ge.build() and ge.strip_gbe(GBE) == ENG6
          and 'library("ZoneEnginePracticalGBPJPY", overlay = true)' in GBE)
    fc = lambda s: tb.func(s, "f_finalizeCluster(")
    rest = lambda s: s.replace(fc(s), "")
    norm = rest(GBE).replace(ge.EDITS[2][1], ge.EDITS[2][0]).replace(ge.EDITS[1][1], ge.EDITS[1][0])
    adds6 = fc(ENG6).count("baseSum += m.baseScore")
    check("GE-02 Engine diff limited to f_finalizeCluster (Accum aggregation), the ZoneCfg field accScoreMax (default "
          "false = Sum), the library name and comments; each of the six per-timeframe additions became 'accA += score' "
          "plus 'baseSum += accScoreMax ? 0.0 : score' (Sum: the same addition at the same place), Max adds "
          "max(accA1, accA2, accA3) once after the member loop and before RN",
          code_only(norm) == code_only(rest(ENG6)) and adds6 - fc(GBE).count("baseSum += m.baseScore") == 6
          and fc(GBE).count("baseSum += c.accScoreMax ? 0.0 : m.baseScore") == 6
          and fc(GBE).count("    if c.accScoreMax\n        baseSum += math.max(accA1, math.max(accA2, accA3))\n") == 1
          and fc(GBE).index("math.max(accA1") > fc(GBE).index("hasACC  := hasACC or")
          and fc(GBE).index("math.max(accA1") < fc(GBE).index("if c.useRnSource")
          and "    bool   accScoreMax        = false" in GBE, str(adds6))
    inp = lambda s: re.search(r"^accScoreMode = input\.string\((.*)$", s.replace(gb.EDITS7[1][2], gb.EDITS7[1][1]), re.M)   # GBJ-4 default (Sum); GBJ-8 sets Max
    cfgl = 'zoneCfg.accScoreMax          := accScoreMode == "Max"\n'
    check("GE-03 Visual and Strategy import ZoneEnginePracticalGBPJPY (one import, no /6), same input Accum Score Mode "
          "(default Sum, options Sum / Max) and the same config line; without the GBJ-4 edits both files are the "
          + PREV + " files byte for byte (Sum = the previous code paths)",
          all(re.findall(r"^import .*$", s, re.M) == [ge.IMPORT_GBE.strip()] for s in (GBV, GBS))   # current version
          and inp(GBV) and inp(GBS) and inp(GBV).group(1) == inp(GBS).group(1)
          and inp(GBV).group(1).startswith('"Sum", "Accum Score Mode", options = ["Sum", "Max"]')
          and GBV.count(cfgl) == 1 and GBS.count(cfgl) == 1
          and revert4(GBV, skip_header=False) == GBV0 and bool(GBV0) and revert4(GBS) == GBS0 and bool(GBS0))
    dline = "        dScore := z.baseSum + f_fvcBase(best) + z.slopeBonus + z.maBonus + z.flipBonus + f_fvcConf(z.catCount + 1)\n"
    acc_uses = lambda s: [l for l in code_only(s).split("\n") if re.search(r"\bscoreAcc\d\b", l)]
    check("GE-04 FVG boost reads the Engine's baseSum (mode-aware) in both files (f_fvcZoneDisplay unchanged); the "
          "scripts never recompute Accum points themselves (scoreAcc1-3 only feed the Engine config)",
          GBV.count(dline) == 1 and GBS.count(dline) == 1
          and all(re.match(r"^(scoreAcc\d = input\.float|zoneCfg\.scoreAcc\d\s*:=)", l) for l in acc_uses(GBV) + acc_uses(GBS))
          and len(acc_uses(GBS)) == 6)
    req = lambda s: re.findall(r"request\.\w+\(.*$", code_only(s), re.M)
    cnt = lambda s, p: len(re.findall(p, code_only(s)))
    check("GE-05 lightweight: requests (10 / 11), zone loops, box / label / line / table, str.*, plot and for-loops "
          "unchanged in both scripts; the Engine gains no loop (aggregation inside the existing member loop); RE10045 "
          "lint clean", req(gb.strip_gbj6(GBV) or "") == req(GBV0) and req(revert4(GBS) or "") == req(GBS0)
          and all(cnt(n, p) == cnt(o, p) for n, o in ((GBV, GBV0), (GBS, GBS0), (GBE, ENG6))
                  for p in (r"zn\.zoneAt\(", r"\b(box|label|table|line)\.new\(", r"\bstr\.\w+\(", r"\bplot\w*\(",
                            r"\bfor\b", r"\bwhile\b", r"request\."))
          and fr.lint_eager_guards(code_only(GBV)) == [] and fr.lint_eager_guards(code_only(GBS)) == [])
    d = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", PREV, "--"] + PROTECTED, capture_output=True, text=True)
    t = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", "--diff-filter=MDR", PREV, "--", "tests/"],
                       capture_output=True, text=True).stdout
    check("GE-06 shared Engine /6 (and /2, /5, Authority), Gold (ZONE-P / ZONE-ST), USDJPY (Visual / Strategy) and old "
          "strategies unchanged vs " + PREV + "; only GBPJPY tests / generators changed",
          d.returncode == 0 and d.stdout.strip() == "" and all(re.match(r"^tests/gb[ejsx]_\w+\.py$", f) for f in t.split()),
          d.stdout + t)


# ---- mirrors ------------------------------------------------------------------------------------------------------------
TF = {"60": 1, "240": 2, "D": 3}
SCORES = {"60": 3.0, "240": 4.0, "D": 5.0}
conf = lambda c: 3.0 if c >= 4 else {2: 1.0, 3: 2.0}.get(c, 0.0)
THR_M, THR_S, THR_VS = 5.0, 9.0, 15.0     # GBJ-3 defaults


def strength(s, htf):
    t = 1 if s < THR_M else 2 if s < THR_S else 3 if s < THR_VS else 4
    return 3 if t == 4 and not htf else t


def finalize(members, acc_max, scores=SCORES, variant=None):
    """Port of the derivative's f_finalizeCluster scoring part (Swing SW-1 max, Accum per TF high / low once,
    other sources added). members: (cat, id, tf, score). Returns (baseSum, cat, htf)."""
    base = 0.0
    sw_max = None
    hits = set()
    acc = {1: 0.0, 2: 0.0, 3: 0.0}
    cats, htf = set(), False
    for cat, sid, tf, sc in members:
        if cat == "ACC":
            sc = scores.get(tf, sc)
            slot = TF.get(tf, 0)
            if slot:
                key = (slot, "hi" if sid == "ACC_HI" else "lo")
                if variant == "once_per_tf":
                    key = (slot,)
                if key not in hits:
                    hits.add(key)
                    acc[slot] += sc
                    if variant == "max_per_member" and acc_max:
                        base += 0.0
                    else:
                        base += 0.0 if acc_max else sc
            else:
                base += sc
            htf = True
            cats.add("ACC")
        elif cat == "SW":
            cats.add("HZ")
            htf |= tf == "60"
            if tf not in hits:
                hits.add(tf)
                add = sc if sw_max is None else max(0.0, sc - sw_max)
                sw_max = sc if sw_max is None else max(sw_max, sc)
                base += add
        else:
            base += sc
            cats.add(cat)
    if acc_max:
        if variant == "max_over_all":
            base = max([base] + list(acc.values()))
        elif variant == "max_per_member":
            base += max([s for c, i, t, s in members if c == "ACC"] or [0.0])
        else:
            base += max(acc[1], max(acc[2], acc[3]))
    return base, len(cats), htf


def spec_accum(members, acc_max, scores=SCORES):
    """Spec: a1H / a4H / aD with the current high / low counting; Sum = a1 + a4 + aD, Max = max(a1, a4, aD)."""
    a = {}
    for slot_tf in TF:
        seen = {(sid) for c, sid, tf, s in members if c == "ACC" and tf == slot_tf}
        a[slot_tf] = scores[slot_tf] * len(seen)
    vals = [a["60"], a["240"], a["D"]]
    return max(vals) if acc_max else sum(vals)


H = lambda tf: ("ACC", "ACC_HI", tf, 0.0)
L = lambda tf: ("ACC", "ACC_LO", tf, 0.0)


def zone(members, acc_max, slope=0.0, fvg=None, variant=None, fvg_sum=False, scores=SCORES):
    base, cat, htf = finalize(members, acc_max, scores, variant)
    sc = base + slope + conf(cat)
    st = strength(sc, htf)
    d_s, d_st, boosted = sc, st, False
    if fvg:
        fb = fvg_base = {"15": 1.0, "60": 2.0, "240": 3.0}[fvg]
        zb = finalize(members, False, scores)[0] if fvg_sum else base       # mutation: FVG side recomputes Sum
        d_s = zb + fb + slope + conf(cat + 1)
        d_st = strength(d_s, htf)
        boosted = d_st > st
        del fvg_base
    eligible = st >= 3 or (boosted and d_st >= 3)
    return dict(base=base, score=sc, str=st, dScore=d_s, dStr=d_st, boosted=boosted, eligible=eligible, cat=cat, htf=htf)


def fixtures(fin=finalize, zn=zone):
    out = []
    ex = [("3 / 4 / 5 (one side each)", [H("60"), H("240"), H("D")], 12.0, 5.0),
          ("1H high + low + 4H one side (6 / 4 / 0)", [H("60"), L("60"), H("240")], 10.0, 6.0),
          ("1H only (3 / 0 / 0)", [H("60")], 3.0, 3.0),
          ("no Accum source (Swing 1H only)", [("SW", "SWING_H", "60", 3.0)], 3.0, 3.0),
          ("timeframe without Accum (0 / 4 / 0)", [L("240")], 4.0, 4.0),
          ("1H high twice (two instances) + low: once each (6)", [H("60"), H("60"), L("60")], 6.0, 6.0)]
    for name, mem, s_exp, m_exp in ex:
        s, m = fin(mem, False)[0], fin(mem, True)[0]
        out.append((f"{name}: Sum {s_exp:g} / Max {m_exp:g}", (s, m) == (s_exp, m_exp)
                    and spec_accum(mem, False) + (3.0 if mem[0][0] == "SW" else 0) == s_exp
                    and spec_accum(mem, True) + (3.0 if mem[0][0] == "SW" else 0) == m_exp))
    tie = {"60": 3.0, "240": 6.0, "D": 5.0}
    mem = [H("60"), L("60"), H("240")]
    out.append(("tie (inputs 3 / 6 / 5): 1H high + low 6 = 4H one side 6 -> Max 6 once, Sum 12",
                (fin(mem, True, tie)[0], fin(mem, False, tie)[0]) == (6.0, 12.0)))
    both = [H("60"), H("240"), H("D"), ("DHL", "DAY_HIGH", "D", 2.0)]
    out.append(("category / HTF unchanged by the mode (ACC counted once, HTF from Accum)",
                fin(both, True)[1:] == fin(both, False)[1:] == (2, True)))
    z_s = zn([("SW", "SWING_H", "60", 3.0), H("240"), H("D"), ("DHL", "DAY_HIGH", "D", 2.0)], False)
    z_m = zn([("SW", "SWING_H", "60", 3.0), H("240"), H("D"), ("DHL", "DAY_HIGH", "D", 2.0)], True)
    out.append(("1H Swing + 4H + D Accum + Day High: Sum 3 + 9 + 2 + 2 = 16 Very Strong; Max 3 + 5 + 2 + 2 = 12 Strong",
                (z_s["score"], z_s["str"], z_m["score"], z_m["str"]) == (16.0, 4, 12.0, 3)))
    f_s = zn([H("240"), H("D")], False, fvg="60")
    f_m = zn([H("240"), H("D")], True, fvg="60")
    out.append(("FVG boost follows the mode: 4H + D Accum with a 1H FVG: Sum 9 Strong (boost 9 + 2 + 1 = 12); Max 5 "
                "Medium -> boost 5 + 2 + 1 = 8 Medium, not eligible",
                (f_s["score"], f_s["str"], f_s["dScore"], f_s["eligible"]) == (9.0, 3, 12.0, True)
                and (f_m["score"], f_m["str"], f_m["dScore"], f_m["dStr"], f_m["eligible"]) == (5.0, 2, 8.0, 2, False)))
    g_m = zn([H("D"), ("SW", "SWING_H", "60", 3.0)], True, fvg="240")
    out.append(("Max: D Accum + 1H Swing 9 Strong already; with a 4H FVG boost 13 (Strong, not boosted); eligible",
                (g_m["score"], g_m["str"], g_m["dScore"], g_m["boosted"], g_m["eligible"]) == (9.0, 3, 13.0, False, True)))
    h_m = zn([H("240"), ("SW", "SWING_H", "15", 2.0)], True, fvg="240")
    out.append(("Max: 4H Accum + 15M Swing 7 Medium -> 4H FVG 4 + 2 + 3 + 2 = 11 Strong boost -> eligible via the "
                "boost range", (h_m["score"], h_m["dScore"], h_m["boosted"], h_m["eligible"]) == (7.0, 11.0, True, True)))
    return out


def port6(members, scores):
    """the /6 addition order (Accum added at the member position, no accA)."""
    base, hits = 0.0, set()
    for cat, sid, tf, sc in members:
        if cat == "ACC":
            key = (TF[tf], sid)
            if key not in hits:
                hits.add(key)
                base += scores[tf]
        else:
            base += sc
    return base


def gate_model():
    for n, ok in fixtures():
        check("GM " + n, ok)
    rng = random.Random(7)
    bad, n = 0, 0
    for _ in range(4000):
        sc = {"60": rng.choice([3.0, 3.3, 2.7, 0.1]), "240": rng.choice([4.0, 4.7, 1.1]), "D": rng.choice([5.0, 5.3, 0.3])}
        mem = []
        for _ in range(rng.randint(1, 9)):
            k = rng.random()
            if k < 0.5:
                mem.append(("ACC", rng.choice(["ACC_HI", "ACC_LO"]), rng.choice(list(TF)), 0.0))
            elif k < 0.8:
                mem.append(("MA", "MA1", "1", rng.choice([2.0, 2.2, 0.7])))
            else:
                mem.append(("DHL", "DAY_HIGH", "D", rng.choice([2.0, 1.3])))
        n += 1
        bad += finalize(mem, False, sc)[0] != port6(mem, sc)
    check(f"GM Sum is bit-identical to /6 on {n} random clusters with non-dyadic scores (same additions, same order; "
          "exact float equality)", bad == 0, str(bad))


def gate_mutation():
    muts = {
        "Sum / Max swapped": dict(fin=lambda m, mx, s=SCORES: finalize(m, not mx, s),
                                  zn=lambda m, mx, **k: zone(m, not mx, **k)),
        "high / low collapsed to once per timeframe": dict(fin=lambda m, mx, s=SCORES: finalize(m, mx, s, "once_per_tf"),
                                                           zn=lambda m, mx, **k: zone(m, mx, variant="once_per_tf", **k)),
        "FVG side recomputes Sum": dict(fin=finalize, zn=lambda m, mx, **k: zone(m, mx, fvg_sum=True, **k)),
        "Max per member (not per timeframe)": dict(fin=lambda m, mx, s=SCORES: finalize(m, mx, s, "max_per_member"),
                                                   zn=lambda m, mx, **k: zone(m, mx, variant="max_per_member", **k)),
        "Max over all sources": dict(fin=lambda m, mx, s=SCORES: finalize(m, mx, s, "max_over_all"),
                                     zn=lambda m, mx, **k: zone(m, mx, variant="max_over_all", **k)),
    }
    caught = {k: not all(ok for _, ok in fixtures(**v)) for k, v in muts.items()}
    check("GU-01 mirror mutations caught (" + str(len(caught)) + "): " + ", ".join(caught), all(caught.values()), str(caught))
    src = {
        "Library: ternary swapped": ("GBE", "baseSum += c.accScoreMax ? 0.0 : m.baseScore", "baseSum += c.accScoreMax ? m.baseScore : 0.0"),
        "Library: high / low once": ("GBE", "else if not isAccHi and not accLo1", "else if not isAccHi and not accHi1"),
        "Library: Max add removed": ("GBE", "        baseSum += math.max(accA1, math.max(accA2, accA3))\n", ""),
        "Scripts: mode mapped inverted": ("BOTH", 'accScoreMode == "Max"', 'accScoreMode == "Sum"'),
        "Scripts: FVG boost from a recomputed Sum": ("BOTH", "dScore := z.baseSum + f_fvcBase(best)",
                                                     "dScore := z.baseSum + scoreAcc1 + f_fvcBase(best)"),
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
