#!/usr/bin/env python3
"""XAU Short automation — stage 2 notification receiver / recorder (NO ORDERS).

Receives the JSON alerts of automation/xau_short/pine/ZoneStrategyXAU_Auto.pine (TradingView webhook, or local sample files),
checks them and records them in a SQLite database that survives restarts. It never connects to MT5 and never places, cancels or
modifies an order: the MT5 side is a separate, empty state ("NOT_CONNECTED") kept for the later stages.

Three separate layers (AU-2):
  1. record      receipts   every request, always (also invalid / duplicate / internal error), with the reasons
  2. facts       events     every valid, new event (any arrival order). The TradingView virtual trade / wait states are
                            DERIVED by replaying a trade's events in (bar_close, rank) order on every new event, so an event
                            that arrives early is kept PENDING and re-evaluated; terminal / cancel facts are kept for good
  3. eligibility intents    per actionable event: may a later stage act on it (eligible 0/1 + reason + how to use it).
                            Re-evaluated on new facts until claimed; claim() is atomic (one claim per event key) so a later
                            stage cannot execute an event twice. Stage 2 never claims and never acts.

Standard library only (Python 3.10+, Windows / Linux).

  python xau_receiver.py serve  [--config config.json]          HTTP receiver (POST /webhook/<token>)
  python xau_receiver.py ingest FILE [FILE ...] [--config ...]   process local sample files (JSON object, array or JSON lines)
  python xau_receiver.py show   [--last N] [--config ...]        recent receipts
  python xau_receiver.py status [--config ...]                   TradingView virtual trades / waits, intents, MT5 state (separate)

The webhook token is read from an environment variable (config "token_env", default XAU_RECEIVER_TOKEN); it is never written to
the code, the config, the database or the log.
"""
import argparse
import hashlib
import hmac
import json
import logging
import logging.handlers
import math
import os
import sqlite3
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SCHEMA = "xau-auto/2"
DB_VERSION = "4"
RULES_VERSION = "4"     # replay / eligibility rules; a stored DB with other rules is fully re-evaluated on open
HERE = os.path.dirname(os.path.abspath(__file__))
BAR_MS = 300_000
# format / storage sanity bounds (not trading thresholds)
TIME_MIN_MS, TIME_MAX_MS = 946_684_800_000, 4_102_444_800_000      # 2000-01-01 .. 2100-01-01 UTC
PRICE_MAX = 1e7
INT64 = (-(2 ** 63), 2 ** 63 - 1)
MAX_TEXT = {"cfg": 8000, "info": 300, "key": 200, "tid": 40, "sid": 80, "sym": 60, "tf": 10, "schema": 20, "ev": 20, "side": 10,
            "otype": 10}

DEFAULT_CONFIG = {
    "host": "127.0.0.1",
    "port": 8787,
    "data_dir": "data",
    "token_env": "XAU_RECEIVER_TOKEN",
    "max_body_bytes": 16384,
    "expected": {
        "schema": SCHEMA,
        "sid": "XAU-SHORT|XA-23|AU-2",
        "symbol": "OANDA:XAUUSD",
        "timeframe": "5",
        "allowed_sides": ["SHORT"],
        "cfg_sha256": None,           # None = not pinned yet (recorded as a warning); set after the first real alert is checked
    },
    "policy": {                       # NOT approved yet -> None = not enforced (the measured values are always recorded)
        "max_age_sec": None,          # notification deadline for actionable events (received - bar_close)
        "max_future_skew_sec": None,  # allowed clock skew when sent / bar_close lie in the future of the receive time
    },
}

# event -> tid prefix, actionable in a later stage
EVENTS = {"PROV": "P", "ENTRY": "T", "CANCEL": "T", "TV_FILL": "T", "TP_SET": "T", "BE_MOVE": "T", "CLOSE_REQ": "T",
          "TV_CLOSED": "T", "TV_FLAT": "T", "WAIT_START": "W", "WAIT_END": "W", "BAR": "B"}
RANKS = {"PROV": 1, "WAIT_START": 5, "ENTRY": 10, "CANCEL": 20, "TV_FILL": 30, "TP_SET": 40, "BE_MOVE": 50, "CLOSE_REQ": 60,
         "TV_CLOSED": 70, "TV_FLAT": 90, "WAIT_END": 95, "BAR": 98}
REQUIRED = {"schema": str, "sid": str, "cfg": str, "ev": str, "key": str, "tid": str, "rank": int, "sym": str, "tf": str,
            "bar_open": int, "bar_close": int, "sent": int, "side": str, "otype": str, "px": "num?", "sl": "num?", "tp": "num?",
            "o": "num?", "h": "num?", "l": "num?", "c": "num?", "info": str}
NEED = {"PROV": ("px", "sl"), "ENTRY": ("px", "sl", "tp"), "CANCEL": (), "TV_FILL": ("px", "sl"), "TP_SET": ("px", "sl", "tp"),
        "BE_MOVE": ("px", "sl"), "CLOSE_REQ": ("px",), "TV_CLOSED": ("px",), "TV_FLAT": (), "WAIT_START": ("px", "sl", "tp"),
        "WAIT_END": (), "BAR": ("px", "o", "h", "l", "c")}
TRANSITIONS = {   # TradingView virtual trade lifecycle (replayed in bar order)
    "INTENT": {"CANCEL": "CANCELLED", "TV_FILL": "TV_OPEN", "TV_CLOSED": "CLOSED"},
    "TV_OPEN": {"TP_SET": "TV_OPEN", "BE_MOVE": "TV_OPEN", "CLOSE_REQ": "CLOSING", "TV_FLAT": "CLOSED"},
    "CLOSING": {"TV_FLAT": "CLOSED"},
}
TERMINAL_STATES = {"CANCELLED", "CLOSED"}
TERMINAL_EVENTS = {"CANCEL", "TV_CLOSED", "TV_FLAT"}
# how a later stage may use an actionable event (stage 2 only records this)
USE = {"ENTRY": "ORDER_INTENT", "CANCEL": "CANCEL_PENDING_ENTRY_IF_ANY", "CLOSE_REQ": "RECOMPUTE_FROM_MT5_FILL",
       "BE_MOVE": "RECOMPUTE_BE_FROM_MT5_FILL (never apply the TradingView stop price)", "TV_CLOSED": "REVIEW_TV_EXIT",
       "TV_FLAT": "REVIEW_TV_EXIT (MT5 may still hold a position)"}
