"""ST-2 fixtures — ZoneStrategyXAU.pine: A / B / C rebound entries, Zone-based SL, fill-price TP.

  TS : static — deterministic build (ST-1 text + ST-2 block), exact inverse, strategy() / Engine / requests / ZONE-P
       computation untouched, single zone loop, orders only on confirmed 5M bars, defaults (Buffer 3, RR 1.5, qty 1,
       Bar Magnifier not enabled), key expressions pinned to the mirror below
  TO : order model — line-by-line Python mirror of the ST-2 block driven by a minimal broker emulator
       (documented OHLC path assumption, NOT TradingView): timing, candidates, cancel conditions, TP, gaps, duplicates
  TU : mutation power — each mirror mutation must be caught by at least one TO fixture

Evidence class: PINE_NOT_VERIFIED. Broker behaviour (exit before fill, stop on the wrong side, close vs stop,
gap fills) is an emulator assumption here and must be confirmed on TradingView.
"""
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import st1_build as tb      # noqa: E402
import st2_build as s2      # noqa: E402
import st3_build as s3      # noqa: E402
import fvg_re10045_sim as fr  # noqa: E402

ROOT = tb.ROOT
ST = s3.strip_st3(__import__("xa_build").pre_xa("ZoneStrategyXAU.pine", open(os.path.join(ROOT, s2.ST_PATH), encoding="utf-8").read()))  # XA-1 Gold defaults stripped -> f253890 text (delta pinned by xa_sim)
RESULTS = []
SUP, RES, ACT, BRK = 1, 2, 0, 3


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


def code_only(src):
    return "\n".join(l for l in src.split("\n") if not l.lstrip().startswith("//"))


# =============================================================================
# TS : static
# =============================================================================
PINS = [
    "array<StCand> src = stModeA ? cur : stPrev",
    "if zSide != 0 and (z.strength >= SR_STRONG or (eBoost and eStr >= SR_STRONG))",
    "pendOK := zSide == oSide and z.bottom <= oL and oL <= z.top and (z.strength >= SR_STRONG or "
    "(eBoost and eStr >= SR_STRONG and eBBot <= oL and oL <= eBTop))",
    "if oState == 1 and not pendOK",
    "if oState == 0 and not cancelBar",
    "px := c.side == 1 ? (c.sZ >= SR_STRONG ? c.top : c.bTop) : (c.sZ >= SR_STRONG ? c.bot : c.bBot)",
    "ok  := (c.side == 1 ? close > c.top : close < c.bot) and aS >= SR_STRONG",
    "[s2, sc2] = f_stAdopt(c, math.max(low, c.bot), math.min(high, c.top))",
    "ok := low <= c.top and high >= c.bot and (c.side == 1 ? close > c.top : close < c.bot) and aS >= SR_STRONG "
    "and trkOK and (not stModeC or (c.side == 1 ? stPatL : stPatS))",
    "bool inB = not na(c.bTop) and math.max(lo, c.bBot) <= math.min(hi, c.bTop)",
    "oSL     := side == 1 ? c.bot - stBuffer : c.top + stBuffer",
    "float risk   = oSide * (fillPx - oSL)",
    "if risk > 0",
    "oTP := fillPx + oSide * stRR * risk",
    "strategy.exit(oXid, oEid, stop = oSL, limit = oTP)",
    "strategy.close(oEid)",
    "strategy.exit(oXid, oEid, stop = oSL)",
    "if dirOK and not map.contains(stUsed, c.track)",
]
PINS2 = ["map.put(stUsed, oTrack, true)"]      # fill open / fill closed in the same bar


