"""AU-1 / AU-2 fixtures — the automation output copy automation/xau_short/pine/ZoneStrategyXAU_Auto.pine (tests/au_build.py).

  AP : static — the copy == au_build.build() and strips back to the normal Gold Short (XA-23) byte for byte; the normal Short,
       the Long, the Engines and every other Pine file unchanged; trading identical (every strategy.* call, every state
       assignment and every condition in the confirmed block, in order, only auTid added); TP / breakeven still on the confirmed
       5m bar; every decision point emits its event (17 calls); keys / tids deterministic from bar times, varip dedup recorded
       only when alert() is called; JSON ON suppresses only the copy's human-text alerts (OFF = the normal alerts)
  AJ : the Pine JSON builder f_auJson evaluated (Pine expression translated literally) -> valid JSON with exactly the receiver's
       fields, accepted by the receiver; the key formula of f_auEmit equals the receiver's
  AC : (AU-2) cfg coverage — every input of the source is in cfg except the display-only ones (listed with the reason and checked to
       be used only for drawing); the Pine cfg expressions evaluated with the defaults equal the sample's predicted cfg;
       cfg_fields.json in sync; JSON escaping of quotes / backslashes; prices with 8 decimals; BAR event every confirmed bar
  AM : mutations do not strip back

Evidence class: PINE_NOT_VERIFIED (TradingView compile and real alert delivery are not verified here).
"""
import json
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import au_build as ab            # noqa: E402
import xa_build as xb            # noqa: E402
import eu_sim as es              # noqa: E402

ROOT = ab.ROOT
sys.path.insert(0, os.path.join(ROOT, "automation", "xau_short", "receiver"))
import xau_receiver as xr        # noqa: E402

raw = lambda p: open(os.path.join(ROOT, p), encoding="utf-8").read()
code_only, func = es.code_only, es.func
A, N = raw(ab.AUTO_PATH), raw(ab.SRC_PATH)
RESULTS = []
MAIN_START, MAIN_END = "if is5mChart and barstate.isconfirmed\n    // (1)", "\nplot(stZones"


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


def block(t, start, end):
    i = t.index(start)
    return t[i:t.index(end, i)]


