# ZoneEngineV2_Rebuild 実装レポート

作成日：2026-09-19（改訂6：静的最終版）
Build ID：**`ZEV2R-20260919-006`**（Library / Visual Harness / 本書で共通）
対象：XAUUSD / 確定5分足 / Pine Script v6
正本：`Zone_definition_spec_v2.md` 全21節 ＋ 軽量化実装指示書 M0〜M19 ＋ 付録A〜D

**静的実装完成。正本に対する既知の静的不一致0。実機適合性は未検証。**

---

## 0. 静的監査の最終状態

| 区分 | 件数 |
|---|---:|
| 仕様上の未解決事項 | **0件** |
| 実装上の既知の暫定処理 | **0件** |
| 結果へ影響する独自解釈 | **0件** |
| **Core associationのCandidate処理順依存** | **0件** |

### Zone判定結果へ影響しない実装決定（全Cfg範囲で不変なもののみ）

- **Split子CoreのGeneration ID**：親のGeneration IDを継承します。Splitは新Zone世代ではないため
  （仕様18のリセット条件を満たさない）、新IDを振ると「新世代開始」と矛盾します。
  Touch / Weak / Fresh のリセットは行いません。影響は表示されるGeneration IDのみで、
  いずれの設定値でもZone判定（Phase / Grade / C / H / Density / Touch / Break / Flip / 世代）は変わりません。

---

## 1. 改訂6の修正

### A. Core Associationの完全な順序非依存化

**変更前の問題**：Candidate単位の逐次処理で、Candidate 1のapplyが旧Core状態
（`originRootIds`・範囲）を変えてからCandidate 2を照合していました。
旧Core origins=[R1,R2]／今バーCandidate X=[R1], Y=[R2] のとき、
Xを先にapplyするとCore originが[R1]へ変わり、Yが一致しなくなって新規Core化する、
という処理順依存が起こり得ました。

**変更後の処理**：`associateCandidates()`を7フェーズへ分離しました。
**Phase 1〜4はLive Coreを一切読み書きしません。**

| Phase | 内容 | 実装 |
|---|---|---|
| 1 | 全Live Coreの不変Snapshot（Core ID / Generation / 前バーorigin / 前バーphysBottom・physTop / Broad Contextか / ActiveTouch有無）。association完了まで変更しない | `snapshotCores()` → `snapCoreIdx` / `snapOriginStart` / `snapOriginLen` / `snapOrigins` / `snapBot` / `snapTop` / `snapBroadCtx` / `snapActive` |
| 2 | 全Candidate × 全旧Core Snapshotのmatchだけを作る（正本12.1：同一性に使えるRoot IDを1つ以上共有＋前回範囲との連続性がM以内）。apply / merge / split / 削除 / origin更新は一切しない | `candMatchesSnap()`。Broad FVG originだけでは局所Zone同一性にならず、Broad standalone contextはBroad originで継続追跡（`candIsBroadContext()` と `snapBroadCtx` の一致を要求） |
| 3 | Candidate ∪ Snapshot の二部グラフをunion-findでconnected componentへ分類。Candidate同士も、非Broad起源共有かつM以内なら同一component（仕様10.7の「Support候補とResistance候補を同じCoreへ」） | `ufFind()` / `ufUnion()` / `candSharesWithCand()` |
| 4 | componentにActiveTouch Coreが1つでもあれば、そのcomponentのMerge / Split / Live Structure変更 / Root ownership移動を**一切行わず**PendingTopologyとして保持 | `anyActive`分岐。TouchStartSnapshotは固定、Root失効による`eligible=false`だけは`finalizeSide()`で即時反映 |
| 5 | 決定済みTopologyを初めてLive Coreへ適用 | 下記 |
| 6 | Root ownershipを1回だけ確定 → 各Coreの範囲・originを再構築 | 下記 B |
| 7 | Zone lifetime（仕様14） | 有効非心理Root・待機Root・待機状態がすべて0のときだけ終了 |

