# ZoneEngineV2_Rebuild 実装レポート

作成日：2026-09-19（改訂2：更新版指示書 付録A 7.4 / M19 反映）
Build ID：`ZEV2R-20260919-002`
対象：XAUUSD / 確定5分足 / Pine Script v6

---

## 0. 現在の状態

| 項目 | 状態 |
|---|---|
| Zone定義v2の論理変更 | **なし** |
| Accum形成条件式 | **正本（付録A 7.4）へ一致させた**。仮置きは解消 |
| Candidate→Confirmed遷移 | 付録A 7.4の確定後ルールを使用。旧Engineの状態管理・固定幅は不使用 |
| Inverse FVGの評価時間足 | M19.3の契約と**実装が既に一致**していることを確認 |
| Broad FVGのProximal局所化 | 実装範囲を6点すべて明示（2.2）。**追加分岐1点の承認待ち** |
| Library / Visual Harness / Report | 3ファイル更新済み |
| **仕様適合性・実行時間・実機動作** | **未検証**（コンパイル・Profiler・75ケースはすべて `NOT RUN`） |

本書の記述は「仕様遵守を意図した実装であり、適合性は未検証」です。
行数・export数・静的検索の結果は、仕様適合や完走の証拠として扱っていません。

---

## 1. 成果物と基準資料

| ファイル | 内容 |
|---|---|
| `ZoneEngineV2_Rebuild.pine` | Pine v6 Library |
| `ZoneEngineV2_Rebuild_VisualHarness.pine` | indicator。Libraryを1本importし、Engineを1インスタンスだけ動かす |
| `ZoneEngineV2_Rebuild_Report.md` | 本書 |

### 1.1 基準とした資料

| 資料 | 扱い |
|---|---|
| `Zone_definition_spec_v2.md` | Zone論理の正本 |
| `Claude_ZoneEngine_v2_lightweight_implementation_instructions`（更新版） | 付録A〜D（論理契約・初期値・受入条件）とM章 |

**この2文書だけを基準に新規実装しています。** 旧Engine／Harnessのソースは読み込んでおらず、
出力の完全一致も前提にしていません。旧実装の不具合・暫定上限・最適化パッチは持ち込んでいません。

