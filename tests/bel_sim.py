"""BEL-1 fixtures — new-entry lock after a breakeven exit until the original TP / SL is reached (tests/bel_build.py).

  BS : static on the delivered files — each == bel_build.build() and strips back to the 7f74b04 file byte for byte; every other
       Pine file unchanged; the changed test files differ by exactly bel_build.TEST_EDITS; every existing input / default unchanged
       and one new input (OFF); the only code changes are the inserted lock blocks and three gate lines; the lock code writes only
       its own state, places no order / alert / label and stLkOn becomes true only under the ON input (OFF = identical); the lock
       start identifies the breakeven stop by order identity + leg (no profit test) and keeps oSL / oTP; the release uses bars after
       the start only and keeps the release bar blocked; every order / confirmed alert / label / Auto ENTRY / WAIT_START / PROV /
       provisional alert / label is under a lock gate; no SATS wait can be alive when a lock starts; Auto JSON (cfg / events)
       unchanged and the Auto lock code == the Gold Short lock code; MSL-1 still present; lint unchanged
  BM : bar-by-bar model of fill / TP set / breakeven / exits / lock (conditions ported from the Pine text): OFF == the code
       without the lock over random series; ON scenarios (XAUUSD Short example A / B / C and its Long mirror, TP after
       breakeven, SL before breakeven, gap stop fill, start bar reaching TP / SL, both on one bar, weekend gap, TP unknown,
       release bar blocked / next bar allowed, provisional per forming bar, stale SATS wait / pending order impossible)
  BU : mutations caught

Evidence class: PINE_NOT_VERIFIED (TradingView compile / broker emulator / Strategy Tester / alert delivery not reproduced here).
"""
import os
import random
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bel_build as bb           # noqa: E402
import msl_build as mb           # noqa: E402
import eu_sim as es              # noqa: E402
import fvg_re10045_sim as fr     # noqa: E402

ROOT = bb.ROOT
B = bb.BASE_REV
raw = lambda p: open(os.path.join(ROOT, p), encoding="utf-8").read()
code_only, input_decls, input_values = es.code_only, es.input_decls, es.input_values
CUR = {p: raw(p) for p in bb.FILES}
OLD = {p: bb.show(B, p) for p in bb.FILES}
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


def git(*a):
    return subprocess.run(["git", "-C", ROOT] + list(a), capture_output=True, text=True).stdout


def changed_lines(old, new):
    import difflib
    rem, add = [], []
    o, n = old.split("\n"), new.split("\n")
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, o, n, autojunk=False).get_opcodes():
        if op != "equal":
            rem += o[i1:i2]
            add += n[j1:j2]
    return rem, add


def enclosing_ifs(lines, i):
    """the `if` / `else if` headers enclosing line i (by indentation); None inside a function definition."""
    ind = len(lines[i]) - len(lines[i].lstrip())
    out = []
    for j in range(i - 1, -1, -1):
        l = lines[j]
        if not l.strip() or l.lstrip().startswith("//"):
            continue
        k = len(l) - len(l.lstrip())
        if k < ind:
            if re.match(r"^\s*(else\s+)?if\b", l):
                out.append(l)
            ind = k
            if k == 0:
                return None if "=>" in l else out
    return out