**決定論的な処理順**：

- component の処理順＝「component内の最小旧Core ID昇順」。旧Coreを含まないcomponentは
  そのcomponentの最良Candidate（正本競合順）で順序付け。
- component内のSnapshotは旧Core ID昇順、Candidateは**正本競合順**
  （C降順 → H降順 → Effective幅昇順 → 成立時刻昇順 → Root ID昇順）。
  `candFormTime` / `candMinId` を採用時に確定して`candBetter()`で比較します。
  最小Root IDまで比較するため、異なるCandidate同士が完全同値になることはありません
  （バッファ添字は到達不能な最終tie-breakとしてのみ存在）。

**Phase 5の適用規則**：

- **Merge**：component内の旧Coreを最小Core IDへ集約（`mergeCoreInto()`）。
  Episodeを一度集約してからdedupe、`startSeq`順へ整列、Episode単位でtrim。
- **Slot割当**：1 slot = 1物理Core。Candidateを正本競合順に見て、
  「そのSideが空いていて、かつ反対Sideに既に入っているCandidateと非Broad起源を共有しM以内」
  の最初のslotへ入れる。入らなければ新slot（＝Split子）。
  これによりSupport/Resistanceの2 Viewは1 Coreへ、同Sideの複数Candidateは別Coreへ、
  いずれも順序非依存で決まります。
- **1対1**：slot 0が旧Core（Core ID維持）。
- **Split**：slot 1以降が子Core。親のGeneration IDを継承。
- **新規**：どの旧CoreともmatchしないCandidateだけが新Coreになります。

### B. Root ownershipをTopology適用後に一括確定

`ownerOfRoot`はCandidate処理途中で更新しません。Phase 6で、
死んだCoreを除去したうえでCore ID昇順に走査し、非Broad Rootについて
Root ID → 最終Core ID を1回だけ確定します。
既に他Coreが所有している非Broad Rootは、そのSideの`rootIds`から除去し
`statOwnerConflict`へ計上します（Phase 3のcandidate–candidate辺により本来発生しません）。
Broad FVGだけが複数局所Zoneへ共有されます。

その後、各Coreで
「applyされなかったSide（ActiveTouch中を除く）を`clearLiveSide()`」→
`refreshCoreRange()`→`rebuildCoreOrigins()`の順に実行します。
`rebuildCoreOrigins()`はLive Side Structureからoriginを作り直したうえで、
**このCoreがまだ所有するInverseWait Root**をwaiting originとして戻すため、
`ownerOfRoot`と矛盾せず、他Core所有の非Broad RootがSide rootIdsにもoriginにも残りません。

### C. 心理価格Rootの同Side ownership

Psych Rootは通常Rootです（Broad FVGではありません）。Sideごとに`sPsyUsed`（使用済みlevel集合）を持ち、

- `psychVariants()`：`psychLevelFree()`が偽のlevelを構成候補から除外。
- `collectPsychRoots()`：使用済みlevelを返さず、採用したlevelを`sPsyUsed`へ追加。
- Stage A次ラウンド・Stage B・Stage Cはすべて同じ`sPsyUsed`を見るため、再利用されません。
- `buildCandidates()`がSide切替時に`sPsyUsed`をクリアするので、
  Supportで使用済みでもResistanceでは独立に評価されます。
- 競合でPsychを失った候補は、次ラウンドの`scanBest()`がPsychなしの構成として再評価します。

### D. Touch Episodeの実接触履歴

`TouchMark`を廃止し、`TouchEpisode` ＋ `ContactSpan`へ置き換えました（旧経路は残していません）。

```text
TouchEpisode : episodeId / side / startSeq / startTime / generationId / touchNo
               snapBottom / snapTop / closeAtTouch / deepestClose / maxDepthPct
               weakByDepth / isNormalTouch / spans[]
ContactSpan  : baseSeq / time / bottom / top
```

