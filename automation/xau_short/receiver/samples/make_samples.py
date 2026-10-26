#!/usr/bin/env python3
"""Builds the local sample notifications (normal_flow.jsonl / bad_cases.jsonl) with the same field order and key / tid rules as
f_auJson / f_auEmit of ZoneStrategyXAU_Auto.pine (AU-2, schema xau-auto/2). Times are UTC epoch ms of 5m bars inside the JST
09:00-02:00 session. Prices are illustrative (not market data). The cfg string is PREDICTED from cfg_fields.json (input defaults
formatted like the Pine copy: bool 1/0, int as is, float up to 10 decimals, strings as is, then JSON-escaped); confirm it
against the first real alert before pinning expected.cfg_sha256."""
import json
import os
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
FIELDS = json.load(open(os.path.join(HERE, "..", "..", "cfg_fields.json"), encoding="utf-8"))
SID = FIELDS["sid"]
SCHEMA = FIELDS["schema"]
RANK = {"PROV": 1, "WAIT_START": 5, "ENTRY": 10, "CANCEL": 20, "TV_FILL": 30, "TP_SET": 40, "BE_MOVE": 50, "CLOSE_REQ": 60,
        "TV_CLOSED": 70, "TV_FLAT": 90, "WAIT_END": 95, "BAR": 98}
JST = timezone(timedelta(hours=9))
T0 = int(datetime(2026, 10, 27, 10, 0, tzinfo=JST).timestamp() * 1000)     # bar 10:00-10:05 JST
BAR = 300000


def _fmt(f):
    v, ty = f["default"], f["type"]
    if ty == "bool":
        return "1" if v == "true" else "0"
    if ty == "int":
        return str(int(v))
    if ty == "float":
        s = f"{float(v):.10f}".rstrip("0").rstrip(".")
        return s if s not in ("", "-0") else "0"
    return v[1:-1].replace('\\"', '"').replace("\\\\", "\\") if v.startswith('"') else v


def predicted_cfg():
    by = {f["name"]: f for f in FIELDS["fields"]}
    raw = FIELDS["cfg_version"] + "|" + "|".join(_fmt(by[n]) for n in FIELDS["included_order"])
    return raw.replace("\\", "\\\\").replace('"', '\\"')


CFG = predicted_cfg()


def bar(i):
    return T0 + i * BAR


def ev(e, i, tid=None, side="SHORT", otype="", px=None, sl=None, tp=None, info="", sent_delay=1500, ohlc=None, **over):
    bo, bc = bar(i), bar(i) + BAR
    tid = tid or {"PROV": f"P{bo}", "WAIT_START": f"W{bc}", "BAR": f"B{bc}"}.get(e, f"T{bc}")
    base = px if px is not None else 2650.0
    o, h, l, c = ohlc or (base + 0.4, base + 1.2, base - 0.9, base)
    m = {"schema": SCHEMA, "sid": SID, "cfg": CFG, "ev": e, "key": f"{SID}|{e}|{tid}|{bc}", "tid": tid, "rank": RANK[e],
         "sym": "OANDA:XAUUSD", "tf": "5", "bar_open": bo, "bar_close": bc, "sent": bc + sent_delay if e != "PROV" else bo + 120000,
         "side": side, "otype": otype, "px": px, "sl": sl, "tp": tp, "o": o, "h": h, "l": l, "c": c, "info": info}
    m.update(over)
    if "sid" in over or "tid" in over:
        m["key"] = f"{m['sid']}|{e}|{m['tid']}|{bc}"
    return m


