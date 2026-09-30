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

## Adopted

| ID | Module | Change | Before | After | Known minimum reduction | Effect | Semantic change | Test | Status |
|---|---|---|---|---|---|---|---|---|---|
| GT-1 | Main pins | W03Apply /3 -> /4, W03F0 /4 -> /5, W03ETimeFvg /2 -> /3 (published TOKEN_REFACTOR_ONLY versions; sources from `1445b76`) | 1,005,307 | <1,000,000 (exact unknown) | > 5,307 | Bundle HIGH | 0 | existing equivalence PASS reused (W03Apply det 147 + 1k, W03F0 det 28 + 5k, W03ETimeFvg det 13 + 5k); static: export signatures identical | ADOPTED; Main PASS (Checkpoint 1) |

Checkpoint rule from here: every semantic Mini-Batch ends with a Main compile; further optimization only when a compile needs it
(next candidates then: W05 / W06, giant signatures). W05 / W06 / giant-signature refactors are not started now.

## Status after W09 B07-R3A

| Item | Value |
|---|---|
| Semantic baseline | `b12adcd` (B07-R3A, W09State /22; backup `backup/w09-b07-r3a-token-gate`) |
| Main compiled | 1,000,878 (CE10216) |
| Headroom | -878 |
| Status | RED |
| Targets | Checkpoint <= 950,000, preferred <= 925,000 (no semantic risk to chase the number) |

| ID | Probe | Change | Before | After | Delta | Effect | Semantic change | Test | Adopt / Revert |
|---|---|---|---|---|---|---|---|---|---|
| M2 | W05Cand unreachable, W06Comp kept (dynamic stubs in a probe copy of W06) | publish `token_probes/M2_W06Component_Worker_M2Probe.pine` as its own library once; Main import line 6 -> it | 1,000,878 | pending | exact if CE10216 shows a number; PASS -> W05 > 878 only | W05 share | probe only | none | never adopted |

M2 probe copy of W06 /19: library renamed `ZoneEngineV2_W06Component_Worker_M2Probe`, the W05 import removed, the three W05 calls
(`selectComponentBothSides` 33 values, `compareCandidates` int, `selectBothSides` 31 values) replaced by `m2Stub33(bar_index)`,
`(bar_index % 3 - 1)`, `m2Stub31(bar_index)` (int fields x + k, bool fields x % k == 0); 14 changed lines. Reachability audit
(baseline `b12adcd` vs Main + probe W06): unreachable W05Cand 27 functions (23,574 source) and W07Fvg `fvgIntervalOrderBuild`
(623, W05-only dependency); W06Comp 19 of 19 functions still reachable (+ the two stubs); nothing else lost.
Decision: >= 5,000 -> W05 first; 2,000-4,999 -> W05 candidate; < 2,000 -> W06 first; PASS (exact unknown) -> one W06-only probe
at most, then decide.

## Probes (Phase B) (Phase B: compiled cost attribution; publish 0, Main compile only; cumulative)

Start: the baseline Main (`41e0440`: W03F0 /4, W03Apply /3, W03ETimeFvg /2, W06 /19, W07 /10, W08Core /18, W08Touch /5,
W08Runtime /15, W03EMsa /7, W09State /21), 1,005,307. G1 -> G3 are cumulative; M1 is applied to the baseline alone (so a PASS
alone proves a W06 + W05 share > 5,307).

| ID | Probe | Change (on the previous step) | Before | After | Delta | Effect | Semantic change | Test | Adopt / Revert |
|---|---|---|---|---|---|---|---|---|---|
| G1 | W03Apply /3 -> /4 | import line 4 | 1,005,307 | 1,003,537 | -1,770 | LOW | 0 (published, verified) | det 147 + 1k smoke (earlier) | adopt candidate (bundle) |
| G2 | W03F0 /4 -> /5 | import line 3 | 1,003,537 | 1,001,007 | -2,530 | MEDIUM | 0 (published, verified) | det 28 + 5k (earlier) | adopt candidate (bundle) |
| G3 | W03ETimeFvg /2 -> /3 | import line 5 | 1,001,007 | <1,000,000 (PASS, exact value not shown) | <= -1,008 (lower bound) | LOW or more | 0 (published, verified) | det 13 + 5k (earlier) | adopt candidate (bundle) |
| G-bundle | G1 + G2 + G3 | - | 1,005,307 | <1,000,000 | <= -5,308 (lower bound) | HIGH | 0 | existing equivalence PASS reused | ADOPTED (GT-1) |
| M1 | W06Comp + W05Cand unreachable (dynamic stubs, attribution only), on the baseline alone (W03 /3 /4 /2) | 3 calls -> 2 local stubs of `bar_index` | 1,005,307 | <1,000,000 (PASS, exact value unknown) | W05 + W06 cost > 5,307 | HIGH (lower bound) | probe only | none | never adopted; further attribution DEFERRED |
| M1-const | constant-tuple stubs | - | - | - | - | REJECTED_PROBE_DESIGN | - | - | - |
| S1 | synthetic 100-parameter function | - | - | - | - | DEFERRED | - | - | - |

M1-const = REJECTED_PROBE_DESIGN: constant propagation contamination risk (constant results could let the compiler drop
downstream Main logic too and overstate the W06 / W05 cost). S1 = DEFERRED: a synthetic parameter's compiled cost need not
match the Production export signatures, cross-library calls, array forwarding or inlining. A value shown after a compile is
recorded as it is; once a step PASSes without a number, that step and every later delta are lower bounds only (never
invented).

M1 dynamic stubs: `m1Stub3(int x) => [x, x + 1, x % 2]` and `m1Stub38(int x)` (int fields x + k, bool fields x % k == 0), both
called with `bar_index`. Reachability audit (cgest reachable graph, baseline vs baseline + M1, same result on G3): unreachable W06Comp 19 functions (30,942
source), W05Cand 27 functions (23,574), W07Fvg `fvgIntervalOrderBuild` 1 function (623; called only by W05Cand); no Main
function and nothing else lost; W06 / W05 still reachable: none; new: the two stubs.

## Structural candidates (source proxy, unverified in compiled tokens)

| Rank | Class | Where | Source tokens |
|---|---|---|---|
| 1 | E: giant signatures + argument forwarding (32 functions with >= 40 parameters) | W03Apply 6.2k, W06Comp 5.5k, W03EMsa 3.3k, W03ETimeFvg 2.8k, W03F0 1.7k, W05Cand 1.3k, W07Fvg 1.1k | ~21.9k (signatures 14.1k + call arguments 7.8k) |
| 2 | A: the same logic in several libraries | originLookupUniqueRaw / originTupleEqualRaw / originKeyComputeRaw / journalAppendRaw (W03EMsa + W03ETimeFvg), root / fvg set membership (Main + W03Apply + W03F0), rootPriceOrderUpperBoundRaw, pendingNewFvgRowRaw, physicalNewCompareRaw (W08Core + W08Runtime) | ~4.5k |
| 3 | A: near-duplicate functions in one library | W05 candEnumerateStageA / StageC (201 of 274 lines equal), W06 recomputeAndMerge / runComponentRaw | ~2.8k |
| 4 | D: S/R, High/Low duplicated blocks inside big functions | W03ETimeFvg w03StageETimeHlRaw 780, W03F0 preflight 500 + virtualPointOrderPreflightRaw 436, W06 buildComponents 200 | ~2.4k |
