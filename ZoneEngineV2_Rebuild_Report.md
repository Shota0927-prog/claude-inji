# ZoneEngineV2_Rebuild 実装レポート

作成日：2026-09-19（改訂5：TradingView実機検証前の最終静的版）
Build ID：**`ZEV2R-20260919-005`**（Library / Visual Harness / 本書で共通）
対象：XAUUSD / 確定5分足 / Pine Script v6
正本：`Zone_definition_spec_v2.md` 全21節 ＋ 軽量化実装指示書 M0〜M19 ＋ 付録A〜D

---

## 0. 静的監査の最終状態

| 区分 | 件数 |
|---|---:|
| 仕様上の未解決事項 | **0件** |
| 実装上の既知の暫定処理 | **0件** |
| 結果へ影響する独自解釈 | **0件** |

### Zone判定結果へ影響しない実装決定（全Cfg範囲で不変なもののみ）

- **Split子CoreのGeneration ID**：親のGeneration IDを継承します。Splitは新Zone世代ではないため
  （仕様18のリセット条件を満たさない）、新IDを振ると「新世代開始」と矛盾します。
  Touch / Weak / Fresh のリセットは行いません。影響は表示されるGeneration IDのみで、
  いずれの設定値でもZone判定（Phase / Grade / C / H / Density / Touch / Break / Flip / 世代）は変わりません。

改訂4で「影響しない実装決定」として記載していた**心理価格の1本選択は削除しました**。
`clusterMaxWidth`を変更すると結果が変わり得るため、この区分に該当しません。
改訂5では選択自体を廃止し、参加可能な全ての心理価格構成を評価します（1章 #3）。

**実機適合性は未検証です。** Compile / 実チャート / Profiler / 75ケース / M15重点ケース /
Bar Replay / reload一致 / リアルタイム一致は**すべて NOT RUN**（6章）。

---

## 1. 改訂5の修正（4項目）

### #1 clearLiveSide後にCore物理範囲とOriginを必ず再構築

**仕様根拠**：仕様4.3（方向別に独立評価）、12.1（同一性）、14（Zone lifetime）。

**変更前の問題**：`refreshCoreRange()`が`historyDirty`条件の内側にあり、
`rebuildOriginIds()`は`applyCandidate()`内でしか呼ばれていませんでした。
Supportだけ今バー更新・ResistanceはclearLiveSideかつ`historyDirty = false`のとき、
`physBottom` / `physTop` / `originRootIds` に前バーResistanceの情報が残り得ました。
これは次バーのCore identity、`candSharesOrigin()`、価格的連続性、Dormant距離、
Zone lifetime、Root ownershipへ影響し得ます。

**変更後の処理**：`associateCandidates()`末尾のCore単位処理を明示的な5段階にしました。

```text
1) Side apply / clear      applyされなかったSideへ clearLiveSide()（ActiveTouch中は除く）
2) refreshCoreRange(c)     現在のLive Side Structureだけから phys range を再構築（無条件）
3) rebuildCoreOrigins(e,c) 現在のLive Side Structureだけから origin 集合を再構築（無条件）
4) historyDirty のときだけ pruneMarksToRange() → rebuildCoreHistory()
5) Zone lifetime 判定
```

`historyDirty`は**Touch Episode再配分が必要かどうかだけ**に使い、
Coreの現在物理範囲・現在Origin集合の再構築条件には使いません。

`rebuildCoreOrigins()`は次を行います。

1. 現在の`originRootIds`から、**まだこのCoreが所有していて**（他Coreへ移っておらず生存）、
   かつ`state = InverseWait`の待機Rootを退避。
2. `rebuildOriginIds()`で現在のLive Side Structureだけから origin を作り直す。
3. 退避した待機Rootを戻す（無効化FVGはどのSideにも参加しないが、
   Coreを`InverseWait | Unavailable`として維持するため）。
4. 非Broad起源の有無から`isBroadContextCore`を再計算し、Broad standalone contextの
   特殊identityを再構築後も維持する。

### #2 Touch Episodeのdedupeキーを統一

**仕様根拠**：仕様12.2「同一Side、同一時刻、同一接触を1回へdedupe」。

**変更前の問題**：`markIsDuplicate()`は Side＋time＋接触範囲tick＋種別 で判定していましたが、
`rebuildSideHistory()`のTouchCount計算は`lastT`（時刻）だけで重複を潰していたため、
同じ5分足内の別価格帯への2接触まで1回にまとめていました。

**変更後の処理**：Episodeの一意キーを1か所へ集約しました。

```pine
sameEpisode(cfg, a, b) =>
    a.side == b.side and a.time == b.time and a.isNormalTouch == b.isNormalTouch and
     toTick(a.contactBottom) == toTick(b.contactBottom) and
     toTick(a.contactTop)    == toTick(b.contactTop)
```

