"""ST-3 fixtures — ZoneStrategyXAU.pine: D (1M BOS rebound), entry session, opposite-zone TP, breakeven stop.

  TS : static — deterministic build (ST-2 text + ST-3 block), exact inverse, Zone / Strength / FVG computation and
       strategy() untouched, request sites = ZONE-P 10 + one request.security_lower_tf (1M, only in D), single zone loop,
       orders only on confirmed 5M bars, defaults, key expressions pinned to the mirror
  TE : with Session / Zone TP / Breakeven off, the ST-3 mirror places and fills exactly the ST-2 orders (A / B / C)
  TD / TT / TR / TB : D order of events and non-repaint, session boundaries, RR 1.0 / 3.0 boundaries, breakeven timing
  TU : mutation power — each ST-3 mirror mutation is caught by at least one fixture

Evidence class: PINE_NOT_VERIFIED. The broker emulator (st2_sim.Broker) is an OHLC-path assumption, not TradingView.
"""
import os
import random
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import st2_build as s2      # noqa: E402
import st3_build as s3      # noqa: E402
import st2_sim as t2        # noqa: E402
import fvg_re10045_sim as fr  # noqa: E402

ROOT = s3.ROOT
ST = open(os.path.join(ROOT, s3.ST_PATH), encoding="utf-8").read()
RESULTS = []
SUP, RES, ACT, BRK = t2.SUP, t2.RES, t2.ACT, t2.BRK
Z, Broker = t2.Z, t2.Broker


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


code_only = t2.code_only

# =============================================================================
# TS : static
# =============================================================================
PINS = [
    "if stModeD and is5mChart",
    '[rt, rh, rl, rc] = request.security_lower_tf(syminfo.tickerid, "1", [time, high, low, close])',
    "if na(m1LastT) or tj > m1LastT",
    "if x.c.side == 1 ? cl > x.lvl : cl < x.lvl",
    "if x.cnt >= stDWait",
    "if dirOK and not map.contains(stUsed, c.track) and l <= c.top and h >= c.bot and (c.side == 1 ? m1PrevC > c.top : m1PrevC < c.bot)",
    "if cc.track == x.c.track and cc.side == x.c.side",
    "if (x.c.side == 1 ? close > x.c.top : close < x.c.bot) and not map.contains(stUsed, x.c.track)",
    "array<StCand> src = stModeA ? cur : stModeD ? dSrc : stPrev",
    "s == e ? true : s < e ? (mins >= s and mins < e) : (mins >= s or mins < e)",
    "bool stSessOK = not stUseSess or f_stInSession(time_close)",
    "if oState == 1 and (not pendOK or not stSessOK)",
    "if oState == 0 and not cancelBar and stSessOK",
    "if z.strength >= SR_MEDIUM",
    "else if eBoost and eStr >= SR_MEDIUM",
    "edge := zSide == -1 ? z.bottom : z.top",
    "edge := zSide == -1 ? eBBot : eBTop",
    "if side == 1 ? e > ref : e < ref",
    "float rrZ = side * (edge - fillPx) / risk",
    "if rrZ < stTpMinRR",
    "else if rrZ < stTpMaxRR",
    "[skipRR, tp] = f_stTp(oSide, oFill, oSL, f_stNearest(oSide == 1 ? tpUp : tpDn, oSide, oFill))",
    "float  ref = stModeA ? pL : close",
    "if stBE and oState == 2 and not oBE",
    "if fillNow and oLimit and oFill != open",
    "if oSide * (fav - oFill) >= stBEDist",
    "oStop := oFill",
]


