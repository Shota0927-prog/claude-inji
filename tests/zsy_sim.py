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


# ---- ZSY Transfer: the Pine section itself, translated and run (tests/acc_pine.py translator, unchanged) ----
def transfer_env():
    import acc_pine as ap
    sec = zb.marked(zb.raw(zb.PROBE), "// ==== ZSY Transfer (begin)", "// ==== ZSY Transfer (end)")
    env = ap.make_env(ap.Broker(), [])
    env["array__new_int"] = lambda n=0, v=None: [v] * n
    exec(compile(ap.Translator().translate(ap.logical_lines(sec)), "<ZSY Transfer>", "exec"), env)
    return env


def sources(rnd, nA, nD, nE, nF, nDead, nP):
    T = 1_767_574_800_000
    aTf = [rnd.randrange(3) for _ in range(nA)]
    aL = [round(2000 + rnd.random() * 100, 3) for _ in range(nA)]
    aU = [x + round(rnd.random() * 10, 3) for x in aL]
    aReg = [T + rnd.randrange(10**6) * 300_000 for _ in range(nA)]
    pc = [round(2000 + rnd.random() * 100, 3) if k < nD else None for k in range(4)]
    rnd.shuffle(pc)
    pcReg = [T + k * 300_000 if pc[k] is not None else None for k in range(4)]
    ze = [None] * 10
    zeReg = [None, None]
    for k in range(nE):
        ze[k * 5:k * 5 + 5] = [2100.0 + k, 2050.0 - k, 1.0, 7.0 + k, 1.0]
        zeReg[k] = T + k
    st = [0] * nF + [2] * nDead
    st = [x if x == 2 else rnd.choice([0, 1]) for x in st]
    rnd.shuffle(st)
    nf = len(st)
    fTf = [rnd.randrange(4) for _ in range(nf)]
    fB = [round(2000 + rnd.random() * 100, 3) for _ in range(nf)]
    fT = [x + 3 + round(rnd.random() * 20, 3) for x in fB]
    fReg = [T + i * 300_000 for i in range(nf)]
    pP = [round(2000 + rnd.random() * 100, 3) for _ in range(nP)]
    pTf = [rnd.randrange(4) for _ in range(nP)]
    pReg = [T + i * 300_000 for i in range(nP)]
    return [aTf, aL, aU, aReg, pc, pcReg, ze, zeReg, fTf, st, fB, fT, fReg, pP, pTf, pReg]


def expected(a):
    aTf, aL, aU, aReg, pc, pcReg, ze, zeReg, fTf, st, fB, fT, fReg, pP, pTf, pReg = a
    out = [(1, aTf[i], aL[i], aU[i], aReg[i], 0) for i in range(len(aTf))]
    out += [(3, k, pc[k], pc[k], pcReg[k], 0) for k in range(4) if pc[k] is not None]
    for k in range(2):
        if ze[k * 5 + 4] == 1:
            for r in (0.236, 0.382, 0.5, 0.618):
                p = ze[k * 5 + 1] + r * (ze[k * 5] - ze[k * 5 + 1])
                out.append((5, k, p, p, zeReg[k], r))
    out += [(4, fTf[i], fB[i], fT[i], fReg[i], st[i]) for i in range(len(st)) if st[i] < 2]
    out += [(2, pTf[i], pP[i], pP[i], pReg[i], 0) for i in range(len(pP))]
    return out


