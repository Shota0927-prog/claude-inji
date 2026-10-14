"""BTC-1 fixtures — ZoneVisualBTCUSD.pine (BINANCE:BTCUSD 5M Zone display, no entries / alerts).

  BS : static — deterministic, idempotent build from ZONE-GBPJPY; strip_btc(file) == ZONE-GBPJPY byte for byte; every
       changed code line is a price input (USD), the title, the RN symbol gate / error text or the Zone geometry text;
       USD defaults / minval / step as specified; dimensionless inputs identical; no yen / pips / 3-decimal leftovers;
       Engine import and API consistent with the repository Engine (ZoneEnginePracticalGBPJPY /3); 5M gate, update
       call, requests, loops and drawing identical; RN gate = ticker BTCUSD only (no basecurrency guess, no stop);
       existing files unchanged vs the base HEAD 5957053
  BM : model — Python mirror of the Engine (practical_zone_sim) at BTC prices with the inputs read from the file: Half
       Width / Cluster candidates; the same data and inputs give identical Zones in both files; FVG min width gate;
       RN level search (f_rnLevelIn port) at 1,000 / 500 USD: boundary inclusive, major first, once per Zone, float
       result equals the exact decimal result on a tick grid; RN step validation across minticks; label geometry

Evidence class: PINE_NOT_VERIFIED (TradingView compile / runtime / display / Profiler external).
"""
import copy
import difflib
import math
import os
import random
import re
import subprocess
import sys
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import btc_build as bb           # noqa: E402
import gbe_build as ge           # noqa: E402
import fvg_re10045_sim as fr     # noqa: E402
import practical_zone_sim as pz  # noqa: E402

ROOT = bb.ROOT
BASE = "5957053"
ENGINE_PATH = "ZoneEnginePracticalGBPJPY.pine"
rd = lambda p: open(os.path.join(ROOT, p), encoding="utf-8").read() if os.path.exists(os.path.join(ROOT, p)) else ""
GBJ = rd(bb.SRC_PATH)
BTC = rd(bb.BTC_PATH)
ENG = rd(ENGINE_PATH)
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


def code_only(src):
    return "\n".join(l for l in src.split("\n") if not l.lstrip().startswith("//"))


def inp(src, name):
    m = re.search(r"^" + name + r"\s*=\s*input\.\w+\((.*)$", src, re.M)
    return m.group(1) if m else ""


def input_decls(src):
    """name -> full declaration text (first line + continuation lines) of every input.* declaration."""
    out, lines = {}, src.split("\n")
    for i, l in enumerate(lines):
        m = re.match(r"^(\w+)\s*=\s*input\.\w+\(", l)
        if m:
            j, txt = i + 1, l
            while j < len(lines) and lines[j].startswith("     ") and not re.match(r"^\w", lines[j]):
                txt += "\n" + lines[j]
                j += 1
            out[m.group(1)] = txt
    return out


def input_values(src):
    return {n: v.strip() for n, v in re.findall(r"^(\w+)\s*=\s*input\.\w+\(([^,]+),", src, re.M)}


def kw(decl, key):
    m = re.search(r"\b" + key + r"\s*=\s*([-\d.]+)", decl)
    return m.group(1) if m else None


PRICE_INPUTS = {   # name: (default, minval, step) — every price difference in the file, USD, unverified starting values
    "zoneHalfWidth": ("50.0", "1.0", "5.0"),
    "clusterDist": ("100.0", "0.0", "5.0"),
    "fvgMinWidth": ("50.0", "0.0", "5.0"),
    "slopeThrMod": ("10.0", "0.0", "1.0"),
    "slopeThrStrong": ("30.0", "0.0", "1.0"),
    "maClusterDist": ("300.0", "0.0", "10.0"),
    "touchRearmDist": ("150.0", "0.0", "10.0"),
    "dsDist": ("50.0", "0.0", "1.0"),
    "breakBuffer": ("50.0", "0.0", "5.0"),
    "flipConfirmDist": ("150.0", "0.0", "10.0"),
    "rnMajorStep": ("1000.0", "1.0", "100.0"),
    "rnMinorStep": ("500.0", "1.0", "50.0"),
}
GEOM_NEW = ('f_num(z.top, format.mintick) + " - " + f_num(z.bottom, format.mintick) + "\\nW " + '
            'f_num(z.top - z.bottom, format.mintick) + " USD"')


