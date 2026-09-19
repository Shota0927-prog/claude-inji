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
| 4 | componentにActiveTouch Coreが1つでもあれば、そのcomponentのMerge / Split / Live Structure変更 / Root ownership移動を**一切行わず**PendingTopologyとして保持 | `anyActive`分岐。TouchStartSnapshotは固定、Root失効による`eligible=false`だけは`finalizeSide()`で即時反映。**Phase 6でも`pendingTopology`のCoreは凍結**（6章参照） |
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
死んだCoreを除去したうえで次の順に1回だけ確定します。

1. **PendingTopology Coreの非Broad Rootを先に登録**する。これらのRootは他Coreへ移動しない。
2. PendingTopology以外のCoreだけが通常の最終ownership確定を行う。既に他Coreが所有している
   非Broad Rootは、その（非Pending）Sideの`rootIds`から除去する。所有者がPendingTopology Coreなら
   `statPendingHold`、そうでなければ`statOwnerConflict`へ計上する
   （後者はPhase 3のcandidate–candidate辺により本来発生しません）。
3. Broad FVGだけが複数局所Zoneへ共有される。

**PendingTopology CoreはPhase 6で一切変更しません。**
`clearLiveSide()`せず、Support / Resistanceの`rootIds`・EffectiveRange・`physBottom` /
`physTop`・`originRootIds`をTopology都合で変更せず、所有Rootも他Coreへ移しません。
`rootIds`からownership conflictを理由にRootを除去することもありません。
TouchStartSnapshotは従来どおり固定で、Root自体の状態失効に伴う`eligible = false`だけは
`finalizeSide()`が即時反映します。

PendingTopology以外のCoreについては、
「applyされなかったSide（ActiveTouch中を除く）を`clearLiveSide()`」→
`refreshCoreRange()`→`rebuildCoreOrigins()`の順に実行します。

Pendingの解除は状態を持ち越しません。`update()`が毎足の冒頭で`pendingTopology := false`へ戻し、
ActiveTouch終了後の再クラスタでcomponent内のActiveTouchが0になった時点で、
**その足の最新Candidate**を使って通常どおりTopologyを解決します（古いPending Candidateは保存しません）。
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
| R4 | 上記componentにActiveTouch Coreあり → Topology即時変更なし | `anyActive`分岐でmerge / split / apply / ownership移動を行わず、component内の全旧Coreへ`pendingTopology = true`、`statDeferred`計上。Phase 6も`pendingTopology`のCoreを完全に凍結（clearLiveSideなし・範囲/origin再構築なし・Root移動なし） | 経路あり |
| R4b | 旧Core：Support = ActiveTouch、Resistance = 有効Live Structure。今バー新RootでSplit候補発生 | `pendingTopology = true`、Support / Resistance 両方のLive Structureを維持、Root ownership維持、Merge / Splitなし。Episode終了後の次の再クラスタで最新CandidateからTopologyを解決 | 経路あり |
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
| RE10110（実行時間超過）の解消 | **NOT RUN** |
| 実チャート実行（XAUUSD 5分足） | **NOT RUN** |
| Profiler | **NOT RUN** |
| Runtime < 40 sec | **NOT RUN** |
| 付録B 75ケース | **全件 NOT RUN** |
| M15重点ケース | **全件 NOT RUN** |
| Bar Replay | **NOT RUN** |
| reload一致 | **NOT RUN** |
| リアルタイム足一致 | **NOT RUN** |
| 保存上限の到達・超過テスト | **NOT RUN** |

静的にコードを直したことと、実機で仕様適合を確認したことは別です。

### 6.1 コンパイルエラー修正（2026-09-19）

TradingViewでの実コンパイルで2件のエラーが出ました。

1. `Error at 221:16 no viable alternative at character "&"` — Pine v6に `&` 演算子がない
2. `Error at 136:21 Mismatched input "and" expecting "set ID"` — Pine v6に `bitwise.and()` も存在しない

Pine Script v6にはビット演算子（`&` `|` `<<` `>>`）もビット演算関数（`bitwise.*`）も存在しないため、
ビットマスク処理を**算術方式へ完全統一**しました（Build IDは `ZEV2R-20260919-006` のまま据え置き）。

#### helper（Library内部、非export、セクション2冒頭）

```pine
maskHas(int mask, int bit) =>
    int(math.floor(mask / bit)) % 2 == 1

maskSet(int mask, int bit) =>
    maskHas(mask, bit) ? mask : mask + bit

bitPow2(int n) =>
    int v = 1
    if n > 0
        for i = 1 to n
            v *= 2
    v
```

`maskOr` は定義していません。本Engineのビット結合はすべて右辺が単一bit（1/2/4/8/16/32 または `bitPow2(n)`）であり、
`maskSet` で完全に足ります。使用されないhelperを残さないため省略しました。
`bitwise.and()` を使う旧helper `bitOr()` は削除済みです。

#### 置換内容

