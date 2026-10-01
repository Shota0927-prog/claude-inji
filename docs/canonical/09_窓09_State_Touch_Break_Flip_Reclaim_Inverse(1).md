# ZoneEngine v2 — 窓09 State_Touch_Break_Flip_Reclaim_Inverse

## この窓の唯一の目的
State価格索引とArmed/Touch/Weak/Break/Gap/Reset/Flip/Reclaim/Inverseを実装しfull scan Reference一致。

## PHASE Aで列挙するもの
- Phase/Grade exact order
- Armed/approach
- Touch episode/count/reset
- WeakDepth/persistence
- BreakReferenceRange/GapBreak
- Flip/Reclaim/Inverse
- same-bar priority
- index extraction canonical order



# 全窓共通：固定実装決定（ユーザー承認済み・質問禁止）

このファイルは次の**2正本**から当該窓に必要な原文を無改変で収録したbundleです。別ファイルの提出を要求しないでください。

- 論理正本：`Zone_definition_spec_v2(5).md` / SHA-256 `f0ada2d851477850aa3d65463056e0318434b0c362383d475d49f9f6e1049cd1`
- 実装正本：`貼り付けたマークダウン（1）(20260922-064602).md` / SHA-256 `db5b1f7d980ecda6f07ea7522d4a4af4a3b7c57b8bcc8ddb2b84049791125c09`

正本優先順位は実装正本I2どおり。ただし、以下D01〜D12は「正本で実装段階に委ねられていた物理事項」について**本書作成後にユーザーが承認した固定決定**としてI2-1に該当します。論理結果を変えるために使ってはいけません。

## Q0 質問禁止
- I27停止条件に該当しない限り、ユーザーへの確認質問・選択肢提示・承認依頼は禁止。
- 「field名をどうするか」「enum値をどうするか」「どちらの実装にするか」等はD01〜D12に従う。
- 原文に答えがある事項を未定義扱いしない。
- 純粋な物理詳細でD01〜D12にもない事項は、論理結果/Event順/ID意味/境界/採用Base足/性能契約を変えない最小コスト・決定論的Pine v6実装を採用し、質問せずHANDOFFへ記録。
- I27該当時だけ`STOP_I27`。I27指定の5項目以外の質問文を付けない。

## D01 納品名
- Production: `ZoneEngineV2_Rebuild.pine`
- library名: `ZoneEngineV2_Rebuild`
- Visual: `ZoneEngineV2_Rebuild_VisualHarness.pine`
- Conformance: `ZoneEngineV2_Rebuild_ConformanceHarness.pine`
- StrategyBenchmark: `ZoneEngineV2_Rebuild_StrategyBenchmark.pine`
- Report: `ZoneEngineV2_Rebuild_Report.md`
- `buildId()` = `"ZoneEngineV2_Rebuild_Strict20sV3"`
- 無関係な既存`indicator.pine`等は変更・削除・流用しない。

## D02 ID / slot / sentinel
- `rootId/coreId/generationId`: 1開始、0=none、再利用禁止。
- slot: 0以上、invalid=-1。free-slotのみ再利用。
- `baseSeq`: 0以上、未処理=-1。
- time: Pine int epoch ms、未設定=`na`。

## D03 enum実値 / mask
- Category: MA=0, Swing=1, Accum=2, TimeHL=3, FVG=4, Psych=5。Category mask=`1 << categoryCode`。
- Side: Support=1, Resistance=-1, None=0（正本固定）。
- Phase: Waiting=0, Armed=1, ActiveTouch=2, Broken=3, FlipWait=4, Dormant=5。
- Grade: Strong=0, Neutral=1, Weak=2, Unavailable=3。
- Density: High=0, Normal=1, BroadContext=2。
- Root state: Candidate=0, Active=1, Invalidated=2, InverseWait=3, InverseActive=4, Retired=5。
- FVG: None=0, Bullish=1, Bearish=2。集約maskはOR、両方=3。
- Weak reason: None=0, Touch=1, Depth=2, Both=3。
- Event type: 正本記載順で1〜15。0は内部none予約。
- name APIの未知値=`"UNKNOWN"`。

## D04 固定TF / EMA
- TF code: 1m=1, 5m=5, 15m=15, 1h=60, 4h=240, D=1440。
- MA=1m、Base=5m、Swing=5/15/60、Accum/FVG=60/240/D。変更不可。
- EMA長=2000/3000固定。Cfg可変fieldにしない。Slope lookbackのみCfg。

## D05 ZoneCfg / host metadata
- `ZoneCfg`は実装正本A4の全設定、論理正本18の可変論理パラメータ、Accum設定、時間設定、保存上限、6カテゴリON/OFF bool（default true）、固定TF metadataを持つ。
- `chartTfMinutes:int`, `mintick:float`もZoneCfgに持つ。`newCfg()`では0/na sentinel。
- Harness/MainはEngine生成前に実chart値を代入する。5分以外/invalid mintickはvalidation failure。
- 固定TF metadataがD04から変わった場合もinvalid。

## D06 validation/error
`validateCfg(cfg)->int`。
0 OK / 1 CHART_TF_NOT_5M / 2 MINTICK_INVALID / 3 FIXED_TF_METADATA / 4 STRONG_UNLIMITED_CONFLICT / 5 TOUCH_THRESHOLD_ORDER / 6 FEED_METADATA_MISMATCH(Stage A専用)。
複数違反は小さいcode優先。
`strongUntilTouch >= weakFromTouch`は`!strongUnlimited && !weakFromTouchOff`の時だけ評価。不正値自動補正禁止。

## D07 Feed validation / duplicate
- FeedはBase OHLC, prevClose, open/close time, baseSeq, baseConfirmed, mintickとSource metadata/eventsを持つ。
- `validateCfg`はCfg単体。Stage Aで内部`validateFeedMetadata(cfg,feed)`を行う。
- 未確定、重複、過去Feedはcommitせずfalse。直前Eventを消さない。
- 初回以外、`baseSeq <= lastBaseSeq OR baseCloseTime <= lastBaseCloseTime`ならreject。

