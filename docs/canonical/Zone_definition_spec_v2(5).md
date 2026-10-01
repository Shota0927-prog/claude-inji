# Zone定義仕様書 v2（矛盾チェック反映版・実装前確定ドラフト）

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

## 3. 各カテゴリの定義

## 3.1 MA系

### 対象

- 1分足EMA2000
- 1分足EMA3000

### Root

- EMA2000とEMA3000は別々の実価格Rootとして保持する。
- 2本の中間価格を架空のMA Rootにしない。
- 離れていれば別Zone候補になれる。
- 同じZoneへ参加しても、CはMA系の1だけ。
- 2本が参加した場合は、両方の実価格を範囲へ反映する。

### 傾き

- EMA自体は1分足から計算する。
- 傾きは確定済み1分足値から計算し、確定5分足時点でのみ更新する。
- 初期値は60本前の1分足EMAとの差とする。
- 差が正なら上向き、負なら下向き、同値ならFlat。
- 形成途中の5分足では品質を変更しない。

### High条件

次の全条件を満たす場合、MA系をHighとする。

- EMA2000とEMA3000が同じDense coreへ参加。
- 2本の価格差が高密集幅以内。
- Support Viewでは2本とも上向き。
- Resistance Viewでは2本とも下向き。

それ以外はNormal。

- EMAが1本だけ。
- 2本の距離が高密集幅を超える。
- 傾きが混在。
- 2本とも対象方向へ逆向き。
- Flatを含む。

逆向きでもRoot自体は削除せず、Highにしないだけとする。

### 有効期間

- 常に現在のEMA価格だけを使う。
- 過去にEMAが通過した価格を残さない。
- EMAがZone候補から外れたら、MA系を外して再計算する。
- MA単独Zoneは現在のMAへ追従する。
- 終値で抜けてもEMA Root自体は消えない。
- EMA移動や後からの重なりだけでは、ZoneFresh、SideFresh、タッチ回数、Zone世代をリセットしない。

---

## 3.2 Swing系

### 対象と初期Pivot Length

| 時間足 | 初期値 |
|---|---:|
| 5分足 | 10 |
| 15分足 | 8 |
| 1時間足 | 6 |

判定は左右同一本数のPivot High／Lowを使う。各Lengthは変更可能。

### 時刻

Swingは次の2時刻を保持する。

- OriginTime：実際のPivot足の時刻
- ConfirmedTime：左右の確認本数が揃った時刻

Rootとして使用できるのはConfirmedTime以降。

確定前にOrigin価格へ触れていた事実は、タッチ履歴へ入れない。

### 同一イベント

複数時間足で同じ転換を検出した場合は1起源へ統合する。

同一イベント条件：

- Pivot価格が最小ティック単位で一致。
- 下位足PivotのOriginTimeが、上位足Pivot足の時間区間内に入る。

条件を満たさない別時期のSwingは、同価格でも別イベントとする。

### Rootと役割

- Swing High／Lowは発生起源タグ。
- 現在の支持・抵抗は接近方向で決める。
- 別時期のSwingが同価格にあるだけではHighへ上げない。
- 過去の反応回数をSwing品質へ加えない。

### High条件

- 1時間足Swing。
- 同一転換点を15分足と5分足が検出。

15分足単独、5分足単独はNormal。

BOSや強い離脱は品質へ使用しない。

### 有効期間

- 確定後の価格は固定。
- 新Swingで古いSwingを移動・上書きしない。
- 抜けてもRootは削除せず、Zone側でBreak／Flipを管理する。
- Flip後も同じSwing起源を引き継ぐ。
- 時間経過だけでは無効化しない。

---

## 3.3 Accum系

### 対象

- 1時間足Accum Box
- 4時間足Accum Box
- 日足Accum Box

### 検出方式

新ZoneではAccum Box方式だけを使用する。

Provisional ATR方式はLEGACY専用とし、新Zoneでは使用しない。

初期検出値：