- ActiveTouch中の各確定5分足で、High/LowがTouchStartSnapshot範囲と交差したら
  `contactBottom = max(low, snapBottom)` / `contactTop = min(high, snapTop)` を
  `addContactSpan()`でEpisodeへ追加（同じ足・同じ範囲はdedupe）。
- Episodeは Reset / Break まで同一。所属判定は`episodeTouchesRange()`が
  **いずれかのContactSpanと交差するか**で行い、Episode全体のmin〜max envelopeは使いません。
- Split時：ContactSpanが子範囲と交差したEpisodeだけを子へ配分。
  同じEpisodeが2子へ実接触していれば**両方へ配分**します（Root二重参加禁止とは別）。
- Merge時：`sameEpisodeKey()`（episodeId一致、または Side＋startTime＋startSeq＋touchNo＋
  Generation＋TouchStartSnapshot範囲tick＋通常/非通常）でdedupe。
  「同じ5分足だった」だけでは統合しません。
- WeakByDepth / maxDepthPct はEpisode単位で保持し、履歴再構築はEpisode集合から行います。

### E. truncateをEpisode単位に

`maxTouchMarksPerCore`は「保存するTouch Episode履歴上限」です。`trimEpisodes()`が
**Episode単位で**古いものから削除し、ContactSpanの部分削除による不完全Episodeを作りません。
truncate後は`marksTruncated`（Core単位）により、TouchCountを減らさない／Weakを解除しない／
Freshへ戻さない、を維持し、Split子へ継承します。

### F. Split履歴配分

Split開始前に親CoreのEpisode集合を`episodeSnap`へ完全Snapshotし、
**全子が同じSnapshotから**`assignEpisodesFromSnapshot()`で配分します。
子1へ配ったことで親配列から消えて子2へ届かない経路は存在しません。
順序は「全子作成 → 各子へContactSpan交差で配分 → 各子で`rebuildCoreHistory()` →
最後に親側のprune/再構築」です。Split自体ではTouchCount / Weak / Fresh のリセットも
新Generation開始も行わず、その子へ実配分された履歴だけから再構築します
（truncate時のみ保守的継承）。

### G. Merge履歴配分

Merge対象の全旧CoreのEpisodeを一度集約 → dedupe → `startSeq`整列 → trim。
その後、Merge後EffectiveRangeへ一度も接触していないEpisodeを`pruneEpisodesToRange()`で除外し、
残Episodeから Support / Resistance 別に
SideTouchCount / UpcomingTouchNo / WeakByTouch / WeakByDepth / MaxDepth / SideFresh / ZoneFresh を
`rebuildSideHistory()` / `rebuildCoreHistory()`で再構築します。
親の集約値の単純max / ORを最終結果にはしません
（`mergeCoreInto()`が残すmax / ORは、truncate時の保守的な下限としてのみ機能します）。

### I. それ以外は未変更

A→B→C候補生成順、Broad局所化4条件、Dense Strong保護、FVG方向とSide資格の分離、
異TF同方向FVG実重複、心理価格は候補開始Rootではない、ReferencePriceのロジック不使用、
ConfirmedTime gate、TouchStartSnapshot、BreakSnapshot、前足Armed gate、
FlipConfirm / InverseConfirm同足再Armed禁止、Fresh / Weakルール、Zone lifetime、
Config validation、tick正規化、5分Harness限定、request 5件 / tuple 84要素、
FVG 50%完全不使用、保存上限保護、Accum Box pair整理、Generation条件 — いずれも変更していません。

---

## 2. 追加静的監査（ケースR1〜R10）

