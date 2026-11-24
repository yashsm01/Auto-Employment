from typing import Protocol

from app.core.errors import ProviderError
from app.schemas.job import JobDraft


class JobSource(Protocol):
    """One place jobs come from. Raises ProviderError when it cannot be reached."""

    name: str

    def search(self, keywords: str) -> list[JobDraft]: ...


class UnavailableSource:
    """A connected source missing something it needs. Each run reports why."""

    def __init__(self, name: str, reason: str) -> None:
        self.name = name
        self._reason = reason

    def search(self, keywords: str) -> list[JobDraft]:
        raise ProviderError(self.name, self._reason)