## D08 Public API return
- `updateConfirmed5m(...)->bool`: commit時true。
- `viewCount/eventCount/rootCount -> int`。
- `viewAt/eventAt/rootAt`はvalid indexのみ。範囲外=`runtime.error("INDEX_OUT_OF_RANGE")`。
- accessorはinternal mutable参照を返さずfresh numeric/bool projection UDTを返す。

## D09 Production string rule
- Engineには履歴Debug文字列/Root診断文字列を保存しない。
- 論理正本の診断表示はnumeric View/Root + name APIからVisual最終バーで生成。実装正本I19を優先。

## D10 cfg fingerprint
- 全Cfg field入力の独立int fingerprint 2本を保持し、どちらか変化時だけ再validation。
- Root/Candidate/Coreの同一性にはfingerprint単独を使わない。

## D11 更新順とAPI所有権
- Engine state mutationは`updateConfirmed5m`のみ。
- Stage A〜Lの順序は絶対固定。
- Event logical clearはduplicate/invalid reject後、新規確定Baseを受理した場合だけ。
- 後続窓は前窓compile済みsignature/enum/field semanticsを変更禁止。

## D12 物理実装の一般規則
- Root/Core/Side stateは実装正本I6のSoA/flattened arrays。per-object UDT registryへ戻さない。
- `SideHistory/TouchMark/TouchStartSnapshot/BreakSnapshot/SideViewState/ZoneCore`は論理モデルとして意味を維持し、物理保存はSoA/ring/pool。
- float元価格と比較tickを併存。比較時のみ`round(price/mintick)`。
- `array.remove(0)`/`array.unshift()`禁止。

# 作業プロトコル

## PHASE A — 読解のみ
1. ファイル全文を読む。コード編集禁止。
2. 担当MUST/MUST NOT、変更対象、変更禁止領域、関数/field/indexを列挙。
3. **質問・提案・承認依頼を出さない。** I27でなければ末尾`PHASE_A_READY`。

## PHASE B — 小Batch実装
- 最大3つの密接した関数/型/索引だけ編集して停止。
- 変更箇所、対応正本、TradingView compile確認点だけ報告。
- ユーザーcompile結果を受けるまで次Batchへ進まない。
- compile error修正は当該Batch内を優先。ロジック変更で逃げない。

## PHASE C — 担当監査
担当原文ごとにIMPLEMENTED / NOT_APPLICABLE / NOT_VERIFIED。未解決差分0、独自条件追加0、仕様削除0を確認。

## PHASE D — HANDOFF
`HANDOFF_Wxx.md`を最大3,000字。compile状態、完成interface、次窓依存field/index、変更禁止、次窓担当の未実装のみ。思考過程を入れない。


---

<!-- SOURCE_VERBATIM: 貼り付けたマークダウン（1）(20260922-064602).md L13-L36 | I0 最上位命令 -->

## I0. Claude Codeへの最上位命令

この文書は、ZoneEngine v2をゼロから再実装するための**完成指示書**です。既存Engineへ追加パッチを重ねず、新規ファイルとして作成してください。

Claude Codeへ渡す必須入力は、`Zone_definition_spec_v2(5).md`と本書の2ファイルだけです。旧Engine、旧Visual Harness、旧軽量版の提出を要求せず、これらを読み込んで流用しないでください。論理正本ファイル自体も編集しません。

Claude Codeに、アーキテクチャ、探索範囲、保存範囲、軽量化方式、代替ロジックを選択する余地は与えません。この本文で指定した構造、処理順、索引、API、検証、性能判定をそのまま実装してください。

次を厳守してください。

1. `Zone_definition_spec_v2(5).md`と本書を最初に最後まで読む。
2. Zoneの判定式、状態遷移、順序、初期値は変更しない。
3. この本文に「必須」と書かれた軽量化を省略しない。
4. 性能不足を理由にRoot、Candidate、Core、履歴、カテゴリ、時間足を黙って削らない。
5. 近似、件数による探索打切り、最初のN件だけの評価を行わない。
6. 未定義事項を独自判断で補完しない。結果へ影響する未定義事項だけを、該当箇所と選択肢を示して質問する。
7. 実装途中の版を完成と報告しない。
8. TradingViewで実測していない項目を`PASS`にしない。
9. 20秒以内を実測できなければ、ロジックを変更せず、Profiler結果と残るボトルネックを報告して停止する。
10. 「おそらく」「必要に応じて」「検討する」「適切な方式を選ぶ」という表現で実装判断を残さない。

本書本文の物理実装指定と、付録の古い「UDTまたはparallel arrayで構わない」等の選択表現が競合する場合は、**本書本文を優先**してください。付録は論理契約、数式、状態、初期値、受け入れ結果の正本として使用します。

---


---

<!-- SOURCE_VERBATIM: 貼り付けたマークダウン（1）(20260922-064602).md L68-L88 | I2 優先順位 -->

## I2. 正本と優先順位

優先順位は次のとおりです。

1. ユーザーが本書作成後に明示承認した変更。
2. `Zone_definition_spec_v2(5).md`。
3. 本書付録A、B、C、Dの論理契約、初期値、受け入れ条件。
4. 本書I章の固定実装方式。

旧Engine、旧Harness、過去のSAFE版、応急処置版は正本ではありません。既存コードの提出を前提にせず、新規実装してください。

次の内容だけが実装上変更可能です。

- 同じ結果を返すデータ配置。
- 同じ候補を漏れなく得る検索方法。
- 同じ入力に対する重複計算の除去。
- キャッシュ、索引、pool、ring bufferの使用。
- 数値状態と表示文字列の分離。
- テスト専用コードとProductionコードの分離。

