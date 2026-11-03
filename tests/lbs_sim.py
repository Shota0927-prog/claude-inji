"""LBS-1 fixture — the five symbol versions of the Zone Combo Lab (ZoneComboLab{BTCUSD,GBPJPY,USDJPY,EURUSD,GBPUSD}.pine).

  python3 tests/lbs_sim.py

  * static: every file == tests/lbs_build.py build() from the gold version at LAB-5 (so the difference from the gold version is the
    exact edit list and nothing else); the gold / normal / external files unchanged; defaults; one conversion of the 9 distances
  * conversion: the LBS Unit block itself (translated Pine) gives the price differences (EURUSD 2 pips = 0.0002, USDJPY 3 pips = 0.03 ...)
  * lots / qty: f_qty of each file (translated Pine) against an independent calculation, JPY-quoted / USD-quoted / BTC, several
    conversion rates; a full trade (legs, ledger, 1R) through the broker emulator
  * differential: every lab_sim scenario run (the gold scenarios, recorded) re-run on the symbol logic with the same inputs and the
    unit factor 1 -> identical orders, fills, waits, timings, ledger, drawings; texts identical up to the price format
  * symbol-magnitude scenarios: POC (4H / D) received and replaced, fib (LongFibWave feed) received and replaced, contact -> TC ->
    entry -> TP / SL, the TP change alert, Zone touch alerts, price text with 5 / 3 / 2 decimals, notification ON / OFF identical
  * mutations of the conversion / format / lot edits are caught

Evidence class: PINE_NOT_VERIFIED (translated Pine logic + emulator; TradingView's compiler, request.security, the real mintick /
pointvalue / conversion rates of the broker feed and the alert delivery are not reproduced).
"""
import copy
import math
import os
import re
import subprocess
import sys
import time as _time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import acc_pine as ap        # noqa: E402
import lab_pine as lp        # noqa: E402
import lbs_build as lb       # noqa: E402

ROOT = lp.ROOT
RESULTS = []
M5 = lp.M5
BASE_REV = "84c4a96"         # the branch head before LBS-1
ap.NAMESPACES.add("format")

# typical broker values for the scenarios (TradingView's actual mintick depends on the data feed: not verified here)
MINTICK = {"BTCUSD": 0.01, "GBPJPY": 0.001, "USDJPY": 0.001, "EURUSD": 0.00001, "GBPUSD": 0.00001}
PRICE = {"BTCUSD": 100000.0, "GBPJPY": 200.0, "USDJPY": 150.0, "EURUSD": 1.08, "GBPUSD": 1.27}
JPY_QUOTED = ("GBPJPY", "USDJPY")
MT_TOKEN = "<format.mintick>"
NTF = "ZCL Zoneタッチ"


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


def raw(path):
    return open(os.path.join(ROOT, path), encoding="utf-8").read()


def git(*a):
    return subprocess.run(["git", "-C", ROOT] + list(a), capture_output=True, text=True).stdout


def code_only(src):
    """source without comments (string literals kept; no '//' inside the strings of these files)"""
    return "\n".join(ln.split("//", 1)[0] for ln in src.split("\n"))


def unit_block(src):
    return lp.block(src, lb.UNIT_BEGIN, lb.UNIT_END)


def mt_decimals(mt):
    return max(0, -int(math.floor(math.log10(mt) + 1e-9)))


def fmt_mt(x, mt):
    """str.tostring(x, format.mintick): rounded to the mintick (ties up), with the mintick's decimals (trailing zeros kept)"""
    return f"{math.floor(x / mt + 0.5) * mt:.{mt_decimals(mt)}f}"


class SymRunner(lp.Runner):
    """lab_pine.Runner on a symbol file: LBS Unit block + LOGIC section translated, the symbol's inputs, format.mintick.
    inp = a complete input dict to use instead of the file's defaults (the differential); overrides = changes on top.
    rate = JPY per unit of the symbol currency (convert_to_account / convert_to_symbol); pip = replaces LBS_PIP (differential)."""

    def __init__(self, sym, overrides=None, rate=150.0, pointvalue=1.0, mintick=None, src=None, pip=None, inp=None):
        src = src if src is not None else raw(lb.path(sym))
        if pip is not None:
            old = f"float LBS_PIP = {lb.SPEC[sym]['pipText']} "
            assert src.count(old) == 1
            src = src.replace(old, f"float LBS_PIP = {pip!r} ")
        super().__init__(overrides=None, usdjpy=rate, src=src)
        self.sym = sym
        self.code = compile(ap.Translator().translate(ap.logical_lines(unit_block(src) + lp.logic_section(src))),
                            f"<{lb.path(sym)} unit + logic>", "exec")
        if inp is not None:
            self.inp = dict(inp)
        for k in (overrides or {}):
            if k not in self.inp:
                raise KeyError("unknown input " + k)
        self.inp.update(overrides or {})
        self.env.update(self.inp)
        self.broker.pointvalue = pointvalue
        mt = mintick if mintick is not None else MINTICK[sym]
        tos = self.env["str__tostring"]
        self.env.update(format__mintick=MT_TOKEN, syminfo__mintick=mt, syminfo__ticker=sym,
                        str__tostring=lambda x, f=None: ("NaN" if x is None else fmt_mt(x, mt)) if f == MT_TOKEN else tos(x, f))


def entries(r):
    return [(e[1], e[2], e[3], e[4]) for e in r.broker.log if e[0] == "order_entry"]


# ============================================================================
# static
# ============================================================================
GOLD_DIST_DEFAULTS = dict(zHalf=2.0, zcMerge=5.0, zfMinW=3.0, fvMinW=1.0, stSatsNearD=1.0, slBuf=5.0, maxSl=40.0, beDist=15.0, tpNtf=5.0)
CHANGED_BOOLS = dict(zcUse1=False, zcUse2=False, zcUse3=True, zcUse4=True, zdUse1=False, zdUse2=True, zdUse3=True, zdUse4=True,
                     zeUse=True, zeUse4=True, zeUseD=True, ntfTouch=True)


