from typing import Any, TypeVar

import anthropic
from pydantic import BaseModel

from app.core.errors import ProviderError

T = TypeVar("T", bound=BaseModel)

NAME = "claude"
_SERVER_FALLBACK_MODELS = {"claude-sonnet-5-5"}
_FALLBACK_BETA = "server-side-fallback-2026-07-01"
_NO_WORKSPACE_MESSAGE = (
    "this API key has no workspace. Create a key inside a workspace in the Claude Console, "
    "put it in backend/.env, and restart the backend"
)


class ClaudeProvider:
    def __init__(self, client: Any, model: str, effort: str = "low") -> None:
        self._client = client
        self._model = model
        self._effort = effort
        self.input_tokens = 0
        self.output_tokens = 0

    def _send(self, **request: Any) -> Any:
        if self._model in _SERVER_FALLBACK_MODELS:
            return self._client.beta.messages.parse(
                betas=[_FALLBACK_BETA], fallbacks="default", **request
            )
        return self._client.messages.parse(**request)

    def parse(self, *, system: str, user: str, schema: type[T], max_tokens: int = 4000) -> T:
        try:
            response = self._send(
                model=self._model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
                output_format=schema,
                output_config={"effort": self._effort},
            )
        except anthropic.AuthenticationError:
            raise ProviderError(NAME, "the API key was rejected") from None
        except anthropic.RateLimitError:
            raise ProviderError(NAME, "rate limit reached") from None
        except anthropic.BadRequestError as error:
            if "scoped to a workspace" in error.message:
                raise ProviderError(NAME, _NO_WORKSPACE_MESSAGE) from None
            raise ProviderError(NAME, "HTTP 400") from None
        except anthropic.APIStatusError as error:
            raise ProviderError(NAME, f"HTTP {error.status_code}") from None
        except anthropic.APIConnectionError:
            raise ProviderError(NAME, "could not connect") from None
        except ValueError:
            # The SDK validates output while parsing, so a cut-off answer raises here.
            raise ProviderError(NAME, "the answer was cut off or in the wrong format") from None

        self.input_tokens += response.usage.input_tokens
        self.output_tokens += response.usage.output_tokens
        if response.stop_reason in ("refusal", "max_tokens"):
            raise ProviderError(NAME, f"response stopped: {response.stop_reason}")
        if response.parsed_output is None:
            raise ProviderError(NAME, "response did not match the expected format")
        return response.parsed_output