---


---

<!-- SOURCE_VERBATIM: 貼り付けたマークダウン（1）(20260922-064602).md L90-L148 | I3-I4 納品/禁止 -->

## I3. 納品ファイルを固定する

次の5ファイルを作成してください。名称を変更しないでください。

1. `ZoneEngineV2_Rebuild.pine`
   - Production Library。
   - Zone論理、状態、数値Event、数値Viewだけを持つ。
   - `request.*()`、box、line、label、table、履歴Debug文字列を持たない。

2. `ZoneEngineV2_Rebuild_VisualHarness.pine`
   - Production Libraryを1本だけimportするindicator。
   - Engineは1インスタンスだけ生成する。
   - Source request、最終バーの描画、必要時だけのDebug表示を担当する。

3. `ZoneEngineV2_Rebuild_ConformanceHarness.pine`
   - 付録Bの75件と、本書I22の最適化同値テストを実行する。
   - 短い決定論的Fixture専用。
   - 素直な全走査Reference処理を含めてよいが、Production Libraryへ入れない。

4. `ZoneEngineV2_Rebuild_StrategyBenchmark.pine`
   - `strategy()`として作成する。
   - Production Libraryを1本だけimportし、Engineを1インスタンスだけ動かす。
   - 当該足Eventを全件読み、数値checksumへ接続する。
   - Entry条件、注文、描画、全View走査、Debug文字列は入れない。
   - Engine処理がコンパイラに除去されないようchecksumをData Windowへ出力する。

5. `ZoneEngineV2_Rebuild_Report.md`
   - 設計、仕様対応、全テスト、実測条件、Profiler、未確認事項を記録する。

旧EngineとのParity Harnessは作りません。Production、Visual、Conformance、StrategyBenchmarkを1ファイルへ統合しないでください。

---

## I4. 絶対禁止事項

以下を一つでも行った場合は不合格です。

- 履歴を15,000本等へ固定して切る。
- 最初の32 Root、最寄りN Root、先頭N Candidateだけを評価する。
- Candidate評価回数へ任意上限を設ける。
- Broad FVGの局所参加数へ任意上限を設ける。
- 時間切れが近いことを理由に途中結果を採用する。
- 遠いRootやDormant Zoneを、仕様の保存整理条件を満たさず削除する。
- ActiveTouch、Broken、FlipWait、InverseWait、PendingGenerationを性能目的で削除する。
- EMA2000／3000を5分EMAや近似EMAへ置換する。
- 1分足データ不足を別時間足で補間する。
- FVG、Accum、Swing、時間高安、心理価格のカテゴリを無効化する。
- `calc_bars_count`でEMAまたはZone入力履歴を任意に短縮する。
- tick丸め方法、epsilon、比較演算子を独自変更する。
- Touch、Weak、Break、Flip、Reclaim、Inverse、Merge、Split、Generationの順序を変える。
- Candidate comparatorまたはtie-breakを変える。
- hash一致だけでRoot集合やCandidateを同一扱いする。
- キャッシュ容量超過時に空結果、0、`na`、一部候補を返す。
- 表示上限30をEngineの保存上限へ流用する。
- Visual HarnessやStrategy側で別のZone判定を再実装する。
- Debug ON/OFFでFeed、Engine更新、状態、Eventを変える。
- 未実測の実行時間を達成済みと報告する。

---


---

<!-- SOURCE_VERBATIM: 貼り付けたマークダウン（1）(20260922-064602).md L1147-L1169 | I27 停止条件 -->

## I27. 相談が必要な停止条件

次の場合だけ作業を停止し、ユーザーへ相談してください。

- 正本同士に、結果が変わる明確な矛盾がある。
- Source確定時刻、offset、gaps等が正本から一意に定まらず、採用Base足が変わる。
- TradingViewが365日分の5分足または必要な1分データを提供しない。
- Pineのcollection／tuple／request制約へ、仕様上必要な状態が収まらない。
- 本書の全同値最適化後も12秒／20秒を超える。
- Root、Core、履歴、カテゴリ、Candidateを削らなければ性能条件を満たせない。
- 正本の数式に必要な入力が欠落している。

相談時は、次の5点だけを提示してください。

1. 該当する正本箇所。
2. 現在の実測結果。
3. ロジックを変えない代替案。
4. ロジックを変える案で変化する結果。
5. 予想される時間削減と根拠。

ユーザー承認前にロジック変更案をコードへ入れないでください。

---


---

<!-- SOURCE_VERBATIM: Zone_definition_spec_v2(5).md L3-L145 | 論理正本0-2 基本モデル/カテゴリ -->

## 0. 目的と適用範囲

- 対象銘柄はXAUUSD。
- Zoneを上位足の上昇・下降・レンジ条件へ依存させず、どの相場環境でも同じ定義で評価する。
- Strongは「次の対象タッチで反発しやすい構造」を表す。
- Weakは「反発より貫通しやすい消耗状態」を表す。
- Weakは無効Zoneではない。将来、Break方向のStrategy条件として別検証できるようにする。
- Zone品質と、エントリー方向、トリガー、TP、SL、時間帯、環境認識は分離する。
- 根拠が少ないだけのZoneをWeakとは呼ばない。
- 反発幅、WIN／LOSS、後から発生したSwingなど、未来の結果をZone強度へ戻さない。
- 現段階では仕様確定が目的であり、まだ実装しない。

---

## 1. 基本モデル

### 1.1 Root

EMA、Swing、Accum境界、期間高安、FVG、心理価格など、Zoneを構成する元の価格情報。

各Rootは少なくとも次を保持する。

- Root ID
- Category
- 発生時間足
- OriginTime
- ConfirmedTime
- 点価格またはNativeRange
- 現在の有効状態
- 発生起源タグ

