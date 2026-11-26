"""ZCR-10 checks — ZoneConfluenceReactionStatsXAU.pine (2-evidence pair reaction).   PYTHONDONTWRITEBYTECODE=1 python3 tests/zcr_sim.py [seeds]

Runs the "ZCR Logic" section (and the "ZCR Display calc" section) of the indicator itself, translated mechanically to Python by
tests/acc_pine.py (unchanged), on synthetic confirmed 5m bars. Everything request.* / input.source would deliver is given per 5m bar
(the feeds of tests/zcr9_sim.py: ZA f{k}*, ZC s{k}*, ZD zd*{k}, ZF g{k}*, ZG zgPk*, ZE ze*), plus the EMA at the bar's close
(m1 / m5 -> zbMa1 / zbMa2, as tests/zcs_sim.py).

  S. static: copies == ZCS (types, the zone index, f_zsOk / f_zsFvgSide / f_zsBetter / f_zsTouch / f_zsContact, the registration block)
     and == ZCR-9 (detection / requests, thresholds, the Lab copies), plots <= 64, no strategy / alert, PINE_NOT_VERIFIED, git status
  1. a third evidence added / removed (input OFF, feed removed) -> the records of the pairs of the remaining evidences are identical
  2. another evidence added while a pair is in contact -> no new contact of that pair (fixed cases)
  3. invariants on all 1,950 rows (new = adopted + skipped, adopted = results + tracking + cut + unmeasurable, tracking == open
     observations), widths independent (fixed cases: one position per pair x direction x width, no adoption on the settling bar)
  4. CSV: records output + queue + tracking == all new contacts (no loss / duplicate), counts recomputed from the records == the table,
     at most K records per bar (FIFO); distribution of new contacts per bar and the drain of the queue (measured, reported)
  5. ZCS: per record vs tests/zcs_sim.py's ZCS runner (one pair x direction selected, filter OFF): (a) armed band / contact bar,
     (b) fill price / intra-bar outcome — counted separately
  6. ZCR-9's touch-bar / first-hit rules kept: fixed paths vs tests/zcr9_sim.py's ZCR-9 runner (edge base) on the same zones
  B. f_zrBest == ZCS's f_zsBest restricted to the next bar's reach (direct, every bar of random runs)
  D. display calc: rows / filters / order / pair names / rate
  K. causality: a run on the first half == the first half of the full run
  P. performance: loop counts per bar (instrumented copy), reported
  X. mutations of the logic that the checks must catch

Evidence class: PINE_NOT_VERIFIED (no TradingView compiler / CSV export here; request.* semantics are not reproduced).
"""
import collections
import copy
import math
import os
import random
import re
import subprocess
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import acc_pine as ap        # noqa: E402
import zcr9_sim as z9        # noqa: E402
import zcs_sim as zs         # noqa: E402
import zcr_csv_tabs as ct    # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PINE = os.path.join(ROOT, "ZoneConfluenceReactionStatsXAU.pine")
ZCS = os.path.join(ROOT, "ZoneConfluenceStrategyXAU.pine")
Z9REF = os.path.join(ROOT, "tests", "zcr9_reference.pine")
DOC = os.path.join(ROOT, "ZONE_CONFLUENCE_REACTION_XAU_ja.md")
BEGIN, END = "// ==== ZCR Logic (begin) ", "// ==== ZCR Logic (end) "
DB, DE = "// ==== ZCR Display calc (begin) ", "// ==== ZCR Display calc (end) "
M1, M5 = 60_000, 300_000
T0 = z9.T0
MT = 0.01
GN = z9.GN
GI = {n: i for i, n in enumerate(GN)}
NF, K = 15, 4
RESULTS = []
INFO = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


def info(s):
    INFO.append(s)


def read(p):
    return open(p, encoding="utf-8").read()


def between(t, a, b):
    i = t.index(a)
    return t[t.index("\n", i) + 1:t.index(b, i)]


def tk(x):
    return math.floor(x / MT + 0.5)


def pair_no(a, b):
    a, b = sorted((a, b))
    return a * (51 - a) // 2 + b - a - 1


PAIRS = [(a, b) for a in range(25) for b in range(a + 1, 26)]
assert all(pair_no(a, b) == i for i, (a, b) in enumerate(PAIRS))


def pdn(a, b, s):
    """ペア・方向の番号: names or ids, s = "L" / "S" """
    a = GI.get(a, a)
    b = GI.get(b, b)
    return pair_no(a, b) * 2 + (0 if s == "L" else 1)


ALL_ON = dict(zaUse1=True, zaUse2=True, zaUse3=True, zbUse1=True, zbUse2=True, zcUse1=True, zcUse2=True, zcUse3=True, zcUse4=True,
              zdUse1=True, zdUse2=True, zdUse3=True, zdUse4=True, zeUse=True, zeUse4=True, zeUseD=True, zfUse1=True, zfUse2=True,
              zfUse3=True, zfUse4=True, zgUse1=True, zgUse4=True, zgUseD=True)
ALL_OFF = {k: False for k in ALL_ON}
ONLY_ZC = dict(ALL_OFF, zcUse1=True, zcUse2=True, zcUse3=True, zcUse4=True)


def prog(src):
    return ap.Translator().translate(ap.logical_lines(between(src, BEGIN, END)))


def prog_ds(src):
    return ap.Translator().translate(ap.logical_lines(between(src, DB, DE)))


def _insert(arr, i, v):
    if i is None or i < 0 or i > len(arr):
        raise ap.PineRuntimeError("array.insert out of bounds")
    arr.insert(i, v)


def _sort_indices(a, order):
    idx = list(range(len(a)))
    return sorted(idx, key=lambda i: a[i], reverse=(order == "desc"))


CODE_CACHE = {}


