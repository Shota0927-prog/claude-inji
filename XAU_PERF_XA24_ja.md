# XA-24: ゴールド Strategy の実行時間エラー対策 (Engine version 3)

対象: `ZoneStrategyXAU.pine` (ZONE-ST、Short) / `ZoneStrategyXAULong.pine` (ZONE-ST-L、Long) /
`automation/xau_short/pine/ZoneStrategyXAU_Auto.pine` (自動化コピー) / `ZoneEnginePracticalXAUUSD.pine` (Library)。

- 報告されたエラー:
  - ZONE-ST: `RE10110 The script takes too long to execute. The time limit is 40 seconds.`
  - ZONE-ST-L: `RE10022 Error on bar 7875: Loop takes too long to execute (> 500 ms)`
    (`zn.f_finalizeCluster():917 / zn.f_buildClusters():1166 / zn.update():1525 / #main():748`)
- この文書の検証は Python の移植モデルと**合成データ**による。TradingView での実行・Profiler 計測・Strategy Tester の比較は**未実施**。
  したがって「エラー解消済み」「結果一致済み」とはまだ言えない (5 章の手順で確認が必要)。

## 1. 計測で確認したこと (原因)

### 1.1 /2 のソースの確認
- リポジトリの `ZoneEnginePracticalXAUUSD.pine` (version 2) は、エラーの行番号と完全に一致する
  (917 = `f_finalizeCluster` の member ループ `for j = 0 to n - 1`、1166 = `f_buildClusters` 最後の Cluster の finalize、
  1525 = `update()` の `int nZ = f_buildClusters(e, c)`)。
  公開済み /2 と同じソースである可能性は高いが、TradingView 上の /2 との byte 比較はできていない。
- Long の 748 行 (`zn.update`) は `is5mChart and barstate.isconfirmed` の中なので、毎 tick の Engine 更新は起きていない
  (履歴足は全て確定足なので 1 足 1 回)。

### 1.2 計測方法
- Engine version 2 の `update()` を Python へ忠実に移植した (`tests/pf_model.py`)。
  - 文の順序・浮動小数の式と加算順は Pine と同じ。
  - Raw Zone・Cluster・member・Track の数と、主要ループの反復回数を足ごとに数える。
- 入力は Short の初期値 (Long は Strong 9.0 だけ違う)。
- データは**合成の 1 分足** (セッション・週末あり、ボラティリティの局面あり)。
  - 5 分足・15 分 / 1 時間 / 4 時間 / 日足、NR-S1 / NR-A1 と同じ「確定した上位足の値を次の期間から渡す」形で feed を作る。
  - 実際の XAUUSD の値ではない。
- 実行: `python3 tests/pf_model.py seed=11 days=75 vol=0.8` (Short) / `cfg=long vol=1.6` (Long・高ボラ)。

### 1.3 結果 (合成データ・約 14,500 本の 5 分足。数値はこの移植の「反復回数」で、ミリ秒ではない)

Short 初期値・vol 0.8 の結果 (1,000 本ごとの区間):

| 区間 (足) | Raw Zone | Zone 数 | 最大 member | Track | f_findTrack 平均/最大 (回/足) | f_finalizeCluster member (回/足) |
|---|---|---|---|---|---|---|
| 0–999 | 51 | 19 | 8 | 34 | 354 / 654 | 57 (うち事前走査 28) |
| 4000–4999 | 120 | 54 | 6 | 123 | 4,366 / 6,094 | 194 |
| 7000–7999 (7875 を含む) | 120 | 59 | 8 | 106 | 4,501 / 5,512 | 206 |
| 12000–12999 | 107 | 50 | 9 | 126 | 4,121 / 6,300 | 193 |

Long 初期値・高ボラ (vol 1.6) の結果:

| 区間 (足) | Raw Zone | Zone 数 | 最大 member | Track | f_findTrack 平均/最大 (回/足) |
|---|---|---|---|---|---|
| 7000–7999 | 137 | 62 | 7 | 175 | 6,150 / 10,863 |
| 10000–10999 | 145 | 87 | 5 | 175 | 11,262 / 14,964 |

わかったこと:
- **毎足の処理で最も多いのは Track 照合 (`f_findTrack`)**。
  - Zone ごとに全 Track を走査するので、1 足あたり「Zone 数 × Track 数」。
  - Track は 500 足 (Zone State Retention) 照合されないまで残るので、履歴が進み値幅が広がるほど増える。
  - ボラティリティが高い局面で Raw Zone・Zone・Track が増え、1 足 1 万回を超える。
- **エラーが出た 917 行のループ (Cluster 内の member) は、1 回の呼び出しで最大 5〜10 回、1 足の合計でも 200〜260 回程度**。
  - 1 member あたり文字列比較を約 25 回行う。
  - Day/Swing Merge Nearby (初期値) では、同じ member を事前に 1 回ずつ走査している (member 反復が 2 倍)。
  - ループ自体の反復回数だけでは 500 ms を説明できない。
  - 917 行が報告されたのは「その時点で動いていたループ」であり、時間を使っている主因が別の場所にある可能性が高い
    (毎足の Zone / uid 配列 / Track uid 配列の新規作成が多く、実行環境のメモリ回収が重なった可能性も含む)。
  - これは推定であり、TradingView の Profiler でしか確定できない。
