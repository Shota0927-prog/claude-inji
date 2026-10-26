"""XA-21 fixtures — provisional / confirmed alerts on the Gold Strategies ZoneStrategyXAU.pine (Short) and
ZoneStrategyXAULong.pine (Long) (tests/xa_build.py STRATEGY_EDITS21; the Long file = XL-1 + the same layer, tests/xal_build.py).

  AS : static on both delivered files — exact build / strip (Short -> 2550d27, Long -> d67941f), other Pine files unchanged; the
       two new inputs (default ON) and every other default kept; calc_on_every_tick = true with the Engine update, the rebound
       history state and every order call on confirmed bars only; the confirmed-bar trading block identical apart from the
       three confirmed-alert calls and the saved TP edges; every order path (SATS pull, SATS immediate, Current A / B-D) sends
       the confirmed alert right after its strategy.entry / exit with the decision's own Entry / SL / TP; the varip array
       guards (-1 = none, explicit check, prov / confirmed separate, freq_all, never in an order condition); the provisional
       block (forming tick, no order / position, session by time_close and by timenow, read-only evaluation ported verbatim
       from the GBPJPY Strategy with the Gold near distance); the message function text
  AM : models — tick sequences with Pine var rollback / varip persistence evaluated with the guard / gate expressions read
       from the delivered file; session boundaries (09:00 / 02:00, date rollover); the message values (prices, widths, RR from
       the shown prices, Entry kind, TP wording); the confirmed-bar history pick equal to the XA-20 push-then-pick; the SATS
       provisional wait evaluation equal to the confirmed decision without writes
  AU : mutations — model mutations caught; source mutations do not strip back to the pre-alert files

Evidence class: PINE_NOT_VERIFIED (TradingView compile, Strategy Tester results and realtime alert delivery are not verified here).
"""
import datetime as dt
import os
import random
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xa_build as xb            # noqa: E402
import xal_build as xl           # noqa: E402
import eu_sim as es              # noqa: E402
import xas_sim as xs             # noqa: E402

ROOT = xb.ROOT
PREV = "4eb7b0d"                 # the last commit before XA-21 (Short = 2550d27 file, Long = d67941f file)
raw = lambda p: open(os.path.join(ROOT, p), encoding="utf-8").read()
code_only, input_values, input_decls, func = es.code_only, es.input_values, es.input_decls, es.func
S, L = raw(xb.STR_PATH), raw(xl.LONG_PATH)
S0, L0 = xb.show("2550d27", xb.STR_PATH), xb.show("d67941f", xl.LONG_PATH)
FILES = {"Short": (S, S0), "Long": (L, L0)}
G = xb.show(xb.PROV_REV, xb.PROV_PATH)     # GBPJPY Strategy (currency reference)
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


def block(t, start, end):
    i = t.index(start)
    return t[i:t.index(end, i)]


MAIN_START, MAIN_END = "if is5mChart and barstate.isconfirmed\n    // (1)", "\nplot(stZones"
CONF_CALLS = {
    "pull": "                    f_stConfAlert(pwSide, close, pwSL0, pwTP0, false, true)",
    "immediate": "                        f_stConfAlert(side, close, pSL, tpRef, false, true)",
    "current": "                f_stConfAlert(side, stModeA ? oL : close, pSL, tpRef, stModeA, false)"}
GUARD_C = "    bool send = stAlertConf and array.get(gConfirmedAlertBar, 0) != time\n"
GATE_P = "bool  stPvA    = stAlertProv and is5mChart and not barstate.isconfirmed and oState == 0 and stPvSess and array.get(gProvAlertBar, 0) != time\n"
SESS_P = "bool  stPvSess = stSessOK and (not stUseSess or f_stInSession(timenow))\n"
DECLS = ("varip array<int> gProvAlertBar      = array.new_int(1, -1)", "varip array<int> gConfirmedAlertBar = array.new_int(1, -1)")
MSG = ('f_stAlertMsg(string kind, int side, float ePx, float sl, float tp, bool isLim, bool isSats) =>\n'
       '    float slW = side * (ePx - sl)\n'
       '    float tpW = side * (tp - ePx)\n'
       '    float rr  = not na(slW) and slW > 0 and not na(tpW) ? tpW / slW : na\n'
       '    int   tAt = kind == "仮" ? timenow : time_close\n'
       '    "【" + kind + "】" + syminfo.ticker + " " + (side == 1 ? "LONG" : "SHORT") +\n'
       '     "\\nEntry：" + f_stPx(ePx) + (isLim ? "（指値価格）" : "（成行参考価格）") +\n'
       '     "\\nSL：" + f_stPx(sl) +\n'
       '     "\\nTP：" + f_stPx(tp) + (isSats ? "（固定TP0）" : "（発注判断時の予定TP。最終TPは約定確認後に決定）") +\n'
       '     "\\nSL幅：" + (na(slW) ? "-" : f_stPx(slW) + "ドル") +\n'
       '     "\\nTP幅：" + (na(tpW) ? "-" : f_stPx(tpW) + "ドル") +\n'
       '     "\\nRR：" + (na(rr) ? "-" : "1:" + str.tostring(rr, "0.00")) +\n'
       '     "\\n日時：" + str.format_time(tAt, "yyyy-MM-dd HH:mm:ss", "Asia/Tokyo") + "（日本時間）" +\n'
       '     (kind == "仮" ? "\\n※未確定：5分足確定時に不成立になる場合あり" : "")\n')


