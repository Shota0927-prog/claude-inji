"""SX-1 fixtures — the Gold SATS / filter / breakeven features rolled out to the BTCUSD / USDJPY / GBPJPY / EURUSD / GBPUSD
Strategies (tests/sx_build.py).

  SX : static on the five delivered Strategies — == sx_build.build(); strip gives the 443c139 files byte for byte; Engines,
       Visuals, Gold and every other Pine file unchanged; strategy() / import / every old input default unchanged; the new
       inputs and defaults (Current, 240, line OFF, body OFF, near OFF / 0, filters OFF, Fixed Distance, R 1.0, TP 0.5);
       the old code changed only at the four hook lines (+ the USDJPY message text under stSats); f_stQty / f_stTp /
       session / weekend / f_stProvEval identical; four new requests only; the SATS code equal to Gold's (XA-7 .. XA-15)
       apart from the near unit, the alert / label lines and comments; Current isolation; read-only provisional evaluation
  SM : models — provisional == the confirmed decision on the final OHLC without touching the state (multi-tick, touch on
       a forming bar not saved), expiry 239 / 240 minutes and a weekend gap, cancel before the rebound, near unit per
       symbol, the size functions per symbol (JPY / USD pairs / BTC), breakeven modes (Gold models reused), filter AND
  SQ : mutations rejected by the exact strip

Evidence class: PINE_NOT_VERIFIED (TradingView compile, SATS values vs the source indicator, Strategy Tester, alerts external).
"""
import copy
import math
import os
import random
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sx_build as sx            # noqa: E402
import xa_build as xb            # noqa: E402
import eu_sim as es              # noqa: E402
import xas_sim as xs             # noqa: E402

ROOT = sx.ROOT
B = sx.BASE_REV
raw = lambda p: open(os.path.join(ROOT, p), encoding="utf-8").read()
code_only, input_values, input_decls, func = es.code_only, es.input_values, es.input_decls, es.func
CUR = {k: __import__("sx2_build").unapply(v["path"], raw(v["path"])) for k, v in sx.CUR.items()}   # SX-1 layer (the later SX-2 reverted exactly)
BASE = {k: sx.show(B, v["path"]) for k, v in sx.CUR.items()}
GOLD = xb.strip_strategy16(raw(xb.STR_PATH)) or ""     # Gold XA-15 layer (the later Gold-only XA-16 reverted exactly)
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


def block(t, start, end):
    i = t.index(start)
    return t[i:t.index(end, i)]


NEW_INPUTS = {"stTiming": '"Current"', "stSatsWait": "240", "stSatsShow": "false", "stSatsBody": "false", "stSatsNear": "false",
              "stSatsNearD": "0.0", "stSatsFD": "false", "stSatsF4": "false", "stSatsF1": "false", "stSatsF15": "false",
              "stSatsF5": "false", "stBEMode": '"Fixed Distance"', "stBER": "1.0", "stBETp": "0.5"}
TABLE = {"BTCUSD": ('"D: 1M BOS Rebound"', '"Long Only"', "1.2"), "USDJPY": ('"D: 1M BOS Rebound"', '"Long Only"', "1.5"),
         "GBPJPY": ('"D: 1M BOS Rebound"', '"Long Only"', "1.2"), "EURUSD": ('"B: Confirmed Rejection"', '"Short Only"', "1.5"),
         "GBPUSD": ('"B: Confirmed Rejection"', '"Both"', "1.5")}
HOOK_OLD = ["if fillNow", "if oSide * (fav - oFill) >= stBEDist", "if not skipRef and not na(pQty)", "if stPvA or stPvL"]
UJ_OLD = ['"\\nMode: " + stMode +', '"\\nE: " + f_num(ePx, "#.000") + (stModeA ? " (指値)" : " (参考。次足始値で成行)") +']


