# ゴールドショート自動化 — 第3段階「デモEA」(ST3-3: ST3-2 再レビュー指摘の修正)

**位置づけ**
- 今回もコード・設計・ローカル試験までです。発注は OFF のままです。
- **MQL5 のコンパイル: 未実施** (この環境に MetaEditor / MT5 がありません)。
- **MT5 デモ実地: 未実施**。
- 「発注動作確認済み」「EA完成」ではありません。
- デモ発注 ON や手動注文の案内、未承認 7 項目の承認手続きは、まだ行いません (この文書には書いていません)。

**変えていないもの**
- 通常版 `ZoneStrategyXAU.pine`、ロング版、Engine、売買条件、input 初期値
- Auto 版 Pine と receiver (`receiver/xau_receiver.py`)

| 区分 | 内容 | 状態 |
|---|---|---|
| Python 試験 | bridge 実コード (`tests/eab_sim.py` 29 件)、EA 規則の Python 参照モデル (`tests/ea_model.py`) と MQL5 ソースの静的照合 (`tests/eam_sim.py` 61 件) | 実施 |
| ST3-2 再レビュー指摘の再現 | 修正前 (5ac972a) と修正後で同じシナリオを実行 (参照モデル。**MQL5 実行ではない**) | 実施 (レビュー zip の `repro_before_5ac972a.txt` / `repro_after_st3-3.txt`) |
| MQL5 コンパイル | `ea/XauShortDemoEA.mq5` | **未実施** |
| MT5 デモ実地 | 発注・取消・SL・TP・建値・再起動・異常系 | **未実施** (第4段階) |

---

## 1. 構成と責務

```
TradingView (シグナル源) ─Webhook→ receiver (変更なし: 受信・記録・実行候補の判定)
   │ SQLite (同じ PC。bridge が書くのは claim() の印だけ)
   ▼
bridge/ea_bridge.py … ENTRY だけを検査して claim → cmd を書く / EA の最終確認 (ask) に GO・NOGO を答える /
                      失効した未実行コマンドを取り消す / 報告を取り込む / 心拍 hb_bridge.txt
   │ ファイル交換: <MT5 Common\Files>\XauShortDemo\ {cmd, ask, ans, rpt, done, ask_done, rpt_done, revoked}
   ▼
ea/XauShortDemoEA.mq5 … 最終確認 → bridge に GO を求める → PRE_SEND 記録 → 全条件を再確認 → 送信 /
                        自分の建玉 (識別子で所有権確認) の保護・管理 / 心拍 hb_ea.txt
```

| 部品 | すること | しないこと |
|---|---|---|
| receiver | 受信・記録・事実の確定・実行候補の判定。claim 後に取消・終了・待機終了を知ると `claim_note=post_claim:*` を記録 (第2段階のまま) | 発注、EA との通信 |
| bridge | 実行候補 ENTRY の検査と claim、cmd 書き出し。**EA の送信直前の問い合わせに最終 GO / NOGO を回答**し、GO 前に失効したコマンドを取り消す (再起動時の recover も同じ)。報告の取り込み、乖離の記録、心拍 | 取引 API、ネットワーク待受、受信記録・設定の書き換え、ENTRY 以外の転送、**約定済み建玉を TV 終了通知で決済すること** |
| EA | 口座・銘柄・journal の照合、期限・価格・スプレッド・ロット・証拠金の確認、GO の取得、PRE_SEND 記録、記録後の全条件再確認、成行 SELL (初期 SL 付き)、約定確認、SL 欠落時の緊急決済、TP0、建値、決済照合、起動時照合、結果不明の照合 | 手動・他 EA・所有権不一致の建玉への書込み、TradingView の BE_MOVE / TV_FLAT / CANCEL / CLOSE_REQ に従うこと |

### 通信方式

MT5 の共通フォルダでのファイル交換です (ST3-1 と同じ)。
- ネットワーク API を新設しないので、Cloudflare の公開範囲は変わりません。
- `.tmp` に書いてから改名するので、読み手は完成したファイルだけを見ます。
- ST3-2 で、最終確認の `ask/` `ans/`、取消用の `revoked/`、心拍ファイルを追加しました。
- コマンドの形式は版 `v=2` になりました。ST3-1 形式 (`v=1`) のコマンドを EA は `cmd_version` で拒否します。

---

## 2. ST3-1 レビュー指摘への対応 (要約)

