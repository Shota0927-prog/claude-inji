"""CAD-1 fixtures — confirmed Entry alert at most once per 5M bar in the GBPJPY-lineage Strategies (USDJPY UJ-5 rolled out).

Runs on the delivered files (with the guard):
  CD : static — ZoneStrategyGBPJPY / EURUSD / GBPUSD / BTCUSD == cad_build.apply(their generator output) (the generators
       re-apply the guard when writing, so a rebuild keeps it); cad_build.strip gives the 867ff7e files byte for byte; the
       code delta is exactly the varip declaration, the guard condition and the key assignment (one each); the guard sits in
       the order branch after strategy.entry / exit, wraps only alert(), keeps the text and alert.freq_all; strategy.*
       calls, f_stAlertMsg, the provisional block (stProvBar), labels, strategy() unchanged; the guard equals USDJPY UJ-5;
       USDJPY unchanged since 867ff7e; every other Pine file byte-identical; classification of the other alert scripts
  CM : model of the guarded branch (var rolled back per realtime execution, varip kept, alert() side effects kept) for
       each file's source pattern: the user's cases (1)-(11)
  CU : mutations — guard removed / var key / reset each tick / key set by the provisional alert / guard around the order

The model checks the guard when the confirmed branch is reached again on the same bar; it is not evidence of what made
TradingView reach it twice. Evidence class: PINE_NOT_VERIFIED (compile, alert delivery, Strategy Tester external).
"""
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cad_build as cb           # noqa: E402
import gbs_build as gs           # noqa: E402
import eu_build as eb            # noqa: E402
import gu_build as gb            # noqa: E402
import btcs_build as sb          # noqa: E402
import eu_sim as es              # noqa: E402

ROOT = cb.ROOT
PREV = "867ff7e"
rd = lambda p: __import__("sx_build").unapply(p, open(os.path.join(ROOT, p), encoding="utf-8").read())   # SX-1 reverted (pinned in sxs_sim)
git = lambda *a: subprocess.run(["git", "-C", ROOT] + list(a), capture_output=True, text=True).stdout
code_only, func = es.code_only, es.func
GEN = {"ZoneStrategyGBPJPY.pine": gs.build, "ZoneStrategyEURUSD.pine": eb.build_strategy,
       "ZoneStrategyGBPUSD.pine": gb.build_strategy, "ZoneStrategyBTCUSD.pine": sb.build}
F = {p: rd(p) for p in cb.FILES}
F0 = {p: git("show", f"{PREV}:{p}") for p in cb.FILES}
UJ = rd("ZoneStrategyUSDJPY.pine")
DECL = "varip int  stConfBar = na"
COND = "if stAlertConf and (na(stConfBar) or stConfBar != time)"
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


def block(t, start, end):
    i = t.index(start)
    return t[i:t.index(end, i)]


def strip_comment(l):
    return re.sub(r"\s+//.*$", "", l).rstrip()


