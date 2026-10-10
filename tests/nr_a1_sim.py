"""NR-A1 fixtures — non-repainting Accum 1H / 4H / D in ZoneVisualPractical.pine.

  NA  static : exact transform of a916283; the local copy == the Library text with ONLY the renames and the removal of
               the `if barstate.isconfirmed` guard (+ de-indent of its body); outputs [1] inside the HTF context;
               HTF branch lookahead_on, same / lower TF keeps the original request; NR-S1 / FVG / Engine untouched
  NF  model  : Python port of the REAL Library formation (f_accumBoxCore / f_accumBoxState / f_accumDetectProvisional /
               accumPack) evaluated tick by tick inside HTF bars, compared in 5 modes:
                 old_hist     lookahead_off historical (HTF k final values on the 5M bar whose close >= C_k)
                 old_rt_ok    lookahead_off realtime, request-side barstate.isconfirmed TRUE on the closing tick
                 old_rt_fail  lookahead_off realtime, request-side barstate.isconfirmed never TRUE (unsupported)
                 new_hist / new_rt   guard removed + outputs [1] + lookahead_on
               and fed through the Engine edge rule (ZoneEnginePractical.pine 1258-1266).
  NT  TFs    : 1H / 4H / D contexts are independent (separate request call sites); same-5M-bar updates keep their own
               IDs / Hi / Lo; delays from the real HTF boundaries (continuous, daily break, weekend, missing 5M slot,
               daily close).

Model limits (reported as unverified, not PASS): Pine's exact warm-up / na handling of ta.highest / ta.lowest / ta.atr
on the first bars, TradingView's HTF session alignment, and the timing of the request-side confirmed tick are modelled,
not observed. Model PASS is not a TradingView PASS.
"""
import difflib
import math
import os
import random
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nr_a1_build as na              # noqa: E402
import nr_s1_build as nb              # noqa: E402
import fvg_re10045_sim as fr          # noqa: E402

ROOT = na.ROOT
CUR = open(os.path.join(ROOT, "ZoneVisualPractical.pine"), encoding="utf-8").read()
CUR = __import__("rnv_build").strip_rnv(CUR) or CUR  # RN-1 V1 stripped -> 6e554b2 text (delta pinned by rnv_sim)
CUR = __import__("zp_overlap_build").strip_zpo(CUR) or CUR  # ZONE-P overlap display stripped -> 11b2b4e text (delta pinned by zp_overlap_sim)
ENG = open(na.ENGINE, encoding="utf-8").read()
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


def git_show(rev, path="ZoneVisualPractical.pine"):
    return subprocess.run(["git", "-C", ROOT, "show", f"{rev}:{path}"], capture_output=True, text=True).stdout


def code_only(src):
    return "\n".join(l for l in src.split("\n") if not l.lstrip().startswith("//"))


BASE = git_show(na.NRA_BASE_REV)
BLK = CUR[CUR.index(na.NRA_BEGIN):CUR.index("\n", CUR.index(na.NRA_END)) + 1] if CUR.count(na.NRA_BEGIN) == 1 else ""
BC = code_only(BLK)