追加で確認した条件：更新版 付録A 7.4（Accum形成条件式とCandidate→Confirmed）、
M19.1〜M19.5。本書2章がその反映内容です。

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
codeSideSupport() ... codeCatCount()
categorySummary() / viewLabelText() / maSlopeText()
```

`ZoneView` はSide別の読み出し専用Projectionで、`rootIds` は `array.copy()` で渡します。
Viewは該当Zoneを**すべて**返し、距離やStrengthでEngine側が絞ることはしません。

---

## 2. 更新版指示書への対応

### 2.1 Accum形成条件式（M19.1）— 解消

`accumCondV2()` を付録A 7.4の式へ一致させました。中間値名・比較演算子・初期化・
ループの向きまで写しています。

| 項目 | 改訂1（仮置き・破棄） | 改訂2（正本一致） |
|---|---|---|
| レンジHigh/Low | `ta.highest(high,N)` / `ta.lowest(low,N)`（ヒゲ） | `ta.highest(bodyTop,N)` / `ta.lowest(bodyBot,N)`（実体端） |
| 基準幅 | ヒゲベース | `ta.highest(bodyTop,B) - ta.lowest(bodyBot,B)` |
| `rangeMid` | ヒゲレンジの中点 | `(rangeHigh + rangeLow) * 0.5`（実体レンジ、全N本へ同じ値を適用） |
| 上下半分 | `close > mid` / `close < mid` | 同じ（`rangeMid`同値はどちらにも加算しない） |
| ドリフト | `abs(close - close[N]) / rangeNow` | `abs(endMid - startMid) / rangeNow`、`endMid=(open+close)*0.5`、`startMid=(open[N-1]+close[N-1])*0.5` |
| 同色連続 | 方向共通の単一カウンタ | `maxBullRun` と `maxBearRun` を別々に数え、Dojiは両方を切る。両方が上限以内 |
| ATR条件 | `na`ガード＋`sRange>0`の共通ゲート | `condAtr = atrValue > 0 and rangeNow <= atrValue * accumAtrMult` |
| 基準幅条件 | 共通ゲートに依存 | `condBar = rangeBase > 0 and rangeNow <= rangeBase * accumBarRatioMax` |
| ドリフト条件 | 共通ゲートに依存 | `condDrift = rangeNow > 0 and drift / rangeNow <= accumDriftMax` |
| 反復方向 | `i = N-1 → 0` | `i = 0 → N-1`（正本どおり） |

一致させた点（付録A 7.4の箇条書きへの対応）：

- レンジHigh/Lowは実体端。ヒゲへ置き換えていない。
- `condBar`は実体レンジ幅どうしの比率。平均値幅・平均実体長は使っていない。
- 上下半分は判定窓で求めた同一 `rangeMid` を全N本へ適用（各足の移動中点ではない）。
- 終値が `rangeMid` と同値なら上下どちらにも加算しない。
- Doji（`open == close`）は `bullRun` と `bearRun` の両方を0へ戻す。
- ドリフトは窓の最古足と最新足の**実体中点差**を `rangeNow` で割る。
- 中間値に丸め・tick正規化を一切かけていない（tick正規化はZone側の比較専用）。
- ATRは `ta.atr()` の値をそのまま使用。
- ATR無効・基準幅0・判定幅0では、その必須条件が成立しない（`na`を0で補完しない）。
- `ta.highest` / `ta.lowest` / `ta.atr` の履歴初期化はPine標準のまま。独自ウォームアップ制限は追加していない。

`accumCondV2()` は `[isAccum, rangeHigh, rangeLow]` を返し、Candidate開始時の初期範囲は
**同じ `rangeHigh` / `rangeLow`** を使います（窓の再計算をせず、中間値の同一性も保証）。
「中点更新で過去N本の所属が変わるため、単純な追加・除去カウンタで代替しない」という指示に従い、
窓内カウントは毎回その窓の `rangeMid` で数え直しています。

Candidate→Confirmedは付録A 7.4の6ステップのみを実装しています。

1. false→true でCandidate開始（`candStart = time`）。
2. 初期範囲＝`rangeHigh` / `rangeLow`。
3. true継続中は当該確定足の実体（`bodyTop` / `bodyBot`）で範囲更新。
4. true→false で直前までの範囲を**一度だけ**Confirmed Boxとして出力。
5. false になった終了足は範囲へ含めない。
6. 出力後にCandidate状態をリセット。

`boxId` と `confirmedTime` の両方で重複登録を防いでいます。ATRは `accumCondV2()` の内部のみで、
確定後のRoot／Zone／Box境界へ持ち出していません。固定幅の付加もありません。

> 注記：`boxId` は `candStart` と境界価格から作る安定ハッシュで、ハッシュ生成時のみ整数化しています。
> `boxTop` / `boxBottom` は丸めずそのまま出力します（形成式の中間値にも影響しません）。

### 2.2 Broad FVGのProximal局所化（M19.2）— 適用範囲の明示・承認待ち

該当コードは `attachFvg()` の以下の分岐です。

```pine
bool inside = intersects(cb, ct, r.nativeBottom, r.nativeTop)
bool proximalAnchored = false
float nb = cb
float nt = ct
if not inside
    float gap = side == 1 ? cb - prox : prox - ct
    if gap > 0.0 and array.get(e.candDensity, k) == 0
        float tb = side == 1 ? prox : cb
        float tt = side == 1 ? ct : prox
        int wT = toTick(tt, cfg.mintick) - toTick(tb, cfg.mintick)
        int limitT = array.get(e.candStrong, k) == 1 ? denseTickLimit(cfg) : mTickLimit(cfg)
        if wT <= limitT
            proximalAnchored := true
            nb := tb
            nt := tt
