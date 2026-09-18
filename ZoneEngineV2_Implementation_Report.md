# ZoneEngine v2 Implementation Report

作成日: 2026-09-18
対象: XAUUSD / TradingView Pine Script v5
基準仕様: `Zone_definition_spec_v2.md`
実装指示: `Claude_ZoneEngine_v2_implementation_instructions.md`

---

## Deliverables

| ファイル | 種別 | 行数 | 内容 |
|---|---|---:|---|
| `ZoneEngineV2.pine` | Pine v6 library (`ZoneEngineV2`) | 4725 | v2 定義の Zone Engine 本体。 |
| `ZoneEngineV2_VisualHarness_FULL.pine` | Pine v6 indicator (**本番**) | 1189 | 全履歴。`calc_bars_count` なし。これが原本。 |
| `ZoneEngineV2_VisualHarness_SAFE.pine` | Pine v6 indicator (検証用 / 自動生成) | 1215 | FULL から `tools/sync_harness.py` で生成。`calc_bars_count` だけ違う。 |
| `tools/sync_harness.py` | 生成スクリプト | - | SAFE を FULL から作る。`python3 tools/sync_harness.py <本数>` |
| `ZoneEngineV2_ParityHarness.pine` | Pine v6 indicator (検証専用) | 715 | Version 3 と新版を照らす。**Phase 3D 以降は対象外 / 未変更**。 |
| `baseline/*.pine` | Pine v6 (A/B 用) | - | 最適化前 (commit `d528a1e`) の控え。 |
| `ZoneEngineV2_Implementation_Report.md` | ドキュメント | - | 本書。 |

旧 `ZoneEngineV2_VisualHarness.pine` は `..._FULL.pine` へリネーム。
旧 `profiler/ZoneEngineV2_VisualHarness_Profiler.pine` は SAFE 版が役割を兼ねるため削除
(同一内容のコピーを 3 つ維持すると古い方を計測してしまうため)。

既存ファイルの変更: **なし**。
- 旧 `ZoneEngine` (v9 / v10 / v11) のソースはこのリポジトリに存在せず、1 文字も変更していない。
- 旧 `FVG + Zone Engine Strategy` (Main Strategy) も変更していない。
- リポジトリ内の既存ファイル `indicator.pine` (無関係のテンプレート) も変更していない。
- v2 は新しい Library 名 (`ZoneEngineV2`) で、旧 Library を import している既存スクリプトへ影響しない。

Harness の import 行は `import sekine3310/ZoneEngineV2/4 as zn2`。
直前の公開が `/3` (Phase 3A) だったので連番として `/4` を入れているが、
**Publish 直後に TradingView が実際に発行した番号を確認して、違っていたら直すこと**。
profiler コピーと Parity Harness の vB も同じ番号へ揃える。

---

## Compile status

**Pine Editor 1 回目: エラー 9 件 → 修正済み。2 回目のコンパイルは未確認 (この実装環境から Pine Editor を開けないため)。**

### 1 回目のコンパイル結果 (利用者側で実施)

`Cannot shadow the built-in variable` 系 9 件。原因は Pine 組み込み名をローカル変数 / 引数 / UDT フィールドとして
再定義していたこと。判定ロジックを一切変えずに名前だけを変更して解消した。

| # | 箇所 | 変更前 | 変更後 |
|---:|---|---|---|
| 1-5 | `f_qualityMa` / `f_qualitySwing` / `f_qualityAccum` / `f_qualityTimeHl` / `f_qualityFvg` | `bool high` | `bool isHighQuality` |
| 6-7 | `f_touchIntersect` の引数 | `float low, float high` | `float barLow, float barHigh` |
| 8 | `TouchMark` のフィールド | `int time` | `int touchTime` |
| 9 | `ZoneEvent` のフィールド | `int time` | `int eventTime` |

追従した参照: `high := ...` / 戻り値の `high`、`f_touchIntersect` 内部の `low` / `high`、
`TouchMark.new(time = ...)` と `t.time` / `tm.time`、`ZoneEvent.new(time = ...)`、
Harness の `ev.time`。呼び出し側へ渡す値 (`f.baseLow` / `f.baseHigh` / `f.baseCloseTime`) と
判定式は変更していない。

`open` / `high` / `low` / `close` / `time` / `time_close` / `volume` / `bar_index` を
宣言名・引数名・UDT フィールド名として使っている箇所が他に無いことを両ファイルで機械走査し、0 件を確認した
(`maPackV2` / `pivotPackV2` / `accumPackV2` / `fvgPackV2` 内の `high` / `low` / `close` / `time` は
外部足コンテキストで価格データを読んでいる正規の使用なので変更していない)。

### 2 回目のコンパイル結果 (利用者側で実施) と v6 移行

`Script has too many local scopes: 774. The limit is 550` (v5 のスコープ総数上限)。
仕様条件やロジックを削って 550 以下へ収める対応はせず、**両ファイルを Pine v6 へ移行**して解消する
(v6 はこのスコープ総数上限が撤廃されている)。

| 変更 | ファイル | 変更前 | 変更後 |
|---|---|---|---|
| バージョン宣言 | `ZoneEngineV2.pine` L54 | `//@version=5` | `//@version=6` |
| バージョン宣言 | `ZoneEngineV2_VisualHarness.pine` L34 | `//@version=5` | `//@version=6` |
| bool の `nz()` (v6 非対応) | `ZoneEngineV2.pine` `accumPackV2` L1045 | `bool endedNow = nz(cond[2], false) and not nz(cond[1], false)` | `bool endedNow = cond[2] and not cond[1]` |
| bool の `nz()` (v6 非対応) | `ZoneEngineV2.pine` `accumPackV2` L1050 | `if nz(cond[i], false)` | `if cond[i]` |

v6 では bool が `na` にならず履歴不足は `false` になるため、この 2 箇所は従来の `false` フォールバックと
同じ挙動のまま。Zone / Root / Touch / Break / Flip / Generation の判定式、ループ、配列上限、保持履歴は
1 箇所も変更していない。

`nz(boolValue, false)` / `na(boolValue)` / `fixnan(boolValue)` が他に残っていないことを両ファイルで確認
(`nz()` の残り 30 箇所はすべて int / float、`na()` は float・int・UDT・table・label が対象。`fixnan` は不使用)。
v6 で厳格化された組み込み名シャドーイングも、広い組み込み名リスト (価格・時刻・名前空間・定数系) で
再走査して 0 件を確認した。

v6 の遅延評価 (`and` / `or` / 三項) は、既に「na オブジェクトや負 index を第 2 項で評価しない」形へ
分解済みのため挙動は変わらない。

**Harness の import 番号**: `ZoneEngineV2.pine` を v6 で再 Publish したあと、
`import shota0927-prog/ZoneEngineV2/<新しい番号> as zn2` へ差し替えること (現状は `/1` のまま)。

### 静的確認 (共通)

この実装環境から TradingView / Pine Editor へアクセスできないため、「コンパイル済み」とは書かない。
実施した静的確認は次のとおり。

1. 全関数・全 UDT の宣言順序 (Pine は前方参照不可) を機械的に検査。
2. 全関数呼び出しの引数個数を定義と機械照合 (不一致 0 件)。
3. 継続行のインデントが 4 の倍数になっていないこと (Pine の継続行規則) を機械検査 (違反 0 件)。
4. Harness が参照する `zn2.*` の関数名・型名・Engine フィールド名が Library の export と一致することを機械照合 (欠落 0 件)。
5. Pine 固有の危険パターンを手作業で洗い出して除去。
   - `array.get(...).field := x` 形式の代入 → 一旦ローカル変数へ受けてから代入する形へ全置換。
   - Pine は `and` / `or` を短絡評価しないため、`na` オブジェクトや負 index を第 2 項で参照していた箇所を分岐へ分解 (`f_pickBestWindow` / FVG attach / Pass 2 primary 選択 / Split 親選択)。
   - 三項演算子の両辺が評価され得るため、`cond ? array.get(a, i) : na` 形式 (i が -1 になり得る) を `if` へ分解。
   - `array.new_*()` のサイズ引数を `int()` で明示。
   - `for i = 0 to n - 1` は n = 0 で逆方向に 1 回まわるため、全ループを `if n > 0` で保護。
   - 配列要素の削除は必ず降順ループ。
   - `var` / `varip` は Library 内で未使用 (状態はすべて Engine オブジェクトが保持)。
6. 未処理の TODO / FIXME / ダミー値 / 未接続の疑似実装が残っていないことを全文検索で確認 (0 件)。

**未確認で残るリスク** (Pine Editor が必要):
- Pine のスクリプトサイズ上限 (local scope 数 / 変数数) に収まるか。
- `request.security` へ渡す各 pack の外部要素数上限 (1 式あたり 254) — 各 pack は input を直接参照せず引数だけを受けるため超過しないと考えているが未検証。
- 可変 index の履歴参照 (`cond[i]` / `open[i]`) に対する `max_bars_back` の自動推定。`accumPackV2` は定数上限ループ (400 / 600) に抑えてある。

---

## Implemented milestones

| Milestone | 状態 | 実装箇所 (ZoneEngineV2.pine) |
|---|---|---|
| M1 骨格 (定数 / Cfg / Root / Side / Snapshot / Core / Engine / View / Event / Factory / 名称変換 / Cfg validation / duplicate base bar guard) | 完了 | 01, 02, 03, 10, `update()` 冒頭 |
| M2 Root 検出 (MA / Swing 同一イベント統合 / Accum Candidate→Confirmed / 時間高安 / 心理価格合成 / FVG 形成・Fresh・構造無効化) | 完了 | 04, 05.1〜05.7 |
| M3 クラスタと品質 (Side 資格 / Dense 候補 / Base Strong / 競合割当 / FVG 局所化・重複・Broad context / ZoneCore 統合 / Reference Price) | 完了 | 06.1〜06.8, 07.1 |
| M4 Touch と Weak (Waiting / Armed / TouchStartSnapshot / Episode / Reset / TouchCount / WeakDepth / Grade / Fresh 3 種) | 完了 | 08.1〜08.4, 08.7 |
| M5 Break 系 (Local Break / GapBreak / BreakSnapshot / FlipAttempt / FlipConfirm / Reclaim / Inverse FVG) | 完了 | 08.1, 08.5, 05.5 |
| M6 Topology と世代 (LiveStructure / PendingTopology / Identity / Merge / Split 履歴割当 / PendingGeneration / 新世代 / Dormant / 保存整理) | 完了 | 07.2〜07.6, 08.6, 05.8, 09 |
| M7 Harness と受け入れ確認 (Zone 描画 / Label / table / Event 表示 / テスト / Report) | Harness 完了 / 受け入れテストは未実行 (下記) | `ZoneEngineV2_VisualHarness.pine`, 本書 |

仮実装を次の Milestone へ持ち越した箇所は無い (Phase を Waiting 固定にしたままの疑似実装等は残していない)。

### 実装した v2 の要点

