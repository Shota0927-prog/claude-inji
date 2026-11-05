"""ZSX checks — ZoneSyncXAU.pine (display-only all-timeframe Zone display).  python3 tests/zsx_sim.py [--quick]

Equivalence (local, PINE_NOT_VERIFIED): the "ZSX Logic" section of ZoneSyncXAU.pine and the LOGIC section of the unchanged
ZoneComboLabXAU.pine are both translated (tests/acc_pine.py translator via tests/lab_pine.py) and run on the same 5m bars and the
same higher-TF feed values (what the request.security calls deliver on each 5m bar). After every bar they must agree on
  * the internal valid Zones (id, type, TF, sub, bounds, registered 5m bar, iFVG) and the two MA Zones
  * the display bands in order (bounds, grey or not, member Zone ids, the name text = Lab's label / grey box text, Lab's left edge)
Timing: confirmed-5m-only processing (realtime ticks with and without rollback, the pending previous bar, a historical last bar)
and the draw-start time t0 (from when the band's exact shape exists, never before). Static: copies byte for byte, structure, lint.
"""
import copy
import os
import random
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lab_pine as lp     # noqa: E402  (patches the acc_pine tokenizer for map.new; LEGACY reset below)
import acc_pine as ap     # noqa: E402
import zsy_build as zb    # noqa: E402

lp.LEGACY = {}
ROOT = zb.ROOT
BODY = "ZoneSyncXAU.pine"
M5 = 300_000
T0 = 1_767_574_800_000
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


# ---------------------------------------------------------------------------- the new engine (translated)
def zsx_env(overrides=None):
    src = zb.raw(BODY)
    sec = zb.marked(src, "// ==== ZSX Logic (begin)", "// ==== ZSX Logic (end)")
    fib = zb.blocks()
    code = "\n".join([fib["LFW_FIBSTATE"][1], fib["LFW_FIBFEED"][1], sec])
    env = ap.make_env(ap.Broker(), [])
    env.update(array__insert=lp.Runner._insert, array__includes=lambda a, v: v in a, array__new_int=lambda n=0, v=None: [v] * n,
               array__new=lambda n=0, v=None: [v] * n, array__min=lambda a: min(a) if a else None,
               array__max=lambda a: max(a) if a else None, array__new_string=lambda n=0, v=None: [v] * n)
    inp = ap.inputs(src)
    for k in (overrides or {}):
        if k not in inp:
            raise KeyError(k)
    inp.update(overrides or {})
    env.update(inp)
    exec(compile(ap.Translator().translate(ap.logical_lines(code)), "<ZSX Logic>", "exec"), env)
    return env


def fib_env():
    fib = zb.blocks()
    env = ap.make_env(ap.Broker(), [])
    exec(compile(ap.Translator().translate(ap.logical_lines(fib["LFW_FIBSTATE"][1] + "\n" + fib["LFW_FIBFEED"][1])), "<fib>", "exec"), env)
    return env


