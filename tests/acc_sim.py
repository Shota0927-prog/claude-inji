"""ACC-1 fixtures — AccumStrategyXAU.pine (XAUUSD 5M Accum-only Strategy).

  AS  static : the Accum copy == the NR-A1 copy in ZoneStrategyXAU.pine / ZoneStrategyXAULong.pine (rename + the added
               formation flag only) and, through the NR-A1 transform, == the Library f_accumBoxCore / f_accumBoxState of
               ZoneEnginePracticalXAUUSD.pine; 3 request calls (60 / 240 / D) with outputs [1] + lookahead_on like NR-A1;
               no import / Engine / SATS / FVG / MA; inputs and strategy() defaults as specified; every other file of the
               repository unchanged; the logic section is fully inside the translated subset
  AD  accum  : the REAL Library formation (tests/nr_a1_sim.py port) fed through the NR-A1 delivery into the translated
               logic: boxes registered once per (TF, ID), forming values follow the feed, fixed values never change, the
               fix happens on the 5M bar that receives the end, TFs independent, Keep Count, expiry, non-repainting
               (decisions on every prefix == decisions of the full run)
  AE  entry  : P1..P4, wick-only breaks, deviation only for P2 / P4, 3 USD wick retest, retest through the planned SL,
               24-bar window (bar 24 in / bar 25 out, weekend counted in bars), re-break after a fakeout, fakeout after a
               flip entry, several entries from one break, waits surviving the accum expiry, equality, fix + break on the
               same bar, deviation and retest on the same bar
  AR  risk   : SL width 5..30, near boundary TP -> skip (no jump), far boundary -> RR extended, no boundary -> fixed RR from
               the fill, expired boundary ignored, D > 4H > 1H, next candidate when the first one fails, LONG / SHORT conflict
  AO  orders : next-open fill, session (fill time, 9:00 in / 2:00 out), one position, 3 % simple lot, realtime BE (ticks)
               vs historical BE, doten ON / OFF, no doten outside the session, one order per bar, gap fills, SL + opposite
               signal on the same bar, SL gap + doten at the same open, random series invariants

Every model check runs the LOGIC SECTION OF THE PINE FILE through tests/acc_pine.py (mechanical translation) with the
broker emulator there. Evidence class: PINE_NOT_VERIFIED (TradingView compile / request.security / broker emulator /
Strategy Tester not reproduced).
"""
import os
import random
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import acc_pine as ap        # noqa: E402

ROOT = ap.ROOT
BASE_REV = "890498e"          # repository state before ACC-1
SRC = ap.read_source()
RESULTS = []
SRC_OVERRIDE = None           # AU: mutated Pine text for the scenario gates
ACC3_REV = "525756f"          # ACC-3 (before P5 / P6)
# ACC-4 changed the defaults (P1..P4 OFF, P5 / P6 ON, doten OFF). The ACC-1..3 gates below test the break patterns, so they run
# with the ACC-3 behaviour switched on; AV pins that this equals the ACC-3 file itself.
ACC3_OV = dict(enP1=True, enP2=True, enP3=True, enP4=True, enP5=False, enP6=False, dtOn=True)


class R(ap.Runner):
    """the Runner with the ACC-3 behaviour (ACC3_OV) under the given overrides."""

    def __init__(self, overrides=None, *a, **kw):
        ov = dict(ACC3_OV)
        ov.update(overrides or {})
        super().__init__(ov, *a, **kw)
M5 = 300_000
H1 = 3_600_000
D1 = 86_400_000


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


def raw(p):
    return open(os.path.join(ROOT, p), encoding="utf-8").read()


def code_only(src):
    return "\n".join(ap.strip_comment(l) for l in src.split("\n"))


def span(src, start, stop):
    i = src.index(start)
    return src[i:src.index(stop, i)]


# ============================================================================
# AS : static
# ============================================================================
def gate_static():
    core = span(SRC, "f_acAccumBoxCore(simple int rangeLen", "\nf_acAccumBoxState(")
    state = span(SRC, "f_acAccumBoxState(simple int rangeLen", "\n// ==== ACC Accum copy (end)")
    ren = lambda s: s.replace("f_acAccumBoxCore(", "f_nraAccumBoxCore(").replace("f_acAccumBoxState(", "f_nraAccumBoxState(")
    for p in ("ZoneStrategyXAU.pine", "ZoneStrategyXAULong.pine"):
        x = raw(p)
        ncore = span(x, "f_nraAccumBoxCore(simple int rangeLen", "\nf_nraAccumBoxState(")
        nstate = span(x, "f_nraAccumBoxState(simple int rangeLen", "\nf_nraAccumDetectProvisional(")
        check(f"AS-01 f_acAccumBoxCore == NR-A1 f_nraAccumBoxCore of {p} byte for byte (rename only)",
              ren(core).rstrip("\n") == ncore.rstrip("\n"))
        st2 = ren(state).rstrip("\n").replace("    [_sid, _top, _bot, _isAccum ? 1 : 0]", "    [_sid, _top, _bot]")
        check(f"AS-02 f_acAccumBoxState == NR-A1 f_nraAccumBoxState of {p} except the 4th output (formation flag)",
              st2 == nstate.rstrip("\n") and state.count("_isAccum ? 1 : 0") == 1)
    import nr_a1_build as na
    eng = raw("ZoneEnginePracticalXAUUSD.pine")
    lcore, lstate, _, _ = na.library_spans(eng)
    lstate = na.remove_gate(lstate)
    for a, b in (("f_accumBoxCore(", "f_acAccumBoxCore("), ("f_accumBoxState(", "f_acAccumBoxState(")):
        lcore, lstate = lcore.replace(a, b), lstate.replace(a, b)
    check("AS-03 the copy == Library f_accumBoxCore / f_accumBoxState of ZoneEnginePracticalXAUUSD.pine (NR-A1 transform: "
          "`if barstate.isconfirmed` guard removed, body de-indented) + the formation flag output",
          lcore.rstrip("\n") == core.rstrip("\n")
          and lstate.rstrip("\n") == state.rstrip("\n").replace("    [_sid, _top, _bot, _isAccum ? 1 : 0]", "    [_sid, _top, _bot]"))
    cc = code_only(SRC)
    reqs = re.findall(r'request\.security\(syminfo\.tickerid, "(\w+)", f_acConfirmed\([^)]*\),\s*lookahead = barmerge\.lookahead_on\)', cc)
    check("AS-04 exactly 3 request calls: 60 / 240 / D, each f_acConfirmed with lookahead_on (NR-A1 HTF branch); no other "
          "request / lookahead", reqs == ["60", "240", "D"] and cc.count("request.") == 3 and cc.count("lookahead =") == 3, str(reqs))
    conf = span(SRC, "f_acConfirmed(simple int", "\n\n")
    nconf = span(raw("ZoneStrategyXAU.pine"), "f_nraAccumConfirmed(simple bool", "\n\n")
    check("AS-05 f_acConfirmed takes the 4 outputs at [1] inside the HTF context (NR-A1 f_nraAccumConfirmed takes its 3 at "
          "[1] the same way) -> same delivery bar, the flag arrives with the values",
          "    [_u[1], _l[1], _i[1], _a[1]]" in conf and "    [_u[1], _l[1], _i[1]]" in nconf
          and "[_i, _u, _l, _a] = f_acAccumBoxState(" in conf)
    bad = [w for w in ("import ", "zn.", "SATS", "satBand", "FVG", "fvg", "ta.ema", "ta.sma", "ta.vwma", "Zone", "trend")
           if w in cc]
    check("AS-06 independent: no import / Engine / SATS / FVG / MA / Zone / trend code", not bad, str(bad))
    inp = ap.inputs()
    want = dict(acUse1=True, acUse2=True, acUse3=True, acKeep1=3, acKeep2=2, acKeep3=1, acLife1=3.0, acLife2=7.0, acLife3=30.0,
                accumRangeLen=10, accumBaseLen=20, accumAtrLen=14, accumMinUpperCloses=4, accumMinLowerCloses=4,
                accumMaxSameColorRun=4, accumAtrMult=2.5, accumBarRatioMax=0.70, accumDriftMax=0.30,
                enP1=False, enP2=False, enP3=False, enP4=False, enP5=True, enP6=True,     # ACC-4 defaults
                rgNear=3.0, rgWait=12, rgMinSl=2.0, rgRR=1.5,
                enRetestBars=24, enDev=5.0, enNear=3.0,
                rkBuf=1.5, rkMinSl=5.0, rkMaxSl=30.0, rkRR=1.5, rkTpAcc=True, beOn=True, beR=1.0, dtOn=False,
                seUse=True, seTz="Asia/Tokyo", seStartH=9, seStartM=0, seEndH=2, seEndM=0,
                mmCapBase=300000.0, mmRiskPct=3.0, mmLotOz=100.0, mmLotMin=0.01, mmLotStep=0.01,
                enFixMode="Start at Fix")
    diff = {k: (inp.get(k), v) for k, v in want.items() if inp.get(k) != v}
    check("AS-07 input defaults as specified (TF / Keep / expiry / detection / entry incl. ACC-4 P1..P4 OFF / P5 P6 ON / SL / TP / "
          "BE / doten OFF (ACC-4) / session / money)",
          not diff, str(diff))
    xau = raw("ZoneStrategyXAU.pine")
    same = all(re.search(rf"^{k}\s+= input\.\w+\({re.escape(str(v) if not isinstance(v, float) else '')}", xau, re.M) for k, v in [])
    acc_lines = re.findall(r"^(accum\w+)\s*=\s*(input\.\w+\(.*)$", SRC, re.M)
    xau_lines = dict(re.findall(r"^(accum\w+)\s*=\s*(input\.\w+\(.*)$", xau, re.M))
    check("AS-08 the 9 detection inputs are the same declarations as ZoneStrategyXAU.pine (names / defaults / limits)",
          len(acc_lines) == 9 and all(xau_lines.get(k) == v for k, v in acc_lines) and same is True)
    head = span(SRC, "strategy(\n", "\n\n")
    want_h = ["calc_on_every_tick      = true", "calc_on_order_fills     = false", "process_orders_on_close = false",
              "pyramiding              = 0", "initial_capital         = 300000", "currency                = currency.JPY"]
    check("AS-09 strategy(): 300,000 JPY, pyramiding 0, orders at the next open, calc_on_every_tick (realtime BE)",
          all(w in head for w in want_h), head)
    import acc_build as ab
    st = subprocess.run(["git", "-C", ROOT, "status", "--porcelain"], capture_output=True, text=True).stdout.split("\n")
    mod = set(subprocess.run(["git", "-C", ROOT, "diff", "--name-only", BASE_REV, "--"], capture_output=True, text=True).stdout.split())
    mod |= {l[3:] for l in st if l.startswith("??")}
    base = lambda m: subprocess.run(["git", "-C", ROOT, "show", f"{BASE_REV}:{m}"], capture_output=True, text=True).stdout
    bad = sorted(m for m in mod if not ab.ok(m)
                 and not (m in ab.TEST_EDITS and ab.unadapt(m, raw(m)) == base(m) and ab.unadapt(m, raw(m)) != raw(m)))
    pine = sorted(m for m in mod if m.endswith(".pine"))     # ACC-3: + the TradingView probe
    check("AS-10 vs 890498e only the ACC files (acc_build.NEW_FILES) are new and only the older fixtures listed in "
          "acc_build.TEST_EDITS change, each by exactly its recorded edit; the only Pine changes are the new AccumStrategyXAU.pine "
          "and the ACC-3 probe AccHistTickProbe.pine "
          "(existing Strategies / Engines / Visuals untouched)", not bad and pine == ["AccHistTickProbe.pine", "AccumStrategyXAU.pine"]
          and set(ab.TEST_EDITS) <= mod, str(bad))
    try:
        ap.transpile()
        ok, why = True, ""
    except Exception as ex:      # noqa: BLE001
        ok, why = False, repr(ex)
    check("AS-11 the whole logic section is inside the translated Pine subset (no history reference / unsupported syntax)", ok, why)
    lg = ap.logic_section(SRC)
    ent = [m.start() for m in re.finditer(r"strategy\.entry\(", lg)]
    conf_at = lg.index("    if barstate.isconfirmed\n")
    check("AS-12 strategy.entry appears once, inside `if barstate.isconfirmed` (no entry on a forming 5M bar)",
          len(ent) == 1 and ent[0] > conf_at and lg.count("strategy.close(") == 1)


