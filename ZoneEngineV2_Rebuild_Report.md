# ZoneEngineV2_Rebuild 実装レポート

作成日：2026-09-19（改訂3：最終静的適合監査・一括修正）
Build ID：**`ZEV2R-20260919-003`**（Library / Visual Harness / 本書で共通）
対象：XAUUSD / 確定5分足 / Pine Script v6
正本：`Zone_definition_spec_v2.md` 全21節 ＋ 軽量化実装指示書 M0〜M19 ＋ 付録A〜D

---

## 0. 今回の完了表現

**静的仕様監査で既知の不一致を解消。実機適合性は未検証。**

| 区分 | 件数 | 内容 |
|---|---:|---|
| 仕様上の未解決事項 | **1件** | 10.2 段階B／段階Cの順序が持つ帰結（2.2-Q）。正本どおりA→B→Cで実装済み、確認のみ |
| 実装上の既知の暫定処理 | **0件** | 暫定上限・fallback・打切りは残っていない |
| 結果へ影響する独自解釈 | **3件** | Broad局所化条件3/4の「内部」限定、Merge後にSide履歴0となった場合のWeak扱い、未照合Coreの終了条件（2.3） |

したがって「完成」とは書きません。上記4件の該当箇所を本書2.2〜2.3に具体的に記載しています。

TradingViewで未実行のもの（Compile / 実チャート / Profiler / 75ケース / M15重点ケース /
Bar Replay / reload一致 / リアルタイム一致）は**すべて NOT RUN**のままです（7章）。

---

## 1. 今回変更した全項目

