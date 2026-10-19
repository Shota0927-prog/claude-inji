"""JPY-1 fixtures — ZoneVisualUSDJPY.pine (OANDA:USDJPY 5M Zone comparison, no entries).

  JS : static — deterministic build from ZONE-P; strip_jpy(file) == ZONE-P byte for byte (only the listed edits);
       price-difference inputs in yen with yen defaults / minval / step; FVG min width input wired into the three FVG
       requests; Round Number OFF; Engine config assignments, requests (10), NR-S1 / NR-A1 / FVG Batch A / C blocks and
       the update order identical to ZONE-P; labels show top / bottom / width / Score / Sources; other files unchanged
  JM : the label geometry string and the yen candidate grid (Half Width x Cluster Distance) evaluated in Python

Evidence class: PINE_NOT_VERIFIED (TradingView compile / display external).
"""
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jpy_build as jb          # noqa: E402
import nr_s1_build as nb        # noqa: E402
import nr_a1_build as na        # noqa: E402
import fvg_batch_c_build as cb  # noqa: E402
import zp_overlap_build as zp   # noqa: E402
import fvg_re10045_sim as fr    # noqa: E402

ROOT = jb.ROOT
VIS = open(os.path.join(ROOT, jb.SRC_PATH), encoding="utf-8").read()
JPY = __import__("uj_build").pre_uj(jb.JPY_PATH) if os.path.exists(os.path.join(ROOT, jb.JPY_PATH)) else ""     # UJ-1: USDJPY Visual / Strategy may differ only by the USDJPY Engine split + sizing (exact, see uj_build)
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


PRICE_INPUTS = {   # name: (default, minval, step, compared now?)
    "zoneHalfWidth": ("0.05", "0.005", "0.005", True),
    "clusterDist": ("0.08", "0.0", "0.005", True),
    "fvgMinWidth": ("0.05", "0.0", "0.005", True),
    "slopeThrMod": ("0.02", "0.0", "0.005", False),
    "slopeThrStrong": ("0.05", "0.0", "0.005", False),
    "maClusterDist": ("0.30", "0.0", "0.01", False),
    "touchRearmDist": ("0.15", "0.0", "0.01", False),
    "breakBuffer": ("0.08", "0.0", "0.005", False),
    "flipConfirmDist": ("0.15", "0.0", "0.01", False),
}


