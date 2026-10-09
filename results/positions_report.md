# 検証1 局面生成と正解計算（候補 500 局面, 各行動 1000 回 × 2方針）

- 計算時間: 27 秒（8並列）
- 分類: 正解あり 7 / 正解なし（拮抗） 233 / 不採用 260
- 採用: 正解あり 7 / 拮抗 30
- RandomとRuleで1位の行動が食い違った局面: 292 / 500（58%）

## 正解あり局面の正解行動の内訳

| 行動 | 正解あり全体 | 採用100局面 |
| --- | --- | --- |
| attack | 0 | 0 |
| power_attack | 0 | 0 |
| defend | 2 | 2 |
| potion | 5 | 5 |
| flee | 0 | 0 |

## 1位と2位の勝率差の分布（候補全件、ポイント）

| 差 | Random方針 | Rule方針 | 2方針の小さい方 |
| --- | --- | --- | --- |
| 0〜5 | 249 | 421 | 437 |
| 5〜10 | 108 | 23 | 32 |
| 10〜20 | 107 | 17 | 24 |
| 20〜30 | 26 | 3 | 4 |
| 30〜50 | 10 | 15 | 3 |
| 50〜100 | 0 | 21 | 0 |

## 局面例

### p039（clear, 正解 defend）

```
You are a knight in a one-on-one turn-based battle. Your goal is to win.
You: wounded, not enough MP for a power attack, no potions left.
Enemy: badly hurt, not enough MP for a power attack, no potions left, charging a power attack (it will hit hard next turn).
Last turn the enemy started charging.
```

| 行動 | Random方針 | Rule方針 |
| --- | --- | --- |
| attack | 0.092 | 0.000 |
| defend | 0.317 | 0.212 |
| flee | 0.008 | 0.000 |

### p237（clear, 正解 defend）

```
You are a knight in a one-on-one turn-based battle. Your goal is to win.
You: wounded, enough MP for a power attack, no potions left.
Enemy: badly hurt, not enough MP for a power attack, no potions left, charging a power attack (it will hit hard next turn).
Last turn the enemy started charging.
```

| 行動 | Random方針 | Rule方針 |
| --- | --- | --- |
| attack | 0.216 | 0.000 |
| power_attack | 0.274 | 0.000 |
| defend | 0.589 | 0.521 |
| flee | 0.074 | 0.000 |

### p002（tie）

```
You are a knight in a one-on-one turn-based battle. Your goal is to win.
You: wounded, enough MP for a power attack, 1 potion left.
Enemy: healthy, enough MP for a power attack, no potions left.
Last turn the enemy tried to run away but failed.
```

| 行動 | Random方針 | Rule方針 |
| --- | --- | --- |
| attack | 0.152 | 0.003 |
| power_attack | 0.217 | 0.002 |
| defend | 0.129 | 0.000 |
| potion | 0.258 | 0.001 |
| flee | 0.081 | 0.000 |

### p007（tie）

```
You are a knight in a one-on-one turn-based battle. Your goal is to win.
You: badly hurt, enough MP for a power attack, 2 potions left.
Enemy: near death, enough MP for a power attack, 1 potion left.
Last turn the enemy attacked.
```

| 行動 | Random方針 | Rule方針 |
| --- | --- | --- |
| attack | 0.906 | 1.000 |
| power_attack | 0.840 | 1.000 |
| defend | 0.716 | 1.000 |
| potion | 0.951 | 1.000 |
| flee | 0.497 | 0.692 |