def gate_static():
    others = [p for p in os.listdir(ROOT) if p.endswith(".pine") and p not in sx.FILES and not __import__("xal_build").ok(p)]
    check("SX-01 the five Strategies == sx_build.build() and strip back to the 443c139 files byte for byte (unapply too); Engines, "
          "Visuals, Gold and every other Pine file byte-identical to 443c139 (no Library re-publish); strategy() (calc_on_every_tick "
          "= true) and the import line unchanged",
          all(CUR[k] == sx.build(v["path"]) and sx.strip(v["path"], CUR[k]) == BASE[k] and sx.unapply(v["path"], CUR[k]) == BASE[k]
              and sx.unapply(v["path"], BASE[k]) == BASE[k] for k, v in sx.CUR.items())
          and not [p for p in others if raw(p) != sx.show(B, p)
                   and not (p == xb.STR_PATH and xb.strip_strategy16(raw(p)) == sx.show(B, p))]     # Gold: later XA-16 exactly
          and all(es.seg(CUR[k], "strategy(", "import ") == es.seg(BASE[k], "strategy(", "import ")
                  and "calc_on_every_tick     = true," in CUR[k]
                  and re.findall(r"^import .*$", CUR[k], re.M) == re.findall(r"^import .*$", BASE[k], re.M) for k in CUR))
    bad = {}
    for k in CUR:
        iv, ib = input_values(CUR[k]), input_values(BASE[k])
        new = {n: v for n, v in iv.items() if n not in ib}
        if new != NEW_INPUTS or any(iv[n] != v for n, v in ib.items()) or (ib["stMode"], ib["stDir"], ib["stRR"]) != TABLE[k] \
                or ib["stBE"] != "false":
            bad[k] = (new, [n for n, v in ib.items() if iv[n] != v])
    check("SX-02 inputs: the new ones exactly (Entry Timing Current, 240, line OFF, body OFF, near OFF / 0, D / 4H / 1H / 15m / 5m "
          "OFF, Fixed Distance, R 1.0 (min 0.1), TP Ratio 0.5 (0.05..1.0)); every old input default unchanged in each file "
          "(Entry / Direction / RR as the table: BTC D / Long / 1.2, USDJPY D / Long / 1.5, GBPJPY D / Long / 1.2, EURUSD B / Short "
          "/ 1.5, GBPUSD B / Both / 1.5; Breakeven OFF and its fixed trigger kept); no Gold value copied",
          not bad and all(es.kw(input_decls(CUR[k])["stBER"], "minval") == "0.1" and es.kw(input_decls(CUR[k])["stBETp"], "maxval") == "1.0"
                          for k in CUR), str(bad))
    units = {k: re.search(r"^float SX_NEAR_UNIT = ([\d.]+)", CUR[k], re.M).group(1) for k in CUR}
    lbls = {k: re.search(r'"SATS · 近接許容距離 \((\w+)\)"', CUR[k]).group(1) for k in CUR}
    check("SX-03 near distance unit: USDJPY / GBPJPY 1 pip = 0.01, EURUSD / GBPUSD 1 pip = 0.0001 (input in pips), BTCUSD in USD "
          "(1.0); the price distance used by the touch test is stSatsNearPx = input x unit (the Gold 1 USD is not reused)",
          units == {"BTCUSD": "1.0", "USDJPY": "0.01", "GBPJPY": "0.01", "EURUSD": "0.0001", "GBPUSD": "0.0001"}
          and lbls == {"BTCUSD": "USD", "USDJPY": "pips", "GBPJPY": "pips", "EURUSD": "pips", "GBPUSD": "pips"}
          and all("float stSatsNearPx = stSatsNearD * SX_NEAR_UNIT" in CUR[k] and CUR[k].count("stSatsNearPx") == 5 and
                  "<= stSatsNearD" not in CUR[k] for k in CUR), str((units, lbls)))
    deltas = {}
    for k in CUR:
        base_lines = set(l.strip() for l in code_only(BASE[k]).split("\n"))
        gone = sorted(l for l in es.changed_code(BASE[k], CUR[k]) if l and l in base_lines and l not in code_only(CUR[k]).split("\n")
                      and l.strip() not in [x.strip() for x in code_only(CUR[k]).split("\n")])
        deltas[k] = gone
    exp = {k: sorted(HOOK_OLD + (UJ_OLD + ['"\\nTP: " + (okR ? f_num(tp, "#.000") : "-") + (kind == "仮" ? "" : " (発注時の予定値。最終 TP は約定確認後に実約定価格から設定)") +']
                                 if k == "USDJPY" else [])) for k in CUR}
    keep_fns = ("f_stQty(int side, float ref, float sl) =>", "f_stTp(", "f_stNearest(", "f_stInSession(int t) =>", "f_stProvEval() =>",
                "f_stAdopt(", "f_stBetter(", "f_stZoneEval(zn.Zone z) =>")
    check("SX-04 old code changed only at the hook lines (if fillNow -> SATS branch + else if fillNow, the breakeven test -> "
          "f_beTrig, the order gate -> if stSats prep + else if, the provisional gate -> SATS / Current branches; USDJPY also its "
          "three message lines, Current text unchanged); f_stQty / f_stTp / f_stNearest / session / f_stProvEval / zone functions "
          "and the BTC weekend day logic identical; four new requests only (D / 240 / 60 / 15)",
          deltas == exp and all(func(CUR[k], h) == func(BASE[k], h) for k in CUR for h in keep_fns if ("\n" + h) in BASE[k])
          and all(CUR[k].count("request.security(") == BASE[k].count("request.security(") + 4
                  and CUR[k].count("request.security_lower_tf(") == BASE[k].count("request.security_lower_tf(") for k in CUR)
          and func(CUR["BTCUSD"], "f_stSessDow(int t) =>") == func(BASE["BTCUSD"], "f_stSessDow(int t) =>")
          and all("stNoWkend" not in CUR[k] for k in CUR if k != "BTCUSD"), str({k: d for k, d in deltas.items() if d != exp[k]}))
    gold_fns = ("f_satTfState() =>", "f_satAllAgainst(int want) =>", "f_satPick(", "f_satRR(", "f_beTrig(", "f_satBand() =>")
    gw = code_only(block(GOLD, "    bool  pwCancelBar = false\n", "    // (4) 新規 Entry"))
    gp = code_only(block(GOLD, "            if stSats\n", "            else if not skipRef and not na(pQty)\n"))
    gf = code_only(block(GOLD, "    if fillNow and stSats\n", "    else if fillNow\n"))
    same = {}
    for k in CUR:
        w = code_only(block(CUR[k], "    bool  pwCancelBar = false\n", "    // (4) 新規 Entry"))
        w = re.sub(r"\n                    if stAlertConf and .*?label\.delete\(array\.shift\(stConfLbls\)\)", "", w, flags=re.S)
        w = w.replace("stSatsNearPx", "stSatsNearD")
        p = code_only(block(CUR[k], "            if stSats\n", "            else if not skipRef and not na(pQty)\n"))
        f = code_only(block(CUR[k], "    if fillNow and stSats\n", "    else if fillNow\n"))
        strip_c = lambda s: re.sub(r"(?<=\S) {2,}", " ", re.sub(r"\s+//.*", "", s))     # comments / alignment spaces only
        same[k] = (all(func(CUR[k], h).rstrip() == func(GOLD, h).rstrip() for h in gold_fns),
                   strip_c(w) == strip_c(gw), strip_c(p) == strip_c(gp), strip_c(f) == strip_c(gf))
    check("SX-05 SATS code == Gold XA-7 .. XA-15: f_satBand (== tests/sats_src/f_satBand.txt, one global call), f_satTfState / "
          "requests, f_satAllAgainst, f_satPick, f_satRR, f_beTrig identical; the waiting block (3b), the prep and the fill "
          "branch (2b') equal to Gold apart from comments, the near unit (stSatsNearPx) and the confirmed alert / label lines",
          all(all(v) for v in same.values()) and all(func(CUR[k], "f_satBand() =>").rstrip("\n") + "\n" == sx.SATS_FN
                                                     and CUR[k].count("= f_satBand()") == 2 for k in CUR), str(same))
    iso = {}
    for k in CUR:
        t = CUR[k]
        cur_order = block(t, "            else if not skipRef and not na(pQty)\n", "    stPrev := cur")
        base_order = block(BASE[k], "            if not skipRef and not na(pQty)\n", "    stPrev := cur")
        cur_fill = block(t, "    else if fillNow\n", "    // (2c)")
        base_fill = block(BASE[k], "    if fillNow\n", "    // (2c)")
        prov = block(t, "if (stPvA or stPvL) and not stSats\n", "bool  stPvOK")
        prov_b = block(BASE[k], "if stPvA or stPvL\n", "bool  stPvOK")
        iso[k] = (cur_order.replace("            else if", "            if", 1) == base_order, cur_fill.replace("    else if", "    if", 1) == base_fill,
                  prov[len("if (stPvA or stPvL) and not stSats\n"):] == prov_b[len("if stPvA or stPvL\n"):],
                  "    if stSats and pwState == 1 and bar_index > pwBar\n" in t, "            if stSats     // SX-1: 決済済み" in t)
    check("SX-06 Current isolation: the Current order branch (entry / exit / confirmed alert / label), the Current fill branch, "
          "the Current provisional evaluation are byte-identical under 'else' / 'not stSats'; every SATS block is gated by stSats "
          "(wait, prep, fill, closed-fill record, provisional); breakeven Fixed Distance = stBEDist (no new check)",
          all(all(v) for v in iso.values()), str(iso))
    rd_only = {}
    for k in CUR:
        pf = func(CUR[k], "f_satProvEval(float pc, float l1p, float l2p, float stbp) =>")
        assigned = set(re.findall(r"^\s*(\w+)\s*(?::=|\+=)", pf, re.M))
        wb = block(CUR[k], "    bool  pwCancelBar = false\n", "    // (4) 新規 Entry")
        prep = block(CUR[k], "            if stSats\n", "            else if not skipRef and not na(pQty)\n")
        rd_only[k] = (assigned <= {"side", "ePx", "sl", "tp", "lk", "lp"}, not re.search(r"strategy\.|alert\(|label\.|varip", pf),
                      CUR[k].count("f_satProvEval(") == 2, "alert(" not in prep and "label." not in prep,
                      wb.count("alert(") == 1 and wb.count("stConfBar := time") == 1 and "(na(stConfBar) or stConfBar != time)" in wb,
                      'f_stAlertMsg("確定", pwSide, close, pwSL0, pwTP0)' in wb and wb.count('f_stAlertMsg("確定", pwSide, close, pwSL0, pwTP0)') == 2,
                      wb.index("strategy.entry(") < wb.index("alert("),
                      "stProvBar" not in pf and "stConfBar" not in pf)
    check("SX-07 alerts / labels: f_satProvEval assigns only its locals (side / ePx / sl / tp / lk / lp), no strategy.* / alert / "
          "label / varip — no wait, touch, counter, Track or order state is written; called once (SATS branch); prep sends nothing; "
          "the SATS confirmed alert is sent only after the SATS strategy.entry, with the existing stConfBar once-per-bar guard, "
          "and the confirmed label shows the same values (order-bar close / SL0 / TP0); the provisional guard (stProvBar) is shared",
          all(all(v) for v in rd_only.values()), str(rd_only))
    uj = CUR["USDJPY"]
    check("SX-08 USDJPY message: under SATS the Mode line adds '/ SATS Pullback', the price is not called a limit and the TP is the "
          "fixed TP0; Current text unchanged (same strings when stSats is false)",
          '"\\nMode: " + stMode + (stSats ? " / SATS Pullback" : "") +' in uj and '(stModeA and not stSats ? " (指値)" : " (参考。次足始値で成行)")' in uj
          and 'stSats ? " (SATS の TP0。約定確認後もこの値)" : " (発注時の予定値。最終 TP は約定確認後に実約定価格から設定)")' in uj)
    pv = {}
    for k in CUR:
        blk4 = block(CUR[k], "    if oState == 0 and not cancelBar and stSessOK\n", "    stPrev := cur")
        wb = block(CUR[k], "    bool  pwCancelBar = false\n", "    // (4) 新規 Entry")
        pv[k] = ("array<StCand> src = stModeA ? cur : stModeD ? dSrc : stPrev" in blk4 and "float  ref = stModeA ? pL : close" in blk4
                 and blk4.index("float  pQty = f_stQty(side, ref, pSL)") < blk4.index("            if stSats\n")
                 and "if not skipRef and not na(pQty) and pwState == 0 and not pwCancelBar" in blk4
                 and "pwP0     := ref" in blk4 and "pwSL0    := pSL" in blk4 and "pwTP0    := tpRef" in blk4 and "pwEndT   := time_close" in blk4
                 and "(not stModeC or (c.side == 1 ? stPatL : stPatS))" in blk4 and CUR[k].count("array.push(dSrc,") == 1
                 and "if stSats and pwState == 1 and bar_index > pwBar" in wb and sorted(re.findall(r"why := (-\d)", wb)) == ["-1", "-4"]
                 and "map.put(stUsed" not in wb and "map.put(stUsed" not in block(blk4, "            if stSats\n", "            else if")
                 and code_only(CUR[k]).count("pwNFill    += 1") == 2 and code_only(CUR[k]).count("pwState  := 1") == 1
                 and "pwRRFill := na" in wb)
    check("SX-10 wait start / life: the prep sits in the shared order block (4) with each mode's source (A cur / D dSrc after its "
          "BOS / B, C stPrev; C pattern only for C), ref = A limit / B, C, D close, after the existing RR / qty checks; stores P0 / "
          "SL0 / TP0 / prep end time once (only without a wait and not on a cancel bar = no overwrite / extension); evaluation from "
          "the next bar (bar_index > pwBar); cancels only by expiry (-1) / SL0 (-4) (no Strong / Track re-check); no used-Track "
          "write at prep / touch / cancel; the actual RR recorded once per fill on each path (open / closed in the fill bar)",
          all(pv.values()), str(pv))
    fm = func(CUR["USDJPY"], "f_stAlertMsg(")
    fm0 = func(BASE["USDJPY"], "f_stAlertMsg(")
    P1 = ' + (stSats ? " / SATS Pullback" : "")'
    P2 = '(stModeA and not stSats ? " (指値)" : " (参考。次足始値で成行)")'
    P3 = 'stSats ? " (SATS の TP0。約定確認後もこの値)" : " (発注時の予定値。最終 TP は約定確認後に実約定価格から設定)"'
    as_cur = fm.replace(P1, "").replace(P2, '(stModeA ? " (指値)" : " (参考。次足始値で成行)")').replace(
        P3, '" (発注時の予定値。最終 TP は約定確認後に実約定価格から設定)"')
    as_sats = fm.replace(P1, ' + " / SATS Pullback"').replace(P2, '" (参考。次足始値で成行)"').replace(P3, '" (SATS の TP0。約定確認後もこの値)"')
    others_msg = all(func(CUR[k], "f_stAlertMsg(") == func(BASE[k], "f_stAlertMsg(") and "指値" not in func(CUR[k], "f_stAlertMsg(")
                     and "約定確認後" not in func(CUR[k], "f_stAlertMsg(") and "stModeA" not in func(CUR[k], "f_stAlertMsg(")
                     for k in CUR if k != "USDJPY")
    check("SX-11 alert / label text (one f_stAlertMsg feeds the alerts and both labels): USDJPY with stSats = false reduces to the "
          "previous function byte for byte (Current text unchanged); with stSats = true there is no '指値' (an Entry A SATS order is "
          "a market order at the next bar) and no '最終 TP は約定確認後に実約定価格から設定' (SATS keeps TP0), the TP is labelled as "
          "the fixed TP0 and the Mode line shows SATS Pullback; the other four messages are unchanged and never say '指値' / "
          "'約定確認後' (Entry / SL / distance / TP / RR only)",
          all(fm.count(x) == 1 for x in (P1, P2, P3)) and fm.count("stSats") == 3 and as_cur == fm0
          and "指値" not in as_sats and "最終 TP" not in as_sats and "次足始値で成行" in as_sats and "SATS の TP0" in as_sats
          and '"\\nMode: " + stMode + " / SATS Pullback" +' in as_sats and others_msg)
    pl = {k: len(re.findall(r"^plot(?:shape)?\(", CUR[k], re.M)) for k in CUR}
    check("SX-09 load: plots + shapes <= 64 per script (%s); the filter requests are 4 per script and the 5m state reuses satBand; "
          "f_satBand runs at global scope every bar (not only while waiting)" % pl,
          all(v <= 64 for v in pl.values())
          and all(re.search(r"^\[satL1, satL2, satStb, .*\] = f_satBand\(\)$", CUR[k], re.M) for k in CUR))


