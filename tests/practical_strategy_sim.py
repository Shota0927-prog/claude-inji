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
#  ★ P02-P10 parity fixtures validate against the Visual authority of that stage (b3b69ae).
#    The current Visual adds only the 5M execution gate; fixture_p16_visual_5m_gate ties it to b3b69ae.
VIS_PRE_GATE_REV = "b3b69ae"
VIS_CUR = open(os.path.join(ROOT, "ZoneVisualPractical.pine"), encoding="utf-8").read()
VIS = __import__("subprocess").run(["git", "-C", ROOT, "show", VIS_PRE_GATE_REV + ":ZoneVisualPractical.pine"],
                                   capture_output=True, text=True).stdout or VIS_CUR
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


# ============================================================================
# P08 : Global 1-Position Gate / same-bar Gate / Priority / Entry Dispatch
# ============================================================================
DH_PATH = os.path.join(ROOT, "PracticalEntryDispatchHarness.pine")
DH = open(DH_PATH, encoding="utf-8").read() if os.path.exists(DH_PATH) else ""
P08_ORDER = ["FVG15", "FVG", "FVGABS15", "FVGABS5", "ZONEREBOUND", "ZONEFAKE", "ZONERETEST", "ZONEBREAK"]
P08_CONST = {"LOGIC_FVG15": "FVG15", "LOGIC_FVG": "FVG", "LOGIC_FVG_ABS15": "FVGABS15", "LOGIC_FVG_ABS5": "FVGABS5",
             "LOGIC_ZONE_RB": "ZONEREBOUND", "LOGIC_ZONE_FK": "ZONEFAKE", "LOGIC_ZONE_RT": "ZONERETEST",
             "LOGIC_ZONE_BK": "ZONEBREAK"}
P08_TAG = {"FVG15": "FVG15", "FVG": "FVG", "FVGABS15": "ABS15", "FVGABS5": "ABS5", "ZONEREBOUND": "ZRB",
           "ZONEFAKE": "ZFK", "ZONERETEST": "ZRT", "ZONEBREAK": "ZBK"}


def fixture_p08_static():
    check("P08 harness file exists", bool(DH))
    if not DH:
        return
    dc = code_only(DH)
    # ---- reuse of P07 (Zone / Inside / TradePlan / TP Mode / Risk / Qty / f_tpDepthFor) ----
    cut = lambda src: src[src.find("import sekine3310/ZoneEnginePractical/3 as zn"):src.find("// ---- Entry 可否の評価結果")
                                                                                     if "// ---- Entry 可否の評価結果" in src
                                                                                     else src.find("// 06. ENTRY DISPATCH")]
    strip = lambda t: [l for l in code_only(t).split("\n") if l.strip()]
    a, b = strip(cut(TH)), strip(cut(DH))
    check("PD1 Zone block / inputs / ZoneCfg / Feed / zn.update / Risk / Qty / f_tpDepthFor / Inside Gate == P07 (code identical)",
          a == b and len(a) > 300, f"{len(b)} lines")
    for fn in ("f_insideAnyZone", "f_qty", "f_tpDepthFor", "f_baseCapital", "f_riskCapital"):
        check(f"PD1 {fn} identical to P07", func_block(DH, fn) == func_block(TH, fn) != "")
    check("PD1 one ZoneEngine / one zn.update / ZoneCfg only in barstate.isfirst",
          len(re.findall(r"zn\.newEngine\(", dc)) == 1 and len(re.findall(r"\bzn\.update\(", dc)) == 1 and
          all(re.match(r"^    zoneCfg\.", l) for l in dc.split("\n") if re.search(r"zoneCfg\.\w+\s*:=", l)))
    te = code_only(func_block(DH, "f_tryEntry"))
    tpm = lambda src: re.findall(r'if tpMode == "STRUCTURAL_ONLY" and p\.tpType == "FALLBACK_RR".*?p\.reason := "STRUCTURAL_TP_EXISTS"',
                                 code_only(src), re.S)
    norm = lambda t: [" ".join(x.split()) for x in t]
    check("PD2 TP Mode filter identical to old Main f_submitSignal (PASS -> FAIL only)",
          norm(tpm(te)) == norm(tpm(func_block(MAIN, "f_submitSignal"))) != [])
    gate = "if cand and dir != 0 and isGold and not positionBlocked and not enteredThisBar"
    toks = [gate, "f_insideAnyZone(entryPrice)", "zn.buildPlanWithTpDepth(", 'if tpMode == "STRUCTURAL_ONLY"',
            "if p.valid", "float qty = f_qty(p.risk)", "if qty >= qtyMin and qty > 0", "strategy.entry(",
            "strategy.exit(", "entered := true"]
    pos = [te.find(t) for t in toks]
    check("PD3 gate order: candidate -> dir -> isGold -> position -> enteredThisBar -> Inside -> buildPlan -> TP Mode "
          "-> valid -> Qty -> qtyMin -> entry -> exit -> entered", -1 not in pos and pos == sorted(pos), str(pos))
    check("PD3 Inside / buildPlan / Qty only reachable after the cheap gates (all nested under the gate line)",
          all(l.startswith("        ") for l in te.split("\n")[te[:pos[0]].count("\n") + 1:] if l.strip()
              and not l.strip().startswith("entered") and l.strip() != "bool entered = false"))
    check("PD3 isGold / position / same-bar gates evaluated before any Zone scan (Gold以外 / 保有中は走査なし)",
          te.find("isGold") < te.find("f_insideAnyZone") and te.find("positionBlocked") < te.find("f_insideAnyZone"))
    # ---- Global gate ----
    gl = re.findall(r"^bool globalPositionBlocked = (.*)$", dc, re.M)
    check("PD4 Global Position Gate = strategy.position_size != 0 or strategy.opentrades > 0 (scalar)",
          gl == ["strategy.position_size != 0 or strategy.opentrades > 0"], str(gl))
    # ---- dispatch order (execution order, not function order) ----
    disp = code_only(DH[DH.find("// 08. DISPATCH"):DH.find("// ---- Flat 遷移検知用")])
    calls = re.findall(r"e := f_tryEntry\(activePos, ds, (\w+), [^,]+, (-?1), [^,]+, globalPositionBlocked, enteredThisBar\)", disp)
    seq = [(P08_CONST.get(l), d) for l, d in calls]
    exp = [(l, d) for l in P08_ORDER for d in ("1", "-1")]
    check("PD5 dispatch execution order FVG15 -> FVG -> ABS15 -> ABS5 -> RB -> FK -> RT -> BK (Long then Short)",
          seq == exp, str([s_[0] for s_ in seq[::2]]))
    lines = [l.strip() for l in disp.split("\n") if l.strip()]
    ci = [i for i, l in enumerate(lines) if l.startswith("e := f_tryEntry(")]
    check("PD5 every dispatch call is immediately followed by enteredThisBar := enteredThisBar or e",
          len(ci) == 16 and all(lines[i + 1] == "enteredThisBar := enteredThisBar or e" for i in ci))
    check("PD5 enteredThisBar is a plain per-bar bool reset to false and the dispatch runs on confirmed bars only",
          re.search(r"^bool\s+enteredThisBar = false$", dc, re.M) is not None and "if barstate.isconfirmed" in disp
          and "var bool enteredThisBar" not in dc)
    # ---- entry / exit branch ----
    tl = te.split("\n")
    ei = [i for i, l in enumerate(tl) if "strategy.entry(" in l]
    xi = [i for i, l in enumerate(tl) if "strategy.exit(" in l]
    ind = lambda l: len(l) - len(l.lstrip())
    check("PD6 strategy.entry / strategy.exit: exactly one each, only in f_tryEntry, same branch",
          dc.count("strategy.entry(") == 1 and dc.count("strategy.exit(") == 1 and len(ei) == len(xi) == 1
          and ind(tl[ei[0]]) == ind(tl[xi[0]]) and 0 < xi[0] - ei[0] <= 2)
    check("PD6 SL / TP passed to strategy.exit are the entry-time plan values (stop = p.sl, limit = p.tp)",
          re.search(r'strategy\.exit\(eid \+ "X", from_entry = eid, stop = p\.sl, limit = p\.tp', te) is not None)
    tags = re.findall(r'(LOGIC_\w+)\s*\?\s*"(\w+)"', code_only(func_block(DH, "f_entryTag")))
    tagmap = {P08_CONST[k]: v for k, v in tags}
    check("PD7 Entry ID unique per Logic x direction (tag + _L / _S, no tag shared)",
          tagmap == P08_TAG and len(set(tagmap.values())) == 8 and 'f_entryTag(logicId) + (dir > 0 ? "_L" : "_S")' in te,
          str(tagmap))
    # ---- active state ----
    aw = [i for i, l in enumerate(tl) if re.match(r"\s*ap\.\w+\s*:=", l)]
    check("PD8 ActivePos written only inside the entered branch (after strategy.exit, same indentation)",
          aw and all(i > xi[0] and ind(tl[i]) == ind(tl[xi[0]]) for i in aw) and
          "activePos." not in re.sub(r"plot\(.*", "", dc[dc.find("// 08. DISPATCH"):]).replace("activePos, ds", ""))
    fields = set(re.findall(r"ap\.(\w+)\s*:=", te))
    check("PD8 entry stores entryId / logicId / dir / entryPrice / SL / TP / Qty",
          {"entryId", "logicId", "dir", "entryPrice", "sl", "tp", "qty"} <= fields, str(sorted(fields)))
    check("PD9 originTrackId / entryTouchCount slots exist and stay na (no guess before P11 / P12)",
          "ap.originTrackId   := na" in te and "ap.entryTouchCount := na" in te)
    check("PD10 flat transition detector present (scalar only), no BE processing attached",
          re.search(r"^bool flatTransition = not globalPositionBlocked and", dc, re.M) is not None and
          "wasInPosition   := globalPositionBlocked" in dc)
    # ---- prohibited ----
    bad = [t for t in ("alert(", "alertcondition", "map.new", "map<", "strategy.close(", "strategy.close_all", "strategy.cancel",
                       "box.new", "label.new", "line.new", "table.new", "tpManagementMode", "Dynamic", "useBreakEven",
                       "breakEven", "SignalEngine") if t in dc]
    check("D18/D20 prohibited: map / alerts / drawing / Dynamic TP / BE / Signal / strategy.close", not bad, str(bad))
    check("D19 no opentrades / closedtrades loop or per-trade accessor (scalars only)",
          not re.search(r"for .*(opentrades|closedtrades)", dc) and
          not re.search(r"strategy\.(opentrades|closedtrades)\.\w+", dc))
    check("P08 no request.* added beyond the P07 Zone block",
          dc.count("request.") == code_only(TH).count("request."))


# ---- Python mirror of the P08 dispatch ---------------------------------------
class Broker:
    def __init__(self, position_size=0.0, opentrades=0, closedtrades=0):
        self.position_size, self.opentrades, self.closedtrades = position_size, opentrades, closedtrades
        self.orders = []


def tp_depth_for(logicId, d, c, compat=True, breakDepth=0.0):
    return breakDepth if compat and logicId == "ZONEBREAK" and d > 0 else c.structuralTpDepthRatio


def try_entry(ap, ds, br, live, c, logicId, cand, d, entry, posBlocked, entered_bar, isGold=True, tpMode="BOTH",
              qtyMin=0.01, compat=True, breakDepth=0.0, **qkw):
    if not (cand and d != 0 and isGold and not posBlocked and not entered_bar):
        return False
    if ds["insPrice"] is not None and entry == ds["insPrice"]:
        ins = ds["insBlocked"]
    else:
        ins, _, _ = inside_any(live, c, entry)
        ds["insideScans"] += 1
        ds["insPrice"], ds["insBlocked"] = entry, ins
    if ins:
        return False
    p = build_plan(live, c, d, entry, tp_depth_for(logicId, d, c, compat, breakDepth))
    ds["plans"] += 1
    if tpMode == "STRUCTURAL_ONLY" and p["tpType"] == "FALLBACK_RR":
        p.update(valid=False, status="FAIL", reason="NO_STRUCTURAL_TP")
    elif tpMode == "FALLBACK_ONLY" and p["tpType"] == "STRUCTURAL":
        p.update(valid=False, status="FAIL", reason="STRUCTURAL_TP_EXISTS")
    if not p["valid"]:
        return False
    q = f_qty_(p["risk"], **qkw)
    ds["qtys"] += 1
    if not (q >= qtyMin and q > 0):
        return False
    eid = P08_TAG[logicId] + ("_L" if d > 0 else "_S")
    br.orders.append(("entry", eid, d, q))
    br.orders.append(("exit", eid + "X", eid, p["sl"], p["tp"]))
    ap.update(entryId=eid, logicId=logicId, dir=d, entryPrice=p["entry"], sl=p["sl"], tp=p["tp"], qty=q,
              originTrackId=None, entryTouchCount=None)
    ds["winPriority"] = P08_ORDER.index(logicId) + 1
    return True


def dispatch(cands, live, c, br, ap, **kw):
    """cands: {logicId: (dirMode 'Long'/'Short'/'Both', price)}  (absent = candidate OFF).
    kw: isGold / tpMode / qtyMin / qtyStep ... or per-logic override via kw['per'] = {logicId: {...}}."""
    per = kw.pop("per", {})
    posBlocked = br.position_size != 0 or br.opentrades > 0
    ds = dict(winPriority=None, insideScans=0, plans=0, qtys=0, insPrice=None, insBlocked=False)
    entered = False
    for lg in P08_ORDER:
        on = lg in cands
        mode, px = cands.get(lg, ("Both", None))
        args = dict(kw, **per.get(lg, {}))
        e = try_entry(ap, ds, br, live, c, lg, on and mode != "Short", 1, px, posBlocked, entered, **args)
        entered = entered or e
        e = try_entry(ap, ds, br, live, c, lg, on and mode != "Long", -1, px, posBlocked, entered, **args)
        entered = entered or e
    return entered, ds


def fixture_p08_behaviour():
    c = TCfg()
    sup = Z(4030, 4040, ST_SUP_, tid=1)
    res_far = Z(4100, 4110, ST_RES_, tid=4)
    res = Z(4070, 4080, ST_RES_, tid=3)
    sup_lo = Z(3980, 3990, ST_SUP_, tid=5)
    live = [sup, res_far]                  # Long @4050 : SL 4025 (risk 25), TP 4100 + depth -> PASS, qty 2
    allL = {lg: ("Long", 4050.0) for lg in P08_ORDER}
    new = lambda: dict(entryId="", logicId="", dir=0, entryPrice=None, sl=None, tp=None, qty=None,
                       originTrackId=None, entryTouchCount=None)
    entries = lambda br: [o for o in br.orders if o[0] == "entry"]

    br, ap = Broker(), new()
    ent, ds = dispatch({"FVG15": ("Long", 4050.0)}, live, c, br, ap)
    check("D01 Flat + FVG15 PASS -> only FVG15 enters", ent and [o[1] for o in entries(br)] == ["FVG15_L"])

    # D02 : FVG15 price has no SL zone (TradePlan FAIL) -> FVG evaluated and enters
    br, ap = Broker(), new()
    ent, ds = dispatch({"FVG15": ("Long", 4035.5 - 100), "FVG": ("Long", 4050.0)}, live, c, br, ap)
    check("D02 FVG15 signal true but TradePlan FAIL -> FVG evaluated and enters",
          ent and [o[1] for o in entries(br)] == ["FVG_L"] and ds["plans"] == 2)

    # D03 : FVG15 qty below qtyMin (tiny capital for FVG15 only) -> FVG
    br, ap = Broker(), new()
    ent, ds = dispatch({"FVG15": ("Long", 4050.0), "FVG": ("Long", 4050.0)}, live, c, br, ap,
                       per={"FVG15": dict(capital=1.0)})
    check("D03 FVG15 qty < qtyMin -> SKIP, FVG enters", ent and [o[1] for o in entries(br)] == ["FVG_L"] and ds["qtys"] == 2)

    # D04 / D05 : all 8 candidates true, FVG15 passes -> the 7 others skip (no scan / plan / qty after success)
    br, ap = Broker(), new()
    ent, ds = dispatch(allL, live, c, br, ap)
    check("D04 FVG15 entered -> FVG..ZONEBREAK all skipped", [o[1] for o in entries(br)] == ["FVG15_L"])
    check("D05 all 8 signals -> only the top-priority PASS logic enters (1 order)", len(entries(br)) == 1 and ds["winPriority"] == 1)
    check("C24 after the successful entry: 0 further Inside scans / buildPlan / Qty", (ds["insideScans"], ds["plans"], ds["qtys"]) == (1, 1, 1),
          str((ds["insideScans"], ds["plans"], ds["qtys"])))

    # D06 : priorities 1-3 FAIL (no SL zone at their price), 4 passes -> ABS5
    br, ap = Broker(), new()
    cands = {"FVG15": ("Long", 3000.0), "FVG": ("Long", 3001.0), "FVGABS15": ("Long", 3002.0), "FVGABS5": ("Long", 4050.0),
             "ZONEREBOUND": ("Long", 4050.0)}
    ent, ds = dispatch(cands, live, c, br, ap)
    check("D06 priorities 1-3 FAIL, 4 PASS -> ABS5 enters", [o[1] for o in entries(br)] == ["ABS5_L"] and ds["winPriority"] == 4)

    # D07 : position held -> 0 entries, no scan / plan / qty
    for pos, ot in ((1.0, 1), (-2.0, 1), (0.0, 1)):
        br, ap = Broker(position_size=pos, opentrades=ot), new()
        ent, ds = dispatch(allL, live, c, br, ap)
        check(f"D07 position held (size {pos}, opentrades {ot}) -> 0 entries, 0 scans / plans / qty",
              not ent and not br.orders and (ds["insideScans"], ds["plans"], ds["qtys"]) == (0, 0, 0))

    # D08 : not Gold -> 0 entries and no Zone scan / TradePlan
    br, ap = Broker(), new()
    ent, ds = dispatch(allL, live, c, br, ap, isGold=False)
    check("D08 non-Gold -> 0 entries, 0 scans / plans / qty", not ent and not br.orders and (ds["insideScans"], ds["plans"], ds["qtys"]) == (0, 0, 0))

    # D09 : FVG15 entry price inside a Strong zone -> FAIL, FVG (other price) enters
    br, ap = Broker(), new()
    ent, ds = dispatch({"FVG15": ("Long", 4035.0), "FVG": ("Long", 4050.0)}, live, c, br, ap)
    check("D09 Inside Any Zone -> that candidate FAIL, next logic evaluated and enters",
          [o[1] for o in entries(br)] == ["FVG_L"] and ds["insideScans"] == 2 and ds["plans"] == 1)

    # D10 : same bar -> no 2nd order even though position_size is still 0 (fill not reflected yet)
    br, ap = Broker(), new()
    ent, ds = dispatch({lg: ("Both", 4050.0) for lg in P08_ORDER}, live, c, br, ap)
    check("D10 same bar: enteredThisBar blocks a 2nd order while position_size is still 0",
          br.position_size == 0 and len(entries(br)) == 1)

    # D11 : next bar while held -> blocked; after close -> entry possible again
    br.position_size, br.opentrades = 2.0, 1
    e2, _ = dispatch(allL, live, c, br, ap)
    n_held = len(entries(br))
    br.position_size, br.opentrades, br.closedtrades = 0.0, 0, 1
    e3, _ = dispatch(allL, live, c, br, ap)
    check("D11 held bar -> no entry; bar after the position closed -> entry possible again",
          not e2 and n_held == 1 and e3 and len(entries(br)) == 2)

    # D12 / D13 : Long / Short on the same logic
    # SL-only zones (strength 2 < tpMinStrength 3): Long SL 4030 / fallback TP, Short SL 4070 / fallback TP -> both PASS alone
    live_ws = [Z(4035, 4040, ST_SUP_, strength=2, tid=12), Z(4060, 4065, ST_RES_, strength=2, tid=13)]
    br_s, ap_s = Broker(), new()
    dispatch({"FVG15": ("Short", 4050.0)}, live_ws, c, br_s, ap_s)
    br, ap = Broker(), new()
    dispatch({"FVG15": ("Both", 4050.0)}, live_ws, c, br, ap)
    check("D12 Long and Short both PASS alone; Both -> Long enters, Short not ordered",
          [o[1] for o in entries(br_s)] == ["FVG15_S"] and [o[1] for o in entries(br)] == ["FVG15_L"])
    live3 = [Z(4060, 4065, ST_RES_, tid=6), Z(4000, 4005, ST_SUP_, tid=7)]   # Long: SL 3995 risk 55 -> FAIL; Short: SL 4070 risk 20 -> PASS
    br, ap = Broker(), new()
    ent, ds = dispatch({"FVG15": ("Both", 4050.0)}, live3, c, br, ap)
    check("D13 Long FAIL -> Short evaluated and enters (Inside scan shared: same price)",
          [o[1] for o in entries(br)] == ["FVG15_S"] and ds["insideScans"] == 1 and ds["plans"] == 2)

    # D14 : SL / TP passed to strategy.exit unchanged
    br, ap = Broker(), new()
    dispatch({"FVG": ("Long", 4050.0)}, live, c, br, ap)
    ex = [o for o in br.orders if o[0] == "exit"][0]
    pl = build_plan(live, c, 1, 4050.0, c.structuralTpDepthRatio)
    check("D14 strategy.exit gets the entry-time plan SL / TP (from_entry = entry ID)",
          ex == ("exit", "FVG_LX", "FVG_L", pl["sl"], pl["tp"]) and pl["sl"] == 4025 and pl["tp"] == 4102.5, str(ex))

    # D15 : TP depth per logic (ZONEBREAK Long compat depth 0.0, others common 0.25)
    tps = {}
    for lg in P08_ORDER:
        br, ap = Broker(), new()
        dispatch({lg: ("Long", 4050.0)}, live, c, br, ap)
        tps[lg] = ap["tp"]
    br, ap = Broker(), new()
    dispatch({"ZONEBREAK": ("Long", 4050.0)}, live, c, br, ap, compat=False)
    check("D15 TP depth per logic: ZONEBREAK Long (compat) 4100.0, all others 4102.5; compat OFF -> 4102.5",
          all(tps[lg] == 4102.5 for lg in P08_ORDER if lg != "ZONEBREAK") and tps["ZONEBREAK"] == 4100.0 and ap["tp"] == 4102.5,
          str(tps))

    # D16 / D17 : scalar active state
    br, ap = Broker(), new()
    dispatch({"ZONERETEST": ("Long", 4050.0)}, live, c, br, ap)
    check("D16 entry stores entryId / logicId / dir / entryPrice / SL / TP / Qty (touch slots na)",
          ap == dict(entryId="ZRT_L", logicId="ZONERETEST", dir=1, entryPrice=4050.0, sl=4025, tp=4102.5, qty=2.0,
                     originTrackId=None, entryTouchCount=None), str(ap))
    before = dict(ap)
    br2 = Broker()
    dispatch({"FVG": ("Long", 3000.0), "FVG15": ("Long", 4035.0)}, live, c, br2, ap)         # plan FAIL / inside
    dispatch(allL, live, c, br2, ap, isGold=False)                                           # gold gate
    dispatch(allL, live, c, Broker(position_size=1.0, opentrades=1), ap)                     # position gate
    dispatch(allL, live, c, br2, ap, capital=1.0)                                            # qty
    check("D17 failed candidates never rewrite the active state", ap == before and not br2.orders)

    # ---- cost audit ----------------------------------------------------------
    # worst case: 8 logics, Long + Short, every candidate fails at the last gate (qtyMin), distinct prices per logic
    br, ap = Broker(), new()
    distinct = {lg: ("Both", 4050.0 + i * 0.5) for i, lg in enumerate(P08_ORDER)}
    ent, ds = dispatch(distinct, live_ws, c, br, ap, capital=0.001)
    worst = (ds["insideScans"], ds["plans"], ds["qtys"])
    check("C24 worst case (16 candidates, all fail at qtyMin, 8 prices): Inside 8 / buildPlan 16 / Qty 16",
          not ent and worst == (8, 16, 16), str(worst))
    br, ap = Broker(), new()
    ent, ds = dispatch({lg: ("Both", 4050.0) for lg in P08_ORDER}, live, c, br, ap, capital=0.001)
    check("C24 one shared entry price: Inside scan 1 for all 16 candidates", ds["insideScans"] == 1 and ds["plans"] == 16)
    br, ap = Broker(), new()
    ent, ds = dispatch(distinct, live, c, br, ap)
    check("C24 after a success at priority 1 Long: Inside 1 / buildPlan 1 / Qty 1, subsequent 0",
          ent and (ds["insideScans"], ds["plans"], ds["qtys"]) == (1, 1, 1))


# ============================================================================
# P09 : Break Even (Scalar 1-Position)
# ============================================================================
BH_PATH = os.path.join(ROOT, "PracticalBreakEvenHarness.pine")
BH = open(BH_PATH, encoding="utf-8").read() if os.path.exists(BH_PATH) else ""


def fixture_p09_static():
    check("P09 harness file exists", bool(BH))
    if not BH:
        return
    bc = code_only(BH)
    BI, MI = parse_inputs(BH), parse_inputs(MAIN)
    names = ["useBreakEven", "breakEvenTrigger", "fvg15BreakEvenTrigger", "absBreakEvenTrigger", "zoneBreakEvenTrigger",
             "breakEvenTriggerMode", "breakLongBreakEvenTrigger", "breakLongRefCompat"]
    diff = [n for n in names if BI.get(n) != MI.get(n) or BI.get(n) is None]
    check("PB1 BE inputs == old Main (name / kind / default / title / group / options / step)", not diff,
          ", ".join(f"{n}={BI[n]['default']}" for n in names if n in BI) if not diff else f"diff={diff}")
    check("PB2 f_breakEvenTriggerFor code identical to old Main (incl. ZONEBREAK Long compat branch)",
          code_only(func_block(BH, "f_breakEvenTriggerFor")) == code_only(func_block(MAIN, "f_breakEvenTriggerFor")) != "")
    m_be = MAIN[MAIN.find("// ---- 8.2 建値移動"):MAIN.find("// ---- 8.3 Dynamic TP")]
    b_be = BH[BH.find("// 09. BREAK EVEN"):BH.find("// ---- Flat 遷移検知用")]
    mr = re.findall(r"reach := (.*)", code_only(m_be))
    br_ = re.findall(r"reach := (.*)", code_only(b_be))
    norm = [x.replace("activePos.beTrigger", "beTrigger") for x in br_]
    check("PB3 Long / Short reach (到達瞬間 high/low, 確定足 isconfirmed + close) identical to old Main",
          len(mr) == 2 and norm == mr, str(norm))
    check("PB3 Long branch = activePos.dir > 0 (old Main: opentrades.size > 0), Short = else",
          "if activePos.dir > 0" in b_be and "if isLong" in m_be)
    ex_m = re.findall(r"strategy\.exit\((.*?)\)\n", " ".join(code_only(m_be).split("\n     ")).replace("\n", "\n") + "\n")
    ex_b = re.findall(r'strategy\.exit\(activePos\.entryId \+ "X", from_entry = activePos\.entryId, stop = ep, '
                      r'limit = activePos\.tp,\s+comment_loss = "BE", comment_profit = "TP"\)', code_only(b_be))
    check("PB4 BE exit: same Exit ID (entryId+X), stop = entry fill price, limit = entry-time TP, BE / TP comments",
          len(ex_b) == 1 and 'stop = ep, limit = gTradeTP.get(eid)' in m_be and 'comment_loss = "BE", comment_profit = "TP"' in m_be)
    check("PB4 BE entry price = fill price (old Main opentrades.entry_price -> scalar position_avg_price)",
          "float ep     = strategy.opentrades.entry_price(i)" in m_be and
          "float beEntryFill        = strategy.position_size != 0 ? strategy.position_avg_price : na" in bc and
          "float ep = beEntryFill" in b_be)
    sets = re.findall(r"(\w+)\.beOn\s*:=\s*(\w+)", bc)
    te = code_only(func_block(BH, "f_tryEntry"))
    fr = code_only(BH[BH.find("if flatTransition"):BH.find("// 07. PROBE")])
    check("PB5 BE irreversible: beOn := true only in the BE section; := false only at new entry / flat transition",
          sorted(sets) == [("activePos", "false"), ("activePos", "true"), ("ap", "false")] and
          "ap.beOn            := false" in te and "activePos.beOn           := false" in fr and
          "activePos.beOn           := true" in b_be and "if not activePos.beOn" in b_be)
    check("PB5 entry stores beOn = false / beTrigger = f_breakEvenTriggerFor(logicId, dir) (scalar, no Entry ID parse)",
          "ap.beTrigger       := f_breakEvenTriggerFor(logicId, dir)" in te and "str.startswith" not in bc
          and "f_logicIdFromEid" not in bc)
    check("PB6 flat reset clears beOn / beTrigger / beActivatedBar and sits BEFORE the dispatch",
          all(x in fr for x in ("activePos.beTrigger      := na", "activePos.beActivatedBar := na"))
          and bc.find("if flatTransition") < bc.find("if barstate.isconfirmed\n    bool fire"))
    check("PB7 BE section AFTER the dispatch (old Main: Section 06 calls -> Section 08 BE)",
          bc.find("e := f_tryEntry(activePos, ds, LOGIC_ZONE_BK") < bc.find("if useBreakEven and strategy.position_size != 0")
          and MAIN.find("string zbkEidShort = f_submitSignal") < MAIN.find("// ---- 8.2 建値移動"))
    check("PB7 BE requires an open position (old Main: opentrades > 0) -> never on the entry-signal bar",
          "if useBreakEven and strategy.position_size != 0 and activePos.entryId != \"\"" in b_be and
          "if useBreakEven and strategy.opentrades > 0" in m_be)
    decl = BH[BH.find("strategy("):BH.find(")", BH.find("calc_on_every_tick")) + 1]
    check("PB8 calc_on_every_tick = true added; dispatch still confirmed-bar only",
          "calc_on_every_tick = true" in decl and "if barstate.isconfirmed\n    bool fire" in bc)
    # ---- P08 dispatch unchanged: P09 = P08 + insertions (only the header title / calc_on_every_tick line replaced) ----
    a = [l for l in code_only(DH).split("\n")]
    b = [l for l in bc.split("\n")]
    ops = [op for op in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes() if op[0] != "equal"]
    repl = [(a[i1:i2], b[j1:j2]) for t, i1, i2, j1, j2 in ops if t != "insert"]
    allowed = [(['     title             = "Practical Entry Dispatch Harness (P08)",', '     shorttitle        = "DISPATCH-P08",'],
                ['     title             = "Practical Break Even Harness (P09)",', '     shorttitle        = "BE-P09",']),
               (['     dynamic_requests  = true)'], ['     dynamic_requests  = true,', '     calc_on_every_tick = true)'])]
    check("PB9 P08 code preserved line-for-line (P09 only inserts; replaced = title / calc_on_every_tick)",
          repl == allowed, str(repl)[:300])
    ins = [l for t, i1, i2, j1, j2 in ops if t == "insert" for l in b[j1:j2]]
    te8 = code_only(func_block(DH, "f_tryEntry")).split("\n")
    te9 = [l for l in te.split("\n") if not re.search(r"ap\.be\w+\s*:=", l)]
    check("PB9 f_tryEntry == P08 except the 3 BE-state writes in the entered branch", te8 == te9)
    bad_ins = [l for l in ins if re.search(r"strategy\.entry|f_tryEntry\(|enteredThisBar|globalPositionBlocked\s*=|"
                                           r"zn\.|f_insideAnyZone|request\.|for ", l)]
    check("PB9 inserted lines touch no dispatch / gate / Zone / request / loop", not bad_ins, str(bad_ins))
    bad = [t for t in ("map.new", "map<", "array.new", "gTradeTP", "gTradeSL", "gTradeBE", "f_isOpenEntry", "alert(",
                       "alertcondition", "tpManagementMode", "Dynamic", "label.new", "box.new", "table.new", "line.new",
                       "strategy.close(", "strategy.cancel") if t in bc]
    check("BE24/BE27 no map / array trade mgmt / gTrade* / f_isOpenEntry / Dynamic TP / alert / drawing", not bad, str(bad))
    check("BE25/BE26 no opentrades / closedtrades loop or per-trade accessor (scalars only)",
          not re.search(r"for .*(opentrades|closedtrades)", bc) and not re.search(r"strategy\.(opentrades|closedtrades)\.\w+", bc))
    check("PB10 cost: BE adds 0 Zone scans / 0 buildPlan / 0 request (counts == P08)",
          bc.count("f_insideAnyZone(") == code_only(DH).count("f_insideAnyZone(") and
          bc.count("zn.buildPlanWithTpDepth(") == code_only(DH).count("zn.buildPlanWithTpDepth(") == 1 and
          bc.count("request.") == code_only(DH).count("request."))


