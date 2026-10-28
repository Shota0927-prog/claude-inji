"""EAB fixtures — automation/xau_short/bridge/ea_bridge.py (stage 3: receiver -> bridge -> demo EA, file exchange).

  EAB-01..05 : claim + one command file for an eligible SHORT MARKET SATS ENTRY only; duplicates / re-sends / two bridges never
               write a second command; LIMIT / CURRENT / PROV / WAIT_* / BAR / TV_* / TP_SET / BE_MOVE / CLOSE_REQ / CANCEL never do
  EAB-06..09 : deadline 60 s (before the claim, at the claim decision after a delay, never a negative age), order inversion
  EAB-10..13 : bridge crash / restart at every step, receiver restart, EA offline / exchange folder unavailable
  EAB-14..16 : EA report ingestion (states, separate times, tickets, unknown, malformed), divergences recorded only
  EAB-17..19 : the receiver's real data is not rewritten (receipts / facts / config), files carry no secrets, single instance
  EAB-20     : end-to-end with the EA reference model (tests/ea_model.py) over the same cmd / rpt files: DRY_RUN, demo send, restart
  EAB-21     : make_test_entry.py writes only into a TEST receiver folder
  EAB-22..28 : regressions of the ST3-1 review: post-claim revocation before / while the EA asks / after a bridge restart, GO once per
               key within the deadline, an emergency close request is not a close, EA / bridge heartbeats, DB upgrade
  EAB-29     : ST3-2 re-review: POSITION_UPDATED (fill in parts) and CLOSE_REQUIRED in the lifecycle
  EAB-30..32 : ST3-6 (fixes found on the user's Windows PC): the real CLI (main -> setup_log -> once / status / run -> heartbeat) in a
               subprocess; the heartbeat replacement retried only for known sharing errors within 250 ms (GO answers never); command
               files named *.entry.txt (MQL5 refused *.cmd with error 5002 on Windows — a Linux file system cannot show that limit, so
               the MQL5 / Windows behaviour stays a separate check on the PC), old *.cmd reported, not moved
Evidence class: local Python only. No TradingView / Windows / MT5 run; the EA side is the Python reference model, not the MQL5 EA.
"""
import hashlib
import json
import logging
import os
import re
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BDIR = os.path.join(ROOT, "automation", "xau_short", "bridge")
RDIR = os.path.join(ROOT, "automation", "xau_short", "receiver")
sys.path.insert(0, BDIR)
sys.path.insert(0, RDIR)
sys.path.insert(0, os.path.join(RDIR, "samples"))
import ea_bridge as eb           # noqa: E402
import xau_receiver as xr        # noqa: E402
import make_samples as ms        # noqa: E402
import ea_model as em            # noqa: E402

RESULTS = []
QUIET = logging.getLogger("eab_sim_quiet")
QUIET.addHandler(logging.NullHandler())
QUIET.propagate = False


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


class Clock:
    def __init__(self, t, step=0):
        self.t, self.step = t, step

    def __call__(self):
        v = self.t
        self.t += self.step
        return v


def E(i, **k):
    return ms.ev("ENTRY", i, otype=k.pop("otype", "MARKET"), px=k.pop("px", 2600.0), sl=k.pop("sl", 2605.0), tp=k.pop("tp", 2592.5),
                 info=k.pop("info", "SATS_NOW"), **k)


class Env:
    """a temp tree: receiver data / bridge data / MT5 common exchange folder (all separate from any real folder)."""

    def __init__(self):
        self.tmp = tempfile.mkdtemp(prefix="eab_")
        self.rdata = os.path.join(self.tmp, "receiver_data_test")
        self.bdata = os.path.join(self.tmp, "bridge_data_test")
        self.xdir = os.path.join(self.tmp, "Common", "Files", "XauShortDemo")
        self.rcv = None
        self.bridges = []

    def receiver(self, clock=None):
        cfg = xr.load_config(None)
        cfg["data_dir"] = self.rdata
        self.rcv = xr.Receiver(cfg, log=QUIET, clock=clock)
        return self.rcv

    def send(self, m, at):
        return self.rcv.process(json.dumps(m, separators=(",", ":")), now_ms=at)["status"]

    def bridge(self, clock, bdata=None, lock=True, **over):
        """require_ea_heartbeat_ms is off unless a fixture sets it (the claim / command fixtures have no EA running)."""
        cfg = eb.load_config(None)
        cfg.update(receiver_data_dir=self.rdata, bridge_data_dir=bdata or self.bdata, exchange_dir=self.xdir, require_ea_heartbeat_ms=None)
        cfg.update(over)
        b = eb.Bridge(cfg, clock=clock, log=QUIET, lock=lock)
        self.bridges.append(b)
        return b

    def cmds(self, sub="cmd"):
        d = os.path.join(self.xdir, sub)
        return sorted(n for n in os.listdir(d)) if os.path.isdir(d) else []

    def read_cmd(self, name, sub="cmd"):
        with open(os.path.join(self.xdir, sub, name), encoding="ascii") as f:
            return dict(l.rstrip("\n").split("=", 1) for l in f)

    def close(self):
        for b in self.bridges:
            try:
                b.close()
            except Exception:
                pass
        if self.rcv:
            self.rcv.store.db.close()
        shutil.rmtree(self.tmp, ignore_errors=True)


def life(b, key):
    r = b._row(key)
    return dict(r) if r else None


