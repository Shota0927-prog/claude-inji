"""EAM fixtures — the demo EA rules (stage 3) on the Python reference model tests/ea_model.py + static checks of the MQL5 source
automation/xau_short/ea/XauShortDemoEA.mq5 (the model and the source must keep the same constants / states / reasons / gates).

  EAM-01..04 : demo only (real account refused at start, every expected value checked, login 0 = no writes), DRY_RUN = zero trade
               writes, new-entries OFF / halt file stop new entries only (own-position protection continues)
  EAM-05..10 : deadline 60 s (1 s clock resolution: never late, never negative), right before the send; price deviation 20 %, spread
               0.50; lot from 3 % of the balance via OrderCalcProfit, step floor, min / max lot, margin, SL rounded never widened
  EAM-11..16 : max one (manual / other EA / pending / in flight), rejects, unknown results, crash after PRE_SEND, reply lost, restart
  EAM-17..25 : initial SL missing -> emergency close (failure -> CRITICAL), TP0 at the fill-bar close only, TP / SL change rejected,
               breakeven 15 USD from the XS fill on closed M5 bars (no pre-fill low), never loosen, TradingView exits never reach the EA
  EAM-26..31 : restart with an own position, two EA instances, bad / duplicate / LIMIT commands, partial fill, environment lost,
               DRY_RUN blocks own-position management too
  EAS-01..08 : the MQL5 source (static): inputs, constants, the only OrderSend sites and their gates, journal states, refusal
               reasons, definite-reject list and the bridge's state map all match the model
Evidence class: local Python only. The MQL5 EA itself is NOT compiled or run here (no MetaEditor / MT5 in this environment).
"""
import hashlib
import math
import os
import re
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MQ5 = os.path.join(ROOT, "automation", "xau_short", "ea", "XauShortDemoEA.mq5")
sys.path.insert(0, os.path.join(ROOT, "automation", "xau_short", "bridge"))
import ea_model as em            # noqa: E402
import ea_bridge as eb           # noqa: E402

RESULTS = []
SID = "XAU-SHORT|XA-23|AU-2"
CFG = "72fa9868a3e196ebcd02e37a12f82416d1149e5bd0567d8bf426e2c49f4695ee"
BC = 1793064000000                  # an M5 bar close (UTC ms)
LOGIN = 1234567


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


class Box:
    """one exchange folder + terminal + EA."""

    def __init__(self, **ea_kw):
        self.tmp = tempfile.mkdtemp(prefix="eam_")
        self.x = os.path.join(self.tmp, "XauShortDemo")
        self.t = em.FakeTerminal(gmt_ms=BC + 2500)
        self.t.bid, self.t.ask = 2600.2, 2600.5
        kw = dict(DryRun=False, AllowNewEntries=True, ExpectedLogin=LOGIN)
        kw.update(ea_kw)
        self.kw = kw
        self.ea = em.EA(self.t, self.x, **kw)
        self.init = self.ea.on_init()
        self.n = 0

    def cmd(self, bc=BC, px=2600.0, sl=2605.0, tp=2592.5, otype="MARKET", ev="ENTRY", path="SATS_NOW", key=None, khash=None, **over):
        key = key or f"{SID}|{ev}|T{bc}|{bc}"
        kh = khash if khash is not None else hashlib.sha256(key.encode()).hexdigest()[:16]
        f = dict(v="1", key=key, key_hash=kh, tid=f"T{bc}", ev=ev, side="SHORT", otype=otype, path=path, px=repr(px), sl=repr(sl),
                 tp=repr(tp), bar_close_ms=str(bc), cfg_sha256=CFG, sid=SID, sym="OANDA:XAUUSD", received_ms=str(bc + 1000),
                 claimed_ms=str(bc + 1500))
        f.update(over)
        self.n += 1
        os.makedirs(os.path.join(self.x, "cmd"), exist_ok=True)
        name = f"{bc}_{kh or 'nohash'}_{self.n:03d}.cmd"
        with open(os.path.join(self.x, "cmd", name), "w", encoding="ascii", newline="\n") as fh:
            fh.write("".join(f"{k}={v}\n" for k, v in f.items()))
        return kh

    def restart(self, crash=False, **kw):
        self.ea.on_deinit(crash=crash)
        k = dict(self.kw)
        k.update(kw)
        self.ea = em.EA(self.t, self.x, **k)
        self.init = self.ea.on_init()
        return self.ea

    def sends(self):
        return [w for w in self.t.writes if w[0] == "send"]

    def touch(self, name):
        open(os.path.join(self.x, name), "w").close()

    def close(self):
        self.ea.on_deinit()
        shutil.rmtree(self.tmp, ignore_errors=True)


def fill(box, **kw):
    """one filled own position via a valid command."""
    kh = box.cmd(**kw)
    box.ea.on_timer()
    return kh


