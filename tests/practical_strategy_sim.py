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
    width = max(len(n) for n, _, _ in RESULTS)
    fails = 0
    for name, ok, detail in RESULTS:
        fails += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {name.ljust(width)}  {detail}")
    print(f"\n{len(RESULTS) - fails}/{len(RESULTS)} passed  [PINE_NOT_VERIFIED: static / mirror checks]")
    raise SystemExit(1 if fails else 0)