def gate_claim():
    env = Env()
    try:
        env.receiver()
        m = E(3)
        bc = m["bar_close"]
        env.send(m, bc + 1500)
        b = env.bridge(Clock(bc + 2000))
        n = b.once()
        files = env.cmds()
        c = env.read_cmd(files[0]) if files else {}
        it = env.rcv.store.one("SELECT * FROM intents WHERE key=?", (m["key"],))
        lg = env.rcv.store.all("SELECT * FROM claim_log WHERE key=?", (m["key"],))
        L = life(b, m["key"])
        kh = hashlib.sha256(m["key"].encode()).hexdigest()[:16]
        check("EAB-01 an eligible SHORT MARKET SATS_NOW ENTRY 2 s after its bar close: claimed once in the receiver DB (claimed_ms, claim_log ok), "
              "ONE command file <bar_close>_<sha256(key)[:16]>.entry.txt (ST3-6; no .tmp left) with the key, key hash, prices, bar close, sid, cfg hash, "
              "TradingView symbol; bridge lifecycle CMD_WRITTEN with separate received / checked / claim start / claimed / written times",
              n == 1 and files == [f"{bc}_{kh}.entry.txt"] and c.get("key") == m["key"] and c.get("key_hash") == kh and c.get("ev") == "ENTRY"
              and c.get("side") == "SHORT" and c.get("otype") == "MARKET" and c.get("path") == "SATS_NOW" and float(c["px"]) == 2600.0
              and float(c["sl"]) == 2605.0 and float(c["tp"]) == 2592.5 and c.get("bar_close_ms") == str(bc) and c.get("v") == "2"
              and c.get("sid") == m["sid"] and c.get("cfg_sha256") == eb.DEFAULT_CONFIG["expected"]["cfg_sha256"] and c.get("sym") == "OANDA:XAUUSD"
              and it["claimed_ms"] == bc + 2000 and len(lg) == 1 and lg[0]["ok"] == 1 and L["state"] == "CMD_WRITTEN"
              and all(L[t] is not None for t in ("received_ms", "checked_ms", "claim_start_ms", "claimed_ms", "cmd_written_ms")), str((files, c, L)))
        # duplicates: a second pass, a re-send of the same notification, a second bridge on the same receiver
        n2 = b.once()
        st = env.send(m, bc + 3000)
        n3 = b.once()
        b2 = env.bridge(Clock(bc + 4000), bdata=os.path.join(env.tmp, "bridge_data_test2"))
        n4 = b2.once()
        L2 = life(b2, m["key"])
        check("EAB-02 duplicates: a second pass, a re-send of the same ENTRY (receiver DUPLICATE) and a second bridge with its own data folder "
              "on the same receiver write no second command (the receiver claim is atomic: True at most once per key)",
              n2 == 0 and st == "DUPLICATE" and n3 == 0 and n4 == 0 and len(env.cmds()) == 1 and L2 is None, str((n2, st, n3, n4, L2)))
        try:
            env.bridge(Clock(bc), lock=True)
            dup_lock = False
        except RuntimeError:
            dup_lock = True
        check("EAB-03 a second bridge process on the same bridge data folder is refused (exclusive OS lock on bridge.lock)", dup_lock)
    finally:
        env.close()

    # concurrent claims from two bridges in the same pass window
    env = Env()
    try:
        env.receiver()
        m = E(3)
        bc = m["bar_close"]
        env.send(m, bc + 1000)
        b1 = env.bridge(Clock(bc + 2000))
        b2 = env.bridge(Clock(bc + 2000), bdata=os.path.join(env.tmp, "b2"))
        c1 = b1._candidates()
        c2 = b2._candidates()
        r1 = b1.rcv.claim(m["key"])
        r2 = b2.rcv.claim(m["key"])
        b1.once()
        b2.once()
        L2 = life(b2, m["key"])
        check("EAB-04 concurrent start: two bridges see the same candidate at the same time; only one claim succeeds (the other is "
              "already_claimed) and the losing bridge records CLAIM_REFUSED / no command",
              len(c1) == len(c2) == 1 and (r1, r2) == (True, False) and (L2 is None or L2["state"] in ("CLAIM_REFUSED",)), str((r1, r2, L2)))
    finally:
        env.close()


def gate_filter():
    env = Env()
    try:
        env.receiver()
        flow = ms.normal_flow()
        for m in flow:
            env.send(m, m["bar_close"] + 1500)
        entry = [m for m in flow if m["ev"] == "ENTRY"][0]
        b = env.bridge(Clock(entry["bar_close"] + 1500))
        n = b.once()
        evs = sorted({m["ev"] for m in flow})
        got = [env.read_cmd(f)["ev"] for f in env.cmds()]
        check("EAB-05 the normal flow (WAIT_START, BAR, PROV, ENTRY SATS_PULL, BAR, TV_FILL, TP_SET, BAR, BE_MOVE, TV_FLAT): only the ENTRY "
              "becomes a command (PROV / WAIT_* / BAR / TV_FILL / TP_SET / BE_MOVE / TV_FLAT are never forwarded; the EA manages its own position)",
              n <= 1 and got in ([], ["ENTRY"]) and "PROV" in evs and "TV_FILL" in evs, str((n, got)))
    finally:
        env.close()
    cases = {"limit": dict(otype="LIMIT"), "current": dict(info="CURRENT"), "pull": dict(info="SATS_PULL;wid=W1")}
    out = {}
    for nm, kw in cases.items():
        env = Env()
        try:
            env.receiver()
            m = E(3, **kw)
            st = env.send(m, m["bar_close"] + 1000)
            b = env.bridge(Clock(m["bar_close"] + 2000))
            b.once()
            it = env.rcv.store.one("SELECT eligible, claimed_ms FROM intents WHERE key=?", (m["key"],))
            out[nm] = (st, (life(b, m["key"]) or {}).get("reason"), it and it["claimed_ms"], env.cmds())
        finally:
            env.close()
    check("EAB-06 a LIMIT ENTRY is skipped and recorded (skip:limit_not_supported, never converted to market, never claimed); an Entry "
          "Timing CURRENT entry is not the initial settings (skip:path_not_initial_settings); none writes a command",
          out["limit"][1] == "skip:limit_not_supported" and out["limit"][2] is None and out["limit"][3] == []
          and str(out["current"][1]).startswith("skip:path_not_initial_settings") and out["current"][3] == [], str(out))
    # cancel / wait end / close request / BAR alone are never candidates
    env = Env()
    try:
        env.receiver()
        t = f"T{ms.bar(3) + ms.BAR}"
        for m in (ms.ev("PROV", 3, otype="MARKET", px=2600.0, sl=2605.0, tp=2592.5, info="SATS_PULL"),
                  ms.ev("CANCEL", 3, tid=t, px=2600.0, sl=2605.0, tp=2592.5, info="cancel"),
                  ms.ev("CLOSE_REQ", 4, tid=t, px=2600.0, sl=2605.0, tp=2592.5, info="fill_side_bad"),
                  ms.ev("BAR", 4, side="", px=2600.0, info="tv_state=0;tv_tid=;tv_be=0;tv_fill=null")):
            env.send(m, m["bar_close"] + 1000)
        b = env.bridge(Clock(ms.bar(4) + ms.BAR + 2000))
        check("EAB-07 PROV / CANCEL / CLOSE_REQ / BAR without an ENTRY: no candidate, no claim, no command",
              b.once() == 0 and env.cmds() == [] and env.rcv.store.one("SELECT COUNT(*) n FROM claim_log")["n"] == 0)
    finally:
        env.close()


