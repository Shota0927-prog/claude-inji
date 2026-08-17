# POINT MASTER — 土台の使い方

`point_master.pine` は、複数ロジック × 複数時間足のシグナルをポイント化して
`LONG SCORE` / `SHORT SCORE` / `NET SCORE` を算出する共通基盤です。
実ロジック（FVG / EMA / TrendLine / DoubleTop 等）はまだ入っていません。

---

## 1. どこへロジックを接続するのか

**§4 LOGIC SIGNAL INPUT AREA** の `f_signalMasks()` 内、
`▼▼▼ ここから ▼▼▼` 〜 `▲▲▲ ここまで ▲▲▲` の間だけです。

```pine
f_signalMasks() =>
    // ▼▼▼ ここから
    bool l01Long  = <FVG の LONG 条件>
    bool l01Short = <FVG の SHORT 条件>
    ...
    // ▲▲▲ ここまで

    longs  = array.from(l01Long,  l02Long,  l03Long)
    shorts = array.from(l01Short, l02Short, l03Short)
```

この関数は `request.security()` 経由で各時間足のコンテキストで実行されるため、
中で書く `close` / `ta.ema()` などは自動的にその時間足の値になります。
**MTF 対応のために特別な記述は不要です。**

---

## 2. ロジックを1個追加する時にやること（4箇所だけ）

| 場所 | やること |
|------|----------|
| §0 | `int N_LOGIC = 3` を `4` に増やす |
| §2 | `grpL4` の input ブロックを追加し、`LOGIC_NAME` / `LOGIC_WEIGHT` の `array.from(...)` に足す |
| §3 | `grpH4` の保持本数 input ブロック + `HOLD04` を追加し、`array.concat(HOLD_ALL, HOLD04)` を1行追加 |
| §4 | `l04Long` / `l04Short` を定義し、`longs` / `shorts` の `array.from(...)` に足す |

集計（§7）・状態管理（§6）・テーブル表示（§8）は配列ベースなので **変更不要** です。

> 注意：`array.from()` の並び順がロジック番号（0,1,2…）になります。
> `longs` / `shorts` / `LOGIC_NAME` / `LOGIC_WEIGHT` / `HOLD_ALL` の順番は必ず揃えてください。

---

## 3. 保持本数の設定場所

**§3 保持本数設定**。ロジック × 時間足ごとに `input.int` があります。

```
③ Logic01 保持本数 : 1M / 5M / 15M / 1H / 4H / 1D
③ Logic02 保持本数 : 〃
③ Logic03 保持本数 : 〃
```

例：`EMA = 6本`, `FVG = 24本`, `TrendLine = 8本` のようにロジック別に設定できます。
本数は **そのTF自身の確定足の本数** です（チャート足の本数ではありません）。

---

## 4. ロジックWeight の設定場所

**§2 ロジック設定**。`② Logic01 → ロジックWeight` など。名称も input なので、
`Logic01` を `FVG` に書き換えればテーブル表示もそのまま変わります。

---

## 5. TF Weight の設定場所

**§1 時間足設定**。時間足そのものも input なので `1M → 3M` のような差し替えも可能です。

初期値：

```
1M = 1.0 / 5M = 1.2 / 15M = 1.5 / 1H = 2.0 / 4H = 3.0 / 1D = 4.0
```

ポイント = **ロジックWeight × 時間足Weight**
例）TrendLine(1.5) × 15M(1.5) = **2.25pt**

---

## 6. LONG → SHORT 切替はどこで処理されているか

**§6 の `f_applySignal()`** です。全ロジック・全TFがこの1関数だけを通ります。

```pine
if sigLong
    st := ST_LONG      // SHORT 保持中ならここで SHORT が即解除され LONG へ切替
    hd := holdBars     // 同方向の再発生なら「保持期限リセット」だけになる
else if sigShort
    st := ST_SHORT     // LONG 保持中ならここで LONG が即解除され SHORT へ切替
    hd := holdBars
else if st != ST_NONE
    hd := hd - 1       // シグナル無し：そのTFの確定足1本ごとに消化
    if hd <= 0
        st := ST_NONE
```

- `st` は単一値なので、同一ロジック・同一TFで LONG と SHORT を同時に持つことは**構造的に不可能**
- 同方向の再発生ではポイントを二重加算せず、保持期限だけリセット
- 逆方向発生時は旧方向を即解除し、新方向の保持を 0 から数え直す

呼び出し側（§6 末尾のループ）は、
**そのTFの確定足が新しくなった瞬間だけ** この関数を呼びます。

---

## 7. リペイント対策

- `lookahead = barmerge.lookahead_off`
- さらに `[1]`（1本前）を参照して確定足のみを使用

そのため、確定足ベースで値が後から変わりません（1本ぶんの遅延が対価です）。

**注意**：チャートの時間足より小さいTFを集計する場合（例：日足チャートで1M集計）、
`request.security()` はチャート足内の最後の1本しか返せません。
正確に集計するには、**集計対象の最小TF以下のチャート**で表示してください。

---

## 8. 動作確認

`④ 動作確認 (ダミーシグナル)` を ON にすると、`bar_index % N` ベースの擬似シグナルが
発生します（実ロジックではありません）。保持・切替・集計・テーブルの検証用です。
`⑥ 表示設定 → ロジック詳細テーブル` を ON にすると
`L(残り本数)` / `S(残り本数)` / `-` でロジック × TF の状態を確認できます。

---

## 9. 今回やっていないこと

FVG / EMA / TrendLine / DoubleTop の本体ロジック、エントリー、`strategy.entry`、
SL / TP、バックテストは未実装です。
