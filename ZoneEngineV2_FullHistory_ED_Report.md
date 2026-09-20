# ZoneEngineV2_FullHistory_ED — Report

Build: `ZEV2-FULLHIST-ED-20260920`

| Deliverable | Lines | Status |
|---|---|---|
| `ZoneEngineV2_FullHistory_ED.pine` | 4,337 | written, **not compiled** |
| `ZoneEngineV2_FullHistory_ED_VisualHarness.pine` | 398 | written, **not compiled** |
| `ZoneEngineV2_FullHistory_ED_Report.md` | this file | — |

Untouched, as required: `ZoneEngineV2_Rebuild.pine`, `ZoneEngineV2_VisualHarness.pine`,
`Zone_Strategy_StrongBounce.pine`, `Zone_StrongReflection_Strategy_Long.pine`.

---

## 0. Two things to read before anything else

### 0.1 The specification documents were not available

Section 2 places `Zone_definition_spec_v2` and
`Claude_ZoneEngine_v2_lightweight_implementation_instructions` above the current
engine in authority. **Neither document is present in this session or in the
repository.** The only inputs available were the four existing `.pine` files.

Consequence: the eight mismatches enumerated in section 22 of the instruction
were implementable, because that section describes each one concretely, and all
eight are implemented. **Any specification mismatch that is not listed in
section 22 could not be detected and therefore is not fixed.** Section D below
lists only what section 22 named plus what static reading of the reference code
revealed.

### 0.2 Nothing here has been executed

There is no TradingView runtime in this environment. Therefore:

* compile status — **unknown**
* every timing in section F — **NOT RUN**
* every counter value in section G — **NOT RUN**
* every acceptance test in section H — **NOT RUN**, except the ones that are
  decidable by reading the code, which are marked `STATIC`

Per the instruction's own rule, this is **not** a completed deliverable. It is
Phases 1–4, 9 and 10 of the 10-phase plan in section 41. Phases 5–8 (logic test,
profiler, hotspot optimisation, load verification) require your machine.

---

## A. Architecture — Fast Path / Slow Path

The engine does not reduce Zone logic. It reduces how often the expensive part
of that logic runs.

```
confirmed 5m Base bar
  │
  ├─ A  freeze previous-bar snapshots
  ├─ B  Armed Views only → Touch / GapBreak      (cheap, per-Core scalar tests)
  ├─ C  ActiveTouch episodes vs TouchStartSnapshot
  ├─ D  Break / WeakDepth / Reset / Flip / Reclaim / Inverse / FVG Fresh
  ├─ E  simultaneous-event precedence
  ├─ F  source events → Root add / update / retire / FVG invalidation
  │        └─ ONLY here can topologyDirty become true
  ├─ G  LiveStructure refresh
  ├─ H  if topologyDirty → SLOW PATH: rebuild the affected bands only
  ├─ I  Merge / Split / Identity / PendingGeneration
  ├─ J  new-generation re-approach (runs early, see FIX 22.7)
  └─ K  next-bar Phase / Grade / Armed
```

**Fast Path** = phases A–G, I, K with `topologyDirty == false`. No candidate
search, no clustering, no Root sweep, no `array.new`, no sort, no string.

**Slow Path** = the same bar plus phase H. Entered only when a Root actually
changed. The counters `fastPathBars` / `slowPathBars` / `slowPathPct` measure
the split; `noOpBars` measures bars that produced no event at all.

The decisive change versus the reference build is in **section 9 — the MA Fast
Path**. EMA2000/EMA3000 move on nearly every Base bar, and the reference build
called `f_markDirty()` on every move, so `topologyDirty` was true on essentially
every bar of a long run and the Slow Path was the only path. That is the single
reason the reference build could not be run over a year.

---

## B. Indexes — what is held and why