`markIsDuplicate()`（Merge時のdedupe）と`rebuildSideHistory()`（SideTouchCountの計上）が
**同じ`sameEpisode()`**を使います。同Side・同時刻でも接触範囲が違うEpisodeは別Touchです。

### #3 心理価格を1本に限定しない

**仕様根拠**：仕様3.6、7.7、5.4、付録A 10.2 段階A 手順6。

**変更前の問題**：`psychAugment()`が参加可能な心理価格を「結果幅が狭い→levelが小さい」で
1本だけ選んでいました。`clusterMaxWidth`は変更可能で、例えばM=60では複数の50ドル刻みが
同じ候補のM以内へ入るため、本来評価されるべき候補を落とし得ます。

**変更後の処理**：`psychVariants()`が、参加可能な心理価格の**全構成**を候補範囲として列挙します。

- 候補範囲に内包される心理価格は必ず参加するため、**範囲が決まれば参加集合が一意に決まります**。
  そこで下方向の拡張本数 × 上方向の拡張本数の全組合せを候補範囲として生成します
  （内側に心理価格があれば拡張0でも参加あり）。
- 幅が`limitTick`（段階A＝denseWidth、段階B/C＝M）を超える組合せは生成しません。
- `scanBest()`は「心理価格なし」＋各構成を**すべて**同じ比較関数で評価します。
- `adoptWindow()`は`collectPsychRoots()`で、採用範囲に入る生存心理価格Rootを**全て**
  候補のRoot一覧へ加えます（EffectiveRangeは実参加価格を反映）。

維持している性質：心理価格単独で候補を開始・維持しない（価格順配列に入らない）、
PsychカテゴリのCは最大1（catMaskのPsychビット32だけを立てる）、Hは常に0（`hMaskNoMa`に心理ビットなし）、
100ドル価格はMajorの1Rootのみ（level偶数）、列挙順は下→上で決定論的、幅M超の組合せは不可。

### #4 Touch Episode pruneを片Side Coreでも実行

**仕様根拠**：仕様12.2 / 12.3。

**変更前の問題**：`pruneMarksToRange()`が「Support ViewとResistance Viewの両方に
EffectiveRangeが存在する」場合だけ実行されており、片Sideだけ有効なCoreでは
現在の物理範囲外のEpisodeが残り続けました。

**変更後の処理**：条件を`not na(c.physBottom)`（#1で無条件に再構築済み）へ変更しました。
併せて、

- 進行中のActiveTouch Episode（いずれかのSideの`activeMark`）は削除しません。
- `TouchStartSnapshot` / `BreakSnapshot`はEpisode配列とは独立に`array.copy()`で保持されており、
  pruneの影響を受けません。
- `marksTruncated`はCore単位で保持され、`rebuildSideHistory()`が回数を下げず・Weakを解除せず・
  Freshへ戻さない契約を維持します。
- Splitは従来どおり、分裂前のEpisode集合から全ての子へ配分した**後**に、
  各Core（親・子）で`pruneMarksToRange()` → `rebuildCoreHistory()`の順で処理します
  （両方に`historyDirty`が立ち、末尾の5段階処理で実行されます）。

---

## 2. 追加静的監査（ケースJ〜Q）

| # | ケース | 経路 | 結果 |
|---|---|---|---|
| J | Supportのみ今バーapply、Resistanceがclearされた後、`physBottom/physTop`・`originRootIds`に前バーResistance Rootが残らない | 末尾処理の 1)→2)→3)。`refreshCoreRange()`はLive Side Structureのみ参照、`rebuildCoreOrigins()`は`rebuildOriginIds()`（Live Side Structureのみ）から作り直す | 経路あり |
| K | Stale Sideにしか存在しなかったRootが、次バーのCore identity一致へ使われない | 同上。`clearLiveSide()`で`rootIds`が空になり、`rebuildOriginIds()`がそのRootを含めない。`candSharesOrigin()`は`originRootIds`のみ参照 | 経路あり |
| L | 同時刻・同Side・異なる接触RangeのEpisode 2件をMerge → TouchCount = 2 | `sameEpisode()`が接触範囲tickも比較するため別Episode。`markIsDuplicate()`は重複と判定せず両方保持、`rebuildSideHistory()`も2件として計上 | 経路あり |
| M | 同時刻・同Side・同一接触Rangeの重複Episode → TouchCount = 1 | `markIsDuplicate()`がMerge時に片方を捨て、仮に両方残っても`rebuildSideHistory()`の`sameEpisode()`重複判定で1件 | 経路あり |
| N | M=20で心理価格参加結果が改訂4と一致 | M=20では候補幅+2M ≤ 60 のため参加可能な心理価格は最大1本、生成される構成も最大1つで、改訂4が選んでいた「最も狭い構成」と同一範囲。**ただし**心理価格の拡張で新たにFVGが交差する構成は、改訂4では評価されず改訂5では評価されます（これが#3の修正点そのものです） | 経路あり・注記 |
| O | M=60等で同一候補周辺へ複数心理価格が存在する場合 | `psychVariants()`が下方向×上方向の全組合せを生成し、`scanBest()`が全て評価。CはPsychビット（32）の1ビットのみでPsychは1、Hは0のまま、`collectPsychRoots()`が採用範囲内の全心理RootをRoot一覧へ入れるためEffectiveRangeは実参加Rootを反映 | 経路あり |
| P | 片Sideだけ存在するMerge後Coreで、現在物理範囲外の古いTouch Episodeが残らない | `pruneMarksToRange()`の条件が`not na(c.physBottom)`。`physBottom`は末尾処理2)で常に再構築済み | 経路あり |
| Q | その後Splitしても、一度Coreから外れた無関係Episodeが復活しない | `splitCore()`は親の**現在の**`touchMarks`からのみ配分。pruneで外れたEpisodeは親配列から物理的に削除済みで、復元経路が存在しない | 経路あり |