def static_build(srcs):
    gold_now = raw(lb.GOLD_PATH)
    gold = lb.gold_source()
    bad = [s for s in lb.SYMBOLS if srcs[s] != lb.build(s, gold)]
    check("LBS-01 each of the 5 files == tests/lbs_build.py build(): the gold version at LAB-5 (3be168d) with exactly the listed edits "
          "(each old text found exactly the stated number of times); the gold file in the tree is still that version",
          not bad and gold_now == gold and gold, str(bad))
    # the five logic sections are identical to each other and differ from the gold logic only by the lot name and the price format
    lg = lp.logic_section(gold)
    exp = lg.replace("mmLotOz", "mmLotSize")
    for old, new, _ in lb.edits("EURUSD"):
        if old.startswith('str.tostring') or old.startswith('" / SL') or old.startswith('xid +') or old.startswith('"\\n判断'):
            exp = exp.replace(old, new)
    ls = {s: lp.logic_section(srcs[s]) for s in lb.SYMBOLS}
    n_fmt = {s: ls[s].count("format.mintick") for s in lb.SYMBOLS}
    check("LBS-02 the LOGIC sections of the 5 files are identical and equal the gold LOGIC section with only mmLotOz -> mmLotSize and "
          "the 7 price texts -> format.mintick (the lot / RR / % / yen formats unchanged)",
          all(ls[s] == exp for s in lb.SYMBOLS) and all(n == 7 for n in n_fmt.values())
          and all(ls[s].count('"#.##"') == lg.count('"#.##"') - 7 for s in lb.SYMBOLS), str(n_fmt))


def static_unchanged():
    keep = ["ZoneComboLabXAU.pine", "MtfPocFeedXAU.pine", "LongFibWave.pine", "MtfPocDetector.pine", "AccumStrategyXAU.pine",
            "ZONE_COMBO_LAB_XAU_ja.md"] + sorted(p for p in os.listdir(ROOT) if re.match(r"Zone(Strategy|EnginePractical|Visual)\w*\.pine$", p))
    bad = [p for p in keep if git("show", f"{BASE_REV}:{p}") != raw(p)]
    staged = git("diff", "--name-only", "HEAD", "--", *keep).split()
    check(f"LBS-03 the gold version, the normal versions and the external indicators are byte-identical to {BASE_REV} "
          f"({len(keep)} files: ZoneComboLabXAU, MtfPocFeedXAU, LongFibWave, MtfPocDetector, AccumStrategyXAU, ZoneStrategy* / "
          "ZoneEnginePractical* / ZoneVisual*, the gold doc)", not bad and not staged and len(keep) > 20, f"{bad} {staged}")


def defaults_bad(src, s, gi):
    si = ap.inputs(src)
    sp = lb.SPEC[s]
    bad = []
    exp = {}
    for n, v in zip(lb.DIST, sp["vals"]):
        exp[n + "In"] = float(v)
    exp.update(CHANGED_BOOLS)
    exp.update(mmLotSize=sp["lot"], mmLotMin=0.01, mmLotStep=0.01, mmCapBase=300000.0, mmRiskPct=3.0, maxSlOn=False, cZE=False,
               seUse=True, seTz="Asia/Tokyo", seStartH=9, seStartM=0, seEndH=2, seEndM=0)
    for k, v in exp.items():
        if si.get(k) != v:
            bad.append((s, k, si.get(k), v))
    # every other input = the gold default (same names)
    others = {k: v for k, v in gi.items() if k not in GOLD_DIST_DEFAULTS and k != "mmLotOz" and k not in CHANGED_BOOLS}
    for k, v in others.items():
        if si.get(k) != v:
            bad.append((s, k, si.get(k), v, "gold"))
    if set(si) != set(others) | set(exp):
        bad.append((s, "input names", sorted(set(si) ^ (set(others) | set(exp)))))
    if 'strategy(\n     title                   = "Zone Combo Lab ' + s + '",\n     shorttitle              = "ZCL-' + s + '",' not in src:
        bad.append((s, "title"))
    for k, txt in (("calc_on_every_tick", "calc_on_every_tick      = false"), ("capital", "initial_capital         = 300000"),
                   ("currency", "currency                = currency.JPY")):
        if txt not in src:
            bad.append((s, k))
    u = sp["unit"]
    names = re.findall(r'^(\w+In) *= input\.float\([^,]+, "([^"]+)"', src, re.M)
    if len(names) != 9 or not all(f"{u})" in t or f"{u}、" in t for _, t in names) or any("$" in t for _, t in names if u != "$"):
        bad.append((s, "distance names", names))
    if f'"{sp["lotName"]}"' not in src or "オンス" in code_only(src):
        bad.append((s, "lot name"))
    bt = "暫定の初期値 (XS の実口座の仕様は未確認)"
    if (bt in src) != (s == "BTCUSD") or "確認済" in src:
        bad.append((s, "BTC lot note"))
    lg = lp.logic_section(src)
    if lg.count("format.mintick") != 7:
        bad.append((s, "price format", lg.count("format.mintick")))
    return bad


def static_defaults(srcs):
    gi = ap.inputs(lb.gold_source())
    bad = [b for s in lb.SYMBOLS for b in defaults_bad(srcs[s], s, gi)]
    check("LBS-04 defaults of the 5 files: the 9 distances of the table (pips / BTC dollars), swing 1H / 4H OFF + D / W ON, POC 1H OFF + "
          "4H / D / W ON, fib detection ON with 4H / D adopted, touch alert ON, entry condition ZE OFF (gold), max SL OFF (gold), 1 lot = "
          "100,000 units / 1 BTC, min lot / step 0.01 (BTC: marked provisional, not 'verified'), 300,000 yen x 3 %, JST 09:00-02:00; every "
          "other input = the gold default; names / units / titles; 7 price texts in format.mintick", not bad, str(bad[:8]))


def static_once(src, sym):
    """one conversion: the converted names are assigned once (unit block), never reassigned, the In inputs are read only there,
    LBS_PIP only in the unit block, the unit block is before the first request.security (the FVG min width passed to the detection
    function is the converted one)"""
    c = code_only(src)
    ub = code_only(unit_block(src))
    lg = code_only(lp.logic_section(src))
    bad = []
    for n in lb.DIST:
        if len(re.findall(rf"^float {n}\s*=\s*{n}In\s*\*\s*LBS_PIP\s*$", ub, re.M)) != 1:
            bad.append((n, "unit"))
        if len(re.findall(rf"(?<![\w.]){n}\s*:?=", c)) != 1:
            bad.append((n, "assigned"))
        if len(re.findall(rf"(?<![\w.]){n}In(?!\w)", c)) != 2:
            bad.append((n, "In used"))
        if re.search(rf"(?<![\w.]){n}(?!\w)\s*\*\s*LBS_PIP|LBS_PIP\s*\*\s*{n}(?!\w)", c):
            bad.append((n, "double"))
    if len(re.findall(r"LBS_PIP", c)) != 10 or "LBS_PIP" in lg or len(re.findall(r"LBS_PIP", ub)) != 10:
        bad.append("LBS_PIP outside the unit block")
    if len(re.findall(r"\w+In\b", lg)):
        bad.append("an In input in the logic")
    if c.index("float zfMinW") > c.index("request.security(") or c.count("f_fvgConfirmed(zfMinW)") != 4:
        bad.append("FVG feed")
    pip_lit = re.findall(r"^float LBS_PIP = ([\d.]+) ", src, re.M)
    if pip_lit != [lb.SPEC[sym]["pipText"]]:
        bad.append(("pip", pip_lit))
    return bad


