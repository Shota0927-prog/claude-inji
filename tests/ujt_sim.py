"""UJ-4 fixtures — ZoneStrategyUSDJPY TP / RR in the provisional / confirmed labels and alert texts.

  UT : static — Strategy == uj_build.build_strategy(); strip_strategy4 gives the UJ-3 Strategy (ab9820f) byte for byte;
       the code delta is only the TP / RR lines of f_stAlertMsg, the 5th argument at the four call sites, the tp returned
       by f_stProvEval (= the tpRef of its existing f_stTp call) and its provisional variable; risk / RR / TP format the
       GBPJPY expressions; f_stProvEval now equals the GBPJPY one; f_stTp / f_stQty / f_stNearest, every strategy.* call,
       alert / label conditions, the provisional dedup and the SL distance unchanged; only the USDJPY Strategy and its
       generator / fixtures change (ujl_sim / uj3_adapt by exactly recorded edits)
  UM : models — a port of f_stTp + the text: LONG / SHORT, fixed RR 1.5, opposite-zone TP (zone / fixed above Max / skip
       below Min / no zone), Entry A (limit) and B / C / D (close) references, RR formatting, invalid values
  UU : mutations — mirror and source mutations are caught
  UC : UJ-5 — the confirmed alert at most once per 5M bar: Strategy == build_strategy(); strip_strategy5 gives 89bc82b
       byte for byte; delta only the varip bar key and the alert guard; order / label / freq_all / provisional unchanged;
       a model of realtime execution (var rollback, varip kept, alert side effects kept): a repeated confirmed update of
       the same bar sent 2 alerts before and 1 now, entries on different bars all alert, the provisional alert of the
       same bar does not suppress it, history sends nothing
  (UT / UM / UU run on the UJ-4 layer: the working-tree file with exactly the UJ-5 edits reverted == 89bc82b)

Evidence class: PINE_NOT_VERIFIED (TradingView compile, realtime alerts and label rendering are external).
"""
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import uj_build as ub            # noqa: E402
import eu_sim as es              # noqa: E402
import fvg_re10045_sim as fr     # noqa: E402

ROOT = ub.ROOT
UJ3 = "ab9820f"
rd = lambda p: __import__("sx_build").unapply(p, open(os.path.join(ROOT, p), encoding="utf-8").read())   # SX-1 reverted (pinned in sxs_sim)
git = lambda *a: subprocess.run(["git", "-C", ROOT] + list(a), capture_output=True, text=True).stdout
code_only, func = es.code_only, es.func
S5 = rd(ub.STR_PATH)                                  # working-tree file (UJ-5 dedup pinned by the UC checks below)
S = ub.strip_strategy5(S5) or ""                      # UJ-4 layer (UJ-5 reverted exactly) == 89bc82b
S3 = git("show", f"{UJ3}:{ub.STR_PATH}")
UJ4 = "89bc82b"
GBS = rd("ZoneStrategyGBPJPY.pine")
MSG = "f_stAlertMsg(string kind, int side, float ePx, float sl, float tp) =>"
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


def block(t, start, end):
    i = t.index(start)
    return t[i:t.index(end, i)]