| Index | Purpose | Kept from reference build? |
|---|---|---|
| `pointPriceIndex` | price-sorted live point Roots; band queries use `f_pointIndexLowerBound` (binary search) and walk forward until the band ends | yes, extended |
| `swingSlots` / `accumSlots` / `timeSlots` / `fvgSlots` | category-local live slots; source ingestion, duplicate detection and storage checks never sweep the Root registry | yes |
| `freshFvgSlots` | only FVGs still Fresh; a Root leaves the set permanently when Fresh becomes false (**P5**) | yes |
| `inverseWaitSlots` | only FVGs in InverseWait; the Inverse machine never scans all FVGs | yes |
| `liveCoreSlots` / `freeCoreSlots` | live Cores and slot reuse | yes |
| `freeRootSlots` | Root slot reuse, so retire/allocate does not grow arrays | yes |
| `dirtyBottoms` / `dirtyTops` | **disjoint** dirty bands; two unrelated changes never merge into one min..max band | yes |
| `work*` scratch arrays | reusable candidate-search buffers; winners copy out, losers allocate nothing | yes |

### Indexes considered and deliberately NOT added

Section 6 asks for `armedSupportSlots`, `armedResistanceSlots`,
`activeTouchSlots`, `breakFlipWaitSlots`, `generationWatchSlots`,
`dormantCoreIndex`, and then says explicitly that where the maintenance cost
exceeds a simple scan, measure instead of assuming.

`maxZoneCores` is 80. A per-bar pass over `liveCoreSlots` is at most 80
iterations of a handful of float comparisons, with an early-out
(`f_coreIdleDormant` + `f_barNearCore`) already rejecting idle far Cores. Against
that, five state indexes must be corrected at every transition in
`f_startTouch`, `f_breakSide`, `f_processActiveSide`, `f_processBreakWait`,
`f_refreshArmDormant`, `f_startNewGeneration`, merge, split, prune and
invalidation — about twenty write sites, each an opportunity for a
state-index-versus-reality bug that would silently change Zone results.

**Decision: not added in this build.** The same effect is obtained from the
existing early-out, and `coresVisitedLast` is exported so the assumption can be
falsified with real numbers. If profiling shows the Core pass is material, the
indexes become worthwhile and the counters will say so. This is the one place
where the instruction's named structure was not implemented, and it is recorded
here rather than quietly skipped.

Similarly, **psychological Roots were left persistent** rather than derived
on demand (section 14). Measured statically: they are created at 50-dollar
spacing only near real Roots, so over a full XAUUSD year the live set is on the
order of tens of Roots, not thousands. The MA relationship test in
`f_maMoveChangesRelationships` does derive psych levels arithmetically rather
than scanning them, which is where the cost actually was.

---

## C. Dirty dependency — what each change recomputes

Root change classes are declared as `RC_*` constants.

| Change | Dirty band | Also recomputed |
|---|---|---|
| `RC_ADDED` (Swing, Accum pair, FVG, Time H/L) | `[p - M, p + M]`, or `[bottom - M, top + M]` for a range Root | nothing else |
| `RC_REMOVED` (retire, prune) | old band | `eligibilityDirty`, `storageCheckDirty` |
| `RC_PRICE_MOVED`, non-MA | old band + new band, merged only if they overlap | — |
| `RC_PRICE_MOVED`, **MA, relationships unchanged** | **none** | the Cores carrying the Root, in place |
| `RC_PRICE_MOVED`, **MA, relationships changed** | old band + new band | — |
| `RC_QUALITY_CHANGED` (`tfMask` gains a timeframe) | `[p - M, p + M]` | — |
| `RC_DIRECTION_CHANGED` (FVG inverse confirm) | `[bottom - M, top + M]` | `eligibilityDirty` |
| `RC_LABEL_CHANGED` (Time H/L label union) | `[p - M, p + M]` | — |
| `RC_FVG_STATE_CHANGED` (structural invalidation) | `[bottom - M, top + M]` | `eligibilityDirty` |
| FVG **Fresh** false | **none** | only the `fvgFreshCount` of Views holding that Root |

Fresh is output state only: it does not enter C, H, Density, participation or
EffectiveRange, so it must not trigger a rebuild. Bands stay disjoint; each is
rebuilt separately in `f_rebuildDirtyTopology`.

### The MA relationship test

