# ゴールドショート自動化 — 第2段階「通知の受信・記録」(AU-1)

TradingView → Windows の受信処理 → (後段) XS の MT5、のうち **受信・記録まで** を実装したものです。
**実注文・MT5 接続・注文 API は一切ありません。** ローカルテストの成功は、TradingView / MT5 での動作確認ではありません。

## 1. 構成

| パス | 役割 |
|---|---|
| `ZoneStrategyXAU.pine` (リポジトリ直下) | 通常版ゴールドショート (XA-23)。**変更していません** |
| `automation/xau_short/pine/ZoneStrategyXAU_Auto.pine` | 自動化専用コピー。通常版 + JSON 出力の追加だけ (生成: `tests/au_build.py`) |
| `automation/xau_short/receiver/xau_receiver.py` | 受信・検査・記録 (Python 標準ライブラリのみ、SQLite) |
| `automation/xau_short/receiver/config.example.json` | 設定の雛形 (認証情報は含まない) |
| `automation/xau_short/receiver/start_receiver.ps1` / `stop_receiver.ps1` / `show_log.ps1` | Windows の起動・停止・確認 |
| `automation/xau_short/receiver/samples/` | ローカル用サンプル通知と生成スクリプト |
| `tests/au_build.py` / `tests/au_sim.py` / `tests/aur_sim.py` | コピーの生成元とテスト |

元ファイルの特定: リポジトリ直下 `ZoneStrategyXAU.pine` (commit 7705907、XA-23。`xa_build.build_strategy()` と一致、SHA-256
`e05386f4…c8d818`)。本文で Short Only / Entry C / SATS Pullback / 即時 ON (1 / 1) / 待機 240 分 / SL Buffer 1.5 / RR 1.5 /
反対側 Zone TP OFF / 建値 ON Fixed 15 / JST 9:00〜翌 2:00 を確認。添付ファイルはこのセッションに届いていないため、添付との差分比較は未実施です。

自動化コピーは通常版を生成元から組み立て直し、決まった追加だけを重ねます (`tests/au_build.py`)。追加を外すと通常版とバイト単位で一致することをテストで固定しています。
売買判定・注文・状態更新の行は 1 行も変えていません (TP 追加・建値移動も通常版どおり確定 5 分足)。

## 2. 通知仕様 (schema `xau-auto/1`)

TradingView の 1 アラート = 1 JSON。フィールド (この順):

| フィールド | 内容 |
|---|---|
| `schema` | `xau-auto/1` |
| `sid` | 版 ID `XAU-SHORT|XA-23|AU-1` |
| `cfg` | 主要入力の値を並べた文字列。受信側が SHA-256 を取り **設定 ID** として保存・照合 |
| `ev` | イベント種別 (下表) |
| `key` | 冪等キー `sid|ev|tid|bar_close` |
| `tid` | 取引 ID (下記) |
| `rank` | 同じ足の中の順序 (下表) |
| `sym` / `tf` | `OANDA:XAUUSD` / `5` |
| `bar_open` / `bar_close` | 判断足の開始・終了時刻 (UTC ミリ秒) |
| `sent` | TradingView が送った時刻 (`timenow`) |
| `side` | `SHORT` (`LONG` は受信側で拒否) |
| `otype` | `MARKET` / `LIMIT` (該当なしは空) |
| `px` / `sl` / `tp` | 参考価格 / SL / TP (なしは `null`) |
| `info` | 経路・理由 (`SATS_PULL;wid=W…` / `SATS_NOW` / `CURRENT` / 取消理由など) |

| ev | rank | 意味 | 後段で実行対象になり得るか |
|---|---|---|---|
| `PROV` | 1 | 仮通知 (形成中の足。確定前に崩れることがある) | ならない (記録のみ) |
| `WAIT_START` | 5 | SATS 待機の準備 (Pine 内の条件待機。業者への指値ではない) | ならない |
| `ENTRY` | 10 | **確定した注文意図** (確定 5 分足で strategy.entry を出した分岐。約定通知ではない) | なり得る |
| `CANCEL` | 20 | Strategy が自分の未約定エントリーを取り消した | なり得る |
| `TV_FILL` | 30 | TradingView 内の疑似建玉が約定した (確定足で検出) | ならない (状態のみ) |
| `TP_SET` | 40 | 約定確認後の TP 設定 (確定 5 分足) | なり得る |
| `BE_MOVE` | 50 | 建値移動 (確定 5 分足) | なり得る |
| `CLOSE_REQ` | 60 | 成行決済 (約定位置不適切 / RR 不足 / risk ≤ 0) | なり得る |
| `TV_CLOSED` | 70 | 約定した足の中で決済まで成立 (疑似) | ならない |
| `TV_FLAT` | 90 | 疑似建玉がなくなった (SL / TP / 建値で終了) | ならない |
| `WAIT_END` | 95 | SATS 待機の終了 (期限 / SL0 到達) | ならない |