# ============================================================================
# NA : static
# ============================================================================
def gate_static():
    check("NA-01 current Visual == nra_transform(a916283) exactly (one NR-A1 block + the 3 Accum request statements)",
          bool(BASE) and na.nra_transform(BASE, ENG) == CUR)
    check("NA-02 removing the NR-A1 block and reverting the 3 edits gives a916283 byte-for-byte (Swing NR-S1, MA, Break, "
          "ZoneFeed, zn.update, FVG A / B / C, drawing unchanged)", na.strip_nra(CUR) == BASE)
    check("NA-03 NR-A1 block placed immediately before the Accum source declarations", (BLK + "\n" + na.NRA_ANCHOR) in CUR)
    # independent machine diff: Library text (renamed) vs the copy in the block
    core, state, prov, pack = na.library_spans(ENG)
    lib = core + "\n" + state + "\n" + prov + "\n" + pack
    for a, b in na.RENAMES:
        lib = lib.replace(a, b)
    copy = BLK[BLK.index("f_nraAccumBoxCore("):BLK.index("f_nraAccumConfirmed(")].rstrip("\n") + "\n"
    diff = [d for d in difflib.ndiff(lib.split("\n"), copy.split("\n")) if d[:1] in "+-"]
    removed = [d[2:] for d in diff if d.startswith("- ")]
    added = [d[2:] for d in diff if d.startswith("+ ")]
    gate_body = removed[1:]
    check("NA-04 local copy vs Library (after the 4 renames): the ONLY differences are the removed `if barstate.isconfirmed` "
          "line and its body de-indented by 4 spaces (formation, Hi / Lo, ID = time, provisional byte-identical)",
          removed[:1] == ["    if barstate.isconfirmed"] and len(gate_body) == len(added) == 9
          and all(r.startswith("        ") and r[4:] == a for r, a in zip(gate_body, added)), f"removed={removed} added={added}")
    check("NA-05 renames are exactly the 4 local names; no Library function name is redefined; the copy calls only its own "
          "f_nra* helpers", all(x in BC for x in ("f_nraAccumBoxCore(", "f_nraAccumBoxState(", "f_nraAccumDetectProvisional(",
                                                    "f_nraAccumPack(")) and "export" not in BC
          and not re.search(r"(?<![\w.])f_accum\w*\(|(?<![\w.])accumPack\(", BC))
    check("NA-06 the 3 outputs are taken at [1] INSIDE the HTF context (wrapper used only as the request expression)",
          "    [_u, _l, _i] = f_nraAccumPack(" in BC and "    [_u[1], _l[1], _i[1]]" in BC
          and code_only(CUR).count("f_nraAccumConfirmed(") == 2)
    check("NA-07 HTF branch (TF > chart TF): request(f_nraAccumConfirmed, lookahead_on); same / lower TF: the original "
          "zn.accumPack + lookahead_off; exactly 2 request call sites in the block",
          "if timeframe.in_seconds(tf) > timeframe.in_seconds()\n        [_a, _b, _c] = request.security(syminfo.tickerid, tf, f_nraAccumConfirmed(" in BC
          and "provMult), lookahead = barmerge.lookahead_on)" in BC and "    else\n        [_a, _b, _c] = request.security(syminfo.tickerid, tf, zn.accumPack(" in BC
          and "provMult), lookahead = barmerge.lookahead_off)" in BC and BC.count("request.security(") == 2)
    cc = code_only(CUR)
    calls = re.findall(r"\[_a(\d)h, _a\1l, _a\1i\] = f_nraAccum\(accTf(\d),\n\s+usePortedAccum, accumRangeLen, accumBaseLen, "
                       r"accumAtrLen, accumMinUpperCloses, accumMinLowerCloses,\n\s+accumMaxSameColorRun, accumAtrMult, "
                       r"accumBarRatioMax, accumDriftMax, accLen(\d), accMult\)", cc)
    check("NA-08 3 separate f_nraAccum call sites (TF #1 / #2 / #3, each its own accTf / accLen) -> 3 separate request "
          "contexts and var instances; no shared state", calls == [("1", "1", "1"), ("2", "2", "2"), ("3", "3", "3")], str(calls))
    w = BC[BC.index("f_nraAccumConfirmed("):]
    check("NA-09 no barstate anywhere in the NR-A1 block; no var / array in the wrapper or f_nraAccum (var only inside the "
          "copied f_nraAccumBoxState / f_nraAccumPack)", "barstate" not in BC and not re.search(r"\bvar\b|array\.", w)
          and BC.count("var ") == 4)
    check("NA-10 RE10045 lint clean for the NR-A1 block", fr.lint_eager_guards(BC) == [])
    check("NA-11 request call sites: 11 -> 10 (3 Accum statements replaced by 2 call sites in the block); inputs unchanged",
          len(re.findall(r"request\.\w+\(", code_only(BASE))) == 11 and len(re.findall(r"request\.\w+\(", cc)) == 10
          and re.findall(r"^\w+\s*=\s*input\..*$", CUR, re.M) == re.findall(r"^\w+\s*=\s*input\..*$", BASE, re.M))
    eng = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", na.NRA_BASE_REV, "--",
                          "ZoneEnginePractical.pine", "ZoneEnginePracticalAuthority.pine", "SignalEnginePractical.pine",
                          "PracticalZoneStrategy_LONG.pine", "PracticalZoneStrategy_SHORT.pine"]
                         + [f for f in os.listdir(ROOT) if f.startswith("Practical") and f.endswith("Harness.pine")],
                         capture_output=True, text=True).stdout.strip()
    check("NA-12 Engine / Library source / SignalEngine / Strategy / Harness unchanged vs a916283; import still /2",
          eng == "" and re.findall(r"^import .*$", cc, re.M) == ["import sekine3310/ZoneEnginePractical/2 as zn"], eng)
    for b, e in ((nb.NRS_BEGIN, nb.NRS_END), ("// ==== FVG Batch A (begin) ", "// ==== FVG Batch A (end) "),
                 ("// ==== FVG Batch B (begin) ", "// ==== FVG Batch B (end) "), ("// ==== FVG Batch C (begin) ", "// ==== FVG Batch C (end) ")):
        blk = lambda s: s[s.index(b):s.index("\n", s.index(e)) + 1]
        check(f"NA-13 {b.strip()[8:-8]} block byte-identical to a916283", blk(CUR) == blk(BASE))