- Score / Strength 整数は存在しない。`Grade` は「Unavailable → Weak → Strong → Neutral」の順序判定だけで決まる。
- Support View と Resistance View は 1 つの `ZoneCore` の中に別インスタンスで持ち、物理 Zone を二重生成しない。
- `NativeRange` (FVG 固定範囲) と `EffectiveZoneRange` (判定範囲) を別フィールドで保持。
- `TouchStartSnapshot` は開始後に `deepestClose` / `maxDepthPct` 以外を書き換えない。
- `BreakSnapshot` が Flip / FlipAttempt / Reclaim の唯一の価格基準。
- `Weak` は `weakByTouch` / `weakByDepth` として Side 別に永続し、新世代開始以外では解除されない。
- 価格比較は `f_geT` / `f_leT` / `f_gtT` / `f_ltT` / `f_eqT` を通し、必ず最小ティックへ正規化してから比較する。
- 同カテゴリ Root 数は C を増やさない。心理価格は C に数えるが H にならない。
- Dense Base Strong core を先に確定し、core 外 Root を後付けして幅を広げない。
- `f_candBetter()` が唯一の候補比較関数 (C 降順 → H 降順 → 幅昇順 → core 成立時刻昇順 → 最小 Root ID 昇順)。

### 旧ロジックの非移植 (静的検索で確認)

`score` / `baseSum` / `reaction` / `confluence` / `flipBonus` / `zoneHalfWidth` / 加重平均 Center / ATR による Zone 幅・Break 幅 / BOS / 上位足環境フィルター / Strategy の勝敗・TP・SL・RR は `ZoneEngineV2.pine` に 1 つも存在しない。ATR は `f_accumCondV2()` (Accum 形成条件) の内部だけで使い、確定後の Root / Zone へ値を持ち出していない。FVG 50% は Library に一切現れず、Harness の表示専用ライン (ラベルに `DISPLAY ONLY`) だけが使う。

---

## Public API

```text
newCfg()                                   -> ZoneCfg
newEngine()                                -> ZoneEngine
newFeed()                                  -> ZoneFeed
validateCfg(cfg)                           -> [bool, string]
constOf(key)                               -> int            // 定数値を名前で取得

maPackV2(len1, len2, slopeLb)               -> [ema1, d1, ema2, d2, confirmedTime]
pivotPackV2(len)                            -> [ph, phOrigin, phOriginEnd, phConfirm,
                                                pl, plOrigin, plOriginEnd, plConfirm]
accumPackV2(rangeLen, baseLen, atrLen, minUpper, minLower, maxRun,
            atrMult, barRatioMax, driftMax)  -> [newConfirmedBox, boxTop, boxBottom,
                                                boxId, candidateStartTime, confirmedTime]
fvgPackV2()                                 -> [bullNew, bullTop, bullBottom, bullOrigin, bullConfirm,
                                                bearNew, bearTop, bearBottom, bearOrigin, bearConfirm,
                                                srcHigh, srcLow, srcClose, srcOpenTime, srcCloseTime]

feedSwing(feed, tfCode, newBar, ph, phOrigin, phOriginEnd, phConfirm,
          pl, plOrigin, plOriginEnd, plConfirm)   -> int
feedAccum(feed, tfCode, newBar, newBox, boxTop, boxBottom, boxId, candStart, confirmTime) -> int
feedFvg(feed, tfCode, newBar, bullNew, ..., srcCloseTime)                                 -> int

update(engine, cfg, feed)                  -> int viewCount

viewCount(engine) / viewAt(engine, i)      -> int / ZoneView
eventCount(engine) / eventAt(engine, i)    -> int / ZoneEvent
rootCount(engine) / rootAt(engine, i)      -> int / RootDebugView
coreCount(engine) / endedGenerationCount(engine) -> int
rootLabelMaskAt(engine, i)                 -> int

phaseName / gradeName / densityName / weakReasonName / categoryMaskName /
eventName / sideName / rootStateName / fvgDirectionName / categoryName /
subtypeName / tfName / timeLabelName       -> string
```

Export 型: `ZoneCfg` / `ZoneFeed` / `SwingIn` / `AccumIn` / `FvgIn` / `Root` / `TouchMark` /
`TouchStartSnapshot` / `BreakSnapshot` / `SideHistory` / `SideViewState` / `ZoneCore` /
`ZoneEvent` / `ZoneView` / `RootDebugView` / `ZoneEngine`。

`ZoneView` の出力: `coreId` `generationId` `side` `effectiveBottom` `effectiveTop` `referencePrice`
`phase` `grade` `cCount` `hCount` `density` `baseStrong` `currentTouchNo` `upcomingTouchNo`
`zoneFresh` `sideFresh` `weakReason` `maxDepthPct` `isBroadContext` `fvgDirectionMask`
`fvgRootCount` `fvgFreshCount` `fvgStructuralStateMask` `eligible` `dormant` `pendingTopology`
`pendingGeneration` `catMask` `highMask` `touchStartGrade` `snapshotBottom` `snapshotTop`
`physBottom` `physTop` `flipAttemptCount` `rootSummary` `categorySummary`。

旧 `TradePlan` / Structural SL・TP API は v2 Library に入れていない。
View は該当する Zone を全件返し、距離や Grade で 1 件へ絞らない。

---

## Storage and request usage

### request.security (Harness / 既定 6 call ← 旧 10 call)

既定設定 (MA 1 / Swing 5、15、60 / Accum 60、240、D / FVG 60、240、D)

| 用途 | 時間足 | call 数 | lookahead |
|---|---|---:|---|
| MA (`maPackV2`) | 1分 | 1 | off |
| Swing #1 (`pivotPackV2`) | 5分 | 1 | off |
| Swing #2 (`pivotPackV2`) | 15分 | 1 | off |
| Swing #3 + Accum #1 + FVG #1 (`swingAccumFvgBundleV2` / UDT) | 1時間 | 1 | off |
| Accum #2 + FVG #2 (`accumFvgBundleV2` / UDT) | 4時間 | 1 | off |
| Accum #3 + FVG #3 (`accumFvgBundleV2` / UDT) | 日足 | 1 | off |
| Base 5分 | (チャート足 built-in) | 0 | - |
| **合計** | | **6** (旧 10) | |

グループごとの場合分け (時間足設定の自由度は落とさない)

| グループ | 時間足の一致状態 | 呼ぶ Pack | request.security | time(tf) |
|---|---|---|---:|---:|
| Group 60 | Swing#3 = Accum#1 = FVG#1 | `swingAccumFvgBundleV2` (UDT) | 1 | 1 |
| Group 60 | Accum#1 = FVG#1 のみ | `accumFvgBundleV2` (UDT) + `pivotPackV2` | 2 | 2 |
| Group 60 | 不一致 | `pivotPackV2` + `accumPackV2` + `fvgPackV2` | 3 | 3 |
| Group 240 | Accum#2 = FVG#2 | `accumFvgBundleV2` (UDT) | 1 | 1 |
| Group 240 | 不一致 | `accumPackV2` + `fvgPackV2` | 2 | 2 |
| Group D | Accum#3 = FVG#3 | `accumFvgBundleV2` (UDT) | 1 | 1 |
| Group D | 不一致 | `accumPackV2` + `fvgPackV2` | 2 | 2 |

これに MA 1 本と Swing #1 / #2 の 2 本 (time も 2 本) が常に加わるので、

| 時間足パターン | request.security | time(tf) |
|---|---:|---:|
| 全グループで完全一致 (既定設定) | **6** | **5** |
| Group 60 が Accum+FVG のみ一致、240 / D は一致 | 7 | 6 |
| Group 60 不一致、240 / D は一致 | 8 | 7 |
| Group 60 不一致、240 不一致、D 一致 | 9 | 8 |
| 全グループ不一致 (最悪) | **10** (= 旧と同じ) | **9** (= 旧と同じ) |

- `swingAccumFvgPackV2()` / `accumFvgPackV2()` は既存の `pivotPackV2()` /
  `accumPackV2()` / `fvgPackV2()` をそのまま呼んで戻り値を連結するだけで、
  計算内容も順序も個別に呼んだときと完全に同じ。
- まとめる条件は「時間足文字列が完全に一致すること」。
  `timeframe.in_seconds()` ではなく文字列で見ているのは、"1440" と "D" が
  秒数では同じでも足の区切り方が違うから。
- 各グループは `if / else if / else` なので同時に成立せず、まとめたデータを
  別 request で二重に取ることはない。
- `time(tf)` も同じグループ内で共有する。文字列が同じなら `time()` の値も
  必ず同じなので完全に同値。merge フラグは入力だけで決まりバーをまたいで
  変わらないため、三項演算子の遅延評価で `time()` の履歴がすれることはない。
  `ta.change()` は全て global scope で無条件に呼んでいる。
- すべての pack は「完全に確定した 1 本」しか返さない (内部で index [1] 以降のみ参照)。
  Harness は `ta.change(time(tf)) != 0` でその時間足の確定を検出し、1 回だけ Feed へ入れる。