def static_conversion(srcs):
    bad = {s: static_once(srcs[s], s) for s in lb.SYMBOLS}
    bad = {s: b for s, b in bad.items() if b}
    check("LBS-05 one conversion per distance: each of the 9 converted names is assigned exactly once (LBS Unit block: name = nameIn * "
          "LBS_PIP), never reassigned; each nameIn is read only there; LBS_PIP appears only in the unit block (no factor on ATR multipliers, "
          "ratios, bar counts, money, lots); the block is before the feeds and the 4 FVG detection calls get the converted zfMinW; fixed pip "
          "GBPJPY / USDJPY 0.01, EURUSD / GBPUSD 0.0001, BTCUSD 1.0", not bad, str(bad))
    # the translated block itself
    got, bad2 = {}, []
    for s in lb.SYMBOLS:
        r = SymRunner(s, overrides=dict(zbUse1=False, zbUse2=False))
        r.step(dict(t=lp_T0(), o=PRICE[s], h=PRICE[s], l=PRICE[s], c=PRICE[s]))
        for n, v in zip(lb.DIST, lb.SPEC[s]["vals"]):
            e = v * lb.SPEC[s]["pip"]
            if abs(r[n] - e) > 1e-12 * max(1.0, abs(e)):
                bad2.append((s, n, r[n], e))
        got[s] = (r["zHalf"], r["slBuf"])
    check("LBS-06 the LBS Unit block (translated Pine) gives the price differences: EURUSD half width 2 pips = 0.0002, USDJPY 3 pips = 0.03, "
          "GBPJPY 4 pips = 0.04, GBPUSD 3 pips = 0.0003, BTCUSD 100 dollars = 100 (all 9 items x 5 symbols = input x pip)",
          not bad2 and abs(got["EURUSD"][0] - 0.0002) < 1e-15 and abs(got["USDJPY"][0] - 0.03) < 1e-15 and abs(got["GBPJPY"][0] - 0.04) < 1e-15
          and abs(got["GBPUSD"][0] - 0.0003) < 1e-15 and got["BTCUSD"][0] == 100.0, f"{bad2} {got}")


def registration():
    bad = []
    for p, eds in lb.TEST_EDITS.items():
        cur = raw(p)
        if not all(cur.count(new) == c for _, new, c in eds):
            bad.append((p, "edit"))
        if lb.unadapt(p, cur) != git("show", f"{BASE_REV}:{p}"):
            bad.append((p, "unadapt"))
    acc = __import__("acc_build")
    cad = __import__("cad_adapt")
    missing = [f for f in lb.NEW_FILES if not os.path.exists(os.path.join(ROOT, f))]
    check("LBS-07 registration in the older fixtures (a layer above LAB-2): the tests/lab2_build.py and tests/cad_adapt.py edits are present "
          f"exactly and lbs_build.unadapt() gives the {BASE_REV} text byte for byte; acc_build.ok() (through lab / fds / lfw / lab2) accepts "
          "exactly the 8 LBS-1 files (not a normal Strategy, not a stray copy); cad_adapt.LATER_NEW lists them",
          not bad and not missing and all(acc.ok(f) and f in cad.LATER_NEW for f in lb.NEW_FILES) and len(lb.NEW_FILES) == 8
          and not acc.ok("ZoneStrategyEURUSD.pine") and not acc.ok("ZoneComboLabEURUSD.pine.bak") and not acc.ok("ZoneComboLabAUDUSD.pine"),
          f"{bad} {missing}")


def lp_T0():
    from datetime import datetime, timezone
    return int(datetime(2026, 1, 5, 1, 0, tzinfo=timezone.utc).timestamp() * 1000)


T0 = lp_T0()
T_HTF = T0 - 86_400_000


# ============================================================================
# lots / qty
# ============================================================================
def ref_lots(budget_jpy, rate, dist, lot, step=0.01, lmin=0.01):
    """independent (counting, no floor formula): the largest N with N x step x lot x dist <= budget / rate in floating point (dist =
    the price difference as the script computes it, ref - SL), N x step >= min lot. Exactly on the budget a float error in dist can
    give one step less (the original formula behaves the same: n x step x size x dist > budget -> n - 1)"""
    bud = budget_jpy / rate
    n = 0
    while (n + 1) * step * lot * dist <= bud:
        n += 1
        if n > 10_000_000:
            break
    return n if n * step >= lmin - 1e-12 else 0


def sc_qty():
    cases = {
        "USDJPY": [(1.0, 0.20), (1.0, 0.13), (1.0, 0.6)],                 # JPY-quoted: conversion JPY -> JPY = 1
        "GBPJPY": [(1.0, 0.26), (1.0, 0.80), (1.0, 0.111)],
        "EURUSD": [(150.0, 0.0020), (140.0, 0.0020), (155.0, 0.0013), (150.0, 0.0040)],
        "GBPUSD": [(150.0, 0.0030), (140.0, 0.0030), (150.0, 0.0007)],
        "BTCUSD": [(150.0, 500.0), (160.0, 500.0), (150.0, 2000.0), (150.0, 7000.0)],
    }
    bad, shown = [], {}
    for s, cs in cases.items():
        lot = lb.SPEC[s]["lot"]
        for rate, dist in cs:
            r = SymRunner(s, rate=rate, overrides=dict(zbUse1=False, zbUse2=False))
            r.step(dict(t=T0, o=PRICE[s], h=PRICE[s], l=PRICE[s], c=PRICE[s]))
            ref = PRICE[s]
            for side in (1, -1):
                sl = ref - side * dist
                n = ref_lots(9000.0, rate, abs(ref - sl), lot)
                q = r["f_qty"](side, ref, sl)
                eq = None if n == 0 else n * 0.01 * lot
                if (q is None) != (eq is None) or (q is not None and abs(q - eq) > 1e-9 * max(1.0, eq)):
                    bad.append((s, rate, dist, side, q, eq))
                if q is not None:
                    loss = q * dist * rate
                    if loss > 9000.0 + 1e-6 or (q / (0.01 * lot) + 1) * 0.01 * lot * dist * rate <= 9000.0 - 1e-6:
                        bad.append((s, "budget", loss))
            shown[(s, rate, dist)] = (n, None if n == 0 else round(n * 0.01, 2), None if n == 0 else round(n * 0.01 * lot, 6))
    # rate changes the lot for USD-quoted / BTC
    ch = shown[("EURUSD", 150.0, 0.0020)][0] != shown[("EURUSD", 140.0, 0.0020)][0] and shown[("BTCUSD", 150.0, 500.0)][0] != shown[("BTCUSD", 160.0, 500.0)][0]
    # pointvalue != 1: qty divided by pointvalue (same lot)
    r = SymRunner("EURUSD", rate=150.0, pointvalue=10.0, overrides=dict(zbUse1=False, zbUse2=False))
    r.step(dict(t=T0, o=1.08, h=1.08, l=1.08, c=1.08))
    qpv = r["f_qty"](1, 1.08, 1.078)
    npv = ref_lots(9000.0, 150.0, 1.08 - 1.078, 100000.0)
    check("LBS-10 f_qty of each file (translated Pine) == an independent loss-budget calculation: 9,000 yen -> symbol currency (x 1 for "
          "USDJPY / GBPJPY, / rate for EURUSD / GBPUSD / BTCUSD) -> floor to 0.01 lot of 100,000 units / 1 BTC -> qty = lots x units; the "
          "loss at the SL never exceeds 9,000 yen and one more step would; a different rate changes the lot (USD-quoted / BTC); "
          "pointvalue 10 divides the qty (same lot). Examples (N steps, lot, qty): "
          + ", ".join(f"{s} {rt:g} {d:g}: {v}" for (s, rt, d), v in list(shown.items())[:9]),
          not bad and ch and qpv is not None and abs(qpv - npv * 0.01 * 100000 / 10.0) < 1e-9, f"{bad} {qpv} {npv}")