| # | 指摘 | 修正 | 回帰試験 |
|---|---|---|---|
| 1 | claim 後に失効した ENTRY がそのまま発注される | **最終実行許可を bridge が出す方式**にしました (§3)。<br>• EA は送信直前に `ask` を書き、bridge の `GO` がなければ送りません。<br>• bridge は claim 後に receiver が知ったことをすべて確認してから回答します (post_claim、CANCEL / TV_FLAT / TV_CLOSED / CLOSE_REQ、待機の WAIT_END、再評価中、60 秒)。<br>• GO は 1 キー 1 回で、有効期限は短くしています。<br>• GO 前に失効したコマンドは `revoked/` へ移して取り消します。bridge 再起動時の recover も同じ判定をします。<br>• 約定済み建玉を TV 終了通知で決済することはしません (乖離の記録のみ)。 | EAB-22〜25, EAR-01 |
| 2 | 送信前記録の失敗・記録中の遅延 | • `Journal()` が FileOpen・書込みバイト数・Flush を確認して成否を返すようにしました。<br>• SEEN / DECIDED / PRE_SEND の記録に失敗したら送りません。<br>• **PRE_SEND の記録後に**、期限・GO の有効期限・すべての新規停止条件 (halt_new ファイル、HALT、CRITICAL、結果不明)・口座全体の建玉と待機注文・最新価格・スプレッド・残高を再確認します。<br>• 注文要求はその時点の市場から作り直し、数量か SL が変わる場合は送りません (`SEND_ABORTED request_changed`)。<br>• 記録障害時も自分の無保護建玉の緊急決済は止めません (§5)。 | EAR-02, EAR-02b, EAM-06 |
| 3 | 所有権不一致の建玉を再起動後に決済できる | • 所有権は「journal の FILLED 記録」+「POSITION_IDENTIFIER」+「銘柄・magic・SELL」で決めます。<br>• 起動時だけでなく、**変更・決済の直前に毎回** `SelectOwn()` で確認します。<br>• 不一致なら `QUARANTINE` + CRITICAL + 新規停止とし、その建玉には書き込みません。<br>• journal はファイル名で口座・サーバー・magic に、`BIND` 行で Strategy (sid / cfg / 銘柄) に結び付けました。不一致なら全書込みを拒否します。 | EAR-03 |
| 4 | 結果不明を空の resume_new だけで解除できる | • 結果不明 (`g_unknownKey`) と通常の新規停止を分けました。<br>• `resume_new` は結果不明がある間は拒否します。<br>• 解消は `resolve_unknown` ファイルだけです。EA が注文履歴・約定履歴・待機注文・建玉を照合した結果と、ファイルの `confirm` が一致したときだけ受け付けます (§6)。<br>• 見つかった建玉は識別子で採用し、直ちに SL を確認します。 | EAR-04, EAR-04b, EAM-13〜16 |
| 5 | 次の足の値動きで約定足の建値判定をする | • 約定足の最安値は `CopyTicksRange` のティック履歴から、**約定時刻より後 (同じミリ秒は除外) で、約定足の終了より前**だけを使います。<br>• OnTick の累積最安値は廃止しました。<br>• ティック到着とタイマーの順序に依存しません。 | EAR-05, EAM-21, EAM-26 |
| 6 | 緊急決済の部分完了を全決済のように記録する | • `ClosePosition()` は実建玉と履歴で結果を確かめ、`CLOSE_DONE` / `CLOSE_PARTIAL` / `CLOSE_FAILED` / `CLOSE_UNKNOWN` を区別します。<br>• `EMERGENCY_CLOSE` は全決済が確認できたときだけ記録し、部分・失敗・不明は CRITICAL です。<br>• 残建玉は所有権を保ったまま再試行します。<br>• 再起動後や毎タイマーでも SL 欠落を検出します。<br>• bridge は `CLOSED` でだけ mt5_open を 0 にします。 | EAR-06, EAB-26, EAM-17, EAM-18 |
| 7 | Position Identifier と Ticket の混同 | • 識別子 (`DEAL_POSITION_ID` = `POSITION_IDENTIFIER`) と現在のチケットを別に保存し、識別子で照合します。<br>• チケットが変わっても決済扱いにしません (`TICKET_CHANGED`)。<br>• 決済は識別子の履歴 (IN 数量 ≦ OUT 数量) で判定し、見えないだけなら `OWN_POSITION_MISSING` (新規停止) です。 | EAR-07 |
| 8 | 未承認仕様と通信監視 | • 未承認の方式を `APPROVED_*` ソース定数 (すべて false) にしました。**1 つでも false なら新規発注しません** (DRY_RUN では全経路を実行して記録)。<br>• 通信監視を実装しました (EA / bridge の心拍と停止条件、§7)。数値は提案です。 | EAR-08, EAB-20, EAB-27, EAS-09 |