ACTIONABLE = {"ENTRY", "CANCEL", "TP_SET", "BE_MOVE", "CLOSE_REQ", "TV_CLOSED", "TV_FLAT"}
# what a later stage may take from an intent (AU-3). Nothing else of the event is to be applied.
SCOPE = {"ENTRY": "entry: side / order type / reference price / SL / TP (Current TP = planned, final TP after the MT5 fill)",
         "TP_SET": "tp only (the stop is never taken from TP_SET)",
         "BE_MOVE": "trigger only (recompute the stop from the MT5 fill; never use px / sl of this event)",
         "CLOSE_REQ": "close request (recompute the reason from the MT5 fill)", "CANCEL": "cancel the pending entry",
         "TV_CLOSED": "review only", "TV_FLAT": "review only"}
STAGE2_MT5_ACTION = "NONE (stage 2: no MT5 connection, no orders)"


def utc_iso(ms):
    try:
        return datetime.fromtimestamp(ms / 1000, timezone.utc).isoformat(timespec="milliseconds")
    except (OverflowError, OSError, ValueError, TypeError):
        return None


def safe_int(v):
    return v if isinstance(v, int) and not isinstance(v, bool) and INT64[0] <= v <= INT64[1] else None


def safe_num(v):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    try:
        f = float(v)
    except OverflowError:
        return None
    return f if math.isfinite(f) else None


def safe_text(v, n):
    return v[:n] if isinstance(v, str) else None


