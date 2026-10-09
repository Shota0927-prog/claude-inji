"""FVG Batch A fixtures — ZoneVisualPractical FVG acquisition / storage / invalidation.

Spec: FVG実装仕様書 v1.0 + A01 + A02, Batch A only (no drawing, no score interaction).

  A1  static : Engine untouched, Visual minus the FVG block == d240ec0, 3 requests only, 5 slots per TF, no input change
  A2  mirror : lifecycle (detect / width / dedupe / fill / partial fill / self-bar / expiry / cap / TF isolation)
  A3  static + mirror : [1] + lookahead_on fields, no barstate.isconfirmed in the request, state only on confirmed 5M bars
  A4  static : the FVG block is not connected to zn.* / zoneEng / zoneFeed and draws nothing

Evidence class: PINE_NOT_VERIFIED (static checks and a Python mirror; TradingView compile / realtime is external).
"""
import math
import os
import re
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIS_PATH = os.path.join(ROOT, "ZoneVisualPractical.pine")
BASE_REV = "d240ec0"            # 5M Production Visual (restored at 84f6ab1, unchanged at 31416a1)
START_REV = "31416a1"
B = "// ==== FVG Batch A (begin) "
E = "// ==== FVG Batch A (end) "

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


def git_show(rev, path):
    return subprocess.run(["git", "-C", ROOT, "show", f"{rev}:{path}"], capture_output=True, text=True).stdout


def code_only(src):
    return "\n".join(l for l in src.split("\n") if not l.lstrip().startswith("//"))


CUR = open(VIS_PATH, encoding="utf-8").read()
BASE = git_show(BASE_REV, "ZoneVisualPractical.pine")


def split_block(src):
    i = src.find("\n" + B)
    j = src.find(E)
    if i < 0 or j < 0:
        return src, ""
    j = src.index("\n", j) + 1
    return src[:i + 1] + src[j:], src[i + 1:j]


REST, BLOCK = split_block(CUR)
# Batch B (display) block follows the Batch A block; A1-01 compares the production part without it.
B2 = "\n// ==== FVG Batch B (begin) "
E2 = "// ==== FVG Batch B (end) "
if REST.count(B2) == 1 and REST.count(E2) == 1 and REST.index(B2) < REST.index(E2):
    REST = REST[:REST.index(B2) + 1] + REST[REST.index("\n", REST.index(E2)) + 1:]
BC = code_only(BLOCK)


# ============================================================================
# A1 / A4 : static
# ============================================================================
def gate_static():
    check("A1-01 Visual outside the FVG Batch A and Batch B blocks == d240ec0 byte-for-byte (MA / Swing / Accum / Break / ZoneFeed / "
          "zn.update / drawing / Stats / inputs unchanged)", bool(BASE) and bool(BLOCK) and REST.rstrip("\n") + "\n" == BASE)
    check("A1-02 FVG block is a single appended block (begins after the last existing line)",
          CUR.startswith(BASE.rstrip("\n")) and CUR.count(B) == 1 and CUR.count(E) == 1)
    eng = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", START_REV, "--",
                          "ZoneEnginePractical.pine", "ZoneEnginePracticalAuthority.pine", "SignalEnginePractical.pine",
                          "PracticalZoneStrategy_LONG.pine", "PracticalZoneStrategy_SHORT.pine"],
                         capture_output=True, text=True).stdout.strip()
    har = [f for f in os.listdir(ROOT) if f.startswith("Practical") and f.endswith("Harness.pine")]
    eh = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", START_REV, "--"] + har,
                        capture_output=True, text=True).stdout.strip()
    check("A1-03 Engine / SignalEngine / Strategies / Harness unchanged vs 31416a1; Visual import still /2",
          eng == "" and eh == "" and re.findall(r"^import .*$", code_only(CUR), re.M) == ["import sekine3310/ZoneEnginePractical/2 as zn"],
          eng + eh)
    req_cur = re.findall(r"request\.security(?:_lower_tf)?\(", code_only(CUR))
    req_base = re.findall(r"request\.security(?:_lower_tf)?\(", code_only(BASE))
    req_blk = re.findall(r"request\.security\(syminfo\.tickerid, (FVG_TF\w+),\s*f_fvgConfirmed\(FVG_MIN_WIDTH\), "
                         r"lookahead = barmerge\.lookahead_on\)", BC)
    check("A1-04 exactly 3 request.security added (FVG 15 / 60 / 240, lookahead_on); no security_lower_tf",
          len(req_cur) == len(req_base) + 3 and req_blk == ["FVG_TF15", "FVG_TF60", "FVG_TF240"]
          and 'string FVG_TF15         = "15"' in BC and 'string FVG_TF60         = "60"' in BC
          and 'string FVG_TF240        = "240"' in BC and "security_lower_tf" not in BC, f"{len(req_base)} -> {len(req_cur)}")
    check("A1-05 storage: fixed 15 slots (5 per TF) allocated once with var; no array.push / array.new outside var; "
          "no unbounded growth", BC.count("= array.new_") == 8 and all(l.lstrip().startswith("var array<") for l in BC.split("\n") if "array.new_" in l)
          and "array.push" not in BC and "array.insert" not in BC and "int    FVG_SLOTS_PER_TF = 5" in BC
          and BC.count("array.new_float(15, na)") == 2 and BC.count("(15,") == 7 and "array.new_int(3, na)" in BC)
    check("A1-06 no input added / changed (FVG constants are not inputs)", "input." not in BC)
    check("A1-07 no ATR / no extra ta.* in the FVG block", "ta." not in BC)
    check("A4-01 FVG block not connected to the Engine: no zn.* / zoneEng / zoneFeed / zoneCfg reference",
          not re.search(r"\bzn\.|zoneEng|zoneFeed|zoneCfg", BC))
    check("A4-02 FVG block draws nothing (no box / label / line / table / plot / alert)",
          not re.search(r"\b(box|label|line|table)\.new|\bplot\w*\(|\balert", BC))
    check("A4-03 FVG requests and state update only on the 5M chart (inside if is5mChart)",
          re.search(r"^if is5mChart\n    \[q15T", BC, re.M) is not None)


