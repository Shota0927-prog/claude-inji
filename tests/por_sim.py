"""POR-1 checks — PocReactionStatsXAU.pine.   python3 tests/por_sim.py

Runs the "POR Logic" section of the indicator itself and its copied f_pocCore / f_feed (mechanical Pine-subset -> Python
translation by tests/acc_pine.py; history references x[k] inside the two POC functions are served from the synthetic
higher-TF series) on synthetic data. Shared harness: tests/mar_sim.py.

  S. static: HL (79e8d2f) copy regions byte-identical, f_pocCore / f_feed byte-identical to MtfPocFeedXAU.pine, the four
     request.security calls (60 / 240 / D / W, lookahead_on, no extra [1]), inputs, max_bars_back, table / notes
  A. the horizontal-line acceptance cases on the POC logic (from above and mirrored)
  P. POC cases 1-6 of the instruction (+ invalid 5m bar with a POC update, same-bar replacement, abnormal feed)
  F. case 7: f_pocCore / f_feed of this file == MtfPocFeedXAU's (both executed) == an independent full-scan POC on synthetic
     OHLCV (equal max-volume bins, zero-range bars, volume na, total volume 0, history < lookback, first bar)
  C. random 5m paths with POC feeds produced by the executed f_feed on aggregated OHLCV (+ invalid bars) vs an oracle
  B. invariants, X. mutations of the judgement functions (only the cases that must fail are checked)

Evidence class: PINE_NOT_VERIFIED (no TradingView compiler / replay here).
"""
import os
import random
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import acc_pine as ap     # noqa: E402
import mar_sim as ms      # noqa: E402
from mar_sim import R, B, A, M5, T0, bar, badbar, check, results, Engine, irecs  # noqa: E402

ROOT = ms.ROOT
POC = os.path.join(ROOT, "PocReactionStatsXAU.pine")
FEED = os.path.join(ROOT, "MtfPocFeedXAU.pine")
FEEDS = [f"pc{x}{k}" for k in (1, 2, 3, 4) for x in "LUT"]
TH = T0 - 3_600_000          # a confirmed higher-TF bar start before every test bar


def por_runner(overrides=None, keep=None, source=None, only1=True, **kw):
    s = source if source is not None else ms.read(POC)
    if keep is not None:
        s = ms.with_keep(s, keep)
    ov = {"pcUse2": False, "pcUse3": False, "pcUse4": False} if only1 else {}
    ov.update(overrides or {})
    return ms.Runner(POC, "POR", FEEDS, ov, source=s, **kw)


def pc(k, c, t=TH, half=0.5):
    return {f"pcL{k}": round(c - half, 2), f"pcU{k}": round(c + half, 2), f"pcT{k}": float(t)}


def por_kit(source=None):
    ref = pc(1, 4300.0)

    def make(rows):
        return [bar(0, 4330, 4332, 4328, 4330, **ref)] + [bar(n, *r, **ref) for n, r in enumerate(rows, start=1)]
    return dict(make=make, ref=ref, runner=lambda overrides=None, keep=None: por_runner(overrides, keep, source=source),
                mirror=lambda bars: ms.mirror(bars, price_keys=[("pcL1", "pcU1")]))