def load_config(path):
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    if path:
        with open(path, encoding="utf-8-sig") as f:     # -sig: Windows PowerShell 5.1 writes UTF-8 with a BOM
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
        self.db = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None, timeout=30)
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
            age_ms INTEGER, sent_skew_ms INTEGER, side TEXT, otype TEXT, px REAL, sl REAL, tp REAL, o REAL, h REAL, l REAL, c REAL,
            info TEXT, mt5_action TEXT);
        CREATE INDEX IF NOT EXISTS receipts_key ON receipts(key);
        CREATE TABLE IF NOT EXISTS events (key TEXT PRIMARY KEY, receipt_id INTEGER NOT NULL, ev TEXT, tid TEXT, wid TEXT,
            bar_close INTEGER, rank INTEGER, side TEXT, otype TEXT, px REAL, sl REAL, tp REAL, o REAL, h REAL, l REAL, c REAL,
            info TEXT, apply_status TEXT, apply_note TEXT);
        CREATE INDEX IF NOT EXISTS events_tid ON events(tid);
        CREATE INDEX IF NOT EXISTS events_wid ON events(wid);
        CREATE TABLE IF NOT EXISTS tv_trades (tid TEXT PRIMARY KEY, state TEXT, entry_seen INTEGER, terminal_seen INTEGER, side TEXT,
            otype TEXT, path TEXT, wid TEXT, ref_px REAL, entry_sl REAL, entry_tp REAL, tv_fill_px REAL, tv_exit_px REAL, sl REAL,
            tp REAL, entry_bar_close INTEGER, last_ev TEXT, last_bar_close INTEGER, pending INTEGER, conflicts INTEGER,
            updated_utc TEXT);
        CREATE TABLE IF NOT EXISTS tv_waits (wid TEXT PRIMARY KEY, state TEXT, side TEXT, p0 REAL, sl0 REAL, tp0 REAL,
            start_bar_close INTEGER, end_bar_close INTEGER, end_reason TEXT, entry_tid TEXT, updated_utc TEXT);
        CREATE TABLE IF NOT EXISTS tv_bars (bar_close INTEGER PRIMARY KEY, bar_open INTEGER, o REAL, h REAL, l REAL, c REAL,
            tv_side TEXT, tv_stop REAL, tv_tp REAL, info TEXT, event_key TEXT);
        CREATE TABLE IF NOT EXISTS intents (key TEXT PRIMARY KEY, tid TEXT, ev TEXT, eligible INTEGER NOT NULL, use TEXT,
            reason TEXT, decided_ms INTEGER, claimed_ms INTEGER, claim_note TEXT);
        CREATE TABLE IF NOT EXISTS claim_log (id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT, attempt_ms INTEGER NOT NULL,
            ok INTEGER NOT NULL, reason TEXT, decided_ms INTEGER);
        CREATE TABLE IF NOT EXISTS mt5_positions (tid TEXT PRIMARY KEY, state TEXT NOT NULL DEFAULT 'NOT_CONNECTED',
            ticket TEXT, volume REAL, open_price REAL, sl REAL, tp REAL, updated_utc TEXT);
        """)
        cols = {r[1] for r in self.db.execute("PRAGMA table_info(intents)")}     # AU-3 columns (a DB created by AU-2 is upgraded)
        for c, ty in (("bar_close", "INTEGER"), ("received_ms", "INTEGER"), ("first_decided_ms", "INTEGER"), ("scope", "TEXT"),
                      ("last_claim_ms", "INTEGER")):
            if c not in cols:
                self.db.execute(f"ALTER TABLE intents ADD COLUMN {c} {ty}")
        if "decided_ms" not in {r[1] for r in self.db.execute("PRAGMA table_info(claim_log)")}:     # AU-3 claim_log upgraded
            self.db.execute("ALTER TABLE claim_log ADD COLUMN decided_ms INTEGER")
        self.db.execute("INSERT OR IGNORE INTO meta(k, v) VALUES ('db_version', ?)", (DB_VERSION,))
        self.db.execute("UPDATE meta SET v=? WHERE k='db_version'", (DB_VERSION,))

    def one(self, sql, args=()):
        return self.db.execute(sql, args).fetchone()

    def all(self, sql, args=()):
        return self.db.execute(sql, args).fetchall()


class _BadJSON(ValueError):
    pass


def _no_constant(name):
    raise _BadJSON(f"format:nonstandard_constant:{name}")


def _pairs(pairs):
    keys = [k for k, _ in pairs]
    if len(keys) != len(set(keys)):
        raise _BadJSON("format:duplicate_field")
    return dict(pairs)


def parse_body(body):
    """strict JSON: UTF-8, no NaN / Infinity constants, no duplicate fields, finite numbers. Returns (msg, error)."""
    if isinstance(body, (bytes, bytearray)):
        try:
            text = bytes(body).decode("utf-8")
        except UnicodeDecodeError:
            return None, "format:not_utf8"
    else:
        text = str(body)
    try:
        msg = json.loads(text, parse_constant=_no_constant, object_pairs_hook=_pairs)
    except _BadJSON as e:
        return None, str(e)
    except (ValueError, RecursionError):
        return None, "format:not_json"
    return msg, None


def _tnum(tid):
    try:
        return int(tid[1:]) if len(tid) > 1 and tid[1:].isdigit() else None
    except ValueError:
        return None


def validate(msg, exp, policy, now_ms):
    """stateless checks (format, identity, values, times, per-event fields). Returns (errors, warnings, cfg_sha, metrics)."""
    errs, warns, met = [], [], {}
    if not isinstance(msg, dict):
        return ["format:not_object"], warns, None, met
    for k, t in REQUIRED.items():
        if k not in msg:
            errs.append(f"format:missing:{k}")
            continue
        v = msg[k]
        if t == "num?":
            if v is not None and (isinstance(v, bool) or not isinstance(v, (int, float))):
                errs.append(f"format:type:{k}")
            elif v is not None and safe_num(v) is None:
                errs.append(f"value:not_finite:{k}")
        elif isinstance(v, bool) or not isinstance(v, t):
            errs.append(f"format:type:{k}")
        elif t is str and len(v) > MAX_TEXT.get(k, 200):
            errs.append(f"format:too_long:{k}")
    extra = set(msg) - set(REQUIRED)
    if extra:
        errs.append("format:unknown_field:" + ",".join(sorted(extra))[:100])
    if errs:
        return errs, warns, None, met
    ev = msg["ev"]
    if ev not in EVENTS:
        return [f"format:unknown_event:{ev[:20]}"], warns, None, met
    for k in ("bar_open", "bar_close", "sent"):
        if not (TIME_MIN_MS <= msg[k] <= TIME_MAX_MS):
            errs.append(f"time:out_of_range:{k}")
    if errs:
        return errs, warns, None, met
    bo, bc = msg["bar_open"], msg["bar_close"]
    if bc - bo != BAR_MS:
        errs.append("time:not_5m_bar")
    if bo % BAR_MS:
        errs.append("time:bar_not_aligned")
    met["age_ms"] = now_ms - bc
    met["sent_skew_ms"] = now_ms - msg["sent"]
    if ev != "PROV" and msg["sent"] < bc:
        warns.append("warn:sent_before_bar_close")          # recorded only (TradingView's closing-tick timing is not verified)
    if ev == "PROV" and not (bo <= msg["sent"] <= bc):
        warns.append("warn:prov_sent_outside_bar")
    fut = policy.get("max_future_skew_sec")
    if fut is not None and (msg["sent"] - now_ms > fut * 1000 or (ev != "PROV" and bc - now_ms > fut * 1000)):
        errs.append("time:in_future")
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
    if msg["key"] != f'{msg["sid"]}|{ev}|{msg["tid"]}|{bc}':
        errs.append("format:key_mismatch")
    if msg["rank"] != RANKS[ev]:
        errs.append("format:rank_mismatch")
    tid, tn = msg["tid"], _tnum(msg["tid"])
    if not tid.startswith(EVENTS[ev]) or tn is None:
        errs.append("format:tid_form")
    else:
        if ev in ("ENTRY", "WAIT_START", "BAR") and tn != bc:
            errs.append("time:tid_not_decision_bar")
        elif ev == "PROV" and tn != bo:
            errs.append("time:tid_not_bar_open")
        elif ev not in ("ENTRY", "WAIT_START", "BAR", "PROV"):
            if tn % BAR_MS or not (TIME_MIN_MS <= tn <= TIME_MAX_MS):
                errs.append("time:tid_time_invalid")
            elif bc <= tn:
                errs.append("time:event_not_after_entry_or_prep_bar")
    side = msg["side"]
    allowed = exp.get("allowed_sides", ["SHORT"])
    if ev == "BAR":
        if side not in ("", *allowed):
            errs.append("value:side_not_allowed")
    elif side not in allowed:
        errs.append("value:side_not_allowed" if side in ("LONG", "SHORT") else "format:side")
    if msg["otype"] not in ("", "MARKET", "LIMIT") or (ev == "ENTRY" and msg["otype"] not in ("MARKET", "LIMIT")):
        errs.append("format:otype")
    for k in ("px", "sl", "tp", "o", "h", "l", "c"):
        v = msg[k]
        if v is not None and not (0 < v < PRICE_MAX):
            errs.append(f"value:price_range:{k}")
    for k in NEED[ev]:
        if msg[k] is None:
            errs.append(f"value:missing_price:{k}")
    if errs:
        return errs, warns, cfg_sha, met
    px, sl, tp = msg["px"], msg["sl"], msg["tp"]
    s = -1 if side == "SHORT" else 1
    if ev in ("ENTRY", "WAIT_START", "TP_SET") and not (s * (px - sl) > 0 and s * (tp - px) > 0):
        errs.append("value:price_geometry")
    if ev == "PROV" and not (s * (px - sl) > 0 and (tp is None or s * (tp - px) > 0)):
        errs.append("value:price_geometry")
    if ev == "BE_MOVE" and (abs(sl - px) > 1e-9 or (tp is not None and s * (tp - sl) <= 0)):
        errs.append("value:be_geometry")
    o, h, l, c = msg["o"], msg["h"], msg["l"], msg["c"]
    if None not in (o, h, l, c) and not (l <= min(o, c) and max(o, c) <= h):
        errs.append("value:ohlc_inconsistent")
    if ev == "ENTRY":
        info = dict(p.split("=", 1) for p in msg["info"].split(";") if "=" in p)
        wid = info.get("wid")
        if msg["info"].split(";")[0] not in ("SATS_PULL", "SATS_NOW", "CURRENT"):
            errs.append("value:entry_path")
        if msg["info"].startswith("SATS_PULL") and (not wid or not wid.startswith("W") or _tnum(wid) is None or _tnum(wid) >= bc):
            errs.append("value:entry_wid")
    return errs, warns, cfg_sha, met


class Receiver:
    def __init__(self, cfg, log=None, clock=None):
        self.cfg = cfg
        self.store = Store(cfg["data_dir"])
        self.log = log or logging.getLogger("xau_receiver")
        self.clock = clock or (lambda: int(time.time() * 1000))     # injectable for tests; production = wall clock
        self.reevaluate_all_if_needed()

    def _meta(self, k):
        r = self.store.one("SELECT v FROM meta WHERE k=?", (k,))
        return r["v"] if r else None

    def reevaluate_all_if_needed(self):
        """AU-4: when the stored facts were evaluated with other rules (an AU-2 / AU-3 database, or an interrupted run), replay
        every stored fact with the current rules: waits, trades, then every intent (unclaimed ones may be revoked / re-decided;
        claimed ones keep claimed_ms and only get a note). Receipts, facts and claim history are kept. A 'reeval_pending' flag is
        committed first and cleared in the same transaction as the result, so claim() refuses everything until it is done."""
        if self._meta("rules_version") == RULES_VERSION and self._meta("reeval_pending") is None:
            return
        with self.store.lock:
            db = self.store.db
            db.execute("INSERT OR REPLACE INTO meta(k, v) VALUES ('reeval_pending', ?)", (str(self.clock()),))
            db.execute("BEGIN IMMEDIATE")
            try:
                now = self.clock()
                db.execute("UPDATE intents SET bar_close=(SELECT e.bar_close FROM events e WHERE e.key=intents.key) WHERE bar_close IS NULL")
                db.execute("UPDATE intents SET received_ms=(SELECT r.received_ms FROM events e JOIN receipts r ON r.id=e.receipt_id"
                           " WHERE e.key=intents.key) WHERE received_ms IS NULL")
                for ev_, sc in SCOPE.items():
                    db.execute("UPDATE intents SET scope=? WHERE ev=? AND scope IS NULL", (sc, ev_))
                for r in db.execute("SELECT DISTINCT wid FROM events WHERE wid IS NOT NULL").fetchall():
                    self._derive_wait(r["wid"])
                tids = [r["tid"] for r in db.execute("SELECT tid, MIN(bar_close) b FROM events WHERE tid LIKE 'T%' GROUP BY tid ORDER BY b")]
                for tid in tids:
                    self._derive_trade(tid)
                for tid in tids:
                    self._decide_intents(tid, now)
                db.execute("INSERT OR REPLACE INTO meta(k, v) VALUES ('rules_version', ?)", (RULES_VERSION,))
                db.execute("INSERT OR REPLACE INTO meta(k, v) VALUES ('reevaluated_ms', ?)", (str(now),))
                db.execute("DELETE FROM meta WHERE k='reeval_pending'")
                db.execute("COMMIT")
            except Exception:
                db.execute("ROLLBACK")
                raise
        self.log.info("re-evaluated %d trades with rules %s", len(tids), RULES_VERSION)

    # -- the whole pipeline for one body; always records a receipt, never raises -------------------------------------
    def process(self, body, source="local", now_ms=None):
        now_ms = self.clock() if now_ms is None else now_ms
        raw = body.decode("utf-8", "replace") if isinstance(body, (bytes, bytearray)) else str(body)
        try:
            msg, perr = parse_body(body)
            errs, warns, cfg_sha, met = ([perr], [], None, {}) if perr else validate(msg, self.cfg["expected"], self.cfg["policy"], now_ms)
            with self.store.lock:
                db = self.store.db
                db.execute("BEGIN IMMEDIATE")
                try:
                    status, reasons = self._decide(msg, errs, warns, met)
                    rid = self._record(msg if isinstance(msg, dict) else {}, raw, source, status, reasons, cfg_sha, met, now_ms)
                    if status == "ACCEPTED":
                        self._store_event(msg, rid)
                        self._reevaluate(msg, now_ms)
                    db.execute("COMMIT")
                except Exception:
                    db.execute("ROLLBACK")
                    raise
            res = {"id": rid, "status": status, "reasons": reasons}
        except Exception as e:     # never crash: record the failure itself
            res = self._record_error(raw, source, now_ms, e)
        self.log.info("receipt %s status=%s reasons=%s", res.get("id"), res["status"], ",".join(res["reasons"])[:300] or "-")
        return res

    def _record_error(self, raw, source, now_ms, e):
        reason = f"internal:{type(e).__name__}"
        try:
            with self.store.lock:
                cur = self.store.db.execute(
                    "INSERT INTO receipts(received_ms, received_utc, source, status, reasons, raw, mt5_action) VALUES (?,?,?,?,?,?,?)",
                    (now_ms, utc_iso(now_ms) or "", safe_text(source, 100), "ERROR", json.dumps([reason]),
                     raw[:self.cfg["max_body_bytes"]], STAGE2_MT5_ACTION))
            return {"id": cur.lastrowid, "status": "ERROR", "reasons": [reason]}
        except Exception:
            self.log.exception("could not record an internal error")
            return {"id": None, "status": "ERROR", "reasons": [reason, "internal:not_recorded"]}

    def _decide(self, msg, errs, warns, met):
        if errs:
            return "REJECTED", errs + warns
        if self.store.one("SELECT 1 FROM events WHERE key = ?", (msg["key"],)):
            return "DUPLICATE", ["dup:same_key_already_accepted"] + warns
        return "ACCEPTED", list(warns)

    def _record(self, m, raw, source, status, reasons, cfg_sha, met, now_ms):
        txt = lambda k: safe_text(m.get(k), MAX_TEXT.get(k, 200))
        cur = self.store.db.execute(
            "INSERT INTO receipts(received_ms, received_utc, source, status, reasons, raw, key, ev, tid, sid, cfg_sha256, rank, bar_open,"
            " bar_close, sent, age_ms, sent_skew_ms, side, otype, px, sl, tp, o, h, l, c, info, mt5_action)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (now_ms, utc_iso(now_ms) or "", safe_text(source, 100), status, json.dumps(reasons)[:2000], raw[:self.cfg["max_body_bytes"]],
             txt("key"), txt("ev"), txt("tid"), txt("sid"), cfg_sha, safe_int(m.get("rank")), safe_int(m.get("bar_open")),
             safe_int(m.get("bar_close")), safe_int(m.get("sent")), safe_int(met.get("age_ms")), safe_int(met.get("sent_skew_ms")),
             txt("side"), txt("otype"), *(safe_num(m.get(k)) for k in ("px", "sl", "tp", "o", "h", "l", "c")), txt("info"),
             STAGE2_MT5_ACTION))
        return cur.lastrowid

    def _store_event(self, m, rid):
        wid = m["tid"] if m["ev"] in ("WAIT_START", "WAIT_END") else dict(
            p.split("=", 1) for p in m["info"].split(";") if "=" in p).get("wid") if m["ev"] == "ENTRY" else None
        st = {"PROV": "INFO", "BAR": "INFO", "WAIT_START": "FACT", "WAIT_END": "FACT"}.get(m["ev"], "NEW")
        self.store.db.execute(
            "INSERT INTO events(key, receipt_id, ev, tid, wid, bar_close, rank, side, otype, px, sl, tp, o, h, l, c, info, apply_status)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (m["key"], rid, m["ev"], m["tid"], wid, m["bar_close"], m["rank"], m["side"], m["otype"], m["px"], m["sl"], m["tp"],
             m["o"], m["h"], m["l"], m["c"], m["info"], st))
        if m["ev"] == "BAR":
            info = dict(p.split("=", 1) for p in m["info"].split(";") if "=" in p)
            self.store.db.execute("INSERT OR IGNORE INTO tv_bars(bar_close, bar_open, o, h, l, c, tv_side, tv_stop, tv_tp, info, event_key)"
                                  " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                                  (m["bar_close"], m["bar_open"], m["o"], m["h"], m["l"], m["c"], m["side"], m["sl"], m["tp"],
                                   json.dumps(info), m["key"]))

    # -- layer 2 / 3: derive states and eligibility from the stored facts ---------------------------------------------
    def _reevaluate(self, m, now_ms):
        db = self.store.db
        tids, wids = set(), set()
        if EVENTS[m["ev"]] == "T":
            tids.add(m["tid"])
        if m["ev"] in ("WAIT_START", "WAIT_END"):
            wids.add(m["tid"])
        if m["ev"] == "ENTRY":
            w = db.execute("SELECT wid FROM events WHERE key=?", (m["key"],)).fetchone()["wid"]
            if w:
                wids.add(w)
        for w in wids:
            self._derive_wait(w)
            tids.update(r["tid"] for r in db.execute("SELECT tid FROM events WHERE ev='ENTRY' AND wid=?", (w,)))
        for t in tids:
            self._derive_trade(t)
        # ENTRY eligibility depends on the other trades: re-check this tid's and every unclaimed eligible ENTRY
        tids.update(r["tid"] for r in db.execute("SELECT tid FROM intents WHERE ev='ENTRY' AND eligible=1 AND claimed_ms IS NULL"))
        for t in tids:
            self._decide_intents(t, now_ms)

    def _derive_wait(self, wid):
        db = self.store.db
        evs = db.execute("SELECT * FROM events WHERE wid=? ORDER BY bar_close, rank", (wid,)).fetchall()
        start = next((e for e in evs if e["ev"] == "WAIT_START"), None)
        end = next((e for e in evs if e["ev"] == "WAIT_END"), None)
        entry = next((e for e in evs if e["ev"] == "ENTRY"), None)
        state = ("ENDED" if start else "ENDED_START_UNSEEN") if end else ("CONSUMED" if entry else "OPEN")
        if not start and not end and entry:
            state = "CONSUMED_START_UNSEEN"
        db.execute("INSERT INTO tv_waits(wid, state, side, p0, sl0, tp0, start_bar_close, end_bar_close, end_reason, entry_tid, updated_utc)"
                   " VALUES (?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(wid) DO UPDATE SET state=excluded.state, side=excluded.side, p0=excluded.p0,"
                   " sl0=excluded.sl0, tp0=excluded.tp0, start_bar_close=excluded.start_bar_close, end_bar_close=excluded.end_bar_close,"
                   " end_reason=excluded.end_reason, entry_tid=excluded.entry_tid, updated_utc=excluded.updated_utc",
                   (wid, state, (start or end or entry)["side"], start["px"] if start else None, start["sl"] if start else None,
                    start["tp"] if start else None, start["bar_close"] if start else None, end["bar_close"] if end else None,
                    end["info"] if end else None, entry["tid"] if entry else None, utc_iso(int(time.time() * 1000))))

    def _derive_trade(self, tid):
        """replay every stored event of the trade in (bar_close, rank) order; store each event's apply status and the state."""
        db = self.store.db
        evs = db.execute("SELECT * FROM events WHERE tid=? ORDER BY bar_close, rank", (tid,)).fetchall()
        entry = next((e for e in evs if e["ev"] == "ENTRY"), None)
        terminal_seen = any(e["ev"] in TERMINAL_EVENTS for e in evs)
        st = {}
        if entry is None:
            for e in evs:
                st[e["key"]] = ("ORPHAN", "entry_not_seen")
            state, side, d = ("TERMINAL_ENTRY_UNSEEN" if terminal_seen else "ENTRY_UNSEEN"), evs[0]["side"], {}
        else:
            state, side = "INTENT", entry["side"]
            d = {"ref_px": entry["px"], "entry_sl": entry["sl"], "entry_tp": entry["tp"], "sl": entry["sl"], "tp": entry["tp"],
                 "fill": None, "exit": None, "last": entry}
            for e in evs:
                if e["key"] == entry["key"]:
                    st[e["key"]] = ("APPLIED", "")
                    continue
                if state in TERMINAL_STATES:
                    st[e["key"]] = ("AFTER_TERMINAL", f"trade_{state.lower()}")
                    continue
                if e["side"] != side:
                    st[e["key"]] = ("CONFLICT", "side_mismatch")
                    continue
                nxt = TRANSITIONS.get(state, {}).get(e["ev"])
                if nxt is None:
                    pending = state == "INTENT" and e["ev"] in ("TP_SET", "BE_MOVE", "CLOSE_REQ", "TV_FLAT")
                    st[e["key"]] = ("PENDING", "waiting_for_tv_fill") if pending else ("CONFLICT", f"invalid_transition:{state}->{e['ev']}")
                    continue
                s = -1 if side == "SHORT" else 1
                if e["ev"] in ("TP_SET", "BE_MOVE", "CLOSE_REQ") and d["fill"] is not None and abs(e["px"] - d["fill"]) > 1e-6:
                    st[e["key"]] = ("CONFLICT", "tv_fill_mismatch")
                    continue
                # AU-3: management integrity (the Strategy sets the TP once, on the fill bar, with the initial stop; the stop only
                # ever moves in the trade's favour). A TP_SET that would put the stop back after a breakeven is a CONFLICT.
                if e["ev"] == "TP_SET":
                    if d.get("tp_set"):
                        st[e["key"]] = ("CONFLICT", "duplicate_tp_set")
                        continue
                    if e["bar_close"] != d.get("fill_bar"):
                        st[e["key"]] = ("CONFLICT", "tp_set_not_on_fill_bar")
                        continue
                    if abs(e["sl"] - d["entry_sl"]) > 1e-6:
                        st[e["key"]] = ("CONFLICT", "tp_set_stop_not_initial")
                        continue
                if e["ev"] in ("TP_SET", "BE_MOVE") and d["sl"] is not None and s * (e["sl"] - d["sl"]) < 0:
                    st[e["key"]] = ("CONFLICT", "stop_would_loosen")
                    continue
                if e["ev"] == "BE_MOVE" and d["sl"] is not None and s * (e["sl"] - d["sl"]) <= 0:
                    st[e["key"]] = ("CONFLICT", "stop_not_improving")
                    continue
                if e["ev"] == "TV_FILL":
                    d["fill"], d["fill_bar"] = e["px"], e["bar_close"]
                elif e["ev"] == "TP_SET":          # AU-4: the TP only (its stop equals the initial stop, checked above)
                    d["tp_set"] = e["key"]
                    d["tp"] = e["tp"]
                elif e["ev"] == "BE_MOVE":         # the stop only (never loosening, checked above); the TP stays
                    d["sl"] = e["sl"]
                elif e["ev"] in ("TV_CLOSED", "TV_FLAT"):
                    d["exit"] = e["px"]
                state, d["last"] = nxt, e
                st[e["key"]] = ("APPLIED", "")
            # a pending event whose predecessor never came stays PENDING; one placed after a terminal never reopens the trade
        for k, (a, note) in st.items():
            db.execute("UPDATE events SET apply_status=?, apply_note=? WHERE key=?", (a, note, k))
        last = d.get("last") if entry else evs[-1]
        db.execute(
            "INSERT INTO tv_trades(tid, state, entry_seen, terminal_seen, side, otype, path, wid, ref_px, entry_sl, entry_tp, tv_fill_px,"
            " tv_exit_px, sl, tp, entry_bar_close, last_ev, last_bar_close, pending, conflicts, updated_utc)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(tid) DO UPDATE SET state=excluded.state,"
            " entry_seen=excluded.entry_seen, terminal_seen=excluded.terminal_seen, side=excluded.side, otype=excluded.otype,"
            " path=excluded.path, wid=excluded.wid, ref_px=excluded.ref_px, entry_sl=excluded.entry_sl, entry_tp=excluded.entry_tp,"
            " tv_fill_px=excluded.tv_fill_px, tv_exit_px=excluded.tv_exit_px, sl=excluded.sl, tp=excluded.tp,"
            " entry_bar_close=excluded.entry_bar_close, last_ev=excluded.last_ev, last_bar_close=excluded.last_bar_close,"
            " pending=excluded.pending, conflicts=excluded.conflicts, updated_utc=excluded.updated_utc",
            (tid, state, int(entry is not None), int(terminal_seen), side, entry["otype"] if entry else None,
             entry["info"].split(";")[0] if entry else None, entry["wid"] if entry else None, d.get("ref_px"), d.get("entry_sl"),
             d.get("entry_tp"), d.get("fill"), d.get("exit"), d.get("sl"), d.get("tp"), entry["bar_close"] if entry else None,
             last["ev"], last["bar_close"], sum(1 for a, _ in st.values() if a == "PENDING"),
             sum(1 for a, _ in st.values() if a == "CONFLICT"), utc_iso(int(time.time() * 1000))))

    def _entry_block(self, tid, entry, first=True):
        """why this ENTRY may not become a new execution candidate (None = no reason). The arrival-time rules (a newer trade
        already known, another candidate position open, the deadline) apply only at the first decision; later re-evaluations
        can only revoke (termination / wait end learnt later), never re-grant (a skipped signal stays skipped)."""
        db = self.store.db
        t = db.execute("SELECT * FROM tv_trades WHERE tid=?", (tid,)).fetchone()
        if t["terminal_seen"]:
            return "late:trade_already_terminated"
        if entry["wid"]:
            w = db.execute("SELECT * FROM tv_waits WHERE wid=?", (entry["wid"],)).fetchone()
            if w and w["end_bar_close"] is not None and w["state"].startswith("ENDED"):
                return f"late:wait_already_ended:{entry['wid']}"
        if not first:
            return None
        newer = db.execute("SELECT tid FROM tv_trades WHERE entry_bar_close > ? AND tid != ? LIMIT 1", (entry["bar_close"], tid)).fetchone()
        if newer:
            return f"late:older_than_newer_trade:{newer['tid']}"
        # an earlier trade still open on the TradingView side whose ENTRY is (or was claimed as) an execution candidate. An ENTRY that
        # was itself refused (late / contradictory) does not block the next one
        act = db.execute("SELECT t.tid FROM tv_trades t JOIN intents i ON i.tid=t.tid AND i.ev='ENTRY' WHERE t.tid != ? AND t.entry_seen=1"
                         " AND t.terminal_seen=0 AND t.entry_bar_close < ? AND (i.eligible=1 OR i.claimed_ms IS NOT NULL) LIMIT 1",
                         (tid, entry["bar_close"])).fetchone()
        if act:
            return f"state:virtual_position_active:{act['tid']}"
        mx = self.cfg["policy"].get("max_age_sec")
        if mx is not None:
            r = db.execute("SELECT r.received_ms FROM receipts r JOIN events e ON e.receipt_id=r.id WHERE e.key=?", (entry["key"],)).fetchone()
            if r and r["received_ms"] - entry["bar_close"] > mx * 1000:
                return "late:older_than_max_age"
        return None

    def _decide_intents(self, tid, now_ms):
        db = self.store.db
        evs = db.execute("SELECT * FROM events WHERE tid=? ORDER BY bar_close, rank", (tid,)).fetchall()
        entry = next((e for e in evs if e["ev"] == "ENTRY"), None)
        entry_ok = None
        if entry is not None:
            pe = db.execute("SELECT * FROM intents WHERE key=?", (entry["key"],)).fetchone()
            if pe is None:
                blk = self._entry_block(tid, entry, first=True)
                e_ok, e_why = blk is None, blk or "ok"
            elif pe["claimed_ms"] is not None:
                blk = self._entry_block(tid, entry, first=False)
                e_ok, e_why = True, pe["reason"]
                if blk:
                    db.execute("UPDATE intents SET claim_note=? WHERE key=?", (f"post_claim:{blk}", entry["key"]))
            elif not pe["eligible"]:
                e_ok, e_why = False, pe["reason"]          # once refused, an ENTRY never becomes a candidate again
            else:
                blk = self._entry_block(tid, entry, first=False)
                mx = self.cfg["policy"].get("max_age_sec")
                if blk is None and mx is not None and now_ms - entry["bar_close"] > mx * 1000:
                    blk = "expired"                          # deadline passed while unclaimed (also re-checked at claim())
                e_ok, e_why = blk is None, ("revoked:" + blk) if blk else pe["reason"]
            entry_ok = e_ok
        order = {e["key"]: i for i, e in enumerate(evs)}
        for e in evs:
            if e["ev"] not in ACTIONABLE:
                continue
            if e["ev"] == "ENTRY":
                ok, why = e_ok, e_why
                use = USE["ENTRY"]
            else:
                use = USE.get(e["ev"]) or ("SET_TP_FIXED_PRICE (TP0)" if e["info"] == "sats_tp0" else "RECOMPUTE_TP_FROM_MT5_FILL")
                if entry is None:
                    ok, why = False, "entry_not_seen"
                elif not entry_ok:
                    ok, why = False, "entry_not_eligible"
                elif e["apply_status"] != "APPLIED":
                    ok, why = False, f"{e['apply_status'].lower()}:{e['apply_note']}"
                else:
                    later = evs[order[e["key"]] + 1:]
                    early = [x for x in later if x["receipt_id"] < e["receipt_id"]]
                    ended = [x for x in later if x["ev"] in TERMINAL_EVENTS and x["apply_status"] == "APPLIED"]
                    if early:      # a newer fact of this trade was already known when this one arrived: never a candidate
                        ok, why = False, f"stale:arrived_after_newer_event:{early[0]['ev']}"
                    elif ended and e["ev"] not in TERMINAL_EVENTS:
                        ok, why = False, f"superseded:trade_ended_by:{ended[0]['ev']}"
                    else:
                        ok, why = True, "ok"
            prev = db.execute("SELECT * FROM intents WHERE key=?", (e["key"],)).fetchone()
            if prev is None:
                rec = db.execute("SELECT received_ms FROM receipts WHERE id=?", (e["receipt_id"],)).fetchone()
                db.execute("INSERT INTO intents(key, tid, ev, eligible, use, reason, decided_ms, bar_close, received_ms, first_decided_ms,"
                           " scope) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                           (e["key"], tid, e["ev"], int(ok), use, why, now_ms, e["bar_close"], rec["received_ms"] if rec else None, now_ms,
                            SCOPE.get(e["ev"])))
            elif prev["claimed_ms"] is None:
                if (prev["eligible"], prev["reason"]) != (int(ok), why):
                    db.execute("UPDATE intents SET eligible=?, reason=?, decided_ms=? WHERE key=?", (int(ok), why, now_ms, e["key"]))
            elif not ok:
                db.execute("UPDATE intents SET claim_note=? WHERE key=?", (f"post_claim:{why}", e["key"]))

    def claim(self, key):
        """for a LATER stage: atomically claim one eligible, unclaimed intent (True at most once per key). Stage 2 never calls it.
        attempt_ms is read when called; the decision time decided_ms is read again AFTER the in-process lock and the SQLite write
        transaction (BEGIN IMMEDIATE, also across processes) are held, so waiting for either never lets an expired candidate
        through. With policy.max_age_sec an ENTRY older than the deadline at decided_ms is revoked ('revoked:expired_at_claim')
        and never claimable again (also after a restart: the DB + config decide). Refused while a re-evaluation is pending.
        Every attempt is written to claim_log (attempt time, decision time, result, reason)."""
        attempt_ms = self.clock()
        with self.store.lock:
            db = self.store.db
            db.execute("BEGIN IMMEDIATE")
            try:
                now_ms = self.clock()                      # the decision time: after both waits
                row = db.execute("SELECT i.*, e.bar_close AS ev_bar_close FROM intents i LEFT JOIN events e ON e.key=i.key WHERE i.key=?",
                                 (key,)).fetchone()
                pending = db.execute("SELECT v FROM meta WHERE k='reeval_pending'").fetchone()
                rules = db.execute("SELECT v FROM meta WHERE k='rules_version'").fetchone()
                reason = None
                if pending is not None or rules is None or rules["v"] != RULES_VERSION:
                    reason = "reevaluation_pending"
                elif row is None:
                    reason = "not_found"
                elif row["claimed_ms"] is not None:
                    reason = "already_claimed"
                elif not row["eligible"]:
                    reason = f"not_eligible:{row['reason']}"
                else:
                    mx = self.cfg["policy"].get("max_age_sec")
                    bc = row["ev_bar_close"] if row["ev_bar_close"] is not None else row["bar_close"]
                    if mx is not None and row["ev"] == "ENTRY" and (bc is None or now_ms - bc > mx * 1000):
                        reason = "expired_at_claim"
                        db.execute("UPDATE intents SET eligible=0, reason='revoked:expired_at_claim', decided_ms=? WHERE key=?", (now_ms, key))
                ok = False
                if reason is None:
                    ok = db.execute("UPDATE intents SET claimed_ms=?, last_claim_ms=? WHERE key=? AND eligible=1 AND claimed_ms IS NULL",
                                    (now_ms, now_ms, key)).rowcount == 1
                    reason = "claimed" if ok else "race_lost"
                elif row is not None:
                    db.execute("UPDATE intents SET last_claim_ms=? WHERE key=?", (now_ms, key))
                db.execute("INSERT INTO claim_log(key, attempt_ms, decided_ms, ok, reason) VALUES (?,?,?,?,?)",
                           (safe_text(key, 200), attempt_ms, now_ms, int(ok), reason))
                db.execute("COMMIT")
            except Exception:
                db.execute("ROLLBACK")
                raise
            return ok


