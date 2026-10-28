# ゴールドショート自動化 — 第3段階「デモEA」(ST3-1)

**現状**
- 今回はコード・設計・ローカル試験までです。
- MQL5 のコンパイルは**未実施**です (この環境に MetaEditor / MT5 がありません)。
- MT5 デモでの動作確認も**未実施**です。
- 「発注動作確認済み」「EA完成」ではありません。デモ環境での確認は、ご本人の Windows / MT5 で行っていただく必要があります。

**変えていないもの**
- 通常版 `ZoneStrategyXAU.pine`、ロング版、Engine、取引条件、input 初期値
- Auto 版 Pine と受信処理 (`receiver/xau_receiver.py`)

| 区分 | 内容 | 状態 |
|---|---|---|
| Python 試験 | bridge (`tests/eab_sim.py`)、EA 規則の Python 参照モデル (`tests/ea_model.py` + `tests/eam_sim.py`)、MQL5 ソースの静的照合 | 実施 (結果は §10) |
| MQL5 コンパイル | `ea/XauShortDemoEA.mq5` | **未実施** |
| MT5 デモ実地 | 発注・取消・SL・TP・建値・再起動・異常系 | **未実施** (第4段階) |
| 実シグナルとの突合 | 約 10 取引日 | 未実施 (第5段階) |

---

## 1. 構成と責務

```
TradingView (ZoneStrategyXAU_Auto, シグナル源・判断はここだけ)
   │ Webhook (既存。Cloudflare Quick Tunnel → 127.0.0.1:8787。公開範囲は変更しない)
   ▼
receiver/xau_receiver.py   … 変更なし。受信・記録・事実の確定・実行候補 (intents) の判定のみ
   │ SQLite (同じ PC 内のファイル。bridge は claim() 以外は読むだけ)
   ▼
bridge/ea_bridge.py        … 新規。ENTRY だけを再検査して claim → コマンドファイルを書く / EA の報告を取り込む
   │ ファイル交換: %APPDATA%\MetaQuotes\Terminal\Common\Files\XauShortDemo\{cmd,rpt,done,rpt_done}
   ▼
ea/XauShortDemoEA.mq5      … 新規。発注判断の最終確認・唯一の取引 API 呼び出し・自分の建玉の SL/TP/建値管理・記録
```

| 部品 | すること | しないこと |
|---|---|---|
| receiver | 通知の受信・記録・重複排除・TradingView 仮想状態・実行候補の判定 (第2段階のまま) | 発注・EA との通信 |
| bridge | 実行候補 ENTRY の再検査 (SHORT / MARKET / SATS 経路 / sid / cfg / 銘柄 / 60 秒 / 時計) → `claim()` → コマンド書き出し。EA 報告の取り込み、ライフサイクル記録 (bridge.sqlite3)、乖離 (TradingView 終了 vs MT5 保有) の記録 | 取引 API、ネットワーク待受、receiver の受信記録・設定の書き換え、ENTRY 以外の転送 |
| EA | 口座・銘柄の照合、期限・価格乖離・スプレッド・ロット・証拠金の最終確認、新規成行 SELL (初期 SL 付き)、約定確認、SL 欠落時の緊急決済、TP0 設定、建値移動、終了記録、起動時照合 | TradingView の BE_MOVE / TV_FLAT / CANCEL / CLOSE_REQ に従うこと、手動・他 EA の注文や建玉に触れること |

### 通信方式: ファイル交換を選んだ理由

MT5 の **共通フォルダ (Terminal\Common\Files)** を使います。

- **外部公開が増えない。** ネットワーク API を新設しないので、Cloudflare の公開範囲は今のまま (Webhook のみ) です。
- **EA の認証が不要。** 同じ PC・同じ Windows ユーザーのファイル権限で閉じます。WebRequest の URL 許可やトークン管理が要りません。
- **原子的に受け渡せる。** bridge は `.tmp` に書いてから `.cmd` に改名します。EA も `.tmp` → `.rpt` で報告します。読み手は完成したファイルしか見ません。
- **再起動に強い。** 処理済みファイルは `done/` と `rpt_done/` に残ります。二重処理は永続記録 (EA の journal、bridge の DB) で防ぎます。
- 不採用案:
  - EA → receiver への HTTP (WebRequest): URL 許可・トークン・待受の拡張が必要になります。
  - 名前付きパイプやソケット: MQL5 標準では扱いにくく、再起動時の取りこぼし設計も重くなります。