def gate_env():
    b = Box()
    t = b.t
    real = em.FakeTerminal(gmt_ms=BC)
    real.account["trade_mode"] = "REAL"
    tmp = tempfile.mkdtemp()
    r = em.EA(real, os.path.join(tmp, "x"), DryRun=False, AllowNewEntries=True, ExpectedLogin=LOGIN).on_init()
    real.account["trade_mode"] = "CONTEST"
    r2 = em.EA(real, os.path.join(tmp, "y"), DryRun=False, AllowNewEntries=True, ExpectedLogin=LOGIN).on_init()
    check("EAM-01 a real (or contest) account is refused at start (INIT_FAILED, no folder / journal written); no input can allow it",
          r == "INIT_FAILED:not_demo" and r2 == "INIT_FAILED:not_demo" and not os.path.exists(os.path.join(tmp, "x")), str((r, r2)))
    shutil.rmtree(tmp, ignore_errors=True)
    b.close()
    res = {}
    for nm, mut, kw in (("login0", None, dict(ExpectedLogin=0)), ("login", ("login", 999), {}), ("server", ("server", "XSFintech-Live"), {}),
                        ("currency", ("currency", "USD"), {}), ("netting", ("margin_mode", "NETTING"), {}), ("symbol", None, dict(Symbol="XAUUSD"))):
        b = Box(**kw)
        if mut:
            b.t.account[mut[0]] = mut[1]
            b.restart()
        kh = b.cmd()
        b.ea.on_timer()
        res[nm] = (b.ea.envOk, b.ea.last(kh, "SKIPPED"), len(b.t.writes))
        b.close()
    check("EAM-02 demo environment checked at start and on every timer: expected login not set (0) / login / server / currency / netting "
          "account / symbol mismatch -> env not ok -> the valid ENTRY is SKIPPED trade_writes_not_allowed with ZERO trade writes",
          all(v[0] is False and v[1] == {"reason": "trade_writes_not_allowed"} and v[2] == 0 for v in res.values()), str(res))
    b = Box(DryRun=True, AllowNewEntries=False)
    d = em.EA.__init__.__defaults__
    kh = b.cmd()
    b.ea.on_timer()
    dr = b.ea.last(kh, "DRY_RUN_NOT_SENT")
    check("EAM-03 DRY_RUN (the default: DryRun=True, AllowNewEntries=False, ExpectedLogin=0): the ENTRY is fully checked and the lot computed "
          "(volume / budget / planned loss / margin in the journal) but DRY_RUN_NOT_SENT with ZERO trade API writes",
          d[:3] == (True, False, 0) and dr is not None and dr["gate"] == "dry_run" and float(dr["volume"]) > 0 and "budget_jpy" in dr
          and b.t.writes == [], str(dr))
    b.close()
    b = Box(AllowNewEntries=False)
    kh = b.cmd()
    b.ea.on_timer()
    off = (b.ea.last(kh, "DRY_RUN_NOT_SENT") or {}).get("gate")
    b.close()
    b = Box()
    kh = fill(b)
    b.touch("halt_new")
    kh2 = b.cmd(bc=BC + 300000)
    b.t.gmt_ms = BC + 300000 + 2000
    b.ea.on_timer()
    skipped = b.ea.last(kh2, "SKIPPED")
    tp_set = b.ea.last(kh, "TP_SET")
    check("EAM-04 the stop switches are not DRY_RUN: AllowNewEntries=false -> DRY_RUN_NOT_SENT (gate new_entries_off), no send; the halt_new "
          "file stops NEW entries (SKIPPED halt_file) while the own position is still protected (TP0 set at the fill-bar close)",
          off == "new_entries_off" and skipped == {"reason": "halt_file"} and tp_set is not None and len(b.sends()) == 1, str((off, skipped, tp_set)))
    b.close()


def gate_deadline():
    res = {}
    for nm, at in (("59.5", 59500), ("59.999", 59999), ("60.0", 60000), ("61", 61000), ("future-0.5", -500), ("future-0.001", -1), ("0.3", 300)):
        b = Box(DryRun=True)
        b.t.gmt_ms = BC + at
        kh = b.cmd()
        b.ea.on_timer()
        res[nm] = (b.ea.last(kh, "SKIPPED") or {}).get("reason") or ("dry" if b.ea.last(kh, "DRY_RUN_NOT_SENT") else None)
        b.close()
    check("EAM-05 deadline from the ENTRY bar close with TimeGMT's 1 s resolution: up to 59.999 s accepted; 60.0 s and later -> expired "
          "(the latest possible 'now' is used, never late); a bar close in the future even by 1 ms -> clock_or_future_bar (the earliest "
          "possible 'now' is used, a negative age is never 'in time')",
          res == {"59.5": "dry", "59.999": "dry", "60.0": "expired", "61": "expired", "future-0.5": "clock_or_future_bar",
                  "future-0.001": "clock_or_future_bar", "0.3": "dry"}, str(res))
    b = Box()
    b.t.gmt_ms = BC + 58500
    b.ea.before_send_hook = lambda: b.t.advance(2000)      # the checks / journal took time
    kh = b.cmd()
    b.ea.on_timer()
    check("EAM-06 the deadline is re-checked right before OrderSend: checks passed at 58.5 s, 'now' is past 60 s at the send -> SKIPPED "
          "expired (stage right_before_send), no PRE_SEND, zero writes",
          b.ea.last(kh, "SKIPPED") == {"reason": "expired", "stage": "right_before_send"} and "PRE_SEND" not in b.ea.states(kh)
          and b.t.writes == [], str(b.ea.states(kh)))
    b.close()


