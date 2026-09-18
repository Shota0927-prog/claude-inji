#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ZoneEngineV2_VisualHarness_SAFE.pine を FULL から生成する。

FULL が唯一の原本。SAFE は FULL と次の 3 点だけが違う。
  1) indicator() に calc_bars_count を付ける (履歴本数を絞る = 検証用)
  2) shorttitle を分けてチャート上で区別できるようにする
  3) 冒頭に「履歴範囲が短いので FULL と同じ過去状態にはならない」注意書きを足す

Zone ロジックに関わる行は 1 文字も変えない。

使い方:
    python3 tools/sync_harness.py            # 既定 calc_bars_count = 300
    python3 tools/sync_harness.py 500        # 500 本で作り直す
"""
import sys, os, io

BARS = int(sys.argv[1]) if len(sys.argv) > 1 else 300
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FULL = os.path.join(ROOT, 'ZoneEngineV2_VisualHarness_FULL.pine')
SAFE = os.path.join(ROOT, 'ZoneEngineV2_VisualHarness_SAFE.pine')

NOTE = u'''// ############################################################################
// ##  ★★ SAFE 版 : 検証用であり、本番は FULL 版 ★★                        ##
// ##                                                                        ##
// ##  このファイルは ZoneEngineV2_VisualHarness_FULL.pine から                 ##
// ##  tools/sync_harness.py で生成している。直接編集しないこと。          ##
// ##  違いは次の 3 点だけで、Zone ロジックに関わる行は全て同一。        ##
// ##      1) indicator() に calc_bars_count を付けている                  ##
// ##      2) shorttitle が別                                              ##
// ##      3) この注意書き                                                ##
// ##                                                                        ##
// ##  ★ 履歴範囲が短いので、FULL 版と完全に同じ過去状態にはならない。 ##
// ##    calc_bars_count より前の足は 1 本も処理されないため、            ##
// ##      ・EMA2000 / EMA3000 がまだ温まっていない                      ##
// ##      ・過去の Swing / Accum / FVG / 時間高安 Root が存在しない          ##
// ##      ・Core の Touch / Break / Flip / Generation の履歴が積まっていない ##
// ##      ・Core ID / Generation ID の番号も FULL 版と一致しない            ##
// ##    だから SAFE 版の表示内容を「本番の判定結果」として扱わない。   ##
// ##    SAFE 版の目的は「40 秒以内で動く履歴本数を探る」ことだけ。     ##
// ##                                                                        ##
// ##  手順 : calc_bars_count を 300 → 500 → 1000 → 2000 と上げて、         ##
// ##         40 秒以内で RE10110 が出ない最大値を採る。                 ##
// ##         再生成 : python3 tools/sync_harness.py <本数>                 ##
// ##  ★ Parity Harness はこちらでは使わない。比較コードも入っていない。  ##
// ############################################################################

'''

def main():
    body = io.open(FULL, encoding='utf-8').read()
    assert '     shorttitle        = "ZONEv2-HARNESS",' in body, 'shorttitle line not found'
    assert '     dynamic_requests  = true\n )' in body, 'indicator() tail not found'
    out = body.replace('     shorttitle        = "ZONEv2-HARNESS",',
                       '     shorttitle        = "ZONEv2-SAFE",', 1)
    out = out.replace('     dynamic_requests  = true\n )',
                      '     dynamic_requests  = true,\n     calc_bars_count   = %d\n )' % BARS, 1)
    assert 'calc_bars_count   = %d' % BARS in out
    io.open(SAFE, 'w', encoding='utf-8').write(NOTE + out)
    print('wrote %s (calc_bars_count = %d)' % (os.path.basename(SAFE), BARS))

main()