# ---- bar-by-bar broker mirror (historical: script runs once at bar close) ----------
BE_TRIG = dict(breakEvenTrigger=15.0, fvg15BreakEvenTrigger=10.0, absBreakEvenTrigger=10.0, zoneBreakEvenTrigger=20.0,
               breakLongBreakEvenTrigger=10.0, breakLongRefCompat=True)


def be_trigger_for(logicId, d, t=BE_TRIG):
    r = t["breakEvenTrigger"]
    if logicId == "FVG15":
        r = t["fvg15BreakEvenTrigger"]
    elif logicId in ("FVGABS5", "FVGABS15"):
        r = t["absBreakEvenTrigger"]
    elif logicId == "ZONEBREAK" and d > 0 and t["breakLongRefCompat"]:
        r = t["breakLongBreakEvenTrigger"]
    elif logicId in ("ZONEREBOUND", "ZONEFAKE", "ZONERETEST", "ZONEBREAK"):
        r = t["zoneBreakEvenTrigger"]
    return r


def be_reach(d, mode, ep, trig, high, low, close, confirmed=True):
    if d > 0:
        return (confirmed and close >= ep + trig) if mode == "確定足" else (high >= ep + trig)
    return (confirmed and close <= ep - trig) if mode == "確定足" else (low <= ep - trig)


def broker_fill_exit(d, o, h, l, c, stop, limit):
    """TV broker emulator bar path: O -> nearer extreme -> other extreme -> C. Returns (price, kind) or None."""
    path = [o, h, l, c] if abs(h - o) <= abs(o - l) else [o, l, h, c]
    prev = o
    for px in path:
        lo_, hi_ = min(prev, px), max(prev, px)
        hits = []
        if d > 0:
            if stop is not None and lo_ <= stop:
                hits.append((stop if prev > stop else prev, "stop", abs(prev - stop)))
            if limit is not None and hi_ >= limit:
                hits.append((limit if prev < limit else prev, "limit", abs(prev - limit)))
        else:
            if stop is not None and hi_ >= stop:
                hits.append((stop if prev < stop else prev, "stop", abs(prev - stop)))
            if limit is not None and lo_ <= limit:
                hits.append((limit if prev > limit else prev, "limit", abs(prev - limit)))
        if hits:
            hits.sort(key=lambda x: x[2])
            return hits[0][0], hits[0][1]
        prev = px
    return None


def run_be_sim(bars, signals, model="p09", useBE=True, mode="到達瞬間", trig=BE_TRIG):
    """bars: [(o,h,l,c)]. signals: {bar: (logicId, dir, risk, rr)} evaluated at that bar's close.
    model: 'p08' (no BE section), 'p09' (scalar, once), 'main' (Map + opentrades loop + re-issue every bar).
    Returns (trades, log) ; trades = [(entryBar, fill, exitBar, exitPx, comment)]."""
    pending = None                       # entry order placed at a confirmed close, fills next open
    pos = None                           # open trade dict
    exit_order = None                    # (eid, stop, limit, comment_loss, comment_profit)
    closed, trades, log, closed_eids = 0, [], [], []
    ap = dict(entryId="", logicId="", dir=0, sl=None, tp=None, beOn=False, beTrigger=None, beActivatedBar=None)
    gTP, gBE, seq = {}, {}, 0
    was_in, last_closed = False, 0
    for i, (o, h, l, c) in enumerate(bars):
        # ---- broker: pending entry fills at open, then the active exit order works on the bar path ----
        if pending is not None:
            pos = dict(eid=pending["eid"], dir=pending["dir"], fill=o, entryBar=i, logicId=pending["logicId"])
            pending = None
        if pos is not None and exit_order is not None and exit_order[0] == pos["eid"]:
            r = broker_fill_exit(pos["dir"], o, h, l, c, exit_order[1], exit_order[2])
            if r is not None:
                px, kind = r
                trades.append((pos["entryBar"], pos["fill"], i, px, exit_order[3] if kind == "stop" else exit_order[4]))
                closed_eids.append(pos["eid"])
                pos, exit_order = None, None
                closed += 1
        # ---- script at bar close ----
        blocked = pos is not None
        if model != "main":
            flat = (not blocked) and (was_in or closed > last_closed)
            if flat and model == "p09":
                ap.update(beOn=False, beTrigger=None, beActivatedBar=None)
        act = False
        if i in signals and not blocked and pending is None:
            lg, d, risk, rr = signals[i]
            seq += 1
            eid = (P08_TAG[lg] + ("_L" if d > 0 else "_S")) if model != "main" else f"{lg}{'_L_' if d > 0 else '_S_'}{seq}"
            sl, tp = c - d * risk, c + d * risk * rr
            pending = dict(eid=eid, dir=d, logicId=lg)
            exit_order = (eid, sl, tp, "SL", "TP")
            ap.update(entryId=eid, logicId=lg, dir=d, sl=sl, tp=tp, beOn=False, beTrigger=be_trigger_for(lg, d, trig),
                      beActivatedBar=None)
            gTP[eid] = tp
            if useBE:
                gBE[eid] = False
        if model == "p09" and useBE and pos is not None and ap["entryId"] != "":
            ep = pos["fill"]
            if not ap["beOn"] and be_reach(ap["dir"], mode, ep, ap["beTrigger"], h, l, c):
                ap.update(beOn=True, beActivatedBar=i)
                exit_order = (ap["entryId"], ep, ap["tp"], "BE", "TP")
                act = True
        elif model == "main":
            if closed > last_closed:            # 8.1 cleanup: only the entry IDs closed since lastClosedCount, if not open
                for k in closed_eids[last_closed:closed]:
                    if pos is None or k != pos["eid"]:
                        gTP.pop(k, None)
                        gBE.pop(k, None)
            if useBE and pos is not None and pos["eid"] in gTP:
                eid = pos["eid"]
                ep = pos["fill"]
                lg = next((x for x in P08_ORDER if eid.startswith(x + "_L_") or eid.startswith(x + "_S_")), "")
                d = 1 if eid.startswith(lg + "_L_") else -1
                was_on = gBE.get(eid, False)
                if was_on or be_reach(pos["dir"], mode, ep, be_trigger_for(lg, d, trig), h, l, c):
                    gBE[eid] = True
                    exit_order = (eid, ep, gTP[eid], "BE", "TP")
                    act = not was_on
        log.append(dict(bar=i, beAct=act, exit=exit_order, ap=dict(ap), pos=dict(pos) if pos else None))
        was_in, last_closed = blocked, closed
    return trades, log


def fixture_p09_behaviour():
    import random
    # ---- deterministic scenario helpers: entry signal at bar 0 close 4000, fill at bar 1 open ----
    def scen(lg, d, path, mode="到達瞬間", useBE=True, risk=30.0, rr=3.0, model="p09", trig=BE_TRIG):
        bars = [(4000.0, 4001.0, 3999.0, 4000.0)] + path
        return run_be_sim(bars, {0: (lg, d, risk, rr)}, model=model, useBE=useBE, mode=mode, trig=trig)

    flat_bar = lambda px: (px, px + 0.5, px - 0.5, px)
    # BE02 FVG Long: fill 4001, trigger 15 -> high 4016 reaches
    tr, lg_ = scen("FVG", 1, [(4001.0, 4016.0, 4000.5, 4010.0), flat_bar(4010.0)])
    check("BE02 FVG Long: entry + breakEvenTrigger(15) reached -> exit stop = entry fill (4001), TP kept",
          lg_[1]["beAct"] and lg_[1]["exit"] == ("FVG_L", 4001.0, 4000.0 + 90.0, "BE", "TP"), str(lg_[1]["exit"]))
    tr, lg_ = scen("FVG", -1, [(3999.0, 3999.5, 3984.0, 3990.0), flat_bar(3990.0)])
    check("BE03 FVG Short: entry - trigger reached -> stop = entry fill (3999)",
          lg_[1]["beAct"] and lg_[1]["exit"] == ("FVG_S", 3999.0, 4000.0 - 90.0, "BE", "TP"), str(lg_[1]["exit"]))
    _, a = scen("FVG", 1, [(4001.0, 4015.5, 4000.5, 4010.0)])
    _, b = scen("FVG", 1, [(4001.0, 4015.5, 4000.5, 4010.0)], model="main")
    check("BE-EP BE measured from the fill price (4001 -> 4016), not the plan close (4000 -> 4015): high 4015.5 -> none (== old Main)",
          not a[1]["beAct"] and not b[1]["beAct"])
    # BE04-BE10 per-logic trigger (Long): reach exactly fill + trigger, 0.01 short -> none
    exp = {"FVG15": 10.0, "FVGABS5": 10.0, "FVGABS15": 10.0, "ZONEREBOUND": 20.0, "ZONEFAKE": 20.0,
           "ZONERETEST": 20.0, "ZONEBREAK": 20.0, "FVG": 15.0}
    labels = {"FVG15": "BE04", "FVGABS5": "BE05", "FVGABS15": "BE06", "ZONEREBOUND": "BE07", "ZONEFAKE": "BE08",
              "ZONERETEST": "BE09", "ZONEBREAK": "BE10"}
    for lg, tg in exp.items():
        if lg not in labels:
            continue
        for d in (1, -1):
            want = tg if not (lg == "ZONEBREAK" and d > 0) else 10.0   # old Main: ZONEBREAK Long compat -> breakLong trigger
            fill = 4000.0 + d
            hit = (fill, fill + want, fill - 0.5, fill) if d > 0 else (fill, fill + 0.5, fill - want, fill)
            miss = (fill, fill + want - 0.01, fill - 0.5, fill) if d > 0 else (fill, fill + 0.5, fill - want + 0.01, fill)
            _, a = scen(lg, d, [hit])
            _, b = scen(lg, d, [miss])
            check(f"{labels[lg]} {lg} {'Long' if d > 0 else 'Short'} -> trigger {want} (hit exact / 0.01 short none)",
                  a[1]["ap"]["beTrigger"] == want and a[1]["beAct"] and not b[1]["beAct"])
    tz = dict(BE_TRIG, breakLongRefCompat=False)
    _, a = scen("ZONEBREAK", 1, [(4001.0, 4021.0, 4000.5, 4001.0)], trig=tz)
    check("BE10b ZONEBREAK Long with compat OFF -> zoneBreakEvenTrigger 20 (old Main mapping)",
          a[1]["ap"]["beTrigger"] == 20.0 and a[1]["beAct"])
    check("BE04-10 mapping == spec list for every logic except ZONEBREAK Long compat (old Main authority)",
          all(be_trigger_for(lg, -1) == exp[lg] for lg in exp) and be_trigger_for("ZONEBREAK", 1) == 10.0)
    # BE11 / BE12 到達瞬間 exact threshold
    _, a = scen("FVG", 1, [(4001.0, 4016.0, 4000.0, 4002.0)])
    _, b = scen("FVG", -1, [(3999.0, 4000.0, 3984.0, 3998.0)])
    check("BE11 到達瞬間 Long high == threshold -> BE", a[1]["beAct"])
    check("BE12 到達瞬間 Short low == threshold -> BE", b[1]["beAct"])
    # BE13 / BE14 / BE15 確定足
    _, a = scen("FVG", 1, [(4001.0, 4030.0, 4000.5, 4015.99)], mode="確定足")
    _, b = scen("FVG", 1, [(4001.0, 4030.0, 4000.5, 4016.0)], mode="確定足")
    _, c_ = scen("FVG", -1, [(3999.0, 3999.5, 3970.0, 3984.01)], mode="確定足")
    _, d_ = scen("FVG", -1, [(3999.0, 3999.5, 3970.0, 3984.0)], mode="確定足")
    check("BE13 確定足 Long: high reached but close below -> no BE", not a[1]["beAct"])
    check("BE14 確定足 Long: confirmed close == threshold -> BE", b[1]["beAct"])
    check("BE15 確定足 Short symmetric (close 0.01 short none / == threshold BE)", not c_[1]["beAct"] and d_[1]["beAct"])
    check("BE15b 確定足 requires barstate.isconfirmed (unconfirmed tick never reaches)",
          not be_reach(1, "確定足", 4001.0, 15.0, 4030.0, 4000.0, 4030.0, confirmed=False)
          and be_reach(1, "到達瞬間", 4001.0, 15.0, 4016.0, 4000.0, 4000.0, confirmed=False))
    # BE16 reversal after BE -> exits at entry (BE), never original SL; BE21 comment
    tr, lg_ = scen("FVG", 1, [(4001.0, 4016.0, 4000.5, 4010.0), (4010.0, 4010.5, 3960.0, 3965.0)])
    check("BE16 price reverses after BE -> exit at entry fill 4001 (not original SL 3970); state stays beOn",
          tr == [(1, 4001.0, 2, 4001.0, "BE")] and lg_[1]["ap"]["beOn"])
    check("BE21 BE stop fill -> comment_loss 'BE'", tr and tr[0][4] == "BE")
    # BE17 TP after BE == entry-time TP
    tr, lg_ = scen("FVG", 1, [(4001.0, 4016.0, 4000.5, 4010.0), (4010.0, 4095.0, 4009.0, 4090.0)])
    check("BE17 TP after BE == entry-time TP 4090 (comment TP)", tr == [(1, 4001.0, 2, 4090.0, "TP")] and lg_[1]["exit"][2] == 4090.0)
    check("BE23 TP fill -> comment_profit 'TP'", tr[0][4] == "TP")
    # BE18 / BE22 no BE -> original structural SL with 'SL'
    tr, lg_ = scen("FVG", 1, [(4001.0, 4010.0, 4000.5, 4005.0), (4005.0, 4006.0, 3960.0, 3965.0)])
    check("BE18 BE not reached -> original structural SL 3970 stays", tr == [(1, 4001.0, 2, 3970.0, "SL")])
    check("BE22 normal SL -> comment_loss 'SL'", tr[0][4] == "SL")
    # BE19 / BE20 flat reset & next trade
    bars = [(4000.0, 4001.0, 3999.0, 4000.0), (4001.0, 4016.0, 4000.5, 4010.0), (4010.0, 4010.5, 3990.0, 3995.0),
            (3995.0, 3996.0, 3994.0, 3995.0), (3995.5, 4005.0, 3995.0, 4000.0), (4000.0, 4001.0, 3999.0, 4000.0)]
    tr, lg_ = run_be_sim(bars, {0: ("FVG", 1, 30.0, 3.0), 3: ("FVG15", 1, 30.0, 3.0)})
    check("BE19 trade closed in bar 2 (BE stop) -> flat transition at bar 2: beOn / beTrigger / beActivatedBar reset",
          tr[0] == (1, 4001.0, 2, 4001.0, "BE") and lg_[1]["ap"]["beOn"] and lg_[2]["ap"]["beOn"] is False
          and lg_[2]["ap"]["beTrigger"] is None and lg_[2]["ap"]["beActivatedBar"] is None)
    check("BE20 next trade does not inherit BE: FVG15 starts beOn=false, own trigger 10; fill 3995.5 -> bar 4 high 4005 < 4005.5 no BE",
          lg_[3]["ap"]["beOn"] is False and lg_[3]["ap"]["beTrigger"] == 10.0 and not lg_[4]["beAct"]
          and lg_[4]["exit"] == ("FVG15_L", 3965.0, 4085.0, "SL", "TP"))
    # ---- same-entry-bar semantics (old Main comparison) ----
    bars = [(4000.0, 4100.0, 3999.0, 4000.0), (4000.0, 4001.0, 3999.5, 4000.0), (4000.0, 4016.0, 3999.5, 4000.0)]
    for mdl in ("p09", "main"):
        _, lg_ = run_be_sim(bars, {0: ("FVG", 1, 30.0, 3.0)}, model=mdl)
        check(f"SEB [{mdl}] entry-signal bar high already beyond trigger -> no BE (position not filled yet); "
              f"fill bar below -> none; next bar reach -> BE", [x["beAct"] for x in lg_] == [False, False, True])
    bars = [(4000.0, 4001.0, 3999.0, 4000.0), (4000.0, 4016.0, 3999.5, 4005.0)]
    res = [run_be_sim(bars, {0: ("FVG", 1, 30.0, 3.0)}, model=m)[1][1]["beAct"] for m in ("p09", "main")]
    check("SEB fill bar (first bar in position) high reaches -> BE on that bar in both p09 and old Main", res == [True, True])
    # ---- randomized parity: p09 (scalar, once) vs old Main (map, loop, re-issue every bar); BE OFF vs P08 ----
    rnd = random.Random(20261005)
    n_tr = mism_main = mism_off = 0
    for trial in range(300):
        px, bars = 4000.0, []
        for _ in range(120):
            o = px + rnd.uniform(-2, 2)
            h = o + abs(rnd.gauss(0, 6))
            l = o - abs(rnd.gauss(0, 6))
            c = rnd.uniform(l, h)
            bars.append((round(o, 2), round(h, 2), round(l, 2), round(c, 2)))
            px = c
        sig = {i: (rnd.choice(P08_ORDER), rnd.choice((1, -1)), rnd.uniform(5, 30), rnd.uniform(1, 3))
               for i in range(len(bars)) if rnd.random() < 0.15}
        mode = rnd.choice(("到達瞬間", "確定足"))
        a, la = run_be_sim(bars, sig, "p09", True, mode)
        b, lb = run_be_sim(bars, sig, "main", True, mode)
        n_tr += len(a)
        mism_main += a != b
        mism_main += [x["beAct"] for x in la] != [x["beAct"] for x in lb]
        mism_main += [x["exit"][1:] if x["exit"] else None for x in la] != [x["exit"][1:] if x["exit"] else None for x in lb]
        c0, _ = run_be_sim(bars, sig, "p08", False, mode)
        c1, _ = run_be_sim(bars, sig, "p09", False, mode)
        mism_off += c0 != c1
    check("BE-PAR p09 scalar (once) == old Main Map/loop (re-issue every bar): trades / BE bars / active exit order "
          "on 300 random paths", mism_main == 0, f"{n_tr} trades, mismatches={mism_main}")
    check("BE01 useBreakEven=false -> identical to P08 (300 random paths)", mism_off == 0, f"{n_tr} trades")




# ============================================================================
# P10 : Provisional + Confirmed Entry Alerts
# ============================================================================
AH_PATH = os.path.join(ROOT, "PracticalAlertHarness.pine")
AH = open(AH_PATH, encoding="utf-8").read() if os.path.exists(AH_PATH) else ""


def fixture_p10_static():
    check("P10 harness file exists", bool(AH))
    if not AH:
        return
    ac = code_only(AH)
    AI, MI = parse_inputs(AH), parse_inputs(MAIN)
    ok = all(AI.get(n) == MI.get(n) and AI.get(n) for n in ("useProvisionalAlert", "useConfirmedAlert"))
    ln = lambda src, n: next((l for l in logical_lines(src) if l.startswith(n + " ")), "")
    check("PA1 alert inputs == old Main (name / type / default / title / group / tooltip): Provisional false, Confirmed true",
          ok and AI["useProvisionalAlert"]["default"] == "false" and AI["useConfirmedAlert"]["default"] == "true"
          and all(ln(AH, n) == ln(MAIN, n) != "" for n in ("useProvisionalAlert", "useConfirmedAlert"))
          and 'var string G_ALERT = "05 · Alerts"' in AH)
    check("PA1 f_provSlot (16 slots) identical to old Main", code_only(func_block(AH, "f_provSlot")) == code_only(func_block(MAIN, "f_provSlot")) != "")
    # ---- P10 = P09 + insertions ----
    a = code_only(BH).split("\n")
    b = ac.split("\n")
    ops = [op for op in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes() if op[0] != "equal"]
    repl = [(a[i1:i2], b[j1:j2]) for t, i1, i2, j1, j2 in ops if t != "insert"]
    check("PA2 P09 code preserved line-for-line (P10 only inserts; replaced = title / shorttitle)",
          repl == [(['     title             = "Practical Break Even Harness (P09)",', '     shorttitle        = "BE-P09",'],
                    ['     title             = "Practical Alert Harness (P10)",', '     shorttitle        = "ALERT-P10",'])], str(repl)[:300])
    ins = [l for t, i1, i2, j1, j2 in ops if t == "insert" for l in b[j1:j2]]
    bad_ins = [l for l in ins if re.search(r"strategy\.(entry|exit|close|cancel)|activePos\.\w+\s*:=|ap\.\w+\s*:=|"
                                           r"enteredThisBar\s*:=|globalPositionBlocked\s*=|ds\.\w+\s*:=|request\.",
                                           re.sub(r'"[^"]*"', '""', l))]
    check("AL01/AL14/AL15 inserted lines: no order / ActivePos / enteredThisBar / dispatch-stat / gate / request write",
          not bad_ins, str(bad_ins))
    te9 = code_only(func_block(BH, "f_tryEntry")).split("\n")
    te10 = code_only(func_block(AH, "f_tryEntry")).split("\n")
    extra = [l.strip() for l in te10 if l not in te9]
    check("PA2 f_tryEntry == P09 + confirmed alert + re-arm lines only",
          [l for l in te10 if l in te9] == te9 and extra == [
              "if useConfirmedAlert", 'alert(f_entryAlertMsg("確定", logicId, dir, p, qty), alert.freq_all)',
              "int pslot = f_provSlot(logicId, dir)", "if pslot >= 0", "array.set(gProvSent, pslot, false)"], str(extra))
    te = code_only(func_block(AH, "f_tryEntry"))
    order = [te.find(x) for x in ("strategy.entry(", "strategy.exit(", "ap.entryId", "ap.beActivatedBar",
                                  "if useConfirmedAlert", "array.set(gProvSent, pslot, false)", "entered := true")]
    tl = te.split("\n")
    ind = lambda l: len(l) - len(l.lstrip())
    ei = next(i for i, l in enumerate(tl) if "strategy.entry(" in l)
    ci = next(i for i, l in enumerate(tl) if "if useConfirmedAlert" in l)
    check("AL17 confirmed alert only inside the strategy.entry branch: entry -> exit -> ActivePos -> Confirmed -> re-arm",
          -1 not in order and order == sorted(order) and ind(tl[ei]) == ind(tl[ci]))
    check("AL17 exactly 2 alert() calls in the file (confirmed in f_tryEntry, provisional in Section 10); no alertcondition",
          ac.count("alert(") == 2 and "alertcondition" not in ac and te.count("alert(") == 1)
    sec = code_only(AH[AH.find("// 10. PROVISIONAL ALERT"):AH.find("// ---- Flat 遷移検知用")])
    pe = code_only(func_block(AH, "f_provEval"))
    check("AL14/AL15/AL16 provisional path: no strategy.* order, no ActivePos / ap / enteredThisBar / ds write, no consume",
          not re.search(r"strategy\.(entry|exit|close|cancel)|activePos|\bap\.|enteredThisBar|\bds\.|consume", sec))
    check("PA3 provisional gate: useProvisionalAlert first, not barstate.isconfirmed (old Main), isGold, Global Position Gate",
          "if useProvisionalAlert and not barstate.isconfirmed and isGold and not globalPositionBlocked" in sec
          and "not barstate.isconfirmed" in code_only(func_block(MAIN, "f_provWouldEnter")))
    m_te = code_only(func_block(AH, "f_tryEntry"))
    seq = lambda body: [body.find(x) for x in ("f_insideAnyZone(entryPrice)", "zn.buildPlanWithTpDepth(", 'if tpMode == "STRUCTURAL_ONLY"',
                                               "if p.valid", "float qty = f_qty(p.risk)", "if qty >= qtyMin and qty > 0")]
    tpm = lambda src: [" ".join(x.split()) for x in re.findall(
        r'if tpMode == "STRUCTURAL_ONLY" and p\.tpType == "FALLBACK_RR".*?p\.reason := "STRUCTURAL_TP_EXISTS"', src, re.S)]
    check("PA4 f_provEval uses the same gate order / TP Mode / Qty rule as f_tryEntry (Inside -> Plan -> TP Mode -> valid -> Qty -> qtyMin)",
          -1 not in seq(pe) and seq(pe) == sorted(seq(pe)) and tpm(pe) == tpm(m_te) != [])
    lg = re.findall(r"(LOGIC_\w+)", code_only(func_block(AH, "f_provLogic")))
    check("AL19 provisional priority order == entry dispatch order (FVG15 > FVG > ABS15 > ABS5 > RB > FK > RT > BK, Long then Short)",
          [P08_CONST[x] for x in lg] == P08_ORDER and "int    d   = k % 2 == 0 ? 1 : -1" in sec and "for k = 0 to 15" in sec)
    loop = sec[sec.find("for k = 0 to 15"):sec.find("if winDir != 0")]
    check("PA5 winner = first Entry-ready (break); provSent is checked AFTER the loop (no fall-through past a sent winner)",
          "if ev.ready" in loop and "break" in loop and "gProvSent" not in loop and
          "if slot >= 0 and not array.get(gProvSent, slot) and (na(gProvLastBar) or gProvLastBar != bar_index)" in sec)
    check("PA6 slot writes: true only in Section 10 (send), false only in the real-entry branch (re-arm)",
          ac.count("array.set(gProvSent") == 2 and "array.set(gProvSent, slot, true)" in sec and
          "array.set(gProvSent, pslot, false)" in te)
    check("PA7 varip dedupe: one varip bool[16] declared once + varip per-bar guard; no map; no other array.new",
          ac.count("varip array<bool> gProvSent = array.new_bool(16, false)") == 1 and ac.count("array.new") == 1 and
          "varip int gProvLastBar = na" in ac and "map." not in ac and "map<" not in ac)
    check("PA8 provisional = alert.freq_once_per_bar (D4: old Main provisional = freq_all); confirmed = alert.freq_all",
          ac.count("alert.freq_once_per_bar") == 1 and ac.count("alert.freq_all") == 1 and
          'alert(f_entryAlertMsg("仮", winLogic, winDir, win.plan, win.qty), alert.freq_once_per_bar)' in sec and
          'alert(f_entryAlertMsg("確定", logicId, dir, p, qty), alert.freq_all)' in te and
          "alert(f_provAlertMsg(logicId, dir), alert.freq_all)" in code_only(func_block(MAIN, "f_provFire")))
    msg = code_only(func_block(AH, "f_entryAlertMsg"))
    check("PA9 alert text: kind / LONG-SHORT / Logic / Symbol / E / SL / TP / RR / Qty; no rating / BE / debug lines (D2 / D3)",
          all(x in msg for x in ('"【" + kind', '"LONG"', '"SHORT"', "Logic: ", "syminfo.ticker", "E: ", "SL: ", "TP: ", "RR: ", "Qty: "))
          and not re.search(r"f_ratingBeLines|f_breakEvenDisplayText|bar_index|time", msg)
          and '"仮"' in sec and '"確定"' in te)
    check("AL22/AL23 no BE / TP / SL / Exit / Dynamic TP alert (BE section has no alert)",
          "alert(" not in code_only(AH[AH.find("// 09. BREAK EVEN"):AH.find("// 10. PROVISIONAL ALERT")]) and "Dynamic" not in ac)
    check("AL25/AL26 no map / trade loop / per-trade accessor",
          not re.search(r"for .*(opentrades|closedtrades)", ac) and not re.search(r"strategy\.(opentrades|closedtrades)\.\w+", ac))
    check("PA10 no request.* added (== P09)", ac.count("request.") == code_only(BH).count("request."))


# ---- Python mirror of the P10 alert layer ---------------------------------------
P10_SLOT = {"FVG": 0, "FVG15": 1, "FVGABS5": 2, "FVGABS15": 3, "ZONEREBOUND": 4, "ZONEFAKE": 5, "ZONERETEST": 6, "ZONEBREAK": 7}


def prov_slot(lg, d):
    return P10_SLOT[lg] * 2 + (0 if d > 0 else 1)


class AlertState:
    def __init__(self):
        self.sent = [False] * 16          # varip
        self.lastBar = None               # varip per-bar guard
        self.alerts = []                  # (bar, kind, logic, dir)  -> alert() calls
        self.delivered = []               # alerts that pass the frequency filter
        self.onceBars = set()             # worst case: freq_once_per_bar quota shared script-wide per bar

    def call(self, bar, kind, logic, d, freq):
        self.alerts.append((bar, kind, logic, d))
        if freq == "freq_all":
            self.delivered.append((bar, kind, logic, d))
        elif bar not in self.onceBars:
            self.onceBars.add(bar)
            self.delivered.append((bar, kind, logic, d))


P10_FREQ = {"仮": "freq_once_per_bar", "確定": "freq_all"}


def prov_eval(ps, live, c, lg, cand, d, entry, tpMode="BOTH", qtyMin=0.01, **qkw):
    if not (cand and d != 0):
        return None
    if ps["insPrice"] is not None and entry == ps["insPrice"]:
        ins = ps["insBlocked"]
    else:
        ins, _, _ = inside_any(live, c, entry)
        ps["insideScans"] += 1
        ps["insPrice"], ps["insBlocked"] = entry, ins
    if ins:
        return None
    p = build_plan(live, c, d, entry, tp_depth_for(lg, d, c))
    ps["plans"] += 1
    if tpMode == "STRUCTURAL_ONLY" and p["tpType"] == "FALLBACK_RR":
        p.update(valid=False)
    elif tpMode == "FALLBACK_ONLY" and p["tpType"] == "STRUCTURAL":
        p.update(valid=False)
    if not p["valid"]:
        return None
    q = f_qty_(p["risk"], **qkw)
    ps["qtys"] += 1
    return (p, q) if q >= qtyMin and q > 0 else None


