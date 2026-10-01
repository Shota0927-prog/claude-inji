# HANDOFF_W09

## 1 状態
- Window 09 COMPLETE / FROZEN（B01〜B20、20 / 20）: State_Touch_Break_Flip_Reclaim_Inverse
- 目的: W08の物理Core（Support / Resistance）上に、Phase / Grade / Touch Episode / Weak / Break / GapBreak / Flip / Reclaim /
  InverseConfirm / Dormant / Merge・Split Side transferをProduction pass（plan → F0 → commit → Stage J）として凍結する
- branch `claude/w09-b07-redesign-v2`
- 未完了Batch 0 / W09担当canonical OPEN 0 / I27 OPEN 0 / Production未commit差分 0
- canonical: `docs/canonical/09_窓09_State_Touch_Break_Flip_Reclaim_Inverse(1).md`
  （SHA-256 `8f5373a47543875927ef403abb9b4cd6fe300e8bc981b435c8848b5b274b9ef8`）、論理正本
  `docs/canonical/Zone_definition_spec_v2(5).md`（`f0ada2d851477850aa3d65463056e0318434b0c362383d475d49f9f6e1049cd1`）。
  W08 input authority = `HANDOFF_W08.md` + `GLOBAL_TOKEN_LEDGER.md`。pre-B01の旧audit artifactはcurrent truthではない
- W10 canonical `10_窓10_Snapshot_Pending_Generation_Fresh_Event_Storage.md`: B20時点でrepo内に存在しない（W10開始時に
  ユーザーから受領・SHA記録が必要）

## 2 HEAD
- W09開始HEAD: `e345208`（W08 closeout）
- B19 CLOSEOUT: `a5ca7a1`
- W10開始HEAD: このHANDOFF最終commitのHEAD

## 3 Production versions（source importで確認）
- Main `ZoneEngineV2_Rebuild` import: W03F0 /5、W03Apply /4、W03ETimeFvg /3、W06Component /25、W07Fvg /12、W08Core /19、
  W08Touch /7、W08Runtime /21、W03EMsa /9、W09State /35
- W09最終: W07Fvg /12、W08Core /19、W08Touch /7、W08Runtime /21、W09State /35（すべてpublish済み）
- Production Main: TradingView compile PASS、compile error 0、runtime error 0、exact compiled token UNKNOWN（色分類なし）
- TV Harness: `ZoneEngineV2_W09ConformanceHarness_B19.pine`（A、W09State /35・W08Touch /7 import、Main非import）、
  `ZoneEngineV2_W09ConformanceHarness_B19_DriftDiag.pine`（B、X1〜X3専用）

## 4 Batch
| Batch | 内容（ledger / commit名称） | 状態 |
|---|---|---|
| B01 | TSS contract（W09Stateコメント内の参照「B01 TSS contract」のみ。ledger独立見出し・commitなし。H01〜H06のW09State worker port / bridge exportが先行） | COMPLETE |
| B02 | State set / price index / canonical extraction primitives（W09State worker新設） | COMPLETE |
| B03 | pure Grade evaluator primitives（weakByTouchNow / strongTouchEligible / gradeExact） | COMPLETE |
| B04 | pure Armed distance / Touch Reset / next-bar seq primitives | COMPLETE |
| B05 | Stage D1 Touch / GapBreak target extraction primitives | COMPLETE |
| B06 | Side current Root list、SideView materialize、Phase / Armed transfer、Stage J接続、TouchStart atomic plan / production、Fresh、TouchMark Episode storage、touch history Merge / Split transfer（PRE2A〜B2C-C2） | COMPLETE |
| B07 | ActiveTouch Episode / WeakDepth / DeepestClose / Reset、projected Stage D、same-bar topology（R1〜R3-B2） | COMPLETE / CLOSED |
| B08 | Local Break / BreakReferenceRange（B08-A ActiveTouch Local Break + BreakSnapshot transfer） | COMPLETE |
| B09 | GapBreak | COMPLETE |
| B10 | Flip / FlipAttempt（+ token compression TC-A〜TC-D） | COMPLETE / FROZEN |
| B11 | Reclaim | COMPLETE / FROZEN |
| B12 | Inverse FVG | COMPLETE / FROZEN |
| B13 | Same-bar priority | COMPLETE / FROZEN |
| B14 | Phase / Grade finalization（W09_B14_PHASE_GRADE_DORMANT_FINALIZATION） | COMPLETE / FROZEN |
| B15 | Merge Side transfer（W09_B15_MERGE_SIDE_TRANSFER） | COMPLETE / FROZEN |
| B16 | Split / topology transfer（W09_B16_SPLIT_TOPOLOGY_TRANSFER） | COMPLETE / FROZEN |
| B17 | Stage C / D / J Production（W09_B17_STAGE_C_D_J_PRODUCTION） | COMPLETE / FROZEN |
| B18 | State Price-Index vs Reference（W09_B18_STATE_PRICE_INDEX_REFERENCE） | COMPLETE / FROZEN |
| B19 | Conformance（W09_B19_CONFORMANCE） | COMPLETE / FROZEN |
| B20 | Final audit / HANDOFF（W09_B20_FINAL_AUDIT） | COMPLETE |

