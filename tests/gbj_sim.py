"""GBJ-1 fixtures — ZoneVisualGBPJPY.pine (OANDA:GBPJPY 5M Zone comparison, no entries / alerts).

  GS : static — deterministic, idempotent build from ZONE-JPY; strip_gbj(file) == ZONE-JPY byte for byte; every EDIT
       only touches comments, the indicator title, input defaults / labels / tooltips / groups, or the label width unit;
       price-difference inputs in yen ([暫定], defaults 0.03 / 0.08 / 0.05 + inherited); input values differ from
       ZONE-JPY only in Zone Half Width; Engine config, requests (10), import /6, update order and the non-repaint /
       FVG blocks identical; no ticker guard other than the XAUUSD Round Number gate; no new drawing / string work;
       protected files unchanged vs the base HEAD 9596357
  GM : model — the Python mirror of ZoneEnginePractical (practical_zone_sim) fed the same yen OHLC / sources with the
       inputs read from each file: identical Zones / Score / Strength / Touch / Break-Flip when the inputs are equal,
       and the only difference at defaults is the Half Width; FVG min width gate; RN gate for GBPJPY; label strings

Evidence class: PINE_NOT_VERIFIED (TradingView compile / display external).
"""
import copy
import os
import random
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gbj_build as gb          # noqa: E402
import jpy_build as jb          # noqa: E402
import nr_s1_build as nb        # noqa: E402
import nr_a1_build as na        # noqa: E402
import fvg_batch_c_build as cb  # noqa: E402
import zp_overlap_build as zp   # noqa: E402
import fvg_re10045_sim as fr    # noqa: E402
import practical_zone_sim as pz  # noqa: E402

ROOT = gb.ROOT
BASE = "9596357"
JPY = open(os.path.join(ROOT, gb.SRC_PATH), encoding="utf-8").read()
GBJ = open(os.path.join(ROOT, gb.GBJ_PATH), encoding="utf-8").read() if os.path.exists(os.path.join(ROOT, gb.GBJ_PATH)) else ""
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


def code_only(src):
    return "\n".join(l for l in src.split("\n") if not l.lstrip().startswith("//"))


def block(src, b, e):
    if src.count(b) != 1 or src.count(e) != 1:
        return None
    i = src.index(b)
    return src[i:src.index("\n", src.index(e)) + 1]


def inp(src, name):
    m = re.search(r"^" + name + r"\s*=\s*input\.\w+\((.*)$", src, re.M)
    return m.group(1) if m else ""


def input_values(src):
    """name -> default literal of every input.* declaration (first positional argument)."""
    return {n: v.strip() for n, v in re.findall(r"^(\w+)\s*=\s*input\.\w+\(([^,]+),", src, re.M)}


PRICE_INPUTS = {   # name: (default, minval, step)  — every price difference in the file, all yen, all [暫定]
    "zoneHalfWidth": ("0.03", "0.005", "0.005"),
    "clusterDist": ("0.08", "0.0", "0.005"),
    "fvgMinWidth": ("0.05", "0.0", "0.005"),
    "slopeThrMod": ("0.02", "0.0", "0.005"),
    "slopeThrStrong": ("0.05", "0.0", "0.005"),
    "maClusterDist": ("0.30", "0.0", "0.01"),
    "touchRearmDist": ("0.15", "0.0", "0.01"),
    "breakBuffer": ("0.08", "0.0", "0.005"),
    "flipConfirmDist": ("0.15", "0.0", "0.01"),
}
PROTECTED = ["ZoneVisualUSDJPY.pine", "ZoneStrategyUSDJPY.pine", "ZoneVisualPractical.pine", "ZoneStrategyXAU.pine",
             "ZoneEnginePractical.pine", "ZoneEnginePracticalRN.pine", "ZoneEnginePracticalSwingMax.pine",
             "ZoneEnginePracticalAuthority.pine", "PracticalZoneStrategy_LONG.pine", "PracticalZoneStrategy_SHORT.pine",
             "SignalEnginePractical.pine"]


