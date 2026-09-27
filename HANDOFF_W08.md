# HANDOFF_W08

## 1 状態
- Window 08 COMPLETE（B01〜B18）: Core_Identity_Merge_Split
- 目的: W05 winner（Support / Resistance）から物理Coreを作り、Identity continuation / fresh / Merge / Split / TouchMark / PendingTopology
  までをProduction pass（plan → F0 → commit）として接続し、W06へのdependency carryまで閉じる
- branch `claude/laughing-dijkstra-3w3zgr`
- 未完了Batch 0 / 未解決canonical diff 0 / 未解決I27 0 / Production未commit差分 0

## 2 HEAD
- W08開始HEAD: `5a87e34`（W07 closeout）
- W08 closeout base: `77333fc`（B17 TV diagnostics）
- W09開始HEAD: このHANDOFF最終commitのHEAD

## 3 Production versions（source importで確認）
- Main `ZoneEngineV2_Rebuild`（source最終変更 `b76c54e`）import: W03F0 /4、W03Apply /3、W03ETimeFvg /2、W06Component /19、W07Fvg /10、
  W08Core /16、W08Touch /3、W08Runtime /4
- W06Component /19 → W05Candidate /5
- W08Runtime /4 → W08Core /16、W08Touch /3（W08Core / W08Touchはimportなし、cycle 0）
- TV Harness: `ZoneEngineV2_W08DependencyCarryHarness`、`ZoneEngineV2_W08PairIdentityConformanceHarness`、
  `ZoneEngineV2_W08MergeSplitTouchConformanceHarness`（いずれもW06 /19・W08Core /16・W08Touch /3・W08Runtime /4 import、Main非import）

## 4 Batch
| Batch | 内容 | 状態 |
|---|---|---|
| B01 | Core origin membership | COMPLETE |
| B02 | Core identity interval index（Worker化） | COMPLETE |
| B03 | inverse-origin index | COMPLETE |
| B04 | Identity gather / dedupe / order | COMPLETE |
| B05 | exact Identity predicate | COMPLETE |
| B06 | S/R physical pairing（interval sweep） | COMPLETE |
| B07 | canonical matching / continuation / fresh allocation / ID ownership / transactional materialization | COMPLETE |
| B08 | Merge topology | COMPLETE |
| B09 | Split topology | COMPLETE |
| B10 | TouchMark truncation / extraction | COMPLETE |
| B11 | Merge TouchMark | COMPLETE |
| B12 | Split TouchMark | COMPLETE |
| B13 | PendingTopology | COMPLETE |
| B14 | changed component / invalidation | COMPLETE |
| B15 | Production integration（Runtime Worker、thin Main）/ dependency carry | COMPLETE |
| B16 | Pairing / Identity conformance | COMPLETE（TV 29 / 29） |
| B17 | Merge / Split / Touch / Pending conformance | COMPLETE（TV 6 / 6） |
| B18 | Final E2E audit / closeout | COMPLETE |

## 5 Canonical（implemented contract）
- 物理Core: Support × Resistance winnerはtick gap <= Mかつ共有non-FVG Rootでpair。canonical最大matching（S / R rank =
  bottom, top, winner index、辞書順最初）。Root union ASC、minRootId、tick / exact envelope
- 同一pass内でFVG RootがS / R両方に出る入力はW05上到達不能。gap <= Mのpairで検出したら全体fail-closed（-1）
- Identity: 共有live non-Broad origin Root かつ gap <= M（old tick = round(exact / mintick)）。Broad FVG共有だけではIdentity / Mergeなし
- inverse same-origin: pass跨ぎのFVG Inverse（同一FVG Root、S → R）はinverse-origin gather + non-Broad FVG origin一致でcontinuation
- gatherはparticipation / interval / inverse index。full Referenceとの取りこぼし0（B16 REFERENCE_ELIGIBLE_MISSED_BY_INDEX = 0）
- matching: old rank（createdTime, coreId）× new rank（bottom, top, minRootId, Root集合）、最大・辞書順最初。完全tieはfail
- continuationはcoreId / generationId継承。freshはnew rank → S / R provenance順、ID = next + rank
- Merge: edge 2本以上のCandidate。survivor = そのcontinuation元、absorbed = 残りをold canonical順
- Split: edge 2本以上のold。continuation child / fresh child
- TouchMark Merge: Side EffectiveRange（winner exact）とexact contactが交差するものだけ。dedupe key（Side, time, bottom,
  top）、代表 = survivor → absorbed canonical → 同source時系列最初、payload丸ごと。順序 time → baseSeq → S < R → bottom →
  top。容量超過は古い順にdrop、drop Side truncated。source Side truncatedは継承
- TouchMark Split: childのSide EffectiveRangeと交差するmarkだけ（非交差コピーなし、untouched可、複数child可）。truncated = child
  がそのSideを持ちsource Side truncated