def gate_static():
    st1 = tb.build()
    check("TS-01 ZoneStrategyXAU.pine == st2_transform(st1_build.build()); strip_st2 is the exact inverse",
          s2.build() == ST and s2.strip_st2(ST) == st1 and s2.st2_transform(s2.strip_st2(ST)) == ST)
    d1 = ST[ST.index("strategy(\n"):ST.index(")\n", ST.index("strategy(\n")) + 2]
    d0 = st1[st1.index("strategy(\n"):st1.index(")\n", st1.index("strategy(\n")) + 2]
    check("TS-02 strategy() unchanged from ST-1 (calc_on_every_tick / process_orders_on_close false, pyramiding 0, "
          "fixed qty 1); Bar Magnifier / calc_on_order_fills not enabled",
          d1 == d0 and "default_qty_value      = 1)" in d1 and "pyramiding             = 0" in d1
          and "use_bar_magnifier" not in ST and "calc_on_order_fills" not in ST)
    pre1 = st1[:st1.index(s2.LOOP_OLD)]
    pre2 = ST[:ST.index(s2.LOOP_NEW)]
    check("TS-03 everything before the evaluation loop (ZONE-P computation, Engine /6 import, FVG Batch A, Batch C "
          "copies, f_stZoneEval) identical to ST-1 except the header line",
          pre2 == pre1.replace(s2.HDR_OLD, s2.HDR_NEW) and ST.endswith(st1[st1.index(s2.LOOP_OLD) + len(s2.LOOP_OLD):]))
    co = code_only(ST)
    req = lambda s: re.findall(r"request\.\w+\(", code_only(s))
    check("TS-04 request.* call sites unchanged (10); single import ZoneEnginePractical/6",
          len(req(ST)) == len(req(st1)) == 10
          and re.findall(r"^import .*$", ST, re.M) == ["import sekine3310/ZoneEnginePractical/6 as zn"])
    blk = code_only(s2.LOOP_NEW)
    check("TS-05 one zone loop per confirmed bar: zn.zoneAt / f_stZoneEval each called once (FVG scans unchanged: "
          "2 per zone), no other Engine calls",
          co.count("zn.zoneAt(") == 1 and co.count("= f_stZoneEval(z)") == 1 and co.count("zn.zoneCount(") == 1
          and not re.search(r"\bzn\.(update|\w+Pack)\b", blk))
    lines = s2.LOOP_NEW.split("\n")
    gi = lines.index("if is5mChart and barstate.isconfirmed")
    gend = next(i for i in range(gi + 1, len(lines)) if lines[i] and not lines[i].startswith(" "))
    orders = [i for i, l in enumerate(lines) if re.search(r"strategy\.(entry|exit|close|cancel|order)\(", l)]
    check("TS-06 every order call is inside the confirmed-5M block; no strategy.order / close_all; plots only to "
          "the data window; no drawing",
          orders and all(gi < i < gend for i in orders) and "strategy.order(" not in co and "close_all" not in co
          and all("display = display.data_window" in l for l in re.findall(r"^plot\(.*$", co, re.M))
          and not re.search(r"\b(box|label|line|table)\.(new|set_\w+|delete)\b", co), str(orders))
    check("TS-07 RE10045 lint clean (no eager index guard); no request / security in the ST-2 block; candidate list and "
          "order state are the only new var state",
          fr.lint_eager_guards(blk) == [] and "request." not in blk
          and re.findall(r"^var (?:map<[^>]*>|\S+)\s+(\w+)", blk, re.M) == ["G_ST", "stPrev", "stUsed", "oState", "oSeq", "oEid", "oXid",
                                                              "oLimit", "oSide", "oTrack", "oL", "oSL", "oTP", "oClosed"])
    ins = dict(re.findall(r"^(st\w+) = (input\.\w+\(.*)$", s2.LOOP_NEW, re.M))
    check("TS-08 inputs: Entry Mode (A / B / C, one executed), Direction (Long / Short / Both), Buffer 3.0, RR 1.5, "
          "Pin Bar ratio; no expiry / replacement inputs",
          sorted(ins) == ["stBuffer", "stDir", "stMode", "stPinRatio", "stRR"]
          and ins["stBuffer"].startswith("input.float(3.0,") and ins["stRR"].startswith("input.float(1.5,")
          and not re.search(r"(?i)expir|replace|r1", " ".join(ins)), str(ins))
    miss = [p for p in PINS if blk.count(p) != 1] + [p for p in PINS2 if blk.count(p) != 2]
    check("TS-09 key expressions present exactly once (mirrored line by line in TO): candidate save, A limit price, "
          "pending validity, cancel bar, B / C touch band + close + Track, SL, TP from the fill price, risk <= 0 close, "
          "Track used once", miss == [], str(miss))
    check("TS-10 TP is only sent from the fill-confirmation branch (exit with limit appears once, inside risk > 0); "
          "the entry-time exit carries the stop only",
          blk.count("limit = oTP") == 1 and blk.index("if risk > 0") < blk.index("limit = oTP") < blk.index("strategy.close(oEid)")
          and blk.count("strategy.exit(") == 2)
    names = ["ZoneVisualPractical.pine", "ZoneEnginePractical.pine", "ZoneEnginePracticalRN.pine",
             "ZoneEnginePracticalSwingMax.pine", "PracticalZoneStrategy_LONG.pine", "PracticalZoneStrategy_SHORT.pine",
             "SignalEnginePractical.pine"]
    d = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", "f1d54bf", "--"] + names, capture_output=True, text=True).stdout
    check("TS-11 ZONE-P, Engines (/2, /5, /6), Strategy LONG / SHORT, SignalEngine unchanged vs f1d54bf", __import__("xa_build").drop_xa(d.split(), "f1d54bf") == [], d)


# =============================================================================
# Broker emulator (assumption, not TradingView)
#   path: O -> H -> L -> C if |O-H| < |O-L| else O -> L -> H -> C
#   market entry / strategy.close: next bar open. limit / stop marketable at activation: current price.
#   strategy.exit for an unfilled entry waits for the fill and is active from the fill point (same bar).
#   flags: stop_wrong_side_fires (default True) — a stop already beyond at activation fills at once;
#          False = it does not fire in the fill bar at all (alternative to compare; TradingView decides).
# =============================================================================
def hit_at_fill(tr, stop):
    """the stop is already beyond at the fill price (wrong side)."""
    return tr["price"] <= stop if tr["side"] == 1 else tr["price"] >= stop


