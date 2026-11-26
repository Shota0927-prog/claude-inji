"""ZCR-10: TradingView のチャートデータ書き出し (CSV) → 3 タブ (ペア別計測・2 根拠 / ペア別 LONG 50% 以上 / ペア別 SHORT 50% 以上)

  python3 tests/zcr_csv_tabs.py export.csv [out_prefix]      -> out_prefix_all.csv / _long50.csv / _short50.csv (+ .xlsx if openpyxl is installed)

入力: ZoneConfluenceReactionStatsXAU.pine (ZCR-10) を表示したチャートの書き出し CSV。列名 = plot のタイトル ("R1 記録番号" ... "R4 決着 $15 (UNIX 秒)")。
各行 (足) の R1..R4 の枠から記録を取り出し (記録番号が空の枠は無視)、記録番号で重複を除いて集計する。
集計は CSV に入った記録 (= 採用した値幅が全部決着した新規接触) だけから作る。追跡中・出力待ちの記録は CSV に入らないので、
表の「未出力」の件数だけ新規接触が少なくなる (仕様書「CSV から 3 タブを作る」)。
"""
import csv
import math
import os
import sys

GN = ["ZA-1H", "ZA-4H", "ZA-D", "ZB-1m", "ZB-5m", "ZC-1H", "ZC-4H", "ZC-D", "ZC-W", "ZD-1H", "ZD-4H", "ZD-D", "ZD-W",
      "ZE-4H", "ZE-D", "ZF-FVG-1H", "ZF-FVG-4H", "ZF-FVG-D", "ZF-FVG-W", "ZG-1H", "ZG-4H", "ZG-D", "ZF-iFVG-1H", "ZF-iFVG-4H", "ZF-iFVG-D", "ZF-iFVG-W"]
PAIRS = [(a, b) for a in range(25) for b in range(a + 1, 26)]
COLS = ["記録番号", "ペア方向コード", "T0", "Zone A ID", "Zone B ID", "Zone A 登録", "Zone B 登録", "帯 上限", "帯 下限", "P0", "結果", "タッチ足判定", "決着 $5",
        "決着 $10", "決着 $15"]
HEAD = ["ペア番号", "ペア", "方向", "値幅", "新規接触", "採用", "見送り", "反発先", "逆行先", "順序不明", "追跡中", "打切り", "計測不能", "先着率"]


def num(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(v) else v


def records_from_rows(header, rows):
    """header: column names; rows: lists of cells. Returns {record no: [15 values]} (duplicates by record number are merged)"""
    slots = []
    for r in range(1, 9):
        idx = [i for i, h in enumerate(header) if h.startswith(f"R{r} ")]       # the 15 plots of slot r, in plot order
        if len(idx) == 15:
            slots.append(idx)
    out = {}
    for row in rows:
        for idx in slots:
            v = [num(row[i]) if i is not None and i < len(row) else None for i in idx]
            if v[0] is None:
                continue
            out[int(v[0])] = v
    return out


def tally(recs):
    """records -> rows [(pair, s, j) -> 9 counts] as the indicator's table (0 new / 1 adopted / 2 skipped / 3 reb / 4 adv / 5 unk / 6 unmeasurable / 7 cut / 8 tracking)"""
    cnt = [[0] * 9 for _ in range(1950)]
    for v in recs.values():
        pd = int(v[1])
        st = int(v[10])
        for j, s in enumerate((st // 100, st // 10 % 10, st % 10)):
            c = cnt[pd * 3 + j]
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
    recs = records_from_rows(rd[0], rd[1:])
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
    nums = sorted(recs)
    gaps = len(range(nums[0], nums[-1] + 1)) - len(nums) if nums else 0
    print(f"records {len(recs)} (record numbers {nums[0] if nums else '-'}..{nums[-1] if nums else '-'}, missing numbers in between {gaps}: "
          f"these are still tracking / waiting at the end of the history, see the table's 未出力)")


if __name__ == "__main__":
    main()