An EMA move can change the outcome only by changing a *relationship*. The test
enumerates them exactly, over `[min(old,new) - 2M, max(old,new) + 2M]`:

* for every point Root: within-M, within-DenseWidth, and which side of the EMA
* for every derived 50-dollar psych level: the same three
* for every FVG: EMA-inside-NativeRange, plus the two classifications against
  `nativeTop` and `nativeBottom`

If none flips, membership, category count C, High count H and the Density class
cannot have changed, and the Cores are updated in place: new EffectiveRange from
the unchanged members (including the FVG proximal-extension rule, reproduced
exactly), Density and BaseStrong from the new width, and ReferencePrice
recomputed for the winner only.

**Known residual.** If two candidates have identical C and identical H, the
winner tie-break falls through to narrower width. An EMA move that changes no
relationship can still change that one width and so, in principle, flip the
winner between two equally-ranked candidates. The test does not cover that case.
`cfg.maFastPath = false` disables the fast path entirely and reproduces the
reference build's behaviour bar for bar; the harness exposes it as a checkbox.
**Run the 14-day parity comparison with it both ON and OFF (test P11) before
trusting a long run.** This is the only intentional inexactness in the build and
it is opt-out.

---

## D. Logic fixes — differences from `ZoneEngineV2_Rebuild`

All eight are implemented and marked in the source as `FIX 22.x`.

| # | Reference-build behaviour | New behaviour |
|---|---|---|
| 22.1 | One high that is simultaneously the session, day and week high created three Roots, so it looked like three independent origins and wrongly satisfied the Time H/L High condition. Superseding one label retired the shared Root and orphaned the other two references. | `f_findTimeRootSameOrigin` merges same subtype + same originTime + same price into one Root carrying a union label mask. `f_replaceTimeRoot` removes only its own label and retires the Root only when nothing points at it, returning the surviving id. |
| 22.2 | Reclaim was nested inside `if wasMoved`, so a reclaim that happened before price had left by ResetDistance was silently dropped. | Reclaim is evaluated from the BreakSnapshot range plus BreakBuffer alone. `movedAway` now gates Flip only. |
| 22.3 | `f_applyCandidate` skipped the whole View update during ActiveTouch, so a Zone whose Roots were invalidated mid-Touch kept publishing dead Roots, a stale EffectiveRange and stale C/H/Density. | Snapshot stays frozen; LiveStructure (rootIds, range, C, H, Density, BaseStrong, Reference, eligible) is refreshed every application. Only episode-owned state is deferred. |
| 22.4 | PendingTopology was flushed on TouchReset only, so an episode that ended in a Local Break left the flag set permanently and the Zone never re-clustered. | `f_flushPendingTopologyIfIdle` is called after Reset, after Break, and as a per-bar safety sweep in `f_processPostRootTransitions`. |
| 22.5 | A Split was materialised mid-episode, moving the ground under the running TouchStartSnapshot. | A Split against a Core with a live episode sets PendingTopology instead; the child Core is created after the episode ends. |
| 22.6 | Split copied the parent's `weakByDepth` and `maxDepthPct` onto every child regardless of which Touches it inherited; merge took `math.max` of counts. The child also received no TouchMarks, so the remap immediately overwrote its history with zero. | `TouchMark` now carries `markSeq`, `touchNo`, `startGrade`, `weakByDepth`, `maxDepthPct`, sealed at episode end. `f_moveMarksToChild` migrates the episodes that intersect the child's range; both parent and child rebuild SideTouchCount, SideFresh, WeakByTouch, WeakByDepth, maxDepthPct and ZoneFresh from the marks they actually own. |
| 22.7 | The generation check ran after Touch detection, so the re-contact that should have opened Generation N+1 was counted as the old generation's next Touch. | `f_processGenerationReapproach` runs before Armed processing; on the switch both eligible Sides are armed from **this** bar, so the contact is recorded as the new generation's Touch 1. |
| 22.8 | Structural invalidation ran before the InverseWait machine, so a Root that became InverseWait on this bar had movedAway / retest / inverseConfirm evaluated against the very Close that invalidated it. | Phase D (`f_updateFvgFresh`, `f_updateInverseWait`) runs before phase F (`f_invalidateFvgsForSource`). A new InverseWait starts advancing from the next Base bar. |

