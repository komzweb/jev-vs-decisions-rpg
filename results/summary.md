# 集計（速度・コスト・対戦）

## 速度（ウォームアップ・リトライ発生分を除く）

| API | n | p50 (ms) | p95 (ms) | 最大 (ms) |
| --- | --- | --- | --- | --- |
| jev | 846 | 168 | 214 | 472 |
| decisions | 862 | 203 | 297 | 607 |

## コスト（全呼び出し）

| API | 呼び出し | 平均入力トークン | 合計入力トークン | 費用 (USD) | 1,000回あたり (USD) |
| --- | --- | --- | --- | --- | --- |
| jev | 856 | 465.3 | 398282 | 0.016728 | 0.019542 |
| decisions | 872 | 248.9 | 217000 | 0.021700 | 0.024885 |

## 対戦結果

| match_id | left | right | winner | end_reason | turns |
| --- | --- | --- | --- | --- | --- |
| jev_vs_decisions_s00 | jev | decisions | jev | ko | 16 |
| jev_vs_decisions_s00_swap | decisions | jev | decisions | ko | 23 |
| jev_vs_decisions_s01 | jev | decisions | decisions | ko | 20 |
| jev_vs_decisions_s01_swap | decisions | jev | decisions | ko | 20 |
| jev_vs_decisions_s02 | jev | decisions | decisions | ko | 21 |
| jev_vs_decisions_s02_swap | decisions | jev | decisions | ko | 25 |
| jev_vs_decisions_s03 | jev | decisions | decisions | ko | 20 |
| jev_vs_decisions_s03_swap | decisions | jev | decisions | ko | 26 |
| jev_vs_decisions_s04 | jev | decisions | decisions | ko | 26 |
| jev_vs_decisions_s04_swap | decisions | jev | decisions | ko | 26 |

- 勝ち数: {'jev': 1, 'decisions': 9}
- 終了理由: {'ko': 10}
- 平均ターン数: 22.3

### 行動の内訳（自分で選んだ行動のみ）

| 行動 | jev | decisions |
| --- | --- | --- |
| attack | 12.6% | 89.6% |
| power_attack | 9.7% | 0.5% |
| defend | 68.0% | 3.6% |
| potion | 9.7% | 6.3% |
| flee | 0.0% | 0.0% |

### 相手が溜め中のときに防御した率

- jev: 1/1（100%）
- decisions: 6/17（35%）

- 対戦中の refusal（ランダム行動で代替）: 0