# ============================================================================
# A3 : non-repaint (static)
# ============================================================================
def gate_nonrepaint_static():
    fn = BC[BC.index("f_fvgConfirmed(float minWidth) =>"):]
    fn = fn[:fn.index("\n\n")]
    check("A3-01 HTF pack returns every field at [1] (previous, confirmed HTF bar): time / time_close / close / dir / top / bottom",
          "[time[1], time_close[1], close[1], _dir[1], _top[1], _bot[1]]" in fn)
    check("A3-02 no barstate.isconfirmed inside the HTF pack (request context)", "barstate" not in fn)
    check("A3-03 every FVG request uses lookahead_on together with the [1] pack (no lookahead_off FVG request)",
          BC.count("lookahead = barmerge.lookahead_on") == 3 and "lookahead_off" not in BC)
    upd = BC[BC.index("if barstate.isconfirmed"):]
    check("A3-04 FVG state (arrays / next expire) changes only under barstate.isconfirmed on the 5M chart",
          all(c in upd for c in ("f_fvgExpire(nowClose)", "f_fvgOnEvent(0,", "f_fvgOnEvent(1,", "f_fvgOnEvent(2,"))
          and BC.count("f_fvgOnEvent(") == 4 and BC.count("f_fvgExpire(") == 2
          and len(re.findall(r"gFvgNextExpire :=", BC)) == 4 and BC.index("if barstate.isconfirmed") < BC.index("gFvgNextExpire :="))
    check("A3-05 update order: expiry -> 15M -> 1H -> 4H; per TF fill -> register -> cap",
          upd.index("f_fvgExpire(") < upd.index("f_fvgOnEvent(0,") < upd.index("f_fvgOnEvent(1,") < upd.index("f_fvgOnEvent(2,")
          and BC.index("array.set(gFvgAlive, s, false)\n        if dir != 0") > 0)


# ============================================================================
# Python mirror (exact port of the Pine block)
# ============================================================================
HOUR = 3_600_000
LIFE = [72 * HOUR, 168 * HOUR, 336 * HOUR]
TF_MS = [15 * 60_000, 60 * 60_000, 240 * 60_000]
SLOTS = 5
MINTICK = 0.01


def round_to_mintick(x, mt=MINTICK):
    # Pine: nearest multiple of mintick, ties rounding up
    return None if x is None else math.floor(x / mt + 0.5) * mt


def fvg_eval(bars, i, min_width=3.0):
    """f_fvgConfirmed body at HTF bar i (before the [1] shift): (dir, top, bot)."""
    if i < 2:
        return 0, None, None
    lo, hi = bars[i]["l"], bars[i]["h"]
    bull = lo > bars[i - 2]["h"]
    bear = hi < bars[i - 2]["l"]
    top = lo if bull else bars[i - 2]["l"] if bear else None
    bot = bars[i - 2]["h"] if bull else hi if bear else None
    d = (1 if bull else -1) if (bull or bear) and round_to_mintick(top - bot) >= min_width else 0
    return d, top, bot