修正前後の同一シナリオの結果は `repro_before_fcffd71.txt` / `repro_after_st3-2.txt` にあります。いずれも参照モデルでの結果で、MQL5 での実行ではありません。

---

## 2b. ST3-2 再レビュー指摘への対応 (ST3-3)

| # | 指摘 | 修正 | 回帰試験 |
|---|---|---|---|
| 1 | 最終 PrepareOrder の処理中に期限切れ・待機注文の追加・halt_new が起きても送信される | `SendCheck` の順序を入れ替えました。<br>• 先に遅い処理 (PrepareOrder・OrderCheck、要求の作り直しと比較) を行います。<br>• その後、最後の手順として `FinalGate` を実行します (期限・GO 有効期限・すべての新規停止条件・口座全体の建玉と待機注文)。<br>• `FinalGate` と `OrderSend` の間には `ZeroMemory` しかありません (静的試験 EAS-10 で確認)。 | EAR-09, EAS-10 |
| 2 | FILL_SIDE_BAD の決済結果を呼び出し元が無視する | EA が必要とする決済 (初期 SL 欠落 / bad_fill_side_mt5) を、すべて 1 つの仕組みにまとめました。<br>• `RequireClose` が `CLOSE_REQUIRED` を記録します。再起動後も復元します。<br>• `ProcessCloseObligation` が結果を処理します。<br>&nbsp;&nbsp;- 全決済確認: `EMERGENCY_CLOSE` / `CLOSE_CONFIRMED`。その後、履歴から `CLOSED`。<br>&nbsp;&nbsp;- 部分 / 拒否 / 不明: 新規停止 + CRITICAL `close_<partial\|failed\|unknown>:<理由>`。残建玉は所有権を保ったまま、EMERGENCY_RETRY_SEC (5 秒、未承認) ごとに再試行します。<br>• 決済が必要な建玉には TP0・建値の変更をしません。<br>• `ClosePosition` を呼ぶのは `ProcessCloseObligation` だけです。 | EAR-10, EAR-10b, EAS-14 |
| 3 | 後続の分割約定で実建玉の平均価格・数量が変わっても EA の基準が更新されない | `SelectOwn` は、実建玉の `POSITION_VOLUME` / `POSITION_PRICE_OPEN` が EA の値と違えば `SyncFill` を呼び、`POSITION_UPDATED` を記録します (cause=add / reduce、最後の IN 約定時刻、IN 約定数)。<br>• 再起動時は journal から復元し、停止中の変化も起動時に記録します。<br>• 建値の基準は実平均価格で、建値の SL も実平均価格です。<br>• 不足分を追加発注で補うことはしません。 | EAR-11, EAB-29, EAS-15 |
| 4 | 建値移動の再試行待ちが再起動で消える | 条件成立を `BE_TRIGGERED` (fav・足・基準価格) として、**SL 変更の前に**記録します。<br>• 再起動後は `bePending` として復元します。ティック履歴の再取得は不要です。<br>• `RetryBreakeven` が M5 足 1 本に 1 回、再起動直後は即時に再試行します。<br>• ティック履歴を取得できない場合は `FILLBAR_TICKS_UNAVAILABLE` (1 回記録) とし、約定足は未評価のまま次のタイマーで読み直します。「条件不成立」とは扱いません。<br>• SL を緩める変更は ModifyOwn が拒否します (従来どおり)。 | EAR-12, EAS-13, EAS-15 |

**約定足の扱い (承認済み部分と未承認部分の区別)**

- 承認済み: 建値は確定 5 分足で Fixed Distance 15 USD 判定、SL は XS の実約定価格、約定前の安値は使わない。
- **未承認 (`APPROVED_FILLBAR_METHOD`):** 約定足をどう使うか。推奨案の実装は次のとおりです。
  - 約定足は、**最後の IN 約定より後**から足の終了前までの Bid ティックだけを使います。分割約定のときは、後続約定の前の値動きを除くためです。`FILLBAR_SKIP` を選べば約定足は使いません。
  - 後続約定が次の足以降に入った場合、その足の安値は後続約定より前の値動きを含み得るので、建値判定に使いません。その次の確定足から使います。
