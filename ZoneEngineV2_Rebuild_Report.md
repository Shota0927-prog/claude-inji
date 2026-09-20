# ZoneEngineV2 Rebuild — 実装レポート

版：Strict 20s Architecture v3 準拠  
作成日：2026-09-20  
最終状態：**IMPLEMENTED / NOT VERIFIED ON TRADINGVIEW**（I23 に従う。本作業環境に TradingView が無く、コンパイルも実測も行っていないため `COMPLETE` とは書かない）

---

## 1. 使用した正本ファイル名と SHA-256

| 役割 | ファイル | SHA-256 | 一致 |
|---|---|---|---|
| 論理正本 | `Zone_definition_spec_v2.md`（指示書の `Zone_definition_spec_v2(5).md`） | `f0ada2d851477850aa3d65463056e0318434b0c362383d475d49f9f6e1049cd1` | 指示書 I 冒頭の記載値と**一致** |
| 実装指示書 | `Claude_ZoneEngine_v2_Strict_20s_Implementation_Instructions.md` | `db5b1f7d980ecda6f07ea7522d4a4af4a3b7c57b8bcc8ddb2b84049791125c09` | — |

旧 Engine、旧 Visual Harness、旧軽量版、`貼り付けられたテキスト…txt` は一切参照していない。論理正本ファイルは編集していない。

## 2. Production build ID と公開 Library 番号

- `buildId()` → `ZEV2-REBUILD-STRICT20S-001`（固定文字列。ロジックには使用しない）
- 公開 Library 番号：**未公開 / NOT PUBLISHED**。各 Harness の `import USERNAME/ZoneEngineV2_Rebuild/1 as ZE` を、公開後の実パスへ置き換える必要がある。

## 3. 5 ファイル一覧

| # | ファイル | 行数 | 役割 |
|---:|---|---:|---|
| 1 | `ZoneEngineV2_Rebuild.pine` | 4434 | Production Library。Zone 論理・状態・数値 Event・数値 View のみ |
| 2 | `ZoneEngineV2_Rebuild_VisualHarness.pine` | 479 | indicator。5 request コンテキスト、Feed 組立、最終バー描画 |
| 3 | `ZoneEngineV2_Rebuild_ConformanceHarness.pine` | 569 | 決定論的 Fixture、全走査 Reference、I22 同値テスト、App.B ケース |
| 4 | `ZoneEngineV2_Rebuild_StrategyBenchmark.pine` | 424 | strategy 負荷 Harness。当該足 Event 全件読出し＋数値 checksum |
| 5 | `ZoneEngineV2_Rebuild_Report.md` | 本書 | 設計・対応・テスト・未確認事項 |

Production Library 内の静的確認（I3-1 / 付録 D）:

- `request.` の出現：**0**（コメント行 1 箇所を除く）
- `box.` / `line.` / `label.` / `table.`：**0**（コメント行 2 箇所を除く）
- `str.` の呼び出し：**0**。名称変換 API は `switch` の文字列リテラルを返すだけで、hot path では呼ばれない
- `score` / `bonus` / `zoneHalfWidth` / `BOS` / 50% 地点参照：**0**

## 4. Public API 一覧

I5 の固定 API はすべて実装済み（名称変更なし）。

```
newCfg()                     validateCfg(cfg)             newEngine(cfg)
newFeed()                    updateConfirmed5m(eng,cfg,feed)
viewCount(eng)               viewAt(eng,index)
eventCount(eng)              eventAt(eng,index)
rootCount(eng)               rootAt(eng,slot)
configErrorCode(eng)         buildId()
categoryName(c) sideName(c) phaseName(c) gradeName(c) densityName(c) eventName(c)
```

追加 export（I5 は「少なくとも次を export」と規定しており、追加は禁止されていない）:

```
weakReasonName(code)         resetFeedEvents(feed)
pushSwing(...) pushAccumBox(...) pushFvg(...) pushSourceClose(...)   // Harness→Feed 投入
diag(eng)                    setInstrumentation(eng,on)              // 数値診断のみ
```

API 規則の実装:

- 状態を変更するのは `updateConfirmed5m()` だけ。
- 重複 Feed（同一 `baseSeq` または同一 `baseOpenTime` 以前）は `false` を返し、状態も直前 Event も変更しない。
- `viewAt()` / `eventAt()` は読み出し専用の値コピーを返す。
- `viewCount()` は Live＋Dormant の全 Core × 2 行を返し、最寄りへ絞らない。
- Cfg fingerprint が変わった時だけ再 validation する。invalid 時は状態を進めず数値 error code を返す（0=ok, 1=timeframe, 2=mintick, 4=strongUnlimited+weakOn, 5=strongUntilTouch>=weakFromTouch, 6=範囲外, 7=Feed metadata 不一致）。

## 5. I8 Stage A〜L と実装関数の対応