def gate_price_lot():
    res = {}
    for nm, bid, ask in (("dev_1.00", 2601.0, 2601.3), ("dev_1.01", 2601.01, 2601.31), ("dev_-1.00", 2599.0, 2599.3),
                         ("spread_0.50", 2600.2, 2600.7), ("spread_0.51", 2600.2, 2600.71)):
        b = Box(DryRun=True)
        b.t.bid, b.t.ask = bid, ask
        kh = b.cmd()
        b.ea.on_timer()
        res[nm] = (b.ea.last(kh, "SKIPPED") or {}).get("reason", "ok")
        b.close()
    check("EAM-07 price deviation |Bid - ENTRY.px| <= 20 % of (ENTRY.sl - ENTRY.px) (SL width 5 -> 1.00 allowed, 1.01 refused, both sides); "
          "spread Ask - Bid <= 0.50 USD (0.51 refused)",
          res == {"dev_1.00": "ok", "dev_1.01": "price_deviation:1.010", "dev_-1.00": "ok", "spread_0.50": "ok", "spread_0.51": "spread:0.510"},
          str(res))
    b = Box()
    kh = fill(b)
    req = b.sends()[0][1]
    loss = (req["sl"] - req["price"]) * req["volume"] * 100 * 150
    loss_more = (req["sl"] - req["price"]) * (req["volume"] + 0.01) * 100 * 150
    dec = b.ea.last(kh, "DECIDED")
    check("EAM-08 lot: budget = balance 1,000,000 JPY x 3 % = 30,000; loss per lot from OrderCalcProfit at the XS Bid 2600.20 -> SL 2605.00 "
          "(= 72,000 JPY with the fake 100 oz / 150 JPY) -> 0.41 lot (planned loss 29,520 <= 30,000, 0.42 would exceed); request SELL at the "
          "Bid with the SL, TP 0 (TP0 comes at the fill-bar close), magic, comment XSD:<key hash>, deviation = the remaining 20 % allowance; "
          "the journal shows that the actual loss can exceed 3 %",
          req["volume"] == 0.41 and loss <= 30000 < loss_more and req["sl"] == 2605.0 and req["price"] == 2600.2 and req["tp"] == 0.0
          and req["type"] == "SELL" and req["magic"] == 26102801 and req["comment"] == "XSD:" + kh and req["deviation"] == 80
          and dec["budget_jpy"] == "30000" and dec["planned_loss_jpy"] == "29520" and "can exceed 3%" in dec["note"], str((req, dec)))
    b.close()
    res = {}
    for nm, setup in (("min_lot", lambda t: t.account.update(balance=10000.0)),
                      ("margin", lambda t: t.account.update(margin_free=1000.0)),
                      ("calc_fail", lambda t: setattr(t, "calc_profit_ok", False)),
                      ("margin_fail", lambda t: setattr(t, "calc_margin_ok", False)),
                      ("spec", lambda t: t.sym.update(tick=0.0)),
                      ("max_cap", lambda t: (t.account.update(balance=1e9, margin_free=1e12), t.sym.update(vmax=5.0))),
                      ("no_price", lambda t: setattr(t, "bid", 0.0)),
                      ("session", lambda t: t.sym.update(session_open=False)),
                      ("sym_trade", lambda t: t.sym.update(trade_mode="LONGONLY"))):
        b = Box()
        setup(b.t)
        kh = b.cmd()
        b.ea.on_timer()
        res[nm] = ((b.ea.last(kh, "SKIPPED") or {}).get("reason"), len(b.sends()), b.sends()[0][1]["volume"] if b.sends() else None)
        b.close()
    check("EAM-09 no order when: even the minimum lot exceeds the 3 % budget (below_min_lot), the margin is not free (margin), OrderCalcProfit "
          "/ OrderCalcMargin fail, the symbol spec is invalid (tick 0), there is no price, the XS session is closed, the symbol cannot be sold; a huge budget is capped at the volume maximum",
          res["min_lot"][:2] == ("below_min_lot", 0) and res["margin"][:2] == ("margin", 0) and res["calc_fail"][:2] == ("order_calc_profit_failed", 0)
          and res["max_cap"] == (None, 1, 5.0) and res["no_price"][:2] == ("no_price", 0) and res["session"][:2] == ("outside_trade_session", 0)
          and res["sym_trade"][:2] == ("symbol_sell_not_allowed", 0) and res["margin_fail"][:2] == ("order_calc_margin_failed", 0)
          and res["spec"][:2] == ("symbol_spec", 0), str(res))
    res = {}
    for nm, sl, tick, bid in (("sl_2605.017", 2605.017, 0.01, 2600.2), ("tick_0.05", 2605.03, 0.05, 2600.2)):
        b = Box()
        b.t.sym["tick"] = tick
        b.t.bid, b.t.ask = bid, bid + 0.3
        kh = b.cmd(sl=sl)
        b.ea.on_timer()
        req = b.sends()[0][1]
        res[nm] = (req["sl"], req["volume"], (req["sl"] - req["price"]) * req["volume"] * 15000)
        b.close()
    check("EAM-10 the SL is put on the tick grid DOWNWARDS for a short (2605.017 -> 2605.01, tick 0.05: 2605.03 -> 2605.00: never widened) "
          "and the volume / risk are computed with the final price and SL (loss <= 30,000 JPY)",
          res["sl_2605.017"][0] == 2605.01 and res["tick_0.05"][0] == 2605.0 and all(v[2] <= 30000 for v in res.values()), str(res))


def gate_slot():
    res = {}
    for nm, setup in (("manual_pos", lambda t: t.positions.update({1: dict(ticket=1, symbol="XAUUSDs", magic=0, comment="", type="BUY", volume=0.01,
                                                                           price_open=2600.0, sl=0.0, tp=0.0, time=0, time_msc=0)})),
                      ("other_symbol", lambda t: t.positions.update({2: dict(ticket=2, symbol="EURUSD", magic=7, comment="", type="SELL",
                                                                             volume=0.1, price_open=1.1, sl=0.0, tp=0.0, time=0, time_msc=0)})),
                      ("pending", lambda t: t.orders.update({3: dict(symbol="XAUUSDs")}))):
        b = Box()
        setup(b.t)
        kh = b.cmd()
        b.ea.on_timer()
        res[nm] = ((b.ea.last(kh, "SKIPPED") or {}).get("reason"), len(b.sends()))
        b.close()
    b = Box()
    kh = fill(b)
    kh2 = b.cmd(bc=BC + 300000)
    b.t.gmt_ms = BC + 300000 + 2000
    b.ea.on_timer()
    held = (b.ea.last(kh2, "SKIPPED") or {}).get("reason")
    b.t.close_position(b.ea.pos.posTicket, 2595.0, "TP")
    b.ea.on_timer()
    b.cmd(bc=BC + 300000)                       # the same signal delivered again after the close
    b.ea.on_timer()
    again = b.ea.states(kh2)
    check("EAM-11 max one for the WHOLE account: a manual position, another EA's position on another symbol, a pending order, or the own "
          "position -> the new ENTRY is SKIPPED (max1_*) and never placed later: after the own position closed, the same signal delivered "
          "again is a DUPLICATE (no second SEEN, no send)",
          res == {"manual_pos": ("max1_position_exists", 0), "other_symbol": ("max1_position_exists", 0), "pending": ("max1_pending_order_exists", 0)}
          and held == "max1_position_exists" and again.count("SEEN") == 1 and len(b.sends()) == 1 and "CLOSED" in b.ea.states(kh), str((res, held, again)))
    b.close()
    b = Box()
    b.t.send_mode = "reject:10006"
    kh = fill(b)
    rej = (b.ea.last(kh, "REJECTED"), b.ea.inflightKey, b.ea.haltNew)
    b.t.send_mode = "fill"
    kh2 = b.cmd(bc=BC + 300000)
    b.t.gmt_ms = BC + 300000 + 2000
    b.ea.on_timer()
    check("EAM-12 a definite reject (10006) -> REJECTED, the slot is free again and new entries are not halted: the next ENTRY is sent",
          rej == ({"retcode": "10006"}, "", False) and "PROTECTED" in b.ea.states(kh2) and len(b.sends()) == 2, str(rej))
    b.close()


