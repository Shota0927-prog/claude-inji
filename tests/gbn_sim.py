"""GBS-5 / GBS-6 fixtures — ZoneStrategyGBPJPY alert text and provisional / confirmed labels.

  GN : static — Strategy == gbs_build.build(); reverting the label and text edits gives c07a97a byte for byte (orders,
       sizes, SL / TP orders, entry conditions, alert conditions / frequency unchanged); Visual / Library / import /3,
       Gold, USDJPY unchanged; the text function (ticker | side, Entry, SL, SL距離 pips, TP, RR, provisional note; no Mode /
       lot / units / loss %); TP = the result of the existing pre-order f_stTp call (confirmed: tpRef of the order
       branch, provisional: the tp f_stProvEval computes); Entry = the existing notification price; the TP order is still
       placed after the fill; labels: inputs, max_labels_count, confirmed label in the order branch with the alert's
       arguments and the keep limit, one provisional label re-set only on realtime ticks from the provisional
       evaluation, independent of the alert switches and of the provisional alert's sent state; no request / zone loop /
       extra f_stTp; no trading state written by the alert / label code
  GM : models — Pine ports of f_stTp and of the text: Long / Short, fixed RR, zone TP, fallback, skip, RR formatting,
       invalid values, internal consistency of Entry / SL / TP / RR; the provisional label tick machine (valid -> update
       -> invalid -> valid -> confirmed tick, alert sent once while the label keeps updating, switches independent,
       nothing on history); confirmed labels (one per order, oldest removed beyond the keep count)

Evidence class: PINE_NOT_VERIFIED. TradingView compile, realtime alerts and label rendering external.
"""
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gbs_build as gs          # noqa: E402
import gbe_build as ge          # noqa: E402
import fvg_re10045_sim as fr    # noqa: E402

ROOT = gs.ROOT
PREV = "c07a97a"
rd = lambda p: open(os.path.join(ROOT, p), encoding="utf-8").read() if os.path.exists(os.path.join(ROOT, p)) else ""
show = lambda p, rev=PREV: subprocess.run(["git", "-C", ROOT, "show", f"{rev}:{p}"], capture_output=True, text=True).stdout
GBS, GBS0 = rd(gs.GBS_PATH), show(gs.GBS_PATH)
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


def code_only(src):
    return "\n".join(l for l in src.split("\n") if not l.lstrip().startswith("//"))


def func(src, head):
    i = src.index("\n" + head) + 1
    m = re.search(r"\n(?=\S)", src[i + len(head):])
    return src[i:i + len(head) + m.start() + 1]


PROTECTED = ["ZoneVisualGBPJPY.pine", "ZoneEnginePracticalGBPJPY.pine", "ZoneEnginePracticalSwingMax.pine",
             "ZoneVisualPractical.pine", "ZoneStrategyXAU.pine", "ZoneVisualUSDJPY.pine", "ZoneStrategyUSDJPY.pine"]
CONF_ARGS = 'f_stAlertMsg("確定", side, stModeA ? oL : close, oSL, tpRef)'
PROV_ARGS = 'f_stAlertMsg("仮", pSide, pPx, pSL, pTP)'


