"""全体集計（検証1の比較基準・統計、検証2の対戦、検証3の速度・コスト）→ results/summary.md

uv run python -m experiments.summarize
"""

from __future__ import annotations

import csv
import json
import random
from collections import Counter, defaultdict

from experiments.common import ROOT, read_jsonl
from experiments.stats import binom_two_sided, ece, mcnemar_exact, wilson
from game.describe import hp_bucket
from game.engine import ACTIONS, Battle
from game.npcs import RuleNPC

POS_LOG = ROOT / "logs" / "positions_api.jsonl"
TOUR_LOG = ROOT / "logs" / "tournament.jsonl"
SMOKE = ROOT / "logs_sample" / "api_smoke.json"
APIS = ("jev", "decisions")
NPCS = ("jev", "decisions", "rule", "random")
PRICE_PER_M = {"jev": 0.042, "decisions": 0.10}  # USD / 100万入力トークン（SPEC.md「検証3」）
PAIRINGS = [("jev", "decisions"), ("jev", "rule"), ("decisions", "rule"),
            ("jev", "random"), ("decisions", "random")]


def fmt_rate(k: int, n: int) -> str:
    if n == 0:
        return "—"
    lo, hi = wilson(k, n)
    return f"{k}/{n} = {100 * k / n:.1f}%（{100 * lo:.1f}〜{100 * hi:.1f}）"


def fmt_p(p: float) -> str:
    return f"{p:.2g}" if p >= 0.0001 else f"{p:.1e}"


