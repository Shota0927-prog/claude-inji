"""MSL-1 fixtures — Max SL Distance filter on every Zone Strategy (tests/msl_build.py).

  MS : static on the delivered files — each == msl_build.build() and strips back to the a31e934 file byte for byte; every other
       Pine file unchanged; the changed test files differ by exactly their recorded / listed edits; every existing input and its
       default unchanged, exactly two new inputs (Enable OFF, the per-symbol limit); strategy() settings, imports, alert / label
       texts, the Auto JSON cfg unchanged; the only code changes are the input block and five one-line gates (each = the old line
       + ` and f_stSlOK(..)`: four); f_stSlOK is pure (no state / history / request) and its inputs are used nowhere else; the gate
       arguments are the reference / SL of the order it guards; every strategy.entry, confirmed alert / label, Auto ENTRY / PROV
       and provisional alert / label sits under a gated condition; no gate inside candidate selection (no fallback); FX unit ==
       the file's own pip constant; eager-evaluation lint unchanged
  MM : models — f_stSlOK ported from the Pine text: OFF = true for every input (so every gated condition == the old one); ON
       boundaries per symbol (below allowed, exact limit / above blocked, Long / Short, float edges, na / invalid blocked); the
       decision model of each order point (Current A / B / C / D, SATS pull-side / immediate, provisional / confirmed, Long /
       Short / Both): OFF == old, ON == old and distance < limit, a blocked top candidate is never replaced
  MU : mutations caught

Evidence class: PINE_NOT_VERIFIED (TradingView compile / Strategy Tester / alert delivery are not reproduced here).
"""
import os
import random
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import msl_build as mb           # noqa: E402
import eu_sim as es              # noqa: E402
import fvg_re10045_sim as fr     # noqa: E402

ROOT = mb.ROOT
B = mb.BASE_REV
raw = lambda p: open(os.path.join(ROOT, p), encoding="utf-8").read()
code_only, input_decls, input_values = es.code_only, es.input_decls, es.input_values
CUR = {p: __import__("bel_build").unapply(p, raw(p)) for p in mb.FILES}     # the later BEL-1 layer reverted exactly (pinned in bel_sim)
OLD = {p: mb.show(B, p) for p in mb.FILES}
RESULTS = []
NEW_INPUTS = ("stMaxSlOn", "stMaxSl")
GATES = {"pull": "f_stSlOK(close, pwSL0)", "now": "f_stSlOK(close, pSL)", "cur": "f_stSlOK(ref, pSL)", "prov": "f_stSlOK(pPx, pSL)"}
# test files MSL-1 changes, each by its exact edit (the Pine files by msl_build.strip)
TEST_EDITS = {
    "tests/xa_build.py": [mb.XA_HOOK],
    "tests/cad_adapt.py": [
        ('             "tests/pf_model.py", "tests/pf_sim.py", "XAU_PERF_XA24_ja.md")                  # new in the later layer XA-24 (Gold run-time reduction)\n',
         '             "tests/pf_model.py", "tests/pf_sim.py", "XAU_PERF_XA24_ja.md",                  # new in the later layer XA-24 (Gold run-time reduction)\n'
         '             "tests/msl_build.py", "tests/msl_sim.py")                                       # new in the later layer MSL-1 (Max SL Distance filter)\n'),
        ("gate_xa5, gate_xa6):\\n'\n                       '        try:\\n')]}\n",
         "gate_xa5, gate_xa6):\\n'\n                       '        try:\\n')]}\n"
         'LATER["tests/xa_build.py"] = LATER["tests/xa_build.py"] + [__import__("msl_build").XA_HOOK]     # later layer MSL-1: its exact xa_build edit\n')],
    "tests/au_build.py": [
        ('             "tests/pf_model.py", "tests/pf_sim.py", "XAU_PERF_XA24_ja.md")\n',
         '             "tests/pf_model.py", "tests/pf_sim.py", "XAU_PERF_XA24_ja.md",\n'
         '             # later layer MSL-1 (Max SL Distance filter): its generator / fixture (the Pine files are accepted through msl_build.unapply)\n'
         '             "tests/msl_build.py", "tests/msl_sim.py")\n')],
    "tests/xal_build.py": [
        ('    return open(os.path.join(ROOT, LONG_PATH), encoding="utf-8").read() == build()\n',
         '    return __import__("msl_build").unapply(LONG_PATH, open(os.path.join(ROOT, LONG_PATH), encoding="utf-8").read()) == build()   # later MSL-1: exact\n'),
        ('    """reverse XA-24 when present (all or nothing) and XA-23 (-> the Long Strategy of d05f8c9); None when not exact."""\n    if text is not None',
         '    """reverse XA-24 when present (all or nothing) and XA-23 (-> the Long Strategy of d05f8c9); None when not exact.\n'
         '    The later MSL-1 layer (msl_build) is reverted first when present, exactly."""\n'
         '    text = __import__("msl_build").unapply(LONG_PATH, text)\n    if text is not None')],
}
_RAW_OLD = 'raw = lambda p: open(os.path.join(ROOT, p), encoding="utf-8").read()\n'
_RAW_NEW = ('raw = lambda p: __import__("msl_build").unapply(p, open(os.path.join(ROOT, p), encoding="utf-8").read())'
            '   # later MSL-1 reverted exactly (pinned in msl_sim)\n')