def gate_static():
    st2 = s2.build()
    check("TS-01 ZoneStrategyXAU.pine == st3_transform(st2_build.build()); strip_st3 is the exact inverse",
          s3.build() == ST and s3.strip_st3(ST) == st2 and s3.st3_transform(s3.strip_st3(ST)) == ST)
    pre2, pre3 = st2[:st2.index(s3.LOOP_OLD)], ST[:ST.index(s3.LOOP_NEW)]
    check("TS-02 Zone generation / Strength / FVG Batch A, C / f_stZoneEval / strategy() identical to ST-2 (only the "
          "header comment and the order block differ)",
          pre3 == pre2.replace(s3.HDR_OLD, s3.HDR_NEW) and ST.endswith(st2[st2.index(s3.LOOP_OLD) + len(s3.LOOP_OLD):]))
    req = lambda s: re.findall(r"request\.\w+\(.*$", code_only(s), re.M)
    extra = [r for r in req(ST) if r not in req(st2)]
    check("TS-03 request sites = ST-2 / ZONE-P 10 + one request.security_lower_tf (1M, high / low / close), only "
          "executed in Entry Mode D",
          len(req(st2)) == 10 and len(req(ST)) == 11 and len(extra) == 1 and "security_lower_tf" in extra[0]
          and "    [rt, rh, rl, rc] = request.security_lower_tf(" in ST
          and ST.index("if stModeD and is5mChart\n") + len("if stModeD and is5mChart\n") == ST.index("    [rt, rh, rl, rc]"), str(extra))
    co = code_only(ST)
    blk = code_only(s3.LOOP_NEW)
    check("TS-04 one zone loop per confirmed bar (zn.zoneAt / f_stZoneEval once); TP edges collected in the same loop",
          co.count("zn.zoneAt(") == 1 and co.count("= f_stZoneEval(z)") == 1 and blk.count("for i = 0 to n - 1") == 1)
    lines = s3.LOOP_NEW.split("\n")
    gi = lines.index("if is5mChart and barstate.isconfirmed")
    gend = next(i for i in range(gi + 1, len(lines)) if lines[i] and not lines[i].startswith(" "))
    orders = [i for i, l in enumerate(lines) if re.search(r"strategy\.(entry|exit|close|cancel|order)\(", l)]
    check("TS-05 every order call inside the confirmed-5M block (nothing on 1M data / intrabar); no drawing; plots only "
          "to the data window", orders and all(gi < i < gend for i in orders)
          and all("display = display.data_window" in l for l in re.findall(r"^plot\(.*$", co, re.M))
          and not re.search(r"\b(box|label|line|table)\.(new|set_\w+|delete)\b", co), str(orders))
    check("TS-06 RE10045 lint clean; strategy() unchanged (no Bar Magnifier, no calc_on_order_fills)",
          fr.lint_eager_guards(blk) == [] and "use_bar_magnifier" not in ST and "calc_on_order_fills" not in ST)
    ins = dict(re.findall(r"^(st\w+) = (input\.\w+\(.*)$", s3.LOOP_NEW, re.M))
    want = {"stBuffer": "input.float(3.0,", "stRR": "input.float(1.5,", "stUseSess": "input.bool(true,",
            "stSessTz": 'input.string("Asia/Tokyo",', "stSessStartH": "input.int(9,", "stSessStartM": "input.int(0,",
            "stSessEndH": "input.int(2,", "stSessEndM": "input.int(0,", "stTpZone": "input.bool(true,",
            "stTpMinRR": "input.float(1.0,", "stTpMaxRR": "input.float(3.0,", "stBE": "input.bool(false,",
            "stBEDist": "input.float(10.0,", "stDWait": "input.int(30,", "stMode": 'input.string("D: 1M BOS Rebound",',
            "stDir": 'input.string("Both",', "stPinRatio": "input.float(2.0,"}
    zin = dict(re.findall(r"^(zoneHalfWidth|clusterDist|maClusterDist) = (input\.float\([0-9.]+),", ST, re.M))
    check("TS-07 defaults (TradingView reference setting): Entry Mode D, Direction Both, session ON JST 09:00-02:00, zone "
          "TP ON (RR 1.0 / 3.0, fixed 1.5R), breakeven OFF (trigger 10$ kept), Buffer 3, D wait 30; Zone Half Width 3 / "
          "Cluster Distance 5 / MA Cluster Distance 20 unchanged; Entry Mode still offers A / B / C / D",
          all(ins.get(k, "").startswith(v) for k, v in want.items()) and len(ins) == len(want)
          and zin == {"zoneHalfWidth": "input.float(3.0", "clusterDist": "input.float(5.0", "maClusterDist": "input.float(20.0"}
          and 'options = ["A: Touch Limit", "B: Confirmed Rejection", "C: Candle Pattern", "D: 1M BOS Rebound"]' in s3.LOOP_NEW,
          str({k: ins.get(k) for k in want}))
    miss = [p for p in PINS if blk.count(p) != 1]
    check("TS-08 key expressions present exactly once (mirrored in the TD / TT / TR / TB fixtures)", miss == [], str(miss))
    names = ["ZoneVisualPractical.pine", "ZoneEnginePractical.pine", "ZoneEnginePracticalRN.pine",
             "ZoneEnginePracticalSwingMax.pine", "PracticalZoneStrategy_LONG.pine", "PracticalZoneStrategy_SHORT.pine",
             "SignalEnginePractical.pine"]
    d = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", "f1d54bf", "--"] + names, capture_output=True, text=True).stdout
    check("TS-09 ZONE-P, Engines (/2, /5, /6), Strategy LONG / SHORT, SignalEngine unchanged", d.strip() == "", d)