# exact UJ-4 edits to the UJ-3 fixtures (generated from the diff against ab9820f)
UJ4_TEST_EDITS = {'tests/uj3_adapt.py (code before ADAPT)': [('"""UJ-3 adaptation record — the exact edits UJ-3 (USDJPY Strategy '
                                             'labels / SL distance) made to older generators / fixtures.\n'
                                             '\n',
                                             '"""UJ-3 / UJ-4 adaptation record — the exact edits UJ-3 (USDJPY labels '
                                             '/ SL distance) and UJ-4 (TP / RR display) made to\n'
                                             'older generators / fixtures.\n'
                                             '\n'),
                                            ('since <rev>" checks accept these files only when they differ by '
                                             'exactly these edits. pine_ok() accepts the USDJPY Strategy\n'
                                             'only when stripping UJ-3 gives the file of the given revision byte for '
                                             'byte. This file and tests/ujl_sim.py are new in UJ-3.\n'
                                             '"""\n',
                                             'since <rev>" checks accept these files only when they differ by '
                                             'exactly these edits. pine_ok() accepts the USDJPY Strategy\n'
                                             'only when stripping UJ-4 / UJ-3 gives the file of the given revision '
                                             'byte for byte. This file and tests/ujl_sim.py are new\n'
                                             'in UJ-3, tests/ujt_sim.py in UJ-4.\n'
                                             '"""\n'),
                                            ('ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))\n'
                                             'NEW_FILES = ("tests/uj3_adapt.py", "tests/ujl_sim.py")\n'
                                             '_rd = lambda p: open(os.path.join(ROOT, p), encoding="utf-8").read()\n',
                                             'ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))\n'
                                             'NEW_FILES = ("tests/uj3_adapt.py", "tests/ujl_sim.py", '
                                             '"tests/ujt_sim.py")\n'
                                             '_rd = lambda p: open(os.path.join(ROOT, p), '
                                             'encoding="utf-8").read()\n'),
                                            ('def pine_ok(path, rev):\n'
                                             '    """True for the USDJPY Strategy when it differs from `rev` exactly '
                                             'by the UJ-3 layer."""\n'
                                             '    import uj_build as ub\n',
                                             'def pine_ok(path, rev):\n'
                                             '    """True for the USDJPY Strategy when it differs from `rev` exactly '
                                             'by the UJ-3 (+ UJ-4) layer."""\n'
                                             '    import uj_build as ub\n')],
 'tests/ujl_sim.py': [('code_only, input_decls, input_values, func = es.code_only, es.input_decls, es.input_values, '
                       'es.func\n'
                       'S, S0 = rd(ub.STR_PATH), git("show", f"{UJ2}:{ub.STR_PATH}")\n'
                       'GBS = rd("ZoneStrategyGBPJPY.pine")\n',
                       'code_only, input_decls, input_values, func = es.code_only, es.input_decls, es.input_values, '
                       'es.func\n'
                       'S4 = rd(ub.STR_PATH)\n'
                       'S = ub.strip_strategy4(S4) or ""     # UJ-3 layer (UJ-4 TP / RR reverted exactly; pinned in '
                       'ujt_sim)\n'
                       'S0 = git("show", f"{UJ2}:{ub.STR_PATH}")\n'
                       'GBS = rd("ZoneStrategyGBPJPY.pine")\n'),
                      ('          "e1c3cea byte for byte; the full chain strips to 3568c05; edit kinds header / '
                       'label / msg only",\n'
                       '          ub.build_strategy() == S and ub.strip_strategy3(S) == S0 and ub.build_strategy2() '
                       '== S0\n'
                       '          and ub.strip_strategy(S) == ub.base(ub.STR_PATH)\n'
                       '          and {k for k, _, _ in ub.STRATEGY_EDITS3} == {"header", "label", "msg"})\n',
                       '          "e1c3cea byte for byte; the full chain strips to 3568c05; edit kinds header / '
                       'label / msg only",\n'
                       '          ub.build_strategy3() == S and ub.strip_strategy3(S) == S0 and ub.build_strategy2() '
                       '== S0\n'
                       '          and ub.strip_strategy(S4) == ub.base(ub.STR_PATH) and ub.strip_strategy3(S4) == '
                       'S0\n'
                       '          and {k for k, _, _ in ub.STRATEGY_EDITS3} == {"header", "label", "msg"})\n'),
                      ('    allowed = {ub.STR_PATH, "tests/uj_build.py", "tests/uj_sim.py", "tests/ujl_sim.py", '
                       '"tests/uj3_adapt.py", "tests/bte_sim.py",\n'
                       '               "tests/xa_sim.py", "tests/xae_sim.py", "tests/xa_build.py"}\n'
                       '    others = [p for p in os.listdir(ROOT) if p.endswith(".pine") and p != ub.STR_PATH]\n',
                       '    allowed = {ub.STR_PATH, "tests/uj_build.py", "tests/uj_sim.py", "tests/ujl_sim.py", '
                       '"tests/uj3_adapt.py", "tests/bte_sim.py",\n'
                       '               "tests/xa_sim.py", "tests/xae_sim.py", "tests/xa_build.py", '
                       '"tests/ujt_sim.py"}\n'
                       '    others = [p for p in os.listdir(ROOT) if p.endswith(".pine") and p != ub.STR_PATH]\n')]}