def prov_tick(st, bar, cands, live, c, br, useProv=True, confirmed=False, isGold=True, **kw):
    """one realtime tick of Section 10. Returns (fired, winner, stats)."""
    ps = dict(insideScans=0, plans=0, qtys=0, insPrice=None, insBlocked=False)
    blocked = br.position_size != 0 or br.opentrades > 0
    if not (useProv and not confirmed and isGold and not blocked):
        return False, None, ps
    win = None
    for lg in P08_ORDER:
        for d in (1, -1):
            mode, px = cands.get(lg, ("Both", None))
            cnd = lg in cands and (mode != "Short" if d > 0 else mode != "Long")
            r = prov_eval(ps, live, c, lg, cnd, d, px, **kw)
            if r is not None:
                win = (lg, d)
                break
        if win:
            break
    if win is None:
        return False, None, ps
    sl = prov_slot(*win)
    if not st.sent[sl] and st.lastBar != bar:
        st.sent[sl] = True
        st.lastBar = bar
        st.call(bar, "仮", win[0], win[1], P10_FREQ["仮"])
        return True, win, ps
    return False, win, ps


def confirmed_bar(st, bar, cands, live, c, br, ap, useConf=True, **kw):
    """confirmed-bar dispatch (P08 mirror) + P10 confirmed alert + re-arm in the entry branch."""
    n0 = len([o for o in br.orders if o[0] == "entry"])
    ent, ds = dispatch(cands, live, c, br, ap, **kw)
    if ent:
        if useConf:
            st.call(bar, "確定", ap["logicId"], ap["dir"], P10_FREQ["確定"])
        st.sent[prov_slot(ap["logicId"], ap["dir"])] = False
    return ent, ds, len([o for o in br.orders if o[0] == "entry"]) - n0


def fixture_p10_behaviour():
    c = TCfg()
    sup = Z(4030, 4040, ST_SUP_, tid=1)
    res_far = Z(4100, 4110, ST_RES_, tid=4)
    live = [sup, res_far]
    new = lambda: dict(entryId="", logicId="", dir=0, entryPrice=None, sl=None, tp=None, qty=None,
                       originTrackId=None, entryTouchCount=None)
    conf = lambda st: [a for a in st.alerts if a[1] == "確定"]
    provs = lambda st: [a for a in st.alerts if a[1] == "仮"]

    # AL02 / AL03 confirmed on / off: same orders, 1 alert vs 0
    res = []
    for uc in (True, False):
        st, br, ap = AlertState(), Broker(), new()
        confirmed_bar(st, 1, {lg: ("Both", 4050.0) for lg in P08_ORDER}, live, c, br, ap, useConf=uc)
        res.append((list(br.orders), len(conf(st))))
    check("AL02 Confirmed OFF -> identical orders, 0 alerts", res[0][0] == res[1][0] and res[1][1] == 0)
    check("AL03 real entry -> exactly 1 confirmed alert", res[0][1] == 1)
    check("AL18 same-bar multiple candidates (16) -> 1 entry / 1 confirmed", len([o for o in res[0][0] if o[0] == "entry"]) == 1 and res[0][1] == 1)
    # AL04-AL07 / AL21 no confirmed when no real entry
    cases = [("AL04 Signal true / TradePlan FAIL", dict(cands={"FVG": ("Long", 3000.0)}, br=Broker(), kw={})),
             ("AL05 Qty below qtyMin", dict(cands={"FVG": ("Long", 4050.0)}, br=Broker(), kw=dict(capital=1.0))),
             ("AL06 Inside Any Zone", dict(cands={"FVG": ("Long", 4035.0)}, br=Broker(), kw={})),
             ("AL07 Position Blocked", dict(cands={"FVG": ("Long", 4050.0)}, br=Broker(position_size=1.0, opentrades=1), kw={})),
             ("AL21 non-Gold", dict(cands={"FVG": ("Long", 4050.0)}, br=Broker(), kw=dict(isGold=False)))]
    for name, cs in cases:
        st, ap = AlertState(), new()
        confirmed_bar(st, 1, cs["cands"], live, c, cs["br"], ap, **cs["kw"])
        pv = AlertState()
        prov_tick(pv, 1, cs["cands"], live, c, cs["br"], **cs["kw"])
        check(f"{name} -> confirmed 0 / provisional 0", not st.alerts and not pv.alerts and not cs["br"].orders)
    # AL08 / AL09 / AL10 provisional once until real entry
    st, br = AlertState(), Broker()
    cand = {"FVG": ("Long", 4050.0)}
    f1, _, _ = prov_tick(st, 1, cand, live, c, br)
    f2, _, _ = prov_tick(st, 1, cand, live, c, br)                      # same bar later tick
    f3, _, _ = prov_tick(st, 1, {}, live, c, br)                        # preview disappears
    f4, _, _ = prov_tick(st, 1, cand, live, c, br)                      # re-appears
    f5, _, _ = prov_tick(st, 2, cand, live, c, br)                      # next bar, still true
    check("AL08 Preview PASS -> 1 provisional", f1 and len(provs(st)) == 1)
    check("AL09 Preview disappears and re-appears -> not re-sent", not f2 and not f3 and not f4)
    check("AL10 next bar Preview continues -> not re-sent", not f5 and len(provs(st)) == 1)
    # AL11 re-arm on same logic/dir entry; AL12 other logic entry no re-arm; AL13 Long entry keeps Short slot
    st.sent[prov_slot("FVG", -1)] = True
    st.sent[prov_slot("FVG15", 1)] = True
    ap = new()
    confirmed_bar(st, 3, {"FVGABS5": ("Long", 4050.0)}, live, c, Broker(), ap)
    check("AL12 another logic's entry (ABS5 L) -> FVG_L / FVG15_L / FVG_S slots untouched",
          st.sent[prov_slot("FVG", 1)] and st.sent[prov_slot("FVG15", 1)] and st.sent[prov_slot("FVG", -1)])
    confirmed_bar(st, 4, {"FVG": ("Long", 4050.0)}, live, c, Broker(), ap)
    check("AL11 same logic + same dir entry (FVG L) -> FVG_L re-armed", not st.sent[prov_slot("FVG", 1)])
    check("AL13 Long entry -> Short slot (FVG_S) untouched", st.sent[prov_slot("FVG", -1)] and st.sent[prov_slot("FVG15", 1)])
    f6, _, _ = prov_tick(st, 5, cand, live, c, Broker())
    check("AL11b after re-arm the next Preview PASS fires again", f6)
    # AL19 / AL20 priority winner
    st = AlertState()
    f, w, _ = prov_tick(st, 1, {lg: ("Long", 4050.0) for lg in P08_ORDER}, live, c, Broker())
    check("AL19 several Entry-ready previews -> only the top priority (FVG15 L) is notified", f and w == ("FVG15", 1) and len(st.alerts) == 1)
    st = AlertState()
    f, w, _ = prov_tick(st, 1, {"FVG15": ("Long", 3000.0), "FVG": ("Long", 4050.0)}, live, c, Broker())
    check("AL20 top candidate not Entry-ready (Plan FAIL) -> next priority (FVG L) notified", f and w == ("FVG", 1))
    st = AlertState()
    st.sent[prov_slot("FVG15", 1)] = True
    f, w, _ = prov_tick(st, 1, {"FVG15": ("Long", 4050.0), "FVG": ("Long", 4050.0)}, live, c, Broker())
    check("PA5b winner FVG15 already sent + FVG Entry-ready -> NO alert (no fall-through to FVG)", not f and w == ("FVG15", 1) and not st.alerts)
    st = AlertState()
    f1, w1, _ = prov_tick(st, 1, {"FVG": ("Long", 4050.0)}, live, c, Broker())
    f2, w2, _ = prov_tick(st, 1, {"FVG15": ("Long", 4050.0), "FVG": ("Long", 4050.0)}, live, c, Broker())
    f3, w3, _ = prov_tick(st, 2, {"FVG15": ("Long", 4050.0), "FVG": ("Long", 4050.0)}, live, c, Broker())
    check("PA6b per bar max 1 provisional script-wide: winner changes FVG -> FVG15 in the same bar -> no 2nd; next bar -> FVG15",
          f1 and not f2 and w2 == ("FVG15", 1) and f3 and [a[2] for a in st.alerts] == ["FVG", "FVG15"])
    # historical / confirmed tick -> no provisional ; OFF -> 0 evaluation
    st = AlertState()
    f, _, ps = prov_tick(st, 1, {"FVG": ("Long", 4050.0)}, live, c, Broker(), confirmed=True)
    check("PA3b confirmed tick (all historical bars) -> provisional not evaluated (0 scans / plans)", not f and ps["plans"] == 0 and ps["insideScans"] == 0)
    f, _, ps = prov_tick(st, 1, {lg: ("Both", 4050.0) for lg in P08_ORDER}, live, c, Broker(), useProv=False)
    check("AL24 useProvisionalAlert=false -> 0 Inside scans / 0 TradePlan / 0 Qty / 0 alert",
          not f and (ps["insideScans"], ps["plans"], ps["qtys"]) == (0, 0, 0))
    # AL14 / AL15 / AL16 provisional does not touch orders / ActivePos
    st, br, ap = AlertState(), Broker(), new()
    before = (list(br.orders), dict(ap))
    prov_tick(st, 1, {lg: ("Both", 4050.0) for lg in P08_ORDER}, live, c, br)
    check("AL14/AL15 provisional tick -> 0 orders, ActivePos unchanged", (list(br.orders), dict(ap)) == before and st.alerts)
    # AL01 / trade parity with alerts ON vs OFF (dispatch outcome identical)
    import random
    rnd = random.Random(1010)
    mism = 0
    for _ in range(300):
        cands = {lg: (rnd.choice(("Long", "Short", "Both")), round(rnd.uniform(4000, 4100), 1)) for lg in P08_ORDER if rnd.random() < 0.5}
        lv = [Z(b, b + 5, rnd.choice((ST_SUP_, ST_RES_, ST_ACT, ST_BRK)), rnd.choice((1, 2, 3, 4)), tid=k)
              for k, b in enumerate(sorted(rnd.uniform(3950, 4150) for _ in range(6)))]
        outs = []
        for on in (True, False):
            st, br, ap = AlertState(), Broker(), new()
            if on:
                prov_tick(st, 1, cands, lv, c, br)
            confirmed_bar(st, 1, cands, lv, c, br, ap, useConf=on)
            outs.append((br.orders, ap))
        mism += outs[0] != outs[1]
    check("AL01/P09-parity alerts ON (prov + confirmed) vs OFF -> identical orders / ActivePos on 300 random bars", mism == 0, f"mismatch={mism}")
    # AL27 provisional fired earlier in the same bar -> confirmed entry alert still delivered (freq_all)
    st, br, ap = AlertState(), Broker(), new()
    cand = {"FVG15": ("Long", 4050.0)}
    fp, _, _ = prov_tick(st, 7, cand, live, c, br)                       # forming tick
    ent, _, n = confirmed_bar(st, 7, cand, live, c, br, ap)               # closing tick of the same bar
    worst = [(b, k) for b, k, _, _ in st.delivered]
    old = AlertState()                                                    # same sequence if confirmed used freq_once_per_bar
    old.call(7, "仮", "FVG15", 1, "freq_once_per_bar")
    old.call(7, "確定", "FVG15", 1, "freq_once_per_bar")
    check("AL27 same bar: provisional fired -> confirmed entry alert still delivered (freq_all), even if the "
          "once-per-bar quota were script-wide (once_per_bar would drop it)",
          fp and ent and n == 1 and worst == [(7, "仮"), (7, "確定")] and [k for _, k, _, _ in old.delivered] == ["仮"])
    # AL28 several confirmed candidates in one bar -> 1 entry, 1 confirmed call
    st, br, ap = AlertState(), Broker(), new()
    ent, _, n = confirmed_bar(st, 8, {lg: ("Both", 4050.0) for lg in P08_ORDER}, live, c, br, ap)
    check("AL28 many confirmed candidates same bar -> strategy.entry 1 / confirmed alert call 1 (freq_all cannot duplicate)",
          ent and n == 1 and len(conf(st)) == 1 and len(st.delivered) == 1)
    # AL29 no entry -> 0 confirmed calls even with freq_all
    zero = True
    for cands, brx, kw in (({"FVG": ("Long", 3000.0)}, Broker(), {}), ({"FVG": ("Long", 4035.0)}, Broker(), {}),
                           ({"FVG": ("Long", 4050.0)}, Broker(position_size=1.0, opentrades=1), {}),
                           ({"FVG": ("Long", 4050.0)}, Broker(), dict(capital=1.0)),
                           ({"FVG": ("Long", 4050.0)}, Broker(), dict(isGold=False)), ({}, Broker(), {})):
        st, ap = AlertState(), new()
        ent, _, n = confirmed_bar(st, 9, cands, live, c, brx, ap, **kw)
        zero = zero and not ent and n == 0 and not st.alerts and not st.delivered
    check("AL29 confirmed freq_all: no real entry (Plan FAIL / Inside / held / Qty / non-Gold / no signal) -> 0 alert calls", zero)
    # AL22 BE activation adds no entry alert (BE section has no alert; mirror: run_be_sim emits none)
    check("AL22 BE activation -> no entry alert (static: 0 alert() in Section 09)", "alert(" not in code_only(AH[AH.find("// 09. BREAK EVEN"):AH.find("// 10. PROVISIONAL ALERT")]))


# ============================================================================
# P11 : PracticalZoneStrategy_LONG (production integration)
# ============================================================================
LG_PATH = os.path.join(ROOT, "PracticalZoneStrategy_LONG.pine")


def _git_rev_file(rev, path):
    import subprocess
    return subprocess.run(["git", "-C", ROOT, "show", f"{rev}:{path}"], capture_output=True, text=True).stdout


#  ★ P11 / P12 integration fixtures validate the integration-stage artifact (e3680f5 = P12 HEAD).
#    The current files are tied to it by the P13A exact-transform fixture (current == p13a_transform(e3680f5)).
P12_STAGE = "e3680f5"
LG_CUR = open(LG_PATH, encoding="utf-8").read() if os.path.exists(LG_PATH) else ""
LG = _git_rev_file(P12_STAGE, "PracticalZoneStrategy_LONG.pine") or LG_CUR


def _strip_str(l):
    return re.sub(r'"[^"]*"', '""', l)


def fixture_p11_static():
    check("P11 LONG file exists", bool(LG))
    if not LG:
        return
    lc = code_only(LG)
    lcs = "\n".join(_strip_str(l) for l in lc.split("\n"))
    check("P11 imports: ZoneEnginePractical/3 as zn + SignalEnginePractical/1 as sg (exactly)",
          re.findall(r"^import .*$", lc, re.M) == ["import sekine3310/ZoneEnginePractical/3 as zn",
                                                  "import sekine3310/SignalEnginePractical/1 as sg"])
    # ---- direction ----
    disp = code_only(LG[LG.find("// 08. DISPATCH"):LG.find("// 09. BREAK EVEN")])
    calls = re.findall(r"e := f_tryEntry\(activePos, ds, (\w+), ([^,]+), (-?\d+), ([^,]+), globalPositionBlocked, enteredThisBar\)", disp)
    check("L01 every dispatch call is dir = 1; strategy.short = 0",
          len(calls) == 8 and all(c_[2] == "1" for c_ in calls) and "strategy.short" not in LG)
    sec10 = code_only(LG[LG.find("// 10. PROVISIONAL ALERT"):])
    check("L02 confirmed alert reachable only via dir = 1 entries (f_tryEntry is the only confirmed alert site)",
          lcs.count("alert(") == 2 and code_only(func_block(LG, "f_tryEntry")).count("alert(") == 1)
    check("L03 provisional: Long previews only (winDir := 1, entry dir 1, no Short preview used)",
          "winDir   := 1" in sec10 and "f_provEval(ps, f_provLogic(li), f_provPreviewLong(li), 1, close)" in sec10
          and not re.search(r"previewShort|pv\w+Short|provFvg15ShortRaw\b(?!\])", sec10.replace("[provFvg15LongRaw, provFvg15ShortRaw]", "")))
    check("L03b enableLong / enableShort are constants true / false (old Main defaults), not inputs",
          "bool enableLong  = true" in lc and "bool enableShort = false" in lc and not re.search(r"^enable(Long|Short)\s*=\s*input", lc, re.M))
    check("L04 probe inputs / helpers fully removed",
          not re.search(r"G_PROBE|probeEvery|\bc[1-8](On|Dr|Of)\b|f_provOn|f_provDirMode|f_provOffset", lc))
    # ---- candidate / preview mapping ----
    exp = [("LOGIC_FVG15", "fvg15Sig.longSignal", "fvg15Sig.entryPrice"), ("LOGIC_FVG", "fvgSig.longSignal", "fvgSig.entryPrice"),
           ("LOGIC_FVG_ABS15", "absSig.long15", "absSig.entryPrice"), ("LOGIC_FVG_ABS5", "absSig.long5", "absSig.entryPrice"),
           ("LOGIC_ZONE_RB", "zlSig.reboundLong", "zlSig.entryPrice"), ("LOGIC_ZONE_FK", "zlSig.fakeLong", "zlSig.entryPrice"),
           ("LOGIC_ZONE_RT", "zlSig.retestLong", "zlSig.entryPrice"), ("LOGIC_ZONE_BK", "zlSig.breakLong", "zlSig.entryPrice")]
    check("L05/L08 8 logics connected; confirmed candidate = SignalEngine output, entryPrice = that signal's entryPrice "
          "(old Main 7.1-7.4 call-sites)", [(a, b, d) for a, b, _, d in calls] == exp, str(calls))
    check("L06 dispatch priority FVG15 > FVG > ABS15 > ABS5 > RB > FK > RT > BK",
          [P08_CONST[c_[0]] for c_ in calls] == P08_ORDER)
    mcalls = code_only(MAIN[MAIN.find("// ---- 7.1 FVG15 Logic"):MAIN.find("// ---- 7.5 Future Logic")])
    for lg_, sig_, px_ in exp:
        check(f"L08 old Main uses the same {lg_} Long signal / entryPrice",
              re.search(r"f_submitSignal\(" + lg_ + r", " + re.escape(sig_) + r"\b[^\n]*,\s+1, " + re.escape(px_) + r"\)", mcalls) is not None)
    pv = code_only(func_block(LG, "f_provPreviewLong"))
    pv_terms = re.findall(r"\? ([\w\.]+)", pv) + re.findall(r": ([\w\.]+)\s*$", pv, re.M)
    check("L07 Preview = SignalEngine Preview outputs only, priority order (fvg15Preview / previewLong / previewLong15 / "
          "previewLong5 / pvReboundLong / pvFakeLong / pvRetestLong / pvBreakLong)",
          pv_terms == ["provFvg15LongRaw", "fvgSig.previewLong", "absSig.previewLong15", "absSig.previewLong5",
                       "zlSig.pvReboundLong", "zlSig.pvFakeLong", "zlSig.pvRetestLong", "zlSig.pvBreakLong"]
          and "[provFvg15LongRaw, provFvg15ShortRaw] = sg.fvg15Preview(fvg15Base, fvg15Sig)" in lc
          and "[provFvg15LongRaw, provFvg15ShortRaw] = sg.fvg15Preview(fvg15Base, fvg15Sig)" in code_only(MAIN), str(pv_terms))
    mprov = code_only(MAIN[MAIN.find("bool provFvgLongRaw"):MAIN.find("//  ---- Group Gate / 優先順位")])
    check("L07 old Main Section 10 reads the same Preview fields",
          all(x in mprov for x in ("fvgSig.previewLong", "absSig.previewLong5", "absSig.previewLong15", "zlSig.pvReboundLong",
                                   "zlSig.pvFakeLong", "zlSig.pvRetestLong", "zlSig.pvBreakLong")))
    pl = code_only(func_block(LG, "f_provLogic"))
    check("L07 provisional priority list == dispatch order", [P08_CONST[x] for x in re.findall(r"(LOGIC_\w+)", pl)] == P08_ORDER)
    check("P11 provisional entry price = close (old Main f_canEnter(logicId, dir, close))",
          "f_provWouldEnter" in MAIN and "r := f_canEnter(logicId, dir, close)" in code_only(MAIN))
    # ---- consume ----
    blocks = [code_only(b) for b in re.split(r"\n    // \d ", LG[LG.find("// 08. DISPATCH"):LG.find("// 09. BREAK EVEN")])]
    def blk(lg_):
        found = [b for b in blocks if f"f_tryEntry(activePos, ds, {lg_}," in b]
        assert len(found) == 1, lg_
        return found[0]
    cons = {"LOGIC_FVG15": ["sg.consumeFvg15(fvg15Ord, 1)", "fvg15Eng.longArmed := false"],
            "LOGIC_FVG": ["fvgEng.longArmed := false"],
            "LOGIC_FVG_ABS15": ["sg.consumeFvgAbs(fvgAbsEng, 15)"], "LOGIC_FVG_ABS5": ["sg.consumeFvgAbs(fvgAbsEng, 5)"],
            "LOGIC_ZONE_RB": ["sg.consumeZoneEvt(zoneEvtEng, 0)"], "LOGIC_ZONE_FK": ["sg.consumeZoneEvt(zoneEvtEng, 1)"],
            "LOGIC_ZONE_RT": ["sg.consumeZoneEvt(zoneEvtEng, 2)"], "LOGIC_ZONE_BK": ["sg.consumeZoneEvt(zoneEvtEng, 3)"]}
    labels = dict(zip(cons, ["L10", "L09", "L11", "L12", "L13", "L14", "L15", "L16"]))
    for lg_, cs in cons.items():
        b = blk(lg_)
        lines_ = [l for l in b.split("\n") if l.strip()]
        guard_ok = all(any(l.strip() == x for l in lines_) for x in cs)
        under_e = all(re.search(r"\n\s*if e( and fvgSig\.noTriggerMode)?\n(.*\n)*?\s*" + re.escape(x), "\n" + b) for x in cs)
        check(f"{labels[lg_]} {P08_CONST[lg_]} consume only inside `if e` (real entry) right after its f_tryEntry",
              guard_ok and under_e and all(lc.count(x) == 1 for x in cs if "consume" in x))
    mf15 = code_only(MAIN[MAIN.find("if fvg15EidLong != \"\""):MAIN.find("if fvg15EidShort != \"\"")])
    check("L10 FVG15 consume == old Main 7.1 (consumeFvg15(fvg15Ord, 1) then noTriggerMode -> fvg15Eng.longArmed := false)",
          "sg.consumeFvg15(fvg15Ord, 1)" in mf15 and "if fvg15Base.noTriggerMode" in mf15 and "fvg15Eng.longArmed := false" in mf15
          and "if fvg15Base.noTriggerMode" in blk("LOGIC_FVG15"))
    check("L09 FVG armed reset == old Main 7.2 (noTriggerMode and entered -> fvgEng.longArmed := false)",
          'if fvgSig.noTriggerMode and fvgEidLong != ""' in code_only(MAIN) and "if e and fvgSig.noTriggerMode" in blk("LOGIC_FVG"))
    check("L09-L16 no consume / armed write anywhere outside the dispatch",
          sum(lc.count(x) for x in ("sg.consumeFvg15(", "sg.consumeFvgAbs(", "sg.consumeZoneEvt(", "longArmed :=", "shortArmed :=")) ==
          sum(disp.count(x) for x in ("sg.consumeFvg15(", "sg.consumeFvgAbs(", "sg.consumeZoneEvt(", "longArmed :=", "shortArmed :=")) == 9)
    # ---- zone snapshot ----
    snap = code_only(LG[LG.find("int zoneMinStrength = zn.strengthIdx(zoneSignalMinStrStr)"):LG.find("//  各Zone Logicの保有状況。")])
    check("L17 snapshot: SUPPORT (+1) and RESISTANCE (-1), strength >= Min Strength, zoneId = Practical trackId, 6 fields copied",
          "if zsZ.strength >= zoneMinStrength and (zsZ.state == ST_SUPPORT or zsZ.state == ST_RESIST)" in snap
          and "array.push(zSnapSide,  zsZ.state == ST_SUPPORT ? 1 : -1)" in snap and "array.push(zSnapId,    zsZ.trackId)" in snap
          and all(f"array.push({a}" in snap for a in ("zSnapTop,   zsZ.top", "zSnapBot,   zsZ.bottom", "zSnapStr,   zsZ.strength", "zSnapScore, zsZ.score")))
    check("L17 snapshot arrays: var + array.clear (6), no per-bar array.new for the snapshot",
          snap.count("array.clear(") == 6 and len(re.findall(r"^var array<\w+>\s+zSnap\w+\s*=", snap, re.M)) == 6)
    check("L17 ST_SUPPORT / ST_RESIST == ZoneEnginePractical (1 / 2)",
          "int ST_SUPPORT = 1" in lc and "int ST_RESIST  = 2" in lc and "int ST_SUPPORT = 1" in ZEP and "int ST_RESIST  = 2" in ZEP)
    LI = parse_inputs(LG)
    ms = LI.get("zoneSignalMinStrStr", {})
    check("L18 Zone Signal Min Strength input: default Strong, title 'Zone Signal · Min Strength'",
          ms.get("default") == '"Strong"' and ms.get("title") == '"Zone Signal · Min Strength"', str(ms))
    check("L19/L20 options Weak / Medium / Strong / Very Strong -> zn.strengthIdx (Medium / Very Strong selectable, not fixed)",
          ms.get("options") == '["Weak", "Medium", "Strong", "Very Strong"]' and "zoneBosMinStrStr" not in lc
          and 'export strengthIdx(string s) =>' in ZEP)
    # ---- origin / touch ----
    ro = code_only(func_block(LG, "f_recordZoneOrigin"))
    check("L21 originTrackId = SignalEngine event zoneId at the signal index (sigRebound / sigFake / sigRetest / sigBreak)",
          "origin := array.get(zoneEvtEng.evts, evIdx).zoneId" in ro and
          all(f"f_recordZoneOrigin(activePos, zoneEvtEng.{x})" in blk(lg_) for lg_, x in
              (("LOGIC_ZONE_RB", "sigRebound"), ("LOGIC_ZONE_FK", "sigFake"), ("LOGIC_ZONE_RT", "sigRetest"), ("LOGIC_ZONE_BK", "sigBreak"))))
    check("L21b origin recorded BEFORE consume in each zone block",
          all(blk(lg_).find("f_recordZoneOrigin") < blk(lg_).find("sg.consumeZoneEvt") for lg_ in
              ("LOGIC_ZONE_RB", "LOGIC_ZONE_FK", "LOGIC_ZONE_RT", "LOGIC_ZONE_BK")))
    check("L22 Touch Count lookup only in f_recordZoneOrigin, called only inside the 4 zone `if e` blocks (no per-bar search)",
          lc.count("zn.zoneTouchCount(") == 1 and "zn.zoneTouchCount(zoneEng, i)" in ro and lc.count("f_recordZoneOrigin(activePos") == 4
          and all(lc.find(x) > lc.find("// 08. DISPATCH") for x in ("f_recordZoneOrigin(activePos",)))
    check("L23 FVG-family entries keep originTrackId / entryTouchCount = na (f_tryEntry writes na; no origin call)",
          "ap.originTrackId   := na" in code_only(func_block(LG, "f_tryEntry")) and
          all("f_recordZoneOrigin" not in blk(lg_) for lg_ in ("LOGIC_FVG15", "LOGIC_FVG", "LOGIC_FVG_ABS15", "LOGIC_FVG_ABS5")))
    # ---- engine counts ----
    check("L24 zn.update = 1 / bar, one ZoneEngine", len(re.findall(r"\bzn\.update\(", lc)) == 1 and len(re.findall(r"zn\.newEngine\(", lc)) == 1)
    check("L25 updateZoneEvents = 1 call, only under useZoneAny",
          lc.count("sg.updateZoneEvents(") == 1 and re.search(r"if useZoneAny\n    zlSig := sg\.updateZoneEvents\(", lc) is not None)
    check("P11 engine instances: FvgEngine x2 (FVG / FVG15 base), Fvg15Engine, FvgAbsEngine, ZoneEvtEngine (all var)",
          lc.count("sg.newFvgEngine()") == 2 and lc.count("sg.newFvg15Engine()") == 1 and lc.count("sg.newFvgAbsEngine()") == 1
          and lc.count("sg.newZoneEvtEngine()") == 1 and len(re.findall(r"^var sg\.(FvgEngine|Fvg15Engine|FvgAbsEngine|ZoneEvtEngine)\s", lc, re.M)) == 5)
    check("P11 updateFvg: base every bar + FVG15 2nd call only under useFvg15Logic (not merged); updateFvg15 / updateFvgAbs gated",
          lc.count("sg.updateFvg(") == 2 and re.search(r"^sg\.FvgSignal fvgSig = sg\.updateFvg\(", lc, re.M) is not None
          and re.search(r"if useFvg15Logic\n    fvg15Base := sg\.updateFvg\(", lc) is not None
          and re.search(r"if absAnyOn\n    absSig := sg\.updateFvgAbs\(", lc) is not None)
    # ---- verbatim ports of old Main ----
    def same_block(a, b):
        return code_only(MAIN[MAIN.find(a):MAIN.find(b)]) == code_only(LG[LG.find(a):LG.find(b)])
    check("P11 old Main 6.1-6.3 (updateFvg / FVG15 / FVGABS env + update) ported verbatim",
          same_block("// ---- 6.1 FVG Logic", "// ---- 6.4 Zone 4-Logic"))
    check("P11 old Main zone vol / ZoneTfEnvCfg x8 block ported verbatim (except var)",
          code_only(MAIN[MAIN.find("//  ---- Zone系専用 高速ボラ"):MAIN.find("sg.ZoneEnvFeed zoneEnvFeed")]) ==
          code_only(LG[LG.find("//  ---- Zone系専用 高速ボラ"):LG.find("sg.ZoneEnvFeed zoneEnvFeed")]))
    mt = code_only(MAIN[MAIN.find("sg.ZoneTfEnvCfg zcRbL"):MAIN.find("sg.ZoneLogicSignal zlSig")])
    lt = code_only(LG[LG.find("var sg.ZoneTfEnvCfg zcRbL"):LG.find("sg.ZoneLogicSignal zlSig")])
    check("P11 ZoneTfEnvCfg x8 / ZoneEnvSet identical to old Main (var only)", re.sub(r"^var ", "", lt, flags=re.M) == mt)
    check("P11 updateZoneEvents call arguments identical to old Main",
          code_only(MAIN[MAIN.find("sg.ZoneLogicSignal zlSig"):MAIN.find("// ============================================================================\n// 07. ORDER")]).strip() ==
          code_only(LG[LG.find("sg.ZoneLogicSignal zlSig"):LG.find("// ============================================================================\n// 08. DISPATCH")]).strip())
    feedm = code_only(MAIN[MAIN.find("// ---- 3.3 Signal Engine Feed (FVG)"):MAIN.find("sg.FvgFeed fvgFeed = sg.FvgFeed.new(")])
    feedl = code_only(LG[LG.find("// ---- 3.3 Signal Engine Feed (FVG)"):LG.find("sg.FvgFeed fvgFeed = sg.FvgFeed.new(")])
    check("P11 Signal Feed requests (trigger / ATR / env / FVG env / FVG15 / ABS / 1M BOS / zone TF / break / daily / accum) verbatim",
          feedm == feedl and feedm.count("request.") == 23)
    check("P11 Session / News filter + Accum zone-centre collection verbatim",
          code_only(MAIN[MAIN.find("// ---- 3.1 共通フィルタ"):MAIN.find("// ---- 3.2 Zone Engine Feed")]) ==
          code_only(LG[LG.find("// ---- 3.1 共通フィルタ"):LG.find("// ---- 3.2b Accum内")]) and
          code_only(MAIN[MAIN.find("// ---- 3.2b Accum内"):MAIN.find("// ---- 3.3 Signal Engine Feed")]) ==
          code_only(LG[LG.find("// ---- 3.2b Accum内"):LG.find("// ---- 3.3 Signal Engine Feed")]))
    E24 = "// ---- 2.4 Signal Engine Config (FVG15 Logic)"
    m_cfg = {l.strip() for l in code_only(MAIN[MAIN.find("sg.FvgCfg fvgCfg = sg.newFvgCfg()"):MAIN.find(E24)]).split("\n") if l.strip().startswith("fvgCfg.")}
    l_cfg = {l.strip() for l in code_only(LG[LG.find("var sg.FvgCfg fvgCfg"):LG.find(E24)]).split("\n") if l.strip().startswith("fvgCfg.")}
    check("P11 FvgCfg assignments == old Main minus minScore* (field removed in P01), set once at barstate.isfirst",
          l_cfg == {x for x in m_cfg if not x.startswith("fvgCfg.minScore")} and len(l_cfg) == 63)
    m15 = [l.strip() for l in code_only(MAIN[MAIN.find("sg.FvgCfg fvg15Cfg"):MAIN.find("// 03. EXTERNAL DATA FEED")]).split("\n") if l.strip().startswith("fvg15Cfg.")]
    l15 = [l.strip() for l in code_only(LG[LG.find("    fvg15Cfg := fvgCfg.copy()"):LG.find("// 03. EXTERNAL DATA FEED")]).split("\n") if l.strip().startswith("fvg15Cfg.")]
    check("P11 fvg15Cfg = fvgCfg.copy() + same 8 overrides (once)", m15 == l15 and len(l15) == 8)
    for t in ("FvgTrigCfg fvgTrigCfg", "FvgEnvCfg fvgEnvCfg", "FvgAccCfg fvgAccCfg"):
        mm = code_only(MAIN[MAIN.find("sg." + t):MAIN.find(")", MAIN.find("sg." + t)) + 1])
        ll = code_only(LG[LG.find("sg." + t):LG.find(")", LG.find("sg." + t)) + 1])
        check(f"P11 {t.split()[0]} (passed into request) built per bar exactly as old Main (not via var)", mm == ll and "var sg." + t not in lc)
    mz = sorted(l.strip() for l in code_only(MAIN[MAIN.find("sg.ZoneCommonCfg zoneCmnCfg"):MAIN.find("//  ---- Zone系専用 高速ボラ")]).split("\n") if l.strip().startswith("zoneCmnCfg."))
    lz = sorted(l.strip() for l in code_only(LG[LG.find("var sg.ZoneCommonCfg zoneCmnCfg"):LG.find("//  ---- Zone系専用 高速ボラ")]).split("\n") if l.strip().startswith("zoneCmnCfg."))
    check("P11 ZoneCommonCfg assignments == old Main (incl. Zone Logic breakBuffer = zoneBreakBuffer, separate from Practical breakBuffer)",
          mz == lz and "zoneCmnCfg.breakBuffer         := zoneBreakBuffer" in lz)
    # ---- inputs ----
    MI_ = parse_inputs(MAIN)
    names = [n for n in parse_inputs(MAIN[MAIN.find("// 01-1. COMMON INPUTS"):MAIN.find("// 01-2. ZONE ENGINE INPUTS")])]
    names += [n for n in parse_inputs(MAIN[MAIN.find("// 01-3. SIGNAL ENGINE INPUTS"):MAIN.find("// 01-4. TRADE ENGINE INPUTS")])]
    names = [n for n in names if n not in ("enableLong", "enableShort", "zoneBosMinStrStr")]
    diff = [n for n in names if LI.get(n) != MI_.get(n)]
    check("P11 Signal inputs == old Main (name / type / default / title / group / options / min / max / step)",
          not diff and len(names) > 250, f"{len(names)} inputs" if not diff else str(diff))
    check("P11 defaults kept: ZONEFAKE OFF / ZONERETEST OFF / Provisional OFF / Confirmed ON / Zone Logic Break Buffer 3",
          LI["useZoneFake"]["default"] == "false" and LI["useZoneRetest"]["default"] == "false"
          and LI["useProvisionalAlert"]["default"] == "false" and LI["useConfirmedAlert"]["default"] == "true"
          and LI["zoneBreakBuffer"]["default"] == "3.0")
    # ---- P10 control parity ----
    #  LONG-only specialisation (P11 cleanup): the only allowed text differences vs P10.
    def long_spec(t):
        t = t.replace("strategy.entry(eid, dir > 0 ? strategy.long : strategy.short, qty = qty)", "strategy.entry(eid, strategy.long, qty = qty)")
        t = t.replace('alert(f_entryAlertMsg("確定", logicId, dir, p, qty), alert.freq_all)', 'alert(f_entryAlertMsgLong("確定", logicId, p, qty), alert.freq_all)')
        t = t.replace('alert(f_entryAlertMsg("仮", winLogic, winDir, win.plan, win.qty), alert.freq_once_per_bar)',
                      'alert(f_entryAlertMsgLong("仮", winLogic, win.plan, win.qty), alert.freq_once_per_bar)')
        t = t.replace("f_entryAlertMsg(string kind, string logicId, int dir, zn.TradePlan p, float qty) =>",
                      "f_entryAlertMsgLong(string kind, string logicId, zn.TradePlan p, float qty) =>")
        t = t.replace('"【" + kind + " " + (dir > 0 ? "LONG" : "SHORT") + "】" +', '"【" + kind + " LONG】" +')
        return t
    for a, b in (("// 05. TRADE PLAN / RISK / QTY", "// 07. PROBE CANDIDATES"), ("// 09. BREAK EVEN", "// 10. PROVISIONAL ALERT")):
        bb = "// 07. SIGNAL ENGINE" if "PROBE" in b else b
        check(f"P11 P10 control block '{a[3:]}' identical (code; LONG-only specialisation only)",
              long_spec(code_only(AH[AH.find(a):AH.find(b)])) == code_only(LG[LG.find(a):LG.find(bb)]))
    for fn in ("f_provEval", "f_insideAnyZone", "f_qty", "f_tpDepthFor", "f_breakEvenTriggerFor", "f_provSlot"):
        check(f"P11 {fn} identical to P10", code_only(func_block(LG, fn)) == code_only(func_block(AH, fn)) != "")
    p10p = long_spec(code_only(AH[AH.find("varip int gProvLastBar"):AH.find("// ---- Flat 遷移検知用")])).split("\n")
    l11p = code_only(LG[LG.find("varip int gProvLastBar"):LG.find("// ---- Flat 遷移検知用")]).split("\n")
    p10_ = [l for l in p10p if not re.search(r"pfire|f_provDirMode|dm != |cnd|int    li |int    d   |for k = 0 to 15|winDir   := d|f_provOffset|ProvEval ev", l)]
    l11_ = [l for l in l11p if not re.search(r"for li = 0 to 7|winDir   := 1|ProvEval ev", l)]
    check("P11 provisional winner / provSent / per-bar guard / alert identical to P10 (only candidate source changed)", p10_ == l11_)
    check("P11 Zone block (inputs / ZoneCfg / Feed / zn.update) identical to P10",
          code_only(AH[AH.find("// 01-2. ZONE ENGINE INPUTS"):AH.find("// 04. TRADE PLAN / RISK / QTY INPUTS")]) ==
          code_only(LG[LG.find("// 01-2. ZONE ENGINE INPUTS"):LG.find("// 01-1. COMMON INPUTS (Signal)")]).rstrip("\n") + "\n" or
          code_only(AH[AH.find("// 01-2. ZONE ENGINE INPUTS"):AH.find("// 04. TRADE PLAN / RISK / QTY INPUTS")]).strip() ==
          code_only(LG[LG.find("// 01-2. ZONE ENGINE INPUTS"):LG.find("// 01-1. COMMON INPUTS (Signal)")]).strip().rsplit("\n", 1)[0].strip()
          or code_only(AH[AH.find("// 01-2. ZONE ENGINE INPUTS"):AH.find("// 04. TRADE PLAN / RISK / QTY INPUTS")]).strip() in code_only(LG))
    check("P11 16 provisional slots kept (P10 f_provSlot unchanged; 8-slot reduction deferred to P13)",
          "varip array<bool> gProvSent = array.new_bool(16, false)" in lc)
    # ---- prohibited ----
    bad = [t for t in ("tpManagementMode", "Dynamic", "gTradeTP", "gTradeSL", "gTradeBE", "f_isOpenEntry", "map.new", "map<",
                       "label.new", "box.new", "table.new", "line.new", "plot(", "plotshape", "bgcolor(", "strategy.close(",
                       "f_openCount", "ZONEBOS", "ZONESR", "DXY") if t in lcs]
    check("L26-L29 no Dynamic TP / map trade mgmt / drawing / plots / old per-logic open loops / excluded logics", not bad, str(bad))
    check("L28 no opentrades / closedtrades loop or per-trade accessor",
          not re.search(r"for .*(opentrades|closedtrades)", lc) and not re.search(r"strategy\.(opentrades|closedtrades)\.\w+", lc))
    # ---- request audit (default inputs) ----
    req = re.findall(r"request\.(security_lower_tf|security)\(", lc)
    check("P11 request call sites: Zone 8 + Signal 23 (= P10 Zone block + old Main Section 03 verbatim)",
          len(req) == 31 and code_only(B_ZONE_SECTION(LG)).count("request.") == 8, str(len(req)))


    # ---- P11 LONG-only structural cleanup (L30-L33) ----
    te10 = code_only(func_block(AH, "f_tryEntry")).split("\n")
    te11 = code_only(func_block(LG, "f_tryEntry")).split("\n")
    swap = {"strategy.entry(eid, dir > 0 ? strategy.long : strategy.short, qty = qty)": "strategy.entry(eid, strategy.long, qty = qty)",
            'alert(f_entryAlertMsg("確定", logicId, dir, p, qty), alert.freq_all)': 'alert(f_entryAlertMsgLong("確定", logicId, p, qty), alert.freq_all)'}
    te10_long = [l.replace(l.strip(), swap[l.strip()]) if l.strip() in swap else l for l in te10]
    check("L30 strategy.short token = 0 in PracticalZoneStrategy_LONG.pine (code and comments)", "strategy.short" not in LG)
    check("L31 strategy.entry direction = strategy.long only (1 call site)",
          re.findall(r"strategy\.entry\(([^)]*)\)", lc) == ["eid, strategy.long, qty = qty"])
    check("L31 f_tryEntry == P10 f_tryEntry with only the dir > 0 branch kept (entry direction / confirmed alert helper)",
          te11 == te10_long)
    am10 = code_only(func_block(AH, "f_entryAlertMsg"))
    am11 = code_only(func_block(LG, "f_entryAlertMsgLong"))
    exp_long = am10.replace("f_entryAlertMsg(string kind, string logicId, int dir, zn.TradePlan p, float qty) =>",
                            "f_entryAlertMsgLong(string kind, string logicId, zn.TradePlan p, float qty) =>") \
                   .replace('"【" + kind + " " + (dir > 0 ? "LONG" : "SHORT") + "】" +', '"【" + kind + " LONG】" +')
    check("L31b alert text LONG-only: f_entryAlertMsgLong == P10 f_entryAlertMsg (dir > 0) ; no SHORT literal; only 【仮 LONG】/【確定 LONG】",
          am11 == exp_long and '"SHORT"' not in lc and "SHORT" not in lcs.replace('""', "") and "f_entryAlertMsg(" not in lc
          and lc.count("f_entryAlertMsgLong(") == 3)
    # L32: identical Long behaviour vs cffdbb3 : only the 4 specialised lines differ
    prev = open(os.path.join(ROOT, "tests", "fixtures_p11_cffdbb3.pine"), encoding="utf-8").read() if os.path.exists(
        os.path.join(ROOT, "tests", "fixtures_p11_cffdbb3.pine")) else None
    if prev is None:
        import subprocess
        prev = subprocess.run(["git", "-C", ROOT, "show", "cffdbb3:PracticalZoneStrategy_LONG.pine"], capture_output=True, text=True).stdout
    a_ = code_only(prev).split("\n")
    b_ = lc.split("\n")
    ops = [op for op in difflib.SequenceMatcher(None, a_, b_, autojunk=False).get_opcodes() if op[0] != "equal"]
    chg = [([x.strip() for x in a_[i1:i2]], [x.strip() for x in b_[j1:j2]]) for t, i1, i2, j1, j2 in ops]
    exp_chg = [(['f_entryAlertMsg(string kind, string logicId, int dir, zn.TradePlan p, float qty) =>',
                 '"【" + kind + " " + (dir > 0 ? "LONG" : "SHORT") + "】" +'],
                ['f_entryAlertMsgLong(string kind, string logicId, zn.TradePlan p, float qty) =>', '"【" + kind + " LONG】" +']),
               (['strategy.entry(eid, dir > 0 ? strategy.long : strategy.short, qty = qty)'], ['strategy.entry(eid, strategy.long, qty = qty)']),
               (['alert(f_entryAlertMsg("確定", logicId, dir, p, qty), alert.freq_all)'], ['alert(f_entryAlertMsgLong("確定", logicId, p, qty), alert.freq_all)']),
               (['alert(f_entryAlertMsg("仮", winLogic, winDir, win.plan, win.qty), alert.freq_once_per_bar)'],
                ['alert(f_entryAlertMsgLong("仮", winLogic, win.plan, win.qty), alert.freq_once_per_bar)'])]
    check("L32 Long entry result identical to cffdbb3: only the dir>0-branch specialisations differ (dir is always 1)",
          bool(prev) and chg == exp_chg, str(chg)[:400])
    # mirror: the two message expressions produce identical text for dir = 1
    msg10 = lambda kind, d: "【" + kind + " " + ("LONG" if d > 0 else "SHORT") + "】"
    msg11 = lambda kind: "【" + kind + " LONG】"
    check("L32b alert header text for dir = 1 unchanged (【仮 LONG】 / 【確定 LONG】)",
          all(msg10(k, 1) == msg11(k) for k in ("仮", "確定")))
    sigsec = lambda src: code_only(src[src.find("// 07. SIGNAL ENGINE"):src.find("// 08. DISPATCH")])
    check("L33 Short shared Signal state kept: Section 07 identical to cffdbb3 (enableShort feed / absEnvShortOk / zone Short env / both sides)",
          sigsec(prev) == sigsec(LG) and "zoneCmnCfg.enableShort         := enableShort" in lc and "bool absEnvShortOk = sg.fvgAbsEnvShort(" in lc
          and "allowShort = useFvgLogic and enableShort" in lc and "rbShort = zcRbS" in lc and "zSnapSide,  zsZ.state == ST_SUPPORT ? 1 : -1" in lc)

