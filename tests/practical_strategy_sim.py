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
import math

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
    NEW = open(os.path.join(ROOT, "SignalEnginePractical.pine"), encoding="utf-8").read()
    gone = ["ZoneBosCfg", "ZoneBosFeed", "ZoneBosEngine", "ZoneBosSignal", "updateZoneBos", "consumeZoneBos",
            "newZoneBosEngine", "newZoneBosCfg", "zoneBosEnvLong", "ZONESR", "efvgBiasText", "efvgReasonText",
            "efvgReboundDebugConfirmed", "efvgAbsDebugConfirmed", "bosBullLowerTf", "newZoneTfEnvCfg",
            "newZoneEnvSet", "updateEma", "FUTURE LOGICS"]
    code = "\n".join(ln for ln in NEW.split("\n") if not ln.lstrip().startswith("//"))
    present = [g for g in gone if g in code]
    check("F9 excluded items absent from code (ZONEBOS / ZONESR / debug / display / future)", not present,
          f"present={present}" if present else f"{len(gone)} checked")
    dbg_fields = [f for t in NT.values() for f in t if f.startswith("dbg")]
    dbg_args = re.findall(r"^\s+(dbg\w+)\s*=", "\n".join(
        b for b in re.findall(r"\w+\.new\((.*?)\)\n", code, re.S)), re.M)
    check("F9 no dbg* field in any type nor in any Type.new(...) argument", not dbg_fields and not dbg_args,
          f"fields={dbg_fields} args={dbg_args}")


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


# =============================================================================
# P03 — FVG / FVG15 port (static differential + behavioural mirror)
# =============================================================================
NEW = open(os.path.join(ROOT, "SignalEnginePractical.pine"), encoding="utf-8").read()   # re-read (P03 appended)
P03_FUNCS = ["calcTriggers", "envTrend", "envTrendConfirmed", "efvgReboundState", "efvgReboundConfirmed",
             "efvgRebound15Pack", "drDailyTuple", "f_accumNTDetect", "f_accumNT15", "accumNT15Confirmed",
             "dailyRangeMedian", "f_accZoneExcLong", "f_accZoneExcShort", "updateFvg", "updateFvg15"]


def expected_port(orig_block, tname, removed):
    """Independent re-implementation of the only allowed edit: drop removed named args from Type.new(...)."""
    out, inside = [], False
    for ln in orig_block.split("\n"):
        if re.match(r"^\s+" + tname + r"\.new\($", ln):
            inside = True
            out.append(ln)
            continue
        if inside:
            m = re.match(r"^\s+(\w+)\s*=", ln)
            closing = ln.rstrip().endswith(")")
            if not (m and m.group(1) in removed):
                out.append(ln)
            if closing:
                inside = False
                if not out[-1].rstrip().endswith(")"):
                    out[-1] = out[-1].rstrip().rstrip(",") + ")"
            continue
        out.append(ln)
    return "\n".join(out)


def state_writes(block):
    return re.findall(r"\b(e\.\w+)\s*(?::=|\+=)", block)


def field_reads(block):
    return sorted(set(re.findall(r"\b(?:e|c|f|tc|ac|ec)\.(\w+)\b", code_only(block))))


def fixture_p03_static():
    for fn in P03_FUNCS:
        o, n = func_block(ORIG, fn), func_block(NEW, fn)
        if fn == "updateFvg":
            exp = expected_port(o, "FvgSignal", REMOVED["FvgSignal"])
        elif fn == "updateFvg15":
            exp = expected_port(o, "Fvg15Signal", REMOVED["Fvg15Signal"])
        else:
            exp = o
        check(f"D1 {fn}: ported verbatim (only removed-field named args dropped)", n != "" and n == exp,
              f"{len(n.splitlines())} lines")
    for fn in ("updateFvg", "updateFvg15"):
        o, n = func_block(ORIG, fn), func_block(NEW, fn)
        check(f"D2 {fn}: state update order identical", state_writes(o) == state_writes(n),
              f"{len(state_writes(n))} writes")
        check(f"D2 {fn}: field reads identical (e/c/f/tc/ac)", field_reads(o) == field_reads(n),
              f"{len(field_reads(n))} fields")
        cond = lambda b: [ln.strip() for ln in b.split("\n") if re.match(r"^\s+(if|else if|else)\b", ln)]
        check(f"D2 {fn}: condition sequence identical", cond(o) == cond(n), f"{len(cond(n))} branches")
    # re-audit (spec 9): every field read by ported code exists in the kept types
    kept = {f for t in NT.values() for f in t}
    for fn in P03_FUNCS:
        miss = [f for f in field_reads(func_block(NEW, fn)) if f not in kept]
        check(f"D3 {fn}: every field it reads exists after P01 pruning (no field to restore)", not miss, str(miss))
    rets = re.findall(r"^\s+(\w+)\s*=", func_block(NEW, "updateFvg").split("FvgSignal.new(")[1], re.M)
    check("D4 updateFvg returns exactly the kept FvgSignal fields", sorted(rets) == sorted(NT["FvgSignal"]), str(rets))
    rets = re.findall(r"^\s+(\w+)\s*=", func_block(NEW, "updateFvg15").split("Fvg15Signal.new(")[1], re.M)
    check("D4 updateFvg15 returns exactly the kept Fvg15Signal fields", sorted(rets) == sorted(NT["Fvg15Signal"]))
    code = code_only(NEW)
    check("D5 no array.new outside factories after P03", all(
        ln.strip().startswith(("FvgEngine.new(", "a15Hi", "ZoneEvtEngine.new(", "roleZoneId", "roleCycleNo",
                               "roleSeenBar", "array.push(pool")) or "array.new" not in ln for ln in code.split("\n")))


# ---- Behavioural mirror of updateFvg (decision core, SignalEngine/21 L1314-1821) ----------------
# Inputs that Pine computes with ta.* (atr / sma / highest / box detection) are passed in as values.
class FCfg:
    def __init__(self, **kw):
        d = dict(useLowerTFTrigger=True, useTriggerCooldown=False, triggerCooldownBars=3,
                 useOppositeTriggerNoTrade=True, volMode="OFF", fixedMin=1.0, useMinVol=True, minAtrDollar=1.5,
                 volModeRel=False, volRatioMin=0.9, fastVolMode="固定値", fastAtrMin=2.2, fastFixedMin=10.0,
                 bodyAvgMin=0.5, useRangeRatioFilter=True, atrRangeRatioMin=0.06, useVolCooldown=False,
                 volRecoveryBars=2, useEnvFilter=True, reqTrend4H="上昇", reqTrend1H="上昇", reqTrend15M="上昇",
                 reqTrend5M="OFF", reqTrend1M="OFF", reqMatchCount=0, useDailyRegimeFilter=True,
                 dailyRegimeMode="当日進行中ベース", reqDailyDirection="OFF", reqDailyVolatility="低ボラ",
                 dailyLowVolThreshold=100.0, dailyHighVolThreshold=100.0, dailyDirectionBodyRatio=0.40,
                 dailyBullCloseLocation=0.65, dailyBearCloseLocation=0.35, dailyInsufficientAsRange=True,
                 useAccumNoTrade=True, useAccumNT5M=True, useAccumNT15M=True, accumNTKeep=1,
                 useAccumExitConfirm=False, accumExitConfirmBars=2, useAccumBreakDirection=True,
                 accumBreakDirectionBars=10, useAccumZoneException=False, useEFVGEnv=True,
                 efvgCombineMode="TrendAndFVG", useEFVGDaily=False, useEFVG4H=False, useEFVG1H=False,
                 useEFVG15M=False, useEFVG5M=True, useEFVG1M=False, efvgIntegrationMode="WeightedScore",
                 efvgReqMatch=3, efvgWeightD=6, efvgWeight4H=5, efvgWeight1H=4, efvgWeight15M=3, efvgWeight5M=2,
                 efvgWeight1M=1, efvgScoreThresh=1, efvgMode4Allow=False, useFvgBosFilter=True,
                 enabledTrig=0, triggerMode="Any", minTriggerCount=1)
        d.update(kw)
        self.__dict__.update(d)


def new_fvg_engine():
    return dict(lastTrigBar=None, volRecoveryStartBar=None, prevVolLow=False, m15GateBias=0, m15PrevReason=0,
                m15PrevRem=0, drDayOpen=None, drDayHigh=None, drDayLow=None, a5Hi=[], a5Lo=[], a5St=[],
                a5BoxHi=None, a5BoxLo=None, a5BoxSt=None, a5Prev=False, a15Hi=[], a15Lo=[], a15St=[],
                a15LastSt=None, prevBlockedByAccum=False, waitExitConfirm=False, outsideConfirmCount=0,
                breakDir=0, breakDirStartBar=None, breakDirActive=False, longArmed=True, shortArmed=True)


def req_code(s):
    return {"上昇": 1, "レンジ": 0, "下降": -1}.get(s)


def dr_dir_code(c, o, h, l, cl):
    if None in (o, h, l, cl) or h - l <= 0:
        return None
    rng = h - l
    br = abs(cl - o) / rng
    loc = (cl - l) / rng
    bull = cl > o and br >= c.dailyDirectionBodyRatio and loc >= c.dailyBullCloseLocation
    bear = cl < o and br >= c.dailyDirectionBodyRatio and loc <= c.dailyBearCloseLocation
    return 1 if bull and not bear else -1 if bear and not bull else 0


def dir_text(code):
    return {1: "上昇", -1: "下降", 0: "レンジ"}.get(code, "-")


def vol_text(code):
    return {1: "高ボラ", -1: "低ボラ", 0: "中ボラ"}.get(code, "-")


def update_fvg(e, c, f, bar, confirmed=True):
    """f: dict of per-bar inputs. Mirrors SignalEngine/21 updateFvg from L1314 onwards."""
    o, h, l, cl, cl1 = f["open"], f["high"], f["low"], f["close"], f.get("close1", f["close"])
    # triggers (lower-TF arrays or current-TF combined result)
    if c.useLowerTFTrigger:
        bull = any(f.get("bullTrig", []))
        bear = any(f.get("bearTrig", []))
    else:
        bull, bear = f.get("trigBullCur", False), f.get("trigBearCur", False)
    trigNoTrade = c.useOppositeTriggerNoTrade and (bull and bear)
    finalBull, finalBear = bull and not trigNoTrade, bear and not trigNoTrade
    cooldownOk = (not c.useTriggerCooldown) or e["lastTrigBar"] is None or (bar - e["lastTrigBar"]) > c.triggerCooldownBars
    if (finalBull or finalBear) and cooldownOk:
        e["lastTrigBar"] = bar
    # vol
    baseVolOk = True
    if c.volMode == "ATR":
        base, avg = f["baseAtr"], f["atrAvg"]
        absOk, relOk = base >= c.minAtrDollar, avg > 0 and base >= avg * c.volRatioMin
        baseVolOk = (not c.useMinVol) or (relOk if c.volModeRel else absOk)
    elif c.volMode == "固定値":
        baseVolOk = (h - l) >= c.fixedMin
    fastPass = True
    if c.fastVolMode == "ATR":
        rw = f["rangeWidth"]
        ratio = f["fastAtr"] / rw if rw > 0 else 0.0
        fastPass = f["fastAtr"] >= c.fastAtrMin and f["bodyAvg"] >= c.bodyAvgMin and \
            ((not c.useRangeRatioFilter) or ratio >= c.atrRangeRatioMin)
    elif c.fastVolMode == "固定値":
        fastPass = f["fastRange"] >= c.fastFixedMin and f["bodyAvg"] >= c.bodyAvgMin
    volLow = not (baseVolOk and fastPass)
    if volLow:
        e["volRecoveryStartBar"] = None
    if (not volLow) and e["prevVolLow"]:
        e["volRecoveryStartBar"] = bar
    recOk = (not c.useVolCooldown) or e["volRecoveryStartBar"] is None or (bar - e["volRecoveryStartBar"]) >= c.volRecoveryBars
    volOk = (baseVolOk and fastPass) and recOk
    # env
    allowEnv = True
    if c.useEnvFilter:
        en = [(c.reqTrend4H, f.get("env4H")), (c.reqTrend1H, f.get("env1H")), (c.reqTrend15M, f.get("env15M")),
              (c.reqTrend5M, f.get("env5M")), (c.reqTrend1M, f.get("env1M"))]
        enabled = sum(1 for r, _ in en if r != "OFF")
        matched = sum(1 for r, v in en if r != "OFF" and v is not None and v == req_code(r))
        need = enabled if c.reqMatchCount == 0 else c.reqMatchCount
        allowEnv = enabled == 0 or matched >= need
    # EFVG with 15M gate
    mBias = 0
    if c.useEFVGEnv and c.useEFVG15M:
        b, r, rem = f.get("mRawBias", 0), f.get("mRawReason", 0), f.get("mRawRem", 0)
        if r != 0 and (r != e["m15PrevReason"] or rem > e["m15PrevRem"]):
            aL = (not c.useFvgBosFilter) or f.get("b5Bos", 0) != -1
            aS = (not c.useFvgBosFilter) or f.get("b5Bos", 0) != 1
            e["m15GateBias"] = (1 if aL else 0) if r == 1 else (-1 if aS else 0) if r == -1 else 0
        if b == 0:
            e["m15GateBias"] = 0
        if c.useFvgBosFilter:
            if e["m15GateBias"] == 1 and f.get("b5Bos", 0) == -1:
                e["m15GateBias"] = 0
            if e["m15GateBias"] == -1 and f.get("b5Bos", 0) == 1:
                e["m15GateBias"] = 0
        e["m15PrevReason"], e["m15PrevRem"] = r, rem
        mBias = e["m15GateBias"]
    tfs = [(c.useEFVGDaily, f.get("dBias", 0), c.efvgWeightD), (c.useEFVG4H, f.get("hBias", 0), c.efvgWeight4H),
           (c.useEFVG1H, f.get("oBias", 0), c.efvgWeight1H), (c.useEFVG15M, mBias, c.efvgWeight15M),
           (c.useEFVG5M, f.get("b5Bias", 0), c.efvgWeight5M), (c.useEFVG1M, f.get("b1Bias", 0), c.efvgWeight1M)]
    encnt = sum(1 for u, _, _ in tfs if u)
    allL = encnt > 0 and all((not u) or bb == 1 for u, bb, _ in tfs)
    allS = encnt > 0 and all((not u) or bb == -1 for u, bb, _ in tfs)
    cntL = sum(1 for u, bb, _ in tfs if u and bb == 1) >= c.efvgReqMatch
    cntS = sum(1 for u, bb, _ in tfs if u and bb == -1) >= c.efvgReqMatch
    score = sum(w * bb for u, bb, w in tfs if u)
    scL, scS = score >= c.efvgScoreThresh, score <= -c.efvgScoreThresh
    htf = sum(w * bb for u, bb, w in tfs[:2] if u)
    htfDir = 1 if htf > 0 else -1 if htf < 0 else 0
    loL = any(u and bb == -1 for u, bb, _ in tfs[2:])
    loS = any(u and bb == 1 for u, bb, _ in tfs[2:])
    htL = htfDir == 1 and (c.efvgMode4Allow or not loL)
    htS = htfDir == -1 and (c.efvgMode4Allow or not loS)
    pick = {"AllAgree": (allL, allS), "MatchCount": (cntL, cntS), "WeightedScore": (scL, scS)}
    biasL, biasS = pick.get(c.efvgIntegrationMode, (htL, htS))
    trendOk = (not c.useEnvFilter) or allowEnv

    def comb(bias):
        if not c.useEFVGEnv:
            return trendOk
        return {"TrendOnly": trendOk, "FVGOnly": bias, "TrendAndFVG": trendOk and bias}.get(c.efvgCombineMode,
                                                                                            trendOk or bias)
    envL, envS = comb(biasL), comb(biasS)
    # daily regime
    drOk = True
    if c.useDailyRegimeFilter:
        if f.get("drNewDay") or e["drDayHigh"] is None:
            e["drDayOpen"], e["drDayHigh"], e["drDayLow"] = o, h, l
        else:
            e["drDayHigh"], e["drDayLow"] = max(e["drDayHigh"], h), min(e["drDayLow"], l)
        if c.dailyRegimeMode == "前日確定ベース":
            q = f["dr1"]
        elif c.dailyRegimeMode == "当日進行中ベース":
            q = (e["drDayOpen"], e["drDayHigh"], e["drDayLow"], cl)
        else:
            q = f["dr0"]
        dcode = dr_dir_code(c, *q)
        dIns = dcode is None
        dAdj = (0 if c.dailyInsufficientAsRange else None) if dIns else dcode
        med = f.get("drMedianRange")
        vcode = None if med is None else (1 if med >= c.dailyHighVolThreshold else -1 if med < c.dailyLowVolThreshold else 0)
        vIns = vcode is None
        vAdj = (0 if c.dailyInsufficientAsRange else None) if vIns else vcode
        dm = c.reqDailyDirection == "OFF" or dir_text(dAdj) == c.reqDailyDirection
        vm = c.reqDailyVolatility == "OFF" or vol_text(vAdj) == c.reqDailyVolatility
        db = c.reqDailyDirection != "OFF" and dIns and not c.dailyInsufficientAsRange
        vb = c.reqDailyVolatility != "OFF" and vIns and not c.dailyInsufficientAsRange
        drOk = dm and vm and not db and not vb
    drL = drS = True
    if c.dailyRegimeMode in ("前日確定ベース", "当日進行中ベース"):
        drL = drS = drOk
    # accum (5M box detection inputs isA5/hi5/lo5 come from f_accumNTDetect)
    in5 = in15 = False
    if c.useAccumNoTrade and c.useAccumNT5M:
        isA5 = f.get("isA5", False)
        start5 = isA5 and not e["a5Prev"]
        e["a5Prev"] = isA5
        if start5:
            e["a5BoxHi"], e["a5BoxLo"], e["a5BoxSt"] = f["hi5"], f["lo5"], bar
            e["a5Hi"].append(e["a5BoxHi"]); e["a5Lo"].append(e["a5BoxLo"]); e["a5St"].append(bar)
            while len(e["a5St"]) > c.accumNTKeep:
                e["a5Hi"].pop(0); e["a5Lo"].pop(0); e["a5St"].pop(0)
        if isA5:
            bt, bb_ = max(o, cl), min(o, cl)
            e["a5BoxHi"] = max(e["a5BoxHi"] if e["a5BoxHi"] is not None else bt, bt)
            e["a5BoxLo"] = min(e["a5BoxLo"] if e["a5BoxLo"] is not None else bb_, bb_)
            if e["a5St"]:
                e["a5Hi"][-1], e["a5Lo"][-1] = e["a5BoxHi"], e["a5BoxLo"]
        in5 = any(lo_ <= cl <= hi_ for hi_, lo_ in zip(e["a5Hi"], e["a5Lo"]))
    if c.useAccumNoTrade and c.useAccumNT15M:
        if f.get("new15Bar"):
            st = f.get("acc15St")
            if st is not None and st != e["a15LastSt"]:
                e["a15Hi"].append(f["acc15Hi"]); e["a15Lo"].append(f["acc15Lo"]); e["a15St"].append(st)
                e["a15LastSt"] = st
                while len(e["a15St"]) > c.accumNTKeep:
                    e["a15Hi"].pop(0); e["a15Lo"].pop(0); e["a15St"].pop(0)
            elif e["a15St"] and st is not None and st == e["a15LastSt"]:
                e["a15Hi"][-1], e["a15Lo"][-1] = f["acc15Hi"], f["acc15Lo"]
        in15 = any(lo_ <= cl <= hi_ for hi_, lo_ in zip(e["a15Hi"], e["a15Lo"]))
    blocked = c.useAccumNoTrade and ((c.useAccumNT5M and in5) or (c.useAccumNT15M and in15))
    blockedL = blockedS = blocked            # useAccumZoneException = false
    exited = c.useAccumNoTrade and e["prevBlockedByAccum"] and not blocked
    if (not c.useAccumNoTrade) or (not c.useAccumExitConfirm):
        e["waitExitConfirm"], e["outsideConfirmCount"] = False, 0
    else:
        if blocked:
            e["waitExitConfirm"], e["outsideConfirmCount"] = False, 0
        elif exited:
            e["waitExitConfirm"], e["outsideConfirmCount"] = True, 0
        elif e["waitExitConfirm"]:
            e["outsideConfirmCount"] += 1
        if e["waitExitConfirm"] and e["outsideConfirmCount"] >= c.accumExitConfirmBars:
            e["waitExitConfirm"] = False
    exitWait = c.useAccumNoTrade and c.useAccumExitConfirm and e["waitExitConfirm"]
    if (not c.useAccumNoTrade) or (not c.useAccumBreakDirection):
        e["breakDir"], e["breakDirStartBar"], e["breakDirActive"] = 0, None, False
    else:
        if blocked:
            e["breakDir"], e["breakDirStartBar"], e["breakDirActive"] = 0, None, False
        elif exited:
            up = down = False
            boxes = (list(zip(e["a5Hi"], e["a5Lo"])) if c.useAccumNT5M else []) + \
                    (list(zip(e["a15Hi"], e["a15Lo"])) if c.useAccumNT15M else [])
            for bh, bl in boxes:
                was = bl <= cl1 <= bh
                up |= was and cl > bh
                down |= was and cl < bl
            if up and not down:
                e["breakDir"], e["breakDirStartBar"], e["breakDirActive"] = 1, bar, True
            elif down and not up:
                e["breakDir"], e["breakDirStartBar"], e["breakDirActive"] = -1, bar, True
            else:
                e["breakDir"], e["breakDirStartBar"], e["breakDirActive"] = 0, None, False
        if e["breakDirActive"] and e["breakDirStartBar"] is not None and bar - e["breakDirStartBar"] > c.accumBreakDirectionBars:
            e["breakDir"], e["breakDirStartBar"], e["breakDirActive"] = 0, None, False
    dirL = (not c.useAccumNoTrade) or (not c.useAccumBreakDirection) or (not e["breakDirActive"]) or e["breakDir"] == 1
    dirS = (not c.useAccumNoTrade) or (not c.useAccumBreakDirection) or (not e["breakDirActive"]) or e["breakDir"] == -1
    majL = drL and f.get("sessionOk", True) and f.get("newsOk", True) and envL and volOk and not blockedL and not exitWait and dirL
    majS = drS and f.get("sessionOk", True) and f.get("newsOk", True) and envS and volOk and not blockedS and not exitWait and dirS
    baseL = confirmed and f["allowLong"] and majL
    baseS = confirmed and f["allowShort"] and majS
    noTrig = c.enabledTrig == 0
    if not majL:
        e["longArmed"] = True
    if not majS:
        e["shortArmed"] = True
    rawL = (baseL and e["longArmed"]) if noTrig else (baseL and finalBull and cooldownOk)
    rawS = (baseS and e["shortArmed"]) if noTrig else (baseS and finalBear and cooldownOk)
    sigL, sigS = rawL, rawS
    if sigL and sigS:
        if cl >= o:
            sigS = False
        else:
            sigL = False
    pvBL, pvBS = f["allowLong"] and majL, f["allowShort"] and majS
    pvL = (pvBL and e["longArmed"]) if noTrig else (pvBL and finalBull and cooldownOk)
    pvS = (pvBS and e["shortArmed"]) if noTrig else (pvBS and finalBear and cooldownOk)
    if pvL and pvS:
        if cl >= o:
            pvS = False
        else:
            pvL = False
    e["prevVolLow"], e["prevBlockedByAccum"] = volLow, blocked
    return dict(longSignal=sigL, shortSignal=sigS, previewLong=pvL, previewShort=pvS, noTriggerMode=noTrig,
                trendOk=trendOk, volOk=volOk, blockedByAccum=blocked, blockedByExitWait=exitWait,
                accumLongDirOk=dirL, accumShortDirOk=dirS, cooldownOk=cooldownOk, score=score, mBias=mBias,
                envL=envL, envS=envS, drOk=drOk)