| Stage | 内容 | 実装 |
|---|---|---|
| A | Cfg 検証・重複 Base 足排除 | `updateConfirmed5m` 冒頭（`cfgFingerprint` / `validateCfg` / dup guard） |
| B | 当該足 Event の logical length を 0 へ | `evClear` |
| C | 前足確定時点の Phase / SideView / Armed 参照 | 前足 Stage J が確定させた `sPhase` / `sArmedBot,Top` / `phSets` / `armedOrder` をそのまま読む |
| D1 | 前足 Armed View の Touch / GapBreak | `stageD_states` 前半（`armedIndexSearch` 抽出 → `sortSideSlots` → `startTouch` / `doBreak(isGap=true)`） |
| D2 | 既存 ActiveTouch の Snapshot 基準評価 | `stageD_states` 中盤（`phSets[2]` 全件） |
| D3 | Break / WeakDepth / Reset / Flip / Reclaim / Inverse / FVG 構造無効化事実 | `stageD_states` 後半（`phSets[3]`、FVG state 3 集合） |
| D4 | 同時成立の優先順位確定 | `stageD_states` 冒頭の invalidation pre-pass（`invCoreList`）と、Break→WeakDepth の評価順 |
| E1 | D4 の FVG 構造無効化を適用 | `stageE_fvgInvalidate` |
| E2 | 新 Root | `stageE_ma` / `stageE_swing` / `stageE_accum` / `stageE_fvgCreate` / `stageE_timeHl` |
| E3 | Root 価格・品質・Fresh・状態更新 | `rootUpdatePrice` / `relabelTimeRoot` / `stageE_fvgFresh` |
| E4 | Root 失効 | `dropTimeRoot` → `rootRetire` |
| F | journal を仕様順で一括適用し索引と revision を更新 | Root 変更は `seedRoots/seedOldLo/seedOldHi` へ積まれ、索引と revision は変更時に差分更新 |
| G | 変更 Root から依存 component を固定点展開 | `expandComponent` + `stageGH_topology` の区間 merge |
| H | component 単位で Side 候補・Core 対応・Merge / Split / Generation 再計算 | `recomputeComponent` |
| I | ActiveTouch 中の変更を PendingTopology へ | `recomputeComponent` の freeze 分岐＋`pendSeedRoots`、解放は `stageGH_topology` 冒頭 |
| J | 次足用 Phase / Grade / Armed / Dormant | `stageJ_phases` |
| K | 保存整理を 1 回だけ | `stageK_prune` |
| L | 数値 Event と確定状態を commit | `updateConfirmed5m` 末尾 |

固定ルールの実装:

- Root イベント 1 件ごとの Candidate/Core 再構築は行わない（全 mutation を積んでから Topology 1 回）。
- 現在足 Touch は Stage C の前足構造（`sArmedBot/Top`）で判定する。
- 現在足で生まれた Root は Stage D の後に登録されるため現在足 Touch に入らない。
- Break と WeakDepth は Break 優先（`doBreak` 実行時は WeakDepth 評価へ進まない）。
- FVG 構造無効化と Reclaim は構造無効化優先（`invCoreList` により当該 Core の Reclaim を当該足で抑止）。
- GapBreak 足では Flip / Reclaim を確定しない（`gapBarBlock`）。

## 6. I9 revision と失効条件

Engine は以下を独立保持する（単一 dirty フラグは使用しない）:

`cfgRevision, rootRegistryRevision, rootPriceRevision, rootEligRevSupport, rootEligRevResistance, rootQualityRevision, fvgStateRevision, fvgFreshRevision, priceOrderRevision, candidateRevSupport, candidateRevResistance, coreTopologyRevision, coreRangeRevision, sideStateRevision, snapshotRevision, pendingRevision, presentationRevision`

Root 単位にも `rGeomRev` / `rQualRev` / `rStateRev` を持ち、component signature（cache key）に含める。

| 変更 | 失効させるもの | 実装 |
|---|---|---|
| Root 追加・削除 | 起源索引、価格順、該当 Side 候補、関連 Core | `rootCreate` / `rootRetire` が seed を積み、当該 component のみ再計算 |
| Root 価格・NativeRange | 旧価格 component と新価格 component の両方 | `rootUpdatePrice` が `seedRoot(slot, min(old,new), max(old,new))` |
| MA 傾き・TF 品質・High | 品質を読む候補と関連 Core | `rQualRev` 更新＋seed |
| FVG direction / state | 該当 Side 資格・FVG 候補・関連 Core・待機状態 | `rStateRev` / `fvgStateRevision` 更新＋seed |
| FVG Fresh のみ | Fresh 出力と Fresh 依存処理 | `fvgFreshRevision` のみ更新。Topology seed は積まない（cache key には含むため、その component だけ再計算される） |
| tie-break 入力（ConfirmedTime 等） | そのRootが参加し得る候補 | signature に `rConfirmedTime` 由来の `rQualRev` / registry revision を含める |
| Touch / Weak のみ | Side state・Event・Snapshot | `sideStateRevision` / `snapshotRevision`。Root 候補は失効させない |
| Break / Flip / Reclaim | Side state と参加資格が変わる構造だけ | `sideStateRevision`、FVG は `rStateRev` |
| Core range / origin | Core 照合・Merge/Split・価格状態索引 | `coreRangeRevision` / `coreTopologyRevision`、`armedOrder` を再挿入 |
| 表示距離・色・文字 | presentation だけ | `presentationRevision`、描画は Harness 最終バーのみ |

## 7. I11 索引と更新関数

