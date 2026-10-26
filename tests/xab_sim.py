"""XA-22 fixtures — the provisional alert at most once per candidate / wait on the Gold Strategies ZoneStrategyXAU.pine (Short)
and ZoneStrategyXAULong.pine (Long) (tests/xa_build.py STRATEGY_EDITS22, the same layer on both files; tests/xal_build.py).

  BS : static on both delivered files — exact build / strip (-> the XA-21 files of 61c48fb), other Pine files unchanged; inputs,
       strategy() settings, message, session, confirmed alert and the per-bar provisional key unchanged; the confirmed-bar
       trading block identical apart from the four key-release calls (after the formal pull / immediate / Current order and the
       formal wait prep); the candidate key (Track | path | side | wait = pwBar for the SATS pull, -1 otherwise; no bar time /
       bar_index / prices); the key list is varip, written only where the provisional alert() is called (and released only by
       Track); the read-only evaluations changed only by returning the path / Track
  BM : models — tick sequences (var rollback, varip persistence) with the delivered send condition and key function: same bar
       flips, the next bar, a wait over several bars with re-touches / re-rebounds, A -> B -> A, a different candidate, a formal
       new wait, release after a formal order, the per-bar limit, the confirmed alert / orders never suppressed
  BU : mutations — model mutations caught; source mutations do not strip back to 61c48fb
Runs on the XA-22 layer of the delivered files (the later XA-23 labels reverted exactly; tests/xac_sim.py).

Evidence class: PINE_NOT_VERIFIED (TradingView compile and realtime alert delivery are not verified here).
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xa_build as xb            # noqa: E402
import xal_build as xl           # noqa: E402
import eu_sim as es              # noqa: E402

ROOT = xb.ROOT
PREV = "61c48fb"                 # XA-21
raw = lambda p: open(os.path.join(ROOT, p), encoding="utf-8").read()
code_only, input_values, func = es.code_only, es.input_values, es.func
S, L = xb.strip_strategy23(raw(xb.STR_PATH)) or "", xl.strip23(raw(xl.LONG_PATH)) or ""   # the XA-22 layer (XA-23 reverted exactly; tests/xac_sim.py)
S0, L0 = xb.show(PREV, xb.STR_PATH), xb.show(PREV, xl.LONG_PATH)
FILES = {"Short": (S, S0), "Long": (L, L0)}
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


def block(t, start, end):
    i = t.index(start)
    return t[i:t.index(end, i)]


MAIN_START, MAIN_END = "if is5mChart and barstate.isconfirmed\n    // (1)", "\nplot(stZones"
PV_START, PV_END = "// ---- XA-21 仮アラート", "// ==== ZONE Strategy · Zone evaluation (end)"
SEND = "if stPvA and pSide != 0 and not na(pvQty) and not array.includes(gProvKeys, pvKey)\n"
KEYLINE = 'string pvKey = pSide != 0 ? f_stPvKey(pTrk, pPath, pSide, pPath == 1 ? pwBar : -1) : ""\n'
KEYFN = ('f_stPvKey(int trk, int path, int side, int wbar) =>\n'
         '    str.tostring(trk) + "|" + str.tostring(path) + "|" + str.tostring(side) + "|" + str.tostring(wbar)\n')
RELFN = ('f_stPvRelease(int trk) =>\n'
         '    int    n   = array.size(gProvKeys)\n'
         '    int    cnt = 0\n'
         '    string pre = str.tostring(trk) + "|"\n'
         '    if n > 0\n'
         '        for i = n - 1 to 0\n'
         '            if str.startswith(array.get(gProvKeys, i), pre)\n'
         '                array.remove(gProvKeys, i)\n'
         '                cnt += 1\n'
         '    cnt\n')
REL_AFTER = {   # each release call follows exactly this line (formal order / formal wait prep of that Track)
    "pull": ("                    f_stConfAlert(pwSide, close, pwSL0, pwTP0, false, true)", "                    f_stPvRelease(pwTrack)"),
    "immediate": ("                        f_stConfAlert(side, close, pSL, tpRef, false, true)", "                        f_stPvRelease(c.track)"),
    "prep": ("                    pwNPrep  += 1", "                    f_stPvRelease(c.track)"),
    "current": ("                f_stConfAlert(side, stModeA ? oL : close, pSL, tpRef, stModeA, false)", "                f_stPvRelease(c.track)")}


# ---- static ------------------------------------------------------------------------------------------------------------
def gate_static():
    others = [p for p in os.listdir(ROOT) if p.endswith(".pine") and p not in (xb.STR_PATH, xl.LONG_PATH)]
    check("BS-01 Short == xa_build.build_strategy() (XA-1 .. XA-22) and strip_strategy22 gives the XA-21 Short of %s byte for byte; Long == "
          "xal_build.build() and strip22 gives the XA-21 Long of %s; the same XA-22 layer on both; every other Pine file unchanged" % (PREV, PREV),
          S == xb.build_strategy22() and xb.strip_strategy22(S) == S0 and xb.build_strategy21() == S0
          and L == xl.build22() and xl.strip22(L) == L0 and xl.build21() == L0 and not [p for p in others if raw(p) != xb.show(PREV, p)])
    keep = {}
    for k, (t, t0) in FILES.items():
        keep[k] = (input_values(t) == input_values(t0) and es.seg(t, "strategy(", "import ") == es.seg(t0, "strategy(", "import ")
                   and all(func(t, h) == func(t0, h) for h in ("f_stAlertMsg(", "f_stConfAlert(", "f_stInSession(", "f_stQty(int side, float ref, float sl) =>",
                                                               "f_stTp(", "f_satHist(int side, float L, int q) =>"))
                   and "bool  stPvA    = stAlertProv and is5mChart and not barstate.isconfirmed and oState == 0 and stPvSess and array.get(gProvAlertBar, 0) != time\n" in t
                   and "bool  stPvSess = stSessOK and (not stUseSess or f_stInSession(timenow))\n" in t
                   and "    array.set(gProvAlertBar, 0, time)\n" in t and "    alert(f_stAlertMsg(\"仮\", pSide, pPx, pSL, pTP, not stSats and stModeA, stSats), alert.freq_once_per_bar)\n" in t
                   and "varip array<int> gProvAlertBar      = array.new_int(1, -1)" in t and "varip array<int> gConfirmedAlertBar = array.new_int(1, -1)" in t)
    check("BS-02 unchanged: every input / default, strategy() settings, the message text, the confirmed alert (f_stConfAlert, its own "
          "varip key), the session check, the per-5m-bar provisional gate / key (gProvAlertBar, still once per bar), size / TP / "
          "history functions", all(keep.values()), str(keep))
    same = {}
    for k, (t, t0) in FILES.items():
        m, m0 = block(t, MAIN_START, MAIN_END), block(t0, MAIN_START, MAIN_END)
        lines = m.split("\n")
        rel = [i for i, l in enumerate(lines) if "f_stPvRelease(" in l]
        pos_ok = sorted(lines[i - 1].split("     //")[0] + "\n" + lines[i].split("     //")[0] for i in rel) == sorted(a + "\n" + b for a, b in REL_AFTER.values())
        same[k] = "\n".join(l for l in lines if "f_stPvRelease(" not in l) == m0 and len(rel) == 4 and pos_ok
    check("BS-03 the confirmed-bar trading block (orders, waits, fills, TP / breakeven, cancels, sizes, session) is byte-identical to "
          "XA-21 apart from four release calls, each right after a formal event of that Track: the SATS pull order (pwTrack), the SATS "
          "immediate order, the formal wait prep and the Current order (c.track)", all(same.values()), str(same))
    keys = {}
    for k, (t, t0) in FILES.items():
        c = code_only(t)
        pv = code_only(block(t, PV_START, PV_END))
        kl = KEYLINE.split("=", 1)[1]
        keys[k] = (KEYFN in t and RELFN in t and KEYLINE in t and SEND in t
                   and not re.search(r"\btime\b|bar_index|close|pPx|pSL|pTP|pvQty", kl)
                   and "varip array<string> gProvKeys = array.new_string()" in t and c.count("gProvKeys") == 8
                   and code_only(func(t, "f_stPvRelease(int trk) =>")).count("gProvKeys") == 3 and pv.count("gProvKeys") == 4
                   and "    array.push(gProvKeys, pvKey)\n    if array.size(gProvKeys) > %d\n        array.shift(gProvKeys)\n" % xb.PV_KEEP in t
                   and pv.index("array.push(gProvKeys") > pv.index(SEND.strip()) and pv.index("array.push(gProvKeys") < pv.index("alert(f_stAlertMsg")
                   and not re.search(r"strategy\.|\bpw\w+\s*:=|\bo[A-Z]\w*\s*:=|map\.|stUsed", func(t, "f_stPvRelease(int trk) =>") + func(t, "f_stPvKey(")))
    check("BS-04 key = \"Track|path|side|wait\" (path 1 SATS pull with wait = pwBar fixed at the wait start, 2 SATS immediate, 3 Current, "
          "wait -1 otherwise; no bar time / bar_index / Entry / SL / TP); `varip array<string> gProvKeys` written only (a) in the send "
          "branch (push right before alert(), at most %d keys, oldest dropped) and (b) by f_stPvRelease (removes that Track's keys; touches "
          "no order / wait / Track state); sent = per-bar gate AND the key not yet sent" % xb.PV_KEEP, all(keys.values()), str(keys))
    rd = {}
    for k, (t, t0) in FILES.items():
        fs, fs0 = func(t, "f_stProvEval() =>"), func(t0, "f_stProvEval() =>")
        fp, fp0 = func(t, "f_satProvEval(float pc, float l1p, float l2p, float stbp) =>"), func(t0, "f_satProvEval(float pc, float l1p, float l2p, float stbp) =>")
        ch = sorted(es.changed_code(fs0 + fp0, fs + fp))
        rd[k] = (ch == sorted(["[side, ePx, sl, tpP]", "[side, ePx, sl, tpP, trk]", "int   trk = -1     // XA-22: 選んだ候補の Track ID", "trk := c.track",
                               "int   path = 0", "int   trk  = -1", "path := 1", "trk  := pwTrack", "path := 2", "trk  := r0",
                               "[s0, e0, l0, t0] = f_stProvEval()", "[s0, e0, l0, t0, r0] = f_stProvEval()",
                               "[side, ePx, sl, tp]", "[side, ePx, sl, tp, path, trk]"])
                 and not re.search(r"strategy\.|array\.(push|set|remove|shift|clear)|map\.(put|remove)|label\.|alert\(", fs + fp))
    check("BS-05 the read-only evaluations change only by returning the candidate's Track (Current: the chosen c.track) and path (SATS "
          "pull: pwTrack, immediate: the signal's Track); their conditions and values are unchanged and they still write nothing",
          all(rd.values()), str(rd))


# ---- models ------------------------------------------------------------------------------------------------------------
def pine_cond(line):
    rhs = line.strip()[3:]
    rhs = rhs.replace("not na(pvQty)", "pvQty is not None").replace("not array.includes(gProvKeys, pvKey)", "pvKey not in gProvKeys")
    return compile(rhs, "<pine>", "eval")


SENDC = pine_cond(SEND)


def pv_key(trk, path, side, wbar):
    """port of f_stPvKey (BS-04 pins the Pine text)."""
    return f"{trk}|{path}|{side}|{wbar}"


class Runtime:
    """realtime Strategy: var state rolled back each execution; varip gProvAlertBar / gProvKeys / gConfirmedAlertBar persistent."""

    def __init__(self, variant=None, prov_on=True):
        self.committed = dict(oState=0, pwBar=None)
        self.gProv, self.gConf, self.keys = [-1], [-1], []
        self.sent, self.orders = [], []
        self.variant, self.prov_on = variant, prov_on

    def release(self, trk):
        if self.variant == "no_release":
            return
        self.keys[:] = [k for k in self.keys if not k.startswith(f"{trk}|")]

    def tick(self, bar, confirmed, cand=None, event=None, commit=True):     # var state is committed only on the closing tick
        """cand = (path, side, track) seen by the provisional evaluation on this forming tick (None = condition off);
        event = formal event at the close: ('order', path, side, track) / ('prep', side, track) / None."""
        st = dict(self.committed)
        if self.variant == "var_keys":
            self.keys = list(st.get("keys", []))
        if confirmed and event is not None and st["oState"] == 0:
            if event[0] == "order":
                st["oState"] = 1
                self.orders.append((bar, event))
                if self.gConf[0] != bar:                                     # XA-21 confirmed alert (own key)
                    self.gConf[0] = bar
                    self.sent.append(("確定", bar, event[3]))
                self.release(event[3])
                st["pwBar"] = None if event[1] == 1 else st["pwBar"]
            else:
                st["pwBar"] = bar                                            # the wait is fixed at its prep bar
                self.release(event[2])
        stPvA = self.prov_on and not confirmed and st["oState"] == 0 and self.gProv[0] != bar
        if cand is not None:
            path, side, trk = cand
            wbar = st["pwBar"] if path == 1 else -1
            key = pv_key(trk, path, side, bar if self.variant == "bar_key" else wbar)
            env = dict(stPvA=stPvA, pSide=side, pvQty=1.0, pvKey=key, gProvKeys=self.keys)
            ok = eval(SENDC, {}, env) if self.variant != "bar_only" else stPvA
            if ok:
                self.gProv[0] = bar
                self.keys.append(key)
                if len(self.keys) > xb.PV_KEEP:
                    self.keys.pop(0)
                self.sent.append(("仮", bar, key))
            elif self.variant == "record_on_eval" and key not in self.keys:
                self.keys.append(key)                                        # mutation: recorded although not sent
        if commit and confirmed:                                             # forming ticks: var state rolled back (varip kept)
            if self.variant == "var_keys":
                st["keys"] = list(self.keys)
            self.committed = st
            if st["oState"] == 1:
                self.committed = dict(st, oState=0)
        return self


B = 1000


def prov(rt, kind=None):
    return [s for s in rt.sent if s[0] == ("仮" if kind is None else kind)]


def run_bar(rt, bar, cands, event=None):
    for cd in cands:
        rt.tick(bar, False, cand=cd)
    rt.tick(bar, True, event=event)
    return rt


def gate_model():
    X = (3, -1, 7)                   # Current, Short, Track 7
    a = run_bar(Runtime(), B, [X, None, X, None, X])
    check("BM-01 (1) the same bar with the condition on / off / on: provisional 1", len(prov(a)) == 1)
    b = Runtime()
    run_bar(b, B, [X, X], None)                   # close: no order (confirmed condition not met)
    run_bar(b, B + 1, [X, X, X], None)            # next bar: the same candidate again
    run_bar(b, B + 2, [None, X], None)
    check("BM-02 (2) provisional, no order at the close, the same candidate on the next bars: no re-send (1 in total)", len(prov(b)) == 1)
    c = Runtime()
    run_bar(c, B, [], ("prep", -1, 7))            # formal wait on Track 7 prepared at bar B
    W = (1, -1, 7)
    for i in range(1, 8):                         # the wait over 7 bars: re-touch / re-rebound, condition on and off
        run_bar(c, B + i, [W, None, W] if i % 2 else [None, W], None)
    check("BM-03 (3) one SATS wait over 7 bars with repeated touches / rebounds (condition on / off): provisional 1 in total "
          "(key Track 7 | pull | Short | wait bar %d)" % B, len(prov(c)) == 1 and prov(c)[0][2] == pv_key(7, 1, -1, B))
    d = Runtime()
    Y = (3, -1, 9)
    run_bar(d, B, [X], None)
    run_bar(d, B + 1, [Y], None)
    run_bar(d, B + 2, [X, Y], None)
    check("BM-04 (4a) a different candidate (Track 9) gets its first provisional; switching back to Track 7 (A -> B -> A) re-sends "
          "nothing", [s[2] for s in prov(d)] == [pv_key(7, 3, -1, -1), pv_key(9, 3, -1, -1)])
    e = Runtime()
    run_bar(e, B, [], ("prep", -1, 7))
    run_bar(e, B + 1, [W], None)                  # first wait: provisional
    run_bar(e, B + 2, [W], None)                  # (wait later expires: no formal event, its key never matches again)
    run_bar(e, B + 60, [], ("prep", -1, 7))       # a new formal wait on the same Track after the old one ended
    run_bar(e, B + 61, [W], None)
    check("BM-05 (4b) a formal new wait on the same Track (new pwBar) gets its first provisional again (2 in total)",
          [s[2] for s in prov(e)] == [pv_key(7, 1, -1, B), pv_key(7, 1, -1, B + 60)])
    f = Runtime()
    run_bar(f, B, [X], None)
    run_bar(f, B + 1, [], ("order", 3, -1, 7))    # formal Current order on Track 7 (e.g. an A limit, later cancelled)
    run_bar(f, B + 5, [X], None)
    check("BM-06 (4c) after a formal order on the Track the key is released: a later re-qualification is a new candidate",
          len(prov(f)) == 2)
    g = Runtime()
    run_bar(g, B, [X, X], ("order", 3, -1, 7))
    h = Runtime()
    run_bar(h, B, [None], ("order", 3, -1, 7))
    k = Runtime()
    run_bar(k, B, [], ("prep", -1, 7))
    run_bar(k, B + 1, [W], None)
    run_bar(k, B + 2, [W, W], ("order", 1, -1, 7))   # pull: provisional already sent -> the confirmed alert still comes
    check("BM-07 (5) the provisional keys never suppress the confirmed alert or the order: provisional + confirmed on the same bar; "
          "confirmed without provisional; a wait whose provisional was sent bars earlier still sends its confirmed alert and orders",
          [s[0] for s in g.sent] == ["仮", "確定"] and [s[0] for s in h.sent] == ["確定"] and len(h.orders) == 1
          and [s[0] for s in k.sent] == ["仮", "確定"] and len(k.orders) == 1)
    m = Runtime()
    run_bar(m, B, [X, Y], None)
    run_bar(m, B + 1, [Y], None)
    check("BM-08 the per-bar limit stays: two candidates on one bar -> 1 provisional; the blocked one is not recorded and gets its "
          "first provisional on the next bar", [s[2] for s in prov(m)] == [pv_key(7, 3, -1, -1), pv_key(9, 3, -1, -1)])
    n = Runtime(prov_on=False)
    run_bar(n, B, [X], None)
    n.prov_on = True
    run_bar(n, B + 1, [X], None)
    check("BM-09 a key is recorded only when the provisional alert() is called (alert OFF records nothing)", len(prov(n)) == 1 and n.sent[0][1] == B + 1)
    q = Runtime()
    for i in range(xb.PV_KEEP + 5):
        run_bar(q, B + i, [(3, 1, 100 + i)], None)
    check("BM-10 the key list keeps at most %d keys (oldest dropped)" % xb.PV_KEEP, len(q.keys) == xb.PV_KEEP and q.keys[0] == pv_key(105, 3, 1, -1))


def gate_mutation():
    def two_bars(v):
        rt = Runtime(variant=v)
        run_bar(rt, B, [(3, -1, 7)], None)
        run_bar(rt, B + 1, [(3, -1, 7)], None)
        return len(prov(rt))
    nr = Runtime(variant="no_release")
    run_bar(nr, B, [(3, -1, 7)], None)
    run_bar(nr, B + 1, [], ("order", 3, -1, 7))
    run_bar(nr, B + 5, [(3, -1, 7)], None)
    ro = Runtime(variant="record_on_eval")
    run_bar(ro, B, [(3, -1, 7), (3, -1, 9)], None)
    run_bar(ro, B + 1, [(3, -1, 9)], None)
    check("BU-01 model mutations caught: per-bar key only (XA-21) re-sends on the next bar, a key containing the bar re-sends, var keys "
          "(rolled back) re-send, no release blocks the re-qualified candidate after an order, recording on evaluation (not on send) "
          "loses the blocked candidate's first alert",
          two_bars("bar_only") == 2 and two_bars("bar_key") == 2 and two_bars("var_keys") == 2 and len(prov(nr)) == 1 and len(prov(ro)) == 1)
    muts = {"bar time in key": S.replace("f_stPvKey(pTrk, pPath, pSide, pPath == 1 ? pwBar : -1)", "f_stPvKey(pTrk, pPath, pSide, time)"),
            "var keys": S.replace("varip array<string> gProvKeys", "var array<string> gProvKeys"),
            "no key check": S.replace(SEND, "if stPvA and pSide != 0 and not na(pvQty)\n"),
            "no record": S.replace("    array.push(gProvKeys, pvKey)\n", ""),
            "no release on prep": S.replace("                    f_stPvRelease(c.track)     // XA-22: 正式な待機準備", "                    // XA-22: 正式な待機準備"),
            "pull key without wait": S.replace("pPath == 1 ? pwBar : -1", "-1")}
    bad = [k for k, m in muts.items() if m == S or xb.strip_strategy22(m) == S0]
    check("BU-02 source mutations (bar time in the key, var keys, no key check, no record, no release on the wait prep, the pull key "
          "without the wait) do not strip back to %s" % PREV, not bad, str(bad))


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
