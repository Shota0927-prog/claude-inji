"""ZCS-1: generator of the pair-selection inputs of ZoneConfluenceStrategyXAU.pine.

    python3 tests/zcs_build.py          rewrite the "ZCS pairs (generated)" section of the strategy
    python3 tests/zcs_build.py --check  exit 1 if the section differs from what this script generates (nothing written)

The section holds, for the 26 evidence IDs of ZCR-9 (names = ZC_GN of ZoneConfluenceReactionStatsXAU.pine, same order):
  * 25 group titles (one per first evidence a = 0..24),
  * 650 input.bool (all 325 pairs a < b x LONG / SHORT, default false); the LONG and SHORT of one pair share an `inline` id,
    so one pair is one row of the settings,
  * zsS01..zsS25 (global var arrays, one per first evidence, built once) and f_zsSel(a01..a25) joining them into zsSel, the 650
    selections as one array<bool> (pair p: LONG = 2p, SHORT = 2p + 1; p = lexicographic order of (a, b)). The inputs are never
    referenced inside a function: a function may use at most 254 outside values (CE10116 on TradingView),
  * zsN00..zsN25: "a pair containing evidence g is selected" (an OR of inputs only = simple bool), used to skip the requests and
    the calculation of the kinds / timeframes no selected pair needs.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PINE = os.path.join(ROOT, "ZoneConfluenceStrategyXAU.pine")
BEGIN = "// ==== ZCS pairs (generated begin) ===="
END = "// ==== ZCS pairs (generated end) ===="
GN = ["ZA-1H", "ZA-4H", "ZA-D", "ZB-1m", "ZB-5m", "ZC-1H", "ZC-4H", "ZC-D", "ZC-W", "ZD-1H", "ZD-4H", "ZD-D", "ZD-W",
      "ZE-4H", "ZE-D", "ZF-FVG-1H", "ZF-FVG-4H", "ZF-FVG-D", "ZF-FVG-W", "ZG-1H", "ZG-4H", "ZG-D", "ZF-iFVG-1H", "ZF-iFVG-4H", "ZF-iFVG-D", "ZF-iFVG-W"]
PER_LINE = 10


def pairs():
    """[(p, a, b)] in the order of the pair number p"""
    out = []
    for a in range(len(GN) - 1):
        for b in range(a + 1, len(GN)):
            out.append((len(out), a, b))
    return out


def wrap(head, items, sep, tail, indent):
    """one statement over several lines: head + items joined by sep, PER_LINE items per line (continuation indent = indent + 5)"""
    lines, cur = [], []
    for i, x in enumerate(items):
        cur.append(x)
        if len(cur) == PER_LINE or i == len(items) - 1:
            lines.append(cur)
            cur = []
    out = []
    for n, ln in enumerate(lines):
        last = n == len(lines) - 1
        body = sep.join(ln) + ("" if last else sep.rstrip())
        out.append((head if n == 0 else " " * (indent + 5)) + body + (tail if last else ""))
    return out


def generate():
    ps = pairs()
    assert len(GN) == 26 and len(ps) == 325
    L = [BEGIN,
         "//  tests/zcs_build.py が生成する区間 (手で編集しない。python3 tests/zcs_build.py で作り直す)。",
         "//  ZCR-9 の 26 根拠 (ZC_GN の順) の全 325 ペア × LONG / SHORT = 650 個のチェック (初期は全 OFF・自動選別なし)。",
         "//  設定画面の 1 行 = 1 ペア (inline で LONG と SHORT を並べる)。グループは最初の根拠ごと (25 グループ)。",
         "//  変数名 pL### / pS### の ### = ペアの通し番号 p (最初の根拠 a < 次の根拠 b の辞書順)。"]
    for a in range(len(GN) - 1):
        L.append(f'var string G_P{a + 1:02d} = "P{a + 1:02d} · ペア {GN[a]} × (後の根拠)"')
    for p, a, b in ps:
        L.append(f'pL{p:03d} = input.bool(false, "{GN[a]} × {GN[b]}  LONG", group = G_P{a + 1:02d}, inline = "q{p:03d}")')
        L.append(f'pS{p:03d} = input.bool(false, "SHORT", group = G_P{a + 1:02d}, inline = "q{p:03d}")')
    # CE10116 (1 関数が参照できる外部の値は 254 個まで) を避けるため、650 個の入力は関数の中で参照しない:
    # グローバルで最初の根拠ごとの小分け配列 zsS01..zsS25 を var で 1 回だけ作り、結合関数 f_zsSel には引数で渡す。
    L.append("// 選択の配列 (ペア p の LONG = 2p、SHORT = 2p + 1)。CE10116 (関数の外部参照 254 個まで) を避けるため、入力は関数の中で参照しない:")
    L.append("//  グローバルで最初の根拠ごとの小分け配列 zsS01..zsS25 を var で初回だけ作り、f_zsSel が引数で受け取って 1 本に結合する")
    for a in range(len(GN) - 1):
        items = [f"{x}{p:03d}" for p, a2, _ in ps if a2 == a for x in ("pL", "pS")]
        L += wrap(f"var array<bool> zsS{a + 1:02d} = array.from(", items, ", ", ")", 0)
    args = [f"array<bool> a{a + 1:02d}" for a in range(len(GN) - 1)]
    L.append("f_zsSel(" + ", ".join(args) + ") =>")    # 関数の宣言は 1 行に (宣言の途中で改行しない)
    L.append("    array<bool> s = array.new_bool()")
    for a in range(len(GN) - 1):
        L.append(f"    array.concat(s, a{a + 1:02d})")
    L.append("    s")
    L += wrap("var array<bool> zsSel = f_zsSel(", [f"zsS{a + 1:02d}" for a in range(len(GN) - 1)], ", ", ")", 0)
    L.append("// 根拠 ID g を含むペアのどれかが選ばれている (入力だけから決まる simple bool。不要な種類・時間足の request と計算を止める)")
    for g in range(len(GN)):
        items = [f"{x}{p:03d}" for p, a, b in ps if g in (a, b) for x in ("pL", "pS")]
        L += wrap(f"bool zsN{g:02d} = ", items, " or ", "", 0)
    L.append(END)
    return "\n".join(L)


def splice(src, gen):
    i = src.index(BEGIN)
    j = src.index(END, i) + len(END)
    return src[:i] + gen + src[j:]


def main():
    src = open(PINE, encoding="utf-8").read()
    new = splice(src, generate())
    if "--check" in sys.argv[1:]:
        same = new == src
        print("generated section: " + ("same" if same else "DIFFERENT"))
        sys.exit(0 if same else 1)
    if new != src:
        open(PINE, "w", encoding="utf-8").write(new)
        print("rewrote the generated section of " + os.path.basename(PINE))
    else:
        print("generated section unchanged")


if __name__ == "__main__":
    main()