def htf_prev(bars, t5):
    """request.security(tf, f_fvgConfirmed()[fields 1], lookahead_on) at a 5M bar opening at t5:
    HTF bar containing t5 is k -> values of bar k-1 (confirmed)."""
    k = None
    for idx, b in enumerate(bars):
        if b["t"] <= t5 < b["tc"]:
            k = idx
    if k is None or k < 1:
        return None
    j = k - 1
    d, top, bot = fvg_eval(bars, j)
    return {"key": bars[j]["t"], "closeT": bars[j]["tc"], "close": bars[j]["c"], "dir": d, "top": top, "bot": bot}


class Store:
    def __init__(self):
        n = 3 * SLOTS
        self.top, self.bot, self.dir = [None] * n, [None] * n, [0] * n
        self.openT, self.closeT, self.expire = [None] * n, [None] * n, [None] * n
        self.alive = [False] * n
        self.lastKey = [None] * 3
        self.nextExpire = None
        self.registered = []          # audit log: (tf, key)

    def expire_scan(self, now):
        nxt = None
        for s in range(3 * SLOTS):
            if self.alive[s]:
                ex = self.expire[s]
                if now >= ex:
                    self.alive[s] = False
                else:
                    nxt = ex if nxt is None else min(nxt, ex)
        return nxt

    def on_event(self, tf, ev, now):
        reg = None
        if ev is None:
            return reg
        key = ev["key"]
        last = self.lastKey[tf]
        if key is not None and (last is None or key != last):
            base = tf * SLOTS
            for k in range(SLOTS):
                s = base + k
                if self.alive[s] and self.openT[s] < key:
                    d = self.dir[s]
                    c = ev["close"]
                    if (d == 1 and c < self.bot[s]) or (d == -1 and c > self.top[s]):
                        self.alive[s] = False
            if ev["dir"] != 0 and ev["closeT"] is not None and now < ev["closeT"] + LIFE[tf]:
                slot, oldest = -1, -1
                for k in range(SLOTS):
                    s = base + k
                    if not self.alive[s]:
                        if slot < 0:
                            slot = s
                    elif oldest < 0 or self.openT[s] < self.openT[oldest]:
                        oldest = s
                if slot < 0:
                    slot = oldest
                self.top[slot], self.bot[slot], self.dir[slot] = ev["top"], ev["bot"], ev["dir"]
                self.openT[slot], self.closeT[slot] = key, ev["closeT"]
                self.expire[slot], self.alive[slot] = ev["closeT"] + LIFE[tf], True
                self.registered.append((tf, key))
                reg = ev["closeT"] + LIFE[tf]
            self.lastKey[tf] = key
        return reg

    def bar(self, t5, htf, confirmed=True):
        """one 5M bar (open time t5). htf = [bars15, bars60, bars240]. State changes only if confirmed."""
        if not confirmed:
            return
        now = t5 + 300_000
        if self.nextExpire is not None and now >= self.nextExpire:
            self.nextExpire = self.expire_scan(now)
        for tf in range(3):
            r = self.on_event(tf, htf_prev(htf[tf], t5), now)
            if r is not None:
                self.nextExpire = r if self.nextExpire is None else min(self.nextExpire, r)

    def alive_set(self, tf=None):
        return sorted((s // SLOTS, self.openT[s], self.dir[s], self.top[s], self.bot[s])
                      for s in range(3 * SLOTS) if self.alive[s] and (tf is None or s // SLOTS == tf))


def mk_bars(tf_ms, t0, hlc):
    return [{"t": t0 + i * tf_ms, "tc": t0 + (i + 1) * tf_ms, "h": h, "l": l, "c": c} for i, (h, l, c) in enumerate(hlc)]


def run(htf, t0, n5, confirmed_pattern=None):
    st = Store()
    for i in range(n5):
        t5 = t0 + i * 300_000
        st.bar(t5, htf, True if confirmed_pattern is None else confirmed_pattern(i))
    return st


def flat(n, p=2000.0):
    return [(p + 1, p - 1, p)] * n


T0 = 1_790_000_000_000 // 86_400_000 * 86_400_000


# ============================================================================
# A2 : lifecycle (mirror)
# ============================================================================
def gate_lifecycle():
    # bullish FVG on 15M bar index 2 (bars 0,1,2): low[2]=... high[0]=2000, low[2nd]=2005 -> width 5
    h15 = mk_bars(TF_MS[0], T0, [(2000, 1995, 1998), (2010, 1999, 2008), (2012, 2005, 2010)] + flat(20, 2010))
    htf = [h15, mk_bars(TF_MS[1], T0, flat(10)), mk_bars(TF_MS[2], T0, flat(5))]
    # before bar 2 is confirmed (5M bars inside 15M bars 0..2) -> nothing registered
    st = run(htf, T0, 9)
    check("A2-01 FVG not registered before the 3rd HTF bar is confirmed (5M bars inside the forming bar)",
          st.alive_set(0) == [])
    st = run(htf, T0, 10)          # first 5M bar of 15M bar 3 -> bar 2 confirmed
    check("A2-02 bullish FVG registered at the first 5M bar after the 3rd 15M bar closed: top = low, bottom = high[2]",
          st.alive_set(0) == [(0, h15[2]["t"], 1, 2005, 2000)])
    hb = mk_bars(TF_MS[0], T0, [(2010, 2005, 2006), (2004, 1990, 1992), (2000, 1994, 1995)] + flat(20, 1995))
    sb = run([hb, htf[1], htf[2]], T0, 10)
    check("A2-03 bearish FVG: high < low[2], top = low[2], bottom = high", sb.alive_set(0) == [(0, hb[2]["t"], -1, 2005, 2000)])

    # width boundary with float prices: 2003.10 - 2000.10 etc. (mintick 0.01)
    def width_case(hi2, lo):
        bars = mk_bars(TF_MS[0], T0, [(hi2, hi2 - 5, hi2 - 2), (hi2 + 10, hi2 - 1, hi2 + 8), (lo + 7, lo, lo + 5)] + flat(5, lo + 5))
        return run([bars, htf[1], htf[2]], T0, 10).alive_set(0) != []
    check("A2-04 width (math.round_to_mintick) 2.99 -> no / 3.00 -> yes / 3.01 -> yes",
          (width_case(2000.10, 2003.09), width_case(2000.10, 2003.10), width_case(2000.10, 2003.11)) == (False, True, True))
    check("A2-04b width 3.00 whose raw float difference is below 3.0 (1024.07 - 1021.07) is accepted only via mintick rounding",
          1024.07 - 1021.07 < 3.0 and width_case(1021.07, 1024.07) and "math.round_to_mintick(_top - _bot) >= minWidth" in BC,
          f"raw = {1024.07 - 1021.07!r}")

    st = run(htf, T0, 30)
    check("A2-05 same HTF event (bar 2 reported on 3 consecutive 5M bars) registered exactly once",
          st.registered.count((0, h15[2]["t"])) == 1 and len(st.registered) == 1)

    def fill_case(closes):
        bars = mk_bars(TF_MS[0], T0, [(2000, 1995, 1998), (2010, 1999, 2008), (2012, 2005, 2010)]
                       + [(2010, min(c, 2004), c) for c in closes] + flat(5, 2010))
        return run([bars, htf[1], htf[2]], T0, 3 * (3 + len(closes) + 1) + 1).alive_set(0)
    check("A2-06 bullish fill boundary: next 15M close == bottom (2000) keeps, < bottom (1999.99) deletes",
          fill_case([2000.0]) != [] and fill_case([1999.99]) == [])
    hb2 = mk_bars(TF_MS[0], T0, [(2010, 2005, 2006), (2004, 1990, 1992), (2000, 1994, 1995), (2005.0, 1996, 2005.0)] + flat(5, 1995))
    hb3 = mk_bars(TF_MS[0], T0, [(2010, 2005, 2006), (2004, 1990, 1992), (2000, 1994, 1995), (2006, 1996, 2005.01)] + flat(5, 1995))
    check("A2-07 bearish fill boundary: close == top (2005) keeps, > top (2005.01) deletes",
          run([hb2, htf[1], htf[2]], T0, 16).alive_set(0) != [] and run([hb3, htf[1], htf[2]], T0, 16).alive_set(0) == [])
    pf = fill_case([2001.0, 2002.0])
    check("A2-08 partial fill (closes inside the gap) keeps the FVG and its original range",
          pf == [(0, h15[2]["t"], 1, 2005, 2000)])
    check("A2-09 the forming HTF bar itself is never used for the fill check (open time < event key required)",
          "array.get(gFvgOpenT, s) < key" in BC)
    hb5m = mk_bars(TF_MS[0], T0, [(2000, 1995, 1998), (2010, 1999, 2008), (2012, 2005, 2010)] + [(2012, 1990, 1990)] + flat(5, 2010))
    s1 = run([hb5m, htf[1], htf[2]], T0, 12)       # 15M bar 3 not closed yet: its 5M closes are below bottom
    check("A2-10 5M closes below the bottom do not fill (only the source-TF confirmed close counts)",
          s1.alive_set(0) == [(0, hb5m[2]["t"], 1, 2005, 2000)] and run([hb5m, htf[1], htf[2]], T0, 13).alive_set(0) == [])

    # expiry 72 / 168 / 336 h from the formation bar's close time
    for tf, life in ((0, 72), (1, 168), (2, 336)):
        bars = mk_bars(TF_MS[tf], T0, [(2000, 1995, 1998), (2010, 1999, 2008), (2012, 2005, 2010)] + flat(400, 2010))
        hs = [mk_bars(TF_MS[i], T0, flat(5000 if i == 0 else 2000)) for i in range(3)]
        hs[tf] = bars
        form_close = bars[2]["tc"]
        exp = form_close + life * HOUR
        n_at = (exp - T0) // 300_000             # 5M bar whose close == exp is index n_at - 1
        before = run(hs, T0, n_at - 1).alive_set(tf)
        at = run(hs, T0, n_at).alive_set(tf)
        check(f"A2-11 expiry {['15M', '1H', '4H'][tf]} = {life}h from formation close: alive at 5M close < expire, "
              "deleted at the first confirmed 5M close >= expire", before != [] and at == [])

    # cap: 6 FVGs on 15M -> oldest dropped; other TFs untouched
    seq = []
    for k in range(6):
        b = 2000 + k * 20
        seq += [(b, b - 5, b - 2), (b + 15, b - 1, b + 12), (b + 17, b + 5, b + 15)]
    cap15 = mk_bars(TF_MS[0], T0, seq + flat(5, 2200))
    f60 = mk_bars(TF_MS[1], T0, [(2000, 1995, 1998), (2010, 1999, 2008), (2012, 2005, 2010)] + flat(30, 2010))
    st = run([cap15, f60, htf[2]], T0, 3 * len(seq) + 3)
    keys = [x[1] for x in st.alive_set(0)]
    check("A2-12 6th FVG on a TF replaces that TF's oldest (5 kept, newest five, by formation open time)",
          len(keys) == 5 and keys == sorted(cap15[3 * k + 2]["t"] for k in range(1, 6)), str(len(keys)))
    check("A2-13 cap / fill / expiry on one TF never touch another TF's slots (1H FVG intact)",
          st.alive_set(1) == [(1, f60[2]["t"], 1, 2005, 2000)])
    check("A2-14 FVGs never merge / score each other (no FVG-vs-FVG comparison in the block)",
          not re.search(r"gFvgTop, \w+\) [<>]=? array\.get\(gFvgTop|overlap", BC))


# ============================================================================
# A3 : non-repaint (mirror)
# ============================================================================
def gate_nonrepaint_mirror():
    h15 = mk_bars(TF_MS[0], T0, [(2000, 1995, 1998), (2010, 1999, 2008), (2012, 2005, 2010), (2010, 1990, 1990)] + flat(20, 2010))
    htf = [h15, mk_bars(TF_MS[1], T0, flat(10)), mk_bars(TF_MS[2], T0, flat(5))]
    hist = run(htf, T0, 30)
    # realtime: each 5M bar first seen as several unconfirmed ticks, then confirmed
    rt = Store()
    for i in range(30):
        t5 = T0 + i * 300_000
        for _ in range(3):
            rt.bar(t5, htf, confirmed=False)
        rt.bar(t5, htf, confirmed=True)
    check("A3-06 history vs realtime (unconfirmed ticks then confirm): identical stored set and registration log",
          hist.alive_set() == rt.alive_set() and hist.registered == rt.registered)
    st = Store()
    for i in range(10):
        st.bar(T0 + i * 300_000, htf, confirmed=False)
    check("A3-07 unconfirmed 5M bars never change state (no registration / deletion)", st.alive_set() == [] and st.registered == [])
    # the value used at a 5M bar is always an HTF bar that closed at or before that 5M bar opened
    ok = True
    for i in range(30):
        t5 = T0 + i * 300_000
        ev = htf_prev(h15, t5)
        if ev is not None and ev["closeT"] > t5:
            ok = False
    check("A3-08 [1] + lookahead_on mapping: every HTF value read closed at or before the reading 5M bar opened (no future leak)", ok)


def main():
    gate_static()
    gate_nonrepaint_static()
    gate_lifecycle()
    gate_nonrepaint_mirror()
    w = max(len(n) for n, _, _ in RESULTS)
    fails = 0
    for n, ok, d in RESULTS:
        fails += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {n.ljust(w)}  {d}")
    print(f"\n{len(RESULTS) - fails}/{len(RESULTS)} passed  [PINE_NOT_VERIFIED: static / mirror checks]")
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