# ---- static ------------------------------------------------------------------------------------------------------------
def gate_static():
    others = [p for p in os.listdir(ROOT) if p.endswith(".pine") and p not in (xb.STR_PATH, xl.LONG_PATH)]
    check("AS-01 Short == xa_build.build_strategy() (XA-1 .. XA-21) and strip_strategy21 gives 2550d27 byte for byte; Long == "
          "xal_build.build() (XL-1 + XA-21) and strip21 gives the XL-1 Long of d67941f byte for byte (strip -> the Short of 2550d27); "
          "both carry the identical alert layer; Engines, Visuals, the currency Strategies and every other Pine file unchanged since %s" % PREV,
          S == xb.build_strategy() and xb.strip_strategy21(S) == S0 and L == xl.build() and xl.strip21(L) == L0 and xl.strip(L) == S0
          and xb.build_strategy20() == S0 and xl.build1() == L0 and not [p for p in others if raw(p) != xb.show(PREV, p)])
    bad = {}
    for k, (t, t0) in FILES.items():
        iv, i0 = input_values(t), input_values(t0)
        d = {n: (i0.get(n), iv.get(n)) for n in set(iv) | set(i0) if iv.get(n) != i0.get(n)}
        dc = input_decls(t)
        if d != {"stAlertProv": (None, "true"), "stAlertConf": (None, "true")} or 'group = G_STA' not in dc["stAlertProv"] + dc["stAlertConf"] \
                or 'var string G_STA = "03 · Strategy Alerts"' not in t or "「alert() function calls only」" not in dc["stAlertProv"]:
            bad[k] = d
    check("AS-02 inputs: exactly two new ones in '03 · Strategy Alerts' — 仮アラート ON / 確定アラート ON (defaults ON, each switchable); every "
          "other default unchanged in both files (Short: Entry C / Short Only / immediate ON ...; Long: Entry D / Long Only / immediate OFF ...)",
          not bad, str(bad))
    gated = {}
    for k, (t, t0) in FILES.items():
        c = code_only(t)
        hist = block(t, "if barstate.isconfirmed\n    hTqL1 := nL1\n", "[pQL, pEL, pKL] = f_hPick(hQsL, hEsL, hKsL)\n")
        top = [l for l in c.split("\n") if re.match(r"^(hTq\w+ :=|array\.(push|remove)\(h|int hN[LS] = f_hPrune)", l)]
        main = block(t, MAIN_START, MAIN_END)
        calls = [l for l in c.split("\n") if re.search(r"\bstrategy\.(entry|exit|close|cancel)\(", l)]
        gated[k] = ("     calc_on_every_tick     = true,\n" in t and "if is5mChart and barstate.isconfirmed\n    zoneCountNow := zn.update(zoneEng, zoneCfg, zoneFeed)\n" in t
                    and c.count("zn.update(") == 1 and not top and hist.count("array.push(") == 18 and hist.count(":= n") == 6
                    and all(l.strip() in main for l in calls) and len(calls) == len([l for l in code_only(t0).split("\n") if re.search(r"\bstrategy\.(entry|exit|close|cancel)\(", l)])
                    and es.seg(t, "strategy(", "import ").replace("calc_on_every_tick     = true,", "calc_on_every_tick     = false,") == es.seg(t0, "strategy(", "import ")
                    and re.findall(r"^import .*$", t, re.M) == re.findall(r"^import .*$", t0, re.M) and t.count("request.") == t0.count("request."))
    check("AS-03 calc_on_every_tick false -> true (every other strategy() setting, the import and the request calls unchanged); forming "
          "ticks run no formal update: zn.update only under `if is5mChart and barstate.isconfirmed` (as GBPJPY), the rebound-history "
          "state (contact records hTq*, candidate prune / push) only under `if barstate.isconfirmed` (as SX-2), all 12 strategy.entry / "
          "exit / close / cancel calls (as many as before) inside the confirmed 5m block", all(gated.values()), str(gated))
    same = {}
    for k, (t, t0) in FILES.items():
        m, m0 = block(t, MAIN_START, MAIN_END), block(t0, MAIN_START, MAIN_END)
        drop = [l for l in m.split("\n") if "f_stConfAlert(" in l or l in ("    stTpUpPrev := tpUp", "    stTpDnPrev := tpDn")]
        same[k] = "\n".join(l for l in m.split("\n") if l not in drop) == m0 and len(drop) == 5
    check("AS-04 the confirmed-bar trading block (fills, Zone scan, TP / breakeven, D waits, cancels, SATS wait / pull / immediate, "
          "Current orders, sizes, session check) is byte-identical to the pre-alert file apart from the three confirmed-alert calls and "
          "the two saved TP-edge lists (stTpUpPrev / stTpDnPrev, read only by the provisional evaluation)", all(same.values()), str(same))
    paths = {}
    for k, (t, _) in FILES.items():
        m = block(t, MAIN_START, MAIN_END)
        pull = block(m, "                    strategy.entry(oEid, pwSide == 1 ? strategy.long : strategy.short, qty = q)\n", "                    pwRRPlan")
        now = block(m, "                        strategy.entry(oEid, side == 1 ? strategy.long : strategy.short, qty = nQty)\n", "                        pwP0     := ref")
        cur = block(m, "                if stModeA\n                    strategy.entry(", "    stPrev := cur")
        prep = block(m, "                if not skipRef and not na(pQty) and pwState == 0 and not pwCancelBar and not nowGo\n", "            else if not skipRef")
        fills = block(m, "    // (1)", "    // (3) ")
        paths[k] = (pull == "                    strategy.entry(oEid, pwSide == 1 ? strategy.long : strategy.short, qty = q)\n"
                           "                    strategy.exit(oXid, oEid, stop = oSL)\n" + CONF_CALLS["pull"] + "     // XA-21 確定: 引きつけの発注 (Entry は判断足の終値、SL0 / TP0 は準備時の固定値)\n"
                    and now == "                        strategy.entry(oEid, side == 1 ? strategy.long : strategy.short, qty = nQty)\n"
                               "                        strategy.exit(oXid, oEid, stop = oSL)\n" + CONF_CALLS["immediate"] + "     // XA-21 確定: 即時の発注 (Entry は判断足の終値、SL0 / TP0 は準備地点の値)\n"
                    and cur.endswith("                strategy.exit(oXid, oEid, stop = oSL)\n" + CONF_CALLS["current"] + "     // XA-21 確定: Current の発注 (A は指値価格、TP は発注判断時の予定)\n")
                    and "qty = pQty, limit = oL)" in cur and "qty = pQty)\n" in cur
                    and m.count("strategy.entry(") == 4 and m.count("f_stConfAlert(") == 3
                    and "f_stConfAlert" not in prep and "alert" not in fills
                    and "                    oSL     := pwSL0\n" in block(m, "                float q = f_stQty(pwSide, close, pwSL0)", "pwRRPlan")
                    and "                    oTP0    := pwTP0\n" in block(m, "                float q = f_stQty(pwSide, close, pwSL0)", "pwRRPlan")
                    and "                        oSL     := pSL\n" in block(m, "                    float nQty", "pwP0     := ref")
                    and "                        oTP0    := tpRef\n" in block(m, "                    float nQty", "pwP0     := ref")
                    and "                oL      := pL\n                oSL     := pSL\n" in cur.join(["", ""]) + block(m, "            else if not skipRef and not na(pQty)\n", "    stPrev := cur"))
    check("AS-05 every order path sends the confirmed alert in the branch that executes strategy.entry (not on fills / position growth): "
          "SATS pull (Entry = decision close, SL0 / TP0 of the wait = oSL / oTP0, not P0), SATS immediate (close, the prep-point SL0 / TP0 "
          "= oSL / oTP0), Current A limit (Entry = limit oL) and B / C / D market (close) with the decision SL and planned TP; 4 "
          "strategy.entry calls / 3 calls; the plain wait prep and the fill / exit handling send nothing", all(paths.values()), str(paths))
    guards = {}
    for k, (t, _) in FILES.items():
        c = code_only(t)
        fc = func(t, "f_stConfAlert(int side, float ePx, float sl, float tp, bool isLim, bool isSats) =>").rstrip("\n") + "\n"
        pv = block(t, "// ---- XA-21 仮アラート", "// ==== ZONE Strategy · Zone evaluation (end)")
        guards[k] = (all(d in t for d in DECLS) and fc == ("f_stConfAlert(int side, float ePx, float sl, float tp, bool isLim, bool isSats) =>\n" + GUARD_C +
                     "    if send\n        array.set(gConfirmedAlertBar, 0, time)\n        alert(f_stAlertMsg(\"確定\", side, ePx, sl, tp, isLim, isSats), alert.freq_all)\n    send\n")
                     and c.count("gConfirmedAlertBar") == 3 and c.count("gProvAlertBar") == 3 and code_only(pv).count("gProvAlertBar") == 2
                     and len(re.findall(r"^\s*alert\(", c, re.M)) == 2 and "na(gProv" not in c and "na(gConf" not in c and "stConfBar" not in c and "stProvBar" not in c
                     and not re.search(r"(if|and|or|not)\s*[^\n]*f_stConfAlert", c))
    check("AS-06 guards: `varip array<int> gProvAlertBar / gConfirmedAlertBar = array.new_int(1, -1)` (separate states, -1 = none sent, "
          "no initial-na comparison); the confirmed send = stAlertConf and the bar's time not yet sent -> set, then alert(..., "
          "alert.freq_all); the guard only gates the notification (the call is a statement after the orders, its result unused); "
          "exactly two alert() calls (confirmed / provisional)", all(guards.values()), str(guards))
    prov = {}
    sp_g = func(G, "f_satProvEval(float pc, float l1p, float l2p, float stbp) =>").replace("stSatsNearPx", "stSatsNearD")
    for k, (t, _) in FILES.items():
        pv = code_only(block(t, "// ---- XA-21 仮アラート", "// ==== ZONE Strategy · Zone evaluation (end)"))
        fs = func(t, "f_stProvEval() =>")
        fp = func(t, "f_satProvEval(float pc, float l1p, float l2p, float stbp) =>")
        writes = re.findall(r"^\s*(\w+)\s*:=", fs + fp, re.M)
        loc = set(re.findall(r"^\s*(?:int|float|bool|StCand|StWait|var)?\s*(\w+)\s*=(?!=)", fs + fp, re.M)) | {"side", "ePx", "sl", "tp", "tpP"}
        prov[k] = (fs == func(G, "f_stProvEval() =>") and code_only(fp) == code_only(sp_g) and set(writes) <= loc
                   and not re.search(r"strategy\.|array\.(push|set|remove|shift|clear)|map\.(put|remove)|label\.|alert\(", fs + fp)
                   and GATE_P in t and SESS_P in t and t.index(GATE_P) > t.index(MAIN_END)
                   and re.findall(r"^\s*(\w+)\s*:=", pv, re.M) == ["pSide", "pPx", "pSL", "pTP"] * 2
                   and "    array.set(gProvAlertBar, 0, time)\n    alert(f_stAlertMsg(\"仮\", pSide, pPx, pSL, pTP, not stSats and stModeA, stSats), alert.freq_once_per_bar)\n" in t
                   and "if stPvA and pSide != 0 and not na(pvQty)\n" in t and "float pvQty = pSide != 0 ? f_stQty(pSide, pPx, pSL) : na" in t
                   and "    [sS, eS, lS, tS] = f_satProvEval(close[1], satL1[1], satL2[1], satStb[1])\n" in t and "    [s0, e0, l0, t0] = f_stProvEval()\n" in t
                   and "stSessOK = not stUseSess or f_stInSession(time_close)" in t)
    check("AS-07 provisional: forming 5m tick only (not barstate.isconfirmed), no order / position at the last confirmed bar, session "
          "by the bar's close time (time_close, as the confirmed orders) AND by the sending time (timenow), not yet sent for this bar; "
          "SATS -> f_satProvEval (pull wait, immediate before a wait; a plain wait prep returns nothing), Current -> f_stProvEval; "
          "both ported from the GBPJPY Strategy (code identical; only stSatsNearPx -> the Gold stSatsNearD and the SX-n comment tags) and read-only (only their locals are "
          "assigned; no order / array / map / label / alert call); valid size required; the block writes only its locals and the "
          "provisional varip key", all(prov.values()), str(prov))
    check("AS-08 message: 【仮／確定】<ticker> LONG／SHORT, Entry (成行参考価格 / 指値価格 for Current A), SL, TP (SATS: 固定TP0 / Current: "
          "発注判断時の予定TP。最終TPは約定確認後に決定), SL幅 / TP幅 in ドル from the shown Entry / SL / TP, RR 1:x.xx = TP幅 ÷ SL幅 (not the "
          "fixed RR), 日時 in Asia/Tokyo (confirmed: the decision bar's close time; provisional: the sending time); prices / widths in "
          "syminfo.mintick digits (f_stPx); the provisional adds the 未確定 note; same text in both files",
          all(MSG in t and "f_stPx(float v) =>\n    na(v) ? \"-\" : str.tostring(v, format.mintick)\n" in t for t, _ in FILES.values()))


