"""LLM grader for benchmark metrics — judges answers, never re-answers from context.

Use only for equivalence / adversarial checks on short strings (~200 tokens/call).
Do NOT send retrieved transcripts to OpenAI.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any

from openai import APIConnectionError, OpenAI, RateLimitError

from benchmarks.metrics.qa import adversarial_passes, grade_answer

INPUT_USD_PER_1M = 0.15
OUTPUT_USD_PER_1M = 0.60
DEFAULT_MODEL = "gpt-4o-mini"


@dataclass
class GradeResult:
    correct: bool
    grading_method: str
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class GraderUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    requests: int = 0

    def add(self, inp: int, out: int) -> None:
        self.input_tokens += inp
        self.output_tokens += out
        self.requests += 1

    @property
    def estimated_usd(self) -> float:
        return (self.input_tokens / 1_000_000 * INPUT_USD_PER_1M) + (
            self.output_tokens / 1_000_000 * OUTPUT_USD_PER_1M
        )


@dataclass
class AnswerGrader:
    """Grades predicted vs gold. Local match first; optional LLM for ambiguous cases."""

    model: str = DEFAULT_MODEL
    usage: GraderUsage = field(default_factory=GraderUsage)
    use_llm_fallback: bool = True

    def __post_init__(self) -> None:
        self._client: OpenAI | None = None
        if self.use_llm_fallback:
            api_key = os.getenv("OPENAI_API_KEY") or os.getenv("openai_api_key")
            if api_key:
                self._client = OpenAI(api_key=api_key)

    def grade(
        self,
        question: str,
        gold: str | int | float | None,
        predicted: str,
        *,
        adversarial: bool = False,
        adversarial_trap: str = "",
    ) -> GradeResult:
        gold_str = "" if gold is None else str(gold)

        if adversarial:
            correct = adversarial_passes("", adversarial_trap or gold_str, predicted)
            return GradeResult(correct=correct, grading_method="adversarial_local")

        correct, method = grade_answer(predicted, gold_str)
        if correct:
            return GradeResult(correct=True, grading_method=f"local_{method}")

        if not self.use_llm_fallback or not self._client or not predicted.strip():
            return GradeResult(correct=False, grading_method=method)

        return self._llm_equivalence(question, gold_str, predicted)

    def _llm_equivalence(
        self, question: str, gold: str, predicted: str
    ) -> GradeResult:
        assert self._client is not None
        response = None
        for attempt in range(6):
            try:
                response = self._client.chat.completions.create(
                    model=self.model,
                    temperature=0,
                    max_tokens=8,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You grade whether two answers to the same question are "
                                "semantically equivalent. Reply with exactly YES or NO."
                            ),
                        },
                        {
                            "role": "user",
                            "content": (
                                f"Question: {question}\n"
                                f"Reference answer: {gold}\n"
                                f"Predicted answer: {predicted}\n"
                                "Equivalent?"
                            ),
                        },
                    ],
                )
                break
            except RateLimitError:
                time.sleep(min(2.0 * (attempt + 1), 20.0))
            except APIConnectionError:
                return GradeResult(correct=False, grading_method="llm_unavailable")
        if response is None:
            return GradeResult(correct=False, grading_method="llm_rate_limited")

        inp = response.usage.prompt_tokens if response.usage else 0
        out = response.usage.completion_tokens if response.usage else 0
        self.usage.add(inp, out)

        verdict = (response.choices[0].message.content or "").strip().upper()
        correct = verdict.startswith("YES")
        return GradeResult(
            correct=correct,
            grading_method="llm_equivalence",
            input_tokens=inp,
            output_tokens=out,
        )


def estimate_grader_cost(
    num_calls: int,
    avg_input_tokens: int = 120,
    avg_output_tokens: int = 4,
    model: str = DEFAULT_MODEL,
) -> dict[str, Any]:
    """Estimate cost when LLM grades only ambiguous answers (not full-context answerer)."""
    total_in = num_calls * avg_input_tokens
    total_out = num_calls * avg_output_tokens
    usd = (total_in / 1_000_000 * INPUT_USD_PER_1M) + (
        total_out / 1_000_000 * OUTPUT_USD_PER_1M
    )
    return {
        "model": model,
        "estimated_calls": num_calls,
        "estimated_input_tokens": total_in,
        "estimated_output_tokens": total_out,
        "estimated_usd": round(usd, 4),
        "note": "Grader-only mode: short equivalence prompts, not full transcript answerer.",
    }