def allowed_code_line(line):
    """A code (non-comment) line a BTC-1 EDIT may change."""
    s = line.strip()
    return (re.match(r"^(" + "|".join(PRICE_INPUTS) + r"|showGeom|enableRn|fvgDirMatch)\s*=\s*input\.\w+\(", s) is not None
            or re.match(r'^(tooltip = )?".*"\)?( \+)?$', s) is not None
            or re.match(r'^(title|shorttitle)\s*=\s*"[^"]*",$', s) is not None
            or s in ("f_jpyGeom(zn.Zone z) =>", "f_usdGeom(zn.Zone z) =>", GEOM_NEW,
                     'f_num(z.top, "#.000") + " - " + f_num(z.bottom, "#.000") + " | W " + f_num(z.top - z.bottom, "0.000") + "円"',
                     'txt := txt + "\\n" + f_jpyGeom(z)', 'txt := txt + "\\n" + f_usdGeom(z)',
                     'var string G_RN = "02 · Round Number (GBPJPY)"', 'var string G_RN = "02 · Round Number (BTCUSD)"',
                     'zoneCfg.useRnSource          := enableRn and rnStepOK and syminfo.ticker == "GBPJPY"',
                     'zoneCfg.useRnSource          := enableRn and rnStepOK and syminfo.ticker == "BTCUSD"')
            or s.startswith('runtime.error("Round Number: 刻みが不正です'))


def engine_type_fields(src, name):
    m = re.search(r"^export type " + name + r"\n((?:    .*\n|\s*\n)+)", src, re.M)
    if not m:
        return set()
    return {f.group(1) for f in re.finditer(r"^    \w+(?:<[^>]+>)?\s+(\w+)", m.group(1), re.M)}