### 改訂4からの確認ケース（A〜I）

| # | ケース | 結果 |
|---|---|---|
| A | Stage AでStrongにならなかったPoint RootがStage BでFVG内部局所Rootになる | 経路あり |
| B | Stage BでFVG局所Zoneへ使われた通常RootがStage Cで再利用されない | 経路あり |
| C | 心理価格が単独で候補列挙を開始しない | 経路あり（#3で更に強化：価格順配列に入らない） |
| D | 親に2 Episode、片方だけWeakDepth到達 → Split後、正しい子だけへ引き継ぐ | 経路あり |
| E | WeakByTouchの親をSplit、Touch 1件を引き継ぐ子 | 経路あり。親のフラグは継承せず子の実Episode数から再計算。`weakFromTouch = 2`で1件継承なら`UpcomingTouchNo = 2`となりWaiting / ArmedでWeak（仕様9.1・受入50どおり）。0件継承なら非Weak |
| F | 有効Rootを持つが今バー未照合のCoreが終了しない | 経路あり |
| G | Supportだけ更新、Resistanceの前バーLiveStructureが残らない | 経路あり（#1で物理範囲・Originまで完全化） |
| H | 重複区間外のPoint局所候補が異TF重複だけでFVG Highにならない | 経路あり |
| I | 5分足以外でEngineが実行されない | 経路あり |

---

## 3. 付録B 75ケースのコード単位監査（判定はすべて NOT RUN）

### A. 境界値

| # | 期待値 | 経路 |
|---:|---|---|
| 1 | 幅=Mちょうどで同一通常Zone可 | `scanBest`：`wTick > limitTick`で`break`、`limitTick = mTickLimit`なので等号は通過 |
| 2 | 幅=denseWidthちょうどでHigh Density | `completeCandidate`：`awT <= denseTickLimit ? 0 : 1` |
| 3 | ResetDistanceちょうどでReset/Armed | `activeEval` / `finalizeSide`：`tGe(f.c, top + touchResetDistance)` |
| 4 | WeakDepthちょうどでWeak | `activeEval`：`depth >= weakDepthPct` |
| 5 | Support CloseがBottom−BufferちょうどでBreak | `activeEval`：`tLe(f.c, bot - breakBuffer)` |
| 6 | Resistance CloseがTop＋BufferちょうどでBreak | `activeEval`：`tGe(f.c, top + breakBuffer)` |
| 7 | FVG CloseがDistal同値なら有効 | `markFvgInvalidation`：`tLt` / `tGt`の厳密比較のみ |
| 8 | WickがZone端と同値ならTouch | `armedEval`：`tGe(f.h, bot) and tLe(f.l, top)` |
| 9 | 一本線Tolerance 0の同値Touch | `armedEval`：`tLe(f.l, bot + tol) and tGe(f.h, bot - tol)` |

### B. MA

| # | 期待値 | 経路 |
|---:|---|---|
| 10 | EMA1本はNormal、C=1ならNeutral | `completeCandidate`：`maCnt == 2`不成立。C=1はBase Strong式でfalse |
| 11 | 2本Denseでも片方下向きならSupport MA Normal | `completeCandidate`：`side == 1 ? maUp == 2 : maDn == 2` |
| 12 | 2本Dense＋両方上向きでSupport MA High | 同上＋`denP == 0`＋`maGapTick <= denseTick`（EMA2本の価格差） |
| 13 | 同状態でResistance側はHighにならない | 同上（`maDn == 2`不成立） |
| 14 | MA High＋別カテゴリ、C=2、High DensityでBase Strong | `(cCnt == 2 and hCnt >= 1)` |
| 15 | EMA移動だけで世代/Fresh/Touch履歴をリセットしない | `ingestMa`は価格と`slopeDir`のみ更新。世代候補は新独立カテゴリ必須 |

