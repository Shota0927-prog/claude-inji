# ZoneEngineV2_Rebuild 実装レポート

作成日：2026-09-19
Build ID：`ZEV2R-20260919-001`
対象：XAUUSD / 確定5分足 / Pine Script v6

---

## 0. 結論（先に読む部分）

| 項目 | 状態 |
|---|---|
| Zone定義v2の論理変更 | **なし**（変更していない） |
| Library / Visual Harness / Report の作成 | 完了 |
| 静的検査（構文規則・ループ境界・前方参照・フィールド名） | 実施済み（本書8章） |
| **Pineコンパイル** | **NOT RUN**（本環境にTradingViewアクセスなし） |
| **実チャート実行・Profiler・実行時間計測** | **NOT RUN**（同上） |
| **付録Bの75ケース** | **全件 NOT RUN**（Pine実機が必要。本書7章に対応表） |
| ユーザー相談が必要な点 | **3件**（本書2章。うち1件は着手前に判明・隔離済み） |

「最適化を何項目入れたか」ではなく実測で完成判断する、という受入条件に従い、
**コード作成完了**と**TradingView確認待ち**を分けて報告します。現時点は前者のみ完了です。

---

## 1. 成果物

| ファイル | 内容 |
|---|---|
| `ZoneEngineV2_Rebuild.pine` | Library本体（2,666行 / export 88件） |
| `ZoneEngineV2_Rebuild_VisualHarness.pine` | indicator。Libraryを1本importし、Engineを1インスタンスだけ動かす（316行） |
| `ZoneEngineV2_Rebuild_Report.md` | 本書 |

既存Engine・既存Main Strategyには触れていません。Parity Harnessは作成していません。
通常版／SAFE版／実験版の分岐は作らず、Engineとharnessは各1系統です。

### 1.1 基準資料

| 資料 | 扱い |
|---|---|
| `Zone_definition_spec_v2.md`（添付） | 論理の正本。全節を実装対象とした |
| `Claude_ZoneEngine_v2_lightweight_implementation_instructions.md`（添付） | 付録A〜Dの論理契約・初期値・受入条件、M章の実装方針 |
| 既存v2 Pineコード | **本リポジトリに存在しない**（`indicator.pine` のMAテンプレートのみ）。式・順序の突き合わせ対象として利用できなかった |
| 改訂前指示書（SHA-256記載のもの） | 本体が無いためハッシュ照合は未実施 |

> 指示書M1.1は「既存コードを式・確定時刻・順序の確認に使う」としていますが、参照コードが
> 入手できませんでした。この影響は2.1に限定されます（他は仕様書と付録で一意に決まります）。

### 1.2 Public API

```text
buildId()
newCfg() / validateCfg() / cfgValid() / cfgError() / cfgDenseWidth()
maPackV2() / pivotPackV2() / accumPackV2() / fvgPackV2()
htfPackSwingV2() / htfPackV2()                      // request統合用
newBaseFeed() / newMaPack() / newPivotPack() / newAccumPack() / newFvgPack()
newEngine()
update(engine, cfg, base, ma, sw5, sw15, sw1h, ac1h, ac4h, acD, fvg1h, fvg4h, fvgD) -> bool
viewCount() / viewAt() / eventCount() / eventAt() / coreCount()
rootCount() / rootAt() / rootInfo()
lastBaseTime() / lastBaseSeq() / engineConfigValid() / engineConfigError()
storagePruned() / prunedRootCount() / prunedZoneCount() / touchHistoryTruncated()
pendingTopologyCount() / pendingGenerationCount()
statCandidates() / statWindowEvals() / statDenseRounds() / statCoreMatches() / statMerges() / statSplits()
categoryName() / sideName() / phaseName() / gradeName() / densityName()
weakReasonName() / rootStateName() / fvgDirName() / eventName() / tfName()
codeSideSupport() ... codeCatCount()                // Harnessが数値定数を直書きしないため
categorySummary() / viewLabelText() / maSlopeText()
```

`ZoneView` はSide別の読み出し専用Projectionで、`rootIds` は `array.copy()` で渡します
（利用側がEngine内部配列を書き換えられない）。Viewは該当Zoneを**すべて**返し、
距離やStrengthでEngine側が1件へ絞ることはしません。

---

## 2. ユーザー相談が必要な点（実装前に判明した1件＋解釈2件）

### 2.1 【要確認・着手前に報告済み】Accum形成条件式が正本に無い