def gate_deadline():
    res = {}
    for nm, at, step in (("late60_9", 60900, 0), ("exact60", 60000, 0), ("future", -1000, 0), ("delay_after_check", 59990, 400)):
        env = Env()
        try:
            env.receiver()
            m = E(3)
            bc = m["bar_close"]
            env.send(m, bc + 1000)
            b = env.bridge(Clock(bc + at, step))
            b.once()
            L = life(b, m["key"])
            lg = env.rcv.store.all("SELECT * FROM claim_log WHERE key=?", (m["key"],))
            it = env.rcv.store.one("SELECT * FROM intents WHERE key=?", (m["key"],))
            res[nm] = (L["state"], L["reason"], [(x["ok"], x["reason"]) for x in lg], it["claimed_ms"], it["eligible"], env.cmds())
        finally:
            env.close()
    check("EAB-08 deadline 60 s from the ENTRY bar close: 60.9 s -> skip:expired_before_claim (not claimed); exactly 60 s -> claimed + command; "
          "a bar close in the FUTURE of the bridge clock (negative age) -> skip:clock_or_future_bar, never 'in time'",
          res["late60_9"][:2] == ("SKIPPED_BY_BRIDGE", "skip:expired_before_claim") and res["late60_9"][3] is None and res["late60_9"][5] == []
          and res["exact60"][0] == "CMD_WRITTEN" and len(res["exact60"][5]) == 1
          and res["future"][:2] == ("SKIPPED_BY_BRIDGE", "skip:clock_or_future_bar") and res["future"][5] == [], str(res))
    d = res["delay_after_check"]
    check("EAB-09 delay after the check: checked at 59.99 s but the claim decision (after the locks) happens past 60 s -> the receiver refuses "
          "(expired_at_claim, the intent is revoked: eligible 0), the bridge records CLAIM_REFUSED and writes no command",
          d[0] == "CLAIM_REFUSED" and d[1] == "expired_at_claim" and d[2] == [(0, "expired_at_claim")] and d[3] is None and d[4] == 0
          and d[5] == [], str(d))
    # order inversion: a terminal fact before the ENTRY, an older ENTRY after a newer one
    env = Env()
    try:
        env.receiver()
        m = E(3)
        flat = ms.ev("TV_FLAT", 5, tid=m["tid"], px=2601.0, sl=2605.0, info="x")
        st_flat = env.send(flat, flat["bar_close"] + 500)
        env.send(m, flat["bar_close"] + 900)
        newer = E(8, px=2610.0, sl=2615.0, tp=2602.5)
        env.send(newer, newer["bar_close"] + 500)
        older = E(6, px=2605.0, sl=2610.0, tp=2597.5)
        env.send(older, newer["bar_close"] + 900)
        b = env.bridge(Clock(newer["bar_close"] + 1000))
        b.once()
        files = [env.read_cmd(f)["key"] for f in env.cmds()]
        check("EAB-10 order inversion: an ENTRY whose TV_FLAT arrived first and an older ENTRY arriving after a newer one are not candidates "
              "(receiver eligibility); only the newest valid ENTRY becomes a command",
              st_flat == "ACCEPTED" and files == [newer["key"]], str((st_flat, files)))
    finally:
        env.close()


def gate_restart():
    out = {}
    # crash after the claim, before the command file (exchange folder unavailable), restart within / after the deadline
    for nm, restart_at in (("within", 20000), ("after", 61000)):
        env = Env()
        try:
            env.receiver()
            m = E(3)
            bc = m["bar_close"]
            env.send(m, bc + 1000)
            b = env.bridge(Clock(bc + 2000))
            orig = b._write_cmd

            def boom(*a, **k):
                raise OSError("exchange folder unavailable")
            b._write_cmd = boom
            try:
                b.once()
                raised = False
            except OSError:
                raised = True
            mid = life(b, m["key"])["state"]
            b._write_cmd = orig
            b.close()
            env.bridges.remove(b)
            env.rcv.store.db.close()
            env.receiver()                     # the receiver restarts too
            b2 = env.bridge(Clock(bc + restart_at))
            b2.once()
            b2.once()
            L = life(b2, m["key"])
            out[nm] = (raised, mid, L["state"], env.cmds(), env.rcv.store.one("SELECT COUNT(*) n FROM claim_log WHERE ok=1")["n"])
        finally:
            env.close()
    check("EAB-11 crash after the claim before the command file (exchange folder unavailable; bridge AND receiver restarted): within the "
          "60 s deadline the command is written once from the stored claim (no second claim); after the deadline it is closed as "
          "EXPIRED_AFTER_BRIDGE_RESTART with no command",
          out["within"][:2] == (True, "CLAIMED") and out["within"][2] == "CMD_WRITTEN" and len(out["within"][3]) == 1 and out["within"][4] == 1
          and out["after"][2] == "EXPIRED_AFTER_BRIDGE_RESTART" and out["after"][3] == [] and out["after"][4] == 1, str(out))
    # crash in CLAIMING: before / after the receiver committed the claim
    out = {}
    for nm in ("before_claim", "after_claim"):
        env = Env()
        try:
            env.receiver()
            m = E(3)
            bc = m["bar_close"]
            env.send(m, bc + 1000)
            b = env.bridge(Clock(bc + 2000))
            b.db.execute("INSERT INTO lifecycle(key, key_hash, tid, bar_close, state, claim_start_ms) VALUES (?,?,?,?,?,?)",
                         (m["key"], eb.key_hash(m["key"]), m["tid"], bc, "CLAIMING", bc + 2000))
            if nm == "after_claim":
                b.rcv.claim(m["key"])
            b.close()
            env.bridges.remove(b)
            b2 = env.bridge(Clock(bc + 5000))
            b2.once()
            b2.once()
            out[nm] = (life(b2, m["key"])["state"], life(b2, m["key"])["reason"], len(env.cmds()),
                       env.rcv.store.one("SELECT COUNT(*) n FROM claim_log WHERE ok=1")["n"])
        finally:
            env.close()
    check("EAB-12 crash while CLAIMING: if the receiver never committed the claim the key is closed (CLAIM_REFUSED "
          "bridge_restart_before_claim, never claimed later); if it did, the command is written once from that claim (no second claim)",
          out["before_claim"][:3] == ("CLAIM_REFUSED", "bridge_restart_before_claim", 0) and out["before_claim"][3] == 0
          and out["after_claim"][0] == "CMD_WRITTEN" and out["after_claim"][2:] == (1, 1), str(out))
    # EA offline: the command stays until the deadline, then it is revoked (never executed late); no second claim
    env = Env()
    try:
        env.receiver()
        m = E(3)
        bc = m["bar_close"]
        env.send(m, bc + 1000)
        b = env.bridge(Clock(bc + 2000))
        b.once()
        name = env.cmds()[0]
        before = os.path.getmtime(os.path.join(env.xdir, "cmd", name))
        for k in range(3):
            b.clock = Clock(bc + 10000 + k * 20000)
            b.once()
        within = (env.cmds() == [name], os.path.getmtime(os.path.join(env.xdir, "cmd", name)) == before, life(b, m["key"])["state"])
        b.clock = Clock(bc + 61000)
        b.once()
        L = life(b, m["key"])
        check("EAB-13 EA offline / no reports: within the 60 s the single command stays in cmd/ untouched and CMD_WRITTEN; after the deadline "
              "it is revoked (REVOKED_BEFORE_GO expired, moved to revoked/) so a returning EA never sees it; no second claim or command",
              within == (True, True, "CMD_WRITTEN") and L["state"] == "REVOKED_BEFORE_GO" and L["nogo_reason"] == "expired"
              and env.cmds() == [] and os.listdir(os.path.join(env.xdir, "revoked")) == [name]
              and env.rcv.store.one("SELECT COUNT(*) n FROM claim_log")["n"] == 1, str((within, dict(L))))
    finally:
        env.close()


def write_rpt(env, name, **f):
    p = os.path.join(env.xdir, "rpt", name)
    with open(p + ".tmp", "w", encoding="ascii", newline="\r\n") as fh:
        fh.write("".join(f"{k}={v}\n" for k, v in f.items()))
    os.replace(p + ".tmp", p)


