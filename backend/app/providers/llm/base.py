from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMProvider(Protocol):
    """A model that returns validated structured output. Raises ProviderError on failure."""

    input_tokens: int
    output_tokens: int

    def parse(self, *, system: str, user: str, schema: type[T], max_tokens: int = 4000) -> T: ...
