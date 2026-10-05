# Practical Zone Strategy — Reference Production (P14)

Status: **REFERENCE_PRODUCTION_COMPLETE**

The LONG and SHORT production strategies at Reference HEAD `acd12ac` are the
fixed functional baseline. Any later performance work (P15+) must reproduce
these files' behaviour exactly.

## Reference files

| File | Lines | sha256 |
|---|---|---|
| `PracticalZoneStrategy_LONG.pine` | 2486 | `8bffaf07bc500487e88f3fe75c28335ac31a18e70ebd72f26011faafa57cdf2d` |
| `PracticalZoneStrategy_SHORT.pine` | 2488 | `faf3b7352a2d6928e3857cf1b4779fa68fafda4bd39fd1170a6d441c79ac5f40` |

Libraries (imported by TradingView version, sources in this repo):

| Import | Repo source sha256 |
|---|---|
| `sekine3310/ZoneEnginePractical/3 as zn` | `ZoneEnginePractical.pine` `d3309c56…52ef21` |
| `sekine3310/SignalEnginePractical/1 as sg` | `SignalEnginePractical.pine` `51be8af7…08508f` |

## TradingView reference (external gate)

Recorded from the user's TradingView run. Python does not compute or verify these numbers.

- XAUUSD 5M, Last 365 days, Deep Backtest, after P13A (`acd12ac`)
- LONG: **46 trades**
- SHORT: **59 trades**
- Compile PASS, no RE10110, no Calculation Error.
- Trade counts were unchanged before and after P13A.

## Known issue

- TradingView shows a **Heavy Script** warning. It is a performance warning, not a runtime error, so it does not block the Reference. It is handled in P15.

## Fixed specification (audited in P14, `fixture_p14_final_audit`)

| # | Item | LONG | SHORT |
|---|---|---|---|
| 1-2 | Direction | `strategy.long` only, `strategy.short` = 0 | `strategy.short` only, `strategy.long` = 0 |
| 3 | 8 Logic | FVG15 / FVG / FVGABS15 / FVGABS5 / ZONEREBOUND / ZONEFAKE / ZONERETEST / ZONEBREAK | same |
| 4 | Priority | FVG15 > FVG > ABS15 > ABS5 > RB > Fake > Retest > Break | same |
| 5 | Position | Global 1-position (`position_size` / `opentrades` scalars) + `enteredThisBar` | same |
| 6 | Inside Any Zone | strength >= activeNoTradeMinStrength and bottom <= entry <= top, state ignored | same |
| 7-9 | TradePlan | `zn.buildPlanWithTpDepth` (Structural SL/TP, Fallback RR), TP Mode PASS→FAIL only | same |
| 10 | Risk / Qty | old Main `f_qty`, qtyMin gate | same |
| 11 | Break Even | measured from fill price, logic-specific trigger, irreversible, SL → fill price, entry-time TP kept | Short: fill − trigger; ZONEBREAK Short uses `zoneBreakEvenTrigger` |
| 12 | Provisional Alert | default OFF, priority winner only, `freq_once_per_bar`, 8 varip slots | same |
| 13 | Confirmed Alert | default ON, fired only in the real `strategy.entry` branch, `freq_all` | same |
| 14-15 | Excluded | Dynamic TP = 0; no BE / TP-change / SL-change / Exit alert | same |
| 16 | Zone Signal Min Strength | default Strong | same |
| 17 | Zone snapshot | SUPPORT (+1) and RESISTANCE (−1) | same |
| 18-20 | originTrackId / entryTouchCount | recorded only on a Zone 4Logic real entry, using the touch count at entry time; never used as an entry condition; FVG entries = na | same |
| 21-24 | Excluded code | probe / harness = 0, drawing = 0, map trade management = 0, opentrades / closedtrades loops = 0 | same |
| 25 | Imports | ZoneEnginePractical/3, SignalEnginePractical/1 | same |

Both files are direction-isolated. The SignalEngine shared state for the other
direction is kept on purpose: triggers, Accum direction, the Zone event roles on
both sides, and the ABS event.

## Requests / allocation (Reference state)

- `request.*` call sites: 31 per file.
- Requests issued with default inputs: `request.security` 19 + `request.security_lower_tf` 2.
  - Zone 7: MA 1M, Swing 5 / 15 / 60, Accum 60 / 240 / D.
  - Environment 5: 4H / 1H / 15M / 5M / 1M.
  - FVG env 5M 1, FVG15 15M 1, ABS 5M + 15M 2, Daily 2, Accum15 1.
  - `lower_tf`: ABS 1M BOS 1, Zone 1M pack 1.
- Per-bar `array.new` = 0.
- Input-only configs are `var`.
- Provisional slots = 8 (varip).
- Per-bar UDTs that remain (series data): Feeds, Signals, `ZoneFeed`, `ZoneEnvFeed`, `DispatchStat`.

## P15 performance optimization candidates (not started)