def B_ZONE_SECTION(src):
    return src[src.find("// 01-2. ZONE ENGINE INPUTS"):src.find("// 01-1. COMMON INPUTS (Signal)")]


# ---- Python mirror : production dispatch + consume + origin / touch -------------
def p11_dispatch(sigs, live_ok, br, ap, zone_evts=None, zone_sig=None, live_zones=None, **kw):
    """sigs: {logic: (signal, entryPrice)}; live_ok: {logic: bool} = would pass Inside/Plan/TP/Qty.
    Returns (entered_logic, consumed list, ap)."""
    blocked = br.position_size != 0 or br.opentrades > 0
    entered, consumed = None, []
    for lg in P08_ORDER:
        sig, px = sigs.get(lg, (False, None))
        ok = sig and kw.get("isGold", True) and not blocked and entered is None and live_ok.get(lg, False)
        if ok:
            entered = lg
            ap.update(logicId=lg, dir=1, entryPrice=px, originTrackId=None, entryTouchCount=None)
            if lg in ("ZONEREBOUND", "ZONEFAKE", "ZONERETEST", "ZONEBREAK"):
                idx = zone_sig.get(lg, -1)
                origin = zone_evts[idx]["zoneId"] if 0 <= idx < len(zone_evts) else None
                touch = next((z["touch"] for z in live_zones if z["trackId"] == origin), None) if origin is not None else None
                ap.update(originTrackId=origin, entryTouchCount=touch)
            consumed.append(lg)
    return entered, consumed, ap


def fixture_p11_behaviour():
    new = lambda: dict(logicId="", dir=0, entryPrice=None, originTrackId=None, entryTouchCount=None)
    allsig = {lg: (True, 4000.0 + i) for i, lg in enumerate(P08_ORDER)}
    e, c_, ap = p11_dispatch(allsig, {lg: True for lg in P08_ORDER}, Broker(), new())
    check("P11-D1 all 8 Long signals + all Entry-ready -> FVG15 only, consume only FVG15", e == "FVG15" and c_ == ["FVG15"])
    e, c_, ap = p11_dispatch(allsig, {lg: lg not in ("FVG15", "FVG") for lg in P08_ORDER}, Broker(), new())
    check("P11-D2 FVG15 / FVG signal true but TradePlan FAIL -> ABS15 enters; FVG15 / FVG NOT consumed", e == "FVGABS15" and c_ == ["FVGABS15"])
    e, c_, ap = p11_dispatch(allsig, {lg: True for lg in P08_ORDER}, Broker(position_size=1.0, opentrades=1), new())
    check("P11-D3 position held -> 0 entries, 0 consume", e is None and c_ == [])
    e, c_, ap = p11_dispatch(allsig, {lg: True for lg in P08_ORDER}, Broker(), new(), isGold=False)
    check("P11-D4 non-Gold -> 0 entries, 0 consume", e is None and c_ == [])
    evts = [dict(zoneId=11), dict(zoneId=22), dict(zoneId=33)]
    live = [dict(trackId=22, touch=3), dict(trackId=33, touch=0)]
    sigs = {"ZONERETEST": (True, 4010.0)}
    e, c_, ap = p11_dispatch(sigs, {"ZONERETEST": True}, Broker(), new(), evts, {"ZONERETEST": 1}, live)
    check("L21/L22 zone entry: originTrackId = event zoneId (22), entryTouchCount = current live zone touch (3)",
          e == "ZONERETEST" and ap["originTrackId"] == 22 and ap["entryTouchCount"] == 3)
    e, c_, ap = p11_dispatch({"ZONEREBOUND": (True, 4010.0)}, {"ZONEREBOUND": True}, Broker(), new(), evts, {"ZONEREBOUND": 0}, live)
    check("L22b origin zone no longer live -> originTrackId kept (11), entryTouchCount = na", ap["originTrackId"] == 11 and ap["entryTouchCount"] is None)
    e, c_, ap = p11_dispatch({"FVG": (True, 4010.0)}, {"FVG": True}, Broker(), new(), evts, {}, live)
    check("L23 FVG entry -> originTrackId / entryTouchCount = na", e == "FVG" and ap["originTrackId"] is None and ap["entryTouchCount"] is None)
    # strength filter mirror
    sidx = {"Weak": 1, "Medium": 2, "Strong": 3, "Very Strong": 4}
    zs = [dict(trackId=1, strength=2, state=1), dict(trackId=2, strength=3, state=2), dict(trackId=3, strength=4, state=1),
          dict(trackId=4, strength=4, state=0), dict(trackId=5, strength=4, state=3)]
    snap = lambda ms: [(z["trackId"], 1 if z["state"] == 1 else -1) for z in zs if z["strength"] >= sidx[ms] and z["state"] in (1, 2)]
    check("L18/L19/L20 snapshot by Min Strength: Strong -> RES 2 + SUP 3; Medium adds SUP 1; Very Strong -> SUP 3 only; ACTIVE / BROKEN never",
          snap("Strong") == [(2, -1), (3, 1)] and snap("Medium") == [(1, 1), (2, -1), (3, 1)] and snap("Very Strong") == [(3, 1)])
    check("L19/L20 ZoneEnginePractical.strengthIdx maps Weak/Medium/Strong/Very Strong to SR_WEAK..SR_VSTRONG",
          'export strengthIdx(string s) =>\n    s == "Very Strong" ? SR_VSTRONG : s == "Strong" ? SR_STRONG : s == "Medium" ? SR_MEDIUM : SR_WEAK' in ZEP)


# ============================================================================
# P12 : PracticalZoneStrategy_SHORT (production integration)
# ============================================================================
SH_PATH = os.path.join(ROOT, "PracticalZoneStrategy_SHORT.pine")
SH_CUR = open(SH_PATH, encoding="utf-8").read() if os.path.exists(SH_PATH) else ""
SH = _git_rev_file(P12_STAGE, "PracticalZoneStrategy_SHORT.pine") or SH_CUR   # P12 integration stage (see LG)


def short_spec_p10(t):
    t = t.replace("strategy.entry(eid, dir > 0 ? strategy.long : strategy.short, qty = qty)", "strategy.entry(eid, strategy.short, qty = qty)")
    t = t.replace('alert(f_entryAlertMsg("確定", logicId, dir, p, qty), alert.freq_all)', 'alert(f_entryAlertMsgShort("確定", logicId, p, qty), alert.freq_all)')
    t = t.replace('alert(f_entryAlertMsg("仮", winLogic, winDir, win.plan, win.qty), alert.freq_once_per_bar)',
                  'alert(f_entryAlertMsgShort("仮", winLogic, win.plan, win.qty), alert.freq_once_per_bar)')
    t = t.replace("f_entryAlertMsg(string kind, string logicId, int dir, zn.TradePlan p, float qty) =>",
                  "f_entryAlertMsgShort(string kind, string logicId, zn.TradePlan p, float qty) =>")
    t = t.replace('"【" + kind + " " + (dir > 0 ? "LONG" : "SHORT") + "】" +', '"【" + kind + " SHORT】" +')
    return t


def fixture_p12_static():
    check("P12 SHORT file exists", bool(SH))
    if not SH:
        return
    sc = code_only(SH)
    scs = "\n".join(_strip_str(l) for l in sc.split("\n"))
    check("P12 imports: ZoneEnginePractical/3 as zn + SignalEnginePractical/1 as sg (exactly)",
          re.findall(r"^import .*$", sc, re.M) == ["import sekine3310/ZoneEnginePractical/3 as zn",
                                                  "import sekine3310/SignalEnginePractical/1 as sg"])
    check("S01 strategy.long token = 0 (code and comments)", "strategy.long" not in SH)
    check("S02 strategy.entry = strategy.short only (1 call site)",
          re.findall(r"strategy\.entry\(([^)]*)\)", sc) == ["eid, strategy.short, qty = qty"])
    check("S03 LONG alert literal / path = 0 (no \"LONG\" in code, only 【仮 SHORT】 / 【確定 SHORT】 helper)",
          "LONG" not in sc and '"【" + kind + " SHORT】" +' in sc and "f_entryAlertMsgLong" not in sc
          and "f_entryAlertMsg(" not in sc and sc.count("f_entryAlertMsgShort(") == 3)
    check("S03b enableLong / enableShort constants = false / true (old Main Short baseline), not inputs",
          "bool enableLong  = false" in sc and "bool enableShort = true" in sc and not re.search(r"^enable(Long|Short)\s*=\s*input", sc, re.M))
    disp = code_only(SH[SH.find("// 08. DISPATCH"):SH.find("// 09. BREAK EVEN")])
    calls = re.findall(r"e := f_tryEntry\(activePos, ds, (\w+), ([^,]+), (-?\d+), ([^,]+), globalPositionBlocked, enteredThisBar\)", disp)
    exp = [("LOGIC_FVG15", "fvg15Sig.shortSignal", "fvg15Sig.entryPrice"), ("LOGIC_FVG", "fvgSig.shortSignal", "fvgSig.entryPrice"),
           ("LOGIC_FVG_ABS15", "absSig.short15", "absSig.entryPrice"), ("LOGIC_FVG_ABS5", "absSig.short5", "absSig.entryPrice"),
           ("LOGIC_ZONE_RB", "zlSig.reboundShort", "zlSig.entryPrice"), ("LOGIC_ZONE_FK", "zlSig.fakeShort", "zlSig.entryPrice"),
           ("LOGIC_ZONE_RT", "zlSig.retestShort", "zlSig.entryPrice"), ("LOGIC_ZONE_BK", "zlSig.breakShort", "zlSig.entryPrice")]
    check("S04 8 Short logics connected, every dispatch call dir = -1", len(calls) == 8 and all(c_[2] == "-1" for c_ in calls))
    check("S05 dispatch priority FVG15 > FVG > ABS15 > ABS5 > RB > FK > RT > BK", [P08_CONST[c_[0]] for c_ in calls] == P08_ORDER)
    check("S06 confirmed candidate / entryPrice = SignalEngine Short outputs", [(a, b, d) for a, b, _, d in calls] == exp, str(calls))
    mcalls = code_only(MAIN[MAIN.find("// ---- 7.1 FVG15 Logic"):MAIN.find("// ---- 7.5 Future Logic")])
    for lg_, sig_, px_ in exp:
        check(f"S06 old Main Short call-site uses the same {lg_} field / entryPrice",
              re.search(r"f_submitSignal\(" + lg_ + r", " + re.escape(sig_) + r"\b[^\n]*,\s+-1, " + re.escape(px_) + r"\)", mcalls) is not None)
    pv = code_only(func_block(SH, "f_provPreviewShort"))
    pv_terms = re.findall(r"\? ([\w\.]+)", pv) + re.findall(r": ([\w\.]+)\s*$", pv, re.M)
    check("S07 Preview = SignalEngine Short preview outputs only, priority order",
          pv_terms == ["provFvg15ShortRaw", "fvgSig.previewShort", "absSig.previewShort15", "absSig.previewShort5",
                       "zlSig.pvReboundShort", "zlSig.pvFakeShort", "zlSig.pvRetestShort", "zlSig.pvBreakShort"]
          and "[provFvg15LongRaw, provFvg15ShortRaw] = sg.fvg15Preview(fvg15Base, fvg15Sig)" in sc, str(pv_terms))
    mprov = code_only(MAIN[MAIN.find("bool provFvgLongRaw"):MAIN.find("//  ---- Group Gate / 優先順位")])
    check("S07 old Main Section 10 reads the same Short preview fields",
          all(x in mprov for x in ("fvgSig.previewShort", "absSig.previewShort5", "absSig.previewShort15", "zlSig.pvReboundShort",
                                   "zlSig.pvFakeShort", "zlSig.pvRetestShort", "zlSig.pvBreakShort", "provFvg15ShortRaw")))
    sec10 = code_only(SH[SH.find("// 10. PROVISIONAL ALERT"):])
    check("S07b provisional loop: Short previews, dir -1, winDir := -1, entry price close; priority list == dispatch",
          "f_provEval(ps, f_provLogic(li), f_provPreviewShort(li), -1, close)" in sec10 and "winDir   := -1" in sec10
          and "f_provPreviewLong" not in sc and not re.search(r"previewLong|pv\w+Long\b", sec10)
          and [P08_CONST[x] for x in re.findall(r"(LOGIC_\w+)", code_only(func_block(SH, "f_provLogic")))] == P08_ORDER)
    blocks = [code_only(b) for b in re.split(r"\n    // \d ", SH[SH.find("// 08. DISPATCH"):SH.find("// 09. BREAK EVEN")])]
    def blk(lg_):
        found = [b for b in blocks if f"f_tryEntry(activePos, ds, {lg_}," in b]
        assert len(found) == 1, lg_
        return found[0]
    cons = {"LOGIC_FVG15": ["sg.consumeFvg15(fvg15Ord, -1)", "fvg15Eng.shortArmed := false"],
            "LOGIC_FVG": ["fvgEng.shortArmed := false"],
            "LOGIC_FVG_ABS15": ["sg.consumeFvgAbs(fvgAbsEng, 15)"], "LOGIC_FVG_ABS5": ["sg.consumeFvgAbs(fvgAbsEng, 5)"],
            "LOGIC_ZONE_RB": ["sg.consumeZoneEvt(zoneEvtEng, 0)"], "LOGIC_ZONE_FK": ["sg.consumeZoneEvt(zoneEvtEng, 1)"],
            "LOGIC_ZONE_RT": ["sg.consumeZoneEvt(zoneEvtEng, 2)"], "LOGIC_ZONE_BK": ["sg.consumeZoneEvt(zoneEvtEng, 3)"]}
    labels = dict(zip(cons, ["S08", "S09", "S10", "S11", "S12", "S13", "S14", "S15"]))
    for lg_, cs in cons.items():
        b = blk(lg_)
        under_e = all(re.search(r"\n\s*if e( and fvgSig\.noTriggerMode)?\n(.*\n)*?\s*" + re.escape(x), "\n" + b) for x in cs)
        check(f"{labels[lg_]} {P08_CONST[lg_]} Short consume only inside `if e` (real entry)",
              under_e and all(any(l.strip() == x for l in b.split("\n")) for x in cs))
    mf15 = code_only(MAIN[MAIN.find('if fvg15EidShort != ""'):MAIN.find("// ---- 7.2 FVG Logic")])
    check("S08 FVG15 Short consume == old Main 7.1 (consumeFvg15(fvg15Ord, -1) then noTriggerMode -> fvg15Eng.shortArmed := false)",
          "sg.consumeFvg15(fvg15Ord, -1)" in mf15 and "if fvg15Base.noTriggerMode" in mf15 and "fvg15Eng.shortArmed := false" in mf15
          and "if fvg15Base.noTriggerMode" in blk("LOGIC_FVG15"))
    check("S09 FVG Short armed reset == old Main 7.2", 'if fvgSig.noTriggerMode and fvgEidShort != ""' in code_only(MAIN)
          and "if e and fvgSig.noTriggerMode" in blk("LOGIC_FVG"))
    check("S08-S15 no consume / armed write outside the dispatch; no Long-side consume / armed write",
          sum(sc.count(x) for x in ("sg.consumeFvg15(", "sg.consumeFvgAbs(", "sg.consumeZoneEvt(", "longArmed :=", "shortArmed :=")) ==
          sum(disp.count(x) for x in ("sg.consumeFvg15(", "sg.consumeFvgAbs(", "sg.consumeZoneEvt(", "longArmed :=", "shortArmed :=")) == 9
          and "longArmed :=" not in sc and "consumeFvg15(fvg15Ord, 1)" not in sc)
    # ---- shared parts identical to P11 ----
    lc = code_only(LG)
    def sect(src, a, b):
        return code_only(src[src.find(a):src.find(b)])
    check("S16/S17 Signal Engine section (inputs-driven config / feed / calls / Zone snapshot both sides / Min Strength) identical to P11",
          sect(SH, "// 07. SIGNAL ENGINE", "// 08. DISPATCH") == sect(LG, "// 07. SIGNAL ENGINE", "// 08. DISPATCH")
          and "if zsZ.strength >= zoneMinStrength and (zsZ.state == ST_SUPPORT or zsZ.state == ST_RESIST)" in sc)
    SI = parse_inputs(SH)
    check("S17 all inputs identical to P11 (Zone Signal Min Strength default Strong, alerts Provisional OFF / Confirmed ON)",
          SI == parse_inputs(LG) and SI["zoneSignalMinStrStr"]["default"] == '"Strong"'
          and SI["useProvisionalAlert"]["default"] == "false" and SI["useConfirmedAlert"]["default"] == "true")
    check("S17b Zone block (Practical inputs / ZoneCfg / feed / zn.update) identical to P11",
          sect(SH, "// 01-2. ZONE ENGINE INPUTS", "// 07. SIGNAL ENGINE").replace("f_entryAlertMsgShort", "X").replace('" SHORT】"', '"D"')
          .replace("strategy.short", "S") ==
          sect(LG, "// 01-2. ZONE ENGINE INPUTS", "// 07. SIGNAL ENGINE").replace("f_entryAlertMsgLong", "X").replace('" LONG】"', '"D"')
          .replace("strategy.long", "S")
          .replace("//  LONG 専用", "//  SHORT 専用"))
    ro = code_only(func_block(SH, "f_recordZoneOrigin"))
    check("S18 originTrackId = Short event zoneId (f_recordZoneOrigin identical to P11, before consume, 4 zone blocks only)",
          ro == code_only(func_block(LG, "f_recordZoneOrigin")) != "" and sc.count("f_recordZoneOrigin(activePos") == 4
          and all(blk(lg_).find("f_recordZoneOrigin(activePos, zoneEvtEng." + x + ")") >= 0 and
                  blk(lg_).find("f_recordZoneOrigin") < blk(lg_).find("sg.consumeZoneEvt") for lg_, x in
                  (("LOGIC_ZONE_RB", "sigRebound"), ("LOGIC_ZONE_FK", "sigFake"), ("LOGIC_ZONE_RT", "sigRetest"), ("LOGIC_ZONE_BK", "sigBreak"))))
    check("S19 Touch Count lookup only at zone entry (1 zoneTouchCount site inside f_recordZoneOrigin)",
          sc.count("zn.zoneTouchCount(") == 1 and "zn.zoneTouchCount(zoneEng, i)" in ro)
    check("S20 FVG-family entries keep originTrackId / entryTouchCount = na",
          "ap.originTrackId   := na" in code_only(func_block(SH, "f_tryEntry")) and
          all("f_recordZoneOrigin" not in blk(lg_) for lg_ in ("LOGIC_FVG15", "LOGIC_FVG", "LOGIC_FVG_ABS15", "LOGIC_FVG_ABS5")))
    # ---- trade engine / BE / alert parity ----
    check("S21 Trade Engine (Section 05/06) == P10 with only the dir < 0 specialisation",
          short_spec_p10(code_only(AH[AH.find("// 05. TRADE PLAN / RISK / QTY"):AH.find("// 07. PROBE CANDIDATES")])) ==
          sect(SH, "// 05. TRADE PLAN / RISK / QTY", "// 07. SIGNAL ENGINE"))
    for fn in ("f_tryEntry", "f_provEval", "f_insideAnyZone", "f_qty", "f_tpDepthFor", "f_breakEvenTriggerFor", "f_provSlot", "f_entryTag"):
        check(f"S21 {fn} == P10 (Short specialisation only)",
              code_only(func_block(SH, fn)) == short_spec_p10(code_only(func_block(AH, fn))) != "")
    check("S22 BE section identical to P10 / P11 (Short reach: low <= fill - trigger / confirmed close <= fill - trigger)",
          sect(SH, "// 09. BREAK EVEN", "// 10. PROVISIONAL ALERT") == sect(LG, "// 09. BREAK EVEN", "// 10. PROVISIONAL ALERT")
          == code_only(AH[AH.find("// 09. BREAK EVEN"):AH.find("// 10. PROVISIONAL ALERT")])
          and "(low <= ep - activePos.beTrigger)" in sc and "(barstate.isconfirmed and close <= ep - activePos.beTrigger)" in sc)
    check("S22 ZONEBREAK Short BE trigger = zoneBreakEvenTrigger (compat branch only for dir > 0)",
          "else if logicId == LOGIC_ZONE_BK and dir > 0 and breakLongRefCompat" in code_only(func_block(SH, "f_breakEvenTriggerFor"))
          and be_trigger_for("ZONEBREAK", -1) == BE_TRIG["zoneBreakEvenTrigger"])
    am = code_only(func_block(SH, "f_entryAlertMsgShort"))
    check("S23 alert helper == P10 f_entryAlertMsg dir < 0 branch; confirmed freq_all / provisional freq_once_per_bar",
          am == short_spec_p10(code_only(func_block(AH, "f_entryAlertMsg"))) and
          'alert(f_entryAlertMsgShort("確定", logicId, p, qty), alert.freq_all)' in sc and
          'alert(f_entryAlertMsgShort("仮", winLogic, win.plan, win.qty), alert.freq_once_per_bar)' in sc and sc.count("alert(") == 2)
    p10p = short_spec_p10(code_only(AH[AH.find("varip int gProvLastBar"):AH.find("// ---- Flat 遷移検知用")])).split("\n")
    s12p = code_only(SH[SH.find("varip int gProvLastBar"):SH.find("// ---- Flat 遷移検知用")]).split("\n")
    p10_ = [l for l in p10p if not re.search(r"pfire|f_provDirMode|dm != |cnd|int    li |int    d   |for k = 0 to 15|winDir   := d|f_provOffset|ProvEval ev", l)]
    s12_ = [l for l in s12p if not re.search(r"for li = 0 to 7|winDir   := -1|ProvEval ev", l)]
    check("S23 provisional winner / provSent (16 slots) / per-bar guard identical to P10 (only candidate source + Short)",
          p10_ == s12_ and "varip array<bool> gProvSent = array.new_bool(16, false)" in sc)
    # ---- prohibited ----
    bad = [t for t in ("tpManagementMode", "Dynamic", "gTradeTP", "gTradeSL", "gTradeBE", "f_isOpenEntry", "map.new", "map<",
                       "label.new", "box.new", "table.new", "line.new", "plot(", "plotshape", "bgcolor(", "strategy.close(",
                       "f_openCount", "ZONEBOS", "ZONESR", "DXY") if t in scs]
    check("S24-S27 no Dynamic TP / trade map / drawing / plots / excluded logics", not bad, str(bad))
    check("S26 no opentrades / closedtrades loop or per-trade accessor",
          not re.search(r"for .*(opentrades|closedtrades)", sc) and not re.search(r"strategy\.(opentrades|closedtrades)\.\w+", sc))
    check("P12 request audit == P11 (same call sites, same guards)",
          re.findall(r"request\.(?:security_lower_tf|security)\(.*", sc) == re.findall(r"request\.(?:security_lower_tf|security)\(.*", lc))
    check("P12 zn.update 1 / updateZoneEvents 1 / engine instances == P11",
          all(sc.count(x) == lc.count(x) for x in ("zn.update(", "sg.updateZoneEvents(", "sg.newFvgEngine()", "sg.newFvg15Engine()",
                                                    "sg.newFvgAbsEngine()", "sg.newZoneEvtEngine()", "sg.updateFvg(")))


