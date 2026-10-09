# 検証1 局面生成と正解計算

- 候補 3000 局面、各行動 1000 回
- 方針: Random（逃走なし）と ε-Rule（ε=0.3）。頑健性確認用に ε=0.2, 0.5 も計算
- 正解あり: 2方針で1位が同じ、かつ両方針で1位-2位の差 ≥ 15ポイント
- 拮抗: 両方針で1位-2位の差 < 5ポイント、かつ両方針で1位の勝率が 0.2〜0.8
- 計算時間: 479 秒（8並列、4方針の合計）

## 分類（ε=0.3）

- 正解あり 151 / 拮抗 83 / 不採用 2766
- 採用: 正解あり 100 / 拮抗 30
- 2方針で1位の行動が食い違った局面: 640 / 3000（21%）

## 正解行動の内訳

| 行動 | 抽出前（正解あり全体） | 抽出後（100局面） |
| --- | --- | --- |
| attack | 31 | 22 |
| power_attack | 8 | 7 |
| defend | 45 | 31 |
| potion | 67 | 40 |
| flee | 0 | 0 |

## 1位と2位の勝率差の分布（ε=0.3、2方針の小さい方、ポイント）

| 差 | 局面数 |
| --- | --- |
| 0〜5 | 2181 |
| 5〜10 | 448 |
| 10〜15 | 218 |
| 15〜20 | 85 |
| 20〜30 | 48 |
| 30〜50 | 18 |
| 50〜100 | 2 |

## 頑健性の確認（採用には使わない）

| ε | 正解ありの件数 | 採用した正解あり局面で、ε-Rule方針の1位が同じ割合 | 同（Random方針と合わせて正解ありの判定も同じ） |
| --- | --- | --- | --- |
| 0.2 | 117 | 100/100（100%） | 77/100（77%） |
| 0.5 | 234 | 100/100（100%） | 99/100（99%） |
| 0.3（本採用） | 151 | — | — |

## 局面例

### p0101（clear、正解 attack）

```
You are a knight in a one-on-one turn-based battle. Your goal is to win.
You: badly hurt, not enough MP for a power attack, no potions left.
Enemy: near death, enough MP for a power attack, 1 potion left.
Last turn the enemy unleashed its power attack.
```

| 行動 | Random方針 | ε-Rule方針 |
| --- | --- | --- |
| attack | 0.784 | 0.290 |
| defend | 0.363 | 0.057 |
| flee | 0.206 | 0.034 |

### p0237（clear、正解 defend）

```
You are a knight in a one-on-one turn-based battle. Your goal is to win.
You: wounded, enough MP for a power attack, no potions left.
Enemy: badly hurt, not enough MP for a power attack, no potions left, charging a power attack (it will hit hard next turn).
Last turn the enemy started charging.
```

| 行動 | Random方針 | ε-Rule方針 |
| --- | --- | --- |
| attack | 0.222 | 0.036 |
| power_attack | 0.273 | 0.103 |
| defend | 0.598 | 0.533 |
| flee | 0.092 | 0.004 |

### p0026（tie）

```
You are a knight in a one-on-one turn-based battle. Your goal is to win.
You: healthy, enough MP for a power attack, 1 potion left.
Enemy: wounded, not enough MP for a power attack, 2 potions left.
Last turn the enemy tried to run away but failed.
```

| 行動 | Random方針 | ε-Rule方針 |
| --- | --- | --- |
| attack | 0.489 | 0.443 |
| power_attack | 0.535 | 0.486 |
| defend | 0.430 | 0.367 |
| potion | 0.335 | 0.117 |
| flee | 0.291 | 0.183 |

### p0059（tie）

```
You are a knight in a one-on-one turn-based battle. Your goal is to win.
You: badly hurt, not enough MP for a power attack, 1 potion left.
Enemy: badly hurt, not enough MP for a power attack, 2 potions left.
Last turn the enemy attacked.
```

| 行動 | Random方針 | ε-Rule方針 |
| --- | --- | --- |
| attack | 0.481 | 0.375 |
| defend | 0.355 | 0.300 |
| potion | 0.458 | 0.388 |
| flee | 0.201 | 0.126 |

