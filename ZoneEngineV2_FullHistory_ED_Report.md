# ZoneEngineV2_FullHistory_ED — Report

Build: `ZEV2-FULLHIST-ED-GUARD-20260920`

| Deliverable | Lines | Status |
|---|---|---|
| `ZoneEngineV2_FullHistory_ED.pine` | 4,651 | written, **not compiled** |
| `ZoneEngineV2_FullHistory_ED_VisualHarness.pine` | 403 | written, **not compiled** |
| `ZoneEngineV2_FullHistory_ED_Report.md` | this file | — |

Untouched: `ZoneEngineV2_Rebuild.pine`, `ZoneEngineV2_VisualHarness.pine`,
`Zone_Strategy_StrongBounce.pine`, `Zone_StrongReflection_Strategy_Long.pine`.

---

## 0. Read first

### 0.1 Nothing has been executed

There is no TradingView runtime here. The section 34 report below is therefore
a **template with every field unmeasured**. Per the instruction's own rule —
"1年Full History・40秒エラーなしを確認できるまでは完成と報告しないでください" —
**this is not reported as complete.**

### 0.2 The specification documents are still unavailable

`Zone_definition_spec_v2` and
`Claude_ZoneEngine_v2_lightweight_implementation_instructions` are not in this
session or the repository. Mismatches beyond those named in the previous
instruction's section 22 remain undetectable.

### 0.3 Priority order followed exactly

1. 40-second limit
2. Touch / Weak / Break / Generation history accuracy
3. Zone definition preserved
4. Continuous-EMA width tie-break is the one accepted compromise

No step was reordered, no "for exactness" per-bar scan was added.

---

## A. Architecture

```
confirmed 5m Base bar
  │
  ├─ EMA update            O(1) guard test per EMA Root. No scan.
  ├─ generationWatchSlots   generation re-approach (before any Touch)
  ├─ armedSupportSlots      Touch / GapBreak, support
  ├─ armedResistanceSlots   Touch / GapBreak, resistance
  ├─ activeTouchSlots       running episodes
  ├─ freshFvgSlots          Fresh only
  ├─ inverseWaitSlots       Inverse only
  ├─ brokenFlipWaitSlots    Break / Flip / Reclaim
  ├─ pendingTopoSlots       deferred topology flush
  ├─ waitingSlots           Arm / Dormant refresh
  └─ dormantSlots           SKIPPED unless the bar reaches the aggregate corridor
```

`liveCoreSlots` is **not iterated on a Fast Path bar**. The Slow Path is entered
only from the fixed list in section 15 of the instruction, and only then may the
Core or Root registry be walked.

---

## B. Indexes

| Index | Purpose |
|---|---|
| `armedSupportSlots`, `armedResistanceSlots` | the only Cores searched for a Touch or GapBreak |
| `activeTouchSlots` | the only Cores with a running episode |
| `brokenFlipWaitSlots` | the only Cores in Break / FlipWait |
| `generationWatchSlots` | the only Cores with a generation candidate |
| `pendingTopoSlots` | the only Cores holding deferred topology |
| `waitingSlots` | quiet Cores that still need the cheap Arm / Dormant refresh |
| `dormantSlots` | parked Cores, behind the aggregate wake corridor |
| `inverseWaitSlots`, `freshFvgSlots` | FVG state sets; no full FVG walk per bar |
| `ema2000CoreSlots`, `ema3000CoreSlots` | EMA → Core reverse index (section 6) |
| `pointPriceIndex` | price-sorted point Roots, for Slow Path band queries |
| `swingSlots`, `accumSlots`, `timeSlots`, `fvgSlots` | category-local, for source events |
| `dirtyBottoms` / `dirtyTops` | disjoint dirty bands, never merged into one min..max |

Membership is a **flag on the Core** (`inArmedSup`, `inActiveSet`, …), so
`f_syncCoreSets` decides add/remove without searching and is idempotent. Every
set is written only through `f_setAddRemove`; there is not one direct push.

Safety net: at the end of every Slow Path the sets are re-synced from
`liveCoreSlots`. A Slow Path is permitted to walk the registry, so this costs
nothing on a normal bar and guarantees the sets cannot drift.

### Dormant (section 19)

Entering Dormant stores `dormantWakeLow` / `dormantWakeHigh`. The engine keeps
an aggregate: the nearest corridor edge below and above the reference price.
While `[baseLow, baseHigh]` stays strictly between them, **no Dormant Core is
touched at all**. Only on a breach is the Dormant set walked and the aggregate
rebuilt.

---

## C. EMA Topology Guard — the central change

### Normal bar, per EMA Root, O(1)

```
newEMA > emaGuardLow  and  newEMA < emaGuardHigh  and  newSlope == emaGuardSlopeSign
```

All three true →

```
Topology rebuild = 0
Candidate search = 0
FVG scan        = 0
Root scan       = 0
Core scan       = 0
```

Only the price fields update, plus the Cores listed in the EMA reverse index.
Comparison is strict, so reaching a boundary breaches (safe side, mintick
based).

