"""SW-1 Gate SW-V1 fixtures — ZoneVisualPractical.pine imports ZoneEnginePractical/6 (Swing max-score).

  SV : static — one-line exact transform of the 110e5b0 Visual, import / references, /6 API vs /5, Swing max in /6,
       protected blocks (NR-S1, NR-A1, FVG A / C, overlap-only display, RN input / config), Engines / Strategy untouched
  SM : scoring through the /6 port (sw1_sim.finalize) and the time-series model (sw1_sim.gate_series), RN OFF and ON

Evidence class: PINE_NOT_VERIFIED (exact transform / static / port / model; TradingView compile / display external).
"""
import difflib
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import swv_build as wb                # noqa: E402
import sw1_build as sb                # noqa: E402
import rnv_build as vb                # noqa: E402
import nr_s1_build as nb              # noqa: E402
import nr_a1_build as na              # noqa: E402
import fvg_batch_c_build as cb        # noqa: E402
import zp_overlap_build as zp         # noqa: E402

ROOT = wb.ROOT
CUR = open(os.path.join(ROOT, "ZoneVisualPractical.pine"), encoding="utf-8").read()
CUR = __import__("fvl_build").strip_fvl(CUR) or CUR  # FVG label info stripped -> 67f8fd2 text (delta pinned by fvl_sim)
BASE = wb.git_show(wb.SWV_BASE_REV)
LIB6 = open(os.path.join(ROOT, sb.SW_PATH), encoding="utf-8").read()       # = published /6 (confirmed by the user)
LIB5 = open(os.path.join(ROOT, sb.SRC_PATH), encoding="utf-8").read()      # /5 source
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


def func(src, head):
    i = src.index(head)
    m = re.search(r"\n(?=\S)", src[i + len(head):])
    return src[i:i + len(head) + (m.start() + 1 if m else len(src))]


def gate_static():
    check("SV-01 current Visual == swv_transform(Visual @ 110e5b0) exactly", bool(BASE) and wb.swv_transform(BASE) == CUR)
    check("SV-02 strip_swv(current) == Visual @ 110e5b0 byte-for-byte", wb.strip_swv(CUR) == BASE)
    dl = [l for l in difflib.unified_diff(BASE.split("\n"), CUR.split("\n"), lineterm="", n=0)
          if l[:1] in "+-" and not l.startswith(("+++", "---"))]
    check("SV-03 the Visual diff vs 110e5b0 is exactly one line: the import /5 -> /6",
          dl == ["-import sekine3310/ZoneEnginePractical/5 as zn", "+import sekine3310/ZoneEnginePractical/6 as zn"], str(dl))
    imps = re.findall(r"^import .*$", CUR, re.M)
    co = code_only(CUR)
    check("SV-04 exactly one import, sekine3310/ZoneEnginePractical/6 as zn; no /2 or /5 ZoneEnginePractical reference in code",
          imps == ["import sekine3310/ZoneEnginePractical/6 as zn"]
          and not re.search(r"ZoneEnginePractical/(?!6\b)\d+", co), str(imps))
    old_exp = re.findall(r"^export .*$", LIB5, re.M)
    new_exp = set(re.findall(r"^export .*$", LIB6, re.M))
    tb = lambda t: {m.group(1): m.group(0) for m in re.finditer(r"^export type (\w+)\n(?:.*\n)*?\n", t, re.M)}
    used = sorted(set(re.findall(r"\bzn\.(\w+)", co)))
    check("SV-05 /6 API == /5 for the Visual: every /5 export line verbatim in /6, every exported type identical, every "
          "zn.* member the Visual uses exists",
          all(e in new_exp for e in old_exp) and len(new_exp) == len(old_exp) and tb(LIB6) == tb(LIB5)
          and all(re.search(rf"^export (type )?{u}\b", LIB6, re.M) for u in used), str(used))
    fz = func(LIB6, "f_finalizeCluster(")
    check("SV-06 /6 carries the Swing max-score (f_swingMaxStep used for the three Swing timeframes, no additive "
          "baseSum += c.scoreHzN); /6 == sw_transform(/5 source)",
          "f_swingMaxStep(float swMax, float s) =>" in LIB6 and fz.count("f_swingMaxStep(swMax, c.scoreHz") == 3
          and not re.search(r"baseSum \+= c\.scoreHz\d", fz) and sb.sw_transform(LIB5) == LIB6)
    for name, b, e in (("NR-S1", nb.NRS_BEGIN, nb.NRS_END), ("NR-A1", na.NRA_BEGIN, na.NRA_END),
                       ("FVG Batch A", cb.A_BEGIN, cb.A_END), ("FVG Batch C", cb.C_BEGIN, cb.C_END),
                       ("FVG overlap-only display", zp.ZPO_BEGIN, zp.ZPO_END)):
        check(f"SV-07 {name} block byte-identical to 110e5b0", block(CUR, b, e) is not None and block(CUR, b, e) == block(BASE, b, e))
    inp = lambda s: re.findall(r"^\s*\w+\s*=\s*input\.\w+\(.*$", s, re.M)
    cfg = lambda s: re.findall(r"^zoneCfg\.\w+\s*:=.*$", s, re.M)
    check("SV-08 RN input (default ON) and `useRnSource := enableRn and syminfo.ticker == \"XAUUSD\"` unchanged; every input "
          "and every zoneCfg assignment identical to 110e5b0",
          co.count(vb.RN_CFG_LINE.rstrip("\n")) == 1 and inp(CUR) == inp(BASE) and cfg(CUR) == cfg(BASE))
    names = ["ZoneEnginePractical.pine", "ZoneEnginePracticalRN.pine", "ZoneEnginePracticalSwingMax.pine",
             "ZoneEnginePracticalAuthority.pine", "ZoneEngine.pine", "SignalEnginePractical.pine", "SignalEngine.pine",
             "PracticalZoneStrategy_LONG.pine", "PracticalZoneStrategy_SHORT.pine", "FvgZoneStrategy.pine",
             "PracticalZoneFeedHarness.pine", "PracticalAlertHarness.pine", "PracticalTradeHarness.pine",
             "PracticalBreakEvenHarness.pine", "PracticalEntryDispatchHarness.pine"]
    d = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", wb.SWV_BASE_REV, "--"] + names, capture_output=True, text=True).stdout
    check("SV-09 Engine sources (/2, /5, /6), Strategy, SignalEngine, Harness unchanged vs 110e5b0", d.strip() == "", d)
    req = lambda s: len(re.findall(r"request\.\w+\(", code_only(s)))
    check("SV-10 request call sites unchanged (10)", req(CUR) == req(BASE) == 10)