def gate_static():
    check("BS-01 ZoneVisualBTCUSD.pine == btc_transform(ZoneVisualGBPJPY.pine); rebuilding gives the same bytes; strip_btc "
          "gives ZONE-GBPJPY back byte for byte (the file differs only by the listed edits)",
          bool(BTC) and bb.build() == BTC and bb.build() == bb.build() and bb.strip_btc(BTC) == GBJ
          and bb.btc_transform(bb.strip_btc(BTC)) == BTC)
    check("BS-02 every EDIT is tagged header / title / input / rn / display and replaces a text that occurs exactly once",
          all(k in ("header", "title", "input", "rn", "display") for k, _, _ in bb.EDITS)
          and all(GBJ.count(a) == 1 and BTC.count(b) == 1 for _, a, b in bb.EDITS))
    ga, ba = code_only(GBJ).split("\n"), code_only(BTC).split("\n")
    changed = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, ga, ba, autojunk=False).get_opcodes():
        if op != "equal":
            changed += [("-", l) for l in ga[i1:i2]] + [("+", l) for l in ba[j1:j2]]
    bad = [l for _, l in changed if not allowed_code_line(l)]
    check("BS-03 diff scope: every changed code line (both sides) is a price input / its tooltip, the title, the RN symbol "
          "gate / group / error text, or the Zone geometry text (no Engine call, request, gate, loop or drawing change)",
          changed and not bad, str(bad[:4]))
    check("BS-04 identity: title 'Zone Visual BTCUSD (Compare)', shorttitle 'ZONE-BTCUSD'; indicator() options otherwise "
          "identical (overlay, dynamic_requests, max boxes / labels 500)",
          '     title            = "Zone Visual BTCUSD (Compare)",\n     shorttitle       = "ZONE-BTCUSD",\n' in BTC
          and BTC[BTC.index("indicator("):BTC.index("import ")].replace("BTCUSD", "GBPJPY")
          == GBJ[GBJ.index("indicator("):GBJ.index("import ")])
    imp = re.findall(r"^import .*$", BTC, re.M)
    check("BS-05 Engine import identical to ZONE-GBPJPY and to the published mapping in gbe_build (ZoneEnginePracticalGBPJPY/3)",
          imp == re.findall(r"^import .*$", GBJ, re.M) and imp == [ge.IMPORT_GBE.strip()]
          and ge.IMPORT_GBE == "import sekine3310/ZoneEnginePracticalGBPJPY/3 as zn\n", str(imp))
    cfgF, feedF, zoneF, engF = (engine_type_fields(ENG, t) for t in ("ZoneCfg", "ZoneFeed", "Zone", "ZoneEngine"))
    exports = set(re.findall(r"^export (\w+)\(", ENG, re.M)) | set(re.findall(r"^export type (\w+)", ENG, re.M))
    used_cfg = set(re.findall(r"zoneCfg\.(\w+)\s*:=", BTC))
    feed_blk = BTC[BTC.index("zn.ZoneFeed.new("):BTC.index("brEval = brEval)") + 1]
    used_feed = set(re.findall(r"(\w+)\s*=", feed_blk))
    used_zn = set(re.findall(r"\bzn\.(\w+)", code_only(BTC)))
    used_z = set(re.findall(r"\b(?:z|bz|sz)\.(\w+)", code_only(BTC)))
    used_e = set(re.findall(r"\bzoneEng\.(\w+)", code_only(BTC)))
    check("BS-06 Engine API: every zoneCfg field set, every ZoneFeed argument, every zn.* function / type, every Zone and "
          "ZoneEngine field read exists in the repository Engine ZoneEnginePracticalGBPJPY.pine (incl. accScoreMax / "
          "accEdgeOnce / dsMerge / dsDist of /3)",
          cfgF and used_cfg <= cfgF and used_feed <= feedF and used_zn <= exports and used_z <= zoneF and used_e <= engF
          and {"accScoreMax", "accEdgeOnce", "dsMerge", "dsDist", "useRnSource", "rnStepMajor"} <= used_cfg,
          str((used_cfg - cfgF, used_feed - feedF, used_zn - exports, used_z - zoneF, used_e - engF)))
    bd, gd = input_decls(BTC), input_decls(GBJ)
    bad = []
    for n, (d, mn, st) in PRICE_INPUTS.items():
        dec = bd.get(n, "")
        if not (input_values(BTC).get(n) == d and kw(dec, "minval") == mn and kw(dec, "step") == st
                and "(USD" in dec and "円" not in dec and "pips" not in dec and "[未検証]" in dec):
            bad.append(n)
    check("BS-07 USD price inputs: Half Width 50 / Cluster 100 / FVG Min Width 50 / Slope 10 · 30 / MA Cluster 300 / "
          "Touch Re-arm 150 / Day/Swing Merge 50 / Break Buffer 50 / Flip Confirm 150 / RN 1,000 · 500 USD, each [未検証], "
          "labelled USD, minval / step in USD", not bad, str(bad))
    tips = {n: bd.get(n, "") for n in ("zoneHalfWidth", "clusterDist", "fvgMinWidth")}
    check("BS-08 comparison candidates in the tooltips (Half Width 25 / 50 / 100, Cluster 50 / 100 / 150, FVG 25 / 50 / 100 "
          "USD), all >= minval; no old GBPJPY candidates / yen text left",
          "25 / 50 / 100 USD" in tips["zoneHalfWidth"] and "50 / 100 / 150 USD" in tips["clusterDist"]
          and "25 / 50 / 100 USD" in tips["fvgMinWidth"]
          and all(not re.search(r"0\.0[358]|0\.1[026]|円|pips|GBPJPY", t) for t in tips.values()))
    same_other = [n for n in gd if n not in PRICE_INPUTS and n not in ("showGeom", "enableRn", "fvgDirMatch")
                  and gd[n] != bd.get(n)]
    check("BS-09 dimensionless / other inputs identical (scores, ATR multiples, lengths, bars, TFs, modes, Day Session "
          "Asia/Tokyo + Reset 5, display / filter / colours); enableRn and FVG Direction Match default false as before; "
          "the input set is the same",
          not same_other and set(gd) == set(bd)
          and input_values(BTC)["enableRn"] == input_values(GBJ)["enableRn"] == "false"
          and input_values(BTC)["fvgDirMatch"] == "false" and input_values(BTC)["dayTz"] == '"Asia/Tokyo"'
          and input_values(BTC)["dayResetHour"] == "5" and input_values(BTC)["accScoreMode"] == '"Max"'
          and input_values(BTC)["accEdgeMode"] == '"Separate"' and input_values(BTC)["dsMode"] == '"Separate"',
          str(same_other))
    co = code_only(BTC)
    check("BS-10 no yen / pips / 3-decimal / XAUUSD leftovers; 'GBPJPY' only in the import (Engine library name) and in "
          "header comments describing the derivation",
          not re.search(r"円|pips|ドル円|XAUUSD|#\.000|0\.000|f_jpyGeom", BTC)
          and [l for l in co.split("\n") if "GBPJPY" in l] == [ge.IMPORT_GBE.strip()])
    check("BS-11 RN symbol gate: useRnSource = enableRn and rnStepOK and syminfo.ticker == \"BTCUSD\" (exact ticker, so "
          "BTCJPY / BTCUSDT do not match); no basecurrency / currency guess; the only runtime.error is the RN step "
          "check, guarded by enableRn (a different symbol never stops the script)",
          co.count('syminfo.ticker == "BTCUSD"') == 1
          and 'zoneCfg.useRnSource          := enableRn and rnStepOK and syminfo.ticker == "BTCUSD"' in co
          and not re.search(r"basecurrency|syminfo\.currency|syminfo\.prefix|syminfo\.type", co)
          and co.count("runtime.error(") == 1 and "if enableRn and not rnStepOK\n    runtime.error(" in co)
    req = lambda s: re.findall(r"request\.\w+\(.*$", code_only(s), re.M)
    cnt = lambda s, p: len(re.findall(p, code_only(s)))
    pats = (r"\bfor\b", r"\bwhile\b", r"zn\.update\(", r"zn\.zoneAt\(", r"box\.new\(", r"label\.new\(", r"plot\(",
            r"barstate\.\w+", r"is5mChart", r"timeframe\.\w+")
    check("BS-12 5M gate / update / load unchanged: is5mChart = minutes x 5; zn.update only under `if is5mChart`; the 10 "
          "request.* calls, loops, zoneAt, box / label creation, plots and barstate uses identical to ZONE-GBPJPY "
          "(no added request, history scan or per-tick work)",
          "bool is5mChart = timeframe.isminutes and timeframe.multiplier == 5" in BTC
          and "if is5mChart\n    zoneCountNow := zn.update(zoneEng, zoneCfg, zoneFeed)" in BTC
          and req(BTC) == req(GBJ) and len(req(BTC)) == 10 and all(cnt(BTC, p) == cnt(GBJ, p) for p in pats)
          and "    if barstate.isconfirmed\n        int nowClose = time_close" in BTC
          and "if barstate.islast and is5mChart" in BTC and fr.lint_eager_guards(co) == [],
          str([(p, cnt(BTC, p), cnt(GBJ, p)) for p in pats]))
    check("BS-13 geometry text: f_usdGeom prints top / bottom / width with format.mintick and 'USD' (width on its own line), "
          "used by both the base and the FVG-boosted label; Strength / Touch / Score / FVG tag / sources unchanged",
          "f_usdGeom(zn.Zone z) =>\n    " + GEOM_NEW + "\n" in BTC and co.count("f_usdGeom(z)") == 2
          and "showGeom   = input.bool(true,  \"Label: Zone 上下限 / 幅 (USD) を表示\"" in BTC)
    check("BS-14 no weekday exclusion added (dayofweek / session filters absent, as in ZONE-GBPJPY)",
          not re.search(r"dayofweek|session\.|input\.session", co) and not re.search(r"dayofweek|input\.session", code_only(GBJ)))
    out = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", BASE, "--"], capture_output=True, text=True).stdout.split()
    tracked = subprocess.run(["git", "-C", ROOT, "ls-files"], capture_output=True, text=True).stdout.split()
    new_ok = {bb.BTC_PATH, "tests/btc_build.py", "tests/btc_sim.py"}
    check(f"BS-15 existing files unchanged vs base HEAD {BASE} (GBPJPY / USDJPY / Gold Visuals, Strategies, Engines, "
          "tests); only the new BTC files are added", subprocess.run(["git", "-C", ROOT, "cat-file", "-e", BASE]).returncode == 0
          and not [f for f in out if f not in new_ok] and all(f in tracked or f in new_ok for f in new_ok | set(out)),
          str(out))
    # mutations: the checks must catch a reverted gate / a leftover yen input / an extra request
    m1 = BTC.replace('syminfo.ticker == "BTCUSD"', 'syminfo.ticker == "GBPJPY"')
    m2 = BTC.replace('zoneHalfWidth = input.float(50.0, "[未検証] Zone Half Width (USD)"', 'zoneHalfWidth = input.float(0.05, "[未検証] Zone Half Width (USD)"')
    m3 = BTC.replace("if is5mChart\n    zoneCountNow := zn.update(", "if true\n    zoneCountNow := zn.update(")
    check("BS-16 mutation: GBPJPY ticker gate, a yen default and an ungated update are each detected",
          'syminfo.ticker == "BTCUSD"' not in code_only(m1) and input_values(m2)["zoneHalfWidth"] != "50.0"
          and "if is5mChart\n    zoneCountNow := zn.update(" not in m3 and bb.strip_btc(m1) is None)


