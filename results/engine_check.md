# 手順1 エンジン確認（Random同士・Rule同士 各100試合, seed=0..99）

| 対戦 | 試合 | 結果内訳 | 平均ターン | 最短/最長 | 行動内訳(%) |
| --- | --- | --- | --- | --- | --- |
| random vs random | 100 | flee: 88, ko_left: 4, ko_right: 8 | 6.5 | 1/20 | flee 23.5, defend 21.4, attack 20.2, power_attack 19.7, potion 15.2 |
| rule vs rule | 100 | ko_draw: 57, ko_left: 17, ko_right: 26 | 13.5 | 13/14 | attack 76.0, potion 16.0, power_attack 8.0 |

- 行動内訳は自分で選んだ行動のみ（溜め後の強攻撃発動ターンは除外）。
- 結果内訳: ko_left/ko_right=KO勝ち, ko_draw=相打ち, flee=逃走成功で終了,
  timeout_decided/timeout_draw=30ターン経過（HP比較で決着/同値）。
