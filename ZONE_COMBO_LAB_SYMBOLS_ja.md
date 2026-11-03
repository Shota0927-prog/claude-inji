# Zone Combo Lab 銘柄版 (LBS-1) — BTCUSD / GBPJPY / USDJPY / EURUSD / GBPUSD

対象ファイル: `ZoneComboLabBTCUSD.pine` / `ZoneComboLabGBPJPY.pine` / `ZoneComboLabUSDJPY.pine` / `ZoneComboLabEURUSD.pine` / `ZoneComboLabGBPUSD.pine`
基準: `ZoneComboLabXAU.pine`（LAB-5・Zone タッチ通知を含む版、3be168d）。生成: `tests/lbs_build.py`（原版 + 決まった編集だけ）。テスト: `tests/lbs_sim.py`。

> **TradingView 実機でのコンパイル・表示・バックテスト・通知は未確認。** 下の確認は、静的照合と Pine の換算区間 + ロジック区間を機械変換して
> 実行したモデル検証（PINE_NOT_VERIFIED）。

## 1. 原版からの差分（これ以外は byte 一致: LBS-01 / LBS-02）

| 項目 | 内容 |
|---|---|
| 名称 | `title` = `Zone Combo Lab <銘柄>`、`shorttitle` = `ZCL-<銘柄>`、先頭の説明に「■ 銘柄版」を追加 |
| 価格幅 9 項目 | 入力名に `In` を付け（例 `zHalfIn`）、表示単位を pips（為替）/ $（BTC）に変更。入力の直後の `LBS Unit` 区間で `zHalf = zHalfIn × LBS_PIP` と**一度だけ**換算し、FVG 検知関数へ渡す最小幅・ロジック区間は換算後の名前（原版と同じ名前）をそのまま使う |
| 1 pip（固定定義） | GBPJPY / USDJPY 0.01、EURUSD / GBPUSD 0.0001、BTCUSD 1 ドル = 価格差 1（`syminfo.mintick` からは求めない） |
| 初期 ON / OFF | 水平線 1H・4H OFF / 日足・週足 ON、出来高POC 1H OFF / 4H・日足・週足 ON、ZE フィボ検知 ON（4H・日足を採用）、Zoneタッチ通知 ON。エントリー条件の「ZE フィボ」は原版どおり OFF |
| lot | `mmLotOz`（1 lot のオンス数 100）→ `mmLotSize`（為替「1 lot の通貨数量」100,000 / BTC「1 lot の BTC 数量」1）。式は原版のまま |
| 価格の表記 | TP の文面・TP 変更 / 到達の通知・エントリーの通知とラベル（判断・SL）・タッチ通知の価格帯の 7 か所を `format.mintick` に。lot・RR・%・円は原版の書式 |

価格幅の初期値（すべて入力で変更可。最大 SL の使う / 使わないは原版どおり OFF）:

| 項目 | BTCUSD ($) | GBPJPY | USDJPY | EURUSD | GBPUSD (pips) |
|---|---:|---:|---:|---:|---:|
| Zone 共通半幅 | 100 | 4 | 3 | 2 | 3 |
| 水平線の統合距離 | 250 | 10 | 8 | 5 | 8 |
| 長期 FVG 最小幅 | 150 | 6 | 5 | 3 | 5 |
| 5分足 FVG 最小幅 | 50 | 2 | 1.5 | 1 | 1.5 |
| SATS 近接許容距離 | 50 | 2 | 1.5 | 1 | 1.5 |
| Zone 外側への SL 余白 | 250 | 10 | 8 | 5 | 8 |
| 最大 SL 距離 | 2000 | 80 | 60 | 40 | 60 |
| 固定幅の建値移動 | 750 | 30 | 20 | 15 | 20 |
| TP 変更通知の幅 | 250 | 10 | 8 | 5 | 8 |

資金管理（30 万円 × 3 % の単利・円口座）・新規エントリー時間（日本時間 09:00〜翌 02:00、BTC も同じ）・最小 lot / lot 刻み 0.01 は原版どおり。
**BTC の最小 lot・lot 刻み 0.01 は暫定の初期値**（XS の実口座の仕様は未確認）。

## 2. 貼り付け