# ----------------------------------------------------------------------------------------------------------------
def por_static():
    s = ms.read(POC)
    ms.static_common(s, "POC", "PocReactionStatsXAU")
    code = "\n".join(ap.strip_comment(x) for x in s.split("\n"))
    f = ms.read(FEED)

    def blk(t):
        a = t[t.index("// ==== FEED POC core (begin)"):t.index("// ==== FEED POC core (end)")]
        b = t[t.index("f_feed(bool enabled, int lookback, int bins) =>"):]
        return a, b[:b.index("\n\n")]
    check("S POC f_pocCore / f_feed は MtfPocFeedXAU.pine と同一 (式・走査順・off = 1)", blk(s) == blk(f))
    req = re.findall(r'\[pcL(\d), pcU\1, pcT\1\] = request\.security\(syminfo\.tickerid, "(\w+)",\s+f_feed\(pcUse\1, pcLen\1, vpBins\), lookahead = barmerge\.lookahead_on\)', code)
    check("S POC 取得 60 / 240 / D / W・lookahead_on・戻り値に [1] なし", req == [("1", "60"), ("2", "240"), ("3", "D"), ("4", "W")]
          and not re.search(r"pc[LUT]\d\[", code), str(req))
    check("S POC 入力 (全 ON・本数 120 / 10〜1000・ビン 75 / 4〜100)・max_bars_back = 1100",
          all(f'pcUse{k} = input.bool(true, "{n} POC"' in code and f'pcLen{k} = input.int(120, "本数", minval = 10, maxval = 1000' in code
              for k, n in ((1, "1H"), (2, "4H"), (3, "D"), (4, "W")))
          and 'vpBins = input.int(75, "VP ビン数 (分割数)", minval = 4, maxval = 100' in code
          and 'indicator("PocReactionStatsXAU", shorttitle = "POR XAU", overlay = true, max_bars_back = 1100)' in code)
    check("S POC 欄外: 各時間足の現状・前回有効POC使用・有効POCなし・世代数",
          "前回有効POC使用" in code and "有効POCなし" in code and "世代 " in code and '"1H POC" : k == 1 ? "4H POC" : k == 2 ? "D POC" : "W POC"' in code
          and '"計算不能"' in code and '"履歴不足"' in code)


