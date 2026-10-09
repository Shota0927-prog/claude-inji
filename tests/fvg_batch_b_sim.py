"""FVG Batch B fixtures — ZoneVisualPractical FVG independent-zone display.

Spec: FVG実装仕様書 v1.0 + A01 + A02, Batch B only (display; no score interaction).

  B1  static : Engine / SignalEngine / Strategy / Harness untouched, Batch A logic untouched, no new request,
               existing drawing untouched, FVG pool <= 15, no FVG-vs-FVG merge / score
  B2  mirror : colours, TF labels, Strength / State filters, showZones / showLabels / showScore / showDetailLbl,
               hidden after fill / expiry / cap, draw order, 15 max (driven by the Batch A mirror's store)
  B3  static : production part == d240ec0 with strict A / B marker handling, Batch A block == e390afc
  B4  static : no request, pool bounded, strings only when a label is drawn, Engine update count unchanged

Evidence class: PINE_NOT_VERIFIED (static checks and a Python mirror; TradingView rendering is external).
"""
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fvg_batch_a_sim as fa          # noqa: E402  (Batch A mirror: Store / mk_bars / run / TF_MS / T0)

ROOT = fa.ROOT
CUR = fa.CUR
BASE = fa.BASE
BATCH_A_REV = "e390afc"
A_BEGIN, A_END = "// ==== FVG Batch A (begin) ", "// ==== FVG Batch A (end) "
B_BEGIN, B_END = "// ==== FVG Batch B (begin) ", "// ==== FVG Batch B (end) "

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


code_only = fa.code_only


def cut(src, begin, end):
    nb = len(re.findall(r"(?m)^" + re.escape(begin), src))
    ne = len(re.findall(r"(?m)^" + re.escape(end), src))
    if nb != 1 or ne != 1 or src.count(begin) != 1 or src.count(end) != 1:
        return src, "", False
    i, j = src.index(begin), src.index(end)
    if not j > i or src[i - 2:i] != "\n\n":
        return src, "", False
    k = src.find("\n", j)
    k = len(src) if k < 0 else k + 1
    return src[:i - 1] + src[k:], src[i:k], True


import fvg_batch_c_build as cb          # noqa: E402
C_BEGIN, C_END = cb.C_BEGIN, cb.C_END


def split(src):
    """(production part, A block, B block, ok): exactly one A, C and B block in the order A < C < B."""
    marks = [A_BEGIN, A_END, C_BEGIN, C_END, B_BEGIN, B_END]
    if [src.count(m) for m in marks] != [1] * 6:
        return src, "", "", False
    pos = [src.index(m) for m in marks]
    if pos != sorted(pos):
        return src, "", "", False
    rest, blk_b, ok_b = cut(src, B_BEGIN, B_END)
    rest, _, ok_c = cut(rest, C_BEGIN, C_END) if ok_b else (src, "", False)
    prod, blk_a, ok_a = cut(rest, A_BEGIN, A_END) if ok_c else (src, "", False)
    return prod, blk_a, blk_b, ok_a and ok_b and ok_c


PROD, BLK_A, BLK_B, SPLIT_OK = split(CUR)
BC = code_only(BLK_B)
A_AT_E390 = subprocess.run(["git", "-C", ROOT, "show", f"{BATCH_A_REV}:ZoneVisualPractical.pine"],
                           capture_output=True, text=True).stdout

# RE10045 fix (the only permitted change to the Batch A block since e390afc): Pine v5 evaluates both operands of
# `or`, so the -1 sentinel test and the array.get on that index must sit in separate branches. Same slot choice.
RE10045_A_OLD = """                if not array.get(gFvgAlive, s)
                    if slot < 0
                        slot := s
                else if oldest < 0 or array.get(gFvgOpenT, s) < array.get(gFvgOpenT, oldest)
                    oldest := s
"""
RE10045_A_NEW = """                // Pine v5 は and / or の両辺を評価するため、-1 判定と array.get を同じ式に書かない
                if not array.get(gFvgAlive, s)
                    if slot < 0
                        slot := s
                else if oldest < 0
                    oldest := s
                else if array.get(gFvgOpenT, s) < array.get(gFvgOpenT, oldest)
                    oldest := s
"""
A_AT_E390_FIXED = A_AT_E390.replace(RE10045_A_OLD, RE10045_A_NEW) if A_AT_E390.count(RE10045_A_OLD) == 1 else ""


