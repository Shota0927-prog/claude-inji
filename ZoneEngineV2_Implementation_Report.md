# ZoneEngine v2 Implementation Report

作成日: 2026-09-18
対象: XAUUSD / TradingView Pine Script v5
基準仕様: `Zone_definition_spec_v2.md`
実装指示: `Claude_ZoneEngine_v2_implementation_instructions.md`

---

## Deliverables

| ファイル | 種別 | 行数 | 内容 |
|---|---|---:|---|
| `ZoneEngineV2.pine` | Pine v5 library (`ZoneEngineV2`) | 3795 | v2 定義の Zone Engine 本体。旧 ZoneEngine とは別名・別実装。 |
| `ZoneEngineV2_VisualHarness.pine` | Pine v5 indicator | 626 | Zone / Root / Event / 診断値の目視確認専用。Strategy 注文は一切無し。 |
| `ZoneEngineV2_Implementation_Report.md` | ドキュメント | - | 本書。 |

既存ファイルの変更: **なし**。
- 旧 `ZoneEngine` (v9 / v10 / v11) のソースはこのリポジトリに存在せず、1 文字も変更していない。
- 旧 `FVG + Zone Engine Strategy` (Main Strategy) も変更していない。
- リポジトリ内の既存ファイル `indicator.pine` (無関係のテンプレート) も変更していない。
- v2 は新しい Library 名 (`ZoneEngineV2`) で、旧 Library を import している既存スクリプトへ影響しない。

Harness の import 行は `import shota0927-prog/ZoneEngineV2/1 as zn2` としてある。
TradingView へ Library を Publish したあと、実際の `<username>/<name>/<version>` に合わせること。

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

### request.security (Harness / 合計 10 call)

| 用途 | 時間足 | call 数 | lookahead |
|---|---|---:|---|
| MA (`maPackV2`) | 1分 | 1 | off |
| Swing (`pivotPackV2`) | 5分 / 15分 / 1時間 | 3 | off |
| Accum (`accumPackV2`) | 1時間 / 4時間 / 日足 | 3 | off |
| FVG (`fvgPackV2`) | 1時間 / 4時間 / 日足 | 3 | off |
| Base 5分 | (チャート足 built-in) | 0 | - |

- すべての pack は「完全に確定した 1 本」しか返さない (内部で index [1] 以降のみ参照)。
- Harness は `ta.change(time(tf)) != 0` でその時間足の確定を検出し、1 回だけ Feed へ入れる。
- Library は `request.*` を 1 つも呼ばない。
- 同じ (時間足, 式) の重複 request は無い。5分 Swing だけはチャート足と同じ時間足だが、位相を他 TF と揃えるため同じ `pivotPackV2` 経路を使っている。

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