def allowed_code_line(line):
    """A code (non-comment) line an EDIT may change: input declaration / tooltip continuation, title, label width."""
    s = line.strip()
    return (re.match(r"^\w+\s*=\s*input\.\w+\(", s) is not None
            or re.match(r'^(tooltip = )?".*"\)?( \+)?$', s) is not None
            or re.match(r'^(title|shorttitle)\s*=\s*"[^"]*",$', s) is not None
            or s == 'f_num(z.top, "#.000") + " - " + f_num(z.bottom, "#.000") + " | W " + f_num(z.top - z.bottom, "0.000") + "円"'
            or s == 'f_num(z.top, "#.000") + " - " + f_num(z.bottom, "#.000") + " | W " + f_num(z.top - z.bottom, "0.000")'
            or s == "f_jpyGeom(zn.Zone z) =>")


def gate_static():
    check("GS-01 ZoneVisualGBPJPY.pine == gbj_transform(ZoneVisualUSDJPY.pine); rebuilding gives the same bytes; strip_gbj "
          "gives ZONE-JPY back byte for byte (the file differs from ZONE-JPY only by the listed edits)",
          bool(GBJ) and gb.build() == GBJ and gb.build() == gb.build() and gb.strip_gbj(GBJ) == JPY
          and gb.gbj_transform(gb.strip_gbj(GBJ)) == GBJ)
    bad = []
    for kind, a, b in gb.EDITS:
        if kind not in ("header", "title", "input", "display"):
            bad.append((kind, b[:40]))
        changed = [l for l in code_only(b).split("\n") if l.strip()] + [l for l in code_only(a).split("\n") if l.strip()]
        if kind == "header" and changed:
            bad.append(("header has code", changed))
        bad += [(kind, l) for l in changed if not allowed_code_line(l)]
    check("GS-02 every EDIT is header comment / title / input default-label-tooltip-group / label width unit; no "
          "calculation line is touched", bad == [], str(bad))
    vj, vg = input_values(JPY), input_values(GBJ)
    diff = {n: (vj.get(n), vg.get(n)) for n in set(vj) | set(vg) if vj.get(n) != vg.get(n)}
    check("GS-03 the input set is ZONE-JPY's (no input added / removed); only Zone Half Width differs in value "
          "(0.05 -> 0.03); every other input value inherited", set(vj) == set(vg) and diff == {"zoneHalfWidth": ("0.05", "0.03")},
          str(diff))
    bad = []
    for n, (dv, mv, st) in PRICE_INPUTS.items():
        a = inp(GBJ, n)
        if not (a.startswith(dv + ",") and f"minval = {mv}," in a and f"step = {st}," in a and "円" in a and "[暫定]" in a):
            bad.append((n, a))
    ins = re.findall(r"^(\w+)\s*=\s*input\.float\((.*)$", code_only(GBJ), re.M)
    yen = sorted(n for n, a in ins if "円" in a)
    check("GS-04 price-difference inputs: exactly the 9 listed, all in 円, all [暫定]: Half Width 0.03, Cluster 0.08, FVG "
          "Min Width 0.05, Slope 0.02 / 0.05, MA Cluster 0.30, Touch Re-arm 0.15, Break Buffer 0.08, Flip Confirm 0.15",
          bad == [] and yen == sorted(PRICE_INPUTS) and not [n for n, a in ins if "$" in a], str((bad, yen)))
    cands = ("0.03 / 0.05 / 0.08 円", "0.08 / 0.12 / 0.16 円", "0.05 / 0.08 / 0.10 円")
    check("GS-05 comparison candidates in the tooltips (HW 0.03 / 0.05 / 0.08, Cluster 0.08 / 0.12 / 0.16, FVG 0.05 / "
          "0.08 / 0.10 円) marked as 検証用・適正値ではない; no USDJPY name left in code; shorttitle ZONE-GBPJPY",
          all(GBJ.count(c) >= 1 for c in cands) and GBJ.count("検証用・適正値ではない") == 3
          and "USDJPY" not in code_only(GBJ) and 'shorttitle       = "ZONE-GBPJPY"' in GBJ)
    conds = re.findall(r"syminfo\.\w+\s*[!=]=\s*\"[^\"]*\"", code_only(GBJ))
    check("GS-06 no symbol guard can block GBPJPY: the only ticker comparison is the XAUUSD Round Number gate (kept, "
          "default OFF); no runtime.error",
          conds == ['syminfo.ticker == "XAUUSD"'] and inp(GBJ, "enableRn").startswith("false,")
          and 'zoneCfg.useRnSource          := enableRn and syminfo.ticker == "XAUUSD"' in GBJ
          and "runtime.error" not in code_only(GBJ), str(conds))
    cfg = lambda s: re.findall(r"^zoneCfg\.\w+\s*:=.*$", s, re.M)
    req = lambda s: re.findall(r"request\.\w+\(.*$", code_only(s), re.M)
    calls = lambda s: re.findall(r"\b(zn\.\w+|f_\w+)\(", code_only(s))
    check("GS-07 Engine config assignments, request call sites (10, none added), import ZoneEnginePractical/6, call sequence "
          "(zn.* / f_*: update order) identical to ZONE-JPY",
          cfg(GBJ) == cfg(JPY) and req(GBJ) == req(JPY) and len(req(GBJ)) == 10
          and re.findall(r"^import .*$", GBJ, re.M) == ["import sekine3310/ZoneEnginePractical/6 as zn"]
          and calls(GBJ) == calls(JPY))
    same = []
    for name, b, e in (("NR-S1", nb.NRS_BEGIN, nb.NRS_END), ("NR-A1", na.NRA_BEGIN, na.NRA_END),
                       ("FVG Batch C", cb.C_BEGIN, cb.C_END), ("ZPO", zp.ZPO_BEGIN, zp.ZPO_END)):
        bg, bj = block(GBJ, b, e), block(JPY, b, e)
        same.append((name, bg is not None and bg == bj))
    ba_g, ba_j = block(GBJ, cb.A_BEGIN, cb.A_END), block(JPY, cb.A_BEGIN, cb.A_END)
    _, f_old, f_new = next(x for x in gb.EDITS if x[1].startswith("fvgMinWidth"))
    same.append(("FVG Batch A (only the FVG min width input text)", ba_g is not None and ba_g.count(f_new) == 1
                 and ba_g.replace(f_new, f_old) == ba_j))
    check("GS-08 non-repaint / FVG / scoring blocks identical to ZONE-JPY: NR-S1, NR-A1, FVG Batch A (input text aside), "
          "Batch C, overlap display", all(o for _, o in same), str(same))
    cnt = lambda s, p: len(re.findall(p, code_only(s)))
    check("GS-09 lightweight: RE10045 lint clean; box / label / table.new, str.* and plot / alert call counts identical to "
          "ZONE-JPY (no new drawing, no new per-bar string work); no alertcondition / alert / strategy call",
          fr.lint_eager_guards(code_only(GBJ)) == []
          and all(cnt(GBJ, p) == cnt(JPY, p) for p in (r"\b(box|label|table|line)\.new\(", r"\bstr\.\w+\(",
                                                       r"\bplot\w*\(", r"\balert\w*\("))
          and cnt(GBJ, r"\balert\w*\(") == 0 and cnt(GBJ, r"\bstrategy\.") == 0 and "strategy(" not in code_only(GBJ))
    d = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", BASE, "--"] + PROTECTED, capture_output=True, text=True)
    check("GS-10 ZONE-JPY, ZONE-STJ, ZONE-P, ZONE-ST, Engines (/2, /5, /6, Authority), old strategies, SignalEngine "
          "unchanged vs base HEAD " + BASE, d.returncode == 0 and d.stdout.strip() == "", d.stdout + d.stderr)
    j = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", BASE, "--", "tests/"], capture_output=True, text=True).stdout
    check("GS-11 existing generator / test scripts unchanged vs " + BASE + " (only gbj_build.py / gbj_sim.py are new) and "
          "jpy_build still regenerates ZONE-JPY", j.strip() == "" and jb.build() == JPY, j)