# ---- models -----------------------------------------------------------------------------------------------------------------
def prov_eval(w, t_close, h, l, c, pc, lines, o, skip=False, qty_ok=True):
    """port of f_satProvEval (read-only): the order decision of the forming bar from the confirmed wait state."""
    if w.state != 1:
        return 0
    if t_close - w.t_end >= w.limit * 60000 or ((l <= w.sl0) if w.side == 1 else (h >= w.sl0)):
        return 0
    if not w.touched:
        k, L = xs.pick(w.side, w.p0, w.sl0, pc, lines)
    else:
        k, L = w.tk, lines[w.tk - 1]
    in_range = k != 0 and L is not None and ((w.sl0 < L < w.p0) if w.side == 1 else (w.p0 < L < w.sl0))
    hit = in_range and l <= L <= h
    near = w.near and in_range and ((l > L and l - L <= w.dist) if w.side == 1 else (h < L and L - h <= w.dist))
    reb_a = (hit or near) and ((c > L) if w.side == 1 else (c < L))
    reb_b = w.touched and in_range and ((pc <= L and c > L) if w.side == 1 else (pc >= L and c < L))
    body = (not w.body) or ((c > o) if w.side == 1 else (c < o))
    price = (w.sl0 < c < w.p0) if w.side == 1 else (w.p0 < c < w.sl0)
    return w.side if (reb_a or reb_b) and body and not skip and price and qty_ok else 0