| # | 索引 | 実体 | 更新関数 |
|---:|---|---|---|
| 1 | Root ID → slot | `map<int,int> rootIdToSlot` | `rootCreate` / `rootRetire` |
| 2 | 起源 tuple → slot | `map<int,int> originHashToSlot` ＋ **完全 tuple 比較** | `originHashOf` / `originEquals` / `findRootByOrigin` |
| 3 | 生存 Root 価格順 | `priceOrder`（点 Root）/ `fvgOrder`（区間 Root）＋ `rPricePos` | `priceOrderInsert` / `priceOrderRemove`（binary search＋局所挿入） |
| 4 | Category / TF / state 別集合 | `catSets[6]`（＋`rTf`, `rState` による絞り込み） | `catSetAdd` / `catSetRemove` |
| 5 | Accum pair → 上下境界 | `rPairKey`（同一 pairKey は同一候補に入れない） | `stageE_accum` |
| 6 | FVG direction / TF / state / Fresh | `catSets[4]` ＋ `rDir` / `rState` / `rFresh` / `rBroad` ＋ `fvgOrder` 区間索引 | `stageE_fvg*` / `gatherFvgRoots` |
| 7 | Root slot → 参加 Core / Side | `rCoreSup` / `rCoreRes` | `applyWinnerToSide` / `clearSideGeometry` / `detachRootFromCores` |
| 8 | Core ID → core slot | `cLiveList` / `cLivePos`（slot 直参照） | `coreAlloc` / `coreFree` |
| 9 | Core / Side の Phase 別集合 | `phSets[6]` ＋ `sPhasePos` | `setPhase` / `phaseSetAdd` / `phaseSetRemove` |
| 10 | Armed View の EffectiveRange 価格索引 | `armedOrder`（`sArmedBotTick` 昇順、binary search） | `armedIndexInsert` / `armedIndexRemove` / `updateArmedRange` |
| 11 | Break / Flip / Reclaim / Inverse 待ち閾値 | `phSets[3]` / `phSets[4]` ＋ 固定 `BreakSnapshot`、FVG は `rState==3` 集合 | `doBreak` / `stageD_states` |
| 12 | Dormant 復帰価格帯 | `cDormant` ＋ Core range と `dormantDistance` | `stageJ_phases` |
| 13 | prune 対象キュー | **未実装（I25-45 参照）**。上限到達時のみカテゴリ集合を順序付き走査 | `pruneCategory` / `stageK_prune` |

価格順配列の規則:

- 全 sort は初期構築・Cfg 変更・Conformance Reference のみ（`statFullSort` で計数）。
- 通常は旧位置から外して binary search で局所挿入（`statLocalInsert`）。
- 同価格の tie-break は Root ID 昇順で固定。
- `array.remove(0)` と `array.unshift()` は全ファイルで**不使用**。
- hash は不一致の高速除外のみ。一致時は必ず完全 tuple 比較（`originEquals`）。

## 8. I12 Candidate アルゴリズムと計算量

Side 別に 3 段階（段階A 点 Root / 段階B FVG / 段階C 残 Root 通常候補）。`buildSideWinners` が入口。

- 入力：共通価格順 `priceOrder` を binary search で component 幅に絞り、Side 資格 (`sideEligibleRoot`) で filter。Support 用 / Resistance 用に Root 情報を複製しない。
- 幅探索：各 left について right を単調に進める two-pointer。left→right の 1 パスで 6 カテゴリの本数・High 本数・Accum TF 集合・MA 2 本の価格差と傾き・最小 Root ID・最大 ConfirmedTime を**差分更新**する。C=`popcount(categoryMask)`、H=`popcount(highMask)`。
- 各 left について採用する窓は「その left で到達可能な最大 (C,H) を最初に達成する right」。C と H は right に対して単調非減少なので、これより広い窓は comparator（C 降順 → H 降順 → 幅昇順）で必ず負ける。すなわち**数学的に劣後する窓だけを捨てる**exact な枝刈りであり、経験則による打切りは行わない。
- Accum pair 排他：窓を右へ伸ばす途中で同一 `pairKey` が現れた時点で伸長を止める（その先の窓は両境界を含むため不可）。
- 心理価格：窓周辺の 50 ドル刻みを数式で合成し、幅上限を超えない最小拡張のものだけ採用。採用候補が確定するまで Root 化しない（`materialisePsych` は勝者確定時のみ）。
- FVG 付加：`fvgAttach` が区間交差または Proximal edge 局所化で参加可否を決め、Broad は 4 条件（Proximal＋別カテゴリ高密集 / 別 TF 同方向実重複 / 内部に High 品質別カテゴリ / 内部に非 FVG 独立カテゴリ 2 つ以上高密集）でのみ High 側になる。
- Comparator は `cdLess` の 1 関数のみ（C↓, H↓, 幅↑, core 成立時刻↑, 最小 Root ID↑）。他の sort key は無い。
- 採用：comparator 順に貪欲割当。非共有 Root は同一 Side で二重参加させない。Broad FVG のみ共有可。

計算量：component 内の点 Root 数を n、幅 M 内に同時に入り得る Root 数を w とすると窓列挙は O(n·w)、FVG 付加は O(n·f)（f は component 内の Side 適格 FVG 数）、採用は候補数 k に対し O(k log k + k·w)。component は価格的に M 以上離れると切れるため n は局所的に小さい。

## 9. I13 component 展開条件

`expandComponent` は次が 0 件になるまで区間を広げる固定点処理：

1. 区間端から `clusterMaxWidth` 以内に存在する点 Root（価格順配列を binary search して両端へ延長）。
2. 区間と `clusterMaxWidth` 以内で交差する Live Core の範囲。

seed は `seedRoots` に積まれた (Root slot, 旧価格 span, 新価格 span) で、追加・削除・価格変更・品質変更・状態変更・PendingTopology 解放がすべて含まれる。EMA は旧価格位置と新価格位置の両方が seed になる。展開回数に上限は無く、件数による局所化は一切行わない。複数 seed の区間は low 昇順に整列して重なりを merge し、component ごとに 1 回だけ `recomputeComponent` を呼ぶ。

## 10. I14 FVG 状態別集合