# ----------------------------------------------------------------------------------------------------------------
def poc_cases():
    B5 = {"hlBreak": 5.0}
    far = dict(o=4330, h=4332, l=4328, c=4330)
    # 1: a new centre 4300 received on a bar touching it -> 1 contact there; the replaced 4290 gets none
    r = por_runner(B5).run([bar(0, 4330, 4332, 4328, 4330, **pc(1, 4290.0)), bar(1, 4295, 4301, 4289, 4300, **pc(1, 4300.0))])
    check("P 1 新中心 4300 を受け取った足で接触 1 件・旧中心 4290 は 0 件",
          r["hcN"][:6] == [0, 0, 0, 1, 1, 1] and [o.p for o in r["hlPend"]] == [430000] and r["pcNGen"][0] == 2, f"{r['hcN'][:6]}")
    r = por_runner(B5).run([bar(0, 4330, 4332, 4328, 4330, **pc(1, 4300.0)), bar(1, 4302, 4303, 4299, 4301, **pc(1, 4300.0))])
    check("P 1b 受け取った足からの接触 (登録の次足まで待たない)", r["hcN"][0] == 1)
    r = por_runner(B5).run([bar(0, 4302, 4303, 4299, 4301, **pc(1, 4300.0))])
    check("P 1c 受け取ったその足が触れれば 1 件", r["hcN"][0] == 1)
    # 2: only the time (or the bin width) changes -> generation and hit kept; continuous contacts are not counted again
    bars = [bar(0, 4302, 4303, 4299, 4301, **pc(1, 4300.0, TH - 7_200_000)), bar(1, 4301, 4302, 4299.5, 4301, **pc(1, 4300.0, TH - 3_600_000)),
            bar(2, 4301, 4302, 4299.5, 4301, **pc(1, 4300.0, TH, half=1.0))]
    r = por_runner(B5)
    gens = []
    for b in bars:
        r.step(b)
        gens.append(r["pcGen"][0])
    check("P 2 時刻・区画幅だけの更新は世代・接触済みを維持・離脱なしの連続接触は増えない",
          r["hcN"][0] == 1 and gens == [1, 1, 1] and r["pcNGen"][0] == 1 and r["pcHit"][0] and r["pcTk"][0] == TH, f"gens={gens}")
    # 3: 4300 -> 4310 -> 4300 = 3 generations, each accepts its first contact
    bars = [bar(0, 4302, 4303, 4299, 4301, **pc(1, 4300.0)), bar(1, 4305, 4311, 4299.5, 4309, **pc(1, 4310.0)),
            bar(2, 4305, 4311, 4299.5, 4309, **pc(1, 4300.0))]
    r = por_runner(B5)
    gens = []
    for b in bars:
        r.step(b)
        gens.append(r["pcGen"][0])
    check("P 3 中心 4300 → 4310 → 4300 は 3 世代・各世代の初回接触を受け付ける",
          gens == [1, 2, 3] and r["pcNGen"][0] == 3 and r["hcN"][0] + r["hcN"][3] == 3, f"gens={gens} N={r['hcN'][:6]}")
    # 4: the observation at 4300 continues after the POC moves to 4310
    r = por_runner(B5, keep=1000).run([bar(0, 4330, 4332, 4328, 4330, **pc(1, 4300.0)), bar(1, 4302, 4304, 4299, 4303, **pc(1, 4300.0)),
                                       bar(2, 4303, 4310, 4302, 4309, **pc(1, 4310.0))])
    rr = results(r)
    po = sorted(o.p for o in r["hlPend"])
    check("P 4 POC が 4310 に変わっても元観測は 4300 基準で継続 ($10 反発)・新世代 4310 は初回接触",
          rr.get((1, 10)) == [(R, 1.0, 1.0)] and po == [430000, 431000] and r["hcN"][0] + r["hcN"][3] == 2, f"{rr} pend={po}")
    r = por_runner(B5, keep=1000).run([bar(0, 4330, 4332, 4328, 4330, **pc(1, 4300.0)), bar(1, 4302, 4304, 4299, 4303, **pc(1, 4300.0)),
                                       bar(2, 4303, 4304, 4302, 4303.5, **pc(1, 4310.0)), bar(3, 4303, 4304, 4295, 4296, **pc(1, 4310.0))])
    check("P 4b 世代更新だけでは未決着を消さず、元の基準 4300 − B で突破", results(r).get((1, 10)) == [(B, None, None)] and len(r["hlPend"]) == 0)
    # 5: all four TFs at the same centre -> one contact per TF; earlier generations are not counted
    allc = lambda c: {k_: v for k in (1, 2, 3, 4) for k_, v in pc(k, c).items()}    # noqa: E731
    r = por_runner(B5, only1=False).run([bar(0, 4330, 4332, 4328, 4330, **allc(4290.0)), bar(1, 4295, 4301, 4289, 4300, **allc(4300.0))])
    check("P 5 全時間足が同じ中心 → 4 系列で各 1 件・過去世代は数えない", [r["hcN"][k * 6 + 3] for k in range(4)] == [1, 1, 1, 1]
          and sum(r["hcN"]) == 12, str(r["hcN"]))
    # 6: calc-unavailable after a valid POC keeps the old centre; never valid -> no contacts
    bars = [bar(0, 4330, 4332, 4328, 4330, **pc(1, 4300.0)),
            dict(bar(1, 4302, 4303, 4299, 4301), pcL1=None, pcU1=None, pcT1=-float(TH + 3_600_000))]
    r = por_runner(B5).run(bars)
    check("P 6 計算不能を受信しても前回有効 POC (4300) で接触を集計・状態 = 計算不能",
          r["hcN"][0] == 1 and r["pcStat"][0] == 2 and r["pcP"][0] == 430000 and r["pcNGen"][0] == 1)
    r = por_runner(B5).run(bars[:1] + [dict(bar(1, 4302, 4303, 4299, 4301), pcL1=None, pcU1=None, pcT1=None)])
    check("P 6b 履歴不足 (時刻 na) も前回有効 POC を保持", r["hcN"][0] == 1 and r["pcStat"][0] == 3)
    r = por_runner(B5).run([dict(bar(0, 4302, 4303, 4299, 4301), pcL1=None, pcU1=None, pcT1=-float(TH)),
                            dict(bar(1, 4301, 4302, 4299, 4300.5), pcL1=None, pcU1=None, pcT1=None)])
    check("P 6c 有効 POC を一度も得ていなければ新規接触 0 (終値で代用しない)", sum(r["hcN"]) == 0 and r["pcStat"][0] == 3 and r["pcP"][0] is None)
    for desc, fv in (("上限 <= 下限", dict(pcL1=4300.5, pcU1=4299.5, pcT1=float(TH))), ("時刻がこの足以後", pc(1, 4310.0, T0 + 5 * M5)),
                     ("時刻が小数", pc(1, 4310.0, TH + 0.5)), ("下限 na", dict(pcL1=None, pcU1=4310.5, pcT1=float(TH)))):
        r = por_runner(B5).run([bar(0, 4330, 4332, 4328, 4330, **pc(1, 4300.0)), dict(bar(1, 4302, 4303, 4299, 4301), **fv)])
        check(f"P 6d 異常 ({desc}) は採用せず前回有効 POC を使う", r["pcStat"][0] == 9 and r["pcP"][0] == 430000 and r["hcN"][0] == 1)
    # invalid 5m bar: the POC update is accepted, that bar counts 0, the next valid bar is the generation's first contact
    r = por_runner(B5).run([bar(0, 4330, 4332, 4328, 4330, **pc(1, 4290.0)), badbar(1, 4310, 4304, 4299, 4302, **pc(1, 4300.0)),
                            bar(2, 4301, 4302, 4299.5, 4300.5, **pc(1, 4300.0))])
    check("P 7 不正 5分足でも POC 更新は受け付ける・その足は 0 件・次の有効足は世代の初回接触",
          r["pcNGen"][0] == 2 and r["hs"].nBad == 1 and r["hcN"][0] == 1, f"N={r['hcN'][:6]} gens={r['pcNGen']}")
    # same bar: replacement and contact; the old centre touched on the same bar is not counted; OFF TF never counts
    r = por_runner({"hlBreak": 5.0, "pcUse3": False}, only1=False).run(
        [bar(0, 4330, 4332, 4328, 4330, **allc(4300.0)), bar(1, 4302, 4303, 4299, 4301, **allc(4300.0))])
    check("P 8 OFF の時間足は数えない", [r["hcN"][k * 6] for k in range(4)] == [1, 1, 0, 1])