def gate_static():
    check("UT-01 Strategy == uj_build.build_strategy() (UJ-1 .. UJ-4); strip_strategy4 gives the UJ-3 Strategy of ab9820f byte "
          "for byte; strip_strategy3 still gives e1c3cea; edit kinds header / msg / prov / conf / label",
          ub.build_strategy4() == S and ub.strip_strategy4(S) == S3 and ub.build_strategy3() == S3
          and ub.strip_strategy3(S) == git("show", f"e1c3cea:{ub.STR_PATH}") and ub.strip_strategy(S5) == ub.base(ub.STR_PATH)
          and ub.strip_strategy4(S5) == S3
          and {k for k, _, _ in ub.STRATEGY_EDITS4} == {"header", "msg", "prov", "conf", "label"})
    removed = sorted(["f_stAlertMsg(string kind, int side, float ePx, float sl) =>",
                      '(kind == "仮" ? "\\n※未確定: 5分足の確定時に不成立になる場合あり" : "\\nTP: 約定確認後に設定")',
                      "[side, ePx, sl]", 'alert(f_stAlertMsg("確定", side, stModeA ? oL : close, oSL), alert.freq_all)',
                      'array.push(stConfLbls, label.new(bar_index, side == 1 ? low : high, f_stAlertMsg("確定", side, stModeA ? oL : close, oSL),',
                      "[s0, e0, l0] = f_stProvEval()", 'alert(f_stAlertMsg("仮", pSide, pPx, pSL), alert.freq_once_per_bar)',
                      'label.set_text(stProvLbl, f_stAlertMsg("仮", pSide, pPx, pSL))',
                      'tooltip = "仮アラートと同じ判定・値。成立中は Entry / SL / SL距離を更新し、不成立・確定時は消す。過去足には出さない。")'])
    ch = es.changed_code(S3, S)
    got = [l for l in removed if l in ch]
    added = list(ch)
    for l in removed:
        if l in added:
            added.remove(l)
    exp_added = sorted([MSG, "float risk   = side == 1 ? ePx - sl : sl - ePx", "bool  okR    = not na(risk) and risk > 0",
                        "float rr     = okR and not na(tp) ? (side == 1 ? tp - ePx : ePx - tp) / risk : na",
                        '"\\nTP: " + (okR ? f_num(tp, "#.000") : "-") + (kind == "仮" ? "" : " (発注時の予定値。最終 TP は約定確認後に実約定価格から設定)") +',
                        '"\\nRR: " + (na(rr) ? "-" : "1:" + str.tostring(rr, "0.##")) +',
                        '(kind == "仮" ? "\\n※未確定: 5分足の確定時に不成立になる場合あり" : "")',
                        "float tpP = na     // 通知 TP: 下の RR 事前判定と同じ f_stTp の結果", "tpP := tpRef", "[side, ePx, sl, tpP]",
                        'alert(f_stAlertMsg("確定", side, stModeA ? oL : close, oSL, tpRef), alert.freq_all)',
                        'array.push(stConfLbls, label.new(bar_index, side == 1 ? low : high, f_stAlertMsg("確定", side, stModeA ? oL : close, oSL, tpRef),',
                        "float pTP      = na", "[s0, e0, l0, t0] = f_stProvEval()", "pTP   := t0",
                        'alert(f_stAlertMsg("仮", pSide, pPx, pSL, pTP), alert.freq_once_per_bar)',
                        'label.set_text(stProvLbl, f_stAlertMsg("仮", pSide, pPx, pSL, pTP))',
                        'tooltip = "仮アラートと同じ判定・値。成立中は Entry / SL / SL距離 / TP / RR を更新し、不成立・確定時は消す。過去足には出さない。")'])
    check("UT-02 code delta vs ab9820f exactly: TP / RR lines of f_stAlertMsg (+ tp argument, the old 'TP: 約定確認後に設定' tail "
          "becomes the TP line with the planned-value note), tp passed at the 2 confirmed and 2 provisional call sites, tpP "
          "returned by f_stProvEval, pTP, the label tooltip", got == removed and sorted(a for a in added if a) == exp_added,
          str(([l for l in removed if l not in got], [a for a in added if a and a not in exp_added][:3])))
    gm = func(GBS, "f_stAlertMsg(string kind, int side, float ePx, float sl, float tp) =>")
    um = func(S, MSG)
    norm = lambda s: re.sub(r"\s+", " ", s.strip())
    check("UT-03 GBPJPY method: risk / okR / rr expressions identical to the GBPJPY f_stAlertMsg; RR '1:' + format 0.## (the "
          "GBPJPY / EURUSD / GBPUSD format); TP '-' when risk <= 0; order Entry -> SL -> SL距離 -> TP -> RR; f_stProvEval "
          "now identical to the GBPJPY one; the confirmed calls pass tpRef like GBPJPY",
          all(norm(x) in norm(gm) for x in ("float risk = side == 1 ? ePx - sl : sl - ePx", "bool okR = not na(risk) and risk > 0",
                                             "float rr = okR and not na(tp) ? (side == 1 ? tp - ePx : ePx - tp) / risk : na"))
          and all(norm(x) in norm(um) for x in ("float risk = side == 1 ? ePx - sl : sl - ePx", "bool okR = not na(risk) and risk > 0",
                                                 "float rr = okR and not na(tp) ? (side == 1 ? tp - ePx : ePx - tp) / risk : na"))
          and '"1:" + str.tostring(rr, "0.##")' in gm and '"1:" + str.tostring(rr, "0.##")' in um
          and um.index('"\\nSL: "') < um.index('"\\nSL距離: "') < um.index('"\\nTP: "') < um.index('"\\nRR: "')
          and func(S, "f_stProvEval() =>") == func(GBS, "f_stProvEval() =>")
          and 'f_stAlertMsg("確定", side, stModeA ? oL : close, oSL, tpRef)' in S
          and 'f_stAlertMsg("確定", side, stModeA ? oL : close, oSL, tpRef)' in GBS)
    keep = ("f_stTp(", "f_stQty(int side, float ref, float sl) =>", "f_stNearest(")
    strat = lambda t: sorted(re.findall(r"strategy\.(?:entry|exit|close|cancel)\(.*$", code_only(t), re.M))
    req = lambda t: re.findall(r"request\.\w+\(", code_only(t))
    pv = lambda t: [l.replace("[side, ePx, sl, tpP]", "[side, ePx, sl]") for l in code_only(func(t, "f_stProvEval() =>")).split("\n")
                    if not re.match(r"^\s*(float tpP = na|tpP := tpRef)", l)]
    al = lambda t: [re.sub(r", (tpRef|pTP)\)", ")", l.strip()) for l in re.findall(r"^\s*alert\(.*$", t, re.M)]
    check("UT-04 logic unchanged: f_stTp / f_stQty / f_stNearest identical; f_stProvEval identical apart from the tpP lines "
          "(side / Entry / SL / skip unchanged); every strategy.* call identical; the two alert() calls identical apart from the "
          "tp argument (same conditions / frequencies); provisional gate / dedup / label conditions and confirmed label "
          "condition / keep limit identical; SL distance line kept; requests unchanged",
          all(func(S, h) == func(S3, h) for h in keep) and pv(S) == pv(S3) and strat(S) == strat(S3) and al(S) == al(S3)
          and req(S) == req(S3) and all(x in S for x in (
              "bool  stPvGate = is5mChart and not barstate.isconfirmed and oState == 0 and stSessOK",
              "bool  stPvA    = stAlertProv and stPvGate and (na(stProvBar) or stProvBar != bar_index)",
              "bool  stPvL    = stLblProv and stPvGate", "bool  stPvOK   = pSide != 0\n", "if barstate.isrealtime\n    if stPvL and stPvOK\n",
              "                if stLblConf     // 確定ラベル", "                    if array.size(stConfLbls) > stLblKeep\n",
              '"\\nSL距離: " + (na(slPips) ? "-" : str.tostring(slPips, "0.0") + " pips") +'))
          and all(fr.lint_eager_guards(code_only(t)) == [] for t in (S,)))
    mod = set(git("diff", "--name-only", UJ3, "--").split()) | {l[3:] for l in git("status", "--porcelain").split("\n") if l.startswith("??")}
    mod -= {"tests/__pycache__/"}
    mod = {m for m in mod if not __import__("cad_adapt").ok(m, UJ3) and not __import__("xal_build").ok(m) and not __import__("acc_build").ok(m)}     # CAD-1 / XL-1: exact
    recs_ok = []
    for key, pairs in UJ4_TEST_EDITS.items():
        path = key.split(" ")[0]
        old, new = git("show", f"{UJ3}:{path}"), __import__("cad_adapt").unadapt(path, rd(path))   # CAD-1 edits reverted first
        if "(code before ADAPT)" in key:
            old, new = old[:old.index("\nADAPT = ")], new[:new.index("\nADAPT = ")]
        s = old
        for a, b in pairs:
            s = s.replace(a, b) if s.count(a) == 1 else None
            if s is None:
                break
        recs_ok.append(s == new)
    others = [p for p in os.listdir(ROOT) if p.endswith(".pine") and not __import__("acc_build").ok(p) and p != ub.STR_PATH and not __import__("xal_build").ok(p)]
    check("UT-05 vs ab9820f only the USDJPY Strategy, uj_build, uj3_adapt (record regenerated; code part by exactly the recorded "
          "edits), ujl_sim (exactly the recorded edits: runs on the UJ-3 layer) and this new fixture change; every other Pine "
          "file byte-identical", mod <= {ub.STR_PATH, "tests/uj_build.py", "tests/uj3_adapt.py", "tests/ujl_sim.py", "tests/ujt_sim.py"}
          and ub.STR_PATH in mod and all(recs_ok) and not [p for p in others if rd(p) != git("show", f"{UJ3}:{p}") and not __import__("cad_adapt").ok(p, UJ3)],
          str((sorted(mod), recs_ok)))
    hdr = S[:S.index("//@version=5")]
    check("UT-06 header names UJ-4 as display / notification only and the confirmed TP as the planned value",
          "UJ-4 (表示・通知のみ)" in hdr and "確定の TP は\n//  発注時の予定値 (最終 TP は約定確認後に実約定価格から設定)" in hdr)