各銘柄の 5分足チャートに、既存の `MtfPocFeedXAU.pine` と `LongFibWave.pine`（どちらも変更なし・共用）と銘柄版 Strategy を追加し、
Strategy の「02d · ZD 出来高 POC」「02e · ZE フィボ」の各 13 項目に同じ名前の系列を選ぶ（名前・順序・protocol 10001 / 20001・接続確認・
異常時の処理は原版と同じ）。ZE フィボ検知が初期 ON のため、LongFibWave を接続しないと「ZE 接続」で新規発注が止まる（原版で ZE を ON にしたときと同じ）。

## 3. テスト（`python3 tests/lbs_sim.py`、`--all` で差分照合を 5 銘柄すべてに）

| ID | 内容 |
|---|---|
| LBS-01 / 02 | 5 ファイル = 原版（3be168d）+ 決まった編集。ロジック区間は 5 銘柄で同一、原版との差は lot の名前と価格の書式だけ |
| LBS-03 | ゴールド版・通常版（ZoneStrategy* / ZoneEnginePractical* / ZoneVisual* / AccumStrategyXAU / MtfPocDetector）・外部インジ（MtfPocFeedXAU / LongFibWave）が変更前と同一 |
| LBS-04 | 初期値（表の 9 項目・ON / OFF・lot・資金・時間帯）、その他の入力は原版の初期値、単位の表記、BTC の暫定表記 |
| LBS-05 / 06 | 換算は 1 回: 換算後の名前の代入は換算区間の 1 回だけ、`In` は換算区間でだけ読む、`LBS_PIP` は換算区間の外にない、FVG 検知へ換算後の値。換算区間を実行して EURUSD 2 pips = 0.0002、USDJPY 3 pips = 0.03 など |
| LBS-07 | 既存 fixture への登録（`tests/lab2_build.py` / `tests/cad_adapt.py` の編集が正確・元に戻すと変更前と一致） |
| LBS-10 / 11 | lot・qty: 損失予算 9,000 円 → 銘柄通貨（円建ては × 1、ドル建て・BTC は ÷ レート 150 / 140 / 155 / 160）→ 0.01 lot 切り捨て。SL での損失は予算以内。pointvalue 10 で qty が 1/10。分割（四捨五入した累積の差 60 / 20 / 20）の各段・合計・台帳 1 件・1R |
| LBS-20 | lab_sim のシナリオ（ゴールド版での 144 実行・ランダム系列を含む）を銘柄版のロジックで同じ入力（換算係数 1）で再実行し、注文・約定・待機・タイミング・段・台帳・描画が一致（文面は価格の書式だけ違う） |
| LBS-30〜33 | 各銘柄の価格帯で: 4H POC の受信 → ヒゲ接触 → TC → SHORT → TP1（日足 POC）で利確 / 逆行で SL（−1R、損失は予算以内）、保有中の日足 POC の入れ替えで TP 更新と TP 変更通知、LongFibWave の波の受信・入れ替え（4 水準）・フィボ帯のタッチ通知、週足 POC の受信足での接触、通知 ON / OFF で売買が同じ |
| LBS-34 / 40 | 価格の書式（5 / 3 / 2 桁）、換算・書式・lot の変異（換算漏れ・二重換算・別の pip・`#.##`・ゴールドの lot）がどれも検出される |

## 4. TradingView で未確認の事項

1. コンパイル（`format.mintick`、`float LBS_PIP = …` を使う入力の換算、request.security への換算後の値の受け渡し）。
2. 各銘柄の `syminfo.mintick`・`syminfo.pointvalue`・`strategy.convert_to_symbol / convert_to_account` の実際の値（テストは mintick を
   BTC 0.01 / JPY ペア 0.001 / USD ペア 0.00001、pointvalue 1、レートは固定値で模擬）と、Strategy Tester の qty（通貨数 / BTC 数）の扱い。
3. BTC の最小 lot・lot 刻み（暫定 0.01）が XS の口座仕様に合うか。
4. 各銘柄の 5分足で MtfPocFeedXAU / LongFibWave の接続（ZD 受信・ZE 受信の表示）、帯・ラベル・集計表の表示、実際の通知の文面。
5. 損失予算がちょうど割り切れる SL 距離では、価格差の浮動小数の誤差で 1 刻み少なくなることがある（原版と同じ式の性質。予算は超えない）。