# ----------------------------------------------------------------------------------------------------------------
# F. the POC functions executed: this file's copy, MtfPocFeedXAU's original, an independent full scan
HIST = re.compile(r"\b(high|low|volume|time)\[(\w+)\]")


def poc_funcs(path):
    s = ms.read(path)
    a = s[s.index("f_pocCore(bool enabled"):s.index("// ==== FEED POC core (end)")]
    b = s[s.index("f_feed(bool enabled, int lookback, int bins) =>"):]
    b = b[:b.index("\n\n")]
    txt = HIST.sub(lambda m: f"_H_{m.group(1)}({m.group(2)})", a + "\n" + b + "\n")
    env = ap.make_env(ap.Broker(), [])
    env.update(array__new_float=lambda n=0, v=None: [v] * n)
    exec(compile(ap.Translator().translate(ap.logical_lines(txt)), f"<{os.path.basename(path)} POC>", "exec"), env)
    return env


def set_series(env, rows, i):
    env["bar_index"] = i
    for f, n in (("high", 1), ("low", 2), ("volume", 4), ("time", 5)):
        env[f"_H_{f}"] = (lambda n_: lambda k: rows[i - k][n_] if i - k >= 0 else None)(n)


def full_scan(rows, i, off, lookback, bins):
    """MtfPocDetector-style reference: every bin for every bar (no b0..b1 window)"""
    if i - off < lookback:
        return None
    win = [rows[i - k] for k in range(off, off + lookback)]
    if any(r[1] is None or r[2] is None or r[4] is None for r in win):
        return None
    hi, lo = None, None
    for r in win:
        hi = r[1] if hi is None else max(hi, r[1])
        lo = r[2] if lo is None else min(lo, r[2])
    rng = hi - lo
    if not rng > 0:
        return None
    bv = [0.0] * bins
    bs = rng / bins
    total = 0.0
    for r in win:
        ch, cl, cv = r[1], r[2], r[4]
        total += cv
        cr = ch - cl
        if cr <= 0:
            bi = max(0, min(bins - 1, int((cl - lo) / bs)))
            bv[bi] += cv
        else:
            for bi in range(bins):
                bb = lo + bi * bs
                ov = min(bb + bs, ch) - max(bb, cl)
                if ov > 0:
                    bv[bi] += cv * ov / cr
    if not total > 0:
        return None
    best, bi_ = -1.0, 0
    for bi in range(bins):
        if bv[bi] > best:
            best, bi_ = bv[bi], bi
    pl = lo + bi_ * bs
    return (pl, pl + bs)


def htf_rows(seed, n, special=True):
    """(open, high, low, close, volume, time) with edge cases"""
    rnd = random.Random(seed)
    rows, p = [], 4300.0
    for i in range(n):
        o = p
        c = round(o + rnd.gauss(0, 6), 2)
        h = round(max(o, c) + abs(rnd.gauss(0, 3)), 2)
        l = round(min(o, c) - abs(rnd.gauss(0, 3)), 2)
        v = float(rnd.randint(1, 900))
        if special:
            u = rnd.random()
            if u < 0.06:
                h = l = round(o, 2)              # zero range
            elif u < 0.08:
                v = None                         # volume na
            elif u < 0.12:
                v = 0.0
        rows.append((o, h, l, c, v, T0 + i * 3_600_000))
        p = c
    return rows


