"""検証1・2で共通のログ処理（SPEC.md「ログ形式」）。"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from deciders.base import Decision

ROOT = Path(__file__).resolve().parent.parent
JST = timezone(timedelta(hours=9))
WARMUP_CALLS = 5  # 各APIの最初の5回は速度の集計から除く（ログには残す）


def now() -> str:
    return datetime.now(JST).isoformat(timespec="seconds")


def decision_fields(dec: Decision) -> dict:
    return {
        "choice": dec.choice,
        "probabilities": dec.probabilities,
        "confidence": dec.confidence,
        "latency_ms": round(dec.latency_ms, 1),
        "input_tokens": dec.input_tokens,
        "retries": dec.retries,
        "refused": dec.refused,
    }


class WarmupCounter:
    """API別の呼び出し回数を数え、最初の WARMUP_CALLS 回を warmup とする。"""

    def __init__(self):
        self.counts: dict[str, int] = {}

    def next(self, api: str) -> bool:
        n = self.counts.get(api, 0)
        self.counts[api] = n + 1
        return n < WARMUP_CALLS


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_sample(src: Path, dst: Path, n: int = 100) -> None:
    lines = src.read_text().splitlines()[:n]
    dst.parent.mkdir(exist_ok=True)
    dst.write_text("\n".join(lines) + "\n")