def fixture_p12_behaviour():
    c = TCfg()
    res = Z(4060, 4065, ST_RES_, strength=2, tid=21)      # Short SL zone (strength 2: SL only)
    sup_far = Z(3990, 4000, ST_SUP_, tid=22)              # Short TP zone
    live = [res, sup_far]
    new = lambda: dict(entryId="", logicId="", dir=0, entryPrice=None, sl=None, tp=None, qty=None,
                       originTrackId=None, entryTouchCount=None)
    br, ap = Broker(), new()
    ent, ds = dispatch({lg: ("Short", 4050.0) for lg in P08_ORDER}, live, c, br, ap)
    ex = [o for o in br.orders if o[0] == "exit"]
    check("S-D1 all 8 Short candidates -> FVG15_S only; SL = top + buffer (4070), structural TP below",
          ent and [o[1] for o in br.orders if o[0] == "entry"] == ["FVG15_S"] and ex[0][3] == 4070.0 and ex[0][4] < 4050.0, str(ex))
    br, ap = Broker(), new()
    ent, ds = dispatch({"FVG15": ("Short", 4062.0), "FVG": ("Short", 4050.0)}, live, c, br, ap)
    check("S-D2 FVG15 Short inside a zone -> FAIL (not consumed), FVG Short enters", [o[1] for o in br.orders if o[0] == "entry"] == ["FVG_S"])
    e, c_, ap2 = p11_dispatch({lg: (True, 4050.0) for lg in P08_ORDER}, {lg: lg != "FVG15" for lg in P08_ORDER}, Broker(),
                              dict(logicId="", dir=0, entryPrice=None, originTrackId=None, entryTouchCount=None))
    check("S08-S15 mirror: consume only the real entry (FVG; FVG15 Plan FAIL not consumed)", e == "FVG" and c_ == ["FVG"])
    # BE Short: fill 3999, trigger zone 20 -> low 3979 reaches
    bars = [(4000.0, 4001.0, 3999.0, 4000.0), (3999.0, 3999.5, 3979.0, 3990.0), (3990.0, 3991.0, 3989.0, 3990.0)]
    tr, lg_ = run_be_sim(bars, {0: ("ZONEBREAK", -1, 30.0, 3.0)})
    check("S22 BE Short ZONEBREAK: trigger 20 (not breakLong 10), fill - 20 reached -> stop = fill 3999",
          lg_[1]["ap"]["beTrigger"] == 20.0 and lg_[1]["beAct"] and lg_[1]["exit"] == ("ZBK_S", 3999.0, 4000.0 - 90.0, "BE", "TP"))
    bars2 = [(4000.0, 4001.0, 3999.0, 4000.0), (3999.0, 3999.5, 3979.01, 3990.0)]
    tr, lg_ = run_be_sim(bars2, {0: ("ZONEBREAK", -1, 30.0, 3.0)})
    check("S22b BE Short 0.01 short of the threshold -> no BE", not lg_[1]["beAct"])
    st = AlertState()
    f, w, _ = prov_tick(st, 1, {lg: ("Short", 4050.0) for lg in P08_ORDER}, live, c, Broker())
    check("S23 provisional Short: top-priority Entry-ready Short (FVG15, -1) only; slot = FVG15_S", f and w == ("FVG15", -1) and st.sent[prov_slot("FVG15", -1)])


# ============================================================================
# P13A : zero-risk performance cleanup (LONG / SHORT production files)
# ============================================================================
P13A_DEAD = ["efvgDReason", "efvgDRem", "efvgDBos", "efvgHReason", "efvgHRem", "efvgHBos", "efvgOReason", "efvgORem",
             "efvgOBos", "efvg5Reason", "efvg5Rem", "efvg1Reason", "efvg1Rem", "efvg1Bos", "efvgMRawReason", "efvgMRawRem"]


def p13a_transform(src):
    """The complete, documented P13A transformation (applied to the e3680f5 LONG / SHORT sources)."""
    t = src

    def R(a, b, n=1):
        nonlocal t
        assert t.count(a) == n, (a[:70], t.count(a))
        t = t.replace(a, b)
    # ---- A1 : input-only request configs -> var (initializer evaluated once, never mutated) ----
    for ty, nm in (("FvgTrigCfg", "fvgTrigCfg"), ("FvgEnvCfg", "fvgEnvCfg"), ("FvgAccCfg", "fvgAccCfg")):
        R(f"\nsg.{ty} {nm} = sg.{ty}.new(", f"\n//  ★ P13A: 全 field が input のみ・以後書き換えなし → var (初期化子は初回バーの1回だけ評価)。\nvar sg.{ty} {nm} = sg.{ty}.new(")
    # ---- A2 : empty placeholders -> one shared read-only empty array ----
    R("array<bool> fvgBullTrig = array.new_bool()\narray<bool> fvgBearTrig = array.new_bool()\n",
      "//  ★ P13A: 毎バーの空配列確保をやめ、共有の空配列 (var・読み取り専用) を placeholder にする。\n"
      "//    SignalEngine はこれらの配列を読むだけ (push / set / clear なし)。request 時は戻り値へ差し替える。\n"
      "var array<bool> gEmptyBool = array.new_bool()\n"
      "array<bool> fvgBullTrig = gEmptyBool\narray<bool> fvgBearTrig = gEmptyBool\n")
    R("array<bool> absBos1m  = array.new_bool()\narray<bool> absBos1mS = array.new_bool()\n",
      "array<bool> absBos1m  = gEmptyBool\narray<bool> absBos1mS = gEmptyBool\n")
    # zone TF arrays: placeholder (lower TF = request result) / scratch push buffer (same or higher TF)
    R("array<float> zbTfC    = array.new_float()\narray<float> zbTfH    = array.new_float()\narray<float> zbTfL    = array.new_float()\n"
      "array<bool>  zbBullArr = array.new_bool()\narray<bool>  zbBearArr = array.new_bool()\n",
      "//  ★ P13A: 判定TF < チャート足 → request の戻り値へ差し替える placeholder。\n"
      "//    判定TF >= チャート足 → そのバーの1本を push する scratch。var バッファを毎バー clear して再利用する\n"
      "//    (毎バー新規の空配列と同値。SignalEngine は読むだけで参照を保持しない)。\n"
      "var array<float> zbBufC    = array.new_float()\nvar array<float> zbBufH    = array.new_float()\nvar array<float> zbBufL    = array.new_float()\n"
      "var array<bool>  zbBufBull = array.new_bool()\nvar array<bool>  zbBufBear = array.new_bool()\n"
      "array<float> zbTfC    = zbBufC\narray<float> zbTfH    = zbBufH\narray<float> zbTfL    = zbBufL\n"
      "array<bool>  zbBullArr = zbBufBull\narray<bool>  zbBearArr = zbBufBear\n")
    R("    else\n        [_zc2, _zh2, _zl2, _zbb, _zbs] = request.security(",
      "    else\n        array.clear(zbBufC)\n        array.clear(zbBufH)\n        array.clear(zbBufL)\n"
      "        array.clear(zbBufBull)\n        array.clear(zbBufBear)\n        [_zc2, _zh2, _zl2, _zbb, _zbs] = request.security(")
    # ---- A3 : provisional slots 16 -> 8 (direction file: one slot per logic) ----
    R("varip array<bool> gProvSent = array.new_bool(16, false)", "varip array<bool> gProvSent = array.new_bool(8, false)")
    R("f_provSlot(string logicId, int dir) =>\n    int li = logicId == LOGIC_FVG ? 0 : logicId == LOGIC_FVG15 ? 1 :\n"
      "         logicId == LOGIC_FVG_ABS5 ? 2 : logicId == LOGIC_FVG_ABS15 ? 3 :\n"
      "         logicId == LOGIC_ZONE_RB ? 4 : logicId == LOGIC_ZONE_FK ? 5 :\n"
      "         logicId == LOGIC_ZONE_RT ? 6 : logicId == LOGIC_ZONE_BK ? 7 : -1\n"
      "    li < 0 ? -1 : li * 2 + (dir > 0 ? 0 : 1)",
      "//  ★ P13A: 方向別ファイルなので slot は Logic ごとに1つ (8 slot)。旧 16 slot の\n"
      "//    「この方向の slot」と1対1 (li * 2 + 方向 → li)。\n"
      "f_provSlot(string logicId) =>\n    logicId == LOGIC_FVG ? 0 : logicId == LOGIC_FVG15 ? 1 :\n"
      "     logicId == LOGIC_FVG_ABS5 ? 2 : logicId == LOGIC_FVG_ABS15 ? 3 :\n"
      "     logicId == LOGIC_ZONE_RB ? 4 : logicId == LOGIC_ZONE_FK ? 5 :\n"
      "     logicId == LOGIC_ZONE_RT ? 6 : logicId == LOGIC_ZONE_BK ? 7 : -1")
    R("int pslot = f_provSlot(logicId, dir)", "int pslot = f_provSlot(logicId)")
    R("int slot = f_provSlot(winLogic, winDir)", "int slot = f_provSlot(winLogic)")
    # ---- A4 : dead scalars ----
    for v in P13A_DEAD:
        R(f"int {v} = 0\n", "")
        t2 = re.sub(r"^    " + v + r" := \w+\n", "", t, count=1, flags=re.M)
        assert t2 != t, v
        t = t2
    R("bool   provFiredNow  = false\nint    provWinPrio   = na\n", "")
    R("        provWinPrio := f_logicPriority(winLogic)\n", "")
    R("            provFiredNow := true\n", "")
    R("float beLevel            = na\n", "")
    R("    beLevel := activePos.dir > 0 ? ep + activePos.beTrigger : ep - activePos.beTrigger\n", "")
    return t


def _git_show(rev, path):
    import subprocess
    return subprocess.run(["git", "-C", ROOT, "show", f"{rev}:{path}"], capture_output=True, text=True).stdout


def fixture_p13a():
    #  P13A validated stage = acd12ac (Reference). Current files are tied to it by the P15 exact-transform fixture.
    for name, cur in (("LONG", _git_show("acd12ac", "PracticalZoneStrategy_LONG.pine")),
                      ("SHORT", _git_show("acd12ac", "PracticalZoneStrategy_SHORT.pine"))):
        prev = _git_show("e3680f5", f"PracticalZoneStrategy_{name}.pine")
        check(f"P13A-{name} A6 file == p13a_transform(e3680f5) exactly (only the documented A1-A4 edits)",
              bool(prev) and p13a_transform(prev) == cur)
        pc, cc = code_only(prev), code_only(cur)
        # A1
        for nm in ("fvgTrigCfg", "fvgEnvCfg", "fvgAccCfg"):
            blk = cc[cc.find(f" {nm} = sg."):]
            blk = blk[blk.find(".new(") + 5:blk.find(")")]
            args = re.findall(r"(\w+) = (\w+)", blk)
            ins = parse_inputs(cur)
            check(f"P13A-{name} A1 {nm}: var, every field = an input of the same name, never re-assigned",
                  f"var sg." in cc and re.search(r"^var sg\.\w+ " + nm + r" = ", cc, re.M) is not None
                  and args and all(a == b and b in ins for a, b in args) and not re.search(nm + r"\.\w+\s*:=", cc)
                  and not re.search(r"\b" + nm + r"\s*:=", cc))
        # A2
        check(f"P13A-{name} A2 per-bar array.new removed: 9 -> 0 (shared read-only empty + 5 var zone buffers cleared per bar)",
              len(re.findall(r"^array<\w+>\s+\w+\s*=\s*array\.new", pc, re.M)) == 9 and
              len(re.findall(r"^array<\w+>\s+\w+\s*=\s*array\.new", cc, re.M)) == 0 and
              cc.count("var array<bool> gEmptyBool = array.new_bool()") == 1 and len(re.findall(r"^var array<\w+>\s+zbBuf\w+", cc, re.M)) == 5)
        check(f"P13A-{name} A2 request-returned arrays untouched (all := from request tuples kept)",
              all(x in cc for x in ("fvgBullTrig := _bull", "fvgBearTrig := _bear", "absBos1m  := _a1b", "absBos1mS := _a1s",
                                    "zbTfC     := _zc", "zbBullArr := _lb", "zbBearArr := _ls")))
        check(f"P13A-{name} A2 shared empty array is never written (no push/set/clear on gEmptyBool)",
              not re.search(r"array\.\w+\(gEmptyBool|gEmptyBool\.\w+\(", cc))
        els = cc[cc.find("    else\n        array.clear(zbBufC)"):cc.find("int zoneJudgeTfSec")]
        check(f"P13A-{name} A2 zone buffers cleared before the conditional push (same as a fresh empty array each bar)",
              els.find("array.clear(zbBufBear)") < els.find("array.push(zbTfC") and els.count("array.clear(") == 5)
        # A3
        check(f"P13A-{name} A3 provisional slots 8, varip, re-arm only in the entry branch, set-true only in Section 10",
              "varip array<bool> gProvSent = array.new_bool(8, false)" in cc and cc.count("array.set(gProvSent") == 2
              and "array.set(gProvSent, pslot, false)" in code_only(func_block(cur, "f_tryEntry"))
              and "array.set(gProvSent, slot, true)" in cc[cc.find("varip int gProvLastBar"):])
        dsign = -1 if name == "SHORT" else 1
        old_slot = lambda li: li * 2 + (0 if dsign > 0 else 1)
        check(f"P13A-{name} A3 slot map is a bijection onto the old {name} slots (li -> li*2+{0 if dsign > 0 else 1})",
              sorted(old_slot(li) for li in range(8)) == sorted(set(old_slot(li) for li in range(8))) and len({old_slot(li) for li in range(8)}) == 8)
        # A4 / A5
        check(f"P13A-{name} A4 dead scalars removed (16 debug efvg* + provFiredNow / provWinPrio / beLevel); used ones kept",
              all(not re.search(r"\b" + v + r"\b", cc) for v in P13A_DEAD + ["provFiredNow", "provWinPrio", "beLevel"])
              and all(re.search(r"\b" + v + r"\b", cc) for v in ("efvg5Bos", "efvgMRawBos", "fvg15RawReason", "fvg15RawRem", "fvg15RawBos")))
        check(f"P13A-{name} A5 request call sites identical to e3680f5 (security 26 / lower_tf 5 sites; default 19 + 2)",
              re.findall(r"request\.(?:security_lower_tf|security)\(.*", pc) == re.findall(r"request\.(?:security_lower_tf|security)\(.*", cc))
        check(f"P13A-{name} shared Signal state untouched (Signal calls / snapshot / consume / dispatch identical)",
              code_only(prev[prev.find("// ---- 7.3 Signal calls"):prev.find("// 09. BREAK EVEN")]) ==
              code_only(cur[cur.find("// ---- 7.3 Signal calls"):cur.find("// 09. BREAK EVEN")]))
    # A6 behavioural: 8-slot dedupe sequence == 16-slot (direction slots) on random event streams
    import random
    rnd = random.Random(1313)
    mism = 0
    for _ in range(500):
        d = rnd.choice((1, -1))
        s16, s8 = [False] * 16, [False] * 8
        for _ in range(60):
            li = rnd.randrange(8)
            if rnd.random() < 0.6:          # provisional winner li
                a = not s16[li * 2 + (0 if d > 0 else 1)]
                b = not s8[li]
                if a:
                    s16[li * 2 + (0 if d > 0 else 1)] = True
                if b:
                    s8[li] = True
                mism += a != b
            else:                            # real entry of logic li -> re-arm
                s16[li * 2 + (0 if d > 0 else 1)] = False
                s8[li] = False
            mism += [s16[i * 2 + (0 if d > 0 else 1)] for i in range(8)] != s8
    check("P13A A6 provisional dedupe: 8-slot series == 16-slot direction slots (500 random streams, send / re-arm)", mism == 0)


# ============================================================================
# P14 : final production audit (current LONG / SHORT files = Reference)
# ============================================================================
#  TradingView external gate (recorded, NOT computed or verified by Python):
#    XAUUSD 5M / Last 365 days / Deep Backtest, after P13A (acd12ac):
#      LONG  = 46 trades,  SHORT = 59 trades   (confirmed by the user in TradingView)
TV_REFERENCE = {"LONG": 46, "SHORT": 59, "head": "acd12ac", "evidence": "USER_TRADINGVIEW_EXTERNAL_GATE"}


def fixture_p14_final_audit(files=None, req_sites=31, label="P14"):
    if files is None:   # P14 audited the Reference stage acd12ac
        files = (("LONG", _git_show("acd12ac", "PracticalZoneStrategy_LONG.pine"), 1),
                 ("SHORT", _git_show("acd12ac", "PracticalZoneStrategy_SHORT.pine"), -1))
    for name, cur, d in files:
        c = code_only(cur)
        cs = "\n".join(_strip_str(l) for l in c.split("\n"))
        own, other = ("strategy.long", "strategy.short") if d > 0 else ("strategy.short", "strategy.long")
        W, O = ("LONG", "SHORT") if d > 0 else ("SHORT", "LONG")
        tag = f"{label}-{name}"
        check(f"{tag} 01/02 direction: strategy.entry = {own} only (1 site), {other} = 0, no '{O}' literal in code",
              re.findall(r"strategy\.entry\(([^)]*)\)", c) == [f"eid, {own}, qty = qty"] and other not in cur and O not in c
              and f'"【" + kind + " {W}】" +' in c)
        disp = cur[cur.find("// 08. DISPATCH"):cur.find("// 09. BREAK EVEN")]
        calls = re.findall(r"e := f_tryEntry\(activePos, ds, (\w+), ([^,]+), (-?\d+), ([^,]+), globalPositionBlocked, enteredThisBar\)", code_only(disp))
        check(f"{tag} 03/04 8 logics in priority FVG15 > FVG > ABS15 > ABS5 > RB > FK > RT > BK, all dir {d}",
              [P08_CONST[x[0]] for x in calls] == P08_ORDER and all(int(x[2]) == d for x in calls))
        sigs = ["fvg15Sig.%sSignal", "fvgSig.%sSignal", "absSig.%s15", "absSig.%s5", "zlSig.rebound%s", "zlSig.fake%s",
                "zlSig.retest%s", "zlSig.break%s"]
        lw = "long" if d > 0 else "short"
        cw = "Long" if d > 0 else "Short"
        exp_sig = [x % (lw if x.endswith("Signal") or x.startswith("absSig") else cw) for x in sigs]
        check(f"{tag} 03 confirmed candidates = SignalEnginePractical {cw} outputs", [x[1] for x in calls] == exp_sig, str([x[1] for x in calls]))
        check(f"{tag} 05 Global 1-position gate (scalar) + enteredThisBar + same-bar chaining",
              "bool globalPositionBlocked = strategy.position_size != 0 or strategy.opentrades > 0" in c
              and code_only(disp).count("enteredThisBar := enteredThisBar or e") == 8)
        te = code_only(func_block(cur, "f_tryEntry"))
        order = [te.find(x) for x in ("if cand and dir != 0 and isGold and not positionBlocked and not enteredThisBar",
                                      "f_insideAnyZone(entryPrice)", "zn.buildPlanWithTpDepth(", 'if tpMode == "STRUCTURAL_ONLY"',
                                      "if p.valid", "float qty = f_qty(p.risk)", "if qty >= qtyMin and qty > 0",
                                      "strategy.entry(", "strategy.exit(")]
        check(f"{tag} 06-10 gate order: Gold/position/same-bar -> Inside Any Zone -> Structural SL/TP + Fallback (buildPlanWithTpDepth) "
              f"-> TP Mode -> valid -> Risk/Qty -> qtyMin -> entry -> exit (SL/TP fixed)",
              -1 not in order and order == sorted(order) and 'stop = p.sl, limit = p.tp' in te)
        ins = code_only(func_block(cur, "f_insideAnyZone"))
        check(f"{tag} 06 Inside Any Zone: strength >= activeNoTradeMinStrength, bottom <= entry <= top, state ignored",
              "z.strength >= zoneCfg.activeNoTradeMinStrength and entryPrice >= z.bottom and entryPrice <= z.top" in ins and "state" not in ins)
        be = code_only(cur[cur.find("// 09. BREAK EVEN"):cur.find("// 10. PROVISIONAL ALERT")])
        check(f"{tag} 11 BE: fill price (position_avg_price), reach high/low or confirmed close, stop = fill, limit = entry TP, irreversible",
              "strategy.position_avg_price" in c and "if not activePos.beOn" in be and "activePos.beOn           := true" in be
              and 'stop = ep, limit = activePos.tp,' in be and 'comment_loss = "BE", comment_profit = "TP"' in be)
        I_ = parse_inputs(cur)
        check(f"{tag} 12/13/16 defaults: Provisional OFF / Confirmed ON / Zone Signal Min Strength Strong / Fake OFF / Retest OFF",
              I_["useProvisionalAlert"]["default"] == "false" and I_["useConfirmedAlert"]["default"] == "true"
              and I_["zoneSignalMinStrStr"]["default"] == '"Strong"' and I_["useZoneFake"]["default"] == "false"
              and I_["useZoneRetest"]["default"] == "false")
        check(f"{tag} 12/13 alerts: exactly 2 alert() (confirmed in entry branch freq_all / provisional freq_once_per_bar), 0 alertcondition",
              c.count("alert(") == 2 and "alertcondition" not in c and te.count("alert(") == 1 and "alert.freq_all" in te
              and c.count("alert.freq_once_per_bar") == 1)
        check(f"{tag} 14/15 Dynamic TP = 0; BE / TP / SL / Exit alerts = 0 (BE section has no alert; one strategy.exit re-issue only at BE)",
              "Dynamic" not in cs and "tpManagementMode" not in c and "alert(" not in be and c.count("strategy.exit(") == 2)
        snap = code_only(cur[cur.find("int zoneMinStrength = zn.strengthIdx(zoneSignalMinStrStr)"):cur.find("//  各Zone Logicの保有状況。")])
        check(f"{tag} 17 Zone snapshot: SUPPORT +1 and RESISTANCE -1, strength >= Min Strength, zoneId = trackId",
              "(zsZ.state == ST_SUPPORT or zsZ.state == ST_RESIST)" in snap and "zsZ.state == ST_SUPPORT ? 1 : -1" in snap
              and "array.push(zSnapId,    zsZ.trackId)" in snap)
        ro = code_only(func_block(cur, "f_recordZoneOrigin"))
        dblocks = [code_only(b) for b in re.split(r"\n    // \d ", disp)]
        zone_blk = [b for b in dblocks if re.search(r"LOGIC_ZONE_(RB|FK|RT|BK),", b)]
        fvg_blk = [b for b in dblocks if re.search(r"LOGIC_FVG(15|_ABS15|_ABS5)?,", b)]
        check(f"{tag} 18/19 originTrackId = event zoneId and entryTouchCount = live Touch Count, only in the 4 zone entry branches (before consume)",
              "origin := array.get(zoneEvtEng.evts, evIdx).zoneId" in ro and "touch := zn.zoneTouchCount(zoneEng, i)" in ro
              and len(zone_blk) == 4 and all(b.find("f_recordZoneOrigin") < b.find("sg.consumeZoneEvt") and "if e" in b for b in zone_blk)
              and c.count("f_recordZoneOrigin(activePos") == 4 and c.count("zn.zoneTouchCount(") == 1)
        check(f"{tag} 19 Touch Count is not an entry condition (not read by f_tryEntry / dispatch gates / provisional)",
              "entryTouchCount" not in te.replace("ap.entryTouchCount := na", "")
              and "entryTouchCount" not in code_only(cur[cur.find("// 10. PROVISIONAL ALERT"):]))
        check(f"{tag} 20 FVG-family entries: originTrackId / entryTouchCount = na (no origin call)",
              len(fvg_blk) == 4 and all("f_recordZoneOrigin" not in b for b in fvg_blk)
              and "ap.originTrackId   := na" in te and "ap.entryTouchCount := na" in te)
        check(f"{tag} 21 probe / harness code = 0",
              not re.search(r"G_PROBE|probeEvery|\bc[1-8](On|Dr|Of)\b|f_provOn|f_provDirMode|f_provOffset|Harness", c))
        check(f"{tag} 22 label / table / box / line / plot drawing = 0",
              not re.search(r"label\.new|table\.new|box\.new|line\.new|\bplot\(|plotshape|bgcolor\(|fill\(", cs))
        check(f"{tag} 23/24 no map trade management, no opentrades / closedtrades loop or per-trade accessor",
              "map." not in cs and "map<" not in cs and not re.search(r"for .*(opentrades|closedtrades)", c)
              and not re.search(r"strategy\.(opentrades|closedtrades)\.\w+", c))
        check(f"{tag} 25 imports = ZoneEnginePractical/3 + SignalEnginePractical/1",
              re.findall(r"^import .*$", c, re.M) == ["import sekine3310/ZoneEnginePractical/3 as zn", "import sekine3310/SignalEnginePractical/1 as sg"])
        check(f"{tag} request call sites {req_sites}, zn.update 1, updateZoneEvents 1",
              len(re.findall(r"request\.(?:security_lower_tf|security)\(", c)) == req_sites and c.count("zn.update(") == 1
              and c.count("sg.updateZoneEvents(") == 1)
        check(f"{tag} allocation state: per-bar array.new 0, provisional slots 8 (varip)",
              len(re.findall(r"^array<\w+>\s+\w+\s*=\s*array\.new", c, re.M)) == 0
              and "varip array<bool> gProvSent = array.new_bool(8, false)" in c)
    check("P14 TradingView reference recorded as external gate (LONG 46 / SHORT 59 @ acd12ac; not computed by Python)",
          TV_REFERENCE == {"LONG": 46, "SHORT": 59, "head": "acd12ac", "evidence": "USER_TRADINGVIEW_EXTERNAL_GATE"})