### C. Swing / Accum / 時間高安

| # | 期待値 | 経路 |
|---:|---|---|
| 16 | PivotはConfirmedTime前にRoot化しない | `ingestSwing`：`highConfirmed <= baseCloseTime` |
| 17 | 同価格tick＋上位足区間内の5分＋15分は同一イベント | `swingIngestOne`：`subtype`一致＋tick一致＋`[originTime, originEndTime)`包含。`labelMask`へTFビット |
| 18 | 別時期の同価格Swingは別イベント | 区間包含不成立→新Root（`originKey`にoriginTimeとHigh/Lowを含む） |
| 19 | Accum Candidate中はRootなし・Touchなし | `accumPackV2`：`outNew`はtrue→false遷移のみ |
| 20 | true→falseのfalse足実体をBoxへ含めない | 終了足では範囲を更新せずに出力 |
| 21 | 同じAccum BoxのTop/BottomがM以内でも別Zone | `scanBest`：`sPairs`に`pairKey`既出なら`break`。整理も`pruneAccumBoxes`がBox単位 |
| 22 | 4時間Accum境界はAccum High | `scanBest`：`acHas4hD := r.tfCode >= 240` |
| 23 | 14:00足からEurope、19:00足からNY、03:00足からセッションなし | `sessionIdxOf`（足のopenTimeで判定、cutは入力可変） |
| 24 | 05:00足から新取引日 | `dayKeyTz`：`t - dayCutMin*60000` |
| 25 | 新極値足が自身をTouchしない | `updateTimeHL()`はステップE（Touch評価の後）。High/Lowは`subtype`で分離 |

### D. FVG

| # | 期待値 | 経路 |
|---:|---|---|
| 26 | BullishはSupportだけ、BearishはResistanceだけ | `fvgSideEligible`の4分岐 |
| 27 | 形成3本目確定前はRootなし | `ingestFvgNew`：`bullConfirmed <= baseCloseTime` |
| 28 | 確定後の最初のwick進入でFresh終了、Rootは存続 | `applyFvgState`：`fvgFresh := false`のみ |
| 29 | 元TF CloseがDistalを厳密に越えた時だけInvalidated | `markFvgInvalidation`：`tLt` / `tGt` |
| 30 | 構造無効化にBreakBufferを使わない | 式にbufferが現れない |
| 31 | 同方向・異TFの実重複は共通区間かつFVG High | `fvgStandalone`（共通区間＝`max(bot)`〜`min(top)`、`ovHigh`） / `fvgAugment`（`fvgOverlapCovers`） |
| 32 | 同方向でも非重複ならM以内だけで結合しない | 結合条件は`intersectsT`のみ |
| 33 | BullishとBearishは相互補強しない | `buildFvgSet` / `fvgOverlapCovers` / `fvgStandalone`すべて`sFvgDir`一致を要求 |
| 34 | FVG 50%を変えてもZone結果が変わらない | 50%の計算がコードに存在しない（表示機能も削除） |
| 35 | Broad単独はStrongにならない | `fvgStandalone`：`broadCtx`で`den = 2`、`candStrong = 0` |
| 36 | Broad＋有効局所化条件では局所部分だけStrong候補にできる | `fvgAugment` / `broadLocalizeOkAt`の4条件。範囲は点Root分布（内部）またはProximal edge〜分布 |

### E. 心理価格 / Strong

| # | 期待値 | 経路 |
|---:|---|---|
| 37 | 心理価格単独ではZoneなし | `collectPoints`が心理価格を列挙対象から除外。合成は既存候補に対してのみ |
| 38 | Major 100ドル位置にStandardを重複生成しない | `syncPsych`：levelごとに1Root、`lvl % 2 == 0`でMajor |
| 39 | 心理はCに数えるがHにならない | catMaskへPsychビット（32）を立てるのみ。`hMaskNoMa`に心理ビットは存在しない |
| 40 | C=1 HighでもBase Strongにならない | `(cCnt == 2 and hCnt >= 1) or cCnt >= 3` |
| 41 | C=2、High Density、H=0ならBase Strongにならない | 同式 |
| 42 | C=2、High Density、H>=1でBase Strong | 同式 |
| 43 | C>=3、High DensityでBase Strong | 同式 |
| 44 | Normal DensityではCが多くてもBase Strongにならない | `aden == 0`必須 |
| 45 | Dense Strong coreへ外側Rootを加えてNeutralへ落とさない | Stage A採用Rootは`sUsed`で再利用されず、Stage Cは残Rootのみ。FVG Proximal付加は`preDenseStrong`時にdense幅上限。心理価格合成も`limitTick`（Stage AではdenseWidth）以内のみ |

### F. Touch / Weak

