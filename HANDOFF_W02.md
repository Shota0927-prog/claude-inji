# HANDOFF_W02

## 1. Window 02 status

**IMPLEMENTATION COMPLETE** — TradingView compile error = 0。

Batch 1〜52（＋修復 Batch 36R / 39R）をすべて外部監査 PASS ＋ TradingView compile gate 通過で完了。
Window 02 の担当範囲（SoA / Registry / Revision / Index の physical foundation）に未実装の残件はない。
business / runtime logic は本 Window の担当外であり、§7 に owning Window への引き渡しとして明記する。

## 2. Production artifact

- file `ZoneEngineV2_Rebuild.pine`（5102 行 / 315,599 bytes / `//@version=6`）
- library `ZoneEngineV2_Rebuild` / `buildId()` = `"ZoneEngineV2_Rebuild_Strict20sV3"`
- 最終 commit `bc79091`（branch `claude/laughing-dijkstra-3w3zgr`）
- SHA-256
  - **`5e4296ca0cbb1fe793dc6a1b727e3b6a9ebf1ed32fb522420fc52a0cee2258da`** — リポジトリ実体（末尾改行あり）。`git show bc79091:ZoneEngineV2_Rebuild.pine` と working tree の両方で一致。W03 はこちらを正本ハッシュとする。
  - `4de4e89a3302aab88153d66593093d759eeb1080513474fa85d613cc005ea180` — 同一内容から**末尾改行を除いた**バイト列のハッシュ（エディタ / TradingView へ貼り付けた本文をそのまま hash した場合の値）。内容差分は 0。

最終 count：

| 項目 | 値 |
|---|---|
| ZoneEngine field | **209** |
| W02AuxStore field | **129** |
| internal function | **39** |
| Public API function | **19** |
| export total | **26**（export type 7 ＋ API function 19） |

`W02AuxStore` は Pine の CE10116（`ZoneEngine.new` external elements 上限 254）回避のために Batch 36R で導入した **Engine-owned singleton storage container**。export type なのは「export type が非 export type を field に持てない」という Pine 制約への対応であり、business API ではない。中身は parallel array / SoA / flat storage のみで、per-Root / per-Core / per-Side の object registry ではない。

## 3. W01 から凍結維持したもの（W02 で変更 0）

- **Public API 19本**：`newCfg` / `validateCfg` / `newEngine` / `newFeed` / `updateConfirmed5m` / `viewCount` / `viewAt` / `eventCount` / `eventAt` / `rootCount` / `rootAt` / `configErrorCode` / `buildId` / `categoryName` / `sideName` / `phaseName` / `gradeName` / `densityName` / `eventName`。signature 変更 0、overload / 別名 / 追加 0。
- **enum / constants**：Category / Side / Phase / Grade / Density / Root state / FVG mask / Weak / Event / TF / EMA / error code。新規 enum・新規 mask・新規 sentinel の追加 0。
- **ZoneCfg**（59 field）／**Feed**（18）／**Root**（20）／**ZoneView**（27）／**ZoneEvent**（12）：field の追加・削除・rename・型変更 0。
- **Stage A〜L の順序**：変更 0。
- **`updateConfirmed5m` mutation 入口**：変更 0（W02 の全 Batch を通じて diff 内出現 0）。

`ZoneEngine` のみ 83 → 209 field（W02 の physical storage 追加）、`W02AuxStore` を 1 type 追加（export total 25 → 26）。

## 4. Window 02 で完成した physical foundations

### 4.1 registry core

- Root SoA 23 / Core SoA 8 / Side SoA 26（flattened、`sideSlot = coreSlot * 2 + sideIndex`）
- Root / Core free-slot lifecycle（LIFO free stack、physical slot 再利用、配列は縮めない）
- Root ID → rootSlot（I11-1）／Core ID → coreSlot（I11-8）
- live collection と ID 昇順 order（`rootLiveSlots` / `rootIdOrderSlots` / `coreLiveSlots` / `coreIdOrderSlots`）
- 17 independent revisions（I9、storage のみ・increment 0）

### 4.2 I11 required index 13/13 — physical foundation 完成