def bar_in(**kw):
    d = dict(open=4050.0, high=4056.0, low=4049.0, close=4055.0, close1=4050.0, allowLong=True, allowShort=False,
             env4H=1, env1H=1, env15M=1, b5Bias=1, b5Bos=0, drMedianRange=50.0, fastRange=12.0, bodyAvg=1.0)
    d.update(kw)
    return d


def fixture_p03_behaviour():
    # FVG1 Trigger OFF: noTriggerMode, armed edge, preview
    c, e = FCfg(), new_fvg_engine()
    r1 = update_fvg(e, c, bar_in(), 1)
    e["longArmed"] = False                      # Main disarms after a real entry
    r2 = update_fvg(e, c, bar_in(), 2)          # still majorOk -> no new signal while disarmed
    r3 = update_fvg(e, c, bar_in(env4H=0), 3)   # majorOk false -> re-arm
    r4 = update_fvg(e, c, bar_in(), 4)          # rising edge -> signal again
    check("FVG1 Trigger OFF: noTriggerMode, signal, disarm after entry, re-arm when major condition drops",
          r1["noTriggerMode"] and r1["longSignal"] and not r2["longSignal"] and not r3["longSignal"] and r4["longSignal"],
          f"{[r['longSignal'] for r in (r1, r2, r3, r4)]}")
    rp = update_fvg(new_fvg_engine(), c, bar_in(), 1, confirmed=False)
    check("FVG1 preview = confirmed condition without barstate.isconfirmed", rp["previewLong"] and not rp["longSignal"])

    # FVG2 Trigger ON: cooldown, opposite trigger block, preview
    c = FCfg(enabledTrig=1, useTriggerCooldown=True, triggerCooldownBars=3)
    e = new_fvg_engine()
    a = update_fvg(e, c, bar_in(bullTrig=[True]), 10)
    b = update_fvg(e, c, bar_in(bullTrig=[True]), 12)    # within cooldown
    d = update_fvg(e, c, bar_in(bullTrig=[True]), 14)    # 14-10 = 4 > 3 -> ok
    check("FVG2 trigger cooldown (shared lastTrigBar)", a["longSignal"] and not b["longSignal"] and d["longSignal"],
          f"{a['longSignal']},{b['longSignal']},{d['longSignal']}")
    e = new_fvg_engine()
    update_fvg(e, c, bar_in(bearTrig=[True]), 20)         # Short trigger only (Short disallowed) still sets lastTrigBar
    x = update_fvg(e, c, bar_in(bullTrig=[True]), 21)
    check("FVG2 Short-only trigger blocks Long via shared cooldown (direction coupling kept)", not x["longSignal"])
    e = new_fvg_engine()
    y = update_fvg(e, c, bar_in(bullTrig=[True], bearTrig=[True]), 30)
    check("FVG2 opposite trigger NoTrade (bull and bear in same bar)", not y["longSignal"] and not y["previewLong"])
    e = new_fvg_engine()
    z = update_fvg(e, c, bar_in(bullTrig=[True]), 40, confirmed=False)
    check("FVG2 preview with trigger", z["previewLong"] and not z["longSignal"])

    # FVG3 Vol: pass / low / recovery
    c = FCfg(useVolCooldown=True, volRecoveryBars=2)
    e = new_fvg_engine()
    v1 = update_fvg(e, c, bar_in(fastRange=12.0), 1)
    v2 = update_fvg(e, c, bar_in(fastRange=5.0), 2)
    v3 = update_fvg(e, c, bar_in(fastRange=12.0), 3)
    v4 = update_fvg(e, c, bar_in(fastRange=12.0), 4)
    v5 = update_fvg(e, c, bar_in(fastRange=12.0), 5)
    check("FVG3 vol pass / low / recovery wait (2 bars)",
          [v["volOk"] for v in (v1, v2, v3, v4, v5)] == [True, False, False, False, True],
          str([v["volOk"] for v in (v1, v2, v3, v4, v5)]))

    # FVG4 Trend combinations
    combos = [(dict(), True), (dict(env1H=0), False), (dict(env15M=-1), False), (dict(env4H=None), False)]
    res = [update_fvg(new_fvg_engine(), FCfg(), bar_in(**kw), 1)["trendOk"] == exp for kw, exp in combos]
    c2 = FCfg(reqTrend5M="上昇", reqTrend1M="下降", reqMatchCount=4)
    r = update_fvg(new_fvg_engine(), c2, bar_in(env5M=1, env1M=1), 1)["trendOk"]          # 4 of 5 match
    r_ = update_fvg(new_fvg_engine(), c2, bar_in(env5M=0, env1M=1), 1)["trendOk"]         # 3 of 5
    check("FVG4 trend 4H/1H/15M/5M/1M match + reqMatchCount", all(res) and r and not r_, f"{res},{r},{r_}")

    # FVG5 Daily regime
    c = FCfg(reqDailyVolatility="低ボラ", dailyLowVolThreshold=100.0, dailyHighVolThreshold=100.0)
    lo = update_fvg(new_fvg_engine(), c, bar_in(drMedianRange=50.0), 1)["drOk"]
    hi = update_fvg(new_fvg_engine(), c, bar_in(drMedianRange=150.0), 1)["drOk"]
    ins = update_fvg(new_fvg_engine(), c, bar_in(drMedianRange=None), 1)["drOk"]          # insufficient -> 中ボラ
    c3 = FCfg(reqDailyVolatility="低ボラ", dailyInsufficientAsRange=False)
    ins2 = update_fvg(new_fvg_engine(), c3, bar_in(drMedianRange=None), 1)["drOk"]
    c4 = FCfg(reqDailyVolatility="OFF", reqDailyDirection="上昇", dailyRegimeMode="前日確定ベース")
    d_up = update_fvg(new_fvg_engine(), c4, bar_in(dr1=(4000, 4100, 3990, 4095)), 1)["drOk"]
    d_dn = update_fvg(new_fvg_engine(), c4, bar_in(dr1=(4100, 4110, 4000, 4005)), 1)["drOk"]
    check("FVG5 daily volatility (low / high / insufficient as range / insufficient block) + direction",
          lo and not hi and not ins and not ins2 and d_up and not d_dn, f"{lo},{hi},{ins},{ins2},{d_up},{d_dn}")

    # FVG6 Accum: inside -> blocked, exit wait, break direction
    c = FCfg(useAccumExitConfirm=True, accumExitConfirmBars=2, useAccumNT15M=False)
    e = new_fvg_engine()
    s1 = update_fvg(e, c, bar_in(isA5=True, hi5=4060.0, lo5=4040.0, open=4050, close=4052, close1=4050), 1)
    s2 = update_fvg(e, c, bar_in(isA5=False, open=4052, close=4070, close1=4052), 2)     # exits upward
    s3 = update_fvg(e, c, bar_in(isA5=False, open=4070, close=4072, close1=4070), 3)
    s4 = update_fvg(e, c, bar_in(isA5=False, open=4072, close=4074, close1=4072), 4)
    check("FVG6 inside accum -> blocked; exit -> exit-wait 2 bars; break direction up -> Long ok / Short blocked",
          s1["blockedByAccum"] and not s1["longSignal"] and s2["blockedByExitWait"] and s3["blockedByExitWait"]
          and not s4["blockedByExitWait"] and s2["accumLongDirOk"] and not s2["accumShortDirOk"],
          f"blk={s1['blockedByAccum']} wait={[s['blockedByExitWait'] for s in (s2, s3, s4)]} dir={s2['accumLongDirOk']},{s2['accumShortDirOk']}")

    # FVG7 EFVG: bias / score / match / 15M BOS gate
    w = update_fvg(new_fvg_engine(), FCfg(), bar_in(b5Bias=-1), 1)
    check("FVG7 weighted score (5M bias -1 -> score -2 -> Long env false)", w["score"] == -2 and not w["envL"])
    cm = FCfg(efvgIntegrationMode="MatchCount", efvgReqMatch=2, useEFVG1H=True)
    m1 = update_fvg(new_fvg_engine(), cm, bar_in(b5Bias=1, oBias=1), 1)["envL"]
    m0 = update_fvg(new_fvg_engine(), cm, bar_in(b5Bias=1, oBias=0), 1)["envL"]
    cg = FCfg(useEFVG15M=True, useEFVG5M=False)
    e = new_fvg_engine()
    g1 = update_fvg(e, cg, bar_in(mRawBias=1, mRawReason=1, mRawRem=5, b5Bos=-1), 1)    # new event blocked by bearish 5M BOS
    g2 = update_fvg(e, cg, bar_in(mRawBias=1, mRawReason=1, mRawRem=6, b5Bos=0), 2)     # new event (rem up) allowed
    g3 = update_fvg(e, cg, bar_in(mRawBias=1, mRawReason=1, mRawRem=6, b5Bos=-1), 3)    # gate cleared by opposite BOS
    check("FVG7 match count + 15M gate (new event / BOS filter / clear on opposite BOS)",
          m1 and not m0 and g1["mBias"] == 0 and g2["mBias"] == 1 and g3["mBias"] == 0,
          f"{m1},{m0},{g1['mBias']},{g2['mBias']},{g3['mBias']}")

    # FVG8 Armed (Long and Short independent) + tie-break only when both allowed
    e = new_fvg_engine()
    r = update_fvg(e, FCfg(), bar_in(allowShort=True, env4H=1, b5Bias=1), 1)
    check("FVG8 armed flags independent per direction; Short not affecting Long when Short env fails",
          r["longSignal"] and not r["shortSignal"] and e["longArmed"] and e["shortArmed"])
    cboth = FCfg(useEFVGEnv=False, useEnvFilter=False)
    tie = update_fvg(new_fvg_engine(), cboth, bar_in(allowShort=True, open=4055, close=4050), 1)
    check("FVG8 simultaneous Long+Short tie-break by candle colour (only with both directions allowed)",
          tie["shortSignal"] and not tie["longSignal"])


# ---- updateFvg15 mirror (SignalEngine/21 L1915-1971) -------------------------
def new_f15():
    return dict(longRebTime=None, shortRebTime=None, longConsumed=False, shortConsumed=False, prevReason=0,
                prevRem=0, last5mBullT=None, last5mBearT=None)