仕様書3.3とパラメータ表は「判定レンジ本数10 / 基準本数20 / ATR本数14 / 上半分最低終値本数4 /
下半分最低終値本数4 / 同色連続上限4 / レンジ幅÷ATR上限2.5 / 短期幅÷基準幅上限0.70 /
ドリフト上限0.30」を規定していますが、**各条件の算式そのもの**は規定していません。
既存v2コードも本リポジトリにありません。

これは「論理変更」ではなく「正本の欠落」なので、作業を止めず、次のように処理しました。

- 式を `accumCondV2()` **1関数へ隔離**（他層はこの関数の真偽値しか見ない）。
- 現在の解釈：
  - `shortRange = highest(high,10) - lowest(low,10)`
  - `shortRange <= atr(14) * 2.5`
  - `shortRange <= (highest(high,20) - lowest(low,20)) * 0.70`
  - 直近10本で `close > (shortHigh+shortLow)/2` の本数 >= 4
  - 直近10本で `close < (shortHigh+shortLow)/2` の本数 >= 4
  - 直近10本の同色（実体方向）連続本数の最大 <= 4
  - `|close - close[10]| / shortRange <= 0.30`（ドリフト）
- Box境界・確定イベント・Candidate非Root化は仕様どおり（ATRは境界へ持ち出さない）。

**確認依頼**：この7条件の式で確定してよいか、別の正本があるか。差し替えは
`accumCondV2()` の置換のみで完結します（他層は無変更）。

### 2.2 【解釈】Broad FVGのProximal局所化と「Dense Strong coreを薄めない」の同時適用

- 仕様5.2：Dense Strong coreへcore外Rootを入れて広げない（受入45）。
- 仕様3.5/5.5：Proximal edge周辺に別カテゴリが高密集なら EffectiveRange は
  「Proximal edge 〜 局所Root分布」。

両立のため、**Proximal edgeまで広げた結果がその候補の密集クラス（High Density）を
維持できる場合にだけ**その付加を採用しています。維持できない場合はFVGを付加しません
（FVGは削除せず、単独候補／Broad contextとして残ります）。
「常に広げる」解釈に変更すると、受入45の結果が変わり得ます。**どちらを正本とするか要確認。**

### 2.3 【解釈】Inverse FVGの手順2〜4で使う終値の時間足

仕様10.6は手順1（構造無効化）を「元時間足終値」と明記し、手順2〜4は時間足を明記していません。
本実装は手順2〜4を**確定5分足終値**で評価します（Engineの時計に合わせ、Flip手順と対称）。
元時間足終値で評価する仕様であれば、`updateFvgInverse()` の入力を差し替えます。

### 2.4 承認を求めていない事項（＝変更していないもの）

指示書M1.3に挙がる項目は一切変更していません。特に、
**探索候補・探索回数・走査範囲の削減、近似探索、途中打ち切り、履歴短縮、保存上限縮小、
lookahead/offset/採用タイミング、同時イベント優先順位、tie-break、ID採番順は変更なし**です。
既存コードにあったとされる「Dense探索最大12回」のような上限は、正本に無く既存コードも
参照できないため、**新たに導入も撤去もしていません**（探索はRoot割当で単調に減るため停止します）。

---

## 3. 旧構造から作り直した点（設計）

| 層 | 保持するもの | 更新契機 |
|---|---|---|
| Source/Feed | 元足の確定値、検出イベント、採用時刻 | 各元足の確定。Library内では`request.*`を呼ばない |
| Root registry | 起源・価格・NativeRange・参加資格・カテゴリ | 対象Rootの実変更のみ |
| Candidate evaluator | Side別候補、範囲、C/H、Density、比較情報 | 入力変化時 |
| Core association | 同一性・Merge・Split・PendingTopology・世代 | 関連Candidate/Coreの変化 |
| State transition | Touch/Weak/Break/Flip/Reclaim/Inverse | 確定5分足すべて |
| Read API | View・当該足Event | 利用側の読み出し |
| Presentation | 選択・文字列・box/line/label/table | Harness側のみ |

主要な作り直し：

1. **Root IDと保存slotの分離**：`idToSlot` map、`liveOrder`（Root ID昇順の走査順）、
   `freeSlots`（slot再利用）。論理IDは再利用しない（心理価格のみ仕様7.7に従い同一価格＝同一安定ID）。
