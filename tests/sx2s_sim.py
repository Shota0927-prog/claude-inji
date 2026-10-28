"""SX-2 fixtures — the final Gold XA-16 .. XA-19 SATS timing features rolled out to the BTCUSD / USDJPY / GBPJPY / EURUSD / GBPUSD
Strategies (tests/sx2_build.py).

  SY : static on the five delivered Strategies — == sx2_build.build(); strip gives the 32cc570 (= SX-1) files byte for byte;
       Gold / Engines / Visuals / every other Pine file unchanged; strategy() / import / calc_on_every_tick / requests unchanged;
       the five new inputs and their defaults; every old default kept; old code changed only at the hook lines; the ported
       code == Gold XA-19 apart from the stated per-symbol differences (near price distance, confirmed-bar history writes with
       a current-bar-first pick, the confirmed alert / label on the immediate order, the provisional coverage); Current and the
       OFF paths unchanged; read-only provisional evaluation
  SZ : models — Nc / Nz / pull-N rules (the Gold models reused), the current-bar-first pick equal to Gold's push-then-pick,
       provisional == confirmed on the final OHLC without state writes (wait with the contact expiry, immediate before a wait),
       the size gate per symbol
  SQ : mutations rejected by the exact strip

Evidence class: PINE_NOT_VERIFIED (TradingView compile, Strategy Tester results and realtime alerts are not verified here).
"""
import math
import os
import random
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sx2_build as s2           # noqa: E402
import sx_build as sx            # noqa: E402
import eu_sim as es              # noqa: E402
import xas_sim as xs             # noqa: E402

ROOT = s2.ROOT
B = s2.BASE_REV
raw = lambda p: open(os.path.join(ROOT, p), encoding="utf-8").read()
code_only, input_values, input_decls, func = es.code_only, es.input_values, es.input_decls, es.func
CUR = {k: __import__("btl_build").unapply(p, raw(p)) for k, p in s2.PATHS.items()}     # later BTL-1 (BTCUSD defaults) reverted exactly
BASE = {k: s2.show(B, p) for k, p in s2.PATHS.items()}
GOLD = s2.gold()
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


def block(t, start, end):
    i = t.index(start)
    return t[i:t.index(end, i)]


NEW = {"stSatsNow": "false", "stSatsNowC": "1", "stSatsNowN": "1", "stSatsTq": "false", "stSatsTqN": "1"}
HOOKS = sorted(["bool rebB      = pwTouched and inRange and (pwSide == 1 ? (pc <= lp and close > lp) : (pc >= lp and close < lp))",
                "pwNTouchPrep += 1", "if not skipRef and not na(pQty) and pwState == 0 and not pwCancelBar",
                'plot(stSats ? pwEv : na,                   "SATS · イベント (1 準備 / 2 発注 / -1 期限 / -4 SL0)", display = display.data_window)'])