## 5 Canonical implemented contract（凍結）
- 物理CoreはSupport / Resistance別のSide stateを保持。Phase = Waiting / Armed / ActiveTouch / Broken / FlipWait / Dormant
- Stage Jがsingle final writer（Phase / Grade / Upcoming / Armed / Dormant / coreDormantFlags）
- Stage C / D（read-only plan）はpersistent mutation 0。D1はold topology、Stage Jはnew topologyで評価
- 1 Event list順序: D1（TouchStart / GapBreak）→ D3 canonical merge（coreId ASC、generationId ASC、Support、Resistance）。
  Episode row内はWeakDepth → Reset → Break。抑止されたEventは0件

## 6 State / Touch / Weak
- Touchはprior-bar Armed authority（ArmedFromSeq <= currentSeq）。同足で初めてArmedになったSideは当足Touch不可
  （ArmedFromSeq = seq + 1）。成立時に価格がZone内ならTouchしない
- new Root / new range / Strong化をcurrent Touch / TSSへretroactive適用しない。ActiveTouch中のtopologyはPendingTopology
- TouchStartSnapshot（TSS）はEpisode中固定。更新はdeepest close / maxDepthのfrozen contractのみ。TouchStartGradeは固定
- in / outの往復はReset条件まで1 Episode。ResetはTSS rangeのtop + rd（Support）/ bottom − rd（Resistance）、confirmed close
- WeakByTouch / WeakByDepth / WeakReasonはnormal Resetで消去しない。WeakDepth後に価格が離れても解除しない。幅ゼロ（line）
  ZoneはWeakDepth非評価。WeakDepth閾値はequality包含
- Grade順: Unavailable（non-psych Rootなし / Flip未確定）> Weak（depth / touch番号）> Strong（Base Strong かつ
  StrongUntilTouch内）> Neutral。Grade finalizationはStage J authority

## 7 Break / Flip / Reclaim / Inverse
- Break: confirmed Close（Support close <= bottom − breakBuffer、Resistance close >= top + breakBuffer）。wick-onlyはBreakなし。
  ActiveTouchはTSS range authority、GapBreakはprior Armed range authority
- GapBreak bar: TouchCount増加なし、WeakDepthなし、Fresh消費なし、同足Flip / Reclaim禁止
- BreakSnapshot（BS）: range、oldSide、Root origin、breakSeq / breakTime、wasGapBreak、movedAway、retestSeenを両Sideへ同一payload
  で固定。後のEMA / topologyでthreshold移動禁止。BS.oldSide = Broken、opposite = FlipWait
- Flip: BS固定threshold。movedAway（前足までに確定）→ later retest contact → confirm。同一OHLCでmovedAwayとretestを同時に
  確定しない。FlipAttempt / FlipConfirmはnormal Touchではない（TouchCount / Weak / Fresh不変、non-normal TouchMark）
- Reclaim: movedAwayに依存しない。BS range + breakBuffer authority（Support close >= top + bb、Resistance close <= bottom − bb）。
  Touch / Weak / Fresh履歴維持、新Rootなし
- re-flip: 過去Side historyはそのSide slotにそのまま残り、使用済みSideへのFlipで復元（bsPairEndRaw / flipApplyは履歴を書かない）
- B13 same-bar priority: Break > WeakDepth、Break > Reset、FVG structural invalidation > Reclaim（D4はflipPlan前）、
  effective Reclaim > FlipConfirm（line BS・bb 0 tickの退化ケース）、invalidationで抑止されたReclaimはFlip pathへ戻る、
  GapBreak bar → Flip / Reclaim禁止、InverseConfirm holder → noArm、opposite-side invariant conflict → whole-pass F0
  （mutation 0、Event 0）
- Inverse lifecycle ownerはW07。W09はInverseConfirm integrationを凍結（one EV_INVERSE_CONFIRM per Root、non-normal TouchMark、
  holder noArm、normal Touchとしてcountしない、two-pass P0 / P1 D1 cancel）
- W07Fvg /12: WAIT_MOVED_AWAY / RETOUCHEDはthreshold index、MOVED_AWAYはW03 FVG NativeRange order再利用。
  InverseWait full predicate scan 0