for _f in ("au_sim", "btl_sim", "pf_sim", "xac_sim", "xal_sim"):
    TEST_EDITS[f"tests/{_f}.py"] = [(_RAW_OLD, _RAW_NEW)]


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


def git(*a):
    return subprocess.run(["git", "-C", ROOT] + list(a), capture_output=True, text=True).stdout


def revert(text, pairs):
    out = text
    for a, b in reversed(pairs):
        if out.count(b) != 1:
            return None
        out = out.replace(b, a)
    return out


def block(path):
    return mb.edits(path)[0][2].replace('var string G_STA = "03 · Strategy Alerts"\n', "")


def changed_lines(old, new):
    """(removed, added) code lines between two texts (difflib on the full text)."""
    import difflib
    rem, add = [], []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, old.split("\n"), new.split("\n"), autojunk=False).get_opcodes():
        if op != "equal":
            rem += old.split("\n")[i1:i2]
            add += new.split("\n")[j1:j2]
    return rem, add


def enclosing_ifs(lines, i):
    """the `if` / `else if` header lines that enclose line i (by indentation); None inside a function definition (its call
    sites are the targets instead)."""
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


# ---- f_stSlOK ported from the Pine text ----------------------------------------------------------------------------------
def port(text):
    m = re.search(r"\nf_stSlOK\(float ref, float sl\) =>\n    (.+)\n", text)
    expr = m.group(1)
    py = (expr.replace("math.abs(", "abs(").replace("not na(ref)", "(ref is not None)").replace("not na(sl)", "(sl is not None)"))
    unit = float(re.search(r"^float ST_MAXSL_UNIT = ([\d.]+)", text, re.M).group(1))
    dflt = float(re.search(r'^stMaxSl = input\.float\(([\d.]+),', text, re.M).group(1))
    fn = eval("lambda ref, sl, stMaxSlOn, stMaxSl, ST_MAXSL_UNIT: " + py)     # noqa: S307 (own repository text)
    return (lambda ref, sl, on, mx=dflt: fn(ref, sl, on, mx, unit)), unit, dflt, expr


