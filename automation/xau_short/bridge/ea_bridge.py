#!/usr/bin/env python3
"""XAU Short stage 3 — bridge between the notification receiver and the demo MQL5 EA (NO trade API here).

Responsibilities (the receiver keeps recording exactly as before; this is a separate process):
  * read the receiver database, pick ENTRY intents the receiver marked eligible, check them again (SHORT / MARKET / SATS path /
    sid / cfg SHA-256 / symbol / 60 s deadline / clock / EA heartbeat) and CLAIM them with the receiver's atomic claim() (= "the
    notification was taken once"; it is NOT an order record and NOT a permanent permission);
  * write one command file per claimed ENTRY into the MT5 common-files exchange folder (atomic rename) for the EA;
  * give the EA the FINAL go / no-go: right before its send the EA writes ask/<key_hash>.ask and waits; the bridge re-checks the
    claim against everything the receiver learnt since (post-claim revocation, CANCEL / TV_CLOSED / TV_FLAT / CLOSE_REQ, the wait's
    WAIT_END, the deadline) and answers ans/<key_hash>.ans with GO (once per key, short validity) or NOGO. Without a GO the EA
    never sends. A command that becomes invalid before its GO is revoked (also after a bridge restart);
  * read the EA's report files and keep the order lifecycle in its own database (bridge.sqlite3), separate from the receiver DB;
  * write its heartbeat (hb_bridge.txt) and read the EA's (hb_ea.txt);
  * log divergences (e.g. TradingView closed its virtual trade while the MT5 position is open) without acting on them: a FILLED
    MT5 position is never closed because of a TradingView exit.
It never forwards PROV / WAIT_* / BAR / TV_* / TP_SET / BE_MOVE / CLOSE_REQ / CANCEL: the EA manages its own position.
It never deletes or rewrites the receiver's config, receipts or facts; its only write to the receiver DB is claim().

  python ea_bridge.py run    --config bridge_config.json      loop (Ctrl+C to stop)
  python ea_bridge.py once   --config bridge_config.json      one pass (tests / manual)
  python ea_bridge.py status --config bridge_config.json      lifecycle of the recent keys + heartbeats

Standard library only.
"""
import argparse
import hashlib
import json
import logging
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
RECEIVER_DIR = os.path.join(os.path.dirname(HERE), "receiver")
DB_VERSION = "2"
MAX_AGE_SEC = 60                       # approved: ENTRY bar close -> 60 s (also re-checked by the EA right before OrderSend)
CMD_VERSION = "2"
ALLOWED_PATHS = ("SATS_PULL", "SATS_NOW")   # the initial settings (Entry Timing SATS Pullback); CURRENT / LIMIT are recorded, not sent
TERMINAL_FOR_ENTRY = ("CANCEL", "TV_CLOSED", "TV_FLAT", "CLOSE_REQ")
SUBDIRS = ("cmd", "rpt", "done", "rpt_done", "ask", "ask_done", "ans", "revoked")

DEFAULT_CONFIG = {
    "receiver_data_dir": None,         # REQUIRED: the receiver's data folder (the bridge only claims there)
    "receiver_config": None,           # optional: the receiver's config.json (read only; its policy gets max_age_sec 60 for claim())
    "bridge_data_dir": "data_bridge",
    "exchange_dir": None,              # REQUIRED: <MT5 Common\\Files>\\XauShortDemo (the EA's InpExchangeDir under Common\\Files)
    "expected": {"sid": "XAU-SHORT|XA-23|AU-2", "symbol": "OANDA:XAUUSD",      # the bridge's own pins (the EA pins them again)
                 "cfg_sha256": "72fa9868a3e196ebcd02e37a12f82416d1149e5bd0567d8bf426e2c49f4695ee"},
    "poll_ms": 200,
    "go_ttl_ms": 3000,                 # PROPOSAL (not approved): validity of a GO answer
    "require_ea_heartbeat_ms": 5000,   # PROPOSAL (not approved): no new claim while the EA heartbeat is older (null = not required)
}