自動化コピーの入力「自動化 JSON 出力」(初期 ON) が ON のとき、このコピーは JSON だけを送ります (人間向け文章アラートは送らない)。
OFF なら通常版と同じ文章アラートです。通常版の通知は何も変わりません。

## 3. 重複・順序の管理

- **取引 ID**: `T` + ENTRY 判断足の終了時刻 (ミリ秒)。その後の CANCEL / TV_* / TP_SET / BE_MOVE / CLOSE_REQ も同じ tid を使います。
  SATS 待機は `W` + 準備足の終了時刻、仮は `P` + 足の開始時刻です。
- 連番ではなく足の時刻から決まるので、TradingView の再読込や受信処理の再起動で変わりません (最大 1 件の発注なので、1 本の足に ENTRY は 1 つだけ)。
- **冪等キー** `sid|ev|tid|bar_close`:
  - Pine 側は varip の送信済みリストで同じキーを再送しません。
  - 受信側は SQLite の主キーで、同じキーを 2 回目以降 `DUPLICATE` として記録します (状態は変えない)。
  - 再起動後も同じ判定です。
- **順序**: 取引ごとに最後に受理した `(bar_close, rank)` を保存し、それより古い通知は `order:out_of_order` で拒否します。
- **状態遷移** (TradingView の疑似建玉): `INTENT → (CANCEL→CANCELLED | TV_FILL→TV_OPEN | TV_CLOSED→CLOSED)`、
  `TV_OPEN → (TP_SET / BE_MOVE → TV_OPEN | CLOSE_REQ → CLOSING | TV_FLAT → CLOSED)`、`CLOSING → TV_FLAT → CLOSED`。
  これ以外は `state:invalid_transition` です。
- **遅延・失効の検査**:
  - 終了済み取引への通知 (`state:trade_closed` / `trade_cancelled`)
  - 未知の取引 (`state:unknown_trade`)
  - 終了済み待機を参照する ENTRY (`late:wait_already_ended`)
  - より新しい取引の後に届いた古い ENTRY (`late:older_than_newer_trade`)
  - 疑似建玉が残っている間の ENTRY (`state:virtual_position_active`。終了通知の欠落を示す)
  - 通知期限 (`policy.max_age_sec`) は **未承認のため初期は無効** で、経過時間 (`age_ms`) だけを記録します。
- **形式・ID の検査**:
  - JSON でない / 必須欄の欠落・型違い / 未知のイベント
  - キーと中身の不一致 / rank の不一致 / tid の形
  - sid・銘柄・時間足の不一致
  - LONG の注文意図 / SL・TP の位置の誤り
  - cfg のハッシュ不一致 (`expected.cfg_sha256` を設定した場合。未設定の間は `warn:cfg_unpinned` を付けて記録)

すべての受信 (拒否・重複を含む) を `receipts` に保存します。受理したものだけが `events` と状態を更新します (1 トランザクション)。

保存項目: 受信時刻、判断足の開始・終了時刻、送信時刻、経過時間、sid、設定 ID (cfg の SHA-256)、取引 ID、イベント、順序 (rank)、
注文種別、参考価格・SL・TP、検査結果 (ACCEPTED / DUPLICATE / REJECTED)、理由、生の本文、後段での実行対象か、MT5 での処理 (常に「なし」)。

**疑似建玉と実建玉の分離**: TradingView 側は `tv_trades` / `tv_waits`、MT5 側は `mt5_positions` (第2段階では一切書き込まない、
状態は `NOT_CONNECTED`) です。両者が一致する前提は置いていません。

## 4. Windows での操作 (次に行うこと)

前提: Windows に Python 3.10 以上 (python.org 版。`py` ランチャー推奨)。外部パッケージは不要です。

1. リポジトリを Windows に置き、PowerShell で `automation\xau_short\receiver` へ移動する。
2. `Copy-Item config.example.json config.json`
3. Webhook 用のトークンを **ローカルだけで** 作って、ユーザー環境変数に保存する (チャット・コード・ログには書かない):
   ```powershell
   $t = py -3 -c "import secrets; print(secrets.token_urlsafe(32))"
   [Environment]::SetEnvironmentVariable("XAU_RECEIVER_TOKEN", $t, "User")
   ```
   その後 PowerShell を開き直す (環境変数を読み直すため)。
