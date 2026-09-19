# ZoneEngineV2_Rebuild 実装レポート

作成日：2026-09-19（改訂4：TradingView実機確認前の最終静的修正）
Build ID：**`ZEV2R-20260919-004`**（Library / Visual Harness / 本書で共通）
対象：XAUUSD / 確定5分足 / Pine Script v6
正本：`Zone_definition_spec_v2.md` 全21節 ＋ 軽量化実装指示書 M0〜M19 ＋ 付録A〜D

---

## 0. 静的監査の最終状態

| 区分 | 件数 |
|---|---:|
| 仕様上の未解決事項 | **0件** |
| 実装上の既知の暫定処理 | **0件** |
| 結果へ影響する独自解釈 | **0件** |

前回の4件は次のように解消しました。

| 前回 | 今回 |
|---|---|
| 2.2-Q（段階B／Cの順序） | 段階順はA→B→Cのまま維持し、**不足していた段階Bの処理（残Point Rootへの局所化）を実装**して解消（1章 #1） |
| I-1（Broad条件3/4の「内部」限定） | 正本の「内部」条件の実装として確定。解釈項目から除外 |
| I-2（Merge後のWeak扱い） | **Touch Episode単位の履歴**へ拡張し、仕様12.2／12.3の履歴再配分として実装（1章 #4） |
| I-3（未照合Coreの終了） | 削除。仕様14のZone lifetime（有効Root・待機Rootが0）で判定（1章 #5） |

**実機適合性は未検証です。** Compile / 実チャート / Profiler / 75ケース / M15重点ケース /
Bar Replay / reload一致 / リアルタイム一致は**すべて NOT RUN**（6章）。

実装決定として記録するもの（Zone判定結果には影響しません）：

- Split子Coreは**親のGeneration IDを継承**します。Splitは新Zone世代ではないため（仕様18のリセット条件を満たさない）、新IDを振ると「新世代開始」と矛盾します。Touch/Weak/Freshのリセットは行いません。影響は表示されるGeneration IDのみです。
- `psychAugment()`が同一候補へ参加可能な心理価格を複数見つけた場合、結果幅が狭い方→level（価格）が小さい方の順で決定論的に1つ選びます。M=20・刻み50では2つが同時に幅条件を満たすことはありませんが、設定変更時のために順序を固定しています。

---

## 1. 今回の修正（12項目）

### #1 段階Bを正本どおり完成（指示1）

**仕様根拠**：付録A 10.2 段階A／B／C、仕様5.5。

**変更前の問題**：段階Bが「FVG同士の重複／FVG単独／Broad context」しか処理せず、
段階Aで使われなかった残Point RootとFVGの局所化（5.5の「FVG内部に局所Root」「Proximal外側に別Rootが高密集」）が
どの段階でも行われていなかった。

**変更後の処理**：段階順はA→B→Cのまま、段階Bを5ステップに完成させました。

| 段階 | 処理 | 実装 |
|---|---|---|
| A | 非FVG・非心理Rootのdense窓 → 心理価格合成 → FVG局所化 → Base Strong判定 → 競合選択 | `scanBest(limit = denseWidth, requireStrong = true, requireFvg = false, useFvg = true)` |
| B-1,2 | 残Point Rootに対するFVG内部局所化・Proximal外側局所化 | `scanBest(limit = M, requireStrong = false, **requireFvg = true**, useFvg = true)` を採用可能な間くり返す |
| B-3,4,5 | 同方向FVG実重複（共通区間）／FVG単独（NativeRange）／Broad未局所化（Broad context） | `fvgStandalone()` |
| C | 段階A・Bで使用されなかった残RootのみでM以下のNormal候補 | `scanBest(limit = M, requireStrong = false, requireFvg = false, **useFvg = false**)` |

- 段階Bで通常Point Rootを採用したら`sUsed`が立つため、同Sideの段階Cで再利用されません。
- Broad FVGだけは`sFvgLocal`で「局所化済み・未消費」となり、複数局所Zoneへ共有できます。
- 段階B・段階Cとも競合は同じ比較関数（C降順 / H降順 / Effective幅昇順 / 成立時刻昇順 / Root ID昇順）です。
- 段階CではFVGを一切付加しません（`useFvg = false`）。「段階C候補へFVGを後付けしてStrong化する」経路は存在しません。