# ---- models -------------------------------------------------------------------------------------------------------------
def cfg_from(src):
    v = input_values(src)
    c = pz.BCfg()
    for f in ("zoneHalfWidth", "clusterDist", "touchRearmDist", "breakBuffer", "flipConfirmDist", "scoreHz1", "scoreHz2",
              "scoreHz3", "thrMedium", "thrStrong", "thrVStrong", "confBonus2", "confBonus3", "confBonus4", "flipBonus"):
        setattr(c, f, float(v[f]))
    c.resetOnReclaim = v["resetOnReclaim"] == "true"
    c.fvgMinWidth = float(v["fvgMinWidth"])
    return c


def usd_scenario(seed, base=65000.0):
    rng = random.Random(seed)
    srcs = []
    for i in range(14):
        cat, sid, tf, sc = rng.choice([(pz.CAT_HZ, "SWING_H", "5", 1.0), (pz.CAT_HZ, "SWING_L", "15", 2.0),
                                      (pz.CAT_HZ, "SWING_H", "60", 3.0), (pz.CAT_ACC, "ACC_HI", "60", 3.0),
                                      (pz.CAT_ACC, "ACC_LO", "240", 4.0), (pz.CAT_DHL, "DAY_H", "D", 3.0)])
        srcs.append((i, sid, cat, tf, round(base + rng.uniform(-1200, 1200), 2), sc))
    path, px = [], base
    for _ in range(240):
        o = px
        px = round(px + rng.gauss(0, 60), 2)
        path.append((round(max(o, px) + abs(rng.gauss(0, 20)), 2), round(min(o, px) - abs(rng.gauss(0, 20)), 2), px))
    return srcs, path


