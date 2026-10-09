"""対戦ログから観戦モード（データ埋め込みの単一HTML）を生成する。APIは呼ばない。

uv run python -m replay.build_replay → replay/index.html
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "logs" / "tournament.jsonl"
CSV = ROOT / "results" / "tournament.csv"
TEMPLATE = Path(__file__).with_name("template.html")
OUT = Path(__file__).with_name("index.html")

FEATURED = ["jev_vs_decisions_s30", "jev_vs_decisions_s00", "decisions_vs_rule_s07"]
INITIAL = "jev_vs_decisions_s30"


def include(match_id: str) -> bool:
    return match_id.startswith("jev_vs_decisions_") or match_id in FEATURED


def side_state(gs: dict, prefix: str = "") -> list:
    return [gs[prefix + "hp"], gs[prefix + "mp"], gs[prefix + "potions"], int(gs[prefix + "charging"])]


def action(row: dict) -> dict:
    """心の声ウィンドウに必要な項目だけ残す。"""
    a = {"c": row["choice"]}
    if row.get("forced"):
        a["x"] = 1
    elif row.get("npc"):
        a["n"] = 1
    else:
        a["p"] = {k: round(v, 2) for k, v in row["probabilities"].items()}
        a["f"] = row["confidence"]
    return a


def build() -> dict:
    matches = {m["match_id"]: m for m in csv.DictReader(CSV.open()) if include(m["match_id"])}
    turns: dict[str, dict[int, dict[str, dict]]] = defaultdict(lambda: defaultdict(dict))
    for line in LOG.open():
        r = json.loads(line)
        if r["match_id"] in matches:
            turns[r["match_id"]][r["turn"]][r["side"]] = r

    out = []
    for mid, m in matches.items():
        ts = []
        for t in sorted(turns[mid]):
            sides = turns[mid][t]
            left = sides["left"]
            ts.append({
                "t": t,
                "s": [side_state(left["game_state"]), side_state(left["game_state"], "enemy_")],
                "a": [action(sides["left"]), action(sides["right"])],
                "ev": [{k: v for k, v in e.items()} for e in left["events"]],
            })
        out.append({"id": mid, "left": m["left"], "right": m["right"], "winner": m["winner"],
                    "reason": m["end_reason"], "turns": ts})
    order = {mid: i for i, mid in enumerate(FEATURED)}
    out.sort(key=lambda x: (order.get(x["id"], len(order)), x["id"]))
    return {"featured": FEATURED, "initial": INITIAL, "matches": out}


def main() -> None:
    data = json.dumps(build(), ensure_ascii=False, separators=(",", ":"))
    html = TEMPLATE.read_text().replace("/*__REPLAY_DATA__*/null", data.replace("</", "<\\/"))
    OUT.write_text(html)
    print(f"{OUT.relative_to(ROOT)}: {OUT.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
