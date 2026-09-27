# HANDOFF_W08（作成中：B15時点の記録）

Window 08は未closeout。本ファイルはB15で確定した静的前提の記録のみ。closeout時に正式HANDOFFへ統合する。

## Reachability invariant（B15 static audit）

`PARTICIPANT_ZERO_LIVE_ORIGIN_REACHABLE = 0`

participant = 0 のCoreが、liveなnon-Broad origin Rootを保持したまま
Identity continuation / Mergeされる状態は、現行Productionでは到達不能。

根拠（W08Runtime /4、W08Core /16、Main b76c54e）:
- Core origin = 物理Candidate Root union = Support / Resistance winner Root sliceの和（W08Core `physicalAppendRaw`）。
  materializeはoriginを書き（Runtime `materializeAppliedRaw` の `W08Core.originAdd`）、同じwinner Rootを
  participationへ接続する（同 `participationAddRaw`）。生成時点で origin Root集合 = participant Root集合。
- Root単位のparticipation detach writerはMain `rootFreeSlotRaw` 内の `participationDetachAllForRootRaw` のみで、
  同時にRootはdead（`rootIdToSlot` から削除）になる。`participationDetachRaw` にcall siteはない。Root IDは再利用されない。
- Identity exact（Runtime `identityExactSliceRaw`）は、liveな共通non-Broad origin Rootを要求する。
- よってparticipant = 0 のCoreはIdentity edgeを持てず、continuation / Merge / absorbed free / range変更を受けない
  （no-successor retainedのみ）。

I27-14（L7 dependency carry）は削除しない: W06 L7はCore range ± mTickの現行PC Root（participant以外を含む）を
依存へ接続するため、participant >= 1 のCoreでもrange縮小 / free時にold rangeだけにあるPC Rootのcarryが必要。
TV検証は `ZoneEngineV2_W08DependencyCarryHarness`（canonical 1 → 1 continuation、Test A / B）。

再監査条件: liveなRootのparticipationだけをdetachする新しいProduction writer、またはorigin ⊄ participantとなる
writerが追加された場合は、この前提を再監査する。