# ============================================================================
# symbol-magnitude scenarios
# ============================================================================
class Sc:
    def __init__(self, rows, t0=T0):
        self.bars = [dict(t=t0 + i * M5, o=float(o), h=float(h), l=float(l), c=float(c)) for i, (o, h, l, c) in enumerate(rows)]

    def hold(self, i0, i1=None, **kv):
        for i in range(i0, len(self.bars) if i1 is None else i1):
            self.bars[i].update(kv)
        return self


def pocv(k, lo, up, t=T_HTF):
    return {f"zdL{k}": lo, f"zdU{k}": up, f"zdT{k}": t}


def fib_none(sc):
    """LongFibWave connected, no wave yet on 4H / D (state 1 = no wave): a normal state, orders not stopped"""
    for k in ("4", "D"):
        sc.hold(0, None, **{f"ze{k}S": 1.0, f"ze{k}I": 0.0, f"ze{k}D": 0.0, f"ze{k}O": None, f"ze{k}E": None, f"ze{k}T": float(T_HTF)})
    return sc


def setup_a(s, after, d_poc=True):
    """SHORT from the 4H POC (centre C = symbol price): quiet bars below, wick into the band on bar 3 (close outside), TC SHORT on
    bar 4 (line C - 2.5h), entry at bar 5 open. TP1 = top of the daily POC (centre C - 12h). h = the half width (price)."""
    P = PRICE[s]
    h = lb.SPEC[s]["vals"][0] * lb.SPEC[s]["pip"]
    C = P

    def q(b):
        return (b, b + 0.3 * h, b - 0.3 * h, b + 0.05 * h)
    rows = [q(C - 3 * h)] * 3 + [(C - 3 * h, C - 0.5 * h, C - 3.2 * h, C - 2.8 * h),
                                 (C - 2.7 * h, C - 2.3 * h, C - 3.3 * h, C - 3.1 * h)] + after(C, h)
    sc = Sc(rows)
    fib_none(sc)
    sc.hold(1, None, **pocv(2, C - 0.4 * h, C + 0.4 * h))
    if d_poc:
        sc.hold(1, None, **pocv(3, C - 12 * h - 0.4 * h, C - 12 * h + 0.4 * h))
    sc.bars[4]["labS1"] = C - 2.5 * h
    return sc, C, h


def down_after(C, h, to=-12.5):
    rows = [(C - 3.1 * h, C - 3.0 * h, C - 4.0 * h, C - 3.9 * h)]
    b = C - 3.9 * h
    while b > C + to * h:
        rows.append((b, b + 0.1 * h, b - 1.0 * h, b - 0.9 * h))
        b -= 0.9 * h
    return rows + [(b, b + 0.2 * h, b - 0.2 * h, b)] * 2


def up_after(C, h, sb):
    rows = [(C - 3.1 * h, C - 3.0 * h, C - 3.3 * h, C - 3.15 * h)]
    b = C - 3.15 * h
    top = C + h + sb + h
    while b < top:
        rows.append((b, b + 1.0 * h, b - 0.1 * h, b + 0.9 * h))
        b += 0.9 * h
    return rows + [(b, b + 0.2 * h, b - 0.2 * h, b)] * 2


ONLY_TC = dict(cTA=False, cTC=True)


def rate_of(s, alt=False):
    return 1.0 if s in JPY_QUOTED else (140.0 if alt else 150.0)