class Broker:
    def __init__(self, stop_wrong_side_fires=True):
        self.entries, self.exits, self.closes = {}, {}, []
        self.open, self.closed, self.fills = [], [], []
        self.swf = stop_wrong_side_fires

    def entry(self, i, side, limit=None):
        self.entries[i] = dict(side=side, limit=limit)

    def exit(self, x, frm, stop, limit=None):
        self.exits[x] = dict(frm=frm, stop=stop, limit=limit)

    def cancel(self, i):
        self.entries.pop(i, None)
        self.exits.pop(i, None)

    def close(self, i):
        self.closes.append(i)

    def _close_trade(self, tr, px, t, why):
        self.open.remove(tr)
        self.closed.append(dict(tr, exit=px, exit_bar=t, why=why))
        for x in [x for x, e in self.exits.items() if e["frm"] == tr["id"]]:
            del self.exits[x]

    def _fill_entry(self, i, px, t):
        e = self.entries.pop(i)
        tr = dict(id=i, side=e["side"], price=px, bar=t)
        self.open.append(tr)
        self.fills.append(tr)
        return tr

    def process(self, t, bar):
        o, h, l, c = bar
        for i in self.closes:
            for tr in [tr for tr in self.open if tr["id"] == i]:
                self._close_trade(tr, o, t, "close")
        self.closes = []
        for i in [i for i, e in self.entries.items() if e["limit"] is None]:
            self._fill_entry(i, o, t)
        pts = [o, h, l, c] if abs(o - h) < abs(o - l) else [o, l, h, c]
        fresh = set(tr["id"] for tr in self.open if tr["bar"] == t)
        for k in range(3):
            p0, p1 = pts[k], pts[k + 1]
            while True:
                ev = []
                for tr in list(self.open):
                    for x, e in self.exits.items():
                        if e["frm"] != tr["id"]:
                            continue
                        s = tr["side"]
                        for kind, lv in (("stop", e["stop"]), ("tp", e["limit"])):
                            if lv is None:
                                continue
                            if kind == "stop" and not self.swf and tr["id"] in fresh and hit_at_fill(tr, lv):
                                continue
                            hit = (lambda p: p <= lv) if (s == 1) == (kind == "stop") else (lambda p: p >= lv)
                            if hit(p0):
                                ev.append((0.0, 0 if kind == "stop" else 1, p0, ("x", tr, kind)))
                            elif hit(p1):
                                ev.append((abs(lv - p0), 0 if kind == "stop" else 1, lv, ("x", tr, kind)))
                for i, e in self.entries.items():
                    lv, s = e["limit"], e["side"]
                    if lv is None or any(True for _ in self.open):
                        continue
                    hit = (lambda p: p <= lv) if s == 1 else (lambda p: p >= lv)
                    if hit(p0):
                        ev.append((0.0, 2, p0, ("e", i)))
                    elif hit(p1):
                        ev.append((abs(lv - p0), 2, lv, ("e", i)))
                if not ev:
                    break
                ev.sort(key=lambda x: (x[0], x[1]))
                _, _, px, what = ev[0]
                if what[0] == "x":
                    self._close_trade(what[1], px, t, what[2])
                else:
                    self._fill_entry(what[1], px, t)
                    fresh.add(what[1])
                p0 = px


# =============================================================================
# Mirror of the ST-2 block (line by line). mut = set of mutation names (TU).
# zone dict: track, state, top, bot, sZ, score, boosted, sB, dScore, bTop, bBot
# =============================================================================
def Z(track, state, top, bot, sZ=3, score=8.0, boosted=False, sB=None, dScore=None, bTop=None, bBot=None):
    return dict(track=track, state=state, top=top, bot=bot, sZ=sZ, score=score, boosted=boosted,
                sB=sZ if sB is None else sB, dScore=score if dScore is None else dScore,
                bTop=bTop if boosted else None, bBot=bBot if boosted else None)