# ============================================================================
# scenario helpers
# ============================================================================
# Monday 2026-01-05 10:00 JST (01:00 UTC)
T0 = 1767574800000
U, L = 4300.0, 4280.0
AID1 = T0 - 10 * H1
FEED_1H = {1: (U, L, AID1, 0)}


def B(o, h, l, c, ticks=None):
    x = (float(o), float(h), float(l), float(c))
    return x if ticks is None else x + ([float(t) for t in ticks],)


IN = B(4290, 4291, 4289, 4290)


def bars_of(seq, feed=FEED_1H, t0=T0, times=None):
    out = []
    for i, x in enumerate(seq):
        o, h, l, c = x[:4]
        b = dict(t=(times[i] if times else t0 + i * M5), o=o, h=h, l=l, c=c,
                 feed=feed(i) if callable(feed) else feed)
        if len(x) > 4:
            b["ticks"] = list(x[4])
        out.append(b)
    return out


def run(seq, feed=FEED_1H, overrides=None, t0=T0, times=None, usdjpy=150.0):
    return R(overrides, usdjpy=usdjpy, src=SRC_OVERRIDE).run(bars_of(seq, feed, t0, times))


def orders(r):
    return [(e[1], e[2], e[3], e[4]) for e in r.broker.log if e[0] == "order_entry"]


def fills(r):
    return [(e[1], e[2], e[3], e[4], e[5]) for e in r.broker.log if e[0] == "fill_entry"]


def exits(r):
    return [(e[1], e[2], e[3], e[4]) for e in r.broker.log if e[0] == "fill_exit"]


def exit_order(r, xid):
    xs = [e for e in r.broker.log if e[0] == "order_exit" and e[2] == xid]
    return xs[-1] if xs else None


def tr(r, i):
    return r.trace[i]


def close_eq(a, b, tol=1e-6):
    return a is not None and b is not None and abs(a - b) <= tol


# ============================================================================
# AD : accum registration / real formula / non-repainting
# ============================================================================
def gate_accum():
    # forming -> fix: values follow the feed while forming, no break event on a forming box, fix on the end bar
    def feed(i):
        if i < 3:
            return {1: (4300.0 + i, 4280.0, AID1, 1)}
        return {1: (4302.0, 4280.0, AID1, 0)}
    seq = [IN, B(4290, 4306, 4290, 4305), IN, IN, IN]
    r = R().run(bars_of(seq, feed)[:2])
    boxes = r["acBoxes"]
    check("AD-01 forming: the box follows the feed (up 4301 on bar 1), is not fixed, and a close above it starts no event",
          len(boxes) == 1 and boxes[0].up == 4301.0 and not boxes[0].fixed and r["acEvs"] == [] and orders(r) == [])
    r = run(seq, feed)
    b = r["acBoxes"][0]
    check("AD-02 fix: the 5M bar receiving acc = 0 fixes up / lo (4302 / 4280), fixTime = that bar's time, expiry + 3 days",
          b.fixed and b.up == 4302.0 and b.fixTime == T0 + 3 * M5 and b.expTime == T0 + 3 * M5 + 3 * D1)

    def feed2(i):
        return {1: (4300.0 if i < 2 else 4350.0, 4280.0 if i < 2 else 4200.0, AID1, 0)}
    r = run([IN] * 4, feed2)
    b = r["acBoxes"]
    check("AD-03 a fixed box never changes (same ID delivered later with other values is ignored); one box per ID",
          len(b) == 1 and b[0].up == 4300.0 and b[0].lo == 4280.0 and r["acSeq"] == 1)

    def feed3(i):
        return {1: (4300.0, 4280.0, AID1, 0), 2: (4300.0, 4280.0, AID1, 0), 3: (4300.0, 4280.0, AID1, 0)}
    r = run([IN] * 3, feed3)
    check("AD-04 1H / 4H / D with the same ID and prices are 3 separate boxes (TF independence, no merging)",
          sorted(x.tf for x in r["acBoxes"]) == [0, 1, 2] and r["acSeq"] == 3)

    # Keep Count 1H = 3: 4 IDs -> the oldest is pushed out (dead -> removed from the registry, no TP / break)
    def feed4(i):
        k = min(i, 3)
        return {1: (4300.0 + 10 * k, 4280.0 + 10 * k, AID1 + k * H1, 0)}
    r = run([IN] * 5, feed4)
    ids = sorted(x.aid for x in r["acBoxes"])
    check("AD-05 Keep Count 1H = 3: the 4th 1H accum pushes out the oldest ID (only the newest 3 remain valid)",
          ids == [AID1 + H1, AID1 + 2 * H1, AID1 + 3 * H1], str(ids))
    r = run([IN] * 5, feed4, overrides=dict(acKeep1=1))
    check("AD-06 Keep Count is per TF and adjustable (1H keep 1 -> 1 box)", [x.aid for x in r["acBoxes"]] == [AID1 + 3 * H1])

    # TF OFF: nothing registered
    r = run([IN] * 3, feed3, overrides=dict(acUse2=False))
    check("AD-07 TF OFF (4H): no 4H box at all", sorted(x.tf for x in r["acBoxes"]) == [0, 2])

    # real formula + NR-A1 delivery + non-repainting
    import nr_a1_sim as nas
    rnd_ok, prefix_ok, fixed_ok, n_fixed, n_boxes, detail = True, True, True, 0, 0, ""
    for seed in (3, 7):
        b5 = nas.market(seed, 30)
        feeds = feeds_from_5m(nas, b5)
        bars = [dict(t=t, o=o, h=h, l=l, c=c, feed=feeds[i]) for i, (t, o, h, l, c) in enumerate(b5)]
        r = R(dict(seUse=False))
        seen = {}
        for i, b in enumerate(bars):
            r.step(b)
            for x in r["acBoxes"] + r["acDrawn"]:
                key = (x.tf, x.aid)
                if x.fixed:
                    if key in seen and seen[key] != (x.up, x.lo):
                        fixed_ok = False
                    seen[key] = (x.up, x.lo)
        n_fixed += len(seen)
        # expected fixed values: the real formula's (top, bot) on the last forming HTF bar of each ID
        exp = expected_fixed(nas, b5)
        got = {k: v for k, v in seen.items()}
        miss = [k for k in got if k not in exp or exp[k] != got[k]]
        if miss:
            rnd_ok, detail = False, f"seed {seed}: {miss[:3]}"
        n_boxes += len(exp)
        # non-repainting: a run on a prefix makes the same orders on that prefix
        full = [(o[0], o[1], o[2], round(o[3], 6)) for o in orders(r)]
        cut = len(bars) * 2 // 3
        rp = R(dict(seUse=False)).run(bars[:cut])
        part = [(o[0], o[1], o[2], round(o[3], 6)) for o in orders(rp)]
        if part != [x for x in full if x[0] < cut]:
            prefix_ok = False
    check("AD-08 real Library formation (nr_a1_sim port) through the NR-A1 delivery: every fixed box == (top, bot) of the "
          "last forming HTF bar of its ID, keyed by (TF, ID)", rnd_ok and n_fixed > 5, f"{detail} fixed={n_fixed}")
    check("AD-09 fixed boundaries never change afterwards (all bars of 2 random 30-day series)", fixed_ok)
    check("AD-10 non-repainting: orders of a run on the first 2/3 == the full run's orders on those bars (2 seeds)", prefix_ok)


def feeds_from_5m(nas, b5):
    """NR-A1 delivery: on the 5M bars inside HTF bar k, the committed outputs of HTF bar k-1 (tests/nr_a1_sim feed new_*)."""
    out = [dict() for _ in b5]
    idx = {t: i for i, (t, *_r) in enumerate(b5)}
    for k_tf, (name, tf, day) in enumerate(nas.TFS, start=1):
        htf = nas.htf_from_5m(b5, tf, day)
        com = htf_committed(nas, htf)
        for k, hb in enumerate(htf):
            if k == 0:
                continue
            for j, s in enumerate(hb["slots"]):
                t = hb["T"] + s * M5
                out[idx[t]][k_tf] = com[k - 1]
    return out


def htf_committed(nas, htf):
    ctx = nas.Ctx(nas.P, "nogate")
    com = []
    for hb in htf:
        subs = hb["subs"]
        o, h, l, c = subs[0][0], max(s[1] for s in subs), min(s[2] for s in subs), subs[-1][3]
        st, ported, _ = ctx.evaluate(o, h, l, c, hb["T"], True)
        ctx.commit(o, h, l, c, hb["T"], st)
        sid, top, bot = ported
        com.append((top, bot, sid, 1 if st["isacc"] else 0))
    return com


def expected_fixed(nas, b5):
    exp = {}
    for k_tf, (name, tf, day) in enumerate(nas.TFS):
        htf = nas.htf_from_5m(b5, tf, day)
        com = htf_committed(nas, htf)
        for k in range(len(com) - 1):           # the last HTF bar is never delivered
            top, bot, sid, acc = com[k]
            if sid is not None and acc == 0:
                exp.setdefault((k_tf, sid), (top, bot))
    return exp