- 保持：`catSets[4]`（全 FVG Root）＋ `fvgOrder`（NativeRange bottom 昇順の区間索引）＋ Root 単位の `rDir` / `rState`（1=Active, 3=Invalidated/InverseWait, 4=InverseActive）/ `rFresh` / `rBroad`。
- 構造無効化は、その FVG の元時間足で新しい確定 Close が Feed に来た足でのみ評価（`stageE_fvgInvalidate`）。Distal と同値では無効化しない。BreakBuffer は加えない。
- Fresh 判定は Fresh が残っている Root に対してのみ、`baseCloseTime > confirmedTime` の足から NativeRange と当該 5 分足 High/Low の inclusive 交差で終了させる。終了後は再評価しない。
- FVG×Candidate は `gatherFvgRoots` が価格区間交差で候補を絞ってから、局所化条件と品質を評価する。
- 非重複の同方向 FVG を距離 M だけで結合しない。反対方向 FVG・50% 地点・方向不適格 FVG を C に加えない。
- Broad：未局所化は NativeRange 全体を `DEN_BROAD_CONTEXT`（BaseStrong=false）として保持。複数局所 Zone へ共有可能で参加数に上限は無い。Broad 共有だけでは Core を結合しない（`sharedOriginCount` は Broad FVG を共有 origin として数えない）。
- Inverse：元時間足 Close で無効化 → 確定 5 分足 Close で離脱（`rMovedAway`）→ 確定 5 分足 High/Low で NativeRange 再接触 → 新役割側へ終値回復で `rState=4`。`InverseConfirm` は通常 Touch に数えない。

## 11. I15 Core 対応、Merge / Split

- Side 候補 → 物理 Core：`winnersShareCore` が「非 FVG（非 Broad）origin Root を 1 つ以上共有」かつ「価格的連続性が M 以内」のときだけ Support 候補と Resistance 候補を 1 Core に統合する。単なる価格重複、Bullish/Bearish 別 FVG、Broad 共有だけでは統合しない。Core ID と Generation ID は両 Side 共通。
- 新旧 Core 対応：`recomputeComponent` が (a) `rCoreSup`/`rCoreRes`（Root→Core 索引）、(b) Core 範囲の区間交差、の 2 経路で旧 Core 候補を集め、`sharedOriginCount`（Root ID 完全比較）と interval gap ≤ M で Identity を判定する。全旧 Core × 全新候補の無条件走査は行わない。
- Split：1 つの旧 Core を複数の新 group が要求した場合、共有 origin 数最大（同値なら最小 Root ID）の group が Core ID と履歴を継ぎ、他は新 Core。子 Core へは `ringTransfer` が「実際にその価格帯へ接触した TouchMark」だけを引き継ぐ。`EV_SPLIT` を発行。
- Merge：group が継いだ Core 以外に条件を満たす旧 Core が残る場合、保護状態が無ければ TouchMark を統合（同時刻・同 Side・同接触範囲は `ringHasSame` で 1 回に dedupe）して `coreFree`。`EV_MERGE` を発行。
- 採番と処理順は map 列挙順に依存しない（component 内は winner の comparator 順、状態評価は coreId → generationId → Support → Resistance 順）。

## 12. I16 State 価格索引

| 判定 | 対象抽出 |
|---|---|
| Touch / GapBreak | `armedOrder` を `[min(prevClose,low) − M, max(prevClose,high)]` で binary search。Touch は幅 ≤ M より `effBot ≥ low − M`、Support GapBreak は `effBot ∈ (high, prevClose]`、Resistance GapBreak は `effBot ∈ (prevClose, low)` を必ず含む**必要十分**な範囲 |
| ActiveTouch | `phSets[2]` 全件 |
| Local Break | ActiveTouch 集合（BreakReferenceRange は TouchStartSnapshot）＋ GapBreak は前足 Armed range |
| Reset / 再 Armed | Stage J が Waiting/Armed View を Core 単位で評価 |
| Flip / Reclaim / FlipAttempt | `phSets[3]` と固定 `BreakSnapshot` |
| Inverse | `catSets[4]` の `rState==3` だけ |
| Dormant 復帰 | Core range と現在 Close の距離 |
| Generation 再接近 | `cGenCandActive/Reset/Armed` と新 EffectiveRange の交差 |

抽出後は必ず `sortSideSlots`（coreId 昇順 → generationId 昇順 → Support → Resistance）へ整列してから predicate 評価と Event 生成を行う。map・集合・価格索引の取得順をそのまま評価順に使わない。Event は Stage/Substage の commit 順に append し、Event が無い足では UDT も文字列も生成しない（logical length を 0 に戻すだけ）。

## 13. I17 pool / ring / prune

- Root slot・Core slot は free stack 方式。slot 再利用時は全 field・全索引・ownership token を初期化する。Root ID / Core ID / Generation ID は再利用しない。
- Candidate scratch（`scSlots` / `scAux` / `scAux2` / `scTicks` / `cd*` / `wc*`）は Engine 所有の再利用配列で、`clear()` せず logical length で上書きする。
- `maxTouchMarksPerCore = 64` は Core ごとの ring（head/count）。`maxEndedGenerations = 30` は終了世代 ring。current-bar Event は再利用 pool。`array.remove(0)` は使わない。ring の物理順は公開順に使わず、`ringIndex` で論理時系列順に読む。
- prune は ActiveTouch / Broken / FlipWait / InverseWait / PendingGeneration / 保護 Accum pair を除外し、古い Dormant かつ Root の少ない Core から整理する。心理価格のみの Core は維持しない。`storagePruned` / `prunedRootCount` / `prunedZoneCount` / `touchHistoryTruncated` を診断値に残す。
- 容量不足で保護対象を削除することは無い。

## 14. I25 必須軽量化チェックリスト