| 設定 | 初期値 |
|---|---:|
| 判定レンジ本数 | 10 |
| 基準本数 | 20 |
| ATR本数 | 14 |
| 上半分最低終値本数 | 4 |
| 下半分最低終値本数 | 4 |
| 同色連続上限 | 4 |
| レンジ幅／ATR上限 | 2.5 |
| 短期幅／基準幅上限 | 0.70 |
| ドリフト上限 | 0.30 |

ATRは形成時にレンジ性を検出するためだけに使う。確定後のZone幅、Break、タッチ距離には使わない。

### Candidate

- 元時間足の確定足でAccum条件がfalseからtrueになったら開始。
- 初期上下限は判定対象期間内の実体上端・実体下端。
- 条件継続中は実体ベースで更新。
- ヒゲは境界へ使わない。
- Candidate中はZone Rootにしない。
- Candidate中の接触をタッチ履歴へ入れない。

### Confirmed

元時間足の確定足でAccum条件がtrueからfalseになった時点でBox確定。

- 最後に条件を満たした足までの上下限を固定。
- falseになった終了足はBoxへ含めない。
- ConfirmedTime以降にRootとして登録。
- 形成中のまま終了していないBoxは未確定。
- 登録後、価格が一度十分に離れてから最初のタッチを数える。

### 境界

- 上限：Box内で最も高いローソク実体上端。
- 下限：Box内で最も低いローソク実体下端。
- 固定幅を追加しない。

### 同じBoxの上下限

同じBoxの上限と下限はMutually Exclusive Pairとする。

- 同じDense coreへ入れない。
- 同じ通常Zoneへ入れない。
- 代表価格計算へ同時に入れない。
- M以内でも結合しない。
- Broad FVGが両方を覆っても結合しない。
- それぞれ別Zone候補、別タッチ履歴、別Break履歴を持てる。

他Rootが両境界へ近い場合でも二重参加させず、クラスタ競合ルールで一方へ割り当てる。

### High条件

- 4時間足または日足の確定境界。
- 異なる時間足の別Box境界が同じcoreで重なる。

1時間足単独はNormal。

同じ時間足の別Box同士だけでは自動でHighにしない。

上限／下限の組み合わせは問わない。ただし同じBox同士は補強禁止。

### 有効期間

- 確定後は境界を動かさない。
- 新Boxで古いBoxを自動削除しない。
- 片側のBreakは同じBoxの反対境界へ影響させない。
- Breakした境界はZone側でFlip待ちにする。
- 時間経過だけでは無効化しない。

---

## 3.4 時間区切り高安系

### 対象

- 現在セッション高値／安値
- 直近確定セッション高値／安値
- 当日高値／安値
- 前日高値／安値
- 現在週高値／安値
- 前週高値／安値

### 価格

- 実際のヒゲ先を使う。
- Accumの実体境界とは分離する。
- 確定5分足ごとに更新する。

### 初期時間

- Asia：09:00〜14:00 JST
- Europe：14:00〜19:00 JST
- New York：19:00〜翌03:00 JST
- 03:00〜09:00：現在セッションなし。直近確定セッションのみ保持。
- 日足区切り：05:00 JST
- 週区切り：月曜05:00 JST

時間帯と区切り時刻は変更可能。

### 現在期間Root

- 新高値／新安値の確定ごとに現在Rootを更新。
- 更新前の価格は時間高安系として残さない。
- 新極値は新Root IDとし、価格が離れるまでWaiting。
- 古い価格がSwingとして確定していればSwing系としてのみ残る。

### 期間終了

- 終了時に高安を固定。
- 同一起源のまま、直近確定セッション、前日、前週へラベル移行。
- 次の対象期間が確定したら、それ以前の時間高安はカテゴリから外す。
- 同じ実イベントへ複数期間ラベルが付いた場合、1Rootへラベルを集約。

### High条件

- 現在週高値／安値。
- 前週高値／安値。
- 前日高値／安値。
- 別起源の期間高安が同じcoreで重なる。

当日、現在セッション、直近確定セッションはNormal。

