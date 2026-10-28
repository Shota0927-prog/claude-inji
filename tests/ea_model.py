"""Python reference model of automation/xau_short/ea/XauShortDemoEA.mq5 (stage 3, ST3-2) + a fake MT5 terminal / broker.

This is NOT the EA: it is a function-by-function port of its decisions (CheckCmd, CheckDeadline, PrepareOrder, AskBridge, SendCheck,
ProcessEntry, SelectOwn, Quarantine, ClosePosition, ModifyOwn, CheckProtection, ManageOwn, FillBarLow, TryBreakeven, DetectUnknown,
CheckResolveUnknown, Reconcile, CheckResume, PollCommands, OnInit / OnTimer) so that the rules can be exercised locally against the
same file protocol as the bridge (cmd / ask / ans / rpt / done / journal_*.txt / hb_*.txt). eam_sim.py checks that the MQL5 source
keeps the same constants, approvals, journal states, refusal reasons and gates (static), so a drift between the two is visible.
Passing here proves the RULES, not the MQL5 code: the MQL5 compile and the MT5 demo run are separate evidence.
"""
import hashlib
import math
import os
import re
import struct

RISK_FRACTION = 0.03
MAX_AGE_SEC = 60
MAX_DEV_FRAC = 0.20
MAX_SPREAD = 0.50
BE_DIST = 15.0
BAR_SEC = 300
CMD_VERSION = "2"
APPROVALS = ("be_price_source", "fillbar_method", "tp_timing", "tp_beyond", "retry_interval", "close_deviation", "monitoring")
ASK_WAIT_MS = 5000
BRIDGE_HB_MAX_MS = 5000
EMERGENCY_RETRY_SEC = 5
CLOSE_DEVIATION_POINTS = 1000
CLOSE_NOT_ALLOWED, CLOSE_FULL, CLOSE_PARTIAL, CLOSE_FAILED, CLOSE_UNKNOWN = 0, 1, 2, 3, 4

DONE, DONE_PARTIAL, PLACED, ERROR, TIMEOUT, CONNECTION = 10009, 10010, 10008, 10011, 10012, 10031
DEFINITE_REJECT = {   # TRADE_RETCODE_* listed in IsDefiniteReject()
    "REQUOTE": 10004, "REJECT": 10006, "CANCEL": 10007, "INVALID": 10013, "INVALID_VOLUME": 10014, "INVALID_PRICE": 10015,
    "INVALID_STOPS": 10016, "TRADE_DISABLED": 10017, "MARKET_CLOSED": 10018, "NO_MONEY": 10019, "PRICE_CHANGED": 10020,
    "PRICE_OFF": 10021, "INVALID_EXPIRATION": 10022, "TOO_MANY_REQUESTS": 10024, "SERVER_DISABLES_AT": 10026,
    "CLIENT_DISABLES_AT": 10027, "INVALID_FILL": 10030, "LIMIT_ORDERS": 10033, "LIMIT_VOLUME": 10034, "LIMIT_POSITIONS": 10040,
    "SHORT_ONLY": 10042, "LONG_ONLY": 10043, "FIFO_CLOSE": 10045, "HEDGE_PROHIBITED": 10046}

_TICK = [0]


def _tick():
    """GetTickCount64(): milliseconds since the PC started (monotonic, also between two EA instances)."""
    _TICK[0] += 1
    return _TICK[0]


_HELD_LOCKS = set()     # FileOpen(ea.lock, FILE_WRITE) without FILE_SHARE_*: exclusive while the handle is open


