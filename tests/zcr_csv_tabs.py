"""ZCR-10: TradingView のチャートデータ書き出し (CSV) → 3 タブ (ペア別計測・2 根拠 / ペア別 LONG 50% 以上 / ペア別 SHORT 50% 以上)

  python3 tests/zcr_csv_tabs.py export.csv [out_prefix]      -> out_prefix_all.csv / _long50.csv / _short50.csv (+ .xlsx if openpyxl is installed)

入力: ZoneConfluenceReactionStatsXAU.pine (ZCR-11) を表示したチャートの書き出し CSV。列名 = plot のタイトル ("R1 イベント ID" ... "R6 決着 (UNIX 秒)")。
各行 (足) の R1..R6 の枠から記録を取り出し (イベント ID が空の枠は無視)、(イベント ID, 値幅) をキーに重複を除いて集計する
(同じキーが 2 回以上あれば警告して 1 回だけ数える)。記録は値幅ごと: 採用した値幅は決着した足で、見送った値幅は新規接触の足で出る。
新規接触の件数 = その値幅の記録数 (= 採用 + 見送り)。追跡中の値幅・出力待ちの記録は CSV に入らないので、
表の「未出力」の件数だけ少なくなる (仕様書「CSV から 3 タブを作る」)。
"""
import csv
import math
import os
import sys

GN = ["ZA-1H", "ZA-4H", "ZA-D", "ZB-1m", "ZB-5m", "ZC-1H", "ZC-4H", "ZC-D", "ZC-W", "ZD-1H", "ZD-4H", "ZD-D", "ZD-W",
      "ZE-4H", "ZE-D", "ZF-FVG-1H", "ZF-FVG-4H", "ZF-FVG-D", "ZF-FVG-W", "ZG-1H", "ZG-4H", "ZG-D", "ZF-iFVG-1H", "ZF-iFVG-4H", "ZF-iFVG-D", "ZF-iFVG-W"]
PAIRS = [(a, b) for a in range(25) for b in range(a + 1, 26)]
COLS = ["イベント ID", "コード", "ペア方向コード", "T0", "Zone A ID", "Zone B ID", "帯 上限", "帯 下限", "P0", "決着"]   # the 10 columns of a slot, in plot order
HEAD = ["ペア番号", "ペア", "方向", "値幅", "新規接触", "採用", "見送り", "反発先", "逆行先", "順序不明", "追跡中", "打切り", "計測不能", "先着率"]


def num(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(v) else v


def records_from_rows(header, rows):
    """header: column names; rows: lists of cells. Returns ({(event ID, width index 0 / 1 / 2): [10 values]}, number of duplicates).
    A record is identified by (event ID, width) (width from the code column): the same key seen again (overlapping exports joined, a row repeated) is counted once
    and reported as a duplicate."""
    slots = []
    for r in range(1, 13):
        idx = [i for i, h in enumerate(header) if h.startswith(f"R{r} ")]       # the 10 plots of slot r, in plot order
        if len(idx) == 10:
            slots.append(idx)
    out = {}
    dup = 0
    for row in rows:
        for idx in slots:
            v = [num(row[i]) if i is not None and i < len(row) else None for i in idx]
            if v[0] is None or v[1] is None:
                continue
            key = (int(v[0]), int(v[1]) // 1000 - 1)
            if key in out:
                dup += 1
                continue
            out[key] = v
    return out, dup


def decode(code):
    """column 1 = width number (1 / 2 / 3 = $5 / $10 / $15) x 1000 + result x 100 + touch-bar judgement x 10 + flag"""
    c = int(code)
    return dict(width=(c // 1000) * 5, result=c // 100 % 10, judge=c // 10 % 10, flag=c % 10)


def tally(recs):
    """records -> rows [(pair, s, j) -> 9 counts] as the indicator's table (0 new / 1 adopted / 2 skipped / 3 reb / 4 adv / 5 unk / 6 unmeasurable / 7 cut / 8 tracking).
    New contacts of a width = the records of that width (adopted + skipped)"""
    cnt = [[0] * 9 for _ in range(1950)]
    for (_, j), v in recs.items():
        c = cnt[int(v[2]) * 3 + j]
        s = decode(v[1])["result"]
        c[0] += 1
        if s == 9:
            c[2] += 1
        else:
            c[1] += 1
            c[{0: 8, 1: 3, 2: 4, 3: 5, 4: 6, 5: 7}[s]] += 1
    return cnt


def rate(a, b):
    return None if a + b == 0 else a / (a + b)


def tabs(cnt):
    """the 3 tabs: all rows / LONG rate >= 50% / SHORT rate >= 50% (exactly 50% included, no minimum count)"""
    allr, lg, sh = [], [], []
    for key in range(1950):
        c = cnt[key]
        pd, j = divmod(key, 3)
        pr, s = divmod(pd, 2)
        a, b = PAIRS[pr]
        rt = rate(c[3], c[4])
        row = [pr, f"{GN[a]}×{GN[b]}", "LONG" if s == 0 else "SHORT", f"${(j + 1) * 5}", c[0], c[1], c[2], c[3], c[4], c[5], c[8], c[7], c[6],
               "" if rt is None else round(rt * 100, 1)]
        allr.append(row)
        if rt is not None and rt >= 0.5:
            (lg if s == 0 else sh).append(row)
    return allr, lg, sh


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    src = sys.argv[1]
    pre = sys.argv[2] if len(sys.argv) > 2 else os.path.splitext(src)[0]
    with open(src, encoding="utf-8-sig", newline="") as f:
        rd = list(csv.reader(f))
    recs, dup = records_from_rows(rd[0], rd[1:])
    if dup:
        print(f"WARNING: {dup} duplicated records ((event ID, width) seen again) were counted once")
    allr, lg, sh = tabs(tally(recs))
    names = [("ペア別計測・2根拠", allr, "_all.csv"), ("ペア別 LONG 50%以上", lg, "_long50.csv"), ("ペア別 SHORT 50%以上", sh, "_short50.csv")]
    for _, rows, suf in names:
        with open(pre + suf, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(HEAD)
            w.writerows(rows)
    try:
        import openpyxl      # noqa: PLC0415
        wb = openpyxl.Workbook()
        wb.remove(wb.active)
        for nm, rows, _ in names:
            ws = wb.create_sheet(nm[:31])
            ws.append(HEAD)
            for r in rows:
                ws.append(r)
        wb.save(pre + "_tabs.xlsx")
    except ImportError:
        pass
    ev = sorted(set(k[0] for k in recs))
    print(f"records {len(recs)} ((event ID, width) pairs; event IDs {ev[0] if ev else '-'}..{ev[-1] if ev else '-'}). "
          f"Missing (event ID, width) pairs up to the last ID: {3 * (ev[-1] if ev else 0) - len(recs)} "
          f"(widths still tracking / records waiting at the end of the history, see the table's 未出力)")

if __name__ == "__main__":
    main()
