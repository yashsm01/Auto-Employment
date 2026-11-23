from typing import Protocol

from app.schemas.job import JobDraft


class JobSource(Protocol):
    """One place jobs come from. Raises ProviderError when it cannot be reached."""

    name: str

    def search(self, keywords: str) -> list[JobDraft]: ...