def sha16(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


def kv_lines(text):
    return [l.rstrip("\r") for l in text.split("\n")]


def kv_get(lines, k):
    for l in lines:
        if l.startswith(k + "="):
            return l[len(k) + 1:]
    return ""


def to_int(s):
    try:
        return int(float(s))
    except (TypeError, ValueError):
        return 0


def to_float(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return 0.0


def dbl_bits(x):
    """ST3-6: the exact IEEE-754 bit pattern of a price as a decimal integer (MQL5: union of double / long)."""
    return str(struct.unpack("<q", struct.pack("<d", float(x)))[0])


PX_EXACT, PX_LEGACY, PX_DAMAGED = "exact", "legacy", "damaged"


def px_read(kv, bits_key, dec_key):
    """ST3-6 / ST3-7: [value, state] of a journaled price.
      exact   : the bit field is present, finite, positive and rounds to the 5-decimal field next to it -> the exact value held.
      legacy  : no bit field (a record written before ST3-6) -> only the 5-decimal value; the full-precision price CANNOT be
                recovered from it.
      damaged : a bit field is present but unusable (not a number / not finite / not positive / does not round to its 5-decimal
                field) -> not trusted at all (not treated as a legacy record): the caller stops new entries and does not reuse it."""
    dec = to_float(kv_get(kv, dec_key))
    b = kv_get(kv, bits_key)
    if b == "":
        return dec, PX_LEGACY
    try:
        x = struct.unpack("<d", struct.pack("<q", int(b)))[0]
    except (TypeError, ValueError, struct.error, OverflowError):
        return dec, PX_DAMAGED
    if math.isfinite(x) and x > 0 and f"{x:.5f}" == f"{dec:.5f}":
        return x, PX_EXACT
    return dec, PX_DAMAGED


def basis_match(basis, live):
    """the breakeven basis still describes the live average (both exact values): the existing tolerance 1e-6. ST3-7: there is no
    comparison at 5 decimals any more — a basis that is not exact is never reused (see EA.reconcile)."""
    return abs(basis - live) <= 1e-6


class FakeTerminal:
    """the parts of the MT5 terminal / XS demo server the EA reads or writes; every trade write is logged in `writes`.
    Positions are keyed by their current TICKET and carry a separate IDENTIFIER (POSITION_IDENTIFIER = DEAL_POSITION_ID)."""

    def __init__(self, gmt_ms, server_offset_sec=7200):
        self.gmt_ms = gmt_ms
        self.server_offset = server_offset_sec
        self.account = dict(trade_mode="DEMO", login=1234567, server="XSFintech-DEMO", currency="JPY", margin_mode="HEDGING",
                            balance=1_000_000.0, margin_free=1_000_000.0, trade_allowed=True, trade_expert=True)
        self.terminal_trade_allowed = True
        self.sym = dict(name="XAUUSDs", tick=0.01, point=0.01, digits=2, vmin=0.01, vmax=100.0, vstep=0.01, vlim=0.0, contract=100.0,
                        stops=0, trade_mode="FULL", session_open=True, selectable=True)
        self.usdjpy = 150.0
        self.leverage = 100.0
        self.bid, self.ask = 2600.0, 2600.3
        self.positions = {}          # ticket -> dict (identifier, symbol, magic, comment, type, volume, price_open, sl, tp, time, time_msc)
        self.orders = {}             # pending orders (manual / other EA): ticket -> dict(symbol, comment)
        self.history_orders = []     # dict(ticket, symbol, magic, comment, time_setup_msc)
        self.deals = {}              # deal ticket -> dict
        self.rates = []              # M5 bars (server time open, low)
        self.ticks = []              # tick history (server time ms, bid)
        self.ticks_unavailable = False
        self.writes = []             # every trade API write: (kind, request)
        self.send_mode = "fill"      # fill | partial | reject:<code> | timeout | fill_lost_reply | fill_no_sl | placed
        self.ticket_offset = 0       # >0: the live position ticket differs from its identifier by this amount
        self.modify_mode = "ok"      # ok | reject
        self.close_mode = "ok"       # ok | reject | partial | timeout_no_change
        self.check_ok = True
        self.calc_profit_ok = True
        self.calc_margin_ok = True
        self.next_ticket = 5000

    # time
    def time_gmt(self):
        return self.gmt_ms // 1000

    def time_server(self):
        return self.gmt_ms // 1000 + self.server_offset

    def time_server_ms(self):
        return self.gmt_ms + self.server_offset * 1000

    def advance(self, ms):
        self.gmt_ms += ms

    # calculations (OrderCalcProfit / OrderCalcMargin, JPY account)
    def calc_profit_sell(self, vol, open_, close):
        if not self.calc_profit_ok:
            return None
        return (open_ - close) * vol * self.sym["contract"] * self.usdjpy

    def calc_margin(self, vol, price):
        if not self.calc_margin_ok:
            return None
        return price * vol * self.sym["contract"] * self.usdjpy / self.leverage

    def _ticket(self):
        self.next_ticket += 1
        return self.next_ticket

    def copy_ticks_range(self, frm, to):
        if self.ticks_unavailable:
            return None
        return [(t, b) for t, b in sorted(self.ticks) if frm <= t <= to]

    def by_identifier(self, ident):
        for tk, p in self.positions.items():
            if p["identifier"] == ident:
                return tk, p
        return 0, None

    # trade API
    def order_send(self, req):
        self.writes.append(("send", dict(req)))
        mode = self.send_mode
        if mode.startswith("reject:"):
            return False, dict(retcode=int(mode.split(":")[1]), order=0, deal=0, price=0.0, volume=0.0)
        if mode == "timeout":
            return False, dict(retcode=TIMEOUT, order=0, deal=0, price=0.0, volume=0.0)
        order = self._ticket()
        self.history_orders.append(dict(ticket=order, symbol=req["symbol"], magic=req["magic"], comment=req["comment"],
                                        time_setup_msc=self.time_server_ms()))
        if mode == "placed":
            self.orders[order] = dict(symbol=req["symbol"], comment=req["comment"])
            return True, dict(retcode=PLACED, order=order, deal=0, price=0.0, volume=0.0)
        vol = req["volume"] / 2 if mode == "partial" else req["volume"]
        vol = round(math.floor(vol / self.sym["vstep"] + 1e-9) * self.sym["vstep"], 8)
        deal = self._ticket()
        ident = order
        ticket = ident + self.ticket_offset
        price = self.bid
        self.positions[ticket] = dict(ticket=ticket, identifier=ident, symbol=req["symbol"], magic=req["magic"], comment=req["comment"],
                                      type="SELL", volume=vol, price_open=price, sl=0.0 if mode == "fill_no_sl" else req["sl"],
                                      tp=req["tp"], time=self.time_server(), time_msc=self.time_server_ms())
        self.deals[deal] = dict(order=order, position=ident, price=price, time=self.time_server(), time_msc=self.time_server_ms(),
                                entry="IN", volume=vol, symbol=req["symbol"], magic=req["magic"], comment=req["comment"], reason="EXPERT",
                                profit=0.0, commission=0.0, swap=0.0)
        if mode == "fill_lost_reply":
            return False, dict(retcode=CONNECTION, order=0, deal=0, price=0.0, volume=0.0)
        return True, dict(retcode=DONE_PARTIAL if mode == "partial" else DONE, order=order, deal=deal, price=price, volume=vol)

    def order_send_sltp(self, req):
        self.writes.append(("sltp", dict(req)))
        if self.modify_mode != "ok":
            return False, dict(retcode=DEFINITE_REJECT["INVALID_STOPS"])
        p = self.positions[req["position"]]
        p["sl"], p["tp"] = req["sl"], req["tp"]
        return True, dict(retcode=DONE)

    def order_send_close(self, req):
        self.writes.append(("close", dict(req)))
        if self.close_mode == "reject":
            return False, dict(retcode=DEFINITE_REJECT["REJECT"])
        if self.close_mode == "timeout_no_change":
            return False, dict(retcode=TIMEOUT)
        p = self.positions[req["position"]]
        if self.close_mode == "partial":
            part = round(p["volume"] / 2, 2)
            self.close_volume(req["position"], part, self.ask, "EXPERT")
            return True, dict(retcode=DONE_PARTIAL)
        self.close_volume(req["position"], p["volume"], self.ask, "EXPERT")
        return True, dict(retcode=DONE)

    def close_volume(self, ticket, vol, price, reason):
        p = self.positions[ticket]
        d = self._ticket()
        self.deals[d] = dict(order=self._ticket(), position=p["identifier"], price=price, time=self.time_server(),
                             time_msc=self.time_server_ms(), entry="OUT", volume=vol, symbol=p["symbol"], magic=p["magic"], comment="",
                             reason=reason, profit=(p["price_open"] - price) * vol * self.sym["contract"] * self.usdjpy, commission=0.0,
                             swap=0.0)
        p["volume"] = round(p["volume"] - vol, 8)
        if p["volume"] <= 1e-9:
            del self.positions[ticket]

    def close_position(self, ticket, price, reason):
        self.close_volume(ticket, self.positions[ticket]["volume"], price, reason)

    def history_by_position(self, ident):
        return [(d, v) for d, v in sorted(self.deals.items()) if v["position"] == ident]


class Pos:
    def __init__(self):
        self.key = ""
        self.posId = self.posTicket = self.orderTicket = self.dealTicket = 0
        self.fill = self.sl0 = self.tp0 = self.volume = 0.0
        self.fillTimeSrv = self.fillTimeMsc = self.lastInMsc = self.inDeals = 0
        self.inSet = self.beInSet = ""
        self.beFillBasis = 0.0
        self.fillSyncPending = False
        self.tpSet = self.beDone = self.bePending = self.fillBarDone = self.fillBarUnavailNoted = False
        self.beFav, self.beBar, self.lastBeTry = 0.0, 0, 0
        self.lastBarDone = self.lastTpTry = self.lastCloseTry = 0
        self.closeReason = ""
        self.protectedNoted = self.slMissingNoted = self.missingNoted = False


class EA:
    """inputs as keyword arguments (same names as the MQL5 inputs without the Inp prefix). `approvals` stands for the APPROVED_*
    source constants (all False in the MQL5 source); tests that exercise the send path pass them explicitly."""

    def __init__(self, term, exchange_root, DryRun=True, AllowNewEntries=False, ExpectedLogin=0, ExpectedServer="XSFintech-DEMO",
                 Symbol="XAUUSDs", ExpectedCurrency="JPY", ExpectedSid="XAU-SHORT|XA-23|AU-2",
                 ExpectedCfgSha="72fa9868a3e196ebcd02e37a12f82416d1149e5bd0567d8bf426e2c49f4695ee", ExpectedTvSym="OANDA:XAUUSD",
                 Magic=26102801, FillBarBe="TICKS_SINCE_FILL", approvals=()):
        self.t = term
        self.root = exchange_root
        self.DryRun, self.AllowNewEntries, self.ExpectedLogin = DryRun, AllowNewEntries, ExpectedLogin
        self.ExpectedServer, self.Symbol, self.ExpectedCurrency = ExpectedServer, Symbol, ExpectedCurrency
        self.ExpectedSid, self.ExpectedCfgSha, self.ExpectedTvSym, self.Magic = ExpectedSid, ExpectedCfgSha, ExpectedTvSym, Magic
        self.FillBarBe = FillBarBe
        self.approved = set(approvals)
        self.pos = Pos()
        self.hasPos = self.envOk = self.ready = self.haltNew = self.critical = self.mgmtNoted = False
        self.bindOk = True
        self.journalOk = True
        self.haltReason = self.critReason = self.inflightKey = self.unknownKey = ""
        self.unknownPreMs, self.unknownSl, self.unknownTp = 0, 0.0, 0.0
        self.journalPath = ""
        self.lock = None
        self.rptSeq = 0
        self.seen = set()
        self.journal_fail_states = set()   # test hook: these journal states cannot be written ("*" = every state)
        self.journal_delay = {}            # test hook: state -> ms the write takes
        self.wait_hook = None              # test hook: runs while the EA waits for the bridge (the bridge "process")
        self.before_send_hook = None       # test hook: runs between PrepareOrder and the final checks / the send

    # -- files ------------------------------------------------------------------------------------------------------
    def path(self, *p):
        return os.path.join(self.root, *p)

    def now_ms(self):
        return self.t.time_gmt() * 1000

    def now_ms_late(self):
        return self.t.time_gmt() * 1000 + 999

    def sleep(self, ms):
        self.t.advance(ms)
        if self.wait_hook:
            self.wait_hook()

    @staticmethod
    def sanitize(s):
        return s.replace("\n", " ").replace("\r", " ").replace("|", "/")

    def read_lines(self, p):
        try:
            with open(p, encoding="ascii", errors="replace") as f:
                return kv_lines(f.read())
        except OSError:
            return None

    def write_atomic(self, d, name, body, rewrite):
        os.makedirs(d, exist_ok=True)
        tmp, dst = os.path.join(d, name + ".tmp"), os.path.join(d, name)
        with open(tmp, "w", encoding="ascii", errors="replace", newline="\r\n") as f:
            f.write(body)
        if os.path.exists(dst) and not rewrite:
            os.remove(tmp)
            return False
        os.replace(tmp, dst)
        return True

    def report(self, key, state, fields):
        body = f"t_ms={self.now_ms()}\nkey_hash={self.sanitize(key)}\nstate={state}\n"
        body += "".join(self.sanitize(p) + "\n" for p in fields.split(";") if p.find("=") > 0)
        for _ in range(5):                         # an existing report is never overwritten
            self.rptSeq += 1
            base = f"{self.now_ms():013d}_{_tick():020d}_{self.rptSeq:08d}"
            if os.path.exists(self.path("rpt_done", base + ".rpt")):
                continue
            if self.write_atomic(self.path("rpt"), base + ".rpt", body, False):
                return

    def journal(self, key, state, fields):
        line = f"{self.now_ms()}|{self.sanitize(key)}|{state}|{self.sanitize(fields)}"
        ok = not (state in self.journal_fail_states or "*" in self.journal_fail_states)
        if ok:
            with open(self.journalPath, "a", encoding="ascii", errors="replace", newline="\r\n") as f:
                f.write(line + "\n")
        if state in self.journal_delay:
            self.t.advance(self.journal_delay[state])
        self.journalOk = ok
        if not ok:
            self.critical, self.critReason = True, "journal_write_failed"
            with open(self.path("journal_fallback.txt"), "a", encoding="ascii", errors="replace") as f:
                f.write(line + "\n")
            return False
        if key:
            self.seen.add(key)
        self.report(key, state, fields)
        return True

    def journal_lines(self):
        try:
            with open(self.journalPath, encoding="ascii") as f:
                return [l.rstrip("\r\n").split("|", 3) for l in f if l.strip()]
        except (FileNotFoundError, TypeError):
            return []

    def halt_new(self, reason):
        if not self.haltNew:
            self.haltNew = True
            self.haltReason = reason
            self.journal("", "HALT_NEW", "reason=" + reason)

    def set_critical(self, key, reason):
        self.critical, self.critReason = True, reason
        self.journal(key, "CRITICAL", "reason=" + reason)

    def halt_file_exists(self):
        return os.path.exists(self.path("halt_new"))

    def unapproved(self):
        for a in APPROVALS:
            if a not in self.approved:
                return a
        return ""

    def bridge_hb_age_ms(self):
        l = self.read_lines(self.path("hb_bridge.txt"))
        if l is None:
            return -1
        t = to_int(kv_get(l, "t_ms"))
        return -1 if t <= 0 else self.now_ms_late() - t

    # -- environment ------------------------------------------------------------------------------------------------
    def is_demo(self):
        return self.t.account["trade_mode"] == "DEMO"

    def verify_environment(self):
        a = self.t.account
        if not self.is_demo():
            return "not_demo_account"
        if self.ExpectedLogin <= 0:
            return "expected_login_not_set"
        if a["login"] != self.ExpectedLogin:
            return "login_mismatch"
        if a["server"] != self.ExpectedServer:
            return "server_mismatch"
        if a["currency"] != self.ExpectedCurrency:
            return "currency_mismatch"
        if a["margin_mode"] != "HEDGING":
            return "not_hedging_account"
        if not (self.t.sym["selectable"] and self.t.sym["name"] == self.Symbol):
            return "symbol_not_available"
        if not self.bindOk:
            return "journal_binding_mismatch"
        return ""

    def trade_writes_allowed(self):
        if self.DryRun or not self.envOk or not self.bindOk or not self.ready or not self.is_demo():
            return False
        return self.t.account["login"] == self.ExpectedLogin and self.t.account["server"] == self.ExpectedServer

    def new_entries_allowed(self, self_key=""):
        ua = self.unapproved()
        hb = self.bridge_hb_age_ms()
        if self.DryRun:
            return "dry_run"
        if not self.AllowNewEntries:
            return "new_entries_off"
        if ua:
            return "unapproved:" + ua
        if not self.trade_writes_allowed():
            return "trade_writes_not_allowed"
        if not self.journalOk:
            return "journal_write_failed"
        if self.critical:
            return "critical:" + self.critReason
        if self.unknownKey:
            return "unknown_unresolved:" + self.unknownKey
        if self.haltNew:
            return "halt_new:" + self.haltReason
        if self.halt_file_exists():
            return "halt_file"
        if self.inflightKey and self.inflightKey != self_key:
            return "in_flight:" + self.inflightKey
        if self.hasPos:
            return "max1_own_position"
        if hb < 0 or hb > BRIDGE_HB_MAX_MS:
            return "bridge_heartbeat_stale"
        return ""

    # -- command ----------------------------------------------------------------------------------------------------
    def read_cmd(self, path):
        l = self.read_lines(path)
        if l is None:
            return None
        g = lambda k: kv_get(l, k)

        def num(v):
            try:
                return float(v)          # StringToDouble: "nan" / "inf" stay non-finite and are refused by CheckCmd
            except ValueError:
                return 0.0
        return dict(v=g("v"), key=g("key"), khash=g("key_hash"), tid=g("tid"), ev=g("ev"), side=g("side"), otype=g("otype"),
                    path=g("path"), cfg=g("cfg_sha256"), sid=g("sid"), sym=g("sym"), px=num(g("px")), sl=num(g("sl")), tp=num(g("tp")),
                    barCloseMs=to_int(g("bar_close_ms")))

    def check_cmd(self, c):
        if c["v"] != CMD_VERSION:
            return "cmd_version"
        if not c["key"] or not c["khash"] or sha16(c["key"]) != c["khash"]:
            return "cmd_key"
        if c["ev"] != "ENTRY":
            return "not_entry"
        if c["side"] != "SHORT":
            return "side_not_short"
        if c["otype"] == "LIMIT":
            return "limit_not_supported"
        if c["otype"] != "MARKET":
            return "otype"
        if c["path"] not in ("SATS_PULL", "SATS_NOW"):
            return "path_not_initial_settings"
        if c["sid"] != self.ExpectedSid:
            return "sid_mismatch"
        if c["cfg"] != self.ExpectedCfgSha:
            return "cfg_mismatch"
        if c["sym"] != self.ExpectedTvSym:
            return "tv_symbol_mismatch"
        if not all(math.isfinite(c[k]) for k in ("px", "sl", "tp")):
            return "price_not_finite"
        if not (c["px"] > 0 and c["sl"] > 0 and c["tp"] > 0):
            return "price_not_positive"
        if not (c["sl"] > c["px"] > c["tp"]):
            return "price_geometry"
        if c["barCloseMs"] <= 0 or c["barCloseMs"] % (BAR_SEC * 1000) != 0:
            return "bar_time"
        return ""

    def check_deadline(self, c):
        if self.now_ms() - c["barCloseMs"] < 0:
            return "clock_or_future_bar"
        if self.now_ms_late() - c["barCloseMs"] > MAX_AGE_SEC * 1000:
            return "expired"
        return ""

    # -- market / account checks and the lot ------------------------------------------------------------------------
    def prepare_order(self, c):
        t, s, a = self.t, self.t.sym, self.t.account
        if not t.terminal_trade_allowed:
            return "terminal_trade_not_allowed", None, ""
        if not (a["trade_allowed"] and a["trade_expert"]):
            return "account_trade_not_allowed", None, ""
        if s["trade_mode"] not in ("FULL", "SHORTONLY"):
            return "symbol_sell_not_allowed", None, ""
        if not s["session_open"]:
            return "outside_trade_session", None, ""
        if t.positions:
            return "max1_position_exists", None, ""
        if t.orders:
            return "max1_pending_order_exists", None, ""
        if self.hasPos:
            return "max1_own_position", None, ""
        if t.bid <= 0 or t.ask <= 0:
            return "no_price", None, ""
        spread = t.ask - t.bid
        if spread > MAX_SPREAD + 1e-9:
            return f"spread:{spread:.3f}", None, ""
        slw = c["sl"] - c["px"]
        if slw <= 0:
            return "sl_width_not_positive", None, ""
        dev = abs(t.bid - c["px"])
        if dev > MAX_DEV_FRAC * slw + 1e-9:
            return f"price_deviation:{dev:.3f}", None, ""
        tick, point, digits = s["tick"], s["point"], s["digits"]
        if tick <= 0 or point <= 0:
            return "symbol_spec", None, ""
        sl = round(math.floor(c["sl"] / tick + 1e-9) * tick, digits)
        price = round(t.bid, digits)
        if sl <= t.ask + s["stops"] * point:
            return "sl_too_close_or_crossed", None, ""
        budget = a["balance"] * RISK_FRACTION
        if budget <= 0:
            return "budget", None, ""
        p1 = t.calc_profit_sell(1.0, price, sl)
        if p1 is None or p1 >= 0:
            return "order_calc_profit_failed", None, ""
        loss_per_lot = -p1
        vmin, vmax, vstep, vlim = s["vmin"], s["vmax"], s["vstep"], s["vlim"]
        if vmin <= 0 or vstep <= 0 or vmax <= 0:
            return "volume_spec", None, ""
        vol = math.floor(budget / loss_per_lot / vstep + 1e-9) * vstep
        if vol > vmax:
            vol = math.floor(vmax / vstep + 1e-9) * vstep
        if vlim > 0 and vol > vlim:
            vol = math.floor(vlim / vstep + 1e-9) * vstep
        loss = 0.0
        guard = 0
        while guard < 1000 and vol >= vmin - 1e-9:
            p = t.calc_profit_sell(vol, price, sl)
            if p is None:
                return "order_calc_profit_failed", None, ""
            loss = -p
            if loss <= budget + 1e-6:
                break
            vol -= vstep
            guard += 1
        vol = round(vol, 8)
        if vol < vmin - 1e-9:
            return "below_min_lot", None, ""
        margin = t.calc_margin(vol, price)
        if margin is None:
            return "order_calc_margin_failed", None, ""
        if margin > a["margin_free"]:
            return "margin", None, ""
        remain = MAX_DEV_FRAC * slw - dev
        req = dict(action="DEAL", symbol=self.Symbol, type="SELL", volume=vol, price=price, sl=sl, tp=0.0, magic=self.Magic,
                   comment="XSD:" + c["khash"], deviation=max(0, math.floor(remain / point)))
        if not t.check_ok:
            return "order_check:10019", None, ""
        detail = (f"bid={t.bid:.{digits}f};ask={t.ask:.{digits}f};spread={spread:.3f};dev={dev:.3f};sl={sl:.{digits}f};volume={vol:.2f};"
                  f"budget_jpy={budget:.0f};planned_loss_jpy={loss:.0f};margin_jpy={margin:.0f};"
                  "note=actual loss can exceed 3% (fill slippage / SL slippage / conversion / commission / swap not in the budget)")
        return "", req, detail

    # -- final permission from the bridge -----------------------------------------------------------------------------
    def ask_bridge(self, c, dry):
        ans = self.path("ans", c["khash"] + ".ans")
        if os.path.exists(ans):
            os.replace(ans, self.path("done", c["khash"] + ".stale.ans"))
        body = f"key_hash={c['khash']}\nt_ms={self.now_ms()}\ndry_run={'1' if dry else '0'}\n"
        if not self.write_atomic(self.path("ask"), c["khash"] + ".ask", body, True):
            return "nogo:ask_write_failed", 0
        waited = 0
        while waited < ASK_WAIT_MS:
            if os.path.exists(ans):
                l = self.read_lines(ans)
                os.replace(ans, self.path("done", c["khash"] + ".ans"))
                if l is None or kv_get(l, "key_hash") != c["khash"]:
                    return "nogo:answer_unreadable", 0
                if kv_get(l, "decision") != "GO":
                    return "nogo:" + kv_get(l, "reason"), 0
                until = min(to_int(kv_get(l, "valid_until_ms")), c["barCloseMs"] + MAX_AGE_SEC * 1000)
                if self.now_ms_late() > until:
                    return "nogo:go_expired_on_arrival", 0
                return "", until
            self.sleep(50)
            waited += 50
        return "nogo:no_answer", 0

    def send_check(self, c, id_, go_until, base):
        why, out, _ = self.prepare_order(c)                # the slow part first (terminal / OrderCheck)
        if why:
            return why, None
        if abs(out["volume"] - base["volume"]) > 1e-9 or abs(out["sl"] - base["sl"]) > 1e-9:
            return "request_changed", None
        why = self.final_gate(c, id_, go_until)            # the cheap checks last, right before OrderSend
        return (why, None) if why else ("", out)

    def final_gate(self, c, id_, go_until):
        gate = self.new_entries_allowed(id_)              # every read (files, terminal lists) first
        if gate:
            return gate
        if self.t.positions:
            return "max1_position_exists"
        if self.t.orders:
            return "max1_pending_order_exists"
        why = self.check_deadline(c)                      # clock only, after every read
        if why:
            return why
        if self.now_ms_late() > go_until:
            return "go_expired"
        return ""

    # -- ownership ------------------------------------------------------------------------------------------------
    def select_own(self):
        """1 = own position open (posTicket refreshed), 0 = identifier not open, -1 = identifier open but not ours -> quarantine."""
        for tk, p in sorted(self.t.positions.items(), reverse=True):
            if p["identifier"] != self.pos.posId:
                continue
            if p["symbol"] != self.Symbol or p["magic"] != self.Magic or p["type"] != "SELL":
                self.quarantine("ownership_mismatch", tk)
                return -1
            if tk != self.pos.posTicket:
                self.journal(self.pos.key, "TICKET_CHANGED", f"position_id={self.pos.posId};old={self.pos.posTicket};new={tk}")
                self.pos.posTicket = tk
            return 1
        return 0

    def fill_stats(self, ident):
        """IN / OUT totals, IN count, last IN time and the IN deal set identity (sha16 of the sorted IN deal tickets)."""
        vin = vout = 0.0
        n_in = last_in = 0
        ins = []
        for d, x in self.t.history_by_position(ident):
            if x["entry"] == "IN":
                vin, n_in, last_in = vin + x["volume"], n_in + 1, max(last_in, x["time_msc"])
                ins.append(d)
            elif x["entry"] == "OUT":
                vout += x["volume"]
        return vin, vout, n_in, last_in, sha16("".join(f"{d}," for d in sorted(ins)))

    def position_unchanged(self, ticket, ident, v, po):
        p = self.t.positions.get(ticket)
        return p is not None and p["identifier"] == ident and abs(p["volume"] - v) <= 1e-9 and abs(p["price_open"] - po) <= 1e-9

    def refresh_fill(self):
        """the fill state must be explained by the history (IN - OUT = live volume); otherwise FILL_HISTORY_PENDING and wait."""
        P = self.pos
        p = self.t.positions.get(P.posTicket)
        if p is None:
            return False
        v, po = p["volume"], p["price_open"]
        vin, vout, n_in, last_in, in_set = self.fill_stats(P.posId)
        stable = self.position_unchanged(P.posTicket, P.posId, v, po)      # re-read AFTER the history
        if not (stable and n_in > 0 and abs(vin - vout - v) <= 1e-6):
            if not P.fillSyncPending:
                P.fillSyncPending = True
                why = "position_changed_during_read" if not stable else "history_does_not_explain_volume"
                self.journal(P.key, "FILL_HISTORY_PENDING", f"reason={why};live_volume={v:.2f};hist_in={vin:.2f};hist_out={vout:.2f};"
                                                            f"in_deals={n_in};note=breakeven_and_fill_checks_wait")
            return False
        last_in = max(last_in, P.fillTimeMsc)
        new_in = in_set != P.inSet or n_in != P.inDeals or last_in != P.lastInMsc
        was_pending = P.fillSyncPending
        changed = new_in or abs(v - P.volume) > 1e-9 or abs(po - P.fill) > 1e-9 or was_pending
        P.fillSyncPending = False
        if not changed:
            return True
        cause = "add" if v > P.volume + 1e-9 else "reduce" if v < P.volume - 1e-9 else "history" if (new_in or was_pending) else "price"
        P.volume, P.fill, P.inDeals, P.inSet, P.lastInMsc = v, po, n_in, in_set, last_in
        self.journal(P.key, "POSITION_UPDATED", f"cause={cause};volume={v:.2f};fill_price={po:.5f};last_in_msc={last_in};"
                                                f"in_deals={n_in};in_set={in_set};position_id={P.posId};fill_bits={dbl_bits(po)}")
        if new_in and not P.beDone:
            self.void_breakeven_basis()
        return True

    def void_breakeven_basis(self):
        P = self.pos
        if P.bePending:
            self.journal(P.key, "BE_TRIGGER_VOID", f"reason=later_in_deal;fav={P.beFav:.5f};bar_open={P.beBar};last_in_msc={P.lastInMsc};"
                                                   f"fill={P.fill:.5f}")
            P.bePending, P.beFav, P.beBar, P.beInSet, P.beFillBasis = False, 0.0, 0, "", 0.0
        fbo = P.fillTimeSrv - P.fillTimeSrv % BAR_SEC
        li = P.lastInMsc // 1000
        lib = li - li % BAR_SEC
        P.fillBarDone = P.fillBarUnavailNoted = False
        P.lastBarDone = max(lib, fbo)

    def own(self):
        return self.t.positions[self.pos.posTicket]

    def quarantine(self, reason, ticket):
        self.journal(self.pos.key, "QUARANTINE", f"reason={reason};position_id={self.pos.posId};ticket={ticket};note=no_write_to_this_position")
        self.hasPos = False
        self.halt_new("quarantine:" + reason)
        self.set_critical(self.pos.key, "quarantine:" + reason)

    def history_volumes(self, ident):
        vin = vout = 0.0
        last_out = None
        for d, v in self.t.history_by_position(ident):
            if v["entry"] == "IN":
                vin += v["volume"]
            elif v["entry"] == "OUT":
                vout += v["volume"]
                last_out = (d, v)
        return vin, vout, last_out

    # -- trade wrappers -----------------------------------------------------------------------------------------------
    def ticket_of_identifier(self, ident):
        for tk, p in sorted(self.t.positions.items(), reverse=True):
            if p["identifier"] == ident and p["symbol"] == self.Symbol and p["magic"] == self.Magic and p["type"] == "SELL":
                return tk
        return 0

    def adopt_own(self, key, pos_id, ticket, order, deal, sl0, tp0, via):
        p = self.t.positions[ticket]
        P = self.pos = Pos()
        P.key, P.posId, P.posTicket, P.orderTicket, P.dealTicket = key, pos_id, ticket, order, deal
        P.fill, P.volume, P.sl0, P.tp0, P.fillTimeSrv, P.fillTimeMsc = p["price_open"], p["volume"], sl0, tp0, p["time"], p["time_msc"]
        vin, vout, n_in, last_in, in_set = self.fill_stats(pos_id)
        ok = self.position_unchanged(ticket, pos_id, P.volume, P.fill) and n_in > 0 and abs(vin - vout - P.volume) <= 1e-6
        P.inDeals = n_in if ok else 0
        P.inSet = in_set if ok else ""
        P.lastInMsc = max(last_in, P.fillTimeMsc) if ok else P.fillTimeMsc
        P.fillSyncPending = not ok
        fbo = P.fillTimeSrv - P.fillTimeSrv % BAR_SEC
        li = P.lastInMsc // 1000
        P.lastBarDone = max(li - li % BAR_SEC, fbo)
        self.hasPos = True
        self.journal(key, "FILLED", f"order={order};deal={deal};position_id={pos_id};position={ticket};fill_price={P.fill:.5f};"
                                    f"volume={P.volume:.2f};sl0={sl0:.5f};tp0={tp0:.5f};fill_time={P.fillTimeSrv};fill_time_msc={P.fillTimeMsc};"
                                    f"in_deals={P.inDeals};last_in_msc={P.lastInMsc};in_set={P.inSet};fill_sync={'ok' if ok else 'pending'};via={via};"
                                    f"fill_bits={dbl_bits(P.fill)}")

    def confirm_fill(self, key, order, deal, sl0, tp0):
        pos_id = self.t.deals[deal]["position"] if deal and deal in self.t.deals else 0
        if not pos_id:
            return False
        tk = self.ticket_of_identifier(pos_id)
        if not tk:
            return False
        self.adopt_own(key, pos_id, tk, order, deal, sl0, tp0, "send")
        return True

    def close_position(self, key, reason):
        if not self.trade_writes_allowed() or not self.hasPos or self.select_own() != 1:
            return CLOSE_NOT_ALLOWED, -1
        p = self.own()
        vol = p["volume"]
        req = dict(action="DEAL", symbol=self.Symbol, type="BUY", position=self.pos.posTicket, volume=vol, price=self.t.ask,
                   magic=self.Magic, comment="XSD:" + self.pos.key + ":C", deviation=CLOSE_DEVIATION_POINTS)
        self.journal(key, "CLOSE_PRE_SEND", f"reason={reason};position_id={self.pos.posId};volume={vol:.2f}")
        ok, res = self.t.order_send_close(req)
        result, remaining = CLOSE_UNKNOWN, -1
        sel = self.select_own()
        if sel == 1:
            remaining = self.own()["volume"]
            if remaining < vol - 1e-9:
                result = CLOSE_PARTIAL
            elif not ok and res["retcode"] in DEFINITE_REJECT.values():
                result = CLOSE_FAILED
        elif sel == 0:
            remaining = 0
            vin, vout, _ = self.history_volumes(self.pos.posId)
            if vin > 0 and vout >= vin - 1e-9:
                result = CLOSE_FULL
        st = {CLOSE_FULL: "CLOSE_DONE", CLOSE_PARTIAL: "CLOSE_PARTIAL", CLOSE_FAILED: "CLOSE_FAILED"}.get(result, "CLOSE_UNKNOWN")
        self.journal(key, st, f"reason={reason};retcode={res['retcode']};remaining={remaining:.2f}")
        return result, remaining

    def modify_own(self, what, new_sl, new_tp):
        if not self.trade_writes_allowed() or not self.hasPos or self.select_own() != 1:
            return False
        cur_sl = self.own()["sl"]
        if new_sl <= 0 or (cur_sl > 0 and new_sl > cur_sl + 1e-9):
            self.journal(self.pos.key, "MODIFY_REFUSED", f"what={what};reason=would_loosen_or_remove_sl")
            return False
        ok, res = self.t.order_send_sltp(dict(action="SLTP", symbol=self.Symbol, position=self.pos.posTicket, sl=new_sl, tp=new_tp,
                                              magic=self.Magic))
        if not ok or res["retcode"] != DONE:
            self.journal(self.pos.key, "MODIFY_FAILED", f"what={what};retcode={res['retcode']};sl_kept={cur_sl:.5f}")
            self.halt_new("modify_failed:" + what)
            return False
        return True

    def process_entry(self, c, id_):
        if not self.journal(id_, "SEEN", f"tid={c['tid']};bar_close_ms={c['barCloseMs']}"):
            return
        why = self.check_cmd(c)
        if not why:
            why = self.check_deadline(c)
        gate, dry = "", False
        if not why:
            gate = self.new_entries_allowed()
            if gate in ("dry_run", "new_entries_off"):
                dry = True
            elif gate:
                why = gate
        detail, req = "", None
        if not why:
            why, req, detail = self.prepare_order(c)
        if why:
            self.journal(id_, "SKIPPED", "reason=" + why)
            return
        go, go_until = self.ask_bridge(c, dry)
        if dry:
            ua = self.unapproved()
            self.journal(id_, "DRY_RUN_NOT_SENT", f"gate={gate};go={go or 'granted'};unapproved={ua or 'none'};{detail}")
            return
        if go:
            self.journal(id_, "SKIPPED", "reason=" + go)
            return
        if not self.journal(id_, "DECIDED", detail):
            return
        self.inflightKey = id_
        if not self.journal(id_, "PRE_SEND", f"volume={req['volume']:.2f};sl={req['sl']:.5f};price={req['price']:.5f};"
                                             f"tp0={c['tp']:.5f};go_until_ms={go_until}"):
            self.inflightKey = ""
            self.halt_new("journal_write_failed")
            return
        if self.before_send_hook:
            self.before_send_hook()
        why, fin = self.send_check(c, id_, go_until, req)
        if why:
            if self.journal(id_, "SEND_ABORTED", "reason=" + why):
                self.inflightKey = ""
            else:
                self.inflightKey = ""
                self.unknownKey, self.unknownPreMs, self.unknownSl, self.unknownTp = id_, self.now_ms(), req["sl"], c["tp"]
            return
        ok, res = self.t.order_send(fin)
        self.journal(id_, "SEND_RETURNED", f"ok={int(ok)};retcode={res['retcode']};order={res['order']};deal={res['deal']};"
                                           f"fill_price={res['price']:.5f};volume={res['volume']:.2f};price_sent={fin['price']:.5f}")
        if res["retcode"] in (DONE, DONE_PARTIAL):
            if self.confirm_fill(id_, res["order"], res["deal"], fin["sl"], c["tp"]):
                self.inflightKey = ""
                if res["retcode"] == DONE_PARTIAL:
                    self.journal(id_, "PARTIAL_FILL", f"volume={self.pos.volume:.2f};requested={fin['volume']:.2f}")
                self.check_protection()
                return
            self.mark_unknown(id_, fin["sl"], c["tp"], "done_but_fill_not_confirmed")
            return
        if not ok and res["retcode"] in DEFINITE_REJECT.values():
            self.inflightKey = ""
            self.journal(id_, "REJECTED", f"retcode={res['retcode']}")
            return
        self.mark_unknown(id_, fin["sl"], c["tp"], f"retcode_{res['retcode']}")

    def mark_unknown(self, id_, sl, tp, reason):
        self.inflightKey = ""
        self.unknownKey, self.unknownPreMs, self.unknownSl, self.unknownTp = id_, self.now_ms() - 1000, sl, tp
        self.journal(id_, "UNKNOWN", "reason=" + reason)
        self.halt_new("unknown_result:" + id_)

    def require_close(self, reason):
        if self.pos.closeReason:
            return
        self.pos.closeReason = reason
        self.journal(self.pos.key, "CLOSE_REQUIRED", f"reason={reason};position_id={self.pos.posId}")

    def process_close_obligation(self):
        P = self.pos
        if not self.hasPos or not P.closeReason or not self.trade_writes_allowed() or self.select_own() != 1:
            return
        now_s = self.t.time_gmt()
        if P.lastCloseTry > 0 and now_s - P.lastCloseTry < EMERGENCY_RETRY_SEC:
            return
        P.lastCloseTry = now_s
        reason = P.closeReason
        emergency = reason == "emergency_initial_sl_missing"
        r, remaining = self.close_position(P.key, reason)
        if r == CLOSE_NOT_ALLOWED:
            return
        if r == CLOSE_FULL:
            if emergency:
                self.journal(P.key, "EMERGENCY_CLOSE", "result=closed_confirmed")
            else:
                self.journal(P.key, "CLOSE_CONFIRMED", f"result=closed_confirmed;reason={reason}")
            return
        kind = {CLOSE_PARTIAL: "partial", CLOSE_FAILED: "failed"}.get(r, "unknown")
        if r == CLOSE_PARTIAL:
            if emergency:
                self.journal(P.key, "EMERGENCY_CLOSE_PARTIAL", f"remaining={remaining:.2f};note=unprotected_remainder_retried")
            else:
                self.journal(P.key, "CLOSE_INCOMPLETE", f"remaining={remaining:.2f};reason={reason};note=remainder_retried")
        self.halt_new("close_incomplete:" + reason)
        cr = "emergency_close_" + kind if emergency else f"close_{kind}:{reason}"
        if not self.critical or self.critReason != cr:
            self.set_critical(P.key, cr)

    def check_protection(self):
        if not self.hasPos or self.select_own() != 1:
            return
        P = self.pos
        sl = self.own()["sl"]
        if sl > 0 and sl <= P.sl0 + self.t.sym["tick"] * 0.5 + 1e-9:
            if not P.protectedNoted:
                P.protectedNoted = True
                self.journal(P.key, "PROTECTED", f"sl={sl:.5f}")
            return
        P.protectedNoted = False
        self.halt_new("initial_sl_missing")
        if not P.slMissingNoted:
            P.slMissingNoted = True
            self.journal(P.key, "SL_MISSING", f"sl_on_position={sl:.5f};sl0={P.sl0:.5f}")
        self.require_close("emergency_initial_sl_missing")
        self.process_close_obligation()

    # -- management -------------------------------------------------------------------------------------------------
    def check_closed_from_history(self):
        P = self.pos
        vin, vout, last = self.history_volumes(P.posId)
        if vin > 0 and vout >= vin - 1e-9:
            d, v = last
            hist = self.t.history_by_position(P.posId)
            self.journal(P.key, "CLOSED", f"reason={v['reason'].lower()};deal={d};price={v['price']:.5f};"
                                          f"profit={sum(x['profit'] for _, x in hist):.0f};commission={sum(x['commission'] for _, x in hist):.0f};"
                                          f"swap={sum(x['swap'] for _, x in hist):.0f};position_id={P.posId}")
            self.hasPos = False
            return
        if not P.missingNoted:
            P.missingNoted = True
            self.journal(P.key, "OWN_POSITION_MISSING", f"position_id={P.posId};in={vin:.2f};out={vout:.2f};note=not_treated_as_closed")
            self.halt_new("own_position_missing")

    def fill_bar_low(self, fill_bar_open):
        frm = max(self.pos.fillTimeMsc, self.pos.lastInMsc) + 1
        to = (fill_bar_open + BAR_SEC) * 1000 - 1
        if to < frm:
            return 0, 0.0
        ticks = self.t.copy_ticks_range(frm, to)
        if ticks is None:
            return -1, 0.0
        bids = [b for tm, b in ticks if b > 0 and frm <= tm <= to]
        return len(bids), (min(bids) if bids else 0.0)

    def manage_own(self):
        if not self.hasPos:
            return
        own = self.select_own()
        if own < 0:
            return
        if own == 0:
            self.check_closed_from_history()
            return
        fill_ok = self.refresh_fill()
        if not self.trade_writes_allowed():
            if not self.mgmtNoted:
                self.mgmtNoted = True
                self.journal(self.pos.key, "MANAGEMENT_BLOCKED", "reason=trade_writes_not_allowed;note=the_server_side_sl_stays")
            return
        self.mgmtNoted = False
        self.check_protection()
        if not self.hasPos or self.select_own() != 1:
            return
        if self.pos.closeReason:
            self.process_close_obligation()
            return
        if not fill_ok or self.select_own() != 1:
            return
        P, t = self.pos, self.t
        sl_now = self.own()["sl"]
        if not (sl_now > 0 and sl_now <= P.sl0 + t.sym["tick"] * 0.5 + 1e-9):
            return
        now = t.time_server()
        fill_bar_open = P.fillTimeSrv - P.fillTimeSrv % BAR_SEC
        if now < fill_bar_open + BAR_SEC:
            return
        digits = t.sym["digits"]
        if not P.tpSet and (P.lastTpTry == 0 or now - now % BAR_SEC > P.lastTpTry - P.lastTpTry % BAR_SEC):
            P.lastTpTry = now
            if not (P.sl0 - P.fill > 0 and P.fill - P.tp0 > 0):
                self.journal(P.key, "FILL_SIDE_BAD", f"fill={P.fill:.{digits}f}")
                self.require_close("bad_fill_side_mt5")
                self.process_close_obligation()
                return
            if self.select_own() != 1:
                return
            cur_sl = self.own()["sl"]
            if self.modify_own("tp0", cur_sl, round(P.tp0, digits)):
                P.tpSet = True
                self.journal(P.key, "TP_SET", f"tp={P.tp0:.{digits}f};sl_kept={cur_sl:.{digits}f}")
        self.retry_breakeven(now)
        if not P.fillBarDone:
            if P.beDone or P.bePending or self.FillBarBe != "TICKS_SINCE_FILL":
                P.fillBarDone = True
            else:
                n, lo = self.fill_bar_low(fill_bar_open)
                if n < 0:
                    if not P.fillBarUnavailNoted:
                        P.fillBarUnavailNoted = True
                        self.journal(P.key, "FILLBAR_TICKS_UNAVAILABLE", f"fill_bar_open={fill_bar_open};note=retried")
                else:
                    if n > 0:
                        self.try_breakeven(lo, fill_bar_open)
                    else:
                        self.journal(P.key, "FILLBAR_NO_TICKS", "n=0")
                    P.fillBarDone = True
        if P.beDone or P.bePending:
            return
        if P.lastBarDone < fill_bar_open:
            P.lastBarDone = fill_bar_open
        last_in_s = max(P.fillTimeMsc, P.lastInMsc) // 1000
        last_in_bar = last_in_s - last_in_s % BAR_SEC
        frm = P.lastBarDone + BAR_SEC
        for (bt, low) in sorted(t.rates):
            if P.beDone or P.bePending:
                break
            if bt < frm or bt > now or bt + BAR_SEC > now:
                continue
            if bt > last_in_bar:
                self.try_breakeven(low, bt)
            P.lastBarDone = bt

    def try_breakeven(self, fav_low, bar_open):
        P = self.pos
        if P.beDone or P.bePending or fav_low <= 0:
            return
        if P.fill - fav_low >= BE_DIST - 1e-9:
            P.bePending, P.beFav, P.beBar, P.beInSet, P.beFillBasis = True, fav_low, bar_open, P.inSet, P.fill
            digits = self.t.sym["digits"]
            self.journal(P.key, "BE_TRIGGERED", f"fav={fav_low:.{digits}f};bar_open={bar_open};fill={P.fill:.5f};"
                                                f"dist={P.fill - fav_low:.{digits}f};last_in_msc={P.lastInMsc};in_deals={P.inDeals};in_set={P.inSet};"
                                                f"fill_bits={dbl_bits(P.fill)}")
            self.apply_breakeven()

    def apply_breakeven(self):
        P = self.pos
        P.lastBeTry = self.t.time_server()
        digits = self.t.sym["digits"]
        if self.select_own() != 1 or not self.refresh_fill():
            return
        if not P.bePending:
            return
        if P.beInSet != P.inSet or not basis_match(P.beFillBasis, P.fill):
            self.void_breakeven_basis()
            return
        if self.select_own() != 1:
            return
        new_sl = round(P.fill, digits)
        cur_tp = self.own()["tp"]
        if self.modify_own("breakeven", new_sl, cur_tp):
            P.beDone, P.bePending = True, False
            self.journal(P.key, "BE_SET", f"sl={new_sl:.{digits}f};bar_open={P.beBar};fav={P.beFav:.{digits}f}")

    def retry_breakeven(self, now):
        P = self.pos
        if not P.bePending or P.beDone:
            return
        if P.lastBeTry > 0 and now - now % BAR_SEC <= P.lastBeTry - P.lastBeTry % BAR_SEC:
            return
        self.apply_breakeven()

    # -- result unknown -------------------------------------------------------------------------------------------------
    def detect_unknown(self, kh, pre_ms):
        tag = "XSD:" + kh
        t = self.t
        frm_srv_ms = (pre_ms // 1000 + t.server_offset - 120) * 1000
        orders = [o["ticket"] for o in t.history_orders if o["symbol"] == self.Symbol and o["magic"] == self.Magic and o["comment"] == tag
                  and o["time_setup_msc"] >= frm_srv_ms]
        pids = []
        for d, v in sorted(t.deals.items()):
            if v["symbol"] != self.Symbol or v["magic"] != self.Magic or v["entry"] != "IN" or v["time_msc"] < frm_srv_ms:
                continue
            if v["comment"] == tag or v["order"] in orders:
                if not pids or pids[-1] != v["position"]:
                    pids.append(v["position"])
        pending = sum(1 for o in t.orders.values() if o.get("comment") == tag)
        tagpos = sum(1 for p in t.positions.values() if p["comment"] == tag)
        if pending:
            return "ambiguous:pending_order", 0, 0
        if len(pids) > 1:
            return "ambiguous:several_positions", 0, 0
        if not pids:
            return ("none" if not orders and not tagpos else "ambiguous:order_or_position_without_deal"), 0, 0
        pid = pids[0]
        tk = self.ticket_of_identifier(pid)
        if tk:
            return "open", pid, tk
        if t.by_identifier(pid)[1] is not None:
            return "ambiguous:position_not_own", 0, 0
        vin, vout, _ = self.history_volumes(pid)
        if vin > 0 and vout >= vin - 1e-9:
            return "closed", pid, 0
        return "ambiguous:history_incomplete", 0, 0

    def check_resolve_unknown(self):
        f = self.path("resolve_unknown")
        if not os.path.exists(f):
            return
        l = self.read_lines(f) or []
        os.remove(f)
        kh, confirm = kv_get(l, "key_hash"), kv_get(l, "confirm")
        if not self.unknownKey or kh != self.unknownKey:
            self.journal("", "UNKNOWN_RESOLVE_REFUSED", f"reason=not_the_unknown_key;given={kh};unknown={self.unknownKey}")
            return
        detected, pid, tk = self.detect_unknown(self.unknownKey, self.unknownPreMs)
        if detected.startswith("ambiguous") or confirm != detected:
            self.journal(self.unknownKey, "UNKNOWN_RESOLVE_REFUSED", f"reason=confirm_mismatch;confirm={confirm};detected={detected}")
            return
        key = self.unknownKey
        if detected == "open":
            if tk not in self.t.positions:
                self.journal(key, "UNKNOWN_RESOLVE_REFUSED", "reason=position_vanished")
                return
            self.adopt_own(key, pid, tk, 0, 0, self.unknownSl, self.unknownTp, "unknown_resolution")
        if not self.journal(key, "UNKNOWN_RESOLVED", f"result={detected};position_id={pid};note=new_entries_stay_halted_until_resume_new"):
            return
        self.unknownKey = ""
        if detected == "open":
            self.check_protection()

    # -- startup reconciliation -------------------------------------------------------------------------------------
    def reconcile(self):
        last_pre = unknown = pos_key = ""
        pre_ms, pre_sl, pre_tp = 0, 0.0, 0.0
        pos_id = fill_msc = fill_time = pos_ticket = 0
        sl0 = tp0 = fill = vol = be_fav = 0.0
        last_in = be_bar = in_deals = 0
        in_set = be_in_set = ""
        be_fill_basis = 0.0
        fill_state = be_state = PX_EXACT
        damaged = []
        close_req = ""
        closed = quarantined = bind_seen = be_set = be_trig = False
        a = self.t.account
        for parts in self.journal_lines():
            if len(parts) < 4:
                continue
            key, st, f = parts[1], parts[2], parts[3]
            kv = f.split(";")
            if key:
                self.seen.add(key)
            if st == "BIND" and not bind_seen:
                bind_seen = True
                self.bindOk = (kv_get(kv, "login") == str(a["login"]) and kv_get(kv, "server") == a["server"]
                               and kv_get(kv, "magic") == str(self.Magic) and kv_get(kv, "sid") == self.sanitize(self.ExpectedSid)
                               and kv_get(kv, "cfg") == self.ExpectedCfgSha and kv_get(kv, "symbol") == self.Symbol)
            if st == "HALT_NEW":
                self.haltNew, self.haltReason = True, f
            if st == "RESUME_NEW":
                self.haltNew, self.haltReason = False, ""
            if st == "CRITICAL":
                self.critical, self.critReason = True, kv_get(kv, "reason")
            if st == "CRITICAL_CLEARED":
                self.critical, self.critReason = False, ""
            if st == "PRE_SEND":
                last_pre, pre_ms = key, int(parts[0])
                pre_sl, pre_tp = to_float(kv_get(kv, "sl")), to_float(kv_get(kv, "tp0"))
            if st in ("REJECTED", "FILLED", "SEND_ABORTED", "UNKNOWN_RESOLVED") and key == last_pre:
                last_pre = ""
            if st == "UNKNOWN":
                unknown = key
            if st == "UNKNOWN_RESOLVED" and key == unknown:
                unknown = ""
            if st == "FILLED":
                pos_key, closed, quarantined = key, False, False
                pos_id, pos_ticket = to_int(kv_get(kv, "position_id")), to_int(kv_get(kv, "position"))
                sl0, tp0 = to_float(kv_get(kv, "sl0")), to_float(kv_get(kv, "tp0"))
                fill, fill_state = px_read(kv, "fill_bits", "fill_price")
                damaged = ["FILLED"] if fill_state == PX_DAMAGED else []     # only the records of the current own position count
                fill_time, fill_msc = to_int(kv_get(kv, "fill_time")), to_int(kv_get(kv, "fill_time_msc"))
                vol = to_float(kv_get(kv, "volume"))
                last_in, in_deals = max(fill_msc, to_int(kv_get(kv, "last_in_msc"))), to_int(kv_get(kv, "in_deals"))
                in_set = kv_get(kv, "in_set")
                close_req, be_set, be_trig = "", False, False
            if not pos_key or key != pos_key:
                continue
            if st == "POSITION_UPDATED":
                fill, fill_state = px_read(kv, "fill_bits", "fill_price")
                if fill_state == PX_DAMAGED:
                    damaged.append("POSITION_UPDATED")
                vol = to_float(kv_get(kv, "volume"))
                last_in, in_deals = max(last_in, to_int(kv_get(kv, "last_in_msc"))), to_int(kv_get(kv, "in_deals"))
                in_set = kv_get(kv, "in_set")
            if st == "CLOSE_REQUIRED":
                close_req = kv_get(kv, "reason")
            if st == "BE_TRIGGERED":
                be_trig, be_fav, be_bar = True, to_float(kv_get(kv, "fav")), to_int(kv_get(kv, "bar_open"))
                be_in_set = kv_get(kv, "in_set")
                be_fill_basis, be_state = px_read(kv, "fill_bits", "fill")
                if be_state == PX_DAMAGED:
                    damaged.append("BE_TRIGGERED")
            # BE_TRIGGER_VOID is informational: whether a condition is restored is decided by its basis below
            if st == "BE_SET":
                be_set = True
            if st == "CLOSED":
                closed = True
            if st == "QUARANTINE":
                quarantined = True
        if not bind_seen:
            self.bindOk = True
            self.journal("", "BIND", f"login={a['login']};server={a['server']};magic={self.Magic};sid={self.ExpectedSid};"
                                     f"cfg={self.ExpectedCfgSha};symbol={self.Symbol}")
        elif not self.bindOk:
            self.journal("", "BIND_MISMATCH", "note=journal_of_another_account_or_strategy;all_trade_writes_refused")
        if last_pre and not unknown:
            unknown = last_pre
            self.journal(unknown, "UNKNOWN", "reason=pre_send_without_result_at_startup")
        if unknown:
            self.unknownKey, self.unknownPreMs, self.unknownSl, self.unknownTp = unknown, pre_ms, pre_sl, pre_tp
            self.halt_new("unknown_result_after_restart")
            det = self.detect_unknown(unknown, pre_ms)[0]
            self.journal(unknown, "UNKNOWN_CHECK", f"detected={det};note=resolve_unknown_file_needed")
        if damaged and pos_key and not closed and not quarantined:
            # ST3-7: a damaged bit field is an anomaly (not a legacy record): new entries stop; the position is still protected
            self.journal(pos_key, "JOURNAL_DAMAGED", f"records={','.join(damaged)};field=fill_bits;note=not_reused")
            self.halt_new("journal_price_damaged")
        if pos_key and not closed and not quarantined and pos_id > 0:
            P = self.pos = Pos()
            P.key, P.posId, P.posTicket, P.sl0, P.tp0, P.fill = pos_key, pos_id, pos_ticket, sl0, tp0, fill
            P.volume, P.fillTimeSrv, P.fillTimeMsc, P.lastInMsc, P.inDeals, P.inSet = vol, fill_time, fill_msc, last_in, in_deals, in_set
            li = last_in // 1000
            P.lastBarDone = max(li - li % BAR_SEC, fill_time - fill_time % BAR_SEC)
            # ST3-7: a met condition is restored only from an EXACT basis (the BE_TRIGGERED bit field) on the same IN deal set. Its
            # average is compared with the journaled average here only when that one is exact too; otherwise the comparison is made
            # against the live average right before the SL change (ApplyBreakeven, 1e-6). A basis known only to 5 decimals (legacy)
            # or damaged is not reused: the condition is voided and re-evaluated from the price history against the live average
            # (fill-bar ticks after the last IN deal, then the closed bars), so no tolerance wider than 1e-6 is ever used.
            void_why = ""
            if be_trig and not be_set and be_state != PX_EXACT:
                void_why = "basis_precision_unknown" if be_state == PX_LEGACY else "basis_record_damaged"
                be_trig = False
            if be_trig and (not be_in_set or be_in_set != in_set or (fill_state == PX_EXACT and not basis_match(be_fill_basis, fill))):
                be_trig = False
            P.closeReason = close_req
            P.beDone, P.bePending, P.beFav, P.beBar = be_set, be_trig and not be_set, be_fav, be_bar
            P.beInSet, P.beFillBasis = (be_in_set, be_fill_basis) if be_trig else ("", 0.0)
            P.fillBarDone = be_trig or be_set
            self.hasPos = True
            if void_why:
                self.journal(pos_key, "BE_TRIGGER_VOID", f"reason={void_why};fav={be_fav:.5f};bar_open={be_bar};fill={be_fill_basis:.5f};"
                                                         "note=re_evaluated_from_price_history")
            sel = self.select_own()
            if sel == 1:
                self.refresh_fill()
                p = self.own()
                P.tpSet = p["tp"] > 0
                P.beDone = P.beDone or abs(p["sl"] - P.fill) <= self.t.sym["tick"] * 0.5 + 1e-9
                if P.beDone:
                    P.bePending = False
                self.journal(pos_key, "OWNED_AT_STARTUP", f"position_id={pos_id};position={P.posTicket}")
            elif sel == 0:
                self.check_closed_from_history()

    def check_resume(self):
        fc = self.path("clear_critical")
        if os.path.exists(fc):
            os.remove(fc)
            if self.critical:
                self.critical, self.critReason = False, ""
                self.journal("", "CRITICAL_CLEARED", "by=operator_file;note=new_entries_stay_halted_until_resume_new")
                self.halt_new("after_critical")
        f = self.path("resume_new")
        if not os.path.exists(f):
            return
        os.remove(f)
        if self.critical:
            self.journal("", "RESUME_REFUSED", "reason=critical")
            return
        if self.unknownKey:
            self.journal("", "RESUME_REFUSED", f"reason=unknown_unresolved;key_hash={self.unknownKey};note=use_resolve_unknown")
            return
        self.haltNew, self.haltReason = False, ""
        self.journal("", "RESUME_NEW", "by=operator_file")

    def poll_commands(self):
        d = self.path("cmd")
        for name in sorted(n for n in os.listdir(d) if n.endswith(".entry.txt")):
            src = os.path.join(d, name)
            c = self.read_cmd(src)
            if c is None:
                self.journal("", "BAD_CMD", f"file={name};reason=unreadable")
            elif not c["khash"] or sha16(c["key"]) != c["khash"]:
                self.journal("", "BAD_CMD", f"file={name};reason=key_hash")
            elif c["khash"] in self.seen:
                self.report(c["khash"], "DUPLICATE", "file=" + name)
            else:
                self.process_entry(c, c["khash"])
            if os.path.exists(src):
                os.replace(src, self.path("done", name))

    def write_heartbeat(self):
        gate = self.new_entries_allowed()
        self.write_atomic(self.path(), "hb_ea.txt", f"t_ms={self.now_ms()}\ndry_run={int(self.DryRun)}\nnew_gate={gate or 'open'}\n"
                                                    f"own_position_id={self.pos.posId if self.hasPos else 0}\ncritical={int(self.critical)}\n"
                                                    f"unknown={self.unknownKey}\n", True)

    # -- events -----------------------------------------------------------------------------------------------------
    def on_init(self):
        if not self.is_demo():
            return "INIT_FAILED:not_demo"
        for sub in ("", "cmd", "rpt", "done", "ask", "ans"):
            os.makedirs(self.path(sub), exist_ok=True)
        lk = os.path.abspath(self.path("ea.lock"))
        if lk in _HELD_LOCKS:
            return "INIT_FAILED:lock"
        _HELD_LOCKS.add(lk)
        self.lock = lk
        a = self.t.account
        self.journalPath = self.path(f"journal_{a['login']}_{re.sub(r'[^0-9A-Za-z-]', '_', a['server'])}_{self.Magic}.txt")
        why = self.verify_environment()
        self.envOk = why == ""
        self.journal("", "START", f"dry_run={int(self.DryRun)};new_entries={int(self.AllowNewEntries)};env={'ok' if self.envOk else why};"
                                  f"server={a['server']};symbol={self.Symbol};unapproved={self.unapproved()}")
        self.reconcile()
        self.envOk = self.verify_environment() == ""
        self.ready = True
        return "INIT_SUCCEEDED"

    def on_deinit(self, crash=False):
        if self.lock:
            if not crash:
                self.journal("", "STOP", "reason=0")
            _HELD_LOCKS.discard(self.lock)
            self.lock = None

    def on_timer(self):
        why = self.verify_environment()
        env = why == ""
        if env != self.envOk:
            self.envOk = env
            self.journal("", "ENV_OK" if env else "ENV_LOST", "reason=" + why)
        self.check_resume()
        self.check_resolve_unknown()
        self.manage_own()
        self.poll_commands()
        self.write_heartbeat()

    def on_trade_transaction(self, deal, order, position, price, volume):
        """recorded only (the deal / position check stays the source of truth)."""
        self.journal(self.inflightKey or (self.pos.key if self.hasPos else ""), "TX_DEAL",
                     f"deal={deal};order={order};position={position};price={price:.5f};volume={volume:.2f}")

    # -- test helpers -----------------------------------------------------------------------------------------------
    def states(self, key=None):
        return [p[2] for p in self.journal_lines() if key is None or p[1] == key]

    def last(self, key, state):
        for p in reversed(self.journal_lines()):
            if p[1] == key and p[2] == state:
                return dict(x.split("=", 1) for x in p[3].split(";") if x.find("=") > 0)
        return None