def gate_unknown():
    b = Box()
    b.t.send_mode = "timeout"
    kh = fill(b)
    st1 = (b.ea.last(kh, "UNKNOWN"), b.ea.inflightKey == kh, b.ea.haltNew)
    b.t.send_mode = "fill"
    kh2 = b.cmd(bc=BC + 300000)
    b.t.gmt_ms = BC + 300000 + 2000
    b.ea.on_timer()
    nxt = (b.ea.last(kh2, "SKIPPED") or {}).get("reason", "")
    b.restart()
    after = (b.ea.haltNew, b.ea.last(kh, "UNKNOWN_NOT_FOUND") is not None)
    kh3 = b.cmd(bc=BC + 600000)
    b.t.gmt_ms = BC + 600000 + 2000
    b.ea.on_timer()
    still = (b.ea.last(kh3, "SKIPPED") or {}).get("reason", "")
    b.touch("resume_new")
    b.ea.on_timer()
    kh4 = b.cmd(bc=BC + 900000)
    b.t.gmt_ms = BC + 900000 + 2000
    b.ea.on_timer()
    check("EAM-13 result unknown (timeout 10012): UNKNOWN, the slot stays occupied and new entries halt (the next ENTRY is SKIPPED, no "
          "re-order); after an EA restart the halt persists (journal) and the reconciliation finds no position (UNKNOWN_NOT_FOUND); only the "
          "operator file resume_new frees it (RESUME_NEW) and the next ENTRY is sent",
          st1[0] == {"retcode": "10012"} and st1[1] and st1[2] and nxt.startswith("halt_new:unknown_result") and after == (True, True)
          and still.startswith("halt_new") and "RESUME_NEW" in b.ea.states("") and "PROTECTED" in b.ea.states(kh4) and len(b.sends()) == 2,
          str((st1, nxt, after, still)))
    b.close()
    b = Box()
    b.ea.crash_after_pre_send = True
    kh = b.cmd()
    try:
        b.ea.on_timer()
    except SystemExit:
        pass
    b.restart(crash=True)
    b.cmd()                                       # the bridge / operator delivers the same command again
    b.ea.on_timer()
    check("EAM-14 crash after the PRE_SEND record (before any send): the restart marks the key UNKNOWN (pre_send_without_result_at_startup), "
          "halts new entries, the re-delivered command is a DUPLICATE: zero sends",
          b.ea.last(kh, "UNKNOWN") == {"reason": "pre_send_without_result_at_startup"} and b.ea.haltNew and b.t.writes == []
          and b.ea.states(kh).count("SEEN") == 1, str(b.ea.states(kh)))
    b.close()
    b = Box()
    b.t.send_mode = "fill_lost_reply"
    kh = fill(b)
    unk = b.ea.last(kh, "UNKNOWN")
    b.restart()
    rec = b.ea.last(kh, "RECONCILED")
    kh2 = b.cmd(bc=BC + 300000)
    b.t.gmt_ms = BC + 300000 + 2000
    b.touch("resume_new")
    b.ea.on_timer()
    check("EAM-15 filled but the reply was lost (10031): UNKNOWN + halt; after a restart the position is FOUND by symbol + magic + the exact "
          "comment XSD:<key hash> + opened after PRE_SEND (RECONCILED) but NOT adopted automatically; even after resume_new the next ENTRY is "
          "blocked by that position (max one), so there is never a second order",
          unk == {"retcode": "10031"} and rec is not None and rec["note"] == "found_open_after_unknown" and not b.ea.hasPos
          and (b.ea.last(kh2, "SKIPPED") or {}).get("reason") == "max1_position_exists" and len(b.sends()) == 1, str((unk, rec)))
    b.close()
    b = Box()
    b.t.send_mode = "placed"
    kh = fill(b)
    check("EAM-16 OrderSend returning true is not a fill: retcode PLACED (no deal / position) -> UNKNOWN + halt, not FILLED",
          "FILLED" not in b.ea.states(kh) and b.ea.last(kh, "UNKNOWN") is not None and b.ea.haltNew, str(b.ea.states(kh)))
    b.close()


