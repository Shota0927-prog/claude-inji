"""RE10045 regression — array.get(..., -1) in the FVG blocks of ZoneVisualPractical.pine.

Root cause: Pine v5 evaluates BOTH operands of `and` / `or` (no short-circuit; lazy evaluation is a v6 change).
A guard such as `oldest < 0 or array.get(gFvgOpenT, oldest) ...` therefore still calls array.get with -1.

  R1  static lint : in the FVG blocks no `and` / `or` expression combines a sentinel guard on an index variable
                    (`v < 0`, `v >= 0`, `na(v)`) with array.get / array.set on that same variable.
                    Run on the pre-fix revision (7956626) -> must FAIL; on the current file -> must PASS.
  R2  eager mirror : the registration and draw-selection loops are transcribed with Pine v5 eager evaluation and an
                    array.get that raises on an out-of-range index (Python's -1 would silently wrap).
                    pre-fix transcription -> raises (bar-156-like case); fixed transcription -> no raise and the same
                    slot choices as the Batch A / B mirrors.
  R3  scenarios  : first registration, 1-5 per TF, 6th replaces the oldest, re-registration after a fill / expiry,
                    TF slot ranges, several TFs registering on one 5M bar, every array index in range.

Evidence class: PINE_NOT_VERIFIED (static lint + eager-evaluation mirror; TradingView runtime is external).
"""
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fvg_batch_a_sim as fa          # noqa: E402
import fvg_batch_b_sim as fb          # noqa: E402
import zp_overlap_build as zp         # noqa: E402

ROOT = fa.ROOT
PRE_FIX_REV = "7956626"
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


def fvg_blocks(src):
    """Batch A + Batch B + Batch C + NR-S1 + NR-A1 block text (code only)."""
    out = []
    for b, e in ((fb.A_BEGIN, fb.A_END), (fb.B_BEGIN, fb.B_END), (fb.C_BEGIN, fb.C_END),
                 ("// ==== NR-S1 Swing (begin) ", "// ==== NR-S1 Swing (end) "),
                 ("// ==== NR-A1 Accum (begin) ", "// ==== NR-A1 Accum (end) ")):
        if src.count(b) == 1 and src.count(e) == 1:
            out.append(src[src.index(b):src.index(e)])
    return fa.code_only("\n".join(out))


def lint_eager_guards(code):
    """Return the offending lines: a boolean and/or expression whose guard tests an index variable against a
    sentinel while another operand indexes an array with that same variable."""
    bad = []
    for line in code.split("\n"):
        if not re.search(r"\b(and|or)\b", line):
            continue
        for v in set(re.findall(r"\b([A-Za-z_]\w*)\s*(?:<|>=)\s*0\b", line)) | set(re.findall(r"\bna\(([A-Za-z_]\w*)\)", line)):
            if re.search(r"array\.(?:get|set)\(\s*\w+\s*,\s*" + re.escape(v) + r"\b", line):
                bad.append(line.strip())
    return bad


# ----------------------------------------------------------------------------
# Pine v5 eager-evaluation mirror
# ----------------------------------------------------------------------------
class PineIndexError(Exception):
    pass


def pget(arr, i):
    if i is None or i < 0 or i >= len(arr):
        raise PineIndexError(f"array.get index {i} out of range, size {len(arr)}")
    return arr[i]


def pset(arr, i, v):
    if i is None or i < 0 or i >= len(arr):
        raise PineIndexError(f"array.set index {i} out of range, size {len(arr)}")
    arr[i] = v


def eager_or(a, b):          # both operands already evaluated by the caller (Pine v5)
    return bool(a) or bool(b)


def register_slot_prefix(st, base):
    """pre-fix Pine (7956626 line 671-677) transcribed with eager `or`."""
    slot, oldest = -1, -1
    for k in range(fa.SLOTS):
        s = base + k
        if not pget(st.alive, s):
            if slot < 0:
                slot = s
        else:
            a = oldest < 0
            b = pget(st.openT, s) < pget(st.openT, oldest)       # evaluated even when a is true
            if eager_or(a, b):
                oldest = s
    if slot < 0:
        slot = oldest
    return slot