- **未承認 (`APPROVED_BE_PRICE_SOURCE`):** 価格源を XS の M5 Bid とすること。

## 3. 最終実行許可 (claim と GO の分離)

1. receiver の `claim()` は「通知を一度取得した」印です。**発注許可ではありません。**
2. bridge は claim 後に cmd を書きます。cmd も「実行候補」にすぎません。
3. EA は ENTRY の静的検査・期限・ゲート・注文要求の作成まで済ませたら、`ask/<key_hash>.ask` を書いて待ちます (ASK_WAIT_MS = 5 秒、提案)。
4. bridge は `still_valid()` で確認し、`ans/<key_hash>.ans` に回答します。**判定は回答ファイルより先に DB へ保存します。**
   - 確認する項目:
     - receiver の再評価中でない
     - claim 済みで、`claim_note` が `post_claim:*` でない
     - そのトレードの CANCEL / TV_CLOSED / TV_FLAT / CLOSE_REQ がない
     - ENTRY の待機 (wid) が終了していない
     - バー確定から 0〜60 秒の範囲内
   - **GO** は 1 キー 1 回です。有効期限は `min(現在 + go_ttl_ms(3 秒、提案), バー確定 + 60 秒)` です。
   - **NOGO** は理由付きで返します。2 回目の問い合わせは `already_granted` です。
5. EA は GO を受け取ったら DECIDED → PRE_SEND を記録し、§4 の再確認をしてから OrderSend します。
6. **GO 前に失効したら**、bridge は `REVOKED_BEFORE_GO` とし、cmd が残っていれば `revoked/` へ移します。
   - EA が既に読んでいても、その問い合わせには NOGO を返します。
   - bridge 再起動時に claim 済み・cmd 未作成のキーも同じ判定をし、失効なら `REVOKED_AFTER_BRIDGE_RESTART` で cmd を書きません。
7. **残る競合 (正直な限界)**
   - GO を出した後、送信までの間 (最大 3 秒 + EA 内の処理) に到着した取消は止められません。
   - 送信後・約定後の取消通知は、約定済み建玉の決済理由にしません (乖離として記録するだけ)。

---

## 4. 送信前記録と記録後の再確認

```
SEEN (記録必須) → CheckCmd / 期限 / ゲート / PrepareOrder → AskBridge (GO)
  → DECIDED (記録必須) → PRE_SEND (記録必須。失敗なら送らず HALT_NEW + CRITICAL)
  → SendCheck: ① PrepareOrder をやり直し (建玉・待機注文・価格・スプレッド・残高・証拠金・OrderCheck) / 数量と SL が同じこと
               ② FinalGate (最後): 期限 (遅い側) / GO 有効期限 / 新規停止の全条件 (halt_new ファイル・HALT・CRITICAL・結果不明・心拍)
                  / 口座全体の建玉・待機注文
  → 不合格: SEND_ABORTED (PRE_SEND の最終結果。何も送らない)
  → 合格: その時点の Bid で作り直した要求を OrderSend → SEND_RETURNED → 約定確認 / REJECTED / UNKNOWN
```

- `Journal()` が失敗した行は、エキスパートログ (Print) と `journal_fallback.txt` に残します。
- FinalGate は時計・小さなファイル 2 つ・端末の一覧を読むだけです。FinalGate と OrderSend の間に処理はありません。
- **残る限界:** FinalGate の後、OrderSend がサーバーに届くまでに起きた変化 (他の注文、価格変化、取消通知) は止められません。価格は許容ずれ (残りの 20 % 枠) で、取消は §3 の限界のとおりです。

---

## 5. 記録障害時の例外 (保護は止めない)

- journal に書けないと **新規発注は止まります** (`journal_write_failed` / CRITICAL)。
- 一方、**自分の無保護建玉の緊急決済は止めません。** `TradeWritesAllowed()` は journal の成否を条件にしていません。
  - 決済の記録は best effort です (Print と `journal_fallback.txt`)。
  - 決済結果は実建玉と履歴で確認します。
- 記録障害の解除は、原因を直したうえで `clear_critical` → `resume_new` です。

---

## 6. 結果不明 (UNKNOWN) の扱い