---

## 2. 仕様 ⇔ コード対応表

| 仕様 (承認済み) | 実装箇所 | 試験 |
|---|---|---|
| 既定は DRY_RUN・新規 OFF、取引 API 書込み全面禁止 | EA `InpDryRun=true` / `InpAllowNewEntries=false`、全書込みは `TradeWritesAllowed()` を通る (OrderSend は 3 か所のみ) | EAM-03, EAM-31, EAS-01, EAS-03 |
| デモ口座の実行時確認。設定だけで本番を許可できない | `OnInit` で非デモは `INIT_FAILED` (入力では変更不可)、書込みの都度 `IsDemoAccount()` + ログイン + サーバー | EAM-01, EAM-02, EAM-30, EAS-04 |
| XSFintech-DEMO / XAUUSDs / JPY / ヘッジ口座、口座・サーバー・銘柄・設定 ID 照合 | `VerifyEnvironment()` (起動時+タイマー毎)、`CheckCmd()` (sid / cfg / TV 銘柄) | EAM-02, EAM-28 |
| ログイン番号は PC 上で設定、パスワードは扱わない | 入力 `InpExpectedLogin` (既定 0 = 書込み不可)。パスワード欄なし | EAS-01 |
| 起動時、照合完了まで発注しない | `g_ready` は `Reconcile()` 後に true | EAS-04 |
| DRY_RUN と「新規だけ止めて既存は保護継続」スイッチの区別 | `InpAllowNewEntries=false` / `halt_new` ファイル / 自動停止 (HALT_NEW) は新規のみ停止 | EAM-04 |
| 確定 SHORT ENTRY のみ・成行のみ。LIMIT は記録して見送り (成行化しない) | bridge `_check` (skip:limit_not_supported)、EA `CheckCmd` (limit_not_supported) | EAB-06, EAM-28 |
| PROV / WAIT_* / BAR / TV_FILL は新規の根拠にしない | bridge は ENTRY 以外を転送しない。EA は ENTRY 以外を `not_entry` | EAB-05, EAB-07, EAM-24 |
| 期限 60 秒 (受信時・claim 時・送信直前)、待機や再起動で復活しない、負の経過は不合格 | bridge `_check` → receiver `claim()` (ロック取得後に判定) → EA `CheckDeadline()` (読込時と OrderSend 直前)。1 秒分解能は「遅い側」で期限、「早い側」で未来判定 | EAB-08, EAB-09, EAB-11, EAM-05, EAM-06 |
| 価格乖離 abs(Bid − px) ≤ 20 % × (sl − px)、SL 幅 ≤ 0 は拒否 | `PrepareOrder` | EAM-07 |
| スプレッド Ask − Bid ≤ 0.50 USD | `PrepareOrder` | EAM-07 |
| 取引時間は Pine の時間条件 (=通知が来る時) + XS の実取引可否 | `InTradeSession()`、`SYMBOL_TRADE_MODE`、口座・端末の取引許可 | EAM-09 |
| ロット: 判断直前残高 × 3 %、価格 = その時点の Bid、OrderCalcProfit、ステップ切捨て、最小ロット超過は見送り、最大・証拠金・計算失敗で中止 | `PrepareOrder` | EAM-08, EAM-09 |
| 価格を tick に丸めたら最終価格で再計算、SL は広げない | SL はショートで下方向 (エントリー側) へ丸め、最終 price / sl で損失を再計算 | EAM-10 |
| 手数料・スワップは予算外で別記録、3 % 超過の可能性を表示 | DECIDED / DRY_RUN_NOT_SENT の `note=`、CLOSED に commission / swap | EAM-08 |
| 最大 1 (口座全体、手動・他 EA を含む)、保有中に見送った信号は後で出さない | `PositionsTotal()` / `OrdersTotal()` > 0 で見送り、見送りは journal に残り重複扱い | EAM-11 |
| 送信中・結果不明も枠を占有、多重起動で同じ注文を出さない | `g_inflightKey` + HALT_NEW、EA は `ea.lock` 排他、bridge は `bridge.lock` 排他 + receiver の原子的 claim | EAM-13, EAM-27, EAB-03, EAB-04 |
| 変更・決済は自システムの建玉だけ (永続記録 + 実チケットで確認) | journal の FILLED 記録のチケット + 銘柄 + magic が一致した建玉だけを管理 | EAM-26, EAM-15 |
| 初期 SL を新規注文に付ける。SL なしに落とさない | 要求に `req.sl` 常時。SL が付かないなら送らない | EAS-08 |
| 約定後に SL 欠落 → 自分の建玉を緊急決済 + 新規停止。失敗は重大エラー | `CheckProtection()` → SL_MISSING / EMERGENCY_CLOSE / CRITICAL | EAM-17, EAM-18 |
| TP: SATS 処理を再現、TP0 は準備時固定、通常版の約定確認に当たる確定足で設定 (約定直後にしない)、SL を戻さない | `ManageOwn()` で MT5 約定足の確定時に TP0、SL は現状維持 | EAM-19 |
| 建値: 確定 5 分足で Fixed Distance 15 USD、XS 実約定価格へ、約定前の安値を使わない、BE_MOVE を XS に適用しない | `ManageOwn()` / `TryBreakeven()` (約定足は約定後の Bid のみ、以後は確定 M5 足の安値) | EAM-21 |
| TradingView が先に終了しても MT5 を追随決済しない、乖離を記録 | bridge `check_divergence()` は記録のみ、EA へは何も送らない | EAB-15, EAM-24 |
| CLOSE_REQ は XS 実約定と実建玉で再確認 | 約定足確定時に XS 約定価格で SL0 / TP0 の外側なら決済 (FILL_SIDE_BAD) | EAM-25 |
| CANCEL を約定済み建玉の決済に置き換えない | CANCEL は転送しない・EA は not_entry | EAM-24 |
| TP / 建値変更の失敗: 既存 SL 維持・新規停止・照合・記録 | `ModifyOwn()` 失敗 → MODIFY_FAILED + HALT_NEW、SL を緩める変更は送信前に拒否 | EAM-20, EAM-22, EAM-23 |
| claim =「通知を一度取得した」であり約定ではない | receiver `claim()` と bridge の CLAIMED / CMD_WRITTEN は EA の FILLED と別状態 | EAB-01, EAB-14 |
| 状態・時刻を分けて保存 | bridge `lifecycle` の 15 時刻列 + EA journal (下記 §3) | EAB-14, EAB-16 |
| キー / 取引 ID ↔ 注文・約定・ポジションチケット | bridge `lifecycle.ea_order / ea_deal / ea_position`、EA journal FILLED | EAB-14 |
| 送信前記録後のクラッシュ / 送信後無応答 / 結果通知だけ消失の区別、結果不明は再発注しない | PRE_SEND あり結果なし → 起動時 UNKNOWN、タイムアウト等 → UNKNOWN、約定済みで返答消失 → 起動時照合で RECONCILED (自動採用しない) | EAM-13, EAM-14, EAM-15 |
| OrderSend の true は約定確定ではない | 約定は deal → position (銘柄・magic・SELL) で確認、PLACED 等は UNKNOWN | EAM-16 |
| 認証用 URL・トークン・パスワードをログ・zip に入れない | bridge / EA ともトークンを読まない。設定例に秘密なし。`.gitignore` | EAB-18, EAB-19, EAS-01 |
| Cloudflare 公開範囲を EA 操作 API に広げない | ネットワーク API を新設しない (ファイル交換) | EAB-18 |
| 実通知・試験通知の保存先を分ける、実記録を消さない | 設定例は TEST フォルダ、`make_test_entry.py` は名前に test を含むフォルダ以外を拒否、bridge は受信記録・設定を書き換えない | EAB-17, EAB-18 |

