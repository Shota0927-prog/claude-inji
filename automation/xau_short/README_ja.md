# ゴールドショート自動化 — 第2段階「通知の受信・記録」(AU-2)

TradingView → Windows の受信処理 → (後段) XS の MT5、のうち **受信・記録まで** を実装したものです。
**実注文・MT5 接続・注文 API は一切ありません。** ローカルテストの成功は、TradingView / Windows / MT5 での動作確認ではありません。

AU-2 は AU-1 のレビュー指摘 (到着順・管理イベントの順序逆転・異常値・設定 ID の網羅性・建値管理用データ・Windows スクリプト)
への修正版です。AU-3 は AU-2 の再レビュー指摘 (TP_SET による SL の巻き戻り、claim 時点の期限再確認) への受信処理だけの修正で、
Pine の自動化コピーと通知仕様 (`xau-auto/2`、sid `…|AU-2`) は AU-2 のままです。

## 1. 構成

| パス | 役割 |
|---|---|
| `ZoneStrategyXAU.pine` (リポジトリ直下) | 通常版ゴールドショート (XA-23)。**変更していません** |
| `automation/xau_short/pine/ZoneStrategyXAU_Auto.pine` | 自動化専用コピー。通常版 + JSON 出力の追加だけ (生成: `tests/au_build.py`) |
| `automation/xau_short/cfg_fields.json` | 設定 ID に含める入力の一覧 (順序・型・初期値・グループ・除外理由)。生成元と同期 |
| `automation/xau_short/receiver/xau_receiver.py` | 受信・検査・記録 (Python 標準ライブラリのみ、SQLite) |
| `automation/xau_short/receiver/config.example.json` | 設定の雛形 (認証情報は含まない) |
| `start_receiver.ps1` / `stop_receiver.ps1` / `show_log.ps1` / `test_samples.ps1` | Windows の起動・停止・確認・サンプル試験 |
| `automation/xau_short/receiver/samples/` | ローカル用サンプル通知と生成スクリプト |
| `tests/au_build.py` / `tests/au_sim.py` / `tests/aur_sim.py` | コピーの生成元とテスト |

元ファイル: リポジトリ直下の `ZoneStrategyXAU.pine` (commit 7705907、XA-23)。末尾の改行 1 つを除いた SHA-256 は
`33ec2773…69c17` で、ユーザー提示の基準コードと一致します。

自動化コピーは通常版を生成元から組み立て直し、決まった追加だけを重ねます。追加を外すと通常版とバイト単位で一致します。
売買判定・注文・状態更新の行は 1 行も変えていません (TP 追加・建値移動も通常版どおり確定 5 分足)。

## 2. 通知仕様 (schema `xau-auto/2`)

TradingView の 1 アラート = 1 JSON。フィールド (この順、追加・欠落は拒否):

| フィールド | 内容 |
|---|---|
| `schema` / `sid` | `xau-auto/2` / `XAU-SHORT|XA-23|AU-2` |
| `cfg` | 設定値の列 (7 章)。受信側が SHA-256 を取り **設定 ID** として保存・照合 |
| `ev` / `key` / `tid` / `rank` | イベント種別 / 冪等キー `sid|ev|tid|bar_close` / 取引 ID / 同じ足の中の順序 |
| `sym` / `tf` | `OANDA:XAUUSD` / `5` |
| `bar_open` / `bar_close` / `sent` | 判断足の開始・終了時刻、送信時刻 (`timenow`)。いずれも UTC ミリ秒 |
| `side` / `otype` | `SHORT` (BAR の無建玉時は空) / `MARKET`・`LIMIT`・空 |
| `px` / `sl` / `tp` | イベントの価格 (下表)。小数 8 桁 (最小刻みへ丸めない)。なしは `null` |
| `o` / `h` / `l` / `c` | イベントの足の OHLC (PROV は形成中の値) |
| `info` | 経路・理由など (JSON エスケープ済み) |