# lifecycle columns (each a separate time; NULL = not reached)
TIMES = ("received_ms", "checked_ms", "claim_start_ms", "claimed_ms", "cmd_written_ms", "go_ms", "revoked_ms", "ea_seen_ms",
         "ea_decided_ms", "ea_pre_send_ms", "ea_send_ms", "ea_result_ms", "ea_filled_ms", "ea_protected_ms", "ea_managed_ms",
         "ea_closed_ms", "ea_unknown_ms")
EA_STATE_TIME = {"SEEN": "ea_seen_ms", "DECIDED": "ea_decided_ms", "SKIPPED": "ea_decided_ms", "DRY_RUN_NOT_SENT": "ea_decided_ms",
                 "PRE_SEND": "ea_pre_send_ms", "SEND_ABORTED": "ea_result_ms", "SEND_RETURNED": "ea_send_ms", "REJECTED": "ea_result_ms",
                 "FILLED": "ea_filled_ms", "PROTECTED": "ea_protected_ms", "SL_MISSING": "ea_protected_ms",
                 "EMERGENCY_CLOSE": "ea_protected_ms", "EMERGENCY_CLOSE_PARTIAL": "ea_protected_ms",
                 "TP_SET": "ea_managed_ms", "BE_SET": "ea_managed_ms", "MODIFY_FAILED": "ea_managed_ms", "OWNED_AT_STARTUP": "ea_managed_ms",
                 "CLOSED": "ea_closed_ms", "UNKNOWN": "ea_unknown_ms", "UNKNOWN_RESOLVED": "ea_unknown_ms", "QUARANTINE": "ea_unknown_ms",
                 "OWN_POSITION_MISSING": "ea_unknown_ms", "CRITICAL": "ea_unknown_ms"}
# informational EA lines (DUPLICATE, TX_DEAL, PARTIAL_FILL, CLOSE_*, MODIFY_REFUSED, MANAGEMENT_BLOCKED, UNKNOWN_CHECK, TICKET_CHANGED ...)
# are kept in ea_reports only and do not overwrite the lifecycle state. mt5_open is set by FILLED / OWNED_AT_STARTUP and cleared ONLY by
# CLOSED (the EA writes CLOSED after the position's history covers its volume; an emergency close request is not a close).


def now_ms():
    return int(time.time() * 1000)


def iso(ms):
    return datetime.fromtimestamp(ms / 1000, timezone.utc).isoformat(timespec="milliseconds") if ms else None


def key_hash(key):
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def _num(v, ty):
    """a report value as a number, None when missing / malformed (a bad report never stops the bridge)."""
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    if x != x or x in (float("inf"), float("-inf")):
        return None
    return ty(x)


def read_kv(path):
    with open(path, encoding="ascii", errors="replace") as f:
        return dict(l.rstrip("\r\n").split("=", 1) for l in f if "=" in l)


def write_atomic(path, body):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="ascii", newline="\n") as f:
        f.write(body)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def load_config(path):
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    base = HERE
    if path:
        with open(path, encoding="utf-8-sig") as f:
            user = json.load(f)
        for k, v in user.items():
            if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                cfg[k].update(v)
            else:
                cfg[k] = v
        base = os.path.dirname(os.path.abspath(path))
    for k in ("receiver_data_dir", "bridge_data_dir", "exchange_dir", "receiver_config"):
        if cfg.get(k):
            cfg[k] = os.path.expandvars(cfg[k])           # e.g. %APPDATA%\\MetaQuotes\\Terminal\\Common\\Files\\XauShortDemo
        if cfg.get(k) and not os.path.isabs(cfg[k]):
            cfg[k] = os.path.join(base, cfg[k])
    return cfg