def gate_static():
    others = [p for p in os.listdir(ROOT) if p.endswith(".pine") and p != ab.SRC_PATH]
    check("AP-01 the copy == au_build.build() and strip gives the normal Gold Short byte for byte; the normal Short == xa_build.build_strategy() "
          "== the committed XA-23 file (7705907) unchanged; the Long, Engines and every other Pine file unchanged by AU-1",
          A == ab.build() and ab.strip(A) == N and N == xb.build_strategy() and N == ab.show(ab.SRC_REV, ab.SRC_PATH)
          and not [p for p in others if __import__("btl_build").unapply(p, raw(p)) != ab.show(ab.SRC_REV, p)])
    m, m0 = block(A, MAIN_START, MAIN_END), block(N, MAIN_START, MAIN_END)
    pick = lambda t: [l.strip() for l in code_only(t).split("\n")
                      if re.search(r"\bstrategy\.(entry|exit|close|cancel)\(|^\s*\w+\s*(:=|\+=)|^\s*(if|else|for)\b", l) and "auTid :=" not in l
                      and "f_auEmit(" not in l and not l.strip().startswith("if auBar")]
    added = [l.strip() for l in code_only(m).split("\n") if l.strip() and l.strip() not in [x.strip() for x in code_only(m0).split("\n")]]
    check("AP-02 trading identical: in the confirmed 5m block every strategy.entry / exit / close / cancel call, every state assignment and "
          "every if / else line is the same, in the same order; the only added lines are f_auEmit calls (18 in the file, incl. the BAR "
          "emit under `if auBar`) and the auTid assignments (3); strategy() settings apart from the name identical (calc_on_every_tick true, process_orders_on_close false)",
          pick(m) == pick(m0) and all(l.startswith(("f_auEmit(", "auTid :=", '"tv_state=')) or l.startswith("if auBar") for l in added)
          and code_only(A).count("f_auEmit(") == 19 and code_only(m).count("auTid :=") == 3
          and es.seg(A, "strategy(", "import ").replace("Zone Strategy XAU Auto", "Zone Strategy XAU").replace("ZONE-ST-AU", "ZONE-ST")
          == es.seg(N, "strategy(", "import "), str([l for l in added if not (l.startswith(("f_auEmit(", "auTid :=", '"tv_state=')) or l.startswith("if auBar"))]))
    after = {   # decision line -> the event emitted right after it (same block)
        "strategy.exit(oXid, oEid, stop = oSL)\n                    f_stConfAlert(pwSide": "ENTRY", "fillNow := true": "TV_FILL",
        "cancelBar := true": "CANCEL", "pwNBad += 1": "CLOSE_REQ", "pwEv        := why": "WAIT_END",
        "oStop := oFill\n            strategy.exit(oXid, oEid, stop = oStop, limit = oTP)": "BE_MOVE"}
    cov = {e: e in m for e in after.values()}
    em = re.findall(r'f_auEmit\("(\w+)"', code_only(A))
    check("AP-03 every decision point emits its event: ENTRY in the three strategy.entry branches (SATS pull / SATS immediate / Current), "
          "CANCEL at both strategy.cancel pairs, CLOSE_REQ at the three strategy.close calls, TP_SET at both post-fill TP exits, BE_MOVE at "
          "the breakeven exit, TV_FILL / TV_CLOSED / TV_FLAT at the virtual fill / in-bar close / flat, WAIT_START / WAIT_END at the SATS "
          "prep / expiry-SL0, PROV at the provisional send, BAR at the end of every confirmed 5m bar; TP_SET / BE_MOVE inside the confirmed 5m block (no tick-time change)",
          sorted(em) == sorted(["ENTRY"] * 3 + ["CANCEL"] * 2 + ["CLOSE_REQ"] * 3 + ["TP_SET"] * 2 + ["BE_MOVE", "TV_FILL", "TV_CLOSED",
                                                                                                     "TV_FLAT", "WAIT_START", "WAIT_END", "PROV", "BAR"])
          and m.index('f_auEmit("BAR"') > m.index("    stTpDnPrev := tpDn")
          and all(cov.values()) and m.count('f_auEmit("TP_SET"') == 2 and m.count('f_auEmit("BE_MOVE"') == 1
          and code_only(m).count("strategy.cancel(oEid)") == 2 and code_only(m).count("strategy.close(oEid)") == 3, str(sorted(em)))
    fe = func(A, "f_auEmit(string ev, string tid, int rank, int side, string ot, float px, float sl, float tp, string info) =>")
    check("AP-04 idempotency: key = SID|ev|tid|bar_close (time_close of the event bar, no counter); tid = \"T\" + the ENTRY decision bar's "
          "close time (later events of the trade reuse auTid, a var set only in the ENTRY branches), \"W\" + the SATS prep bar close (pwEndT), "
          "\"P\" + the provisional bar open; varip key list, appended only in the branch that calls alert(), at most %d" % ab.KEEP,
          '    string key  = AU_SID + "|" + ev + "|" + tid + "|" + str.tostring(time_close)\n' in fe
          and "    bool   send = auJson and not array.includes(auSent, key)\n" in fe
          and fe.index("array.push(auSent, key)") > fe.index("    if send\n") and fe.index("array.push(auSent, key)") < fe.index("alert(f_auJson(")
          and "varip array<string> auSent = array.new_string()" in A and 'var string auTid = ""' in A
          and A.count('auTid := "T" + str.tostring(time_close)') == 3 and '"W" + str.tostring(pwEndT)' in A and '"W" + str.tostring(time_close)' in A
          and '"P" + str.tostring(time)' in A and "        if array.size(auSent) > %d\n" % ab.KEEP in fe)
    check("AP-05 human-text alerts of the copy only when JSON output is OFF (confirmed: inside f_stConfAlert; provisional: the same gate / "
          "dedup, JSON PROV or text); input '自動化 JSON 出力' default ON; labels and every other input unchanged",
          '        if not auJson     // AU:' in A and "    if auJson     // AU:" in A and len(re.findall(r"^\s*alert\(", code_only(A), re.M)) == 3
          and {k: v for k, v in es.input_values(A).items() if k not in ("auJson", "auBar")} == es.input_values(N)
          and es.input_values(A)["auJson"] == "true" and es.input_values(A)["auBar"] == "true")