| 状況 | EA |
|---|---|
| 送信の応答がタイムアウト・接続断・PLACED 等 | `UNKNOWN` + HALT_NEW。`g_unknownKey` が新規枠を占有し、再送しません |
| 約定したが確認できない (`done_but_fill_not_confirmed`) | 同上 |
| PRE_SEND 後にクラッシュし、最終結果の記録がない | 再起動時に `UNKNOWN (pre_send_without_result_at_startup)` |
| 起動時・照合時 | `DetectUnknown()` が履歴を照合し、`UNKNOWN_CHECK detected=…` を記録します (下記) |

`DetectUnknown()` が見るもの:
- PRE_SEND 前後の注文履歴 (銘柄・magic・コメント `XSD:<key_hash>`)
- 約定履歴 (IN 約定の注文番号・コメント → 識別子)
- 待機注文
- 建玉

`detected` の値:

| 値 | 意味 |
|---|---|
| `none` | 注文・約定・建玉のいずれもない |
| `open` | 識別子が 1 つで、自分の建玉として建っている |
| `closed` | 履歴の OUT が IN を満たす |
| `ambiguous:*` | 待機注文がある、複数ある、履歴が不完全、識別子は建っているが他の magic 等 |

**解消手順 (運用者):**
1. MT5 の取引履歴・建玉で確認する。
2. `...\XauShortDemo\resolve_unknown` に次の 2 行を書く。
   ```
   key_hash=<16桁>
   confirm=none   (または open / closed)
   ```
3. EA が読み取って消します。**キーが一致し、かつ EA の照合結果と confirm が一致したときだけ** `UNKNOWN_RESOLVED` になります。
   - `ambiguous` は解消できません (手動で整理し、再照合してから)。
   - `confirm=open` なら、識別子で管理対象に採用して直ちに SL を確認します。SL がなければ緊急決済です。
4. 解消後も新規停止は続きます。改めて `resume_new` が必要です。**`resume_new` だけでは結果不明は解除されません。**

---

## 7. 通信監視と停止条件 (数値は提案・未承認)

| 停止したもの | 新規エントリー | 既存の自分の建玉 |
|---|---|---|
| **bridge** | `hb_bridge.txt` が BRIDGE_HB_MAX_MS (5 秒、提案) より古い → EA は `bridge_heartbeat_stale` で新規停止。GO も得られないので送れない | EA が単独で保護・TP0・建値・決済照合を続ける |
| **EA** | bridge は `hb_ea.txt` が require_ea_heartbeat_ms (5 秒、提案) より古いと claim しない (`skip:ea_heartbeat_stale`)。claim 済みの未回答コマンドは 60 秒で取消 | 注文時の初期 SL はサーバー側に残る。TP0・建値・緊急決済は止まる (要監視) |
| **receiver / Cloudflare** | 新しい ENTRY が届かない。bridge の心拍に最終受信時刻 (`last_receipt_ms`) を出し、`status` で確認 | 影響なし (EA が管理) |
| receiver 停止で **取消通知が届かない** | 残る危険: ENTRY 受信後に取消が届かない場合、GO の判定に反映されない (60 秒以内の窓) | 約定後は関係なし (TV 終了で決済しない) |

- 監視の閾値 (5 秒・5 秒・GO 3 秒・待ち 5 秒) は**提案**で、`APPROVED_MONITORING` が false の間は新規発注に使いません。
- 停止しても既存建玉の保護は止めません。DRY_RUN を除きます。DRY_RUN はすべての書込み停止です。

---

## 8. 未承認事項 — 解消するまで新規発注は許可されません

EA ソースの定数で、すべて `false` です。input では変えられません。

| 定数 | 推奨案 (実装済み・未承認) |
|---|---|
| `APPROVED_BE_PRICE_SOURCE` | 建値判定は XS の M5 Bid 足 (OANDA の BAR は記録・比較のみ) |
| `APPROVED_FILLBAR_METHOD` | 約定足は最後の IN 約定より後〜足終了前の Bid ティック履歴 (`InpFillBarBe = FILLBAR_TICKS_SINCE_FILL`)、または約定足を使わない (`FILLBAR_SKIP`)。後続約定を含む足は使わない。履歴が取れない間は未評価のまま読み直す |
| `APPROVED_TP_TIMING` | TP0 は MT5 の約定足の確定時に設定 |
| `APPROVED_TP_BEYOND` | その時点で価格が TP0 を越えていたら: 現在は変更拒否 → SL 維持・新規停止・次の足で再試行。代案は成行決済 (Pine の指値 TP 即約定と同等) |
| `APPROVED_RETRY_INTERVAL` | TP / 建値の変更失敗は M5 足 1 本に 1 回 (建値は再起動直後に 1 回)、必要な決済 (緊急・FILL_SIDE_BAD) の再試行は 5 秒ごと |
| `APPROVED_CLOSE_DEVIATION` | 成行決済の許容ずれ 1000 points |
| `APPROVED_MONITORING` | §7 の閾値 (心拍 5 秒・GO 3 秒・待ち 5 秒) |

