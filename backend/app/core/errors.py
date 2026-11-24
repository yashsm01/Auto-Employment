"""Application errors. The API layer turns these into HTTP responses."""


class AppError(Exception):
    """Base class for errors this application raises on purpose."""


class NotFound(AppError):
    """A requested record does not exist."""


class BadRequest(AppError):
    """The request cannot be used, for example an unreadable resume file."""


class Conflict(AppError):
    """The request is valid but cannot be applied to the current state."""


class ProviderError(AppError):
    """An external API failed. Messages must never contain credentials."""

    def __init__(self, provider: str, message: str) -> None:
        super().__init__(f"{provider}: {message}")
        self.provider = provider