# ============================================================================
# AE : entry patterns
# ============================================================================
def gate_entry():
    # P1: break 4302 (no deviation), fakeout close 4298 -> SHORT, SL = max high (4306) + 1.5, TP = lower 4280 (RR 1.89)
    seq = [IN, B(4295, 4303, 4294, 4302), B(4302, 4306, 4298, 4298), B(4297.5, 4298, 4296, 4297)]
    r = run(seq)
    o = orders(r)
    check("AE-01 P1 upper fakeout: break close 4302 / back below 4300 -> SHORT on the next open (no 5 USD deviation needed); "
          "SL = 4306 + 1.5 (break-to-fakeout high incl. both bars), TP = 1H lower 4280 (RR 18 / 9.5 >= 1.5)",
          o == [(2, "S1", -1, 6.0)] and exit_order(r, "X1")[4:] == (4307.5, 4280.0) and fills(r)[0][1:] == ("S1", -1, 6.0, 4297.5)
          and r["nEnt1"] == 1, f"{o} {exit_order(r, 'X1')}")
    check("AE-02 P1 after the fill: TP stays the boundary, real RR from the fill price (17.5 / 10)",
          close_eq(tr(r, 3)["oRRReal"], 17.5 / 10) and tr(r, 3)["oTP"] == 4280.0 and tr(r, 3)["oState"] == 2)
    # P2: break with deviation (close 4306), retest low 4302.5 close 4304 -> LONG, SL 4298.5, fixed RR from the fill
    seq = [IN, B(4295, 4307, 4294, 4306), B(4306, 4306.5, 4302.5, 4304), B(4304.5, 4305, 4304, 4304.8)]
    r = run(seq)
    xo = exit_order(r, "X1")
    check("AE-03 P2 upper flip: deviation on the break bar (4306 >= 4305), wick to 4302.5 (<= 4303) and close 4304 > 4300 "
          "-> LONG; SL = 4300 - 1.5; no boundary above -> fixed RR; provisional TP from the signal close (4312.25), then "
          "4304.5 + 1.5 x 6 = 4313.5 from the fill",
          orders(r) == [(2, "L1", 1, 10.0)] and exit_order(r, "X1") is not None and tr(r, 3)["oTP"] == 4313.5
          and [e[4:] for e in r.broker.log if e[0] == "order_exit" and e[2] == "X1"] == [(4298.5, 4312.25), (4298.5, 4313.5)]
          and r["nEnt2"] == 1, f"{orders(r)} {xo}")
    # P3 mirror
    seq = [IN, B(4285, 4286, 4277, 4278), B(4278, 4282, 4274, 4282), B(4282.5, 4283, 4282, 4282.5)]
    r = run(seq)
    check("AE-04 P3 lower fakeout: break close 4278 / back above 4280 -> LONG; SL = 4274 - 1.5; TP = 1H upper 4300 "
          "(RR 18 / 9.5)", orders(r) == [(2, "L1", 1, 6.0)] and exit_order(r, "X1")[4:] == (4272.5, 4300.0), str(orders(r)))
    # P4 mirror
    seq = [IN, B(4285, 4286, 4273, 4274), B(4274, 4277.5, 4273, 4276), B(4275.5, 4276, 4275, 4275.5)]
    r = run(seq)
    check("AE-05 P4 lower flip: deviation 4274 <= 4275, wick 4277.5 >= 4277, close 4276 < 4280 -> SHORT, SL 4281.5, "
          "fixed RR", orders(r) == [(2, "S1", -1, 10.0)] and tr(r, 3)["oTP"] == 4275.5 - 1.5 * 6.0, str(orders(r)))
    # wick-only break
    seq = [IN, B(4295, 4310, 4294, 4299), B(4299, 4300, 4290, 4291), IN]
    r = run(seq)
    check("AE-06 wick-only break (high 4310, close 4299) starts no event -> no P1 / P2", r["acEvs"] == [] and orders(r) == [])
    # P2 needs the deviation: max close 4304.99
    seq = [IN, B(4295, 4305, 4294, 4304.99), B(4304, 4305, 4302, 4304), B(4304, 4305, 4302, 4304), IN]
    r = run(seq, {1: (U, 4240.0, AID1, 0)})
    check("AE-07 no deviation (best close 4304.99 < 4305): retests produce no P2; the later fakeout still gives P1 "
          "(no deviation for P1)", [o[1][0] for o in orders(r)] == ["S"] and r["nSig2"] == 0 and r["nSig1"] == 1, str(orders(r)))
    # near: low exactly 4303 accepted, 4303.01 refused
    base = [IN, B(4295, 4307, 4294, 4306)]
    r1 = run(base + [B(4306, 4306.5, 4303.0, 4305), IN])
    r2 = run(base + [B(4306, 4306.5, 4303.01, 4305), IN])
    check("AE-08 retest proximity: wick to 4303.00 (= 4300 + 3) accepted, 4303.01 refused",
          r1["nSig2"] == 1 and r2["nSig2"] == 0)
    # retest wick through the planned SL (4298.5) but close above 4300 -> still LONG
    r = run(base + [B(4306, 4306.5, 4297.0, 4304), B(4304, 4305, 4303.5, 4304.5)])
    check("AE-09 retest wick to 4297 (below the planned SL 4298.5) with close 4304 > 4300 -> LONG accepted",
          orders(r) == [(2, "L1", 1, 10.0)], str(orders(r)))
    # 24-bar window: break at bar 1; bars 2.. stay above (closes 4310, no touch); retest at age 24 / 25
    stay = B(4310, 4311, 4309, 4310)
    def window(age):
        return [IN, B(4295, 4307, 4294, 4306)] + [stay] * (age - 1) + [B(4310, 4310, 4302.5, 4305.5), stay]
    r24, r25 = run(window(24)), run(window(25))
    check("AE-10 window: retest on bar 24 after the break -> LONG; on bar 25 -> expired (no signal, event removed)",
          r24["nSig2"] == 1 and r25["nSig2"] == 0 and r25["acEvs"] == [], f"{r24['nSig2']} {r25['nSig2']}")
    def fwindow(age):
        return [IN, B(4295, 4303, 4294, 4302)] + [B(4302, 4303, 4301, 4302)] * (age - 1) + [B(4302, 4303, 4297, 4298), IN]
    f24, f25 = run(fwindow(24)), run(fwindow(25))
    check("AE-11 window: fakeout on bar 24 -> P1; on bar 25 -> nothing (expired)", f24["nSig1"] == 1 and f25["nSig1"] == 0)
    r = run(window(24), overrides=dict(enRetestBars=10))
    check("AE-12 the window is an input (10 bars: the bar-24 retest is refused)", r["nSig2"] == 0)
    # weekend: break on Saturday 05:30 JST, 5 bars to 05:55, Monday from 07:00 -> bars counted, not hours
    sat = 1767990600000                      # 2026-01-09 20:30 UTC = Sat 05:30 JST
    mon = 1768168800000                      # 2026-01-11 22:00 UTC = Mon 07:00 JST
    times = [sat - M5] + [sat + i * M5 for i in range(6)] + [mon + i * M5 for i in range(40)]
    seq = [IN, B(4295, 4307, 4294, 4306)] + [stay] * 23 + [B(4310, 4310, 4302.5, 4305.5)] + [stay] * 21
    r = run(seq, times=times, overrides=dict(seUse=False))
    check("AE-13 weekend: break Sat 05:35, retest on the 24th 5M bar (Mon 08:30, 51 h later) -> LONG (real bars only)",
          r["nSig2"] == 1 and orders(r) and orders(r)[0][0] == 25, str(orders(r)))
    # re-break after a fakeout: new event, new window
    seq = [IN, B(4295, 4303, 4294, 4302), B(4302, 4303, 4297, 4298), B(4298, 4299, 4296, 4297),
           B(4297, 4304, 4297, 4303)] + [B(4303, 4304, 4302, 4303)] * 20 + [B(4303, 4303.5, 4296, 4297)]
    r = run(seq, overrides=dict(dtOn=False))
    check("AE-14 re-break after a fakeout: 2nd event from bar 4; its fakeout on bar 25 (24 bars after the re-break, 24 after "
          "the 1st break would be 25) -> P1 again", r["nSig1"] == 2, str(r["nSig1"]))
    # fakeout after a flip entry (doten)
    seq = [IN, B(4295, 4307, 4294, 4306), B(4306, 4306.5, 4302.5, 4304), B(4304.5, 4306, 4304, 4305),
           B(4305, 4305.5, 4299, 4299.5), B(4299, 4299.5, 4297, 4298)]
    r = run(seq)
    o = orders(r)
    check("AE-15 fakeout after a flip LONG: close back below 4300 within the window -> P1 SHORT (doten): SL = highest high "
          "since the break (4307) + 1.5", [x[1] for x in o] == ["L1", "S2"] and exit_order(r, "X2")[4] == 4308.5
          and r["nDoten"] == 1 and r.broker.max_abs_pos <= 10.0 + 1e-9, f"{o}")
    # several entries from one break: TP hit, then a second retest
    seq = [IN, B(4295, 4307, 4294, 4306), B(4306, 4306.5, 4302.5, 4304), B(4304.5, 4314, 4304.5, 4313),
           B(4313, 4313.5, 4302, 4305), B(4305, 4306, 4304.5, 4305.5)]
    r = run(seq)
    check("AE-16 several entries from one break: LONG 1 reaches TP (4313.5), a later retest of the same break -> LONG 2 "
          "(no re-arm distance, window not extended)", [x[1] for x in orders(r)] == ["L1", "L2"]
          and [x[1:3] for x in exits(r)][0] == ("L1", "X1") and r["acEvs"][0].bBar == 1, f"{orders(r)} {exits(r)}")
    # accum expiry during the wait
    exp_t = T0 + 3 * D1
    times = [T0] + [exp_t - 3 * M5 + i * M5 for i in range(7)]
    seq = [IN, B(4295, 4307, 4294, 4306), stay, stay, stay, B(4310, 4310, 4302.5, 4305.5), stay, stay]
    r = run(seq, feed={1: (U, L, AID1, 0)}, times=times, t0=None, overrides=dict(seUse=False))
    # the box is fixed on bar 0 (T0) -> expires at T0 + 3 days = bar 4; the break was on bar 1 (15 min before)
    check("AE-17 the accum expires 3 days after its fix (bar 4 here) while the break waits; the retest on bar 5 still "
          "-> LONG; the expired box is gone from the registry (no new break / TP)",
          r["nSig2"] == 1 and r["acBoxes"] == [], f"{r['nSig2']} {r['acBoxes']}")
    # the HTF keeps delivering the ended ID with the same values after the expiry: no re-registration, no new event
    times2 = [T0] + [T0 + 3 * D1 + i * M5 for i in range(4)]
    rb = run([IN, IN, B(4295, 4307, 4294, 4306), B(4306, 4306.5, 4302.5, 4304), IN], {1: (U, L, AID1, 0)}, times=times2,
             overrides=dict(seUse=False))
    check("AE-18 after the expiry the same ID (still delivered by the HTF every bar) is not registered again: no new break "
          "event, no signal, acSeq stays 1", rb["acEvs"] == [] and rb["nSig2"] == 0 and rb["acSeq"] == 1 and rb["acBoxes"] == [],
          f"{rb['acEvs']} {rb['acSeq']}")
    # equality
    seq = [IN, B(4295, 4301, 4294, 4300), B(4300, 4303, 4299, 4302), B(4302, 4303, 4299, 4300), B(4300, 4301, 4299, 4300.5),
           B(4300.5, 4301, 4299, 4299.5)]
    r = run(seq)
    check("AE-19 equality: close = 4300 is no break (bar 1) and no fakeout (bar 3); the fakeout comes on close 4299.5",
          [e for e in r.broker.log if e[0] == "order_entry"][0][1] == 5 and r["nSig1"] == 1, str(orders(r)))
    # fix and break on the same bar
    def feed5(i):
        return {1: (U, L, AID1, 1 if i < 2 else 0)}
    seq = [IN, IN, B(4295, 4303, 4294, 4302), B(4302, 4303, 4297, 4298), IN]
    r = run(seq, feed5)
    check("AE-20 accum end confirmed on the same 5M bar that closes above (prev 4290 <= 4300 < 4302) -> the break counts; "
          "P1 on the next bar", r["nSig1"] == 1 and orders(r)[0][0] == 3, str(orders(r)))
    seq = [IN, B(4295, 4303, 4294, 4302), B(4302, 4303, 4301, 4302), B(4302, 4303, 4297, 4298)]
    def feed6(i):
        return {1: (U, L, AID1, 1 if i < 2 else 0)}
    r1 = run(seq, feed6, overrides=dict(enFixMode="Wait for Cross"))
    r2 = run(seq, feed6)
    check("AE-21 already outside when fixed (close 4302 since bar 1, fixed on bar 2): default Start at Fix (ACC-2) -> event "
          "from the fix bar, P1 on bar 3; Wait for Cross (comparison) -> no event / no P1", r1["nSig1"] == 0 and r2["nSig1"] == 1)
    # deviation and retest on the same bar: no signal on that bar
    seq = [IN, B(4295, 4303, 4294, 4302), B(4302, 4306.5, 4302, 4306), B(4306, 4306.5, 4302.8, 4304), IN]
    r = run(seq)
    check("AE-22 deviation (close 4306) and a 4302 wick on the same bar -> no P2 there (deviation first needed on an "
          "earlier bar); next bar's retest -> P2", r["nSig2"] == 1 and orders(r)[0][0] == 3, str(orders(r)))
    r = run([IN, B(4295, 4303, 4294, 4302), B(4302, 4303, 4297, 4298), IN], overrides=dict(enP1=False))
    check("AE-23 pattern OFF (P1): no order, the event still ends on the fakeout", orders(r) == [] and r["acEvs"] == []
          and r["nSig1"] == 0)