### #2 心理価格を候補列挙Rootにしない（指示2）

**仕様根拠**：付録A 10.2 段階A の手順1→6、仕様3.6。

**変更前の問題**：`collectPoints(..., includePsych = true)`で心理価格を価格順配列へ入れていたため、
心理価格が候補窓の開始点・終了点になり、非心理Rootだけの候補列挙・競合に影響し得た。

**変更後の処理**：

- `collectPoints()`はカテゴリ0〜3（MA / Swing / Accum / 時間高安）だけを価格順配列へ入れます。心理価格とFVGは入りません。
- 窓を確定した後に`psychAugment(bot, top, limitTick)`が、その候補へM以内で参加可能な心理価格を合成します。
- 各窓について**「心理価格なし」と「心理価格あり」の2通りを評価**し、比較関数で勝った方を採用します
  （手順6「参加可能なら再評価」）。心理価格でC=2＋H≧1＋High DensityとなりBase Strongになることは許可されます。
- 心理価格は候補を開始・維持しません（窓は必ず非心理Rootから始まる）。

### #3 Broad条件3・4の「内部」（指示3）

`broadLocalizeOkAt()`は`inside == true`のときだけ条件3・条件4を評価します。
Proximal外側は条件1、実FVG重複は条件2で処理します。正本の「内部に」の実装として確定しました。

### #4 Touch履歴をEpisode単位で再構築（指示4）

**仕様根拠**：仕様12.2／12.3、19。

**変更前の問題**：`TouchMark`が接触範囲と時刻しか持たず、Weak履歴は親Sideの集約値をコピーしていたため、
「親に2 Episode、片方だけWeakDepth到達」を子ごとに正しく分離できなかった。

**変更後の処理**：`TouchMark`を通常Touch Episodeの記録へ拡張しました。

```text
side / baseSeq / time / touchNo / generationId / isNormalTouch
contactBottom, contactTop          接触範囲
snapBottom, snapTop                TouchStartSnapshot範囲
deepestClose, maxDepthPct          そのEpisodeの侵入実績
weakByDepth                        そのEpisodeでWeakDepthへ到達したか
```

- `startTouch()`がEpisodeを生成し、`SideViewState.activeMark`が進行中Episodeを指します。
- `activeEval()`が`deepestClose` / `maxDepthPct` / `weakByDepth`をEpisodeへ記録し、Reset・Breakで参照を外します。
- Merge / Split後は`rebuildSideHistory()`が、**新EffectiveRange（Sideに範囲が無ければCore物理範囲）へ実接触したEpisodeだけ**から
  1. SideTouchCount（同一Side・同一時刻をdedupe）
  2. WeakByTouch（再計算した通常Touch回数から導出）
  3. WeakByDepth（割り当てEpisodeの`weakByDepth`のOR）
  4. MaxDepth（割り当てEpisodeの最大）
  5. SideFresh（回数0）／ZoneFresh（通常Episode0件）
  を再計算します。**親がWeakだったから子も自動Weak、にはなりません。**
- `markIsDuplicate()`がSide・時刻・接触範囲tick・種別で重複Episodeを除外します。
- `marksTruncated`（Core単位）が立っている場合は、回数を下げない／Weakを解除しない／Freshへ戻さない、を維持し、
  Split子へ継承します。不明な過去を「未接触」と推測しません。
- Merge/Split後、両Side Viewが生きているCoreでは`pruneMarksToRange()`が
  新物理範囲へ属さないEpisodeを削除します。Split子は削除前の親Episode集合から作られるため、
  各子への配分が先に完了します。

### #5 未照合だけでCoreを終了しない（指示5）

**仕様根拠**：仕様14。

**変更前の問題**：`lastMatchSeq != f.seq`（今バー未照合）を終了条件に使っていた。

**変更後の処理**：`associateCandidates()`末尾を次へ置き換えました。

1. `e.ownerOfRoot`（当該足のRoot→Core割当）から、他Coreへ正式に移ったRootと消滅したRootを
   そのCoreの`originRootIds`から外す。
2. 今バーapplyされなかったSideのLive Structureを失効させる（#6）。
3. 残った起源から
   - 有効な非心理Root（state = Active / InverseActive）
   - 待機Root（state = InverseWait）
   を数え、さらにActiveTouch / Broken / FlipWait / BreakSnapshot / PendingTopology / PendingGeneration を待機状態として扱う。