### 1.2 Category

同じ考え方から生まれたRootをまとめた独立カテゴリ。

同カテゴリ内に複数のRoot、複数時間足、複数ラベルがあっても、独立カテゴリ数Cは1とする。

### 1.3 ZoneCore

Root起源、物理的位置、Zone世代を共有する本体。

同じZoneCoreの中に、支持側評価と抵抗側評価を別々に持つ。

### 1.4 Side View

ZoneCoreを特定方向から接近した場合の有効評価。

各ZoneCoreは次を別管理する。

- Support View
- Resistance View

各Side Viewは次を保持する。

- 方向上有効なRoot
- EffectiveZoneRange
- C：独立カテゴリ数
- H：高品質カテゴリ数
- Density
- Base Strongの可否
- SideTouchCount
- Weak理由
- Phase
- Grade
- SideFresh

### 1.5 NativeRange

FVGなど区間Rootが本来持つ、固定された元の範囲。

FVG Fresh、構造無効化、Distal／Proximal管理に使用する。

### 1.6 EffectiveZoneRange

実際のZone判定に使用する範囲。

次へ使用する。

- タッチ
- Weak侵入率
- ローカルBreak
- 密集度
- M判定
- Zone結合

FVGのNativeRangeとEffectiveZoneRangeは同じとは限らない。

### 1.7 Structural quality

独立カテゴリ数、カテゴリ内部品質、密集度から決まる構造品質。

タッチ履歴や反発結果は含めない。

### 1.8 Consumption state

タッチ番号、終値侵入、Breakなどから決まる消耗状態。

構造品質とは別に管理する。

### 1.9 PhaseとGrade

Phaseは接触段階、GradeはZone評価。

Phase：

- Waiting
- Armed
- ActiveTouch
- Broken
- FlipWait
- Dormant

Grade：

- Strong
- Neutral
- Weak
- Unavailable

Waitingは弱いという意味ではない。構造上Strongでも、まだタッチ受付前なら「Waiting｜Strong構造」となる。

### 1.10 Zone generation

特定のRoot構成と履歴を持つZoneインスタンス。

同価格でも、旧世代終了後に新しい独立構造が成立すれば、新しいZone世代とする。

---

## 2. 独立カテゴリ

独立カテゴリは次の6つ。

1. MA系
2. Swing系
3. Accum系
4. 時間区切り高安系
5. HTF FVG系
6. 心理価格系

同カテゴリ内の本数を増やして、Cを水増ししない。

---


---

<!-- SOURCE_VERBATIM: Zone_definition_spec_v2(5).md L1386-L1403 | 論理正本21 最終設計原則 -->

## 21. 最終設計原則

1. 同じロジックは1カテゴリ。
2. 実価格Rootを保持し、架空の加重平均Rootを作らない。
3. NativeRangeとEffectiveZoneRangeを混同しない。
4. Zone範囲は根拠分布を反映し、一律幅にしない。
5. Dense Strong coreを外側Rootで薄めない。
6. Strongは構造品質、Weakは消耗事実。
7. 根拠不足をWeakと呼ばない。
8. PhaseとGradeを混同しない。
9. 支持側と抵抗側を別評価し、物理Zoneは重複生成しない。
10. 未来情報で過去ラベルを書き換えない。
11. 確定前のRootや接触を履歴へ使わない。
12. Flip／Inverse確定接触を通常タッチとして消費しない。
13. 消耗履歴を消せるのは新Zone世代だけ。
14. FVGだけは形成方向を保持する。
15. Zone定義とStrategy条件を混ぜない。
16. 新条件を増やす前に、独立ロジックか既存カテゴリ派生かを確認する。


---

<!-- SOURCE_VERBATIM: Zone_definition_spec_v2(5).md L750-L1073 | 論理正本7-10 Phase/Touch/Weak/Break/Flip/Reclaim/Inverse -->

## 7. Phase・Grade・Armed

## 7.1 Phase

### Waiting

Zoneは存在するが、対象側から十分に離れていない。

### Armed

次のタッチを受け付けられる。

### ActiveTouch

現在、同一タッチEpisode中。

### Broken／FlipWait

旧役割をBreakし、Reclaimまたは反対側のFlip確認を待つ。

### Dormant

現在価格から遠く、表示・計算を休止している。履歴は保持。

## 7.2 Grade

各Side ViewのGrade判定順：

1. 有効な非心理Rootがない、またはFlip未確定：Unavailable。
2. WeakByDepth、または対象タッチ番号がWeakFromTouch以上：Weak。
3. Base Strongかつ対象タッチ番号がStrongUntilTouch以内：Strong。
4. それ以外：Neutral。

PhaseとGradeは別表示する。

例：

- Waiting｜Strong構造
- Armed｜Strong
- ActiveTouch｜開始時Strong
- ActiveTouch｜現在Weak
- FlipWait｜Unavailable

## 7.3 Root確定前禁止

- Swing：ConfirmedTime以降。
- Accum：Box ConfirmedTime以降。
- FVG：3本目の元時間足確定後。
- 時間高安：新極値の5分足確定後。
- 新Zone世代：必要Root確定後。

確定前の接触をタッチ履歴へ入れない。

## 7.4 Armed条件

初期TouchResetDistance＝10ドル。

Support View：

- 5分足終値がEffectiveZoneRange上端＋TouchResetDistance以上。

Resistance View：

- 5分足終値がEffectiveZoneRange下端−TouchResetDistance以下。

距離不足またはZone内ならWaiting。

確定時点ですでに距離条件を満たしていても、使用開始は次の5分足から。

---

## 8. タッチEpisode

## 8.1 タッチ開始

前の確定5分足時点でArmedだったZoneだけが、現在足でタッチ開始できる。