2. **カテゴリ別索引**：`idxMa / idxSwing / idxAccum / idxTime / idxFvg / idxPsych`。
   カテゴリ限定の更新（FVG Fresh、構造無効化、時間高安、整理）で全件走査しない。
3. **起源キー索引**：`originToId` によりSwing/Accum/FVGの重複イベント登録を防止。
4. **価格順は1回のnative sort＋同値タイ整列**：`array.sort_indices` の後、
   同一priceTick区間のみ Root ID昇順へ整列（毎足の比較結果が変わらない）。
5. **候補探索は数値のみ**：落選候補でオブジェクト／文字列／中央値を作らない。
   採用時にだけ実データを確定（`adoptWindow`）。
6. **Reference Priceは採用構造に対して1回だけ計算**し、その値を保持
   （ActiveTouch中にRootが動いても当時の値が残る）。
7. **dirtyフラグを用途別に分離**：`dirtyRootSet / dirtyRootPrice / dirtyQuality /
   dirtyFvgState / dirtyCore`（単一のtopologyDirtyでEngine全体を止めない）。
8. **scratchはEngine所有で再利用**：`sLot* / sUsed / sCatCnt / sPairs / sTmp* / sRefs / cand*`。
   Snapshotだけは `array.copy()` で独立所有（参照共有しない）。

---

## 4. 仕様書・付録Aへの実装対応表

