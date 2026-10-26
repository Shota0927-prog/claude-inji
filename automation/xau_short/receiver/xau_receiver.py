#!/usr/bin/env python3
"""XAU Short automation — stage 2 notification receiver / recorder (NO ORDERS).

Receives the JSON alerts of automation/xau_short/pine/ZoneStrategyXAU_Auto.pine (TradingView webhook, or local sample files),
validates them, and records every receipt in a SQLite database that survives restarts. It never connects to MT5 and never
places, cancels or modifies an order: the MT5 side is a separate, empty state ("NOT_CONNECTED") kept for the later stages.

Standard library only (Python 3.10+, Windows / Linux).

  python xau_receiver.py serve  [--config config.json]          HTTP receiver (POST /webhook/<token>)
  python xau_receiver.py ingest FILE [FILE ...] [--config ...]   process local sample files (JSON object, array or JSON lines)
  python xau_receiver.py show   [--last N] [--config ...]        recent receipts
  python xau_receiver.py status [--config ...]                   TradingView virtual trades / waits, MT5 state (separate)

The webhook token is read from an environment variable (config "token_env", default XAU_RECEIVER_TOKEN); it is never written to
the code, the config, the database or the log.
"""
import argparse
import hashlib
import hmac
import json
import logging
import logging.handlers
import os
import sqlite3
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SCHEMA = "xau-auto/1"
DB_VERSION = "1"
HERE = os.path.dirname(os.path.abspath(__file__))

DEFAULT_CONFIG = {
    "host": "127.0.0.1",
    "port": 8787,
    "data_dir": "data",
    "token_env": "XAU_RECEIVER_TOKEN",
    "max_body_bytes": 16384,
    "expected": {
        "schema": SCHEMA,
        "sid": "XAU-SHORT|XA-23|AU-1",
        "symbol": "OANDA:XAUUSD",
        "timeframe": "5",
        "allowed_sides": ["SHORT"],
        "cfg_sha256": None,           # None = not pinned yet (recorded as a warning); set after the first real alert is checked
    },
    "policy": {
        "max_age_sec": None,          # notification deadline: NOT approved yet -> None = not enforced (age is recorded)
    },
}

# event -> (tid prefix, actionable in a later stage, needs prices)
EVENTS = {
    "PROV": ("P", False, False), "ENTRY": ("T", True, True), "CANCEL": ("T", True, False), "TV_FILL": ("T", False, False),
    "TP_SET": ("T", True, False), "BE_MOVE": ("T", True, False), "CLOSE_REQ": ("T", True, False), "TV_CLOSED": ("T", False, False),
    "TV_FLAT": ("T", False, False), "WAIT_START": ("W", False, False), "WAIT_END": ("W", False, False),
}
RANKS = {"PROV": 1, "WAIT_START": 5, "ENTRY": 10, "CANCEL": 20, "TV_FILL": 30, "TP_SET": 40, "BE_MOVE": 50, "CLOSE_REQ": 60,
         "TV_CLOSED": 70, "TV_FLAT": 90, "WAIT_END": 95}
REQUIRED = {"schema": str, "sid": str, "cfg": str, "ev": str, "key": str, "tid": str, "rank": int, "sym": str, "tf": str,
            "bar_open": int, "bar_close": int, "sent": int, "side": str, "otype": str, "px": (int, float, type(None)),
            "sl": (int, float, type(None)), "tp": (int, float, type(None)), "info": str}
# TradingView virtual trade lifecycle: allowed event per state (anything else is an invalid transition)
TRANSITIONS = {
    "INTENT": {"CANCEL": "CANCELLED", "TV_FILL": "TV_OPEN", "TV_CLOSED": "CLOSED"},
    "TV_OPEN": {"TP_SET": "TV_OPEN", "BE_MOVE": "TV_OPEN", "CLOSE_REQ": "CLOSING", "TV_FLAT": "CLOSED"},
    "CLOSING": {"TV_FLAT": "CLOSED"},
}
TERMINAL = {"CANCELLED", "CLOSED"}
STAGE2_MT5_ACTION = "NONE (stage 2: no MT5 connection, no orders)"