# ============================================================================
# Python port of the Library Accum (ZoneEnginePractical.pine 528-647)
# ============================================================================
P = dict(rangeLen=10, baseLen=20, atrLen=14, minUpper=4, minLower=4, maxRun=4, atrMult=2.5, barRatioMax=0.70,
         driftMax=0.30, provLen=20, provMult=1.2)
NA_ = None


def highest(xs, n):
    return max(xs[-n:]) if len(xs) >= n else NA_


def lowest(xs, n):
    return min(xs[-n:]) if len(xs) >= n else NA_


class Ctx:
    """one request context (one TF): committed history + var state; evaluate(bar) = one Pine execution on (o,h,l,c)."""

    def __init__(self, p, gate_mode):
        self.p, self.gate_mode = p, gate_mode
        self.o, self.h, self.l, self.c, self.t = [], [], [], [], []
        self.rma = {}                    # length -> committed RMA value
        self.rma_n = {}                  # length -> committed TR history count for the SMA seed
        self.tr_hist = []
        self.isacc_hist, self.qacc_hist, self.qnew_hist, self.qhi_hist, self.qlo_hist = [], [], [], [], []
        self.var = (NA_, NA_, NA_)       # _top, _bot, _sid
        self.qsid = NA_

    def _atr(self, length, tr):
        prev = self.rma.get(length)
        trs = self.tr_hist + [tr]
        if prev is None:
            return sum(trs[-length:]) / length if len(trs) >= length else NA_
        return (tr + (length - 1) * prev) / length

    def evaluate(self, o, h, l, c, t, gate):
        p = self.p
        O, H, L, C = self.o + [o], self.h + [h], self.l + [l], self.c + [c]
        tr = h - l if not self.c else max(h - l, abs(h - self.c[-1]), abs(l - self.c[-1]))
        # ---- f_accumBoxCore -------------------------------------------------
        atr = self._atr(p["atrLen"], tr)
        bt = [max(a, b) for a, b in zip(O, C)]
        bb = [min(a, b) for a, b in zip(O, C)]
        rh, rl = highest(bt, p["rangeLen"]), lowest(bb, p["rangeLen"])
        n = len(C)
        if rh is NA_ or rl is NA_ or n < p["rangeLen"]:
            isacc = False
        else:
            rnow, rmid = rh - rl, (rh + rl) * 0.5
            up = lo = bull = bear = mbull = mbear = 0
            for i in range(p["rangeLen"]):
                ci, oi = C[n - 1 - i], O[n - 1 - i]
                up += 1 if ci > rmid else 0
                lo += 1 if ci < rmid else 0
                if ci > oi:
                    bull, bear = bull + 1, 0
                elif ci < oi:
                    bear, bull = bear + 1, 0
                else:
                    bull = bear = 0
                mbull, mbear = max(mbull, bull), max(mbear, bear)
            smid = (O[n - p["rangeLen"]] + C[n - p["rangeLen"]]) * 0.5
            emid = (o + c) * 0.5
            drift = abs(emid - smid)
            c_atr = atr is not NA_ and atr > 0 and rnow <= atr * p["atrMult"]
            rshort = rh - rl
            rbh, rbl = highest(bt, p["baseLen"]), lowest(bb, p["baseLen"])
            rbase = NA_ if rbh is NA_ else rbh - rbl
            c_bar = rbase is not NA_ and rbase > 0 and rshort <= rbase * p["barRatioMax"]
            c_bal = up >= p["minUpper"] and lo >= p["minLower"]
            c_drift = rnow > 0 and (drift / rnow) <= p["driftMax"]
            c_run = mbull <= p["maxRun"] and mbear <= p["maxRun"]
            isacc = c_atr and c_bar and c_bal and c_drift and c_run
        # ---- f_accumBoxState ------------------------------------------------
        ah, al = highest(bt, p["rangeLen"]), lowest(bb, p["rangeLen"])
        prev_acc = self.isacc_hist[-1] if self.isacc_hist else False
        is_start = isacc and not prev_acc
        top, bot, sid = self.var
        if gate:
            if is_start:
                top, bot, sid = ah, al, t
            if isacc:
                b1, b2 = max(o, c), min(o, c)
                top = max(b1 if top is NA_ else top, b1)
                bot = min(b2 if bot is NA_ else bot, b2)
        # ---- f_accumDetectProvisional + accumPack provisional -----------------
        hh, ll = highest(H, p["provLen"]), lowest(L, p["provLen"])
        atrq = self._atr(p["provLen"], tr) if p["provLen"] != p["atrLen"] else atr
        qacc = atrq is not NA_ and atrq > 0 and hh is not NA_ and (hh - ll) <= atrq * p["provMult"]
        qprev = self.qacc_hist[-1] if self.qacc_hist else False
        qnew = qacc and not qprev
        qsid = self.qsid
        if not qprev:
            qsid = NA_
        if self.qnew_hist and self.qnew_hist[-1]:
            qsid = self.t[-1]
        qhi_prev = self.qhi_hist[-1] if self.qhi_hist else NA_
        qlo_prev = self.qlo_hist[-1] if self.qlo_hist else NA_
        state = dict(tr=tr, atr=atr, atrq=atrq, isacc=isacc, var=(top, bot, sid), qacc=qacc, qnew=qnew, qsid=qsid, hh=hh, ll=ll)
        ported = (sid, top, bot)
        prov = (qsid, qhi_prev, qlo_prev)
        return state, ported, prov

    def commit(self, o, h, l, c, t, st):
        self.o.append(o); self.h.append(h); self.l.append(l); self.c.append(c); self.t.append(t)
        for length, val in ((self.p["atrLen"], st["atr"]), (self.p["provLen"], st["atrq"])):
            if val is not NA_:
                self.rma[length] = val
        self.tr_hist.append(st["tr"])
        self.isacc_hist.append(st["isacc"]); self.qacc_hist.append(st["qacc"]); self.qnew_hist.append(st["qnew"])
        self.qhi_hist.append(st["hh"]); self.qlo_hist.append(st["ll"])
        self.var, self.qsid = st["var"], st["qsid"]