def sc_trade():
    bad, ex = [], {}
    for s in lb.SYMBOLS:
        sp = lb.SPEC[s]
        pip, mt, rate = sp["pip"], MINTICK[s], rate_of(s)
        sb = sp["vals"][5] * pip
        sc, C, h = setup_a(s, down_after)
        r = SymRunner(s, rate=rate, overrides=dict(ONLY_TC)).run(sc.bars)
        en = entries(r)
        ref = C - 3.1 * h
        sl = C + h + sb                    # the POC band = centre +- h (the POC centre = (L + U) / 2 = C)
        tp1 = C - 12 * h + h
        n = ref_lots(9000.0, rate, sl - ref, sp["lot"])
        fills = [e for e in r.broker.log if e[0] in ("fill_entry", "fill_exit")]
        ex_ord = [e for e in r.broker.log if e[0] == "order_exit"]
        closed = r.broker.closed
        pnl = sum(c["profit"] for c in closed)
        al = [m for _, m in r.alerts]
        ent_al = [m for m in al if m.startswith("ZCL 確定")]
        tp_al = [m for m in al if m.startswith("ZCL TP 到達")]
        tch = [(b, m) for b, m in r.alerts if m.startswith(NTF)]
        lots_txt = f"{n * 0.01:.2f}".rstrip("0").rstrip(".")
        ok = (len(en) == 1 and en[0][0] == 4 and en[0][2] == -1 and abs(en[0][3] - n * 0.01 * sp["lot"]) < 1e-9 * sp["lot"]
              and ex_ord and abs(ex_ord[0][5] - sl) < 1e-9 * C and abs(ex_ord[0][6] - tp1) < 1e-9 * C
              and len(closed) == 1 and abs(closed[0]["exit_price"] - tp1) < 1e-9 * C and abs(closed[0]["price"] - ref) < 1e-9 * C
              and abs(pnl - (ref - tp1) * n * 0.01 * sp["lot"] * rate) < 1e-6 and r["bkN"][0] == 1 and r["bkW"][0] == 1
              and abs(r["bkNet"][0] - pnl) < 1e-6
              and ent_al and f"判断 {fmt_mt(ref, mt)}  SL {fmt_mt(sl, mt)}" in ent_al[0] and f"TP1 {fmt_mt(tp1, mt)} ({lots_txt} lot)" in ent_al[0]
              and tp_al and f" {fmt_mt(tp1, mt)} ({lots_txt} lot)" in tp_al[0]
              and len(tch) >= 2 and tch[0][0] == 3 and tch[0][1].endswith(f"\n4時間足 出来高POC  {fmt_mt(C - h, mt)}〜{fmt_mt(C + h, mt)}")
              and any(m.endswith(f"\n日足 出来高POC  {fmt_mt(C - 13 * h, mt)}〜{fmt_mt(C - 11 * h, mt)}") for _, m in tch))
        if not ok:
            bad.append((s, en, ex_ord[:1], fills[:3], ent_al[:1], tp_al[:1], tch[:2], n))
        ex[s] = (n, ent_al[0].split("\n")[2] if ent_al else "", tch[0][1].split("\n")[1] if tch else "")
        # SL case: up after the entry -> stop at the SL, loss within the budget, ledger -1R
        sc2, _, _ = setup_a(s, lambda C_, h_: up_after(C_, h_, sb))
        r2 = SymRunner(s, rate=rate, overrides=dict(ONLY_TC)).run(sc2.bars)
        c2 = r2.broker.closed
        p2 = sum(c["profit"] for c in c2)
        rj = (sl - ref) * n * 0.01 * sp["lot"] * rate
        if not (len(c2) == 1 and abs(c2[0]["exit_price"] - sl) < 1e-9 * C and -9000.0 - 1e-6 <= p2 < 0 and abs(p2 + rj) < 1e-6
                and r2["bkL"][0] == 1 and abs(r2["bkR"][0] + 1.0) < 1e-9):
            bad.append((s, "SL", c2, p2, rj, r2["bkR"][0]))
    check("LBS-30 each symbol at its price (BTC 100,000 / GBPJPY 200 / USDJPY 150 / EURUSD 1.08 / GBPUSD 1.27), defaults, TC only: 4H POC "
          "received -> a wick into its band (close outside) -> TC SHORT -> entry on the decision bar, lots from the 9,000-yen budget, SL = "
          "band top + SL margin, TP1 = top of the daily POC band (100 % at one target), filled at TP1, ledger 1 win = broker profit; the entry "
          "alert / TP alert / touch alerts show the prices with the mintick decimals; the same entry going up instead stops at the SL with "
          "a loss within 9,000 yen = -1R. Entry lines: " + "; ".join(f"{s} N={v[0]} '{v[1].strip()}' / '{v[2]}'" for s, v in ex.items()),
          not bad, str(bad[:2]))


def sc_partial():
    """3 targets below (daily POC top C - 11h, weekly POC top C - 15h, daily swing low band top C - 19h), price falls through all of them:
    legs = rounded cumulative 60 / 80 % of N, the rest on TP3 (0 legs not ordered); each exit qty = legs x lotQ; the broker's partial
    closes add up to N x lotQ and to one ledger trade; 1R = |fill - SL| x qty x rate. USD-quoted / BTC also with the rate 140."""
    bad, ex = [], {}
    for s in lb.SYMBOLS:
        sp = lb.SPEC[s]
        sb = sp["vals"][5] * sp["pip"]
        for alt in ((False, True) if s not in JPY_QUOTED else (False,)):
            rate = rate_of(s, alt)
            sc, C, h = setup_a(s, lambda C_, h_: down_after(C_, h_, to=-21.0))
            sc.hold(1, None, **pocv(4, C - 16 * h - 0.4 * h, C - 16 * h + 0.4 * h))
            sc.bars[2].update(s3l=C - 20 * h, s3lt=T_HTF)
            r = SymRunner(s, rate=rate, overrides=dict(ONLY_TC)).run(sc.bars)
            ref, sl = C - 3.1 * h, C + h + sb
            n = ref_lots(9000.0, rate, sl - ref, sp["lot"])
            lotQ = 0.01 * sp["lot"]
            c1, c2 = math.floor(0.6 * n + 0.5), math.floor(0.8 * n + 0.5)
            legs = [c1, c2 - c1, n - c2]
            tps = [C - 11 * h, C - 15 * h, C - 19 * h]
            closed = r.broker.closed
            want = [(round(L * lotQ, 9), tp) for L, tp in zip(legs, tps) if L > 0]
            got = [(round(c["qty"], 9), c["exit_price"]) for c in closed]
            pnl = sum(c["profit"] for c in closed)
            fill = closed[0]["price"] if closed else None
            r1 = abs(fill - sl) * n * lotQ * rate if closed else None
            e_q = [e[4] for e in r.broker.log if e[0] == "order_exit"]
            ok = (len(entries(r)) == 1 and abs(entries(r)[0][3] - n * lotQ) < 1e-9 * max(1.0, n * lotQ)
                  and len(got) == len(want) and all(a[0] == b[0] and abs(a[1] - b[1]) < 1e-9 * C for a, b in zip(got, want))
                  and abs(sum(c["qty"] for c in closed) - n * lotQ) < 1e-9 * max(1.0, n * lotQ)
                  and r["bkN"][0] == 1 and abs(r["bkNet"][0] - pnl) < 1e-6 and abs(r["bkR"][0] - pnl / r1) < 1e-9
                  and all(abs(q / lotQ - round(q / lotQ)) < 1e-9 for q in e_q if q is not None))
            if not ok:
                bad.append((s, rate, n, legs, got, want, list(r["bkN"])[:1]))
            ex[(s, rate)] = (n, legs, round(pnl), round(r1))
    check("LBS-11 partial exits at each symbol's price (3 targets): legs = rounded cumulative 60 / 80 % of the N lot steps, the rest on "
          "TP3 (legs of 0 not ordered), every exit order an integer number of lot steps, the partial closes sum to N x lotQ and make one "
          "ledger trade, ledger net = broker profit, R = profit / (|fill - SL| x qty x rate); USD-quoted pairs and BTC with rate 150 and 140 "
          "(N steps, legs, profit yen, 1R yen): " + ", ".join(f"{s} {rt:g}: {v}" for (s, rt), v in ex.items()), not bad, str(bad[:2]))