# ============================================================================
# AR : SL / TP / priority
# ============================================================================
def gate_risk():
    def p1(high):    # P1 with fakeout close 4298, SL = high + 1.5
        return [IN, B(4295, 4301, 4294, 4300.5), B(4300.5, high, 4298, 4298), IN]
    widths = {}
    for hh, w in ((4301.49, 4.99), (4301.5, 5.0), (4326.5, 30.0), (4326.51, 30.01)):
        widths[w] = len(orders(run(p1(hh), {1: (U, 4240.0, AID1, 0)})))
    check("AR-01 SL width: 4.99 skip / 5.00 take / 30.00 take / 30.01 skip (never widened / narrowed)",
          widths == {4.99: 0, 5.0: 1, 30.0: 1, 30.01: 0}, str(widths))
    # near boundary: 1H lower 4290 is 8 below the fakeout close 4298 with SL width 9.5 -> RR 0.84 -> skip, even with a
    # 4H boundary far below
    seq = [IN, B(4295, 4303, 4294, 4302), B(4302, 4306, 4298, 4298), IN]
    fd = {1: (U, 4290.0, AID1, 0), 2: (4400.0, 4200.0, AID1, 0)}
    r = run([B(4295, 4296, 4294, 4295)] + seq[1:], fd)
    check("AR-02 nearest boundary in the profit direction gives RR < 1.5 -> the trade is skipped (no jump to the farther 4200)",
          orders(r) == [] and r["nSkipRR"] == 1)
    fd = {1: (U, 4250.0, AID1, 0)}
    r = run(seq, fd)
    check("AR-03 far boundary (4250, RR 48 / 9.5 = 5.05) -> TP = 4250 (not limited to 1.5R)",
          exit_order(r, "X1")[5] == 4250.0 and close_eq(tr(r, 2)["oRRPlan"], 48 / 9.5))
    r = run(seq, {1: (U, L, AID1, 0)}, overrides=dict(rkTpAcc=False))
    check("AR-04 boundary TP OFF / no boundary -> fixed RR 1.5 from the fill: 4297.5... TP = fill - 1.5 x (SL - fill)",
          close_eq(tr(r, 3)["oTP"], tr(r, 3)["oFill"] - 1.5 * (4307.5 - tr(r, 3)["oFill"])))
    # expired boundary ignored for TP: a 4H accum fixed 8 days before (expired) at 4290 below
    def feed_exp(i):
        if i == 0:
            return {2: (4310.0, 4290.0, AID1 - 9 * D1, 0)}
        return {1: (U, 4250.0, AID1, 0)}
    times = [T0 - 8 * D1] + [T0 + i * M5 for i in range(4)]
    r = run([IN] + seq, feed_exp, times=times)
    check("AR-05 an expired accum boundary (4H 4290, fixed 8 days earlier, 7-day expiry) is not a TP candidate -> TP 4250",
          exit_order(r, "X1") is not None and exit_order(r, "X1")[5] == 4250.0, str(exit_order(r, "X1")))
    # priority: same price action breaks 1H (4300 / 4280) and D (4301 / 4260) upper bounds; D first
    fdp = {1: (4300.0, 4250.0, AID1, 0), 2: (4300.5, 4250.0, AID1, 0), 3: (4301.0, 4250.0, AID1, 0)}
    seq = [IN, B(4295, 4303, 4294, 4302), B(4302, 4306, 4298, 4298), IN]
    r = run(seq, fdp)
    check("AR-06 priority D > 4H > 1H: three P1 candidates on one bar -> the D one (TF 2, SL from its own extreme)",
          tr(r, 2)["oTf"] == 2 and r["nSig1"] == 3, str(tr(r, 2)))
    # first candidate fails (D SL too wide via a huge spike before its own break) -> 4H taken
    fdq = {2: (4300.0, 4250.0, AID1, 0), 3: (4299.0, 4250.0, AID1, 0)}
    seq = [IN, B(4290, 4330, 4289, 4299.5), B(4299.5, 4303, 4299, 4302), B(4302, 4304, 4298, 4298), IN]
    r = run(seq, fdq)
    check("AR-07 the D candidate fails the SL width (high 4330 since its break -> 33.5) -> the 4H candidate is adopted",
          tr(r, 3)["oTf"] == 1 and r["nSkipSl"] == 1 and len(orders(r)) == 1, f"{tr(r, 3)['oTf']} {r['nSkipSl']}")
    # same TF: nearer boundary first
    fdn = {1: (4300.0, 4250.0, AID1, 0), 2: (4400.0, 4200.0, AID1, 0)}
    r = run(seq, {1: (4300.0, 4250.0, AID1, 0)})
    # conflict: an upper fakeout SHORT (1H 4300) and a lower fakeout LONG (4H, lower 4299) on the same bar
    fdc = {1: (4300.0, 4250.0, AID1, 0), 2: (4310.0, 4240.0, AID1, 0)}
    seq = [IN, B(4290, 4313, 4290, 4312), B(4312, 4312.5, 4302.5, 4304), IN]
    r = run(seq, fdc, overrides=dict(rkTpAcc=False))
    check("AR-08 LONG and SHORT valid on the same bar (4H upper fakeout P1 SHORT + 1H upper flip P2 LONG at close 4304) "
          "-> both skipped (nothing on bar 2; the 1H fakeout of bar 3 is a separate later SHORT)",
          [o for o in orders(r) if o[0] == 2] == [] and r["nConflict"] == 1 and r["nSig1"] == 2 and r["nSig2"] == 1,
          f"{orders(r)} {r['nConflict']}")
    # same TF two candidates: nearest boundary wins
    fds = {1: (4300.0, 4250.0, AID1, 0)}
    fdt = lambda i: {1: (4300.0, 4250.0, AID1, 0)} if i == 0 else {1: (4296.0, 4240.0, AID1 + H1, 0)}
    seq = [B(4290, 4291, 4289, 4290), B(4290, 4291, 4289, 4290), B(4295, 4303, 4294, 4302), B(4302, 4304, 4294, 4294), IN]
    r = run(seq, fdt)
    check("AR-09 same TF: two P1 candidates (1H 4300 and 1H 4296) -> the boundary nearer the close 4294 (4296) is used",
          len(orders(r)) == 1 and exit_order(r, "X1")[4] == 4304 + 1.5 and r["nSig1"] == 2, str(exit_order(r, "X1")))


# ============================================================================
# AO : orders / session / lot / BE / doten
# ============================================================================
def gate_orders():
    seq = [IN, B(4295, 4303, 4294, 4302), B(4302, 4306, 4298, 4298), B(4297.5, 4298, 4296, 4297)]
    r = run(seq)
    check("AO-01 signal on the confirmed bar 2, market fill at bar 3's open (4297.5), SL / TP exit sent with the entry",
          orders(r)[0][0] == 2 and fills(r)[0][0] == 3 and fills(r)[0][4] == 4297.5
          and [e for e in r.broker.log if e[0] == "order_exit"][0][1] == 2)
    # session: JST 08:50 bar closing 08:55 -> refused; bar 08:55 closing 09:00 -> ok; 01:55 closing 02:00 -> refused
    def at(jst_h, jst_m):
        t = 1767538800000 + (jst_h * 60 + jst_m) * 60000   # 2026-01-05 00:00 JST = 2026-01-04 15:00 UTC
        return t
    def sig_at(start):
        times = [start + i * M5 for i in range(-2, 2)]
        return run([IN, B(4295, 4303, 4294, 4302), B(4302, 4306, 4298, 4298), IN], times=times)
    a = sig_at(at(8, 50))      # signal bar 08:50-08:55
    b = sig_at(at(8, 55))      # signal bar 08:55-09:00
    c = sig_at(at(25, 50))     # 01:50-01:55 next day
    d = sig_at(at(25, 55))     # 01:55-02:00
    check("AO-02 session by the next-open fill time: 08:55 fill refused, 09:00 fill ok, 01:55 fill ok, 02:00 fill refused",
          (len(orders(a)), len(orders(b)), len(orders(c)), len(orders(d))) == (0, 1, 1, 0) and a["nSkipSess"] == 1)
    # break / retest outside the session still tracked: break at 08:30, retest at 08:55 -> fill 09:00
    times = [at(8, 40) + i * M5 for i in range(5)]
    r = run([IN, B(4295, 4307, 4294, 4306), B(4306, 4307, 4305, 4306), B(4306, 4306.5, 4302.5, 4304), IN], times=times)
    check("AO-03 break (08:45) and deviation tracked outside the session; the retest bar closing 09:00 -> LONG",
          orders(r) == [(3, "L1", 1, 10.0)], str(orders(r)))
    # one position: second LONG signal while long -> ignored
    seq = [IN, B(4295, 4307, 4294, 4306), B(4306, 4306.5, 4302.5, 4304), B(4304.5, 4306, 4302.6, 4304.6),
           B(4304.6, 4305, 4304, 4304.5)]
    r = run(seq)
    check("AO-04 one position: a second P2 LONG while long is ignored (no order, no pyramiding)",
          [x[1] for x in orders(r)] == ["L1"] and r["nSig2"] == 2 and r.broker.max_abs_pos == 10.0)
    # lot: 9,000 JPY / 150 = 60 USD; SL width 9.5 -> floor(60 / 9.5) = 6 -> 0.06 lot = 6 oz
    seq = [IN, B(4295, 4303, 4294, 4302), B(4302, 4306, 4298, 4298), IN]
    r1, r2 = run(seq), run(seq, usdjpy=100.0)
    q1, q2 = orders(r1)[0][3], orders(r2)[0][3]
    check("AO-05 lot: 300,000 x 3 % = 9,000 JPY -> 60 USD at 150 (strategy.convert_to_symbol, not a fixed USDJPY): "
          "0.06 lot (6 oz, 57 USD <= 60); at 100 -> 90 USD -> 0.09 lot", q1 == 6.0 and q2 == 9.0 and q1 * 9.5 <= 60.0)
    r3 = run(seq, usdjpy=100000.0)
    check("AO-06 lot below the minimum (budget 0.09 USD) -> skipped (never rounded up)", orders(r3) == [] and r3["nSkipQty"] == 1)
    # BE realtime vs historical: LONG fill 4304.5, SL 4298.5 -> 1R 6 -> trigger 4310.5
    pre = [IN, B(4295, 4307, 4294, 4306), B(4306, 4306.5, 4302.5, 4304), B(4304.5, 4305, 4304, 4304.8)]
    hist = run(pre + [B(4305, 4311, 4304, 4306), B(4306, 4307, 4303, 4304)])
    rt = run(pre + [B(4305, 4311, 4304, 4306, [4305, 4311, 4304, 4306]), B(4306, 4307, 4305, 4306)])
    ex_rt = exits(rt)
    check("AO-07 realtime BE: tick 4311 (>= 4310.5) moves the stop to the fill 4304.5 immediately; the tick 4304 in the "
          "same bar exits the LONG at BE (no wait for the 5M close)", ex_rt and ex_rt[0][0] == 4 and ex_rt[0][2] == "X1"
          and 4298.5 < ex_rt[0][3] <= 4304.5, str(ex_rt))
    ex_h = exits(hist)
    check("AO-08 historical BE: the same bar path keeps the original SL inside the bar (only one execution per bar); the "
          "stop is 4304.5 from the next bar (exit there at 4304.5)", ex_h and ex_h[0][0] == 5 and ex_h[0][3] == 4304.5
          and hist.trace[4]["oStop"] == 4304.5 and hist["nBE"] == 1, str(ex_h))
    r = run(pre + [B(4305, 4311, 4304, 4306), B(4306, 4307, 4303, 4304)], overrides=dict(beOn=False))
    check("AO-09 BE OFF: stop stays at the initial SL", exits(r) == [] and r.trace[-1]["oStop"] == 4298.5)
    # doten ON / OFF: LONG (P2) then upper fakeout SHORT
    seq = [IN, B(4295, 4307, 4294, 4306), B(4306, 4306.5, 4302.5, 4304), B(4304.5, 4306, 4304, 4305),
           B(4305, 4305.5, 4299, 4299.5), B(4299, 4299.5, 4297, 4298)]
    on, off = run(seq), run(seq, overrides=dict(dtOn=False))
    check("AO-10 doten ON: opposite signal -> one reversal order at the next open: LONG closed and SHORT opened with its own "
          "SL / TP / lot; never more than one position", [x[1] for x in orders(on)] == ["L1", "S2"]
          and fills(on)[-1][1:3] == ("S2", -1) and on.broker.pos == -fills(on)[-1][3]
          and ("L1", "S2") in [x[1:3] for x in exits(on)] and on.broker.max_abs_pos <= 10.0 + 1e-9, f"{orders(on)} {exits(on)}")
    check("AO-11 doten OFF: the opposite signal is ignored, the LONG keeps its SL / TP (still long after the signal's next "
          "open, closed later by its own SL 4298.5)", [x[1] for x in orders(off)] == ["L1"] and off.trace[5]["pos"] == 0
          and exits(off)[0][1:4] == ("L1", "X1", 4298.5) and off.trace[4]["pos"] == 10.0 and off["nSig1"] == 1)
    # doten outside the session: nothing (no close either)
    times = [at(1, 35) + i * M5 for i in range(6)]
    r = run(seq, times=times, overrides=dict(seStartH=9, seEndH=2))
    check("AO-12 opposite signal outside the session (fill 02:05): no doten and no close", [x[1] for x in orders(r)] == ["L1"]
          and r.trace[4]["pos"] == 10.0 and exits(r)[0][2] == "X1" and r["nSkipSess"] >= 1, str(orders(r)))
    # conflict while holding -> no doten
    fdc = {1: (4300.0, 4250.0, AID1, 0), 2: (4320.0, 4299.0, AID1, 0)}
    seq = [IN, B(4295, 4303, 4294, 4302), B(4302, 4303, 4296, 4297), B(4297, 4306, 4297, 4299.5), IN]
    # one bar per order
    nb = {}
    for o in orders(on):
        nb[o[0]] = nb.get(o[0], 0) + 1
    check("AO-13 at most one entry order per 5M bar", all(v == 1 for v in nb.values()))
    # gap beyond SL at the fill: SHORT SL 4307.5, fill gaps to 4309 -> the exit is not trusted -> market close + count
    seq = [IN, B(4295, 4303, 4294, 4302), B(4302, 4306, 4298, 4298), B(4309, 4310, 4308, 4309), IN]
    r = run(seq)
    check("AO-14 fill beyond the SL (gap): the position is closed (stop at the gap price), no exit kept, state cleared, "
          "counted as an invalid exit",
          r.broker.pos == 0 and r.trace[3]["oState"] == 0 and exits(r) and exits(r)[0][3] == 4309 and r["nBadExit"] == 1,
          f"{exits(r)} {r.trace[3]}")
    seq = [IN, B(4295, 4303, 4294, 4302), B(4302, 4306, 4298, 4298), B(4279, 4280, 4278, 4279), IN]
    r = run(seq)
    check("AO-15 fill beyond the boundary TP (gap to 4279 < 4280): taken at the gap price; no invalid exit order stays; counted",
          r.broker.pos == 0 and exits(r)[0][3] == 4279 and r.broker.exits == {} and r["nBadExit"] == 1)
    # fixed-RR TP with the fill above the signal close: TP from the fill (AE-03) / invalid relation counter via ticks
    pre2 = [IN, B(4295, 4307, 4294, 4306), B(4306, 4306.5, 4302.5, 4304)]
    r = run(pre2 + [B(4297, 4305, 4296, 4304, [4297, 4296, 4305, 4304]), IN])
    check("AO-16 realtime: fill at 4297 below the SL 4298.5 (gap) -> the exit stop fills at once; nothing invalid left open",
          r.broker.pos == 0 and r["oState"] == 0, str(r.trace[-2:]))
    # SL hit inside the bar of an opposite signal -> normal entry (not doten)
    seq = [IN, B(4295, 4307, 4294, 4306), B(4306, 4306.5, 4302.5, 4304), B(4304.5, 4305, 4304, 4304.8),
           B(4304.8, 4305, 4297, 4299)]
    r = run(seq)
    check("AO-17 SL (4298.5) hit inside the bar whose close is an upper fakeout -> flat at the close -> the SHORT is a normal "
          "new entry (doten count 0)", [x[1] for x in orders(r)] == ["L1", "S2"] and r["nDoten"] == 0
          and exits(r)[0][2] == "X1", f"{orders(r)} {exits(r)}")
    # SL gap at the same open as the doten fill: one reversal, no double size
    seq = [IN, B(4295, 4307, 4294, 4306), B(4306, 4306.5, 4302.5, 4304), B(4304.5, 4306, 4304, 4305),
           B(4305, 4305.5, 4299, 4299.5), B(4296, 4297, 4295, 4296), IN]
    r = run(seq)
    check("AO-18 doten order and an old-SL gap on the same open: the old exit was cancelled with the doten order -> one "
          "reversal at the open, position = the new qty only", r.broker.pos == -fills(r)[-1][3]
          and r.broker.max_abs_pos <= 10.0 + 1e-9 and len([x for x in exits(r) if x[1] == "L1"]) == 1, f"{exits(r)} {fills(r)}")
    # session realtime check: signal evaluated only on the confirmed tick
    pre3 = [IN, B(4295, 4307, 4294, 4306)]
    r = run(pre3 + [B(4306, 4306.5, 4302.5, 4306.2, [4306, 4302.5, 4304, 4306.5, 4306.2])])
    r2 = run(pre3 + [B(4306, 4306.5, 4299, 4299, [4306, 4304, 4302.5, 4306.5, 4299])])
    check("AO-19 realtime: intrabar ticks that satisfy a retest (4304 > 4300 after the 4302.5 wick) send nothing; only the "
          "confirmed close decides (4306.2 -> LONG / 4299 -> fakeout SHORT)",
          [x[1] for x in orders(r)] == ["L1"] and [x[1] for x in orders(r2)] == ["S1"] and orders(r)[0][0] == 2)