| # | 期待値 | 経路 |
|---:|---|---|
| 46 | Root成立時に価格がZone内ならWaiting、成立足Touchなし | 新Coreは`phase = 0`。Armedは距離条件＋`armedFromSeq = seq+1` |
| 47 | 前足ArmedでないZoneはwick交差してもTouchなし | `ph == 1`かつ`armedFromSeq <= f.seq`かつ`sv.eligible`のViewのみ |
| 48 | 同一Episode内の複数往復はTouch 1回 | `activeEval`：Reset成立まで`phase = 2`、`currentTouchNo`固定 |
| 49 | 初期値ではBase StrongのTouch 1がStrong | `gradeOf`：`targetTouchNo <= strongUntilTouch` |
| 50 | Touch 1完了後、Upcoming Touch 2がWeak | `finalizeSide`：`upcomingTouchNo = 2 >= weakFromTouch` |
| 51 | Touch 1中にDepth 50%でCurrent Weak、TouchStartGradeはStrongのまま | `activeEval`：`h.weakByDepth`とEpisodeの`weakByDepth`を立て、`sn.touchStartGrade`は不変 |
| 52 | Reset後もWeakは維持 | Reset処理はWeakに触れない。解除は世代開始、またはMerge/Splitでそのsideへ属するEpisodeが0件になった場合のみ（仕様12.2/12.3） |
| 53 | 一本線ではWeakDepthを使わない | `activeEval`：`widthT > 0`のときのみ |

### G. Break / Flip / Reclaim

| # | 期待値 | 経路 |
|---:|---|---|
| 54 | Wick抜けだけではBreakしない | 条件は`f.c`のみ |
| 55 | Touch足でBreak：TouchCountは増えBreakがWeakより優先 | `startTouch` → `activeEval`。`brk`分岐でWeakDepthを評価しない |
| 56 | 完全GapBreakでTouchCount/WeakDepth/Freshを変えない | `armedEval`：非交差時に`applyBreak(gap = true)`のみ、`startTouch`を通らない |
| 57 | GapBreak足でFlip/Reclaimを同時確定しない | `processBreakState`：`bs.breakSeq != f.seq` |
| 58 | Reset距離を取る前の再接触はFlipConfirmにならない | `bs.movedAway`が先に必要 |
| 59 | FlipConfirm接触は通常Touchへ数えない | `TouchMark(isNormalTouch = false)`。`sideTouchCount`に触れず、Freshも消費しない |
| 60 | Flip後は別足で再度Resetしてから通常Touch 1 | `lastFlipConfirmSeq = f.seq` → 当該足Armed不可 → 次足以降にReset → `armedFromSeq = seq+1` |
| 61 | 過去に使ったSideへ再FlipでTouch/Weak履歴を復元 | Side別`SideHistory`が常駐。Flipは履歴を消さない |
| 62 | ReclaimでFresh/Weakをリセットしない | `bs.valid := false`とphase復帰のみ |
| 63 | EMA移動後もFlip/Reclaim基準がBreakSnapshotから動かない | 判定は`bs.rangeBottom/Top`のみ |
| 64 | FVG無効化とReclaim同時ならFVG無効化優先 | `markFvgInvalidation`を検出最前段で実行、`sideHasLiveNonPsych`が`pendingInvalidate`を除外 |
| 65 | InverseConfirmを通常Touchへ数えない | `updateFvgInverse`はEventのみ。`inverseConfirmSeq`で当該足のArmedも抑止 |

### H. Topology / 世代 / 再現性

| # | 期待値 | 経路 |
|---:|---|---|
| 66 | ActiveTouch中の新RootでTouchStartGradeを書き換えない | Snapshotは`array.copy()`で凍結。関係CoreがActiveTouchならMerge/Split/applyを行わず`pendingTopology` |
| 67 | ActiveTouch中のRoot失効後もOutcome記録は継続、新Signalには使わない | `activeEval`はSnapshot範囲で継続、`finalizeSide`が`eligible := sideHasLiveNonPsych()`で即時反映 |
| 68 | Mergeで同一接触を二重カウントしない | `sameEpisode()`（Side・時刻・接触範囲tick・種別）を`markIsDuplicate()`と`rebuildSideHistory()`の両方で使用。同時刻でも接触範囲が違えば別Touch |
| 69 | Splitで実際に触れていない子はFreshになれる | `splitCore`が`intersectsT`で配分、`rebuildCoreHistory`が通常Episodeのみで判定。`marksTruncated`時はFresh復活しない |
| 70 | 未タッチZoneへのRoot追加は同世代 | `updateGenerationCandidate`：`consumed`（Touch/Weak/Break/非Fresh）が必要 |
| 71 | 同カテゴリRoot追加・EMA移動・心理価格追加だけでは新世代にならない | `catMask`差分から心理ビット(32)を除去。同カテゴリは`catMask`を変えない |
| 72 | 新独立カテゴリ＋Base Strong＋Reset＋再接触でだけ新世代Touch 1 | `genCandidateReady` ＋ `genCandidateMovedAway` ＋ 接触足で`startGeneration()` |
| 73 | 新世代開始時のみ両SideのTouch/Weak/Freshをリセット | `startGeneration`が両Side履歴・`zoneFresh`・`breakSnap`・Episodeをリセットし、旧世代を`endedGen*`へ保存 |
| 74 | 同じ確定Feedを二度渡しても二重更新しない | `bf.openTime > e.lastBaseOpenTime` |
| 75 | reload後に同じデータでID/Phase/Grade/イベント列が再現 | ID採番は確定足順、価格順は同値でRoot ID整列、心理IDは価格level由来の固定値、比較は5段tie-break |

