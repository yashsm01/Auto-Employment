"""Google Places Text Search (New). The field mask controls what Google bills for."""

import re
from dataclasses import dataclass

import httpx

from app.core.errors import ProviderError
from app.core.nz_places import is_nz_location

NAME = "places"
URL = "https://places.googleapis.com/v1/places:searchText"
FIELD_MASK = ",".join(
    f"places.{field}"
    for field in (
        "id",
        "displayName",
        "formattedAddress",
        "location",
        "websiteUri",
        "nationalPhoneNumber",
    )
)
_LEGAL_WORDS = {"ltd", "limited", "nz", "new", "zealand", "the", "group", "co", "company", "inc"}
_WORDS = re.compile(r"[a-z0-9]+")
_NZ_POSTCODE_END = re.compile(r"\b\d{4}$")


@dataclass(frozen=True)
class PlaceMatch:
    place_id: str
    address: str | None
    lat: float | None
    lng: float | None
    website: str | None
    phone: str | None
    name: str = ""


def _is_nz_address(address: str | None) -> bool:
    """With regionCode NZ, Google leaves the country off NZ addresses but names others."""
    if not address:
        return False
    if "new zealand" in address.casefold():
        return True
    last = address.rsplit(",", 1)[-1].strip()
    return bool(_NZ_POSTCODE_END.search(last)) or is_nz_location(last)


def _name_words(name: str) -> set[str]:
    return set(_WORDS.findall(name.casefold())) - _LEGAL_WORDS


def _same_business(wanted: str, found: str) -> bool:
    first, second = _name_words(wanted), _name_words(found)
    return bool(first and second) and (first <= second or second <= first)


def _to_match(place: dict) -> PlaceMatch:
    location = place.get("location") or {}
    return PlaceMatch(
        place_id=place.get("id") or "",
        address=place.get("formattedAddress"),
        lat=location.get("latitude"),
        lng=location.get("longitude"),
        website=place.get("websiteUri"),
        phone=place.get("nationalPhoneNumber"),
        name=(place.get("displayName") or {}).get("text") or "",
    )


class PlacesClient:
    def __init__(self, client: httpx.Client, api_key: str) -> None:
        self._client = client
        self._api_key = api_key

    def find(self, name: str, city: str) -> PlaceMatch | None:
        """Find the business. A result with a different name is treated as no match."""
        query = " ".join(part for part in (name, city, "New Zealand") if part)
        places = self._request(query, 1)
        if not places:
            return None
        return places[0] if _same_business(name, places[0].name) else None

    def search(self, query: str, limit: int = 20) -> list[PlaceMatch]:
        """Businesses matching a search like "software company in Timaru", in NZ only."""
        text = query if "new zealand" in query.casefold() else f"{query}, New Zealand"
        return [
            place
            for place in self._request(text, limit)
            if place.name and _is_nz_address(place.address)
        ]

    def _request(self, query: str, limit: int) -> list[PlaceMatch]:
        try:
            response = self._client.post(
                URL,
                json={"textQuery": query, "regionCode": "NZ", "pageSize": limit},
                headers={"X-Goog-Api-Key": self._api_key, "X-Goog-FieldMask": FIELD_MASK},
            )
        except httpx.HTTPError as error:
            raise ProviderError(NAME, f"request failed ({type(error).__name__})") from None
        if response.status_code != httpx.codes.OK:
            raise ProviderError(NAME, f"HTTP {response.status_code}")

        try:
            places = response.json().get("places") or []
        except ValueError:
            raise ProviderError(NAME, "unexpected response format") from None
        return [_to_match(place) for place in places]