| # | index | 実体 |
|---|---|---|
| 1 | Root ID → slot | `rootIdToSlot`（map、live key only） |
| 2 | origin identity → slot | originKey bucket head map ＋ 双方向 chain ＋ expectedRootId（Batch 42） |
| 3 | live Root price order | `rootPriceOrderSlots` ＋ `rootPriceOrderPositions`（Batch 32） |
| 4 | Category / TF / state sets | 各6 set ＋ 3 reverse positions（Batch 15–17） |
| 5 | Accum pair | upper / lower pair map（Batch 18） |
| 6 | FVG direction / TF / state / Fresh / Inverse | 非価格 11 set ＋ 4 reverse positions ＋ NativeRange interval order 2本 ＋ 2 reverse positions（Batch 19–22） |
| 7 | Root → participating Core/Side | flat edge pool ＋ Root 側 head / count、atomic add / detach / detach-all、Root free・Core free へ接続済み（Batch 23–31） |
| 8 | Core ID → slot | `coreIdToSlot` |
| 9 | Core / Side Phase sets | 6 Phase set ＋ `sidePhaseSetPositions`、Core lifecycle 接続済み（Batch 13–14） |
| 10 | Armed EffectiveRange price index | bottom / top order ＋ 2 reverse positions（Batch 33） |
| 11 | Break / Flip / Reclaim / Inverse-wait threshold index | Broken / Flip frozen-snapshot bottom・top order ＋ 4 reverse positions（Batch 34）。Reclaim は Broken 側を共有。Inverse待ちは **専用 order を持たず** InverseWait state set ＋ FVG NativeRange price index の composition（Batch 35） |
| 12 | Dormant recovery index | bottom / top order ＋ 2 reverse positions（Batch 33） |
| 13 | prune queues | Root 4 category heap SoA ＋ `rootPruneRevisions`（Batch 36 / 36R）、Dormant Core heap SoA ＋ `corePruneRevisions`（Batch 37） |

### 4.3 pool / ring / scratch

- Candidate scratch 4 regions（Support/Resistance × old/new、logical length 方式、`array.clear` 不使用）
- TouchMark per-Core ring（`blockBase = coreSlot * touchMarkCapacityPerCore`、logical chronology `(head + i) % capacity`、append / physical-index helper 実装済み）
- current-bar Event pool（12 array ＋ `eventLogicalCount`、`eventAppendRaw` 実装済み）
- EndedGeneration ring foundation（Engine-global 1本、payload 7 array ＋ head / count scalar、Batch 50）
- Root / Core prune queue foundation（stale entry は ID ＋ revision ＋ snapshot 照合、線形削除しない設計）

### 4.4 logical-state physical foundations

- TouchStartSnapshot scalar 18（per Side、Core lifecycle 接続済み）
- TouchStartSnapshot **独立** Root copy（per-Side head/tail/count ＋ flat linked node pool ＋ free stack ＋ raw reset/alloc/free）
- BreakSnapshot scalar 11（per Side、Core lifecycle 接続済み、fixed-range contract 記載）
- BreakSnapshot **独立** Root copy（同構造・別 pool ＋ raw reset/alloc/free）
- Side current valid Root ID list（A6.7、per Side、第3の独立 pool）
- Zone origin Root ID set（A6.8、**per Core**、第4の独立 pool）
- PendingTopology 存在 flag / PendingGeneration 存在 flag（per Core、Batch 48）
- PendingTopology **multi-child** 独立 Root-copy storage（`Core → 0..N child → 各 child が独立 Root ID list`、child pool ＋ Root node pool ＋ 2 free stack、Batch 52）
- per-Side Core FVG diagnostics 4（Batch 51）
- Root float ＋ comparison tick write foundation（`rootWritePricesAndTicksRaw`、Batch 49）

いずれも **real membership / real row = 0**、`valid = true` / `live = true` の書込 0。Production call site を持たない raw foundation。

## 5. 重要な不変条件（後続 Window で維持必須）

1. Root ID / Core ID / Generation ID は **1-based、0 = none、never reuse**（D02）。
2. 再利用されるのは **slot のみ**（`SLOT_INVALID = -1`）。slot は identity ではない。
3. `sideSlot = coreSlot * 2 + sideIndex`（0 = Support、1 = Resistance）。
4. Support / Resistance で physical Core を二重生成しない。1 physical Core = 1 coreSlot（I6.3）。
5. Root ID と rootSlot を混同しない。stale 参照は `expectedRootId` / `expectedCoreId`（＋文脈により Generation ID / breakSeq / TouchNo）で照合する。Generation ID は ownership token ではない。
6. 元の float 価格を保持し、追加丸めをしない（I6.4）。
7. 比較用 tick = `round(price / mintick)`。na price → `int(na)`（0 tick へ落とさない）。比較時のみ tick を使う。
8. Snapshot / PendingTopology の Root copy は **独立**。他 pool・他 Snapshot・Candidate scratch と array も free stack も共有しない（I6.1）。
9. Candidate scratch を採用済み state の storage として流用しない（I17.1）。
10. `array.remove(0)` / `array.shift` / `array.unshift` / `array.clear` / `array.sort` を Production で使わない（実測：非コメント出現 0）。
11. Production で `request.*` 禁止（非コメント出現 0）。
12. Production で box / line / label / table 禁止（非コメント出現 0）。
13. nested collection（`array<array<...>>` / `map<int, array<int>>`）と per-object UDT registry（`array<Root>` / `array<Core>` / `array<Side>`）禁止（実測 0）。
14. 全 mutation は preflight → single commit path。検証に失敗したら **partial mutation 0・修復 0**。live flag は add の最後、row の解放は detach の最後。
15. `ZoneEngine.new` の external elements 上限（254）。新しい W02 系 auxiliary storage は原則 `W02AuxStore` 配下へ追加する。

