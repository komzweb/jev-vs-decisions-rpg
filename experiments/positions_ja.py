"""おまけB：日本語プロンプト版。正解あり100＋拮抗30局面を、検証1の順番の1通り目だけで両APIに投げる。

uv run python -m experiments.positions_ja run        # 130 × 2API = 260回（途中から再開可）
uv run python -m experiments.positions_ja summarize  # results/bonus.md を更新
"""

from __future__ import annotations

import sys

from config import prompts as P
from experiments.common import (ROOT, WarmupCounter, append_jsonl, decision_fields, now,
                                read_jsonl, write_sample)
from experiments.positions_api import LOG as EN_LOG, load_positions, option_orders
from experiments.stats import ece, mcnemar_exact, wilson
from game.describe import describe

LOG = ROOT / "logs" / "positions_ja.jsonl"
APIS = ("jev", "decisions")
ORDER_INDEX = 0
PRICE_PER_M = {"jev": 0.042, "decisions": 0.10}


def run() -> None:
    from deciders.jev import JevDecider
    from deciders.openai_decisions import DecisionsDecider

    deciders = {"jev": JevDecider(), "decisions": DecisionsDecider()}
    done = {(r["position_id"], r["actor"]) for r in read_jsonl(LOG) if not r.get("error")}
    warmup = WarmupCounter()
    for i, pos in enumerate(load_positions()):
        order = option_orders(pos)[ORDER_INDEX]
        options = {a: P.ACTION_DESCRIPTIONS_JA[a] for a in order}
        state = describe(pos["game_state"], lang="ja")
        for api in (APIS if i % 2 == 0 else APIS[::-1]):
            if (pos["id"], api) in done:
                continue
            d = deciders[api]
            row = {"experiment": "positions_ja", "position_id": pos["id"], "order_index": ORDER_INDEX,
                   "label": pos["label"], "answer": pos["answer"], "actor": api,
                   "game_state": pos["game_state"], "state_text": state, "option_order": order}
            is_warmup = warmup.next(api)
            try:
                dec = d.choose(state, P.ACTION_QUESTION_JA, options)
                row.update(decision_fields(dec))
                if dec.refused:
                    row["choice"] = "refusal"
                row["raw"] = dec.raw
            except Exception as e:  # noqa: BLE001
                status = getattr(e, "status_code", None)
                row.update({"choice": None, "error": f"{type(e).__name__} {status or ''}".strip()})
            row.update({"warmup": is_warmup, "model": d.model, "timestamp": now()})
            append_jsonl(LOG, row)
            print(f"{pos['id']} {api:9s} -> {row.get('choice')} conf={row.get('confidence')}", flush=True)
    write_sample(LOG, ROOT / "logs_sample" / "positions_ja_head100.jsonl")


def fmt(k: int, n: int) -> str:
    lo, hi = wilson(k, n)
    return f"{k}/{n} = {100 * k / n:.1f}%（{100 * lo:.1f}〜{100 * hi:.1f}）"