def gate_static():
    others = [p for p in os.listdir(ROOT) if p.endswith(".pine") and p not in s2.FILES and not __import__("xal_build").ok(p)]
    check("SY-01 the five Strategies == sx2_build.build() and strip back to the 32cc570 files (= the SX-1 files of b59d621) byte for "
          "byte; Gold, Engines, Visuals and every other Pine file byte-identical to 32cc570; strategy() (calc_on_every_tick = true), "
          "the import line and the request count unchanged",
          all(CUR[k] == s2.build(p) and s2.strip(p, CUR[k]) == BASE[k] and s2.unapply(p, CUR[k]) == BASE[k] and BASE[k] == s2.show("b59d621", p)
              for k, p in s2.PATHS.items())
          and not [p for p in others if __import__("xa_build").unapply24(p, raw(p)) != s2.show(B, p)     # XA-24 (later): exact
                   and not (p == s2.GOLD_PATH and __import__("xa_build").strip_strategy20(raw(p)) == s2.show(B, p))]   # Gold: later XA-20 exactly
          and all(es.seg(CUR[k], "strategy(", "import ") == es.seg(BASE[k], "strategy(", "import ") and "calc_on_every_tick     = true," in CUR[k]
                  and re.findall(r"^import .*$", CUR[k], re.M) == re.findall(r"^import .*$", BASE[k], re.M)
                  and CUR[k].count("request.") == BASE[k].count("request.") for k in CUR))
    bad = {}
    for k in CUR:
        iv, ib, d = input_values(CUR[k]), input_values(BASE[k]), input_decls(CUR[k])
        new = {n: v for n, v in iv.items() if n not in ib}
        if new != NEW or any(iv[n] != v for n, v in ib.items()) or not all(
                es.kw(d[n], "minval") == "0" and es.kw(d[n], "step") == "1" for n in ("stSatsNowC", "stSatsNowN", "stSatsTqN")):
            bad[k] = new
    gl = {n: input_decls(GOLD)[n].split(",")[1] for n in NEW}
    check("SY-02 inputs: the five new ones (即時 OFF, 即時 接触→反発 1, 即時 反発→Zone 1, 引きつけ 接触期限 OFF, 引きつけ 接触→反発 1; counts "
          "int / min 0 / step 1) with the Gold names; every old input default of each symbol unchanged (no Gold value copied)",
          not bad and all(input_decls(CUR[k])[n].split(",")[1] == gl[n] for k in CUR for n in NEW), str(bad))
    deltas = {}
    for k in CUR:
        cur_lines = set(x.strip() for x in code_only(CUR[k]).split("\n"))
        base_lines = set(x.strip() for x in code_only(BASE[k]).split("\n"))
        deltas[k] = sorted(l for l in base_lines - cur_lines if l)
    keep = ("f_stQty(int side, float ref, float sl) =>", "f_stTp(", "f_stProvEval() =>", "f_stInSession(int t) =>", "f_stAlertMsg(",
            "f_satBand() =>", "f_satPick(", "f_satRR(", "f_beTrig(", "f_satTfState() =>", "f_satAllAgainst(int want) =>")
    check("SY-03 old code changed only at the hook lines (provisional: touch flag / B with the contact expiry; the wait's touch count; the "
          "prep gate + and not nowGo; the event plot title + 3 即時); the size / TP / provisional / session / message / SATS functions "
          "identical in every symbol",
          all(d == HOOKS for d in deltas.values()) and all(func(CUR[k], h) == func(BASE[k], h) for k in CUR for h in keep if ("\n" + h) in BASE[k]),
          str({k: d for k, d in deltas.items() if d != HOOKS}))
    strip_c = lambda s: re.sub(r"(?<=\S) {2,}", " ", re.sub(r"\s+//.*", "", code_only(s)))
    eq = {}
    for k in CUR:
        t = CUR[k]
        nb = block(t, "                // XA-16: 直近の反発で即時エントリー", "                if not skipRef and not na(pQty) and pwState == 0 and not pwCancelBar and not nowGo\n")
        nb_g = block(GOLD, "                // XA-16: 直近の反発で即時エントリー", "                if not skipRef and not na(pQty) and pwState == 0 and not pwCancelBar and not nowGo\n")
        nb_wo = re.sub(r"\n                        if stAlertConf and .*?label\.delete\(array\.shift\(stConfLbls\)\)", "", nb, flags=re.S)
        exp = block(t, "            // XA-17: 引きつけ側の接触期限 (ON のとき)", "            int   lk = 0\n")
        exp_g = block(GOLD, "            // XA-17: 引きつけ側の接触期限 (ON のとき)", "            int   lk = 0\n")
        eq[k] = (func(t, "f_satHist(int side, float L, int q) =>") == func(GOLD, "f_satHist(int side, float L, int q) =>").replace("stSatsNearD", "stSatsNearPx"),
                 func(t, "f_hPrune(") == func(GOLD, "f_hPrune(") and func(t, "f_hPick(") == func(GOLD, "f_hPick("),
                 strip_c(nb_wo) == strip_c(nb_g), exp == exp_g,
                 "                pwNTouchPrep += pwTouchSeen ? 0 : 1\n                pwTouchSeen  := true\n" in t and "                    pwTouchSeen := false\n" in t,
                 "                    oTP0    := pwTP0\n                    oPath   := 1\n" in t)
    check("SY-04 ported code == Gold XA-19: f_satHist (only stSatsNearD -> the symbol's stSatsNearPx), f_hPrune / f_hPick, the immediate block "
          "(apart from the added confirmed alert / label and comments), the pull-side expiry block, the per-prep touch flag, the wait path "
          "marker; stated differences: near price distance, confirmed-bar history writes + current-bar-first pick, immediate confirmed "
          "alert / label, provisional coverage",
          all(all(v) for v in eq.values()), str(eq))
    gate = {}
    for k in CUR:
        t = CUR[k]
        g = block(t, "if barstate.isconfirmed\n    hTqL1 := nL1\n", "[pQL, pEL, pKL] = f_hPick(")
        hist = block(t, "// XA-16 / XA-17: 準備前の SATS 反発の履歴", "[pQL, pEL, pKL] = f_hPick(")
        outside = hist.replace(g, "")
        gate[k] = (len(re.findall(r"^\s*hTq\w+\s*:=", t, re.M)) == 6 == len(re.findall(r"^\s*hTq\w+\s*:=", g, re.M))
                   and t.count("array.push(hQs") + t.count("array.push(hEs") + t.count("array.push(hKs") == 18 == g.count("array.push(h")
                   and t.count("f_hPrune(h") == 2 == g.count("f_hPrune(h")
                   and "int  hEL = hNowL ? bar_index : pEL" in t and "int  hQL = hNowL ? (hL1 ? qL1 : hL2 ? qL2 : qL3) : pQL" in t
                   and "int  hKL = hNowL ? (hL1 ? 1 : hL2 ? 2 : 3) : pKL" in t and "int  hES = hNowS ? bar_index : pES" in t)
    check("SY-05 calc_on_every_tick: the history state (contact records hTq*, candidate arrays: push / prune) is written only inside "
          "'if barstate.isconfirmed' (forming ticks only read it; no reliance on rollback, no double write per bar); the pick takes "
          "the forming / current bar's rebound first (LINE1 -> LINE2 -> STB), else the latest committed candidate",
          all(gate.values()), str(gate))
    iso = {}
    for k in CUR:
        t, b = CUR[k], BASE[k]
        prep = block(t, "                if not skipRef and not na(pQty) and pwState == 0 and not pwCancelBar and not nowGo\n", "            else if not skipRef")
        prep_b = block(b, "                if not skipRef and not na(pQty) and pwState == 0 and not pwCancelBar\n", "            else if not skipRef")
        cur_order = block(t, "            else if not skipRef and not na(pQty)\n", "    stPrev := cur")
        cur_order_b = block(b, "            else if not skipRef and not na(pQty)\n", "    stPrev := cur")
        prov_cur = block(t, "if (stPvA or stPvL) and not stSats\n", "bool  stPvOK")
        prov_cur_b = block(b, "if (stPvA or stPvL) and not stSats\n", "bool  stPvOK")
        iso[k] = (prep.split("\n", 1)[1] == prep_b.split("\n", 1)[1].replace(
                      "                    pwTouched  := false     // 新しい準備は接触待ちから\n",
                      "                    pwTouched  := false     // 新しい準備は接触待ちから\n                    pwTouchSeen := false\n"),
                  cur_order == cur_order_b, prov_cur == prov_cur_b,
                  "                if stSatsNow and not skipRef and not na(pQty) and pwState == 0 and not pwCancelBar\n" in t,
                  "            if stSatsTq and pwTouched and bar_index - pwTouchBar > stSatsTqN\n" in t)
    check("SY-06 OFF paths: immediate OFF -> nowGo stays false and the prep is the SX-1 prep (+ the per-prep touch flag reset); pull expiry "
          "OFF -> the SX-1 wait (the touch count stays one per prep); the Current order branch and the Current provisional path are "
          "byte-identical; all new order logic is under stSats",
          all(all(v) for v in iso.values()), str(iso))
    al = {}
    for k in CUR:
        t = CUR[k]
        nb = block(t, "                // XA-16: 直近の反発で即時エントリー", "                if not skipRef and not na(pQty) and pwState == 0 and not pwCancelBar and not nowGo\n")
        prep = block(t, "                if not skipRef and not na(pQty) and pwState == 0 and not pwCancelBar and not nowGo\n", "            else if not skipRef")
        pf = func(t, "f_satProvEval(float pc, float l1p, float l2p, float stbp) =>")
        assigned = set(re.findall(r"^\s*(\w+)\s*(?::=|\+=)", pf, re.M))
        al[k] = (nb.index("strategy.entry(") < nb.index("alert(") and nb.count("alert(") == 1 and "(na(stConfBar) or stConfBar != time)" in nb
                 and nb.count('f_stAlertMsg("確定", side, close, pSL, tpRef)') == 2 and "stConfBar := time" in nb
                 and "alert(" not in prep and "label." not in prep
                 and assigned <= {"side", "ePx", "sl", "tp", "lk", "lp"} and not re.search(r"strategy\.|alert\(|label\.|varip", pf)
                 and "bool tchd = pwTouched and not (stSatsTq and bar_index - pwTouchBar > stSatsTqN)" in pf
                 and "bool rebB      = tchd and inRange" in pf and "else if stSats and stSatsNow and pwState == 0" in pf
                 and "not na(f_stQty(s0, e0, l0)) and not na(f_stQty(s0, close, l0))" in pf
                 and "bar_index - hBar >= 0 and bar_index - hBar <= stSatsNowN and nMtf and nDir" in pf
                 and t.count("alert(") == BASE[k].count("alert(") + 1)
    check("SY-07 alerts / labels: the immediate order sends the existing confirmed alert (stConfBar once-per-bar guard, shared switch) and "
          "label right after its strategy.entry with the order values (decision close / SL0 / TP0); the plain wait prep sends nothing; the "
          "provisional evaluation stays read-only (locals only, no strategy / alert / label / varip) and now covers the pull-side contact "
          "expiry (tchd) while waiting and, with the immediate entry ON before a wait, an immediate order of the forming bar (Zone signal "
          "of f_stProvEval + t - e <= Nz + filter + SL / TP side + both sizes); one extra alert() per file (the immediate one)",
          all(al.values()), str(al))
    pl = {k: len(re.findall(r"^plot(?:shape)?\(", CUR[k], re.M)) for k in CUR}
    check("SY-08 display: path, immediate count, line, e - q, t - e, planned / actual RR per path, candidate ages, pull-side contact age / "
          "expiry count, the immediate marker (pwEv 3); plots + shapes per file %s <= 64" % pl,
          all(v <= 64 for v in pl.values()) and all('"SATS · 即時発注"' in CUR[k] and "SATS · 引きつけ側 接触期限切れ件数" in CUR[k] for k in CUR))
    sym = {}
    for k in CUR:
        t = CUR[k]
        sym[k] = ("stSatsNearPx" in func(t, "f_satHist(int side, float L, int q) =>") and "stSatsNearD)" not in func(t, "f_satHist(int side, float L, int q) =>")
                  and "float nQty = f_stQty(side, close, pSL)" in t and "    if oState == 0 and not cancelBar and stSessOK\n" in t
                  and (("stNoWkend" in t) == (k == "BTCUSD")))
    check("SY-09 per symbol: the near test uses the symbol's price distance stSatsNearPx (pips x 0.01 / 0.0001, USD for BTC); the immediate "
          "size is the symbol's own f_stQty(side, close, SL0); the immediate order sits inside the existing session gate (BTC weekend rule "
          "included; no weekend rule added to FX)", all(sym.values()), str(sym))


