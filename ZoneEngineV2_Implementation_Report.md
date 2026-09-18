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

### Phase 3F : Candidate / CoreCand のオブジェクトプール化 (実装済み)

#### 先に見つけたコンパイルエラー (Phase 3E で入れてしまっていた)

`export type ZoneEngine` に `array<ZoneCand>` / `array<CoreCand>` のフィールドを追加したのに、
`ZoneCand` / `CoreCand` が非 export のままだった。Pine の export type は非 export 型を
フィールドに持てないので、両型を export した (使うのは Library 内部だけ)。

#### 1 足あたりの allocation

`N_c` = 保存する Candidate 数、`N_k` = CoreCand 数、`W` = dense 窓数。

| | Version 3 | Phase 3F |
|---|---|---|
| `ZoneCand.new` | `N_c` + 探索用 scratch 1 + attach 用 2 | **0** (プールが育ち切った後) |
| Candidate の配列 (6 本/件) | `6 × (N_c + 3)` | **0** (clear + push で使い回す) |
| `CoreCand.new` | `N_k` | **0** |
| CoreCand の配列 (2 本/件) | `2 × N_k` | **0** |
| `array.new<ZoneCand>` / `array.new<CoreCand>` (入れ物) | 3 | **0** (Phase 3E) |
| `array.new_bool` / `array.new_int` (rUsed 他) | 4 | **0** (Phase 3E) |
| `f_newScratchCand()` | 3 (探索 1 + attach 2) | **0** (永続 scratch + プール) |
| `originRootIdsSorted` の再ソート | 追加 Root ごと (`O(n² log n)`) | **1 回だけ** (`O(n log n)`) |
| 窓ごとの allocation | すでに 0 (Phase 3B) | 0 |

ソース上に残っている `ZoneCand.new` / `CoreCand.new` は、
`f_newScratchCand()` と `f_acquireCoreCand()` の **プールが足りないときの伸長分** と
`newEngine()` の初期化だけ。定常状態では 1 つも走らない。

#### originRootIds の重複判定 (同値性)

Version 3 の判定は `array.includes(cc.originRootIds, xid)` 、つまり「すでに push されているか」
だけ。これを `map<int, bool>` に置き換えたので、答えは完全に同じ。
push 順も `originRootIds` の元の順序も変わらず、昇順コピーは最後に 1 回作る。
(Phase 3B で入れた「追加ごとに `f_sortedCopy`」が一番重かった)

#### 参照共有をしていない根拠

- プールの巻き戻しは **1 足に 1 回だけ**、`f_updateCore()` の先頭で行う。
  足の途中では `used` が増えるだけなので、同じ足の中で 2 つの生きた Candidate が
  同じスロットを共有することはない。
  (`f_liveStructurePrune()` が `f_rebuildCores()` より前で `f_buildCand()` を呼ぶため、
   リセットを `f_rebuildCores()` 内に置くのは危険 — ここを直した)
- `f_acquireCand()` / `f_acquireCoreCand()` は取り出し時に **全フィールド** を宣言時の
  既定値へ戻す (`f_fillCandFrom()` が書かない `refPrice` / `selected` も含む)。
- 永続先 (`ZoneCore` / `SideViewState` / Snapshot) へは必ず `f_copyInto()` または
  `array.copy()` で deep copy してから渡す。`ZoneCore` / `SideViewState` は
  `ZoneCand` / `CoreCand` をフィールドとして保持していない (型定義を確認済み)。
- `CoreCand` は sup / res を **index** でしか指していない。

#### 変えていないもの

`export` 関数の署名は全て同一 (diff で確認。差分は `export type ZoneCand` と
`export type CoreCand` の 2 行追加だけ)。探索最大 12 回、dense 探索順、
C / H / Density / BaseStrong、FVG attach 順、Support / Resistance の走査順、
Merge / Split 条件、Core ID / Generation ID、Touch / Weak / Break / Flip / Reclaim、
EMA2000 / EMA3000、Root 保存上限、lookahead、Feed 値、tie-break — いずれも未変更。

### 指示 5 (f_rebuildCores の dirty ゲート) : 検証して **実装しない** と判断

指示の「証明できない場合は skip しない」に従い、入れていない。理由は 4 つ。

1. **窓は毎足動く。** `f_buildPointSnapshot()` と `f_collectFvgRoots()` は
   `refClose = f.baseClose` から `dormantDistance` 以内で絞る。baseClose はほぼ毎足変わるので、
   Root が 1 つも変わらなくても参加 Root 集合は変わり得る。
   したがって dirty 判定自体が毎足窓を再評価する必要があり、安くなるのは
   「窓と全フィールドが完全に一致したときだけ」。
2. **fingerprint に入れなければならないフィールドが多い。**
   rootId / pointPrice / nativeBottom / nativeTop / state / category / subtype /
   tfCode / tfMask / direction / inverseDir / isBroadFvg / fvgFresh /
   confirmedTime / originTime / labelMask / pairKey / isRangeRoot。
   1 つ漏れれば黙って結果がずれる (エラーにならないのが一番悪い)。
3. **後半はどうしても skip できない。** `f_rebuildCores()` のマッチング / Merge / Split は
   `ZoneCore` の physBottom / physTop / phase / matched / pendingTopology /
   pendingGeneration / breakSnap を読む。これらは毎足 `f_rebuildCores()` の前に走る
   `f_processSide()` / `f_processBreakState()` / `f_generationSwitch()` が書き換える。
   つまり skip できるのは前半 (snapshot + 候補生成 + pairSides) だけ。
4. **前半を skip するには前足の sup / res / ccs を残す必要があり、Phase 3F の
   プール化と真っ向から矛盾する。** プールは 1 足ごとに巻き戻す前提で安全になっている。
   両方を成立させるには Candidate を足をまたいで immutable に保持することになり、
   毎足 allocation が戻ってくる (1〜3 の成果を消してしまう)。

よって、`f_rebuildCores()` は引き続き **全確定足で実行** する。
Break / Touch / Flip / Reclaim の状態更新も従来どおり全確定足。

### 指示 1 (topology dirty / cache) : 実装しても発火しないことを確認

指示の dirty 条件には「Root の価格・範囲変更」が入っている。
`f_upsertMa()` は毎確定足で次を書き換える。

```
r.pointPrice    := price          // 1分足 EMA2000 / EMA3000 の値
r.direction     := dir
r.confirmedTime := f.maConfirmTime
```

- `pointPrice` は 1 分足 EMA なので、ほぼ毎 5 分足で値が動く。
- `maConfirmTime` は 1 分足の `time_close[1]` なので **必ず毎足進む**。

この 2 つはどちらもクラスタリングの直接入力。

| 値 | 影響するところ |
|---|---|
| `pointPrice` | 窓の内外判定 / snapshot の並び / Candidate の bottom・top / Density / `f_qualityMa` の `abs(e1p - e2p)` |
| `confirmedTime` | `firstConfirmTime` = `f_candBetter()` の **tie-break 項** |

よって `useMa = true` (既定。EMA 削除は禁止) の間、**dirty は毎足 true になる**。
topology dirty / cache を入れても 1 度も skip できず、fingerprint 計算 (`O(roots + cores)`)
の分だけ **遅くなる**。だから入れていない (判断の問題ではなく算数の問題)。

代わりに、同じ発想 (入力が変わらない作業をやり直さない) を
**実際に成立する粒度** で適用したのが下の Phase 3G。

### Phase 3G (実験 / 既定 OFF) : dense 探索のラウンド間キャッシュ

`ZoneCfg.denseRoundCache` (既定 `false`)。Harness の Debug グループに input を用意してある。
**OFF の間は Phase 3F と完全に同じ経路を通る** (`f_searchDenseBest()` 本体は一切未変更)。

#### 何を削るのか

`f_buildSideCands()` は同じ引数で `f_searchDenseBest()` を 12 回呼ぶ。
ラウンド間で変わるのは `e.scUsed` だけなのに、毎回全開始位置を走査し直している。

| | Phase 3F | Phase 3G (ON) |
|---|---|---|
| 1 ラウンド目 | `O(n · k)` | `O(n · k)` (変わらない) |
| 2〜12 ラウンド目 | 毎回 `O(n · k)` | `O(|affected| · k)` |
| 合計 (Side ごと) | `12 · O(n · k)` | `≈ O(n · k) + 11 · O(|affected| · k)` |

`|affected|` = 前ラウンドで used になった index を読み範囲に含む開始位置の数。
既定では dense 幅 = `M × denseRatio` = 10、snapshot は ±`dormantDistance` = 500 なので、
通常は snapshot 全体のごく一部だけが affected になる。

