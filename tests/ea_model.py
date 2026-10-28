"""Python reference model of automation/xau_short/ea/XauShortDemoEA.mq5 (stage 3) + a fake MT5 terminal / broker.

This is NOT the EA: it is a line-by-line port of its decision functions (CheckCmd, CheckDeadline, PrepareOrder, ProcessEntry,
CheckProtection, ManageOwn, TryBreakeven, Reconcile, ReconcileUnknown, CheckResume, PollCommands, OnInit / OnTimer) so that the
rules can be exercised locally against the same file protocol as the bridge (cmd / rpt / done / journal.txt). eam_sim.py checks
that the MQL5 source keeps the same constants, journal states, refusal reasons and gates (static), so a drift between the two is
visible. Passing here proves the RULES, not the MQL5 code: the MQL5 compile and the MT5 demo run are separate evidence.
"""
import hashlib
import math
import os

RISK_FRACTION = 0.03
MAX_AGE_SEC = 60
MAX_DEV_FRAC = 0.20
MAX_SPREAD = 0.50
BE_DIST = 15.0
BAR_SEC = 300
CMD_VERSION = "1"

DONE, DONE_PARTIAL, PLACED, ERROR, TIMEOUT, CONNECTION = 10009, 10010, 10008, 10011, 10012, 10031
DEFINITE_REJECT = {   # TRADE_RETCODE_* listed in IsDefiniteReject()
    "REQUOTE": 10004, "REJECT": 10006, "CANCEL": 10007, "INVALID": 10013, "INVALID_VOLUME": 10014, "INVALID_PRICE": 10015,
    "INVALID_STOPS": 10016, "TRADE_DISABLED": 10017, "MARKET_CLOSED": 10018, "NO_MONEY": 10019, "PRICE_CHANGED": 10020,
    "PRICE_OFF": 10021, "INVALID_EXPIRATION": 10022, "TOO_MANY_REQUESTS": 10024, "SERVER_DISABLES_AT": 10026,
    "CLIENT_DISABLES_AT": 10027, "INVALID_FILL": 10030, "LIMIT_ORDERS": 10033, "LIMIT_VOLUME": 10034, "LIMIT_POSITIONS": 10040,
    "SHORT_ONLY": 10042, "LONG_ONLY": 10043, "FIFO_CLOSE": 10045, "HEDGE_PROHIBITED": 10046}

_TICK = [0]


def _tick():
    """GetTickCount(): milliseconds since the PC started (moves on between two EA instances)."""
    _TICK[0] += 1
    return _TICK[0] % 10**10


_HELD_LOCKS = set()     # FileOpen(ea.lock, FILE_WRITE) without FILE_SHARE_*: exclusive while the handle is open


