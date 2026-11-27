"""Auto mode: what it may do on its own, and what it did today."""

from collections.abc import Iterable

from pydantic import BaseModel, Field, field_validator

MAX_BUSINESS_TYPES = 20
MAX_BUSINESS_TYPE_LENGTH = 60


def clean_business_types(items: Iterable[str]) -> list[str]:
    """Trim each entry, drop empty ones, and keep the first of any casefold duplicates."""
    seen: set[str] = set()
    cleaned: list[str] = []
    for item in items:
        text = item.strip()
        key = text.casefold()
        if text and key not in seen:
            seen.add(key)
            cleaned.append(text)
    return cleaned


class AutoModeSettings(BaseModel):
    enabled: bool = False
    min_score: int = Field(80, ge=0, le=100)
    daily_limit: int = Field(5, ge=0, le=20)
    prospects_enabled: bool = False
    prospects_per_day: int = Field(5, ge=1, le=10)
    business_types: list[str] = Field(default_factory=list)

    @field_validator("business_types")
    @classmethod
    def _check_business_types(cls, items: list[str]) -> list[str]:
        cleaned = clean_business_types(items)
        if len(cleaned) > MAX_BUSINESS_TYPES:
            raise ValueError(f"At most {MAX_BUSINESS_TYPES} business types.")
        if any(len(item) > MAX_BUSINESS_TYPE_LENGTH for item in cleaned):
            raise ValueError(
                f"Each business type must be {MAX_BUSINESS_TYPE_LENGTH} characters or fewer."
            )
        return cleaned


class AutoModeView(AutoModeSettings):
    approved_today: int
    sending_enabled: bool
    calls_enabled: bool
    business_types_suggested: list[str] = Field(default_factory=list)