- Pending: componentのold Coreに1つでもSide ActiveTouch → component全体を適用せずlatest canonical pendingへ（同一snapshotは
  no-op）。ActiveTouchなしの既存pending = READY、最新topologyを適用してconsume
- map / storage順非依存（B16 / B17 permutation drift 0）
- 物理 / Identity / plan storageは毎pass fresh rebuild（persistent Pass1 cacheなし）

## 6 I27
- I27-10: no-successor / degree 0 / gap > Mだけではfreeしない（retained）
- I27-11: freeはapplied Merge relationのexplicit absorbedのみ、continuationされず、free preflight通過時
- I27-12: 73-field MERGE_STATE_DEFAULT_GUARD（absorbedのdeferred fieldがdefault以外ならpass reject）
- I27-13R: persistent Pass1 cacheなし、毎pass fresh rebuild / re-enumeration
- I27-14: W06 L6 / L7 / L8 dependency carry、L7はold / new range ± mTickのPC Root、mask 0 seed、W06 /19 semantic Root filter
- Reachability invariant: `PARTICIPANT_ZERO_LIVE_ORIGIN_REACHABLE = 0`（participant = 0かつlive non-Broad originを持つCoreは
  Productionで到達不能。origin = 生成時participant、participation detachはRoot free時のみ、Root ID再利用なし）。
  liveなRootだけのparticipation detach writer、またはorigin ⊄ participantとなるwriterが追加されたら再監査

## 7 B15 dependency repair
- W06 /19: semantic changed Root filterはmask 0 seedを除外（semantic changed componentは正しく出る）
- Main Aux `candDependencyCarryRootIds`: commit時にpass.dependencyChangedRootIdsをunion（sorted unique）
- 次barでmask 0 seedとしてinject。W06 buildがinjectを使いcache validのときだけclear、失敗時は保持
- L7はold / new range両方のPC Rootをscan（I27-14）
- duplicate / past FeedはW08 passに到達しない（Stage G後、lastBase commit前の1 callsite）

## 8 TV evidence
- B15: DEPENDENCY_PROBE_PASS = 1（A〜H）
- B16: B16_CONFORMANCE_PASS = 1、PAIR / IDENTITY / FAIL_CLOSED drift 0、CASES 29 / 29
- B17: B17_CONFORMANCE_PASS = 1、MERGE / SPLIT / TOUCH / PENDING drift 0、CASES 6 / 6（`77333fc`）。
  `7e890c2`初回実行はFAIL報告、Production / PASS式 / fixture不変の`77333fc`でPASS。初回FAILの原因は特定されていない
- Python: B17_REFERENCE_VALID 50000、mutant M1〜M10全検出、permutation drift 0

## 9 Carry
- CLOSED: W08_CARRY_B08_CHANGED_COMPONENT、W08_CARRY_B15_MAIN_REACHABLE_BUDGET（Main reachable 23593 < 24525、target <= 23800）
- OPEN（W09必須）: `W09_CARRY_MERGE_SIDE_STATE_TRANSFER`（73 fields = 55 MERGE_DEFERRED_STATE_FIELDS + 18 Side再評価field、
  W08Runtime `coreDeferredStateRaw`）。W08では実装・推測しない。W08未完了扱いではない
- W07から継続: `I22_HASH_PATH = ABSENT`、`GLOBAL_I22_CFG_FINGERPRINT_COLLISION = DEFERRED_TO_LATER_ENGINE_CONFORMANCE`

## 10 Main構造（`77333fc`再測定）
- direct fields: ZoneEngine 151、W02Aux 159、W08TouchStore 12、CoreRegistryStore 109
- Main W08 algorithmic loop 0。Runtimeと同名の旧W08 helper 28関数のうちreachableは`pendingStoreViewRaw`（view構築のみ）、
  残り27はdead legacy reference
- thin callsite 1: `w08ProductionRaw` → `W08Runtime.runShadow`（commit時のみnextCoreId / nextGenerationId /
  coreRangeRevision書き戻しとcarry merge）

## 11 W09開始時の禁止事項
- W08 ID semantics（continuation継承、fresh順、ID再利用なし）変更禁止
- TouchMark semantics（交差判定、dedupe key、代表、順序、truncation）変更禁止
- Merge / Split topology変更禁止
- MERGE_STATE_DEFAULT_GUARDをW09 state transfer実装前に削除禁止
- W08 Productionロジックを理由なく変更禁止（W08 verified contractはfrozen dependency）

## 12 W09で最初にやること
- 73-field real Merge Side state transfer設計（survivor / absorbedのSide stateをどう合成・継承するか）。Default Guardはtransfer
  実装とconformance完了まで維持

## 13 Git
- branch `claude/laughing-dijkstra-3w3zgr`、START GATE = local = remote、0 / 0、clean