# ---- models ------------------------------------------------------------------------------------------------------------
def pine_expr(line):
    """the right-hand side of a delivered Pine boolean line, as Python (only the names used in the guard lines)."""
    rhs = line.split("=", 1)[1].strip()
    rhs = rhs.replace("array.get(gProvAlertBar, 0)", "gProv[0]").replace("array.get(gConfirmedAlertBar, 0)", "gConf[0]")
    rhs = rhs.replace("barstate.isconfirmed", "confirmed").replace("f_stInSession(timenow)", "insess(now)")
    return compile(rhs, "<pine>", "eval")


JST = dt.timezone(dt.timedelta(hours=9))


def ms(y, mo, d, h, mi, s=0):
    return int(dt.datetime(y, mo, d, h, mi, s, tzinfo=JST).timestamp() * 1000)


def in_session(t, sh=9, sm=0, eh=2, em=0):
    """port of f_stInSession (minutes of the JST clock in [start, end), start > end wraps midnight)."""
    x = dt.datetime.fromtimestamp(t / 1000, JST)
    mins, s, e = x.hour * 60 + x.minute, sh * 60 + sm, eh * 60 + em
    return True if s == e else (s <= mins < e) if s < e else (mins >= s or mins < e)


PV = pine_expr(GATE_P)
PS = pine_expr(SESS_P)
CG = pine_expr(GUARD_C.strip())