| 旧表記 | 新表記 | 箇所数 |
|---|---|---|
| `(mask & bit) != 0` | `maskHas(mask, bit)` | 18 |
| `(mask & bit) == 0` | `not maskHas(mask, bit)` | 1 |
| `mask \| bit` | `maskSet(mask, bit)` | 14 |
| `(1 << n)` | `bitPow2(n)` | 7 |
| `m - (m & 16)`（単一bitクリア） | `maskHas(m, 16) ? m - 16 : m` | 2 |
| `(m & 56) != 0`（複合bitテスト） | `maskHas(m,8) or maskHas(m,16) or maskHas(m,32)` | 1 |
| `catMask - (catMask & baseline)` からさらに bit32 を除去（複合AND-NOT） | bit 0〜5 の明示ループ（`maskHas` + `maskSet`） | 1 |

#### 対象マスク（全件確認済み）

FVG state mask / FVG direction mask / category mask / high mask / label mask（Time H/L）/
Swing TF mask / Accum TF mask / candidate cat・high mask / Generation category mask。
いずれも使用bitは 1 / 2 / 4 / 8 / 16 / 32 のみ（最大bit index 5）で、負値を取りません。

#### 値同一性の確認

mask 0〜63 × bit 1〜32 の全組み合わせで、`maskHas` = `(m & b) != 0`、`maskSet` = `m | b`、
`bitPow2(n)` = `1 << n` が一致することを確認しました。
複合bitテスト（56）、単一bitクリア、Generation category の AND-NOT ループも、
catMask 0〜63 × baseline 0〜63 の全組み合わせで旧式と同値です（不一致 0 件）。
**Zoneロジック・mask値・bitの意味は一切変更していません**（Pine v6構文互換のみ）。

#### 静的確認

`ZoneEngineV2_Rebuild.pine` / `ZoneEngineV2_Rebuild_VisualHarness.pine` の両方で、
文字列リテラルとコメントを除いた実行コード内の出現数：

| 検索文字列 | 件数 |
|---|---|
| `&` | 0 |
| `\|` | 0 |
| `<<` | 0 |
| `>>` | 0 |
| `bitwise.` | 0 |
| `bitOr` | 0 |

`maskHas` 定義136行／初回使用140行、`maskSet` 定義139行／初回使用1266行、`bitPow2` 定義142行／初回使用771行。
前方参照なし、未使用helperなし。Visual Harnessは元からビット演算を使用しておらず変更0行です。

再コンパイルは **NOT RUN** です。

---

### 6.2 関数の戻り値型の安定化（2026-09-19）

TradingViewでの実コンパイルで
`Error around line 1263: Return type of one of the "if" or "switch" blocks is not compatible with return type of other block(s) (series bool; series int)`
が出ました。

`swingIngestOne()` の最終statementが `if mergeId != 0 / else` で、
merge側の最終expressionが `e.dirtyQuality := true`（bool）、
new Root側が `registerRoot(e, r)`（int）だったためです。

同種エラーを1件ずつ出さないよう、Library全体を静的走査しました。

**走査条件**：ユーザー定義関数の最終top-level statementが `if` / `switch` / `for` / `while`（`else` は対応する `if` まで遡る）。

**該当39関数**のうち、

- 戻り値を呼び出し側で使用していない**side-effect専用29関数**：末尾に固定 `0`（int）を追加
- 戻り値を使用している**10関数**：変更なし（全branchが同一型 + default branchあり）

#### `0` を追加した29関数（すべてlocal、bare callのみ）

| セクション | 関数 |
|---|---|
| 7 Root registry | `liveOrderInsert` / `liveOrderRemove` |
| 8 Ingestion | `ingestMa` / `swingIngestOne` / `fvgIngestOne` / `ingestFvgNew` / `timeLabelDrop` / `updateTimeHL` / `markFvgInvalidation` / `updateFvgInverse` |
| 9 Candidate入力 | `syncPsych` |
| 10 Candidate生成 | `fvgStandalone` |
| 11 Core association | `rebuildOriginIds` / `addContactSpan` / `trimEpisodes` / `rebuildSideHistory` / `rebuildCoreHistory` / `pruneEpisodesToRange` / `ufUnion` / `sortEpisodesByStart` / `associateCandidates` |
| 12 状態遷移 | `activeEval` / `armedEval` / `processBreakState` |
| 13 Generation / 保存整理 / 投影 | `updateGenerationCandidate` / `pruneCategorySimple` / `pruneAccumBoxes` / `pruneStorage` / `buildViews` |

#### 変更しなかった10関数

`categoryName` / `phaseName` / `gradeName` / `densityName` / `weakReasonName` / `rootStateName` / `eventName` / `tfName`（全branch string、default `=> "?"` 等あり）、
`catIndexArr`（全branch `array<int>`、default `=> e.idxPsych`）、`catEnabled`（全branch bool、default `=> cfg.catPsych`）。

#### 呼び出し側への影響確認

`0` を追加した関数のbare callが「呼び出し元関数の最終expression」になっている箇所は3件でした。