def gate_protect():
    b = Box()
    b.t.send_mode = "fill_no_sl"
    kh = fill(b)
    st = b.ea.states(kh)
    closes = [w for w in b.t.writes if w[0] == "close"]
    check("EAM-17 the initial SL is missing on the filled position: SL_MISSING, new entries halt, emergency close of the OWN position (by its "
          "ticket) -> EMERGENCY_CLOSE",
          "SL_MISSING" in st and "EMERGENCY_CLOSE" in st and b.ea.haltNew and len(closes) == 1 and closes[0][1]["position"] == b.ea.pos.posTicket
          and b.ea.pos.posTicket not in b.t.positions, str(st))
    b.close()
    b = Box()
    b.t.send_mode, b.t.close_mode = "fill_no_sl", "reject"
    kh = fill(b)
    crit = (b.ea.critical, b.ea.last(kh, "CRITICAL"))
    b.touch("resume_new")
    b.ea.on_timer()
    refused = "RESUME_REFUSED" in b.ea.states("")
    b.restart()
    persists = b.ea.critical
    b.touch("clear_critical")
    b.ea.on_timer()
    cleared = (b.ea.critical, b.ea.haltNew)
    check("EAM-18 the emergency close also fails: CRITICAL (never reported as success), resume_new is refused, CRITICAL survives a restart; "
          "only the operator file clear_critical clears it and new entries stay halted until resume_new",
          crit[0] and crit[1] == {"reason": "emergency_close_failed"} and refused and persists and cleared == (False, True), str((crit, cleared)))
    b.close()
    b = Box()
    kh = fill(b)
    p = b.t.positions[b.ea.pos.posTicket]
    tp_at_fill = p["tp"]
    fill_srv = p["time"]
    bar_close_srv = fill_srv - fill_srv % 300 + 300
    b.t.gmt_ms = (bar_close_srv - 1 - b.t.server_offset) * 1000
    b.ea.on_timer()
    before = (p["tp"], [w for w in b.t.writes if w[0] == "sltp"])
    b.t.gmt_ms = (bar_close_srv - b.t.server_offset) * 1000
    b.ea.on_timer()
    tp = b.ea.last(kh, "TP_SET")
    check("EAM-19 TP: none at the fill (request TP 0); still none 1 s before the fill-bar close; at the fill-bar close (the normal version's "
          "fill confirmation) TP0 2592.50 is set with the SL kept (2605.00)",
          tp_at_fill == 0.0 and before == (0.0, []) and p["tp"] == 2592.5 and p["sl"] == 2605.0 and tp == {"tp": "2592.50", "sl_kept": "2605.00"},
          str((before, tp)))
    b.close()
    b = Box()
    kh = fill(b)
    p = b.t.positions[b.ea.pos.posTicket]
    b.t.modify_mode = "reject"
    bc_srv = p["time"] - p["time"] % 300 + 300
    for s in (0, 1, 2, 100):
        b.t.gmt_ms = (bc_srv + s - b.t.server_offset) * 1000
        b.ea.on_timer()
    n_same_bar = len([w for w in b.t.writes if w[0] == "sltp"])
    b.t.modify_mode = "ok"
    b.t.gmt_ms = (bc_srv + 300 - b.t.server_offset) * 1000
    b.ea.on_timer()
    check("EAM-20 the TP0 change is rejected: MODIFY_FAILED (sl_kept 2605), new entries halt, the SL is untouched; it is retried once per M5 "
          "bar (1 attempt during the rest of the bar, not every timer) and succeeds on the next bar",
          n_same_bar == 1 and b.ea.last(kh, "MODIFY_FAILED") == {"what": "tp0", "retcode": "10016", "sl_kept": "2605.00000"}
          and b.ea.haltNew and p["sl"] == 2605.0 and p["tp"] == 2592.5, str(b.ea.states(kh)))
    b.close()


def gate_be():
    res = {}
    for nm, ticks, bars, fb in (("prefill_low", [2596.0], [(0, 2580.0)], "TICKS_SINCE_FILL"),
                                ("fill_bar_ticks", [2590.0, 2585.2], [], "TICKS_SINCE_FILL"),
                                ("fill_bar_skip", [2585.2], [], "SKIP"),
                                ("next_bar_15.0", [], [(300, 2585.2)], "TICKS_SINCE_FILL"),
                                ("next_bar_14.99", [], [(300, 2585.21)], "TICKS_SINCE_FILL"),
                                ("unclosed_bar", [], [(600, 2580.0)], "TICKS_SINCE_FILL")):
        b = Box(FillBarBe=fb)
        kh = fill(b)
        p = b.t.positions[b.ea.pos.posTicket]
        fo = p["time"] - p["time"] % 300
        for x in ticks:
            b.t.bid = x
            b.ea.on_tick()
        b.t.bid = 2598.0
        b.t.rates = [(fo + off, low) for off, low in bars]
        b.t.gmt_ms = (fo + 600 + 10 - b.t.server_offset) * 1000      # fill bar and the next bar closed; the bar at +600 is open
        b.ea.on_timer()
        res[nm] = (b.ea.last(kh, "BE_SET"), p["sl"])
        b.close()
    check("EAM-21 breakeven Fixed Distance 15 USD from the XS FILL (2600.20) -> SL = the XS fill: the fill bar's pre-fill low (2580) is never "
          "used; the fill bar uses only the Bid seen after the fill (2585.20 -> BE) unless FillBarBe=SKIP; a later closed M5 bar low 2585.20 "
          "(15.00) -> BE, 2585.21 (14.99) -> none; a bar that has not closed is never used",
          res["prefill_low"] == (None, 2605.0) and res["fill_bar_ticks"][1] == 2600.2 and res["fill_bar_skip"] == (None, 2605.0)
          and res["next_bar_15.0"][1] == 2600.2 and res["next_bar_15.0"][0]["sl"] == "2600.20" and res["next_bar_14.99"] == (None, 2605.0)
          and res["unclosed_bar"] == (None, 2605.0), str(res))
    b = Box()
    kh = fill(b)
    p = b.t.positions[b.ea.pos.posTicket]
    fo = p["time"] - p["time"] % 300
    b.t.modify_mode = "ok"
    b.t.gmt_ms = (fo + 300 - b.t.server_offset) * 1000
    b.ea.on_timer()                                # TP0 set
    b.t.modify_mode = "reject"
    b.t.rates = [(fo + 300, 2584.0), (fo + 600, 2599.0)]
    b.t.gmt_ms = (fo + 600 + 5 - b.t.server_offset) * 1000
    b.ea.on_timer()
    failed = (b.ea.last(kh, "MODIFY_FAILED"), p["sl"], b.ea.pos.bePending)
    b.t.modify_mode = "ok"
    b.t.gmt_ms = (fo + 900 + 5 - b.t.server_offset) * 1000
    b.ea.on_timer()
    check("EAM-22 the breakeven change is rejected: MODIFY_FAILED, new entries halt, the SL stays 2605 (never deleted / loosened); the "
          "breakeven stays pending and is retried on the next closed bar even though that bar's low (2599) alone would not trigger it",
          failed[0]["what"] == "breakeven" and failed[1] == 2605.0 and failed[2] and p["sl"] == 2600.2 and b.ea.last(kh, "BE_SET") is not None
          and b.ea.haltNew, str(failed))
    b.close()
    b = Box()
    kh = fill(b)
    p = b.t.positions[b.ea.pos.posTicket]
    p["sl"] = 2599.0                               # someone moved the SL below the fill already
    fo = p["time"] - p["time"] % 300
    b.t.rates = [(fo + 300, 2584.0)]
    b.t.gmt_ms = (fo + 600 + 5 - b.t.server_offset) * 1000
    b.ea.on_timer()
    sltp = [w[1] for w in b.t.writes if w[0] == "sltp"]
    check("EAM-23 a change that would loosen the SL (breakeven 2600.20 above the current 2599.00) is refused before any send "
          "(MODIFY_REFUSED); the TP0 change keeps the current SL; no SL / TP change ever removes the SL (sl > 0 in every request)",
          b.ea.last(kh, "MODIFY_REFUSED") == {"what": "breakeven", "reason": "would_loosen_or_remove_sl"} and p["sl"] == 2599.0
          and all(r["sl"] > 0 and r["sl"] <= 2605.0 for r in sltp) and len(sltp) == 1, str(sltp))
    b.close()
    res = {}
    for ev in ("TV_FLAT", "TV_CLOSED", "CANCEL", "CLOSE_REQ", "BE_MOVE", "TP_SET"):
        b = Box()
        kh = fill(b)
        n0 = len(b.t.writes)
        kx = b.cmd(ev=ev, key=f"{SID}|{ev}|T{BC}|{BC + 300000}")
        b.ea.on_timer()
        res[ev] = (b.ea.last(kx, "SKIPPED"), len(b.t.writes) - n0, b.ea.pos.posTicket in b.t.positions)
        b.close()
    check("EAM-24 TradingView's management / exit events never act on MT5: even if one reached the EA as a command (the bridge never "
          "forwards them) it is SKIPPED not_entry with zero writes and the own position stays open with its own SL / TP / breakeven",
          all(v == ({"reason": "not_entry"}, 0, True) for v in res.values()), str(res))
    b = Box()
    b.t.bid, b.t.ask = 2592.45, 2592.75
    kh = fill(b, px=2593.0, sl=2598.0, tp=2592.5)
    p = b.t.positions[b.ea.pos.posTicket]
    fo = p["time"] - p["time"] % 300
    b.t.gmt_ms = (fo + 300 - b.t.server_offset) * 1000
    b.ea.on_timer()
    check("EAM-25 CLOSE_REQ equivalent re-checked with the XS fill: the XS fill 2592.45 is already beyond TP0 2592.50 -> FILL_SIDE_BAD and the "
          "OWN position is closed at the fill-bar close (decided by the XS fill / real position, not by TradingView's notification)",
          "FILL_SIDE_BAD" in b.ea.states(kh) and b.ea.last(kh, "CLOSE_SENT") is not None and p["ticket"] not in b.t.positions, str(b.ea.states(kh)))
    b.close()