# ============================================================================
# B1 / B3 / B4 : static
# ============================================================================
def gate_static():
    check("B3-01 strict markers: one Batch A block, one Batch B block, A before B, each preceded by a blank line",
          SPLIT_OK and CUR.index(A_END) < CUR.index(B_BEGIN))
    import nr_s1_build as nb
    import nr_a1_build as na
    prod_n = nb.cut_block(na.strip_nra(PROD), nb.NRS_BEGIN, nb.NRS_END)
    check("B3-02 production part (file minus the NR-A1 / NR-S1 / A / C / B blocks, NR-A1 edits reverted) == d240ec0 with exactly the NR-S1 Swing #2 / #3 "
          "edits + Batch C draw-loop edits",
          SPLIT_OK and prod_n is not None and prod_n == nb.apply_nrs_edits(cb.apply_prod_edits(BASE)))
    _, a_e390, ok_e = split_a_only(A_AT_E390_FIXED)
    if not SPLIT_OK:
        raise ValueError("FVG markers invalid")
    check("B1-01 Batch A block byte-identical to e390afc + the RE10045 fix only (lifecycle semantics unchanged)",
          bool(A_AT_E390_FIXED) and ok_e and SPLIT_OK and BLK_A == a_e390)
    check("B3-03 Batch B block is the last block of the file (after A and C)",
          SPLIT_OK and CUR.endswith(BLK_B))
    eng = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", BATCH_A_REV, "--",
                          "ZoneEnginePractical.pine", "ZoneEnginePracticalAuthority.pine", "SignalEnginePractical.pine",
                          "PracticalZoneStrategy_LONG.pine", "PracticalZoneStrategy_SHORT.pine"]
                         + [f for f in os.listdir(ROOT) if f.startswith("Practical") and f.endswith("Harness.pine")],
                         capture_output=True, text=True).stdout.strip()
    check("B1-02 Engine / SignalEngine / Strategy / Harness / Authority source unchanged vs e390afc", eng == "", eng)
    check("B1-03 no request.* in the Batch B block (FVG draw adds no request)", not re.search(r"request\.\w+\(", BC))
    writes = re.findall(r"array\.(?:set|push|insert|remove|clear|shift|pop|fill)\((gFvg\w+)", BC)
    check("B1-04 Batch B never writes Batch A state (only its own gFvgBoxes / gFvgLabels pools)",
          set(writes) <= {"gFvgBoxes", "gFvgLabels"} and "gFvgNextExpire :=" not in BC
          and not re.search(r"\bgFvg(Top|Bot|Dir|OpenT|CloseT|Expire|Alive|LastKey)\s*:=", BC), str(set(writes)))
    check("B1-05 not connected to the Engine: no zn.update / zoneEng / zoneFeed / zoneCfg; only zn.strengthName (pure text)",
          not re.search(r"zoneEng|zoneFeed|zoneCfg", BC) and set(re.findall(r"\bzn\.(\w+)", BC)) == {"strengthName"})
    check("B1-06 FVG pool bounded: FVG_DRAW_MAX = 15, box push only when nFb < FVG_DRAW_MAX, label push only inside a drawn box; "
          "no delete", "int FVG_DRAW_MAX = 15" in BC and "if showIt and nFb < FVG_DRAW_MAX" in BC
          and BC.count("array.push(gFvgBoxes") == 1 and BC.count("array.push(gFvgLabels") == 1
          and BC.index("if showIt and nFb < FVG_DRAW_MAX") < BC.index("array.push(gFvgBoxes") < BC.index("array.push(gFvgLabels")
          and not re.search(r"\.delete\(", BC))
    check("B1-07 no FVG-vs-FVG merge / score: no comparison between two FVGs' top / bottom, no cluster",
          not re.search(r"array\.get\(gFvg(Top|Bot), \w+\)\s*[<>=]+\s*array\.get\(gFvg(Top|Bot)", BC) and "cluster" not in BC.lower())
    check("B1-08 existing Zone pool / maxZonesDraw not used by FVG drawing",
          not re.search(r"\bgBoxes\b|\bgLabels\b|maxZonesDraw", BC))
    check("B4-01 drawing only at barstate.islast on the 5M chart; label text built only inside showLabels for a drawn box",
          "if barstate.islast and is5mChart" in BC and BC.count("f_fvgLabelText(") == 2
          and BC.index("if showLabels") < BC.index("string txt = f_fvgLabelText(")
          and len(re.findall(r"^\S", BC.split("if barstate.islast and is5mChart")[1], re.M)) == 0)
    check("B4-02 no array allocation per bar (pools are var; ordering uses a 5-slot selection loop, no sort array)",
          all(l.lstrip().startswith("var array<") for l in BC.split("\n") if "array.new" in l)
          and "sort" not in BC and "array.copy" not in BC)
    check("B4-03 Engine update count unchanged (zn.update appears once in the whole file)", code_only(CUR).count("zn.update(") == 1)
    # strength rule mirrors Engine f_strengthOf exactly
    eng_src = open(os.path.join(ROOT, "ZoneEnginePractical.pine"), encoding="utf-8").read()
    ef = eng_src[eng_src.index("f_strengthOf(float score, bool hasHtf, ZoneCfg c) =>"):]
    ef = ef[:ef.index("\n\n")].split("\n", 1)[1].replace("c.", "")
    cc_ = code_only(CUR[CUR.index(C_BEGIN):CUR.index(C_END)])
    bf = cc_[cc_.index("f_fvcStrengthOf(float score, bool hasHtf) =>"):]
    bf = bf[:bf.index("\n\n")].split("\n", 1)[1]
    check("B2-00 FVG strength (Batch C f_fvcStrengthOf) body == Engine f_strengthOf body (thresholds / HTF requirement / "
          "downgrade), cfg fields -> the same Visual inputs; no second copy left in Batch B",
          ef == bf and "f_fvgStrengthOf" not in BC, f"\n{ef}\n{bf}")
    check("B2-00b FVG box / label styling uses the existing helpers and formulas (f_zoneColor Support / Resistance, f_zoneTransp, "
          "border = tr - 30, width 2 for >= STRONG, label colour bc + 20, white text, label_left, small)",
          all(x in BC for x in ("color bc = f_zoneColor(dir > 0 ? ST_SUPPORT : ST_RESIST)", "int   tr = f_zoneTransp(fs)",
                                "color bd = color.new(bc, math.max(tr - 30, 0))", "int   bw = fs >= SR_STRONG ? 2 : 1",
                                "color  lc  = color.new(bc, 20)", "style = label.style_label_left", "size = size.small",
                                "int xL = bar_index - zoneLeftBars", "int xR = bar_index + zoneRightBars")))