def sha16(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


class FakeTerminal:
    """the parts of the MT5 terminal / XS demo server the EA reads or writes; every trade write is logged in `writes`."""

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
        self.positions = {}          # ticket -> dict
        self.orders = {}             # pending orders (manual / other EA)
        self.deals = {}              # deal ticket -> dict
        self.rates = []              # M5 bars (server time open, low)
        self.writes = []             # every trade API write: (kind, request)
        self.send_mode = "fill"      # fill | partial | reject:<code> | timeout | fill_lost_reply | fill_no_sl | placed
        self.modify_mode = "ok"      # ok | reject
        self.close_mode = "ok"       # ok | reject
        self.check_ok = True
        self.calc_profit_ok = True
        self.calc_margin_ok = True
        self.next_ticket = 5000

    # time
    def time_gmt(self):
        return self.gmt_ms // 1000

    def time_server(self):
        return self.gmt_ms // 1000 + self.server_offset

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

    # trade API
    def order_send(self, req):
        self.writes.append(("send", dict(req)))
        mode = self.send_mode
        if mode.startswith("reject:"):
            return False, dict(retcode=int(mode.split(":")[1]), order=0, deal=0, price=0.0, volume=0.0)
        if mode == "timeout":
            return False, dict(retcode=TIMEOUT, order=0, deal=0, price=0.0, volume=0.0)
        if mode == "placed":
            return True, dict(retcode=PLACED, order=self._ticket(), deal=0, price=0.0, volume=0.0)
        vol = req["volume"] / 2 if mode == "partial" else req["volume"]
        vol = round(math.floor(vol / self.sym["vstep"] + 1e-9) * self.sym["vstep"], 8)
        order, deal = self._ticket(), self._ticket()
        price = self.bid
        pos = dict(ticket=order, symbol=req["symbol"], magic=req["magic"], comment=req["comment"], type="SELL", volume=vol,
                   price_open=price, sl=0.0 if mode == "fill_no_sl" else req["sl"], tp=req["tp"], time=self.time_server(),
                   time_msc=self.gmt_ms + self.server_offset * 1000)
        self.positions[order] = pos
        self.deals[deal] = dict(position=order, price=price, time=self.time_server(), entry="IN")
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
        if self.close_mode != "ok":
            return False, dict(retcode=DEFINITE_REJECT["REJECT"])
        self.close_position(req["position"], self.ask, "EXPERT")
        return True, dict(retcode=DONE)

    def close_position(self, ticket, price, reason):
        p = self.positions.pop(ticket)
        d = self._ticket()
        self.deals[d] = dict(position=ticket, price=price, time=self.time_server(), entry="OUT", reason=reason,
                             profit=(p["price_open"] - price) * p["volume"] * self.sym["contract"] * self.usdjpy, commission=0.0, swap=0.0)

    def history_out_deal(self, ticket):
        for d, v in sorted(self.deals.items(), reverse=True):
            if v["position"] == ticket and v["entry"] == "OUT":
                return d, v
        return None, None


class Pos:
    def __init__(self):
        self.key = self.khash = ""
        self.posTicket = self.orderTicket = self.dealTicket = 0
        self.fill = self.sl0 = self.tp0 = self.volume = 0.0
        self.fillTimeSrv = 0
        self.tpSet = self.beDone = self.tracked = self.bePending = False
        self.minBid = 0.0
        self.lastBarDone = 0
        self.lastTpTry = 0


class EA:
    """inputs as keyword arguments (same names as the MQL5 inputs without the Inp prefix)."""

    def __init__(self, term, exchange_root, DryRun=True, AllowNewEntries=False, ExpectedLogin=0, ExpectedServer="XSFintech-DEMO",
                 Symbol="XAUUSDs", ExpectedCurrency="JPY", ExpectedSid="XAU-SHORT|XA-23|AU-2",
                 ExpectedCfgSha="72fa9868a3e196ebcd02e37a12f82416d1149e5bd0567d8bf426e2c49f4695ee", ExpectedTvSym="OANDA:XAUUSD",
                 Magic=26102801, FillBarBe="TICKS_SINCE_FILL"):
        self.t = term
        self.root = exchange_root
        self.DryRun, self.AllowNewEntries, self.ExpectedLogin = DryRun, AllowNewEntries, ExpectedLogin
        self.ExpectedServer, self.Symbol, self.ExpectedCurrency = ExpectedServer, Symbol, ExpectedCurrency
        self.ExpectedSid, self.ExpectedCfgSha, self.ExpectedTvSym, self.Magic = ExpectedSid, ExpectedCfgSha, ExpectedTvSym, Magic
        self.FillBarBe = FillBarBe
        self.pos = Pos()
        self.hasPos = self.envOk = self.ready = self.haltNew = self.critical = self.dryMgmtNoted = False
        self.haltReason = self.inflightKey = ""
        self.lock = None
        self.rptSeq = 0
        self.seen = set()
        self.journal_fail = False      # test hook: the journal file cannot be written
        self.started = False

    # -- files ------------------------------------------------------------------------------------------------------
    def path(self, *p):
        return os.path.join(self.root, *p)

    def now_ms(self):
        return self.t.time_gmt() * 1000

    def now_ms_late(self):
        return self.t.time_gmt() * 1000 + 999

    @staticmethod
    def sanitize(s):
        return s.replace("\n", " ").replace("\r", " ").replace("|", "/")

    def report(self, key, state, fields):
        lines = [f"t_ms={self.now_ms()}", f"key_hash={self.sanitize(key)}", f"state={state}"]
        lines += [self.sanitize(p) for p in fields.split(";") if p.find("=") > 0]
        for _ in range(5):                         # FileMove without FILE_REWRITE: an existing name is never overwritten
            self.rptSeq += 1
            base = f"{self.now_ms():013d}_{self.rptSeq:08d}_{_tick():010d}"
            tmp = self.path("rpt", base + ".tmp")
            with open(tmp, "w", encoding="ascii", errors="replace", newline="\r\n") as f:
                f.write("\n".join(lines) + "\n")
            dst = self.path("rpt", base + ".rpt")
            if not os.path.exists(dst) and not os.path.exists(self.path("rpt_done", base + ".rpt")):
                os.replace(tmp, dst)
                return
            os.remove(tmp)

    def journal(self, key, state, fields):
        line = f"{self.now_ms()}|{self.sanitize(key)}|{state}|{self.sanitize(fields)}"
        if self.journal_fail:
            self.critical = True
            return
        with open(self.path("journal.txt"), "a", encoding="ascii", errors="replace", newline="\r\n") as f:
            f.write(line + "\n")
        if key:
            self.seen.add(key)
        self.report(key, state, fields)

    def journal_lines(self):
        try:
            with open(self.path("journal.txt"), encoding="ascii") as f:
                return [l.rstrip("\r\n").split("|", 3) for l in f if l.strip()]
        except FileNotFoundError:
            return []

    def halt_new(self, reason):
        if not self.haltNew:
            self.haltNew = True
            self.haltReason = reason
            self.journal("", "HALT_NEW", "reason=" + reason)

    def halt_file_exists(self):
        return os.path.exists(self.path("halt_new"))

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
        return ""

    def trade_writes_allowed(self):
        if self.DryRun or not self.envOk or not self.ready or not self.is_demo():
            return False
        return self.t.account["login"] == self.ExpectedLogin and self.t.account["server"] == self.ExpectedServer

    def new_entries_allowed(self):
        if self.DryRun:
            return "dry_run"
        if not self.AllowNewEntries:
            return "new_entries_off"
        if not self.trade_writes_allowed():
            return "trade_writes_not_allowed"
        if self.critical:
            return "critical"
        if self.haltNew:
            return "halt_new:" + self.haltReason
        if self.halt_file_exists():
            return "halt_file"
        if self.inflightKey:
            return "in_flight:" + self.inflightKey
        return ""

    # -- command ----------------------------------------------------------------------------------------------------
    @staticmethod
    def read_cmd(path):
        c = dict(v="", key="", khash="", tid="", ev="", side="", otype="", path="", cfg="", sid="", sym="", px=0.0, sl=0.0, tp=0.0,
                 barCloseMs=0)
        names = {"key_hash": "khash", "cfg_sha256": "cfg", "bar_close_ms": "barCloseMs"}
        with open(path, encoding="ascii", errors="replace") as f:
            for line in f:
                line = line.rstrip("\r\n")
                p = line.find("=")
                if p <= 0:
                    continue
                k, v = line[:p], line[p + 1:]
                k = names.get(k, k)
                if k in ("px", "sl", "tp"):
                    try:
                        c[k] = float(v)          # StringToDouble: "nan" / "inf" stay non-finite and are refused by CheckCmd
                    except ValueError:
                        c[k] = 0.0
                elif k == "barCloseMs":
                    try:
                        c[k] = int(v)
                    except ValueError:
                        c[k] = 0
                elif k in c:
                    c[k] = v
        return c

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

    # -- trade wrappers ---------------------------------------------------------------------------------------------
    def find_tagged_position(self, khash):
        for tk, p in sorted(self.t.positions.items(), reverse=True):
            if p["symbol"] == self.Symbol and p["magic"] == self.Magic and p["comment"] == "XSD:" + khash:
                return tk
        return 0

    def confirm_fill(self, key, khash, order, deal, sl0, tp0):
        pos_id = 0
        if deal and deal in self.t.deals:
            pos_id = self.t.deals[deal]["position"]
        if not pos_id:
            pos_id = self.find_tagged_position(khash)
        p = self.t.positions.get(pos_id)
        if not p or p["symbol"] != self.Symbol or p["magic"] != self.Magic or p["type"] != "SELL":
            return False
        P = self.pos = Pos()
        P.key, P.khash, P.posTicket, P.orderTicket, P.dealTicket = key, khash, pos_id, order, deal
        P.fill, P.volume, P.sl0, P.tp0, P.fillTimeSrv = p["price_open"], p["volume"], sl0, tp0, p["time"]
        P.tracked, P.minBid = True, P.fill
        self.hasPos = True
        self.journal(key, "FILLED", f"order={order};deal={deal};position={pos_id};fill_price={P.fill:.5f};volume={P.volume:.2f};"
                                    f"sl0={sl0:.5f};tp0={tp0:.5f};fill_time={P.fillTimeSrv}")
        return True

    def close_position(self, key, reason):
        if not self.trade_writes_allowed() or not self.hasPos or self.pos.posTicket not in self.t.positions:
            return False
        p = self.t.positions[self.pos.posTicket]
        req = dict(action="DEAL", symbol=self.Symbol, type="BUY", position=self.pos.posTicket, volume=p["volume"], price=self.t.ask,
                   magic=self.Magic, comment="XSD:" + self.pos.khash + ":C")
        self.journal(key, "CLOSE_PRE_SEND", f"reason={reason};position={self.pos.posTicket}")
        ok, res = self.t.order_send_close(req)
        good = ok and res["retcode"] in (DONE, DONE_PARTIAL)
        self.journal(key, "CLOSE_SENT" if good else "CLOSE_FAILED", f"reason={reason};retcode={res['retcode']}")
        return good

    def modify_own(self, what, new_sl, new_tp):
        if not self.trade_writes_allowed() or not self.hasPos or self.pos.posTicket not in self.t.positions:
            return False
        cur_sl = self.t.positions[self.pos.posTicket]["sl"]
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
        self.journal(id_, "SEEN", f"tid={c['tid']};bar_close_ms={c['barCloseMs']}")
        why = self.check_cmd(c)
        if not why:
            why = self.check_deadline(c)
        gate = ""
        if not why:
            gate = self.new_entries_allowed()
            if gate and gate not in ("dry_run", "new_entries_off"):
                why = gate
        detail, req = "", None
        if not why:
            why, req, detail = self.prepare_order(c)
        if why:
            self.journal(id_, "SKIPPED", "reason=" + why)
            return
        if gate in ("dry_run", "new_entries_off"):
            self.journal(id_, "DRY_RUN_NOT_SENT", f"gate={gate};{detail}")
            return
        self.journal(id_, "DECIDED", detail)
        if self.before_send_hook:
            self.before_send_hook()
        why = self.check_deadline(c)
        if not why and not self.trade_writes_allowed():
            why = "trade_writes_not_allowed"
        if why:
            self.journal(id_, "SKIPPED", f"reason={why};stage=right_before_send")
            return
        self.inflightKey = id_
        self.journal(id_, "PRE_SEND", f"volume={req['volume']:.2f};sl={req['sl']:.5f};price={req['price']:.5f}")
        if self.crash_after_pre_send:
            raise SystemExit("simulated crash after PRE_SEND")
        ok, res = self.t.order_send(req)
        self.journal(id_, "SEND_RETURNED", f"ok={int(ok)};retcode={res['retcode']};order={res['order']};deal={res['deal']};"
                                           f"fill_price={res['price']:.5f};volume={res['volume']:.2f}")
        if res["retcode"] in (DONE, DONE_PARTIAL):
            if self.confirm_fill(id_, c["khash"], res["order"], res["deal"], req["sl"], c["tp"]):
                self.inflightKey = ""
                if res["retcode"] == DONE_PARTIAL:
                    self.journal(id_, "PARTIAL_FILL", f"volume={self.pos.volume:.2f};requested={req['volume']:.2f}")
                self.check_protection()
                return
            self.journal(id_, "UNKNOWN", "reason=done_but_fill_not_confirmed")
            self.halt_new("unknown_result:" + c["khash"])
            return
        if not ok and res["retcode"] in DEFINITE_REJECT.values():
            self.inflightKey = ""
            self.journal(id_, "REJECTED", f"retcode={res['retcode']}")
            return
        self.journal(id_, "UNKNOWN", f"retcode={res['retcode']}")
        self.halt_new("unknown_result:" + c["khash"])

    before_send_hook = None
    crash_after_pre_send = False

    def check_protection(self):
        if not self.hasPos or self.pos.posTicket not in self.t.positions:
            return
        sl = self.t.positions[self.pos.posTicket]["sl"]
        if sl > 0 and abs(sl - self.pos.sl0) <= self.t.sym["tick"] * 0.5 + 1e-9:
            self.journal(self.pos.key, "PROTECTED", f"sl={sl:.5f}")
            return
        self.halt_new("initial_sl_missing")
        self.journal(self.pos.key, "SL_MISSING", f"sl_on_position={sl:.5f}")
        if self.close_position(self.pos.key, "emergency_initial_sl_missing"):
            self.journal(self.pos.key, "EMERGENCY_CLOSE", "result=sent")
        else:
            self.critical = True
            self.journal(self.pos.key, "CRITICAL", "reason=emergency_close_failed")

    # -- management -------------------------------------------------------------------------------------------------
    def manage_own(self):
        if not self.hasPos:
            return
        P, t = self.pos, self.t
        if P.posTicket not in t.positions:
            d, v = t.history_out_deal(P.posTicket)
            if d:
                self.journal(P.key, "CLOSED", f"reason={v['reason'].lower()};deal={d};price={v['price']:.5f};profit={v['profit']:.0f};"
                                              f"commission={v['commission']:.0f};swap={v['swap']:.0f}")
            else:
                self.journal(P.key, "CLOSED", "reason=not_found_in_history")
            self.hasPos = False
            return
        if P.tracked and t.bid > 0:
            P.minBid = min(P.minBid, t.bid)
        if not self.trade_writes_allowed():
            if not self.dryMgmtNoted:
                self.dryMgmtNoted = True
                self.journal(P.key, "MANAGEMENT_BLOCKED", "reason=trade_writes_not_allowed;note=the_server_side_sl_stays")
            return
        self.dryMgmtNoted = False
        now = t.time_server()
        fill_bar_open = P.fillTimeSrv - P.fillTimeSrv % BAR_SEC
        if now < fill_bar_open + BAR_SEC:
            return
        digits = t.sym["digits"]
        if not P.tpSet and (P.lastTpTry == 0 or now - now % BAR_SEC > P.lastTpTry - P.lastTpTry % BAR_SEC):
            P.lastTpTry = now
            if not (P.sl0 - P.fill > 0 and P.fill - P.tp0 > 0):
                self.journal(P.key, "FILL_SIDE_BAD", f"fill={P.fill:.{digits}f}")
                self.close_position(P.key, "bad_fill_side_mt5")
                return
            cur_sl = t.positions[P.posTicket]["sl"]
            if self.modify_own("tp0", cur_sl, round(P.tp0, digits)):
                P.tpSet = True
                self.journal(P.key, "TP_SET", f"tp={P.tp0:.{digits}f};sl_kept={cur_sl:.{digits}f}")
        if P.lastBarDone == 0:
            if not P.beDone and self.FillBarBe == "TICKS_SINCE_FILL" and P.tracked:
                self.try_breakeven(P.minBid, fill_bar_open)
            P.lastBarDone = fill_bar_open
        if P.beDone:
            return
        frm = P.lastBarDone + BAR_SEC
        for (bt, low) in sorted(t.rates):
            if P.beDone:
                break
            if bt < frm or bt > now or bt + BAR_SEC > now:
                continue
            self.try_breakeven(low, bt)
            P.lastBarDone = bt

    def try_breakeven(self, fav_low, bar_open):
        P = self.pos
        if P.beDone or (fav_low <= 0 and not P.bePending):
            return
        if P.bePending or P.fill - fav_low >= BE_DIST - 1e-9:
            P.bePending = True
            digits = self.t.sym["digits"]
            new_sl = round(P.fill, digits)
            cur_tp = self.t.positions[P.posTicket]["tp"]
            if self.modify_own("breakeven", new_sl, cur_tp):
                P.beDone, P.bePending = True, False
                self.journal(P.key, "BE_SET", f"sl={new_sl:.{digits}f};bar_open={bar_open};fav={fav_low:.{digits}f}")

    # -- startup reconciliation -------------------------------------------------------------------------------------
    def reconcile(self):
        last_pre_send, pre_send_ms = "", 0
        pos_ticket, pos_key, sl0, tp0, fill, fill_time, closed = 0, "", 0.0, 0.0, 0.0, 0, False
        for parts in self.journal_lines():
            if len(parts) < 4:
                continue
            key, st, f = parts[1], parts[2], parts[3]
            if key:
                self.seen.add(key)
            if st == "HALT_NEW":
                self.haltNew, self.haltReason = True, f
            if st == "RESUME_NEW":
                self.haltNew, self.haltReason, last_pre_send = False, "", ""
            if st == "CRITICAL_CLEARED":
                self.critical = False
            if st == "PRE_SEND":
                last_pre_send, pre_send_ms = key, int(parts[0])
            if st in ("REJECTED", "FILLED") and key == last_pre_send:
                last_pre_send = ""
            if st == "FILLED":
                pos_key, closed = key, False
                kv = dict(x.split("=", 1) for x in f.split(";") if x.find("=") > 0)
                pos_ticket = int(kv.get("position", 0))
                sl0, tp0, fill = float(kv.get("sl0", 0)), float(kv.get("tp0", 0)), float(kv.get("fill_price", 0))
                fill_time = int(kv.get("fill_time", 0))
            if st == "CLOSED" and key == pos_key:
                closed = True
            if st == "CRITICAL":
                self.critical = True
        if last_pre_send:
            self.inflightKey = last_pre_send
            self.halt_new("unknown_result_after_restart")
            self.journal(last_pre_send, "UNKNOWN", "reason=pre_send_without_result_at_startup")
        if pos_key and not closed and pos_ticket > 0:
            p = self.t.positions.get(pos_ticket)
            P = self.pos = Pos()
            P.key = P.khash = pos_key
            P.posTicket = pos_ticket
            self.hasPos = True
            if p and p["symbol"] == self.Symbol and p["magic"] == self.Magic:
                P.sl0, P.tp0, P.fill, P.fillTimeSrv, P.volume = sl0, tp0, fill, fill_time, p["volume"]
                P.tpSet = p["tp"] > 0
                P.beDone = abs(p["sl"] - fill) <= self.t.sym["tick"] * 0.5 + 1e-9
                P.tracked, P.minBid = False, fill
                self.journal(pos_key, "OWNED_AT_STARTUP", f"position={pos_ticket}")
        if self.inflightKey:
            self.reconcile_unknown(self.inflightKey, pre_send_ms)

    def reconcile_unknown(self, key, pre_send_ms):
        for tk, p in self.t.positions.items():
            if p["magic"] == self.Magic and p["symbol"] == self.Symbol and p["comment"] == "XSD:" + key \
                    and p["time_msc"] - (self.t.time_server() - self.t.time_gmt()) * 1000 >= pre_send_ms - 60000:
                self.journal(key, "RECONCILED", f"position={tk};note=found_open_after_unknown;comment={p['comment']};"
                                                "new_entries=still_halted_until_resume")
                return
        self.journal(key, "UNKNOWN_NOT_FOUND", "note=no_open_position_with_magic_and_tag;new_entries=still_halted_until_resume")

    def check_resume(self):
        fc = self.path("clear_critical")
        if os.path.exists(fc):
            os.remove(fc)
            if self.critical:
                self.critical = False
                self.journal("", "CRITICAL_CLEARED", "by=operator_file;note=new_entries_stay_halted_until_resume_new")
                self.halt_new("after_critical")
        f = self.path("resume_new")
        if not os.path.exists(f):
            return
        os.remove(f)
        if self.critical:
            self.journal("", "RESUME_REFUSED", "reason=critical")
            return
        self.inflightKey = ""
        self.haltNew, self.haltReason = False, ""
        self.journal("", "RESUME_NEW", "by=operator_file")

    def poll_commands(self):
        d = self.path("cmd")
        for name in sorted(n for n in os.listdir(d) if n.endswith(".cmd")):
            src = os.path.join(d, name)
            try:
                c = self.read_cmd(src)
            except OSError:
                c = None
            if c is None:
                self.journal("", "BAD_CMD", f"file={name};reason=unreadable")
            elif not c["khash"] or sha16(c["key"]) != c["khash"]:
                self.journal("", "BAD_CMD", f"file={name};reason=key_hash")
            elif c["khash"] in self.seen:
                self.report(c["khash"], "DUPLICATE", "file=" + name)
            else:
                self.process_entry(c, c["khash"])
            os.replace(src, self.path("done", name))

    # -- events -----------------------------------------------------------------------------------------------------
    def on_init(self):
        if not self.is_demo():
            return "INIT_FAILED:not_demo"
        for sub in ("", "cmd", "rpt", "done"):
            os.makedirs(self.path(sub), exist_ok=True)
        lk = os.path.abspath(self.path("ea.lock"))
        if lk in _HELD_LOCKS:
            return "INIT_FAILED:lock"
        _HELD_LOCKS.add(lk)
        self.lock = lk
        why = self.verify_environment()
        self.envOk = why == ""
        self.journal("", "START", f"dry_run={int(self.DryRun)};new_entries={int(self.AllowNewEntries)};env={'ok' if self.envOk else why};"
                                  f"server={self.t.account['server']};symbol={self.Symbol}")
        self.reconcile()
        self.ready = True
        self.started = True
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
        self.manage_own()
        self.poll_commands()

    def on_trade_transaction(self, deal, order, position, price, volume):
        """recorded only (the deal / position check stays the source of truth)."""
        self.journal(self.inflightKey or (self.pos.key if self.hasPos else ""), "TX_DEAL",
                     f"deal={deal};order={order};position={position};price={price:.5f};volume={volume:.2f}")

    def on_tick(self):
        if self.hasPos and self.pos.tracked and self.t.bid > 0:
            self.pos.minBid = min(self.pos.minBid, self.t.bid)

    # -- test helpers -----------------------------------------------------------------------------------------------
    def states(self, key=None):
        return [p[2] for p in self.journal_lines() if key is None or p[1] == key]

    def last(self, key, state):
        for p in reversed(self.journal_lines()):
            if p[1] == key and p[2] == state:
                return dict(x.split("=", 1) for x in p[3].split(";") if x.find("=") > 0)
        return None