高値／安値は起源タグであり、現在役割は接近方向で決める。

---

## 3.5 HTF FVG系

### 対象

- 1時間足FVG
- 4時間足FVG
- 日足FVG

5分足・15分足FVGはエントリー／トリガー用に残し、構造Zone Rootにはしない。

### 形成

元時間足の確定済み3本で判定する。

Bullish FVG：

- 3本目の安値が1本目の高値より上。
- NativeRangeは1本目高値〜3本目安値。
- 上端がProximal edge、下端がDistal edge。

Bearish FVG：

- 3本目の高値が1本目の安値より下。
- NativeRangeは3本目高値〜1本目安値。
- 下端がProximal edge、上端がDistal edge。

3本目の元時間足確定後からRootとして使用する。

### NativeRange

- 元区間を固定。
- ヒゲが入っても縮小しない。
- 固定幅を追加しない。
- 50%地点は表示専用。
- 50%地点をRoot、加点、局所化、基準価格へ使わない。

### 方向

- Bullish FVG：Support Viewでのみ参加。
- Bearish FVG：Resistance Viewでのみ参加。
- 反対方向では不参加。
- BullishとBearishは相互補強しない。

### Fresh

- 確定後、NativeRangeへ一度も再訪していなければFVG Fresh。
- ヒゲがNativeRangeへ一度でも入ればFresh終了。
- Fresh終了だけでは無効化しない。
- Zone Freshとは別属性。

### 構造無効化

- Bullish：元時間足終値がDistal edgeより明確に下。
- Bearish：元時間足終値がDistal edgeより明確に上。
- 同値では無効化しない。
- Zone用BreakBufferを加えない。

無効化後：

- Root状態をInvalidated／InverseWait。
- 元方向へ即時不参加。
- Inverse確定までは反対方向にも不参加。
- 他Rootは無効化しない。

### FVG構造無効化とローカルBreak

両者を別階層で管理する。

- FVG構造無効化：Rootの参加資格。
- ローカルBreak：EffectiveZoneRangeに対するZone状態。

他に有効な非心理Rootが残る場合、そのRootだけでZoneを再評価する。

FVG以外に有効Rootがなければ、Zoneは「InverseWait｜Unavailable」として保持する。

### 同方向FVGの重複

- 各NativeRangeは別々に保持。
- 実際の共通区間をEffectiveZoneRangeにできる。
- 異なる時間足同士の重複ならFVGカテゴリをHigh。
- 同じ時間足の別FVG同士は、重複してもNormal。
- 一方が無効化されたら、そのRootだけ外して再計算。

同方向でも重なっていないFVGは、距離がM以内という理由だけでは結合しない。

### High条件

- 非Broadの4時間足または日足FVG。
- 異なる時間足の同方向FVGが実際に重なる。
- Broad FVGが有効条件で局所化される。

1時間足単独はNormal。

BOSは使用しない。

### Broad FVG

NativeRange幅がMを超えるFVG。

- 強いインバランスだが、反応位置の精度が低い状態。
- NativeRange全体を保持。
- 全域をStrong Zoneにしない。
- Distal edgeを高品質反発地点にしない。
- 局所化できない場合はBroad Neutral contextとして保持。

Strong用に局所化できる条件：

- Proximal edge周辺に別カテゴリが高密集。
- 同方向の別時間足FVGと実際に重なる。
- 内部に高品質な別カテゴリがある。
- 内部にFVG以外の独立カテゴリが2つ以上高密集。

内部に通常品質の別カテゴリが1つあるだけでは、任意位置をStrongにしない。

---

## 3.6 心理価格系

### 対象

- 100ドル刻み：Major
- 50ドル刻み：Standard
- 100ドル価格はMajorの1Rootだけ。
- 10ドル・25ドル刻みは対象外。

### 扱い