| # | 項目 | 仕様根拠 | 変更前の問題 | 変更後の処理 | 関係受入ケース |
|---:|---|---|---|---|---|
| 1 | Broad局所化の保護対象 | 5.2 / 3.5 / M19.2 | 全High Density候補にdense幅を課していた | `preDenseStrong`（FVG付加**前**にBase Strongだった候補）だけdense幅上限。他はM上限 | 45, 36 |
| 2 | Broadの幾何のみ付加 | 3.5 | `inside`／`proximalAnchored`だけで付加していた | Broadは`broadLocalizeOkAt()`の4条件のいずれかを満たす時だけ付加。不成立なら`consumed`にせず段階BでNativeRange全体のBroad Neutral contextとして出力 | 35, 36 |
| 3 | Broad条件2の空間対応 | 3.5 / M19.2 | 「どこかで別TFと重なる」だけで局所化し得た | `fvgOverlapCovers()`が、同方向・別TFの**実共通区間**が当該候補範囲と交差する場合だけ条件2を成立させる | 31, 36 |
| 4 | Bullish/Bearish非補強 | 3.5 / 9 / M19 14 | `overlapOtherTf`が方向を見ず、Side資格だけで重複扱いし得た | 重複判定は`sFvgDir`（形成方向）一致＋TF相違＋実重複。Side資格（Inverse後を含む）とFVG方向カテゴリ品質を完全に分離 | 26, 31, 33, 65 |
| 5 | 候補生成順を正本へ | 付録A 10.2 | Dense→Normal→FVG後付けで、Normal候補が後からStrong化し得る順序依存 | 段階A（Dense窓＝心理価格込み＋FVG局所化を反映してからBase Strong判定と競合）→段階B（同方向実重複／FVG単独／Broad context）→段階C（残RootのみでM以下のNormal候補） | 36, 40-45 |
| 6 | 競合時点での完成候補評価 | 10.2 / 10.4 | FVG・心理価格の寄与が競合後に付いていた | `scanBest()`が窓ごとに`fvgAugment()`まで実行し、C/H/Density/Base Strongを**完成候補**で判定してから比較関数へ渡す | 40-45 |
| 7 | ReferencePriceのロジック分離 | 5.6 / 付録D | Dormant入り／復帰判定が`referencePrice`を使用 | Dormantは`intervalGap(EffectiveZoneRange, close)`の実距離で判定。`referencePrice`はView出力と表示のみ | - |
| 8 | ActiveTouch中のMerge/Split | 11.4 / 16.1 / 16.2 | 一致Core発見時点で即`mergeCores()`、その後にActiveTouch判定 | 関係Coreのいずれかが`ActiveTouch`なら**merge/split/applyを一切行わず**、全関係Coreを`pendingTopology`にして`lastMatchSeq`だけ更新。終了後の再クラスタで適用 | 66, 67 |
| 9 | Merge履歴の再構築 | 12.2 | 単純append＋`max(sideTouchCount)` | 同一Side・同一時刻・同一接触範囲（tick）・同一`isNormalTouch`を`markIsDuplicate()`でdedupe。統合後に新EffectiveRangeへ実接触する通常TouchMarkから`rebuildCoreHistory()`でSide別履歴を再構築 | 68 |
| 10 | 通常再クラスタでは履歴を再構築しない | 12.1 | （新規の副作用回避） | `rebuildCoreHistory()`はMerge発生時とSplit時のみ。範囲がわずかに動いただけでTouch履歴が減ることはない | 68, 69 |
| 11 | Split履歴とFresh | 12.3 / 19 | `zoneFresh = touchMarks==0` が非通常Touchも数えていた | 子は`contact range`が交差した履歴だけ継承。ZoneFresh/SideFreshは**通常Touchのみ**で消費（FlipConfirm等は消費しない） | 59, 65, 69 |
| 12 | 履歴truncate時のFresh禁止 | 12.3 / 付録A 17.3 | engine全体の`touchHistoryTruncated`しか無く、Fresh復活を防げていなかった | Core単位`marksTruncated`。truncate済みCoreではカウントを既存値未満へ下げず、Freshへ戻さない。Merge/Splitで伝播 | 69 |
| 13 | Merge後の上限・dedupe・診断 | 4.4 / 12.2 | Merge時に`maxTouchMarksPerCore`が適用されていなかった | `mergeCores()`が`trimTouchMarks()`を呼び、超過時に`marksTruncated`と`touchHistoryTruncated`を立てる | - |
| 14 | FlipConfirm後の再Armed | 12 / 15.1 / 15.3 | `lastFlipConfirmSeq`が保存のみで未使用 | `finalizeSide()`が`f.seq <= h.lastFlipConfirmSeq`の足ではArmedにしない。次以降の確定足でReset距離達成→`armedFromSeq = seq+1`→さらに次足から通常Touch | 60 |
| 15 | InverseConfirm後の再Armed | 12 / 15.4 / M19.3 | 同様の抑止が無かった | `Root.inverseConfirmSeq`を保存し、`sideInverseConfirmedNow()`が該当足のArmedを抑止 | 65 |
| 16 | Inverse手順の足順序 | M19.3 | （確認のみ） | 構造無効化＝元時間足Close、距離離脱／再接触／終値回復＝確定5分足。1本の確定足では「離脱」か「再接触＋回復」の一方しか進まない | 64, 65 |
| 17 | Broad contextのCore同一性 | 12.1 / 5.7 | Broad Rootを`originRootIds`から全面除外→Broad standaloneが毎足新Core | 局所Zoneの同一性はBroad以外の起源のみ。**非Broad起源が1つも無いCore**は`isBroadContextCore`とし、そのBroad FVG起源で同一性を追跡。`candSharesOrigin()`は候補側の`candBroadCtx`と一致する場合だけBroad起源で照合 | 35, 75 |
| 18 | 心理価格の安定ID | 3.6 / 7.7 | `psychTickToId` map、512超で全消去→同じ価格が別IDになり得た | mapを廃止。`rootId = PSYCH_ID_BASE + level`（level = 価格/50）。同じ正規化心理価格は常に同じ論理ID。100ドル倍数はMajor 1Rootのみ | 37, 38, 39, 75 |
| 19 | Core整理の優先順 | 4.4 / 14 | `victim < 0`だけで非Dormant Coreが最初の候補になり得た | 2パス。pass0＝Dormantのみ、pass1＝非Dormant。各パス内でRoot数昇順→`lastSeenTime`昇順。Dormantが存在する限り非Dormantは選ばれない | - |
| 20 | Core保護対象 | 4.4 | InverseWait Rootを持つCoreが未保護 | `coreProtected()`がActiveTouch / Broken / FlipWait / BreakSnapshot / PendingTopology / PendingGeneration / InverseWait・InverseActive Root保有を保護 | - |
| 21 | Accum整理の単位 | 4.4 / 3.3 | Root本数（`maxAccumBoxes*2`）で整理し、片側だけ削除し得た | `accumBoxCount()`でBox単位に数え、`pruneAccumBoxes()`が**上下両境界とも未保護**のBoxだけを両方まとめて削除 | 21 |
| 22 | 上限超過の診断 | 4.4 / M13.2 | 保護のみ残った場合に黙って抜けていた | `storageOverLimit=true`を立て、`storageOverLimit()`でexport、Debug表に`OVER-LIMIT`を表示 | - |
| 23 | 整理順（Core→Root） | M13.1 | Root保護集合をCore整理前に作っていたため収束が遅い | Core整理→保護集合再構築→Root/Box整理の順 | - |
| 24 | 世代履歴の保存 | 13 / 18 | `startGeneration()`が旧Generationを`endedGen*`へ残していなかった | 世代開始時に旧Core ID/Generation IDを限定履歴へ push し、`maxEndedGenerations`でtrim | 72, 73 |
| 25 | SplitとGeneration | 13 / 17 / 18 | 子Coreに新Generation IDを採番していた | 子は**親のGeneration IDを継承**。Splitは新Zone世代ではなく、Touch/Weak/Freshのリセットも行わない | 69, 70-73 |
| 26 | Config変更検知 | M4.2 | `cfgFingerprint()`の加重和floatで、未収録項目（accum下限3種・時間設定6種・保存4種）があり衝突もあり得た | Fingerprintを廃止。**確定Base足ごとに`validateCfg()`を実行**。検証項目も全設定へ拡張。`mintick`はFeedから同じ足で反映 | 74, 75 |
| 27 | カテゴリOFFの反映 | 6.1 / M4.2 | ON時に作ったRootがOFF後も候補探索へ残った | `collectPoints()`が`catEnabled()`で除外、`fvgSideEligible()`が`cfg.catFvg`を確認、`sideHasLiveNonPsych()`も同様。Root自体は削除しない | - |
| 28 | Swing起源タグ衝突 | 3.2 / 7.3 | 同tick・同区間ならHighとLowが1Rootへ統合され得た | 同一イベント統合は`subtype`（High/Low）一致が前提。`originKey`にもHigh/Lowを混入 | 17, 18 |
| 29 | 時間高安の起源タグ衝突 | 3.4 / 7.6 | 同tick・同`originTime`ならHighとLowが集約され得た | `timeLabelSet()`が`subtype`一致を要求。ラベル集約は同じ極値種別の中だけ | 25 |
| 30 | 全価格比較のtick正規化 | 18 / 付録D | 幅・密集のみtick、Touch/Break/Reset/Weak/FVG/Gapは生float | `tGe/tLe/tGt/tLt/intersectsT`を導入し、境界を決める比較を全てtick正規化。WeakDepthもtick差から算出 | 1-9 |
| 31 | Debug/表示の完成 | 付録C 22.3 / 22.4 | Root summary、FVG state、採用元足時刻、session/day/week ID、0件切り分けが不足 | 3章の一覧どおり追加 | - |
| 32 | FVG 50%表示 | 22.3 / 付録D | EffectiveRangeの中点を描いていた（誤り） | `fvgNativeMid()`が参加FVGの**NativeRange**中点を返す。FVG不参加なら`na`で非表示。ラベルに`DISPLAY ONLY`を明示。Engineへは渡さない | 34 |
| 33 | 時間設定の可変化 | 3.4 / 17 | Harnessが初期値固定 | timezone / Asia / Europe / NY開始・終了 / dayCut / weekCut をHarness入力に追加し`ZoneCfg`へ反映 | 23, 24 |
| 34 | 探索上限の撤去 | M1.3 | 保存整理のwhileに安全カウンタ（512/256）が残っていた | 削除。両ループは「削除対象なしでbreak」または「1件削除」で必ず進むため停止は保証。`MAX_PSYCH_ROOTS`も未使用のため削除 | - |