| 仕様 | 実装箇所（`ZoneEngineV2_Rebuild.pine`） |
|---|---|
| 1.1-1.4 Root / Category / ZoneCore / Side View | `type Root` / `type ZoneCore` / `type SideViewState` |
| 1.5-1.6 NativeRange と EffectiveZoneRange | `Root.nativeBottom/nativeTop` と `SideViewState.effectiveBottom/Top`。判定は常にEffective |
| 1.7-1.8 構造品質と消耗状態の分離 | `cCount/hCount/density/baseStrong` と `SideHistory`（別オブジェクト） |
| 1.9 Phase / Grade | `finalizeSide()` / `gradeOf()`。別フィールドで別表示 |
| 1.10 Zone generation | `startGeneration()` / `genBaselineCatMask` |
| 2 独立カテゴリ6 | `CAT_*` と `popCount6(catMask)`。同カテゴリ本数はCへ加算しない |
| 3.1 MA | `ingestMa()`。EMA2本を別Root、固定ID、現在値のみ、傾きは確定5分足で更新、High条件は`scanBest()`内 |
| 3.2 Swing | `pivotPackV2()`（OriginTime/OriginEndTime/ConfirmedTime分離）、`swingIngestOne()`（同一イベント統合＋TF mask保持） |
| 3.3 Accum | `accumPackV2()`（Candidateは非Root、true→falseで1回だけ確定、終了足は含めない）、上下限は`pairKey`で排他 |
| 3.4 時間区切り高安 | `updateTimeHL()` / `timeLabelSet/Drop/Move`。ヒゲ先、厳密な`>`/`<`、新極値＝新ID、期間移行はID維持 |
| 3.5 HTF FVG | `fvgPackV2()` / `applyFvgState()` / `updateFvgInverse()` / `attachFvg()`。50%は一切使わない |
| 3.6 心理価格 | `syncPsych()`。100ドル=Major1本、50ドル=Standard、Hにならない、単独でZoneを作らない |
| 4.1-4.3 Side View / 役割 | `fvgSideEligible()` / `applyCandidate()`（eligible） / 1 ZoneCore に2 View |
| 5.1 Mと密集度 | `denseTickLimit()/mTickLimit()`、幅はEffective全幅、等号は狭い側、数珠つなぎ禁止（全幅で判定） |
| 5.2 Dense core優先 | `buildCandidates()`：Base Strongのdenseラウンドを先に実行し、残Rootで通常候補 |
| 5.3 クラスタ競合 | `scanBest()` の比較関数（C↓ H↓ 幅↑ 成立時刻↑ 最小RootID↑）1か所のみ |
| 5.4-5.5 範囲 | 点Root＝参加実価格のmin〜max（1本なら一本線）。FVGは局所化規則。描画幅は不使用 |
| 5.6 ZoneReferencePrice | `computeRefPrice()`。カテゴリ代表の単純中央値、重み付けなし、FVG 50%不使用 |
| 5.7 複数Zoneの重なり | `associateCandidates()`。Broad共有だけでは結合しない。Viewは全件返す |
| 6.1 品質集約 | `scanBest()` のhMask（1カテゴリH最大1）。ActiveTouch中はSnapshot品質固定 |
| 6.2 Base Strong | `C==2 && High && H>=1` / `C>=3 && High`（`scanBest`と`candRefresh`の同一式） |
| 6.3 点数制の排除 | score/bonus/合計加点は存在しない（8章の静的確認参照） |
| 7.1 Phase | `PH_*`、`finalizeSide()` |
| 7.2 Grade順序 | `gradeOf()`：Unavailable → Weak → Strong → Neutral |
| 7.3 Root確定前禁止 | 各ingestの `confirmedTime <= baseCloseTime` gate |
| 7.4 Armed条件 | `finalizeSide()`：`armedFromSeq = seq + 1`（当足では開始不可） |
| 8.1-8.4 タッチEpisode | `armedEval()` / `startTouch()` / `activeEval()`。同一足Reset完了も可能 |
| 9.1 Strong期限 | `gradeOf()` と `validateCfg()`（strongUntilTouch < weakFromTouch を強制） |
| 9.2 WeakDepth | `activeEval()`：Snapshot範囲、確定終値のみ、clamp 0-100、閾値同値でWeak、一本線は不使用 |
| 9.3 Weak維持 | Side別に保持。解除は`startGeneration()`のみ。WeakByTouch/Depth/Bothを区別 |
| 10.1 ローカルBreak | `activeEval()` → `applyBreak()`。確定終値1本、ヒゲ抜けは不可、Break優先 |
| 10.2 GapBreak | `armedEval()`：非交差＋Break終値。TouchCount/WeakDepth/Freshを変えない。同足でFlip/Reclaimしない |
| 10.3-10.5 Flip / Attempt / Reclaim | `processBreakState()`。基準は必ず`BreakSnapshot` |
| 10.6 Inverse FVG | `updateFvgInverse()`。通常Touchに数えない、Cを増やさない |
| 11.1-11.4 Snapshot / LiveStructure / Pending | `TouchStartSnapshot`（開始後はdeepestClose/maxDepthPctのみ更新）、`sideHasLiveNonPsych()`、`pendingTopology` |
| 12.1-12.3 同一性 / Merge / Split | `candSharesOrigin()`＋`intervalGap<=M`、`mergeCores()`、`splitCore()`（TouchMarkの実接触で割当） |
| 13 新Zone世代 | `updateGenerationCandidate()` ＋ `startTouch()` 冒頭の切替（その接触が新世代Touch 1） |
| 14 Zoneの有効期間 | `associateCandidates()` 末尾（待機Root・保護Phaseがある限り保持） |
| 15 同一5分足内の処理順 | `update()` のA→J（本書5章） |
| 16 Fresh 3種 | `ZoneCore.zoneFresh` / `SideHistory.sideFresh` / `Root.fvgFresh` |
| 17 出力 | `ZoneView` / `ZoneEvent`（Weak Break検証用の値をすべて含む） |
| 18 初期パラメータ | `ZoneCfg` 既定値。判定式に数値直書きなし |
| 19 Zone定義へ入れないもの | 環境認識・TP/SL・BOS・他銘柄・エントリー足FVGは一切なし |

---

## 5. 確定5分足1本の処理順（実装）

```text
update(engine, cfg, feed...):
  cfg fingerprint 変化時のみ validateCfg（不変中は再利用、永久スキップはしない）
  configValid かつ baseConfirmed かつ 新しい baseOpenTime のときだけ処理（重複足ガード）
  当該足Eventをクリア

  pre) FVG構造無効化の「事実」だけを先に確定（markFvgInvalidation）
       → Reclaimより優先（仕様15）。registry変更はここでは行わない
  A)  前足Armedだったviewだけ、現在High/LowでTouch または GapBreak
  B)  ActiveTouchをTouchStartSnapshot基準で評価
  C)  Break / WeakDepth / Reset / Flip / Reclaim / FlipAttempt
  D)  同時イベント優先：Break > WeakDepth、FVG無効化 > Reclaim、GapBreak足はFlip/Reclaim不可
  E)  FVG状態適用、Inverse進行、MA更新、Swing/Accum/FVG登録、時間高安更新
  F)  LiveStructure（参加資格喪失は即時反映＝sideHasLiveNonPsych）
  G)  価格順再構築 → 心理価格同期 → 候補生成（Dense→通常→FVG）→ Core対応付け
      ActiveTouch中のCoreは形状を適用せず pendingTopology
  H)  世代候補の更新（新独立カテゴリ＋Base Strong＋離脱）
  I)  次足用 Phase / Grade / Armed / Dormant を確定
  J)  保存整理（保護対象は削除しない）→ read-only View生成
```