def utc_iso(ms):
    return datetime.fromtimestamp(ms / 1000, timezone.utc).isoformat(timespec="milliseconds")


def load_config(path):
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    if path:
        with open(path, encoding="utf-8") as f:
            user = json.load(f)
        for k, v in user.items():
            if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                cfg[k].update(v)
            else:
                cfg[k] = v
    base = os.path.dirname(os.path.abspath(path)) if path else HERE
    if not os.path.isabs(cfg["data_dir"]):
        cfg["data_dir"] = os.path.join(base, cfg["data_dir"])
    return cfg


class Store:
    """SQLite store (WAL). All writes of one receipt happen in one transaction."""

    def __init__(self, data_dir):
        os.makedirs(data_dir, exist_ok=True)
        self.path = os.path.join(data_dir, "xau_receiver.sqlite3")
        self.db = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT);
        CREATE TABLE IF NOT EXISTS receipts (
            id INTEGER PRIMARY KEY AUTOINCREMENT, received_ms INTEGER NOT NULL, received_utc TEXT NOT NULL, source TEXT,
            status TEXT NOT NULL, reasons TEXT NOT NULL, raw TEXT,
            key TEXT, ev TEXT, tid TEXT, sid TEXT, cfg_sha256 TEXT, rank INTEGER, bar_open INTEGER, bar_close INTEGER, sent INTEGER,
            age_ms INTEGER, side TEXT, otype TEXT, px REAL, sl REAL, tp REAL, info TEXT, actionable INTEGER, mt5_action TEXT);
        CREATE INDEX IF NOT EXISTS receipts_key ON receipts(key);
        CREATE TABLE IF NOT EXISTS events (key TEXT PRIMARY KEY, receipt_id INTEGER NOT NULL, ev TEXT, tid TEXT,
            bar_close INTEGER, rank INTEGER);
        CREATE TABLE IF NOT EXISTS tv_trades (tid TEXT PRIMARY KEY, state TEXT, side TEXT, otype TEXT, path TEXT, wid TEXT,
            entry_px REAL, sl REAL, tp REAL, entry_bar_close INTEGER, last_ev TEXT, last_bar_close INTEGER, last_rank INTEGER,
            updated_utc TEXT);
        CREATE TABLE IF NOT EXISTS tv_waits (wid TEXT PRIMARY KEY, state TEXT, side TEXT, p0 REAL, sl0 REAL, tp0 REAL,
            start_bar_close INTEGER, end_bar_close INTEGER, end_reason TEXT, last_rank INTEGER, updated_utc TEXT);
        CREATE TABLE IF NOT EXISTS mt5_positions (tid TEXT PRIMARY KEY, state TEXT NOT NULL DEFAULT 'NOT_CONNECTED',
            ticket TEXT, volume REAL, open_price REAL, sl REAL, tp REAL, updated_utc TEXT);
        """)
        self.db.execute("INSERT OR IGNORE INTO meta(k, v) VALUES ('db_version', ?)", (DB_VERSION,))

    def one(self, sql, args=()):
        return self.db.execute(sql, args).fetchone()

    def all(self, sql, args=()):
        return self.db.execute(sql, args).fetchall()


def validate_shape(msg, exp):
    """format / schema / identity checks that need no state. Returns (errors, warnings, cfg_sha256)."""
    errs, warns = [], []
    if not isinstance(msg, dict):
        return ["format:not_object"], warns, None
    for k, t in REQUIRED.items():
        if k not in msg:
            errs.append(f"format:missing:{k}")
        elif isinstance(msg[k], bool) or not isinstance(msg[k], t):
            errs.append(f"format:type:{k}")
    if errs:
        return errs, warns, None
    ev = msg["ev"]
    if ev not in EVENTS:
        return [f"format:unknown_event:{ev}"], warns, None
    cfg_sha = hashlib.sha256(msg["cfg"].encode("utf-8")).hexdigest()
    if msg["schema"] != exp["schema"]:
        errs.append("identity:schema_mismatch")
    if msg["sid"] != exp["sid"]:
        errs.append("identity:sid_mismatch")
    if exp.get("symbol") and msg["sym"] != exp["symbol"]:
        errs.append("identity:symbol_mismatch")
    if exp.get("timeframe") and msg["tf"] != exp["timeframe"]:
        errs.append("identity:timeframe_mismatch")
    if exp.get("cfg_sha256"):
        if cfg_sha != exp["cfg_sha256"]:
            errs.append("identity:cfg_mismatch")
    else:
        warns.append("warn:cfg_unpinned")
    if msg["key"] != f'{msg["sid"]}|{ev}|{msg["tid"]}|{msg["bar_close"]}':
        errs.append("format:key_mismatch")
    if msg["rank"] != RANKS[ev]:
        errs.append("format:rank_mismatch")
    if not msg["tid"].startswith(EVENTS[ev][0]) or not msg["tid"][1:].isdigit():
        errs.append("format:tid_form")
    if not (0 < msg["bar_open"] < msg["bar_close"]):
        errs.append("format:bar_times")
    if msg["side"] not in ("SHORT", "LONG", ""):
        errs.append("format:side")
    if ev == "ENTRY":
        if msg["side"] not in exp.get("allowed_sides", ["SHORT"]):
            errs.append("intent:side_not_allowed")
        if msg["otype"] not in ("MARKET", "LIMIT"):
            errs.append("intent:otype")
        if msg["tid"] != f'T{msg["bar_close"]}':
            errs.append("intent:tid_not_decision_bar")
        if None in (msg["px"], msg["sl"], msg["tp"]):
            errs.append("intent:price_missing")
        else:
            s = -1 if msg["side"] == "SHORT" else 1
            if not (s * (msg["px"] - msg["sl"]) > 0 and s * (msg["tp"] - msg["px"]) > 0):
                errs.append("intent:price_geometry")
    return errs, warns, cfg_sha


class Receiver:
    def __init__(self, cfg, log=None):
        self.cfg = cfg
        self.store = Store(cfg["data_dir"])
        self.log = log or logging.getLogger("xau_receiver")

    # -- the whole pipeline for one body; always records a receipt ---------------------------------------------------
    def process(self, body, source="local", now_ms=None):
        now_ms = int(time.time() * 1000) if now_ms is None else now_ms
        raw = body.decode("utf-8", "replace") if isinstance(body, (bytes, bytearray)) else str(body)
        msg, errs, warns, cfg_sha = None, [], [], None
        try:
            msg = json.loads(raw)
        except (ValueError, TypeError):
            errs = ["format:not_json"]
        if not errs:
            errs, warns, cfg_sha = validate_shape(msg, self.cfg["expected"])
        with self.store.lock:
            db = self.store.db
            db.execute("BEGIN IMMEDIATE")
            try:
                status, reasons = self._decide(msg, errs, warns, now_ms)
                rid = self._record(msg if isinstance(msg, dict) else {}, raw, source, status, reasons, cfg_sha, now_ms)
                if status == "ACCEPTED":
                    self._apply(msg, rid)
                db.execute("COMMIT")
            except Exception:
                db.execute("ROLLBACK")
                raise
        self.log.info("receipt %s status=%s ev=%s tid=%s reasons=%s", rid, status,
                      msg.get("ev") if isinstance(msg, dict) else None, msg.get("tid") if isinstance(msg, dict) else None,
                      ",".join(reasons) or "-")
        return {"id": rid, "status": status, "reasons": reasons}

    def _decide(self, msg, errs, warns, now_ms):
        if errs:
            return "REJECTED", errs + warns
        s = self.store
        if s.one("SELECT 1 FROM events WHERE key = ?", (msg["key"],)):
            return "DUPLICATE", ["dup:same_key_already_accepted"] + warns
        ev, tid, bc, rank = msg["ev"], msg["tid"], msg["bar_close"], msg["rank"]
        reasons = list(warns)
        mx = self.cfg["policy"].get("max_age_sec")
        if mx is not None and EVENTS[ev][1] and now_ms - bc > mx * 1000:
            return "REJECTED", ["late:older_than_max_age"] + reasons
        if ev == "PROV":
            return "ACCEPTED", reasons
        if ev in ("WAIT_START", "WAIT_END"):
            w = s.one("SELECT * FROM tv_waits WHERE wid = ?", (tid,))
            if ev == "WAIT_START":
                return ("REJECTED", ["order:wait_exists"] + reasons) if w else ("ACCEPTED", reasons)
            if not w:
                return "REJECTED", ["state:unknown_wait"] + reasons
            if w["state"] != "OPEN":
                return "REJECTED", [f"state:wait_{w['state'].lower()}"] + reasons
            if (bc, rank) < (w["start_bar_close"], w["last_rank"]):
                return "REJECTED", ["order:out_of_order"] + reasons
            return "ACCEPTED", reasons
        t = s.one("SELECT * FROM tv_trades WHERE tid = ?", (tid,))
        if ev == "ENTRY":
            if t:
                return "REJECTED", ["state:trade_exists"] + reasons
            newer = s.one("SELECT tid FROM tv_trades WHERE entry_bar_close > ? LIMIT 1", (bc,))
            if newer:
                return "REJECTED", [f"late:older_than_newer_trade:{newer['tid']}"] + reasons
            act = s.one("SELECT tid, state FROM tv_trades WHERE state NOT IN ('CANCELLED', 'CLOSED') LIMIT 1")
            if act:
                return "REJECTED", [f"state:virtual_position_active:{act['tid']}"] + reasons
            wid = dict(p.split("=", 1) for p in msg["info"].split(";") if "=" in p).get("wid")
            if wid:
                w = s.one("SELECT * FROM tv_waits WHERE wid = ?", (wid,))
                if w and w["state"] == "ENDED" and w["end_bar_close"] <= bc:
                    return "REJECTED", [f"late:wait_already_ended:{wid}"] + reasons
                if w is None:
                    reasons.append("warn:wait_not_seen")
            return "ACCEPTED", reasons
        if not t:
            return "REJECTED", ["state:unknown_trade"] + reasons
        if t["state"] in TERMINAL:
            return "REJECTED", [f"state:trade_{t['state'].lower()}"] + reasons
        if (bc, rank) < (t["last_bar_close"], t["last_rank"]):
            return "REJECTED", ["order:out_of_order"] + reasons
        if ev not in TRANSITIONS.get(t["state"], {}):
            return "REJECTED", [f"state:invalid_transition:{t['state']}->{ev}"] + reasons
        return "ACCEPTED", reasons

    def _record(self, m, raw, source, status, reasons, cfg_sha, now_ms):
        ev = m.get("ev") if isinstance(m.get("ev"), str) else None
        num = lambda k: m.get(k) if isinstance(m.get(k), (int, float)) and not isinstance(m.get(k), bool) else None
        txt = lambda k: m.get(k) if isinstance(m.get(k), str) else None
        bc = num("bar_close")
        cur = self.store.db.execute(
            "INSERT INTO receipts(received_ms, received_utc, source, status, reasons, raw, key, ev, tid, sid, cfg_sha256, rank, bar_open,"
            " bar_close, sent, age_ms, side, otype, px, sl, tp, info, actionable, mt5_action)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (now_ms, utc_iso(now_ms), source, status, json.dumps(reasons), raw[:self.cfg["max_body_bytes"]], txt("key"), ev,
             txt("tid"), txt("sid"), cfg_sha, num("rank"), num("bar_open"), bc, num("sent"),
             (now_ms - int(bc)) if bc is not None else None, txt("side"), txt("otype"), num("px"), num("sl"), num("tp"), txt("info"),
             int(bool(ev in EVENTS and EVENTS[ev][1])), STAGE2_MT5_ACTION))
        return cur.lastrowid

    def _apply(self, m, rid):
        db, ev, tid, bc, rank = self.store.db, m["ev"], m["tid"], m["bar_close"], m["rank"]
        now = utc_iso(int(time.time() * 1000))
        db.execute("INSERT INTO events(key, receipt_id, ev, tid, bar_close, rank) VALUES (?,?,?,?,?,?)", (m["key"], rid, ev, tid, bc, rank))
        if ev == "WAIT_START":
            db.execute("INSERT INTO tv_waits(wid, state, side, p0, sl0, tp0, start_bar_close, last_rank, updated_utc) VALUES (?,?,?,?,?,?,?,?,?)",
                       (tid, "OPEN", m["side"], m["px"], m["sl"], m["tp"], bc, rank, now))
        elif ev == "WAIT_END":
            db.execute("UPDATE tv_waits SET state='ENDED', end_bar_close=?, end_reason=?, last_rank=?, updated_utc=? WHERE wid=?",
                       (bc, m["info"], rank, now, tid))
        elif ev == "ENTRY":
            info = dict(p.split("=", 1) for p in m["info"].split(";") if "=" in p)
            path = m["info"].split(";")[0]
            db.execute("INSERT INTO tv_trades(tid, state, side, otype, path, wid, entry_px, sl, tp, entry_bar_close, last_ev, last_bar_close,"
                       " last_rank, updated_utc) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                       (tid, "INTENT", m["side"], m["otype"], path, info.get("wid"), m["px"], m["sl"], m["tp"], bc, ev, bc, rank, now))
            if info.get("wid"):
                db.execute("UPDATE tv_waits SET state='CONSUMED', end_bar_close=?, end_reason='entry', updated_utc=? WHERE wid=? AND state='OPEN'",
                           (bc, now, info["wid"]))
        elif ev in EVENTS and EVENTS[ev][0] == "T":
            t = db.execute("SELECT state, sl, tp FROM tv_trades WHERE tid=?", (tid,)).fetchone()
            new = TRANSITIONS[t["state"]][ev]
            sl = m["sl"] if ev in ("TP_SET", "BE_MOVE") and m["sl"] is not None else t["sl"]
            tp = m["tp"] if ev == "TP_SET" and m["tp"] is not None else t["tp"]
            db.execute("UPDATE tv_trades SET state=?, sl=?, tp=?, last_ev=?, last_bar_close=?, last_rank=?, updated_utc=? WHERE tid=?",
                       (new, sl, tp, ev, bc, rank, now, tid))


# ---- HTTP -----------------------------------------------------------------------------------------------------------
def make_handler(rcv, token):
    class Handler(BaseHTTPRequestHandler):
        server_version = "xau-receiver/1"

        def log_message(self, fmt, *args):     # never log the request path (it carries the token)
            rcv.log.debug("http %s %s", self.client_address[0], self.command)

        def _reply(self, code, obj):
            body = json.dumps(obj).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/health":
                return self._reply(200, {"ok": True, "stage": 2, "orders": "disabled"})
            return self._reply(404, {"error": "not_found"})

        def do_POST(self):
            parts = self.path.split("?")[0].strip("/").split("/")
            if len(parts) != 2 or parts[0] != "webhook" or not token or not hmac.compare_digest(parts[1].encode(), token.encode()):
                rcv.log.warning("unauthorized POST from %s", self.client_address[0])
                return self._reply(404, {"error": "not_found"})
            n = int(self.headers.get("Content-Length") or 0)
            if n <= 0 or n > rcv.cfg["max_body_bytes"]:
                rcv.log.warning("rejected body size %s from %s", n, self.client_address[0])
                return self._reply(413, {"error": "size"})
            res = rcv.process(self.rfile.read(n), source=f"http:{self.client_address[0]}")
            return self._reply(200, res)
    return Handler


def setup_log(cfg):
    os.makedirs(cfg["data_dir"], exist_ok=True)
    log = logging.getLogger("xau_receiver")
    log.setLevel(logging.INFO)
    if not log.handlers:
        fh = logging.handlers.RotatingFileHandler(os.path.join(cfg["data_dir"], "receiver.log"), maxBytes=5_000_000, backupCount=5,
                                                  encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        log.addHandler(fh)
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        log.addHandler(sh)
    return log


def serve(cfg, token=None, ready=None, stop=None):
    rcv = Receiver(cfg, setup_log(cfg))
    token = token if token is not None else os.environ.get(cfg["token_env"], "")
    if not token:
        rcv.log.error("environment variable %s is not set: refusing to start (no token, no receiver)", cfg["token_env"])
        return 2
    srv = ThreadingHTTPServer((cfg["host"], int(cfg["port"])), make_handler(rcv, token))
    with open(os.path.join(cfg["data_dir"], "receiver.pid"), "w") as f:
        f.write(str(os.getpid()))
    rcv.log.info("listening on %s:%s (POST /webhook/<token>, GET /health); stage 2: no orders", cfg["host"], srv.server_address[1])
    if ready is not None:
        ready(srv)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
        rcv.log.info("stopped")
    return 0


def read_samples(path):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    s = text.strip()
    if s.startswith("["):
        return [json.dumps(x, ensure_ascii=False) for x in json.loads(s)]
    if s.startswith("{") and "\n{" not in s:
        return [s]
    return [ln for ln in text.splitlines() if ln.strip()]


def main(argv=None):
    ap = argparse.ArgumentParser(description="XAU Short stage-2 receiver (no orders)")
    ap.add_argument("cmd", choices=["serve", "ingest", "show", "status"])
    ap.add_argument("files", nargs="*")
    ap.add_argument("--config", default=None)
    ap.add_argument("--last", type=int, default=20)
    a = ap.parse_args(argv)
    cfg = load_config(a.config)
    if a.cmd == "serve":
        return serve(cfg)
    if a.cmd == "ingest":
        rcv = Receiver(cfg, setup_log(cfg))
        for p in a.files:
            for body in read_samples(p):
                r = rcv.process(body, source=f"file:{os.path.basename(p)}")
                print(json.dumps(r, ensure_ascii=False))
        return 0
    st = Store(cfg["data_dir"])
    if a.cmd == "show":
        for r in reversed(st.all("SELECT * FROM receipts ORDER BY id DESC LIMIT ?", (a.last,))):
            print(f'{r["id"]:>6} {r["received_utc"]} {r["status"]:<9} {str(r["ev"]):<10} {str(r["tid"]):<16} '
                  f'bar_close={r["bar_close"]} px={r["px"]} sl={r["sl"]} tp={r["tp"]} reasons={r["reasons"]}')
        return 0
    print("TradingView virtual trades (TV_* = the Strategy's own state, not MT5):")
    for r in st.all("SELECT * FROM tv_trades ORDER BY entry_bar_close DESC LIMIT 20"):
        print(f'  {r["tid"]} {r["state"]:<9} {r["side"]} {r["otype"]} {r["path"]} entry={r["entry_px"]} sl={r["sl"]} tp={r["tp"]} last={r["last_ev"]}')
    print("TradingView SATS waits:")
    for r in st.all("SELECT * FROM tv_waits ORDER BY start_bar_close DESC LIMIT 20"):
        print(f'  {r["wid"]} {r["state"]:<8} {r["side"]} p0={r["p0"]} sl0={r["sl0"]} tp0={r["tp0"]} end={r["end_reason"]}')
    n = st.one("SELECT COUNT(*) AS n FROM mt5_positions")["n"]
    print(f"MT5 actual positions: NOT_CONNECTED (stage 2; {n} rows, never written)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
