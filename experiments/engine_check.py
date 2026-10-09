"""実装順序 手順1の確認：Random同士・Rule同士で100試合ずつ、Rule vs Randomを左右入れ替えで100試合回す（API不要）。

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


def make_npcs(kind: str, seed: int) -> tuple[dict, dict[str, str]]:
    """(npcs, side -> NPC名)。rule_vs_random は 50シード × 左右入れ替え。"""
    if kind == "random":
        return {s: RandomNPC(f"{seed}-{s}") for s in SIDES}, {"left": "random", "right": "random"}
    if kind == "rule":
        return {s: RuleNPC() for s in SIDES}, {"left": "rule", "right": "rule"}
    rule_side = "left" if seed % 2 == 0 else "right"
    names = {rule_side: "rule", ("right" if rule_side == "left" else "left"): "random"}
    npcs = {s: RuleNPC() if names[s] == "rule" else RandomNPC(f"{seed // 2}-{s}") for s in SIDES}
    return npcs, names


def run(kind: str) -> dict:
    outcomes = Counter()
    wins_by_npc = Counter()
    turns = []
    action_counts = Counter()
    action_by_npc: dict[str, Counter] = {}
    samples = []
    for i in range(N):
        seed = i // 2 if kind == "rule_vs_random" else i
        npcs, names = make_npcs(kind, i)
        turn_log = []

        def on_turn(battle, actions, events, turn_log=turn_log):
            for s in SIDES:
                if actions[s] is not None:
                    action_counts[actions[s]] += 1
                    action_by_npc.setdefault(names[s], Counter())[actions[s]] += 1
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
        if b.winner is not None:
            wins_by_npc[names[b.winner]] += 1
        else:
            wins_by_npc["draw"] += 1
        turns.append(b.turn)
        if i == 0:
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
        "wins_by_npc": dict(wins_by_npc),
        "actions_by_npc": {n: {a: round(100 * c / sum(cnt.values()), 1) for a, c in cnt.most_common()}
                           for n, cnt in action_by_npc.items()},
        "sample": samples,
    }


def main() -> None:
    results = [run("random"), run("rule"), run("rule_vs_random")]
    lines = ["# 手順1 エンジン確認（各100試合。同型対戦は seed=0..99、Rule vs Random は seed=0..49 × 左右入れ替え）", ""]
    lines.append("| 対戦 | 試合 | 結果内訳 | 平均ターン | 最短/最長 | 行動内訳(%) |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for r in results:
        lines.append(
            f"| {r['kind'] if '_vs_' in r['kind'] else r['kind'] + ' vs ' + r['kind']} | {r['matches']} | "
            f"{', '.join(f'{k}: {v}' for k, v in sorted(r['outcomes'].items()))} | "
            f"{r['avg_turns']:.1f} | {r['min_turns']}/{r['max_turns']} | "
            f"{', '.join(f'{k} {v}' for k, v in r['actions_pct'].items())} |"
        )
    rvr = results[2]
    w = rvr["wins_by_npc"]
    lines += ["", "## Rule vs Random", "",
              f"- Rule勝ち {w.get('rule', 0)} / Random勝ち {w.get('random', 0)} / 引き分け {w.get('draw', 0)}"
              f"（Rule勝率 {100 * w.get('rule', 0) / rvr['matches']:.0f}%）",
              f"- 行動内訳(%) Rule: {rvr['actions_by_npc']['rule']}",
              f"- 行動内訳(%) Random: {rvr['actions_by_npc']['random']}",
              "- Randomの逃走成功はRandomの負けとして数える"]
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