def gate_static():
    others = [p for p in os.listdir(ROOT) if p.endswith(".pine") and p not in mb.FILES]
    others += [os.path.join("automation/xau_short/pine", p) for p in os.listdir(os.path.join(ROOT, "automation/xau_short/pine"))
               if os.path.join("automation/xau_short/pine", p) not in mb.FILES]
    check("MS-01 the eight Strategies == msl_build.build() and strip back to the a31e934 files byte for byte (unapply too, idempotent "
          "on the old text); every other Pine file (Engines, Visuals, the other Strategies / harnesses) unchanged vs a31e934",
          all(CUR[p] == mb.build(p) and mb.strip(p, CUR[p]) == OLD[p] and mb.unapply(p, CUR[p]) == OLD[p] and mb.unapply(p, OLD[p]) == OLD[p]
              for p in mb.FILES)
          and not [p for p in others if os.path.exists(os.path.join(ROOT, p)) and raw(p) != mb.show(B, p)])
    st = git("status", "--porcelain").split("\n")
    mod = set(git("diff", "--name-only", B, "--").split()) | {l[3:] for l in st if l.startswith("??")}
    mod -= {"tests/__pycache__/"}
    bad = sorted(m for m in mod if m not in mb.FILES and m not in mb.NEW_TESTS and m not in __import__("bel_build").NEW_TESTS
                 and m not in __import__("gja_build").NEW_TESTS and m not in __import__("uja_build").NEW_TESTS
                 and not (m in TEST_EDITS and revert(__import__("bel_build").unadapt(m, raw(m)), TEST_EDITS[m]) == mb.show(B, m)))
    check("MS-02 vs a31e934 only the eight Strategies, the new msl_build / msl_sim and the listed test files change; each test file by "
          "exactly its recorded edit (xa_build: the appended MSL-1 hook, = cad_adapt LATER; cad_adapt / au_build: the new-file lists; "
          "xal_build / au / btl / pf / xac / xal sims: the later-layer revert)",
          not bad and set(mb.FILES) <= mod, str(bad))
    bad_in = {}
    for p in mb.FILES:
        ic, io = input_decls(CUR[p]), input_decls(OLD[p])
        if {k: v for k, v in ic.items() if k not in NEW_INPUTS} != io or set(ic) - set(io) != set(NEW_INPUTS):
            bad_in[p] = "decls"
        sym, unit, dflt, ul, step, prov = mb.CFG[p]
        iv = input_values(CUR[p])
        if iv.get("stMaxSlOn") != "false" or iv.get("stMaxSl") != dflt:
            bad_in[p] = (iv.get("stMaxSlOn"), iv.get("stMaxSl"))
        if '"Enable Max SL Distance"' not in ic["stMaxSlOn"] or f'Max SL Distance ({ul})"' not in ic["stMaxSl"]:
            bad_in[p] = "names"
        if prov != ("[暫定] Max SL Distance" in ic["stMaxSl"]):
            bad_in[p] = "provisional tag"
    lim = {p: input_values(CUR[p])["stMaxSl"] for p in mb.FILES}
    check("MS-03 every existing input declaration (name, default, options, tooltip, group) unchanged; exactly two new inputs: "
          "'Enable Max SL Distance' default OFF and 'Max SL Distance' (Gold $ 40.0; BTC USD / FX pips marked [暫定])",
          not bad_in and all(lim[p] == "40.0" for p in mb.GOLD) and lim["ZoneStrategyBTCUSD.pine"] == "1000.0"
          and lim["ZoneStrategyUSDJPY.pine"] == "40.0" and lim["ZoneStrategyEURUSD.pine"] == "25.0"
          and lim["ZoneStrategyGBPJPY.pine"] == "60.0" and lim["ZoneStrategyGBPUSD.pine"] == "30.0", str(bad_in))
    bad_lines = {}
    for p in mb.FILES:
        rem, add = changed_lines(OLD[p], CUR[p])
        blk = block(p).split("\n")[:-1]     # the block lines incl. its closing blank line
        add_g = [l for l in add if l not in blk]
        pairs = [(o, n) for o, n in zip(rem, add_g)]
        ok = (len(rem) == 4 and len(add_g) == 4 and all(n.startswith(o + " and f_stSlOK(") and n.endswith("     // MSL-1") or
                                                        (" and f_stSlOK(pPx, pSL)" in n and n.replace(" and f_stSlOK(pPx, pSL)", "").replace("     // MSL-1", "") == o)
                                                        for o, n in pairs)
              and [l for l in add if l in blk] == blk)
        if not ok:
            bad_lines[p] = (rem, add_g)
    check("MS-04 the only changes: the inserted input / helper block (before '03 · Strategy Alerts') and four one-line gates, each "
          "= the old line + ` and f_stSlOK(..)` (pull-side order, immediate order, Current order, provisional output); nothing deleted",
          not bad_lines, str(bad_lines)[:600])
    pure = {}
    for p in mb.FILES:
        f = es.func(CUR[p], "f_stSlOK(float ref, float sl) =>")
        body = f.split("\n", 1)[1]
        c = code_only(CUR[p])
        uses = {n: len(re.findall(r"\b" + n + r"\b", c)) for n in ("stMaxSlOn", "stMaxSl", "ST_MAXSL_UNIT", "G_STX", "f_stSlOK")}
        if (re.search(r":=|\[|\bta\.|request\.|\bvar\b|varip|strategy\.|alert\(|label\.", body) or
                uses != {"stMaxSlOn": 2, "stMaxSl": 2, "ST_MAXSL_UNIT": 2, "G_STX": 3, "f_stSlOK": 5}):
            pure[p] = uses
    check("MS-05 f_stSlOK is pure (no assignment, history index, ta / request / strategy / alert / label call); its inputs and unit "
          "are used only in it; f_stSlOK = the definition + exactly four uses (so OFF cannot change any other state)",
          not pure, str(pure))
    eq = {}
    for p in mb.FILES:
        c, o = CUR[p], OLD[p]
        same = (es.seg(c, "strategy(", "import ") == es.seg(o, "strategy(", "import ")
                and re.findall(r"^import .*$", c, re.M) == re.findall(r"^import .*$", o, re.M)
                and re.findall(r"alert\(.*$", c, re.M) == re.findall(r"alert\(.*$", o, re.M)
                and re.findall(r"label\.\w+\(.*$", c, re.M) == re.findall(r"label\.\w+\(.*$", o, re.M)
                and re.findall(r"strategy\.(?:entry|exit|close|cancel|close_all)\(.*$", c, re.M)
                == re.findall(r"strategy\.(?:entry|exit|close|cancel|close_all)\(.*$", o, re.M)
                and re.findall(r"^var string auCfg.*$", c, re.M) == re.findall(r"^var string auCfg.*$", o, re.M)
                and re.findall(r"f_auEmit\(.*$", c, re.M) == re.findall(r"f_auEmit\(.*$", o, re.M)
                and "stMaxSl" not in "".join(re.findall(r"^var string auCfg.*$", c, re.M)))
        for h in ("f_stQty(int side, float ref, float sl) =>", "f_stTp(", "f_stAlertMsg(", "f_stProvEval() =>", "f_stBetter(",
                  "f_satProvEval(", "f_beTrig(", "f_stConfAlert(", "f_stLblText(", "f_auEmit("):
            if ("\n" + h) in o:
                same = same and es.func(c, h) == es.func(o, h)
        if not same:
            eq[p] = False
    check("MS-06 unchanged: strategy() settings, imports, every alert / label / strategy.entry / exit / close / cancel call line, "
          "f_stQty / f_stTp / f_stAlertMsg / f_stProvEval / f_stBetter / f_satProvEval / f_beTrig / f_stConfAlert / f_stLblText, the "
          "Auto JSON cfg strings (no new field) and every f_auEmit call",
          not eq, str(eq))
    place = {}
    for p in mb.FILES:
        L = CUR[p].split("\n")
        tg = [i for i, l in enumerate(L) if "=>" not in l and not l.lstrip().startswith("//") and
              (re.search(r"strategy\.entry\(|f_stConfAlert\(|f_auEmit\(\"(ENTRY|PROV)\"", l)
               or re.search(r'alert\(f_stAlertMsg\("(確定|仮)"', l) or re.search(r'label\.new\(.*f_stAlertMsg\("確定"', l)
               or re.search(r'label\.set_text\(stProvLbl, f_stAlertMsg\("仮"', l))]
        pvok = re.search(r"^bool  stPvOK   = .*$", CUR[p], re.M)
        tg = [i for i in tg if enclosing_ifs(L, i) is not None]
        miss = [L[i].strip()[:60] for i in tg
                if not any("f_stSlOK(" in h or ("stPvOK" in h and pvok and "f_stSlOK(pPx, pSL)" in pvok.group(0))
                           for h in enclosing_ifs(L, i))]
        n_entry = sum(1 for i in tg if "strategy.entry(" in L[i])
        if miss or n_entry != 4:
            place[p] = (miss, n_entry)
    check("MS-07 every strategy.entry (4 per file), confirmed alert / label (f_stConfAlert on Gold), Auto ENTRY / PROV and provisional "
          "alert / label sits under a condition carrying f_stSlOK (or stPvOK, which carries it)",
          not place, str(place))
    args = {}
    for p in mb.FILES:
        c = CUR[p]
        ok = (c.count("if not na(q) and " + GATES["pull"]) == 1 and c.count("and not na(nQty) and " + GATES["now"]) == 1
              and c.count("else if not skipRef and not na(pQty) and " + GATES["cur"]) == 1 and c.count(GATES["prov"]) == 1
              and c.count("            float  ref = stModeA ? pL : close\n") == 1
              and c.count("                float q = f_stQty(pwSide, close, pwSL0)\n                if not na(q) and") == 1
              and "strategy.entry(oEid, pwSide == 1 ? strategy.long : strategy.short, qty = q)" in c
              and "float nQty = f_stQty(side, close, pSL)" in c and "float  pQty = f_stQty(side, ref, pSL)" in c)
        if not ok:
            args[p] = False
    check("MS-08 gate arguments = the order's own reference / SL: pull-side (close, SL0) like f_stQty(pwSide, close, pwSL0); immediate "
          "(close, pSL) like nQty; Current (ref, pSL) with ref = stModeA ? limit : close like pQty; provisional (pPx, pSL) = the values "
          "the provisional alert / label shows",
          not args, str(args))
    nofb = {}
    for p in mb.FILES:
        c = CUR[p]
        sel = [es.func(c, h) for h in ("f_stProvEval() =>", "f_stBetter(") if ("\n" + h) in c]
        i0 = c.index("        int side = 0\n        if bkL >= 0 and bkS >= 0")     # the confirmed selection
        loop = c[c.rindex("        int   bkL = -1\n", 0, i0):i0]                    # the confirmed candidate loops before it
        if any("f_stSlOK" in s for s in sel) or "f_stSlOK" in loop:
            nofb[p] = True
    check("MS-09 no fallback: f_stSlOK is not used in candidate collection / priority (f_stProvEval, f_stBetter, the confirmed "
          "candidate loops); it gates only after the existing selection, so a blocked top candidate is not replaced",
          not nofb, str(nofb))
    pip = {}
    for p in mb.FILES:
        sym, unit, dflt, ul, step, prov = mb.CFG[p]
        c = CUR[p]
        u = re.search(r"^float ST_MAXSL_UNIT = ([\d.]+)", c, re.M).group(1)
        own = re.search(r"^float ST_PIP = ([\d.]+)", c, re.M)
        nu = re.search(r"^float SX_NEAR_UNIT = ([\d.]+)", c, re.M)
        exp = {"USDJPY": "0.01", "GBPJPY": "0.01", "EURUSD": "0.0001", "GBPUSD": "0.0001", "XAUUSD": "1.0", "BTCUSD": "1.0"}[sym]
        if u != exp or (ul == "pips" and (own is None or own.group(1) != u or nu is None or nu.group(1) != u)) or \
                (sym == "BTCUSD" and nu.group(1) != u):
            pip[p] = (u, own and own.group(1), nu and nu.group(1))
    check("MS-10 unit: FX pips = the file's own ST_PIP / SX_NEAR_UNIT (JPY pairs 0.01, EURUSD / GBPUSD 0.0001); XAUUSD $ / BTCUSD "
          "USD = 1.0 price unit (BTC = its SX_NEAR_UNIT)",
          not pip, str(pip))
    lint = {p: (fr.lint_eager_guards(code_only(CUR[p])), fr.lint_eager_guards(code_only(OLD[p]))) for p in mb.FILES}
    check("MS-11 eager-evaluation lint (RE10045 guard / index pattern): no new finding on any Strategy",
          all(a == b for a, b in lint.values()), str({p: v for p, v in lint.items() if v[0] != v[1]}))


