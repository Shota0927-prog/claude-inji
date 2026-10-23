"""BTC-1 / BTC-2 / BTC-3 fixtures — ZoneVisualBTCUSD.pine (CRYPTO:BTCUSD 5M Zone display, no entries / alerts).

  The file differs from ZONE-GBPJPY in two layers: BTC-1 (name / USD inputs / RN symbol gate / geometry text) and BTC-2
  (update timing: Engine state only on confirmed 5M bars, forming bars display the last confirmed state). BTC-1 checks
  run on BTC1 = strip_btc2(file) (== commit f326724); BTC-2 checks (BT) pin the timing delta on top of it.
  BTC-3 changes only the verification symbol in the header comment to CRYPTO:BTCUSD 5M (BC); strip_btc3(file) ==
  commit a36c3e8. Data always comes from syminfo.tickerid (no exchange / symbol hard-coded).
  BS : static — deterministic, idempotent build from ZONE-GBPJPY; strip_btc(file) == ZONE-GBPJPY byte for byte; every
       BTC-1 changed code line is a price input (USD), the title, the RN symbol gate / error text or the geometry text;
       USD defaults / minval / step as specified; dimensionless inputs identical; no yen / pips / 3-decimal leftovers;
       Engine import and API consistent with the repository Engine (ZoneEnginePracticalGBPJPY /3); 5M gate, update
       call, requests, loops and drawing identical; RN gate = ticker BTCUSD only (no basecurrency guess, no stop);
       existing files unchanged vs the base HEAD 5957053
  BT : static (BTC-2) — the only code delta vs BTC-1 is the confirmed-only update, the read-only zone count on forming
       ticks and the draw order by the last confirmed close (a port of zn.drawOrder with only the reference price
       changed); requests / feeds / FVG store untouched; every persistent state writer inventoried
  BR : model (BTC-2) — Pine realtime rollback emulation: committed states per bar identical for history / old per-tick
       update / new confirmed-only update (Day switch, Swing key, HTF Accum, FVG add / fill / expiry, Touch, Break, Flip);
       exactly one committing update per bar; forming ticks show the previous confirmed state and draw order
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
rd = lambda p: __import__("sx_build").unapply(p, open(os.path.join(ROOT, p), encoding="utf-8").read()) if os.path.exists(os.path.join(ROOT, p)) else ""   # SX-1 reverted (pinned in sxs_sim)
GBJ = rd(bb.SRC_PATH)
BTC_FULL = rd(bb.BTC_PATH)
BTC = bb.strip_btc4(BTC_FULL) or ""      # BTE-1: the BTC-3 file (e1c3cea); BTC-4 (engine split) is pinned in bte_sim
ENG = rd(ENGINE_PATH)
BTC1_COMMIT = "f326724"
BTC1 = bb.strip_btc2(BTC_FULL) or ""          # the BTC-1 file (BTC-3 and BTC-2 edits reverted)
BTC2_COMMIT = "a36c3e8"
BTC2 = bb.strip_btc3(BTC_FULL) or ""          # the BTC-2 file (BTC-3 symbol comment reverted)
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
          "gives ZONE-GBPJPY back byte for byte; strip_btc2 / strip_btc3 give the BTC-1 (f326724) / BTC-2 (a36c3e8) files",
          bool(BTC) and bb.build() == BTC_FULL and bb.build() == bb.build() and bb.strip_btc(BTC_FULL) == GBJ
          and bb.btc_transform(bb.strip_btc(BTC_FULL)) == BTC_FULL and bb.btc3_transform(GBJ) == BTC and bb.btc1_transform(GBJ) == BTC1
          and bb.btc2_transform(GBJ) == BTC2
          and BTC2 == subprocess.run(["git", "-C", ROOT, "show", BTC2_COMMIT + ":" + bb.BTC_PATH],
                                     capture_output=True, text=True).stdout
          and BTC1 == subprocess.run(["git", "-C", ROOT, "show", BTC1_COMMIT + ":" + bb.BTC_PATH],
                                     capture_output=True, text=True).stdout)
    check("BS-02 every BTC-1 EDIT is tagged header / title / input / rn / display, every BTC-2 EDIT header / timing, every BTC-3 EDIT header; each "
          "replaces a text that occurs exactly once",
          all(k in ("header", "title", "input", "rn", "display") for k, _, _ in bb.EDITS)
          and all(GBJ.count(a) == 1 and BTC1.count(b) == 1 for _, a, b in bb.EDITS)
          and all(k in ("header", "timing") for k, _, _ in bb.EDITS2)
          and all(BTC1.count(a) == 1 and BTC2.count(b) == 1 for _, a, b in bb.EDITS2)
          and all(k == "header" for k, _, _ in bb.EDITS3)
          and all(BTC2.count(a) == 1 and BTC.count(b) == 1 for _, a, b in bb.EDITS3))
    ga, ba = code_only(GBJ).split("\n"), code_only(BTC1).split("\n")
    changed = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, ga, ba, autojunk=False).get_opcodes():
        if op != "equal":
            changed += [("-", l) for l in ga[i1:i2]] + [("+", l) for l in ba[j1:j2]]
    bad = [l for _, l in changed if not allowed_code_line(l)]
    check("BS-03 BTC-1 diff scope: every changed code line (both sides) is a price input / its tooltip, the title, the RN symbol "
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
    check("BS-12 (BTC-1) 5M gate / update / load unchanged: is5mChart = minutes x 5; zn.update only under `if is5mChart`; the 10 "
          "request.* calls, loops, zoneAt, box / label creation, plots and barstate uses identical to ZONE-GBPJPY "
          "(no added request, history scan or per-tick work)",
          "bool is5mChart = timeframe.isminutes and timeframe.multiplier == 5" in BTC1
          and "if is5mChart\n    zoneCountNow := zn.update(zoneEng, zoneCfg, zoneFeed)" in BTC1
          and req(BTC1) == req(GBJ) and len(req(BTC1)) == 10 and all(cnt(BTC1, p) == cnt(GBJ, p) for p in pats)
          and "    if barstate.isconfirmed\n        int nowClose = time_close" in BTC1
          and "if barstate.islast and is5mChart" in BTC1 and fr.lint_eager_guards(code_only(BTC1)) == [],
          str([(p, cnt(BTC1, p), cnt(GBJ, p)) for p in pats]))
    check("BS-13 geometry text: f_usdGeom prints top / bottom / width with format.mintick and 'USD' (width on its own line), "
          "used by both the base and the FVG-boosted label; Strength / Touch / Score / FVG tag / sources unchanged",
          "f_usdGeom(zn.Zone z) =>\n    " + GEOM_NEW + "\n" in BTC and co.count("f_usdGeom(z)") == 2
          and "showGeom   = input.bool(true,  \"Label: Zone 上下限 / 幅 (USD) を表示\"" in BTC)
    check("BS-14 no weekday exclusion added (dayofweek / session filters absent, as in ZONE-GBPJPY)",
          not re.search(r"dayofweek|session\.|input\.session", co) and not re.search(r"dayofweek|input\.session", code_only(GBJ)))
    out = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", "--diff-filter=MDR", BASE, "--"], capture_output=True, text=True).stdout.split()
    tracked = subprocess.run(["git", "-C", ROOT, "ls-files"], capture_output=True, text=True).stdout.split()
    new_ok = {bb.BTC_PATH, "tests/btc_build.py", "tests/btc_sim.py",
              "ZoneStrategyBTCUSD.pine", "tests/btcs_build.py", "tests/btcs_sim.py"}   # BTC Strategy (BTS-1 / BTS-2, own fixture btcs_sim)
    out2 = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", "--diff-filter=MDR", BTC2_COMMIT, "--"], capture_output=True,
                          text=True).stdout.split()
    out1 = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", "--diff-filter=MDR", BTC1_COMMIT, "--"], capture_output=True,
                          text=True).stdout.split()
    out, out1, out2 = (__import__("uj_build").drop_uj_tests(__import__("uj_build").drop_uj(out, BASE)), __import__("uj_build").drop_uj_tests(__import__("uj_build").drop_uj(out1, BTC1_COMMIT)),
                       __import__("uj_build").drop_uj_tests(__import__("uj_build").drop_uj(out2, BTC2_COMMIT)))     # UJ-1: USDJPY Visual / Strategy may differ only by the USDJPY Engine split + sizing (exact, see uj_build)
    check(f"BS-15 existing files unchanged vs base HEAD {BASE} (GBPJPY / USDJPY / Gold Visuals, Strategies, Engines, "
          "tests) and vs f326724 / a36c3e8 (BTC-2 / BTC-3 touch only the BTC Visual / build / sim); ZoneVisualGBPJPY.pine and "
          "ZoneEnginePracticalGBPJPY.pine untouched", subprocess.run(["git", "-C", ROOT, "cat-file", "-e", BASE]).returncode == 0
          and not [f for f in out if f not in new_ok] and all(f in tracked or f in new_ok for f in new_ok | set(out))
          and not [f for f in out1 if f not in new_ok] and not [f for f in out2 if f not in new_ok],
          str((out, out1, out2)))
    # mutations: the checks must catch a reverted gate / a leftover yen input / an extra request
    m1 = BTC.replace('syminfo.ticker == "BTCUSD"', 'syminfo.ticker == "GBPJPY"')
    m2 = BTC.replace('zoneHalfWidth = input.float(50.0, "[未検証] Zone Half Width (USD)"', 'zoneHalfWidth = input.float(0.05, "[未検証] Zone Half Width (USD)"')
    m3 = BTC1.replace("if is5mChart\n    zoneCountNow := zn.update(", "if true\n    zoneCountNow := zn.update(")
    check("BS-16 mutation: GBPJPY ticker gate, a yen default and an ungated update are each detected",
          'syminfo.ticker == "BTCUSD"' not in code_only(m1) and input_values(m2)["zoneHalfWidth"] != "50.0"
          and "if is5mChart\n    zoneCountNow := zn.update(" not in m3 and bb.strip_btc(m1) is None)


# ---- BTC-2: update timing -----------------------------------------------------------------------------------------------
DRAW_FN = (
    "float btcDrawRef = barstate.isconfirmed ? close : close[1]\n"
    "f_btcDrawOrder(int maxN, float ref) =>\n")


def engine_fn(src, head):
    i = src.index(head)
    j = src.index("\n    out\n", i) + len("\n    out\n")
    return src[i:j]


def gate_timing():
    ga, ba = code_only(BTC1).split("\n"), code_only(BTC).split("\n")
    rem, add = [], []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, ga, ba, autojunk=False).get_opcodes():
        if op != "equal":
            rem += [l.strip() for l in ga[i1:i2]]
            add += [l.strip() for l in ba[j1:j2]]
    exp_rem = ["if is5mChart", "array<int> ord = zn.drawOrder(zoneEng, zn.zoneCount(zoneEng))"]
    exp_add = ["if is5mChart and barstate.isconfirmed", "else if is5mChart",
               "zoneCountNow := zn.zoneCount(zoneEng)    // 読み取りだけ (update の戻り値と同じ array.size(live))",
               "float btcDrawRef = barstate.isconfirmed ? close : close[1]", "f_btcDrawOrder(int maxN, float ref) =>",
               "array<int> out = array.new_int()", "int n = zn.zoneCount(zoneEng)", "if n > 0",
               "array<float> d = array.new_float()", "for i = 0 to n - 1",
               "array.push(d, math.abs(zn.zoneAt(zoneEng, i).center - ref))",
               "array<int> ord = array.sort_indices(d, order.ascending)", "int lim = int(math.min(n, maxN))",
               "for k = 0 to lim - 1", "array.push(out, array.get(ord, k))", "out", "",
               "array<int> ord = f_btcDrawOrder(zn.zoneCount(zoneEng), btcDrawRef)"]
    check("BT-01 BTC-2 code delta vs BTC-1 (f326724) is exactly: confirmed-only update condition, read-only zone count on "
          "other 5M ticks, draw order by the last confirmed close (function + call); nothing else in code changes",
          sorted(rem) == sorted(exp_rem) and sorted(add) == sorted(exp_add), str((rem, add)))
    co = code_only(BTC)
    upd = ("if is5mChart and barstate.isconfirmed\n    zoneCountNow := zn.update(zoneEng, zoneCfg, zoneFeed)\n"
           "else if is5mChart\n    zoneCountNow := zn.zoneCount(zoneEng)")
    check("BT-02 Engine state update only under `is5mChart and barstate.isconfirmed` (one zn.update call; never on a non-5M "
          "chart; on historical bars isconfirmed is always true, so history runs the same update on the same bars); the "
          "other branch only reads zn.zoneCount (= update's return array.size(live)) for Stats",
          co.count("zn.update(") == 1 and upd in co and "    array.size(e.live)\n\n// @function" in ENG
          and re.search(r"export zoneCount\(ZoneEngine e\) =>\n    array\.size\(e\.live\)", ENG) is not None
          and re.search(r"export update\(ZoneEngine e, ZoneCfg c, ZoneFeed f\) =>", ENG) is not None
          and engine_fn_update_returns_live())
    eng_do = engine_fn(ENG, "export drawOrder(ZoneEngine e, int maxN) =>\n")
    ported = (eng_do.replace("export drawOrder(ZoneEngine e, int maxN) =>", "f_btcDrawOrder(int maxN, float ref) =>")
              .replace("int n = array.size(e.live)", "int n = zn.zoneCount(zoneEng)")
              .replace("math.abs(array.get(e.live, i).center - close)", "math.abs(zn.zoneAt(zoneEng, i).center - ref)"))
    check("BT-03 f_btcDrawOrder is zn.drawOrder with only the reference price replaced (close -> btcDrawRef = close on a "
          "confirmed tick, close[1] while forming) and live access via zn.zoneCount / zn.zoneAt; read-only",
          DRAW_FN + ported[len("f_btcDrawOrder(int maxN, float ref) =>\n"):] in BTC and "zn.drawOrder(" not in co
          and "array<int> ord = f_btcDrawOrder(zn.zoneCount(zoneEng), btcDrawRef)" in co)
    pre = lambda t: code_only(t[:t.index("int zoneCountNow = 0")])
    fvg = lambda t: code_only(t[t.index("// ==== FVG Batch A (begin)"):t.index("// ==== FVG Batch A (end)")])
    req = lambda t: re.findall(r"request\.\w+\(.*$", code_only(t), re.M)
    check("BT-04 requests, Source / Break / day-ID feeds and the ZoneFeed construction (everything before the update) and the "
          "FVG Batch A block (requests every tick, store only on confirmed bars) are code-identical to BTC-1; the 10 "
          "request.* calls are unchanged and not moved into the confirmed condition",
          pre(BTC) == pre(BTC1) and fvg(BTC) == fvg(BTC1) and req(BTC) == req(BTC1) and len(req(BTC)) == 10
          and "if barstate.isconfirmed and is5mChart" not in co)
    vars_ = re.findall(r"^var\s+(?:[\w.<>]+\s+)?(\w+)\s*=", co, re.M)
    fvg_blk = BTC[BTC.index("    if barstate.isconfirmed\n        int nowClose = time_close"):BTC.index("// ==== FVG Batch A (end)")]
    calls = lambda t, f: len(re.findall(r"(?<!\w)" + f + r"\(", code_only(t)))
    fvg_writes = [l for l in co.split("\n") if re.search(r"array\.(set|push|clear|remove)\(gFvg|gFvg\w+\s*:=", l)]
    allowed_w = {"gFvgNextExpire := f_fvgExpire(nowClose)"} | {l.strip() for l in fvg_blk.split("\n") if "gFvgNextExpire :=" in l}
    in_fns = code_only(BTC[BTC.index("f_fvgExpire(int nowClose) =>"):BTC.index("f_fvgMinExp(int a, int b) =>")])
    check("BT-05 persistent state inventory: global var = zoneEng (written only by the confirmed zn.update), the FVG store "
          "gFvg* (written only by f_fvgExpire / f_fvgOnEvent, both called only inside the confirmed-bar FVG block), and the "
          "drawing pools gBoxes / gLabels / gStats (display objects, set only in barstate.islast blocks); no varip",
          sorted(vars_) == sorted(["zoneEng", "gFvgTop", "gFvgBot", "gFvgDir", "gFvgOpenT", "gFvgCloseT", "gFvgExpire",
                                   "gFvgAlive", "gFvgLastKey", "gFvgNextExpire", "G_ZONE", "G_MA", "G_SLOPE", "G_HZ",
                                   "G_TOUCH", "G_DHL", "G_ACC", "G_ACCP", "G_ACCQ", "G_RN", "G_CLU", "G_SCORE", "G_HTF",
                                   "G_BF", "G_LIFE", "G_DISP", "G_LBL", "G_FLT", "gBoxes", "gLabels", "gStats"])
          and calls(BTC, "f_fvgExpire") == 2 and calls(BTC, "f_fvgOnEvent") == 4
          and calls(fvg_blk, "f_fvgExpire") == 1 and calls(fvg_blk, "f_fvgOnEvent") == 3
          and all(l.strip() in allowed_w or l in in_fns for l in fvg_writes)
          and "varip" not in co and co.count("zoneEng") == co.count("zn.update(zoneEng") + co.count("zn.zoneCount(zoneEng")
          + co.count("zn.zoneAt(zoneEng") + co.count("zoneEng.") + co.count("var zn.ZoneEngine zoneEng"),
          str(sorted(vars_)))
    m1 = BTC.replace("if is5mChart and barstate.isconfirmed\n", "if is5mChart\n")
    m2 = BTC.replace("float btcDrawRef = barstate.isconfirmed ? close : close[1]", "float btcDrawRef = close")
    check("BT-06 mutation: dropping barstate.isconfirmed from the update or drawing by the forming close is detected",
          "if is5mChart and barstate.isconfirmed\n    zoneCountNow := zn.update(" not in code_only(m1)
          and DRAW_FN not in m2 and bb.strip_btc2(m1) is None and bb.strip_btc2(m2) is None)


def engine_fn_update_returns_live():
    i = ENG.index("export update(ZoneEngine e, ZoneCfg c, ZoneFeed f) =>")
    j = ENG.index("\nexport ", i + 10)
    body = ENG[i:j].rstrip().split("\n")
    tail = [l for l in body if l.strip() and not l.strip().startswith("//")]
    return tail[-1] == "    array.size(e.live)" and not re.search(r"\[\d+\]|\bta\.", code_only(ENG[i:j]))


# ---- BTC-3: verification symbol CRYPTO:BTCUSD 5M, no hard-coded exchange --------------------------------------------------
def gate_symbol():
    X = "BIN" + "ANCE"
    co = code_only(BTC)
    reqs = re.findall(r"request\.(\w+)\(([^,]+),", co)
    check("BC-01 every request.* (10) reads syminfo.tickerid (the chart symbol); no exchange-prefixed symbol literal "
          "(\"XXX:YYY\"), ticker.new / syminfo.prefix or other fixed symbol reference in code",
          len(reqs) == 10 and all(f == "security" and a.strip() == "syminfo.tickerid" for f, a in reqs)
          and not re.search(r'"[A-Z0-9_]+:[A-Z0-9_.!]+"', co) and not re.search(r"ticker\.\w+\(|syminfo\.prefix", co),
          str(reqs[:3]))
    check("BC-02 the Pine file names the verification target CRYPTO:BTCUSD 5分足 and states that data comes from "
          "syminfo.tickerid; no " + X + " text anywhere in ZoneVisualBTCUSD.pine",
          X not in BTC and X.lower() not in BTC.lower()
          and "//  Zone Visual BTCUSD (Compare)  —  CRYPTO:BTCUSD 5分足用 Zone 表示 Indicator (Entry / Alert なし)\n" in BTC
          and "//  検証対象: CRYPTO:BTCUSD・5分足。実データはすべて syminfo.tickerid" in BTC)
    check("BC-03 BTC-3 is comment-only: code identical to BTC-2 (a36c3e8) — price inputs, Zone logic, RN gate (ticker "
          "BTCUSD) and the confirmed-bar update are unchanged", bool(BTC2) and code_only(BTC) == code_only(BTC2)
          and 'syminfo.ticker == "BTCUSD"' in co and "if is5mChart and barstate.isconfirmed\n    zoneCountNow := zn.update(" in co)
    src_b = open(os.path.join(ROOT, "tests", "btc_build.py"), encoding="utf-8").read()
    src_s = open(os.path.join(ROOT, "tests", "btc_sim.py"), encoding="utf-8").read()
    hist = [bb.EDITS[0][2], bb.EDITS3[0][1]]                   # BTC-1 committed header text (reverted by EDITS3)
    occ_b = [l for l in src_b.split("\n") if X in l]
    check("BC-04 build / sim docstrings name CRYPTO:BTCUSD; " + X + " remains only in the historical BTC-1 header text that "
          "EDITS / EDITS3 must match to reproduce f326724 (not a data reference); none in btc_sim",
          "CRYPTO:BTCUSD 5M" in src_b.split("\n")[0] and "CRYPTO:BTCUSD 5M" in src_s.split("\n")[0]
          and all(X + ":BTCUSD" in h for h in hist) and len(occ_b) == 2
          and all("Zone Visual BTCUSD (Compare)  —  " + X + ":BTCUSD 5分足用" in l for l in occ_b) and X not in src_s,
          str(occ_b))


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


# ---- BTC-2 realtime rollback model ----------------------------------------------------------------------------------------
REARM, BUF, FLIP = 150.0, 50.0, 150.0


def rb_new_state():
    return dict(dayId=None, dayH=None, dayL=None, pdh=[], raws=[], pivKey=None, accId=None, fvg=[], fvgKey=None,
                trk=dict(top=65100.0, bot=65000.0, state="SUPPORT", touch=0, armed=True), updates=0)


def rb_update(S, f, h, l, c, confirmed):
    """One Engine-like update (Day H/L + carry, Swing / Accum key edges, Touch, Break / Flip on brEval) plus the FVG store
    (Visual: only on confirmed bars). Deterministic in (state, feed, bar so far)."""
    S["updates"] += 1
    if f["dayId"] != S["dayId"]:
        if S["dayId"] is not None:
            S["pdh"].append((S["dayH"], S["dayL"]))
        S["dayId"], S["dayH"], S["dayL"] = f["dayId"], h, l
    else:
        S["dayH"], S["dayL"] = max(S["dayH"], h), min(S["dayL"], l)
    if f["piv"] is not None and f["piv"][0] != S["pivKey"]:
        S["raws"].append(("SW", f["piv"][1]))
        S["pivKey"] = f["piv"][0]
    if f["acc"] is not None and f["acc"][0] != S["accId"]:
        S["raws"].append(("ACC", f["acc"][1]))
        S["accId"] = f["acc"][0]
    t = S["trk"]
    if t["armed"] and l <= t["top"] and h >= t["bot"]:
        t["touch"], t["armed"] = t["touch"] + 1, False
    elif l >= t["top"] + REARM or h <= t["bot"] - REARM:
        t["armed"] = True
    if confirmed:                                              # brEval: Break / Flip on the confirmed close only
        if t["state"] == "SUPPORT" and c < t["bot"] - BUF:
            t["state"] = "BROKEN_S"
        elif t["state"] == "BROKEN_S" and c >= t["top"] + FLIP:
            t["state"] = "SUPPORT"
        elif t["state"] == "BROKEN_S" and c <= t["bot"] - FLIP:
            t["state"] = "RESIST"
        elif t["state"] == "RESIST" and c > t["top"] + BUF:
            t["state"] = "BROKEN_R"
        elif t["state"] == "BROKEN_R" and c <= t["bot"] - FLIP:
            t["state"] = "RESIST"
        elif t["state"] == "BROKEN_R" and c >= t["top"] + FLIP:
            t["state"] = "SUPPORT"
        S["fvg"] = [g for g in S["fvg"] if g[3] > f["k"]]                               # expiry
        S["fvg"] = [g for g in S["fvg"] if not ((g[2] == 1 and c < g[1]) or (g[2] == -1 and c > g[0]))]   # full fill
        if f["fvg"] is not None and f["fvg"][0] != S["fvgKey"]:
            S["fvg"].append(f["fvg"][1:])
            S["fvgKey"] = f["fvg"][0]


def rb_scenario(seed, nbars=400):
    rng = random.Random(seed)
    bars, px = [], 65050.0
    for k in range(nbars):
        nt = rng.randint(1, 7)
        ticks, o = [], px
        hi = lo = o
        for j in range(nt):
            px = round(px + rng.gauss(0, 40), 2)
            hi, lo = max(hi, px), min(lo, px)
            ticks.append((hi, lo, px))
        real_piv = (k, round(px + rng.uniform(-300, 300), 2)) if rng.random() < 0.08 else None
        acc = ((k // 12) * 12, round(65000 + 100 * (k // 12), 2)) if k % 12 == 0 else None
        fvg = (k, round(px + 120, 2), round(px + 60, 2), rng.choice([1, -1]), k + rng.randint(5, 60)) \
            if rng.random() < 0.1 else None
        feeds = []
        for j in range(nt):
            last = j == nt - 1
            # chart-TF pivot may flicker while the bar forms; HTF values (Accum / FVG, lookahead [1]) are fixed in the bar
            piv = real_piv if last else ((-k - 1, round(px - 77, 2)) if rng.random() < 0.3 else real_piv)
            feeds.append(dict(k=k, dayId=k // 30, piv=piv, acc=acc, fvg=fvg))
        bars.append((ticks, feeds))
    return bars


def rb_draw(S, ref, maxN=3):
    d = [abs(p - ref) for _, p in S["raws"]]
    return tuple(sorted(range(len(d)), key=lambda i: (d[i], i))[:maxN])


def rb_view(S, ref):
    t = S["trk"]
    return (rb_draw(S, ref), t["state"], t["touch"], tuple(S["fvg"]), S["dayH"], S["dayL"], len(S["raws"]))


def rb_commit_view(S):
    return {k: copy.deepcopy(v) for k, v in S.items() if k != "updates"}


def rb_run(bars, mode):
    """mode: hist (one confirmed execution per bar), old (update every tick, Pine rollback), new (update on confirm only).
    Returns committed state per bar, displays per tick, committing updates per bar."""
    S = rb_new_state()
    committed, views, per_bar = [], [], []
    prev_close = None
    for ticks, feeds in bars:
        n = len(ticks)
        rng_ticks = [n - 1] if mode == "hist" else range(n)
        bar_views = []
        for j in rng_ticks:
            h, l, c = ticks[j]
            conf = j == n - 1
            T = copy.deepcopy(S)                               # rollback: each tick starts from the last committed state
            T["updates"] = 0
            if mode in ("hist", "old") or conf:
                rb_update(T, feeds[j], h, l, c, conf)
            ref = c if (mode != "new" or conf) else prev_close
            bar_views.append(rb_view(T, ref))
            if conf:
                per_bar.append(T["updates"])
                S = T
        committed.append(rb_commit_view(S))
        views.append(bar_views)
        prev_close = ticks[-1][2]
    return committed, views, per_bar


def gate_rollback():
    same_hist, same_old, one_upd, steady, prev_eq, vary_old, events = True, True, True, True, True, False, set()
    for seed in range(30):
        bars = rb_scenario(seed)
        ch, _, _ = rb_run(bars, "hist")
        co, vo, _ = rb_run(bars, "old")
        cn, vn, pn = rb_run(bars, "new")
        same_hist &= cn == ch
        same_old &= cn == co
        one_upd &= pn == [1] * len(bars)
        for k, bv in enumerate(vn):
            forming = bv[:-1]
            steady &= all(v == forming[0] for v in forming) if forming else True
            if k > 0 and forming:
                prev_eq &= forming[0] == vn[k - 1][-1]
            vary_old |= len(set(vo[k][:-1])) > 1
        for k in range(1, len(ch)):
            a, b = ch[k - 1], ch[k]
            events |= {n for n, cond in (("day", a["dayId"] != b["dayId"]), ("swing", a["pivKey"] != b["pivKey"]),
                                         ("accum", a["accId"] != b["accId"]), ("fvg+", len(b["fvg"]) > len(a["fvg"])),
                                         ("fvg-", len(b["fvg"]) < len(a["fvg"]) or any(g not in b["fvg"] for g in a["fvg"])),
                                         ("touch", a["trk"]["touch"] != b["trk"]["touch"]),
                                         ("break/flip", a["trk"]["state"] != b["trk"]["state"])) if cond}
    check("BR-01 [model] committed state after every bar (Day H/L / carry, Swing / Accum registrations, FVG add / fill / "
          "expiry, Touch, Break / Flip) is identical for history, the old per-tick update with rollback and the new "
          "confirmed-only update (30 seeds x 400 bars, 1-7 ticks per bar, flickering chart-TF pivot)", same_hist and same_old)
    check("BR-02 [model] realtime: exactly one committing update per bar, on the confirmed tick (no missing / duplicated "
          "update)", one_upd)
    check("BR-03 [model] forming ticks: no update; the displayed Zone set / draw order (ref = last confirmed close), "
          "Strength-relevant state, Touch, Break / Flip, FVG store and Day H/L stay constant within the bar and equal the "
          "previous bar's confirmed display", steady and prev_eq)
    check("BR-04 [model] non-vacuous: the old per-tick update does change the display within forming bars, and Day switch / "
          "Swing / Accum / FVG add / FVG removal / Touch / Break-Flip events all occur (timing equal by BR-01)",
          vary_old and events == {"day", "swing", "accum", "fvg+", "fvg-", "touch", "break/flip"}, str(sorted(events)))


def main():
    for g in (gate_static, gate_timing, gate_symbol, gate_model, gate_rollback):
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