**凡例**：IMPLEMENTED = 指定どおり実装 / PARTIAL = 同じ結果を保つ別実装または一部のみ / FAIL = 未実装。PARTIAL と FAIL は理由を明記する。

| No. | 項目 | 状態 | 備考 |
|---:|---|---|---|
| 1 | 確定5分足につきEngine更新1回 | IMPLEMENTED | Library 側 dup guard ＋ Harness の `barstate.isconfirmed` |
| 2 | Source requestを5コンテキストへ統合 | IMPLEMENTED | 1m / 15m / 60 / 240 / D。5m はチャートデータ |
| 3 | Source内計算をBase側で再計算しない | IMPLEMENTED | Pivot・Accum・FVG は Source 内で確定させ、イベントだけ返す |
| 4 | 同一足Root mutationをjournalへ集約しTopology更新1回 | IMPLEMENTED | `seedRoots` journal → Stage G/H で 1 回 |
| 5 | Root／Core／SideをSoA＋flattened array | IMPLEMENTED | 223 の field 別配列、`sideSlot = coreSlot*2 + sideIdx` |
| 6 | Root ID／Core IDとslotを分離 | IMPLEMENTED | |
| 7 | free-slot stackでslot再利用 | IMPLEMENTED | 全 field 再初期化つき |
| 8 | 全論理enumをint、集合をbit mask化 | IMPLEMENTED | categoryMask / highMask / fvgState mask |
| 9 | float原価格と比較用tickを分離 | IMPLEMENTED | 出力は元 float、比較は tick |
| 10 | Root ID→slot、起源、カテゴリ、TF、状態索引 | IMPLEMENTED | |
| 11 | 生存Root価格順を差分更新、毎足全sort禁止 | IMPLEMENTED | binary search ＋ 局所挿入 |
| 12 | EMAは固定2 Rootだけ更新 | IMPLEMENTED | 固定 Root ID、価格と傾きのみ |
| 13 | Swing／Accum／時間高安／FVGをイベント更新 | IMPLEMENTED | |
| 14 | 心理価格を候補周囲だけ数式合成 | IMPLEMENTED | 採用時のみ materialize |
| 15 | Side非依存Root読出しを共有 | IMPLEMENTED | 価格順配列は 1 本 |
| 16 | Support／Resistance候補はSide別に正確評価 | IMPLEMENTED | |
| 17 | 物理ZoneCoreを両Sideで共有し二重生成禁止 | IMPLEMENTED | |
| 18 | two-pointerで幅境界を計算 | IMPLEMENTED | |
| 19 | C／H／Densityを窓移動で差分集計 | IMPLEMENTED | 窓内再走査なし |
| 20 | 落選CandidateのUDT／配列／中央値生成禁止 | PARTIAL | UDT・中央値・文字列は生成しない（中央値は採用構造のみ）。ただし参加 Root ID 列は再利用 pool 上で全候補について書き込む。新規 allocation は無いが「勝者だけ materialize」ではない |
| 21 | Candidate comparatorを1関数へ統一 | IMPLEMENTED | `cdLess` |
| 22 | 数学的上限だけでexact branch-and-bound | PARTIAL | 劣後窓の exact 枝刈り（§8）のみ。上限計算による早期終了は未実装。経験則枝刈りは無し（結果は同一） |
| 23 | Candidate重複は完全Root集合比較後だけ統合 | PARTIAL | 重複統合そのものを行わない（安全側）。異なる Root 集合を統合する事象は発生し得ない |
| 24 | Candidate cacheへ全依存revisionを含める | IMPLEMENTED | component signature（Root ID＋価格＋geom/qual/state rev＋FVG state/Fresh）＋ cfg/registry/quality/fvg revision。hash 一致後に入力列を完全比較 |
| 25 | cache超過時は完全再計算 | IMPLEMENTED | LRU evict → 完全再計算。候補を落とさない |
| 26 | 変更Rootから依存componentを固定点展開 | IMPLEMENTED | |
| 27 | 件数制限による局所化禁止 | IMPLEMENTED | |
| 28 | EMA旧位置・新位置の両componentを再計算 | IMPLEMENTED | |
| 29 | FVGをFresh／state／TF／direction別集合で管理 | PARTIAL | 1 集合＋区間索引＋state/direction/Fresh フラグで等価に絞り込む。8 本の独立 slot 集合は保持していない |
| 30 | FVG×Candidateを価格区間索引で列挙 | IMPLEMENTED | `fvgOrder` |
| 31 | Broad FVGの全局所参加を維持 | IMPLEMENTED | 参加数上限なし |
| 32 | Side候補とCore対応をinterval sweep化 | PARTIAL | component 内 winner 同士の共有 origin＋gap 判定。全域ソート sweep ではない |
| 33 | Root→Core索引で新旧Core候補を抽出 | IMPLEMENTED | `rCoreSup` / `rCoreRes` |
| 34 | hashは不一致除外だけ、一致後完全比較 | IMPLEMENTED | |
| 35 | Merge／Splitをchanged componentだけで処理 | IMPLEMENTED | |
| 36 | Merge各Pass後に依存cacheを失効 | PARTIAL | cache key は Root 入力のみを参照し、Merge/Split は Root 入力を変えないため失効不要という構成。Core を読む cache は存在しない |
| 37 | Phase別Core／Side集合を保持 | IMPLEMENTED | `phSets[6]` |
| 38 | Touch等を価格索引で対象抽出 | IMPLEMENTED | `armedOrder` |
| 39 | ActiveTouch／Flip／Reclaim／Inverse待ちを専用集合化 | PARTIAL | ActiveTouch/Broken/FlipWait は専用 Phase 集合。Inverse 待ちは FVG カテゴリ集合を state で絞る走査 |
| 40 | ageを開始Seqとの差で遅延計算 | IMPLEMENTED | `tsStartSeq` / `bsSeq` / `armedFromSeq` |
| 41 | TouchStartSnapshotをEpisode中固定 | IMPLEMENTED | 可変は `deepestClose` と `maxDepthPct` のみ |
| 42 | current-bar Eventを数値poolで管理 | IMPLEMENTED | |
| 43 | StrategyへEvent APIを提供し全Core走査を不要化 | IMPLEMENTED | Benchmark は Event のみ読む |
| 44 | TouchMarkと終了世代をring buffer化 | IMPLEMENTED | |
| 45 | prune候補queueを差分維持 | **FAIL** | 上限到達時のみカテゴリ集合を走査して最古・未保護を選ぶ方式。差分維持キューは未実装（結果は同一だが指定方式ではない） |
| 46 | `array.remove(0)`／`array.unshift()`禁止 | IMPLEMENTED | 全ファイルで 0 件 |
| 47 | scratchをlogical lengthで再利用 | IMPLEMENTED | |
| 48 | Candidate hot loop内allocation／copy禁止 | IMPLEMENTED | No.20 の但し書きを除き allocation なし |
| 49 | 配列size／Cfg／loop boundをhoist | IMPLEMENTED | 窓走査の上限・tick 換算値は loop 外 |
| 50 | 安い除外条件を先に評価 | IMPLEMENTED | live/state/価格区間 → 集合比較・品質の順 |
| 51 | Engine内の文字列生成禁止 | IMPLEMENTED | 名称 API のみ |
| 52 | Viewを要求時だけ数値Projection化 | IMPLEMENTED | |
| 53 | 描画・sort・文字列を最終バーへ限定 | IMPLEMENTED | Visual Harness は `barstate.islast` のみ |
| 54 | 描画object poolを再利用 | IMPLEMENTED | box/line/label を初回生成し setter で更新 |
| 55 | Production、Visual、Conformance、Benchmarkを分離 | IMPLEMENTED | |
| 56 | 索引と全走査Referenceの同値テスト | IMPLEMENTED（コード） / NOT RUN（実行） | Conformance Harness に実装済み。実行環境なし |
| 57 | 局所再計算と全体再計算の毎足比較テスト | IMPLEMENTED（コード） / NOT RUN | 同上 |
| 58 | 365日以上・3回の性能測定 | **NOT RUN** | TradingView が無く測定不能 |
| 59 | Engine 12秒、Strategy／Visual 20秒gate | **NOT RUN** | 同上 |
| 60 | 不合格時にロジックを変えず停止・報告 | 遵守 | 性能都合のロジック変更は 1 件も行っていない |