def normal_flow():
    w = f"W{bar(0) + BAR}"
    t = f"T{bar(3) + BAR}"
    return [
        ev("WAIT_START", 0, px=2650.25, sl=2656.75, tp=2640.5, info="sats_wait"),
        ev("BAR", 0, side="", px=2650.25, info="tv_state=0;tv_tid=;tv_be=0;tv_fill=null"),
        ev("PROV", 3, otype="MARKET", px=2652.1, sl=2656.75, tp=2640.5, info="SATS_PULL"),
        ev("ENTRY", 3, otype="MARKET", px=2651.8, sl=2656.75, tp=2640.5, info=f"SATS_PULL;wid={w}"),
        ev("BAR", 3, px=2651.8, sl=2656.75, info=f"tv_state=1;tv_tid={t};tv_be=0;tv_fill=null"),
        ev("TV_FILL", 4, tid=t, px=2651.9, sl=2656.75, info="virtual_fill"),
        ev("TP_SET", 4, tid=t, px=2651.9, sl=2656.75, tp=2640.5, info="sats_tp0"),
        ev("BAR", 4, px=2650.0, sl=2656.75, tp=2640.5, info=f"tv_state=2;tv_tid={t};tv_be=0;tv_fill=2651.9"),
        ev("BE_MOVE", 9, tid=t, px=2651.9, sl=2651.9, tp=2640.5, info="breakeven_tv_fill_based", ohlc=(2640.0, 2641.0, 2636.0, 2637.5)),
        ev("TV_FLAT", 15, tid=t, px=2651.9, sl=2651.9, tp=2640.5, info="virtual_position_closed"),
    ]


def bad_cases():
    """(name, message): a dict or a raw string (non-standard JSON cannot come from json.dumps)."""
    flow = normal_flow()
    t = flow[3]["tid"]
    late_w = f"W{bar(30) + BAR}"
    e40 = ev("ENTRY", 40, otype="MARKET", px=2600.0, sl=2605.0, tp=2592.5, info="CURRENT")
    inf = json.dumps(ev("ENTRY", 42, otype="MARKET", px=2600.0, sl=2605.0, tp=2592.5, info="CURRENT"), separators=(",", ":"))
    inf = inf.replace('"sl":2605.0', '"sl":Infinity')
    huge = json.dumps(ev("ENTRY", 43, otype="MARKET", px=2600.0, sl=2605.0, tp=2592.5, info="CURRENT"), separators=(",", ":"))
    huge = huge.replace(f'"bar_close":{bar(43) + BAR}', '"bar_close":' + str(10 ** 40))
    return [
        ("not_json", "this is not json"),
        ("missing_field", {k: v for k, v in e40.items() if k != "sl"}),
        ("sl_infinity", inf),
        ("bar_close_10e40", huge),
        ("negative_price", ev("ENTRY", 44, otype="MARKET", px=-2600.0, sl=-2595.0, tp=-2607.5, info="CURRENT")),
        ("duplicate_resend", flow[3]),
        ("late_manage_after_close", ev("BE_MOVE", 12, tid=t, px=2651.9, sl=2651.8, tp=2640.5, info="breakeven_tv_fill_based")),
        ("long_side_be_on_short", ev("BE_MOVE", 13, tid=t, side="LONG", px=2651.9, sl=-999.0, tp=2640.5, info="breakeven_tv_fill_based")),
        ("unknown_trade_manage", ev("TP_SET", 50, tid=f"T{bar(49) + BAR}", px=2600.0, sl=2605.0, tp=2592.5, info="sats_tp0")),
        ("wait_start", ev("WAIT_START", 30, px=2620.0, sl=2626.0, tp=2611.0, info="sats_wait")),
        ("wait_end", ev("WAIT_END", 40, tid=late_w, px=2620.0, sl=2626.0, tp=2611.0, info="expired")),
        ("late_entry_for_ended_wait", ev("ENTRY", 41, otype="MARKET", px=2619.0, sl=2626.0, tp=2611.0, info=f"SATS_PULL;wid={late_w}")),
        ("wrong_side", ev("ENTRY", 60, side="LONG", otype="MARKET", px=2600.0, sl=2595.0, tp=2607.5, info="CURRENT")),
        ("bad_geometry", ev("ENTRY", 61, otype="MARKET", px=2600.0, sl=2595.0, tp=2607.5, info="CURRENT")),
        ("sid_mismatch", ev("ENTRY", 62, otype="MARKET", px=2600.0, sl=2605.0, tp=2592.5, info="CURRENT", sid="XAU-SHORT|XA-22|AU-0")),
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
    write(HERE)
    print("written normal_flow.jsonl / bad_cases.jsonl")
