"""数値の状態 → 英語の状態文（SPEC.md「状態の言語化ルール」）。"""

from __future__ import annotations

from config import prompts as P
from game.engine import MAX_HP


def hp_bucket(hp: int, max_hp: int = MAX_HP) -> str:
    pct = max(hp, 0) / max_hp * 100
    for lower, text in P.HP_BUCKETS:
        if pct >= lower:
            return text
    return P.HP_BUCKETS[-1][1]


def mp_text(mp: int) -> str:
    return P.MP_ENOUGH if mp >= P.MP_POWER_ATTACK_THRESHOLD else P.MP_NOT_ENOUGH


def potion_text(n: int) -> str:
    return P.POTION_TEXT[min(n, 2)]


def describe(gs: dict, lang: str = "en") -> str:
    """engine.Battle.game_state() の dict から状態文を作る。lang="ja" は日本語版（おまけB）。"""
    if lang == "ja":
        return describe_ja(gs)
    you = f"You: {hp_bucket(gs['hp'])}, {mp_text(gs['mp'])}, {potion_text(gs['potions'])}."
    enemy_parts = [
        hp_bucket(gs["enemy_hp"]),
        mp_text(gs["enemy_mp"]),
        potion_text(gs["enemy_potions"]),
    ]
    if gs["enemy_charging"]:
        enemy_parts.append(P.ENEMY_CHARGING)
    lines = [P.INTRO, you, f"Enemy: {', '.join(enemy_parts)}."]
    last = gs.get("enemy_last_action")
    if last:
        lines.append(P.LAST_ENEMY_ACTION[last])
    if gs["turn"] >= P.TIMEOUT_WARNING_TURN:
        lines.append(P.TIMEOUT_WARNING)
    return "\n".join(lines)


def describe_ja(gs: dict) -> str:
    """describe() の日本語版。バケツの閾値は英語版と共通。"""
    def parts(hp, mp, potions):
        return [P.HP_TEXT_JA[hp_bucket(hp)],
                P.MP_ENOUGH_JA if mp >= P.MP_POWER_ATTACK_THRESHOLD else P.MP_NOT_ENOUGH_JA,
                P.POTION_TEXT_JA[min(potions, 2)]]

    enemy = parts(gs["enemy_hp"], gs["enemy_mp"], gs["enemy_potions"])
    if gs["enemy_charging"]:
        enemy.append(P.ENEMY_CHARGING_JA)
    lines = [P.INTRO_JA,
             f"あなた：{'、'.join(parts(gs['hp'], gs['mp'], gs['potions']))}。",
             f"敵：{'、'.join(enemy)}。"]
    last = gs.get("enemy_last_action")
    if last:
        lines.append(P.LAST_ENEMY_ACTION_JA[last])
    if gs["turn"] >= P.TIMEOUT_WARNING_TURN:
        lines.append(P.TIMEOUT_WARNING_JA)
    return "\n".join(lines)