| 呼び出し | 呼び出し元 | 影響 |
|---|---|---|
| `fvgIngestOne` | `ingestFvgNew` | `ingestFvgNew` 自身も本修正対象（末尾 `0`）。戻り値未使用 |
| `trimEpisodes` | `assignEpisodesFromSnapshot` | `assignEpisodesFromSnapshot` の戻り値は未使用（bare callのみ） |
| `activeEval` | `startTouch` | `startTouch` の戻り値は未使用（bare callのみ） |

いずれも戻り値を読む箇所がなく、`update()` の戻り値（`processed`、bool）にも影響しません。
`export update()` の最終expressionは `processed` のままです。

**ロジック変更は0件**（statementの追加のみ、既存の分岐・代入・呼び出し順序は不変）。

再コンパイルは **NOT RUN** です。

---

### 6.3 組み込み識別子のshadowing解消（2026-09-19）

TradingViewでの実コンパイルで
`Error around line 1762: Cannot shadow the built-in variable "high" because it has already been used as a built-in.`
が出ました。

セクション6の `fvgPackV2()` が組み込み `high` / `low` を読んでおり、その後にローカル変数 `bool high` を宣言していたためです。

#### rename（2スコープ・7行）

| 関数 | 行 | 旧 | 新 |
|---|---|---|---|
| `fvgAugment()` | 1762 / 1765 / 1767 / 1772 | `high` | `fvgHigh` |
| `fvgStandalone()` | 2094 / 2105 / 2109 | `high` | `fvgHigh` |

いずれも「そのFVG系候補がHigh densityに寄与するか」を表すbool。**値・条件式・処理順は不変**で、変数名のみの変更です。

#### 全体走査

Library / Visual Harness の全宣言（型付きローカル宣言・`var` / `varip`・`for` ループ変数・tuple分解・関数引数、複数行シグネチャを結合して解析）を、
組み込み識別子 約70語（`open` `high` `low` `close` `time` `volume` `hl2` `hlc3` `ohlc4` `bar_index` `na` `math` `array` `map` `str` `timeframe` `syminfo` および `ta` `request` `color` `line` `label` `box` `table` `input` `format` `size` `position` `text` `source` `order` `log` `alert` `chart` `session` `barstate` `runtime` `strategy` 等）と突き合わせました。

| 項目 | 結果 |
|---|---|
| 組み込みをshadowする宣言 | **0件**（rename後） |
| ユーザー定義関数名と衝突する変数宣言 | **0件** |
| Visual Harnessのshadowing | **0件**（元から該当なし） |

#### 変更しなかったもの（shadowingではない）

- **セクション6の組み込み読み取り**：`maPackV2` / `pivotPackV2` / `accumCondV2` / `accumPackV2` / `fvgPackV2` 内の `open` `high` `low` `close` `time`。
  これらは呼び出し側のrequest contextで評価される正規の組み込み参照で、宣言ではありません（計33箇所）。
- **UDTフィールド `ContactSpan.time` / `ZoneEvent.time`**：フィールド名は型の名前空間に属し、組み込み変数をshadowしません
  （Pine組み込みの `chart.point` にも `time` フィールドがあります）。`ContactSpan.new(time = ...)` / `ZoneEvent.new(time = ...)` は名前付き引数で、同じく宣言ではありません。
- **関数引数 `mintick`**：`toTick(float price, float mintick)` 等。`mintick` は単独の組み込み変数ではなく `syminfo.mintick` の一部であり、衝突しません。

**ロジック変更は0件**（変数名のみ）。

再コンパイルは **NOT RUN** です。

---

### 6.4 UDTオブジェクトの直接比較の解消（2026-09-19）

TradingViewでの実コンパイルで
`Error around line 2534: Cannot call "operator ==" with argument "expr0"="c.supportView.activeEpisode". An argument of "TouchEpisode" type was used...`
が出ました。Pine v6はUDTオブジェクト同士を `==` / `!=` で比較できません。

#### 修正（`pruneEpisodesToRange()` 1箇所）

```pine
// 旧
bool isActive = (not na(c.supportView.activeEpisode) and c.supportView.activeEpisode == ep) or
     (not na(c.resistanceView.activeEpisode) and c.resistanceView.activeEpisode == ep)

// 新
bool supActive = not na(c.supportView.activeEpisode) and
     c.supportView.activeEpisode.episodeId == ep.episodeId
bool resActive = not na(c.resistanceView.activeEpisode) and
     c.resistanceView.activeEpisode.episodeId == ep.episodeId
bool isActive = supActive or resActive
```

`episodeId` は `newEpisode()` が `e.nextEpisodeId` から採番するTouchEpisodeの安定IDで、Merge / Split / truncate を通じて不変です。
`na` ガードの位置と `or` の短絡順序も旧式と同一のため、**判定結果は完全に一致**します（「同じActive Episodeか」の判定方法のみ変更）。

#### 全体走査