# ---- models ------------------------------------------------------------------------------------------------------------
def f_tp(side, px, sl, edge, rr=1.5, tpzone=False, mn=1.0, mx=3.0):
    """port of f_stTp: [skip, tp]."""
    risk = side * (px - sl)
    tp = px + side * rr * risk
    skip = False
    if tpzone and edge is not None:
        rrz = side * (edge - px) / risk
        if rrz < mn:
            skip = True
        elif rrz < mx:
            tp = edge
    return skip, tp


def fmt_rr(v):
    s = f"{round(v + 1e-12, 2):.2f}".rstrip("0").rstrip(".")
    return s


def text_tp_rr(kind, side, e, sl, tp):
    """port of the TP / RR lines of the USDJPY f_stAlertMsg."""
    risk = None if e is None or sl is None else (e - sl if side == 1 else sl - e)
    ok = risk is not None and risk > 0
    rr = (tp - e if side == 1 else e - tp) / risk if ok and tp is not None else None
    tpl = "TP: " + (f"{tp:.3f}" if ok and tp is not None else "-") + ("" if kind == "仮" else " (発注時の予定値。最終 TP は約定確認後に実約定価格から設定)")
    return tpl, "RR: " + ("-" if rr is None else "1:" + fmt_rr(rr))


def gate_model():
    s, tp = f_tp(1, 150.250, 150.000, None)
    s2, tp2 = f_tp(-1, 150.000, 150.250, None)
    check("UM-01 fixed RR 1.5: LONG Entry 150.250 / SL 150.000 (25.0 pips) -> TP 150.625, RR 1:1.5; SHORT Entry 150.000 / "
          "SL 150.250 -> TP 149.625, RR 1:1.5",
          not s and abs(tp - 150.625) < 1e-9 and text_tp_rr("確定", 1, 150.250, 150.000, tp)[1] == "RR: 1:1.5"
          and text_tp_rr("仮", 1, 150.250, 150.000, tp)[0] == "TP: 150.625"
          and not s2 and abs(tp2 - 149.625) < 1e-9 and text_tp_rr("仮", -1, 150.000, 150.250, tp2) == ("TP: 149.625", "RR: 1:1.5"))
    z = [f_tp(1, 150.250, 150.000, 150.700, tpzone=True), f_tp(-1, 150.000, 150.250, 149.550, tpzone=True),
         f_tp(1, 150.250, 150.000, 151.250, tpzone=True), f_tp(1, 150.250, 150.000, 150.400, tpzone=True),
         f_tp(1, 150.250, 150.000, None, tpzone=True)]
    check("UM-02 opposite-zone TP ON (Min 1.0 / Max 3.0): LONG edge 150.700 (RR 1.8) -> TP = the zone, RR 1:1.8; SHORT edge "
          "149.550 -> TP 149.550, RR 1:1.8; edge at RR 4.0 (>= Max) -> fixed 1.5; edge at RR 0.6 (< Min) -> skip (no order / "
          "alert, as before); no zone -> fixed",
          abs(z[0][1] - 150.700) < 1e-9 and text_tp_rr("確定", 1, 150.250, 150.000, z[0][1])[1] == "RR: 1:1.8"
          and abs(z[1][1] - 149.550) < 1e-9 and text_tp_rr("確定", -1, 150.000, 150.250, z[1][1])[1] == "RR: 1:1.8"
          and abs(z[2][1] - 150.625) < 1e-9 and z[3][0] is True and abs(z[4][1] - 150.625) < 1e-9)
    tA = f_tp(1, 150.180, 150.030, None)[1]
    check("UM-03 Entry A uses the limit price as the reference (provisional: bpL / bpS, confirmed: oL), B / C / D the "
          "confirmed / forming close; the TP / RR follow that reference: A limit 150.180, SL 150.030 -> TP 150.405, RR 1:1.5 "
          "(read from the Pine source for the references)",
          abs(tA - 150.405) < 1e-9 and "ePx := stModeA ? (side == 1 ? bpL : bpS) : close" in func(S, "f_stProvEval() =>")
          and "float  ref = stModeA ? pL : close" in S and "stModeA ? oL : close, oSL, tpRef" in S)
    check("UM-04 invalid values: SL on the wrong side or Entry na -> TP '-' and RR '-'; TP na -> RR '-'; RR rounding 1:1.33 / "
          "1:2 / 1:1.25",
          text_tp_rr("仮", 1, 150.0, 150.1, 150.2) == ("TP: -", "RR: -") and text_tp_rr("仮", 1, None, 150.0, 150.2) == ("TP: -", "RR: -")
          and text_tp_rr("仮", 1, 150.3, 150.0, None)[1] == "RR: -"
          and text_tp_rr("仮", 1, 150.30, 150.0, 150.70)[1] == "RR: 1:1.33" and text_tp_rr("仮", -1, 150.3, 150.4, 150.1)[1] == "RR: 1:2"
          and text_tp_rr("仮", 1, 150.2, 150.0, 150.45)[1] == "RR: 1:1.25")
    check("UM-05 provisional vs confirmed text: provisional TP line has no note (the 未確定 note follows RR), confirmed TP line "
          "carries the planned-value note and no 未確定 note — the meaning of the former 'TP: 約定確認後に設定' kept",
          text_tp_rr("仮", 1, 150.25, 150.0, 150.625)[0] == "TP: 150.625"
          and text_tp_rr("確定", 1, 150.25, 150.0, 150.625)[0].endswith("(発注時の予定値。最終 TP は約定確認後に実約定価格から設定)"))


