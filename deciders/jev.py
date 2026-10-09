"""Jev（TypeSafe System One）の Decider。HTTP APIを直接呼ぶ。"""

from __future__ import annotations

import httpx

from deciders.base import Decision, RetryableError, call_with_retry, is_retryable, require_env

ENDPOINT = "https://api.typesafe.ai/v1/systemone"
MODEL = "jev-1.13.0"  # エイリアス（jev-latest）は使わずバージョン固定
QUESTION_ID = "action"


class JevDecider:
    name = "jev"
    model = MODEL

    def __init__(self, timeout: float = 30.0):
        self.client = httpx.Client(
            timeout=timeout,
            headers={"Authorization": f"Bearer {require_env('TYPESAFE_API_KEY')}"},
        )

    def request_body(self, state: str, instructions: str, options: dict[str, str]) -> dict:
        return {
            "model": MODEL,
            "state": state,
            "questions": {
                QUESTION_ID: {
                    "type": "choice",
                    "instructions": instructions,
                    "criteria": dict(options),  # 並び順は呼び出し側の options の順
                }
            },
        }

    def choose(self, state: str, instructions: str, options: dict[str, str]) -> Decision:
        body = self.request_body(state, instructions, options)

        def send() -> dict:
            resp = self.client.post(ENDPOINT, json=body)
            if is_retryable(resp.status_code):
                raise RetryableError(resp.status_code)
            resp.raise_for_status()
            return resp.json()

        raw, latency_ms, retries = call_with_retry(send)
        answer = raw["answers"][QUESTION_ID]
        return Decision(
            choice=answer["choice"],
            probabilities={k: float(v) for k, v in answer["probabilities"].items()},
            confidence=answer.get("confidence"),
            latency_ms=latency_ms,
            input_tokens=(raw.get("usage") or {}).get("input_tokens"),
            raw=raw,
            retries=retries,
        )