Library / Visual Harness の全 `==` / `!=` / `<` / `>` / `<=` / `>=` について、両辺の式の型を解決して確認しました。
型解決は、UDT定義17種のフィールド型表、関数シグネチャの引数型（複数行シグネチャを結合）、関数スコープ単位のローカル宣言、
`array<T>` の要素型経由の `array.get()`、UDTを返すユーザー関数の戻り型、の各経路で行っています。

| 対象UDT | 直接比較 |
|---|---|
| `TouchEpisode` | **0件**（修正後） |
| `ZoneCore` / `SideViewState` / `SideHistory` | 0件 |
| `Root` / `ContactSpan` | 0件 |
| `TouchStartSnapshot` / `BreakSnapshot` | 0件 |
| `ZoneCfg` / `ZoneEngine` / `ZoneEvent` / `ZoneView` | 0件 |
| `BaseFeed` / `MaPack` / `PivotPack` / `AccumPack` / `FvgPack` | 0件 |

Visual Harnessは0件（元から該当なし）。

#### 既存の同一性判定（変更なし）

以下はすべて元からprimitive field比較であり、そのまま維持しています。

| 箇所 | 比較キー |
|---|---|
| `episodeIsDuplicate()` | `o.episodeId == ep.episodeId` または `sameEpisodeKey()` |
| `sameEpisodeKey()` | Side + time + 接触レンジtick + normalフラグのfield単位比較 |
| `sortEpisodesByStart()` | `a.startSeq` / `a.episodeId` |
| Core同一性 | `coreId` |
| Root同一性 | `rootId`（`candIdentityHasRoot()` 等） |
| ContactSpan | `baseSeq` / `time` / bottom・top tick |

**ロジック変更は0件**（比較方法のみ）。

再コンパイルは **NOT RUN** です。

---

### 6.5 式の戻り値への直接field assignmentの解消（2026-09-19）

TradingViewでの実コンパイルで
`Unable to determine the object for the field assignment. Try putting the object into a separate variable before assigning values to its fields.`
が出ました。Pine v6は `array.get(...).field := value` のように、式の戻り値へ直接fieldを代入できません。

#### 修正（2箇所）

**1. `associateCandidates()` Phase 5（候補なしcomponentのCore保持）**

```pine
// 旧
for q = 0 to cs - 1
    array.get(e.cores, array.get(e.snapCoreIdx, array.get(e.compSnapBuf, q))).lastMatchSeq := f.seq

// 新
for q = 0 to cs - 1
    int snapIdxK = array.get(e.compSnapBuf, q)
    int coreIdxK = array.get(e.snapCoreIdx, snapIdxK)
    ZoneCore cKeep = array.get(e.cores, coreIdxK)
    cKeep.lastMatchSeq := f.seq
```

**2. `applyBreak()`（反対SideのFlipWait遷移）**

```pine
// 旧
viewOf(c, -side).history.phase := 4

// 新
SideViewState oppView = viewOf(c, -side)
oppView.history.phase := 4
```

どちらもローカル変数への取得を1段挟んだだけで、参照先オブジェクト・代入値・実行位置は同一です。
Pine のUDTは参照型のため、ローカル変数経由の代入は元のオブジェクトを書き換えます（**挙動は完全に一致**）。

#### 全体走査

Library / Visual Harness の全代入（`:=` `+=` `-=` `*=` `/=` `%=`）について、左辺が
「`)` の直後に `.field`（複数段含む）」の形になっているものを検索しました。
`array.get(...)` / `map.get(...)` / `array.pop(...)` / `array.shift(...)` / 任意のユーザー関数呼び出し / `Type.new(...)` すべてを対象としています。

| ファイル | 該当数 |
|---|---|
| `ZoneEngineV2_Rebuild.pine` | **0件**（修正後） |
| `ZoneEngineV2_Rebuild_VisualHarness.pine` | **0件**（元から該当なし） |

primitive値の取得（`int x = array.get(...)`）やfieldの**読み取り**（`array.get(c.episodes, i).isNormalTouch` 等）は
Pineで問題がないため変更していません。

**ロジック変更は0件**（ローカル変数への分割のみ）。

再コンパイルは **NOT RUN** です。

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

### Debug table（20行）

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

## 12. 構造最適化（改訂7・結果不変）

目的は **RE10110（実行時間超過）の解消**のみで、Zone仕様・判定結果は一切変更していません。
履歴bar削減・直近N本限定・Root/FVG/Zone上限削減・カテゴリ削減・探索回数上限・timeout回避break・近似・
M変更・初期値変更・仕様条件削除は **すべて0件** です。変更したのは「同じ結果に到達するまでの計算方法」だけです。

| 禁止項目 | 件数 |
|---|---:|
| 履歴bar skip | **0** |
| 直近N本限定 | **0** |
| Root / FVG / Zone / カテゴリ上限の削減 | **0** |
| 探索回数上限・打切りbreak | **0** |
| 近似（median近似を含む） | **0** |
| M・初期値・仕様条件の変更 | **0** |

---

### 12.1 Point Root working setのcompact化（指示1）