def gate_static():
    others = [p for p in os.listdir(ROOT) if p.endswith(".pine") and p not in bb.FILES]
    others += [os.path.join("automation/xau_short/pine", p) for p in os.listdir(os.path.join(ROOT, "automation/xau_short/pine"))
               if os.path.join("automation/xau_short/pine", p) not in bb.FILES]
    check("BS-01 the eight Strategies == bel_build.build() and strip back to the 7f74b04 files byte for byte (unapply too, idempotent "
          "on the old text); every other Pine file (Engines, Visuals, other Strategies / harnesses) unchanged vs 7f74b04",
          all(CUR[p] == bb.build(p) and bb.strip(p, CUR[p]) == OLD[p] and bb.unapply(p, CUR[p]) == OLD[p] and bb.unapply(p, OLD[p]) == OLD[p]
              for p in bb.FILES)
          and not [p for p in others if os.path.exists(os.path.join(ROOT, p)) and raw(p) != bb.show(B, p)])
    st = git("status", "--porcelain").split("\n")
    mod = set(git("diff", "--name-only", B, "--").split()) | {l[3:] for l in st if l.startswith("??")}
    mod -= {"tests/__pycache__/", "ZoneStrategyUSDJPY_Diagnostic.pine", "tests/stjd_build.py", "tests/stjd_sim.py"}   # untracked, not ours
    bad = sorted(m for m in mod if m not in bb.FILES and m not in bb.NEW_TESTS
                 and not (m in bb.TEST_EDITS and bb.unadapt(m, raw(m)) == bb.show(B, m) and bb.unadapt(m, raw(m)) != raw(m)))
    check("BS-02 vs 7f74b04 only the eight Strategies, bel_build / bel_sim and the four test files of bel_build.TEST_EDITS change "
          "(msl_build: BEL-1 reverted first; msl_sim: reads with BEL-1 reverted; cad_adapt / au_build: new-file lists), each exactly",
          not bad and set(bb.FILES) <= mod, str(bad))
    bad_in = {}
    for p in bb.FILES:
        ic, io = input_decls(CUR[p]), input_decls(OLD[p])
        if {k: v for k, v in ic.items() if k != "stBeLock"} != io or set(ic) - set(io) != {"stBeLock"}:
            bad_in[p] = "decls"
        elif input_values(CUR[p])["stBeLock"] != "false" or '"Lock New Entries After BE Until Original TP/SL", group = G_STT,' not in ic["stBeLock"]:
            bad_in[p] = ic["stBeLock"][:80]
    be = {p: input_values(CUR[p])["stBE"] for p in bb.FILES}
    check("BS-03 every existing input declaration unchanged (Breakeven Stop defaults kept: Gold / BTC ON, FX OFF; MSL-1 inputs kept); "
          "one new input 'Lock New Entries After BE Until Original TP/SL' default OFF in group 03 · Strategy TP / Breakeven",
          not bad_in and [be[p] for p in bb.FILES] == ["true", "true", "true", "false", "false", "false", "false", "true"], str((bad_in, be)))
    shape = {}
    for p in bb.FILES:
        rem, add = changed_lines(OLD[p], CUR[p])
        blk = set((bb.INPUT + bb.RELEASE + bb.START).split("\n"))
        add_g = [l for l in add if l not in blk]
        ok = len(rem) == 3 and len(add_g) == 3 and all(
            n in (o + " and not stLkBlk     // BEL-1", o + " and not stLkOn     // BEL-1") for o, n in zip(rem, add_g))
        if not ok:
            shape[p] = (rem, add_g)
    check("BS-04 the only changes: the input / state block, the release block (top of the confirmed block), the start block (inside "
          "the flat branch, before oState := 0) and three gate lines, each = the old line + ` and not stLkBlk` / ` and not stLkOn`",
          not shape, str(shape)[:600])
    added = bb.RELEASE + bb.START
    writes = set(re.findall(r"^\s*(\w+)\s*:=", added, re.M)) | set(re.findall(r"^\s*(?:bool|int|float)\s+(\w+)\s*=", added, re.M))
    pure = (writes == {"stLkOn", "stLkSide", "stLkSL", "stLkTP", "stLkBar", "stLkBlk", "lkC"}
            and not re.search(r"strategy\.(entry|exit|close|cancel|order)\(|alert\(|label\.|f_auEmit|\bvarip\b|request\.", added)
            and "profit" not in added and "stLkOn := true" not in bb.RELEASE
            and re.findall(r"stLkOn\s+:= true", added) == ["stLkOn   := true"]
            and bb.START.index("if stBeLock and oBE and oState == 2") < bb.START.index("stLkOn   := true"))
    uses = {p: [l.strip()[:50] for l in code_only(CUR[p]).split("\n") if re.search(r"\bstBeLock\b", l)] for p in bb.FILES}
    check("BS-05 OFF = identical: the lock code writes only its own new state (stLk*, lkC), places no order / exit / alert / label / "
          "JSON, uses no profit figure; stLkOn becomes true only under `if stBeLock and ...` (stBeLock read nowhere else), so with OFF "
          "stLkOn / stLkBlk stay false and every gate line equals its old condition",
          pure and all(len(u) == 2 for u in uses.values()), str((writes, uses))[:400])
    det = {}
    for p in bb.FILES:
        c = CUR[p]
        flat = c.index("    else if oState >= 2 and strategy.opentrades == 0\n")
        be_blk = c[c.index("    // (2c) 建値移動"):c.index("    // (2d)")]
        rel = c.index(bb.RELEASE)
        one = c.index("    // (1) 発注済み Entry の約定 / 決済を確認する")
        ok = (rel < one < flat and c.index(bb.START) == flat + len("    else if oState >= 2 and strategy.opentrades == 0\n")
              and "oSL" not in "".join(re.findall(r"^\s*(\w+)\s*:=", be_blk, re.M)) and "oStop := oFill" in be_blk
              and "oBE   := true" in be_blk and "oTP   := " in c
              and "strategy.exit(oXid, oEid, stop = oStop, limit = oTP)" in be_blk)
        if not ok:
            det[p] = False
    check("BS-06 start: inside the existing flat branch (before its oState := 0), after (1) has seen the trade close; release: before "
          "(1), only for a lock of an earlier bar (bar_index > stLkBar); the breakeven move writes oStop / oBE only (oSL stays the "
          "original SL), the same exit order oXid carries stop = oFill and limit = oTP after it",
          not det, str(det))
    place = {}
    for p in bb.FILES:
        c = CUR[p]
        L = c.split("\n")
        tg = [i for i, l in enumerate(L) if "=>" not in l and not l.lstrip().startswith("//") and
              (re.search(r"strategy\.entry\(|f_stConfAlert\(|f_auEmit\(\"(ENTRY|PROV|WAIT_START)\"", l)
               or re.search(r'alert\(f_stAlertMsg\("(確定|仮)"', l) or re.search(r'label\.new\(.*f_stAlertMsg\("確定"', l)
               or re.search(r'label\.set_text\(stProvLbl, f_stAlertMsg\("仮"', l)
               or re.search(r"^\s*pwState\s+:= 1\b", l) or re.search(r"^\s*oState\s+:= 1\b", l))]
        tg = [i for i in tg if enclosing_ifs(L, i) is not None]
        gv = {n: (re.search(r"^bool  " + n + r"\s*= (.*)$", c, re.M) or [None, ""])[1] for n in ("stPvGate", "stPvA", "stPvL")}

        def lk(name, depth=0):     # the provisional gate names resolve to `not stLkOn` (stPvA / stPvL -> stPvGate on the FX files)
            d = gv.get(name, "")
            return "not stLkOn" in d or (depth < 2 and any(re.search(r"\b" + n + r"\b", d) and lk(n, depth + 1) for n in gv))
        gated = lambda h: "stLkBlk" in h or "stLkOn" in h or any(re.search(r"\b" + n + r"\b", h) and lk(n) for n in gv)
        miss = [L[i].strip()[:60] for i in tg if not any(gated(h) for h in enclosing_ifs(L, i))]
        if miss or sum(1 for i in tg if "strategy.entry(" in L[i]) != 4:
            place[p] = miss
    check("BS-07 every strategy.entry (4), new order state (oState := 1), SATS wait start (pwState := 1), confirmed alert / label "
          "(f_stConfAlert on Gold), Auto ENTRY / WAIT_START / PROV and provisional alert / label sits under a lock gate (stLkBlk on the "
          "confirmed bar, stLkOn via stPvGate / stPvA on forming ticks)",
          not place, str(place))
    sats = {}
    for p in bb.FILES:
        c = CUR[p]
        new4 = c[c.index("    if oState == 0 and not cancelBar and stSessOK and not stLkBlk"):c.index("    stPrev := cur")]
        pull = c[c.index("    if stSats and pwState == 1 and bar_index > pwBar"):c.index("    // (4) 新規 Entry")]
        ok = (len(re.findall(r"pwState\s+:= 1\b", c)) == 1 and re.search(r"pwState\s+:= 1\b", new4)
              and re.search(r"pwState\s+:= 0\b", pull[pull.index("strategy.entry("):]) and "pwState" not in
              new4[new4.index("bool nowGo = false"):new4.index("if not skipRef and not na(pQty) and pwState == 0 and not pwCancelBar and not nowGo")].replace("pwState == 0", ""))
        if not ok:
            sats[p] = False
    check("BS-08 no stale SATS wait / pending order at a lock start: a wait starts only in (4) (oState == 0, now gated), the pull-side "
          "order ends it, the immediate order does not start one; positions come only from these orders; a pending order (oState 1) "
          "and an open position (oState 2) are one state, so when the position closes there is neither a wait nor a pending order",
          not sats, str(sats))
    a, s = CUR["automation/xau_short/pine/ZoneStrategyXAU_Auto.pine"], CUR["ZoneStrategyXAU.pine"]
    ao = OLD["automation/xau_short/pine/ZoneStrategyXAU_Auto.pine"]
    au = (re.findall(r"^var string auCfg.*$", a, re.M) == re.findall(r"^var string auCfg.*$", ao, re.M)
          and re.findall(r"f_auEmit\(.*$", a, re.M) == re.findall(r"f_auEmit\(.*$", ao, re.M)
          and "stBeLock" not in "".join(re.findall(r"^var string auCfg.*$", a, re.M))
          and bb.edits("automation/xau_short/pine/ZoneStrategyXAU_Auto.pine") == bb.edits("ZoneStrategyXAU.pine")
          and all(x in a and x in s for x in (bb.INPUT, bb.RELEASE, bb.START)))
    check("BS-09 Auto: JSON cfg strings (config ID) and every f_auEmit call (ENTRY / PROV / WAIT_START / CANCEL / TP_SET / BE_MOVE / "
          "CLOSE_REQ / TV_*) unchanged, no new event or field; the Auto lock code / gates are the same text as the Gold Short, so the "
          "same settings give the same entry decisions", au)
    keep = {}
    for p in bb.FILES:
        c = CUR[p]
        if mb.unapply(p, c) is None or c.count("f_stSlOK(") != 5 or not all(
                es.func(c, h) == es.func(OLD[p], h) for h in ("f_stQty(int side, float ref, float sl) =>", "f_stTp(", "f_beTrig(", "f_stSlOK(")):
            keep[p] = False
        same = lambda pat: re.findall(pat, c, re.M) == re.findall(pat, OLD[p], re.M)
        if not (same(r"strategy\.(?:entry|exit|close|cancel)\(.*$") and same(r"alert\(.*$") and same(r"label\.\w+\(.*$")
                and es.seg(c, "strategy(", "import ") == es.seg(OLD[p], "strategy(", "import ")):
            keep[p] = "calls"
    check("BS-10 unchanged: MSL-1 (its block and four gates; msl_build still strips it), f_stQty / f_stTp / f_beTrig, every order / "
          "exit / cancel / alert / label call line, strategy() settings and imports", not keep, str(keep))
    lint = {p: (fr.lint_eager_guards(code_only(CUR[p])), fr.lint_eager_guards(code_only(OLD[p]))) for p in bb.FILES}
    check("BS-11 eager-evaluation lint (RE10045 guard / index pattern): no new finding (the closed-trade index lkC is read only "
          "under strategy.closedtrades > oClosed >= 0)", all(x == y for x, y in lint.values()), str(lint)[:300])


