# HANDOFF_W01

## 1. Window 01 status
COMPLETE / TradingView compile verified (user実測) / Window 01未解決差分 0。

## 2. Normative sources
- 論理正本 `Zone_definition_spec_v2(5).md` SHA-256 `f0ada2d851477850aa3d65463056e0318434b0c362383d475d49f9f6e1049cd1`
- 実装正本 `貼り付けたマークダウン（1）(20260922-064602).md` SHA-256 `db5b1f7d980ecda6f07ea7522d4a4af4a3b7c57b8bcc8ddb2b84049791125c09`
- Window 01 instruction: `01_窓01_Config_PublicAPI_Types.md`（旧窓分割指示は不使用）

## 3. Production artifact
- file `ZoneEngineV2_Rebuild.pine`（964行, //@version=6）
- library `ZoneEngineV2_Rebuild` / `buildId()` = `"ZoneEngineV2_Rebuild_Strict20sV3"`
- SHA-256 `35a2daaaa67621aa1c73e8ec4cbb46219383b8eaebb7a18755a2d90995dee2bc`
- `indicator.pine` は変更・流用 0。

## 4. Frozen UDT contract（後続窓で変更禁止）
`ZoneCfg`59 / `Feed`18 / `Root`20 / `ZoneView`27 / `ZoneEvent`12 / `ZoneEngine`83 field。
Root は外部projection専用（`originKey`/`pairKey`はint、内部tick fieldは非公開）。ZoneView/ZoneEventにstring field 0。Pine v6制約によりUDT field defaultは全てリテラル（const参照不可）。

## 5. Frozen Public API（19本）
`newCfg()` / `validateCfg(ZoneCfg)` / `newEngine(ZoneCfg)` / `newFeed()` / `updateConfirmed5m(ZoneEngine,ZoneCfg,Feed)` / `viewCount(ZoneEngine)` / `viewAt(ZoneEngine,int)` / `eventCount(ZoneEngine)` / `eventAt(ZoneEngine,int)` / `rootCount(ZoneEngine)` / `rootAt(ZoneEngine,int)` / `configErrorCode(ZoneEngine)` / `buildId()` / `categoryName(int)` / `sideName(int)` / `phaseName(int)` / `gradeName(int)` / `densityName(int)` / `eventName(int)`。overload・別名・追加API 0。

## 6. Fixed enum / sentinel / error
ID 1開始・0=none・再利用禁止、slot invalid=-1、`baseSeq`未処理=-1、time未設定=na。
Category0-5(mask 1/2/4/8/16/32) / Side 1,-1,0 / Phase0-5 / Grade0-3 / Density0-2 / Root state0-5 / FVG0-2(mask OR,両立3) / Weak0-3 / Event1-15(0=none予約) / TF 1,5,15,60,240,1440 / EMA 2000・3000は定数。
error 0=OK,1=CHART_TF_NOT_5M,2=MINTICK_INVALID,3=FIXED_TF_METADATA,4=STRONG_UNLIMITED_CONFLICT,5=TOUCH_THRESHOLD_ORDER,6=FEED_METADATA_MISMATCH(Stage A専用)。name API未知値="UNKNOWN"。
Pineにbitwise演算子がないため mask は同値の2冪定数。

## 7. Engine physical layout
Root SoA 23本(20 contract + `rootPointTicks`/`rootNativeBottomTicks`/`rootNativeTopTicks`) / Core SoA 8本 / Side flattened SoA 26本（`sideSlot = coreSlot*2 + sideIndex`、0=Support,1=Resistance）/ 当該足Event SoA 12本、論理長は`eventLogicalCount`。per-object registry化禁止。float原価格とint tickを併存。`array.remove(0)` / `array.unshift()` 不使用。prune診断4値は永続（毎足reset禁止）。