Not changed, by design: the same-5m processing order of section 23, all storage
limits, dormant distance, pruning, protection of ActiveTouch / Broken /
FlipWait / InverseWait / PendingGeneration Cores, and every Zone-definition
threshold.

---

## E. Source requests

Six contexts, one request each, in the harness:

| Context | Payload | Requests |
|---|---|---|
| chart (5m) | 5m Swing — native, no request | 0 |
| 1m | `MAPack`: EMA2000, EMA3000, slope2000, slope3000 | 1 |
| 15m | `SwingPack` | 1 |
| 1H | `TFPack`: Swing + Accum + FVG | 1 |
| 4H | `TFPack`: Accum + FVG | 1 |
| 1D | `TFPack`: Accum + FVG | 1 |

**No `calc_bars_count` is passed anywhere**, in the harness or the library, so
no source warmup is shortened (section 3.3). EMA2000/EMA3000 and the 60-bar
slope get the full history TradingView serves. No `lookahead_on`. No use of an
unconfirmed HTF bar — the engine's own `confirmedTime <= baseCloseTime` gates
are unchanged, and the per-source `lastSource*Time` gate still ensures one
confirmed source bar is consumed exactly once.

### The binding constraint for multi-year runs

MA is defined on 1m. A 5m chart covering one XAUUSD year needs roughly **360,000
1m bars** from the `"1"` context. TradingView does not serve that. Beyond
whatever 1m depth your plan provides, `ma1m` is `na`, `f_ensureMA` does not fire,
and the oldest part of the run simply has no MA Roots — which changes Zone
composition there.

This is a data-availability limit, not something the engine can optimise away,
and section 3.3 forbids papering over it by shortening the request. Two honest
options, both preserving the MA definition exactly:

1. Accept the horizon the 1m context actually reaches, and read it off the run.
2. Host the engine on a **1m chart** and compute `ze.maPackV2()` natively, with
   the Base timeframe still 5m — the structure already proven in
   `Zone_StrongReflection_Strategy_Long.pine`. That removes the 1m request
   entirely. It then needs ~360,000 **chart** bars for a year instead, which is
   a different ceiling, and only Deep Backtesting-class bar counts reach it.

Option 2 is the one to try if option 1's horizon is too short. Neither changes a
line of Zone logic.

---

## F. Performance

**NOT RUN.** No TradingView runtime was available.

| Range | Completed | Wall time | Slow path % | Notes |
|---|---|---|---|---|
| 14 d | NOT RUN | — | — | |
| 30 d | NOT RUN | — | — | |
| 90 d | NOT RUN | — | — | |
| 180 d | NOT RUN | — | — | |
| 1 y | NOT RUN | — | — | |
| 3 y | NOT RUN | — | — | |
| 5 y | NOT RUN | — | — | |

Fill this in by following section 31 in order: 14 d logic first, 30 d with the
Profiler, optimise, then 90 d / 180 d / 1 y without the Profiler. Do not profile
at 1 y — the Profiler's own overhead will dominate and mislead.

### What the design predicts, and how to falsify it

The prediction is that `slowPathPct` collapses from ~100 % (reference build) to
the rate at which Roots actually change: new 5m/15m/1H Swings, confirmed Accum
boxes, new or invalidated FVGs, and session/day/week high-low updates. On XAUUSD
5m that should be single-digit percent.

`maFastUpdates` versus `maSlowUpdates` is the number that decides whether this
build is worth anything. If `maSlowUpdates` is a large fraction of
`baseBarsProcessed`, the MA relationship test is rejecting too often — most
likely because the EMAs sit permanently inside a dense Root neighbourhood — and
the next exact optimisation is to narrow the test's `2M` scan window and to
cache each EMA's neighbour set between bars.

---

## G. Counters

All exported, all written only when `cfg.countersOn` is true (the harness ties
that to the Debug checkbox, so a production run pays nothing):