# ---- model --------------------------------------------------------------------------------------------------------------
def _py(expr):
    e = expr.replace("strategy.closedtrades.exit_price(lkC)", "xp")
    e = re.sub(r"(\w+) == 1 \? \((.+?)\) : \((.+?)\)$", r"((\2) if \1 == 1 else (\3))", e)
    return e


_REL = re.search(r"    if stLkOn and bar_index > stLkBar and \((.+)\)\n", bb.RELEASE).group(1)
_LEG = re.search(r"and (oSide \* \(strategy\.closedtrades\.exit_price\(lkC\) - oTP\) < 0)\n", bb.START).group(1)
REL = eval("lambda stLkSide, high, low, stLkTP, stLkSL: " + _py("(" + _REL + ")"))   # noqa: S307
LEG = eval("lambda oSide, xp, oTP: " + _py(_LEG))     # noqa: S307


class Sim:
    """one Strategy in miniature, bar by bar: market orders at the next open (A: limit), SL with the order, TP / exit at the fill
    check, breakeven at a confirmed bar (next bar active), exits on the bar's path (open, then the nearer of high / low first, as the
    broker emulator assumes), the confirmed-bar script order: release -> (1) fill / flat (+ lock start) -> (2b) TP -> (2c) BE -> (4)."""

    def __init__(self, lock, has_lock=True, be_trig=15.0, tp_known=True):
        self.lock, self.has_lock, self.trig, self.tp_known = lock, has_lock, be_trig, tp_known
        self.o = 0
        self.oBE = False
        self.side = self.fill = self.sl = self.tp = self.stop = None
        self.pend = None            # (side, sl, tp, limit) ordered at the last close
        self.closed = []            # (entry_id, exit_id, exit_price)
        self.oEid = None
        self.seq = 0
        self.trades = []            # (bar, side, ref, sl) orders sent
        self.lkOn, self.lkSide, self.lkSL, self.lkTP, self.lkBar = False, 0, None, None, None
        self.events = []
        self.blocked = []

    def broker(self, i, o, h, l, c):
        if self.pend is not None and self.o == 1:
            side, sl, tp, lim = self.pend
            px = o if lim is None else (lim if (side == 1 and l <= lim) or (side == -1 and h >= lim) else None)
            if lim is not None and px is not None:
                px = min(o, lim) if side == 1 else max(o, lim)
            if px is not None:
                self.side, self.fill, self.sl, self.stop, self.tp = side, px, sl, sl, None
                self.pos = True
                self.tp0 = tp
                self.pend = None
                self.filled_bar = i
                self._exits(o, h, l, c, first=True)
            return
        if self.o >= 2 and getattr(self, "pos", False):
            self._exits(o, h, l, c)

    def _exits(self, o, h, l, c, first=False):
        s, stop, tp = self.side, self.stop, None if first else self.tp
        hit_s = (l <= stop) if s == 1 else (h >= stop)
        hit_t = tp is not None and ((h >= tp) if s == 1 else (l <= tp))
        gap_s = (o <= stop) if s == 1 else (o >= stop)
        gap_t = tp is not None and ((o >= tp) if s == 1 else (o <= tp))
        if gap_s or gap_t:
            leg = "stop" if gap_s else "tp"
            px = o
        elif hit_s and hit_t:
            high_first = abs(h - o) < abs(o - l)
            leg = ("tp" if s == 1 else "stop") if high_first else ("stop" if s == 1 else "tp")
            px = stop if leg == "stop" else tp
        elif hit_s or hit_t:
            leg = "stop" if hit_s else "tp"
            px = stop if hit_s else tp
        else:
            return
        self.pos = False
        self.closed.append((self.oEid, self.oEid + " SL/TP", px))
        self.exit_leg = leg

    def script(self, i, o, h, l, c, sig):
        blk = self.lkOn if self.has_lock else False
        if self.has_lock and self.lkOn and i > self.lkBar and REL(self.lkSide, h, l, self.lkTP, self.lkSL):
            self.lkOn = False
            self.events.append(("release", i))
        fill_now = False
        if self.o == 1:
            if getattr(self, "pos", False):
                self.o, fill_now = 2, True
            elif self.closed and self.closed[-1][0] == self.oEid:
                self.o = 0
            elif self.pend is None:
                self.o = 0
        elif self.o >= 2 and not getattr(self, "pos", False):
            if self.has_lock and self.lock and self.oBE and self.o == 2 and self.sl is not None and self.tp is not None and self.closed:
                eid, xid, xp = self.closed[-1]
                if eid == self.oEid and xid == self.oEid + " SL/TP" and LEG(self.side, xp, self.tp):
                    self.lkOn, self.lkSide, self.lkSL, self.lkTP, self.lkBar = True, self.side, self.sl, self.tp, i
                    blk = True
                    self.events.append(("lock", i))
            self.o = 0
        if fill_now:
            self.tp = self.tp0 if self.tp_known else None
        if self.o == 2 and not self.oBE:     # (2c): Fixed Distance trigger (needs no TP)
            fav = h if self.side == 1 else l
            if self.side * (fav - self.fill) >= self.trig:
                self.oBE = True
                self.stop = self.fill
                self.events.append(("be", i))
        if blk:
            self.blocked.append(i)
        if self.o == 0 and not blk and sig is not None:
            side, ref, sl, tp, lim = sig
            self.seq += 1
            self.oEid = ("L" if side == 1 else "S") + str(self.seq)
            self.o, self.oBE, self.pend = 1, False, (side, sl, tp, lim)
            self.trades.append((i, side, ref, sl))
            self.events.append(("entry", i))

    def prov_ok(self):
        """forming-tick provisional gate as written: oState == 0 (last confirmed) and not stLkOn (last confirmed)."""
        return self.o == 0 and not (self.has_lock and self.lkOn)

    def run(self, bars, sigs):
        prov = []
        for i, (o, h, l, c) in enumerate(bars):
            prov.append(self.prov_ok())
            self.broker(i, o, h, l, c)
            self.script(i, o, h, l, c, sigs.get(i))
        return prov