def gate_static():
    check("GN-01 Strategy == gbs_build.build() (rebuild identical); reverting the label and alert-text edits gives the "
          + PREV + " Strategy byte for byte (orders, sizes, SL / TP orders, entry and alert conditions unchanged); the "
          "GBS-5 text alone (labels reverted) also rebuilds", bool(GBS) and gs.build() == GBS
          and gs.strip_msg(GBS) == GBS0 and bool(GBS0) and gs.strip_lbl(GBS) is not None)
    d = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", PREV, "--"] + PROTECTED, capture_output=True, text=True)
    check("GN-02 Visual, Library (/3 source), shared /6, Gold and USDJPY unchanged vs " + PREV + "; import stays /3",
          d.returncode == 0 and d.stdout.strip() == "" and re.findall(r"^import .*$", GBS, re.M) == [ge.IMPORT_GBE.strip()],
          d.stdout)
    fn = func(GBS, "f_stAlertMsg(")
    check("GN-03 text: 【kind】ticker｜LONG/SHORT, Entry / SL / TP with format.mintick, SL距離 = risk / 0.01 in pips (0.0), "
          "RR = 1:(reward / risk) with up to 2 decimals, provisional note '※未確定：5分足確定時に不成立になる場合あり'; "
          "risk <= 0 or TP na -> '-'; no Entry Mode, lot, units or loss %",
          'f_stAlertMsg(string kind, int side, float ePx, float sl, float tp) =>' in fn
          and '"【" + kind + "】" + syminfo.ticker + "｜" + (side == 1 ? "LONG" : "SHORT")' in fn
          and '"\\nEntry：" + f_stPx(ePx)' in fn and '"\\nSL：" + f_stPx(sl)' in fn
          and 'str.tostring(risk / ST_PIP, "0.0") + " pips"' in fn and '"\\nTP：" + (okR ? f_stPx(tp) : "-")' in fn
          and '"1:" + str.tostring(rr, "0.##")' in fn and "float risk = side == 1 ? ePx - sl : sl - ePx" in fn
          and "(side == 1 ? tp - ePx : ePx - tp) / risk" in fn and '"\\n※未確定：5分足確定時に不成立になる場合あり"' in fn
          and "float ST_PIP = 0.01" in GBS and 'str.tostring(v, format.mintick)' in GBS
          and not re.search(r"stMode|Lot|qty|通貨|stLotUnits|損失", fn))
    pe = func(GBS, "f_stProvEval(")
    ob = GBS[GBS.index("            float  pQty = f_stQty(side, ref, pSL)"):GBS.index("    stPrev := cur\n")]
    co, co0 = code_only(GBS), code_only(GBS0)
    check("GN-04 TP source: confirmed alert / label take tpRef of the order branch's own f_stTp call (the RR pre-check), "
          "the provisional ones the tp of f_stProvEval's existing f_stTp call; no f_stTp call added; Entry = the existing "
          "notification price (A limit / B, C, D close); the TP order is still set only after the fill",
          "[skipRef, tpRef] = f_stTp(side, ref, pSL" in GBS and "if not skipRef and not na(pQty)\n" in ob
          and ob.count(CONF_ARGS) == 2 and "        tpP := tpRef\n" in pe and "    [side, ePx, sl, tpP]\n" in pe
          and co.count("f_stTp(") == co0.count("f_stTp(") == 4
          and "strategy.exit(oXid, oEid, stop = oSL)\n" in ob and "limit = oTP" in co and co.count("limit = oTP") == co0.count("limit = oTP"))
    pv = GBS[GBS.index("varip int stProvBar = na\n"):]
    check("GN-05 alert conditions / frequency unchanged: provisional = alert ON, 5M chart, unconfirmed tick, no order, "
          "session, not yet sent on this bar, a side and a valid size; the sent state is set before alert(); once per "
          "bar; confirmed in the order branch with freq_all",
          "bool  stPvGate = is5mChart and not barstate.isconfirmed and oState == 0 and stSessOK\n" in pv
          and "bool  stPvA    = stAlertProv and stPvGate and (na(stProvBar) or stProvBar != bar_index)\n" in pv
          and "bool  stPvOK   = pSide != 0 and not na(pvQty)\n" in pv
          and "if stPvA and stPvOK\n    stProvBar := bar_index\n    alert(" + PROV_ARGS + ", alert.freq_once_per_bar)\n" in pv
          and "if stAlertConf\n                    alert(" + CONF_ARGS + ", alert.freq_all)\n" in ob)
    inp = lambda n: (re.search(r"^" + n + r"\s*=\s*input\.\w+\((.*)$", GBS, re.M) or [None, ""])[1]
    lbl = pv[pv.index("if barstate.isrealtime\n"):]
    check("GN-06 labels: inputs 仮 ON / 確定 ON / keep 50 (1-200), max_labels_count 500; confirmed label made next to the "
          "confirmed alert in the order branch with the same arguments, Long below / Short above, oldest deleted beyond the "
          "keep count; provisional label: one var label re-set only on realtime ticks, shown while the provisional "
          "evaluation is valid, hidden otherwise (incl. the confirmed tick), independent of the alert switch and the sent "
          "state",
          inp("stLblProv").startswith("true,") and inp("stLblConf").startswith("true,")
          and inp("stLblKeep").startswith('50, "確定ラベル保持数", minval = 1, maxval = 200,')
          and "max_labels_count       = 500)" in GBS
          and "                if stLblConf" in ob and "label.new(bar_index, side == 1 ? low : high, " + CONF_ARGS in ob
          and "yloc = side == 1 ? yloc.belowbar : yloc.abovebar" in ob
          and "if array.size(stConfLbls) > stLblKeep\n                        label.delete(array.shift(stConfLbls))" in ob
          and "var label stProvLbl = label.new(" in GBS and co.count("label.new(") == 2
          and "bool  stPvL    = stLblProv and stPvGate\n" in pv and "stProvBar" not in "bool  stPvL    = stLblProv and stPvGate"
          and "    if stPvL and stPvOK\n" in lbl and "label.set_text(stProvLbl, " + PROV_ARGS + ")" in lbl
          and 'label.set_text(stProvLbl, "")' in lbl and "yloc.belowbar : yloc.abovebar" in lbl)
    req = lambda s: re.findall(r"request\.\w+\(.*$", code_only(s), re.M)
    cnt = lambda s, p: len(re.findall(p, code_only(s)))
    seg = code_only(GBS[GBS.index("varip int stProvBar = na\n"):])
    check("GN-07 lightweight and non-interfering: requests, zone loops, for-loops and plots unchanged; one f_stProvEval "
          "definition and one call; text built only inside alert() / the label branches; the provisional alert / label code writes only the "
          "sent state, its locals and the label (no strategy.* call, no Track / wait / order state); RE10045 lint clean",
          req(GBS) == req(GBS0) and all(cnt(GBS, p) == cnt(GBS0, p) for p in (r"zn\.zoneAt\(", r"\bfor\b", r"\bwhile\b",
                                                                          r"\bplot\("))
          and co.count("f_stProvEval() =>") == 1 and co.count("= f_stProvEval()") == 1 and co.count("f_stAlertMsg(") == 5
          and "strategy." not in seg and not re.search(r"\b(stUsed|stWaits|stPrev|oState|m1LastT|m1PrevC)\s*:=", seg)
          and not re.search(r"map\.put|array\.(push|set|remove|clear)\((stUsed|stWaits|stPrev)", seg)
          and fr.lint_eager_guards(co) == [])