# ---- HTTP -----------------------------------------------------------------------------------------------------------
def make_handler(rcv, token):
    class Handler(BaseHTTPRequestHandler):
        server_version = "xau-receiver/2"

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
            try:
                parts = self.path.split("?")[0].strip("/").split("/")
                if len(parts) != 2 or parts[0] != "webhook" or not token or not hmac.compare_digest(parts[1].encode(), token.encode()):
                    rcv.log.warning("unauthorized POST from %s", self.client_address[0])
                    return self._reply(404, {"error": "not_found"})
                try:
                    n = int(self.headers.get("Content-Length") or 0)
                except ValueError:
                    n = -1
                if n <= 0 or n > rcv.cfg["max_body_bytes"]:
                    rcv.log.warning("rejected body size %s from %s", n, self.client_address[0])
                    return self._reply(413, {"error": "size"})
                res = rcv.process(self.rfile.read(n), source=f"http:{self.client_address[0]}")
                return self._reply(200, res)
            except Exception:
                rcv.log.exception("request handling failed")
                return self._reply(500, {"error": "internal"})
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


def write_pid(cfg, srv):
    """PID file with what stop_receiver.ps1 checks before stopping (owner check: PID + start time + command line markers)."""
    info = {"pid": os.getpid(), "started_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "script": os.path.abspath(__file__), "data_dir": os.path.abspath(cfg["data_dir"]), "port": srv.server_address[1],
            "marker": "xau_receiver.py serve"}
    with open(os.path.join(cfg["data_dir"], "receiver.pid"), "w", encoding="utf-8") as f:
        json.dump(info, f)