# ---- models ---------------------------------------------------------------------------------------------------------------------
def gate_model():
    # current-bar-first pick == Gold push-then-pick on random sequences (both sides, three lines, Nc / Nz random)
    random.seed(2201)
    same = True
    n_cases = 0
    for _ in range(300):
        nc, nz = random.choice((0, 1, 2, 3)), random.choice((0, 1, 2, 3))
        side = random.choice((1, -1))
        px, bars = 2600.0, []
        for _ in range(40):
            o = px
            c = round(o + random.uniform(-3, 3), 1)
            bars.append((o, max(o, c) + round(random.uniform(0, 2), 1), min(o, c) - round(random.uniform(0, 2), 1), c))
            px = c
        lines = [[round(b[3] + random.uniform(-4, 4), 1) for b in bars] for _ in range(3)]
        flags = [xs.hist18(side, bars, lines[k], nc) for k in range(3)]
        committed = []
        for t in range(len(bars)):
            now = [(flags[k][t][1], t, k + 1) for k in range(3) if flags[k][t][0]]
            gold_pick = xs.pick19(committed + now, t, nz, nc)
            mine = now[0] if now else xs.pick19(committed, t, nz, nc)
            same &= (gold_pick == mine)
            committed = [x for x in committed + now if t - x[1] <= nz]
            n_cases += 1
    check("SZ-01 model: the current-bar-first pick equals Gold's push-then-pick on %d random bars (Nc / Nz 0-3, Long / Short, three lines)" % n_cases, same)
    ex = (xs.pick19([(1, 2, 1)], 3, 1, 1), xs.pick19([(1, 1, 1)], 2, 1, 1), xs.pick19([(1, 2, 1)], 4, 1, 1),
          [(q, e) for e, (r, q) in enumerate(xs.hist18(1, [(2612, 2613, 2608, 2610), (2610, 2610.5, 2604.0, 2604.5), (2604.5, 2604.9, 2603.5, 2604),
                                                           (2604, 2607, 2603.9, 2606)], [2605.0] * 4, 1)) if r])
    check("SZ-02 model (Gold XA-19 rules, Nc = Nz = 1): contact 10 / rebound 11 / Zone 12 valid; contact + rebound 10 / Zone 11 valid; Zone 13 "
          "invalid (Nz); contact 10 / rebound 12 without a new contact -> no rebound (Nc)",
          ex == ((1, 2, 1), (1, 1, 1), None, []), str(ex))

    def prov_wait(w, t_close, h, l, c, pc, lines, o, skip=False, qty_ok=True):
        """port of the SX-2 f_satProvEval wait branch (with the pull-side expiry as tchd)."""
        if w.state != 1:
            return 0
        if t_close - w.t_end >= w.limit * 60000 or ((l <= w.sl0) if w.side == 1 else (h >= w.sl0)):
            return 0
        tchd = w.touched and not (w.tq and w.cur_bar - w.tbar > w.tqn)
        if not tchd:
            k, L = xs.pick(w.side, w.p0, w.sl0, pc, lines)
        else:
            k, L = w.tk, lines[w.tk - 1]
        in_range = k != 0 and L is not None and ((w.sl0 < L < w.p0) if w.side == 1 else (w.p0 < L < w.sl0))
        hit = in_range and l <= L <= h
        near = w.near and in_range and ((l > L and l - L <= w.dist) if w.side == 1 else (h < L and L - h <= w.dist))
        ra = (hit or near) and ((c > L) if w.side == 1 else (c < L))
        rb = tchd and in_range and ((pc <= L and c > L) if w.side == 1 else (pc >= L and c < L))
        bd = (not w.body) or ((c > o) if w.side == 1 else (c < o))
        pr = (w.sl0 < c < w.p0) if w.side == 1 else (w.p0 < c < w.sl0)
        return w.side if (ra or rb) and bd and not skip and pr and qty_ok else 0

    random.seed(2202)
    agree = untouched = True
    n = 0
    for side in (1, -1):
        for _ in range(300):
            p0, sl0 = (2600.0, 2580.0) if side == 1 else (2600.0, 2620.0)
            w = xs.Wait17(side, p0, sl0, 0.0, body=random.random() < 0.5, near=random.random() < 0.5, dist=1.0,
                          tq=random.random() < 0.6, tqn=random.choice((0, 1, 3)))
            pc = p0
            for i in range(1, 30):
                if w.state != 1:
                    break
                c = round(pc + random.uniform(-4, 4), 1)
                o = round(pc + random.uniform(-2, 2), 1)
                h, l = max(o, c) + round(random.uniform(0, 3), 1), min(o, c) - round(random.uniform(0, 3), 1)
                lines = tuple(None if random.random() < 0.1 else round(c + random.uniform(-6, 6), 1) for _ in range(3))
                sk = random.random() < 0.2
                w.cur_bar = 10 + i
                before = (w.state, w.touched, w.tk, w.tbar, w.n_tq, w.n_touch_prep, len(w.orders))
                for f in (0.3, 0.7):
                    tc = round(o + (c - o) * f, 1)
                    prov_wait(w, xs.tb(i), max(o, tc), min(o, tc), tc, pc, lines, o, skip=sk)
                pv = prov_wait(w, xs.tb(i), h, l, c, pc, lines, o, skip=sk)
                untouched &= before == (w.state, w.touched, w.tk, w.tbar, w.n_tq, w.n_touch_prep, len(w.orders))
                r = w.step(10 + i, xs.tb(i), h, l, c, pc, lines, o=o, skip=sk)
                agree &= (pv != 0) == (r == 2)
                n += 1
                pc = c
    check("SZ-03 model: while waiting, the provisional evaluation (with the pull-side contact expiry, body / near / filter random) on the final "
          "OHLC equals the confirmed decision on %d random bars and writes nothing over several forming ticks (touch record, expiry count, "
          "touch count, orders)" % n, agree and untouched, str((agree, untouched)))

    def immediate(sig_side, p0, sl0, tp0, close_px, e_bar, t_bar, nz, mtf=True, q_ref=True, q_close=True):
        """the confirmed immediate test (block (4)) and the provisional one (f_satProvEval) share this expression."""
        if sig_side == 0 or e_bar is None:
            return False
        nd = sig_side * (close_px - sl0) > 0 and sig_side * (tp0 - close_px) > 0
        return 0 <= t_bar - e_bar <= nz and mtf and nd and q_ref and q_close
    cases = {"valid": immediate(-1, 2600, 2620, 2570, 2604, 9, 10, 1), "Nz over": immediate(-1, 2600, 2620, 2570, 2604, 8, 10, 1),
             "close beyond SL0": immediate(-1, 2600, 2620, 2570, 2621, 10, 10, 1), "close beyond TP0": immediate(-1, 2600, 2620, 2570, 2569, 10, 10, 1),
             "filter": immediate(-1, 2600, 2620, 2570, 2604, 10, 10, 1, mtf=False), "size at P0": immediate(-1, 2600, 2620, 2570, 2604, 10, 10, 1, q_ref=False),
             "size at close": immediate(-1, 2600, 2620, 2570, 2604, 10, 10, 1, q_close=False), "no rebound": immediate(-1, 2600, 2620, 2570, 2604, None, 10, 1),
             "no signal": immediate(0, 2600, 2620, 2570, 2604, 10, 10, 1), "P0 worse ok": immediate(-1, 2600, 2620, 2570, 2595, 10, 10, 1)}
    pf = func(CUR["GBPJPY"], "f_satProvEval(float pc, float l1p, float l2p, float stbp) =>")
    nb = block(CUR["GBPJPY"], "                if stSatsNow and not skipRef", "                        oSeq    += 1\n")
    check("SZ-04 model: the immediate test (confirmed block (4) and the provisional pre-wait branch use the same terms: t - e <= Nz, filter, "
          "SL0 < close < TP0 side, size at P0 and at close) — valid / Nz over / close beyond SL0 or TP0 / filter / either size invalid / no "
          "rebound / no signal; a close worse than P0 is still allowed (no P0 improvement)",
          cases == {"valid": True, "Nz over": False, "close beyond SL0": False, "close beyond TP0": False, "filter": False, "size at P0": False,
                    "size at close": False, "no rebound": False, "no signal": False, "P0 worse ok": True}
          and "not skipRef and not na(pQty)" in nb and "float nQty = f_stQty(side, close, pSL)" in nb and "f_stQty(s0, e0, l0)" in pf, str(cases))

    def q_jpy(dist):
        return math.floor(9000.0 / (dist * 1000.0) + 1e-9) * 1000.0 if dist > 0 and math.floor(9000.0 / (dist * 1000.0) + 1e-9) >= 1 else None

    def q_btc(dist, bud=60.0, step=0.01, mn=0.01):
        n = math.floor(bud / (dist * step) + 1e-9)
        if n * step * dist > bud:
            n -= 1
        return n * step if n >= 1 and n * step >= mn * (1 - 1e-9) else None
    gate_ok = {}
    for k in CUR:
        t = CUR[k]
        prov_br = block(t, "if (stPvA or stPvL) and stSats", "if (stPvA or stPvL) and not stSats")
        g = "bool  stPvOK   = pSide != 0\n" if k == "USDJPY" else "bool  stPvOK   = pSide != 0 and not na(pvQty)\n"
        gate_ok[k] = g in t and (("pvQty" not in prov_br) if k == "USDJPY" else ("pvQty := pSide != 0 ? f_stQty(pSide, pPx, pSL) : na" in prov_br))
    check("SZ-05 size gate of the provisional output: f_satProvEval returns a side only with valid sizes (wait: f_stQty(close, SL0); immediate: "
          "f_stQty(P0, SL0) and f_stQty(close, SL0)); the four files with pvQty recompute it from (side, close, SL0) as the SX-1 branch "
          "does, USDJPY gates on the side; model: JPY 0.30 -> 30,000 units valid, 900 -> invalid; BTC 1,000 USD -> 0.06, 7,000 -> none",
          all(gate_ok.values()) and q_jpy(0.30) == 30000.0 and q_jpy(900.0) is None and abs(q_btc(1000.0) - 0.06) < 1e-9 and q_btc(7000.0) is None,
          str(gate_ok))