def percentile(xs: list[float], p: float) -> float:
    xs = sorted(xs)
    k = (len(xs) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


# --- 検証2：対戦 ----------------------------------------------------------------

def tournament(matches: list[dict], rows: list[dict]) -> list[str]:
    L = ["## 検証2 対戦結果", "",
         "勝率は全試合に対する割合（95% Wilson信頼区間）。p値は引き分けを除いた勝ち数の両側二項検定（勝ち数が五分か）。", "",
         "| 対戦 (A vs B) | 試合 | A勝ち | B勝ち | 引き分け | Aの勝率 | p値 | 平均ターン | 終了理由 |",
         "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for a, b in PAIRINGS:
        ms = [m for m in matches if {m["left"], m["right"]} == {a, b}]
        if not ms:
            continue
        wa = sum(m["winner"] == a for m in ms)
        wb = sum(m["winner"] == b for m in ms)
        dr = len(ms) - wa - wb
        reasons = Counter(m["end_reason"] for m in ms)
        L.append(f"| {a} vs {b} | {len(ms)} | {wa} | {wb} | {dr} | {fmt_rate(wa, len(ms))} | "
                 f"{fmt_p(binom_two_sided(wa, wa + wb))} | "
                 f"{sum(int(m['turns']) for m in ms) / len(ms):.1f} | "
                 f"{', '.join(f'{k} {v}' for k, v in reasons.most_common())} |")

    L += ["", "### 行動の内訳（自分で選んだ行動のみ。全対戦の合計）", "",
          "| 行動 | " + " | ".join(NPCS) + " |", "| --- |" + " --- |" * len(NPCS)]
    chosen = {n: Counter(r["choice"] for r in rows if r["actor"] == n and not r.get("forced"))
              for n in NPCS}
    for act in ACTIONS:
        L.append(f"| {act} | " + " | ".join(
            f"{100 * chosen[n][act] / max(1, sum(chosen[n].values())):.1f}%" for n in NPCS) + " |")
    L.append("| （選択回数） | " + " | ".join(str(sum(chosen[n].values())) for n in NPCS) + " |")

    L += ["", "### 対戦相手別の行動内訳（APIのみ）", "",
          "| NPC | 相手 | " + " | ".join(ACTIONS) + " |", "| --- | --- |" + " --- |" * len(ACTIONS)]
    by_match = {m["match_id"]: m for m in matches}
    for n in APIS:
        for opp in NPCS:
            if opp == n:
                continue
            rs = [r for r in rows if r["actor"] == n and not r.get("forced")
                  and opp in (by_match[r["match_id"]]["left"], by_match[r["match_id"]]["right"])]
            if rs:
                c = Counter(r["choice"] for r in rs)
                L.append(f"| {n} | {opp} | " + " | ".join(f"{100 * c[a] / len(rs):.1f}%" for a in ACTIONS) + " |")

    L += ["", "### 相手が溜め中のときに防御した率", ""]
    for n in NPCS:
        rs = [r for r in rows if r["actor"] == n and not r.get("forced") and r["game_state"]["enemy_charging"]]
        d = sum(r["choice"] == "defend" for r in rs)
        L.append(f"- {n}: {fmt_rate(d, len(rs))}")
    L += ["", f"- 対戦中の refusal（ランダム行動で代替）: {sum(r.get('refused', False) for r in rows)}"]
    return L


# --- 検証1：比較基準・統計 --------------------------------------------------------

def positions_section(pos_rows: list[dict]) -> list[str]:
    positions = read_jsonl(ROOT / "data" / "positions.jsonl")
    clear = [p for p in positions if p["label"] == "clear"]
    rule_choice = {p["id"]: RuleNPC().act(Battle.from_state(p["game_state"], seed=0), "left")
                   for p in positions}

    L = ["## 検証1 正答率と比較基準（正解あり100局面）", "",
         "括弧内は95% Wilson信頼区間。APIは100局面 × 5順序 = 500回、比較基準は順番に依存しないので100局面。", "",
         "| 方法 | 正答率 |", "| --- | --- |"]
    by_api = {a: [r for r in pos_rows if r["actor"] == a and r["label"] == "clear"] for a in APIS}
    for a in APIS:
        ok = sum(r["choice"] == r["answer"] for r in by_api[a])
        L.append(f"| {a} | {fmt_rate(ok, len(by_api[a]))} |")
    ok = sum(rule_choice[p["id"]] == p["answer"] for p in clear)
    L.append(f"| Rule NPC（if文） | {fmt_rate(ok, len(clear))} |")
    exp = sum(1 / len(p["available"]) for p in clear) / len(clear)
    L.append(f"| ランダムに選んだ場合の期待値 | {100 * exp:.1f}% |")
    ok = sum(p["answer"] == "attack" for p in clear)
    L.append(f"| 常に attack | {fmt_rate(ok, len(clear))} |")

    # 正解行動別
    L += ["", "### 正解行動別の正答率", "",
          "| 正解 | 局面 | jev | decisions | Rule | 常にattack |", "| --- | --- | --- | --- | --- | --- |"]
    for ans in ["attack", "power_attack", "defend", "potion"]:
        ps = [p for p in clear if p["answer"] == ans]
        cells = []
        for a in APIS:
            rs = [r for r in by_api[a] if r["answer"] == ans]
            cells.append(fmt_rate(sum(r["choice"] == ans for r in rs), len(rs)))
        rk = sum(rule_choice[p["id"]] == ans for p in ps)
        L.append(f"| {ans} | {len(ps)} | " + " | ".join(cells) +
                 f" | {rk}/{len(ps)} | {len(ps) if ans == 'attack' else 0}/{len(ps)} |")

    # McNemar
    key = lambda r: (r["position_id"], r["order_index"])
    j = {key(r): r["choice"] == r["answer"] for r in by_api["jev"]}
    d = {key(r): r["choice"] == r["answer"] for r in by_api["decisions"]}
    ks = j.keys() & d.keys()
    b = sum(j[k] and not d[k] for k in ks)
    c = sum(d[k] and not j[k] for k in ks)
    L += ["", "### Jev vs Decisions の正答率の差（McNemar検定、同じ局面・同じ順番の対応あり）", "",
          f"- 両方正解 {sum(j[k] and d[k] for k in ks)} / Jevだけ正解 {b} / Decisionsだけ正解 {c} / "
          f"両方不正解 {sum(not j[k] and not d[k] for k in ks)}（計 {len(ks)}）",
          f"- 正確McNemar検定 p = {fmt_p(mcnemar_exact(b, c))}",
          "- 参考：同じ局面の5回は互いに独立ではないため、局面単位の多数決でも比べる："]
    maj = {}
    for a in APIS:
        g = defaultdict(list)
        for r in by_api[a]:
            g[r["position_id"]].append(r["choice"] == r["answer"])
        maj[a] = {pid: sum(v) >= 3 for pid, v in g.items()}
    b2 = sum(maj["jev"][p] and not maj["decisions"][p] for p in maj["jev"])
    c2 = sum(maj["decisions"][p] and not maj["jev"][p] for p in maj["jev"])
    L.append(f"  - 5回中3回以上正解の局面: jev {sum(maj['jev'].values())} / decisions "
             f"{sum(maj['decisions'].values())}（Jevだけ {b2}、Decisionsだけ {c2}、McNemar p = {fmt_p(mcnemar_exact(b2, c2))}）")

    # 拮抗局面の Rule の選択（参考）
    ties = [p for p in positions if p["label"] == "tie"]
    tie_api = {a: defaultdict(Counter) for a in APIS}
    for r in pos_rows:
        if r["label"] == "tie":
            tie_api[r["actor"]][r["position_id"]][r["choice"]] += 1
    L += ["", "### 拮抗30局面での選択（参考）", "",
          "| 行動 | Rule NPC（局面数） | jev（150回） | decisions（150回） |", "| --- | --- | --- | --- |"]
    rc = Counter(rule_choice[p["id"]] for p in ties)
    tot = {a: sum((sum(tie_api[a].values(), Counter())).values()) for a in APIS}
    sums = {a: sum(tie_api[a].values(), Counter()) for a in APIS}
    for act in ACTIONS:
        L.append(f"| {act} | {rc[act]} | " + " | ".join(
            f"{100 * sums[a][act] / max(1, tot[a]):.1f}%" for a in APIS) + " |")
    agree = {a: sum(tie_api[a][p["id"]][rule_choice[p["id"]]] for p in ties) for a in APIS}
    L.append("")
    L.append("- Rule NPCと同じ行動を選んだ割合: " + ", ".join(
        f"{a} {fmt_rate(agree[a], tot[a])}" for a in APIS))

    L += [""] + calibration(by_api) + [""] + first_position(pos_rows)
    return L


def calibration(by_api: dict[str, list[dict]]) -> list[str]:
    L = ["## 自信の正直さ：選んだ行動の probability（正解あり500回）", "",
         "「その行動に付けた確率」で区切り、実際に正解だった割合と比べる。確率と正答率が近いほど較正が良い。", "",
         "| 選んだ行動の probability | " + " | ".join(f"{a} 件数 | {a} 平均確率 | {a} 正答率" for a in APIS) + " |",
         "| --- |" + " --- | --- | --- |" * len(APIS)]
    pairs = {a: [(r["probabilities"].get(r["choice"], 0.0), r["choice"] == r["answer"])
                 for r in by_api[a] if r["probabilities"]] for a in APIS}
    for i in range(5):
        lo, hi = i / 5, (i + 1) / 5
        cells = []
        for a in APIS:
            b = [(p, ok) for p, ok in pairs[a] if lo <= p < hi or (i == 4 and p == 1.0)]
            if b:
                cells += [str(len(b)), f"{sum(p for p, _ in b) / len(b):.2f}",
                          f"{100 * sum(ok for _, ok in b) / len(b):.1f}%"]
            else:
                cells += ["0", "—", "—"]
        L.append(f"| {lo:.1f}〜{hi:.1f} | " + " | ".join(cells) + " |")
    L += ["", "| | " + " | ".join(APIS) + " |", "| --- | --- | --- |",
          "| ECE（5区間） | " + " | ".join(f"{ece(pairs[a], 5):.3f}" for a in APIS) + " |",
          "| ECE（10区間） | " + " | ".join(f"{ece(pairs[a], 10):.3f}" for a in APIS) + " |",
          "| 平均確率 | " + " | ".join(f"{sum(p for p, _ in pairs[a]) / len(pairs[a]):.3f}" for a in APIS) + " |",
          "| 正答率 | " + " | ".join(f"{sum(ok for _, ok in pairs[a]) / len(pairs[a]):.3f}" for a in APIS) + " |",
          "| 選んだ行動が確率最大だった割合 | " + " | ".join(
              f"{100 * sum(r['probabilities'][r['choice']] >= max(r['probabilities'].values()) for r in by_api[a]) / len(by_api[a]):.1f}%"
              for a in APIS) + " |"]
    return L


def first_position(pos_rows: list[dict]) -> list[str]:
    """局面×行動の組ごとに「1番目に置かれたとき」と「それ以外」の選ばれた割合の差を平均する。"""
    L = ["## 先頭の選択肢に寄るか（局面をそろえた比較、全130局面）", "",
         "同じ局面の5通りの順番のうち、ある行動が1番目に置かれた回と、それ以外の位置の回の両方がある"
         "（局面, 行動）の組について、選ばれた割合の差（1番目 − それ以外）を平均した。"
         "95%区間は局面単位のブートストラップ（5,000回）。", "",
         "| API | 組の数 | 1番目のとき | それ以外のとき | 差の平均 | 95%区間 |", "| --- | --- | --- | --- | --- | --- |"]
    for a in APIS:
        g = defaultdict(list)
        for r in pos_rows:
            if r["actor"] == a:
                g[r["position_id"]].append(r)
        per_pos: dict[str, list[tuple[float, float]]] = defaultdict(list)
        for pid, rs in g.items():
            for act in rs[0]["option_order"]:
                first = [r["choice"] == act for r in rs if r["option_order"][0] == act]
                other = [r["choice"] == act for r in rs if r["option_order"][0] != act]
                if first and other:
                    per_pos[pid].append((sum(first) / len(first), sum(other) / len(other)))
        flat = [x for v in per_pos.values() for x in v]
        diffs = [f - o for f, o in flat]
        mean = sum(diffs) / len(diffs)
        rng = random.Random(0)
        pids = list(per_pos)
        boots = []
        for _ in range(5000):
            sample = [d for pid in (rng.choice(pids) for _ in pids) for d in (f - o for f, o in per_pos[pid])]
            boots.append(sum(sample) / len(sample))
        boots.sort()
        L.append(f"| {a} | {len(flat)} | {100 * sum(f for f, _ in flat) / len(flat):.1f}% | "
                 f"{100 * sum(o for _, o in flat) / len(flat):.1f}% | {100 * mean:+.1f}pt | "
                 f"{100 * boots[124]:+.1f}〜{100 * boots[4874]:+.1f}pt |")
    return L


# --- 検証3：速度・コスト -------------------------------------------------------------

def speed_and_cost(pos_rows: list[dict], tour_rows: list[dict]) -> list[str]:
    calls = [r for r in pos_rows + tour_rows
             if r.get("actor") in APIS and not r.get("forced") and not r.get("npc") and not r.get("error")]
    L = ["## 検証3 速度（ウォームアップ・リトライ発生分を除く）", "",
         "| API | 区分 | n | p50 (ms) | p95 (ms) | 最大 (ms) |", "| --- | --- | --- | --- | --- | --- |"]
    groups = [("全呼び出し", lambda r: True),
              ("逐次（検証1・最初の10試合）", lambda r: r.get("concurrency", 1) == 1),
              ("並列8試合（残りの対戦）", lambda r: r.get("concurrency", 1) > 1)]
    for a in APIS:
        for gname, f in groups:
            lat = [r["latency_ms"] for r in calls if r["actor"] == a and f(r)
                   and not r.get("warmup") and not r.get("retries")]
            if lat:
                L.append(f"| {a} | {gname} | {len(lat)} | {percentile(lat, .5):.0f} | "
                         f"{percentile(lat, .95):.0f} | {max(lat):.0f} |")

    smoke = json.loads(SMOKE.read_text())["calls"] if SMOKE.exists() else []
    L += ["", "## 検証3 コスト（全呼び出し。#1の疎通確認を含む）", "",
          "| API | 呼び出し | 平均入力トークン | 合計入力トークン | 費用 (USD) | 1,000回あたり (USD) | リトライ |",
          "| --- | --- | --- | --- | --- | --- | --- |"]
    total_usd = 0.0
    for a in APIS:
        toks = [r["input_tokens"] for r in calls if r["actor"] == a and r.get("input_tokens") is not None]
        toks += [c["input_tokens"] for c in smoke if c["api"] == a]
        total = sum(toks)
        cost = total * PRICE_PER_M[a] / 1e6
        total_usd += cost
        retries = sum(r.get("retries") or 0 for r in calls if r["actor"] == a)
        L.append(f"| {a} | {len(toks)} | {total / len(toks):.1f} | {total} | {cost:.4f} | "
                 f"{cost / len(toks) * 1000:.4f} | {retries} |")
    L += ["", f"- 検証全体の総費用: **${total_usd:.4f}**",
          f"- エラーで失敗した呼び出し: {sum(bool(r.get('error')) for r in pos_rows + tour_rows)}"]
    return L


# --- 記事に使えそうな試合 ------------------------------------------------------------

def highlight_candidates(matches: list[dict], rows: list[dict]) -> list[str]:
    by_match = defaultdict(list)
    for r in rows:
        by_match[r["match_id"]].append(r)
    L = ["## 記事に使えそうな試合の候補（自動抽出）", "",
         "| match_id | 勝者 | 理由 |", "| --- | --- | --- |"]
    cands = []
    for m in matches:
        w = m["winner"]
        if w not in APIS:
            continue
        rs = sorted(by_match[m["match_id"]], key=lambda r: r["turn"])
        wr = [r for r in rs if r["actor"] == w and r["side"] in ("left", "right")]
        wside = wr[0]["side"]
        mine = [r for r in rs if r["side"] == wside]
        min_hp = min(r["game_state"]["hp"] for r in mine)
        worst = min(mine, key=lambda r: r["game_state"]["hp"] - r["game_state"]["enemy_hp"])
        deficit = worst["game_state"]["enemy_hp"] - worst["game_state"]["hp"]
        low = [r for r in mine if r.get("confidence") is not None and r["confidence"] < 0.5]
        last3 = [r for r in mine if r["turn"] >= int(m["turns"]) - 2 and r.get("confidence") is not None]
        reasons = []
        score = 0
        if min_hp < 20:
            reasons.append(f"勝者のHPが最低{min_hp}まで減ってから勝利")
            score += 2
        if deficit >= 40:
            reasons.append(f"最大でHP差{deficit}をつけられてから逆転（ターン{worst['turn']}）")
            score += 2
        if last3 and min(r["confidence"] for r in last3) < 0.35:
            r0 = min(last3, key=lambda r: r["confidence"])
            reasons.append(f"終盤ターン{r0['turn']}で confidence {r0['confidence']:.2f} の迷いながら {r0['choice']}")
            score += 1
        if reasons:
            cands.append((score, deficit, m["match_id"], w, "、".join(reasons)))
    for score, _, mid, w, why in sorted(cands, reverse=True)[:10]:
        L.append(f"| {mid} | {w} | {why} |")
    return L


def main() -> None:
    pos_rows = read_jsonl(POS_LOG)
    tour_rows = read_jsonl(TOUR_LOG)
    matches = list(csv.DictReader((ROOT / "results" / "tournament.csv").open()))
    L = ["# 集計", ""]
    L += tournament(matches, tour_rows) + [""]
    L += positions_section(pos_rows) + [""]
    L += speed_and_cost(pos_rows, tour_rows) + [""]
    L += highlight_candidates(matches, tour_rows)
    text = "\n".join(L)
    (ROOT / "results" / "summary.md").write_text(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