class Runner:
    """bars: dicts t, tc (default t + 5m), o, h, l, c, feeds by name, m1 / m5 (EMA at the bar's close)."""

    def __init__(self, ov=None, src=None, maxpend=None, drop=(), pre=None):
        s = src if src is not None else read(PINE)
        if maxpend is not None:
            cap = "int   ZC_MAXPEND = 2000 "
            assert s.count(cap) == 1
            s = s.replace(cap, f"int   ZC_MAXPEND = {maxpend} ")
        key = s
        if key not in CODE_CACHE:
            CODE_CACHE[key] = (compile(prog(s), "<ZCR-10>", "exec"), compile(prog_ds(s), "<ZCR-10 display>", "exec"))
        self.code, self.dcode = CODE_CACHE[key]
        inp = ap.inputs(s)
        inp.setdefault("zcStart", z9.START0)
        ov = dict(ov or {})
        for k in ("zcWarm", "zbWarm1"):
            if k not in ov:
                inp[k] = 0
        for k in ov:
            if k not in inp:
                raise KeyError(k)
        inp.update(ov)
        self.inp = inp
        env = ap.make_env(ap.Broker(), [])
        env.update(inp)
        env.update(array__new=lambda n=0, v=None: [v] * n, array__insert=_insert, math__ceil=math.ceil, array__copy=lambda a: list(a),
                   array__indexof=lambda arr, v: arr.index(v) if v in arr else -1, array__includes=lambda arr, v: v in arr,
                   str__split=lambda s_, sep: s_.split(sep), str__tonumber=z9.tonum, zdProto=10001,
                   array__sort_indices=_sort_indices, order=types.SimpleNamespace(descending="desc", ascending="asc"),
                   syminfo__mintick=MT, hlRun=True, _VARS=set(), _VARIPS=set(), __first__=True)
        self.env = env
        self.drop = set(drop)          # feeds not delivered (a kind removed at the source)
        self.pre = pre                 # hook called before each bar (env, bar) — B checks
        self.bi = -1
        self.out = []                  # (bar index, [record...]) of every bar with an output
        self.nnew = []                 # new contacts per bar
        self.qlen = []

    def step(self, b):
        self.bi += 1
        e = self.env
        if self.pre is not None and not e["__first__"]:
            self.pre(self, b)
        e.update(time=b["t"], time_close=b.get("tc", b["t"] + M5), bar_index=self.bi, barstate__isconfirmed=True, open=b["o"], high=b["h"],
                 low=b["l"], close=b["c"], zbMa1=b.get("m1"), zbMa2=b.get("m5"))
        for f in z9.FEEDS:
            e[f] = None if f in self.drop else b.get(f)
            if f.startswith("zgPk") and e[f] is None:
                e[f] = ""
        exec(self.code, e)
        e["__first__"] = False
        o = e["zcOut"]
        recs = [o[r * NF:(r + 1) * NF] for r in range(K) if o[r * NF] is not None]
        assert all(all(x is None for x in o[r * NF:(r + 1) * NF]) for r in range(len(recs), K))
        if recs:
            self.out.append((self.bi, [list(x) for x in recs]))
        self.nnew.append(len(e["zrNp"]))
        self.qlen.append(len(e["zcQ"]))
        return self

    def run(self, bars):
        for b in bars:
            self.step(b)
        return self

    def __getitem__(self, k):
        return self.env[k]

    # ---- views ----
    def cnt(self, key, item):
        return self.env["zrCnt"][key * 9 + item]

    def rows(self):
        c = self.env["zrCnt"]
        return [tuple(c[k * 9:(k + 1) * 9]) for k in range(1950)]

    def out_recs(self):
        return [r for _, rs in self.out for r in rs]

    def queue_recs(self):
        return [list(q.v) for q in self.env["zcQ"]]

    def pend_recs(self):
        """the records the tracking observations would give now (state 0 for open widths), made from the objects (nothing changed)"""
        out = []
        for ob in self.env["zcPend"]:
            v = [ob.id, ob.pi, ob.t0 / 1000.0, ob.za, ob.zb, ob.zta / 1000.0, ob.ztb / 1000.0, ob.cT * MT, ob.cL * MT, ob.p0 * MT,
                 ob.fSt[0] * 100 + ob.fSt[1] * 10 + ob.fSt[2], ob.flags * 1000 + ob.tbJ[0] * 100 + ob.tbJ[1] * 10 + ob.tbJ[2]]
            v += [None if x is None else x / 1000.0 for x in ob.fTc]
            out.append(v)
        return out

    def all_recs(self):
        return self.out_recs() + self.queue_recs() + self.pend_recs()

    def ds(self, name, *a):
        """run a function of the Display calc section on the current state"""
        e = self.env
        exec(self.dcode, e)
        return e[name](*a)