# ---- model ------------------------------------------------------------------------------------------------------------
def cfg_from(src):
    v = input_values(src)
    c = pz.BCfg()
    for f in ("zoneHalfWidth", "clusterDist", "touchRearmDist", "breakBuffer", "flipConfirmDist", "scoreHz1", "scoreHz2",
              "scoreHz3", "thrMedium", "thrStrong", "thrVStrong", "confBonus2", "confBonus3", "confBonus4", "flipBonus"):
        setattr(c, f, float(v[f]))
    c.resetOnReclaim = v["resetOnReclaim"] == "true"
    c.fvgMinWidth = float(v["fvgMinWidth"])
    return c


def yen_scenario(seed, c, base=190.0):
    """Same yen sources (Swing / Accum / Day H-L centres around `base`) and the same 5M OHLC path for any config."""
    rng = random.Random(seed)
    srcs = []
    for i in range(14):
        cat, sid, tf, sc = rng.choice([(pz.CAT_HZ, "SWING_H", "5", 1.0), (pz.CAT_HZ, "SWING_L", "15", 2.0),
                                      (pz.CAT_HZ, "SWING_H", "60", 3.0), (pz.CAT_ACC, "ACC_HI", "60", 3.0),
                                      (pz.CAT_ACC, "ACC_LO", "240", 4.0), (pz.CAT_DHL, "DAY_H", "D", 3.0)])
        srcs.append((i, sid, cat, tf, round(base + rng.uniform(-0.6, 0.6), 3), sc))
    path, px = [], base
    for _ in range(240):
        o = px
        px = round(px + rng.gauss(0, 0.03), 3)
        path.append((round(max(o, px) + abs(rng.gauss(0, 0.01)), 3), round(min(o, px) - abs(rng.gauss(0, 0.01)), 3), px))
    return srcs, path