def gate_restart_misc():
    b = Box()
    kh = fill(b)
    tk = b.ea.pos.posTicket
    b.restart()
    own = (b.ea.hasPos, b.ea.pos.posTicket == tk, b.ea.pos.tracked, b.ea.pos.fill, b.ea.pos.sl0)
    p = b.t.positions[tk]
    fo = p["time"] - p["time"] % 300
    b.t.bid = 2580.0
    b.ea.on_tick()                                 # not tracked after a restart
    b.t.rates = [(fo, 2570.0)]
    b.t.gmt_ms = (fo + 300 + 5 - b.t.server_offset) * 1000
    b.ea.on_timer()
    fill_bar_be = b.ea.last(kh, "BE_SET")
    b.ea.on_deinit()
    b.t.close_position(tk, 2605.0, "SL")
    b.ea = em.EA(b.t, b.x, **b.kw)
    b.ea.on_init()
    b.ea.on_timer()
    check("EAM-26 EA restart with its own position: re-adopted only from the journal FILLED record + the live ticket (symbol + magic), the fill "
          "bar is NOT used for breakeven after a restart (ticks since the fill unknown), TP0 is still set; a position closed while the EA was "
          "off is recorded CLOSED with the deal reason (sl)",
          own == (True, True, False, 2600.2, 2605.0) and fill_bar_be is None and b.ea.last(kh, "TP_SET") is not None
          and (b.ea.last(kh, "CLOSED") or {}).get("reason") == "sl", str((own, b.ea.states(kh))))
    b.close()
    b = Box()
    second = em.EA(b.t, b.x, DryRun=False, AllowNewEntries=True, ExpectedLogin=LOGIN)
    r2 = second.on_init()
    j_before = len(b.ea.journal_lines())
    second.on_deinit()
    check("EAM-27 a second EA instance on the same exchange folder is refused (INIT_FAILED, exclusive ea.lock) and writes nothing into the "
          "running instance's journal (not even STOP)",
          r2 == "INIT_FAILED:lock" and len(b.ea.journal_lines()) == j_before, r2)
    b.close()
    b = Box(DryRun=True)
    kh = b.cmd()
    b.cmd()                                        # the same key twice in cmd/
    b.cmd(bc=BC, key=f"{SID}|ENTRY|T{BC}|{BC}x", khash="0" * 16)
    kl = b.cmd(bc=BC, key=f"{SID}|ENTRY|TL|{BC}", otype="LIMIT")
    kn = b.cmd(bc=BC, key=f"{SID}|ENTRY|TN|{BC}", px=float("nan"))
    ka = b.cmd(bc=BC + 1000, key=f"{SID}|ENTRY|TA|{BC}")
    kc = b.cmd(bc=BC, key=f"{SID}|ENTRY|TC|{BC}", path="CURRENT")
    kg = b.cmd(bc=BC, key=f"{SID}|ENTRY|TG|{BC}", px=2606.0)
    ks = b.cmd(bc=BC, key=f"{SID}|ENTRY|TS|{BC}", cfg_sha256="0" * 64)
    b.ea.on_timer()
    rs = lambda k: (b.ea.last(k, "SKIPPED") or {}).get("reason")
    rpts = os.listdir(os.path.join(b.x, "rpt"))
    dup = sum(1 for n in rpts if "state=DUPLICATE" in open(os.path.join(b.x, "rpt", n)).read())
    check("EAM-28 commands: the same key twice -> one SEEN + DUPLICATE; a key hash that is not SHA-256(key)[:16] -> BAD_CMD (never processed); "
          "LIMIT -> limit_not_supported (never converted); NaN price -> price_not_finite; unaligned bar -> bar_time; Entry Timing CURRENT -> "
          "path_not_initial_settings; SL below the price -> price_geometry; another cfg hash -> cfg_mismatch; every file moved to done/; "
          "no trade write",
          b.ea.states(kh).count("SEEN") == 1 and dup == 1 and "BAD_CMD" in b.ea.states("") and rs(kl) == "limit_not_supported"
          and rs(kn) == "price_not_finite" and rs(ka) == "bar_time" and rs(kc) == "path_not_initial_settings" and rs(kg) == "price_geometry"
          and rs(ks) == "cfg_mismatch" and os.listdir(os.path.join(b.x, "cmd")) == [] and len(os.listdir(os.path.join(b.x, "done"))) == 9
          and b.t.writes == [], str([rs(k) for k in (kl, kn, ka, kc, kg, ks)]))
    b.close()
    b = Box()
    b.t.send_mode = "partial"
    kh = fill(b)
    part = b.ea.last(kh, "PARTIAL_FILL")
    check("EAM-29 partial fill (DONE_PARTIAL): the position's ACTUAL volume (0.20 of 0.41) is adopted, protected with the initial SL "
          "(PROTECTED), no top-up order (one send)",
          part == {"volume": "0.20", "requested": "0.41"} and "PROTECTED" in b.ea.states(kh) and len(b.sends()) == 1 and b.ea.pos.volume == 0.2,
          str(part))
    b.close()
    b = Box()
    kh = fill(b)
    b.t.account["login"] = 7654321                # the terminal was switched to another account
    p = b.ea.pos.posTicket
    n0 = len(b.t.writes)
    fo = b.t.positions[p]["time"] - b.t.positions[p]["time"] % 300
    b.t.gmt_ms = (fo + 300 - b.t.server_offset) * 1000
    b.ea.on_timer()
    b.ea.on_timer()
    check("EAM-30 the account / server changes while running: ENV_LOST, every trade write stops (also SL / TP management: "
          "MANAGEMENT_BLOCKED once; the SL already on the position stays)",
          "ENV_LOST" in b.ea.states("") and len(b.t.writes) == n0 and b.ea.states(kh).count("MANAGEMENT_BLOCKED") == 1, str(b.ea.states("")))
    b.close()