#### 同値性の根拠 (3 点)

1. **スカン本体は切り出しただけ。** `f_scanStartDense()` は `f_searchDenseBest()` の
   `a` ループの中身を 1 行ずつそのまま切り出して dedent したもの (式に手を入れていない)。
   continue / break の位置、衝突判定、比較子も同一。
2. **全体 best の取り方 (argmax の分解)。** 比較は厳密不等号だけで、完全同値なら
   先に見つけた方が勝つ。`a` を昇順に見て各 `a` の best (= その `a` の中で最初の best)
   を同じ比較で結んでいくと、全走査したときの「最初の best」と必ず一致する。
3. **影響範囲は superset を使う。** used を `continue` で飛ばすため break 位置自体が
   used でずれ得る。そこで「確実にこれ以降は読まない」位置 `dsEnd[a]` を使う :
   並びの正規化 tick は非減少なので、`tick(price[b]) - tick(price[a])` が
   `tick(maxWidth) + 1` を超えた位置以降は幅で必ず break する。
   `+1` は「差の丸め」と「丸めの差」のずれを吸収する余裕。
   superset なので、余分に再計算することはあっても見落とすことはない。

勝った `a` の窓 index 列は `a..dsB[a]` を used を飛ばして歩き直して得る。
`dsB[a]` まで到達した = その途中で break していないので、used でない b は全て push されていた。

#### なぜ既定 OFF なのか

上の 3 点は紙の上では成立するが、**私は実機で A/B を走らせていない**。
指示 5 の「1 項目でも差が出たら採用しない」を満たしていない状態で、
一番 parity に厳しい関数を既定経路にするのは危う。
そのため **既定 OFF (= Phase 3F と完全一致) で出し、A/B で全一致を確かめてから ON にする**
手順にしている。A/B を通したら既定を ON へ切り替える。

#### 指示 3 (Root snapshot / Candidate metadata のキャッシュ) の現状

| 項目 | 状況 | どこで |
|---|---|---|
| Root index | 済 | `map<int,int> rootIdx` + dirty。dense 探索からは 1 回も引かない |
| category / timeframe / direction / confirmedTime / originTime | 済 | `snCat` / `snTf` / `snDir` / `snConfirm` / `snOrigin` (1 足 1 回) |
| identityIds | 済 | Candidate 生成時に 1 回 (Phase 3A) |
| rootIdsSorted / nonFvgIdentitySorted | 済 | `f_finishCandArrays()` で 1 回 |
| C / H / catMask / highMask | 済 | 探索中は増分スカラ、保存時に 1 回 |
| FVG direction / Fresh / structural | 済 | `f_fillCandFrom()` で 1 回、attach 試行は scratch |
| Support×Resistance ごとの `f_identityIds()` | 済 (再実行しない) | Phase 3A |

指示 3 は新規作業なしで完了している。

### 同値検証 (未実施)

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

## Phase 4 : 一括軽量化の実施状況

### 実施したもの

| 項目 | 内容 |
|---|---|
| Parity Harness の廃止 | `ZoneEngineV2_ParityHarness.pine` を削除。参照も全削除。Harness の Engine import は FULL / SAFE とも **1 つだけ** (検査済み) |
| FVG 索引 (項目 6) | `f_buildFvgIndex()` を 1 足 1 回。従来 `f_collectFvgRoots()` が Side ごとに全 Root を走査していた (2 回/足) のを 1 回へ。距離計算も 1 回へ |
| BarContext (項目 1) の既存部分 | 点 Root snapshot (`snRootId` / `snIdx` / `snPrice` / `snCat` / `snTf` / `snTfMask` / `snDir` / `snConfirm` / `snOrigin` / `snLabel` / `snPair`) は 1 足 1 回。FVG 索引をここへ追加 |
| インデックスの mutation gateway (項目 2) | Root の追加 / 削除 / retire は `f_pushRoot()` / `f_removeRootAt()` / `f_retireRoot()` の 3 つだけを通る。`rootIdx` / `originKeyMap` / `psychKeyMap` / `pairTokenMap` / cap dirty をここで維持 |
| Candidate 一括化 (項目 4) | 1 つの snapshot から Dense / Sweep / FVG attach / standalone を作る構造は Phase 3B で完了。nested loop 内の `array.new` / `array.copy` は 0 (機械的に確認済み) |
| Dense 事前計算 (項目 5) | 価格 / category mask / Accum token / side 適格 / 窓の終了 index は snapshot と `dsEnd` で事前計算済み |
| Visual Harness (項目 9) | Engine import 1 つ / 描画・テーブル・Event 文字列は `needRedraw` (= `barstate.islast` 必須) と `show*` の両方が true のときだけ / 過去足では Projection も Event も作らない (Phase 3D) / 描画配列は persistent pool |

### 項目 3 (dirty 統合による topology 再構築の省略) を入れていない理由

指示の dirty 条件には「Root の価格・range 変更」が含まれている。
`f_upsertMa()` は毎確定足で EMA2000 / EMA3000 Root の

```
r.pointPrice    := price          // 1分足 EMA の値 → ほぼ毎足動く
r.confirmedTime := f.maConfirmTime // 1分足 time_close[1] → 必ず毎足進む
```

を書き換える。`pointPrice` は窓判定 / 並び / Candidate の bottom・top / Density /
`f_qualityMa` に、`confirmedTime` は `firstConfirmTime` (= `f_candBetter()` の tie-break 項) に
直接入る。よって `useMa = true` (既定、EMA 削除は禁止) の間は **dirty が毎足 true**。
ゲートを入れても 1 度も skip できず、dirty 判定の分だけ FULL が遅くなる。

これは実装の良し悪しではなく、**指示された dirty 条件をそのまま適用した結果**。
これを回避するには EMA Root を dirty 判定から外すしかなく、それは
「価格が変わっても再構築しない」= 結果が変わる可能性のある skip になるので行わない。

### 項目 7 (Core 再構築の条件実行) を入れていない理由

上と同じ。加えて、`f_rebuildCores()` の Pass 1〜4 は `ZoneCore` の phase /
physRange / pendingTopology / pendingGeneration / breakSnap を読むが、それらは毎足
`f_rebuildCores()` の前に走る `f_processSide()` / `f_processBreakState()` /
`f_generationSwitch()` が書き換える。

### 残っている支配項 (Profiler の数値がないと次を決められない)

| 箇所 | 計算量 | 削るには |
|---|---|---|
| `f_searchDenseBest()` × 12 × 2 side | `12 · O(n · k)` | Phase 3G (既定 OFF。A/B 後に ON) |
| `f_fvgAttachAndStandalone()` | `O(fvg · cand)` | 試行を減らす = attach 順変更になるため不可 |
| `f_rebuildCores()` Pass 1 / 2 / 4 | `O(cores · cands)` | 価格帯索引で `nearOk` が偽の組を事前除外 (未実装 / 要計測) |
| `f_pairSides()` | `O(sup · res)` | 同上 |

## Phase 5 : 全コード監査と dense 探索の事前除外

### 監査結果 (ファイル全体 / 全件抽出)

`tools` の監査スクリプトで、指定された構造を全件抽出し、
包囲関数とループ深度を付けて分類した (Engine 5160 行)。

| 構造 | 件数 | 最大ループ深度 | 処置 |
|---|---:|---:|---|
| `request.*` | **0** | - | Library は 1 つも呼ばない (Feed は Harness から) |
| `label` / `line` / `box` / `table` 生成 | **0** | - | Library に描画なし |
| `array.copy` | 4 | 0 | 全て「新しい ZoneCore を作る箇所」(`f_newCore` / `f_archiveCore`)。新規オブジェクトには新規配列が必要なので削除不可 |
| `array.insert` | 3 | 1 | `f_buildPointSnapshot()` の Version 3 準拠挿入。`array.sort` への置換は禁止されているので維持 |
| `array.sort` | 3 | 0 | `f_medianInPlace` (scratch) / `f_sortedCopy` (比較専用コピー) / `f_collectFvgRoots` (走査順の一部) — いずれも結果に必要 |
| `array.new` | 63 | 0 | 53 件は `newEngine()` (生涉 1 回)。残りは pool 伸長分と Snapshot / View 生成。**nested loop 内は 0** |
| `map.new` | 7 | 0 | 6 件は `newEngine()`。残り 1 件は `f_countAccumBoxes()` (cap dirty 時だけ) |
| `array.includes` | 13 | 1 | 下記内訳 |
| `f_rootIdxById` | 38 | 2 | 下記内訳 |
| 文字列生成 | 10 | 1 | 9 件は originKey / pairKey の組み立て (Root 同一性の鍵。削除不可)。1 件は `f_rootSummary` (表示足のみ) |
| Candidate / Core 生成 | 13 | 1 | 全て pool 経由または新規 Root / Core 生成。毎足の ZoneCand / CoreCand 新規は 0 |
| `array.size(e.roots)` (全件走査の目安) | 21 | 2 | 下記内訳 |
| `for` / `while` | 129 | **2** | 深度 2 は `f_searchDenseBest` / `f_scanStartDense` の a×b と、品質関数 × ids だけ |