### M15 追加重点ケース

| ケース | 経路 |
|---|---|
| Root削除＋slot再利用 | `unregisterRoot`が`freeSlots`へ返却、`registerRoot`が再利用。論理IDは再利用しない（心理価格のみ価格由来の固定ID） |
| Merge後の後続照合再評価 | `mergeCores`後に`refreshCoreRange` / `rebuildOriginIds`が更新され、後続候補は更新後のCoreに対して照合 |
| 保存上限 直前／到達／超過 | `pruneStorage`：Core整理→保護集合再構築→Swing/FVG/Time整理→Accum Box整理 |
| 保護対象だけが残る | `coreProtected` / `rootProtected`が全て真なら`storageOverLimit = true`、削除しない |
| Accum片側保護 | `pruneAccumBoxes`が同一`pairKey`の全Rootの保護状態を確認してから両方を削除 |
| Touch履歴truncate | `trimTouchMarks`が`marksTruncated`（Core単位）と`touchHistoryTruncated`（診断）を設定、`rebuildSideHistory`がFresh復活を禁止 |
| scratch容量超過時のexact fallback | `SCRATCH_MAX_ROOTS`超過は`scratchOverflow`診断のみ。探索・候補は一切削らないため代替経路が不要 |
| リアルタイム／reload／Bar Replay同値 | 更新は`barstate.isconfirmed`かつ`openTime`単調増加の足のみ。描画は`varip`を使わず毎回再構成 |

---

## 4. 付録D 静的確認

### 4.1 存在してはいけない依存（コード全体検索＋処理経路確認）

| 対象 | 結果 | 確認方法 |
|---|---|---|
| Score閾値によるGrade | **0件** | `gradeOf()`はUnavailable→Weak→Strong→Neutralの4分岐のみ。score変数が存在しない |
| Reaction Bonus / Flip Bonus | **0件** | `flipAttemptCount` / `inverseAttemptCount`は保存のみで`gradeOf()`から参照されない |
| 加重平均CenterによるTouch/Break | **0件** | Touch/Breakは`lastArmedRange*`とSnapshotのみ参照 |
| FVG 50%ロジック | **0件** | 50%の計算がLibrary・Harnessとも存在しない（表示機能も削除） |
| ATRによるZone幅 / Break幅 / Reset距離 | **0件** | `ta.atr()`は`accumCondV2()`内の1箇所のみ |
| BOS | **0件** | 不在 |
| Strategy勝敗 | **0件** | Entry/Exit/PnLの型・関数が存在しない |
| HTF環境フィルター | **0件** | 上位足の上昇/下降/レンジ判定が存在しない |
| 中心±固定幅 | **0件** | 範囲は常に参加Rootの実価格分布／NativeRange／共通区間 |
| ReferencePriceのロジック利用 | **0件** | 代入は`computeRefPrice()` → `sv.referencePrice` → `ZoneView` → ラベルのみ。Dormantは`intervalGap(EffectiveRange, close)` |

### 4.2 存在必須（処理経路まで確認）

| 対象 | 経路 |
|---|---|
| tick正規化 | `toTick` / `tGe,tLe,tGt,tLt` / `intersectsT`。生floatでの境界比較は静的検索で**0件** |
| ConfirmedTime gate | `ingestSwing` / `ingestAccum` / `ingestFvgNew` / `markFvgInvalidation` / `applyFvgState` |
| 前足Armed gate | `armedEval`：`h.armedFromSeq <= f.seq`（`finalizeSide`が`seq + 1`を設定）＋`sv.eligible` |
| TouchStartSnapshot | `startTouch`で`array.copy(sv.rootIds)`ごと凍結 |
| BreakSnapshot | `applyBreak`で作成、Flip/Attempt/Reclaimはこの固定範囲のみ参照 |
| Side別履歴 | `SideViewState.history`をSupport/Resistanceで別インスタンス |
| Weak永続 | `startGeneration`、およびMerge/Splitでそのsideへ属するEpisodeが0件になった場合（仕様12.2/12.3）以外では解除されない |
| FVG方向filter | `fvgSideEligible` |
| PendingTopology | `associateCandidates`のActiveTouch分岐でmerge/split/applyを抑止 |
| 新世代の新カテゴリ条件 | `updateGenerationCandidate`：`catMask`差分から心理ビット除去、Base Strong、Reset離脱、再接近で`startTouch`冒頭切替 |
| 決定論tie-break | `collectPoints`の同値区間Root ID整列 ＋ `scanBest`の5段比較 |
| duplicate base guard | `update`：`bf.openTime > e.lastBaseOpenTime` |