# ============================================================================
# AF : random series invariants
# ============================================================================
def gate_fuzz():
    import nr_a1_sim as nas
    inv_ok, n_orders, n_pat, detail = True, 0, [0, 0, 0, 0], ""
    for seed, ov in ((11, {}), (12, dict(dtOn=False)), (13, dict(enFixMode="Wait for Cross", seUse=False)),
                     (14, dict(rkTpAcc=False, beOn=False))):
        b5 = nas.market(seed, 30)
        feeds = feeds_from_5m(nas, b5)
        bars = [dict(t=t, o=o, h=h, l=l, c=c, feed=feeds[i]) for i, (t, o, h, l, c) in enumerate(b5)]
        r = R(ov).run(bars)
        n_orders += len(orders(r))
        for k in range(4):
            n_pat[k] += r[f"nEnt{k + 1}"]
        per_bar = {}
        for o in orders(r):
            per_bar[o[0]] = per_bar.get(o[0], 0) + 1
        # max one position of one order's size, one order per bar, every fill protected by an exit order of its id
        maxq = max([o[3] for o in orders(r)] or [0])
        if r.broker.max_abs_pos > maxq + 1e-9 or any(v > 1 for v in per_bar.values()):
            inv_ok, detail = False, f"seed {seed}: pos {r.broker.max_abs_pos} / {maxq}"
        xs = {e[3] for e in r.broker.log if e[0] == "order_exit"}
        if any(f[1] not in xs for f in fills(r)):
            inv_ok, detail = False, f"seed {seed}: unprotected fill"
        if r["nQtyAnom"] != 0:
            inv_ok, detail = False, f"seed {seed}: qty anomaly"
        if not ov.get("seUse", True) is False:
            import acc_pine
            for o in orders(r):
                tc = bars[o[0]]["t"] + M5
                env = r.env
                if not env["f_inSession"](tc):
                    inv_ok, detail = False, f"seed {seed}: order outside the session at bar {o[0]}"
    check("AF-01 random 30-day series x 4 settings (real accum feed): one position at most (|pos| <= order qty), one order "
          "per bar, every fill has its SL / TP order from the signal bar, no quantity anomaly, orders only in the session",
          inv_ok and n_orders > 0, f"{detail} orders={n_orders} by pattern={n_pat}")


# ============================================================================
# AN : ACC-2 — break at the accum end, BE / TP on history vs realtime, recalculation settings
# ============================================================================
PRE_L = [IN, B(4295, 4307, 4294, 4306), B(4306, 4306.5, 4302.5, 4304)]     # P2 LONG ordered on bar 2, fill bar 3


def gate_acc2():
    # --- 1. break at the accum end -------------------------------------------------------------------------------
    def fd(i):
        return {1: (U, L, AID1, 1 if i < 2 else 0)}
    seq = [IN, B(4290, 4302, 4290, 4301), B(4301, 4304, 4300.5, 4303), B(4303, 4304, 4297, 4298), IN]
    r = run(seq, fd)
    ev = [e for e in r.broker.log if e[0] == "order_entry"]
    w = run(seq, fd, overrides=dict(enFixMode="Wait for Cross"))
    check("AN-01 accum end received on bar 2 whose close 4303 is already above the fixed upper 4300 (it was above while "
          "forming on bar 1: no event then) -> default: break bar = bar 2, P1 SL = max(high bar 2, bar 3) + 1.5 = 4305.5 "
          "(bar 1 not used); Wait for Cross: nothing",
          ev and ev[0][1] == 3 and exit_order(r, "X1")[4] == 4305.5 and w["nSig1"] == 0 and orders(w) == [], str(ev))
    seq = [IN, IN, B(4290, 4303, 4290, 4302), B(4302, 4303, 4297, 4298), IN]
    a, b = run(seq, fd), run(seq, fd, overrides=dict(enFixMode="Wait for Cross"))
    check("AN-02 cross on the fix bar itself (prev 4290 <= 4300 < 4302): a break in both modes", a["nSig1"] == 1 and b["nSig1"] == 1)
    seq = [IN, IN, B(4290, 4296, 4290, 4295), B(4295, 4303, 4294, 4302), B(4302, 4303, 4297, 4298), IN]
    def fd3(i):
        return {1: (U, L, AID1, 1 if i < 2 else 0)}
    a, b = run(seq, fd3), run(seq, fd3, overrides=dict(enFixMode="Wait for Cross"))
    ra = R(src=SRC_OVERRIDE).run(bars_of(seq, fd3)[:4])
    check("AN-03 fix bar inside (close 4295), next bar closes 4302 -> break on that next bar (bar 3) in both modes",
          [e.bBar for e in ra["acEvs"]] == [3] and a["nSig1"] == 1 and b["nSig1"] == 1)
    # --- 2. BE on history vs realtime ------------------------------------------------------------------------------
    # fill bar 3 at 4304.5, SL 4298.5, 1R 6 -> trigger 4310.5
    hist = run(PRE_L + [B(4304.5, 4311, 4304, 4305), B(4305, 4306, 4304.8, 4305.5)])
    rt = run(PRE_L + [B(4304.5, 4311, 4304, 4305, [4304.5, 4311, 4304, 4305]), B(4305, 4306, 4304.8, 4305.5)])
    check("AN-05 +1R reached on the entry's fill bar: realtime -> stop to 4304.5 on the 4311 tick and the LONG exits on the "
          "4304 tick of the same bar; history -> no exit in the fill bar (the bar path O-L-H-C has the low first), stop moved "
          "at its close (effective from bar 4), counted as 'BE revisit possible'",
          exits(rt) and exits(rt)[0][0] == 3 and exits(rt)[0][3] <= 4304.5 and not [x for x in exits(hist) if x[0] == 3]
          and hist.trace[3]["oStop"] == 4304.5 and hist["nBeRevisit"] == 1 and rt["nBeRevisit"] == 0,
          f"{exits(rt)} {exits(hist)} {hist['nBeRevisit']}")
    pre = PRE_L + [B(4304.5, 4305, 4304, 4304.8)]
    hist = run(pre + [B(4305, 4311, 4304, 4306), B(4306, 4307, 4303, 4304)])
    rt = run(pre + [B(4305, 4311, 4304, 4306, [4305, 4311, 4307, 4304, 4306]), B(4306, 4307, 4305, 4306)])
    check("AN-06 +1R then back to the entry inside one later bar: realtime exit at BE in that bar; history keeps the trade "
          "(exit at 4304.5 on the next bar) and counts the bar (diagnostic only, orders unchanged)",
          exits(rt)[0][0] == 4 and exits(rt)[0][3] <= 4304.5 and exits(hist)[0][0] == 5 and hist["nBeRevisit"] == 1)
    hist = run(PRE_L + [B(4304.5, 4311, 4297, 4300), IN])
    rt = run(PRE_L + [B(4304.5, 4311, 4297, 4300, [4304.5, 4311, 4306, 4304, 4297, 4300]), IN])
    check("AN-07 SL and BE in one bar (fill bar: 4311 then 4297): realtime -> BE first, exit <= 4304.5 and above the SL; "
          "history (path O-H-L-C) -> initial SL 4298.5 and the bar is counted as 'SL while +1R reached'",
          exits(rt)[0][3] <= 4304.5 and exits(rt)[0][3] > 4298.5 and exits(hist)[0][3] == 4298.5 and hist["nBeSlConf"] == 1
          and rt["nBeSlConf"] == 0, f"{exits(rt)} {exits(hist)}")
    r = run(PRE_L + [B(4304.5, 4305, 4304, 4304.8), B(4305, 4311, 4297, 4300), IN])
    check("AN-08 same conflict on a later bar (position open since bar 3): history exits at the SL, counted once",
          exits(r)[0][3] == 4298.5 and r["nBeSlConf"] == 1 and r["nBeRevisit"] == 0)

    # --- 3. TP right after the fill ---------------------------------------------------------------------------------
    # signal close 4304 -> provisional TP 4304 + 1.5 x 5.5 = 4312.25; gap fill 4306 -> exact 4306 + 1.5 x 7.5 = 4317.25
    hist = run(PRE_L + [B(4306, 4313, 4305.5, 4312), IN])
    rt = run(PRE_L + [B(4306, 4313, 4305.5, 4312, [4306, 4305.5, 4313, 4312]), IN])
    xo = [e[4:] for e in rt.broker.log if e[0] == "order_exit" and e[2] == "X1"]
    check("AN-09 gap fill (4306 vs signal 4304), fixed RR: realtime -> TP 4317.25 from the fill on the tick after the fill, "
          "the 4313 tick does not exit, SL 4298.5 never removed; history -> the provisional 4312.25 is hit inside the fill "
          "bar (counted as 'provisional TP changed the result')",
          rt.trace[3]["pos"] == 10.0 and (4298.5, 4317.25) in xo and all(x[0] == 4298.5 for x in xo)
          and exits(hist) and exits(hist)[0][3] == 4312.25 and hist["nTpProvDiff"] == 1 and rt["nTpProvDiff"] == 0, f"{xo} {exits(hist)}")
    r = run([IN, B(4295, 4303, 4294, 4302), B(4302, 4306, 4298, 4298), B(4299, 4300, 4285, 4290), IN])
    check("AN-10 boundary TP with a gap fill (4299 vs 4298): TP stays 4280, real RR from the fill, no provisional-TP count",
          exit_order(r, "X1")[5] == 4280.0 and close_eq(r.trace[3]["oRRReal"], 19 / 8.5) and r["nTpProvDiff"] == 0)
    hist = run(PRE_L + [B(4304.5, 4310, 4304, 4309), IN])
    check("AN-11 no gap (fill 4304.5): exact TP 4313.5 set at the fill bar's close, no count",
          hist.trace[3]["oTP"] == 4313.5 and hist["nTpProvDiff"] == 0)
    # --- 4. doten vs SL / TP ------------------------------------------------------------------------------------------
    seq = PRE_L + [B(4304.5, 4305, 4304, 4304.8), B(4305, 4314, 4299, 4299.5), IN]
    r = run(seq, {1: (U, 4250.0, AID1, 0)})
    check("AN-13 old TP (4313.5) filled inside the bar whose close is an upper fakeout -> flat at the close -> the SHORT is "
          "a normal entry (no doten), one position", [x[1] for x in orders(r)] == ["L1", "S2"] and r["nDoten"] == 0
          and exits(r)[0][1:4] == ("L1", "X1", 4313.5) and r.broker.max_abs_pos <= 10.0, f"{orders(r)} {exits(r)}")
    seq = PRE_L + [B(4304.5, 4306, 4304, 4305), B(4305, 4305.5, 4299, 4299.5), B(4314, 4315, 4296, 4297), IN]
    r = run(seq)
    check("AN-14 doten fill at an open that gaps through the old TP (4314 > 4313.5): the old exit was cancelled with the "
          "doten order, one reversal at the open, position = the SHORT qty only",
          r.broker.pos in (0.0, -fills(r)[-1][3]) and r.broker.max_abs_pos <= 10.0
          and len([x for x in exits(r) if x[1] == "L1"]) == 1 and [x for x in exits(r) if x[1] == "L1"][0][2] == "S2",
          f"{exits(r)} {fills(r)}")

    # --- 5. recalculation settings ------------------------------------------------------------------------------------
    seq = PRE_L + [B(4304.5, 4305, 4304, 4304.8), B(4304.8, 4305, 4297, 4299), IN, IN]
    def stopped(**kw):
        r = R(None, src=SRC_OVERRIDE, **kw)
        try:
            r.run(bars_of(seq))
        except ap.PineScriptStopped as ex:
            return r, str(ex)
        return r, None
    r, msg = stopped(recalc_fills=True)
    check("AN-15 'After order is filled' ON (history, varip kept): the 2nd execution of the fill bar stops the script "
          "(runtime.error) before any further order", msg is not None and "2 回以上" in msg and len(orders(r)) == 1, str(msg))
    r, msg = stopped(recalc_fills=True, varip_rollback=True)
    check("AN-16 same with varip rolled back (guard 1 blind): the recalc after the SL fill sees the final close (lookahead) "
          "and sends S2, which fills inside the bar; the next execution finds S2 open while its rolled-back state manages L1 -> "
          "runtime.error (no second "
          "S2 / no double position)", msg is not None and ("S2" in msg) and r.broker.max_abs_pos <= 10.0, str(msg))
    r, msg = stopped(recalc_fills=True, varip_rollback=True, recalc_confirmed=False)
    base = run(seq)
    check("AN-17 recalcs marked unconfirmed: no order and no BE from a recalc (BE on history only at the close) -> same "
          "orders / exits as the normal run", msg is None and orders(r) == orders(base) and exits(r) == exits(base))
    beseq = PRE_L + [B(4304.5, 4311, 4304, 4305), B(4305, 4306, 4304.8, 4305.5)]
    r = R(None, src=SRC_OVERRIDE, recalc_fills=True, recalc_confirmed=False, varip_rollback=True).run(bars_of(beseq))
    n = run(beseq)
    check("AN-19 history recalc after the open fill sees the bar's final high 4311 (>= trigger): the BE is NOT taken from "
          "it (history BE only at the close) -> no exit inside the fill bar, same exits as the normal run",
          exits(r) == exits(n) and not [x for x in exits(r) if x[0] == 3], f"{exits(r)} {exits(n)}")
    rtseq = PRE_L + [B(4304.5, 4311, 4304, 4305, [4304.5, 4311, 4304, 4305]), B(4305, 4306, 4304.8, 4305.5, [4305, 4306, 4304.8, 4305.5])]
    a = R(src=SRC_OVERRIDE).run(bars_of(rtseq))
    b = R(src=SRC_OVERRIDE, recalc_fills=True).run(bars_of(rtseq))
    check("AN-18 realtime ticks with 'After order is filled' ON: allowed (no stop), same orders / exits, one entry per bar",
          orders(a) == orders(b) and exits(a) == exits(b) and len(orders(b)) == 1)