#### `array.includes` 13 件の内訳

| 箇所 | 件数 | 処置 |
|---|---:|---|
| `f_rootEssential()` | 6 | prune が必要な足だけ、かつ hot core に限定済み。毎足の hot path ではない |
| `f_markCoreFvgInvalid()` | 3 | FVG が構造無効化した足だけ。探す配列は 1 View の rootIds (数件) |
| `f_qualityMa()` | 2 | ids に EMA1 / EMA2 がいるかの判定。ids は数件〜数十件 |
| `f_identityIds()` | 2 | 重複排除。ソートを入れると push 順 (= identity の順) が変わるので不可 |

クラスタリング / Core マッチングの hot path からは **0 件** (two-pointer / 二分探索へ置換済み)。

#### `f_rootIdxById` 38 件の内訳

- **dense 探索 (最も重い経路) からは 0 件**。必要な値は全て snapshot 配列から直読。
- 深度 2 の 14 件は品質関数 (`f_qualityFvgWith` / `Accum` / `TimeHl` / `Fvg`) 内。
  呼ばれるのは **保存する Candidate ごと 1 回** で、ids は数件。
  1 パスへ統合するには品質判定式を 2 箇所に複写することになり、
  仕様がずれるリスクに見合わないため入れていない (理由を記録)。
- 残りは Root 更新経路の 1 件ずつ (`f_upsertMa` など)。map 引き O(1)。

#### `array.size(e.roots)` 21 件の内訳

毎足全 Root を走査するのは **6 箇所** (`f_updateFvgStructural` / `f_updateFvgInverse` /
`f_updateFvgFresh` / `f_updateTimeHlRoots` / `f_syncPsychRoots` / `f_buildPointSnapshot` +
`f_buildFvgIndex`)。いずれも「Root の状態更新そのもの」または「1 足 1 回の Snapshot 作成」で、
指示 9 が「毎バー必ず実行」と指定している処理。残りは dirty 時のみ
(`f_reindexRoots` / `f_removeRetiredRoots` / `f_pruneCategoryToCap` / `f_countAccumBoxes`)。

### 実施 : dense 探索の事前除外 (項目 5 / **既定経路**)

監査で唤一のループ深度 2 かつ 12 × 2 side 呼び出しと分かった
`f_searchDenseBest()` に、**結果が変わらないと証明できる除外** を入れた。

`f_buildDenseBounds()` を 1 足 1 Side に 1 回だけ走らせ、各開始位置 `a` について

- `dsHardEnd[a]` : `a` の走査が確実に読まなくなる index (真の読み範囲の superset)
- `dsMaxCatCnt[a]` : `[a, dsHardEnd[a])` の category 数 (used を無視した上限)

を求め、`requireStrong` かつ `dsMaxCatCnt[a] < 2` の `a` を丸こと飛ばす。

**同値性の証明**

1. `requireStrong` のとき BaseStrong は `(wC == 2 and wH >= 1) or wC >= 3` を要求するので、
   必ず `wC >= 2`。
2. いかなるラウンドでも `a` の窓は `[a, dsHardEnd[a])` の部分集合 (used は Root を
   減らすだけ、break 位置はこの境界を越えない)。
3. よってその窓の `wC <= dsMaxCatCnt[a]`。`dsMaxCatCnt[a] < 2` なら
   `a` からのどの窓でも BaseStrong になり得ない → best に影響しない。

探索回数 (最大 12)、走査順、break / continue の位置、tie-break、`f_candBetter()` は
1 つも変えていない。近似ではなく、**結果が変わらないと証明できる組み合わせだけの除外**。

心理価格 Root は 50 ドル刻みで大量に生成されるため、孤立した Psych のみの `a` が
多いと見込まれる。そこは 12 ラウンド全てでスキップされる。
(実際の削減率は銘柄と設定依存なので、Profiler での確認が必要)

### 項目 3 / 8 (dirty で Candidate・Core 再構築を省略) を入れていない理由

`f_upsertMa()` が毎確定足で EMA Root の `pointPrice` と `confirmedTime` を書き換えるため、
指定された dirty 条件 (「Root の価格・range 変更」) に毎足該当する。
詳細は上の Phase 4 節に記載。

## Phase 6 : 20 項目の一括処理結果

分類は 3 つだけ : **実装済み** / **変更不要** / **結果同値を保証できないため未変更**。

