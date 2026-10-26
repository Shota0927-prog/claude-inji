"""AU receiver fixtures — automation/xau_short/receiver/xau_receiver.py (stage 2: receive / record only, no orders).

  RR : basics — sample flow, bad / edge cases, restart persistence, HTTP (token path, refusals, nothing secret in the log),
       concurrent re-sends, cfg pinning, deadline policy off by default, TradingView virtual state vs MT5 state, no order code,
       samples / config files in sync
  RG : regressions reported on AU-1 (ChatGPT review) —
       1 terminal / cancel / wait-end facts arriving BEFORE the ENTRY: kept for good, the late ENTRY is stored but never an
         execution candidate (records / state / eligibility separate)
       2 management events out of order (ENTRY -> TP_SET -> TV_FILL): kept PENDING and re-evaluated; a terminal trade never
         reopens; an older stop never overwrites a newer one; one claim per event (no double execution)
       3 abnormal values: Infinity / NaN / 1e400, negative prices, LONG + negative stop BE on a SHORT trade, bar_close 10**40,
         unaligned bars, duplicate fields, unknown fields, non-UTF-8 — recorded with reasons, no unhandled exception
       5 BAR events (OHLC + TradingView virtual state) recorded separately; the TradingView BE stop is marked recompute-only
       6 PowerShell: quoted arguments, PID ownership check, sample test in a separate data folder (static checks)
  RG-07..09 : regressions reported on AU-2 — a TP_SET loosening the stop after a breakeven (and late / duplicate / non-initial
       TP_SET, intent scope / stale / superseded); the deadline re-checked at claim() (also after a restart; separate times, claim
       log); claim / evaluation races; upgrade of an AU-2 database
  RG-10..12 : regressions reported on AU-3 — a normal TP_SET updates the TP only (initial vs final TP); the claim deadline is decided
       after the in-process lock and the SQLite write lock (attempt vs decision time); real AU-2 / AU-3 databases with data are
       fully re-evaluated on open (claims refused while pending, history kept, claimed intents never claimable again)
Evidence class: local Python only (no TradingView / Windows / MT5 run; PowerShell scripts not executed here).
"""
import hashlib
import json
import logging
import os
import re
import sys
import tempfile
import threading
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RDIR = os.path.join(ROOT, "automation", "xau_short", "receiver")
sys.path.insert(0, RDIR)
sys.path.insert(0, os.path.join(RDIR, "samples"))
import xau_receiver as xr        # noqa: E402
import make_samples as ms        # noqa: E402

RESULTS = []
QUIET = logging.getLogger("aur_sim_quiet")
QUIET.addHandler(logging.NullHandler())
QUIET.propagate = False


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


def rcv(d, clock=None, **over):
    cfg = xr.load_config(None)
    cfg["data_dir"] = d
    for k, v in over.items():
        cfg[k].update(v) if isinstance(v, dict) else cfg.__setitem__(k, v)
    return xr.Receiver(cfg, log=QUIET, clock=clock)


def body(m):
    return m if isinstance(m, str) else json.dumps(m, separators=(",", ":"))


def intent(r, key):
    return r.store.one("SELECT * FROM intents WHERE key=?", (key,))


def ev_status(r, key):
    row = r.store.one("SELECT apply_status, apply_note FROM events WHERE key=?", (key,))
    return (row["apply_status"], row["apply_note"]) if row else None


E = lambda i, **k: ms.ev("ENTRY", i, otype="MARKET", px=k.pop("px", 2600.0), sl=k.pop("sl", 2605.0), tp=k.pop("tp", 2592.5),
                         info=k.pop("info", "SATS_NOW"), **k)