def short_example(after):
    """XAUUSD Short: entry 4000 (market at bar 1 open), SL 4040, TP 3940, BE trigger 15: 3985 reached -> BE; back to 4000 -> BE exit."""
    bars = [(4002, 4004, 3999, 4001), (4000, 4003, 3995, 3996), (3995, 3996, 3985, 3990), (3990, 4001, 3989, 4000)] + after
    return bars, {0: (-1, 4001, 4040.0, 3940.0, None)}


def gate_model():
    rnd = random.Random(20261030)
    # OFF == code without the lock, random series (incl. breakeven exits)
    diff = 0
    for seed in range(400):
        r = random.Random(seed)
        px, bars = 4000.0, []
        for _ in range(160):
            o = px + r.uniform(-3, 3)
            h, l = o + r.uniform(0, 25), o - r.uniform(0, 25)
            c = r.uniform(l, h)
            bars.append((round(o, 2), round(h, 2), round(l, 2), round(c, 2)))
            px = c
        sigs = {}
        for i in range(0, 160, r.randint(2, 6)):
            s = r.choice([1, -1])
            c = bars[i][3]
            sigs[i] = (s, c, round(c - s * r.uniform(10, 60), 2), round(c + s * r.uniform(15, 90), 2), None)
        a, b = Sim(lock=False), Sim(lock=False, has_lock=False)
        pa, pb = a.run(bars, sigs), b.run(bars, sigs)
        diff += (a.trades != b.trades) + (a.closed != b.closed) + (pa != pb) + bool(a.events and any(e[0] == "lock" for e in a.events))
        on = Sim(lock=True)
        on.run(bars, sigs)
        ent = [i for i, *_ in on.trades]
        if set(ent) & set(on.blocked):
            diff += 1
    check("BM-01 OFF == no lock code: 400 random XAUUSD-like series (breakeven exits included): orders, exits and the provisional "
          "gate identical, no lock ever starts; ON: no order on any blocked bar", diff == 0, str(diff))
    res = {}
    for name, after, want_rel in (("A TP 3940", [(4000, 4005, 3990, 3992), (3992, 3995, 3940, 3950)], 5),
                                  ("B SL 4040", [(4000, 4010, 3995, 4005), (4005, 4040, 4000, 4030)], 5),
                                  ("C none", [(4000, 4030, 3950, 4000)] * 6, None)):
        bars, sigs = short_example(after)
        s = Sim(lock=True)
        s.run(bars, sigs)
        res[name] = ([e for e in s.events if e[0] in ("be", "lock", "release")], s.lkOn)
    ok = (res["A TP 3940"][0] == [("be", 2), ("lock", 3), ("release", 5)] and not res["A TP 3940"][1]
          and res["B SL 4040"][0] == [("be", 2), ("lock", 3), ("release", 5)] and not res["B SL 4040"][1]
          and res["C none"][0] == [("be", 2), ("lock", 3)] and res["C none"][1])
    check("BM-02 XAUUSD Short example (Entry 4000, SL 4040, TP 3940, BE 15: 3985 -> BE, back to 4000 -> BE exit): lock from the exit "
          "bar; A 3940 reached -> released; B 4040 reached -> released; C neither -> still locked", ok, str(res))
    # Long mirror
    bars = [(1998, 2001, 1996, 1999), (2000, 2005, 1997, 2004), (2004, 2015, 2003, 2010), (2010, 2011, 1999, 2000),
            (2000, 2010, 1990, 2005), (2005, 2060, 2004, 2050)]
    s = Sim(lock=True)
    s.run(bars, {0: (1, 1999, 1960.0, 2060.0, None)})
    bars2 = bars[:5] + [(2005, 2006, 1960, 1970)]
    s2 = Sim(lock=True)
    s2.run(bars2, {0: (1, 1999, 1960.0, 2060.0, None)})
    check("BM-03 Long mirror (Entry 2000, SL 1960, TP 2060): BE -> BE exit -> lock; high >= 2060 releases, low <= 1960 releases",
          [e for e in s.events if e[0] != "entry"] == [("be", 2), ("lock", 3), ("release", 5)]
          and [e for e in s2.events if e[0] != "entry"] == [("be", 2), ("lock", 3), ("release", 5)], str((s.events, s2.events)))
    # no lock: TP after breakeven, SL before breakeven, breakeven OFF (trigger never), lock OFF
    bars_tp, sig = short_example([])
    bars_tp = bars_tp[:3] + [(3990, 3992, 3940, 3945)]
    s_tp = Sim(lock=True)
    s_tp.run(bars_tp, sig)
    s_sl = Sim(lock=True)
    s_sl.run([(4002, 4004, 3999, 4001), (4000, 4041, 3995, 4035)], {0: (-1, 4001, 4040.0, 3940.0, None)})
    s_nobe = Sim(lock=True, be_trig=1e9)
    s_nobe.run(short_example([(4000, 4005, 3990, 3992)])[0], sig)
    s_off = Sim(lock=False)
    s_off.run(short_example([(4000, 4005, 3990, 3992)])[0], sig)
    check("BM-04 no lock: TP after the breakeven move (leg = limit), SL before the breakeven move (oBE false), Breakeven Stop OFF "
          "(no breakeven exit), the lock input OFF (breakeven exit still happens, no lock)",
          not any(e[0] == "lock" for x in (s_tp, s_sl, s_nobe, s_off) for e in x.events)
          and any(e[0] == "be" for e in s_tp.events) and any(e[0] == "be" for e in s_off.events), "")
    # gap stop fill (worse than breakeven) is still the stop leg; a TP leg is never classed as the stop
    bars_g, sig = short_example([])
    bars_g = bars_g[:3] + [(4012, 4015, 4008, 4010)]     # opens above the breakeven stop 4000
    s_g = Sim(lock=True)
    s_g.run(bars_g, sig)
    legs = [LEG(-1, 4000.0, 3940.0), LEG(-1, 4012.0, 3940.0), LEG(-1, 3940.0, 3940.0), LEG(-1, 3930.0, 3940.0),
            LEG(1, 2000.0, 2060.0), LEG(1, 1990.0, 2060.0), LEG(1, 2060.0, 2060.0), LEG(1, 2070.0, 2060.0)]
    check("BM-05 leg identification (ported): stop at breakeven / gapped worse -> stop leg (lock); TP fill at TP or better (gap) -> "
          "not; the gapped breakeven exit at 4012 starts the lock",
          legs == [True, True, False, False, True, True, False, False] and ("lock", 3) in s_g.events, str(legs))
    # the start bar's own high / low never release; both on one later bar -> released; release bar blocked, next allowed
    bars_s, sig = short_example([(4000, 4001, 3999, 4000), (4000, 4001, 3999, 4000)])
    bars_s[3] = (4030, 4045, 3935, 4000)          # the BE exit bar (gap above the stop) also spans TP and SL
    s_s = Sim(lock=True)
    s_s.run(bars_s, sig)
    bars_b, sig = short_example([(4000, 4045, 3935, 4000), (4000, 4001, 3999, 4000)])
    s_b = Sim(lock=True)
    sigs_b = dict(sig)
    sigs_b.update({3: sig[0], 4: sig[0], 5: sig[0]})
    s_b.run(bars_b, sigs_b)
    check("BM-06 the breakeven-exit bar reaching TP / SL does not release (monitoring starts next bar); TP and SL on one later bar -> "
          "released (no order guessed); no entry on the lock-start bar or the release bar, the next bar enters",
          s_s.lkOn and ("lock", 3) in s_s.events and not any(e[0] == "release" for e in s_s.events)
          and ("release", 4) in s_b.events and [i for i, *_ in s_b.trades] == [0, 5] and {3, 4} <= set(s_b.blocked),
          str((s_s.events, s_b.events, s_b.trades)))
    # weekend / long gap: no bar reaches -> lock kept for any number of bars (bars carry no time; the condition is price only)
    bars_w, sig = short_example([(4000, 4020, 3960, 4000)] * 500 + [(3970, 3975, 3939.9, 3950), (3950, 3955, 3945, 3950)])
    sigs_w = {i: sig[0] for i in range(4, 506)}
    sigs_w[0] = sig[0]
    s_w = Sim(lock=True)
    s_w.run(bars_w, sigs_w)
    check("BM-07 day / weekend crossing: 500 bars without TP / SL -> locked throughout with no order (signals every bar); the bar "
          "reaching TP releases, the next bar enters",
          [i for i, *_ in s_w.trades][:2] == [0, 505] and ("release", 504) in s_w.events, str(s_w.trades[:3]))
    s_n = Sim(lock=True, tp_known=False)
    s_n.run(short_example([(4000, 4005, 3990, 3992)])[0], short_example([])[1])
    check("BM-08 TP unknown (na) at the breakeven exit -> no lock (the virtual position cannot be watched; the Pine start requires "
          "not na(oSL) and not na(oTP))", not any(e[0] == "lock" for e in s_n.events) and "not na(oSL) and not na(oTP)" in bb.START)
    # provisional: per forming bar = the last confirmed state
    bars_p, sig = short_example([(4000, 4005, 3990, 3992), (3992, 3995, 3940, 3950), (3950, 3955, 3945, 3950)])
    s_p = Sim(lock=True)
    prov = s_p.run(bars_p, sig)
    check("BM-09 provisional (forming ticks read the last confirmed state): blocked while the position is open, on the bar after the "
          "BE exit and on the forming release bar; allowed from the bar after the release",
          prov == [True, False, False, False, False, False, True], str(prov))