| # | 項目 | 分類 | 内容 / 理由 |
|---|---|---|---|
| 1 | `f_rebuildCores()` の毎バー廃止 + Topology dirty | **結果同値を保証できないため未変更** | `f_upsertMa()` が毎確定足で EMA Root の `pointPrice` と `confirmedTime` を書き換える。この 2 つは窓判定・並び・Candidate range・Density・`f_qualityMa`・`firstConfirmTime` (tie-break) の直接入力。よって指定された dirty 条件が毎足 true になり skip できない。加えて Pass 1〜4 は Core の phase / physRange / pending / breakSnap を読み、それらは毎足 `f_processSide()` 等が書き換える |
| 2 | `f_buildPointSnapshot()` の挿入順キャッシュ | **一部実装済み** (キャッシュは未変更) | キャッシュは #1 と同じ理由で不可。代わりに **挿入位置探しを tick の二分探索で絞った** (`O(R²)` → `O(R log R + 同 tick 群)`)。tick が違う 2 値の大小は必ず raw の大小と一致するので、tick が小さい範囲は条件が必ず偽 → 調べる必要がない。同 tick 群の中は Version 3 と完全に同じ線形走査。`array.sort` への置換はしていない |
| 3 | Root ID / category / TF / direction / state / FVG / Core membership の全索引化 | **一部実装済み + 変更不要** | 実装済み : `rootIdx` (ID→index) / `originKeyMap` / `psychKeyMap` / `pairTokenMap` / `fvIdx` (FVG)。変更不要 : category / TF / direction 別一覧は、監査の結果毎足全 Root 走査が残る 6 箇所がすべて「指示 9 が毎足必須とした状態更新」または「1 足 1 回の Snapshot 作成」で、索引を作る自体が同じ全走査になる |
| 4 | Hot loop の `f_rootIdxById()` を事前 index 参照へ | **実装済み** | `f_fillCandFrom()` の既存ループで ids の Root index を 1 回解決し `e.scIdxOfIds` へ保持。`f_qualityMa/Swing/Accum/TimeHl/Fvg` はこれを読む。全体 38 → **25 件**、ループ深度 2 の箇所 14 → **2 件**。dense 探索からは引き続き **0 件** |
| 5 | Hot loop の `array.includes()` を mask / map / ソート済みへ | **実装済み** | クラスタリング / Core マッチングの hot path は **0 件** (two-pointer `f_sharedSorted` / 二分探索 `f_containsSorted`)。全体 13 → **11 件** (`f_qualityMa` の 2 件を今回除去)。残りは `f_rootEssential` 6 (prune 時のみ) / `f_markCoreFvgInvalid` 3 (構造無効化足のみ) / `f_identityIds` 2 (push 順を変えられない) |
| 6 | Candidate の C/H/Density/identity/median/range/FVG 品質を 1 回計算し共有 | **実装済み** | Phase 3A/3B。探索中は増分スカラ、保存時に 1 回。`refPrice` も Candidate ごと 1 回キャッシュ |
| 7 | Dense / Sweep / Support / Resistance で同じ Root Snapshot を共有 | **実装済み** | Phase 3B。1 足 1 回の 11 本の並行配列 (`snRootId` 他) を 4 経路で共有 |
| 8 | FVG attach/standalone の FVG×Candidate を事前索引で絞る | **変更不要** | 高コストな `f_fvgTrialEval()` はすでに安価な幾何判定 (`f_rangesTouch` / `f_intervalGap`) で gate されており、索引を入れても除外できるのは同じ幾何判定の再実施分のみ。FVG 側の窓絞りは `f_buildFvgIndex()` で Phase 4 に実装済み |
| 9 | Core×Candidate の gap / shared / membership を 1 回計算し全 Pass で共有 | **結果同値を保証できないため未変更** | Pass 3 の `f_mergeCore()` と Pass 4 の `f_applyCoreCand()` が Core の `physBottom/physTop` と `originRootIdsSorted` を書き換えるため、Pass 1 で求めた gap / shared は Pass 4 時点では古い。キャッシュして共有すると Split 先の選択が変わり得る |
| 10 | Merge / Split / primary Core 選択の重複走査統合 | **実装済み** | Pass 2 を `O(k × cores)` の二重ループから **Core 1 周 `O(cores)`** へ。結果は「k を選んだ Core の coreId 最小」= argmin で、Core ID は一意なので走査順に依らない → 厳密に同値 |
| 11 | Core の waiting/live/mustKeep 用 Root 状態キャッシュ | **変更不要** | `f_coreHasWaitingRoot` / `f_coreHasAnyLiveRoot` はその Core 自身の origin 一覧 (数件) を走るだけで、引きはすでに map で `O(1)`。全 Root 走査ではない |
| 12 | FVG Structural/Fresh/Inverse の全 Root・全 Core 再走査を索引化 | **変更不要** | 索引を作るには同じバー内で全 Root 走査が必要 (この 3 処理の途中で FVG Root が生成されるため)。FVG Root は全体の約 20% なので、全走査 3 回 → 索引再構築 2 回 + 索引走査 3 回 で正味が小さい (約 13%)。無効化リスクに見合わない |
| 13 | Swing/Accum/TimeHL/Psych の全 Root 検索を category/key 索引へ | **一部実装済み + 変更不要** | 実装済み : Swing/Accum/FVG/TimeHL は `originKeyMap`、Psych は `psychKeyMap`。変更不要 : `f_registerSwing()` の同価格探しは新規 Pivot イベントのときだけ (毎足ではない) で、且つ最初の一致で break する順序依存がある |
| 14 | Retired Root / category cap / Core prune / Pending 集計を dirty 時だけ | **実装済み** | `retiredDirty` / `capDirtySwing/Accum/Fvg/Time`。Pending 集計は `O(cores)` の軽いループで、Core prune も dirty 条件付き |
| 15 | Source helper の Accum/Swing/FVG/MA 計算と scratch 再利用 | **実装済み + 変更不要** | 実装済み : `accumCondV2` の `rangeShort = rangeNow` 再利用 (`ta.highest`/`ta.lowest` 2 回削減)。変更不要 : Pack は `request.security` の別評価コンテキストで走るので Engine の scratch を共有できない。`ACCUM_RUN_SCAN_MAX` は未変更 |
| 16 | `request.security` を同一 symbol・同一時間足で統合 | **実装済み** | 10 → **6 call** (既定設定)。`time(tf)` も 9 → **5 本**。UDT Bundle で tuple 要素 192 → **104** (上限 127) |
| 17 | Candidate/CoreCand/一時配列/map/median/sort 配列を pool・scratch 化 | **実装済み** | Phase 3E/3F。定常状態で `ZoneCand.new` / `CoreCand.new` は **0**。nested loop 内の `array.new` / `array.copy` は **0** |
| 18 | 過去足の View/Event/Label/Line/Box/Table 生成を完全停止 | **実装済み** | Phase 3D。`updateVisualLite(buildProjection, captureEvents)`。Library 内の描画生成は監査上 **0 件** |
| 19 | Visual Harness を Engine 1 つの standalone 构成に | **実装済み** | Parity Harness 削除済み。FULL / SAFE とも import 行数 = 1 (検査済み) |
| 20 | 全 `for/while/array.new/copy/insert/sort/includes/f_rootIdxById` の監査 | **実装済み** | `tools/audit_hotspots.py`。包囲関数とループ深度付きで全件抽出し、各群の処置を記録 |

### 旧版 (Phase 5) との差分

| 指標 | Phase 5 | Phase 6 |
|---|---:|---:|
| `f_buildPointSnapshot()` の挿入探索 | `O(R²)` | `O(R log R + 同 tick 群)` |
| `f_rebuildCores()` Pass 2 | `O(k × cores)` | `O(cores)` |
| `f_rootIdxById` 篇所 (全体 / 深度2) | 38 / 14 | **25 / 2** |
| `array.includes` 篇所 | 13 | **11** |

### 残っている Hot loop (全件)

| 箇所 | 深度 | 計算量 | 状態 |
|---|---:|---|---|
| `f_searchDenseBest()` a×b | 2 | `12 · O(n · k)` / Side | Phase 5 の事前除外で `dsMaxCatCnt < 2` の a を全ラウンドスキップ。Phase 3G (既定 OFF) で 2〜12 ラウンドを affected のみへ |
| `f_fvgAttachAndStandalone()` | 2 | `O(fvg · cand)` | 高コスト部分は幾何判定で gate 済み |
| `f_rebuildCores()` Pass 1 / Pass 4 | 1 | `O(cores · cands)` | #9 の理由で共有不可 |
| `f_pairSides()` | 1 | `O(sup · res)` | gap 先判定 + two-pointer 済み |
| `f_qualityFvgWith()` / `f_qualityAccum` の a×b | 2 | `O(ids²)` | ids は数件〜数十件 |

## Phase 7 : バグ修正と 20 項目の再実施

### 1. コンパイルエラー (指摘のとおり、私のバグ)

`f_catPricesMedianSc()` 内の `idx` は未定義だった。Phase 6 の一括置換で使った
関数本体の切り出しが `\n\nf_` を境界にしていたため、`f_qualityFvg` の後にある
コメントブロックを越えて `f_catPricesMedianSc()` まで書き換えてしまっていた。
指示どおり `f_rootIdxById(e, array.get(ids, k))` へ戻し、
`e.scIdxOfIds` は別 Candidate の内容で上書きされる scratch なのでこの関数では流用しない
旨をコメントに残した。

### 2. 静的検査が見逃した原因と修正

旧チェッカは **未定義「関数」だけ** を見ていて、未定義「変数」を見ていなかった。
`tools/check_pine.py` を新設し、**関数スコープ単位の未定義変数検査** を入れた。

- 関数ごとに、引数 / 型付きローカル / tuple 宣言 / ループ変数 / `:=` 対象を scope として集め、
  それ以外の名前の読み出しを全件報告する (file-level global / UDT フィールド / 組み込み / import alias は除外)。
- 併せて、括弧不均衡 / 行を跨ぐ文字列リテラル / 継続行インデントも同じスクリプトで見る。

**回帰テスト済み** : 同じバグを意図的に再導入したコピーを検査すると、
`f_catPricesMedianSc` を含む 5 箇所を `undefined name: idx` として検出する。
現行 3 ファイルは **0 件**。

### 3. Snapshot の計算量記述の訂正と、指定された 2 段構造の実装

指摘のとおり、Phase 6 の記述は誕張だった。二分探索したのは **位置検索の比較回数**
だけで、`array.insert()` の要素移動 `O(R)` が毎件残っていたので、全体は依然 `O(R²)` だった。

今回ご提案の 2 段構造を実装した。

1. 対象 Root を未ソート配列へ push (e.roots 順)
2. `key = tick * 1000000 + 元の順番` を `array.sort_indices` で tick グループ化
   (key は一意なので同値なし = 結果は一意、群の中は元の順)
3. 異なる tick 間は tick 昇順
4. **同一 tick 内だけ** 旧版と同じ挿入処理を元の Root 走査順で再現
5. 完成した tick グループを最終配列へ push

**同値性** : 旧版の挿入条件は `price < pk or (eqT(price,pk) and rootId < ik)`。
tick が違う 2 値は tick の大小と raw の大小が必ず一致するので、
tick が小さい位置は必ず偽・tick が大きい位置は必ず真。したがって旧版の配列は
tick 昇順の群列で、**1 件の挿入が並びを動かすのは自分と同じ tick の群の中だけ**。
よって群ごとに分けて同じ挿入を行い tick 昇順に連結すれば同一の配列になる。

**計算量 (今回の正しい記述)** : `O(R²)` → `O(R log R + Σ g²)` (g = 同 tick 群のサイズ)。
`array.insert` の要素移動も群内に限定される。`array.sort` への単純置換はしていない。

### 4. 「変更不要」を実装に置き換えたもの

