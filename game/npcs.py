"""比較用の Random NPC と Rule NPC（SPEC.md「検証2」）。"""

from __future__ import annotations

import random

from game.describe import hp_bucket
from game.engine import Battle, other


class RandomNPC:
    name = "random"

    def __init__(self, seed: int | str | None = None, allow_flee: bool = True):
        self.rng = random.Random(seed)
        self.allow_flee = allow_flee  # False は検証1のシミュレーション専用

    def act(self, battle: Battle, side: str) -> str:
        acts = battle.available_actions(side)
        if not self.allow_flee:
            acts = [a for a in acts if a != "flee"]
        return self.rng.choice(acts)


class RuleNPC:
    name = "rule"

    def act(self, battle: Battle, side: str) -> str:
        me, en = battle.fighters[side], battle.fighters[other(side)]
        avail = battle.available_actions(side)
        if en.charging:
            return "defend"
        if hp_bucket(me.hp) == "near death" and "potion" in avail:
            return "potion"
        if "power_attack" in avail and hp_bucket(en.hp) == "healthy":
            return "power_attack"
        return "attack"