同時成立の扱いは付録A第11節と仕様15節のとおりで、変更していません。
**新Rootによる強化は当該足のTouchStartSnapshotへ後付けしません**（Snapshotは開始時に凍結）。

---

## 6. M16 監査表（24項目）

| No. | 対象 | 実施内容 | 効果 | 計測 |
|---:|---|---|---|---|
| 1 | 全確定足の更新契約、重複Feed排除 | `baseOpenTime` 単調増加ガード、`seq`はEngine採番 | 二重更新なし | NOT RUN |
| 2 | Source helperの式の重複・初期化 | 窓集計を1関数へ集約、Accumは状態機械で1回のみ確定 | 元足あたりの重複計算を排除 | NOT RUN |
| 3 | request統合・Feed採用時刻 | 1m/15m/1H/4H/1D の**5コンテキスト**。5mはチャート直接計算。tuple 5/8/29/21/21要素 | 外部request 5系統 | 数は静的確定、負荷はNOT RUN |
| 4 | Root ID／起源／カテゴリ／TF索引 | `idToSlot` `originToId` `idxCat*` `psychTickToId` | 全件走査の除去 | NOT RUN |
| 5 | 削除・slot再利用・索引更新 | slot再利用＋`liveOrder`（ID昇順）＋`freeSlots` | 削除時の全要素ずらしを回避 | 実測比較は NOT RUN |
| 6 | 固定Rootと移動Rootの価格順 | 毎足 native sort 1回＋同値タイのみ局所整列 | `O(R log R)`＋小さな定数 | NOT RUN |
| 7 | Support/Resistance共通読み出し | 価格・tick・起源は共有、FVG資格/MA品質/使用済み/Side履歴は分離 | 重複計算の削減 | NOT RUN |
| 8 | Dense初回探索の窓境界と増分品質 | 開始位置ごとにtick幅で終端を打ち切り、窓内カテゴリ・High入力を**増分更新**。全部分窓を比較 | `O(R·k)`（k=窓内本数） | NOT RUN |
| 9 | Denseラウンド間の再利用 | **未実装**。各ラウンドを完全再計算（同値保証を優先） | 効果なし（残る負荷として記載） | NOT RUN |
| 10 | 通常候補生成とRoot使用済み管理 | `sUsed` で使用済みを除外し、残Rootだけで再探索。Broad FVGのみ共有可 | 二重参加なし | NOT RUN |
| 11 | FVG Fresh/無効化/Inverse対象集合 | `idxFvg` をTFで絞り、Fresh終了済みはFresh判定をしない | 対象限定 | NOT RUN |
| 12 | FVG付加・重複・standalone | 安価な幾何条件（交差／Proximal距離）で足切り後に品質判定 | 高価な判定の回数削減 | NOT RUN |
| 13 | C/H/Density/identityの再計算 | 付加時は `candRefresh()` で差分再評価 | 全再計算の回避 | NOT RUN |
| 14 | Referenceの計算と保存 | 採用候補のみ1回計算し保持（過去足の遅延再構築はしない） | 落選候補の中央値計算をゼロに | NOT RUN |
| 15 | Support/Resistance候補のCore統合 | 同一非FVG起源＋M以内で1 Coreの2 View | 物理Zoneの二重生成なし | NOT RUN |
| 16 | Core×Candidate照合、Pass間失効 | 範囲gapの安価な事前判定→起源集合の突合。Merge後は更新済みCoreで後続判定 | 全組合せの重い照合を回避 | NOT RUN |
| 17 | Merge/Split/TouchMark割当 | 実接触範囲の交差で子へ割当、同時刻・同Sideはdedupe | 集計値代替をしない | NOT RUN |
| 18 | ActiveTouch/Snapshot/Pending/世代 | 形状変更はPendingTopology、資格喪失のみ即時 | 仕様どおり | NOT RUN |
| 19 | Dormant復帰・prune・保護 | 保護集合を整理1回につき1度だけ構築 | 削除ごとの再構築を回避 | NOT RUN |
| 20 | scratch/pool/deep copyの境界 | Engine所有のscratchを再利用。Snapshot/Viewは`array.copy()` | 候補評価内のarray.new を排除 | NOT RUN |
| 21 | map/cacheの寿命・容量超過 | 索引サイズは生存Rootに連動。`psychTickToId`のみ安定ID用に永続（512超で再初期化） | mapの無制限増加を防止 | NOT RUN |
| 22 | View/Event APIと文字列の分離 | 数値Viewと`viewLabelText()`を分離。Event文字列は蓄積しない | 表示OFFでも論理不変 | NOT RUN |
| 23 | 描画再利用・Debug・rollback | box/line/labelを起動時に生成しsetterで更新。`varip`の描画済みフラグを使わない | 再描画コスト削減 | NOT RUN |
| 24 | Pineコンパイル・実機・長期性能・公開版整合 | **未実施**（環境なし） | - | NOT RUN |