| ev | rank | 意味 | px / sl / tp |
|---|---|---|---|
| `PROV` | 1 | 仮通知 (形成中の足。確定前に崩れることがある) | 参考価格 / SL / TP |
| `WAIT_START` | 5 | SATS 待機の準備 (Pine 内の条件待機。業者への指値ではない) | P0 / SL0 / TP0 |
| `ENTRY` | 10 | **確定した注文意図** (確定 5 分足で strategy.entry を出した分岐。約定通知ではない) | 参考価格 (成行は判断足終値、A は指値) / SL / TP |
| `CANCEL` | 20 | Strategy が自分の未約定エントリーを取り消した | – / SL / – |
| `TV_FILL` | 30 | TradingView 内の疑似建玉が約定 (確定足で検出) | **疑似約定価格** / SL |
| `TP_SET` | 40 | 約定確認後の TP 設定 (確定 5 分足) | 疑似約定価格 / SL / TP |
| `BE_MOVE` | 50 | 建値移動 (確定 5 分足、疑似約定価格基準) | 疑似約定価格 / 新 SL (= 疑似約定価格) / TP |
| `CLOSE_REQ` | 60 | 成行決済 (約定位置不適切 / RR 不足 / risk ≤ 0) | 疑似約定価格 |
| `TV_CLOSED` | 70 | 約定した足の中で決済まで成立 (疑似) | 疑似決済価格 |
| `TV_FLAT` | 90 | 疑似建玉がなくなった (SL / TP / 建値で終了) | 疑似決済価格 |
| `WAIT_END` | 95 | SATS 待機の終了 (期限 / SL0 到達) | P0 / SL0 / TP0 |
| `BAR` | 98 | 確定 5 分足ごと: OHLC と、この足の処理後の疑似建玉 | 終値 / 疑似 SL / 疑似 TP。`info` に `tv_state` / `tv_tid` / `tv_be` / `tv_fill` |

取引 ID:
- `T` + ENTRY 判断足の終了時刻。以後の CANCEL / TV_* / TP_SET / BE_MOVE / CLOSE_REQ も同じ ID を使います。
- `W` + 待機準備足の終了時刻、`P` + 仮の足の開始時刻、`B` + BAR の足の終了時刻。
- 連番ではないので、再読込・再起動で変わりません。

入力「自動化 JSON 出力」(初期 ON): ON ではこのコピーは JSON だけを送ります。OFF なら通常版と同じ文章アラートです。
入力「BAR 通知」も初期 ON です。どちらも出力形式だけの入力で、売買には影響しません。

## 3. 受信処理の 3 層 (記録・状態確定・後段実行可否を分離)

1. **記録 (`receipts`)**
   - 全受信を必ず 1 行記録します。不正・重複・内部エラーも含みます。
   - 状態は `ACCEPTED` / `DUPLICATE` / `REJECTED` / `ERROR`。理由と生の本文 (サイズ上限内) を保存します。
   - 数値・文字列は保存前に安全化します: 64 ビット整数の範囲外、非有限値は NULL、文字列は長さ上限で切ります。
   - 処理中の想定外例外も `ERROR` (`internal:<型>`) として記録し、HTTP は落ちません。
2. **事実と状態 (`events` / `tv_trades` / `tv_waits` / `tv_bars`)**
   - 検査を通った新しいイベントは、到着順にかかわらず事実として永続保存します。
   - 取引の状態は、その取引の全事実を `(bar_close, rank)` 順に **毎回再生して導出** します。
   - 各事実の適用状態は次のいずれかです:
     - `APPLIED`
     - `PENDING`: 前提の TV_FILL がまだ届いていない。再評価されます
     - `AFTER_TERMINAL`: 終了後の通知。再開させません
     - `CONFLICT`: 方向・疑似約定価格の不一致、停止値が改善しない、不正な遷移
     - `ORPHAN`: ENTRY 未着
     - `INFO` / `FACT`
   - ENTRY 前に届いた終了・取消 (TV_CLOSED / TV_FLAT / CANCEL) と WAIT_END も事実として残ります。
   - **管理イベントの整合 (AU-3)**:
     - TP_SET は 1 取引に 1 回だけ、TV_FILL と同じ足、SL は ENTRY の初期 SL のときだけ適用します。
       違えば `CONFLICT` (`tp_set_not_on_fill_bar` / `duplicate_tp_set` / `tp_set_stop_not_initial`)。
     - SL を緩める状態更新はしません (`stop_would_loosen`)。BE_MOVE は改善方向だけです。
     - 例: 建値移動 (SL 2600.4) の後の足に TP_SET (SL 2605) が届いても `CONFLICT` で、SL は 2600.4 のままです。
   - 疑似約定価格 (`tv_fill_px`) は注文判断時の参考価格 (`ref_px`) と別に保存します。
