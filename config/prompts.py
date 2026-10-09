"""質問文・選択肢の説明・状態文の言語化ルール（閾値）・検証の採用基準をまとめた唯一の定義ファイル。

両APIで1文字も変えずに共通利用する（SPEC.md「API呼び出し仕様」「状態の言語化ルール」）。
"""

# --- 行動の質問 -------------------------------------------------------------

ACTION_QUESTION = "Which action should you take this turn to maximize your chance of winning?"

ACTION_DESCRIPTIONS: dict[str, str] = {
    "attack": "A normal attack dealing moderate damage.",
    "power_attack": (
        "Spend 10 MP to charge this turn and deal heavy damage next turn. "
        "The enemy can see you charging."
    ),
    "defend": "Block. Takes 70% less damage this turn.",
    "potion": "Drink a potion to restore a large amount of HP.",
    "flee": "Try to run away. Succeeds only sometimes, and fleeing counts as not winning.",
}

# --- 状態文 ----------------------------------------------------------------

INTRO = "You are a knight in a one-on-one turn-based battle. Your goal is to win."

# HP割合のバケツ（下限%, 文言）。上から順に判定する。
HP_BUCKETS: list[tuple[int, str]] = [
    (80, "healthy"),
    (50, "wounded"),
    (20, "badly hurt"),
    (0, "near death"),
]

MP_POWER_ATTACK_THRESHOLD = 10
MP_ENOUGH = "enough MP for a power attack"
MP_NOT_ENOUGH = "not enough MP for a power attack"

POTION_TEXT = {2: "2 potions left", 1: "1 potion left", 0: "no potions left"}

ENEMY_CHARGING = "charging a power attack (it will hit hard next turn)"

# 直前の相手の行動。SPECの4種に加え、逃走失敗と強攻撃の発動も文言を用意している。
LAST_ENEMY_ACTION = {
    "attack": "Last turn the enemy attacked.",
    "defend": "Last turn the enemy defended.",
    "potion": "Last turn the enemy used a potion.",
    "power_attack": "Last turn the enemy started charging.",
    "power_release": "Last turn the enemy unleashed its power attack.",
    "flee": "Last turn the enemy tried to run away but failed.",
}

TIMEOUT_WARNING_TURN = 25
TIMEOUT_WARNING = "The battle is about to time out."


# --- 検証1 正解計算の設定・採用基準（SPEC.md「検証1」） ------------------------

POS_N_CANDIDATES = 3000
POS_TRIALS = 1000
POS_GEN_SEED = 20261009
POS_SELECT_SEED = 1
POS_EPSILON = 0.3                    # 本採用の ε-Rule の ε
POS_ROBUSTNESS_EPSILONS = (0.2, 0.5)  # 頑健性確認用（採用には使わない）
POS_CLEAR_GAP = 0.15        # 正解あり：2方針で1位が同じ、かつ両方針で1位-2位の差がこれ以上
POS_TIE_GAP = 0.05          # 拮抗：両方針で1位-2位の差がこれ未満
POS_TIE_TOP_RANGE = (0.2, 0.8)  # 拮抗：両方針で1位の勝率がこの範囲（両端含む）
POS_N_CLEAR = 100
POS_N_TIE = 30
POS_MAX_SAME_ANSWER = 40    # 抽出する正解あり局面で、同じ正解行動の上限