### 6.1 キャッシュ一覧（キー／失効／容量／fallback／所有）

| 対象 | キー | 失効条件 | 容量 | 容量超過時 | 所有 |
|---|---|---|---|---|---|
| `idToSlot` | Root ID | 登録／削除 | 生存Root数 | なし（生存数に連動） | Engine |
| `originToId` | 起源キー | 登録／削除 | 生存Root数 | なし | Engine |
| `psychTickToId` | 正規化tick | 512件超で全初期化 | 512 | 初期化（以後新ID） | Engine |
| `idxCat*` | カテゴリ | 登録／削除 | 生存Root数 | なし | Engine |
| `sLot*`（価格順） | なし（毎足再構築） | 毎足 | 生存点Root数 | `SCRATCH_MAX_ROOTS`超過で`scratchOverflow=true`（結果は正しいまま） | Engine |
| `cand*`（採用候補） | なし（毎足再構築） | 毎足 | 候補数 | なし | Engine |
| cfg validation | `cfgFingerprint` | 値変化時 | 1 | 再検証 | Engine |
| Feed重複排除 | 元足closeTime／originTime | 新しい元足 | 各1 | なし | Engine |

**足をまたぐ候補キャッシュは実装していません。** 同一足内の再利用を優先し、
「同値が確認できないものは再計算する」という指示に合わせています（No.9の残課題）。

### 6.2 計算量（変更前後）

既存v2コードが参照できないため「変更前」は**推定不可**です。本実装の計算量のみ記載します。

| 処理 | 計算量 | 隠れた線形処理 |
|---|---|---|
| 価格順構築 | `O(R log R)`（native sort）＋同値区間の局所整列 | sort_indices は毎足1本の新規配列を確保 |
| Dense/通常候補探索 | 開始位置ごとに窓内本数k → `O(R·k)`／ラウンド。ラウンド数 ≤ R/2 | `array.insert`（FVG付加）は`O(候補Root総数)` |
| 心理価格同期 | `O(R + P log P)`（P=心理Root数、存在判定は二分探索） | 生成・削除時に`liveOrder`へ二分挿入＋線形移動 |
| Core照合 | `O(候補数 × Core数)` の安価な範囲判定 ＋ 一致候補のみ起源突合 | `liveOrderRemove` は線形探索（削除時のみ） |
| 状態遷移 | `O(Core数)` | なし |
| 保存整理 | 上限超過時のみ `O(Root数)` × 削除件数 | 保護集合構築は整理1回につき1度 |

`liveOrder` の挿入は二分探索で位置を決めますが、**要素移動は線形**です（指示書M7.1の
注意どおり、全体が自動で `O(R log R)` になるとは主張しません）。

---

## 7. 検証状況

### 7.1 実施した静的検査（本環境で機械的に実行）

| 検査 | 結果 |
|---|---|
| 行継続インデントがPineの「4の倍数でない」規則を満たすか（括弧継続・演算子継続の全箇所） | PASS（違反0件） |
| `for x = n - 1 to 0` 等の降順ループに `n > 0` ガードがあるか | PASS（全5箇所） |
| 昇順ループの上限が空配列で負にならないか | PASS（4件は外側の`while`/`if`で保証） |
| 関数の前方参照（定義前呼び出し） | PASS（96関数、0件） |
| UDTフィールド名のtypo（全`obj.field`参照の突合） | PASS（0件） |
| 括弧・角括弧の対応 | PASS（複数行継続のみ） |
| 禁止ロジックの文字列検査（付録D） | 8.1参照 |

### 7.2 実行できていない検証

