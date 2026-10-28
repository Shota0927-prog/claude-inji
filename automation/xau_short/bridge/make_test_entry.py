#!/usr/bin/env python3
"""XAU Short stage 3 — put ONE synthetic SHORT MARKET SATS_NOW ENTRY into the TEST receiver folder of a bridge config, so the
bridge -> EA path can be checked in DRY_RUN without TradingView. It refuses any receiver folder whose name does not contain
"test" (the real receiver data is never written by this script).

  python make_test_entry.py --config bridge_config.json --px 2650.00 [--sl-width 5.0] [--tp-width 7.5]

It waits for the next 5-minute bar close (UTC, at most 5 minutes) and records the ENTRY 1 s after it, like a real alert, so the
60 s deadline of the bridge and the EA starts from a real bar close. --px should be close to the XS Bid at that moment, otherwise
the EA skips it (price deviation > 20 % of the SL width) — that skip is also a valid check. Standard library only.
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
RECEIVER_DIR = os.path.join(os.path.dirname(HERE), "receiver")
BAR_MS = 300000


def main(argv=None):
    ap = argparse.ArgumentParser(description="one synthetic ENTRY into the TEST receiver folder (never the real one)")
    ap.add_argument("--config", required=True)
    ap.add_argument("--px", type=float, required=True)
    ap.add_argument("--sl-width", type=float, default=5.0)
    ap.add_argument("--tp-width", type=float, default=7.5)
    ap.add_argument("--no-wait", action="store_true", help="use the last bar close (only useful for expiry checks)")
    a = ap.parse_args(argv)
    sys.path.insert(0, HERE)
    sys.path.insert(0, RECEIVER_DIR)
    sys.path.insert(0, os.path.join(RECEIVER_DIR, "samples"))
    import ea_bridge as eb
    import xau_receiver as xr
    import make_samples as ms
    cfg = eb.load_config(a.config)
    rdir = cfg["receiver_data_dir"]
    if "test" not in os.path.basename(os.path.normpath(rdir)).lower():
        print(f"refused: receiver_data_dir {rdir} is not a TEST folder (its name must contain 'test')")
        return 2
    if not (a.px > 0 and a.sl_width > 0 and a.tp_width > 0):
        print("refused: px / widths must be positive")
        return 2
    now = int(time.time() * 1000)
    bc = (now // BAR_MS) * BAR_MS
    if not a.no_wait:
        bc += BAR_MS
        while int(time.time() * 1000) < bc + 1000:
            time.sleep(0.2)
    m = ms.ev("ENTRY", 0, otype="MARKET", px=round(a.px, 2), sl=round(a.px + a.sl_width, 2), tp=round(a.px - a.tp_width, 2),
              info="SATS_NOW", sent_delay=1000)
    tid = f"T{bc}"
    m.update(bar_open=bc - BAR_MS, bar_close=bc, sent=bc + 1000, tid=tid, key=f"{m['sid']}|ENTRY|{tid}|{bc}")
    rcfg = xr.load_config(None)
    rcfg["data_dir"] = rdir
    r = xr.Receiver(rcfg)
    res = r.process(json.dumps(m, separators=(",", ":")), source="make_test_entry")
    it = r.store.one("SELECT eligible, reason FROM intents WHERE key=?", (m["key"],))
    print(json.dumps({"status": res["status"], "key": m["key"], "bar_close_ms": bc, "eligible": it and it["eligible"],
                      "reason": it and it["reason"], "px": m["px"], "sl": m["sl"], "tp": m["tp"]}))
    r.store.db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
