"""Auto mode: what it may do on its own, and what it did today."""

from pydantic import BaseModel, Field


class AutoModeSettings(BaseModel):
    enabled: bool = False
    min_score: int = Field(80, ge=0, le=100)
    daily_limit: int = Field(5, ge=0, le=20)


class AutoModeView(AutoModeSettings):
    approved_today: int
    sending_enabled: bool
    calls_enabled: bool
