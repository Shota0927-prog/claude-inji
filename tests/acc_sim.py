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
                enP1=True, enP2=True, enP3=True, enP4=True, enRetestBars=24, enDev=5.0, enNear=3.0,
                rkBuf=1.5, rkMinSl=5.0, rkMaxSl=30.0, rkRR=1.5, rkTpAcc=True, beOn=True, beR=1.0, dtOn=True,
                seUse=True, seTz="Asia/Tokyo", seStartH=9, seStartM=0, seEndH=2, seEndM=0,
                mmCapBase=300000.0, mmRiskPct=3.0, mmLotOz=100.0, mmLotMin=0.01, mmLotStep=0.01)
    diff = {k: (inp.get(k), v) for k, v in want.items() if inp.get(k) != v}
    check("AS-07 input defaults as specified (TF / Keep / expiry / detection / entry / SL / TP / BE / doten / session / money)",
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
    others = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", BASE_REV, "--", ".", ":!AccumStrategyXAU.pine",
                             ":!tests/acc_sim.py", ":!tests/acc_pine.py", ":!ACCUM_STRATEGY_XAU_ja.md"],
                            capture_output=True, text=True).stdout.split()
    check("AS-10 no other file of the repository changed vs 890498e (existing Strategies / Engines / tests untouched)",
          others == [], str(others))
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
    return ap.Runner(overrides, usdjpy=usdjpy, src=SRC_OVERRIDE).run(bars_of(seq, feed, t0, times))


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
    r = ap.Runner().run(bars_of(seq, feed)[:2])
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
        r = ap.Runner(dict(seUse=False))
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
        rp = ap.Runner(dict(seUse=False)).run(bars[:cut])
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
    r1 = run(seq, feed6)
    r2 = run(seq, feed6, overrides=dict(enFixMode="Start at Fix"))
    check("AE-21 already outside when fixed (close 4302 since bar 1, fixed on bar 2): Wait for Cross -> no event / no P1; "
          "Start at Fix -> event from the fix bar, P1 on bar 3", r1["nSig1"] == 0 and r2["nSig1"] == 1)
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
    for seed, ov in ((11, {}), (12, dict(dtOn=False)), (13, dict(enFixMode="Start at Fix", seUse=False)),
                     (14, dict(rkTpAcc=False, beOn=False))):
        b5 = nas.market(seed, 30)
        feeds = feeds_from_5m(nas, b5)
        bars = [dict(t=t, o=o, h=h, l=l, c=c, feed=feeds[i]) for i, (t, o, h, l, c) in enumerate(b5)]
        r = ap.Runner(ov).run(bars)
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
            for g in (gate_entry, gate_risk, gate_orders):
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
    for g in (gate_static, gate_accum, gate_entry, gate_risk, gate_orders, gate_fuzz, gate_mutation):
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
