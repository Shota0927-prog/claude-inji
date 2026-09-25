# HANDOFF_W05

## 1 Status
- W05 COMPLETE / branch `claude/laughing-dijkstra-3w3zgr`
- final code HEAD `8cf84e2ea2002ecbdd1e71b5ef106e5f0794858e`
- TV compile（実測）: B01〜B20各0 error、Worker `/2` 0、Main final 0

## 2 Canonical
`05_窓05_ProductionCandidate_TwoPointer.md`（I12/I18/I25/A10）、PHASE A final/correction、HANDOFF_W04、W04 Reference（ConformanceHarness）

## 3 Architecture
- Main: Stage G分岐・revision・cache。heavy Candidate 0
- Worker `ZoneEngineV2_W05Candidate_Worker/2`: helper 22(private)、export `selectBothSides`、private UDT `CandidateCtx`
- 入力98 / 返値31 / write-back 29、配列はreference渡し
- fields: ZoneEngine 211 / W03SourceRootStore 142 / W02AuxStore 145
- MainへのWorker型leak 0

## 4 Completed
Eligibility、scratch、two-pointer全subwindow、差分C/H、Accum pair排他、Virtual Psych(50$)、Density/BaseStrong、FVG 5mode、Broad C1〜C4/Context、5-key comparator、identity、Stage A/B/C、Dense→C→Context greedy、used(Broad除外)、tie→Side failure、winner-only materialization、ReferencePrice、S→R、revision、cache、I25#22 B&B

## 5 I25#22 exact B&B（IMPLEMENTED）
- Stage A: 既存denseTick boundRight / Stage C: 既存mTick boundRight
- Point 4カテゴリはmonotonic scalar pointer
- maxH = Point存在カテゴリ数 + (FVG scratch>0)、maxC = maxH + (usePsych)
- actual C <= maxC、actual H <= maxH
- prune: `maxC < bestC` or (`maxC == bestC` and `maxH < bestH`) のみ。上限同値・best無しはpruneしない
- width/createdTime/minRootId prune 0、Stage B prune 0
- CONTEXT_SCANはprune禁止（全候補のBroad participation mark維持のexactness guard）

## 6 Frozen
API19 / export type8 / total27 / buildId `ZoneEngineV2_Rebuild_Strict20sV3`、ID 1開始0=none・slot -1 invalid、mutationは`updateConfirmed5m`のみ、comparator 5 key、Side順、Worker interface、cache key

## 7 Revision / Cache
- `cfgRevision`: fingerprint変化時+1
- `candidateTieBreakRevision`: MA_UPDATE confirmedTime差分かつStage F成功時+1
- cache: W02AuxStore、Side別valid＋7 snapshot（Side eligibility、rootPrice、rootQuality、priceOrder、fvgState、cfg、tieBreak）、全一致のみhit
- 両hit→Worker 0。miss→Worker 1回で両Side full recompute、両Side save、miss Sideの`candidateRevision*`のみ+1（各Side最大1/bar）
- 0件・-1・failedも保存。初回は両miss。fvgFresh単独はdirtyにしない

## 8 Physical decisions
CE10117(169826>100256)→Worker分離（import UDT案はCE10293で棄却、PLAN A）。Worker `/1`でB01〜B20完成。B18 constructor risk→cacheをW02AuxStoreへ。CLOSEOUTでI25#22不足検出→R1 Worker B&B、compile 0、`/2` publish→R2 Main import `/2`、compile 0

## 9 NOT YET VERIFIED
Appendix B 75/75、I22 10/10、XAUUSD 5m≥365d×3、Engine≤12s、StrategyBenchmark≤20s、Visual≤20s、40s runtime error 0、500ms loop error 0、collection/index/history error 0、Realtime/Replay/reload一致、runtime conformance

## 10 Out of scope → W06以降
Core統合(A10.7)、topology、Merge/Split、Generation、Touch、Weak、Break、Flip、Reclaim、Inverse、View projection、Strategy/Visual

## 11 W06 start
本書必須、branch一致、local==remote、clean、divergence 0/0、Main import `/2`、Worker/Main compile済み。W06のcomponent cache/局所再計算/dedupがW05 frozenと競合時は置換せず「W05 frozen vs W06 canonical」差分を先に報告

## 12 I27
NO_I27

## 13 Verdict
spec diff 0、independent completion 0、out-of-scope modification 0、I25#22 IMPLEMENTED、NO_I27 — W05 COMPLETE
