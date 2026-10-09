"""検証1のAPI実行：確定した130局面 × 選択肢の順番5通り × 2API。

uv run python -m experiments.positions_api run        # API実行（途中から再開可）
uv run python -m experiments.positions_api summarize  # results/positions_api.md
"""

from __future__ import annotations

import hashlib
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

from config.prompts import ACTION_DESCRIPTIONS, ACTION_QUESTION
from experiments.common import (ROOT, WarmupCounter, append_jsonl, decision_fields, now,
                                read_jsonl, write_sample)

POSITIONS = ROOT / "data" / "positions.jsonl"
POSITIONS_SHA256 = "b617226fd5ed61a7f21dc23cd9e57c7eb6e86a2b57c3d926da57322e6a5f8499"
LOG = ROOT / "logs" / "positions_api.jsonl"
N_ORDERS = 5


def load_positions() -> list[dict]:
    digest = hashlib.sha256(POSITIONS.read_bytes()).hexdigest()
    if digest != POSITIONS_SHA256:
        raise SystemExit(f"positions.jsonl の sha256 が確定版と違います: {digest}")
    return read_jsonl(POSITIONS)


def option_orders(pos: dict) -> list[list[str]]:
    """局面IDから決まるシードで、重複しない5通りの並び順を作る（両APIで共通）。"""
    rng = random.Random(f"{pos['id']}-orders")
    orders: list[list[str]] = []
    while len(orders) < N_ORDERS:
        o = pos["available"][:]
        rng.shuffle(o)
        if o not in orders:
            orders.append(o)
    return orders


def run() -> None:
    from deciders.jev import JevDecider
    from deciders.openai_decisions import DecisionsDecider

    positions = load_positions()
    deciders = {"jev": JevDecider(), "decisions": DecisionsDecider()}
    done = {(r["position_id"], r["order_index"], r["actor"])
            for r in read_jsonl(LOG) if not r.get("error")}
    warmup = WarmupCounter()
    for pos in positions:
        for oi, order in enumerate(option_orders(pos)):
            options = {a: ACTION_DESCRIPTIONS[a] for a in order}
            # 局面・順番ごとに先に呼ぶAPIを交互にする（時間帯の偏りを避ける）
            apis = ["jev", "decisions"] if oi % 2 == 0 else ["decisions", "jev"]
            for api in apis:
                if (pos["id"], oi, api) in done:
                    continue
                d = deciders[api]
                row = {
                    "experiment": "positions",
                    "position_id": pos["id"],
                    "order_index": oi,
                    "label": pos["label"],
                    "answer": pos["answer"],
                    "actor": api,
                    "game_state": pos["game_state"],
                    "state_text": pos["state_text"],
                    "option_order": order,
                }
                is_warmup = warmup.next(api)
                try:
                    dec = d.choose(pos["state_text"], ACTION_QUESTION, options)
                    fields = decision_fields(dec)
                    if dec.refused:  # 検証1ではランダム行動に置き換えない
                        fields["choice"] = "refusal"
                    row.update(fields)
                    row["raw"] = dec.raw
                except Exception as e:  # noqa: BLE001 - 失敗もログに残して続行
                    status = getattr(e, "status_code", None) or getattr(
                        getattr(e, "response", None), "status_code", None)
                    row.update({"choice": None, "error": f"{type(e).__name__} {status or ''}".strip()})
                row.update({"warmup": is_warmup, "model": d.model, "timestamp": now()})
                append_jsonl(LOG, row)
                print(f"{pos['id']} o{oi} {api:9s} -> {row.get('choice')} "
                      f"conf={row.get('confidence')} lat={row.get('latency_ms')}", flush=True)
    write_sample(LOG, ROOT / "logs_sample" / "positions_api_head100.jsonl")


# --- 集計 ---------------------------------------------------------------------

def pct(n: int, d: int) -> str:
    return f"{100 * n / d:.1f}%" if d else "—"