def run_engine(c, srcs, path):
    raws = [pz.Raw(i, sid, cat, tf, ctr, sc, c) for i, sid, cat, tf, ctr, sc in srcs]
    zones = pz.practical_build(raws, [], c)
    out = []
    for z in zones:
        t = pz.Track(z["top"], z["bottom"], wasStrong=False)
        t.flipped = False
        evs = [pz.engine_bar(t, c, z["strength"], z["top"], z["bottom"], hlc, k) for k, hlc in enumerate(path)]
        out.append((round(z["bottom"], 6), round(z["top"], 6), z["uids"], z["score"], z["strength"], t.state,
                    t.touchCount, tuple(e for e in evs if e)))
    return out


def rn_level_in(zbot, ztop, step):
    """port of Engine f_rnLevelIn (float arithmetic as in Pine)."""
    k1, k2 = math.ceil(zbot / step), math.floor(ztop / step)
    if k1 > k2:
        return None
    ctr = (ztop + zbot) / 2
    kc = max(k1, min(k2, math.floor(ctr / step)))
    lv = kc * step
    if kc + 1 <= k2 and (kc + 1) * step - ctr < ctr - lv:
        lv = (kc + 1) * step
    return lv


def rn_exact(zbot, ztop, step):
    b, t, s = Decimal(zbot), Decimal(ztop), Decimal(step)
    return (b / s).to_integral_value(ROUND_CEILING) <= (t / s).to_integral_value(ROUND_FLOOR)