`baseBarsProcessed`, `fastPathBars`, `slowPathBars`, `noOpBars`,
`slowPathPct`, `noOpPct`, `candidateRebuildCount`, `candidateWindowEvalCount`,
`rootFullScanCount`, `coreFullScanCount`, `dirtyBandCount`,
`maxDirtyBandWidth`, `mergeEvalCount`, `splitEvalCount`, `referenceCalcCount`,
`maFastUpdates`, `maSlowUpdates`, `maxLiveRoots`, `maxLiveCores`,
`requestContextCount`.

`arrayAllocDiagnosticCount` from section 26 is **not** implemented: Pine offers
no allocation hook, and a hand-maintained counter would be a claim rather than a
measurement. P6 is therefore a code-reading test, not a runtime one.

Values: **NOT RUN.**

---

## H. Acceptance tests

`STATIC` = decidable by reading the code, and checked. `NOT RUN` = needs the
platform. Nothing is marked PASS on the strength of an argument alone.

| # | Test | Result |
|---|---|---|
| P1 | No Root event ⇒ candidate rebuild = 0 | **STATIC** — `topologyDirty` is set only by `f_markDirty`, whose only callers are Root add / retire / move / quality / label / FVG-state. Confirm at runtime with `candidateRebuildCount`. |
| P2 | Small EMA move with unchanged neighbourhood ⇒ full topology rebuild = 0 | **STATIC** — `f_updateMaRoot` skips `f_markDirty` when `f_maMoveChangesRelationships` is false. Confirm with `maFastUpdates`. |
| P3 | Distant Swing added ⇒ unrelated price bands untouched | **STATIC** — the new Root's band is `[p-M, p+M]`; `f_collectLocalCoreSlots` filters Cores to that band ±M. |
| P4 | 1H FVG confirmed ⇒ 4H/1D FVGs not swept | **STATIC** — `f_invalidateFvgsForSource` filters on `r.tfCode == p.tfCode` and on `lastSourceCloseTime`. |
| P5 | Fresh=false FVG not re-checked | **STATIC** — the slot is removed from `freshFvgSlots` on the bar Fresh ends. |
| P6 | No-op Base bar performs no array allocation | **STATIC, partial** — the Fast Path calls no `array.new`/`array.copy`. Not machine-verified; see section G. |
| P7 | Debug ON/OFF ⇒ identical Views | **STATIC** — `countersOn` guards only counter writes; no counter is read by any Zone decision. Verify by diffing a View dump both ways. |
| P8 | 30 / 1 / 0 views drawn ⇒ identical Views | **STATIC** — `maxDraw` is consumed only inside `barstate.islast` presentation. |
| P9 | New Zones agree with the 14-day build over the same 14 days | **NOT RUN** |
| P10 | Zones older than 14 days keep real Touch history and do not reproduce the old build's Fresh misread | **NOT RUN** |
| P11 (added) | `maFastPath` ON vs OFF ⇒ identical Views over 14 days | **NOT RUN** — this is the test that closes the section C residual. Run it first. |

The existing acceptance suite (Touch, Weak, Break, Flip, Reclaim, Inverse,
Generation, C/H/Density, EffectiveRange, eligibility, processing order) is
**NOT RUN**. Note that fixes 22.1–22.8 change behaviour on purpose, so any
expected value in that suite that encoded the old Reclaim gating, the old split
history copy or the old generation timing must be re-derived from the
specification before it is used as a pass criterion.

---

## I. Remaining issues

1. **The specification documents were never read.** Section 0.1. Mismatches
   outside section 22 are unaddressed.
2. **Nothing compiled.** Expect first-compile errors. The riskiest new code, in
   order: `f_maRecomputeView` (nested loops over `rootIds` with `break`),
   `f_moveMarksToChild` (`array.unshift` while iterating downward),
   `f_processGenerationReapproach` (arms from the current bar, which the Armed
   path has never been asked to do before), and the restructured
   `f_applyCandidate` (the live block is no longer inside an `else`).