- Dormant（B14）: d = confirmed Closeから最近接EffectiveRange edge（inside 0）。entry d > dormantDistance、recovery
  d <= dormantDistance。recoveryはWaitingへ戻して同Stage JでGrade / Reset / Armedを再評価、recovery barはTouchなし。
  当足のtransition（Reset / Break / pair end / noArm）があるSideはDormantにしない

## 8 Merge / Split / Stage order
- Merge（B15）transfer group: Touch history（TouchMark plan由来、same Side / time / contact dedupe）、TouchCount、
  LastNormalTouchTime、CurrentTouchNo 0、WeakByTouch（最終countから再導出）、WeakByDepth / MaxDepth（OR / max）、
  SideFresh / ZoneFresh（全source SideのAND、復活なし）、BS（breakSeq max → breakTime max → old Core canonical order、
  whole row）、FlipAttemptCount / lastFlipConfirmSeq（選択BS row / same-Side max）、TSS（merge禁止: ActiveTouch component
  はPendingTopology、当足完了TSSはcommit後clear）、Phase / Armed / ArmedFromSeq / LastArmedRange（baseline → Stage J再導出）、
  Dormant（Stage J派生）。W09_CARRY_MERGE_SIDE_STATE_TRANSFER = CLOSED（B15）
- Split / R4（B16、I27-B16-1）: BREAK_LIFECYCLE_CONTINUATION_OWNERSHIP。unresolved BSは1物理Coreのpaired lifecycle。
  continuation childのみがBS pairを保持、fresh childはold unresolved BSなし、range intersectionでownershipを決めない、
  Split後のrangeでBS payloadを書き換えない。source pairはboth invalidまたはboth valid + 同一payloadのみ、不一致はF0
  （mutation 0、Event 0）。R4はI27-15 #2のSplit BS ownership部分のみsupersede、Merge BS ruleは不変
- Stage order（B17）物理: A → B → D FVG fact → C / D read-only plan → E → F → G → H / I transaction → W09 transfer / apply /
  Event → J → K / L。canonical意味: C / D → E / F → G / H / I → J
- B17 F1: 旧Productionのreclaim評価順違反をcanonical順へ修正（canonicalで一意、I27なし）
- B17 F2: Stage F Root commitは後続W08 F0でrollbackしない。lastBaseSeq / lastBaseCloseTime / committedはstageFOk authority。
  同Feed retryではなく次Base barのfresh rebuild（I27-13R）。Root二重適用禁止。duplicate FeedはStage Aでreject、前Event保持

## 9 Price index（B18）
- key representation: EDGE_KEY_PLUS_QUERY_OFFSET_ACCEPTED_EQUIVALENT（edge key + query offset、整数tick）
- Production抽出: Armed（LastArmedRange）、Waiting / Dormant（EffectiveRange）、Broken / FlipWait BS（BS frozen range）、
  Inverse（W07 /12）。candidate取得後にcanonical orderへ戻す
- Stage J全live Core scan 0、Broken full predicate scan 0、InverseWait full predicate scan 0
- Reference parity: MISSING / EXTRA / ORDER_DRIFT / RESULT_DRIFT / INDEX_STALE / INDEX_MISSING / INDEX_ORDER = 0
- 観察（変更なし）: invHoldersRawはInverseConfirm / deferred-confirm Rootのある足だけlive Coreを走査（event-gated、B12 frozen）

## 10 TV evidence
- B19 Harness A（`ZoneEngineV2_W09ConformanceHarness_B19.pine` = `44e41f6`）: compile PASS、Appendix B 46〜69 = 24 / 24 PASS
  （FAILED 0）、I22_STATE_INDEX_PASS PASS（MISSING / EXTRA / ORDER_DRIFT / RESULT_DRIFT 0、INDEX_CHECKS 1730）、RUNTIME 0
- B19 Harness B（`ZoneEngineV2_W09ConformanceHarness_B19_DriftDiag.pine` = `2ddf0f7`）: X1 / X2 / X3 PASS、EVENT_DRIFT 0、
  STATE_DRIFT 0、FIXTURE_PRECONDITION_FAIL 0、FIRST_DRIFT NONE、golden 14 / 14、comparison 14、各case実行1回
- X2旧FAIL: HARNESS_FIXTURE_RESISTANCE_PHASE_ORIENTATION（Harness fixture defect、Production defect NO）
- local: Appendix 46〜69 24 / 24、per-bar state / Event drift 0、I22 W09 State index PASS。mutation: B19 M31〜M47 17 / 17、
  B18代表 9 / 9、B18 M1〜M30 + M17main全検出（ledger）、W09_MUTATION_UNDETECTED 0。random 0、5k / 50k / 200k NOT RUN
