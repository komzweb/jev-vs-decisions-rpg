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

from config import prompts as C
from game.describe import describe
from game.engine import ACTIONS, Battle
from game.simulate import ME, gap, generate_position, ranked, win_rates

ROOT = Path(__file__).resolve().parent.parent

# win_rates のキー → シミュレーション方針
MAIN_POLICIES = {"random": "random", "eps_rule": f"eps_rule:{C.POS_EPSILON}"}
ROBUST_POLICIES = {f"eps_rule_{e}": f"eps_rule:{e}" for e in C.POS_ROBUSTNESS_EPSILONS}


def generate_candidates() -> list[dict]:
    rng = random.Random(C.POS_GEN_SEED)
    seen, out = set(), []
    while len(out) < C.POS_N_CANDIDATES:
        gs = generate_position(rng)
        key = json.dumps(gs, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "id": f"p{len(out) + 1:04d}",
            "game_state": gs,
            "state_text": describe(gs),
            "available": Battle.from_state(gs, seed=0, side=ME).available_actions(ME),
        })
    return out


def evaluate(pos: dict) -> dict:
    pos = dict(pos)
    run = lambda pol: win_rates(pos["game_state"], pos["available"], pol, pos["id"], C.POS_TRIALS)
    pos["win_rates"] = {k: run(pol) for k, pol in MAIN_POLICIES.items()}
    pos["win_rates_robustness"] = {k: run(pol) for k, pol in ROBUST_POLICIES.items()}
    pos["label"], pos["answer"] = classify(pos["win_rates"])
    return pos


def classify(wr: dict[str, dict[str, float]]) -> tuple[str, str | None]:
    """2方針の勝率から (label, answer) を決める。"""
    tops = [ranked(r)[0] for r in wr.values()]
    gaps = [gap(r) for r in wr.values()]
    if len({a for a, _ in tops}) == 1 and all(g >= C.POS_CLEAR_GAP for g in gaps):
        return "clear", tops[0][0]
    lo, hi = C.POS_TIE_TOP_RANGE
    if all(g < C.POS_TIE_GAP for g in gaps) and all(lo <= v <= hi for _, v in tops):
        return "tie", None
    return "rejected", None


def select(cands: list[dict]) -> list[dict]:
    """正解あり・拮抗からランダムに抽出。正解あり側は同じ正解行動を上限までに抑える。"""
    rng = random.Random(C.POS_SELECT_SEED)
    clear = [c for c in cands if c["label"] == "clear"]
    tie = [c for c in cands if c["label"] == "tie"]
    rng.shuffle(clear)
    picked, per_answer = [], Counter()
    for c in clear:
        if len(picked) >= C.POS_N_CLEAR:
            break
        if per_answer[c["answer"]] < C.POS_MAX_SAME_ANSWER:
            picked.append(c)
            per_answer[c["answer"]] += 1
    picked += rng.sample(tie, min(C.POS_N_TIE, len(tie)))
    return sorted(picked, key=lambda c: c["id"])


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))