| | 旧 | 新 |
|---|---|---|
| 保持 | `sLotSlot` / `sLotPrice` / `sLotTick` ＋ `sUsed` フラグ | `activeRootId` / `activeSlot` / `activePrice` / `activeTick` / `activeCategory` / `activePairKey` / `activeTfCode` / `activeLabelMask` / `activeSlopeDir` / `activeConfirmedTime` |
| `scanBest()`の走査対象 | 採用済みRootを含む全Root（`sUsed`で毎回skip） | 未使用Rootのみ |
| 採用後の除去 | `sUsed[k] := 1`（配列長は不変） | `compactActivePoints()` 1回 |

`collectPoints()` は master table（`sLotRootId` / `sLotCat` / `sLotPair` / `sLotTf` / `sLotLabel` / `sLotSlope` / `sLotConf`）を
**bar内で1回だけ**作ります。順序は旧 `sLot` と完全一致で、`array.sort_indices()` による価格昇順 1回 ＋
同tick時のRoot ID昇順 stable insertion sort（比較式は旧コードのまま）です。

`resetActivePoints()` は master をそのままコピーするだけで、旧 `array.clear(e.sUsed)` ＋ 全要素0 push と等価です。
Support評価の終了後に再構築し、Resistanceを独立に評価します。Psych / FVG はこの配列に入れません。

`compactActivePoints()` は `array.remove` を使わず、
**未採用Rootをtmp parallel arraysへ元順序のまま1回コピー → active clear → 戻す**、の1パスです。
Stage A → B → C は同Sideの同じactive setを引き継ぎます。

**結果不変の理由**：旧 `scanBest()` の内側ループは `sUsed[j]==1` を `continue` で読み飛ばしていたので、
実際に評価された j の列は「未使用Rootの列」そのものです。compact後のactive配列はその列と
Root ID・価格順まで一致します（下の機械検証で20,000試行・不一致0）。

---

### 12.2 scanBest内のRoot UDT lookup全廃（指示2）

inner loopの `rootOf()` と `array.get(e.roots, ...)` を **0回** にしました。
`r.pairKey` / `r.category` / `r.confirmedTime` / `r.rootId` / `r.slopeDir` / `r.priceTick` / `r.tfCode` / `r.labelMask`
はすべて `active*` parallel arrayから読みます（`activeConfirmedTime` は master生成時に `nz()` 済み＝旧 `int rct = nz(r.confirmedTime)` と同値）。

Root UDT取得はCandidate採用後（`adoptWindow()` 末尾の formTime / minId 再計算、`applyCandidate()`、`computeRefPrice()`）
だけに残しています。

| 位置 | 旧 lookup回数 | 新 |
|---|---|---|
| `scanBest()` inner loop | 窓評価ごとに1回 | **0** |
| `adoptWindow()` の採用Root列挙 | 採用Rootごとに1回 | **0**（`activeRootId` から直接） |

---

### 12.3 greedy意味の維持（指示3）

`i` → `j` を右へ進める → 幅超過で即 `break`、Accum pair conflictで `break`、という意味は変更していません。
comparator（C降順 / H降順 / Effective幅昇順 / 成立時刻昇順 / Root ID昇順）も、
`scanBest()` 内の `better` 連鎖も `candBetter()` も**1文字も変えていません**。
「Candidate採用 → active set compact → 再度 `scanBest()`」というgreedy順序も同じです。
全Candidateを一括生成してsortする方式は採用していません。

---

### 12.4 Psych検索範囲（指示4）

`sPsyUsed` によるownership仕様は変更なし。
`psychVariants()` は `floor((bot - M) / 50)` 〜 `ceil((top + M) / 50)` のlevel範囲だけを走査し、
各levelを `slotOf(e, psychIdOfLevel(lvl))`（ID直引き）で確認します。
`collectPsychRoots()` も `floor(bot / 50)` 〜 `ceil(top / 50)` のlevelを直接計算します。
**Psych Root配列の全走査は0件**（`e.idxPsych` を走査するのは `syncPsych()` の生成・失効処理だけで、Candidate評価経路にはありません）。

---

### 12.5 FVGの2 sorted index（指示5）

`buildFvgSet()` がSideごとに**1回だけ**次を作ります。

- `fvgBotTickOf` / `fvgTopTickOf`（working set index → tick）
- `fvgBottomTicksSorted` ＋ `fvgBottomOrder`
- `fvgTopTicksSorted` ＋ `fvgTopOrder`

sortはSideあたり bottom 1回 / top 1回のみ。Candidateごとのsortはしていません。

`fvgAugment()` は Candidate範囲から

```
searchBottomMax = candidateTopTick    + MTick
searchTopMin    = candidateBottomTick - MTick
```

を計算し、専用helper `sortedCountLe()` / `sortedFirstGe()`（`array.binary_search_rightmost` /
`array.binary_search_leftmost` を起点に、同値境界をtick単位でinclusiveに補正）で

- A：`bottomTick <= searchBottomMax` を満たす prefix
- B：`topTick >= searchTopMin` を満たす suffix