## 15. 付録B 75 件の結果

**すべて NOT RUN（理由：TradingView 上でのコンパイル・Bar Replay を実行できる環境が本作業に無い）。**

ただし Conformance Harness には次の 24 ケースが自動判定として実装済みで、TradingView 上で読み込めば即座に PASS/FAIL が表になる：

B1, B2, B3, B4, B5, B8, B21, B26, B41, B42, B43, B45, B47, B48, B49, B50, B51, B52, B54(構成上), B55, B59, B74。

残り（B6, B7, B9〜B20, B22〜B25, B27〜B40, B44, B46, B53, B56〜B58, B60〜B73, B75）は Fixture 未整備のため **NOT RUN**。主な理由：

- B9, B53：一本線 Zone へ価格を到達させる Fixture が未整備。
- B10〜B15：MA カテゴリを Fixture で OFF にしているため（EMA 2 本の傾き組合せ用 Fixture が別途必要）。
- B16〜B20, B22〜B25：Source helper（Pivot 確定時刻、Accum 状態機械、JST セッション境界）の実データ挙動確認が必要。
- B27〜B36：FVG の生成・Fresh・無効化・Inverse・Broad 局所化を通す多足 Fixture が未整備。
- B37〜B40：心理価格を Fixture で OFF にしているため。
- B56〜B58, B60〜B65：GapBreak・Flip 再 Reset・Reclaim・Inverse の個別 Fixture が未整備。
- B66〜B73：ActiveTouch 中の Merge/Split/Root 失効、新世代条件の Fixture が未整備。
- B75：Indicator reload の再現性は TradingView 上でしか確認できない。

## 16. I22 追加テストの結果

| テスト | 状態 | 備考 |
|---|---|---|
| I22.1-1 増分価格順 vs 毎回全sort | IMPLEMENTED / NOT RUN | Conformance Harness の brute force Reference と毎 Fixture 足比較 |
| I22.1-2 two-pointer/差分集計 vs 全subwindow再集計 | IMPLEMENTED / NOT RUN | 同上（全 contiguous subwindow・窓内全再走査の Reference） |
| I22.1-3 Candidate cache ON vs OFF | IMPLEMENTED / NOT RUN | `cacheSize=64` と `0` の 2 Engine を同一 Feed で毎足比較 |
| I22.1-4 局所component vs 全Root全Topology | IMPLEMENTED / NOT RUN | Reference は毎足全 Root から再構築 |
| I22.1-5 FVG価格索引 vs 全pair | **NOT RUN / 未実装** | Reference 側が FVG 付加を再実装していない（Fixture の比較帯から FVG を除外している） |
| I22.1-6 Core interval sweep vs 全旧Core×全新Candidate | IMPLEMENTED / NOT RUN | Reference の最良 core と Production View を比較 |
| I22.1-7 State価格索引 vs 全Core全走査 | IMPLEMENTED / NOT RUN | 同上 |
| I22.1-8 ring buffer論理順 vs 単純時系列配列 | **NOT RUN / 未実装** | TouchMark 読出し API が未 export のため比較不能 |
| I22.1-9 free-slot再利用あり/なし | **NOT RUN / 未実装** | 再利用無効モードを持たない |
| I22.1-10 Debug／描画入力ON・OFFでEngine結果一致 | IMPLEMENTED（構成上） / NOT RUN | Debug 入力は Engine 更新経路に一切入らない（Library に描画・文字列が無い） |
| I22.2 毎足比較項目 | 部分実装 / NOT RUN | View 全項目・Event 件数/内容/順序・C/H/Density/BaseStrong・Range・Phase/Grade/Fresh/Touch番号・WeakReason を比較。Snapshot と PendingTopology の直接比較は API 未 export のため未実装 |
| I22.3 境界ケース | 部分実装 / NOT RUN | Mちょうど・denseWidthちょうど・Reset ちょうど・WeakDepth ちょうど・Break buffer ちょうど・Accum pair・重複 Feed を Fixture 化済み。cache 容量 0 は cfgB で実施。残りは未整備 |

