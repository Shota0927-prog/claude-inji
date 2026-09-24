# HANDOFF_W03

## 1. Status

- W01 COMPLETE / W02 COMPLETE / **W03 COMPLETE**（B01–B29 COMPLETE、Closeout Repair R1–R3 COMPLETE）
- TradingView compile error 0：Production Main、Harness、Worker 3本（ユーザー実測）
- Project 全体の完了ではない（§6）。

## 2. Final files / HEAD

- code-final HEAD：`c42d92faf66c1d29a49a80fde75075c004da9437`
- W03 handoff / branch HEAD：`8138b369d54c398bbe3034895f9cfbc54c8d021f`（branch `claude/laughing-dijkstra-3w3zgr`）
- Production：`sekine3310/ZoneEngineV2_Rebuild/20`（`ZoneEngineV2_Rebuild.pine`）
- Worker：`sekine3310/ZoneEngineV2_W03F0_Worker/2`、`.../ZoneEngineV2_W03Apply_Worker/1`、`.../ZoneEngineV2_W03ETimeFvg_Worker/1`
- Harness：`ZoneEngineV2_Rebuild_W03Harness.pine`（`/20` を import）

## 3. Completed interfaces

- Public API 19（W02 と同一）、export type 8 / total 27。Feed 110 = 既存18 ＋ Source 92。ZoneEngine 210、W03Store 86、W02Aux 129。
- `updateConfirmed5m`：A 検証 → B Event clear → C no-op → D3 FVG facts → E MA / Swing / Accum → ETimeFvg Worker（TimeHL → FVG）→ F（F0 → Apply → nextRootId → F5 → F6）→ L。
- Source 5 request（gaps_off / lookahead_off）：1m MA、15m Swing、1H Swing+Accum+FVG、4H / D Accum+FVG。5m Swing は chart。
- adoption / de-dup は Production（lastConsumed 11）。Harness は raw packet のみ。
- MA / Swing / Accum / TimeHL / FVG の Root generation、origin identity、23-field journal、index membership。
- revisions 8（rootRegistry / rootPrice / rootEligibilitySupport / rootEligibilityResistance / rootQuality / fvgState / fvgFresh / priceOrder）：dirty 集約、1 bar 最大 1 increment。

## 4. Frozen contracts

変更禁止：
- Public API、Feed の name / type / order、既存 enum / constants。
- B27 / B28 Source helper、5 request context、Production の request.* 0。
- W02 invariant 10（remove(0) / shift / unshift / clear / sort を 0）。
- Worker interface（F0 97 / Apply 107 / ETimeFvg 125）。
- Stage A–F、revision、adoption の semantics、Root identity（1-based・never reuse）。

## 5. W03 physical decisions

- N1：ACTIVE → INVALIDATED ＋ structurallyActive detach。Inverse には触れない。
- N2：FVG は NativeRange の bottom / top order のみ。common order は point Root だけ。
- N3：M = cfg.clusterMaxWidth（Broad は width tick > round(M / mintick)）。
- N8：baseOpenTime ＋ zoneTimezone で判定。新 period の最初の bar で遷移し、backdate しない。
- Q0：Subtype 1 / 2、TimeHL label 1 / 2 / 4 / 8 / 16 / 32、Swing mask 1 / 2 / 4、slope −1 / 0 / 1。
- Q0（Accum）：originEndTime = na、boxId = startTime、pairKey は Engine counter。
- merged Swing は作成時の tf / 時刻を維持。
- F0 の違反は `runtime.error("W03_JOURNAL_PREFLIGHT")`。op code は固定済み。

## 6. Not implemented / not verified

- LATER：Psych runtime Root、Core / Candidate / Side、EV_FVG_INVALIDATE、最終 Zone、Visual、StrategyBenchmark、range Root の common key。
- NOT_VERIFIED：Appendix B 75/75、I22 10/10、365日×3、≤12s / ≤20s、長期 runtime / loop / history、Realtime / Replay / reload の一致。
- parity は自作インタプリタ上の比較（実機ではない）。

## 7. Next Window notes

- W04 以降へ進む。W03 を再設計しない。
- W03 の Source / Root を入力契約として使う。Psych や Zone を W03 へ逆流させない。
- 旧 Stage F / E-tail の定義は到達不能のまま残している。Worker を変える場合は再 publish ＋ import 更新が必要。
- Main の token は上限に近い。追加時は実測すること。