def gate_mutation():
    bad = []
    for k, p in s2.PATHS.items():
        t = CUR[k]
        muts = [t.replace("if barstate.isconfirmed\n    hTqL1 := nL1\n", "if true\n    hTqL1 := nL1\n"),
                t.replace("int  hEL = hNowL ? bar_index : pEL", "int  hEL = pEL"),
                t.replace("            bool tchd = pwTouched and not (stSatsTq and bar_index - pwTouchBar > stSatsTqN)\n", "            bool tchd = pwTouched\n"),
                t.replace("and not na(f_stQty(s0, e0, l0)) and not na(f_stQty(s0, close, l0))", "and not na(f_stQty(s0, close, l0))"),
                t.replace("                            alert(f_stAlertMsg(\"確定\", side, close, pSL, tpRef), alert.freq_all)\n", ""),
                t.replace("near  = ok and stSatsNear and (side == 1 ? (low > L and low - L <= stSatsNearPx)", "near  = ok and stSatsNear and (side == 1 ? (low > L and low - L <= stSatsNearD)"),
                t.replace('stSatsNow = input.bool(false, "SATS · 直近の反発で即時エントリー"', 'stSatsNow = input.bool(true, "SATS · 直近の反発で即時エントリー"')]
        for i, m in enumerate(muts):
            if m == t or s2.strip(p, m) is not None:
                bad.append((k, i))
    check("SQ-01 mutations (history written on forming ticks, the forming-bar rebound ignored in the pick, the provisional ignoring the contact "
          "expiry, the P0 size check dropped, the immediate confirmed alert dropped, the near test reading the pips input as a price, the "
          "immediate entry ON by default) do not strip back to 32cc570 in any file", not bad, str(bad))


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