| 対象 | 実装内容 | 同値性の根拠 |
|---|---|---|
| 全 FVG Root を永続配列で管理 | `e.catFvg` (rootId の永続配列)。`f_pushRoot()` で append、`f_removeRootAt()` で除去 | `e.roots` は append と `array.remove` だけで並び替えをしないので、この一覧の順 = `e.roots` 順の FVG だけ |
| Structural / Inverse / Fresh | 3 つとも `e.catFvg` だけを走る (全 Root 走査を廃止) | 三つの関数はもともと `r.category == CAT_FVG` のものだけを触る。集合と順序が同じ |
| Swing 同価格探し | `e.catSwing` だけを走る | 同上 (「最初の一致で break」の結果も順序が同じなら同じ) |
| Accum / TimeHL の件数・箱数 | `e.catAccum` / `e.catTime` を走る | 数える対象と条件は未変更 |
| `f_buildFvgIndex()` | `e.catFvg` を走る | push 順は従来と同じ |
| Core × Candidate 比較値 | Pass 1 で `gap` / `shared` を `nc × nk` に保持。Pass 4 の親探しで **その Core が Pass 1 以降書き換わっていなければ** 再利用 | `f_mergeCore()` / `f_applyCoreCand()` を呼んだ瞬間に `coreTouched[ci]` を立て、立っている Core は従来どおり再計算する。比較式と入力が同じなら同じ値 |
| waiting / live / mustKeep (essential 判定) | `f_buildEssentialSet()` で hot Core の membership 合併を `f_pruneRoots()` の先頭で 1 回作り、`f_rootEssential()` は map 引きのみ | hot の定義と 6 本の配列は未変更。Core 状態は `f_finalizeCore()` 後に確定しており、`f_pruneRoots()` 内の Root 削除は Core の membership 配列を変えない |

### 監査数値の推移

| 指標 | Phase 5 | Phase 6 | **Phase 7** |
|---|---:|---:|---:|
| `array.includes` | 13 | 11 | **5** |
| `array.insert` | 3 | 4 | **3** (同 tick 群内のみ) |
| `array.size(e.roots)` (全件走査の目安) | 21 | 21 | **14** |
| 毎足全 Root 走査する関数 | 6 | 6 | **3** (`f_buildPointSnapshot` / `f_syncPsychRoots` / `f_updateTimeHlRoots`) |
| `f_buildDenseBounds()` の呼び出し | 2 / 足 (Side ごと) | 2 / 足 | **1 / 足** (両 Side 共有) |
| FVG attach の Candidate 走査 | 全件 (`O(fvg · cand)`) | 全件 | **帯のみ** (`O(fvg · log cand + Σ hits)`) |
| `f_rootIdxById` | 38 | 25 | 33 |
| Snapshot 構築 | `O(R²)` | `O(R²)` (比較回数のみ減) | **`O(R log R + Σ g²)`** |

`f_rootIdxById` が 25 → 33 へ増えているのは、カテゴリ別一覧が rootId を持つため
解決が必要になったからで、**1 件ごとは map 引き `O(1)`**。
置き換えたのは `O(R)` の全走査なので、呼び出し回数の増加と引き換えに増減は逆向きになる。
この点は「削減」とは記述しない。

### 残っている Hot loop と、Pine 上で同値最適化ができない具体的根拠

| 箇所 | 計算量 | 根拠 |
|---|---|---|
| `f_searchDenseBest()` a×b | `12 · O(n · k)` | 探索する窓の集合を減らせば結果が変わる。Phase 5 の事前除外 (BaseStrong 不可能な a) と Phase 3G (ラウンド間キャッシュ) が、結果を変えずに削れる限度 |
| `f_rebuildCores()` Pass 1 | `O(nc · nk)` | Pass 1 は全ペアの `gap` を知らないと argmax が決まらない。価格帯索引で絞るには Core を範囲でソートした構造が必要だが、Pass 3/4 が Core の範囲を書き換えるためその構造を Pass を越えて保てない |
| `f_rebuildCores()` Pass 4 親探し | `O(nk · nc)` → キャッシュヒット時は `O(1)` / ペア | Phase 7 でキャッシュ済み。書き換わった Core だけ再計算 |
| `f_fvgAttachAndStandalone()` | `O(fvg · log cand + Σ hits)` | Phase 7 で価格帯索引を実装。残るのは帯に入った Candidate の従来判定そのもの (これを減らすと結果が変わる) |
| `f_pairSides()` | `O(sup · res)` | Support 候補ごとに「最もよく一致する Resistance 候補」を選ぶ argmax なので、全ペアの判定が必要。gap 先判定と two-pointer で定数倍は落としてある |
| `f_qualityFvgWith` / `f_qualityAccum` の a×b | `O(ids²)` | 「異なる時間足の別 Box 境界が同じ core にいるか」は全ペア判定。ids は Candidate 1 件分 (数件〜数十件) |

#### FVG × Candidate (Phase 7 で実装) の同値性

同値性の根拠 :
attach が成立するのは `inside or proximal` 、つまり Candidate の範囲が FVG の NativeRange から
`denseWidth` 以内にある場合だけ。attach 対象の Candidate は `isBroadContext` でないので
幅は `clusterMaxWidth` 以下。よって Candidate を `bottom` でソートしておけば、
`[r.nativeBottom - denseWidth - M, r.nativeTop + denseWidth]` の連続帯が superset になる。
その帯を元の Candidate index 昇順に並び直して従来の判定をかければ厳密に同値。
期待効果はこのループで約 4 倍 (fvg 120 × cand 40 の場合)。

索引の key は「索引作成時点の bottom」で固定する。attach による差し替えは
`fb = math.min(cd.bottom, pedge)` なので bottom は減る一方で、かつ差し替え後も
`okWidth` (幅 <= `clusterMaxWidth` = W) を満たすので、常に

    live <= key      かつ      key <= live + W        (key <= live_top <= live + W)

が成り立つ。よって key に対する帯を両側へ W だけ広げれば live な bottom の
必要条件をすべて含む superset になり、足の途中で索引を作り直す必要がない。
`isBroadContext` の Candidate は幅が W を超え得るが、従来の判定でも最初に
`not cd.isBroadContext` で落ちるので、帯に入るかどうかは結果に影響しない。

処理順は帯の中を **元の Candidate index 昇順**へ並べ直してから回すので、
`bestIdx < 0` の first-wins と `f_candBetter()` の tie-break は不変。
Broad FVG の `array.set(cands, ci, ...)` の適用順も index 昇順で変わらない。
(ここで使う `array.sort` は int の昇順 = 全順序であり、Snapshot の非推移的
比較順の代用ではない)

`r.nativeBottom` / `r.nativeTop` が `na` のときは帯を使わず従来の全走査に落とす
(従来もその FVG は 1 件も通らないので結果は同じ)。

### 5. 指示 4 (毎バーの Core 再構築) — 副項目ごとの判定

`f_rebuildCores()` 全体スキップはしていない。指定された 6 つの副項目を個別に判定した。