- Library は `request.*` を 1 つも呼ばない。
- 注意 (既存の挙動と同じ) : 別スロット同士 (例として Accum #1 と Accum #2) を
  同じ時間足にした場合は、その 2 本は別 request のままになる。
  これは Version 3 でも同じで、既定設定では発生しない。スロットを越えた統合は
  組み合わせが爆発して割当先を間違えるリスクが高いため入れていない。
- 5分 Swing だけはチャート足と同じ時間足だが、位相を他 TF と揃えるため同じ
  `pivotPackV2` 経路を使っている。

### request.* の tuple 要素数 (上限 127)

Pine の `request.*` には「スクリプト内の全 request の tuple 要素数の合計」に
127 の上限がある。`if / else` で実行時に 1 分岐しか通らなくても、input で
分岐する以上はソース上の全分岐が合算される。
そのため統合 Pack は **UDT を 1 つ返す形 (tuple 要素 1)** を使う。

新規の export 型と API (中身は既存 Pack をそのまま呼んで詰め直すだけ)

| 名前 | 中身 | フィールド | tuple 要素 |
|---|---|---:|---:|
| `SwingAccumFvgBundle` | Swing 8 + Accum 6 + FVG 15 | 29 (bool/int/float のスカラーのみ) | — |
| `AccumFvgBundle` | Accum 6 + FVG 15 | 21 (同上) | — |
| `swingAccumFvgBundleV2()` | `pivotPackV2` + `accumPackV2` + `fvgPackV2` | → `SwingAccumFvgBundle` | **1** |
| `accumFvgBundleV2()` | `accumPackV2` + `fvgPackV2` | → `AccumFvgBundle` | **1** |

tuple 版 (`swingAccumFvgPackV2` / `accumFvgPackV2`) は互換性のため export したまま残してあるが、
Visual Harness / Parity Harness / profiler コピーの `request.security` からは呼んでいない。

#### ファイルごとの tuple 要素合計

| ファイル | UDT 化前 | UDT 化後 | 上限 127 |
|---|---:|---:|---|
| `ZoneEngineV2_VisualHarness.pine` | 192 | **104** | OK |
| `ZoneEngineV2_ParityHarness.pine` | 163 | **95** | OK |
| `profiler/...Profiler.pine` (本番と同一) | 192 | **104** | OK |

Visual Harness の内訳 (ソース上の全分岐の合算)

| 箇所 | 内容 | 要素 |
|---|---|---:|
| 固定部分 | `maPackV2` 5 + `pivotPackV2` 8 × 2 | 21 |
| Group 60 ① | `swingAccumFvgBundleV2` | 1 |
| Group 60 ② | `pivotPackV2` 8 + `accumFvgBundleV2` 1 | 9 |
| Group 60 ③ | `pivotPackV2` 8 + `accumPackV2` 6 + `fvgPackV2` 15 | 29 |
| Group 240 ① / ② | `accumFvgBundleV2` 1 / (`accumPackV2` 6 + `fvgPackV2` 15) | 22 |
| Group D ① / ② | 同上 | 22 |
| **合計** | | **104** |

Parity Harness の内訳

| 箇所 | 内容 | 要素 |
|---|---|---:|
| Version 3 側 (個別 Pack / 変更なし) | `maPackV2` 5 + `pivotPackV2` 8×3 + `accumPackV2` 6×3 + `fvgPackV2` 15×3 | 92 |
| 新版側 (UDT) | `swingAccumFvgBundleV2` 1 + `accumFvgBundleV2` 1×2 | 3 |
| **合計** | | **95** |

#### UDT が na のとき

HTF の確定足がまだ無い間は UDT 自体が `na` になるので、Harness は
`if not na(bundle)` で囲ってからフィールドを読む。`na` のときは宣言時の既定値
(float / int は `na`、bool は `false`) がそのまま残るので、tuple 版で各要素が
`na` / `false` で返ってくるのと同じ状態になる。

### 保存上限と診断値

| 設定 | 初期値 |
|---|---:|
| `maxSwingRoots` | 180 |
| `maxAccumBoxes` | 60 (Box 数。境界 Root は最大その 2 倍) |
| `maxFvgRoots` | 120 |
| `maxTimeRoots` | 32 |
| `maxZoneCores` | 80 |
| `maxEndedGenerations` | 30 |
| `maxTouchMarksPerCore` | 64 |
| `dormantDistance` | 500.0 |

- 削除対象から常に除外するもの: ActiveTouch / Broken / FlipWait / PendingTopology / PendingGeneration /
  BreakSnapshot 保持中の Core に関係する Root、FVG の Invalidated / InverseWait、現在期間の時間高安 Root。
- Accum は Box 単位で削除する (上限・下限の片側だけを残さない)。
- 削除・切り詰めが起きたら `storagePruned` / `prunedRootCount` / `prunedZoneCount` /
  `touchHistoryTruncated` を Engine へ残し、`EV_STORAGE_PRUNE` を出す。Harness の Debug table に常時表示。
- Dormant は履歴削除ではない。Core ID / 世代 ID / 消耗履歴を保ったまま計算と表示を休止する。

### 実行コストのための実装

- `map<int,int>` による Root ID → index 索引 (`f_reindexRoots`)。索引が古い場合は線形探索へフォールバックするので結果は常に同じ。
- クラスタリング対象は現在価格から `dormantDistance` 以内の Root だけ (窓の外の Zone は Dormant として保持)。
- Dense Base Strong の探索は 1 バー 1 Side あたり最大 12 core まで。
- `ZoneReferencePrice` は候補探索中は計算せず、View へ適用するときだけ計算する。
- 表示用文字列 (`rootSummary` / `categorySummary`) は `barstate.islast` のバーだけ組み立てる。

---

## Acceptance test results

**結論: 75 件すべて `NOT RUN`。**

理由: この実装環境から TradingView へアクセスできず、Bar Replay と Debug 出力による確認 (指示書 24 章が
要求する確認方法) を実行できない。Pine の実行結果を伴わない判定を `PASS` と書くことはしない。

各ケースについて、判定に使う実装箇所と静的に確認した内容を以下に示す。実際の PASS / FAIL 判定は
XAUUSD 5分足チャートで Harness を実行し、Bar Replay と Debug table / Event log で行うこと。

### A. 境界値 (1-9)

| # | 期待 | 状態 | 実装箇所 / 静的確認 |
|---:|---|---|---|
| 1 | Effective 幅 = M ちょうどで同一通常 Zone 可 | NOT RUN | `f_buildCand` の `f_leT(width, clusterMaxWidth)` (等号を狭い側へ含む) |
| 2 | 幅 = denseWidth ちょうどで High Density | NOT RUN | `f_buildCand` の `f_leT(width, f_denseWidth(c))` |
| 3 | ResetDistance ちょうどで Reset / Armed 成立 | NOT RUN | `f_episodeStep` の `f_geT(close, top + reset)` / `f_finalizeSide` の distOk |
| 4 | WeakDepth ちょうどで Weak | NOT RUN | `f_episodeStep` の `depth >= c.weakDepthPct` |
| 5 | Support Close = Bottom − Buffer ちょうどで Break | NOT RUN | `f_episodeStep` / `f_processSide` の `f_leT(close, ref - breakBuffer)` |
| 6 | Resistance Close = Top + Buffer ちょうどで Break | NOT RUN | 同上 (`f_geT`) |
| 7 | FVG Close が Distal と同値なら構造有効 | NOT RUN | `f_updateFvgStructural` は厳密比較 `f_ltT` / `f_gtT` のみ |
| 8 | Wick が Zone 端と同値なら Touch | NOT RUN | `f_touchIntersect` は inclusive (`f_geT` / `f_leT`) |
| 9 | 一本線 Zone で Tolerance 0 の同値 Touch | NOT RUN | `f_touchIntersect` の幅 0 分岐 (`touchTolerance` のみ使用) |

### B. MA (10-15)

| # | 期待 | 状態 | 実装箇所 / 静的確認 |
|---:|---|---|---|
| 10 | EMA1 本だけは MA Normal / C=1 は Neutral | NOT RUN | `f_qualityMa` は 2 本必須、`f_buildCand` の `cc == 1` は BaseStrong 不可 |
| 11 | 2 本 Dense でも Support で片方下向きなら Normal | NOT RUN | `f_qualityMa` の `dirOk` |
| 12 | 2 本 Dense かつ両方上向きで Support MA High | NOT RUN | `f_qualityMa` |
| 13 | 同じ状態で Resistance 側は High にならない | NOT RUN | `f_qualityMa` は side ごとに判定 |
| 14 | MA High + 別カテゴリ / C=2 / HighDensity で Base Strong | NOT RUN | `f_buildCand` の BaseStrong 式 |
| 15 | EMA 移動だけで世代 / Fresh / Touch 履歴がリセットされない | NOT RUN | `f_generationRefresh` は「基準構造に無い独立カテゴリの新規確定」必須。MA は既存カテゴリ |

### C. Swing / Accum / 時間高安 (16-25)

| # | 期待 | 状態 | 実装箇所 / 静的確認 |
|---:|---|---|---|
| 16 | Pivot は ConfirmedTime 前に Root 化されない | NOT RUN | `pivotPackV2` は確定足のみ返す / `f_registerSwing` は confirm 必須 |
| 17 | 上位足区間内 + 価格 tick 一致の 5分+15分は同一イベント | NOT RUN | `f_registerSwing` の `lowerIntoHigher` / `higherOverLower` |
| 18 | 別時期の同価格 Swing は別イベント | NOT RUN | 同上 (区間条件を満たさないと統合しない) |
| 19 | Accum Candidate 中は Root なし / Touch なし | NOT RUN | `accumPackV2` は true→false の確定時にしか出力しない |
| 20 | true→false の false 足実体を Box へ含めない | NOT RUN | `accumPackV2` の走査は index 2 起点 (確定足 [1] は含めない) |
| 21 | 同じ Box の Top と Bottom が M 以内でも別 Zone | NOT RUN | `f_accumPairConflict` (pairKey 一致は同一候補へ入れない) |
| 22 | 4時間 Accum 境界は Accum High | NOT RUN | `f_qualityAccum` |
| 23 | 14:00→Europe / 19:00→NY / 03:00→current session なし | NOT RUN | Harness の `sessCode` / Library は `SESS_NONE` で現在セッション Root を作らない |
| 24 | 05:00 足から新取引日 | NOT RUN | Harness の `tradingDay` (`locH < dayResetHour`) |
| 25 | 時間高安の新極値足が自身を Touch しない | NOT RUN | `update()` の順序 (検出 → `f_updateTimeHlRoots`) |

### D. FVG (26-36)

| # | 期待 | 状態 | 実装箇所 / 静的確認 |
|---:|---|---|---|
| 26 | Bullish は Support だけ / Bearish は Resistance だけ | NOT RUN | `f_rootEligibleForSide` |
| 27 | 形成 3 本目確定前は Root なし | NOT RUN | `fvgPackV2` は [1]〜[3] のみ / Harness は TF 確定時のみ Feed |
| 28 | 確定後の最初の wick 進入で FVG Fresh 終了、Root は存続 | NOT RUN | `f_updateFvgFresh` (`baseCloseTime > confirmedTime` 条件つき) |
| 29 | 元 TF Close が Distal を厳密に越えた時だけ Invalidated | NOT RUN | `f_updateFvgStructural` |
| 30 | FVG 構造無効化に BreakBuffer を使わない | NOT RUN | 同関数に `breakBuffer` は現れない |
| 31 | 同方向・異 TF の実重複は共通区間かつ FVG High | NOT RUN | `f_fvgAttachAndStandalone` の共通区間 / `f_qualityFvg` |
| 32 | 同方向でも非重複なら M 以内だけで結合しない | NOT RUN | 同関数は交差判定のみ (距離では結合しない) |
| 33 | Bullish と Bearish は相互補強しない | NOT RUN | Side 別資格 + `f_qualityFvg` の `sameDir` 条件 |
| 34 | FVG 50% を変えても Zone 結果が変わらない | NOT RUN | Library に 50% 計算が存在しない (全文検索済み) |
| 35 | Broad 単独は Strong にならない | NOT RUN | `f_buildCand` の `forceBroadContext` → `isBroadContext` → BaseStrong false |
| 36 | Broad + 有効局所化条件で局所部分だけ Strong 候補 | NOT RUN | `f_buildCand` の `broadLocalized` 4 条件 / attach 経路 |

### E. 心理価格 / Strong (37-45)

| # | 期待 | 状態 | 実装箇所 / 静的確認 |
|---:|---|---|---|
| 37 | 心理価格単独では Zone なし | NOT RUN | `f_buildCand` の `hasNonPsych` / 候補採用条件 |
| 38 | Major 100 ドル位置に Standard を重複生成しない | NOT RUN | `f_syncPsychRoots` は価格 tick ごとに 1 Root (Major 判定で subtype 分岐) |
| 39 | 心理価格は C に数えるが H にならない | NOT RUN | `f_buildCand` は CAT_PSYCH の catHigh を設定しない |
| 40 | C=1 High でも Base Strong にならない | NOT RUN | BaseStrong 式 (`cc == 2 and hh >= 1` / `cc >= 3`) |
| 41 | C=2 / HighDensity / H=0 は Base Strong にならない | NOT RUN | 同式 |
| 42 | C=2 / HighDensity / H>=1 は Base Strong | NOT RUN | 同式 |
| 43 | C>=3 / HighDensity は Base Strong | NOT RUN | 同式 |
| 44 | Normal Density では C が多くても Base Strong にならない | NOT RUN | 同式 (`density == DEN_HIGH` 必須) |
| 45 | Dense Strong core へ外側 Root を加えて Neutral へ落とさない | NOT RUN | 段階 A で Dense Strong を先に確定し使用済み Root を排他。attach も `keepStrong` で拒否 |

### F. Touch / Weak (46-53)

| # | 期待 | 状態 | 実装箇所 / 静的確認 |
|---:|---|---|---|
| 46 | Root 成立時に価格が Zone 内なら Waiting / 成立足 Touch なし | NOT RUN | `f_newCore` は Waiting 開始 / `f_finalizeSide` の insideZone |
| 47 | 前足 Armed でない Zone は現在 wick 交差でも Touch なし | NOT RUN | `f_processSide` の `phase == PH_ARMED and baseSeq >= armedFromSeq` |
| 48 | 同一 Episode 内の複数往復は Touch 1 回 | NOT RUN | `currentTouchNo` は Reset まで固定 |
| 49 | 初期値では Base Strong の Touch 1 が Strong | NOT RUN | `f_computeGrade` |
| 50 | Touch 1 完了後、Upcoming Touch 2 が Weak | NOT RUN | `f_finalizeSide` の weakByTouch 永続化 |
| 51 | Touch 1 中に Depth 50% 到達で Current Weak / TouchStartGrade は Strong のまま | NOT RUN | `f_episodeStep` は Snapshot の `touchStartGrade` を書き換えない |
| 52 | Reset 後も Weak は維持 | NOT RUN | `weakByTouch` / `weakByDepth` は新世代以外で false へ戻さない |
| 53 | 一本線では WeakDepth を使わない | NOT RUN | `f_episodeStep` の `f_gtT(width, 0.0)` 条件 |

### G. Break / Flip / Reclaim (54-65)

| # | 期待 | 状態 | 実装箇所 / 静的確認 |
|---:|---|---|---|
| 54 | Wick 抜けだけでは Break しない | NOT RUN | Break 判定は `f.baseClose` のみ |
| 55 | Touch 足で Break した場合 TouchCount は増え Break が Weak より優先 | NOT RUN | `f_processSide` は touchStart → episodeStep、`f_episodeStep` は Break 優先 |
| 56 | 完全 GapBreak では TouchCount / WeakDepth / Fresh を変えない | NOT RUN | `f_processSide` の GapBreak 経路は `f_doBreak` のみ呼ぶ |
| 57 | GapBreak 足で Flip / Reclaim を同時確定しない | NOT RUN | `f_processBreakState` の `bs.breakSeq < f.baseSeq` |
| 58 | Break 後 Reset 距離前の再接触は FlipConfirm にならない | NOT RUN | `movedAway` 必須 + `movedAwaySeq < baseSeq` |
| 59 | FlipConfirm 接触は通常 Touch へ数えない | NOT RUN | `isNormalTouch = false` の TouchMark のみ |
| 60 | Flip 後は別足で再 Reset してから通常 Touch 1 | NOT RUN | `armBlockSeq = baseSeq` |
| 61 | 過去に使った Side へ再 Flip 時、その Side の Touch / Weak 履歴を復元 | NOT RUN | `SideHistory` は Side ごとに永続 (Flip では初期化しない) |
| 62 | Reclaim で Fresh / Weak をリセットしない | NOT RUN | `f_processBreakState` の Reclaim 分岐 (phase と flipPending のみ変更) |
| 63 | EMA 移動後も Flip / Reclaim 基準が BreakSnapshot から動かない | NOT RUN | 判定は `bs.rangeBottom` / `bs.rangeTop` のみ |
| 64 | FVG 無効化と Reclaim 同時なら FVG 無効化優先 | NOT RUN | `fvgInvalidNow` で Reclaim を抑止 |
| 65 | InverseConfirm を通常 Touch へ数えない | NOT RUN | `f_updateFvgInverse` は TouchCount に触れない |

### H. Topology / 世代 / 再現性 (66-75)

| # | 期待 | 状態 | 実装箇所 / 静的確認 |
|---:|---|---|---|
| 66 | ActiveTouch 中の新 Root で TouchStartGrade を書き換えない | NOT RUN | Snapshot は生成後に構造を変更しない / `f_applyCoreCand` は ActiveTouch 中に形状を変えない |
| 67 | ActiveTouch 中の Root 失効後も旧 Snapshot の Outcome 記録は続くが新 Signal には使わない | NOT RUN | `f_liveStructurePrune` (即時反映) + Episode は Snapshot 基準で継続 |
| 68 | Merge で同一接触を二重カウントしない | NOT RUN | `f_pushTouchMark` の (side, time, isNormalTouch) dedupe |
| 69 | Split で実際に触れていない子は Fresh になれる | NOT RUN | `f_assignSplitHistory` (contact range 交差のみ引き継ぐ) |
| 70 | 未タッチ Zone への Root 追加は同世代 | NOT RUN | `f_generationRefresh` の `oldEligible` |
| 71 | 同カテゴリ Root 追加 / EMA 移動 / 心理価格追加だけでは新世代にならない | NOT RUN | 新カテゴリ条件 (`cat != CAT_PSYCH` かつ baseMask に無い) |
| 72 | 新独立カテゴリ + Base Strong + Reset + 再接触でだけ新世代 Touch 1 | NOT RUN | `f_generationRefresh` → `f_generationSwitch` → `f_startNewGeneration` |
| 73 | 新世代開始時のみ両 Side の Touch / Weak / Fresh をリセット | NOT RUN | `f_startNewGeneration` だけが履歴を初期化する |
| 74 | 同じ確定 Feed を二度渡しても状態が二重更新されない | NOT RUN | `update()` の duplicate base bar guard (`baseOpenTime` / `baseSeq`) |
| 75 | Indicator reload 後、同じデータで ID / Phase / Grade / イベント列が再現する | NOT RUN | 全 tie-break を Root ID / Core ID まで決定論化。`var` / `varip` を Library で未使用 |

---

## Deviations from specification

仕様のロジックを変えた箇所は無いが、Pine の言語制約と仕様が明示していない点について、次の実装判断をしている。

1. **セッション / 日 / 週 の ID を呼び出し側で計算する (Pine 制約)**
   `hour()` / `timestamp()` の timezone 引数を series 化できないため、timezone に依存する区切り判定を
   Library から Feed 契約へ出した。Harness が `sessionCode` / `sessionId` / `dayId` / `weekId` を計算して渡す。
   高安の更新・ラベル移行・Root 化そのものは Library 側 (仕様どおり確定 5分足で更新)。

2. **Dormant をクラスタ窓として実装している**
   現在価格から `dormantDistance` より遠い Root はクラスタ候補生成から除外し、その Root だけで構成される
   Core は「未マッチだが遠方」として Dormant のまま保持する (Core ID / 世代 / 消耗履歴を維持)。
   Dormant 中は Touch / Break 検出を行わない。仕様 14 章の「表示・計算を休止」をこの形で実現している。
   価格が窓の内側へ戻った足では Dormant 解除のみを行い、検出は次の確定足から再開する (1 足の遅延)。
   ActiveTouch / Broken / FlipWait / InverseWait / Pending の Core は Dormant へ落とさない。

3. **Armed は粘着的 (Armed → Waiting へ戻すのは「終値が Zone 内」の場合だけ)**
   仕様 7.4 の「距離不足またはZone内ならWaiting」を毎足そのまま適用すると、Reset 距離より近い足の
   次足で起きる通常タッチが原理的に成立しなくなる (接近足は必ず Reset 距離より近い)。
   仕様 12 章の Phase 遷移表にも Armed → Waiting の降格行が無いため、
   「最後に距離条件を満たした側で接近方向を固定する」ほうを採用し、確定終値が Zone 内へ入った場合だけ
   Waiting へ戻して再度 Reset 距離を要求する。

4. **通常 (非 Dense) クラスタは決定論的な価格昇順スイープ**
   仕様 5.2 / 5.3 が優先順位と競合解決を要求しているのは「Base Strong を満たす Dense core」。
   残 Root の通常候補は、価格昇順に左から全幅 M 以下で貪欲にまとめる一方向スイープで作る
   (バーごとに結果が揺れない)。Dense 段階は比較関数 `f_candBetter` で選び、1 バー 1 Side あたり
   最大 12 core まで探索する。

5. **Split の Weak 履歴復元**
   `TouchMark` は侵入率を保持しないため、子 Zone の `weakByDepth` / `maxDepthPct` は
   「その Side で通常 TouchMark を 1 件以上引き継いだ場合だけ」親から復元する。
   引き継ぎが無い子は仕様どおり未タッチ (Fresh) になる。

6. **Merge の Touch 数**
   新範囲へ実際に接触した TouchMark を数え直すが、仕様「タッチ履歴をゼロにしない」を満たすため
   統合前の値より小さくはしない (`math.max`)。

7. **Flip 確定後の旧 Side**
   仕様は FlipConfirm 後の新 Side だけを規定している。実装では BreakSnapshot を破棄し
   (以後 Reclaim 不可)、旧 Side も Waiting へ戻して再度 Reset 距離から扱う。

8. **movedAway と再接触は別の確定足**
   一般 Flip も Inverse FVG も、離脱 (movedAway) と再接触 / 回復確定を同じ足で成立させない。
   5分足内部の値動き順序を推測しないため。

9. **FVG Root 状態を 2 段階に分ける**
   構造無効化直後は `ROOT_INVALIDATED`、Reset 距離の離脱を満たしたら `ROOT_INVERSE_WAIT`、
   再接触 + 回復で `ROOT_INVERSE_ACTIVE`。どちらの状態でも元方向・反対方向へ参加しない。

10. **Broad FVG だけで構成された候補の同一性**
    同一性判定は原則 Broad FVG を除外するが、候補が Broad FVG のみの場合 (Broad context Zone) は
    同一性の手がかりが無くなるため、その Broad FVG 自身を使う。Broad FVG の共有だけで
    別々の局所 Zone を結合しないという規則は維持している。

11. **Proximal 局所化の実装条件**
    「Proximal 外側に別 Root が高密集」は「点候補と NativeRange の gap が 0 より大きく denseWidth 以内、
    かつその点候補が High Density」で判定し、EffectiveRange を Proximal edge まで広げる。
    結果が M を超える場合、または Base Strong が落ちる場合は採用しない。

12. **`accumPackV2` の走査上限 (Pine 制約)**
    可変 index の履歴参照に定数上限が必要なため、Candidate の連続本数は最大 400 本、
    Box 範囲の走査は最大 600 本まで。これを超える長大な Accum Candidate は範囲が切り詰められる。

13. **MA の傾きを `Root.direction` に載せている**
    FVG 以外で `direction` を使わないため、MA Root の `direction` を傾き符号 (+1 / -1 / 0) として使う。

14. **`rootSummary` / `categorySummary` は `barstate.islast` のみ**
    Hot loop で文字列連結しないという指示に従い、表示用文字列は最終バーだけ生成する
    (判定には一切使わない)。

15. **`ZoneCfg.mintick` を Feed で上書きする**
    `update()` は Feed の `mintick` が有効ならそれを `cfg.mintick` へ入れる。
    Harness は毎バー `newCfg()` から Cfg を組み立てるため副作用は残らない。

---

## Performance work (RE10110 対応)

`Runtime error: RE10110 The script takes too long to execute. The time limit is 40 seconds.`
に対して、**Zone 判定ロジックを 1 行も変えずに**負荷を下げる作業。指示された Phase 順で進める。

### Phase 1 : 計測 (準備のみ完了 / 計測は未実施)

- Baseline を `baseline/` へ保存した。
  - `baseline/ZoneEngineV2_baseline.pine`
  - `baseline/ZoneEngineV2_VisualHarness_baseline.pine`
  - (= git `d528a1e` 時点。v6 化直後・最適化前)
- Profiler 用の一時コピーを `profiler/ZoneEngineV2_VisualHarness_Profiler.pine` に作成した。
  本番コードとの違いは `calc_bars_count = 3000` と `shorttitle` だけ。ヘッダに
  「PROFILER ONLY / 本番では使わない / ここで出た Zone を判定結果として扱わない」と明記済み。
- **Profiler の実行はこの環境からできない (TradingView 非接続)。**
  `Pine Editor -> More -> Profiler mode` で上記コピーを実行し、次の実行回数と負荷割合を
  記録して共有してほしい: `request.security` 10 本 / `zn2.update()` / `f_rebuildCores()` /
  `f_buildSideCands()` / `f_pickBestWindow()` / `f_fvgAttachAndStandalone()` / `f_pairSides()` /
  `f_buildViews()` / `f_reindexRoots()` / 描画・テーブル・Event Log。

### Phase 2 : Harness の低リスク軽量化 (実装済み)

すべて「表示専用」または「allocation 削減」で、Engine へ渡る値・順序・タイミングは不変。

| # | 変更 | 分類 |
|---|---|---|
| 2-1 | `ZoneCfg` を `var` の永続オブジェクトにし、初回 1 回だけ全フィールドを設定 (`cfgInitialized` フラグ)。input 変更時はスクリプト全体が再計算されるため値は維持される | allocation 削減 |
| 2-2 | `zn2.constOf()` の 21 個を `var int` にして初回 1 回だけ取得 | allocation 削減 |
| 2-3 | `tfCodeOf()` の 9 回呼び出しを `var int swCode1..fvgCode3` として初回だけ算出 | allocation 削減 |
| 2-4 | `ZoneFeed` を毎足 `newFeed()` せず 1 つを使い回す。Library へ `resetFeed()` を追加し、各足の先頭で `swings`/`accums`/`fvgs` を clear + スカラーを既定値へ戻してから従来どおり全フィールドを代入 | allocation 削減 |
| 2-5 | Event Log 文字列の生成を `if showEventLog and isFiveMin and barstate.isconfirmed` の中へ移動 (Engine 内部の Event 生成は従来どおり) | 表示専用 |
| 2-6 | Zone ラベル文字列 / Root Debug View / Root 並べ替え / Event Log / Debug table / FVG 50% を、対応する表示 input が ON のときだけ実行。Library へ表示専用フラグ `ZoneCfg.buildDisplayStrings` を追加し、ラベル非表示なら `ZoneView` の説明文字列も作らない | 表示専用 |
| 2-7 | box / line / label を毎回全削除して作り直す方式をやめ、プールを `box.set_*` / `line.set_*` / `label.set_*` で更新。余った分だけ削除、足りない分だけ新規作成。さらに **未確定ティックごとの再構築をやめ、Engine の確定状態 (`processedBars`) が進んだときだけ**描画・テーブル・警告を更新 (`varip` の表示用カウンタで判定) | 表示専用 |

Library 側の変更は次の 2 つだけで、どちらも追加のみ・判定に不参加:
`export resetFeed(ZoneFeed f)` の追加、`ZoneCfg.buildDisplayStrings` (表示文字列生成の ON/OFF) の追加。

**Phase 2 だけでは RE10110 が消えない可能性が高い。** 40 秒制限の主因は、全ヒストリカル足で回る
Engine 内部のクラスタリング (`f_buildSideCands` -> `f_pickBestWindow` -> `f_buildCand`) の
重複計算と一時配列生成であり、そこは Phase 3 の対象。Phase 2 が主に効くのは
リアルタイムの毎ティック描画コストと、1 足あたりの UDT / 配列生成コスト。

### Phase 3A : Engine 内部の安全な軽量化 (実装済み)

比較基準は公開済み **Version 2** (`sekine3310/ZoneEngineV2/2`)。Version 2 は A/B 比較用に残し、
本リポジトリの `ZoneEngineV2.pine` を新バージョンとして Publish する。

| # | 変更 | 分類 |
|---|---|---|
| 3A-1 | `ZoneEngine.rootIdxDirty` (初期値 true) を追加。`e.roots` の追加・削除は `f_pushRoot()` / `f_removeRootAt()` の 2 関数だけを通し、そこでだけ dirty を立てる。`f_reindexRoots()` は dirty が false なら map の clear / 再構築をせず終了し、再構築後に false へ戻す | 探索高速化 |
| 3A-2 | `validateCfg()` を最初の `update()` だけで実行 (`cfgValidated`)。Feed 有効性 / duplicate bar / baseConfirmed / mintick 反映 / configValid・configError の保持は毎足のまま | 探索高速化 |
| 3A-3 | 内部型 `ZoneCand` の `array<bool> catUsed` / `catHigh` を `int catMask` / `int highMask` へ。C・H は mask から 1 度だけ数え、`f_applyCandToView()` は再ループせず計算済みの mask / C / H をそのまま渡す | allocation 削減 |
| 3A-4 | `f_pickBestWindow()` の部分窓ごとの `ZoneCand` 生成・`rootIds` コピー・カテゴリ配列生成を廃止。評価は使い回しの scratch Candidate (`f_fillCandFrom()`) で行い、best 更新時だけ `f_cloneCand()` で deep copy する | allocation 削減 |
| 3A-5 | `f_pickBestWindow()` の `cur`、通常候補スイープの `cur` / `curIdx` を関数内で 1 本だけ作り、各反復の先頭で `array.clear()` して再利用 | allocation 削減 |
| 3A-6 | Candidate 生成時に identity Root ID 一覧 (`ZoneCand.identityIds`) を 1 度だけ作り、`f_pairSides()` は Support × Resistance の組み合わせごとに作り直さず再利用する | allocation 削減 |

#### `e.roots` を構造変更する箇所と dirty 設定

追加 7 / 削除 3 = 10 箇所。すべて `f_pushRoot()` / `f_removeRootAt()` 経由へ変更し、
生の `array.push(e.roots, ...)` / `array.remove(e.roots, ...)` はこの 2 関数の中だけに残した。

| 関数 | 操作 |
|---|---|
| `f_upsertMa()` | push (EMA Root 新規作成) |
| `f_registerSwing()` | push |
| `f_updateAccumRoots()` | push × 2 (Box 上限 / 下限) |
| `f_registerFvgOne()` | push |
| `f_acquireTimeRoot()` | push |
| `f_syncPsychRoots()` | push |
| `f_removeRetiredRoots()` | remove |
| `f_pruneCategoryToCap()` | remove × 2 (Accum pair 一括 / 単体) |

`array.insert` / `array.shift` / `array.pop` / `array.clear` / sort は `e.roots` に対して 1 箇所も存在しない
(全文検索で確認)。Root オブジェクト内部の価格・state・labelMask・fvgFresh の変更では dirty を立てない
(配列 index が動かないため)。`f_rootIdxById()` の ID 照合と線形探索フォールバックはそのまま残してあるので、
万一 map が古くても返る index は常に正しい。

#### Candidate 評価中に削減した allocation

| 箇所 | Version 2 | Phase 3A |
|---|---|---|
| Dense 探索の 1 部分窓ごと | `ZoneCand` 1 + `array.copy(rootIds)` 1 + `array.new_bool(6)` 2 = 4 オブジェクト | 0 (scratch を上書き) |
| Dense 探索の窓の開始ごと | `array.new_int()` (cur) | 0 (呼び出し内で 1 本を clear 再利用) |
| best 更新時 | 0 (参照代入) | `f_cloneCand()` 1 回 (rootIds / identityIds を deep copy) |
| 通常候補スイープ 1 クラスタごと | `cur` / `curIdx` 2 本 | 0 (1 組を clear 再利用) |
| `f_pairSides()` の Support × Resistance 組み合わせごと | `array.new_int()` + `f_identityIds()` | 0 (Candidate の identityIds を参照) |
| `f_pairSides()` の CoreCand ごと | `f_identityIds()` 2 回ぶんの再計算 | 0 (キャッシュ済み ID を push するだけ) |
| すべての `ZoneCand` | bool 配列 2 本 | 0 (int mask) |

#### deep copy した所有境界

- `f_buildCand()` : `rootIds = array.copy(ids)` / `identityIds` は新規配列。保存用 Candidate は必ず自分の配列を所有する。
- `f_cloneCand()` : `rootIds = array.copy(ids)` (scratch の配列は使わない) / `identityIds` も新規作成。
  clone 後に scratch や `cur` を clear しても保存済み Candidate は一切変化しない。
- scratch Candidate の `rootIds` / `identityIds` は空のまま一度も読まれない (`f_candBetter()` はスカラーのみ比較)。
- `f_applyCandToView()` : `v.rootIds := array.copy(cd.rootIds)`。
- `f_pairSides()` : `cc.originRootIds` は新規配列に identityIds の「値」を push (参照共有しない)。
- Engine のフィールドへ scratch 配列を保存して足をまたいで共有する処理は入れていない。

#### Version 2 から処理順・tie-break を変更していないこと

- `f_candBetter()` (C 降順 -> H 降順 -> 幅昇順 -> 成立時刻昇順 -> 最小 Root ID 昇順) は 1 文字も変更なし。
- Dense 候補探索の最大 12 回、`requireStrong`、`continue` / `break`、Accum pair conflict の位置と条件は不変。
- 通常候補スイープの走査順、使用済み Root の marking、FVG attach / standalone の順序は不変。
- `f_pairSides()` の Support 走査順・Resistance 選択条件 (shAll / gap / near) と `originRootIds` の並び順は不変。
- `f_identityIds()` の中身 (Broad FVG 除外規則と、Broad のみの場合のフォールバック) は不変。
  評価タイミングだけが「pairing 時」から「Candidate 確定時」へ移ったが、`isBroadFvg` は Root 生成時に確定して
  以後変化せず、Root の削除は `update()` の末尾でしか起きないため、同じバー内では同じ結果になる。

#### Zone ロジックを変更していないこと

Root の生成・更新・失効条件、クラスタリング、Dense 判定、C / H / Density / BaseStrong / Grade、
Support・Resistance の参加方向、FVG の方向・Fresh・Inverse、Touch / Weak / Break / Flip / Reclaim、
Merge / Split / Core ID / Generation ID、`request.security` の内容、履歴期間、`dormantDistance`、
各保存上限、有効カテゴリは 1 つも変更していない。`calc_bars_count` は本番コードに無い。

#### Phase 3A で意図的に未実装とした最適化

- `array.includes()` -> two-pointer 比較 (rootIds / originRootIds が Root ID 昇順でないため、
  Phase 3B で「比較専用のソート済みコピー」を別に作る形で検討する)
- 既存配列の sort、Root 順 / Core 順の変更
- Candidate 探索の省略、近似計算、キャッシュ結果の足またぎ利用
- `f_fvgAttachAndStandalone()` の attach 試行 Candidate の削減
- `f_rebuildCores()` のスキップや dirty 化

### Phase 3B / 3C : 探索の増分化と request 統合 (実装済み)

対象 commit

| 内容 | commit |
|---|---|
| Engine 内部 (探索 / 集合比較 / registry / allocation) | `710326b` |
| まとめ Pack と Harness (request 統合 / 数値 Event ログ) | `51bfbcb` |
| Parity Harness 追加 / profiler 再同期 | `c5076b7` |
| `f_countAccumBoxes()` の map 化 / 本レポート | 本 commit |

#### 1. commit hash

上表のとおり。ブランチは `claude/tender-dijkstra-dh7v3f`。

#### 2. request 呼び出し回数の変化

| | Version 3 | Phase 3B/3C (既定設定) | Phase 3B/3C (全グループ不一致) |
|---|---:|---:|---:|
| `request.security` | 10 | **6** | 10 |
| `time(tf)` | 9 | **5** | 9 |
| 合計 (request 系) | 19 | **11** | 19 |

時間足を別のものへ変えても動作は変わらず、そのグループだけが自動で旧構成へ戻る。
グループ別の場合分けは上の "request.security (Harness)" 節の表。

#### 3. Dense 探索の計算量 (before / after)

記号 : `R` = 窓 (現在価格 ± `dormantDistance`) 内の点 Root 数、`W` = dense 窓の数 (≤ R)、
`K` = 1 窓に入る Root 数、`D` = dense ラウンド数 (最大 12)。

| | Version 3 | Phase 3B/3C |
|---|---|---|
| Root の並び作成 | Version 3 の挿入処理 `O(R²)` を **Side ごとに 2 回 / 毎足** | **まったく同じ挿入処理** を **1 足に 1 回だけ** (`f_buildPointSnapshot()`)。並び順は完全一致。汎用ソートは使わない |
| 1 窓の評価 | `ZoneCand` 生成 + `array.copy` + 品質関数再計算 `O(K)` 割と定数倍が大きい | 増分スカラ (catMask / cCount / hasNonPsych / minRootId / firstConfirmTime / カテゴリフラグ) を窓の進行とともに更新 `O(1)` 摊還 |
| 1 ラウンド | `O(W · K)` + 毎窓 allocation | `O(R)` (two-pointer で窓を進める) + allocation なし |
| 全体 | `O(2 · R² + D · W · K)` | `O(R² + D · R)` (`R²` の並び作成は 1 回だけ) |
| 保存候補の生成 | 窓ごと | 採用された 1 窓だけ (`f_materializeBest()` → 未変更の `f_buildCand()`) |

探索する窓の集合、continue / break の位置、衝突判定の位置、比較子
(`C desc → H desc → 幅 asc → firstConfirmTime asc → minRootId asc`) は 1 つも変えていない。
dense ラウンドは最大 12 のまま。

#### 3-b. 並び順の同値性 (汎用ソートを使わない理由)

Version 3 の挿入条件は

```
r.pointPrice < pk or (f_eqT(r.pointPrice, pk, c.mintick) and r.rootId < ik)
```

これは「生の価格の大小」と「正規化 tick の同値判定」を混ぜているため、
**一般の sort comparator としては推移律を満たさない**。生価格が違っていても同一 tick と
判定されれば Root ID で順番が決まるからで、`array.sort` / `array.sort_indices` でも
「生価格が完全一致したときだけ ID 比較」でも同じ列にならない。

よって `f_buildPointSnapshot()` は **汎用ソートを使わず**、`e.roots` の元の走査順で
Version 3 と同じ挿入処理をそのまま再現する。削ったのは次の 2 点だけ。

- Side ごとに 2 回やっていたものを 1 足 1 回にした (非 FVG Root の参加資格は
  `f_rootEligibleForSide()` の非 FVG 分岐が `state == ROOT_ACTIVE` だけなので Side に依存しない)。
- 毎回の `array.new_int` / `array.new_float` をやめ、永続 scratch
  (`scRawPrice` / `scRawId` / `scRawIdx`) へ挿入するようにした。

挿入比較の回数も打ち切り位置 (`break`) も Version 3 と同じ。

#### 4. 部分窓あたりの allocation

| | Version 3 | Phase 3B/3C |
|---|---:|---:|
| `ZoneCand` 新規 | 1 / 窓 | **0** (engine 保持の scratch 1 個を使い回す) |
| `array.new_int` / `array.copy` | 2〜4 / 窓 | **0** |
| 品質判定用の一時配列 | 1〜2 / 窓 | **0** |
| 文字列連結 (Accum 衝突の pairKey) | 窓内 Accum 数分 | **0** (int token) |

足ごとの allocation (窓単位ではないもの)

| | Version 3 | Phase 3B/3C |
|---|---:|---:|
| 点 Root 並び用の `array.new_*` | 4 本 / 足 (ids × 2 + prices × 2、Side ごと) | **0** (`scRawPrice` / `scRawId` / `scRawIdx` を使い回す) |
| `used` の `array.new_bool` | 2 本 / 足 | **0** (`scUsed` を clear + push) |
| 心理価格の `array.new_float` + `map.new` | 2 個 / 足 | **0** (`scPsychNeed` / `scPsychSeen`) |
| FVG attach / standalone の一時配列 | attach 試行ごと | **0** (scratch。採用時だけ `f_buildCand()`) |

保存する候補を作るときだけ `f_buildCand()` が従来どおり配列を新規作成する。
FVG attach も同じで、試行中は scratch (`f_fvgTrialEval()`)、採用されたときだけ
`f_materializeAttach()` が本体を作る。

#### 4-b. break 用の幅と Candidate 実幅の分離

並びが生価格の完全な昇順になるとは限らないので (上記 3-b)、
`f_searchDenseBest()` では 2 種類の幅を完全に別に持っている。

| | 式 | 使い道 |
|---|---|---|
| 探索の打ち切り | `array.get(e.snPrice, b) - lo` (`lo` = 探索開始位置 `a` の価格) | `if f_gtT(w, maxWidth, c.mintick)` → `break`。**Version 3 の式そのまま** |
| Candidate の実幅 | `wPmax - wPmin` (窓へ Root を追加するたびに逐次更新) | 幅 / Density / tie-break / BaseStrong / 評価値 |

実装箇所 (`ZoneEngineV2.pine`)

- `wPmin` / `wPmax` の宣言 : `f_searchDenseBest()` の窓開始直後 (`float lo = ...` の直下)
- 逐次更新 : 「窓へ 1 Root 追加 (増分更新)」の先頭で
  `wPmin := na(wPmin) ? rpx : math.min(wPmin, rpx)` / `wPmax := ... math.max ...`
  — `f_fillCandFrom()` の `pmin` / `pmax` と同じ式
- Candidate 幅 : `float wid = na(wPmin) or na(wPmax) ? float(na) : wPmax - wPmin`
- Density : `wid` を `c.clusterMaxWidth` / `f_denseWidth(c)` と比較 (`f_fillCandFrom()` と同じ順)
- tie-break : `f_candBetter()` が `nz(top - bottom, 0)` を使うのに合わせて `nz(wid, 0)` で比較
- break 式 : `float w = array.get(e.snPrice, b) - lo` のまま (未変更)

保存される Candidate の `bottom` / `top` は従来どおり `f_buildCand()` → `f_fillCandFrom()` が
ids を走査して `pmin` / `pmax` を作るので、ここは元から真の max - min だった。
今回直したのは **探索中の評価値** で、ここを `price[b] - lo` で代用していたのは
Version 3 と違う候補を選び得る真の不一致だった。

#### 5. Hot loop に残っている `array.includes()`

ファイル全体で 20 箰所 → **15 箰所** (うち 1 つはコメント)。
クラスタリング / 同一性判定 / Core マッチングの hot path からは **全部消えている**
(two-pointer `f_sharedSorted()` と二分探索 `f_containsSorted()` へ置換)。
残っているのは次の 3 種類で、いずれも毎足の全探索ではない。

| 場所 | 残した理由 |
|---|---|
| `f_markCoreFvgInvalid()` (3) | FVG Root が構造無効化された足だけ。探す配列は 1 View の rootIds (数件) |
| `f_rootEssentialByCore()` (6) | 保存上限超過時の prune 内だけ。しかも hot core に限定済み |
| `f_identityIds()` / `f_refPrice()` の EMA 判定 (4) | 候補 1 件の ids (数件〜数十件) の重複排除。ソートを入れると push 順が変わる |

`f_countAccumBoxes()` の pairKey 文字列線形探索 (`O(n²)`) は `map<string, bool>` へ置換して
消した。数える対象と件数の定義は Version 3 と同じ。

#### 6. Hot loop に残っている `f_rootIdxById()`

`f_rootIdxById()` 自体は map 引き + ID 照合 + (古いときだけ) 線形フォールバックなので、
平均 `O(1)`。`f_reindexRoots()` は `rootIdxDirty` が立っているときだけ map を作り直す。
dirty を立てるのは `f_pushRoot()` / `f_removeRootAt()` の 2 つだけで、ここを通らない
配列操作は無い。

呼び出し箰所は 33 → 38 へ増えているが、増えた分は「毎足 1 回の snapshot 作成」と
「候補を保存するとき」で、代わりに **窓ごと / ペアごとの呼び出しが消えている**。
探索中 (`f_searchDenseBest()` の窓ループ) からは 1 回も呼ばない — 必要な値は全て
snapshot 配列 (`snRootId` / `snPrice` / `snCat` / `snTf` / `snDir` / `snPair` など) から直読する。

#### 7. 毎足の全走査をやめたもの

| 処理 | Version 3 | Phase 3B/3C |
|---|---|---|
| `f_reindexRoots()` | 毎足 map 再構築 | `rootIdxDirty` が立った足だけ |
| `validateCfg()` | 毎足 | 初回 + Cfg 変更時だけ |
| `f_removeRetiredRoots()` | 毎足全走査 | `retiredDirty` (= `f_retireRoot()` が味方したとき) だけ |
| カテゴリ別上限 prune (Swing / Accum / FVG / TimeHL) | 毎足 4 回の全走査 | `capDirty<cat>` が立ったカテゴリだけ |
| `f_countAccumBoxes()` | 毎足 `O(n²)` 文字列比較 | prune が dirty のときだけ、かつ `O(n)` |
| `originKey` から Root を引く | 毎回線形走査 | `originKeyMap` (map) |
| 心理価格の重複判定 / 不要判定 | 毎回線形走査 | 正規化 tick を鍵にした map |
| 点 Root の価格昇順並べ替え | 探索のたび | 毎足 Side ごとに 1 回 (snapshot) |

`zn2.update()` と `f_rebuildCores()` は毎確定足 1 回、従来どおり必ず実行する。
「HTF 更新が無いから Core 再構築を飛ばす」などの危うい全体スキップは入れていない
(価格が動けば Touch / Break / Dormant / 距離判定は変わるため)。

#### 8. Deep copy の所有権境界

| 配列 | 所有者 | 新規作成される場所 |
|---|---|---|
| `ZoneCand.rootIds` / `identityIds` / `rootIdsSorted` / `identitySorted` / `nonFvgIdentitySorted` / `fvgIds` | その Candidate | `f_buildCand()` のみ (scratch は `f_newScratchCand()` の 1 個きり) |
| engine scratch (`scRawPrice` / `scWinIdx` / `scBestIdx` / `scCurIds` / `scAccTok` / `scMedian` / `scCatPrices` / `scFvgIds` 他) | `ZoneEngine` | `newEngine()` で 1 回だけ。以降は `array.clear()` で使い回す |
| snapshot (`snRootId` / `snPrice` / `snCat` / …) | `ZoneEngine` | 同上。毎足 Side ごとに詰め直す |
| `SideViewState.rootIds` / `rootIdsSorted` | その View | `f_applyCandToView()` の `array.copy()` (Candidate と共有しない) |
| `ZoneCore.originRootIds` / `originRootIdsSorted` | その Core | `f_applyCoreCand()` / `f_mergeCore()` の `array.copy()` |
| `TouchStartSnapshot.rootIds` / `BreakSnapshot.rootIds` | その Snapshot | 取得時の `array.copy()` (以後不変) |

規則は 1 つ : **scratch は絶対に保存されるオブジェクトへ渡さない**。採用が決まった時点で
`f_materializeBest()` / `f_materializeAttach()` が未変更の `f_buildCand()` を呼び、そこで新しい
配列を持った候補を作る。これにより scratch を `clear()` しても保存済みの内容は変わらない。
`SideViewState.rootIdsSorted` は比較専用の昇順コピーで、意味のある順序を持つ `rootIds`
自体は一切並べ替えていない。

#### 9. Version 3 とロジックが変わっていない根拠

| 項目 | 根拠 |
|---|---|
| Root 生成条件 | 各 `f_sync*Roots()` の条件式は未変更。変えたのは「どう引くか (map)」だけ |
| 探索する窓 | `f_buildPointSnapshot()` のフィルタは Version 3 の `f_collectPointRoots()` と同一条件 (窓 / 非 FVG / pointPrice あり / ROOT_ACTIVE) |
| Root の順序 | Version 3 の挿入条件 (`price < pk or (f_eqT(price, pk) and rootId < ik)`) を `e.roots` の元の走査順でそのまま再現。汎用ソートは使っていない (理由は 3-b) |
| Candidate の幅 | 探索中も `wPmax - wPmin` (`f_fillCandFrom()` の `pmin` / `pmax` と同じ)。break 式とは分離 (4-b) |
| 候補の比較 | `f_candBetter()` 未変更。tie-break 順も未変更 |
| dense 回数 | 最大 12 のまま。探索の打ち切り位置 (continue / break) も同じ |
| C / H / Density / BaseStrong | 品質関数の条件式は未変更。増分スカラは同じ式を逐次更新しているだけ |
| Accum 排他 | `pairKey` 文字列比較 → int token 比較。token は pairKey と 1:1 なので判定結果は同じ |
| 集合の共有数 | `array.includes()` の入れ子 → 重複の無い昇順コピーの two-pointer。同じ件数を返す |
| gap 判定と共有数の順 | 元々 `and` の連言なので順番を入れ替えても真偽は変わらない |
| Touch / Weak / Break / Flip / Reclaim | 8 章は 1 行も触っていない |
| FVG Fresh / Inverse / 方向 | 5.5 節は未変更。attach は評価を scratch へ移しただけで試行集合も順番も同じ |
| Accum 条件 | `rangeShort` は `ta.highest(bodyTop, rangeLen) - ta.lowest(bodyBot, rangeLen)` で `rangeNow` と同じ式だったので再呼び出しをやめただけ |
| 公開 API | `export` 行を Version 3 と diff して完全一致 (新規 2 関数の追加のみ) |
| イベント | 生成箇所・順番未変更。Harness 側で文字列化を遅らせただけ |

実機での照らし合わせは `ZoneEngineV2_ParityHarness.pine` で行う (下記)。

#### 10. 意図的に残したボトルネック

| 残したもの | なぜ残したか |
|---|---|
| クラスタリングは依然として `O(bars · R · D)` | dense ラウンドを減らす / 探索を間引くのは禁止されている。定数倍だけを落とした |
| `f_rebuildCores()` の Core × Candidate マッチング | 順序と tie-break を変えずに探索を落とす方法がない。集合比較だけ two-pointer 化した |
| `request.security` 6 本 | MA (1分) と Swing 5分 / 15分 は他と時間足が違うのでまとめられない |
| EMA2000 / EMA3000 の 1分足計算 | 仕様そのもの。期間を短くするのはロジック変更 |
| `f_rootEssentialByCore()` の `array.includes()` 群 | prune が必要な足だけしか走らない上、hot core に限定済み |
| 描画・テーブル | すでにプール + 最終足のみ。これ以上は表示内容を削ることになる |

これでも RE10110 が残る場合、残る重さは「足数 × 窓内 Root 数」で、そこを下げるには
禁止されている手段 (履歴削減 / 上限縮小 / 探索間引き) に触るため、ここでは入れていない。
次に取るべきは Phase 5 (Alert consumer の分離 : 描画を持たない軽い消費側を別スクリプトにする)
と思うが、それは別途指示を待つ。

#### 11. Publish 後に差し替える import 行

`ZoneEngineV2_VisualHarness.pine` の次の 1 行だけ。

```
import sekine3310/ZoneEngineV2/4 as zn2          // ← ★ Publish 後の実番号を確認すること
```

- 直前の公開が `/3` (Phase 3A) だったので、連番として `/4` を入れている。
- ★ `/4` は仮の値。Publish 直後に TradingView が実際に発行した番号を見て、
  違っていたらこの 1 行を直すこと。
- 今回は新 API (`swingAccumFvgPackV2` / `accumFvgPackV2`) を使うため、`/3` のままだと
  関数が見つからずコンパイルできない。
- `profiler/ZoneEngineV2_VisualHarness_Profiler.pine` と
  `ZoneEngineV2_ParityHarness.pine` (vB 側) にも同じ番号を入れる。
  Parity Harness の vB は仮置き (`/4`) のままなので必ず確認して直すこと。

#### Phase 3B / 3C で入れていないもの (禁止事項の確認)

`calc_bars_count` / 開始日時による切り捨て / Root・Core・Touch 上限の縮小 /
dense 12 回の削減 / Root・Candidate・FVG attach 試行の間引き / カテゴリ・時間足の無効化 /
価格のバケット化・丸め方の変更 / 「N 足に 1 回だけ再計算」/ `dormantDistance` や Zone 幅の既定値変更 /
`request.security` の確定足・`lookahead_off` の意味変更 / Root・Candidate・Core・Event 順の変更 /
tie-break の変更 / Touch・Weak・Break・Flip・Reclaim のタイミング変更 /
FVG Fresh・Inverse・方向の変更 / Accum 条件の変更 — いずれも行っていない。
本番 Harness (`ZoneEngineV2_VisualHarness.pine`) に `calc_bars_count` は無い。

### Phase 3D : 表示専用の軽量更新経路 (実装済み)

RE10110 の残る重さは「全履歴 × 1 足あたりの処理量」で、request 統合と
配列再利用だけでは主処理量が減らない。そこで **表示のためにしか使わないもの**
を「表示する足」だけで作る経路を追加した。

#### 追加した API (既存 `update()` はそのまま残してある)

```
export updateVisualLite(ZoneEngine e, ZoneCfg c, ZoneFeed f,
     bool buildProjection, bool captureEvents)
```

- `update(e, c, f)` = `f_updateCore(e, c, f, true, true)` — 従来と完全に同じ。
- `updateVisualLite()` は同じ `f_updateCore()` へ渡すだけ。
- `f_updateCore()` の中身は旧 `update()` の本体と diff を取って次の 2 箇所のだけ違い。
  1. 先頭で `e.captureEvents := captureEvents`
  2. 末尾の `f_buildViews(e, c, f)` を `if buildProjection` で囲んだ (else は `array.clear(e.views)`)

#### 過去履歴の足で作らないもの

| やめたもの | 場所 |
|---|---|
| ZoneView の生成 | `f_buildViews()` → `f_pushView()` |
| `rootSummary` / `categorySummary` の文字列生成 | `f_pushView()` の中 (上を飛ばせば同時に消える) |
| ZoneEvent オブジェクトの生成と保存 | `f_emit()` の `array.push` を `e.captureEvents` で gate |
| Event の `info` 文字列連結 (4 箇所) | `e.captureEvents ? ... : ""` (v6 の三項演算子は遅延評価) |
| Event ログ配列への格納 | Harness 側 : `lastWantEvents` で gate |
| 表示文字列・描画・テーブル | 従来どおり `needRedraw` (= `barstate.islast` 必須) の下だけ |

#### Projection / Event を作る足

```
bool wantProjection = barstate.islastconfirmedhistory or (barstate.islast and barstate.isconfirmed)
bool wantEvents     = wantProjection or fullHistoryEvents
```

`fullHistoryEvents` は新規 input (既定 OFF)。ON にすると全確定足で ZoneEvent を
作って過去分も Event log へ溜められる (その分重い)。ON / OFF どちらでも
Zone の判定・Root・Core ID・Generation ID・Touch・Grade は変わらない。

#### これが安全な根拠 (指示 6 の確認)

`e.views` と `e.events` は Engine 内部の判定から一切読まれていない。全参照箇所を列挙して確認済み。

| 配列 | 書く場所 | 読む場所 | 判定で使っているか |
|---|---|---|---|
| `e.events` | `f_emit()` の push / 足頭の `array.clear` | `eventCount()` / `eventAt()` / `f_emit()` の戻り値 | 使っていない |
| `e.views` | `f_pushView()` の push / `f_buildViews()` の `array.clear` | `viewCount()` / `viewAt()` / `update()` の戻り値 | 使っていない |

`f_emit()` の戻り値 (`array.size(e.events)`) を使っている呼び出し側は 14 箇所全部で 0 件。
`f_pushView()` は `ZoneView` を作って push するだけで、Core / View / Snapshot を書き換えない。

#### 変えていないもの (指示 5)

Root 生成 / 失効、EMA2000 / EMA3000、Swing / Accum / FVG / TimeHL / Psych、
Candidate 探索条件と最大 12 回、Support / Resistance 判定、Merge / Split、
Core ID / Generation ID、Touch / Weak / Break / Flip / Reclaim、Grade / Density / High 判定、
保存上限、Feed 値、`request.security` の `lookahead_off`、Engine の処理順 —
いずれも 1 行も変えていない。旧 `update()` 本体との diff は上記 2 箇所だけ。

#### 履歴本数の切り分け確認 (本番とは別)

本番 `ZoneEngineV2_VisualHarness.pine` に `calc_bars_count` は入れていない。
履歴本数が主因かを見るのは `profiler/ZoneEngineV2_VisualHarness_Profiler.pine`
(本番と同一内容 + `shorttitle` + `calc_bars_count`)。現在 `calc_bars_count = 1000`。
500 / 1000 / 2000 と変えて、

- 1000 で動き全履歴で落ちる → 主因は履歴本数 × 1 足の処理量
- 500 でも落ちる → 1 足の処理量そのものが重いので、
  `f_buildPointSnapshot` / `f_searchDenseBest` / `f_fvgAttachAndStandalone` /
  `f_pairSides` / `f_rebuildCores` を Profiler で特定してから scratch / プールを追加する

### Phase 3E : Core 再構築の入れ物をプール化 (実装済み)

毎足の `array.new*` / `array.copy()` を減らした。探索順・比較条件・push 順は未変更。

| 対象 | 変更前 (毎足) | 変更後 |
|---|---|---|
| Support 候補の容器 | `array.new<ZoneCand>()` | `e.poolSup` を clear + push |
| Resistance 候補の容器 | `array.new<ZoneCand>()` | `e.poolRes` を clear + push |
| CoreCand の容器 | `array.new<CoreCand>()` | `e.poolCcs` を clear + push |
| `rUsed` | `array.new_bool(max(nr,1), false)` | `e.pRUsed` + `f_fillBool()` |
| `coreToCand` | `array.new_int(max(nc,1), -1)` | `e.pCoreToCand` + `f_fillInt()` |
| `coreMerged` | `array.new_bool(max(nc,1), false)` | `e.pCoreMerged` + `f_fillBool()` |
| `candPrimary` | `array.new_int(max(nk,1), -1)` | `e.pCandPrimary` + `f_fillInt()` |
| `f_applyCandToView()` の View 配列 | `v.rootIds := array.copy(...)` × 2 | `f_copyInto()` × 2 (View がすでに所有している配列へ deep copy) |
| Core の origin 配列 | `z.originRootIds := array.copy(...)` × 2 | `f_copyInto()` × 2 |
| BreakSnapshot / TouchStartSnapshot | `rootIds := array.copy(v.rootIds)` | `f_copyInto()` |

`f_fillBool()` / `f_fillInt()` は長さも初期値も従来と同じ (`max(n, 1)` 件)。

#### 参照共有をしていないことの根拠

- プールしたのは「容器」だけ。中に入る `ZoneCand` / `CoreCand` は従来どおり
  `f_buildCand()` / `CoreCand.new()` が毎足新規に作る。
- `ZoneCand` / `CoreCand` の参照は 1 回の `f_rebuildCores()` の外へ出ない。
  `CoreCand` は sup / res を **index** でしか指していない。
- 永続オブジェクト (`ZoneCore` / `SideViewState` / Snapshot) へは必ず
  `f_copyInto()` または `array.copy()` で deep copy している。
- 新しい `ZoneCore` を作る箇所 (`f_applyCoreCand()` の新規 / `f_archiveCore()`) と
  `f_buildCand()` の `rootIds` だけは、新しい配列が必要なので `array.copy()` を残している。

#### dirty skip は入れていない

Phase 3E では「依存値が変わっていないと証明できない skip」を 1 つも入れていない。
`f_rebuildCores()` は全確定足で従来どおり実行する。

### Parity Harness (`ZoneEngineV2_ParityHarness.pine`)

★ Phase 3D では対象外。1 行も変更していない。比較コードは本番 Harness へ一切入っていない。
(Parity Harness は `vA.update()` / `vB.update()` の完全版同じを照らすツールのまま)


本番 Harness とは別ファイルの検証専用スクリプト。

- 公開済み Version 3 を `vA`、Phase 3B/3C 版を `vB` として **同時に import** する。
- ZoneCfg を 2 つ同じ値で作り、`vA` の個別 Pack から取った **まったく同じ値** を両方へ流す。
  これにより違いが出たときは Engine 内部の違いと断定できる。
- 毎確定 5分足で照らす項目 : `processedBars` / `configValid` / `configError` /
  Root ・ Core ・ View ・ Event ・ 終了世代の件数 /
  ZoneView の全フィールド (ID / Phase / Grade / C / H / Density / Touch 番号 /
  Fresh / WeakReason / MaxDepth / FVG 方向・件数・状態 mask / Pending / Snapshot 範囲 /
  物理範囲 / Flip 試行回数 / 表示文字列) /
  RootDebugView の全フィールド + `rootLabelMaskAt()` / ZoneEvent の全フィールド。
  Merge / Split は coreId ・ generationId の推移と Event で見る。
- まとめ Pack と個別 Pack の同値性も同じ仕組みで照らす。
- 違いは **最初の 1 件だけ** 残し、足の時刻 / 項目名 / Version 3 の値 / 新版の値を表へ出す。
  プロットにも 0 (一致) / 1 (不一致) を出す。
- このファイルにだけ `calc_bars_count` がある。目的は「2 つの Engine を同じ本数だけ回して
  照らす」ことで、本番の RE10110 を退けるためのものではない。本番 Harness には入れていない。
- 比較コストはこのファイルの中だけで、本番 Harness は 1 行も背負っていない。

### 同値検証 (未実施)

★ Phase 3B/3C 分の照らし合わせは `ZoneEngineV2_ParityHarness.pine` を使う。
人間が目で表を見比べる必要は無く、差が 1 件でもあれば "DIFF FOUND" とその場所が出る。
手順 : 新版を Publish → Parity Harness の vB import を発行番号へ→ XAUUSD 5分足へ適用。

Phase 2 の変更は「Engine へ渡る Cfg / Feed の値と順序が毎足同一」「Engine 内部の処理は
未変更」という構成上の理由で結果は一致するはずだが、指示どおり Baseline との A/B 比較を
実機で行うこと。比較は同一 XAUUSD 5分足・同一設定・同一計算期間で、Debug table の
Live cores / views / Roots / Pending / Merge・Split / Events、および Zone ラベルの
Core ID / Gen ID / Phase / Grade / C / H / Density / Touch 番号 / WeakReason / MaxDepth /
EffectiveRange / ReferencePrice を突き合わせる。1 項目でも差があればその最適化は採用しない。

### 履歴制限 (Phase 4) について

現時点では `FULL_PARITY` のみ。本番コード (`ZoneEngineV2_VisualHarness.pine`) に
`calc_bars_count` は入れていない。`LIVE_LIGHT` モードは Phase 3 の効果を測ってからでなければ
Warmup 本数を決められない (EMA3000 / EMA slope lookback / Pivot 確認期間 / Accum 最大走査 600 本 /
日足・週足の現行＋前期間 / Zone の Touch・Break・Flip 履歴を全部含める必要がある)。
`calc_bars_count` だけでエラーを隠して完了扱いにはしない。

### Alert Consumer 分離 (Phase 5) について

構造としては既に分離可能: Engine 更新に必要なのは Library の
`newEngine()` / `newCfg()` / `newFeed()` / `resetFeed()` / `feedSwing()` / `feedAccum()` /
`feedFvg()` / `update()` と、読み出しの `eventCount()` / `eventAt()` / `viewCount()` / `viewAt()` だけで、
描画・テーブル・Event Log・Root Debug は Harness 側にしか無い。
Alert 条件は今回決めない (指示どおり)。

## Known limitations

- **Pine Editor でのコンパイル・実行を確認していない。** スクリプトサイズ上限、`request.security` の
  外部要素数、`max_bars_back` の推定は実機でしか確認できない。
- **実行コスト。** 1 バーあたりのクラスタリング量は「現在価格 ±`dormantDistance` の Root 数」に依存する。
  `dormantDistance` を大きくする / `maxSwingRoots` を増やすと、Pine のループ実行時間上限に当たる可能性がある。
  まず既定値 (500 / 180) で Bar Replay を回し、`Debug table` の Root 数を見ながら調整すること。
- **EMA2000 / EMA3000 は 1 分足の履歴深度に依存する。** チャートの遡及範囲が足りないバーでは
  `maValid = false` として MA Root を作らない (Zone は他カテゴリだけで評価される)。
- **Dormant 復帰に 1 確定足の遅延がある** (Deviations 2)。
- **Split / Merge の履歴割当は TouchMark の保持本数に依存する。** 上限で欠けた場合は推測で Fresh へ
  戻さず `touchHistoryTruncated = true` を出す。
- **終了世代の履歴は軽量コピー。** `endedCores` は Side 履歴と範囲だけを保持し、TouchMark は保持しない。
- **受け入れテスト 75 件が未実行。** 実機確認前に本実装を Strategy へ接続してはいけない。

---

## Deferred strategy integration

今回の範囲は Library と表示検証用 Harness までで、**Strategy への接続は行っていない**。

- 既存 Main Strategy は変更していない。旧 `ZoneEngine` を import したままで動く。
- v2 Library に Entry / Exit / TP / SL / RR / 建値移動 / BOS / 上位足環境フィルターは入っていない。
- 旧 `TradePlan` / Structural SL・TP API も入っていない (旧 API との互換も取っていない)。
- Weak は「無効 Zone」ではなく消耗状態として View に出しているだけで、Engine は Entry Signal を作らない。
  将来 Break 方向の検証をするときは `weakReason` (`WeakByTouch` / `WeakByDepth` / `WeakByBoth`) と
  実際の Break イベントを分けて集計すること。

### 次の段階 (推奨手順)

1. `ZoneEngineV2.pine` を Library として Publish し、Harness の import 行のバージョンを合わせる。
2. XAUUSD 5分足で Harness を開き、コンパイルエラーと実行時エラー (ループ時間 / `max_bars_back` / メモリ) を潰す。
3. Debug table の `Config` / `Storage` / `Pending` / `Events this bar` を見ながら Bar Replay で
   受け入れテスト 75 件を埋める (本書の表に PASS / FAIL を記入する)。
4. FAIL が 0 になってから、将来の Signal / Strategy 側の接続設計に進む。接続時に使うのは
   `side` / `phase` / `grade` / `eligible` / 範囲 / ID であり、Score や Strength 整数ではない。