def gate_static():
    check("JS-01 ZoneVisualUSDJPY.pine == jpy_transform(ZoneVisualPractical.pine); strip_jpy gives ZONE-P back byte for "
          "byte (the file differs from ZONE-P only by the listed edits)",
          bool(JPY) and jb.build() == JPY and jb.strip_jpy(JPY) == VIS and jb.jpy_transform(jb.strip_jpy(JPY)) == JPY)
    bad = []
    for n, (dv, mv, st, _) in PRICE_INPUTS.items():
        a = inp(JPY, n)
        if not (a.startswith(dv + ",") and f"minval = {mv}," in a and f"step = {st}," in a and "円" in a):
            bad.append((n, a))
    check("JS-02 price-difference inputs in yen: Half Width 0.05 (min 0.005, step 0.005), Cluster Distance 0.08, FVG Min "
          "Width 0.05; unit-converted placeholders ([暫定]) for slope thresholds 0.02 / 0.05, MA Cluster 0.30, Touch "
          "Re-arm 0.15, Break Buffer 0.08, Flip Confirm 0.15", bad == [], str(bad))
    ins = re.findall(r"^(\w+)\s*=\s*input\.float\((.*)$", code_only(JPY), re.M)
    dollar = [n for n, a in ins if "$" in a]
    check("JS-03 no input is labelled in $ any more (every price difference is in 円)", dollar == [], str(dollar))
    check("JS-04 Round Number default OFF; the XAUUSD ticker gate on the Engine config is kept",
          inp(JPY, "enableRn").startswith("false,")
          and 'zoneCfg.useRnSource          := enableRn and syminfo.ticker == "XAUUSD"' in JPY)
    calls = re.findall(r"f_fvgConfirmed\((\w+)\)", code_only(JPY))
    check("JS-05 FVG min width: the fixed 3.0 is replaced by the input, used by all three FVG requests (15M / 1H / 4H)",
          "float  FVG_MIN_WIDTH    = fvgMinWidth" in JPY and "FVG_MIN_WIDTH    = 3.0" not in JPY
          and calls == ["FVG_MIN_WIDTH"] * 3, str(calls))
    cfg = lambda s: re.findall(r"^zoneCfg\.\w+\s*:=.*$", s, re.M)
    req = lambda s: re.findall(r"request\.\w+\(.*$", code_only(s), re.M)
    check("JS-06 Engine config assignments identical to ZONE-P; request call sites identical (10, no new request); single "
          "import ZoneEnginePractical/6; zn.update called once",
          cfg(JPY) == cfg(VIS) and req(JPY) == req(VIS) and len(req(JPY)) == 10
          and re.findall(r"^import .*$", JPY, re.M) == ["import sekine3310/ZoneEnginePractical/6 as zn"]
          and code_only(JPY).count("zn.update(") == code_only(VIS).count("zn.update(") == 1)
    same = []
    for name, b, e in (("NR-S1", nb.NRS_BEGIN, nb.NRS_END), ("NR-A1", na.NRA_BEGIN, na.NRA_END),
                       ("FVG Batch C", cb.C_BEGIN, cb.C_END), ("ZPO", zp.ZPO_BEGIN, zp.ZPO_END)):
        bj, bv = block(JPY, b, e), block(VIS, b, e)
        if name == "FVG Batch C":
            bj = bj.replace('    if showGeom\n        txt := txt + "\\n" + f_jpyGeom(z)\n', "") if bj else bj
        same.append((name, bj is not None and bj == bv))
    ba_j, ba_v = block(JPY, cb.A_BEGIN, cb.A_END), block(VIS, cb.A_BEGIN, cb.A_END)
    fvg_old, fvg_new = next(x for x in jb.EDITS if x[0].startswith("float  FVG_MIN_WIDTH"))
    same.append(("FVG Batch A (only FVG_MIN_WIDTH source)", ba_j is not None and ba_j.count(fvg_new) == 1
                 and ba_j.replace(fvg_new, fvg_old) == ba_v))
    check("JS-07 non-repaint / scoring blocks identical to ZONE-P: NR-S1, NR-A1, FVG Batch A (except the FVG min width "
          "source), Batch C scoring (labels aside), overlap display", all(o for _, o in same), str(same))
    lt = re.search(r"^f_labelText\(zn\.Zone z\) =>\n(?:    .*\n)+", JPY, re.M).group(0)
    ft = re.search(r"^f_fvcLabelText\(zn\.Zone z, int dStr, float dScore\) =>\n(?:    .*\n)+", JPY, re.M).group(0)
    order = lambda t: [t.index(k) for k in ("strengthName", "showScore", "showGeom", "showDetailLbl")]
    check("JS-08 labels: Strength | Touch | Score (| FVG tag) / top - bottom | W width (yen, 3 decimals) / Sources; Score, "
          "geometry and Sources ON by default; same for the FVG-boosted label (geometry of the Engine zone)",
          "f_jpyGeom(z)" in lt and "f_jpyGeom(z)" in ft and order(lt) == sorted(order(lt)) and order(ft) == sorted(order(ft))
          and inp(JPY, "showScore").startswith("true,") and inp(JPY, "showGeom").startswith("true,")
          and inp(JPY, "showDetailLbl").startswith("true,")
          and 'f_num(z.top, "#.000") + " - " + f_num(z.bottom, "#.000") + " | W " + f_num(z.top - z.bottom, "0.000")' in JPY)
    check("JS-09 RE10045 lint clean; drawing still only on barstate.islast (no new box / label / table call sites)",
          fr.lint_eager_guards(code_only(JPY)) == []
          and len(re.findall(r"\b(box|label|table)\.new\(", JPY)) == len(re.findall(r"\b(box|label|table)\.new\(", VIS)))
    names = ["ZoneVisualPractical.pine", "ZoneStrategyXAU.pine", "ZoneEnginePractical.pine", "ZoneEnginePracticalRN.pine",
             "ZoneEnginePracticalSwingMax.pine", "PracticalZoneStrategy_LONG.pine", "PracticalZoneStrategy_SHORT.pine",
             "SignalEnginePractical.pine"]
    d = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", "25af623", "--"] + names, capture_output=True, text=True).stdout
    check("JS-10 XAUUSD Visual (ZONE-P), Strategy (ZONE-ST), Engines (/2, /5, /6) and the old strategies unchanged vs 25af623",
          d.strip() == "", d)


def gate_model():
    fmt3 = lambda v: f"{v:.3f}"
    geo = lambda top, bot: fmt3(top) + " - " + fmt3(bot) + " | W " + fmt3(top - bot)
    check("JM-01 label geometry for a USDJPY zone: top 151.284, bottom 151.184 -> '151.284 - 151.184 | W 0.100'",
          geo(151.284, 151.184) == "151.284 - 151.184 | W 0.100")
    # one Raw zone = center +/- HW (width 2 HW); two sources merge when their centers are <= CD apart (Engine cluster rule)
    grid = [(hw, cd, round(2 * hw, 3), round(2 * hw + cd, 3)) for hw in (0.03, 0.05, 0.08) for cd in (0.05, 0.08, 0.12)]
    check("JM-02 comparison grid is in yen and inside the input ranges (Half Width 0.03 / 0.05 / 0.08 >= min 0.005, Cluster "
          "Distance 0.05 / 0.08 / 0.12 >= 0, all on the 0.005 step); single-source width 2 x HW, two merged sources up to "
          "2 x HW + CD", all(hw >= 0.005 and cd >= 0 and abs(hw / 0.005 - round(hw / 0.005)) < 1e-9
                             and abs(cd / 0.005 - round(cd / 0.005)) < 1e-9 for hw, cd, _, _ in grid), str(grid))


def main():
    for g in (gate_static, gate_model):
        try:
            g()
        except Exception:
            import traceback
            check(f"{g.__name__} completed without error", False, traceback.format_exc()[-600:])
    fails = 0
    for n, ok, d in RESULTS:
        fails += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {n[:150].ljust(150)}  {'' if ok else d}")
    print(f"\n{len(RESULTS) - fails}/{len(RESULTS)} passed  [PINE_NOT_VERIFIED: exact build / static]")
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