---

## 3. 状態遷移

### bridge (bridge.sqlite3 `lifecycle`、キーごと)

```
(intents: ENTRY eligible=1 未claim)
   → CHECKED ─(検査不合格)→ SKIPPED_BY_BRIDGE  (reason: skip:limit_not_supported / skip:expired_before_claim / skip:clock_or_future_bar ...)
   → CLAIMING ─(receiver が拒否)→ CLAIM_REFUSED (expired_at_claim / already_claimed / bridge_restart_before_claim ...)
   → CLAIMED ─(再起動時、期限切れ)→ EXPIRED_AFTER_BRIDGE_RESTART
   → CMD_WRITTEN
   → EA_SEEN → EA_SKIPPED | EA_DRY_RUN_NOT_SENT | EA_DECIDED → EA_PRE_SEND → EA_SEND_RETURNED
        → EA_REJECTED | EA_UNKNOWN (→ EA_RECONCILED / EA_UNKNOWN_NOT_FOUND)
        → EA_FILLED → EA_PROTECTED | EA_SL_MISSING → EA_EMERGENCY_CLOSE | EA_CRITICAL
        → EA_TP_SET → EA_BE_SET → EA_CLOSED   (EA_MODIFY_FAILED は途中で入り得る)
```

時刻列は別々に保存し、最初の到達時刻を保持します。
- bridge 側: `received_ms`, `checked_ms`, `claim_start_ms`, `claimed_ms`, `cmd_written_ms`
- EA 側: `ea_seen_ms`, `ea_decided_ms`, `ea_pre_send_ms`, `ea_send_ms`, `ea_result_ms`, `ea_filled_ms`, `ea_protected_ms`, `ea_managed_ms`, `ea_closed_ms`, `ea_unknown_ms`