3. **後段実行可否 (`intents`)**
   - 対象: ENTRY / CANCEL / TP_SET / BE_MOVE / CLOSE_REQ / TV_CLOSED / TV_FLAT。
   - 1 イベントごとに「後段が使ってよいか (`eligible`)」「理由」「使い方 (`use`)」を記録します。
   - ENTRY を実行候補にできないのは、次のいずれかに当たる場合です:
     - その取引の終了・取消を既に知っている
     - 関連する SATS 待機が終了済み
     - より新しい取引を既に知っている
     - 実行候補の疑似建玉が残っている
     - 通知期限を超えた (設定時のみ)
   - 「より新しい取引」「建玉あり」の判定は最初の判断時だけ行います (保有中に見送ったシグナルは後で復活しない)。
   - 後から終了・取消を知った場合は取り消し (`revoked:`) だけを行い、復活はさせません。
   - 管理イベントが可になる条件 (`PENDING` は再評価で可になり得ます):
     - ENTRY が実行候補で、かつ適用状態が `APPLIED` であること
     - **(AU-3) 届いた時点で同じ取引のより新しい事実を既に受け取っていない**こと。
       遅れて届いた古い通知は `stale:arrived_after_newer_event` で、状態の再生には使っても実行候補にはしません。
     - その後に取引の終了が確定していないこと (`superseded:trade_ended_by:…`)
   - **適用範囲 (`scope`、AU-3)**: 後段がその通知から取ってよい値だけを明記します。
     - TP_SET は「TP だけ」(SL は TP_SET から取らない)
     - BE_MOVE は「発動の合図だけ」(SL は MT5 の約定価格から再計算し、通知の px / sl は使わない)
     - CLOSE_REQ は MT5 の約定価格で理由を再計算、TV_* は確認のみ
   - `claim(key)` は 1 キーにつき 1 回だけ成功する原子的な操作です (後段で同じイベントを二重実行しないため)。**第2段階では呼びません。**
     - 検査と取得は同じ書き込みトランザクション (`BEGIN IMMEDIATE`) で行います。別プロセスからでも、評価と取得の間に状態が変わりません。
     - **(AU-3)** `policy.max_age_sec` を設定した場合、ENTRY は取得時の現在時刻でも期限を再確認します。
       期限切れは `revoked:expired_at_claim` (以後も取得不可、再起動後も同じ)。未取得のまま期限を過ぎたものは再評価時にも取り消します。
     - 時刻は受信 (`received_ms`)・初回判断 (`first_decided_ms`)・最終判断 (`decided_ms`)・取得 (`claimed_ms`)・最終取得試行 (`last_claim_ms`) を分けて保存し、
       全取得試行を `claim_log` に残します。
     - AU-2 で作ったデータベースは起動時にこれらの列を追加して移行します (db_version 3)。
   - `use` の例:
     - BE_MOVE: `RECOMPUTE_BE_FROM_MT5_FILL`。TradingView の停止値をそのまま XS に適用しない
     - TV_FLAT: `REVIEW_TV_EXIT`。MT5 だけ保有が残る可能性
     - TP_SET: SATS は `SET_TP_FIXED_PRICE (TP0)`、Current は `RECOMPUTE_TP_FROM_MT5_FILL`
     - CLOSE_REQ: `RECOMPUTE_FROM_MT5_FILL`

MT5 の実建玉は `mt5_positions` (第2段階では一切書き込まない、`NOT_CONNECTED`) で、TradingView の疑似状態とは別です。

## 4. 検査一覧

