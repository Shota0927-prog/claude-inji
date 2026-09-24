# HANDOFF_W04

## 1. STATUS

CODE_COMPLETE_PENDING_B10_TV_COMPILE

## 2. AUTHORITY

- current authority: `04_窓04_ReferenceCandidate_Quality_Eligibility.md`（+ PHASE A Repair v2 / Final Repair v3 固定 D13–D25）
- old authority ではない: `04_窓04_FVG_Quality_Eligibility.md`（W04 正本として使用しない）

## 3. BRANCH / HEAD

- branch: `claude/laughing-dijkstra-3w3zgr`
- Start HEAD (W04 PHASE A): `b2d019176a02cf694adb56e61e1da32732135c81`
- B10 New HEAD (code commit): `7679e952b8c01310e7ffac17fab6c7ea2b577961`

## 4. FILES

- 変更 Production: 0（`ZoneEngineV2_Rebuild.pine`、W03 Worker 3本、`ZoneEngineV2_Rebuild_W03Harness.pine` は W04 中 diff 0）
- Reference: `ZoneEngineV2_Rebuild_ConformanceHarness.pine`（indicator、Production import 0、request.* 0、描画 0、非表示 compile anchor 1）
- handoff: `HANDOFF_W04.md`

## 5. REFERENCE TYPES

- `RefRoot` 19 field（D25 Fixture 入力。Virtual Psych は格納しない）
- `RefCandidate` 18 field（`rootIndexes` は RefRoot 配列 index、Virtual Psych は psych 3 field のみ）
- `RefResult` 18 field（`materializedRootIds` は rootId ASC、Virtual Psych なし）
- Reference 内部 const 43（`REF_*`、export なし）

## 6. REFERENCE FUNCTION INVENTORY（コード実数 23）

B02 `refEligible`, `refBuildPointOrder` / B03 `refAccumPairValid`, `refBuildPsychLevels` / B04 `refPointEffectiveRange`, `refDensity`, `refBaseStrong` / B05 `refCategoryHigh`, `refQualityAggregate` / B06 `refFvgRange`, `refBroadLocalization`, `refFvgHigh` / B07 `refAppendDenseCandidate`, `refAppendStageAVariants`, `refEnumerateStageA` / B08 `refAppendStageBCandidate`, `refEnumerateStageB` / B09 `refEnumerateStageC`, `refCompareCandidates`, `refSelectReferenceWinners` / B10 `refReferencePrice`, `refCandidateToResult`, `refBuildReferenceResults`

## 7. FROZEN LOGIC

- Eligibility: 非FVG は ACTIVE のみ両 Side。FVG Bullish ACTIVE→Support / INVERSE_ACTIVE→Resistance、Bearish は逆。他 state・RefRoot Psych は不可。
- Category High: MA＝Dense（Stage C 以外）+ EMA2000/3000 + gap ≤ denseTick + slope 両方 +1(Support)/−1(Resistance)。Swing＝mask ≥ 4 または == 3（Root 間合成なし）。Accum＝4H/D、または異TF・別 pairKey 共参加。TimeHL＝label 8/16/32（0..63）、または別 Root 2本共参加。FVG＝非Broad 4H/D、異TF同方向実重複、局所化 Broad。Psych＝常に Normal。
- C/H: Category ごと最大 1。Psych は C +1 / H 0。方向不適格 Root は invalid。
- Density: width ≤ denseTick HIGH、≤ mTick NORMAL、超過 −1、BroadContext 最優先。等号は狭い側。
- BaseStrong: C==2 & HIGH & H≥1、または C≥3 & HIGH。
- Accum pair: 同一非0 pairKey の 2 Root を含む window 全体 INVALID。
- Stage A: canonical order `(pointTick ASC, rootId ASC)` の全 contiguous window、Dense のみ、Psych なし + 単一 Psych level、非Broad FVG INSIDE/PROXIMAL、Broad C1/C3/C4。
- Stage B: 非Broad standalone、全 pair i<j（非Broad×非Broad OVERLAP、Broad 含みは C2 のみ）、各 base に Psych なし + 単一 Psych（limit mTick）、current-round BroadContext。
- Stage C: 残 Root、width ≤ mTick、実 density 保存、MA High false、C3 は Stage C 品質、PROXIMAL は denseTick 維持、Stage B 由来候補は品質再計算。
- Virtual Psych: 50 ドル刻み（100 倍数 Major）、1 候補 1 level、rootId なし、createdTime/minRootId 不参加、used 化なし。
- FVG EffectiveRange: STANDALONE NativeRange / INSIDE 点分布 / PROXIMAL 接近側 edge〜点分布（≤ denseTick、Support は nativeTop より上）/ OVERLAP `max(bottom)..min(top)`（幅0可）/ BROAD_CONTEXT NativeRange。
- Broad C1–C4: 各条件独立評価、cache なし、毎 round 再評価。BroadContext は当該 round に局所化 0 件の Broad のみ。
- Comparator: C↓, H↓, width↑, createdTime↑, minRootId↑ の 5 key のみ。
- winner/used: Dense（A+B、HIGH & baseStrong & 非Context）→ Stage C（全候補）→ final BroadContext。winner の Point Root・非Broad FVG を used、Broad と Psych は used 化なし。exact identity 既出 winner は除外。5 key 同値・別 identity は −1。
- ReferencePrice: Category 代表の単純中央値（偶数は中央2値平均、float、tick 丸めなし）。MA 2本は他 Point Category 代表中央値に近い EMA（同距離は rootId 小）、他なしは平均。FVG 代表は INSIDE 0票、PROXIMAL/STANDALONE/BROAD_CONTEXT は接近側 native edge、OVERLAP は共通区間の接近側端。50% 不使用。
- RefResult: Candidate 値をそのまま複写し、ReferencePrice のみ新規。winner 順を維持。

## 8. W05 EXACT-EQUIVALENCE CONTRACT

W05 Production Candidate は Side 別に W04 Reference と以下が一致必須: winner count/order、materialized Root ID set、effectiveBottomTick、effectiveTopTick、categoryMask、highMask、C、H、density、baseStrong、isBroadContext、createdTime、minRootId、ReferencePrice。

## 9. W05 REVISION DEPENDENCIES

- Support: `rootEligibilityRevisionSupport`, `rootPriceRevision`, `rootQualityRevision`, `priceOrderRevision`, `fvgStateRevision`
- Resistance: `rootEligibilityRevisionResistance`, `rootPriceRevision`, `rootQualityRevision`, `priceOrderRevision`, `fvgStateRevision`
- `fvgFreshRevision` だけの変更は Candidate dirty 根拠にしない。

## 10. OUT OF SCOPE / NOT YET VERIFIED

- 75 Conformance: NOT RUN
- I22 Reference vs optimized: NOT RUN
- 365d Benchmark: NOT RUN
- Production <=12 sec: NOT RUN
- Strategy <=20 sec: NOT RUN
- Visual <=20 sec: NOT RUN
- Reference の動作確認は Python 模擬のみ（TradingView 実行なし）。

## 11. TRADINGVIEW COMPILE

- B01〜B09: CONFIRMED 0 ERROR
- B10: PENDING USER VERIFICATION

## 12. W05 START GATE

- expected branch: `claude/laughing-dijkstra-3w3zgr`
- expected HEAD: B10 New HEAD（本ファイルを最終更新した commit `W04 B10 record final handoff head` の HEAD）
- git status: clean
- divergence: 0 / 0

## 13. I27

NONE