def update_fvg15(e, baseL, baseS, reason, rem, rebT, useOrder, close, bos5Hi, bos5Lo, t, confirmed=True):
    newL = reason == 1 and (reason != e["prevReason"] or rem > e["prevRem"])
    newS = reason == -1 and (reason != e["prevReason"] or rem > e["prevRem"])
    if newL:
        e["longRebTime"], e["longConsumed"] = rebT, False
    if newS:
        e["shortRebTime"], e["shortConsumed"] = rebT, False
    e["prevReason"], e["prevRem"] = reason, rem
    if confirmed:
        if close > bos5Hi:
            e["last5mBullT"] = t
        if close < bos5Lo:
            e["last5mBearT"] = t
    okL = e["last5mBullT"] is not None and e["longRebTime"] is not None and e["last5mBullT"] >= e["longRebTime"]
    gateL = (not useOrder) or (okL and not e["longConsumed"])
    pvT = t if close > bos5Hi else e["last5mBullT"]
    pvOk = pvT is not None and e["longRebTime"] is not None and pvT >= e["longRebTime"]
    pvGateL = (not useOrder) or (pvOk and not e["longConsumed"])
    return dict(longSignal=baseL and gateL, previewGateLong=pvGateL)


def fixture_p03_fvg15():
    e = new_f15()
    update_fvg15(e, False, False, 0, 0, None, True, 4050, 4060, 4040, 100)
    r = update_fvg15(e, False, False, 1, 3, 1000, True, 4050, 4060, 4040, 1100)
    check("F15-1 rebound event: reason 1 -> longRebTime = rebound 15M bar open, consumed reset",
          e["longRebTime"] == 1000 and not e["longConsumed"])
    e = new_f15()
    update_fvg15(e, True, False, 0, 0, None, True, 4065, 4060, 4040, 900)       # BOS at t=900 (before event)
    r1 = update_fvg15(e, True, False, 1, 3, 1000, True, 4050, 4060, 4040, 1100)
    r2 = update_fvg15(e, True, False, 1, 3, 1000, True, 4066, 4060, 4040, 1200)  # BOS after event
    check("F15-2 BOS before event -> no signal; BOS after event -> signal", not r1["longSignal"] and r2["longSignal"])
    c_ok = r2["longSignal"]
    e["longConsumed"] = True                                                       # consumeFvg15(+1) after real entry
    r3 = update_fvg15(e, True, False, 1, 3, 1000, True, 4067, 4060, 4040, 1300)
    r4 = update_fvg15(e, True, False, 1, 4, 1250, True, 4068, 4060, 4040, 1400)  # new event (rem up) re-arms
    e2 = new_f15()
    update_fvg15(e2, True, False, 1, 3, 1000, True, 4066, 4060, 4040, 1200)       # signal, but TradePlan FAIL -> no consume
    r5 = update_fvg15(e2, True, False, 1, 3, 1000, True, 4066, 4060, 4040, 1300)
    check("F15-3 consume only on real entry: consumed blocks; new event re-arms; FAIL (no consume) keeps signal",
          c_ok and not r3["longSignal"] and r4["longSignal"] and r5["longSignal"])
    e = new_f15()
    update_fvg15(e, True, False, 1, 3, 1000, True, 4050, 4060, 4040, 1100)
    pv = update_fvg15(e, True, False, 1, 3, 1000, True, 4066, 4060, 4040, 1200, confirmed=False)
    check("F15-4 preview: forming 5M bar counts as BOS without writing state; confirmed gate stays false",
          pv["previewGateLong"] and not pv["longSignal"] and e["last5mBullT"] is None)


# =============================================================================
# P04 — FVGABS5 / FVGABS15 port (static differential + behavioural mirror)
# =============================================================================
P04_FUNCS = ["efvgAbsState", "efvgAbsConfirmed", "bosPack", "updateFvgAbs", "fvgAbsEnvLong", "fvgAbsEnvShort",
             "consumeFvgAbs"]


def expected_port_multi(orig_block, tname, removed):
    """Independent re-derivation of the allowed edit for constructors with several args per line."""
    text = orig_block
    m = re.search(tname + r"\.new\((.*)\)\s*$", text, re.S)
    args_src = m.group(1)
    kept_lines = []
    for ln in args_src.split("\n"):
        parts = [a.strip() for a in ln.split(",") if a.strip()]
        parts = [a for a in parts if a.split("=")[0].strip() not in removed]
        if parts:
            kept_lines.append((ln[:len(ln) - len(ln.lstrip())], parts))
    rebuilt = []
    for i, (ind, parts) in enumerate(kept_lines):
        rebuilt.append((ind if i else "") + ", ".join(parts) + ("," if i < len(kept_lines) - 1 else ")"))
    return text[:m.start()] + tname + ".new(" + "\n".join(rebuilt)


def fixture_p04_static():
    NEWS = open(os.path.join(ROOT, "SignalEnginePractical.pine"), encoding="utf-8").read()
    for fn in P04_FUNCS:
        o, n = func_block(ORIG, fn), func_block(NEWS, fn)
        exp = expected_port_multi(o, "FvgAbsSignal", REMOVED["FvgAbsSignal"]) if fn == "updateFvgAbs" else o
        check(f"A-D1 {fn}: ported verbatim (only removed-field named args dropped)", n != "" and n == exp,
              f"{len(n.splitlines())} lines")
    o, n = func_block(ORIG, "updateFvgAbs"), func_block(NEWS, "updateFvgAbs")
    check("A-D2 updateFvgAbs: state write order identical", state_writes(o) == state_writes(n),
          " / ".join(state_writes(n)))
    check("A-D2 updateFvgAbs: field reads identical", field_reads(o) == field_reads(n), f"{len(field_reads(n))} fields")
    cond = lambda b: [ln.strip() for ln in code_only(b).split("\n") if re.match(r"^\s+(if|else if|else)\b", ln)]
    check("A-D2 updateFvgAbs: if-condition sequence identical", cond(o) == cond(n), f"{len(cond(n))} branches")
    cmp_ = lambda b: re.findall(r"e\.\w+\s*>=\s*e\.\w+|pvBos5mTimeS?\s*>=\s*e\.\w+", b)
    check("A-D2 updateFvgAbs: event-time comparisons identical (BOS time >= event time)",
          cmp_(o) == cmp_(n) and len(cmp_(n)) == 6, " | ".join(cmp_(n)))
    for fn in ("efvgAbsState", "updateFvgAbs"):
        o2, n2 = func_block(ORIG, fn), func_block(NEWS, fn)
        vw = lambda b: re.findall(r"^\s+(_\w+)\s*:=", b, re.M)
        check(f"A-D2 {fn}: var/local state update order identical", vw(o2) == vw(n2))
    kept = {f for t in NT.values() for f in t}
    miss = [f for f in field_reads(func_block(NEWS, "updateFvgAbs")) if f not in kept]
    check("A-D3 re-audit FvgAbsEngine/FvgAbsSignal/FvgFeed/FvgCfg: no removed field is read (nothing to restore)",
          not miss, str(miss))
    rets = re.findall(r"(\w+)\s*=\s*[\w.]+", func_block(NEWS, "updateFvgAbs").split("FvgAbsSignal.new(")[1])
    check("A-D4 updateFvgAbs returns exactly the kept FvgAbsSignal fields", sorted(rets) == sorted(NT["FvgAbsSignal"]),
          str(rets))
    for fn in ("efvgAbsDebugConfirmed", "bosBullLowerTf"):
        check(f"A-D5 excluded {fn} absent", func_block(NEWS, fn) == "")


# ---- efvgAbsState mirror (SignalEngine/21 L927-981) ----------------------------
def abs_state_new():
    return dict(btop=None, bbot=None, bbar=None, babs=False, rtop=None, rbot=None, rbar=None, rabs=False,
                bias=0, evbar=None, evtime=None)


def abs_state(s, b, hold, minThick, bodyMin, edge, useColor=True, useBody=True, useEdge=True):
    """b: dict(o,h,l,c,h2,l2,atr,bar,time). Returns (bias, eventId, eventTime)."""
    o, h, l, c = b["o"], b["h"], b["l"], b["c"]
    ref = b.get("atr", 1.0)
    body, rng = abs(c - o), h - l
    newBull = ref > 0 and l > b["h2"] and (l - b["h2"]) / ref >= minThick
    newBear = ref > 0 and h < b["l2"] and (b["l2"] - h) / ref >= minThick
    if newBull:
        s.update(btop=l, bbot=b["h2"], bbar=b["bar"], babs=False)
    if newBear:
        s.update(rtop=b["l2"], rbot=h, rbar=b["bar"], rabs=False)
    strong = rng > 0 and body / rng >= bodyMin
    nearHi = rng > 0 and (c - l) / rng >= edge
    nearLo = rng > 0 and (h - c) / rng >= edge
    aL = s["rtop"] is not None and not s["rabs"] and b["bar"] > s["rbar"] and c > s["rtop"] and \
        ((not useColor) or c > o) and ((not useBody) or strong) and ((not useEdge) or nearHi)
    aS = s["btop"] is not None and not s["babs"] and b["bar"] > s["bbar"] and c < s["bbot"] and \
        ((not useColor) or c < o) and ((not useBody) or strong) and ((not useEdge) or nearLo)
    if aL and aS:
        s.update(bias=0, evbar=None, evtime=None, rabs=True, babs=True)
    elif aL:
        s.update(bias=1, evbar=b["bar"], evtime=b["time"], rabs=True)
    elif aS:
        s.update(bias=-1, evbar=b["bar"], evtime=b["time"], babs=True)
    active = s["evbar"] is not None and (b["bar"] - s["evbar"]) < hold
    return (s["bias"] if active else 0), s["evbar"], s["evtime"]


# ---- updateFvgAbs mirror (SignalEngine/21 L2039-2145) -----------------------------
def abs_engine_new():
    return dict(ev5Id=None, ev5Time=None, ev5Consumed=None, bos1mTime=None, ev15Id=None, ev15Time=None,
                ev15Consumed=None, bos5mTime=None, bos1mTimeS=None, bos5mTimeS=None)


def update_fvg_abs(e, envL, envS, a5, a15, bull1m, bear1m, use5, use15, close, bos5Hi, bos5Lo, t, confirmed=True):
    b5, ev5, et5 = a5
    b15, ev15, et15 = a15
    if ev5 is not None and (e["ev5Id"] is None or ev5 != e["ev5Id"]):
        e["ev5Id"], e["ev5Time"] = ev5, et5
    if ev15 is not None and (e["ev15Id"] is None or ev15 != e["ev15Id"]):
        e["ev15Id"], e["ev15Time"] = ev15, et15
    if any(bull1m):
        e["bos1mTime"] = t
    if any(bear1m):
        e["bos1mTimeS"] = t
    if confirmed and close > bos5Hi:
        e["bos5mTime"] = t
    if confirmed and close < bos5Lo:
        e["bos5mTimeS"] = t
    ge = lambda a, b_: a is not None and b_ is not None and a >= b_
    ok5, ok15 = ge(e["bos1mTime"], e["ev5Time"]), ge(e["bos5mTime"], e["ev15Time"])
    ok5S, ok15S = ge(e["bos1mTimeS"], e["ev5Time"]), ge(e["bos5mTimeS"], e["ev15Time"])
    un5 = e["ev5Consumed"] is None or e["ev5Consumed"] != e["ev5Id"]
    un15 = e["ev15Consumed"] is None or e["ev15Consumed"] != e["ev15Id"]
    l5 = use5 and envL and confirmed and b5 == 1 and e["ev5Id"] is not None and un5 and ok5
    l15 = use15 and envL and confirmed and b15 == 1 and e["ev15Id"] is not None and un15 and ok15
    s5 = use5 and envS and confirmed and b5 == -1 and e["ev5Id"] is not None and un5 and ok5S
    s15 = use15 and envS and confirmed and b15 == -1 and e["ev15Id"] is not None and un15 and ok15S
    pvT = t if close > bos5Hi else e["bos5mTime"]
    pvTS = t if close < bos5Lo else e["bos5mTimeS"]
    pv5 = use5 and envL and b5 == 1 and e["ev5Id"] is not None and un5 and ok5
    pv15 = use15 and envL and b15 == 1 and e["ev15Id"] is not None and un15 and ge(pvT, e["ev15Time"])
    pvS5 = use5 and envS and b5 == -1 and e["ev5Id"] is not None and un5 and ok5S
    pvS15 = use15 and envS and b15 == -1 and e["ev15Id"] is not None and un15 and ge(pvTS, e["ev15Time"])
    return dict(long5=l5, long15=l15, short5=s5, short15=s15, previewLong5=pv5, previewLong15=pv15,
                previewShort5=pvS5, previewShort15=pvS15)


def consume_abs_(e, which):
    if which == 5:
        e["ev5Consumed"] = e["ev5Id"]
    elif which == 15:
        e["ev15Consumed"] = e["ev15Id"]


def abs_env(allow, trend, sess, news, med, vmin, vmax, vol, blk, wait, dirOk):
    dv = med is not None and vmin <= med < vmax
    return allow and trend and dv and sess and news and vol and not blk and not wait and dirOk


NOB = (0, None, None)