def split_a_only(src):
    rest, blk, ok = cut(src, A_BEGIN, A_END)
    return rest, blk, ok


# ============================================================================
# Python mirror of the Batch B draw pass
# ============================================================================
SR_WEAK, SR_MEDIUM, SR_STRONG, SR_VSTRONG = 1, 2, 3, 4
NAMES = {1: "WEAK", 2: "MEDIUM", 3: "STRONG", 4: "VERY STRONG"}
TFN = ["15M", "1H", "4H"]


def strength_of(score, has_htf, st):
    t = SR_WEAK if score < st["thrMedium"] else SR_MEDIUM if score < st["thrStrong"] else SR_STRONG if score < st["thrVStrong"] else SR_VSTRONG
    if t == SR_VSTRONG and st["requireHtf"] and not has_htf:
        t = SR_STRONG
    return t


DEFAULT = dict(thrMedium=5.0, thrStrong=10.0, thrVStrong=15.0, requireHtf=True, showZones=True, showLabels=True,
               showScore=False, showDetailLbl=False, showWeak=False, showMedium=False, showStrong=True, showVStrong=True,
               showSupport=True, showResistance=True,
               trWeak=90, trMedium=80, trStrong=68, trVStrong=55)


def draw(store, st):
    """Mirror of the Batch B block: returns the drawn list [(slot, colourRole, transp, borderWidth, text)]."""
    out = []
    if not st["showZones"]:
        return out
    for tf in range(3):
        base = tf * fa.SLOTS
        score = tf + 1.0
        fs = strength_of(score, False, st)
        prev = None
        for _ in range(fa.SLOTS):
            pick = -1
            for k in range(fa.SLOTS):
                s = base + k
                if store.alive[s]:
                    ot = store.openT[s]
                    if (prev is None or ot < prev) and (pick < 0 or ot > store.openT[pick]):
                        pick = s
            if pick < 0:
                break
            prev = store.openT[pick]
            d = store.dir[pick]
            show = {1: st["showWeak"], 2: st["showMedium"], 3: st["showStrong"], 4: st["showVStrong"]}[fs] and \
                (st["showSupport"] if d > 0 else st["showResistance"])
            if show and len(out) < 15:
                tr = {1: st["trWeak"], 2: st["trMedium"], 3: st["trStrong"], 4: st["trVStrong"]}[fs]
                txt = None
                if st["showLabels"]:
                    txt = f"{NAMES[fs]} | {TFN[tf]} FVG"
                    if st["showScore"]:
                        txt += f" | {score:g}"
                    if st["showDetailLbl"]:
                        txt += f"\n{'Bullish' if d > 0 else 'Bearish'} · {TFN[tf]} · formed {store.closeT[pick]}" \
                               f"\n{store.top[pick]} - {store.bot[pick]} · base {score:g}"
                out.append((pick, "Support" if d > 0 else "Resistance", tr, 2 if fs >= SR_STRONG else 1, txt))
    return out


