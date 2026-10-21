"""UJ-3 fixtures — ZoneStrategyUSDJPY Entry labels (provisional / confirmed) and the SL distance in the alert text.

  UL : static — Strategy == uj_build.build_strategy(); strip_strategy3 gives the UJ-2 Strategy (e1c3cea) byte for byte;
       the code delta is only max_labels_count, the label inputs / colours / label objects, the SL distance in
       f_stAlertMsg, the confirmed label next to the confirmed alert and the provisional block (evaluation shared by the
       alert and the label + the label update); the label layer equals the GBPJPY one (GBS-6) except the message
       arguments; alert conditions / frequencies / the provisional dedup state unchanged; Entry / SL / TP / qty / order
       code, f_stProvEval, f_stTp, f_stQty unchanged; Visual / Engine / other Pine files unchanged
  UM : models — the provisional alert firing (old vs new block, every gate combination over tick sequences), the label
       tick machine (realtime only, one provisional label, hidden when invalid / on the confirmed tick / OFF, confirmed
       label once per order with the keep limit, provisional alert does not suppress the confirmed one), LONG / SHORT
       colours / positions, the SL distance text (|Entry - SL| / 0.01, 0.0)
  UU : mutations — mirror and source mutations are caught

Evidence class: PINE_NOT_VERIFIED (TradingView compile, realtime alerts and label rendering are external).
"""
import itertools
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import uj_build as ub            # noqa: E402
import gbs_build as gs           # noqa: E402
import eu_sim as es              # noqa: E402
import fvg_re10045_sim as fr     # noqa: E402

ROOT = ub.ROOT
UJ2 = "e1c3cea"
PREV = "7363ef1"
rd = lambda p: open(os.path.join(ROOT, p), encoding="utf-8").read()
git = lambda *a: subprocess.run(["git", "-C", ROOT] + list(a), capture_output=True, text=True).stdout
code_only, input_decls, input_values, func = es.code_only, es.input_decls, es.input_values, es.func
S4 = rd(ub.STR_PATH)
S = ub.strip_strategy4(S4) or ""     # UJ-3 layer (UJ-4 TP / RR reverted exactly; pinned in ujt_sim)
S0 = git("show", f"{UJ2}:{ub.STR_PATH}")
GBS = rd("ZoneStrategyGBPJPY.pine")
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


def block(t, start, end):
    i = t.index(start)
    return t[i:t.index(end, i)]


def readonly(fn):
    """every := target of the function body is a local declared in it; no varip / strategy.* / alert / label call."""
    body = code_only(fn).split("\n", 1)[1]
    targets = set(re.findall(r"^\s*(\w+)\s*:=", body, re.M))
    declared = set(re.findall(r"^\s*(?:var\s+)?(?:float|int|bool|string|color|\w+(?:<\w+>)?)\s+(\w+)\s*=(?!=)", body, re.M))
    declared |= {v.strip() for tup in re.findall(r"^\s*\[([^\]]+)\]\s*=", body, re.M) for v in tup.split(",")}
    return bool(targets) and targets <= declared and not re.search(r"varip|strategy\.|alert\(|label\.", body)