def sc_replace():
    """while SHORT: the daily POC is replaced (centre moves down by tpNtf + h) -> one POC per TF, TP1 re-planned, TP change alert with
    mintick prices; the 4H fib wave received -> 4 Zones at E + r (O - E) +- h, replaced on a new wave; a touch alert names the level"""
    bad, ex = [], {}
    for s in lb.SYMBOLS:
        sp = lb.SPEC[s]
        pip, mt, rate = sp["pip"], MINTICK[s], rate_of(s)
        tpn = sp["vals"][8] * pip
        sb = sp["vals"][5] * pip

        def after(C, h):
            return [(C - 3.1 * h, C - 3.0 * h, C - 3.3 * h, C - 3.2 * h)] * 6
        sc, C, h = setup_a(s, after)
        newc = C - 12 * h - tpn - h
        sc.hold(7, None, **pocv(3, newc - 0.4 * h, newc + 0.4 * h))
        r = SymRunner(s, rate=rate, overrides=dict(ONLY_TC)).run(sc.bars)
        al = [m for _, m in r.alerts if m.startswith("ZCL TP 変更")]
        pocs = [z for z in r["lbZs"] if z.typ == 3 and z.tf == 2]
        ex_ord = [e for e in r.broker.log if e[0] == "order_exit"]
        sl = C + h + sb
        if not (len(entries(r)) == 1 and len(pocs) == 1 and abs(pocs[0].ctr - newc) < 1e-9 * C and abs(ex_ord[-1][6] - (newc + h)) < 1e-9 * C
                and len(al) == 1 and f"TP1 {fmt_mt(newc + h, mt)}" in al[0] and al[0].endswith(f"/ SL {fmt_mt(sl, mt)}")):
            bad.append((s, "poc", len(pocs), ex_ord[-1:], al))
        ex[s] = al[0] if al else ""
        # fib: 4H wave from bar 2 (down wave O = C + 40h, E = C - 40h), new wave from bar 6 (E = C - 30h); a bar touching the 0.5 level
        P = PRICE[s]
        h = sp["vals"][0] * pip
        rows = [(P - 50 * h, P - 49.5 * h, P - 50.5 * h, P - 49.9 * h)] * 10
        rows[8] = (P - 49.9 * h, P - 49.9 * h + 0.1 * h, P - 51 * h, P - 50 * h)
        sc3 = Sc(rows)
        fib_none(sc3)
        O, E1, E2 = P + 40 * h, P - 40 * h, P - 30 * h
        sc3.hold(2, 6, ze4O=O, ze4E=E1, ze4D=-1.0, ze4I=1.0, ze4S=3.0, ze4T=float(sc3.bars[2]["t"] + M5))
        sc3.hold(6, None, ze4O=O, ze4E=E2, ze4D=-1.0, ze4I=2.0, ze4S=3.0, ze4T=float(sc3.bars[6]["t"] + M5))
        # the 0.5 level of wave 2 is (O + E2) / 2 = P + 5h; bar 9 wicks into it from below
        sc3.bars[9].update(o=P + 2 * h, h=P + 4.5 * h, l=P + 1.5 * h, c=P + 2 * h)
        r3 = SymRunner(s, rate=rate, overrides=dict(ONLY_TC)).run(sc3.bars[:6])
        z1 = sorted((z.infoA, z.ctr) for z in r3["lbZs"] if z.typ == 5 and z.tf == 0)
        r4 = SymRunner(s, rate=rate, overrides=dict(ONLY_TC)).run(sc3.bars)
        z2 = sorted((z.infoA, z.ctr) for z in r4["lbZs"] if z.typ == 5 and z.tf == 0)
        rs = (0.236, 0.382, 0.5, 0.618)
        e1 = [(x, E1 + x * (O - E1)) for x in rs]
        e2 = [(x, E2 + x * (O - E2)) for x in rs]
        t4 = [m for b, m in r4.alerts if m.startswith(NTF) and b == 9]
        lvl = E2 + 0.5 * (O - E2)
        if not (len(z1) == 4 and all(a == b and abs(c - d) < 1e-9 * P for (a, c), (b, d) in zip(z1, e1))
                and len(z2) == 4 and all(a == b and abs(c - d) < 1e-9 * P for (a, c), (b, d) in zip(z2, e2))
                and r4["lbZeStat"][0] == 1 and r4["lbZeStat"][1] == 2
                and t4 and t4[0].endswith(f"\n4時間足 フィボ 0.5  {fmt_mt(lvl - h, mt)}〜{fmt_mt(lvl + h, mt)}")):
            bad.append((s, "fib", z1, z2, t4, list(r4["lbZeStat"])))
    check("LBS-31 each symbol: the daily POC replaced while SHORT -> still one daily POC (the new centre), TP1 moved to the new band top, "
          "one TP change alert with mintick prices and the unchanged SL; the 4H LongFibWave wave received -> 4 Zones at E + r (O - E) for "
          "0.236 / 0.382 / 0.5 / 0.618, a new wave replaces them, state 'valid' (4H) / 'no wave' (D: normal, orders not stopped); a wick into "
          "the 0.5 band gives a touch alert '4時間足 フィボ 0.5  lo〜hi'. TP alerts: " + " | ".join(f"{s}: {v}" for s, v in ex.items()),
          not bad, str(bad[:2]))


def sc_poc_recv_bar():
    """the POC is judged from the bar it is received on (LAB-3h): a weekly POC received on a bar whose high reaches its band -> wait on
    that bar; the same on a bar 1/4 band short -> no wait; a swing line (D) registered on the bar is judged from the next bar"""
    bad = []
    for s in lb.SYMBOLS:
        P = PRICE[s]
        h = lb.SPEC[s]["vals"][0] * lb.SPEC[s]["pip"]
        res = []
        for reach in (True, False):
            rows = [(P - 5 * h, P - 4.7 * h, P - 5.3 * h, P - 4.95 * h)] * 6
            rows[3] = (P - 4.9 * h, (P - h) if reach else (P - 1.25 * h), P - 5 * h, P - 4.8 * h)
            sc = fib_none(Sc(rows))
            sc.hold(3, None, **pocv(4, P - 0.4 * h, P + 0.4 * h))
            sc.hold(3, None, s3h=P + 0.0, s3ht=T_HTF)
            r = SymRunner(s, rate=rate_of(s), overrides=dict(ONLY_TC)).run(sc.bars)
            res.append([(w[1], w[3]) for w in r.trace[3]["waits"]])
        if not (res[0] == [(-1, 3)] and res[1] == []):
            bad.append((s, res))
    check("LBS-32 each symbol: a weekly POC received on a bar whose high reaches its band (P - h) gives a SHORT wait on that bar; 1/4 of the "
          "band short gives none; the daily swing line received on the same bar (same band, merged display) does not add a second wait on "
          "that bar (other types from the next bar)", not bad, str(bad[:3]))