# ============================================================================
# P15 : one-shot performance optimization (Main side only; Library unchanged)
# ============================================================================
P15_REF = "acd12ac"
SEP_SRC = open(os.path.join(ROOT, "SignalEnginePractical.pine"), encoding="utf-8").read()


def p15_transform(src):
    """Complete documented P15 transformation of the acd12ac (= P13A) LONG / SHORT sources.
    Every optimization is guarded by an input switch (default ON); switch OFF = the exact Reference code path."""
    t = src

    def R(a, b, n=1):
        nonlocal t
        assert t.count(a) == n, (a[:80], t.count(a))
        t = t.replace(a, b)

    # ---- switches (inputs) ----
    R("// ============================================================================\n// 01-2. ZONE ENGINE INPUTS",
      "// ============================================================================\n"
      "// 00. P15 PERFORMANCE SWITCHES (既定 ON。OFF = Reference と同一の取得経路)\n"
      "// ----------------------------------------------------------------------------\n"
      "//  どれも「同じ値を安く取る」ための切り替えで、Signal / Entry / Exit の判定式は変えない。\n"
      "//  TradingView で Reference (acd12ac) と差が出た場合に、1つずつ OFF にして原因を切り分ける。\n"
      "// ============================================================================\n"
      "var string G_P15 = \"99 · P15 Performance (検証用・既定ON)\"\n"
      "p15MergeLtf1m   = input.bool(true, \"O1 1M lower_tf 統合 (ABS BOS + Zone 精密TF)\", group = G_P15)\n"
      "p15LocalChartTf = input.bool(true, \"O2 チャート足と同TFの request をローカル計算\", group = G_P15)\n"
      "p15SkipOffEnv   = input.bool(true, \"O3 未使用の環境TF request を発行しない\", group = G_P15)\n"
      "p15PackSameTf   = input.bool(true, \"O4 同TF・同lookahead request の統合 (15M / Zone 60M)\", group = G_P15)\n\n"
      "// ============================================================================\n// 01-2. ZONE ENGINE INPUTS")

    # ---- O2 : Zone swing TF #1 at chart TF -> local pivotPack ----
    R("    [_h1, _h1t, _l1, _l1t] = request.security(syminfo.tickerid, hzTf1, zn.pivotPack(pivLen1), lookahead = barmerge.lookahead_off)\n",
      "    //  ★ P15 O2: TF #1 がチャート足と同じなら、同じ関数をチャート足でそのまま評価する\n"
      "    //    (同一TF・lookahead_off の request.security はチャート足の系列そのもの)。\n"
      "    float _h1  = na\n    int   _h1t = na\n    float _l1  = na\n    int   _l1t = na\n"
      "    if p15LocalChartTf and timeframe.in_seconds(hzTf1) == timeframe.in_seconds()\n"
      "        [_x1, _x1t, _y1, _y1t] = zn.pivotPack(pivLen1)\n"
      "        _h1  := _x1\n        _h1t := _x1t\n        _l1  := _y1\n        _l1t := _y1t\n"
      "    else\n"
      "        [_x1, _x1t, _y1, _y1t] = request.security(syminfo.tickerid, hzTf1, zn.pivotPack(pivLen1), lookahead = barmerge.lookahead_off)\n"
      "        _h1  := _x1\n        _h1t := _x1t\n        _l1  := _y1\n        _l1t := _y1t\n")
    # ---- O4 : Zone swing TF #3 + Accum TF #1 (same TF, both lookahead_off) -> one request ----
    R("    [_h3, _h3t, _l3, _l3t] = request.security(syminfo.tickerid, hzTf3, zn.pivotPack(pivLen3), lookahead = barmerge.lookahead_off)\n",
      "    //  ★ P15 O4: Swing #3 と Accum #1 が同TFなら Accum 側で1本にまとめて取得する (下の Accum block)。\n"
      "    float _h3  = na\n    int   _h3t = na\n    float _l3  = na\n    int   _l3t = na\n"
      "    if not p15PackHzAcc\n"
      "        [_x3, _x3t, _y3, _y3t] = request.security(syminfo.tickerid, hzTf3, zn.pivotPack(pivLen3), lookahead = barmerge.lookahead_off)\n"
      "        _h3  := _x3\n        _h3t := _x3t\n        _l3  := _y3\n        _l3t := _y3t\n")
    R("float ph3 = na\n", "//  P15 O4 : Swing #3 (hzTf3) と Accum #1 (accTf1) が同TF・両方ON のとき1本の request にまとめる。\n"
      "bool p15PackHzAcc = p15PackSameTf and useHzSource and useAccSource and hzTf3 == accTf1\nfloat ph3 = na\n")
    R("if useAccSource\n    [_a1h, _a1l, _a1i] = request.security(syminfo.tickerid, accTf1,\n"
      "         zn.accumPack(usePortedAccum, accumRangeLen, accumBaseLen, accumAtrLen, accumMinUpperCloses, accumMinLowerCloses,\n"
      "         accumMaxSameColorRun, accumAtrMult, accumBarRatioMax, accumDriftMax, accLen1, accMult), lookahead = barmerge.lookahead_off)\n",
      "//  ★ P15 O4: Swing #3 + Accum #1 を同じTFコンテキストで1回に評価する (各関数・引数は元と同一)。\n"
      "f_p15HzAccPack() =>\n"
      "    [_ph, _pt, _pl, _lt] = zn.pivotPack(pivLen3)\n"
      "    [_ah, _al, _ai] = zn.accumPack(usePortedAccum, accumRangeLen, accumBaseLen, accumAtrLen, accumMinUpperCloses, accumMinLowerCloses,\n"
      "         accumMaxSameColorRun, accumAtrMult, accumBarRatioMax, accumDriftMax, accLen1, accMult)\n"
      "    [_ph, _pt, _pl, _lt, _ah, _al, _ai]\n\n"
      "if useAccSource\n"
      "    float _a1h = na\n    float _a1l = na\n    int   _a1i = na\n"
      "    if p15PackHzAcc\n"
      "        [_q3h, _q3ht, _q3l, _q3lt, _qa1h, _qa1l, _qa1i] = request.security(syminfo.tickerid, accTf1, f_p15HzAccPack(), lookahead = barmerge.lookahead_off)\n"
      "        ph3  := _q3h\n        ph3T := _q3ht\n        pl3  := _q3l\n        pl3T := _q3lt\n"
      "        _a1h := _qa1h\n        _a1l := _qa1l\n        _a1i := _qa1i\n"
      "    else\n"
      "        [_qa1h, _qa1l, _qa1i] = request.security(syminfo.tickerid, accTf1,\n"
      "             zn.accumPack(usePortedAccum, accumRangeLen, accumBaseLen, accumAtrLen, accumMinUpperCloses, accumMinLowerCloses,\n"
      "             accumMaxSameColorRun, accumAtrMult, accumBarRatioMax, accumDriftMax, accLen1, accMult), lookahead = barmerge.lookahead_off)\n"
      "        _a1h := _qa1h\n        _a1l := _qa1l\n        _a1i := _qa1i\n")
    #  hz block: when packed, ph3.. are assigned in the Accum block; keep them untouched in the Swing block
    R("    ph3 := _h3\n    ph3T := _h3t\n    pl3 := _l3\n    pl3T := _l3t\n",
      "    if not p15PackHzAcc\n        ph3 := _h3\n        ph3T := _h3t\n        pl3 := _l3\n        pl3T := _l3t\n")

    # ---- O3 / O4 / O2 : environment requests ----
    R("bool absAnyOn = useFvgAbs5Logic or useFvgAbs15Logic\n",
      "bool absAnyOn = useFvgAbs5Logic or useFvgAbs15Logic\n"
      "//  ★ P15 O3: 結果を読む可能性がある TF だけ request する (input 定数だけで決まる)。\n"
      "//    updateFvg は env を en = reqTrend != \"OFF\" のときだけ読む。Zone 4Logic は 4H / 1H / 15M のみ読む。\n"
      "bool needEnv4H  = not p15SkipOffEnv or (useEnvFilter and reqTrend4H  != \"OFF\") or useZoneAny\n"
      "bool needEnv1H  = not p15SkipOffEnv or (useEnvFilter and reqTrend1H  != \"OFF\") or useZoneAny\n"
      "bool needEnv15M = not p15SkipOffEnv or (useEnvFilter and reqTrend15M != \"OFF\") or useZoneAny\n"
      "bool needEnv5M  = not p15SkipOffEnv or (useEnvFilter and reqTrend5M  != \"OFF\")\n"
      "bool needEnv1M  = not p15SkipOffEnv or (useEnvFilter and reqTrend1M  != \"OFF\")\n"
      "//  ★ P15 O4: 15M・lookahead_on の4本 (env15M / FVG15 反発 / FVGABS15 / Accum15) を1本にまとめる。\n"
      "//    4本とも有効・同じTFのときだけ。各関数と引数は元の request と同一。\n"
      "bool p15Pack15 = p15PackSameTf and (useEnvFilter or useZoneAny) and needEnv15M and useFvg15Logic and useFvgAbs15Logic and\n"
      "     useAccumNoTrade and useAccumNT15M and tf15M == efvg15MTF and accumNT15Tf == efvg15MTF\n"
      "f_p15Pack15() =>\n"
      "    int _e = sg.envTrendConfirmed(fvgEnvCfg, len20, len50, len200, envAtrLen, slopeBars, convDivBars, crossBars, rangeBars, minScore15M)\n"
      "    [_b, _r, _rem, _bos, _t] = sg.efvgRebound15Pack(fvg15Hold, efvgMinThick, reboundDepthMax, reboundRecoverRatio, false, fvgBosLookback)\n"
      "    [_ab, _ae, _at] = sg.efvgAbsConfirmed(efvgHold15M, efvgMinThick, efvgAbsBodyMin, efvgAbsEdge, useAbsCandleColor, useAbsBodyFilter, useAbsEdgeFilter)\n"
      "    [_h, _l, _s] = sg.accumNT15Confirmed(fvgAccCfg, accumNTRangeLen, accumNTBaseLen, accumNTAtrLen)\n"
      "    [_e, _b, _r, _rem, _bos, _t, _ab, _ae, _at, _h, _l, _s]\n"
      "int   pk15Env = na\nint   pk15B   = 0\nint   pk15R   = 0\nint   pk15Rem = 0\nint   pk15Bos = 0\nint   pk15T   = na\n"
      "int   pk15Ab  = 0\nint   pk15Ae  = na\nint   pk15At  = na\nfloat pk15Hi  = na\nfloat pk15Lo  = na\nint   pk15St  = na\n"
      "if p15Pack15\n"
      "    [_qe, _qb, _qr, _qrem, _qbos, _qt, _qab, _qae, _qat, _qh, _ql, _qs] = request.security(syminfo.tickerid, efvg15MTF, f_p15Pack15(), lookahead = barmerge.lookahead_on)\n"
      "    pk15Env := _qe\n    pk15B   := _qb\n    pk15R   := _qr\n    pk15Rem := _qrem\n    pk15Bos := _qbos\n    pk15T   := _qt\n"
      "    pk15Ab  := _qab\n    pk15Ae  := _qae\n    pk15At  := _qat\n    pk15Hi  := _qh\n    pk15Lo  := _ql\n    pk15St  := _qs\n")
    R("    env4H  := request.security(syminfo.tickerid, tf4H,",
      "    if needEnv4H\n        env4H  := request.security(syminfo.tickerid, tf4H,")
    R("    env1H  := request.security(syminfo.tickerid, tf1H,",
      "    if needEnv1H\n        env1H  := request.security(syminfo.tickerid, tf1H,")
    R("    env15M := request.security(syminfo.tickerid, tf15M,",
      "    if p15Pack15\n        env15M := pk15Env\n    else if needEnv15M\n        env15M := request.security(syminfo.tickerid, tf15M,")
    R("    env5M  := request.security(syminfo.tickerid, tf5M,  sg.envTrend(fvgEnvCfg, len20, len50, len200, envAtrLen, slopeBars, convDivBars, crossBars, rangeBars, minScore5M),  lookahead = barmerge.lookahead_off)\n",
      "    if needEnv5M\n"
      "        if p15LocalChartTf and timeframe.in_seconds(tf5M) == timeframe.in_seconds()\n"
      "            env5M  := sg.envTrend(fvgEnvCfg, len20, len50, len200, envAtrLen, slopeBars, convDivBars, crossBars, rangeBars, minScore5M)\n"
      "        else\n"
      "            env5M  := request.security(syminfo.tickerid, tf5M,  sg.envTrend(fvgEnvCfg, len20, len50, len200, envAtrLen, slopeBars, convDivBars, crossBars, rangeBars, minScore5M),  lookahead = barmerge.lookahead_off)\n")
    R("    env1M  := request.security(syminfo.tickerid, tf1M,",
      "    if needEnv1M\n        env1M  := request.security(syminfo.tickerid, tf1M,")
    # ---- O2 : FVG env 5M at chart TF -> local ----
    R("if need5MState\n    [_b, _r, _rem, _bos] = request.security(syminfo.tickerid, efvg5MTF, sg.efvgReboundConfirmed(efvgHold5M, efvgMinThick, reboundDepthMax, reboundRecoverRatio, useFvgBosFilter, fvgBosLookback), lookahead = barmerge.lookahead_on)\n"
      "    efvg5Bias := _b\n    efvg5Bos := _bos\n",
      "if need5MState\n"
      "    //  ★ P15 O2: 5M = チャート足なら同じ関数をそのまま評価 (lookahead_on + 関数内 [1] = 同一TFでは当該バーの式値)。\n"
      "    if p15LocalChartTf and timeframe.in_seconds(efvg5MTF) == timeframe.in_seconds()\n"
      "        [_b, _r, _rem, _bos] = sg.efvgReboundConfirmed(efvgHold5M, efvgMinThick, reboundDepthMax, reboundRecoverRatio, useFvgBosFilter, fvgBosLookback)\n"
      "        efvg5Bias := _b\n        efvg5Bos := _bos\n"
      "    else\n"
      "        [_b, _r, _rem, _bos] = request.security(syminfo.tickerid, efvg5MTF, sg.efvgReboundConfirmed(efvgHold5M, efvgMinThick, reboundDepthMax, reboundRecoverRatio, useFvgBosFilter, fvgBosLookback), lookahead = barmerge.lookahead_on)\n"
      "        efvg5Bias := _b\n        efvg5Bos := _bos\n")
    # ---- O4 : FVG15 raw from the 15M pack ----
    R("if useFvg15Logic\n    [_b, _r, _rem, _bos, _t] = request.security(syminfo.tickerid, efvg15MTF, sg.efvgRebound15Pack(fvg15Hold, efvgMinThick, reboundDepthMax, reboundRecoverRatio, false, fvgBosLookback), lookahead = barmerge.lookahead_on)\n"
      "    fvg15RawBias   := _b\n    fvg15RawReason := _r\n    fvg15RawRem    := _rem\n    fvg15RawBos    := _bos\n    fvg15RawTime   := _t\n",
      "if useFvg15Logic\n"
      "    if p15Pack15\n"
      "        fvg15RawBias   := pk15B\n        fvg15RawReason := pk15R\n        fvg15RawRem    := pk15Rem\n        fvg15RawBos    := pk15Bos\n        fvg15RawTime   := pk15T\n"
      "    else\n"
      "        [_b, _r, _rem, _bos, _t] = request.security(syminfo.tickerid, efvg15MTF, sg.efvgRebound15Pack(fvg15Hold, efvgMinThick, reboundDepthMax, reboundRecoverRatio, false, fvgBosLookback), lookahead = barmerge.lookahead_on)\n"
      "        fvg15RawBias   := _b\n        fvg15RawReason := _r\n        fvg15RawRem    := _rem\n        fvg15RawBos    := _bos\n        fvg15RawTime   := _t\n")
    # ---- O2 : ABS 5M at chart TF -> local ; O4 : ABS 15M from the pack ----
    R("if useFvgAbs5Logic\n    [_ab, _ae, _at] = request.security(syminfo.tickerid, efvg5MTF, sg.efvgAbsConfirmed(absHold5M, efvgMinThick, efvgAbsBodyMin, efvgAbsEdge, useAbsCandleColor, useAbsBodyFilter, useAbsEdgeFilter), lookahead = barmerge.lookahead_on)\n"
      "    absBias5      := _ab\n    absEvent5     := _ae\n    absEventTime5 := _at\n",
      "if useFvgAbs5Logic\n"
      "    if p15LocalChartTf and timeframe.in_seconds(efvg5MTF) == timeframe.in_seconds()\n"
      "        [_ab, _ae, _at] = sg.efvgAbsConfirmed(absHold5M, efvgMinThick, efvgAbsBodyMin, efvgAbsEdge, useAbsCandleColor, useAbsBodyFilter, useAbsEdgeFilter)\n"
      "        absBias5      := _ab\n        absEvent5     := _ae\n        absEventTime5 := _at\n"
      "    else\n"
      "        [_ab, _ae, _at] = request.security(syminfo.tickerid, efvg5MTF, sg.efvgAbsConfirmed(absHold5M, efvgMinThick, efvgAbsBodyMin, efvgAbsEdge, useAbsCandleColor, useAbsBodyFilter, useAbsEdgeFilter), lookahead = barmerge.lookahead_on)\n"
      "        absBias5      := _ab\n        absEvent5     := _ae\n        absEventTime5 := _at\n")
    R("if useFvgAbs15Logic\n    [_ab, _ae, _at] = request.security(syminfo.tickerid, efvg15MTF, sg.efvgAbsConfirmed(efvgHold15M, efvgMinThick, efvgAbsBodyMin, efvgAbsEdge, useAbsCandleColor, useAbsBodyFilter, useAbsEdgeFilter), lookahead = barmerge.lookahead_on)\n"
      "    absBias15      := _ab\n    absEvent15     := _ae\n    absEventTime15 := _at\n",
      "if useFvgAbs15Logic\n"
      "    if p15Pack15\n"
      "        absBias15      := pk15Ab\n        absEvent15     := pk15Ae\n        absEventTime15 := pk15At\n"
      "    else\n"
      "        [_ab, _ae, _at] = request.security(syminfo.tickerid, efvg15MTF, sg.efvgAbsConfirmed(efvgHold15M, efvgMinThick, efvgAbsBodyMin, efvgAbsEdge, useAbsCandleColor, useAbsBodyFilter, useAbsEdgeFilter), lookahead = barmerge.lookahead_on)\n"
      "        absBias15      := _ab\n        absEvent15     := _ae\n        absEventTime15 := _at\n")
    # ---- O1 : merge the two 1M lower_tf requests ----
    R("if useFvgAbs5Logic\n    [_a1b, _a1s] = request.security_lower_tf(syminfo.tickerid, triggerTF, sg.bosPack(absBos1mLookback))\n"
      "    absBos1m  := _a1b\n    absBos1mS := _a1s\n",
      "//  ★ P15 O1: ABS 1M BOS と Zone 精密TF (下位足) が同じTFなら、1回の security_lower_tf で両方取る。\n"
      "//    同一シンボル・同一TF・同じ intrabar 列。各関数 (bosPack / zoneTfPack) と引数は元と同一。\n"
      "bool p15Merge1m = p15MergeLtf1m and useFvgAbs5Logic and useZoneAny and\n"
      "     timeframe.in_seconds(zoneBosTf) < timeframe.in_seconds() and triggerTF == zoneBosTf\n"
      "f_p15Ltf1m() =>\n"
      "    [_ab, _as] = sg.bosPack(absBos1mLookback)\n"
      "    [_zc, _zh, _zl, _zb, _zs] = sg.zoneTfPack(zoneBosLookback)\n"
      "    [_ab, _as, _zc, _zh, _zl, _zb, _zs]\n"
      "array<float> p15ZbC = na\narray<float> p15ZbH = na\narray<float> p15ZbL = na\narray<bool>  p15ZbB = na\narray<bool>  p15ZbS = na\n"
      "if useFvgAbs5Logic\n"
      "    if p15Merge1m\n"
      "        [_m1b, _m1s, _mzc, _mzh, _mzl, _mzb, _mzs] = request.security_lower_tf(syminfo.tickerid, triggerTF, f_p15Ltf1m())\n"
      "        absBos1m  := _m1b\n        absBos1mS := _m1s\n"
      "        p15ZbC := _mzc\n        p15ZbH := _mzh\n        p15ZbL := _mzl\n        p15ZbB := _mzb\n        p15ZbS := _mzs\n"
      "    else\n"
      "        [_a1b, _a1s] = request.security_lower_tf(syminfo.tickerid, triggerTF, sg.bosPack(absBos1mLookback))\n"
      "        absBos1m  := _a1b\n        absBos1mS := _a1s\n")
    R("    if zbLowerTf\n        [_zc, _zh, _zl, _lb, _ls] = request.security_lower_tf(syminfo.tickerid, zoneBosTf, sg.zoneTfPack(zoneBosLookback))\n"
      "        zbTfC     := _zc\n        zbTfH     := _zh\n        zbTfL     := _zl\n        zbBullArr := _lb\n        zbBearArr := _ls\n",
      "    if zbLowerTf\n"
      "        if p15Merge1m\n"
      "            zbTfC     := p15ZbC\n            zbTfH     := p15ZbH\n            zbTfL     := p15ZbL\n            zbBullArr := p15ZbB\n            zbBearArr := p15ZbS\n"
      "        else\n"
      "            [_zc, _zh, _zl, _lb, _ls] = request.security_lower_tf(syminfo.tickerid, zoneBosTf, sg.zoneTfPack(zoneBosLookback))\n"
      "            zbTfC     := _zc\n            zbTfH     := _zh\n            zbTfL     := _zl\n            zbBullArr := _lb\n            zbBearArr := _ls\n")
    # ---- O4 : Accum15 from the pack ----
    R("if useAccumNoTrade and useAccumNT15M\n    [_h15, _l15, _s15] = request.security(syminfo.tickerid, accumNT15Tf, sg.accumNT15Confirmed(fvgAccCfg, accumNTRangeLen, accumNTBaseLen, accumNTAtrLen), lookahead = barmerge.lookahead_on)\n"
      "    acc15Hi := _h15\n    acc15Lo := _l15\n    acc15St := _s15\n",
      "if useAccumNoTrade and useAccumNT15M\n"
      "    if p15Pack15\n"
      "        acc15Hi := pk15Hi\n        acc15Lo := pk15Lo\n        acc15St := pk15St\n"
      "    else\n"
      "        [_h15, _l15, _s15] = request.security(syminfo.tickerid, accumNT15Tf, sg.accumNT15Confirmed(fvgAccCfg, accumNTRangeLen, accumNTBaseLen, accumNTAtrLen), lookahead = barmerge.lookahead_on)\n"
      "        acc15Hi := _h15\n        acc15Lo := _l15\n        acc15St := _s15\n")
    # ---- O6 : shared read-only default Signal objects + reused DispatchStat ----
    R("sg.FvgSignal   fvg15Base = sg.FvgSignal.new()\nsg.Fvg15Signal fvg15Sig  = sg.Fvg15Signal.new()\n",
      "//  ★ P15 O6: OFF 時の既定 Signal は共有の var オブジェクト (読み取り専用・誰も書き換えない)。\n"
      "var sg.FvgSignal       gDefFvgSig   = sg.FvgSignal.new()\nvar sg.Fvg15Signal     gDefFvg15Sig = sg.Fvg15Signal.new()\n"
      "var sg.FvgAbsSignal    gDefAbsSig   = sg.FvgAbsSignal.new()\nvar sg.ZoneLogicSignal gDefZoneSig  = sg.ZoneLogicSignal.new()\n"
      "sg.FvgSignal   fvg15Base = gDefFvgSig\nsg.Fvg15Signal fvg15Sig  = gDefFvg15Sig\n")
    R("sg.FvgAbsSignal absSig = sg.FvgAbsSignal.new()\n", "sg.FvgAbsSignal absSig = gDefAbsSig\n")
    R("sg.ZoneLogicSignal zlSig = sg.ZoneLogicSignal.new()\n", "sg.ZoneLogicSignal zlSig = gDefZoneSig\n")
    R("DispatchStat ds             = DispatchStat.new()\n",
      "//  ★ P15 O6: DispatchStat は var で1個を再利用し、毎バー全 field を初期値へ戻す (= 毎バー new と同値)。\n"
      "var DispatchStat ds        = DispatchStat.new()\n"
      "ds.winPriority := na\nds.insideScans := 0\nds.plans       := 0\nds.qtys        := 0\nds.insPrice    := na\nds.insBlocked  := false\n")
    return t


def p15_default_requests(src, optimized):
    """Mirror of the request guards with DEFAULT inputs (chart = 5M). Returns (security, lower_tf) issued per bar."""
    I = {k: v["default"].strip('"') for k, v in parse_inputs(src).items() if v.get("default")}
    b = lambda k: I[k] == "true"
    chart = 300
    sec = {"1": 60, "5": 300, "15": 900, "60": 3600, "240": 14400, "D": 86400}
    useZoneAny = b("useZoneRebound") or b("useZoneFake") or b("useZoneRetest") or b("useZoneBreak")
    absAny = b("useFvgAbs5Logic") or b("useFvgAbs15Logic")
    on = optimized
    S = L = 0
    # Zone block
    S += b("useMaSource")
    if b("useHzSource"):
        S += 0 if (on and sec[I["hzTf1"]] == chart) else 1
        S += 1
        packHzAcc = on and b("useAccSource") and I["hzTf3"] == I["accTf1"]
        S += 0 if packHzAcc else 1
    else:
        packHzAcc = False
    if b("useAccSource"):
        S += 3
    S += 0 if sec[I["breakTf"]] == chart else 1
    # Signal block
    trig = sum(b(k) for k in ("useEngulfingTrigger", "usePinbarTrigger", "useBOSTrigger", "useEMARejectTrigger",
                              "useFVGTriggerFormation", "useStrongCandleTrigger"))
    L += 1 if (b("useLowerTFTrigger") and trig > 0) else 0
    S += 1 if (I["volMode"] == "ATR" and I["atrTf"] != "") else 0
    envBlock = b("useEnvFilter") or useZoneAny
    need = lambda tf: (not on) or (b("useEnvFilter") and I["reqTrend" + tf] != "OFF") or (useZoneAny and tf in ("4H", "1H", "15M"))
    pack15 = on and envBlock and need("15M") and b("useFvg15Logic") and b("useFvgAbs15Logic") and b("useAccumNoTrade") \
        and b("useAccumNT15M") and I["tf15M"] == I["efvg15MTF"] and I["accumNT15Tf"] == I["efvg15MTF"]
    if envBlock:
        S += need("4H") + need("1H") + (0 if pack15 else need("15M"))
        S += (0 if (on and sec[I["tf5M"]] == chart) else 1) if need("5M") else 0
        S += need("1M")
    if b("useEFVGEnv") and b("useEFVGDaily"): S += 1
    if b("useEFVGEnv") and b("useEFVG4H"): S += 1
    if b("useEFVGEnv") and b("useEFVG1H"): S += 1
    if b("useEFVGEnv") and (b("useEFVG5M") or (b("useEFVG15M") and b("useFvgBosFilter"))):
        S += 0 if (on and sec[I["efvg5MTF"]] == chart) else 1
    if b("useEFVGEnv") and b("useEFVG15M"): S += 1
    if b("useFvg15Logic"): S += 0 if pack15 else 1
    if b("useEFVGEnv") and b("useEFVG1M"): S += 1
    if b("useFvgAbs5Logic"): S += 0 if (on and sec[I["efvg5MTF"]] == chart) else 1
    if b("useFvgAbs15Logic"): S += 0 if pack15 else 1
    merge1m = on and b("useFvgAbs5Logic") and useZoneAny and sec[I["zoneBosTf"]] < chart and I["triggerTF"] == I["zoneBosTf"]
    if b("useFvgAbs5Logic"): L += 1
    if useZoneAny:
        if sec[I["zoneBosTf"]] < chart:
            L += 0 if merge1m else 1
        else:
            S += 1
        S += 0 if sec[I["zoneBreakTf"]] <= chart else 1
    if b("useDailyRegimeFilter"): S += 1
    if b("useDailyRegimeFilter") or absAny or useZoneAny: S += 1
    if b("useAccumNoTrade") and b("useAccumNT15M"): S += 0 if pack15 else 1
    S += pack15
    return S, L


P15_LEDGER = {"O1": "PASS", "O2": "PASS", "O3": "PASS", "O4": "PASS", "O5": "SKIPPED_UNSAFE", "O6": "PASS",
              "O7": "PASS (Main audit: no further eliminable calculation; library-internal candidates deferred)",
              "O8": "SKIPPED_UNSAFE"}