を求め、**件数の少ない側だけ**を走査します。A側走査時は `fvgTopTick >= searchTopMin` を、
B側走査時は `fvgBottomTick <= searchBottomMax` を必ず追加確認するので、
最終集合は常に完全intersection `fvgBottom <= candidateTop + M AND fvgTop >= candidateBottom - M` です。

**結果不変の理由（証明）**：`fvgAugment()` の評価中レンジ `[nb, nt]` は

1. `inside` 経路ではレンジを動かさない
2. `prox` 経路は `wT <= limitT`（`limitT` は `denseTickLimit` または `mTickLimit`、いずれも `<= MTick`）を満たすときだけ採用され、
   side==1 では下方向、side==-1 では上方向にしか広がらない

ため、常に初期 `[bot, top]` を含み、tick幅は `MTick` を超えません。
したがって attach され得るFVGは必ず

- inside：`fbT <= ntT <= botT + MTick` かつ `ftT >= nbT >= topT - MTick >= botT - MTick`
- prox(side=1)：`ftT < nbT <= botT` かつ `ftT >= ntT - MTick >= botT - MTick`
- prox(side=-1)：`fbT > ntT >= topT` かつ `fbT <= nbT + MTick <= topT + MTick`

を満たし、pre-filterの帯の外にあるFVGは **inside でも prox でも到達不能**です。
落としているのは「既存判定上、絶対に参加不可能なFVG」だけで、direction / inside / proximal /
Broad 4条件 / Dense Strong保護 / same-direction overlap / High判定は pre-filter後にそのまま実行します。

なお pre-filter後のindex bufferは、走査前に**working set index昇順へ戻して**います。
`fvgAugment()` はレンジを逐次広げるため、評価順序が結果に影響するからです（対象は通過FVGのみで、Root集合のsortではありません）。

---

### 12.6 Candidate ↔ Core の逆引き（指示6）

全Candidate × 全Snapshot ループを削除しました。

```pine
export type IntBucket
    array<int> values = na
```

- `map<int, IntBucket> rootToSnapshots`：通常Coreの**非Broad** origin Root ID → Snapshot index
- `map<int, IntBucket> broadRootToSnapshots`：Broad standalone contextの**Broad FVG** Root ID → Snapshot index

`snapshotCores()` の直後に `buildSnapshotIndex()` が1回だけ構築します。
Candidateは、通常Candidateなら自分の非Broad identity Rootから `rootToSnapshots` だけを、
Broad contextなら `broadRootToSnapshots` だけを引き、`seenSnap` scratch mapでdedupeしてから
**`candMatchesSnap()` の最終判定式をそのまま**実行します。

**結果不変の理由**：`candMatchesSnap(k, si)` が true になるには、
「Snapshot si の origin Root rid が Candidate k にも含まれ、かつ `isBroadFvg(rid) == candBroadCtx(k) == snapBroadCtx(si)`」
が必要です。indexはまさにその条件でしか登録・参照されないため、
true になり得るpairは全列挙され、共有Rootを持たないpair（必ずfalse）だけが事前除外されます。

---

### 12.7 Candidate ↔ Candidate の逆引き（指示7）

`for k1 / for k2` の総当たりを削除し、`map<int, IntBucket> rootToCandidates` に置換しました。
Candidateを正順に1件ずつ処理し、非Broad identity Rootごとに既存Candidate indexを引いて
`seenCand` でdedupeし、そのpairだけ `candSharesWithCand()` を実行して `ufUnion()`。
処理後にCandidate kを各非Broad Root bucketへ追加します。Broad FVG Rootはこのmapへ入れません。

**結果不変の理由**：`candSharesWithCand(k1, k2)` は
「`rid ∈ roots(k1) ∧ rid ∈ roots(k2) ∧ ¬isBroadFvg(rid)`」＋ gap ≤ M であり、Root共有部分は完全に対称です。
非Broad Rootを共有しないpairは必ずfalseなので、呼び出しを省いても結果は変わりません。
また union-find は常に小さいindexを代表にするため、union の呼び出し順序は最終componentに影響しません。

---

### 12.8 Component構築の1パス化（指示8）

```pine
export type ComponentBucket
    int rep           = -1
    int minCoreId     = 2147483647
    int bestCandidate = -1
    array<int> candidates = na
    array<int> snapshots  = na
```

`map<int, ComponentBucket> repToComponent` により、**node列 1回の走査**でcomponentを構築します。
componentごとに全Candidate / 全Snapshotをscanして所属を探す処理は削除しました。
Phase 4 / 5 は bucket内の candidate / snapshot だけを処理します。

component処理順は旧仕様のまま（minCoreId昇順、旧Coreなしcomponent同士は `bestCandidate` の `candBetter()` 比較）。
`bestCandidate` は bucket構築時に「component内candidateをindex昇順に見て `ba < 0 or candBetter(k, ba)`」で1回決めます
（旧コードがinsertion sortの内側で毎回全Candidateをscanして求めていたものと同一規則）。
この順序比較は全順序（最終tie-breakが `k1 < k2`）なので、初期並びに依存しません。