_RUN_CACHE = {}


def run_ctx(htf, mode, p=P):
    """committed outputs per HTF bar and the realtime value seen after each 5M sub-bar (memoised: a pure function of
    the HTF series, the mode and the parameters)."""
    ck = (id(htf), len(htf), mode, tuple(sorted(p.items())))
    if ck not in _RUN_CACHE:
        _RUN_CACHE[ck] = (htf, _run_ctx(htf, mode, p))
    return _RUN_CACHE[ck][1]


def _run_ctx(htf, mode, p):
    ctx = Ctx(p, mode)
    committed, intra = [], {}
    for k, b in enumerate(htf):
        subs = b["subs"]
        for j in range(len(subs)):
            o = subs[0][0]
            h = max(s[1] for s in subs[:j + 1]); l = min(s[2] for s in subs[:j + 1]); c = subs[j][3]
            last = j == len(subs) - 1
            gate = {"hist": True, "rt_ok": last, "rt_fail": False, "nogate": True}[mode]
            st, ported, prov = ctx.evaluate(o, h, l, c, b["T"], gate)
            intra[(k, j)] = (ported, prov)
            if last:
                fin = (st, ported, prov, (o, h, l, c))
        st, ported, prov, (o, h, l, c) = fin
        if mode == "hist":                # historical bars run once with final values and the guard true
            st, ported, prov = ctx.evaluate(o, h, l, c, b["T"], True)
        ctx.commit(o, h, l, c, b["T"], st)
        committed.append((ported, prov))
    return committed, intra