def gate_basic():
    with tempfile.TemporaryDirectory() as d:
        r = rcv(d)
        st = [r.process(body(m))["status"] for m in ms.normal_flow()]
        trade = r.store.one("SELECT * FROM tv_trades WHERE tid=?", (ms.normal_flow()[3]["tid"],))
        wait = r.store.one("SELECT * FROM tv_waits")
        bars = r.store.one("SELECT COUNT(*) n FROM tv_bars")["n"]
        check("RR-01 normal flow (WAIT_START, BAR, PROV, ENTRY SATS pull, BAR, TV_FILL, TP_SET, BAR, BE_MOVE, TV_FLAT) all ACCEPTED; trade CLOSED "
              "with the reference price 2651.8 and the TradingView virtual fill 2651.9 stored separately, breakeven stop / TP0; wait CONSUMED; "
              "3 BAR rows; every receipt keeps received / bar / sent times, sid, cfg hash, tid, event, rank, prices, OHLC, reasons",
              st == ["ACCEPTED"] * 10 and trade["state"] == "CLOSED" and trade["ref_px"] == 2651.8 and trade["tv_fill_px"] == 2651.9
              and trade["sl"] == 2651.9 and trade["tp"] == 2640.5 and wait["state"] == "CONSUMED" and bars == 3
              and all(x["received_ms"] and x["bar_close"] and x["sid"] and x["cfg_sha256"] and x["tid"] and x["rank"] is not None and x["o"]
                      for x in r.store.all("SELECT * FROM receipts")), str(st))
        exp = {"not_json": ("REJECTED", "format:not_json"), "missing_field": ("REJECTED", "format:missing:sl"),
               "sl_infinity": ("REJECTED", "format:nonstandard_constant:Infinity"), "bar_close_10e40": ("REJECTED", "time:out_of_range:bar_close"),
               "negative_price": ("REJECTED", "value:price_range:px"), "duplicate_resend": ("DUPLICATE", "dup:same_key_already_accepted"),
               "late_manage_after_close": ("REJECTED", "value:be_geometry"), "long_side_be_on_short": ("REJECTED", "value:side_not_allowed"),
               "unknown_trade_manage": ("ACCEPTED", None), "wait_start": ("ACCEPTED", None), "wait_end": ("ACCEPTED", None),
               "late_entry_for_ended_wait": ("ACCEPTED", None), "wrong_side": ("REJECTED", "value:side_not_allowed"),
               "bad_geometry": ("REJECTED", "value:price_geometry"), "sid_mismatch": ("REJECTED", "identity:sid_mismatch"),
               "entry_ok": ("ACCEPTED", None), "entry_while_virtual_active": ("ACCEPTED", None), "older_entry_after_newer": ("ACCEPTED", None)}
        got = {}
        for name, m in ms.bad_cases():
            res = r.process(body(m))
            got[name] = (res["status"], [x for x in res["reasons"] if not x.startswith("warn:")])
        ok = all(got[k][0] == v[0] and (v[1] is None or v[1] in got[k][1]) for k, v in exp.items())
        bc = {n: m for n, m in ms.bad_cases()}
        elig = {n: (intent(r, bc[n]["key"])["eligible"], intent(r, bc[n]["key"])["reason"]) for n in
                ("late_entry_for_ended_wait", "entry_ok", "entry_while_virtual_active", "older_entry_after_newer")}
        orphan = ev_status(r, bc["unknown_trade_manage"]["key"])
        check("RR-02 bad / edge cases recorded with their reason (raw kept): not JSON, missing field, sl Infinity, bar_close 10**40, negative "
              "prices, re-send (DUPLICATE), a BE stop that is not the fill, LONG BE on the SHORT trade, LONG intent, wrong SL / TP side, sid "
              "mismatch; valid facts in a doubtful order are ACCEPTED as facts but are not execution candidates: management for an unseen "
              "trade (ORPHAN), ENTRY for an ended wait, ENTRY while a candidate position is open, an older ENTRY after a newer one; the "
              "valid ENTRY stays the only candidate",
              ok and orphan[0] == "ORPHAN" and elig["entry_ok"] == (1, "ok") and elig["late_entry_for_ended_wait"][0] == 0
              and "late:wait_already_ended" in elig["late_entry_for_ended_wait"][1] and elig["entry_while_virtual_active"][0] == 0
              and "state:virtual_position_active" in elig["entry_while_virtual_active"][1] and elig["older_entry_after_newer"][0] == 0
              and "late:older_than_newer_trade" in elig["older_entry_after_newer"][1], str((got, elig, orphan)))
    with tempfile.TemporaryDirectory() as d:
        r = rcv(d)
        t = E(3)
        r.process(body(t))
        r.store.db.close()
        r2 = rcv(d)
        again = r2.process(body(t))
        check("RR-03 restart: a new receiver on the same data directory keeps receipts / facts / states; the same ENTRY re-sent after the "
              "restart is DUPLICATE (bar-time key, no in-memory counter)",
              again["status"] == "DUPLICATE" and r2.store.one("SELECT COUNT(*) n FROM receipts")["n"] == 2
              and r2.store.one("SELECT state FROM tv_trades")["state"] == "INTENT", str(again))
    with tempfile.TemporaryDirectory() as d:
        token = "test-token-" + os.urandom(8).hex()
        cfg = xr.load_config(None)
        cfg.update(data_dir=d, port=0)
        holder = {}
        th = threading.Thread(target=xr.serve, kwargs=dict(cfg=cfg, token=token, ready=lambda s: holder.update(s=s)), daemon=True)
        th.start()
        for _ in range(200):
            if "s" in holder:
                break
            threading.Event().wait(0.02)
        port = holder["s"].server_address[1]

        def post(path, data):
            req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=5) as resp:
                    return resp.status, json.loads(resp.read())
            except urllib.error.HTTPError as e:
                return e.code, None
        ok = post(f"/webhook/{token}", body(E(80, info="CURRENT")).encode())
        bad = post("/webhook/wrong", body(E(81)).encode())
        big = post(f"/webhook/{token}", b"{" + b" " * 20000 + b"}")
        huge = post(f"/webhook/{token}", body(ms.bad_cases()[3][1]).encode())
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=5) as resp:
            health = json.loads(resp.read())
        results = []
        ths = [threading.Thread(target=lambda: results.append(post(f"/webhook/{token}", body(E(90, info="CURRENT")).encode()))) for _ in range(12)]
        [x.start() for x in ths]
        [x.join() for x in ths]
        pid = json.load(open(os.path.join(d, "receiver.pid"), encoding="utf-8"))
        holder["s"].shutdown()
        log = open(os.path.join(d, "receiver.log"), encoding="utf-8").read()
        sts = sorted(x[1]["status"] for x in results)
        check("RR-04 HTTP: POST /webhook/<token> -> 200 ACCEPTED; wrong token -> 404 (not recorded); body over the limit -> 413; bar_close "
              "10**40 -> 200 REJECTED (no crash); /health says orders disabled; 12 concurrent re-sends -> 1 ACCEPTED + 11 DUPLICATE; the token "
              "never appears in the log; the PID file records pid / start time / script / data dir / marker for the stop script",
              ok[0] == 200 and ok[1]["status"] == "ACCEPTED" and bad[0] == 404 and big[0] == 413 and huge[0] == 200
              and huge[1]["status"] == "REJECTED" and health.get("orders") == "disabled" and sts == ["ACCEPTED"] + ["DUPLICATE"] * 11
              and token not in log and {"pid", "started_utc", "script", "data_dir", "marker"} <= set(pid), str((ok, bad, big, huge, sts)))
    m = ms.normal_flow()[3]
    sha = hashlib.sha256(m["cfg"].encode()).hexdigest()
    with tempfile.TemporaryDirectory() as d:
        a = rcv(d, expected={"cfg_sha256": sha}).process(body(m))
    with tempfile.TemporaryDirectory() as d:
        b = rcv(d, expected={"cfg_sha256": "0" * 64}).process(body(m))
    with tempfile.TemporaryDirectory() as d:
        c = rcv(d).process(body(m), now_ms=m["bar_close"] + 3600_000)
        cs = rcv(d).store.one("SELECT age_ms FROM receipts")["age_ms"]
    with tempfile.TemporaryDirectory() as d:
        r = rcv(d, policy={"max_age_sec": 60})
        e = r.process(body(E(100, info="CURRENT")), now_ms=ms.bar(101) + 120_000)
        e_int = intent(r, E(100, info="CURRENT")["key"])
    with tempfile.TemporaryDirectory() as d:
        f_none = rcv(d).process(body(E(110, sent_delay=-7200_000 + 300_000 + 1500)), now_ms=ms.bar(110) - 3600_000)
    with tempfile.TemporaryDirectory() as d:
        f_set = rcv(d, policy={"max_future_skew_sec": 5}).process(body(E(110)), now_ms=ms.bar(110) - 3600_000)
    check("RR-05 settings ID pinned: the matching cfg is accepted without the warning, a different cfg REJECTED cfg_mismatch; the deadline "
          "and the future-skew tolerance are off by default (a 1 h old ENTRY / a bar 1 h in the future accepted, age recorded) and work only "
          "when configured (old ENTRY: fact accepted, not a candidate 'late:older_than_max_age'; future: REJECTED time:in_future)",
          a["status"] == "ACCEPTED" and "warn:cfg_unpinned" not in a["reasons"] and "identity:cfg_mismatch" in b["reasons"]
          and c["status"] == "ACCEPTED" and cs == 3600_000 and e["status"] == "ACCEPTED" and e_int["eligible"] == 0
          and e_int["reason"] == "late:older_than_max_age" and f_none["status"] == "ACCEPTED" and "time:in_future" in f_set["reasons"],
          str((a, b, c, e, dict(e_int), f_none, f_set)))
    src = open(os.path.join(RDIR, "xau_receiver.py"), encoding="utf-8").read()
    with tempfile.TemporaryDirectory() as d:
        r = rcv(d)
        for mm in ms.normal_flow():
            r.process(body(mm))
        mt5 = r.store.one("SELECT COUNT(*) n FROM mt5_positions")["n"]
        acts = {x["mt5_action"] for x in r.store.all("SELECT mt5_action FROM receipts")}
        claimed = r.store.one("SELECT COUNT(*) n FROM intents WHERE claimed_ms IS NOT NULL")["n"]
    check("RR-06 TradingView virtual state (tv_trades / tv_waits / tv_bars) and MT5 actual positions (mt5_positions) are separate; stage 2 "
          "never writes MT5 state, never claims an intent, every receipt says no MT5 action; no MetaTrader5 / order / socket client code",
          mt5 == 0 and claimed == 0 and acts == {xr.STAGE2_MT5_ACTION}
          and not re.search(r"MetaTrader5|order_send|order_check|positions_get|socket\.connect|urlopen|requests\.", src), str((mt5, acts)))
    with tempfile.TemporaryDirectory() as d:
        ms.write(d)
        same = all(open(os.path.join(d, f), encoding="utf-8").read() == open(os.path.join(RDIR, "samples", f), encoding="utf-8").read()
                   for f in ("normal_flow.jsonl", "bad_cases.jsonl"))
    cfg_file = json.load(open(os.path.join(RDIR, "config.example.json"), encoding="utf-8"))
    check("RR-07 the committed samples equal make_samples.py output; config.example.json == the built-in defaults (no token, no credentials; "
          "deadline / future skew / cfg pin unset)", same and cfg_file == xr.DEFAULT_CONFIG)


