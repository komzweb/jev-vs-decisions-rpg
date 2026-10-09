# 手順1 エンジン確認（各100試合。同型対戦は seed=0..99、Rule vs Random は seed=0..49 × 左右入れ替え）

| 対戦 | 試合 | 結果内訳 | 平均ターン | 最短/最長 | 行動内訳(%) |
| --- | --- | --- | --- | --- | --- |
| random vs random | 100 | flee: 81, ko_left: 10, ko_right: 9 | 6.1 | 1/18 | flee 23.6, defend 21.8, attack 20.3, power_attack 18.7, potion 15.7 |
| rule vs rule | 100 | ko_draw: 59, ko_left: 21, ko_right: 20 | 12.7 | 12/14 | attack 74.2, potion 17.2, power_attack 8.6 |
| rule_vs_random | 100 | flee: 58, ko_left: 17, ko_right: 25 | 8.2 | 1/19 | attack 44.1, defend 18.5, power_attack 18.3, flee 10.9, potion 8.2 |

## Rule vs Random

- Rule勝ち 100 / Random勝ち 0 / 引き分け 0（Rule勝率 100%）
- 行動内訳(%) Rule: {'attack': 66.8, 'power_attack': 16.3, 'defend': 14.9, 'potion': 2.0}
- 行動内訳(%) Random: {'defend': 22.2, 'flee': 22.1, 'attack': 20.8, 'power_attack': 20.3, 'potion': 14.5}
- Randomの逃走成功はRandomの負けとして数える

- 行動内訳は自分で選んだ行動のみ（溜め後の強攻撃発動ターンは除外）。
- 結果内訳: ko_left/ko_right=KO勝ち, ko_draw=相打ち, flee=逃走成功で終了,
  timeout_decided/timeout_draw=30ターン経過（HP比較で決着/同値）。
