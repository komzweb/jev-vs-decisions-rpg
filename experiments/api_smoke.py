"""実装順序 手順2：両APIの疎通確認。

同じ局面1つを、選択肢の順番を変えて3回ずつ両APIに投げ、生レスポンスを保存する。
uv run python -m experiments.api_smoke → logs_sample/api_smoke.json
"""

from __future__ import annotations

import json
import random
from dataclasses import asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

from config.prompts import ACTION_DESCRIPTIONS, ACTION_QUESTION
from deciders.jev import JevDecider
from deciders.openai_decisions import DecisionsDecider
from game.describe import describe

ROOT = Path(__file__).resolve().parent.parent
JST = timezone(timedelta(hours=9))

# SPEC.mdの状態文の例に相当する局面
GAME_STATE = {
    "turn": 6, "hp": 30, "mp": 12, "potions": 1, "charging": False,
    "enemy_hp": 60, "enemy_mp": 4, "enemy_potions": 1,
    "enemy_charging": True, "enemy_last_action": "power_attack",
}
AVAILABLE = ["attack", "power_attack", "defend", "potion", "flee"]
N_ORDERS = 3


def main() -> None:
    state = describe(GAME_STATE)
    rng = random.Random(0)
    orders = []
    while len(orders) < N_ORDERS:
        o = AVAILABLE[:]
        rng.shuffle(o)
        if o not in orders:
            orders.append(o)

    deciders = [JevDecider(), DecisionsDecider(seed=0)]
    calls = []
    for order in orders:
        options = {a: ACTION_DESCRIPTIONS[a] for a in order}
        for d in deciders:  # 両APIに同じ並び順を使う
            dec = d.choose(state, ACTION_QUESTION, options)
            rec = {
                "api": d.name,
                "model": d.model,
                "option_order": order,
                "request": d.request_body(state, ACTION_QUESTION, options),
                "timestamp": datetime.now(JST).isoformat(timespec="seconds"),
                **{k: v for k, v in asdict(dec).items() if k != "raw"},
                "raw": dec.raw,
            }
            calls.append(rec)
            print(f"{d.name:9s} {order} -> {dec.choice} conf={dec.confidence} "
                  f"lat={dec.latency_ms:.0f}ms tok={dec.input_tokens}")

    out = {"game_state": GAME_STATE, "state_text": state, "calls": calls}
    (ROOT / "logs_sample" / "api_smoke.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