### 4.3 機械実行した静的検査

| 検査 | 結果 |
|---|---|
| 行継続インデント（括弧継続・演算子継続がPineの規則を満たす） | 違反0件 |
| 降順ループのゼロ件ガード | 違反0件 |
| 関数の前方参照 | 0件 |
| 呼び出し先未定義 | 0件 |
| UDTフィールド名の突合 | 0件 |
| 未使用のローカル関数 | 0件 |
| Library内の`request.*`呼び出し | 0件 |
| Harnessが使う`ze.*`のexport存在 | 全件存在 |
| 生float境界比較の残存 | 0件 |

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

実ソースを機械的に数えた値です。条件分岐内の追加`request`はありません。コンパイル確認ではありません。

---

## 6. 検証状況（NOT RUN一覧）

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

静的にコードを直したことと、実機で仕様適合を確認したことは別です。

---

## 7. 計算構造

### 7.1 キャッシュ（キー／失効／容量／fallback／所有）

| 対象 | キー | 失効条件 | 容量 | 容量超過時 | 所有 |
|---|---|---|---|---|---|
| `idToSlot` | Root ID | 登録／削除 | 生存Root数 | なし | Engine |
| `originToId` | 起源キー | 登録／削除 | 生存Root数 | なし | Engine |
| `ownerOfRoot` | Root ID | 毎足`map.clear()` | 当該足の参加Root数 | なし | Engine |
| `idxCat*` | カテゴリ | 登録／削除 | 生存Root数 | なし | Engine |
| `sLot*`（価格順） | なし（毎足再構築） | 毎足 | 生存点Root数 | 打切りなし。`scratchOverflow`診断のみ | Engine |
| `sFvg*`（Side別FVG集合） | Side | Side切替ごとに再構築 | 当該Sideの適格FVG数 | なし | Engine |
| `sPsyBot` / `sPsyTop`（心理価格構成） | なし（窓ごとに再構築） | 窓ごと | 下方向×上方向の組合せ数 | なし | Engine |
| `cand*`（採用候補） | なし（毎足再構築） | 毎足 | 候補数 | なし | Engine |
| Feed重複排除 | 元足closeTime／originTime | 新しい元足 | 各1 | なし | Engine |
| 設定検証 | なし（毎確定足実行） | 毎足 | - | - | Engine |

足をまたぐ候補キャッシュは実装していません。

### 7.2 計算量

| 処理 | 本実装 | 単純計算との差 |
|---|---|---|
| 価格順構築 | `O(R log R)`＋同値区間のみ挿入整列 | 毎足の全比較ソートを回避 |
| 候補探索 | 開始位置ごとに窓内本数k、1窓につき「心理なし」＋心理構成数（M=20で最大1、M=60でも数個） → `O(R·k)`／ラウンド | 窓ごとに窓内全Rootを引き直す`O(R·k²)`を回避（カテゴリ・品質要約を増分更新） |
| FVG局所化 | 窓あたり`O(F)`、Broad条件2と非Broad Highの空間判定のみ`O(F)`追加 | 全FVG×全候補の品質判定を回避 |
| Root検索 | ID→slot / 起源→ID / カテゴリ→slot集合 | 全件線形探索を回避 |
| Core照合 | 範囲gapの安価判定→一致候補のみ起源突合 | 全Core×全Candidateの重い照合を回避 |
| 履歴再構築 | Merge / Split時のみ、Episode数に比例 | 毎足の履歴再計算を回避 |
| Reference | 採用候補のみ1回 | 落選候補の中央値計算をゼロに |
| 元足取得 | 5コンテキスト・84要素 | カテゴリ／時間足ごとの個別requestを回避 |
| 保存整理 | 上限超過時のみ。保護集合は整理1回につき1度構築 | 削除ごとの保護再構築を回避 |

**隠れた線形処理**：`liveOrder`の挿入は二分探索で位置を決めますが要素移動は線形です。
`array.insert` / `array.remove`（category index、cores、originRootIds、touchMarks）も線形です。
`markIsDuplicate()`はMerge時にEpisode数に比例します。

---

## 8. Visual Harness（付録C）

### Label（`viewLabelText()`）

CoreID / GenerationID / Side、Phase | Grade、Range / Reference、C / H / Density（＋BaseStrong）、
Current または Upcoming Touch、WeakReason / MaxDepth、ZoneFresh / SideFresh、
FVG direction / Fresh count / state（＋BROAD CONTEXT）、Category summary（Highは`(H)`）、Root summary。