- **1 つでも false なら、`InpDryRun=false` と `InpAllowNewEntries=true` にしても新規は `SKIPPED unapproved:<名前>` になります。**
- DRY_RUN では最後まで実行し、`DRY_RUN_NOT_SENT ... unapproved=<名前>` と記録します。
- 承認されたら、該当の定数を true にしてコンパイルし直します。これはご判断の後に行います。

---

## 9. 状態遷移

### bridge (bridge.sqlite3)

`lifecycle` の遷移:
```
CHECKED → SKIPPED_BY_BRIDGE (… / skip:ea_heartbeat_stale)
        → CLAIMING → CLAIM_REFUSED
        → CLAIMED → CMD_WRITTEN
                  → REVOKED_BEFORE_GO / REVOKED_AFTER_BRIDGE_RESTART / EXPIRED_AFTER_BRIDGE_RESTART
                  → (GO: go_ms, go_until_ms) → EA_… (EA の報告)
```

- 列 `nogo_reason` / `revoked_ms` / `go_ms` / `go_until_ms` を追加しました (ST3-1 の DB はその場で列追加します)。
- 回答の記録は `answers` 表に残ります。

### EA (journal_<login>_<server>_<magic>.txt、追記のみ)

1 行は `t_ms|key_hash|STATE|k=v;…` です。
- **起動:** `START` → `BIND` (初回) / `BIND_MISMATCH` → 照合
  - `UNKNOWN`, `UNKNOWN_CHECK`, `OWNED_AT_STARTUP`, `CLOSED`, `OWN_POSITION_MISSING`, `QUARANTINE`, `HALT_NEW` …
- **新規:** `SEEN` → `SKIPPED` | `DRY_RUN_NOT_SENT` | `DECIDED` → `PRE_SEND` → `SEND_ABORTED` | `SEND_RETURNED`
  → `FILLED` (+`PARTIAL_FILL`) → `PROTECTED` | `SL_MISSING`
  → `CLOSE_REQUIRED` (emergency_initial_sl_missing / bad_fill_side_mt5) → `CLOSE_PRE_SEND` → `CLOSE_DONE` / `CLOSE_PARTIAL` / `CLOSE_FAILED` / `CLOSE_UNKNOWN`
  → `EMERGENCY_CLOSE` / `CLOSE_CONFIRMED` (全決済確認) | `EMERGENCY_CLOSE_PARTIAL` / `CLOSE_INCOMPLETE` + `CRITICAL` (再試行)
  - 送信結果が確定しなければ `REJECTED` | `UNKNOWN`
- **管理:**
  - `TP_SET` / `BE_TRIGGERED` → `BE_SET` / `MODIFY_FAILED` / `MODIFY_REFUSED` / `FILL_SIDE_BAD`
  - `FILLBAR_NO_TICKS` (履歴あり・ティック 0) / `FILLBAR_TICKS_UNAVAILABLE` (履歴なし・再読込)
  - `POSITION_UPDATED` / `TICKET_CHANGED` / `MANAGEMENT_BLOCKED` / `CLOSED`
- **再起動で復元するもの:** 自分の建玉 (FILLED + POSITION_UPDATED)、必要な決済 (CLOSE_REQUIRED)、成立済みの建値 (BE_TRIGGERED / BE_SET)、結果不明、HALT / CRITICAL
- **結果不明:** `UNKNOWN` → `UNKNOWN_CHECK` → `UNKNOWN_RESOLVE_REFUSED` | `UNKNOWN_RESOLVED`
- **運用:**
  - `HALT_NEW` / `RESUME_NEW` / `RESUME_REFUSED`
  - `CRITICAL` / `CRITICAL_CLEARED`
  - `QUARANTINE`
  - `ENV_OK` / `ENV_LOST`
  - `DUPLICATE` / `BAD_CMD` / `TX_DEAL` / `STOP`

---

## 10. 仕様 ⇔ コード対応 (主要部。ST3-1 からの変更点を含む)