4. **すべて0のときだけ**世代終了（`endedGen*`へ記録して削除）。

Weak・Local Break後・Dormant・時間経過だけでは終了しません。心理価格だけになったCoreは
有効非心理Root0となり終了します（仕様14）。

### #6 片Sideだけ更新された時のStale Side Viewを失効（指示6）

**仕様根拠**：仕様4.3（方向別に独立評価）、16.1。

`clearLiveSide()`を追加し、当該足でapplyされなかったSideの
rootIds / EffectiveRange / Reference / C・H / cat・highMask / Density / BaseStrong /
FVG projection / eligible を失効させます。

維持するもの：SideHistory、Touch Episode、TouchStartSnapshot、BreakSnapshot、Weak履歴、
Flip履歴、Generation履歴。

ActiveTouch中のSideだけは例外で、凍結したSnapshot構造を保ったまま
`finalizeSide()`が`eligible := sideHasLiveNonPsych()`でLiveStructureの参加資格を即時反映します（16.1）。
`armedEval()`は`sv.eligible`を要求するため、失効したSideは次バーにタッチ判定へ入りません。

コード上も「毎バー再構築するLive Side Structure」と「永続するSide History / Snapshot」を
`SideViewState`内で区分けしてコメントしています。

### #7 FVG異TF重複Highを空間的に結び付け（指示7）

**変更前の問題**：`sFvgOvlOk`（「どこかで重なっている」グローバルフラグ）で非BroadのFVG Highを決めていた。

**変更後の処理**：`sFvgOvlOk`を廃止し、非Broadも`fvgOverlapCovers(i, 候補範囲)`を使用します。
同方向・別TFのFVGとの**実共通区間が当該候補EffectiveRangeと交差する場合だけ**High根拠になります。
4H / 日足の非Broad FVG単独のHigh条件（`tfCode >= 240`）はそのまま維持しています。

### #8 FVG 50%表示を削除（指示8）

`i_showFvg50` / `fvg50Line` / `fvg50Label` / `fvgNativeMid()` と専用描画処理、
および`SideViewState` / `ZoneView`の`fvgNativeBottom` / `fvgNativeTop`を削除しました。
ZoneロジックのFVG 50%は引き続き完全不使用です。

### #9 Visual Harnessを5分足専用に強制（指示9）

```pine
bool tfOk = timeframe.period == "5"
if not tfOk
    runtime.error("ZoneEngine v2 Rebuild requires a 5 minute chart. Current timeframe: " + ...)
```

`ze.update()`、描画、Debug表はすべて`tfOk`を条件にしています。
5分足以外では明確なruntime errorとなり、Engineは静かに動きません。

### #10 Debug時刻のtimezone（指示10）

`tstr()`が`i_tz`（`cfg.zoneTimezone`と同じ入力）を使用します。

### #11 段階表記の統一（指示11）

Library先頭コメント、セクション見出し、`buildCandidates()`内コメント、本書をすべて
Stage A → Stage B → Stage C に統一しました。Stage Bの範囲（FVG局所Point候補＋Proximal局所化＋
FVG実重複＋FVG単独＋Broad context）も明記しています。

### #12 再監査（指示12）

3章・4章・5章に結果を記載しています。

---

## 2. 指示12の追加確認ケース（静的確認）