def gate_mutation():
    m = [text_tp_rr("確定", -1, 150.000, 150.250, 149.625)[1] == "RR: 1:1.5",
         f_tp(-1, 150.000, 150.250, None)[1] != 150.375]
    check("UU-01 mirror sanity: the SHORT sign is not mirrored as LONG (TP below the entry)", all(m))
    muts = [S.replace("float rr     = okR and not na(tp) ? (side == 1 ? tp - ePx : ePx - tp) / risk : na",
                      "float rr     = okR and not na(tp) ? (tp - ePx) / risk : na"),
            S.replace('f_stAlertMsg("確定", side, stModeA ? oL : close, oSL, tpRef), alert.freq_all', 'f_stAlertMsg("確定", side, stModeA ? oL : close, oSL, na), alert.freq_all'),
            S.replace("        tpP := tpRef\n", "        tpP := ePx + (ePx - sl) * stRR\n"),
            S.replace('"1:" + str.tostring(rr, "0.##")', 'str.tostring(rr, "0.00")')]
    check("UU-02 source mutations rejected by the exact strip: RR without the SHORT sign, confirmed TP missing, provisional TP "
          "recomputed instead of reusing tpRef, RR format changed", all(x != S and ub.strip_strategy4(x) is None for x in muts))


def run_bar(state, bar_time, conf_ok, confirmed, varip_key, guarded, realtime=True):
    """one execution of the confirmed-bar block. state = committed var state (rolled back per execution); varip_key is
    kept across executions. Returns (new var state, new varip key, alerts sent in this execution)."""
    st = dict(state)                       # rollback: every execution starts from the committed var values
    sent = 0
    if confirmed and st["oState"] == 0 and conf_ok:
        st["oState"], st["oSeq"] = 1, st["oSeq"] + 1          # order branch (strategy.entry / exit)
        if not guarded or varip_key != bar_time:
            if guarded:
                varip_key = bar_time
            sent = 1 if realtime else 0                      # alert(): side effect, never rolled back (no alert on history)
    return st, varip_key, sent


