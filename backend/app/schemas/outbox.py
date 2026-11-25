"""The Outbox: applications waiting to send, sent and waiting for a reply, and replies."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class SendRequest(BaseModel):
    to: str = Field(max_length=254)


class OutcomeRequest(BaseModel):
    action: Literal["replied", "closed", "followed_up", "stop_follow_ups"]


class OutboxSettings(BaseModel):
    daily_send_limit: int = Field(ge=0, le=50)


class ToSendItem(BaseModel):
    application_id: UUID
    title: str
    company: str
    suggested_to: str | None = None
    job_url: str | None = None
    pdf_url: str | None = None
    cover_note: str = ""


class OutboxItem(BaseModel):
    id: UUID
    application_id: UUID
    title: str
    company: str
    kind: Literal["application", "follow_up", "after_call"]
    to: str
    subject: str
    scheduled_at: datetime
    attempts: int
    error: str | None = None


class WaitingItem(BaseModel):
    application_id: UUID
    title: str
    company: str
    apply_method: Literal["email", "manual"]
    to: str | None = None
    applied_at: datetime | None = None
    follow_ups: int
    next_follow_up: date | None = None
    follow_up_due: bool
    job_url: str | None = None
    call_status: str | None = None
    captured_email: str | None = None


class DoneItem(BaseModel):
    application_id: UUID
    title: str
    company: str
    status: str
    updated_at: datetime


class OutboxView(BaseModel):
    sending_enabled: bool
    reading_enabled: bool
    daily_limit: int
    sent_today: int
    to_send: list[ToSendItem]
    queued: list[OutboxItem]
    failed: list[OutboxItem]
    waiting: list[WaitingItem]
    replied: list[DoneItem]