## 8. Validation / fingerprint
`validateCfg`はCfg単体でcode 0-5のみ、判定順固定、最小code優先、自動補正なし。code 6は内部`validateFeedMetadata(cfg,feed)`のみが返し、`cfgErrorCode`/`configValid`へ保存しない。fingerprintはZoneCfg全59 fieldを固定順で畳み込み、seed/mult 2組で独立2本（A:16777619/1000003、B:987654323/31、mod 2^31-1、float×1e8、string=文字コード畳み込み）。変更時のみ再validation。Root/Core/Candidate identityへ流用禁止。

## 9. updateConfirmed5m contract
Stage A→L順序固定。Window 01実装：Stage A（fingerprint差分時のみ再validation→Cfg invalid reject→Feed metadata→未確定reject→`lastBaseSeq != -1`時のみ`baseSeq <=`/`baseCloseTime <=`でduplicate・past reject）、Stage B（`eventLogicalCount := 0`のみ、physical array clear禁止）、Stage C〜K（順序コメントのみのno-op）、Stage L（`lastBaseSeq`/`lastBaseCloseTime` commit→true）。reject時は必ずfalseでEvent・Base状態不変。運用中のEngine mutationは本関数のみ（`newEngine`はFactory初期化）。

## 10. Accessor contract
`rootCount`=`array.size(rootIds)`（filter禁止）、`rootAt`は同sizeが境界でfresh `Root.new`20 field。`eventCount`=`eventLogicalCount`、`eventAt`は同値が境界でfresh `ZoneEvent.new`12 field。`viewCount`=`array.size(coreIds)*2`、`viewAt`はSupport→Resistance順でfresh `ZoneView.new`、Side View範囲を使用（物理Core範囲で上書きしない）、`weakReason`は2 boolから4状態導出。範囲外は全て`runtime.error("INDEX_OUT_OF_RANGE")`（clamp/sentinel/na禁止）。全accessorはread-only。

## 11. Intentional deferred（未解決差分ではなく owner window 未実装）
- ZoneView 7 field `fvgDirectionMask`/`fvgRootCount`/`fvgFreshCount`/`fvgStructuralStateMask`/`rootCountInView`/`categoryMask`/`highMask` は現在 **0 sentinel＝最終値ではない**。Root membership・FVG集約backing state実装窓が**同じfieldへ正本値を接続すること**。
- Stage C〜K本体（Source検出、Root/Core/Candidate、Touch/Break/Flip/Inverse、Merge/Split/Generation、PendingTopology、Dormant、prune実処理、Event生成）。
- Feedの EMA / Swing / Accum / FVG / 時間高安 / 心理価格 / source確定時刻 field は窓03で正本I7に従い追加。

## 12. Compile history（TradingView compile error 0、全てユーザー実測）
Batch1 / Batch2(+fix: UDT default literal化) / Batch3 / Batch4(+fix: CE10237) / Batch5(+fix: bool na) / Batch6A / 6B / 6C / 6D / 6E / Batch7。

## 13. Not yet verified
付録B 75件 = NOT_VERIFIED / I22 Reference同値10件 = NOT_VERIFIED / 365日XAUUSD 5m benchmark×3 = LATER_WINDOW_GATE / Production ≤12秒・StrategyBenchmark ≤20秒・Visual ≤20秒 = LATER_WINDOW_GATE / Realtime・Bar Replay・reload同一性 = NOT_VERIFIED / 40秒runtime・500msループ・collection・history長期実測 = LATER_WINDOW_GATE。compile verified と runtime/benchmark verified は別物。

## 14. Next-window MUST NOT
compile確定signature変更禁止 / enum実値変更禁止 / field名・型・semantics変更禁止 / Stage A〜L順序変更禁止 / SoAをper-object registryへ戻す禁止 / code 6を永続Cfg失敗へ変換禁止 / prune診断値の毎足reset禁止 / ZoneView 7 sentinel fieldを未接続のまま最終化禁止 / Production へ request.*・描画・Debug文字列追加禁止。

## 15. Window 01 COMPLETE GATE
担当原文の未解決差分 0 / I27以外の質問 0 / 担当外ロジック先回り実装 0 / 全Batch TradingView compile error 0 / `HANDOFF_W01.md` generated。