- **形式**:
  - UTF-8 の厳密な JSON であること。NaN / Infinity / -Infinity / 1e400 などの非有限値、重複フィールド、未知フィールドは不可
  - 必須フィールドと型 (bool は数値扱いしない)
  - 文字列の長さ上限、イベント種別、キーと中身の一致、rank、tid の形
- **ID**: schema / sid / 銘柄 / 時間足 / cfg の SHA-256 (設定した場合)。
- **時刻**:
  - 範囲は 2000〜2100 年 (保存可能・妥当範囲の健全性チェック)
  - `bar_close − bar_open = 5 分`、5 分境界に揃っていること
  - tid と判断足の一致、管理イベントが ENTRY 足より後であること
  - 送信時刻が判断足の終了より前なら警告として記録
- **価格**:
  - 有限、0 より大きく 1e7 未満 (健全性チェック)
  - イベントごとの必須価格 (2 章の表)
  - 方向別の位置関係:
    - SHORT は ENTRY / WAIT_START / TP_SET で SL > 価格 > TP、PROV は SL > 価格
    - BE_MOVE は新 SL = 疑似約定価格かつ TP の反対側
  - OHLC の整合 (L ≤ O, C ≤ H)
- **方向**: SHORT 以外は拒否 (BAR の無建玉時は空を許可)。管理通知の方向が取引と違えば `CONFLICT`。
- **取引との整合**:
  - TP_SET / BE_MOVE / CLOSE_REQ の疑似約定価格が TV_FILL と一致すること
  - BE は停止値が改善方向であること
  - 状態遷移表に合うこと

## 5. 重複・順序

- **冪等キー** `sid|ev|tid|bar_close`:
  - Pine 側は varip の送信済みリストで同じキーを再送しません。
  - 受信側は主キーで 2 回目以降を `DUPLICATE` として記録します。再起動後も同じです。
- **到着順に依存しない再生**:
  - 例: ENTRY → TP_SET → TV_FILL の到着では、TP_SET は TV_FILL が届くまで `PENDING`、届いた時点で `APPLIED` になります。
  - 古い TP_SET が新しい BE_MOVE の後に届いても、足の順序で再生するので新しい停止値は上書きされません。
  - 終了・取消が確定した取引は再開しません。
- 後段の二重実行防止は `intents.claimed_ms` と `claim()` で行います。

## 6. 後段の建値管理用データ (今回は通知・記録まで)

`BE_MOVE` の停止値は TradingView の疑似約定価格が基準なので、**XS へそのまま適用してはいけません**。
`BAR` イベント (確定 5 分足ごとの時刻・OHLC、疑似建玉の状態) を売買と独立に記録しているので、後段は XS の実約定価格から通常版の建値判定を再現できます。

- **通常版の建値判定** (確定 5 分足ごと、保有中かつ未移動のとき):
  - 有利側の値 `fav` は Long なら `high`、Short なら `low`。
    - ただし、約定を確認した足で指値約定かつ約定価格 ≠ 始値のときは `close` を使います。
  - Trigger 幅 = Fixed Distance (初期 15 USD) / Risk Multiple (初期リスク距離 × R) / TP Progress (TP までの距離 × 比率)。
  - `side × (fav − 約定価格) ≥ Trigger 幅` で停止値を約定価格へ移します。有効になるのは次の足からです。
- **後段での再現**:
  - 約定価格は MT5 の実約定価格、OHLC は BAR を使います。
  - 判定する足: MT5 で約定した時刻を含む足から、各確定足で上の式を評価します。
  - 設定値は cfg に含まれます (`stBE` / `stBEMode` / `stBEDist` / `stBER` / `stBETp`)。
- **注意点**:
  - BAR は OANDA の価格で、XS の価格とは差があります。XS 自身の M5 足を使う案もあり、後段で決めます (7 章)。
  - TradingView が先に決済 (`TV_FLAT` / `TV_CLOSED`) して MT5 だけ保有が残る場合も、BAR は届き続けます。
  - TV_FLAT の intent は `REVIEW_TV_EXIT` とし、MT5 側をどう扱うか (追随決済・独立管理) は後段の決定事項です。

## 7. 設定 ID (cfg)