# ============================================================================
# AT : ACC-3 — "On history bar tick" (calc_on_every_history_tick) against the ACC-2 Strategy
#      emulated as: historical bars replayed tick by tick, barstate.isconfirmed TRUE on every tick (the behaviour cited for the
#      setting, not verified here), var rolled back before every tick, varip kept
# ============================================================================
ACC2_REV = "936d27f"
NO_GUARD1 = ("        if acExecN > 1\n            runtime.error(", "        if false\n            runtime.error(")


def gate_acc3():
    seq = [IN + ([4290.0, 4291.0, 4289.0, 4290.0],), B(4295, 4307, 4294, 4306, [4295, 4294, 4307, 4306]),
           B(4306, 4306.5, 4299, 4299, [4306, 4302.5, 4304, 4306.5, 4299]), B(4299, 4300, 4297, 4298, [4299, 4300, 4297, 4298])]
    r = R(src=SRC_OVERRIDE, history_ticks="all_confirmed")
    try:
        r.run(bars_of(seq))
        msg = None
    except ap.PineScriptStopped as ex:
        msg = str(ex)
    check("AT-01 ACC-2 under history ticks (isconfirmed on every tick): stopped by runtime.error on the first historical bar "
          "with a 2nd execution, before any order", msg is not None and "2 回以上" in msg and r.bar_index == 0 and orders(r) == [],
          str(msg))
    if SRC_OVERRIDE is not None:
        return
    src = SRC.replace(*NO_GUARD1)
    r = R(src=src, history_ticks="all_confirmed")
    try:
        r.run(bars_of(seq))
        msg = None
    except ap.PineScriptStopped as ex:
        msg = str(ex)
    n = R().run(bars_of([x[:4] for x in seq]))
    check("AT-02 why the guard stays (guard 1 removed in memory only): the tick 4304 after the 4302.5 wick (not the bar's "
          "close) is taken as a confirmed retest -> P2 LONG sent and filled INSIDE that bar at 4306.5; the 5M close (4299) "
          "decides P1 SHORT at the next open in the normal run; the unmanaged-position guard then stops the script",
          orders(r) == [(2, "L1", 1, 10.0)] and fills(r) == [(2, "L1", 1, 10.0, 4306.5)] and msg is not None and "管理外" in msg
          and orders(n) == [(2, "S1", -1, 6.0)] and fills(n)[0][0] == 3, f"{orders(r)} {fills(r)} {msg} / {orders(n)}")
    # accum / break state alone: rolled back before every tick -> equal to the normal run at every bar end (no orders here)
    seq2 = [IN + ([4290.0, 4291.0, 4289.0, 4290.0],), B(4295, 4307, 4294, 4299, [4295, 4307, 4306, 4294, 4299]),
            B(4299, 4303, 4279.5, 4285, [4299, 4303, 4279.5, 4280, 4285]), IN + ([4290.0, 4291.0, 4289.0, 4290.0],)]
    def feed(i):
        return {1: (U, L, AID1, 1 if i < 1 else 0)}
    a = R(src=src, history_ticks="all_confirmed")
    b = R()
    same = True
    for x, y in zip(bars_of(seq2, feed), bars_of([z[:4] for z in seq2], feed)):
        a.step(x)
        b.step(y)
        if repr(a["acBoxes"]) != repr(b["acBoxes"]) or repr(a["acEvs"]) != repr(b["acEvs"]) or a["acSeq"] != b["acSeq"]:
            same = False
    check("AT-03 accum and break-event state under history ticks (guard 1 removed, var rolled back before every tick): equal to "
          "the normal run at every bar end although intermediate ticks cross the boundaries -> the state is not broken; the "
          "orders are (AT-02)", same and orders(a) == [] and orders(b) == [])
    show = lambda rev, path: subprocess.run(["git", "-C", ROOT, "show", f"{rev}:{path}"], capture_output=True, text=True).stdout
    probe = raw("AccHistTickProbe.pine")
    check("AT-04 ACC-3 kept the ACC-2 Strategy byte for byte (525756f == 936d27f; ACC-4 changes are pinned by AV); the probe is "
          "unchanged since ACC-3, a separate file with no trading by default (prOrders false) and no link to the Strategy",
          show(ACC3_REV, "AccumStrategyXAU.pine") == show(ACC2_REV, "AccumStrategyXAU.pine") and probe == show(ACC3_REV, "AccHistTickProbe.pine")
          and 'prOrders = input.bool(false,' in probe and "import " not in code_only(probe)
          and "AccumStrategyXAU" not in code_only(probe) and "strategy.entry(" in probe)


def gate_acc2_series():
    """ACC-2 checks over random series (kept out of the mutation loop for run time)."""
    # no unconfirmed HTF information: real formula, fix bar = first 5M bar after the close of the HTF bar that ended the accum
    import nr_a1_sim as nas
    ok_fix, ok_ev, n_chk, det = True, True, 0, ""
    for seed in (3, 7):
        b5 = nas.market(seed, 30)
        feeds = feeds_from_5m(nas, b5)
        bars = [dict(t=t, o=o, h=h, l=l, c=c, feed=feeds[i]) for i, (t, o, h, l, c) in enumerate(b5)]
        exp = {}
        for k_tf, (name, tf, day) in enumerate(nas.TFS):
            htf = nas.htf_from_5m(b5, tf, day)
            com = htf_committed(nas, htf)
            for k in range(len(com) - 1):
                top, bot, sid, acc = com[k]
                if sid is not None and acc == 0 and (k_tf, sid) not in exp and (k == 0 or com[k - 1][2] != sid or com[k - 1][3] == 1):
                    nxt = htf[k + 1]
                    exp[(k_tf, sid)] = (htf[k]["C"], nxt["T"] + nxt["slots"][0] * M5)
        rr = R(dict(seUse=False))
        fixes, idx = {}, {}
        for i, bb in enumerate(bars):
            rr.step(bb)
            idx[bb["t"]] = i
            for x in rr["acBoxes"] + rr["acDrawn"]:
                if x.fixed:
                    fixes.setdefault((x.tf, x.aid), x.fixTime)
            for e in rr["acEvs"]:
                fx = fixes.get((e.tf, e.aid))
                if fx is None or e.bBar < idx[fx]:
                    ok_ev, det = False, f"seed {seed} event {e}"
        for key, fx in fixes.items():
            if key in exp:
                n_chk += 1
                hclose, first5 = exp[key]
                if fx != first5 or fx < hclose:
                    ok_fix, det = False, f"seed {seed} {key}: fix {fx} expected {first5} (HTF close {hclose})"
    check("AN-04 no unconfirmed HTF data (real formula, 2 series): every accum is fixed exactly on the first 5M bar opening "
          "at / after the close of the HTF bar that ended it, and no break event starts before its accum's fix bar",
          ok_fix and ok_ev and n_chk > 5, f"{det} checked={n_chk}")

    # protection never missing: at every bar end, an open trade has an exit order with a stop
    import nr_a1_sim as nas2
    gaps_ok = True
    for seed in (31, 32):
        b5 = nas2.market(seed, 20)
        feeds = feeds_from_5m(nas2, b5)
        rr = R(dict(seUse=False))
        for i, (t, o, h, l, c) in enumerate(b5):
            rr.step(dict(t=t, o=o, h=h, l=l, c=c, feed=feeds[i]))
            for tr_ in rr.broker.open_trades:
                if not any(x["from_id"] == tr_["id"] and x["stop"] is not None for x in rr.broker.exits.values()):
                    gaps_ok = False
    check("AN-12 random series: every open trade has its stop order at every bar end (SL never interrupted by TP updates)", gaps_ok)