# ---- models -------------------------------------------------------------------------------------------------------------
MINTICK, PIP = 0.001, 0.01


def f_tp(side, px, sl, edge, rr=1.2, tpzone=False, mn=1.0, mx=3.0):
    """port of f_stTp: [skip, tp]."""
    risk = side * (px - sl)
    tp = px + side * rr * risk
    skip = False
    if tpzone and edge is not None:
        rz = side * (edge - px) / risk
        if rz < mn:
            skip = True
        elif rz < mx:
            tp = edge
    return skip, tp


def fmt_px(v):
    return "-" if v is None else f"{round(v / MINTICK) * MINTICK:.3f}"


def fmt_rr(v):
    s = f"{round(v, 2):.2f}".rstrip("0").rstrip(".")
    return s


def msg(kind, side, e, sl, tp, ticker="GBPJPY"):
    """port of f_stAlertMsg."""
    risk = (e - sl) if side == 1 else (sl - e)
    ok = risk is not None and risk > 0
    rr = ((tp - e) if side == 1 else (e - tp)) / risk if ok and tp is not None else None
    return (f"【{kind}】{ticker}｜{'LONG' if side == 1 else 'SHORT'}"
            f"\nEntry：{fmt_px(e)}\nSL：{fmt_px(sl)}"
            f"\nSL距離：{(f'{risk / PIP:.1f} pips') if ok else '-'}"
            f"\nTP：{fmt_px(tp) if ok else '-'}"
            f"\nRR：{('1:' + fmt_rr(rr)) if rr is not None else '-'}"
            + ("\n※未確定：5分足確定時に不成立になる場合あり" if kind == "仮" else ""))


def parse(m):
    vals = dict(re.findall(r"\n(Entry|SL|TP)：([0-9.]+)", m))
    pips = re.search(r"SL距離：([0-9.]+) pips", m)
    rr = re.search(r"RR：1:([0-9.]+)", m)
    return {k: float(v) for k, v in vals.items()}, float(pips.group(1)), float(rr.group(1))