## 6. 未解決事項 — NOT_FIXED / 発明禁止

以下は**現行正本で未固定**。後続 Window でも正本なしに勝手に固定してはならない。

1. **full origin tuple の完全 field 列挙**（category / tf / originTime / originEndTime / boundary subtype / direction ほか）と full comparator。originKey は coarse bucket / prefilter であり identity proof ではない。
2. **価格順の equal-tick stable tie-break**（Root price order・FVG NativeRange order・Armed / Dormant / Broken / Flip price index すべて）。
3. **PendingGeneration の完全 payload**（candidate range / Side / mask / reference price / Root IDs / reset distance / re-approach threshold / base range / armed state ほか）。
4. **PendingTopology の完全 Candidate scalar payload**（Side / stage / effective bottom・top / reference price / cCount / hCount / density / baseStrong / broad / FVG 各情報 / createdTime / minRootId / psych tick ほか）。
5. **EndedGeneration の完全 canonical payload**。現在の 7 field は既存 v2 互換 diagnostic record であり canonical とは主張しない。
6. **FVG `structuralStateMask` の bit layout**（Active / Invalidated / InverseWait / InverseActive への bit 割当）。

参考として、W02 が **Q0 physical choice として固定した**もの（正本は logical requirement のみ固定）：I11-2 の originKey bucket、I11-3 の bottom/top order 方式、I11-10 / I11-11 / I11-12 の bottom/top order ＋ reverse position、I11-13 の category 別 priority heap SoA、A6.5 / A6.6 / A6.7 / A6.8 / I6.1 の flat linked node pool。いずれも「物理表現の選択」であり、logical 仕様の上書きではない。

## 7. 後続 Window へ引き渡すもの（W02 欠落ではない）

business / runtime owning Window が実装する：

- Source / Root generation
- full origin tuple fields 確定と full comparator、origin bucket の actual membership
- Root price order の actual insert / detach / reinsert、equal-price stable tie-break
- Category / TF / state の actual membership
- Accum の actual registration
- FVG の actual membership / Fresh / structural / Inverse logic
- Candidate evaluation
- Core association / Merge / Split
- Phase transition
- Armed / Touch / Weak
- Break / Flip / Reclaim
- Dormant runtime
- prune heap operations / protection / Stage K execution
- Snapshot の actual capture / copy
- PendingTopology child lifecycle / Candidate scalar / plan creation・refresh・apply
- PendingGeneration candidate payload / transition
- EndedGeneration append / read / overwrite
- FVG diagnostic calculation
- ZoneView deferred diagnostics の接続（`fvgDirectionMask` / `fvgRootCount` / `fvgFreshCount` / `fvgStructuralStateMask` / `rootCountInView` / `categoryMask` / `highMask` — W01 で field として存在、W02 では `viewAt` に未接続）
- I9 revision の increment / invalidation wiring

### 7.1 接続順序の必須注意（W02 コメントにも記載済み）

real membership / real row を作り始める **前に**、以下の clear / detach を必ず lifecycle へ先行接続すること。後から足すと Core / Root free が孤児を残す。

- TouchStartSnapshot Root copy：Snapshot clear → `coreResetSlotRaw`
- BreakSnapshot Root copy：BreakSnapshot clear → `coreResetSlotRaw`
- Side current valid Root list：clear / detach → `coreResetSlotRaw`
- Zone origin Root set：clear / detach → `coreResetSlotRaw`
- PendingTopology child ＋ Root node：detach-clear → `coreResetSlotRaw` と Core free path
- Root price order・origin bucket：detach → `rootFreeSlotRaw`（participation は Batch 29 / 31 で接続済み、同じ形で）

## 8. compile history

Batch 1〜52 の各 compile gate を通過（Batch ごとに TradingView 実機 compile → error 0 を確認してから次 Batch へ進む運用）。
compile error が出たのは 1 回のみ：Batch 36 の **CE10116**（`ZoneEngine.new` external elements 259 > 254）。Batch 36R で `W02AuxStore` へ physical grouping し解消（logical 変更 0）。
comment 精度修正のみの修復 Batch：36R（併せて）、39R。
最終 Batch 52 も TradingView error 0。

## 9. 次 Window

**Window 03** へ進む。

W03 開始時の正本入力：

1. `HANDOFF_W02.md`（本ファイル）
2. `ZoneEngineV2_Rebuild.pine`（commit `bc79091` / SHA-256 `5e4296ca0cbb1fe793dc6a1b727e3b6a9ebf1ed32fb522420fc52a0cee2258da`）

加えて、W01 の凍結契約は `HANDOFF_W01.md` が引き続き有効。