- 静的な点Root。
- 上からなら支持、下からなら抵抗。
- Major／Standardとも心理価格系の1カテゴリ。
- 常にNormal。
- 2カテゴリStrongに必要なHigh側にはなれない。
- 単独ではZoneを生成・維持しない。
- 他の非心理カテゴリとM以内で重なる場合だけ参加。
- 心理価格の追加だけではZone世代、ZoneFresh、SideFreshをリセットしない。
- 表示・計算は現在価格周辺だけに限定できる。

---

## 4. 支持・抵抗とSide View

### 4.1 Potential Role

FVG以外は接近方向で役割候補を決める。

- 上から接近：支持候補。
- 下から接近：抵抗候補。

Swing High／Low、Accum上限／下限、期間高値／安値は発生起源タグであり、現在役割を固定しない。

### 4.2 Eligible Role

- 未解決のBreakがなければPotential Roleを使用可能。
- 旧側Break後、反対側からの接近はFlipCandidate。
- Flip確定までは通常ZoneとしてUnavailable。
- FVGは形成方向またはInverse方向の一致も必要。

新規Zoneに過去のBreak履歴がない場合は、最初にどちらから接近してもFlip確認不要。

### 4.3 方向別評価

Support ViewとResistance Viewで別々に計算する。

- 有効Root
- EffectiveZoneRange
- C・H
- Density
- Base Strong
- タッチ履歴
- Weak状態
- Phase
- Grade

有効な非心理Rootがない側はUnavailable。

物理Zoneを二重生成せず、1つのZoneCoreに2つのSide Viewを持たせる。

---

## 5. クラスタリングとZone範囲

## 5.1 Mと密集度

初期値：

- M＝20ドル。
- DenseRatio＝50%。
- 高密集幅＝M × DenseRatio＝10ドル。

Mは中心からの距離ではなく、EffectiveZoneRangeの全体幅。

- 幅が高密集幅以下：High Density。
- 高密集幅超〜M以下：Normal Density。
- M超：同じ通常Zoneにしない。

等号は狭い側へ含める。

### 数珠つなぎ禁止

A-B、B-Cが近くても、A-C全体がMを超える場合は1Zoneにしない。

## 5.2 Dense core優先

Base Strongを満たすDense coreは、M以内の通常結合より優先する。

1. 高密集幅以内の候補を作る。
2. Base Strong条件を満たせばStrong coreとして確定。
3. core外Rootは、M以内でもStrong Zoneへ入れない。
4. core外RootはAdjacent Rootまたは別Zone候補。
5. Base Strong coreがない場合にだけ、M以内の通常クラスタを作る。

Rootが増えたことによって、既存のDense StrongがNormal Densityへ広がり、Neutralへ落ちることを防ぐ。

## 5.3 クラスタ競合

同じSide Viewで複数Dense core候補がRootを奪い合う場合、次の順で決定する。

1. Cが多い。
2. Hが多い。
3. EffectiveZoneRangeが狭い。
4. 先に確定したcore。
5. 完全同条件なら固定Root ID順。

選ばれたcoreへ通常Rootを割り当て、残Rootで再度候補を作る。

同じ通常Rootを、同方向の複数Zoneへ二重参加させない。

例外としてBroad FVGは複数局所Zoneへ参加可能。ただしBroad FVGの共有だけではZoneを結合しない。

## 5.4 点Rootの範囲

- 参加実価格の最安値〜最高値。
- Rootが1本なら一本線。
- 一律の中心±5ドル方式は使用しない。
- 描画上の太さをロジックへ使わない。

## 5.5 FVGの範囲

- 通常FVG単独：NativeRange全体。
- FVG内部に局所Root：局所Rootの実分布。
- Proximal外側にRootが高密集：Proximal edge〜局所Root分布。
- 同方向FVG重複：実際の共通区間。
- Broad未局所化：NativeRangeをBroad contextとして保持。

M、Density、タッチ、Weak、ローカルBreak、Zone結合にはEffectiveZoneRangeを使う。

広いNativeRangeを使って、離れたZoneを橋渡ししない。

## 5.6 ZoneReferencePrice

ZoneReferencePriceは表示・追跡用であり、Rootではない。ロジック判定にも使わない。

点Rootカテゴリ：