- `cfg` = `c2|` + 入力値を `|` でつないだ文字列です。
  - 並びは宣言順、bool は 1 / 0、整数はそのまま、小数は最大 10 桁 (末尾の 0 なし)、文字列はそのまま。
  - JSON 用にエスケープします。
- 受信側はこの SHA-256 を設定 ID として全受信に保存します。
- **対象**: 通常版の全入力 143 個のうち、**141 個** を含めます。
  - Zone (MA / Swing / Day H/L / Accum / RN / Cluster / Score / HTF / Break / Lifetime)
  - FVG、Entry (A〜D、ピン比率、D の待機本数)、SATS (待機・反発・近接・逆方向一致・即時・接触期限)
  - 時間帯、TP、建値、数量 (元金・損失率・lot 仕様)、通知 (仮・確定アラート)
  - 一覧と理由は `cfg_fields.json` にあります。
- **除外 2 個** (表示専用):
  - `stSatsShow`: SATS 線の plot だけに使用
  - `stLblConf`: 確定ラベルの表示だけに使用
  - 生成元が「表示にしか使われていない」ことをテストで確認しています。
- 出力形式の入力 (自動化 JSON 出力 / BAR 通知) は自動化コピー専用で、cfg には含めません。
- 固定手順: 初回の実通知の `cfg` を目で確認 → その SHA-256 を `config.json` の `expected.cfg_sha256` に設定します (以後の不一致は拒否)。
  - サンプルの cfg は初期値からの **予測値** で、TradingView の小数表記は未確認です。

## 8. Windows での操作 (次に行うこと)

前提: Windows に Python 3.10 以上 (python.org 版。`py` ランチャー推奨)。外部パッケージは不要です。

1. リポジトリ (または zip) を Windows に置き、PowerShell で `automation\xau_short\receiver` へ移動する。空白・日本語を含むパスでも構いません。
2. `Copy-Item .\config.example.json .\config.json`
3. Webhook 用のトークンを **ローカルだけで** 作り、ユーザー環境変数に保存する (チャット・コード・ログには書かない):
   ```powershell
   $t = py -3 -c "import secrets; print(secrets.token_urlsafe(32))"
   [Environment]::SetEnvironmentVariable("XAU_RECEIVER_TOKEN", $t, "User")
   ```
   その後 PowerShell を開き直す。
4. サンプル試験 (**実通知の保存先とは別の一時フォルダで実行。実データは消しません**):
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\test_samples.ps1
   ```
5. 起動: `powershell -ExecutionPolicy Bypass -File .\start_receiver.ps1`
6. 確認: `Invoke-RestMethod http://127.0.0.1:8787/health` → `orders: disabled`
7. 記録の確認: `powershell -ExecutionPolicy Bypass -File .\show_log.ps1` (`-Follow` でログ追従)
8. 停止: `powershell -ExecutionPolicy Bypass -File .\stop_receiver.ps1`
   - PID・コマンドライン (`xau_receiver.py` と `serve`)・起動時刻が一致するときだけ停止します。
   - PID が別のプログラムに再利用されていれば止めずにエラーを出します。
9. 記録は `data\xau_receiver.sqlite3` (再起動後も残る) と `data\receiver.log` (5 MB × 5 世代) にあります。

## 9. 外部 HTTPS の受信経路 (構成案のみ。契約・公開は未実施)

- TradingView の Webhook はインターネット上の HTTPS (443) / HTTP (80) の URL にしか送れません。
  受信処理は既定で `127.0.0.1:8787` だけで待ち受けます。
- **案 A: Cloudflare Tunnel (cloudflared)**
  - `https://<ホスト名>/webhook/<トークン>` を `http://127.0.0.1:8787` へ転送します。ポート開放は不要です。
  - 必要なもの: Cloudflare アカウント、ドメイン、cloudflared のサービス登録。
- **案 B: VPS のリバースプロキシ (nginx / Caddy + TLS) → VPN / SSH トンネルで Windows へ**
- **共通**
  - URL のトークンは秘密として扱います。TradingView の送信元 IP だけを許可する設定も推奨します (IP は TradingView の最新案内で確認)。
  - アラートは「alert() function calls only」で作成し、Webhook URL を設定します。コード更新後はアラートを作り直します。