# ============================================================================
# AQ : ACC-4 — P5 upper range rebound SHORT / P6 lower range rebound LONG (ACC-4 defaults: P1..P4 OFF, P5 P6 ON, doten OFF)
# ============================================================================
FR = {1: (4300.0, 4250.0, AID1, 0)}          # 1H accum 4300 / 4250, fixed on bar 0
M = B(4275, 4276, 4274, 4275)                 # middle of the range
BU = B(4280, 4283, 4279, 4282)                # bullish bar in the middle (no P5, no contact)
BD = B(4270, 4271, 4266, 4267)                # bearish bar in the middle (no P6, no contact)


def run4(seq, feed=FR, overrides=None, times=None, t0=T0):
    return ap.Runner(overrides, src=SRC_OVERRIDE).run(bars_of(seq, feed, t0, times))


def pats(r):
    return [(o[0], o[1][0], r.trace[o[0]]["oPat"]) for o in orders(r)]


def gate_acc4():
    r = run4([M, B(4296, 4298, 4291, 4292), M])
    check("AQ-01 contact bar (high 4298 >= 4297, close 4292 inside) closes bearish -> P5 on that bar (0本目): SHORT, SL = "
          "4300 + 1.5, TP = the same accum's lower 4250 (RR 42 / 9.5), next-open order",
          pats(r) == [(1, "S", 5)] and exit_order(r, "X1")[4:] == (4301.5, 4250.0) and r["nTouch5"] == 1 and r["nSig5"] == 1
          and r["nEnt5"] == 1 and fills(r)[0][0] == 2, f"{pats(r)} {exit_order(r, 'X1')}")
    r = run4([M, B(4292, 4298, 4291, 4296), BU, BU, BU, B(4288, 4289, 4284, 4285), M])
    check("AQ-02 contact bar bullish -> wait; the price moves away (bars at 4280: wait kept, no distance cancel); bearish close "
          "4285 on bar 5 -> P5", pats(r) == [(5, "S", 5)] and r["nTouch5"] == 1, str(pats(r)))
    r = run4([M, B(4254, 4259, 4252, 4257), M])
    check("AQ-03 contact bar (low 4252 <= 4253) closes bullish -> P6: LONG, SL = 4250 - 1.5, TP = the same accum's upper 4300",
          pats(r) == [(1, "L", 6)] and exit_order(r, "X1")[4:] == (4248.5, 4300.0) and r["nTouch6"] == 1, str(pats(r)))
    r = run4([M, B(4256, 4258, 4252, 4254), BD, BD, BD, B(4262, 4266, 4261, 4265), M])
    check("AQ-04 contact bar bearish -> wait; later bullish close 4265 -> P6", pats(r) == [(5, "L", 6)], str(pats(r)))
    a = run4([M, B(4298, 4303, 4294, 4295), M])
    b = run4([M, B(4252, 4256, 4247, 4255), M])
    check("AQ-05 wick through the boundary with the close inside is valid: high 4303 / close 4295 bearish -> P5; low 4247 / "
          "close 4255 bullish -> P6", pats(a) == [(1, "S", 5)] and pats(b) == [(1, "L", 6)])
    a = run4([M, B(4302, 4303, 4299, 4300), B(4299, 4299.5, 4294, 4295), M], overrides=dict(rkBuf=3.0))
    b = run4([M, B(4248, 4253, 4247, 4250), B(4251, 4256, 4250.5, 4255), M], overrides=dict(rkBuf=3.0))
    check("AQ-06 close exactly on the boundary (4300 bearish / 4250 bullish; SL Buffer 3 so the SL width 3 would pass): no "
          "signal on that bar (not inside, not a break: the contact starts) -> the next inside rebound bar gives P5 / P6", pats(a) == [(2, "S", 5)] and pats(b) == [(2, "L", 6)]
          and a["nRgBrk"] == 0)
    t12 = run4([M, B(4292, 4298, 4291, 4296)] + [BU] * 11 + [B(4288, 4289, 4284, 4285), M])
    t13 = run4([M, B(4292, 4298, 4291, 4296)] + [BU] * 12 + [B(4288, 4289, 4284, 4285), M])
    check("AQ-07 bearish rebound on bar 12 after the contact -> P5 (bar 13 order); on bar 13 -> expired (no order, one expiry)",
          pats(t12) == [(13, "S", 5)] and pats(t13) == [] and t13["nRgExp"] == 1 and t12["nRgExp"] == 0, f"{pats(t12)} {pats(t13)}")
    near = B(4292, 4298, 4291, 4296)
    r = run4([M, near, BU, BU, BU, BU, near] + [BU] * 7 + [B(4288, 4289, 4284, 4285), M])
    check("AQ-08 a 2nd touch on bar 6 does not restart or extend the wait: the rebound on bar 14 (13 after the 1st contact) "
          "-> expired", pats(r) == [] and r["nTouch5"] == 1 and r["nRgExp"] == 1, str(pats(r)))
    r = run4([M, B(4296, 4298, 4291, 4292), B(4292, 4302, 4291, 4295), B(4296, 4298, 4290, 4291), B(4291, 4296, 4288, 4290),
              B(4294, 4298, 4290, 4291), M])
    check("AQ-09 after an order the contact is used: SL hit on bar 2 (flat), bar 3 touches again bearish -> nothing (not "
          "re-armed); bar 4 high 4296 < 4297 re-arms (no contact on that bar); bar 5 touches bearish -> new contact -> P5",
          pats(r) == [(1, "S", 5), (5, "S", 5)] and r["nTouch5"] == 2 and exits(r)[0][1:4] == ("S1", "X1", 4301.5), str(pats(r)))
    zone_bull = B(4296, 4298, 4295, 4297.5)
    r = run4([M, B(4292, 4298, 4291, 4296)] + [zone_bull] * 13 + [B(4298, 4298.5, 4294, 4295), B(4295, 4296, 4293, 4295.5),
                                                                    B(4296, 4298, 4292, 4293), M])
    check("AQ-10 expiry with the price still in the zone: no new contact (bar 15 bearish -> nothing); a bar with high < 4297 "
          "re-arms; the next touch (bar 17) -> P5", pats(r) == [(17, "S", 5)] and r["nTouch5"] == 2 and r["nRgExp"] == 1, str(pats(r)))
    r = run4([M, B(4292, 4298, 4291, 4296), B(4297, 4303, 4296, 4302), B(4301, 4302, 4294, 4295), M])
    check("AQ-11 close above the upper (4302) cancels the wait; the bearish return bar (4295, high 4302) gives no P5",
          pats(r) == [] and r["nRgBrk"] == 1, str(pats(r)))
    r = run4([M, B(4292, 4298, 4291, 4296), B(4280, 4281, 4245, 4248), B(4262, 4263, 4255, 4258), M])
    check("AQ-12 close below the lower (4248) cancels the P5 wait of the same accum too", pats(r) == [] and r["nRgBrk"] == 1, str(pats(r)))
    r = run4([M, B(4296, 4306, 4295, 4305), B(4305, 4306, 4294, 4295), B(4294, 4296, 4290, 4292), B(4293, 4298, 4289, 4290), M])
    check("AQ-13 break (close 4305) then return inside (4295, bearish): no P5 on the return bar; high 4296 re-arms; the next "
          "touch (high 4298, bearish) -> P5 - with P1..P4 OFF", pats(r) == [(4, "S", 5)] and r["nTouch5"] == 1, str(pats(r)))
    exp_t = T0 + 3 * D1
    r = run4([M, B(4296, 4298, 4291, 4292), M], times=[T0, exp_t + M5, exp_t + 2 * M5])
    check("AQ-14 expired accum (fixed T0, touch at T0 + 3 days + 5 min): no new contact", pats(r) == [] and r["nTouch5"] == 0)
    r = run4([M, B(4292, 4298, 4291, 4296), BU, BU, B(4288, 4289, 4284, 4285), M],
             times=[T0, exp_t - 10 * 60000, exp_t - 5 * 60000, exp_t, exp_t + M5, exp_t + 2 * M5])
    check("AQ-15 a wait started before the expiry continues after it: rebound at T0 + 3 days + 5 min -> P5 with the saved lower "
          "4250 as TP (the accum is gone from the registry)", pats(r) == [(4, "S", 5)] and exit_order(r, "X1")[5] == 4250.0
          and r["acBoxes"] == [], str(pats(r)))
    def fk(i):
        return {1: (4300.0, 4250.0, AID1, 0)} if i < 3 else {1: (4400.0, 4350.0, AID1 + H1, 0)}
    r = run4([M, B(4292, 4298, 4291, 4296), BU, BU, B(4288, 4289, 4284, 4285), M], fk, overrides=dict(acKeep1=1))
    check("AQ-16 Keep Count (1H keep 1): a newer 1H accum on bar 3 pushes the touched one out; its wait continues -> P5 on bar 4 "
          "with the saved SL 4301.5 / TP 4250", pats(r) == [(4, "S", 5)] and exit_order(r, "X1")[4:] == (4301.5, 4250.0), str(pats(r)))
    r = run4([M, BU, BU, BU, B(4296, 4298, 4291, 4292), M], fk, overrides=dict(acKeep1=1))
    check("AQ-17 after the Keep Count exclusion no new contact on the excluded accum", pats(r) == [] and r["nTouch5"] == 0)
    r = run4([B(4296, 4298, 4291, 4292), M, B(4296, 4298, 4291, 4292), M])
    check("AQ-18 no contact on the bar that fixes the accum (bar 0, bearish touch); from the next bar (bar 2) -> P5",
          pats(r) == [(2, "S", 5)] and r["nTouch5"] == 1, str(pats(r)))
    r = run4([M, B(4292, 4298, 4291, 4296), B(4299.9, 4299.95, 4299.5, 4299.6), B(4297, 4297.5, 4292, 4293), M])
    check("AQ-19 SL width 1.9 (< 2, P5 / P6 minimum) -> skipped without consuming the contact; the next rebound -> P5",
          pats(r) == [(3, "S", 5)] and r["nSkipSl56"] == 1 and r["nSkipSl"] == 0, str(pats(r)))
    r = run4([M, B(4292, 4298, 4291, 4296), B(4274, 4275, 4270, 4271), M])
    check("AQ-20 SL width 30.5 (> 30) -> skipped", pats(r) == [] and r["nSkipSl56"] == 1)
    r = run4([M, B(4297, 4298, 4295, 4296), M], {1: (4300.0, 4290.0, AID1, 0)})
    check("AQ-21 RR 6 / 5.5 = 1.09 (< 1.5, TP = the same accum's lower 4290, no other boundary used) -> skipped",
          pats(r) == [] and r["nSkipRR56"] == 1 and r["nSkipRR"] == 0)
    r = run4([M, B(4254, 4259, 4252, 4257), B(4257, 4270, 4256, 4268), B(4268, 4290, 4267, 4289), B(4289, 4298, 4288, 4296),
              B(4296, 4298.5, 4292, 4293), B(4293, 4300.5, 4292, 4299), B(4299, 4299.5, 4294, 4295), M])
    check("AQ-22 while a P6 LONG is held (doten OFF), the P5 contact (bar 4) and its bearish rebound (bar 5) are recorded but not "
          "used; the LONG reaches its TP 4300 on bar 6; the bearish bar 7 (same wait, age 3) -> P5 SHORT; one position at a time",
          pats(r) == [(1, "L", 6), (7, "S", 5)] and exits(r)[0][1:4] == ("L1", "X1", 4300.0) and r["nSig5"] == 2
          and r.broker.max_abs_pos <= 12.0 and r["nDoten"] == 0, f"{pats(r)} {exits(r)}")
    seq = [M, B(4276, 4296, 4275, 4295.5), B(4297, 4298, 4292.5, 4294), B(4294, 4295, 4287, 4288), M]
    r = run4(seq, {1: (4300.0, 4250.0, AID1, 0), 2: (4290.0, 4200.0, AID1, 0)}, overrides=dict(enP2=True, rkTpAcc=False))
    check("AQ-23 P5 SHORT (1H) and P2 LONG (4H retest) valid on the same bar -> both skipped, the P5 contact is kept; the next "
          "bearish bar -> P5", [x[:2] for x in pats(r)] == [(3, "S")] and pats(r)[0][2] == 5 and r["nConflict"] == 1, str(pats(r)))
    hist = run4([M, B(4292, 4298, 4291, 4296), BU, B(4288, 4289, 4284, 4285), M])
    rt = run4([M + ([4275.0, 4276.0, 4274.0, 4275.0],), B(4292, 4298, 4291, 4296, [4292, 4291, 4298, 4296]),
               B(4280, 4283, 4279, 4282, [4280, 4279, 4283, 4282]), B(4288, 4289, 4284, 4285, [4288, 4289, 4284, 4285]),
               M + ([4275.0, 4276.0, 4274.0, 4275.0],)])
    rt2 = run4([M, B(4292, 4298, 4291.5, 4296, [4292, 4298, 4291.5, 4296]), B(4288, 4289, 4284, 4285, [4288, 4284, 4289, 4285]), M])
    check("AQ-24 realtime ticks vs history: same contact / wait / order (the state changes only on the confirmed tick); a "
          "bearish moment inside the touching bar (tick 4291.5 < open 4292, bar closes bullish 4296) sends nothing", pats(rt) == pats(hist) == [(3, "S", 5)] and rt["nTouch5"] == 1
          and pats(rt2) == [(2, "S", 5)] and orders(rt2)[0][0] == 2, f"{pats(rt)} {pats(hist)} {pats(rt2)}")
    r = run4([M, B(4299, 4299.5, 4297, 4298.5), M])
    check("AQ-26 SL width 3 (between the P5 / P6 minimum 2 and the P1..P4 minimum 5) -> taken (P5 / P6 use their own minimum)",
          pats(r) == [(1, "S", 5)] and exit_order(r, "X1")[4] == 4301.5, str(pats(r)))
    r = run4([M, B(4296, 4298, 4291, 4292), M], overrides=dict(enP5=False))
    check("AQ-25 P5 OFF: the contact is still recorded, no order", pats(r) == [] and r["nTouch5"] == 1 and r["nSig5"] == 0)



