# ZoneLevelEngine v3 — `projectLevelAfterNextTouch()` の追加手順

## これは何か

`Zone_Level_Rebound_Strategy_Lite.pine` の

```
Entry Mode              = EDGE_LIMIT
Edge Limit Level Source = PROJECTED_POST_TOUCH
```

が動くために必要な、**ZoneLevelEngine 側の作業手順**です。

Strategy 側は「次の Touch が起きたら Level はいくつになるか」を
ZoneLevelEngine へ**問い合わせるだけ**にしてあります。
Strategy 側で BirthScore / TouchCount から Level 式を再実装することは
していませんし、してはいけません（二重実装は必ずズレます）。

> このリポジトリに ZoneLevelEngine のソースは含まれていないため、
> v3 の作成・publish は TradingView 上で行ってください。

---

## 1. 原則：式をコピーしない

やってはいけないこと:

```pine
// ❌ 既存の Level 判定式をコピーして別実装にする
export projectLevelAfterNextTouch(ZoneLevel z) =>
    z.birthScore >= 10 ? ... : ...   // ← 実 Level 計算と二重実装になる
```

やること:

**実際に `zoneLevel` を決めている判定式を private 関数へ「移動」し、
通常 Level 計算と Projected Level 計算の両方がその同じ関数を呼ぶ。**

---

## 2. 手順

### (1) 現在の Level 判定箇所を特定する

`endBaseBar()`（または Level を確定している内部処理）の中で、
`zoneLevel` に値を入れている部分を探します。おおよそ次の形のはずです。

```pine
// Before (endBaseBar 内)
    z.zoneLevel     := <birthScore と touchCount を使った既存の判定式>
    z.zoneLevelName := <その Level 名>
```

### (2) その式をそのまま private 関数へ切り出す

**式は 1 文字も変えずに移動します。**
引数は、その式が実際に読んでいる値だけにします
（下は例です。実際に使っている値に合わせてください）。

```pine
// 追加 (export しない内部関数)
f_levelFrom(float birthScore, int touchCount) =>
    <(1) から移動してきた既存の判定式をそのまま>
```

### (3) `endBaseBar()` はその関数を呼ぶだけにする

```pine
// After (endBaseBar 内) — 式を複製しない
    z.zoneLevel     := f_levelFrom(z.birthScore, z.touchCount)
    z.zoneLevelName := <Level 名の決め方は従来どおり>
```

ここまでで **v2 と結果が完全に一致していること**を確認します
(Zone Level Display の表示が変わらないこと)。

### (4) export を追加する

```pine
// @function     次に Touch が 1 回起きた場合の zoneLevel を返す。
// @param  z     現在の ZoneLevel
// @returns      touchCount + 1 を反映した zoneLevel
export projectLevelAfterNextTouch(ZoneLevel z) =>
    f_levelFrom(z.birthScore, z.touchCount + 1)
```

- `birthScore` など **Level 判定に実際に使っている値は、現在 Zone の値をそのまま**渡します。
- 推測で条件を足さないでください。変えるのは `touchCount` を `+1` にすることだけです。

### (5) v3 として publish する

v2 は壊さず、新しいバージョンとして公開します。
Zone 生成 / TouchCount / 現在 Level / Display 互換は v2 と完全一致のままで、
**新規機能は `projectLevelAfterNextTouch()` だけ**にします。

---

## 3. Strategy 側のつなぎ込み（2 箇所だけ）

`Zone_Level_Rebound_Strategy_Lite.pine` を編集します。

### (1) import

```pine
import sekine3310/ZoneLevelEngine/2 as zl
```
↓
```pine
import sekine3310/ZoneLevelEngine/3 as zl
```

### (2) Section 04B の `f_projectedLevel()`

```pine
f_projectedLevel(z) =>
    int r = z.trackId >= 0 ? PROJ_NA : PROJ_NA   // ← この行を削除
    // r := zl.projectLevelAfterNextTouch(z)     // ← このコメントを外す
    r
```

つなぎ込み前は `PROJ_NA (-1)` が返るため、
`PROJECTED_POST_TOUCH` を選んでも候補が 1 つも出ません
（**現在 Level で代用しない**ので、誤った集合でバックテストが回ることはありません）。
CSV Parity Audit の `Projected Source` 行が `NOT CONNECTED (v3)` と表示されます。

---

## 4. つなぎ込み後の確認

`08 · CSV Parity Audit` を ON にして確認します。

| 行 | 期待 |
|---|---|
| `Projected Source` | `zl (connected)` |
| `Projected Mismatch` | **0** |
| `Projected T1 Touches` | Logger の POST_TOUCH / Strong / EXACT / T1_ONLY の `Events` とほぼ一致 |

`Projected Mismatch > 0` の場合、**Strategy 側で帳尻を合わせないでください。**
「実 Level 計算」と「Projected 計算」が同じ内部関数を通っていない
（= (2)(3) の切り出しが不完全で、どこかに式が残っている）サインです。
ZoneLevelEngine 側を直してください。

### 参考：検証設定

Strategy:

| 項目 | 値 |
|---|---|
| Entry Mode | `EDGE_LIMIT` |
| Edge Limit Level Source | `PROJECTED_POST_TOUCH` |
| Edge Limit Level | `Strong` |
| Edge Limit Level Match | `EXACT` |
| Edge Limit Touch | `T1_ONLY` |
| TP Mode | `FIXED_MOVE` |
| Fixed Move | `20` |
| SL Buffer | `5` |
| Break Even | `OFF` |

Logger Repro:

| 項目 | 値 |
|---|---|
| Level | `Strong` |
| Level Match | `EXACT` |
| Level Timing | `POST_TOUCH` |
| Touch Filter | `T1_ONLY` |
| Target | `10 / 20 / 30` |

最初に見るのは PnL ではなく、
**Strategy が対象にしている T1 が CSV / Logger の POST_TOUCH Strong T1 と
同じ集合になったか**です。