| 副項目 | 分類 | 内容 / 根拠 |
|---|---|---|
| 静的 Root メタデータの再利用 | **実装済み** | Root は永続 UDT で、`category` / `tf` / `direction` / `nativeTop` / `nativeBottom` / `rootId` / `firstConfirmTime` は `f_pushRoot()` の 1 回しか書かない。毎足 再導出している箇所は監査上 0 件 |
| EMA 2 本だけの価格更新 | **実装済み** | `f_upsertMa()` は `rootIdx` 経由で該当 2 件だけを引き、`pointPrice` / `confirmedTime` を書く。EMA のために全 Root を走る処理はない |
| Snapshot の全フィールド再コピー削減 | **変更不要** | 11 本の並行配列は 1 足 **1 回** 作られ、dense 12 ラウンド × 2 Side + sweep + pair から **`O(n·k)` 回読まれる**。コピーを止めて `snRootId` だけ持ち `rootIdx` + field 参照に変えると、削るのは 1 足 1 回の `O(R)` で、増やすのは最内ループの map 引き。つまり平坦配列化そのものが hot loop を安くしている構造なので、コピー削減はコストを hot 側へ移す変更になる (「効果が小さい」ではなく、方向が逆) |
| Snapshot の**増分**更新 (EMA の移動分だけ差し替え) | **結果同値を保証できないため未変更** | 同 tick 群内の挿入条件 `pr < pk or (eqT and rid < ik)` は非推移的なので、**群から 1 要素を抜くと残りの相対順が変わり得る**。反例 : A, B, C をこの順に挿入し、C の述語が A に対して真・B に対して偽のとき順は `C, A, B` (C は B より前)。A が無い場合は `B, C` (C は B より後)。したがって「EMA Root を抜いて入れ直す」だけでは V3 と同じ配列を再現できない |
| 変化しないカテゴリ品質結果の再利用 (足内) | **実装済み** | 品質 (`f_qualityMa/Swing/Accum/TimeHl/Fvg`) は探索中には一切呼ばれず、確定した Candidate の保存時に 1 回だけ計算する (Phase 3A/3B)。同一 ids に対する足内の重複計算は 0 |
| 変化しないカテゴリ品質結果の再利用 (足をまたぐ) | **結果同値を保証できないため未変更** | cross-bar キャッシュの key には、品質関数が読む可変フィールドを全部入れる必要がある : MA Root の `pointPrice` (毎足変化) と、FVG Root の Fresh / Inverse / Broad フラグ (指示 9 で毎足更新が必須)。ids に MA か FVG が 1 件でも入ると key が毎足変わるため、成立する窓が「MA も FVG も含まない窓」に限定され、しかもその判定自体に全 Root 分の dirty stamp 管理が必要になる。同値を保証できる形にできていない |
| Support / Resistance 共有値の再利用 | **実装済み (Phase 7 で追加)** | Phase 5 では `f_buildDenseBounds()` を Side ごとに 2 回呼んでいた。これは `snRootId` / `snPrice` / `snCat` / `c.mintick` / `maxWidth` だけの関数で、`side` も `scUsed` も読まない。Snapshot は 1 足 1 回しか作られず Support 側の探索も書き換えないので、**1 足 1 回に括り出して両 Side で共有**した。出力は 1 ビットも変わらない |
| Pass ごとの比較結果キャッシュ | **実装済み** | 上の `ccGap` / `ccSh` + `coreTouched`。Pass 1 で保存し、Pass 4 の親探しで未書き換え Core だけ再利用 |

### 6. 20 項目の再確認 (Phase 7 時点)

分類は指定の 3 つだけ。Phase 6 の表で「一部実装済み」としていたものは、Phase 7 の
実装で片付いた分を **実装済み** に、残した分の理由を分けて書き直した。

| # | 項目 | 分類 (Phase 6 → Phase 7) | Phase 7 での状態 |
|---|---|---|---|
| 1 | `f_rebuildCores()` 毎バー廃止 + Topology dirty | 未変更 → **結果同値を保証できないため未変更** | 全体スキップは不可 (EMA が毎足 `pointPrice` / `confirmedTime` を動かし、それが窓判定・並び・range・Density・`f_qualityMa`・`firstConfirmTime` の直接入力)。代わりに上記 §5 の 8 副項目を個別に処置した |
| 2 | Snapshot の挿入順キャッシュ | 一部 → **実装済み** (キャッシュ本体は結果同値を保証できないため未変更) | 指定の 2 段構造を実装。`O(R log R + Σg²)`。キャッシュ (足をまたぐ再利用) は §5 の非推移性の反例により不可 |
| 3 | Root ID / category / TF / direction / state / FVG / Core membership の索引化 | 一部 → **実装済み** | `rootIdx` / `originKeyMap` / `psychKeyMap` / `pairTokenMap` / `fvIdx` に加え、Phase 7 で **category 別永続一覧** (`catSwing` / `catAccum` / `catFvg` / `catTime`) を追加。毎足全 Root 走査は 6 → **3** |
| 4 | Hot loop の `f_rootIdxById()` を事前 index へ | 実装済み | 維持 (`e.scIdxOfIds`)。深度 2 の箇所は **2 件**。総数 33 は category 一覧が rootId 持ちのため増えたもので、1 件は map 引き `O(1)` (削減とは書かない) |
| 5 | Hot loop の `array.includes()` を mask / map / ソート済みへ | 実装済み | 13 → **5 件**。クラスタリングと Core マッチングの hot path は 0 件 |
| 6 | Candidate の品質・identity・median・range を 1 回計算し共有 | 実装済み | 維持 |
| 7 | Dense / Sweep / Support / Resistance で Snapshot 共有 | 実装済み | 維持 + Phase 7 で `dsHardEnd` / `dsMaxCatCnt` も 1 足 1 回の共有に |
| 8 | FVG×Candidate を事前索引で絞る | 変更不要 → **実装済み** | `f_buildFvgCandBand()` で Candidate を bottom 昇順に索引化し (1 Side 1 回)、FVG ごとに `[nativeBottom - bandW, nativeTop + bandW]` (`bandW = denseWidth + clusterMaxWidth + 4 tick`) を二分探索で切り出し、**元の Candidate index 昇順へ並べ直して**従来の判定にかける。帯が全 Candidate になる場合は並べ替えを足さず従来どおりの全走査に落とす |
| 9 | Core×Candidate の比較値を全 Pass で共有 | 未変更 → **実装済み (Pass 1 → Pass 4、無効化付き)** | `ccGap` / `ccSh` を Pass 1 で保持、`coreTouched[ci]` が立った Core だけ再計算。Pass 3 の merge / Pass 4 の apply が書き換えた瞬間にフラグを立てるので、古い値を読むことはない |
| 10 | Merge / Split / primary Core 選択の統合 | 実装済み | 維持 (Pass 2 一本化 `O(cores)`) |
| 11 | waiting / live / mustKeep の Root 状態キャッシュ | 変更不要 → **実装済み** | `f_buildEssentialSet()` を `f_pruneRoots()` 先頭で 1 回。`f_rootEssential()` は map 引きのみ (旧 : Core × 6 配列の `array.includes`) |
| 12 | FVG Structural / Fresh / Inverse の索引化 | 変更不要 → **実装済み** | 3 つとも `e.catFvg` だけを走る。`f_buildFvgIndex()` も同じ |
| 13 | Swing / Accum / TimeHL / Psych の検索索引化 | 一部 → **実装済み** | `f_registerSwing()` の同価格探しは `catSwing` のみ、件数系は `catAccum` / `catTime` のみ。Psych は `psychKeyMap` |
| 14 | Retired / cap / prune / Pending を dirty 時だけ | 実装済み | 維持 |
| 15 | Source helper の再利用 | 実装済み (+ 変更不要) | 維持。Pack は `request.security` の別評価コンテキストなので Engine scratch は共有不可 (Pine の構造上) |
| 16 | `request.security` の統合 | 実装済み | 6 call / `time(tf)` 5 本 / tuple 要素 104 |
| 17 | Candidate / CoreCand / 一時配列の pool 化 | 実装済み | 定常状態で `ZoneCand.new` / `CoreCand.new` は 0、nested loop 内の `array.new` / `array.copy` は 0 |
| 18 | 過去足の View / Event / 描画生成の停止 | 実装済み | `updateVisualLite(buildProjection, captureEvents)` |
| 19 | Visual Harness を Engine 1 つの standalone に | 実装済み | Parity Harness 削除済み。FULL / SAFE とも import 1 行 |
| 20 | 全 hot spot の監査 | 実装済み | `tools/audit_hotspots.py` + **`tools/check_pine.py`** (関数スコープ未定義変数検査) |

### 7. Phase 7 の完了条件に対する自己申告

| 条件 | 状態 |
|---|---|
| Pine コンパイルエラー 0 件 | **静的検査では 0 件** (括弧・文字列・継続行インデント・未定義変数)。TradingView 上でのコンパイルは未実施 (私は TradingView にアクセスできない) |
| 未定義変数 0 件 | `tools/check_pine.py` で 3 ファイルすべて 0 件。バグを戻すと 5 箇所検出することで回帰確認済み |
| 20 項目すべて再確認 | 上記 §6 |
| 「効果が小さい」を未変更理由にしない | 20 項目のうち未変更は **3 件** で、理由は (a) EMA が毎足 `pointPrice` / `confirmedTime` (窓判定・並び・range・Density・`f_qualityMa`・`firstConfirmTime` の直接入力) を書き換える、(b) 同 tick 群挿入の非推移性による反例 (`C,A,B` → `B,C` の順序反転)、(c) cross-bar キャッシュ key に毎足変化するフィールド (MA の `pointPrice`、FVG の Fresh/Inverse/Broad) が入る — いずれも構造的不可能性。Phase 6 で「変更不要」としていた 5 件 (項目 8 / 9 / 11 / 12 / 13) はすべて実装に置き換えた |
| 残した Hot loop の根拠 | §「残っている Hot loop」の表 |
| Snapshot の計算量説明の訂正 | `O(R²)` → **`O(R log R + Σg²)`** と、Phase 6 の記述が「位置検索の比較回数削減」に過ぎなかったことを明記 |
| **RE10110 解消** | **未確認**。Publish・コンパイル・実行・Profiler 計測をいずれも行えていないため、RE10110 が消えたかどうかは検証できていない |
| Root index 共有 / Core Pass 2 一本化の維持 | 両方維持 (`e.scIdxOfIds` / Pass 2 の `O(cores)` 一周)。ただし `f_catPricesMedianSc()` では `scIdxOfIds` を使わない (別 Candidate に上書きされる scratch のため) |