def gate_static():
    check("UL-01 Strategy == uj_build.build_strategy() (UJ-1 + UJ-2 + UJ-3); strip_strategy3 gives the UJ-2 Strategy of "
          "e1c3cea byte for byte; the full chain strips to 3568c05; edit kinds header / label / msg only",
          ub.build_strategy3() == S and ub.strip_strategy3(S) == S0 and ub.build_strategy2() == S0
          and ub.strip_strategy(S4) == ub.base(ub.STR_PATH) and ub.strip_strategy3(S4) == S0
          and {k for k, _, _ in ub.STRATEGY_EDITS3} == {"header", "label", "msg"})
    removed = sorted(["default_qty_value      = 1)", "if stAlertProv and is5mChart and not barstate.isconfirmed and oState == 0 and stSessOK",
                      "if na(stProvBar) or stProvBar != bar_index", "[pSide, pPx, pSL] = f_stProvEval()", "if pSide != 0",
                      "stProvBar := bar_index", 'alert(f_stAlertMsg("仮", pSide, pPx, pSL), alert.freq_once_per_bar)'])
    ch = es.changed_code(S0, S)
    got = [l for l in removed if l in ch]
    added = list(ch)
    for l in removed:
        if l in added:
            added.remove(l)
    ok = (r"^default_qty_value      = 1,$|^max_labels_count       = 500\)$|^var string G_STL = |^stLbl(Prov|Conf|Keep) = input\.|^tooltip = "
          r"|^color ST_LBL_(PROV|LONG|SHORT)\s+= color\.new\(|^var array<label> stConfLbls = |^var label stProvLbl = label\.new\("
          r"|^float ST_PIP = 0\.01$|^float slPips = |^\"\\nSL距離: \" \+ |^if stLblConf|^array\.push\(stConfLbls, label\.new\("
          r"|^yloc = side == 1|^textcolor = color\.white|^if array\.size\(stConfLbls\) > stLblKeep$|^label\.delete\(array\.shift\(stConfLbls\)\)$"
          r"|^bool  stPv(Gate|A|L|OK)\s+= |^int   pSide    = 0$|^float p(Px|SL)\s+= na$|^if stPvA or stPvL$|^\[s0, e0, l0\] = f_stProvEval\(\)$"
          r"|^p(Side|Px|SL)\s+:= [sel]0$|^if stPvA and stPvOK$|^stProvBar := bar_index$|^alert\(f_stAlertMsg\(\"仮\", pSide, pPx, pSL\), alert\.freq_once_per_bar\)$"
          r"|^if barstate\.isrealtime$|^if stPvL and stPvOK$|^label\.set_\w+\(stProvLbl, |^else$")
    bad = [l for l in added if l and not re.search(ok, l)]
    check("UL-02 code delta vs e1c3cea only: max_labels_count 500, label inputs / colours / objects, ST_PIP + the SL距離 line, "
          "the confirmed label in the order branch, the provisional block (shared evaluation + label update); removed lines "
          "exactly the old provisional block and the strategy() closing line", got == removed and not bad,
          str((bad[:4], [l for l in removed if l not in got])))
    lbl_in = lambda t: block(t, 'var string G_STL = "03 · Strategy Labels"', "\n\n")
    gconf = block(GBS, "                if stLblConf", "    stPrev := cur")
    uconf = block(S, "                if stLblConf", "    stPrev := cur")
    gprov = block(GBS, "if barstate.isrealtime\n    if stPvL and stPvOK", "// ==== ZONE Strategy · Zone evaluation (end)")
    uprov = block(S, "if barstate.isrealtime\n    if stPvL and stPvOK", "// ==== ZONE Strategy · Zone evaluation (end)")
    check("UL-03 label layer == the GBPJPY Strategy (GBS-6): inputs (ON / ON / keep 50, tooltip names SL距離 instead of TP / RR), "
          "colours (provisional orange + black text, LONG teal / SHORT maroon + white text), label objects, confirmed label "
          "(belowbar + label_up for LONG at low, abovebar + label_down for SHORT at high, size small, keep limit) and the "
          "provisional label update are identical except the message arguments (USDJPY has no TP argument)",
          lbl_in(S) == lbl_in(GBS).replace("成立中は Entry / SL / TP / RR を更新し", "成立中は Entry / SL / SL距離を更新し")
          and uconf == gconf.replace("oSL, tpRef)", "oSL)") and uprov == gprov.replace("pSL, pTP)", "pSL)")
          and "max_labels_count       = 500)" in S and S.count("label.new(") == 2)
    msg = func(S, "f_stAlertMsg(string kind, int side, float ePx, float sl) =>")
    msg0 = func(S0, "f_stAlertMsg(string kind, int side, float ePx, float sl) =>")
    check("UL-04 alert text: one added line 'SL距離: x.x pips' with x = |Entry - SL| / 0.01 (ST_PIP 0.01, format 0.0, '-' when "
          "Entry / SL na) right after SL; every other line (【仮/確定 LONG/SHORT】, ticker, Mode, E (指値 / 参考), SL, note / TP "
          "line) unchanged",
          "float slPips = na(ePx) or na(sl) ? na : math.abs(ePx - sl) / ST_PIP" in msg
          and '"\\nSL距離: " + (na(slPips) ? "-" : str.tostring(slPips, "0.0") + " pips") +' in msg
          and msg.replace('    float slPips = na(ePx) or na(sl) ? na : math.abs(ePx - sl) / ST_PIP\n', "")
          .replace('     "\\nSL距離: " + (na(slPips) ? "-" : str.tostring(slPips, "0.0") + " pips") +\n', "") == msg0
          and "float ST_PIP = 0.01\nf_stAlertMsg(" in S)
    al = re.findall(r"^\s*alert\(.*$", S, re.M)
    al0 = re.findall(r"^\s*alert\(.*$", S0, re.M)
    br = block(S, "            if not skipRef and not na(pQty)\n", "    stPrev := cur")
    check("UL-05 alert conditions unchanged: the same two alert() calls / frequencies; confirmed alert still inside the order "
          "branch right after strategy.entry / strategy.exit under 'if stAlertConf'; provisional alert gated by stAlertProv, "
          "5M, unconfirmed tick, no order / position, session, once per bar (stProvBar), pSide != 0 — the same predicate as "
          "e1c3cea; the provisional state is not read by the order branch",
          [l.strip() for l in al] == [l.strip() for l in al0] and len(al) == 2
          and "strategy.exit(oXid, oEid, stop = oSL)\n                if stAlertConf\n                    alert(f_stAlertMsg(\"確定\"" in br
          and "bool  stPvGate = is5mChart and not barstate.isconfirmed and oState == 0 and stSessOK" in S
          and "bool  stPvA    = stAlertProv and stPvGate and (na(stProvBar) or stProvBar != bar_index)" in S
          and "bool  stPvOK   = pSide != 0\n" in S and "stProvBar" not in br and "stPv" not in br)
    keep = ("f_stProvEval() =>", "f_stTp(", "f_stQty(int side, float ref, float sl) =>", "f_stNearest(")
    req = lambda t: re.findall(r"request\.\w+\(", code_only(t))
    strat = lambda t: sorted(re.findall(r"strategy\.(?:entry|exit|close|cancel)\(.*$", code_only(t), re.M))
    check("UL-06 trading logic unchanged: f_stProvEval / f_stTp / f_stQty / f_stNearest identical; every strategy.entry / exit / "
          "close / cancel call identical; Zone / FVG / Entry A-D / BOS / SL / TP / RR / breakeven / sizing / session code "
          "(everything outside the listed display blocks) identical; f_stProvEval read-only (no :=, varip, strategy.*, alert, "
          "label); requests unchanged; calc_on_every_tick true kept",
          all(func(S, h) == func(S0, h) for h in keep) and strat(S) == strat(S0) and req(S) == req(S0)
          and readonly(func(S, "f_stProvEval() =>"))
          and "calc_on_every_tick     = true," in S
          and code_only(S[S.index("bool stModeA   ="):S.index("// ---- 仮 / 確定アラート (USDJPY)")])
          == code_only(S0[S0.index("bool stModeA   ="):S0.index("// ---- 仮 / 確定アラート (USDJPY)")])
          and all(fr.lint_eager_guards(code_only(t)) == [] for t in (S,)))
    mod = set(git("diff", "--name-only", PREV, "--").split()) | {l[3:] for l in git("status", "--porcelain").split("\n") if l.startswith("??")}
    mod -= {"tests/__pycache__/"}
    mod = {m for m in mod if not __import__("cad_adapt").ok(m, PREV)}     # CAD-1 (confirmed-alert dedup): exact
    allowed = {ub.STR_PATH, "tests/uj_build.py", "tests/uj_sim.py", "tests/ujl_sim.py", "tests/uj3_adapt.py", "tests/bte_sim.py",
               "tests/xa_sim.py", "tests/xae_sim.py", "tests/xa_build.py", "tests/ujt_sim.py"}
    others = [p for p in os.listdir(ROOT) if p.endswith(".pine") and p != ub.STR_PATH]
    check("UL-07 vs 7363ef1 only the USDJPY Strategy and the USDJPY generator / fixtures (+ the exact adaptation of four older "
          "fixtures) change; the USDJPY Visual / Engine and every other Pine file byte-identical",
          mod <= allowed and ub.STR_PATH in mod and not [p for p in others if rd(p) != git("show", f"{PREV}:{p}") and not __import__("cad_adapt").ok(p, PREV)],
          str(sorted(mod - allowed)))
    hdr = S[:S.index("//@version=5")]
    check("UL-08 header names UJ-3 as display / notification only (no logic change claim beyond that)",
          "UJ-3 (表示・通知のみ)" in hdr and "アラートの発火条件・頻度、Entry / SL / TP / 数量 / 注文・約定の処理は変えない。" in hdr)