class Runtime:
    """one Strategy instance in realtime: var state rolled back on every execution, varip keys persistent. Each tick runs the
    confirmed 5m block (orders + confirmed alert) on the closing tick, then the provisional block — with the delivered guard /
    gate expressions."""

    def __init__(self, prov_on=True, conf_on=True, use_sess=True, variant=None):
        self.committed = dict(oState=0)
        self.gProv, self.gConf = [-1], [-1]
        if variant == "na_init":
            self.gProv, self.gConf = [None], [None]
        self.prov_on, self.conf_on, self.use_sess, self.variant = prov_on, conf_on, use_sess, variant
        self.sent, self.orders = [], []

    def _eval(self, code, env):
        if self.variant == "na_init":     # Pine: na != x is na (false) -> the first alert would be blocked
            if env["gProv"][0] is None or env["gConf"][0] is None:
                env = dict(env, gProv=[env["gProv"][0] if env["gProv"][0] is not None else "NA"], gConf=[env["gConf"][0] if env["gConf"][0] is not None else "NA"])
                if code is CG and env["gConf"][0] == "NA":
                    return False
                if code is PV and env["gProv"][0] == "NA":
                    return False
        return eval(code, {}, env)

    def tick(self, bar, close_t, now, confirmed, prov=0, order=None, commit=True, realtime=True):
        st = dict(self.committed)                                       # var rollback
        if self.variant == "var_keys":
            self.gProv, self.gConf = list(self.committed.get("gProv", [-1])), list(self.committed.get("gConf", [-1]))
        sess_ok = (not self.use_sess) or in_session(close_t)
        env = dict(stAlertProv=self.prov_on, stAlertConf=self.conf_on, is5mChart=True, confirmed=confirmed, oState=st["oState"],
                   stSessOK=sess_ok, stUseSess=self.use_sess, insess=in_session, now=now, time=bar, gProv=self.gProv, gConf=self.gConf)
        if confirmed and order is not None and st["oState"] == 0 and sess_ok:
            st["oState"] = 1
            self.orders.append((bar, order))                            # strategy.entry / exit (before and outside the guard)
            if self._eval(CG, env):
                self.gConf[0] = bar
                if realtime:
                    self.sent.append(("確定", bar, order))
        if self.variant != "time_close_only":
            pv_a = self._eval(PV, dict(env, stPvSess=self._eval(PS, env)))
        else:
            pv_a = self.prov_on and not confirmed and st["oState"] == 0 and sess_ok and self.gProv[0] != bar
        if pv_a and prov != 0:
            self.gProv[0] = bar
            if realtime:
                self.sent.append(("仮", bar, prov))
        if commit:
            if self.variant == "var_keys":
                st["gProv"], st["gConf"] = list(self.gProv), list(self.gConf)
            self.committed = st
            if st["oState"] == 1:
                self.committed = dict(st, oState=0)                     # filled and closed before the next entry bar (model)
        return self


