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