def serve(cfg, token=None, ready=None):
    rcv = Receiver(cfg, setup_log(cfg))
    token = token if token is not None else os.environ.get(cfg["token_env"], "")
    if not token:
        rcv.log.error("environment variable %s is not set: refusing to start (no token, no receiver)", cfg["token_env"])
        return 2
    srv = ThreadingHTTPServer((cfg["host"], int(cfg["port"])), make_handler(rcv, token))
    write_pid(cfg, srv)
    rcv.log.info("listening on %s:%s (POST /webhook/<token>, GET /health); stage 2: no orders", cfg["host"], srv.server_address[1])
    if ready is not None:
        ready(srv)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
        try:
            os.remove(os.path.join(cfg["data_dir"], "receiver.pid"))
        except OSError:
            pass
        rcv.log.info("stopped")
    return 0


def read_samples(path):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    s = text.strip()
    if s.startswith("["):
        try:
            return [json.dumps(x, ensure_ascii=False) for x in json.loads(s)]
        except ValueError:
            pass
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
                print(json.dumps(rcv.process(body, source=f"file:{os.path.basename(p)}"), ensure_ascii=False))
        return 0
    st = Store(cfg["data_dir"])
    if a.cmd == "show":
        for r in reversed(st.all("SELECT * FROM receipts ORDER BY id DESC LIMIT ?", (a.last,))):
            print(f'{r["id"]:>6} {r["received_utc"]} {r["status"]:<9} {str(r["ev"]):<10} {str(r["tid"]):<16} '
                  f'bar_close={r["bar_close"]} px={r["px"]} sl={r["sl"]} tp={r["tp"]} reasons={r["reasons"]}')
        return 0
    print("TradingView virtual trades (the Strategy's own state, not MT5):")
    for r in st.all("SELECT * FROM tv_trades ORDER BY COALESCE(entry_bar_close, last_bar_close) DESC LIMIT 20"):
        print(f'  {r["tid"]} {r["state"]:<22} ref={r["ref_px"]} tv_fill={r["tv_fill_px"]} sl={r["sl"]} tp={r["tp"]} '
              f'pending={r["pending"]} conflicts={r["conflicts"]} terminal_seen={r["terminal_seen"]}')
    print("TradingView SATS waits:")
    for r in st.all("SELECT * FROM tv_waits ORDER BY COALESCE(start_bar_close, end_bar_close) DESC LIMIT 20"):
        print(f'  {r["wid"]} {r["state"]:<22} p0={r["p0"]} sl0={r["sl0"]} tp0={r["tp0"]} end={r["end_reason"]}')
    print("Intents (later-stage eligibility; stage 2 never claims):")
    for r in st.all("SELECT * FROM intents ORDER BY decided_ms DESC LIMIT 20"):
        print(f'  {r["ev"]:<10} {r["tid"]} eligible={r["eligible"]} use={r["use"]} reason={r["reason"]} claimed={r["claimed_ms"]}')
    n = st.one("SELECT COUNT(*) AS n FROM mt5_positions")["n"]
    print(f"MT5 actual positions: NOT_CONNECTED (stage 2; {n} rows, never written)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