# ============================================================================
# AV : ACC-4 — the ACC-3 file vs ACC-4 with P5 / P6 OFF (the P1..P4 / doten / BE / money behaviour unchanged); random series
# ============================================================================
AV_COUNTERS = ("nSig1", "nSig2", "nSig3", "nSig4", "nEnt1", "nEnt2", "nEnt3", "nEnt4", "nSkipSl", "nSkipRR", "nSkipSess",
               "nSkipQty", "nConflict", "nDoten", "nBE", "nBadExit", "nQtyAnom", "nBeRevisit", "nBeSlConf", "nTpProvDiff")


def gate_acc4_series():
    import nr_a1_sim as nas
    old_src = subprocess.run(["git", "-C", ROOT, "show", f"{ACC3_REV}:AccumStrategyXAU.pine"], capture_output=True, text=True).stdout
    settings = [dict(), dict(dtOn=False), dict(enP2=False, enP3=False, enP4=False), dict(enP1=False, enP3=False, enP4=False),
                dict(enP1=False, enP2=False, enP4=False), dict(enP1=False, enP2=False, enP3=False)]
    same, n_ord, det = True, 0, ""
    for seed in (41, 42):
        b5 = nas.market(seed, 20)
        feeds = feeds_from_5m(nas, b5)
        bars = [dict(t=t, o=o, h=h, l=l, c=c, feed=feeds[i]) for i, (t, o, h, l, c) in enumerate(b5)]
        for ov in (settings if seed == 41 else settings[:2]):
            a = ap.Runner(dict(ov, seUse=False), src=old_src).run(bars)
            b = ap.Runner(dict(ACC3_OV, **ov, seUse=False)).run(bars)
            n_ord += len(orders(a))
            if a.broker.log != b.broker.log or any(a[k] != b[k] for k in AV_COUNTERS):
                same, det = False, f"seed {seed} {ov}"
    check("AV-01 P1..P4 unchanged: the ACC-3 file (525756f) and ACC-4 with P5 / P6 OFF give the identical broker log (orders, "
          "exits, cancels, fills) and counters on random series - all of P1..P4, doten OFF, and each of P1 / P2 / P3 / P4 alone",
          same and n_ord > 0, f"{det} orders={n_ord}")
    inv, n56, det = True, 0, ""
    for seed, ov in ((43, {}), (44, dict(enP1=True, enP2=True, enP3=True, enP4=True, dtOn=True)), (45, dict(enP5=False)),
                     (46, dict(enP6=False))):
        b5 = nas.market(seed, 20)
        feeds = feeds_from_5m(nas, b5)
        bars = [dict(t=t, o=o, h=h, l=l, c=c, feed=feeds[i]) for i, (t, o, h, l, c) in enumerate(b5)]
        try:
            r = ap.Runner(ov).run(bars)
        except ap.PineScriptStopped as ex:
            inv, det = False, f"seed {seed}: stopped {ex}"
            continue
        n56 += r["nEnt5"] + r["nEnt6"]
        per = {}
        for o in orders(r):
            per[o[0]] = per.get(o[0], 0) + 1
        maxq = max([o[3] for o in orders(r)] or [0])
        xs = {e[3] for e in r.broker.log if e[0] == "order_exit"}
        ids = [o[1] for o in orders(r)]
        if (r.broker.max_abs_pos > maxq + 1e-9 or any(v > 1 for v in per.values()) or any(f[1] not in xs for f in fills(r))
                or len(ids) != len(set(ids)) or r["nQtyAnom"] != 0):
            inv, det = False, f"seed {seed} {ov}"
        if ov.get("enP5") is False and r["nEnt5"] != 0 or ov.get("enP6") is False and r["nEnt6"] != 0:
            inv, det = False, f"seed {seed}: disabled pattern ordered"
    check("AV-02 random series with P5 / P6 ON (ACC-4 defaults; all six + doten ON; P5 only; P6 only): one position, one order per "
          "bar, every fill protected from the signal bar, unique order IDs, no unmanaged position / stop, a disabled pattern never "
          "orders", inv and n56 > 0, f"{det} P5+P6 orders={n56}")


# ============================================================================
# AU : mutations of the Pine text are caught by the scenario gates
# ============================================================================
MUTATIONS = [
    ("fakeout on an equal close", "bool fake = e.dir == 1 ? close < e.lvl : close > e.lvl",
     "bool fake = e.dir == 1 ? close <= e.lvl : close >= e.lvl"),
    ("window 23 bars (off by one)", "if age > enRetestBars", "if age >= enRetestBars"),
    ("P2 / P4 without the deviation", "bool rt = e.dev and (", "bool rt = true and ("),
    ("retest proximity strict", "low - e.lvl <= enNear + EPS", "low - e.lvl < enNear - EPS"),
    ("retest on the deviation bar", "if not e.dev and e.dir * (close - e.lvl) >= enDev - EPS\n                            e.dev    := true",
     "if false\n                            e.dev    := true"),
    ("break by the wick", "if close > b.up and (", "if high > b.up and ("),
    ("break without the cross", "((not na(acPrevClose) and acPrevClose <= b.up) or atFix)", "true"),
    ("SL extreme without the fakeout bar", "e.ext := e.dir == 1 ? math.max(e.ext, high) : math.min(e.ext, low)",
     "e.ext := e.ext"),
    ("TP boundary below the minimum RR accepted", "if c.rr < rkRR - EPS", "if c.rr < 0"),
    ("TP capped at the fixed RR", "c.tp     := bnd", "c.tp     := ref + side * rkRR * slw"),
    ("SL width upper bound ignored", "if slw < rkMinSl - EPS or slw > rkMaxSl + EPS", "if slw < rkMinSl - EPS"),
    ("priority 1H first", "a.tf != b.tf ? a.tf > b.tf", "a.tf != b.tf ? a.tf < b.tf"),
    ("no LONG / SHORT conflict skip", "if not na(bestL) and not na(bestS)\n            nConflict += 1\n        else if not na(bestL)",
     "if false\n            nConflict += 1\n        else if not na(bestL)"),
    ("session by the signal bar's open", "f_inSession(time_close)", "f_inSession(time)"),
    ("doten regardless of the input", "bool  rev  = dtOn and", "bool  rev  = true and"),
    ("BE at 2R", "float trig = oFill + oSide * beR * r1", "float trig = oFill + oSide * 2 * beR * r1"),
    ("fixed-RR TP not rebuilt from the fill", "                oTP := oFill + oSide * rkRR * risk\n",
     "                oTP := oTP\n"),
    ("expired accum registered again", "if na(last) or aid != last", "if f_findBox(k, aid) < 0"),
    ("fixed USDJPY 150 instead of strategy.convert_to_symbol", "strategy.convert_to_symbol(budget)", "budget / 150.0"),
    ("minimum lot ignored", "if n >= 1 and n * mmLotStep >= mmLotMin * (1 - 1e-9)", "if n >= 0"),
    ("ACC-2 default back to Wait for Cross", 'enFixMode = input.string("Start at Fix",', 'enFixMode = input.string("Wait for Cross",'),
    ("ACC-2 history multi-execution guard removed", "        if acExecN > 1\n            runtime.error(", "        if false\n            runtime.error("),
    ("ACC-2 unmanaged position guard removed", "        if otId != oId\n", "        if false\n"),
    ("ACC-2 BE from history recalcs", "and (not barstate.ishistory or barstate.isconfirmed)", "and true"),
    ("ACC-4 P5 on an equal close", "                else if close < w.up and close > w.lo\n", "                else if close <= w.up and close >= w.lo\n"),
    ("ACC-4 P5 without the bearish close", "if w.side == -1 and close < open and enP5", "if w.side == -1 and enP5"),
    ("ACC-4 wait 13 bars (off by one)", "if rage > rgWait", "if rage > rgWait + 1"),
    ("ACC-4 contact not consumed by the order", "                            if wj.id == pick.rtId\n", "                            if false\n"),
    ("ACC-4 no re-arm needed", "                            if b.armU and high >= b.up - rgNear - EPS", "                            if high >= b.up - rgNear - EPS"),
    ("ACC-4 contact on the fix bar", "if f_valid(b) and time > b.fixTime and close <= b.up", "if f_valid(b) and close <= b.up"),
    ("ACC-4 break does not cancel the wait", "                if close > w.up or close < w.lo\n", "                if false\n"),
    ("ACC-4 P5 / P6 minimum SL = P1..P4 minimum", "    if slw < rgMinSl - EPS or slw > rkMaxSl + EPS", "    if slw < rkMinSl - EPS or slw > rkMaxSl + EPS"),
]


def gate_mutation():
    global SRC_OVERRIDE, RESULTS
    keep = RESULTS
    caught, missed = 0, []
    try:
        for name, old, new in MUTATIONS:
            if SRC.count(old) != 1:
                missed.append(name + " (pattern not found once)")
                continue
            SRC_OVERRIDE = SRC.replace(old, new)
            RESULTS = []
            for g in (gate_entry, gate_risk, gate_orders, gate_acc2, gate_acc3, gate_acc4):
                try:
                    g()
                except Exception:      # noqa: BLE001
                    RESULTS.append(("crash", False, ""))
            if any(not ok for _, ok, _ in RESULTS):
                caught += 1
            else:
                missed.append(name)
    finally:
        SRC_OVERRIDE, RESULTS = None, keep
    check(f"AU-01 every one of {len(MUTATIONS)} mutations of the Pine logic (equality, window, deviation, proximity, wick "
          "break, cross, SL extreme, TP rules, SL bounds, priority, conflict, session, doten, BE, fill-based TP, re-registration, "
          "USDJPY conversion, minimum lot) makes at least one scenario check fail", caught == len(MUTATIONS) and not missed, str(missed))


def main():
    for g in (gate_static, gate_accum, gate_entry, gate_risk, gate_orders, gate_acc2, gate_acc3, gate_acc4, gate_acc2_series, gate_acc4_series, gate_fuzz, gate_mutation):
        try:
            g()
        except Exception:      # noqa: BLE001
            import traceback
            check(f"{g.__name__} completed without error", False, traceback.format_exc()[-1500:])
    w = max(len(n) for n, _, _ in RESULTS)
    fails = 0
    for n, ok, d in RESULTS:
        fails += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {n.ljust(w)[:180]}  {'' if ok else d}")
    print(f"\n{len(RESULTS) - fails}/{len(RESULTS)} passed  [PINE_NOT_VERIFIED: static / translated Pine logic + emulator]")
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