def gate_reports():
    env = Env()
    try:
        env.receiver()
        m = E(3)
        bc = m["bar_close"]
        env.send(m, bc + 1000)
        b = env.bridge(Clock(bc + 2000))
        b.once()
        kh = eb.key_hash(m["key"])
        seq = [("SEEN", {}), ("DECIDED", {"volume": "0.66"}), ("PRE_SEND", {"volume": "0.66"}),
               ("SEND_RETURNED", {"ok": "1", "retcode": "10009", "order": "5001", "deal": "5002"}),
               ("FILLED", {"order": "5001", "deal": "5002", "position": "5001", "fill_price": "2600.10", "volume": "0.66"}),
               ("PROTECTED", {"sl": "2605.00"}), ("TX_DEAL", {"deal": "5002"}), ("TP_SET", {"tp": "2592.50"})]
        for i, (st, f) in enumerate(seq):
            write_rpt(env, f"{bc + 3000 + i:013d}_{i:08d}_0000000000.rpt", t_ms=bc + 3000 + i, key_hash=kh, state=st, **f)
        write_rpt(env, f"{bc + 3500:013d}_00000099_0000000000.rpt", t_ms="garbage", key_hash=kh, state="BE_SET", sl="nan", volume="x")
        write_rpt(env, f"{bc + 3600:013d}_00000100_0000000000.rpt", t_ms=bc + 3600, key_hash="", state="HALT_NEW", reason="test")
        b.once()
        L = life(b, m["key"])
        flat = ms.ev("TV_FLAT", 9, tid=m["tid"], px=2600.0, sl=2600.0, tp=2592.5, info="virtual_position_closed")
        env.send(flat, flat["bar_close"] + 500)
        b.clock = Clock(flat["bar_close"] + 1000)
        b.once()
        b.once()
        dv = b.db.execute("SELECT * FROM divergences").fetchall()
        rows = b.db.execute("SELECT COUNT(*) n FROM ea_reports").fetchone()["n"]
        check("EAB-14 EA reports: SEEN / DECIDED / PRE_SEND / SEND_RETURNED / FILLED / PROTECTED / TP_SET each set their own time column once; "
              "order / deal / position tickets, the XS fill price and volume are stored; informational lines (TX_DEAL) do not overwrite the "
              "state; mt5_open=1 after FILLED; every report is kept in ea_reports and moved to rpt_done/",
              L["state"] == "EA_BE_SET" and L["ea_order"] == 5001 and L["ea_deal"] == 5002 and L["ea_position"] == 5001
              and L["fill_price"] == 2600.10 and L["volume"] == 0.66 and L["mt5_open"] == 1
              and all(L[c] is not None for c in ("ea_seen_ms", "ea_decided_ms", "ea_pre_send_ms", "ea_send_ms", "ea_filled_ms",
                                                 "ea_protected_ms", "ea_managed_ms"))
              and rows == 10 and os.listdir(os.path.join(env.xdir, "rpt")) == [] and len(os.listdir(os.path.join(env.xdir, "rpt_done"))) == 10,
              str(L))
        check("EAB-15 a malformed report (t_ms 'garbage', sl NaN, volume 'x') and an EA-level line without a key are stored and moved but "
              "never stop the bridge or write non-numbers into the lifecycle; TradingView's TV_FLAT while the MT5 position is open is "
              "recorded ONCE as a divergence (no close / no command: the EA keeps its own SL / TP / breakeven)",
              L["volume"] == 0.66 and len(dv) == 1 and dv[0]["kind"] == "tv_exit_while_mt5_open" and dv[0]["detail"].startswith("TV_FLAT@")
              and env.cmds() == [os.path.basename(env.cmds()[0])] and len(env.cmds()) == 1, str([dict(x) for x in dv]))
        write_rpt(env, f"{bc + 9000:013d}_00000200_0000000000.rpt", t_ms=bc + 9000, key_hash=kh, state="UNKNOWN", retcode="10012")
        write_rpt(env, f"{bc + 9100:013d}_00000201_0000000000.rpt", t_ms=bc + 9100, key_hash=kh, state="CLOSED", reason="sl")
        b.once()
        L = life(b, m["key"])
        check("EAB-16 UNKNOWN sets its own time (ea_unknown_ms); CLOSED sets ea_closed_ms, the reason and mt5_open=0",
              L["ea_unknown_ms"] == bc + 9000 and L["ea_closed_ms"] == bc + 9100 and L["mt5_open"] == 0 and L["state"] == "EA_CLOSED"
              and L["reason"] == "sl", str(L))
    finally:
        env.close()