def snap(w):
    return (w.state, w.touched, w.tk, w.tbar, w.n_touch_prep, w.n_same, w.n_later, len(w.orders), w.p0, w.sl0, w.tp0, w.t_end)


def gate_model():
    random.seed(1801)
    agree = untouched = ticks_ok = True
    n = 0
    for side in (1, -1):
        for _ in range(400):
            p0, sl0 = (2600.0, 2580.0) if side == 1 else (2600.0, 2620.0)
            w = xs.Wait13(side, p0, sl0, 0.0, body=random.random() < 0.5, near=random.random() < 0.5, dist=random.choice((0.0, 1.0, 3.0)))
            pc = p0
            for i in range(1, 30):
                if w.state != 1:
                    break
                c = round(pc + random.uniform(-4, 4), 1)
                o = round(pc + random.uniform(-2, 2), 1)
                h, l = max(o, c) + round(random.uniform(0, 3), 1), min(o, c) - round(random.uniform(0, 3), 1)
                lines = tuple(None if random.random() < 0.1 else round(c + random.uniform(-6, 6), 1) for _ in range(3))
                sk = random.random() < 0.2
                # forming ticks: partial OHLC (running high / low, moving close); provisional on each, state untouched
                before = snap(w)
                th, tl = o, o
                for tc in (round(o + (c - o) * f, 1) for f in (0.3, 0.7)):
                    th, tl = max(th, tc), min(tl, tc)
                    prov_eval(w, xs.tb(i), th, tl, tc, pc, lines, o, skip=sk)
                    ticks_ok &= snap(w) == before
                pv = prov_eval(w, xs.tb(i), h, l, c, pc, lines, o, skip=sk)
                untouched &= snap(w) == before
                r = w.step(10 + i, xs.tb(i), h, l, c, pc, lines, o=o, skip=sk)
                agree &= (pv != 0) == (r == 2)
                n += 1
                pc = c
    check("SM-01 model: on %d random confirmed bars (Long / Short, body / near / distance / filter random) the provisional "
          "evaluation on the final OHLC equals the confirmed order decision; it never changes the wait (state, touch record, line "
          "kind, counters, orders, P0 / SL0 / TP0, prep time), also over several forming ticks (a touch on a forming tick is not "
          "saved)" % n, agree and untouched and ticks_ok, str((agree, untouched, ticks_ok)))
    w = xs.Wait13(-1, 2600.0, 2620.0, 2570.0)
    first = prov_eval(w, xs.tb(1), 2611, 2606, 2612, 2605.0, (2610.0, None, None), 2608)       # touch, close above L: no
    later_b = prov_eval(w, xs.tb(2), 2609, 2604, 2605, 2611.0, (2610.0, None, None), 2608)     # not touched yet: B impossible
    check("SM-02 the first touch bar is not taken as an earlier touch: without a confirmed touch, a forming bar that only crosses "
          "back (B shape) gives no provisional order", first == 0 and later_b == 0 and not w.touched)

    def exp_at(minutes):
        e = xs.Wait13(-1, 2600.0, 2620.0, 2570.0, t_end=xs.T0, prep_bar=0)
        return e.step(1, xs.T0 + minutes * 60000, 2608, 2604, 2605, 2606.0, (2610.0, None, None), o=2606)
    gap = xs.Wait13(-1, 2600.0, 2620.0, 2570.0, t_end=xs.T0, prep_bar=0)
    g1 = gap.step(1, xs.T0 + 30 * 60000, 2608, 2604, 2605, 2606.0, (2610.0, None, None), o=2606)
    g2 = gap.step(2, xs.T0 + 2 * 86400000, 2609, 2604, 2605, 2605.0, (2610.0, None, None), o=2606)   # first bar after a weekend
    sl = xs.Wait13(-1, 2600.0, 2620.0, 2570.0, t_end=xs.T0, prep_bar=0)
    s1 = sl.step(1, xs.T0 + 5 * 60000, 2620, 2604, 2605, 2606.0, (2610.0, None, None), o=2611)     # SL0 + a rebound A bar
    pv_exp = prov_eval(xs.Wait13(-1, 2600.0, 2620.0, 2570.0, t_end=xs.T0, prep_bar=0), xs.T0 + 240 * 60000, 2611, 2606, 2605, 2606.0, (2610.0, None, None), 2608)
    check("SM-03 model: expiry by wall clock: 239 min no cancel / 240 min cancel; a weekend gap cancels on the first bar after it "
          "(the clock does not stop); SL0 reached cancels before a same-bar rebound; the provisional also returns nothing at 240",
          exp_at(239) == 0 and exp_at(240) == -1 and g1 == 0 and g2 == -1 and s1 == -4 and not sl.orders and pv_exp == 0)

    def near_ok(unit, d_input, L, h):
        return h < L and L - h <= d_input * unit
    check("SM-04 near distance per symbol: USDJPY 2 pips = 0.02 (L 150.100, high 150.080 near; 150.070 not), EURUSD 2 pips = "
          "0.0002 (L 1.10000, high 1.09985 near; 1.09970 not), BTC 50 USD; input 0 = real touch only",
          near_ok(0.01, 2, 150.100, 150.080) and not near_ok(0.01, 2, 150.100, 150.070)
          and near_ok(0.0001, 2, 1.10000, 1.09985) and not near_ok(0.0001, 2, 1.10000, 1.09970)
          and near_ok(1.0, 50, 65000.0, 64960.0) and not near_ok(1.0, 50, 65000.0, 64940.0)
          and not near_ok(0.01, 0, 150.100, 150.099))

    def q_jpy(dist, budget=9000.0, units=100000.0, step=0.01, pv=1.0):
        su = units * step
        return math.floor(budget / (dist * pv * su) + 1e-9) * su if dist > 0 and math.floor(budget / (dist * pv * su) + 1e-9) >= 1 else None

    def q_usd(dist, conv=150.0, units=100000.0, step=0.01):
        return q_jpy(dist, budget=9000.0 / conv, units=units, step=step)

    def q_btc(dist, conv=150.0, step=0.01, mn=0.01):
        bud = 9000.0 / conv
        n = math.floor(bud / (dist * step) + 1e-9)
        if n * step * dist > bud:
            n -= 1
        return n * step if n >= 1 and n * step >= mn * (1 - 1e-9) else None
    check("SM-05 size per symbol (the existing f_stQty, called with the order-bar close and SL0): JPY pairs 9,000 JPY / (0.30 x "
          "1,000) -> 30,000 units; USD pairs 60 USD / (0.0030 x 1,000) -> 20,000; BTC 60 USD / 1,000 USD -> 0.06 BTC, 7,000 USD -> "
          "below the 0.01 minimum -> no order; the SATS order uses f_stQty(pwSide, close, pwSL0) in all five files",
          q_jpy(0.30) == 30000.0 and abs(q_usd(0.0030) - 20000.0) < 1e-6 and abs(q_btc(1000.0) - 0.06) < 1e-9 and q_btc(7000.0) is None
          and all("float q = f_stQty(pwSide, close, pwSL0)" in CUR[k] and "not na(f_stQty(pwSide, close, pwSL0))" in CUR[k] for k in CUR))
    check("SM-06 breakeven modes (Gold models reused): Short fill 2610 / SL 2620 / TP 2570 -> 1R 2600, 0.5TP 2590; Fixed keeps the "
          "symbol's own trigger; na / 0 base -> no move; the f_beTrig text is Gold's",
          2610 - xs.be_trig("Risk Multiple", -1, 2610, 2620, 2570) == 2600 and 2610 - xs.be_trig("TP Progress", -1, 2610, 2620, 2570) == 2590
          and xs.be_trig("Fixed Distance", -1, 2610, 2620, 2570, dist=0.15) == 0.15 and xs.be_trig("Risk Multiple", -1, 2610, 2610, 2570) is None)
    sel = {"D": False, "4": True, "1": True, "15": False, "5": False}
    check("SM-07 filter AND (Gold model reused): all OFF never skips; 4H + 1H both blue skip Short, one unlit / na does not",
          not xs.skip13({}, dict.fromkeys(xs.TFS13, 1), 1) and xs.skip13(sel, {"4": 1, "1": 1}, 1)
          and not xs.skip13(sel, {"4": 1, "1": 0}, 1) and not xs.skip13(sel, {"4": None, "1": 1}, 1))
    QTY = {"USDJPY": lambda ref, sl: q_jpy(abs(ref - sl)), "GBPJPY": lambda ref, sl: q_jpy(abs(ref - sl)),
           "EURUSD": lambda ref, sl: q_usd(abs(ref - sl)), "GBPUSD": lambda ref, sl: q_usd(abs(ref - sl)),
           "BTCUSD": lambda ref, sl: q_btc(abs(ref - sl))}
    struct = {}
    for k in CUR:
        tx = CUR[k]
        pf = func(tx, "f_satProvEval(float pc, float l1p, float l2p, float stbp) =>")
        sats_br = block(tx, "if (stPvA or stPvL) and stSats", "if (stPvA or stPvL) and not stSats")
        gate = "bool  stPvOK   = pSide != 0\n" if k == "USDJPY" else "bool  stPvOK   = pSide != 0 and not na(pvQty)\n"
        struct[k] = ("if (rebA or rebB) and bodyOK and mtfOK and priceOK and not na(f_stQty(pwSide, close, pwSL0))" in pf
                     and "ePx  := close" in pf and "sl   := pwSL0" in pf and gate in tx
                     and ("pvQty" not in sats_br if k == "USDJPY" else "    pvQty := pSide != 0 ? f_stQty(pSide, pPx, pSL) : na\n" in sats_br)
                     and "if stPvA and stPvOK\n" in tx and "    if stPvL and stPvOK\n" in tx
                     and block(tx, "bool  stPvOK", "// ==== ZONE Strategy · Zone evaluation (end)") == block(BASE[k], "bool  stPvOK", "// ==== ZONE Strategy · Zone evaluation (end)"))

    def pv_flow(k, w, bar, qfn):
        """port of the provisional path of file k: f_satProvEval (qty gate f_stQty(side, close, SL0)) -> SATS branch (pvQty for the
        four files) -> stPvOK -> alert (stPvA) / label (stPvL, realtime). Returns (alert sent, label shown)."""
        t_close, h, l, c, pc, lines, o = bar
        q_in = qfn(c, w.sl0)
        p_side = prov_eval(w, t_close, h, l, c, pc, lines, o, qty_ok=q_in is not None)
        p_px, p_sl = (c, w.sl0) if p_side else (None, None)
        if k == "USDJPY":
            ok = p_side != 0
        else:
            pv_qty = qfn(p_px, p_sl) if p_side else None
            ok = p_side != 0 and pv_qty is not None
        return ok, ok

    res = {}
    for k in CUR:
        jpy = k in ("USDJPY", "GBPJPY")
        btc_k = k == "BTCUSD"
        if btc_k:
            p0, sl0, L, near_bad = 65000.0, 65900.0, 65400.0, 80000.0     # bad: 12,100 USD to SL0 -> below 0.01 BTC
            good = (xs.tb(1), 65450.0, 65300.0, 65200.0, 65100.0, (L, None, None), 65300.0)
            w_bad = xs.Wait13(-1, p0, near_bad, 50000.0)
            bad = (xs.tb(1), 68100.0, 67900.0, 67800.0, 67700.0, (68000.0, None, None), 67900.0)
        elif jpy:
            p0, sl0, L = 150.00, 150.40, 150.20
            good = (xs.tb(1), 150.22, 150.12, 150.10, 150.05, (L, None, None), 150.15)
            w_bad = xs.Wait13(-1, p0, 1500.0, 100.0)
            bad = (xs.tb(1), 750.5, 749.5, 749.0, 748.0, (750.0, None, None), 749.5)
        else:
            p0, sl0, L = 1.10000, 1.10400, 1.10200
            good = (xs.tb(1), 1.10220, 1.10120, 1.10100, 1.10050, (L, None, None), 1.10150)
            w_bad = xs.Wait13(-1, p0, 10.0, 0.5)
            bad = (xs.tb(1), 5.05, 4.95, 4.90, 4.85, (5.0, None, None), 4.95)
        w_ok = xs.Wait13(-1, p0, sl0, p0 - 1.0)
        snap0 = snap(w_ok)
        a_ok = pv_flow(k, w_ok, good, QTY[k])
        a_bad = pv_flow(k, w_bad, bad, QTY[k])
        q_good, q_bad = QTY[k](good[3], sl0), QTY[k](bad[3], w_bad.sl0)
        fires_if_qty = prov_eval(w_bad, *bad, qty_ok=True) == -1     # the bad bar is a full SATS signal apart from the size
        res[k] = (struct[k], a_ok == (True, True), a_bad == (False, False), q_good is not None, q_bad is None, snap(w_ok) == snap0,
                  fires_if_qty)
    check("SM-09 provisional quantity gate in all five files: f_satProvEval returns a side only when the existing f_stQty(side, the "
          "forming close, SL0) is valid (USDJPY: stPvOK = pSide != 0 relies on it; the other four also recompute pvQty with the "
          "same f_stQty(pSide, pPx = close, pSL = SL0) in the SATS branch, as their Current branch does); model per symbol (JPY "
          "pairs / USD pairs / BTC size functions): a valid quantity sends the provisional alert and shows the label, an invalid "
          "one (below the minimum lot) sends / shows nothing; the alert / label code after stPvOK is unchanged; state untouched",
          all(all(v) for v in res.values()), str(res))
    btc = CUR["BTCUSD"]
    check("SM-08 sessions: the SATS order and the prep both need stSessOK (BTC: includes the weekend day rule, unchanged; FX: no new "
          "weekend rule); the SATS order also needs oState == 0",
          all("if (rebA or rebB) and bodyOK and mtfOK and priceOK and stSessOK and oState == 0" in CUR[k]
              and "    if oState == 0 and not cancelBar and stSessOK\n" in CUR[k] for k in CUR)
          and "bool stSessOK  = (not stUseSess or f_stInSession(time_close)) and stWkdOK" in btc)