- 同カテゴリ内の重複イベントを除外。
- 局所参加Rootの中央値をカテゴリ代表の基本とする。
- 各点カテゴリ代表の単純中央値をZoneReferencePriceとする。
- 品質による加重平均はしない。

MA：

- 他カテゴリcoreに近い実EMAを代表にする。
- MA単独で2本なら中間値は表示中心だけ。

FVG：

- 内部に別カテゴリRootがあれば、FVGを中央値へ入れない。
- Proximal局所化なら実際のProximal edgeを代表にできる。
- FVG重複だけなら、共通区間の接近側Proximal edge。
- FVG単独なら接近側Proximal edge。
- 50%地点は使わない。

強度判定ではFVGもCへ1加算するが、基準価格計算へ人工的な1票を作らない。

## 5.7 複数Zoneの重なり

- Dense coreと競合割当後のRoot構成で判定。
- Mを超える別coreは、範囲が一部重なっても別Zone。
- Broad FVG共有だけでは結合しない。
- ZoneEngineは該当Zoneをすべて返す。
- エントリー優先順位と同時シグナル抑止はSignal側で決める。

---

## 6. Category品質とBase Strong

## 6.1 品質集約

- 品質はNormal／Highの2段階。
- 1カテゴリにつきHへ最大1。
- EffectiveZoneRangeへ実際に参加するRootだけ評価。
- Adjacent Rootとcore外Rootは品質を上げない。
- Support／Resistanceごとに再評価。
- ActiveTouch開始後はSnapshot品質を固定。

High条件一覧：

| カテゴリ | High条件 |
|---|---|
| MA | EMA2本＋高密集＋対象方向へ同傾斜 |
| Swing | 1時間足、または同一転換点の15分足＋5分足 |
| Accum | 4時間足・日足、または異なる時間足の別Box重複 |
| 時間高安 | 現在週・前週・前日、または別起源の期間高安重複 |
| FVG | 非Broadの4時間足・日足、異なる時間足の同方向重複、有効なBroad局所化 |
| 心理価格 | Highにならない |

High条件を複数満たしてもHは1。

## 6.2 Base Strong

- C＝1：HighでもNeutralが上限。
- C＝2：High Densityかつ、少なくとも1カテゴリがHighならBase Strong。
- C＝3以上：High DensityならBase Strong。
- Normal Densityではカテゴリ数が多くても自動Strongにしない。

補足：

- 心理価格はCへ数えるが、2カテゴリ判定のHigh側にはなれない。
- Broad FVGは有効局所化部分でだけHigh側になれる。
- 方向無効FVGはCへ数えない。
- 同カテゴリRoot数はCへ加算しない。

## 6.3 点数制

新Zoneでは合計加点式をStrong／Weak判定へ使わない。

- EMA2本を別加点しない。
- 複数時間足を別カテゴリ加点しない。
- 過去反応を加点しない。
- 点数不足をWeakにしない。
- 旧スコア式はLEGACY専用。

診断表示：

- C
- H
- Density
- Current／Upcoming Touch
- Phase
- Grade
- WeakReason

---

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

## 11. Snapshot・LiveStructure・PendingTopology

## 11.1 TouchStartSnapshot

タッチ開始時に固定する。

- EffectiveZoneRange上下端
- 参加Rootとカテゴリ
- 各カテゴリ品質
- C・H・Density
- TouchStartGrade
- CurrentTouchNo
- 接近方向

過去記録として絶対に書き換えない。

## 11.2 LiveStructure

現在の使用可否を管理する。

- Root無効化は確定時点で即時反映。
- 無効Rootは新規判定・シグナルへ使わない。
- 残RootでSide Viewを再計算。
- RootがなくなればUnavailable。

## 11.3 ActiveTouchOutcome

- Episode終了までSnapshot範囲で侵入、Break、離脱を記録。
- Rootが途中無効化されても開始済み観測記録を捨てない。
- 無効化後の古い構造から新規シグナルは出さない。
- 過去TouchStartGradeは維持。

