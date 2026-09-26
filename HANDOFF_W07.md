# HANDOFF_W07

## 1 状態
- Window 07 COMPLETE（B01〜B19）: FVG_State_Index_Localization
- branch `claude/laughing-dijkstra-3w3zgr`
- 未完了Batch 0 / 未解決canonical diff 0 / 未解決非I27質問 0 / Production未commit差分 0

## 2 最終HEAD
- W07 closeout base: `093f67b3c71f216acdeb7b3508b1d77859fe30e5`
- W08開始HEAD: このHANDOFF最終commitのHEAD

## 3 Production published versions（source importで確認）
- Main `ZoneEngineV2_Rebuild` /22（W07 B17〜B19 Harnessのimport）
- Main import: W03F0 /4、W03Apply /3、W03ETimeFvg /2、W05Candidate /4、W06Component /16、W07Fvg /10
- W05Candidate /4 → W07Fvg /10、W06Component /16 → W05Candidate /4
- W05 /3 = baseline（B19 parity比較用）

## 4 W07 canonical（verified contract）
- FVG TFは1H / 4H / Dailyのみ、NativeRange固定
- Fresh: formation third bar自身は消費しない、inclusive intersection、false後復活なし
- Structural invalidation: original FVG TF close、Bull Close < Distal / Bear Close > Distal、equalityはvalid
- Active / Inverse role: canonicalどおり
- Broad: width > M、localizationは4種のみ、unlocalized = BroadContext、BaseStrong false
- actual overlap: 同方向・異TF → High、同TF → Normal。non-overlapはM以内でもmergeなし
- 50%はRoot / scoring / localization / referenceに不使用

## 5 TV evidence
- B17: Fresh / Structural / Combined 全Failures 0。Main /22後のStructural再実行PASS
- B18（Build 180210）: Failures 0、Fixture 22、FirstFail -1、Lifecycle / Boundary / Eligibility / Touch 0、Ref / Opt ActiveFinals 10 / 10
- B19 Probe: B19Probe /1、B19BaselineProbe /1 compile / publish PASS。record hookはStage A 2 / Stage B 1 / Stage C 0、business drift 0
- B19 Lane1（190101）: Failures 0、Fixture 66、Main E2E 0、Pair 134 / 134
- B19 L2A（190201）: Failures 0、Fixture 53、W04 Ref / W05 Parity / Broad / Invalid 0
- B19 L2B（190202）: Failures 0、Fixture 50、Missing 0 / Extra 0、Offer 768 / 768
- B19 L2C3（190203）/ L2C4（190204）: 各Failures 0、Fixture 53、Winner / Broad / Invalid 0

## 6 B19 proof stack
1. Lane1 interval primitive: Reference = interval-index
2. L2A logical winner parity: W04 full Reference = W05 /3 = W05 /4（W 50）、/3 = /4（53）
3. L2B actual offer trace parity: /3 BaselineProbe = /4 Probe の Stage A/B offer多重集合
4. L2C ProbeDrift: actual /3 = BaselineProbe /1、actual /4 = B19Probe /1（winner drift 0）

## 7 branch-and-bound注意
W05 Stage A（Stage Cも）はcanonical exact branch-and-boundを持ち、勝てないcandidateはcandOfferRawへ到達しない。
よってW04 full enumeration（全candidate集合）とactual offer traceを同一集合として直接比較しない。
W04とはwinner（L2A）で、traceは/3 vs /4（L2B）で比較する。

## 8 Broad cap audit
- NO_EXPLICIT_BROAD_PARTICIPATION_CAP_FOUND、F04_MULTI_CLUSTER_TV_VERIFIED
- Broad共有だけではLOCAL component mergeなし

## 9 Harness rule（B18知見）
fixture dispatcherでwhileを使わず、forで実行する（whileでfixture方向の誤りを観測、forで解消）。
既存verbatim helper内のcanonical whileは変更不要。

## 10 Deferred（W07でPASS扱いしない）
- `I22_HASH_PATH = ABSENT`
- `GLOBAL_I22_CFG_FINGERPRINT_COLLISION = DEFERRED_TO_LATER_ENGINE_CONFORMANCE`
- W08以降へそのまま引き継ぐ

## 11 W08開始条件
- 次Window: W08 Core_Identity_Merge_Split
- 開始HEAD = 本closeout commit後HEAD、START GATE（local = remote、0 / 0、clean）
- W07 Productionロジックを理由なく変更禁止。W07 verified contractはfrozen dependency