## 17. 365日 Benchmark

**BLOCKED / NOT RUN。**

- `syminfo.tickerid`：未記録（実行していない）
- Base timeframe：5 分（設計上の固定値）
- データ先頭時刻 / 末尾時刻 / Base 本数：未取得
- 各 Source の利用可能期間：未取得
- 通常実行 3 回の実測値：**未測定**
- Runtime limit error / 500ms loop error / collection error：**未測定**

理由：本作業環境から TradingView へスクリプトを読み込み、チャート上で実行することができない。I0-8 / I20.2 に従い、実測していない項目を `PASS` とはしない。

**測定時に想定される制約（I27 該当の可能性）**：1 分足 EMA3000 は 1 分足 3000 本以上の履歴を要し、365 暦日分の 5 分足と同期間の 1 分足の両方が必要になる。TradingView のプラン別 intraday 履歴上限によっては `BLOCKED: DATA AVAILABILITY` となり得る。その場合も短いデータを 365 日合格と読み替えてはならず、EMA を近似で埋めてもならない。

## 18. Profiler 上位 10 箇所

**NOT RUN。** 実測していないため記載しない（推測値は書かない）。

## 19. 最大 Root / Core / Candidate / component / 配列要素数

設計上の上限（Cfg 初期値）:

| 対象 | 上限 | 物理配列への影響 |
|---|---:|---|
| Swing Root | 180 | Root SoA は 31 本の field 別配列 |
| Accum 境界 Root | 60 Box × 2 = 120 | 同上 |
| FVG Root | 120 | 同上 |
| 時間高安 Root | 32 | 同上 |
| 心理 Root | 参加 Core が無くなり次第 retire（実質 Core 数に比例） | 同上 |
| Root slot 合計（概算上限） | 約 460 ＋ 心理 | 31 配列 × 約 500 = 約 15,500 要素 |
| ZoneCore | 80（Live＋Dormant） | Core SoA 18 配列 ＋ Side 配列 46 本 ×（80×2） |
| Side slot | 160 | 46 × 160 = 7,360 要素 |
| TouchMark | 64 / Core × 80 Core = 5,120 | `TouchRing` 8 配列 × 64 × 80 |
| 終了世代 ring | 30 | 5 配列 |
| Candidate cache | 64 エントリ | 各エントリに入力 Root 列（可変） |
| current-bar Event pool | 可変（実測必要） | 14 配列 |

**1 コレクション 100,000 要素未満**という Pine 制約に対して、最大の単一配列は TouchMark ring 1 本あたり 64 要素 × Core 数分の独立オブジェクト（`array<TouchRing>`）であり、単一配列が 100,000 に近づく箇所は無い。ただし**実測は未実施**。

最大 Candidate 数・最大 component 数・最大 component 内 Root 数は実行時カウンタ（`diag()` の `components` / `candidateWindows`）で取得できるが、**未測定**。

## 20. request context 数、tuple 要素合計、Source 利用可能期間

| コンテキスト | tuple 要素数 | 内容 |
|---|---:|---|
| 1 分 | 5 | EMA2000、傾き、EMA3000、傾き、元足確定時刻 |
| 15 分 | 5 | Pivot High/Low、OriginTime、OriginEndTime、確定時刻 |
| 1 時間 | 20 | Swing 4、Accum 4、FVG 7、OHLC/時刻 5 |
| 4 時間 | 20 | 同（Swing 値は na） |
| 日足 | 20 | 同 |
| **合計** | **70** | 127 未満 ✔ |

- unique `request.*()` context 数：**5**（補助 request なし）。5 分 Base OHLC と 5 分 Swing はチャートデータから直接取得。
- 全 context で `gaps = barmerge.gaps_off`、`lookahead = barmerge.lookahead_off` を明示。
- 採用位相：`baseTimeClose >= sourceCloseTime` となる最初の確定 5 分足で 1 回だけ採用し、`lastSrc*` / `lastSwing*` / `lastAccum*` / `lastFvg*` を時間足・イベント種別ごとに保持。機械的な `[1]` は使用しない。
- Source 利用可能期間：**未取得（実行していない）**。

## 21. Runtime / loop / collection / index error 件数

**未測定（NOT RUN）。** 実行していないため 0 件とは書かない。

## 22. 未確認事項、データ制約、Pine 制約

### 22.1 正本から一意に定まらず、実装判断を明示した箇所（I0-6 / I27 該当。**承認が必要**）

