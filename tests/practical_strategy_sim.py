#!/usr/bin/env python3
"""
Practical Zone Strategy — structural fixtures (Python, NOT a Pine compile).

P02: PracticalZoneFeedHarness.pine Zone parity with ZoneVisualPractical (Z1-Z8).
P01: SignalEnginePractical.pine must be a faithful extraction of SignalEngine.pine
(SignalEngine/21 source). This script parses both Pine files and checks:

  F1  Factory functions are verbatim copies (initial engine state identical)
  F2  Engine state types: same fields, same defaults
  F3  Cfg types: same fields, same defaults (only documented dead fields removed)
  F4  consume* / fvg15Preview are verbatim, and their state transitions behave as
      SignalEngine/21 defines them (Python mirror of the copied source)
  F5  Preview fields exist on every Signal type
  F6  Zone event lifecycle fields exist (frozen geometry + phase + done flags)
  F7  Long/Short shared state is retained
  F8  Every removed field is unread by SignalEngine/21 decision code
  F9  Excluded items (ZONEBOS / ZONESR / debug / display helpers) are absent
  F10 Helpers used by decisions are verbatim
  F11 No array.new outside factories (no per-bar allocation in the library)

Evidence class: PINE_NOT_VERIFIED (static / mirror checks only).
Run:  python3 tests/practical_strategy_sim.py
"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORIG = open(os.path.join(ROOT, "SignalEngine.pine"), encoding="utf-8").read()
NEW = open(os.path.join(ROOT, "SignalEnginePractical.pine"), encoding="utf-8").read()

RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))


FIELD_RE = re.compile(r"^\s+(bool|int|float|string|array<\w+>|\w+)\s+(\w+)(?:\s*=\s*(.*?))?\s*(?://.*)?$")


def parse_types(src):
    """{TypeName: {field: (type, default)}} for every `export type`."""
    types, cur = {}, None
    for ln in src.split("\n"):
        m = re.match(r"^export type (\w+)", ln)
        if m:
            cur = m.group(1)
            types[cur] = {}
            continue
        if cur is None:
            continue
        if ln and not ln[0].isspace():
            cur = None
            continue
        if ln.strip().startswith("//") or not ln.strip():
            continue
        fm = FIELD_RE.match(ln)
        if fm:
            types[cur][fm.group(2)] = (fm.group(1), (fm.group(3) or "").strip())
    return types


def func_block(src, name):
    """Source text of a top-level function `name(` up to the next top-level line."""
    lines = src.split("\n")
    out, inside = [], False
    for ln in lines:
        if re.match(r"^(export\s+)?" + re.escape(name) + r"\(", ln):
            inside = True
            out.append(ln)
            continue
        if inside:
            if ln and not ln[0].isspace():
                break
            out.append(ln)
    while out and not out[-1].strip():
        out.pop()
    return "\n".join(out)


OT = parse_types(ORIG)
NT = parse_types(NEW)

REMOVED = {
    "FvgCfg": {"minScore4H", "minScore1H", "minScore15M", "minScore5M", "minScore1M"},
    "FvgFeed": {"dReason", "dRem", "dBos", "hReason", "hRem", "hBos", "oReason", "oRem", "oBos",
                "b5Reason", "b5Rem", "b1Reason", "b1Rem", "b1Bos"},
    "FvgSignal": {"drLongOk", "drShortOk", "trigBull", "trigBear", "trigNoTrade", "longMajorOk",
                  "shortMajorOk", "efvgFinalBias", "efvgScore", "mBias", "mReason", "mRem", "mBos",
                  "drDirCode", "drVolCode", "trigCooldownOk"} | {f for f in OT["FvgSignal"] if f.startswith("dbg")},
    "Fvg15Signal": {"bosOkLong", "bosOkShort", "rebReason", "previewBosOkLong", "previewBosOkShort"},
    "FvgAbsSignal": {"bos5Ok", "bos15Ok", "bos5OkS", "bos15OkS", "previewBos15Ok", "previewBos15OkS"},
    "ZoneEnvFeed": {"blockedByAccum"},
    "ZoneLogicSignal": {"evtCount", "candTouch", "candFake", "candRetest"} |
                       {f for f in OT["ZoneLogicSignal"] if f.startswith("dbgRb")},
}
KEPT_TYPES = ["FvgTrigCfg", "FvgEnvCfg", "FvgAccCfg", "FvgCfg", "FvgFeed", "FvgEngine", "FvgSignal",
              "Fvg15Engine", "Fvg15Signal", "FvgAbsEngine", "FvgAbsSignal",
              "ZoneTfEnvCfg", "ZoneEnvSet", "ZoneCommonCfg", "ZoneEnvFeed", "ZoneEvt", "ZoneEvtEngine",
              "ZoneLogicSignal"]


def fixture_types():
    check("T0 kept type set == expected 18 types", sorted(NT) == sorted(KEPT_TYPES), str(sorted(NT)))
    for t in KEPT_TYPES:
        o, n = OT[t], NT.get(t, {})
        exp = {k: v for k, v in o.items() if k not in REMOVED.get(t, set())}
        same = exp == n
        tag = ("F2" if "Engine" in t or t == "ZoneEvt" else "F3" if "Cfg" in t or t == "ZoneEnvSet"
               else "F3f" if "Feed" in t else "F5s")
        diff = ""
        if not same:
            diff = f"missing={sorted(set(exp) - set(n))} extra={sorted(set(n) - set(exp))} " \
                   f"changed={[k for k in exp if k in n and exp[k] != n[k]]}"
        check(f"{tag} {t}: fields/defaults identical to SignalEngine/21 (minus documented dead fields)",
              same, diff or f"{len(n)} fields, removed {len(o) - len(n)}")


def fixture_factories():
    for fn in ["newFvgCfg", "newFvgEngine", "newFvg15Engine", "newFvgAbsEngine", "newZoneCommonCfg",
               "newZoneEvtEngine"]:
        check(f"F1 factory {fn} verbatim", func_block(ORIG, fn) == func_block(NEW, fn) and func_block(NEW, fn) != "")


def fixture_consume_preview():
    for fn in ["consumeFvg15", "consumeFvgAbs", "consumeZoneEvt", "fvg15Preview"]:
        check(f"F4 {fn} verbatim", func_block(ORIG, fn) == func_block(NEW, fn) and func_block(NEW, fn) != "")

    # --- Python mirror of the copied consume source -------------------------
    def consume_fvg15(e, d):
        if d > 0:
            e["longConsumed"] = True
        elif d < 0:
            e["shortConsumed"] = True

    def consume_abs(e, which):
        if which == 5:
            e["ev5Consumed"] = e["ev5Id"]
        elif which == 15:
            e["ev15Consumed"] = e["ev15Id"]

    def consume_zone(e, kind):
        idx = [e["sigRebound"], e["sigFake"], e["sigRetest"], e["sigBreak"]][kind]
        if idx is not None and 0 <= idx < len(e["evts"]):
            q = e["evts"][idx]
            if kind == 0:
                q.update(reboundDone=True, alive=False)
            elif kind == 1:
                q.update(fakeDone=True, retestDone=True, alive=False)
            elif kind == 2:
                q.update(retestDone=True, alive=False)
            else:
                q.update(breakDone=True)

    def defaults(t):
        conv = {"true": True, "false": False, "na": None, "": None}
        out = {}
        for k, (_, d) in NT[t].items():
            if d in conv:
                out[k] = conv[d]
            else:
                try:
                    out[k] = int(d)
                except ValueError:
                    out[k] = d
        return out

    e = defaults("Fvg15Engine")
    consume_fvg15(e, 1)
    check("F4a consumeFvg15(+1): longConsumed only", e["longConsumed"] and not e["shortConsumed"], str(e))
    e = defaults("Fvg15Engine")
    consume_fvg15(e, -1)
    check("F4b consumeFvg15(-1): shortConsumed only", e["shortConsumed"] and not e["longConsumed"])

    a = defaults("FvgAbsEngine")
    a.update(ev5Id=101, ev15Id=202)
    consume_abs(a, 5)
    check("F4c consumeFvgAbs(5): ev5Consumed = ev5Id, ev15 untouched",
          a["ev5Consumed"] == 101 and a["ev15Consumed"] is None, str(a))
    consume_abs(a, 15)
    check("F4d consumeFvgAbs(15): ev15Consumed = ev15Id", a["ev15Consumed"] == 202)

    def zeng():
        z = defaults("ZoneEvtEngine")
        z["evts"] = [defaults("ZoneEvt") for _ in range(4)]
        z.update(sigRebound=0, sigFake=1, sigRetest=2, sigBreak=3)
        return z

    exp = {0: dict(reboundDone=True, alive=False), 1: dict(fakeDone=True, retestDone=True, alive=False),
           2: dict(retestDone=True, alive=False), 3: dict(breakDone=True, alive=True)}
    for kind, want in exp.items():
        z = zeng()
        consume_zone(z, kind)
        q = z["evts"][kind]
        others_untouched = all(z["evts"][k] == defaults("ZoneEvt") for k in range(4) if k != kind)
        check(f"F4z consumeZoneEvt(kind={kind}) state change", all(q[k] == v for k, v in want.items())
              and others_untouched, str({k: q[k] for k in want}))
    z = zeng()
    z["sigRebound"] = -1
    consume_zone(z, 0)
    check("F4z consumeZoneEvt with no signal index (-1): no-op",
          all(q == defaults("ZoneEvt") for q in z["evts"]))
    check("F4z ZoneEvtEngine sig* defaults are -1 (no signal)",
          all(defaults("ZoneEvtEngine")[k] == -1 for k in ("sigRebound", "sigFake", "sigRetest", "sigBreak")))


def fixture_preview_lifecycle_shared():
    pv = {
        "FvgSignal": ["previewLong", "previewShort"],
        "Fvg15Signal": ["previewGateLong", "previewGateShort"],
        "FvgAbsSignal": ["previewLong5", "previewLong15", "previewShort5", "previewShort15"],
        "ZoneLogicSignal": ["pvReboundLong", "pvReboundShort", "pvFakeLong", "pvFakeShort",
                            "pvRetestLong", "pvRetestShort", "pvBreakLong", "pvBreakShort"],
    }
    for t, fs in pv.items():
        check(f"F5 {t}: preview fields present", all(f in NT[t] for f in fs), ",".join(fs))
    confirmed = {
        "FvgSignal": ["longSignal", "shortSignal", "entryPrice", "noTriggerMode", "trendOk", "volOk",
                      "blockedByAccum", "blockedByAccumLong", "blockedByAccumShort", "blockedByExitWait",
                      "accumLongDirOk", "accumShortDirOk"],
        "Fvg15Signal": ["longSignal", "shortSignal", "entryPrice"],
        "FvgAbsSignal": ["long5", "long15", "short5", "short15", "entryPrice"],
        "ZoneLogicSignal": ["reboundLong", "reboundShort", "fakeLong", "fakeShort", "retestLong",
                            "retestShort", "breakLong", "breakShort", "entryPrice"],
    }
    for t, fs in confirmed.items():
        check(f"F5 {t}: confirmed + filter outputs present", all(f in NT[t] for f in fs))

    life = ["zoneId", "roleCycle", "top", "bottom", "strength", "score", "side", "startBar", "phase",
            "breakBar", "breakDir", "breakTime", "rearmBar", "touchBar", "reclaimBar", "rejectBar", "rejectTime",
            "movedAway", "reclaimed", "touched", "rejected", "fakeAlive", "bkOnly", "rbCancelled",
            "reboundDone", "breakDone", "fakeDone", "retestDone", "tfSec", "brkTfSec", "alive"]
    check("F6 ZoneEvt lifecycle + frozen geometry fields (trackId/top/bottom/side/strength/score)",
          all(f in NT["ZoneEvt"] for f in life), f"{len(life)} fields")

    shared = {
        "FvgEngine": ["lastTrigBar", "volRecoveryStartBar", "prevVolLow", "m15GateBias", "m15PrevReason",
                      "m15PrevRem", "drDayOpen", "drDayHigh", "drDayLow", "a5Hi", "a5Lo", "a5St", "a5BoxHi",
                      "a5BoxLo", "a5BoxSt", "a5Prev", "a15Hi", "a15Lo", "a15St", "a15LastSt",
                      "prevBlockedByAccum", "waitExitConfirm", "outsideConfirmCount", "breakDir",
                      "breakDirStartBar", "breakDirActive", "longArmed", "shortArmed"],
        "Fvg15Engine": ["prevReason", "prevRem", "longRebTime", "shortRebTime", "longConsumed", "shortConsumed",
                        "last5mBullT", "last5mBearT"],
        "FvgAbsEngine": ["ev5Id", "ev5Time", "ev5Consumed", "ev15Id", "ev15Time", "ev15Consumed",
                         "bos1mTime", "bos5mTime", "bos1mTimeS", "bos5mTimeS"],
        "ZoneEvtEngine": ["evts", "barNo", "prevClose", "sigRebound", "sigFake", "sigRetest", "sigBreak",
                          "roleZoneId", "roleSide", "roleCycleNo", "roleSeen", "roleSeenBar"],
        "FvgFeed": ["allowLong", "allowShort", "bullTrig", "bearTrig", "b5Bias", "b5Bos", "mRawBias",
                    "mRawReason", "mRawRem", "mRawBos", "accZnSupCtrs", "accZnResCtrs"],
        "ZoneCommonCfg": ["enableLong", "enableShort"],
        "ZoneEnvFeed": ["blockedByAccumLong", "blockedByAccumShort", "accumLongDirOk", "accumShortDirOk"],
    }
    for t, fs in shared.items():
        miss = [f for f in fs if f not in NT[t]]
        check(f"F7 {t}: Long/Short shared + both-direction state retained", not miss, f"missing={miss}" if miss
              else f"{len(fs)} fields")


def fixture_removed_dead():
    # Decision code of SignalEngine/21 = everything except type definitions.
    body = "\n".join(ln for ln in ORIG.split("\n") if not re.match(r"^\s+(bool|int|float|string|array<\w+>)\s+\w+", ln))
    for t, fs in REMOVED.items():
        bad = []
        for f in fs:
            if t in ("FvgCfg",):
                pat = r"\bc\." + f + r"\b"
            elif t == "FvgFeed":
                pat = r"\b(f|ef|zf|feed)\." + f + r"\b"
            elif t == "ZoneEnvFeed":
                # scope to functions whose `f` parameter is a ZoneEnvFeed (ZoneBosFeed also names it `f`)
                scoped = "\n".join(func_block(ORIG, n) for n in
                                   re.findall(r"^export (\w+)\([^)]*ZoneEnvFeed f", ORIG, re.M))
                if re.search(r"\bf\." + f + r"\b", scoped):
                    bad.append(f)
                continue
            else:  # Signal outputs: only ever written via Type.new(name = ...), never read as x.name
                pat = r"\b\w+\." + f + r"\b"
            if re.search(pat, body):
                bad.append(f)
        check(f"F8 {t}: removed fields are never read by SignalEngine/21 decision code", not bad,
              f"read={bad}" if bad else f"{len(fs)} removed")


def fixture_excluded():
    gone = ["ZoneBosCfg", "ZoneBosFeed", "ZoneBosEngine", "ZoneBosSignal", "updateZoneBos", "consumeZoneBos",
            "newZoneBosEngine", "newZoneBosCfg", "zoneBosEnvLong", "ZONESR", "efvgBiasText", "efvgReasonText",
            "efvgReboundDebugConfirmed", "efvgAbsDebugConfirmed", "bosBullLowerTf", "newZoneTfEnvCfg",
            "newZoneEnvSet", "updateEma", "FUTURE LOGICS"]
    code = "\n".join(ln for ln in NEW.split("\n") if not ln.lstrip().startswith("//"))
    present = [g for g in gone if g in code]
    check("F9 excluded items absent from code (ZONEBOS / ZONESR / debug / display / future)", not present,
          f"present={present}" if present else f"{len(gone)} checked")
    check("F9 no dbg* field anywhere", not re.search(r"\bdbg\w+", code))


def fixture_helpers():
    for fn in ["f_enabledTrigCount", "f_combineTrig", "f_reqCode", "dailyDirectionText", "dailyVolatilityText",
               "f_drDirCode"]:
        check(f"F10 helper {fn} verbatim", func_block(ORIG, fn) == func_block(NEW, fn) and func_block(NEW, fn) != "")


def fixture_alloc():
    allowed = set()
    for fn in ["newFvgEngine", "newZoneEvtEngine"]:
        allowed |= set(func_block(NEW, fn).split("\n"))
    stray = [ln.strip() for ln in NEW.split("\n")
             if "array.new" in ln and not ln.lstrip().startswith("//") and ln not in allowed]
    check("F11 array.new only inside factories (no per-bar allocation)", not stray, str(stray))


# =============================================================================
# P02 — Practical Zone Feed harness parity (static)
# =============================================================================
VIS = open(os.path.join(ROOT, "ZoneVisualPractical.pine"), encoding="utf-8").read()
MAIN = open(os.path.join(ROOT, "FvgZoneStrategy.pine"), encoding="utf-8").read()
HAR_PATH = os.path.join(ROOT, "PracticalZoneFeedHarness.pine")
HAR = open(HAR_PATH, encoding="utf-8").read() if os.path.exists(HAR_PATH) else ""
ZEP = open(os.path.join(ROOT, "ZoneEnginePractical.pine"), encoding="utf-8").read()

DISPLAY_GROUPS = {"G_DISP", "G_LBL", "G_FLT"}


def code_only(src):
    return "\n".join(ln for ln in src.split("\n") if not ln.lstrip().startswith("//"))


def logical_lines(src):
    """Join Pine continuation lines (indented, non-multiple-of-4 or starting after an open paren)."""
    out = []
    for ln in src.split("\n"):
        if out and ln.startswith("     ") and not ln.startswith("    if") and (len(ln) - len(ln.lstrip())) % 4 != 0:
            out[-1] += " " + ln.strip()
        else:
            out.append(ln)
    return out


def split_args(argstr):
    depth, cur, args, q = 0, "", [], None
    for ch in argstr:
        if q:
            cur += ch
            if ch == q:
                q = None
            continue
        if ch in "\"'":
            q = ch; cur += ch; continue
        if ch in "([":
            depth += 1
        if ch in ")]":
            if depth == 0:
                break
            depth -= 1
        if ch == "," and depth == 0:
            args.append(cur.strip()); cur = ""
            continue
        cur += ch
    if cur.strip():
        args.append(cur.strip())
    return args


def parse_inputs(src):
    res = {}
    for ln in logical_lines(src):
        m = re.match(r"^(\w+)\s*=\s*input\.(\w+)\((.*)$", ln)
        if not m:
            continue
        name, kind, rest = m.groups()
        args = split_args(rest)
        pos = [a for a in args if not re.match(r"^\w+\s*=", a)]
        kw = dict((a.split("=", 1)[0].strip(), a.split("=", 1)[1].strip()) for a in args if re.match(r"^\w+\s*=", a))
        res[name] = dict(kind=kind, default=pos[0] if pos else kw.get("defval"),
                         title=pos[1] if len(pos) > 1 else kw.get("title"),
                         group=kw.get("group"), options=kw.get("options"), minval=kw.get("minval"),
                         maxval=kw.get("maxval"), step=kw.get("step"))
    return res


def cfg_assigns(src):
    out = {}
    for ln in src.split("\n"):
        m = re.match(r"^\s*zoneCfg\.(\w+)\s*:=\s*(.+?)\s*$", ln)
        if m:
            out[m.group(1)] = m.group(2)
    return out


def section(src, start_pat, end_pat):
    a = re.search(start_pat, src, re.M).start()
    b = re.search(end_pat, src[a:], re.M).start() + a
    return src[a:b]


def fixture_p02():
    check("P02 harness file exists", bool(HAR))
    if not HAR:
        return
    VI, HI, MI = parse_inputs(VIS), parse_inputs(HAR), parse_inputs(MAIN)
    v_zone = {k: v for k, v in VI.items() if v["group"] not in DISPLAY_GROUPS}
    sltp_names = {k for k, v in MI.items() if v["group"] == "G_SLTP"}
    h_zone = {k: v for k, v in HI.items() if k not in sltp_names}
    diff = [k for k in set(v_zone) | set(h_zone) if v_zone.get(k) != h_zone.get(k)]
    check("Z1 Zone inputs == ZoneVisualPractical (name/kind/default/title/group/options/min/max/step), display excluded",
          not diff, f"{len(h_zone)} inputs" if not diff else f"diff={sorted(diff)}")
    dsl = [k for k in sltp_names if HI.get(k) != MI.get(k)]
    check("Z1 Structural SL/TP inputs == old Main (authority; absent from Visual)", not dsl and sltp_names,
          f"{len(sltp_names)} inputs" if not dsl else f"diff={dsl}")
    check("Z1 no display input in harness", not any(v["group"] in DISPLAY_GROUPS for v in HI.values()))

    vc, hc, mc = cfg_assigns(VIS), cfg_assigns(HAR), cfg_assigns(MAIN)
    m_sl = {k: v for k, v in mc.items() if k in ("slBuffer", "tpBuffer", "maxSlDist", "minStructRR", "slMinScore",
                                               "slMinStrength", "tpMinScore", "tpMinStrength", "obsMinStrength",
                                               "activeNoTradeMinStrength", "structuralTpDepthRatio", "fallbackRR")}
    exp = dict(vc); exp.update(m_sl)
    miss = sorted(set(exp) - set(hc)); extra = sorted(set(hc) - set(exp))
    chg = sorted(k for k in exp if k in hc and exp[k] != hc[k])
    check("Z2 ZoneCfg assignments == Visual (+ Main SL/TP): missing 0 / extra 0 / changed 0",
          not (miss or extra or chg), f"{len(hc)} fields" if not (miss or extra or chg) else f"{miss} {extra} {chg}")
    # every ZoneCfg field of the engine is either assigned or left at the library default intentionally
    zcfg = parse_types(ZEP)["ZoneCfg"]
    unassigned = sorted(set(zcfg) - set(hc))
    check("Z2 ZoneCfg fields not assigned by harness are not assigned by Visual/Main either (library default)",
          all(k not in vc and k not in mc for k in unassigned), f"unassigned={unassigned}")
    # first-bar-once equivalence: RHS only uses inputs (+ zn.strengthIdx / string compare)
    input_names = set(HI)
    bad_rhs = []
    for k, rhs in hc.items():
        ids = set(re.findall(r"\b[A-Za-z_]\w*\b", re.sub(r'"[^"]*"', "", rhs))) - {"zn", "strengthIdx"}
        if not ids <= input_names:
            bad_rhs.append((k, sorted(ids - input_names)))
    check("Z2 every ZoneCfg RHS is input-only (no series) -> first-bar assignment == Visual per-bar assignment",
          not bad_rhs, str(bad_rhs))
    lines = HAR.split("\n")
    i_if = next(i for i, ln in enumerate(lines) if ln.strip() == "if barstate.isfirst")
    inside = set()
    for ln in lines[i_if + 1:]:
        if ln and not ln.startswith("    "):
            break
        m = re.match(r"^\s+zoneCfg\.(\w+)\s*:=", ln)
        if m:
            inside.add(m.group(1))
    check("Z2 all ZoneCfg assignments are inside `if barstate.isfirst`", inside == set(hc), f"{len(inside)}/{len(hc)}")
    hco = code_only(HAR)
    check("Z2 ZoneCfg / ZoneEngine created once (var), no per-bar zn.newCfg / zn.newEngine",
          re.findall(r"^.*zn\.newCfg\(\).*$", hco, re.M) == ["var zn.ZoneCfg    zoneCfg = zn.newCfg()"] and
          re.findall(r"^.*zn\.newEngine\(\).*$", hco, re.M) == ["var zn.ZoneEngine zoneEng = zn.newEngine()"])

    vfeed = section(VIS, r"^// ---- 3\.2 Zone Engine Feed", r"^int zoneCountNow = zn\.update")
    hfeed = section(HAR, r"^// ---- 3\.2 Zone Engine Feed", r"^int zoneCountNow = zn\.update")
    check("Z3-Z6 feed block (MA / Swing / Accum / Break / trading day / ZoneFeed) verbatim == Visual",
          vfeed == hfeed, f"{len(hfeed.splitlines())} lines")

    def reqs(src):
        return [" ".join(x.split()) for x in re.findall(r"request\.security\((.*?lookahead\s*=\s*\w+\.\w+)\)",
                                                          code_only(src).replace("\n", " "))]
    hr, vr = reqs(hfeed), reqs(vfeed)
    check("Z3 request.security calls identical (symbol / TF / expression / lookahead)", hr == vr and len(hr) == 8,
          f"{len(hr)} call sites")
    for tag, pat in (("MA", r"maTf,\s*zn\.maPack"), ("Swing", r"hzTf\d, zn\.pivotPack"),
                     ("Accum", r"accTf\d,\s*zn\.accumPack"), ("Break", r"breakTf, \[close, high, low\]")):
        n = len([r for r in hr if re.search(pat, r)])
        want = {"MA": 1, "Swing": 3, "Accum": 3, "Break": 1}[tag]
        check(f"Z3 {tag}: {want} call site(s), lookahead_off, syminfo.tickerid",
              n == want and all("syminfo.tickerid" in r and "lookahead_off" in r for r in hr if re.search(pat, r)),
              f"{n}")
    gates = {"MA": r"^if useMaSource$", "Swing": r"^if useHzSource$", "Accum": r"^if useAccSource$"}
    for tag, g in gates.items():
        check(f"Z3 {tag} request only when source ON ({g[1:-1]})", re.search(g, hfeed, re.M) is not None)

    # ---- Z4 Break 3 paths ---------------------------------------------------
    brk = section(hfeed, r"^int   brTfSec", r"^// 取引日ID")
    same = section(brk, r"^if brSameTf", r"^else if brHtf")
    htf = section(brk, r"^else if brHtf", r"^else$")
    low = brk[re.search(r"^else$", brk, re.M).start():]
    check("Z4 TF == chart: no request, brClose/High/Low = close/high/low, brEval = barstate.isconfirmed",
          "request." not in same and re.search(r"if barstate\.isconfirmed\n\s+brClose := close\n\s+brHigh  := high\n"
                                                r"\s+brLow   := low\n\s+brEval  := true", same) is not None
          and "[1]" not in same)
    check("Z4 request.security only when Break TF != chart (`if not brSameTf`)",
          re.search(r"^if not brSameTf\n\s+\[_bc, _bh, _bl\] = request\.security", brk, re.M) is not None)
    check("Z4 TF > chart: evaluated once on the confirmed HTF-closing bar with the HTF values (no [1], no fallback)",
          "barstate.isconfirmed and brClosesNow" in htf and "brClose := brSrcC\n" in htf and "[1]" not in htf
          and "brDoneTfTime" not in brk)
    check("Z4 TF < chart: Visual legacy path kept ([1] on new period)", "brSrcC[1]" in low and "brNewPeriod" in low)

    # mirror of the 3 paths on synthetic bars
    def feed(path, bars):
        ev = []
        for i, b in enumerate(bars):
            if path == "same":
                if b["conf"]:
                    ev.append((i, b["c"]))
            elif path == "htf":
                if b["conf"] and b["closesHtf"]:
                    ev.append((i, b["htfC"]))
            else:
                if i > 0 and b["newPer"]:
                    ev.append((i, bars[i - 1]["c"]))
        return ev
    bars = [dict(c=4050 + i, conf=True, closesHtf=(i % 3 == 2), htfC=4050 + i, newPer=True) for i in range(6)]
    check("Z4m 5M/5M: each confirmed bar evaluates its own close (not close[1])",
          feed("same", bars) == [(i, 4050 + i) for i in range(6)], str(feed("same", bars)))
    rt = [dict(c=4071, conf=False, closesHtf=False, htfC=4071, newPer=False),
          dict(c=4068, conf=True, closesHtf=False, htfC=4068, newPer=False)]
    check("Z4m realtime unconfirmed tick: no evaluation; closing tick: its own close",
          feed("same", rt) == [(1, 4068)])
    check("Z4m 15M on 5M: once per HTF bar on its closing bar", feed("htf", bars) == [(2, 4052), (5, 4055)])

    # ---- Z5 trading day ------------------------------------------------------
    td = ["int _locY = year(time, dayTz)", "int _locM = month(time, dayTz)", "int _locD = dayofmonth(time, dayTz)",
          "int _locH = hour(time, dayTz)", "int _calDayNo    = int(timestamp(dayTz, _locY, _locM, _locD, 0, 0) / 86400000)",
          "int tradingDayId = _locH < dayResetHour ? _calDayNo - 1 : _calDayNo"]
    check("Z5 trading day (dayTz / dayResetHour / dayId) identical to Visual",
          all(t in hfeed and t in vfeed for t in td) and HI.get("dayTz") == VI.get("dayTz")
          and HI.get("dayResetHour") == VI.get("dayResetHour"))

    # ---- Z6 ZoneFeed mapping ------------------------------------------------
    def feed_map(src):
        m = re.search(r"zn\.ZoneFeed\.new\((.*?)\)\n", src, re.S)
        return dict((a.split("=")[0].strip(), a.split("=")[1].strip()) for a in split_args(" ".join(m.group(1).split())))
    hm, vm = feed_map(hfeed), feed_map(vfeed)
    zfeed_fields = set(parse_types(ZEP)["ZoneFeed"])
    check("Z6 ZoneFeed mapping identical to Visual and covers every ZoneFeed field",
          hm == vm and set(hm) == zfeed_fields, f"{len(hm)}/{len(zfeed_fields)} fields")

    # ---- Z7 / Z8 ---------------------------------------------------------------
    check("Z7 zn.update called exactly once", len(re.findall(r"\bzn\.update\(", hco)) == 1)
    check("Z7 exactly one ZoneEngine", len(re.findall(r"zn\.newEngine\(", hco)) == 1 and
          len(re.findall(r"\bzn\.ZoneEngine\b", hco)) == 1)
    prohibited = ["SignalEngine", "strategy.", "alert(", "box.new", "label.new", "table.new", "drawOrder",
                  "sourceText", "htfText", "line.new"]
    found = [p for p in prohibited if p in hco]
    check("Z8 prohibited tokens absent (SignalEngine / strategy.* / alert / box / label / table / drawOrder / text)",
          not found, str(found) if found else f"{len(prohibited)} checked")
    check("Z8 imports only ZoneEnginePractical/3",
          re.findall(r"^import .*$", hco, re.M) == ["import sekine3310/ZoneEnginePractical/3 as zn"])
    check("Z8 no array.new / touch scan in harness", "array." not in hco and "touchCount" not in hco)


if __name__ == "__main__":
    fixture_types()
    fixture_factories()
    fixture_consume_preview()
    fixture_preview_lifecycle_shared()
    fixture_removed_dead()
    fixture_excluded()
    fixture_helpers()
    fixture_alloc()
    fixture_p02()
    width = max(len(n) for n, _, _ in RESULTS)
    fails = 0
    for name, ok, detail in RESULTS:
        fails += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {name.ljust(width)}  {detail}")
    print(f"\n{len(RESULTS) - fails}/{len(RESULTS)} passed  [PINE_NOT_VERIFIED: static / mirror checks]")
    raise SystemExit(1 if fails else 0)