---

## 2. 監査結果と残る論点

### 2.1 確認して問題が無かった項目（変更なし）

- FVG構造無効化がReclaimより優先（`markFvgInvalidation()`を検出の最前段で実行）— ケース64。
- GapBreak足でFlip/Reclaimを確定しない（`bs.breakSeq != f.seq`）— ケース57。
- movedAway前の再接触でFlipを確定しない（`bs.movedAway`を要求）— ケース58。
- Touch足でBreakした場合、TouchCountは増えBreakがWeakより優先（`startTouch()`→`activeEval()`の順、`brk`分岐でWeakDepthを評価しない）— ケース55。
- ActiveTouch中の新RootがTouchStartSnapshotへ入らない（Snapshotは`array.copy()`で凍結、再クラスタは当該Coreに適用されない）— ケース66。
- ActiveTouch中のRoot失効はLiveStructureへ即時反映、Snapshot記録は継続（`sideHasLiveNonPsych()`）— ケース67。
- 同一Feed二重処理の防止（`bf.openTime > e.lastBaseOpenTime`）— ケース74。
- 決定論的tie-break（価格順の同値区間をRoot ID昇順へ整列、比較関数は5段で最後にRoot ID）— ケース75。

### 2.2 仕様上の未解決事項（1件）— 確認のみお願いします

**Q. 段階Cの通常候補へFVG局所化は及ぶべきか。**

付録A 10.2の段階順（A→B→C）と、今回いただいた段階定義に従い、
FVG局所化は段階A（Dense窓）で行い、段階Bで残FVGの実重複／単独／Broad contextを確定し、
段階Cは残Rootだけで通常候補を作る、という順序で実装しました。

その帰結として、**段階Cで初めて構成される通常候補（Normal Density）の内部にFVGがある場合、
そのFVGは段階Bで単独候補（またはBroad context）として確定済みのため、通常候補へは合流しません。**

- この動作は仕様5.5の「通常FVG単独：NativeRange全体」「Broad未局所化：Broad context」に該当し、
  いずれも正本にある扱いです。Normal Densityは定義上Base Strongになれないため、
  「後付けでStrongへ昇格する順序依存」は存在しません（ご指摘の主目的は満たしています）。
- 一方で仕様5.5の「FVG内部に局所Root：局所Rootの実分布」を段階C候補にも適用する読み方も可能です。
  その場合は段階Bを段階Cの後へ移すだけで実現できます（局所化条件・範囲規則・競合順は不変）。

**現状は正本の段階順どおりです。** 変更が必要ならご指示ください（A→C→Bへの入れ替え1箇所）。

### 2.3 結果へ影響する独自解釈（3件）

| # | 箇所 | 解釈 | 理由 | 反対の実装にした場合の差 |
|---:|---|---|---|---|
| I-1 | `broadLocalizeOkAt()` の条件3・条件4 | 「内部に高品質な別カテゴリがある」「内部にFVG以外の独立カテゴリが2つ以上高密集」は、候補がFVG NativeRangeと交差している場合（`inside`）にのみ評価する | 仕様3.5が「内部に」と明記しており、Proximal外側に位置する候補は内部条件を満たさないため | Proximal局所化でも条件3/4が成立し得るようになり、Broadの局所化が増える |
| I-2 | `rebuildSideHistory()` | Merge/Split後にそのSideの通常TouchMarkが0件になった場合、`sideTouchCount=0`／`sideFresh=true`／Weak（Touch・Depth）をクリアする。ただし`marksTruncated`のCoreではクリアしない | 仕様12.2「新範囲へ実際に接触していた履歴だけ引き継ぐ」と12.3「未接触の子Zoneは未タッチにできる」に合わせた。Weakは接触の消耗事実なので、接触履歴が属さなくなったSideへは残さない | Weakが範囲移動後も残り続け、接触履歴0のSideがWeak表示になる |
| I-3 | `associateCandidates()` 末尾 | 当該足でどの候補とも照合しなかったCoreは、保護Phase（ActiveTouch/Broken/FlipWait/Pending*/BreakSnapshot）も待機Root（InverseWait/InverseActive）も無い場合に終了世代として閉じる | 仕様14「すべての有効Rootと待機Rootがなくなった時だけ世代終了」に対し、Rootが他Coreへ吸収された場合の重複Zone発生を避けるため | Rootが他Coreへ移った後も空のCoreが残り、同一構造のZoneが二重に出力され得る |

### 2.4 実装上の既知の暫定処理（0件）

- 探索回数・走査範囲の上限、近似探索、時間切れ、空結果fallbackは**存在しません**。
- `SCRATCH_MAX_ROOTS`は診断フラグ（`scratchOverflow`）を立てるだけで、探索・候補・Rootを一切捨てません。
- 保存整理は保護対象を削除せず、削除できない場合は`storageOverLimit`で報告します。
- 心理価格の合成範囲限定は仕様3.6／7.7が明示的に認めている「現在価格周辺」です。

---

## 3. Visual Harness / Debugの充足状況（付録C）

### Label（`viewLabelText()`）