def gate_static():
    check("CD-01 the four Strategies == cad_build.apply(generator output) (gbs_build / eu_build / gu_build / btcs_build write "
          "them that way, so regeneration keeps the guard); cad_build.strip gives the 867ff7e file byte for byte",
          all(F[p] == cb.apply(GEN[p]()) and cb.strip(F[p]) == F0[p] and F0[p] for p in cb.FILES),
          str([p for p in cb.FILES if not (F[p] == cb.apply(GEN[p]()) and cb.strip(F[p]) == F0[p])]))
    bad = {}
    for p in cb.FILES:
        ch = sorted(strip_comment(l) for l in es.changed_code(F0[p], F[p]) if l)
        exp = sorted(["if stAlertConf", COND, "stConfBar := time", DECL])
        if ch != exp or code_only(F[p]).count(DECL) != 1 or code_only(F[p]).count(COND) != 1 or code_only(F[p]).count("stConfBar") != 4:
            bad[p] = ch
    check("CD-02 code delta per file exactly: one varip declaration (global, beside the order state), the guard condition "
          "replacing 'if stAlertConf', one 'stConfBar := time'; no second declaration / condition / assignment", not bad, str(bad))
    pos, same = [], []
    strat = lambda t: sorted(re.findall(r"strategy\.(?:entry|exit|close|cancel)\(.*$", code_only(t), re.M))
    al = lambda t: [l.strip() for l in re.findall(r"^\s*alert\(.*$", t, re.M)]
    for p in cb.FILES:
        t = F[p]
        br = block(t, "            if not skipRef and not na(pQty)\n", "    stPrev := cur")
        g = br.index(COND)
        pos.append(br.index("strategy.exit(oXid, oEid, stop = oSL)") < g < br.index("if stLblConf")
                   and br[g:].split("\n")[1].strip() == "stConfBar := time"
                   and br[g:].split("\n")[2].strip().startswith('alert(f_stAlertMsg("確定"') and br[g:].split("\n")[2].strip().endswith("alert.freq_all)")
                   and "stConfBar" not in t[t.index("varip int stProvBar = na"):]
                   and t.index(DECL) < t.index("if is5mChart and barstate.isconfirmed\n    // (1)"))
        same.append(strat(t) == strat(F0[p]) and al(t) == al(F0[p])
                    and func(t, "f_stAlertMsg(") == func(F0[p], "f_stAlertMsg(")
                    and t[t.index("varip int stProvBar = na"):] == F0[p][F0[p].index("varip int stProvBar = na"):]
                    and block(t, "                if stLblConf", "    stPrev := cur") == block(F0[p], "                if stLblConf", "    stPrev := cur")
                    and t[t.index("strategy("):t.index("import ")] == F0[p][F0[p].index("strategy("):F0[p].index("import ")]
                    and all(func(t, h) == func(F0[p], h) for h in ("f_stTp(", "f_stQty(int side, float ref, float sl) =>", "f_stProvEval() =>")))
    check("CD-03 placement: in the confirmed-bar order branch (after strategy.entry / strategy.exit, before the confirmed label), "
          "the key set right before alert(), alert text and alert.freq_all kept; the provisional block (stProvBar) never reads "
          "or writes stConfBar; the key is declared once at global scope and never reset", all(pos), str(pos))
    check("CD-04 unchanged: every strategy.entry / exit / close / cancel call, both alert() lines, f_stAlertMsg, f_stTp / "
          "f_stQty / f_stProvEval, the provisional block, the confirmed label block, strategy() options", all(same), str(same))
    ujg = [strip_comment(l).strip() for l in UJ.split("\n") if "stConfBar" in l and not l.lstrip().startswith("//")]
    cdg = [[strip_comment(l).strip() for l in F[p].split("\n") if "stConfBar" in l and not l.lstrip().startswith("//")] for p in cb.FILES]
    check("CD-05 the guard equals USDJPY UJ-5 (same declaration, condition and assignment); USDJPY Strategy unchanged since "
          "867ff7e", all(c == ujg for c in cdg) and len(ujg) == 3 and UJ == git("show", f"{PREV}:ZoneStrategyUSDJPY.pine"),
          str((ujg, cdg[0])))
    others = [p for p in os.listdir(ROOT) if p.endswith(".pine") and p not in cb.FILES and not __import__("xal_build").ok(p)]   # XL-1 Long: exact
    changed = [p for p in others if rd(p) != git("show", f"{PREV}:{p}") and not __import__("cad_adapt").later_pine_ok(p, PREV)]   # later layers: exact
    cls = {"ZoneStrategyXAU.pine": "alert(" not in code_only(rd("ZoneStrategyXAU.pine")),
           "us_trend_strategy.pine": "alert.freq_all" not in rd("us_trend_strategy.pine"),
           "PointMasterFvgAbsRebound.pine": "varip int lastRealtimePhaseCode = na" in rd("PointMasterFvgAbsRebound.pine")}
    check("CD-06 every other Pine file byte-identical to 867ff7e (USDJPY, XAU, Practical LONG / SHORT, FVG strategies, harnesses, "
          "indicators, Visuals, Engines); XAU has no alert (none added), us_trend only provisional freq_once_per_bar alerts, "
          "PointMaster an indicator with its own varip guard", not changed and all(cls.values()), str((changed, cls)))
    mod = set(git("diff", "--name-only", PREV, "--").split()) | {l[3:] for l in git("status", "--porcelain").split("\n") if l.startswith("??")}
    mod -= {"tests/__pycache__/"}
    mod = {m for m in mod if not __import__("xal_build").ok(m)}     # XL-1 (Gold Long, new): exact
    pine = {m for m in mod if m.endswith(".pine")}
    rec = __import__("cad_adapt")
    check("CD-07 vs 867ff7e the changed Pine files are exactly the four Strategies; every changed test / generator is either new "
          "in CAD-1 or carries exactly its recorded CAD-1 edits (cad_adapt: reverting them gives the 867ff7e text)",
          pine - {m for m in pine if __import__("cad_adapt").later_pine_ok(m, PREV)} == set(cb.FILES) and all(m in rec.NEW_FILES or rec.unadapt(m, rd(m)) == git("show", f"{PREV}:{m}") for m in mod - pine),
          str(sorted(m for m in mod - pine if not (m in rec.NEW_FILES or rec.unadapt(m, rd(m)) == git("show", f"{PREV}:{m}")))))