def pine_json(env):
    """evaluate the delivered f_auJson body (a Pine string expression) literally in Python."""
    body = func(A, "f_auJson(string ev, string tid, int rank, int side, string ot, float px, float sl, float tp, string info, string key) =>")
    expr = body.split("=>\n", 1)[1]
    expr = expr.replace('(side == 1 ? "LONG" : side == -1 ? "SHORT" : "")', '("LONG" if side == 1 else "SHORT" if side == -1 else "")')
    expr = expr.replace("syminfo.tickerid", "SYM").replace("timeframe.period", "TF").replace("str.tostring", "tostr")
    expr = re.sub(r"\b(open|high|low|close)\b", lambda x: x.group(1).upper(), expr)
    expr = " ".join(x.strip() for x in expr.split("\n") if x.strip())
    return eval(expr, {}, env)


def gate_json():
    num = lambda v: "null" if v is None else (f"{v:.8f}".rstrip("0").rstrip(".") or "0")
    esc = lambda s: s.replace("\\", "\\\\").replace('"', '\\"')
    tostr = lambda v: str(v)
    cfg = "dir=Short Only;mode=C: Candle Pattern;tim=SATS Pullback"
    bo, bc = 1793063700000, 1793064000000
    key = f"{ab.SID}|ENTRY|T{bc}|{bc}"
    env = dict(AU_SCHEMA=ab.SCHEMA, AU_SID=ab.SID, auCfg=esc(cfg), ev="ENTRY", tid=f"T{bc}", rank=10, side=-1, ot="MARKET", px=2651.8,
               sl=2656.75, tp=2640.5, info="SATS_NOW", key=key, SYM="OANDA:XAUUSD", TF="5", time=bo, time_close=bc, timenow=bc + 900,
               tostr=tostr, f_auNum=num, f_auEsc=esc, OPEN=2652.2, HIGH=2653.0, LOW=2650.9, CLOSE=2651.8)
    s = pine_json(env)
    msg = json.loads(s)
    weird = dict(env, info='SATS_NOW;note="q"\\b', px=2651.123456789, auCfg=esc('c2|a"b\\c'))
    w = json.loads(pine_json(weird))
    check("AJ-01 the delivered f_auJson expression (evaluated literally) gives valid JSON whose fields are exactly the receiver's REQUIRED "
          "fields in order (incl. the bar OHLC), with the bar times / side / prices / key; a quote / backslash in info or cfg stays valid JSON "
          "and decodes back exactly (f_auEsc); prices carry 8 decimals",
          list(msg) == list(xr.REQUIRED) and msg["side"] == "SHORT" and msg["bar_close"] == bc and msg["px"] == 2651.8 and msg["key"] == key
          and msg["tp"] == 2640.5 and (msg["o"], msg["h"], msg["l"], msg["c"]) == (2652.2, 2653.0, 2650.9, 2651.8)
          and w["info"] == 'SATS_NOW;note="q"\\b' and w["cfg"] == 'c2|a"b\\c' and w["px"] == 2651.12345679, s)
    with tempfile.TemporaryDirectory() as d:
        r = xr.Receiver(xr.load_config(None) | {"data_dir": d}, log=None)
        r.log = __import__("logging").getLogger("au_sim_silent")
        res = r.process(s, source="test")
        dup = r.process(s, source="test")
    check("AJ-02 the receiver accepts the Pine-built ENTRY (key = SID|ev|tid|bar_close checked) and marks the same message again DUPLICATE",
          res["status"] == "ACCEPTED" and dup["status"] == "DUPLICATE", str((res, dup)))