| # | ケース | 経路 | 結果 |
|---|---|---|---|
| R1 | 旧Core origins=[A,B]、Candidate X=[A] / Y=[B] → Splitとして処理。X→Y / Y→X で同じ最終結果 | 両Candidateが同じSnapshotとunion（Phase 2/3）。slot割当はバッファ順ではなく`candBetter()`の正本競合順で行い、同Sideは別slot＝Split。最小Root IDまで比較するため完全同値は起こらない | 経路あり |
| R2 | 旧Core1=[A] / 旧Core2=[B]、Candidate=[A,B] → Merge | 1 Candidateが2 Snapshotとunion → 同一component、`cs = 2` → `mergeCoreInto()`で最小Core IDへ集約 | 経路あり |
| R3 | 旧Core1=[A,B] / 旧Core2=[C]、Candidate X=[A] / Y=[B,C] → connected componentとして順序非依存に解決 | X–Core1、Y–Core1、Y–Core2 の辺で1 component。Merge（Core2→Core1）→ slot割当（競合順）→ slot1がSplit子 | 経路あり |
| R4 | 上記componentにActiveTouch Coreあり → Topology即時変更なし | `anyActive`分岐でmerge / split / apply / ownership移動を行わず、component内の全旧Coreへ`pendingTopology = true`、`statDeferred`計上 | 経路あり |
| R5 | 同一Psych 4500が2候補へ参加可能 → 競合で採用された片方だけ所有、もう片方はPsychなしで再評価 | `sPsyUsed`（Side別）。採用時に`collectPsychRoots()`がlevelをusedにし、次ラウンドの`psychVariants()` / `collectPsychRoots()`が除外。Psychを失った候補はPsychなし構成として再評価 | 経路あり |
| R6 | Broad FVG → 複数局所Zone共有可能 | `adoptWindow()`はBroadを`sFvgLocal`にするだけで`sFvgUsed`にしない。Phase 6のownershipもBroadを除外 | 経路あり |
| R7 | Episode開始足はZone上部のみ接触、途中で下部にも接触 → Split後、上下両子へEpisode履歴を配分 | ContactSpanが足ごとに積まれ、`episodeTouchesRange()`が各子範囲に対して個別に交差判定。両子で真なら両方へ配分 | 経路あり |
| R8 | Episode中に100〜102と108〜110だけ接触 → 子103〜107には配らない | 判定はContactSpan単位。min〜max envelope（100〜110）は使用しない | 経路あり |
| R9 | 同じEpisodeをMerge元2Coreが保持 → 1回。異なるEpisodeが同じ5分足に存在 → 2回 | `sameEpisodeKey()`がepisodeIdまたは Side＋startTime＋startSeq＋touchNo＋Generation＋Snapshot範囲で判定。同じ足でもtouchNoやSnapshot範囲が違えば別Episode | 経路あり |
| R10 | Candidate配列順を逆転しても Core ID / Generation ID / Root ownership / Touch履歴 / Phase / Grade / イベント列が一致 | Phase 1〜4がLive Coreを読み書きしない。component順は最小旧Core ID、component内は`candBetter()`の正本競合順。ownershipはPhase 6で一括。Core ID採番はcomponent順とslot順にのみ依存 | 経路あり |

### 改訂4〜5からの確認ケース（A〜I / J〜Q）

A〜I、J〜Q の全ケースは改訂6でも同じ経路で成立します。
特にJ・K（Stale Side後の物理範囲・Origin）はPhase 6で無条件に再構築、
P・Q（片Side CoreのEpisode prune / Split後の無関係履歴復活なし）は
`pruneEpisodesToRange()`と`episodeSnap`方式で維持しています。

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
| 68 | Mergeで同一接触を二重カウントしない | `sameEpisodeKey()`（episodeId、または Side＋startTime＋startSeq＋touchNo＋Generation＋Snapshot範囲）を`episodeIsDuplicate()`と`rebuildSideHistory()`の両方で使用 |
| 69 | Splitで実際に触れていない子はFreshになれる | `assignEpisodesFromSnapshot()`がContactSpan交差で配分、`rebuildCoreHistory()`が通常Episodeのみで判定。`marksTruncated`時はFresh復活しない |
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
| Merge後の後続照合再評価 | 照合はPhase 2でSnapshotに対してのみ行われるため、Merge結果が後続照合へ影響しない（順序非依存） |
| 保存上限 直前／到達／超過 | `pruneStorage`：Core整理→保護集合再構築→Swing/FVG/Time整理→Accum Box整理 |
| 保護対象だけが残る | `coreProtected` / `rootProtected`が全て真なら`storageOverLimit = true`、削除しない |
| Accum片側保護 | `pruneAccumBoxes`が同一`pairKey`の全Rootの保護状態を確認してから両方を削除 |
| Touch履歴truncate | `trimEpisodes()`がEpisode単位で削除し`marksTruncated`（Core単位）と`touchHistoryTruncated`（診断）を設定、`rebuildSideHistory()`がFresh復活を禁止 |
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
| `sPsyUsed`（Side別Psych所有） | Side | Side切替でクリア | 当該Sideの採用level数 | なし | Engine |
| `snap*` / `edge*` / `uf*` / `comp*` / `slot*` / `episodeSnap` | なし（毎足再構築） | association開始時 | Core数＋Candidate数 | なし | Engine |
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
4. **XAUUSD 5分足**へHarnessを追加。Debug表の`build`が`ZEV2R-20260919-006`であることを確認
   （5分足以外ではruntime errorになります）。
