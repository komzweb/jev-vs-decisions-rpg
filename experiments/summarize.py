"""速度・コストと対戦結果の集計（検証3と全体集計）→ results/summary.md

uv run python -m experiments.summarize
"""

from __future__ import annotations

import csv
from collections import Counter

from experiments.common import ROOT, read_jsonl

LOGS = [ROOT / "logs" / "positions_api.jsonl", ROOT / "logs" / "tournament.jsonl"]
APIS = ("jev", "decisions")
PRICE_PER_M = {"jev": 0.042, "decisions": 0.10}  # USD / 100万入力トークン（SPEC.md「検証3」）


def percentile(xs: list[float], p: float) -> float:
    xs = sorted(xs)
    k = (len(xs) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def speed_and_cost() -> list[str]:
    calls = [r for path in LOGS for r in read_jsonl(path)
             if r.get("actor") in APIS and not r.get("forced") and not r.get("error")]
    L = ["## 速度（ウォームアップ・リトライ発生分を除く）", "",
         "| API | n | p50 (ms) | p95 (ms) | 最大 (ms) |", "| --- | --- | --- | --- | --- |"]
    for a in APIS:
        lat = [r["latency_ms"] for r in calls
               if r["actor"] == a and not r.get("warmup") and not r.get("retries")]
        if lat:
            L.append(f"| {a} | {len(lat)} | {percentile(lat, .5):.0f} | {percentile(lat, .95):.0f} | {max(lat):.0f} |")
    L += ["", "## コスト（全呼び出し）", "",
          "| API | 呼び出し | 平均入力トークン | 合計入力トークン | 費用 (USD) | 1,000回あたり (USD) |",
          "| --- | --- | --- | --- | --- | --- |"]
    for a in APIS:
        toks = [r["input_tokens"] for r in calls if r["actor"] == a and r.get("input_tokens") is not None]
        if toks:
            total = sum(toks)
            cost = total * PRICE_PER_M[a] / 1e6
            L.append(f"| {a} | {len(toks)} | {total / len(toks):.1f} | {total} | {cost:.6f} | "
                     f"{cost / len(toks) * 1000:.6f} |")
    return L


def tournament() -> list[str]:
    path = ROOT / "results" / "tournament.csv"
    if not path.exists():
        return []
    matches = list(csv.DictReader(path.open()))
    rows = [r for r in read_jsonl(ROOT / "logs" / "tournament.jsonl")]
    L = ["## 対戦結果", "", "| match_id | left | right | winner | end_reason | turns |",
         "| --- | --- | --- | --- | --- | --- |"]
    L += [f"| {m['match_id']} | {m['left']} | {m['right']} | {m['winner']} | {m['end_reason']} | {m['turns']} |"
          for m in matches]
    wins = Counter(m["winner"] for m in matches)
    L += ["", f"- 勝ち数: {dict(wins)}",
          f"- 終了理由: {dict(Counter(m['end_reason'] for m in matches))}",
          f"- 平均ターン数: {sum(int(m['turns']) for m in matches) / len(matches):.1f}", "",
          "### 行動の内訳（自分で選んだ行動のみ）", "",
          "| 行動 | " + " | ".join(APIS) + " |", "| --- | --- | --- |"]
    chosen = {a: Counter(r["choice"] for r in rows if r["actor"] == a and not r.get("forced")) for a in APIS}
    for act in ["attack", "power_attack", "defend", "potion", "flee"]:
        L.append(f"| {act} | " + " | ".join(
            f"{100 * chosen[a][act] / max(1, sum(chosen[a].values())):.1f}%" for a in APIS) + " |")
    L += ["", "### 相手が溜め中のときに防御した率", ""]
    for a in APIS:
        rs = [r for r in rows if r["actor"] == a and not r.get("forced") and r["game_state"]["enemy_charging"]]
        d = sum(r["choice"] == "defend" for r in rs)
        L.append(f"- {a}: {d}/{len(rs)}" + (f"（{100 * d / len(rs):.0f}%）" if rs else ""))
    refusals = sum(r.get("refused", False) for r in rows)
    L += ["", f"- 対戦中の refusal（ランダム行動で代替）: {refusals}"]
    return L


def main() -> None:
    L = ["# 集計（速度・コスト・対戦）", ""] + speed_and_cost() + [""] + tournament()
    text = "\n".join(L)
    (ROOT / "results" / "summary.md").write_text(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