### Debug table（18行）

build ID / config validation / 最終Base足時刻＋seq / 採用した1m MA元足時刻 /
採用したFVG元足時刻（1H・4H・日）/ 採用したAccum確定時刻（1H・4H・日）/
Root数 / Candidate数 / Core数・View数 / **Zone 0件の理由** /
PendingTopology・PendingGeneration・deferred数 / Merge・Split・照合数 /
窓評価数・Denseラウンド数 / prune（TOUCH-TRUNC / OVER-LIMIT / SCRATCH）/
終了世代数 / MA傾き / session・day・week ID / 当該足Event列。

Zone 0件の切り分け：`config invalid` → `engine never updated` → `engine updated, 0 roots` →
`engine updated, roots present, 0 candidates` → `candidates present, 0 cores` → `cores present, 0 views`。

### 禁止事項

`strategy()`宣言なし、Entry/Exitなし、勝敗集計なし、環境認識フィルターなし、
Zone選択を1件へ絞る処理なし（距離順は表示順のみ、Engineは全Viewを返す）。
FVG 50%表示は削除済み。5分足以外では`runtime.error()`でEngineを実行しない。

### 可変な時間設定

`zoneTimezone` / Asia開始 / Europe開始 / NY開始・終了 / dayCut / weekCut をHarness入力から`ZoneCfg`へ反映。
Debug表の時刻も同じ`i_tz`で表示します。

---

## 9. TradingViewでの次工程

1. `ZoneEngineV2_Rebuild.pine` を **Add to chart** でコンパイル確認（エラーは行番号とメッセージを共有）。
2. **Publish library** → 発行された `<username>/ZoneEngineV2_Rebuild/<version>` を控える。
3. Harnessの `import YOUR_TV_USERNAME/ZoneEngineV2_Rebuild/1` を実番号へ置換。
4. **XAUUSD 5分足**へHarnessを追加。Debug表の`build`が`ZEV2R-20260919-005`であることを確認
   （5分足以外ではruntime errorになります）。
5. 通常実行の完走可否 → 別実行でProfiler。
6. 計測条件を記録：ticker ID、時間足、セッション、履歴開始/終了と本数、全パラメータ、
   Library公開番号、build ID、TradingViewが表示する実行制限。
7. 付録B 75ケース・M15重点ケース・本書2章のA〜IをBar Replayで確認し、本書へPASS/FAIL/NOT RUNを追記。

---

## 10. まとめ

- Zone定義v2の論理は変更していません。改訂5は既存契約へ合わせる静的修正4件のみです。
- **仕様上の未解決事項0件 / 実装上の暫定処理0件 / 結果へ影響する独自解釈0件。**
- Zone判定結果へ影響しない実装決定は、Split子のGeneration ID継承（履歴リセットなし・表示のみ、
  全Cfg範囲で不変）の1件だけです。心理価格の1本選択は設定依存だったため廃止しました。
- 実機適合性・実行時間・描画・再現性はすべて未検証（`NOT RUN`）です。
- 次は追加設計修正ではなく、9章の手順によるTradingView実機検証へ進みます。

---

## 11. 改訂履歴（実装状態の由来）

| 改訂 | Build ID | 主な内容 |
|---|---|---|
| 1 | -001 | 仕様v2の新規実装（Library / Harness / Report）。Accum形成条件式は正本欠落のため仮置きし、隔離して報告 |
| 2 | -002 | 付録A 7.4のAccum形成式を正本として一致（実体端レンジ、単一rangeMid、実体中点ドリフト、bull/bear別ラン、条件別ガード）。CandidateはrangeHigh/rangeLowを共有。Broad保護をBase Strong候補へ限定 |
| 3 | -003 | 全34項目の静的監査：段階Aの完成候補評価、Broad局所化4条件、Bullish/Bearish非補強、ActiveTouch中のMerge/Split遅延、Merge履歴再構築、Flip/Inverse後の再Armed抑止、Broad context同一性、心理価格の安定ID、保存整理の優先順とBox単位Accum、毎足validate、起源タグ衝突、全比較のtick正規化、Debug/表示の完成 |
| 4 | -004 | 段階Bの完成（残Point Rootへの局所化）、心理価格を候補列挙Rootから除外、Touch Episode単位の履歴、Zone lifetimeを仕様14へ、Stale Side Structureの失効、非BroadのFVG重複Highの空間結合、FVG 50%表示の削除、Harnessの5分足強制、Debug timezone、段階表記の統一 |
| 5 | -005 | 本書1章の4項目：Core物理範囲/Originの無条件再構築、Episode dedupeキーの統一、心理価格構成の全評価、片Side Coreでも有効なEpisode prune |

各改訂の差分はgit履歴（ブランチ `claude/new-session-vss3r2`）に保存されています。