---

### 12.9 ufFindの重複呼出し禁止（指示9）

union構築完了後に `nodeRep` へ各nodeのfinal representativeを**1回だけ**保存し、
component sort / membership / topology処理は `nodeRep` と bucket だけを読みます。
path compressionは `ufFind()` 内に維持しています。

| 位置 | 旧 `ufFind()` 呼出し | 新 |
|---|---|---|
| component代表の収集 | `total` 回 | `total` 回（唯一の呼出し） |
| minCoreId 決定 | `sn` 回 | 0 |
| component sortの内側 | 比較ごとに `kn` 回 | 0 |
| snapshot所属判定 | component数 × `sn` 回 | 0 |
| candidate所属判定 | component数 × `kn` 回 | 0 |

---

### 12.10 ReferencePriceは採用Live Sideだけ（指示10・11）

`buildCandidates()` 末尾の「全Candidate → `computeRefPrice()`」ループを削除し、
`applyCandidate()` が Live Side へ採用したCandidateについてのみ、`candRefComputed` で1回だけ計算します。

ReferencePriceは表示・追跡専用で、Candidate競合・Topology・Phase・Grade・Touch・Break・Merge・Split・世代判定の
どこからも読まれません（`sv.referencePrice` への代入と `ZoneView.referencePrice` の出力だけ）。
`computeRefPrice()` は候補buffer（association中は不変）とRootのみを読む純関数なので、**値は旧実装と完全一致**します。
同一barで同じCandidateを2回計算することはありません。

内部の median sort は据え置きです。同一呼出し内で同じcategory値集合を2回sortすることはありません
（`sRefs` の2回目は maRep を追加した別集合）。median近似は入れていません。

---

### 12.11 scratch配列のnew排除（指示12）

bar処理中の `array.new` / `map.new` を排除しました。

| 対象 | 旧 | 新 |
|---|---|---|
| `buildProtectedSet()` | 毎bar `map.new<int,int>()` | `e.protMap` を `map.clear()` して再利用 |
| 逆引きbucket | （新規） | `e.bucketPool` からpool取得（初回のみ確保、以後 `array.clear()`） |
| ComponentBucket | （新規） | `e.compPool` からpool取得（同上） |
| active / tmpAct / FVG sorted index | （新規） | `newEngine()` で1回確保、毎bar `array.clear()` |

例外として残したのは、bar跨ぎで保存が必要な状態データだけです：
`TouchStartSnapshot` / `BreakSnapshot` / `TouchEpisode` / `ContactSpan` / `newSideView()` / `newCoreFrom()`。
状態データをscratchへ流用してはいません。

---

### 12.12 sort回数（指示13）

| sort | 1 Side / 1 bar |
|---|---:|
| Point Root 価格 sort（`array.sort_indices`） | **1回**（barで1回、両Sideが共有するmaster table） |
| Point Root 同tick時のRoot ID stable sort | **1回**（同上） |
| FVG bottom sort | **1回** |
| FVG top sort | **1回** |
| Candidate単位のRoot全体sort | **0回** |
| component単位の全Candidate再sort | **0回**（bucket内candidateのみ） |

---

### 12.13 Debug / Presentationの分離（指示14）

`update()` から到達可能な116関数を機械走査した結果、`str.tostring` / `str.format` は **0件**です。
Libraryが持つのは primitive counter / state だけで、文字列化は Visual Harness の
`barstate.islast` かつ表示ONのときだけ行います。

`validateCfg()` も、全チェックを primitive の bool 比較にしてから `if bad` の中でだけ error text を組み立てるよう変更しました。
**valid時（通常のbar）は文字列連結が1回も起きません**。invalid時のテキストは旧実装と1文字も同じです。

追加した primitive counter（Zoneロジック値には一切影響しません）：
`statFvgPrefiltered` / `statFvgScanned` / `statSnapChecks` / `statPairChecks` / `statRefPriceCalls`。
Harnessのdebug tableに2行（18・19行目）として追加しました。

---

### 12.14 触っていない処理（指示15）

Touch / Weak / Break / Flip / Inverse / Generation / Storage prune / Accum detection / Swing detection /
Time H/L / MA detection のロジックは**1行も変更していません**。
性能のために条件式を省略・統合した箇所も0件です。

最適化対象は `buildCandidates` / `scanBest` / `fvgAugment` / association / ReferencePrice / scratch allocation のみです。

---

### 12.15 更新前後の同値チェック（指示16）

コード上の同値性に加えて、各変換を抽象モデル化して機械検証しました。

| 検証 | 試行数 | 結果 |
|---|---:|---|
| FVG pre-filter：全走査 vs pre-filter後走査の attach集合・最終レンジ | 40,000 | 不一致 **0**（除外率 72.2%、参加不可能FVGのみ除外） |
| 逆引きassociation：全pair総当たり vs 逆引きの component分割 | 8,000 | 不一致 **0**（pair判定呼出しは 22.5% に減少） |
| active compact：旧 `sUsed==0` のRoot列との一致（Root ID・価格順） | 20,000 | 不一致 **0** |
| binary search境界helper：組込みが**どのindexを返しても**正しい境界になるか | 200,000 | 誤り **0** |