def fixture_p04_behaviour():
    HI, LO = 4100.0, 4000.0          # 5M BOS levels far away unless needed
    # ABS1 5M Long: event at t=500, 1M bull BOS before -> false; after -> true
    e = abs_engine_new()
    r0 = update_fvg_abs(e, True, True, NOB, NOB, [True], [], True, False, 4050, HI, LO, 400)   # BOS at 400 (no event yet)
    r1 = update_fvg_abs(e, True, True, (1, 77, 500), NOB, [], [], True, False, 4050, HI, LO, 600)
    r2 = update_fvg_abs(e, True, True, (1, 77, 500), NOB, [False, True], [], True, False, 4050, HI, LO, 700)
    check("ABS1 5M Long: event -> 1M Bull BOS before event = false, after event = true",
          not r0["long5"] and not r1["long5"] and r2["long5"] and e["ev5Time"] == 500)
    # ABS2 5M Short (symmetric)
    e = abs_engine_new()
    update_fvg_abs(e, True, True, NOB, NOB, [], [True], True, False, 4050, HI, LO, 400)
    s1 = update_fvg_abs(e, True, True, (-1, 78, 500), NOB, [], [], True, False, 4050, HI, LO, 600)
    s2 = update_fvg_abs(e, True, True, (-1, 78, 500), NOB, [], [True], True, False, 4050, HI, LO, 700)
    check("ABS2 5M Short symmetric (bear 1M BOS after event)", not s1["short5"] and s2["short5"] and not s2["long5"])
    # ABS3 15M Long: event -> 5M bull BOS (confirmed chart bar)
    e = abs_engine_new()
    a = update_fvg_abs(e, True, True, NOB, (1, 90, 1000), [], [], False, True, 4050, 4060, LO, 1100)
    b = update_fvg_abs(e, True, True, NOB, (1, 90, 1000), [], [], False, True, 4061, 4060, LO, 1200)
    check("ABS3 15M Long: 15M absorption event -> later confirmed 5M bull BOS -> long15", not a["long15"] and b["long15"])
    # ABS4 15M Short
    e = abs_engine_new()
    a = update_fvg_abs(e, True, True, NOB, (-1, 91, 1000), [], [], False, True, 4050, HI, 4040, 1100)
    b = update_fvg_abs(e, True, True, NOB, (-1, 91, 1000), [], [], False, True, 4039, HI, 4040, 1200)
    check("ABS4 15M Short symmetric", not a["short15"] and b["short15"])
    # ABS5 BOS before event is not used (same event later, no new BOS)
    e = abs_engine_new()
    update_fvg_abs(e, True, True, NOB, NOB, [], [], False, True, 4061, 4060, LO, 900)          # 5M BOS at 900
    c1 = update_fvg_abs(e, True, True, NOB, (1, 92, 1000), [], [], False, True, 4050, 4060, LO, 1100)
    same_bar = abs_engine_new()
    c2 = update_fvg_abs(same_bar, True, True, (1, 93, 1000), NOB, [True], [], True, False, 4050, HI, LO, 1000)
    check("ABS5 BOS before event ignored; BOS in the event bar itself is valid (>=)",
          not c1["long15"] and e["bos5mTime"] == 900 and c2["long5"])
    # ABS6 consume only when called
    e = abs_engine_new()
    r = update_fvg_abs(e, True, True, (1, 77, 500), NOB, [True], [], True, False, 4050, HI, LO, 600)
    r_again = update_fvg_abs(e, True, True, (1, 77, 500), NOB, [], [], True, False, 4050, HI, LO, 700)
    before = dict(e)
    consume_abs_(e, 5)
    r_after = update_fvg_abs(e, True, True, (1, 77, 500), NOB, [], [], True, False, 4050, HI, LO, 800)
    r_new = update_fvg_abs(e, True, True, (1, 88, 850), NOB, [True], [], True, False, 4050, HI, LO, 900)
    check("ABS6 signal alone / FAIL do not consume (signal persists); consumeFvgAbs blocks; new eventId re-arms",
          r["long5"] and r_again["long5"] and before["ev5Consumed"] is None and not r_after["long5"] and r_new["long5"])
    # ABS7 5M / 15M consumed independent
    e = abs_engine_new()
    update_fvg_abs(e, True, True, (1, 77, 500), (1, 90, 500), [True], [], True, True, 4061, 4060, LO, 600)
    consume_abs_(e, 5)
    q = update_fvg_abs(e, True, True, (1, 77, 500), (1, 90, 500), [], [], True, True, 4050, 4060, LO, 700)
    check("ABS7 ev5Consumed does not touch ev15 (15 still signals)", not q["long5"] and q["long15"]
          and e["ev15Consumed"] is None)
    # ABS8 env: each single NG -> false
    base = dict(allow=True, trend=True, sess=True, news=True, med=50.0, vmin=0.0, vmax=100.0, vol=True, blk=False,
                wait=False, dirOk=True)
    ng = {"trend": dict(trend=False), "daily vol": dict(med=150.0), "daily vol na": dict(med=None),
          "session": dict(sess=False), "news": dict(news=False), "vol": dict(vol=False), "accum blocked": dict(blk=True),
          "exit wait": dict(wait=True), "accum direction": dict(dirOk=False)}
    okb = abs_env(**base)
    bad = [k for k, kw in ng.items() if abs_env(**{**base, **kw})]
    check("ABS8 env: base ok; each of trend/daily vol/session/news/vol/accum/exit wait/direction alone -> false",
          okb and not bad, f"still-true={bad}")
    check("ABS8 daily vol band is [min, max): med == max is NG, med == min is OK",
          not abs_env(**{**base, "med": 100.0}) and abs_env(**{**base, "med": 0.0}))
    # ABS9 quality boundaries
    def run(bar, **kw):
        s_ = abs_state_new()
        abs_state(s_, dict(o=4000, h=4010, l=4002, c=4008, h2=4000, l2=4020, atr=10.0, bar=1, time=100), 3, 0.0, 0.5, 0.6)
        return abs_state(s_, bar, kw.pop("hold", 3), kw.pop("thick", 0.0), kw.pop("bodyMin", 0.5), kw.pop("edge", 0.6), **kw)
    # bearish FVG recorded at bar1: top = low[2]=4020, bot = high=4010. Absorption bar closes above 4020
    good = dict(o=4012, h=4030, l=4010, c=4028, h2=4000, l2=4000, atr=10.0, bar=2, time=200)   # body 16/20=0.8 edge 0.9
    check("ABS9 absorption long fires on bearish FVG close-through (bias 1, event bar / time)", run(good) == (1, 2, 200))
    check("ABS9 colour filter: bearish candle closing above top is rejected",
          run(dict(good, o=4029, c=4028.5))[0] == 0)
    edge_bar = dict(good, o=4012, h=4030, l=4010, c=4022)       # body 10/20 = 0.5 (==min OK), edge (4022-4010)/20 = 0.6 (==min OK)
    check("ABS9 body / edge boundaries inclusive (>=)", run(edge_bar)[0] == 1 and
          run(dict(edge_bar, o=4012.5))[0] == 0 and run(dict(edge_bar, c=4021.9, o=4011.9))[0] == 0)
    check("ABS9 colour/body/edge filters can be disabled", run(dict(good, o=4029, c=4028.5), useColor=False,
                                                                useBody=False, useEdge=False)[0] == 1)
    s_ = abs_state_new()
    thick = abs_state(s_, dict(o=4000, h=4010, l=4002, c=4008, h2=4000, l2=4020, atr=10.0, bar=1, time=100), 3, 1.0, 0.5, 0.6)
    s2_ = abs_state_new()
    thick_ok = abs_state(s2_, dict(o=4000, h=4010, l=4002, c=4008, h2=4000, l2=4020, atr=10.0, bar=1, time=100), 3, 1.0, 0.5, 0.6)
    after = abs_state(s2_, good, 3, 1.0, 0.5, 0.6)
    s3_ = abs_state_new()
    abs_state(s3_, dict(o=4000, h=4011, l=4002, c=4008, h2=4000, l2=4020, atr=10.0, bar=1, time=100), 3, 1.0, 0.5, 0.6)
    after_thin = abs_state(s3_, good, 3, 1.0, 0.5, 0.6)
    check("ABS9 min thickness boundary: (low[2]-high)/atr = 1.0 >= 1.0 forms the FVG; 0.9 does not",
          after == (1, 2, 200) and after_thin[0] == 0)
    s_ = abs_state_new()
    abs_state(s_, dict(o=4000, h=4010, l=4002, c=4008, h2=4000, l2=4020, atr=10.0, bar=1, time=100), 3, 0.0, 0.5, 0.6)
    seq = [abs_state(s_, good, 3, 0.0, 0.5, 0.6)[0]] + \
          [abs_state(s_, dict(o=4030, h=4031, l=4029, c=4030, h2=4040, l2=4000, atr=10.0, bar=b_, time=b_ * 100), 3,
                     0.0, 0.5, 0.6)[0] for b_ in (3, 4, 5)]
    check("ABS9 hold: bias kept while bar - eventBar < hold (3), then 0; same FVG absorbs only once",
          seq == [1, 1, 1, 0], str(seq))
    # ABS10 preview does not change engine state
    e = abs_engine_new()
    update_fvg_abs(e, True, True, NOB, (1, 90, 1000), [], [], False, True, 4050, 4060, LO, 1100)
    snap = dict(e)
    pv = update_fvg_abs(e, True, True, NOB, (1, 90, 1000), [], [], False, True, 4061, 4060, LO, 1200, confirmed=False)
    check("ABS10 preview: forming 5M bar BOS counts for previewLong15 without writing bos5mTime; long15 false",
          pv["previewLong15"] and not pv["long15"] and e == snap)


# =============================================================================
# P05 — Zone 4Logic core (static differential + behavioural mirror)
# =============================================================================
import difflib

P05_VERBATIM = ["zoneTfPack", "zoneTfEnvOk", "zoneDailyVolOk", "zoneBaseEnvOk", "zoneDailyVolOkBreak",
                "zoneBaseEnvOkBreak", "zoneDailyVolOkBreakLong", "zoneBaseEnvOkBreakLong", "zoneEnvLongBreak",
                "zoneEnvShortBreak", "zoneEnvLong", "zoneEnvShort", "consumeZoneEvt"]


def fixture_p05_static():
    NEWS = open(os.path.join(ROOT, "SignalEnginePractical.pine"), encoding="utf-8").read()
    for fn in P05_VERBATIM:
        o, n = func_block(ORIG, fn), func_block(NEWS, fn)
        check(f"ZD1 {fn}: verbatim", n != "" and n == o)
    o = func_block(ORIG, "updateZoneEvents").split("\n")
    n = func_block(NEWS, "updateZoneEvents").split("\n")
    ops = difflib.SequenceMatcher(a=o, b=n, autojunk=False).get_opcodes()
    deleted, bad = [], []
    for tag, i1, i2, j1, j2 in ops:
        if tag == "equal":
            continue
        if tag == "delete":
            deleted += o[i1:i2]
        elif tag == "replace" and i2 - i1 > 1 and j2 - j1 == 1 and \
                o[i1].rstrip().rstrip(",") + ")" == n[j1].rstrip():
            deleted += o[i1 + 1:i2]            # last kept arg line re-closed + following debug args dropped
        else:
            bad.append((tag, o[i1:i2][:2], n[j1:j2][:2]))
    check("ZD2 updateZoneEvents: only deletions (+ re-closing the last kept constructor line)", not bad,
          f"{len(deleted)} lines deleted" if not bad else str(bad)[:300])
    # every deleted local is never read by any kept line
    decl = set(re.findall(r"^\s+(?:int|float|bool)\s+(\w+)\s*=", "\n".join(deleted), re.M))
    kept_code = code_only("\n".join(n))
    leaked = sorted(v for v in decl if re.search(r"\b" + v + r"\b", kept_code))
    check("ZD3 deleted debug locals are not read by any kept line (debug-only proven)", decl and not leaked,
          f"decl={sorted(decl)} leaked={leaked}")
    del_code = [ln for ln in deleted if ln.strip() and not ln.strip().startswith("//")]
    writes_in_deleted = [ln.strip() for ln in del_code if re.search(r"\b(q|e|qb|qr)\.\w+\s*:=", ln)]
    check("ZD3 deleted lines contain no engine / event state write", not writes_in_deleted, str(writes_in_deleted))
    oc, nc = code_only("\n".join(o)), kept_code
    sw = lambda b: re.findall(r"\b((?:q|qb|qr|e)\.\w+)\s*(?::=|\+=)", b)
    check("ZD4 state write order identical (q / qb / qr / e)", sw(oc) == sw(nc), f"{len(sw(nc))} writes")
    br = lambda b: [ln.strip() for ln in b.split("\n") if re.match(r"^\s+(if|else if|else|for|while)\b", ln)
                    and not re.search(r"iDbgRb|oRb", ln)]
    check("ZD4 branch / loop sequence identical (minus debug-only branches)", br(oc) == br(nc), f"{len(br(nc))}")
    phase = lambda b: re.findall(r"\.phase\s*(?::=|==)\s*\d", b)
    check("ZD4 phase transitions / tests identical", phase(oc) == phase(nc), " ".join(phase(nc)))
    newev = lambda b: re.findall(r"ZoneEvt\.new\((.*?)\)\)", b, re.S)
    check("ZD4 event creation (frozen zoneId/roleCycle/top/bottom/strength/score/side/startBar/tfSec) identical",
          newev(oc) == newev(nc) and len(newev(nc)) == 1)
    sig = lambda b: re.findall(r"e\.sig\w+\s*:=\s*\w+", b)
    check("ZD4 consume index (sig slots) assignment identical", sig(oc) == sig(nc) and len(sig(nc)) == 4)
    rets = re.findall(r"(\w+)\s*=", func_block(NEWS, "updateZoneEvents").split("ZoneLogicSignal.new(")[1])
    check("ZD4 return fields == kept ZoneLogicSignal (8 signals + 8 previews + entryPrice)",
          sorted(rets) == sorted(NT["ZoneLogicSignal"]), str(len(rets)))


# ---- Python mirror of updateZoneEvents (SignalEnginePractical, debug removed) --------------------
class ZCfg:
    def __init__(self, **kw):
        d = dict(enableLong=True, enableShort=True, useRebound=True, useFake=True, useRetest=True, useBreak=True,
                 reqDailyVol="OFF", dailyLowVol=0.0, dailyHighVol=80.0, insufficientAsRange=True, breakBuffer=3.0,
                 fakeMaxBars=10, retestMinDist=10.0, retestWidthMult=0.5, waitBars=30, minMoveAway=0.0,
                 reboundRecoveryRatio=1.0, breakWaitBars=30, breakReqDailyVol="OFF", breakDailyLowVol=0.0,
                 breakDailyHighVol=80.0, breakLongRefCompat=False, breakLongWaitBars=30,
                 breakLongReqDailyVol="OFF", breakLongDailyLowVol=0.0, breakLongDailyHighVol=80.0,
                 breakLongUseAccumNoTrade=True, breakLongUseAccumExitWait=True, breakLongUseAccumDirection=True)
        d.update(kw)
        self.__dict__.update(d)


def zone_engine():
    return dict(evts=[], barNo=0, prevClose=None, sigRebound=-1, sigFake=-1, sigRetest=-1, sigBreak=-1,
                roleZoneId=[], roleSide=[], roleCycleNo=[], roleSeen=[], roleSeenBar=[])


def new_evt(**kw):
    d = dict(zoneId=None, roleCycle=0, top=None, bottom=None, strength=0, score=None, side=0, startBar=None,
             phase=0, breakBar=None, breakDir=0, breakTime=None, rearmBar=None, touchBar=None, reclaimBar=None,
             rejectBar=None, rejectTime=None, movedAway=False, reclaimed=False, touched=False, rejected=False,
             fakeAlive=False, bkOnly=False, rbCancelled=False, reboundDone=False, breakDone=False, fakeDone=False,
             retestDone=False, tfSec=0, brkTfSec=0, alive=True)
    d.update(kw)
    return d


def tf_env_ok(t, e4, e1, e15):
    t = dict(dict(up4H=False, rg4H=False, dn4H=False, up1H=False, rg1H=False, dn1H=False, up15M=False,
                  rg15M=False, dn15M=False, useAnd=False), **(t or {}))
    en4, en1, en15 = t["up4H"] or t["rg4H"] or t["dn4H"], t["up1H"] or t["rg1H"] or t["dn1H"], \
        t["up15M"] or t["rg15M"] or t["dn15M"]
    v4, v1, v15 = e4 or 0, e1 or 0, e15 or 0
    ok = lambda u, r, d, v: (u and v == 1) or (r and v == 0) or (d and v == -1)
    ok4, ok1, ok15 = ok(t["up4H"], t["rg4H"], t["dn4H"], v4), ok(t["up1H"], t["rg1H"], t["dn1H"], v1), \
        ok(t["up15M"], t["rg15M"], t["dn15M"], v15)
    if en4 or en1 or en15:
        if t["useAnd"]:
            return (not en4 or ok4) and (not en1 or ok1) and (not en15 or ok15)
        return (en4 and ok4) or (en1 and ok1) or (en15 and ok15)
    return True


def daily_vol_ok(req, lo, hi, ins_as_range, med):
    code = None if med is None else (1 if med >= hi else -1 if med < lo else 0)
    ins = code is None
    adj = (0 if ins_as_range else None) if ins else code
    return (req == "OFF" or vol_text(adj) == req) and not (req != "OFF" and ins and not ins_as_range)


def zone_env(c, f, t, long_, brk=False):
    base = f["sessionOk"] and f["newsOk"] and f["volOk"]
    if brk and long_:
        cp = c.breakLongRefCompat
        req, lo, hi = (c.breakLongReqDailyVol, c.breakLongDailyLowVol, c.breakLongDailyHighVol) if cp else \
            (c.breakReqDailyVol, c.breakDailyLowVol, c.breakDailyHighVol)
        wait = False if (cp and not c.breakLongUseAccumExitWait) else f["blockedByExitWait"]
        blk = False if (cp and not c.breakLongUseAccumNoTrade) else f["blockedByAccumLong"]
        dok = True if (cp and not c.breakLongUseAccumDirection) else f["accumLongDirOk"]
        return base and daily_vol_ok(req, lo, hi, c.insufficientAsRange, f["drMedianRange"]) and not wait and \
            not blk and dok and tf_env_ok(t, f["env4H"], f["env1H"], f["env15M"])
    if brk:
        dv = daily_vol_ok(c.breakReqDailyVol, c.breakDailyLowVol, c.breakDailyHighVol, c.insufficientAsRange,
                          f["drMedianRange"])
    else:
        dv = daily_vol_ok(c.reqDailyVol, c.dailyLowVol, c.dailyHighVol, c.insufficientAsRange, f["drMedianRange"])
    blk = f["blockedByAccumLong"] if long_ else f["blockedByAccumShort"]
    dok = f["accumLongDirOk"] if long_ else f["accumShortDirOk"]
    return base and dv and not f["blockedByExitWait"] and not blk and dok and \
        tf_env_ok(t, f["env4H"], f["env1H"], f["env15M"])


def zfeed(**kw):
    d = dict(sessionOk=True, newsOk=True, volOk=True, blockedByAccumLong=False, blockedByAccumShort=False,
             blockedByExitWait=False, accumLongDirOk=True, accumShortDirOk=True, env4H=1, env1H=1, env15M=1,
             drMedianRange=50.0)
    d.update(kw)
    return d


