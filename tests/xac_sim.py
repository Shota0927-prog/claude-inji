"""XA-23 fixtures — confirmed labels on the Gold Strategies ZoneStrategyXAU.pine (Short) and ZoneStrategyXAULong.pine (Long)
(tests/xa_build.py STRATEGY_EDITS23, the same layer on both files; tests/xal_build.py).

  CS : static on both delivered files — exact build / strip (-> the XA-22 files of d05f8c9), other Pine files unchanged; one new
       input (確定ラベルを表示, ON) and every other default / strategy() setting kept; the confirmed-bar trading block identical
       apart from three label calls, each in the branch of a confirmed alert call with the same arguments (SATS pull, SATS
       immediate, Current A / B-D); no label on the wait prep / fills, no provisional label; the label switch and the alert
       switches / keys independent; dedup by order id in a var key; at most 50 labels; Long below / Short above, two colours
  CM : models — Pine var rollback / varip with label drawings: one label per order on re-executed realtime bars (none lost,
       none doubled), historical orders labelled, alert / label switches independent, 50 kept, the label text values
  CU : mutations — model mutations caught; source mutations do not strip back to d05f8c9

Evidence class: PINE_NOT_VERIFIED (TradingView compile, chart display and Strategy Tester results are not verified here).
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xa_build as xb            # noqa: E402
import xal_build as xl           # noqa: E402
import eu_sim as es              # noqa: E402

ROOT = xb.ROOT
PREV = "d05f8c9"                 # XA-22
raw = lambda p: __import__("msl_build").unapply(p, open(os.path.join(ROOT, p), encoding="utf-8").read())   # later MSL-1 reverted exactly (pinned in msl_sim)
code_only, input_values, input_decls, func = es.code_only, es.input_values, es.input_decls, es.func
S, L = raw(xb.STR_PATH), raw(xl.LONG_PATH)
S0, L0 = xb.show(PREV, xb.STR_PATH), xb.show(PREV, xl.LONG_PATH)
FILES = {"Short": (S, S0), "Long": (L, L0)}
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


def block(t, start, end):
    i = t.index(start)
    return t[i:t.index(end, i)]


MAIN_START, MAIN_END = "if is5mChart and barstate.isconfirmed\n    // (1)", "\nplot(stZones"
TEXT = ('f_stLblText(int side, float ePx, float sl, float tp, bool isLim, bool isSats) =>\n'
        '    float slW = side * (ePx - sl)\n'
        '    float tpW = side * (tp - ePx)\n'
        '    float rr  = not na(slW) and slW > 0 and not na(tpW) ? tpW / slW : na\n'
        '    "確定 " + (side == 1 ? "LONG" : "SHORT") +\n'
        '     "\\nEntry：" + f_stPx(ePx) + (isLim ? "（指値）" : "（成行・参考）") +\n'
        '     "\\nSL：" + f_stPx(sl) + "（" + (na(slW) ? "-" : f_stPx(slW) + "ドル") + "）" +\n'
        '     "\\n" + (isSats ? "TP" : "予定TP") + "：" + f_stPx(tp) + "（" + (na(tpW) ? "-" : f_stPx(tpW) + "ドル") + "）" +\n'
        '     "\\nRR：" + (na(rr) ? "-" : "1:" + str.tostring(rr, "0.00"))\n')
MK = "    bool mk = stLblConf and array.get(stLblEid, 0) != oEid\n"


def args(line, fn):
    return line.split("     //")[0].strip().split(fn + "(", 1)[1].rsplit(")", 1)[0]


# ---- static ------------------------------------------------------------------------------------------------------------
def gate_static():
    others = [p for p in os.listdir(ROOT) if p.endswith(".pine") and not __import__("acc_build").ok(p) and p not in (xb.STR_PATH, xl.LONG_PATH)]     # ACC-1 new files: exact
    check("CS-01 Short == xa_build.build_strategy() (XA-1 .. XA-23), strip_strategy23 gives the XA-22 Short of %s byte for byte; Long == "
          "xal_build.build(), strip23 gives the XA-22 Long of %s; the same XA-23 layer on both; every other Pine file unchanged" % (PREV, PREV),
          S == xb.build_strategy() and xb.strip_strategy23(S) == S0 and xb.build_strategy22() == S0
          and L == xl.build() and xl.strip23(L) == L0 and xl.build22() == L0 and not [p for p in others if __import__("btl_build").unapply(p, raw(p)) != xb.show(PREV, p)])   # later BTL-1 reverted exactly
    inp = {}
    for k, (t, t0) in FILES.items():
        iv, i0 = input_values(t), input_values(t0)
        d = {n: (i0.get(n), iv.get(n)) for n in set(iv) | set(i0) if iv.get(n) != i0.get(n)}
        c = code_only(t)
        pv = code_only(block(t, "// ---- XA-21 仮アラート", "// ==== ZONE Strategy · Zone evaluation (end)"))
        inp[k] = (d == {"stLblConf": (None, "true")} and '"確定ラベルを表示"' in input_decls(t)["stLblConf"]
                  and 'var string G_STL = "03 · Strategy Labels"' in t and es.seg(t, "strategy(", "import ") == es.seg(t0, "strategy(", "import ")
                  and c.count("label.new(") == 1 and "label." not in pv and "stLblProv" not in c and "stProvLbl" not in c)
    check("CS-02 one new input '確定ラベルを表示' (default ON, group 03 · Strategy Labels); every other input / default and strategy() "
          "unchanged in both files; one label.new (the confirmed label); the provisional block draws nothing (no provisional label)",
          all(inp.values()), str(inp))
    same = {}
    for k, (t, t0) in FILES.items():
        m, m0 = block(t, MAIN_START, MAIN_END), block(t0, MAIN_START, MAIN_END)
        ls = m.split("\n")
        al = [args(l, "f_stConfAlert") for l in ls if "f_stConfAlert(" in l]
        lb = [args(l, "f_stConfLabel") for l in ls if "f_stConfLabel(" in l]
        pairs_ok = True
        for i, l in enumerate(ls):
            if "f_stConfLabel(" in l:      # the label call sits in the same branch right after the alert call (+ the XA-22 release)
                ind = len(l) - len(l.lstrip())
                pairs_ok &= "f_stConfAlert(" in ls[i - 2] and "f_stPvRelease(" in ls[i - 1] and all(len(x) - len(x.lstrip()) == ind for x in ls[i - 2:i + 1])
        prep = block(m, "                if not skipRef and not na(pQty) and pwState == 0 and not pwCancelBar and not nowGo\n", "            else if not skipRef")
        fills = block(m, "    // (1)", "    // (3) ")
        same[k] = ("\n".join(l for l in ls if "f_stConfLabel(" not in l) == m0 and al == lb and len(lb) == 3 and pairs_ok
                   and "f_stConfLabel" not in prep + fills and m.count("strategy.entry(") == 4)
    check("CS-03 the confirmed-bar trading block is byte-identical to XA-22 apart from three label calls; each sits in the branch that "
          "executed strategy.entry, right after that branch's confirmed alert call, with the same arguments (SATS pull: close / SL0 / TP0; "
          "SATS immediate: close / SL0 / TP0; Current: A limit oL or B-D close / SL / planned TP); none on the wait prep or the fill / exit "
          "handling (no wait for the fill)", all(same.values()), str(same))
    ind = {}
    for k, (t, _) in FILES.items():
        fl = func(t, "f_stConfLabel(int side, float ePx, float sl, float tp, bool isLim, bool isSats) =>")
        fa = func(t, "f_stConfAlert(int side, float ePx, float sl, float tp, bool isLim, bool isSats) =>")
        c = code_only(t)
        ind[k] = (MK in fl and "    if mk\n        array.set(stLblEid, 0, oEid)\n" in fl
                  and not re.search(r"stAlert|gConfirmedAlertBar|gProv|alert\(", fl) and "stLblConf" not in fa
                  and 'var array<string> stLblEid   = array.new_string(1, "")' in t and "varip array<string> stLblEid" not in t
                  and "var array<label>  stConfLbls = array.new<label>()" in t and "int   ST_LBL_KEEP  = 50\n" in t
                  and "        if array.size(stConfLbls) > ST_LBL_KEEP\n            label.delete(array.shift(stConfLbls))\n" in fl
                  and "label.new(bar_index, side == 1 ? low : high, f_stLblText(side, ePx, sl, tp, isLim, isSats),\n" in fl
                  and "yloc = side == 1 ? yloc.belowbar : yloc.abovebar, color = side == 1 ? ST_LBL_LONG : ST_LBL_SHORT," in fl
                  and "style = side == 1 ? label.style_label_up : label.style_label_down" in fl
                  and "color ST_LBL_LONG  = color.new(color.teal, 0)" in t and "color ST_LBL_SHORT = color.new(color.maroon, 0)" in t
                  and TEXT in t and c.count("stLblConf") == 2 and c.count("stLblEid") == 3)
    check("CS-04 label switch and alert switches independent (the label function reads only stLblConf and its own key; the alert "
          "function does not read the label switch); one label per order id oEid in a `var` key (rolled back together with the "
          "drawing); latest 50 kept (oldest deleted); Long below the bar (teal, label up) / Short above (maroon, label down); text: "
          "確定 LONG／SHORT, Entry (指値 / 成行・参考), SL (width), TP or 予定TP for Current (width), RR from the shown prices, mintick digits",
          all(ind.values()), str(ind))


# ---- models ------------------------------------------------------------------------------------------------------------
def px(v):
    return "-" if v is None else f"{v:.2f}"


def lbl_text(side, e, sl, tp, lim, sats):
    """port of f_stLblText (CS-04 pins the Pine text)."""
    slw = None if None in (e, sl) else side * (e - sl)
    tpw = None if None in (e, tp) else side * (tp - e)
    rr = tpw / slw if slw is not None and slw > 0 and tpw is not None else None
    return ("確定 " + ("LONG" if side == 1 else "SHORT") + "\nEntry：" + px(e) + ("（指値）" if lim else "（成行・参考）")
            + "\nSL：" + px(sl) + "（" + ("-" if slw is None else px(slw) + "ドル") + "）"
            + "\n" + ("TP" if sats else "予定TP") + "：" + px(tp) + "（" + ("-" if tpw is None else px(tpw) + "ドル") + "）"
            + "\nRR：" + ("-" if rr is None else "1:" + f"{rr:.2f}"))


class Runtime:
    """Strategy instance: var state (incl. the label key and the drawings) rolled back unless committed; varip alert key kept."""

    def __init__(self, lbl_on=True, conf_on=True, variant=None):
        self.committed = dict(oSeq=0, eid_key="", labels=[])
        self.gConf = [-1]
        self.varip_eid = [""]
        self.lbl_on, self.conf_on, self.variant = lbl_on, conf_on, variant
        self.sent = []

    def labels(self):
        return self.committed["labels"]

    def close_bar(self, bar, order=None, commit=True, realtime=True):
        """order = (path, side, ePx, sl, tp, lim, sats) decided on this confirmed bar (None = no strategy.entry)."""
        st = dict(self.committed, labels=list(self.committed["labels"]))
        if order is not None:
            st["oSeq"] += 1
            eid = f"S{st['oSeq']}"                                            # oEid of this order (var)
            if self.conf_on and self.gConf[0] != bar:                         # XA-21 confirmed alert (varip key)
                self.gConf[0] = bar
                if realtime:
                    self.sent.append(bar)
            gate = (self.lbl_on and self.conf_on) if self.variant == "label_needs_alert" else self.lbl_on
            if self.variant == "varip_key":
                mk = gate and self.varip_eid[0] != eid
                if mk:
                    self.varip_eid[0] = eid
            else:
                mk = gate and st["eid_key"] != eid
                if mk:
                    st["eid_key"] = eid
            if self.variant == "no_key":
                mk = gate
            if mk:
                path, side, e, sl, tp, lim, sats = order
                st["labels"].append((bar, "below" if side == 1 else "above", lbl_text(side, e, sl, tp, lim, sats)))
                if len(st["labels"]) > 50 and self.variant != "no_cap":
                    st["labels"].pop(0)
            if self.variant == "no_key" and mk:
                st["labels"].append(st["labels"][-1])                         # a second call on the same order
        if commit:
            self.committed = st                                               # else: rolled back with its drawings
        return self


ORDERS = {"pull": ("pull", -1, 2650.25, 2655.75, 2642.00, False, True),
          "immediate": ("immediate", -1, 2603.00, 2610.00, 2585.00, False, True),
          "current A": ("current", 1, 2600.00, 2595.50, 2606.75, True, False),
          "current B-D": ("current", 1, 2610.40, 2604.90, 2618.65, False, False)}


def gate_model():
    per = {k: Runtime().close_bar(100, o).labels() for k, o in ORDERS.items()}
    check("CM-01 every order path (SATS pull, SATS immediate, Current A limit, Current B-D market) gives exactly one label on the "
          "decision bar with the confirmed alert's prices; Long below / Short above",
          all(len(v) == 1 and v[0][0] == 100 for v in per.values())
          and [v[0][1] for v in per.values()] == ["above", "above", "below", "below"])
    t = {k: v[0][2] for k, v in per.items()}
    check("CM-02 label values: SATS pull Short 2650.25 / SL0 2655.75 (5.50ドル) / TP0 2642.00 (8.25ドル) / RR 1:1.50; immediate Short close "
          "2603.00 (not P0) / 2610.00 (7.00ドル) / 2585.00 (18.00ドル) / RR 1:2.57; Current A Long limit 2600.00（指値） / 予定TP 2606.75 / "
          "1:1.50; Current B-D market（成行・参考） / 予定TP",
          t["pull"] == "確定 SHORT\nEntry：2650.25（成行・参考）\nSL：2655.75（5.50ドル）\nTP：2642.00（8.25ドル）\nRR：1:1.50"
          and t["immediate"] == "確定 SHORT\nEntry：2603.00（成行・参考）\nSL：2610.00（7.00ドル）\nTP：2585.00（18.00ドル）\nRR：1:2.57"
          and t["current A"] == "確定 LONG\nEntry：2600.00（指値）\nSL：2595.50（4.50ドル）\n予定TP：2606.75（6.75ドル）\nRR：1:1.50"
          and t["current B-D"].startswith("確定 LONG\nEntry：2610.40（成行・参考）") and "予定TP：2618.65（8.25ドル）" in t["current B-D"],
          "\n---\n".join(t.values()))
    r = Runtime()
    r.close_bar(100, ORDERS["pull"], commit=False).close_bar(100, ORDERS["pull"], commit=False).close_bar(100, ORDERS["pull"])
    check("CM-03 realtime recalculation of the confirmed bar (two rolled-back executions, then the final one): one label, not lost and "
          "not doubled; the confirmed alert once", len(r.labels()) == 1 and r.sent == [100])
    combos = {}
    for lo in (True, False):
        for co in (True, False):
            x = Runtime(lbl_on=lo, conf_on=co).close_bar(100, ORDERS["current A"])
            combos[(lo, co)] = (len(x.labels()), len(x.sent))
    check("CM-04 switches independent: label ON / alert OFF -> label only; label OFF / alert ON -> alert only; both ON -> both; both OFF -> none",
          combos == {(True, True): (1, 1), (True, False): (1, 0), (False, True): (0, 1), (False, False): (0, 0)}, str(combos))
    h = Runtime()
    for i in range(5):
        h.close_bar(10 + i, ORDERS["current B-D"], realtime=False)
    check("CM-05 historical orders are labelled (5 bars -> 5 labels) while no alert is sent on history", len(h.labels()) == 5 and h.sent == [])
    k = Runtime()
    for i in range(60):
        k.close_bar(100 + i, ORDERS["pull"])
    check("CM-06 the latest 50 labels are kept (60 orders -> 50, the oldest deleted)", len(k.labels()) == 50 and k.labels()[0][0] == 110)
    w = Runtime().close_bar(100, None).close_bar(101, None)
    check("CM-07 bars without strategy.entry (e.g. a wait prep only, or a fill) get no label", w.labels() == [])


def gate_mutation():
    rec = lambda v: Runtime(variant=v).close_bar(100, ORDERS["pull"], commit=False).close_bar(100, ORDERS["pull"]).labels()
    ind = Runtime(variant="label_needs_alert", conf_on=False).close_bar(100, ORDERS["pull"]).labels()
    cap = Runtime(variant="no_cap")
    for i in range(60):
        cap.close_bar(100 + i, ORDERS["pull"])
    check("CU-01 model mutations caught: a varip label key loses the label after a rolled-back execution, no key doubles it, a label "
          "gated by the alert switch disappears with the alert OFF, no cap keeps 60",
          rec("varip_key") == [] and len(Runtime(variant="no_key").close_bar(100, ORDERS["pull"]).labels()) == 2 and ind == []
          and len(cap.labels()) == 60 and len(rec(None)) == 1)
    muts = {"varip key": S.replace('var array<string> stLblEid   = array.new_string(1, "")', 'varip array<string> stLblEid   = array.new_string(1, "")'),
            "gated by alert": S.replace(MK, "    bool mk = stLblConf and stAlertConf and array.get(stLblEid, 0) != oEid\n"),
            "immediate label dropped": S.replace("                        f_stConfLabel(side, close, pSL, tpRef, false, true)", "                        // "),
            "P0 as Entry": S.replace("f_stConfLabel(pwSide, close, pwSL0, pwTP0, false, true)", "f_stConfLabel(pwSide, pwP0, pwSL0, pwTP0, false, true)"),
            "fixed RR": S.replace('    float rr  = not na(slW) and slW > 0 and not na(tpW) ? tpW / slW : na\n    "確定 "', '    float rr  = stRR\n    "確定 "'),
            "no cap": S.replace("        if array.size(stConfLbls) > ST_LBL_KEEP\n            label.delete(array.shift(stConfLbls))\n", "")}
    bad = [k for k, m in muts.items() if m == S or xb.strip_strategy23(m) == S0]
    check("CU-02 source mutations (varip label key, label gated by the alert switch, the immediate label dropped, P0 as the SATS Entry, "
          "the fixed RR, no cap) do not strip back to %s" % PREV, not bad, str(bad))


def main():
    for g in (gate_static, gate_model, gate_mutation):
        try:
            g()
        except Exception:
            import traceback
            check(f"{g.__name__} completed without error", False, traceback.format_exc()[-900:])
    fails = 0
    for nm, ok, d in RESULTS:
        fails += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {nm[:150].ljust(150)}  {'' if ok else d}")
    print(f"\n{len(RESULTS) - fails}/{len(RESULTS)} passed  [PINE_NOT_VERIFIED: exact build / static / Python models]")
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
