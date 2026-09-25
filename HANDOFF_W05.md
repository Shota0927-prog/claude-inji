# HANDOFF_W05

## 1 Status
- W05 COMPLETE候補 / branch `claude/laughing-dijkstra-3w3zgr`
- final code HEAD `ede77d05c2cb37a2c7836c97e7e18b343c177fee`
- TV compile: B01〜B20 各Batch 0 error（ユーザー実測）。Main / Worker `/1` 最終 0 error

## 2 Canonical
`05_窓05_ProductionCandidate_TwoPointer.md`（I12/I18/I25/A10）、W05 PHASE A final/correction（Batch指示）、HANDOFF_W04、W04 Reference `ZoneEngineV2_Rebuild_ConformanceHarness.pine`

## 3 Architecture
- Main `ZoneEngineV2_Rebuild.pine`: Stage G 分岐、revision、cache。heavy Candidate 0
- Worker `ZoneEngineV2_W05Candidate_Worker/1`: 22 private helper、export `selectBothSides` 1本、private UDT `CandidateCtx`
- 入力98 / 返値31 / scalar write-back 29。Candidate配列はreference渡し
- fields: ZoneEngine 211 / W03SourceRootStore 142 / W02AuxStore 145
- Main export typeにWorker型なし（transitive leak 0）

## 4 Completed
Eligibility、Point/FVG scratch、two-pointer全contiguous subwindow、差分C/H mask、Accum pair排他、Virtual Psych(50$、1候補1level)、Density/BaseStrong、FVG 5mode、Broad C1〜C4/BroadContext、5-key comparator、completion identity、Stage A/B/C、Dense→StageC→BroadContext greedy、used(Broad除外)、tie→Side failure、winner-only materialization(RootId ASC)、ReferencePrice、Support→Resistance、cfg/tie-break/Candidate revision、Side cache

## 5 Frozen
API19 / export type8 / total27 / buildId `ZoneEngineV2_Rebuild_Strict20sV3`、ID 1開始0=none・slot -1 invalid、mutationは`updateConfirmed5m`のみ、comparator 5 key、Side順、Worker interface、cache key

## 6 Revision
- `cfgRevision`: fingerprint変化時+1（Stage A-1）
- `candidateTieBreakRevision`: MA_UPDATE confirmedTime差分かつStage F成功時+1
- `candidateRevisionSupport/Resistance`: miss Side再計算時のみ+1、各Side最大1/bar
- fvgFresh単独はdirtyにしない

## 7 Cache
W02AuxStore、Side別 valid＋7 snapshot（Side eligibility、rootPrice、rootQuality、priceOrder、fvgState、cfg、tieBreak）。全一致のみhit。両hit→Worker 0。1つでもmiss→`selectBothSides`1回で両Side再計算、両Side save。0件・-1・failed も保存し再利用。初回は両miss

## 8 Physical decisions
CE10117(169826>100256)でWorker分離（PLAN A、R0B/R0Cでimport UDT保持はCE10293で棄却）。Main旧Candidate削除。B18はconstructor riskでW02AuxStoreへ配置。cacheはPHASE A決定でSide全体単位（I12.7のcomponent/Stage/epoch keyは未採用）

## 9 Recorded decision
I12.5/I25#22 branch-and-bound: Batch指示によりmTick/denseTick境界とAccum conflict打切りのみ。結果不変、性能のみ影響。性能未達時に再検討

## 10 NOT YET VERIFIED
Appendix B 75/75、I22 10/10、365d XAUUSD 5m x3、Engine<=12s、StrategyBenchmark<=20s、Visual<=20s、40s runtime error 0、500ms loop error 0、collection/index/history error 0、Realtime/Replay/reload一致、runtime conformance全般

## 11 Out of scope → W06
Side候補→Core統合(A10.7)、topology、Merge/Split、Generation、Touch/Armed/ActiveTouch、Weak、Break、Flip、Reclaim、Inverse、View projection、Strategy/Visual

## 12 W06 start
HEAD一致・clean・divergence 0、本書必須。W06のcomponent cache/dedup/局所再計算がW05と競合する場合、置換前に「W05 frozen vs W06要求」差分表を提示

## 13 I27
NO_I27

## 14 Verdict
spec diff 0（9は記録済み決定）、独自補完0、担当外変更0
