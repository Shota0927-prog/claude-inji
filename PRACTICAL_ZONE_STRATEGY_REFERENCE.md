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