| 必須項目 | 実装 |
|---|---|
| CoreID / GenerationID / Side | `#<id> / G<gen> / <Side>` |
| Phase / Grade | `Waiting\|Strong` 形式で別表示 |
| Range / Reference | `Range <bottom>-<top> / Ref <price>` |
| C / H / Density | `C2 H1 High BaseStrong` |
| Current / Upcoming Touch | Phaseに応じてどちらか |
| WeakReason / MaxDepth | `WeakByBoth / MaxDepth 62.5%` |
| ZoneFresh / SideFresh | `ZoneFresh Y / SideFresh N` |
| FVG direction | `fvgDirText()`（Bullish/Bearish） |
| FVG Fresh count | `fresh 1/2` |
| FVG state | `fvgStateText()`（Active / InverseWait / InverseActive） |
| Broad context | `| BROAD CONTEXT` |
| Category summary | `categorySummary()`（High は `(H)`） |
| Root summary | `rootSummary()`（カテゴリ＋RootID＋元時間足） |

### Debug table（18行）

build ID / config validation / 最終Base足時刻＋seq / 採用した1m MA元足時刻 /
採用したFVG元足時刻（1H・4H・日） / 採用したAccum確定時刻（1H・4H・日） /
Root数 / Candidate数 / Core数・View数 / **Zone 0件の理由** /
PendingTopology・PendingGeneration・deferred数 / Merge・Split・照合数 /
窓評価数・Denseラウンド数 / prune（TOUCH-TRUNC / OVER-LIMIT / SCRATCH） /
終了世代数 / MA傾き / session・day・week ID / 当該足Event列。

**Zone 0件の切り分け**は次の順で表示します：
`config invalid` → `engine never updated` → `engine updated, 0 roots` →
`engine updated, roots present, 0 candidates` → `candidates present, 0 cores` →
`cores present, 0 views`。

### Harnessで禁止されているもの

`strategy()`宣言なし、Entry/Exitなし、勝敗集計なし、環境認識フィルターなし、
Zone選択を1件へ絞る処理なし（距離順は**表示順のみ**で、Engineは全Viewを返します）。

FVG 50%は任意表示。有効時は参加FVGのNativeRange中点に線を引き、
ラベルへ`FVG NativeRange 50% - DISPLAY ONLY`と明示します。View にFVG Rootが無ければ非表示です。

---

## 4. 静的確認結果（付録D）

### 4.1 存在してはいけない依存（コード全体検索＋経路確認）

| 対象 | 結果 | 確認方法 |
|---|---|---|
| Score閾値によるGrade | **0件** | `gradeOf()`はUnavailable→Weak→Strong→Neutralの4分岐のみ。score変数自体が存在しない |
| Reaction Bonus / Flip Bonus | **0件** | `flipAttemptCount`/`inverseAttemptCount`は保存のみで`gradeOf()`から参照されない |
| 加重平均CenterによるTouch/Break | **0件** | Touch/Breakは`h.lastArmedRange*`と`TouchStartSnapshot`/`BreakSnapshot`のみを読む |
| FVG 50%ロジック | **0件** | Library内に50%の計算は`fvgNativeMid()`（export・表示専用）だけ。Engineの判定経路から呼ばれない |
| ATRによるZone幅 / Break幅 / Reset距離 | **0件** | `ta.atr()`は`accumCondV2()`内の1箇所のみ。値はBox境界にもZoneにも出ない |
| BOS | **0件** | 文字列・概念とも不在 |
| Strategy勝敗 | **0件** | Entry/Exit/PnLに関する型・関数が存在しない |
| HTF環境フィルター | **0件** | 上位足の上昇/下降/レンジ判定が存在しない |
| 中心±固定幅（`zoneHalfWidth`相当） | **0件** | 範囲は常に参加Rootの実価格分布／NativeRange／共通区間 |
| ReferencePriceのロジック利用 | **0件** | 代入は`computeRefPrice()`→`sv.referencePrice`→`ZoneView`→ラベルのみ（本書1章#7） |

### 4.2 存在必須（処理経路まで確認）

| 対象 | 経路 |
|---|---|
| tick正規化 | `toTick()` / `tGe,tLe,tGt,tLt` / `intersectsT`。Touch・Break・Reset・Weak・Gap・FVG無効化・Inverse・Armed・identity gap・幅/密集の全境界で使用。生floatの境界比較は静的検索で0件 |
| ConfirmedTime gate | `ingestSwing`（`highConfirmed <= baseCloseTime`）、`ingestAccum`、`ingestFvgNew`、`markFvgInvalidation`/`applyFvgState`（`srcCloseTime <= closeTime`） |
| 前足Armed gate | `armedEval()`の`h.armedFromSeq <= f.seq`。`finalizeSide()`が`armedFromSeq = f.seq + 1`を設定 |
| TouchStartSnapshot | `startTouch()`で`array.copy(sv.rootIds)`ごと凍結。以後`deepestClose`/`maxDepthPct`以外は書き換えない |
| BreakSnapshot | `applyBreak()`で作成。Flip/FlipAttempt/Reclaimは`processBreakState()`でこの固定範囲のみ参照 |
| Side別履歴 | `SideViewState.history`（`SideHistory`）をSupport/Resistanceで別インスタンス保持 |
| Weak永続 | `weakByDepth`は`startGeneration()`（と2.3 I-2のMerge/Split再割当）以外で false に戻らない。`weakByTouch`は`sideTouchCount`から毎足導出 |
| FVG方向filter | `fvgSideEligible()`。Bullish Active→Support、Bearish Active→Resistance、Invalidated/InverseWait→不参加、Inverse Active→反対側 |
| PendingTopology | `associateCandidates()`のActiveTouch分岐で設定し、merge/split/applyを抑止 |
| 新世代の新カテゴリ条件 | `updateGenerationCandidate()`：`catMask - (catMask & genBaselineCatMask)` から心理ビット(32)を除去、かつBase Strong、かつReset距離離脱、かつ再接近時に`startTouch()`冒頭で切替 |
| 決定論tie-break | `collectPoints()`の同値区間Root ID整列 ＋ `scanBest()`の5段比較（C↓ H↓ 幅↑ 成立時刻↑ 最小RootID↑） |
| duplicate base guard | `update()`の`bf.openTime > e.lastBaseOpenTime` |