T9 = ms(2026, 10, 26, 9, 5)       # bar 09:05-09:10 (time = open), close 09:10


def bar_ticks(rt, bar, provs, order, t_open=None, sess=True):
    """forming ticks (one per entry of provs: the provisional side seen on that tick) then the closing tick with the order decision."""
    t_open = bar if t_open is None else t_open
    close_t = t_open + 300000
    for i, p in enumerate(provs):
        rt.tick(bar, close_t, t_open + 30000 * (i + 1), False, prov=p)
    rt.tick(bar, close_t, close_t, True, order=order)
    return rt


def kinds(rt):
    return [x[0] for x in rt.sent]


def gate_model():
    a = bar_ticks(Runtime(), T9, [1, 1, 1, 1], "current")
    check("AM-01 provisional then confirmed on the same 5m bar: provisional 1, confirmed 1 (4 forming ticks with the condition on)",
          kinds(a) == ["仮", "確定"])
    b = bar_ticks(Runtime(), T9, [-1, -1], None)
    check("AM-02 provisional only and the condition broken at the close: no order, no confirmed alert", kinds(b) == ["仮"] and not b.orders)
    c = bar_ticks(Runtime(), T9, [0, 0, 0], "pull")
    check("AM-03 confirmed without any provisional (the condition only at the close): confirmed 1", kinds(c) == ["確定"])
    d = Runtime()
    d.tick(T9, T9 + 300000, T9 + 300000, True, order="immediate", commit=False)
    d.tick(T9, T9 + 300000, T9 + 300000, True, order="immediate", commit=False)
    d.tick(T9, T9 + 300000, T9 + 300000, True, order="immediate")
    check("AM-04 the confirmed branch re-executed on the same bar (3 times): confirmed alert 1, the order placed on every execution "
          "(the guard never blocks orders)", kinds(d) == ["確定"] and len(d.orders) == 3)
    e = bar_ticks(Runtime(), T9, [1, 0, 1, 0, 1, 1, 0], "pull")
    check("AM-05 the provisional condition flipping on / off within the bar: provisional 1 (no re-send), confirmed 1", kinds(e) == ["仮", "確定"])
    f = bar_ticks(Runtime(prov_on=False), T9, [1, 1], "current")
    f2 = bar_ticks(Runtime(conf_on=False), T9, [1, 1], "current")
    check("AM-06 provisional OFF / confirmed ON -> confirmed only; provisional ON / confirmed OFF -> provisional only (orders unchanged)",
          kinds(f) == ["確定"] and kinds(f2) == ["仮"] and f.orders == f2.orders == [(T9, "current")])
    g = Runtime()
    for i in range(3):
        bar_ticks(g, T9 + i * 300000, [1, 1], ["pull", "immediate", "current"][i])
    check("AM-07 each 5m bar keeps its own key (bar time): three consecutive order bars -> 仮 / 確定 once each per bar (6)",
          [(k, b) for k, b, _ in g.sent] == [(k, T9 + i * 300000) for i in range(3) for k in ("仮", "確定")])
    h = Runtime()
    for i in range(5):
        h.tick(T9 - (10 - i) * 300000, T9 - (9 - i) * 300000, T9 - (9 - i) * 300000, True, order="pull", realtime=False)
    bar_ticks(h, T9, [1], "pull")
    check("AM-08 historical bars send nothing (their keys do not block): the first realtime bar sends 仮 and 確定", kinds(h) == ["仮", "確定"])
    i_ = Runtime()
    i_.committed = dict(oState=2)
    bar_ticks(i_, T9, [1, 1], None)
    check("AM-09 with an order / position open at the last confirmed bar no provisional alert", i_.sent == [])
    # session boundaries (JST, defaults 09:00 inclusive -> 02:00 exclusive, judged by the bar close time; provisional also by now)
    D = (2026, 10, 26)
    cases = {}
    for name, (oh, om, nd) in {"08:50": (8, 50, 0), "08:55": (8, 55, 0), "09:00": (9, 0, 0), "01:50": (1, 50, 1), "01:55": (1, 55, 1),
                               "02:00": (2, 0, 1), "23:55": (23, 55, 0)}.items():
        t_open = ms(D[0], D[1], D[2] + nd, oh, om)
        rt = bar_ticks(Runtime(), t_open, [1, 1, 1], "current")
        cases[name] = tuple(kinds(rt))
    exp = {"08:50": (), "08:55": ("確定",), "09:00": ("仮", "確定"), "01:50": ("仮", "確定"), "01:55": (), "02:00": (), "23:55": ("仮", "確定")}
    check("AM-10 session (09:00 inclusive -> 02:00 exclusive, JST): bar 08:50 none; bar 08:55 (close 09:00) no provisional before "
          "09:00 but the confirmed order / alert at 09:00 (existing time_close basis); 09:00 both; 01:50 (close 01:55) both; 01:55 (close "
          "02:00) none; 02:00 none; 23:55 (close 00:00, date rollover) both", cases == exp, str(cases))
    off = bar_ticks(Runtime(use_sess=False), ms(2026, 10, 26, 3, 0), [1], "current")
    check("AM-11 session limit OFF -> both alerts at any time (03:00)", kinds(off) == ["仮", "確定"])

    # message values (port of f_stAlertMsg; AS-08 pins the Pine text)
    def px(v):
        return "-" if v is None else f"{v:.2f}"

    def msg(kind, side, e, sl, tp, lim, sats, t_ms):
        slw = None if None in (e, sl) else side * (e - sl)
        tpw = None if None in (e, tp) else side * (tp - e)
        rr = tpw / slw if slw is not None and slw > 0 and tpw is not None else None
        x = dt.datetime.fromtimestamp(t_ms / 1000, JST).strftime("%Y-%m-%d %H:%M:%S")
        return ("【" + kind + "】XAUUSD " + ("LONG" if side == 1 else "SHORT") + "\nEntry：" + px(e) + ("（指値価格）" if lim else "（成行参考価格）")
                + "\nSL：" + px(sl) + "\nTP：" + px(tp) + ("（固定TP0）" if sats else "（発注判断時の予定TP。最終TPは約定確認後に決定）")
                + "\nSL幅：" + ("-" if slw is None else px(slw) + "ドル") + "\nTP幅：" + ("-" if tpw is None else px(tpw) + "ドル")
                + "\nRR：" + ("-" if rr is None else "1:" + f"{rr:.2f}") + "\n日時：" + x + "（日本時間）"
                + ("\n※未確定：5分足確定時に不成立になる場合あり" if kind == "仮" else ""))
    m1 = msg("確定", -1, 2650.25, 2655.75, 2642.00, False, True, ms(2026, 10, 26, 9, 10))
    m2 = msg("確定", 1, 2600.00, 2595.50, 2606.75, True, False, ms(2026, 10, 26, 23, 55))
    m3 = msg("確定", -1, 2603.00, 2610.00, 2585.00, False, True, ms(2026, 10, 27, 0, 0))     # immediate: P0 2600 not shown, RR from close
    m4 = msg("仮", 1, 2601.37, 2598.00, None, False, False, ms(2026, 10, 26, 9, 2, 41))
    check("AM-12 message values: SATS pull Short close 2650.25 / SL0 2655.75 / TP0 2642.00 -> SL幅 5.50ドル, TP幅 8.25ドル, RR 1:1.50; "
          "Current A Long limit 2600.00 -> （指値価格）, 4.50 / 6.75, 1:1.50, 23:55 JST; SATS immediate Short close 2603.00 (not P0 2600) / "
          "SL0 2610 / TP0 2585 -> 7.00 / 18.00, RR 1:2.57 (from the shown prices, not the fixed 1.5), date rollover 2026-10-27 00:00:00; "
          "na TP -> '-' for TP / TP幅 / RR; provisional note",
          m1 == "【確定】XAUUSD SHORT\nEntry：2650.25（成行参考価格）\nSL：2655.75\nTP：2642.00（固定TP0）\nSL幅：5.50ドル\nTP幅：8.25ドル\nRR：1:1.50\n日時：2026-10-26 09:10:00（日本時間）"
          and "Entry：2600.00（指値価格）" in m2 and "SL幅：4.50ドル\nTP幅：6.75ドル\nRR：1:1.50" in m2 and "（発注判断時の予定TP。最終TPは約定確認後に決定）" in m2
          and "SL幅：7.00ドル\nTP幅：18.00ドル\nRR：1:2.57\n日時：2026-10-27 00:00:00" in m3
          and "TP：-（発注判断時の予定TP" in m4 and "TP幅：-\nRR：-" in m4 and m4.endswith("※未確定：5分足確定時に不成立になる場合あり"),
          "\n---\n".join((m1, m2, m3, m4)))

    # the confirmed-bar history pick (gated writes, current-bar-first) == the XA-20 push-then-pick (Gold history unchanged)
    random.seed(2121)
    same, n = True, 0
    for _ in range(300):
        nc, nz = random.choice((0, 1, 2, 3)), random.choice((0, 1, 2, 3))
        side = random.choice((1, -1))
        px0, bars = 2600.0, []
        for _ in range(40):
            o = px0
            c2 = round(o + random.uniform(-3, 3), 1)
            bars.append((o, max(o, c2) + round(random.uniform(0, 2), 1), min(o, c2) - round(random.uniform(0, 2), 1), c2))
            px0 = c2
        lines = [[round(b[3] + random.uniform(-4, 4), 1) for b in bars] for _ in range(3)]
        flags = [xs.hist18(side, bars, lines[k], nc, near=True, dist=1.0, body=random.random() < 0.5) for k in range(3)]
        committed = []
        for t in range(len(bars)):
            now = [(flags[k][t][1], t, k + 1) for k in range(3) if flags[k][t][0]]
            old = xs.pick19(committed + now, t, nz, nc)
            new = now[0] if now else xs.pick19(committed + now, t, nz, nc)
            same &= old == new
            committed = [x for x in committed + now if t - x[1] <= nz]
            n += 1
    check("AM-13 model: on confirmed bars the gated history (prune / push inside `if barstate.isconfirmed`, then the current-bar rebound "
          "first, else the latest candidate) picks the same (q, e, line) as the XA-20 push-then-pick on %d random bars (near 1.0 USD, body "
          "random, Nc / Nz 0-3) — the historical orders do not change" % n, same)

    def prov_wait(w, t_close, hh, ll, cc, pc, lines, o, skip=False):
        """port of f_satProvEval's wait branch (Gold near distance)."""
        if w.state != 1:
            return 0
        if t_close - w.t_end >= w.limit * 60000 or ((ll <= w.sl0) if w.side == 1 else (hh >= w.sl0)):
            return 0
        tchd = w.touched and not (w.tq and w.cur_bar - w.tbar > w.tqn)
        if not tchd:
            k, Lp = xs.pick(w.side, w.p0, w.sl0, pc, lines)
        else:
            k, Lp = w.tk, lines[w.tk - 1]
        rng = k != 0 and Lp is not None and ((w.sl0 < Lp < w.p0) if w.side == 1 else (w.p0 < Lp < w.sl0))
        hit = rng and ll <= Lp <= hh
        near = w.near and rng and ((ll > Lp and ll - Lp <= w.dist) if w.side == 1 else (hh < Lp and Lp - hh <= w.dist))
        ra = (hit or near) and ((cc > Lp) if w.side == 1 else (cc < Lp))
        rb = tchd and rng and ((pc <= Lp and cc > Lp) if w.side == 1 else (pc >= Lp and cc < Lp))
        bd = (not w.body) or ((cc > o) if w.side == 1 else (cc < o))
        pr = (w.sl0 < cc < w.p0) if w.side == 1 else (w.p0 < cc < w.sl0)
        return w.side if (ra or rb) and bd and not skip and pr else 0
    random.seed(2122)
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
                cc = round(pc + random.uniform(-4, 4), 1)
                o = round(pc + random.uniform(-2, 2), 1)
                hh, ll = max(o, cc) + round(random.uniform(0, 3), 1), min(o, cc) - round(random.uniform(0, 3), 1)
                lines = tuple(None if random.random() < 0.1 else round(cc + random.uniform(-6, 6), 1) for _ in range(3))
                sk = random.random() < 0.2
                w.cur_bar = 10 + i
                before = (w.state, w.touched, w.tk, w.tbar, w.n_tq, w.n_touch_prep, len(w.orders))
                for fr in (0.3, 0.7):
                    tc = round(o + (cc - o) * fr, 1)
                    prov_wait(w, xs.tb(i), max(o, tc), min(o, tc), tc, pc, lines, o, skip=sk)
                pv = prov_wait(w, xs.tb(i), hh, ll, cc, pc, lines, o, skip=sk)
                untouched &= before == (w.state, w.touched, w.tk, w.tbar, w.n_tq, w.n_touch_prep, len(w.orders))
                r = w.step(10 + i, xs.tb(i), hh, ll, cc, pc, lines, o=o, skip=sk)
                agree &= (pv != 0) == (r == 2)
                n += 1
                pc = cc
    sp = func(S, "f_satProvEval(float pc, float l1p, float l2p, float stbp) =>")
    check("AM-14 model: while a SATS wait is open, the provisional evaluation on the final OHLC equals the confirmed pull decision on %d "
          "random bars (contact expiry, body, near 1.0 USD, filter random) and writes nothing over several forming ticks; a plain wait prep "
          "(state 0, immediate OFF) returns no side" % n,
          agree and untouched and "    else if stSats and stSatsNow and pwState == 0\n" in sp and "if stSats and pwState == 1 and bar_index > pwBar" in sp,
          str((agree, untouched)))