def gate_mutation():
    bad = []
    for k, v in sx.CUR.items():
        t = CUR[k]
        muts = [t.replace("float SX_NEAR_UNIT = " + v["unit"], "float SX_NEAR_UNIT = 0.1"),
                t.replace("            bool touchNow  = touchHit or touchNear\n            bool rebA      = touchNow",
                          "            bool touchNow  = touchHit or touchNear\n            pwTouched := touchNow\n            bool rebA      = touchNow"),
                t.replace("if (stPvA or stPvL) and not stSats\n", "if stPvA or stPvL\n"),
                t.replace("                    pwNPrep  += 1\n", "                    pwNPrep  += 1\n                    alert(\"prep\", alert.freq_all)\n"),
                t.replace("    if stSats and pwState == 1 and bar_index > pwBar\n", "    if stSats and pwState == 1\n"),
                t.replace("stTiming = input.string(\"Current\"", "stTiming = input.string(\"SATS Pullback\""),
                t.replace("            bool mtfOK   = not (pwSide == 1 ? satSkipL : satSkipS)\n", "            bool mtfOK   = true\n")]
        muts.append(t.replace(" and not na(f_stQty(pwSide, close, pwSL0))\n", "\n"))
        if k == "USDJPY":
            muts.append(t.replace('(stModeA and not stSats ? " (指値)"', '(stModeA ? " (指値)"'))
            muts.append(t.replace('stSats ? " (SATS の TP0。約定確認後もこの値)" : ', ''))
        else:
            muts.append(t.replace("    pTP   := tS\n    pvQty := pSide != 0 ? f_stQty(pSide, pPx, pSL) : na\n", "    pTP   := tS\n"))
        for i, m in enumerate(muts):
            if m == t or sx.strip(v["path"], m) is not None:
                bad.append((k, i))
    check("SQ-01 mutations (wrong pip unit, the provisional writing the touch state, Current provisional also under SATS, an alert "
          "on the prep, an order on the prep bar, SATS as default, the filter dropped, the provisional quantity gate dropped, the SATS "
          "pvQty dropped (BTC / GBPJPY / EURUSD / GBPUSD), USDJPY saying 指値 / the Current TP tail under SATS) do not strip back to "
          "443c139 in any file",
          not bad, str(bad))


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