def feed(htf, mode, which, p=P):
    """(chart bars, values seen by the Engine, source HTF index) for which = 0 ported / 1 provisional."""
    chart = [dict(k=k, j=j, open=b["T"] + b["slots"][j] * M5, close=b["T"] + b["slots"][j] * M5 + M5)
             for k, b in enumerate(htf) for j in range(len(b["subs"]))]
    if mode == "old_hist":
        com, _ = run_ctx(htf, "hist", p)
        out, last = [], -1                 # last HTF bar with close <= chart-bar close (HTF closes are increasing)
        for c in chart:
            while last + 1 < len(htf) and htf[last + 1]["C"] <= c["close"]:
                last += 1
            out.append((com[last][which], last) if last >= 0 else ((NA_, NA_, NA_), -1))
    elif mode in ("old_rt_ok", "old_rt_fail"):
        _, intra = run_ctx(htf, mode[4:], p)
        out = [(intra[(c["k"], c["j"])][which], c["k"]) for c in chart]
    else:
        com, _ = run_ctx(htf, "nogate", p)
        out = [(com[c["k"] - 1][which], c["k"] - 1) if c["k"] > 0 else ((NA_, NA_, NA_), -1) for c in chart]
    return chart, out


def events(htf, mode, which=0, p=P):
    """Engine edge rule (1258-1266) + registration kind (same ID -> update, new ID -> new). Only values of HTF bars that
    have a successor are compared (the last HTF bar's values reach the new path only on the next HTF bar)."""
    chart, out = feed(htf, mode, which, p)
    ev, prev, seen = [], (NA_, NA_, NA_), set()
    for i, (c, ((sid, top, bot), src)) in enumerate(zip(chart, out)):
        if src > len(htf) - 2:
            break
        trig = (sid is not NA_ and (prev[0] is NA_ or sid != prev[0])) or (top is not NA_ and (prev[1] is NA_ or top != prev[1])) \
            or (bot is not NA_ and (prev[2] is NA_ or bot != prev[2]))
        if trig and sid is not NA_:
            ev.append(("upd" if sid in seen else "new", sid, top, bot, i, c["close"], src))
            seen.add(sid)
        prev = (sid, top, bot)
    return ev


M5 = 300_000
H1 = 3_600_000


