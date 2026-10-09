"""実装順序 手順1の確認：Random同士・Rule同士で100試合ずつ回す（API不要）。

uv run python -m experiments.engine_check
→ results/engine_check.md, logs_sample/engine_events_sample.json
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from game.describe import describe
from game.engine import SIDES, play_match
from game.npcs import RandomNPC, RuleNPC

ROOT = Path(__file__).resolve().parent.parent
N = 100


def run(kind: str) -> dict:
    outcomes = Counter()
    turns = []
    action_counts = Counter()
    samples = []
    for seed in range(N):
        if kind == "random":
            npcs = {s: RandomNPC(f"{seed}-{s}") for s in SIDES}
        else:
            npcs = {s: RuleNPC() for s in SIDES}
        turn_log = []

        def on_turn(battle, actions, events, turn_log=turn_log):
            for s in SIDES:
                if actions[s] is not None:
                    action_counts[actions[s]] += 1
            turn_log.append({"turn": battle.turn, "actions": actions, "events": events,
                             "after": battle.snapshot()})

        b = play_match(seed, npcs, on_turn)
        if b.end_reason == "flee":
            outcomes["flee"] += 1
        elif b.end_reason == "timeout":
            outcomes["timeout_" + ("draw" if b.winner is None else "decided")] += 1
        elif b.winner is None:
            outcomes["ko_draw"] += 1
        else:
            outcomes["ko_" + b.winner] += 1
        turns.append(b.turn)
        if seed == 0:
            samples = turn_log
    total_actions = sum(action_counts.values())
    return {
        "kind": kind,
        "matches": N,
        "outcomes": dict(outcomes),
        "avg_turns": sum(turns) / len(turns),
        "min_turns": min(turns),
        "max_turns": max(turns),
        "actions_pct": {a: round(100 * c / total_actions, 1)
                        for a, c in action_counts.most_common()},
        "sample": samples,
    }


def main() -> None:
    results = [run("random"), run("rule")]
    lines = ["# 手順1 エンジン確認（Random同士・Rule同士 各100試合, seed=0..99）", ""]
    lines.append("| 対戦 | 試合 | 結果内訳 | 平均ターン | 最短/最長 | 行動内訳(%) |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for r in results:
        lines.append(
            f"| {r['kind']} vs {r['kind']} | {r['matches']} | "
            f"{', '.join(f'{k}: {v}' for k, v in sorted(r['outcomes'].items()))} | "
            f"{r['avg_turns']:.1f} | {r['min_turns']}/{r['max_turns']} | "
            f"{', '.join(f'{k} {v}' for k, v in r['actions_pct'].items())} |"
        )
    lines += ["", "- 行動内訳は自分で選んだ行動のみ（溜め後の強攻撃発動ターンは除外）。",
              "- 結果内訳: ko_left/ko_right=KO勝ち, ko_draw=相打ち, flee=逃走成功で終了,",
              "  timeout_decided/timeout_draw=30ターン経過（HP比較で決着/同値）。"]
    (ROOT / "results" / "engine_check.md").write_text("\n".join(lines) + "\n")

    # 1試合分の events サンプル（Random同士 seed=0）と、最初のターンの状態文
    from game.engine import Battle
    sample = {
        "match": "random_vs_random_s0",
        "turns": results[0]["sample"],
        "state_text_example_turn1_left": describe(Battle(seed=0).game_state("left")),
    }
    (ROOT / "logs_sample" / "engine_events_sample.json").write_text(
        json.dumps(sample, indent=2, ensure_ascii=False) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