# ---- models ------------------------------------------------------------------------------------------------------------
def prov_old(t, st):
    """e1c3cea provisional block for one tick t: returns (alert sent, new stProvBar)."""
    if t["alertProv"] and t["is5m"] and not t["confirmed"] and t["oState0"] and t["sess"]:
        if st is None or st != t["bar"]:
            if t["pSide"] != 0:
                return True, t["bar"]
    return False, st


def prov_new(t, st, variant=None):
    """UJ-3 provisional block: (alert sent, new stProvBar, label shown, label text side)."""
    gate = t["is5m"] and not t["confirmed"] and t["oState0"] and t["sess"]
    pa = t["alertProv"] and gate and (st is None or st != t["bar"] or variant == "no_dedup")
    pl = t["lblProv"] and gate
    side = t["pSide"] if (pa or pl) else 0
    ok = side != 0
    sent = False
    if pa and ok:
        st, sent = t["bar"], True
    shown = None
    if t["realtime"]:
        shown = (pl and ok) if variant != "keep_on_invalid" else (pl and ok) or t.get("prev_shown", False)
    return sent, st, shown, side


def gate_model():
    keys = ("alertProv", "lblProv", "is5m", "confirmed", "oState0", "sess", "realtime")
    bad = 0
    n = 0
    for combo in itertools.product((False, True), repeat=len(keys)):
        for side in (0, 1, -1):
            for seq_bars in ((5, 5, 6), (5, 6, 6)):
                st_o = st_n = None
                for b in seq_bars:
                    t = dict(zip(keys, combo), pSide=side, bar=b)
                    so, st_o = prov_old(t, st_o)
                    sn, st_n, _, _ = prov_new(t, st_n)
                    n += 1
                    bad += (so != sn) or (st_o != st_n)
    check(f"UM-01 provisional alert firing and dedup state identical to e1c3cea over every gate combination (alert / label "
          f"switches, 5M, confirmed tick, no order, session, realtime, LONG / SHORT / none) and bar sequences ({n} ticks); the "
          f"label switch never changes what is sent", bad == 0, str(bad))
    # tick machine: one bar of realtime ticks, then the confirmed tick with / without an order
    ticks = [dict(pSide=1), dict(pSide=1), dict(pSide=0), dict(pSide=1), dict(pSide=-1)]
    st, sent, shown = None, [], []
    for tk in ticks:
        t = dict(alertProv=True, lblProv=True, is5m=True, confirmed=False, oState0=True, sess=True, realtime=True, bar=10, **tk)
        s, st, sh, sd = prov_new(t, st)
        sent.append(s)
        shown.append((sh, sd if sh else 0))
    conf = dict(alertProv=True, lblProv=True, is5m=True, confirmed=True, oState0=True, sess=True, realtime=True, bar=10, pSide=-1)
    _, _, sh_c, _ = prov_new(conf, st)
    check("UM-02 provisional label within a bar: shown while valid (LONG), hidden on an invalid tick, shown again, follows a "
          "side change to SHORT; the alert is sent once (first valid tick) while the label keeps updating; hidden on the "
          "confirmed tick (no provisional label left next to the confirmed one)",
          sent == [True, False, False, False, False] and shown == [(True, 1), (True, 1), (False, 0), (True, 1), (True, -1)]
          and sh_c is False)
    hist = dict(alertProv=True, lblProv=True, is5m=True, confirmed=False, oState0=True, sess=True, realtime=False, bar=3, pSide=1)
    off = dict(hist, realtime=True, lblProv=False)
    check("UM-03 no provisional label on historical bars; label OFF hides it while the alert still fires",
          prov_new(hist, None)[2] is None and prov_new(off, None)[2] is False and prov_new(off, None)[0] is True)
    labels, keep = [], 3
    for k in range(5):
        labels.append(("conf", k))
        if len(labels) > keep:
            labels.pop(0)
    check("UM-04 confirmed labels: one per order (created in the order branch, not on the fill), oldest deleted beyond the keep "
          "count (keep 3, 5 orders -> orders 2, 3, 4 kept)", labels == [("conf", 2), ("conf", 3), ("conf", 4)])
    style = lambda side: ("teal" if side == 1 else "maroon", "belowbar" if side == 1 else "abovebar",
                          "label_up" if side == 1 else "label_down", "low" if side == 1 else "high")
    check("UM-05 LONG / SHORT: confirmed LONG teal below the bar (label_up at low), SHORT maroon above the bar (label_down at "
          "high); provisional orange, same positions — read from the Pine source",
          style(1) == ("teal", "belowbar", "label_up", "low") and style(-1) == ("maroon", "abovebar", "label_down", "high")
          and "color = side == 1 ? ST_LBL_LONG : ST_LBL_SHORT" in S and "yloc = side == 1 ? yloc.belowbar : yloc.abovebar" in S
          and "style = side == 1 ? label.style_label_up : label.style_label_down" in S
          and "label.new(bar_index, side == 1 ? low : high," in S
          and "label.set_xy(stProvLbl, bar_index, pSide == 1 ? low : high)" in S)
    pips = lambda e, sl: "-" if e is None or sl is None else f"{abs(e - sl) / 0.01:.1f}"
    cases = [((150.250, 150.000), "25.0"), ((150.000, 150.250), "25.0"), ((151.337, 151.192), "14.5"),
             ((149.999, 149.949), "5.0"), ((150.123, 150.123), "0.0"), ((None, 150.0), "-"), ((151.0, 150.88), "12.0")]
    check("UM-06 SL distance: |Entry - SL| / 0.01 with one decimal: 150.250 / 150.000 -> 25.0 (LONG and SHORT), 151.337 / "
          "151.192 -> 14.5, 149.999 / 149.949 -> 5.0, 151.000 / 150.880 -> 12.0, na -> '-' (provisional: forming-bar reference "
          "Entry from f_stProvEval; confirmed: the order reference stModeA ? oL : close)",
          all(pips(*c) == e for c, e in cases)
          and 'alert(f_stAlertMsg("確定", side, stModeA ? oL : close, oSL), alert.freq_all)' in S
          and "ePx := stModeA ? (side == 1 ? bpL : bpS) : close" in func(S, "f_stProvEval() =>"))
    t = dict(alertProv=True, lblProv=True, is5m=True, confirmed=False, oState0=True, sess=True, realtime=True, bar=7, pSide=1)
    s1 = prov_new(t, None)
    check("UM-07 the provisional alert does not suppress the confirmed one: the confirmed alert reads only stAlertConf inside "
          "the order branch (no provisional state), and the provisional state is per bar",
          s1[0] and s1[1] == 7 and "stProvBar" not in block(S, "            if not skipRef and not na(pQty)\n", "    stPrev := cur"))