def fvg_bars(tf_ms, n_fvg, bear=False, tail=40):
    """n_fvg FVGs of width 5 (non-overlapping triples); bear = exact price mirror (p -> 4000 - p) of the bull series."""
    seq = []
    for k in range(n_fvg):
        b = 2000 + k * 20
        seq += [(b, b - 5, b - 2), (b + 15, b - 1, b + 12), (b + 17, b + 5, b + 15)]
    last = 2000 + (n_fvg - 1) * 20
    # tail continues at the last FVG's level so the sequence -> tail transition forms no extra gap
    seq += fa.flat(tail, last + 10)
    if bear:
        seq = [(4000 - l, 4000 - h, 4000 - c) for h, l, c in seq]
    return fa.mk_bars(tf_ms, fa.T0, seq)


def store_with(n15=0, n60=0, n240=0, bear15=False, n5=None):
    h = [fvg_bars(fa.TF_MS[0], n15, bear15) if n15 else fa.mk_bars(fa.TF_MS[0], fa.T0, fa.flat(200)),
         fvg_bars(fa.TF_MS[1], n60) if n60 else fa.mk_bars(fa.TF_MS[1], fa.T0, fa.flat(60)),
         fvg_bars(fa.TF_MS[2], n240) if n240 else fa.mk_bars(fa.TF_MS[2], fa.T0, fa.flat(20))]
    n = n5 if n5 is not None else max(3 * (3 * max(n15, 1) + 1), 12 * (3 * max(n60, 1) + 1), 48 * (3 * max(n240, 1) + 1)) + 1
    return fa.run(h, fa.T0, n), h