- 外側からヒゲまたは実体がEffectiveZoneRangeへ初めて入る。
- 接近しただけではタッチにしない。
- Zone成立時に価格が中にいる場合は数えない。
- 接近直前に価格がいた側でSupport／Resistanceを決める。
- FVG参加可否は方向も確認。

## 8.2 一本線Zone

初期TouchTolerance＝0ドル。

- low以下かつhigh以上にRoot価格があればタッチ。
- 端と同値を含む。
- 描画幅は使わない。

## 8.3 タッチ番号

各Side ViewにSideTouchCountを持つ。

Armed中：

- UpcomingTouchNo＝SideTouchCount＋1。

タッチ開始時：

- SideTouchCountを1増やす。
- その値をCurrentTouchNoとして固定。
- Episode中は同じCurrentTouchNoを使う。

Episode終了後：

- 次回はSideTouchCount＋1。

タッチ開始時にカウントは増えるが、進行中Episodeへ次回番号を適用しない。

## 8.4 Episode継続と終了

- Zone内外を往復しても、Reset条件までは同一Episode。
- Support：開始時Snapshot上端＋TouchResetDistance以上で5分足終値確定。
- Resistance：開始時Snapshot下端−TouchResetDistance以下で5分足終値確定。
- 条件達成後はEpisode完了し、次足からArmed。
- 反対側へBreakした場合はEpisode終了し、Broken／FlipWait。

TouchResetDistanceは反発強度ではなく、Episode分離専用。

Armed済みの足でタッチし、その足の終値がReset条件も満たした場合、同一足で1Episodeを完了できる。

---

## 9. Strong期限とWeak

## 9.1 タッチ回数設定

初期値：

- StrongUntilTouch＝1。
- WeakFromTouch＝2。

数値指定時はStrongUntilTouchよりWeakFromTouchを大きくする。

- StrongUntilTouch：1以上またはUnlimited。
- WeakFromTouch：2以上またはOFF。
- StrongUntilTouchがUnlimitedならWeakFromTouchはOFF。
- WeakFromTouchがOFFでもWeakDepthは有効。
- UnlimitedでもWeakDepthへ到達すればWeak。

判定対象：

- Armed／Waiting：UpcomingTouchNo。
- ActiveTouch：CurrentTouchNo。

初期値なら、1回目はBase StrongならStrong。1回目完了後の2回目以降はWeak。

## 9.2 WeakDepth

初期WeakDepthPct＝50%。0〜100%またはOFF。

確定5分足終値だけを使う。

Support：

- 幅があるZoneでは、上端から下端方向への終値侵入率。

Resistance：

- 幅があるZoneでは、下端から上端方向への終値侵入率。

閾値以上でWeak。

Zone端を越えてもBreakBuffer内ならWeak。

一本線Zoneでは侵入率を使わず、タッチ回数とBreakだけで管理。

同一Episode中は最も深い確定終値を保存する。

## 9.3 Weak維持

WeakはSide View別に維持する。

- WeakDepth到達後、価格が離れても解除しない。
- Reclaimしても解除しない。
- Root増減だけでは解除しない。
- 反対側へFlipしても旧側履歴を保存。
- 新Zone世代成立時だけリセット。

Weak理由を別保存する。

- WeakByTouchCount
- WeakByDepth
- WeakByBoth

ActiveTouch中にWeakへ変化しても、TouchStartGradeは書き換えない。

---

## 10. Break・Gap・Flip・Reclaim

## 10.1 ローカルBreak

初期BreakBuffer＝2ドル。

BreakReferenceRange：

- ActiveTouch中はTouchStartSnapshot範囲。
- GapBreakでは前足確定時点のArmed済みEffectiveZoneRange。

Support：

- 5分足終値がBreakReferenceRange下端−BreakBuffer以下。

Resistance：

- 5分足終値がBreakReferenceRange上端＋BreakBuffer以上。

条件：

- 確定終値1本。
- ヒゲ抜けではBrokenにしない。
- Buffer内ならWeak。
- BreakはZone PhaseをBroken／FlipWaitにするが、一般Rootを自動削除しない。

Waiting中でまだ役割が有効化されていない初期Zoneの単なる離脱は、Breakとして扱わない。

Break確定時にBreakSnapshotを作る。

- Break時のEffectiveZoneRange。
- Breakされた旧Side。
- Break時のRoot起源。
- Break確定時刻。

Flip、FlipAttempt、Reclaimの価格基準はBreakSnapshotへ固定する。EMA移動や後のZone再編で、移行中の確認価格を動かさない。

## 10.2 GapBreak

前足終値側から反対側へ完全にGapし、Zone内で価格が付かないまま5分足終値がBreak条件を満たした場合：

- GapBreakEvent。
- SideTouchCountを増やさない。
- WeakDepthへ入れない。
- PhaseはBroken／FlipWait。
- 過去の消耗履歴は維持。

GapBreak確定足と同じ足ではFlip／Reclaimを確定しない。次足以降から判定する。

始値がZone内なら、前足時点でArmedの場合は通常タッチ。

## 10.3 Flip

一般ZoneのFlip手順：

1. 5分足終値でローカルBreak。
2. BreakSnapshotからBreak側へTouchResetDistance以上離れて終値確定。
3. 反対側からBreakSnapshot範囲へ再接触。
4. 新役割側へ5分足終値回復。
5. Flip確定。

SupportからResistance：

- 再接触後、BreakSnapshot下側で終値確定。

ResistanceからSupport：

- 再接触後、BreakSnapshot上側で終値確定。

Flip確認接触は通常タッチではなくFlipConfirmEvent。

- 新側のSideTouchCountへ入れない。
- Strong／Weakタッチにしない。
- 確定後、価格がTouchResetDistance離れてから通常タッチを受付。

新側が当該世代で初めて有効化される場合、SideTouchCountは0。

過去に同じ側が使われていた場合は、その側のSideTouchCountとWeak履歴を復元する。