### EA (Common\Files\XauShortDemo\journal.txt、追記のみ)

1 行は `t_ms|key_hash|STATE|k=v;...` です。key_hash は SHA-256(key) の先頭 16 桁で、key に `|` を含むため。同じ内容を `rpt/` に報告します。

- 起動: `START` → (照合) `UNKNOWN` / `RECONCILED` / `UNKNOWN_NOT_FOUND` / `OWNED_AT_STARTUP` / `HALT_NEW` …
- 新規: `SEEN` → `SKIPPED` | `DRY_RUN_NOT_SENT` | `DECIDED` → `PRE_SEND` (送信前に必ず書く) → `SEND_RETURNED` → `FILLED` (+ `PARTIAL_FILL`) → `PROTECTED` | `SL_MISSING` → `CLOSE_PRE_SEND` → `CLOSE_SENT` / `CLOSE_FAILED` → `EMERGENCY_CLOSE` / `CRITICAL`
  - それ以外の送信結果は `REJECTED` | `UNKNOWN`
- 管理: `TP_SET` / `BE_SET` / `MODIFY_FAILED` / `MODIFY_REFUSED` / `FILL_SIDE_BAD` / `MANAGEMENT_BLOCKED` / `CLOSED` (reason=sl / tp / expert / manual / other)
- 運用:
  - `HALT_NEW` / `RESUME_NEW` / `RESUME_REFUSED` / `CRITICAL_CLEARED`
  - `ENV_OK` / `ENV_LOST`
  - `DUPLICATE` (報告のみ) / `BAD_CMD` / `TX_DEAL` (記録のみ) / `STOP`

### 結果不明の扱い

| 状況 | EA の扱い |
|---|---|
| PRE_SEND の後にクラッシュ | 起動時に `UNKNOWN (pre_send_without_result_at_startup)` + HALT_NEW。再発注しない |
| 送信したが応答がタイムアウト / 接続断 / PLACED 等 | `UNKNOWN` + HALT_NEW、枠は占有のまま |
| 約定したが返答だけ消えた | `UNKNOWN`。再起動時に「銘柄 + magic + コメント `XSD:<key_hash>` 完全一致 + PRE_SEND 以後」で建玉を探して `RECONCILED` を記録。**自動では管理対象に採用しません**。口座全体最大 1 なので新規も出ません |
| 解除 | 実際の注文・建玉・履歴を MT5 で確認してから、`resume_new` ファイルを置く (§7) |

---

## 4. 未決定事項と推奨 (いずれも発注 OFF で検証可能。取引結果を変える置換は行っていません)

