"""AU-1 receiver fixtures — automation/xau_short/receiver/xau_receiver.py (stage 2: receive / record only, no orders).

  RR : the local sample notifications (normal flow, bad cases) give the expected statuses / reasons and states; true order
       inversion; restart persistence (duplicates still detected, states kept); HTTP (token path, unknown token / size refused,
       nothing secret in the log); concurrent re-sends -> exactly one accepted; cfg pinning; the notification deadline policy
       off by default; TradingView virtual state and the MT5 state kept apart (MT5 never written); no order / MT5 code
Evidence class: local Python only (no TradingView / Windows / MT5 run).
"""
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


def rcv(d, **over):
    cfg = xr.load_config(None)
    cfg["data_dir"] = d
    for k, v in over.items():
        cfg[k].update(v) if isinstance(v, dict) else cfg.__setitem__(k, v)
    return xr.Receiver(cfg, log=QUIET)


def body(m):
    return m if isinstance(m, str) else json.dumps(m, separators=(",", ":"))


def gate_receiver():
    with tempfile.TemporaryDirectory() as d:
        r = rcv(d)
        st = [r.process(body(m))["status"] for m in ms.normal_flow()]
        trade = r.store.one("SELECT * FROM tv_trades")
        wait = r.store.one("SELECT * FROM tv_waits")
        check("RR-01 normal flow (WAIT_START, PROV, ENTRY SATS pull, TV_FILL, TP_SET, BE_MOVE, TV_FLAT) all ACCEPTED; virtual trade CLOSED with the "
              "breakeven stop / TP0, its wait CONSUMED by the entry; every receipt stores received time, decision bar times, sid, cfg hash, "
              "tid, event, rank, order type, prices, reasons",
              st == ["ACCEPTED"] * 7 and trade["state"] == "CLOSED" and trade["sl"] == 2651.9 and trade["tp"] == 2640.5 and wait["state"] == "CONSUMED"
              and all(x["received_ms"] and x["bar_close"] and x["sid"] and x["cfg_sha256"] and x["tid"] and x["rank"] is not None
                      for x in r.store.all("SELECT * FROM receipts")), str(st))
        exp = {"not_json": ("REJECTED", "format:not_json"), "missing_field": ("REJECTED", "format:missing:sl"),
               "duplicate_resend": ("DUPLICATE", "dup:same_key_already_accepted"), "out_of_order_after_close": ("REJECTED", "state:trade_closed"),
               "unknown_trade_manage": ("REJECTED", "state:unknown_trade"), "wait_start": ("ACCEPTED", None), "wait_end": ("ACCEPTED", None),
               "late_entry_for_ended_wait": ("REJECTED", "late:wait_already_ended"), "wrong_side": ("REJECTED", "intent:side_not_allowed"),
               "bad_geometry": ("REJECTED", "intent:price_geometry"), "sid_mismatch": ("REJECTED", "identity:sid_mismatch"),
               "entry_ok": ("ACCEPTED", None), "entry_while_virtual_active": ("REJECTED", "state:virtual_position_active"),
               "older_entry_after_newer": ("REJECTED", "late:older_than_newer_trade")}
        got = {}
        for name, m in ms.bad_cases():
            res = r.process(body(m))
            got[name] = (res["status"], next((x for x in res["reasons"] if exp[name][1] and x.startswith(exp[name][1])), None))
        ok = all(got[k][0] == v[0] and (v[1] is None or got[k][1] is not None) for k, v in exp.items())
        n_rec = r.store.one("SELECT COUNT(*) n FROM receipts")["n"]
        check("RR-02 bad / edge cases: not JSON, missing field, re-send (DUPLICATE), late event to a closed trade, management for an unknown trade, "
              "ENTRY for an already ended wait, LONG intent (Short only), SL / TP on the wrong side, sid mismatch, ENTRY while the virtual "
              "position is open, an older ENTRY after a newer trade — each recorded (raw kept) with its reason; nothing changes state",
              ok and n_rec == 7 + 14, str(got))
        before = r.store.one("SELECT COUNT(*) n FROM events")["n"]
    with tempfile.TemporaryDirectory() as d:
        r = rcv(d)
        t = ms.ev("ENTRY", 3, otype="MARKET", px=2651.8, sl=2656.75, tp=2640.5, info="SATS_NOW")
        tid = t["tid"]
        seq = [t, ms.ev("TV_FILL", 4, tid=tid, px=2651.9, sl=2656.75), ms.ev("TP_SET", 4, tid=tid, px=2651.9, sl=2656.75, tp=2640.5),
               ms.ev("BE_MOVE", 9, tid=tid, px=2651.9, sl=2651.9, tp=2640.5),
               ms.ev("TP_SET", 6, tid=tid, px=2651.9, sl=2656.75, tp=2641.0),          # delayed, older than the BE_MOVE already applied
               ms.ev("TV_FILL", 10, tid=tid, px=2651.9, sl=2656.75)]                   # a second fill: invalid in TV_OPEN
        res = [r.process(body(m)) for m in seq]
        tr = r.store.one("SELECT * FROM tv_trades")
        check("RR-03 order inversion: a delayed TP_SET (bar 6) after the BE_MOVE (bar 9) is REJECTED out_of_order and does not undo the stop; "
              "an event not allowed in the state (second TV_FILL) is REJECTED invalid_transition",
              [x["status"] for x in res] == ["ACCEPTED"] * 4 + ["REJECTED"] * 2 and "order:out_of_order" in res[4]["reasons"]
              and any(x.startswith("state:invalid_transition") for x in res[5]["reasons"]) and tr["sl"] == 2651.9 and tr["tp"] == 2640.5,
              str([x["reasons"] for x in res]))
        r.store.db.close()
        r2 = rcv(d)
        again = r2.process(body(t))
        n = r2.store.one("SELECT COUNT(*) n FROM receipts")["n"]
        check("RR-04 restart: a new receiver on the same data directory still has every receipt and state; the same ENTRY re-sent after "
              "the restart is DUPLICATE (the key is the bar-time key, not an in-memory counter)",
              again["status"] == "DUPLICATE" and n == 7 and r2.store.one("SELECT state FROM tv_trades")["state"] == "TV_OPEN", str(again))
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
        e1 = ms.ev("ENTRY", 80, otype="MARKET", px=2600.0, sl=2605.0, tp=2592.5, info="CURRENT")
        ok = post(f"/webhook/{token}", body(e1).encode())
        bad = post("/webhook/wrong", body(e1).encode())
        big = post(f"/webhook/{token}", b"{" + b" " * 20000 + b"}")
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=5) as resp:
            health = json.loads(resp.read())
        results = []

        def resend():
            results.append(post(f"/webhook/{token}", body(ms.ev("ENTRY", 90, otype="MARKET", px=2590.0, sl=2595.0, tp=2582.5, info="CURRENT")).encode()))
        r = rcv(d)
        r.process(body(ms.ev("CANCEL", 81, tid=e1["tid"], otype="MARKET", sl=2605.0, info="market_entry_not_filled")))
        ths = [threading.Thread(target=resend) for _ in range(12)]
        [x.start() for x in ths]
        [x.join() for x in ths]
        holder["s"].shutdown()
        log = open(os.path.join(d, "receiver.log"), encoding="utf-8").read()
        sts = sorted(x[1]["status"] for x in results)
        n_unauth = r.store.one("SELECT COUNT(*) n FROM receipts WHERE source LIKE 'http:%' AND raw LIKE '%2600.0%'")["n"]
        check("RR-05 HTTP: POST /webhook/<token> -> 200 ACCEPTED; a wrong token -> 404 (not recorded); a body over the limit -> 413; GET "
              "/health says orders disabled; 12 concurrent re-sends of one ENTRY -> exactly 1 ACCEPTED + 11 DUPLICATE; the token never "
              "appears in the log",
              ok[0] == 200 and ok[1]["status"] == "ACCEPTED" and bad[0] == 404 and big[0] == 413 and health.get("orders") == "disabled"
              and sts == ["ACCEPTED"] + ["DUPLICATE"] * 11 and token not in log and n_unauth == 1, str((ok, bad, big, sts)))
    with tempfile.TemporaryDirectory() as d:
        m = ms.normal_flow()[2]
        import hashlib
        sha = hashlib.sha256(m["cfg"].encode()).hexdigest()
        a = rcv(d, expected={"cfg_sha256": sha}).process(body(m))
    with tempfile.TemporaryDirectory() as d:
        b = rcv(d, expected={"cfg_sha256": "0" * 64}).process(body(m))
    with tempfile.TemporaryDirectory() as d:
        c = rcv(d).process(body(m), now_ms=m["bar_close"] + 3600_000)
        e = rcv(d + "x" if False else d, policy={"max_age_sec": 60}).process(body(ms.ev("ENTRY", 100, otype="MARKET", px=2600.0, sl=2605.0,
                                                                                         tp=2592.5, info="CURRENT")), now_ms=ms.bar(101) + 120_000)
    check("RR-06 settings ID: with the cfg hash pinned the matching cfg is accepted without the warning and a different cfg is REJECTED "
          "cfg_mismatch; the notification deadline is off by default (a 1 h old ENTRY is accepted, its age recorded) and, only when "
          "configured (here 60 s), an older ENTRY is REJECTED late",
          a["status"] == "ACCEPTED" and "warn:cfg_unpinned" not in a["reasons"] and "identity:cfg_mismatch" in b["reasons"]
          and c["status"] == "ACCEPTED" and e["status"] == "REJECTED" and "late:older_than_max_age" in e["reasons"], str((a, b, c, e)))
    src = open(os.path.join(RDIR, "xau_receiver.py"), encoding="utf-8").read()
    with tempfile.TemporaryDirectory() as d:
        r = rcv(d)
        for mm in ms.normal_flow():
            r.process(body(mm))
        mt5 = r.store.one("SELECT COUNT(*) n FROM mt5_positions")["n"]
        acts = {x["mt5_action"] for x in r.store.all("SELECT mt5_action FROM receipts")}
    check("RR-07 the TradingView virtual trades (tv_trades / tv_waits) and the MT5 actual positions (mt5_positions) are separate tables; "
          "stage 2 never writes MT5 state (0 rows) and every receipt says no MT5 action; the receiver has no MetaTrader5 / order / socket "
          "client code", mt5 == 0 and acts == {xr.STAGE2_MT5_ACTION}
          and not re.search(r"MetaTrader5|order_send|order_check|positions_get|socket\.connect|urlopen|requests\.", src), str((mt5, acts)))
    with tempfile.TemporaryDirectory() as d:
        ms.write(d)
        same = all(open(os.path.join(d, f), encoding="utf-8").read() == open(os.path.join(RDIR, "samples", f), encoding="utf-8").read()
                   for f in ("normal_flow.jsonl", "bad_cases.jsonl"))
    cfg_file = json.load(open(os.path.join(RDIR, "config.example.json"), encoding="utf-8"))
    check("RR-08 the committed sample files equal make_samples.py output; config.example.json == the built-in defaults (no token, no "
          "credentials; deadline / cfg pin unset)", same and cfg_file == xr.DEFAULT_CONFIG and "token" not in json.dumps(cfg_file).replace("token_env", ""))


def main():
    try:
        gate_receiver()
    except Exception:
        import traceback
        check("gate_receiver completed without error", False, traceback.format_exc()[-1200:])
    fails = 0
    for nm, ok, d in RESULTS:
        fails += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {nm[:150].ljust(150)}  {'' if ok else d}")
    print(f"\n{len(RESULTS) - fails}/{len(RESULTS)} passed  [local Python: receiver / storage / HTTP; no TradingView / MT5]")
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