def feed_compare():
    mine, orig = poc_funcs(POC), poc_funcs(FEED)
    cases = []
    rows = htf_rows(5, 260)
    for L, nb in ((10, 75), (12, 4), (30, 100), (120, 75)):
        cases.append((f"乱数 (値幅0・volume na・0 を含む) L={L} bins={nb}", rows, L, nb))
    # equal max-volume bins -> the lower bin; total volume 0; flat window; history < lookback
    tie = [(4300, 4301, 4300, 4301, 100.0, T0 + i * 3_600_000) if i % 2 == 0 else (4310, 4311, 4310, 4311, 100.0, T0 + i * 3_600_000)
           for i in range(40)]
    zero = [(4300 + i, 4301 + i, 4299 + i, 4300 + i, 0.0, T0 + i * 3_600_000) for i in range(40)]
    flat = [(4300, 4300, 4300, 4300, 50.0, T0 + i * 3_600_000) for i in range(40)]
    cases += [("最大出来高区画が同量 → 下側", tie, 10, 22), ("合計 volume 0", zero, 10, 75), ("値幅 0 の窓", flat, 10, 75)]
    total = mism = nref = 0
    kinds = {"normal": 0, "neg": 0, "na": 0}
    tie_lower = None
    for name, rws, L, nb in cases:
        bad = []
        for i in range(len(rws)):
            set_series(mine, rws, i)
            set_series(orig, rws, i)
            a = mine["f_feed"](True, L, nb)
            b = orig["f_feed"](True, L, nb)
            ref = full_scan(rws, i, 1, L, nb)
            tk = rws[i - 1][5] if i >= 1 else None
            want = (None, None, None) if tk is None else ((None, None, -float(tk)) if ref is None else (ref[0], ref[1], float(tk)))
            total += 1
            kinds["na" if a[2] is None else "neg" if a[2] < 0 else "normal"] += 1
            if not (a == b == want):
                bad.append((i, a, b, want))
            if ref is not None:
                nref += 1
            if name.startswith("最大") and a[0] is not None:
                tie_lower = (a[0], a[1])
        mism += len(bad)
        check(f"F f_pocCore / f_feed: {name} — 写し == MtfPocFeedXAU == 全区画走査", not bad, str(bad[:2]))
    off = mine["f_feed"](False, 10, 75)
    check("F f_feed: OFF は時刻 0・上下限 na、初回足は時刻 na、履歴不足は負の時刻", off == (None, None, 0.0) and kinds["na"] >= 1 and kinds["neg"] > 10
          and kinds["normal"] > 100, f"{kinds} total={total}")
    check("F 同量の最大区画は下側 (4300 側) を選ぶ", tie_lower is not None and tie_lower[0] < 4305, str(tie_lower))


# ----------------------------------------------------------------------------------------------------------------
def make_poc_path(seed, n=4000):
    """5m bars + the f_feed outputs of aggregated 1H / 4H / D / W bars, delivered like request.security(lookahead_on)"""
    rnd = random.Random(seed)
    rows, p = [], 4300.0
    for i in range(n):
        o = round(p + (rnd.uniform(-4, 4) if rnd.random() < 0.05 else 0), 2)
        c = round(o + rnd.gauss(0, 1.3), 2)
        h = round(max(o, c) + abs(rnd.gauss(0, 0.8)), 2)
        l = round(min(o, c) - abs(rnd.gauss(0, 0.8)), 2)
        rows.append([o, h, l, c, float(rnd.randint(1, 400)) if rnd.random() > 0.0015 else None])
        p = c
    fn = poc_funcs(POC)
    blocks = {1: 12, 2: 24, 3: 48, 4: 96}     # synthetic scale: every TF gets enough completed bars
    lens = {1: 10, 2: 10, 3: 10, 4: 10}
    bins = (6, 12, 75)[seed % 3]
    feeds = [dict() for _ in range(n)]
    for k, L in blocks.items():
        hb = []
        for s in range(0, n, L):
            seg = rows[s:s + L]
            vol = None if any(r[4] is None for r in seg) else sum(r[4] for r in seg)
            hb.append((seg[0][0], max(r[1] for r in seg), min(r[2] for r in seg), seg[-1][3], vol, T0 + s * M5))
        for m in range(len(hb)):
            set_series(fn, hb, m)
            lo, up, tt = fn["f_feed"](True, lens[k], bins)
            for i in range(m * L, min((m + 1) * L, n)):
                feeds[i].update({f"pcL{k}": lo, f"pcU{k}": up, f"pcT{k}": tt})
    bars = [dict(t=T0 + i * M5, o=r[0], h=r[1], l=r[2], c=r[3], **feeds[i]) for i, r in enumerate(rows)]
    for i in range(5, n):
        if rnd.random() < 0.012:
            k = rnd.randrange(3)
            if k == 0:
                bars[i][rnd.choice("ohlc")] = None
            elif k == 1:
                bars[i]["h"] = round(max(bars[i]["o"], bars[i]["c"]) - 0.4, 2)
            else:
                bars[i]["l"] = round(min(bars[i]["o"], bars[i]["c"]) + 0.4, 2)
    return bars, bins