## Phase 8 : 残存オーバーヘッドの削減 (必須 3 件 + 再監査分)

Zone 定義・Root 参加条件・方向判定・探索回数/範囲/走査順・C/H/Density/BaseStrong/Grade・
FVG Fresh/Inverse/attach/standalone・Touch/Weak/Break/Flip/Reclaim・Merge/Split/Core ID/
Generation ID・tie-break/first-wins・`request.security` の意味と lookahead・履歴期間・
保存上限・`denseRoundCache` の既定値 (OFF)・Public API は 1 つも変えていない。

### 必須修正 1 : Essential Set を必要な足だけ構築

```pine
bool needCapPrune = e.capDirtySwing or e.capDirtyAccum or e.capDirtyFvg or e.capDirtyTime
if needCapPrune
    f_buildEssentialSet(e)
```

**同値性** : `e.essIds` を読むのは `f_rootEssential()` だけ。`f_rootEssential()` を呼ぶのは
`f_pruneCategoryToCap()` だけ。`f_pruneCategoryToCap()` を呼ぶのは `f_pruneCatIfDirty()` の
`dirty == true` の枝だけ。よって 4 つの cap dirty が 1 つも立っていない足では
`essIds` の中身は参照されず、prune の選択結果・削除順・削除件数は 1 件も変わらない。
`retiredDirty` だけの足は `f_removeRetiredRoots()` が `state` しか見ないので構築しない。
構築位置は従来どおり Root 削除より前 (`f_removeRetiredRoots()` の手前)。

**削減** : 全 Core × 6 配列 (`originRootIds` / support view / resistance view /
2 つの touchSnapshot / breakSnap) の走査が、cap dirty が立っていない足では 0 回になる。

### 必須修正 2 : Accum Box 集計用 map の scratch 化

`ZoneEngine` へ `map<string, bool> scAccumBoxKeys` を追加し、生成時に 1 回だけ
`map.new<string, bool>()`。`f_countAccumBoxes()` は `map.clear(e.scAccumBoxKeys)` で再利用する。
集計対象 (`CAT_ACCUM` かつ非 `ROOT_RETIRED`)、key (`r.pairKey`)、返却する `map.size()` は不変。
中身は関数の外へ渡さない。

**呼び出し頻度** : `f_pruneCatIfDirty(CAT_ACCUM)` から 1 回 + `f_pruneCategoryToCap()` の
guard ループ 1 周ごとに 1 回。**これで Engine 内の `map.new` は 1 足あたり 0 件になった。**

### 必須修正 3 : Root 追加時の全 reindex を廃止

```pine
int newIdx = array.size(e.roots)
array.push(e.roots, r)
if not e.rootIdxDirty
    map.put(e.rootIdx, r.rootId, newIdx)
```

**同値性** : `e.roots` 末尾への append では既存 Root の index が 1 つも動かない。
したがって dirty でない (= map が完全に正しい) 状態から 1 件足しても map は正しいまま。
すでに dirty だった場合は `true` のまま維持し、次の `f_reindexRoots()` に再構築させる
(古い map を部分更新して「一見きれい」な状態にはしない)。
index がずれる `f_removeRootAt()` は従来どおり `rootIdxDirty := true`。
`f_rootIdxById()` の Root ID 照合と線形探索フォールバックは残してある。
rootId は単調増加の一意値なので、append で既存 key を上書きすることはない。

**削減** : Root が 1 件増えるたびに走っていた `f_reindexRoots()` の
`map.clear` + 全 Root ループ `O(R)` が、append 経路では `map.put` 1 回になる。
心理価格 Root が毎足生成される構成では、この全走査が毎足発生していた。

### 再監査で同じコミットに入れた分

| 対象 | 変更 | 同値性の根拠 |
|---|---|---|
| `f_updateTimeHlRoots()` の `useTimeHL == false` 経路 | 全 Root 走査 → `e.catTime` 走査 | 対象は `CAT_TIME_HL` のみで、`catTime` はその rootId をちょうど保持している。`f_retireRoot()` は `state` と `retiredDirty` を立てるだけなので順序に依存しない |
| `f_pruneCategoryToCap()` の worst 探索 | 全 Root 走査 → カテゴリ別一覧の走査 | 選ぶのは (`confirmedTime` 昇順 → `rootId` 昇順) の**厳密な argmin**。`rootId` は一意なので同値になるペアが存在せず、argmin は走査順に依存せず一意に決まる。よって返す `worstIdx` が指す Root は同じ 1 件で、削除される Root も削除順も不変 |
| 同ループ先頭の `f_reindexRoots(e)` | 追加 | 索引キャッシュの再構築のみ。`f_rootIdxById()` は ID 照合 + 線形探索フォールバックを持つので結果は不変。`f_removeRetiredRoots()` が直前に Root を消して map を dirty にした状態で、カテゴリ別一覧の引きが `O(R)` 線形フォールバックへ落ちるのを防ぐ |

### 静的検査 (完了条件 4)

`tools/check_pine.py` に 2 種を追加した。

| 検査 | 結果 |
|---|---|
| 関数スコープ未定義変数 | 3 ファイル **0 件** |
| **宣言順** (`f_*` / UDT が使用箇所より後で宣言されていないか) | 3 ファイル **0 件**。回帰確認 : `f_lowerBoundFloat` をファイル末尾へ移すと `used before declaration (declared L5530)` を検出 |
| **`request.*` tuple 要素数** (Pine の上限 127、全分岐合計。継続行に分かれた statement の所有者を辿って数える) | FULL / SAFE とも **104 / 127** |
| local scope / 引数照合 | 未定義変数検査に含む。回帰確認 : 旧 `idx` バグを戻すと `f_catPricesMedianSc` で検出 |
| 括弧バランス / 行跨ぎ文字列 / 継続行インデント %4 | 3 ファイル 0 件 |

### 生の `e.roots` 追加・削除 (完了条件 3)

```
1672: array.push(e.roots, r)      → f_pushRoot() の中
1704: Root r = array.remove(...)  → f_removeRootAt() の中
```

`e.roots` に対する `push` / `remove` / `insert` / `set` / `clear` / `pop` / `shift` は
この 2 箇所だけで、どちらも gateway の内側。gateway 外に生の追加・削除はない。

### 残存 hot loop (今回変えていないもの)

| 箇所 | 計算量 | 残す理由 |
|---|---|---|
| `f_searchDenseBest()` a×b | `12 · O(n · k)` / Side | 探索する窓の集合を減らせば結果が変わる。除外できるのは「BaseStrong になり得ない a」だけ (Phase 5 で実装済み) |
| `f_rebuildCores()` Pass 1 | `O(nc · nk)` | 全ペアの `gap` を知らないと argmax が決まらない。価格帯で絞るには Core を範囲でソートした構造が必要だが、Pass 3/4 が Core の範囲を書き換えるため Pass を越えて保てない |
| `f_pairSides()` | `O(sup · res)` | Support 候補ごとの argmax なので全ペア判定が必要 |
| `f_syncPsychRoots()` の全 Root 走査 | `O(R)` / 足 | `f.baseClose` が毎足変わるため dirty で止められない。さらに `need` への push 順が新規 Psych Root の rootId を決めるので、カテゴリ別一覧に分けると **e.roots 順の interleave が崩れて rootId が変わる**。CAT_PSYCH 以外の全カテゴリを 1 本の順序で走る必要がある |
| `f_removeRetiredRoots()` の逆順全走査 | `O(R)`、`retiredDirty` の足のみ | 対象は全カテゴリ (MA / Psych を含む) なので、どのカテゴリ別一覧でも覆えない。逆順走査は削除中の index 有効性を保つため |
| `f_pruneCategoryToCap()` の ACCUM pairKey 一括削除 | `O(R)`、実際に削除する足のみ | 同じ `pairKey` の上下限を両方外すため逆順で全走査する。カテゴリ別一覧に置き換えると削除順と index 有効性の保証を作り直す必要があり、厳密同値を示せていない |
| `f_qualityFvgWith` / `f_qualityAccum` の a×b | `O(ids²)` | 「別時間足の別 Box 境界が同じ core にいるか」は全ペア判定。ids は Candidate 1 件分 (数件〜数十件) |
| `f_updateAccumRoots()` の key 文字列生成 | 3 本 / Box / 足 | `pairKey` は `map<string, bool>` の distinct 判定キーで、Root にも保存され `f_countAccumBoxes()` と ACCUM 一括削除の照合に使われる。int token へ変えると `boxId` の上限を仮定しないと単射性を示せないため、厳密同値を保証できない |