# ---- models ---------------------------------------------------------------------------------------------------------------
def gate_model():
    rnd = random.Random(20261029)
    ports = {p: port(CUR[p]) for p in mb.FILES}
    off_bad = []
    for p, (ok, unit, dflt, expr) in ports.items():
        for _ in range(4000):
            ref = rnd.choice([None, rnd.uniform(0.5, 120000.0)])
            sl = rnd.choice([None, rnd.uniform(0.5, 120000.0)])
            if ok(ref, sl, False, rnd.choice([dflt, 0.0, 1e-9, 1e9])) is not True:
                off_bad.append((p, ref, sl))
    check("MM-01 OFF: the ported f_stSlOK is true for every input (random / na / any limit), so each gated condition `X and "
          "f_stSlOK(..)` == X: trades, entries, SL / TP, alerts and labels identical to a31e934 with the filter OFF",
          not off_bad, str(off_bad[:3]))
    xau = ports["ZoneStrategyXAU.pine"][0]
    cases = []
    for side in (1, -1):     # Long: SL below the reference; Short: SL above
        for d, want in ((39.99, True), (40.00, False), (40.01, False), (50.00, False), (0.01, True)):
            ref = 2650.00
            sl = round(ref - side * d, 2)
            cases.append(((side, d), xau(ref, sl, True), want))
    check("MM-02 XAUUSD limit 40.0 ON (Short / Long / Auto, same text): 39.99 allowed; 40.00, 40.01, 50.00 blocked; Long and Short",
          all(g == w for _, g, w in cases) and all(ports[p][3] == ports["ZoneStrategyXAU.pine"][3] for p in mb.GOLD), str(cases))
    fx = []
    for p, ref, lim in (("ZoneStrategyUSDJPY.pine", 150.123, 40.0), ("ZoneStrategyGBPJPY.pine", 195.456, 60.0),
                        ("ZoneStrategyEURUSD.pine", 1.08765, 25.0), ("ZoneStrategyGBPUSD.pine", 1.27654, 30.0)):
        ok, unit, dflt, _ = ports[p]
        dec = 3 if unit == 0.01 else 5
        for side in (1, -1):
            for pips, want in ((lim - 0.1, True), (lim, False), (lim + 0.1, False), (lim * 2, False), (1.0, True)):
                sl = round(ref - side * pips * unit, dec)
                fx.append((p[12:18], side, pips, ok(ref, sl, True), want, dflt == lim))
    check("MM-03 FX pips ON (provisional limits USDJPY 40 / GBPJPY 60 / EURUSD 25 / GBPUSD 30 pips): 0.1 pip below allowed, exact "
          "limit (prices on the 0.001 / 0.00001 grid, float error absorbed) and above blocked; Long and Short",
          all(g == w and d for *_, g, w, d in fx), str([x for x in fx if x[3] != x[4] or not x[5]][:4]))
    btc = ports["ZoneStrategyBTCUSD.pine"][0]
    bc = [(btc(65000.00, 65000.00 - s * d, True), w) for s in (1, -1) for d, w in ((999.99, True), (1000.00, False), (1000.01, False))]
    check("MM-04 BTCUSD USD ON (provisional 1000): 999.99 allowed, 1000.00 / 1000.01 blocked, Long and Short",
          all(g == w for g, w in bc), str(bc))
    inv = [ok(None, 100.0, True) or ok(100.0, None, True) or ok(None, None, True) for ok, *_ in ports.values()]
    custom = [ports["ZoneStrategyXAU.pine"][0](2000.0, 1990.0, True, 10.0), ports["ZoneStrategyXAU.pine"][0](2000.0, 1990.01, True, 10.0)]
    check("MM-05 ON with an invalid reference / SL (na) -> blocked on every Strategy (the old f_stQty already refuses distance <= 0); "
          "the user's limit is used (10.0: 10.00 blocked, 9.99 allowed)",
          not any(inv) and custom == [False, True], str((inv, custom)))

    # decision model of the five gated points (the old condition X is abstract; the gate is applied as in the Pine line)
    def decide(cands, mode, dirn, path, on, lim, ok):
        """cands: [(side, priority, ref_close, limit_px, sl)] already satisfying the old conditions; the old selection = the best
        priority per side, Both with one per side -> A: nearer limit (tie: none), B / C / D: none. Returns the order (side, ref, sl)
        or None. path: 'cur' / 'pull' / 'now' / 'prov' (prov uses the same reference the confirmed point uses)."""
        best = {}
        for c in cands:
            if (c[0] == 1 and dirn == "Short Only") or (c[0] == -1 and dirn == "Long Only"):
                continue
            if c[0] not in best or c[1] > best[c[0]][1]:
                best[c[0]] = c
        if len(best) == 2:
            if mode != "A":
                return None
            dl, ds = abs(best[1][2] - best[1][3]), abs(best[-1][2] - best[-1][3])
            if dl == ds:
                return None
            pick = best[1] if dl < ds else best[-1]
        elif best:
            pick = list(best.values())[0]
        else:
            return None
        ref = pick[3] if (mode == "A" and path in ("cur", "prov")) else pick[2]
        if not ok(ref, pick[4], on, lim):
            return None
        return (pick[0], ref, pick[4])

    ok = ports["ZoneStrategyXAU.pine"][0]
    bad = []
    for trial in range(3000):
        n = rnd.randint(1, 4)
        cands = []
        for k in range(n):
            side = rnd.choice([1, -1])
            close = round(rnd.uniform(2600, 2700), 2)
            lim_px = round(close - side * rnd.uniform(0, 5), 2)
            sl = round(close - side * rnd.choice([rnd.uniform(1, 80), 40.0, 39.99, 40.01]), 2)
            cands.append((side, rnd.random(), close, lim_px, sl))
        for mode in ("A", "B", "C", "D"):
            for dirn in ("Long Only", "Short Only", "Both"):
                for path in ("cur", "pull", "now", "prov"):
                    old = decide(cands, mode, dirn, path, False, 40.0, lambda r, s, o, m: True)
                    off = decide(cands, mode, dirn, path, False, 40.0, ok)
                    on = decide(cands, mode, dirn, path, True, 40.0, ok)
                    if off != old:
                        bad.append(("off", mode, dirn, path))
                    if old is None and on is not None:
                        bad.append(("more", mode, dirn, path))
                    if old is not None and (on is not None) != (abs(old[1] - old[2]) < 40.0 - 1e-6):
                        bad.append(("on", mode, dirn, path, old))
                    if on is not None and on != old:
                        bad.append(("fallback", mode, dirn, path))
    check("MM-06 decision model, Entry Mode A / B / C / D x Long Only / Short Only / Both x Current / SATS pull-side / SATS immediate "
          "/ provisional (3000 random candidate sets incl. 39.99 / 40.00 / 40.01): OFF == old; ON == old only when |ref - SL| < 40 "
          "(ref: A limit / otherwise the close), else no order; never an order the old code would not send, never another candidate",
          not bad, str(bad[:4]))
    # provisional == confirmed: the provisional reference / SL are the same values the confirmed point gates on
    pv = []
    for p in mb.FILES:
        c = CUR[p]
        pv.append(("pPx   := eS" in c or "pPx   := e0" in c) and "pSL   := l0" in c and "ePx := stModeA ? (side == 1 ? bpL : bpS) : close" in c
                  and "sl  := side == 1 ? c.bot - stBuffer : c.top + stBuffer" in c
                  and "float  pSL = side == 1 ? c.bot - stBuffer : c.top + stBuffer" in c)
    check("MM-07 provisional and confirmed use the same reference / SL (f_stProvEval: A limit / otherwise close, SL = Zone edge -+ "
          "SL Buffer = the confirmed pSL / ref; SATS provisional: close / SL0 = the confirmed pull / immediate values)", all(pv), str(pv))