def gate_regressions():
    # 1. terminal / cancel facts before the ENTRY
    res1 = {}
    for term in ("TV_CLOSED", "TV_FLAT", "CANCEL"):
        with tempfile.TemporaryDirectory() as d:
            r = rcv(d)
            ent = E(3)
            tid = ent["tid"]
            t = ms.ev(term, 5, tid=tid, px=None if term == "CANCEL" else 2601.0, sl=2605.0, otype="MARKET" if term == "CANCEL" else "",
                      info="x")
            a = r.process(body(t))
            b = r.process(body(ent))
            r.store.db.close()
            r2 = rcv(d)                                 # restart between the two: the terminal fact must persist
            again = r2.process(body(E(3)))
            it = intent(r2, ent["key"])
            res1[term] = (a["status"], ev_status(r2, t["key"]), b["status"], it["eligible"], it["reason"], again["status"],
                          r2.store.one("SELECT state FROM tv_trades WHERE tid=?", (tid,))["state"])
    with tempfile.TemporaryDirectory() as d:
        r = rcv(d)
        wid = f"W{ms.bar(0) + ms.BAR}"
        we = ms.ev("WAIT_END", 2, tid=wid, px=2650.25, sl=2656.75, tp=2640.5, info="expired")
        ent = E(3, info=f"SATS_PULL;wid={wid}")
        r.process(body(we))
        r.process(body(ent))
        it_w = intent(r, ent["key"])
        wst = r.store.one("SELECT state FROM tv_waits WHERE wid=?", (wid,))["state"]
    check("RG-01 a terminal / cancel fact (TV_CLOSED / TV_FLAT / CANCEL) arriving BEFORE its ENTRY is ACCEPTED and kept (ORPHAN fact, "
          "survives a restart); the later ENTRY is stored as a fact but is NOT an execution candidate (eligible 0, "
          "late:trade_already_terminated) and the trade stays terminal; a WAIT_END arriving first makes the related SATS pull ENTRY "
          "ineligible (late:wait_already_ended), not just a warning",
          all(v[0] == "ACCEPTED" and v[2] == "ACCEPTED" and v[3] == 0 and v[4] == "late:trade_already_terminated" and v[5] == "DUPLICATE"
              for v in res1.values()) and res1["TV_FLAT"][6] in ("INTENT", "CLOSED", "TERMINAL_ENTRY_UNSEEN")
          and it_w["eligible"] == 0 and it_w["reason"].startswith("late:wait_already_ended") and wst == "ENDED_START_UNSEEN",
          str((res1, dict(it_w), wst)))
    # 2. management out of order
    with tempfile.TemporaryDirectory() as d:
        r = rcv(d)
        ent = E(3)
        tid = ent["tid"]
        tp = ms.ev("TP_SET", 4, tid=tid, px=2600.4, sl=2605.0, tp=2592.5, info="sats_tp0")
        fill = ms.ev("TV_FILL", 4, tid=tid, px=2600.4, sl=2605.0, info="virtual_fill")
        be = ms.ev("BE_MOVE", 9, tid=tid, px=2600.4, sl=2600.4, tp=2592.5, info="breakeven_tv_fill_based")
        flat = ms.ev("TV_FLAT", 12, tid=tid, px=2600.4, sl=2600.4, tp=2592.5, info="virtual_position_closed")
        late_be = ms.ev("BE_MOVE", 14, tid=tid, px=2600.4, sl=2600.4, tp=2592.5, info="breakeven_tv_fill_based")
        r.process(body(ent))
        r.process(body(tp))
        s_tp_before = ev_status(r, tp["key"])
        i_tp_before = intent(r, tp["key"])["eligible"]
        r.process(body(be))                              # BE before the fill too: pending
        r.process(body(fill))
        s_tp_after, s_be = ev_status(r, tp["key"]), ev_status(r, be["key"])
        tr = r.store.one("SELECT * FROM tv_trades WHERE tid=?", (tid,))
        sl_after_be = tr["sl"]
        claim1 = r.claim(tp["key"])
        claim2 = r.claim(tp["key"])
        r.process(body(flat))
        r.process(body(late_be))
        tr2 = r.store.one("SELECT * FROM tv_trades WHERE tid=?", (tid,))
        s_late = ev_status(r, late_be["key"])
        old_tp = ms.ev("TP_SET", 4, tid=tid, px=2600.4, sl=2605.0, tp=2592.5, info="sats_tp0")
        dup_old = r.process(body(old_tp))
    check("RG-02 ENTRY -> TP_SET -> BE_MOVE -> TV_FILL arrival: TP_SET / BE_MOVE are PENDING (not eligible) until the fill arrives, then "
          "replayed in bar / rank order and APPLIED (TP 2592.5, stop moved to the virtual fill 2600.4 by the newer BE, never back to the "
          "older 2605); after TV_FLAT a later valid BE (bar 14) is AFTER_TERMINAL and the trade stays CLOSED with the BE stop; an intent "
          "can be claimed once only (second claim False); re-sending the old TP_SET is DUPLICATE",
          s_tp_before == ("PENDING", "waiting_for_tv_fill") and i_tp_before == 0 and s_tp_after == ("APPLIED", "") and s_be == ("APPLIED", "")
          and sl_after_be == 2600.4 and tr["tp"] == 2592.5 and claim1 and not claim2 and tr2["state"] == "CLOSED" and tr2["sl"] == 2600.4
          and s_late == ("AFTER_TERMINAL", "trade_closed") and dup_old["status"] == "DUPLICATE",
          str((s_tp_before, s_tp_after, s_be, sl_after_be, claim1, claim2, tr2["state"], s_late)))
    with tempfile.TemporaryDirectory() as d:
        r = rcv(d)
        ent = E(3)
        tid = ent["tid"]
        r.process(body(ent))
        r.process(body(ms.ev("TV_FILL", 4, tid=tid, px=2600.4, sl=2605.0, info="virtual_fill")))
        r.process(body(ms.ev("BE_MOVE", 9, tid=tid, px=2600.4, sl=2600.4, tp=2592.5, info="breakeven_tv_fill_based")))
        older = ms.ev("TP_SET", 4, tid=tid, px=2600.4, sl=2605.0, tp=2592.5, info="sats_tp0")
        r.process(body(older))                          # same-bar TP_SET arriving after the newer BE: replayed before it
        tr = r.store.one("SELECT * FROM tv_trades WHERE tid=?", (tid,))
        mism = ms.ev("BE_MOVE", 11, tid=tid, px=2601.0, sl=2601.0, tp=2592.5, info="breakeven_tv_fill_based")
        r.process(body(mism))
    check("RG-03 a delayed same-bar TP_SET arriving after the newer BE_MOVE is replayed in bar order (APPLIED) and the stop stays at the newer "
          "BE value 2600.4 (not overwritten by the older 2605); a BE whose fill price differs from the recorded virtual fill is CONFLICT",
          tr["sl"] == 2600.4 and tr["tp"] == 2592.5 and ev_status(r, older["key"]) == ("APPLIED", "")
          and ev_status(r, mism["key"])[0] == "CONFLICT", str((dict(tr), ev_status(r, mism["key"]))))
    # 3. abnormal values
    base = json.dumps(E(20), separators=(",", ":"))
    cases = {"NaN": base.replace('"sl":2605.0', '"sl":NaN'), "-Infinity": base.replace('"tp":2592.5', '"tp":-Infinity'),
             "1e400": base.replace('"sl":2605.0', '"sl":1e400'), "neg": body(E(21, px=-2600.0, sl=-2595.0, tp=-2607.5)),
             "zero": body(E(22, px=0.0)), "bool_px": base.replace('"px":2600.0', '"px":true'),
             "huge_int_px": base.replace('"px":2600.0', '"px":' + str(10 ** 400)),
             "bar_close_10e40": base.replace(f'"bar_close":{ms.bar(20) + ms.BAR}', '"bar_close":' + str(10 ** 40)),
             "unaligned": body(E(23, bar_open=ms.bar(23) + 60000)), "not_5m": body(E(24, bar_close=ms.bar(24) + 600000)),
             "dup_field": base[:-1] + ',"sl":2606.0}', "unknown_field": base[:-1] + ',"extra":1}', "non_utf8": b'{"ev":"\xff"}',
             "be_long_neg": body(ms.ev("BE_MOVE", 25, tid=f"T{ms.bar(24) + ms.BAR}", side="LONG", px=2600.0, sl=-999.0, tp=2590.0)),
             "deep": "[" * 5000 + "]" * 5000, "string_body_null": "null", "array": "[1,2]",
             "tid_before_bar": body(ms.ev("TV_FILL", 26, tid=f"T{ms.bar(27) + ms.BAR}", px=2600.0, sl=2605.0)),
             "ohlc_bad": body(E(27, ohlc=(2600.0, 2599.0, 2601.0, 2600.0)))}
    got = {}
    with tempfile.TemporaryDirectory() as d:
        r = rcv(d)
        for k, v in cases.items():
            res = r.process(v.encode() if isinstance(v, str) else v)
            got[k] = (res["status"], res["reasons"][:2])
        n = r.store.one("SELECT COUNT(*) n FROM receipts")["n"]
        ints_ok = all(x["bar_close"] is None or abs(x["bar_close"]) < 2 ** 63 for x in r.store.all("SELECT bar_close FROM receipts"))
    check("RG-04 abnormal input never raises and is always recorded (one receipt each, %d): NaN / -Infinity (non-standard constants), 1e400 "
          "and 10**400 (non-finite / out of range), negative / zero / boolean prices, bar_close 10**40, an unaligned or non-5m bar, a "
          "duplicate or unknown field, non-UTF-8, a LONG BE with stop -999 on the SHORT strategy, deeply nested JSON, null / array bodies, an "
          "event before its entry bar, inconsistent OHLC -> REJECTED with a reason; stored integers stay within SQLite's range" % len(cases),
          all(v[0] == "REJECTED" for v in got.values()) and n == len(cases) and ints_ok
          and "format:nonstandard_constant:NaN" in got["NaN"][1] and got["1e400"][1][0].startswith("value:not_finite")
          and "time:out_of_range:bar_close" in got["bar_close_10e40"][1] and "time:bar_not_aligned" in got["unaligned"][1]
          and "format:duplicate_field" in got["dup_field"][1] and "format:not_utf8" in got["non_utf8"][1], str(got))
    # 5. BAR data + BE stop marked recompute-only
    with tempfile.TemporaryDirectory() as d:
        r = rcv(d)
        for mm in ms.normal_flow():
            r.process(body(mm))
        bars = r.store.all("SELECT * FROM tv_bars ORDER BY bar_close")
        be_key = ms.normal_flow()[8]["key"]
        be_use = r.store.one("SELECT use FROM intents WHERE key=?", (be_key,))["use"]
        flat_use = r.store.one("SELECT use FROM intents WHERE key=?", (ms.normal_flow()[9]["key"],))["use"]
    check("RG-05 BAR events (bar open / close times, OHLC, TradingView virtual side / stop / TP, tv_state / tv_fill in info) are stored in "
          "tv_bars independently of the trade facts; the BE_MOVE intent says RECOMPUTE_BE_FROM_MT5_FILL (the TradingView stop is never to be "
          "applied to XS) and TV_FLAT says REVIEW_TV_EXIT (MT5 may still hold a position)",
          len(bars) == 3 and all(b["o"] and b["h"] and b["l"] and b["c"] and b["bar_open"] for b in bars)
          and json.loads(bars[2]["info"]).get("tv_fill") == "2651.9" and be_use.startswith("RECOMPUTE_BE_FROM_MT5_FILL")
          and flat_use.startswith("REVIEW_TV_EXIT"), str((len(bars), be_use, flat_use)))
    # 6. PowerShell scripts (static: not executed here)
    rd = lambda f: open(os.path.join(RDIR, f), encoding="utf-8").read()
    s, p, t = rd("start_receiver.ps1"), rd("stop_receiver.ps1"), rd("test_samples.ps1")
    check("RG-06 PowerShell (static): start quotes every argument with the Windows rules (Format-WinArg, Resolve-Path -LiteralPath, one "
          "argument line, PYTHONUTF8) so spaces / Japanese paths work; stop reads the JSON PID file and stops only when the command line has "
          "xau_receiver.py + serve AND the process start time matches (re-used PID safe); the sample test writes a new data folder under "
          "%TEMP% and never deletes the real one; the config loader accepts UTF-8 with BOM",
          "function Format-WinArg" in s and "Resolve-Path -LiteralPath $Config" in s and "-ArgumentList $argLine" in s and "PYTHONUTF8" in s
          and "Win32_Process" in p and 'Contains("xau_receiver.py")' in p and 'Contains("serve")' in p and "CreationDate" in p
          and "started_utc" in p and "GetTempPath()" in t and "Remove-Item" not in t.split("Write-Host")[0]
          and 'encoding="utf-8-sig"' in rd("xau_receiver.py"))