| 項目 | 推奨 | 理由 / 実装の状態 |
|---|---|---|
| 建値判定の価格源 | **XS の価格 (M5 足の Bid 安値、約定足は約定後の Bid)** | XS の建玉を動かす判断なので XS の価格で判定し、OANDA の BAR は記録・比較に使う。EA はこの推奨で実装済み。比較は第5段階で |
| 約定足の約定前の値動きを除く方法 | **EA が約定後に見た Bid の最安値だけを使う** (`InpFillBarBe = FILLBAR_TICKS_SINCE_FILL`)。再起動で見ていない区間がある場合は約定足を使わない | 足の安値は約定前の値を含み得る。別案 `FILLBAR_SKIP` (約定足は使わない) も入力で選べる。どちらにするかはご判断ください |
| TV と MT5 の約定時刻がずれたときの TP「対応する確定足」 | **MT5 の約定が入った M5 足 (サーバー時刻) の確定時** | ENTRY 足確定から 60 秒以内に送るため、通常は TradingView の仮想約定と同じ足になる。ずれた件数は bridge の記録 (TV_FILL と ea_filled_ms) で数えられる |
| TP0 設定時点で既に価格が TP0 を越えていた場合 | 現在は TP 変更が拒否され MODIFY_FAILED → 新規停止 → 次の足で再試行 (SL は維持)。**提案: その時点で成行決済 (Pine で指値 TP が即約定するのと同等)** | 取引結果を変える判断なので未実装 |
| 遅れた管理通知 | **使わない** (EA が自分で管理) | bridge は ENTRY 以外を転送しない |
| 通信監視 | bridge `status`、EA のチャート表示 (Comment)、`rpt/` の滞留。**提案: EA の心拍ファイルと bridge 側の滞留警告** | 未実装 |
| 再試行間隔 | TP0 / 建値の変更失敗は **M5 足 1 本に 1 回**。新規注文は再試行しない | 毎タイマー再試行による過剰送信を防ぐ |
| 時計ずれの許容 | **許容幅を設けない** (負の経過は不合格、期限は遅い側で判定)。Windows の時刻同期を運用で確認 (`w32tm /query /status`) | 未決定の許容幅は追加していない |
| 部分約定 | **実約定数量を保護・管理し、不足分の追加発注はしない** (PARTIAL_FILL を記録) | 平均価格は建玉の `POSITION_PRICE_OPEN` |
| XS デモが初期 SL 付き成行を受け付けるか | **デモで最初に確認** (§8 の 1)。拒否 (INVALID_STOPS 等) なら REJECTED になるだけで、SL なし発注には落としません | 未確認 |
| 約定方式 (filling) | FOK → IOC → RETURN の順で銘柄の対応方式を選ぶ | XS の実際の方式はデモで確認 |

---

## 5. 完全な排他の限界 (正直な制約)

- **口座全体の最大 1 は「判断の瞬間」の確認です。**
  - EA が `PositionsTotal()` / `OrdersTotal()` を見てから約定するまでの間に、手動や他 EA が注文を出すと、両方が建つことはあり得ます。
  - MT5 には口座単位のロックがありません。
- **magic とコメントは他の EA でも同じ値を付けられます。**
  - そのため、管理対象は「journal の FILLED 記録のチケット」+「銘柄・magic の一致」で決めます。
  - コメントは結果不明時の探索の手掛かりにだけ使います。
- **ブローカーはコメントを書き換えることがあります** (決済時の `[sl]` 等)。
  - 結果不明の探索で見つからない場合があります。その場合も再発注はせず、手動確認を求めます。
- **EA を止めている間は自動の TP0 / 建値移動が行われません。**
  - 注文時に付けた初期 SL はサーバー側に残ります。
  - DRY_RUN に切り替えた場合も同じです。DRY_RUN は「すべての書込み停止」です。
  - 新規だけを止めたい場合は `InpAllowNewEntries=false` または `halt_new` ファイルを使ってください。
- **EA の時計は PC の時計 (TimeGMT、1 秒分解能) です。**
  - 期限側は最大 1 秒厳しめに判定します (60.0 秒ちょうどは期限切れ)。

---

## 6. ファイル