def gate_dry_mgmt():
    b = Box()
    kh = fill(b)
    p = b.t.positions[b.ea.pos.posTicket]
    b.restart(DryRun=True)
    n0 = len(b.t.writes)
    fo = p["time"] - p["time"] % 300
    b.t.rates = [(fo + 300, 2580.0)]
    b.t.gmt_ms = (fo + 600 + 5 - b.t.server_offset) * 1000
    b.ea.on_timer()
    b.t.send_mode = "fill_no_sl"
    b.ea.check_protection()
    check("EAM-31 DRY_RUN blocks EVERY trade write, also for an own position adopted after a restart: no TP0, no breakeven, no close "
          "(MANAGEMENT_BLOCKED is journaled; the server-side SL stays) — DRY_RUN is not the 'stop new entries' switch",
          len(b.t.writes) == n0 and p["tp"] == 0.0 and p["sl"] == 2605.0 and "MANAGEMENT_BLOCKED" in b.ea.states(kh), str(b.ea.states(kh)))
    b.close()


# ---- static checks of the MQL5 source ------------------------------------------------------------------------------------
def _func(src, name):
    m = re.search(r"\n[a-zA-Z_ ]+\b" + name + r"\([^)]*\)\s*\n  \{", src)
    assert m, name
    i = m.end()
    depth = 1
    while depth:
        c = src[i]
        depth += c == "{"
        depth -= c == "}"
        i += 1
    return src[m.start():i]


