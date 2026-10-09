"""NR-A1 — non-repainting Accum 1H / 4H / D: exact transform of ZoneVisualPractical.pine @ a916283.

  1. a marked NR-A1 block is inserted just before the Accum source declarations. It holds
     - a LOCAL COPY of the Library Accum functions (ZoneEnginePractical.pine f_accumBoxCore / f_accumBoxState /
       f_accumDetectProvisional / accumPack), derived MECHANICALLY from the Library text by local_copy():
         * renames  f_accumBoxCore -> f_nraAccumBoxCore, f_accumBoxState -> f_nraAccumBoxState,
                    f_accumDetectProvisional -> f_nraAccumDetectProvisional, export accumPack -> f_nraAccumPack
         * f_nraAccumBoxState: the `if barstate.isconfirmed` guard line removed and its body de-indented by 4
       nothing else (formation formula, Hi / Lo, ID = time, provisional path byte-identical)
     - f_nraAccumConfirmed: the 3 outputs (upper, lower, instance ID) at [1] INSIDE the HTF context
     - f_nraAccum(tf, ...): TF above the chart TF -> request(tf, f_nraAccumConfirmed(...), lookahead_on);
                           same / lower TF -> the original request(tf, zn.accumPack(...), lookahead_off)
  2. exactly the 3 Accum request statements are replaced by f_nraAccum(accTf1/2/3, ...) (NRA_PROD_EDITS).
Engine / Library / Swing (NR-S1) / MA / Break / FVG A / B / C untouched.
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NRA_BASE_REV = "a916283"
NRA_BEGIN, NRA_END = "// ==== NR-A1 Accum (begin) ", "// ==== NR-A1 Accum (end) "
NRA_ANCHOR = "bool usePortedAccum = accumModule == \"Accum Box (ported)\"\n"
ENGINE = os.path.join(ROOT, "ZoneEnginePractical.pine")

GATE = "    if barstate.isconfirmed\n"
RENAMES = [("f_accumBoxCore(", "f_nraAccumBoxCore("), ("f_accumBoxState(", "f_nraAccumBoxState("),
           ("f_accumDetectProvisional(", "f_nraAccumDetectProvisional("), ("export accumPack(", "f_nraAccumPack(")]


def library_spans(eng):
    """the four Library function texts, exactly as in ZoneEnginePractical.pine."""
    def span(start, stop):
        i = eng.index(start)
        j = eng.index(stop, i)
        return eng[i:j]
    core = span("f_accumBoxCore(simple int rangeLen", "\nf_accumBoxState(") + "\n"
    state = span("f_accumBoxState(simple int rangeLen", "\nf_accumDetectProvisional(") + "\n"
    prov = span("f_accumDetectProvisional(simple int len", "\n// @function            Accumulation Box") + "\n"
    i = eng.index("export accumPack(")
    j = eng.index("    [upper, lower, instId]\n", i) + len("    [upper, lower, instId]\n")
    pack = eng[i:j]
    return core.rstrip("\n") + "\n", state.rstrip("\n") + "\n", prov.rstrip("\n") + "\n", pack


def remove_gate(state):
    """drop the `if barstate.isconfirmed` line and de-indent its body (the lines indented deeper than the if)."""
    assert state.count(GATE) == 1
    i = state.index(GATE)
    head, rest = state[:i], state[i + len(GATE):]
    out, lines = [], rest.split("\n")
    k = 0
    while k < len(lines) and lines[k].startswith("        "):
        out.append(lines[k][4:])
        k += 1
    return head + "\n".join(out + lines[k:])


def local_copy(eng_text):
    core, state, prov, pack = library_spans(eng_text)
    state = remove_gate(state)
    t = core + "\n" + state + "\n" + prov + "\n" + pack
    for a, b in RENAMES:
        t = t.replace(a, b)
    return t


def nra_block(eng_text):
    return ("// ==== NR-A1 Accum (begin) ====================================================\n"
            "//  Accum 1H / 4H / D の非リペイント化 (NR-A1)。\n"
            "//  ・下の f_nra* 4関数は ZoneEnginePractical.pine の f_accumBoxCore / f_accumBoxState /\n"
            "//    f_accumDetectProvisional / accumPack の写し (形成式・Hi / Lo・ID = time・Provisional は同一)。\n"
            "//    差分は関数名と、f_accumBoxState の `if barstate.isconfirmed` ガードの除去 (本体を1段浅く) だけ\n"
            "//    (fixture NR-A1 が Library 本文との機械照合で固定)。ガードの代わりに出力 3 値を HTF 側で [1] にし\n"
            "//    lookahead_on で取得するので、Engine に届くのは確定した HTF 足の状態だけ (request 内の\n"
            "//    barstate.isconfirmed に依存しない。var は tick ごとに巻き戻り、確定時の最終値だけが残る)。\n"
            "//  ・届く足: HTF 確定後の最初の5分足 (連続 +1本 / 休場・週末明け / 最後の5分枠欠損なら 0)。\n"
            "//  ・チャート足と同じ / 下位の TF は従来の request (zn.accumPack, lookahead_off) のまま。\n"
            "//  ・1H / 4H / D は別々の request 呼び出し = 別々の var 状態 (TF 間で共有しない)。\n"
            + local_copy(eng_text) + "\n" +
            "f_nraAccumConfirmed(simple bool usePorted, simple int rangeLen, simple int baseLen, simple int atrLen,\n"
            "     simple int minUpper, simple int minLower, simple int maxRun,\n"
            "     float atrMult, float barRatioMax, float driftMax,\n"
            "     simple int provLen, float provMult) =>\n"
            "    [_u, _l, _i] = f_nraAccumPack(usePorted, rangeLen, baseLen, atrLen, minUpper, minLower, maxRun,\n"
            "         atrMult, barRatioMax, driftMax, provLen, provMult)\n"
            "    [_u[1], _l[1], _i[1]]\n"
            "\n"
            "f_nraAccum(simple string tf, simple bool usePorted, simple int rangeLen, simple int baseLen, simple int atrLen,\n"
            "     simple int minUpper, simple int minLower, simple int maxRun,\n"
            "     float atrMult, float barRatioMax, float driftMax,\n"
            "     simple int provLen, float provMult) =>\n"
            "    float u  = na\n"
            "    float l  = na\n"
            "    int   id = na\n"
            "    if timeframe.in_seconds(tf) > timeframe.in_seconds()\n"
            "        [_a, _b, _c] = request.security(syminfo.tickerid, tf, f_nraAccumConfirmed(usePorted, rangeLen, baseLen, atrLen,\n"
            "             minUpper, minLower, maxRun, atrMult, barRatioMax, driftMax, provLen, provMult), lookahead = barmerge.lookahead_on)\n"
            "        u  := _a\n"
            "        l  := _b\n"
            "        id := _c\n"
            "    else\n"
            "        [_a, _b, _c] = request.security(syminfo.tickerid, tf, zn.accumPack(usePorted, rangeLen, baseLen, atrLen,\n"
            "             minUpper, minLower, maxRun, atrMult, barRatioMax, driftMax, provLen, provMult), lookahead = barmerge.lookahead_off)\n"
            "        u  := _a\n"
            "        l  := _b\n"
            "        id := _c\n"
            "    [u, l, id]\n"
            "// ==== NR-A1 Accum (end) ======================================================\n")


def _old_req(n):
    return (f"    [_a{n}h, _a{n}l, _a{n}i] = request.security(syminfo.tickerid, accTf{n},\n"
            "         zn.accumPack(usePortedAccum, accumRangeLen, accumBaseLen, accumAtrLen, accumMinUpperCloses, accumMinLowerCloses,\n"
            f"         accumMaxSameColorRun, accumAtrMult, accumBarRatioMax, accumDriftMax, accLen{n}, accMult), lookahead = barmerge.lookahead_off)\n")


def _new_req(n):
    return (f"    [_a{n}h, _a{n}l, _a{n}i] = f_nraAccum(accTf{n},\n"
            "         usePortedAccum, accumRangeLen, accumBaseLen, accumAtrLen, accumMinUpperCloses, accumMinLowerCloses,\n"
            f"         accumMaxSameColorRun, accumAtrMult, accumBarRatioMax, accumDriftMax, accLen{n}, accMult)\n")


NRA_PROD_EDITS = [(_old_req(n), _new_req(n)) for n in (1, 2, 3)]


def _rep(t, a, b):
    assert t.count(a) == 1, ("NR-A1 anchor not unique", a[:80], t.count(a))
    return t.replace(a, b)


def nra_transform(src, eng_text=None):
    """a916283 -> NR-A1 file."""
    eng_text = eng_text if eng_text is not None else open(ENGINE, encoding="utf-8").read()
    t = src
    j = t.index(NRA_ANCHOR)
    assert t[j - 2:j] == "\n\n"
    t = t[:j] + nra_block(eng_text) + "\n" + t[j:]
    for a, b in NRA_PROD_EDITS:
        t = _rep(t, a, b)
    return t


def apply_nra_edits(t):
    for a, b in NRA_PROD_EDITS:
        t = _rep(t, a, b)
    return t


def revert_nra_edits(t):
    for a, b in NRA_PROD_EDITS:
        assert t.count(b) == 1, ("NR-A1 edit missing / duplicated", b[:80], t.count(b))
        t = t.replace(b, a)
    return t


def cut_block(src, begin, end):
    """remove one marked block and its separating blank line; None if the markers are not exactly one well-placed pair."""
    if src is None or src.count(begin) != 1 or src.count(end) != 1 or not src.index(begin) < src.index(end):
        return None
    i = src.index(begin)
    if src[i - 2:i] != "\n\n":
        return None
    k = src.index("\n", src.index(end)) + 1
    return src[:i - 1] + src[k:]


def strip_nra(src):
    """file -> the same file without the NR-A1 block and with the 3 Accum edits reverted (None if not exact)."""
    t = cut_block(src, NRA_BEGIN, NRA_END)
    if t is None:
        return None
    try:
        return revert_nra_edits(t)
    except AssertionError:
        return None