def gate_au3():
    # 1. TP_SET must not loosen the stop after a breakeven (reported sequence), late / duplicate TP_SET handling
    with tempfile.TemporaryDirectory() as d:
        r = rcv(d)
        ent = E(3)
        tid = ent["tid"]
        seq = [ent, ms.ev("TV_FILL", 4, tid=tid, px=2600.4, sl=2605.0, info="virtual_fill"),
               ms.ev("BE_MOVE", 9, tid=tid, px=2600.4, sl=2600.4, tp=2592.5, info="breakeven_tv_fill_based"),
               ms.ev("TP_SET", 12, tid=tid, px=2600.4, sl=2605.0, tp=2592.5, info="sats_tp0")]
        res = [r.process(body(m)) for m in seq]
        tr = r.store.one("SELECT * FROM tv_trades WHERE tid=?", (tid,))
        it = intent(r, seq[3]["key"])
        claim_bad = r.claim(seq[3]["key"])
    check("RG-07 reported: ENTRY 2600 / SL 2605 / TP 2592.5 -> TV_FILL 2600.4 -> BE_MOVE SL 2600.4 -> a later-bar TP_SET (SL 2605, sats_tp0): "
          "the TP_SET is accepted as a fact but CONFLICT (tp_set_not_on_fill_bar; it would also loosen the stop) and not applied; the "
          "trade keeps SL 2600.4; its intent eligible 0 and claim() refuses it",
          [x["status"] for x in res] == ["ACCEPTED"] * 4 and ev_status(r, seq[3]["key"]) == ("CONFLICT", "tp_set_not_on_fill_bar")
          and tr["sl"] == 2600.4 and it["eligible"] == 0 and not claim_bad, str((ev_status(r, seq[3]["key"]), tr["sl"], dict(it))))
    out = {}
    with tempfile.TemporaryDirectory() as d:
        r = rcv(d)
        ent = E(3)
        tid = ent["tid"]
        fill = ms.ev("TV_FILL", 4, tid=tid, px=2600.4, sl=2605.0, info="virtual_fill")
        be = ms.ev("BE_MOVE", 9, tid=tid, px=2600.4, sl=2600.4, tp=2592.5, info="breakeven_tv_fill_based")
        late_tp = ms.ev("TP_SET", 4, tid=tid, px=2600.4, sl=2605.0, tp=2592.5, info="sats_tp0")      # same bar as the fill, arrives last
        for m in (ent, fill, be, late_tp):
            r.process(body(m))
        out["late"] = (ev_status(r, late_tp["key"]), dict(intent(r, late_tp["key"])), r.store.one("SELECT sl FROM tv_trades")["sl"],
                       r.claim(late_tp["key"]), dict(intent(r, be["key"])))
    with tempfile.TemporaryDirectory() as d:
        r = rcv(d)
        ent = E(3)
        tid = ent["tid"]
        tp_ok = ms.ev("TP_SET", 4, tid=tid, px=2600.4, sl=2605.0, tp=2592.5, info="sats_tp0")
        tp_bad = ms.ev("TP_SET", 5, tid=tid, px=2600.4, sl=2604.0, tp=2592.5, info="sats_tp0")
        for m in (ent, ms.ev("TV_FILL", 4, tid=tid, px=2600.4, sl=2605.0, info="virtual_fill"), tp_ok, tp_bad):
            r.process(body(m))
        out["dup"] = (ev_status(r, tp_ok["key"]), ev_status(r, tp_bad["key"]), dict(intent(r, tp_ok["key"])))
    with tempfile.TemporaryDirectory() as d:
        r = rcv(d)
        ent = E(30)
        tid = ent["tid"]
        wrong = ms.ev("TP_SET", 31, tid=tid, px=2600.4, sl=2604.0, tp=2592.5, info="sats_tp0")
        for m in (ent, ms.ev("TV_FILL", 31, tid=tid, px=2600.4, sl=2605.0, info="virtual_fill"), wrong):
            r.process(body(m))
        out["initial"] = ev_status(r, wrong["key"])
    L = out["late"]
    check("RG-07b a same-bar TP_SET arriving after the newer BE_MOVE: replayed in bar order (APPLIED, the state keeps SL 2600.4) but it is "
          "never an execution candidate (stale:arrived_after_newer_event) and claim() refuses it; the BE intent is scope 'trigger only' "
          "(recompute from the MT5 fill); a second TP_SET is CONFLICT duplicate_tp_set; a TP_SET whose stop is not the initial SL is "
          "CONFLICT; the TP_SET intent scope is 'tp only (the stop is never taken from TP_SET)'",
          L[0] == ("APPLIED", "") and L[1]["eligible"] == 0 and L[1]["reason"].startswith("stale:arrived_after_newer_event") and L[2] == 2600.4
          and L[3] is False and L[4]["scope"].startswith("trigger only") and out["dup"][1] == ("CONFLICT", "duplicate_tp_set")
          and out["dup"][2]["scope"].startswith("tp only") and out["dup"][2]["eligible"] == 1
          and out["initial"] == ("CONFLICT", "tp_set_stop_not_initial"), str(out))
    # 2. deadline re-checked at claim()
    clk = {}
    clock = lambda: clk["t"]
    with tempfile.TemporaryDirectory() as d:
        ent = E(50)
        bc = ent["bar_close"]
        clk["t"] = bc + 1000
        r = rcv(d, clock=clock, policy={"max_age_sec": 60})
        r.process(body(ent))
        before = dict(intent(r, ent["key"]))
        r.store.db.close()
        clk["t"] = bc + 86_400_000
        r2 = rcv(d, clock=clock, policy={"max_age_sec": 60})        # restart, next day
        c_next_day = r2.claim(ent["key"])
        after = dict(intent(r2, ent["key"]))
        clk["t"] = bc + 2000
        c_again = r2.claim(ent["key"])
        log = [dict(x) for x in r2.store.all("SELECT ok, reason, attempt_ms FROM claim_log WHERE key=?", (ent["key"],))]
    with tempfile.TemporaryDirectory() as d:
        ent2 = E(52)
        clk["t"] = ent2["bar_close"] + 1000
        r = rcv(d, clock=clock, policy={"max_age_sec": 60})
        r.process(body(ent2))
        clk["t"] = ent2["bar_close"] + 30_000
        c_in_time = r.claim(ent2["key"])
        row = dict(intent(r, ent2["key"]))
    with tempfile.TemporaryDirectory() as d:
        ent3 = E(54)
        clk["t"] = ent3["bar_close"] + 1000
        r = rcv(d, clock=clock)
        r.process(body(ent3))
        clk["t"] = ent3["bar_close"] + 86_400_000
        c_no_policy = r.claim(ent3["key"])
    check("RG-08 reported: max_age_sec 60, ENTRY received 1 s after the bar close (eligible), restart, claim() the next day -> False; the "
          "intent becomes eligible 0 'revoked:expired_at_claim' and stays unclaimable (also with an earlier clock); within the deadline "
          "claim() succeeds once; without a deadline (default) the time is not limited; received / first decided / decided / claimed / "
          "last claim times are separate columns and every attempt is in claim_log",
          before["eligible"] == 1 and before["received_ms"] == bc + 1000 and before["first_decided_ms"] == bc + 1000 and before["bar_close"] == bc
          and c_next_day is False and after["eligible"] == 0 and after["reason"] == "revoked:expired_at_claim" and after["claimed_ms"] is None
          and after["last_claim_ms"] == bc + 86_400_000 and c_again is False and [x["reason"] for x in log][0] == "expired_at_claim"
          and c_in_time is True and row["claimed_ms"] == ent2["bar_close"] + 30_000 and c_no_policy is True, str((before, after, log, row)))
    # 3. claim vs evaluation race, AU-2 database upgrade
    with tempfile.TemporaryDirectory() as d:
        r = rcv(d)
        ent = E(60)
        r.process(body(ent))
        res = []
        r_other = rcv(d)                                             # a second connection (as a separate later-stage process would be)
        ths = [threading.Thread(target=lambda rr=rr: res.append(rr.claim(ent["key"]))) for rr in [r, r_other] * 6]
        ths.append(threading.Thread(target=lambda: r.process(body(ms.ev("CANCEL", 61, tid=ent["tid"], otype="MARKET", sl=2605.0, info="x")))))
        [x.start() for x in ths]
        [x.join() for x in ths]
        n_ok = sum(1 for x in res if x)
        logn = r.store.one("SELECT COUNT(*) n FROM claim_log")["n"]
    import sqlite3
    with tempfile.TemporaryDirectory() as d:
        db = sqlite3.connect(os.path.join(d, "xau_receiver.sqlite3"))
        db.executescript("CREATE TABLE intents (key TEXT PRIMARY KEY, tid TEXT, ev TEXT, eligible INTEGER NOT NULL, use TEXT, reason TEXT,"
                         " decided_ms INTEGER, claimed_ms INTEGER, claim_note TEXT);"
                         "CREATE TABLE meta (k TEXT PRIMARY KEY, v TEXT); INSERT INTO meta VALUES ('db_version','2');")
        db.commit()
        db.close()
        r = rcv(d)
        cols = {x[1] for x in r.store.db.execute("PRAGMA table_info(intents)")}
        ver = r.store.one("SELECT v FROM meta WHERE k='db_version'")["v"]
    check("RG-09 claim() racing with other claims (two connections, 12 threads) and with an event evaluation: at most one success, every "
          "attempt logged; a database created by AU-2 is upgraded in place (intents get bar_close / received_ms / first_decided_ms / scope / "
          "last_claim_ms, db_version %s)" % xr.DB_VERSION,
          n_ok <= 1 and logn == 12 and {"bar_close", "received_ms", "first_decided_ms", "scope", "last_claim_ms"} <= cols and ver == xr.DB_VERSION,
          str((n_ok, logn, ver)))