def register_slot_fixed(st, base):
    """fixed Pine: the -1 sentinel and the array access are in separate branches."""
    slot, oldest = -1, -1
    for k in range(fa.SLOTS):
        s = base + k
        if not pget(st.alive, s):
            if slot < 0:
                slot = s
        elif oldest < 0:
            oldest = s
        elif pget(st.openT, s) < pget(st.openT, oldest):
            oldest = s
    if slot < 0:
        slot = oldest
    return slot


def pick_prefix(st, base, prev):
    """pre-fix Batch B selection (7956626) with eager `and` / `or`."""
    pick = -1
    for k in range(fa.SLOTS):
        s = base + k
        if pget(st.alive, s):
            ot = pget(st.openT, s)
            c1 = prev is None or (ot < prev)
            c2a = pick < 0
            c2b = ot > pget(st.openT, pick)                          # evaluated even when c2a is true
            if c1 and (c2a or c2b):
                pick = s
    return pick


def pick_fixed(st, base, prev):
    pick = -1
    for k in range(fa.SLOTS):
        s = base + k
        if pget(st.alive, s):
            ot = pget(st.openT, s)
            if prev is None or ot < prev:
                if pick < 0:
                    pick = s
                elif ot > pget(st.openT, pick):
                    pick = s
    return pick


class EagerStore(fa.Store):
    """Batch A Store whose registration slot choice uses the eager transcription (pre-fix or fixed)."""

    def __init__(self, fixed):
        super().__init__()
        self.fixed = fixed
        self.chosen = []

    def on_event(self, tf, ev, now):
        reg = None
        if ev is None:
            return reg
        key = ev["key"]
        last = pget(self.lastKey, tf)
        if key is not None and (last is None or key != last):
            base = tf * fa.SLOTS
            for k in range(fa.SLOTS):
                s = base + k
                if pget(self.alive, s) and pget(self.openT, s) < key:
                    d = pget(self.dir, s)
                    c = ev["close"]
                    if (d == 1 and c < pget(self.bot, s)) or (d == -1 and c > pget(self.top, s)):
                        pset(self.alive, s, False)
            if ev["dir"] != 0 and ev["closeT"] is not None and now < ev["closeT"] + fa.LIFE[tf]:
                slot = (register_slot_fixed if self.fixed else register_slot_prefix)(self, base)
                for arr, v in ((self.top, ev["top"]), (self.bot, ev["bot"]), (self.dir, ev["dir"]), (self.openT, key),
                               (self.closeT, ev["closeT"]), (self.expire, ev["closeT"] + fa.LIFE[tf]), (self.alive, True)):
                    pset(arr, slot, v)
                self.registered.append((tf, key))
                self.chosen.append(slot)
                reg = ev["closeT"] + fa.LIFE[tf]
            pset(self.lastKey, tf, key)
        return reg


def run_eager(htf, n5, fixed):
    st = EagerStore(fixed)
    err = None
    for i in range(n5):
        try:
            st.bar(fa.T0 + i * 300_000, htf, True)
        except PineIndexError as ex:
            err = (i, str(ex))
            break
    return st, err


def draw_order_eager(st, fixed):
    out = []
    for tf in range(3):
        base, prev = tf * fa.SLOTS, None
        for _ in range(fa.SLOTS):
            p = (pick_fixed if fixed else pick_prefix)(st, base, prev)
            if p < 0:
                break
            prev = st.openT[p]
            out.append(p)
    return out


def htf_set(n15=0, n60=0, n240=0, bear15=False):
    return [fb.fvg_bars(fa.TF_MS[0], n15, bear15) if n15 else fa.mk_bars(fa.TF_MS[0], fa.T0, fa.flat(200)),
            fb.fvg_bars(fa.TF_MS[1], n60) if n60 else fa.mk_bars(fa.TF_MS[1], fa.T0, fa.flat(60)),
            fb.fvg_bars(fa.TF_MS[2], n240) if n240 else fa.mk_bars(fa.TF_MS[2], fa.T0, fa.flat(20))]