def fixture_p15():
    refs = {n: _git_show(P15_REF, f"PracticalZoneStrategy_{n}.pine") for n in ("LONG", "SHORT")}
    curs = {"LONG": LG_CUR, "SHORT": SH_CUR}
    for n in ("LONG", "SHORT"):
        ref, cur = refs[n], curs[n]
        rc, cc = code_only(ref), code_only(cur)
        check(f"P15-00-{n} file == p15_transform({P15_REF}) exactly (documented O1/O2/O3/O4/O6 edits only)",
              bool(ref) and p15_transform(ref) == cur)
        check(f"P15-00b-{n} Reference SHA matches PRACTICAL_ZONE_STRATEGY_REFERENCE.md",
              ("8bffaf07bc500487e88f3fe75c28335ac31a18e70ebd72f26011faafa57cdf2d" if n == "LONG" else
               "faf3b7352a2d6928e3857cf1b4779fa68fafda4bd39fd1170a6d441c79ac5f40") in open(os.path.join(ROOT, "PRACTICAL_ZONE_STRATEGY_REFERENCE.md"), encoding="utf-8").read()
              and __import__("hashlib").sha256(ref.encode("utf-8")).hexdigest() in open(os.path.join(ROOT, "PRACTICAL_ZONE_STRATEGY_REFERENCE.md"), encoding="utf-8").read())
        # ---- OFF path = Reference: every Reference request expression is still present verbatim ----
        ref_req = [" ".join(m.split()) for m in re.findall(r"(request\.security(?:_lower_tf)?\((?:[^()]|\((?:[^()]|\([^()]*\))*\))*\))", rc)]
        cur_flat = " ".join(cc.split())
        miss = [r_ for r_ in ref_req if r_ not in cur_flat]
        check(f"P15-13-{n} every Reference request expression kept verbatim as the switch-OFF / non-default path",
              len(ref_req) == 31 and not miss, str(miss)[:300])
        # ---- O1 ----
        f1 = code_only(func_block(cur, "f_p15Ltf1m"))
        check(f"P15-14-{n} O1 merged lower_tf = bosPack(absBos1mLookback) + zoneTfPack(zoneBosLookback) unchanged, same symbol / TF, "
              "only when both active, zone TF is lower and triggerTF == zoneBosTf; outputs mapped in order",
              "[_ab, _as] = sg.bosPack(absBos1mLookback)" in f1 and "[_zc, _zh, _zl, _zb, _zs] = sg.zoneTfPack(zoneBosLookback)" in f1
              and "[_ab, _as, _zc, _zh, _zl, _zb, _zs]" in f1
              and "request.security_lower_tf(syminfo.tickerid, triggerTF, f_p15Ltf1m())" in cc
              and "bool p15Merge1m = p15MergeLtf1m and useFvgAbs5Logic and useZoneAny and" in cc
              and "timeframe.in_seconds(zoneBosTf) < timeframe.in_seconds() and triggerTF == zoneBosTf" in cc
              and all(x in cc for x in ("absBos1m  := _m1b", "absBos1mS := _m1s", "zbTfC     := p15ZbC", "zbTfH     := p15ZbH",
                                         "zbTfL     := p15ZbL", "zbBullArr := p15ZbB", "zbBearArr := p15ZbS")))
        # ---- O2 ----
        locs = [("zn.pivotPack(pivLen1)", "hzTf1"), ("sg.efvgReboundConfirmed(efvgHold5M, efvgMinThick, reboundDepthMax, reboundRecoverRatio, useFvgBosFilter, fvgBosLookback)", "efvg5MTF"),
                ("sg.efvgAbsConfirmed(absHold5M, efvgMinThick, efvgAbsBodyMin, efvgAbsEdge, useAbsCandleColor, useAbsBodyFilter, useAbsEdgeFilter)", "efvg5MTF"),
                ("sg.envTrend(fvgEnvCfg, len20, len50, len200, envAtrLen, slopeBars, convDivBars, crossBars, rangeBars, minScore5M)", "tf5M")]
        for ex, tf in locs:
            ref_has = re.search(r"request\.security\(syminfo\.tickerid, " + re.escape(tf) + r",\s*" + re.escape(ex) + r",", rc) is not None
            loc_has = re.search(r"(=|:=)\s*" + re.escape(ex) + r"\s*$", cc, re.M) is not None
            guard = f"p15LocalChartTf and timeframe.in_seconds({tf}) == timeframe.in_seconds()" in cc
            check(f"P15-01/13-{n} O2 local {ex.split('(')[0]} ({tf}) = the exact expression the Reference requested on that TF, only when TF == chart",
                  ref_has and loc_has and guard)
        # ---- O3 ----
        check(f"P15-02-{n} O3 env requests issued only when their result can be read (updateFvg: en = reqTrend != OFF; Zone: 4H/1H/15M)",
              'bool needEnv5M  = not p15SkipOffEnv or (useEnvFilter and reqTrend5M  != "OFF")' in cc
              and 'bool needEnv1M  = not p15SkipOffEnv or (useEnvFilter and reqTrend1M  != "OFF")' in cc
              and 'bool needEnv4H  = not p15SkipOffEnv or (useEnvFilter and reqTrend4H  != "OFF") or useZoneAny' in cc
              and 'm5M  = en5M  and not na(f.env5M)  and f.env5M  == f_reqCode(c.reqTrend5M)' in SEP_SRC
              and 'en5M  = c.reqTrend5M  != "OFF"' in SEP_SRC and SEP_SRC.count("f.env5M") == 2 and SEP_SRC.count("f.env1M") == 2
              and "zoneTfEnvOk(t, f.env4H, f.env1H, f.env15M)" in SEP_SRC and "env5M" not in cc[cc.find("sg.ZoneEnvFeed zoneEnvFeed"):cc.find("var sg.ZoneTfEnvCfg zcRbL")])
        # ---- O4 ----
        f15 = code_only(func_block(cur, "f_p15Pack15"))
        inner = ["sg.envTrendConfirmed(fvgEnvCfg, len20, len50, len200, envAtrLen, slopeBars, convDivBars, crossBars, rangeBars, minScore15M)",
                 "sg.efvgRebound15Pack(fvg15Hold, efvgMinThick, reboundDepthMax, reboundRecoverRatio, false, fvgBosLookback)",
                 "sg.efvgAbsConfirmed(efvgHold15M, efvgMinThick, efvgAbsBodyMin, efvgAbsEdge, useAbsCandleColor, useAbsBodyFilter, useAbsEdgeFilter)",
                 "sg.accumNT15Confirmed(fvgAccCfg, accumNTRangeLen, accumNTBaseLen, accumNTAtrLen)"]
        check(f"P15-13-{n} O4 15M pack = the 4 Reference lookahead_on expressions unchanged, same TF guard, lookahead_on, ordered mapping",
              all(x in f15 and x in rc for x in inner) and "[_e, _b, _r, _rem, _bos, _t, _ab, _ae, _at, _h, _l, _s]" in f15
              and "request.security(syminfo.tickerid, efvg15MTF, f_p15Pack15(), lookahead = barmerge.lookahead_on)" in cc
              and "tf15M == efvg15MTF and accumNT15Tf == efvg15MTF" in cc
              and all(f"lookahead = barmerge.lookahead_on" in l for l in rc.split("\n") if any(x in l for x in inner) and "request." in l)
              and all(x in cc for x in ("env15M := pk15Env", "fvg15RawBias   := pk15B", "fvg15RawTime   := pk15T", "absBias15      := pk15Ab",
                                         "absEventTime15 := pk15At", "acc15Hi := pk15Hi", "acc15St := pk15St")))
        fz = code_only(func_block(cur, "f_p15HzAccPack"))
        check(f"P15-13-{n} O4 Zone pack = pivotPack(pivLen3) + accumPack(.., accLen1, ..) unchanged, both lookahead_off, hzTf3 == accTf1",
              "zn.pivotPack(pivLen3)" in fz and "accLen1, accMult)" in fz and "bool p15PackHzAcc = p15PackSameTf and useHzSource and useAccSource and hzTf3 == accTf1" in cc
              and "request.security(syminfo.tickerid, accTf1, f_p15HzAccPack(), lookahead = barmerge.lookahead_off)" in cc
              and "request.security(syminfo.tickerid, hzTf3, zn.pivotPack(pivLen3), lookahead = barmerge.lookahead_off)" in rc)
        # ---- O6 ----
        ds_fields = re.findall(r"^\s+\w+\s+(\w+)\s*=", code_only(cur[cur.find("type DispatchStat"):cur.find("// ---- 1候補の評価")]), re.M)
        resets = re.findall(r"^ds\.(\w+)\s*:=", cc, re.M)
        check(f"P15-05-{n} O6 DispatchStat reused: every field reset each bar (== fresh object); default Signals shared and never written",
              sorted(ds_fields) == sorted(resets) and len(resets) == 6 and "var DispatchStat ds        = DispatchStat.new()" in cc
              and not re.search(r"\b(gDef\w+|fvg15Base|fvg15Sig|absSig|zlSig)\.\w+\s*:=", cc))
        # ---- unchanged semantics: trade engine / dispatch / BE / provisional ----
        sec = lambda src, a, b_: code_only(src[src.find(a):src.find(b_)])
        check(f"P15-03/04/06-12-{n} Trade Engine (05/06), dispatch / consume / origin+touch (08), BE (09), alerts (10) identical to Reference "
              "(except the DispatchStat allocation line)",
              sec(cur, "// 05. TRADE PLAN / RISK / QTY", "// 07. SIGNAL ENGINE") == sec(ref, "// 05. TRADE PLAN / RISK / QTY", "// 07. SIGNAL ENGINE")
              and sec(cur, "// 09. BREAK EVEN", "// ---- Flat 遷移検知用") == sec(ref, "// 09. BREAK EVEN", "// ---- Flat 遷移検知用")
              and [l for l in sec(cur, "// 08. DISPATCH", "// 09. BREAK EVEN").split("\n") if not l.startswith("ds.") and "var DispatchStat ds" not in l]
              == [l for l in sec(ref, "// 08. DISPATCH", "// 09. BREAK EVEN").split("\n") if "DispatchStat ds             = DispatchStat.new()" not in l])
        check(f"P15-05-{n} Signal Engine calls / Zone snapshot / ZoneCommonCfg identical to Reference (default objects aside)",
              [l for l in sec(cur, "// ---- 7.3 Signal calls", "// ============================================================================\n// 08. DISPATCH").split("\n") if "gDef" not in l]
              == [l for l in sec(ref, "// ---- 7.3 Signal calls", "// ============================================================================\n// 08. DISPATCH").split("\n")
                  if not re.search(r"= sg\.(FvgSignal|Fvg15Signal|FvgAbsSignal|ZoneLogicSignal)\.new\(\)", l)]
              + [])
        check(f"P15-{n} SignalEngine call count unchanged (updateFvg 2 / updateFvg15 1 / updateFvgAbs 1 / updateZoneEvents 1), zn.update 1",
              all(cc.count(x) == rc.count(x) for x in ("sg.updateFvg(", "sg.updateFvg15(", "sg.updateFvgAbs(", "sg.updateZoneEvents(", "zn.update(")))
        check(f"P15-{n} allocation not worse: per-bar array.new 0, input-only configs var, provisional slots 8",
              len(re.findall(r"^array<\w+>\s+\w+\s*=\s*array\.new", cc, re.M)) == 0
              and all(re.search(r"^var sg\." + t_ + r" \w+ = ", cc, re.M) for t_ in ("FvgTrigCfg", "FvgEnvCfg", "FvgAccCfg"))
              and "varip array<bool> gProvSent = array.new_bool(8, false)" in cc)
        I = parse_inputs(cur)
        check(f"P15-{n} switches are inputs defaulting to ON (OFF = Reference path)",
              all(I.get(k, {}).get("default") == "true" for k in ("p15MergeLtf1m", "p15LocalChartTf", "p15SkipOffEnv", "p15PackSameTf")))
        before, after = p15_default_requests(ref, False), p15_default_requests(cur, True)
        check(f"P15-{n} default issued requests: before security {before[0]} + lower_tf {before[1]}; after security {after[0]} + lower_tf {after[1]}",
              before == (19, 2) and after == (10, 1), f"{before} -> {after}")
    # P15-16/17 direction isolation and full production audit on the optimized files
    fixture_p14_final_audit(files=(("LONG", LG_CUR, 1), ("SHORT", SH_CUR, -1)), req_sites=34, label="P15-16/17")
    check("P15 ledger: O1 PASS / O2 PASS / O3 PASS / O4 PASS / O5 SKIPPED_UNSAFE / O6 PASS / O7 PASS / O8 SKIPPED_UNSAFE",
          [P15_LEDGER[k].split()[0] for k in sorted(P15_LEDGER)] == ["PASS", "PASS", "PASS", "PASS", "SKIPPED_UNSAFE", "PASS", "PASS", "SKIPPED_UNSAFE"])


# ============================================================================
# P16 : Zone Visual (Practical) — 5M-only execution gate
# ============================================================================
def vis_eval_5m(src):
    """Partially evaluate the gated Visual with is5mChart = true: remove the flag / gate comments,
    drop 'is5mChart and ' guards, de-indent the 'if is5mChart' blocks, restore the original declarations."""
    t = src
    t = re.sub(r"\n\n// ---- 5分足専用 Execution Gate -+\n(//.*\n)*bool is5mChart = timeframe\.isminutes and timeframe\.multiplier == 5\n", "\n", t)
    t = re.sub(r"^//  ★ 5分足専用.*\n(//    .*\n)?", "", t, flags=re.M)
    t = t.replace("is5mChart and ", "").replace(" and is5mChart", "")
    # trading day
    t = t.replace("int tradingDayId = na\nif is5mChart\n", "")
    t = t.replace("    tradingDayId := _locH < dayResetHour ? _calDayNo - 1 : _calDayNo\n",
                  "int tradingDayId = _locH < dayResetHour ? _calDayNo - 1 : _calDayNo\n")
    for v in ("_locY", "_locM", "_locD", "_locH", "_calDayNo"):
        t = re.sub(r"^    int " + v + r"\b", "int " + v, t, flags=re.M)
    # engine update
    t = t.replace("int zoneCountNow = 0\n\nif is5mChart\n    zoneCountNow := zn.update(zoneEng, zoneCfg, zoneFeed)\n",
                  "int zoneCountNow = zn.update(zoneEng, zoneCfg, zoneFeed)\n")
    # break block: de-indent the 'if is5mChart' body and put the 4 declarations back after brNewPeriod
    i = t.find("if is5mChart\n    int   brTfSec")
    if i >= 0:
        j = t.find("\n\n", i)
        body = t[i + len("if is5mChart\n"):j + 1]
        ded = "".join(l[4:] if l.startswith("    ") else l for l in body.splitlines(True))
        decl = "float brClose = na\nfloat brHigh  = na\nfloat brLow   = na\nbool  brEval  = false\n"
        ded = ded.replace("bool  brNewPeriod = bar_index > 0 and not na(brTfTime) and nz(ta.change(brTfTime), 0) != 0\n",
                          "bool  brNewPeriod = bar_index > 0 and not na(brTfTime) and nz(ta.change(brTfTime), 0) != 0\n" + decl)
        t = t[:i] + ded + t[j + 1:]
        t = t.replace(decl + "int   brTfSec", "int   brTfSec", 1)
    return t


VIS_GATE_REV = "d240ec0"      # 5M gate + import /2 stage; the /4 Visual is tied to it by fixture_v4_5m_direct
VIS_GATE = __import__("subprocess").run(["git", "-C", ROOT, "show", VIS_GATE_REV + ":ZoneVisualPractical.pine"],
                                        capture_output=True, text=True).stdout


def fixture_p16_visual_5m_gate():
    pre, cur = VIS, VIS_GATE
    cc = code_only(cur)
    check("P16-01 5M flag = timeframe.isminutes and timeframe.multiplier == 5 (not in_seconds == 300)",
          "bool is5mChart = timeframe.isminutes and timeframe.multiplier == 5" in cc and "in_seconds() == 300" not in cc)
    imp1, imp2 = "import sekine3310/ZoneEnginePractical/1 as zn\n", "import sekine3310/ZoneEnginePractical/2 as zn\n"
    check("P16-02 5M chart: gated Visual partially evaluated with is5mChart = true == pre-gate Visual (b3b69ae) exactly "
          "(only the library import version /1 -> /2 differs)",
          bool(pre) and imp1 in pre and vis_eval_5m(cur).replace(imp2, imp1) == pre)
    check("P16-03 MA / Swing / Accum source requests only on 5M (if is5mChart and use*Source)",
          all(f"if is5mChart and {x}\n" in cc for x in ("useMaSource", "useHzSource", "useAccSource"))
          and not re.search(r"^if use(Ma|Hz|Acc)Source\n", cc, re.M))
    br = cc[cc.find("float brClose = na"):cc.find("int tradingDayId = na")]
    check("P16-04 Break: brClose/High/Low = na, brEval = false declared first; all acquisition / evaluation (3 paths, unchanged) inside if is5mChart",
          br.startswith("float brClose = na\nfloat brHigh  = na\nfloat brLow   = na\nbool  brEval  = false\nif is5mChart\n")
          and all(l.startswith("    ") or not l.strip() for l in br.split("\n")[5:])
          and "request.security(syminfo.tickerid, breakTf, [close, high, low]," in br and "// Break TF < チャート足 : 旧版の経路 (変更なし)" in VIS_CUR)
    check("P16-05 tradingDayId = na, real calculation only inside if is5mChart (same formula / timezone / reset hour)",
          "int tradingDayId = na\nif is5mChart\n    int _locY = year(time, dayTz)" in cc
          and "    tradingDayId := _locH < dayResetHour ? _calDayNo - 1 : _calDayNo" in cc)
    check("P16-06 zn.update is called only inside if is5mChart (never with empty feed on other TFs)",
          cc.count("zn.update(") == 1 and "int zoneCountNow = 0\n\nif is5mChart\n    zoneCountNow := zn.update(zoneEng, zoneCfg, zoneFeed)" in cc)
    check("P16-07 Zone box / label drawing, MA lines, Stats table gated by is5mChart",
          "if barstate.islast and is5mChart\n    int nBox = 0" in cc and "if barstate.islast and is5mChart and showStats" in cc
          and cc.count("plot(is5mChart and showMaLines and useMaSource ?") == 2 and cc.count("plot(") == 2
          and len(re.findall(r"\b(box|label|table)\.new\(", cc)) == len(re.findall(r"\b(box|label|table)\.new\(", code_only(pre))))
    req_pre = re.findall(r"request\.security\(.*", code_only(pre))
    req_cur = re.findall(r"request\.security\(.*", cc)
    check("P16-08 request expressions / lookahead / TFs unchanged (only wrapped by the gate)", req_pre == req_cur and len(req_cur) == 8)
    check("P16-09 inputs / defaults unchanged; library import = Production ZoneEnginePractical/2 (only import line changed)",
          parse_inputs(cur) == parse_inputs(pre) and re.findall(r"^import .*$", cc, re.M) == ["import sekine3310/ZoneEnginePractical/2 as zn"])
    # non-5M mirror: every gated item is skipped
    gated = {"MA": "if is5mChart and useMaSource", "HZ": "if is5mChart and useHzSource", "ACC": "if is5mChart and useAccSource",
             "BREAK": "bool  brEval  = false\nif is5mChart", "DAY": "int tradingDayId = na\nif is5mChart",
             "UPDATE": "if is5mChart\n    zoneCountNow := zn.update", "DRAW": "if barstate.islast and is5mChart\n",
             "STATS": "if barstate.islast and is5mChart and showStats"}
    check("P16-10 non-5M (1M / 15M / 1H): Source requests, Break, trading day, zn.update, boxes / labels, MA lines, Stats all skipped",
          all(v in cc for v in gated.values()))


# ============================================================================
# L3 : ZoneEnginePractical — Authority Feed version (new library source)
# ============================================================================
#  Source of the next ZoneEnginePractical publish. The existing ZoneEnginePractical.pine (source of the
#  versions imported by the Strategy / Visual today) is NOT modified.
L3_SRC_PATH = os.path.join(ROOT, "ZoneEnginePracticalAuthority.pine")
import sys as _sys
_sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import visual_mtf as vm                                     # noqa: E402
from visual_mtf_build import v4_mtf_transform, v4_mtf_eval_off   # noqa: E402
L3_BASE_REV = "b572dc8"     # ZoneEnginePractical.pine at this rev = the base the parity is proven against


def l3_transform(src):
    """built-in -> Authority Feed substitution. Only *which value is read* changes; no expression is altered."""
    t = src

    def R(a, b, n=1):
        nonlocal t
        assert t.count(a) == n, (a[:90], t.count(a))
        t = t.replace(a, b)
    # ---- header note ----
    R("//  ZoneEnginePractical  —  Practical Zone v1 (Support / Resistance Zone Engine)\n",
      "//  ZoneEnginePractical  —  Practical Zone v1 (Support / Resistance Zone Engine)\n"
      "//  ★ Authority Feed 版 (Zone Visual MTF 用)。update() 経路はチャート足の high / low / close /\n"
      "//    time / bar_index を直接読まず、ZoneFeed の barHigh / barLow / barClose / barTime / barIndex\n"
      "//    (= 今処理している Engine 足 (5分足) 自身の値) を読む。判定式は従来と同一で、\n"
      "//    呼び出し側が barX = 組み込み値を渡せば結果は従来版と完全一致する。\n"
      "//    drawOrder / nearestIdx の基準 close も最後に処理した Authority close。\n")
    # ---- ZoneFeed fields ----
    R("    float brLow   = na\n    bool  brEval  = false\n",
      "    float brLow   = na\n    bool  brEval  = false\n"
      "    // ★ Authority bar (今処理している Engine 足自身の値。必須)\n"
      "    //   Engine 足のチャートで呼ぶ場合は high / low / close / time / bar_index をそのまま渡す。\n"
      "    float barHigh  = na\n    float barLow   = na\n    float barClose = na\n    int   barTime  = na\n    int   barIndex = na\n")
    # ---- ZoneEngine: authority copy of the bar being processed ----
    R("    array<int>     sIds         // Accum 世代管理用\n",
      "    array<int>     sIds         // Accum 世代管理用\n"
      "    // ---- Authority bar (update() 冒頭で ZoneFeed からコピー。helper はこれを読む) ----\n"
      "    //  aClose は最後に処理した Authority close (drawOrder / nearestIdx の基準)。\n"
      "    float aHigh  = na\n    float aLow   = na\n    float aClose = na\n    int   aTime  = na\n    int   aIndex = na\n")
    # ---- f_makeRaw ----
    R("f_makeRaw(ZoneCfg c, int uid, string id, string cat, string tf, float ctr, float bs, bool dyn) =>",
      "f_makeRaw(ZoneCfg c, int uid, string id, string cat, string tf, float ctr, float bs, bool dyn, int aIdx, int aTm) =>")
    R("baseScore = bs, createdBar = bar_index, createdTime = time, dynamic = dyn)",
      "baseScore = bs, createdBar = aIdx, createdTime = aTm, dynamic = dyn)")
    R("RawZone rz = f_makeRaw(c, f_nextUid(e), id, cat, tf, price, bs, false)",
      "RawZone rz = f_makeRaw(c, f_nextUid(e), id, cat, tf, price, bs, false, e.aIndex, e.aTime)")
    R("RawZone rz = f_makeRaw(c, f_nextUid(e), id, CAT_ACC, tf, price, bs, false)",
      "RawZone rz = f_makeRaw(c, f_nextUid(e), id, CAT_ACC, tf, price, bs, false, e.aIndex, e.aTime)")
    # ---- f_registerStatic (lifetime) ----
    R("                        z.expireTime := time + life\n", "                        z.expireTime := e.aTime + life\n")
    R("            rz.expireTime := life > 0 ? time + life : 0\n", "            rz.expireTime := life > 0 ? e.aTime + life : 0\n")
    # ---- f_prunePersist (lifetime) ----
    R("    if not na(e.nextPersistExpireTime) and time > e.nextPersistExpireTime\n",
      "    if not na(e.nextPersistExpireTime) and e.aTime > e.nextPersistExpireTime\n")
    R("                    if z.expireTime > 0 and time > z.expireTime\n", "                    if z.expireTime > 0 and e.aTime > z.expireTime\n")
    # ---- f_findTrack ----
    R("            if na(t.matchedBar) or t.matchedBar != bar_index\n", "            if na(t.matchedBar) or t.matchedBar != e.aIndex\n")
    # ---- f_naturalState ----
    R("f_naturalState(float top, float bottom) =>\n    close > top ? ST_SUPPORT : close < bottom ? ST_RESIST : ST_ACTIVE\n",
      "f_naturalState(float top, float bottom, float refClose) =>\n    refClose > top ? ST_SUPPORT : refClose < bottom ? ST_RESIST : ST_ACTIVE\n")
    # ---- f_updateTrack ----
    R("f_updateTrack(ZoneTrack t, ZoneCfg c, bool evalBar, float bc, float bh, float bl) =>",
      "f_updateTrack(ZoneTrack t, ZoneCfg c, bool evalBar, float bc, float bh, float bl, float aClose, int aIdx) =>")
    R("            t.breakBar := bar_index\n", "            t.breakBar := aIdx\n", 2)
    R("                    t.state := f_naturalState(t.top, t.bottom)\n", "                    t.state := f_naturalState(t.top, t.bottom, aClose)\n", 2)
    R("        t.state := f_naturalState(t.top, t.bottom)\n\n    if t.state == ST_SUPPORT",
      "        t.state := f_naturalState(t.top, t.bottom, aClose)\n\n    if t.state == ST_SUPPORT")
    # ---- f_updateTouch ----
    R("f_updateTouch(ZoneTrack t, Zone z, ZoneCfg c) =>", "f_updateTouch(ZoneTrack t, Zone z, ZoneCfg c, float aHigh, float aLow, int aIdx) =>")
    R("        if eligible and low <= t.top and high >= t.bottom\n", "        if eligible and aLow <= t.top and aHigh >= t.bottom\n")
    R("            t.lastTouchBar := bar_index\n", "            t.lastTouchBar := aIdx\n")
    R("        bool awayUp   = low  >= t.top    + c.touchRearmDist\n        bool awayDown = high <= t.bottom - c.touchRearmDist\n",
      "        bool awayUp   = aLow  >= t.top    + c.touchRearmDist\n        bool awayDown = aHigh <= t.bottom - c.touchRearmDist\n")
    # ---- f_maSlopeBonus ----
    R("f_maSlopeBonus(float maVal, int dir, int st, ZoneCfg c) =>\n    bool aligned = (dir > 0 and close > maVal) or (dir < 0 and close < maVal)\n",
      "f_maSlopeBonus(float maVal, int dir, int st, ZoneCfg c, float aClose) =>\n    bool aligned = (dir > 0 and aClose > maVal) or (dir < 0 and aClose < maVal)\n")
    # ---- f_pushDyn ----
    R("    rz.createdBar     := bar_index\n    rz.createdTime    := time\n", "    rz.createdBar     := e.aIndex\n    rz.createdTime    := e.aTime\n")
    # ---- update ----
    R("export update(ZoneEngine e, ZoneCfg c, ZoneFeed f) =>\n",
      "export update(ZoneEngine e, ZoneCfg c, ZoneFeed f) =>\n"
      "    // ---- 6.0 Authority bar : 以降の判定は全てこの値を読む (チャート足の組み込み変数は読まない) ----\n"
      "    e.aHigh  := f.barHigh\n    e.aLow   := f.barLow\n    e.aClose := f.barClose\n    e.aTime  := f.barTime\n    e.aIndex := f.barIndex\n")
    R("        e.dayHigh     := high\n        e.dayLow      := low\n", "        e.dayHigh     := f.barHigh\n        e.dayLow      := f.barLow\n")
    R("        e.dayHigh := na(e.dayHigh) ? high : math.max(e.dayHigh, high)\n        e.dayLow  := na(e.dayLow)  ? low  : math.min(e.dayLow,  low)\n",
      "        e.dayHigh := na(e.dayHigh) ? f.barHigh : math.max(e.dayHigh, f.barHigh)\n        e.dayLow  := na(e.dayLow)  ? f.barLow  : math.min(e.dayLow,  f.barLow)\n")
    R("f_maSlopeBonus(f.ma1, ma1Dir, ma1State, c)", "f_maSlopeBonus(f.ma1, ma1Dir, ma1State, c, f.barClose)")
    R("f_maSlopeBonus(f.ma2, ma2Dir, ma2State, c)", "f_maSlopeBonus(f.ma2, ma2Dir, ma2State, c, f.barClose)")
    R("                     state = f_naturalState(z.top, z.bottom), lastSeenBar = bar_index,\n",
      "                     state = f_naturalState(z.top, z.bottom, f.barClose), lastSeenBar = f.barIndex,\n")
    R("                int expBar = bar_index + c.trackStaleBars + 1\n", "                int expBar = f.barIndex + c.trackStaleBars + 1\n")
    R("            t.matchedBar  := bar_index\n", "            t.matchedBar  := f.barIndex\n")
    R("            t.lastSeenBar := bar_index\n", "            t.lastSeenBar := f.barIndex\n")
    R("            int ev = f_updateTrack(t, c, f.brEval, f.brClose, f.brHigh, f.brLow)\n",
      "            int ev = f_updateTrack(t, c, f.brEval, f.brClose, f.brHigh, f.brLow, f.barClose, f.barIndex)\n")
    R("            z.touchCount := f_updateTouch(t, z, c)\n", "            z.touchCount := f_updateTouch(t, z, c, f.barHigh, f.barLow, f.barIndex)\n")
    R("    if not na(e.nextTrackExpireBar) and bar_index >= e.nextTrackExpireBar\n",
      "    if not na(e.nextTrackExpireBar) and f.barIndex >= e.nextTrackExpireBar\n")
    R("                    if bar_index - t.lastSeenBar > c.trackStaleBars\n", "                    if f.barIndex - t.lastSeenBar > c.trackStaleBars\n")
    # ---- drawOrder / nearestIdx : last processed Authority close ----
    R("            array.push(d, math.abs(array.get(e.live, i).center - close))\n",
      "            array.push(d, math.abs(array.get(e.live, i).center - e.aClose))\n")
    R("            bool ok = wantSupport ? z.top < close : z.bottom > close\n", "            bool ok = wantSupport ? z.top < e.aClose : z.bottom > e.aClose\n")
    R("array.push(dist, wantSupport ? close - z.top : z.bottom - close)", "array.push(dist, wantSupport ? e.aClose - z.top : z.bottom - e.aClose)")
    return t


L3_BUILTIN = r"\b(high|low|close|open|time|time_close|bar_index|volume|hl2|hlc3|ohlc4)\b|\bta\.\w+|\bbarstate\.\w+|\btimeframe\.\w+"


