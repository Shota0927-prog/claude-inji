"""FVG label info — ZoneVisualPractical.pine: exact transform of the Visual @ 67f8fd2 (inside the overlap-only display).

  * f_zpoFvgTag(best): " | FVG 15M +1" / " | FVG 1H +2" / " | FVG 4H +3" for the Batch C best FVG (f_zpoBestFvg, the same
    selection as f_fvcZoneDisplay), "" when no FVG overlaps -> label text identical to the old one
  * f_zpoWithFvg(txt, tag): the tag goes after Strength / Touch / Score and before the Detailed Labels line
  * the tag is put on the boost label when it is drawn, otherwise on the original label (never on both)
Score / Strength / boxes / FVG selection / filters are unchanged; only label strings change.
"""
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FVL_BASE_REV = "67f8fd2"

FVL_EDITS = [
    ("             style = label.style_label_left, color = lc, textcolor = color.white, size = size.small))\n"
     "    idx + 1\n"
     "\n"
     "if barstate.islast and is5mChart\n",
     "             style = label.style_label_left, color = lc, textcolor = color.white, size = size.small))\n"
     "    idx + 1\n"
     "\n"
     "// FVG ラベル情報: 採用 FVG (best = f_zpoBestFvg) の時間足と FVG 基本点 (Confluence 増分は含まない)。無ければ \"\"\n"
     "f_zpoFvgTag(int best) =>\n"
     "    string tag = \"\"\n"
     "    if best >= 0\n"
     "        float b = f_fvcBase(best)\n"
     "        tag := \" | FVG \" + (b == 1.0 ? \"15M\" : b == 2.0 ? \"1H\" : \"4H\") + \" +\" + str.tostring(b, \"#\")\n"
     "    tag\n"
     "\n"
     "// ラベル文字列に FVG 情報を差し込む (Strength / Touch / Score の後、Detailed Labels の改行の前)\n"
     "f_zpoWithFvg(string txt, string tag) =>\n"
     "    string out = txt\n"
     "    if tag != \"\"\n"
     "        int p = str.pos(txt, \"\\n\")\n"
     "        out := na(p) ? txt + tag : str.substring(txt, 0, p) + tag + str.substring(txt, p)\n"
     "    out\n"
     "\n"
     "if barstate.islast and is5mChart\n"),
    ("                if showLabels\n"
     "                    color lc = color.new(bc, 20)\n"
     "                    if showBoost\n"
     "                        nLbl := f_zpoLabel(nLbl, xR, oTop, f_fvcLabelText(z, dStr, dScore), lc)\n"
     "                    if showBase and not (showBoost and oTop == z.top)\n"
     "                        nLbl := f_zpoLabel(nLbl, xR, z.top, f_labelText(z), lc)\n",
     "                if showLabels\n"
     "                    color lc = color.new(bc, 20)\n"
     "                    // FVG 情報は昇格ラベルが描かれるならそちらだけ、無ければ元ラベルに付ける (重複表示しない)\n"
     "                    string fvgTag = f_zpoFvgTag(best)\n"
     "                    if showBoost\n"
     "                        nLbl := f_zpoLabel(nLbl, xR, oTop, f_zpoWithFvg(f_fvcLabelText(z, dStr, dScore), fvgTag), lc)\n"
     "                    if showBase and not (showBoost and oTop == z.top)\n"
     "                        nLbl := f_zpoLabel(nLbl, xR, z.top, f_zpoWithFvg(f_labelText(z), showBoost ? \"\" : fvgTag), lc)\n"),
]


def git_show(rev, path="ZoneVisualPractical.pine"):
    return subprocess.run(["git", "-C", ROOT, "show", f"{rev}:{path}"], capture_output=True, text=True).stdout


def fvl_transform(src):
    t = src
    for a, b in FVL_EDITS:
        assert t.count(a) == 1, ("FVL anchor not unique", a[:70], t.count(a))
        t = t.replace(a, b)
    return t


def strip_fvl(src):
    if src is None:
        return None
    t = src
    for a, b in reversed(FVL_EDITS):
        if t.count(b) != 1:
            return None
        t = t.replace(b, a)
    return t
