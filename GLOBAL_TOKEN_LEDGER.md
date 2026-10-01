# GLOBAL TOKEN LEDGER (ZoneEngineV2 Main compiled tokens)

Compiled Token Rule: ZONEENGINE_COMPILED_TOKEN_RULES.md (canonical, all Windows / Batches).

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
| M2 | W05Cand unreachable, W06Comp kept (dynamic stubs in a probe copy of W06) | not published | 1,000,878 | - | - | - | probe only | none | DEFERRED |

M2 probe copy of W06 /19: library renamed `ZoneEngineV2_W06Component_Worker_M2Probe`, the W05 import removed, the three W05 calls
(`selectComponentBothSides` 33 values, `compareCandidates` int, `selectBothSides` 31 values) replaced by `m2Stub33(bar_index)`,
`(bar_index % 3 - 1)`, `m2Stub31(bar_index)` (int fields x + k, bool fields x % k == 0); 14 changed lines. Reachability audit
(baseline `b12adcd` vs Main + probe W06): unreachable W05Cand 27 functions (23,574 source) and W07Fvg `fvgIntervalOrderBuild`
(623, W05-only dependency); W06Comp 19 of 19 functions still reachable (+ the two stubs); nothing else lost.
M2 = DEFERRED: publishing the probe library costs a publish slot and only attributes cost; a direct TOKEN_REFACTOR_ONLY
refactor of the known W05 duplication (StageA / StageC) is worth more. The probe file stays in `token_probes/` (unpublished).

### GT-2: W05 StageA / StageC enumeration shared (TOKEN_REFACTOR_ONLY)

| ID | Module | Change | Before | After | Delta | Effect | Semantic change | Test | Adopt / Revert |
|---|---|---|---|---|---|---|---|---|---|
| GT-2 | W05Cand /5 -> /6 (+ W06Comp /19 -> /20 import W05 /6 only; Main W06 /20) | StageA / StageC commonization: `candEnumerateStageARaw` + `candEnumerateStageCRaw` -> one `candEnumerateStageACRaw(..., stage)` | 1,000,878 | <1,000,000 (Main PASS, exact value not shown) | > 878 reduction (lower bound; exact UNKNOWN) | LOW or more (exact class unknown) | UNCHANGED | det 15/15 + mutants 8/8 killed | ADOPTED |

Source proxy: W05 25,478 -> 23,575 (-1,903 source tokens; reference only, never used as the compiled delta).

Audit (StageA 274 lines vs StageC 302 lines, 201 identical):

| Class | Block | Handling |
|---|---|---|
| COMMON identical | prologue (side / scratch / FVG scratch checks), branch-and-bound, window reset / enter, Psych variant loop, FVG per-entry checks and INSIDE / PROXIMAL / C1 / C3 / C4 ranges, FVG High, vCreated / vMinId | shared as is |
| COMMON parameter only | Stage constant (8 calls: QualityFinish x2, Offer x2, BroadLocalization x4) | `stage` argument |
| COMMON parameter only | window width D: A `denseTick`, C `mTick` (bound advance, base width, Psych bounds, Psych variant width) | `wTick = isA ? denseTick : mTick` |
| COMMON parameter only | density accepted: A High, C High or Normal (2 places) | `DEN_HIGH or not isA and DEN_NORMAL` |
| A_ONLY | W07 B14 FVG interval index (state, first-pass pre-scan, LEGACY / replay, indexed loop bound, replay `ok := false`) | kept verbatim; C starts with `fvgIndexReady = not isA`, `fvgLegacy = not isA` -> never builds the index, full scan 0 .. fvgN - 1, no replay (the old C loop exactly) |
| C_ONLY | FVG-only candidates (standalone / overlap / C2 Broad, Psych variants) after the point loop | kept verbatim, gated `while ok and not isA and fi < fvgN` |
| Semantic difference merged | none | - |

Callers: the 4 call sites pass `CAND_STAGE_A` / `CAND_STAGE_C`; call order unchanged (A, B, then C; Stage C phase; CONTEXT_SCAN A, B, C).
Test (`w05ac_det.py`, interpreted before vs after, every callee a recording oracle stub; PASS = same return, same ordered call
trace with every argument, i.e. every Offer in order, same final ctx): A / C normal, Support / Resistance, tie (constant C / H),
no candidate, multiple candidates with equal width / createdTime / minRootId, Broad heavy + CONTEXT_SCAN, FVG index LEGACY
(duplicate rootId) + replay (na confirmedTime), C FVG-only tail, Psych off, fail propagation: 15/15. Mutants (A accepts Normal
x2, wTick fixed x2, Psych bound, C index on, C legacy off, tail on A) 8/8 killed.

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
| 3 | A: near-duplicate functions in one library | W05 candEnumerateStageA / StageC (201 of 274 lines equal; done as GT-2); W06 recomputeAndMerge / runComponentRaw (GT-3 audit: signature overlap only, class E) | ~2.8k |
| 4 | D: S/R, High/Low duplicated blocks inside big functions | W03ETimeFvg w03StageETimeHlRaw 780, W03F0 preflight 500 + virtualPointOrderPreflightRaw 436, W06 buildComponents 200 | ~2.4k |

## Baseline after GT-2

| Item | Value |
|---|---|
| Branch | `claude/global-token-optimization` |
| Production pins | W03F0 /5, W03Apply /4, W03ETimeFvg /3, W05Cand /6 (via W06), W06Comp /20, W07Fvg /10, W08Core /18, W08Touch /5, W08Runtime /15, W03EMsa /7, W09State /22 |
| Main compiled | <1,000,000 (PASS, exact value unknown) |
| Semantics | W09 B07-R3A FROZEN; R3-B still forbidden |

From here every later "Before" is <1,000,000 without an exact value, so a later PASS gives no exact delta (recorded as After
<1,000,000 only; never estimated).

## GT-3 audit: W06 runComponentRaw vs recomputeAndMerge (not implemented)

`runComponentRaw` (255 lines, private, one caller) and `recomputeAndMerge` (333 lines, export) share 10 identical stripped
lines (`if ok`, `k += 1`, `side += 1` ...) and 967 token 8-shingles. Where the shingles are:

| Shared shingles | runComponentRaw | recomputeAndMerge | Class | Decision |
|---|---|---|---|---|
| 633 | signature (672 tokens) | signature (972 tokens) | giant signature (class E) | out of scope (giant signatures not touched now) |
| 179 | - | the `runComponentRaw(...)` call (argument forwarding) | giant signature (class E) | out of scope |
| 180 | W05 `selectComponentBothSides` 33-value unpack (`w*`) | `fullFallbackRaw` 31-value unpack (`fb*`) | return payload of two different producers, different consumers | semantic difference: not merged |
| 134 | winner-buffer size check after the W05 call, first conjunct `recSize >= wWinnerLogicalCount` | pre-commit check at step 5, first conjuncts `nS + nR <= cap and rootsS + rootsR <= cap and rootCount <= cap` | COMMON with semantic difference (different guard, different time: per row after the W05 call vs once before the global commit) | not merged |
| 32 | `runFilterOrdersRaw(...)` arguments | `mergeSideRaw(...)` x2 arguments | argument forwarding (class E) | out of scope |
| 9 | - | `compSideMaskRaw(...)` arguments | argument forwarding | out of scope |

RUN_ONLY: row validation, DIRTY Side detection, W05 per-component call and epoch check, pass 1 validation / sizes, per-Side
capacity (NOT_STORED), pass 2 append, row commit / pool rollback. RECOMPUTE_ONLY: component build, row loop, status /
NOT_STORED fallback, global Side merges, seen validation, exact range check, LOCAL commit of the winner buffer and seen stamps,
FULL fallback, the 45-value output. COMMON identical logic: none beyond the trivial lines above. COMMON parameter-only
logic: only the 17 `array.size(candidateWinner*) == recSize` conjuncts inside the two different checks; sharing them needs a
new 18-parameter helper and two 18-argument calls (heavier than the ~130 source tokens it removes, a new large signature), so
it is not done.

Decision: GT-3 = NO_CHANGE (reason: no semantic-identical duplicate; CORRECT_STOP; nothing implemented, W06 /21 not created, no publish, no compile). The rank 3 structural candidate
"W06 recomputeAndMerge / runComponentRaw" was a shingle artefact of the shared parameter list; it belongs to rank 1 (giant
signatures + argument forwarding).

## GT-4: huge signatures + argument forwarding (audit; GT-4A AUDIT_PENDING)

Audit (`gt4_audit.py`, reachable Production at the GT-2 baseline): 32 functions with >= 40 parameters. Per call site each
argument is classed FWD (a caller parameter), FIELD (`x.y`), LOCAL (a caller local), CONST or EXPR.

Structural finding: every Main -> library export call (W06 `recomputeAndMerge` 186 args, W03EMsa `run` 131, W03ETimeFvg `run`
125, W03Apply `applyThroughF4` 107, W03F0 `preflight` 97, W07 `stageEFreshInversePrepare` 67) passes Main engine FIELDs. A
library cannot receive Main's UDT, so replacing those scalars by one existing authority needs a new exported bundle type
(forbidden). The same holds for W06 -> W05 (`selectComponentBothSides` 100, `selectBothSides` 99: W05 builds its private
CandidateCtx from them). What is left is intra-library forwarding: a private callee with one call site whose arguments are
the caller's own parameters. Removing that callee's signature and forwarding needs no new structure: the callee is folded
into its single call site (the same values, the same place, evaluated once).

| Rank | Module | Caller -> callee | Callee params | Call sites | Forward-only | Caller-computed | Readable from an existing object | Removable params | New structure | Semantic risk | Publishes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | W06Comp | `recomputeAndMerge` -> `fullFallbackRaw` -> `W05Cand.selectBothSides` | 99 | 1 | 98 | 1 (`workSeenEpoch` -> `candidateBroadSeenEpoch`) | 0 (not needed) | 99 (signature 471 source tokens, call 198, 31-value pass-through tuple) | none | LOW | 1 (W06 /21, Main pin) |
| 2 | W06Comp | `recomputeAndMerge` -> `runComponentRaw` | 134 | 1 | 129 | 5 (`r`, `workSeenEpoch`, `filteredPriceScratch`, `filteredIdScratch`, `cap`) | 0 | 134 (signature 672, call 268, `[ok, epoch]` tuple) | none | LOW-MEDIUM (3,259-token body moves into the row loop; local name collisions: `ok`, `side`, `k`, `i`, `g`, `recSize` ...) | 1 |
| 3 | W06Comp | `buildComponents` -> `compExpandFixedPointRaw` -> `compExternalLinksRaw` | 56 / 55 | 1 / 1 | 55 / 55 | 1 (`workEpoch`) / 0 | 0 | 111 | none | MEDIUM (3,065-token body into a nested loop; `[added, failed]` tuple) | 1 |
| 4 | W03EMsa | `run` -> `w03StageEMaRaw` / `w03StageESwingRaw` / `w03StageEAccumRaw` | 51 / 74 / 88 | 1 each | 49 / 72 / 86 | 2 each (`journalCountNow`, `journalInvariantViolationNow`) | 0 | 213 | none | MEDIUM (three bodies, journal counter threading, 2-tuples) | 1 (W03EMsa /8) |
| 5 | W03Apply | `applyThroughF4` -> `maUpdateApplyRaw` (+ 6 sibling apply helpers 67-106 params) | 74 | 1 | 73 | 1 (`row`) | 0 | 74 (per helper) | none | MEDIUM (inside the journal op dispatch) | 1 (W03Apply /5) |

Not ranked: `mergeSideRaw` (2 call sites: folding would duplicate its body), `journalAppendRaw` (W03EMsa 6 / W03ETimeFvg 4
sites, mixed arguments), W07 `freshFacts` (W07 is imported by W05: publish chain W07 -> W05 -> W06), the Main -> library
exports and W06 -> W05 above (a new bundle type would be needed).

RECOMMENDED_GT4A = rank 1. `fullFallbackRaw` is a pure pass-through (checked mechanically): its body is exactly
`[fb... 31] = W05Cand.selectBothSides(p1, ..., p99)` then `[fb... 31]`, the 99 W05 arguments are its 99 parameters in the
same order, the return is the unpacked tuple unchanged. So its one call site
`[fb... 31] = fullFallbackRaw(a1, ..., a99)` is exactly `[fb... 31] = W05Cand.selectBothSides(a1, ..., a99)`; the change is
the callee name at that site and the deletion of the 3-line function. The argument list, its order, `workSeenEpoch`, the
evaluation point (the FULL fallback branch after the `keepCache` clearing), the bar and the single W05 call are unchanged.

| ID | Module | Change | Before | After | Delta | Effect | Semantic change | Test | Status |
|---|---|---|---|---|---|---|---|---|---|
| GT-4A | W06Comp /20 -> /21 (Main W06 /21) | fold `fullFallbackRaw` into its single call site (99-parameter signature removed, 99 forwarded arguments removed) | <1,000,000 | <1,000,000 (Main PASS) | UNKNOWN | - | UNCHANGED | GT-4A + GT-4B harness 15/15 | ADOPTED |

### GT-4B audit: inline `runComponentRaw` into `recomputeAndMerge` (APPROVED; not implemented yet)

Goal: delete the 134-parameter signature, the 134-argument call and the call boundary (`[ok, outEpoch]` tuple); the body is
moved verbatim, nothing of its logic is removed. Mechanical audit (`gt4b_audit.py`):

| Check | Result |
|---|---|
| A. call sites | 1 (line 2635, in `recomputeAndMerge` step 2 row loop); the only other reference is the definition. Pine has no function references |
| B. reachability | private, not exported, called from no other helper |
| Parameter mapping | 134 parameters : 134 arguments, 1:1 in order; 129 identity (each a `recomputeAndMerge` parameter of the same name, same object / value); 5 mapped: `row` <- `r`, `inCandidateBroadSeenEpoch` <- `workSeenEpoch`, `filteredPriceOrderSlots` <- `filteredPriceScratch`, `filteredIdOrderSlots` <- `filteredIdScratch`, `capacity` <- `cap` |
| Mapped-name substitution | whole-word replacement in the moved body: `row` 22, `inCandidateBroadSeenEpoch` 3, `filteredPriceOrderSlots` 2, `filteredIdOrderSlots` 2, `capacity` 9 -> `cap` (hazard: `recomputeAndMerge` has its own raw `capacity` parameter, so `capacity` must be substituted, never left) |
| Evaluation timing of the 5 caller values | the body assigns none of its parameters (checked: 0); `r`, `workSeenEpoch`, `cap` and the two scratch arrays are not written between the old call point and the end of the body; `workSeenEpoch := outEpoch` and `localOk := ok` follow the body exactly where `workSeenEpoch := runEpoch` / `localOk := runOk` were |
| Local collisions (99 callee locals) | with names visible at the call site (186 parameters + enclosing locals): none; `ok`, `outEpoch` unused in `recomputeAndMerge`; same names declared later in sibling / later blocks of `recomputeAndMerge` (`g`, `gId`, `hi`, `i`, `k`, `lo`, `recSize`, `side`): different scopes, no overlap in lifetime (the file already declares `int r = 0` in two sibling blocks) -> no rename needed |
| Scope / lifetime | every callee local is declared inside the function body, re-initialised on each call; after the move they are declared inside the loop body, re-initialised on each iteration: identical. No `var` / `varip`, no history `[n]`, no `ta.` / `request.`: no call-site-bound state |
| Control flow | no `break` / `continue`, no early exit (Pine has none); all loops (pass 1 Side 0 -> 1, member binary search, pass 2 append, seen scan, rollback pops) move verbatim: loop order, Side order (Support then Resistance), record order unchanged |
| W05 call | `W05Cand.selectComponentBothSides` once per DIRTY row, same position; `runFilterOrdersRaw` once, same position |
| DIRTY / epoch / pass 1 / capacity / pass 2 / commit / rollback / fail-closed | verbatim; every `ok := false` path and the `if not ok` pool rollback unchanged |
| Mutation parity | persistent: the 10 component row status / offset / length arrays; pools: `candRecordInts`, `candRecordReferencePrices`, `candRecordExactPrices`, `candRecordRootIds`, `candSeenBroadRootIds`; scratch: the two filtered arrays (via `runFilterOrdersRaw`) and the W05 winner buffers: the same objects (identity arguments / mapped aliases), the same writes in the same order |
| Return parity | `[ok, outEpoch]` -> `localOk := ok`, `workSeenEpoch := outEpoch` (same values, same order of the two caller writes) |
| C. order | identical |
| D. new recomputation | 0 |
| E. new allocation | 0 (no `array.new` / `copy` / `from` / `map.new` in the body; the two scratch arrays stay allocated once before the loop) |
| F. new high-cost structure | 0 (one tuple removed) |
| G. semantic risk | LOW (verbatim move + 5 whole-word substitutions, no rename of locals) |

Decision: GT-4B = APPROVED. Next implementation batch: GT-4A + GT-4B as one W06 change (W06 /21, Main W06 /20 -> /21, one
publish). Harness plan: interpreted old vs new `recomputeAndMerge` with `buildComponents`, `mergeSideRaw`, `compSideMaskRaw`,
`runFilterOrdersRaw` and the two W05 calls as recording oracle stubs (the real row loop body), <= 15 deterministic cases.

| ID | Module | Change | Before | After | Delta | Effect | Semantic change | Test | Status |
|---|---|---|---|---|---|---|---|---|---|
| GT-4B | W06Comp /20 -> /21 (with GT-4A) | inline `runComponentRaw` into its single call site (134-parameter signature removed, 134 forwarded arguments removed) | <1,000,000 | <1,000,000 (Main PASS) | UNKNOWN | - | UNCHANGED | det 15/15, mutants 5/5 killed, static PASS | ADOPTED |

### GT-4A + GT-4B implementation (W06 /21, Main W06 /20 -> /21)

- GT-4A: the single call site now calls `W05Cand.selectBothSides(...)` with the unchanged 99-argument list (same order,
  `workSeenEpoch` at the same position, same place in the FULL fallback branch); `fullFallbackRaw` (99-parameter signature,
  31-value unpack + return) deleted.
- GT-4B: `runComponentRaw` body (229 lines) moved verbatim into the row loop of `recomputeAndMerge` (+8 indent), whole-word
  substitutions in code only: `row` -> `r` 22, `inCandidateBroadSeenEpoch` -> `workSeenEpoch` 3, `filteredPriceOrderSlots` ->
  `filteredPriceScratch` 2, `filteredIdOrderSlots` -> `filteredIdScratch` 2, `capacity` -> `cap` 9 (exactly the audited
  counts); then `workSeenEpoch := outEpoch`, `localOk := ok`, `r += 1`. No local renamed. `runComponentRaw` (134-parameter
  signature, `[ok, outEpoch]` return) deleted.
- Static: `runComponentRaw` / `fullFallbackRaw` code references 0; `W05Cand.selectComponentBothSides` 1 -> 1,
  `W05Cand.selectBothSides` 1 -> 1, `runFilterOrdersRaw` calls unchanged; `array.new` 44 -> 44, `.copy` 0 -> 0, tuple
  unpacks 8 -> 6, functions 19 -> 17; the inlined body reversed through the mapping equals the old body line for line; raw
  `capacity` inside it 0; `r`, `workSeenEpoch`, `cap` and the two scratch arrays are never assigned inside it.
- Removed: signatures 99 + 134 = 233 parameters; forwarded arguments 99 + 134 = 233 (the W05 fallback call keeps its 99).
- Test `gt4ab_det.py` (interpreted /20 vs /21 `recomputeAndMerge`; build / merge / side mask / filter / both W05 calls are
  recording oracle stubs; PASS = same 45-value return or error, same ordered call trace with deep snapshots of every argument,
  same final state of all 186 inputs): normal, single Support, single Resistance, LOCAL + BROAD_ONLY with seen stamps and
  merged seen, status fallback (no merge, cache kept, GT-4A path), multi-record merge, DIRTY false, DIRTY mix, epoch fail,
  pass 1 fail, pass 2 over 3 rows, capacity 64 / 63 / clamped (-1 -> cap 0), rollback (filter fail after an append; W05
  count mismatch), W05 / merge failure, build FULL_FALLBACK (GT-4A pass-through): 15/15, 0.4 s. Mutants 5/5 killed
  (raw `capacity`, raw input epoch, raw epoch in the GT-4A call, lost epoch update, fixed row).
- Source proxy (reference only): W06 31,275 -> 29,524 (-1,751).

GT-4A + GT-4B result: Main PASS (<1,000,000, exact value not shown). Removed signatures 99 + 134 parameters, removed
forwarding 233 arguments, compiled delta UNKNOWN, semantics UNCHANGED. Decision: ADOPT.

## Baseline after GT-4A + GT-4B

W05Cand /6, W06Comp /21, W03Apply /4, W03F0 /5, W03ETimeFvg /3, W03EMsa /7, W07Fvg /10, W08Core /18, W08Touch /5,
W08Runtime /15, W09State /22. Main PASS (<1,000,000, exact unknown). R3-A FROZEN; R3-B not started.

### GT-4C audit: W06 buildComponents -> compExpandFixedPointRaw -> compExternalLinksRaw (APPROVED; not implemented)

Mechanical audit (`gt4_inline_audit.py`, all 12 Production files searched):

| Check | compExpandFixedPointRaw (into buildComponents) | compExternalLinksRaw (into compExpandFixedPointRaw) |
|---|---|---|
| Parameters / arguments | 56 : 56, 1:1 in order | 55 : 55, 1:1 in order |
| Call sites / references | 1 (line 1709) / definition + that call only | 1 (line 790) / definition + that call only |
| Export / recursion / other paths | private / none / reachable only through that call | private / none / reachable only through that call |
| Identity arguments | 55 (all `buildComponents` parameters) | 55 (54 `compExpandFixedPointRaw` parameters + the loop local `currentSlot`) |
| Mapped | `visitEpoch` <- `workEpoch` (caller local; hazard: `buildComponents` has its own `visitEpoch` parameter, so every `visitEpoch` in the moved code must become `workEpoch`: 3 in compExpand + 9 in compExternal after the chain) | none |
| Params assigned inside | none | none |
| Return | `finalRootCount` (int) -> `fr` | `[addedCount, failed]` -> `addedTotal += addedCount`, caller `failed := <callee failed>` |
| Allocation / state | no `array.new` / `copy` / `from` / `map.new`, no `var` / `varip`, no history, no `ta.` / `request.` | same; writes `candQueueRootSlots` (push) and `candVisitedEpochByRootSlot` (set), the same objects |
| break / continue | none | none |
| Loops | FIFO fixed-point over `candQueueRootSlots` (`readIndex` until the queue stops growing), verbatim | external-link scans verbatim (Side / Root / queue order unchanged) |
| Collisions visible at the call site | `failed` (caller's job `failed`) | `failed`, `currentMask`, `currentIsPc`, `currentIsFc` (the caller's own copies); after the chain also `rootCount` (buildComponents) |
| Same names in non-visible sibling scopes | - | `t`, `currentCategory`, `c` (no overlap) |
| Resolution | rename the moved local `failed` only | rename the moved locals `failed`, `rootCount`, `currentMask`, `currentIsPc`, `currentIsFc` only |
| Scope / lifetime | the renamed locals stay declared at the same point of the moved body, re-initialised per call -> per loop iteration: identical | same |
| Existing duplicate reads | - | compExternal recomputes `currentMask` / `currentIsPc` / `currentIsFc` from `currentSlot` as today (kept verbatim, not merged with the caller's copies) |

Conditions: A single-call YES (both), B order YES, C new recomputation 0, D new allocation 0, E mutation order YES, F return
YES, G new high-cost structure 0, H rename-only YES (6 locals), I risk MEDIUM (3,065-token body; about 30 renamed occurrences;
the `visitEpoch` -> `workEpoch` substitution through two levels).

Compile-only risk (not semantic): after both levels the deepest line sits at 76 spaces (19 levels; the file maximum today is
48 / 12). Pine publishes no nesting limit that the audit can check; only the TV compile decides. Fallback if it fails:
GT-4C' = compExpandFixedPointRaw into buildComponents only (56 parameters, deepest 36 / 9 levels), compExternalLinksRaw kept.

Decision: GT-4C = APPROVED (both levels, 111 parameters + 111 forwarded arguments; not implemented).

GT-4D pre-check (W03EMsa, no detailed audit): `run` -> `w03StageEMaRaw` (51 params), `w03StageESwingRaw` (74),
`w03StageEAccumRaw` (88): each has exactly one call site (W03EMsa lines 469 / 472 / 475) -> single-call YES for all three.
Main still holds unreachable same-named legacy definitions (no call site; not Production code paths).

### GT-4C1: inline `compExpandFixedPointRaw` into `buildComponents` (W06 /22, Main W06 /21 -> /22)

Decision before implementation: full two-level GT-4C (nest depth 12 -> 19) deferred; GT-4C1 (this level only) first,
GT-4C2 (`compExternalLinksRaw`) judged only after a TV PASS of GT-4C1.

- Body (27 code lines) moved verbatim to the single call site (+16 indent) with whole-word code-only substitutions:
  `visitEpoch` -> `workEpoch` 3 (the audited count), the moved local `failed` -> `xFailed` 4 (the only collision: the job
  `failed` of `buildComponents`). No other rename. `int fr = ...` / `failed := fr < 1` -> `failed := finalRootCount < 1`.
- `compExternalLinksRaw` untouched: its 55-parameter signature stays, 1 call at the same position.
- Static: `compExpandFixedPointRaw` code references 0; calls of `compExternalLinksRaw` 1 -> 1, `compPointRangeScanRaw`
  3 -> 3, `compFvgLinkRaw` 1 -> 1; `array.new` 44 -> 44; `copy` / `from` / `map.new` 6 -> 6; `var` 0; tuple unpacks 6 -> 6;
  types 0 -> 0; functions 17 -> 16; the diff is exactly the deleted helper (40 lines) and the replaced call (2 -> 40 lines);
  the block reversed through the mapping equals the old body; no raw `visitEpoch`, no reference to the caller `failed`, no
  write to `workEpoch` inside it. Max nest: block 36 spaces (9 levels), file max 48 unchanged.
- Test `gt4c1_det.py`: the old two lines (with the real old helper) and the new block, extracted from the files, each run in
  the same `buildComponents` environment (106 parameters + `workEpoch` + `failed`); side mask / point range scan / FVG link /
  external link are recording oracle stubs that grow the queue and stamp visited epochs. PASS = same (failed, workEpoch), same
  ordered call trace with deep argument snapshots, same final state of every input. Cases: normal, single Root, multiple
  Roots, Support-only mask, Resistance-only mask, no expansion, FVG expansion with a Broad FVG not expanded, multi-round chain,
  no external link, external links over two rounds, already visited, workEpoch != visitEpoch parameter, external failure,
  visited-size boundary (rootCount - 1 / rootCount), failure after additions with denseTick > mTick: 15/15, 0.1 s. The rest
  of `buildComponents` is textually identical (static diff). Mutants: raw `visitEpoch` killed, caller `failed` assigned
  killed, `W` without denseTick killed; `finalRootCount < 0` is an equivalent mutant (the queue always holds the start Root,
  so the count is never 0).
- Removed: signature 56 parameters, forwarding 56 arguments. Source proxy (reference only): W06 29,524 -> 29,071 (-453).

| ID | Module | Change | Before | After | Delta | Effect | Semantic change | Test | Status |
|---|---|---|---|---|---|---|---|---|---|
| GT-4C1 | W06Comp /21 -> /22 (Main W06 /22) | inline `compExpandFixedPointRaw` into its single call site (56-parameter signature removed, 56 forwarded arguments removed) | <1,000,000 | <1,000,000 (Main PASS) | UNKNOWN | - | UNCHANGED | det 15/15, mutants 3/3 non-equivalent killed, static PASS | ADOPTED |
| GT-4C2 | W06Comp /22 -> /23 (Main W06 /23) | inline `compExternalLinksRaw` into its single call site (55-parameter signature removed, 55 forwarded arguments removed) | <1,000,000 | <1,000,000 (Main PASS) | UNKNOWN | - | UNCHANGED | det 15/15, mutants 4/4 killed, static PASS | ADOPTED |

Baseline after GT-4C1: W05Cand /6, W06Comp /22, W03Apply /4, W03F0 /5, W03ETimeFvg /3, W03EMsa /7, W07Fvg /10, W08Core /18,
W08Touch /5, W08Runtime /15, W09State /22; Main PASS (<1,000,000, exact unknown). R3-A FROZEN, R3-B not started.

### GT-4C2: inline `compExternalLinksRaw` (W06 /23, Main W06 /22 -> /23)

Pre-implementation re-check on /22: 1 call site (inside the GT-4C1 block of `buildComponents`), no other reference, 55 : 55
1:1 (53 `buildComponents` parameters + the block local `currentSlot` identity, `visitEpoch` <- `workEpoch`: 9 occurrences,
hazard: `buildComponents` has its own `visitEpoch` parameter); `currentSlot` / `workEpoch` never written in the body;
collisions visible at the call site: `failed`, `rootCount`, `currentMask`, `currentIsPc`, `currentIsFc` (as audited);
non-visible sibling names `c`, `currentCategory`, `t` unchanged; nest after inline 76 spaces = 19 levels (as audited). No new
issue.

- Body (280 lines) moved verbatim (+24 indent) with whole-word code-only substitutions: `visitEpoch` -> `workEpoch` 9,
  `failed` -> `eFailed` 17, `rootCount` -> `eRootCount` 6, `currentMask` -> `eCurrentMask` 3, `currentIsPc` ->
  `eCurrentIsPc` 4, `currentIsFc` -> `eCurrentIsFc` 3 (declaration points / initialisation unchanged). Result:
  `[extAdded, extFailed] = ...`, `addedTotal += extAdded`, `xFailed := extFailed` -> `addedTotal += addedCount`,
  `xFailed := eFailed` (same order).
- Static: `compExternalLinksRaw` code references 0; calls `compSideMaskRaw` 20 -> 20, `compPointRangeScanRaw` 4 -> 4,
  `compFvgLinkRaw` 2 -> 2; `array.push` 158 -> 158, `array.set` 107 -> 107, `array.new` 44 -> 44, copy / from / map.new
  6 -> 6, `var` 0, tuple unpacks 6 -> 5, types 0, functions 16 -> 15; diff = the deleted helper (306 lines incl. comment) and
  the replaced call (3 -> 308 lines); the moved body reversed through the mapping equals the old body (280 lines); inside it
  no raw `visitEpoch`, no caller `failed` / `xFailed` / `rootCount` / `currentMask` / `currentIsPc` / `currentIsFc`, no write
  to `workEpoch` / `currentSlot`. File max nest 48 -> 76 spaces (12 -> 19 levels).
- Test `gt4c2_det.py`: the /22 GT-4C1 block with the real old `compExternalLinksRaw` vs the /23 block, extracted from the
  files, same `buildComponents` environment; stubs: side mask, point range scan, FVG link (recording). World fixtures with
  accum pairs (L4), origin buckets (L5), participation chains (L6), live Core ranges (L7), PendingTopology children / Root
  nodes (L8). Cases: normal, no external link, accum pair, multiple link kinds, Support-only / Resistance-only masks,
  Resistance-side participation with an FVG member, L7 only, FC start with a Broad member never added, mask 0 / mask
  differences, already visited, append order across L4 / L5 / L6 / L8, multi-round chain over two Cores and a pair,
  corruption (bucket / edge count / child count), visitEpoch 4 vs workEpoch 9 on every link kind, failure after additions
  with a stale PendingTopology root id: 15/15, 0.35 s. Mutants 4/4 killed (raw `visitEpoch` in the pair check, raw
  `visitEpoch` in the edge-pool stamp, bucket corruption writing the caller `failed`, dropped result `failed`).
- Removed: signature 55 parameters, forwarding 55 arguments. Source proxy (reference only): W06 29,071 -> 28,619 (-452).

## Checkpoint after GT-4 (W06)

Adopted Production: W03Apply /4, W03F0 /5, W03ETimeFvg /3, W03EMsa /7, W05Cand /6, W06Comp /23, W07Fvg /10, W08Core /18,
W08Touch /5, W08Runtime /15, W09State /22. W06: GT-4A, GT-4B, GT-4C1, GT-4C2 ADOPTED; removed forwarding 99 + 134 + 56 + 55
= 344 arguments, semantic change 0. Main: TradingView PASS, exact compiled UNKNOWN (headroom UNKNOWN; status not
determinable, never assumed GREEN). GT-4D (W03EMsa StageE Ma / Swing / Accum) and later: DEFERRED. Next: W09 B07 R3-B,
starting with a compiled-cost Probe.

## W09 B07-R3B0: R3-B compiled-cost Probe (rules: ZONEENGINE_COMPILED_TOKEN_RULES.md)

Branch `claude/w09-b07-redesign-v2` fast-forwarded to the global optimization head (`28ebec4`; 0/0, clean, Production bytes
identical to `claude/global-token-optimization`).

TOKEN START REVIEW: Main compiled PASS / exact UNKNOWN; headroom UNKNOWN; status not determinable (not treated as GREEN);
R3-B = Merge / Split / State Transfer / atomic transaction -> Probe required YES; Main business logic added NO.

R3-B reachable structure (audit of W09State /22, W08Touch /5, Main `w08ProductionRaw`, C2 transfer path):

| Item | R3-B need | Planned form |
|---|---|---|
| New helper | overlay from the Episode rows (FORCE_ACTIVE s / FORCE_INACTIVE -(s+1), ei col 9) replacing the TouchStart-only overlay of `planPassWithActiveTouchOverlay` | W09State `episodeOverlayBuild(ei, out)` (2 params) |
| New helper | inject the projected marks into the W08-built Merge / Split TouchMark plans (scratch of this bar) | W09State `touchPlanProject(TouchProjectView, tv, ei, ef)` (4 params); `TouchProjectView` = 5 references (W08Store, TouchRing, TouchPlan, SplitTouchPlan, winner exact prices), no copy |
| Merge path | per relation whose survivor / absorbed old is the Episode Core: winner exact range intersection, per-Side dedupe (time, bottom, top) in source priority, canonical position, shared S/R cap (drop oldest, truncated per dropped Side), A-type weak / max patch of the carried row | inside `touchPlanProject` (R3-B1) |
| Split path | SPLIT_LOCAL rows of the Episode Core: projected mark appended last (ring logical order), per-Side winner intersection, > cap fails | inside `touchPlanProject` (R3-B1) |
| Ring eviction | a full source ring loses its oldest row when the projected mark is appended: that row leaves the plans, its Side becomes truncated | inside `touchPlanProject` (R3-B1) |
| Changed helper | `episodeApply`: rows whose Core was consumed by an applied Merge / Split write no ring row (the plan carries it) and clear their TSS | W09State (R3-B2) |
| Changed wiring | Main TouchStart `markAppend` loop must skip consumed Cores | move the loop into W09State (`touchStartMarkApply`), Main keeps the event rows only (R3-B2) |
| C2 transfer | `freshTransferPlan` / `touchHistoryTransferPlan` already read the projected values (R3-A accessor) | unchanged |
| Added calls in Main | overlay build, projection, one view construction | 3 calls; the ring view hoisted once (R3-B2) |
| Added scratch | overlay list (<= 2 x Episode rows ints) | Main-local array; plan scratch reused (no new plan arrays) |
| Event wiring | EV_WEAK_DEPTH / EV_TOUCH_RESET unchanged | unchanged |

High-cost checklist: huge UDT `.copy` NO; huge tuple NO; mass array passing NO (one 5-reference view); huge export signature NO
(2 / 4 params); mass argument forwarding NO; projected state copy NO (ei / ef / plan rows referenced); duplicate plan build NO
(the W08 plans are patched, never rebuilt); Support / Resistance duplication NO (Side index); Main business logic NO.
Merge / Split rule duplication: RISK, decision at R3-B1 -> (A) export the W08Touch compare / rules (W08Touch /6 forces
W08Runtime /16, same TouchPlan type) or (C) a minimal incremental copy in W09State (compare ~12 lines, dedupe / range / cap
~15 lines). Not needed for the Probe.

Probe (W09State /23, Main W09State /22 -> /23): the R3-B boundaries reachable at their final call position (after the W08
plan, before the preflights) with a read-only body: `episodeOverlayBuild` (real overlay encoding, writes only the Main-local
`ov`, not passed to W08 yet) and `touchPlanProject` (locates, per Episode row, the Merge relations with the Core as survivor
/ absorbed and a target winner on the Side, the Split rows of the Core, the B plan row / A ring row of the mark; reads the
plan counts, exact ranges, ring; writes nothing; returns a count). Main: `tsOk := tsOk and overlay >= 0 and project >= 0`
(both >= 0 by construction, so tsOk and every later step are unchanged). Existing W09State code: 0 lines changed (+74 lines,
2 imports of the pinned W08Core /18 and W08Touch /5 for types only). Not in the Probe: the injection writes (R3-B1 body).

Probe check `r3b0_det.py` (fixed-seed deterministic fixtures, 0.14 s): well-formed worlds, malformed / stale sizes (relation
count above the rows, short absorbed / plan / split / planInts / ring / prices, negative offset, short ef), no Episode row,
overlay encoding: 10/10 (no failure, result >= 0, inputs unchanged, only `out` written). Source proxy (reference only):
W09State 23,167 -> 24,000, Main 79,570 -> 79,637.

| ID | Module | Change | Before | After | Delta | Status |
|---|---|---|---|---|---|---|
| R3B0 | W09State /22 -> /23 (Main W09State /23) | R3-B boundary Probe (read-only) | <1,000,000 (W06 /23 + W09State /22 PASS, exact UNKNOWN) | 1,113,110 (CE10216) | >= +113,111 | REJECTED (HIGH_COST_STRUCTURE); architecture not adopted |

### R3B0 result and attribution

TradingView: Main with W09State /23 + the Probe calls = 1,113,110 / 1,000,000 (CE10216), over by 113,110; the previous
baseline (W06 /23, W09State /22) PASSed, so the R3B0 increase is >= +113,111. Decision: R3-B0 architecture REJECTED; R3-B
implementation forbidden; not to be offset by Global Optimization (the structure is rebuilt instead, semantics kept).
FAIL class: HIGH_COST_STRUCTURE (most likely cross-library import / type reachability: W09State importing W08Core /18 and
W08Touch /5 and holding their store / ring / plan types in a view; not yet confirmed).

Production restored to the baseline (W09State /22, W06 /23; the bytes of `28ebec4`, Main PASS). W09State /23 is kept as the
failed Probe version (`token_probes/R3B0_W09State_Worker_v23_REJECTED.pine`, Main `token_probes/R3B0_Rebuild_Main_REJECTED.pine`);
/23 is never overwritten or reused; the next Production W09State takes the next unused version when a change is needed.

Attribution (one compile, no new version): R3B0_P1 = the baseline Main with the W09State import at /23 (the three Probe
lines removed; `token_probes/R3B0_P1_Rebuild_Main.pine`). CASE A about 1.11M -> W09State /23 itself (cross-library import /
type dependency) is the cause; CASE B much lower -> the reachable Probe call path; CASE C PASS -> the W08 dependency becomes
reachable only when called. Whatever the case, the R3-B0 architecture is not adopted.

Next architecture (design after P1): W09State imports no W08 library and holds no W08 type; it only emits the compact Episode
delta in the flat scratch (ei / ef). The Merge / Split TouchMark rules (range intersection, dedupe, canonical order,
capacity, truncation) stay in W08Touch (authority, option A): projected mark injection is a W08Touch helper taking primitive
scalars / arrays and existing W08-owned objects only (no W09State type, no import of W09State, no view, no plan / ring
copy). `episodeOverlayBuild` may stay in W09State (ei only, no W08 import).

| ID | Module | Change | Before | After | Delta | Status |
|---|---|---|---|---|---|---|
| R3B0_P1 | Main only (W09State /23 import kept, Probe calls removed) | attribution compile | 1,113,110 (R3B0) | 1,112,872 (CE10216) | -238 | CASE A: W09State /23 itself is the cause (>= +112,873 over the /22 baseline); the Probe call path costs 238; classification only, never adopted |

P1 = 1,112,872 (CE10216) -> CASE A. The two Probe calls and the view construction cost only 238; W09State /23 itself adds
>= +112,873 without any call of the new functions. /23 differs from /22 only by two imports (W08Core /18, W08Touch /5, types
only) and one exported UDT with W08 fields (+ two uncalled-from-P1 functions). The cost therefore sits in the cross-library
import / foreign-type dependency of W09State (the two parts, import vs the exported UDT with foreign fields, are not
separated by P1). Consequence for every design: a new import edge between libraries (even of a version Main already
imports) and a foreign type in an exported UDT are treated as HIGH_COST_STRUCTURE until measured otherwise.

Open question for later (not acted on; needs a measured Probe and approval): the existing library-to-library imports
(W08Runtime -> W08Core /18 + W08Touch /5, W06 -> W05 /6, W05 -> W07 /10) may carry the same kind of cost.

### R3-B0 status

R3-B0 architecture: REJECTED completely (TouchProjectView, W09State -> W08Core / W08Touch import, W09State
`touchPlanProject`: never reused; /23 never made Production, archived as a failed Probe only). Production baseline:
W09State /22, W06 /23, Main TradingView PASS (the bytes of `28ebec4`), confirmed on `claude/w09-b07-redesign-v2`.

### R3-B1 compact architecture v2 (design audit only; not implemented)

TOKEN START REVIEW: Main PASS / exact UNKNOWN; headroom UNKNOWN; status UNKNOWN; planned: W08Touch-side projected
injection; new cross-library import 0; foreign Production type 0; huge UDT 0; `.copy` 0; huge tuple 0; mass array forwarding 0
(4 primitive arrays); projected copy 0; plan double build 0; Merge / Split rule duplication 0; Main business logic 0.

Dependency graph: unchanged edges (Main -> all; W08Runtime -> W08Core, W08Touch; W06 -> W05; W05 -> W07). W08Touch stays a
leaf (imports nothing; never W09State). W09State imports nothing (no W08 import, no W08 type).

Authority of the projected data (no second copy): the Episode rows `ei` (stride 10: col 0 Side slot, 1 touchNo, 2 flags,
3 Core ID, 4 generation, 7 TouchStart plan row or -1, 8 ring row of the existing mark or -1, 9 override) and `ef` (stride 6:
col 4 Episode max depth), the TouchStart plan rows (`touchStartPlanInts` stride 30: 1 Core slot, 3 generation, 4 side, 6
touchNo, 16 baseSeq, 17 time, 27 normal; `touchStartPlanFloats` stride 7: 2 contact bottom, 3 contact top, 4 close). The
projected TouchMark of an Episode row is exactly what F0 writes today: B = `markAppend(plan payload, weakByDepth false, max
0.0)` then `episodeApply` sets weakByDepth = flags bit 32 and max = ef col 4; A = the ring row col 8 with the same two
fields replaced (col 8 = -1, truncated absent: no update). W08Touch reads these four primitive arrays through ~15 layout
constants (a data contract; no rule is copied).

| Item | Design |
|---|---|
| W08Touch helpers changed | `mergePlanBuild` and `splitPlanBuild` (existing exports) take the four arrays (`ei`, `ef`, `pI`, `pF`): 10 -> 14 and 16 -> 20 parameters; no new export |
| W08Touch private helpers added | projected payload accessor by virtual row (negative index -> Episode row), virtual-aware canonical compare over the existing 5 keys, virtual-aware row push (`weakByDepth` / `max` overridden for the Episode's mark), source eviction count |
| Merge, projected new mark (B) | the source old's extraction gets the projected mark as its newest row of that Side, then the unchanged pipeline: exact winner range intersection, per-Side dedupe (time, bottom, top) in source priority, canonical insertion, shared S/R cap (oldest dropped, truncated per dropped Side) |
| Merge, existing mark update (A, and B's own mark) | the row pushed from the ring row col 8 (or the virtual row) carries weakByDepth = flags bit 32, max = ef col 4 |
| Split, projected new mark | appended after the ring rows in the source's logical order (plan order for two marks of one Core), the unchanged per-Side winner intersection, > cap fails |
| Split, existing mark update | same field override on push |
| Ring eviction | a source ring with count + appends > cap loses its oldest logical rows (one per append, as `markAppend`): they leave the extraction / logical list and set their Side's truncated flag |
| Identity | an Episode row applies to a source old only when (slot, Core ID) match (col 0 / 2, col 3) |
| W08Runtime | new version /16 because the W08Touch export signatures change: ShadowContext + 4 primitive-array fields, the two existing plan-build calls pass them; import W08Touch /6; nothing else |
| W09State | unchanged in R3-B1 (/22). The Episode overlay (`episodeOverlayBuild(ei, out)`, ints only, R1 signed semantics) belongs to R3-B2 in the next unused W09State version |
| Main | wiring only: `ei` / `ef` allocated before `ShadowContext.new`, 4 arrays added to it, imports W08Touch /6 and W08Runtime /16 |
| A / B type | both projected through the same Episode rows; in R3-B1 the overlay is still the TouchStart-only list, so no Episode Core enters a Merge / Split and the injection is inert in Production (behaviour unchanged); it becomes active when R3-B2 switches the overlay |
| F0 before persistent mutation | 0 (only the W08 plan scratch of this bar is written, as today) |
| Capacity / truncation / dedupe / range | the existing W08Touch code path, single source |

Publishes: W08Touch /6, W08Runtime /16 (then Main compile). Probe (next step, after approval): the wiring and the new
parameters with the private helpers stubbed (arrays read, no rule body), foreign type import 0; then the R3-B1 body.
Deterministic plan for R3-B1 (later): harness of W08Touch plan builds with vs without projected rows equal to the ring after
the F0 writes (the ring written first, plans rebuilt) for B new mark, A update, eviction, dedupe, cap drop, Split cap fail,
both Sides, two marks of one Core.

### R3-B1 wiring Probe (W08Touch /6, W08Runtime /16; W09State /22 kept)

Design contract fixed before the Probe:
- Capacity is three separate things, never mixed: (A) source ring projected append = `markAppend` semantics (a full source
  ring loses its oldest mark per append, that mark's Side becomes truncated); (B) Merge destination = the W08Touch canonical
  pipeline on the projected source history (range intersection, dedupe, canonical sort, then the shared cap drops the
  oldest rows, each dropped Side truncated); (C) Split destination = ring logical order, no dedupe, a child above the cap
  FAILS (never trimmed; "drop the oldest" is not applied to a Split destination).
- Scratch-format contract: W08Touch reads `ei` / `ef` / TouchStart plan ints / floats through compile-time constants
  (EI_*, EF_*, PI_*, PF_*); no contract library, no new import, no foreign type. Static conformance outside Production:
  `tests/r3b1_scratch_contract_check.py` (W08Touch constants vs W09State PLAN_* / EP_* constants, the episodePlan ei / ef
  row expressions, the episodeApply mark write, the Main markAppend wiring): PASS; self-test: 6 seeded mismatches (5
  constants, 1 Main column) all FAIL.

TOKEN START REVIEW: Main PASS / exact UNKNOWN; headroom UNKNOWN; status UNKNOWN; this batch: R3-B1 wiring Probe only;
W08Touch /6 (mergePlanBuild 10 -> 14, splitPlanBuild 16 -> 20 params), W08Runtime /16 (4 primitive-array references in
ShadowContext), Main (ei / ef allocation moved before ShadowContext.new, 4 references passed, 2 imports); new cross-library
import 0 (edges unchanged, versions only); foreign Production type 0; huge UDT 0; `.copy` 0; tuple 0; projected state copy 0;
plan rebuild 0; Merge / Split rule duplication 0; Main business logic 0; Probe required YES.

Probe body: private `projectedScratchProbeRaw(ei, ef, pI, pF)` in W08Touch reads sizes, strides and the representative
columns (plan row, mark row, flags bit 32, Episode max, plan touchNo / contact bottom) with bounds checks and na guards,
writes nothing, returns >= 0; both plan builds AND it into their existing `ok` (always true, so the plans are unchanged).
No Merge / Split rule change. Check `r3b1p_det.py`: well-formed, empty Episode, empty TouchStart plan, exact stride, short
ei / ef / plan ints / plan floats, na arrays, non-destructive: 10/10 (0.1 s). The existing plan code is otherwise
byte-identical (diff: helper + constants + two signatures + two `ok` lines; W08Runtime: import, 4 fields, 2 call sites).

| ID | Module | Change | Before | After | Delta | Status |
|---|---|---|---|---|---|---|
| R3B1P | W08Touch /5 -> /6, W08Runtime /15 -> /16, Main | 4-array wiring Probe (read-only) | PASS (exact UNKNOWN) | PASS (exact UNKNOWN) | UNKNOWN | APPROVED (R3-B1 wiring architecture) |

### R3-B1 body: projected mark injection (W08Touch /7, W08Runtime /17; W09State /22 kept)

TOKEN START REVIEW: Main PASS / exact UNKNOWN; headroom UNKNOWN; status UNKNOWN; added: the projected mark injection inside
W08Touch; high-cost candidate: the Merge / Split plan injection; Probe: R3-B1 wiring Probe PASS; new cross-library import 0;
foreign Production type 0; huge UDT 0; `.copy` 0; huge tuple 0; mass array forwarding 0 (the 4 approved primitive arrays);
projected state copy 0; plan double build 0; Merge / Split rule duplication 0; Main business logic 0; policy: the smallest
change inside the existing W08Touch canonical path.

Implementation (W08Touch only; W08Runtime /17 and Main change only the import versions):
- `keyCompareRaw` = the one canonical compare body (time, baseSeq, Side rank, contact bottom, contact top); `rowCompareRaw`
  (ring / Merge plan orders) and `projCompareRaw` (projected rows) call it. `mergeRowCompareRaw` and the wiring Probe helper
  are removed.
- Projected rows: x >= 0 = ring row, x <= -2 = the new mark of TouchStart plan row -x - 2. Accessors `projIntRaw` /
  `projFloatRaw`; `rowPushRaw` pushes either kind whole (new mark: plan payload, markAppend WeakByDepth false / max 0.0) and
  then carries the Episode WeakByDepth (flags bit 32) / max (ef col 4) on the Episode's mark (`projEpisodeRaw`: Side slot,
  Core ID, generation, touchNo; A = ring row col 8 inside the slot block with the ring owner; B = plan row col 7 with the
  plan Core slot / Core ID / side / generation / touchNo).
- (A) source ring projected append: `projDropRaw` = max(0, count + appends of (slot, Core ID) - ring capacity); the oldest
  logical rows of ring rows + appends (plan order) are gone and each truncates its own Side (markAppend semantics).
- (B) Merge: per source and Side the projected history (surviving ring rows, then this Side's new marks) runs through the
  unchanged steps: exact range intersection, per-Side dedupe (time, bottom, top) in source priority, canonical insertion,
  shared cap drop of the oldest rows (each drop truncates its Side); source truncation (ring flag or eviction) OR-ed.
- (C) Split: the source logical list loses its pushed-out rows (truncating their Sides), the new marks are appended in plan
  order; no dedupe, no re-sort; the child cap check is unchanged (a child above the cap FAILS; nothing is trimmed).
- Contract: one more constant `PI_CORE_ID = 2` (an existing TouchStart plan column; no column / stride change); the
  conformance check covers it (PASS).

Deterministic `r3b1_det.py` (reference = W08Touch /6 plans on a fixture ring to which this bar's F0 writes were applied
first: markAppend of every plan row in plan order, then the episodeApply mark write on the Episode's mark when its key still
matches; optimized = /7 on the untouched ring with ei / ef / plan ints / floats; compared: return values, every plan array
(row count, order, 11 fields, offsets / counts, truncated S / R), and the /7 input ring unchanged): 29/29 in 0.5 s — source
(append, not full, full, oldest Support / Resistance dropped, A WeakByDepth, A max, key mismatch), Merge (intersect,
non-intersect, absorbed A update, dedupe collision, canonical insertion, shared cap drop, dropped Side truncated, source
truncation inherited), Split (one child, multiple children, no child, logical order, no dedupe, cap exact, two appends at
cap - 1, source truncation inherited), atomic (Merge + Split, ring unchanged), inert (Episode Core outside every relation =
/6), plus 27-29 added after mutants M2 / M4 / M5 survived the first 26 (eviction outside the winner range truncates, a new
Resistance mark inside the Support range stays out of the Support rows, same time -> baseSeq before bottom). Mutants 5/5
killed (M1 Split without source eviction -> the child goes above the cap and the Split FAILS, never trimmed; M2 Merge without
eviction; M3 Episode fields not carried; M4 no Side filter; M5 compare without baseSeq). random 0.

Static: imports 0 -> 0 (W08Touch leaf; W08Runtime edges unchanged); exports 10 -> 10 (same names); types 3 -> 3; `.copy` 0;
tuple unpacks 3 -> 3; `array.new` 30 -> 30; functions 20 -> 27 (private helpers); no write to the ring / ei / ef / plan
ints / floats on the plan path; the Split cap FAIL line kept; one compare body. Source proxy (reference only): W08Touch
6,918 -> 8,344.

| ID | Module | Change | Before | After | Delta | Status |
|---|---|---|---|---|---|---|
| R3B1 | W08Touch /6 -> /7, W08Runtime /16 -> /17, Main imports | projected mark injection | PASS (exact UNKNOWN) | 1,003,009 (CE10216) | UNKNOWN (Before exact unknown) | TV Gate FAIL; semantics KEEP / FROZEN (det 29/29, reference parity PASS); R3-B1 NOT COMPLETE; R3-B2 forbidden |

### R3-B1 TradingView Gate: FAIL (TOKEN_PROBE)

Main 1,003,009 / 1,000,000 (CE10216); headroom -3,009; status RED (> 975,000: no new semantic Batch; compress first).
R3-B1 semantics FROZEN at `d7b5d9d` (backup `backup/w09-b07-r3b1-token-gate`). Failure class TOKEN_PROBE: the wiring Probe
measured the 4-array forwarding only, not the injection body (private helpers, Merge / Split projected processing,
canonical row handling). Next: TOKEN_REFACTOR_ONLY, one structure at a time (refactor -> short equivalence -> publish ->
Main compile -> compiled value); CE10216 still showing a number means every step is measured exactly.

### Token refactor audit after R3-B1 (no Production change)

W08Touch /7 private helpers (params / call sites / body lines): keyCompareRaw 10 / 2 / 9, rowCompareRaw 7 / 1 / 1 (pure
pass-through to keyCompareRaw), projIntRaw 4 / 11 / 7, projFloatRaw 4 / 10 / 8, projCompareRaw 5 / 2 / 3, projPlanRowsRaw
2 / 3 / 3, projAppendsRaw 5 / 2 / 12, projDropRaw 5 / 2 / 3, projLogicalRaw 3 / 1 / 7, projEpisodeRaw 5 / 1 / 30, rowPushRaw
17 / 2 / 33 (planRowCompareRaw 3 / 2 / 3, existing).

| # | Candidate | Params | Call sites | Forward-only | Body | Semantic risk | Publishes |
|---|---|---|---|---|---|---|---|
| T1 | W08Touch `rowCompareRaw` (pure pass-through; planRowCompareRaw calls keyCompareRaw directly) | 7 | 1 | 7 | 1 line | LOW | 2 (W08Touch /8 + W08Runtime /18) |
| T2 | W08Touch `projEpisodeRaw` inlined into `rowPushRaw` | 5 | 1 | 5 | 30 lines (renames `e`, `o`) | LOW-MEDIUM | 2 |
| T3 | W08Touch `projLogicalRaw` inlined into the Merge source loop | 3 | 1 | 3 | 7 lines | LOW | 2 |
| D1 | W03EMsa `run` -> `w03StageEMaRaw` inline | 51 | 1 | 49 (+ 2 journal counters) | 33 lines, 22 locals, 2-value tuple | LOW | 1 (W03EMsa /8) |
| D2 | W03EMsa `run` -> `w03StageESwingRaw` inline | 74 | 1 | 72 (+ 2) | 60 lines, 29 locals, 4-value tuple | LOW-MEDIUM | 1 |
| D3 | W03EMsa `run` -> `w03StageEAccumRaw` inline | 88 | 1 | 86 (+ 2) | 98 lines, 50 locals, 17-value tuple | MEDIUM | 1 |

D1-D3 pattern (checked): the callee opens with `journalCountNow = journalCountIn` / `journalInvariantViolationNow =
journalInvariantViolationIn` (the caller's own `journalCountNow` / `journalInvariantViolationNow`), reads the *In params only
there, and the caller writes the returned values straight back; inlined, the body updates the caller's two variables
directly (same values, same order), and the signature, the argument list and the tuple disappear.

RECOMMENDED_NEXT_TOKEN_REFACTOR = D1 (`w03StageEMaRaw` inline, W03EMsa /8, Main pin). Reason: LOW risk (49 identity
arguments, the two counters are the caller's own variables, no allocation / var / history / break, one tuple removed), one
publish, 51 parameters + 51 forwarded arguments + a tuple removed, and while Main is still CE10216 the compile shows the
exact value, so the effect of an inline is measured for the first time. The R3-B1 boundaries T1-T3 are LOW risk but remove
only 3-7 parameters each and cost two publishes; they are kept as a later bundle (not dropped).

### D1: inline `w03StageEMaRaw` into W03EMsa `run` (W03EMsa /8, Main W03EMsa /7 -> /8; TOKEN_REFACTOR_ONLY)

T1 / T2 / T3 (W08Touch internal boundaries) = DEFERRED_BUNDLE (small single removals, two publishes each; to be done later
as one W08Touch cleanup). D2 / D3 not started.

- The helper body (30 lines, same indent) moved verbatim to its single call site; its two opening lines
  (`journalCountNow = journalCountIn`, `journalInvariantViolationNow = journalInvariantViolationIn`), its
  `[journalCountNow, journalInvariantViolationNow]` return and the caller's two write-backs removed: the body now updates
  the caller's own two variables (the *In params were read only by those two lines; same values, same order). No rename
  (the only shared names are exactly those two variables).
- Static: `w03StageEMaRaw` code references 0; functions 15 -> 14; tuple unpacks 7 -> 6; imports / types / `array.new` /
  `.copy` 0 -> 0; diff = the deleted helper (37 lines) and the replaced call (3 -> 32 lines); the moved body is identical;
  removed: signature 51 parameters, forwarding 51 arguments, one 2-value tuple.
- Test `d1_det.py` (old call + write-backs with the real old helper vs the new block, extracted from the files, same `run`
  environment; recording stubs: originKeyComputeRaw, maSlopeDirRaw, originLookupUniqueRaw, journalAppendRaw): two new
  Roots, unchanged Roots, price / slope (na -> value) / open time / close time change, lookup violation stop, incoming
  violation, pending row, MA disabled, na EMA2000, unusable source / mintick 0: 12/12 (0.06 s); mutants 2/2 killed. R3-B1
  29 not rerun (unchanged). Source proxy (reference only): W03EMsa 7,038 -> 6,637.

| ID | Module | Change | Before | After | Delta | Status |
|---|---|---|---|---|---|---|
| D1 | W03EMsa /7 -> /8 (Main pin) | inline `w03StageEMaRaw` | 1,003,009 (CE10216) | 1,002,458 (CE10216) | -551 | LOW; ADOPTED (semantic risk LOW, change 0; 51-param signature, 51 forwarded args and one tuple removed) |

Status after D1: Main 1,002,458 / 1,000,000, headroom -2,458, RED (R3-B2 and new semantic Batches forbidden; TOKEN_REFACTOR_ONLY
continues). First exact measurement of a single-call inline: 51 parameters + 51 arguments + a 2-value tuple = -551 compiled.

### D2 pre-implementation re-audit on W03EMsa /8: CHANGED -> not implemented (STOP)

`w03StageESwingRaw` (74 params, 1 call site, 72 identity arguments + the two journal counters, 29 locals, 4-value return
`[journalCountNow, journalInvariantViolationNow, out15m, out1h]` -> caller `[swingJournalCount, swingViolation, swing15mOut,
swing1hOut]`, journal / Stage E order unchanged). New since the /7 audit: two more locals collide at the call site,
`usable` and `stopped`. D1 put the MA block's top-level locals (`usable`, `stopped`, `k`) into `run`'s top-level scope, and
the Swing body declares its own top-level `bool usable` / `bool stopped` (Swing: `stopped = not cfgUseSwing`); inlined as is
they would be re-declared in the same scope. Proposed resolution (needs approval): rename the Swing block's two locals
(e.g. `swingUsable`, `swingStopped`; declaration points and lifetimes unchanged), and map its outputs by renaming `out15m` /
`out1h` to the caller's `swing15mOut` / `swing1hOut` (their two declarations become the caller's; the journal pair works as
in D1). Every other shared name (`lookupViolation`, `newRow`, `originKey`, `pendingRow`, `pointTick`, `rootSlot`, `subtype`)
lives in sibling nested blocks (no overlap).

### D2: inline `w03StageESwingRaw` into W03EMsa `run` (W03EMsa /9, Main W03EMsa /8 -> /9; TOKEN_REFACTOR_ONLY)

Approved resolution applied: Swing block only, whole-word code-only renames `usable` -> `swingUsable` (2), `stopped` ->
`swingStopped` (3), `out15m` -> `swing15mOut` (2), `out1h` -> `swing1hOut` (2); the MA block's `usable` / `stopped` / `k`
untouched. The body (57 lines) sits at the old call site: `swing15mOut` / `swing1hOut` are declared there (where the tuple
was), with the old initial values and update order; the journal pair is the caller's own (the helper's two copy-in lines,
its 4-value return and the two write-backs removed).

- Static: `w03StageESwingRaw` code references 0; `out15m` / `out1h` 0; in the Swing block `usable` 0 / `stopped` 0
  (`swingUsable` 2 / `swingStopped` 3); the MA block identical to /8; functions 14 -> 13; tuple unpacks 6 -> 5; imports / types
  / `array.new` / `.copy` 0; diff = the deleted helper (63 lines incl. comment) and the replaced call (3 -> 60 lines); the
  moved body equals the old body after the reverse rename (57 lines); removed: signature 74, forwarding 74, one tuple.
- Test `d2_det.py` (the /8 segment MA block + Swing call + write-backs with the real old helper vs the /9 segment MA block +
  inlined Swing block, same `run` environment; recording stubs for the 7 callees; outputs include the MA block's usable /
  stopped / k): normal, no Swing, 15m / 1h not adoptable, Resistance-only / Support-only swings, TF bit on / off, pending
  row with predicted slot / id and a journal TF merge row, unusable inputs, Swing lookup violation, violation from the MA
  block, MA off / MA full then Swing (no interference), mintick 0, mixed journal growth: 15/15 (0.16 s; first run had 4
  fixture errors: the append stub did not grow the parallel journal arrays, both versions failed identically; fixed).
  Mutants 2/2 killed (stop flag left as the MA `stopped`; 1h output not updated). R3-B1 29 not rerun. Source proxy: 6,637
  -> 6,113.

| ID | Module | Change | Before | After | Delta | Status |
|---|---|---|---|---|---|---|
| D2 | W03EMsa /8 -> /9 (Main pin) | inline `w03StageESwingRaw` | 1,002,458 (CE10216) | 1,001,847 (CE10216) | -611 | LOW; ADOPTED |

Status after D2: Main 1,001,847 / 1,000,000, headroom -1,847, RED (leaving RED needs >= 26,847; GREEN >= 51,847). Policy
change: MICRO TOKEN REFACTOR stopped, HIGH-IMPACT STRUCTURAL REFACTOR. D3 = DEFERRED_HIGH_IMPACT_PHASE; T1 / T2 / T3 =
DEFERRED_BUNDLE (kept, not implemented).

### GT-5A audit: W03Apply `applyThroughF4` single-call helper family (no Production change)

All private helpers called by `applyThroughF4` (each has exactly one call site in the whole file, inside the op dispatch of
the group / row loop; no var / history / ta / request / break / continue / allocation in any body; no helper assigns its
parameters; every other argument is the same-named `applyThroughF4` parameter):

| Helper | Params | Forward-only | Mapped (caller value) | Return | Body lines | Locals | Writes | Collisions at the call site (renames) | Inlined max nest | Class |
|---|---|---|---|---|---|---|---|---|---|---|
| newRootApplyRaw | 106 | 104 | `nextRootId` <- `nextRootIdLocal` (hazard: `applyThroughF4` has its own `nextRootId` parameter, so every use must be substituted), `journalRow` <- `row` | `[result, nextRootIdOut]` -> `[newSlot, newNextRootId]` | 91 | 30 | root arrays (categories, confirmed times, directions, FVG fresh / Broad / dynamic / range flags, labels, ...), journal target slot / expected ID | ok, category, direction (3) | 32 (8 levels) | SAFE_INLINE |
| fvgInvalidateApplyRaw | 87 | 86 | `journalRow` <- `row` | `structuralDetached and stateMoved` -> `ok` | 53 | 17 | rootStates (via set helpers) | ok, direction (2) | 28 (7) | SAFE_INLINE |
| fvgFreshEndApplyRaw | 87 | 86 | `journalRow` <- `row` | `detached` -> `ok` | 51 | 16 | rootFvgFreshFlags | ok, direction (2) | 32 (8) | SAFE_INLINE |
| maUpdateApplyRaw | 74 | 73 | `journalRow` <- `row` | `ok` -> `ok` | 36 | 10 | confirmed / origin times, last update seqs, price order | ok, rootSlot, subtype (3) | 28 (7) | SAFE_INLINE |
| swingTfMergeApplyRaw | 67 | 66 | `journalRow` <- `row` | `ok` -> `ok` | 39 | 9 | rootSwingTfMasks | ok (1) | 32 (8) | SAFE_INLINE |
| timeHlLabelApplyRaw | 67 | 66 | `journalRow` <- `row` | `ok` -> `ok` | 30 | 7 | rootLabelMasks | ok (1) | 24 (6) | SAFE_INLINE |
| rootRetireApplyRaw | 67 | 66 | `journalRow` <- `row` | `retired` -> `ok` | 44 | 11 | rootStates | ok (1) | 32 (8) | SAFE_INLINE |
| pendingNewFvgRowRaw | 8 | 7 | `freshRow` <- `row` (its own local `row` collides) | `[matchRow, matchCount]` | 13 | 6 | none | direction, row (2) | 36 (9, above the file max 32) | SAFE_INLINE (excluded: 8 params, raises the max nest) |

NOT_SAFE: none. NOT_SINGLE_CALL: none among the direct helpers (the second-level chain `newRootApplyRaw` -> `rootAllocSlotRaw`
(46) -> `rootResetSlotRaw` (42) is single-call too; a later GT-5B candidate, not in GT-5A).

RECOMMENDED_GT5A_BUNDLE = the 7 apply helpers (newRoot, fvgInvalidate, fvgFreshEnd, maUpdate, swingTfMerge, timeHlLabel,
rootRetire), each body moved verbatim into its own dispatch branch (sibling branches; no cross-helper interaction):
removed parameters 555, removed forwarding 555, removed tuples 1 (newRoot), body lines 344, renames 13 (the colliding callee
locals only; each result goes back through one `ok :=` / tuple-equivalent assignment at the old position), substitutions
`journalRow` -> `row` (7 helpers) and `nextRootId` -> `nextRootIdLocal` (newRoot), max nest 32 = the current file max
(no increase), W03Apply /4 -> /5 (unused) + Main pin: 1 publish, semantic risk LOW-MEDIUM (mechanical, but 344 lines and 21
name edits). Journal / apply / F-stage order, fail-closed, rollback, masks, slots, IDs, prices, ticks untouched.

Measured context (not an estimate of GT-5A): D1 removed 51 params -> -551, D2 74 params -> -611. At those measured rates the
555-parameter bundle would not by itself reach the 26,847 needed to leave RED. The one measured large lever so far is the
cross-library import / foreign-type cost (INC-1: +112,873 for two imports into W09State). The existing library-to-library
imports (W08Runtime -> W08Core /18 + W08Touch /7, W06 -> W05 /6, W05 -> W07 /10) are therefore candidates for one
attribution Probe (requires approval).

### HIGH-IMPACT TOKEN ATTRIBUTION: existing cross-library import cost (one Probe, one compile)

GT-5A (7 apply helpers, 555 params / 555 forwarding / 1 tuple) = APPROVED_DEFERRED (kept; resumed if the attribution does
not open a larger structural change).

Static comparison of the existing library-to-library edges (Main imports: W03F0, W03Apply, W03ETimeFvg, W06, W07, W08Core,
W08Touch, W08Runtime, W03EMsa, W09State):

| Edge | Target size (functions / exports / exported types / source) | Used by the importer | Foreign types | Main also imports the target | Probe cost / contamination |
|---|---|---|---|---|---|
| A: W08Runtime -> W08Core /18, W08Touch /7 | 49 / 31 / 3 / 23,524 and 27 / 10 / 3 / 8,344 | 22 + 6 functions, 40 call sites | W08Store, CoreRegistryStore, PendingTopologyStore, TouchPlan, SplitTouchPlan, TouchRing; exported ShadowContext has foreign fields (the INC-1 pattern) | yes (both) | no clean Probe: removing the edge means rewriting the W08Runtime plan / commit path and its exported types |
| B: W06 -> W05 /6 | 27 / 3 / 0 / 23,575 | 3 functions, 3 call sites | none | no | 1 publish (W06 with W05 merged in), but the W05 -> W07 edge would move to W06 |
| C: W05 -> W07 /10 | 22 / 14 / 0 / 11,148 | 2 functions (closure of 3), 4 call sites | none | yes (duplicate import, as in INC-1) | 2 probe publishes, same code reachable, cleanest attribution |

RECOMMENDED_IMPORT_PROBE = C (W05 -> W07). It is the INC-1 situation (a library Main already imports, imported again by a
worker) without foreign types, the code stays byte-for-byte the same logic, and no module loses anything else.

Probe C (Production files unchanged; separate probe library names, no Production version used):
- `token_probes/R3B1C_W05Candidate_Worker_NoW07Probe.pine` = W05 /6 with no W07 import; the 4 `W07Fvg.` call sites call
  verbatim copies of the W07 closure `fvgIntervalOrderBuild`, `fvgIntervalQuery`, `fvgIntervalLowerBoundRaw` (export
  keyword removed) placed before their first use (originally appended at the end: see PROBE_BUILD_ERROR below); one constant added (`FVG_INTERVAL_BUILD_INVALID_INPUT = 1`, W07's value;
  `FVG_INTERVAL_BUILD_OK`, `ID_NONE`, `SLOT_INVALID` already equal). Library name `ZoneEngineV2_W05Candidate_Worker_NoW07Probe`.
- `token_probes/R3B1C_W06Component_Worker_NoW07Probe.pine` = W06 /23 with only the library name and the W05 import changed
  (-> `ZoneEngineV2_W05Candidate_Worker_NoW07Probe/1`).
- `token_probes/R3B1C_Rebuild_Main_Probe.pine` = Main with only two import lines changed: W06 -> the W06 probe /1, and the
  ballast W03EMsa /9 -> /7.

Reachability audit: W05 / W06 reachable code unchanged (the same functions, the 3 W07 functions now private in W05); W07
reachable from Main 22 -> 21 (only `fvgIntervalOrderBuild` leaves W07); `fvgIntervalQuery` and `fvgIntervalLowerBoundRaw`
stay reachable inside W07 through Main's W07 roots, so the Probe holds them twice (a bias against the saving: the measured
delta = edge cost - that duplicate); nothing else in any module changes; no stub, no constant folding.

PASS-only information check and the ballast: baseline 1,001,847 is only 1,847 over the limit, so a plain Probe would PASS
for any delta above 1,847 and tell nothing more. The probe Main therefore pins W03EMsa /7 instead of /9: measured exactly
+1,162 with every other pin identical (1,003,009 at D1's Before vs 1,001,847 now; assumed additive, a different library).
Reading: Probe = 1,003,009 - delta. CE10216 with a number -> delta = 1,003,009 - Probe (exact; LOW if < 3,000). PASS ->
delta > 3,009 (at least MEDIUM; the exact size stays unknown).

User decision (Probe C approved): the +1,162 additivity is NOT used. The baseline is the historical exact 1,003,009
(R3-B1 semantics complete + W03EMsa /7), allowed only if a machine audit proves the probe configuration differs from
that configuration only by the W05 / W06 probe replacement.

| ID | Probe | Change | Baseline | Probe compiled | Delta | Status |
|---|---|---|---|---|---|---|
| IP-C | W05 -> W07 import removed (probe libraries), Main pins = the 1,003,009 configuration (W03EMsa /7) | 2 probe publishes + 1 Main compile | 1,003,009 (historical exact, machine-audited, see below) | PASS (< 1,000,000; W05 probe /1 PASS, W06 probe /1 PASS) | net > 3,009 (exact UNKNOWN; effect >= MEDIUM) | attribution only, never adopted; Production unchanged (Main 1,001,847 RED) |

Baseline match audit (machine, before the TV run): PASS.
- `git diff d7b5d9d:ZoneEngineV2_Rebuild.pine token_probes/R3B1C_Rebuild_Main_Probe.pine`: exactly 1 changed line
  (W06Component /23 -> `ZoneEngineV2_W06Component_Worker_NoW07Probe/1`); no other code or pin line differs, so the
  Main semantic wiring equals the 1,003,009 Main.
- Probe Main pins: W03F0 /5, W03Apply /4, W03ETimeFvg /3, W06 probe /1 (= W06 /23 equivalent), W07Fvg /10, W08Core /18,
  W08Touch /7, W08Runtime /17, W03EMsa /7, W09State /22 (the same published versions the 1,003,009 compile used).
- `git diff d7b5d9d HEAD` on W05 / W06 / W07 / W08Core / W08Touch / W08Runtime / W09State / W03F0 / W03Apply /
  W03ETimeFvg sources: empty (W03EMsa changed only by D1 / D2 = /8, /9, which the probe does not pin).
- W06 probe vs W06 /23 source: only the library name and the W05 import line differ.
- W05 probe vs W05 /6 source: library name, W07 import removed, 4 code call sites `W07Fvg.f` -> `f`, one constant
  `FVG_INTERVAL_BUILD_INVALID_INPUT = 1` (= W07 value), 3 appended functions byte-identical to W07 /10 apart from
  `export` (checked by script); the 3 remaining `W07Fvg.` occurrences are comments; ID_NONE / SLOT_INVALID /
  FVG_INTERVAL_BUILD_OK equal W07's values.
=> The only difference from the 1,003,009 configuration is the W05 / W06 probe boundary. Baseline 1,003,009 is valid.

Result handling (fixed before the run): CE10216 -> delta = 1,003,009 - Probe; >= 20,000 VERY_HIGH, 10,000-19,999 HIGH,
3,000-9,999 MEDIUM, < 3,000 LOW. LOW -> import redesign deferred, back to GT-5A. MEDIUM -> compare boundary removal with
GT-5A. HIGH+ -> import boundary redesign first. PASS -> "< 1,000,000, delta > 3,009, effect >= MEDIUM, exact UNKNOWN";
no further Probe and not straight back to GT-5A: design audit for removing the W05 -> W07 boundary in Production with
zero semantic change and a single semantic authority (owner move, worker split, safe inline, dependency direction);
a permanent copy of the 3 functions is not adopted automatically (double authority). The duplicated W07 functions
bias the delta downward; the result is not over-read. GT-5A stays APPROVED_DEFERRED.

PROBE_BUILD_ERROR (not a token result; IP-C stays unmeasured, baseline stays 1,003,009): the first W05 probe publish
failed with CE10245 ("A library must contain at least one exported function, method, or type").
- Export audit: W05 /6 has 3 exports (`selectBothSides`, `compareCandidates`, `selectComponentBothSides`, the ones W06
  calls); the probe had the same 3 with identical signature lines. The export-strip step touched only the 3 W07 copies.
- Construction defect found: the 3 private copies were appended at the end of the file, after their callers (first use
  at source line 324); Pine needs a user function declared before its use, so the probe could not compile, and a
  library that does not compile reports no exported function. Fix: the same 3 bodies moved above the first W05 function
  (after `type CandidateCtx`), in W07's order (LowerBoundRaw, OrderBuild, Query); nothing else changed.
- Static gate after the fix: export count 3 = 3, names and signature lines identical, `W07Fvg.` code references 0 (3
  comment mentions), no import, the 3 copies byte-identical to W07 /10 apart from `export` and private, each declared
  before its first use, the constants they use (ID_NONE, SLOT_INVALID, FVG_INTERVAL_BUILD_OK / _INVALID_INPUT) declared
  above them; the diff against W05 /6 is only library name, W07 import, the 4 call sites (`W07Fvg.` prefix only), 1
  constant and the 189-line block. W06 probe and Main probe unchanged. Probe library /1 is still unused.

### IP-C result (TV): PASS
- W05 probe /1 PASS (after the PROBE_BUILD_ERROR fix), W06 probe /1 PASS, Main probe PASS (< 1,000,000; no number).
- Historical exact baseline 1,003,009 -> Import C net delta > 3,009 compiled tokens; effect MEDIUM or more; exact UNKNOWN.
  The delta is net of the duplicate `fvgIntervalQuery` / `fvgIntervalLowerBoundRaw` the probe held twice; not over-read.
- Probe result only: the probe libraries are not adopted; Production Main stays 1,001,847 (RED). No further Probe.
- Clearly larger than D1 (-551) / D2 (-611). GT-5A stays APPROVED_DEFERRED; next = Production design audit below.

### IMPORT C PRODUCTION DESIGN AUDIT (design only; no code change, no Probe)

Facts (source, current Production):
- Authority today: W07Fvg /10 owns `fvgIntervalLowerBoundRaw` (private), `fvgIntervalOrderBuild` (export),
  `fvgIntervalQuery` (export). Constants used: ID_NONE, SLOT_INVALID, FVG_INTERVAL_BUILD_OK / _INVALID_INPUT. No UDT.
- W07-internal use: `fvgIntervalQuery` <- `freshFacts` (Stage E fresh match; reachable from Main through
  `stageEFreshInversePrepare`); `fvgIntervalLowerBoundRaw` <- `fvgIntervalQuery`. `fvgIntervalOrderBuild` has no W07
  caller (only W05 and old pinned harnesses).
- W05 use: 4 call sites in 2 separate functions: `candFvgIndexedMatchesRaw` (OrderBuild + Query) and
  `candEnumerateStageBRaw` (OrderBuild + Query).
- Main uses W07 directly (`stageEFreshInversePrepare`, `inverseStageFCommit`, `inverseStageFCommitWithConfirm`,
  `freshIndexSyncFromJournal` x2); Main never calls the 3 interval functions.
- W07: 1,112 lines, 14 exports, 0 types. W05: 2,325 lines, 3 exports, 1 private type (CandidateCtx).

Dependency graph (Production now):
  Main -> W03F0, W03Apply, W03ETimeFvg, W03EMsa, W09State
  Main -> W06 -> W05 -> W07          (edge under study: W05 -> W07)
  Main -> W07
  Main -> W08Core, W08Touch, W08Runtime -> W08Core, W08Touch

| Item | A: new Interval worker (WI) | B: authority to W05, W07 -> W05 | C: W07 inlines, authority W05 | D: W05 physical inline, W07 keeps authority | E: other |
|---|---|---|---|---|---|
| graph change | W05 -> W07 removed; W05 -> WI, W07 -> WI added | W05 -> W07 removed; W07 -> W05 added | W07 still needs Query semantics -> needs W05 import (= B) or its own copy | W05 -> W07 removed | see below |
| cycle | 0 | 0 (W05 no longer imports W07) | 0 / n.a. | 0 | - |
| Main reachable | same functions; the 3 now in WI (reached via W07 and W05) | W05 reached twice (via W06 and via W07) | - | 3 bodies in W07 + inlined copies in W05 | - |
| nested import of a library Main already imports | none (WI not imported by Main) | yes: W05 behind W07 and W06 (same shape as the removed edge, larger library, has a type) | - | none | - |
| foreign type | 0 (arrays / ints only) | CandidateCtx is private, but W07 would sit on a 2,325-line library | - | 0 | - |
| exports | WI 2-3 new; W07 loses 2 | W05 +2; W07 -2 | - | 0 new | - |
| signature / forwarding | unchanged (same parameter lists, calls re-prefixed) | unchanged | - | inline removes 2 signatures x 2 call paths | - |
| duplicated logic | 0 | 0 | yes (REJECT) | yes: OrderBuild + Query bodies into 2 W05 functions (2 copies) and Query / LowerBound also stay in W07 | - |
| authority count | 1 (WI) | 1 (W05) | 2 | 2 (REJECT, 9. condition) | - |
| publishes | WI /1, W07 /11, W05 /7, W06 /24 (+ Main pins) | W05 /7, W07 /11, W06 /24 (+ Main) | - | - | - |
| files changed | 5 (WI new, W07, W05, W06 pin, Main pins) | 4 | - | - | - |
| semantic risk | LOW (bodies moved verbatim, call prefix only) | LOW (verbatim) | - | - | - |
| maintenance risk | LOW (FVG interval index has its own owner) | MEDIUM-HIGH (FVG index owned by the Candidate library; W07 depends on W05) | HIGH | HIGH | - |
| compiled-token risk | UNKNOWN: Probe C removed the edge without adding one; A adds 2 edges to a 3-function type-free library | HIGH: recreates the cross edge with a larger library | - | - | - |

E (other) checked and rejected:
- E1 pass precomputed orders into W05 from W06 / Main: the order sets are built from W05-local scratch
  (indexable slots, fvgScratch) mid-selection -> changes W05 signatures / timing; Main business logic risk. REJECT.
- E2 move `candFvgIndexedMatchesRaw` / `candEnumerateStageBRaw` into W07: they take CandidateCtx (would become a foreign
  type, INC-1 pattern) and split Candidate authority. REJECT.
- E3 authority in a library both already import: W05 and W07 share no dependency. n.a.
- E4 W07 keeps only Query / LowerBound, W05 owns OrderBuild alone: W05 still needs Query -> edge stays or copy. REJECT.
- D (special check, section 9): W05 has 2 separate call paths, each using OrderBuild and Query, so a single inline
  point does not exist; and W07 must keep Query / LowerBound for `freshFacts`, so any W05 inline is a second copy of
  that logic. REJECT (authority 2, duplication > 0).

Condition check (section 8) for A: semantic authority 1, logic duplication 0, cycle 0, Main business logic 0, new
foreign UDT dependency 0, state / history semantics change 0, FVG interval semantics change 0 -> all satisfied.
B satisfies authority / duplication / cycle but inverts ownership and re-creates the measured edge shape -> not chosen.

RECOMMENDED_IMPORT_C_PRODUCTION_DESIGN = A (dedicated `ZoneEngineV2_W07Interval_Worker` owning the 3 functions and
their 2 status constants; W07 and W05 import it; bodies verbatim; only the `W07Fvg.` / local call prefix changes).
Open risk stated, not estimated: Probe C measured removal of the W05 -> W07 edge with no new edge; A adds two edges to a
tiny, type-free, 3-function library. Its compiled effect is UNKNOWN until the implementation compile; if Main does
not improve, the pins roll back (Production versions untouched).

GT-5A comparison (structure, not compiled estimate):
- GT-5A: one module (W03Apply /5), 7 single-call helpers, 555 params / 555 forwarded args / 1 tuple removed, 13
  renames (nextRootId hazard), semantic risk LOW-MEDIUM, 1 publish + Main pin, maintenance neutral.
- Import C (A): library boundary change, 0 renames, verbatim bodies, semantic risk LOW, 4 publishes + Main pins,
  maintenance improves (FVG interval index gets one owner, W05 no longer depends on the whole W07).
- The only measured evidence is Probe C (> 3,009 for removing the edge); GT-5A is unmeasured. Order stays: Import C
  design A first (if approved), GT-5A APPROVED_DEFERRED.

### IMPORT C A: Production implementation (TOKEN_REFACTOR_ONLY; TV pending)

TOKEN START REVIEW: Main 1,001,847 / 1,000,000 (CE10216), headroom -1,847, RED. Planned: move the 3 FVG interval
helpers from W07 /10 to a new `ZoneEngineV2_W07Interval_Worker` /1 (single authority); W05 and W07 import it; W05 no
longer imports W07. Probe: done (IP-C PASS, > 3,009 for removing the edge); A adds 2 edges to a type-free 3-function
library (effect UNKNOWN until the compile). Main business logic added: NO.

Consumer check before the change (repo-wide grep of the 3 names): Production consumers = W05 only; Main direct = 0;
other Production workers = 0. Non-Production only: `ZoneEngineV2_W05Candidate_B19Probe`, the W07 B17 Fresh and B19
CandidateInterval conformance harnesses, all pinned to W07 /10 (immutable published version, unaffected).

Changes (publish order fixed):
1. `ZoneEngineV2_W07Interval_Worker.pine` /1 (new): header, the 4 constants (ID_NONE, SLOT_INVALID,
   FVG_INTERVAL_BUILD_OK / _INVALID_INPUT, W07 /10 values), and the 187-line W07 /10 block moved verbatim
   (`fvgIntervalLowerBoundRaw` private, `fvgIntervalOrderBuild` / `fvgIntervalQuery` exported as in W07 /10). No import,
   no type, no state.
2. W07 /11: block removed (no wrapper), `import ZoneEngineV2_W07Interval_Worker/1 as W07Interval`, the one internal call
   in `freshFacts` -> `W07Interval.fvgIntervalQuery`, header comment updated. W07 exports 14 -> 12. The now-unused
   FVG_INTERVAL_BUILD_* constants stay (no logic).
3. W05 /7: `W07Fvg /10` import -> `W07Interval /1`; the 4 call sites change only the prefix `W07Fvg.` -> `W07Interval.`.
4. W06 /24: W05 import /6 -> /7 only.
5. Main: W06 /23 -> /24, W07 /10 -> /11 only (W03EMsa stays /9). Rollback = W06 /23, W07 /10 (published, untouched).

Dependency graph after: Main -> W06 -> W05 -> W07Interval; Main -> W07 -> W07Interval; W08Runtime -> W08Core, W08Touch.

Static gate: PASS. W05 -> W07 = 0, W05 -> W07Interval = 1, W07 -> W07Interval = 1, W07Interval imports = 0; each of the
3 functions defined once (W07Interval), 0 in W07 / W05 (authority 1, duplicate body 0, wrapper 0); moved block
byte-identical to W07 /10; cycle 0; types in W07Interval 0 (foreign UDT 0); W07 diff = block + import + 1 call prefix
+ 2 comment lines; W05 diff = import + 4 prefix-only call sites; Main diff = 2 pin lines (business logic 0).

Deterministic (scratchpad `ic_det.py`, W07 /10 snapshot vs W07Interval /1, return + mutated output arrays compared):
15/15 PASS - OrderBuild empty / single / multi with duplicate prices / invalid len / duplicate slot / slot range /
rootId 0; Query equal boundary / multi range / none / lo > hi / na / empty index; LowerBoundRaw strict vs non-strict /
bad probed slot. Sensitivity: 2 mutants (strictGreater compare, bottom <= top check) each fail 1 case. random 0,
5k / 50k / 200k 0, R3-B1 29 cases not re-run, runtime < 1 s.

TV Gate: pending. PASS -> Import C A ADOPT; stop token refactors (GT-5A, D3, T1-T3, further import search DEFERRED);
return to W09 B07 R3-B2; no extra compression toward 975k / 950k. CE10216 -> record delta = 1,001,847 - After exactly,
STOP, no automatic GT-5A.

### IMPORT C A: TV Gate PASS -> ADOPT; token detour closed

TOKEN END REVIEW (Import C A): Before 1,001,847 (CE10216); After < 1,000,000 (PASS); Delta > 1,847 (exact UNKNOWN);
CE10216 RESOLVED; GREEN / YELLOW / RED UNKNOWN (not inferred from a PASS); Production semantic change 0; Main business
logic 0; authority duplication 0; new foreign UDT 0; TOKEN_REFACTOR_ONLY yes; long test no; > 5 min no; needless retest
no; rule violations 0.

| ID | Module | Change | Before | After | Delta | Status |
|---|---|---|---|---|---|---|
| IC-A | W07Interval /1 (new), W07 /11, W05 /7, W06 /24, Main pins | FVG interval helpers single authority in W07Interval; W05 -> W07 edge removed | 1,001,847 (CE10216) | < 1,000,000 (PASS) | > -1,847 (exact UNKNOWN) | ADOPTED |

Production pins (canonical): W03F0 /5, W03Apply /4, W03ETimeFvg /3, W06 /24 (-> W05 /7 -> W07Interval /1), W07 /11
(-> W07Interval /1), W08Core /18, W08Touch /7, W08Runtime /17 (-> W08Core /18, W08Touch /7), W03EMsa /9, W09State /22.

DEFERRED: GT-5A (APPROVED_DEFERRED), D3, T1-T3, further import search. Token refactor: STOP (no compression toward
975k / 950k). Only a new CE10216 after a semantic Batch reopens token work.

R3-B1: COMPLETE (semantics verified: det 29/29, reference parity, contract check; Production Main compile PASS with
W08Touch /7 / W08Runtime /17). R3-B1 semantics FROZEN; never redesigned for token reasons.
Next: W09 B07 R3-B2.

## W09 B07 R3-B2: resume after the token gate (scope restoration; no code change)

START GATE: branch `claude/w09-b07-redesign-v2`, local = remote = `752d206` (0 / 0), status clean. Production pins = the
Main PASS configuration: W07Interval /1, W07 /11, W05 /7, W06 /24, W08Core /18, W08Touch /7, W08Runtime /17, W09State /22,
W03EMsa /9 (+ W03F0 /5, W03Apply /4, W03ETimeFvg /3).

Recorded R3-B2 scope (this ledger, R3-B0 table rows marked R3-B2, and the R3-B1 v2 table):
1. Overlay switch: `episodeOverlayBuild(ei, out)` in the next unused W09State version (ints only, R1 signed encoding:
   FORCE_ACTIVE s / FORCE_INACTIVE -(s + 1) from ei col 9); Main passes it to
   `W08Runtime.planPassWithActiveTouchOverlay` instead of the TouchStart-only `touchStartPlanSideSlots`.
2. `episodeApply`: rows whose Core was consumed by an applied Merge / Split write no ring row (the W08 plan carries the
   mark, R3-B1) and clear their TSS.
3. The Main TouchStart `markAppend` loop skips consumed Cores: moved into W09State (`touchStartMarkApply`); Main keeps the
   EV_TOUCH_START rows.
4. Unchanged: C2 transfer plans (read projected values through the R3-A accessor), EV_WEAK_DEPTH / EV_TOUCH_RESET wiring.

Found in the current source, not decided by any recorded plan (needed once item 1 lets an Episode Core into the applied
topology, i.e. A: previous ActiveTouch -> Reset -> same-bar topology; B: TouchStart -> same-bar Reset -> same-bar topology):
- Q1 `touchStartPostPlanPreflight` (W09State /22) fails when an Episode Core or a TouchStart target Core is a busy old Core
  ("R2: an Episode never meets the applied topology"). Which busy relations become allowed (Merge absorbed / survivor,
  Split source, continuation old, freed / consumed READY) and for which Episodes (Reset only?) is not recorded.
- Q2 `phaseArmedTransferPreflight` reads the persistent Phase and fails on an ActiveTouch Side ("applied components hold
  none"). A-type sources are persistent ActiveTouch; their projected Phase after Reset is Waiting with ArmedFromSeq =
  currentSeq + 1. The R3-A accessor covers 6 values (TouchCount, LastNormalTouchTime, WeakByDepth, MaxDepthPct, SideFresh,
  ZoneFresh), not Phase / Armed. How the Phase / Armed transfer class and values of an Episode source are projected is
  not recorded.
- Q3 `touchStartApply` on a B Episode Core consumed the same bar (Phase / TSS copy / Armed detach / TouchCount on an old
  slot after commit): skip, or apply before the transfer; not recorded.
- Q4 TSS clear of a consumed Episode Core: `episodeApply` (item 2) vs the C2 completed-TSS clear in
  `touchHistoryTransferApply`, which captures valid TSS of freed / continuing sources; ownership of that clear and its
  order ("TSS cleanup after topology / C2") not recorded.
- Q5 continuation old (ownership kind 0: the Core continues as the target): is it "consumed" for items 2 / 3 or does the
  ring row / TSS stay on the continuing Core; not recorded.
Rule followed: the scope is not uniquely restorable -> no design invented, no code change; STOP for decisions Q1-Q5.

### R3-B2: same-bar topology (Q1-Q5 fixed by the user; design, W09State /24)

TOKEN START REVIEW: Main PASS (Import C A), exact UNKNOWN; headroom UNKNOWN; status UNKNOWN (not inferred from PASS).
Planned: W09State /24 (next unused: /23 is the rejected R3B0 Probe) + Main wiring (overlay scratch, one role scratch,
the TouchMark append guard, 3 changed call signatures, W09State pin). High-cost candidates: none (no import, no type,
no UDT copy, no tuple, no new array forwarding into W08). Probe: NO (small W09State helpers; the TV compile after the
batch is the gate). Main business logic added: NO (one `if` on a W09State-computed flag). Token policy: no token
refactor; CE10216 after the batch -> STOP.

Fixed semantics mapped onto the projected architecture (the plans are built before the W08 F0 from the projected Stage D
values, R3-A / R3-B1; persistent writes run after every F0 in the Main commit block; the fixed logical order 1-8 is the
projected order, the physical writes keep "persistent mutation 0 until all F0"):
1. Overlay: `episodeOverlayBuild(ei, out)` from ei col 9 (FORCE_ACTIVE s / FORCE_INACTIVE -(s + 1)); Main passes it to
   `planPassWithActiveTouchOverlay` instead of the TouchStart-only list. A no-Reset A stays ActiveTouch (persistent), a
   no-Reset B is FORCE_ACTIVE -> W08 PendingTopology (N1 / N2). A Reset A is FORCE_INACTIVE, a Reset B NO_OVERRIDE (its
   persistent Phase is Armed) -> its component may apply this bar (A1-A3 / B1-B3).
2. Busy (Q1): `touchStartPostPlanPreflight` keeps the busy set; an Episode / TouchStart Core in it passes only when its
   Episode Resets this bar and the Core has a topology role (below); a no-Reset Episode Core in the applied topology
   still fails (fail-closed guard of W08 Pending). The preflight writes the per-Core role into a caller scratch:
   0 none, 1 = old Core of a plain 1:1 continuation, 2 = Merge / Split old Core (survivor / Split continuation /
   absorbed / Split source) or freed.
3. Phase / Armed (Q2): `phaseArmedTransferPreflight(+ei)` accepts a persistent ActiveTouch Side whose Episode Resets
   (projected Waiting, CurrentTouchNo 0). The final Phase / Armed stays Stage J's (post-topology EffectiveRange,
   confirmed close; Waiting -> Armed with ArmedFromSeq = currentSeq + 1); unchanged code.
4. B TouchStart (Q3): logically applied through its plan row (TouchCount, CurrentTouchNo, TSS, TouchMark, Fresh are the
   projected values the Fresh / history transfer plans and the W08 Merge / Split TouchMark plans already read);
   EV_TOUCH_START always. Role 2: `touchStartApply` writes nothing on the old slot and reports "no persistent ring
   append" for the row (the W08 plan carries the projected mark); Main appends the mark only when flagged. Role 1: normal
   apply, the Armed index removal is skipped (released before commit by `phaseArmedIndexRelease`).
5. TSS (Q4): Merge / Split sources: the C2 completed-TSS clear (`touchHistoryTransferApply`, after commit and transfer)
   is the owner; `episodeApply` never clears them. A freed Episode Core outside every relation (no C2 capture): the TSS
   still valid after C2 is cleared by `episodeApply` (after commit / transfer; one owner per TSS, no double clear).
   Role 0 / 1: the existing Reset cleanup path.
6. Continuation (Q5): role 1 keeps its slot, ring and history (W08 "continuation release in place"): `episodeApply` runs
   its normal path (mark, Side WeakByDepth / MaxDepth, Reset: TSS clear, CurrentTouchNo 0, Waiting). Role 2 survivor /
   Split continuation: history = the C2 transfer (projected), ring = the W08 plan (projected marks), Phase = Stage J
   baseline; `episodeApply` writes nothing there. Merge absorbed: freed by W08.
Unchanged: C2 transfer semantics, Fresh transfer, W08 / W08Touch / W08Runtime, Break, WeakDepth / Reset Event wiring,
episodePlan, Stage J.

### R3-B2 implementation (W09State /24, Main wiring; TV compile pending)

W09State /24 (imports 0 -> 0, types 6 -> 6, exports 46 -> 47 (+episodeOverlayBuild), `.copy` 0, no tuple added, no
use-before-definition):
- `episodeOverlayBuild(ei, out)` (new export).
- `phaseArmedTransferPreflight(+activeOverlay)`: ActiveTouch passes only with its FORCE_INACTIVE entry (Reset A).
  (Placed before the EP_* constants, so it reads the projected state from the overlay, not from ei.)
- `touchStartPostPlanPreflight(+roles)`: role scratch (0 / 1 / 2), busy relaxed only for a Reset Episode with a role.
- `touchStartApply(+roles, +ringOut)`: role 2 no write / no ring append; role 1 no Armed index removal.
- `episodeApply(+roles)`: role 2 no write except a TSS still valid after C2 (freed outside every relation).
Main: overlay scratch `ov` -> planPassWithActiveTouchOverlay and phaseArmedTransferPreflight; role scratch `tro`;
ring flag `tsr` guards `W08Touch.markAppend` (the call stays in Main: W09State imports no W08 library, INC-1); the
three changed calls; W09State pin /22 -> /24. EV_TOUCH_START / WeakDepth / Reset Event loops unchanged.

Deterministic `r3b2_det.py` (Production W09State /24 + the Main commit slice interpreted; W08 = stub: PendingTopology
predicate on the overlay, hand-written projected Merge / Split TouchMark plan rows, commit = Core free / ring rewrite /
post-topology EffectiveRange): 15/15 in < 2 s. Compared per case: TouchCount, TouchMark ring rows, Side / Zone Fresh,
CurrentTouchNo, TSS (valid, Root count, node freed, no orphan), Phase, ArmedFromSeq (LastArmedRange), Core ID,
Generation ID, liveness, Events.
- A1 Merge survivor (new range top 112 -> Waiting: the old snapshot range is not used), A2 Merge absorbed (survivor Armed
  from seq + 1), A3 Split continuation, A4 freed outside every relation (TSS cleared once by episodeApply).
- B1 Merge survivor, B2 Merge absorbed, B3 Split continuation: TouchStart logical (count / mark / Fresh projected,
  EV_TOUCH_START + EV_TOUCH_RESET), no persistent ring append, TSS never persisted.
- K1 / K2 1:1 continuation (A / B): same slot, ring and history, Reset cleanup path, Armed from seq + 1.
- N1 / N2 no Reset -> W08 Pending (topology not applied, Episode / TouchStart normal); G1 / G2 the same forced into the
  applied topology -> preflight fails, persistent mutation 0.
- F1 / F2 W08 F0 failure after every W09 preflight -> persistent mutation 0.
Mutants (W09State): 8 non-equivalent killed (role-2 writes, role-2 ring append, no FORCE_INACTIVE, busy never relaxed,
transfer preflight ignoring the overlay, role-1 index removal, continuation as role 2, TSS fallback skipped); 2
equivalent (plan-row busy relaxation without Reset: the same Side's Episode check fails first; double TSS reset after
C2: idempotent defaults).
Regression of the changed functions (harness call signatures adapted only): R2 39/40 unchanged, the 1 change is C31
(R2 "Reset A + applied topology -> fail closed", now allowed by Q1; its new values are K1); R3A 20/20; B3A Phase
transfer 13/13 (empty overlay); R3-B1 scratch contract check PASS. random 0, 5k / 50k / 200k 0, R3-B1 29 cases not
re-run (W08Touch unchanged).
Publish: W09State /24 -> Main compile (TV Gate). CE10216 -> STOP.

### R3-B2 TV Gate: PASS -> R3-B2 COMPLETE; B07 CLOSEOUT

TOKEN END REVIEW (R3-B2 semantic batch): Before Production Main PASS; After Production Main PASS (W09State /24
published); compiled exact UNKNOWN; CE10216 none; token refactor 0; Main business logic 0 (the markAppend guard is
plumbing; the semantic authority is W09State); cross-library foreign type 0; Production semantics = R3-B2 as specified;
long test no; > 5 min no; needless retest no (changed functions only); rule violations 0. No further compression.

| ID | Module | Change | Before | After | Delta | Status |
|---|---|---|---|---|---|---|
| R3B2 | W09State /22 -> /24, Main | same-bar topology of Reset Episodes | PASS (exact UNKNOWN) | PASS (exact UNKNOWN) | UNKNOWN | COMPLETE; Q1-Q5 FROZEN |

B07: COMPLETE (existing ActiveTouch, same-bar TouchStart, WeakDepth, Reset, wouldBreak WeakDepth suppression, same-bar
Reset, next Touch from the next bar, projected Episode state, same-bar topology, projected TouchMark transfer, TSS
cleanup owner, post-topology Phase / Armed, persistent mutation 0 until all F0). Open B07 semantics: 0. B07 closed.

## W09 B08: Local Break / BreakReferenceRange - Phase A audit (no code change)

START GATE: `claude/w09-b07-redesign-v2` local = remote = `7d711b4` (0 / 0), clean. Pins = the Main PASS configuration:
W07Interval /1, W07 /11, W05 /7, W06 /24, W08Core /18, W08Touch /7, W08Runtime /17, W03EMsa /9, W09State /24 (+ W03F0 /5,
W03Apply /4, W03ETimeFvg /3).

Existing Break-related structure (source):
| Item | Where | State |
|---|---|---|
| BreakSnapshot storage per Side slot: valid, coreId, generationId, oldSide, range bottom / top, breakSeq, breakTime, wasGapBreak, movedAway, retestSeen, Root list head / tail / count | W08Core CoreRegistryStore (15 arrays) | storage only; no writer |
| BreakSnapshot Root node pool (rootId, next, owner Side slot, expected coreId / generationId / breakSeq, live, free stack) | Main W02AuxStore; `breakSnapshotRootNodeReset / Alloc / FreeRaw` in Main | raw lifecycle defined, unreachable (no caller) |
| Broken / FlipWait price-order indexes | Main engine `brokenSnapshot*` / `flipSnapshot*OrderSideSlots`, W08Core `side*SnapshotOrderPositions` | storage only; W08 reset clears positions |
| Phase enum PH_BROKEN 3 / PH_FLIP_WAIT 4, PhaseSet lists | W08Runtime / W09State (`phaseMoveRaw`) | sets maintained; no writer to Broken / FlipWait |
| Flip fields sideFlipAttemptCounts / sideLastFlipConfirmSeqs | W08Core | storage only (Flip = later batch) |
| Events EV_LOCAL_BREAK 4 / EV_GAP_BREAK 5; `eventAppendRaw` (type, time, seq, coreId, gen, side, range b / t, touchNo, gradeAtStart, weakReason, rootId) | Main | names only; no Break Event writer |
| `breakWouldMet` / `closeBeyondRaw` (Support close <= bottom - buffer, Resistance close >= top + buffer, ticks, inclusive) | W09State | B07 guard: episodePlan flag 1 (wouldBreak) on the TSS range (A) / the plan range = TSS-to-be (B); suppresses depth / WeakDepth (Break priority already holds) |
| `gapBreakTargetSlots` / `gapBreakMetExclusive` (strict full gap, close beyond the level, exclusive of a normal Touch) | W09State | B09 geometry; a GapBreak-only Armed target is not a Touch; no Break effect |
| W08 MERGE_STATE_DEFAULT_GUARD | W08Runtime | checks the 15 BreakSnapshot fields (an absorbed Core with a valid BS fails the W08 F0) |
| `phaseArmedTransferPreflight` | W09State | a Merge / Split source in Broken / FlipWait or with a valid BS fails the whole pass (temporary fail-closed; BS transfer not implemented) |
| W08 PendingTopology predicate | W08Runtime | ActiveTouch only (persistent or overlay); Broken / FlipWait not pending |
| Stage J | W09State | Broken / FlipWait / Dormant untouched |

Canonical (given): BreakReferenceRange = TSS range while ActiveTouch (GapBreak: previous-bar Armed EffectiveZoneRange, B09);
Local Break on the confirmed 5m close, Support close <= refBottom - breakBuffer, Resistance close >= refTop +
breakBuffer (inclusive) = exactly `breakWouldMet`; Break > WeakDepth on the bar (no WeakDepth Event; history not
rewound); ActiveTouch Break: Episode ends, old Side Broken, opposite Side FlipWait, BreakSnapshot created, TSS / Episode
cleanup in the Break commit order; B07 same-bar topology / atomicity kept. GapBreak body = B09.

Not fixed by the canonical text or the source (decisions needed before B08-A):
- D1 same-bar TouchStart + Local Break (B Episode breaking on its start bar): Break on the same bar (TouchCount +1, TSS ->
  BreakSnapshot, like the same-bar Reset) or not.
- D2 BreakSnapshot layout: the Side slot that stores it (the broken Side, the FlipWait Side, or both), the meaning of
  `oldSide`, and its Root list source (copy of the TSS Root list, or the current Root list).
- D3 the opposite Side at Break: FlipWait from every Phase? (Armed: index detach; ActiveTouch with its own Episode on the
  same bar, which may Reset on the same close; Broken / FlipWait / Dormant already).
- D4 the Broken / FlipWait price-order indexes: maintained from B08 (keys = the BreakSnapshot range) or left to their
  owner batch (MovedAway / Retest / Flip).
- D5 topology: (a) the Break bar: the breaking Episode stays PendingTopology (today: A no override = persistent Active,
  B FORCE_ACTIVE); (b) later bars: a Core with a Broken / FlipWait Side or a valid BS as a Merge / Split source fails the
  whole W09 pass (and the W08 guard), so a W08 plan that applies it blocks every commit. Options: W08Runtime PendingTopology
  predicate extended to Broken / FlipWait / BS valid (W08Runtime /18), or BreakSnapshot transfer (I27-15 §10 / §12).
- D6 after Break: CurrentTouchNo, current Grade, Upcoming (TouchCount / Weak / MaxDepth / Fresh kept).
- D7 EV_LOCAL_BREAK row: time / seq, range = BreakReferenceRange, touchNo, gradeAtStart = TouchStartGrade, weakReason,
  rootId; order against the WeakDepth / Reset / TouchStart Events.

Proposed minimal semantic batch B08-A "ActiveTouch Local Break" (after D1-D7): W09State next version (/25): episodePlan's
flag 1 becomes the Local Break (reference = the TSS range, never the live range; no new geometry); a Break branch in
the Episode apply after the TouchStart apply (BreakSnapshot write + Root copy into the BS pool, then the TSS clear;
CurrentTouchNo per D6; Phase ActiveTouch -> Broken and the opposite Side per D3 through the PhaseSet); the post-plan
preflight extended (BS pool growth, Event room, D3 preconditions); Main: the BS pool / BreakSnapshot arrays passed by
reference (a view or the existing TouchStartPlanView extended), EV_LOCAL_BREAK rows in the Episode Event loop. D5 decides
whether W08Runtime changes. Token: Main status UNKNOWN (PASS only) and B08-A adds a state writer with a new view ->
TOKEN START REVIEW with Probe YES (the view / pool wiring and the Break body together, INC-2) before the full batch.
STOP.

### B08 decisions D1-D7 (fixed by the user; B08-A = ActiveTouch Local Break)

- D1 same-bar TouchStart -> Local Break: YES (TouchStart counted: TouchCount +1, CurrentTouchNo, TSS / TouchMark / Fresh,
  EV_TOUCH_START; then the Break on the same close, EV_LOCAL_BREAK). No WeakDepth Event on a Break bar; Break > Reset.
- D2 BreakSnapshot: the same logical snapshot stored on both Side slots (Broken old Side, FlipWait opposite Side), two
  physical copies each owned by its Side: coreId, generationId, oldSide (= the broken Side, never rewritten on the
  opposite copy), range = TSS range (never the live range), breakSeq, breakTime, wasGapBreak false, movedAway false,
  retestSeen false, Root list = copy of the TSS Root list (never rebuilt from the current Root list).
- D3 opposite Side -> FlipWait: from Waiting; Armed (Armed index detach); Dormant (Dormant / index detach); ActiveTouch
  only when its Episode is projected ended on the same bar (else fail-closed); already Broken / FlipWait: fail-closed
  (no silent BS overwrite).
- D4 indexes synchronized in the same transaction: ActiveTouch / Armed / Dormant detach, Broken / FlipWait PhaseSet
  attach, Broken / FlipWait price-order index membership on the fixed BS thresholds. MovedAway / Retest / FlipAttempt /
  FlipConfirm / Reclaim predicates: B10 / B11.
- D5-a the Break Episode ends: overlay FORCE_INACTIVE, same-bar PendingTopology allowed (as the B07 Reset).
- D5-b no W08 Pending for Broken / FlipWait / BS valid; BreakSnapshot transfer (I27-15): continuation keeps the BS;
  Merge keeps the unresolved BS, several sources -> newest breakSeq -> breakTime -> canonical Core order; Split -> the
  child whose Side EffectiveRange relates to the BS fixed range (no copy to unrelated children); Phase / Grade / Armed
  after the BS transfer; no silent drop.
- D5 order: BS create -> BS Root copy -> projected Broken / FlipWait -> topology plan -> BS transfer -> Phase / index
  finalization -> TSS cleanup -> commit; persistent mutation 0 until all F0; no partial commit.
- D6 broken and opposite Side CurrentTouchNo 0; TouchCount, WeakByTouch, past WeakByDepth, MaxDepth, Fresh kept;
  Upcoming = TouchCount + 1 (derived, not used for a Touch while Broken / FlipWait); Grade Unavailable for Broken and
  FlipWait; TouchStartGrade unchanged.
- D7 EV_LOCAL_BREAK: time / seq of the bar, TSS coreId / generationId, side = old Side, range = BS range, touchNo = the
  Episode's fixed TouchNo, gradeAtStart = TSS grade, weakReason = the persistent Weak reason before the bar (the
  suppressed WeakDepth candidate excluded), rootId ID_NONE. Order: existing ActiveTouch -> EV_LOCAL_BREAK only;
  same-bar TouchStart -> EV_TOUCH_START then EV_LOCAL_BREAK; no WeakDepth / TouchReset Event with a Break; canonical
  (coreId, generationId, Support, Resistance).
- BS cleanup: TSS never cleared before the BS copy; with same-bar topology after the BS transfer, else after the BS
  commit; the BS is kept until Flip / Reclaim (no new clear condition in B08).

### B08-A physical design audit

Placement (no new import, no foreign type; W09State owns the semantics, W08 / Main plumbing only):
| Step | Where | Form |
|---|---|---|
| Break fact | W09State `episodePlan` | flag 1 (breakWouldMet on the TSS / plan range) becomes the Local Break; Break => no Reset flag (Break > Reset), override FORCE_INACTIVE (D5-a) |
| overlay | W09State `episodeOverlayBuild` | unchanged code (col 9 = 2 for a Break Episode) |
| opposite / preconditions | W09State post-plan preflight | D3 checks (projected-ended opposite Episode), BS pool growth, Event room (+1 per Break), Broken / Flip index insert proof |
| BS transfer plan | W09State, next to the C2 history plan | per applied Merge / Split destination Side: selected source BS (D5-b); scratch rows (stride fixed) |
| index release | W09State, pre-commit (next to phaseArmedIndexRelease) | Broken / FlipWait index removal of every continuation old / freed source Side (W08 reset clears positions only) |
| W08 guard | W08Runtime | MERGE_STATE_DEFAULT_GUARD must release the 15 BreakSnapshot fields (absorbed BS is transferred, like the C2 Touch history release in /13) -> W08Runtime /18 (edges unchanged, no new type) |
| BS / Phase apply | W09State, after commit | Local Break apply (BS on both Sides + Root copy into the BS pool, Broken / FlipWait through the PhaseSet, indexes, CurrentTouchNo 0, Grade Unavailable, TSS clear after the copy), BS transfer apply, destination Phase from the transferred BS before Stage J |
| Event | Main Episode Event loop | EV_LOCAL_BREAK rows from ei (flag), after EV_TOUCH_START |
| storage refs | Main | the 15 sideBreakSnapshot* arrays, the BS Root pool (8), the Broken / Flip order arrays (4) and positions (4) added to the existing W09State views (TouchStartPlanView 80 refs, PhaseArmedTransferView 69 refs) at their one construction site; no new UDT |

TOKEN START REVIEW (B08-A): Main PASS, exact UNKNOWN, headroom UNKNOWN, status UNKNOWN. Added: Local Break writer, BS
Root copy, BS transfer plan / apply, Broken / Flip index maintenance, EV_LOCAL_BREAK, W08 guard release. High-cost
candidates: ~31 more array references into the two existing W09-owned views (one construction site each; no foreign
type, no import, no tuple, no `.copy`); W08Runtime /18 (guard only). Probe: YES, one body-inclusive Probe (the view
growth plus the BS copy / transfer bodies reachable), per the rule "large array forwarding -> Probe once". Main business
logic: NO (Event rows from ei only).

Blocking gap (not in the repo; only "I27-15 §10 / §12" references): the Split rule "child Side EffectiveRange vs BS
fixed range" (intersection, containment, nearest, tie rule, several related children) and the destination Phase rule
after a BS transfer (Broken when the Side = BS oldSide, else FlipWait? versus the Stage J Waiting baseline, and a
destination that also receives an Armed / Waiting source). Without that text the BS transfer cannot be written without
guessing -> STOP before implementation. Minor: the Dormant index has no key array and no Dormant writer exists
(unreachable today): proposal, Dormant opposite -> PhaseSet detach, fail-closed if it holds a Dormant index position;
Broken / FlipWait index keys = the Side's BS range bottom / top.

### I27-15 BreakSnapshot transfer (restored and fixed by the user; the final I27-15 text is not in the repo)

1. Merge: several valid BS sources -> one source by breakSeq max, then breakTime max, then old Core canonical order; its
   whole BS row (all scalars + Root copy) is taken (no field-wise mix).
2. Split: source BS fixed range [bsBottom, bsTop] vs the child Side new EffectiveRange [childBottom, childTop]:
   inherited only on inclusive intersection (childTop >= bsBottom and childBottom <= bsTop); no containment, no nearest;
   every intersecting child inherits; 0 intersecting children -> F0 fail-closed (never dropped); several BS into one
   destination -> the Merge order.
3. Phase after BS: a destination Side with a valid BS -> Broken when its side = BS.oldSide, else FlipWait (over the
   Waiting / Armed / Dormant re-evaluation, also when merged with an Armed / Waiting source); CurrentTouchNo 0; Upcoming
   = resulting TouchCount + 1; Grade Unavailable; TouchCount / Weak / MaxDepth / Fresh = the transfer result. Sides
   without a valid BS: the normal Stage J (new EffectiveRange, current close).
4. Transfer order: TouchMark -> Side history -> derived state -> BreakSnapshot -> Phase / Grade / Armed; TSS cleanup
   after the real topology transfer; persistent mutation 0 until all F0.
5. Dormant opposite: PhaseSet detach; preflight that every Dormant recovery reverse position is SLOT_INVALID
   (FlipWait); any real membership -> fail-closed; no new Dormant order algorithm.
6. Broken / FlipWait price indexes: keys = the BS frozen range (bottom / top) of the Side, ticked only for comparison;
   no EffectiveRange, no buffer / reset offsets; index order never used as Event order.
7. W08Runtime /18: only the 14 BreakSnapshot fields leave MERGE_STATE_DEFAULT_GUARD (field by field; nothing else).
   (Correction: the W08 guard lists 14 BreakSnapshot fields; "15" above was a miscount.)
8. Token Probe: YES, exactly one, body-inclusive (BS create, BS Root copy, BS Merge / Split transfer, Phase / index,
   Event path); PASS -> Production with the same design, no further Probe; CE10216 -> record and STOP.

### B08-A body-inclusive Token Probe (one Probe; Production unchanged)

Probe = the full B08-A implementation under a Probe library name (no stub, every body reachable from Main):
- `token_probes/B08A_W09State_Worker_Probe.pine` = W09State /24 + B08-A, library `ZoneEngineV2_W09State_Worker_B08AProbe`
  (source diff vs /24: 441 changed lines): PhaseArmedTransferView + 31 BS / pool / index / Dormant refs + 3 scratch;
  helpers bsIndexRaw, bsClearRaw, bsNodeFreeRaw, bsWriteRaw, bsRootAppendRaw, bsSourceRaw; episodePlan (flag 1 = Local
  Break, Break > Reset, override); phaseArmedTransferPreflight (source Broken / BS fail-closed lifted);
  phaseArmedIndexRelease (+ Broken / FlipWait release of Merge / Split / freed sources); touchStartPostPlanPreflight
  (+ef: Break as an Episode end for busy, D3 opposite rules, BS range, Event room, BS pool growth); episodeApply (+seq /
  time / mintick: Local Break branch - BS on both Sides from the TSS with its Root copy before the TSS clear, Broken /
  FlipWait, Armed detach, CurrentTouchNo 0, Grade Unavailable, Broken / FlipWait index attach; a Reset keeps a partner's
  FlipWait); bsTransferPlan / bsTransferApply (Merge selection, Split inclusive intersection, 0-child fail, release list,
  whole-row copy); phaseArmedStageJFinalize (a destination with a valid BS -> Broken / FlipWait, Grade Unavailable,
  index attach).
- `token_probes/B08A_Rebuild_Main_Probe.pine` = Main + B08-A wiring, only the W09State import pointing at the Probe /1:
  34 added `pav` arguments, bsTransferPlan in the preflight chain, bsTransferApply after the C2 apply, post-plan +ef,
  episodeApply + seq / time / mintick, the Episode Event loop k 0..2 (EV_LOCAL_BREAK = flag 1).
- Not in the Probe: W08Runtime /18 (the 14 BreakSnapshot guard rows move under `if write`: no new code path, cost
  neutral or lower); it is published with the Production batch.

Sanity (not the Production gate) on the Probe bodies, `b8a_det.py` (W09State + Main slice interpreted, W08 stub with the
W08 free BS reset): 16/16 - L1 / L2 existing Support / Resistance Break, L3 / L4 same-bar TouchStart -> Break (Events
TouchStart then LocalBreak), L5 / L6 / L7 Break + Merge survivor / absorbed / Split continuation (BS transfer, Stage J
Broken / FlipWait), L8 / L9 opposite Armed / Dormant, F1 opposite unresolved ActiveTouch, F2 Split child missing the BS
range (plan fails), F3 W08 F0 fail (mutation 0), P1 Break over WeakDepth, P2 Weak history kept, M1 persistent BS Merge
selection (newest whole row), M2 Broken 1:1 continuation unchanged. Two first-run failures were fixture / expectation
errors (L8 another Core's Stage J Armed Side; F1 opposite range that Resets), no code change.

Implementation choices to confirm (not covered by D1-D7 / I27-15 text): (a) a Core freed outside every relation (no
Merge / Split, W08 free) releases its persistent BS with the Core (the Core ends; no destination exists); (b) a
same-bar Local Break on such a Core emits EV_LOCAL_BREAK but no BS is materialized (no destination). Alternatives:
fail-closed (would block every W08 plan that retires a Broken Core).

TV: publish `ZoneEngineV2_W09State_Worker_B08AProbe` /1 (the Probe file), then compile the Probe Main once.
Reading: PASS -> B08-A Production with this design (W09State /25, W08Runtime /18, Main), no further Probe;
CE10216 -> record the number, STOP.

### B08-A pre-Probe semantic correction (R2 of the Probe source; still the one Probe)

User decision: W08 frees a Core only as an applied Merge relation's explicit absorbed Core (no-successor / degree 0 /
gap > M keep it retained; a continuation is never freed). A Core freed outside every Merge / Split relation is therefore
unreachable in B08-A and is NOT a normal cleanup: with a valid BS or a same-bar Local Break it is an INVARIANT FAIL ->
F0 fail-closed, persistent mutation 0 (no BS drop, no BS Root pool change, no Event, no EV_LOCAL_BREAK without its BS).
Core-lifecycle cleanup (generation end, storage prune) belongs to W10 and its canonical text. The earlier choices
(a) "release the BS with the Core" and (b) "Event without BS" are withdrawn.
Correction confirmed: the W08 guard holds 14 BreakSnapshot fields; W08Runtime /18 releases exactly those 14.

Probe source change (`token_probes/B08A_W09State_Worker_Probe.pine`, bsTransferPlan): a freed Core that is not a Merge /
Split source and holds a persistent BS or a same-bar Local Break (bsSourceRaw != -2 on either Side) fails the plan (the
Episode Event loop is after the commit gate, so no Event). The release list now covers Merge / Split sources only.
Sanity `b8a_det.py` on the Probe sources: 16/16 (P1 + P2 merged into P1; X1 added: an invalid W08 plan freeing a Core
outside every relation (a) with a persistent BS, (b) with a same-bar Break -> F0 false, mutation 0, no Event); mutant
"invariant removed" -> X1 fails (killed). Production files unchanged. Probe still one; TV steps unchanged.

### B08-A Token Probe PASS -> Production (W09State /25, W08Runtime /18, Main)

TV: `ZoneEngineV2_W09State_Worker_B08AProbe` /1 + the Probe Main: PASS (exact UNKNOWN). Probe design ADOPTED; further
Probe 0; token refactor 0.

| ID | Module | Change | Before | After | Delta | Status |
|---|---|---|---|---|---|---|
| B08AP | Probe libraries (W09State B08AProbe /1 + Probe Main) | B08-A body-inclusive | PASS (exact UNKNOWN) | PASS (exact UNKNOWN) | UNKNOWN | ADOPTED (design) |

Production port (semantics = Probe R2):
- W09State /25 = the Probe R2 source with only the library name changed (diff: 1 line).
- Main = the Probe Main with only the pins W09State /25 and W08Runtime /18 (diff: 2 lines).
- W08Runtime /18: MERGE_STATE_DEFAULT_GUARD 25 -> 11 fields; the removed 14 are exactly the BreakSnapshot fields (valid,
  coreId, generationId, oldSide, range bottom / top, breakSeq, breakTime, wasGapBreak, movedAway, retestSeen, Root head /
  tail / count), now reset-only under `if write` (the reset still writes them); no other guard field changed; imports
  unchanged (W08Core /18, W08Touch /7).

Gates: `b8a_det.py` on the Production sources 16/16; R3-B2 frozen cases replayed on /25 through the new signatures
15/15 (B07 behaviour unchanged); static: W09State imports 0 / types 6 / `.copy` 0 / exports 47 -> 49 (bsTransferPlan,
bsTransferApply), no use-before-definition, no foreign UDT, no new import edge; Main pins W09State /25, W08Runtime /18
(others unchanged); single BS writer = W09State (Main passes references; its legacy `breakSnapshotRootNode*Raw` pool
helpers stay unreachable); relation-outside free invariant = X1 (F0 false, mutation 0, no Event). random 0, 5k / 50k /
200k 0, > 5 min 0.
TV order: W09State /25 publish -> W08Runtime /18 publish -> Production Main compile. CE10216 -> STOP.

### B08-A TV Gate: PASS -> B08-A COMPLETE; B08 CLOSEOUT

TOKEN END REVIEW (B08-A): Before Production Main PASS; After Production Main PASS (W09State /25, W08Runtime /18
published); compiled exact UNKNOWN; CE10216 none; Probe 1 (B08-A body-inclusive, PASS), further Probe 0; token refactor
0; foreign UDT 0; new import edge 0; Main business logic 0 (plumbing only); W08Runtime /18 released only the 14
BreakSnapshot guard fields (the other deferred fields stay guarded); rule violations 0. No further compression.

| ID | Module | Change | Before | After | Delta | Status |
|---|---|---|---|---|---|---|
| B08A | W09State /24 -> /25, W08Runtime /17 -> /18, Main | ActiveTouch Local Break + BreakSnapshot transfer | PASS (exact UNKNOWN) | PASS (exact UNKNOWN) | UNKNOWN | COMPLETE; semantics FROZEN (det 16/16, B07 replay 15/15) |

B08: COMPLETE (BreakReferenceRange, ActiveTouch Local Break, same-bar TouchStart -> Break, Break priority,
BreakSnapshot, BS Root copy, Broken / FlipWait, BS transfer, state / index, Event, atomicity). Open B08 semantics: 0.

## W09 B09: GapBreak - Phase A audit (no code change)

START GATE: `claude/w09-b07-redesign-v2` local = remote = `93506ed` (0 / 0), clean. Pins = the Main PASS configuration:
W07Interval /1, W07 /11, W05 /7, W06 /24, W08Core /18, W08Touch /7, W08Runtime /18, W03EMsa /9, W09State /25 (+ W03F0 /5,
W03Apply /4, W03ETimeFvg /3).

Existing structure (source):
| Item | Where | State |
|---|---|---|
| GapBreak geometry | W09State `gapBreakTargetSlots` (index query on the Armed indexes: Support bottomTick >= max(highTick + 1, closeTick + bufTick), Resistance symmetric) and `gapBreakMetExclusive` (per Side: high < bottom strict and close <= bottom - buffer inclusive, Resistance symmetric; false when `normalTouchMetExact` holds) | predicates only; `gapBreakMetExclusive` has no caller |
| BreakReferenceRange = LastArmedRange | the Armed indexes are keyed by sideLastArmedRangeBottoms / Tops; Stage J writes LastArmedRange = EffectiveRange of the confirmed bar; Stage D runs before this bar's Stage J | = the previous-bar Armed range (canonical) |
| previous-bar Armed | `d1TargetSlots` = Touch targets U GapBreak targets, kept only when Phase Armed, eligible, armedFromSeq <= currentSeq (a Side armed on this bar excluded), canonical order (coreId, generationId, Support, Resistance) | GapBreak targets are already in the D1 list |
| normal Touch priority | `touchStartPlanPreflight / Build` take a D1 target only when `normalTouchMetExact`; a GapBreak-only target is dropped | GapBreak has no effect today |
| B08 authority to reuse | bsWriteRaw / bsRootAppendRaw / bsNodeFreeRaw / bsClearRaw / bsIndexRaw, bsSourceRaw + bsTransferPlan / Apply (Merge selection, Split intersection, release list, relation-outside invariant), Stage J BS priority, post-plan preflight D3 rules, EV loop | available |
| W08Touch contract | TouchStart plan rows (PI_*) and ei rows (EI_*) are read by W08Touch /7 for projected TouchMarks | GapBreak rows must not enter either (no TouchMark for a GapBreak) |

Derived from the existing canon (not questions):
- GapBreak targets = D1 targets that are not a normal Touch and satisfy `gapBreakMetExclusive` on LastArmedRange; normal
  Touch > GapBreak (already exclusive); no TouchCount / WeakDepth / ZoneFresh / SideFresh effect; no TSS / TouchMark.
- BreakSnapshot (B08 D2 layout, both Sides): coreId / generationId of the Core, oldSide = the gap-broken Side, range =
  LastArmedRange, breakSeq / breakTime of the bar, wasGapBreak true, movedAway / retestSeen false; Root copy = the Side
  current Root list (the same previous-confirmed Root source the TouchStart TSS copy uses for this range; there is no TSS
  on an Armed Side).
- Phase: gap-broken Side Armed -> Broken (Armed index detach; ArmedFromSeq / LastArmedRange kept, as the B08 Armed
  opposite), opposite -> FlipWait by the B08 D3 rules (Waiting / Armed detach / Dormant without position / ActiveTouch only
  when projected ended; Broken / FlipWait or a still-active opposite fail-closed); CurrentTouchNo 0 (already 0 on an Armed
  Side; opposite 0), Grade Unavailable on both, Upcoming = TouchCount + 1 unchanged; Broken / FlipWait indexes on the BS
  range.
- Same-bar topology: the Side is not ActiveTouch (no overlay entry, W08 sees Armed) -> its Core may meet the topology;
  the projected GapBreak BS enters bsSourceRaw / bsTransferPlan (Merge / Split transfer, Stage J Broken / FlipWait);
  relation-outside free with a GapBreak -> F0 invariant fail (B08-A rule).
- Event: EV_GAP_BREAK; D1 is one canonical target list (B05 P3), so EV_TOUCH_START and EV_GAP_BREAK rows are written in
  that one D1 canonical order, before the Episode Events (WeakDepth / Reset / LocalBreak); range = LastArmedRange;
  weakReason = the persistent Weak reason (as D7); rootId ID_NONE; time / seq of the bar; coreId / generationId of the Core.
- Preflight: BS absent on the Core, LastArmedRange valid, opposite D3, Event room +1, BS pool growth (2 x Root count).
- Flip / Reclaim on the GapBreak bar: not confirmed (Flip / Reclaim = B10 / B11, not implemented; their batch must keep it).

Physical sketch: GapBreak rows in a separate Main-local int scratch (Side slots; not the TouchStart plan / ei, which
W08Touch reads); W09State: plan in the TouchStart plan pass (targets not touched + gapBreakMetExclusive), preflight in the
post-plan preflight, bsSourceRaw / bsTransferPlan see the projected GapBreak BS, apply next to the Local Break branch
(role 0 / 1; role 2 through the transfer); Main: the scratch, EV_GAP_BREAK rows in the D1 Event loop. No new type, import
or tuple; a few more parameters on existing calls. TOKEN START REVIEW / Probe decision after the design.

Undefined (I27 text not in the repo, no canonical source): the EV_GAP_BREAK row's
- touchNo: no Touch Episode exists (TouchCount unchanged): SideTouchCount, UpcomingTouchNo (TouchCount + 1) or 0?
- gradeAtStart: no TouchStartGrade exists: the current Side Grade before the break, GR_UNAVAILABLE, or another value?
STOP for these two fields.

### B09 GapBreak: Event resolution (user) and implementation (W09State /26, Main; W08Runtime /18 kept)

EV_GAP_BREAK (fixed): time / seq of the bar, Core / Generation ID, side = the gap-broken oldSide, range = the
previous-confirmed LastArmedRange, touchNo 0 (no Touch Episode sentinel; never SideTouchCount / Upcoming), gradeAtStart
GR_UNAVAILABLE (no TouchStartGrade; never the current Grade), weakReason = the persistent Side Weak reason, rootId ID_NONE.

TOKEN START REVIEW (B09): Main PASS, exact UNKNOWN; no new UDT / import / foreign type / tuple / mass array forwarding;
B08 BS helpers reused; GapBreak rows in Main-local flat scratch; a few parameters on existing calls -> Probe NO.

Implementation:
- W09State /26: GB_STRIDE scratch contract (gbi [Side slot, Core ID, Generation ID, Weak reason, Root offset, Root count],
  gbf [LastArmedRange], gbr [the Side current Root IDs], d1 = the D1 fact order); touchStartPlanBuild (+d1 / gbi / gbf /
  gbr): a D1 target that is no normal Touch and meets gapBreakMetExclusive becomes a GapBreak row (Root list proven);
  breakOppositeOkRaw (the B08 D3 rule, shared); breakCommitRaw (the Break commit, shared by the Local Break and the
  GapBreak); touchStartPostPlanPreflight (+gbi / gbf: Armed in both indexes, no Episode, no BS, valid range, opposite,
  Event room, BS pool; roles also when only GapBreak rows exist); bsSourceRaw (+gbi: a GapBreak -> -3 - k) and
  bsTransferPlan (+gbi / gbf / gbr: the projected GapBreak BS, wasGapBreak, Root copy from gbr; the relation-outside
  invariant covers it); gapBreakApply (role 0 / 1; role 2 through the transfer).
- Main: W09State /26 pin, the four scratch arrays, the new arguments, gapBreakApply after touchStartApply, the D1 Event
  loop over d1 (TouchStart row: its TouchMark when flagged + EV_TOUCH_START; GapBreak row: EV_GAP_BREAK) before the
  Episode Event loop. W08Runtime unchanged (/18).

B08 reuse-audit fixes (inside the shared helpers; B08 semantics as fixed by D3, no new rule):
- R1: the D3 opposite check read the persistent Phase only, so an opposite with a same-bar TouchStart (projected
  ActiveTouch, no Reset) passed as Armed and was committed as FlipWait with a valid TSS; now any opposite with a same-bar
  Episode must end by Reset (fail-closed otherwise). On /25 the case committed (FlipWait + TSS valid); on /26 it fails,
  mutation 0.
- R2: a Local Break on a 1:1 continuation (role 1) with an Armed opposite removed the opposite from the Armed indexes a
  second time (already released before commit) -> runtime.error; now the release is not repeated. On /25 runtime.error;
  on /26 Broken / FlipWait.

Gates: `b9_det.py` 16/16 (G1 / G13 Support GapBreak + Event row, G2 Resistance, G3 / G4 boundary equality, G5 / G6
high == bottom / low == top -> normal Touch, G7 no Touch / Weak / MaxDepth / Fresh / TSS / TouchMark change, G8 BS
(wasGapBreak, LastArmedRange, current Root copy, indexes), G9 Merge survivor transfer, G10 Split continuation transfer,
G11 opposite Armed, G12 relation-outside free -> F0 false / mutation 0 / no Event, G14 tolerance line-Zone Touch wins,
G15 D1 canonical order across Cores, R1, R2); B08 regression `b8a_det.py` on /26 16/16; R3-B2 replay 15/15; R3-B1
scratch contract check PASS (the check now matches the plan-row variable of the D1 loop by regex; strides unchanged);
static: W09State imports 0 / types 6 / `.copy` 0 / exports 49 -> 50 (gapBreakApply), no use-before-definition, BS
written only through breakCommitRaw / bsTransferApply. random 0, 5k / 50k / 200k 0, > 5 min 0. Harness fixture errors on
the first run (R1 opposite range that Resets) and a harness constant gap (GR_) were fixed in the harness only.
TV: W09State /26 publish -> Production Main compile. CE10216 -> STOP.

### B09 TV Gate: PASS -> B09 COMPLETE; B09 CLOSEOUT

TOKEN END REVIEW (B09): Before Production Main PASS; After Production Main PASS (W09State /26 published); compiled exact
UNKNOWN; CE10216 none; Probe 0; token refactor 0; new UDT 0; new import 0; foreign type 0; Main business logic 0;
W09State /25 -> /26; W08Runtime /18 kept; rule violations 0. No further compression.

| ID | Module | Change | Before | After | Delta | Status |
|---|---|---|---|---|---|---|
| B09 | W09State /25 -> /26, Main | GapBreak (+ B08 reuse-audit fixes R1 / R2) | PASS (exact UNKNOWN) | PASS (exact UNKNOWN) | UNKNOWN | COMPLETE; FROZEN (det 16/16, B08 16/16, R3-B2 15/15, contract PASS) |

B09: COMPLETE, FROZEN. Open B09 semantics: 0.

## W09 B10: Flip / FlipAttempt - Phase A audit (no code change)

START GATE: `claude/w09-b07-redesign-v2` local = remote = `0f01df2` (0 / 0), clean. Pins = the Main PASS configuration
(W09State /26, W08Runtime /18, W08Core /18, W08Touch /7, W07Interval /1, W07 /11, W05 /7, W06 /24, W03EMsa /9, W03F0 /5,
W03Apply /4, W03ETimeFvg /3).

Existing structure (source):
| Item | State |
|---|---|
| BreakSnapshot reader / storage | W09State PhaseArmedTransferView (B08-A): valid, coreId, gen, oldSide, range, breakSeq / breakTime, wasGapBreak, movedAway, retestSeen, Root list; B08 / B09 writers |
| movedAway / retestSeen | written false at a Break (breakCommitRaw); copied whole by the BS transfer; no other writer / reader |
| sideFlipAttemptCounts / sideLastFlipConfirmSeqs | W08Core storage; no writer; still in the W08 MERGE_STATE_DEFAULT_GUARD (an absorbed Core with a non-default value fails the W08 F0) |
| Broken / FlipWait PhaseSet and price indexes | maintained by B08 (keys = BS range; Stage J BS priority) |
| EV_FLIP_ATTEMPT 6 / EV_FLIP_CONFIRM 7 / EV_RECLAIM 8 | Main constants and names only |
| Reclaim predicate | none in the repo (B11) |
| Stage order | the repo names Stage C, D1-D3, E, F / G, H (topology), J; no Flip stage and no I8 stage list in the repo |

Derived from the given canon and the source (not questions):
- Price authority = the BS range only (never EffectiveRange / EMA / re-clustered range); ticks for comparisons.
- movedAway (Support Break): confirmed close <= bsBottom - touchResetDistance (inclusive); Resistance: close >= bsTop +
  touchResetDistance.
- Retest (Support Break, from below): the bar reaches the BS range inclusively (highTick >= bsBottomTick); Resistance
  symmetric (lowTick <= bsTopTick). A retest counts only on a bar after the movedAway bar (movedAway is a close fact;
  the intrabar order is never guessed).
- FlipConfirm (Support Break): on a retest bar, close <= bsBottom -> Resistance FlipConfirm (the retest precedes the
  close within the bar); Resistance Break symmetric (close >= bsTop -> Support FlipConfirm).
- Same-bar suppression: only a BS confirmed on an earlier bar is evaluated (breakSeq < currentSeq), so no Flip fact on
  the GapBreak bar (as fixed) and, since a retest needs a bar after the movedAway close, none on the Local Break bar
  either (derived from "close-only facts + no intrabar order").
- FlipAttempt / FlipConfirm are not normal Touches: no TouchCount / Weak / ZoneFresh / SideFresh / Grade effect; the
  FlipWait Side becomes Waiting at FlipConfirm (not Armed on that bar: "another confirmed bar", so Stage J must not arm a
  Side flipped on this bar; arming from the next bar through the normal Waiting -> Armed rule); no TouchStart on the
  FlipConfirm bar (the Side is not Armed).
- New Side history: the Side slot's own persistent TouchCount / Weak history is kept (a never-used Side has TouchCount 0);
  no reset at Flip.
- sideLastFlipConfirmSeqs = currentSeq at FlipConfirm (on the flipped Side).
- Event rows (EV_FLIP_ATTEMPT / EV_FLIP_CONFIRM): non-Touch facts -> touchNo 0, gradeAtStart GR_UNAVAILABLE (B09
  rule); range = the BS range; rootId ID_NONE; time / seq of the bar; Core / Generation ID of the Core; side = the new
  role Side (the FlipWait Side); weakReason = that Side's persistent Weak reason.
- Reuse: BS storage / Root pool / Merge-Split transfer / Stage J BS priority / Broken-FlipWait indexes (retest
  candidates from the FlipWait / Broken index on the BS keys) / relation-outside invariant / atomic plan -> preflight ->
  commit (a projected Flip state enters the BS transfer as B08 / B09 did).

Undefined (the I27 / I8 text is not in the repo; STOP):
- Q1 Reclaim predicate: a FlipAttempt requires "not a Reclaim"; the Reclaim condition (B11) is not in the repo, so the
  Attempt / Reclaim boundary on a retest bar cannot be written.
- Q2 movedAway on the Break bar: may the Break bar's own close set movedAway (close <= bsBottom - resetDistance on the
  Local / Gap Break bar), or only a later bar?
- Q3 Repeated retests: after a FlipAttempt, does another Attempt need a new movedAway, or is every later retest bar an
  Attempt? Meaning and writer of retestSeen (set at the first retest, reset when?).
- Q4 FlipAttemptCount: which Side slot holds it (FlipWait / Broken / both), reset timing (Break, FlipConfirm), and its
  Merge / Split transfer (with the selected BS row?); sideLastFlipConfirmSeqs transfer. Both are still W08-guarded: once
  written, an absorbed Core with a non-default value fails the W08 F0 unless their transfer is defined.
- Q5 After FlipConfirm: the old (Broken) Side's Phase, and the BreakSnapshot cleanup (both copies cleared at
  FlipConfirm, or kept for B11 Reclaim; Broken / FlipWait index removal).
- Q6 Stage position of the Flip facts in the bar and their Event order against the D1 (TouchStart / GapBreak) and
  Episode (WeakDepth / Reset / LocalBreak) Events.

### B10 Flip / FlipAttempt: Q1-Q6 fixed (user) and implementation (W09State /27, W08Runtime /19, Main)

Fixed (user, no further questions): Q1 wouldReclaim fact only (Support-break: close >= top + breakBuffer; Resistance:
close <= bottom - breakBuffer; suppresses the Attempt; Reclaim Event / Phase / BS cleanup = B11); Q2 movedAway also on the
Break bar's own close (Support close <= bottom - resetDistance, Resistance symmetric) but a retest only for a BS already
movedAway at the bar start; Q3 retestSeen = distinct contact latch (first contact bar: Confirm / Reclaim / else one
Attempt; no Attempt on continuous contact; a full exit to the break side clears it; no new movedAway needed);
Q4 flipAttemptCount on the FlipWait Side, per BS transition (new BS 0, Attempt +1, Merge = the selected source row,
Split = copied to every child taking the BS, Confirm / Reclaim / new generation 0), lastFlipConfirmSeq on the new Side
(Merge max, Split continuation kept, a fresh child only with this bar's Confirm, new generation -1); W08 guard releases
exactly these 2 (Inverse stays until B12); FlipAttempt / FlipConfirm append a non-normal 11-field TouchMark (touchNo 0,
contact = bar / BS range intersection) through the existing W08 transfer; Q5 FlipConfirm ends the transition: both Sides
Waiting, not armed on that bar, history kept, CurrentTouchNo 0, Grade by Stage J, both BS copies + Roots + indexes
cleared (after the topology F0 when same-bar), never revived by the Stage J BS priority; Q6 Flip / Reclaim facts in
Stage D3, priority D4, D1 Events first, then ONE canonical D3 order (coreId, generationId, Support, Resistance) over
LocalBreak / WeakDepth / Reset / FlipAttempt / FlipConfirm (no per-type pass); Event rows: BS range, side = the new
(FlipWait) Side, touchNo 0, gradeAtStart GR_UNAVAILABLE, the new Side's persistent Weak reason, rootId ID_NONE.

TOKEN START REVIEW (B10): Main PASS, exact UNKNOWN. No new UDT / import / foreign type / tuple; B08 BS helpers and the
TouchMark path reused; +9 references on the existing TouchStartPlanView construction, +2 on PhaseArmedTransferView, four
Main-local scratch arrays, a few parameters on existing calls, W08Runtime /19 (guard only). The Flip TouchMarks reach
the W08 Merge / Split TouchMark plans with no W08Touch change: W08Touch /7 projects every row of the TouchStart plan
arrays as an append of its Core (projPlanRowsRaw = rows of pI; projAppendsRaw matches Core slot / ID), so the Flip mark
rows are appended after the TouchStart rows (verified by reading W08Touch /7; not executed against W08Touch). Probe: NO.

Implementation:
- W09State /27: GB_STRIDE 7 (+ movedAway at the GapBreak bar), FL_STRIDE rows, Episode flag 128 = movedAway at the Local
  Break bar (the three `>= 64` flag tests now `% 128 >= 64`), breakCommitRaw callers pass movedAway; TouchStartPlanView
  + BS / Flip refs; flipPlan (Stage D3 / D4 facts from the Broken PhaseSet, canonical by the FlipWait Side; mark rows
  appended to the plan arrays; d3 = merged canonical D3 order); flipApply (role 0 / 1: flags on both BS copies, attempt
  count, Confirm cleanup, noArm; ring flags for the mark rows in plan order); bsSourceRaw (+fli: a BS confirmed this bar
  is none) and bsTransferPlan / Apply (BSP_STRIDE 12: + attempt count, lastFlipConfirmSeq, noArm; projected movedAway /
  retestSeen; noArm pushed for affected destinations); post-plan preflight (+fli: plan arrays may hold mark rows, Event
  room + Flip Events, roles also computed for Flip-only bars); Stage J (+noArm: not armed on the FlipConfirm bar).
- W08Runtime /19: MERGE_STATE_DEFAULT_GUARD 11 -> 9 fields (sideFlipAttemptCounts, sideLastFlipConfirmSeqs reset-only).
- Main: pins W09State /27, W08Runtime /19; the new refs / scratch / arguments; flipPlan after episodePlan (before the W08
  plan); flipApply after gapBreakApply; the D3 Event loop over d3 (Episode row Events or the Flip row's TouchMark when
  flagged + EV_FLIP_*), replacing the three per-type passes; Stage J + noArm.

Gates: `b10_det.py` 14/14 (F1 / F2 movedAway on the Break bar, F3 no same-bar retest on a newly movedAway BS, F4 + F11
first retest -> FlipConfirm (Waiting, BS / Roots / indexes cleared, attempt 0, lastFlipConfirmSeq), F10 no Armed on the
Confirm bar and Armed from seq + 1 on the next, F5 + F14 first retest -> Attempt with the non-normal TouchMark, F6
wouldReclaim suppresses the Attempt, F7 continuous contact -> one Attempt, F8 full exit clears retestSeen, F9 second
retest -> count 2, F12 Merge absorbed Flip-state transfer (count 3, freed slot untouched), F13 Split continuation transfer,
F15 D3 canonical order across Cores (Core 11 FlipAttempt before Core 20 WeakDepth), F16 W08 F0 failure -> mutation 0,
no Event). Regression: B08 16/16 and B09 16/16 (their expected BS movedAway updated to true where the Break-bar close is
beyond the reset distance: the Q2 change, no other field), R3-B2 15/15, R3-B1 contract PASS. Static: W09State imports 0 /
types 6 / `.copy` 0 / exports 50 -> 52 (flipPlan, flipApply), no use-before-definition; W08Touch / W08Core unchanged.
A defect found by F13 and fixed before commit: a bar with only Flip rows computed no topology roles (role 0), so
flipApply wrote on top of the transfer (count 4) and onto a freed slot; roles are now computed when Flip rows exist.
random 0, 5k / 50k / 200k 0, > 5 min 0.
TV: W09State /27 publish -> W08Runtime /19 publish -> Production Main compile. CE10216 -> STOP.

### B10 PRE-TV TEST COMPLETION (R2): Flip TouchMark transfer asserts in F12 / F13 (test only)
Production semantic change 0, Production source change 0 (W09State /27, W08Runtime /19, W08Touch /7, W08Core, Main as
in f862f3e). New test case 0: assertions added to the existing F12 / F13 only. The asserts run the real, unchanged
W08Touch /7 source (interpreted `mergePlanBuild` / `splitPlanBuild` + `mergeApplyPreflight` / `mergeApplyCommit` /
`splitApplyPreflight` / `splitApplyCommit`) on the pre-bar ring with this bar's TouchStart plan arrays (pI / pF, which
carry the Flip mark row) and ei / ef, replacing the previous code-reading-only confirmation of that path.
- F12 Merge (Flip Attempt on the absorbed Core 10 into survivor 11): Merge plan and the committed destination ring hold
  the Flip TouchMark exactly once with isNormalTouch false, touchNo 0, side Resistance, generationId 3, baseSeq / time of
  the bar, contact 100..102 (= bar x BS range), close 101; SideTouchCount of the destination unchanged.
- F13 Split (source Core 10, children 95..108 and 103..109): only the child whose Side EffectiveRange meets the contact
  range 100..102 receives the mark (same fields); the non-intersecting child receives no copy; the committed child ring
  holds it; SideTouchCount unchanged.
Result: F12 / F13 2/2 PASS (only the changed cases re-run; the other B10 cases unchanged). Probe 0, random 0, > 5 min 0.
TV: W09State /27 publish -> W08Runtime /19 publish -> Production Main compile. CE10216 -> STOP.

## W09 B10 AGGRESSIVE TOKEN COMPRESSION: Compression Batch TC-A (TOKEN_REFACTOR_ONLY)

START GATE: branch `claude/w09-b07-redesign-v2`, local = remote = `4357841`, divergence 0 / 0, clean. Backup
`backup/w09-b10-pre-aggressive-token-cut` (= `4357841`, pushed). Pins before: W03F0 /5, W03Apply /4, W03ETimeFvg /3,
W06 /24 (-> W05 /7 -> W07Interval /1), W07 /11 (-> W07Interval /1), W08Core /18, W08Touch /7, W08Runtime /19 (-> W08Core /18,
W08Touch /7), W03EMsa /9, W09State /27.

TOKEN START REVIEW: Main 1,009,747 / 1,000,000 (B10 TV, CE10216); headroom -9,747; RED. Target <= 950,000 (headroom
>= +50,000), preferred 930,000-950,000. Semantics frozen; physical duplicates only. Probe: NO (the batch removes structure;
it adds no import / type / signature / forwarding). Main business logic added: NO.

Reachable delta B09 (`0f01df2`) -> B10 (`f862f3e`), cgest E2 (reference only): +3,243 source tokens in total - flipPlan
+1,414, w08ProductionRaw (Main) +495, flipApply +445, bsTransferPlan +437, bsTransferApply +75, touchStartPostPlanPreflight
+74, bsSourceRaw +72, flipBitRaw +71, flipRowRaw +65, touchStartPlanBuild +32, episodePlan +26, Stage J +16, gapBreakApply
+13, episodeApply +10. Call tree: Main w08ProductionRaw -> W09State.flipPlan (-> flipRowRaw, flipBitRaw, breakOppositeOkRaw)
/ flipApply (-> flipRowRaw, bsClearRaw, bsNodeFreeRaw, bsIndexRaw, phaseMoveRaw) / bsTransferPlan (-> bsSourceRaw) /
bsTransferApply / touchStartPostPlanPreflight / phaseArmedStageJFinalize; D3 Event loop + markAppend in Main (plumbing).
Audit A-H over that tree: the whole B10 addition is ~3.2k source tokens, so no rework of the B10 bodies (forwarding, D3
kernel sharing, BS re-derivation, Event row assembly, S/R bodies, preflight / apply) can reach -60,000; those stay TIER B / C.

Import-edge evidence (measured, not estimated): R3B0 = +113k for one extra library edge to W08Core /18 + W08Touch /5 with no
W08 function called (types only; the W08 type definitions are ~1.2k source tokens, so the types cannot explain it); Import C
A (the W05 -> W07 edge replaced, W05 used 3 small W07 helpers) saved far more than those helpers (B08 / B09 then PASSed on top
of it). Reading: every library that references another library pays a full copy of it. Production today holds that copy twice
for W08Core /18 and W08Touch /7 (Main -> both, W08Runtime -> both).

| Tier | Candidate | Mechanism | Status |
|---|---|---|---|
| A | TC-A: W08Core /18 + W08Touch /7 bodies inside W08Runtime /20; Main imports W08Runtime only | one of the two full W08Core + W08Touch copies removed; W08Core call-0 bodies dropped | IMPLEMENTED |
| B | W09State call-0 bodies (10 functions, ~1.0k source) | dead library code | DEFERRED (needs W09State /28) |
| B | W07Interval /1 held by W07 and W05 (1.4k source) | duplicate edge | DEFERRED (W05 / W06 / W07 publishes) |
| B | W05 `candWindowExitRaw` call-0 (1.2k source) | dead library code | DEFERRED |
| C | GT-5A (555 params), D3, T1-T3 | forwarding / signatures | DEFERRED (D1 / D2 measured -551 / -611) |
| C | B10 A-H (forwarding, D3 kernel, Event rows, S/R) | small source share | DEFERRED |

TC-A (W08Runtime /20, Main pins; W08Core /18 and W08Touch /7 stay published, no longer imported by Production):
- Kept lines are the source lines verbatim (static check: 4,490 code lines identical to the source sequence after the
  transforms below; the merge is reproducible from `4357841` sources).
- Transforms: the two imports dropped; `W08Core.` / `W08Touch.` qualifiers dropped in the former W08Runtime code; W08Touch
  `mergePlanBuild` / `splitPlanBuild` -> `touchMergePlanBuild` / `touchSplitPlanBuild` (W08Core owns the unqualified names);
  duplicate constants kept once (all 10 duplicates equal in value, asserted); W08Runtime `identityEdgeFollowsRaw` /
  `physicalNewCompareRaw` removed in favour of the byte-identical W08Core copies.
- Call-0 bodies dropped (no path from Main through any library): W08Core intervalMove, originRemove, inverseOriginDetach,
  pendingPoolsOkRaw, pendingChainOkRaw, pendingClearChainRaw, pendingCanClearCore, pendingClearCore, ufFindRaw,
  pendingNewChildRaw, pendingNewRootRaw, topologyComponentsRaw (the W08Core variant; W08Runtime keeps its own),
  pendingPlanBuild, changedPlanBuild; W08Touch markPhysicalIndex; W08Runtime planPass, runShadow.
- Order W08Core -> W08Touch -> W08Runtime (declare-before-use violations 0, duplicate definitions 0, local / global name
  collisions 0).
- Main: 3 import lines -> 1 (W08Runtime /20); `W08Core.` / `W08Touch.` -> `W08Runtime.` in code (22 references, all resolve
  to exports of /20); Main identical otherwise.
- Static: semantic constants changed 0, comparisons 0, Event / Stage order 0, Root conditions 0; imports Main 10 -> 8,
  library-to-library edges 4 -> 2 (total edges 15 -> 11); foreign UDT fields 0 new (ShadowContext's W08Core / W08Touch field
  types are now local); new signatures 0; forwarding added 0; Main business logic added 0.
- Equivalence (TOKEN_REFACTOR_ONLY, expectations unchanged, TC-A Main + markAppend and the Merge / Split TouchMark plan +
  commit taken from the merged /20 source): B08 L1 / L5 / L7 / F3, B09 G1 / G9 / G12 / G15, B10 F3 / F4 / F5 / F12 / F13 /
  F15 / F16: 15/15 PASS (1.6 s); control: the same run against the old W08Touch file fails F12 / F13 (merged source is the one
  exercised). R3-B1 scratch contract PASS (now read from W08Runtime /20). random 0, 5k / 50k / 200k 0, > 5 min 0.
- Expectation (not an estimate of the value): the removed copy is the structure R3B0 measured at +113k; exact UNKNOWN until
  the TV compile.

TV: W08Runtime /20 publish (merged library) -> Production Main compile. W09State /27 unchanged. Record the compiled value
against 1,009,747. CE10216 or a build error -> STOP.

### TC-A result: REJECTED (library limit), Production restored

| ID | Module | Change | Before | After | Delta | Status |
|---|---|---|---|---|---|---|
| TC-A | W08Runtime /20 (W08Core + W08Touch bodies merged) | monolithic merge | 1,009,747 (Main, CE10216) | W08Runtime /20 publish FAIL: CE10117, 128,207 / 100,256 library limit (+27,951) | Main not compiled | REJECTED |

The failure is the per-library compiled limit (100,256), not the Main limit: one library cannot hold W08Core + W08Touch +
W08Runtime (128,207 even with the call-0 bodies dropped). Rejected: merging library bodies. Not rejected: removing the
duplicate import edge. Data point kept: the three bodies together compile to 128,207 as one library. Production Main compile
for TC-A: not run.

Restore (no history rewrite): W08Runtime and Main sources (and the contract-check default) back to the bytes of
`backup/w09-b10-pre-aggressive-token-cut` (= `4357841`): Main imports W08Core /18, W08Touch /7, W08Runtime /19; W08Runtime
/19 imports W08Core /18 + W08Touch /7. W09State /27, W08Core /18, W08Touch /7 untouched. W08Runtime /20 stays a failed
publish attempt (the version number is not reused).

## TC-B: import edge elimination (Main -> W08Core / W08Touch), Facade Probe (design + files, not Production)

Goal: Main -> W08Runtime -> (W08Core /18, W08Touch /7) only; no W08Core / W08Touch body copied; W08Runtime keeps both imports.

Main -> W08Core / W08Touch references (28 code lines, 9 symbols; none is class A primitive-only or class D constant-only):

| # | Line(s) | Symbol | Class | Why Main needs it | TC-B handling |
|---|---|---|---|---|---|
| 1 | 958 | `W08Core.W08Store` (ZoneEngine field `w08CoreStore`) | C (UDT field type) | persistent W08 store owned by the engine | field becomes `W08Runtime.ShadowContext w08Hold` (existing W08Runtime type; only `ws` / `sp` set); `engine.w08CoreStore` -> `engine.w08Hold.ws` |
| 2 | 467 | `W08Touch.SplitTouchPlan` (W08TouchStore field `splitTouchPlan`) | C (UDT field type) | persistent Split TouchMark plan | moved to the same holder (`w08Hold.sp`); `t.splitTouchPlan` -> `engine.w08Hold.sp` (both readers have `engine`) |
| 3 | 1301 | `W08Core.newStore()` | B (returns W08Core UDT) | engine init | `W08Runtime.newHolder()` = `ShadowContext.new(ws = W08Core.newStore(), sp = W08Touch.newSplitTouchPlan())` |
| 4 | 484 | `W08Touch.newSplitTouchPlan()` | B (returns W08Touch UDT) | W08TouchStore init | folded into `newHolder()` (same object, created on the same first-bar init) |
| 5-19 | 1665, 1714, 1876, 1906, 1940, 2062, 2092, 2121, 6005, 6012, 6123, 6336, 6339, 6357, 6439 | `W08Core.CoreRegistryStore cr = ...` | C (local annotation) | type annotation only | `cr = ...` (type inference; no wrapper) |
| 20 | 6117 | `W08Core.PendingTopologyStore ps = ...` | C (local annotation) | annotation only | `ps = ...` |
| 21 | 6175 | `W08Touch.TouchRing ring = ...` | C (local annotation) | annotation only | `ring = ...` |
| 22 | 6007 | `W08Core.PendingTopologyStore.new(...)` (20 arrays) | B (constructor of a W08Core UDT) | pending-pool view per bar | `W08Runtime.pendingStoreOf(cr, 16 pool arrays)` (one constructor call inside; argument list proven identical) |
| 23 | 6013 | `W08Touch.TouchRing.new(...)` (18 cr fields) | B (constructor of a W08Touch UDT) | ring view per bar | `W08Runtime.touchRingOf(cr)` (18 field reads inside; identical) |
| 24 | 6122 | `W08Touch.TouchPlan.new(...)` (14 arrays) | B (constructor of a W08Touch UDT) | Merge plan view per bar | `W08Runtime.touchPlanOf(14 arrays)` (identical) |
| 25-26 | 6187, 6214 | `W08Touch.markAppend(ring, ...)` | B (W08Touch UDT parameter) | TouchStart / Flip mark append | `W08Runtime.markAppend(...)` (same 13-parameter signature, one call inside; both call argument lists identical) |
| 27-28 | 6019, 6051 | `W08Core.W08Store ws` (parameter of the two current-Root functions) | C (parameter type) | reads `ws.physical*` arrays | parameter `W08Runtime.ShadowContext wh` + first line `ws = wh.ws` (body unchanged) |

Foreign-UDT audit: no new type; the holder is the existing exported ShadowContext (already built by Main every bar; its
W08Core / W08Touch field types already live in W08Runtime). The wrappers take / return W08Core / W08Touch UDTs that W08Runtime
already imports (no new edge). Signatures: newHolder 0, touchRingOf 1, pendingStoreOf 17, touchPlanOf 14, markAppend 13
parameters (the largest, 17, replaces a 20-argument constructor call in Main; no tuple). Forwarding: Main argument counts
equal or smaller (20 -> 17, 18 -> 1, 14 -> 14, 13 -> 13). Main business logic: none (plumbing renames only).

Probe files (not Production, never adopted as is):
- `token_probes/TCB_W08Runtime_FacadeProbe.pine`: library `ZoneEngineV2_W08Runtime_FacadeProbe` = W08Runtime /19 verbatim
  (imports W08Core /18 + W08Touch /7 unchanged) + the 5 wrappers above at the end.
- `token_probes/TCB_Rebuild_Main_Probe.pine`: Production Main with the W08Core / W08Touch imports removed and
  `ZoneEngineV2_W08Runtime_FacadeProbe/1 as W08Runtime` instead of W08Runtime /19 (alias unchanged), changes 1-28 above;
  every other line identical.

Probe Gate (one Probe): 1) publish FacadeProbe /1 (must build <= 100,256; CE10117 -> STOP); 2) compile Main Probe; record
against 1,009,747. <= 950,000 -> Production design (W08Runtime next unused version + Main); 950,001-999,999 -> compile restored,
Tier B next; > 1,000,000 -> record the exact value, STOP; foreign-UDT blow-up -> STOP.

### TC-B result: REJECTED (explicit-import rule)

| ID | Module | Change | Before | After | Delta | Status |
|---|---|---|---|---|---|---|
| TC-B | W08Runtime_FacadeProbe /1 + Main Probe | Main without direct W08Core / W08Touch imports | 1,009,747 | build error: "Library is not explicitly imported. To use the type, import that library." at `W08Runtime.ShadowContext w08Hold` | Main Probe not compiled | REJECTED |

ShadowContext holds W08Core / W08Touch UDT fields, so Main must import W08Core / W08Touch explicitly to use it; a type is never
reachable through a transitive import. Consequence: the import graph Main -> {W08Core, W08Touch, W08Runtime},
W08Runtime -> {W08Core, W08Touch} stays. Production unchanged by TC-B.

## TC-C: per-library Production slimming (TOKEN_REFACTOR_ONLY)

Usage audit (fixed-point call graph from Production Main over functions, types and constants; P0 Main-referenced, P1
cross-library from reachable W08Runtime code, P2 other reachable, T tests / harness only, D nowhere):

| Library | Symbols | P0 | P1 | P2 | T | D | Source tokens (cgest) | Removable | Remaining |
|---|---|---|---|---|---|---|---|---|---|
| W08Core /18 | 56 | 4 | 22 | 14 | 3 | 13 | 22,550 | 7,477 (14 functions) + 2 constants | 15,073 |
| W08Touch /7 | 63 | 5 | 6 | 48 | 3 (EI_OVERRIDE, EF_RANGE_BOTTOM / TOP: scratch-contract constants, kept) | 1 (markPhysicalIndex, 79) | 7,915 | 79 | 7,836 |
| W08Runtime /19 | 92 | 13 | 0 | 77 | 2 (planPass, runShadow: old harnesses only, pinned to old versions) | 0 | 24,915 | 53 | 24,862 |

W08Core removed (cgest source tokens / lines; Production callers 0; test callers): changedPlanBuild 2,041 / 168 (T: the
TC-B probe file's comments only), pendingPlanBuild 1,457 / 143 (same), topologyComponentsRaw 1,040 / 87 (callers: the two
above only), intervalMove 864 / 47, pendingChainOkRaw 463 / 40, pendingPoolsOkRaw 390 / 26, pendingClearChainRaw 351 / 35,
originRemove 318 / 31, inverseOriginDetach 165 / 18, pendingNewChildRaw 123 / 15, pendingNewRootRaw 103 / 13,
pendingCanClearCore 62 / 6, ufFindRaw 62 / 6, pendingClearCore 38 / 5 (T: W08Runtime_ProbeHarness, pinned to an old
version); dedicated-helper closure: topologyComponentsRaw, pendingChainOkRaw, pendingPoolsOkRaw, pendingClearChainRaw,
pendingNewChildRaw, pendingNewRootRaw, pendingCanClearCore, ufFindRaw are reachable only from the dead exports; constants
PH_ACTIVE_TOUCH, CAND_MEMBER_ROLE_INCLUDED_BROAD used only by them. W08Runtime keeps its own copies of the pending / topology
helpers (unchanged).

Slim versions (kept lines verbatim, order unchanged):
- W08Core /19 = /18 minus the 14 functions (with their attached comment lines) and the 2 constants: code lines 1,608 equal
  the /18 sequence without them (static IDENTICAL).
- W08Runtime /20 = /19 minus planPass / runShadow, import W08Core /18 -> /19: code lines 2,272 IDENTICAL. /20: the TC-A
  publish failed at compile, so no /20 was created; the next successful publish is expected to become /20 (if TradingView
  assigns another number, the Main pin follows it).
- W08Touch: unchanged /7 (79 removable tokens do not justify a publish).
- Main: pins W08Core /18 -> /19, W08Runtime /19 -> /20 (2 lines); W08Touch /7, W09State /27 unchanged.
Static: no removed symbol referenced by Main, W08Runtime /20, W08Core /19, W08Touch /7 or W09State /27; semantic constants /
comparisons / Event / Stage order / Root conditions changed 0; imports unchanged in shape; no new type / signature / forwarding;
Main business logic 0.
Equivalence: the 15 representative B08 / B09 / B10 cases (L1, L5, L7, F3, G1, G9, G12, G15, F3, F4, F5, F12, F13, F15, F16)
on the TC-C Main: 15/15 PASS; R3-B1 scratch contract PASS. random 0, > 5 min 0.

Other libraries, call-0 bodies (cgest source tokens, TOP 10; no change in TC-C, candidates after TC-C): W05
candWindowExitRaw 1,196; W09State touchSnapshotRootListDetachAllRaw 301, stateSetUpdate 176, touchResetMet 126,
touchSnapshotRootListAppend 78, touchSnapshotRootListDetachAll 73, touchSnapshotRootListValidate 69, breakWouldMet 52,
phaseMembershipValid 46, phaseDetach 46 (phaseAdd 46). W06 / W07 / W07Interval: none.

TV order: W08Core /19 publish -> W08Runtime /20 publish (imports W08Core /19) -> Production Main compile; record against
1,009,747. CE10117 / build error -> STOP.

### TC-C result: Main PASS

| ID | Module | Change | Before | After | Delta | Status |
|---|---|---|---|---|---|---|
| TC-C | W08Core /19, W08Runtime /20, Main pins | call-0 bodies removed (W08Core 14 functions + 2 constants, W08Runtime planPass / runShadow) | 1,009,747 (CE10216) | < 1,000,000 (Main PASS; W08Core /19 and W08Runtime /20 publish PASS) | > -9,747 (exact UNKNOWN) | ADOPTED |

New baseline: W08Core /19, W08Touch /7, W08Runtime /20, W09State /27, W06 /24, W05 /7; Main PASS, exact UNKNOWN. Backup
`backup/w09-b10-post-tcc-pass` (= `2f42b0e`). Semantics frozen.

## TC-D: additional compression (TOKEN_REFACTOR_ONLY)

A. Full dead-code audit (every library reachable from Main, fixed point over functions / types / constants; source tokens
cgest, reference only):

| Library | Symbols | Reachable | Dead | Source | Dead source |
|---|---|---|---|---|---|
| W03Apply | 79 | 79 | 0 | 23,997 | 0 |
| W03EMsa | 50 | 50 | 0 | 6,105 | 0 |
| W03ETimeFvg | 58 | 58 | 0 | 8,411 | 0 |
| W03F0 | 71 | 71 | 0 | 15,972 | 0 |
| W05Candidate /7 | 86 | 85 | 1 | 23,559 | 1,196 (candWindowExitRaw, 139 lines, no dead helper) |
| W06Component /24 | 78 | 78 | 0 | 28,603 | 0 |
| W07Fvg /11 | 47 | 45 | 2 constants | 9,748 | 10 |
| W07Interval /1 | 7 | 7 | 0 | 1,415 | 0 |
| W08Core /19 | 40 | 40 | 0 | 16,029 | 0 (re-fixed-point after TC-C: no new dead helper) |
| W08Runtime /20 | 90 | 90 | 0 | 25,438 | 0 |
| W08Touch /7 | 63 | 59 | 1 function + 3 constants | 8,336 | 94 (markPhysicalIndex 79) |
| W09State /27 | 166 | 146 | 12 functions / types + 8 constants | 32,391 | 1,154 |

W09State dead chains: touchSnapshotRootList* (DetachAllRaw 301 <- DetachAll 73; Append 78; Validate 69; type
TouchSnapshotRootPoolView 58, used only by them) = 579; stateSetUpdate 176; touchResetMet 126; breakWouldMet 52;
phaseMembershipValid / phaseAdd / phaseDetach 46 each + W09State's own type PhaseSetView 43 (used only by them; Main uses
W08Runtime.PhaseSetView). Production callers 0, test callers 0 (two probe files match the name PhaseSetView of W08Runtime
only). Dead W09State constants (PLAN_I_* / PLAN_F_* / EP_I_MARK) and W08Touch / W07 constants: KEPT (scratch-layout
contract, read by tests/r3b1_scratch_contract_check.py; no body).

B. W07Interval duplicate edge: W05 uses fvgIntervalOrderBuild x2 + fvgIntervalQuery x2; W07 uses fvgIntervalQuery x1 (+ the
private fvgIntervalLowerBoundRaw). No UDT (primitive arrays only). The whole library is 1,415 source tokens; removing either
edge means a byte-equivalent copy of query + lowerBound (~1.0k of the 1.4k) or of all three in the importer, so the net is
about 0.4k source at best, and it reverses the Import C A single-authority design. Library-limit risk: low, gain: negligible.
Decision: NOT ADOPTED (no TIER A in TC-D).

Tiers: A none; B W05 candWindowExitRaw 1,196 (one chain) + W09State dead set 1,154 (several chains, one module, one
publish); C W08Touch markPhysicalIndex 79, constants (not done).

TC-D implementation:
- W05Candidate /8 = /7 minus candWindowExitRaw (code lines 2,107 IDENTICAL to the /7 sequence without it).
- W06Component /25 = /24 with the W05 pin /7 -> /8 only (2,629 code lines IDENTICAL otherwise).
- W09State /28 = /27 minus the 10 functions and 2 types above (2,229 code lines IDENTICAL); constants unchanged.
- Main: pins W06 /24 -> /25, W09State /27 -> /28 (2 lines).
Static: no removed symbol referenced by any Production file (Main + 12 libraries); semantics / comparisons / order / Root
conditions 0; imports unchanged in shape; no new type, signature or forwarding.
Equivalence: 15 representative B08 / B09 / B10 cases on W09State /28 + TC-D Main: 15/15 PASS; R3-B1 scratch contract PASS.
random 0, > 5 min 0.

TV order: W05Candidate /8 publish -> W06Component /25 publish (imports W05 /8) -> W09State /28 publish -> Production Main
compile. Build error -> STOP.

### TC-D result and TOKEN COMPRESSION CLOSEOUT

| ID | Module | Change | Before | After | Delta | Status |
|---|---|---|---|---|---|---|
| TC-D | W05 /8, W06 /25, W09State /28, Main pins | call-0 bodies (W05 candWindowExitRaw; W09State 10 functions + 2 types) | < 1,000,000 (TC-C, exact UNKNOWN) | < 1,000,000 (Main PASS; W05 /8, W06 /25, W09State /28 publish PASS) | UNKNOWN | ADOPTED, FROZEN |

TOKEN END REVIEW (B10 aggressive compression, TC-A .. TC-D):
- Before compiled: 1,009,747 (B10 Main, CE10216). After compiled: < 1,000,000 (Main PASS, exact UNKNOWN; CE10216 none).
- Delta: < -9,747 (exact UNKNOWN). Headroom: > 0 (exact UNKNOWN). Status: not RED-by-overflow; exact class UNKNOWN (GREEN not
  proven; the 950,000 target is unverified).
- Changed Production: W08Core /19, W08Runtime /20, W05Candidate /8, W06Component /25, W09State /28, Main pins (W08Touch /7,
  W03* / W07 / W07Interval unchanged).
- New reachable heavy structure: none (TC-A / TC-B rejected and never adopted; TC-C / TC-D only remove bodies).
- TOKEN_REFACTOR_ONLY: yes. Long tests: none. > 5 min: none. Unneeded retests: none (15 representative cases per batch).
- Rule check: TC-A was implemented without a library-limit check (the per-library 100,256 limit was not in the rules) ->
  class DESIGN, prevention: "a library body merge must first estimate the merged library against the 100,256 library limit
  (the merged W08 libraries measured 128,207)". TC-B: a type held in another library's UDT needs an explicit import in the
  consumer (Pine rule) -> class DESIGN, prevention: "a facade cannot hide a foreign UDT; Main needs the explicit import of
  every library whose types it touches through a field".
- Results kept: TC-A REJECTED (CE10117 128,207 / 100,256), TC-B REJECTED (explicit-import rule), TC-C SUCCESS, TC-D SUCCESS.
- Dead code: essentially removed (left: W08Touch markPhysicalIndex 79 source tokens and layout constants). W08 import
  graph: no safe structural change left. W07Interval: no meaningful net. GT-5A / D3 / T1-T3: DEFERRED (candidates if CE10216
  returns). Further token refactors: forbidden until then; back to semantics.
- Next Batch start: YES. Next Batch token risk: MEDIUM (exact headroom unknown).

## W09 B10 CLOSEOUT

B10 Flip / FlipAttempt: COMPLETE, FROZEN (not reopened). Fixed: movedAway, retestSeen, FlipAttempt, FlipConfirm, the
wouldReclaim fact, the Flip non-normal TouchMark, FlipAttemptCount, LastFlipConfirmSeq, Merge / Split transfer, FlipConfirm
cleanup, D3 canonical Event order, same-bar topology, F0 atomicity. Gates: B10 deterministic PASS (14/14 + F12 / F13 R2
TouchMark asserts), B08 / B09 regression PASS, Production Main PASS (after TC-C / TC-D). Open B10 semantics: 0.

## W09 B11 Reclaim: START GATE and Phase A audit (no code change)

START GATE: branch `claude/w09-b07-redesign-v2` at `9576d1d` (pushed), clean. Pins: W03F0 /5, W03Apply /4, W03ETimeFvg /3,
W06 /25 (-> W05 /8 -> W07Interval /1), W07 /11 (-> W07Interval /1), W08Core /19, W08Touch /7, W08Runtime /20 (-> W08Core /19,
W08Touch /7), W03EMsa /9, W09State /28. Main PASS (exact UNKNOWN). Canon: the user's B11 text (sections 5-12); the repo
holds no other Reclaim text (HANDOFF_W02 #11: Reclaim shares the Broken index; Main EV_RECLAIM = 8 name only).

Existing code (W09State /28, Main):
- wouldReclaim: flipPlan `rc = mv0 and (sup ? cT >= tT + bbT : cT <= bT - bbT)` (ticks of the BS range, close, breakBuffer;
  inclusive), stored as fli flag 16, used only to suppress the Attempt (`at` needs contact, contact needs mv0). The canon
  Reclaim predicate (section 5) has no movedAway condition; the mv0 factor is redundant for the Attempt (at => ct => mv0), so
  the one predicate can become the Reclaim authority without the mv0 factor and without changing any B10 result (flag 16 is
  read nowhere else; a row is written only on mv / rs change, Attempt or Confirm). No second Reclaim predicate exists.
- Candidates: flipPlan already walks every Broken pair (Broken old Side sb, FlipWait sf, same valid BS, breakSeq <
  currentSeq) = exactly "before Flip is confirmed", price authority = the BS range only (no EffectiveRange / EMA /
  recluster).
- Same-bar Break / GapBreak suppression: a BS of this bar (Local Break or GapBreak) has breakSeq = currentSeq and is never
  a candidate; a Broken / FlipWait Side can be neither Local-broken (not ActiveTouch) nor GapBroken (not Armed) again.
  Confirm (close <= bottom / >= top) and Reclaim (close >= top + buffer / <= bottom - buffer) exclude each other (bottom
  <= top, buffer >= 0); Reclaim excludes the Attempt (B10). No intra-bar order is guessed.
- FVG structural invalidation (W03 journal JGROUP_E1 / JOP_FVG_INVALIDATE) runs in the Root stage before W08 / W09 Stage D;
  the Side current Root lists are derived from the post-topology state, never from the BS. A Reclaim writes no Root (the BS
  Root copy is freed, not restored), so an invalidated FVG Root is never revived or turned back to its old direction, and
  no Root / quality evidence is created.
- Cleanup: flipApply's FlipConfirm block = Broken / FlipWait index detach (bsIndexRaw), BS Root nodes freed
  (bsNodeFreeRaw), both BS copies cleared (bsClearRaw), CurrentTouchNo 0, both Sides Waiting (phaseMoveRaw), attempt count
  0; then the Confirm-only parts (noArm, lastFlipConfirmSeq). Reclaim needs exactly the shared part: one helper for both.
- Side history: a Break writes BS, Phase, CurrentTouchNo 0 and Grade Unavailable only (breakCommitRaw); TouchCount, Weak
  flags, MaxDepth, Side / Zone Fresh are never touched by Break / Flip, so a Reclaim keeps them by writing nothing there
  (no Fresh revival); Grade is recomputed by Stage J for Waiting / Armed.
- Phase: Stage J (unchanged) arms a Waiting Side when eligible + non-psych Root + armedDistanceMet on the current
  EffectiveRange and close, with ArmedFromSeq = currentSeq + 1 = "Waiting or Armed from the next bar"; no normal Touch can
  start on the Reclaim bar (D1 reads the previous-bar Armed state; Broken / FlipWait are not Armed). So Reclaim does not use
  noArm (that is FlipConfirm-only, B10 Q5); both Sides (old Side and the released FlipWait Side) go to Waiting.
- Same-bar topology: bsSourceRaw treats a BS consumed by a FlipConfirm of the bar as none; a Reclaim consumes the BS the
  same way (flag 16 joins the test), so the BS transfer drops it, the Stage J baseline gives Waiting to the destination
  unless another source BS wins (unchanged Merge / Split rules), attempt count 0 (taken only from a chosen persistent BS),
  lastFlipConfirmSeq unchanged (Confirm-only), noArm not set; the old Side history reaches the destination through the
  unchanged C2 transfer. Relation-outside free with a BS: the existing F0 invariant.
- Event: Main D3 loop already emits EV_FLIP_ATTEMPT / EV_FLIP_CONFIRM from fli (BS range from flf, touchNo 0,
  GR_UNAVAILABLE, fli column 4 weak reason, ID_NONE); EV_RECLAIM = the same row with side = oldSide and the old Side's
  persistent Weak reason (fli column 4 holds the FlipWait Side's today: a Reclaim row stores the old Side's). D3 order:
  one canonical (coreId, generationId, Side) merge; a Core holds at most one Broken pair and then no Episode, so a Reclaim
  row never ties with another row of its Core.
- TouchMark: the canon names no Reclaim TouchMark (B10 Q4 covers FlipAttempt / FlipConfirm only): none.
- F0: flipPlan is read-only before the W08 plan; flipApply runs after every F0 (runtime.error on a broken proof);
  touchStartPostPlanPreflight counts Flip Events for the Event room (Reclaim joins the count).

Phase A result: every audited item follows from the canon and the frozen B10 rules; I27 0; no question.
Planned physical shape (for the design step, not implemented): flipPlan rc without mv0 + a row on rc + old-Side weak
reason on a Reclaim row + d3 / Event room on flag 16; one shared pair-release helper used by FlipConfirm and Reclaim in
flipApply; bsSourceRaw consumes on Confirm or Reclaim; Main D3 loop EV_RECLAIM branch (plumbing). No new UDT / import /
foreign type / tuple / forwarding: Probe expected NO (TOKEN START REVIEW at the design step).

### B11 Phase A corrections (user)

1. Authority: the Reclaim text exists in the W09 canon bundle / Zone_definition_spec_v2 (not in this repo): Flip-unconfirmed
   only; old Support close >= BS.rangeTop + breakBuffer, old Resistance close <= BS.rangeBottom - breakBuffer, inclusive;
   after Reclaim: Broken / FlipWait released, old Side history kept, Zone / Side Fresh not revived, Weak not cleared, no new
   Root / quality evidence, Waiting or Armed from the next bar by the current distance. (The Phase A line "the user's text
   only" is withdrawn.)
2. movedAway is not a Reclaim condition (required): eligible = valid BS, Flip unconfirmed, breakSeq < currentSeq, the close
   condition.
3. FVG structural invalidation order (the Phase A line "E1 runs before Stage D" is withdrawn as an argument): canon order is
   D3 facts (Reclaim + FVG structural invalidation) -> D4 priority -> E1 apply of the accepted invalidation. "The Root is
   removed later anyway" is not a priority implementation: D4 resolves FVG structural invalidation > Reclaim explicitly on
   the projected invalidation; no remaining valid structure for the old Side -> Reclaim suppressed (no state change, no
   EV_RECLAIM); another valid Root left -> Reclaim kept, the invalidated Root never restored.

## W09 B11 Reclaim: implementation (W09State /29, Main)

TOKEN START REVIEW: Main PASS, exact UNKNOWN, headroom UNKNOWN. Added: one W09State export (reclaimResolve, D4, 10 params:
pav / fli / d3 + the journal op / group / Root-ID arrays + count + the Root registry map / states / live flags), one private
helper (bsPairEndRaw: the FlipConfirm cleanup moved out, now shared), small edits in flipPlan / flipApply / bsSourceRaw /
touchStartPostPlanPreflight / bsTransferPlan; Main: pin, one call in the existing preflight chain, the D3 Event type / side
selection. New UDT 0, import 0, foreign type 0, tuple 0, mass forwarding 0 (10 references once per bar). Probe: NO. Main
business logic: NO (the journal filter and the Root validity test live in W09State). W08Runtime /20 unchanged.

Implementation:
- D3 fact (flipPlan): the one Reclaim predicate rc = close >= top + breakBuffer (old Support) / close <= bottom - breakBuffer
  (old Resistance) on ticks, inclusive, without the movedAway factor (the B10 Attempt is unchanged: at => contact =>
  movedAway); a Flip row is written on rc too; a Reclaim row carries the old Side's persistent Weak reason, no TouchMark
  row; d3 takes flag 16 (Attempt 4 / Confirm 8 / Reclaim 16). Candidates stay the persistent Broken pairs with breakSeq <
  currentSeq (a BS of this bar, Local Break or GapBreak, is never one).
- D4 (reclaimResolve, read-only, after sideViewPreflight and before phaseArmedTransferPreflight / bsTransferPlan / the Event
  room preflight): I = Root IDs of this bar's journal rows JOP_FVG_INVALIDATE / JGROUP_E1 (the projected invalidation, not
  the registry after apply); a Reclaim row whose old-Side BS Root list meets I keeps the Reclaim only while another Root of
  the list is outside I, live and ROOT_ACTIVE; else flag 16 is removed and its d3 entry dropped (no state change, no Event).
  Confirm / Reclaim stay exclusive by price; the Attempt suppression by the Reclaim fact (B10) is unchanged.
- Apply (flipApply, role 0 / 1): FlipConfirm and Reclaim both call bsPairEndRaw (Broken / FlipWait index detach, BS Root
  nodes freed, both copies cleared, CurrentTouchNo 0, attempt count 0, both Sides Waiting); FlipConfirm alone adds noArm and
  lastFlipConfirmSeq. Reclaim: no noArm, lastFlipConfirmSeq kept; Stage J (unchanged) arms by the current EffectiveRange and
  close with ArmedFromSeq = currentSeq + 1. TouchCount, Weak, MaxDepth, Side / Zone Fresh, LastNormalTouchTime, Root lists:
  not written.
- Topology: bsSourceRaw treats a BS consumed by a FlipConfirm or a Reclaim (flag 8 / 16 after D4) as none, so a same-bar
  Merge / Split transfers no BS from it (Stage J baseline Waiting unless another source BS wins).
- Relation-outside free invariant: the bsTransferPlan free check now reads the BS held at the bar start (no Flip rows), so a
  consumed BS still fails the pass. /27 and /28 let a FlipConfirm-consumed BS pass it (latent B10 gap, found by R13; the
  invariant is B08's; fixed here for Confirm and Reclaim alike).
- Event (Main D3 loop, same single canonical order): EV_RECLAIM (fixed BS range, side = old Side, touchNo 0, GR_UNAVAILABLE,
  old-Side persistent Weak reason, ID_NONE, current time / baseSeq / coreId / generationId); suppressed Reclaims append
  nothing; Event room counts flag 16.

Gates: `b11_det.py` 14/14 (R1 + R9 Support Reclaim with movedAway false and the full EV_RECLAIM row, R2 Resistance, R3 / R4
equality + controls, R5 Local Break bar + same-seq persistent BS fail-closed, R6 GapBreak bar, R7 history kept, R8 Stage J
re-arm from currentSeq + 1, R10 no TouchMark, R11 Merge, R12 Split, R13 relation-outside free (Reclaim and Confirm) F0 /
mutation 0 / Event 0, R14 FVG invalidation with another valid Root: Reclaim kept, Root 81 not restored, R15 invalidation of
the only Root (and of one Root when the other is no longer live): suppressed, Core 10 unchanged, no Event, non-E1 rows
ignored). Regression: B08 L1 / L5 / L7 / F3, B09 G1 / G9 / G12 / G15, B10 F3 / F4 / F5 / F12 / F13 / F15 / F16: 15/15; B10 F6
re-run with its expectation moved to B11 (the wouldReclaim bar is now a Reclaim: EV_RECLAIM, BS cleared; still no Attempt
and no TouchMark): PASS. R3-B1 contract PASS. Static: W09State imports 0, types 4, exports 37 -> 38, use-before-definition
0; JOP_FVG_INVALIDATE / JGROUP_E1 / ROOT_ACTIVE equal Main's. random 0, > 5 min 0.
TV: W09State /29 publish -> Production Main compile. CE10216 -> STOP (no semantic cut; deferred GT-5A / D3 / T1-T3).

## W09 B11 CLOSEOUT

B11 Reclaim: COMPLETE, FROZEN (W09State /29 publish PASS, Production Main PASS; not reopened; open semantics 0).
Recorded separately: the relation-outside free check in bsTransferPlan reading the bar-start BS (no Flip rows) is a
"B11-discovered corrective invariant fix to the frozen B08 / B10 path" (the B08 invariant, enforced again for a BS consumed by a
same-bar FlipConfirm); it is not a B10 semantic change.

## W09 B12 Inverse FVG: START GATE and Phase A audit (no code change)

START GATE: `claude/w09-b07-redesign-v2` at `8bee144`, clean. Pins: W03F0 /5, W03Apply /4, W03ETimeFvg /3, W06 /25 (-> W05
/8 -> W07Interval /1), W07 /11 (-> W07Interval /1), W08Core /19, W08Touch /7, W08Runtime /20, W03EMsa /9, W09State /29. Main
PASS (exact UNKNOWN).

Existing Root-level Inverse lifecycle (W03 / W07 contracts, frozen; Main Stage D -> E -> F -> G -> W08 / W09):

| Step | Writer (stage) | State (owner: FVG Root) | Notes |
|---|---|---|---|
| structural invalidation fact | W03 Stage D `w03StageDFvgFactsRaw` (1h / 4h / D close beyond NativeRange: Bull close < bottom, Bear close > top) | journal JOP_FVG_INVALIDATE / JGROUP_E1 | fact only |
| invalidation apply | Main Stage F `fvgInvalidateApplyRaw` (E1) | rootStates ACTIVE -> INVALIDATED, structurallyActive set detach | direction, NativeRange, origin, Fresh flag untouched |
| InverseWait entry | W07 `inversePostApplyFinalize` -> `inverseWaitEnterApply` (same Stage F, same bar) | INVALIDATED -> INVERSE_WAIT, generic set move, inverseWaitFvgRootSlots, progress WAIT_MOVED_AWAY (1) | "the invalidation bar is never a moved-away bar": the bar's Stage E facts ran before the Root was waiting |
| movedAway | W07 Stage E `inverseFacts` / `inverseEvalOneRaw`, Stage F `inversePendingApply` | progress 1 -> MOVED_AWAY (2): Bull close <= bottom - reset, Bear close >= top + reset (ticks) | one step per bar |
| retest | same | 2 -> RETOUCHED (3): bar meets NativeRange inclusively (low <= top and high >= bottom) without the confirm close | later bars only (one step per bar) |
| InverseConfirm | same | 2 (touch + confirm) or 3 (confirm close) -> ACTIVE (4): Bull close <= bottom, Bear close >= top; INVERSE_WAIT -> INVERSE_ACTIVE, wait set -> inverseActiveFvgRootSlots | rootId, originKey, category / subtype, direction, NativeRange unchanged; no new Root / origin |
| after Confirm | W07 `inversePostApplyFinalize` | Candidate seed STATE | FVG (| BROAD); eligibility dirty of the new Side (Bull -> Resistance, Bear -> Support) | W04 eligibility: Bull INVERSE_ACTIVE -> Resistance, Bear -> Support; INVALIDATED / INVERSE_WAIT eligible nowhere -> the Root counts on one Side only (no C double count) |
| confirm list | W07 `inverseConfirmListBuildRaw` -> Main `fvgInverseConfirmRootIds` / `fvgInverseConfirmCount` | rootIds of this bar's Confirms ("same-bar normal Touch suppression marker", W07 B12) | written every bar, read by nothing yet (the W09 consumer is B12's) |
| topology | W05 / W06 / W08 (unchanged) | the Root joins the new-Side Candidate; W08 identity "inverse same-origin": the same FVG Root S -> R across passes continues the Core (inverse-origin gather + non-Broad origin match) | no new Generation for an Inverse (W08 semantics unchanged) |

Physical owners: Root state (rootStates, rootFvgInverseProgresses 0..4 = none / waitMovedAway / movedAway / retouched / active,
wait / active FVG sets + positions, generic state sets, NativeRange ticks, direction, origin, Fresh): Root (W03 / W07), never a
Side, Core or Generation. movedAway / retestSeen equivalents exist (progress 2 / 3); attempt / confirm state: confirm =
progress 4 + confirm list; no attempt state exists. Merge / Split / new generation never touch the Root registry, so the
Inverse wait / progress / NativeRange / origin survive every Core topology change without a transfer. The general Flip
BreakSnapshot is not involved (Inverse prices = NativeRange only). No new Root field / collection is needed for the
Root-level lifecycle; the W09 part is only the Side / Phase / Event / TouchMark coupling.

Derived (no question): Inverse is not a normal Touch (no SideTouchCount, no WeakDepth, no Side / Zone Fresh use: W07 writes
none of them); same origin / category, no extra C (single eligibility Side); the invalidation bar only enters InverseWait,
movedAway / retest / Confirm only on later bars (W07, one progress step per bar); prices = NativeRange; no new Generation
from Inverse; W08 identity / pairing unchanged.

sideInverseAttemptCounts: W08Core CoreRegistryStore Side field (allocated 0, no writer, no reader), still in the W08Runtime
MERGE_STATE_DEFAULT_GUARD (an absorbed Side must hold the default). EV_INVERSE_ATTEMPT = 10 and EV_INVERSE_CONFIRM = 11:
Main enum + names only (no producer, no row contract). No repo text defines an InverseAttempt or the Inverse Event rows.
Structural fact: during InverseWait the Root is eligible on no Side (INVALIDATED / INVERSE_WAIT), so a Side-unit attempt count
has no Side membership to attach to while the attempts would happen.

I27 (STOP; not derivable from the repo canon or the frozen W03 / W07 / W08 contracts):
- I27-B12-1 InverseAttempt: does the canon define it (EV_INVERSE_ATTEMPT exists)? If yes: trigger (W07 progress 2 -> 3 =
  retouch without the confirm close, once per wait or per retouch), the owner of sideInverseAttemptCounts while the Root is
  on no Side (the former Side? the future inverse Side? an aggregate?), reset / Merge / Split / new-generation rules, TouchMark.
  If no: B12 = Confirm only, the field stays default-guarded and unused, EV_INVERSE_ATTEMPT unused.
- I27-B12-2 EV_INVERSE_CONFIRM row: coreId / generationId (the post-topology Core whose inverse-direction Side current Root list
  holds the Root? none when it forms no Core?), side (inverse direction), range (NativeRange or the Side range), rootId (the FVG
  Root?), touchNo / gradeAtStart / weakReason; one Event per Root or per Side.
- I27-B12-3 Confirm-bar gating: which Sides get "no normal Touch start / not Armed on the confirm bar" (the post-topology Sides
  holding a confirm Root via the confirm list -> noArm like FlipConfirm? a destination Side that is already Armed or ActiveTouch:
  forced to Waiting, kept, or its same-bar TouchStart suppressed?), and how the pre-topology D1 TouchStart plan reads the marker.
- I27-B12-4 TouchMark of InverseConfirm: the repo holds no authority; confirm "none" or give the rule (non-normal row, contact,
  which ring / Side).

Token: no code change. Root-level state fully reused (W07); expected W09 additions are Side-level only (confirm list ->
Side mapping, Event rows); no new UDT / import / foreign type expected; Probe decision at the design step.

### B12 I27 resolution (user) and design-time conflicts (no code change)

RESOLVED (user):
- I27-B12-1: no InverseAttempt in B12 (W07 canonical audit: its trigger is not defined in the W07 bundle). EV_INVERSE_ATTEMPT
  unused; sideInverseAttemptCounts: no writer / reader, stays 0 and in the Default Guard (reserved); progress 2 -> 3 is the
  RETOUCHED step only (no Event, no TouchMark, no count).
- I27-B12-2: one EV_INVERSE_CONFIRM per confirmed Root (several Roots on a bar = several Events); side = Resistance for an
  original Bullish FVG, Support for Bearish; range = the Root NativeBottom / NativeTop; rootId = the Root; touchNo 0;
  GR_UNAVAILABLE; WEAK_NONE; time / baseSeq = the confirm bar; coreId / generationId = the destination Physical Core whose
  inverse-direction Side holds the Root after Stage H topology (never the pre-topology owner); unresolvable destination ->
  F0 fail-closed (mutation 0, Event 0). Order: (coreId, generationId, Support, Resistance), Roots of one Side in the W07 confirm
  list order; no per-type sort.
- I27-B12-3: the destination Side gets no normal Touch on the confirm bar: Stage J noArm (Waiting); a later bar meeting the reset
  distance arms it with ArmedFromSeq = that bar + 1. A same-bar D1 TouchStart plan of that Side / Core is cancelled (no
  TouchCount, CurrentTouchNo, TSS, normal TouchMark, Fresh use, EV_TOUCH_START), by the W07 confirm marker, no intra-bar
  order guess. A destination Side already ActiveTouch at the bar start keeps its Episode / TSS; the topology change follows
  the PendingTopology contract (A16), never a forced Waiting.
- I27-B12-4: one non-normal TouchMark per confirmed Root (A6.4): baseSeq / time = the confirm bar, side = inverse direction,
  generationId = the destination Core's, isNormalTouch false, touchNo 0, close = the bar close, weakByDepth false, max 0,
  contact = [max(low, NativeBottom), min(high, NativeTop)]; Merge / Split by the existing TouchMark contract.
- W07 state machine unchanged; no new Root field; sideInverseAttemptCounts untouched; Default Guard release 0.

Design-time conflicts found before implementation (existing W08 / W09 contracts, verified in the code):
- C1 (pending destination): W08 applies only changed components with no old Side in ActiveTouch; a component holding an
  ActiveTouch Side at the bar start, or a projected ActiveTouch from a same-bar D1 TouchStart without Reset (episodeOverlayBuild
  FORCE_ACTIVE), is pending: no Core materializes it this bar and w09CurrentRootProduceRaw leaves its Cores untouched. A
  confirmed Root whose new-Side Candidate lies in such a component has no post-topology destination owner on the confirm bar.
  By the I27-B12-2 rule that is an F0 failure of the whole W08 / W09 transaction of the bar (every other Core's update and
  Event of the bar dropped), and the confirm itself is lost (the W07 confirm list is rebuilt every bar). The I27-B12-3 /
  I16 case ("already ActiveTouch -> Episode / TSS kept -> topology deferred") is exactly this case, so the two rules conflict.
- C2 (same-bar D1 TouchStart cancel): a same-bar TouchStart without Reset makes its component pending (C1), so a confirmed Root
  can enter that Side on the confirm bar only when the TouchStart's Episode resets on the same bar. Then the cancel must remove
  the TouchStart row, its Episode row and their TouchMark rows from the plan arrays that the W08 plan already consumed
  (W08Touch Merge / Split plans project every plan row before the destination is known): the destination is known only
  after the W08 plan that read the rows to be cancelled. No rule in the repo orders this (re-plan, pre-topology rule, or
  fail-closed).
- C3 (no winner): a confirmed Root that no applied Side winner holds (the W05 selection may leave it out) has no destination
  either -> F0 by I27-B12-2; to be confirmed as intended.

Status: B12 implementation NOT started (STOP): C1 / C2 need a rule; C3 a confirmation.

### B12 C1 / C2 / C3 resolution (user) and the I27 ledger correction

Withdrawn: "destination owner unresolved -> F0 fail" (I27-B12-2 / B12-3 as recorded above): it conflicts with the A16
ActiveTouch PendingTopology contract. Corrected rules:
- C1 Pending component: no F0 failure; the component stays Pending (A16); the W07 Root state (INVERSE_ACTIVE) stands.
- Event: EV_INVERSE_CONFIRM is always published on the confirm bar (never later, never again): time / baseSeq = the confirm
  bar, side = Resistance for an original Bullish FVG / Support for Bearish, range = NativeBottom / NativeTop, touchNo 0,
  GR_UNAVAILABLE, WEAK_NONE, rootId = the Root; coreId / generationId = the one materialized inverse-direction destination
  after the final topology, else ID_NONE / ID_NONE (Pending, no applied winner, several destinations, any non-unique case),
  never an F0 failure, never a guess.
- C3 no winner: normal (no F0); Root stays INVERSE_ACTIVE; Event with ID_NONE core / generation; no TouchMark, no noArm; no
  later Event / TouchMark when the Root becomes a winner afterwards.
- Pending TouchMark: a Root-unit deferred mark in flat SoA (no UDT): valid, expectedRootId, confirmBaseSeq, confirmTime,
  inverseSide, nativeBottom, nativeTop, contactBottom = max(confirm low, NativeBottom), contactTop = min(confirm high, NativeTop),
  closeAtTouch = confirm close. After each bar's final topology: A a materialized destination Side -> the mark (original
  payload, non-normal, touchNo 0, weak false, max 0) to every destination Side that holds the Root and whose EffectiveRange
  meets the original contact inclusively (Broad: every such Side; existing W08 TouchMark dedupe / capacity / truncation), then
  clear; B still in the PendingTopology Root set -> keep; C neither -> clear (no winner), no mark. No Event in A / B / C.
- C2 same-bar D1 TouchStart: (a) counterfactual read-only plan P0 -> cancel -> final re-plan P1 only when needed. Only on a bar
  with an InverseConfirm and a D1 TouchStart candidate: P0 = the existing W08 plan with this bar's new D1 TouchStarts left out
  of the projected ActiveTouch overlay (bar-start ActiveTouch, same-bar Resets of existing Episodes, Breaks: as before);
  persistent mutation / Event / TouchMark 0. The new D1 TouchStarts mapped by P0 to an InverseConfirm Root's projected
  destination Side are cancelled (no TouchCount + 1, CurrentTouchNo, TSS, normal TouchMark, Fresh use, EV_TOUCH_START); other
  D1s stay. P1 = the same plan call again only when a surviving D1 changes the final projected Active state; P1 alone is the
  authority for F0 / commit / Events / TouchMarks / Stage J. All D1s cancelled (projected state = P0's) -> P0 is final, no
  P1. Bars without an InverseConfirm or without a D1 candidate: one plan as today. An ActiveTouch at the bar start is never
  cancelled: Episode / TSS kept, component Pending, the Event on the bar, the mark deferred.
- noArm: a same-bar materialized destination Side -> Waiting, noArm on the confirm bar; a later bar meeting the reset distance
  -> ArmedFromSeq = that bar + 1. Pending: the Episode continues; on the pending-apply bar A16 steps 5 / 6 evaluate the
  current close on the new range (Armed from that bar + 1); never retroactively.
I27-B12-1 .. 4: RESOLVED (as corrected). C1 / C2 / C3: RESOLVED. I27 OPEN = 0.

### B12 TOKEN START REVIEW

Main: PASS, exact UNKNOWN, headroom UNKNOWN. Planned additions: W09State (confirm Root -> destination Side / Core mapping, Event
and TouchMark projection, noArm, D1 cancel set from P0, deferred mark resolve), Main plumbing (the plan loop, the deferred SoA
in W02AuxStore, Event / mark wiring), W07 / W08 unchanged, sideInverseAttemptCounts untouched (Guard release 0). New UDT 0,
import 0, foreign type 0, tuple 0. High-cost candidate: the same large W08 plan function reached twice (C2) -> rule §5 /
§6 HIGH_COST_STRUCTURE candidate -> Probe REQUIRED before Production.
Verified for the two-pass shape: planPassWithActiveTouchOverlay is a shadow plan (pending pool copied into ctx.psPlan, plan
scratch in the W08Store / TouchPlan arrays rebuilt per call, the overlay only feeds the Pending predicate); ShadowScalars
nextCoreId / nextGenerationId move only in materializeAppliedRaw with commit = true. A second call overwrites the first one's
scratch; no persistent write.

Probe (one file, Main only, Production imports unchanged: W09State /29, W08Runtime /20, W08Core /19, W08Touch /7):
`token_probes/B12_Rebuild_Main_TwoPassProbe.pine` = Production Main + (1) the 10-field deferred mark SoA in W02AuxStore with its
init; (2) one plan call site in a loop: P0 with the FORCE_ACTIVE overlay entries (this bar's new D1 TouchStarts) left out, run
only when fvgInverseConfirmCount > 0 and a D1 TouchStart plan row exists, P1 (the same call) only when such an entry exists
(stand-in for the W09State cancel decision), the last run final; (3) a stand-in deferred-row writer from the W07 confirm list
(native ticks * mintick, contact = bar / NativeRange intersection, side from the direction). No plan body copied, no business
logic duplicated, no new import / type. TradingView: compile the Probe Main; CE10216 / CE10117 -> STOP; PASS -> Production
implementation (exact value not needed).

## W09 B12 Inverse FVG: implementation (W09State /30, Main)

Probe `token_probes/B12_Rebuild_Main_TwoPassProbe.pine`: TradingView PASS (no CE10216 / CE10117) -> the two-pass shape
(P0 -> D1 cancel -> conditional P1, one plan call site) is adopted (a token gate, not a semantic PASS).

Changed: W09State /29 -> /30; Main (pin, W02AuxStore deferred SoA, plan loop, preflight, post-commit wiring, D3 branch).
Unchanged: W07, W08Core, W08Touch, W08Runtime, W05, W06 (no new export used from them; the existing plan function only).

W09State /30:
- touchStartPlanBuild + tsExcl: a normal Touch of a Side in tsExcl gets no plan row (never re-read as a GapBreak).
- inverseConfirmPreflight (pre-commit, every bar): each W07 confirm Root live, INVERSE_ACTIVE, Bullish / Bearish; else F0.
- inverseCancelPlan (after P0, read-only): per confirm Root (inverse Side: Bullish -> Resistance, Bearish -> Support), every
  applied P0 Candidate whose inverse-Side winner holds the Root; the TouchStart candidate Sides of that parity on an old Core
  flowing into it (Merge survivor / absorbed, Split source, 1:1 continuation old) are cancelled. A Root whose destination is
  Pending or winner-less cancels nothing (no Side receives it on this bar; A16); a bar-start ActiveTouch is never a D1
  candidate.
- inverseDeferredResolve (post-commit, rows of earlier bars): Root gone from the registry -> row dropped (I29 slot reuse /
  retire); Root in a live PendingTopology Root node -> kept; else the original non-normal mark to every live inverse-Side
  holder (current Root list) whose EffectiveRange meets the original contact, row dropped (no holder -> no mark). No Event.
- inverseConfirmProject (post-commit, after the resolve): per confirm Root: holders = live inverse-Side current Root lists
  holding it, pending = a live PendingTopology Root node holds it. Event row: NativeRange, side, rootId, coreId / generationId
  of the single holder when not pending, else ID_NONE. Not pending and >= 1 holder: one non-normal mark per holder meeting the
  contact [max(low, NativeBottom), min(high, NativeTop)] (close = bar close, gen = holder's). Pending: defer flag (every mark
  deferred, none partial). Every holder not ActiveTouch joins noArm (Waiting on the confirm bar; Stage J arms on a later bar
  from that bar + 1). d3 rewritten as the merged D3 order: existing entries in order, Inverse rows by (coreId, generationId,
  Support, Resistance, rootId), after the existing entries of an equal (coreId, generationId, Side) key; ID_NONE rows first.
- sideInverseAttemptCounts / EV_INVERSE_ATTEMPT: no reference (Default Guard unchanged, 0 fields released).
Main:
- Plan loop: pass 0 = the usual build + one W08 plan; with an InverseConfirm and a D1 TouchStart candidate, pass 0 only
  records the candidates, P0 = all new D1 TouchStarts excluded (plan rows, Episodes, overlay, marks), W08 plan, cancel set;
  all cancelled -> P0 final; else P1 = only the cancelled ones excluded, the same plan call again (final). W08 plan calls per
  bar: 1 normally, at most 2; one call site each for the plan, the three W09 planners, SideView / transfer views and
  inverseCancelPlan.
- Preflight: inverseConfirmPreflight in the existing chain; Event room minus the confirm count.
- Post-commit (after flipApply): inverseDeferredResolve, inverseConfirmProject, deferred rows pushed to the 10-field SoA (the
  Probe layout; one row per Root and confirm), the resolution marks appended before the D1 loop, the D3 loop's InverseConfirm
  branch (immediate marks, then EV_INVERSE_CONFIRM: NativeRange, touchNo 0, GR_UNAVAILABLE, WEAK_NONE, rootId).
- The 11-field TouchMark contract has no snapBottom / snapTop / deepestClose (TSS fields): not written for the Inverse mark.

Gates: `b12_det.py` 22/22 covering I1-I30 (W07 lifecycle steps I3-I7 on the frozen W07 source: boundary confirm, invalidation
bar only WAIT_MOVED_AWAY, moved-away bar no retest / confirm, retest only -> RETOUCHED, RETOUCHED -> confirm by the close;
W09: I1 / I2 Side mapping, I8 history, I9 Event fields, I10 two Roots, I11 / I12 non-normal mark + Native contact, I13 / I27
destination D1 cancelled and P0 final (one plan), I14 noArm with the reset distance met, I15 next bar armed from + 1, I16 /
I21 bar-start ActiveTouch: Pending, Episode / TSS kept, Event ID_NONE, mark deferred, I17 Merge survivor, I18 Split child with
/ without contact overlap, I19 broken confirm list -> F0 mutation 0 Event 0, I20 no sideInverseAttemptCounts reference, I22
pending applied later with the original payload, I23 multi-bar pending (one row, no repeat), I24 no winner, I25 two holders
(Event ID_NONE, a mark each), I26 / I28 related D1 cancelled, unrelated kept, P1 (two plans) committed, I29 Root gone ->
row dropped, I30 pending + holder -> all deferred). Regression: B08 L1 / L5 / L7 / F3, B09 G1 / G9 / G12 / G15, B10 F3 / F4 /
F5 / F12 / F13 / F15 / F16 (15/15), B11 R1 / R2 / R14 / R15 (4/4). R3-B1 contract PASS (its regex now targets the TouchStart
markAppend; the Inverse marks read mki). Static: W09State imports 0, types 4, exports 42, use-before-definition 0;
FVG_BULLISH / FVG_BEARISH / ROOT_INVERSE_ACTIVE equal W07 and Main. random 0, > 5 min 0.

Token structure: plan body copy 0, new import / UDT / foreign type 0, third plan 0. New exports: inverseConfirmPreflight (5
params), inverseCancelPlan (9), inverseDeferredResolve (17: the 10 SoA arrays + views / pool / outputs), inverseConfirmProject
(23); touchStartPlanBuild + 1. Risk: medium (two larger signatures, called once per bar). CE10216 -> STOP (no semantic cut;
GT-5A / D3 / T1-T3).
TV: W09State /30 publish -> Production Main compile.

### B12 R2 (pre-TV correction, W09State /30 still unpublished)

- Pending destination D1 rule corrected (the R1 rule "a Pending destination cancels nothing" is withdrawn): inverseCancelPlan
  takes every P0 Candidate whose inverse-Side winner holds a confirm Root: applied -> its old Cores (Merge survivor / absorbed,
  Split source, 1:1 continuation); not applied (Pending) -> every old Core of its changed component (the existing W08 plan
  scratch changedTargets [p, component, ...] / changedOldCores [slot, component], passed from Main; no new W08 export). New D1
  TouchStarts of that parity on those Cores are cancelled, materialized or Pending alike (the W07 confirm list is the
  same-bar normal Touch exclusion authority); winner-less Roots cancel nothing; a bar-start ActiveTouch is never cancelled.
  After the cancel a component that is still Pending (bar-start ActiveTouch) stays Pending: Event on the bar with ID_NONE,
  mark deferred; a component no longer Pending is taken from the P0 / P1 final plan (P0 is the counterfactual authority).
  P1 rule and the two-plan maximum unchanged. inverseCancelPlan: 9 -> 11 params.
- TouchMark: the W08Touch /7 11-field schema only (isNormalTouch false, not counted); no snapBottom / snapTop / deepestClose
  (the R1 report already wrote none).
- Token review correction: the Two-pass Probe measured the two plan calls, the deferred SoA and the import graph only; the
  W09State /30 export signatures were not in it: inverseDeferredResolve 17 args and inverseConfirmProject 23 args are recorded
  as HIGH_COST_STRUCTURE / mass-forwarding risk. Audit: every parameter of both (and of inverseCancelPlan, 11) is read by
  the body and none is derivable from another (the 10 SoA columns are compacted together; confirmCount bounds a list with a
  physical tail): nothing removed. No new UDT / import / wrapper / body copy / synthetic Probe. Authority: W09State /30
  publish -> Production Main compile; CE10216 -> STOP (GT-5A / D3 / T1-T3).
- Gates: b12_det.py 25/25 (I1-I30 as before, re-run in full because the harness stub changed: the stub SideView keeps a
  Pending Candidate, the stub changed-plan scratch is passed; + I31 bar-start ActiveTouch + Pending confirm + same-component
  new D1 -> ActiveTouch kept, only the D1 cancelled, P0 final, Pending kept, Event ID_NONE, mark deferred; I32 Pending
  destination + related / unrelated D1 -> related cancelled, P1, unrelated TouchStart committed; I33 winner-less confirm + other
  Core D1 -> cancel 0, P1 commits the D1, Event ID_NONE). Older batches not re-run (the change is inside inverseCancelPlan,
  reached only on a bar with an InverseConfirm and a D1 candidate). R3-B1 contract PASS; static: imports 0,
  use-before-definition 0.

## W09 B12 CLOSEOUT

B12 Inverse FVG: COMPLETE, FROZEN (W09State /30 publish PASS, Production Main PASS, exact UNKNOWN; I27 OPEN 0; not reopened).
Frozen: two-pass P0 / P1 (at most two W08 plan calls, one call site), Pending destination D1 cancel (R2), EV_INVERSE_CONFIRM
(one per Root, ID_NONE when not unique / Pending / winner-less), deferred non-normal TouchMark (10-field SoA).

## W09 B13 Same-bar priority: START GATE and Phase A audit (no code change, no fixture re-run)

START GATE: `claude/w09-b07-redesign-v2` at `3707a4d`, clean. Pins: W03F0 /5, W03Apply /4, W03ETimeFvg /3, W06 /25, W07 /11,
W08Core /19, W08Touch /7, W08Runtime /20, W03EMsa /9, W09State /30. Main PASS (exact UNKNOWN).

Production stage map (Main `w08ProductionRaw`): plan (D1 touchStartPlanBuild -> D2 episodePlan -> D3 flipPlan, Episode / Flip
facts merged into d3) -> W08 plan (P0 / P1) -> preflight chain (sideView, inverseConfirmPreflight, D4 reclaimResolve,
transfers, touchStartPostPlanPreflight, W08 preflight) -> commit -> fresh / history / BS transfer apply -> touchStartApply ->
gapBreakApply -> flipApply -> inverseDeferredResolve / inverseConfirmProject -> D1 Event loop (TouchMark, EV_TOUCH_START /
EV_GAP_BREAK) -> episodeApply -> D3 Event loop (Episode / Flip / Inverse) -> Stage J (phaseArmedStageJFinalize, noArm).

Explicit priorities (code):
- A LocalBreak > WeakDepth: episodePlan `meas = not brk`, `hit = meas and ...` (flags 4 / 8 / 32 / 64 need hit): correct.
- B FVG invalidation > Reclaim: reclaimResolve (D4): I = this bar's journal JOP_FVG_INVALIDATE / JGROUP_E1 rows (fact, not the
  apply); a Root in I never counts as kept, other Roots count only when live and ROOT_ACTIVE, so the result is independent of
  the Stage F apply order; no Root write (no revival); another valid Root keeps the Reclaim; else flag 16 and the d3 entry
  are removed (no transition, no EV_RECLAIM, no mark): correct.
- C GapBreak bar: flipPlan candidates = the bar-start Broken PhaseSet with `bBreakSeqs(sb) < currentSeq`; the new BS
  (breakSeq = currentSeq, written in gapBreakApply / episodeApply after the plan) is never a candidate; scope per BS / Core
  (other Cores' older BS evaluated): correct.
- D first Armed on this bar: Stage J `nextArmedFromSeq(baseSeq) = currentSeq + 1`; d1TargetSlots reads the bar-start Phase
  Armed and `currentSeq >= fromSeq`: correct.
- E Root first confirmed on this bar: D1 uses LastArmedRange (previous Stage J) and the pre-commit current Root list
  (planRootIds); topology output reaches only the next bar's Stage J; an InverseConfirm Root's destination D1 is cancelled
  (inverseCancelPlan): correct.
- F Strong-ization: TSS range / masks / counts / density / grade are written only by touchStartApply (plan row) and cleared by
  tssResetRaw; no topology / SideView writer: correct.

D2 outcomes (episodePlan, authority B08 D1 user decision "Break > Reset", B07 same-bar Reset): Break -> flag 1 only (rst =
not brk, meas = not brk: no WeakDepth, no Reset, no weak marks); no Break -> WeakDepth and Reset each by formula; a Reset is
never committed on a Break bar; D2 runs on the TouchStart bar (B Episodes = the plan rows).

Exclusivity proofs (ticks):
- D1 TouchStart vs GapBreak: `if nt ... else if not nt and gapBreakMetExclusive` and gapBreakMetExclusive itself ANDs
  `not normalTouchMetExact`: exclusive.
- Reset vs WeakDepth: Support rst: close >= top + rd -> depth = clamp((top - close) / (top - bottom)) = 0 (Resistance
  symmetric) -> hit only when weakDepthPct <= 0 (then B07 per-row independent flags, WeakDepth before Reset).
- FlipAttempt: `at = ct and not rs0 and not cf and not rc`: exclusive with Confirm and Reclaim (the wouldReclaim fact
  suppresses the Attempt, B10 Q1; a D4 suppression of the Reclaim does not revive it: the fact stays true).
- FlipConfirm vs Reclaim (Support break): cf needs cT <= bT, rc needs cT >= tT + bbT; bT <= tT, bbT >= 0 -> both only when
  bT = tT and bbT = 0 and cT = bT (contact and mv0 hold then). Reachable: a line BS with round(breakBuffer / mintick) = 0
  (breakBuffer < mintick / 2; default 2.0 with mintick >= 5, or a cfg breakBuffer < mintick / 2; validateCfg does not bound
  it). See G2 / I27-B13-1.
- Flip vs Break (Local / Gap): scope C above; a Core holding a BS has both Sides Broken / FlipWait, so no D1 / D2 fact on it.

InverseConfirm conflicts (Root level W07 vs Side level W09): an Inverse Root is INVERSE_WAIT (eligible nowhere) before the
confirm, so it is in no pre-topology Side fact; holders are post-topology current Root lists. TouchStart: destination D1
cancelled (PRIORITY IC). Break / Flip / Reclaim / Reset / WeakDepth: independent Events; Phase effect only through noArm (OR).
Finding G1: inverseConfirmProject skips noArm for a holder whose pav.sidePhases is ActiveTouch, but it runs before
episodeApply / the Stage J baseline, so a holder whose bar-start Episode ends by Reset on this bar (applied component:
overlay FORCE_INACTIVE; role 0 / 1 slot, or a role 2 survivor slot still showing the old Phase) is read as ActiveTouch,
gets no noArm, ends Waiting and Stage J may arm it on the confirm bar (ArmedFromSeq = currentSeq + 1). Canon (I27-B12-3 /
C1-C3 noArm): a materialized destination Side is Waiting on the confirm bar; the ActiveTouch exemption covers an Episode that
continues ("keeps its Episode / TSS"). Derivable, no I27. Fix shape: noArm for every holder (Stage J touches only Waiting /
Armed, so a continuing ActiveTouch is unaffected): the Phase condition removed, no new parameter.

Independent events / global suppression: the only same-bar fact conflict ending in a whole-bar F0 is breakOppositeOkRaw
(B08 D3 / B09, frozen): a Local / Gap Break whose opposite Side has a continuing Episode (no Reset), its own Break, or its own
GapBreak fails touchStartPostPlanPreflight -> every Core's update and Event of the bar dropped (state unchanged, the same
condition can recur next bar). Reachable with crossed Side ranges inside one Core (example, defaults rd 10 / bb 2:
Resistance [96, 110] ActiveTouch, Support [90, 95] armed at close 106 and touched at 92, then close 87: Support Break, the
Resistance Episode neither Resets (<= 86) nor Breaks). Conflicts with the B13 rule "an independent event is never globally
suppressed" -> I27-B13-2. Other F0 guards (inverseConfirmPreflight, busy-Core checks, capacity) are invariant guards, not
fact priorities (busy + continuing Episode is NOT_REACHABLE: FORCE_ACTIVE makes the component Pending).

Event order: D1 loop (d1 canonical: coreId, generationId, Support, Resistance) then the D3 loop over the one merged d3 list
(Episode rows: WeakDepth, Reset, LocalBreak per row; Flip rows; Inverse rows by (coreId, generationId, Side, rootId), ID_NONE
first; Reclaim keyed on the old Side); no per-type pass or sort; priority resolution (reclaimResolve, tsExcl, rst / meas)
happens before ordering. Correct.
TouchMark order: Inverse deferred-resolution marks (original payload, B12) -> D1 TouchStart marks (tsr) -> D3 Flip marks
(tsr[mr]) and immediate Inverse marks in d3 order. Suppressed transitions: cancelled D1 (no plan row), GapBreak, Reclaim
(suppressed or not) write none; role 2 marks via the W08 plan. Exception G2 (degenerate cf and rc: a Flip mark under an
EV_RECLAIM).

Phase writers (one final writer per Side per bar):
| Transition | Fact source (stage) | Priority | Writer | Stage J |
|---|---|---|---|---|
| Armed -> ActiveTouch | D1 touchStartPlanBuild | GapBreak exclusive; IC cancel | touchStartApply | not touched |
| Armed -> Broken, opposite -> FlipWait | D1 GapBreak | B08 D3 opposite rule | gapBreakApply / breakCommitRaw | not touched |
| ActiveTouch -> Broken, opposite -> FlipWait | D2 Break | Break > Reset / WeakDepth | episodeApply / breakCommitRaw | not touched |
| ActiveTouch -> Waiting | D2 Reset | no Break | episodeApply | Waiting -> Armed unless noArm |
| Broken / FlipWait -> Waiting (pair) | D3 FlipConfirm / Reclaim | FVG > Reclaim (D4) | flipApply / bsPairEndRaw | Confirm: noArm; Reclaim: arms |
| non-continuation destination | W08 topology + BS transfer | - | Stage J baseline (Waiting / Broken / FlipWait) | then arming |
| Waiting <-> Armed, Armed -> Waiting | Stage J | noArm OR | phaseArmedStageJFinalize | final |
Apply order touchStart -> gapBreak -> flip -> episode keeps a same-bar TouchStart + Reset / Break and an opposite Reset +
Break consistent (the later row sees FlipWait and does not move it).

noArm sources (push only, read only by `array.includes` in Stage J: OR-only): flipApply (FlipConfirm: sf, sb), bsTransferApply
(destination of a same-bar FlipConfirm, bsPlan column 11), inverseConfirmProject (holders not ActiveTouch; see G1). No
remover.

Priority matrix (same Side; the Flip types per BS pair / Core; A = row wins, B = column wins; FI = Root-level E1 fact, no
Event producer exists for EV_FVG_INVALIDATE):
| | WD | RS | LB | GB | FA | FC | RC | FI | IC |
|---|---|---|---|---|---|---|---|---|---|
| TS | INDEP (B07 B Episode) | INDEP (B07) | INDEP (B08 D1) | MUT_EXCL (nt) | NOT_REACH (Phase) | NOT_REACH | NOT_REACH | INDEP | PRIORITY_B (inverseCancelPlan) |
| WD | - | MUT_EXCL (pct > 0) | PRIORITY_B (meas) | NOT_REACH | NOT_REACH | NOT_REACH | NOT_REACH | INDEP | INDEP |
| RS | | - | PRIORITY_B (rst) | NOT_REACH | NOT_REACH | NOT_REACH | NOT_REACH | INDEP | INDEP (noArm OR; G1) |
| LB | | | - | NOT_REACH (Phase) | PRIORITY_A (scope) | PRIORITY_A (scope) | PRIORITY_A (scope) | INDEP | INDEP |
| GB | | | | - | PRIORITY_A (C) | PRIORITY_A (C) | PRIORITY_A (C) | INDEP | INDEP |
| FA | | | | | - | MUT_EXCL | PRIORITY_B (rc fact) | INDEP | INDEP |
| FC | | | | | | - | MUT_EXCL (bbT >= 1 or bT < tT; else I27-B13-1) | INDEP | INDEP (noArm OR) |
| RC | | | | | | | - | PRIORITY_B (reclaimResolve) | INDEP (noArm OR) |
| FI | | | | | | | | INDEP (per Root) | NOT_REACH same Root (W07) / INDEP |
Diagonal: one row per Side per type (NOT_REACH twice); IC per Root (INDEP). Opposite Side of one Core: Break (L / G) +
Waiting / Armed / Dormant -> FlipWait (SAME_TRANSITION); + Reset Episode -> INDEP (Reset Event, then FlipWait); + continuing
Episode / Break / GapBreak -> whole-bar F0 (I27-B13-2); TouchStart + TouchStart -> INDEP.

Implementation gap list: A-F correct; D2 correct; TouchStart / GapBreak correct; FA / FC / RC partial (G2); Reclaim D4
correct; InverseConfirm partial (G1); Event order correct; TouchMark order correct except G2; Phase writers correct; noArm
OR-only correct; wrong global suppression: the B08 D3 path (I27-B13-2); duplicate 0.
- G1 (derivable): InverseConfirm holder noArm misses a holder whose Episode ends this bar (Reset). Fix: noArm every holder.
- G2 (needs I27-B13-1): cf and rc both true -> fli flag 24: EV_RECLAIM, but flipApply also applies the Confirm-only noArm /
  lastFlipConfirmSeq and the FlipConfirm non-normal mark is written. Whatever the rule, one transition must win (one-line
  guard in flipPlan).

I27 (STOP; not decided by the repo canon):
- I27-B13-1 FlipConfirm vs Reclaim on the degenerate bar (line BS, breakBuffer = 0 ticks, close on the line, retest contact):
  which wins? Recommendation: FlipConfirm (the B08 D1 precedent "Break > Reset": in the zero-buffer degenerate case the
  break-side fact wins; FlipConfirm also carries the movedAway + retest condition).
- I27-B13-2 B08 D3 / B09 opposite rule (frozen fail-closed) vs B13 "never suppress an independent event globally": keep the
  whole-bar F0, or a Core-local rule (e.g. the Break of that Core is held while the opposite Episode continues; other Cores
  commit normally)? Reopens a frozen B08 / B09 decision, so it is the user's.
I27 OPEN = 2.

Token: no code change. Expected B13 code: G1 = one condition removed (W09State), G2 = one guard in flipPlan; I27-B13-2 depends
on the decision (a Core-local hold would touch touchStartPostPlanPreflight / episodePlan, no new UDT / import). No priority
engine.

### B13 I27 resolution (user)

- I27-B13-1 RESOLVED: Reclaim > FlipConfirm (authority: Reclaim = "return to the old side before the Flip is confirmed";
  the Reference evaluates Reclaim before the Flip check). Degenerate bar (line BS, breakBuffer 0 ticks, close on the line):
  Reclaim only; FlipConfirm noArm / lastFlipConfirmSeq / mark / Event / new-Side transition suppressed; Reclaim transition,
  EV_RECLAIM, cleanup and old-Side history as frozen B11. Flag 24 Production-unreachable.
- I27-B13-2 RESOLVED: the B08 D3 / B09 whole-pass F0 stays. The B13 "no global suppression" rule is a semantic rule over valid
  D4 facts / plans; an F0 invariant failure is transaction validity (whole confirmed-5m pass, persistent mutation 0); no
  Core-local commit, no Break pending state / deferred Break Event / carried Break fact. Repeated F0 is fixture-tested, not
  hidden; frequency evidence from W11 / W12 conformance / replay would be a separate architecture-level I27.
- Matrix correction: FC x RC = RECLAIM_PRIORITY (MUTUALLY_EXCLUSIVE under normal prices, Reclaim wins only on the degenerate
  bar); opposite-side Break conflict = TRANSACTION_INVARIANT_FAIL (separate class, checked before INDEPENDENT).
I27 OPEN = 0.

### B13 TOKEN START REVIEW

Main PASS, exact UNKNOWN. Planned: G1 one condition removed (inverseConfirmProject noArm), G2 one guard (flipPlan cf and not
rc), I27-B13-2 Production change 0. New UDT / import / tuple / mass forwarding / priority engine 0; signatures unchanged.
Probe NO (small predicate / condition only).

## W09 B13 Same-bar priority: implementation (W09State /31, Main pin)

- flipPlan: rc evaluated first, `cf = ct and (close beyond the BS on the break side) and not rc` (one predicate each, no
  duplicate). The Attempt guard (not cf and not rc) unchanged. A Reclaim later suppressed by D4 (reclaimResolve) does not
  revive the FlipConfirm (fact-level priority, like the Attempt).
- inverseConfirmProject: every holder joins noArm (no pre-Episode Phase condition). Stage J reads noArm only for Waiting /
  Armed: a holder whose bar-start Episode Resets on the bar ends Waiting (ArmedFromSeq unset); a continuing ActiveTouch keeps
  Episode / TSS (never forced Waiting).
- Main: W09State pin /30 -> /31 only.
Gates (scratchpad harness, Production W09State /31 + Main slice interpreted, W08 stub): `b13_det.py` 9/9 - P1 / P2 degenerate
Support / Resistance Reclaim only (EV_RECLAIM 1, FlipConfirm Event 0, Flip mark 0, noArm 0, lastFlipConfirmSeq unchanged,
cleanup, history kept), P3 buffer > 0 FlipConfirm (B10 unchanged), P4 Reclaim with contact (B11 unchanged), P5 bar-start
ActiveTouch + same-bar Reset + Inverse holder -> Reset done, EV_INVERSE_CONFIRM, noArm, Waiting, ArmedFromSeq unset; P5b next
bar Armed from that bar + 1; P6 continuing ActiveTouch holder keeps ActiveTouch / TSS; P7 opposite conflict F0, mutation 0,
Event 0; P8 P7 + a planned Core 11 D1 -> whole-pass F0, Core 11 not committed. Sensitivity: on /30 P1 / P2 / P5 / P5b / P6
FAIL (5 of 9). Regression (selected only): B08 L8 / F1, B09 G11 / R1, B10 F4 / F10, B11 R1 / R2, B12 I14 / I30: 10/10. R3-B1
contract PASS. Static: W09State imports 0, rc defined before cf, signatures unchanged. random 0, > 5 min 0, 5k / 50k / 200k 0.
TV: W09State /31 publish -> Production Main compile. CE10216 -> STOP (GT-5A / D3 / T1-T3).

### B13 R2 (pre-TV correction, W09State /31 still unpublished, kept at /31)

Problem in the first /31: `cf = ... and not rc` used the raw Reclaim price fact, and the D4 (reclaimResolve, FVG structural
invalidation > Reclaim) ran later, so a D4-suppressed Reclaim still killed the FlipConfirm. Staged priority (user; Reference
`if reclaim and not fvgInvalidNow -> Reclaim else Flip path`): 1. FVG invalidation > Reclaim; 2. Reclaim > FlipConfirm only for
a Reclaim that survives D4.
- reclaimResolve moved before flipPlan (plan loop, one call site, also before the W08 plan that projects the Flip TouchMark
  rows): read-only over the bar-start Broken Sides, out = the BS Sides whose Reclaim D4 suppresses (same rule: BS Root list
  meets this bar's journal E1 invalidation and no other Root is outside it, live, ROOT_ACTIVE). Signature: explicit BS Root
  list arrays instead of PhaseArmedTransferView (that view exists only after the W08 plan) + out; no longer edits fli / d3.
- flipPlan + rcSup: `rc = rawReclaimPrice and not includes(rcSup, sb)` (one price predicate), `cf = rawConfirm and not rc`,
  Attempt guard `not cf and not rc` unchanged in form, so a D4-suppressed Reclaim leaves the whole Flip path (Confirm and
  Attempt; Reference "else Flip path"). Before B13 a D4-suppressed Reclaim also left no Attempt (raw wouldReclaim fact): this
  Attempt consequence is recorded explicitly (P12).
- Cases: A raw Reclaim, no invalidation, raw Confirm -> Reclaim only; B + invalidation -> FlipConfirm (Event, mark, noArm,
  lastFlipConfirmSeq); C + invalidation, no Confirm -> neither; D no raw Reclaim -> FlipConfirm.
- Main: reclaimResolve call moved from the preflight chain into the plan loop (before flipPlan), scratch `rcs`; pin /31.
- G1 (holder noArm) and I27-B13-2 (whole-pass F0) unchanged. New UDT / import / export / tuple / Probe 0 (flipPlan +1 param,
  reclaimResolve 10 -> 13 params).
Gates: `b13_det.py` 13/13 (P1-P8 kept, P9 degenerate + invalidation + Confirm -> FlipConfirm with mark / noArm /
lastFlipConfirmSeq, P10 degenerate raw Reclaim + invalidation, no Flip condition -> nothing, P11 degenerate without
invalidation -> Reclaim, P12 Attempt after a D4-suppressed Reclaim). Sensitivity on the first /31 (old wiring): P9 / P12 FAIL.
Affected regression only: B10 F4 / F5, B11 R1 / R2 / R14 / R15: 6/6. R3-B1 contract PASS; W09State imports 0. Harness txn8
mirrors the new Main order. random 0, > 5 min 0.
TV: W09State /31 publish -> Production Main compile; CE10216 -> STOP.

## W09 B13 CLOSEOUT

B13 Same-bar priority: COMPLETE, FROZEN (W09State /31 publish PASS, Production Main PASS, exact UNKNOWN; I27 OPEN 0; not
reopened). Frozen: LocalBreak > WeakDepth, Break > Reset, FVG invalidation > Reclaim (D4 before flipPlan), effective Reclaim >
FlipConfirm, effective Reclaim false -> Flip path (Confirm and Attempt on the effective Reclaim), GapBreak-bar Flip / Reclaim
exclusion (breakSeq < currentSeq), InverseConfirm holder noArm (every holder), whole-pass F0 kept, semantic priority separate
from transaction failure.

## W09 B14 Phase / Grade finalization: START GATE and Phase A audit (no code change, no fixture run)

START GATE: `claude/w09-b07-redesign-v2` at `c9623bd`, clean. Pins: W03F0 /5, W03Apply /4, W03ETimeFvg /3, W06 /25, W07 /11,
W08Core /19, W08Touch /7, W08Runtime /20, W03EMsa /9, W09State /31. Main PASS (exact UNKNOWN).

Stage J = `phaseArmedStageJFinalize` (last W09 call of the committed pass; after it Main only copies the W08 scalars and the
dependency carry; an F0 bar runs no Stage J). Step 1: every applied fresh / Merge / Split destination Side -> Waiting (or
Broken / FlipWait from a transferred BS, Grade Unavailable, Broken / FlipWait index attach), ArmedFromSeq unset,
LastArmedRange na; a 1:1 continuation keeps its Phase. Step 2: every live Side Upcoming = TouchCount + 1; Waiting / Armed only:
Grade = gradeExact(target Upcoming), q = eligible and non-psych Root and EffectiveRange valid and armedDistanceMet and not
noArm; Waiting + q -> Armed (ArmedFromSeq = currentSeq + 1, LastArmedRange = EffectiveRange, both Armed indexes); Armed + q ->
Armed (ArmedFromSeq kept, range re-keyed); Armed + not q -> Waiting (index removed; ArmedFromSeq / LastArmedRange kept: B06
option b, read only for Phase Armed). ActiveTouch / Broken / FlipWait / Dormant untouched.

Phase table (A current, B fact, C final Phase, D final Grade, E ArmedFromSeq, F history, G writer, H index, I revision):
| A | B | C | D | E | F | G | H | I |
|---|---|---|---|---|---|---|---|---|
| Waiting | distance met, eligible, non-psych, no noArm | Armed | gradeExact(Upcoming) | currentSeq + 1 | kept | Stage J | PhaseSet + Armed indexes | none |
| Waiting | not met / noArm | Waiting | gradeExact(Upcoming) | unchanged | kept | Stage J | none | none |
| Armed | normal Touch (D1, prev-bar Armed, fromSeq <= seq) | ActiveTouch | Episode: gradeExact(CurrentTouchNo); TSS grade = plan | unchanged | TouchCount + 1, WeakByTouch OR, TSS | touchStartApply, episodeApply | Armed detach, PhaseSet | none |
| Armed | complete GapBreak | old Broken / opp FlipWait | Unavailable | unchanged | kept, BS written | gapBreakApply / breakCommitRaw | Armed detach, PhaseSet, Broken / FlipWait | none |
| Armed | distance lost / noArm | Waiting | gradeExact(Upcoming) | kept (option b) | kept | Stage J | Armed detach, PhaseSet | none |
| ActiveTouch | continuing Episode | ActiveTouch | gradeExact(CurrentTouchNo, current structure) | unchanged | WeakByDepth / MaxDepth monotone | episodeApply | none | none |
| ActiveTouch | Snapshot Reset, no Break | Waiting -> Stage J Armed if q (noArm: Waiting) | gradeExact(Upcoming) | currentSeq + 1 if armed | kept, TSS cleared | episodeApply -> Stage J | PhaseSet (+ Armed) | none |
| ActiveTouch | LocalBreak | old Broken / opp FlipWait | Unavailable | unchanged | kept, BS from TSS | episodeApply / breakCommitRaw | PhaseSet, Broken / FlipWait | none |
| Broken / FlipWait | none / movedAway / retest / Attempt | unchanged | Unavailable | unchanged | kept | flipApply (flags) | none | none |
| Broken / FlipWait | effective Reclaim | both Waiting -> Stage J (old Side may arm) | gradeExact(Upcoming) | currentSeq + 1 if armed | kept | flipApply / bsPairEndRaw -> Stage J | Broken / FlipWait detach, PhaseSet | none |
| Broken / FlipWait | FlipConfirm | both Waiting (noArm) | gradeExact(Upcoming) | unchanged | kept; lastFlipConfirmSeq | flipApply -> Stage J | as above | none |
| InverseConfirm holder | confirm Root in its current list | Waiting / ActiveTouch kept (noArm) | gradeExact | unchanged | kept | inverseConfirmProject -> Stage J | Armed detach if it was Armed | none |
| Pending release bar | Episode ended, component applied | destination baseline Waiting -> current close | gradeExact(Upcoming) | currentSeq + 1 if armed | C2 transfer | W08 commit, transfers, Stage J | PhaseSet, Armed | W08 topology / range |
| Dormant | - | no writer | - | - | - | none | Dormant set / recovery index storage only | - |

Checks: §5 Armed formula (armedDistanceMet, ticks, inclusive) PASS; same-bar Touch forbidden (fromSeq = currentSeq + 1, D1
reads the bar-start Phase) PASS; FlipConfirm / InverseConfirm bar no Armed (noArm) PASS. §6 noArm sources: flipApply
(FlipConfirm sf / sb), bsTransferApply (destination of a same-bar FlipConfirm), inverseConfirmProject (every holder); push only,
read only by `array.includes` in Stage J; no priority / Grade in it: PASS. §7 ActiveTouch: Stage J skips it; a Reset ends the
Episode first (episodeApply before Stage J), G1 consistent: PASS. §8 Broken / FlipWait: only flipApply (bsPairEndRaw) releases
it; Stage J skips; baseline restores it from a transferred BS: PASS. §11 gradeExact order Unavailable -> Weak -> Strong ->
Neutral: PASS (flipUnconfirmed is passed false; Broken / FlipWait carry a direct GR_UNAVAILABLE and are never re-graded until
a Flip / Reclaim ends the BS: equivalent). §12 target Touch No: Waiting / Armed Upcoming, ActiveTouch CurrentTouchNo (fixed
TSS no): PASS. §13 TouchStartGrade = tssGrades, written only by touchStartApply: PASS. §14 Weak persistence: WeakByTouch /
WeakByDepth writers are touchStartApply (OR), episodeApply (OR), touchHistoryTransferApply (I27-15 / 18 Merge / Split transfer
from the marks, frozen), W08 reset table (new slot / free); no writer in Reset / Reclaim / Flip / Stage J: PASS. §15 Phase and
Grade separate (gradeExact has no Phase input): PASS. §16 BaseStrong from the post-commit SideView into the next View Grade
(Stage J) and the current Episode View Grade (episodeApply); TSS untouched: PASS. §17 Stage J writes no history (reads only);
new-slot reset = W08 coreDeferredStateRaw; Generation creation untouched (W10): PASS. §18 Pending: an ActiveTouch component is
not applied, Stage J step 1 never runs for it; on the release bar the baseline then the current close: PASS. §20 indexes:
phaseMoveRaw (PhaseSet detach / write / add), priceOrderUpdate (Armed), bsIndexRaw (Broken / FlipWait), incremental, invariant
violation = runtime.error: PASS. §21 revision: no Side-state revision exists; Stage J writes none (topologyRevision /
coreRangeRevision are W08 commit's): PASS (no architecture change).

Writer matrix (persistent):
| Field | D1 | D2 | D3 / D4 | Topology transfer | Stage J | Generation / slot reset |
|---|---|---|---|---|---|---|
| sidePhase | touchStartApply, gapBreakApply (breakCommitRaw) | episodeApply (Reset, breakCommitRaw) | flipApply (bsPairEndRaw) | - | Stage J baseline + step 2 | W08 new slot (Waiting) |
| sideGrade | breakCommitRaw | episodeApply (no Reset / Break), breakCommitRaw | - | - | Stage J (baseline BS Unavailable, step 2) | W08 reset (Unavailable) |
| sideArmedFromSeq | - | - | - | - | Stage J | W08 reset (unset) |
| sideUpcomingTouchNo | - | - | - | - | Stage J | W08 reset (0) |
| sideCurrentTouchNo | touchStartApply, breakCommitRaw | episodeApply | bsPairEndRaw | touchHistoryTransferApply (0) | - | W08 reset (0) |
| sideWeakByTouch | touchStartApply | - | - | touchHistoryTransferApply | - | W08 reset |
| sideWeakByDepth | - | episodeApply | - | touchHistoryTransferApply | - | W08 reset |
| sideMaxDepthPct | - | episodeApply | - | touchHistoryTransferApply | - | W08 reset |
| lastFlipConfirmSeq | - | - | flipApply | bsTransferApply | - | W08 reset (unset) |
No semantic writer after Stage J. No duplicate writer per transition (one Phase writer phaseMoveRaw).

Implementation gap list: Waiting / Armed / ActiveTouch / Broken / FlipWait / Reclaim / FlipConfirm / InverseConfirm destination
/ Pending release / Grade order / target Touch No / TouchStartGrade / Weak persistence / BaseStrong / Generation boundary /
indexes / revision / noArm: PASS. Dormant entry, Dormant recovery, Dormant index maintenance, coreDormantFlags: MISSING (no
writer anywhere: PH_DORMANT is read by the PhaseSet helpers, breakOppositeOkRaw and the transfer preflight only;
cfg.dormantDistance = 500.0 is only fingerprinted; the Dormant recovery bottom / top orders and the Dormant Core prune heap are
W02 storage only). DUPLICATE 0, CONFLICT 0, PARTIAL 0. Dormant protection (§9) holds vacuously (nothing enters Dormant).

I27 (STOP; the repo canon does not define these):
- I27-B14-1 Dormant condition: the distance and its reference (close vs EffectiveRange edge per Side, e.g. Support close >=
  top + dormantDistance?), inclusive or not, the Phases it applies to (Waiting / Armed only, per the given table) and whether it
  is per Side (Phase) or per Core (coreDormantFlags; both Sides?).
- I27-B14-2 monitor range / recovery: the recovery predicate (the same distance strictly inside? the Dormant recovery index keys
  = which edge), the Phase on recovery (Waiting, then the Stage J Armed test on the same bar from currentSeq + 1, or Waiting
  only on the recovery bar), and the Armed index / LastArmedRange / ArmedFromSeq on Dormant entry.
- I27-B14-3 Dormant vs topology: a Dormant Side / Core as a Merge / Split source or 1:1 continuation (baseline Waiting and
  re-evaluate, or keep Dormant), and the Dormant Core prune heap (B14 or the prune owner batch).
I27 OPEN = 3.

Token: no code change. Expected B14 code after I27: Dormant entry / recovery inside Stage J step 2 (existing priceOrderUpdate on
the Dormant recovery orders, phaseMoveRaw), no new UDT / import; Probe decision at the TOKEN START REVIEW.

### B14 I27 resolution (user) and Phase A correction

Correction: the Phase A statement "the repo canon does not define Dormant" is withdrawn; the W09 canonical bundle holds the
Dormant semantic contract (given by the user, recorded here). I27-B14-1 / 2 / 3 CLOSED, I27 OPEN = 0. Fixed rules: Dormant is
per Side View; d = nearest distance of baseClose to the EffectiveZoneRange (below bottom - close, above close - top, inside 0);
enter when d > dormantDistance (equality = monitor range), recover when d <= dormantDistance; only Waiting / Armed enter
(never ActiveTouch / Broken / FlipWait / InverseWait / PendingTopology / PendingGeneration); recovery -> Waiting then the usual
noArm / Reset distance / Grade / Upcoming in the same Stage J (Armed from currentSeq + 1, no Touch on the recovery bar);
Dormant is no invalidation (IDs, Generation, history kept; ArmedFromSeq / LastArmedRange not cleared, non-authoritative
outside Armed); Grade by the exact order (Dormant is no Grade reason); coreDormantFlags derived from the Side Phases (never
read back); no Dormant Merge / Split rule (Stage J re-evaluates after topology); the Dormant recovery price index (B18) and the
prune heap (Stage K) are out of scope.

### B14 TOKEN START REVIEW

Main PASS, exact UNKNOWN (no colour class). Plan: Stage J (phaseArmedStageJFinalize, single final writer) + 6 parameters
(ei, fli, dormantDistance, corePendingTopologyFlags, corePendingGenerationFlags, coreDormantFlags), two private helpers
(dormantFarRaw on closeBeyondRaw, stageJTransitionRaw), Main: one call site + pins. Design-time conflict found and resolved by
precedent: the W08 MERGE_STATE_DEFAULT_GUARD compares coreDormantFlags with its default false for every freed (absorbed)
Core, so a W09 writer setting it true would fail the W08 F0 of any later Merge absorbing that Core (whole-pass F0, repeatable).
Resolution = the B08 (/18 BreakSnapshot) / B10 (/19 Flip fields) precedent: the field becomes reset-only in
coreDeferredStateRaw (the reset still writes false; nothing else changes; Merge / Split / Pending semantics unchanged) ->
W08Runtime /21. New UDT / import / export / tuple 0. Probe NO (small Stage J diff, one guard row).

## W09 B14 Phase / Grade finalization: implementation (W09State /32, W08Runtime /21, Main pins)

- W09State /32: dormantFarRaw (far = not (bottom - dd <= close <= top + dd) in ticks via closeBeyondRaw, dd rounded once;
  na / no range -> false); stageJTransitionRaw (an ei row that Resets / Breaks, or a fli pair end with flag >= 8: the
  "transition" of the bar). Stage J step 2 now covers Waiting / Armed / Dormant: Grade first (unchanged formula, also for
  Dormant); Dormant and not far -> Waiting (phaseMoveRaw) and the usual Armed test; Waiting / Armed and far and no pending
  (corePendingTopologyFlags / corePendingGenerationFlags) and not noArm and no same-bar transition -> Dormant (Armed indexes left
  through the existing priceOrderUpdate path, ArmedFromSeq / LastArmedRange untouched); final Phase through one phaseMoveRaw.
  Per live Core after its two Sides: coreDormantFlags = no pending and each Side Dormant or a non-participating (not eligible)
  Waiting Side. A pending Core blocks entry only (an existing Dormant Side recovers by distance alone).
- W08Runtime /21: coreDormantFlags reset-only (guard 9 -> 8 fields).
- Main: Stage J call + ei, fli, cfg.dormantDistance, cr.corePendingTopologyFlags, cr.corePendingGenerationFlags,
  cr.coreDormantFlags; pins W09State /31 -> /32, W08Runtime /20 -> /21.
- Writers: Dormant (PH_DORMANT in / out) = Stage J only; coreDormantFlags = Stage J (derivation) + W08 slot reset.
Gates (scratchpad harness, Production sources interpreted, W08 stub): `b14_det.py` 17/17 (D1-D18 + D18b FlipConfirm bar).
Regression (selected): B08 L5 / L8 / F1 / M1, B09 G11 / R1, B10 F4 / F5 / F10, B11 R1 / R2 / R8 / R12 / R14 / R15, B12 I14 / I30,
B13 P1-P12: all PASS. R3-B1 contract PASS. Static: W09State imports 0, helpers defined before Stage J, no shadowing.
random 0, > 5 min 0.

### B14 TOKEN END REVIEW

Diff: W09State +2 private helpers (~25 lines), Stage J +6 params and ~20 lines; W08Runtime 1 guard row -> reset-only (smaller);
Main 1 call (+6 args) and 2 pins. No new UDT / import / export / tuple / mass forwarding; no semantic cut. Exact tokens UNKNOWN
(TradingView only). TV: W08Runtime /21 publish, W09State /32 publish, Production Main compile; CE10216 / CE10117 -> STOP.

### B14 Final Gate: D19, Default Guard, W08 conformance (Production unchanged since 89a52ce)

User ACCEPT: W08Runtime /21 coreDormantFlags reset-only (formal: W09 Stage J is the writer; reset / alloc / slot reuse write
false; never used by survivor / continuation / identity / pending predicates; no Side Phase from it), same-bar transition
Sides not entering Dormant. I27 OPEN 0.

D19 (scratch `b14_d19.py`: bar-start ActiveTouch Resistance of Core 10 Resets on the bar -> component READY -> same-bar
topology; close 60, holder range 100..110, d 40 > dormantDistance 20):
| Case | A holder not Dormant on the bar | B next bar Dormant | C nothing on freed slot | D other Sides normal | E IDs / survivor / continuation | F no F0 |
|---|---|---|---|---|---|---|
| Merge survivor (Core 10 survives) | PASS (slot 1 Armed) | PASS | PASS | PASS | PASS | PASS |
| Merge absorbed (Core 10 into Core 11) | FAIL: survivor Resistance slot 3 Dormant on the transition bar | PASS | PASS | PASS | PASS | PASS |
| Split continuation | PASS | PASS | PASS | PASS | PASS | PASS |
G (W08 F0 variant): persistent mutation 0, Event 0. D1-D18 / D18b: 17/17 (harness nextbar now also clears the W08 stub X
scratch; Production unchanged).
Cause: stageJTransitionRaw keys the transition by the pre-topology Side slot (ei / fli rows); when the transitioned Side's
state flows into a different post-topology slot (Merge absorbed -> survivor, and by the same reading a Split fresh child,
not built in the stub), the final holder is not recognized. Per the gate rule: D19 FAIL -> STOP, no fix applied.

Default Guard (scratch `b14_guard.py`, coreDeferredStateRaw interpreted from the /21 and /20 sources): G1 absorbed Core with
coreDormantFlags true and every other field default -> /21 PASS (/20 rejected); G2 one remaining guard field non-default
(sideFvgRootCounts / corePruneRevisions) -> FAIL (F0); G3 F0 -> persistent mutation 0 (preflightPass is read-only; harness F0
variant mutation 0 / Event 0); G4 reset write -> coreDormantFlags false (alloc pushes false, unchanged); G5 Merge survivor flag
re-derived by Stage J from its final Sides (absorbed true not carried: false with one live Side, true with both Dormant).

W08 B16 / B17 conformance: not re-run. The two TradingView harnesses pin W08Runtime /13 (B17) and /4 (B16) with W08Core /18 /
/16 and call W08Runtime.planPass / runShadow, removed in W08Runtime /20 (TC-C); running them on /21 needs a harness port (API +
three pins). Static: /20 -> /21 differs by exactly the coreDormantFlags guard row (git diff: 3 + / 1 -), and neither harness nor
W08Core / W08Touch writes coreDormantFlags (0 references), so every harness guard outcome is identical by construction.
TradingView (W08Runtime /21, W09State /32 publish, Main compile): not performed (STOP on D19).
B14: NOT COMPLETE.

### B14 D19 correction (W09State /33) and the W08Runtime /21 conformance decision

User: D19 fix ACCEPT; no /21 port of the old B16 / B17 harnesses (they call planPass / runShadow removed in /20 and never
write coreDormantFlags, so they cannot reach the changed branch). B14_W08_RUNTIME21_CONFORMANCE =
STATIC_EQUIVALENCE_PLUS_TARGETED_GUARD: (1) function-level diff /20 -> /21 = coreDeferredStateRaw only (the coreDormantFlags
compare row -> reset-only write; git diff c9623bd: 3 + / 1 -); (2) every other reachable W08Runtime function byte-identical;
(3) G1-G5 PASS; (4) the remaining guard fields keep the F0 contract (G2); (5) W08 topology semantics change 0. Formal integrated
W08 conformance carried to W11 / W12. I27 OPEN 0.

TOKEN START REVIEW: pass-local projection inside Stage J from the existing classes / plan mapping (invSourcesRaw, moved before
Stage J unchanged); no wrapper / tuple / forwarding / UDT copy; no new parameter. Probe NO.

Implementation (W09State /33; W08Runtime /21 kept; Main pins W08Runtime /21, W09State /33):
- invSourcesRaw moved unchanged before Stage J (B12 Inverse and Stage J share it).
- Stage J step 1: pass-local `trx` (per Side slot, -1 none / 0 / 1): for every applied non-continuation destination p, a Merge
  target Side (survivor / fresh) = OR of stageJTransitionRaw over its survivor and absorbed source Sides of the same parity;
  a Split continuation child = its source Side; a fresh target and a Split fresh child = 0 (no lifecycle inheritance, no
  broadcast). Step 2: same-bar transition = trx when set, else the direct slot fact (continuation / untouched Cores). The
  Dormant entry condition is unchanged otherwise (Waiting / Armed, far, not pending, not noArm, not same-bar transition);
  noArm untouched; nothing persistent, nothing carried to the next bar.
Gates: D19 (`b14_d19.py`): Merge survivor / Merge absorbed / Split continuation A-G all PASS (absorbed: survivor Resistance
slot 3 Armed, not Dormant, on the transition bar; next bar Dormant); D19-D Split continuation + fresh child (Stage J unit with
the post-commit split state): continuation child Resistance not Dormant, fresh child Resistance Dormant (no broadcast); D19-D2 a
Reset row on the reused fresh slot is not read (projection 0). G (F0) mutation 0. D1-D18 / D18b 17/17. Default Guard G1-G5 PASS
(/20 pinned at c9623bd for the contrast). B08-B13 target regression (B08 L5 / L8 / F1 / M1, B09 G11 / R1, B10 F4 / F5 / F10, B11
R1 / R2 / R8 / R12 / R14 / R15, B12 I14 / I30, B13 P1-P12) PASS. R3-B1 contract PASS. Static: W09State imports 0,
invSourcesRaw / stageJTransitionRaw / dormantFarRaw defined before Stage J, no shadowing (step 1 loop variables m / qi / tr /
src distinct).
TOKEN END REVIEW: W09State +~15 lines in Stage J and one function moved (no body copy); signatures unchanged; Main 1 pin.
Exact tokens UNKNOWN (no colour class). TV next: W08Runtime /21 publish, W09State /33 publish, Production Main compile.
B14: not COMPLETE until the Main compile PASS.

## W09 B14 CLOSEOUT: W09_B14_PHASE_GRADE_DORMANT_FINALIZATION = COMPLETE / FROZEN

TradingView: W08Runtime /21 publish PASS, W09State /33 publish PASS, Production Main compile PASS (pins W08Runtime /21,
W09State /33), compile error 0, runtime error 0, exact compiled tokens UNKNOWN (no GREEN / YELLOW / RED class). Production
HEAD 15cc56b (this closeout changes the ledger only). I27 OPEN 0.

Frozen:
1. Dormant is a Side Phase.
2. Entry: Phase Waiting or Armed AND d > cfg.dormantDistance AND no PendingTopology AND no PendingGeneration AND not noArm
   AND no same-bar transition.
3. d: baseClose < effectiveBottom -> effectiveBottom - baseClose; baseClose > effectiveTop -> baseClose - effectiveTop; inside 0.
4. d == dormantDistance -> not Dormant.
5. Recovery: d <= dormantDistance -> Waiting -> the usual Armed test in the same Stage J -> Reset met and not noArm -> Armed,
   armedFromSeq = currentSeq + 1.
6. No normal Touch on the recovery bar.
7. Grade on a Dormant Side by the exact order Unavailable -> Weak -> Strong -> Neutral; the Dormant distance is no Weak /
   Unavailable reason.
8. Dormant alone clears no Core ID / Generation ID / TouchCount / Weak / Fresh / consumption history / Generation history.
9. armedFromSeq / lastArmedRangeBottom / lastArmedRangeTop not cleared by Dormant entry; non-authoritative outside Armed.
10. coreDormantFlags: Core-level lifecycle / optimization flag derived in Stage J from the Side Phases; never a Side Phase
    authority.
11. coreDormantFlags outside the W08 Default Guard; false on reset / alloc / slot reuse (W08Runtime /21).
12. The same-bar transition fact is pass-local, never persistent.
13. Across topology it is projected with the same source -> destination relation as the Side lifecycle / history transfer.
14. Merge: target Side = OR of the survivor and absorbed source transitions.
15. Split: only the continuation child inherits the source transition.
16. Fresh target and Split fresh child: no transition inherited.
17. D19-D2: a fresh child never reads a stale source transition left on a reused slot.
18. noArm projection and transition projection are separate.
19. phaseArmedStageJFinalize stays the single final writer of Phase / Grade / Armed / Dormant.
20. W08 topology semantics change 0 (Core ID, Generation ID, Merge survivor, Split continuation, Pending component, TouchMark:
    W08 frozen contract).

Evidence: D1-D18 / D18b 17/17 PASS; D19 Merge survivor / Merge absorbed / Split continuation / Split continuation + fresh child
/ D19-D2 slot reuse PASS; F0 persistent mutation 0, Event 0; Default Guard G1-G5 PASS; B08-B13 target regression PASS; R3-B1
contract PASS; static PASS; TradingView as above.
B14_W08_RUNTIME21_CONFORMANCE = STATIC_EQUIVALENCE_PLUS_TARGETED_GUARD (/20 -> /21 = the coreDormantFlags guard row of
coreDeferredStateRaw only; every other reachable W08Runtime function semantically identical); formal integrated W08
conformance carried to W11 / W12 (not a B14 completion condition).
Carry to B15: no B14 redesign; Stage J final authority kept; Dormant / transition projection not changed again; B15 Merge
Side transfer takes the B14 state as its input.

## W09 B15 Merge Side transfer: canonical docs, START GATE and Phase A audit (no code change)

Canonical docs (docs-only commit e713f2f, verbatim): docs/canonical/Zone_definition_spec_v2(5).md SHA-256
f0ada2d851477850aa3d65463056e0318434b0c362383d475d49f9f6e1049cd1 (= the required value);
docs/canonical/09_窓09_State_Touch_Break_Flip_Reclaim_Inverse(1).md SHA-256
8f5373a47543875927ef403abb9b4cd6fe300e8bc981b435c8848b5b274b9ef8.
START GATE: branch claude/w09-b07-redesign-v2, local = remote = e713f2f, 0 / 0, clean; W08Runtime /21, W09State /33 (Main
pins); ledger, HANDOFF_W08, both canonical files present. Authority: W09 bundle > spec v2(5) > HANDOFF_W08 > ledger / B01-B14
closeouts > Production > old B01 audit.
TOKEN START REVIEW: Main PASS, exact UNKNOWN (no class); audit only; new UDT / tuple / forwarding / Main logic candidates: none
needed (see below). Probe NO.

Current W08Runtime /21 coreDeferredStateRaw (re-extracted; the old "73" is not used):
- CURRENT_GUARD_FIELD_COUNT = 8: coreLastSeenTimes, corePruneRevisions, corePendingGenerationFlags [Core];
  sideInverseAttemptCounts, sideFvgDirectionMasks, sideFvgRootCounts, sideFvgFreshCounts, sideFvgStructuralStateMasks [Side].
  Writers: alloc / reset only (no Production writer) -> always default -> never fails a Merge; kept (no writer, no rule).
- CURRENT_RESET_ONLY_FIELD_COUNT = 67: Core coreZoneFreshFlags, coreDormantFlags; Side sideTouchCounts, sideWeakByTouchFlags,
  sideWeakByDepthFlags, sideMaxDepthPcts, sideFreshFlags, sidePhases, sideGrades, sideCurrentTouchNos, sideUpcomingTouchNos,
  sideArmedFromSeqs, sideLastArmedRangeBottoms / Tops, sideLastNormalTouchTimes, sideEffectiveBottoms / Tops,
  sideReferencePrices, sideCCounts, sideHCounts, sideDensities, sideBaseStrongFlags, sideHasNonPsychRootFlags,
  sideIsBroadContextFlags, sideEligibleFlags, sideCategoryMasks, sideHighMasks, the 21 TouchStartSnapshot fields (valid, coreId,
  generationId, side, range bottom / top, category / high masks, C, H, density, grade, currentTouchNo, approachSide, startSeq,
  startTime, deepestClose, maxDepthPct, Root head / tail / count), sideCurrentRoot head / tail / count, sideFlipAttemptCounts,
  sideLastFlipConfirmSeqs, the 14 BreakSnapshot fields.
- CURRENT_TRANSFER_RELEVANT_FIELD_COUNT = 13 persistent consumption / lifecycle fields with a Merge writer: sideTouchCounts,
  sideWeakByTouchFlags, sideWeakByDepthFlags, sideMaxDepthPcts, sideLastNormalTouchTimes, sideCurrentTouchNos, sideFreshFlags,
  coreZoneFreshFlags, BreakSnapshot (14 fields as one row), sideFlipAttemptCounts, sideLastFlipConfirmSeqs, completed TSS
  (cleanup only), coreDormantFlags (Stage J derivation); the rest is Stage J / SideView re-derivation or slot reset.

Resolved since the old "UNDEFINED" audit (authority -> Production writer):
| Field group | Merge rule | Authority | Writer |
|---|---|---|---|
| TouchCount / LastNormalTouchTime / CurrentTouchNo | marks of the W08 Merge TouchMark plan for that Side (union -> contact with the new range -> same Side / time / contact dedupe, frozen W08), normal marks: count, latest time; truncated: max with the relevant sources; CurrentTouchNo 0 | spec 12.2 (no zero reset, same contact once, only touches contacting the new range), 11.4 step 3; B06 I27-15 / I27-18 (frozen) | touchHistoryTransferPlan / Apply |
| WeakByDepth / MaxDepth | OR / max over those marks (truncated: + sources) | spec 9.3 / 12.2; B06 I27-18 | same |
| WeakByTouch | weakByTouchNow(resulting count) | spec 13.4 (touch-count Weak follows the count) | same |
| SideFresh / ZoneFresh | AND over every source Core (survivor and absorbed; a Side that never held a winner is true); fresh target all true | spec 16 (Fresh revives only in a new generation); B06 I27-15 §8 / §15 / §16 | freshTransferPlan / Apply |
| BreakSnapshot (14) | one whole row: breakSeq max -> breakTime max -> old Core canonical order; no field mix | I27-15 #1 (ledger) | bsTransferPlan / Apply |
| flipAttemptCount | the selected BS source row (+1 for its Attempt of the bar) | B10 Q4 | bsTransferPlan |
| lastFlipConfirmSeq | max over the same-Side sources (a Confirm of the bar = baseSeq) | B10 Q4 | bsTransferPlan |
| Phase / Armed / ArmedFromSeq / LastArmedRange | destination baseline Waiting (Broken / FlipWait from a valid BS), unset / na, then Stage J (B14 Dormant included) | I27-15 #3 / #4, spec 11.4 steps 4-5, B14 | phaseArmedStageJFinalize |
| Grade / Upcoming / EffectiveRange / C / H / Density / BaseStrong / eligibility / masks / reference price / current Root lists | recomputed from the final topology | spec 4.3 / 6 / 7.2 / 8.3 | sideViewProduce, w09CurrentRootProduceRaw, Stage J |
| TSS | never merged: an ActiveTouch component is PendingTopology (W08 frozen, spec 11.4); a TSS completed this bar (Reset / Break) is captured and cleared after commit | spec 11.1 / 11.4, I27-15 #4 | touchHistoryTransferApply |
| coreDormantFlags | Stage J derivation, not transferred | B14 | Stage J |
| same-bar transition / noArm | pass-local, not persistent | B13 / B14 | Stage J / applies |
sideLastNormalTouchTimes: writers touchStartApply and touchHistoryTransferApply; only reader = touchHistoryTransferPlan's
truncated fallback for itself; no Event / Grade / Phase / View / Main accessor reads it -> non-authoritative for results (no I27).

Reachability (same Side): A both default (untouched Merge), B survivor touched, C absorbed touched, D both touched / Broken
sources: all reachable once no ActiveTouch is in the component (the W08 Pending predicate); ActiveTouch-with-ActiveTouch is
unreachable. Alloc default != semantic initial for Fresh (reset false, new generation true): freshTransferPlan sets fresh
targets true explicitly; Merge targets take the AND of the source semantic values.
TouchMark boundary: the W08 Merge TouchMark plan is frozen (union, contact, Side, dedupe key, survivor-first representative,
no payload mix); the Side history is derived from it only as spec 12.2 / 11.4 state; no TSS / BS / Fresh is rebuilt from marks.
Source -> target: mergeOfP / mergeRelations [p, survivor slot, survivor id, absorbed offset, count] / mergeAbsorbed, classes
(TX_MERGE_SURVIVOR / TX_MERGE_FRESH), materializedCoreSlots, invSourcesRaw; W08 topology selection untouched.
Default Guard: no change (the 8 remaining fields have no writer and no transfer rule; removed only with a writer + rule +
conformance).
I27 candidates: none meet all three conditions (reachable, result-changing, not uniquely decided): every reachable
result-changing Merge field has a frozen B06 / B08 / B10 / B14 rule or a spec 12.2 / 16 rule. Provenance note: the B06
I27-15 §8 / §15 / §16 and I27-18 texts are recorded in the frozen Production comments, not as ledger text (I27-15 BS part is).
I27 OPEN = 0. W09_CARRY_MERGE_SIDE_STATE_TRANSFER: satisfied by B06 (history / Fresh), B08 (BS), B10 (Flip state), B14
(Phase / Dormant); B15 Phase B = verification only (Merge A-D x field conformance fixtures on the existing harness, carry
closure), no Production change expected.

## W09 B15 Merge Side transfer: Phase B (verification only) and CLOSEOUT

START: 6ce942f, local = remote, 0 / 0, clean; W08Runtime /21, W09State /33; Main compile PASS (B14); I27 OPEN 0.
TOKEN START REVIEW: Main PASS, exact UNKNOWN. TOKEN END REVIEW: Production delta 0, compiled token delta N/A (UNKNOWN); no
colour class.

Authority provenance (frozen implementation decisions; git history, not comments alone):
| Decision | First commit / batch | Rule (current code = introduced rule) | Fixtures at introduction / now | Later changes |
|---|---|---|---|---|
| I27-15 §8 / §15 / §16 Fresh transfer | 5e2063c W09 B06-B2C-B0 (W09State /15, W08Runtime /9 Fresh guard release) | new generation all true; 1:1 untouched; Merge = AND over every source Core (ZoneFresh, each SideFresh); Split child from its normal marks (none + complete -> true, truncated -> no inferred revival) | b0_det.py + mutB0_01..12 (scratchpad); now B15 M1 / M5 / M13 | b12adcd B07-R3A: sources read through episodeSideValueRaw (projected same-bar Stage D values); rule lines unchanged |
| I27-15 / I27-18 Touch history transfer + truncation fallback, LastNormalTouchTime | c0fc087 B06-B2C-C1 (11-field TouchMark, I27-18), da141f3 W09 B06-B2C-C2 (W09State /18, W08Runtime /13 field-by-field guard release) | marks of the target Side in the W08 plan: normal count, latest time, weakByDepth OR, maxDepth max; truncated: count = max(mark count, relevant sources' same-Side count), time / weak / max also from the truncated sources; WeakByTouch = weakByTouchNow(count); CurrentTouchNo 0; completed TSS captured and cleared | c2_det.py / c2_mut.py / c2b_det.py (scratchpad); now B15 M1-M4 / M6 / M12 / M13 | b12adcd B07-R3A (projected source values); cfbe71b / 93506ed / f862f3e / 8bee144 touched the surrounding apply code (TSS clear moved to tssResetRaw, BS / Flip / Reclaim neighbours); history rule lines unchanged (diff da141f3..HEAD of touchHistoryTransferPlan = signature + 4 projected-source reads only) |
| I27-15 #1-#4 BreakSnapshot transfer and Phase after BS | 9ae99d8 (rules recorded in this ledger, "I27-15 BreakSnapshot transfer"), 93506ed W09 B08-A (W09State /25, W08Runtime /18) | one whole BS row: breakSeq max -> breakTime max -> old Core canonical order (coreId, generationId), Roots copied, no field mix; destination with a BS -> Broken / FlipWait over Waiting / Armed | b8a_det.py L5 / L6 / M1 / M2 (frozen B08); now B15 M7 / M8 / M8b / M10b | 0f01df2 B09 (+ GapBreak source), f862f3e B10 (+ Flip columns), 8bee144 B11 (consumed BS); selection predicate unchanged |
| B10 Q4 attempt / lastFlipConfirmSeq | f862f3e W09 B10 (W09State /27, W08Runtime /19); ledger "B10 Flip / FlipAttempt: Q1-Q6 fixed (user)" | flipAttemptCount = the selected BS source row (+1 for its Attempt of the bar); lastFlipConfirmSeq Merge = max over the same-Side sources (a Confirm of the bar = baseSeq); W08 guard releases exactly these 2 | b10_det.py F12 / F13 (+ real W08Touch /7 R2); now B15 M9 | none (B11 / B12 / B13 neighbour edits only) |
All four: introduced in a frozen batch, fixture-covered, current Production equal to the introduced rule -> PASS. No STOP.

sideLastNormalTouchTimes (corrected wording): not a direct public output, but a persistent history helper that feeds the
I27-18 truncation fallback and so can change a later Merge transfer result; not dead; covered by B15 M1 / M6 / M13.

Transfer-relevant fields (13; writer stage = post-commit apply after freshTransferApply unless noted):
| # | Field | Writer helper | Source | Destination | Reference rule | Fixtures |
|---|---|---|---|---|---|---|
| 1 | sideTouchCounts | touchHistoryTransferPlan (F0) / Apply | W08 Merge TouchMark plan rows of the Side; truncated: + every source count | Merge target Side | spec 12.2, I27-18 | M1 M2 M3 M6 M13 |
| 2 | sideCurrentTouchNos | touchHistoryTransferApply | - | target Side = 0 | spec 8.3 (no Episode on a Merge target) | M1 |
| 3 | sideLastNormalTouchTimes | same | latest retained normal mark; truncated: + truncated sources | target Side | I27-18 | M1 M6 M13 |
| 4 | sideWeakByTouchFlags | same | final count | target Side | spec 13.4 | M4 |
| 5 | sideWeakByDepthFlags | same | OR of retained marks; truncated: + truncated sources | target Side | spec 9.3 / 12.2, I27-18 | M4 M6 M13 |
| 6 | sideMaxDepthPcts | same | max of retained marks; truncated: + truncated sources | target Side | I27-18 | M4 M6 |
| 7 | sideFreshFlags | freshTransferPlan (F0) / Apply | AND over every source Core Side | target Side | spec 16, I27-15 §8 / §16 | M1 M5 M13 |
| 8 | coreZoneFreshFlags | same | AND over every source Core | target Core | spec 16, I27-15 §8 | M1 M5 |
| 9 | BreakSnapshot (14 fields + Root list) | bsTransferPlan (F0) / Apply | the selected source row | both target Sides | I27-15 #1 | M7 M8 M8b |
| 10 | sideFlipAttemptCounts | bsTransferPlan / Apply | the selected BS row (+1 Attempt of the bar) | target FlipWait Side | B10 Q4 | M9 |
| 11 | sideLastFlipConfirmSeqs | bsTransferPlan / Apply | max over same-Side sources | target Side | B10 Q4 | M9 |
| 12 | completed TouchStartSnapshot | touchHistoryTransferApply (capture / clear); live TSS never merged (Pending) | source TSS completed on the bar | none (cleared) | spec 11.1 / 11.4, I27-15 #4 | M11 M12 |
| 13 | coreDormantFlags | phaseArmedStageJFinalize (Stage J derivation, not transferred) | final target Side Phases | target Core | B14 | B14 D15 / G5 |
Phase / Armed / ArmedFromSeq / LastArmedRange and every SideView field: destination baseline + Stage J / sideViewProduce
(re-derivation, not transfer): M10 / M10b.

Fixtures (`b15_det.py`, scratchpad; real W08Touch /7 mergePlanBuild interpreted for the TouchMark plan, the harness W08
stub for the topology, W09State /33 + Main slice interpreted; expected from an independent Python Reference): M1 basic, M2
duplicate contact (one mark, survivor representative, no double count), M3 out-of-range mark not inherited, M4 Weak OR /
max / WeakByTouch from the count, M5-1 / M5-2 Fresh kept / no revival (ZoneFresh and SideFresh separately; alloc false not
read as semantic), M6 truncation fallback (no count / Weak / max drop, LastNormalTouchTime from the truncated source, no
Fresh revival), M7 single BS whole row, M8 / M8b competing BS (breakSeq, tie -> Core order), M9 attempt = selected row,
lastFlipConfirmSeq = max, M10 / M10b Phase / Armed (no Phase OR / max; baseline + Stage J; BS -> Broken / FlipWait), M11
ActiveTouch -> Pending (no transfer, TSS / TouchStartGrade fixed), M12 Reset -> READY Merge (completed TSS cleared, not
reused), M13 Case A-D: 16/16 PASS (one fixture error fixed before the result: the first M10 bar touched the Armed range).
Guard 8 fields (coreLastSeenTimes, corePruneRevisions, corePendingGenerationFlags, sideInverseAttemptCounts,
sideFvgDirectionMasks, sideFvgRootCounts, sideFvgFreshCounts, sideFvgStructuralStateMasks): static over the 13 Production
sources, NON_DEFAULT_REACHABLE_WRITER_COUNT = 0 (only the alloc push and the coreDeferredStateRaw default row); unchanged,
kept in the guard.
Regression: B08-B12 selected (L5 / L8 / F1 / M1, G11 / R1, F4 / F5 / F10, R1 / R2 / R8 / R12 / R14 / R15, I14 / I30), B13
P1-P12, B14 D1-D18 / D18b, D19 A-D / D2 / G, Default Guard G1-G5: PASS. R3-B1 contract PASS. random 0, 5k / 50k 0.
Production source delta 0 (Worker versions and Main pins unchanged); the B14 Main compile PASS stands.

W09_CARRY_MERGE_SIDE_STATE_TRANSFER = CLOSED.
W09_B15_MERGE_SIDE_TRANSFER = COMPLETE / FROZEN. I27 OPEN 0.

## W09 B16 Split / topology transfer: START GATE and Phase A audit (no code change)

START GATE: claude/w09-b07-redesign-v2, local = remote = 1ae698a, 0 / 0, clean; canonical SHA-256 f0ada2d8... (spec v2(5)) /
8f5373a4... (W09 bundle); HANDOFF_W08, ledger present; pins W08Core /19, W08Touch /7, W08Runtime /21, W09State /33; B15
COMPLETE / FROZEN, W09_CARRY_MERGE_SIDE_STATE_TRANSFER CLOSED. TOKEN START REVIEW: Main PASS, exact UNKNOWN, no class; audit
only (no UDT / tuple / forwarding / Main logic / Probe). TOKEN END REVIEW: delta 0, exact UNKNOWN.

Split canon: spec 12.3 (each child inherits only the history that actually contacted its price part; an uncontacted child
may be untouched; real touch price / time decide the owner; ActiveTouch -> PendingTopology), 11.4 (READY order: Pending
apply -> recluster -> history by real touch price / time -> new range vs close -> Waiting / Armed), 12.1 (identity: shared
origin Root and continuity <= M; a discontinuous move is a new generation), 13 (new generation only on its own conditions:
new independent category, Base Strong, reset distance, re-approach; resets both Sides' history), 16 (Fresh). W08 frozen:
Split = an old with >= 2 new edges, continuation child (coreId / generationId kept) / fresh child (new IDs); TouchMark Split
= marks whose contact meets the child Side EffectiveRange (no non-meeting copy, untouched allowed, one mark may go to several
children), truncated = the child has that Side and the source Side is truncated.

Physical fresh child vs semantic generation: Case 1. The W08 generationId of a fresh child is the identity generation of spec
12.1; spec 12.3 explicitly gives every child its contacted history, and the 13 reset (both Sides to 0) belongs to the 13
trigger only. Frozen B06 matches: history from the child's Split marks for continuation and fresh children alike; ZoneFresh
of a fresh child re-derived from its marks ("new generation re-starts it"), of a continuation child ANDed with the source.
The 13 trigger has no writer (corePendingGenerationFlags: no writer; W10), so 13-vs-12.3 precedence is not reachable now:
carried to W10, not a B16 I27.

Split writer inventory (introducing commit / current W09State /33 unless noted):
| Helper | Commit | Source -> destination | Continuation child | Fresh child | Fields |
|---|---|---|---|---|---|
| W08Touch splitPlanBuild / splitApplyPreflight / splitApplyCommit | W08 B12 (W08Touch /7) | source ring -> child ring | marks meeting the child Side range | same | TouchMark rows, child truncated flags |
| touchHistoryTransferPlan / Apply | da141f3 B06-B2C-C2 | Split marks of the child Side; truncated: + source | rebuilt from its marks | rebuilt from its marks | TouchCount, CurrentTouchNo 0, LastNormalTouchTime, WeakByTouch, WeakByDepth, MaxDepth; completed TSS clear |
| freshTransferPlan / Apply | 5e2063c B06-B2C-B0 | child marks + source Fresh | SideFresh from marks; ZoneFresh = both Sides AND source ZoneFresh | SideFresh from marks; ZoneFresh = both Sides | sideFreshFlags, coreZoneFreshFlags |
| bsTransferPlan / Apply | 93506ed B08-A (+0f01df2 B09, f862f3e B10, 8bee144 B11) | source BS -> child Side | per Side: winner range meets BS range | same | 14 BS fields, flipAttemptCount, lastFlipConfirmSeq, noArm |
| phaseArmedStageJFinalize step 1 / 2 | 1b57251 B06-B2B3-B (+ B08 BS baseline, B14 Dormant / transition) | final topology | baseline Waiting / Broken / FlipWait then Stage J; inherits the source same-bar transition (B14) | same; no transition inherited | Phase, Grade, ArmedFromSeq, LastArmedRange, Upcoming, coreDormantFlags |
| sideViewProduce / w09CurrentRootProduceRaw | B06 | winners | recomputed | recomputed | SideView derived, current Root lists |
| episodeApply role 2 / touchHistoryTransferApply TSS capture | 7d711b4 B07-R3B2 | completed TSS | cleared, never reused | not copied | TSS |

Field matrix (Split; persistent unless noted):
| Field | Continuation child | Fresh child | Untouched child | Mark meeting several children | Source truncated | Authority |
|---|---|---|---|---|---|---|
| TouchCount / LastNormalTouchTime / WeakByDepth / MaxDepth | its meeting normal marks (parent 3, 1 meeting, complete -> 1) | same | 0 / na / false / 0 | counted in each child | count = max(marks, source count); time / weak / max also from the source (no revival) | spec 12.3, I27-18 (B06) |
| WeakByTouch | weakByTouchNow(count) | same | false (count 0, not truncated) | - | from the fallback count | spec 13.4 |
| CurrentTouchNo / Upcoming | 0 / count + 1 (Stage J) | same | 0 / 1 | - | - | spec 8.3 |
| SideFresh | >= 1 meeting normal mark -> false; none + complete -> true; none + truncated -> source SideFresh | same | true when complete | false in each child | no inferred revival | spec 12.3 / 16, I27-15 §8 / §16 |
| ZoneFresh | both Sides fresh AND source ZoneFresh | both Sides fresh | - | - | - | spec 16, B06 |
| BreakSnapshot | per Side: child Side winner range meets the BS range -> whole row; else none | same | same | every meeting child Side | - | I27-15 #2 (see I27-B16-1) |
| flipAttemptCount | copied to every child Side taking the BS | same | 0 | - | - | B10 Q4 |
| lastFlipConfirmSeq | source value kept | baseSeq only for this bar's Confirm on the new Side meeting the BS, else unset | - | - | - | B10 Q4 (read only by bsTransferPlan) |
| sideInverseAttemptCounts | guarded, never written | same | same | - | - | B12 |
| Phase / Armed / ArmedFromSeq / LastArmedRange | baseline (Broken / FlipWait from a BS, else Waiting; unset / na) + Stage J; same-bar transition inherited | same; no transition | same | - | - | I27-15 #3, B14 |
| TSS | live: Pending (never split); completed: cleared | not copied | - | - | - | spec 11.1 / 11.4 |
| coreDormantFlags | Stage J derivation | same | same | - | - | B14 |
| coreLastSeenTimes / corePendingGenerationFlags / corePruneRevisions | guarded, no writer | same | same | - | - | Stage K / W10 |
| Grade / EffectiveRange / ReferencePrice / C / H / Density / BaseStrong / eligibility | recomputed (sideViewProduce, Stage J) | same | same | - | - | spec 4.3 / 6 / 7.2 |

PendingTopology: an ActiveTouch component is not applied (W08 frozen); on READY the plan applies, marks are redistributed,
Stage J evaluates the new range and the current close (spec 11.4 order kept).
Merge + Split mixed: W08 sets splitOfP only when mergeOfP == -1 for the same applied target (else the plan fails) and W09
phaseArmedTransferPreflight requires mergeOfP < 0 or splitOfP < 0 per p, so no destination gets two transfers; a
many-to-many component is a W08 plan failure (frozen topology, transaction class), never a double transfer.
Reachability: S1 untouched parent -> children, S2 / S3 contact only in the continuation / fresh child, S4 one mark meeting
both, S5 marks spread, S6 truncated source with a no-mark child, S7 WeakByDepth parent with the depth mark in one child, S9
Dormant parent (baseline + Stage J), S10 Split after READY: reachable and decided as above. S8 Broken / FlipWait parent:
reachable; see I27-B16-1. S11: unreachable as a double transfer (plan failure).
Guard 8 fields: unchanged (no Split path frees a Core; absorbed-only free).

I27-B16-1 (STOP): Split BreakSnapshot ownership splits a Broken / FlipWait pair.
1. Reachable case: a Broken Core (Support Broken, Resistance FlipWait, one logical BS on both Sides, B08 D2) splits into a
   continuation child with only a Support winner (W08Core builds single-sided physical candidates: sIdx or rIdx = -1) whose
   range meets the BS range, and a fresh child with only a Resistance winner meeting it (or no child Resistance winner at all).
2. Parent state: valid BS pair on both Sides (Broken / FlipWait), BS range fixed at the break.
3. Children: per Side, bsTransferPlan gives the BS to a child Side only when that Side's winner range meets the BS range.
4. Candidate results: R1 (current per-Side rule, I27-15 #2 read literally): child A Support Broken without the Resistance
   copy, child B Resistance FlipWait without the Support copy (or no child holds the Resistance copy -> that bar F0); from
   the next bar flipPlan finds a Broken Side whose opposite has no BS and returns false -> whole-pass F0 on every following
   bar (no state can change while the pass fails). R2 pair per child: a child inherits the BS on both Sides when either of
   its Sides meets the BS range (pair kept; a Side without a winner still carries Broken / FlipWait). R3 pair per child only
   when both Sides meet; otherwise none -> the source BS may reach no child -> F0 (I27-15 #2 fail-closed).
5. Why not unique: I27-15 #2 states the per "child Side" intersection; B08 D2 / B10 require the same BS on both Sides of a
   Core as one pair; spec 10.1 / 12.3 define no Split rule for a BreakSnapshot; the frozen texts conflict exactly in the
   single-sided / asymmetric child case and the results differ (permanent F0 vs a Broken / FlipWait child).
6. Fields: the 14 BreakSnapshot fields of both Sides, flipAttemptCount / lastFlipConfirmSeq / noArm (follow the BS row),
   Phase (Broken / FlipWait baseline), Broken / FlipWait price indexes.
I27 OPEN = 1 -> STOP_I27 (B16 Phase B not started).

### B16 I27-B16-1 resolution (user) and R4 Reference fixture (Production unchanged)

I27-B16-1 RESOLVED: decision R4 = BREAK_LIFECYCLE_CONTINUATION_OWNERSHIP (R1 / R2 / R3 not adopted). An unresolved
BreakSnapshot is one paired Break lifecycle of a physical Core (the same row on both Sides; Broken = BS.oldSide, opposite
FlipWait; movedAway / retestSeen updated together; cleared together on Flip / Reclaim). On Split only the continuation child
(old coreId / generationId, W08 frozen) inherits it, as the whole pair (every BS field, Roots, wasGapBreak, movedAway,
retestSeen), with Phase from BS.oldSide even when the continuation has a winner on one Side only; the child Side range vs BS
range intersection is no ownership condition (spec 10.1: criteria fixed at the Break, not moved by later re-zoning); fresh
children inherit no BS (14 fields default, no Broken / FlipWait from it), never a duplicate holder. flipAttemptCount and the
other BS-pair lifecycle fields follow the BS to the continuation; lastFlipConfirmSeq stays Side history (B10 / B15 frozen:
continuation keeps the source value, fresh child only by the existing same-bar Confirm writer). noArm / same-bar transition:
B13 / B14 frozen (continuation only inherits the transition). Not an F0 reason: a one-sided continuation, a continuation range
missing the BS, a fresh child meeting the BS. Still fail-closed: an inconsistent source pair (Support / Resistance rows differ,
oldSide contradiction) and the existing transaction invariants.
I27_B16_1_SUPERSEDES_I27_15_2_SPLIT_BS_OWNERSHIP: the Split part of I27-15 #2 (per child-Side intersection) is replaced by the
continuation atomic pair ownership; the Merge BS selection (I27-15 #1) is unchanged.
I27 OPEN = 0. B16 not COMPLETE.

R4 Reference fixture (`b16_r4.py`, scratchpad; Split bar = unit of bsTransferPlan -> phaseArmedIndexRelease ->
bsTransferApply -> Stage J on the post-commit Split state, Main order; next bars = txn8 from the R4 post-Split state; expected
from an independent R4 Reference), current Production W09State /33:
| Case | Result on /33 | First failing field |
|---|---|---|
| R4-0 control (continuation with both winners meeting the BS, fresh missing it) | PASS | - |
| R4-1 continuation Support-only / fresh Resistance-only | FAIL (expected) | continuation Resistance BreakSnapshot valid flag (the Resistance copy goes to the fresh child) |
| R4-2 continuation Resistance-only / fresh Support-only | FAIL (expected) | continuation Support BreakSnapshot valid flag |
| R4-3 continuation range misses the BS, fresh meets it | FAIL (expected) | continuation BS (both copies go to the fresh child) |
| R4-4 fresh children meeting the BS | FAIL (expected) | continuation BS (holder = the fresh child) |
| R4-9 GapBreak BS | FAIL (expected) | continuation Resistance BreakSnapshot valid flag |
| R4-10 inconsistent source pair (breakSeq 40 / 41) | FAIL (expected): the plan accepts it (no pair consistency check) | plan result true |
| R4-5 movedAway on the R4 continuation (one-sided) | PASS (pair synchronized) | - |
| R4-6 FlipAttempt | PASS (one Event, attempt +1, no F0) | - |
| R4-7 FlipConfirm | PASS (one Event, both copies cleared, nothing on the fresh Core) | - |
| R4-8 Reclaim | PASS (one Event, both copies cleared) | - |
| R4-X current-rule consequence (asymmetric result, next bars) | confirms: every later bar F0, mutation 0 | - |
The fixture detects the defect (R4-1 / R4-2 FAIL on /33). Production fix not started (STOP as instructed).

### B16 R4 Production repair (W09State /34, Main pin) - B16_R4_LOCAL_GATE PASS

START GATE: 5c89568, local = remote, 0 / 0, clean; W08Core /19, W08Touch /7, W08Runtime /21, W09State /33; canonical files,
ledger; B15 FROZEN; I27-B16-1 RESOLVED; I27 OPEN 0. TOKEN START REVIEW: Main PASS, exact UNKNOWN, no class; small predicate /
transfer change, one small helper, no UDT / tuple / forwarding / Main logic, Probe NO.

Change (W09State /34 only; W08 / Merge BS / Touch history / Fresh / TSS / B10 Flip / B13 / B14 / noArm / transition / lastFlipConfirmSeq unchanged):
- bsTransferPlan, Split rows: take = (class == TX_SPLIT_CONTINUATION) instead of the per-Side winner range x BS range
  intersection; the continuation child (W08 ownership class from phaseArmedTransferPreflight) receives the source BS row on
  both Sides (whole row, Roots, wasGapBreak, movedAway, retestSeen unchanged); TX_SPLIT_FRESH rows get kind 0 (no BS);
  flipAttemptCount follows the taken row (continuation only, existing writer). The existing check "a split source BS must
  reach a child" now means its continuation child (no continuation -> fail-closed, never dropped).
- bsPairOkRaw (new private helper): the persistent source BS of each Split source Core must be both invalid or both valid
  with an identical row (coreId, generationId, oldSide, range bottom / top ticks, breakSeq, breakTime, wasGapBreak,
  movedAway, retestSeen, Root list in order); else the plan returns false (pre-commit F0, mutation 0, Event 0).
- Main: W09State pin /33 -> /34 (W08Core /19, W08Touch /7, W08Runtime /21 unchanged).
Gates (scratchpad): `b16_r4.py` 13/13 on /34: R4-0 control, R4-1 / R4-2 one-sided continuation keeps the pair (fresh none,
no F0), R4-3 continuation missing the BS keeps it, R4-4 fresh children meeting it get none, R4-5 movedAway synchronized, R4-6
Attempt, R4-7 Confirm (one Event, pair cleared, no fresh duplicate), R4-8 Reclaim, R4-9 GapBreak BS, R4-10 inconsistent pair
-> plan false, mutation 0; R4-X (pre-fix consequence evidence) and R4-X_FIXED (R4-1 Split then Attempt and Confirm bars
commit, no F0). Mutations: MUT-BS-SIDE (per-Side intersection restored) -> R4-1 / 2 / 3 / 4 / 9 / X_FIXED FAIL;
MUT-BS-FRESH (fresh copy allowed) -> R4-0 / 1 / 2 / 3 / 4 / 9 FAIL; MUT-BS-PAIRCHECK (check removed) -> R4-10 FAIL: 3 / 3
detected.
Regression: B08 L5 / L6 / L7 / F1 / M1 / M2 PASS and F2 updated to R4 (old expectation "continuation range misses the BS ->
F0" = the superseded I27-15 #2 Split part; now the continuation keeps the pair, no F0); B09 G9 / G10 / G11 / R1; B10 F4 / F5 /
F10 / F12 / F13; B11 R1 / R2 / R8 / R11 / R12 / R14 / R15; B12 I14 / I17 / I18 / I30; B13 P1-P12; B14 D1-D18 / D18b, D19 A-D /
D2 / G, G1-G5; B15 M1-M13: PASS. R3-B1 contract PASS. Static: imports 0, bsPairOkRaw defined before bsTransferPlan, no
shadowing. random 0, 5k / 50k 0.
TOKEN END REVIEW: Before Main PASS; After TradingView not run; exact UNKNOWN; source delta W09State +~28 / -7 lines and one pin;
no high-cost structure; Probe none; no class.
B16_R4_LOCAL_GATE = PASS. I27-B16-1 = RESOLVED / IMPLEMENTED_LOCAL. B16 not COMPLETE: waiting for W09State /34 publish and the
Production Main compile.

## W09 B16 CLOSEOUT: W09_B16_SPLIT_TOPOLOGY_TRANSFER = COMPLETE / FROZEN

TradingView: W09State /34 publish PASS, Production Main compile PASS, compile error 0, runtime error 0, exact compiled tokens
UNKNOWN (no GREEN / YELLOW / RED class). Production HEAD 1d9e2db; this closeout changes the ledger only (Production delta 0).
Production: W08Core /19, W08Touch /7, W08Runtime /21 (unchanged), W09State /33 -> /34, Main pin W09State /34.
I27-B16-1: RESOLVED / IMPLEMENTED / VERIFIED, decision R4 = BREAK_LIFECYCLE_CONTINUATION_OWNERSHIP. I27 OPEN 0.

R4 frozen semantic:
1. An unresolved BreakSnapshot is one paired Break lifecycle of a physical Core, not per-Side state.
2. Split BS ownership: the continuation child only.
3. Fresh child: unresolved BS transfer NONE.
4. The continuation keeps the BS pair with a Support-only, Resistance-only or two-sided winner set.
5. The child Side EffectiveRange x BS range intersection is not used for BS ownership.
6. The current range after the Split never rewrites the BS range, Roots, breakSeq, breakTime or any snapshot payload.
7. BS.oldSide is the authority: oldSide Broken, opposite FlipWait.
8. The old Break lifecycle is never copied to a fresh child.
9. One parent unresolved Break is never duplicated to several children.
10. The continuation child is the only unresolved BS holder.
Source pair invariant: a Split source's persistent BS pair is both invalid, or both valid with an identical pair payload
(coreId, generationId, oldSide, rangeBottom, rangeTop, breakSeq, breakTime, wasGapBreak, movedAway, retestSeen, Root list =
every pair-authoritative BS field of the current store); otherwise F0 false, persistent mutation 0, Event 0.
I27_B16_1_SUPERSEDES_I27_15_2_SPLIT_BS_OWNERSHIP: only the Split part of I27-15 #2 (distribution by child Side range
intersection) is superseded; the Merge BS selection rule and every other B08 semantic are unchanged.
B08 F2: the old fixture verified that superseded Split rule ("child range misses the BS -> F0"); only its expectation was
updated to R4 (the continuation keeps the pair, no F0). This is the B16 supersession, not a change of B08 as a whole.

Evidence: R4-0 .. R4-10 and R4-X_FIXED PASS on /34; before the fix R4-1 / R4-2 / R4-3 / R4-4 / R4-9 / R4-10 failed (detection
power confirmed). Mutations 3 / 3 detected (MUT-BS-SIDE, MUT-BS-FRESH, MUT-BS-PAIRCHECK). Regression B08 / B09 / B10 / B11 /
B12 / B13 / B14 / B15 PASS; R3-B1 contract PASS; static PASS; random 0; 5k / 50k NOT RUN.
B16 is not redesigned; later Windows / Batches take R4 as a frozen input. Next: B17 Stage C / D / J Production.

## W09 B17 Stage C / D / J Production: START GATE and Phase A audit (no code change)

START GATE: claude/w09-b07-redesign-v2, local = remote = 35e8f8e, 0 / 0, clean; canonical SHA-256 f0ada2d8... / 8f5373a4...;
HANDOFF_W08, ledger; pins W08Core /19, W08Touch /7, W08Runtime /21, W09State /34; B16 COMPLETE / FROZEN, I27-B16-1 VERIFIED,
I27 OPEN 0. TOKEN START REVIEW: Main PASS, exact UNKNOWN, no class; audit only (Main direct reachable: one thin W08 / W09
callsite; no new callsite, tuple, forwarding or duplicate large call needed). TOKEN END REVIEW: delta 0, exact UNKNOWN.

Main call graph (updateConfirmed5m, accepted confirmed bar):
| Stage | Production path | Callsites | Mutation |
|---|---|---|---|
| A | cfg fingerprint / validateCfg, validateFeedMetadata, baseConfirmed, duplicate / past reject | 1 | cfg scalars only; a duplicate stops here |
| B | engine.eventLogicalCount := 0 (only after the duplicate reject) | 1 | Event pool length |
| D3 FVG facts | journalResetRaw, w03StageDFvgFactsRaw (W03 structural invalidation -> journal E1 rows) | 1 | journal scratch |
| E | W03EMsa (MA / Swing / Accum), W03ETimeFvg, W07Fvg.stageEFreshInversePrepare (Fresh, Inverse facts) | 1 each | journal / next-scalars scratch |
| F | w03StageFApplyAndCommitRaw (E1 apply, W07 inverse commit + confirm list), W06 seedPostApply, dependencyCarryInject | 1 | Root registry (W03 / W07 frozen commit) |
| G | W06Comp.recomputeAndMerge (W05 winners), cache / revision write-back | 1 | Candidate scratch / caches |
| C + D1-D4 + H + I + J | w08ProductionRaw: plan loop (touchStartPlanPreflight / Build, episodePlan, reclaimResolve, flipPlan, episodeOverlayBuild, W08Runtime.planPassWithActiveTouchOverlay, inverseCancelPlan; P0 / P1 max two plans) -> preflight chain (w09CurrentRootPreflightRaw, sideViewPreflight, inverseConfirmPreflight, phaseArmedTransferPreflight, freshTransferPlan, touchHistoryTransferPlan, bsTransferPlan, touchStartPostPlanPreflight, W08Runtime.preflightPass) -> commit (w09CurrentRootReleaseRaw, phaseArmedIndexRelease, W08Runtime.commitPass, w09CurrentRootProduceRaw, sideViewProduce, freshTransferApply, touchHistoryTransferApply, bsTransferApply, touchStartApply, gapBreakApply, flipApply, inverseDeferredResolve, inverseConfirmProject, D1 Event / mark loop, episodeApply, D3 Event loop) -> phaseArmedStageJFinalize | 1 | read-only until every F0 passed; then W08 + W09 state, Events |
| K / L | W08 scalars (nextCoreId / nextGenerationId / coreRangeRevision) and dependency carry on commit; lastBaseSeq / lastBaseCloseTime when Stage F succeeded | 1 | Main scalars |
W09State /34 exports: every orchestration export has exactly one Main callsite (sideViewPreflight / Produce,
phaseArmedTransferPreflight, phaseArmedIndexRelease, phaseArmedStageJFinalize, episodeOverlayBuild, touchStartPlanPreflight /
Build / PostPlanPreflight / Apply, freshTransferPlan / Apply, touchHistoryTransferPlan / Apply, episodePlan / Apply, flipPlan,
reclaimResolve, flipApply, bsTransferPlan / Apply, gapBreakApply, inverseConfirmPreflight, inverseCancelPlan,
inverseDeferredResolve, inverseConfirmProject; currentRootList* 1-3 in Main's current Root producer); the 0-callsite exports
(priceOrderUpdate / Range, canonicalSideSlots, weakByTouchNow, strongTouchEligible, gradeExact, armedDistanceMet,
nextArmedFromSeq, touchTargetSlots, gapBreakTargetSlots, d1TargetSlots, normalTouchMetExact, gapBreakMetExclusive) are internal
primitives reached through them. Reachability of B01-B16 semantics: A (Production reachable through w08ProductionRaw) for all;
C / D (fixture-only / dead): none.
Stage C authority: no physical snapshot copy; D1 / D2 / D3 read the persistent previous-confirmed W09 state (Phase, Armed index,
ArmedFromSeq, LastArmedRange, eligibility, SideView, current Root lists, TSS, BS), which Stages E-G never write (they write the
Root registry, journal and Candidate scratch only; the W09 Side fields change only after the W08 commit). Equivalent to the
canonical C-before-E order: the D facts that read the Root registry are order-independent by design (reclaimResolve uses the
journal E1 fact, B11 / B13; Inverse confirm = the W07 confirm list, B12); E1 receives every W03 structural invalidation, and D4
never suppresses one (FVG invalidation > Reclaim), so raw = D4-confirmed.
Stage D order: D1 touchStartPlanBuild (TouchStart / GapBreak exclusive), D2 episodePlan (Break > WeakDepth / Reset), D3 / D4
reclaimResolve -> flipPlan (effective Reclaim > FlipConfirm / Attempt, breakSeq < currentSeq) -> W08 plan; InverseConfirm
noArm in inverseConfirmProject; P0 / P1 inside the same plan loop (bar-start ActiveTouch never cancelled, Pending destinations
cancel related D1s). Matches B08-B13 frozen order.
Transaction: every W09 / W08 writer runs only inside the branch after the full preflight chain passed; an F0 bar writes no
Core / Touch / Pending / index / ID / revision / W08 scalar / Event / W09 state (the W03 / W07 Stage F Root commit and
lastBaseSeq of the accepted bar are the frozen W03 / W07 / W08 B15 contract, unchanged). Events: cleared only in Stage B,
appended only after commit from the final plan (no P0 / suppressed / pre-F0 Event).
Stage G / H / I: W08 topology frozen; W09 transfers run between commitPass and Stage J. Stage J: phaseArmedStageJFinalize is
the only final writer of Phase / Grade / Upcoming / Armed / Dormant / coreDormantFlags; nothing after it rewrites them. Old /
new boundary: D1 reads the Stage C (pre-commit) topology, Stage J the committed topology and the current close. B16 R4: Split
BS to the continuation only, consumed by the next bar's flipPlan.
Legacy: Main breakSnapshotRootNode* / touchStartSnapshotRoot* helpers form a closed chain with no external caller (dead
legacy, never executed); Main has no writer of sidePhases / sideGrades / sideArmedFromSeqs / sideTouchCounts / Weak / BS
fields. Reachable duplicate execution: none.
Missing wiring matrix: every Stage C / D / J responsibility is reachable on the Production path; missing 0; files to change
none; semantic change none; token risk none.
B17 Phase B proposal: verification only (no Production change expected): integrated-path conformance C1-C3, D1-D10, J1-J5,
F0-1, Duplicate, new Root / Strong on the existing scratch harness (txn8 mirrors w08ProductionRaw); most cases already exist
in B07-B16 fixtures and are collected, the rest (C2 same-bar first Armed, C3 same-bar new Root, Duplicate Feed) added.
I27: none (no reachable result-changing undefined wiring). I27 OPEN 0.

## W09 B17 Phase B: canonical stage order (I8) refactor - B17_CANONICAL_STAGE_ORDER_LOCAL PASS

START GATE: claude/w09-b07-redesign-v2 at 1784b6b, clean; pins W08Core /19, W08Touch /7, W08Runtime /21, W09State /34
(unchanged). Files changed: ZoneEngineV2_Rebuild.pine (Main) only; W09State / W08 Workers unchanged -> no version bump, no
/35. TOKEN START REVIEW: Main exact UNKNOWN (no class); planned: +2 thin Main functions (w09PlanViewRaw: the existing
TouchStartPlanView constructor moved, w09StageCDPlanRaw: the 5 existing planner calls moved), 0 new UDT / tuple / Worker
export, one 16-argument wrapper callsite added (P0 / P1) and 12 reference arguments forwarded once to w08ProductionRaw; every
W09State planner keeps exactly one callsite. TOKEN END REVIEW: source +48 / -26 lines (+2363 bytes); compiled exact UNKNOWN
(TradingView compile = the TV gate).

Physical order now (updateConfirmed5m): A validation / duplicate reject -> B eventLogicalCount 0 -> journal reset -> Stage D
FVG structural facts (w03StageDFvgFactsRaw, E1 rows) -> Stage C / D W09 plan (w09PlanViewRaw, w09StageCDPlanRaw d4 = true:
D1 touchStartPlanPreflight / Build, D2 episodePlan, D4 reclaimResolve on the bar-start Root states, D3 flipPlan; pass-local
scratch only) -> E (W03EMsa, W03ETimeFvg, W07 stageEFreshInversePrepare) -> F (w03StageFApplyAndCommitRaw, W06 seed, carry
inject) -> G (W06Comp.recomputeAndMerge) -> w08ProductionRaw: H / I (W08 plan with the Episode overlay; B12 P0 / P1 rebuild
through the same wrapper with d4 = false, tsx from the Stage C / D D1 candidate set, rcs kept from Stage D) -> preflights
(W09 + W08 F0) -> release / commit / producers / transfers / applies / Events -> Stage J (one callsite, last writer) -> K / L.
P0 / P1 rebuild inputs: the W08 / W09 persistent state read by the planners (core registry Side / TSS / BS / ring / Armed
index / phase sets) has no writer in Stage E / F / G (grep: W03 / W07 / W05 Workers 0 references, W06 receives sidePhases /
core arrays read-only, Main Stage E / F helpers 0 writes); journal E1 rows are appended only by w03StageDFvgFactsRaw. So
the rebuild is a function of the Stage C state + tsx, never of the new topology.

Finding B17-F1 (correction of the Phase A note "D facts order-independent"): reclaimResolve's keep test (another BS Root
live and ROOT_ACTIVE) read the post-Stage-F Root states in the pre-B17 order. Case: BS Roots {r1 invalidated by this bar's
Stage D FVG fact, r2 ACTIVE at bar start and retired / made non-active by Stage E2-E4 of the same bar}: pre-B17 suppressed the
Reclaim (r2 gone), canonical I8 (D4 in Stage D, before E4) keeps it -> EV_RECLAIM. Uniquely decided by I8 + B13 (D4 in Stage
D), so no I27; the B17 order implements it (fixture O8). Every other fixture: before / after identical.

Finding B17-F2 (reported, not changed): the Stage F Root commit (W03 / W07 frozen) and lastBaseSeq / lastBaseCloseTime are
committed when stageFOk even if the later W08 / W09 F0 fails; a W08 F0 does not roll the Root commit back (Root changes of
the bar stay, the bar is not re-processed, W08 / W09 state and Events of the bar stay 0). Making Root + W08 / W09 one
transaction would be a separate design change (W03 / W07 / W08 B15 contracts), out of B17 scope.

Inverse: InverseConfirm facts are produced by W07 in Stage E / F (frozen W07) and consumed by W09 after Stage G (P0 / P1,
inverseConfirmPreflight / Project); unchanged.

Evidence (scratchpad harness, Main w09StageCDPlanRaw interpreted from the source, Stage E / F stub between C / D and W08):
O1 / O2 / O13 static order PASS; O3 Stage C / D no persistent mutation PASS; O4-O12, O14 PASS (B17_FAIL[NEW] = 0 of 14).
Order mutants 3 / 3 detected: MUT-ORDER-LATE-D1 (O4 / O5 / O6 / O8), MUT-ORDER-NEW-RANGE (O5 / O6), MUT-ORDER-NEW-GRADE (O7);
source mutant (Stage C / D call moved after Stage G) caught by O1. Before / after (B17OLD mirror vs Production order): diff
only O8 (B17-F1). Regression on the Production order, each suite identical to the pre-B17 order: B08 16, B09 16, B10 14, B11
14, B12 25 (P0 / P1), B13 13, B14 17 + D19, B15 16, B16 R4 13 - all PASS; B14 W08Runtime guard PASS. Legacy B06 / B07-era
harnesses (b0 / c2 / c2b order, b7_det, r3b2_det, b3b_stagej) already did not run on the pre-B17 Main (superseded), not used.
random 0; 5k / 50k / 200k NOT RUN.
Status: B17_CANONICAL_STAGE_ORDER_LOCAL PASS. B17 not COMPLETE: LOCAL PASS / TV GATE WAITING (Main compile / publish by the
user). Next: STOP (no B18).

## W09 B17 F2 focused audit (Stage L lastBaseSeq / lastBaseCloseTime / committed) - B17_F2_AUDIT_PASS

Scope: Stage L only (Stage F Root commit out of scope, never rolled back). HEAD 6e36942, Main ZoneEngineV2_Rebuild.pine.
Actual code (updateConfirmed5m): Stage A duplicate / past reject (baseSeq <= lastBaseSeq or baseCloseTime <=
lastBaseCloseTime, first bar exempt) -> B eventLogicalCount 0 -> journal reset -> D FVG facts -> C / D W09 plan -> E -> stageFOk
= w03StageFApplyAndCommitRaw (true only when W03F0.preflight and W03Apply succeeded; the source cursors / time-HL / accum
scalars commit inside) -> if stageFOk: W06 seedPostApply, carry inject, W05 / W06 Stage G, then bool w08Committed =
w08ProductionRaw(...) -> if stageFOk: lastBaseSeq := feed.baseSeq, lastBaseCloseTime := feed.baseCloseTime, committed := true
-> return committed. w08ProductionRaw returns pr.committed (false when tsOk or any W09 / W08 preflight fails: commitPass not
called; W08 scalars and carry merge only under pr.committed). w08Committed is not read by the lastBase / committed condition.
Authority: canonical D07 / D08 (unconfirmed / duplicate / past Feed: no commit, false, previous Events kept; commit -> true),
HANDOFF_W01 s9 (reject -> false with Event / Base state unchanged, Stage L commit -> true), HANDOFF_W03 (F -> L), HANDOFF_W08
s7 (W08 callsite after Stage G and before the lastBase commit; duplicate / past Feed never reaches the W08 pass; W06 failure
keeps the carry for a later bar), W08DependencyCarryHarness F CARRY_RETRY (retry on a later build, not a re-fed bar), I27-13R
(every W08 pass is a fresh rebuild). Retry semantic = B: the F0 bar is committed through Stage F and lastBase advances; the
same Feed is a duplicate (no Stage E / F re-run, no Root double apply, no W08 retry of that bar); the next bar's W08 pass
re-plans from the current Root / Candidate state, so the F0 bar's Root changes are reconciled there; the F0 bar's own W08 /
W09 facts and Events stay 0 (B13 I27-B13-2 whole-pass F0). Option A (lastBase gated on w08Committed) contradicts D07 / W01
(false after a Root mutation) and double-applies Stage F on a re-fed bar (counterfactual run: rootLog [10, 10]).
Evidence (scratchpad f2_det.py, Production updateConfirmed5m interpreted, stubbed callees, real W08Runtime carry helpers):
F2-A / F2-B / F2-C / F2-D / F2-E / F2-S PASS (F2_FAIL = 0 of 6); counterfactual option A fails F2-B / F2-C / F2-S.
Judgement: Case 1 (consistent with the frozen retry contract and canonical Stage L); Production change none; I27 none.
B17 status unchanged: LOCAL PASS (provisional) / TV GATE WAITING. STOP.

## W09 B17 CLOSEOUT: W09_B17_STAGE_C_D_J_PRODUCTION COMPLETE / FROZEN

START: claude/w09-b07-redesign-v2, local = remote = f321860 (B17 Production implementation 6e36942, F2 audit f321860),
0 / 0, clean; pins W08Core /19, W08Touch /7, W08Runtime /21, W09State /34; I27 OPEN 0. CLOSEOUT changes this ledger only.

Frozen: canonical physical stage order (updateConfirmed5m): A validation / duplicate reject -> B eventLogicalCount 0 -> D
FVG fact detection (journal reset, w03StageDFvgFactsRaw) -> C / D W09 read-only plan (w09PlanViewRaw, w09StageCDPlanRaw) ->
E -> F (Root commit) -> G (W06) -> H / I W08 transaction (w08ProductionRaw plan, B12 P0 / P1, preflights, commit) -> W09
transfer / apply / Event -> J (phaseArmedStageJFinalize) -> K / L. Canonical meaning C/D -> E/F -> G/H/I -> J holds. Later
Batches take this order as a frozen input.
Stage C / D contract: persistent mutation 0; the bar-start persistent state (Phase, Armed, ActiveTouch, TSS, BS) is the
authority for D1 / D2 / D3 / D4, fixed into scratch; a current-bar new Root / range / Grade is never applied retroactively
to the current Touch, TouchStartSnapshot or TouchStart Grade.
P0 / P1 (B12 frozen): InverseConfirm + same-bar D1 candidate -> P0 -> related D1 cancel -> P1 when needed, at most two plans;
the Stage C / D D1 candidate set is the authority; no D1 recompute from the new topology.
Stage J: phaseArmedStageJFinalize is the only final writer, once per committed bar: Phase, Grade, Upcoming, Armed,
armedFromSeq, lastArmedRange, Dormant, coreDormantFlags for the next bar; later rewrite 0.
B17-F1 FINAL: the pre-B17 Production read the post-Stage-F Root states in reclaimResolve (BS Root r1 invalidated by this
bar's Stage D FVG fact, r2 ACTIVE at bar start and retired in E2-E4 of the same bar: old order suppressed the Reclaim). The
canonical order evaluates D4 on the bar-start state -> Reclaim -> EV_RECLAIM. A correction of a canonical stage-order
violation, not an unintended semantic change; unique by canonical I8; I27 none.
B17-F2 FINAL: the Stage F Root commit is not rolled back by a later W08 F0 (correct). W08 F0: W08 / W09 state mutation 0, W08
Event 0, no W08 scalar commit, no carry merge; the Stage F Root mutation is already committed. lastBaseSeq /
lastBaseCloseTime / committed advance on stageFOk (authority); w08Committed is not a lastBase condition. Retry: an F0 bar
returns true; the same Feed is a duplicate / past reject (false, no Stage F re-run, no Root double apply); the retry is the
next Base bar's fresh W08 rebuild (I27-13R, B15 dependency retry contract). Mutation stageFOk AND w08Committed: false on an F0
bar after a Root mutation and a Stage F re-run (Root double apply) on the re-fed bar -> rejected; stageFOk authority kept.
Local evidence: O1-O14 14 / 14 PASS; order mutations 3 / 3 detected (MUT-ORDER-LATE-D1, MUT-ORDER-NEW-RANGE,
MUT-ORDER-NEW-GRADE). Regression B08 / B09 / B10 / B11 / B12 / B13 / B14 / B15 / B16 PASS, W08Runtime guard PASS; random 0;
5k / 50k / 200k NOT RUN. F2 focused audit: F2-A / F2-B / F2-C / F2-D / F2-E / F2-S PASS, F2_FAIL 0 of 6, B17_F2_AUDIT_PASS.
TradingView Final Gate (user): Production Main compile PASS, compile error 0, runtime error 0, exact compiled token
UNKNOWN (no GREEN / YELLOW / RED class); Worker change 0, Worker republish not needed.
Production diff: B17 changed Main only; W08Core / W08Touch / W08Runtime / W09State /34 unchanged; CLOSEOUT Production change 0.
I27: B17 OPEN 0 (F1 unique by canonical, F2 consistent with the frozen retry contract; no new I27).
Status: W09_B17_STAGE_C_D_J_PRODUCTION COMPLETE / FROZEN. Next: B18 state price-index vs Reference (not started).

## W09 B18 Phase A: State Price-Index vs naive full-scan Reference - W09_B18_STATE_PRICE_INDEX_REFERENCE_PHASE_A_PASS

START GATE: claude/w09-b07-redesign-v2, local = remote = beb3260, 0 / 0, clean; pins W08Core /19, W08Touch /7, W08Runtime /21,
W09State /34; B17 COMPLETE / FROZEN (Main TV compile PASS); I27 OPEN 0. TOKEN START REVIEW: Main compile PASS, exact UNKNOWN;
Phase A = audit + scratch Reference only. Production diff 0, version / pin change 0, random 0, 5k / 50k / 200k not run.

Production extraction inventory (W09State /34 + Main, repo names):
| State | Production extraction | Index / set (owner, key, order, bound) | Maintenance |
|---|---|---|---|
| Touch / GapBreak (D1) | touchStartPlanPreflight / Build -> d1TargetSlots = touchTargetSlots + gapBreakTargetSlots (priceOrderRange) -> Armed / eligible / armedFromSeq <= seq filter -> canonicalSideSlots | armedBottom/TopOrderSideSlots + positions (W09State, key round(sideLastArmedRange{Bottom,Top} / mintick), ASC, tie slot ASC); Touch: bottom (-inf, high], top [low, +inf), line bottom [low - tol, high + tol] with bottom == top; GapBreak: Support bottom [max(high + 1, close + bb), +inf), Resistance top (-inf, min(low - 1, close - bb)]; all inclusive | insert: Stage J arm (key set before insert); remove: Stage J (not q / key change), phaseArmedIndexRelease (applied continuation / freed Core before commit), TouchStart apply, Break / GapBreak (BS pair) |
| ActiveTouch / Local Break / Episode Reset | episodePlan: phaseActiveTouchSideSlots + this bar's TouchStart rows -> canonicalSideSlots (no price filter) | Phase set (swap-pop, sidePhaseSetPositions) | phaseMoveRaw (detach + add) |
| Flip / Reclaim | flipPlan: phaseBrokenSideSlots -> paired FlipWait Side -> canonicalSideSlots (no price filter); predicate on the fixed BS payload; reclaimResolve D4 | Broken / FlipWait Phase sets; broken/flipBottom/TopOrderSideSlots (key round(bsRange / mintick)) maintained by bsIndexRaw, not consumed by any extraction | Stage J BS attach, Break / GapBreak, bsPairEndRaw (FlipConfirm / Reclaim), release of Merge / Split old Cores |
| Waiting Reset / reArm, Dormant enter / recovery, Grade / Upcoming | phaseArmedStageJFinalize: full scan of every live Core x 2 Sides (Waiting / Armed / Dormant) | none (dormantBottom/TopPositions declared in the view, never written) | - |
| Inverse | W07 inverseFacts: every Root of inverseWaitFvgRootSlots (no price filter, W07 owner); W09 consumes the confirm list | W07 InverseWait set | W07 (frozen) |
Canonical order: canonicalSideSlots (coreId ASC, generationId ASC, Support, Resistance; key coreId * 2 + side), used by every
extraction before evaluation / Events. W10_CARRY: Generation re-approach / PendingGeneration (corePendingGenerationFlags is
read-only input to Stage J), not B18 scope.

Reference (scratch b18_det.py): every live Core x (Support, Resistance) in canonical order, predicates computed directly from
Phase, LastArmedRange / EffectiveRange, TSS, BS payload, high / low / close and cfg (no priceOrderRange / target helper /
Phase set / canonicalSideSlots); index audit = each Phase set and each price index against the full scan (membership,
duplicates, positions, order by the current key). Level 1 target parity + Level 2 result parity (Events type / Core / Side /
order, final Phase per Side) on the Production path (txn8, Main w09StageCDPlanRaw interpreted).
Fixtures P1-P24 + P25 (Armed range change re-key): 25 / 25 PASS. TOUCH / GAP / D1 / ACTIVE / BREAK / RESET / FLIP / RECLAIM /
INVERSE / DORMANT MISSING 0 and EXTRA 0; ORDER_DRIFT 0; RESULT_DRIFT 0; INDEX_STALE 0, INDEX_MISSING 0, INDEX_ORDER 0.
Coverage (bars with a non-empty Reference set): Touch 24, GapBreak 11, D1 32, Active 9, Break candidates 32, FlipWait 10,
Broken 10. Harness-only corrections during the run (class A): Stage B event clear between bars, the SideView current Root
list of fixture Sides, the Reference BS pair over an opposite same-bar Reset (B08 rule), the P10 static pattern.
Mutations: M1 bound off-by-one, M2 inclusive -> exclusive, M3 Support reArm comparison reversed, M4 Resistance reversed, M5
Phase-set remove deleted, M6 Phase-set insert deleted, M7 canonical sort by slot, M8 stale range key (Armed index inserted
with the pre-change LastArmedRange), M9 Split fresh BS inherit, M10 Dormant equality exclusive: 10 / 10 detected,
MUTATION_UNDETECTED 0. Note: the first M8 form (drop the Stage J key-change re-key condition) is an equivalent mutant: every
applied continuation / freed Core leaves the Armed index in phaseArmedIndexRelease before commit and EffectiveRange changes
only for applied Cores, so a member with a changed key is unreachable at Stage J.
Findings (no result drift, recorded for the Phase B decision): B18-F1 Stage J evaluates Reset / reArm and Dormant enter /
recovery by a full live-Core scan every bar (I16 rule 1 / table rows "Reset / 再Armed", "Dormant復帰" ask for state-set +
price extraction); results are exact (full scan is complete), the gap is the extraction shape / per-bar cost. B18-F2 the
Broken / FlipWait BS price indexes are maintained but unused (Flip / Reclaim read the whole Broken set, complete), and the
Dormant price positions are declared but never written. Neither is a predicate / ordering defect; I27 none (I16 is explicit,
nothing undefined). Production drift: none. I27 OPEN 0.
TOKEN END REVIEW: Production delta 0; exact UNKNOWN. Status: W09_B18_STATE_PRICE_INDEX_REFERENCE_PHASE_A_PASS (B18 not
COMPLETE / FROZEN). STOP.

## W09 B18 Phase B: I11 / I16 index extraction (B18-F1 / B18-F2) - W09_B18_STATE_PRICE_INDEX_REFERENCE_LOCAL PASS

START GATE: claude/w09-b07-redesign-v2, local = remote = fecdcec, 0 / 0, clean; pins W08Core /19, W08Touch /7, W08Runtime /21,
W09State /34; B17 COMPLETE / FROZEN; I27 OPEN 0. TOKEN START REVIEW: Main compile PASS, exact UNKNOWN; W09State-centred, Main
thin wiring only, no new UDT / tuple / approximate index / truncation / per-bar full sort.
Files: ZoneEngineV2_W09State_Worker.pine (/35), ZoneEngineV2_Rebuild.pine (pin W09State /35; W08Core /19, W08Touch /7,
W08Runtime /21 unchanged).

B18-B1 (B18_F2_BS_DORMANT_REQUIRED_INDEX, BS part): new export bsTargetSlots - Flip / Reclaim targets from the existing Broken
BreakSnapshot price indexes (keys = fixed BS range ticks, never the EffectiveRange): Support sb when bottom >= close + reset
(movedAway) or bottom >= high + 1 (full exit) or top <= close - breakBuffer (Reclaim); Resistance sb when top <= close -
reset or top <= low - 1 or bottom >= close + breakBuffer; both when bottom <= high and top >= low (contact) - inclusive tick
bounds, a superset of every flipPlan row. Main w09StageCDPlanRaw calls it once and passes the target list to reclaimResolve
and flipPlan in place of the Broken set; flipPlan / reclaimResolve bodies (B10 / B11 / B13 predicates, canonicalSideSlots)
unchanged. Inverse: W07 inverseFacts evaluates the whole InverseWait set, no W07 threshold index exists ->
W07_I11_INVERSE_THRESHOLD_INDEX_CARRY to the W11 / W12 final conformance (W07 not changed).
B18-B2 (B18_F1_STAGEJ_PRICE_EVENT_INDEX): Stage J no longer scans every live Core. phaseArmedStageJFinalize iterates the
canonical target list of stageJTargetsRaw = A every Side of an applied destination (classes != TX_NONE), B the bar's
transition Sides (Episode rows, Flip rows both Sides, noArm, TouchStart plan Sides, GapBreak rows), C-E the price targets of
stageJPriceTargetsRaw: Waiting index (keys = EffectiveRange) Support Reset top <= close - reset, Resistance Reset bottom >=
close + reset, Dormant entry bottom >= close + dormant + 1 or top <= close - dormant - 1 (strict); Armed index (keys =
LastArmedRange = the EffectiveRange of an indexed Armed Side) Armed distance lost (B06-B2B3 option b: Support top >= close -
reset + 1, Resistance bottom <= close + reset - 1) and Dormant entry; Dormant recovery index (I11 #12, keys = EffectiveRange,
Main storage dormantRecovery* now used) bottom <= close + dormant and top >= close - dormant (inclusive). Union -> dedupe ->
canonical (coreId, Support, Resistance). The per-Side finalize (B14 / B10 / B06 predicates, Grade / Upcoming / Armed /
Dormant / noArm order) is unchanged; coreDormantFlags for every target Core; relCore / transition projection are pass-local
maps (no per-bar array over every Core). Key choice: each index keys the range edge tick; the cfg distance (reset / dormant) is
added in the query, so an integer-tick threshold (edge + distance) is compared exactly and a cfg change needs no re-key.
Maintenance: phaseMoveRaw drops a Side leaving Waiting / Dormant from that index (every Phase change goes through it);
phaseArmedIndexRelease drops the Waiting / Dormant Sides of applied old Cores and freed Cores before commit (with Armed / BS);
Stage J inserts every target on its final Phase and EffectiveRange; breakOppositeOkRaw accepts a Dormant opposite with a
consistent Dormant index membership (was: no Dormant recovery position). Main: ZoneEngine waiting* order / positions storage,
the PhaseArmedTransferView gets the 6 index arrays, Stage J gets the TouchStart plan Sides and gbi.

Evidence (scratchpad b18_det.py, Production interpreted, Reference = naive full scan): P1-P42 + S1-S4 static 43 / 43 PASS;
TOUCH / GAP / D1 / ACTIVE / BREAK / RESET / FLIP / RECLAIM / INVERSE / DORMANT MISSING 0, EXTRA 0; ORDER_DRIFT 0; RESULT_DRIFT
0; INDEX_STALE 0, INDEX_MISSING 0, INDEX_ORDER 0 (Waiting / Dormant / Armed / Broken / FlipWait indexes and Phase sets).
No-semantic-change gate: the same fixtures on /34 + the pre-B18 Main vs /35: 106 bars compared, Events, Phase, history,
BreakSnapshot rows, coreDormantFlags and Phase sets identical (DIFF 0). Mutations M1-M20 (+ M17 Main form, caught by S2):
21 / 21 detected, MUTATION_UNDETECTED 0. F0 (P24): Phase, every index and positions, Events unchanged. Regression on /35:
B08 16, B09 16, B10 14, B11 14, B12 25, B13 13, B14 17 + D19, B15 16, B16 R4 13, B17 O1-O14 14 all PASS; W08Runtime guard PASS.
Static: Stage J O(N) scan / allocation 0; Flip / Reclaim Broken / FlipWait set scan 0; no array.sort in W09State
(sort_indices only on candidate / target lists). Harness-only corrections (class A): fixture Upcoming = TouchCount + 1, the
fresh materialization of a reused slot (Stage J insert emulated), the P35 expectation. random 0; 5k / 50k / 200k not run.
Observation (not changed, outside the B18 state-extraction scope): touchHistoryTransferPlan / bsTransferPlan /
touchStartPostPlanPreflight still allocate O(Core count) validation scratch per bar.
TOKEN END REVIEW: W09State /35 +256 / -25 lines, Main +23 / -? (thin wiring, storage); exact UNKNOWN, no class.
Status: B18_F1_STAGEJ_PRICE_EVENT_INDEX IMPLEMENTED_LOCAL; B18_F2_BS_DORMANT_REQUIRED_INDEX IMPLEMENTED_LOCAL;
W09_B18_STATE_PRICE_INDEX_REFERENCE_LOCAL PASS. B18 not COMPLETE: LOCAL PASS / TV GATE WAITING (W09State /35 publish, Main
compile by the user). I27 OPEN 0. STOP.

## W09 B18-B4: Inverse threshold index completion (W07 /12) - W09_B18_STATE_PRICE_INDEX_REFERENCE_LOCAL PASS

START GATE: claude/w09-b07-redesign-v2, local = remote = 157e7e7, 0 / 0, clean; W07Fvg Production /11 (repo source = /11,
Main import /11); Inverse owner W07 (inverseFacts via inverseStageEPrepare <- stageEFreshInversePrepare, Main Stage E callsite
1; wait entry / pending apply via inverseStageFCommitWithConfirm, Main Stage F callsite 1); InverseWait set
inverseWaitFvgRootSlots (Main engine, W07-maintained); the W03 FVG NativeRange interval orders fvgNativeBottom /
TopOrderRootSlots (W03-owned, every live FVG Root; an invalidated Root stays in them; no FVG Root free / retire path - W03
retires TimeHL only, rootFreeSlots has no writer); progress owner W07 (rootFvgInverseProgresses); W09State /35, Main pin /35.
B18_INDEX_KEY_REPRESENTATION = EDGE_KEY_PLUS_QUERY_OFFSET_ACCEPTED_EQUIVALENT (Waiting / Armed / Dormant / BS indexes: the
range edge tick is the key, reset / dormant / buffer offsets are applied in the query; not an I27).
Frozen W07 predicate (inverseEvalOneRaw, ticks round(price / mintick), reset = round(touchResetDistance / mintick)):
| Progress | Reads | Fact | Inclusive |
|---|---|---|---|
| 1 WAIT_MOVED_AWAY | direction, NativeRange edge, close | Bullish close <= bottom - reset, Bearish close >= top + reset -> 2 | yes |
| 2 MOVED_AWAY | NativeRange, high / low, close | low <= top and high >= bottom -> 4 when the close confirms (Bullish close <= bottom, Bearish close >= top), else 3 | yes |
| 3 RETOUCHED | direction, NativeRange edge, close | confirm (as above) -> 4 | yes |
| 4 ACTIVE | - | InverseActive set, ROOT_INVERSE_ACTIVE, confirm list row (pending order) | - |
Output: pending rows (slot, rootId, new progress) in ascending wait position, applied in Stage F (progress write / ACTIVE move),
the Candidate seed STATE | FVG (| BROAD), FVG state / new-Side eligibility dirty, the confirm list (pending order).
Implementation (W07Fvg /12, Production): invWaitBull (WAIT_MOVED_AWAY Bullish, key bottom), invWaitBear (key top),
invRetouchBull (RETOUCHED Bullish, key bottom), invRetouchBear (key top), one reverse position array rootInvIdxPositions
(Main aux storage, W07-maintained; order (key tick, rootId), freshIndexInsertRaw / freshIndexDetachRaw). MOVED_AWAY reuses the
W03 FVG NativeRange orders (no duplicate interval index) with the InverseWait / MOVED_AWAY filter. inverseFacts candidates:
Bullish WAIT bottom >= close + reset, Bearish WAIT top <= close - reset, Bullish RETOUCHED bottom >= close, Bearish RETOUCHED
top <= close, contact bottom <= high and top >= low (W03 orders) - each exactly its predicate; then the frozen wait-set order
(ascending wait position = the former loop order), the unchanged per-Root checks plus source-index / progress / direction
agreement, and inverseEvalOneRaw. Maintenance: inverseWaitEnterApply inserts into the WAIT index (dry run first);
inversePendingApply moves the Root between indexes (1 -> 2 out of WAIT, 2 -> 3 into RETOUCHED, 2 / 3 -> 4 out); a failed move
is runtime.error W07_INVERSE_APPLY_INVARIANT. Count invariant: the four index sizes never exceed the wait set.
Main: W02Aux invWaitBull / invWaitBear / invRetouchBull / invRetouchBear RootSlots, rootInvIdxPositions; the two W07 calls
get the index arrays (Stage E also the W03 FVG NativeRange orders / positions, Stage F also the native ticks); import W07 /12.
Evidence (scratchpad b18_inv.py: W07 /12 and /11 interpreted on a synthetic FVG Root store, Reference = every InverseWait Root
in wait order with the predicate written independently; Level 1 = the Roots actually evaluated by Production): P43-P57 + S5
16 / 16 PASS; INVERSE_MISSING 0, INVERSE_EXTRA 0, INVERSE_ORDER_DRIFT 0, INVERSE_RESULT_DRIFT 0 (/12 vs Reference and vs /11:
pending rows, confirm list, Root states, progress, wait / active sets, positions, seeds identical), INVERSE_INDEX_STALE 0,
INVERSE_INDEX_MISSING 0, INVERSE_INDEX_DUPLICATE 0; coverage: 23 moved-away, 12 retouched, 10 confirm facts. P53 / P54: no
FVG Root free / retire path exists; an InverseActive Root or a slot with another W07 identity cannot (re-)enter and leaves
no index entry. B18 P1-P42 + S1-S4 43 / 43 PASS (P10 now checks the step parity; extraction in b18_inv). Mutations M21-M30
10 / 10 detected; M1-M20 (+ M17 Main) re-run 21 / 21 detected; MUTATION_UNDETECTED 0. Static: inverseFacts has no
InverseWait scan, no array.sort in W07 (sort_indices on the candidate list only). Regression B08-B17 PASS (B10 Flip /
Reclaim, B12 InverseConfirm, B13 priority / noArm, B14 Stage J + D19, B15 Merge, B16 R4, B17 order), W08Runtime guard PASS.
random 0; 5k / 50k / 200k not run.
W10_CARRY_I17_REUSABLE_SCRATCH_3PATHS = OPEN: W09State touchHistoryTransferPlan (seen, 2 x Core count), bsTransferPlan (rel,
2 x Core count, plus its loop over every Side), touchStartPostPlanPreflight (busy / roles, Core count, when any row exists)
allocate per-bar scratch sized by the Core count; I17 asks for Engine-owned reusable scratch with logical-length reuse. Not
changed in B18-B4; must be CLOSED by W10 or the Final Integration and re-audited before the final canonical diff 0 decision.
W07_I11_INVERSE_THRESHOLD_INDEX_CARRY = CLOSED. B18_INVERSE_THRESHOLD_INDEX = IMPLEMENTED_LOCAL.
TOKEN END REVIEW: W07Fvg /12 (+ index helpers, extraction), Main +storage / call args; W09State /35 unchanged (no /36);
exact UNKNOWN, no class. Status: W09_B18_STATE_PRICE_INDEX_REFERENCE_LOCAL PASS; B18 not COMPLETE: LOCAL PASS / TV GATE
WAITING (W07Fvg /12, W09State /35 publish, Main compile). I27 OPEN 0. STOP.

## W09 B18 TV Gate fix: B18_TV_GATE_W07_12_CE10150_IDENTIFIER_FIX

TV Gate: W07Fvg /12 compile FAIL, line 506 CE10150 ("to" cannot be used as a variable or function name). Fix: invIdxMoveRaw
local `to` -> `toOrder` (declaration + 2 references, 3 lines); semantic diff 0; W07Fvg stays /12 (never published), Main
import /12, W09State /35. Static reserved-identifier check over the B18 diffs (W07 since 157e7e7, Main / W09State since
fecdcec, code only): W07 0, Main 0; W09State /35 still declares `array<int> to` in wdIndexRaw (B18 Phase B) - the same
CE10150 will occur at its TV Gate; not changed here (this rally forbids W09State changes), reported for a decision.
Local gate: b18_inv P43-P57 + S5 16 / 16 (Inverse metrics all 0), b18_det P1-P42 + S1-S4 43 / 43, M21-M30 10 / 10 detected,
B12 25 / 25, B13 13 / 13. random 0; 5k / 50k / 200k not run. I27 OPEN 0.

## W09 B18 TV Gate fix: B18_TV_GATE_W09STATE_35_CE10150_IDENTIFIER_FIX

W09State /35 wdIndexRaw: local `to` -> `toOrder` (declaration + 2 references, 2 lines); semantic diff 0; W09State /35
unchanged (never published), Main pin /35, W07Fvg /12, Main / W07 / W08 unchanged. Static reserved-identifier check over the
B18 diffs (code only, comments / strings excluded; to / from / Pine v6 keywords and type names): W09State 0, W07 0, Main 0.
Local gate: P1-P42 + S1-S4 43 / 43, P43-P57 + S5 16 / 16, Reference MISSING / EXTRA / ORDER / RESULT all 0, M1-M30
(+ M17 Main) 31 / 31 detected (W09 mutants rebuilt on the renamed source), B12 25 / 25, B13 13 / 13, B14 17 / 17 + D19.
random 0; 5k / 50k / 200k NOT RUN. I27 OPEN 0.

## W09 B18 TV Gate fix: B18_TV_GATE_W09STATE_35_CE10271_HELPER_ORDER_FIX

TV Gate: W09State /35 compile FAIL, line 1261 CE10271 (could not find function 'wdIndexRaw'; "1 of 3 problems"). Cause:
phaseArmedIndexRelease (B18 Phase B release of Waiting / Dormant Sides) called wdIndexRaw, which was defined after it (with
orderDropRaw, right before phaseMoveRaw). Fix: the helper block (orderDropRaw, wdIndexRaw and their comments, 27 lines) moved
unchanged to just before phaseArmedIndexRelease; dependency order now priceOrderUpdate (112) / indexMemberRaw (317) /
PhaseArmedTransferView (923) -> orderDropRaw -> wdIndexRaw -> phaseArmedIndexRelease -> phaseMoveRaw -> Stage J helpers /
caller. Pure move: the file's line multiset is identical (semantic diff 0). Static audit over every top-level function / type /
const in W09State, W07Fvg and Main: FORWARD_REFERENCE 0, UNRESOLVED_FUNCTION_REFERENCE 0 (before the fix: exactly 1, this
call); shadowing on B18-changed lines 0; reserved identifiers (to / from / keywords / type names) 0. The local interpreter does
not enforce definition order, so the audit is the static gate for this class. The other two TV problems could not be
reproduced locally (no further unresolved / forward / reserved / shadow finding); not guessed. W09State /35, W07Fvg /12,
Main imports unchanged. Local gate: 43 / 43, 16 / 16, Reference metrics 0, M1-M30 (+ M17 Main) 31 / 31 detected (W09
mutants re-applied on the moved source), B12 25 / 25, B13 13 / 13, B14 17 / 17 + D19. random 0; 5k / 50k / 200k NOT RUN.
I27 OPEN 0.

## W09 B18 CLOSEOUT: W09_B18_STATE_PRICE_INDEX_REFERENCE COMPLETE / FROZEN

START: claude/w09-b07-redesign-v2, local = remote = bd220ed, 0 / 0, clean; Production W07Fvg /12, W08Core /19, W08Touch /7,
W08Runtime /21, W09State /35; Main imports W07Fvg /12, W09State /35; I27 OPEN 0. CLOSEOUT changes this ledger only.

Phase A evidence: naive full-scan Reference vs Production optimized path P1-P25 PASS; MISSING 0, EXTRA 0, ORDER_DRIFT 0,
RESULT_DRIFT 0; index stale / missing / duplicate 0; Phase A Production drift 0.
B18-F1 FINAL: the per-bar full live-Core scan of Stage J = REMOVED. Stage J targets = union of state set + price index +
same-bar transition / topology targets -> dedupe -> canonical order -> phaseArmedStageJFinalize (the one final writer);
semantic diff 0.
B18-F2 FINAL: the BS price index is consumed by Production (Flip / Reclaim targets); Waiting Reset / reArm index, Dormant
entry / recovery index and Armed price index used by Production; the Inverse threshold index is used by Production in W07
/12. W07_I11_INVERSE_THRESHOLD_INDEX_CARRY = CLOSED.
B18_INDEX_KEY_REPRESENTATION = EDGE_KEY_PLUS_QUERY_OFFSET_ACCEPTED_EQUIVALENT: the indexes keep the range edge tick as the
key; rd / dd / break / reset buffer offsets are applied in the query; exactly equivalent to the canonical predicate on integer
ticks; no needless re-key on a cfg change. Not an I27.
W07 Inverse index: W07 /11 -> /12, Inverse lifecycle semantic change 0; WAIT_MOVED_AWAY dedicated threshold index,
MOVED_AWAY reuses the W03 FVG NativeRange order, RETOUCHED dedicated threshold index; InverseWait full predicate scan 0.
Reference parity MISSING / EXTRA / ORDER / RESULT / INDEX_STALE / INDEX_MISSING / INDEX_DUPLICATE all 0.
Full deterministic evidence: P1-P57 all PASS; B18 static gates (S1-S5, forward reference, reserved identifier) all PASS;
Production / Reference MISSING 0, EXTRA 0, ORDER_DRIFT 0, RESULT_DRIFT 0; /34 baseline vs B18 final Production Event /
Phase / history drift 0. Mutations M1-M30 (incl. the M17 Main variant) all detected, MUTATION_UNDETECTED 0.
Regression: B08 / B09 / B10 / B11 / B12 / B13 / B14 / B15 / B16 / B17 PASS, W08Runtime guard PASS, W07 /11 vs /12 semantic
drift 0; random 0; 5k / 50k / 200k NOT RUN.
TV compile fixes during the B18 TV Gate (semantic-neutral): A W07Fvg /12 reserved identifier `to` -> `toOrder`; B W09State
/35 reserved identifier `to` -> `toOrder`; C W09State /35 CE10271 helper dependency order (orderDropRaw / wdIndexRaw before
phaseArmedIndexRelease; physical placement only). Semantic diff 0; W07 /12 and W09State /35 kept.
TradingView Final Gate (user): W07Fvg /12 publish PASS, W09State /35 publish PASS, Production Main compile PASS, compile
error 0, runtime error 0, exact compiled token UNKNOWN (no GREEN / YELLOW / RED class).
OPEN carries (not B18 blockers; must be CLOSED before the final canonical diff 0):
- W10_CARRY_I17_REUSABLE_SCRATCH_3PATHS = OPEN: touchHistoryTransferPlan (seen), bsTransferPlan (rel + full Side loop),
  touchStartPostPlanPreflight (busy / roles); I17 authority = Engine-owned reusable scratch + logical length reuse; CLOSE by
  W10 or the Final Integration.
- W10_CARRY_W07_INVERSE_INDEX_FREE_RETIRE_CLEANUP = OPEN: no FVG Root free / retire path today; when W10 Storage / Prune
  makes one reachable, the W07 /12 Inverse WAIT / RETOUCHED index entries, the NativeRange-related membership and the
  reverse positions must be detached / reset before free / slot reuse. Re-audit in W10.
Production final versions: W07Fvg /12, W08Core /19, W08Touch /7, W08Runtime /21, W09State /35 (Main imports these).
I27: OPEN 0, no new I27 in B18. CLOSEOUT Production change 0.
Status: W09_B18_STATE_PRICE_INDEX_REFERENCE COMPLETE / FROZEN. Frozen inputs from here: the price index semantic, the
edge-key + query-offset representation, Stage J indexed targeting, BS indexed targeting, W07 Inverse index targeting; only the
two W10 carries above may reopen them. Next: B19 Conformance (not started).

## W09 B19 Conformance (local): W09_B19_CONFORMANCE_LOCAL PASS / TV HARNESS WAITING

START: claude/w09-b07-redesign-v2, local = remote = c8f4311, 0 / 0, clean; Production W07Fvg /12, W08Core /19, W08Touch /7,
W08Runtime /21, W09State /35 (Main imports these; Main TV compile PASS at B18); I27 OPEN 0. TOKEN START REVIEW: Production
compiled exact UNKNOWN (no GREEN / YELLOW / RED class); B19 plans no Production change.
Scope: Appendix B 46-69 (24 cases) as a final conformance of the frozen B01-B18 W09 semantics; no new Zone logic. Authority =
canonical + frozen decisions (the old ZoneEngineV2_Rebuild_ConformanceHarness is not used as authority).
Harness (local, scratch, not committed): 3 layers. (1) independent Reference b19_ref.py: a per-Side state machine (coreId,
generationId, Side, Phase, Grade, WeakByTouch / WeakByDepth, TouchCount, CurrentTouchNo, Fresh / ZoneFresh, TSS, BreakSnapshot
incl. movedAway / retestSeen, attempt, lastFlipConfirmSeq, Dormant, EffectiveRange / LastArmedRange, history); it reads the
fixture once and evolves its own state; no Production helper is called (no index / target / Grade helper). (2) Production
path: W09State /35 + Main w09StageCDPlanRaw + Main post-commit slice interpreted in the Main stage order (B17), W08 stub.
(3) comparison per bar: final Side state (17 fields), ZoneFresh, Core Dormant (Stage J target Cores), the Event list (count /
type / time / seq / coreId / generationId / Side / range / touchNo / gradeAtStart / weakReason / rootId; canonical order
coreId, generationId, Support, Resistance; suppressed Events 0) + the B18 I22 audits on every bar (index_audit pre / post,
target_audit: full-scan state sets and price indexes).
APPENDIX_B_W09 46-69 = 24 / 24 PASS, FAILED 0, NOT_RUN 0 (LOCAL_REFERENCE_PASS; TV not claimed). 81 Reference bars + 6 Merge /
Split topology runs: STATE_DRIFT 0, EVENT_DRIFT 0, RUNTIME_ERROR 0, unexpected F0 0. Extra Reference scenarios: X1 B14 Stage J
(Armed -> Dormant, recovery bar touching the zone without a Touch, ArmedFromSeq = seq + 1, a Reset far away is a transition ->
no Dormant), X2 B13 Reclaim > FlipConfirm (degenerate line BS), X3 F0 fixture (mutation 0, Event 0, index mutation 0): 3 / 3.
61 (re-flip history restore): Production keeps the per-Side history on its own Side slot; bsPairEndRaw / flipApply never write
TouchCount / Weak / MaxDepth / Fresh, so a re-flip to the used Side restores it (canonical 10.3 / 15.3) - verified end to end
(Touch 2 + Break -> Resistance Flip / Touch / Break -> Support FlipConfirm -> Touch 3, WEAK_BY_BOTH). No drift, no I27.
I22_W09_STATE_INDEX_REFERENCE (local) PASS: TOUCH / GAP / D1 / ACTIVE / BREAK / RESET / FLIP / RECLAIM / INVERSE / DORMANT
MISSING and EXTRA 0, ORDER_DRIFT 0, RESULT_DRIFT 0, INDEX_STALE / MISSING / ORDER 0 over every B19 bar (I22 10 / 10 not claimed).
Regression (current HEAD, Production unchanged): B09 16 / 16, B10 14 / 14, B11 14 / 14, B12 25 / 25, B13 13 / 13 (same-bar
priority), B14 17 / 17 + D19 + guard (Stage J), B15 16 / 16 (Merge transfer fields), B16 13 / 13 (Split / R4 incl. pair-mismatch
F0), B17 14 / 14 (stage order, F1 / F2), F2 6 / 6 (duplicate Feed: Stage A reject, previous Events kept, lastBase unchanged),
B18 43 / 43 + B18_INV 16 / 16 (W07 /12 Inverse index), Reference metrics 0.
Mutations: B19 M31-M47 (W09State 15 + Main 2) 17 / 17 detected; M36 first draft (flipPlan breakSeq < -> <=) was an equivalent
mutant (a bar-start Broken set never holds a BS of the current bar, B17 stage order) and was replaced by the Reclaim equality
mutant; M45 (Dormant entry ignoring the bar's transition) needed the X1c scenario (harness coverage, class B). Representative
B18 mutants re-run: M1 / M5 / M10 / M15 / M20 / M17main (b18_det) and M21 / M25 / M30 (b18_inv) all detected.
W09_MUTATION_UNDETECTED = 0.
Static: FORWARD_REFERENCE 0 (W09State, W07Fvg, W08Core, W08Touch, W08Runtime, Main, B19 TV harness); reserved identifier 0;
per-bar Production full live-Core scan 0 (B18 S1: Stage J target extraction), Broken full scan 0 (S2: BS index targets),
InverseWait full scan 0 (B18-B4 S5); Main W09 business duplication 0 (no Main function shares a W09State name; Main reads W09
only through W09State calls). Observation (not a per-bar scan, frozen B12, not changed): invHoldersRaw walks the live Cores once
per InverseConfirm / deferred-confirm Root on bars that carry such a fact (event-gated).
Drift classes: A (Reference) 0; B (harness) 5 fixed in the harness only (two-Core fixture over-touch in the first draft, a
harness helper name shadowing the interpreter, harness J / IV attributes in the F0 state diff, the M36 equivalent mutant, the
X1c coverage); C (Production) 0; D (canonical ambiguity) 0 -> no STOP_I27.
Production drift 0; Production diff 0 (W07Fvg /12, W08Core /19, W08Touch /7, W08Runtime /21, W09State /35, Main untouched; no
version change, no publish).
TV harness: ZoneEngineV2_W09ConformanceHarness_B19.pine (new, indicator, not Production). Imports W09State /35 and W08Touch /7
(the only published W09 path it drives). Layer 1 = golden vectors of the independent Python Reference (81 bars: Events + 31
fields per live Side + ZoneFresh / Core Dormant; 6 Merge / Split mark / history / plan records); layer 2 = the published
helpers in the Main order (view constructors, Stage C / D wrapper and post-commit slice generated from Main's own source text;
W08 topology = the local stub); layer 3 = per-bar comparison + I22 full-scan index / target audit. Output table:
W09_CONFORMANCE_PASS, APPENDIX_B_W09_PASSED / TOTAL / FAILED, I22_STATE_INDEX_PASS, STATE_INDEX_MISSING / EXTRA / ORDER_DRIFT /
RESULT_DRIFT, EVENT_DRIFT_TOTAL, STATE_DRIFT_TOTAL, RUNTIME_ERROR_COUNT (+ EXTRA_X1_X3_FAILED, BARS / GOLDEN, INDEX_CHECKS).
Locally executed as Pine (interpreter, published-source W09State /35 / W08Touch /7): PASS, 24 / 24, all drift 0, 87 bars, 81 /
81 golden, 1730 index checks; the same harness reports FAIL on mutants M31 / M32 / M35 / M37 / M40 / M43 / M44 / M45 and on the
B18 index mutants M5 / M15 (M10 is outside its scenarios; detected by the local B18 suite). Static on the harness: forward
reference 0, HW / HF field references all declared, W09State / W08Touch calls all exported, call arity 0 mismatches. TV compile
/ runtime = NOT RUN (user, next rally).
OPEN carries unchanged (not B19 blockers, not PASS): W10_CARRY_I17_REUSABLE_SCRATCH_3PATHS = OPEN (touchHistoryTransferPlan
seen, bsTransferPlan rel + full Side loop, touchStartPostPlanPreflight busy / roles); W10_CARRY_W07_INVERSE_INDEX_FREE_RETIRE_CLEANUP
= OPEN; Generation 70-73 -> W10; Reproducibility 75 -> W11 / W12.
TOKEN END REVIEW: Production delta 0 (exact UNKNOWN, no class); harness-only addition (2416 lines, compiled exact UNKNOWN).
random 0; 5k / 50k / 200k NOT RUN. I27 OPEN 0.
Status: W09_B19_CONFORMANCE_LOCAL PASS; APPENDIX_B_W09_46_69_LOCAL 24 / 24; I22_W09_STATE_INDEX_LOCAL PASS. B19 = LOCAL PASS /
TV HARNESS WAITING (not COMPLETE).

## W09 B19 TV Harness fix: B19_TV_HARNESS_CE10116_HW_SPLIT_FIX

TV Harness Gate (user): ZoneEngineV2_W09ConformanceHarness_B19.pine compile FAIL, CE10116 "The HW.new function uses 269
external elements. The limit is 254." Cause: the harness-only world UDT HW held all 254 storage fields in one type (186 Main
storage arrays the W09 views read + 68 harness-only fields); its auto constructor exceeded the limit. Not a Production defect.
Fix (harness / generator only): HW split by semantic owner through one generator ownership table (field -> owner, 1 : 1):
HWCore 41 (Core identity, range inputs, current Root lists, Root registry / journal, Core flags), HWState 51 (Phase-carrying
Side state: Touch / Weak / Grade / Fresh / TSS / BreakSnapshot / attempt / history), HWIndex 27 (state sets, set positions,
Armed / Broken / FlipWait / Waiting / Dormant order slots + positions), HWTopo 69 (W08 stub plan, Merge / Split mark arrays,
topology spec, SideView winner rows), HWAux 66 (TouchMark ring, TSS / BS Root node pools, plan scratch, Events, Inverse,
noArm); HW = 5-field wrapper (core / state / idx / topo / aux). Every w.field reference rewritten mechanically to
w.<owner>.field (no hand edit). Estimated external elements per auto constructor (fields x 269 / 254): HW 6, HWCore 44,
HWState 55, HWIndex 29, HWTopo 74, HWAux 70, HF 17; maximum 74 (target <= 200 met). Library view constructors unchanged
(TouchStartPlanView 89 / PhaseArmedTransferView 111 args, the same lists Main compiles with). CE10116 risk 0.
Aliasing kept: each Main storage array is one field with one owner; every view argument references that field (no copy);
UNMAPPED_HW_FIELD 0, DUPLICATE_HW_FIELD_OWNER 0, the hwNew initialisation multiset (254 fields) identical to the pre-split
harness. Harness semantic diff 0: with the owner qualification removed, the type / constructor blocks excluded, the source is
line-identical to the CE10116 version (golden vectors, expectations, predicates, comparisons, I22 audit, stage order,
Merge / Split, R4, Dormant, Inverse unchanged).
Local interpreter (same Pine file): APPENDIX_B_W09 24 / 24, STATE_DRIFT 0, EVENT_DRIFT 0, RUNTIME 0, I22 MISSING / EXTRA /
ORDER / RESULT 0 (1730 index checks), X1-X3 PASS, 87 bars, 81 / 81 golden. Mutation sensitivity: M31 / M32 / M35 / M37 / M40 /
M43 / M44 / M45 + B18 M5 / M15 all reported FAIL (undetected 0).
Static on the regenerated harness: FORWARD_REFERENCE 0, RESERVED_IDENTIFIER 0, UNDEFINED_FIELD 0 (owner-qualified and HF),
UNMAPPED_HW_FIELD 0, DUPLICATE_HW_FIELD_OWNER 0, NON_EXPORTED_CALL 0, ARITY_MISMATCH 0 (harness functions, library functions,
UDT constructors), SHADOWING_ERROR 0. request.* 0, input.* 0, imports unchanged (W09State /35, W08Touch /7).
Production diff 0 (W07Fvg /12, W08Core /19, W08Touch /7, W08Runtime /21, W09State /35, Main untouched, no re-publish).
TOKEN: Production delta 0; harness compiled exact UNKNOWN. I27 OPEN 0. B19 = LOCAL PASS / TV HARNESS WAITING (not COMPLETE).

## W09 B19 TV drift diagnostics: B19_TV_HARNESS_DRIFT_DIAG

TV run (user, harness 44e41f6): W09_CONFORMANCE_PASS FAIL; APPENDIX_B_W09 24 / 24 (FAILED 0); I22_STATE_INDEX_PASS PASS
(MISSING / EXTRA / ORDER / RESULT 0, INDEX_CHECKS 1730); RUNTIME_ERROR_COUNT 0; EVENT_DRIFT_TOTAL 1; STATE_DRIFT_TOTAL 10;
EXTRA_X1_X3_FAILED 1; BARS / GOLDEN 87 / 81 of 81. The local interpreter run of the same file is all 0, so the drift is a
local-vs-TV difference located in one of the extra scenarios X1-X3 (case pass = no counter increase during the case; the 24
Appendix cases all passed). Not classified yet; Production not suspected before the first drift is known; Production frozen.
Diagnostic harness (counters / first-failure capture / table only; golden vectors, Reference expectations, predicates, Production
slice, scenario feeds and every comparison unchanged - the only edited comparison lines bind the same vecDiff operands to
named variables): metric container HM (23 fields: the existing counters + per-field counters + first-failure capture);
X1_PASS / X2_PASS / X3_PASS; FIRST_DRIFT_SCENARIO / BAR_INDEX / GOLDEN_INDEX / KIND (TAG / RUNTIME / EVENT / STATE / GOLDEN /
TOPO) / FIELD / SIDE-CORE / EXPECTED / ACTUAL / EXPECTED_TAG / ACTUAL_TAG; Event first drift = count mismatch first, else the
first differing Event with all 12 fields expected / actual; per-field state counters for the 31 compared Side fields +
ZONE_FRESH / CORE_DORMANT / STATE_LENGTH / TOPO_MARK_HISTORY; execution counts (runAll, goldInit, goldXInit, each of the 27
cases, X1 / X2 / X3, comparisons). The first drift is captured once, never overwritten.
BARS / GOLDEN meaning: 87 = transactions run = 81 golden Reference bars (Appendix 46-67 + X1-X3) + 6 Merge / Split topology
runs (68-0..2, 69-0..2), which compare against the separate topology golden records; 81 = golden Reference records consumed;
"of 81" = golden records in the file. Expected values (87 / 81 / 81).
Local (same file): 24 / 24, X1 / X2 / X3 PASS, state / event drift 0, I22 0, runs runAll / goldInit / goldXInit 1 / 1 / 1,
every case 1, comparisons 81, FIRST_DRIFT none. Diagnostic self-test on mutants: M45 -> X1 FAIL, first drift X1 bar 9 golden 75
STATE PHASE side 0 expected 1 actual 5; M41 -> X2 FAIL, LAST_FLIP_CONFIRM_SEQ expected -1 actual 50; M32 -> EVENT
EVENT_COUNT expected 2 actual 1 with the expected WeakDepth Event fields; M31 -> RUNTIME TXN_OK.
Static: FORWARD_REFERENCE 0, RESERVED_IDENTIFIER 0, UNDEFINED_FIELD 0 (HW owners, HF, HM), NON_EXPORTED_CALL 0,
ARITY_MISMATCH 0, SHADOWING_ERROR 0; UDT fields HW 5, HWCore 41, HWState 51, HWIndex 27, HWTopo 69, HWAux 66, HF 16, HM 23
(max 69, CE10116 margin kept); request.* 0, input.* 0, imports unchanged. Production diff 0. I27 OPEN 0.
Status: B19 = LOCAL PASS / TV DRIFT DIAG WAITING (not COMPLETE).

## W09 B19 TV diagnostics split: B19_TV_DIAGNOSTIC_CE10117_SPLIT

TV Gate (user): the 35763c2 diagnostic harness (one file, 2646 lines) compile FAIL, CE10117 "Compiled code contains too many
tokens: 104908, limit 100256". Not a Production defect: the diagnostics (+ ~230 lines) pushed the 44e41f6 harness, which already
compiled close to the limit, over it. Fix by structural split, no token squeezing:
Harness A = ZoneEngineV2_W09ConformanceHarness_B19.pine restored byte-identical to 44e41f6 (the B19 harness authority; no
diagnostics added). TV evidence kept: compile PASS; APPENDIX_B_W09 24 / 24 (FAILED 0); I22_STATE_INDEX_PASS PASS; STATE_INDEX
MISSING / EXTRA / ORDER_DRIFT / RESULT_DRIFT 0; INDEX_CHECKS 1730; RUNTIME_ERROR_COUNT 0; open items EVENT_DRIFT_TOTAL 1,
STATE_DRIFT_TOTAL 10, EXTRA_X1_X3_FAILED 1 (local 0) -> diagnosed by Harness B.
Harness B = ZoneEngineV2_W09ConformanceHarness_B19_DriftDiag.pine (new, 1592 lines): X1-X3 drift diagnosis only. Kept
unchanged from 35763c2: the X1-X3 fixtures / feeds / expectations / comparisons, the HM diagnostics (X1 / X2 / X3 pass, first
drift scenario / bar / golden index (B index and A index = B + 67) / kind / field / side / expected / actual int and float /
tags, full first drifting Event, 31 + 4 per-field counters, run counts), the Main-generated views / Stage C / D wrapper / post-
commit slice, fixture helpers, HW owner split. Golden: the 14 X1-X3 records only (byte-identical to their 35763c2 strings; A
indexes 67-80). Removed (not reached by X1-X3, no effect on its Production path): Appendix 46-69 scenarios, the 81-record
golden, the 68 / 69 Merge / Split fixtures and topology golden, the I22 index / target audits (read-only), the W08 topology
stub commit / producer branches (X1-X3 have no topology; a topology there is a runtime.error, never silent).
Token estimate (local, NOT a TV value): linear model TV = a * harness tokens + b * reachable library tokens fitted to the TV
facts (35763c2 = 104908, 44e41f6 < 100256) gives Harness B between ~61.5k and ~73.8k (lexical harness tokens 19351 vs 33000,
reachable library tokens 34362 vs 39569); target < 90000; exact TV count UNKNOWN until the user compiles it.
UDT fields (Harness B): HW 5, HWCore 41, HWState 51, HWIndex 27, HWTopo 69, HWAux 66, HF 16, HM 23 (max 69 < 100;
estimated external elements max 74).
Local interpreter (Harness B): X1 / X2 / X3 PASS, EVENT_DRIFT 0, STATE_DRIFT 0, RUNTIME 0, FIRST_DRIFT NONE, runs runAll /
goldInit 1 / 1, X1 / X2 / X3 1 / 1 / 1, comparisons 14, bars 14 / golden 14. Mutations: M45 -> X1 FAIL (first drift X1 bar 9,
B index 8, STATE PHASE side 0 exp 1 act 5); M41 -> X2 FAIL (LAST_FLIP_CONFIRM_SEQ exp -1 act 50); M48 (F0 class: the Stage C / D
TouchStart plan writes TouchCount persistently) -> X3 FAIL (and X1). Static (Harness B): FORWARD_REFERENCE 0,
RESERVED_IDENTIFIER 0, UNDEFINED_FIELD 0, UNDEFINED_FUNCTION 0, NON_EXPORTED_CALL 0, ARITY_MISMATCH 0, SHADOWING_ERROR 0;
request.* 0, input.* 0; imports W09State /35, W08Touch /7. The 35763c2 single-file diagnostic harness stays in history as a
TV compile FAIL artifact; it is not a B19 harness authority. Production diff 0. I27 OPEN 0.
Status: B19 = LOCAL PASS / TV DRIFT DIAG WAITING (Harness B to be run on TV; not COMPLETE).

## W09 B19 TV drift diagnosis: B19_TV_X2_RECLAIM_PIPELINE_DIAG

TV run of Harness B (f685e1c, user): X1_PASS PASS, X2_PASS FAIL, X3_PASS PASS; FIRST_DRIFT X2, bar index 2 (= the second X2
sub-case X2-1, old Side RESISTANCE; X2-0 SUPPORT passed), golden index 11 / 78, kind EVENT, field EVENT_COUNT, expected 1
(EV_RECLAIM) actual 0; EVENT_DRIFT_TOTAL 1, STATE_DRIFT_TOTAL 10, RUNTIME_ERROR_COUNT 0 (the transaction committed: golden ok
= 1 matched). Not classified as a Production defect. Local interpreter (same file): both sub-cases pass.
Local counter-check (scratch experiments, not committed): forcing "no Reclaim row" (empty bsTargetSlots output, or the flipPlan
row removed) in X2-1 gives EVENT_DRIFT 1 but STATE_DRIFT 20 (PHASE / GRADE / 8 BS fields on both Sides), not the TV 10; the TV
outcome is therefore not a plain "Reclaim row missing / nothing applied" and the per-field counters of the TV run are needed.
Harness B diagnostic added (display / capture only; golden, X1-X3 expectations, predicates, Production slice and scenario
feeds unchanged): X2 pipeline per sub-case (X2-0 SUPPORT, X2-1 RESISTANCE): bar-start BS state of both Sides (phase, valid,
bottom, top, oldSide, breakSeq, movedAway, retestSeen, wasGap), BS pair invariant, breakBuffer ticks, H / L / C; Broken /
FlipWait set counts and membership; B18 Broken / FlipWait BS price-index membership, positions, keys, index size; read-only
W09State /35 bsTargetSlots (ok, count, old Side / opposite in the targets); raw Reclaim / FlipConfirm / FlipAttempt (flipPlan
formulas, harness-computed, display only); reclaimResolve (FVG invalidation now, suppressed, effective Reclaim); read-only
flipPlan probe (ok, input count, row count, Reclaim / Confirm / Attempt row flags); the real transaction's recorded values
(Stage C / D ok, Flip rows, first row flags, d3 count, rcs count, preflight ok, commit ok, Event append count); after-state (BS
valid, Phase of both Sides); X2_SUBCASE_PASS; FIRST_PIPELINE_FAILURE = the first failing stage of BS_INDEX / BS_TARGET /
RAW_RECLAIM / RECLAIM_RESOLVE / FLIP_PLAN (no Reclaim row, or a FlipConfirm flag on it) / PREFLIGHT / COMMIT / EVENT_APPEND /
NONE. The probe runs before the bar on the bar-start state; its only writes are local scratch and the plan scratch arrays,
cleared before the transaction (which clears them again).
Local (Harness B, this file): X1 / X2 / X3 PASS, drift 0, FIRST_DRIFT NONE, FIRST_PIPELINE_FAILURE NONE / NONE, every stage of
both sub-cases as expected (index member 1, targets {old Side}, raw Reclaim 1 and raw FlipConfirm 1 (the B13 degenerate case),
effective Reclaim 1, row Reclaim 1 / Confirm 0, flags 19, preflight 1, commit 1, Events 1, BS cleared, both Waiting). Mutants:
M41 -> X2 FAIL with FIRST_PIPELINE_FAILURE FLIP_PLAN (Confirm flag on the Reclaim row) on both sub-cases; M45 -> X1 FAIL; M48 ->
X3 FAIL. Static: FORWARD_REFERENCE 0, RESERVED_IDENTIFIER 0, UNDEFINED_FIELD 0, UNDEFINED_FUNCTION 0, NON_EXPORTED_CALL 0,
ARITY_MISMATCH 0, SHADOWING_ERROR 0; UDT max 69 fields (HWAux 67, HM 24); request.* / input.* 0. Token estimate (local model,
not TV): ~70k-79k (< 90k). Harness A unchanged (44e41f6). Production diff 0. I27 OPEN 0.
Status: B19 = LOCAL PASS / TV DRIFT DIAG WAITING.

## W09 B19 X2 TV drift root cause: B19_X2_TV_DRIFT_ROOT_CAUSE

Classification: HARNESS_FIXTURE_RESISTANCE_PHASE_ORIENTATION. Production defect: NO.
TV evidence (Harness B 28bbbc9, user): X2-1 (old Side RESISTANCE): BS oldSide -1 on the old slot (correct) but PRE_OLD_PHASE 4
(FlipWait) and PRE_OPP_PHASE 3 (Broken) - reversed against the B08 / B10 / B13 frozen invariant (BS.oldSide Broken, opposite
FlipWait); X2_BROKEN_SET_COUNT 0, X2_FLIPWAIT_SET_COUNT 1, old Side not in the Broken set, X2_BS_INDEX_MEMBER_OLD 0, positions
-1 / -1, BROKEN_INDEX_SLOT_COUNT 0, BS_TARGET_OK 1 with X2_BS_TARGET_COUNT 0. The Reclaim predicate never ran: the old Side was not
in the Broken set / Broken BS index, so bsTargetSlots returned no target. The X2-0 SUPPORT sub-case was correct.
Notes: the fixture source (setBS) already wrote Broken / FlipWait relative to the old slot; the TV pre-state was also not a clean
swap (a local pure-swap fixture mutant gives Broken set 1, STATE 20, RUNTIME 1, vs TV Broken set 0, STATE 10, RUNTIME 0), i.e. the
TV world of the second sub-case was inconsistent with its source. Both X2 sub-case worlds were built inside one while loop of
sX2 (the only loop-built fixture in the harness); the local interpreter does not reproduce it.
Fix (Harness B only): X2 fixture made explicitly oldSide-relative and loop-free: x2Case(oldSide) per sub-case (old slot 0 for
SUPPORT, 1 for RESISTANCE), straight-line calls x2Case(SUPPORT) then x2Case(RESISTANCE); BS pair / Broken / FlipWait Phases
via setBS on the old slot, every Phase set and Broken / FlipWait BS price index / position via finishW (the existing fixture
helpers). Mirror invariant x2Pre at fixture start (both sub-cases): Phase(old) Broken, Phase(opposite) FlipWait, both BS valid,
BS.oldSide = the old Side on both, old Side in the Broken set and both Broken BS indexes, opposite in the FlipWait set and both
FlipWait indexes; a failure counts FIXTURE_PRECONDITION_FAIL, is captured as the first drift (kind FIXTURE, X2_PRECONDITION) and
fails the case. Golden / X2 expectations / predicates / Production slice unchanged (B13 frozen: raw Reclaim and raw FlipConfirm
true, effective Reclaim true, FlipConfirm false, EV_RECLAIM 1, BS pair cleared).
Local (Harness B): X2-0 SUPPORT and X2-1 RESISTANCE: old Phase Broken, opposite FlipWait, Broken set 1, old in Broken set 1, old BS
index member 1, BS target count 1 (old Side), raw Reclaim 1, effective Reclaim 1, row Reclaim 1 / Confirm 0, preflight 1, commit
1, Event 1, BS cleared, both Waiting; X1 / X2 / X3 PASS; EVENT / STATE drift 0; FIRST_DRIFT NONE; FIRST_PIPELINE_FAILURE NONE;
FIXTURE_PRECONDITION_FAIL 0. Mutation: M41 -> X2 FAIL (FLIP_PLAN on both sub-cases); harness fixture mutant (RESISTANCE Phase swap
back to the old wrong state) -> FIXTURE_PRECONDITION_FAIL 1, first drift FIXTURE X2_PRECONDITION (slot 1, expected 3, actual 4),
FIRST_PIPELINE_FAILURE BS_INDEX, X2 FAIL; M45 -> X1 FAIL; M48 -> X1 / X3 FAIL. Static: FORWARD_REFERENCE 0, RESERVED_IDENTIFIER 0,
UNDEFINED_FIELD 0, UNDEFINED_FUNCTION 0, NON_EXPORTED_CALL 0, ARITY_MISMATCH 0, SHADOWING_ERROR 0; UDT max 69 (HM 25). Harness A
unchanged (44e41f6 evidence: Appendix 24 / 24, I22 PASS). Production diff 0. I27 OPEN 0.
Status: B19 = LOCAL PASS / TV DIAG RECHECK WAITING.

## W09 B19 CLOSEOUT: W09_B19_CONFORMANCE COMPLETE / FROZEN

START: claude/w09-b07-redesign-v2, local = remote = 2ddf0f7, 0 / 0, clean. CLOSEOUT changes this ledger only (Production change 0,
harness semantic change 0, version change 0).
TradingView Final Gate (user):
Harness A ZoneEngineV2_W09ConformanceHarness_B19.pine (= 44e41f6): compile PASS; APPENDIX_B_W09 46-69 PASSED 24 / TOTAL 24 /
FAILED 0; I22_STATE_INDEX_PASS PASS; STATE_INDEX_MISSING 0, EXTRA 0, ORDER_DRIFT 0, RESULT_DRIFT 0; RUNTIME_ERROR_COUNT 0.
Harness B ZoneEngineV2_W09ConformanceHarness_B19_DriftDiag.pine (= 2ddf0f7): X1_PASS / X2_PASS / X3_PASS PASS; EVENT_DRIFT_TOTAL
0; STATE_DRIFT_TOTAL 0; RUNTIME_ERROR_COUNT 0; FIXTURE_PRECONDITION_FAIL 0; BARS_RUN 14; GOLDEN 14 / 14; X1 / X2 / X3 execution
1 / 1 / 1; COMPARISON_COUNT 14; FIRST_DRIFT NONE; every field drift 0. X2 Support / Resistance: old Side Broken, opposite FlipWait,
BS pair valid, BS.oldSide = old Side, Broken set 1, FlipWait set 1, old Side in Broken set and BS index, BS target 1 (old Side).
Recorded: APPENDIX_B_W09_46_69_TV 24 / 24 PASS; I22_W09_STATE_INDEX_TV PASS; W09_B19_STATE_DRIFT 0; W09_B19_EVENT_DRIFT 0;
W09_B19_RUNTIME_ERROR 0.
X2 root cause final: B19_X2_TV_DRIFT_ROOT_CAUSE = HARNESS_FIXTURE_RESISTANCE_PHASE_ORIENTATION; Production defect NO (the old
Resistance fixture world had old Side FlipWait / opposite Broken, the old Side outside the Broken set / BS index, bsTargetSlots 0,
so the Reclaim predicate was never reached; fixed by the oldSide-relative, loop-free X2 fixture with the mirror precondition).
Local evidence: Appendix 46-69 24 / 24, per-bar state drift 0, Event drift 0, I22 W09 state index PASS; mutations B19 M31-M47
17 / 17 detected, B18 representative 9 / 9 detected, W09_MUTATION_UNDETECTED 0; regression B09-B18 + F2 PASS.
Scope: Appendix B closed in B19 = 46-69 only (70-73 Generation -> W10; 75 full reproducibility -> W11 / W12); Appendix 75 / 75
not claimed. I22 closed in B19 = I22.1-7 (State price index vs all Core / Side scan, I22_W09_STATE_INDEX_REFERENCE PASS); I22
10 / 10 not claimed (remaining items in later windows).
Production final: W07Fvg /12, W08Core /19, W08Touch /7, W08Runtime /21, W09State /35; Main compile PASS; B19 Production semantic
diff 0 (harness changes only).
OPEN carries (not PASS): W10_CARRY_I17_REUSABLE_SCRATCH_3PATHS; W10_CARRY_W07_INVERSE_INDEX_FREE_RETIRE_CLEANUP; Appendix
70-73 -> W10; Appendix 75 -> W11 / W12; 365-day benchmark -> W11; Visual final conformance -> W11.
TOKEN: Production delta 0; exact compiled tokens UNKNOWN (no class). I27 OPEN 0.
Status: W09_B19_CONFORMANCE COMPLETE / FROZEN. Next: B20 Final / HANDOFF_W09 (not started).

## W09 B20 Final audit / HANDOFF: W09_B20_FINAL_AUDIT PASS, W09 COMPLETE / FROZEN

START GATE: claude/w09-b07-redesign-v2, local = remote = a5ca7a1, 0 / 0, clean, Production uncommitted diff 0, I27 OPEN 0,
B01-B19 COMPLETE / FROZEN. Canonical: 09_窓09 (SHA-256 8f5373a4...b9ef8) and Zone_definition_spec_v2(5) (f0ada2d8...49cd1)
present; HANDOFF_W08.md (99ddb63d...ab5be7) present; W10 canonical 10_窓10_Snapshot_Pending_Generation_Fresh_Event_Storage.md
NOT in the repo (to be received at W10 START). The pre-B01 audit artifact is not current truth.
TOKEN START REVIEW: Production source delta 0, Main compile PASS, exact UNKNOWN. TOKEN END REVIEW: Production delta 0, version
delta 0, new high-cost structure 0; B20 is document-only (this ledger + HANDOFF_W09.md).
Final static: Main imports W03F0 /5, W03Apply /4, W03ETimeFvg /3, W06Component /25, W07Fvg /12, W08Core /19, W08Touch /7,
W08Runtime /21, W03EMsa /9, W09State /35 (W07Fvg /12 and W09State /35 published); Main TradingView compile PASS, compile error 0,
runtime error 0, exact compiled tokens UNKNOWN (no class); B19 harness evidence files present (A 2436 lines = 44e41f6,
B 1764 lines = 2ddf0f7); I27 OPEN 0; W09 canonical OPEN 0 (W09 scope); Production uncommitted diff 0.
Batch table: B01 (TSS contract, referenced in W09State comments only; no separate ledger heading / commit) .. B19 from the
ledger / commit names; B20 COMPLETE. I27 in W09: I27-15 (B08, #2 Split part superseded by I27-B16-1), I27-18 (B06), I27-13R
(applied in B17 F2), I27-B12-1..4, I27-B13-1..2, I27-B14-1..3, I27-B16-1 (R4) - all RESOLVED / CLOSED; OPEN 0.
Carries: W09_CARRY_MERGE_SIDE_STATE_TRANSFER CLOSED (B15). OPEN to W10: W10_CARRY_I17_REUSABLE_SCRATCH_3PATHS,
W10_CARRY_W07_INVERSE_INDEX_FREE_RETIRE_CLEANUP; later windows: Appendix B 70-73 -> W10, Appendix B 75 -> W11 / W12, 365-day
benchmark -> W11, Visual final conformance -> W11 (not W09 incompleteness).
Recorded: W09_B20_FINAL_AUDIT PASS; W09_WINDOW_STATUS COMPLETE / FROZEN; W09_BATCH 20 / 20 COMPLETE; W09_I27_OPEN 0;
W09_CANONICAL_OPEN 0 (W09 scope); W09_PRODUCTION_UNCOMMITTED_DIFF 0; HANDOFF_W09 CREATED. W10 carries stay OPEN.
Next window: W10 Snapshot_Pending_Generation_Fresh_Event_Storage (not started).

## Visual V01 - ZoneEngineV2_Rebuild_VisualHarness.pine (display only, Production diff 0)
New indicator, 502 lines. Import: ZoneEngineV2_Rebuild only (pinned /26 = Main source at W09 final HEAD 5bedafa; to be
published by the user, adjust the pin if TradingView assigns another number). Engine: one newEngine + updateConfirmed5m
per confirmed 5m bar over the full history; Source helpers / five request.security / Cfg / 110 Feed fields byte-identical
to ZoneEngineV2_Rebuild_W03Harness lines 14-334 (no calc_bars_count, no history window). View: viewCount / viewAt on
barstate.islast only; visual filters (eligible, side, grade, phase), bounded top-K (<= 30) insertion by distance ASC,
coreId ASC, generationId ASC, Support first (randomized check vs full sort 0 / 20000 mismatches); fixed pools 30 boxes +
30 lines created on the first bar, never deleted. debugPerf (default off) = 1 table, 6 cells. Static: forward reference
0, reserved identifiers 0. Exact compiled tokens UNKNOWN (no colour class); TV compile WAITING (user). random = 0.

## Visual V01 lightweight audit (pre TV Gate; Main /26 NOT published)
Pools (box 30 + line 30) and the debugPerf table are now created lazily on the first barstate.islast execution only (I19.2:
0 objects on historical bars), then reused through setters. Read path audit (Main source): A viewCount + viewAt = O(1)
per call (direct slot reads, no scan), O(N) per last bar; B coreViewAt scans every participation edge per Core = O(N x E),
carries no Side state (side / phase / grade / eligible / effective range), and the facades own a separate hidden engine
(viewAt unusable on it) -> B cannot reproduce the display; A kept. Top-K now stores the drawn fields, so the second viewAt
pass is removed: last-bar Public API calls = 1 viewCount + 2N viewAt. Feed section still byte-identical to W03Harness
14-334; forward reference 0; Production diff 0; 516 lines. Exact tokens UNKNOWN; TV compile WAITING.

## Visual V01 consumer token path (P0 measured, thin facade added)
TV (user): old Visual (Main /26 + explicit W08Touch / W08Core imports, consumer `var ZE.ZoneEngine`) 1,108,083 (CE10216);
P0 (`token_probes/P0_FacadeTokenProbe.pine`, Main /26 only, existing `visualStepAndCoreViews`, no ZoneEngine in the
consumer) 1,003,501 (CE10216, over 3,501) -> removing the consumer-side Engine type exposure saved 104,582.
Main (read-only API add, source +31 lines, deletions 0): `export type VisualZoneRow` (8 primitive fields: coreId,
generationId, side, effectiveBottom, effectiveTop, phase, grade, eligible) and `visualStepAndZoneRows(cfg, feed, doUpdate,
wantSnapshot) -> [committed, array<VisualZoneRow>]`: own `var` engine, updateConfirmed5m once when doUpdate, rows only when
wantSnapshot (coreIdOrderSlots order, Support then Resistance, viewAt slot reads, O(1) per row), function-owned `var` row
array cleared / rebuilt in place (no allocation on historical bars). Existing CoreView facades unchanged. Worker diff 0,
stage / semantic diff 0. Local parity (`v01_parity.py`, 60 deterministic fixtures, 348 rows) viewAt vs rows ORDER 0 /
VALUE 0; mutants 6 / 6 killed. Forward reference 0. Estimator (E2, candidate selection only): P0 path 221,767, P1 path
221,687 (-80 source), Main all exports 223,200 -> 223,434 (+234). P1 TV compile: WAITING (Main /27 publish by the user).

## W09 Windowed Visual V01 (provisional, not full-history parity)
TV (user): P2 (TM-1 Main probe /1 consumer, no drawing) compile PASS, runtime RE10110 (> 40 s) -> full-history Engine update
is the runtime blocker. New file `ZoneEngineV2_W09_WindowedVisual_V01.pine` (542 lines; `ZoneEngineV2_Rebuild_VisualHarness.pine`
kept): V03E runtime architecture (indicator calc_bars_count 5000, engineWindowDays 1..14 default 7, last_bar_time anchored
window, per-request calc_bars_count formulas; source / window / request block identical to V03E lines 33-248, Feed block
identical to V03E 265-383) + backend `ZoneEngineV2_Rebuild_TM1Probe /1` `visualStepAndZoneRows` (provisional probe backend,
semantic drift 0 vs Production) + the V01 display (filters, bounded top-K, lazy islast-only box / line pools 30 + 30).
CoreView / physical geometry / delete-new registry removed. Production diff 0. TV compile / runtime: WAITING.

## Runtime Repair R01-B1: I17 reusable scratch 3 paths (W09State /36, Main pin; allocation only)
TV (user): Windowed Visual 7 d RE10110; 3 d passed once, then RE10110 after a Heavy Script warning; P2R 2016 / 864 bars
RE10110 -> shortening history alone does not fix runtime; per-bar fixed cost first. Semantics FROZEN (W09).
- W09State /36: `export type I17Scratch` (histSrc, histSeen, bsSrc, bsHit, bsRel, bsNoFli, postBusy, postSeen) +
  `newI17Scratch()`; helpers `scratchBoolRaw` / `scratchIntRaw` (exact former length n, all v; grow / shrink only when n
  changes). touchHistoryTransferPlan (src clear, seen), bsTransferPlan (hit, src clear, rel, nfl clear),
  touchStartPostPlanPreflight (busy sized only when ok and nb - its only reads are inside loops that cannot run otherwise;
  roles (caller-owned) exactly the former length of 0s without the temp array; seen map cleared) take `I17Scratch i17`.
- Main: W09State pin /35 -> /36; ZoneEngine field `w09I17Scratch` (newEngine: W09State.newI17Scratch()); the 3 calls pass
  `engine.w09I17Scratch`. Main business logic 0. W08Runtime / W08Core / W08Touch / others unchanged. TM-1 not mixed in.
- Per-bar allocations of the 3 paths: before 9 (2 + 4 + 3: array.new x7 incl. the roles temp, map.new x1, + src) -> after 0
  (one-time 8 in newEngine; growth only when the Core slot count grows; shrink only on an ok = false bar or a smaller n).
- Parity (interpreted Production sources, test shim supplies one persistent I17Scratch per interpreter = the Engine field):
  B08-A / B09 / B10 / B11 / B12 / B13 / B14 / B14 D19 / B15 / B16 R4 / B17 / B18 / B18-INV / B19 (+ TV harness A 24/24,
  X1-X3, harness B) outputs byte-identical to the /35 baseline. Helper exhaustive 196 / 196. Mutants: no fill (bool),
  busy not cleared, no postSeen clear -> killed; no fill (int), redundant src / nfl clears -> survive (roles is a fresh
  caller array, hit reuse not reached by the fixtures, src cleared again before every use, nfl never written: covered by
  the helper exhaustive check / equivalent by construction). random 0; 5k / 50k / 200k not run.
- Estimator (E2, candidate selection only): Main all exports 223,434 -> 223,663; W09State functions 36,508 -> 36,716.
  Exact compiled UNKNOWN. TV: W09State /36 publish -> Main compile; runtime Gate via the TM-1 probe (/2) Windowed Visual.

## Runtime Repair R02-H1: pending pool read-only pass fast path (W08Runtime /22, Main pin; physical only)
TV (user): R01-B1 gate 3 d still RE10110 -> B1 alone insufficient; 7 d gate not run.
- Audit: pool writers = W08Runtime only (Main / W08Core / W09State write none): pendingPlanTrustedRaw (+ pendingNewChildRaw /
  pendingNewRootRaw / pendingClearChainRaw) on the pass pool; commitPass: pendingReplaceRaw (step 1), pendingClearChainRaw
  (consumed READY), coreFreeCommitRaw, coreAllocSlotRaw / coreResetSlotRaw (per-Core arrays) on the real pool. The planner
  writes only the parents of components with diff set, and diff is set only for active components (a live old Core with a
  Side in ActiveTouch in the pass phases). Readers on the pass pool: topologyComponentsRaw, changedPlanTrustedRaw,
  pendingPoolsOkRaw, pendingChainOkRaw, coreFreePreflightRaw, commitPass candidate scan (all read-only).
- /22: `pendingPassReadOnlyRaw(ps, coreLive, phases)` = pool shape as the planners expect, no live pending (every Core
  flag false, no live child, no live Root node) and no live old Core Side in ActiveTouch in the pass phases (the empty-pool
  part is the requested conservative restriction; the ActiveTouch part alone already excludes every write). planPass:
  `ctx.pendingPlanShared` = that predicate; psPlan = ps when shared, else pendingCopyRaw(ps) as before. commitPass: step 1
  pendingReplaceRaw only when not shared. pendingPoolsOkRaw kept on every pass (fail-closed scan; not proven skippable).
  ShadowContext + trailing field `pendingPlanShared = false` (Main's 18 positional args unchanged). Main: W08Runtime pin
  /21 -> /22 only; W09State /36 kept.
- Harness `r02/h1_harness.py` (interpreted /22 source, deterministic 1000 bars, no PRNG; pending created / kept / consumed,
  planner F0 239 bars, downstream F0 91 bars): OLD vs NEW pool / planner / scan drift 0, writes on a shared pass 0; calls
  copy 1000 -> 791, replace 685 -> 500, scan 1000 -> 1000, fast hits 209 / 1000 (fixture mix, not a market rate).
  Mutants: M-H1-1 (always fast) KILLED (drift 953), M-H1-3 (ActiveTouch ignored) KILLED (drift 953), M-H1-2 (pool non-empty
  ignored) SURVIVES = equivalent by the write proof above (kept as the conservative guard).
- Regression B08-A ... B19, TV harness A / B: byte-identical (those suites stub the W08 chain). Exact compiled UNKNOWN.
