import anthropic
import httpx
import pytest
from pydantic import BaseModel

from app.core.config import Settings
from app.core.errors import ProviderError
from app.providers.llm.claude import ClaudeProvider
from app.providers.llm.factory import build_claude
from tests.fakes import FakeAnthropic, claude_response


class Answer(BaseModel):
    value: str


def _call(provider: ClaudeProvider) -> Answer:
    return provider.parse(system="rules", user="data", schema=Answer)


def test_returns_the_validated_output_and_counts_tokens():
    client = FakeAnthropic(claude_response(Answer(value="ok"), input_tokens=12, output_tokens=3))
    provider = ClaudeProvider(client, "claude-haiku-5-5")

    assert _call(provider) == Answer(value="ok")
    assert (provider.input_tokens, provider.output_tokens) == (12, 3)


def test_haiku_uses_the_standard_endpoint_without_unsupported_settings():
    client = FakeAnthropic(claude_response(Answer(value="ok")))

    _call(ClaudeProvider(client, "claude-haiku-5-5", effort="low"))

    sent = client.messages.calls[0]
    assert sent["model"] == "claude-haiku-5-5"
    assert sent["output_format"] is Answer
    assert sent["output_config"] == {"effort": "low"}
    assert sent["system"] == "rules"
    assert not {"temperature", "top_p", "top_k", "thinking", "tool_choice"} & set(sent)
    assert client.beta.messages.calls == []


def test_sonnet_turns_on_refusal_fallbacks():
    client = FakeAnthropic(claude_response(Answer(value="ok")))

    _call(ClaudeProvider(client, "claude-sonnet-5-5"))

    sent = client.beta.messages.calls[0]
    assert sent["betas"] == ["server-side-fallback-2026-07-01"]
    assert sent["fallbacks"] == "default"
    assert client.messages.calls == []


@pytest.mark.parametrize("stop_reason", ["refusal", "max_tokens"])
def test_an_incomplete_answer_is_an_error_even_with_parsed_output(stop_reason):
    client = FakeAnthropic(claude_response(Answer(value="partial"), stop_reason=stop_reason))

    with pytest.raises(ProviderError, match=stop_reason):
        _call(ClaudeProvider(client, "claude-haiku-5-5"))


def test_a_missing_parsed_output_is_an_error():
    client = FakeAnthropic(claude_response(None))

    with pytest.raises(ProviderError):
        _call(ClaudeProvider(client, "claude-haiku-5-5"))


def _status_error(cls, status: int):
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(status, request=request)
    return cls("failed with key sk-secret", response=response, body=None)


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (_status_error(anthropic.AuthenticationError, 401), "API key"),
        (_status_error(anthropic.RateLimitError, 429), "rate limit"),
        (_status_error(anthropic.InternalServerError, 500), "500"),
    ],
)
def test_api_errors_become_provider_errors_without_details(error, expected):
    client = FakeAnthropic(error=error)

    with pytest.raises(ProviderError, match=expected) as caught:
        _call(ClaudeProvider(client, "claude-haiku-5-5"))

    assert "sk-secret" not in str(caught.value)


def test_a_key_without_a_workspace_explains_the_fix():
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    error = anthropic.BadRequestError(
        "This API key is not scoped to a workspace, so this request must include the "
        "anthropic-workspace-id header with the ID of the workspace to use.",
        response=httpx.Response(400, request=request),
        body=None,
    )

    with pytest.raises(ProviderError, match="Create a key inside a workspace"):
        _call(ClaudeProvider(FakeAnthropic(error=error), "claude-haiku-5-5"))


def test_other_bad_requests_do_not_expose_the_api_message():
    error = _status_error(anthropic.BadRequestError, 400)

    with pytest.raises(ProviderError, match="HTTP 400") as caught:
        _call(ClaudeProvider(FakeAnthropic(error=error), "claude-haiku-5-5"))

    assert "sk-secret" not in str(caught.value)


def test_connection_errors_become_provider_errors():
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    client = FakeAnthropic(error=anthropic.APIConnectionError(request=request))

    with pytest.raises(ProviderError, match="connect"):
        _call(ClaudeProvider(client, "claude-haiku-5-5"))


@pytest.mark.parametrize("name", ["ANTHROPIC_API_KEY", "GOOGLE_API_KEY"])
def test_shared_shell_keys_are_never_used(monkeypatch, name):
    # A key in the shell may belong to something else, and using it would spend its money.
    monkeypatch.setenv(name, "key-from-shell")

    settings = Settings(_env_file=None)

    assert settings.anthropic_api_key.get_secret_value() == ""
    assert settings.google_api_key.get_secret_value() == ""
    assert build_claude(settings, "claude-haiku-5-5") is None


def test_ai_keys_are_read_from_the_project_env_file(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "key-from-shell")
    env_file = tmp_path / ".env"
    env_file.write_text("ANTHROPIC_API_KEY=key-from-file\n", encoding="utf-8")

    settings = Settings(_env_file=env_file)

    assert settings.anthropic_api_key.get_secret_value() == "key-from-file"


def test_other_settings_can_still_come_from_the_shell(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://example.invalid/db")

    assert Settings(_env_file=None).database_url == "postgresql://example.invalid/db"


def test_a_client_is_built_with_the_configured_key():
    settings = Settings(_env_file=None, anthropic_api_key="configured-key")

    provider = build_claude(settings, "claude-haiku-5-5", effort="low")

    assert isinstance(provider, ClaudeProvider)


def test_an_invalid_or_cut_off_answer_is_a_provider_error():
    try:
        Answer.model_validate_json('{"value": "cut off')
    except ValueError as error:
        cut_off = error

    with pytest.raises(ProviderError, match="cut off"):
        _call(ClaudeProvider(FakeAnthropic(error=cut_off), "claude-haiku-5-5"))