def gate_scoring():
    import sw1_sim as ss
    import practical_zone_sim as pz
    c = ss.Cfg()
    sw = lambda u, tf, x=4200.0: pz.Raw(u, "SWING_H", pz.CAT_HZ, tf, x, 1.0, c)
    acc = pz.Raw(9, "ACC_HI", pz.CAT_ACC, "240", 4201.0, 4.0, c)
    rows = []
    for rn in (False, True):
        for mem, exp in (([sw(1, "5"), sw(2, "15"), sw(3, "60")], 3.0), ([sw(1, "5"), sw(2, "15")], 2.0),
                         ([sw(1, "60")], 3.0), ([sw(1, "5"), sw(2, "15"), sw(3, "60"), acc], 7.0), ([acc], 4.0)):
            n = ss.finalize(mem, c, 4196, 4204, rn)
            o = ss.finalize(mem, c, 4196, 4204, rn, False)
            rows.append((rn, len(mem), n["baseSum"], n["rnBaseSumExRn"]))
            ok = n["rnBaseSumExRn"] == exp and n["baseSum"] == exp + (3.0 if rn else 0.0) \
                and (n["catCount"], n["hasHtf"], n["srcM"], n["rnBase"]) == (o["catCount"], o["hasHtf"], o["srcM"], o["rnBase"])
            if not ok:
                break
    check("SM-01 /6 scoring with RN OFF and ON: 5M + 15M + 1H = 3, 5M + 15M = 2, 1H = 3, + Accum 4H = 7, Accum only 4; RN "
          "adds its 3 on top; Swing category / HTF / srcMask / RN unchanged", len(rows) == 10, str(rows))
    ss.RESULTS.clear()
    ss.gate_series()
    sub = {n: (ok, d) for n, ok, d in ss.RESULTS}
    ok = all(v[0] for v in sub.values()) and len(sub) == 3
    check("SM-02 time-series model (additive /5 vs max /6, RN OFF and ON): Raw Zones, geometry, members, Track, Break / Flip, "
          "events, FVG storage identical; only clusters with 2+ Swing timeframes change; RN restoration holds",
          ok, str([(n[:6], v[0]) for n, v in sub.items()]))


def main():
    for g in (gate_static, gate_scoring):
        try:
            g()
        except Exception:
            import traceback
            check(f"{g.__name__} completed without error", False, traceback.format_exc()[-500:])
    w = max(len(n) for n, _, _ in RESULTS)
    fails = 0
    for n, ok, d in RESULTS:
        fails += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {n.ljust(w)}  {'' if ok else d}")
    print(f"\n{len(RESULTS) - fails}/{len(RESULTS)} passed  [PINE_NOT_VERIFIED: exact transform / static / port / model]")
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