def gate_mutation():
    p = "ZoneStrategyXAU.pine"
    c = CUR[p]
    muts = [c.replace("< stMaxSl - 1e-6", "<= stMaxSl"), c.replace("not stMaxSlOn or ", ""),
            c.replace("if not na(q) and f_stSlOK(close, pwSL0)", "if not na(q)"),
            c.replace("and not na(nQty) and f_stSlOK(close, pSL)", "and not na(nQty) and f_stSlOK(ref, pSL)"),
            c.replace("and not na(pQty) and f_stSlOK(ref, pSL)", "and not na(pQty)"),
            c.replace("and f_stSlOK(pPx, pSL) and not array.includes", "and not array.includes"),
            c.replace('stMaxSlOn = input.bool(false,', 'stMaxSlOn = input.bool(true,'),
            c.replace('stMaxSl = input.float(40.0,', 'stMaxSl = input.float(45.0,')]
    caught = [m != c and mb.strip(p, m) is None for m in muts]
    ok0 = port(muts[0])[0]
    check("MU-01 mutations (<= instead of <, OFF not honoured, a gate dropped / wrong reference, provisional gate dropped, default ON, "
          "other limit) do not strip back to a31e934; the `<=` port allows the exact limit (so MM-02 would catch it)",
          all(caught) and ok0(2650.0, 2610.0, True) is True, str(caught))


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
    print(f"\n{len(RESULTS) - fails}/{len(RESULTS)} passed  [PINE_NOT_VERIFIED: exact build / static / Python models]")
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