# ---- model of the guarded branch ----------------------------------------------------------------------------------------
def pattern_ok(t):
    br = block(t, "            if not skipRef and not na(pQty)\n", "    stPrev := cur")
    return (DECL in t and COND in br and "\n                    stConfBar := time\n                    alert(" in br)


class Strat:
    """one Strategy instance: committed var state + varip key; each execute() starts from the committed var state."""

    def __init__(self, guarded=True, variant=None):
        self.committed = dict(oState=0)
        self.key = None
        self.guarded, self.variant = guarded, variant
        self.sent = []
        self.labels = []
        self.prov_bar = None

    def execute(self, bar, confirmed, entry, side=1, conf_on=True, prov_on=True, lbl_on=True, commit=True, realtime=True, prov_valid=False):
        st = dict(self.committed)                                    # var rollback
        if self.variant == "reset_each_tick":
            self.key = None
        if not confirmed and prov_on and st["oState"] == 0 and prov_valid and self.prov_bar != bar:
            self.prov_bar = bar                                       # provisional: its own varip stProvBar
            if realtime:
                self.sent.append(("仮", bar, side))
            if self.variant == "prov_sets_key":
                self.key = bar
        labels = []
        if confirmed and entry and st["oState"] == 0:
            st["oState"] = 1                                          # strategy.entry / exit (outside the guard)
            ok = conf_on and (not self.guarded or self.key is None or self.key != bar)
            if self.variant == "var_key":
                ok = conf_on and (st.get("key") is None or st.get("key") != bar)
                if ok:
                    st["key"] = bar
            elif ok and self.guarded:
                self.key = bar
            if ok and realtime:
                self.sent.append(("確定", bar, side))
            if lbl_on:
                labels.append(("conf", bar, side))
        if commit:
            self.committed = st
            self.labels += labels
            if st["oState"] == 1:
                self.committed = dict(st, oState=0)                   # the order is handled before the next entry bar
        return self


def conf(s):
    return [x for x in s.sent if x[0] == "確定"]


