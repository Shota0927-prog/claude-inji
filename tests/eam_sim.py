"""EAM fixtures — the demo EA rules (stage 3) on the Python reference model tests/ea_model.py + static checks of the MQL5 source
automation/xau_short/ea/XauShortDemoEA.mq5 (the model and the source must keep the same constants / approvals / states / reasons / gates).

  EAM-01..04 : demo only (real account refused at start, every expected value checked, login 0 = no writes), DRY_RUN = zero trade
               writes, new-entries OFF / halt file stop new entries only (own-position protection continues)
  EAM-05..10 : deadline 60 s (1 s clock resolution: never late, never negative), after the PRE_SEND record; price deviation 20 %,
               spread 0.50; lot from 3 % of the balance via OrderCalcProfit, step floor, min / max lot, margin, SL never widened
  EAM-11..16 : max one (manual / other EA / pending / own), rejects, unknown results, crash after PRE_SEND, reply lost, PLACED
  EAM-17..25 : initial SL missing -> emergency close (failure -> CRITICAL), TP0 at the fill-bar close only, TP / SL change rejected,
               breakeven 15 USD from the XS fill, never loosen, TradingView exits never reach the EA, fill beyond TP0
  EAM-26..31 : restart with an own position, two EA instances, bad / duplicate / LIMIT commands, partial fill, environment lost,
               DRY_RUN blocks own-position management too
  EAR-01..08 : regressions of the ST3-1 review (items 1-8): final go / no-go, required records + checks after PRE_SEND, ownership
               quarantine, unknown-result resolution, fill-bar ticks bounded by the bar, partial emergency close, position identifier vs
               ticket, approvals / heartbeats
  EAR-09..12 : regressions of the ST3-2 re-review (items 1-4): the last checks after the slow final PrepareOrder, FILL_SIDE_BAD close
               results + persisted close obligation, later deals of the same order (volume / average), breakeven pending across restarts
  EAR-13..15 : regressions of the ST3-3 re-review: the clock checked after FinalGate's file reads, the fill state / last IN deal from
               the history (adoption with several IN deals, history arriving late, restart), breakeven basis voided by a later IN deal
  EAR-16..17 : regressions of the ST3-4 re-review: a change during the history read (pass, adoption, right before the SL change),
               a same-ms IN deal with / without a crash between POSITION_UPDATED and BE_TRIGGER_VOID, restart
  EAS-01..17 : the MQL5 source (static): inputs, constants, approvals, the only OrderSend sites and their gates / order, journal
               states, refusal reasons, definite-reject list, ownership by identifier, unknown handling, fill-bar ticks, bridge map
Evidence class: local Python only. The MQL5 EA itself is NOT compiled or run here (no MetaEditor / MT5 in this environment).
"""
import hashlib
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
ALL = em.APPROVALS


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


class FakeBridge:
    """the bridge as the EA sees it: hb_bridge.txt + answers to ask/*.ask (mode GO / NOGO reason / silent)."""

    def __init__(self, box):
        self.b = box
        self.mode = "GO"
        self.ttl = 3000
        self.asks = 0
        self.alive = True

    def hb(self):
        if self.alive:
            with open(os.path.join(self.b.x, "hb_bridge.txt"), "w") as f:
                f.write(f"t_ms={self.b.t.gmt_ms}\n")

    def __call__(self):
        self.hb()
        d = os.path.join(self.b.x, "ask")
        if not self.alive or not os.path.isdir(d):
            return
        for n in sorted(os.listdir(d)):
            if not n.endswith(".ask"):
                continue
            kv = dict(l.strip().split("=", 1) for l in open(os.path.join(d, n)) if "=" in l)
            self.asks += 1
            if self.mode == "silent":
                continue
            now = self.b.t.gmt_ms
            body = (f"key_hash={kv['key_hash']}\ndecision=GO\nreason=ok\nvalid_until_ms={now + self.ttl}\n" if self.mode == "GO" else
                    f"key_hash={kv['key_hash']}\ndecision=NOGO\nreason={self.mode}\nvalid_until_ms=0\n")
            with open(os.path.join(self.b.x, "ans", kv["key_hash"] + ".ans"), "w") as f:
                f.write(body)
            os.remove(os.path.join(d, n))


