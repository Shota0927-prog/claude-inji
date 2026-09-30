# ZONEENGINE_COMPILED_TOKEN_RULES

正本（canonical）。ユーザー提示の「ZoneEngine｜軽量化・Compiled Token管理 固定ルール」§0〜§18 を原文のまま保存する。
全Window・全Batch（W09 / W10 / W11 / W12 以降）に継承する。要約・意味変更禁止。
参照元: `GLOBAL_TOKEN_LEDGER.md`、各 `HANDOFF_*.md`（`Compiled Token Rule: ZONEENGINE_COMPILED_TOKEN_RULES.md`）。

```text
【ZoneEngine｜軽量化・Compiled Token管理 固定ルール】

━━━━━━━━━━━━━━━━━━
■ 0. 目的
━━━━━━━━━━━━━━━━━━

「実装した後にtoken超過して削る」
を繰り返さない。

今後は：

設計
→ token予算確認
→ 最小Probe
→ TradingView実測
→ 本実装
→ compile確認

の順を原則とする。

source tokenではなく、
TradingViewのcompiled tokenを最終authorityとする。


━━━━━━━━━━━━━━━━━━
■ 1. Main compiled-token予算
━━━━━━━━━━━━━━━━━━

Pine上限：

1,000,000

状態区分：

GREEN
<= 950,000

YELLOW
950,001 ～ 975,000

RED
> 975,000

原則：

GREEN
→ 新semantic Batch開始可。

YELLOW
→ 小Batchのみ。
   大きなstate機能追加前にtoken Probe必須。

RED
→ 新しい大規模semantic実装禁止。
   先に構造圧縮する。

「compileが通ったからOK」
だけで次へ進まない。


━━━━━━━━━━━━━━━━━━
■ 2. B08以降の実装前Gate
━━━━━━━━━━━━━━━━━━

新Batch開始前に必ず確認：

1. 現在Main compiled token
2. 現在headroom
3. 今回追加予定のreachable構造
4. UDT copyの有無
5. tuple returnの有無
6. 巨大引数forwardingの有無
7. Support/Resistance重複の有無
8. plan/preflight/apply重複の有無
9. Mainにbusiness logicが入らないか
10. Worker側で共通化できるか

大きな構造を新設する場合：

本実装前に
最小compiled-cost Probeを作る。

Probe結果を見てから本実装する。


━━━━━━━━━━━━━━━━━━
■ 3. Mainは薄くする
━━━━━━━━━━━━━━━━━━

Mainへ置いてよいのは原則：

・Worker call
・plan call
・preflight call
・apply call
・Stage wiring
・最小限のevent wiring

禁止：

巨大predicate
巨大validation
Support/Resistance別ロジック
カテゴリ別business logic
大量の同型array操作
巨大tuple加工
同じ引数の繰り返しforwarding。


━━━━━━━━━━━━━━━━━━
■ 4. 最初から共通化する
━━━━━━━━━━━━━━━━━━

実装後に軽量化するのではなく、
最初から以下を検討：

Support / Resistance
→ Side共通処理

High / Low
→ 固定方向parameter

カテゴリ別同型処理
→ canonical fixed-order loop

同型journal処理
→ common helper

plan / preflight / apply
→ 共通validation

同じfield群
→ flat scratch / indexed arrays

同じ巨大引数群
→ 可能な範囲で共通context。

ただし意味論を変える共通化は禁止。


━━━━━━━━━━━━━━━━━━
■ 5. 高コスト構造の警戒
━━━━━━━━━━━━━━━━━━

以下はsource量が少なくても
compiled tokenが大きくなる可能性があるため
事前Probe対象：

・巨大UDT .copy()
・大きなUDTを複数返すtuple
・巨大tuple
・大量arrayの受け渡し
・巨大export signature
・同じ巨大関数の複数call path
・大量のgeneric wrapper
・大量argument forwarding
・projected stateの複製
・同型処理を別関数で複数保持

source estimatorだけで安全判定禁止。


━━━━━━━━━━━━━━━━━━
■ 6. TOKEN_REFACTOR_ONLY
━━━━━━━━━━━━━━━━━━

意味論不変の軽量化では：

必須：

・代表deterministic equivalence
・必要ならrandom smoke 最大500件
・TradingView compile

原則不要：

5k
50k
200k
mutation

5分超のテスト禁止。

最終確認は
TradingView compiled token。


━━━━━━━━━━━━━━━━━━
■ 7. semantic Batch
━━━━━━━━━━━━━━━━━━

通常ロジック追加では：

基本：

・仕様対応deterministic
・関連Harness
・TradingView compile

random testは標準Gateにしない。

Merge / Split /
State Transfer /
複雑なatomic transaction

など、
代表ケースだけでは不足する理由がある場合のみ
最大1k程度から開始。

5k以上は
ユーザー承認なしに実行禁止。


━━━━━━━━━━━━━━━━━━
■ 8. 5分ルール
━━━━━━━━━━━━━━━━━━

5分以上かかる可能性がある：

test
fuzz
benchmark
equivalence
background job

を勝手に開始禁止。

必要なら事前に：

・目的
・必要理由
・予想時間
・短縮案

を報告してSTOP。

ユーザー承認後のみ実行。


━━━━━━━━━━━━━━━━━━
■ 9. 既存PASS再利用
━━━━━━━━━━━━━━━━━━

変更していないsemanticsについて：

過去のPASS結果を再利用する。

理由なく：

deterministic再実行
5k再実行
50k再実行
大量regression

をしない。

変更範囲だけ検証。


━━━━━━━━━━━━━━━━━━
■ 10. Batch途中compile
━━━━━━━━━━━━━━━━━━

大きなsemantic Batchでは
最後まで実装してからcompileしない。

compiled-costが高そうな機能は：

設計
→ 最小Probe
→ compile

本体50%程度
→ 必要ならcompile

本体完成
→ compile

と小刻みに確認。

ただしユーザーへ
無意味に何十回もpublishさせない。


━━━━━━━━━━━━━━━━━━
■ 11. source estimatorの位置づけ
━━━━━━━━━━━━━━━━━━

reachable source token等は：

参考値のみ。

PASS/FAIL判定へ使用禁止。

TradingView compiled tokenと
相関が確認できない場合は、

source削減量から
compiled削減量を推測しない。


━━━━━━━━━━━━━━━━━━
■ 12. 軽量化でロジックを削らない
━━━━━━━━━━━━━━━━━━

token対策を理由に禁止：

条件削除
近似
履歴短縮
候補数制限
Root削減
精度変更
comparison変更
順序変更
fail-closed弱化
state削除
event削除。

削るのは：

重複構造

だけ。


━━━━━━━━━━━━━━━━━━
■ 13. Batch開始時レビュー
━━━━━━━━━━━━━━━━━━

毎Batch開始時に必ず出す：

【TOKEN START REVIEW】

Main compiled：
xxxxxx / 1,000,000

Headroom：
xxxxxx

Status：
GREEN / YELLOW / RED

今回追加予定：
○○

高コスト候補：
○○

Probe必要：
YES / NO

Main business logic追加：
YES / NO
※ YESなら設計見直し

今回のtoken方針：
○○


━━━━━━━━━━━━━━━━━━
■ 14. Batch終了時レビュー
━━━━━━━━━━━━━━━━━━

毎Batch終了時に必ず出す：

【TOKEN END REVIEW】

Before compiled：
xxxxxx

After compiled：
xxxxxx

Delta：
+ / - xxxxx

Headroom：
xxxxxx

Status：
GREEN / YELLOW / RED

変更Production：
○○

新規reachable heavy structure：
○○

TOKEN_REFACTOR_ONLY：
有 / 無

長時間テスト：
有 / 無

5分超処理：
有 / 無

不要な再テスト：
有 / 無

ルール違反：
0 / 内容

次Batch開始可能：
YES / NO

次Batch token risk：
LOW / MEDIUM / HIGH


━━━━━━━━━━━━━━━━━━
■ 15. 振り返り項目
━━━━━━━━━━━━━━━━━━

各Batch完了時に以下を確認する。

Q1.
今回、実装後にtoken問題が発覚したか？

YESなら：
なぜ事前Probeで捕まらなかったか記録。

Q2.
source estimatorを信用しすぎなかったか？

Q3.
Mainへbusiness logicを入れなかったか？

Q4.
Support/Resistance等の重複を
最初から共通化できなかったか？

Q5.
巨大UDT / tuple / argument forwardingを
事前にProbeしたか？

Q6.
不要なrandom testを回していないか？

Q7.
5分超作業をユーザー承認なしに実行していないか？

Q8.
変更していない範囲を
無駄に再テストしていないか？

Q9.
次Batchに十分なtoken headroomを残したか？

Q10.
「compileが通っただけ」で
次へ進もうとしていないか？


━━━━━━━━━━━━━━━━━━
■ 16. FAIL時
━━━━━━━━━━━━━━━━━━

軽量化ルール違反が1つでもあれば、

次Batchへそのまま進まない。

原因：

DESIGN
TOKEN_PROBE
MAIN_BLOAT
OVER_TEST
RETEST
HIGH_COST_STRUCTURE
OTHER

のいずれかで分類。

再発防止を1行で記録してから進む。


━━━━━━━━━━━━━━━━━━
■ 17. Window closeout
━━━━━━━━━━━━━━━━━━

Window終了時には：

各Batchの
TOKEN START / END REVIEW

を見返し、

・最もtokenを増やしたBatch
・最も効果のあった圧縮
・効かなかった圧縮
・不要だったテスト
・次Windowで避ける構造

をHANDOFFへ残す。

次Windowはその振り返りを
START GATEで読む。


━━━━━━━━━━━━━━━━━━
■ 18. 最重要原則
━━━━━━━━━━━━━━━━━━

後から軽量化しない。

最初から：

「この実装はcompiled tokenを
どれくらい使う可能性があるか」

を設計条件に含める。

正確性を落とさず、
重複だけを最初から作らない。
```

