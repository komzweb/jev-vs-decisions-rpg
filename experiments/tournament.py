"""検証2：対戦トーナメント。

uv run python -m experiments.tournament jev decisions --seeds 0-4            # 10試合（左右入れ替え）
uv run python -m experiments.tournament jev rule --seeds 0-24 --dry-run      # APIの代わりにRandom NPC

ログ：logs/tournament.jsonl（API呼び出し1回につき1行。溜め中で行動を選べないターンも
replay用に actor ごとに1行残し、"forced": true とする）
結果：results/tournament.csv（1試合1行）
--dry-run のときは logs/tournament_dry.jsonl・results/tournament_dry.csv に書く
"""

from __future__ import annotations

import argparse
import csv
import random

from config.prompts import ACTION_DESCRIPTIONS, ACTION_QUESTION
from deciders.base import Decision
from experiments.common import ROOT, WarmupCounter, append_jsonl, decision_fields, now, read_jsonl
from game.describe import describe
from game.engine import SIDES, Battle
from game.npcs import RandomNPC, RuleNPC

LOG = ROOT / "logs" / "tournament.jsonl"
CSV = ROOT / "results" / "tournament.csv"
CSV_FIELDS = ["match_id", "left", "right", "seed", "winner", "end_reason", "turns"]
API_NAMES = ("jev", "decisions")


class DryRunDecider:
    """--dry-run 用：APIを呼ばずに一様ランダムで選ぶ Decider。"""

    def __init__(self, name: str, seed):
        self.name = name
        self.model = f"dry-run-{name}"
        self.rng = random.Random(seed)

    def choose(self, state: str, instructions: str, options: dict[str, str]) -> Decision:
        c = self.rng.choice(list(options))
        return Decision(choice=c, probabilities={k: 1 / len(options) for k in options},
                        confidence=None, latency_ms=0.0, input_tokens=None, raw={})


def make_deciders(names: list[str], dry_run: bool) -> dict:
    out = {}
    for n in names:
        if n not in API_NAMES or n in out:
            continue
        if dry_run:
            out[n] = DryRunDecider(n, n)
        elif n == "jev":
            from deciders.jev import JevDecider
            out[n] = JevDecider()
        else:
            from deciders.openai_decisions import DecisionsDecider
            out[n] = DecisionsDecider()
    return out


def play(match_id: str, seed: int, names: dict[str, str], deciders: dict,
         warmup: WarmupCounter, log=LOG, experiment: str = "tournament") -> Battle:
    battle = Battle(seed=seed)
    npcs = {s: (RuleNPC() if names[s] == "rule" else RandomNPC(f"{match_id}-{s}"))
            for s in SIDES if names[s] not in API_NAMES}
    order_rng = random.Random(f"{match_id}-order")
    while not battle.over:
        turn = battle.turn + 1
        actions, rows = {}, {}
        for s in SIDES:
            gs = battle.game_state(s)
            if battle.is_locked(s):
                actions[s] = None
                if names[s] in API_NAMES:
                    rows[s] = {"game_state": gs, "choice": "power_release", "forced": True}
                continue
            if names[s] not in API_NAMES:
                actions[s] = npcs[s].act(battle, s)
                continue
            d = deciders[names[s]]
            order = battle.available_actions(s)
            order_rng.shuffle(order)
            state_text = describe(gs)
            is_warmup = warmup.next(names[s])
            dec = d.choose(state_text, ACTION_QUESTION, {a: ACTION_DESCRIPTIONS[a] for a in order})
            actions[s] = dec.choice
            rows[s] = {"game_state": gs, "state_text": state_text, "option_order": order,
                       **decision_fields(dec), "warmup": is_warmup, "model": d.model, "raw": dec.raw}
        events = battle.step(actions)
        for s, extra in rows.items():
            append_jsonl(log, {
                "experiment": experiment, "match_id": match_id, "seed": seed, "turn": turn,
                "actor": names[s], "side": s, **extra, "events": events, "timestamp": now(),
            })
    return battle


def parse_seeds(text: str) -> list[int]:
    if "-" in text:
        a, b = text.split("-")
        return list(range(int(a), int(b) + 1))
    return [int(x) for x in text.split(",")]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--seeds", required=True, help="例: 0-4 または 0,3,7")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    deciders = make_deciders([args.a, args.b], args.dry_run)
    log, csv_path = LOG, CSV
    if args.dry_run:
        log = LOG.with_name("tournament_dry.jsonl")
        csv_path = CSV.with_name("tournament_dry.csv")
    warmup = WarmupCounter()
    done = {r["match_id"] for r in (csv.DictReader(csv_path.open()) if csv_path.exists() else [])}
    new_csv = not csv_path.exists()
    with csv_path.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if new_csv:
            w.writeheader()
        for seed in parse_seeds(args.seeds):
            for swap in (False, True):
                left, right = (args.b, args.a) if swap else (args.a, args.b)
                match_id = f"{args.a}_vs_{args.b}_s{seed:02d}" + ("_swap" if swap else "")
                if match_id in done:
                    continue
                b = play(match_id, seed, {"left": left, "right": right}, deciders, warmup, log)
                winner = {"left": left, "right": right}.get(b.winner, "draw")
                w.writerow({"match_id": match_id, "left": left, "right": right, "seed": seed,
                            "winner": winner, "end_reason": b.end_reason, "turns": b.turn})
                f.flush()
                print(f"{match_id}: winner={winner} reason={b.end_reason} turns={b.turn}", flush=True)


if __name__ == "__main__":
    main()
