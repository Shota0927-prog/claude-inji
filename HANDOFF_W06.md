# HANDOFF_W06

## A 状態
- Window 06 COMPLETE（B01〜B18）/ branch `claude/laughing-dijkstra-3w3zgr`
- 目的: Candidate cache + dependency component fixed-point + local recomputation
- 結果: global Reference / FULL とConformance一致（TV VERIFIED）

## B Production version
- Main: W06 Worker `/15`（Stage G）。compile / runtime PASS、RE10043 0、他runtime error 0
- W05: `/2` = Reference parity用、`/3` = Production dependency
- W06 Worker: `/15` compile PASS

## C 確定仕様
- component identity = kind + exact sorted MEMBER Root ID set
- hash不使用、exact key比較
- fixed-point展開、任意iteration capなし
- Broad共有だけではLOCAL component結合なし
- LOCAL_NORMAL / BROAD_ONLY domain分離
- global merge = W05 exact 5-key comparator、6th tie-breakなし
- forceFull = not cacheValid or cacheCfgRevision != cfgRevision
- capacity: Main 100000、Worker clamp [0,100000]

## D status enum
0 OK / 1 FAILED_AMBIGUOUS / 2 NOT_STORED / 3 NOT_COMPUTED
- FAILED_AMBIGUOUS: key一致中保持、strict FULL fallback（cache保持）
- NOT_STORED: capacity storage failure、strict FULL fallback、cache invalidate→rebuild
- global merge tie: FULL fallback

## E source-sensitive stabilizer
Worker `/15` mergeSideRaw の `array.set(cursor, best, src + 1)` 直後に
`int dAfterSize = array.size(mergedRecordInts)` がexactly 1個。
B17でTV上のRE10043を抑止したexecution-sensitive differential。
削除・移動・統合禁止。「compiler bug」と断定禁止。

## F B18 Conformance（TV VERIFIED）
- Test A: Failures 0 / Lane 0 / First Fail -1 / Local 16 / Fallback 0 / Last 15。Status Regression Failures 0
- Test B: Failures 0 / Fixture Failures 0 / First Compare 0。19 fixtures（F01〜F14、21A、21B-1、21B-2、21C、21D）、41 steps、Local 31 / Fallback 10 / Full 41 / Reference 82、W05 /2 vs /3 failure 0、K = 32
- 比較: A(H03 cache ON) vs B(H04 FULL) = H05全contract、A/B vs C = H06 W04 Reference

## G Harness split
CE10117（combined 107287 tokens > limit 100256）→ 分割。fixture・比較の削減なし
- Test A: `ZoneEngineV2_Rebuild_ConformanceHarness.pine`（91fa241 blob）
- Test B: `ZoneEngineV2_Rebuild_ConformanceHarness_B18_TestB.pine`

## H Deferred
- `I22_HASH_PATH = ABSENT`
- `GLOBAL_I22_CFG_FINGERPRINT_COLLISION = DEFERRED_TO_LATER_ENGINE_CONFORMANCE`
- W06 PASS扱いのhash collisionではない。Main upstream cfgFingerprint A/B collision検証を後続Engine Conformanceへ明示的に持ち越す

## I Production freeze
理由なく変更禁止: W05 `/3`、W06 `/15`、Main Stage G、dAfterSize、status semantics、capacity / forceFull