def gate_model():
    _, tp = f_tp(1, 210.000, 209.700, None)
    m = msg("確定", 1, 210.000, 209.700, tp)
    check("GM confirmed Long, fixed RR 1.2: the user's example exactly (Entry 210.000, SL 209.700, 30.0 pips, TP 210.360, "
          "RR 1:1.2)", m == "【確定】GBPJPY｜LONG\nEntry：210.000\nSL：209.700\nSL距離：30.0 pips\nTP：210.360\nRR：1:1.2", m)
    _, tps = f_tp(-1, 210.000, 210.300, None)
    ms = msg("仮", -1, 210.000, 210.300, tps)
    check("GM provisional Short: risk = SL - Entry, TP = Entry - risk x RR = 209.640, same items + the note",
          ms == "【仮】GBPJPY｜SHORT\nEntry：210.000\nSL：210.300\nSL距離：30.0 pips\nTP：209.640\nRR：1:1.2"
          "\n※未確定：5分足確定時に不成立になる場合あり", ms)
    cases = []
    for edge, exp in ((210.600, ("zone", 210.600, "2")), (210.240, ("skip", None, None)), (211.100, ("fixed", 210.360, "1.2")),
                      (210.375, ("zone", 210.375, "1.25")), (210.400, ("zone", 210.400, "1.33"))):
        skip, tpz = f_tp(1, 210.000, 209.700, edge, tpzone=True)
        got = ("skip", None, None) if skip else (("zone" if tpz == edge else "fixed"), round(tpz, 3),
                                                 parse(msg("確定", 1, 210.000, 209.700, tpz))[2])
        exp_rr = None if exp[2] is None else float(exp[2])
        cases.append((edge, got, exp, got[0] == exp[0] and (got[1] is None or abs(got[1] - exp[1]) < 1e-9)
                      and (exp_rr is None or got[2] == exp_rr)))
    check("GM zone TP (same f_stTp): RR 2.0 edge -> TP edge, 1:2; RR 0.8 -> skipped (no order, no alert); RR 3.67 >= Max -> "
          "fixed 1.2; RR formatting 1:1.25 / 1:1.33 (up to 2 decimals)", all(c[3] for c in cases), str(cases))
    bad = msg("確定", 1, 210.000, 210.000, 210.360) + msg("確定", 1, 210.000, 209.700, None)
    check("GM invalid values: risk <= 0 -> SL距離 / TP / RR '-'; TP na -> TP / RR '-' (no inf / nan / negative pips)",
          "SL距離：-" in bad and "TP：-" in bad and "RR：-" in bad and "nan" not in bad and "inf" not in bad)
    ok = True
    for side, e, sl in ((1, 210.000, 209.700), (-1, 190.155, 190.468), (1, 189.731, 189.444), (-1, 210.000, 210.091)):
        _, t = f_tp(side, e, sl, None)
        v, pips, rr = parse(msg("確定", side, e, sl, t))
        risk = side * (v["Entry"] - v["SL"])
        ok &= abs(pips - round(risk / PIP, 1)) < 1e-9 and abs(side * (v["TP"] - v["Entry"]) / risk - rr) < 0.006
    check("GM the text is internally consistent: SL距離 = |Entry - SL| / 0.01 and RR = reward / risk from the printed Entry / "
          "SL / TP (Long and Short, off-round prices)", ok)

    # provisional label tick machine (port of the GBS-6 block) -------------------------------------------------------
    def run(ticks, alert_on=True, label_on=True, realtime=True):
        prov_bar, sent, frames = None, [], []
        for bar, confirmed, side, e, sl, tp in ticks:
            gate = not confirmed
            need_a = alert_on and gate and (prov_bar is None or prov_bar != bar)
            need_l = label_on and gate
            ok = (need_a or need_l) and side != 0
            if need_a and ok:
                prov_bar = bar
                sent.append((bar, msg("仮", side, e, sl, tp)))
            if realtime:
                frames.append(msg("仮", side, e, sl, tp) if (need_l and ok) else "")
        return sent, frames
    T = [(1, False, 0, None, None, None), (1, False, 1, 210.0, 209.7, 210.36), (1, False, 1, 210.05, 209.7, 210.47),
         (1, False, 0, None, None, None), (1, False, 1, 210.02, 209.7, 210.404), (1, True, 1, 210.03, 209.7, 210.426)]
    sent, frames = run(T)
    check("GM provisional label: invalid -> hidden, valid -> shown, values update (the alert was sent once on the first "
          "valid tick and the label keeps updating), invalid -> hidden, valid again -> shown, confirmed tick -> hidden",
          len(sent) == 1 and frames[0] == "" and "Entry：210.000" in frames[1] and "Entry：210.050" in frames[2]
          and frames[3] == "" and "Entry：210.020" in frames[4] and frames[5] == "" and sent[0][1] == frames[1], str(frames))
    s_off, f_on = run(T, alert_on=False)
    s_on, f_off = run(T, label_on=False)
    _, f_hist = run([(b, True, s, e, l, t) for b, _, s, e, l, t in T], realtime=False)
    check("GM switches independent: alert OFF -> labels still shown; label OFF -> alert still sent, no label; historical "
          "bars -> no label calls at all", s_off == [] and f_on == frames and len(s_on) == 1 and all(f == "" for f in f_off)
          and f_hist == [])
    check("GM same evaluation -> same numbers: the provisional alert text equals the label text of that tick (both call "
          "f_stAlertMsg with the same arguments)", sent[0][1] == frames[1])

    keep, lbls, deleted = 50, [], []
    for k in range(60):                      # one confirmed order per bar at most (one order at a time)
        lbls.append(k)
        if len(lbls) > keep:
            deleted.append(lbls.pop(0))
    check("GM confirmed labels: one per order, 60 orders with keep 50 -> the latest 50 remain, the 10 oldest deleted in "
          "order", lbls == list(range(10, 60)) and deleted == list(range(10)))


def main():
    for g in (gate_static, gate_model):
        try:
            g()
        except Exception:
            import traceback
            check(f"{g.__name__} completed without error", False, traceback.format_exc()[-900:])
    fails = 0
    for n, ok, d in RESULTS:
        fails += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {n[:150].ljust(150)}  {'' if ok else d}")
    print(f"\n{len(RESULTS) - fails}/{len(RESULTS)} passed  [PINE_NOT_VERIFIED: exact build / static / model]")
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