---

## LESSONS / INCIDENT（追記欄。§0〜§18本文は変更しない）

### INC-1: W09 B07-R3B0 compiled-cost Probe（HIGH_COST_STRUCTURE、確定）

- R3B0 full：1,113,110（CE10216）。直前baseline（W06 /23・W09State /22）はMain PASS（<1,000,000）。
- P1（W09State /23 import維持、Probe call 3行削除）：1,112,872（CE10216）。
- Probe-call cost：238。
- 増加量：W09State /23だけで +112,873以上。
- 原因：cross-library foreign-type / import reachability（W09State → W08Core /18・W08Touch /5 のimport、W08型fieldを持つTouchProjectView）。
- 分類：HIGH_COST_STRUCTURE。
- 再発防止：「小さいView型でも、他Production libraryの巨大型・plan型を跨いでimportするとcompiled reachabilityが爆発する可能性がある。foreign Production type dependencyはHIGH_COST_STRUCTUREとして扱い、本実装前Probe必須。」

### INC-2: W09 B07-R3B1 本体（TOKEN_PROBE）

- 結果：Main 1,003,009（CE10216）、headroom -3,009、Status RED。R3-B1 semanticはKEEP / FROZEN（deterministic 29/29、reference parity PASS）、TV Gate FAIL、R3-B1 NOT COMPLETE。
- 原因：R3-B1 Wiring Probeは4 primitive array forwardingとW08Touch / W08Runtime wiringのcompiled costだけを確認し、Projected Mark Injection本体（private helper群、Merge / Split projected processing、canonical row handling）のcompiled costを含まなかった。
- 分類：TOKEN_PROBE。
- 再発防止：「配線ProbeがPASSしても、本体側に複数helper / loop / canonical処理追加があるsemantic Batchでは、本体物理構造を含む中間Gateを検討する。」

### LESSON-3: RED中の大きな削減（運用ルール）

- RED状態で必要削減量が大きい場合、500token級のmicro-refactorをpublish単位で連続実施しない。
- 同一module・同一callerのLOW-risk single-call helper群をbundle監査し、意味論不変の範囲で大きい物理境界をまとめて消す。
- 実測：D1（51 params）-551、D2（74 params）-611。

