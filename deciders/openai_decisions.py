"""Decisions API（OpenAI）の Decider。openai SDK の client.decisions.create を使う。"""

from __future__ import annotations

import json
import random

import openai

from deciders.base import Decision, RetryableError, call_with_retry, is_retryable, require_env

MODEL = "gpt-6-luna"
QUESTION_NAME = "action"


class DecisionsDecider:
    name = "decisions"
    model = MODEL

    def __init__(self, timeout: float = 30.0, seed: int | None = None):
        # リトライは call_with_retry で行い、レイテンシーから除外するため SDK 側は無効化
        self.client = openai.OpenAI(
            api_key=require_env("OPENAI_API_KEY"), max_retries=0, timeout=timeout
        )
        self.rng = random.Random(seed)

    def request_body(self, state: str, instructions: str, options: dict[str, str]) -> dict:
        return {
            "model": MODEL,
            "input": state,
            "questions": [{
                "type": "choice",
                "name": QUESTION_NAME,
                "instructions": instructions,
                "choices": [{"value": k, "description": v} for k, v in options.items()],
            }],
        }

    def choose(self, state: str, instructions: str, options: dict[str, str]) -> Decision:
        body = self.request_body(state, instructions, options)

        def send() -> dict:
            try:
                resp = self.client.decisions.with_raw_response.create(**body)
            except openai.APIStatusError as e:
                if is_retryable(e.status_code):
                    raise RetryableError(e.status_code) from e
                raise
            return json.loads(resp.text)

        raw, latency_ms, retries = call_with_retry(send)
        answer = raw["answers"][0]
        usage = raw.get("usage") or {}
        if answer["type"] == "refusal":
            return Decision(
                choice=self.rng.choice(list(options)),
                probabilities={},
                confidence=None,
                latency_ms=latency_ms,
                input_tokens=usage.get("input_tokens"),
                raw=raw,
                retries=retries,
                refused=True,
            )
        return Decision(
            choice=answer["choice"],
            probabilities={p["value"]: float(p["probability"]) for p in answer["probabilities"]},
            confidence=answer.get("confidence"),
            latency_ms=latency_ms,
            input_tokens=usage.get("input_tokens"),
            raw=raw,
            retries=retries,
        )
