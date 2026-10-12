"""STJ-1 — ZoneStrategyUSDJPY.pine: OANDA:USDJPY 5M entry strategy (A / B / C / D of ZoneStrategyXAU).

Deterministic build, same pipeline as ZoneStrategyXAU but starting from the USDJPY Visual:
  ZoneVisualUSDJPY text (jpy_build.build())
    -> st1_build.st_transform   (computation part kept byte for byte, display removed, Zone evaluation block)
    -> st2_build.st2_transform  (A / B / C orders)
    -> st3_build.st3_transform  (D 1M BOS, session, opposite-zone TP, breakeven; current XAU defaults)
    -> EDITS                    (identity / header, yen SL Buffer and Breakeven Trigger, drop the display-only
                                 label helper f_jpyGeom)
strip_stj() reverses EDITS exactly (fixture stj_sim). Zone calculation = ZONE-JPY, order logic = ZONE-ST.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jpy_build as jb     # noqa: E402
import st1_build as tb     # noqa: E402
import st2_build as s2     # noqa: E402
import st3_build as s3     # noqa: E402

ROOT = jb.ROOT
STJ_PATH = "ZoneStrategyUSDJPY.pine"

EDITS = [
    ("//  Zone Strategy XAU  —  ZONE-P (ZoneVisualPractical) の Zone 判定をそのまま使う XAUUSD 5分足 Strategy\n",
     "//  Zone Strategy USDJPY  —  ZONE-JPY (ZoneVisualUSDJPY) の Zone 判定をそのまま使う OANDA:USDJPY 5分足 Strategy\n"
     "//  (生成: tests/stj_build.py。Zone 計算は ZONE-JPY、注文処理は ZONE-ST (ZoneStrategyXAU) と同じ式。価格差は円)\n"),
    ('     title                  = "Zone Strategy XAU",\n     shorttitle             = "ZONE-ST",\n',
     '     title                  = "Zone Strategy USDJPY",\n     shorttitle             = "ZONE-ST-JPY",\n'),
    ('\n// Zone の上下限と最終的な幅 (円、小数 3 桁)\n'
     'f_jpyGeom(zn.Zone z) =>\n'
     '    f_num(z.top, "#.000") + " - " + f_num(z.bottom, "#.000") + " | W " + f_num(z.top - z.bottom, "0.000")\n',
     ''),
    ('stBuffer = input.float(3.0, "SL Buffer ($)", minval = 0.0, step = 0.5, group = G_ST)\n',
     'stBuffer = input.float(0.05, "[暫定] SL Buffer (円)", minval = 0.0, step = 0.005, group = G_ST)\n'),
    ('stBEDist = input.float(10.0, "Breakeven Trigger ($)", minval = 0.0, step = 0.5, group = G_STT)\n',
     'stBEDist = input.float(0.15, "[暫定] Breakeven Trigger (円)", minval = 0.0, step = 0.005, group = G_STT)\n'),
]


def pipeline():
    """ZONE-JPY -> ST-1 -> ST-2 -> ST-3 (before the USDJPY edits)."""
    return s3.st3_transform(s2.st2_transform(tb.st_transform(jb.build())))


def stj_transform(st3_text):
    out = st3_text
    for a, b in EDITS:
        assert out.count(a) == 1, a[:80]
        out = out.replace(a, b) if b else out.replace(a, "")
    return out


def strip_stj(text):
    """exact inverse of stj_transform (None when the text is not a USDJPY build)."""
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
    return stj_transform(pipeline())


if __name__ == "__main__":
    open(os.path.join(ROOT, STJ_PATH), "w", encoding="utf-8").write(build())
    print("written", STJ_PATH)