def _sha(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def gate_real_data():
    env = Env()
    try:
        env.receiver()
        for m in ms.normal_flow():
            env.send(m, m["bar_close"] + 1500)
        m = E(20)
        env.send(m, m["bar_close"] + 1000)
        cfgp = os.path.join(env.tmp, "config.json")
        shutil.copy(os.path.join(RDIR, "config.example.json"), cfgp)
        cfg_sha = _sha(cfgp)
        snap = lambda: [tuple(r) for r in env.rcv.store.all("SELECT * FROM receipts ORDER BY id")] + \
            [tuple(r) for r in env.rcv.store.all("SELECT * FROM events ORDER BY key")]
        before = snap()
        b = env.bridge(Clock(m["bar_close"] + 2000), receiver_config=cfgp)
        b.once()
        after = snap()
        check("EAB-17 the bridge never rewrites the receiver's receipts / facts or its config.json (byte-identical); its only receiver write "
              "is claim() (intents.claimed_ms + claim_log); the bridge keeps its own database in its own folder",
              before == after and _sha(cfgp) == cfg_sha and os.path.exists(os.path.join(env.bdata, "bridge.sqlite3"))
              and not os.path.exists(os.path.join(env.rdata, "bridge.sqlite3")))
    finally:
        env.close()
    src = open(os.path.join(BDIR, "ea_bridge.py"), encoding="utf-8").read()
    ex = open(os.path.join(BDIR, "bridge_config.example.json"), encoding="utf-8").read()
    exj = json.loads(ex)
    code = re.sub(r"#[^\n]*", "", re.sub(r'"""[\s\S]*?"""', "", src))      # code only (docstrings / comments may name what is absent)
    check("EAB-18 the bridge has no network listener / client and no trade API (no socket / http / urllib / OrderSend), reads no token; "
          "bridge_config.example.json has no token / password / URL and points at TEST folders separate from the receiver's real data",
          not re.search(r"\bimport (socket|http|urllib|requests)|OrderSend|token|password", code, re.I)
          and not re.search(r"token|password|https?://|trycloudflare", ex, re.I)
          and "test" in exj["receiver_data_dir"].lower() and "test" in exj["bridge_data_dir"].lower()
          and exj["receiver_data_dir"] != "data" and set(exj) <= set(eb.DEFAULT_CONFIG) | {"_comment"}, str(exj))
    # bridge data that must not land in a review zip / git
    gi = open(os.path.join(BDIR, ".gitignore"), encoding="utf-8").read().split()
    check("EAB-19 bridge/.gitignore keeps the real bridge config, data folders and logs out of git (bridge_config.json, data_bridge*/, "
          "*.sqlite3*, *.log)", all(x in gi for x in ("bridge_config.json", "data_bridge*/", "*.sqlite3*", "*.log")), str(gi))


def _ea(term, xdir, live, **kw):
    ea = em.EA(term, xdir, DryRun=not live, AllowNewEntries=live, ExpectedLogin=1234567, approvals=em.APPROVALS if live else (), **kw)
    assert ea.on_init() == "INIT_SUCCEEDED"
    return ea


def gate_e2e():
    """bridge -> cmd file -> EA model -> ask / final GO -> rpt files -> bridge, on the same exchange folder and one clock."""
    out = {}
    for nm in ("dry_run", "demo_on", "demo_late_ea", "restart_unknown"):
        env = Env()
        try:
            env.receiver()
            m = E(3)
            bc = m["bar_close"]
            env.send(m, bc + 1000)
            term = em.FakeTerminal(gmt_ms=bc + 1500)
            term.bid, term.ask = 2600.2, 2600.5
            live = nm != "dry_run"
            b = env.bridge(lambda: term.gmt_ms, require_ea_heartbeat_ms=5000)
            ea = _ea(term, env.xdir, live)
            ea.wait_hook = b.once                  # the bridge process runs while the EA waits for its answer
            b.once()                               # no EA heartbeat yet -> not claimed
            first = life(b, m["key"])["state"]
            env.rcv.store.db.execute("UPDATE intents SET eligible=1 WHERE key=?", (m["key"],))
            b.db.execute("DELETE FROM lifecycle")
            ea.on_timer()                          # EA heartbeat
            term.advance(500)
            b.once()
            if nm == "demo_late_ea":
                term.advance(70000)            # the EA (or the terminal) was busy / offline: the command is too old
            if nm == "restart_unknown":
                def crash():
                    raise SystemExit("crash after PRE_SEND")
                ea.before_send_hook = crash
                try:
                    ea.on_timer()
                except SystemExit:
                    pass
                ea.on_deinit(crash=True)
                ea = _ea(term, env.xdir, True)
                ea.wait_hook = b.once
            ea.on_timer()
            b.once()
            L = life(b, m["key"])
            out[nm] = (L["state"], L["reason"], L["ea_pre_send_ms"] is not None, len(term.writes), L["volume"], L["mt5_open"],
                       env.cmds(), len([n for n in env.cmds("done") if n.endswith(".entry.txt")]), L["go_ms"] is not None, first)
            ea.on_deinit()
        finally:
            env.close()
    check("EAB-20 end-to-end over the files with the EA reference model and the bridge answering the EA's final ask: no EA heartbeat -> "
          "skip:ea_heartbeat_stale (not claimed); DRY_RUN -> GO recorded, EA_DRY_RUN_NOT_SENT, zero trade writes; demo ON (all approvals) "
          "-> one send, EA_PROTECTED with the volume and mt5_open=1; the EA reading the command 70 s late -> EA_SKIPPED expired, zero "
          "writes; a crash after PRE_SEND and a restart -> EA_UNKNOWN (no re-send); the command file is moved to done/ every time",
          out["dry_run"][0] == "EA_DRY_RUN_NOT_SENT" and out["dry_run"][3] == 0 and out["dry_run"][8]
          and out["demo_on"][0] == "EA_PROTECTED" and out["demo_on"][3] == 1 and out["demo_on"][4] > 0 and out["demo_on"][5] == 1
          and out["demo_late_ea"][0] == "EA_SKIPPED" and out["demo_late_ea"][1] == "expired" and out["demo_late_ea"][3] == 0
          and out["restart_unknown"][0] == "EA_UNKNOWN" and out["restart_unknown"][3] == 0 and out["restart_unknown"][2]
          and all(v[6] == [] and v[7] == 1 and v[9] == "SKIPPED_BY_BRIDGE" for v in out.values()), str(out))


def _pull_env(clock):
    """a SATS_PULL ENTRY from wait W (WAIT_START at bar 0), claimed and commanded."""
    env = Env()
    env.receiver()
    w = f"W{ms.bar(0) + ms.BAR}"
    ws = ms.ev("WAIT_START", 0, px=2600.0, sl=2605.0, tp=2592.5, info="sats_wait")
    env.send(ws, ws["bar_close"] + 500)
    m = E(3, info=f"SATS_PULL;wid={w}")
    env.send(m, m["bar_close"] + 1000)
    return env, m, w


def gate_review():
    """regressions of the ST3-1 review on the bridge side (item 1: a claim is not a permission; items 6 / 8: reports, heartbeats)."""
    out = {}
    for nm in ("before_ea_reads", "while_ea_waits"):
        env, m, w = _pull_env(None)
        try:
            bc = m["bar_close"]
            term = em.FakeTerminal(gmt_ms=bc + 1500)
            term.bid, term.ask = 2600.2, 2600.5
            b = env.bridge(lambda: term.gmt_ms)
            b.once()
            we = ms.ev("WAIT_END", 3, tid=w, px=2600.0, sl=2605.0, tp=2592.5, info="expired")
            ea = _ea(term, env.xdir, True)
            if nm == "before_ea_reads":
                env.send(we, bc + 2000)
                term.advance(500)
                b.once()
                ea.wait_hook = b.once
            else:
                sent = []

                def hook():
                    if not sent:
                        sent.append(env.send(we, term.gmt_ms))
                    b.once()
                ea.wait_hook = hook
            ea.on_timer()
            b.once()
            L = life(b, m["key"])
            note = env.rcv.store.one("SELECT claim_note FROM intents WHERE key=?", (m["key"],))["claim_note"]
            kh = eb.key_hash(m["key"])
            out[nm] = (L["state"], L["nogo_reason"], L["go_ms"], len([x for x in term.writes if x[0] == "send"]), note,
                       os.listdir(os.path.join(env.xdir, "revoked")), (ea.last(kh, "SKIPPED") or {}).get("reason"))
            ea.on_deinit()
        finally:
            env.close()
    a, c = out["before_ea_reads"], out["while_ea_waits"]
    check("EAB-22 (review 1) SATS_PULL ENTRY claimed and commanded, then the WAIT_END of its wait arrives (receiver: post_claim:late): before "
          "the EA read the command -> REVOKED_BEFORE_GO, the command moved to revoked/, the EA never sees it; while the EA waits for its "
          "final answer -> NOGO revoked_after_claim:late:wait_already_ended, EA SKIPPED nogo:...; zero sends in both cases",
          a[0] == "REVOKED_BEFORE_GO" and a[1].startswith("revoked_after_claim:late:wait_already_ended") and a[2] is None and a[3] == 0
          and str(a[4]).startswith("post_claim:late") and len(a[5]) == 1
          and c[1].startswith("revoked_after_claim:late:wait_already_ended") and c[2] is None and c[3] == 0
          and str(c[6]).startswith("nogo:revoked_after_claim:late:wait_already_ended"), str(out))
    res = {}
    for term_ev in ("CANCEL", "TV_FLAT", "TV_CLOSED", "CLOSE_REQ"):
        env = Env()
        try:
            env.receiver()
            m = E(3)
            bc = m["bar_close"]
            env.send(m, bc + 1000)
            b = env.bridge(Clock(bc + 2000))
            b.once()
            t = ms.ev(term_ev, 4, tid=m["tid"], px=None if term_ev == "CANCEL" else 2601.0, sl=2605.0,
                      otype="MARKET" if term_ev == "CANCEL" else "", info="x")
            st = env.send(t, bc + 3000)
            b.clock = Clock(bc + 3500)
            b.once()
            res[term_ev] = (st, life(b, m["key"])["state"], life(b, m["key"])["nogo_reason"], env.cmds())
        finally:
            env.close()
    check("EAB-23 (review 1) CANCEL / TV_FLAT / TV_CLOSED / CLOSE_REQ of the trade learnt after the claim and before any GO -> the command is "
          "revoked (no GO will ever be given)",
          all(v[0] == "ACCEPTED" and v[1] == "REVOKED_BEFORE_GO" and v[2] and v[3] == [] for v in res.values()), str(res))
    env, m, w = _pull_env(None)
    try:
        bc = m["bar_close"]
        b = env.bridge(Clock(bc + 2000))
        orig = b._write_cmd

        def boom(*a_, **k_):
            raise OSError("exchange folder unavailable")
        b._write_cmd = boom
        try:
            b.once()
        except OSError:
            pass
        b._write_cmd = orig
        b.close()
        env.bridges.remove(b)
        we = ms.ev("WAIT_END", 3, tid=w, px=2600.0, sl=2605.0, tp=2592.5, info="expired")
        env.send(we, bc + 3000)
        b2 = env.bridge(Clock(bc + 4000))
        b2.once()
        L = life(b2, m["key"])
        r23 = (L["state"], L["nogo_reason"], env.cmds())
    finally:
        env.close()
    check("EAB-24 (review 1) the same after a bridge restart: claimed, crash before the command, WAIT_END arrives, restart -> recover writes "
          "NO command (REVOKED_AFTER_BRIDGE_RESTART, the post-claim revocation is the reason)",
          r23[0] == "REVOKED_AFTER_BRIDGE_RESTART" and r23[1].startswith("revoked_after_claim:late:wait_already_ended") and r23[2] == [],
          str(r23))
    env = Env()
    try:
        env.receiver()
        m = E(3)
        bc = m["bar_close"]
        env.send(m, bc + 1000)
        clk = [bc + 2000]
        b = env.bridge(lambda: clk[0], go_ttl_ms=3000)
        b.once()
        kh = eb.key_hash(m["key"])

        def ask(k):
            with open(os.path.join(env.xdir, "ask", k + ".ask"), "w") as f:
                f.write(f"key_hash={k}\nt_ms={clk[0]}\ndry_run=0\n")
            b.answer_asks()
            return eb.read_kv(os.path.join(env.xdir, "ans", k + ".ans"))
        g1 = ask(kh)
        g2 = ask(kh)
        g3 = ask("0123456789abcdef")
        clk[0] = bc + 58500
        b.db.execute("UPDATE lifecycle SET go_ms=NULL, nogo_reason=NULL WHERE key=?", (m["key"],))
        g4 = ask(kh)
        clk[0] = bc + 61000
        b.db.execute("UPDATE lifecycle SET go_ms=NULL, nogo_reason=NULL WHERE key=?", (m["key"],))
        g5 = ask(kh)
        n_answers = b.db.execute("SELECT COUNT(*) n FROM answers").fetchone()["n"]
    finally:
        env.close()
    check("EAB-25 (review 1) GO at most once per key: the first ask -> GO valid 3 s (go_ttl_ms, a proposal), a second ask -> NOGO "
          "already_granted, an unknown key -> NOGO unknown_key; the validity never passes the 60 s deadline (asked at 58.5 s -> valid until "
          "60.0 s); after the deadline -> NOGO expired; every answer is stored before its file",
          g1["decision"] == "GO" and int(g1["valid_until_ms"]) == bc + 5000 and (g2["decision"], g2["reason"]) == ("NOGO", "already_granted")
          and (g3["decision"], g3["reason"]) == ("NOGO", "unknown_key") and g4["decision"] == "GO" and int(g4["valid_until_ms"]) == bc + 60000
          and (g5["decision"], g5["reason"]) == ("NOGO", "expired") and n_answers == 5, str((g1, g2, g3, g4, g5)))
    env = Env()
    try:
        env.receiver()
        m = E(3)
        bc = m["bar_close"]
        env.send(m, bc + 1000)
        b = env.bridge(Clock(bc + 2000))
        b.once()
        kh = eb.key_hash(m["key"])
        seq = [("FILLED", {"position": "5001", "fill_price": "2600.2", "volume": "0.41"}), ("SL_MISSING", {}),
               ("EMERGENCY_CLOSE_PARTIAL", {"remaining": "0.21"}), ("CRITICAL", {"reason": "emergency_close_partial"})]
        for i, (st, f) in enumerate(seq):
            write_rpt(env, f"{bc + 3000 + i:013d}_{i:08d}_0000000000.rpt", t_ms=bc + 3000 + i, key_hash=kh, state=st, **f)
        b.once()
        o1 = life(b, m["key"])["mt5_open"]
        write_rpt(env, f"{bc + 4000:013d}_00000010_0000000000.rpt", t_ms=bc + 4000, key_hash=kh, state="EMERGENCY_CLOSE", result="closed_confirmed")
        b.once()
        o2 = life(b, m["key"])["mt5_open"]
        write_rpt(env, f"{bc + 5000:013d}_00000011_0000000000.rpt", t_ms=bc + 5000, key_hash=kh, state="CLOSED", reason="expert")
        b.once()
        o3 = life(b, m["key"])["mt5_open"]
    finally:
        env.close()
    check("EAB-26 (review 6) the bridge never treats an emergency close request as a close: after FILLED, EMERGENCY_CLOSE_PARTIAL (remainder "
          "0.21) and even EMERGENCY_CLOSE keep mt5_open=1; only the EA's CLOSED (written after the history covers the volume) clears it",
          (o1, o2, o3) == (1, 1, 0), str((o1, o2, o3)))
    env = Env()
    try:
        env.receiver()
        m = E(3)
        bc = m["bar_close"]
        env.send(m, bc + 1000)
        b = env.bridge(Clock(bc + 2000), require_ea_heartbeat_ms=5000)
        with open(os.path.join(env.xdir, "hb_ea.txt"), "w") as f:
            f.write(f"t_ms={bc - 9000}\n")           # the EA's last heartbeat is 11 s old
        b.once()
        s1 = (life(b, m["key"])["state"], life(b, m["key"])["reason"], env.cmds())
        hb = eb.read_kv(os.path.join(env.xdir, "hb_bridge.txt"))
    finally:
        env.close()
    check("EAB-27 (review 8) monitoring: with the EA heartbeat older than require_ea_heartbeat_ms (5 s, a proposal) a new ENTRY is not "
          "claimed (skip:ea_heartbeat_stale, no command); the bridge writes hb_bridge.txt every pass with the last receipt time (the EA "
          "refuses new entries when it is stale)",
          s1 == ("SKIPPED_BY_BRIDGE", "skip:ea_heartbeat_stale", []) and int(hb["t_ms"]) == bc + 2000 and int(hb["last_receipt_ms"]) == bc + 1000,
          str((s1, hb)))
    env = Env()
    try:
        os.makedirs(env.bdata)
        import sqlite3
        old = sqlite3.connect(os.path.join(env.bdata, "bridge.sqlite3"))
        old.executescript("CREATE TABLE lifecycle (key TEXT PRIMARY KEY, key_hash TEXT, tid TEXT, bar_close INTEGER, state TEXT, reason TEXT,"
                          " px REAL, sl REAL, tp REAL, path TEXT, otype TEXT, ea_retcode INTEGER, ea_order INTEGER, ea_deal INTEGER,"
                          " ea_position INTEGER, fill_price REAL, volume REAL, mt5_open INTEGER DEFAULT 0, received_ms INTEGER, checked_ms INTEGER,"
                          " claim_start_ms INTEGER, claimed_ms INTEGER, cmd_written_ms INTEGER, ea_seen_ms INTEGER, ea_decided_ms INTEGER,"
                          " ea_pre_send_ms INTEGER, ea_send_ms INTEGER, ea_result_ms INTEGER, ea_filled_ms INTEGER, ea_protected_ms INTEGER,"
                          " ea_managed_ms INTEGER, ea_closed_ms INTEGER, ea_unknown_ms INTEGER);"
                          " INSERT INTO lifecycle(key, key_hash, state) VALUES ('k1', 'h1', 'CMD_WRITTEN');")
        old.commit()
        old.close()
        env.receiver()
        b = env.bridge(Clock(ms.bar(3)))
        cols = {r[1] for r in b.db.execute("PRAGMA table_info(lifecycle)")}
        kept = life(b, "k1")["state"]
    finally:
        env.close()
    env = Env()
    try:
        env.receiver()
        m = E(3)
        bc = m["bar_close"]
        env.send(m, bc + 1000)
        b = env.bridge(Clock(bc + 2000))
        b.once()
        kh = eb.key_hash(m["key"])
        write_rpt(env, f"{bc + 3000:013d}_00000001_0000000000.rpt", t_ms=bc + 3000, key_hash=kh, state="FILLED", position="5001",
                  fill_price="2600.20000", volume="0.20")
        write_rpt(env, f"{bc + 4000:013d}_00000002_0000000000.rpt", t_ms=bc + 4000, key_hash=kh, state="POSITION_UPDATED", cause="add",
                  volume="0.40", fill_price="2600.60000")
        write_rpt(env, f"{bc + 5000:013d}_00000003_0000000000.rpt", t_ms=bc + 5000, key_hash=kh, state="CLOSE_REQUIRED", reason="bad_fill_side_mt5")
        b.once()
        L29 = life(b, m["key"])
        r29 = (L29["volume"], L29["fill_price"], L29["mt5_open"], L29["state"])
    finally:
        env.close()
    check("EAB-29 (re-review 2/3) the EA's POSITION_UPDATED (a later deal of the same order) updates the lifecycle's volume / fill price; "
          "CLOSE_REQUIRED is recorded but is not a close (mt5_open stays 1 until CLOSED)",
          r29 == (0.4, 2600.6, 1, "EA_CLOSE_REQUIRED"), str(r29))
    check("EAB-28 a bridge database written by ST3-1 is upgraded in place (go_ms / go_until_ms / nogo_reason / revoked_ms added), rows kept",
          {"go_ms", "go_until_ms", "nogo_reason", "revoked_ms"} <= cols and kept == "CMD_WRITTEN", str(cols))


def gate_test_entry():
    import subprocess
    tmp = tempfile.mkdtemp(prefix="eab_mte_")
    try:
        res = {}
        for nm, rdir in (("real", "data"), ("test", "data_receiver_test")):
            cfgp = os.path.join(tmp, f"bridge_{nm}.json")
            with open(cfgp, "w", encoding="utf-8") as f:
                json.dump({"receiver_data_dir": rdir, "bridge_data_dir": "data_bridge_test", "exchange_dir": "x_test"}, f)
            r = subprocess.run([sys.executable, os.path.join(BDIR, "make_test_entry.py"), "--config", cfgp, "--px", "2650", "--no-wait"],
                               capture_output=True, text=True, timeout=60)
            res[nm] = (r.returncode, r.stdout.strip()[-300:], os.path.exists(os.path.join(tmp, rdir)))
        out = json.loads(res["test"][1]) if res["test"][0] == 0 else {}
        check("EAB-21 make_test_entry.py refuses a receiver folder that is not a TEST folder (exit 2, the folder is not even created) and puts "
              "one synthetic SHORT MARKET SATS_NOW ENTRY (px 2650 / sl 2655 / tp 2642.5, on a real 5-minute bar close) into a TEST folder",
              res["real"][0] == 2 and "refused" in res["real"][1] and not res["real"][2] and out.get("status") == "ACCEPTED"
              and out.get("px") == 2650.0 and out.get("sl") == 2655.0 and out.get("tp") == 2642.5 and out.get("bar_close_ms", 1) % 300000 == 0,
              str(res))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def gate_st36():
    import signal
    import subprocess
    import time
    from unittest import mock
    script = os.path.join(BDIR, "ea_bridge.py")
    # 1. the real entry point: main -> load_config -> setup_log (module-level logging.handlers) -> once / status / run
    tmp = tempfile.mkdtemp(prefix="eab_cli_")
    out = {}
    try:
        cfgp = os.path.join(tmp, "bridge_config.json")
        json.dump({"receiver_data_dir": os.path.join(tmp, "receiver_test"), "bridge_data_dir": os.path.join(tmp, "bridge_test"),
                   "exchange_dir": os.path.join(tmp, "exchange_test")}, open(cfgp, "w"))
        cmd = lambda mode: [sys.executable, script, mode, "--config", cfgp]
        hb = os.path.join(tmp, "exchange_test", "hb_bridge.txt")
        r1 = subprocess.run(cmd("once"), capture_output=True, text=True, timeout=30)
        out["once"] = (r1.returncode, (r1.stdout.strip().splitlines() or [""])[-1], os.path.isfile(os.path.join(tmp, "bridge_test", "bridge.log")),
                       os.path.isfile(hb), "Traceback" in r1.stdout + r1.stderr)
        os.makedirs(os.path.join(tmp, "exchange_test", "cmd"), exist_ok=True)
        open(os.path.join(tmp, "exchange_test", "cmd", "1_old.cmd"), "w").write("v=2\n")
        r2 = subprocess.run(cmd("status"), capture_output=True, text=True, timeout=30)
        out["status"] = (r2.returncode, "hb_bridge.txt: age" in r2.stdout, "legacy *.cmd in cmd/ (not read by the EA since ST3-6): 1  1_old.cmd" in r2.stdout)
        os.remove(hb)
        pr = subprocess.Popen(cmd("run"), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            dl = time.monotonic() + 15
            while not os.path.exists(hb) and pr.poll() is None and time.monotonic() < dl:
                time.sleep(0.05)
            first = os.stat(hb).st_mtime_ns if os.path.exists(hb) else None
            dl = time.monotonic() + 5
            while first is not None and os.stat(hb).st_mtime_ns == first and time.monotonic() < dl:
                time.sleep(0.05)
            out["run"] = (first is not None, first is not None and os.stat(hb).st_mtime_ns != first, pr.poll() is None)
        finally:
            if pr.poll() is None:
                pr.send_signal(signal.SIGINT)
            so, se = pr.communicate(timeout=15)
        out["run"] += (pr.returncode, "Traceback" in so + se, "legacy command files" in so + se,
                       os.path.exists(os.path.join(tmp, "exchange_test", "cmd", "1_old.cmd")))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    check("EAB-30 (ST3-6, found on Windows: UnboundLocalError from the local `import logging.handlers` in setup_log) the real CLI in a "
          "subprocess with TEST folders: once -> exit 0, {\"commands_written\": 0}, bridge.log and hb_bridge.txt written, no traceback; status "
          "reads the database / heartbeat and reports an old *.cmd; run starts, writes and keeps updating its heartbeat, stops on SIGINT "
          "with exit 0; the old *.cmd is warned about and left in place",
          out.get("once") == (0, '{"commands_written": 0}', True, True, False) and out.get("status") == (0, True, True)
          and out.get("run") == (True, True, True, 0, False, True, True), str(out))
    # 2. heartbeat replacement: bounded retry for known Windows sharing errors only, GO answers unchanged
    def denied(code):
        e = PermissionError("simulated Windows sharing violation")
        e.winerror = code
        return e
    res = {}
    tmp = tempfile.mkdtemp(prefix="eab_hb_")
    try:
        target = os.path.join(tmp, "hb_bridge.txt")
        real = os.replace
        for code in (5, 32, 33):
            open(target, "w").write("old")
            calls, seen_old = [], []
            def rep(src, dst, calls=calls, seen_old=seen_old, code=code):
                calls.append(1)
                if len(calls) < 3:
                    seen_old.append(open(dst).read())
                    raise denied(code)
                real(src, dst)
            with mock.patch.object(eb.os, "replace", rep), mock.patch.object(eb.time, "sleep"):
                eb.write_atomic(target, "new", retry_sharing=True)
            res[code] = (len(calls), seen_old, open(target).read())
        for nm, enabled, code in (("answer path", False, 32), ("other winerror", True, 999), ("no winerror", True, None)):
            with mock.patch.object(eb.os, "replace", side_effect=denied(code)) as rp, mock.patch.object(eb.time, "sleep") as sl:
                try:
                    eb.write_atomic(target, "new", retry_sharing=enabled)
                    raised = False
                except PermissionError:
                    raised = True
            res[nm] = (raised, rp.call_count, sl.call_count)
        now = [0.0]
        with mock.patch.object(eb.os, "replace", side_effect=denied(5)), mock.patch.object(eb.time, "monotonic", side_effect=lambda: now[0]), \
                mock.patch.object(eb.time, "sleep", side_effect=lambda d: now.__setitem__(0, now[0] + d)):
            try:
                eb.write_atomic(target, "new", retry_sharing=True)
                res["persistent"] = (False, now[0])
            except PermissionError:
                res["persistent"] = (True, round(now[0], 4))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    src = open(os.path.join(BDIR, "ea_bridge.py"), encoding="utf-8").read()
    calls = re.findall(r"write_atomic\(([^\n]*)\)\n", src)
    check("EAB-31 (ST3-6, found on Windows: WinError 5 / 32 replacing hb_bridge.txt) heartbeat only: WinError 5 / 32 / 33 retried until the "
          "atomic replace succeeds, the old file intact meanwhile; a persistent denial raised after the 250 ms window (never swallowed); "
          "no retry without the opt-in (the GO / NOGO answers keep their timing) nor for another error; the only opt-in is write_heartbeat "
          "(the answer write has none). The root cause of the sharing errors is not solved by this",
          all(res[c] == (3, ["old", "old"], "new") for c in (5, 32, 33)) and res["answer path"] == (True, 1, 0)
          and res["other winerror"] == (True, 1, 0) and res["no winerror"] == (True, 1, 0) and res["persistent"][0]
          and 0.25 <= res["persistent"][1] <= 0.251 and src.count("retry_sharing=True") == 1
          and [c for c in calls if "retry_sharing" in c] == ['self._x("hb_bridge.txt"), f"t_ms={self.clock()}\\nlast_receipt_ms={(last and last[\'m\']) or 0}\\n", retry_sharing=True']
          and any(c.startswith('self._x("ans", kh + ".ans"), body') and "retry_sharing" not in c for c in calls), str((res, calls)))
    # 3. command file name
    mq = open(os.path.join(ROOT, "automation", "xau_short", "ea", "XauShortDemoEA.mq5"), encoding="utf-8").read()
    env = Env()
    try:
        env.receiver()
        m = E(5)
        bc = m["bar_close"]
        env.send(m, bc + 1500)
        b = env.bridge(Clock(bc + 2000))
        b.once()
        names = env.cmds()
        b._revoke(b._row(m["key"]), "test", bc + 2500)
        moved = env.cmds("revoked")
    finally:
        env.close()
    check("EAB-32 (ST3-6, found on Windows: MQL5 FileFindFirst / FileIsExist on *.cmd -> error 5002) the bridge writes and revokes "
          "<bar_close>_<key hash>.entry.txt and the EA reads only \\*.entry.txt; no .cmd name left in the bridge / EA code; the ask / ans / "
          "rpt / tmp names were exercised by the user's synthetic ENTRY on Windows. Linux cannot reproduce the MQL5 restriction: the EA side "
          "is a separate check on the PC",
          len(names) == 1 and names[0].endswith(".entry.txt") and moved == names
          and mq.count('FileFindFirst(Dir("cmd") + "\\\\*.entry.txt"') == 1 and ".cmd\"" not in mq and "*.cmd" not in mq
          and '.cmd"' not in src.replace('n.endswith(".cmd")', ""), str((names, moved)))


def main():
    for g in (gate_claim, gate_filter, gate_deadline, gate_restart, gate_reports, gate_real_data, gate_e2e, gate_review, gate_test_entry,
              gate_st36):
        try:
            g()
        except Exception:
            import traceback
            check(f"{g.__name__} completed without error", False, traceback.format_exc()[-1500:])
    fails = 0
    for nm, ok, d in RESULTS:
        fails += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {nm[:150].ljust(150)}  {'' if ok else d}")
    print(f"\n{len(RESULTS) - fails}/{len(RESULTS)} passed  [local Python: bridge + EA reference model; no TradingView / Windows / MT5]")
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