def fx_random(s, seed=6, n=400):
    """lab_sim rand_bars mapped to the symbol price (1 gold dollar -> 1 pip / 50 BTC dollars): p -> P + (p - 2000) x scale"""
    import lab_sim as ls
    sc = ls.rand_bars(seed, n=n)
    P, pip = PRICE[s], lb.SPEC[s]["pip"] * (50.0 if s == "BTCUSD" else 1.0)     # BTC defaults = gold x 50
    keys = ("o", "h", "l", "c", "zdL1", "zdU1", "g1c", "g1t", "g1b", "s1h", "labS1", "zbMa1")
    out = []
    for b in sc.bars:
        nb = {k: v for k, v in b.items() if k in lp.FEED_DEFAULT or k in ("t", "o", "h", "l", "c")}
        for k in keys:
            if nb.get(k) is not None:
                nb[k] = P + (nb[k] - 2000.0) * pip
        out.append(nb)
    w = Sc([])
    w.bars = out
    fib_none(w)
    return w.bars


def sc_ntf_onoff():
    bad, stat = [], {}
    for s in lb.SYMBOLS:
        bars = fx_random(s)
        ov = dict(zcUse1=True, zdUse1=True, zbUse2=False, dsZone=True)
        a = SymRunner(s, rate=rate_of(s), overrides=dict(ov, ntfTouch=True)).run(bars)
        b = SymRunner(s, rate=rate_of(s), overrides=dict(ov, ntfTouch=False)).run(bars)
        other = lambda r: [x for x in r.alerts if not x[1].startswith(NTF)]
        na_ = len([1 for _, m in a.alerts if m.startswith(NTF)])
        ok = (a.broker.log == b.broker.log and a.trace == b.trace and a.broker.closed == b.broker.closed
              and list(a["bkNet"]) == list(b["bkNet"]) and other(a) == other(b) and na_ > 5
              and not [1 for _, m in b.alerts if m.startswith(NTF)] and len(entries(a)) > 0)
        stat[s] = (len(entries(a)), na_)
        if not ok:
            bad.append((s, stat[s]))
        # the default (ON) and an explicit ON are the same run
        if s == "EURUSD":
            d = SymRunner(s, rate=rate_of(s), overrides=dict(ov)).run(bars)
            if d.alerts != a.alerts or d.broker.log != a.broker.log:
                bad.append((s, "default"))
    check("LBS-33 each symbol, 400 random bars at its price (POC / FVG / swing / SATS / MA feeds mapped, LongFibWave connected): the touch "
          "alert ON / OFF gives identical orders, fills, closed trades, waits, timings, legs, ledger and other alerts; ON produced touch "
          "alerts (entries, touch alerts: " + ", ".join(f"{s} {v}" for s, v in stat.items()) + ")", not bad, str(bad))


def sc_formats():
    """price text vs '#.##': at 5 / 3 decimals the band edges, SL and TP are distinguishable; lots / RR / yen keep their formats"""
    bad = []
    for s, mt, lo, hi in (("EURUSD", 0.00001, 1.07983, 1.08017), ("GBPUSD", 0.00001, 1.26970, 1.27030), ("USDJPY", 0.001, 149.97, 150.03),
                          ("GBPJPY", 0.001, 199.96, 200.04), ("BTCUSD", 0.01, 99900.0, 100100.0)):
        old = ap.make_env(ap.Broker(), [])["str__tostring"]
        a, b = fmt_mt(lo, mt), fmt_mt(hi, mt)
        o1, o2 = old(lo, "#.##"), old(hi, "#.##")
        dec = mt_decimals(mt)
        if not (a != b and len(a.split(".")[1]) == dec and float(a) == round(lo, dec)):
            bad.append((s, a, b))
        if s != "BTCUSD" and s not in JPY_QUOTED and o1 != o2:
            bad.append((s, "old format distinguishes?", o1, o2))
    check("LBS-34 format.mintick: EURUSD / GBPUSD 1.07983 / 1.08017 -> '1.07983' / '1.08017' (5 decimals; '#.##' gave '1.08' for both), "
          "USDJPY / GBPJPY 3 decimals, BTCUSD 2 decimals", not bad, str(bad))


# ============================================================================
# differential: the lab_sim scenarios (gold) re-run on the symbol logic with the same inputs
# ============================================================================
NUM = re.compile(r"-?\d+(?:\.\d+)?")


def same_text(a, b, tol=0.0100001):
    if a == b:
        return True
    if not isinstance(a, str) or not isinstance(b, str):
        return False
    pa, pb = NUM.split(a), NUM.split(b)
    na_, nb_ = NUM.findall(a), NUM.findall(b)
    return pa == pb and len(na_) == len(nb_) and all(abs(float(x) - float(y)) <= tol for x, y in zip(na_, nb_))


def same_draw(d1, d2):
    if d1.kind != d2.kind or d1.deleted != d2.deleted or len(d1.args) != len(d2.args) or set(d1.kw) != set(d2.kw):
        return False
    if not all(same_text(x, y) if isinstance(x, str) else x == y for x, y in zip(d1.args, d2.args)):
        return False
    if not all(same_text(d1.kw[k], d2.kw[k]) if isinstance(d1.kw[k], str) else d1.kw[k] == d2.kw[k] for k in d1.kw):
        return False
    a1 = {k: v for k, v in vars(d1).items() if k not in ("kind", "args", "kw", "deleted")}
    a2 = {k: v for k, v in vars(d2).items() if k not in ("kind", "args", "kw", "deleted")}
    return set(a1) == set(a2) and all(same_text(a1[k], a2[k]) if isinstance(a1[k], str) else a1[k] == a2[k] for k in a1)


def map_inputs(gi):
    si = {}
    for k, v in gi.items():
        if k in GOLD_DIST_DEFAULTS:
            si[k + "In"] = v
        elif k == "mmLotOz":
            si["mmLotSize"] = v
        else:
            si[k] = v
    return si


BK = ("bkN", "bkW", "bkL", "bkBE", "bkGP", "bkGL", "bkR", "bkNet", "skipN")


