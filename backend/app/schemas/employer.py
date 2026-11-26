from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.contacts import EmployerContacts


class NearbySearch(BaseModel):
    business: str = Field(min_length=1, max_length=80)
    town: str = Field(min_length=1, max_length=80)


class NearbyEmployer(BaseModel):
    place_id: str
    name: str
    address: str | None
    phone: str | None
    website: str | None
    lat: float | None
    lng: float | None
    map_url: str
    saved: bool
    rating: float | None = None
    rating_count: int | None = None
    hours: list[str] = Field(default_factory=list)
    business_type: str | None = None


class NearbyResults(BaseModel):
    results: list[NearbyEmployer]
    searches_left: int


class SaveEmployer(BaseModel):
    place_id: str = Field(min_length=1, max_length=300)
    name: str = Field(min_length=1, max_length=200)
    address: str | None = Field(default=None, max_length=300)
    phone: str | None = Field(default=None, max_length=40)
    website: str | None = Field(default=None, max_length=500)
    lat: float | None = None
    lng: float | None = None
    rating: float | None = Field(default=None, ge=0, le=5, allow_inf_nan=False)
    rating_count: int | None = Field(default=None, ge=0)
    hours: list[Annotated[str, Field(max_length=120)]] = Field(default_factory=list, max_length=7)


class SavedEmployer(BaseModel):
    id: UUID
    name: str
    address: str | None
    phone: str | None
    website: str | None
    map_url: str
    last_checked: datetime | None
    contacts: EmployerContacts | None = None


class SavedEmployers(BaseModel):
    items: list[SavedEmployer]