class Box:
    """one exchange folder + terminal + EA + fake bridge."""

    def __init__(self, **ea_kw):
        self.tmp = tempfile.mkdtemp(prefix="eam_")
        self.x = os.path.join(self.tmp, "XauShortDemo")
        os.makedirs(self.x)
        self.t = em.FakeTerminal(gmt_ms=BC + 2500)
        self.t.bid, self.t.ask = 2600.2, 2600.5
        kw = dict(DryRun=False, AllowNewEntries=True, ExpectedLogin=LOGIN, approvals=ALL)
        kw.update(ea_kw)
        self.kw = kw
        self.fb = FakeBridge(self)
        self.ea = self._wire(em.EA(self.t, self.x, **kw))
        self.init = self.ea.on_init()
        self.n = 0

    def _wire(self, ea):
        ea.wait_hook = self.fb
        return ea

    def timer(self):
        self.fb.hb()
        self.ea.on_timer()

    def cmd(self, bc=BC, px=2600.0, sl=2605.0, tp=2592.5, otype="MARKET", ev="ENTRY", path="SATS_NOW", key=None, khash=None, **over):
        key = key or f"{SID}|{ev}|T{bc}|{bc}"
        kh = khash if khash is not None else hashlib.sha256(key.encode()).hexdigest()[:16]
        f = dict(v="2", key=key, key_hash=kh, tid=f"T{bc}", ev=ev, side="SHORT", otype=otype, path=path, px=repr(px), sl=repr(sl),
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
        self.ea = self._wire(em.EA(self.t, self.x, **k))
        self.init = self.ea.on_init()
        return self.ea

    def sends(self):
        return [w for w in self.t.writes if w[0] == "send"]

    def touch(self, name, body=""):
        with open(os.path.join(self.x, name), "w") as f:
            f.write(body)

    def at_srv(self, srv_sec):
        self.t.gmt_ms = (srv_sec - self.t.server_offset) * 1000

    def own(self):
        return self.t.positions.get(self.ea.pos.posTicket)

    def close(self):
        self.ea.on_deinit()
        shutil.rmtree(self.tmp, ignore_errors=True)


def fill(box, **kw):
    """one filled own position via a valid command."""
    kh = box.cmd(**kw)
    box.timer()
    return kh


def fill_bar(box):
    p = box.own()
    return p["time"] - p["time"] % 300


def gate_env():
    b = Box()
    real = em.FakeTerminal(gmt_ms=BC)
    real.account["trade_mode"] = "REAL"
    tmp = tempfile.mkdtemp()
    r = em.EA(real, os.path.join(tmp, "x"), DryRun=False, AllowNewEntries=True, ExpectedLogin=LOGIN, approvals=ALL).on_init()
    real.account["trade_mode"] = "CONTEST"
    r2 = em.EA(real, os.path.join(tmp, "y"), DryRun=False, AllowNewEntries=True, ExpectedLogin=LOGIN, approvals=ALL).on_init()
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
        b.timer()
        res[nm] = (b.ea.envOk, b.ea.last(kh, "SKIPPED"), len(b.t.writes))
        b.close()
    check("EAM-02 demo environment checked at start and on every timer: expected login not set (0) / login / server / currency / netting "
          "account / symbol mismatch -> env not ok -> the valid ENTRY is SKIPPED trade_writes_not_allowed with ZERO trade writes",
          all(v[0] is False and v[1] == {"reason": "trade_writes_not_allowed"} and v[2] == 0 for v in res.values()), str(res))
    b = Box(DryRun=True, AllowNewEntries=False)
    d = em.EA.__init__.__defaults__
    kh = b.cmd()
    b.timer()
    dr = b.ea.last(kh, "DRY_RUN_NOT_SENT")
    check("EAM-03 DRY_RUN (the default: DryRun=True, AllowNewEntries=False, ExpectedLogin=0, no approvals): the ENTRY is fully checked, the "
          "lot computed and the bridge asked (go=granted) but DRY_RUN_NOT_SENT with ZERO trade API writes",
          d[:3] == (True, False, 0) and d[-1] == () and dr is not None and dr["gate"] == "dry_run" and dr["go"] == "granted"
          and float(dr["volume"]) > 0 and "budget_jpy" in dr and b.t.writes == [], str(dr))
    b.close()
    b = Box(AllowNewEntries=False)
    kh = b.cmd()
    b.timer()
    off = (b.ea.last(kh, "DRY_RUN_NOT_SENT") or {}).get("gate")
    b.close()
    b = Box()
    kh = fill(b)
    b.touch("halt_new")
    kh2 = b.cmd(bc=BC + 300000)
    b.t.gmt_ms = BC + 300000 + 2000
    b.timer()
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
        b.timer()
        res[nm] = (b.ea.last(kh, "SKIPPED") or {}).get("reason") or ("dry" if b.ea.last(kh, "DRY_RUN_NOT_SENT") else None)
        b.close()
    check("EAM-05 deadline from the ENTRY bar close with TimeGMT's 1 s resolution: up to 59.999 s accepted; 60.0 s and later -> expired "
          "(the latest possible 'now' is used, never late); a bar close in the future even by 1 ms -> clock_or_future_bar (the earliest "
          "possible 'now' is used, a negative age is never 'in time')",
          res == {"59.5": "dry", "59.999": "dry", "60.0": "expired", "61": "expired", "future-0.5": "clock_or_future_bar",
                  "future-0.001": "clock_or_future_bar", "0.3": "dry"}, str(res))
    b = Box()
    b.t.gmt_ms = BC + 58500
    b.fb.ttl = 10000
    b.ea.before_send_hook = lambda: b.t.advance(2000)      # time passes between the PRE_SEND record and the send
    kh = b.cmd()
    b.timer()
    check("EAM-06 the deadline is checked again AFTER the PRE_SEND record, right before OrderSend: checks passed at 58.5 s, 'now' is past "
          "60 s at the send -> SEND_ABORTED expired (a final result for the PRE_SEND), zero writes, the slot is free again",
          b.ea.last(kh, "SEND_ABORTED") == {"reason": "expired"} and "PRE_SEND" in b.ea.states(kh) and b.t.writes == []
          and b.ea.inflightKey == "" and b.ea.unknownKey == "", str(b.ea.states(kh)))
    b.close()


def gate_price_lot():
    res = {}
    for nm, bid, ask in (("dev_1.00", 2601.0, 2601.3), ("dev_1.01", 2601.01, 2601.31), ("dev_-1.00", 2599.0, 2599.3),
                         ("spread_0.50", 2600.2, 2600.7), ("spread_0.51", 2600.2, 2600.71)):
        b = Box(DryRun=True)
        b.t.bid, b.t.ask = bid, ask
        kh = b.cmd()
        b.timer()
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
        b.timer()
        res[nm] = ((b.ea.last(kh, "SKIPPED") or {}).get("reason"), len(b.sends()), b.sends()[0][1]["volume"] if b.sends() else None)
        b.close()
    check("EAM-09 no order when: even the minimum lot exceeds the 3 % budget (below_min_lot), the margin is not free (margin), OrderCalcProfit "
          "/ OrderCalcMargin fail, the symbol spec is invalid (tick 0), there is no price, the XS session is closed, the symbol cannot be sold; "
          "a huge budget is capped at the volume maximum",
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
        b.timer()
        req = b.sends()[0][1]
        res[nm] = (req["sl"], req["volume"], (req["sl"] - req["price"]) * req["volume"] * 15000)
        b.close()
    check("EAM-10 the SL is put on the tick grid DOWNWARDS for a short (2605.017 -> 2605.01, tick 0.05: 2605.03 -> 2605.00: never widened) "
          "and the volume / risk are computed with the final price and SL (loss <= 30,000 JPY)",
          res["sl_2605.017"][0] == 2605.01 and res["tick_0.05"][0] == 2605.0 and all(v[2] <= 30000 for v in res.values()), str(res))


def gate_slot():
    res = {}
    mk = lambda tk, sym, magic, typ: {tk: dict(ticket=tk, identifier=tk, symbol=sym, magic=magic, comment="", type=typ, volume=0.1,
                                               price_open=2600.0, sl=0.0, tp=0.0, time=0, time_msc=0)}
    for nm, setup in (("manual_pos", lambda t: t.positions.update(mk(1, "XAUUSDs", 0, "BUY"))),
                      ("other_symbol", lambda t: t.positions.update(mk(2, "EURUSD", 7, "SELL"))),
                      ("pending", lambda t: t.orders.update({3: dict(symbol="XAUUSDs", comment="")}))):
        b = Box()
        setup(b.t)
        kh = b.cmd()
        b.timer()
        res[nm] = ((b.ea.last(kh, "SKIPPED") or {}).get("reason"), len(b.sends()))
        b.close()
    b = Box()
    kh = fill(b)
    kh2 = b.cmd(bc=BC + 300000)
    b.t.gmt_ms = BC + 300000 + 2000
    b.timer()
    held = (b.ea.last(kh2, "SKIPPED") or {}).get("reason")
    b.t.close_position(b.ea.pos.posTicket, 2595.0, "TP")
    b.timer()
    b.cmd(bc=BC + 300000)                       # the same signal delivered again after the close
    b.timer()
    again = b.ea.states(kh2)
    check("EAM-11 max one for the WHOLE account: a manual position, another EA's position on another symbol, a pending order, or the own "
          "position -> the new ENTRY is SKIPPED (max1_*) and never placed later: after the own position closed, the same signal delivered "
          "again is a DUPLICATE (no second SEEN, no send)",
          res == {"manual_pos": ("max1_position_exists", 0), "other_symbol": ("max1_position_exists", 0), "pending": ("max1_pending_order_exists", 0)}
          and held == "max1_own_position" and again.count("SEEN") == 1 and len(b.sends()) == 1 and "CLOSED" in b.ea.states(kh), str((res, held, again)))
    b.close()
    b = Box()
    b.t.send_mode = "reject:10006"
    kh = fill(b)
    rej = (b.ea.last(kh, "REJECTED"), b.ea.inflightKey, b.ea.haltNew)
    b.t.send_mode = "fill"
    kh2 = b.cmd(bc=BC + 300000)
    b.t.gmt_ms = BC + 300000 + 2000
    b.timer()
    check("EAM-12 a definite reject (10006) -> REJECTED, the slot is free again and new entries are not halted: the next ENTRY is sent",
          rej == ({"retcode": "10006"}, "", False) and "PROTECTED" in b.ea.states(kh2) and len(b.sends()) == 2, str(rej))
    b.close()


def gate_unknown():
    b = Box()
    b.t.send_mode = "timeout"
    kh = fill(b)
    st1 = (b.ea.last(kh, "UNKNOWN"), b.ea.unknownKey == kh, b.ea.haltNew)
    b.t.send_mode = "fill"
    kh2 = b.cmd(bc=BC + 300000)
    b.t.gmt_ms = BC + 300000 + 2000
    b.timer()
    nxt = (b.ea.last(kh2, "SKIPPED") or {}).get("reason", "")
    b.restart()
    after = (b.ea.unknownKey == kh, (b.ea.last(kh, "UNKNOWN_CHECK") or {}).get("detected"))
    check("EAM-13 result unknown (timeout 10012): UNKNOWN, new entries stop and nothing is re-sent (the next ENTRY is SKIPPED "
          "unknown_unresolved); after an EA restart the unknown persists and the history check finds no order (UNKNOWN_CHECK detected=none)",
          st1[0] == {"reason": "retcode_10012"} and st1[1] and st1[2] and nxt == "unknown_unresolved:" + kh and after == (True, "none")
          and len(b.sends()) == 1, str((st1, nxt, after)))
    b.close()
    b = Box()

    def crash():
        raise SystemExit("simulated crash after the PRE_SEND record")
    b.ea.before_send_hook = crash
    kh = b.cmd()
    try:
        b.timer()
    except SystemExit:
        pass
    b.restart(crash=True)
    b.cmd()                                       # the bridge / operator delivers the same command again
    b.timer()
    check("EAM-14 crash after the PRE_SEND record (before any send): the restart marks the key UNKNOWN (pre_send_without_result_at_startup), "
          "halts new entries, the re-delivered command is a DUPLICATE: zero sends",
          b.ea.last(kh, "UNKNOWN") == {"reason": "pre_send_without_result_at_startup"} and b.ea.haltNew and b.t.writes == []
          and b.ea.states(kh).count("SEEN") == 1 and b.ea.unknownKey == kh, str(b.ea.states(kh)))
    b.close()
    b = Box()
    b.t.send_mode = "fill_lost_reply"
    kh = fill(b)
    unk = b.ea.last(kh, "UNKNOWN")
    b.restart()
    det = (b.ea.last(kh, "UNKNOWN_CHECK") or {}).get("detected")
    kh2 = b.cmd(bc=BC + 300000)
    b.t.gmt_ms = BC + 300000 + 2000
    b.timer()
    check("EAM-15 filled but the reply was lost (10031): UNKNOWN + halt; after a restart the history check finds the order / deal / open "
          "position (detected=open) but does NOT adopt it automatically; the next ENTRY stays blocked (unknown_unresolved), never a second order",
          unk == {"reason": "retcode_10031"} and det == "open" and not b.ea.hasPos
          and (b.ea.last(kh2, "SKIPPED") or {}).get("reason") == "unknown_unresolved:" + kh and len(b.sends()) == 1, str((unk, det)))
    b.close()
    b = Box()
    b.t.send_mode = "placed"
    kh = fill(b)
    det, _, _ = b.ea.detect_unknown(kh, b.ea.unknownPreMs)
    check("EAM-16 OrderSend returning true is not a fill: retcode PLACED (no deal / position) -> UNKNOWN + halt, not FILLED; the history "
          "check reports it as ambiguous (a pending order with the key's tag)",
          "FILLED" not in b.ea.states(kh) and b.ea.last(kh, "UNKNOWN") is not None and b.ea.haltNew and det == "ambiguous:pending_order",
          str((b.ea.states(kh), det)))
    b.close()


def gate_protect():
    b = Box()
    b.t.send_mode = "fill_no_sl"
    kh = fill(b)
    st = b.ea.states(kh)
    closes = [w for w in b.t.writes if w[0] == "close"]
    tk = b.ea.pos.posTicket
    b.timer()
    check("EAM-17 the initial SL is missing on the filled position: SL_MISSING, new entries halt, emergency close of the OWN position (by its "
          "ticket) -> CLOSE_DONE verified on the position and its history -> EMERGENCY_CLOSE closed_confirmed; the next timer records CLOSED",
          "SL_MISSING" in st and b.ea.last(kh, "EMERGENCY_CLOSE") == {"result": "closed_confirmed"} and b.ea.haltNew and len(closes) == 1
          and closes[0][1]["position"] == tk and tk not in b.t.positions and "CLOSED" in b.ea.states(kh) and not b.ea.critical, str(st))
    b.close()
    b = Box()
    b.t.send_mode, b.t.close_mode = "fill_no_sl", "reject"
    kh = fill(b)
    crit = (b.ea.critical, b.ea.last(kh, "CRITICAL"))
    b.touch("resume_new")
    b.timer()
    refused = "RESUME_REFUSED" in b.ea.states("")
    b.t.close_mode = "ok"
    b.restart()
    persists = b.ea.critical
    b.timer()                                     # after the restart: SL still missing -> the emergency close is retried and succeeds
    closed_after_restart = b.ea.last(kh, "EMERGENCY_CLOSE")
    b.touch("clear_critical")
    b.timer()
    cleared = (b.ea.critical, b.ea.haltNew)
    check("EAM-18 the emergency close is rejected: CLOSE_FAILED + CRITICAL emergency_close_failed (never reported as success), resume_new is "
          "refused, CRITICAL survives a restart; after the restart the missing SL is detected again and the close retried (closed_confirmed); "
          "only clear_critical clears CRITICAL and new entries stay halted until resume_new",
          crit[0] and crit[1] == {"reason": "emergency_close_failed"} and refused and persists
          and closed_after_restart == {"result": "closed_confirmed"} and cleared == (False, True), str((crit, cleared, closed_after_restart)))
    b.close()
    b = Box()
    kh = fill(b)
    p = b.own()
    tp_at_fill = p["tp"]
    fo = fill_bar(b)
    b.at_srv(fo + 299)
    b.timer()
    before = (p["tp"], [w for w in b.t.writes if w[0] == "sltp"])
    b.at_srv(fo + 300)
    b.timer()
    tp = b.ea.last(kh, "TP_SET")
    check("EAM-19 TP: none at the fill (request TP 0); still none 1 s before the fill-bar close; at the fill-bar close (the normal version's "
          "fill confirmation) TP0 2592.50 is set with the SL kept (2605.00)",
          tp_at_fill == 0.0 and before == (0.0, []) and p["tp"] == 2592.5 and p["sl"] == 2605.0 and tp == {"tp": "2592.50", "sl_kept": "2605.00"},
          str((before, tp)))
    b.close()
    b = Box()
    kh = fill(b)
    p = b.own()
    b.t.modify_mode = "reject"
    fo = fill_bar(b)
    for s in (300, 301, 302, 400):
        b.at_srv(fo + s)
        b.timer()
    n_same_bar = len([w for w in b.t.writes if w[0] == "sltp"])
    b.t.modify_mode = "ok"
    b.at_srv(fo + 600)
    b.timer()
    check("EAM-20 the TP0 change is rejected: MODIFY_FAILED (sl_kept 2605), new entries halt, the SL is untouched; it is retried once per M5 "
          "bar (1 attempt during the rest of the bar, not every timer) and succeeds on the next bar",
          n_same_bar == 1 and b.ea.last(kh, "MODIFY_FAILED") == {"what": "tp0", "retcode": "10016", "sl_kept": "2605.00000"}
          and b.ea.haltNew and p["sl"] == 2605.0 and p["tp"] == 2592.5, str(b.ea.states(kh)))
    b.close()


def gate_be():
    res = {}
    for nm, ticks, bars, fb in (("prefill_low", [(-1000, 2580.0), (500, 2596.0)], [], "TICKS_SINCE_FILL"),
                                ("fill_bar_ticks", [(500, 2590.0), (900, 2585.2)], [], "TICKS_SINCE_FILL"),
                                ("fill_bar_skip", [(500, 2585.2)], [], "SKIP"),
                                ("next_bar_15.0", [], [(300, 2585.2)], "TICKS_SINCE_FILL"),
                                ("next_bar_14.99", [], [(300, 2585.21)], "TICKS_SINCE_FILL"),
                                ("unclosed_bar", [], [(600, 2580.0)], "TICKS_SINCE_FILL")):
        b = Box(FillBarBe=fb)
        kh = fill(b)
        p = b.own()
        fo = fill_bar(b)
        b.t.ticks = [(p["time_msc"] + dt, bid) for dt, bid in ticks]
        b.t.rates = [(fo + off, low) for off, low in bars]
        b.at_srv(fo + 600 + 10)                    # fill bar and the next bar closed; the bar at +600 is open
        b.timer()
        res[nm] = (b.ea.last(kh, "BE_SET"), p["sl"])
        b.close()
    check("EAM-21 breakeven Fixed Distance 15 USD from the XS FILL (2600.20) -> SL = the XS fill: a tick before the fill (2580) is never used; "
          "the fill bar uses only the Bid ticks after the fill (2585.20 -> BE) unless FillBarBe=SKIP; a later closed M5 bar low 2585.20 "
          "(15.00) -> BE, 2585.21 (14.99) -> none; a bar that has not closed is never used",
          res["prefill_low"] == (None, 2605.0) and res["fill_bar_ticks"][1] == 2600.2 and res["fill_bar_skip"] == (None, 2605.0)
          and res["next_bar_15.0"][1] == 2600.2 and res["next_bar_15.0"][0]["sl"] == "2600.20" and res["next_bar_14.99"] == (None, 2605.0)
          and res["unclosed_bar"] == (None, 2605.0), str(res))
    b = Box()
    kh = fill(b)
    p = b.own()
    fo = fill_bar(b)
    b.at_srv(fo + 300)
    b.timer()                                      # TP0 set
    b.t.modify_mode = "reject"
    b.t.rates = [(fo + 300, 2584.0), (fo + 600, 2599.0)]
    b.at_srv(fo + 600 + 5)
    b.timer()
    failed = (b.ea.last(kh, "MODIFY_FAILED"), p["sl"], b.ea.pos.bePending)
    b.t.modify_mode = "ok"
    b.at_srv(fo + 900 + 5)
    b.timer()
    check("EAM-22 the breakeven change is rejected: MODIFY_FAILED, new entries halt, the SL stays 2605 (never deleted / loosened); the "
          "breakeven stays pending and is retried on the next closed bar even though that bar's low (2599) alone would not trigger it",
          failed[0]["what"] == "breakeven" and failed[1] == 2605.0 and failed[2] and p["sl"] == 2600.2 and b.ea.last(kh, "BE_SET") is not None
          and b.ea.haltNew, str(failed))
    b.close()
    b = Box()
    kh = fill(b)
    p = b.own()
    p["sl"] = 2599.0                               # someone moved the SL below the fill already
    fo = fill_bar(b)
    b.t.rates = [(fo + 300, 2584.0)]
    b.at_srv(fo + 600 + 5)
    b.timer()
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
        b.timer()
        res[ev] = (b.ea.last(kx, "SKIPPED"), len(b.t.writes) - n0, b.ea.pos.posTicket in b.t.positions)
        b.close()
    check("EAM-24 TradingView's management / exit events never act on MT5: even if one reached the EA as a command (the bridge never "
          "forwards them) it is SKIPPED not_entry with zero writes and the own position stays open with its own SL / TP / breakeven",
          all(v == ({"reason": "not_entry"}, 0, True) for v in res.values()), str(res))
    b = Box()
    b.t.bid, b.t.ask = 2592.45, 2592.75
    kh = fill(b, px=2593.0, sl=2598.0, tp=2592.5)
    tk = b.ea.pos.posTicket
    fo = fill_bar(b)
    b.at_srv(fo + 300)
    b.timer()
    check("EAM-25 CLOSE_REQ equivalent re-checked with the XS fill: the XS fill 2592.45 is already beyond TP0 2592.50 -> FILL_SIDE_BAD and the "
          "OWN position is closed at the fill-bar close (CLOSE_DONE verified; decided by the XS fill / real position, not by TradingView)",
          "FILL_SIDE_BAD" in b.ea.states(kh) and b.ea.last(kh, "CLOSE_DONE") is not None and tk not in b.t.positions, str(b.ea.states(kh)))
    b.close()


def gate_restart_misc():
    b = Box()
    kh = fill(b)
    tk = b.ea.pos.posTicket
    p = b.own()
    b.t.ticks = [(p["time_msc"] - 500, 2570.0)]    # only a PRE-fill tick in the fill bar
    b.restart()
    own = (b.ea.hasPos, b.ea.pos.posTicket == tk, b.ea.pos.posId == p["identifier"], b.ea.pos.fill, b.ea.pos.sl0)
    fo = fill_bar(b)
    b.at_srv(fo + 300 + 5)
    b.timer()
    fill_bar_be = b.ea.last(kh, "BE_SET")
    b.ea.on_deinit()
    b.t.close_position(tk, 2605.0, "SL")
    b.ea = b._wire(em.EA(b.t, b.x, **b.kw))
    b.ea.on_init()
    b.timer()
    check("EAM-26 EA restart with its own position: re-adopted only from the journal FILLED record + the live position identifier (symbol + "
          "magic + SELL); the fill-bar breakeven reads the tick history after the fill (the pre-fill tick 2580 is never used); TP0 is still "
          "set; a position closed while the EA was off is recorded CLOSED from its history (reason sl)",
          own == (True, True, True, 2600.2, 2605.0) and fill_bar_be is None and b.ea.last(kh, "TP_SET") is not None
          and (b.ea.last(kh, "CLOSED") or {}).get("reason") == "sl", str((own, b.ea.states(kh))))
    b.close()
    b = Box()
    second = em.EA(b.t, b.x, DryRun=False, AllowNewEntries=True, ExpectedLogin=LOGIN, approvals=ALL)
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
    kv1 = b.cmd(bc=BC, key=f"{SID}|ENTRY|TV|{BC}", v="1")
    b.timer()
    rs = lambda k: (b.ea.last(k, "SKIPPED") or {}).get("reason")
    rpts = os.listdir(os.path.join(b.x, "rpt"))
    dup = sum(1 for n in rpts if "state=DUPLICATE" in open(os.path.join(b.x, "rpt", n)).read())
    check("EAM-28 commands: the same key twice -> one SEEN + DUPLICATE; a key hash that is not SHA-256(key)[:16] -> BAD_CMD (never processed); "
          "LIMIT -> limit_not_supported (never converted); NaN price -> price_not_finite; unaligned bar -> bar_time; Entry Timing CURRENT -> "
          "path_not_initial_settings; SL below the price -> price_geometry; another cfg hash -> cfg_mismatch; an old protocol command (v=1, "
          "no final go) -> cmd_version; every file moved to done/; no trade write",
          b.ea.states(kh).count("SEEN") == 1 and dup == 1 and "BAD_CMD" in b.ea.states("") and rs(kl) == "limit_not_supported"
          and rs(kn) == "price_not_finite" and rs(ka) == "bar_time" and rs(kc) == "path_not_initial_settings" and rs(kg) == "price_geometry"
          and rs(ks) == "cfg_mismatch" and rs(kv1) == "cmd_version" and os.listdir(os.path.join(b.x, "cmd")) == []
          and len([n for n in os.listdir(os.path.join(b.x, "done")) if n.endswith(".cmd")]) == 10 and b.t.writes == [],
          str([rs(k) for k in (kl, kn, ka, kc, kg, ks, kv1)]))
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
    n0 = len(b.t.writes)
    fo = fill_bar(b)
    b.at_srv(fo + 300)
    b.timer()
    b.timer()
    check("EAM-30 the account / server changes while running: ENV_LOST, every trade write stops (also SL / TP management: "
          "MANAGEMENT_BLOCKED once; the SL already on the position stays)",
          "ENV_LOST" in b.ea.states("") and len(b.t.writes) == n0 and b.ea.states(kh).count("MANAGEMENT_BLOCKED") == 1, str(b.ea.states("")))
    b.close()


def gate_dry_mgmt():
    b = Box()
    kh = fill(b)
    p = b.own()
    b.restart(DryRun=True)
    n0 = len(b.t.writes)
    fo = fill_bar(b)
    b.t.rates = [(fo + 300, 2580.0)]
    p["sl"] = 0.0                                   # even an unprotected own position: DRY_RUN writes nothing (journaled)
    b.at_srv(fo + 600 + 5)
    b.timer()
    check("EAM-31 DRY_RUN blocks EVERY trade write, also for an own position adopted after a restart: no TP0, no breakeven, no close "
          "(MANAGEMENT_BLOCKED is journaled; the server-side SL stays) — DRY_RUN is not the 'stop new entries' switch",
          len(b.t.writes) == n0 and p["tp"] == 0.0 and "MANAGEMENT_BLOCKED" in b.ea.states(kh), str(b.ea.states(kh)))
    b.close()


# ---- regressions of the ST3-1 review --------------------------------------------------------------------------------------
def gate_review():
    # 1. final go / no-go (EA side; the bridge side is eab_sim EAB-22..26)
    res = {}
    for nm, mode, ttl, hook in (("nogo", "revoked_after_claim:late:wait_already_ended:W1", 3000, None), ("silent", "silent", 3000, None),
                                ("go_expired", "GO", 3000, 4000)):
        b = Box()
        b.fb.mode, b.fb.ttl = mode, ttl
        if hook:
            b.ea.before_send_hook = lambda b=b, hook=hook: b.t.advance(hook)
        kh = b.cmd()
        b.timer()
        res[nm] = ((b.ea.last(kh, "SKIPPED") or b.ea.last(kh, "SEND_ABORTED") or {}).get("reason"), len(b.sends()))
        b.close()
    check("EAR-01 (review 1) a claim is not a permission: the EA sends only with the bridge's final GO. NOGO (e.g. the wait ended after the "
          "claim) -> SKIPPED nogo:<reason>; no answer within ASK_WAIT_MS -> nogo:no_answer; a GO that expired before the send -> "
          "SEND_ABORTED go_expired; zero sends in every case",
          res == {"nogo": ("nogo:revoked_after_claim:late:wait_already_ended:W1", 0), "silent": ("nogo:no_answer", 0),
                  "go_expired": ("go_expired", 0)}, str(res))
    # 2. required records and the checks after the PRE_SEND record
    res = {}
    cases = (("pre_send_fails", dict(fail={"PRE_SEND"})), ("seen_fails", dict(fail={"SEEN"})),
             ("record_takes_2s_at_59", dict(at=59000, delay={"PRE_SEND": 2000}, ttl=10000)),
             ("pending_after_record", dict(hook=lambda b: b.t.orders.update({99: dict(symbol="XAUUSDs", comment="")}))),
             ("halt_file_after_record", dict(hook=lambda b: b.touch("halt_new"))),
             ("spread_after_record", dict(hook=lambda b: setattr(b.t, "ask", b.t.bid + 0.9))),
             ("balance_after_record", dict(hook=lambda b: b.t.account.update(balance=500000.0))),
             ("bid_moves_ok", dict(hook=lambda b: (setattr(b.t, "bid", 2600.21), setattr(b.t, "ask", 2600.51)))))
    for nm, c in cases:
        b = Box()
        b.ea.journal_fail_states = c.get("fail", set())
        b.ea.journal_delay = c.get("delay", {})
        if "at" in c:
            b.t.gmt_ms = BC + c["at"]
        if "ttl" in c:
            b.fb.ttl = c["ttl"]
        if "hook" in c:
            b.ea.before_send_hook = lambda b=b, h=c["hook"]: h(b)
        kh = b.cmd()
        b.timer()
        res[nm] = (b.ea.states(kh).count("PRE_SEND"), (b.ea.last(kh, "SEND_ABORTED") or {}).get("reason"), len(b.sends()),
                   b.sends()[0][1]["price"] if b.sends() else None, b.fb.asks)
        if nm == "pre_send_fails":
            fb_ = open(os.path.join(b.x, "journal_fallback.txt")).read()
            res[nm] += (b.ea.critical, b.ea.haltNew, "|PRE_SEND|" in fb_)
        b.close()
    check("EAR-02 (review 2) no order without its PRE_SEND record and nothing old is sent: PRE_SEND write fails -> zero sends, CRITICAL "
          "journal_write_failed + halt, the line kept in journal_fallback.txt; SEEN write fails -> not even asked; after the record the "
          "deadline / halt file / pending orders / spread / balance are checked again and the request rebuilt from the current market: "
          "record taking 2 s at 59 s -> SEND_ABORTED expired; a pending order or halt_new appearing -> aborted; spread 0.90 -> aborted; "
          "balance halved (volume would change) -> request_changed; a small Bid move with the same volume -> sent at the CURRENT Bid",
          res["pre_send_fails"] == (0, None, 0, None, 1, True, True, True) and res["seen_fails"][2:] == (0, None, 0)
          and res["record_takes_2s_at_59"][:3] == (1, "expired", 0) and res["pending_after_record"][1:3] == ("max1_pending_order_exists", 0)
          and res["halt_file_after_record"][1:3] == ("halt_file", 0) and res["spread_after_record"][1:3] == ("spread:0.900", 0)
          and res["balance_after_record"][1:3] == ("request_changed", 0) and res["bid_moves_ok"][1:4] == (None, 1, 2600.21), str(res))
    b = Box()
    kh = fill(b)
    p = b.own()
    b.ea.journal_fail_states = {"*"}               # the journal breaks while an own position is open
    p["sl"] = 0.0                                  # and the position loses its SL
    b.timer()
    fbk = open(os.path.join(b.x, "journal_fallback.txt")).read()
    check("EAR-02b a broken journal never leaves an unprotected own position alone: the emergency close is still sent and verified (the "
          "position is gone), the records go to journal_fallback.txt; new entries stay blocked (journal_write_failed / critical)",
          p["ticket"] not in b.t.positions and [w[0] for w in b.t.writes].count("close") == 1 and "|CLOSE_PRE_SEND|" in fbk
          and "|CLOSE_DONE|" in fbk and b.ea.new_entries_allowed().startswith(("journal_write_failed", "critical")), fbk[-300:])
    b.close()
    # 3. ownership mismatch
    b = Box()
    kh = fill(b)
    tk = b.ea.pos.posTicket
    b.ea.on_deinit()
    b.t.positions[tk]["magic"] = 777               # the same identifier now carries another magic
    b.t.positions[tk]["sl"] = 0.0
    b.ea = b._wire(em.EA(b.t, b.x, **b.kw))
    b.ea.on_init()
    fo = fill_bar(b) if False else b.t.positions[tk]["time"] - b.t.positions[tk]["time"] % 300
    b.at_srv(fo + 300)
    n0 = len(b.t.writes)
    b.timer()
    b.timer()
    q1 = (b.ea.last(kh, "QUARANTINE"), b.ea.critical, b.ea.hasPos, len(b.t.writes) - n0, tk in b.t.positions)
    b.close()
    b = Box()
    kh = fill(b)
    p = b.own()
    p["magic"] = 4242                              # changes while managed
    fo = fill_bar(b)
    b.at_srv(fo + 300)
    n0 = len(b.t.writes)
    b.timer()
    q2 = ((b.ea.last(kh, "QUARANTINE") or {}).get("reason"), len(b.t.writes) - n0, p["tp"])
    b.close()
    b = Box()
    kh = fill(b)
    b.restart(ExpectedCfgSha="1" * 64)             # the journal belongs to another Strategy setting
    b.cmd(bc=BC + 300000, cfg_sha256="1" * 64)
    b.t.gmt_ms = BC + 300000 + 2000
    n0 = len(b.t.writes)
    b.timer()
    q3 = (b.ea.bindOk, "BIND_MISMATCH" in b.ea.states(""), len(b.t.writes) - n0)
    b.close()
    b = Box()
    kh = fill(b)
    b.ea.on_deinit()
    b.t.account["login"] = 7654321                 # another demo account on the same PC / folder
    b.ea = b._wire(em.EA(b.t, b.x, **dict(b.kw, ExpectedLogin=7654321)))
    b.ea.on_init()
    q4 = (b.ea.hasPos, os.path.basename(b.ea.journalPath))
    b.close()
    check("EAR-03 (review 3) ownership: a journal FILLED record whose identifier now holds another magic -> QUARANTINE + CRITICAL after the "
          "restart, nothing written to it (no close / SL / TP) and it stays open; the same mismatch appearing while managed -> QUARANTINE "
          "before the TP0 change (zero writes); a journal bound to another Strategy (BIND cfg differs) -> BIND_MISMATCH, every trade write "
          "refused; another account's journal is another file (journal_<login>_<server>_<magic>.txt) and is never adopted",
          q1[0] is not None and q1[0]["reason"] == "ownership_mismatch" and q1[1:] == (True, False, 0, True)
          and q2 == ("ownership_mismatch", 0, 0.0) and q3 == (False, True, 0)
          and q4 == (False, "journal_7654321_XSFintech-DEMO_26102801.txt"), str((q1, q2, q3, q4)))
    # 4. unknown result: resume_new never clears it; resolve_unknown must match the history check
    b = Box()
    b.t.send_mode = "timeout"
    kh = fill(b)
    b.touch("resume_new")
    b.timer()
    r1 = ((b.ea.last("", "RESUME_REFUSED") or {}).get("reason"), b.ea.unknownKey == kh, b.ea.new_entries_allowed())
    b.touch("resolve_unknown", f"key_hash={kh}\nconfirm=open\n")
    b.timer()
    r2 = (b.ea.last(kh, "UNKNOWN_RESOLVE_REFUSED"), b.ea.unknownKey == kh)
    b.touch("resolve_unknown", f"key_hash={'f' * 16}\nconfirm=none\n")
    b.timer()
    b.touch("resolve_unknown", f"key_hash={kh}\nconfirm=none\n")
    b.timer()
    r3 = (b.ea.last(kh, "UNKNOWN_RESOLVED"), b.ea.unknownKey, b.ea.new_entries_allowed())
    b.touch("resume_new")
    b.timer()
    r4 = b.ea.new_entries_allowed()
    b.close()
    check("EAR-04 (review 4) an unknown result is never cleared by an empty resume_new (RESUME_REFUSED unknown_unresolved, the gate stays "
          "closed); resolve_unknown is accepted only for the unknown key AND when its confirm equals the history check (confirm=open while "
          "nothing exists -> refused; another key -> refused; confirm=none -> UNKNOWN_RESOLVED); new entries still need resume_new afterwards",
          r1[0] == "unknown_unresolved" and r1[1] and r1[2] == "unknown_unresolved:" + kh
          and r2[0] == {"reason": "confirm_mismatch", "confirm": "open", "detected": "none"} and r2[1]
          and r3[0] == {"result": "none", "position_id": "0", "note": "new_entries_stay_halted_until_resume_new"} and r3[1] == ""
          and r3[2].startswith("halt_new") and r4 == "", str((r1, r2, r3, r4)))
    b = Box()
    b.t.send_mode = "fill_lost_reply"
    kh = fill(b)
    tk = max(b.t.positions)
    b.t.positions[tk]["sl"] = 0.0                  # found position without its SL
    b.touch("resolve_unknown", f"key_hash={kh}\nconfirm=open\n")
    b.timer()
    o1 = (b.ea.last(kh, "UNKNOWN_RESOLVED"), (b.ea.last(kh, "FILLED") or {}).get("via"), b.ea.last(kh, "EMERGENCY_CLOSE"), tk in b.t.positions)
    b.close()
    b = Box()
    b.t.send_mode = "fill_lost_reply"
    kh = fill(b)
    tk = max(b.t.positions)
    b.touch("resolve_unknown", f"key_hash={kh}\nconfirm=open\n")
    b.timer()
    fo = b.t.positions[tk]["time"] - b.t.positions[tk]["time"] % 300
    b.at_srv(fo + 300)
    b.timer()
    o2 = (b.ea.hasPos, b.ea.last(kh, "PROTECTED") is not None, b.t.positions[tk]["tp"])
    b.close()
    b = Box()
    b.t.send_mode = "fill_lost_reply"
    kh = fill(b)
    b.t.close_position(max(b.t.positions), 2605.0, "SL")
    b.touch("resolve_unknown", f"key_hash={kh}\nconfirm=closed\n")
    b.timer()
    o3 = (b.ea.last(kh, "UNKNOWN_RESOLVED") or {}).get("result")
    b.close()
    b = Box()
    b.t.send_mode = "placed"
    kh = fill(b)
    b.touch("resolve_unknown", f"key_hash={kh}\nconfirm=none\n")
    b.timer()
    o4 = (b.ea.last(kh, "UNKNOWN_RESOLVE_REFUSED") or {}).get("detected")
    b.close()
    check("EAR-04b resolution by the history check: an order that filled but whose reply was lost -> detected open; confirm=open adopts it "
          "by its identifier (FILLED via=unknown_resolution) and checks its SL at once (missing -> emergency close), otherwise it is managed "
          "normally (PROTECTED, TP0 at the fill-bar close); closed meanwhile -> confirm=closed; a pending order with the tag -> ambiguous, "
          "never resolvable by a file",
          o1[0] is not None and o1[0]["result"] == "open" and o1[1] == "unknown_resolution" and o1[2] == {"result": "closed_confirmed"}
          and o1[3] is False and o2 == (True, True, 2592.5) and o3 == "closed" and o4 == "ambiguous:pending_order", str((o1, o2, o3, o4)))
    # 5. the fill bar never sees the next bar
    res = {}
    for nm, ticks, timers in (("next_bar_first_tick_16", [(400, 2595.2), ("close", 2584.2)], ["close+1"]),
                              ("tick_exactly_at_close", [(400, 2595.2), ("close+0", 2584.0)], ["close+0", "close+1"]),
                              ("tick_1ms_before_close", [("close-1", 2585.0)], ["close+0"]),
                              ("tick_same_ms_as_fill", [(0, 2584.0)], ["close+0"]),
                              ("timer_before_next_tick", [(400, 2595.2)], ["close+0", "add:2584.2", "close+2"])):
        b = Box()
        kh = fill(b)
        p = b.own()
        fo = fill_bar(b)
        close_ms = (fo + 300) * 1000
        for dt, bid in ticks:
            tm = (p["time_msc"] + dt) if isinstance(dt, int) else close_ms + (int(dt[5:]) if dt[5:] else 0)
            b.t.ticks.append((tm, bid))
        for tmr in timers:
            if tmr.startswith("add:"):
                b.t.ticks.append((close_ms + 500, float(tmr[4:])))
                continue
            b.t.gmt_ms = close_ms + int(tmr[6:]) * 1000 - b.t.server_offset * 1000
            b.timer()
        res[nm] = (b.ea.last(kh, "BE_SET") or {}).get("fav")
        b.close()
    b = Box()
    kh = fill(b)
    fo = fill_bar(b)
    b.t.ticks_unavailable = True
    b.at_srv(fo + 300)
    b.timer()
    w1 = b.ea.pos.fillBarDone
    b.t.ticks_unavailable = False
    b.t.ticks = [(b.own()["time_msc"] + 1000, 2584.9)]
    b.at_srv(fo + 310)
    b.timer()
    w2 = (b.ea.last(kh, "BE_SET") or {}).get("fav")
    b.close()
    check("EAR-05 (review 5) the fill-bar breakeven uses only ticks strictly after the fill and strictly before the fill-bar close (server "
          "ms): the fill bar moved 5.0, the next bar's first tick 16.0 -> no BE on the fill bar; a tick exactly at the close belongs to the "
          "next bar; a tick 1 ms before the close counts (15.2); a tick in the same ms as the fill is excluded; the order of ticks and timers "
          "at the boundary does not matter; tick history not ready yet -> retried, then evaluated",
          res == {"next_bar_first_tick_16": None, "tick_exactly_at_close": None, "tick_1ms_before_close": "2585.00",
                  "tick_same_ms_as_fill": None, "timer_before_next_tick": None} and w1 is False and w2 == "2584.90", str((res, w1, w2)))
    # 6. partial emergency close
    b = Box()
    b.t.send_mode, b.t.close_mode = "fill_no_sl", "partial"
    kh = fill(b)
    p = b.own()
    s1 = (b.ea.last(kh, "EMERGENCY_CLOSE_PARTIAL"), b.ea.critical, b.ea.last(kh, "EMERGENCY_CLOSE"), p["volume"], b.ea.hasPos)
    b.t.close_mode = "ok"
    b.t.advance(1000)
    b.timer()                                      # within EMERGENCY_RETRY_SEC: no second attempt yet
    n_close_1s = [w[0] for w in b.t.writes].count("close")
    b.t.advance(5000)
    b.timer()
    s2 = (b.ea.last(kh, "EMERGENCY_CLOSE"), p["ticket"] in b.t.positions)
    b.timer()
    s3 = "CLOSED" in b.ea.states(kh)
    b.close()
    b = Box()
    b.t.send_mode, b.t.close_mode = "fill_no_sl", "timeout_no_change"
    kh = fill(b)
    s4 = ((b.ea.last(kh, "CRITICAL") or {}).get("reason"), b.ea.last(kh, "CLOSE_UNKNOWN") is not None)
    b.close()
    b = Box()
    kh = fill(b)
    b.ea.on_deinit()
    b.own()["sl"] = 0.0                            # the SL disappeared while the EA was off
    b.ea = b._wire(em.EA(b.t, b.x, **b.kw))
    b.ea.on_init()
    b.timer()
    s5 = (b.ea.last(kh, "SL_MISSING") is not None, b.ea.last(kh, "EMERGENCY_CLOSE"))
    b.close()
    check("EAR-06 (review 6) a partial emergency close is not a close: EMERGENCY_CLOSE_PARTIAL + CRITICAL emergency_close_partial, the "
          "unprotected remainder (0.21 of 0.41) stays owned and is closed on the next attempt after EMERGENCY_RETRY_SEC (not before) -> "
          "closed_confirmed, then CLOSED from the history; a close whose result cannot be told -> CLOSE_UNKNOWN + CRITICAL "
          "emergency_close_unknown; after a restart a missing SL is detected and the own position closed",
          s1[0] is not None and s1[1] and s1[2] is None and s1[3] == 0.21 and s1[4] and n_close_1s == 1
          and s2 == ({"result": "closed_confirmed"}, False) and s3 and s4 == ("emergency_close_unknown", True)
          and s5 == (True, {"result": "closed_confirmed"}), str((s1, n_close_1s, s2, s3, s4, s5)))
    # 7. position identifier vs ticket
    b = Box()
    b.t.ticket_offset = 1000
    kh = fill(b)
    f = b.ea.last(kh, "FILLED")
    p = b.own()
    t1 = (f["position_id"] != f["position"], b.ea.pos.posId == p["identifier"], "PROTECTED" in b.ea.states(kh))
    new_tk = p["ticket"] + 77                      # the live ticket changes, the identifier stays
    b.t.positions[new_tk] = dict(b.t.positions.pop(p["ticket"]), ticket=new_tk)
    fo = p["time"] - p["time"] % 300
    b.at_srv(fo + 300)
    b.timer()
    t2 = ("TICKET_CHANGED" in b.ea.states(kh), "CLOSED" not in b.ea.states(kh), b.t.positions[new_tk]["tp"], b.ea.pos.posTicket == new_tk)
    b.t.close_position(new_tk, 2592.5, "TP")
    b.timer()
    t3 = (b.ea.last(kh, "CLOSED") or {}).get("reason")
    b.close()
    b = Box()
    kh = fill(b)
    p = b.own()
    del b.t.positions[p["ticket"]]                 # not visible and NOT closed in the history
    b.timer()
    t4 = (b.ea.last(kh, "OWN_POSITION_MISSING") is not None, "CLOSED" not in b.ea.states(kh), b.ea.haltNew, b.ea.hasPos)
    b.close()
    check("EAR-07 (review 7) the position identifier (DEAL_POSITION_ID = POSITION_IDENTIFIER) and the ticket are kept apart: a fill whose "
          "ticket differs from its identifier is confirmed and protected; a ticket change is followed by identifier (TICKET_CHANGED, TP0 set "
          "on the new ticket, not 'closed'); CLOSED only from the identifier's history (tp); a position that vanished without a closing "
          "history is OWN_POSITION_MISSING (halt), never CLOSED",
          t1 == (True, True, True) and t2 == (True, True, 2592.5, True) and t3 == "tp" and t4 == (True, True, True, True), str((t1, t2, t3, t4)))
    # 8. approvals and monitoring
    b = Box(approvals=())
    kh = b.cmd()
    b.timer()
    a1 = ((b.ea.last(kh, "SKIPPED") or {}).get("reason"), b.t.writes, b.fb.asks)
    b.close()
    b = Box(approvals=ALL[:-1])
    kh = b.cmd()
    b.timer()
    a2 = (b.ea.last(kh, "SKIPPED") or {}).get("reason")
    b.close()
    b = Box(DryRun=True, approvals=())
    kh = b.cmd()
    b.timer()
    a3 = (b.ea.last(kh, "DRY_RUN_NOT_SENT") or {}).get("unapproved")
    b.close()
    b = Box()
    b.fb.alive = False
    kh = b.cmd()
    b.ea.on_timer()
    a4 = ((b.ea.last(kh, "SKIPPED") or {}).get("reason"), b.t.writes)
    b.close()
    b = Box()
    kh = fill(b)
    b.fb.alive = False                              # the bridge stops: the own position is still managed
    os.remove(os.path.join(b.x, "hb_bridge.txt"))
    fo = fill_bar(b)
    b.at_srv(fo + 300)
    b.ea.on_timer()
    hb = open(os.path.join(b.x, "hb_ea.txt")).read()
    a5 = (b.ea.last(kh, "TP_SET") is not None, "new_gate=" in hb, b.ea.new_entries_allowed())
    b.close()
    check("EAR-08 (review 8) unapproved proposals never trade: with no APPROVED_* (the source default) a valid ENTRY with DryRun=false is "
          "SKIPPED unapproved:be_price_source (no ask, no write); one missing approval (monitoring) is enough to refuse; DRY_RUN records the "
          "missing approvals; a stale / missing bridge heartbeat -> SKIPPED bridge_heartbeat_stale; with the bridge down the own position is "
          "still managed (TP0 set) and the EA keeps writing hb_ea.txt",
          a1 == ("unapproved:be_price_source", [], 0) and a2 == "unapproved:monitoring" and a3 == "be_price_source"
          and a4 == ("bridge_heartbeat_stale", []) and a5[0] and a5[1] and a5[2] == "max1_own_position", str((a1, a2, a3, a4, a5)))


def gate_rereview():
    """regressions of the ST3-2 re-review (items 1-4)."""
    # 1. the final PrepareOrder itself takes time / something changes during it
    res = {}
    for nm in ("delay_4s", "pending_order", "halt_new", "nothing_changes"):
        b = Box()
        b.t.gmt_ms = BC + 58000
        orig = b.ea.prepare_order
        calls = [0]

        def slow(c, b=b, nm=nm, orig=orig, calls=calls):
            r = orig(c)
            calls[0] += 1
            if calls[0] == 2:                       # the PrepareOrder of the final check, after the PRE_SEND record
                if nm == "delay_4s":
                    b.t.advance(4000)
                elif nm == "pending_order":
                    b.t.orders[99] = dict(symbol="XAUUSDs", comment="")
                elif nm == "halt_new":
                    b.touch("halt_new")
            return r
        b.ea.prepare_order = slow
        kh = b.cmd()
        b.timer()
        res[nm] = (len(b.sends()), (b.ea.last(kh, "SEND_ABORTED") or {}).get("reason"), b.ea.inflightKey)
        b.close()
    check("EAR-09 (re-review 1) the slow final PrepareOrder (OrderCheck) runs BEFORE the last checks: a 4 s delay inside it (ENTRY + 62 s, "
          "past the GO validity) -> SEND_ABORTED expired; a pending order or halt_new appearing during it -> aborted; zero sends; without "
          "a change the order is still sent once",
          res == {"delay_4s": (0, "expired", ""), "pending_order": (0, "max1_pending_order_exists", ""), "halt_new": (0, "halt_file", ""),
                  "nothing_changes": (1, None, "")}, str(res))
    # 2. FILL_SIDE_BAD: every close result handled, the obligation persists
    res = {}
    for mode in ("partial", "reject", "timeout_no_change", "ok"):
        b = Box()
        b.t.bid, b.t.ask = 2592.45, 2592.75
        kh = fill(b, px=2593.0, sl=2598.0, tp=2592.5)
        tk = b.ea.pos.posTicket
        b.t.close_mode = mode
        fo = fill_bar(b)
        b.at_srv(fo + 300)
        b.timer()
        n1 = [w[0] for w in b.t.writes].count("close")
        b.t.advance(1000)
        b.timer()
        n2 = [w[0] for w in b.t.writes].count("close")
        b.t.advance(5000)
        b.timer()
        n3 = [w[0] for w in b.t.writes].count("close")
        res[mode] = ((b.ea.last(kh, "CRITICAL") or {}).get("reason"), b.ea.haltNew, (n1, n2, n3), tk in b.t.positions,
                     b.ea.last(kh, "CLOSE_REQUIRED"), "CLOSED" in b.ea.states(kh))
        b.close()
    check("EAR-10 (re-review 2) FILL_SIDE_BAD requires a close (CLOSE_REQUIRED reason=bad_fill_side_mt5) whose result is handled: partial / "
          "rejected / unknown -> halt + CRITICAL close_<partial|failed|unknown>:bad_fill_side_mt5, the remainder is retried after "
          "EMERGENCY_RETRY_SEC (not 1 s later, not only at the next bar); a full close -> no CRITICAL, CLOSED from the history",
          res["partial"][:3] == ("close_partial:bad_fill_side_mt5", True, (1, 1, 2)) and res["partial"][3]
          and res["reject"][:4] == ("close_failed:bad_fill_side_mt5", True, (1, 1, 2), True)
          and res["timeout_no_change"][:4] == ("close_unknown:bad_fill_side_mt5", True, (1, 1, 2), True)
          and res["ok"][0] is None and res["ok"][2][0] == 1 and res["ok"][3] is False and res["ok"][5]
          and all(v[4] == {"reason": "bad_fill_side_mt5", "position_id": v[4]["position_id"]} for v in res.values()), str(res))
    b = Box()
    b.t.bid, b.t.ask = 2592.45, 2592.75
    kh = fill(b, px=2593.0, sl=2598.0, tp=2592.5)
    tk = b.ea.pos.posTicket
    b.t.close_mode = "reject"
    fo = fill_bar(b)
    b.at_srv(fo + 300)
    b.timer()
    b.restart()                                    # the close obligation survives the restart
    restored = b.ea.pos.closeReason
    b.t.close_mode = "ok"
    b.timer()
    b.timer()
    after = (tk in b.t.positions, b.ea.last(kh, "CLOSE_CONFIRMED"), "CLOSED" in b.ea.states(kh), b.t.positions.get(tk, {}).get("tp"))
    b.close()
    check("EAR-10b (re-review 2) a required close that was rejected is restored after an EA restart (closeReason from CLOSE_REQUIRED) and "
          "retried at once; no TP0 is set on a position that must be closed; after the full close CLOSE_CONFIRMED then CLOSED",
          restored == "bad_fill_side_mt5" and after == (False, {"result": "closed_confirmed", "reason": "bad_fill_side_mt5"}, True, None),
          str((restored, after)))
    # 3. a later deal of the same order changes the live volume / average price
    def later_deal(b, p, dt_ms, price, add):
        tot = round(p["volume"] + add, 2)
        p["price_open"] = round((p["price_open"] * p["volume"] + price * add) / tot, 5)
        p["volume"] = tot
        d = b.t._ticket()
        b.t.deals[d] = dict(order=b.ea.pos.orderTicket, position=p["identifier"], price=price, time=p["time"] + dt_ms // 1000,
                            time_msc=p["time_msc"] + dt_ms, entry="IN", volume=add, symbol="XAUUSDs", magic=p["magic"],
                            comment=p["comment"], reason="EXPERT", profit=0.0, commission=0.0, swap=0.0)
    b = Box()
    b.t.send_mode = "partial"
    kh = fill(b)
    p = b.own()
    later_deal(b, p, 20000, 2601.0, 0.20)          # 0.20 @ 2600.20 + 0.20 @ 2601.00 = 0.40 @ 2600.60
    fo = fill_bar(b)
    b.t.rates = [(fo + 300, 2585.50)]
    b.at_srv(fo + 600 + 5)
    b.timer()
    u = b.ea.last(kh, "POSITION_UPDATED")
    r1 = (b.ea.pos.volume, b.ea.pos.fill, (b.ea.last(kh, "BE_SET") or {}).get("sl"), p["sl"])
    b.restart()
    r2 = (b.ea.pos.volume, b.ea.pos.fill, b.ea.pos.lastInMsc == p["time_msc"] + 20000, b.ea.states(kh).count("POSITION_UPDATED"))
    b.close()
    b = Box()
    b.t.send_mode = "partial"
    kh = fill(b)
    p = b.own()
    b.ea.on_deinit()
    later_deal(b, p, 20000, 2601.0, 0.20)          # while the EA is off
    b.ea = b._wire(em.EA(b.t, b.x, **b.kw))
    b.ea.on_init()
    r3 = (b.ea.pos.volume, b.ea.pos.fill, (b.ea.last(kh, "POSITION_UPDATED") or {}).get("cause"))
    b.close()
    b = Box()
    b.t.send_mode = "partial"
    kh = fill(b)
    p = b.own()
    fo = fill_bar(b)
    later_deal(b, p, (fo + 300) * 1000 + 60000 - p["time_msc"], 2601.0, 0.20)   # the second part fills one minute into the NEXT bar
    b.t.ticks = [(p["time_msc"] + 1000, 2584.0)]   # a 16 USD move in the fill bar, BEFORE the second part filled
    b.t.rates = [(fo + 300, 2585.0), (fo + 600, 2590.0)]   # the next bar's low may precede the second part
    b.at_srv(fo + 900 + 5)
    b.timer()
    r4 = (b.ea.last(kh, "BE_SET"), b.ea.last(kh, "FILLBAR_NO_TICKS"))
    b.close()
    check("EAR-11 (re-review 3) a later deal of the same order (same identifier) is followed: POSITION_UPDATED cause=add, the EA's volume / "
          "fill become the live 0.40 @ 2600.60, the bar low 2585.50 (15.10 from the average) moves the SL to 2600.60; the update is restored "
          "from the journal after a restart (no second POSITION_UPDATED when nothing changed) (and one that happened while the EA was off is recorded at start); no price before the last IN deal is used: "
          "neither the fill-bar ticks nor the bar holding the later deal -> no breakeven from them; no top-up order",
          u is not None and u["cause"] == "add" and u["volume"] == "0.40" and u["fill_price"] == "2600.60000"
          and r1 == (0.4, 2600.6, "2600.60", 2600.6) and r2 == (0.4, 2600.6, True, 1) and r3 == (0.4, 2600.6, "add")
          and r4 == (None, {"n": "0"}), str((u, r1, r2, r3, r4)))
    # 4. a met breakeven condition survives a restart; tick history not available is not "not met"
    b = Box()
    kh = fill(b)
    p = b.own()
    fo = fill_bar(b)
    b.t.ticks = [(p["time_msc"] + 1000, 2584.2)]   # 16 USD in the fill bar after the fill
    b.t.modify_mode = "reject"
    b.at_srv(fo + 300)
    b.timer()
    before = (b.ea.pos.bePending, b.ea.last(kh, "BE_TRIGGERED") is not None, p["sl"])
    b.restart()
    pend_after = b.ea.pos.bePending
    b.t.ticks_unavailable = True
    b.t.rates = [(fo + 300, 2599.2)]               # the next bar moves only 1 USD
    b.at_srv(fo + 600 + 5)
    b.timer()                                      # still refused: stays pending, SL kept
    still = (b.ea.pos.bePending, p["sl"], b.ea.last(kh, "FILLBAR_NO_TICKS"))
    b.t.modify_mode = "ok"
    b.at_srv(fo + 900 + 5)
    b.timer()
    after = ((b.ea.last(kh, "BE_SET") or {}).get("sl"), p["sl"], b.ea.pos.bePending)
    b.close()
    b = Box()
    kh = fill(b)
    p = b.own()
    fo = fill_bar(b)
    b.t.ticks = [(p["time_msc"] + 1000, 2584.2)]
    b.t.ticks_unavailable = True
    b.at_srv(fo + 300)
    b.timer()
    b.at_srv(fo + 900 + 5)                         # two more bars later, still unavailable
    b.timer()
    u1 = (b.ea.pos.fillBarDone, b.ea.last(kh, "FILLBAR_TICKS_UNAVAILABLE") is not None, b.ea.last(kh, "FILLBAR_NO_TICKS"),
          b.ea.states(kh).count("FILLBAR_TICKS_UNAVAILABLE"))
    b.t.ticks_unavailable = False
    b.at_srv(fo + 905)
    b.timer()
    u2 = ((b.ea.last(kh, "BE_SET") or {}).get("fav"), b.ea.pos.fillBarDone)
    b.close()
    check("EAR-12 (re-review 4) a met breakeven condition (BE_TRIGGERED, journaled before the SL change) whose change was refused stays "
          "pending across a restart (no tick re-reading needed), is retried once per bar (refused again: SL kept 2605, no FILLBAR_NO_TICKS) "
          "and applied when allowed although the later bars moved only 1 USD; tick history that cannot be read is FILLBAR_TICKS_UNAVAILABLE "
          "(once), never 'not met': the fill bar stays open and is evaluated when the history comes back",
          before == (True, True, 2605.0) and pend_after is True and still == (True, 2605.0, None) and after == ("2600.20", 2600.2, False)
          and u1 == (False, True, None, 1) and u2 == ("2584.20", True), str((before, pend_after, still, after, u1, u2)))


def gate_rereview2():
    """regressions of the ST3-3 re-review (items 1-2)."""
    # 1. a slow file read inside FinalGate
    res = {}
    for nm, start, delay in (("deadline", 58000, 4000), ("go_validity", 52000, 4000), ("no_expiry", 30000, 1000)):
        b = Box()
        b.t.gmt_ms = BC + start
        orig = b.ea.bridge_hb_age_ms
        done = [False]

        def slow(b=b, orig=orig, done=done, delay=delay):
            age = orig()
            if b.ea.inflightKey and not done[0]:       # the heartbeat file read inside FinalGate (after the PRE_SEND record)
                done[0] = True
                b.t.advance(delay)
            return age
        b.ea.bridge_hb_age_ms = slow
        kh = b.cmd()
        b.timer()
        res[nm] = (len(b.sends()), (b.ea.last(kh, "SEND_ABORTED") or {}).get("reason"), done[0])
        b.close()
    check("EAR-13 (ST3-3 re-review 1) a 4 s delay in FinalGate's own file read (hb_bridge.txt, the heartbeat itself still fresh): started at "
          "58 s -> SEND_ABORTED expired; started at 52 s with a 3 s GO -> SEND_ABORTED go_expired; zero sends. The deadline and the GO "
          "validity are checked after every read; a 1 s delay with nothing expired still sends once",
          res == {"deadline": (0, "expired", True), "go_validity": (0, "go_expired", True), "no_expiry": (1, None, True)}, str(res))

    def add_in(b, p, at_msc, price, vol, to_history=True):
        tot = round(p["volume"] + vol, 2)
        p["price_open"] = round((p["price_open"] * p["volume"] + price * vol) / tot, 5)
        p["volume"] = tot
        d = b.t._ticket()
        deal = dict(order=0, position=p["identifier"], price=price, time=at_msc // 1000, time_msc=at_msc, entry="IN", volume=vol,
                    symbol="XAUUSDs", magic=p["magic"], comment=p["comment"], reason="EXPERT", profit=0.0, commission=0.0, swap=0.0)
        if to_history:
            b.t.deals[d] = deal
        return d, deal

    def lost_reply_two_parts(ticks):
        """an order filled in two parts (0.20 @ 2600.20, 20 s later 0.20 @ 2601.00) whose reply was lost; adopted afterwards."""
        b = Box()
        b.t.send_mode = "fill_lost_reply"
        kh = fill(b)
        tk = max(b.t.positions)
        p = b.t.positions[tk]
        p["volume"] = 0.20
        for v_ in b.t.deals.values():
            if v_["position"] == p["identifier"]:
                v_["volume"] = 0.20
        F = p["time_msc"]
        b.t.ticks = [(F + dt, bid) for dt, bid in ticks]
        add_in(b, p, F + 20000, 2601.0, 0.20)
        b.t.advance(30000)
        b.touch("resolve_unknown", f"key_hash={kh}\nconfirm=open\n")
        b.timer()
        return b, kh, p, F

    # 2A. several IN deals before the adoption
    b, kh, p, F = lost_reply_two_parts([(5000, 2584.2), (25000, 2600.0)])
    fo = p["time"] - p["time"] % 300
    f_ = b.ea.last(kh, "FILLED")
    b.at_srv(fo + 300)
    b.timer()
    a1 = (f_["in_deals"], int(f_["last_in_msc"]) - F, f_["fill_sync"], b.ea.last(kh, "BE_SET"), p["sl"])
    b.close()
    b, kh, p, F = lost_reply_two_parts([(5000, 2584.2), (25000, 2585.5)])   # 15.10 from the average AFTER the second part
    fo = p["time"] - p["time"] % 300
    b.at_srv(fo + 300)
    b.timer()
    a2 = ((b.ea.last(kh, "BE_SET") or {}).get("fav"), p["sl"])
    b.close()
    # 2B. the live position changes first, the IN deal reaches the history later
    b = Box()
    b.t.send_mode = "partial"
    kh = fill(b)
    p = b.own()
    F = p["time_msc"]
    fo = p["time"] - p["time"] % 300
    b.t.ticks = [(F + 5000, 2584.2), (F + 25000, 2600.0)]
    d, deal = add_in(b, p, F + 20000, 2601.0, 0.20, to_history=False)
    b.t.advance(25000)
    b.timer()
    pend = (b.ea.pos.fillSyncPending, b.ea.last(kh, "FILL_HISTORY_PENDING") is not None, b.ea.pos.lastInMsc == F)
    b.at_srv(fo + 300)
    b.timer()                                       # the fill bar closes while the history still lags: no decision
    during = (b.ea.last(kh, "BE_SET"), b.ea.last(kh, "TP_SET"), b.ea.pos.fillBarDone)
    b.restart()                                     # a restart while it lags keeps waiting
    after_restart = b.ea.pos.fillSyncPending
    b.t.deals[d] = deal                             # the history arrives
    b.at_srv(fo + 305)
    b.timer()
    upd = b.ea.last(kh, "POSITION_UPDATED")
    b2 = (b.ea.pos.fillSyncPending, upd and upd["cause"], b.ea.pos.lastInMsc - F, b.ea.last(kh, "BE_SET"), p["sl"],
          b.ea.last(kh, "TP_SET") is not None)
    b.close()
    check("EAR-14 (ST3-3 re-review 2A/2B) the last IN deal comes from the history: adopted with 2 IN deals -> FILLED in_deals=2, "
          "last_in_msc = the second part (+20 s), the 16 USD before it is not used (no BE; SL stays 2605) while 15.10 after it is (BE at "
          "the average 2600.60); when the live position changes before its deal reaches the history -> FILL_HISTORY_PENDING, no "
          "breakeven / TP decision while it lags (also across a restart), then POSITION_UPDATED (cause=add: 0.20 -> 0.40) with the new last IN and still "
          "no BE from the earlier move; TP0 is set once the state is explained",
          a1 == ("2", 20000, "ok", None, 2605.0) and a2 == ("2585.50", 2600.6) and pend == (True, True, True)
          and during == (None, None, False) and after_restart is True and b2 == (False, "add", 20000, None, 2605.0, True),
          str((a1, a2, pend, during, after_restart, b2)))
    # 2C. a breakeven condition met before a later IN deal
    def pending_then_later_in(next_bar_low, restart=False):
        b = Box()
        b.t.send_mode = "partial"
        kh = fill(b)
        p = b.own()
        F = p["time_msc"]
        fo = p["time"] - p["time"] % 300
        b.t.ticks = [(F + 1000, 2584.2)]
        b.t.modify_mode = "reject"
        b.at_srv(fo + 300)
        b.timer()                                   # BE_TRIGGERED, refused, pending
        pend = b.ea.pos.bePending
        add_in(b, p, (fo + 330) * 1000, 2599.4, 0.20)   # 0.40 @ 2599.80, 30 s into the next bar
        b.t.modify_mode = "ok"
        if restart:
            b.restart()
        b.t.rates = [(fo + 300, 2580.0), (fo + 600, next_bar_low)]
        b.at_srv(fo + 900 + 5)
        b.timer()
        return b, kh, p, pend
    b, kh, p, pend = pending_then_later_in(2598.0)
    c1 = (pend, b.ea.last(kh, "BE_TRIGGER_VOID") is not None, b.ea.last(kh, "BE_SET"), p["sl"], b.ea.pos.bePending)
    b.close()
    b, kh, p, pend = pending_then_later_in(2584.7)              # 15.10 from the new average in the bar AFTER the later deal's bar
    c2 = ((b.ea.last(kh, "BE_SET") or {}).get("fav"), p["sl"], [x[2] for x in b.ea.journal_lines() if x[1] == kh].count("BE_TRIGGERED"))
    b.close()
    b, kh, p, pend = pending_then_later_in(2598.0, restart=True)
    c3 = (b.ea.pos.bePending, b.ea.last(kh, "BE_SET"), p["sl"], b.ea.last(kh, "BE_TRIGGER_VOID") is not None)
    b.close()
    b = Box()
    b.t.send_mode = "partial"
    kh = fill(b)
    p = b.own()
    fo = p["time"] - p["time"] % 300
    b.t.ticks = [(p["time_msc"] + 1000, 2584.2)]
    b.at_srv(fo + 300)
    b.timer()                                       # BE done at 2600.20
    n_before = len(b.t.writes)
    add_in(b, p, (fo + 330) * 1000, 2598.0, 0.20)   # a later part BELOW: average 2599.10
    b.at_srv(fo + 600 + 5)
    b.timer()
    c4 = (p["sl"], b.ea.pos.fill, len(b.sends()), [w for w in b.t.writes[n_before:] if w[0] == "sltp" and w[1]["sl"] > 2600.2])
    b.close()
    check("EAR-15 (ST3-3 re-review 2C) a breakeven condition met before a later IN deal is void (BE_TRIGGER_VOID): with the change allowed "
          "again and only ~1.8 USD after the later deal there is no BE (SL stays 2605, nothing pending); a 15.10 move after it (bar after "
          "the later deal's bar) gives a NEW BE_TRIGGERED / BE_SET at the new average; the void survives a restart; a BE already set is "
          "never loosened by a later part (SL kept 2600.20) and nothing is topped up (one send)",
          c1 == (True, True, None, 2605.0, False) and c2 == ("2584.70", 2599.8, 2) and c3 == (False, None, 2605.0, True)
          and c4 == (2600.2, 2599.1, 1, []), str((c1, c2, c3, c4)))


def gate_rereview3():
    """regressions of the ST3-4 re-review (items 1-2)."""
    def later_in(b, p, at_msc, price, vol):
        tot = round(p["volume"] + vol, 2)
        p["price_open"] = round((p["price_open"] * p["volume"] + price * vol) / tot, 5)
        p["volume"] = tot
        d = b.t._ticket()
        b.t.deals[d] = dict(order=0, position=p["identifier"], price=price, time=at_msc // 1000, time_msc=at_msc, entry="IN", volume=vol,
                            symbol="XAUUSDs", magic=p["magic"], comment=p["comment"], reason="EXPERT", profit=0.0, commission=0.0, swap=0.0)

    def change_during_read(after_ticks):
        b = Box()
        b.t.send_mode = "partial"
        kh = fill(b)
        p = b.own()
        F = p["time_msc"]
        fo = p["time"] - p["time"] % 300
        b.t.ticks = [(F + 5000, 2584.2), (F + 25000, after_ticks)]
        orig = b.ea.fill_stats
        armed = [False]

        def stats_then_change(*a, **k):
            r = orig(*a, **k)
            if armed[0]:
                armed[0] = False
                later_in(b, p, F + 20000, 2601.0, 0.20)
            return r
        b.ea.fill_stats = stats_then_change
        b.at_srv(fo + 300)
        armed[0] = True
        b.timer()
        first = ((b.ea.last(kh, "FILL_HISTORY_PENDING") or {}).get("reason"), b.ea.pos.volume, b.ea.last(kh, "BE_SET"), p["sl"])
        b.at_srv(fo + 301)
        b.timer()
        upd = b.ea.last(kh, "POSITION_UPDATED")
        second = (upd and (upd["volume"], int(upd["last_in_msc"]) - F, upd["in_deals"]), (b.ea.last(kh, "BE_SET") or {}).get("sl"), p["sl"])
        b.close()
        return first, second
    r1 = change_during_read(2600.0)
    r2 = change_during_read(2585.5)                 # 15.10 from the new average after the second part
    b = Box()
    b.t.send_mode = "fill_lost_reply"
    kh = fill(b)
    tk = max(b.t.positions)
    p = b.t.positions[tk]
    orig = b.ea.fill_stats
    armed = [True]
    later_ok = []

    def adopt_hook(*a, **k):
        r = orig(*a, **k)
        if armed[0]:
            armed[0] = False
            later_in(b, p, p["time_msc"] + 20000, 2601.0, 0.20)
            later_ok.append(1)
        return r
    b.t.advance(30000)
    b.touch("resolve_unknown", f"key_hash={kh}\nconfirm=open\n")
    b.ea.fill_stats = adopt_hook                  # the change lands while AdoptOwn reads the history
    b.timer()
    f_ = b.ea.last(kh, "FILLED")
    r3 = (f_ and f_["fill_sync"], f_ and f_["in_set"], bool(later_ok))
    b.close()
    b = Box()
    b.t.send_mode = "partial"
    kh = fill(b)
    p = b.own()
    F = p["time_msc"]
    fo = p["time"] - p["time"] % 300
    b.t.ticks = [(F + 1000, 2584.2)]
    b.t.modify_mode = "reject"
    b.at_srv(fo + 300)
    b.timer()                                       # BE_TRIGGERED, refused, pending
    b.t.modify_mode = "ok"
    orig_retry = b.ea.retry_breakeven
    landed = []

    def deal_lands_then_retry(now):
        if b.ea.pos.bePending and not landed:
            landed.append(1)
            later_in(b, p, (fo + 330) * 1000, 2599.4, 0.20)   # lands after ManageOwn's refresh, before the SL change
        return orig_retry(now)
    b.ea.retry_breakeven = deal_lands_then_retry
    b.at_srv(fo + 600 + 5)
    b.timer()
    r4 = (b.ea.last(kh, "BE_SET"), p["sl"], b.ea.last(kh, "BE_TRIGGER_VOID") is not None, b.ea.pos.bePending, b.ea.pos.fill)
    b.close()
    check("EAR-16 (ST3-4 re-review 1) a later deal landing WHILE the history is read: the pair is refused (FILL_HISTORY_PENDING "
          "position_changed_during_read), the EA keeps 0.20 and decides nothing in that pass (no BE from the 2584.20 before the second part); "
          "the next pass takes 0.40 / last IN +20 s / 2 IN deals and still no BE, while 15.10 after the second part gives BE at 2600.60; at "
          "adoption the same race gives FILLED fill_sync=pending; a deal landing after ManageOwn's refresh but before the SL change is caught "
          "by ApplyBreakeven's own refresh (BE_TRIGGER_VOID, no BE, SL stays 2605)",
          r1[0] == ("position_changed_during_read", 0.2, None, 2605.0) and r1[1] == (("0.40", 20000, "2"), None, 2605.0)
          and r2[1] == (("0.40", 20000, "2"), "2600.60", 2600.6) and r3 == ("pending", "", True)
          and r4 == (None, 2605.0, True, False, 2599.8), str((r1, r2, r3, r4)))

    def same_ms(crash, price_only=False):
        b = Box()
        b.t.send_mode = "partial"
        kh = fill(b)
        p = b.own()
        F = p["time_msc"]
        fo = p["time"] - p["time"] % 300
        b.t.ticks = [(F + 1000, 2584.2)]
        b.t.modify_mode = "reject"
        b.at_srv(fo + 300)
        b.timer()
        pend = b.ea.pos.bePending
        if price_only:
            p["price_open"] = 2599.0                # the average changes WITHOUT a new deal (e.g. a broker adjustment)
        else:
            later_in(b, p, F, 2596.2, 0.20)         # same time_msc as the first IN: 0.40 @ 2598.20
        b.t.modify_mode = "ok"
        if crash:
            orig_j = b.ea.journal

            def crash_after_update(key, state, fields):
                r = orig_j(key, state, fields)
                if state == "POSITION_UPDATED":
                    raise SystemExit("crash between POSITION_UPDATED and BE_TRIGGER_VOID")
                return r
            b.ea.journal = crash_after_update
        b.at_srv(fo + 301)
        try:
            b.timer()
        except SystemExit:
            pass
        void = b.ea.last(kh, "BE_TRIGGER_VOID") is not None
        b.restart(crash=crash)
        restored = b.ea.pos.bePending
        b.at_srv(fo + 600 + 5)
        b.timer()
        upd = b.ea.last(kh, "POSITION_UPDATED")
        out = (pend, void, restored, b.ea.last(kh, "BE_SET"), p["sl"], upd and upd["in_deals"], upd and int(upd["last_in_msc"]) - F)
        b.close()
        return out
    c1, c2, c3 = same_ms(True), same_ms(False), same_ms(True, price_only=True)
    check("EAR-17 (ST3-4 re-review 2) a second IN deal with the SAME time_msc changes the IN deal set (in_set) although last_in_msc stays: "
          "crash between POSITION_UPDATED and BE_TRIGGER_VOID -> the restart does not restore the old condition (basis = IN set + average, "
          "not the VOID record), no BE from the old 2584.20 (14.00 from the new average 2598.20), SL stays 2605; without the crash the VOID "
          "is written and the result is the same; with the SAME IN set but another average (price-only change) the condition is not "
          "restored either (the basis includes the average): no BE at 2599.00 from the old 2584.20 (14.80 now)",
          c1 == (True, False, False, None, 2605.0, "2", 0) and c2 == (True, True, False, None, 2605.0, "2", 0)
          and c3[:5] == (True, False, False, None, 2605.0), str((c1, c2, c3)))


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


NON_STATES = {"DEMO", "REAL", "CONTEST", "HEDGING", "NETTING", "FULL", "SHORTONLY", "LONGONLY", "SELL", "BUY", "DEAL", "SLTP", "EXPERT", "IN",
              "OUT", "GO", "NOGO", "TICKS_SINCE_FILL", "SKIP", "TP", "SL", "INIT_SUCCEEDED", "XSD", "ENTRY", "SHORT", "MARKET", "LIMIT",
              "SATS_PULL", "SATS_NOW", "OANDA", "CLIENT"}


def gate_static():
    src = open(MQ5, encoding="utf-8").read()
    code = re.sub(r"//[^\n]*", "", src)
    mdl_all = open(os.path.join(ROOT, "tests", "ea_model.py"), encoding="utf-8").read()
    mdl = mdl_all[mdl_all.index("class EA:"):]
    inp = dict(re.findall(r"input\s+\w+\s+(Inp\w+)\s*=\s*([^;]+);", src))
    check("EAS-01 inputs: InpDryRun = true, InpAllowNewEntries = false, InpExpectedLogin = 0, server XSFintech-DEMO, symbol XAUUSDs, "
          "currency JPY, the sid / cfg hash / TradingView symbol of the bridge; no password / token / URL / WebRequest / socket anywhere",
          inp.get("InpDryRun") == "true" and inp.get("InpAllowNewEntries") == "false" and inp.get("InpExpectedLogin") == "0"
          and inp.get("InpExpectedServer") == '"XSFintech-DEMO"' and inp.get("InpSymbol") == '"XAUUSDs"' and inp.get("InpExpectedCurrency") == '"JPY"'
          and inp.get("InpExpectedSid") == f'"{SID}"' and inp.get("InpExpectedCfgSha") == f'"{CFG}"' and inp.get("InpExpectedTvSym") == '"OANDA:XAUUSD"'
          and not re.search(r"password|token|https?://|WebRequest|Socket", code, re.I), str(inp))
    consts = dict(re.findall(r"const\s+\w+\s+(\w+)\s*=\s*([^;]+);", code))
    check("EAS-02 approved constants are constants (not inputs) and equal the model: RISK_FRACTION 0.03, MAX_AGE_SEC 60, MAX_DEV_FRAC 0.20, "
          "MAX_SPREAD 0.50, BE_DIST 15.0, BAR_SEC 300, CMD_VERSION \"2\" (= the bridge's); proposal values ASK_WAIT_MS / BRIDGE_HB_MAX_MS / "
          "EMERGENCY_RETRY_SEC / CLOSE_DEVIATION_POINTS equal the model",
          float(consts["RISK_FRACTION"]) == em.RISK_FRACTION == 0.03 and int(consts["MAX_AGE_SEC"]) == em.MAX_AGE_SEC == 60
          and float(consts["MAX_DEV_FRAC"]) == em.MAX_DEV_FRAC == 0.2 and float(consts["MAX_SPREAD"]) == em.MAX_SPREAD == 0.5
          and float(consts["BE_DIST"]) == em.BE_DIST == 15.0 and int(consts["BAR_SEC"]) == em.BAR_SEC == 300
          and consts["CMD_VERSION"].strip('"') == em.CMD_VERSION == eb.CMD_VERSION == "2" and eb.MAX_AGE_SEC == 60
          and int(consts["ASK_WAIT_MS"]) == em.ASK_WAIT_MS and int(consts["BRIDGE_HB_MAX_MS"]) == em.BRIDGE_HB_MAX_MS
          and int(consts["EMERGENCY_RETRY_SEC"]) == em.EMERGENCY_RETRY_SEC and int(consts["CLOSE_DEVIATION_POINTS"]) == em.CLOSE_DEVIATION_POINTS,
          str(consts))
    sends = [m.start() for m in re.finditer(r"\bOrderSend\(", code)]
    owners = [(n, _func(code, n).count("OrderSend(")) for n in ("ProcessEntry", "ClosePosition", "ModifyOwn")]
    pe, cp, mo = _func(code, "ProcessEntry"), _func(code, "ClosePosition"), _func(code, "ModifyOwn")
    check("EAS-03 the only trade API writes are 3 OrderSend calls (ProcessEntry / ClosePosition / ModifyOwn; no CTrade, OrderSendAsync, "
          "PositionClose, OrderDelete); ClosePosition / ModifyOwn start with the TradeWritesAllowed + own-position (SelectOwn() == 1) gate; "
          "ModifyOwn refuses to loosen / remove the SL before sending",
          len(sends) == 3 and owners == [("ProcessEntry", 1), ("ClosePosition", 1), ("ModifyOwn", 1)]
          and not re.search(r"CTrade|Trade\.mqh|OrderSendAsync|PositionClose|OrderDelete", code)
          and re.search(r"\{\s*remaining = -1;\s*if\(!TradeWritesAllowed\(\) \|\| !g_hasPos \|\| SelectOwn\(\) != 1\)", cp)
          and re.search(r"\{\s*if\(!TradeWritesAllowed\(\) \|\| !g_hasPos \|\| SelectOwn\(\) != 1\)", mo)
          and mo.index("would_loosen_or_remove_sl") < mo.index("OrderSend("), str(owners))
    oi, twa = _func(code, "OnInit"), _func(code, "TradeWritesAllowed")
    check("EAS-04 OnInit refuses a non-demo account before anything else (INIT_FAILED); TradeWritesAllowed needs DryRun off, env ok, the "
          "journal binding, startup reconciliation done, a demo account and the expected login + server at the time of every write; the "
          "journal file is named by login / server / magic",
          oi.index("ACCOUNT_TRADE_MODE_DEMO") < oi.index("FolderCreate") and "INIT_FAILED" in oi.split("FolderCreate")[0]
          and all(x in twa for x in ("InpDryRun", "g_envOk", "g_bindOk", "g_ready", "IsDemoAccount()", "ACCOUNT_LOGIN", "ACCOUNT_SERVER"))
          and oi.index("Reconcile()") < oi.index("g_ready = true") and '"\\\\journal_" + IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN))' in oi, "")
    st_src = set(re.findall(r'"([A-Z][A-Z_]{2,})"', code)) - NON_STATES
    st_mdl = set(re.findall(r'"([A-Z][A-Z_]{2,})"', mdl)) - NON_STATES
    check("EAS-05 the journal / report states of the MQL5 EA and the model are the same set (%d states)" % len(st_src), st_src == st_mdl,
          str((sorted(st_src - st_mdl), sorted(st_mdl - st_src))))
    rs_src = set(re.findall(r'return\("([a-z0-9_]+)', _func(code, "CheckCmd") + _func(code, "CheckDeadline") + _func(code, "PrepareOrder")))
    seg = mdl[mdl.index("    def check_cmd"):mdl.index("    # -- final permission")]
    rs_mdl = set(re.findall(r'return f?"([a-z0-9_]+)', seg))
    check("EAS-06 the refusal reasons of CheckCmd / CheckDeadline / PrepareOrder are the same in the MQL5 EA and the model (%d)" % len(rs_src),
          rs_src == rs_mdl, str((sorted(rs_src - rs_mdl), sorted(rs_mdl - rs_src))))
    dr = set(re.findall(r"case TRADE_RETCODE_(\w+):", _func(code, "IsDefiniteReject")))
    check("EAS-07 IsDefiniteReject lists exactly the model's definite rejects (%d codes); anything else after a send (timeout, error, "
          "connection, placed, ...) is UNKNOWN" % len(dr), dr == set(em.DEFINITE_REJECT), str(sorted(dr ^ set(em.DEFINITE_REJECT))))
    pr = _func(code, "PrepareOrder")
    check("EAS-08 the request: SELL at the Bid, the rounded initial SL always attached, TP 0 (TP0 at the fill-bar close), comment XSD:<key "
          "hash>; TRADE_ACTION_SLTP only in ModifyOwn; every state the bridge maps is a state the EA writes",
          "req.sl           = sl;" in pr and "req.tp           = 0.0;" in pr and 'req.comment      = "XSD:" + c.khash;' in pr
          and "ORDER_TYPE_SELL" in pr and "tk.bid" in pr and code.count("TRADE_ACTION_SLTP") == 1 and "TRADE_ACTION_SLTP" in mo
          and set(eb.EA_STATE_TIME) <= st_src, str(sorted(set(eb.EA_STATE_TIME) - st_src)))
    appr = re.findall(r"const bool\s+APPROVED_(\w+)\s*=\s*(\w+);", code)
    ua, nea = _func(code, "Unapproved"), _func(code, "NewEntriesAllowed")
    names = re.findall(r'if\(!APPROVED_(\w+)\)\s*return\("(\w+)"\)', ua)
    check("EAS-09 (review 8) every unapproved proposal is a source constant APPROVED_* = false (%d), Unapproved() lists them in the model's "
          "order, NewEntriesAllowed refuses while any is missing (after the DRY_RUN / new-entries gates), and no input can set them" % len(appr),
          len(appr) == 7 and all(v == "false" for _, v in appr) and [n for _, n in names] == list(em.APPROVALS)
          and [a for a, _ in appr] == [a for a, _ in names] and nea.index('"unapproved:"') > nea.index('"new_entries_off"')
          and not re.search(r"input[^\n]*APPROVED", code), str((appr, names)))
    i_go, i_dec, i_pre = pe.index("AskBridge("), pe.index('"DECIDED"'), pe.index('if(!Journal(id, "PRE_SEND"')
    i_chk, i_send = pe.index("SendCheck("), pe.index("OrderSend(")
    sc, fg = _func(code, "SendCheck"), _func(code, "FinalGate")
    between = pe[pe.index("MqlTradeResult res;"):i_send]
    check("EAS-10 (review 1/2, re-review 1) ProcessEntry order: SEEN record required -> checks -> AskBridge (final GO) -> DECIDED record "
          "required -> PRE_SEND record required -> SendCheck: the slow PrepareOrder (OrderCheck) and the request comparison FIRST, then "
          "FinalGate (deadline, GO validity, every gate, positions, pending orders) as its LAST step -> nothing but ZeroMemory before "
          "OrderSend; Journal() verifies open / write length / flush",
          'if(!Journal(id, "SEEN"' in pe and i_go < i_dec < i_pre < i_chk < i_send and 'if(!Journal(id, "DECIDED"' in pe
          and sc.index("PrepareOrder(c, out, detail)") < sc.index('"request_changed"') < sc.index("return(FinalGate(c, id, goUntil));")
          and all(x in fg for x in ("CheckDeadline(c)", "NowMsLate() > goUntil", "NewEntriesAllowed(gate, id)", "PositionsTotal() > 0",
                                    "OrdersTotal() > 0"))
          and "PrepareOrder" not in fg and "OrderCheck" not in fg and re.sub(r"\s+", " ", between).strip() == "MqlTradeResult res; ZeroMemory(res); bool ok ="
          and re.search(r"uint w = FileWriteString\(h, line \+ \"\\n\"\);\s*FileFlush\(h\);\s*ok = w >= ", _func(code, "Journal")) is not None,
          repr(between))
    so, cf = _func(code, "SelectOwn"), _func(code, "ConfirmFill")
    check("EAS-11 (review 3/7) ownership by POSITION_IDENTIFIER: SelectOwn compares the identifier, quarantines a symbol / magic / type "
          "mismatch and refreshes the ticket; ConfirmFill maps DEAL_POSITION_ID to the live ticket via TicketOfIdentifier (never "
          "PositionSelectByTicket(identifier)); history queries use the identifier; Reconcile adopts only through SelectOwn",
          "POSITION_IDENTIFIER) != g_pos.posId" in so and "Quarantine(\"ownership_mismatch\"" in so and "g_pos.posTicket = t;" in so
          and "DEAL_POSITION_ID" in cf and "TicketOfIdentifier(posId)" in cf and "PositionSelectByTicket(posId)" not in code
          and "HistorySelectByPosition(posId)" in _func(code, "HistoryVolumes") and "SelectOwn()" in _func(code, "Reconcile"), "")
    cr = _func(code, "CheckResume")
    check("EAS-12 (review 4) resume_new is refused while an unknown result exists; the unknown key is cleared only in CheckResolveUnknown after "
          "the history check (DetectUnknown) matches the operator's confirm",
          'if(g_unknownKey != "")' in cr and "unknown_unresolved" in cr and code.count('g_unknownKey = "";') == 1
          and 'g_unknownKey = "";' in _func(code, "CheckResolveUnknown") and "DetectUnknown(g_unknownKey" in _func(code, "CheckResolveUnknown")
          and "confirm != detected" in _func(code, "CheckResolveUnknown"), "")
    fbl = _func(code, "FillBarLow")
    mo_ = _func(code, "ManageOwn")
    check("EAS-13 (review 5, re-review 3/4) the fill-bar low comes from CopyTicksRange strictly after the LAST IN deal (max(fillTimeMsc, "
          "lastInMsc) + 1) and strictly before the fill-bar close; history not available (-1) is FILLBAR_TICKS_UNAVAILABLE and retried, "
          "never 'not met'; a bar holding a later IN deal is not used; OnTick keeps no running minimum",
          "CopyTicksRange(InpSymbol, ticks, COPY_TICKS_INFO, from, to)" in fbl and "MaxL(g_pos.fillTimeMsc, g_pos.lastInMsc) + 1" in fbl
          and "* 1000 - 1" in fbl and "minBid" not in code and '"FILLBAR_TICKS_UNAVAILABLE"' in mo_
          and re.search(r"if\(n < 0\)\s*\{[^}]*\{[^}]*\}\s*\}\s*else", mo_) is not None and "rates[i].time > lastInBar" in mo_, "")
    bsrc = open(os.path.join(ROOT, "automation", "xau_short", "bridge", "ea_bridge.py"), encoding="utf-8").read()
    cpr, pco = _func(code, "CheckProtection"), _func(code, "ProcessCloseObligation")
    check("EAS-14 (review 6, re-review 2) ClosePosition verifies the result on the live position / history (CLOSE_DONE / PARTIAL / FAILED / "
          "UNKNOWN); every close the EA requires (initial SL missing AND bad_fill_side_mt5) goes through RequireClose + "
          "ProcessCloseObligation, which handles every result (EMERGENCY_CLOSE / CLOSE_CONFIRMED only for CLOSE_FULL, otherwise halt + "
          "CRITICAL) and is the only caller of ClosePosition; the bridge clears mt5_open only on CLOSED",
          all(x in cp for x in ('"CLOSE_DONE"', '"CLOSE_PARTIAL"', '"CLOSE_FAILED"', '"CLOSE_UNKNOWN"', "HistoryVolumes(g_pos.posId"))
          and 'RequireClose("emergency_initial_sl_missing");' in cpr and "ProcessCloseObligation();" in cpr
          and 'RequireClose("bad_fill_side_mt5");' in mo_ and re.search(r"if\(r == CLOSE_FULL\)\s*\{", pco) is not None
          and "SetCritical(" in pco and "HaltNew(" in pco and len(re.findall(r"\bClosePosition\(", code)) == 2
          and "ClosePosition(" in pco and bsrc.count('upd["mt5_open"] = 0') == 1
          and 'if state == "CLOSED":\n                    upd["mt5_open"] = 0' in bsrc, "")
    rc, tb, rf = _func(code, "Reconcile"), _func(code, "TryBreakeven"), _func(code, "RefreshFill")
    check("EAS-15 (re-review 2/3/4, ST3-3 re-review 2) persisted and restored: CLOSE_REQUIRED, POSITION_UPDATED (volume / average / last IN "
          "deal / IN count), BE_TRIGGERED (with its basis last_in_msc) journaled BEFORE the SL change and restored only on the same basis, "
          "BE_TRIGGER_VOID; RefreshFill runs every timer and at restart, takes the state as synced only when IN - OUT = the live volume "
          "(otherwise FILL_HISTORY_PENDING) and voids the breakeven basis on a new IN deal; ManageOwn waits while it is pending",
          all(x in rc for x in ('"CLOSE_REQUIRED"', '"POSITION_UPDATED"', '"BE_TRIGGERED"', "g_pos.closeReason = closeReq;",
                                "g_pos.bePending = beTrig && !beSet;", "beInSet != inSet", "RefreshFill();"))
          and all(x in rf for x in ("FillStats(g_pos.posId", "MathAbs(vin - vout - v) <= 1e-6", '"FILL_HISTORY_PENDING"', "VoidBreakevenBasis();"))
          and "SyncFill" not in code and tb.index('"BE_TRIGGERED"') < tb.index("ApplyBreakeven();") and "in_set=" in tb
          and mo_.index("bool fillOk = RefreshFill();") < mo_.index("if(!fillOk || SelectOwn() != 1)") < mo_.index("RetryBreakeven(now);")
          and mo_.index("RetryBreakeven(now);") < mo_.index("FillBarLow(") and "FillStats(posId" in _func(code, "AdoptOwn")
          and 'ModifyOwn("breakeven"' in _func(code, "ApplyBreakeven"), "")
    ab, fs = _func(code, "ApplyBreakeven"), _func(code, "FillStats")
    check("EAS-17 (ST3-4 re-review 1/2) the fill state is taken only from a stable read: RefreshFill reads the position, then the history "
          "(FillStats), then re-reads the position (PositionUnchanged: ticket / identifier / volume / average) and refuses a pair taken "
          "while it changed; the IN deal set identity (sorted IN tickets, hashed) is the basis together with the average; ApplyBreakeven "
          "refreshes the state and compares the basis immediately before ModifyOwn; Reconcile restores a condition only on the same IN set "
          "and average and never decides by reading BE_TRIGGER_VOID",
          rf.index("FillStats(g_pos.posId") < rf.index("PositionUnchanged(g_pos.posTicket") and "bool ok = read && stable" in rf
          and "ArraySort(ins);" in fs and "Sha16(j)" in fs and "inSet != g_pos.inSet" in rf
          and ab.index("RefreshFill()") < ab.index("g_pos.beInSet != g_pos.inSet") < ab.index('ModifyOwn("breakeven"')
          and "MathAbs(g_pos.beFillBasis - g_pos.fill) > 1e-6" in ab and 'st == "BE_TRIGGER_VOID"' not in rc
          and "MathAbs(beFillBasis - fill) > 1e-6" in rc and "PositionUnchanged(ticket, posId" in _func(code, "AdoptOwn"), "")
    fg2 = _func(code, "FinalGate")
    check("EAS-16 (ST3-3 re-review 1) FinalGate reads first and checks the clock last: NewEntriesAllowed (halt file, bridge heartbeat file, "
          "...), PositionsTotal, OrdersTotal, THEN CheckDeadline and the GO validity, then return; nothing between FinalGate and OrderSend",
          fg2.index("NewEntriesAllowed(gate, id)") < fg2.index("PositionsTotal() > 0") < fg2.index("OrdersTotal() > 0")
          < fg2.index("CheckDeadline(c)") < fg2.index("NowMsLate() > goUntil") and fg2.count("CheckDeadline(") == 1
          and "ReadLines" not in fg2[fg2.index("CheckDeadline(c)"):] and "File" not in fg2[fg2.index("CheckDeadline(c)"):], "")

def main():
    for g in (gate_env, gate_deadline, gate_price_lot, gate_slot, gate_unknown, gate_protect, gate_be, gate_restart_misc, gate_dry_mgmt,
              gate_review, gate_rereview, gate_rereview2, gate_rereview3, gate_static):
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