def rec(v):
    """a record (15 values) -> dict (prices in ticks, times in ms)"""
    st = int(v[10])
    tj = int(v[11])
    return dict(id=int(v[0]), pd=int(v[1]), pair=int(v[1]) // 2, d=1 if int(v[1]) % 2 == 0 else -1, t0=round(v[2] * 1000), za=int(v[3]), zb=int(v[4]),
                ta=round(v[5] * 1000), tb=round(v[6] * 1000), top=tk(v[7]), bot=tk(v[8]), p0=tk(v[9]),
                st=(st // 100, st // 10 % 10, st % 10), tbj=(tj // 100 % 10, tj // 10 % 10, tj % 10), flags=tj // 1000,
                tc=tuple(None if x is None else round(x * 1000) for x in v[12:15]))


def ident(r):
    """a record without the zone IDs / record number (they depend on the other evidences' registrations)"""
    return (r["pd"], r["t0"], r["ta"], r["tb"], r["top"], r["bot"], r["p0"], r["st"], r["tbj"], r["flags"], r["tc"])


# ----------------------------------------------------------------------------------------------------------------
# data
def rbars(seed, n5=2500):
    return zs.zcs_bars(seed, n5)


def rows_bars(rows, feeds0, start=4310.0, feeds=None, bad=()):
    bars = z9.bars_from_rows(rows, feeds0, start=start, feeds=feeds)
    for i in bad:
        bars[i]["h"] = round(max(bars[i]["o"], bars[i]["c"]) - 1.0, 2)
    return bars


BASE = z9.merge(z9.zc(2, 1, 4300.0), z9.zc(3, -1, 4301.0))      # ZC-D 4298..4302, ZC-W 4299..4303 -> common 4299..4302
PL = pdn("ZC-D", "ZC-W", "L")
PS = pdn("ZC-D", "ZC-W", "S")


def recs_of(r, pd):
    return sorted((rec(v) for v in r.all_recs() if int(v[1]) == pd), key=lambda x: x["t0"])


# ----------------------------------------------------------------------------------------------------------------
# S. static
def blk(t, a, b, incl_b=False):
    i = t.index(a)
    j = t.index(b, i)
    return t[i:j + (len(b) if incl_b else 0)]


def func(t, sig):
    """a top-level function: its signature line up to the next blank line"""
    i = t.index("\n" + sig) + 1
    j = t.index("\n\n", i)
    return t[i:j]


def static():
    s, z, r9 = read(PINE), read(ZCS), read(Z9REF)
    # copies from ZCS
    a = blk(s, "// Zone 1 個。", "// ペア・方向 1 個")
    check("S 写し (ZCS と byte 一致): LbZone / LbAcc / ZsIdx の型", a == blk(z, "// Zone 1 個。", "// ペア・方向 1 個") and len(a) > 1000)
    a = blk(s, "f_inc(array<int> a, int ix, int v) =>", "// ---- ZCR-10: ペア別の計測")
    b = blk(z, "f_inc(array<int> a, int ix, int v) =>", "// 発注の候補 (終値 c") + blk(z, "// 確定 5分足 [l, h] に触れた候補", "// 上位足サッツバンドで")
    check("S 写し (ZCS と byte 一致): f_inc / f_ds* / f_zsLower / f_zsUpper / f_lbAdd / f_lbRemoveS / f_lbRemove / Lab の関数 / f_swAdd / f_zcMaSet / "
          "f_zcGid / f_zsIxOf / f_zsOk / f_zsFvgSide / f_zsMaIdx / f_zsBetter / f_zsTouch / f_zsContact (f_zsBest だけ除く)",
          a == b and "f_zsContact(ZsPd p, int h, int l) =>" in a and "f_zsBest(" not in a, f"{len(a)} {len(b)}")
    a = blk(s, "        // ==== LAB register (begin)", "        // ==== LAB register (end) ====", True)
    b = blk(z, "        // ==== LAB register (begin)", "        // ==== LAB register (end) ====", True)
    check("S 写し (ZCS と byte 一致): Zone の登録 / 更新 / 失効のブロック (= ZCR-9 のブロック)", a == b and a == blk(r9, "        // ==== LAB register (begin)", "        // ==== LAB register (end) ====", True))
    zb_s = blk(s, "        // ==== LAB register (end) ====", "        for k = 0 to 1\n            if array.get(lbZeStat")
    zb_z = blk(z, "        // ==== LAB register (end) ====", "\n\n    // ---- (4) 注文")
    check("S ZB の帯: 足 k の確定時点の EMA (zbMa1 / zbMa2) で足 k の終わりに置き直し、索引を作り直す (ZCS と同じ行)", zb_s.rstrip("\n") == zb_z.rstrip("\n") and "f_zsMaIdx()" in zb_s, zb_s)
    # from ZCR-9: detection / requests (only the ZB [1] lines changed), thresholds and the Lab copies
    d_s = blk(s, "// ---- ZA: Accum 検出", "bool hlRun")
    d_9 = blk(r9, "// ---- ZA: Accum 検出", "bool hlRun")
    l9 = [x for x in d_9.split("\n") if not x.startswith(("float zbP1", "float zbP5", "// ---- ZB: EMA"))]
    ls = [x for x in d_s.split("\n") if not x.startswith("// ---- ZB: EMA")]
    check("S Zone の検知・取得 (ZA〜ZG の検出関数・request) は ZCR-9 と byte 一致 (ZB の [1] の 2 行と見出しだけ削除・変更)", ls == l9 and len(ls) > 400, f"{len(ls)} {len(l9)}")
    a = blk(s, "// 閾値 (ティック", "// ==== LAB copy zgParse (end)")
    check("S 写し (ZCR-9 と byte 一致): 閾値 (zcWT / zcDepT / zcDepMs)・f_za/zb/zc/zdUse・LAB copy use・f_zgShow・f_zgParse", a == blk(r9, "// 閾値 (ティック", "// ==== LAB copy zgParse (end)"))
    i9 = ap.inputs(r9)
    ii = ap.inputs(s)
    same = [k for k in i9 if k in ii and i9[k] != ii[k]]
    zone_keys = [k for k in i9 if not k.startswith(("zcP0", "zcKind", "zcView", "zcDirMode", "zcHzMode", "zcPerPage", "zcPage", "zcOnMode", "zcPlMode", "zcShowLbl"))]
    check("S Zone・判定の入力は ZCR-9 と同じ名前・初期値 (起点切替と ZCR-9 の表示の入力だけ削除)", not same and all(k in ii for k in zone_keys),
          str(same) + str([k for k in zone_keys if k not in ii]))
    code = "\n".join(ap.strip_comment(x) for x in s.split("\n"))
    np_ = len(re.findall(r"^plot\(", code, re.M))
    check("S plot は 64 本以下 (記録 15 列 × 4 件 = 60 + 状態 3 = 63)、strategy / alert なし", np_ == 63 and "strategy(" not in code and "alert" not in code, str(np_))
    rq_s = len(re.findall(r"request\.security\(", code))
    rq_9 = len(re.findall(r"request\.security\(", "\n".join(ap.strip_comment(x) for x in r9.split("\n"))))
    check("S request.security の数は ZCR-9 と同じ", rq_s == rq_9, f"{rq_s} {rq_9}")
    check("S 削除したもの: 場所の極大集合・K1 / K2・時間内統計 (9 条件)・根拠集合別 / 根拠数別の表・起点切替 (終値起点)",
          all(x not in code for x in ("f_zcPlace", "zcP0Mode", "zrMask", "ZcRow", "zcWin", "wMfe", "nFxK1", "zcEdgeP0")))
    lines = s.split("\n")
    badi = [x for x in lines if x.strip() and not x.lstrip(" ").startswith("//") and (len(x) - len(x.lstrip(" "))) % 4 not in (0, 1)]
    check("S 継続行以外のインデントは 4 の倍数、タブなし", not badi and "\t" not in s, str(badi[:3]))
    check("S 冒頭と仕様書に未検証 (PINE_NOT_VERIFIED) の明記", "PINE_NOT_VERIFIED" in s.split("indicator(")[0] and "PINE_NOT_VERIFIED" in read(DOC))
    mine = {"ZoneConfluenceReactionStatsXAU.pine", "tests/zcr_sim.py", "ZONE_CONFLUENCE_REACTION_XAU_ja.md", "tests/zcr9_reference.pine",
            "tests/zcr9_sim.py", "tests/zcs_sim.py", "tests/zcr_csv_tabs.py"}
    try:
        stt = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
        lines_ = [x for x in stt.split("\n") if x.strip() and "__pycache__" not in x]
        other = [x for x in lines_ if x[3:] not in mine]
        check("S git status: 変更・追加は ZCR-10 のファイルだけ (ZCS 本体・tests/zcs_build.py ほかは未変更)", not other, str(lines_))
        zr9 = subprocess.run(["git", "show", "1f0469e:ZoneConfluenceReactionStatsXAU.pine"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
        check("S tests/zcr9_reference.pine == ZCR-9 (1f0469e) の本体", zr9 == r9)
    except Exception as ex:        # noqa: BLE001
        check("S git status / ZCR-9 の取得", False, repr(ex))


# ----------------------------------------------------------------------------------------------------------------
# 1. a third evidence added / removed
OFF_SETS = [
    ("ZD 全部 OFF", dict(zdUse1=False, zdUse2=False, zdUse3=False, zdUse4=False), (9, 10, 11, 12)),
    ("ZG・ZA-4H OFF", dict(zgUse1=False, zgUse4=False, zgUseD=False, zaUse2=False), (19, 20, 21, 1)),
    ("ZB・ZC-1H OFF", dict(zbUse1=False, zbUse2=False, zcUse1=False), (3, 4, 5)),
]
DROP_FEEDS = [("ZD の取得値を外す (Zone が登録されない)", [f"zd{x}{k}" for k in (1, 2, 3, 4) for x in "LUT"], (9, 10, 11, 12)),
              ("ZC-4H / ZC-W の取得値を外す", ["s2h", "s2ht", "s2l", "s2lt", "s4h", "s4ht", "s4l", "s4lt"], (6, 8))]


def by_pd(r, gone):
    out = collections.defaultdict(list)
    for v in r.all_recs():
        x = rec(v)
        a, b = PAIRS[x["pair"]]
        if a in gone or b in gone:
            continue
        out[x["pd"]].append(ident(x))
    return {k: sorted(v) for k, v in out.items()}


def rows_kept(r, gone):
    return [row for k, row in enumerate(r.rows()) if PAIRS[k // 6][0] not in gone and PAIRS[k // 6][1] not in gone]


def third_evidence(seeds):
    for seed in seeds:
        bars = rbars(seed)
        full = Runner(ALL_ON).run(bars)
        for name, ov, gone in OFF_SETS:
            r = Runner(dict(ALL_ON, **ov)).run(bars)
            a, b = by_pd(full, gone), by_pd(r, gone)
            n = sum(len(v) for v in a.values())
            check(f"1 seed {seed}: 第 3 の根拠を削除 ({name}) → 残った根拠同士の全ペアの記録 (起点・帯・接触の時刻・結果・決着時刻・判定) と表の行が一致",
                  a == b and rows_kept(full, gone) == rows_kept(r, gone) and n > 50 and full["st"].oSeq > r["st"].oSeq,
                  f"recs={n} full={full['st'].oSeq} off={r['st'].oSeq} diff={[k for k in set(a) | set(b) if a.get(k) != b.get(k)][:5]}")
        for name, feeds, gone in DROP_FEEDS[seed % 2:seed % 2 + 1]:
            r = Runner(ALL_ON, drop=feeds).run(bars)
            a, b = by_pd(full, gone), by_pd(r, gone)
            check(f"1 seed {seed}: 第 3 の根拠を取得側で除く ({name}) → 残ったペアの記録と表の行が一致 (追加の向きでも同じ: full = 追加後)",
                  a == b and rows_kept(full, gone) == rows_kept(r, gone) and sum(len(v) for v in a.values()) > 50)


# ----------------------------------------------------------------------------------------------------------------
# 2 / 3 / 6. fixed cases
def run_rows(rows, feeds0=BASE, ov=None, start=4310.0, feeds=None, bad=(), **kw):
    return Runner(dict(ONLY_ZC, **(ov or {})), **kw).run(rows_bars(rows, feeds0, start=start, feeds=feeds, bad=bad))


def fixed_cases():
    ZD = z9.zd(2, 4301.0)          # ZD-D 4299..4303 (zHalf 2)
    pzd = pdn("ZC-D", "ZD-D", "L")
    ov_zd = dict(zdUse3=True)
    # F1 basic: LONG above the band, the low reaches the top 4302 -> one new contact, P0 = 4302, band 4299..4302, T0 = time_close of bar 1
    r = run_rows([(4310, 4311, 4301, 4305), (4305, 4306, 4303, 4305)])
    x = recs_of(r, PL)
    check("F1 帯より上から安値が上端 4302 に届く → (ZC-D, ZC-W) LONG の新規接触 1 件。帯 4299〜4302、P0 = 上端 4302、T0 = タッチ足の time_close",
          len(x) == 1 and (x[0]["top"], x[0]["bot"], x[0]["p0"], x[0]["t0"]) == (tk(4302), tk(4299), tk(4302), T0 + 2 * M5) and r["st"].oSeq == 1, str(x))
    r = run_rows([(4310, 4311, 4302.01, 4305)])
    r2 = run_rows([(4302, 4302, 4302, 4302), (4302, 4302, 4296, 4296)], start=4302.0)
    check("F2 安値が上端に 0.01 届かない → 新規接触なし。終値が上端ちょうど (終値 > 上端でない) → 武装しない (次の足で下がっても新規接触なし。接触中になるだけ)",
          r["st"].oSeq == 0 and r2["st"].oSeq == 0 and r2["zsPd"][PL].on, f"{r['st'].oSeq} {r2['st'].oSeq}")
    r = run_rows([(4290, 4300, 4289, 4295)], start=4290.0)
    x = recs_of(r, PS)
    check("F3 SHORT: 帯より下から高値が下端 4299 に届く → SHORT の新規接触、P0 = 下端 4299", len(x) == 1 and x[0]["p0"] == tk(4299) and x[0]["d"] == -1, str(x))
    r = run_rows([(4296, 4297, 4295, 4296)])
    x = recs_of(r, PL)
    check("F4 ギャップで帯の下から始まった足 (始値 4296 < 下端) も安値 <= 上端なので新規接触 (ZCS の始値約定の足と同じ)。起点は帯端 4302 に固定",
          len(x) == 1 and x[0]["p0"] == tk(4302), str(x))
    # 2. another evidence added while in contact
    rows = [(4310, 4311, 4301, 4305), (4305, 4307, 4304, 4306), (4306, 4306, 4301, 4303), (4303, 4304, 4302.5, 4303)]
    ra = run_rows(rows, ov=ov_zd)
    rb = run_rows(rows, ov=ov_zd, feeds={2: ZD})
    xa, xb = recs_of(ra, PL), recs_of(rb, PL)
    check("2a 接触中 (足 1 で新規接触、離脱前) に ZD-D 4299〜4303 が足 2 で登録 → 足 3 で帯に戻っても (ZC-D, ZC-W) LONG は再計上されない (ZD なしと同じ 1 件・同じ記録)",
          len(xa) == 1 and [ident(q) for q in xa] == [ident(q) for q in xb] and rb["zsPd"][PL].on, f"{xa} {xb}")
    y = recs_of(rb, pzd)
    check("2b 同じ場面で、追加した根拠を含む別のペア (ZC-D, ZD-D) は自分の規則だけで数える (足 2 の終値 4306 > 共通帯の上端 4302 で武装 → 足 3 で新規接触 1 件)。"
          "(ZC-D, ZC-W) の件数は変わらない",
          len(y) == 1 and y[0]["t0"] == T0 + 4 * M5 and rb.cnt(PL * 3, 0) == 1 and ra.cnt(PL * 3, 0) == 1, str(y))
    rows2 = [(4310, 4311, 4300, 4301), (4301, 4302, 4300, 4301), (4301, 4302, 4300, 4301.5)]
    rc = run_rows(rows2, ov=ov_zd, feeds={1: ZD})
    check("2c 価格が帯の中に居るまま ZD-D が登録 → どのペアも新規接触なし (終値が帯の中では武装しない。接触中になるだけ)",
          rc["st"].oSeq == 1 and rc["zsPd"][pzd].on and rc.cnt(pzd * 3, 0) == 0, f"{rc['st'].oSeq}")
    # departure and re-contact: distance 5 from the contact band, then again above -> a second new contact
    rows3 = [(4310, 4311, 4301, 4305), (4308, 4312, 4307.01, 4311), (4311, 4311, 4301, 4304)]
    rd = run_rows(rows3)
    rows4 = [(4310, 4311, 4301, 4305), (4306.99, 4307, 4306.99, 4306.99), (4306.99, 4306.99, 4301, 4304)]
    re_ = run_rows(rows4)
    check("2d 離脱 (接触の帯の上端から 5 ドル以上離れた足) の後に帯へ戻る → 2 件目の新規接触。4.99 ドルでは離脱せず再計上しない",
          rd.cnt(PL * 3, 0) == 2 and re_.cnt(PL * 3, 0) == 1, f"{rd.cnt(PL * 3, 0)} {re_.cnt(PL * 3, 0)}")
    rows5 = [(4310, 4311, 4301, 4305)] + [(4305, 4306, 4303, 4305)] * 6 + [(4305, 4305, 4301, 4303)]
    rows5b = [(4310, 4311, 4301, 4305)] + [(4305, 4306, 4303, 4305)] * 5 + [(4305, 4305, 4301, 4303)]
    rf, rg = run_rows(rows5), run_rows(rows5b)
    check("2e 時間の離脱: 接触の帯の完全に外側が 30 分 (6 本) 続いた後に戻る → 2 件目。5 本 (25 分) では離脱せず 1 件",
          rf.cnt(PL * 3, 0) == 2 and rg.cnt(PL * 3, 0) == 1, f"{rf.cnt(PL * 3, 0)} {rg.cnt(PL * 3, 0)}")
    # 3. widths independent
    rows6 = [(4310, 4311, 4301.5, 4304), (4304, 4308, 4303, 4307.5), (4308, 4311, 4308, 4310), (4310, 4310, 4301, 4303)]
    r = run_rows(rows6)
    x = recs_of(r, PL)
    ok = (len(x) == 2 and x[0]["st"][0] == 1 and x[0]["tc"][0] == T0 + 3 * M5 and x[1]["st"] == (0, 9, 9)
          and r.cnt(PL * 3, 1) == 2 and r.cnt(PL * 3 + 1, 2) == 1 and r.cnt(PL * 3 + 2, 2) == 1 and r["zrBusy"][PL * 3:PL * 3 + 3] == [1, 1, 1])
    check("3a 値幅ごとに独立: $5 は足 2 で反発先に決着、$10 / $15 は未決着のまま離脱 → 足 4 の 2 件目は $5 だけ採用、$10 / $15 は見送り (後から採用しない)",
          ok, str([(q["st"], q["tc"]) for q in x]))
    rows7 = ([(4310, 4311, 4301, 4303)] + [(4303, 4306, 4303, 4305)] * 6 + [(4305, 4305, 4303.5, 4305), (4306, 4307.2, 4301, 4303)])
    r = run_rows(rows7)
    x = recs_of(r, PL)
    check("3b 1 件目の $5 が決着した足と同じ足の新規接触は $5 も見送り (足の中の順序を推測して同じ足で採用しない)",
          len(x) == 2 and x[0]["st"][0] == 1 and x[0]["tc"][0] == x[1]["t0"] and x[1]["st"][0] == 9, str([(q["st"], q["tc"], q["t0"]) for q in x]))
    rows8 = [(4310, 4311, 4301, 4303), (4308, 4320, 4308, 4319), (4319, 4319, 4301, 4310)]
    r = run_rows(rows8)
    x = recs_of(r, PL)
    check("3c 全値幅が決着した後に離脱 → 次の新規接触は全値幅で採用", len(x) == 2 and x[0]["st"] == (1, 1, 1) and 9 not in x[1]["st"], str([q["st"] for q in x]))
    # bad bar -> unmeasurable; the cap -> cut
    r = run_rows([(4310, 4311, 4301, 4304), (4304, 4305, 4303, 4304), (4304, 4305, 4303, 4304)], bad=(2,))
    x = recs_of(r, PL)
    check("3d 決着前の不正足 → 未決着の値幅は計測不能 (4)、決着時刻 = その足", len(x) == 1 and x[0]["st"] == (4, 4, 4) and x[0]["tc"][0] == T0 + 3 * M5, str(x))
    rows9 = [(4310, 4311, 4301, 4303), (4308, 4312, 4307.5, 4311), (4311, 4311, 4301, 4303), (4303, 4304, 4302.5, 4303)]
    r = run_rows(rows9, maxpend=1)
    x = recs_of(r, PL)
    check("3e 追跡中の記録が上限を超えたら古い順に未決着の値幅を打ち切り (5)。打切りは表の打切り列と記録に出る",
          r["st"].nCut == 1 and x[0]["st"][2] == 5 and r.cnt(PL * 3 + 2, 7) == 1, str([q["st"] for q in x]))


# ----------------------------------------------------------------------------------------------------------------
# 6. ZCR-9 rules vs the ZCR-9 runner
Z9_PATHS = [
    ("タッチ足の終値で $5 反発確認 → タッチ足で反発先 (経過 0 分)", [(4310, 4311, 4301, 4308), (4308, 4320, 4307, 4319)], ()),
    ("タッチ足の安値で $5 逆行到達 → タッチ足で逆行先", [(4310, 4310, 4296.5, 4300), (4300, 4320, 4299, 4319)], ()),
    ("タッチ足の高値だけ $5 (終値で未確認 = 判定 4) → 後で逆行先なら順序不明", [(4310, 4310, 4301, 4303), (4303, 4304, 4296, 4297), (4297, 4330, 4296, 4329)], ()),
    ("タッチ足で終値確認と逆行到達の両方 → 順序不明", [(4310, 4310, 4296, 4308), (4308, 4330, 4307, 4329)], ()),
    ("始値が P0 より下 (帯の中へギャップ) の足でも同じ規則", [(4300, 4303, 4296.5, 4301), (4301, 4330, 4299, 4329)], ()),
    ("次の足の始値が目標を越えている → 始値で決着", [(4310, 4311, 4301, 4304), (4312, 4313, 4290, 4291), (4291, 4330, 4280, 4329)], ()),
    ("同じ足で両側に届く → 順序不明", [(4310, 4311, 4301, 4304), (4304, 4318, 4286, 4300), (4300, 4330, 4299, 4329)], ()),
    ("不正足 → 計測不能", [(4310, 4311, 4301, 4304), (4304, 4305, 4303, 4304), (4304, 4330, 4303, 4329)], (2,)),
    ("SHORT: 下から高値が下端に届き、後で下落", [(4290, 4300, 4289, 4294), (4294, 4295, 4270, 4271)], ()),
]


def z9_rules():
    n = 0
    for name, rows, bad in Z9_PATHS:
        start = 4290.0 if "SHORT" in name else 4310.0
        bars = rows_bars(rows, BASE, start=start, bad=bad)
        r10 = Runner(ONLY_ZC).run(copy.deepcopy(bars))
        r9 = z9.Runner(dict(z9.ONLY_ZC, zcP0Mode=z9.EDGE)).run(copy.deepcopy(bars))
        x = recs_of(r10, PS if "SHORT" in name else PL)
        e9 = [dict(t0=round(v[1] * 1000), p0=tk(v[2]), fst=[int(v[38 + j]) for j in range(3)], fmin=[v[41 + j] for j in range(3)],
                   tbj=[int(v[47 + j]) for j in range(3)], flags=int(v[32])) for v in r9.records()]
        e9 += [dict(t0=o["t0"], p0=o["p0"], fst=o["fst"], fmin=o["fmin"], tbj=o["tbj"], flags=o["flags"]) for o in r9.pending()]
        e9.sort(key=lambda o: o["t0"])
        ok = bool(x) and bool(e9)
        det = ""
        if ok:
            a, v = x[0], e9[0]
            tc9 = tuple(None if (v["fst"][j] in (0, 4, 5) or v["fmin"][j] is None) else v["t0"] + int(v["fmin"][j]) * M1 for j in range(3))
            tc10 = tuple(None if s_ in (0, 4, 5) else t_ for s_, t_ in zip(a["st"], a["tc"]))
            ok = (v["p0"] == a["p0"] and v["t0"] == a["t0"] and tuple(v["fst"]) == a["st"] and tuple(v["tbj"]) == a["tbj"] and tc9 == tc10
                  and (v["flags"] & 32768 > 0) == (a["flags"] > 0) and len(x) == 1)
            det = f"ZCR-9 {v} | ZCR-10 {a}"
        n += ok
        check(f"6 ZCR-9 の帯端起点と同じ判定 ({name}): 起点・T0・結果 3 幅・決着時刻・タッチ足判定・フラグ", ok, det)


# ----------------------------------------------------------------------------------------------------------------
# 3 / 4. invariants and CSV on random runs
def invariants(r):
    bad = []
    rows = r.rows()
    open_w = collections.Counter()
    for ob in r["zcPend"]:
        for j in range(3):
            if ob.fSt[j] == 0:
                open_w[ob.pi * 3 + j] += 1
    for k, c in enumerate(rows):
        if c[0] != c[1] + c[2] or c[1] != sum(c[3:9]) or c[8] != open_w.get(k, 0) or r["zrBusy"][k] != (1 if c[8] else 0) or c[8] > 1:
            bad.append((k, c, open_w.get(k, 0), r["zrBusy"][k]))
    return bad


def from_records(recs):
    """the table counts recomputed from records (state 0 = still tracking)"""
    cnt = [[0] * 9 for _ in range(1950)]
    for x in recs:
        for j, s in enumerate(x["st"]):
            c = cnt[x["pd"] * 3 + j]
            c[0] += 1
            if s == 9:
                c[2] += 1
            else:
                c[1] += 1
                c[{0: 8, 1: 3, 2: 4, 3: 5, 4: 6, 5: 7}[s]] += 1
    return [tuple(c) for c in cnt]


def csv_checks(r, label):
    outs = [rec(v) for v in r.out_recs()]
    q = [rec(v) for v in r.queue_recs()]
    p = [rec(v) for v in r.pend_recs()]
    ids = [x["id"] for x in outs + q + p]
    n = r["st"].oSeq
    check(f"4 {label}: 出力済み + 出力待ち + 追跡中 = 全新規接触 (記録番号 1..{n} が欠落・重複なし)。出力は確定した順 (FIFO)",
          sorted(ids) == list(range(1, n + 1)) and len(ids) == len(set(ids)) and r["st"].nOut == len(outs) and r["st"].nDone == len(outs) + len(q),
          f"n={n} out={len(outs)} q={len(q)} p={len(p)}")
    check(f"4 {label}: 1 足の出力は {K} 件まで、出力待ちがある限り毎足 {K} 件出す (出し切れない分は次の足へ)",
          all(len(rs) <= K for _, rs in r.out) and all((len(dict(r.out).get(i, [])) == K) or r.qlen[i] == 0 for i in range(len(r.qlen))))
    rc = from_records(outs + q + p)
    check(f"4 {label}: 記録 (出力済み + 出力待ち + 追跡中) から再計算した集計 == 表の 1,950 行 (新規接触・採用・見送り・各結果・追跡中)", rc == r.rows())
    ro = from_records(outs)
    unout = sum(1 for _ in q) + len(p)
    tot_tab = sum(c[0] for c in r.rows()) // 3
    check(f"4 {label}: CSV (出力済み) だけの新規接触 + 未出力 (出力待ち + 追跡中) = 表の新規接触 (欠けている件数は表の「未出力」と一致)",
          sum(c[0] for c in ro) // 3 + unout == tot_tab == n, f"csv={sum(c[0] for c in ro) // 3} unout={unout} tab={tot_tab}")
    # the CSV of the chart export (one row per bar, the plots as columns, empty = na) -> tests/zcr_csv_tabs.py
    titles = re.findall(r'^plot\(array\.get\(zcOut, \d+\),\s+"([^"]+)"', read(PINE), re.M)
    header = ["time"] + titles
    rows_csv = []
    outd = dict(r.out)
    for i in range(len(r.nnew)):
        vals = [""] * len(titles)
        for k, v in enumerate(outd.get(i, [])):
            for x in range(NF):
                vals[k * NF + x] = "" if v[x] is None else repr(v[x])
        rows_csv.append([str(i)] + vals)
    got = ct.records_from_rows(header, rows_csv)
    check(f"4 {label}: チャート書き出し相当の CSV (足ごとの R1〜R4 の plot) → tests/zcr_csv_tabs.py の集計 == 出力済みの記録の集計 (記録番号の重複・欠落なし)",
          len(titles) == K * NF and sorted(got) == sorted(x["id"] for x in outs) and [tuple(c) for c in ct.tally(got)] == ro)
    allr, lg, sh = ct.tabs(ct.tally(got))
    check(f"4 {label}: 3 タブ (全 1,950 行 / LONG 先着率 50% 以上 / SHORT 50% 以上、ちょうど 50% を含む・最低件数なし)",
          len(allr) == 1950 and all(r_[2] == "LONG" and r_[13] >= 50 for r_ in lg) and all(r_[2] == "SHORT" and r_[13] >= 50 for r_ in sh)
          and len(lg) + len(sh) == sum(1 for r_ in allr if r_[13] != "" and r_[7] >= r_[8]))
    st_ok = all(all(s != 0 for s in x["st"]) for x in outs + q) and all(any(s == 0 for s in x["st"]) for x in p)
    check(f"4 {label}: 出力済み・出力待ちの記録に追跡中 (0) は無い (全採用値幅が決着した記録だけ出す)、追跡中の記録には必ず未決着がある", st_ok)
    return outs


def random_runs(seeds):
    hist = collections.Counter()
    nbar = 0
    qmax = 0
    unout_end = []
    stats = collections.Counter()
    runs = {}
    for seed in seeds:
        bars = rbars(seed)
        r = Runner(ALL_ON if seed % 2 else None).run(bars)
        runs[seed] = (bars, r)
        bad = invariants(r)
        rows = r.rows()
        check(f"3 seed {seed}: 全 1,950 行で 新規接触 = 採用 + 見送り、採用 = 反発先 + 逆行先 + 順序不明 + 追跡中 + 打切り + 計測不能、"
              "追跡中 = 未決着の観測 (値幅ごとに同時 1 件以下・追跡中フラグと一致)",
              not bad and sum(c[0] for c in rows) > 300 and sum(c[2] for c in rows) > 20, f"{bad[:3]} new={sum(c[0] for c in rows)} skip={sum(c[2] for c in rows)}")
        outs = csv_checks(r, f"seed {seed}")
        for c in rows:
            for i, nm in enumerate(("new", "adopt", "skip", "reb", "adv", "unk", "bad", "cut", "trk")):
                stats[nm] += c[i]
        for x in outs:
            stats["tb_settle"] += sum(1 for s, t in zip(x["st"], x["tc"]) if s in (1, 2, 3) and t == x["t0"])
            stats["flag"] += 1 if x["flags"] else 0
        hist.update(r.nnew)
        nbar += len(r.nnew)
        qmax = max(qmax, max(r.qlen))
        unout_end.append((seed, len(r["zcQ"]), len(r["zcPend"]), r["st"].oSeq))
        on_ok = sorted(r["zrOnL"]) == sorted(p.pi for p in r["zsPd"] if p.on)
        check(f"3 seed {seed}: 接触中の一覧 (zrOnL) == 接触中のペア・方向 (重複なし)", on_ok and len(set(r["zrOnL"])) == len(r["zrOnL"]))
    need = dict(reb=300, adv=300, unk=10, bad=3, skip=50, tb_settle=50, flag=1)
    check("3 乱数系列の合計で各区分が使われている (反発先・逆行先・順序不明・計測不能・見送り・タッチ足で決着・判定 4 から順序不明)",
          all(stats[k] >= v for k, v in need.items()), str(dict(stats)))
    tot = sum(hist.values())
    dist = {k: hist[k] for k in sorted(hist)}
    info(f"[4] 1 足あたりの新規接触 (全 650 ペア・方向、{len(seeds)} 系列 × 2500 本 = {nbar} 本): 度数 {dist}、"
         f"平均 {sum(k * v for k, v in hist.items()) / tot:.3f}、最大 {max(hist)}、K = {K} を超える足 {sum(v for k, v in hist.items() if k > K)} 本、"
         f"出力待ちの最大 {qmax}、履歴末尾の未出力 (系列, 出力待ち, 追跡中, 全記録) {unout_end}")
    info(f"[3] 区分の合計 (全系列・全行): {dict(stats)}")
    return runs


# ----------------------------------------------------------------------------------------------------------------
# B. f_zrBest == ZCS f_zsBest restricted to the reach of the next bar
def zs_best_code():
    z = read(ZCS)
    src = func(z, "f_zsBest(ZsPd p, int c) =>")
    return compile(ap.Translator(known_types=("ZsIdx", "LbZone", "ZsPd")).translate(ap.logical_lines(src)), "<ZCS f_zsBest>", "exec")


def best_checks(seeds):
    code = zs_best_code()
    stat = collections.Counter()
    bad = []

    def pre(run, b):
        e = run.env
        st = e["st"]
        if not st.live or b["o"] is None or b["h"] is None or b["l"] is None or b["c"] is None or b["h"] < max(b["o"], b["c"]) or b["l"] > min(b["o"], b["c"]):
            return
        exec(code, e)
        rnd = random.Random(run.bi)
        h, l = tk(b["h"]), tk(b["l"])
        for p in rnd.sample(e["zsPd"], 40):
            if p.on:
                continue
            q1, q2 = copy.copy(p), copy.copy(p)
            f1 = e["f_zsBest"](q1, st.pC)
            lim = l if p.d == 1 else h
            f2 = e["f_zrBest"](q2, st.pC, lim)
            want = f1 and (q1.cT >= lim if p.d == 1 else q1.cL <= lim)
            stat["n"] += 1
            stat["zs"] += f1
            stat["reach"] += want
            if f2 != want or (want and (q1.cL, q1.cT, q1.ca.id, q1.cb.id) != (q2.cL, q2.cT, q2.ca.id, q2.cb.id)):
                bad.append((run.bi, p.pi, f1, f2, want))
    for seed in seeds:
        Runner(ALL_ON, pre=pre).run(rbars(seed, 1500))
    check("B f_zrBest (次の足の安値 / 高値に届く候補だけ探す) == ZCS の f_zsBest の最良が届くときのその候補 (届かないときは無し)。乱数 3 系列の毎足 40 ペア・方向",
          not bad and stat["reach"] > 100 and stat["zs"] > stat["reach"], f"{dict(stat)} {bad[:3]}")


# ----------------------------------------------------------------------------------------------------------------
# 5. ZCS: per record
ZCS_PAIRS = [("ZC-D", "ZC-W"), ("ZA-4H", "ZC-D"), ("ZD-D", "ZF-FVG-4H"), ("ZB-5m", "ZC-W"), ("ZC-1H", "ZD-4H"), ("ZF-iFVG-1H", "ZC-4H"),
             ("ZB-1m", "ZD-1H"), ("ZC-4H", "ZF-FVG-1H")]


def zcs_compare(runs):
    tot = collections.Counter()
    fails = []
    for seed, (bars, r) in runs.items():
        if seed % 2 == 0:
            continue                    # the runs with all kinds ON
        recs = collections.defaultdict(list)
        for v in r.all_recs():
            x = rec(v)
            recs[x["pd"]].append(x)
        for a, b in ZCS_PAIRS:
            for s in "LS":
                pd = pdn(a, b, s)
                zr_ = zs.Runner([(a, b, s)], dict(zsX=15))
                oband = []
                for bb in bars:
                    zr_.step(bb)
                    q = zr_.env["zsPd"][0]
                    oband.append((q.oL, q.oT) if q.act else None)     # the working order's band at the end of each bar
                br = zr_.broker
                tr = br.trades_all()
                fills = {t["bar"]: t for t in tr}
                mine = {x["t0"]: x for x in recs[pd]}
                t2b = {bb.get("tc", bb["t"] + M5): i for i, bb in enumerate(bars)}
                cbar = {t2b[t]: x for t, x in mine.items()}
                # (a) candidates / bands / contact bars
                for fb, t in fills.items():
                    tot["zcs_fill"] += 1
                    x = cbar.get(fb)
                    ob_ = oband[fb - 1]
                    if x is None:
                        tot["a_fill_without_contact"] += 1
                        fails.append(("a", seed, pd, fb))
                    elif ob_ is None or (x["p0"], x["bot"], x["top"]) != (t["lim"], ob_[0], ob_[1]):
                        tot["a_band_diff"] += 1
                        fails.append(("a band", seed, pd, fb, x, t))
                    else:
                        tot["a_same"] += 1
                pos = set()
                for t in tr:
                    xb = t["xbar"] if t["xbar"] is not None else len(bars)
                    pos.update(range(t["bar"], xb))       # in position at the end of these bars (exit bar: flat at its end)
                for cb, x in cbar.items():
                    if cb in fills:
                        continue
                    if cb - 1 in pos:
                        tot["a_contact_zcs_in_position"] += 1
                        tot["a_contact_zcs_in_position_zcr15_" + ("skipped" if x["st"][2] == 9 else "adopted")] += 1
                    else:
                        tot["a_contact_without_fill"] += 1
                        fails.append(("a extra", seed, pd, cb))
                # (b) fill price / outcome ($15 = zsX) for the matched ones
                for fb, t in fills.items():
                    x = cbar.get(fb)
                    if x is None:
                        continue
                    tot["b_gap_fill" if t["px"] != t["lim"] else "b_fill_at_p0"] += 1
                    s15 = x["st"][2]
                    why = t["why"]
                    if s15 == 9:
                        tot["b_zcr_skipped_15"] += 1
                    elif why is None:
                        tot["b_zcs_open"] += 1
                    elif s15 == 0:
                        tot["b_zcr_tracking"] += 1
                    elif (why, s15) in (("TP", 1), ("SL", 2)) and t["xbar"] == bars_index(bars, x["tc"][2]):
                        tot["b_same_result_same_bar"] += 1
                    elif (why, s15) in (("TP", 1), ("SL", 2)):
                        tot["b_same_result_other_bar"] += 1
                    elif s15 == 3:
                        tot["b_zcr_unknown_zcs_" + why] += 1
                    elif s15 == 4:
                        tot["b_zcr_unmeasurable"] += 1
                    else:
                        tot[f"b_diff_zcs_{why}_zcr_{s15}"] += 1
    ok = tot["a_fill_without_contact"] == 0 and tot["a_band_diff"] == 0 and tot["a_contact_without_fill"] == 0 and tot["a_same"] > 50
    check("5 ZCS との個別照合 (a): ZCS の約定はすべて同じ足・同じ帯 (下端・上端)・P0 = 指値の ZCR-10 新規接触。ZCR-10 だけの新規接触は "
          "すべて ZCS がその前の足の終わりに保有中だった足 (ZCS は 1 ポジションで発注しない)", ok, f"{dict(tot)} {fails[:3]}")
    info("[5] ZCS 照合の内訳 (乱数 seed 奇数・全種類 ON、ペア " + ", ".join(f"{a}×{b}" for a, b in ZCS_PAIRS) + " × L / S、ZCS zsX = $15): " + str(dict(sorted(tot.items()))))


def bars_index(bars, tc):
    if tc is None:
        return None
    for i, b in enumerate(bars):
        if b.get("tc", b["t"] + M5) == tc:
            return i
    return None


# ----------------------------------------------------------------------------------------------------------------
# D. display calc
def display_checks(r):
    rows = r.ds("f_dsRows", -1, -1, False, False)
    check("D 絞り込みなし・番号順 = 1,950 行、キー (ペア番号 * 2 + 方向) * 3 + 値幅 の昇順", rows == list(range(1950)))
    rows2 = r.ds("f_dsRows", 1, 2, True, True)
    exp = sorted([k for k in range(1950) if (k // 3) % 2 == 1 and k % 3 == 2 and r.cnt(k, 0) > 0], key=lambda k: (-r.cnt(k, 0), k))
    check("D SHORT・$15・多い順・0 件を隠す = 新規接触の降順 (同数はキー順)", rows2 == exp and len(exp) > 10, f"{rows2[:5]} {exp[:5]}")
    ab = [tuple(r.ds("f_dsAB", p)) for p in range(325)]
    check("D ペア番号 → 根拠 (a, b) が ZCS の番号付け (ZC_GN 順の a < b の辞書順) と一致", ab == PAIRS)
    check("D 先着率 = 反発先 / (反発先 + 逆行先)、0 / 0 は —、ちょうど 50%", r.ds("f_dsRate", 0, 0) == "—" and r.ds("f_dsRate", 1, 1) == "50%" and r.ds("f_dsRate", 2, 1) == "66.7%")
    check("D 合計 = 行の和", r.ds("f_dsSum", rows, 0) == sum(c[0] for c in r.rows()) and r.ds("f_dsSum", rows, 8) == sum(c[8] for c in r.rows()))
    check("D ページ数・ページの丸め", r.ds("f_dsPages", 0, 20) == 1 and r.ds("f_dsPages", 41, 20) == 3 and r.ds("f_dsPage", 9, 3) == 3 and r.ds("f_dsPage", 0, 3) == 1)


# ----------------------------------------------------------------------------------------------------------------
# K. causality
def causality(seed=3):
    bars = rbars(seed, 1600)
    full = Runner(ALL_ON).run(bars)
    half = Runner(ALL_ON).run(bars[:800])
    alt = copy.deepcopy(bars[:800]) + copy.deepcopy(rbars(seed + 100, 1600)[800:])
    r3 = Runner(ALL_ON)
    for b in alt[:800]:
        r3.step(b)
    cut = [x for x in full.out if x[0] < 800]
    check("K 前半だけの実行 == 全体の実行の前半 (出力・表・接触中)。後半を差し替えても前半は同じ",
          cut == half.out and cut == r3.out and full.nnew[:800] == half.nnew)


# ----------------------------------------------------------------------------------------------------------------
# P. performance (instrumented copy)
LOOPS = [("f_zrHas", "            LbZone z = array.get(ix.z, k)\n"), ("f_zrBest 外側", "            LbZone zo = array.get(io.z, k)\n"),
         ("f_zrBest 内側", "                        LbZone zi = array.get(ii.z, j)\n"), ("f_zsTouch 外側", "            LbZone za = array.get(ia.z, k)\n"),
         ("f_zsTouch 内側", "                    LbZone zb = array.get(ib.z, j)\n"), ("二分探索", "        int mid = int((lo + hi) / 2)\n")]


def perf(seeds=(1, 3)):
    s = read(PINE)
    for i, (_, ln) in enumerate(LOOPS):
        ind = ln[:len(ln) - len(ln.lstrip(" "))]
        assert ln in s, ln
        s = s.replace(ln, ln + f"{ind}f_inc(zrLoop, {i}, 1)\n")
    tot = []
    for seed in seeds:
        r = Runner(ALL_ON, src=s)
        r.env["zrLoop"] = [0] * len(LOOPS)
        per = []
        prev = [0] * len(LOOPS)
        work = []
        pw = 0
        for b in rbars(seed):
            r.step(b)
            cur = list(r.env["zrLoop"])
            per.append(sum(cur) - sum(prev))
            prev = cur
            work.append(r["st"].nWork - pw)
            pw = r["st"].nWork
        tot.append((seed, sum(per) / len(per), max(per), sum(work) / len(work), max(work), dict(zip([n for n, _ in LOOPS], r.env["zrLoop"])), len(r["zcPend"])))
    for seed, avg, mx, wa, wm, br, npd in tot:
        info(f"[P] seed {seed} (全種類 ON、2500 本): Zone 走査ループ + 二分探索の反復 = 1 足平均 {avg:.0f} / 最大 {mx}、"
             f"候補探索・接触判定を呼んだペア・方向 = 1 足平均 {wa:.1f} / 最大 {wm}、内訳 {br}")
    check("P 性能の目安を測った (1 足の反復回数の平均・最大を報告)", all(x[1] > 0 for x in tot))


# ----------------------------------------------------------------------------------------------------------------
# X. mutations
MUTATIONS = [
    ("見送りせず毎回採用する", "        if array.get(zrBusy, ix) == 0\n            array.set(zrBusy, ix, 1)", "        if true\n            array.set(zrBusy, ix, 1)"),
    ("接触中でも武装する", "                        if not p.on\n                            st.nWork += 1", "                        if true\n                            st.nWork += 1"),
    ("新規接触の記録を古い記録の更新の前に追跡中へ入れる (同じ足で更新される)",
     "    int oi0 = 0\n    while oi0 < array.size(zcPend)",
     "    if array.size(zrNw) > 0\n        for i = 0 to array.size(zrNw) - 1\n            array.push(zcPend, array.get(zrNw, i))\n    array.clear(zrNw)\n    int oi0 = 0\n    while oi0 < array.size(zcPend)"),
    ("新規接触したペア・方向を接触中の一覧に入れない", "                array.push(zrOnL, array.get(zrNp, i))", "                int dummy = array.get(zrNp, i)"),
    ("起点を帯の中央にする", "p.d == 1 ? p.cT : p.cL, p.cT, p.cL,", "int((p.cT + p.cL) / 2), p.cT, p.cL,"),
    ("判定 4 の後の逆行先を順序不明にしない", "                if res == 2 and array.get(ob.tbJ, j) == 4", "                if false"),
    ("f_zrBest で次の足に届く条件を外す", "(p.d == 1 ? ct < c and ct >= lim : cl > c and cl <= lim)", "(p.d == 1 ? ct < c : cl > c)"),
    ("1 足に 1 件しか出力しない", "    int nq = math.min(ZR_K, array.size(zcQ))", "    int nq = math.min(1, array.size(zcQ))"),
]


def mutations():
    s0 = read(PINE)
    saved = (list(RESULTS), list(INFO))
    for name, a, b in MUTATIONS:
        assert s0.count(a) == 1, name
        s = s0.replace(a, b)
        RESULTS.clear()
        caught = False
        try:
            fixed_cases_src(s)
            z9_rules_src(s)
            r = Runner(ALL_ON, src=s).run(rbars(5, 1200))
            if invariants(r):
                RESULTS.append(("inv", False, ""))
            csv_checks(r, "mut")
            caught = any(not ok for _, ok, _ in RESULTS)
        except Exception:         # noqa: BLE001
            caught = True
        RESULTS[:] = saved[0]
        check(f"X 変異「{name}」を検出", caught)
    INFO[:] = saved[1]




def fixed_cases_src(s):
    global Runner
    orig = Runner

    class R2(orig):
        def __init__(self, ov=None, src=None, **kw):
            super().__init__(ov, src=s if src is None else src, **kw)
    Runner = R2
    try:
        fixed_cases()
    finally:
        Runner = orig


def z9_rules_src(s):
    global Runner
    orig = Runner

    class R2(orig):
        def __init__(self, ov=None, src=None, **kw):
            super().__init__(ov, src=s if src is None else src, **kw)
    Runner = R2
    try:
        z9_rules()
    finally:
        Runner = orig


def main():
    seeds = [int(x) for x in sys.argv[1:]] or [1, 2, 3, 4, 5, 6]
    static()
    fixed_cases()
    z9_rules()
    runs = random_runs(seeds)
    display_checks(runs[seeds[0]][1])
    third_evidence(seeds[:3])
    best_checks(seeds[:3])
    zcs_compare(runs)
    causality()
    perf()
    mutations()
    bad = 0
    for name, ok, det in RESULTS:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else "  " + det))
        bad += 0 if ok else 1
    for s in INFO:
        print("INFO " + s)
    print(f"{len(RESULTS) - bad}/{len(RESULTS)} passed")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
