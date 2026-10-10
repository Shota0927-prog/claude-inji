"""RN-1 Gate V1 fixtures — ZoneVisualPractical.pine imports ZoneEnginePractical/5 and enables Round Number for XAUUSD.

  VS : static — exact transform of the 6e554b2 Visual, import / input / config line, protected blocks, /5 API
       compatibility with the /2 text, Accum functions unchanged in /5, requests / inputs, ticker gate
  VD : display model — Engine time-series model (rn1_engine_model) RN OFF / ON through the draw mirror
       (zp_overlap_sim.draw_new): OFF draws exactly what the old Engine gives, ON keeps every zone extent and only
       changes strength / score / Touch driven attributes

Evidence class: PINE_NOT_VERIFIED (exact transform / static / Python model; TradingView compile / display external).
"""
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rnv_build as vb                # noqa: E402
import rn1_build as rb                # noqa: E402
import nr_s1_build as nb              # noqa: E402
import nr_a1_build as na              # noqa: E402
import fvg_batch_c_build as cb        # noqa: E402
import zp_overlap_build as zp         # noqa: E402

ROOT = vb.ROOT
CUR = open(os.path.join(ROOT, "ZoneVisualPractical.pine"), encoding="utf-8").read()
BASE = vb.git_show(vb.RNV_BASE_REV)
LIB_NEW = open(os.path.join(ROOT, rb.RN_PATH), encoding="utf-8").read()       # = published /5 (L3 accepted by the user)
LIB_OLD = open(os.path.join(ROOT, rb.OLD_PATH), encoding="utf-8").read()      # /2 reference text
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


def type_block(src, name):
    i = src.index(f"export type {name}\n")
    j = src.index("\n\n", i)
    return [l for l in src[i:j].split("\n")[1:] if l.strip() and not l.strip().startswith("//")]


def func(src, head):
    i = src.index(head)
    m = re.search(r"\n(?=\S)", src[i + len(head):])
    return src[i:i + len(head) + (m.start() + 1 if m else len(src))]


def ticker_gate(enable, ticker):
    """mirror of `enableRn and syminfo.ticker == "XAUUSD"`."""
    return bool(enable) and ticker == "XAUUSD"