毎回のFlipで消耗履歴をリセットしない。

## 10.4 Flip待ち中

- 接触はFlipAttemptEventとして別記録。
- 通常SideTouchCountへ入れない。
- 失敗回数をStrong／Weakへ反映しない。
- 将来検証用にAttempt回数を保存可能。

## 10.5 Reclaim

Flip確定前に旧側へ戻った場合。

元Support：

- 5分足終値がBreakSnapshot上端＋BreakBuffer以上。

元Resistance：

- 5分足終値がBreakSnapshot下端−BreakBuffer以下。

Reclaim後：

- Broken／FlipWait解除。
- 元側履歴を維持。
- ZoneFresh／SideFreshを復活させない。
- Rootや品質根拠を新規作成しない。
- 現在距離に応じてWaitingまたはArmed。

FVGが元時間足で構造無効化済みなら、元FVGのReclaimは不可。

## 10.6 Inverse FVG

1. 元時間足終値でFVG構造無効化。
2. 無効化側へTouchResetDistance以上離れて終値確定。
3. 反対側からNativeRangeへ再接触。
4. 新しい役割側へ終値回復。
5. Inverse確定。

Bullish FVG無効化後：

- 下から再接触し、NativeRange下側へ終値回復するとBearish Inverse。

Bearish FVG無効化後：

- 上から再接触し、NativeRange上側へ終値回復するとBullish Inverse。

InverseConfirmEventは通常タッチへ数えない。

同じFVG起源・同じFVGカテゴリを引き継ぎ、独立根拠を増やさない。

新しい側が当該世代で初めて有効化される場合、その側のSideTouchCountは0。以前使われた側なら、既存のタッチ・Weak履歴を復元する。

---


---

<!-- SOURCE_VERBATIM: Zone_definition_spec_v2(5).md L1219-L1243 | 論理正本15 same-bar order -->

## 15. 同一5分足内の処理順

現在足で通常タッチを開始できるのは、前足確定時点でArmedだったZoneだけ。

処理順：

1. 前足確定時点のPhase・Side Viewを取得。
2. Armed済みZoneだけ現在足高安でタッチ開始判定。
3. ActiveTouchを現在足終値で評価。
4. 構造無効化、ローカルBreak、WeakDepth、Resetを確定。
5. 新Root、Root更新、品質変化を反映。
6. 結合、分裂、新世代候補を更新。
7. 次足用Phase・Grade・Armedを確定。

同時成立時：

- WeakとBreak：Break優先。
- FVG構造無効化とReclaim：構造無効化優先。
- 新RootによるStrong化：現在タッチへ反映しない。
- 現在足終値で初めてArmed：次足から有効。
- 現在足で初めてRoot確定：現在足ヒゲをタッチにしない。

確定値だけで再現し、5分足内部の見えない値動き順序を推測しない。

---


---

<!-- SOURCE_VERBATIM: 貼り付けたマークダウン（1）(20260922-064602).md L340-L379 | I8 Stage C/D -->

## I8. 1本の確定5分足の処理順を固定する

`updateConfirmed5m()`は次の順だけで処理してください。順序変更は禁止です。

```text
Stage A  Feedと設定を検証し、重複Base足を排除
Stage B  当該足Eventのlogical lengthを0へ戻す
Stage C  前足確定時点のPhase / SideView / Armedを参照
Stage D  現在足の状態事実を検出
         D1 前足Armed ViewのTouch / GapBreak
         D2 既存ActiveTouchのSnapshot基準評価
         D3 Break / WeakDepth / Reset / Flip / Reclaim / Inverseと、Feed内のFVG構造無効化事実
         D4 同時成立の優先順位確定
Stage E  Source事実をRoot mutation journalへ積む
         E1 D4で確定したFVG構造無効化を適用対象へ積む
         E2 新Root
         E3 Root価格・品質・Fresh・状態更新
         E4 Root失効
Stage F  journalを仕様順で一括適用し、全索引とrevisionを更新
Stage G  変更Rootから影響依存componentを固定点まで展開
Stage H  component単位でSide候補、Core対応、Merge / Split / Generationを再計算
Stage I  ActiveTouch中の変更をPendingTopologyへ保存
Stage J  次足用Phase / Grade / Armed / Dormant状態を確定
Stage K  保存整理を1回だけ実行
Stage L  数値Eventと確定状態をcommit
```

固定ルール：

- Rootイベント1件ごとにCandidate/Coreを再構築しない。
- 同一Base足の全Root mutationを適用してからTopologyを1回更新する。
- 現在足TouchはStage Cの前足構造で判定する。
- 現在足で生まれたRootを現在足Touchへ入れない。
- 新RootによるStrong化を現在のTouchStartSnapshotへ入れない。
- BreakとWeakDepthはBreak優先。
- FVG構造無効化とReclaimは構造無効化優先。
- GapBreak足でFlip／Reclaimを確定しない。
- 5分足内部の見えない順序を推測しない。

---


---

<!-- SOURCE_VERBATIM: 貼り付けたマークダウン（1）(20260922-064602).md L707-L739 | I16 state indexes -->

## I16. 毎足State処理を価格イベント型へ固定する

全Core／全Sideへ全状態判定を毎足行いません。状態別集合と価格索引から、当該足で遷移し得るViewだけを取得します。

| 判定 | 対象抽出 |
|---|---|
| Touch／GapBreak | 前足Armed ViewのEffectiveRangeと現在High-Lowが交差し得るもの |
| ActiveTouch | ActiveTouch集合の全件 |
| Local Break | 該当SideのBreak境界を現在Closeが越え得るもの |
| Reset／再Armed | Reset閾値を現在Closeが満たすWaiting View |
| Flip | FlipWait集合と固定BreakSnapshot閾値 |
| Reclaim | Broken／ReclaimWait集合と固定BreakSnapshot閾値 |
| Inverse | InverseWait集合とNativeRange／離脱閾値 |
| Dormant復帰 | 現在価格が復帰bandへ入ったDormant Core |
| Generation再接近 | PendingGeneration集合と決定論的再接近閾値 |