def gate_mutation():
    p = "ZoneStrategyXAU.pine"
    c = CUR[p]
    muts = [c.replace("bar_index > stLkBar and", "bar_index >= stLkBar and"),
            c.replace("    bool stLkBlk = stLkOn\n", "    bool stLkBlk = false\n"),
            c.replace("and oSide * (strategy.closedtrades.exit_price(lkC) - oTP) < 0", ""),
            c.replace("if stBeLock and oBE and oState == 2", "if stBeLock and oState == 2"),
            c.replace("and stSessOK and not stLkBlk     // BEL-1\n", "and stSessOK\n"),
            c.replace("and oState == 0 and not stLkBlk     // BEL-1\n", "and oState == 0\n"),
            c.replace(" and not stLkOn     // BEL-1\n", "\n"),
            c.replace('stBeLock = input.bool(false,', 'stBeLock = input.bool(true,'),
            c.replace("                stLkSL   := oSL\n", "                stLkSL   := oStop\n")]
    caught = [m != c and bb.strip(p, m) is None for m in muts]
    rel2 = eval("lambda stLkSide, high, low, stLkTP, stLkSL: " + _py("(" + _REL.replace(">= stLkTP", "> stLkTP") + ")"))   # noqa: S307
    check("BU-01 mutations (release on the start bar, release bar not blocked, no leg check, no breakeven flag, gates dropped, default "
          "ON, SL copied from the moved stop) do not strip back to 7f74b04; a strict `>` release port misses an exact TP touch",
          all(caught) and REL(1, 2060.0, 2000.0, 2060.0, 1960.0) and not rel2(1, 2060.0, 2000.0, 2060.0, 1960.0), str(caught))


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
    print(f"\n{len(RESULTS) - fails}/{len(RESULTS)} passed  [PINE_NOT_VERIFIED: exact build / static / Python model]")
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