### 4.3 機械実行した静的検査（構文・構造）

| 検査 | 結果 |
|---|---|
| 行継続インデントがPineの規則（4の倍数でない）を満たすか（括弧継続・演算子継続） | 違反0件 |
| 降順ループ（`n-1 to 0`）のゼロ件ガード | 違反0件 |
| 昇順ループ上限が空配列で負にならないか | 外側の`while`/`if`で保証 |
| 関数の前方参照 | 0件 |
| 呼び出し先未定義 | 0件 |
| UDTフィールド名の突合 | 0件 |
| Library内の`request.*`呼び出し | 0件（コメント記述のみ） |
| Harnessが使う`ze.*`のexport存在確認 | 全件存在 |

**これらは構文・構造の検査であり、仕様適合や実行時間の証拠ではありません。**

---

## 5. request数 / tuple要素数

| コンテキスト | 呼出 | tuple要素 | 内容 |
|---|---:|---:|---|
| 1分足 | 1 | 5 | EMA2000 / 傾き / EMA3000 / 傾き / 元足closeTime |
| 5分足 | **0** | 8 | チャート直接計算（`ze.pivotPackV2`） |
| 15分足 | 1 | 8 | Swing |
| 1時間足 | 1 | 29 | Swing8 + Accum6 + FVG10 + 確定元足5 |
| 4時間足 | 1 | 21 | Accum6 + FVG10 + 確定元足5 |
| 日足 | 1 | 21 | Accum6 + FVG10 + 確定元足5 |
| **合計** | **5** | **84** | tuple要素上限127以内 |

実ソースを機械的に数えた値です。条件分岐内の追加`request`・補助`request`はありません。
これはコンパイル確認ではありません。

---

## 6. 計算構造とキャッシュ

### 6.1 キャッシュ（キー／失効／容量／fallback／所有）

| 対象 | キー | 失効条件 | 容量 | 容量超過時 | 所有 |
|---|---|---|---|---|---|
| `idToSlot` | Root ID | 登録／削除 | 生存Root数 | なし | Engine |
| `originToId` | 起源キー | 登録／削除 | 生存Root数 | なし | Engine |
| `idxCat*` | カテゴリ | 登録／削除 | 生存Root数 | なし | Engine |
| `sLot*`（価格順） | なし（毎足再構築） | 毎足 | 生存点Root数 | 打切りなし。`scratchOverflow`を立てるだけ | Engine |
| `sFvg*`（Side別FVG集合） | Side | Side切替ごとに再構築 | 当該Sideの適格FVG数 | なし | Engine |
| `cand*`（採用候補） | なし（毎足再構築） | 毎足 | 候補数 | なし | Engine |
| Feed重複排除 | 元足closeTime／originTime | 新しい元足 | 各1 | なし | Engine |
| 設定検証 | なし（毎確定足実行） | 毎足 | - | - | Engine |

**心理価格のmapは廃止しました**（論理IDを価格から直接算出するため、寿命管理が不要になりました）。
足をまたぐ候補キャッシュは実装していません。

### 6.2 計算量と、素直に計算した場合からの削減

| 処理 | 本実装 | 単純計算との差 |
|---|---|---|
| 価格順構築 | `O(R log R)`（native sort）＋同値区間のみ挿入整列 | 毎足の全比較ソートを回避 |
| Dense/通常候補探索 | 開始位置ごとに窓内本数k → `O(R·k)`／ラウンド | 窓ごとに窓内全Rootを引き直す`O(R·k²)`を回避（カテゴリ・品質要約を増分更新） |
| FVG局所化 | 窓あたり`O(F)`（Broadのみ`O(F²)`の空間条件） | 全FVG×全候補の品質判定を回避 |
| Root検索 | ID→slot / 起源→ID / カテゴリ→slot集合 | 全件線形探索を回避 |
| Core照合 | 範囲gapの安価判定→一致候補のみ起源突合 | 全Core×全Candidateの重い照合を回避 |
| Reference | 採用候補のみ1回 | 落選候補の中央値計算をゼロに |
| 元足取得 | 5コンテキスト・84要素 | カテゴリ／時間足ごとの個別requestを回避 |
| 保存整理 | 上限超過時のみ。保護集合は整理1回につき1度構築 | 削除ごとの保護再構築を回避 |

**隠れた線形処理**：`liveOrder`の挿入は二分探索で位置を決めますが要素移動は線形です。
`array.insert`／`array.remove`（category index、cores）も線形です。
`markIsDuplicate()`はMerge時にマーク数に比例します。

---

## 7. 検証状況（NOT RUN一覧）

| 検証 | 状態 |
|---|---|
| Pineコンパイル | **NOT RUN** |
| 実チャート実行（XAUUSD 5分足） | **NOT RUN** |
| Profiler | **NOT RUN** |
| 実行時間（40秒制限に対する0.5L=20秒目標） | **NOT RUN** |
| 付録B 75ケース | **全件 NOT RUN** |
| M15重点ケース | **全件 NOT RUN** |
| Bar Replay | **NOT RUN** |
| reload一致 | **NOT RUN** |
| リアルタイム足一致 | **NOT RUN** |
| 保存上限の到達・超過テスト | **NOT RUN** |

本実行環境からTradingViewへアクセスできないため、上記はいずれも実行していません。
静的にコードを直したことと、実機で仕様適合を確認したことは別です。

---

## 8. 付録B 75ケースのコード単位事前監査

すべて判定は`NOT RUN`です。「経路」は現在のコード上で当該条件を決めている箇所です。