def update_zone(e, c, f, v, snap, tf, brkClose, brkValid, bar, t, confirmed=True, opens=(False,) * 4):
    """snap: list of (id, side, top, bot, str, score); tf: list of (c, h, l, bull, bear)."""
    v = v or {}
    envRbL, envRbS = zone_env(c, f, v.get("rbL"), True), zone_env(c, f, v.get("rbS"), False)
    envFkL, envFkS = zone_env(c, f, v.get("fkL"), True), zone_env(c, f, v.get("fkS"), False)
    envRtL, envRtS = zone_env(c, f, v.get("rtL"), True), zone_env(c, f, v.get("rtS"), False)
    envBkL, envBkS = zone_env(c, f, v.get("bkL"), True, True), zone_env(c, f, v.get("bkS"), False, True)
    oRb, oFk, oRt, oBk = opens
    aRbL, aRbS = c.useRebound and c.enableLong and envRbL and not oRb, c.useRebound and c.enableShort and envRbS and not oRb
    aFkL, aFkS = c.useFake and c.enableLong and envFkL and not oFk, c.useFake and c.enableShort and envFkS and not oFk
    aRtL, aRtS = c.useRetest and c.enableLong and envRtL and not oRt, c.useRetest and c.enableShort and envRtS and not oRt
    aBkL, aBkS = c.useBreak and c.enableLong and envBkL and not oBk, c.useBreak and c.enableShort and envBkS and not oBk
    effBk = c.breakWaitBars if c.useBreak else c.waitBars
    effBkL = (c.breakLongWaitBars if c.breakLongRefCompat else c.breakWaitBars) if c.useBreak else c.waitBars
    e["evts"] = [q for q in e["evts"] if q["alive"]]
    if len(e["evts"]) > 60:
        cut, bi = len(e["evts"]) - 60, 0
        while cut > 0 and bi < len(e["evts"]):
            if e["evts"][bi]["bkOnly"]:
                e["evts"].pop(bi); cut -= 1
            else:
                bi += 1
    while len(e["evts"]) > 60:
        e["evts"].pop(0)
    e["roleSeen"] = [False] * len(e["roleZoneId"])
    for (zi, zs, _, _, _, _) in snap:
        ri = -1
        for j, z in enumerate(e["roleZoneId"]):
            if z == zi:
                ri = j
        if ri < 0:
            e["roleZoneId"].append(zi); e["roleSide"].append(zs); e["roleCycleNo"].append(1)
            e["roleSeen"].append(True); e["roleSeenBar"].append(bar)
        else:
            e["roleSeen"][ri], e["roleSeenBar"][ri] = True, bar
            if e["roleSide"][ri] != zs:
                e["roleSide"][ri] = zs
                e["roleCycleNo"][ri] += 1
    for i in range(len(e["roleZoneId"])):
        if not e["roleSeen"][i] and e["roleSide"][i] != 0:
            e["roleSide"][i] = 0
    rbL = rbS = fkL = fkS = rtL = rtS = bkL = bkS = False
    iRb = iFk = iRt = iBk = -1
    for (tc, th, tl, tb, ts) in tf:
        e["barNo"] += 1
        if snap and e["prevClose"] is not None:
            for (zi, zs, zt, zb, zstr, zsc) in snap:
                hit = tl <= zt and th >= zb
                sd = 1 if e["prevClose"] > zt else -1 if e["prevClose"] < zb else 0
                if hit and sd != 0 and sd == zs:
                    rc = 0
                    for j, z in enumerate(e["roleZoneId"]):
                        if z == zi:
                            rc = e["roleCycleNo"][j]
                    exists = any(q["alive"] and not q["bkOnly"] and q["zoneId"] == zi and q["side"] == sd and
                                 q["roleCycle"] == rc for q in e["evts"])
                    if not exists:
                        e["evts"].append(new_evt(zoneId=zi, roleCycle=rc, top=zt, bottom=zb, strength=zstr,
                                                 score=zsc, side=sd, startBar=e["barNo"], phase=0, tfSec=60))
        for i, q in enumerate(e["evts"]):
            if not q["alive"]:
                continue
            w = q["top"] - q["bottom"]
            rd = max(c.retestMinDist, w * c.retestWidthMult)
            if q["phase"] == 0:
                brk1m = tc < q["bottom"] - c.breakBuffer if q["side"] > 0 else tc > q["top"] + c.breakBuffer
                if brk1m:
                    q["rbCancelled"] = True
                if not q["rbCancelled"]:
                    rcvL = q["top"] if c.reboundRecoveryRatio >= 1.0 else q["bottom"] + w * c.reboundRecoveryRatio
                    rcvS = q["bottom"] if c.reboundRecoveryRatio >= 1.0 else q["top"] - w * c.reboundRecoveryRatio
                    if c.minMoveAway <= 0 and c.reboundRecoveryRatio >= 1.0:
                        q["movedAway"] = True
                    elif q["side"] > 0 and tc >= rcvL + c.minMoveAway:
                        q["movedAway"] = True
                    elif q["side"] < 0 and tc <= rcvS - c.minMoveAway:
                        q["movedAway"] = True
                el0 = e["barNo"] - q["startBar"]
                if c.useBreak and el0 > c.waitBars:
                    q["bkOnly"] = True
                elMax = effBkL if q["side"] < 0 else effBk
                if el0 > max(c.waitBars, elMax):
                    q["alive"] = False
                if q["alive"] and not q["bkOnly"] and not q["rbCancelled"] and not q["reboundDone"] and q["movedAway"] and iRb < 0:
                    if q["side"] > 0 and tb and aRbL:
                        rbL, iRb = True, i
                    elif q["side"] < 0 and ts and aRbS:
                        rbS, iRb = True, i
            elif q["phase"] == 1:
                el = e["barNo"] - q["breakBar"]
                if el > c.fakeMaxBars:
                    q["fakeAlive"] = False
                if q["fakeAlive"]:
                    if not q["reclaimed"]:
                        if q["side"] > 0 and tc > q["top"]:
                            q["reclaimed"], q["reclaimBar"] = True, e["barNo"]
                        elif q["side"] < 0 and tc < q["bottom"]:
                            q["reclaimed"], q["reclaimBar"] = True, e["barNo"]
                    if not q["fakeDone"] and q["reclaimed"] and q["reclaimBar"] is not None and e["barNo"] >= q["reclaimBar"] and iFk < 0:
                        if q["side"] > 0 and tb and aFkL:
                            fkL, iFk = True, i
                        elif q["side"] < 0 and ts and aFkS:
                            fkS, iFk = True, i
                far = tc <= q["bottom"] - rd if q["side"] > 0 else tc >= q["top"] + rd
                if far:
                    q.update(phase=2, rearmBar=e["barNo"], fakeAlive=False, reclaimed=False, reclaimBar=None,
                             touched=False, rejected=False)
                elif el > max(c.fakeMaxBars, c.waitBars):
                    q["alive"] = False
            else:
                invalid = tc > q["top"] if q["side"] > 0 else tc < q["bottom"]
                if invalid:
                    q["alive"] = False
                else:
                    if not q["touched"] and tl <= q["top"] and th >= q["bottom"]:
                        q["touched"], q["touchBar"] = True, e["barNo"]
                    if q["touched"] and not q["rejected"]:
                        rej = tc < q["bottom"] if q["side"] > 0 else tc > q["top"]
                        if rej:
                            q["rejected"], q["rejectBar"], q["rejectTime"] = True, e["barNo"], t
                    if not q["touched"] and e["barNo"] - q["rearmBar"] > c.waitBars:
                        q["alive"] = False
                    if q["touched"] and e["barNo"] - q["touchBar"] > c.waitBars:
                        q["alive"] = False
                    if q["alive"] and q["rejected"] and q["rejectBar"] is not None and e["barNo"] >= q["rejectBar"] and not q["retestDone"] and iRt < 0:
                        if q["side"] > 0 and ts and aRtS:
                            rtS, iRt = True, i
                        elif q["side"] < 0 and tb and aRtL:
                            rtL, iRt = True, i
        e["prevClose"] = tc
    if 0 <= iRt < len(e["evts"]) and not e["evts"][iRt]["alive"]:
        rtL = rtS = False
        iRt = -1
    if brkValid and brkClose is not None:
        for i, qb in enumerate(e["evts"]):
            if qb["alive"] and qb["phase"] == 0:
                brk5 = brkClose < qb["bottom"] - c.breakBuffer if qb["side"] > 0 else brkClose > qb["top"] + c.breakBuffer
                if brk5:
                    elB = e["barNo"] - qb["startBar"]
                    okB = c.useBreak and elB <= (effBkL if qb["side"] < 0 else effBk)
                    if qb["bkOnly"]:
                        if okB and not qb["breakDone"] and iBk < 0:
                            if qb["side"] > 0 and aBkS:
                                bkS, iBk = True, i
                            elif qb["side"] < 0 and aBkL:
                                bkL, iBk = True, i
                        qb["alive"] = False
                    else:
                        qb.update(phase=1, breakBar=e["barNo"], breakDir=-qb["side"], breakTime=t, brkTfSec=300,
                                  fakeAlive=True, reclaimed=False, reclaimBar=None, touched=False, rejected=False,
                                  rejectBar=None)
                        if okB and not qb["breakDone"] and iBk < 0:
                            if qb["side"] > 0 and aBkS:
                                bkS, iBk = True, i
                            elif qb["side"] < 0 and aBkL:
                                bkL, iBk = True, i
    e["sigRebound"], e["sigFake"], e["sigRetest"], e["sigBreak"] = iRb, iFk, iRt, iBk
    cf = confirmed
    return dict(reboundLong=rbL and cf, reboundShort=rbS and cf, fakeLong=fkL and cf, fakeShort=fkS and cf,
                retestLong=rtL and cf, retestShort=rtS and cf, breakLong=bkL and cf, breakShort=bkS and cf,
                pvReboundLong=rbL, pvReboundShort=rbS, pvFakeLong=fkL, pvFakeShort=fkS, pvRetestLong=rtL,
                pvRetestShort=rtS, pvBreakLong=bkL, pvBreakShort=bkS)


def consume_zone_(e, kind):
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
            q["breakDone"] = True


SUP = [(7, 1, 4065.0, 4045.0, 3, 12.0)]          # Support zone 4045-4065 (trackId 7)
RES = [(8, -1, 4065.0, 4045.0, 3, 12.0)]         # Resistance zone 4045-4065 (trackId 8)


def bar1(c_, h=None, l=None, bull=False, bear=False):
    return (c_, c_ + 1 if h is None else h, c_ - 1 if l is None else l, bull, bear)


def run_bars(e, c, snap, bars, f=None, brk=None, start=1, confirmed=True):
    out = []
    for k, tfb in enumerate(bars):
        bc = None if brk is None else brk[k]
        out.append(update_zone(e, c, f or zfeed(), None, snap, [tfb], bc, bc is not None, start + k,
                               (start + k) * 60, confirmed))
    return out


def fixture_p05_events():
    c = ZCfg()
    # ZEV1 Support approached from above -> event side +1
    e = zone_engine()
    run_bars(e, c, SUP, [bar1(4080), bar1(4062, l=4060)])
    q = e["evts"][0] if e["evts"] else {}
    check("ZEV1 Support approached from above -> event (side +1, frozen top/bottom/strength/score/zoneId/roleCycle)",
          len(e["evts"]) == 1 and q["side"] == 1 and (q["top"], q["bottom"], q["strength"], q["score"], q["zoneId"],
                                                       q["roleCycle"]) == (4065.0, 4045.0, 3, 12.0, 7, 1))
    # ZEV2 Support entered from below -> no event
    e = zone_engine()
    run_bars(e, c, SUP, [bar1(4030), bar1(4050, h=4052)])
    check("ZEV2 Support entered from below -> no event", e["evts"] == [])
    e = zone_engine()
    run_bars(e, c, SUP, [bar1(4055), bar1(4050)])
    check("ZEV2b start inside the zone (prevClose inside) -> no event", e["evts"] == [])
    # ZEV3 Resistance approached from below -> side -1
    e = zone_engine()
    run_bars(e, c, RES, [bar1(4030), bar1(4048, h=4050)])
    check("ZEV3 Resistance approached from below -> event side -1", len(e["evts"]) == 1 and e["evts"][0]["side"] == -1)
    # ZEV4 Resistance entered from above -> none
    e = zone_engine()
    run_bars(e, c, RES, [bar1(4080), bar1(4062, l=4060)])
    check("ZEV4 Resistance entered from above -> no event", e["evts"] == [])
    # ZEV5 no duplicate for same zoneId+side+roleCycle
    e = zone_engine()
    run_bars(e, c, SUP, [bar1(4080), bar1(4062, l=4060), bar1(4070), bar1(4063, l=4061)])
    check("ZEV5 same zoneId+side+roleCycle not registered twice", len(e["evts"]) == 1)
    # ZEV6 role re-established -> roleCycle+1 -> new event allowed even with the old one alive
    e = zone_engine()
    run_bars(e, c, SUP, [bar1(4080), bar1(4062, l=4060)])
    run_bars(e, c, [], [bar1(4080)], start=3)                 # zone leaves snapshot -> role 0
    run_bars(e, c, SUP, [bar1(4080), bar1(4062, l=4060)], start=4)
    cyc = sorted(q["roleCycle"] for q in e["evts"])
    check("ZEV6 role lost then re-established -> roleCycle 2 -> new event while gen-1 still alive",
          cyc == [1, 2] and all(q["alive"] for q in e["evts"]), str(cyc))


def fixture_p05_rebound_break():
    c = ZCfg(useBreak=True)
    # ZRB1 touch -> recovery (close >= top) -> bull BOS -> rebound long
    e = zone_engine()
    r = run_bars(e, c, SUP, [bar1(4080), bar1(4058, l=4050), bar1(4066), bar1(4068, bull=True)])
    check("ZRB1 Long: touch -> recovery above top -> BOS -> reboundLong", r[-1]["reboundLong"] and not any(
        x["reboundLong"] for x in r[:-1]))
    e = zone_engine()
    r = run_bars(e, c, RES, [bar1(4030), bar1(4050, h=4058), bar1(4044), bar1(4042, bear=True)])
    check("ZRB1s Short symmetric: reboundShort", r[-1]["reboundShort"])
    # ZRB2 BOS before recovery -> no rebound (needs minMoveAway / ratio < 1 for a real recovery gate)
    c2 = ZCfg(minMoveAway=2.0)
    e = zone_engine()
    r = run_bars(e, c2, SUP, [bar1(4080), bar1(4058, l=4050, bull=True), bar1(4066), bar1(4068)])
    check("ZRB2 BOS before recovery -> no rebound (recovery 4065+2 reached only after the BOS)",
          not any(x["reboundLong"] for x in r))
    # ZRB3 1M close through breakBuffer -> rbCancelled, no rebound afterwards
    e = zone_engine()
    r = run_bars(e, c, SUP, [bar1(4080), bar1(4050, l=4046), bar1(4040), bar1(4068, bull=True)])
    check("ZRB3 1M close < bottom - buffer -> rbCancelled; later BOS does not fire rebound",
          e["evts"][0]["rbCancelled"] and not any(x["reboundLong"] for x in r))
    # ZRB4 env NG at signal time -> no signal (env evaluated only at signal)
    e = zone_engine()
    run_bars(e, c, SUP, [bar1(4080), bar1(4058, l=4050), bar1(4066)])
    ng = update_zone(e, c, zfeed(sessionOk=False), None, SUP, [bar1(4068, bull=True)], None, False, 4, 240)
    e = zone_engine()
    run_bars(e, c, SUP, [bar1(4080), bar1(4058, l=4050)], f=zfeed(sessionOk=False))   # NG at start only
    ok = run_bars(e, c, SUP, [bar1(4066), bar1(4068, bull=True)], start=3)
    tfng = update_zone(zone_engine(), c, zfeed(env4H=-1), {"rbL": dict(up4H=True)}, SUP, [bar1(4080)], None, False, 1, 60)
    check("ZRB4 env NG at signal -> none; NG only at event start -> signal ok (env not frozen)",
          not ng["reboundLong"] and ok[-1]["reboundLong"])
    # ZBK1 1M close through only -> no break
    e = zone_engine()
    r = run_bars(e, c, SUP, [bar1(4080), bar1(4050, l=4046), bar1(4040)], brk=[None, None, None])
    check("ZBK1 1M close through without a valid break-TF close -> no Break, phase stays 0",
          not any(x["breakShort"] for x in r) and e["evts"][0]["phase"] == 0)
    # ZBK2 brkValid + break-TF close beyond bottom - buffer -> breakShort, phase 1
    e = zone_engine()
    r = run_bars(e, c, SUP, [bar1(4080), bar1(4050, l=4046), bar1(4040)], brk=[None, None, 4040.0])
    check("ZBK2 Support: valid break-TF close < bottom - buffer -> breakShort; event phase 1 frozen",
          r[-1]["breakShort"] and e["evts"][0]["phase"] == 1 and e["evts"][0]["breakDir"] == -1)
    e = zone_engine()
    r = run_bars(e, c, RES, [bar1(4030), bar1(4050, h=4058), bar1(4070)], brk=[None, None, 4070.0])
    check("ZBK2s Resistance: break-TF close > top + buffer -> breakLong", r[-1]["breakLong"])
    e = zone_engine()
    r = run_bars(e, c, SUP, [bar1(4080), bar1(4050, l=4046), bar1(4043)], brk=[None, None, 4042.0])
    check("ZBK2b strict: close == bottom - buffer (4042) -> no break", not r[-1]["breakShort"])
    # ZBK3 consume break keeps event alive
    e = zone_engine()
    run_bars(e, c, SUP, [bar1(4080), bar1(4050, l=4046), bar1(4040)], brk=[None, None, 4040.0])
    consume_zone_(e, 3)
    check("ZBK3 consume Break (kind 3) -> breakDone, event stays alive (Fake / Retest continue)",
          e["evts"][0]["breakDone"] and e["evts"][0]["alive"])