def rn_pick(zbot, ztop, maj=1000.0, mnr=500.0, smaj=3.0, smin=2.0):
    """Engine RN block: major first, else minor; one bonus per Zone."""
    lv = rn_level_in(zbot, ztop, maj)
    if lv is not None:
        return lv, smaj
    lv = rn_level_in(zbot, ztop, mnr)
    return (lv, smin) if lv is not None else (None, 0.0)


def rn_step_ok(maj, mnr, mintick):
    """port of the Visual rnStepOK expression."""
    ratio = maj / mnr if mnr > 0 else 0.0
    majT, minT = maj / mintick, mnr / mintick
    return (mnr > 0 and maj > mnr and abs(ratio - round(ratio)) < 1e-9 and abs(majT - round(majT)) < 1e-6
            and abs(minT - round(minT)) < 1e-6 and maj * 8 == round(maj * 8) and mnr * 8 == round(mnr * 8))


def fvg_dir(h2, l2, h0, l0, min_w, mintick=0.01):
    bull, bear = l0 > h2, h0 < l2
    top, bot = (l0, h2) if bull else (l2, h0)
    w = round(round((top - bot) / mintick) * mintick, 6)
    return (1 if bull else -1) if (bull or bear) and w >= min_w else 0


def gate_model():
    cb, cg = cfg_from(BTC), cfg_from(GBJ)
    check("BM-01 Engine config read from the BTC file: HW 50 / Cluster 100 / FVG 50 / Touch 150 / Break 50 / Flip 150 USD; "
          "scores / thresholds / confluence identical to ZONE-GBPJPY",
          (cb.zoneHalfWidth, cb.clusterDist, cb.fvgMinWidth, cb.touchRearmDist, cb.breakBuffer, cb.flipConfirmDist)
          == (50.0, 100.0, 50.0, 150.0, 50.0, 150.0)
          and all(getattr(cb, f) == getattr(cg, f) for f in ("scoreHz1", "scoreHz2", "scoreHz3", "thrMedium", "thrStrong",
                                                             "thrVStrong", "confBonus2", "confBonus3", "confBonus4",
                                                             "flipBonus", "resetOnReclaim")))
    same, nonvac, zcount = True, False, 0
    for seed in range(40):
        srcs, path = usd_scenario(seed)
        cg_eq = copy.copy(cg)
        for f in ("zoneHalfWidth", "clusterDist", "touchRearmDist", "breakBuffer", "flipConfirmDist", "fvgMinWidth"):
            setattr(cg_eq, f, getattr(cb, f))             # the GBPJPY file with the same (USD) inputs
        a = run_engine(cb, srcs, path)
        same &= a == run_engine(cg_eq, srcs, path)
        nonvac |= any(e for z in a for e in z[7])
        zcount += len(a)
    check("BM-02 same BTC OHLC + sources + inputs (40 seeds): Zones, Score, Strength, state, Touch and Break / Flip events "
          "identical between the BTC and GBPJPY files' configs (only inputs differ); non-vacuous (zones and events occur)",
          same and nonvac and zcount > 40, str(zcount))
    srcs = [(0, "SWING_H", pz.CAT_HZ, "5", 65000.00, 1.0), (1, "SWING_L", pz.CAT_HZ, "15", 65800.00, 2.0),
            (2, "ACC_HI", pz.CAT_ACC, "60", 67000.00, 3.0), (3, "SWING_H", pz.CAT_HZ, "60", 67080.00, 3.0)]
    widths = {}
    for hw in (25.0, 50.0, 100.0):
        c = copy.copy(cb)
        c.zoneHalfWidth = hw
        widths[hw] = [(len(z[2]), round(z[1] - z[0], 6)) for z in run_engine(c, srcs, [(65900, 65850, 65880)])]
    check("BM-03 Half Width candidates 25 / 50 / 100 USD (Cluster 100): a single-source Zone is 2 x HW wide; two sources "
          "80 USD apart merge into min bottom - max top = 2 x HW + 80",
          all(w == [(1, 2 * hw), (1, 2 * hw), (2, 2 * hw + 80)] for hw, w in widths.items()), str(widths))
    merged = {}
    for cd in (50.0, 100.0, 150.0):
        c = copy.copy(cb)
        c.clusterDist = cd
        merged[cd] = sorted(len(z[2]) for z in run_engine(c, [(0, "SWING_H", pz.CAT_HZ, "5", 65000.0, 1.0),
                                                                (1, "SWING_L", pz.CAT_HZ, "15", 65240.0, 1.0)], [(65100, 65050, 65060)]))
    check("BM-04 Cluster Distance candidates 50 / 100 / 150 USD (membership = every centre within the distance of the "
          "weighted centre): two equal-score sources 240 USD apart (120 from the centre) stay separate at 50 / 100, merge at 150", merged == {50.0: [1, 1], 100.0: [1, 1], 150.0: [2]}, str(merged))
    g = [fvg_dir(65000.00, 64900.00, 65200.00, 65050.00, cb.fvgMinWidth), fvg_dir(65000.00, 64900.00, 65200.00, 65049.99, 50.0),
         fvg_dir(65000.00, 64900.00, 65200.00, 65025.00, 25.0), fvg_dir(65000.00, 64900.00, 65200.00, 65099.99, 100.0)]
    check("BM-05 FVG min width (mintick 0.01): a 50.00 USD gap qualifies at 50, 49.99 does not; candidates 25 / 100 gate "
          "the same way", g == [1, 0, 1, 0], str(g))
    cases = {
        "major inside": (64950.00, 65050.00, (65000.0, 3.0)),
        "minor only": (64450.00, 64550.00, (64500.0, 2.0)),
        "none": (64600.00, 64900.00, (None, 0.0)),
        "bottom on major": (65000.00, 65100.00, (65000.0, 3.0)),
        "top on major": (64900.00, 65000.00, (65000.0, 3.0)),
        "top on minor": (64400.00, 64500.00, (64500.0, 2.0)),
        "just below major": (64900.00, 64999.99, (None, 0.0)),
        "just above minor": (64500.01, 64600.00, (None, 0.0)),
        "major beats minor": (64400.00, 65100.00, (65000.0, 3.0)),
        "two majors, nearest": (64800.00, 66300.00, (66000.0, 3.0)),
    }
    got = {k: rn_pick(b, t) for k, (b, t, _) in cases.items()}
    check("BM-06 RN (1,000 / 500 USD, +3 / +2): inside range only, boundary inclusive, nothing at 0.01 outside, major "
          "first when both qualify, one level / one bonus per Zone (nearest the centre)",
          all(got[k] == exp for k, (_, _, exp) in cases.items()), str({k: v for k, v in got.items() if v != cases[k][2]}))
    rng, bad = random.Random(7), []
    for _ in range(200000):
        base = rng.choice([rng.randint(10000, 150000) * 1.0, rng.randint(20, 300) * 500.0])
        hw = rng.choice([25.0, 50.0, 100.0])
        ctr = round(base + rng.choice([0, 0, rng.randint(-20000, 20000) / 100]) + rng.choice([-hw, hw, 0.0]), 2)
        b, t = round(ctr - hw, 2), round(ctr + hw, 2)
        for st in (1000.0, 500.0):
            if (rn_level_in(b, t, st) is not None) != rn_exact(repr(b), repr(t), repr(st)):
                bad.append((b, t, st))
    check("BM-07 RN float check == exact decimal check on a 0.01 tick grid (200k zones near / on 1,000 / 500 multiples, "
          "HW 25 / 50 / 100; float ceil / floor of price / step never misses or adds a boundary level)", not bad, str(bad[:3]))
    ok = {mt: rn_step_ok(1000.0, 500.0, mt) for mt in (0.01, 0.1, 1.0, 0.5, 0.05, 0.001)}
    check("BM-08 RN step validation passes for 1,000 / 500 USD at minticks 0.01 / 0.1 / 1 / 0.5 / 0.05 / 0.001 (no false "
          "runtime error); still rejects bad steps (major not a multiple, minor > major, 333.3)",
          all(ok.values()) and not rn_step_ok(1000.0, 300.0, 0.01) and not rn_step_ok(500.0, 1000.0, 0.01)
          and not rn_step_ok(1000.0, 333.3, 0.01), str(ok))
    gate = lambda enable, ticker: enable and ticker == "BTCUSD"
    check("BM-09 RN gate: OFF by default; with the input ON it adds only on ticker BTCUSD (BTCJPY / BTCUSDT / GBPJPY / XAUUSD "
          "get no RN; nothing stops)", gate(False, "BTCUSD") is False and gate(True, "BTCUSD") is True
          and not any(gate(True, t) for t in ("BTCJPY", "BTCUSDT", "GBPJPY", "XAUUSD")))
    fm = lambda v: f"{v:.2f}"            # format.mintick at mintick 0.01
    geo = lambda top, bot: fm(top) + " - " + fm(bot) + "\nW " + fm(top - bot) + " USD"
    check("BM-10 label geometry (mintick 0.01): top 65050, bottom 64950 -> '65050.00 - 64950.00' / 'W 100.00 USD'; "
          "6-digit prices keep a short second line", geo(65050.0, 64950.0) == "65050.00 - 64950.00\nW 100.00 USD"
          and geo(123456.78, 123256.78) == "123456.78 - 123256.78\nW 200.00 USD")


def main():
    for g in (gate_static, gate_model):
        try:
            g()
        except Exception:
            import traceback
            check(f"{g.__name__} completed without error", False, traceback.format_exc()[-900:])
    fails = 0
    for n, ok, d in RESULTS:
        fails += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {n[:150].ljust(150)}  {'' if ok else d}")
    print(f"\n{len(RESULTS) - fails}/{len(RESULTS)} passed  [PINE_NOT_VERIFIED: exact build / static / model]")
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
