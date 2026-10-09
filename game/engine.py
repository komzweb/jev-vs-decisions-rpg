"""バトルのルール・乱数・勝敗判定・events生成（SPEC.md「ゲームルール」）。"""

from __future__ import annotations

import random
from dataclasses import dataclass, field, asdict

MAX_HP = 100
MAX_MP = 30
START_POTIONS = 2
MAX_TURNS = 30

ATTACK_DAMAGE = (12, 18)
POWER_DAMAGE = (28, 36)
POWER_MP_COST = 10
DEFEND_REDUCTION = 0.7
POTION_HEAL = 35
FLEE_SUCCESS_RATE = 0.30
MP_REGEN = 2

ACTIONS = ["attack", "power_attack", "defend", "potion", "flee"]
SIDES = ("left", "right")


def other(side: str) -> str:
    return "right" if side == "left" else "left"


@dataclass
class Fighter:
    hp: int = MAX_HP
    mp: int = MAX_MP
    potions: int = START_POTIONS
    charging: bool = False          # 溜め中（次のターンに強攻撃が自動で発動する）
    last_action: str | None = None  # 直前ターンの行動（power_release を含む）


@dataclass
class Battle:
    seed: int
    turn: int = 0  # 直近に解決したターン番号
    fighters: dict[str, Fighter] = field(
        default_factory=lambda: {"left": Fighter(), "right": Fighter()}
    )
    over: bool = False
    winner: str | None = None       # "left" / "right" / None（引き分け・未決着）
    end_reason: str | None = None   # "ko" / "flee" / "timeout"
    fled: str | None = None         # 逃走に成功した側

    def __post_init__(self) -> None:
        self.rng = random.Random(self.seed)

    # --- 問い合わせ ---------------------------------------------------------

    def is_locked(self, side: str) -> bool:
        """溜め中は行動を選べず、このターンは強攻撃の発動で固定。"""
        return self.fighters[side].charging

    def available_actions(self, side: str) -> list[str]:
        f = self.fighters[side]
        if f.charging:
            return []
        acts = []
        for a in ACTIONS:
            if a == "power_attack" and f.mp < POWER_MP_COST:
                continue
            if a == "potion" and f.potions <= 0:
                continue
            acts.append(a)
        return acts

    def game_state(self, side: str) -> dict:
        """side 視点のスナップショット（ログ・状態文の元データ）。"""
        me, en = self.fighters[side], self.fighters[other(side)]
        return {
            "turn": self.turn + 1,
            "hp": me.hp, "mp": me.mp, "potions": me.potions, "charging": me.charging,
            "enemy_hp": en.hp, "enemy_mp": en.mp, "enemy_potions": en.potions,
            "enemy_charging": en.charging, "enemy_last_action": en.last_action,
        }

    # --- 1ターン解決 --------------------------------------------------------

    def step(self, actions: dict[str, str | None]) -> list[dict]:
        """両者の行動を同時に解決し、そのターンの events を返す。

        溜め中の側の行動は無視され、強攻撃の発動（power_release）になる。
        解決順：溜め開始 → 防御 → 回復 → 逃走 → 攻撃 → KO判定 → MP回復。
        """
        assert not self.over
        self.turn += 1
        events: list[dict] = []
        acts: dict[str, str] = {}
        for s in SIDES:
            f = self.fighters[s]
            if f.charging:
                acts[s] = "power_release"
            else:
                a = actions[s]
                if a not in self.available_actions(s):
                    raise ValueError(f"{s}: action {a!r} not available")
                acts[s] = a

        # 溜め開始（MP消費）
        for s in SIDES:
            if acts[s] == "power_attack":
                self.fighters[s].mp -= POWER_MP_COST
                events.append({"type": "charge_start", "target": s})

        defending = {s: acts[s] == "defend" for s in SIDES}

        # 回復
        for s in SIDES:
            if acts[s] == "potion":
                f = self.fighters[s]
                f.potions -= 1
                amount = min(POTION_HEAL, MAX_HP - f.hp)
                f.hp += amount
                events.append({"type": "heal", "target": s, "amount": amount})

        # 逃走（攻撃より先に判定。成功したらそのターンの攻撃は発生しない）
        fled = []
        for s in SIDES:
            if acts[s] == "flee":
                if self.rng.random() < FLEE_SUCCESS_RATE:
                    fled.append(s)
                    events.append({"type": "flee_success", "target": s})
                else:
                    events.append({"type": "flee_fail", "target": s})
        if fled:
            self.over = True
            self.end_reason = "flee"
            if len(fled) == 1:
                self.fled = fled[0]
                self.winner = other(fled[0])
            self._finish_turn(acts)
            return events

        # 攻撃（同時に適用）
        for s in SIDES:
            src = acts[s]
            if src not in ("attack", "power_release"):
                continue
            lo, hi = ATTACK_DAMAGE if src == "attack" else POWER_DAMAGE
            dmg = self.rng.randint(lo, hi)
            tgt = other(s)
            blocked = defending[tgt]
            if blocked:
                dmg = round(dmg * (1 - DEFEND_REDUCTION))
            self.fighters[tgt].hp -= dmg
            source = "attack" if src == "attack" else "power_attack"
            events.append({"type": "damage", "target": tgt, "amount": dmg,
                           "source": source, "blocked": blocked})

        # KO判定
        ko = [s for s in SIDES if self.fighters[s].hp <= 0]
        for s in ko:
            events.append({"type": "ko", "target": s})
        if ko:
            self.over = True
            self.end_reason = "ko"
            self.winner = other(ko[0]) if len(ko) == 1 else None
            self._finish_turn(acts)
            return events

        # MP回復
        for s in SIDES:
            f = self.fighters[s]
            amount = min(MP_REGEN, MAX_MP - f.mp)
            if amount > 0:
                f.mp += amount
                events.append({"type": "mp_regen", "target": s, "amount": amount})

        self._finish_turn(acts)

        # タイムアウト（HP割合が高い方の勝ち。最大HPは同じなのでHPで比較）
        if not self.over and self.turn >= MAX_TURNS:
            self.over = True
            self.end_reason = "timeout"
            l, r = self.fighters["left"].hp, self.fighters["right"].hp
            self.winner = "left" if l > r else "right" if r > l else None
        return events

    def _finish_turn(self, acts: dict[str, str]) -> None:
        for s in SIDES:
            f = self.fighters[s]
            f.charging = acts[s] == "power_attack"
            f.last_action = acts[s]

    def snapshot(self) -> dict:
        return {s: asdict(f) for s, f in self.fighters.items()}


def play_match(seed: int, npcs: dict, on_turn=None) -> Battle:
    """NPC同士で1試合を最後まで進める。

    npcs: {"left": npc, "right": npc}。npc.act(battle, side) -> 行動ID。
    on_turn(battle, actions, events) はターン解決ごとに呼ばれる（ログ用）。
    """
    battle = Battle(seed=seed)
    while not battle.over:
        actions = {
            s: None if battle.is_locked(s) else npcs[s].act(battle, s) for s in SIDES
        }
        events = battle.step(actions)
        if on_turn:
            on_turn(battle, actions, events)
    return battle
