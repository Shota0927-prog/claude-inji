#!/usr/bin/env python3
"""Builds the local sample notifications (normal_flow.jsonl / bad_cases.jsonl) with the same field order and key / tid rules as
f_auJson / f_auEmit of ZoneStrategyXAU_Auto.pine (AU-1). Times are UTC epoch ms of 5m bars inside the JST 09:00-02:00 session.
Prices are illustrative (not market data)."""
import json
import os
from datetime import datetime, timedelta, timezone

SID = "XAU-SHORT|XA-23|AU-1"
# the auCfg string the Pine copy is expected to build with the default inputs (str.tostring of floats assumed minimal digits;
# confirm against the first real alert before pinning cfg_sha256)
CFG = ("dir=Short Only;mode=C: Candle Pattern;tim=SATS Pullback;now=1;nc=1;nz=1;tq=0;tqn=1;wait=240;body=1;near=1;neard=1;f=41;"
       "buf=1.5;rr=1.5;tpz=0;be=1;bem=Fixed Distance;bed=15;ber=1;betp=0.5;sess=1,Asia/Tokyo,9:0-2:0;cap=300000;risk=3;"
       "strong=10;zhw=6;role=Retest Confirmed")
RANK = {"PROV": 1, "WAIT_START": 5, "ENTRY": 10, "CANCEL": 20, "TV_FILL": 30, "TP_SET": 40, "BE_MOVE": 50, "CLOSE_REQ": 60,
        "TV_CLOSED": 70, "TV_FLAT": 90, "WAIT_END": 95}
JST = timezone(timedelta(hours=9))
T0 = int(datetime(2026, 10, 27, 10, 0, tzinfo=JST).timestamp() * 1000)     # bar 10:00-10:05 JST
BAR = 300000


def bar(i):
    return T0 + i * BAR


def ev(e, i, tid=None, side="SHORT", otype="", px=None, sl=None, tp=None, info="", sent_delay=1500, **over):
    bo, bc = bar(i), bar(i) + BAR
    tid = tid or {"PROV": f"P{bo}", "WAIT_START": f"W{bc}"}.get(e, f"T{bc}")
    m = {"schema": "xau-auto/1", "sid": SID, "cfg": CFG, "ev": e, "key": f"{SID}|{e}|{tid}|{bc}", "tid": tid, "rank": RANK[e],
         "sym": "OANDA:XAUUSD", "tf": "5", "bar_open": bo, "bar_close": bc, "sent": bc + sent_delay if e != "PROV" else bo + 120000,
         "side": side, "otype": otype, "px": px, "sl": sl, "tp": tp, "info": info}
    m.update(over)
    return m


def normal_flow():
    w = f"W{bar(0) + BAR}"
    t = f"T{bar(3) + BAR}"
    return [
        ev("WAIT_START", 0, px=2650.25, sl=2656.75, tp=2640.5, info="sats_wait"),
        ev("PROV", 3, otype="MARKET", px=2652.1, sl=2656.75, tp=2640.5, info="SATS_PULL"),
        ev("ENTRY", 3, otype="MARKET", px=2651.8, sl=2656.75, tp=2640.5, info=f"SATS_PULL;wid={w}"),
        ev("TV_FILL", 4, tid=t, px=2651.9, sl=2656.75, info="virtual_fill"),
        ev("TP_SET", 4, tid=t, px=2651.9, sl=2656.75, tp=2640.5, info="sats_tp0"),
        ev("BE_MOVE", 9, tid=t, px=2651.9, sl=2651.9, tp=2640.5, info="breakeven"),
        ev("TV_FLAT", 15, tid=t, px=2651.9, sl=2651.9, tp=2640.5, info="virtual_position_closed"),
    ]


def bad_cases():
    flow = normal_flow()
    t = flow[2]["tid"]
    late_w = f"W{bar(30) + BAR}"
    return [
        ("not_json", "this is not json"),
        ("missing_field", {k: v for k, v in ev("ENTRY", 40, otype="MARKET", px=2600.0, sl=2605.0, tp=2592.5).items() if k != "sl"}),
        ("duplicate_resend", flow[2]),
        ("out_of_order_after_close", ev("BE_MOVE", 12, tid=t, px=2651.9, sl=2651.9, tp=2640.5, info="breakeven")),
        ("unknown_trade_manage", ev("TP_SET", 50, tid=f"T{bar(49) + BAR}", px=2600.0, sl=2605.0, tp=2592.5)),
        ("wait_start", ev("WAIT_START", 30, px=2620.0, sl=2626.0, tp=2611.0, info="sats_wait")),
        ("wait_end", ev("WAIT_END", 40, tid=late_w, px=2620.0, sl=2626.0, tp=2611.0, info="expired")),
        ("late_entry_for_ended_wait", ev("ENTRY", 41, otype="MARKET", px=2619.0, sl=2626.0, tp=2611.0, info=f"SATS_PULL;wid={late_w}")),
        ("wrong_side", ev("ENTRY", 60, side="LONG", otype="MARKET", px=2600.0, sl=2595.0, tp=2607.5, info="CURRENT")),
        ("bad_geometry", ev("ENTRY", 61, otype="MARKET", px=2600.0, sl=2595.0, tp=2607.5, info="CURRENT")),
        ("sid_mismatch", ev("ENTRY", 62, otype="MARKET", px=2600.0, sl=2605.0, tp=2592.5, info="CURRENT", sid="XAU-SHORT|XA-22|AU-0",
                            key=f"XAU-SHORT|XA-22|AU-0|ENTRY|T{bar(62) + BAR}|{bar(62) + BAR}")),
        ("entry_ok", ev("ENTRY", 70, otype="MARKET", px=2600.0, sl=2605.0, tp=2592.5, info="SATS_NOW")),
        ("entry_while_virtual_active", ev("ENTRY", 72, otype="MARKET", px=2598.0, sl=2605.0, tp=2587.5, info="CURRENT")),
        ("older_entry_after_newer", ev("ENTRY", 65, otype="MARKET", px=2601.0, sl=2605.0, tp=2595.0, info="CURRENT")),
    ]


def write(dirpath):
    with open(os.path.join(dirpath, "normal_flow.jsonl"), "w", encoding="utf-8") as f:
        for m in normal_flow():
            f.write(json.dumps(m, ensure_ascii=False, separators=(",", ":")) + "\n")
    with open(os.path.join(dirpath, "bad_cases.jsonl"), "w", encoding="utf-8") as f:
        for _, m in bad_cases():
            f.write((m if isinstance(m, str) else json.dumps(m, ensure_ascii=False, separators=(",", ":"))) + "\n")


if __name__ == "__main__":
    write(os.path.dirname(os.path.abspath(__file__)))
    print("written normal_flow.jsonl / bad_cases.jsonl")
