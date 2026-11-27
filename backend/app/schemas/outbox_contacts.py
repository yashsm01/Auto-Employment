from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.services.advert_contact import AdvertContact


class ContactRow(BaseModel):
    application_id: UUID
    title: str
    company: str
    kind: Literal["advert", "speculative"]
    status: str
    hiring_emails: list[str] = Field(default_factory=list)
    emails: list[str] = Field(default_factory=list)
    advert_contact: AdvertContact | None = None
    phone: str | None = None
    phone_source: str | None = None
    address_used: str | None = None
    missing_reason: str | None = None
    checked_at: datetime | None = None


class OutboxContacts(BaseModel):
    rows: list[ContactRow]