def htf_from_5m(bars5, tf_ms, day_mode=False):
    """aggregate 5M bars (open time, o, h, l, c) into HTF bars on the tf grid (day_mode: one bar per session day,
    closing at the session close 22:00 UTC)."""
    groups = {}
    for t, o, h, l, c in bars5:
        key = (t - 22 * H1) // 86_400_000 if day_mode else t // tf_ms
        groups.setdefault(key, []).append((t, o, h, l, c))
    out = []
    for key in sorted(groups):
        g = groups[key]
        T = key * 86_400_000 + 22 * H1 if day_mode else key * tf_ms
        C = T + 86_400_000 if day_mode else T + tf_ms
        out.append(dict(T=T, C=C, subs=[(o, h, l, c) for _, o, h, l, c in g], slots=[(t - T) // M5 for t, *_ in g]))
    return out


def market(seed, days=40, missing=0.0):
    """5M XAUUSD-like path: session 23:00 -> 22:00 UTC (1h daily break), no weekend bars, alternating trend / range."""
    rnd = random.Random(seed)
    p, out, t0 = 2000.0, [], 1_790_000_000_000 // 86_400_000 * 86_400_000
    regime, left = 0.0, 0
    for d in range(days):
        if (d % 7) in (5, 6):                       # weekend
            continue
        for s in range(23 * 12):
            t = t0 + d * 86_400_000 - H1 + s * M5   # 23:00 previous day .. 21:55
            if missing and rnd.random() < missing:
                continue
            if left <= 0:
                regime, left = rnd.choice([0.0, 0.0, 0.6, -0.6]), rnd.randint(40, 300)
            left -= 1
            q = p + regime + rnd.gauss(0, 0.9)
            out.append((t, p, max(p, q) + abs(rnd.gauss(0, .4)), min(p, q) - abs(rnd.gauss(0, .4)), q))
            p = q
    return out


def key(ev):
    return [e[:4] for e in ev]


def gate_model():
    # NF-01..: real formula, 1H / 4H / D from one 5M path, ported and provisional
    agg = dict(n=0, new_eq=0, new_rt=0, ok_vals=0, ported_ev=0, fail_div=0, prov_fail_eq=0, prov=0, ev=0, newcnt=0,
               updcnt=0)
    delays, zero_ok = set(), True
    for seed in range(6):
        b5 = market(seed)
        for tf, day in ((H1, False), (4 * H1, False), (None, True)):
            htf = htf_from_5m(b5, tf, day)
            for which in (0, 1):
                r = {m: events(htf, m, which) for m in ("old_hist", "old_rt_ok", "old_rt_fail", "new_hist", "new_rt")}
                agg["n"] += 1
                agg["new_eq"] += key(r["new_hist"]) == key(r["old_hist"])
                agg["new_rt"] += r["new_hist"] == r["new_rt"]
                agg["ok_vals"] += key(r["old_rt_ok"]) == key(r["old_hist"])
                if which == 0 and r["old_hist"]:
                    agg["ported_ev"] += 1
                    agg["fail_div"] += key(r["old_rt_fail"]) != key(r["old_hist"])
                if which == 1:
                    agg["prov"] += 1
                    agg["prov_fail_eq"] += key(r["old_rt_fail"]) == key(r["old_hist"])
                agg["ev"] += len(r["new_hist"])
                agg["newcnt"] += sum(e[0] == "new" for e in r["new_hist"])
                agg["updcnt"] += sum(e[0] == "upd" for e in r["new_hist"])
                if which == 0 and key(r["new_hist"]) == key(r["old_hist"]):
                    for a, b in zip(r["old_hist"], r["new_hist"]):
                        delays.add(b[5] - a[5])
                        hb = htf[a[6]]
                        last_missing = hb["T"] + hb["slots"][-1] * M5 + M5 < hb["C"]
                        zero_ok &= (b[5] == a[5]) == last_missing    # delay 0 <=> the HTF bar's last 5M slot is absent
    check("NF-01 real formula (port), 6 markets x 1H / 4H / D x ported / provisional: NR-A1 historical == realtime in every run",
          agg["new_rt"] == agg["n"], str(agg))
    check("NF-02 real formula: NR-A1 Box Hi / Lo, IDs, new / update event counts == current historical in every run "
          "(only the 5M bar changes)", agg["new_eq"] == agg["n"] and agg["newcnt"] > 0 and agg["updcnt"] > 0, str(agg))
    check("NF-03 regression: current realtime with an unsupported request-side isconfirmed diverges from historical in every "
          "ported run that registers boxes (reproduced); with a working isconfirmed the values agree in every run; the "
          "provisional path (no guard) is unaffected", agg["ported_ev"] > 0 and agg["fail_div"] == agg["ported_ev"]
          and agg["ok_vals"] == agg["n"] and agg["prov_fail_eq"] == agg["prov"],
          f"ported runs with boxes {agg['ported_ev']}, rt_fail diverging {agg['fail_div']}; rt_ok equal {agg['ok_vals']}/{agg['n']}")
    allowed = {0, M5, H1 + M5, 2 * 86_400_000 + H1 + M5}
    check("NF-04 real HTF boundaries: every delay is 0 (HTF period ends after the session close, last 5M slot absent), "
          "+5 min (continuous), +1h05 (daily break) or +2d1h05 (weekend); never negative; 0 occurs exactly for HTF bars "
          "whose last 5M slot is absent", delays and delays <= allowed and min(delays) >= 0 and zero_ok and len(delays) >= 3,
          f"{sorted(delays)} zero_ok={zero_ok}")

    # NF-05.. targeted cases built from the real formula: find bars where the outcome hinges on one condition
    b5 = market(11)
    htf = htf_from_5m(b5, H1)
    com, intra = run_ctx(htf, "rt_ok")
    hist, _ = run_ctx(htf, "hist")
    tmp_only = late_only = 0
    ctx_hist = Ctx(P, "hist")
    for k, b in enumerate(htf):
        subs = b["subs"]
        acc_intra = []
        for j in range(len(subs)):
            o = subs[0][0]; h = max(s[1] for s in subs[:j + 1]); l = min(s[2] for s in subs[:j + 1]); c = subs[j][3]
            st, _, _ = ctx_hist.evaluate(o, h, l, c, b["T"], False)
            acc_intra.append(st["isacc"])
        fin_st, _, _ = ctx_hist.evaluate(subs[0][0], max(s[1] for s in subs), min(s[2] for s in subs), subs[-1][3], b["T"], True)
        tmp_only += any(acc_intra[:-1]) and not fin_st["isacc"]
        late_only += (not any(acc_intra[:-1])) and fin_st["isacc"]
        ctx_hist.commit(subs[0][0], max(s[1] for s in subs), min(s[2] for s in subs), subs[-1][3], b["T"], fin_st)
    r = {m: events(htf, m) for m in ("old_hist", "new_hist", "new_rt")}
    check("NF-05 cases present in the data: formation true only mid-HTF-bar (false at the close) and false mid-bar but true "
          "at the close; NR-A1 registers neither the transient nor misses the late one (== historical)",
          tmp_only > 0 and late_only > 0 and key(r["new_hist"]) == key(r["old_hist"]) and r["new_hist"] == r["new_rt"],
          f"tmp_only={tmp_only} late_only={late_only}")
    # boundary sweeps: move one threshold to the exact value of a bar's statistic -> formation flips; NR-A1 still == hist
    flips = 0
    for name, vals in (("atrMult", (1.5, 2.5, 3.5)), ("driftMax", (0.1, 0.3, 0.6)), ("minUpper", (2, 4, 6)),
                       ("maxRun", (2, 4, 6))):
        outs = []
        for v in vals:
            p = dict(P, **{name: v})
            rr = {m: events(htf, m, 0, p) for m in ("old_hist", "new_hist", "new_rt")}
            outs.append(len(rr["old_hist"]))
            ok = key(rr["new_hist"]) == key(rr["old_hist"]) and rr["new_hist"] == rr["new_rt"]
            check(f"NF-06 condition sweep {name}={v}: NR-A1 historical == realtime == current historical values / IDs",
                  ok, f"events={len(rr['old_hist'])}")
        flips += len(set(outs)) > 1
    check("NF-07 the sweeps really move the formation (ATR / drift / upper-lower closes / colour-run conditions are exercised)",
          flips == 4, f"conditions that changed the event count: {flips}/4")


# ============================================================================
# NT : TF independence and timing
# ============================================================================
TFS = (("1H", H1, False), ("4H", 4 * H1, False), ("D", None, True))


def combined(b5, which, p):
    """1H / 4H / D from one 5M path, each through its own context, then the Engine edge rule run over the shared 5M
    timeline with one prev / seen state per TF (as the 3 separate feeds in the Visual)."""
    sets = {name: htf_from_5m(b5, tf, day) for name, tf, day in TFS}
    single = {name: events(h, "new_hist", which, p) for name, h in sets.items()}
    per_tf = {}
    for name, h in sets.items():
        _, out = feed(h, "new_hist", which, p)
        per_tf[name] = dict(zip([b["T"] + s * M5 for b in h for s in b["slots"]], out))
    comb = {name: [] for name in sets}
    prev = {name: (NA_, NA_, NA_) for name in sets}
    seen = {name: set() for name in sets}
    same_bar, distinct = {}, True
    for t in sorted({t for t, *_ in b5}):
        upd = {}
        for name in sets:
            (sid, top, bot), src = per_tf[name][t]
            if src > len(sets[name]) - 2:
                continue
            pv = prev[name]
            trig = (sid is not NA_ and (pv[0] is NA_ or sid != pv[0])) or (top is not NA_ and (pv[1] is NA_ or top != pv[1])) \
                or (bot is not NA_ and (pv[2] is NA_ or bot != pv[2]))
            if trig and sid is not NA_:
                comb[name].append(("upd" if sid in seen[name] else "new", sid, top, bot))
                seen[name].add(sid)
                upd[name] = (sid, top, bot)
            prev[name] = (sid, top, bot)
        if len(upd) > 1:
            same_bar[tuple(upd)] = same_bar.get(tuple(upd), 0) + 1
            distinct &= len(set(upd.values())) == len(upd)
    return sets, single, comb, same_bar, distinct


def gate_tfs():
    sets, single, comb, _, _ = combined(market(1, 120), 0, P)
    check("NT-01 1H / 4H / D processed together give exactly the per-TF event lists of isolated contexts (no shared state)",
          all(comb[n] == key(single[n]) for n in sets), str({n: len(single[n]) for n in sets}))
    check("NT-02 each TF registers its own boxes (1H-only, 4H-only and D-only formations: all three form in this market)",
          all(any(e[0] == "new" for e in single[n]) for n in sets), str({n: sum(e[0] == "new" for e in single[n]) for n in sets}))
    ids = {n: {e[1] for e in single[n]} for n in sets}
    check("NT-03 IDs are the HTF bar times of each TF's own start bar (distinct per TF where the start bars differ)",
          all(all(i in [b["T"] for b in sets[n]] for i in ids[n]) for n in sets), str({n: len(ids[n]) for n in sets}))
    # same-5M-bar coincidences: ported with looser thresholds (1H+4H, 1H+D) and provisional with a wide box (1H+4H+D)
    PL = dict(P, rangeLen=6, baseLen=10, atrMult=3.0, driftMax=0.5, minUpper=2, minLower=2)
    sets, single, comb, sb, dist = combined(market(0, 120), 0, PL)
    check("NT-04 ported: 1H+4H and 1H+D register on the same 5M bar; every TF still equals its isolated context and the "
          "coinciding boxes keep their own ID / Hi / Lo", ("1H", "4H") in sb and ("1H", "D") in sb and dist
          and all(comb[n] == key(single[n]) for n in sets), str(sb))
    sets, single, comb, sb, dist = combined(market(0, 60), 1, dict(P, provLen=5, provMult=6.0))
    check("NT-04b provisional: 1H+4H+D register on the same 5M bar; each TF equals its isolated context, own ID / Hi / Lo",
          ("1H", "4H", "D") in sb and dist and all(comb[n] == key(single[n]) for n in sets), str(sb))
    b5 = market(1, 120)
    sets = {name: htf_from_5m(b5, tf, day) for name, tf, day in TFS}
    # timing with a missing 5M slot at HTF closes: delay 0 there
    b5m = market(5, missing=0.05)
    hm = htf_from_5m(b5m, H1)
    oh, nh = events(hm, "old_hist"), events(hm, "new_hist")
    d = sorted({b[5] - a[5] for a, b in zip(oh, nh)}) if key(oh) == key(nh) else None
    check("NT-05 missing 5M bars (5 %): same values / IDs as historical; delays include 0 (last slot missing) and are within "
          "{0, +5 min, +1h05, +2d1h05}", d is not None and 0 in d and set(d) <= {0, M5, H1 + M5, 2 * 86_400_000 + H1 + M5}, str(d))
    dd = events(sets["D"], "new_hist")
    od = events(sets["D"], "old_hist")
    check("NT-06 Daily: delivered on the first 5M bar after the session close (daily break +1h05, Friday -> Monday +2d1h05)",
          key(dd) == key(od) and {b[5] - a[5] for a, b in zip(od, dd)} <= {H1 + M5, 2 * 86_400_000 + H1 + M5},
          str(sorted({b[5] - a[5] for a, b in zip(od, dd)})))


def main():
    for g in (gate_static, gate_model, gate_tfs):
        try:
            g()
        except Exception as ex:
            import traceback
            check(f"{g.__name__} completed without error", False, traceback.format_exc()[-400:])
    w = max(len(n) for n, _, _ in RESULTS)
    fails = 0
    for n, ok, d in RESULTS:
        fails += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {n.ljust(w)}  {'' if ok else d}")
    print(f"\n{len(RESULTS) - fails}/{len(RESULTS)} passed  [PINE_NOT_VERIFIED: exact transform / static / real-formula model]")
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