- Raw Zone は 200 件の上限で抑えられている。
  - 同じ Source の重複登録は ±Zone Half Width 内の寿命更新になる。
  - 期限切れ・古い Track の削除も event gate で動いている。
  - これらが無制限に増える不具合は見つからなかった。
- Strategy 側:
  - 毎確定足に全 Zone について `f_stZoneEval` が FVG 15 枠を 2 回走査する (`f_fvcZoneDisplay` と `f_zpoBestFvg`)。
    1 足あたり Zone 数 × 30 回で、Engine の finalize より多い。
  - Long の Entry D の待機検索は、候補 Zone が 1 足 0〜5 件 (Long 初期値、合成データ) なので小さい。

## 2. 以前は出なかった理由 (確認結果と未確認点)
- Engine は XA-6 (version 2) 以降変わっていない。
- 履歴足での Strategy の処理増は小さい:
  - XA-21〜23 のアラート・仮通知・ラベルは、主に確定足の発注時かリアルタイム tick でだけ動く
    (`f_stProvEval` は `not barstate.isconfirmed` のときだけ)。
  - `calc_on_every_tick = true` は履歴足の回数を変えない。
- 確認できた負荷の増え方: Track 照合の回数は「Zone 数 × Track 数」で、値動きの大きい期間が履歴に入るほど増える。
  2025〜2026 年のゴールドは値幅が大きく、読み込まれる履歴がその期間に移ったことで増えた可能性がある。
- 未確認:
  - TradingView 上での実時間。
  - 同じ履歴での以前の読み込みとの比較。
  - 読み込まれる足の本数の違い (プラン・Deep Backtesting)。
  - サーバー負荷による変動 (同じスクリプトでも限界付近ではエラーの出る足が変わることがある)。

## 3. 変更箇所と負荷が減る理由

### 3.1 Engine (ZoneEnginePracticalXAUUSD **version 3**。生成: `tests/xa_build.py` の `ENGINE_EDITS7`)
1. **Track 照合の二分探索** (`f_findTrack` / `update`)
   - 足ごとに 1 回、照合前の Track center を昇順に並べた index を作る (`array.sort_indices`)。
   - 各 Zone は `|center 差| <= clusterDist` の範囲だけを二分探索で見る。
   - 選ばれる Track は version 2 と同じ: このバー未照合・継続性あり・距離最小、同距離は index の小さい方
     (浮動小数の差は center について単調なので、範囲は並びの中で連続する)。
   - 照合済み Track・このバーで作った Track の扱いも同じ。
   - 反復は「Zone × Track」から「Zone × (log Track + 近くの Track)」へ。合成データの平均で約 1/10。
2. **Source 番号** (`f_kind`, `f_finalizeCluster`)
   - Raw Zone の作成時 (動的 Source は毎足の設定時) に、srcCat / srcId と設定 6 時間足との一致を番号で持たせる。
   - Cluster 集計では文字列比較をしない。
   - Source / HTF mask は bit ごとの有無を持ってループ後に 1 回だけ足す (f_setBit と同じ値)。
   - 時間足の設定が番号を作ったときと違う足では、全 Raw Zone の番号を作り直す (入力由来なので通常は最初の 1 回だけ)。
3. **Day High / Low の事前走査の廃止**
   - Cluster の DAY_HIGH / DAY_LOW の価格を `f_buildClusters` が member を加えるときに拾う。
   - 最後の 1 件を使うので、事前走査と同じ値になる。
   - 917 行のループ (Merge Nearby) の member 反復は 2 倍 → 1 倍。
4. **Track uid の複製削減**: 内容が同じなら `array.copy` しない。
   - Track は自分の配列を持ち続け、Zone と共有しない。
   - 毎足 Zone 数ぶんの配列作成が、合成データでは約 99% 減る。

変えていないもの:
- Source の登録順・Cluster の並べ替えと所属判定・加算順・Zone 上下限・Score / Strength。
- Track ID・Break / Flip / Touch・寿命と上限・古い Track の削除。
- 毎足の update (Source が変わらない足も省略しない)。
- 公開 API (型・関数名・引数) は互換。追加は RawZone / ZoneEngine の内部用フィールドだけ。

### 3.2 Strategy (Short / Long / 自動化コピー。生成: `xa_build.STRATEGY_EDITS24`、`xal_build`、`au_build`)
- `import sekine3310/ZoneEnginePracticalXAUUSD/2` → `/3`。
- `f_stZoneEval`:
  - 採用 FVG は `f_zpoBestFvg` で 1 回だけ選ぶ (`f_fvcZoneDisplay` と同じ候補・同じ比較)。
  - dScore / dStr は `f_fvcZoneDisplay` と同じ式で計算する。
  - FVG 枠の走査は Zone ごとに 2 回 → 1 回。
  - `f_fvcZoneDisplay` / `f_zpoBestFvg` は ZONE-P の byte コピーのまま残す。