```

6つの確認事項への回答：

| 確認事項 | 実装 |
|---|---|
| 保護対象は既存Dense Base Strong coreか、全候補か | **Base Strong候補のみ**（`candStrong == 1`）。それ以外は通常のM上限。改訂1では全High Density候補へdense幅を課していたため、指摘どおり修正しました |
| FVG内部の点Root局所化とProximal外側を区別しているか | **区別している**。`inside`（NativeRangeと候補範囲が交差）では範囲を**変更しない**（FVG全幅を足さない）。`proximalAnchored` のときだけ範囲を拡張 |
| Proximal外側でEffectiveRangeが「実Proximal edge〜局所Root分布」になっているか | Support側は `[prox, candTop]`、Resistance側は `[candBottom, prox]`。`prox` は接近側の実Proximal edge（Support=NativeTop、Resistance=NativeBottom） |
| 付加でdense幅を超える場合、元のDense Strongを維持しFVG Root／Broad contextを失わないか | 付加を見送るだけで、候補（Dense Strong）はそのまま。FVG Rootは`consumed`にならないため、他候補への付加、または段階BのFVG単独／重複候補（Broadは`DEN_BROAD_CONTEXT`）として必ず出力されます |
| Normal候補・FVG単独・FVG重複へ一律「dense幅以内のみ」を足していないか | **足していない**。`inside` 付加に幅条件なし。FVG単独／重複の範囲はNativeRange／共通区間のみで決まり、dense幅条件は入りません |
| 方向・4つのBroad局所化条件・競合順・二重参加禁止を維持しているか | 方向は `fvgSideEligible()`（Bullish=Support、Bearish=Resistance、Inverse確定後は反対側、無効化中はどちらも不可）。Broadは `broadLocalizeOk()` が仕様3.5の4条件（Proximal周辺の高密集／同方向別TFの実重複／内部の高品質別カテゴリ／内部のFVG以外独立カテゴリ2つ以上の高密集）のいずれか。候補の走査順は採用順（Dense→通常）で不変。非Broad FVGは1候補で`consumed`、Broadのみ複数局所Zoneへ参加可、通常Rootは`sUsed`で二重参加禁止 |

指示書の例に対する動作：

- M=20、dense幅=10、Dense Strong範囲 `[100,106]`、Proximal=95 → 拡張後 `[95,106]` は幅11。
  `candStrong==1` なので上限はdense幅10 → **付加しない**。`[100,106]` はDense Strongのまま、
  FVGは他候補または単独／Broad contextとして残ります。
- 同条件でProximal=96 → 拡張後 `[96,106]` は幅10で幅条件は満たしますが、それだけでは付加しません。
  併せて、方向適格（`fvgSideEligible`）、`gap > 0`、候補がHigh Density、
  Broadなら `broadLocalizeOk()` の4条件のいずれか、非Broadなら4H/日足または異TF重複でH、
  `consumed` 状態（非Broadは1候補のみ）を確認しています。

**承認待ちの追加分岐は1点だけです**：`limitT` の `candStrong == 1` 分岐
（既存Dense Base Strongをdense幅超へ広げない）。M19.2で仕様5.2と整合と示していただいた条件ですが、
「現時点で追加の局所化ルールは承認していません」との記載に従い、明示的な承認をお願いします。
不要であれば `limitT` を常に `mTickLimit(cfg)` にするだけで外せます（受入45の結果が変わります）。

### 2.3 Inverse FVGの評価時間足（M19.3）— 確認済み、変更不要

実装は既に契約どおりでした。

| 手順 | 実装 | 箇所 |
|---|---|---|
| 元FVGの構造無効化 | **元時間足の確定Close**（`fp.srcClose` と `srcCloseTime <= baseCloseTime`） | `markFvgInvalidation()` / `applyFvgState()` |
| 距離離脱（movedAway） | 確定5分足Close | `updateFvgInverse()` |
| NativeRangeへの再接触 | 確定5分足High/Lowの交差 | `updateFvgInverse()`（`intersects(f.l, f.h, …)`） |
| 新役割側への終値回復 | 確定5分足Close | `updateFvgInverse()` |
| InverseConfirm接触 | 通常Touchへ加算しない（TouchMarkも作らない） | `updateFvgInverse()` |
| 5分足内の順序推測 | していない。1本の確定足では「距離離脱」か「再接触＋回復」のどちらか一方しか進めない | `updateFvgInverse()` |

### 2.4 Pine制約に関する報告の訂正（M19.4）

- **local scope上限のリスク記載を撤回します。** 2025年2月のリリースでscope数上限は撤廃されており、
  現行v6のリスクとして報告すべきものではありませんでした。本書から削除しています。
- tuple要素数：実ソースの `request.security` を数えた結果は**5コンテキスト**で、
  5（1m）＋8（15m）＋29（1H）＋21（4H）＋21（1D）＝**84要素**。
  上限127要素の範囲内です。別分岐・条件付きの追加requestはありません
  （Library内に `request.*` の呼び出しは0件。5分足Swingはチャート直接計算）。
  これはコンパイル済みという判断ではありません。

### 2.5 探索上限について（M1.3）

正本にない探索打切りや暫定上限は追加していません。

- Dense／通常候補探索に回数上限はありません。各ラウンドが最低1本のRootを消費するため停止します。
- 改訂1で保存整理のwhileに入れていた安全カウンタ（512／256）は、
  「上限の追加」と受け取られ得るため**削除しました**。
  どちらのループも「削除対象なしでbreak」または「1件削除」で必ず進むため、停止は保証されます。
- `SCRATCH_MAX_ROOTS` は診断フラグ（`scratchOverflow`）を立てるだけで、探索・候補を打ち切りません。
- 未使用だった `MAX_PSYCH_ROOTS` は、上限と誤解されないよう削除しました。
  心理価格の合成範囲は仕様3.6／7.7の「現在価格周辺に限定できる」に基づき
  `dormantDistance` 以内の非心理Root周辺のみです（Zone判定に使う範囲を削ってはいません）。

---

## 3. 採用した計算構造と設計理由

| 層 | 保持するもの | 更新契機 |
|---|---|---|
| Source/Feed | 元足の確定値、検出イベント、採用時刻 | 各元足の確定。Library内では`request.*`を呼ばない |
| Root registry | 起源・価格・NativeRange・参加資格・カテゴリ | 対象Rootの実変更のみ |
| Candidate evaluator | Side別候補、範囲、C/H、Density、比較情報 | 入力変化時 |
| Core association | 同一性・Merge・Split・PendingTopology・世代 | 関連Candidate/Coreの変化 |
| State transition | Touch/Weak/Break/Flip/Reclaim/Inverse | 確定5分足すべて |
| Read API | View・当該足Event | 利用側の読み出し |
| Presentation | 選択・文字列・box/line/label/table | Harness側のみ |

設計理由つきの主要構造：

1. **Root IDと保存slotの分離**（`idToSlot` / `liveOrder` / `freeSlots`）。
   削除のたびに全Rootをずらす方式を避け、走査順はRoot ID昇順で固定して決定性を保つため。
2. **カテゴリ別索引**（`idxMa/idxSwing/idxAccum/idxTime/idxFvg/idxPsych`）。
   FVG Fresh・構造無効化・時間高安・整理を対象カテゴリだけで回すため。
3. **起源キー索引**（`originToId`）。Swing/Accum/FVGの重複イベント登録を検索なしで防ぐため。
4. **価格順は毎足1回のnative sort＋同値区間のみ局所整列**。
   `array.sort_indices` の同値順序に依存せず、Root IDまでtie-breakして毎足同じ順序にするため。
5. **候補探索は数値のみ**。落選候補でオブジェクト・文字列・中央値を作らず、採用時のみ実データ化。
6. **Reference Priceは採用構造に対して1回計算し保持**。
   ActiveTouch中にRootが移動・削除されても当時の値を保つため（遅延再構築を禁止）。
7. **dirtyフラグの用途別分離**（RootSet／RootPrice／Quality／FvgState／Core）。
   単一フラグでEngine全体を止めないため。
8. **scratchはEngine所有で再利用**し、Snapshotのみ `array.copy()` で独立所有。

### 3.1 単純計算からの削減

| 処理 | 素直に計算した場合 | 本実装 |
|---|---|---|
| 候補窓のC/H | 窓ごとに窓内Rootを引き直す（窓数 × k） | 開始位置ごとに終端を伸ばしながらカテゴリ・品質要約を増分更新（各Rootは開始位置あたり1回） |
| 価格順 | 毎足すべてを比較ソート | native sort 1回＋同値区間のみ挿入整列 |
| Root検索 | 全件線形探索 | ID→slot、起源→ID、カテゴリ→slot集合 |
| FVG判定 | 全FVG × 全候補の品質判定 | 交差／Proximal距離の安価な幾何条件で足切り後に品質判定 |
| Core照合 | 全Core × 全Candidate | 範囲gapの安価な判定→一致し得る組のみ起源集合を突合 |
| Reference | 全候補で中央値計算 | 採用候補のみ1回 |
| 元足取得 | カテゴリ・時間足ごとに個別request | 同一コンテキストを1 tupleへ統合（5コンテキスト） |

---

## 4. 仕様書・付録Aへの実装対応表

| 仕様 | 実装箇所 |
|---|---|
| 1.1-1.4 Root / Category / ZoneCore / Side View | `type Root` / `type ZoneCore` / `type SideViewState` |
| 1.5-1.6 NativeRange と EffectiveZoneRange | `Root.nativeBottom/nativeTop` と `SideViewState.effectiveBottom/Top`。判定は常にEffective |
| 1.7-1.8 構造品質と消耗状態の分離 | `cCount/hCount/density/baseStrong` と `SideHistory` |
| 1.9 Phase / Grade | `finalizeSide()` / `gradeOf()` |
| 1.10 Zone generation | `startGeneration()` / `genBaselineCatMask` |
| 2 独立カテゴリ6 | `CAT_*` と `popCount6(catMask)` |
| 3.1 MA | `ingestMa()`。固定ID、現在値のみ、傾きは確定5分足で更新、High条件は`scanBest()` |
| 3.2 Swing | `pivotPackV2()`（3時刻分離）、`swingIngestOne()`（同一イベント統合＋TF mask保持） |
| 3.3 Accum | `accumCondV2()`（付録A 7.4の式）＋ `accumPackV2()`（6ステップの状態機械）、上下限は`pairKey`で排他 |
| 3.4 時間区切り高安 | `updateTimeHL()` / `timeLabelSet/Drop/Move` |
| 3.5 HTF FVG | `fvgPackV2()` / `applyFvgState()` / `updateFvgInverse()` / `attachFvg()` |
| 3.6 心理価格 | `syncPsych()` |
| 4.1-4.3 Side View / 役割 | `fvgSideEligible()` / `applyCandidate()` / 1 ZoneCoreに2 View |
| 5.1 Mと密集度 | `denseTickLimit()/mTickLimit()`、Effective全幅、等号は狭い側、数珠つなぎ禁止 |
| 5.2 Dense core優先 | `buildCandidates()`：Base Strongのdenseラウンド→残Rootで通常候補 |
| 5.3 クラスタ競合 | `scanBest()` の比較関数（C↓ H↓ 幅↑ 成立時刻↑ 最小RootID↑）1か所のみ |
| 5.4-5.5 範囲 | 点Root＝実価格のmin〜max。FVGは2.2の局所化規則 |
| 5.6 ZoneReferencePrice | `computeRefPrice()`。重み付けなし、FVG 50%不使用 |
| 5.7 複数Zoneの重なり | `associateCandidates()`。Broad共有だけでは結合しない |
| 6.1 品質集約 | `scanBest()` のhMask（1カテゴリH最大1） |
| 6.2 Base Strong | `C==2 && High && H>=1` / `C>=3 && High` |
| 6.3 点数制の排除 | score/bonus/合計加点は不在（8章） |
| 7.1-7.4 Phase / Grade / 確定前禁止 / Armed | `finalizeSide()` / `gradeOf()` / 各ingestのConfirmedTime gate / `armedFromSeq = seq + 1` |
| 8.1-8.4 タッチEpisode | `armedEval()` / `startTouch()` / `activeEval()` |
| 9.1-9.3 Strong期限 / WeakDepth / Weak維持 | `gradeOf()` / `activeEval()` / `startGeneration()`以外で解除しない |
| 10.1-10.2 Break / GapBreak | `activeEval()`→`applyBreak()` / `armedEval()` |
| 10.3-10.5 Flip / Attempt / Reclaim | `processBreakState()`（基準は必ず`BreakSnapshot`） |
| 10.6 Inverse FVG | `updateFvgInverse()`（2.3の時間足契約） |
| 11.1-11.4 Snapshot / LiveStructure / Pending | `TouchStartSnapshot` / `sideHasLiveNonPsych()` / `pendingTopology` |
| 12.1-12.3 同一性 / Merge / Split | `candSharesOrigin()`＋`intervalGap<=M` / `mergeCores()` / `splitCore()` |
| 13 新Zone世代 | `updateGenerationCandidate()` ＋ `startTouch()` 冒頭の切替 |
| 14 Zoneの有効期間 | `associateCandidates()` 末尾 |
| 15 同一5分足内の処理順 | `update()` のA→J（5章） |
| 16 Fresh 3種 | `zoneFresh` / `sideFresh` / `fvgFresh` |
| 17 出力 | `ZoneView` / `ZoneEvent` |
| 18 初期パラメータ | `ZoneCfg` 既定値。判定式に数値直書きなし |
| 19 Zone定義へ入れないもの | 環境認識・TP/SL・BOS・他銘柄・エントリー足FVGは不在 |

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

---

## 6. M16 監査表（24項目）

| No. | 対象 | 実施内容 | 効果 | 計測 |
|---:|---|---|---|---|
| 1 | 全確定足の更新契約、重複Feed排除 | `baseOpenTime` 単調増加ガード、`seq`はEngine採番 | 二重更新なし | NOT RUN |
| 2 | Source helperの式の重複・初期化 | 形成式は付録A 7.4のまま。`rangeHigh/rangeLow`をCandidate初期範囲へ再利用し窓を二重計算しない | 元足あたりの重複計算を排除 | NOT RUN |
| 3 | request統合・Feed採用時刻 | 1m/15m/1H/4H/1D の5コンテキスト、計84 tuple要素。5mはチャート直接計算 | 外部request 5系統 | 数は実ソースで確認、負荷はNOT RUN |
| 4 | Root ID／起源／カテゴリ／TF索引 | `idToSlot` `originToId` `idxCat*` `psychTickToId` | 全件走査の除去 | NOT RUN |
| 5 | 削除・slot再利用・索引更新 | slot再利用＋ID昇順`liveOrder`＋`freeSlots` | 全要素ずらしの回避 | 実測比較は NOT RUN |
| 6 | 固定Rootと移動Rootの価格順 | native sort 1回＋同値区間のみ局所整列 | `O(R log R)`＋小さな定数 | NOT RUN |
| 7 | Support/Resistance共通読み出し | 価格・tick・起源は共有、FVG資格/MA品質/使用済み/Side履歴は分離 | 重複計算の削減 | NOT RUN |
| 8 | Dense初回探索の窓境界と増分品質 | 開始位置ごとにtick幅で終端打ち切り、窓内カテゴリ・High入力を増分更新。全部分窓を比較 | `O(R·k)` | NOT RUN |
| 9 | Denseラウンド間の再利用 | **未実装**。各ラウンドを完全再計算（同値保証を優先） | 効果なし（残る負荷として記載） | NOT RUN |
| 10 | 通常候補生成とRoot使用済み管理 | `sUsed` で使用済みを除外。Broad FVGのみ共有可 | 二重参加なし | NOT RUN |
| 11 | FVG Fresh/無効化/Inverse対象集合 | `idxFvg` をTFで絞り、Fresh終了済みはFresh判定をしない | 対象限定 | NOT RUN |
| 12 | FVG付加・重複・standalone | 幾何条件で足切り後に品質判定（2.2） | 高価な判定の回数削減 | NOT RUN |
| 13 | C/H/Density/identityの再計算 | 付加時は `candRefresh()` で差分再評価 | 全再計算の回避 | NOT RUN |
| 14 | Referenceの計算と保存 | 採用候補のみ1回計算し保持 | 落選候補の中央値計算をゼロに | NOT RUN |
| 15 | Support/Resistance候補のCore統合 | 同一非FVG起源＋M以内で1 Coreの2 View | 二重生成なし | NOT RUN |
| 16 | Core×Candidate照合、Pass間失効 | 範囲gapの事前判定→起源突合。Merge後は更新済みCoreで後続判定 | 全組合せの重い照合を回避 | NOT RUN |
| 17 | Merge/Split/TouchMark割当 | 実接触範囲の交差で子へ割当、同時刻・同Sideはdedupe | 集計値代替をしない | NOT RUN |
| 18 | ActiveTouch/Snapshot/Pending/世代 | 形状変更はPendingTopology、資格喪失のみ即時 | 仕様どおり | NOT RUN |
| 19 | Dormant復帰・prune・保護 | 保護集合を整理1回につき1度だけ構築 | 削除ごとの再構築を回避 | NOT RUN |
| 20 | scratch/pool/deep copyの境界 | Engine所有scratchを再利用。Snapshot/Viewは`array.copy()` | 候補評価内の`array.new`を排除 | NOT RUN |
| 21 | map/cacheの寿命・容量超過 | 索引サイズは生存Rootに連動。`psychTickToId`のみ安定ID用に永続（512超で再初期化） | mapの無制限増加を防止 | NOT RUN |
| 22 | View/Event APIと文字列の分離 | 数値Viewと`viewLabelText()`を分離。Event文字列は蓄積しない | 表示OFFでも論理不変 | NOT RUN |
| 23 | 描画再利用・Debug・rollback | box/line/labelを起動時生成しsetterで更新。`varip`の描画済みフラグ不使用 | 再描画コスト削減 | NOT RUN |
| 24 | Pineコンパイル・実機・長期性能・公開版整合 | **未実施** | - | NOT RUN |

### 6.1 キャッシュ一覧（キー／失効／容量／fallback／所有）

| 対象 | キー | 失効条件 | 容量 | 容量超過時 | 所有 |
|---|---|---|---|---|---|
| `idToSlot` | Root ID | 登録／削除 | 生存Root数 | なし | Engine |
| `originToId` | 起源キー | 登録／削除 | 生存Root数 | なし | Engine |
| `psychTickToId` | 正規化tick | 512件超で全初期化 | 512 | 初期化（以後新ID） | Engine |
| `idxCat*` | カテゴリ | 登録／削除 | 生存Root数 | なし | Engine |
| `sLot*`（価格順） | なし（毎足再構築） | 毎足 | 生存点Root数 | `SCRATCH_MAX_ROOTS`超過で`scratchOverflow=true`（結果は正しいまま、打切りなし） | Engine |
| `cand*`（採用候補） | なし（毎足再構築） | 毎足 | 候補数 | なし | Engine |
| cfg validation | `cfgFingerprint` | 値変化時 | 1 | 再検証 | Engine |
| Feed重複排除 | 元足closeTime／originTime | 新しい元足 | 各1 | なし | Engine |

足をまたぐ候補キャッシュは実装していません（同値が確認できないものは再計算する方針）。

### 6.2 計算量

| 処理 | 計算量 | 隠れた線形処理 |
|---|---|---|
| 価格順構築 | `O(R log R)`＋同値区間の局所整列 | `sort_indices` が毎足1本の新規配列を確保 |
| Dense/通常候補探索 | 開始位置ごとに窓内本数k → `O(R·k)`／ラウンド。ラウンド数 ≤ R/2 | FVG付加の`array.insert`は`O(候補Root総数)` |
| 心理価格同期 | `O(R + P log P)` | 生成・削除時の`liveOrder`への挿入は線形移動 |
| Core照合 | `O(候補数 × Core数)` の安価な範囲判定＋一致候補のみ起源突合 | `liveOrderRemove` は線形探索（削除時のみ） |
| 状態遷移 | `O(Core数)` | なし |
| 保存整理 | 上限超過時のみ `O(Root数)` × 削除件数 | 保護集合構築は整理1回につき1度 |

`liveOrder` の挿入位置は二分探索ですが、**要素移動は線形**です。

---

## 7. 検証状況

### 7.1 実施した静的検査（本環境で機械実行）

これらは**構文・構造の検査であり、仕様適合の証拠ではありません**。

| 検査 | 結果 |
|---|---|
| 行継続インデントがPineの規則（4の倍数でない）を満たすか | 違反0件 |
| 降順ループ（`n-1 to 0`）のゼロ件ガード | 違反0件 |
| 昇順ループ上限が空配列で負にならないか | 外側の`while`/`if`で保証 |
| 関数の前方参照 | 0件 |
| UDTフィールド名の突合 | 0件 |
| Library内の`request.*`呼び出し | 0件（コメント記述のみ） |
| Harnessの`request.security`数と tuple要素数 | 5件 / 84要素（上限127以内） |
| 禁止ロジックの全文検索（付録D） | 8章 |

### 7.2 未実施

| 検証 | 状態 | 理由 |
|---|---|---|
| Pineコンパイル | **NOT RUN** | 本実行環境からPine Editorへアクセスできない |
| 実チャート実行（XAUUSD 5分足） | **NOT RUN** | 同上 |
| Profiler・実行時間（40秒制限に対する0.5L=20秒目標） | **NOT RUN** | 同上 |
| 再現性確認（再ロード／Bar Replay／リアルタイム足で確定結果が一致） | **NOT RUN** | 同上 |
| 保存上限の到達・超過テスト | **NOT RUN** | 同上 |
| 付録B 75ケース | **全件 NOT RUN** | Pine実機とBar Replayが必要 |
| M15追加重点ケース（初期化／比較境界／Dense／Cache／Mutation／Reference／FVG／保存／Feed／表示／長期負荷） | **全件 NOT RUN** | 同上 |

「この変更で確実にRE10110が消える」「最大限まで最適化済み」といった断定はしません。実測はゼロです。

### 7.3 付録B 75ケースの実装対応（判定はすべて NOT RUN）

| 群 | ケース | 実装対応 | 判定 |
|---|---|---|---|
| A 境界値 | 1-9 | tick正規化後の比較。等号は狭い側／Weak側／Touch側へ含む。FVG Distal同値は有効 | NOT RUN |
| B MA | 10-15 | `scanBest`のMA High条件（2本＋High Density＋対象方向同傾斜）。EMA移動で世代/Fresh/Touchを触らない | NOT RUN |
| C Swing/Accum/時間 | 16-25 | ConfirmedTime gate、同一イベント統合、Candidate非Root、終了足除外、`pairKey`排他、JST区切り、新極値足の自己タッチ防止 | NOT RUN |
| D FVG | 26-36 | 方向filter、3本目確定gate、Fresh終了でもRoot存続、厳密不等号の無効化、BreakBuffer不使用、共通区間、非重複は非結合、50%不使用、Broad単独は非Strong | NOT RUN |
| E 心理/Strong | 37-45 | 心理単独不可、Major重複防止、CのみでH不可、Base Strong式、Dense core優先（45は2.2の保護分岐が該当） | NOT RUN |
| F Touch/Weak | 46-53 | Zone内成立はWaiting、前足Armed gate、同一Episode、Snapshot Grade固定、Weak維持、一本線はDepth不使用 | NOT RUN |
| G Break/Flip | 54-65 | 終値1本、Break優先、GapBreakの非消費、同足Flip禁止、Reset前の再接触はFlip不成立、確認接触は非Touch、履歴復元、BreakSnapshot固定、FVG無効化優先 | NOT RUN |
| H Topology/世代 | 66-75 | Snapshot凍結、LiveStructure即時、Merge dedupe、Split未接触はFresh、未タッチは同世代、新カテゴリ必須、両Sideリセット、重複Feedガード、決定論的再現 | NOT RUN |

---

## 8. 付録D 静的確認

### 8.1 存在してはいけない判定依存

| 対象 | 結果 |
|---|---|
| Score閾値によるGrade / baseSum / bonus | 不在 |
| Reaction Bonus / Flip Bonus / 過去反発による昇格 | 不在 |
| 加重平均CenterによるTouch/Break | 不在（Referenceは表示専用） |
| FVG 50%によるRoot／局所化 | 不在（Libraryに50%計算なし。Harnessは表示のみでEngineへ渡さない） |
| Zone幅・Break幅・Reset距離へのATR | 不在（ATRは`accumCondV2()`の内部のみ） |
| BOS | 不在 |
| Strategyの勝敗 / TP / SL / 建値 | 不在 |
| 上位足環境フィルター | 不在 |
| `zoneHalfWidth` 等の中心±固定幅 | 不在 |
| 単一`state`でSupport/Resistance共用 | 不在（Side別`SideHistory`） |

### 8.2 存在しなければならないもの

| 対象 | 実装 |
|---|---|
| 全価格比較前のtick正規化 | `toTick()`。幅・密集判定は整数tick（Accum形成式の中間値には適用しない） |
| ConfirmedTime gate | 各ingest |
| 前足Armed gate | `armedFromSeq <= f.seq` |
| TouchStartSnapshot / BreakSnapshot | `startTouch()` / `applyBreak()`（`array.copy()`で凍結） |
| Side別履歴 / Weak永続化 | `SideHistory`、解除は`startGeneration()`のみ |
| FVG方向filter | `fvgSideEligible()` |
| PendingTopology | `ZoneCore.pendingTopology` |
| 新世代の新カテゴリ条件 | `updateGenerationCandidate()`（心理価格ビットを除外） |
| 決定論的tie-break | `scanBest()` の5段比較＋Root IDまで |
| duplicate base bar guard | `update()` 冒頭 |

---

## 9. 残る制約・未確認事項

1. **コンパイル未確認。** 実機で最初に確認すべき点：
   - `request.security()` のtuple（29要素の1H系）が実際に通ること。合計84要素は上限127以内です。
   - `ta.ema(close, 3000)` を1分足コンテキストで使うため、十分な1分足履歴が必要
     （履歴短縮はしていません）。
   - `ta.highest(bodyTop, N)` のように関数内で作った系列へ `ta.*` を適用している箇所の挙動。
2. **Harnessの`import`行はプレースホルダ**（`YOUR_TV_USERNAME/ZoneEngineV2_Rebuild/1`）。
   公開後の実番号に置き換えるまでコンパイルできません。番号は推測せず、公開時にbuild IDと記録してください。
3. **Denseラウンド間キャッシュ未実装**（M16 No.9）。同値保証を優先しました。
4. **Dormantは状態評価のみ休止**し、候補生成には参加します（遠方Zoneの履歴を正しく再開するため）。
   探索負荷は下がりません。
5. **Merge時のSideTouchCount**は、TouchMark履歴が上限で切り捨てられている場合に限り `max()` を使い、
   `touchHistoryTruncated=true` を立てます（推測でFreshへ戻しません）。
6. **Splitの子Core**には新しいGeneration IDを割り当てます（仕様に明記がないため実装決定）。
7. **2.2の `candStrong` 分岐が承認待ち**です。

---

## 10. TradingViewでの実行手順

1. Pine Editorで `ZoneEngineV2_Rebuild.pine` を開き、**Add to chart** でコンパイル確認。
   エラー時は行番号とメッセージをそのまま共有してください。
2. **Publish library** で公開し、発行された `<username>/ZoneEngineV2_Rebuild/<version>` を控える。
3. Harnessの `import` 行をその実番号へ置き換える。
4. **XAUUSD の5分足**チャートへHarnessを追加（他TFではDebug表に警告が出ます）。
5. Debug表で確認：`build` / `cfg` / `last base` / `roots` / `cores / views` / `candidates` /
   `window evals` / `prune` / `bar events` / `chart tf`。
   Zoneが0件でも `roots` `candidates` `last base` が更新されていれば「処理完了かつ候補0件」です。
6. 実行時間：まず通常実行の完走可否、次にProfilerを**別実行として**確認。
7. 記録項目：ticker ID、チャート時間足とセッション、履歴開始/終了と本数、全パラメータ、
   Library公開番号、build ID、TradingViewが表示する実行制限。
8. Accum確認：1H/4H/日足でBoxが確定する足（条件true→false）を Bar Replay で確認し、
   Box上下限が**実体端**（ヒゲではない）になっていること、終了足が含まれないことを見てください。
9. 付録B 75ケースをBar ReplayとDebug表で確認し、PASS/FAIL/NOT RUN を7.3へ追記。

---

## 11. 論理変更の有無

Zone定義v2の論理は変更していません。Accum形成条件式は付録A 7.4の正本へ一致させました
（改訂1の仮置き式は破棄）。未確認のまま残っているのは2.2の1分岐で、承認前提です。
仕様適合性・実行時間・実機動作はいずれも未検証です。