| 検証 | 状態 | 理由 |
|---|---|---|
| Pineコンパイル | **NOT RUN** | 本実行環境からTradingView Pine Editorへアクセスできない |
| 実チャート実行（XAUUSD 5分足） | **NOT RUN** | 同上 |
| Profiler・実行時間（40秒制限に対する0.5L=20秒目標） | **NOT RUN** | 同上 |
| Bar Replay・再ロード・リアルタイム足の一致 | **NOT RUN** | 同上 |
| 保存上限到達・超過テスト | **NOT RUN** | 同上 |
| 付録B 75ケース | **全件 NOT RUN** | Pine実機とBar Replayが必要 |

「この変更で確実にRE10110が消える」「最大限まで最適化済み」といった断定はしません。
現状は**実測ゼロ**です。

### 7.3 付録B 75ケースの実装対応（すべて NOT RUN／実装上の対応箇所）

| 群 | ケース | 実装対応 | 判定 |
|---|---|---|---|
| A 境界値 | 1-9 | tick正規化後の比較。等号は仕様どおり狭い側／Weak側／Touch側へ含む。FVG Distal同値は有効 | NOT RUN |
| B MA | 10-15 | `scanBest`のMA High条件（2本＋High Density＋対象方向同傾斜）。EMA移動では世代/Fresh/Touchを触らない | NOT RUN |
| C Swing/Accum/時間 | 16-25 | ConfirmedTime gate、同一イベント統合、Candidate非Root、終了足除外、pairKey排他、JST区切り、新極値足の自己タッチ防止（時間高安更新はタッチ評価後） | NOT RUN |
| D FVG | 26-36 | 方向filter、3本目確定gate、Fresh終了でもRoot存続、厳密不等号の無効化、BreakBuffer不使用、共通区間、非重複は非結合、50%不使用、Broad単独は非Strong | NOT RUN |
| E 心理/Strong | 37-45 | 心理単独不可、Major重複防止、CのみでH不可、Base Strong式、Dense core優先 | NOT RUN |
| F Touch/Weak | 46-53 | Zone内成立はWaiting、前足Armed gate、同一Episode、Snapshot Grade固定、Weak維持、一本線はDepth不使用 | NOT RUN |
| G Break/Flip | 54-65 | 終値1本、Break優先、GapBreakの非消費、同足Flip禁止、Reset前の再接触はFlip不成立、確認接触は非Touch、履歴復元、BreakSnapshot固定、FVG無効化優先 | NOT RUN |
| H Topology/世代 | 66-75 | Snapshot凍結、LiveStructure即時、Merge dedupe、Split未接触はFresh、未タッチは同世代、新カテゴリ必須、両Sideリセット、重複Feedガード、決定論的再現 | NOT RUN |

### 7.4 M15追加重点ケース

初期化0/1/2件、`na`初期Feed、同tick異価格、M/dense幅ちょうど、Accum上下限競合、
容量直前・超過、slot再利用、Merge後の後続照合、Reference凍結、Broad多重参加、
保存上限、週末/欠損、再ロード前後、表示切替、長期負荷 — **すべて NOT RUN**。
コード上の対応箇所は4章・6章の該当行を参照してください。

---

## 8. 付録D 静的確認

### 8.1 存在してはいけない判定依存（全文検索結果）

| 対象 | 結果 |
|---|---|
| Score閾値によるGrade / baseSum / bonus | **不在** |
| Reaction Bonus / Flip Bonus / 過去反発による昇格 | **不在** |
| 加重平均CenterによるTouch/Break | **不在**（Referenceは表示専用で判定に使わない） |
| FVG 50%によるRoot／局所化 | **不在**（Libraryに50%の計算なし。Harnessは表示のみ・Engineへ渡さない） |
| Zone幅・Break幅・Reset距離へのATR | **不在**（ATRは`accumCondV2()`の内部のみ） |
| BOS | **不在** |
| Strategyの勝敗 / TP / SL / 建値 | **不在** |
| 上位足環境フィルター | **不在** |
| `zoneHalfWidth` 等の中心±固定幅 | **不在** |
| 単一`state`でSupport/Resistance共用 | **不在**（Side別`SideHistory`） |

### 8.2 存在しなければならないもの