def fixture_p05_fake_retest():
    c = ZCfg(useBreak=True)
    pre = [bar1(4080), bar1(4050, l=4046), bar1(4040)]
    brk = [None, None, 4040.0]
    # ZFK1 break -> reclaim (close > top) -> bull BOS -> fakeLong (Support broken down, reclaimed up)
    e = zone_engine()
    run_bars(e, c, SUP, pre, brk=brk)
    r = run_bars(e, c, SUP, [bar1(4066), bar1(4068, bull=True)], start=4)
    check("ZFK1 Break -> full reclaim -> BOS -> fakeLong", r[-1]["fakeLong"])
    e = zone_engine()
    run_bars(e, c, RES, [bar1(4030), bar1(4050, h=4058), bar1(4070)], brk=[None, None, 4070.0])
    r = run_bars(e, c, RES, [bar1(4044), bar1(4042, bear=True)], start=4)
    check("ZFK1s symmetric fakeShort", r[-1]["fakeShort"])
    # ZFK2 BOS before reclaim -> no fake
    e = zone_engine()
    run_bars(e, c, SUP, pre, brk=brk)
    r = run_bars(e, c, SUP, [bar1(4050, bull=True), bar1(4066)], start=4)
    check("ZFK2 BOS before reclaim -> no fake (reclaim bar has no BOS)", not any(x["fakeLong"] for x in r))
    # ZFK3 fakeMaxBars exceeded -> no fake
    cf = ZCfg(useBreak=True, fakeMaxBars=2)
    e = zone_engine()
    run_bars(e, cf, SUP, pre, brk=brk)
    r = run_bars(e, cf, SUP, [bar1(4040), bar1(4041), bar1(4042), bar1(4066, bull=True)], start=4)
    check("ZFK3 reclaim after fakeMaxBars -> fakeAlive false -> no fake", not any(x["fakeLong"] for x in r))
    # ZRT1 touch right after break (not rearmed) -> no retest
    e = zone_engine()
    run_bars(e, c, SUP, pre, brk=brk)
    r = run_bars(e, c, SUP, [bar1(4044, h=4046), bar1(4040, bear=True)], start=4)
    check("ZRT1 touch right after break (no rearm) -> no retestShort", not any(x["retestShort"] for x in r)
          and e["evts"][0]["phase"] == 1)
    # ZRT2 rearm (far >= max(10, 20*0.5)=10 below bottom) -> touch -> rejection -> BOS -> retestShort
    e = zone_engine()
    run_bars(e, c, SUP, pre, brk=brk)
    r = run_bars(e, c, SUP, [bar1(4034), bar1(4044, h=4047), bar1(4043), bar1(4041, bear=True)], start=4)
    check("ZRT2 rearm -> touch -> rejection -> BOS -> retestShort", r[-1]["retestShort"]
          and not any(x["retestShort"] for x in r[:-1]))
    e = zone_engine()
    run_bars(e, c, RES, [bar1(4030), bar1(4050, h=4058), bar1(4070)], brk=[None, None, 4070.0])
    r = run_bars(e, c, RES, [bar1(4076), bar1(4066, l=4063), bar1(4067), bar1(4069, bull=True)], start=4)
    check("ZRT2s symmetric retestLong", r[-1]["retestLong"])
    # ZRT3 BOS before rejection -> no retest
    e = zone_engine()
    run_bars(e, c, SUP, pre, brk=brk)
    r = run_bars(e, c, SUP, [bar1(4034), bar1(4046, h=4047, bear=True), bar1(4043)], start=4)
    check("ZRT3 BOS at touch bar before rejection -> no retest on that bar; rejection bar without BOS -> none",
          not any(x["retestShort"] for x in r))
    # ZRT4 reverse full reclaim -> retest event invalid
    e = zone_engine()
    run_bars(e, c, SUP, pre, brk=brk)
    r = run_bars(e, c, SUP, [bar1(4034), bar1(4066), bar1(4041, bear=True)], start=4)
    check("ZRT4 close > top during retest -> event dead -> no retest",
          not any(x["retestShort"] for x in r) and (not e["evts"] or not e["evts"][0]["alive"]))
    # same-chart-bar cancel: retest fires on an early 1M then invalidated later in the same chart bar
    e = zone_engine()
    run_bars(e, c, SUP, pre, brk=brk)
    run_bars(e, c, SUP, [bar1(4034), bar1(4044, h=4047), bar1(4043)], start=4)
    rr = update_zone(e, c, zfeed(), None, SUP, [bar1(4041, bear=True), bar1(4066)], None, False, 7, 420)
    check("ZRT4b retest BOS then reverse reclaim within the same chart bar -> signal cancelled",
          not rr["retestShort"] and e["sigRetest"] == -1)


def fixture_p05_consume_preview():
    c = ZCfg(useBreak=True)
    e = zone_engine()
    r = run_bars(e, c, SUP, [bar1(4080), bar1(4058, l=4050), bar1(4066), bar1(4068, bull=True)])
    idx = e["sigRebound"]
    consume_zone_(e, 0)
    check("ZCON1 kind 0 Rebound -> reboundDone, alive=false (index = sigRebound)",
          r[-1]["reboundLong"] and e["evts"][idx]["reboundDone"] and not e["evts"][idx]["alive"])
    e = zone_engine()
    run_bars(e, c, SUP, [bar1(4080), bar1(4050, l=4046), bar1(4040)], brk=[None, None, 4040.0])
    run_bars(e, c, SUP, [bar1(4066), bar1(4068, bull=True)], start=4)
    consume_zone_(e, 1)
    q = e["evts"][0]
    check("ZCON1 kind 1 Fake -> fakeDone, retestDone, alive=false", q["fakeDone"] and q["retestDone"] and not q["alive"])
    e = zone_engine()
    run_bars(e, c, SUP, [bar1(4080), bar1(4050, l=4046), bar1(4040)], brk=[None, None, 4040.0])
    run_bars(e, c, SUP, [bar1(4034), bar1(4044, h=4047), bar1(4043), bar1(4041, bear=True)], start=4)
    consume_zone_(e, 2)
    q = e["evts"][0]
    check("ZCON1 kind 2 Retest -> retestDone, alive=false", q["retestDone"] and not q["alive"])
    e = zone_engine()
    run_bars(e, c, SUP, [bar1(4080), bar1(4058, l=4050), bar1(4066)])
    consume_zone_(e, 0)
    check("ZCON1 signal not produced -> sig index -1 -> consume is a no-op", e["evts"][0]["alive"]
          and not e["evts"][0]["reboundDone"])
    # ZPV1 preview == raw signal without confirmation, 8 fields
    e = zone_engine()
    run_bars(e, c, SUP, [bar1(4080), bar1(4058, l=4050), bar1(4066)])
    snap_ = repr(e)
    pv = update_zone(e, c, zfeed(), None, SUP, [bar1(4068, bull=True)], None, False, 4, 240, confirmed=False)
    keys = ["pvReboundLong", "pvReboundShort", "pvFakeLong", "pvFakeShort", "pvRetestLong", "pvRetestShort",
            "pvBreakLong", "pvBreakShort"]
    check("ZPV1 8 preview fields present; preview = same raw flag, confirmed = raw and isconfirmed",
          all(k in pv for k in keys) and pv["pvReboundLong"] and not pv["reboundLong"])
    e2 = zone_engine()
    run_bars(e2, c, SUP, [bar1(4080), bar1(4058, l=4050), bar1(4066)])
    cf = update_zone(e2, c, zfeed(), None, SUP, [bar1(4068, bull=True)], None, False, 4, 240, confirmed=True)
    e.pop("_", None)
    check("ZPV2 preview call mutates state exactly like the confirmed call (Pine rolls back realtime ticks; "
          "no extra preview-only write)", repr(e) == repr(e2) and cf["reboundLong"])


# =============================================================================
# P06 — Zone 4Logic boundary audit (B01-B12) + static compile readiness
# =============================================================================
def _one(e, c, snap, tfbars, brk=None, bar=1, t=60, f=None, confirmed=True):
    return update_zone(e, c, f or zfeed(), None, snap, tfbars, brk, brk is not None, bar, t, confirmed)


def _seed_event(e, **kw):
    q = new_evt(**kw)
    e["evts"].append(q)
    return q


def fixture_p06_boundaries():
    SUP_Z, RES_Z = SUP, RES          # 4045-4065, width 20
    c = ZCfg(useBreak=True)          # breakBuffer 3 -> Support break < 4042, Resistance break > 4068

    # ---- B01 Break boundary (break-TF close, strict) ----------------------
    for name, snap, eq, beyond, key in (("Support", SUP_Z, 4042.0, 4041.99, "breakShort"),
                                        ("Resistance", RES_Z, 4068.0, 4068.01, "breakLong")):
        res = []
        for px in (eq, beyond):
            e = zone_engine()
            side = 1 if name == "Support" else -1
            _seed_event(e, zoneId=7, roleCycle=1, top=4065.0, bottom=4045.0, side=side, startBar=0)
            res.append(_one(e, c, snap, [], brk=px)[key])
        check(f"B01 {name}: break-TF close == boundary -> no Break; 1 tick beyond -> Break", res == [False, True], str(res))

    # ---- B02 Rebound cancel boundary (1M close, strict) --------------------
    for name, snap, side, eq, beyond in (("Support", SUP_Z, 1, 4042.0, 4041.99), ("Resistance", RES_Z, -1, 4068.0, 4068.01)):
        res = []
        for px in (eq, beyond):
            e = zone_engine()
            _seed_event(e, zoneId=7, roleCycle=1, top=4065.0, bottom=4045.0, side=side, startBar=0)
            e["prevClose"] = px
            _one(e, c, snap, [bar1(px)])
            res.append(e["evts"][0]["rbCancelled"])
        check(f"B02 {name}: 1M close == bottom-buffer/top+buffer -> no cancel; beyond -> rbCancelled",
              res == [False, True], str(res))

    # ---- B03 Recovery boundary (>= / <= inclusive) -------------------------
    cr = ZCfg(useBreak=True, reboundRecoveryRatio=0.5, minMoveAway=1.0)   # base = 4055 -> Long needs >= 4056
    for name, side, eq, short_of in (("Long", 1, 4056.0, 4055.99), ("Short", -1, 4054.0, 4054.01)):
        res = []
        for px in (eq, short_of):
            e = zone_engine()
            _seed_event(e, zoneId=7, roleCycle=1, top=4065.0, bottom=4045.0, side=side, startBar=0)
            e["prevClose"] = px
            _one(e, cr, SUP_Z if side > 0 else RES_Z, [bar1(px)])
            res.append(e["evts"][0]["movedAway"])
        check(f"B03 Recovery {name}: close == base +/- minMoveAway -> movedAway; 1 tick short -> not", res == [True, False],
              str(res))
    e = zone_engine()
    _seed_event(e, zoneId=7, roleCycle=1, top=4065.0, bottom=4045.0, side=1, startBar=0)
    e["prevClose"] = 4050.0
    _one(e, ZCfg(useBreak=True, reboundRecoveryRatio=1.0, minMoveAway=0.0), SUP_Z, [bar1(4050)])
    check("B03 ratio >= 1.0 and minMoveAway <= 0 -> movedAway unconditionally (canonical legacy-compat branch)",
          e["evts"][0]["movedAway"])

    # ---- B04 Retest rearm boundary (<= / >= inclusive) ---------------------
    #   rd = max(10, 20*0.5) = 10 : Support broken down rearms at close <= 4035; Resistance at >= 4075
    for name, side, eq, short_of in (("Support", 1, 4035.0, 4035.01), ("Resistance", -1, 4075.0, 4074.99)):
        res = []
        for px in (eq, short_of):
            e = zone_engine()
            _seed_event(e, zoneId=7, roleCycle=1, top=4065.0, bottom=4045.0, side=side, startBar=0, phase=1,
                        breakBar=0, fakeAlive=True)
            _one(e, c, [], [bar1(px)])
            res.append(e["evts"][0]["phase"])
        check(f"B04 {name}: distance == max(retestMinDist, w*mult) -> phase 2; 1 tick short -> phase 1",
              res == [2, 1], str(res))
    e = zone_engine()
    _seed_event(e, zoneId=7, roleCycle=1, top=4065.0, bottom=4045.0, side=1, startBar=0, phase=1, breakBar=0,
                fakeAlive=True)
    _one(ZCfg() and e, ZCfg(useBreak=True, retestMinDist=10.0, retestWidthMult=1.0), [], [bar1(4035.0)])
    check("B04 width term dominates when w*mult (20) > retestMinDist (10): 4035 does not rearm",
          e["evts"][0]["phase"] == 1)

    # ---- B05 Reclaim boundary (strict) -------------------------------------
    for name, side, eq, beyond in (("Support (Fake Long)", 1, 4065.0, 4065.01), ("Resistance (Fake Short)", -1, 4045.0, 4044.99)):
        res = []
        for px in (eq, beyond):
            e = zone_engine()
            _seed_event(e, zoneId=7, roleCycle=1, top=4065.0, bottom=4045.0, side=side, startBar=0, phase=1,
                        breakBar=0, fakeAlive=True)
            _one(e, c, [], [bar1(px)])
            res.append(e["evts"][0]["reclaimed"])
        check(f"B05 Fake reclaim {name}: close == boundary -> not reclaimed; 1 tick beyond -> reclaimed",
              res == [False, True], str(res))
    for name, side, eq, beyond in (("Support (Retest Short)", 1, 4065.0, 4065.01), ("Resistance (Retest Long)", -1, 4045.0, 4044.99)):
        res = []
        for px in (eq, beyond):
            e = zone_engine()
            _seed_event(e, zoneId=7, roleCycle=1, top=4065.0, bottom=4045.0, side=side, startBar=0, phase=2, rearmBar=0)
            _one(e, c, [], [bar1(px, h=px, l=px)])
            res.append(e["evts"][0]["alive"])
        check(f"B05 Retest invalidation {name}: close == boundary -> alive; 1 tick beyond -> dead",
              res == [True, False], str(res))

    # ---- B06 same 1M bar ordering ------------------------------------------
    NEWS = open(os.path.join(ROOT, "SignalEnginePractical.pine"), encoding="utf-8").read()
    body = code_only(func_block(NEWS, "updateZoneEvents"))

    def pos(pat):
        m = re.search(pat, body)
        return m.start() if m else -1
    order_p2 = [pos(r"bool invalid = "), pos(r"q\.touched  := true"), pos(r"q\.rejected   := true"),
                pos(r"if not q\.touched and e\.barNo - q\.rearmBar > c\.waitBars"), pos(r"rtS := true")]
    order_p1 = [pos(r"if el > c\.fakeMaxBars"), pos(r"q\.reclaimed  := true"), pos(r"fkL := true"), pos(r"bool far = ")]
    order_p0 = [pos(r"bool brk1m = "), pos(r"q\.rbCancelled := true"), pos(r"q\.movedAway := true"),
                pos(r"q\.bkOnly := true"), pos(r"q\.alive := false"), pos(r"rbL := true")]
    check("B06 static: phase 2 order invalid -> touch -> rejection -> expiry -> signal",
          -1 not in order_p2 and order_p2 == sorted(order_p2), str(order_p2))
    check("B06 static: phase 1 order fake expiry -> reclaim -> fake signal -> rearm check",
          -1 not in order_p1 and order_p1 == sorted(order_p1), str(order_p1))
    check("B06 static: phase 0 order cancel -> recovery -> bkOnly -> expiry -> rebound signal",
          -1 not in order_p0 and order_p0 == sorted(order_p0), str(order_p0))
    e = zone_engine()
    _seed_event(e, zoneId=7, roleCycle=1, top=4065.0, bottom=4045.0, side=1, startBar=0, phase=2, rearmBar=0)
    r = _one(e, c, [], [(4044.0, 4046.0, 4043.0, False, True)])          # touch + rejection + bear BOS in one 1M bar
    check("B06 Retest: touch + rejection + BOS in the same 1M bar -> retestShort on that bar (rejectBar == barNo)",
          r["retestShort"] and e["evts"][0]["touchBar"] == e["evts"][0]["rejectBar"] == e["barNo"])
    e = zone_engine()
    _seed_event(e, zoneId=7, roleCycle=1, top=4065.0, bottom=4045.0, side=1, startBar=0, phase=1, breakBar=0,
                fakeAlive=True)
    r = _one(e, c, [], [(4066.0, 4067.0, 4060.0, True, False)])          # reclaim + bull BOS same 1M bar
    check("B06 Fake: reclaim + BOS in the same 1M bar -> fakeLong (reclaimBar == barNo)", r["fakeLong"])
    e = zone_engine()
    _seed_event(e, zoneId=7, roleCycle=1, top=4065.0, bottom=4045.0, side=1, startBar=0, movedAway=False)
    cm = ZCfg(useBreak=True, minMoveAway=1.0)
    r = _one(e, cm, [], [(4041.0, 4070.0, 4040.0, True, False)])         # cancel-level close + BOS
    check("B06 Rebound: cancel evaluated before recovery/signal -> no rebound even with BOS", not r["reboundLong"]
          and e["evts"][0]["rbCancelled"])

    # ---- B07 same 5M chart bar, 1M order preserved -------------------------
    seqA = [bar1(4058, l=4050), bar1(4066), bar1(4068, bull=True)]       # touch -> recovery -> BOS
    seqB = [bar1(4070, bull=True), bar1(4058, l=4050), bar1(4066)]       # BOS -> touch -> recovery
    ra, rb = [], []
    for seq, out in ((seqA, ra), (seqB, rb)):
        e = zone_engine()
        _one(e, c, SUP_Z, [bar1(4080)], bar=1, t=60)
        out.append(_one(e, c, SUP_Z, seq, bar=2, t=120)["reboundLong"])
    agg = any(b[3] for b in seqB) and max(b[0] for b in seqB) >= 4065       # what a 5M aggregation would conclude
    check("B07 one 5M bar: [touch, recovery, BOS] -> rebound; [BOS, touch, recovery] -> none (1M order kept, "
          "not aggregated)", ra == [True] and rb == [False] and agg, f"A={ra} B={rb}")

    # ---- B08 lower-TF transitions + 5M break in the same chart bar ---------
    e = zone_engine()
    _one(e, c, SUP_Z, [bar1(4080)], bar=1, t=60)
    r = _one(e, c, SUP_Z, [bar1(4050, l=4046), bar1(4066), bar1(4040)], brk=4040.0, bar=2, t=120)
    q = e["evts"][0]
    check("B08 1M steps (event create, reclaim-level close) run first, then 5M break once: breakShort, phase 1, "
          "no Fake in the same chart bar", r["breakShort"] and q["phase"] == 1 and not r["fakeLong"]
          and q["breakBar"] == e["barNo"])
    r2 = _one(e, c, SUP_Z, [bar1(4066), bar1(4068, bull=True)], bar=3, t=180)
    check("B08 Fake becomes possible only from the next chart bar's 1M steps", r2["fakeLong"])

    # ---- B09 expiry boundaries (== stays, > expires) -----------------------
    cw = ZCfg(useBreak=False, waitBars=3, fakeMaxBars=2)
    def phase0_alive(el):
        e = zone_engine()
        _seed_event(e, zoneId=7, roleCycle=1, top=4065.0, bottom=4045.0, side=1, startBar=0)
        e["barNo"] = el - 1
        _one(e, cw, [], [bar1(4070)])
        return e["evts"][0]["alive"]
    check("B09 phase 0: elapsed == waitBars alive; waitBars+1 dead", phase0_alive(3) and not phase0_alive(4))
    cb = ZCfg(useBreak=True, waitBars=3, breakWaitBars=6)
    e = zone_engine()
    _seed_event(e, zoneId=7, roleCycle=1, top=4065.0, bottom=4045.0, side=1, startBar=0)
    e["barNo"] = 3
    _one(e, cb, [], [bar1(4070)])
    bk4 = (e["evts"][0]["bkOnly"], e["evts"][0]["alive"])
    e["barNo"] = 5
    _one(e, cb, [], [bar1(4070)])
    bk6 = (e["evts"][0]["bkOnly"], e["evts"][0]["alive"])
    _one(e, cb, [], [bar1(4070)])
    bk7 = e["evts"][0]["alive"] if e["evts"] else False
    check("B09 phase 0 with Break: elapsed waitBars+1 -> bkOnly but alive; == breakWaitBars alive; +1 dead",
          bk4 == (True, True) and bk6 == (True, True) and not bk7, f"{bk4} {bk6} {bk7}")
    def phase1(el):
        e = zone_engine()
        _seed_event(e, zoneId=7, roleCycle=1, top=4065.0, bottom=4045.0, side=1, startBar=0, phase=1, breakBar=0,
                    fakeAlive=True)
        e["barNo"] = el - 1
        _one(e, cw, [], [bar1(4050)])
        return e["evts"][0]["fakeAlive"], e["evts"][0]["alive"]
    check("B09 phase 1: fakeAlive kept at el == fakeMaxBars, lost at +1; alive kept at el == max(fake,wait), dead at +1",
          phase1(2) == (True, True) and phase1(3) == (False, True) and phase1(3)[1] and phase1(4) == (False, False),
          f"{phase1(2)} {phase1(3)} {phase1(4)}")
    def phase2(el, touched):
        e = zone_engine()
        _seed_event(e, zoneId=7, roleCycle=1, top=4065.0, bottom=4045.0, side=1, startBar=0, phase=2, rearmBar=0,
                    touched=touched, touchBar=0 if touched else None)
        e["barNo"] = el - 1
        _one(e, cw, [], [bar1(4030, h=4031, l=4029)])
        return e["evts"][0]["alive"]
    check("B09 phase 2: not touched rearm+waitBars alive / +1 dead; touched touch+waitBars alive / +1 dead",
          phase2(3, False) and not phase2(4, False) and phase2(3, True) and not phase2(4, True))

    # ---- B10 event FIFO 60 --------------------------------------------------
    e = zone_engine()
    for k in range(61):
        _seed_event(e, zoneId=100 + k, roleCycle=1, top=4065.0, bottom=4045.0, side=1, startBar=0)
    _one(e, ZCfg(useBreak=False, waitBars=10_000), [], [])
    check("B10 61 alive events -> oldest (index 0) dropped at the start of the next update; 60 remain",
          len(e["evts"]) == 60 and e["evts"][0]["zoneId"] == 101)
    e = zone_engine()
    for k in range(61):
        _seed_event(e, zoneId=100 + k, roleCycle=1, top=4065.0, bottom=4045.0, side=1, startBar=0, bkOnly=(k == 30))
    _one(e, ZCfg(useBreak=True, waitBars=10_000, breakWaitBars=10_000), [], [])
    check("B10 bkOnly event dropped before older normal events", len(e["evts"]) == 60
          and 130 not in [q["zoneId"] for q in e["evts"]] and e["evts"][0]["zoneId"] == 100)
    e = zone_engine()
    for k in range(3):
        _seed_event(e, zoneId=100 + k, roleCycle=1, top=4065.0, bottom=4045.0, side=1, startBar=0)
    e["evts"][0]["alive"] = False
    e["sigRebound"] = 2
    idx_ok = e["evts"][2]["zoneId"] == 102            # index valid until the next update (dead not swept yet)
    _one(e, ZCfg(useBreak=False, waitBars=10_000), [], [])
    check("B10 dead events are swept only at the start of the next update (consume index stays valid until then)",
          idx_ok and [q["zoneId"] for q in e["evts"]] == [101, 102])

    # ---- B11 role table cleanup boundary -----------------------------------
    def role_case(age):
        e = zone_engine()
        for k in range(201):
            e["roleZoneId"].append(k); e["roleSide"].append(1); e["roleCycleNo"].append(3)
            e["roleSeen"].append(False); e["roleSeenBar"].append(5000 - age if k == 0 else 5000)
        cleanup = len(e["roleZoneId"]) > 200
        if cleanup:
            keep = [i for i in range(len(e["roleZoneId"])) if not (5000 - e["roleSeenBar"][i] > 1000)]
            for key in ("roleZoneId", "roleSide", "roleCycleNo", "roleSeen", "roleSeenBar"):
                e[key] = [e[key][i] for i in keep]
        return 0 in e["roleZoneId"]
    NEWS_UZ = func_block(NEWS, "updateZoneEvents")
    check("B11 static: cleanup only when table > 200 rows and rows unseen > 1000 chart bars",
          "if array.size(e.roleZoneId) > 200" in NEWS_UZ and "bar_index - array.get(e.roleSeenBar, i) > 1000" in NEWS_UZ)
    check("B11 unseen == 1000 bars kept; 1001 removed", role_case(1000) and not role_case(1001))
    e = zone_engine()
    _one(e, c, SUP_Z, [bar1(4080)], bar=1)
    e["roleCycleNo"][0] = 5                                         # simulate an old zone at cycle 5
    e["roleZoneId"], e["roleSide"], e["roleCycleNo"], e["roleSeen"], e["roleSeenBar"] = [], [], [], [], []   # cleaned
    _one(e, c, SUP_Z, [bar1(4080)], bar=2000)
    check("B11 after cleanup a returning zone restarts at roleCycle 1 (canonical); duplicate check still uses "
          "zoneId+side+roleCycle", e["roleCycleNo"] == [1])

    # ---- B12 bkOnly does not block a new Rebound registration --------------
    cb2 = ZCfg(useBreak=True, waitBars=2, breakWaitBars=50)
    e = zone_engine()
    _one(e, cb2, SUP_Z, [bar1(4080)], bar=1)
    _one(e, cb2, SUP_Z, [bar1(4058, l=4050)], bar=2)                                  # event (cycle 1)
    _one(e, cb2, SUP_Z, [bar1(4070), bar1(4071), bar1(4072)], bar=3)                  # > waitBars -> bkOnly
    first_bk = e["evts"][0]["bkOnly"] and e["evts"][0]["alive"]
    _one(e, cb2, SUP_Z, [bar1(4058, l=4050)], bar=4)                                  # same zone/side/cycle again
    check("B12 bkOnly (break-only, extended) event does not block a new Rebound event of the same zone/side/cycle",
          first_bk and len(e["evts"]) == 2 and not e["evts"][1]["bkOnly"] and e["evts"][1]["roleCycle"] == 1)