class Script:
    def __init__(self, mode="B", dir="Both", buffer=3.0, rr=1.5, pin=2.0, mut=()):
        self.mode, self.buffer, self.rr, self.pin, self.mut = mode, buffer, rr, pin, set(mut)
        self.longOK, self.shortOK = dir != "Short", dir != "Long"
        self.prev, self.used = [], set()
        self.oState, self.oSeq, self.oEid, self.oXid = 0, 0, "", ""
        self.oLimit, self.oSide, self.oTrack, self.oL, self.oSL, self.oTP, self.oClosed = False, 0, -1, None, None, None, 0
        self.log = []

    def adopt(self, c, lo, hi):
        if "band_open" in self.mut:
            inB = c["bTop"] is not None and max(lo, c["bBot"]) < min(hi, c["bTop"])
        else:
            inB = c["bTop"] is not None and max(lo, c["bBot"]) <= min(hi, c["bTop"])
        return (c["sB"], c["dScore"]) if inB else (c["sZ"], c["score"])

    @staticmethod
    def better(distFirst, a, b):
        aS, aSc, aD, aT = a
        bS, bSc, bD, bT = b
        if distFirst and aD != bD:
            return aD < bD
        if aS != bS:
            return aS > bS
        if aSc != bSc:
            return aSc > bSc
        if aD != bD:
            return aD < bD
        return aT < bT

    def pat(self, side, bar, prev):
        o, h, l, c = bar
        po, ph, pl, pc = prev
        body, wl, wh = abs(c - o), min(o, c) - l, h - max(o, c)
        if side == 1:
            return (c > o and pc < po and o <= pc and c >= po) or (wl > 0 and wl >= self.pin * body and wl > wh)
        return (c < o and pc > po and o >= pc and c <= po) or (wh > 0 and wh >= self.pin * body and wh > wl)

    def step(self, t, bar, prev, zones, B):
        o, h, l, c = bar
        modeA, modeC = self.mode == "A", self.mode == "C"
        ev = dict(t=t)
        # (1)
        if self.oState == 1:
            filledOpen = len(B.open) > 0 and B.open[-1]["id"] == self.oEid
            filledClosed = (not filledOpen) and len(B.closed) > self.oClosed and B.closed[-1]["id"] == self.oEid
            if filledOpen:
                self.used.add(self.oTrack)
                fillPx = B.open[-1]["price"]
                if "tp_from_L" in self.mut and self.oLimit:
                    fillPx = self.oL
                risk = self.oSide * (fillPx - self.oSL)
                if risk > 0 or ("risk_ge0" in self.mut and risk == 0):
                    self.oTP = fillPx + self.oSide * self.rr * risk
                    B.exit(self.oXid, self.oEid, stop=self.oSL, limit=self.oTP)
                    ev["tp"] = self.oTP
                else:
                    B.close(self.oEid)
                    ev["close"] = True
                self.oState = 2
            elif filledClosed:
                self.used.add(self.oTrack)
                self.oState = 0
                ev["same_bar_exit"] = True
            elif not self.oLimit:
                B.cancel(self.oEid)
                B.cancel(self.oXid)
                self.oState = 0
        elif self.oState == 2 and len(B.open) == 0:
            self.oState = 0
        # (2)
        cur, curTrk, pendOK = [], [], False
        for z in zones:
            curTrk.append((z["track"], z["state"]))
            zSide = 1 if z["state"] == SUP else -1 if z["state"] == RES else 0
            strong = z["sZ"] >= 3 or (z["boosted"] and z["sB"] >= 3 and "cand_no_boost" not in self.mut)
            if zSide != 0 and strong:
                cur.append(dict(side=zSide, track=z["track"], top=z["top"], bot=z["bot"], bTop=z["bTop"], bBot=z["bBot"],
                                sZ=z["sZ"], sB=z["sB"], score=z["score"], dScore=z["dScore"]))
            if self.oState == 1 and z["track"] == self.oTrack:
                inB = z["boosted"] and z["sB"] >= 3 and z["bBot"] <= self.oL <= z["bTop"]
                strOK = True if "pend_nostr" in self.mut else (z["sZ"] >= 3 or inB)
                inZ = True if "pend_noinz" in self.mut else z["bot"] <= self.oL <= z["top"]
                pendOK = zSide == self.oSide and inZ and strOK
        if "pend_notrack" in self.mut and self.oState == 1 and self.oTrack not in [t_ for t_, _ in curTrk]:
            pendOK = True
        # (3)
        cancelBar = False
        if self.oState == 1 and not pendOK:
            B.cancel(self.oEid)
            B.cancel(self.oXid)
            self.oState, cancelBar = 0, True
            ev["cancel"] = self.oEid
        if "no_cancelbar" in self.mut:
            cancelBar = False
        # (4)
        if self.oState == 0 and not cancelBar:
            src = cur if (modeA or "bc_cur" in self.mut) else self.prev
            best = {1: None, -1: None}
            for k, cd in enumerate(src):
                dirOK = self.longOK if cd["side"] == 1 else self.shortOK
                if not dirOK or (cd["track"] in self.used and "no_used" not in self.mut):
                    continue
                px = None
                if modeA:
                    if "a_top_only" in self.mut:
                        px = cd["top"] if cd["side"] == 1 else cd["bot"]
                    else:
                        px = (cd["top"] if cd["sZ"] >= 3 else cd["bTop"]) if cd["side"] == 1 else (cd["bot"] if cd["sZ"] >= 3 else cd["bBot"])
                    aS, aSc = self.adopt(cd, px, px)
                    d = abs(c - px)
                    ok = (c > cd["top"] if cd["side"] == 1 else c < cd["bot"]) and aS >= 3
                else:
                    aS, aSc = self.adopt(cd, max(l, cd["bot"]), min(h, cd["top"]))
                    d = abs(c - (cd["top"] if cd["side"] == 1 else cd["bot"]))
                    st = dict(curTrk).get(cd["track"])
                    trkOK = True if "no_trk_check" in self.mut else st == (SUP if cd["side"] == 1 else RES)
                    closeOK = True if (modeC and "c_noclose" in self.mut) else (c > cd["top"] if cd["side"] == 1 else c < cd["bot"])
                    ok = l <= cd["top"] and h >= cd["bot"] and closeOK and aS >= 3 and trkOK \
                        and (not modeC or self.pat(cd["side"], bar, prev))
                if ok:
                    key = (aS, aSc, d, cd["track"])
                    b = best[cd["side"]]
                    if b is None or self.better(modeA, key, b[1]):
                        best[cd["side"]] = (k, key, px)
            side = 0
            if best[1] and best[-1]:
                if modeA and best[1][1][2] != best[-1][1][2]:
                    side = 1 if best[1][1][2] < best[-1][1][2] else -1
            elif best[1]:
                side = 1
            elif best[-1]:
                side = -1
            if side != 0:
                cd = src[best[side][0]]
                self.oSeq += 1
                self.oEid = ("L" if side == 1 else "S") + str(self.oSeq)
                self.oXid = self.oEid + " SL/TP"
                self.oSide, self.oTrack, self.oLimit = side, cd["track"], modeA
                self.oL = best[side][2] if modeA else None
                if "sl_wrong" in self.mut:
                    self.oSL = cd["top"] - self.buffer if side == 1 else cd["bot"] + self.buffer
                else:
                    self.oSL = cd["bot"] - self.buffer if side == 1 else cd["top"] + self.buffer
                self.oTP, self.oClosed, self.oState = None, len(B.closed), 1
                B.entry(self.oEid, side, limit=self.oL if modeA else None)
                if "tp_in_entry" in self.mut and modeA:
                    B.exit(self.oXid, self.oEid, stop=self.oSL, limit=self.oL + side * self.rr * abs(self.oL - self.oSL))
                else:
                    B.exit(self.oXid, self.oEid, stop=self.oSL)
                ev["order"] = dict(id=self.oEid, side=side, track=cd["track"], L=self.oL, SL=self.oSL)
        self.prev = cur
        self.log.append(ev)