def gate_mutation():
    rep = lambda rt: (rt.tick(T9, T9 + 300000, T9 + 300000, True, order="pull", commit=False)
                      .tick(T9, T9 + 300000, T9 + 300000, True, order="pull"))
    na0 = bar_ticks(Runtime(variant="na_init"), T9, [1], "pull")
    vk = rep(Runtime(variant="var_keys"))
    tco = Runtime(variant="time_close_only")
    bar_ticks(tco, ms(2026, 10, 26, 8, 55), [1, 1], "pull")
    check("AU-01 model mutations caught: keys initialised to na (na != time is na -> the first alerts blocked), var keys (rolled back -> the "
          "re-executed confirmed bar sends twice), the provisional session by time_close only (sends before 09:00)",
          na0.sent == [] and kinds(vk) == ["確定", "確定"] and kinds(tco)[:1] == ["仮"])
    muts = {"guard removed": S.replace(GUARD_C, "    bool send = stAlertConf\n"),
            "var keys": S.replace("varip array<int> gConfirmedAlertBar", "var array<int> gConfirmedAlertBar"),
            "na init": S.replace("array.new_int(1, -1)     // XA-21: 確定", "array.new_int(1)     // XA-21: 確定"),
            "pull call dropped": S.replace(CONF_CALLS["pull"], "                    // "),
            "immediate call dropped": S.replace(CONF_CALLS["immediate"], "                        // "),
            "prov session time_close only": S.replace(SESS_P, "bool  stPvSess = stSessOK\n"),
            "prov on confirmed": S.replace(" and not barstate.isconfirmed and oState == 0 and stPvSess", " and oState == 0 and stPvSess"),
            "engine every tick": S.replace("if is5mChart and barstate.isconfirmed\n    zoneCountNow", "if is5mChart\n    zoneCountNow"),
            "history every tick": S.replace("if barstate.isconfirmed\n    hTqL1 := nL1\n", "if true\n    hTqL1 := nL1\n"),
            "SATS P0 as Entry": S.replace("f_stConfAlert(pwSide, close, pwSL0, pwTP0, false, true)", "f_stConfAlert(pwSide, pwP0, pwSL0, pwTP0, false, true)"),
            "fixed RR": S.replace("tpW / slW : na", "stRR : na"),
            "alert on wait prep": S.replace("                    pwEv     := 1\n", "                    pwEv     := 1\n                    alert(\"prep\", alert.freq_all)\n")}
    bad = [k for k, m in muts.items() if m == S or xb.strip_strategy21(m) == S0]
    check("AU-02 source mutations (guard removed, var key, na init, the pull / immediate confirmed call dropped, provisional session "
          "without timenow, provisional on the confirmed tick, Engine / history updated every tick, P0 as the SATS Entry, the fixed RR "
          "in the message, an alert on the wait prep) do not strip back to the pre-alert file", not bad, str(bad))


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