Candidate comparatorは旧コードと文字単位で同一（`candBetter()` と `scanBest()` の `better` 連鎖を無変更）。
Psych ownership（`sPsyUsed` / `psychLevelFree()` / `collectPsychRoots()`）も無変更です。

---

### 12.16 削減した走査・sort・lookupの一覧

| 項目 | 旧 | 新 |
|---|---|---|
| `scanBest()` の外側 i ループ | 全Point Root（採用済み含む） | 未使用Point Rootのみ |
| `scanBest()` の `sUsed` 判定 | i と j で毎回 | **全廃** |
| `scanBest()` inner loopのRoot UDT lookup | 窓評価ごとに1回 | **0** |
| `fvgAugment()` のFVG走査 | working set全件 | binary searchのintersectionのみ |
| Candidate × Snapshot | `kn × sn` 件の `candMatchesSnap()` | 共有Rootを持つpairのみ |
| Candidate × Candidate | `kn(kn-1)/2` 件の `candSharesWithCand()` | 非Broad Root共有pairのみ |
| component所属の再走査 | component数 ×（`kn` + `sn`） | **0**（1パスbucket構築） |
| component sort内の `ufFind()` | 比較ごとに `kn` 回 | **0** |
| `ufFind()` 総数 | union後も各所で再計算 | node 1回だけ |
| `computeRefPrice()` | 全Candidate | Live Side採用Candidateのみ |
| `map.new` / `array.new`（bar内） | `buildProtectedSet()` で毎bar | **0** |
| `update()` 内の文字列生成 | `validateCfg()` が毎bar連結 | **0**（invalid時のみ） |

---

## 11. 改訂履歴（実装状態の由来）

| 改訂 | Build ID | 主な内容 |
|---|---|---|
| 1 | -001 | 仕様v2の新規実装（Library / Harness / Report）。Accum形成条件式は正本欠落のため仮置きし、隔離して報告 |
| 2 | -002 | 付録A 7.4のAccum形成式を正本として一致（実体端レンジ、単一rangeMid、実体中点ドリフト、bull/bear別ラン、条件別ガード）。CandidateはrangeHigh/rangeLowを共有。Broad保護をBase Strong候補へ限定 |
| 3 | -003 | 全34項目の静的監査：段階Aの完成候補評価、Broad局所化4条件、Bullish/Bearish非補強、ActiveTouch中のMerge/Split遅延、Merge履歴再構築、Flip/Inverse後の再Armed抑止、Broad context同一性、心理価格の安定ID、保存整理の優先順とBox単位Accum、毎足validate、起源タグ衝突、全比較のtick正規化、Debug/表示の完成 |
| 4 | -004 | 段階Bの完成（残Point Rootへの局所化）、心理価格を候補列挙Rootから除外、Touch Episode単位の履歴、Zone lifetimeを仕様14へ、Stale Side Structureの失効、非BroadのFVG重複Highの空間結合、FVG 50%表示の削除、Harnessの5分足強制、Debug timezone、段階表記の統一 |
| 5 | -005 | Core物理範囲/Originの無条件再構築、Episode dedupeキーの統一、心理価格構成の全評価、片Side Coreでも有効なEpisode prune |
| 6 | -006 | Core associationの7フェーズ化（順序非依存）、Root ownershipの一括確定、Psychの同Side ownership、TouchEpisode + ContactSpanによる実接触履歴、Episode単位truncate、Split/Merge履歴配分 |
| 6a | -006（据え置き） | Pine v6構文互換修正のみ：ビットマスク処理を算術方式へ統一（`maskHas` / `maskSet` / `bitPow2`）。ビット演算子と`bitwise.*`を全廃。ロジック・mask値の変更なし |
| 6b | -006（据え置き） | Pine v6構文互換修正のみ：side-effect専用29関数の末尾に固定 `0` を追加し、関数戻り値型を安定化。ロジック変更なし |
| 6c | -006（据え置き） | Pine v6構文互換修正のみ：組み込み `high` をshadowするローカル変数2件を `fvgHigh` へrename。ロジック変更なし |
| 6d | -006（据え置き） | Pine v6構文互換修正のみ：TouchEpisodeの直接 `==` 比較を `episodeId` 比較へ変更。ロジック変更なし |
| 6e | -006（据え置き） | Pine v6構文互換修正のみ：式の戻り値への直接field assignment 2件をローカル変数経由へ分割。ロジック変更なし |
| 7 | -006（据え置き） | RE10110対策の構造最適化（§12）。active Point working set / Root UDT lookup全廃 / FVG 2 sorted index / 逆引きassociation / component 1パス構築 / ufFind 1回 / ReferencePrice採用時のみ / scratch new排除 / Debug分離。結果不変、仕様変更0 |

各改訂の差分はgit履歴（ブランチ `claude/new-session-vss3r2`）に保存されています。