4. 起動: `powershell -ExecutionPolicy Bypass -File .\start_receiver.ps1`
5. 確認: `Invoke-RestMethod http://127.0.0.1:8787/health` → `orders: disabled`
6. サンプルで記録を試す (受信処理と同じデータベースに入ります。試験後は `data` フォルダを消すか、別の config で `data_dir` を分ける):
   ```powershell
   py -3 .\xau_receiver.py ingest .\samples\normal_flow.jsonl .\samples\bad_cases.jsonl --config .\config.json
   ```
   HTTP 経由で試す場合:
   `Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8787/webhook/$env:XAU_RECEIVER_TOKEN" -Body (Get-Content .\samples\normal_flow.jsonl -TotalCount 1)`
7. 記録の確認: `powershell -ExecutionPolicy Bypass -File .\show_log.ps1` (`-Follow` でログ追従)
8. 停止: `powershell -ExecutionPolicy Bypass -File .\stop_receiver.ps1`
9. 記録は `data\xau_receiver.sqlite3` (再起動後も残る) と `data\receiver.log` (5 MB × 5 世代) にあります。

## 5. 外部 HTTPS の受信経路 (構成案のみ。契約・公開は未実施)

- TradingView の Webhook は **インターネット上の HTTPS (443) / HTTP (80) の URL にしか送れません**。
  受信処理は既定で `127.0.0.1:8787` だけで待ち受けるので、外部からは届きません。
- **案 A: Cloudflare Tunnel (cloudflared)**
  - Windows に cloudflared を入れ、`https://<任意のホスト名>/webhook/<トークン>` を `http://127.0.0.1:8787` へ転送します。
  - ポート開放は不要です。必要なもの: Cloudflare アカウント、ドメイン、cloudflared のサービス登録。
- **案 B: VPS などのリバースプロキシ (nginx / Caddy + TLS) → VPN / SSH トンネルで Windows へ**
- **共通**
  - URL のトークンを秘密として扱い、漏れたら作り直します。TradingView が公表している送信元 IP だけを許可する設定を追加で推奨します (IP は TradingView の最新の案内で確認)。
  - TradingView 側は「alert() function calls only」で作成し、Webhook URL を設定します。
- いずれも **まだ実施していません**。アカウント作成・ドメイン・外部公開は承認後に行います。

## 6. 後段へ引き継ぐ条件 (今回は実装していない)

- 損失予算 = 発注判断時の口座残高 × 3 %。円損失は発注のたびに MT5 の `OrderCalcProfit` 等で計算する。固定値・Tick Value の表示値だけでは決めない。
  - 取得時の参考値: 0.01 lot SELL で 1 ドル逆行すると −157 円。これは固定値として使いません。
  - 通常版の数量計算 (元金基準額 300,000 円 × 3 %、単利) とは別物です。
- 最大 1 ポジション。保有中の追加シグナルは見送る。日次損失上限は追加しない。
- 通常版を維持し、実注文の管理担当は一本化する。
- XS デモ仕様 (XSFintech-DEMO、XAUUSDs、JPY、ヘッジ、100 oz/lot、0.01〜10 lot、刻み 0.01、価格刻み 0.01、Stops / Freeze 0 (取得時)、スプレッド変動 (取得時 0.18)、手数料未確認)。

## 7. 未決定事項 (提案のみ。採用していません)

| 項目 | 現状 | 提案 (承認待ち) |
|---|---|---|
| 通知期限 | 無効 (経過時間のみ記録) | ENTRY は判断足の終了から 60〜90 秒以内なら実行候補 |
| 価格ずれ | 未実装 | 参考価格からの乖離が SL 幅の 20〜30 % を超えたら見送り |
| スプレッド上限 | 未実装 | 例: 0.50 ドル超で見送り (XS の実測分布を見て決める) |
| 手数料 | 未確認 | MT5 の約定履歴で確認してから損失予算に含めるか決める |
| 切り下げ・最小数量 | 未実装 | 0.01 lot 未満になる場合は見送り (通常版と同じ考え方) |
| 指値中の残高変化 | 対象なし (初期は成行のみ) | Entry A を使う場合だけ検討 |
| 最大 1 件の適用範囲 | 未決定 | この Strategy (magic 番号) 単位か、口座単位か |
| 週末制限 | **現コードに曜日制限はない** (時間帯だけ) | 運用上の希望 (例: 金曜深夜以降の新規見送り) は別途決定 |
| cfg の固定 | 未設定 (`warn:cfg_unpinned`) | 初回の実通知の cfg を確認してから `expected.cfg_sha256` に設定 |

## 8. 未検証の部分

- 自動化コピーの TradingView 上でのコンパイル、実アラートの JSON 本文、Webhook の実配信
  - `str.tostring` の小数表記や `format.mintick` の桁を含みます。
  - サンプルの cfg 文字列は想定値で、初回の実通知で確認が必要です。
- Windows 上での PowerShell スクリプトの実行 (このリポジトリの環境は Linux。Python 部分は Linux で試験済み)
- 外部 HTTPS 経路、TradingView の再送挙動
- MT5 との照合 (後段)