def gate_mirror():
    st, h = store_with(n15=2, n60=1, n240=1)
    allw = dict(DEFAULT, showWeak=True)
    d = draw(st, allw)
    check("B2-01 bullish FVG -> Support colour, bearish -> Resistance colour",
          all(r == "Support" for _, r, _, _, _ in d)
          and all(r == "Resistance" for _, r, _, _, _ in draw(store_with(n15=2, bear15=True)[0], allw)))
    check("B2-02 TF labels WEAK | 15M FVG / WEAK | 1H FVG / WEAK | 4H FVG (default thresholds, base 1 / 2 / 3)",
          [t for *_, t in d] == ["WEAK | 15M FVG", "WEAK | 15M FVG", "WEAK | 1H FVG", "WEAK | 4H FVG"], str([t for *_, t in d]))
    check("B2-03 default filter (Show Weak OFF): every FVG is WEAK -> nothing drawn (state is kept)",
          draw(st, DEFAULT) == [] and len(st.alive_set()) == 4)
    thr = dict(allw, showMedium=True, thrMedium=2.0, thrStrong=3.0, thrVStrong=3.0)
    dt = draw(st, thr)
    check("B2-04 Strength from base score with the existing thresholds: thrMedium 2 / thrStrong 3 / thrVStrong 3 -> "
          "15M WEAK, 1H MEDIUM, 4H STRONG (Very Strong capped: FVG has no HTF in Batch B); transparency / width follow",
          [t.split(" | ")[0] for *_, t in dt] == ["WEAK", "WEAK", "MEDIUM", "STRONG"]
          and [(tr, bw) for _, _, tr, bw, _ in dt] == [(90, 1), (90, 1), (80, 1), (68, 2)])
    check("B2-05 Strength filter: Show Medium only -> only the 1H FVG",
          [t for *_, t in draw(st, dict(thr, showWeak=False, showMedium=True, showStrong=False, showVStrong=False))]
          == ["MEDIUM | 1H FVG"])
    stb, _ = store_with(n15=2, bear15=True)
    check("B2-06 State filter: Show Resistance OFF hides bearish FVGs; Show Support OFF hides bullish FVGs",
          draw(stb, dict(allw, showResistance=False)) == [] and draw(st, dict(allw, showSupport=False)) == []
          and len(draw(stb, dict(allw, showSupport=False))) == 2)
    check("B2-07 showZones OFF -> no FVG box / label", draw(st, dict(allw, showZones=False)) == [])
    dl = draw(st, dict(allw, showLabels=False))
    check("B2-08 showLabels OFF -> boxes drawn, no label text", len(dl) == 4 and all(t is None for *_, t in dl))
    ds = draw(st, dict(allw, showScore=True))
    check("B2-09 showScore ON -> base score appended (1 / 2 / 3)",
          [t for *_, t in ds] == ["WEAK | 15M FVG | 1", "WEAK | 15M FVG | 1", "WEAK | 1H FVG | 2", "WEAK | 4H FVG | 3"])
    dd = draw(st, dict(allw, showDetailLbl=True))
    check("B2-10 showDetailLbl ON -> direction / TF / formation close time / top - bottom / base",
          all(("Bullish" in t and " · formed " in t and " - " in t and " · base " in t) for *_, t in dd)
          and all(x in BC for x in ('(dir > 0 ? "Bullish" : "Bearish")', '" · formed " + str.format_time(closeT',
                                     'str.tostring(top, format.mintick) + " - " + str.tostring(bot, format.mintick)',
                                     '" · base " + f_num(tfIdx + 1.0, "#.#")', '" · zone " + (na(zoneBase) ? "-" : f_num(zoneBase, "#.#"))',
                                     '" · conf " + f_num(conf, "#.#")')))
    # hidden after fill / expiry / cap
    h15 = fa.mk_bars(fa.TF_MS[0], fa.T0, [(2000, 1995, 1998), (2010, 1999, 2008), (2012, 2005, 2010), (2010, 1990, 1990)] + fa.flat(20, 2010))
    hs = [h15, fa.mk_bars(fa.TF_MS[1], fa.T0, fa.flat(10)), fa.mk_bars(fa.TF_MS[2], fa.T0, fa.flat(5))]
    check("B2-11 after a full fill the FVG is no longer drawn (drawn before the fill)",
          len(draw(fa.run(hs, fa.T0, 12), allw)) == 1 and draw(fa.run(hs, fa.T0, 13), allw) == [])
    he = [fa.mk_bars(fa.TF_MS[0], fa.T0, [(2000, 1995, 1998), (2010, 1999, 2008), (2012, 2005, 2010)] + fa.flat(400, 2010)),
          fa.mk_bars(fa.TF_MS[1], fa.T0, fa.flat(200)), fa.mk_bars(fa.TF_MS[2], fa.T0, fa.flat(60))]
    exp_n = (he[0][2]["tc"] + 72 * fa.HOUR - fa.T0) // 300_000
    check("B2-12 after expiry the FVG is no longer drawn (drawn one 5M bar before)",
          len(draw(fa.run(he, fa.T0, exp_n - 1), allw)) == 1 and draw(fa.run(he, fa.T0, exp_n), allw) == [])
    s6, h6 = store_with(n15=6)
    d6 = draw(s6, allw)
    check("B2-13 after the cap evicts the oldest, only the 5 kept FVGs are drawn (the evicted one is not)",
          len(d6) == 5 and h6[0][2]["t"] not in [s6.openT[p] for p, *_ in d6])
    so, ho = store_with(n15=3, n60=2, n240=2)
    do = draw(so, allw)
    keys = [(p // fa.SLOTS, so.openT[p]) for p, *_ in do]
    check("B2-14 draw order 15M -> 1H -> 4H, newest formation first within a TF",
          keys == sorted(keys, key=lambda x: (x[0], -x[1])) and [k[0] for k in keys] == [0, 0, 0, 1, 1, 2, 2])
    sm, _ = store_with(n15=5, n60=5, n240=5)
    dm = draw(sm, allw)
    check("B2-15 maximum 15 FVG boxes (5 per TF all drawn)", len(dm) == 15 and len(sm.alive_set()) == 15)
    dfil = draw(sm, dict(thr, showWeak=False))
    check("B2-16 filtered FVGs do not consume the 15 slots (15M hidden -> 10 drawn, all 1H / 4H)",
          len(dfil) == 10 and all(p // fa.SLOTS > 0 for p, *_ in dfil))
    snap = (list(sm.alive), list(sm.top), list(sm.openT), sm.nextExpire, list(sm.lastKey))
    for cfg in (allw, DEFAULT, dict(allw, showZones=False), thr):
        draw(sm, cfg)
    check("B2-17 drawing never changes the Batch A store (filters do not affect storage / fill / expiry)",
          snap == (list(sm.alive), list(sm.top), list(sm.openT), sm.nextExpire, list(sm.lastKey)))
    check("B2-18 Pine draw pass mirrors the selection loop (alive, open time strictly older than the previous pick, newest first)",
          "if na(prevT) or ot < prevT\n                            if pick < 0\n                                pick := s\n"
          "                            else if ot > array.get(gFvgOpenT, pick)\n                                pick := s" in BC
          and "bool showIt = f_fvgShowByStrength(fs) and (dir > 0 ? showSupport : showResistance)" in BC
          and "[fvgScore, fs, fZoneBase, fConf] = f_fvcFvgDisplay(pick)" in BC
          and BC.index("int dir = array.get(gFvgDir, pick)") < BC.index("f_fvcFvgDisplay(pick)") < BC.index("bool showIt")
          and "for tf = 0 to 2" in BC and "if showZones" in BC)
    check("B2-19 surplus pool objects are hidden (transparent box / empty transparent label), never deleted",
          all(x in BC for x in ("box.set_bgcolor(b, C_HIDDEN)", "box.set_border_color(b, C_HIDDEN)",
                                 'label.set_text(lb, "")', "label.set_color(lb, C_HIDDEN)")))


def main():
    for gate in (gate_static, gate_mirror):
        try:
            gate()
        except Exception as ex:          # a broken file must report FAIL, never pass silently
            check(f"{gate.__name__} completed without error", False, repr(ex))
    w = max(len(n) for n, _, _ in RESULTS)
    fails = 0
    for n, ok, d in RESULTS:
        fails += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {n.ljust(w)}  {d if not ok else ''}")
    print(f"\n{len(RESULTS) - fails}/{len(RESULTS)} passed  [PINE_NOT_VERIFIED: static / mirror checks]")
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
