"""Test doubles for the Anthropic client and for model-backed providers."""

from types import SimpleNamespace
from typing import Any

from app.core.errors import ProviderError


def claude_response(parsed: Any, stop_reason: str = "end_turn", input_tokens=10, output_tokens=5):
    return SimpleNamespace(
        parsed_output=parsed,
        stop_reason=stop_reason,
        stop_details=None,
        model="fake-model",
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
    )


class FakeParse:
    def __init__(self, response=None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.response


class FakeAnthropic:
    def __init__(self, response=None, error: Exception | None = None) -> None:
        self.messages = FakeParse(response, error)
        self.beta = SimpleNamespace(messages=FakeParse(response, error))


class ScriptedLLM:
    """Returns queued results in order. A queued exception is raised."""

    def __init__(self, *results: Any) -> None:
        self.results = list(results)
        self.calls: list[dict[str, Any]] = []
        self.input_tokens = 0
        self.output_tokens = 0

    def parse(self, *, system: str, user: str, schema: type, max_tokens: int = 4000):
        self.calls.append({"system": system, "user": user, "schema": schema})
        if not self.results:
            raise ProviderError("scripted", "no result queued")
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result
