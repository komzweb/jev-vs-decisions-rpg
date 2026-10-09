"""おまけ実験の集計 → results/bonus.md（速度・費用は本編と分けて記録する）。"""

from __future__ import annotations

from experiments import positions_ja, shopkeeper
from experiments.common import ROOT, read_jsonl
from experiments.summarize import PRICE_PER_M, percentile

APIS = ("jev", "decisions")


def speed_and_cost() -> list[str]:
    L = ["## おまけ実験の速度・費用（本編とは別集計。ウォームアップ・リトライ発生分は速度から除く）", "",
         "| 実験 | API | 呼び出し | p50 (ms) | p95 (ms) | 平均入力トークン | 費用 (USD) |",
         "| --- | --- | --- | --- | --- | --- | --- |"]
    total = 0.0
    for name, log in (("A 道具屋", shopkeeper.LOG), ("B 日本語", positions_ja.LOG)):
        rows = [r for r in read_jsonl(log) if not r.get("error")]
        for a in APIS:
            rs = [r for r in rows if r["actor"] == a]
            if not rs:
                continue
            lat = [r["latency_ms"] for r in rs if not r.get("warmup") and not r.get("retries")]
            toks = [r["input_tokens"] for r in rs if r.get("input_tokens") is not None]
            cost = sum(toks) * PRICE_PER_M[a] / 1e6
            total += cost
            L.append(f"| {name} | {a} | {len(rs)} | {percentile(lat, .5):.0f} | {percentile(lat, .95):.0f} | "
                     f"{sum(toks) / len(toks):.1f} | {cost:.4f} |")
    L += ["", f"- おまけ実験の合計費用: ${total:.4f}"]
    return L


def write() -> str:
    L = ["# おまけ実験", ""] + shopkeeper.summarize() + [""] + positions_ja.summarize() + [""] + speed_and_cost()
    text = "\n".join(L)
    (ROOT / "results" / "bonus.md").write_text(text + "\n")
    return text