1. **Armed の持続**（仕様 7.4 / 12）  
   「距離不足または Zone 内なら Waiting」を文字どおり毎足再判定すると、価格が接近するにつれ Armed が解除され通常タッチがほぼ成立しなくなる。本実装は「一度 Armed になった View は、Touch 開始・Break・Dormant・資格喪失のいずれかまで Armed を維持する」と解釈した。**結果（タッチ回数）に直結するため確認が必要。**
2. **comparator 第 4 キー「core 成立時刻」の定義**  
   参加 Root の `confirmedTime` の**最大値**（＝その構成が揃った時刻）を採用した。代替案：Core の `createdTime`、または最小 `confirmedTime`。同点時の採用候補が変わり得る。
3. **中央値（Reference Price）の偶数個の扱い**  
   中央 2 値の単純平均とした。仕様は「中央値」としか規定していない。表示専用値のためロジック結果は変わらない。
4. **新世代の「基準構造」カテゴリ集合**  
   優先順（直近 TouchStartSnapshot → BreakSnapshot → 世代開始時構造）のうち、付録 A 6.6 の BreakSnapshot は category mask を保持しないため、Break 時点の Side category mask を Core に保存して代用した。
5. **Flip 確定後の旧 Side の Phase**  
   仕様の遷移表は新 Side を Waiting にするとしか書いていない。本実装は旧 Side を Broken（Grade Unavailable）のまま保持し、以後の Reclaim 判定を行わない（15.2「Flip 確定前だけ判定」に従う）。再び反対側が Break した時に旧 Side の履歴が復元される。
6. **心理価格 Root の排他性**  
   「同じ通常 Root を同方向の複数 Zone へ二重参加させない」を心理 Root にも適用した（Broad FVG のみ共有可）。
7. **Broad FVG 単独候補の生成担当 component**  
   同一 Broad FVG が複数 component から重複 Core 化されるのを防ぐため、「NativeRange の下端を含む component だけがその FVG の単独候補を生成する」という決定論的な所有規則を置いた。Zone 論理（Broad の共有可・結合不可）は変更していない。
8. **ActiveTouch 中の component freeze 粒度**  
   ActiveTouch の Core を含む component は、その component 全体の再クラスタを Episode 終了まで保留する（PendingTopology）。Root 参加資格の喪失だけは LiveStructure へ即時反映する。より細かい粒度（当該 Core だけ保留）も解釈可能。

### 22.2 データ制約

- 1 分足 EMA2000 / EMA3000 は、365 暦日の全区間で 1 分足履歴が必要。TradingView のプラン別 intraday 履歴で不足する場合は `BLOCKED: DATA AVAILABILITY` として報告すること（近似・補間は禁止）。
- XAUUSD の `mintick` は Feed の `syminfo.mintick` を使用。Cfg と Feed の `mintick` 不一致は `cfgError = 7` で更新を止める。

### 22.3 Pine 制約（**未検証・実機確認が必要**）

1. **コンパイル可否そのものが未検証。** 本環境に Pine コンパイラが無い。
2. Production Library は 4,434 行・UDT field 298（うち collection 223）。Pine の local scope 数上限・コンパイル済みスクリプトサイズ上限に収まるかは TradingView 上でのみ判定できる。収まらない場合、I27 に従い**ロジックを変えずに**停止・報告し、ファイル分割（Library 2 本化）等の選択肢を提示すること。
3. `for i = 0 to n - 1` は Pine では `n = 0` のとき降順実行となり index out of range を起こすため、全ループへ空範囲ガードを機械的に付与済み（Library 102 箇所、Harness 29 箇所）。
4. `math.round()` / `math.floor()` は float を返すため、index・tick として使う全箇所へ `int()` を付与済み。hash は 32bit 帯（`% 2147483647`）に制限して int64 overflow を回避した。
5. Harness の `import USERNAME/ZoneEngineV2_Rebuild/1` は Library 公開後の実パスに置換が必要。

## 23. ロジック変更の有無

**NONE。**

性能・Pine 制約・実装都合を理由に、Zone 定義 v2 の判定式・状態遷移・処理順・初期値を変更した箇所は無い。旧仕様（score、Reaction Bonus、Flip Bonus、加重平均 Center、FVG 50%、ATR 連動 Zone 幅、BOS、`zoneHalfWidth`）は 1 つも移植していない。付録 D の「存在してはいけない判定依存」は全ファイル検索で 0 件、「存在しなければならないもの」（tick 正規化、ConfirmedTime gate、前足 Armed gate、TouchStartSnapshot、BreakSnapshot、Side 別履歴、Weak 永続化、FVG 方向 filter、PendingTopology、新世代の新カテゴリ条件、決定論的 tie-break、duplicate base bar guard）は全て実装されている。

22.1 に列挙した 8 項目は、正本が一意に定めていない箇所について**明示した解釈**であり、承認前にロジック変更案をコードへ入れてはいないが、1 と 2 は結果に影響するため確認を求める。

## 24. 最終状態

**IMPLEMENTED / NOT VERIFIED ON TRADINGVIEW**

- 5 ファイルは存在する。
- Pine v6 コンパイル：**未実施**（環境なし）。
- 付録 B 75 件：**全件 NOT RUN**（うち 24 件は Harness に自動判定として実装済み）。
- I22 追加テスト：6 項目は実装済みで NOT RUN、4 項目は未実装。
- 365 日 Benchmark と 12 秒 / 20 秒 gate：**NOT RUN**。
- ロジック変更：**NONE**。

I23 に従い、コンパイルと実機実測が完了するまで `COMPLETE` とは報告しない。