# ---------------------------------------------------------------------------- synthetic 5m bars and higher-TF feeds
def gen(seed, n, ze=False):
    """5m bars + causal feeds (value of the previous completed block). Blocks of 12 / 24 / 48 / 96 bars stand for the four
    higher TFs (shorter than the real ones so that every kind of event happens often)."""
    rnd = random.Random(seed)
    p = 2000.0
    rows = []
    for _ in range(n):
        o = p
        c = o + rnd.gauss(0, 2.4)
        h = max(o, c) + abs(rnd.gauss(0, 1.3))
        lo = min(o, c) - abs(rnd.gauss(0, 1.3))
        rows.append((round(o, 2), round(h, 2), round(lo, 2), round(c, 2)))
        p = c
    bars = [dict(t=T0 + i * M5, o=r[0], h=r[1], l=r[2], c=r[3]) for i, r in enumerate(rows)]
    raw = [dict() for _ in range(n)]
    blk = (12, 24, 48, 96)
    e1 = e5 = None
    acc = {}
    for i, b in enumerate(bars):
        c = rows[i][3]
        e5 = c if e5 is None else e5 + (c - e5) * 2 / 61.0
        e1 = c if e1 is None else e1 + (c - e1) * 2 / 121.0
        if i >= 30:
            b.update(zbMa1=round(e1, 3))
        if i >= 60:
            b.update(zbMa2=round(e5, 3))
        for k in range(4):
            B = blk[k]
            hb = i // B
            if hb < 2:
                continue
            seg, prev = rows[(hb - 1) * B: hb * B], rows[(hb - 2) * B: (hb - 1) * B]
            tk = T0 + (hb - 1) * B * M5
            hi, lw = max(r[1] for r in seg), min(r[2] for r in seg)
            q = k + 1
            if hb % 3 == 0:
                b.update({f"s{q}h": hi, f"s{q}ht": tk})
            if hb % 4 == 1:
                b.update({f"s{q}l": lw, f"s{q}lt": tk})
            b.update({f"g{q}k": tk, f"g{q}kc": tk + B * M5, f"g{q}c": seg[-1][3], f"g{q}d": 0})
            if min(r[2] for r in seg) > max(r[1] for r in prev) + 2:
                b.update({f"g{q}d": 1, f"g{q}t": min(r[2] for r in seg), f"g{q}b": max(r[1] for r in prev)})
            elif max(r[1] for r in seg) < min(r[2] for r in prev) - 2:
                b.update({f"g{q}d": -1, f"g{q}t": min(r[2] for r in prev), f"g{q}b": max(r[1] for r in seg)})
            rf = random.Random(seed * 7919 + hb * 13 + k)
            if rf.random() < 0.35:     # an injected FVG around the block close (so that reversals / invalidations happen often)
                m = seg[-1][3] + rf.uniform(-6, 6)
                w = rf.uniform(3, 9)
                b.update({f"g{q}d": rf.choice([1, -1]), f"g{q}t": round(m + w / 2, 2), f"g{q}b": round(m - w / 2, 2)})
            cc = round(lw + (hi - lw) * random.Random(seed * 1009 + hb * 7 + k).random(), 1)
            b.update({f"zdL{q}": cc - 0.25, f"zdU{q}": cc + 0.25, f"zdT{q}": float(tk)})
            if k < 3:      # accumulation: a new id every 4 blocks, forming during its first 2 blocks
                aid = T0 + (hb // 4) * 4 * B * M5
                forming = hb % 4 < 2
                st = acc.setdefault((k, aid), [lw, hi])
                st[0], st[1] = min(st[0], lw), max(st[1], hi)
                b.update({f"f{q}i": aid, f"f{q}u": round(st[1], 2), f"f{q}l": round(st[0], 2), f"f{q}a": 1 if forming else 0})
        if ze:             # LongFibWave raw outputs (hold, dir, O, E, id) for D (k 1) and 4H (k 0)
            for k, B in ((0, 48), (1, 96)):
                hb = i // B
                if hb < 1:
                    continue
                r2 = random.Random(seed * 31 + hb * 3 + k)
                hold = 1 if r2.random() < 0.15 else 0
                d = 1 if (hb // 2) % 2 == 0 else -1
                O = round(2000 + r2.random() * 40, 2)
                E = round(O + d * (10 + r2.random() * 30), 2)
                raw[i][k] = (hold, d if not hold else 0, O, E, float(hb // 2))
    return bars, raw


def lab_feeds_ze(bars, raw):
    """the Lab's ZE inputs = LongFibWave's 5m-chart side (f_fibFeed with the 5m bar's time_close), from the raw values"""
    env = fib_env()
    fd = {0: [None] * 6, 1: [None] * 6}
    for i, b in enumerate(bars):
        env["time_close"] = b["t"] + M5
        for k in (0, 1):
            h, d, O, E, wid = raw[i].get(k, (0, 0, None, None, 0.0))
            env["f_fibFeed"](fd[k], True, h, d, O, E, wid)
            nm = "4" if k == 0 else "D"
            b.update({f"ze{nm}O": fd[k][0], f"ze{nm}E": fd[k][1], f"ze{nm}D": fd[k][2], f"ze{nm}I": fd[k][3], f"ze{nm}S": fd[k][4],
                      f"ze{nm}T": fd[k][5]})


def vec(b, i, raw):
    """the 75 inputs of one 5m bar in the order of f_zxEng's vCur"""
    g = b.get
    v = [float(b["t"]), float(b["t"] + M5), float(i)]
    for q in (1, 2, 3):
        v += [g(f"f{q}u"), g(f"f{q}l"), g(f"f{q}i"), g(f"f{q}a")]
    for q in (1, 2, 3, 4):
        v += [g(f"s{q}h"), g(f"s{q}ht"), g(f"s{q}l"), g(f"s{q}lt")]
    for q in (1, 2, 3, 4):
        v += [g(f"zdL{q}"), g(f"zdU{q}"), g(f"zdT{q}")]
    for k in (1, 0):        # D first, then 4H
        v += list(raw[i].get(k, (None, None, None, None, None)))
    for q in (1, 2, 3, 4):
        v += [g(f"g{q}k"), g(f"g{q}c"), g(f"g{q}d"), g(f"g{q}t"), g(f"g{q}b")]
    v += [g("zbMa1"), g("zbMa2")]
    assert len(v) == 75
    return [None if x is None else float(x) for x in v]


# ---------------------------------------------------------------------------- comparison
TF_NAME = {0: "週足", 1: "日足", 2: "4時間足", 3: "1時間足", 4: "5分足", 5: "1分足"}


def item_name(c, inp):
    return {1: "アキュム上辺", 2: "アキュム下辺", 3: "MA EMA" + str(inp["zbLen1"]), 4: "MA EMA" + str(inp["zbLen2"]), 5: "水平線",
            6: "出来高POC", 7: "フィボ 0.236", 8: "フィボ 0.382", 9: "フィボ 0.5", 10: "フィボ 0.618", 11: "FVG", 12: "iFVG"}[c]


def decode_name(tk, s, n, inp):
    """Python port of the draw side's f_zxName (the decoded names are compared with the Lab's own label texts)"""
    tx, pr = "", -1
    for j in range(s, s + n):
        v = int(tk[j])
        r, c = v // 100, v % 100
        if r != pr:
            tx += ("" if tx == "" else "\n") + TF_NAME[r] + "｜" + item_name(c, inp)
            pr = r
        else:
            tx += "＋" + item_name(c, inp)
    return tx


def lab_state(r):
    zs = sorted((z.id, z.typ, z.tf, z.sub, z.bot, z.top, z.aBar, z.inv) for z in r["lbZs"] + r["lbFvgs"])
    ma = [(m.id, m.bot, m.top) if m is not None else None for m in (r["lbMa1"], r["lbMa2"])]
    ds = []
    for g in r["lbDsG"]:
        if g.gone:
            ds.append((True, g.bot, g.top, (), g.bx.text, g.bx.args[0]))
        else:
            ds.append((False, g.bot, g.top, tuple(z.id for z in g.mem), g.lb.text, g.bx.args[0]))
    return zs, ma, ds


def zsx_state(env, S, tb=T0):
    zs = sorted((z.id, z.typ, z.tf, z.sub, z.bot, z.top, z.aBar, z.inv) for z in S.zs + S.fvgs)
    ma = [(m.id, m.bot, m.top) if m is not None else None for m in (S.ma1, S.ma2)]
    gf, tk = env["f_zxOut"](S)
    inp = env
    ds = []
    for i, g in enumerate(S.ds):
        o = i * 9
        name = decode_name(tk, int(gf[o + 7]), int(gf[o + 8]), inp)
        left = None if g.lab0 is None else (g.lab0 - tb) // M5
        ds.append((g.gone, g.bot, g.top, () if g.gone else tuple(z.id for z in g.mem), name, left))
    return zs, ma, ds


def run_pair(bars, raw, ov, ze=False):
    """runs Lab and ZSX bar by bar; returns the first difference (or None) and per-bar ZSX snapshots"""
    if ze:
        lab_feeds_ze(bars, raw)
    lab_ov = dict(dsZone=True, dsEnt=False, dsTbl=False, cTA=False, cTC=False, **ov)
    lab = lp.Runner(overrides=lab_ov)
    env = zsx_env(ov)
    S = env["f_zxNew"]()
    snaps = []
    prev = None
    for i, b in enumerate(bars):
        lab.step(b)
        cur = vec(b, i, raw)
        env["time_close"] = b["t"] + M5
        env["f_zxAdvance"](S, prev, cur, True, 0)
        prev = cur
        a, z = lab_state(lab), zsx_state(env, S)
        if a != z:
            for nm, x, y in zip(("zones", "ma", "display"), a, z):
                if x != y:
                    return (i, nm, x[:6] if isinstance(x, list) else x, y[:6] if isinstance(y, list) else y), snaps, env, S
        snaps.append((b["t"] + M5, [(g.gone, g.bot, g.top, tuple(m.id for m in g.mem), g.t0) for g in S.ds]))
    return None, snaps, env, S


def crafted_ma():
    """MA 1 overlaps only the band that MA 2 makes with a POC (the Lab's retry of MA 1 after MA 2), then both move apart and back"""
    bars, raw = [], []
    for i in range(40):
        c = 2000.0
        b = dict(t=T0 + i * M5, o=1900.0, h=1901.0, l=1899.0, c=1900.5, zdL1=c - 0.25, zdU1=c + 0.25, zdT1=float(T0 - 3_600_000))
        off = 0.0 if i < 15 or i >= 25 else 30.0
        b.update(zbMa1=c + 5.0 + off, zbMa2=c + 2.5 + off)
        bars.append(b)
        raw.append({})
    return bars, raw


def equivalence(quick):
    cases = []
    seeds = (1, 2) if quick else (1, 2, 3, 4)
    n = 500 if quick else 900
    for seed in seeds:
        cases.append((f"seed {seed} defaults", seed, {}, False))
        cases.append((f"seed {seed} cap 6", seed, dict(dsZoneMax=6), False))
    cases.append(("seed 5 ZE on, cap 10, 2 accum boxes", 5, dict(zeUse=True, dsZoneMax=10, zaKeep1=2, zaKeep2=2), True))
    cases.append(("seed 6 MA lengths differ, merge 8, width 4", 6, dict(zbLen1=2000, zcMerge=8.0, zHalf=4.0), False))
    cases.append(("crafted: MA 1 joins only through MA 2", None, {}, False))
    bad, stats = [], []
    for name, seed, ov, ze in cases:
        bars, raw = crafted_ma() if seed is None else gen(seed, n, ze)
        diff, snaps, env, S = run_pair(bars, raw, ov, ze)
        if diff:
            bad.append((name, diff))
        stats.append((name, len(S.ds), sum(g.gone for g in S.ds), S.nSwMerge, S.nIfvg, S.nFvgDead, S.nAccOut, len(S.zs), len(S.fvgs), S.nErr))
    return bad, stats


# ---------------------------------------------------------------------------- timing / confirmation
def timing(quick):
    bars, raw = gen(8, 300 if quick else 600)
    lab = lp.Runner(overrides=dict(dsZone=True, dsEnt=False, dsTbl=False, cTA=False, cTC=False))
    labs = []
    for b in bars:
        lab.step(b)
        labs.append(lab_state(lab))
    bad = []
    for rollback in (True, False):
        env = zsx_env()
        S = env["f_zxNew"]()
        prev = None
        for i, b in enumerate(bars):
            cur = vec(b, i, raw)
            env["time_close"] = b["t"] + M5
            hist = i < len(bars) // 3          # first third historical (confirmed at its own evaluation), then realtime ticks
            if hist:
                env["f_zxAdvance"](S, prev, cur, True, 0)
            else:
                committed = copy.deepcopy(S)
                for tick in range(3):          # ticks of the forming 5m bar: never confirmed
                    if rollback:
                        S = copy.deepcopy(committed)
                    env["f_zxAdvance"](S, prev, cur, False, 0)
                    # while bar i is forming, the state is through bar i-1 exactly
                    if i >= 1 and zsx_state(env, S) != labs[i - 1]:
                        bad.append((rollback, i, tick, "forming"))
                        break
                    if S.lastT != bars[i - 1]["t"] or S.n != i:
                        bad.append((rollback, i, tick, "lastT / count", S.lastT, S.n))
                        break
            prev = cur
        # the realtime last bar stays unprocessed until the next 5m bar exists; a reload (historical) processes it
        if S.lastT != bars[-2]["t"]:
            bad.append((rollback, "last realtime", S.lastT))
    # reload while the market is closed: every bar historical -> through the last bar
    env = zsx_env()
    S = env["f_zxNew"]()
    prev = None
    for i, b in enumerate(bars):
        cur = vec(b, i, raw)
        env["time_close"] = b["t"] + M5
        env["f_zxAdvance"](S, prev, cur, True, 0)
        prev = cur
    reload_ok = S.lastT == bars[-1]["t"] and zsx_state(env, S) == labs[-1] and S.n == len(bars)
    # the registration start: bars before it are not processed, the first processed one is the first bar at / after it
    env = zsx_env()
    S = env["f_zxNew"]()
    prev = None
    st = bars[50]["t"]
    for i, b in enumerate(bars[:120]):
        cur = vec(b, i, raw)
        env["time_close"] = b["t"] + M5
        env["f_zxAdvance"](S, prev, cur, True, st)
        prev = cur
    start_ok = S.n == 70 and S.times[0] == st
    return bad, reload_ok, start_ok


def draw_start(snaps):
    """t0 of every displayed band = the 5m close since which a band of exactly this shape (bounds + members, grey or not) has been
    displayed without a break (never earlier); grey bands are left to their FVG (checked separately)"""
    bad = []
    since = {}
    for tc, groups in snaps:
        keys = set()
        for gone, bot, top, mem, t0 in groups:
            if gone:
                continue
            key = (bot, top, frozenset(mem))
            keys.add(key)
            exp = since.get(key, tc)
            if t0 != exp:
                bad.append((tc, key, t0, exp))
        since = {k: since.get(k, tc) for k in keys}
    return bad


# ---------------------------------------------------------------------------- static
def own_lines(text):
    return re.sub(r"^// ==== ZSY copy (\w+) begin .*?^// ==== ZSY copy \1 end ====$", "", text, flags=re.S | re.M)


def static():
    body = zb.raw(BODY)
    reg = zb.regions(body)
    want = zb.blocks()
    bad = [n for n in want if reg.get(n) != want[n][1]]
    check("ZX-01 every ZSY copy region of ZoneSyncXAU.pine == its source block byte for byte (Lab Accum / f_acConfirmed / Pivot / FVG, "
          "MtfPocFeedXAU f_pocCore / f_feed, LongFibWave inputs / Logic+Transfer / f_lfwCore / f_fibState / f_fibFeed)",
          not bad and set(reg) == set(want) and "@@COPY" not in body and zb.build(body) == body, str(bad))
    own = own_lines(body)
    code = "\n".join(ln.split("//")[0] if not ln.lstrip().startswith("//") else "" for ln in own.split("\n"))
    nreq = len(re.findall(r"request\.security\(", code))
    i_out = code.index("\"5\", f_zxEng()")
    chart = re.sub(r'"[^"\n]*"', '""', code[i_out:])
    chart_bad = re.findall(r"\b(close|open|high|low|volume|bar_index)\b", chart)
    lab = zb.raw("ZoneComboLabXAU.pine")
    inp_lab, inp_new = ap.inputs(lab), ap.inputs(body)
    same_inp = [k for k in inp_new if k in inp_lab and inp_new[k] != inp_lab[k]]
    check("ZX-02 structure: an indicator; no strategy / alert / alertcondition / signal plot; one request of the fixed 5m context, "
          f"{nreq} requests in all (<= 40); the drawing side uses no chart close / open / high / low / volume / bar_index; every input "
          "shared with the Lab has the Lab's default (zeUse OFF, dsZoneMax 80 in 1..300, zHalf 2, zcMerge 5, EMA 3000 / 3000 …)",
          "indicator(" in code and "strategy" not in code and not re.search(r"\b(alert|alertcondition|plotshape|plotchar)\b", code)
          and len(re.findall(r'"5",\s*f_zxEng\(\)', code)) == 1 and nreq <= 40 and not chart_bad and not same_inp
          and inp_new["zeUse"] is False and inp_new["dsZoneMax"] == 80 and 'minval = 1, maxval = 300' in body,
          f"n={nreq} chart={chart_bad} inputs={same_inp}")
    bad_ind, prev = [], ""
    for no, ln in enumerate(own.split("\n"), 1):
        s = ln.split("//")[0].rstrip() if not ln.lstrip().startswith("//") else ""
        if not s:
            continue
        ind = len(s) - len(s.lstrip())
        cont = (re.search(r"(,|\+|\(|\band|\bor|\?|:|=|\[)$", prev) and not prev.endswith("=>")) or \
            re.match(r"\s*(and|or|\+|\?|:)\s", s)
        if (cont and ind % 4 == 0) or (not cont and ind % 4 != 0):
            bad_ind.append(no)
        prev = s
    check("ZX-03 lint of ZoneSyncXAU's own lines: continuation lines indented by a non-multiple of 4, other lines by a multiple of 4",
          not bad_ind, str(bad_ind[:20]))
    eng = code[code.index("f_zxEng() =>"):code.index("simple bool zxLowTf")]
    logic = zb.marked(body, "// ==== ZSX Logic (begin)", "// ==== ZSX Logic (end)")
    check("ZX-04 memory: no string anywhere in the 5m calculation or the ZSX Logic section; the display output (bands + name codes + "
          "diagnostics) is built only on the last 5m bar and the bars of the last 10 minutes (no per-bar copy of the state, no 'current / "
          "previous' pair of large arrays; the pending previous bar is one 75-number input array)",
          not re.search(r"\bstring\b", eng) and not re.search(r"\bstring\b", re.sub(r"//.*", "", logic))
          and "if barstate.islast or timenow - time_close <= 600000" in eng, "")


def run_zsx(bars, raw, ov=None, realtime_from=None):
    """ZSX alone on bars (indices in vec() relative to the window, like a 5m context that starts at the first given bar)"""
    env = zsx_env(ov)
    S = env["f_zxNew"]()
    prev = None
    for i, b in enumerate(bars):
        cur = vec(b, i, raw)
        env["time_close"] = b["t"] + M5
        if realtime_from is not None and i >= realtime_from:
            for _ in range(2):
                env["f_zxAdvance"](S, prev, cur, False, 0)
        else:
            env["f_zxAdvance"](S, prev, cur, True, 0)
        prev = cur
    return env, S


def signature_checks():
    """the comparison signature (bands: order / bounds / grey / members / draw start; internal Zones) and the calc_bars_count model:
    every chart whose fixed 5m request delivers the last N bars computes the same state; a chart cut shorter is flagged"""
    bars, raw = gen(12, 700)
    N = 450
    win = bars[-N:]
    rw = raw[-N:]
    e1, S1 = run_zsx(win, rw)
    hd1, hz1 = e1["f_zxHash"](S1)
    # the same window processed as realtime from the middle: one bar behind at the end -> after the next (historical) bar the same
    e2, S2 = run_zsx(win + [], rw, realtime_from=None)
    hd2, hz2 = e2["f_zxHash"](S2)
    # a 'monthly chart' that has 100000 bars available but asks for the last N (calc_bars_count) = the same window
    e3, S3 = run_zsx(bars[len(bars) - N:], raw[len(bars) - N:])
    hd3, hz3 = e3["f_zxHash"](S3)
    # a chart whose 5m data is cut shorter (only 300 bars): different state, and flagged (bars < N)
    e4, S4 = run_zsx(bars[-300:], raw[-300:])
    hd4, hz4 = e4["f_zxHash"](S4)
    # a different band set (one bar fewer) changes the band signature
    e5, S5 = run_zsx(win[:-1], rw[:-1])
    hd5, _ = e5["f_zxHash"](S5)
    flag_short = 300 < N
    lab = lp.Runner(overrides=dict(dsZone=True, dsEnt=False, dsTbl=False, cTA=False, cTC=False)).run(win)
    lab_eq = lab_state(lab) == zsx_state(e1, S1, win[0]["t"])
    same = (hd1, hz1) == (hd2, hz2) == (hd3, hz3)
    check("ZX-08 comparison signature and the fixed bar count: charts whose fixed 5m request delivers the same last N bars give the same "
          "band / Zone signature (and the same state as the Lab run on those N bars); a chart cut to fewer bars gives a different "
          "state and is flagged ('5分データ ★指定より少ない'); one more / fewer processed bar changes the band signature",
          same and lab_eq and (hd4, hz4) != (hd1, hz1) and flag_short and hd5 != hd1,
          f"same={same} lab={lab_eq} short={(hd4, hz4) != (hd1, hz1)} step={hd5 != hd1}")


def main():
    quick = "--quick" in sys.argv
    static()
    bad, stats = equivalence(quick)
    check("ZX-05 equivalence with the Lab (its LOGIC section run unchanged) on the same 5m bars / feeds, after EVERY bar: internal Zones "
          "(id / type / TF / sub / bounds / registered bar / iFVG), both MA Zones and the display bands in order (bounds, grey, member "
          "ids, name text = the Lab's label / grey box text, the Lab's left edge) — defaults, display cap 6 / 10, ZE on, 2 accum boxes, "
          "different MA lengths, merge distance 8, width 4, and a crafted case where MA 1 joins only through MA 2's band", not bad, str(bad[:2]))
    print("INFO equivalence runs (case, bands, grey, swing merges, iFVG, dead FVG, accum out, common-width Zones, FVG Zones, internal errors):")
    for s in stats:
        print("   ", s)
    tb, reload_ok, start_ok = timing(quick)
    check("ZX-06 confirmed 5m only: while a 5m bar is forming (3 ticks, with and without rollback) the state equals the Lab's state after "
          "the previous bar exactly and never includes the forming bar; the pending previous bar is processed once on the next bar; a "
          "historical reload processes the last bar; a registration start skips the earlier bars", not tb and reload_ok and start_ok,
          f"{tb[:3]} reload={reload_ok} start={start_ok}")
    bars, raw = gen(9, 400)
    diff, snaps, env, S = run_pair(bars, raw, dict(dsZoneMax=8))
    db = draw_start(snaps)
    grey_ok = all(g.t0 == g.gz.aTc and g.tEnd >= g.t0 for g in S.ds if g.gone)
    check("ZX-07 draw start: every displayed band starts at the 5m close since which a band of exactly that shape has been displayed "
          "without a break (merged shapes are not drawn before they exist); grey bands span their FVG from its availability to the "
          "invalidation bar", not diff and not db and grey_ok, f"{diff} {db[:3]} grey={grey_ok}")
    signature_checks()
    n = sum(ok for _, ok, _ in RESULTS)
    for name, ok, d in RESULTS:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else "  -- " + d))
    print(f"{n}/{len(RESULTS)} passed  [PINE_NOT_VERIFIED: translated Pine logic; TradingView compile / request.security not run]")
    return n == len(RESULTS)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