# ---- static compile readiness (spec 13) --------------------------------------
PINE_KEYWORDS = {"if", "else", "for", "while", "switch", "and", "or", "not", "to", "by", "true", "false", "na",
                 "var", "varip", "export", "type", "import", "return", "continue", "break", "in"}
PINE_BUILTIN_CALLS = {"na", "nz", "int", "float", "bool", "string", "color", "fixnan", "library", "time",
                      "max", "min"}


def fixture_p06_compile():
    NEWS = open(os.path.join(ROOT, "SignalEnginePractical.pine"), encoding="utf-8").read()
    code = code_only(NEWS)
    code_ns = re.sub(r'"[^"]*"', '""', code)
    defs = re.findall(r"^(?:export\s+)?(\w+)\(.*?\)\s*=>", code_ns, re.M | re.S)
    defs_simple = re.findall(r"^(?:export\s+)?(\w+)\(", code_ns, re.M)
    types = set(re.findall(r"^export type (\w+)", code_ns, re.M))
    dup = sorted({d for d in defs_simple if defs_simple.count(d) > 1})
    check("C1 no duplicate function definitions", not dup, str(dup))
    calls = set(re.findall(r"(?<![\w.])([A-Za-z_]\w*)\(", code_ns))
    undefined = sorted(c_ for c_ in calls if c_ not in set(defs_simple) and c_ not in PINE_KEYWORDS
                       and c_ not in PINE_BUILTIN_CALLS)
    check("C2 every non-namespaced call resolves to a function defined in the file or a Pine builtin",
          not undefined, str(undefined))
    tcalls = set(re.findall(r"\b([A-Z]\w*)\.new\(", code_ns))
    check("C3 every Type.new / type reference is an exported type of this file", tcalls <= types,
          str(sorted(tcalls - types)))
    used_types = set(re.findall(r"\b([A-Z][A-Za-z0-9]+)\s+\w+\s*[,)=]", code_ns)) & (set(OT) | types)
    check("C3 no parameter / variable of a removed type (ZoneBos*)", not (used_types - types), str(used_types - types))
    kept_fields = {f for t in parse_types(NEWS).values() for f in t}
    bad_args, bad_dot = [], []
    for t, fs in REMOVED.items():
        for blk in re.findall(r"\b" + t + r"\.new\((.*?)\)\s*(?:\n|$)", code_ns, re.S):
            names = re.findall(r"(\w+)\s*=(?!=)", blk)
            bad_args += [f"{t}.{x}" for x in names if x in fs]
        bad_dot += [f"{t}.{x}" for x in fs if x not in kept_fields and re.search(r"\.\s*" + x + r"\b", code_ns)]
    check("C4 no removed field passed to its Type.new(...) and no .field access to a field no kept type owns",
          not bad_args and not bad_dot, f"args={bad_args} dot={bad_dot}")
    order_bad = []
    defined_at = {}
    for i, ln in enumerate(code_ns.split("\n")):
        m = re.match(r"^(?:export\s+)?(\w+)\(", ln)
        if m:
            defined_at.setdefault(m.group(1), i)
    for name, i in defined_at.items():
        blk = func_block(code_ns, name)
        for cl in set(re.findall(r"(?<![\w.])([A-Za-z_]\w*)\(", blk)) - {name}:
            if cl in defined_at and defined_at[cl] > i:
                order_bad.append(f"{name}->{cl}")
    check("C5 every local function is defined before it is called (Pine declaration order)", not order_bad,
          str(order_bad))


# =============================================================================
# P07 — TradePlan / Inside Any Zone / TP Mode / Risk / Qty
# =============================================================================
TH_PATH = os.path.join(ROOT, "PracticalTradeHarness.pine")
TH = open(TH_PATH, encoding="utf-8").read() if os.path.exists(TH_PATH) else ""
LEG_ZE = open(os.path.join(ROOT, "ZoneEngine.pine"), encoding="utf-8").read()


def fixture_p07_static():
    check("P07 harness file exists", bool(TH))
    if not TH:
        return
    HI, MI = parse_inputs(TH), parse_inputs(MAIN)
    names = ["slBuffer", "tpBuffer", "maxSlDist", "minStructRR", "tpMode", "slMinScore", "slMinStrStr", "tpMinScore",
             "tpMinStrStr", "obsMinStrStr", "activeNoTradeMinStrStr", "structuralTpDepthRatio", "fallbackRR",
             "riskPct", "useCompound", "qtyStep", "qtyMin", "breakLongRefCompat", "breakLongTpDepthRatio"]
    diff = [n for n in names if HI.get(n) != MI.get(n)]
    check("PS1 TradePlan / TP Mode / Risk / Qty inputs == old Main (name/kind/default/title/group/options/min/max/step)",
          not diff, f"{len(names)} inputs" if not diff else f"diff={diff}")
    for fn in ("f_baseCapital", "f_riskCapital", "f_qty", "f_tpDepthFor"):
        check(f"PS2 {fn} verbatim from old Main", func_block(TH, fn) == func_block(MAIN, fn) and func_block(TH, fn) != "")
    tpm = lambda src: re.findall(r'if tpMode == "STRUCTURAL_ONLY" and p\.tpType == "FALLBACK_RR".*?p\.reason := "STRUCTURAL_TP_EXISTS"',
                                 code_only(src), re.S)
    norm = lambda t: [" ".join(x.split()) for x in t]
    check("PS3 TP Mode filter identical to old Main f_submitSignal (PASS -> FAIL only)",
          norm(tpm(func_block(TH, "f_evalEntry"))) == norm(tpm(func_block(MAIN, "f_submitSignal"))) != [])
    hz = section(HAR, r"^// 01-2\. ZONE ENGINE INPUTS", r"^// zn\.update は上の1回だけ")
    tz = section(TH, r"^// 01-2\. ZONE ENGINE INPUTS", r"^// =+\n// 04\. TRADE PLAN")
    strip = lambda t: [l for l in code_only(t).split("\n") if l.strip()]
    tooltip_fix = lambda ls: [l.replace('     "Dynamic TP にも同じ定義がそのまま使われる。")', '     "")') for l in ls]
    check("PS4 Zone block (inputs / ZoneCfg first-bar / feed / zn.update) == P02 harness (code identical; "
          "only a Dynamic-TP tooltip/comment removed)", tooltip_fix(strip(hz)) == strip(tz), f"{len(strip(tz))} lines")
    tc = code_only(TH)
    check("PS5 one ZoneEngine, one zn.update, ZoneCfg only written inside barstate.isfirst",
          len(re.findall(r"zn\.newEngine\(", tc)) == 1 and len(re.findall(r"\bzn\.update\(", tc)) == 1 and
          all(re.match(r"^    zoneCfg\.", l) for l in tc.split("\n") if re.search(r"zoneCfg\.\w+\s*:=", l)))
    check("PS5 Structural SL/TP not reimplemented: only zn.buildPlanWithTpDepth is used (1 call site)",
          len(re.findall(r"zn\.buildPlanWithTpDepth\(", tc)) == 1 and
          not re.search(r"zn\.(getLong|getShort)Structural|zn\.buildPlan\(", tc))
    body = code_only(func_block(TH, "f_evalEntry"))
    order = [body.find(x) for x in ("if dir == 0", "else if insideBlocked", "zn.buildPlanWithTpDepth",
                                    'if tpMode == "STRUCTURAL_ONLY"', "if not isGold", "else if not p.valid",
                                    "float qty = f_qty(p.risk)", "if qty < qtyMin or qty <= 0")]
    check("PS6 gate order: dir -> Inside Any Zone -> buildPlan -> TP Mode -> Gold -> valid -> Qty -> qtyMin",
          -1 not in order and order == sorted(order), str(order))
    m_ex = code_only(func_block(MAIN, "f_executeTrade"))
    check("PS6 old Main reference order: isGold -> valid -> qty -> (logicFull / opposite = P08) -> qtyMin",
          m_ex.find("if isGold") < m_ex.find("if not p.valid") < m_ex.find("float qty = f_qty(p.risk)") <
          m_ex.find("else if qty < qtyMin or qty <= 0"))
    bad = [t for t in ("strategy.entry", "strategy.exit", "strategy.close", "alert(", "alertcondition", "map.new",
                       "opentrades", "closedtrades", "box.new", "label.new", "table.new", "tpManagementMode",
                       "Dynamic", "useBreakEven", "SignalEngine") if t in tc]
    check("PS7 prohibited in harness code: orders / alerts / map / trade scans / drawing / Dynamic TP / BE / Signal",
          not bad, str(bad))
    scan = code_only(func_block(TH, "f_insideAnyZone"))
    check("PS8 Inside Any Zone: one loop over live zones, no state filter, break on first hit, scalar results",
          scan.count("for ") == 1 and "z.state" not in scan and "break" in scan and
          "zoneCfg.activeNoTradeMinStrength" in scan and "entryPrice >= z.bottom and entryPrice <= z.top" in scan)
    probe = code_only(TH[TH.find("// 06. PROBE"):])
    check("PS8 probe computes the Inside gate once per bar and shares it for Long and Short",
          probe.count("f_insideAnyZone(") == 1 and probe.count("f_evalEntry(") == 2)
    for fn in ("getLongStructuralSL", "getShortStructuralSL", "getLongStructuralTpAt", "getShortStructuralTpAt",
               "getObstacleCount", "isInsideActiveZone", "buildPlanWithTpDepth", "buildPlan"):
        check(f"PS9 ZoneEnginePractical.{fn} == legacy ZoneEngine (canonical TradePlan API)",
              func_block(ZEP, fn) == func_block(LEG_ZE, fn) and func_block(ZEP, fn) != "")


