"""GBS-1 — ZoneStrategyGBPJPY.pine: OANDA:GBPJPY 5M comparison strategy (A / B / C / D + provisional / confirmed alerts).

Deterministic build, the same pipeline as ZoneStrategyUSDJPY (stj_build) but starting from the GBPJPY Visual:
  ZoneVisualGBPJPY text (gbj_build.build())
    -> st1_build.st_transform   (computation part kept byte for byte, display removed, Zone evaluation block)
    -> st2_build.st2_transform  (A / B / C orders)
    -> st3_build.st3_transform  (D 1M BOS, session, opposite-zone TP, breakeven)
    -> EDITS                    (= stj_build.EDITS, the USDJPY order / alert edits, with only these differences:
                                 identity / header / comments name GBPJPY, the display-only label helper removed is the
                                 GBPJPY one, Direction keeps Both, Zone Half Width already 0.03 in the GBPJPY Visual)
strip_gbs() reverses EDITS exactly (fixture gbs_sim). Zone calculation = ZONE-GBPJPY, order / alert logic = ZONE-ST-JPY.
Comparison defaults (not optimised for GBPJPY): D, Both, HW 0.03 / Cluster 0.08 / FVG 0.05, SL Buffer 0.05, RR 1.3,
session JST 09:00-02:00, zone TP OFF, breakeven OFF (0.15), D wait 30, provisional / confirmed alerts ON.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gbj_build as gb     # noqa: E402
import st1_build as tb     # noqa: E402
import st2_build as s2     # noqa: E402
import st3_build as s3     # noqa: E402
import stj_build as sj     # noqa: E402

ROOT = gb.ROOT
GBS_PATH = "ZoneStrategyGBPJPY.pine"

HEADER_JPY = sj.EDITS[0][1]
HEADER_GBS = ("//  Zone Strategy GBPJPY  —  ZONE-GBPJPY (ZoneVisualGBPJPY) の Zone 判定をそのまま使う OANDA:GBPJPY 5分足 Strategy\n"
              "//  (生成: tests/gbs_build.py。Zone 計算は ZONE-GBPJPY、注文処理・仮 / 確定アラートは ZONE-ST-JPY\n"
              "//   (ZoneStrategyUSDJPY) と同じ式。価格差は円。初期値は比較開始用で、GBPJPY の最適値ではない)\n")
TITLE_JPY = sj.EDITS[1][1]
TITLE_GBS = '     title                  = "Zone Strategy GBPJPY",\n     shorttitle             = "ZONE-ST-GBPJPY",\n'
GEOM_GBS = ('\n// Zone の上下限と最終的な幅 (円、小数 3 桁 = OANDA:GBPJPY の最小刻み 0.001。pips ではない)\n'
            'f_jpyGeom(zn.Zone z) =>\n'
            '    f_num(z.top, "#.000") + " - " + f_num(z.bottom, "#.000") + " | W " + f_num(z.top - z.bottom, "0.000") + "円"\n')
# USDJPY edits not needed here: Half Width is already 0.03 in ZONE-GBPJPY; Direction keeps the ZONE-ST default Both.
SKIP_PREFIX = ('zoneHalfWidth = input.float(0.05,', 'stDir = input.string("Both"')


def _gbs_edits():
    out = []
    for a, b in sj.EDITS:
        if a.startswith(SKIP_PREFIX):
            continue
        if b == "":                                   # display-only label helper (removed)
            out.append((GEOM_GBS, ""))
        elif b == HEADER_JPY:
            out.append((a, HEADER_GBS))
        elif b == TITLE_JPY:
            out.append((a, TITLE_GBS))
        else:                                         # USDJPY only appears in comments of these edits
            out.append((a, b.replace("USDJPY", "GBPJPY")))
    return out


EDITS = _gbs_edits()


def pipeline():
    """ZONE-GBPJPY -> ST-1 -> ST-2 -> ST-3 (before the strategy edits)."""
    return s3.st3_transform(s2.st2_transform(tb.st_transform(gb.build())))


def gbs_transform(st3_text):
    out = st3_text
    for a, b in EDITS:
        assert out.count(a) == 1, a[:80]
        out = out.replace(a, b) if b else out.replace(a, "")
    return out


def strip_gbs(text):
    """exact inverse of gbs_transform (None when the text is not a GBPJPY build)."""
    out = text
    for a, b in reversed(EDITS):
        if b:
            if out.count(b) != 1:
                return None
            out = out.replace(b, a)
        else:      # removed block: it sat right after f_num
            anchor = 'f_num(float v, string fmt) =>\n    na(v) ? "-" : str.tostring(v, fmt)\n'
            if out.count(anchor) != 1:
                return None
            out = out.replace(anchor, anchor + a)
    return out


def build():
    return gbs_transform(pipeline())


if __name__ == "__main__":
    open(os.path.join(ROOT, GBS_PATH), "w", encoding="utf-8").write(build())
    print("written", GBS_PATH)
