# GLOBAL TOKEN LEDGER (ZoneEngineV2 Main compiled tokens)

Authority: the TradingView Main compile (CE10216 limit 1,000,000 compiled tokens). The source estimator (`cgest.py` E2 =
reachable source tokens, each function once) only selects candidates; it never decides PASS / FAIL.

Effect classes (compiled delta): HIGH >= 5,000, MEDIUM 2,000-4,999, LOW 500-1,999, NONE < 500 (NONE directions are not
mined further).

Targets: minimum <= 950,000, recommended ~900,000 (headroom for W09 B08-B20, W10, W11, W12).

## Baseline

| Item | Value |
|---|---|
| Branch | `claude/global-token-optimization` (from `41e0440`, backup `backup/w09-b07-r2-frozen`) |
| Semantics | frozen at W09 B07-R2 (W09State /21, W08Runtime /15) |
| Main compiled | 1,005,307 (CE10216) |
| Reachable source (E2) | 209,163 (360 functions) |

## Measured changes

| ID | Module | Change | Before | After | Delta | Effect | Semantic test | Status |
|---|---|---|---|---|---|---|---|---|
| H-1 | Main | unreachable legacy removed (C1, `d75d54e`, 1,305 lines) | 1,000,146 | 1,000,146 | 0 | NONE | n/a | historical: unreachable code has no cost |
| H-2 | W03Apply | /3 -> /4 shared journal-apply tests as helpers (overflow line) | 1,018,366 | 1,016,596 | -1,770 | LOW | det 147 + 1k smoke | published /4, not adopted on this line yet |
| H-3 | W09State | /20 -> /21 closeBeyondRaw + phaseMoveRaw | 1,005,614 | 1,005,307 | -307 | NONE | R2 det 40/40 | adopted (frozen R2 baseline) |

Historical data points: C1 `207,147` source = 1,000,146 compiled; B07 overflow 1,018,366; B07-R2 /20 1,005,614.
Observed compiled / source ratio of refactors: 0.9 (H-3) to 1.7 (H-2), far below the whole-code average (~4.8): shorter
source through small helpers returns little. Candidates are ranked by structure, then calibrated by probes.

## Pending probes (Phase B: compiled cost attribution; publish 0, Main compile only)

Every probe starts from the baseline Main (`41e0440`: W03F0 /4, W03Apply /3, W03ETimeFvg /2, W06 /19, W07 /10, W08Core /18,
W08Touch /5, W08Runtime /15, W03EMsa /7, W09State /21) and changes one thing.

| ID | Probe | Change | Before | After | Delta | Effect | Semantic change | Test | Adopt / Revert |
|---|---|---|---|---|---|---|---|---|---|
| G-A | W03Apply /3 -> /4 | import line 4 | 1,005,307 | pending | pending | pending | 0 (published, verified) | det 147 + 1k smoke (earlier) | pending |
| G-F | W03F0 /4 -> /5 | import line 3 | 1,005,307 | pending | pending | pending | 0 (published, verified) | det 28 + 5k (earlier) | pending |
| G-E | W03ETimeFvg /2 -> /3 | import line 5 | 1,005,307 | pending | pending | pending | 0 (published, verified) | det 13 + 5k (earlier) | pending |
| M1 | W06Comp + W05Cand unreachable (scratch, attribution only) | 3 calls -> 2 local stubs | 1,005,307 | pending | pending | module share | probe only | none | never adopted |
| S1 | synthetic 100-parameter function | - | - | - | - | DEFERRED | - | - | - |

S1 = DEFERRED: a synthetic parameter's compiled cost need not match the Production export signatures, cross-library calls,
array forwarding or inlining.

M1 reachability audit (cgest reachable graph, probe vs baseline): unreachable W06Comp 19 functions (30,942 source), W05Cand 27
functions (23,574), W07Fvg `fvgIntervalOrderBuild` 1 function (623; called only by W05Cand, so part of the W05 cost); nothing
else; W06 / W05 still reachable: none; new: the two stubs. A value shown after the compile is recorded as it is; a PASS without a
number is recorded as After = <1,000,000 and Delta as the minimum only.

## Structural candidates (source proxy, unverified in compiled tokens)

| Rank | Class | Where | Source tokens |
|---|---|---|---|
| 1 | E: giant signatures + argument forwarding (32 functions with >= 40 parameters) | W03Apply 6.2k, W06Comp 5.5k, W03EMsa 3.3k, W03ETimeFvg 2.8k, W03F0 1.7k, W05Cand 1.3k, W07Fvg 1.1k | ~21.9k (signatures 14.1k + call arguments 7.8k) |
| 2 | A: the same logic in several libraries | originLookupUniqueRaw / originTupleEqualRaw / originKeyComputeRaw / journalAppendRaw (W03EMsa + W03ETimeFvg), root / fvg set membership (Main + W03Apply + W03F0), rootPriceOrderUpperBoundRaw, pendingNewFvgRowRaw, physicalNewCompareRaw (W08Core + W08Runtime) | ~4.5k |
| 3 | A: near-duplicate functions in one library | W05 candEnumerateStageA / StageC (201 of 274 lines equal), W06 recomputeAndMerge / runComponentRaw | ~2.8k |
| 4 | D: S/R, High/Low duplicated blocks inside big functions | W03ETimeFvg w03StageETimeHlRaw 780, W03F0 preflight 500 + virtualPointOrderPreflightRaw 436, W06 buildComponents 200 | ~2.4k |