def gate_mutation():
    m1 = any(prov_new(dict(alertProv=True, lblProv=True, is5m=True, confirmed=False, oState0=True, sess=True, realtime=True,
                           bar=5, pSide=1), 5, variant="no_dedup")[0] for _ in (0,))
    t_inv = dict(alertProv=True, lblProv=True, is5m=True, confirmed=False, oState0=True, sess=True, realtime=True, bar=5,
                 pSide=0, prev_shown=True)
    m2 = prov_new(t_inv, None, variant="keep_on_invalid")[2] is True
    check("UU-01 mirror mutations caught: dedup removed (a second alert in the same bar), label kept on an invalid tick",
          m1 and m2)
    muts = [S.replace("math.abs(ePx - sl) / ST_PIP", "math.abs(ePx - sl) / 0.001"),
            S.replace("bool  stPvA    = stAlertProv and stPvGate and (na(stProvBar) or stProvBar != bar_index)",
                      "bool  stPvA    = stAlertProv and stPvGate"),
            S.replace("color = side == 1 ? ST_LBL_LONG : ST_LBL_SHORT", "color = ST_LBL_LONG"),
            S.replace('                if stLblConf     // 確定ラベル', '                if stLblConf and stAlertConf     // 確定ラベル'),
            S.replace("float ST_PIP = 0.01", "float ST_PIP = 0.1")]
    check("UU-02 source mutations rejected by the exact strip: x10 pip, provisional dedup removed, one colour for both sides, "
          "confirmed label tied to the alert switch, wrong ST_PIP",
          all(m != S and ub.strip_strategy3(m) is None for m in muts))


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
    print(f"\n{len(RESULTS) - fails}/{len(RESULTS)} passed  [PINE_NOT_VERIFIED: exact build / static / Python models]")
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