def summarize() -> str:
    rows = read_jsonl(LOG)
    apis = ["jev", "decisions"]
    by_api = {a: [r for r in rows if r["actor"] == a] for a in apis}
    L = ["# 検証1 API実行結果", "",
         f"- 呼び出し {len(rows)} 回（{', '.join(f'{a} {len(by_api[a])}' for a in apis)}）",
         "- 正答率は正解あり100局面 × 5順序。refusal・エラーは不正解として数える", ""]

    # 正答率
    L += ["## 正答率", "", "| | " + " | ".join(apis) + " |", "| --- | --- | --- |"]
    clear = {a: [r for r in by_api[a] if r["label"] == "clear"] for a in apis}
    L.append("| 全体 | " + " | ".join(
        f"{sum(r['choice'] == r['answer'] for r in clear[a])}/{len(clear[a])}"
        f"（{pct(sum(r['choice'] == r['answer'] for r in clear[a]), len(clear[a]))}）" for a in apis) + " |")
    for ans in ["attack", "power_attack", "defend", "potion"]:
        cells = []
        for a in apis:
            rs = [r for r in clear[a] if r["answer"] == ans]
            ok = sum(r["choice"] == ans for r in rs)
            cells.append(f"{ok}/{len(rs)}（{pct(ok, len(rs))}）")
        L.append(f"| 正解 {ans} | " + " | ".join(cells) + " |")

    # 正解あり局面で何を選んだか
    L += ["", "## 正解あり局面で選んだ行動の内訳", "",
          "| 行動 | " + " | ".join(apis) + " |", "| --- | --- | --- |"]
    ch = {a: Counter(r["choice"] for r in clear[a]) for a in apis}
    for act in ["attack", "power_attack", "defend", "potion", "flee", "refusal", None]:
        if any(ch[a][act] for a in apis):
            L.append(f"| {act} | " + " | ".join(pct(ch[a][act], len(clear[a])) for a in apis) + " |")

    # 自信の正直さ
    L += ["", "## 自信の正直さ（正解あり、confidence 0.2刻み）", "",
          "| confidence | " + " | ".join(f"{a} 件数 | {a} 正答率" for a in apis) + " |",
          "| --- |" + " --- | --- |" * len(apis)]
    edges = [0, 0.2, 0.4, 0.6, 0.8, 1.0001]
    for i in range(5):
        cells = []
        for a in apis:
            rs = [r for r in clear[a] if r.get("confidence") is not None
                  and edges[i] <= r["confidence"] < edges[i + 1]]
            ok = sum(r["choice"] == r["answer"] for r in rs)
            cells += [str(len(rs)), pct(ok, len(rs))]
        L.append(f"| {edges[i]:.1f}〜{min(edges[i + 1], 1):.1f} | " + " | ".join(cells) + " |")

    # 拮抗 vs 正解ありの平均confidence
    L += ["", "## 平均confidence", "", "| | " + " | ".join(apis) + " |", "| --- | --- | --- |"]
    for label, name in (("clear", "正解あり"), ("tie", "拮抗")):
        cells = []
        for a in apis:
            cs = [r["confidence"] for r in by_api[a] if r["label"] == label and r.get("confidence") is not None]
            cells.append(f"{sum(cs) / len(cs):.3f}（n={len(cs)}）" if cs else "—")
        L.append(f"| {name} | " + " | ".join(cells) + " |")

    # 順番への頑健性
    L += ["", "## 順番への頑健性（5順序で答えがすべて一致した局面の割合）", "",
          "| 局面 | " + " | ".join(apis) + " |", "| --- | --- | --- |"]
    for label, name in (("clear", "正解あり"), ("tie", "拮抗"), (None, "全体")):
        cells = []
        for a in apis:
            g = defaultdict(list)
            for r in by_api[a]:
                if label is None or r["label"] == label:
                    g[r["position_id"]].append(r["choice"])
            same = sum(len(set(v)) == 1 and len(v) == N_ORDERS for v in g.values())
            cells.append(f"{same}/{len(g)}（{pct(same, len(g))}）")
        L.append(f"| {name} | " + " | ".join(cells) + " |")

    # 両APIの一致率
    key = lambda r: (r["position_id"], r["order_index"])
    j = {key(r): r["choice"] for r in by_api["jev"]}
    d = {key(r): r["choice"] for r in by_api["decisions"]}
    common = j.keys() & d.keys()
    L += ["", "## 両APIの一致率（同じ局面・同じ順番）", ""]
    for label, name in (("clear", "正解あり"), ("tie", "拮抗"), (None, "全体")):
        ks = [k for k in common if label is None or next(
            r["label"] for r in by_api["jev"] if key(r) == k) == label]
        same = sum(j[k] == d[k] for k in ks)
        L.append(f"- {name}: {same}/{len(ks)}（{pct(same, len(ks))}）")

    # 位置バイアス
    L += ["", "## 選択肢の位置ごとの選ばれやすさ", "",
          "その位置に置かれた行動が選ばれた割合。偏りがなければ「一様なら」の値に近くなる。", "",
          "| 位置 | " + " | ".join(apis) + " | 一様なら |", "| --- | --- | --- | --- |"]
    for k in range(5):
        cells, base = [], None
        for a in apis:
            rs = [r for r in by_api[a] if len(r["option_order"]) > k and r["choice"] in r["option_order"]]
            hit = sum(r["option_order"].index(r["choice"]) == k for r in rs)
            cells.append(f"{pct(hit, len(rs))}（n={len(rs)}）")
            base = sum(1 / len(r["option_order"]) for r in rs) / len(rs) if rs else None
        L.append(f"| {k + 1}番目 | " + " | ".join(cells) + f" | {100 * base:.1f}% |" if base else "")
    L += ["", "5択の呼び出しだけに絞った場合：", "",
          "| 位置 | " + " | ".join(apis) + " |", "| --- | --- | --- |"]
    for k in range(5):
        cells = []
        for a in apis:
            rs = [r for r in by_api[a] if len(r["option_order"]) == 5 and r["choice"] in r["option_order"]]
            hit = sum(r["option_order"].index(r["choice"]) == k for r in rs)
            cells.append(f"{pct(hit, len(rs))}（n={len(rs)}）")
        L.append(f"| {k + 1}番目 | " + " | ".join(cells) + " |")

    # refusal・エラー・リトライ
    L += ["", "## refusal・エラー・リトライ", "", "| | " + " | ".join(apis) + " |", "| --- | --- | --- |",
          "| refusal | " + " | ".join(str(sum(r.get("refused", False) for r in by_api[a])) for a in apis) + " |",
          "| エラー | " + " | ".join(str(sum(bool(r.get("error")) for r in by_api[a])) for a in apis) + " |",
          "| リトライが発生した呼び出し | " + " | ".join(str(sum((r.get("retries") or 0) > 0 for r in by_api[a])) for a in apis) + " |",
          "| リトライ回数の合計 | " + " | ".join(str(sum(r.get("retries") or 0 for r in by_api[a])) for a in apis) + " |"]
    text = "\n".join(L)
    (ROOT / "results" / "positions_api.md").write_text(text + "\n")
    return text


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    if cmd == "run":
        run()
    print(summarize())