- 入力・初期値・strategy() 設定 (calc_on_every_tick を含む)・売買・SATS・数量・注文・SL / TP・建値・アラート・
  再送防止・ラベルは変更なし。
- 自動化コピーの JSON・キー・cfg・SID (`XAU-SHORT|XA-23|AU-2`) も変更なし。

### 3.3 実施しなかったもの
- Entry D の Track ID 検索 (map 化):
  - 候補 Zone は Long 初期値で 1 足 0〜5 件 (合成データ)、待機はその数以下なので、効果が小さい。
  - 配列 3 か所の削除と map の同期が必要で、順序・整合の誤りの危険が効果を上回るため見送った。
- 禁止された方法 (Raw Zone 上限・寿命・計算期間・Zone / 候補の間引き・時間外の更新停止・calc_on_every_tick OFF・
  ラベル / アラート削除) は使っていない。
- 仕様変更はない。

## 4. 新旧結果の一致確認 (Python 移植モデル・合成データ。TradingView ではない)
`tests/pf_sim.py` (22 項目) で確認した:
- version 2 と version 3 の移植を同じ feed で同時に動かし、**毎足**、全 Zone・全 Track・イベント・Raw Zone が一致した。
  - Zone: 上下限 / Score / 内訳 / Strength / State / Flip / Track ID / member / mask / RN。
  - Track: ID / 状態 / Break / Retest / Flip / Touch / uid / 並び順。
  - イベント: Break / Flip。
- 対象の feed:
  - Short 初期値 8,200 本 (7875 本目を含む)。
  - Long 初期値 8,200 本。
  - 高ボラ 6,000 本、低ボラ 6,000 本。
  - 設定 19 通り (Role Reversal、Day/Swing、Accum モード、同じ時間足の重複設定、Cluster 2 / 12 / -1、継続率 0.01 / 1、
    上限 20、保持 10、HTF 全 ON、Source OFF など)。
  - 実行途中の時間足設定の変更。
- Track 検索 (30,000 件)・Cluster 集計 (20,000 件)・Strategy の FVG 評価 (20,000 件) をランダムに比べ、全件一致した。
  同距離・境界・照合済み Track・未知の Source 名・等しい時間足設定を含む。
- 変異試験: 同距離で後の Track を選ぶ、二分探索の開始位置ずれ、最初の Day High を使う、HTF bit の取り方の変更、
  FVG の Confluence の誤りをすべて検出した。
- 既存の全 fixture と生成元 (`python3 tests/xa_build.py` / `xal_build.py` / `au_build.py`) で、出力ファイルとの一致を確認した。
- 未確認 (TradingView が必要): 実データでの一致、Pine のコンパイル、Strategy Tester の取引一覧の一致、実行時間。

## 5. TradingView での確認手順と残る作業
1. **Library version 3 の公開** (/2 は残す):
   - Pine Editor に `ZoneEnginePracticalXAUUSD.pine` (この版) を開いて「Publish new version」を実行する。
   - 付いた番号が 3 でなければ、`tests/xa_build.py` の `IMPORT_XAE3` を直して次を実行する:
     - `python3 tests/xa_build.py; python3 tests/xal_build.py; python3 tests/au_build.py`
2. **Strategy の更新**: Short / Long (自動化コピーを使う場合はそれも) をこの版に貼り替えて保存する。
   - import 先は自動では変わらないので、貼り替えが必要。
   - 自動化コピーを更新したら、アラートを作り直す (README_ja 13 章 6 と同じ手順。古いアラートは古いコードで動き続ける)。
3. **新旧比較** (同じ OANDA:XAUUSD 5 分足・同じ入力・同じ履歴の開始):
   - 旧 (/2 の現行版) と新 (/3) を別チャートに置き、Strategy Tester の「List of Trades」を書き出して比べる。
     - 比べる列: Entry / Exit の時刻・価格・数量。
     - 旧版がエラーになる場合は、Deep Backtesting の期間を 7875 本目より手前にして比べる。
   - 確定ラベルとアラートの記録 (同じ足・同じ価格) も比べる。
4. **Profiler で負荷を測る** (Pine Editor の「Profiler mode」):
   - 新旧の上位の行と時間を記録する。新版では `f_findTrack` の時間が大きく減ることを確認する。
   - Profiler 自体にも負荷があるので、測定用の読み込みと通常の読み込みを分ける。
5. **再読み込みを複数回**行う:
   - Short / Long の初期設定で RE10110 / RE10022 が出ないことを確認する。
   - 7875 本目を含む期間と、それより長い履歴 (Deep Backtesting) の両方で確認する。
6. それでもエラーが出る場合:
   - Profiler の上位の行を報告してもらえれば、次の削減対象を決める。
   - 残る候補: Cluster ごとの Zone / uid 配列の新規作成、継続性判定の `array.includes`、Strategy の Zone 走査。