### A. 境界値

| # | 期待値 | 対応関数 | 対応条件・経路 |
|---:|---|---|---|
| 1 | 幅=Mちょうどで同一通常Zone可 | `scanBest` | `wTick > limitTick`で`break`。`limitTick = mTickLimit`なので等号は通過 |
| 2 | 幅=denseWidthちょうどでHigh Density | `scanBest` / `adoptWindow` | `awT <= denseTickLimit(cfg) ? 0 : 1` |
| 3 | ResetDistanceちょうどでReset/Armed | `activeEval` / `finalizeSide` | `tGe(f.c, top + cfg.touchResetDistance)` |
| 4 | WeakDepthちょうどでWeak | `activeEval` | `depth >= cfg.weakDepthPct` |
| 5 | Support CloseがBottom−BufferちょうどでBreak | `activeEval` | `tLe(f.c, bot - cfg.breakBuffer)` |
| 6 | Resistance CloseがTop＋BufferちょうどでBreak | `activeEval` | `tGe(f.c, top + cfg.breakBuffer)` |
| 7 | FVG CloseがDistal同値なら有効 | `markFvgInvalidation` | `tLt` / `tGt` の**厳密**比較のみ無効化 |
| 8 | WickがZone端と同値ならTouch | `armedEval` | `tGe(f.h, bot) and tLe(f.l, top)` |
| 9 | 一本線Tolerance 0の同値Touch | `armedEval` | `tLe(f.l, bot + tol) and tGe(f.h, bot - tol)` |

### B. MA

| # | 期待値 | 対応関数 | 経路 |
|---:|---|---|---|
| 10 | EMA1本はNormal、C=1ならNeutral | `scanBest` / `gradeOf` | `maCnt == 2`不成立でMA Highなし。C=1はBase Strong式でfalse |
| 11 | 2本Denseでも片方下向きならSupport MA Normal | `scanBest` | `side == 1 ? maUp == 2 : maDn == 2` |
| 12 | 2本Dense＋両方上向きでSupport MA High | `scanBest` | 同上＋`denP == 0` |
| 13 | 同状態でResistance側はHighにならない | `scanBest` | 同上（`maDn == 2`が不成立） |
| 14 | MA High＋別カテゴリ、C=2、High DensityでBase Strong | `scanBest` | `(cCnt == 2 and hCnt >= 1)` |
| 15 | EMA移動だけで世代/Fresh/Touchをリセットしない | `ingestMa` / `updateGenerationCandidate` | 価格と`slopeDir`のみ更新。世代候補は「新独立カテゴリ」必須 |

### C. Swing / Accum / 時間高安

| # | 期待値 | 対応関数 | 経路 |
|---:|---|---|---|
| 16 | PivotはConfirmedTime前にRoot化しない | `ingestSwing` | `pk.highConfirmed <= baseCloseTime` |
| 17 | 同価格tick＋上位足区間内の5分＋15分は同一イベント | `swingIngestOne` | `r.subtype == sub and r.priceTick == tick` ＋ `[originTime, originEndTime)`包含。`labelMask`にTFビットを追加 |
| 18 | 別時期の同価格Swingは別イベント | `swingIngestOne` | 区間包含が不成立→新Root（`originKey`にoriginTimeとHigh/Lowを含む） |
| 19 | Accum Candidate中はRootなし・Touchなし | `accumPackV2` | `outNew`はtrue→false遷移でのみtrue。Candidateは外部へ出さない |
| 20 | true→falseのfalse足実体をBoxへ含めない | `accumPackV2` | 終了足では`candTop/candBot`を更新せずに出力 |
| 21 | 同じAccum BoxのTop/BottomがM以内でも別Zone | `scanBest` | `e.sPairs`に`pairKey`が既出なら`break`（同一候補へ入れない）。整理も`pruneAccumBoxes`がBox単位 |
| 22 | 4時間Accum境界はAccum High | `scanBest` | `acHas4hD := r.tfCode >= 240` |
| 23 | 14:00足からEurope、19:00足からNY、03:00足からセッションなし | `sessionIdxOf` | `m >= europeStartMin and m < nyStartMin` 等。足のopenTimeで判定 |
| 24 | 05:00足から新取引日 | `dayKeyTz` | `t - dayCutMin*60000`の日付で判定 |
| 25 | 新極値足が自身をTouchしない | `update` | `updateTimeHL()`はステップE（Touch評価の後）で実行。High/LowのRootは`subtype`で分離 |

### D. FVG

| # | 期待値 | 対応関数 | 経路 |
|---:|---|---|---|
| 26 | BullishはSupportだけ、BearishはResistanceだけ | `fvgSideEligible` | 4分岐（Active・Inverse Active） |
| 27 | 形成3本目確定前はRootなし | `ingestFvgNew` | `bullConfirmed <= baseCloseTime` |
| 28 | 確定後の最初のwick進入でFresh終了、Rootは存続 | `applyFvgState` | `f.closeTime > r.confirmedTime`かつ`intersectsT` → `fvgFresh := false`のみ |
| 29 | 元TF CloseがDistalを厳密に越えた時だけInvalidated | `markFvgInvalidation` | `tLt(srcClose, nativeBottom)` / `tGt(srcClose, nativeTop)` |
| 30 | 構造無効化にBreakBufferを使わない | `markFvgInvalidation` | 式にbufferが現れない |
| 31 | 同方向・異TFの実重複は共通区間かつFVG High | `fvgStandalone` / `buildFvgSet` | 重複は`sFvgDir`一致＋TF相違＋`intersectsT`。範囲は`max(bot)`〜`min(top)` |
| 32 | 同方向でも非重複ならM以内だけで結合しない | `fvgStandalone` | 結合条件は`intersectsT`のみ（距離条件なし） |
| 33 | BullishとBearishは相互補強しない | `buildFvgSet` / `fvgOverlapCovers` / `fvgStandalone` | すべて`sFvgDir`一致を要求。Side資格（Inverse後の反対側参加）とは別経路 |
| 34 | FVG 50%を変えてもZone結果が変わらない | Library全体 | 50%はexport `fvgNativeMid()`のみでEngineの判定経路に存在しない |
| 35 | Broad単独はStrongにならない | `fvgStandalone` | `broadCtx`時に`den = 2`、`candStrong = 0`固定 |
| 36 | Broad＋有効局所化条件では局所部分だけStrong候補にできる | `fvgAugment` / `broadLocalizeOkAt` | 4条件のいずれか成立時のみ付加。範囲は点Root分布（内部）またはProximal edge〜分布 |

