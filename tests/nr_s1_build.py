"""NR-S1 — non-repainting Swing 15M / 1H: exact transform of ZoneVisualPractical.pine @ 5758a61.

  1. a marked NR-S1 block (two functions) is inserted just before the Swing source declarations,
  2. exactly the Swing #2 / #3 request lines are replaced by f_nrsSwing(...) (NRS_PROD_EDITS).

f_nrsSwing: TF above the chart TF -> request(tf, f_nrsPivotConfirmed(len), lookahead_on) = every zn.pivotPack field
of the previous, CONFIRMED HTF bar ([1]); otherwise the original request(tf, zn.pivotPack(len), lookahead_off)
(same / lower TF: unchanged). Swing #1 (5M), Accum, MA, Break, FVG A / B / C and the Engine are untouched.
"""
NRS_BASE_REV = "5758a61"
NRS_BEGIN, NRS_END = "// ==== NR-S1 Swing (begin) ", "// ==== NR-S1 Swing (end) "
NRS_ANCHOR = "float ph1 = na\nint   ph1T = na\n"

NRS_BLOCK = """// ==== NR-S1 Swing (begin) ====================================================
//  Swing 15M / 1H の非リペイント化 (NR-S1)。
//  ・チャート足より上位の Swing TF は、zn.pivotPack の各フィールドを [1] (= 直前の確定 HTF 足) にして
//    lookahead_on で取得する。HTF k の確定値は「次に実在する HTF 期間の最初の5分足」から読める
//    (履歴 / リアルタイムとも同じ)。形成中 HTF 足の値・後で消える Pivot は Engine に届かない。
//  ・Pivot の検知式 / パラメータ (zn.pivotPack / pivLen) は不変。値・Pivot 時刻キーも同じで、届く足だけが変わる:
//      連続取引 +1本 (5分) / HTF 確定がセッション終了と一致 -> 休場 + 5分 / HTF 最後の5分枠が欠損 -> 0。
//  ・チャート足と同じ / 下位の TF は従来の request (lookahead_off) のまま。
f_nrsPivotConfirmed(simple int len) =>
    [_ph, _pt, _pl, _lt] = zn.pivotPack(len)
    [_ph[1], _pt[1], _pl[1], _lt[1]]

f_nrsSwing(simple string tf, simple int len) =>
    float h  = na
    int   ht = na
    float l  = na
    int   lt = na
    if timeframe.in_seconds(tf) > timeframe.in_seconds()
        [_a, _at, _b, _bt] = request.security(syminfo.tickerid, tf, f_nrsPivotConfirmed(len), lookahead = barmerge.lookahead_on)
        h  := _a
        ht := _at
        l  := _b
        lt := _bt
    else
        [_a, _at, _b, _bt] = request.security(syminfo.tickerid, tf, zn.pivotPack(len), lookahead = barmerge.lookahead_off)
        h  := _a
        ht := _at
        l  := _b
        lt := _bt
    [h, ht, l, lt]
// ==== NR-S1 Swing (end) ======================================================
"""

NRS_PROD_EDITS = [
    ("    [_h2, _h2t, _l2, _l2t] = request.security(syminfo.tickerid, hzTf2, zn.pivotPack(pivLen2), lookahead = barmerge.lookahead_off)\n",
     "    [_h2, _h2t, _l2, _l2t] = f_nrsSwing(hzTf2, pivLen2)\n"),
    ("    [_h3, _h3t, _l3, _l3t] = request.security(syminfo.tickerid, hzTf3, zn.pivotPack(pivLen3), lookahead = barmerge.lookahead_off)\n",
     "    [_h3, _h3t, _l3, _l3t] = f_nrsSwing(hzTf3, pivLen3)\n"),
]


def _rep(t, a, b):
    assert t.count(a) == 1, ("NR-S1 anchor not unique", a[:80], t.count(a))
    return t.replace(a, b)


def nrs_transform(src):
    """5758a61 -> NR-S1 file."""
    t = src
    j = t.index(NRS_ANCHOR)
    assert t[j - 2:j] == "\n\n"
    t = t[:j] + NRS_BLOCK + "\n" + t[j:]
    for a, b in NRS_PROD_EDITS:
        t = _rep(t, a, b)
    return t


def apply_nrs_edits(t):
    for a, b in NRS_PROD_EDITS:
        t = _rep(t, a, b)
    return t


def revert_nrs_edits(t):
    for a, b in NRS_PROD_EDITS:
        assert t.count(b) == 1, ("NR-S1 edit missing / duplicated", b[:80], t.count(b))
        t = t.replace(b, a)
    return t


def cut_block(src, begin, end):
    """remove one marked block and its separating blank line; None if the markers are not exactly one well-placed pair."""
    if src.count(begin) != 1 or src.count(end) != 1 or not src.index(begin) < src.index(end):
        return None
    i = src.index(begin)
    if src[i - 2:i] != "\n\n":
        return None
    k = src.index("\n", src.index(end)) + 1
    return src[:i - 1] + src[k:]