- いずれも **未実施** です。

## 10. 後段へ引き継ぐ条件 (今回は実装していない)

- 損失予算 = 発注判断時の口座残高 × 3 %。円損失は発注のたびに MT5 の `OrderCalcProfit` 等で計算します。
  - 固定値・Tick Value の表示値だけでは決めません。取得時の参考値 (0.01 lot SELL で 1 ドル逆行 → −157 円) も固定値として使いません。
  - 通常版の数量計算 (元金基準額 × 3 %、単利) とは別物です。
- 最大 1 ポジション。保有中の追加シグナルは見送り。日次損失上限は追加しない。通常版を維持し、実注文の管理担当は一本化する。
- XS デモ仕様: XSFintech-DEMO / XAUUSDs / JPY / ヘッジ / 100 oz/lot / 0.01〜10 lot・刻み 0.01 / 価格刻み 0.01 /
  Stops・Freeze 0 (取得時) / スプレッド変動 (取得時 0.18) / 手数料未確認。

## 11. 未決定事項 (提案のみ。採用していません)

| 項目 | 現状 | 提案 (承認待ち) |
|---|---|---|
| 通知期限 `policy.max_age_sec` | 無効 (経過時間を記録)。設定時は受信時・再評価時・取得時に ENTRY を確認 | ENTRY は判断足終了から 60〜90 秒 |
| 管理イベントの期限 | なし (TP_SET / BE_MOVE / CLOSE_REQ は時刻で失効しない) | 後段の設計時に決める (例: BE は次の足の確定前まで) |
| 未来時刻の許容 `policy.max_future_skew_sec` | 無効 (差を記録) | 5〜10 秒 (Windows の時刻同期を前提) |
| 価格ずれ | 未実装 | 参考価格からの乖離が SL 幅の 20〜30 % 超で見送り |
| スプレッド上限 | 未実装 | XS の実測分布を見て決める (例 0.50 USD) |
| 手数料 | 未確認 | MT5 の約定履歴で確認後に損失予算へ含めるか決める |
| 切り下げ・最小数量 | 未実装 | 0.01 lot 未満は見送り |
| 指値中の残高変化 | 対象なし (初期は成行のみ) | Entry A を使う場合だけ検討 |
| 最大 1 件の適用範囲 | 未決定 | Strategy (magic 番号) 単位か口座単位か |
| 建値判定の価格源 | BAR (OANDA) を記録 | OANDA の BAR か XS の M5 足か |
| TradingView 先行決済時の MT5 | 記録のみ (`REVIEW_TV_EXIT`) | 追随決済か、MT5 側で独立管理か |
| BAR の頻度 | 常時 (1 日 288 件) | 常時のままか、保有中・決済後 N 本だけにするか |
| 週末制限 | **現コードに曜日制限はない** (時間帯だけ) | 運用上の希望 (例: 金曜深夜以降の新規見送り) は別途決定 |
| cfg の固定 | 未設定 (`warn:cfg_unpinned`) | 初回の実通知を確認してから設定 |

健全性の範囲 (時刻 2000〜2100 年、価格 0〜1e7、文字列長) は保存・形式のための値で、売買の閾値ではありません。

## 12. 未検証の部分

- 自動化コピーの TradingView 上でのコンパイル、実アラートの JSON 本文。次の点も実機で確認が必要です:
  - `str.tostring` の `#.##########` / `#.########` の表記、`str.replace_all` のエスケープ
  - 1 本の足での alert 数 (最大 5 程度) とアラート頻度の制限
  - 通知の長さ (cfg を含めて約 1.5 KB) の上限
- 確定足での `timenow` と `time_close` の前後関係 (送信時刻の警告として記録のみ)、TradingView の再送挙動、Webhook の実配信
- Windows 上での PowerShell スクリプトの実行
  - この環境は Linux で PowerShell がないため、スクリプトは静的確認のみです。Python 部分は Linux で試験済み。
- 外部 HTTPS 経路、MT5 との照合 (後段)