### E. 心理価格 / Strong

| # | 期待値 | 対応関数 | 経路 |
|---:|---|---|---|
| 37 | 心理価格単独ではZoneなし | `scanBest` | `nonPsych > 0`でなければ候補として評価しない |
| 38 | Major 100ドル位置にStandardを重複生成しない | `syncPsych` | levelごとに1Root、`lvl % 2 == 0`でMajor |
| 39 | 心理はCに数えるがHにならない | `scanBest` | `catMask`へは加算、`hMaskP`のビットに心理は存在しない |
| 40 | C=1 HighでもBase Strongにならない | `scanBest` | `(cCnt == 2 and hCnt >= 1) or cCnt >= 3` |
| 41 | C=2、High Density、H=0ならBase Strongにならない | `scanBest` | 同式 |
| 42 | C=2、High Density、H>=1でBase Strong | `scanBest` | 同式 |
| 43 | C>=3、High DensityでBase Strong | `scanBest` | 同式 |
| 44 | Normal DensityではCが多くてもBase Strongにならない | `scanBest` | `aden == 0`必須 |
| 45 | Dense Strong coreへ外側Rootを加えてNeutralへ落とさない | `buildCandidates` / `fvgAugment` | 段階Aで採用したRootは`sUsed`で再利用されず、段階Cは残Rootのみ。FVG Proximal付加は`preDenseStrong`時にdense幅上限 |

### F. Touch / Weak

| # | 期待値 | 対応関数 | 経路 |
|---:|---|---|---|
| 46 | Root成立時に価格がZone内ならWaiting、成立足Touchなし | `associateCandidates` / `finalizeSide` | 新Coreは`phase = 0`。Armedは距離条件＋`armedFromSeq = seq+1` |
| 47 | 前足ArmedでないZoneはwick交差してもTouchなし | `update` / `armedEval` | `ph == 1`かつ`armedFromSeq <= f.seq`のViewのみ評価 |
| 48 | 同一Episode内の複数往復はTouch 1回 | `activeEval` | Reset成立まで`phase = 2`のまま、`currentTouchNo`固定 |
| 49 | 初期値ではBase StrongのTouch 1がStrong | `gradeOf` | `targetTouchNo <= strongUntilTouch(1)` |
| 50 | Touch 1完了後、Upcoming Touch 2がWeak | `finalizeSide` / `gradeOf` | `upcomingTouchNo = 2 >= weakFromTouch(2)` |
| 51 | Touch 1中にDepth 50%でCurrent Weak、TouchStartGradeはStrongのまま | `activeEval` | `h.weakByDepth := true`。`sn.touchStartGrade`は書き換えない |
| 52 | Reset後もWeakは維持 | `activeEval` / `startGeneration` | Reset処理はWeakに触れない。解除は世代開始のみ（2.3 I-2の例外あり） |
| 53 | 一本線ではWeakDepthを使わない | `activeEval` | `widthT > 0`のときのみ計算 |

### G. Break / Flip / Reclaim

| # | 期待値 | 対応関数 | 経路 |
|---:|---|---|---|
| 54 | Wick抜けだけではBreakしない | `activeEval` / `armedEval` | 条件は`f.c`（確定終値）のみ |
| 55 | Touch足でBreak：TouchCountは増えBreakがWeakより優先 | `startTouch`→`activeEval` | カウント加算後に`brk`分岐。`brk`時はWeakDepthを評価しない |
| 56 | 完全GapBreakでTouchCount/WeakDepth/Freshを変えない | `armedEval` | 非交差判定の後`applyBreak(..., gap = true)`のみ。`startTouch`を通らない |
| 57 | GapBreak足でFlip/Reclaimを同時確定しない | `processBreakState` | `bs.breakSeq != f.seq` |
| 58 | Reset距離を取る前の再接触はFlipConfirmにならない | `processBreakState` | `bs.movedAway`が先に必要 |
| 59 | FlipConfirm接触は通常Touchへ数えない | `processBreakState` | `TouchMark(isNormalTouch = false)`。`sideTouchCount`に触れない |
| 60 | Flip後は別足で再度Resetしてから通常Touch 1 | `processBreakState` / `finalizeSide` | `lastFlipConfirmSeq = f.seq` → 当該足はArmed不可 → 次足以降にReset成立 → `armedFromSeq = seq+1` |
| 61 | 過去に使ったSideへ再FlipでTouch/Weak履歴を復元 | `SideHistory` | Side別インスタンスが常駐。Flipは履歴を消さない |
| 62 | ReclaimでFresh/Weakをリセットしない | `processBreakState` | `bs.valid := false`とphase復帰のみ |
| 63 | EMA移動後もFlip/Reclaim基準がBreakSnapshotから動かない | `applyBreak` / `processBreakState` | 判定は`bs.rangeBottom/Top`のみ |
| 64 | FVG無効化とReclaim同時ならFVG無効化優先 | `markFvgInvalidation` / `sideHasLiveNonPsych` | 無効化の事実を検出の最前段で確定し、`oldRootsLive`がfalseならReclaimしない |
| 65 | InverseConfirmを通常Touchへ数えない | `updateFvgInverse` | EventのみでTouchMark・`sideTouchCount`に触れない。`inverseConfirmSeq`で当該足のArmedも抑止 |