# =============================================================================
# VS : static
# =============================================================================
def gate_static():
    check("VS-01 current Visual == rnv_transform(Visual @ 6e554b2) exactly (import, Round Number input, useRnSource)",
          bool(BASE) and vb.rnv_transform(BASE) == CUR)
    check("VS-02 strip_rnv(current) == Visual @ 6e554b2 byte-for-byte", vb.strip_rnv(CUR) == BASE)
    imps = re.findall(r"^import .*$", CUR, re.M)
    check("VS-03 exactly one import: sekine3310/ZoneEnginePractical/5 as zn", imps == ["import sekine3310/ZoneEnginePractical/5 as zn"],
          str(imps))
    co = code_only(CUR)
    check("VS-04 Enable Round Number: one bool input, default ON, own group",
          co.count('enableRn = input.bool(true, "Enable Round Number", group = G_RN,') == 1
          and co.count("enableRn") == 2 and 'var string G_RN = "02 · Round Number (XAUUSD)"' in co)
    rn_cfg = re.findall(r"^zoneCfg\.(rn\w+|useRnSource)\s*:=.*$", co, re.M)
    check("VS-05 config: only useRnSource is set, exactly `enableRn and syminfo.ticker == \"XAUUSD\"` (exact ticker; no "
          "contains / tickerid / partial match); RN steps / points left at the Library defaults (100 -> 3, 50 -> 2)",
          rn_cfg == ["useRnSource"] and co.count(vb.RN_CFG_LINE.rstrip("\n")) == 1
          and not re.search(r"str\.(contains|pos|startswith|endswith|match)|syminfo\.tickerid\s*==", co))
    check("VS-06 the Visual reads no rn* Zone field (display changes only through score / strength / Touch / srcMask)",
          not re.search(r"\.rn(Level|Base|ScoreDelta|BaseSumExRn)\b", co))
    for name, b, e in (("NR-S1", nb.NRS_BEGIN, nb.NRS_END), ("NR-A1", na.NRA_BEGIN, na.NRA_END),
                       ("FVG Batch A", cb.A_BEGIN, cb.A_END), ("FVG Batch C", cb.C_BEGIN, cb.C_END),
                       ("FVG overlap-only display", zp.ZPO_BEGIN, zp.ZPO_END)):
        check(f"VS-07 {name} block byte-identical to 6e554b2", block(CUR, b, e) is not None and block(CUR, b, e) == block(BASE, b, e))
    names = ["ZoneEnginePractical.pine", "ZoneEnginePracticalRN.pine", "ZoneEnginePracticalAuthority.pine", "ZoneEngine.pine",
             "SignalEnginePractical.pine", "SignalEngine.pine", "PracticalZoneStrategy_LONG.pine", "PracticalZoneStrategy_SHORT.pine",
             "FvgZoneStrategy.pine", "PracticalZoneFeedHarness.pine", "PracticalAlertHarness.pine", "PracticalTradeHarness.pine",
             "PracticalBreakEvenHarness.pine", "PracticalEntryDispatchHarness.pine"]
    d = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", vb.RNV_BASE_REV, "--"] + names, capture_output=True, text=True).stdout
    check("VS-08 Engine (/2 text and /5 text), Strategy, SignalEngine, Harness unchanged vs 6e554b2", d.strip() == "", d)
    # /5 API compatibility for everything the Visual uses
    old_exp = re.findall(r"^export .*$", LIB_OLD, re.M)
    new_exp = set(re.findall(r"^export .*$", LIB_NEW, re.M))
    types_ok = all(all(l in type_block(LIB_NEW, t) for l in type_block(LIB_OLD, t))
                   and [l for l in type_block(LIB_NEW, t) if l in type_block(LIB_OLD, t)] == type_block(LIB_OLD, t)
                   for t in ("ZoneCfg", "RawZone", "Zone", "ZoneTrack", "ZoneFeed", "ZoneEngine", "TradePlan"))
    used = sorted(set(re.findall(r"\bzn\.(\w+)", co)))
    check("VS-09 /5 is a superset of /2 for the Visual: every /2 export line present verbatim, every type keeps its /2 fields "
          "in order (only appended RN fields), every zn.* member used by the Visual exists",
          all(e in new_exp for e in old_exp) and types_ok
          and all(re.search(rf"^export (type )?{u}\b", LIB_NEW, re.M) for u in used), str(used))
    accs = ["f_accumBoxCore(", "f_accumBoxState(", "f_accumDetectProvisional(", "export accumPack(", "export pivotPack(", "export maPack("]
    check("VS-10 Accum / Swing / MA packs identical in /5 and /2 (NR-A1 local copy and the same / lower TF branch stay valid)",
          all(func(LIB_NEW, h) == func(LIB_OLD, h) for h in accs))
    req = lambda s: len(re.findall(r"request\.\w+\(", code_only(s)))
    inp = lambda s: re.findall(r"^\s*(\w+)\s*=\s*input\.\w+\(", s, re.M)
    check("VS-11 request call sites unchanged (10); inputs = 6e554b2 inputs + enableRn only",
          req(CUR) == req(BASE) == 10 and [x for x in inp(CUR) if x != "enableRn"] == inp(BASE)
          and inp(CUR).count("enableRn") == 1)
    table = [((True, "XAUUSD"), True), ((False, "XAUUSD"), False), ((True, "XAUUSD.PRO"), False), ((True, "XAUUSDm"), False),
             ((True, "GOLD"), False), ((True, "XAUEUR"), False), ((True, "xauusd"), False), ((True, "OANDA:XAUUSD"), False),
             ((True, "GC1!"), False), ((True, "XAUUSDT"), False)]
    check("VS-12 ticker gate: ON only for enable and ticker exactly \"XAUUSD\"; suffixed / lower-case / other gold symbols "
          "stay OFF", all(ticker_gate(*a) == e for a, e in table))


