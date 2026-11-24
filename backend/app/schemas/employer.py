from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


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


class SavedEmployer(BaseModel):
    id: UUID
    name: str
    address: str | None
    phone: str | None
    website: str | None
    map_url: str
    last_checked: datetime | None


class SavedEmployers(BaseModel):
    items: list[SavedEmployer]
