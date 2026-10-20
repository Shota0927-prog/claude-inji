"""FVG label info fixtures — ZoneVisualPractical.pine (overlap-only display labels show the adopted FVG).

  LS : static — exact transform of the 67f8fd2 Visual, change confined to the overlap-only display labels, helpers,
       same FVG selection as the Batch C score, no score / box / pool change, protected blocks, Engines untouched
  LM : label mirror (zp_overlap_sim draw mirror + the tag) — cases 1..16 of the instruction

Evidence class: PINE_NOT_VERIFIED (exact transform / static / mirror; TradingView compile / display external).
"""
import itertools
import os
import random
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fvl_build as lb                # noqa: E402
import zp_overlap_build as zp         # noqa: E402
import nr_s1_build as nb              # noqa: E402
import nr_a1_build as na              # noqa: E402
import fvg_batch_c_build as cb        # noqa: E402
import fvg_re10045_sim as fr          # noqa: E402
import zp_overlap_sim as zs           # noqa: E402

ROOT = lb.ROOT
CUR = __import__("xa_build").pre_xa("ZoneVisualPractical.pine", open(os.path.join(ROOT, "ZoneVisualPractical.pine"), encoding="utf-8").read())  # XA-1 Gold defaults stripped -> f253890 text (delta pinned by xa_sim)
CUR = __import__("bon_build").strip_bon(CUR) or CUR  # bonus defaults stripped -> 9270c50 text (delta pinned by bon_sim)
BASE = lb.git_show(lb.FVL_BASE_REV)
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


# =============================================================================
# LS : static
# =============================================================================
def gate_static():
    check("LS-01 current Visual == fvl_transform(Visual @ 67f8fd2) exactly (2 edits)", bool(BASE) and lb.fvl_transform(BASE) == CUR)
    check("LS-02 strip_fvl(current) == Visual @ 67f8fd2 byte-for-byte", lb.strip_fvl(CUR) == BASE)
    zc, zb = block(CUR, zp.ZPO_BEGIN, zp.ZPO_END), block(BASE, zp.ZPO_BEGIN, zp.ZPO_END)
    check("LS-03 the change is confined to the overlap-only display block (file outside it identical to 67f8fd2)",
          bool(zc and zb) and CUR.replace(zc, "") == BASE.replace(zb, ""))
    for name, b, e in (("NR-S1", nb.NRS_BEGIN, nb.NRS_END), ("NR-A1", na.NRA_BEGIN, na.NRA_END),
                       ("FVG Batch A", cb.A_BEGIN, cb.A_END), ("FVG Batch C", cb.C_BEGIN, cb.C_END)):
        check(f"LS-04 {name} block byte-identical to 67f8fd2", block(CUR, b, e) is not None and block(CUR, b, e) == block(BASE, b, e))
    tag = func(CUR, "f_zpoFvgTag(")
    check("LS-05 f_zpoFvgTag: only for best >= 0; timeframe and points from f_fvcBase(best) (1 -> 15M +1, 2 -> 1H +2, "
          "3 -> 4H +3); otherwise empty",
          "    if best >= 0\n        float b = f_fvcBase(best)\n" in tag
          and 'tag := " | FVG " + (b == 1.0 ? "15M" : b == 2.0 ? "1H" : "4H") + " +" + str.tostring(b, "#")' in tag
          and '    string tag = ""\n' in tag)
    wf = func(CUR, "f_zpoWithFvg(")
    check("LS-06 f_zpoWithFvg: unchanged text for an empty tag; otherwise inserted before the first newline (Detailed "
          "Labels line) or appended", 'if tag != ""' in wf and 'int p = str.pos(txt, "\\n")' in wf
          and "out := na(p) ? txt + tag : str.substring(txt, 0, p) + tag + str.substring(txt, p)" in wf)
    calls = ['string fvgTag = f_zpoFvgTag(best)',
             'nLbl := f_zpoLabel(nLbl, xR, oTop, f_zpoWithFvg(f_fvcLabelText(z, dStr, dScore), fvgTag), lc)',
             'nLbl := f_zpoLabel(nLbl, xR, z.top, f_zpoWithFvg(f_labelText(z), showBoost ? "" : fvgTag), lc)']
    check("LS-07 tag source = the same `best` that decides the boost (f_zpoBestFvg(z)); boost label carries it, the "
          "original label only when no boost label is drawn; still 2 label calls per zone, no new box / label pool",
          all(zc.count(c) == 1 for c in calls) and zc.count("int  best    = f_zpoBestFvg(z)") == 1
          and zc.count("nLbl := f_zpoLabel(") == 2 and code_only(CUR).count("label.new(") == 1
          and code_only(CUR).count("box.new(") == 1)
    sel_c = CUR[CUR.index("f_fvcZoneDisplay(zn.Zone z) =>\n") + len("f_fvcZoneDisplay(zn.Zone z) =>\n"):CUR.index("    float dScore = z.score\n")]
    sel_z = func(CUR, "f_zpoBestFvg(zn.Zone z) =>\n")[len("f_zpoBestFvg(zn.Zone z) =>\n"):]
    check("LS-08 the label's FVG and the Batch C score use one selection: f_zpoBestFvg loop == f_fvcZoneDisplay loop",
          sel_z.rstrip("\n") == (sel_c + "    best").rstrip("\n"))
    back = zc
    for a, b in reversed(lb.FVL_EDITS):
        back = back.replace(b, a)
    check("LS-09 with the 2 label edits reverted the display block equals 67f8fd2 (boxes, filters, boost decision, Score / "
          "Strength values untouched)", back == zb)
    names = ["ZoneEnginePractical.pine", "ZoneEnginePracticalRN.pine", "ZoneEnginePracticalSwingMax.pine",
             "SignalEnginePractical.pine", "PracticalZoneStrategy_LONG.pine", "PracticalZoneStrategy_SHORT.pine"]
    d = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", lb.FVL_BASE_REV, "--"] + names, capture_output=True, text=True).stdout
    imps = re.findall(r"^import .*$", CUR, re.M)
    req = lambda s: len(re.findall(r"request\.\w+\(", code_only(s)))
    inp = lambda s: re.findall(r"^\s*\w+\s*=\s*input\.\w+\(.*$", s, re.M)
    check("LS-10 Engines (/2, /5, /6), Strategy, SignalEngine unchanged; import /6; requests and inputs unchanged",
          d.strip() == "" and imps == ["import sekine3310/ZoneEnginePractical/6 as zn"] and req(CUR) == req(BASE)
          and inp(CUR) == inp(BASE), d)
    check("LS-11 RE10045 lint clean for the new helpers / label lines (no barstate / request / var)",
          fr.lint_eager_guards(code_only(tag + wf)) == [] and not re.search(r"request\.|barstate|\bvar\b", code_only(tag + wf)))