def gate_cfg():
    fields = ab.cfg_fields()
    names = list(es.input_decls(N))
    inc = [f["name"] for f in fields if f["included"]]
    cfg_lines = re.findall(r"^string auCfg\d+ = (.*)$", A, re.M)
    refs = [x for line in cfg_lines for x in re.findall(r"\b([a-zA-Z_]\w*)\b", line) if x in names]
    disp_ok = {}
    for nm in ab.EXCLUDED:
        uses = [l.strip() for l in code_only(N).split("\n") if re.search(r"\b" + nm + r"\b", l) and not l.startswith(nm + " =")]
        disp_ok[nm] = bool(uses) and all(u.startswith("plot(") or u == "bool mk = stLblConf and array.get(stLblEid, 0) != oEid" for u in uses)
    check("AC-01 cfg covers every input of the Gold Short (%d) except the display-only ones %s (each with its reason, and used only to draw: "
          "plot / the label switch); each included input appears exactly once in the Pine cfg expressions, in declaration order; "
          "cfg_fields.json in the repository == au_build.cfg_fields_json()" % (len(names), sorted(ab.EXCLUDED)),
          [f["name"] for f in fields] == names and set(names) - set(inc) == set(ab.EXCLUDED) and refs == inc and all(disp_ok.values())
          and open(os.path.join(ROOT, ab.CFG_FIELDS_PATH), encoding="utf-8").read() == ab.cfg_fields_json(), str((disp_ok, len(refs), len(inc))))
    vals = es.input_values(N)

    def py(v, ty):
        if ty == "bool":
            return v == "true"
        if ty == "int":
            return int(v)
        if ty == "float":
            return float(v)
        return v[1:-1]
    env = {f["name"]: py(vals[f["name"]], f["type"]) for f in fields}
    fmt10 = lambda v: f"{v:.10f}".rstrip("0").rstrip(".") or "0"
    parts = []
    for line in cfg_lines:
        e = re.sub(r'str\.tostring\((\w+), "#\.##########"\)', r"fmt10(\1)", line)
        e = re.sub(r"str\.tostring\((\w+)\)", r"str(\1)", e)
        e = re.sub(r'\((\w+) \? "1" : "0"\)', r'("1" if \1 else "0")', e)
        parts.append(eval(e, {"fmt10": fmt10}, env))
    raw = ab.CFG_VERSION + "|" + "|".join(parts)
    sys.path.insert(0, os.path.join(ROOT, "automation", "xau_short", "receiver", "samples"))
    import make_samples as mks
    check("AC-02 the Pine cfg expressions evaluated with the default inputs give the cfg the samples predict (make_samples.predicted_cfg, "
          "float formatting '#.##########' assumed = up to 10 decimals without trailing zeros; to be confirmed on TradingView)",
          raw.replace("\\", "\\\\").replace('"', '\\"') == mks.predicted_cfg() and raw.count("|") == len(inc), raw[:200])


def gate_mutation():
    muts = [A.replace("                    strategy.entry(oEid, pwSide == 1 ? strategy.long : strategy.short, qty = q)\n",
                      "                    strategy.entry(oEid, pwSide == 1 ? strategy.long : strategy.short, qty = q * 2)\n"),
            A.replace('    string key  = AU_SID + "|" + ev + "|" + tid + "|" + str.tostring(time_close)\n',
                      '    string key  = AU_SID + "|" + ev + "|" + str.tostring(bar_index)\n'),
            A.replace("varip array<string> auSent", "var array<string> auSent"),
            A.replace("        if not auJson     // AU:", "        if true     // AU:")]
    check("AM-01 mutations (a trading line, a bar_index key, a var key list, human alerts always on) do not strip back to the normal Short",
          all(x != A and ab.strip(x) != N for x in muts))


def main():
    for g in (gate_static, gate_json, gate_cfg, gate_mutation):
        try:
            g()
        except Exception:
            import traceback
            check(f"{g.__name__} completed without error", False, traceback.format_exc()[-900:])
    fails = 0
    for nm, ok, d in RESULTS:
        fails += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {nm[:150].ljust(150)}  {'' if ok else d}")
    print(f"\n{len(RESULTS) - fails}/{len(RESULTS)} passed  [PINE_NOT_VERIFIED: exact build / static / Pine JSON expression evaluated]")
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