| パス | 内容 |
|---|---|
| `automation/xau_short/STAGE3_ja.md` | この文書 |
| `automation/xau_short/bridge/ea_bridge.py` | bridge 本体 (標準ライブラリのみ) |
| `automation/xau_short/bridge/bridge_config.example.json` | 設定例 (TEST フォルダ向け、秘密情報なし) |
| `automation/xau_short/bridge/make_test_entry.py` | TEST フォルダへ試験用 ENTRY を 1 件入れる (実データ用フォルダは拒否) |
| `automation/xau_short/bridge/.gitignore` | 実設定・データ・ログを git に入れない |
| `automation/xau_short/ea/XauShortDemoEA.mq5` | デモ EA (未コンパイル) |
| `tests/ea_model.py` | EA 規則の Python 参照モデル + 疑似 MT5 |
| `tests/eab_sim.py` / `tests/eam_sim.py` | 試験 |

---

## 7. Windows での手順

前提:
- receiver は README_ja.md の手順で動いていること。`start_receiver.ps1` が終了コード 2 になる件は未解決なので、従来どおり Python を直接起動して構いません。
- Python 3.10 以上。

### 7.1 EA の配置とコンパイル

1. MT5 (XSFintech-DEMO にログイン済み) で **ファイル → データフォルダを開く** → `MQL5\Experts` に `XauShortDemoEA.mq5` をコピーします。
2. MetaEditor でこのファイルを開き **コンパイル** します。
   - エラー・警告は全文を控えてください。
   - こちらでは未コンパイルのため、修正が必要な箇所が出る可能性があります。結果を共有いただければ直します。
3. MT5 の **ツール → オプション → エキスパートアドバイザー** で「アルゴリズム取引を許可」を確認します。
   - DRY_RUN 中は不要ですが、ON にしても EA は書き込みません。
   - WebRequest の URL 追加は不要です。

### 7.2 DRY_RUN (発注なし) の開始

1. XAUUSDs の M5 チャートに EA をドラッグします。入力は次のとおりです。
   - `InpDryRun = true` (既定のまま)
   - `InpAllowNewEntries = false` (既定のまま)
   - `InpExpectedLogin` = **デモ口座のログイン番号** (PC 上で入力。パスワードはどこにも入力しません)
   - `InpExchangeDir`:
     - 試験時は `XauShortDemoTest`
     - 実通知で DRY_RUN するときは `XauShortDemo`
2. チャート左上の表示を確認します: `DRY_RUN=true new=OFF(dry_run) env=ok`。
   - `env=` に理由が出たら照合不一致です (login_mismatch 等)。
   - 実口座で起動すると、EA は開始時に拒否されます (エキスパートタブに `refused (not a demo account)`)。
3. bridge (別の PowerShell)。`automation\xau_short\bridge` へ移動して実行します。
   ```powershell
   Copy-Item .\bridge_config.example.json .\bridge_config.json
   py -3 .\ea_bridge.py run --config .\bridge_config.json
   ```
4. 試験用 ENTRY (TEST フォルダのみ。実データは触りません)。
   - XS の現在 Bid に近い値を `--px` に入れます。
   - 次の 5 分足確定まで待ってから 1 件入ります。
   ```powershell
   py -3 .\make_test_entry.py --config .\bridge_config.json --px 2650.00
   ```
5. 確認:
   - `py -3 .\ea_bridge.py status --config .\bridge_config.json` に次の値が出ること:
     - `EA_DRY_RUN_NOT_SENT`
     - volume / budget_jpy / planned_loss_jpy (EA の journal / 報告)
   - `%APPDATA%\MetaQuotes\Terminal\Common\Files\XauShortDemoTest\journal.txt` に `SEEN` → `DRY_RUN_NOT_SENT` の行があること。
   - MT5 の取引履歴に何も増えていないこと。
6. 実通知で DRY_RUN するとき:
   - `bridge_config.json` を次のように変えます。
     - `receiver_data_dir` を `"..\\receiver\\data"`
     - `bridge_data_dir` を `"data_bridge"`
     - `exchange_dir` を `...\\XauShortDemo`
   - EA の `InpExchangeDir` を `XauShortDemo` にします。
   - **注意:** bridge は実 receiver DB の実行候補に `claim` の印 (claimed_ms と claim_log) を付けます。受信記録・事実・設定は書き換えません。

### 7.3 デモ発注 ON (§8 のチェックをすべて済ませてから)

1. EA の入力を `InpDryRun = false`、`InpAllowNewEntries = true` に変更します (変更すると EA は再初期化され、起動時照合が走ります)。
2. 表示が `new=ON` になることを確認します。