class SingleInstance:
    """an exclusive OS lock on <bridge_data_dir>/bridge.lock (released by the OS when the process dies)."""

    def __init__(self, path):
        self.f = open(path, "a+")
        try:
            if os.name == "nt":
                import msvcrt
                self.f.seek(0)
                msvcrt.locking(self.f.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.f.close()
            raise RuntimeError("another bridge instance holds " + path)

    def release(self):
        try:
            self.f.close()
        except OSError:
            pass


class Bridge:
    def __init__(self, cfg, clock=None, log=None, lock=True):
        if not cfg.get("receiver_data_dir") or not cfg.get("exchange_dir"):
            raise ValueError("receiver_data_dir and exchange_dir must be set in the bridge config")
        self.cfg = cfg
        self.clock = clock or now_ms
        self.log = log or logging.getLogger("ea_bridge")
        os.makedirs(cfg["bridge_data_dir"], exist_ok=True)
        self.lock = SingleInstance(os.path.join(cfg["bridge_data_dir"], "bridge.lock")) if lock else None
        for sub in SUBDIRS:
            os.makedirs(os.path.join(cfg["exchange_dir"], sub), exist_ok=True)
        sys.path.insert(0, RECEIVER_DIR)
        import xau_receiver as xr
        self.xr = xr
        rcfg = xr.load_config(cfg.get("receiver_config")) if cfg.get("receiver_config") else xr.load_config(None)
        rcfg["data_dir"] = cfg["receiver_data_dir"]
        rcfg["policy"] = dict(rcfg.get("policy") or {}, max_age_sec=MAX_AGE_SEC)   # the claim re-checks the approved 60 s
        self.rcv = xr.Receiver(rcfg, log=self.log, clock=self.clock)
        self.db = sqlite3.connect(os.path.join(cfg["bridge_data_dir"], "bridge.sqlite3"), isolation_level=None, timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT);
        CREATE TABLE IF NOT EXISTS lifecycle (key TEXT PRIMARY KEY, key_hash TEXT, tid TEXT, bar_close INTEGER, state TEXT, reason TEXT,
            px REAL, sl REAL, tp REAL, path TEXT, otype TEXT, ea_retcode INTEGER, ea_order INTEGER, ea_deal INTEGER, ea_position INTEGER,
            fill_price REAL, volume REAL, mt5_open INTEGER DEFAULT 0, """ + ", ".join(f"{t} INTEGER" for t in TIMES) + """);
        CREATE INDEX IF NOT EXISTS lifecycle_kh ON lifecycle(key_hash);
        CREATE TABLE IF NOT EXISTS ea_reports (id INTEGER PRIMARY KEY AUTOINCREMENT, file TEXT UNIQUE, key_hash TEXT, state TEXT, t_ms INTEGER,
            fields TEXT, ingested_ms INTEGER);
        CREATE TABLE IF NOT EXISTS divergences (id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT, tid TEXT, kind TEXT, detail TEXT,
            t_ms INTEGER, UNIQUE(key, kind, detail));
        CREATE TABLE IF NOT EXISTS answers (id INTEGER PRIMARY KEY AUTOINCREMENT, key_hash TEXT, ask_t_ms INTEGER, decision TEXT,
            reason TEXT, valid_until_ms INTEGER, dry_run TEXT, t_ms INTEGER);
        """)
        cols = {r[1] for r in self.db.execute("PRAGMA table_info(lifecycle)")}      # a ST3-1 database is upgraded in place
        for c, ty in (("go_ms", "INTEGER"), ("go_until_ms", "INTEGER"), ("nogo_reason", "TEXT"), ("revoked_ms", "INTEGER")):
            if c not in cols:
                self.db.execute(f"ALTER TABLE lifecycle ADD COLUMN {c} {ty}")
        self.db.execute("INSERT OR IGNORE INTO meta(k, v) VALUES ('db_version', ?)", (DB_VERSION,))
        self.db.execute("UPDATE meta SET v=? WHERE k='db_version'", (DB_VERSION,))

    def close(self):
        self.db.close()
        self.rcv.store.db.close()
        if self.lock:
            self.lock.release()

    # -- helpers ----------------------------------------------------------------------------------------------------------
    def _x(self, *p):
        return os.path.join(self.cfg["exchange_dir"], *p)

    def _row(self, key):
        return self.db.execute("SELECT * FROM lifecycle WHERE key=?", (key,)).fetchone()

    def _set(self, key, **kw):
        cols = ", ".join(f"{k}=?" for k in kw)
        self.db.execute(f"UPDATE lifecycle SET {cols} WHERE key=?", (*kw.values(), key))

    def _candidates(self):
        """ENTRY intents the receiver marked eligible and nobody claimed yet, with their facts and receipt."""
        rdb = self.rcv.store.db
        return rdb.execute(
            "SELECT i.key, i.tid, i.eligible, i.claimed_ms, e.bar_close, e.side, e.otype, e.px, e.sl, e.tp, e.info, r.sid, r.cfg_sha256,"
            " r.raw, r.received_ms FROM intents i JOIN events e ON e.key=i.key JOIN receipts r ON r.id=e.receipt_id"
            " WHERE i.ev='ENTRY' AND i.eligible=1 AND i.claimed_ms IS NULL ORDER BY e.bar_close").fetchall()

    def ea_heartbeat_age(self, now):
        try:
            t = _num(read_kv(self._x("hb_ea.txt")).get("t_ms"), int)
        except OSError:
            return None
        return None if not t else now - t

    def _check(self, c, now):
        """bridge-side checks before the claim (the EA checks again with live prices right before OrderSend)."""
        exp = self.cfg["expected"]
        try:
            sym = json.loads(c["raw"]).get("sym")
        except ValueError:
            sym = None
        path = (c["info"] or "").split(";")[0]
        if c["side"] != "SHORT":
            return "skip:side_not_short"
        if c["otype"] != "MARKET":
            return "skip:limit_not_supported" if c["otype"] == "LIMIT" else "skip:otype"
        if path not in ALLOWED_PATHS:
            return f"skip:path_not_initial_settings:{path}"
        if c["sid"] != exp["sid"]:
            return "skip:sid_mismatch"
        if exp.get("cfg_sha256") and c["cfg_sha256"] != exp["cfg_sha256"]:
            return "skip:cfg_mismatch"
        if sym != exp["symbol"]:
            return "skip:symbol_mismatch"
        if not (c["px"] and c["sl"] and c["tp"]) or not (c["sl"] > c["px"] > c["tp"] > 0):
            return "skip:price_geometry"
        age = now - c["bar_close"]
        if age < 0:
            return "skip:clock_or_future_bar"          # a negative age is never 'within the deadline'
        if age > MAX_AGE_SEC * 1000:
            return "skip:expired_before_claim"
        lim = self.cfg.get("require_ea_heartbeat_ms")
        if lim is not None:
            hb = self.ea_heartbeat_age(now)
            if hb is None or hb > lim or hb < -lim:
                return "skip:ea_heartbeat_stale"       # the EA is offline: the signal could not be executed in time anyway
        return None

    def still_valid(self, key, now):
        """None while the claimed ENTRY may still be executed; otherwise why not. Everything the receiver learnt AFTER the claim
        counts: its own post-claim re-decision (claim_note post_claim:*), a terminal / cancel / close-request fact of the trade, the
        end of the SATS wait the ENTRY came from, a pending re-evaluation, and the 60 s deadline."""
        st = self.rcv.store
        if st.one("SELECT v FROM meta WHERE k='reeval_pending'") is not None:
            return "receiver_reevaluation_pending"
        it = st.one("SELECT * FROM intents WHERE key=?", (key,))
        if it is None:
            return "intent_missing"
        if it["claimed_ms"] is None:
            return "not_claimed"
        note = it["claim_note"] or ""
        if note.startswith("post_claim:"):
            return "revoked_after_claim:" + note[len("post_claim:"):]
        ev = st.one("SELECT tid, bar_close, info FROM events WHERE key=?", (key,))
        if ev is None:
            return "entry_fact_missing"
        tr = st.one("SELECT terminal_seen FROM tv_trades WHERE tid=?", (ev["tid"],))
        if tr is not None and tr["terminal_seen"]:
            return "trade_terminated"
        x = st.one("SELECT ev FROM events WHERE tid=? AND ev IN (%s) ORDER BY bar_close LIMIT 1" % ",".join("?" * len(TERMINAL_FOR_ENTRY)),
                   (ev["tid"], *TERMINAL_FOR_ENTRY))
        if x is not None:
            return "tv_" + x["ev"].lower() + "_seen"
        wid = next((p[4:] for p in (ev["info"] or "").split(";") if p.startswith("wid=")), "")
        if wid:
            w = st.one("SELECT state FROM tv_waits WHERE wid=?", (wid,))
            if w is not None and (w["state"] or "").startswith("ENDED"):
                return "wait_ended:" + wid
        age = now - ev["bar_close"]
        if age < 0:
            return "clock_or_future_bar"
        if age > MAX_AGE_SEC * 1000:
            return "expired"
        return None

    def _write_cmd(self, c, claimed_ms):
        """one command file per key, written as .tmp and renamed (the EA only reads *.cmd)."""
        kh = key_hash(c["key"])
        lines = {"v": CMD_VERSION, "key": c["key"], "key_hash": kh, "tid": c["tid"], "ev": "ENTRY", "side": c["side"], "otype": c["otype"],
                 "path": (c["info"] or "").split(";")[0], "px": repr(float(c["px"])), "sl": repr(float(c["sl"])), "tp": repr(float(c["tp"])),
                 "bar_close_ms": str(c["bar_close"]), "cfg_sha256": c["cfg_sha256"] or "", "sid": c["sid"], "sym": self.cfg["expected"]["symbol"],
                 "received_ms": str(c["received_ms"]), "claimed_ms": str(claimed_ms)}
        body = "".join(f"{k}={v}\n" for k, v in lines.items())
        assert all("\n" not in str(v) and "=" not in k for k, v in lines.items())
        d = self._x("cmd")
        tmp = os.path.join(d, f"{c['bar_close']}_{kh}.tmp")
        with open(tmp, "w", encoding="ascii", newline="\n") as f:
            f.write(body)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, os.path.join(d, f"{c['bar_close']}_{kh}.cmd"))

    def _revoke(self, row, why, now, state="REVOKED_BEFORE_GO"):
        """no GO will ever be given for this key; its command file (if the EA has not taken it yet) is moved to revoked/."""
        self._set(row["key"], nogo_reason=why, revoked_ms=now, **({"state": state} if row["state"] in ("CLAIMED", "CMD_WRITTEN") else {}))
        name = f"{row['bar_close']}_{row['key_hash']}.cmd"
        try:
            os.replace(self._x("cmd", name), self._x("revoked", name))
        except OSError:
            pass                                       # already taken by the EA: its ask will get NOGO
        self.log.info("revoked %s before GO: %s", row["tid"], why)

    # -- one pass -------------------------------------------------------------------------------------------------------
    def once(self):
        self.ingest_reports()
        self.recover()
        self.answer_asks()
        self.revoke_invalid()
        n_cmd = 0
        for c in self._candidates():
            now = self.clock()
            if self._row(c["key"]) is None:
                self.db.execute("INSERT INTO lifecycle(key, key_hash, tid, bar_close, state, px, sl, tp, path, otype, received_ms, checked_ms)"
                                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                                (c["key"], key_hash(c["key"]), c["tid"], c["bar_close"], "CHECKED", c["px"], c["sl"], c["tp"],
                                 (c["info"] or "").split(";")[0], c["otype"], c["received_ms"], now))
            row = self._row(c["key"])
            if row["state"] not in ("CHECKED",):
                continue                                   # already handled (skipped / claimed) by this bridge
            why = self._check(c, now)
            if why:
                self._set(c["key"], state="SKIPPED_BY_BRIDGE", reason=why)
                self.log.info("skip %s %s", c["tid"], why)
                continue
            self._set(c["key"], state="CLAIMING", claim_start_ms=now)
            ok = self.rcv.claim(c["key"])                  # atomic; re-checks the 60 s deadline at the decision time
            if not ok:
                lg = self.rcv.store.one("SELECT reason FROM claim_log WHERE key=? ORDER BY id DESC LIMIT 1", (c["key"],))
                self._set(c["key"], state="CLAIM_REFUSED", reason=lg["reason"] if lg else "unknown")
                continue
            claimed = self.rcv.store.one("SELECT claimed_ms FROM intents WHERE key=?", (c["key"],))["claimed_ms"]
            self._set(c["key"], state="CLAIMED", claimed_ms=claimed)
            self._write_cmd(c, claimed)
            self._set(c["key"], state="CMD_WRITTEN", cmd_written_ms=self.clock())
            n_cmd += 1
        self.answer_asks()
        self.check_divergence()
        self.write_heartbeat()
        return n_cmd

    def recover(self):
        """after a bridge restart: a key claimed (by this bridge) but whose command was not written is written only if it is still
        valid (still_valid: not revoked / terminated / wait ended, within the deadline); otherwise it is closed without a command. A key
        left in CLAIMING is resolved from the receiver's intent (claimed_ms) — never claimed twice."""
        for row in self.db.execute("SELECT * FROM lifecycle WHERE state IN ('CLAIMING', 'CLAIMED')").fetchall():
            it = self.rcv.store.one("SELECT claimed_ms FROM intents WHERE key=?", (row["key"],))
            if row["state"] == "CLAIMING" and (it is None or it["claimed_ms"] is None):
                self._set(row["key"], state="CLAIM_REFUSED", reason="bridge_restart_before_claim")
                continue
            now = self.clock()
            why = self.still_valid(row["key"], now)
            if why == "expired":
                self._set(row["key"], state="EXPIRED_AFTER_BRIDGE_RESTART", claimed_ms=it["claimed_ms"], nogo_reason=why, revoked_ms=now)
                continue
            if why:
                self._set(row["key"], claimed_ms=it["claimed_ms"])
                self._revoke(self._row(row["key"]), why, now, state="REVOKED_AFTER_BRIDGE_RESTART")
                continue
            c = self.rcv.store.one(
                "SELECT i.key, i.tid, e.bar_close, e.side, e.otype, e.px, e.sl, e.tp, e.info, r.sid, r.cfg_sha256, r.received_ms"
                " FROM intents i JOIN events e ON e.key=i.key JOIN receipts r ON r.id=e.receipt_id WHERE i.key=?", (row["key"],))
            self._write_cmd(c, it["claimed_ms"])
            self._set(row["key"], state="CMD_WRITTEN", claimed_ms=it["claimed_ms"], cmd_written_ms=self.clock())

    def revoke_invalid(self):
        """commands not yet given a GO (the EA may not even have read them) whose ENTRY is no longer valid are revoked."""
        for row in self.db.execute("SELECT * FROM lifecycle WHERE cmd_written_ms IS NOT NULL AND go_ms IS NULL AND nogo_reason IS NULL"
                                   " AND state IN ('CMD_WRITTEN', 'EA_SEEN')").fetchall():
            now = self.clock()
            why = self.still_valid(row["key"], now)
            if why:
                self._revoke(row, why, now)

    def answer_asks(self):
        """the EA's final ask: GO at most once per key and only while still_valid(); the decision is stored before the answer file."""
        d = self._x("ask")
        for name in sorted(os.listdir(d)):
            if not name.endswith(".ask"):
                continue
            p = os.path.join(d, name)
            try:
                f = read_kv(p)
            except OSError:
                continue
            kh = f.get("key_hash", "")
            now = self.clock()
            row = self.db.execute("SELECT * FROM lifecycle WHERE key_hash=?", (kh,)).fetchone() if kh else None
            until = None
            if row is None:
                why = "unknown_key"
            elif row["go_ms"] is not None:
                why = "already_granted"
            elif row["nogo_reason"]:
                why = row["nogo_reason"]
            elif row["claimed_ms"] is None or row["cmd_written_ms"] is None:
                why = "not_commanded"
            else:
                why = self.still_valid(row["key"], now)
            if why is None:
                until = min(now + int(self.cfg.get("go_ttl_ms") or 3000), row["bar_close"] + MAX_AGE_SEC * 1000)
                self._set(row["key"], go_ms=now, go_until_ms=until)
            elif row is not None and row["go_ms"] is None and not row["nogo_reason"]:
                self._revoke(row, why, now)
            self.db.execute("INSERT INTO answers(key_hash, ask_t_ms, decision, reason, valid_until_ms, dry_run, t_ms) VALUES (?,?,?,?,?,?,?)",
                            (kh, _num(f.get("t_ms"), int), "GO" if why is None else "NOGO", why, until, f.get("dry_run"), now))
            body = f"key_hash={kh}\ndecision={'GO' if why is None else 'NOGO'}\nreason={why or 'ok'}\nvalid_until_ms={until or 0}\nt_ms={now}\n"
            if kh and all(ch in "0123456789abcdef" for ch in kh) and len(kh) == 16:
                write_atomic(self._x("ans", kh + ".ans"), body)
            os.replace(p, self._x("ask_done", f"{name}.{now}"))

    def write_heartbeat(self):
        last = self.rcv.store.one("SELECT MAX(received_ms) m FROM receipts")
        write_atomic(self._x("hb_bridge.txt"), f"t_ms={self.clock()}\nlast_receipt_ms={(last and last['m']) or 0}\n")

    def ingest_reports(self):
        d = self._x("rpt")
        for name in sorted(os.listdir(d)):
            if not name.endswith(".rpt"):
                continue
            p = os.path.join(d, name)
            try:
                fields = read_kv(p)
            except OSError:
                continue
            kh, state = fields.get("key_hash", ""), fields.get("state", "")
            t = _num(fields.get("t_ms"), int) or 0
            try:
                self.db.execute("INSERT INTO ea_reports(file, key_hash, state, t_ms, fields, ingested_ms) VALUES (?,?,?,?,?,?)",
                                (name, kh, state, t, json.dumps(fields), self.clock()))
            except sqlite3.IntegrityError:
                pass
            row = self.db.execute("SELECT * FROM lifecycle WHERE key_hash=?", (kh,)).fetchone() if kh else None
            col = EA_STATE_TIME.get(state)
            if row is not None and col:
                key = row["key"]
                upd = {"state": "EA_" + state}
                if row[col] is None:
                    upd[col] = t
                for f_, c_ in (("retcode", "ea_retcode"), ("order", "ea_order"), ("deal", "ea_deal"), ("position", "ea_position"),
                               ("fill_price", "fill_price"), ("volume", "volume")):
                    v = _num(fields.get(f_), float if c_ in ("fill_price", "volume") else int)
                    if v is not None:
                        upd[c_] = v
                if fields.get("reason"):
                    upd["reason"] = fields["reason"][:300]
                if state in ("FILLED", "OWNED_AT_STARTUP") and fields.get("position"):
                    upd["mt5_open"] = 1
                if state == "CLOSED":
                    upd["mt5_open"] = 0
                self._set(key, **upd)
            os.replace(p, self._x("rpt_done", name))

    def check_divergence(self):
        """TradingView closed its virtual trade while the MT5 position (per EA reports) is open: record only, never act."""
        for row in self.db.execute("SELECT key, tid FROM lifecycle WHERE mt5_open=1").fetchall():
            for e in self.rcv.store.all("SELECT ev, bar_close FROM events WHERE tid=? AND ev IN ('TV_FLAT', 'TV_CLOSED', 'CANCEL')", (row["tid"],)):
                try:
                    self.db.execute("INSERT INTO divergences(key, tid, kind, detail, t_ms) VALUES (?,?,?,?,?)",
                                    (row["key"], row["tid"], "tv_exit_while_mt5_open", f"{e['ev']}@{e['bar_close']}", self.clock()))
                    self.log.warning("divergence: TradingView %s for %s while the MT5 position is open (no action)", e["ev"], row["tid"])
                except sqlite3.IntegrityError:
                    pass

    def run(self):
        self.log.info("bridge running (receiver DB %s, exchange %s); it never calls a trade API", self.cfg["receiver_data_dir"],
                      self.cfg["exchange_dir"])
        try:
            while True:
                try:
                    self.once()
                except Exception:
                    self.log.exception("pass failed (next pass continues)")
                time.sleep(self.cfg["poll_ms"] / 1000.0)
        except KeyboardInterrupt:
            pass


def setup_log(cfg):
    os.makedirs(cfg["bridge_data_dir"], exist_ok=True)
    log = logging.getLogger("ea_bridge")
    log.setLevel(logging.INFO)
    if not log.handlers:
        import logging.handlers
        fh = logging.handlers.RotatingFileHandler(os.path.join(cfg["bridge_data_dir"], "bridge.log"), maxBytes=5_000_000, backupCount=5,
                                                  encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        log.addHandler(fh)
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        log.addHandler(sh)
    return log


def main(argv=None):
    ap = argparse.ArgumentParser(description="XAU Short stage-3 bridge (receiver -> demo EA); no trade API")
    ap.add_argument("cmd", choices=["run", "once", "status"])
    ap.add_argument("--config", required=True)
    ap.add_argument("--last", type=int, default=20)
    a = ap.parse_args(argv)
    cfg = load_config(a.config)
    if a.cmd == "status":
        db = sqlite3.connect(os.path.join(cfg["bridge_data_dir"], "bridge.sqlite3"))
        db.row_factory = sqlite3.Row
        now = now_ms()
        for nm in ("hb_ea.txt", "hb_bridge.txt"):
            try:
                kv = read_kv(os.path.join(cfg["exchange_dir"], nm))
                print(f"{nm}: age {(now - int(kv.get('t_ms', '0'))) / 1000:.1f} s  " + " ".join(f"{k}={v}" for k, v in kv.items() if k != "t_ms"))
            except (OSError, ValueError):
                print(f"{nm}: missing")
        for r in db.execute("SELECT * FROM lifecycle ORDER BY bar_close DESC LIMIT ?", (a.last,)):
            print(f'{r["tid"]} {r["state"]:<28} reason={r["reason"]} go={iso(r["go_ms"])} nogo={r["nogo_reason"]} retcode={r["ea_retcode"]}'
                  f' pos={r["ea_position"]} fill={r["fill_price"]} vol={r["volume"]} claimed={iso(r["claimed_ms"])} cmd={iso(r["cmd_written_ms"])}')
        for r in db.execute("SELECT * FROM divergences ORDER BY id DESC LIMIT 10"):
            print(f'DIVERGENCE {r["tid"]} {r["kind"]} {r["detail"]}')
        return 0
    b = Bridge(cfg, log=setup_log(cfg))
    try:
        if a.cmd == "once":
            print(json.dumps({"commands_written": b.once()}))
        else:
            b.run()
    finally:
        b.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