- 主張しない: Appendix 75 / 75、I22 10 / 10

## 11 I27（W09、すべて解決済み。OPEN 0）
- I27-15 BreakSnapshot transfer（B08、ユーザー復元・確定）: RESOLVED。#2 Split部分のみI27-B16-1でsupersede
- I27-18 TouchMark Episode storage / Merge・Split history（B06）: RESOLVED（frozen Production comments）
- I27-13R（ledger: B15 dependency retry contract、B17 F2の根拠）: 既存authorityとして適用
- I27-B12-1〜4（InverseAttempt非定義、EV_INVERSE_CONFIRM row、confirm-bar gating、InverseConfirm TouchMark）: RESOLVED
  （+ B12 C1 / C2 / C3 RESOLVED）
- I27-B13-1（退化ケースReclaim > FlipConfirm）、I27-B13-2（B08 D3 / B09 whole-pass F0維持）: RESOLVED
- I27-B14-1〜3（Dormant距離 / recovery / topology）: CLOSED（ユーザーcontract）
- I27-B16-1（Split BS ownership）: RESOLVED / IMPLEMENTED / VERIFIED、decision R4

## 12 Carry
- CLOSED（W08 → W09）: W09_CARRY_MERGE_SIDE_STATE_TRANSFER（B15、B06 / B08 / B10 / B14 / B16で充足）。W10へ再carryしない
- OPEN → W10
  1. `W10_CARRY_I17_REUSABLE_SCRATCH_3PATHS`: touchHistoryTransferPlan（seen）、bsTransferPlan（rel + full Side loop）、
     touchStartPostPlanPreflight（busy / roles）。authority = I17 Engine-owned reusable scratch + logical length reuse。
     W10またはFinal IntegrationまでにCLOSE必須
  2. `W10_CARRY_W07_INVERSE_INDEX_FREE_RETIRE_CLEANUP`: 現在free / retire pathなし。W10 Storage / Pruneでfree / retireを追加する
     場合、W07 Inverse index entry（WAIT / RETOUCHED）+ NativeRange membership + positionsをfree / slot reuse前にdetach / reset
- OPEN → 後続Window（W09未完了を意味しない）: Appendix B 70〜73 Generation → W10、Appendix B 75 full reproducibility →
  W11 / W12、365日Benchmark → W11、Visual final conformance → W11
- W07から継続（W08 HANDOFF記載のまま）: `I22_HASH_PATH = ABSENT`、`GLOBAL_I22_CFG_FINGERPRINT_COLLISION =
  DEFERRED_TO_LATER_ENGINE_CONFORMANCE`

## 13 W10禁止事項
- W10目的: Snapshot、Pending、Generation、Fresh、Event、ring / prune、View projection、storage completion
- W09 semanticをW10で再設計禁止（frozen dependency）: Touch、Weak、Break、GapBreak、Flip、Reclaim、Inverse integration、
  Dormant（B14）、same-bar priority（B13）、Merge transfer（B15）、Split R4（B16）、Stage order / F1 / F2（B17）、
  price-index semantics（B18）、B19 conformance expected
- W08 frozenも維持: Core ID、Generation ID current ownership、pairing、Identity、Merge survivor、Split continuation / fresh、
  TouchMark、PendingTopology order
- Generation lifecycleの新しいsemanticはW10 canonicalからのみ実装（推測禁止）
- compiled token: UNKNOWNのまま色分類しない。ZONEENGINE_COMPILED_TOKEN_RULES.md §0〜§18変更禁止

## 14 W10で最初にやること
1. START GATE（branch / HEAD / remote / clean / Production diff 0 / I27 OPEN 0）
2. HANDOFF_W09を読む
3. `10_窓10_Snapshot_Pending_Generation_Fresh_Event_Storage.md`を読む（repo未収録: 受領・SHA記録）
4. PHASE A read-only audit: frozen snapshot fields、live vs snapshot、PendingTopology / PendingGeneration、Generation条件 /
   reapproach、Fresh 3層、Event output、ring / prune protection、numeric View projection、I17 storage / scratch
5. W09 carry 2件（I17 scratch 3 paths、W07 Inverse index free / retire）を最初から監査対象に含める
6. いきなりProduction変更しない

## 15 Git
- branch `claude/w09-b07-redesign-v2`
- B20 START = local = remote = `a5ca7a1`、0 / 0、clean
- B20はdocument-only（GLOBAL_TOKEN_LEDGER.md、HANDOFF_W09.mdのみ）。Production source / version / Harness semantic変更0