def report(cands: list[dict], selected: list[dict], elapsed: float) -> str:
    labels = Counter(c["label"] for c in cands)
    clear = [c for c in cands if c["label"] == "clear"]
    sel_clear = [c for c in selected if c["label"] == "clear"]
    sel_tie = [c for c in selected if c["label"] == "tie"]
    disagree = sum(len({ranked(r)[0][0] for r in c["win_rates"].values()}) > 1 for c in cands)

    L = [f"# 検証1 局面生成と正解計算", "",
         f"- 候補 {len(cands)} 局面、各行動 {C.POS_TRIALS} 回",
         f"- 方針: Random（逃走なし）と ε-Rule（ε={C.POS_EPSILON}）。頑健性確認用に ε="
         f"{', '.join(map(str, C.POS_ROBUSTNESS_EPSILONS))} も計算",
         f"- 正解あり: 2方針で1位が同じ、かつ両方針で1位-2位の差 ≥ {C.POS_CLEAR_GAP * 100:.0f}ポイント",
         f"- 拮抗: 両方針で1位-2位の差 < {C.POS_TIE_GAP * 100:.0f}ポイント、かつ両方針で1位の勝率が "
         f"{C.POS_TIE_TOP_RANGE[0]}〜{C.POS_TIE_TOP_RANGE[1]}",
         f"- 計算時間: {elapsed:.0f} 秒（8並列、4方針の合計）", "",
         "## 分類（ε=0.3）", "",
         f"- 正解あり {labels['clear']} / 拮抗 {labels['tie']} / 不採用 {labels['rejected']}",
         f"- 採用: 正解あり {len(sel_clear)} / 拮抗 {len(sel_tie)}",
         f"- 2方針で1位の行動が食い違った局面: {disagree} / {len(cands)}（{100 * disagree / len(cands):.0f}%）",
         "", "## 正解行動の内訳", "",
         f"| 行動 | 抽出前（正解あり全体） | 抽出後（{len(sel_clear)}局面） |", "| --- | --- | --- |"]
    ca, cs = Counter(c["answer"] for c in clear), Counter(c["answer"] for c in sel_clear)
    for a in ACTIONS:
        L.append(f"| {a} | {ca[a]} | {cs[a]} |")

    bins = [0, 0.05, 0.10, 0.15, 0.20, 0.30, 0.50, 1.01]
    names = ["0〜5", "5〜10", "10〜15", "15〜20", "20〜30", "30〜50", "50〜100"]
    counts = [0] * len(names)
    for c in cands:
        g = min(gap(r) for r in c["win_rates"].values())
        counts[next(i for i in range(len(names)) if bins[i] <= g < bins[i + 1])] += 1
    L += ["", "## 1位と2位の勝率差の分布（ε=0.3、2方針の小さい方、ポイント）", "",
          "| 差 | 局面数 |", "| --- | --- |"]
    L += [f"| {n} | {k} |" for n, k in zip(names, counts)]

    L += ["", "## 頑健性の確認（採用には使わない）", "",
          "| ε | 正解ありの件数 | 採用した正解あり局面で、ε-Rule方針の1位が同じ割合 | 同（Random方針と合わせて正解ありの判定も同じ） |",
          "| --- | --- | --- | --- |"]
    for key in ROBUST_POLICIES:
        n_clear = 0
        for c in cands:
            label, _ = classify({"random": c["win_rates"]["random"], key: c["win_rates_robustness"][key]})
            n_clear += label == "clear"
        same_top = sum(ranked(c["win_rates_robustness"][key])[0][0] == c["answer"] for c in sel_clear)
        same_label = sum(
            classify({"random": c["win_rates"]["random"], key: c["win_rates_robustness"][key]})
            == ("clear", c["answer"]) for c in sel_clear)
        e = key.rsplit("_", 1)[1]
        L.append(f"| {e} | {n_clear} | {same_top}/{len(sel_clear)}（{100 * same_top / len(sel_clear):.0f}%） "
                 f"| {same_label}/{len(sel_clear)}（{100 * same_label / len(sel_clear):.0f}%） |")
    L.append(f"| {C.POS_EPSILON}（本採用） | {labels['clear']} | — | — |")

    L += ["", "## 局面例", ""]
    for group, label in ((sel_clear, "clear"), (sel_tie, "tie")):
        for c in group[:2]:
            L += [f"### {c['id']}（{label}{'、正解 ' + c['answer'] if c['answer'] else ''}）", "",
                  "```", c["state_text"], "```", "",
                  "| 行動 | Random方針 | ε-Rule方針 |", "| --- | --- | --- |"]
            for a in c["available"]:
                L.append(f"| {a} | {c['win_rates']['random'][a]:.3f} | {c['win_rates']['eps_rule'][a]:.3f} |")
            L.append("")
    return "\n".join(L)


def main() -> None:
    cands = generate_candidates()
    t0 = time.time()
    with Pool(8) as pool:
        cands = pool.map(evaluate, cands, chunksize=8)
    elapsed = time.time() - t0

    selected = select(cands)
    write_jsonl(ROOT / "data" / "positions_candidates.jsonl", cands)
    write_jsonl(ROOT / "data" / "positions.jsonl",
                [{k: v for k, v in c.items() if k != "win_rates_robustness"} for c in selected])
    text = report(cands, selected, elapsed)
    (ROOT / "results" / "positions_report.md").write_text(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