def _old_receiver(rev, name):
    """the receiver module exactly as committed at `rev` (AU-2 = 070c1ed, AU-3 = 287d371), to create real old databases."""
    import importlib.util
    import subprocess
    src = subprocess.run(["git", "-C", ROOT, "show", f"{rev}:automation/xau_short/receiver/xau_receiver.py"], capture_output=True,
                         text=True).stdout
    d = tempfile.mkdtemp()
    p = os.path.join(d, f"{name}.py")
    open(p, "w", encoding="utf-8").write(src)
    spec = importlib.util.spec_from_file_location(name, p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def gate_au4():
    # 1. a normal TP_SET updates the TP only
    with tempfile.TemporaryDirectory() as d:
        r = rcv(d)
        ent = E(3, info="CURRENT")
        tid = ent["tid"]
        tp = ms.ev("TP_SET", 4, tid=tid, px=2600.4, sl=2605.0, tp=2593.5, info="fill_rr")
        for m in (ent, ms.ev("TV_FILL", 4, tid=tid, px=2600.4, sl=2605.0, info="virtual_fill"), tp):
            r.process(body(m))
        a = dict(r.store.one("SELECT * FROM tv_trades WHERE tid=?", (tid,)))
        r.process(body(ms.ev("BE_MOVE", 9, tid=tid, px=2600.4, sl=2600.4, tp=2593.5, info="breakeven_tv_fill_based")))
        b = dict(r.store.one("SELECT * FROM tv_trades WHERE tid=?", (tid,)))
        it = dict(intent(r, tp["key"]))
    check("RG-10 reported: Current ENTRY 2600 / SL 2605 / TP 2592.5 -> TV_FILL 2600.4 -> same-bar TP_SET TP 2593.5 (fill_rr): APPLIED and "
          "the trade's TP becomes 2593.5 (initial TP 2592.5 kept in entry_tp), SL stays 2605; a later BE_MOVE moves only the stop "
          "(2600.4) and keeps TP 2593.5; the TP_SET intent is eligible with use RECOMPUTE_TP_FROM_MT5_FILL / scope tp only",
          ev_status(r, tp["key"]) == ("APPLIED", "") and a["tp"] == 2593.5 and a["entry_tp"] == 2592.5 and a["sl"] == 2605.0
          and b["sl"] == 2600.4 and b["tp"] == 2593.5 and it["eligible"] == 1 and it["use"] == "RECOMPUTE_TP_FROM_MT5_FILL"
          and it["scope"].startswith("tp only"), str((a["tp"], a["sl"], b["tp"], b["sl"], it["eligible"])))
    # 2. the deadline decided after the lock / write-transaction waits
    import sqlite3
    import time as _t
    res = {}
    for mode in ("lock", "sqlite", "control"):
        with tempfile.TemporaryDirectory() as d:
            ent = E(70)
            bc = ent["bar_close"]
            clk = {"t": bc + 1000}
            r = rcv(d, clock=lambda: clk["t"], policy={"max_age_sec": 60})
            r.process(body(ent))
            clk["t"] = bc + 59_000
            out = []
            other = None
            if mode == "lock":
                r.store.lock.acquire()
            elif mode == "sqlite":
                other = sqlite3.connect(r.store.path, isolation_level=None, timeout=30)
                other.execute("BEGIN IMMEDIATE")
            th = threading.Thread(target=lambda: out.append(r.claim(ent["key"])))
            th.start()
            _t.sleep(0.4)
            alive = th.is_alive()
            if mode != "control":
                clk["t"] = bc + 61_000          # the clock passes the deadline while claim() waits
            if mode == "lock":
                r.store.lock.release()
            elif mode == "sqlite":
                other.execute("COMMIT")
                other.close()
            th.join(10)
            lg = dict(r.store.one("SELECT * FROM claim_log WHERE key=?", (ent["key"],)))
            res[mode] = (alive, out, lg["attempt_ms"] - bc, lg["decided_ms"] - bc, lg["reason"], intent(r, ent["key"])["eligible"])
    check("RG-11 reported: deadline 60 s, claim() called at 59 s while (a) the in-process lock or (b) the SQLite write lock (another "
          "connection's BEGIN IMMEDIATE) is held, the clock passes 61 s during the wait -> False, 'expired_at_claim', the intent revoked; "
          "claim_log keeps the attempt time (59 s) and the decision time (61 s) apart; control without the clock change -> True at 59 s",
          res["lock"][:2] == (True, [False]) and res["lock"][2:5] == (59_000, 61_000, "expired_at_claim") and res["lock"][5] == 0
          and res["sqlite"][:2] == (True, [False]) and res["sqlite"][2:5] == (59_000, 61_000, "expired_at_claim")
          and res["control"][1] == [True] and res["control"][2:5] == (59_000, 59_000, "claimed"), str(res))
    # 3. real AU-2 / AU-3 databases with data
    mig = {}
    for rev, name in (("070c1ed", "xr_au2"), ("287d371", "xr_au3")):
        old = _old_receiver(rev, name)
        with tempfile.TemporaryDirectory() as d:
            ocfg = old.load_config(None)
            ocfg["data_dir"] = d
            o = old.Receiver(ocfg, log=QUIET)
            ent = E(3)
            tid = ent["tid"]
            fill = ms.ev("TV_FILL", 4, tid=tid, px=2600.4, sl=2605.0, info="virtual_fill")
            be = ms.ev("BE_MOVE", 9, tid=tid, px=2600.4, sl=2600.4, tp=2592.5, info="breakeven_tv_fill_based")
            bad_tp = ms.ev("TP_SET", 12, tid=tid, px=2600.4, sl=2605.0, tp=2592.5, info="sats_tp0")
            o.process(body(ent))
            claimed_entry = o.claim(ent["key"])
            for m in (fill, be, bad_tp, "not json", ent):
                o.process(body(m))
            old_bad = dict(o.store.one("SELECT eligible, claimed_ms FROM intents WHERE key=?", (bad_tp["key"],)))
            old_sl = o.store.one("SELECT sl FROM tv_trades WHERE tid=?", (tid,))["sl"]
            n_rec = o.store.one("SELECT COUNT(*) n FROM receipts")["n"]
            ent_claim_ms = o.store.one("SELECT claimed_ms FROM intents WHERE key=?", (ent["key"],))["claimed_ms"]
            o.store.db.close()
            r = rcv(d)                                                     # open with the current code
            new_bad = dict(intent(r, bad_tp["key"]))
            new = dict(r.store.one("SELECT * FROM tv_trades WHERE tid=?", (tid,)))
            mig[name] = dict(
                old_bad_eligible=old_bad["eligible"], old_sl=old_sl, claimed_entry=claimed_entry,
                bad_status=ev_status(r, bad_tp["key"]), bad_eligible=new_bad["eligible"], bad_claim=r.claim(bad_tp["key"]),
                sl=new["sl"], tp=new["tp"], receipts_kept=r.store.one("SELECT COUNT(*) n FROM receipts")["n"] == n_rec,
                entry_claim_kept=intent(r, ent["key"])["claimed_ms"] == ent_claim_ms, entry_reclaim=r.claim(ent["key"]),
                be_claim=r.claim(be["key"]), rules=r._meta("rules_version"), pending=r._meta("reeval_pending"),
                cols_filled=intent(r, be["key"])["bar_close"] == be["bar_close"] and intent(r, be["key"])["received_ms"] is not None)
            other = sqlite3.connect(r.store.path, isolation_level=None)
            other.execute("INSERT OR REPLACE INTO meta(k, v) VALUES ('reeval_pending', '1')")
            other.close()
            r.process(body(ms.ev("TV_FLAT", 15, tid=tid, px=2600.4, sl=2600.4, tp=2592.5, info="virtual_position_closed")))
            ent2 = E(30)                                                   # trade A is closed: a new, eligible ENTRY
            r.process(body(ent2))
            mig[name]["claim_while_pending"] = r.claim(ent2["key"])
            mig[name]["pending_reason"] = r.store.one("SELECT reason FROM claim_log ORDER BY id DESC LIMIT 1")["reason"]
            r.store.db.close()
            r3 = rcv(d)                                                    # the next open finishes the pending re-evaluation
            mig[name]["claim_after"] = r3.claim(ent2["key"])
    a2, a3 = mig["xr_au2"], mig["xr_au3"]
    ok = (a2["old_bad_eligible"] == 1 and a2["old_sl"] == 2605.0 and a3["old_bad_eligible"] == 0
          and all(m["claimed_entry"] and m["bad_status"][0] == "CONFLICT" and m["bad_eligible"] == 0 and m["bad_claim"] is False
                  and m["sl"] == 2600.4 and m["tp"] == 2592.5 and m["receipts_kept"] and m["entry_claim_kept"] and m["entry_reclaim"] is False
                  and m["be_claim"] is True and m["rules"] == xr.RULES_VERSION and m["pending"] is None and m["cols_filled"]
                  and m["claim_while_pending"] is False and m["pending_reason"] == "reevaluation_pending" and m["claim_after"] is True
                  for m in mig.values()))
    check("RG-12 reported: databases written by the real AU-2 (070c1ed) and AU-3 (287d371) receivers with a claimed ENTRY, TV_FILL, BE_MOVE, "
          "the invalid later-bar TP_SET (AU-2: applied, SL back to 2605, eligible 1), a rejected receipt and a duplicate: opening with the "
          "current code re-evaluates every stored fact (rules version %s) -> the TP_SET is CONFLICT / eligible 0 / not claimable, the "
          "trade is SL 2600.4 / TP 2592.5, receipts and the claimed ENTRY (claimed_ms) are kept and it cannot be claimed again, the valid "
          "BE intent stays claimable, the new intent columns are back-filled; while a re-evaluation is pending claim() refuses "
          "(reevaluation_pending) and the next open completes it" % xr.RULES_VERSION, ok, str(mig))


def main():
    for g in (gate_basic, gate_regressions, gate_au3, gate_au4):
        try:
            g()
        except Exception:
            import traceback
            check(f"{g.__name__} completed without error", False, traceback.format_exc()[-1500:])
    fails = 0
    for nm, ok, d in RESULTS:
        fails += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {nm[:150].ljust(150)}  {'' if ok else d}")
    print(f"\n{len(RESULTS) - fails}/{len(RESULTS)} passed  [local Python: receiver / storage / HTTP; no TradingView / Windows / MT5]")
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