### 残存 allocation (削除できないもの)

| 箇所 | 頻度 | 残す理由 |
|---|---|---|
| `f_newCore()` の `array.copy(cc.originRootIds)` / `array.copy(...Sorted)` / `array.new<TouchMark>()` / `f_newBreakSnap()` | 新 Core 生成時のみ | 生成された `ZoneCore` が配列を**所有**する。CoreCand の scratch を共有すると次の足で上書きされるので、永続オブジェクトへの所有権移動が必須 |
| `f_archiveCore()` の `array.copy` 2 本 + `array.new<TouchMark>()` + `f_newBreakSnap()` | Core 終了時のみ | archive は live Core と別実体でなければならない (live 側の後続変更が履歴へ漏れる) |
| `f_acquireCoreCand()` の `CoreCand.new(array.new_int(), array.new_int())` | **プールを伸ばすときだけ** (定常状態 0) | プールの成長分。1 足あたりの新規生成は定常状態で 0 |
| `array.sort_indices()` × 2 (`f_buildPointSnapshot` / `f_buildFvgCandBand`) | 1 足 1 回 / 1 Side 1 回 | Pine に in-place の `sort_indices` がない。独自ソートへの置換は、Snapshot の非推移的な挿入順・FVG Candidate の元 index 順・負 tick・同 tick・最大 Root 数・int overflow まで含めた厳密同値を示せていないため実施しない (`key = tick * 1000000 + 元 index` の一意性に依存している現行のままにする) |
| `f_emit()` の Event UDT | `captureEvents` が true の足のみ | `updateVisualLite()` の `captureEvents = false` では文字列も UDT も作らない |
| `f_buildViews()` の View / 文字列 | `buildProjection` が true の足のみ | 同上 |

### 1 足あたりの allocation (Phase 8 時点)

| 種別 | 件数 / 足 (定常状態) |
|---|---:|
| `map.new` | **0** |
| `array.new` / `array.copy` (Core 生成・終了以外) | **0** |
| `ZoneCand.new` / `CoreCand.new` | **0** |
| nested loop 内の一時配列・一時 UDT・文字列 | **0** |
| `f_reindexRoots()` の全 Root ループ (append 起因) | **0** |
| `f_buildEssentialSet()` (cap dirty なしの足) | **0** |

### RE10110

**未確認。** TradingView での Publish・コンパイル・実行・Profiler 計測を行えていないため、
RE10110 が解消したかどうかは断言できない。上記は静的検査と計算量の議論のみ。

## Phase 8b : cap prune の件数追跡と reindex 位置の修正

Phase 8 の他の変更 (Essential Set の cap dirty 時限定構築 / `scAccumBoxKeys` の再利用 /
append 時の `rootIdx` 差分更新 / TimeHL のカテゴリ一覧走査) はすべて維持している。

### 1. `f_reindexRoots(e)` を count より前へ

**ご指摘の問題** : Phase 8 では順序が

1. `f_countRootsInCategory()` / `f_countAccumBoxes()`
2. `f_reindexRoots(e)`

だった。1 件削除すると `f_removeRootAt()` が `rootIdxDirty := true` を立てるため、
次の周回の count はカテゴリ内の各 Root について `f_rootIdxById()` の全 Root 線形探索へ
フォールバックし、`O(カテゴリ Root 数 × 全 Root 数)` になっていた。
結果は変わらないが RE10110 対策としては逆効果。

**修正** : `f_reindexRoots(e)` を

- ループに入る前 (最初の count より前)
- 各削除の直後 (次の対象探索より前)

の 2 箇所へ置いた。ループ内の count 自体は下記 2 で廃止したので、
「count が dirty な索引を引く」経路は無くなった。

### 2. 件数を開始時に 1 回だけ取り、削除ごとに減算する

```pine
f_pruneCategoryToCap(ZoneEngine e, ZoneCfg c, ZoneFeed f, int cat, int cap) =>
    int  removed    = 0
    bool stillDirty = false
    f_reindexRoots(e)                                    // count より前
    int cnt = cat == CAT_ACCUM ? f_countAccumBoxes(e) : f_countRootsInCategory(e, cat)
    for guard = 1 to 64
        if cnt <= cap
            break
        ... worst 探索 (protected / essential / current TimeHL / 選択順は現行のまま) ...
        if worstIdx < 0
            break
        if cat == CAT_ACCUM
            ... 同一 pairKey を全削除 ...
            cnt := cnt - 1
        else
            f_removeRootAt(e, worstIdx)
            removed := removed + 1
            cnt := cnt - 1
        f_reindexRoots(e)                                // 次の対象探索より前
    stillDirty := cnt > cap
    [removed, stillDirty]
```

`f_pruneCatIfDirty()` は追跡された `stillDirty` をそのまま受け取り、**終了後の再集計を廃止**した。

```pine
    if dirty
        [rm2, sd2] = f_pruneCategoryToCap(e, c, f, cat, cap)
        rm         := rm2
        stillDirty := sd2
```

### 3. `cnt` を減算できる根拠 (厳密同値)

| ケース | 削除するもの | 件数の変化 |
|---|---|---|
| 非 Accum | worst 探索のフィルタが `category == cat and state != ROOT_RETIRED` を要求するので、**必ず非 RETIRED の当該カテゴリ Root を 1 件** | `f_countRootsInCategory()` はちょうど 1 減る |
| Accum | `worstIdx` の Root は非 RETIRED でその `pairKey` を持つ。削除ループは state を問わず同じ `pairKey` の `CAT_ACCUM` Root を**すべて**外す | distinct `pairKey` 件数はちょうど 1 減る (他の `pairKey` には触らない) |

ループ中に削除以外の state 変更は一切ない (`f_rootProtected()` / `f_rootEssential()` は
読み取りのみ、`f_removeRootAt()` は削除のみ、`e.essIds` はループに入る前に確定している)。
カテゴリ別一覧に同じ rootId が二重に入ることもない (`f_pushRoot()` は 1 回 append、
rootId は単調増加の一意値)。したがって終了時の `cnt` は「その場で再集計した値」と
必ず一致し、`stillDirty` の真偽は従来と同一になる。

各終了経路も従来と一致する。

| 終了経路 | 旧 (ループ後に再集計) | 新 (追跡値) |
|---|---|---|
| 入口で `cnt <= cap` | 即 break → 再集計 → false | false |
| 減算で `cnt <= cap` | break → 再集計 → false | false |
| `worstIdx < 0` (全部 protected / essential) | break → 再集計 → `cnt > cap` = true | true |
| guard 64 回打ち切り | 再集計 → `cnt > cap` | 同値 |

### 4. count / reindex の呼び出し回数 (R = その足で削除した件数)

| | 旧 | 新 |
|---|---:|---:|
| `f_countRootsInCategory()` / `f_countAccumBoxes()` | `R + 2` (ループ先頭 `R+1` 回 + `f_pruneCatIfDirty` の 1 回) | **1** |
| うち dirty な索引を引く count | `R` | **0** |
| `f_reindexRoots()` | `R` (count より後) | `R + 1` (すべて count / 探索より前。`rootIdxDirty == false` なら no-op) |

### 5. 変えていないもの

最大 64 回 / protected / essential / current TimeHL の条件 / 削除対象の選択順 /
Accum の pair 単位削除 / 上限判定 (`cnt > cap`) / Zone ロジック / Public API
(`f_pruneCategoryToCap()` と `f_pruneCatIfDirty()` はどちらも非 export の内部関数で、
呼び出し元は `f_pruneRoots()` 1 箇所のみ)。

### 6. 静的検査

| 検査 | 結果 |
|---|---|
| 関数スコープ未定義変数 | 3 ファイル 0 件 |
| 宣言順 (`f_*` / UDT の前方参照) | 3 ファイル 0 件 |
| `request.*` tuple 要素数 | FULL / SAFE とも 104 / 127 |
| 括弧バランス / 行跨ぎ文字列 / 継続行インデント %4 | 0 件 |

**RE10110 は未確認** (TradingView での Publish・コンパイル・実行・Profiler 計測を行えていない)。

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
