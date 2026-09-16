# Projected Level（次 Touch 後 Level）の実装状況

## 結論：v2 のままで完成済み

`Zone_Level_Rebound_Strategy_Lite.pine` の

```
Entry Mode              = EDGE_LIMIT
Edge Limit Level Source = PROJECTED_POST_TOUCH
```

は **ZoneLevelEngine v2 のまま動作します**。新しいバージョンの publish 待ちの
TODO は残っていません。

```pine
import sekine3310/ZoneLevelEngine/2 as zl      // 131 行目

f_projectedLevel(z) =>                          // Section 04B
    zl.levelFrom(z.birthScore, z.touchCount + 1, lvlCfg)
```

## なぜ v2 で足りるのか

v2 は Level 判定を **private 関数 1 本に集約済み**で、しかもそれを export
しています。

```pine
// v2 : feedZone() の中（実際の Level 計算）
int _lv = f_levelOf(_bs, _tc, c)

// v2 : export
export levelFrom(float birthScore, int touchCount, ZoneLevelCfg c) =>
    f_levelOf(birthScore, touchCount, c)
```

つまり「Level 決定処理を共通 private 関数へ切り出す」作業は**既に終わっています**。
`levelFrom()` は実 Level 計算とまったく同じ `f_levelOf()` を呼ぶため、

```pine
zl.levelFrom(z.birthScore, z.touchCount + 1, lvlCfg)
```

は `f_levelOf(birthScore, touchCount + 1, cfg)` そのものであり、

- Strategy 側に Level 式を 1 つも書いていない（二重実装ゼロ）
- 閾値は同一インスタンス `lvlCfg`（`zl.newCfg()` の既定値）を渡すので実 Level 計算と同じ
- `birthScore` は誕生時に固定される値なので、**変えているのは `touchCount + 1` だけ**

を同時に満たします。v2 の既存判定結果も 1 件も変えていません（Library は無改変）。

## v3 は任意

より明示的な API 名 `projectLevelAfterNextTouch()` が欲しい場合の追加パッチを
`docs/ZoneLevelEngine_v3_patch.pine` に置いてあります。**計算結果は同じ**なので、
当てるかどうかは好みの問題です。当てる場合も既存行は 1 文字も変更せず、
関数を 1 つ追加するだけです。

## 確認方法

`08 · CSV Parity Audit` を ON にして確認します。

| 行 | 期待 |
|---|---|
| `Projected Source` | `zl.levelFrom(tc+1)` |
| `Projected Mismatch` | **0** |
| `Projected T1 Touches` | Logger の POST_TOUCH / Strong / EXACT / T1_ONLY の `Events` とほぼ一致 |

`Projected Mismatch > 0` になった場合、**Strategy 側で帳尻を合わせないでください。**
Projected と実 Level が別経路を通っているサインです。

### 検証設定

Strategy

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

Logger Repro

| 項目 | 値 |
|---|---|
| Level | `Strong` |
| Level Match | `EXACT` |
| Level Timing | `POST_TOUCH` |
| Touch Filter | `T1_ONLY` |
| Target | `10 / 20 / 30` |

最初に見るのは PnL ではなく、**Strategy が対象にしている T1 が CSV / Logger の
POST_TOUCH Strong T1 と同じ集合になったか**です。