| 仕様 | 実装 | 試験 |
|---|---|---|
| 既定 DRY_RUN・新規 OFF、全書込み禁止 | `InpDryRun=true` / `InpAllowNewEntries=false`、OrderSend は 3 か所のみで全て `TradeWritesAllowed()` を通る | EAM-03, EAM-31, EAS-03 |
| デモ口座の実行時確認 | `OnInit` で非デモは INIT_FAILED、書込みごとに demo・ログイン・サーバー確認 | EAM-01, 02, 30, EAS-04 |
| 未承認方式で発注しない | `APPROVED_*` = false → `unapproved:*` | EAR-08, EAS-09 |
| 確定 SHORT 成行 ENTRY のみ、LIMIT 見送り | bridge `_check`、EA `CheckCmd` | EAB-06, EAM-28 |
| 60 秒 (受信・claim・GO・記録後) / 負の経過不合格 | `_check` → `claim()` → `still_valid()` → `CheckDeadline()` (2 回) | EAB-08, 09, 25, EAM-05, 06, EAR-02 |
| claim は発注許可ではない・失効は実行しない | GO / NOGO、`revoke_invalid()`、`recover()` | EAB-22〜25, EAR-01 |
| 価格乖離 20 %・スプレッド 0.50・ロット 3 %・SL を広げない | `PrepareOrder` (記録後にも再実行) | EAM-07〜10, EAR-02 |
| 最大 1 (口座全体)・送信中 / 不明も占有 | `PositionsTotal/OrdersTotal`、`g_inflightKey`、`g_unknownKey`、`g_hasPos` | EAM-11, 13, 15 |
| 所有権 = 永続記録 + 実建玉 | journal FILLED + `POSITION_IDENTIFIER` + 銘柄・magic・SELL、変更・決済の直前に毎回 | EAR-03, EAR-07, EAS-11 |
| 初期 SL 必須・欠落時緊急決済・失敗は重大 | `CheckProtection()` (約定後・起動後・毎タイマー)、`ClosePosition()` の結果区別 | EAM-17, 18, EAR-06 |
| TP0 は約定足確定時・SL を戻さない (未承認方式) | `ManageOwn()` | EAM-19, 20 |
| 建値 15 USD・XS 約定価格へ・約定前の安値を使わない (未承認方式) | `FillBarLow()` (ティック履歴の区間限定) + 確定 M5 足 | EAM-21, 22, EAR-05 |
| TV 終了で追随決済しない・乖離を記録 | bridge `check_divergence()` (記録のみ) | EAB-15, EAM-24 |
| 結果不明は再発注しない・照合して解消 | `MarkUnknown`、`DetectUnknown`、`resolve_unknown` | EAM-13〜16, EAR-04 |
| 認証情報・URL を記録しない、Cloudflare 公開範囲を広げない | ネットワーク API なし、設定例に秘密なし | EAB-18, 19, EAS-01 |

---

## 11. 完全な排他の限界

- **今回の修正で競合が無くなったわけではありません。**
  - GO 発行後 (最大 3 秒) に到着した取消は止められません (§3)。
  - FinalGate から約定までの間の変化も止められません (§4)。
- **口座全体の最大 1 は、送信直前 (FinalGate) の確認です。** 確認から約定までの間に手動・他 EA が注文すると、両方が建つことはあり得ます。
- **分割約定の後続分は、ブローカーが同じ識別子に約定させたものだけを追跡します。** 別の注文・別の識別子になった建玉は自分の建玉として扱いません (口座全体の最大 1 で新規は止まります)。
- **magic・コメントは他 EA でも同じ値にできます。**
  - 管理対象は journal の FILLED 記録の識別子で決めます。
  - コメントは結果不明の照合の手掛かりにだけ使い、自動採用はしません (運用者の confirm が必要)。
- **EA を止めている間・DRY_RUN の間は、自動の TP0 / 建値 / 緊急決済は行われません。** 初期 SL はサーバー側に残ります。
- **期限判定は PC 時計 (1 秒分解能) です。** 期限側は最大 1 秒厳しめで、未来側は早い側で判定します。
- **Strategy 設定 (sid / cfg / 銘柄) を変えると、その journal は BIND 不一致になり全書込みを拒否します。**
  - 自分の建玉が残っている間は設定を変えないでください。
  - 変える場合は建玉の整理後に journal を退避します (削除ではなく改名)。

---

## 12. ファイル

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

## 13. Windows での手順 (発注 OFF のまま行える範囲)