# =============================================================================
# VD : display model (Engine model + draw mirror)
# =============================================================================
def gate_display():
    import rn1_engine_model as em
    import zp_overlap_sim as zs
    stats = dict(snaps=0, off_eq_old=0, extent_eq=0, nonrn_eq=0, rn_zones=0, changed=0, n=0)
    bad = []
    for seed in (2, 3):
        b1, chart, htf = em.build(seed, 12)
        F = em.Feeds(b1, chart, htf, "nr")
        E_old, E_off, E_on = em.Engine(), em.Engine(), em.Engine()
        E_on.rn_attach = True
        for i in range(len(chart)):
            f = F.feed(i, len(chart[i]["subs"]) - 1, "hist")
            for E in (E_old, E_off, E_on):
                E.update(f, i)
            if i % 40 != 39:
                continue
            stats["snaps"] += 1

            def draws(E, cfg):
                zones = [dict(top=z["top"], bottom=z["bottom"], baseSum=z["baseSum"], catCount=z["catCount"],
                              hasHtf=z["hasHtf"], state=z["state"], touch=z["touch"], slopeBonus=z["slopeB"],
                              maBonus=z["maB"], flipBonus=z["flipBonus"], score=z["score"], strength=z["strength"])
                         for z in E.live]
                S = zs.Slots([zs.fvg(s, E.fTop[s], E.fBot[s], E.fClose[s], True) for s in range(15) if E.fAlive[s]])
                return zones, zs.draw_new(cfg, zones, S)

            cfg_def = zs.Cfg()                                                   # Visual defaults (Strong / VS shown)
            cfg_all = zs.Cfg(show={1: True, 2: True, 3: True, 4: True}, showState={0: True, 1: True, 2: True, 3: True},
                             showScore=True, maxZonesDraw=500)
            for cfg in (cfg_def, cfg_all):
                _, d_old = draws(E_old, cfg)
                _, d_off = draws(E_off, cfg)
                stats["off_eq_old"] += d_old == d_off
                stats["n"] += 1
            zon, (b_on, l_on) = draws(E_on, cfg_all)
            zoff, (b_off, l_off) = draws(E_off, cfg_all)
            ext = lambda bx, k: (max(x[3] for x in bx if x[2] == k), min(x[4] for x in bx if x[2] == k)) if any(x[2] == k for x in bx) else None
            ok_ext = all(ext(b_on, k) == ext(b_off, k) == (zon[k]["top"], zon[k]["bottom"]) for k in range(len(zon)))
            stats["extent_eq"] += ok_ext
            for k, z1 in enumerate(E_on.live):
                if z1["rnBase"] > 0:
                    stats["rn_zones"] += 1
                    stats["changed"] += [x for x in b_on if x[2] == k] != [x for x in b_off if x[2] == k] \
                        or [x for x in l_on if x[2] == k] != [x for x in l_off if x[2] == k]
                else:
                    same = [x for x in b_on if x[2] == k] == [x for x in b_off if x[2] == k] \
                        and [x for x in l_on if x[2] == k] == [x for x in l_off if x[2] == k]
                    stats["nonrn_eq"] += same
                    if not same:
                        bad.append((seed, i, k))
    check("VD-01 RN OFF draws exactly what the old Engine gives (Visual defaults and all-strengths / scores shown), every "
          "snapshot", stats["n"] > 0 and stats["off_eq_old"] == stats["n"], str(stats))
    check("VD-02 RN ON keeps every zone's drawn extent [bottom, top] (base + boost boxes cover the same range as OFF)",
          stats["extent_eq"] == stats["snaps"], str(stats))
    check("VD-03 zones without a Round Number draw identically ON / OFF (boxes, labels, scores)", not bad, str(bad[:5]))
    check("VD-04 zones with a Round Number do change (strength / score / Touch driven boxes and labels)",
          stats["rn_zones"] > 0 and stats["changed"] > 0, str(stats))


def main():
    for g in (gate_static, gate_display):
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
    print(f"\n{len(RESULTS) - fails}/{len(RESULTS)} passed  [PINE_NOT_VERIFIED: exact transform / static / display model]")
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