def run(bars, zones, broker=None, **kw):
    """bars[t] = (o, h, l, c); zones[t] = zone list after zn.update(t). Bar 0 is warm-up for the previous bar."""
    S, B = Script(**kw), broker or Broker()
    for t in range(len(bars)):
        if t > 0:
            B.process(t, bars[t])
        S.step(t, bars[t], bars[t - 1] if t > 0 else bars[t], zones[t], B)
    return S, B


def orders(S):
    return [(e["t"], e["order"]) for e in S.log if "order" in e]


# =============================================================================
# TO : order-model fixtures
# =============================================================================
ZL = Z(1, SUP, 100.0, 94.0)                                                  # Long, Strong, SL 91
ZLb = Z(1, SUP, 100.0, 94.0, sZ=2, score=5.0, boosted=True, sB=3, dScore=7.0, bTop=97.0, bBot=94.0)   # Medium, FVG part Strong
FLAT = (105.0, 106.0, 104.0, 105.0)


def fixtures(mut=()):
    R = []

    def ok(name, cond, detail=""):
        R.append((name, bool(cond), detail))

    m = dict(mut=mut)
    # --- B timing / fill / TP -------------------------------------------------------------------------------------
    bars = [FLAT, (103.0, 103.5, 99.0, 101.0), (101.5, 118.0, 101.0, 102.0), (102.0, 118.0, 101.9, 110.0)]
    S, B = run(bars, [[ZL]] * 4, mode="B", **m)
    o = orders(S)
    ok("TO-01 B: touch + close > top on t with the t-1 candidate -> market at t+1 open, SL = bottom - 3 sent with the "
       "entry, TP first sent at the fill-bar close from the fill price (1.5R), no TP inside the fill bar (high 118 >= "
       "TP 117.25 there), TP fills on the next bar",
       o == [(1, dict(id="L1", side=1, track=1, L=None, SL=91.0))] and B.fills[0]["price"] == 101.5 and B.fills[0]["bar"] == 2
       and S.log[2].get("tp") == 117.25 and B.closed and B.closed[0]["exit_bar"] == 3 and B.closed[0]["exit"] == 117.25,
       str((o, B.fills, B.closed, S.log[2])))
    S, B = run(bars[:2], [[], [ZL]], mode="B", **m)
    ok("TO-02 B: a zone that only exists after zn.update(t) is not used on t (candidates are from t-1)", orders(S) == [])
    S1, _ = run(bars[:2], [[ZL], []], mode="B", **m)
    S2, _ = run(bars[:2], [[ZL], [dict(ZL, state=BRK)]], mode="B", **m)
    S3, _ = run(bars[:2], [[ZL], [dict(ZL, state=ACT)]], mode="B", **m)
    ok("TO-03 B: Track lost / BROKEN / other State after zn.update(t) -> no entry", orders(S1) == orders(S2) == orders(S3) == [])
    S1, _ = run([FLAT, (103.0, 103.5, 99.0, 99.5)], [[ZL]] * 2, mode="B", **m)
    ok("TO-04 B: close inside the zone -> no entry", orders(S1) == [])
    S1, _ = run([FLAT, (103.0, 103.5, 97.0, 101.0)], [[ZLb]] * 2, mode="B", **m)
    S2, _ = run([FLAT, (103.0, 103.5, 97.01, 101.0)], [[ZLb]] * 2, mode="B", **m)
    ok("TO-05 Medium zone with FVG-only Strong range [94, 97]: touch band [97, 100] (one-point contact) qualifies, "
       "[97.01, 100] does not; SL = original bottom - 3",
       [x[1]["SL"] for x in orders(S1)] == [91.0] and orders(S2) == [], str((orders(S1), orders(S2))))
    # --- C ---------------------------------------------------------------------------------------------------------
    pin = (101.0, 101.6, 96.0, 101.5)
    pin_in = (99.5, 99.9, 96.0, 99.8)
    plain = (100.2, 103.0, 99.9, 102.8)
    eng0, eng1 = (102.0, 102.5, 100.5, 101.0), (100.8, 103.5, 99.5, 103.0)
    Sp, _ = run([FLAT, pin], [[ZL]] * 2, mode="C", **m)
    Si, _ = run([FLAT, pin_in], [[ZL]] * 2, mode="C", **m)
    Sn, _ = run([FLAT, plain], [[ZL]] * 2, mode="C", **m)
    Sb, _ = run([FLAT, plain], [[ZL]] * 2, mode="B", **m)
    Se, _ = run([eng0, eng1], [[ZL]] * 2, mode="C", **m)
    ok("TO-06 C: pin bar + close > top -> entry; pin bar closing inside the zone -> none (close beyond the zone is "
       "required); no pattern -> none in C while B enters; bullish engulfing -> entry",
       len(orders(Sp)) == 1 and orders(Si) == [] and orders(Sn) == [] and len(orders(Sb)) == 1 and len(orders(Se)) == 1,
       str([orders(x) for x in (Sp, Si, Sn, Sb, Se)]))
    # --- A placement / fill / TP -------------------------------------------------------------------------------------
    S1, B1 = run([FLAT], [[ZL]], mode="A", **m)
    S2, B2 = run([FLAT], [[ZLb]], mode="A", **m)
    S3, _ = run([(99.0, 99.5, 98.0, 99.0)], [[ZL]], mode="A", **m)
    ok("TO-07 A: limit on the t list with close beyond the zone: Strong zone -> L = top 100; FVG-only Strong -> L = bTop "
       "97; SL = original bottom - 3 = 91 in both, sent with the entry (stop only); close inside the zone -> no order",
       [x[1]["L"] for x in orders(S1)] == [100.0] and [x[1]["L"] for x in orders(S2)] == [97.0]
       and B1.exits["L1 SL/TP"] == dict(frm="L1", stop=91.0, limit=None) and B2.exits["L1 SL/TP"]["stop"] == 91.0
       and orders(S3) == [], str((orders(S1), orders(S2), B1.exits)))
    S, B = run([FLAT, (101.0, 114.0, 99.5, 105.0), (105.0, 114.0, 104.9, 106.0)], [[ZL], [dict(ZL, bot=93.0)], [ZL]], mode="A", **m)
    ok("TO-08 A: fill at L intrabar, no TP inside the fill bar (high 114 >= 113.5 after the fill), TP = 100 + 1.5 x 9 "
       "sent at the fill-bar close, SL stays 91 when the zone bottom moves, TP fills next bar",
       B.fills and B.fills[0]["price"] == 100.0 and B.fills[0]["bar"] == 1 and S.log[1].get("tp") == 113.5
       and B.closed and B.closed[0]["exit_bar"] == 2 and B.closed[0]["exit"] == 113.5, str((B.fills, B.closed, S.log)))
    S, B = run([FLAT, (99.0, 104.0, 98.5, 103.0)], [[ZL], [ZL]], mode="A", **m)
    ok("TO-09 gap: A limit opened through (open 99 < L 100) fills at the open 99 and TP uses the actual fill "
       "(99 + 1.5 x 8 = 111)", B.fills and B.fills[0]["price"] == 99.0 and S.log[1].get("tp") == 111.0, str((B.fills, S.log[1])))
    # --- A pending cancel (each condition separately) ---------------------------------------------------------------
    nb = (104.0, 104.5, 101.0, 104.0)                       # never reaches L (100 / 97)
    cross = (103.0, 103.5, 95.0, 96.0)                       # would cross L (100 / 97) on the next bar
    cases = [
        ("FVG expired (no boost)", ZLb, dict(ZLb, boosted=False, sB=2, bTop=None, bBot=None), True),
        ("boost range moved (bTop 96.5 < L 97)", ZLb, dict(ZLb, bTop=96.5), True),
        ("boost range moved, L still inside (bTop 98)", ZLb, dict(ZLb, bTop=98.0), False),
        ("original Strength lowered (Medium, no boost)", ZL, dict(ZL, sZ=2), True),
        ("original lowered but L inside a Strong boost range", ZL, Z(1, SUP, 100.0, 94.0, sZ=2, boosted=True, sB=3, bTop=100.0, bBot=96.0), False),
        ("Track lost", ZL, None, True),
        ("State BROKEN", ZL, dict(ZL, state=BRK), True),
        ("L outside the zone (top 99.5)", ZL, dict(ZL, top=99.5), True),
    ]
    bad = []
    for name, z0, z1, cancel in cases:
        S, B = run([FLAT, nb, cross], [[z0], [z1] if z1 else [], [z1] if z1 else []], mode="A", **m)
        got = "cancel" in S.log[1]
        later = bool(B.fills)
        if got != cancel or (cancel and (later or B.exits)) or (not cancel and not later):
            bad.append((name, got, later, B.exits))
    ok("TO-10 A pending, checked on each confirmed bar after the update: cancelled exactly when the Track is lost, the "
       "State is invalid, L leaves the zone, or L loses Strong (FVG expired / boost range moved / original lowered); "
       "kept when L stays Strong; a cancelled order and its stop never fill later", bad == [], str(bad))
    S, B = run([FLAT, (103.0, 103.5, 92.0, 93.5), FLAT], [[ZL], [dict(ZL, state=BRK)], []], mode="A", **m)
    ok("TO-11 filled before the cancel: L crossed inside the bar whose close breaks the zone -> recorded as a fill, no "
       "cancel, Track used, TP from the fill (the stop stays)",
       "cancel" not in S.log[1] and B.fills and 1 in S.used and S.log[1].get("tp") == 113.5 and S.oState == 2,
       str((S.log, B.fills, S.used)))
    Z2 = Z(2, SUP, 98.0, 95.0)
    S, B = run([FLAT, nb, nb], [[ZL], [Z2], [Z2]], mode="A", **m)
    ok("TO-12 no new order on the cancel bar (another valid zone exists); placed on the next bar",
       [(t, x["track"]) for t, x in orders(S)] == [(0, 1), (2, 2)], str(orders(S)))
    S, B = run([FLAT, nb, (104.0, 104.5, 101.5, 104.2)], [[ZL], [ZL, Z(3, SUP, 102.0, 101.0, sZ=4)], [ZL, Z(3, SUP, 102.0, 101.0, sZ=4)]], mode="A", **m)
    ok("TO-13 R0: no replacement while the pending limit stays valid (a nearer / stronger zone appears)",
       [(t, x["track"]) for t, x in orders(S)] == [(0, 1)], str(orders(S)))
    # --- same-bar Entry / SL, wrong side, TP already crossed ----------------------------------------------------------
    S, B = run([FLAT, (104.0, 104.2, 90.0, 95.0), FLAT], [[ZL], [ZL], [ZL]], mode="A", **m)
    ok("TO-14 same bar Entry + SL: filled at 100 and stopped at 91 in the fill bar -> detected via closedtrades, no TP, "
       "Track used once (no new order on track 1 later)",
       B.closed and B.closed[0]["bar"] == B.closed[0]["exit_bar"] == 1 and B.closed[0]["exit"] == 91.0
       and S.log[1].get("same_bar_exit") and "tp" not in S.log[1] and orders(S) == [(0, orders(S)[0][1])] and 1 in S.used,
       str((B.closed, S.log)))
    gapbar = (90.0, 92.0, 89.0, 91.5)
    S, B = run([FLAT, gapbar, FLAT], [[ZL]] * 3, mode="A", **m)
    S2, B2 = run([FLAT, gapbar, FLAT], [[ZL]] * 3, broker=Broker(stop_wrong_side_fires=False), mode="A", **m)
    S3, B3 = run([FLAT, (91.0, 92.0, 90.5, 91.5), FLAT], [[ZL]] * 3, broker=Broker(stop_wrong_side_fires=False), mode="A", **m)
    ok("TO-15 wrong side: limit filled at a gap open 90 below SL 91. Emulator A (stop fires at once): closed in the fill "
       "bar at 90, no TP. Emulator B (stop does not fire): risk <= 0 at the close -> no TP, strategy.close -> next open; "
       "fill exactly at SL (risk 0) is handled the same way",
       S3.log[1].get("close") and "tp" not in S3.log[1]
       and B.closed and B.closed[0]["exit"] == 90.0 and "tp" not in S.log[1]
       and S2.log[1].get("close") and "tp" not in S2.log[1] and B2.closed and B2.closed[0]["exit"] == 105.0
       and B2.closed[0]["why"] == "close", str((B.closed, S.log[1], B2.closed, S2.log[1])))
    S, B = run([FLAT, (103.0, 103.5, 99.0, 101.0), (101.5, 120.0, 101.4, 119.0), (119.5, 120.0, 119.0, 119.6)], [[ZL]] * 4, mode="B", **m)
    rr = (B.closed[0]["exit"] - 101.5) / 10.5 if B.closed else None
    ok("TO-16 TP already crossed when sent (fill-bar close 119 >= TP 117.25): TP formula unchanged, the limit fills at "
       "the next open 119.5, realized RR 1.71 != 1.5",
       S.log[2].get("tp") == 117.25 and B.closed and B.closed[0]["exit"] == 119.5 and rr is not None and rr > 1.5,
       str((S.log[2], B.closed)))
    S, B = run([FLAT, (101.0, 101.5, 88.0, 90.0)], [[ZL]] * 2, mode="B", **m)
    S, B = run([FLAT, (103.0, 103.5, 99.0, 101.0), (101.5, 102.0, 101.0, 101.8), (88.0, 89.0, 87.0, 88.5)], [[ZL]] * 4, mode="B", **m)
    ok("TO-17 SL gap: the bar opens at 88 through SL 91 -> stop fills at the open 88 (emulator), loss beyond 1R",
       B.closed and B.closed[0]["exit"] == 88.0 and B.closed[0]["why"] == "stop", str(B.closed))
    # --- duplicates / priority / direction ---------------------------------------------------------------------------
    bars = [FLAT, (103.0, 103.5, 99.0, 101.0), (101.5, 102.0, 99.0, 101.5), (101.5, 102.0, 99.0, 101.5)]
    S, B = run(bars, [[ZL, Z(2, SUP, 100.5, 96.0)]] * 4, mode="B", **m)
    ok("TO-18 one order at a time: while the position is open no new entry (another touched zone qualifies)",
       len(orders(S)) == 1 and len(B.fills) == 1, str(orders(S)))
    S, B = run([FLAT, nb, FLAT, FLAT], [[ZL], [dict(ZL, state=ACT)], [ZL], [ZL]], mode="A", **m)
    ok("TO-19 a Track only cancelled (never filled) is not marked used and can be ordered again",
       [(t, x["track"]) for t, x in orders(S)] == [(0, 1), (2, 1)] and S.used == set(), str(orders(S)))
    bar = (103.0, 103.5, 99.0, 101.0)
    S, _ = run([FLAT, bar], [[ZL, Z(2, SUP, 100.0, 95.0, sZ=4, score=12.0)]] * 2, mode="B", **m)
    S2, _ = run([FLAT, bar], [[ZL, Z(2, SUP, 100.0, 95.0, sZ=3, score=9.0)]] * 2, mode="B", **m)
    ok("TO-20 B priority: higher adopted Strength, then higher Score",
       [x["track"] for _, x in orders(S)] == [2] and [x["track"] for _, x in orders(S2)] == [2], str((orders(S), orders(S2))))
    ZS = Z(5, RES, 108.0, 102.0)
    bb = (101.0, 102.5, 99.5, 101.0)
    Sb, _ = run([FLAT, bb], [[ZL, ZS]] * 2, mode="B", **m)
    Sl, _ = run([FLAT, bb], [[ZL, ZS]] * 2, mode="B", dir="Long", **m)
    Ss, _ = run([FLAT, bb], [[ZL, ZS]] * 2, mode="B", dir="Short", **m)
    Sa, _ = run([(104.0, 104.5, 103.5, 104.0)], [[ZL, Z(2, SUP, 98.0, 95.0), Z(6, RES, 113.0, 109.0)]], mode="A", **m)
    ok("TO-21 Both: B with Long and Short on the same bar -> skip; Long Only / Short Only take their side (Short SL = "
       "top + 3); A takes the limit nearest to the close (100 vs 98 vs 109)",
       orders(Sb) == [] and [x["side"] for _, x in orders(Sl)] == [1] and [(x["side"], x["SL"]) for _, x in orders(Ss)] == [(-1, 111.0)]
       and [(x["track"], x["L"]) for _, x in orders(Sa)] == [(1, 100.0)], str((orders(Sb), orders(Sl), orders(Ss), orders(Sa))))
    return R