### H. Topology / 世代 / 再現性

| # | 期待値 | 対応関数 | 経路 |
|---:|---|---|---|
| 66 | ActiveTouch中の新RootでTouchStartGradeを書き換えない | `startTouch` / `associateCandidates` | Snapshotは`array.copy()`で凍結。ActiveTouch中のCoreは`pendingTopology`のみ |
| 67 | ActiveTouch中のRoot失効後もOutcome記録は継続、新Signalには使わない | `activeEval` / `sideHasLiveNonPsych` | `activeEval`はSnapshot範囲で継続。参加資格は即時反映 |
| 68 | Mergeで同一接触を二重カウントしない | `markIsDuplicate` / `rebuildCoreHistory` | Side・時刻・接触範囲tick・種別でdedupe後、実接触マークから再計上 |
| 69 | Splitで実際に触れていない子はFreshになれる | `splitCore` / `rebuildCoreHistory` | `intersectsT`で割当、通常Touchのみで`zoneFresh`/`sideFresh`判定。`marksTruncated`時はFresh復活しない |
| 70 | 未タッチZoneへのRoot追加は同世代 | `updateGenerationCandidate` | `consumed`（Touch/Weak/Break/非Fresh）が必要 |
| 71 | 同カテゴリRoot追加・EMA移動・心理価格追加だけでは新世代にならない | `updateGenerationCandidate` | `catMask`差分から心理ビット(32)を除去。同カテゴリは`catMask`を変えない |
| 72 | 新独立カテゴリ＋Base Strong＋Reset＋再接触でだけ新世代Touch 1 | `updateGenerationCandidate` / `startTouch` | `genCandidateReady` ＋ `genCandidateMovedAway` ＋ 接触足で`startGeneration()`→その接触がTouch 1 |
| 73 | 新世代開始時のみ両SideのTouch/Weak/Freshをリセット | `startGeneration` | 両Side履歴・`zoneFresh`・`breakSnap`・TouchMarkをリセットし、旧世代を`endedGen*`へ保存 |
| 74 | 同じ確定Feedを二度渡しても二重更新しない | `update` | `bf.openTime > e.lastBaseOpenTime` |
| 75 | reload後に同じデータでID/Phase/Grade/イベント列が再現 | 全体 | ID採番は確定足順、価格順は同値でRoot ID整列、心理IDは価格から決定、比較は全段tie-break |

### M15 追加重点ケース

| ケース | 対応経路 | 判定 |
|---|---|---|
| Root削除＋slot再利用 | `unregisterRoot`が`freeSlots`へ返却、`registerRoot`が再利用。論理IDは再利用しない（心理価格のみ価格由来の固定ID） | NOT RUN |
| Merge後の後続照合再評価 | `mergeCores`後に`refreshCoreRange`/`rebuildOriginIds`が更新され、後続候補の照合は更新後のCoreに対して行われる | NOT RUN |
| 保存上限 直前／到達／超過 | `pruneStorage`：Core整理→保護集合再構築→Swing/FVG/Time/Accum整理 | NOT RUN |
| 保護対象だけが残る | `coreProtected` / `rootProtected`が全て真なら`storageOverLimit = true`、削除せず診断 | NOT RUN |
| Accum片側保護 | `pruneAccumBoxes`が同一`pairKey`の全Rootの保護状態を確認してから両方を削除 | NOT RUN |
| Touch履歴truncate | `trimTouchMarks`が`marksTruncated`と`touchHistoryTruncated`を設定、`rebuildSideHistory`がFresh復活を禁止 | NOT RUN |
| scratch容量超過時のexact fallback | `SCRATCH_MAX_ROOTS`超過は`scratchOverflow`診断のみ。探索・候補は一切削らないため再計算経路が不要 | NOT RUN |
| リアルタイム／reload／Bar Replay同値 | 更新は`barstate.isconfirmed`かつ`openTime`単調増加の足のみ。描画は`varip`を使わず毎回再構成 | NOT RUN |

---

## 9. TradingViewでの次工程（実測のみ）

1. `ZoneEngineV2_Rebuild.pine` をPine Editorで **Add to chart** → コンパイル確認。
   エラーは行番号とメッセージをそのまま共有してください。
2. **Publish library** → 発行された `<username>/ZoneEngineV2_Rebuild/<version>` を控える。
3. Harnessの `import YOUR_TV_USERNAME/ZoneEngineV2_Rebuild/1` を実番号へ置換。
4. **XAUUSD 5分足**へHarnessを追加。Debug表の`build`が`ZEV2R-20260919-003`であることを確認。
5. Debug表で処理状況を確認。Zoneが0件でも「zone 0 reason」で段階を切り分けられます。
6. 通常実行の完走可否 → 別実行でProfiler（測定負荷は別物として扱う）。
7. 計測条件を記録：ticker ID、時間足、セッション、履歴開始/終了と本数、全パラメータ、
   Library公開番号、build ID、TradingViewが表示する実行制限。
8. 付録B 75ケースとM15重点ケースをBar Replayで確認し、本書8章へPASS/FAIL/NOT RUNを追記。
9. Accum確認：1H/4H/日足でtrue→falseとなる足を再生し、Box上下限が**実体端**であること、
   終了足が含まれないこと、ATRがBox幅へ出ていないことを確認。

---

## 10. まとめ

- Zone定義v2の論理は変更していません。
- 今回の一括修正で、既知の不一致（1章の34項目）を解消しました。
- **仕様上の未解決事項1件（2.2）**、**独自解釈3件（2.3）**、**暫定処理0件（2.4）** です。
- 実機適合性・実行時間・描画・再現性はすべて未検証（`NOT RUN`）です。
