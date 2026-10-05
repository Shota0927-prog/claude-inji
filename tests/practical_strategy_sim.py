#!/usr/bin/env python3
"""
Practical Zone Strategy — structural fixtures (Python, NOT a Pine compile).

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


if __name__ == "__main__":
    fixture_types()
    fixture_factories()
    fixture_consume_preview()
    fixture_preview_lifecycle_shared()
    fixture_removed_dead()
    fixture_excluded()
    fixture_helpers()
    fixture_alloc()
    width = max(len(n) for n, _, _ in RESULTS)
    fails = 0
    for name, ok, detail in RESULTS:
        fails += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {name.ljust(width)}  {detail}")
    print(f"\n{len(RESULTS) - fails}/{len(RESULTS)} passed  [PINE_NOT_VERIFIED: static / mirror checks]")
    raise SystemExit(1 if fails else 0)
