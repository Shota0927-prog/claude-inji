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
| R3B0 | W09State /22 -> /23 (Main W09State /23) | R3-B boundary Probe (read-only) | <1,000,000 (exact UNKNOWN) | pending (TV) | UNKNOWN | TV pending; CE10216 -> no R3-B implementation (compact the structure or GT-4D); PASS -> R3-B1 |