3. **The section C tie-break residual** in the MA Fast Path. Opt-out exists;
   test P11 decides.
4. **State indexes from section 6 not built.** Deliberate and argued in section
   B, but it is a deviation from the instruction and `coresVisitedLast` exists
   so it can be overturned with data.
5. **`arrayAllocDiagnosticCount` not implemented.** Section G.
6. **1m source depth** caps how far a 5m-hosted run can actually reach. Section
   E.
7. **Storage prune / touch truncation over a full year: unknown.** With
   `maxSwingRoots = 180`, `maxFvgRoots = 120`, `maxTimeRoots = 32`,
   `maxAccumBoxes = 60`, `maxZoneCores = 80`, `maxTouchMarksPerCore = 64`, a
   one-year run will certainly prune, and pruning is part of the specification.
   But if `touchHistoryTruncated` turns true, Merge/Split history reconstruction
   falls back to the parent aggregate and fix 22.6 loses precision. Read both
   flags off the Debug table on the first long run; if truncation is common,
   raising `maxTouchMarksPerCore` is a specification change and needs your
   decision, not mine.

---

## J. If the run exceeds 40 seconds

Do not shorten the history. Report these first, all of which the build already
exports:

```
slowPathPct            how often the Slow Path ran at all
maSlowUpdates          how often the MA test rejected
candidateRebuildCount  bands rebuilt
candidateWindowEvalCount  window evaluations - the real inner cost
dirtyBandCount / maxDirtyBandWidth   whether bands stayed narrow
coreFullScanCount      whether Core passes are material
referenceCalcCount     whether ReferencePrice is being recomputed too often
```

The next exact optimisations, in the order they should be attempted, none of
which touch Zone logic:

1. **Cache each EMA's neighbour set.** Recompute it only when a Root is added or
   retired inside `[ema - 2M, ema + 2M]`. Removes the per-bar scan inside
   `f_maMoveChangesRelationships`.
2. **Narrow the relationship scan** from `2M` to `M + |move|`, which is
   provably sufficient.
3. **Build the section 6 state indexes**, if `coreFullScanCount` and
   `coresVisitedLast` say the Core passes matter.
4. **Incremental Dense window summaries** across starts in `f_scoreStartCache`,
   if `candidateWindowEvalCount` dominates.
5. **Root → Core reverse index**, if invalidation-driven rebuilds dominate.

### Safe Bounded History — proposal only, NOT implemented

Offered under section 34, to be built only with your approval and only after the
measurements above show Full Exact cannot reach 40 s.

A Zone whose Root structure is seeded from before continuous replay began would
carry `historyComplete = false`. Such a Zone may be displayed, may act as
context and may hold Root structure, but is **excluded from the Strong
reflection strategy's entry candidates**, and is never presented as Fresh Strong
or Touch 1 Strong. It becomes `historyComplete = true` only when a new
Generation is established entirely inside the continuously tracked window.

This is deliberately not implemented. Measure first.

---

## Final checklist

| Item | Status |
|---|---|
| Compiles | **UNKNOWN — not compiled** |
| 14 d run | **NOT RUN** |
| 90 d run | **NOT RUN** |
| 180 d run | **NOT RUN** |
| 1 y run | **NOT RUN** |
| Measured time | **NOT RUN** |
| Full History (no artificial cut) | **YES** — no `historyDays`, `historyStartTime`, `inEngineWindow`, `bootstrapDays`, `bootstrapDistance` or `calc_bars_count` anywhere in either file |
| Logic tests | P1–P8 **STATIC**, P9–P11 **NOT RUN** |
| Remaining spec gaps | section 0.1 (documents unavailable), section C (tie-break residual), section B (state indexes not built) |
| Storage pruning | unchanged limits, unchanged protection rules; **occurrence over a year NOT MEASURED** |
| Touch history truncation | mechanism unchanged; **occurrence over a year NOT MEASURED** |

**This is not a completed deliverable.** Per the instruction's own standard,
completion requires the compile, the 14-day parity against the Visual Harness,
and the 1-year run. Paste compile errors and the first Debug table and the work
continues from there.
