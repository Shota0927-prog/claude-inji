"""SW-1 Gate SW-L1 — ZoneEnginePracticalSwingMax.pine: exact transform of ZoneEnginePracticalRN.pine (/5 source) @ 3c29718.

Swing max-score (plan B): inside one cluster the Swing sources (hzTf1 / hzTf2 / hzTf3) contribute only the largest
configured score (scoreHz1 / scoreHz2 / scoreHz3) of the timeframes present, instead of their sum.
  * implemented incrementally inside the member loop: the first Swing timeframe adds its score exactly as before
    (bit-identical for clusters with at most one Swing timeframe); a later timeframe adds only (score - running max)
    when it is larger. No clamping: a negative-only Swing set keeps its (negative) maximum, no Swing adds nothing.
  * srcMask Swing bits, hasHZ (one confluence category), HTF bits, members, Raw Zones, clusters, Track / Touch / Break /
    Flip, RN scoring and the four RN fields are untouched (rnBaseSumExRn = the new pre-RN baseSum).
ZoneEnginePractical.pine (/2) and ZoneEnginePracticalRN.pine (/5) stay byte-identical.
"""
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SW_BASE_REV = "3c29718"
SRC_PATH = "ZoneEnginePracticalRN.pine"
SW_PATH = "ZoneEnginePracticalSwingMax.pine"


def _hit(n):
    old = (f"                if not swHit{n}\n"
           f"                    swHit{n}  := true\n"
           f"                    baseSum += c.scoreHz{n}\n")
    new = (f"                if not swHit{n}\n"
           f"                    swHit{n}  := true\n"
           f"                    [_sa{n}, _sm{n}] = f_swingMaxStep(swMax, c.scoreHz{n})\n"
           f"                    baseSum += _sa{n}\n"
           f"                    swMax   := _sm{n}\n")
    return old, new


SW_EDITS = [
    ("//  ★ RN-1 版 (Round Number 加点専用)。",
     "//  ★ SW-1 版 (Swing 最大点方式)。同一 Cluster 内の Swing (hzTf1 / hzTf2 / hzTf3) は、含まれる時間足の\n"
     "//    設定点 (scoreHz1 / 2 / 3) の最大値だけを baseSum に加える (旧: 時間足ごとに合算)。Swing の検知 / 登録 /\n"
     "//    Cluster / srcMask / Confluence (Horizontal 1 カテゴリ) / HTF / Track / Touch / RN は変更しない。\n"
     "//  ★ RN-1 版 (Round Number 加点専用)。"),
    ("//  zBot / zTop : f_buildClusters の running aggregate (min member.bottom / max member.top)\nf_finalizeCluster(",
     "// Swing 最大点方式 (SW-1): 現在の最大点 swMax (Swing 未出現は na) に点数 s の Swing 時間足を加えるときの\n"
     "//   [baseSum への加算量, 新しい最大点]。最初の Swing は s をそのまま (旧版と同じ加算)、以降は最大点が\n"
     "//   上がる分だけ。0 への切り上げ等はしない (負の点数だけなら負の最大値)。\n"
     "f_swingMaxStep(float swMax, float s) =>\n"
     "    float add = na(swMax) ? s : s > swMax ? s - swMax : 0.0\n"
     "    float mx  = na(swMax) ? s : math.max(swMax, s)\n"
     "    [add, mx]\n"
     "\n"
     "//  zBot / zTop : f_buildClusters の running aggregate (min member.bottom / max member.top)\nf_finalizeCluster("),
    ("    bool swHit3 = false\n",
     "    bool swHit3 = false\n"
     "    float swMax = na     // SW-1: このCluster で採用中の Swing 最大点 (Swing 未出現は na)\n"),
    _hit(1), _hit(2), _hit(3),
]


def git_show(rev, path):
    return subprocess.run(["git", "-C", ROOT, "show", f"{rev}:{path}"], capture_output=True, text=True).stdout


def sw_transform(src):
    t = src
    for a, b in SW_EDITS:
        assert t.count(a) == 1, ("SW-1 anchor not unique", a[:70], t.count(a))
        t = t.replace(a, b)
    return t


def strip_sw(src):
    t = src
    for a, b in reversed(SW_EDITS):
        if t.count(b) != 1:
            return None
        t = t.replace(b, a)
    return t
