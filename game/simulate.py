"""局面ごとの行動別勝率をシミュレーションで計算する（SPEC.md「検証1」の正解）。

1手目に自分が指定の行動を取り、相手の1手目と2手目以降（自分・相手とも）は方針（policy）で動かす。
- "random":       逃走を選ばない Random（シミュレーション専用）
- "eps_rule:<ε>":  確率εで逃走以外から一様ランダム、残りは Rule と同じ行動（シミュレーション専用）
- "rule":         Rule NPC（決定的なため検証1の採用には使わない）
各試行のシードは (局面ID, 試行番号) から決まる。同じ試行番号は行動間で同じ乱数列を使う。
"""

from __future__ import annotations

import random

from game.engine import Battle, other
from game.npcs import EpsilonRuleNPC, RandomNPC, RuleNPC

ME = "left"
ENEMY = other(ME)


def make_policy(policy: str, seed: str):
    if policy == "random":
        return RandomNPC(seed, allow_flee=False)
    if policy == "rule":
        return RuleNPC()
    if policy.startswith("eps_rule:"):
        return EpsilonRuleNPC(float(policy.split(":", 1)[1]), seed)
    raise ValueError(policy)


def play_from(gs: dict, first_action: str, policy: str, pos_id: str, trial: int) -> str | None:
    """1試行を最後まで進め、勝者（"left"=自分 / "right" / None=引き分け）を返す。"""
    seed = f"{pos_id}-{trial}"
    b = Battle.from_state(gs, seed=seed, side=ME)
    npcs = {ME: make_policy(policy, f"{seed}-me"), ENEMY: make_policy(policy, f"{seed}-enemy")}
    first = True
    while not b.over:
        actions = {}
        for s in (ME, ENEMY):
            if b.is_locked(s):
                actions[s] = None
            elif first and s == ME:
                actions[s] = first_action
            else:
                actions[s] = npcs[s].act(b, s)
        first = False
        b.step(actions)
    return b.winner


def win_rates(gs: dict, available: list[str], policy: str, pos_id: str,
              trials: int) -> dict[str, float]:
    """行動ごとの勝率（勝ち数 / 試行数。引き分け・逃走成功は勝ちに数えない）。"""
    rates = {}
    for a in available:
        wins = sum(play_from(gs, a, policy, pos_id, t) == ME for t in range(trials))
        rates[a] = wins / trials
    return rates


def ranked(rates: dict[str, float]) -> list[tuple[str, float]]:
    return sorted(rates.items(), key=lambda kv: kv[1], reverse=True)


def gap(rates: dict[str, float]) -> float:
    r = ranked(rates)
    return r[0][1] - r[1][1] if len(r) > 1 else 1.0


# --- 局面の生成 ---------------------------------------------------------------

def generate_position(rng: random.Random) -> dict:
    """ゲーム中に実際に起こりうる局面を1つ作る（自分は行動を選べる状態）。"""
    from game.engine import MAX_HP, MAX_MP, POWER_DAMAGE, POWER_MP_COST, MP_REGEN, START_POTIONS

    while True:
        turn = rng.randint(1, 29)
        if turn == 1:
            return {"turn": 1, "hp": MAX_HP, "mp": MAX_MP, "potions": START_POTIONS,
                    "charging": False, "enemy_hp": MAX_HP, "enemy_mp": MAX_MP,
                    "enemy_potions": START_POTIONS, "enemy_charging": False,
                    "enemy_last_action": None}
        past = turn - 1
        max_dmg = POWER_DAMAGE[1] * past  # これまでに受けうる最大ダメージ
        gs = {"turn": turn, "charging": False}
        for prefix in ("", "enemy_"):
            gs[prefix + "hp"] = rng.randint(max(1, MAX_HP - max_dmg), MAX_HP)
            gs[prefix + "potions"] = rng.randint(max(0, START_POTIONS - past), START_POTIONS)
            gs[prefix + "mp"] = rng.randrange(0, MAX_MP + 1, 2)  # MPは常に偶数
        charging = rng.random() < 0.25
        gs["enemy_charging"] = charging
        if charging:
            # 前ターンに溜めた：溜め時にMP10以上 → 現在は (溜め前MP - 10 + 2) ≤ 22
            if gs["enemy_mp"] > MAX_MP - POWER_MP_COST + MP_REGEN:
                continue
            gs["enemy_last_action"] = "power_attack"
        else:
            last = rng.choice(["attack", "defend", "potion", "flee", "power_release"])
            if last == "potion" and gs["enemy_potions"] == START_POTIONS:
                continue
            if last == "power_release" and (past < 2 or gs["enemy_mp"] > MAX_MP - POWER_MP_COST + 2 * MP_REGEN):
                continue  # 発動には溜めのターンが前に必要（MPは溜めで10減っている）
            gs["enemy_last_action"] = last
        return gs