def summarize() -> list[str]:
    ja_rows = read_jsonl(LOG)
    if not ja_rows:
        return []
    en_rows = [r for r in read_jsonl(EN_LOG) if r["order_index"] == ORDER_INDEX]
    ja = {(r["position_id"], r["actor"]): r for r in ja_rows}
    en = {(r["position_id"], r["actor"]): r for r in en_rows}
    L = ["## B. 日本語プロンプト版", "",
         "正解あり100局面＋拮抗30局面を、検証1の順番の1通り目（order_index 0）だけで実行し、"
         "英語版の同じ局面・同じ順番の結果と比べた。", "",
         "### 正答率（正解あり100局面、95%信頼区間）", "",
         "| API | 英語 | 日本語 | 英語だけ正解 | 日本語だけ正解 | McNemar p |", "| --- | --- | --- | --- | --- | --- |"]
    for a in APIS:
        keys = [k for k in ja if k[1] == a and ja[k]["label"] == "clear" and k in en]
        e_ok = {k: en[k]["choice"] == en[k]["answer"] for k in keys}
        j_ok = {k: ja[k]["choice"] == ja[k]["answer"] for k in keys}
        b = sum(e_ok[k] and not j_ok[k] for k in keys)
        c = sum(j_ok[k] and not e_ok[k] for k in keys)
        L.append(f"| {a} | {fmt(sum(e_ok.values()), len(keys))} | {fmt(sum(j_ok.values()), len(keys))} | "
                 f"{b} | {c} | {mcnemar_exact(b, c):.2g} |")

    L += ["", "### 英語版と同じ行動を選んだ割合", "", "| API | 正解あり | 拮抗 | 全体 |", "| --- | --- | --- | --- |"]
    for a in APIS:
        cells = []
        for label in ("clear", "tie", None):
            keys = [k for k in ja if k[1] == a and k in en and (label is None or ja[k]["label"] == label)]
            cells.append(fmt(sum(ja[k]["choice"] == en[k]["choice"] for k in keys), len(keys)))
        L.append(f"| {a} | " + " | ".join(cells) + " |")

    L += ["", "### 入力トークン数と費用（同じ130局面・同じ順番）", "",
          "| API | 英語 平均 | 日本語 平均 | 倍率 | 英語 1,000回あたり (USD) | 日本語 1,000回あたり (USD) |",
          "| --- | --- | --- | --- | --- | --- |"]
    for a in APIS:
        keys = [k for k in ja if k[1] == a and k in en and ja[k].get("input_tokens")]
        et = sum(en[k]["input_tokens"] for k in keys) / len(keys)
        jt = sum(ja[k]["input_tokens"] for k in keys) / len(keys)
        L.append(f"| {a} | {et:.1f} | {jt:.1f} | ×{jt / et:.2f} | {et * PRICE_PER_M[a] / 1e3:.4f} | "
                 f"{jt * PRICE_PER_M[a] / 1e3:.4f} |")

    L += ["", "### 較正：選んだ行動の probability（正解あり100局面）", "",
          "| probability | " + " | ".join(f"{a} 日本語 件数 | 平均確率 | 正答率" for a in APIS) + " |",
          "| --- |" + " --- | --- | --- |" * len(APIS)]
    pairs = {}
    for a in APIS:
        rs = [ja[k] for k in ja if k[1] == a and ja[k]["label"] == "clear" and ja[k]["probabilities"]]
        pairs[a] = [(r["probabilities"].get(r["choice"], 0.0), r["choice"] == r["answer"]) for r in rs]
    for i in range(5):
        lo, hi = i / 5, (i + 1) / 5
        cells = []
        for a in APIS:
            b = [(p, ok) for p, ok in pairs[a] if lo <= p < hi or (i == 4 and p == 1.0)]
            cells += ([str(len(b)), f"{sum(p for p, _ in b) / len(b):.2f}", f"{100 * sum(ok for _, ok in b) / len(b):.0f}%"]
                      if b else ["0", "—", "—"])
        L.append(f"| {lo:.1f}〜{hi:.1f} | " + " | ".join(cells) + " |")
    en_pairs = {}
    for a in APIS:
        rs = [en[k] for k in en if k[1] == a and en[k]["label"] == "clear"]
        en_pairs[a] = [(r["probabilities"].get(r["choice"], 0.0), r["choice"] == r["answer"]) for r in rs]
    L += ["", "| ECE（5区間） | " + " | ".join(APIS) + " |", "| --- | --- | --- |",
          "| 日本語 | " + " | ".join(f"{ece(pairs[a], 5):.3f}" for a in APIS) + " |",
          "| 英語（同じ100局面・順番0） | " + " | ".join(f"{ece(en_pairs[a], 5):.3f}" for a in APIS) + " |",
          "", "件数が100しかないため、ECEは目安。",
          "", "### 使った日本語訳", "", f"- 質問文：{P.ACTION_QUESTION_JA}", "- 行動の説明："]
    for k, v in P.ACTION_DESCRIPTIONS_JA.items():
        L.append(f"  - `{k}`：{v}")
    ex = ja_rows[0]
    L += ["- 状態文の例（" + ex["position_id"] + "）：", "", "```", ex["state_text"], "```"]
    return L


if __name__ == "__main__":
    if (sys.argv[1] if len(sys.argv) > 1 else "run") == "run":
        run()
    from experiments.bonus_report import write
    print(write())