5. 通常実行の完走可否 → 別実行でProfiler。
6. 計測条件を記録：ticker ID、時間足、セッション、履歴開始/終了と本数、全パラメータ、
   Library公開番号、build ID、TradingViewが表示する実行制限。
7. 付録B 75ケース・M15重点ケース・本書2章のA〜IをBar Replayで確認し、本書へPASS/FAIL/NOT RUNを追記。

---

## 10. まとめ

- Zone定義v2の論理は変更していません。
- **静的実装完成。正本に対する既知の静的不一致0。実機適合性は未検証。**
- 仕様上の未解決事項0件 / 実装上の暫定処理0件 / 結果へ影響する独自解釈0件 /
  Core associationのCandidate処理順依存0件。
- Zone判定結果へ影響しない実装決定は、Split子のGeneration ID継承（履歴リセットなし・表示のみ、
  全Cfg範囲で不変）の1件だけです。
- 次はTradingView実機検証（9章の手順）です。

## 11. 改訂履歴（実装状態の由来）

| 改訂 | Build ID | 主な内容 |
|---|---|---|
| 1 | -001 | 仕様v2の新規実装（Library / Harness / Report）。Accum形成条件式は正本欠落のため仮置きし、隔離して報告 |
| 2 | -002 | 付録A 7.4のAccum形成式を正本として一致（実体端レンジ、単一rangeMid、実体中点ドリフト、bull/bear別ラン、条件別ガード）。CandidateはrangeHigh/rangeLowを共有。Broad保護をBase Strong候補へ限定 |
| 3 | -003 | 全34項目の静的監査：段階Aの完成候補評価、Broad局所化4条件、Bullish/Bearish非補強、ActiveTouch中のMerge/Split遅延、Merge履歴再構築、Flip/Inverse後の再Armed抑止、Broad context同一性、心理価格の安定ID、保存整理の優先順とBox単位Accum、毎足validate、起源タグ衝突、全比較のtick正規化、Debug/表示の完成 |
| 4 | -004 | 段階Bの完成（残Point Rootへの局所化）、心理価格を候補列挙Rootから除外、Touch Episode単位の履歴、Zone lifetimeを仕様14へ、Stale Side Structureの失効、非BroadのFVG重複Highの空間結合、FVG 50%表示の削除、Harnessの5分足強制、Debug timezone、段階表記の統一 |
| 5 | -005 | Core物理範囲/Originの無条件再構築、Episode dedupeキーの統一、心理価格構成の全評価、片Side Coreでも有効なEpisode prune |
| 6 | -006 | Core associationの7フェーズ化（順序非依存）、Root ownershipの一括確定、Psychの同Side ownership、TouchEpisode + ContactSpanによる実接触履歴、Episode単位truncate、Split/Merge履歴配分 |

各改訂の差分はgit履歴（ブランチ `claude/new-session-vss3r2`）に保存されています。