価格索引は判定対象を除外するための近似ではありません。各predicateがtrueになり得る必要十分な価格範囲で抽出してください。Conformance Harnessで、索引抽出結果と全Core全走査Referenceの結果を毎ケース比較します。

map、set、価格索引から取得したslot順を、そのまま状態評価順やEvent順へ使いません。抽出後に仕様の正規順で整列し、全走査Referenceと同じ順序でpredicate評価とEvent生成を行ってください。

Event配列はI8のStage／Substageで事実をcommitした順にappendします。同じSubstage内では`coreId`昇順、`generationId`昇順、Support、Resistanceの順にします。優先規則で抑止されたWeakDepth、Reclaim、Flip等のEventはappendしません。

その他の固定ルール：

- age、経過bar数を全件毎足incrementしない。開始`baseSeq`を保持し、必要時に差を計算する。
- ActiveTouch開始時の`coreId + generationId + TouchStartSnapshot`をEpisode終了まで固定する。
- Episode中に変更できるSnapshot値は`deepestClose`と`maxDepthPct`だけ。
- ActiveTouch中のTopology変更はPendingTopologyへ送る。
- Eventがない足にEvent UDTや文字列を生成しない。
- Event配列は物理容量を再利用し、毎足logical lengthだけ0へ戻す。
- Strategy側が全View走査しなくても、当該足の全Eventを順序どおり取得できるようにする。

---


---

<!-- SOURCE_VERBATIM: 貼り付けたマークダウン（1）(20260922-064602).md L1950-L2218 | 付録A11-15 -->

### 11. 5分足1本の更新順

更新は「現在足で起きた事実の検出」と「次足から有効な構造」を分離してください。

擬似コードは次の順です。

```text
update(engine, cfg, feed):
    validate cfg and confirmed base bar
    reject duplicate base bar
    clear current-bar events

    prev = previous confirmed Phase / SideView / Armed snapshot

    A. prev時点でArmedだったViewだけ、現在High/LowでTouchまたはGapBreakを検出
    B. 既存ActiveTouchをTouchStartSnapshot基準で評価
    C. 現在足からBreak / WeakDepth / Reset / Flip / Reclaim / Inverseの事実を検出
    D. 同時イベントの優先順位を解決
    E. FVG構造無効化、新Root、Root更新、Root失効を反映
    F. LiveStructureの参加資格を即時更新
    G. ActiveTouch関連の形状変更はPendingTopologyへ送り、それ以外を再クラスタ
    H. Merge / Split / Identity / PendingGenerationを更新
    I. 次足用Phase / Grade / Armedを確定
    J. 安全な保存整理とread-only View生成
```

同時イベントは、次を必ず守ります。

- Local BreakとWeakDepth：Break優先。WeakDepthイベントを同時確定しない。
- FVG構造無効化とReclaim：FVG構造無効化優先。
- 新RootによるStrong化：現在TouchStartSnapshotへ反映しない。
- 現在足終値で初めてArmed：次足からタッチ可。
- 現在足で初めてRoot確定：現在足ヒゲをタッチにしない。
- GapBreak足：同じ足でFlip／Reclaimを確定しない。

5分足内部の値動き順序を推測しないでください。確定OHLCだけで判定できない順序は発生させません。

---

### 12. Armedと接近方向

SideごとにArmedを管理します。

Support：

```text
baseClose >= effectiveTop + touchResetDistance
```

Resistance：

```text
baseClose <= effectiveBottom - touchResetDistance
```

等号を含みます。

距離条件を現在足で初めて満たした場合、`armedFromSeq = currentSeq + 1`相当とし、現在足ではタッチを開始できません。

接近方向は、最後に距離条件を満たした側で固定します。Zone内で成立した新ZoneはWaitingです。過去ヒゲを遡ってタッチにしません。

Flip／Inverse確認後も同じです。確認接触の直後に通常タッチを開始せず、確認後の別の確定足でReset距離を満たしてから次のタッチを受け付けます。

#### 12.1 Phase遷移表

| 現在Phase | 条件 | 次Phase |
|---|---|---|
| Waiting | 対象SideでReset距離を確定 | 次足からArmed |
| Armed | 通常交差 | ActiveTouch |
| Armed | 非交差の完全Gap＋Break Close | Broken／反対SideはFlipWait |
| ActiveTouch | Snapshot基準のReset、Breakなし | 次足からArmed |
| ActiveTouch | Local Break | 旧SideはBroken、反対SideはFlipWait |
| Broken／FlipWait | Reclaim | 旧SideをWaitingまたは次足Armedへ復元 |
| Broken／FlipWait | FlipConfirm | 新SideをWaitingへ。履歴は新Sideの保存値を使用 |
| InverseWait | InverseConfirm | Inverse方向SideをWaitingへ |
| Waiting／Armed | Dormant距離より遠く、移行処理なし | Dormant |
| Dormant | 監視距離へ復帰 | 履歴を保ったままWaiting／次足Armedを再計算 |

Dormantは論理無効化ではありません。ActiveTouch、Broken、FlipWait、InverseWait、PendingTopology、PendingGenerationをDormantへ落とさないでください。

---

### 13. タッチEpisode

#### 13.1 Touch start

前足確定時点で対象SideがArmedであり、現在足のHigh／Lowが前足時点のEffectiveZoneRangeとinclusiveに交差した場合だけ開始します。

幅あり：

```text
high >= bottom and low <= top
```

一本線：

```text
low <= price + touchTolerance
and high >= price - touchTolerance
```

タッチ開始時に次を同じ処理で行います。