| 対象 | 実装 |
|---|---|
| 全価格比較前のtick正規化 | `toTick()`、幅・密集判定は整数tick |
| ConfirmedTime gate | 各ingest（Swing/Accum/FVG/時間高安） |
| 前足Armed gate | `armedFromSeq <= f.seq` |
| TouchStartSnapshot / BreakSnapshot | `startTouch()` / `applyBreak()`（`array.copy()`で凍結） |
| Side別履歴 / Weak永続化 | `SideHistory`、解除は`startGeneration()`のみ |
| FVG方向filter | `fvgSideEligible()` |
| PendingTopology | `ZoneCore.pendingTopology` |
| 新世代の新カテゴリ条件 | `updateGenerationCandidate()`（心理価格ビットを除外） |
| 決定論的tie-break | `scanBest()` の5段比較＋同値Root IDまで |
| duplicate base bar guard | `update()` 冒頭 |

---

## 9. 残る制約・リスク（実測前に明示）

1. **コンパイル未確認**。特に次はTradingView上での確認が必須です。
   - `request.security()` に渡すtupleの要素数（29 / 21）。分割が必要なら1H系を2コンテキストへ分ける代替案があります（統合数は報告値が変わります）。
   - Pineの **local scope上限**。本Libraryのブロックスコープは約323、関数104で**合計およそ430**です。
     公称上限（550前後）内の見込みですが、余裕は大きくありません。超過時は
     Source helper群を第2 Libraryへ分離するのが最小の対処で、**その場合は事前に相談します**。
   - `ta.ema(close, 3000)` を1分足コンテキストで使うため、ウォームアップに十分な
     1分足履歴が必要です（履歴不足時の挙動は実機確認が必要。**履歴短縮はしていません**）。
2. **Harnessの`import`行はプレースホルダ**です（`YOUR_TV_USERNAME/ZoneEngineV2_Rebuild/1`）。
   公開後の実番号に置き換えるまでコンパイルできません。番号は推測せず、
   公開時にbuild IDと一緒に記録してください。
3. **Denseラウンド間キャッシュ未実装**（M16 No.9）。同値保証を優先しました。
   残る負荷はラウンド数×`O(R·k)`です。
4. **Dormantは状態評価のみ休止**し、候補生成には参加します（履歴のあるZoneが
   遠方でも正しく再開できることを優先）。表示・状態遷移の負荷は下がりますが、
   探索の負荷は下がりません。
5. **Merge時のSideTouchCount**は、TouchMark履歴が上限で切り捨てられている場合に限り
   `max()` を使い、`touchHistoryTruncated=true` を立てます（推測でFreshへ戻しません）。
6. **Splitの子Core**には新しいGeneration IDを割り当てます（仕様に明記がないため実装決定）。
7. 2章の相談3件が未確定です。

---

## 10. TradingViewでの実行手順（ユーザー操作が必要な部分）

1. Pine Editorで `ZoneEngineV2_Rebuild.pine` を開き、**Add to chart** でコンパイルを確認。
   - エラーが出た場合は、行番号とメッセージをそのまま共有してください。
2. **Publish script → Publish library** でLibraryを公開し、発行された
   `<username>/ZoneEngineV2_Rebuild/<version>` を控える。
3. `ZoneEngineV2_Rebuild_VisualHarness.pine` の `import` 行をその実番号へ置き換える。
4. **XAUUSD の5分足**チャートへHarnessを追加する（他の時間足ではDebug表に警告が出ます）。
5. Debug表で次を確認：`build` / `cfg` / `last base` / `roots` / `cores / views` /
   `candidates` / `window evals` / `prune` / `bar events` / `chart tf`。
   - Zoneが0件でも、`roots` と `candidates` と `last base` が更新されていれば
     「処理完了かつ候補0件」です。処理が途中停止した状態とは区別できます。
6. 実行時間計測：まず通常実行の完走可否、次に Profiler を**別実行として**確認
   （Profilerの負荷は非計測時の処理時間と同一視しません）。
7. 計測時に記録する項目：ticker ID、チャート時間足とセッション、履歴開始/終了と本数、
   全パラメータ、Library公開番号、build ID、TradingViewの表示する実行制限。
8. 付録B 75ケースは Bar Replay とDebug表で1件ずつ確認し、PASS/FAIL/NOT RUNを本書7.3へ追記。

---

## 11. 論理変更の有無

**本実装でZone定義v2の論理は変更していません。** 仕様の解釈が一意に定まらない箇所は
2章に3件として明示し、実装上の既定値と差し替え手順を示しました。「なし」で片付けていません。