MUTS = ["bc_cur", "c_noclose", "a_top_only", "sl_wrong", "pend_nostr", "pend_noinz", "pend_notrack", "tp_from_L",
        "no_cancelbar", "no_used", "risk_ge0", "cand_no_boost", "tp_in_entry", "no_trk_check", "band_open"]


def gate_model():
    for n, o, d in fixtures():
        check(n, o, d)


def gate_mutation():
    weak = []
    for mu in MUTS:
        try:
            res = fixtures((mu,))
            caught = any(not o for _, o, _ in res)
        except Exception:
            caught = True
        if not caught:
            weak.append(mu)
    check(f"TU-01 every mirror mutation ({len(MUTS)}: t-1 vs t list, C close, A limit price, SL side, pending Strength / "
          "zone / Track checks, TP from L, cancel-bar guard, Track reuse, risk <= 0, boost-only candidates, TP with the "
          "entry, Track State check, closed-interval band) is caught by at least one TO fixture", weak == [], str(weak))


def main():
    for g in (gate_static, gate_model, gate_mutation):
        try:
            g()
        except Exception:
            import traceback
            check(f"{g.__name__} completed without error", False, traceback.format_exc()[-800:])
    w = max(len(n) for n, _, _ in RESULTS)
    fails = 0
    for n, ok, d in RESULTS:
        fails += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {n[:150].ljust(min(w, 150))}  {'' if ok else d}")
    print(f"\n{len(RESULTS) - fails}/{len(RESULTS)} passed  [PINE_NOT_VERIFIED: static / mirror + emulator assumption]")
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