def replay(execs, guarded):
    """execs = list of (bar_time, conf_ok, confirmed, commit[, realtime]). commit=True: the execution's var state is
    committed (last update of the bar); commit=False: a repeated update of the same bar (its var changes rolled back)."""
    committed = dict(oState=0, oSeq=0)
    key, total = None, 0
    for bt, ok, cf, commit, *rt in execs:
        st, key, s = run_bar(committed, bt, ok, cf, key, guarded, rt[0] if rt else True)
        total += s
        if commit:
            committed = st
            if cf and st["oState"] == 1:
                committed = dict(st, oState=0)               # next bar: the market order filled and closed (state free)
    return total


def gate_dedup():
    ch = es.changed_code(S, S5)
    exp = sorted(["if stAlertConf", "if stAlertConf and (na(stConfBar) or stConfBar != time)     // UJ-5: 同じ 5分足では最大 1 回",
                  "stConfBar := time", "varip int  stConfBar = na     // UJ-5: 確定アラートを送った 5分足の time。varip = 同じ足の再計算 (rollback) でも残る"])
    check("UC-01 Strategy == uj_build.build_strategy() (UJ-1 .. UJ-5); strip_strategy5 gives the UJ-4 Strategy of 89bc82b byte "
          "for byte; the code delta is only the varip bar key and the guard of the confirmed alert",
          ub.build_strategy() == S5 and ub.strip_strategy5(S5) == git("show", f"{UJ4}:{ub.STR_PATH}")
          and sorted(l for l in ch if l) == exp and {k for k, _, _ in ub.STRATEGY_EDITS5} == {"header", "dedup"}, str(ch))
    br = block(S5, "            if not skipRef and not na(pQty)\n", "    stPrev := cur")
    al = re.findall(r"^\s*alert\(.*$", S5, re.M)
    guard = ("                if stAlertConf and (na(stConfBar) or stConfBar != time)     // UJ-5: 同じ 5分足では最大 1 回\n"
             "                    stConfBar := time\n"
             "                    alert(f_stAlertMsg(\"確定\", side, stModeA ? oL : close, oSL, tpRef), alert.freq_all)\n")
    check("UC-02 the guard: the confirmed alert keeps alert.freq_all and its text; it is sent only when stConfBar (varip, its "
          "own state, never read by the provisional block) is not this bar's time, and stConfBar is set right before sending; "
          "strategy.entry / exit and the confirmed label stay outside the guard (unchanged); the provisional block still uses "
          "only stProvBar",
          "varip int  stConfBar = na" in S5 and code_only(S5).count("stConfBar") == 4 and guard in br
          and br.index("strategy.exit(oXid, oEid, stop = oSL)") < br.index("stConfBar") < br.index("if stLblConf")
          and "stConfBar" not in S5[S5.index("varip int stProvBar = na"):] and len(al) == 2
          and [l.strip() for l in al] == [l.strip() for l in re.findall(r"^\s*alert\(.*$", S, re.M)])
    strat = lambda t: sorted(re.findall(r"strategy\.(?:entry|exit|close|cancel)\(.*$", code_only(t), re.M))
    check("UC-03 trading / display unchanged by UJ-5: every strategy.* call, f_stTp / f_stQty / f_stProvEval, the labels, "
          "the provisional alert and the strategy() options identical to 89bc82b (the guard only gates alert(), so the "
          "Strategy Tester result cannot change)",
          strat(S5) == strat(S) and all(func(S5, h) == func(S, h) for h in ("f_stTp(", "f_stQty(int side, float ref, float sl) =>", "f_stProvEval() =>"))
          and S5[S5.index("varip int stProvBar = na"):] == S[S.index("varip int stProvBar = na"):]
          and S5[S5.index("strategy("):S5.index("import ")] == S[S.index("strategy("):S.index("import ")])
    rep_ = [(1000, True, True, False), (1000, True, True, True)]          # the confirmed update of bar 1000 runs twice
    check("UC-04 model: the same bar's confirmed update executed twice (the first one rolled back): before UJ-5 2 identical "
          "confirmed alerts (var oState rolled back to 0 -> the order branch runs again), with the varip key 1",
          replay(rep_, False) == 2 and replay(rep_, True) == 1)
    legit = [(1000, True, True, True), (1300, True, True, True), (1600, True, True, True)]
    rep3 = [e for b in legit for e in ((b[0], True, True, False), b)]
    check("UC-05 model: entries on different bars (1000 / 1300 / 1600) each send their confirmed alert (3); with a repeat on "
          "every bar still 3 with the key (6 without)", replay(legit, True) == 3 and replay(legit, False) == 3
          and replay(rep3, True) == 3 and replay(rep3, False) == 6)
    prov = [(1000, True, False, False), (1000, True, False, False), (1000, True, True, True)]
    check("UC-06 model: provisional ticks of the same bar (unconfirmed, stProvBar) do not touch stConfBar -> the confirmed "
          "alert of that bar is still sent; historical bars send nothing and the key does not block the first realtime bar",
          replay(prov, True) == 1 and replay([(10, True, True, True, False), (20, True, True, True, False)], True) == 0
          and replay([(10, True, True, True, False), (1000, True, True, True)], True) == 1)
    m = S5.replace("(na(stConfBar) or stConfBar != time)", "(na(stConfBar) or stConfBar != bar_index)")
    m2 = S5.replace("varip int  stConfBar = na", "var int    stConfBar = na")
    check("UC-07 mutations: a var (rolled back) key or a bar_index key are rejected by the exact strip; the model without "
          "the guard shows the duplicate", m != S5 and m2 != S5 and ub.strip_strategy5(m) is None
          and ub.strip_strategy5(m2) is None and replay(rep_, False) == 2)


def main():
    for g in (gate_static, gate_model, gate_mutation, gate_dedup):
        try:
            g()
        except Exception:
            import traceback
            check(f"{g.__name__} completed without error", False, traceback.format_exc()[-900:])
    fails = 0
    for n, ok, d in RESULTS:
        fails += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {n[:150].ljust(150)}  {'' if ok else d}")
    print(f"\n{len(RESULTS) - fails}/{len(RESULTS)} passed  [PINE_NOT_VERIFIED: exact build / static / Python models]")
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