### 7.4 停止

- **新規だけ止める (既存建玉の SL / TP / 建値管理は続ける):** 次のどちらか。
  - `...\XauShortDemo\halt_new` という空ファイルを置く。消せば再開します。
  - 入力 `InpAllowNewEntries = false`
- **すべての書込みを止める:** `InpDryRun = true`。既存建玉の自動管理も止まります。初期 SL はサーバー側に残ります。
- **EA を止める:** チャートから EA を外す (journal に STOP)。
- **bridge を止める:** Ctrl+C。

### 7.5 復旧

- **`HALT_NEW` (結果不明・SL/TP 変更失敗・SL 欠落など) で新規が止まったとき:**
  1. MT5 で注文・建玉・履歴を確認する。
  2. journal / `ea_bridge.py status` の理由と照らし合わせる。
  3. 問題がなければ `...\XauShortDemo\resume_new` という空ファイルを置く (EA が読んで消し、`RESUME_NEW` を記録)。
- **`CRITICAL` (緊急決済も失敗) のとき:**
  1. MT5 で建玉を手動で処理する。
  2. `clear_critical` ファイルを置く。
  3. 確認のうえ `resume_new` を置く。
  - `resume_new` だけでは解除されません。
- **再起動後に `RECONCILED` (結果不明だった注文の建玉が見つかった) が出たとき:**
  - その建玉は自動管理されません。
  - SL / TP を MT5 で確認し、手動で扱ってください。
- **bridge / EA / receiver の再起動:**
  - それぞれ永続記録から再開します。
  - 期限 60 秒を過ぎたコマンドは復活しません。
- journal.txt・bridge.sqlite3・receiver のデータは**削除しないでください** (重複防止の記録です)。

---

## 8. デモ発注を ON にする前のチェックリスト

1. **初期 SL 付き成行を XS デモが受け付けるか。** 0.01 ロットで手動の成行 SELL (SL 付き) を発注して確認します。
   - 受け付けない場合は ON にせず、結果を共有してください。
2. **XAUUSDs の銘柄仕様。** 次の値を控えてください。
   - 契約サイズ、ティックサイズ / ポイント、桁数
   - 最小 / 最大ロット、ロットステップ
   - ストップレベル、約定方式 (filling)、取引時間
3. 口座が **XSFintech-DEMO / JPY / ヘッジ** であること。`env=ok` が表示されること。
4. **DRY_RUN で実通知を数件流し、各 ENTRY について次を確認します:**
   - `DRY_RUN_NOT_SENT` の volume / planned_loss_jpy が残高 × 3 % 以内
   - 見送り理由 (期限・乖離・スプレッド) が妥当
5. **PC の時刻同期** (`w32tm /query /status`)。
   - ずれていると期限判定で全件見送り、または未来判定になります。
6. **口座に他の建玉・待機注文がないこと** (あると最大 1 で見送られます)。
7. `halt_new` / `resume_new` / `clear_critical` の置き場所 (`Common\Files\XauShortDemo`) を確認しておく。
8. **XS の手数料の有無** (0 と確認できていません)。決済後 CLOSED の commission を確認します。
9. **MQL5 のコンパイルがエラー 0 であること。** 警告も共有いただければ確認します。

ON にした後の確認項目 (第4段階):
- 約定チケット・初期 SL・約定足確定での TP0・建値移動・CLOSED の理由
- 拒否時の REJECTED、通信断時の UNKNOWN → 再起動 → 照合
- 手動建玉があるときの見送り、二重起動の拒否

---

## 9. 証拠の区分

- **Python の疑似試験:**
  - bridge は実コードです。
  - EA は MQL5 の行単位の移植 (参照モデル) と疑似 MT5 で、**MQL5 の実行ではありません**。
  - MQL5 ソースとモデルの一致 (定数・状態・拒否理由・ゲート・確定拒否コード) は静的照合しています。
- **MQL5 コンパイル: 未実施。**
- **MT5 デモ実地: 未実施。**
- **TradingView: 今回は変更なし。** Auto 版の負荷対策 (AU-5) で RE10110 が再発しないかも未確認です。

## 10. 試験結果

コミット時点の全試験結果は、レビュー zip の `test_results.txt` を参照してください。