def gate_model():
    pats = {p: pattern_ok(F[p]) for p in cb.FILES}
    check("CM-00 every file has the modelled pattern (varip key declared, guard on the confirmed alert, key set right before "
          "alert())", all(pats.values()), str(pats))
    a = Strat().execute(100, True, True)
    check("CM-01 (1) first confirmed entry -> 1 alert", conf(a) == [("確定", 100, 1)])
    b = Strat().execute(100, True, True, commit=False).execute(100, True, True, commit=False).execute(100, True, True)
    c = Strat(guarded=False).execute(100, True, True, commit=False).execute(100, True, True)
    check("CM-02 (2) the confirmed branch reached 2 / 3 times on the same bar -> 1 alert (without the guard 2)",
          len(conf(b)) == 1 and len(conf(Strat().execute(100, True, True, commit=False).execute(100, True, True))) == 1 and len(conf(c)) == 2)
    d = Strat().execute(100, True, True).execute(400, True, True).execute(700, True, True, side=-1)
    check("CM-03 (3) legitimate entries on different bars -> 1 alert each", conf(d) == [("確定", 100, 1), ("確定", 400, 1), ("確定", 700, -1)])
    e = Strat().execute(100, True, True).execute(400, True, True)
    check("CM-04 (4) another bar with the same text / prices is still sent (the key is the bar time, not the text)", len(conf(e)) == 2)
    f = Strat().execute(100, False, False, prov_valid=True).execute(100, False, False, prov_valid=True).execute(100, True, True)
    check("CM-05 (5) provisional then confirmed on the same bar -> provisional 1, confirmed 1",
          [x[0] for x in f.sent] == ["仮", "確定"])
    g = Strat().execute(100, False, False, prov_on=False, prov_valid=True).execute(100, True, True, prov_on=False)
    check("CM-06 (6) provisional alert OFF -> the confirmed alert still works", [x[0] for x in g.sent] == ["確定"])
    h = Strat().execute(100, True, True, conf_on=False)
    h2 = h.execute(100, True, True, conf_on=False, commit=False)
    check("CM-07 (7) confirmed alert OFF -> nothing sent and the key not written (a later bar with alerts ON sends)",
          conf(h2) == [] and h.key is None and len(conf(Strat().execute(100, True, True, conf_on=False).execute(400, True, True))) == 1)
    i = Strat().execute(100, False, True).execute(100, True, False)
    check("CM-08 (8) unconfirmed tick or no order (branch not reached) -> no confirmed alert, key untouched",
          conf(i) == [] and i.key is None)
    j1 = Strat().execute(100, True, True, lbl_on=False)
    j2 = Strat().execute(100, True, True, lbl_on=True)
    check("CM-09 (9) label ON / OFF does not change what is sent", conf(j1) == conf(j2) == [("確定", 100, 1)]
          and j1.labels == [] and j2.labels == [("conf", 100, 1)])
    k = Strat().execute(100, True, True, side=-1, commit=False).execute(100, True, True, side=-1)
    check("CM-10 (10) SHORT has the same dedup as LONG", conf(k) == [("確定", 100, -1)]
          and conf(Strat().execute(100, True, True, side=1, commit=False).execute(100, True, True, side=1)) == [("確定", 100, 1)])
    s1, s2 = Strat(), Strat()
    s1.execute(100, True, True, commit=False).execute(100, True, True)
    s2.execute(100, True, True, side=-1)
    check("CM-11 (11) separate Strategies (separate scripts, separate varip) at the same time each send their own alert",
          conf(s1) == [("確定", 100, 1)] and conf(s2) == [("確定", 100, -1)])
    hist = Strat().execute(10, True, True, realtime=False).execute(100, True, True)
    check("CM-12 historical bars send nothing and their key does not block the first realtime entry",
          conf(hist) == [("確定", 100, 1)])


def gate_mutation():
    rep = lambda s: s.execute(100, True, True, commit=False).execute(100, True, True)
    check("CU-01 model mutations caught: a var (rolled back) key duplicates, a key reset each tick duplicates, a key set by "
          "the provisional alert suppresses the confirmed one",
          len(conf(rep(Strat(variant="var_key")))) == 2 and len(conf(rep(Strat(variant="reset_each_tick")))) == 2
          and conf(Strat(variant="prov_sets_key").execute(100, False, False, prov_valid=True).execute(100, True, True)) == [])
    p = cb.FILES[0]
    t = F[p]
    muts = [t.replace(COND, "if stAlertConf"), t.replace(DECL, "var int    stConfBar = na"),
            t.replace("                    stConfBar := time\n", ""), t.replace(COND, "if stAlertConf and (na(stConfBar) or stConfBar != bar_index)")]
    check("CU-02 source mutations rejected by the exact strip: guard removed, var key, missing assignment, bar_index key",
          all(m != t and cb.strip(m) is None for m in muts))


def main():
    for g in (gate_static, gate_model, gate_mutation):
        try:
            g()
        except Exception:
            import traceback
            check(f"{g.__name__} completed without error", False, traceback.format_exc()[-900:])
    fails = 0
    for n, ok, d in RESULTS:
        fails += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {n[:150].ljust(150)}  {'' if ok else d}")
    print(f"\n{len(RESULTS) - fails}/{len(RESULTS)} passed  [PINE_NOT_VERIFIED: exact build / static / Python model]")
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