def run_engine(c, srcs, path):
    raws = [pz.Raw(i, sid, cat, tf, ctr, sc, c) for i, sid, cat, tf, ctr, sc in srcs]
    zones = pz.practical_build(raws, [], c)
    out = []
    for z in zones:
        t = pz.Track(z["top"], z["bottom"], wasStrong=False)
        t.flipped = False
        evs = [pz.engine_bar(t, c, z["strength"], z["top"], z["bottom"], hlc, k) for k, hlc in enumerate(path)]
        out.append((round(z["bottom"], 6), round(z["top"], 6), z["uids"], z["score"], z["strength"], t.state,
                    t.touchCount, tuple(e for e in evs if e)))
    return out


def fvg_dir(h2, l2, h0, l0, min_w, mintick=0.001):
    """f_fvgConfirmed detection: gap between bar[2] and bar[0], width normalised to mintick, >= minWidth."""
    bull, bear = l0 > h2, h0 < l2
    top, bot = (l0, h2) if bull else (l2, h0)
    w = round(round((top - bot) / mintick) * mintick, 6)
    return (1 if bull else -1) if (bull or bear) and w >= min_w else 0


def gate_model():
    cj, cg = cfg_from(JPY), cfg_from(GBJ)
    fields = [f for f in dir(cj) if not f.startswith("_")]
    dif = sorted(f for f in fields if getattr(cj, f) != getattr(cg, f))
    check("GM-01 Engine-relevant config read from the two files differs only in zoneHalfWidth (USDJPY Visual 0.05 / GBPJPY "
          "0.03); Cluster 0.08, FVG 0.05, Touch 0.15, Break 0.08, Flip 0.15 equal", dif == ["zoneHalfWidth"]
          and (cj.zoneHalfWidth, cg.zoneHalfWidth, cg.clusterDist, cg.fvgMinWidth) == (0.05, 0.03, 0.08, 0.05), str(dif))
    same, nonvac = True, False
    for seed in range(40):
        cg_eq = copy.copy(cg)
        cg_eq.zoneHalfWidth = cj.zoneHalfWidth          # GBPJPY file with the same inputs as the USDJPY file
        srcs, path = yen_scenario(seed, cj)
        a, b = run_engine(cj, srcs, path), run_engine(cg_eq, srcs, path)
        same &= a == b
        nonvac |= run_engine(cg, srcs, path) != a
    check("GM-02 same yen OHLC + same sources + same inputs (40 seeds): Zone bottom / top, members, Score, Strength, "
          "state, Touch count and Break / Flip events identical between the two files' configs", same)
    check("GM-03 non-vacuous: at the file defaults (HW 0.03 vs 0.05) the zones do differ on the same data", nonvac)
    srcs = [(0, "SWING_H", pz.CAT_HZ, "5", 190.000, 1.0), (1, "SWING_L", pz.CAT_HZ, "15", 190.500, 2.0),
            (2, "ACC_HI", pz.CAT_ACC, "60", 191.000, 3.0), (3, "SWING_H", pz.CAT_HZ, "60", 191.050, 3.0)]
    widths = {}
    for hw in (0.03, 0.05, 0.08):
        c = copy.copy(cg)
        c.zoneHalfWidth = hw
        widths[hw] = [(len(z[2]), round(z[1] - z[0], 6)) for z in run_engine(c, srcs, [(190.5, 190.4, 190.45)])]
    check("GM-04 Half Width candidates 0.03 / 0.05 / 0.08 (Cluster 0.08): a single-source Zone is exactly 2 x HW wide "
          "(0.06 / 0.10 / 0.16 円); two sources 0.05 apart merge into min bottom - max top = 2 x HW + 0.05",
          all(w == [(1, round(2 * hw, 6)), (1, round(2 * hw, 6)), (2, round(2 * hw + 0.05, 6))] for hw, w in widths.items()),
          str(widths))
    g = [fvg_dir(190.100, 190.000, 190.250, 190.150, cg.fvgMinWidth), fvg_dir(190.100, 190.000, 190.250, 190.149, 0.05),
         fvg_dir(190.100, 190.000, 190.250, 190.149, 0.049)]
    check("GM-05 FVG min width 0.05 円: a 0.050 gap qualifies, 0.049 does not (mintick 0.001); the input is what gates it",
          g == [1, 0, 1], str(g))
    rn = lambda enable, ticker: enable and ticker == "XAUUSD"
    check("GM-06 Round Number: OFF by default and stays OFF on GBPJPY even if the input is switched on (XAUUSD gate)",
          rn(False, "GBPJPY") is False and rn(True, "GBPJPY") is False and rn(True, "XAUUSD") is True)
    f3 = lambda v: f"{v:.3f}"
    geo = lambda top, bot: f3(top) + " - " + f3(bot) + " | W " + f3(top - bot) + "円"
    check("GM-07 label geometry for a GBPJPY zone: top 190.284, bottom 190.224 -> '190.284 - 190.224 | W 0.060円' (yen, "
          "3 decimals = mintick 0.001, not pips)", geo(190.284, 190.224) == "190.284 - 190.224 | W 0.060円")
    grid = [(hw, cd, fw) for hw in (0.03, 0.05, 0.08) for cd in (0.08, 0.12, 0.16) for fw in (0.05, 0.08, 0.10)]
    on_step = lambda x, s: abs(x / s - round(x / s)) < 1e-9
    check("GM-08 comparison grid (27 combinations) inside the input ranges and on the 0.005 step",
          all(hw >= 0.005 and on_step(hw, 0.005) and on_step(cd, 0.005) and on_step(fw, 0.005) for hw, cd, fw in grid))


def main():
    for g in (gate_static, gate_model):
        try:
            g()
        except Exception:
            import traceback
            check(f"{g.__name__} completed without error", False, traceback.format_exc()[-800:])
    fails = 0
    for n, ok, d in RESULTS:
        fails += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {n[:150].ljust(150)}  {'' if ok else d}")
    print(f"\n{len(RESULTS) - fails}/{len(RESULTS)} passed  [PINE_NOT_VERIFIED: exact build / static / mirror model]")
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