# ---- Python mirror: ZoneEnginePractical TradePlan API + harness evaluator -----
class TCfg:
    def __init__(self, **kw):
        d = dict(slBuffer=5.0, tpBuffer=0.0, maxSlDist=30.0, minStructRR=1.0, slMinScore=4.0, slMinStrength=2,
                 tpMinScore=7.0, tpMinStrength=3, obsMinStrength=2, activeNoTradeMinStrength=2,
                 structuralTpDepthRatio=0.25, fallbackRR=2.0)
        d.update(kw)
        self.__dict__.update(d)


ST_ACT, ST_SUP_, ST_RES_, ST_BRK = 0, 1, 2, 3


def Z(bottom, top, state, strength=3, score=12.0, tid=1):
    return dict(bottom=bottom, top=top, center=(bottom + top) / 2, state=state, strength=strength, score=score,
                trackId=tid)


def long_sl(live, c, entry):
    sl, idx, best = None, -1, 1e20
    for i, z in enumerate(live):
        if z["top"] < entry and z["strength"] >= c.slMinStrength and z["score"] >= c.slMinScore and z["state"] == ST_SUP_:
            d = entry - z["top"]
            if d < best:
                best, sl, idx = d, z["bottom"] - c.slBuffer, i
    return sl, idx


def short_sl(live, c, entry):
    sl, idx, best = None, -1, 1e20
    for i, z in enumerate(live):
        if z["bottom"] > entry and z["strength"] >= c.slMinStrength and z["score"] >= c.slMinScore and z["state"] == ST_RES_:
            d = z["bottom"] - entry
            if d < best:
                best, sl, idx = d, z["top"] + c.slBuffer, i
    return sl, idx


def long_tp(live, c, entry, depth):
    r = c.structuralTpDepthRatio if depth is None else depth
    tp, idx, best = None, -1, 1e20
    for i, z in enumerate(live):
        if z["bottom"] > entry and z["strength"] >= c.tpMinStrength and z["score"] >= c.tpMinScore and z["state"] == ST_RES_:
            d = z["bottom"] - entry
            if d < best:
                best, tp, idx = d, z["bottom"] + (z["top"] - z["bottom"]) * r - c.tpBuffer, i
    return tp, idx


def short_tp(live, c, entry, depth):
    r = c.structuralTpDepthRatio if depth is None else depth
    tp, idx, best = None, -1, 1e20
    for i, z in enumerate(live):
        if z["top"] < entry and z["strength"] >= c.tpMinStrength and z["score"] >= c.tpMinScore and z["state"] == ST_SUP_:
            d = entry - z["top"]
            if d < best:
                best, tp, idx = d, z["top"] - (z["top"] - z["bottom"]) * r + c.tpBuffer, i
    return tp, idx


def obstacles(live, c, entry, tp, d):
    if entry is None or tp is None:
        return 0
    b = tp + c.tpBuffer if d > 0 else tp - c.tpBuffer
    return sum(1 for z in live if z["strength"] >= c.obsMinStrength and z["state"] == (ST_RES_ if d > 0 else ST_SUP_)
               and ((z["bottom"] > entry and z["top"] < b) if d > 0 else (z["top"] < entry and z["bottom"] > b)))


def inside_active(live, c, entry):
    return any(z["state"] == ST_ACT and z["bottom"] <= entry <= z["top"] and z["strength"] >= c.activeNoTradeMinStrength
               for z in live)


def build_plan(live, c, d, entry, depth=None):
    lsl, lsi = long_sl(live, c, entry)
    ltp, lti = long_tp(live, c, entry, depth)
    ssl, ssi = short_sl(live, c, entry)
    stp, sti = short_tp(live, c, entry, depth)
    sl = lsl if d > 0 else ssl if d < 0 else None
    si = lsi if d > 0 else ssi if d < 0 else -1
    tpz = ltp if d > 0 else stp if d < 0 else None
    ti = lti if d > 0 else sti if d < 0 else -1
    risk = None if sl is None or entry is None else abs(entry - sl)
    p = dict(valid=False, status="FAIL", reason="NO_ENTRY", dir=d, entry=entry, sl=sl, risk=risk, tp=0.0, reward=0.0,
             rr=0.0, tpType="-", usedFallbackTP=False, obstacles=0)
    if d == 0:
        p["reason"] = "NO_ENTRY"
    elif inside_active(live, c, entry):
        p["reason"] = "INSIDE_ACTIVE_ZONE"
    elif si < 0 or sl is None:
        p["reason"] = "NO_SL_ZONE"
    elif risk is None or risk <= 0:
        p["reason"] = "INVALID_SL"
    elif risk > c.maxSlDist:
        p["reason"] = "SL_TOO_FAR"
    elif ti >= 0:
        p.update(tp=tpz, reward=abs(tpz - entry), tpType="STRUCTURAL")
        p["rr"] = p["reward"] / risk if risk > 0 else None
        p["obstacles"] = obstacles(live, c, entry, tpz, d)
        if p["reward"] <= 0:
            p["reason"] = "TP_WRONG_SIDE"
        elif p["rr"] is None or p["rr"] < c.minStructRR:
            p["reason"] = "LOW_STRUCTURAL_RR"
        else:
            p.update(valid=True, status="PASS", reason="OK_STRUCTURAL_TP")
    else:
        ftp = entry + d * risk * c.fallbackRR
        p.update(tp=ftp, reward=abs(ftp - entry), rr=c.fallbackRR, usedFallbackTP=True, tpType="FALLBACK_RR",
                 valid=True, status="PASS", reason="OK_FALLBACK_TP")
        p["obstacles"] = obstacles(live, c, entry, ftp, d)
    return p


def f_qty_(risk, capital=1000.0, riskPct=5.0, pointvalue=1.0, qtyStep=1.0):
    raw = capital * riskPct / 100.0 / (risk * pointvalue) if risk > 0 else 0.0
    q = math.floor(raw / qtyStep) * qtyStep if qtyStep > 0 else raw
    return round(q, 8)


def inside_any(live, c, entry):
    for z in live:
        if z["strength"] >= c.activeNoTradeMinStrength and z["bottom"] <= entry <= z["top"]:
            return True, z["trackId"], z["strength"]
    return False, None, None


def eval_entry(live, c, d, entry, tpMode="BOTH", depth=None, isGold=True, qtyMin=0.01, **qkw):
    if d == 0:
        return dict(ready=False, reason="NO_ENTRY", plan=None, qty=None)
    blocked, _, _ = inside_any(live, c, entry)
    if blocked:
        return dict(ready=False, reason="INSIDE_ANY_ZONE", plan=None, qty=None)
    p = build_plan(live, c, d, entry, depth)
    if tpMode == "STRUCTURAL_ONLY" and p["tpType"] == "FALLBACK_RR":
        p.update(valid=False, status="FAIL", reason="NO_STRUCTURAL_TP")
    elif tpMode == "FALLBACK_ONLY" and p["tpType"] == "STRUCTURAL":
        p.update(valid=False, status="FAIL", reason="STRUCTURAL_TP_EXISTS")
    if not isGold:
        return dict(ready=False, reason="NOT_GOLD", plan=p, qty=None)
    if not p["valid"]:
        return dict(ready=False, reason=p["reason"], plan=p, qty=None)
    q = f_qty_(p["risk"], **qkw)
    if q < qtyMin or q <= 0:
        return dict(ready=False, reason="SKIP_NO_QTY", plan=p, qty=q)
    return dict(ready=True, reason="ENTRY_READY", plan=p, qty=q)


def fixture_p07_behaviour():
    c = TCfg()
    sup = Z(4030, 4040, ST_SUP_, tid=1)                 # Support below entry 4050
    sup_far = Z(4000, 4010, ST_SUP_, tid=2)
    res = Z(4070, 4080, ST_RES_, tid=3)                 # Resistance above
    res_far = Z(4100, 4110, ST_RES_, tid=4)
    live = [sup_far, sup, res, res_far]
    # T01 / T02 SL
    sl, i = long_sl(live, c, 4050)
    check("T01 Long SL = nearest valid Support below entry: bottom - slBuffer (4030-5)", sl == 4025 and i == 1)
    sl, i = short_sl(live, c, 4050)
    check("T02 Short SL = nearest valid Resistance above entry: top + slBuffer (4080+5)", sl == 4085 and i == 2)
    # T03 / T04 TP selection
    tp, i = long_tp(live, c, 4050, 0.0)
    check("T03 Long TP = nearest Resistance above (bottom 4070 at depth 0)", tp == 4070 and i == 2)
    tp, i = short_tp(live, c, 4050, 0.0)
    check("T04 Short TP = nearest Support below (top 4040 at depth 0)", tp == 4040 and i == 1)
    # T05 TP depth
    ld = [long_tp(live, c, 4050, d_)[0] for d_ in (0.0, 0.25, 0.5, 1.0)]
    sd = [short_tp(live, c, 4050, d_)[0] for d_ in (0.0, 0.25, 0.5, 1.0)]
    check("T05 TP depth 0 / 0.25 / 0.5 / 1.0 (Long 4070..4080, Short 4040..4030)",
          ld == [4070, 4072.5, 4075, 4080] and sd == [4040, 4037.5, 4035, 4030], f"{ld} {sd}")
    check("T05 Logic TP depth is an argument (ZoneCfg.structuralTpDepthRatio unchanged)",
          c.structuralTpDepthRatio == 0.25 and build_plan(live, c, 1, 4050, 0.0)["tp"] == 4070)
    # T06 / T07
    check("T06 NO_SL_ZONE", build_plan([res], c, 1, 4050)["reason"] == "NO_SL_ZONE")
    check("T07 SL_TOO_FAR (risk 4050-(4000-5)=55 > 30)", build_plan([sup_far, res], c, 1, 4050)["reason"] == "SL_TOO_FAR")
    # T08 Structural RR boundary: risk = 4050-4025 = 25 -> RR == 1 at TP 4075
    eq = build_plan([sup, Z(4075, 4085, ST_RES_)], c, 1, 4050, 0.0)
    lo = build_plan([sup, Z(4074.99, 4085, ST_RES_)], c, 1, 4050, 0.0)
    check("T08 Structural RR == minStructRR -> PASS; below -> LOW_STRUCTURAL_RR", eq["valid"] and eq["rr"] == 1.0
          and lo["reason"] == "LOW_STRUCTURAL_RR", f"{eq['reason']} {lo['reason']}")
    # T09 / T10
    fb = build_plan([sup], c, 1, 4050)
    check("T09 no Structural TP -> Fallback RR TP (entry + risk*2)", fb["valid"] and fb["tpType"] == "FALLBACK_RR"
          and fb["tp"] == 4100)
    check("T10 Structural TP exists but RR short -> FAIL, never escapes to Fallback",
          lo["tpType"] == "STRUCTURAL" and not lo["valid"] and not lo["usedFallbackTP"])
    # T11-T13 TP Mode
    ok_s = eval_entry([sup, res_far], c, 1, 4050)
    ok_f = eval_entry([sup], c, 1, 4050)
    check("T11 BOTH: Structural and Fallback both ENTRY_READY", ok_s["ready"] and ok_f["ready"])
    r1 = eval_entry([sup, res_far], c, 1, 4050, tpMode="STRUCTURAL_ONLY")
    r2 = eval_entry([sup], c, 1, 4050, tpMode="STRUCTURAL_ONLY")
    check("T12 STRUCTURAL_ONLY: structural READY; fallback -> NO_STRUCTURAL_TP", r1["ready"] and r2["reason"] == "NO_STRUCTURAL_TP")
    r3 = eval_entry([sup, res_far], c, 1, 4050, tpMode="FALLBACK_ONLY")
    r4 = eval_entry([sup], c, 1, 4050, tpMode="FALLBACK_ONLY")
    r5 = eval_entry([sup, Z(4074.99, 4085, ST_RES_)], c, 1, 4050, tpMode="FALLBACK_ONLY", depth=0.0)
    check("T13 FALLBACK_ONLY: structural -> STRUCTURAL_TP_EXISTS; fallback READY; LOW_RR plan relabelled (canonical)",
          r3["reason"] == "STRUCTURAL_TP_EXISTS" and r4["ready"] and r5["reason"] == "STRUCTURAL_TP_EXISTS")
    # T14-T19 Inside Any Zone
    for tag, st in (("T14 Support", ST_SUP_), ("T15 Resistance", ST_RES_), ("T16 Active", ST_ACT), ("T17 Broken", ST_BRK)):
        r = eval_entry([sup, Z(4045, 4055, st, tid=9), res_far], c, 1, 4050)
        check(f"{tag}: entry inside a Strong zone -> INSIDE_ANY_ZONE (state ignored)", r["reason"] == "INSIDE_ANY_ZONE")
    weak = eval_entry([sup, Z(4045, 4055, ST_SUP_, strength=1, tid=9), res_far], c, 1, 4050)
    check("T18 zone strength below activeNoTradeMinStrength -> not blocked by the added gate", weak["ready"])
    check("T19 entry == top and entry == bottom are inside",
          inside_any([Z(4045, 4050, ST_SUP_)], c, 4050)[0] and inside_any([Z(4050, 4055, ST_RES_)], c, 4050)[0])
    check("T19b legacy buildPlan alone would NOT block Support/Resistance/Broken (only ACTIVE) -> gate is the intended diff",
          build_plan([sup, Z(4045, 4055, ST_SUP_), res_far], c, 1, 4050)["valid"] and
          build_plan([sup, Z(4045, 4055, ST_ACT), res_far], c, 1, 4050)["reason"] == "INSIDE_ACTIVE_ZONE")
    # T20-T23 Qty (old Main formula: floor(capital*risk%/(risk*pointvalue)/step)*step)
    qL = eval_entry([sup, res_far], c, 1, 4050)
    qS = eval_entry([Z(4060, 4070, ST_RES_), Z(4000, 4010, ST_SUP_)], c, -1, 4050)
    check("T20 Qty Long: risk 25 -> floor(50/25 / 1)*1 = 2", qL["qty"] == 2.0, str(qL["qty"]))
    check("T21 Qty Short: risk 25 (SL 4075) -> 2", qS["ready"] and qS["qty"] == 2.0, str(qS["qty"]))
    check("T21b qtyStep 0.01 keeps decimals: 50/7 -> 7.14", f_qty_(7.0, qtyStep=0.01) == 7.14)
    big = TCfg(maxSlDist=10_000)
    # SL = bottom(-10) - slBuffer(5) = -15 -> entry 4985: risk 5000 -> 50/5000 = 0.01; entry 4986: risk 5001 -> 0.00
    mn = eval_entry([Z(-10, 0, ST_SUP_), Z(20000, 20010, ST_RES_)], big, 1, 4985, qtyMin=0.01, qtyStep=0.01)
    under = eval_entry([Z(-10, 0, ST_SUP_), Z(20000, 20010, ST_RES_)], big, 1, 4986, qtyMin=0.01, qtyStep=0.01)
    check("T22 Qty == qtyMin passes (risk 5000 -> 0.01); below qtyMin -> SKIP_NO_QTY",
          mn["ready"] and mn["qty"] == 0.01 and under["reason"] == "SKIP_NO_QTY", f"{mn['qty']} {under['qty']}")
    stepped = eval_entry([sup, res_far], TCfg(maxSlDist=100), 1, 4050, qtyMin=0.01, capital=10.0)
    check("T23 integer qtyStep with tiny risk capital -> qty 0 -> SKIP_NO_QTY (never ENTRY_READY)",
          stepped["reason"] == "SKIP_NO_QTY" and not stepped["ready"])
    check("T23b invalid SL (no SL zone) / wrong side never reaches Qty", eval_entry([res], c, 1, 4050)["qty"] is None)
    check("T23c non-Gold symbol never ENTRY_READY", eval_entry([sup, res_far], c, 1, 4050, isGold=False)["reason"] == "NOT_GOLD")


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
    fixture_p03_static()
    fixture_p03_behaviour()
    fixture_p03_fvg15()
    fixture_p04_static()
    fixture_p04_behaviour()
    fixture_p05_static()
    fixture_p05_events()
    fixture_p05_rebound_break()
    fixture_p05_fake_retest()
    fixture_p05_consume_preview()
    fixture_p06_boundaries()
    fixture_p06_compile()
    fixture_p07_static()
    fixture_p07_behaviour()
    width = max(len(n) for n, _, _ in RESULTS)
    fails = 0
    for name, ok, detail in RESULTS:
        fails += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {name.ljust(width)}  {detail}")
    print(f"\n{len(RESULTS) - fails}/{len(RESULTS)} passed  [PINE_NOT_VERIFIED: static / mirror checks]")
    raise SystemExit(1 if fails else 0)