# =============================================================================
# Mirror of the ST-3 block. bar extras: tmin (minutes of day in the session timezone of time_close), m1 = [(t, h, l, c)]
# =============================================================================
class Script3(t2.Script):
    def __init__(self, mode="B", dir="Both", buffer=3.0, rr=1.5, pin=2.0, mut=(), sess=True, s=9 * 60, e=3 * 60,
                 tpzone=True, minrr=1.0, maxrr=3.0, be=True, bedist=10.0, dwait=30):
        super().__init__(mode, dir, buffer, rr, pin, mut)
        self.sess, self.s, self.e = sess, s, e
        self.tpzone, self.minrr, self.maxrr, self.be, self.bedist = tpzone, minrr, maxrr, be, bedist
        self.oFill, self.oStop, self.oBE = None, None, False
        self.dwait, self.waits, self.m1LastT, self.m1PrevC = dwait, [], None, None

    def in_sess(self, mins):
        s, e = self.s, self.e
        if "sess_closed_end" in self.mut:
            return s <= mins <= e if s < e else (mins >= s or mins <= e)
        return True if s == e else (s <= mins < e if s < e else (mins >= s or mins < e))

    def d_process(self, m1, cur, c):
        """(2d): confirmed 1M bars of this 5M bar, each once; then release / collect against the post-update list."""
        mu = self.mut
        for (tj, h, l, cl) in m1:
            if not (self.m1LastT is None or tj > self.m1LastT or "d_dup" in mu):
                continue
            self.m1LastT = tj
            for x in reversed(list(self.waits)):
                if not x["bos"]:
                    x["cnt"] += 1
                    s_ = x["c"]["side"]
                    if (cl > x["lvl"]) if s_ == 1 else (cl < x["lvl"]):
                        x["bos"] = True
                    else:
                        x["run"] = max(x["run"], h) if s_ == 1 else min(x["run"], l)
                        if (l < x["ext"]) if s_ == 1 else (h > x["ext"]):
                            x["ext"] = l if s_ == 1 else h
                            x["lvl"] = x["run"]
                        lim = self.dwait + (1 if "d_expire_late" in mu else 0)
                        if x["cnt"] >= lim and "d_noexpire" not in mu:
                            self.waits.remove(x)
            pc = self.m1PrevC
            for cd in self.prev:
                dirOK = self.longOK if cd["side"] == 1 else self.shortOK
                frm = True if "d_anydir" in mu else (pc is not None and (pc > cd["top"] if cd["side"] == 1 else pc < cd["bot"]))
                pre = "d_prebos" in mu and (cl > cd["top"] + 3 if cd["side"] == 1 else cl < cd["bot"] - 3)
                if dirOK and cd["track"] not in self.used and ((l <= cd["top"] and h >= cd["bot"] and frm) or pre):
                    if any(w["c"]["track"] == cd["track"] for w in self.waits):
                        continue
                    aS, aSc = self.adopt(cd, max(l, cd["bot"]), min(h, cd["top"]))
                    if aS >= 3 or pre:
                        e0, r0 = (l, h) if cd["side"] == 1 else (h, l)
                        w = dict(c=cd, ext=e0, run=r0, lvl=r0, cnt=0, bos=pre, aS=aS, aSc=aSc)
                        if "d_same_bar" in mu and self.m1PrevC is not None:
                            w["lvl"] = self.m1PrevC
                            if (cl > w["lvl"]) if cd["side"] == 1 else (cl < w["lvl"]):
                                w["bos"] = True
                        self.waits.append(w)
            self.m1PrevC = cl
        if "d_carry_off" in mu:
            for x in list(self.waits):
                if not x["bos"]:
                    self.waits.remove(x)
        dSrc = []
        for x in reversed(list(self.waits)):
            valid = any(cc["track"] == x["c"]["track"] and cc["side"] == x["c"]["side"] for cc in cur)
            if not valid and "d_no_invalid" not in mu:
                self.waits.remove(x)
            elif x["bos"]:
                cd = x["c"]
                closeOK = True if "d_noclose" in mu else (c > cd["top"] if cd["side"] == 1 else c < cd["bot"])
                if closeOK and cd["track"] not in self.used:
                    dSrc.append((cd, x["aS"], x["aSc"]))
                self.waits.remove(x)
        return dSrc

    @staticmethod
    def nearest(edges, side, ref):
        best = None
        for e in edges:
            if (e > ref) if side == 1 else (e < ref):
                if best is None or ((e < best) if side == 1 else (e > best)):
                    best = e
        return best

    def tp(self, side, fill, sl, edge):
        risk = side * (fill - sl)
        tp, skip = fill + side * self.rr * risk, False
        if self.tpzone and edge is not None:
            rrZ = side * (edge - fill) / risk
            if rrZ < self.minrr or ("rr_min_le" in self.mut and rrZ <= self.minrr):
                skip = True
            elif rrZ < self.maxrr or ("rr_max_le" in self.mut and rrZ <= self.maxrr):
                tp = edge
            elif "rr_far_fixed" in self.mut:
                tp = edge
        return skip, tp

    def step(self, t, bar, prev, zones, B, tmin=12 * 60, m1=()):
        o, h, l, c = bar
        modeA, modeC, modeD = self.mode == "A", self.mode == "C", self.mode == "D"
        sessOK = (not self.sess) or self.in_sess(tmin)
        ev = dict(t=t)
        fillNow = False
        # (1)
        if self.oState == 1:
            filledOpen = len(B.open) > 0 and B.open[-1]["id"] == self.oEid
            filledClosed = (not filledOpen) and len(B.closed) > self.oClosed and B.closed[-1]["id"] == self.oEid
            if filledOpen:
                self.used.add(self.oTrack)
                self.oFill, self.oState, fillNow = B.open[-1]["price"], 2, True
            elif filledClosed:
                self.used.add(self.oTrack)
                self.oState = 0
                ev["same_bar_exit"] = True
            elif not self.oLimit:
                B.cancel(self.oEid)
                B.cancel(self.oXid)
                self.oState = 0
        elif self.oState >= 2 and len(B.open) == 0:
            self.oState = 0
        # (2)
        cur, curTrk, pendOK, tpUp, tpDn = [], [], False, [], []
        for z in zones:
            curTrk.append((z["track"], z["state"]))
            zSide = 1 if z["state"] == SUP else -1 if z["state"] == RES else 0
            if zSide != 0 and (z["sZ"] >= 3 or (z["boosted"] and z["sB"] >= 3)):
                cur.append(dict(side=zSide, track=z["track"], top=z["top"], bot=z["bot"], bTop=z["bTop"], bBot=z["bBot"],
                                sZ=z["sZ"], sB=z["sB"], score=z["score"], dScore=z["dScore"]))
            if self.oState == 1 and z["track"] == self.oTrack:
                inB = z["boosted"] and z["sB"] >= 3 and z["bBot"] <= self.oL <= z["bTop"]
                pendOK = zSide == self.oSide and z["bot"] <= self.oL <= z["top"] and (z["sZ"] >= 3 or inB)
            if zSide != 0 or "tp_any_state" in self.mut:
                side_ = zSide if zSide != 0 else (-1 if z["bot"] > c else 1)
                edge = None
                minS = 1 if "tp_weak" in self.mut else 2
                if z["sZ"] >= minS:
                    edge = z["bot"] if side_ == -1 else z["top"]
                elif z["boosted"] and z["sB"] >= minS:
                    edge = z["bot"] if ("tp_boost_full" in self.mut and side_ == -1) else (z["bBot"] if side_ == -1 else z["bTop"])
                if edge is not None:
                    (tpUp if side_ == -1 else tpDn).append(edge)
        if "tp_far" in self.mut:
            tpUp, tpDn = [max(tpUp)] if tpUp else [], [min(tpDn)] if tpDn else []
        # (2b)
        if fillNow:
            fill = self.oFill
            if "tp_from_ref" in self.mut and self.oLimit:
                fill = self.oL
            risk = self.oSide * (fill - self.oSL)
            if risk > 0:
                skip, tp = self.tp(self.oSide, fill, self.oSL, self.nearest(tpUp if self.oSide == 1 else tpDn, self.oSide, fill))
                if skip:
                    B.close(self.oEid)
                    self.oState = 3
                    ev["rr_skip"] = True
                else:
                    self.oTP, self.oStop = tp, self.oSL
                    B.exit(self.oXid, self.oEid, stop=self.oStop, limit=self.oTP)
                    ev["tp"] = tp
            else:
                B.close(self.oEid)
                self.oState = 3
                ev["close"] = True
        # (2c)
        if self.be and self.oState == 2 and not self.oBE:
            fav = h if self.oSide == 1 else l
            if fillNow and self.oLimit and self.oFill != o and "be_fill_hl" not in self.mut:
                fav = c
            dist = self.bedist + (0.01 if "be_strict" in self.mut else 0.0)
            if self.oSide * (fav - self.oFill) >= dist:
                self.oBE, self.oStop = True, self.oFill
                if "be_retro" in self.mut:
                    B.exits[self.oXid]["stop"] = self.oFill
                    for tr in list(B.open):
                        if (tr["side"] == 1 and l <= self.oFill) or (tr["side"] == -1 and h >= self.oFill):
                            B._close_trade(tr, self.oFill, t, "stop")
                else:
                    B.exit(self.oXid, self.oEid, stop=self.oStop, limit=self.oTP)
                ev["be"] = True
        # (2d)
        dSrc = self.d_process(m1, cur, c) if modeD else []
        # (3)
        cancelBar = False
        sessCancel = sessOK or "sess_no_cancel" in self.mut
        if self.oState == 1 and (not pendOK or not sessCancel):
            B.cancel(self.oEid)
            B.cancel(self.oXid)
            self.oState, cancelBar = 0, True
            ev["cancel"] = self.oEid
        # (4)
        if self.oState == 0 and not cancelBar and (sessOK or "sess_off_entry" in self.mut):
            src = cur if modeA else [x[0] for x in dSrc] if modeD else self.prev
            best = {1: None, -1: None}
            for k, cd in enumerate(src):
                dirOK = self.longOK if cd["side"] == 1 else self.shortOK
                if not dirOK or cd["track"] in self.used:
                    continue
                px = None
                if modeA:
                    px = (cd["top"] if cd["sZ"] >= 3 else cd["bTop"]) if cd["side"] == 1 else (cd["bot"] if cd["sZ"] >= 3 else cd["bBot"])
                    aS, aSc = self.adopt(cd, px, px)
                    d = abs(c - px)
                    ok = (c > cd["top"] if cd["side"] == 1 else c < cd["bot"]) and aS >= 3
                elif modeD:
                    aS, aSc = dSrc[k][1], dSrc[k][2]
                    d = abs(c - (cd["top"] if cd["side"] == 1 else cd["bot"]))
                    ok = True
                else:
                    aS, aSc = self.adopt(cd, max(l, cd["bot"]), min(h, cd["top"]))
                    d = abs(c - (cd["top"] if cd["side"] == 1 else cd["bot"]))
                    st = dict(curTrk).get(cd["track"])
                    trkOK = st == (SUP if cd["side"] == 1 else RES)
                    ok = l <= cd["top"] and h >= cd["bot"] and (c > cd["top"] if cd["side"] == 1 else c < cd["bot"]) \
                        and aS >= 3 and trkOK and (not modeC or self.pat(cd["side"], bar, prev))
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
                pL = best[side][2] if modeA else None
                pSL = cd["bot"] - self.buffer if side == 1 else cd["top"] + self.buffer
                ref = pL if modeA else c
                skipRef = False if "no_precheck" in self.mut else \
                    self.tp(side, ref, pSL, self.nearest(tpUp if side == 1 else tpDn, side, ref))[0]
                if skipRef:
                    ev["rr_skip_ref"] = True
                else:
                    self.oSeq += 1
                    self.oEid = ("L" if side == 1 else "S") + str(self.oSeq)
                    self.oXid = self.oEid + " SL/TP"
                    self.oSide, self.oTrack, self.oLimit = side, cd["track"], modeA
                    self.oL, self.oSL, self.oStop, self.oTP, self.oFill, self.oBE = pL, pSL, pSL, None, None, False
                    self.oClosed, self.oState = len(B.closed), 1
                    B.entry(self.oEid, side, limit=self.oL if modeA else None)
                    B.exit(self.oXid, self.oEid, stop=self.oSL)
                    ev["order"] = dict(id=self.oEid, side=side, track=cd["track"], L=self.oL, SL=self.oSL)
        self.prev = cur
        self.log.append(ev)