## 11.4 PendingTopology

ActiveTouch中に発生した次は、現在Episodeへ後付けしない。

- 新Root
- EMA移動
- 時間高安更新
- Root失効
- Zone結合
- Zone分裂
- 新世代候補

関係するActiveTouch終了後に適用する。

ただしRoot参加資格の喪失はLiveStructureへ即時反映し、形状再編だけを終了後へ送る。

Episode終了後：

1. PendingTopology反映。
2. 再クラスタリング。
3. 実タッチ価格・時刻で履歴を割り当て。
4. 新範囲と現在価格の距離を確認。
5. WaitingまたはArmedを決定。

---

## 12. Zone同一性・結合・分裂

## 12.1 同一性

次の両方で追跡する。

- 前回と同じ起源IDのRootを1つ以上共有。
- 前回範囲との価格的連続性がM以内。

中央値移動だけでは新Zoneにしない。

同じRoot IDでも不連続にMを超えて移動した場合は新世代。

Broad FVG起源IDだけでは局所Zoneの同一性を決めない。

## 12.2 結合

- Rootを統合して再計算。
- タッチ履歴をゼロにしない。
- 同時刻・同接触を1回へ統合。
- 新範囲へ実際に接触していた履歴だけ引き継ぐ。
- ActiveTouch中はPendingTopology。

## 12.3 分裂

- 子Zoneごとに、該当価格部分へ実際に接触した履歴だけ引き継ぐ。
- 未接触の子Zoneは未タッチにできる。
- 実タッチ価格・時刻を保存して所属先を決める。
- ActiveTouch中はPendingTopology。

---

## 13. 新しいZone世代

### 対象となる旧状態

1回以上のタッチ履歴がある、または次の状態。

- Weak
- Neutral
- タッチ済みStrong
- Broken
- FlipWait

未タッチZoneは履歴リセット不要なので、同世代へRoot追加。

ActiveTouch中はPendingGeneration。

### 必須条件

1. 直近のTouchStartSnapshot、タッチがなければBreakSnapshotまたは世代開始時構造になかった独立カテゴリが新たに確定。
2. 同カテゴリRoot追加だけでは不可。
3. EMA移動による重なりだけでは不可。
4. 心理価格追加だけでは不可。
5. 新構造が対象方向でBase Strong。
6. 価格が新EffectiveZoneRangeからTouchResetDistance以上離れて終値確定。
7. その後に再接近。

全条件成立時：

- 旧世代を履歴として終了。
- 新世代開始。
- 両Side Viewのタッチ・Weak履歴を0へ。
- 旧世代のBroken／FlipWaitを引き継がない。
- 過去履歴は分析用に保持。

ActiveTouch中に条件が揃っても、現在タッチへ後付けせず、離脱後の再接近から開始。

---

## 14. Zoneの有効期間

- 有効な非心理Root、または明示的なFlip／Inverse待ちRootが1つ以上ある間は保持。
- Weakでも削除しない。
- ローカルBreakでも削除しない。
- 時間経過だけでは削除しない。
- 現在価格から遠い場合はDormantにできる。
- Rootが有効なら、復帰時に同じ履歴で再開。
- すべての有効Rootと待機Rootがなくなったら世代終了。
- 心理価格だけなら維持しない。
- 保存整理は古い、Dormant、Rootが少ないZoneから。

Dormant距離と保存上限は実装設定。

---

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

## 16. Fresh

### Zone Fresh

当該Zone世代で、どちら側からも通常タッチが一度も開始していない全体履歴属性。

- Strong／Neutral／Weakとは別。
- どちらか一方で通常タッチが始まれば終了。
- 新Zone世代でだけ復活。

### Side Fresh

各Side Viewで、通常タッチが一度も開始していない方向別履歴属性。

- SideTouchCountが0ならSideFresh。
- StrongUntilTouchを2以上にすれば、SideFreshではないStrongも存在。
- FlipAttempt、FlipConfirm、InverseConfirmは通常タッチではないため、SideFreshを消費しない。
- 過去に使われた側へ再Flipした場合、以前のSideFresh状態を復元。
- 新Zone世代で両側ともリセット。

