"""CAD-1 — confirmed Entry alert at most once per 5M bar in the GBPJPY-lineage Strategies (USDJPY UJ-5 rolled out).

Files: ZoneStrategyGBPJPY.pine (gbs_build: CAD_EDITS is its last layer) and the Strategies generated from it, which inherit
the edit unchanged: ZoneStrategyEURUSD.pine (eu_build, from GBPJPY), ZoneStrategyGBPUSD.pine (gu_build, from EURUSD),
ZoneStrategyBTCUSD.pine (btcs_build, from GBPJPY). USDJPY already has the same guard (uj_build UJ-5).
The edit (notification only, same as UJ-5): a varip bar key stConfBar (time of the 5M bar, kept across realtime
rollbacks); the existing confirmed alert() in the order branch is sent only when stConfBar != time and stConfBar is set
right before sending. strategy.* calls, labels, the provisional alert (stProvBar), the text and alert.freq_all unchanged.
strip() reverses it exactly (all or nothing); a text without the edit is returned unchanged by unapply().
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = ("ZoneStrategyGBPJPY.pine", "ZoneStrategyEURUSD.pine", "ZoneStrategyGBPUSD.pine", "ZoneStrategyBTCUSD.pine")
ALERT = '                    alert(f_stAlertMsg("確定", side, stModeA ? oL : close, oSL, tpRef), alert.freq_all)\n'
CAD_EDITS = [
    ("var int    oClosed = 0\n",
     "var int    oClosed = 0\n"
     "varip int  stConfBar = na     // CAD-1: 確定アラートを送った 5分足の time。varip = 同じ足の再計算 (rollback) でも残る (USDJPY UJ-5 と同じ)\n"),
    ("                if stAlertConf\n" + ALERT,
     "                if stAlertConf and (na(stConfBar) or stConfBar != time)     // CAD-1: 同じ 5分足では最大 1 回 (USDJPY UJ-5 と同じ)\n"
     "                    stConfBar := time\n" + ALERT),
]


def apply(text):
    out = text
    for a, b in CAD_EDITS:
        assert out.count(a) == 1, a[:60]
        out = out.replace(a, b)
    return out


def strip(text):
    """reverse CAD-1 exactly; None when the edit is not present exactly."""
    out = text
    for a, b in reversed(CAD_EDITS):
        if out is None or out.count(b) != 1:
            return None
        out = out.replace(b, a)
    return out


_rd = lambda p: open(os.path.join(ROOT, p), encoding="utf-8").read()


def pre_cad(path, text=None):
    """the file text with CAD-1 reverted for the four Strategies (all or nothing); other paths unchanged. The older
    generators / fixtures read these files through it, so they keep pinning the pre-CAD content exactly."""
    if text is None:
        text = _rd(path)
    text = __import__("sx_build").unapply(path, text)     # SX-1 (later layer on the five Strategies) reverted first
    return unapply(text) if path in FILES else text


def unapply(text):
    """reverse CAD-1 when present (all or nothing): unchanged without it, None with only part of it."""
    if text is None:
        return None
    hits = [text.count(b) for _, b in CAD_EDITS]
    if not any(hits):
        return text
    return strip(text)