前提:
- receiver は README_ja.md の手順で動いていること。`start_receiver.ps1` の終了コード 2 は未解決のため、Python の直接起動で構いません。
- Python 3.10 以上。

### 13.1 EA の配置とコンパイル

1. MT5 の **ファイル → データフォルダを開く** → `MQL5\Experts` に `XauShortDemoEA.mq5` をコピーします。
2. MetaEditor でコンパイルします。
   - こちらでは未コンパイルなので、エラー・警告は全文を共有してください。
3. WebRequest の URL 追加は不要です。

### 13.2 DRY_RUN (発注なし)

1. XAUUSDs の M5 チャートに EA を付けます。入力:
   - `InpDryRun = true`、`InpAllowNewEntries = false` (既定のまま)
   - `InpExpectedLogin` = デモ口座のログイン番号 (PC 上で入力。パスワードはどこにも入力しません)
   - `InpExchangeDir`: 試験時は `XauShortDemoTest`、実通知で DRY_RUN するときは `XauShortDemo`
2. チャート表示を確認します: `DRY_RUN=true new=OFF(dry_run) env=ok unknown=none`。
3. bridge を起動します (別の PowerShell で `automation\xau_short\bridge` へ移動)。
   ```powershell
   Copy-Item .\bridge_config.example.json .\bridge_config.json
   py -3 .\ea_bridge.py run --config .\bridge_config.json
   ```
4. 試験用 ENTRY を入れます (TEST フォルダのみ)。`--px` は XS の現在 Bid に近い値にします。
   ```powershell
   py -3 .\make_test_entry.py --config .\bridge_config.json --px 2650.00
   ```
5. 確認:
   - `py -3 .\ea_bridge.py status --config .\bridge_config.json` で次を確認します。
     - 心拍 (`hb_ea.txt` / `hb_bridge.txt` の経過秒)
     - `EA_DRY_RUN_NOT_SENT`、`go=` の時刻
   - journal (`...\XauShortDemoTest\journal_<ログイン>_<サーバー>_26102801.txt`) に次の流れがあることを確認します: `SEEN` → `DRY_RUN_NOT_SENT gate=dry_run;go=granted;unapproved=be_price_source;…`
   - MT5 の取引履歴に何も増えていないことを確認します。
6. 失効の確認 (任意): bridge を止めたまま試験用 ENTRY を入れると、EA は `nogo:no_answer` で見送ります。
7. 実通知で DRY_RUN するとき:
   - `bridge_config.json` を次のように変えます。
     - `receiver_data_dir` を `"..\\receiver\\data"`
     - `bridge_data_dir` を `"data_bridge"`
     - `exchange_dir` を `...\\XauShortDemo`
   - EA の `InpExchangeDir` を `XauShortDemo` にします。
   - bridge は実 receiver DB の実行候補に claim の印を付けます。受信記録・事実・設定は書き換えません。

### 13.3 停止・復旧の操作ファイル (`<Common\Files>\XauShortDemo\`)

| ファイル | 働き |
|---|---|
| `halt_new` (空) | 置いている間、新規だけ停止 (保護は継続) |
| `resume_new` (空) | 通常の新規停止を解除。CRITICAL・結果不明があれば拒否 |
| `clear_critical` (空) | 手動確認後に CRITICAL を解除 (新規停止は続く) |
| `resolve_unknown` | `key_hash=` と `confirm=` の 2 行。§6 の照合と一致したときだけ結果不明を解消 |

- journal・bridge.sqlite3・receiver のデータは削除しないでください (重複防止と照合の記録です)。

### 13.4 デモ発注 ON について

再レビュー後にご案内します。ON の前提は次のとおりです。
- §8 の承認がすべて揃い、該当定数を変更して再コンパイルすること
- MQL5 コンパイルがエラー 0 であること

---

## 14. 証拠の区分

- **Python 試験:**
  - bridge は実コードです。
  - EA は MQL5 の関数単位の移植 (参照モデル) と疑似 MT5 で、**MQL5 の実行ではありません**。
- **MQL5 ソースとモデルの静的照合:** 定数・承認定数・状態・拒否理由・確定拒否コード・送信順序・所有権・結果不明・ティック区間・決済結果の区別。
  - 参照モデルだけを直して MQL5 に反映しないと、この照合が失敗します。
- **MQL5 コンパイル: 未実施。MT5 デモ実地: 未実施。**
- **TradingView: 変更なし。** AU-5 で RE10110 が再発しないかも未確認です。