### FVG Fresh

NativeRange固有の属性。

- Zone Freshとは別管理。
- NativeRangeへヒゲが入れば終了。
- 終了してもRootは直ちに無効にならない。

---

## 17. 出力と将来検証

ZoneEngineは少なくとも次を返せるようにする。

- Zone ID／Generation ID
- Side
- EffectiveZoneRange
- ZoneReferencePrice
- Phase
- Grade
- C・H・Density
- CurrentTouchNo／UpcomingTouchNo
- ZoneFresh／SideFresh
- WeakReason
- FVG方向・Fresh・構造状態

### Weak Break検証

Weakは将来、反発ではなくBreak方向のStrategy条件として検証する。

- Weak Supportへ上から接近：下抜け候補。
- Weak Resistanceへ下から接近：上抜け候補。

Weakだけで自動エントリーしない。

Strategy側で具体的なBreakトリガーを決める。

検証では次を分ける。

- WeakByTouchCount
- WeakByDepth
- WeakByBoth
- 実際にBreakしたか

Break結果を過去のWeak判定へ後付けしない。

---

## 18. 初期パラメータ

| パラメータ | 初期値 | 制約・用途 |
|---|---:|---|
| M | 20ドル | 0より大きい |
| DenseRatio | 50% | 0超〜100%以下 |
| 高密集幅 | 10ドル | M × DenseRatio |
| TouchResetDistance | 10ドル | 0より大きい |
| StrongUntilTouch | 1 | 1以上またはUnlimited |
| WeakFromTouch | 2 | 2以上またはOFF |
| WeakDepthPct | 50% | 0〜100%またはOFF |
| BreakBuffer | 2ドル | 0以上 |
| TouchTolerance | 0ドル | 0以上 |
| EMA Slope Lookback | 1分足60本 | 1以上 |
| Swing Pivot 5M | 10 | 1以上 |
| Swing Pivot 15M | 8 | 1以上 |
| Swing Pivot 1H | 6 | 1以上 |

数値は変更可能な入力とするが、ATRで自動変動させない。

例外としてAccum形成判定内のATRは、Accum検出ロジック固有の入力として使用する。

### 境界値

- 幅がMちょうど：同じZone可。
- 幅が高密集幅ちょうど：High Density。
- ResetDistanceちょうど：Armed。
- WeakDepthちょうど：Weak。
- Support Break：下端−BreakBuffer以下。
- Resistance Break：上端＋BreakBuffer以上。
- FVG Distalと同値：構造無効化しない。
- Touch：端と同値を含む。

価格比較前に最小ティックへ正規化する。

判定式では10ドル、2ドルなどを直書きせず、必ずパラメータ名を使う。

---

## 19. Zone定義へ入れないもの

- 4時間足・1時間足・15分足の上昇／下降／レンジ環境。
- エントリー方向の許可。
- DXY、Yield、Oil、Silver。
- 包み足、ピンバー、EMA Reject、強ローソク。
- 5分足・15分足のエントリー用FVG。
- TP、SL、RR、建値移動。
- 反発後最大値幅による加点。
- StrategyのWIN／LOSS。
- BOS。
- Order Block／Departure Baseの別カテゴリ追加。
- Fibonacci、Pivot Point、Trendlineなど、既存6カテゴリから派生する重複Root。

必要ならSignal／Strategy側、または検証側で扱う。

---

## 20. 実装段階で決めるもの

- Swing、Accum、FVG、Zoneの最大保存本数。
- Dormant距離。
- ラベル、色、表示優先順位。
- 同時に複数Zoneがタッチされた場合のSignal選択。
- LEGACYとの入力名・出力互換。
- Pine配列、request数、実行時間を踏まえたデータ構造。
- FlipAttemptの表示方法。
- Weak Break Strategyの具体トリガー。
- 実装後の検証期間と比較方法。

これらはZone論理定義を変更せずに決める。

---

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