def main():
    cur = open(os.path.join(ROOT, "ZoneVisualPractical.pine"), encoding="utf-8").read()
    cur = __import__("rnv_build").strip_rnv(cur) or cur  # RN-1 V1 stripped -> 6e554b2 text (delta pinned by rnv_sim)
    cur = zp.strip_zpo(cur) or cur  # ZONE-P overlap display stripped -> 11b2b4e text (delta pinned by zp_overlap_sim)
    pre = subprocess.run(["git", "-C", ROOT, "show", f"{PRE_FIX_REV}:ZoneVisualPractical.pine"], capture_output=True, text=True).stdout
    bad_pre, bad_cur = lint_eager_guards(fvg_blocks(pre)), lint_eager_guards(fvg_blocks(cur))
    check("R1-01 lint detects the RE10045 pattern in the pre-fix revision 7956626 (registration + draw selection)",
          len(bad_pre) == 2 and any("oldest < 0 or array.get(gFvgOpenT, s)" in b for b in bad_pre)
          and any("pick < 0 or ot > array.get(gFvgOpenT, pick)" in b for b in bad_pre), str(bad_pre))
    check("R1-02 current FVG blocks: no and / or guard combined with array access on the guarded index", bad_cur == [], str(bad_cur))

    # bar-156-like case: a 1H TF registers its 2nd FVG while its first slot (5) is still alive
    h = htf_set(n60=2)
    n5 = 12 * 7 + 1
    _, err_pre = run_eager(h, n5, fixed=False)
    st_fix, err_fix = run_eager(h, n5, fixed=True)
    check("R2-01 eager pre-fix transcription raises array.get(-1) on the 2nd registration of a TF whose first slot is alive "
          "(bar-156-like case: 1H)", err_pre is not None and "index -1" in err_pre[1], str(err_pre))
    check("R2-02 eager fixed transcription: no out-of-range index, both 1H FVGs stored in slots 5 and 6",
          err_fix is None and st_fix.chosen == [5, 6] and [x[0] for x in st_fix.alive_set()] == [1, 1], str(err_fix))
    s4 = fa.Store()
    for i in range(n5):
        s4.bar(fa.T0 + i * 300_000, h, True)
    check("R2-03 fixed transcription stores exactly what the Batch A mirror stores", st_fix.alive_set() == s4.alive_set())
    sd, _ = run_eager(htf_set(n15=3, n60=2, n240=2), 48 * 7 + 1, fixed=True)
    try:
        draw_order_eager(sd, fixed=False)
        pre_draw_err = None
    except PineIndexError as ex:
        pre_draw_err = str(ex)
    check("R2-04 eager pre-fix Batch B selection raises array.get(-1) as soon as a TF has a live FVG",
          pre_draw_err is not None and "index -1" in pre_draw_err, str(pre_draw_err))
    allw = dict(fb.DEFAULT, showWeak=True)
    ref = [p for p, *_ in fb.draw(sd, allw)]
    check("R2-05 eager fixed selection: no out-of-range index, same order as the Batch B mirror (15M -> 1H -> 4H, newest first)",
          draw_order_eager(sd, fixed=True) == ref and len(ref) == 7)

    # R3 scenarios (fixed transcription, every array access range-checked)
    st, err = run_eager(htf_set(n15=1), 3 * 4 + 1, fixed=True)
    check("R3-01 first registration with 0 FVGs -> slot 0", err is None and st.chosen == [0])
    ok = True
    for n in range(1, 6):
        for tf, kw, per in ((0, "n15", 3), (1, "n60", 12), (2, "n240", 48)):
            st, err = run_eager(htf_set(**{kw: n}), per * (3 * n + 1) + 1, fixed=True)
            ok = ok and err is None and st.chosen == [tf * 5 + i for i in range(n)]
    check("R3-02 1..5 registrations per TF fill that TF's own slots in order (15M 0-4 / 1H 5-9 / 4H 10-14), no error", ok)
    st, err = run_eager(htf_set(n15=6), 3 * 19 + 1, fixed=True)
    check("R3-03 6th registration replaces the oldest (slot 0) and keeps 5", err is None and st.chosen == [0, 1, 2, 3, 4, 0]
          and len(st.alive_set(0)) == 5)
    # fill then re-register: FVG A (filled by the next 15M close) then FVG B reuses the freed slot 0
    bars = fa.mk_bars(fa.TF_MS[0], fa.T0, [(2000, 1995, 1998), (2010, 1999, 2008), (2012, 2005, 2010), (2010, 1990, 1990),
                                           (1985, 1980, 1982), (1996, 1981, 1994), (1998, 1990, 1996)] + fa.flat(10, 1994))
    st, err = run_eager([bars, h[1] if False else fa.mk_bars(fa.TF_MS[1], fa.T0, fa.flat(20)), fa.mk_bars(fa.TF_MS[2], fa.T0, fa.flat(5))],
                        3 * 8 + 1, fixed=True)
    # bar 3 closes 1990 < bottom 2000 -> slot 0 freed; bar 4 forms a bearish FVG (high 1985 < low[2] 2005) which
    # is registered on the very next event into the freed slot 0; bar 6 forms a bullish FVG -> slot 1
    check("R3-04 re-registration right after a full fill reuses the freed slot (0 -> filled -> 0), no index error",
          err is None and st.chosen == [0, 0, 1] and st.registered[1][1] == bars[4]["t"], str((err, st.chosen)))
    he = [fa.mk_bars(fa.TF_MS[0], fa.T0, [(2000, 1995, 1998), (2010, 1999, 2008), (2012, 2005, 2010)] + fa.flat(300, 2010)
                     + [(2010, 2005, 2008), (2020, 2009, 2018), (2022, 2015, 2020)] + fa.flat(10, 2020)),
          fa.mk_bars(fa.TF_MS[1], fa.T0, fa.flat(200)), fa.mk_bars(fa.TF_MS[2], fa.T0, fa.flat(60))]
    st, err = run_eager(he, 3 * 310, fixed=True)
    check("R3-05 re-registration after expiry (72h) reuses the expired slot", err is None and st.chosen == [0, 0]
          and len(st.alive_set(0)) == 1, str((err, st.chosen)))
    st, err = run_eager(htf_set(n15=4, n60=1, n240=1), 48 * 4 + 1, fixed=True)
    same_bar = 48 * 3                           # 4H bar 2 closes at 12h = 15M bar 47 / 1H bar 11 boundary
    check("R3-06 several TFs register on the same 5M bar without index errors (15M / 1H / 4H slot ranges kept)",
          err is None and sorted(set(x[0] for x in st.alive_set())) == [0, 1, 2]
          and all(0 <= c <= 4 or 5 <= c <= 9 or 10 <= c <= 14 for c in st.chosen), str(st.chosen))
    fixed_txt = fvg_blocks(cur)
    check("R3-07 Pine registration / selection now separate the -1 sentinel from the array access (structure matches R2 fixed)",
          "else if oldest < 0\n                    oldest := s\n                else if array.get(gFvgOpenT, s) < array.get(gFvgOpenT, oldest)\n                    oldest := s" in fixed_txt
          and "if na(prevT) or ot < prevT\n                            if pick < 0\n                                pick := s\n                            else if ot > array.get(gFvgOpenT, pick)\n                                pick := s" in fixed_txt)

    w = max(len(n) for n, _, _ in RESULTS)
    fails = 0
    for n, ok, d in RESULTS:
        fails += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {n.ljust(w)}  {'' if ok else d}")
    print(f"\n{len(RESULTS) - fails}/{len(RESULTS)} passed  [PINE_NOT_VERIFIED: static lint / eager-evaluation mirror]")
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