1. SideTouchCountを1増やす。
2. CurrentTouchNoへ固定。
3. TouchStartSnapshot作成。
4. TouchMark追加。
5. ZoneFresh／SideFresh更新。
6. `EV_TOUCH_START`出力。

#### 13.2 同一Episode

Zone内外を往復しても、Snapshot基準のReset達成までは同じCurrentTouchNoです。

Support reset：

```text
close >= snapshotTop + touchResetDistance
```

Resistance reset：

```text
close <= snapshotBottom - touchResetDistance
```

等号を含みます。タッチ開始足でReset条件も満たす場合、同じ足で1Episodeを完了できます。次のタッチ受付は次足以降です。

#### 13.3 WeakDepth

幅が0より大きい場合だけ計算します。

Support：

```text
depthPct = clamp((snapshotTop - close) / width * 100, 0, 100)
```

Resistance：

```text
depthPct = clamp((close - snapshotBottom) / width * 100, 0, 100)
```

Episode中の最大値を保持します。閾値と同値でWeakです。Zone端を越えたがBreakBuffer内のCloseは100%としてWeakになり得ます。

一本線ではWeakDepthを使いません。

#### 13.4 Touch回数によるGrade

- Waiting／Armed：`upcomingTouchNo = sideTouchCount + 1`を評価。
- ActiveTouch：固定した`currentTouchNo`を評価。

Grade順序は必ず次です。

1. 非心理Rootなし、またはFlip未確定：Unavailable。
2. WeakByDepth、または対象Touch番号がWeakFromTouch以上：Weak。
3. Base Strongかつ対象Touch番号がStrongUntilTouch以内：Strong。
4. その他：Neutral。

TouchStartGradeはEpisode途中でWeakへ変わっても書き換えません。現在のView Gradeは、Weak確定条件を満たした時点でWeakへ変更してください。

Touch回数条件へ到達したSideでは`WeakByTouch=true`を保持し、Depth条件にも到達した場合はWeak理由を`WeakByBoth`にします。Reclaim、離脱、Root増減、反対側へのFlipでは解除しません。

---

### 14. BreakとGapBreak

#### 14.1 BreakReferenceRange

- ActiveTouch中：TouchStartSnapshot。
- GapBreak：前足確定時点のArmed range。

Support Break：

```text
close <= referenceBottom - breakBuffer
```

Resistance Break：

```text
close >= referenceTop + breakBuffer
```

等号を含み、確定終値だけを使います。ヒゲだけではBreakしません。Waiting中で一度も役割が有効化されていないZoneの単なる離脱はBreakにしません。

#### 14.2 GapBreak

前足でArmedだったSideについて、現在足がZoneと一度も交差せず、反対側へ完全にGapし、CloseがBreak条件を満たす場合です。

Supportの下抜け例：

- 前足はSupport Armed。
- 現在足HighがreferenceBottom未満。
- 現在CloseがSupport Break条件以下。

Resistanceは対称です。

GapBreakでは次を行いません。

- SideTouchCount増加。
- WeakDepth計算。
- ZoneFresh／SideFresh消費。

BreakSnapshotを作り、`wasGapBreak=true`を保存します。

Local BreakはZone Phaseを変える処理であり、Swing、Accum、時間高安などの一般Rootを削除する処理ではありません。

---

### 15. Flip、Reclaim、Inverse FVG

#### 15.1 一般Flip

Supportが下抜けた場合：

1. BreakSnapshot作成。
2. Closeが`snapshotBottom - touchResetDistance`以下でmovedAway。
3. その後、下側からBreakSnapshotへinclusiveに再接触。
4. Closeが`snapshotBottom`以下ならResistance Flip確定。

Resistanceが上抜けた場合は対称です。

1. Closeが`snapshotTop + touchResetDistance`以上でmovedAway。
2. 上側から再接触。
3. Closeが`snapshotTop`以上ならSupport Flip確定。

Flip確認接触は通常Touchではありません。SideTouchCount、WeakDepth、ZoneFresh、SideFreshを変えません。

再接触したが新役割側でCloseできず、Reclaimにも該当しない場合はFlipAttemptです。Attempt回数だけを保存し、Gradeへ反映しません。

#### 15.2 Reclaim

Flip確定前だけ判定します。

- 元Support：Closeが`snapshotTop + breakBuffer`以上。
- 元Resistance：Closeが`snapshotBottom - breakBuffer`以下。

Reclaim後は元Side履歴をそのまま復元します。FreshとWeakを復活・解除しません。現在距離に応じてWaitingまたは、次足からArmedにします。

構造無効化済みFVG RootはReclaimで元方向へ戻しません。

#### 15.3 Flip後の履歴

- 新Sideが当該世代で初回ならTouchCount 0。
- 過去に同じSideが使われていたなら、TouchCountとWeak履歴を復元。
- Flipを繰り返しても履歴をリセットしない。
- FlipConfirm足では通常タッチを開始しない。

#### 15.4 Inverse FVG

一般Flipとは別に、FVG Root単位で管理します。

Bullish FVG無効化後：

1. CloseがNativeBottom−ResetDistance以下でmovedAway。
2. 下側からNativeRangeへ再接触。
3. CloseがNativeBottom以下でBearish Inverse確定。

Bearish FVG無効化後は対称です。

1. CloseがNativeTop＋ResetDistance以上。
2. 上側から再接触。
3. CloseがNativeTop以上でBullish Inverse確定。

InverseConfirmも通常Touchへ数えません。同じFVG origin、同じFVGカテゴリを引き継ぎ、Cを増やしません。

---


---

# 窓09 COMPLETE GATE
- 担当原文の未解決差分0。
- I27以外の質問0。
- 担当外ロジックの先回り実装0。
- 各BatchはTradingView compile 0確認後に次へ（未実測時NOT_VERIFIED）。
- `HANDOFF_W09.md`生成。