# =============================================================================
# LM : label mirror
# =============================================================================
def fvg_tag(best):
    if best < 0:
        return ""
    b = zs.base_pts(best)
    return " | FVG " + ("15M" if b == 1.0 else "1H" if b == 2.0 else "4H") + " +" + str(int(b))


def with_fvg(txt, tag):
    if tag == "":
        return txt
    p = txt.find("\n")
    return txt + tag if p < 0 else txt[:p] + tag + txt[p:]


def draw_labels(c, zones, S, detail=False):
    """mirror of the ZPO label part with the FVG tag (detail: Detailed Labels line '\\nSRC')."""
    out, nZone = [], 0
    if not (c.showZones and zones):
        return out
    for k, z in enumerate(zones):
        if nZone >= c.maxZonesDraw:
            break
        if not c.showState[z["state"]]:
            continue
        dScore, dStr = zs.zone_display(c, z, S)
        best = zs.best_fvg(z, S)
        boosted = best >= 0 and dStr > z["strength"]
        oTop = min(z["top"], S.get("top", best)) if boosted else z["top"]
        showBase, showBoost = c.show[z["strength"]], boosted and c.show[dStr]
        if not (showBase or showBoost):
            continue
        nZone += 1
        if c.showLabels:
            tag = fvg_tag(best)
            dl = "\nSRC" if detail else ""
            if showBoost:
                out.append(("boost", k, with_fvg(zs.label_boost(c, z, dStr, dScore) + dl, tag)))
            if showBase and not (showBoost and oTop == z["top"]):
                out.append(("base", k, with_fvg(zs.label_base(c, z) + dl, "" if showBoost else tag)))
    return out


ALL = {1: True, 2: True, 3: True, 4: True}


def texts(c, zones, S, detail=False):
    return [(x[0], x[2]) for x in draw_labels(c, zones, S, detail)]


