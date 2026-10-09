"""両APIを同じインターフェースで呼ぶための共通定義（SPEC.md「API呼び出し仕様」）。"""

from __future__ import annotations

import os
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Protocol

ROOT = Path(__file__).resolve().parent.parent

RETRY_STATUSES = {429, 529}
MAX_RETRIES = 5


@dataclass
class Decision:
    choice: str                     # 選ばれた行動ID
    probabilities: dict[str, float] # 行動ID -> 確率
    confidence: float | None
    latency_ms: float               # 送信から受信までの実測（成功した試行のみ）
    input_tokens: int | None        # レスポンスのusageから取得
    raw: dict                       # 生レスポンス（ログ用）
    retries: int = 0                # ログの "retries" 用
    refused: bool = False           # Decisionsの refusal をランダム行動で代替した場合 True


class Decider(Protocol):
    name: str
    def choose(self, state: str, instructions: str,
               options: dict[str, str]) -> Decision: ...


class RetryableError(Exception):
    def __init__(self, status: int):
        super().__init__(f"retryable HTTP {status}")
        self.status = status


def is_retryable(status: int) -> bool:
    return status in RETRY_STATUSES or 500 <= status < 600


def call_with_retry(fn: Callable[[], dict]) -> tuple[dict, float, int]:
    """fn を呼び、429/529/5xx なら指数バックオフで最大5回リトライする。

    返り値は (結果, 成功した試行のレイテンシーms, リトライ回数)。
    リトライ待ち時間・失敗した試行の時間はレイテンシーに含めない。
    """
    for attempt in range(MAX_RETRIES + 1):
        t0 = time.perf_counter()
        try:
            result = fn()
        except RetryableError:
            if attempt == MAX_RETRIES:
                raise
            time.sleep(min(2 ** attempt, 30) + random.random())
            continue
        return result, (time.perf_counter() - t0) * 1000, attempt
    raise AssertionError("unreachable")


def load_env() -> None:
    """.env があれば、未設定の環境変数だけ読み込む（値は表示しない）。"""
    for name in (".env", ".env.local"):
        path = ROOT / name
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def require_env(key: str) -> str:
    load_env()
    value = os.environ.get(key)
    if not value:
        raise RuntimeError(f"環境変数 {key} が設定されていません")
    return value