The previous build's `f_maMoveChangesRelationships` — which walked point Roots,
psych levels, all FVGs and all Cores on every EMA move — is **deleted**, along
with `f_maLocalCoreUpdate` and the now-unused `f_updatePointRoot`,
`f_coreIdleDormant` and `f_barNearCore`.

### Guard construction — Slow Path only

Critical boundaries, exactly as specified in section 3, folded as
`{b, b±M, b±DenseWidth}`:

* every point Root within `EMA ± 3M`, including the other EMA
* the two psych levels `floor(EMA/50)*50` and `ceil(EMA/50)*50` — **derived, not
  scanned across the price range**
* every FVG whose NativeRange (padded by M) reaches the window; folding both
  `nativeBottom` and `nativeTop` covers the proximal edge of either Side

`emaGuardLow` = nearest boundary below, `emaGuardHigh` = nearest boundary above.
With nothing inside `3M`, the fallback is `EMA ± 2M`, which is provably safe: a
Root further than `3M` cannot come within `M` or `DenseWidth` of a point `2M`
away. An EMA sitting exactly on a boundary gets `[EMA, EMA]`, so any move
breaches.

### The one accepted compromise (section 5)

While the guard holds, participating Roots, C, H, Density class, FVG
participation and MA slope quality are all unchanged, so the winner cannot move
for any structural reason. What the EMA still shifts is a candidate's **width**.
Two candidates with identical C and identical H can therefore swap the
"narrower wins" tie-break without the guard noticing:

```
Candidate A width 7.8 → 8.1
Candidate B width 8.0 → 7.9
```

This is **not tracked** until the next guard event. It is deliberate, it is the
only intentional inexactness in the build, and no per-bar competitor evaluation
was added to close it.

Per section 32, full-Zone equality between `maFastPath` ON and OFF is **not** an
acceptance criterion. What must match: M crossing, Dense crossing, Root
join/leave, C, H, Density, slope quality, FVG participation state, and the
Touch / Weak / Break / Generation history.

---

## D. Logic fixes carried forward and extended

All eight fixes from the previous instruction are retained (`FIX 22.x` markers
in the source): Time H/L same-origin merge; Reclaim without `movedAway`;
LiveStructure separate from TouchStartSnapshot; PendingTopology flushed on both
Reset and Break; Merge/Split deferred during ActiveTouch; Merge/Split history
rebuilt from TouchMarks; generation switched before the Touch is counted;
Inverse FVG not advanced on its invalidation bar.

Three additions from this instruction:

| § | Change |
|---|---|
| 29 | `generationCandidateSide` is stored. On the re-approach bar **only that Side** is armed from the current bar and takes Touch 1; the opposite Side stays Waiting. Previously both Sides were armed. |
| 30 | `TouchMark` now carries `episodeWeakByDepth` and `episodeMaxDepthPct`. Sealing writes **the episode's own result** (`touchSnapshot.maxDepthPct` and whether it crossed `weakDepthPct`), never the cumulative SideHistory. Merge/Split rebuild Weak history from inherited marks only. |
| 31 | Truncation is per Core and per Side: `SideHistory.historyIncomplete`. Core A losing a TouchMark no longer makes Core B's history look incomplete. Engine-wide `touchHistoryTruncated` is diagnostic only. |

---

## E. Source requests

Six contexts, one request each, **no `calc_bars_count` anywhere**: chart 5m
Swing (native), 1m MAPack, 15m SwingPack, 1H TFPack, 4H TFPack, 1D TFPack. All
`gaps_off` + `lookahead_off`. The section 21 revision/time gates are unchanged,
so one confirmed source bar is consumed exactly once.

**The horizon limit is unchanged and is not an engine problem.** MA is defined on
1m; a 5m chart covering a year needs roughly 360,000 1m bars, which TradingView
does not serve. Beyond that depth `ma1m` is `na` and the oldest bars carry no MA
Roots. Section 3.3 forbids shortening the request, so the options are to accept
the horizon the 1m context reaches, or to host on a 1m chart with native
`maPackV2()` and a 5m Base — the structure already proven in
`Zone_StrongReflection_Strategy_Long.pine`. Neither changes Zone logic.

---

## F. Section 34 report — TO BE FILLED BY A RUN

```
Compile: NOT RUN

14d:  NOT RUN
30d:  NOT RUN
90d:  NOT RUN
180d: NOT RUN
1y:   NOT RUN

1y 40-second error: NOT RUN

FastPath %:  NOT RUN
No-op %:     NOT RUN
SlowPath %:  NOT RUN

EMA Guard hit count:    NOT RUN
EMA Guard breach count: NOT RUN

Candidate rebuild count: NOT RUN
Root full scan count:    NOT RUN
Core full scan count:    NOT RUN
FVG full scan count:     NOT RUN

Storage prune:            NOT RUN
Touch history truncation: NOT RUN

Known accepted compromise:
Continuous EMA width tie-break only
```