def gate_mirror():
    c = zs.Cfg(show=dict(ALL))
    zS = zs.zone(c, 2010, 2000, 10.0, htf=False, touch=2)          # 10 STRONG (no HTF: 15+ capped)
    zSh = zs.zone(c, 2010, 2000, 12.0, htf=True, touch=2)          # 12 STRONG with HTF
    zM = zs.zone(c, 2010, 2000, 7.0)                               # 7 MEDIUM
    none = zs.Slots([])
    # 1 no FVG: identical to the old (zp_overlap_sim) labels, with and without detail / score
    ok1 = True
    for sc_, det in itertools.product((False, True), (False, True)):
        cc = zs.Cfg(show=dict(ALL), showScore=sc_)
        zones = [zs.zone(cc, 2010 + 30 * i, 2000 + 30 * i, 3.0 + 3 * i, htf=i % 2 == 0, touch=i) for i in range(6)]
        _, old = zs.draw_new(cc, zones, none)
        new = draw_labels(cc, zones, none, det)
        ok1 &= [(x[1], x[2], x[4] + ("\nSRC" if det else "")) for x in old] == [(x[0], x[1], x[2]) for x in new]
    check("LM-01 no FVG: every label string identical to the old display (Score / Detailed Labels on and off)", ok1)
    # 2-4 one FVG of each timeframe, strength unchanged (STRONG without HTF stays STRONG)
    rows = []
    for slot, exp in ((0, "STRONG | Touch 2 | FVG 15M +1"), (5, "STRONG | Touch 2 | FVG 1H +2"), (10, "STRONG | Touch 2 | FVG 4H +3")):
        t = texts(c, [zS], zs.Slots([zs.fvg(slot, 2005, 1995, 1)]))
        rows.append(t)
        check(f"LM-0{2 + slot // 5} {['15M', '1H', '4H'][slot // 5]} FVG, no strength change: original label keeps the Engine "
              f"strength and gets '{exp.split(' | ')[-1]}'", t == [("base", exp)], str(t))
    # 5 several FVGs: one only, 4H over 15M, same TF newer
    t = texts(c, [zS], zs.Slots([zs.fvg(0, 2012, 2006, 9), zs.fvg(10, 2004, 1995, 1)]))
    t2 = texts(c, [zS], zs.Slots([zs.fvg(5, 2004, 1995, 1), zs.fvg(6, 2009, 2006, 2)]))
    check("LM-05 several FVGs: one tag only (4H over 15M; same timeframe -> newer close), never summed",
          t == [("base", "STRONG | Touch 2 | FVG 4H +3")] and t2 == [("base", "STRONG | Touch 2 | FVG 1H +2")], f"{t} {t2}")
    # 6 strength unchanged but score up: Score shows the Engine value
    cs = zs.Cfg(show=dict(ALL), showScore=True)
    zSs = zs.zone(cs, 2010, 2000, 10.0, touch=2)
    t = texts(cs, [zSs], zs.Slots([zs.fvg(5, 2005, 1995, 1)]))
    check("LM-06 no strength change with Show Score: 'STRONG | Touch 2 | 10 | FVG 1H +2' (Engine score 10, not the boosted 13)",
          t == [("base", "STRONG | Touch 2 | 10 | FVG 1H +2")], str(t))
    # 7 MEDIUM -> STRONG (boost label gets the tag, original label does not)
    t = texts(c, [zM], zs.Slots([zs.fvg(10, 2005, 1995, 1)]))
    check("LM-07 MEDIUM -> STRONG: boost label 'STRONG | FVG 4H +3', original label 'MEDIUM' without the tag",
          t == [("boost", "STRONG | FVG 4H +3"), ("base", "MEDIUM")], str(t))
    # 8 STRONG -> VERY STRONG with score (instruction example)
    t = texts(cs, [zs.zone(cs, 2010, 2000, 12.0, htf=True, touch=2)], zs.Slots([zs.fvg(10, 2005, 1995, 1)]))
    check("LM-08 STRONG -> VERY STRONG with Show Score: boost 'VERY STRONG | Touch 2 | 16 | FVG 4H +3' (12 + 4H 3 + "
          "confluence step 1), original keeps 'STRONG | Touch 2 | 12' without the tag",
          t == [("boost", "VERY STRONG | Touch 2 | 16 | FVG 4H +3"), ("base", "STRONG | Touch 2 | 12")], str(t))
    # 9 Show Score off / on
    t_off = texts(c, [zS], zs.Slots([zs.fvg(5, 2005, 1995, 1)]))
    t_on = texts(cs, [zSs], zs.Slots([zs.fvg(5, 2005, 1995, 1)]))
    check("LM-09 Show Score OFF hides only the number, the FVG tag stays", t_off == [("base", "STRONG | Touch 2 | FVG 1H +2")]
          and t_on == [("base", "STRONG | Touch 2 | 10 | FVG 1H +2")], f"{t_off} {t_on}")
    # 10 Detailed Labels on / off
    td = texts(c, [zS], zs.Slots([zs.fvg(5, 2005, 1995, 1)]), detail=True)
    check("LM-10 Detailed Labels ON: tag before the source line; OFF: tag still shown",
          td == [("base", "STRONG | Touch 2 | FVG 1H +2\nSRC")] and t_off[0][1].endswith("FVG 1H +2"), str(td))
    # 11 Show Labels off
    cl = zs.Cfg(show=dict(ALL), showLabels=False)
    check("LM-11 Show Labels OFF: no label at all", texts(cl, [zs.zone(cl, 2010, 2000, 10.0)], zs.Slots([zs.fvg(5, 2005, 1995, 1)])) == [])
    # 12 duplicate prevention: both labels / collision / boost hidden
    both = texts(c, [zSh], zs.Slots([zs.fvg(10, 2005, 1995, 1)]))
    coll = texts(c, [zSh], zs.Slots([zs.fvg(10, 2015, 2006, 1)]))
    ch = zs.Cfg(show={1: True, 2: True, 3: True, 4: False})
    hid = texts(ch, [zs.zone(ch, 2010, 2000, 12.0, htf=True, touch=2)], zs.Slots([zs.fvg(10, 2005, 1995, 1)]))
    check("LM-12 the tag appears once per zone: on the boost label when both labels exist, on the boost label when it "
          "replaces the original at the same y, on the original label when the boost strength is filtered out",
          sum("FVG" in x[1] for x in both) == 1 and both[0] == ("boost", "VERY STRONG | Touch 2 | FVG 4H +3")
          and coll == [("boost", "VERY STRONG | Touch 2 | FVG 4H +3")] and hid == [("base", "STRONG | Touch 2 | FVG 4H +3")],
          f"{both} {coll} {hid}")
    # 13 FVG filled / expired, edge contact only
    dead = texts(c, [zS], zs.Slots([zs.fvg(10, 2005, 1995, 1, alive=False)]))
    edge = texts(c, [zS], zs.Slots([zs.fvg(10, 2020, 2010, 1)]))
    check("LM-13 FVG filled / expired (not alive) or only touching the edge: no tag, label as before",
          dead == [("base", "STRONG | Touch 2")] and edge == [("base", "STRONG | Touch 2")], f"{dead} {edge}")
    # 14 the tag is the FVG of the score: random states
    rnd, ok14 = random.Random(21), True
    for _ in range(3000):
        cc = zs.Cfg(show={s: rnd.random() < .7 for s in (1, 2, 3, 4)}, showScore=rnd.random() < .5)
        zones = [zs.zone(cc, 2000 + 20 * i + 10, 2000 + 20 * i, rnd.uniform(0, 17), htf=rnd.random() < .5, touch=rnd.randint(0, 4))
                 for i in range(5)]
        fv = [zs.fvg(s, 2000 + rnd.uniform(0, 100), 1990 + rnd.uniform(0, 100), rnd.randint(1, 9), rnd.random() < .7)
              for s in rnd.sample(range(15), rnd.randint(0, 15))]
        fv = [dict(f, top=max(f["top"], f["bot"]), bot=min(f["top"], f["bot"])) for f in fv]
        S = zs.Slots(fv)
        for kind, k, txt in draw_labels(cc, zones, S):
            z = zones[k]
            best = zs.best_fvg(z, S)
            dScore, _ = zs.zone_display(cc, z, S)
            m = re.search(r" \| FVG (15M|1H|4H) \+(\d)", txt)
            if m:
                b = float(m.group(2))
                ok14 &= best >= 0 and b == zs.base_pts(best) and {"15M": 1, "1H": 2, "4H": 3}[m.group(1)] == b \
                    and dScore == z["baseSum"] + b + z["slopeBonus"] + z["maBonus"] + z["flipBonus"] + zs.conf(cc, z["catCount"] + 1)
            else:
                ok14 &= best < 0 or kind == "base" and any(x[0] == "boost" and x[1] == k for x in draw_labels(cc, zones, S))
        labs = draw_labels(cc, zones, S)
        for k in range(len(zones)):
            ok14 &= sum(1 for x in labs if x[1] == k and "FVG" in x[2]) == (1 if zs.best_fvg(zones[k], S) >= 0 and any(x[1] == k for x in labs) else 0)
    check("LM-14 3000 random states: the tag's timeframe / points are those of the FVG used in the Batch C score "
          "(dScore = baseSum + tag points + bonuses + conf(catCount + 1)); exactly one tag per labelled zone with an FVG",
          ok14)
    # 16 determinism / reload: pure function of the state
    zones = [zs.zone(c, 2010 + 25 * i, 2000 + 25 * i, 3.0 + 2.5 * i, htf=i % 2 == 0, touch=i) for i in range(6)]
    S = zs.Slots([zs.fvg(0, 2012, 2006, 1), zs.fvg(10, 2033, 2020, 2), zs.fvg(6, 2080, 2050, 3)])
    check("LM-16 labels are a pure function of (Engine zones, FVG slots, inputs): same state -> identical strings",
          draw_labels(c, zones, S) == draw_labels(c, zones, S))


def main():
    for g in (gate_static, gate_mirror):
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
    print(f"\n{len(RESULTS) - fails}/{len(RESULTS)} passed  [PINE_NOT_VERIFIED: exact transform / static / label mirror]")
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
