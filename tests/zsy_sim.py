"""ZSY checks — ZoneSyncProbe.pine (ZSP-1) and the ZSY registration.  python3 tests/zsy_sim.py

Static only (there is no Pine compiler here): the copied regions == the unchanged sources byte for byte, no existing file changed
(diff against the branch before ZSY, the two registration edits revert exactly), the registration accepts exactly the ZSY files,
the probe's structure (one fixed 5m request, nested requests <= 40, no strategy / alert / drawing of Zones, the chart side uses no
chart close / bar_index), and a continuation-indent lint of the probe's own lines.
Evidence class: STATIC (TradingView compile / run NOT verified).
"""
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import zsy_build as zb     # noqa: E402

ROOT = zb.ROOT
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


def git(*a):
    return subprocess.run(["git", "-C", ROOT] + list(a), capture_output=True, text=True)


def own_lines(text):
    """the probe's own lines (the ZSY copy regions removed)"""
    return re.sub(r"^// ==== ZSY copy (\w+) begin .*?^// ==== ZSY copy \1 end ====$", "", text, flags=re.S | re.M)


def main():
    probe = zb.raw(zb.PROBE)
    reg = zb.regions(probe)
    want = zb.blocks()
    bad = [n for n in want if reg.get(n) != want[n][1]]
    check("ZS-01 every ZSY copy region of ZoneSyncProbe.pine == its source block byte for byte (Lab Accum / f_acConfirmed / "
          "f_lbPivotConfirmed / FVG, MtfPocFeedXAU f_pocCore / f_feed, LongFibWave inputs / Logic+Transfer / f_lfwCore / f_fibState / "
          "f_fibFeed); no placeholder left; build() is a fixed point",
          not bad and set(reg) == set(want) and "@@COPY" not in probe and zb.build(probe) == probe, str(bad))

    # ---- no existing file changed ----
    st = git("diff", "--name-status", zb.BASE_REV).stdout.split("\n")
    st += ["A\t" + p for p in git("ls-files", "--others", "--exclude-standard").stdout.split("\n") if p]
    changed = {ln.split("\t")[-1]: ln.split("\t")[0] for ln in st if ln.strip()}
    extra = {p: s for p, s in changed.items() if p not in zb.NEW_FILES and p not in zb.TEST_EDITS}
    rev_ok = all(zb.unadapt(p, zb.raw(p)) == git("show", f"{zb.BASE_REV}:{p}").stdout for p in zb.TEST_EDITS)
    src_same = all(zb.raw(p) == git("show", f"{zb.BASE_REV}:{p}").stdout for p in zb.SOURCES + ("StochMtfSignal.pine",))
    check(f"ZS-02 against {zb.BASE_REV} (before ZSY) only the ZSY files differ; the 2 registration edits revert exactly to the {zb.BASE_REV} "
          "text; ZoneComboLabXAU / MtfPocFeedXAU / LongFibWave / StochMtfSignal are byte for byte unchanged",
          not extra and rev_ok and src_same, f"{extra} rev_ok={rev_ok} src_same={src_same}")

    # ---- registration ----
    acc = __import__("acc_build")
    cad = __import__("cad_adapt")
    lbs = __import__("lbs_build")
    regs_ok = all(all(zb.raw(p).count(new) == c for _, new, c in eds) for p, eds in zb.TEST_EDITS.items())
    lbs_rev = all(lbs.unadapt(p, zb.raw(p)) == git("show", f"84c4a96:{p}").stdout for p in lbs.TEST_EDITS)     # lbs_sim BASE_REV
    check("ZS-03 registration (a layer above LBS-1, same method): the tests/lbs_build.py and tests/cad_adapt.py edits are present exactly, "
          "acc_build.ok() (through lab / fds / lfw / lab2 / lbs) accepts exactly the ZSY files, cad_adapt.LATER_NEW lists them, and "
          "lbs_build.unadapt() still gives its own base text (the ZSY edits are reverted first)",
          regs_ok and lbs_rev and all(acc.ok(f) and f in cad.LATER_NEW for f in zb.NEW_FILES)
          and not acc.ok("ZoneSyncProbe.pine.bak") and not acc.ok("ZoneSyncProbeNest.pine") and not acc.ok("ZoneComboLabXAU.pine.bak"),
          f"regs={regs_ok} lbs_rev={lbs_rev}")

    # ---- structure ----
    own = own_lines(probe)
    code = "\n".join(ln.split("//")[0] if not ln.lstrip().startswith("//") else "" for ln in own.split("\n"))
    nreq = len(re.findall(r"request\.security\(", code))
    outer = re.findall(r'request\.security\(\s*syminfo\.tickerid,\s*"5",\s*f_zpEng\(\)', code)
    i_out = code.index("f_zpEng(), lookahead")
    chart_side = re.sub(r'"[^"\n]*"', '""', code[i_out:])
    chart_bad = re.findall(r"\b(close|open|high|low|bar_index|volume)\b", chart_side)
    check("ZS-04 structure: an indicator (not a strategy); no strategy.* / alert / box / label / line (no Zone drawing, no trading); exactly one "
          f"request of the fixed 5m context (f_zpEng) and {nreq} requests in all (<= 40); the chart side after it uses no chart "
          "close / open / high / low / volume / bar_index (only time_close / timenow to pick the confirmed 5m state)",
          "indicator(" in code and "strategy" not in code and not re.search(r"\b(alert|alertcondition|box\.new|label\.new|line\.new)\b", code)
          and len(outer) == 1 and nreq <= 40 and not chart_bad, f"n={nreq} outer={len(outer)} chart={chart_bad}")

    # ---- lint: a continuation line must not be indented by a multiple of 4 (Pine) ----
    bad_ind = []
    prev = ""
    for no, ln in enumerate(own.split("\n"), 1):
        s = ln.split("//")[0].rstrip() if not ln.lstrip().startswith("//") else ""
        if not s:
            continue
        ind = len(s) - len(s.lstrip())
        cont = re.search(r"(,|\+|\(|\band|\bor|\?|:|=|\[)$", prev) and not prev.endswith("=>")
        if cont and ind % 4 == 0:
            bad_ind.append(no)
        if not cont and ind % 4 != 0:
            bad_ind.append(-no)
        prev = s
    check("ZS-05 lint of the probe's own lines: every continuation line (after , + ( and or ? : = [) is indented by a non-multiple of 4 and "
          "every other line by a multiple of 4", not bad_ind, str(bad_ind[:20]))

    # ---- informational: files the older fixtures' 'no other file' checks still do not account for ----
    left = sorted(p for p in os.listdir(ROOT) if p.endswith(".pine") and not acc.ok(p)
                  and git("cat-file", "-e", f"ce1686d:{p}").returncode != 0)
    print("INFO root .pine files added after ce1686d that acc_build.ok() still does not accept (not ZSY):", left)

    n = sum(ok for _, ok, _ in RESULTS)
    for name, ok, d in RESULTS:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else "  -- " + d))
    print(f"{n}/{len(RESULTS)} passed  [STATIC: TradingView compile / run not verified]")
    return n == len(RESULTS)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
