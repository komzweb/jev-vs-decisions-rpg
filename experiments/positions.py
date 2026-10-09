"""検証1：局面生成と、シミュレーションによる正解計算（APIは呼ばない）。

uv run python -m experiments.positions
→ data/positions_candidates.jsonl（候補全件）, data/positions.jsonl（採用局面）,
  results/positions_report.md（集計）
"""

from __future__ import annotations

import json
import random
import time
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

from game.describe import describe
from game.engine import Battle
from game.simulate import ME, POLICIES, gap, generate_position, ranked, win_rates

ROOT = Path(__file__).resolve().parent.parent
N_CANDIDATES = 500
TRIALS = 1000
GEN_SEED = 20261009
SELECT_SEED = 1
N_CLEAR, N_TIE = 100, 30
CLEAR_GAP = 0.20  # 正解あり：両方針で1位が同じ、かつ両方針で1位-2位の差がこれ以上
TIE_GAP = 0.05    # 拮抗：両方針で1位-2位の差がこれ未満


def generate_candidates() -> list[dict]:
    rng = random.Random(GEN_SEED)
    seen, out = set(), []
    while len(out) < N_CANDIDATES:
        gs = generate_position(rng)
        key = json.dumps(gs, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        pid = f"p{len(out) + 1:03d}"
        out.append({
            "id": pid,
            "game_state": gs,
            "state_text": describe(gs),
            "available": Battle.from_state(gs, seed=0, side=ME).available_actions(ME),
        })
    return out


def evaluate(pos: dict) -> dict:
    pos = dict(pos)
    pos["win_rates"] = {
        p: win_rates(pos["game_state"], pos["available"], p, pos["id"], TRIALS) for p in POLICIES
    }
    return classify(pos)


def classify(pos: dict) -> dict:
    wr = pos["win_rates"]
    tops = {p: ranked(wr[p])[0][0] for p in POLICIES}
    gaps = {p: gap(wr[p]) for p in POLICIES}
    if len(set(tops.values())) == 1 and all(g >= CLEAR_GAP for g in gaps.values()):
        pos["label"], pos["answer"] = "clear", tops["random"]
    elif all(g < TIE_GAP for g in gaps.values()):
        pos["label"], pos["answer"] = "tie", None
    else:
        pos["label"], pos["answer"] = "rejected", None
    return pos


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))


def report(cands: list[dict], selected: list[dict], elapsed: float) -> str:
    labels = Counter(c["label"] for c in cands)
    clear = [c for c in cands if c["label"] == "clear"]
    sel_clear = [c for c in selected if c["label"] == "clear"]
    disagree = sum(
        len({ranked(c["win_rates"][p])[0][0] for p in POLICIES}) > 1 for c in cands)

    bins = [0, 0.05, 0.10, 0.20, 0.30, 0.50, 1.01]
    bin_names = ["0〜5", "5〜10", "10〜20", "20〜30", "30〜50", "50〜100"]

    def hist(policy_or_min: str) -> list[int]:
        counts = [0] * len(bin_names)
        for c in cands:
            if policy_or_min == "min":
                g = min(gap(c["win_rates"][p]) for p in POLICIES)
            else:
                g = gap(c["win_rates"][policy_or_min])
            for i in range(len(bin_names)):
                if bins[i] <= g < bins[i + 1]:
                    counts[i] += 1
        return counts

    L = [f"# 検証1 局面生成と正解計算（候補 {len(cands)} 局面, 各行動 {TRIALS} 回 × 2方針）", ""]
    L += [f"- 計算時間: {elapsed:.0f} 秒（8並列）",
          f"- 分類: 正解あり {labels['clear']} / 正解なし（拮抗） {labels['tie']} / 不採用 {labels['rejected']}",
          f"- 採用: 正解あり {sum(c['label'] == 'clear' for c in selected)} / 拮抗 {sum(c['label'] == 'tie' for c in selected)}",
          f"- RandomとRuleで1位の行動が食い違った局面: {disagree} / {len(cands)}（{100 * disagree / len(cands):.0f}%）",
          ""]
    L += ["## 正解あり局面の正解行動の内訳", "", "| 行動 | 正解あり全体 | 採用100局面 |", "| --- | --- | --- |"]
    ca, cs = Counter(c["answer"] for c in clear), Counter(c["answer"] for c in sel_clear)
    for a in ["attack", "power_attack", "defend", "potion", "flee"]:
        L.append(f"| {a} | {ca[a]} | {cs[a]} |")
    L += ["", "## 1位と2位の勝率差の分布（候補全件、ポイント）", "",
          "| 差 | Random方針 | Rule方針 | 2方針の小さい方 |", "| --- | --- | --- | --- |"]
    hr, hu, hm = hist("random"), hist("rule"), hist("min")
    for i, name in enumerate(bin_names):
        L.append(f"| {name} | {hr[i]} | {hu[i]} | {hm[i]} |")
    L += ["", "## 局面例", ""]
    for label in ("clear", "tie"):
        for c in [c for c in selected if c["label"] == label][:2]:
            L += [f"### {c['id']}（{label}{', 正解 ' + c['answer'] if c['answer'] else ''}）", "",
                  "```", c["state_text"], "```", "",
                  "| 行動 | Random方針 | Rule方針 |", "| --- | --- | --- |"]
            for a in c["available"]:
                L.append(f"| {a} | {c['win_rates']['random'][a]:.3f} | {c['win_rates']['rule'][a]:.3f} |")
            L.append("")
    return "\n".join(L)


def main() -> None:
    cands = generate_candidates()
    t0 = time.time()
    with Pool(8) as pool:
        cands = pool.map(evaluate, cands, chunksize=4)
    elapsed = time.time() - t0

    rng = random.Random(SELECT_SEED)
    clear = [c for c in cands if c["label"] == "clear"]
    tie = [c for c in cands if c["label"] == "tie"]
    selected = rng.sample(clear, min(N_CLEAR, len(clear))) + rng.sample(tie, min(N_TIE, len(tie)))
    selected.sort(key=lambda c: c["id"])

    write_jsonl(ROOT / "data" / "positions_candidates.jsonl", cands)
    write_jsonl(ROOT / "data" / "positions.jsonl", selected)
    text = report(cands, selected, elapsed)
    (ROOT / "results" / "positions_report.md").write_text(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