def poc_oracle(bars, B):
    en = Engine(B, 4)
    en.start()
    last, P, hit, gens = [None] * 4, [None] * 4, [False] * 4, [0] * 4
    for b in bars:
        t = b["t"]
        bad = Engine.bad(b)
        if bad:
            en.invalid(t)
        else:
            en.update(*(en.tk(b[x]) for x in "ohlc"), t)
        for k in range(4):
            tt, lo, up = b.get(f"pcT{k + 1}"), b.get(f"pcL{k + 1}"), b.get(f"pcU{k + 1}")
            ok = tt is not None and tt > 0 and abs(tt) >= 1e11 and abs(tt) < t and tt == round(tt) and lo is not None and up is not None and up > lo
            if ok:
                c = (lo + up) / 2.0
                if last[k] is None or c != last[k]:
                    last[k], P[k], hit[k] = c, en.tk(c), False
                    gens[k] += 1
        if not bad:
            o, h, l, c = (en.tk(b[x]) for x in "ohlc")
            for k in range(4):
                if P[k] is None or not (l <= P[k] <= h):
                    continue
                if hit[k] and not (en.prev is not None and (en.prev[2] > P[k] or en.prev[1] < P[k])):
                    continue
                hit[k] = True
                en.contact(k, P[k], last[k], o, h, l, c, t)
            en.prev = (o, h, l, c)
    return en, gens


def poc_random(seeds):
    wg = 0
    for seed in seeds:
        bars, bins = make_poc_path(seed)
        Bw = (15.0, 5.0, 3.0)[seed % 3]
        r = por_runner({"hlBreak": Bw}, keep=10 ** 6, only1=False).run(bars)
        en, gens = poc_oracle(bars, Bw)
        g, c = en.agg(), r.counters()
        same = all(c[k] == g[k] for k in g) and irecs(r) == en.recs and list(r["pcNGen"]) == gens
        nN = sum(g["hcN"]) // 3
        st = [sum(1 for b in bars if b.get(f"pcT{k}") is not None and b[f"pcT{k}"] < 0) for k in (1, 2, 3, 4)]
        check(f"C POC random seed {seed} (B={Bw}, bins={bins}) == oracle (集計・確定記録の全件と順序・世代数)",
              same and nN > 100 and g["bad"] > 15 and min(gens[:3]) >= 2, f"contacts={nN} gens={gens} calc-unavailable bars={st} unk={sum(g['hlUnk'])} "
              f"bad={g['bad']} recs={len(en.recs)} diff={[k for k in g if c[k] != g[k]]} recs_equal={irecs(r) == en.recs}")
        wg += gens[3]
    check("C POC random: W も複数世代を含む (全シード計)", wg >= 5, f"W generations={wg}")
    return bars


def main():
    por_static()
    ms.hl_cases(por_kit())
    poc_cases()
    feed_compare()
    bars = poc_random([1, 2, 4, 5])
    ms.invariants(lambda overrides=None, keep=None, **kw: por_runner(overrides, keep, only1=False, **kw), bars, "POC")
    ms.mutations(POC, por_kit, ms.MUTS, "POC")
    sys.exit(1 if ms.report() else 0)


if __name__ == "__main__":
    main()