def _pine_functions(src):
    """top-level function name -> body text (code only)."""
    out, cur, name = {}, [], None
    for ln in src.split("\n"):
        m = re.match(r"^(?:export\s+)?([A-Za-z_]\w*)\(", ln)
        if m and not ln.startswith(" "):
            if name:
                out[name] = "\n".join(cur)
            name, cur = m.group(1), [ln]
        elif name is not None:
            if ln and not ln[0].isspace() and not ln.startswith("//"):
                out[name] = "\n".join(cur)
                name, cur = None, []
            else:
                cur.append(ln)
    if name:
        out[name] = "\n".join(cur)
    return {k: code_only(v) for k, v in out.items()}


def _reachable(funcs, root):
    seen, todo = set(), [root]
    while todo:
        f_ = todo.pop()
        if f_ in seen or f_ not in funcs:
            continue
        seen.add(f_)
        body = funcs[f_].split("\n", 1)[1] if "\n" in funcs[f_] else ""
        todo += [c_ for c_ in re.findall(r"(?<![\.\w])([A-Za-z_]\w*)\(", body) if c_ in funcs]
    return seen


def fixture_l3():
    base = _git_show(L3_BASE_REV, "ZoneEnginePractical.pine")
    new = open(L3_SRC_PATH, encoding="utf-8").read() if os.path.exists(L3_SRC_PATH) else ""
    check("L3-00 existing ZoneEnginePractical.pine (published /2 / /3 source) unchanged",
          open(os.path.join(ROOT, "ZoneEnginePractical.pine"), encoding="utf-8").read() == base)
    check("L3-00b Authority library source == l3_transform(base) exactly (documented substitutions only)",
          bool(new) and l3_transform(base) == new)
    check("L3-00c same library name (publishes as the next ZoneEnginePractical version)",
          re.findall(r'^library\("(\w+)"', base, re.M) == re.findall(r'^library\("(\w+)"', new, re.M) == ["ZoneEnginePractical"])
    fb, fn_ = _pine_functions(base), _pine_functions(new)
    # ---- L3-10 : no chart built-in reachable from update() ----
    reach = _reachable(fn_, "update")
    left = {f_: sorted(set(m.group(0) for m in re.finditer(L3_BUILTIN, _strip_str_all(fn_[f_])))) for f_ in reach}
    left = {k: v for k, v in left.items() if v}
    check("L3-10 no chart built-in (high/low/close/open/time/bar_index/ta.*/barstate.*/timeframe.*) in any function reachable from update()",
          not left and len(reach) > 15, f"{len(reach)} reachable; left={left}")
    check("L3-10b base: the same reachable set DID read built-ins (Day H/L, Touch, State, Slope, Lifetime, Track, Break)",
          {k for k in _reachable(fb, "update") if re.search(L3_BUILTIN, _strip_str_all(fb[k]))} ==
          {"update", "f_makeRaw", "f_registerStatic", "f_prunePersist", "f_findTrack", "f_naturalState", "f_updateTrack",
           "f_updateTouch", "f_maSlopeBonus", "f_pushDyn"})
    rest = {k: sorted(set(m.group(0) for m in re.finditer(L3_BUILTIN, _strip_str_all(v)))) for k, v in fn_.items() if k not in reach}
    rest = {k: v for k, v in rest.items() if v}
    check("L3-10c built-ins outside update(): only Source packs evaluated inside request.* (maPack / pivotPack / accumPack + internals)",
          set(rest) <= {"maPack", "f_ma", "pivotPack", "accumPack", "f_accumBoxCore", "f_accumBoxState", "f_accumDetectProvisional"}
          and not ({"drawOrder", "nearestIdx"} & set(rest)), str(rest))
    # ---- parity on the Engine TF : barX = built-in  =>  every substituted read returns the same value ----
    upd = fn_["update"]
    head = upd.split("\n")[1:6]
    check("L3-01 Authority values copied from the Feed as the FIRST statements of update() (before any helper reads them)",
          [h.strip() for h in head] == ["e.aHigh  := f.barHigh", "e.aLow   := f.barLow", "e.aClose := f.barClose",
                                        "e.aTime  := f.barTime", "e.aIndex := f.barIndex"])
    #  reverse substitution: map every Authority read back to its built-in and drop the added params -> base, exactly
    rev = new
    for a, b in (("e.aHigh  := f.barHigh\n", ""), ("e.aLow   := f.barLow\n", ""), ("e.aClose := f.barClose\n", ""),
                 ("e.aTime  := f.barTime\n", ""), ("e.aIndex := f.barIndex\n", "")):
        rev = rev.replace("    " + a, b)
    sub = {"f.barHigh": "high", "f.barLow": "low", "f.barClose": "close", "f.barTime": "time", "f.barIndex": "bar_index",
           "e.aHigh": "high", "e.aLow": "low", "e.aClose": "close", "e.aTime": "time", "e.aIndex": "bar_index",
           "aHigh": "high", "aLow": "low", "aClose": "close", "aTm": "time", "aIdx": "bar_index", "refClose": "close"}
    body_rev = rev
    for k in sorted(sub, key=len, reverse=True):
        body_rev = re.sub(r"(?<![\w\.])" + re.escape(k) + r"\b", sub[k], body_rev)
    for a, b in ((", float close) =>", ") =>"), (", int bar_index, int time) =>", ") =>"), (", float close, int bar_index) =>", ") =>"),
                 (", float high, float low, int bar_index) =>", ") =>"),
                 (", false, bar_index, time)", ", false)"), (", c, close)", ", c)"), (", c, high, low, bar_index)", ", c)"),
                 (", f.brLow, close, bar_index)", ", f.brLow)"), ("(t.top, t.bottom, close)", "(t.top, t.bottom)"),
                 ("(z.top, z.bottom, close)", "(z.top, z.bottom)")):
        body_rev = body_rev.replace(a, b)
    rb = {k: v for k, v in _pine_functions(body_rev).items()}
    same = [k for k in fb if k in rb and fb[k] == rb[k]]
    diff = [k for k in fb if fb.get(k) != rb.get(k)]
    check("L3-01..09 Engine-TF parity: substituting barX = high / low / close / time / bar_index turns every function back into the base "
          "(Touch / State / Score / Strength / Lifetime / Track / Break / Flip / Day H/L / drawOrder all read identical values)",
          not diff and len(same) == len(fb), str(diff))
    for tag, fns in (("L3-02 Touch", ["f_updateTouch"]), ("L3-03 State", ["f_naturalState", "f_updateTrack"]),
                     ("L3-04 Score / Strength (MA slope bonus)", ["f_maSlopeBonus", "f_finalizeCluster", "f_applyStrength"]),
                     ("L3-05 Lifetime", ["f_registerStatic", "f_prunePersist", "f_makeRaw", "f_pushDyn"]),
                     ("L3-06 Track / Continuity", ["f_findTrack", "f_trackContinuous"]), ("L3-07 Break / Flip", ["f_updateTrack"]),
                     ("L3-08 Day H/L", ["update"]), ("L3-09 drawOrder / nearestIdx", ["drawOrder", "nearestIdx"])):
        check(f"{tag}: parity on the Engine TF (reverse substitution == base)", all(fb.get(f_) == rb.get(f_) and f_ in fb for f_ in fns))
    check("L3 ZoneFeed gained exactly barHigh / barLow / barClose / barTime / barIndex; ZoneEngine gained aHigh / aLow / aClose / aTime / aIndex",
          all(f"    float {x}" in new or f"    int   {x}" in new for x in ("barHigh  = na", "barLow   = na", "barClose = na", "barTime  = na", "barIndex = na"))
          and all(f"    float {x}" in new or f"    int   {x}" in new for x in ("aHigh  = na", "aLow   = na", "aClose = na", "aTime  = na", "aIndex = na")))
    check("L3 exported API unchanged (same export list and signatures; packs / TradePlan API untouched)",
          re.findall(r"^export \w+\(.*", base, re.M) == re.findall(r"^export \w+\(.*", new, re.M)
          and all(fb[k] == fn_[k] for k in ("maPack", "pivotPack", "accumPack", "buildPlanWithTpDepth", "buildPlan", "getLongStructuralSL",
                                             "getShortStructuralSL", "isInsideActiveZone", "getObstacleCount")))


def _strip_str_all(t):
    return re.sub(r'"[^"\n]*"', '""', t)


# ============================================================================
# V4 : ZoneVisualPractical on ZoneEnginePractical/4 — 5M direct path (stage 2-5)
# ============================================================================
V4_IMP_OLD = "import sekine3310/ZoneEnginePractical/2 as zn\n"
V4_IMP_NEW = "import sekine3310/ZoneEnginePractical/4 as zn\n"
V4_FEED_OLD = "     brClose = brClose, brHigh = brHigh, brLow = brLow, brEval = brEval)\n"
V4_FEED_NEW = ("     brClose = brClose, brHigh = brHigh, brLow = brLow, brEval = brEval,\n"
               "     barHigh = high, barLow = low, barClose = close, barTime = time, barIndex = bar_index)\n")


def v4_transform(src):
    """d240ec0 Visual -> /4 Visual: import version + the 5 Authority fields fed from the 5M chart itself."""
    assert src.count(V4_IMP_OLD) == 1 and src.count(V4_FEED_OLD) == 1
    return src.replace(V4_IMP_OLD, V4_IMP_NEW).replace(V4_FEED_OLD, V4_FEED_NEW)


def fixture_v4_5m_direct():
    cur, gate = VIS_CUR, VIS_GATE
    cc = code_only(cur)
    check("V4-01 Visual /4 5M direct path parity: MTF Visual with Parity Mode OFF on 5M == v4_transform(d240ec0) exactly "
          "(only import /2 -> /4 and the 5 Authority feed args; Source / Break / dayId / update order unchanged)",
          bool(gate) and v4_mtf_eval_off(cur) == v4_transform(gate))
    check("V4-01b import = ZoneEnginePractical/4 only (single library import)",
          re.findall(r"^import .*$", cc, re.M) == ["import sekine3310/ZoneEnginePractical/4 as zn"])
    feed = cc[cc.find("zn.ZoneFeed zoneFeed = zn.ZoneFeed.new(") + len("zn.ZoneFeed zoneFeed = zn.ZoneFeed.new("):]
    feed = feed[:feed.find(")\n") + 1]
    args = dict(re.findall(r"(\w+) = ([\w.]+)", feed))
    check("V4-02 Authority barHigh/Low/Close/Time/Index = 5M chart high / low / close / time / bar_index (direct path)",
          all(args.get(k) == v for k, v in (("barHigh", "high"), ("barLow", "low"), ("barClose", "close"),
                                             ("barTime", "time"), ("barIndex", "bar_index"))))
    lib = open(L3_SRC_PATH, encoding="utf-8").read()
    t = lib[lib.find("export type ZoneFeed"):]
    t = t[:t.find("\n\n")]
    fields = re.findall(r"^\s+\w+\s+(\w+)\s*=", t, re.M)
    check("V4-02b every ZoneFeed field of /4 is fed exactly once by the Visual (no field left at na)",
          sorted(args) == sorted(fields) and len(re.findall(r"\b(\w+) = ", feed)) == len(fields),
          f"feed={len(args)} lib={len(fields)}")
    check("V4-02c 5M parity chain: Engine reads aHigh/aLow/aClose/aTime/aIndex == built-ins on 5M "
          "(L3 reverse-substitution proof holds for the /4 source)",
          all(re.search(r"^    e\." + a + r"\s*:= f\." + b + r"$", lib, re.M) for a, b in (("aHigh", "barHigh"), ("aLow", "barLow"),
              ("aClose", "barClose"), ("aTime", "barTime"), ("aIndex", "barIndex"))))
    rc = __import__("subprocess").run(["git", "-C", ROOT, "diff", "--name-only", "03b9f46", "--",
                                       "PracticalZoneStrategy_LONG.pine", "PracticalZoneStrategy_SHORT.pine",
                                       "SignalEnginePractical.pine", "ZoneEnginePractical.pine",
                                       "ZoneEnginePracticalAuthority.pine"],
                                      capture_output=True, text=True).stdout.strip()
    check("V4-PROD Strategy LONG / SHORT, SignalEngine, ZoneEnginePractical.pine, Authority source unchanged vs 03b9f46; "
          "Strategies still import /3", rc == "" and all("import sekine3310/ZoneEnginePractical/3 as zn" in
          open(os.path.join(ROOT, f), encoding="utf-8").read() for f in ("PracticalZoneStrategy_LONG.pine", "PracticalZoneStrategy_SHORT.pine")), rc)


# ============================================================================
# V4-MTF : ZoneVisualPractical MTF Authority (Engine Start Time)
# ============================================================================
V4_DIRECT_REV = "a251a0a"      # 5M /4 direct-path parity commit

TF_SEC = {"15S": 15, "30S": 30, "1": 60, "3": 180, "5": 300, "15": 900, "30": 1800, "60": 3600, "120": 7200,
          "240": 14400, "360": 21600, "720": 43200, "D": 86400, "W": 604800, "M": 2592000}


def _v4_market(n=4000):
    # 5M bars with session gaps (daily 1h break every 276 bars, a weekend-like 2-day break once)
    gaps = set()
    for d in range(0, 40):
        gaps |= set(range(d * 288 + 276, d * 288 + 288))
    gaps |= set(range(5 * 288, 7 * 288))
    t0 = 1_790_000_100 // 86400 * 86400
    return vm.five_min_bars(t0, n, gaps)


def _v4_run(tf, times, chart_start, start_t, **kw):
    sec = TF_SEC[tf]
    if sec == 300:
        g, fed = vm.simulate_direct(times, chart_start, start_t)
        calls = {}
        for f in fed:
            calls[f[1]] = calls.get(f[1], 0) + 1
        return g, fed, calls
    if sec < 300:
        return vm.simulate_lower(times, sec, chart_start, start_t, **kw)
    return vm.simulate_upper(times, sec, chart_start, start_t, **kw)


def fixture_v4_mtf():
    cur = VIS_CUR
    cc = code_only(cur)
    base = _git_show(V4_DIRECT_REV, "ZoneVisualPractical.pine")
    check("V4-MTF-00 current Visual == v4_mtf_transform(a251a0a) exactly (MTF = marked V4 blocks + 4 gate expressions)",
          bool(base) and v4_mtf_transform(base) == cur)
    check("V4-MTF-01 5M Parity kept: Parity Mode OFF partial evaluation == a251a0a exactly",
          bool(base) and v4_mtf_eval_off(cur) == base)
    # ---- feed pack ---------------------------------------------------------
    pk = cur[cur.index("f_authPack(int startT) =>\n"):]
    pk = pk[:pk.index("\n\n") + 1]
    check("V4-MTF-PACK f_authPack == mechanical transform of the 5M direct-path Source / Break / dayId code "
          "(gates dropped, comments dropped, timeframe.in_seconds() -> in_seconds(AUTH_TF); no formula change)",
          pk == vm.pine_auth_pack(vm.direct_segment(cur)))
    direct = vm.direct_segment(cur)
    req_d = re.findall(r"request\.security\(syminfo\.tickerid, (\w+),", direct)
    req_p = re.findall(r"request\.security\(syminfo\.tickerid, (\w+),", pk)
    check("V4-MTF-PACK2 pack Source requests == direct path (MA maTf / Swing hzTf1-3 / Accum accTf1-3 / Break breakTf), "
          "same lookahead_off", req_d == req_p == ["maTf", "hzTf1", "hzTf2", "hzTf3", "accTf1", "accTf2", "accTf3", "breakTf"]
          and pk.count("lookahead = barmerge.lookahead_off") == direct.count("lookahead = barmerge.lookahead_off") == 8, str(req_p))
    ret = re.findall(r"^    \[(.*)\]$", pk, re.M)[-1].split(", ")
    check("V4-MTF-PACK3 pack returns 36 primitives in ZoneFeed order (35 fields with barHigh/Low/Close/Time = 5M-context "
          "high/low/close/time, barIndex = start-relative 5M index) + startOk; no UDT crosses the request",
          ret == vm.PACK_RETURN and len(ret) == 36 and "zn.ZoneFeed" not in pk and ".new(" not in pk)
    prev = cur[cur.index("f_authPackPrev(int startT) =>\n"):]
    prev = prev[:prev.index("\n\n") + 1]
    check("V4-MTF-PACK4 f_authPackPrev = every pack element [1] (previous confirmed 5M bar), nothing else",
          prev == vm.pine_auth_pack_prev())
    # ---- nested-request static audit ----------------------------------------
    outer_s = re.findall(r"request\.security\(syminfo\.tickerid, AUTH_TF,\s*f_authPackPrev\(engineStartTime\), lookahead = barmerge\.lookahead_on\)", cur)
    outer_l = re.findall(r"request\.security_lower_tf\(syminfo\.tickerid, AUTH_TF,\s*f_authPack\(engineStartTime\)\)", cur)
    check("V4-MTF-NEST static: <5m = 1 request.security(AUTH_TF, f_authPackPrev, lookahead_on); >5m = 1 "
          "security_lower_tf(AUTH_TF, f_authPack); 8 nested Source requests inside the pack; dynamic_requests = true "
          "[PINE_COMPILE_REQUIRED: nested request / lower_tf nested request / 36-element tuple]",
          len(outer_s) == 1 and len(outer_l) == 1 and "dynamic_requests = true" in cur and len(req_p) == 8
          and 'string AUTH_TF    = "5"' in cur)
    check("V4-MTF-NEST2 no drawing / plot / alert / table inside the pack (drawing stays in main context)",
          not re.search(r"\b(box|label|line|table)\.new|plot\(|alert\(|zn\.update", pk + prev))
    # ---- engine purity / offset invariance (parity follows from identical feed sequences) ----------
    lib = open(L3_SRC_PATH, encoding="utf-8").read()
    funcs = _pine_functions(lib)
    reach = _reachable(funcs, "update")
    body = "\n".join(funcs[f_] for f_ in reach)
    check("V4-MTF-PURE zn.update reachable set has no ta.*, no [n] history, no chart built-in -> state is a pure "
          "fold over the fed 5M sequence (safe to call k times per chart bar in replay order)",
          not re.search(r"\bta\.", body) and not re.search(r"[\w)]\[[^\]]+\]", re.sub(r"array<\w+>|\[\]", "", body))
          and not re.search(r"(?<![\.\w])(high|low|close|open|time|bar_index|barstate)\b(?!\s*=)", body), str(sorted(reach))[:80])
    uses = re.findall(r"[^\n]*\b(createdBar|breakBar|lastSeenBar|matchedBar|lastTouchBar|nextTrackExpireBar)\b[^\n]*", body)
    check("V4-MTF-PURE2 Authority index consumers are only equality / differences / min (offset-invariant): "
          "start-relative index (MTF) and 5M bar_index (5M direct) give the same state",
          all(not re.search(r"\b(createdBar|breakBar|lastSeenBar|lastTouchBar)\b\s*[<>]=?\s*\d", l) for l in uses))
    # ---- MTF structure ------------------------------------------------------
    upd = cc[cc.index("if is5mChart and not useEngineStart"):cc.index("bool authDisplayOk")]
    check("V4-MTF-STRUCT =5m direct (OFF: unchanged / ON: f_authKey + guard), <5m security[1] + guard, "
          ">5m lower_tf replay i = 0..n-1 (oldest -> newest) + guard; every non-OFF zn.update behind f_authAccept",
          upd.count("zn.update(") == 4 and upd.count("f_authAccept(") == 3
          and "for i = 0 to nAuth - 1\n            if i < nAuth - 1 or barstate.isconfirmed\n                if f_authAccept(authG, array.get(l34, i), array.get(l35, i), array.get(l33, i))" in upd
          and "if f_authAccept(authG, s34, s35, s33)\n        zn.update(" in upd
          and "if f_authAccept(authG, d5Idx, d5Ok, time)" in upd and cc.count("zn.update(") == 4)
    feed_s = re.findall(r"(\w+) = (s\d+)", upd)
    feed_l = re.findall(r"(\w+) = array\.get\((l\d+), i\)", upd)
    check("V4-15 MTF ZoneFeed: every field from the 5M Authority pack element (barHigh/Low/Close/Time/Index = 5M-context "
          "high/low/close/time/start-relative index); no chart high/low/close/time/bar_index on <5m / >5m paths",
          feed_s == [(f, "s%d" % k) for k, f in enumerate(vm.FEED_FIELDS)]
          and feed_l == [(f, "l%d" % k) for k, f in enumerate(vm.FEED_FIELDS)]
          and not re.search(r"= (high|low|close|time|bar_index)\b", upd[upd.index("else if useEngineStart and chartTfSec < authTfSec"):]))
    check("V4-MTF-DRAW drawing / MA lines / Stats gated by authDisplayOk = (ON: guard status OK, OFF: is5mChart); "
          "drawOrder from /4 (Authority close), box width unchanged",
          "bool authDisplayOk = useEngineStart ? authG.status == 1 : is5mChart" in cc
          and "if barstate.islast and authDisplayOk\n    int nBox = 0" in cc
          and "if barstate.islast and authDisplayOk and showStats" in cc
          and cc.count("plot(authDisplayOk and showMaLines and useMaSource ?") == 2
          and "zn.drawOrder(zoneEng, zn.zoneCount(zoneEng))" in cc
          and "int xL = bar_index - zoneLeftBars" in cc and "int xR = bar_index + zoneRightBars" in cc)
    check("V4-MTF-INPUT only the 2 MTF inputs added (MTF Parity Mode default OFF, Engine Start Time); every other input / default unchanged",
          parse_inputs(base) == {k: v for k, v in parse_inputs(cur).items() if k not in ("useEngineStart", "engineStartTime")}
          and len(parse_inputs(cur)) == len(parse_inputs(base)) + 2 and "useEngineStart = input.bool(false," in cur)

    # ---- mirror: all TFs from the same Engine Start Time -------------------
    times = _v4_market()
    start_t = times[1500] - 120                       # first 5M bar >= start = times[1500]
    chart_start = times[0]
    ref_g, ref_fed, _ = _v4_run("5", times, chart_start, start_t)
    ref_state = vm.run_engine(ref_fed)
    tfs = ["15S", "30S", "1", "3", "5", "15", "30", "60", "120", "240", "360", "720", "D", "W", "M"]
    res = {tf: _v4_run(tf, times, chart_start, start_t) for tf in tfs}
    sup = [tf for tf in tfs if res[tf][0].status == vm.ST_OK]
    check("V4-MTF-START-01 every SUPPORTED TF: firstAuthorityTime == 5M firstAuthorityTime (= first 5M bar >= start), "
          "firstAuthorityIndex == 0",
          len(sup) == len(tfs) and all(res[tf][0].firstTime == ref_g.firstTime == times[1500] and res[tf][0].firstIdx == 0 for tf in sup),
          f"supported={sup}")
    n_ref = len(times) - 1500
    check("V4-MTF-START-02 processed 5M bar count identical on every SUPPORTED TF (<5m: through the last completed 5M bar)",
          all(res[tf][0].count == (n_ref - 1 if TF_SEC[tf] < 300 else n_ref) for tf in sup) and ref_g.count == n_ref,
          str({tf: res[tf][0].count for tf in sup}))
    check("V4-MTF-START-03 missing authority bar = 0 on every SUPPORTED TF", all(res[tf][0].missing == 0 for tf in sup))
    check("V4-MTF-START-04 duplicate zn.update = 0 (each authority index updated exactly once)",
          all(all(v == 1 for v in res[tf][2].values()) for tf in sup))
    check("V4-MTF-START-05 authority order identical (strictly +1 sequence, same times as 5M)",
          all([f[:2] for f in res[tf][1]] == [f[:2] for f in ref_fed[:len(res[tf][1])]] for tf in sup)
          and all(res[tf][0].inversion == 0 for tf in sup))
    same_cut = [tf for tf in sup if TF_SEC[tf] >= 300]
    check("V4-MTF-PARITY Zone state identical (count / top / bottom / score / strength / state / touch / srcMask / "
          "Break / Flip / Track / Lifetime): Engine = pure fold over identical feed sequences",
          all(vm.run_engine(res[tf][1]) == ref_state for tf in same_cut)
          and all(vm.run_engine(res[tf][1]) == vm.run_engine(ref_fed[:-1]) for tf in sup if TF_SEC[tf] < 300))
    for nid, name in (("V4-07", "Zone count"), ("V4-08", "top / bottom"), ("V4-09", "score / strength"),
                      ("V4-10", "state / touch"), ("V4-11", "Break / Flip"), ("V4-12", "srcMask"), ("V4-13", "Track / Lifetime")):
        check(f"{nid} {name} parity (confirmed 5M): follows V4-MTF-PURE + V4-MTF-START-05 + V4-MTF-PARITY",
              all(vm.run_engine(res[tf][1]) == ref_state for tf in same_cut))
    g1 = res["1"]
    check("V4-03 1M chart: each 5M Feed reported 5x but zn.update once (dupSkip > 0, duplicate update 0)",
          g1[0].dupSkip > 0 and all(v == 1 for v in g1[2].values()))
    for nid, tf, k in (("V4-04", "15", 3), ("V4-05", "60", 12), ("V4-06", "240", 48)):
        sec = TF_SEC[tf]
        bars = {}
        for f in res[tf][1]:
            bars.setdefault((f[0] - chart_start) // sec, []).append(f[0])
        full = [v for v in bars.values() if len(v) == k]
        check(f"{nid} {tf} chart: full chart bars replay {k} 5M bars oldest -> newest",
              len(full) > 0 and all(v == sorted(v) and v[-1] - v[0] == (k - 1) * 300 for v in full), f"full bars={len(full)}")
    check("V4-14 duplicate update = 0 on all TFs", all(all(v == 1 for v in res[tf][2].values()) for tf in tfs))

    # ---- realtime: unconfirmed 5M bar never processed on >5m -----------------
    gl, fl, _ = vm.simulate_upper(times, 3600, chart_start, start_t, live_last=True)
    check("V4-MTF-RT >5m realtime chart bar: the last (forming) 5M intrabar is not processed; parity holds through the "
          "latest confirmed 5M bar", gl.status == vm.ST_OK and fl == ref_fed[:len(fl)] and len(fl) == n_ref - 1)

    # ---- insufficient history: never start mid-way, hide zones -----------------
    late = times[1600]
    for tf in ("1", "5"):
        g, fed, _ = _v4_run(tf, times, late, start_t)
        check(f"V4-MTF-INSUFF-{tf} chart history starts after Engine Start -> INSUFFICIENT 5M HISTORY, Engine never "
              "starts (0 updates), zones hidden", g.status == vm.ST_INSUFF and fed == [] and g.count == 0)
    g, fed, _ = vm.simulate_upper(times, 3600, chart_start, start_t, intrabar_limit=2000)
    check("V4-MTF-INSUFF-LTF >5m intrabar limit does not reach Engine Start -> INSUFFICIENT, 0 updates (no thinning, "
          "no late start)", g.status == vm.ST_INSUFF and fed == [])
    g, fed, _ = _v4_run("15", times, chart_start, start_t, ctx_start=times[1500])
    check("V4-MTF-INSUFF-EDGE 5M context starts exactly at the start bar (cannot prove it is the first 5M bar >= start) "
          "-> INSUFFICIENT", g.status == vm.ST_INSUFF and fed == [])
    g, fed, _ = vm.simulate_upper(times, 3600, chart_start, times[-1] + 600)
    check("V4-MTF-INSUFF-WAIT Engine Start after the last 5M bar -> status 0 (no authority bar), zones hidden",
          g.status == vm.ST_WAIT and fed == [])
    # 3m chart: a 5M bar whose trades all fall in a 3m bar that opened in the previous 5M slot -> its predecessor is
    # never reported -> AUTHORITY GAP (detected, zones hidden; nothing approximated)
    tr = {times[1700]: [10, 40]}                      # 5M bar times[1700]: trades only at +10 s / +40 s
    tr.update({times[1699]: [0, 100, 200]})           # previous 5M bar: no trade after +200 s
    g, fed, _ = vm.simulate_lower(times, 180, chart_start, start_t, trades=tr)
    check("V4-MTF-GAP-3M missing 5M report on a sparse 3m chart -> AUTHORITY GAP: processing stops, zones hidden, "
          "missing counted (never skipped silently)",
          g.status == vm.ST_BROKEN and g.missing >= 1 and fed == ref_fed[:len(fed)], f"missing={g.missing}")
    # guard unit cases
    g = vm.Guard()
    seq = [(None, False, 1), (0, True, 2), (0, True, 2), (1, True, 3), (3, True, 5)]
    out = [vm.guard_accept(g, r, ok, t) for r, ok, t in seq]
    check("V4-MTF-GUARD guard: pre-start skip, start accept, repeat = dupSkip, +1 accept, jump = AUTHORITY GAP (no accept)",
          out == [False, True, False, True, False] and g.status == vm.ST_BROKEN and g.missing == 1 and g.dupSkip == 1)
    g = vm.Guard()
    out = [vm.guard_accept(g, r, ok, t) for r, ok, t in [(0, True, 1), (1, True, 2), (0, True, 1)]]
    check("V4-MTF-GUARD2 order inversion -> status 3, never re-processed", out == [True, True, False] and g.status == vm.ST_BROKEN and g.inversion == 1)
    # Pine guard text mirrors guard_accept
    ga = cur[cur.index("f_authAccept(AuthGuard g"):]
    ga = ga[:ga.index("\n    acc\n") + 8]
    check("V4-MTF-GUARD3 Pine f_authAccept branch structure == Python mirror (start: rel == 0 and startOk; repeat skip; "
          "+1 accept; inversion / jump -> status 3; first non-start -> status 2)",
          all(x in ga for x in ("if g.status <= 1 and not na(rel) and rel >= 0", "if rel == 0 and startOk",
                                 "g.status := 2", "else if rel == g.lastIdx\n            g.dupSkip := g.dupSkip + 1",
                                 "else if rel == g.lastIdx + 1\n            acc := true", "g.inversion := g.inversion + 1",
                                 "g.missing := g.missing + rel - g.lastIdx - 1")))
    fk = cur[cur.index("f_authKey(int startT) =>"):]
    check("V4-MTF-KEY f_authKey: index 0 = first 5M bar with time >= Engine Start; startOk = a 5M bar exists before it",
          "if na(startIdx) and time >= startT\n        startIdx := bar_index\n        startOk  := bar_index > 0" in fk)


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
    fixture_p08_static()
    fixture_p08_behaviour()
    fixture_p09_static()
    fixture_p09_behaviour()
    fixture_p10_static()
    fixture_p10_behaviour()
    fixture_p11_static()
    fixture_p11_behaviour()
    fixture_p12_static()
    fixture_p12_behaviour()
    fixture_p13a()
    fixture_p14_final_audit()
    fixture_p15()
    fixture_p16_visual_5m_gate()
    fixture_l3()
    fixture_v4_5m_direct()
    fixture_v4_mtf()
    width = max(len(n) for n, _, _ in RESULTS)
    fails = 0
    for name, ok, detail in RESULTS:
        fails += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {name.ljust(width)}  {detail}")
    print(f"\n{len(RESULTS) - fails}/{len(RESULTS)} passed  [PINE_NOT_VERIFIED: static / mirror checks]")
    raise SystemExit(1 if fails else 0)