def gate_static():
    src = open(MQ5, encoding="utf-8").read()
    code = re.sub(r"//[^\n]*", "", src)
    mdl = open(os.path.join(ROOT, "tests", "ea_model.py"), encoding="utf-8").read()
    inp = dict(re.findall(r"input\s+\w+\s+(Inp\w+)\s*=\s*([^;]+);", src))
    check("EAS-01 inputs: InpDryRun = true, InpAllowNewEntries = false, InpExpectedLogin = 0, server XSFintech-DEMO, symbol XAUUSDs, "
          "currency JPY, the sid / cfg hash / TradingView symbol of the bridge; no password / token / URL / WebRequest / socket anywhere",
          inp.get("InpDryRun") == "true" and inp.get("InpAllowNewEntries") == "false" and inp.get("InpExpectedLogin") == "0"
          and inp.get("InpExpectedServer") == '"XSFintech-DEMO"' and inp.get("InpSymbol") == '"XAUUSDs"' and inp.get("InpExpectedCurrency") == '"JPY"'
          and inp.get("InpExpectedSid") == f'"{SID}"' and inp.get("InpExpectedCfgSha") == f'"{CFG}"' and inp.get("InpExpectedTvSym") == '"OANDA:XAUUSD"'
          and not re.search(r"password|token|https?://|WebRequest|Socket", code, re.I), str(inp))
    consts = dict(re.findall(r"const\s+\w+\s+(\w+)\s*=\s*([^;]+);", code))
    check("EAS-02 approved constants are constants (not inputs) and equal the model: RISK_FRACTION 0.03, MAX_AGE_SEC 60, MAX_DEV_FRAC 0.20, "
          "MAX_SPREAD 0.50, BE_DIST 15.0, BAR_SEC 300, CMD_VERSION \"1\"",
          float(consts["RISK_FRACTION"]) == em.RISK_FRACTION == 0.03 and int(consts["MAX_AGE_SEC"]) == em.MAX_AGE_SEC == 60
          and float(consts["MAX_DEV_FRAC"]) == em.MAX_DEV_FRAC == 0.2 and float(consts["MAX_SPREAD"]) == em.MAX_SPREAD == 0.5
          and float(consts["BE_DIST"]) == em.BE_DIST == 15.0 and int(consts["BAR_SEC"]) == em.BAR_SEC == 300
          and consts["CMD_VERSION"].strip('"') == em.CMD_VERSION and eb.MAX_AGE_SEC == 60 and eb.CMD_VERSION == "1", str(consts))
    sends = [m.start() for m in re.finditer(r"\bOrderSend\(", code)]
    owners = []
    for name in ("ProcessEntry", "ClosePosition", "ModifyOwn"):
        f = _func(code, name)
        owners.append((name, f.count("OrderSend(")))
    pe = _func(code, "ProcessEntry")
    gate_ok = pe.index("TradeWritesAllowed()") < pe.index("\"PRE_SEND\"") < pe.index("OrderSend(")
    cp, mo = _func(code, "ClosePosition"), _func(code, "ModifyOwn")
    check("EAS-03 the only trade API writes are 3 OrderSend calls (ProcessEntry / ClosePosition / ModifyOwn; no CTrade, OrderSendAsync, "
          "PositionClose, OrderDelete); ProcessEntry checks TradeWritesAllowed and journals PRE_SEND before OrderSend; ClosePosition / "
          "ModifyOwn start with the TradeWritesAllowed gate; ModifyOwn refuses to loosen / remove the SL before sending",
          len(sends) == 3 and owners == [("ProcessEntry", 1), ("ClosePosition", 1), ("ModifyOwn", 1)] and gate_ok
          and not re.search(r"CTrade|Trade\.mqh|OrderSendAsync|PositionClose|OrderDelete", code)
          and re.search(r"\{\s*if\(!TradeWritesAllowed\(\)", cp) and re.search(r"\{\s*if\(!TradeWritesAllowed\(\)", mo)
          and mo.index("would_loosen_or_remove_sl") < mo.index("OrderSend("), str(owners))
    oi = _func(code, "OnInit")
    twa = _func(code, "TradeWritesAllowed")
    check("EAS-04 OnInit refuses a non-demo account before anything else (INIT_FAILED); TradeWritesAllowed needs DryRun off, env ok, startup "
          "reconciliation done, a demo account and the expected login + server at the time of every write; the lock file is exclusive",
          oi.index("ACCOUNT_TRADE_MODE_DEMO") < oi.index("FolderCreate") and "INIT_FAILED" in oi.split("FolderCreate")[0]
          and all(x in twa for x in ("InpDryRun", "g_envOk", "g_ready", "IsDemoAccount()", "ACCOUNT_LOGIN", "ACCOUNT_SERVER"))
          and oi.index("Reconcile()") < oi.index("g_ready = true"), "")
    st_src = set(re.findall(r'(?:Journal|Report)\([^;]*?,\s*"([A-Z_]+)"', code)) | set(re.findall(r'\?\s*"([A-Z_]+)"\s*:\s*"([A-Z_]+)"', code)[0])
    st_src |= {"ENV_OK", "ENV_LOST", "CLOSE_SENT", "CLOSE_FAILED"}
    st_mdl = set(re.findall(r'(?:journal|report)\([^\n]*?,\s*"([A-Z_]+)"', mdl)) | {"ENV_OK", "ENV_LOST", "CLOSE_SENT", "CLOSE_FAILED"}
    check("EAS-05 the journal / report states of the MQL5 EA and the model are the same set (%d states)" % len(st_src), st_src == st_mdl,
          str((sorted(st_src - st_mdl), sorted(st_mdl - st_src))))
    rs_src = set(re.findall(r'return\("([a-z0-9_]+)', _func(code, "CheckCmd") + _func(code, "CheckDeadline") + _func(code, "PrepareOrder")))
    rs_mdl = set(re.findall(r'return "([a-z0-9_]+)', mdl)) | set(re.findall(r'return f"([a-z0-9_]+)', mdl))
    rs_mdl = {r for r in rs_mdl if r not in ("not_demo_account", "expected_login_not_set", "login_mismatch", "server_mismatch", "currency_mismatch",
                                             "not_hedging_account", "symbol_not_available", "dry_run", "new_entries_off", "trade_writes_not_allowed",
                                             "critical", "halt_new", "halt_file", "in_flight")}
    check("EAS-06 the refusal reasons of CheckCmd / CheckDeadline / PrepareOrder are the same in the MQL5 EA and the model (%d)" % len(rs_src),
          rs_src == rs_mdl, str((sorted(rs_src - rs_mdl), sorted(rs_mdl - rs_src))))
    dr = set(re.findall(r"case TRADE_RETCODE_(\w+):", _func(code, "IsDefiniteReject")))
    check("EAS-07 IsDefiniteReject lists exactly the model's definite rejects (%d codes); anything else after a send (timeout, error, "
          "connection, placed, ...) is UNKNOWN" % len(dr), dr == set(em.DEFINITE_REJECT), str(sorted(dr ^ set(em.DEFINITE_REJECT))))
    pr = _func(code, "PrepareOrder")
    check("EAS-08 the request: SELL at the Bid, the rounded initial SL always attached, TP 0 (TP0 at the fill-bar close), comment XSD:<key "
          "hash>; ManageOwn uses TRADE_ACTION_SLTP only through ModifyOwn; every state the bridge maps is a state the EA writes",
          "req.sl           = sl;" in pr and "req.tp           = 0.0;" in pr and 'req.comment      = "XSD:" + c.khash;' in pr
          and "ORDER_TYPE_SELL" in pr and "tk.bid" in pr and code.count("TRADE_ACTION_SLTP") == 1 and "TRADE_ACTION_SLTP" in mo
          and set(eb.EA_STATE_TIME) <= st_src, str(sorted(set(eb.EA_STATE_TIME) - st_src)))


def main():
    for g in (gate_env, gate_deadline, gate_price_lot, gate_slot, gate_unknown, gate_protect, gate_be, gate_restart_misc, gate_dry_mgmt, gate_static):
        try:
            g()
        except Exception:
            import traceback
            check(f"{g.__name__} completed without error", False, traceback.format_exc()[-1500:])
    fails = 0
    for nm, ok, d in RESULTS:
        fails += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {nm[:150].ljust(150)}  {'' if ok else d}")
    print(f"\n{len(RESULTS) - fails}/{len(RESULTS)} passed  [local Python: EA reference model + MQL5 static checks; MQL5 not compiled, no MT5]")
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