1. Merge the two 1M `request.security_lower_tf` calls (ABS `bosPack` + Zone `zoneTfPack`) into one tuple request.
2. Pack requests that share a timeframe:
   - "D": `drDailyTuple` + `dailyRangeMedian`, but their lookahead differs, so this needs care.
   - 15M: FVG15 `efvgRebound15Pack` + ABS15 `efvgAbsConfirmed` + Accum15.
   - 5M: env5M + FVG env 5M + ABS5.
3. Compute the 5M (chart TF) requests locally instead of through `request.security`. This needs a parity proof for confirmed / lookahead semantics.
4. Remove the duplicated `updateFvg()` (FVG15 base runs a second full `updateFvg`).
5. Replace the O(Z·R) Zone role lookup in `updateZoneEvents` (library change → SignalEnginePractical/2).
6. Early-gate the env 5M / 1M requests when `reqTrend5M` / `reqTrend1M` are OFF (only the 4H/1H/15M envs are needed for Zone).
7. Reduce the remaining per-bar UDT constructions (FvgFeed copy, the default Signal objects).

Every P15 change must keep the TradingView reference (LONG 46 / SHORT 59) and pass the existing fixtures.

## Fixtures

- `python3 tests/practical_strategy_sim.py` → 709/709. Covers P01–P14; P11/P12 integration checks are pinned to `e3680f5`, and the current files are tied to it by the P13A exact-transform check.
- `python3 tests/practical_zone_sim.py` → 44/44.
- Evidence class: PINE_NOT_VERIFIED (static / mirror checks). The TradingView gate is external.

---

## P15 — Performance optimization (candidate; awaiting the single TradingView gate)

The Reference stays `acd12ac` (LONG 46 / SHORT 59). The P15 files are derived from it
by `p15_transform()` in `tests/practical_strategy_sim.py`; fixture P15-00 proves
`current == p15_transform(acd12ac)` exactly. Library sources are unchanged:
SignalEnginePractical/1 and ZoneEnginePractical/3 are still the imports.

Every optimization has an input switch in group "99 · P15 Performance". All switches
default to ON. Turning a switch OFF restores the Reference request path for that item.
If the TradingView trade counts differ, turn the switches OFF one by one to isolate the
cause.

| # | Result | What |
|---|---|---|
| O1 | PASS | ABS 1M BOS (`bosPack`) and Zone precise-TF (`zoneTfPack`) are fetched with one `security_lower_tf` call. Applies only when both are active, the zone TF is lower than the chart and `triggerTF == zoneBosTf`. |
| O2 | PASS | Requests whose TF equals the chart TF are evaluated locally: Zone swing #1 `pivotPack`, FVG env 5M `efvgReboundConfirmed`, ABS5 `efvgAbsConfirmed`, env5M `envTrend`. Each uses the same expression with the same arguments. |
| O3 | PASS | An env TF is requested only if its result can be read. updateFvg reads an env TF only when its `reqTrend` is not OFF; Zone reads only 4H / 1H / 15M. With defaults, env5M and env1M are not requested. |
| O4 | PASS (partial) | One 15M request (lookahead_on) carries env15M + FVG15 rebound + FVGABS15 + Accum15. One 60M request (lookahead_off) carries Zone swing #3 + Accum #1. Daily is not packed: the Zone accum D request runs before the Signal-section Daily request, and `dailyRangeMedian` uses a different lookahead. |
| O5 | SKIPPED_UNSAFE | De-duplicating the two `updateFvg()` calls means splitting a 628-line library function whose ta history must stay per engine. That is a library change with high risk to the FVG / FVG15 state. |
| O6 | PASS | The default Signal objects are shared (var, read-only). `DispatchStat` is a var whose 6 fields are reset every bar. The Feed objects stay per bar, because their fields are new series every bar. |
| O7 | PASS | Main side was audited: dead scalars were already removed in P13A, and no other result is computed and then never read. Library-internal candidates are deferred. |
| O8 | SKIPPED_UNSAFE | The Zone role lookup (O(Z·R)) is library-internal state (roleCycle / creation / cleanup timing). Equivalence cannot be proven without a library rewrite and republish. |

Default issued requests: `request.security` 19 → 10 and `security_lower_tf` 2 → 1, so the total goes from 21 to 11 (−47.6 %).
Removed defaults: env 5M, env 1M (a 1M-TF security), FVG env 5M, ABS5 5M, Zone swing 5M,
one 1M lower_tf, and 3 of the 4 15M requests plus 1 of the 2 60M zone requests (packed).

Per-bar UDT constructions in Main: 9 → 4. The 4 default Signal objects and the DispatchStat are now reused;
FvgFeed, its copy, ZoneEnvFeed and ZoneFeed remain.

Per-bar `array.new` = 0. The 3 input-only request Cfgs are var, and there are 8 provisional slots (unchanged).

SignalEngine call counts are unchanged: updateFvg 2, updateFvg15 1, updateFvgAbs 1, updateZoneEvents 1, zn.update 1.
Zone event complexity is unchanged, because O8 was skipped.

**TradingView gate (one time):**
- XAUUSD 5M, 365 days, Deep Backtest.
- LONG = 46 and SHORT = 59, with identical entries and exits.
- No RE10110 and no Calculation Error.
- Check whether the Heavy Script warning still appears.