def run3(bars, zones, broker=None, tmins=None, m1s=None, **kw):
    S, B = Script3(**kw), broker or Broker()
    for t in range(len(bars)):
        if t > 0:
            B.process(t, bars[t])
        S.step(t, bars[t], bars[t - 1] if t > 0 else bars[t], zones[t], B,
               tmin=(tmins[t] if tmins else 12 * 60), m1=(m1s[t] if m1s else ()))
    return S, B


orders = t2.orders
OFF = dict(sess=False, tpzone=False, be=False)
ZL = t2.ZL
FLAT = t2.FLAT


# =============================================================================
# fixtures
# =============================================================================
def fixtures(mut=()):
    R = []

    def ok(name, cond, detail=""):
        R.append((name, bool(cond), detail))

    m = dict(mut=mut)
    # --- D -----------------------------------------------------------------------------------------------------------
    def M(*bars_m1, t0=0):
        """1M arrays with unique increasing times (5 per 5M bar); bar 0 defaults to one 1M bar closing at 105."""
        out = []
        for b, lst in enumerate(bars_m1):
            lst = lst if (lst or b) else [(106.0, 104.0, 105.0)]
            out.append([(t0 + b * 5 + j, h, l, c) for j, (h, l, c) in enumerate(lst)])
        return out

    D = dict(mode="D", **OFF, **m)
    # bar 1: from above (prev 1M close 105) -> touch 99.0 -> BOS close 102.6 > 102.5 (high from touch to the low)
    bt = (103.0, 103.5, 99.0, 101.5)
    good = [(103.5, 102.0, 102.2), (102.5, 99.0, 100.0), (101.0, 99.5, 100.8), (102.7, 100.5, 102.6), (102.8, 101.3, 101.5)]
    nxt = (101.6, 102.0, 101.0, 101.8)
    S, B = run3([FLAT, bt, nxt], [[ZL]] * 3, m1s=M([], good, []), **D)
    ok("TD-01 D: touch from above -> rebound -> confirmed 1M BOS inside the same 5M bar -> order at that 5M close, filled at "
       "the next 5M open 101.6 (not at the 1M BOS)",
       [x for _, x in orders(S)] == [dict(id="L1", side=1, track=1, L=None, SL=91.0)] and orders(S)[0][0] == 1
       and B.fills and B.fills[0]["price"] == 101.6 and B.fills[0]["bar"] == 2, str((orders(S), B.fills)))
    t1 = [(103.5, 102.0, 102.2), (102.5, 99.0, 100.0), (101.0, 99.5, 100.8), (101.5, 100.2, 101.0), (101.2, 100.4, 100.9)]
    t2_ = [(101.3, 100.6, 101.1), (102.4, 100.9, 102.3), (102.7, 101.9, 102.6), (102.8, 102.0, 102.5), (102.9, 102.2, 102.7)]
    S, B = run3([FLAT, (103.0, 103.5, 99.0, 100.9), (101.0, 102.9, 100.6, 102.7), nxt], [[ZL]] * 4, m1s=M([], t1, t2_, []), **D)
    ok("TD-02 D carries the wait to the next 5M bar: touch in bar 1 (no BOS there), BOS by the 1M close 102.6 in bar 2 -> "
       "order at the bar-2 close only (none at bar 1), filled at the bar-3 open",
       [t for t, _ in orders(S)] == [2] and B.fills and B.fills[0]["bar"] == 3, str((S.log, B.fills)))
    pre = [(103.5, 102.0, 103.4), (103.4, 101.0, 101.2), (101.3, 99.0, 99.5), (100.2, 99.2, 100.0), (101.25, 99.9, 101.2)]
    S, _ = run3([FLAT, (103.0, 103.5, 99.0, 101.2), FLAT], [[ZL]] * 3, m1s=M([], pre, [(101.3, 101.0, 101.2)] * 5), **D)
    ok("TD-03 a break of structure before the touch is not counted (1M closes 103.4 before the touch; after the touch no "
       "close beyond the touch-to-low high 101.3) -> no entry", orders(S) == [], str(S.log))
    below = [(99.5, 98.5, 99.4), (100.0, 99.0, 99.8), (101.0, 99.5, 100.8), (102.7, 100.5, 102.6), (102.8, 101.3, 101.5)]
    S, _ = run3([(99.0, 99.6, 98.0, 99.2), bt], [[ZL]] * 2, m1s=M([(99.6, 98.0, 99.2)], below), **D)
    ok("TD-04 approach from inside / below the zone (previous 1M close 99.2) is not a valid touch -> no entry",
       orders(S) == [], str(S.log))
    same = [(103.5, 102.0, 102.2), (103.9, 99.0, 103.8), (103.9, 103.0, 103.2), (103.5, 102.9, 103.0), (103.2, 101.3, 101.5)]
    S, _ = run3([FLAT, (103.0, 103.9, 99.0, 101.5)], [[ZL]] * 2, m1s=M([], same), **D)
    ok("TD-05 the touch 1M bar itself cannot be the BOS (close 103.8 there); later closes stay below the level 103.9 -> no "
       "entry", orders(S) == [], str(S.log))
    # expiry: touch = 1M #0 of 5M bar 1; drift bars never close above the level 102.5; BOS on the k-th 1M bar after the touch
    touch = (102.5, 99.0, 100.0)
    drift = (101.5, 100.3, 100.8)            # stays above the zone (no re-touch) and below the level
    bosb = (103.0, 100.6, 102.8)

    def expiry_case(k, wait=30):
        seq = [touch] + [drift] * (k - 1) + [bosb] + [drift] * 6
        chunks = [seq[x:x + 5] for x in range(0, len(seq), 5)]
        nbar = len(chunks) + 1
        bars = [FLAT] + [(101.0, 103.0, 99.0, 102.8 if bosb in ch else 100.5) for ch in chunks]
        S, B = run3(bars + [nxt], [[ZL]] * (nbar + 1), m1s=M([], *chunks, []), dwait=wait, **D)
        return [t for t, _ in orders(S)], 1 + (k // 5)

    e30, e31 = expiry_case(30), expiry_case(31)
    e5 = expiry_case(5, wait=5)
    e6 = expiry_case(6, wait=5)
    ok("TD-06 wait limit counts confirmed 1M bars after the touch: BOS on the 30th -> order at that 5M close; on the 31st "
       "-> released, no order (input 5: 5th yes, 6th no)",
       e30[0] == [e30[1]] and e31[0] == [] and e5[0] == [e5[1]] and e6[0] == [],
       str((e30, e31, e5, e6)))
    S, _ = run3([FLAT, (103.0, 103.5, 99.0, 100.9), (101.0, 102.9, 100.6, 102.7), nxt],
                [[ZL], [ZL], [dict(ZL, state=ACT)], [ZL]], m1s=M([], t1, t2_, []), **D)
    S2, _ = run3([FLAT, (103.0, 103.5, 99.0, 100.9), (101.0, 102.9, 100.6, 101.0), (101.0, 102.9, 100.6, 102.7)],
                 [[ZL], [dict(ZL, sZ=2)], [ZL], [ZL]], m1s=M([], t1, [(101.2, 100.6, 101.0)] * 5, t2_), **D)
    ok("TD-07 the wait is released when the zone stops being a valid candidate (State ACTIVE at the BOS bar; Strength "
       "Medium for one bar before the BOS) -> no entry, even when the zone is valid again later",
       orders(S) == [] and orders(S2) == [], str((S.log, S2.log)))
    dup1 = [(103.5, 102.0, 103.4), (103.4, 101.6, 101.8), (101.9, 99.0, 100.0), (101.0, 99.5, 100.5), (101.0, 100.2, 100.8)]
    m1s = M([], dup1, [(101.0, 100.4, 100.8)] * 5, [])
    m1s[2] = m1s[1][:2] + m1s[2]                   # bar 2 repeats two already-processed 1M bars (old times)
    S, _ = run3([FLAT, (103.0, 103.5, 99.0, 100.8), (101.0, 101.0, 100.4, 100.8), nxt], [[ZL]] * 4, m1s=m1s, **D)
    ok("TD-08 each 1M bar is processed once: 1M bars whose time is not after the last processed one are skipped (a repeated "
       "close 103.4 would otherwise count as a BOS)", orders(S) == [], str(S.log))
    S1, _ = run3([FLAT, (103.0, 103.5, 99.0, 99.8)], [[ZL]] * 2, m1s=M([], good[:4] + [(102.8, 99.5, 99.8)]), **D)
    S2, _ = run3([FLAT, bt], [[], [ZL]], m1s=M([], good), **D)
    S3, _ = run3([FLAT, bt], [[ZL], [dict(ZL, state=BRK)]], m1s=M([], good), **D)
    ok("TD-09 the BOS bar's 5M close back inside the zone -> none; a zone that only exists after the update of t is not "
       "touched in t (touches use the t-1 candidates) -> none; Track BROKEN at t -> none",
       orders(S1) == orders(S2) == orders(S3) == [], str((S1.log, S2.log, S3.log)))
    base = [FLAT, (103.0, 103.5, 99.0, 100.9), (101.0, 102.9, 100.6, 102.7), nxt, (101.8, 103.0, 101.5, 102.5)]
    S1, B1 = run3(base, [[ZL]] * 5, m1s=M([], t1, t2_, [], []), **D)
    alt = base[:3] + [(95.0, 96.0, 80.0, 81.0), (81.0, 82.0, 70.0, 71.0)]
    S2, B2 = run3(alt, [[ZL]] * 3 + [[]] * 2, m1s=M([], t1, t2_, [(96.0, 80.0, 81.0)], []), **D)
    ok("TD-10 non-repaint: decisions up to t depend only on confirmed 1M / 5M data up to t (later bars changed -> same "
       "log up to t and the same order at t)", S1.log[:3] == S2.log[:3] and len(orders(S1)) == 1 and orders(S1) == orders(S2),
       str((S1.log[:3], S2.log[:3])))
    S, B = run3([FLAT, bt, nxt, (101.8, 102.0, 101.5, 101.9)], [[ZL, Z(2, SUP, 100.5, 96.0)]] * 4,
                m1s=M([], good, [(102.0, 101.0, 101.8)] * 5, []), **D)
    ok("TD-11 one order at a time: the second zone's touch / BOS while the first order is open is consumed without an "
       "order", len(orders(S)) == 1, str(orders(S)))
    # --- Session -----------------------------------------------------------------------------------------------------
    hits = []
    for tm, exp in ((8 * 60 + 55, 0), (9 * 60, 1), (23 * 60 + 55, 1), (0, 1), (2 * 60 + 55, 1), (3 * 60, 0), (5 * 60, 0)):
        S, B = run3([FLAT, (103.0, 103.5, 99.0, 101.0), FLAT], [[ZL]] * 3, tmins=[tm] * 3, mode="B", tpzone=False, be=False, **m)
        hits.append((tm, len(orders(S)), exp))
    ok("TT-01 new entries only when the decision bar's close time (= the next-open fill time) is in [09:00, 03:00) JST: "
       "08:55 no, 09:00 yes, 23:55 / 00:00 / 02:55 yes, 03:00 / 05:00 no", all(n == e for _, n, e in hits), str(hits))
    S, B = run3([FLAT, (104.0, 104.5, 101.0, 104.0), (104.0, 104.5, 101.0, 104.0), (103.0, 103.5, 99.0, 100.5)], [[ZL]] * 4,
                tmins=[2 * 60 + 50, 2 * 60 + 55, 3 * 60, 3 * 60 + 5], mode="A", tpzone=False, be=False, **m)
    ok("TT-02 A pending: placed at 02:50, kept at 02:55, cancelled at the 03:00 close (out of session) -> the 03:00-03:05 "
       "bar crosses L 100 without a fill; no new order out of session",
       [t for t, _ in orders(S)] == [0] and "cancel" in S.log[2] and not B.fills, str((S.log, B.fills)))
    S, B = run3([FLAT, (103.0, 103.5, 99.0, 101.0), (101.5, 104.0, 101.0, 103.5), (103.5, 112.0, 103.0, 111.0),
                 (111.0, 119.0, 110.5, 118.0)], [[ZL]] * 5, tmins=[2 * 60 + 45, 2 * 60 + 50, 2 * 60 + 55, 3 * 60 + 30, 4 * 60],
                mode="B", tpzone=False, **m)
    ok("TT-03 out of session the open position is still managed: breakeven moved at 03:30, TP 117.25 filled at 04:00",
       S.log[3].get("be") and B.closed and B.closed[0]["exit"] == 117.25 and B.closed[0]["exit_bar"] == 4, str((S.log, B.closed)))
    S, _ = run3([FLAT, (103.0, 103.5, 99.0, 101.0)], [[ZL]] * 2, tmins=[5 * 60] * 2, mode="B", s=9 * 60, e=9 * 60, tpzone=False, **m)
    ok("TT-04 start == end means all day", len(orders(S)) == 1)
    dv = {k: int(v) for k, v in re.findall(r"^(stSess(?:Start|End)[HM]) = input\.int\((\d+),", s3.LOOP_NEW, re.M)}
    sd, ed = dv["stSessStartH"] * 60 + dv["stSessStartM"], dv["stSessEndH"] * 60 + dv["stSessEndM"]
    hits = []
    for tm, exp in ((8 * 60 + 55, 0), (9 * 60, 1), (23 * 60 + 55, 1), (0, 1), (60 + 55, 1), (2 * 60, 0), (2 * 60 + 30, 0),
                    (2 * 60 + 55, 0), (3 * 60, 0)):
        S, B = run3([FLAT, (103.0, 103.5, 99.0, 101.0), FLAT], [[ZL]] * 3, tmins=[tm] * 3, mode="B", s=sd, e=ed,
                    tpzone=False, be=False, **m)
        hits.append((tm, len(orders(S)), exp))
    S, B = run3([FLAT, (104.0, 104.5, 101.0, 104.0), (104.0, 104.5, 101.0, 104.0), (103.0, 103.5, 99.0, 100.5)], [[ZL]] * 4,
                tmins=[60 + 50, 60 + 55, 2 * 60, 2 * 60 + 5], mode="A", s=sd, e=ed, tpzone=False, be=False, **m)
    ok("TT-05 Pine default session (parsed from the source) = JST 09:00-02:00 across midnight: decision-bar close 08:55 no, "
       "09:00 / 23:55 / 00:00 / 01:55 yes, 02:00 / 02:30 / 02:55 / 03:00 no (last entry fills at the 01:55 open); an A "
       "limit placed at 01:50 is cancelled at the 02:00 close and does not fill in the 02:00-02:05 bar",
       (sd, ed) == (9 * 60, 2 * 60) and all(n == e for _, n, e in hits)
       and [t for t, _ in orders(S)] == [0] and "cancel" in S.log[2] and not B.fills, str((sd, ed, hits, S.log)))
    # --- TP: nearest opposite zone, RR 1.0 / 3.0 ----------------------------------------------------------------------
    # B long: fill at next open 101.5, SL 91, risk 10.5. RR(edge) = (edge - 101.5) / 10.5
    bars = [FLAT, (103.0, 103.5, 99.0, 101.0), (101.5, 102.0, 101.0, 101.8), (101.8, 140.0, 101.7, 139.0)]

    def tp_case(edge, ref_ok=True):
        zr = Z(9, RES, edge + 5.0, edge, sZ=2, score=4.0)
        zs = [[ZL, zr]] * 4
        S, B = run3(bars, zs, mode="B", sess=False, be=False, **m)
        return S, B

    res = {}
    for name, edge in (("0.99", 101.5 + 0.99 * 10.5), ("1.0", 101.5 + 1.0 * 10.5), ("2.99", 101.5 + 2.99 * 10.5),
                       ("3.0", 101.5 + 3.0 * 10.5)):
        S, B = tp_case(edge)
        res[name] = (len(orders(S)), S.log[2].get("tp"), bool(S.log[2].get("rr_skip")))
    ok("TR-01 RR boundaries on the actual fill (101.5, SL 91, risk 10.5): zone RR 0.99 -> no TP, market exit (RR skip); "
       "RR 1.0 -> TP = zone edge; RR 2.99 -> zone edge; RR 3.0 -> fixed 1.5R (117.25)",
       res["0.99"][:3] == (1, None, True)
       and res["1.0"][1] == 101.5 + 10.5 and res["2.99"][1] == 101.5 + 2.99 * 10.5 and res["3.0"][1] == 117.25, str(res))
    pre_ = []
    for edge in (101.0 + 0.99 * 10.0, 101.0 + 1.0 * 10.0):
        S, B = run3(bars, [[ZL, Z(9, RES, edge + 5.0, edge, sZ=2, score=4.0)]] * 4, mode="B", sess=False, be=False, **m)
        pre_.append((len(orders(S)), bool(S.log[1].get("rr_skip_ref"))))
    ok("TR-01b pre-check with the reference price (decision close 101, SL 91): zone RR 0.99 -> no order; RR 1.0 -> ordered",
       pre_ == [(0, True), (1, False)], str(pre_))
    S, B = run3(bars, [[ZL]] * 4, mode="B", sess=False, be=False, **m)
    ok("TR-02 no eligible opposite zone -> fixed 1.5R from the actual fill", S.log[2].get("tp") == 117.25, str(S.log[2]))
    # reference passes (close 101 -> RR 1.05), the actual fill gaps up to 101.9 -> RR 0.95 -> no TP, market exit
    edge = 101.0 + 1.05 * 10.0
    S, B = run3([FLAT, (103.0, 103.5, 99.0, 101.0), (101.9, 102.0, 101.5, 101.8), (101.7, 102.0, 101.0, 101.5)],
                [[ZL, Z(9, RES, edge + 5, edge, sZ=2, score=4.0)]] * 4, mode="B", sess=False, be=False, **m)
    ok("TR-03 RR is re-decided on the actual fill: the reference passes but the fill (101.9) gives RR < 1.0 -> no TP, "
       "strategy.close at the next open (the trade exists and is labelled as an RR skip)",
       len(orders(S)) == 1 and S.log[2].get("rr_skip") and "tp" not in S.log[2] and B.closed and B.closed[0]["why"] == "close",
       str((S.log, B.closed)))
    near_weak = Z(8, RES, 106.0, 104.0, sZ=1, score=1.0)
    near_low = Z(9, RES, 110.0, 108.0, sZ=2, score=4.0)            # RR 0.62 -> skip, never jump to 125
    far = Z(10, RES, 130.0, 125.0, sZ=3, score=8.0)
    S, B = run3(bars, [[ZL, near_weak, near_low, far]] * 4, mode="B", sess=False, be=False, **m)
    S2, B2 = run3(bars, [[ZL, near_weak, far]] * 4, mode="B", sess=False, be=False, **m)
    ok("TR-04 only Medium+ opposite zones count (Weak 104 ignored); the nearest one decides (108, RR < 1.0 -> skip, no jump "
       "to the farther 125); without it the farther zone 125 (RR 2.24) is the TP",
       orders(S) == [] and S2.log[2].get("tp") == 125.0, str((S.log, S2.log[2])))
    zb = Z(11, RES, 125.0, 110.0, sZ=1, score=2.0, boosted=True, sB=2, dScore=4.0, bTop=125.0, bBot=118.0)
    zbad = Z(12, BRK, 112.0, 111.0, sZ=3)
    S, B = run3(bars, [[ZL, zb, zbad]] * 4, mode="B", sess=False, be=False, **m)
    ok("TR-05 a Weak zone whose FVG boost range is Medium gives its boost-range near edge (118, RR 1.57); BROKEN / ACTIVE "
       "zones are not TP candidates", S.log[2].get("tp") == 118.0, str(S.log[2]))
    zs = Z(13, SUP, 90.0, 85.0, sZ=2)
    S, B = run3([FLAT, (101.0, 102.5, 99.5, 101.0)], [[Z(5, RES, 108.0, 102.0), zs]] * 2, mode="B", dir="Short", sess=False, be=False, **m)
    S2, B2 = run3([FLAT, (101.0, 102.5, 99.5, 101.0), (101.0, 101.5, 80.0, 82.0)],
                  [[Z(5, RES, 108.0, 102.0), Z(14, SUP, 95.0, 92.0, sZ=2)]] * 3, mode="B", dir="Short", sess=False, be=False, **m)
    ok("TR-06 Short side: the TP is the nearest SUPPORT top below the fill (100 -> 95, RR = 5 / 10 = 0.5 skip; with "
       "the zone at 90 (top) and SL 111: RR 11 / 10 = 1.1 -> TP 90)",
       S2.log[1].get("rr_skip_ref") and orders(S2) == [] and len(orders(S)) == 1, str((S.log, S2.log)))
    S, B = run3([FLAT, (99.0, 104.0, 98.5, 103.0), FLAT], [[ZL]] * 3, mode="A", sess=False, be=False, **m)
    ok("TR-07 A gap fill (open 99 below L 100): RR / TP use the actual fill (99 + 1.5 x 8 = 111), not the limit price",
       B.fills and B.fills[0]["price"] == 99.0 and S.log[1].get("tp") == 111.0, str(S.log[1]))
    # --- Breakeven -----------------------------------------------------------------------------------------------------
    S, B = run3([FLAT, (103.0, 103.5, 99.0, 101.0), (101.5, 111.6, 100.0, 101.0), (100.0, 100.5, 95.0, 96.0)], [[ZL]] * 4,
                mode="B", sess=False, tpzone=False, **m)
    ok("TB-01 breakeven reached inside the fill bar (high 111.6 >= 101.5 + 10) is detected at that bar's close; the bar's own "
       "later fall to 100 does not hit a breakeven stop; the moved stop works from the next bar (opens 100 below 101.5 -> "
       "stop fills at the open 100 in the emulator)",
       S.log[2].get("be") and not any(c_["exit_bar"] == 2 for c_ in B.closed) and B.closed and B.closed[0]["exit_bar"] == 3
       and B.closed[0]["exit"] == 100.0, str((S.log, B.closed)))
    S, B = run3([FLAT, (104.0, 111.0, 99.5, 105.0), (105.0, 106.0, 104.0, 105.5)], [[ZL]] * 3, mode="A", sess=False, tpzone=False, **m)
    ok("TB-02 A filled mid-bar: the fill bar's high 111 came before the fill (O -> H -> L path) -> only the close 105 is "
       "used (< 110) -> no breakeven on the fill bar", B.fills and "be" not in S.log[1], str(S.log))
    res = []
    for hi in (111.5, 111.49):
        S, B = run3([FLAT, (103.0, 103.5, 99.0, 101.0), (101.5, 102.0, 101.0, 101.8), (101.8, hi, 101.6, 105.0)], [[ZL]] * 4,
                    mode="B", sess=False, tpzone=False, **m)
        res.append(bool(S.log[3].get("be")))
    S, B = run3([FLAT, (103.0, 103.5, 99.0, 101.0), (101.5, 102.0, 101.0, 101.8), (101.8, 112.0, 101.6, 105.0)], [[ZL]] * 4,
                mode="B", sess=False, tpzone=False, be=False, **m)
    ok("TB-03 trigger is >= 10$: +10.00 moves, +9.99 does not; breakeven OFF never moves",
       res == [True, False] and not any(e.get("be") for e in S.log), str(res))
    return R


# =============================================================================
# TE : equivalence with ST-2 when Session / Zone TP / Breakeven are off
# =============================================================================
def random_case(rnd, n=40):
    bars, zones, p = [], [], 100.0
    tracks = {}
    for t in range(n):
        o = p
        c = o + rnd.gauss(0, 2.5)
        h, l = max(o, c) + abs(rnd.gauss(0, 1.5)), min(o, c) - abs(rnd.gauss(0, 1.5))
        bars.append((round(o, 2), round(h, 2), round(l, 2), round(c, 2)))
        p = c
        if rnd.random() < 0.3 or not tracks:
            k = rnd.randint(1, 6)
            ctr = p + rnd.choice([-1, 1]) * rnd.uniform(1, 8)
            tracks[k] = (round(ctr + 3, 2), round(ctr - 3, 2))
        zs = []
        for k, (tp_, bt_) in sorted(tracks.items()):
            st = SUP if c > tp_ else RES if c < bt_ else ACT
            if rnd.random() < 0.05:
                st = BRK
            sZ = rnd.choice([2, 3, 3, 4])
            if rnd.random() < 0.3:
                bT = round(rnd.uniform(bt_, tp_), 2)
                bB = round(rnd.uniform(bt_, bT), 2)
                zs.append(Z(k, st, tp_, bt_, sZ=min(sZ, 2), score=5.0, boosted=True, sB=3, dScore=7.0, bTop=bT, bBot=bB))
            else:
                zs.append(Z(k, st, tp_, bt_, sZ=sZ, score=float(sZ * 3)))
        zones.append(zs)
    return bars, zones


def gate_equiv():
    rnd = random.Random(11)
    bad, n_orders = [], 0
    for i in range(300):
        bars, zones = random_case(rnd)
        mode = ["A", "B", "C"][i % 3]
        dr = ["Both", "Long", "Short"][(i // 3) % 3]
        Sa, Ba = t2.run(bars, zones, mode=mode, dir=dr)
        Sb, Bb = run3(bars, zones, mode=mode, dir=dr, **OFF)
        n_orders += len(orders(Sa))
        if orders(Sa) != orders(Sb) or Ba.fills != Bb.fills or Ba.closed != Bb.closed:
            bad.append(i)
    check("TE-01 Session / Zone TP / Breakeven OFF: A / B / C orders, fills and exits identical to ST-2 (300 random cases, "
          "all modes and directions)", bad == [] and n_orders > 50, f"bad={bad[:10]} orders={n_orders}")


MUTS = ["d_anydir", "d_same_bar", "d_prebos", "d_noclose", "d_dup", "d_expire_late", "d_noexpire", "d_no_invalid",
        "d_carry_off", "sess_closed_end", "sess_no_cancel", "sess_off_entry",
        "rr_min_le", "rr_max_le", "rr_far_fixed", "tp_weak", "tp_boost_full", "tp_far", "tp_any_state",
        "tp_from_ref", "no_precheck", "be_fill_hl", "be_strict", "be_retro"]


def gate_fixtures():
    for n, o, d in fixtures():
        check(n, o, d)


def gate_mutation():
    weak = []
    for mu in MUTS:
        try:
            caught = any(not o for _, o, _ in fixtures((mu,)))
        except Exception:
            caught = True
        if not caught:
            weak.append(mu)
    check(f"TU-01 every ST-3 mirror mutation ({len(MUTS)}: D touch direction / same-bar BOS / pre-touch BOS / close, session "
          "end / cancel / entry, RR 1.0 and 3.0 boundaries, Medium filter, boost edge, nearest zone, state, fill vs "
          "reference, pre-check, breakeven fill-bar / >= / retroactive) is caught", weak == [], str(weak))


def main():
    for g in (gate_static, gate_equiv, gate_fixtures, gate_mutation):
        try:
            g()
        except Exception:
            import traceback
            check(f"{g.__name__} completed without error", False, traceback.format_exc()[-900:])
    fails = 0
    for n, ok, d in RESULTS:
        fails += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {n[:150].ljust(150)}  {'' if ok else d}")
    print(f"\n{len(RESULTS) - fails}/{len(RESULTS)} passed  [PINE_NOT_VERIFIED: static / mirror + emulator assumption]")
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