Every field above is a row in the harness Debug table. Enable Debug, read them
off the last bar, and paste them back.

Run order (section 25, do not change): 14d → 30d → 90d → 180d → 1y. Profiler is
allowed at 30d. **1y must be run with the Profiler OFF.**

### What the design predicts

`emaGuardBreaches` should be a small fraction of `baseBarsProcessed`; each
breach is one Slow Path. If breaches are frequent, the EMAs are sitting inside a
dense boundary field and the guard interval is narrow — which is information,
not a bug, and section 26's remedy order applies.

---

## G. Counters

Exported and written only when `cfg.countersOn` (tied to the Debug checkbox, so
a production run pays nothing):

`baseBarsProcessed`, `fastPathBars`, `slowPathBars`, `noOpBars`, `slowPathPct`,
`noOpPct`, `emaGuardHits`, `emaGuardBreaches`, `candidateRebuildCount`,
`candidateWindowEvalCount`, `rootFullScanCount`, `coreFullScanCount`,
`fvgFullScanCount`, `dirtyBandCount`, `maxDirtyBandWidth`, `mergeEvalCount`,
`splitEvalCount`, `referenceCalcCount`, `maFastUpdates`, `maSlowUpdates`,
`maxLiveRoots`, `maxLiveCores`, plus the live set sizes
(`armedSetSize`, `activeTouchSetSize`, `breakFlipSetSize`,
`generationWatchSetSize`, `dormantSetSize`, `waitingSetSize`).

`arrayAllocDiagnosticCount` is still not implemented: Pine has no allocation
hook, and a hand-counted number would be a claim, not a measurement.

---

## H. Static verification performed

Machine-checked on the source, not on a run:

| Check | Result |
|---|---|
| No direct push into any state set (all go through `f_setAddRemove`) | 0 violations |
| `liveCoreSlots` iterated only in: Slow Path resync, `f_collectLocalCoreSlots`, `f_rebuildEmaCoreIndex`, `f_refreshLiveEligibility`, `f_refreshFvgFreshViews`, `f_rootReferenced`, storage pruning, read-only view API | confirmed |
| `for i = 0 to array.size(e.roots)-1` reachable only from storage pruning | confirmed |
| EMA update path contains no array loop when the guard holds | confirmed by reading `f_updateMaRoot`; the only loop is the reverse-index Core update, which is the specified section 6/7 behaviour |
| Tabs / trailing whitespace / indent anomalies | 0 |
| Dead code removed (`f_maMoveChangesRelationships`, `f_maLocalCoreUpdate`, `f_updatePointRoot`, `f_coreIdleDormant`, `f_barNearCore`) | confirmed |

Acceptance tests P1–P11 from the previous round: **NOT RUN.**

---

## I. Remaining issues, stated rather than worked around

1. **Not compiled.** Highest-risk new code, in order: `f_syncCoreSets` (eight
   flag/set pairs that must stay consistent), the snapshot-then-iterate pattern
   in `f_processExistingState` / `f_processPostRootTransitions`,
   `f_rebuildDormantGuard`, and `f_buildEmaGuard`.
2. **Set-drift risk.** The design relies on `f_syncCoreSets` being called after
   every phase change. The Slow Path resync limits any drift to at most the
   bars between two Slow Paths, but it does not prevent it. If a Zone ever looks
   frozen, compare `armedSetSize` against `phaseCount(engine, 2)`; a mismatch
   is the signature.
3. **The section 5 compromise** is real and unbounded in the sense that it
   persists until the next guard event.
4. **1m source depth** still caps a 5m-hosted year. Section E.
5. **Storage prune / touch truncation over a year: unknown.** Limits are
   unchanged, as required. If `touchHistoryTruncated` turns true often,
   Merge/Split history falls back per Side to the parent aggregate; that is now
   isolated per Core/Side (section 31) but is still a loss of precision. Raising
   `maxTouchMarksPerCore` would be a specification change and is **not** made
   here.
6. **`arrayAllocDiagnosticCount`** not implemented. Section G.

Per section 33, none of these was resolved by shortening history, by disabling a
category, by changing a storage limit, or by adding an unspecified cache.

---

## J. If 1 year exceeds 40 seconds

Follow section 26's order, using the counters:

| Priority | Question | Counter |
|---|---|---|
| 1 | any per-bar full Core walk left? | `coreFullScanCount` vs `baseBarsProcessed` |
| 2 | any per-bar full FVG walk left? | `fvgFullScanCount` vs `baseBarsProcessed` |
| 3 | any array loop inside the EMA Fast Path? | `emaGuardHits` high while time is high |
| 4 | Candidate / Reference / allocation on a Fast Path bar? | `candidateRebuildCount`, `referenceCalcCount` vs `slowPathBars` |
| 5 | Slow Path candidate search itself | `candidateWindowEvalCount`, `maxDirtyBandWidth` |

Do not shorten history. Do not disable a category. Report the numbers and the
work continues from there.