def differential(syms):
    import lab_sim as ls
    Orig = lp.Runner
    rec = []

    class Rec(Orig):
        def __init__(self, overrides=None, usdjpy=150.0, src=None):
            super().__init__(overrides=overrides, usdjpy=usdjpy, src=src)
            self._rec = src is None and lp.SRC_OVERRIDE is None
            self._bars = []
            if self._rec:
                rec.append(self)

        def step(self, bar):
            self._bars.append(dict(bar))
            super().step(bar)
            # some scenarios call the script's functions directly after the bars (sc_display): compare what the bars produced
            self._nd, self._na = len(self.draws), len(self.alerts)
            self._end = {k: list(self.env[k]) for k in BK}
            self._end["st"] = dict(vars(self.env["st"]))
            return self

    scen = [ls.sc_basic, ls.sc_windows, ls.sc_carry, ls.sc_conflict, ls.sc_roles, ls.sc_combo, ls.sc_fvg, ls.sc_partial, ls.sc_tp_mixed,
            ls.sc_qty_table, ls.sc_be, ls.sc_lock_far, ls.sc_and_only_sel, ls.sc_sel_tp, ls.sc_consume, ls.sc_zones, ls.sc_acc_keep,
            ls.sc_dup_swing, ls.sc_ta, ls.sc_session, ls.sc_and_timing, ls.sc_ledger, ls.sc_zd_recv, ls.sc_tp_ref, ls.sc_display,
            ls.sc_fvg_display, ls.sc_swing_merge, ls.sc_names_labels, ls.sc_poc_latest, ls.sc_ze, ls.sc_touch_ntf, ls.sc_random]
    lp.Runner = Rec
    try:
        for f in scen:
            f()
    finally:
        lp.Runner = Orig
    gold_pass = sum(1 for _, ok, _ in ls.RESULTS if ok)
    gold_n = len(ls.RESULTS)
    bad = []
    n_runs = n_bars = n_alerts = n_draws = 0
    for s in syms:
        for g in rec:
            if not g._bars:
                continue
            r = SymRunner(s, rate=g.broker.usdjpy, pointvalue=g.broker.pointvalue, mintick=0.01, pip=1.0, inp=map_inputs(g.inp))
            r.env["syminfo__ticker"] = "XAUUSD"
            for b in g._bars:
                r.step(b)
            n_runs += 1
            n_bars += len(g._bars)
            n_alerts += g._na
            n_draws += g._nd
            same = (r.broker.log == g.broker.log and r.broker.closed == g.broker.closed and r.trace == g.trace
                    and [x[0] for x in r.alerts] == [x[0] for x in g.alerts[:g._na]]
                    and all(same_text(x[1], y[1]) for x, y in zip(r.alerts, g.alerts))
                    and len(r.draws) == g._nd and all(same_draw(x, y) for x, y in zip(r.draws, g.draws))
                    and all(list(r[k]) == g._end[k] for k in BK) and vars(r["st"]) == g._end["st"])
            if not same:
                bad.append((s, len(g._bars), g.inp.get("zHalf")))
    check(f"LBS-20 differential: all {len(rec)} recorded runs of the lab_sim scenarios on the gold file ({len(scen)} scenario groups incl. "
          f"random paths; gold checks {gold_pass}/{gold_n}) re-run on the symbol logic ({', '.join(syms)}) with the same inputs (distances "
          "as nameIn, LBS_PIP = 1, mmLotOz -> mmLotSize) give identical orders, fills, closed trades, waits, timings, legs, ledger, skip counts, "
          f"state and drawings; alert / label texts identical up to the price format ({n_runs} runs, {n_bars} bars, {n_alerts} alerts, "
          f"{n_draws} drawings)", not bad and n_runs > 100, str(bad[:5]))


# ============================================================================
# mutations of the LBS edits
# ============================================================================
def mutation():
    s = "EURUSD"
    src = raw(lb.path(s))
    gi = ap.inputs(lb.gold_source())
    muts = [
        ("float zfMinW      = zfMinWIn      * LBS_PIP", "float zfMinW      = zfMinWIn", "FVG min width not converted"),
        ("float zHalf       = zHalfIn       * LBS_PIP", "float zHalf       = zHalfIn       * LBS_PIP * LBS_PIP", "half width converted twice"),
        ("low - labH2 >= fvMinW - EPS", "low - labH2 >= fvMinW * LBS_PIP - EPS", "5m FVG width converted again in the logic"),
        ("float LBS_PIP = 0.0001 ", "float LBS_PIP = 0.00001 ", "pip = mintick"),
        ('str.tostring(z.bot, format.mintick) + "〜"', 'str.tostring(z.bot, "#.##") + "〜"', "touch alert price format"),
        ('mmLotSize = input.float(100000.0,', 'mmLotSize = input.float(100.0,', "lot size copied from gold"),
        ("float slBuf       = slBufIn       * LBS_PIP", "float slBuf       = slBufIn       * 0.01", "SL margin with another pip"),
    ]
    survived = []
    for old, new, what in muts:
        if src.count(old) != 1:
            survived.append((what, "count", src.count(old)))
            continue
        m = src.replace(old, new)
        killed = bool(static_once(m, s)) or bool(defaults_bad(m, s, gi))
        if not killed:
            survived.append(what)
    # behavioural: the formats / lot mutant also fail the scenario (not only the build comparison)
    m = src.replace('str.tostring(z.bot, format.mintick) + "〜"', 'str.tostring(z.bot, "#.##") + "〜"')
    sc, C, h = setup_a(s, down_after)
    r = SymRunner(s, rate=150.0, overrides=dict(ONLY_TC), src=m).run(sc.bars)
    t = [x for _, x in r.alerts if x.startswith(NTF)]
    beh = t and not t[0].endswith(f"{fmt_mt(C - h, MINTICK[s])}〜{fmt_mt(C + h, MINTICK[s])}")
    check(f"LBS-40 mutation: {len(muts)} changes to the LBS edits (a missing / double / extra conversion, pip = mintick, another pip, the "
          "'#.##' price format, the gold lot size) are each caught by the static checks LBS-04 / LBS-05 (not by the build comparison); the format mutant also changes the touch alert of LBS-30",
          not survived and beh, str(survived))


def main():
    t = _time.time()
    srcs = {s: raw(lb.path(s)) for s in lb.SYMBOLS}
    static_build(srcs)
    static_unchanged()
    static_defaults(srcs)
    static_conversion(srcs)
    registration()
    sc_qty()
    sc_trade()
    sc_partial()
    sc_replace()
    sc_poc_recv_bar()
    sc_ntf_onoff()
    sc_formats()
    mutation()
    differential(["EURUSD", "BTCUSD"] if "--all" not in sys.argv else list(lb.SYMBOLS))
    npass = sum(1 for _, ok, _ in RESULTS if ok)
    for name, ok, detail in RESULTS:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else "  -- " + detail))
    print(f"{npass}/{len(RESULTS)} passed  [PINE_NOT_VERIFIED: static / translated Pine unit + logic + emulator]  {(_time.time() - t):.1f}s")


if __name__ == "__main__":
    main()