| # | ケース | 経路 | 結果 |
|---|---|---|---|
| A | Stage AでStrongにならなかったPoint Rootが、Stage BでFVG内部局所RootとしてFVG Zoneになる | Stage Aは`requireStrong = true`のみ採用し、残Rootの`sUsed`は0のまま。Stage B-1,2の`scanBest(requireFvg = true)`が、`fvgAugment()`で`inside`成立したFVG付き候補を採用 | 経路あり |
| B | Stage BでFVG局所Zoneへ使われた通常RootがStage Cで再利用されない | `adoptWindow()`が採用Point Rootへ`sUsed = 1`。Stage Cの`scanBest`は`sUsed == 1`をスキップ | 経路あり |
| C | 心理価格が単独で候補列挙を開始しない | `collectPoints()`はカテゴリ0〜3のみ。心理価格は`psychAugment()`で既存候補へ合成されるだけ | 経路あり |
| D | 親に2 Episode、片方だけWeakDepth到達。Split後それぞれ別子へ分かれた時、WeakDepth履歴も正しい子だけへ | `TouchMark.weakByDepth`がEpisodeごと。`splitCore()`が`intersectsT`で配分し、`rebuildSideHistory()`が割当EpisodeのORでWeakByDepthを再計算（truncate時のみ親値をOR） | 経路あり |
| E | WeakByTouchの親をSplitし、Touch 1件だけ引き継ぐ子 | `rebuildSideHistory()`が**親のフラグを継承せず**、子の実Episode数から`weakByTouch = (cnt + 1) >= weakFromTouch`を再計算します。**注記**：`weakFromTouch = 2`で子が通常Touchを1件引き継いだ場合、次回は2回目になるため仕様9.1・受入50によりWeakByTouchは`true`です。子が0件を引き継いだ場合に`false`になります（「親のWeakを自動継承しない」という要求は満たしています） | 経路あり・注記 |
| F | 有効Rootを持つが今バー未照合のCoreが終了しない | 終了条件から「未照合」を削除。有効非心理Root・待機Root・待機状態がすべて0のときだけ終了 | 経路あり |
| G | Supportだけ更新、Resistance候補0のCoreで前バーLiveStructureが残らない | `clearLiveSide()`をapplyされなかったSideへ適用（ActiveTouch中を除く） | 経路あり |
| H | 非Broad FVGが遠い場所で別TFと重なっていても、重複区間外のPoint局所候補がFVG Highにならない | 非BroadのHighは`tfCode >= 240 or fvgOverlapCovers(i, 候補範囲)`。`fvgOverlapCovers`は共通区間と候補範囲の交差を要求 | 経路あり |
| I | 5分以外でEngineが実行されない | `tfOk`が偽なら`runtime.error()`、かつ`ze.update()`・描画・Debugは`tfOk`条件 | 経路あり |

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
| 39 | 心理はCに数えるがHにならない | `catMask | 32`のみ。`hMaskNoMa`に心理ビットは存在しない |
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
| 68 | Mergeで同一接触を二重カウントしない | `markIsDuplicate`（Side・時刻・接触範囲tick・種別）＋`rebuildSideHistory`の時刻dedupe |
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
| `cand*`（採用候補） | なし（毎足再構築） | 毎足 | 候補数 | なし | Engine |
| Feed重複排除 | 元足closeTime／originTime | 新しい元足 | 各1 | なし | Engine |
| 設定検証 | なし（毎確定足実行） | 毎足 | - | - | Engine |

足をまたぐ候補キャッシュは実装していません。

### 7.2 計算量

| 処理 | 本実装 | 単純計算との差 |
|---|---|---|
| 価格順構築 | `O(R log R)`＋同値区間のみ挿入整列 | 毎足の全比較ソートを回避 |
| 候補探索 | 開始位置ごとに窓内本数k、1窓につき最大2変種（心理なし／あり） → `O(R·k)`／ラウンド | 窓ごとに窓内全Rootを引き直す`O(R·k²)`を回避（カテゴリ・品質要約を増分更新） |
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
4. **XAUUSD 5分足**へHarnessを追加。Debug表の`build`が`ZEV2R-20260919-004`であることを確認
   （5分足以外ではruntime errorになります）。
5. 通常実行の完走可否 → 別実行でProfiler。
6. 計測条件を記録：ticker ID、時間足、セッション、履歴開始/終了と本数、全パラメータ、
   Library公開番号、build ID、TradingViewが表示する実行制限。
7. 付録B 75ケース・M15重点ケース・本書2章のA〜IをBar Replayで確認し、本書へPASS/FAIL/NOT RUNを追記。

---

## 10. まとめ

- Zone定義v2の論理は変更していません。今回は既存契約へ合わせる静的修正のみです。
- **仕様上の未解決事項0件 / 実装上の暫定処理0件 / 結果へ影響する独自解釈0件。**
- 実装決定として、Split子のGeneration ID継承（履歴リセットなし・表示のみ）と
  心理価格合成の決定論的tie-breakを0章に記録しています。
- 実機適合性・実行時間・描画・再現性はすべて未検証（`NOT RUN`）です。