def transfer_checks():
    import random
    env = transfer_env()
    recs, chk = env["f_zpRecs"], env["f_zpRecCheck"]

    def run(a, maxEl):
        r, need, over, ck, *n = recs(*[list(x) for x in a], maxEl)
        return r, need, over, ck, n

    def decode(r):
        return [tuple(r[i + 1:i + 7]) for i in range(0, len(r), 7)]

    rnd = random.Random(7)
    bad = []
    for case in range(300):
        cnt = (rnd.randrange(0, 12), rnd.randrange(0, 5), rnd.randrange(0, 3), rnd.randrange(0, 60), rnd.randrange(0, 30), rnd.randrange(0, 400))
        a = sources(rnd, *cnt)
        r, need, over, ck, n = run(a, 100000)
        exp = expected(a)
        m, shape, seq, ckok, c = chk(r, ck)
        want_c = [0, cnt[0], cnt[5], cnt[1], cnt[3], 4 * cnt[2]]
        if over or need != 7 * len(exp) or decode(r) != exp or not (shape and seq and ckok) or m != len(exp) or c != want_c \
                or n != [cnt[0], cnt[1], 4 * cnt[2], cnt[3], cnt[5]]:
            bad.append((case, cnt, need, m, c))
    check("ZS-06 transfer (the ZSY Transfer section run as is): 300 random sets (accum 0-11, POC 0-4, fib waves 0-2, FVG / iFVG 0-59 + 0-29 "
          "invalid, pivots 0-399): every valid Zone is one 7-number record in the fixed order with the source values (decoded == an "
          "independent Python list), invalid FVGs excluded, counts taken from the source arrays, and the receiver sees whole records, "
          "sequence 0..n-1, the same checksum and the same per-type counts", not bad, str(bad[:3]))

    # boundary: total Zones Z -> 7Z elements; limit just above / exactly / just below, and the real limit 100,000
    bad = []
    for Z, lim, ok in ((50, 351, True), (50, 350, True), (50, 349, False), (14285, 100000, True), (14286, 100000, False)):
        a = sources(random.Random(Z), 0, 0, 0, 0, 0, Z)
        r, need, over, ck, n = run(a, lim)
        m, shape, seq, ckok, c = chk(r, ck)
        if ok:
            good = not over and len(r) == 7 * Z and m == Z and shape and seq and ckok and decode(r) == expected(a)
        else:
            good = over and len(r) == 0 and need == 7 * Z
        if not good:
            bad.append((Z, lim, ok, over, len(r), need))
    check("ZS-07 limit (elements): 50 Zones = 350 elements with limit 351 (just below) and 350 (exactly) -> all 50 records; limit 349 -> "
          "'over' with no record at all (not cut); the real limit 100,000: 14,285 Zones (99,995) all, 14,286 (100,002) 'over', empty",
          not bad, str(bad))

    # growing: pivots added one by one across the limit; the result flips to 'over' exactly when 7Z > limit and is never partial
    bad = []
    base = sources(random.Random(3), 2, 3, 1, 10, 4, 0)
    lim = 7 * (2 + 3 + 4 + 10) + 7 * 30
    for z in range(0, 40):
        a = [list(x) for x in base]
        a[13] = [2000.0 + i for i in range(z)]
        a[14] = [i % 4 for i in range(z)]
        a[15] = [1_767_574_800_000 + i for i in range(z)]
        r, need, over, ck, n = run(a, lim)
        if over != (need > lim) or (over and r) or (not over and decode(r) != expected(a)):
            bad.append((z, need, over, len(r)))
    check("ZS-08 growing Zones (one more pivot per step across a limit of 49 Zones): complete records up to 49, then 'over' with an empty "
          "array (no partial list) from 50 on", not bad, str(bad))

    # tampering the received array is detected (boundary, missing / duplicated / swapped record, changed value)
    a = sources(random.Random(11), 3, 2, 1, 8, 2, 20)
    r, need, over, ck, n = run(a, 100000)
    cases = {
        "last field cut": r[:-1],
        "last record missing": r[:-7],
        "record duplicated": r[:7] + r,
        "two records swapped": r[7:14] + r[:7] + r[14:],
        "value changed": r[:10] + [r[10] + 0.001] + r[11:],
    }
    det = {k: (lambda res: not (res[1] and res[2] and res[3]))(chk(v, ck)) for k, v in cases.items()}
    check("ZS-09 the receiver detects a cut record boundary, a missing / duplicated / swapped record and a changed value (shape, "
          "sequence or checksum NG)", all(det.values()), str(det))


def string_checks():
    own = own_lines(zb.raw(zb.PROBE))
    code = "\n".join(ln.split("//")[0] for ln in own.split("\n") if not ln.lstrip().startswith("//"))
    eng = code[code.index("f_zpEng() =>"):code.index("simple bool zpLowTf")]
    acc = re.findall(r"\b(\w+)\s*:=\s*\1\s*\+", code)
    strs = [v for v in acc if re.search(r"\bstring\s+" + v + r"\b", code)]
    check("ZS-10 no string is built up: no 'string' variable in the fixed 5m calculation, no str.split / str.repeat, no string variable "
          "accumulated with ':= x +' anywhere (table cells are single expressions of fixed pieces and numbers)",
          "string" not in eng and "str.split" not in code and "str.repeat" not in code and not strs, str(strs))


def main():
    probe = zb.raw(zb.PROBE)
    reg = zb.regions(probe)
    want = zb.blocks()
    bad = [n for n in want if reg.get(n) != want[n][1]]
    check("ZS-01 every ZSY copy region of ZoneSyncProbe.pine == its source block byte for byte (Lab Accum / f_acConfirmed / "
          "f_lbPivotConfirmed / FVG, MtfPocFeedXAU f_pocCore / f_feed, LongFibWave inputs / Logic+Transfer / f_lfwCore / f_fibState / "
          "f_fibFeed); no placeholder left; build() is a fixed point",
          not bad and set(reg) == set(want) and "@@COPY" not in probe and zb.build(probe) == probe, str(bad))

    # ---- no existing file changed (by ZSY: the files touched by the ZSY commits + uncommitted changes; other layers' commits on the
    #      same branch are not ZSY changes) ----
    log = git("log", f"{zb.BASE_REV}..HEAD", "--format=@@%s", "--name-only").stdout
    touched, cur = set(), False
    for ln in log.split("\n"):
        if ln.startswith("@@"):
            cur = ln[2:].startswith("ZSY")
        elif ln.strip() and cur:
            touched.add(ln.strip())
    touched |= {ln[3:] for ln in git("status", "--porcelain").stdout.split("\n") if ln.strip()}
    gone_ok = {"ZoneSyncProbeNest.pine", "ZoneSyncProbeRecv.pine", "ZoneSyncProbeWrap.pine"}     # ZSP-0, added and removed by ZSY
    extra = sorted(p for p in touched if p not in zb.NEW_FILES and p not in zb.TEST_EDITS and p not in gone_ok)
    rev_ok = all(zb.unadapt(p, zb.raw(p)) == git("show", f"{zb.BASE_REV}:{p}").stdout for p in zb.TEST_EDITS)
    src_same = all(zb.raw(p) == git("show", f"{zb.BASE_REV}:{p}").stdout for p in zb.SOURCES + ("StochMtfSignal.pine",))
    check(f"ZS-02 the ZSY commits since {zb.BASE_REV} (and uncommitted changes) touch only the ZSY files and the 2 registration edits, which "
          f"revert exactly to the {zb.BASE_REV} text; ZoneComboLabXAU / MtfPocFeedXAU / LongFibWave / StochMtfSignal are byte for byte unchanged",
          not extra and rev_ok and src_same and touched, f"{extra} rev_ok={rev_ok} src_same={src_same}")

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

    transfer_checks()
    string_checks()

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
