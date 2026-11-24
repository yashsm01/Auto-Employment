"""Decides whether a job location is in New Zealand.

Global careers boards list jobs worldwide, and many NZ place names also exist overseas.
Names that are mostly foreign when written alone, such as Cambridge or Richmond, are left
out of this list. They still count when the user chooses them.
"""

import re
import unicodedata
from collections.abc import Iterable

from app.core.normalize import contains_term

NZ_PLACES = frozenset(
    {
        "ashburton", "auckland", "bay of plenty", "blenheim",
        "canterbury", "christchurch", "dargaville", "dunedin", "feilding", "gisborne",
        "greymouth", "hamilton", "havelock north", "hawera", "hawke's bay", "hawkes bay",
        "hokitika", "invercargill", "kaitaia", "kapiti", "kapiti coast", "kerikeri", "levin",
        "lower hutt", "manawatu", "manawatu-whanganui", "manukau", "marlborough", "masterton",
        "matamata", "motueka", "mount maunganui", "napier", "nelson", "new plymouth",
        "north shore", "northland", "oamaru", "otago", "palmerston north", "papakura",
        "paraparaumu", "porirua", "pukekohe", "queenstown", "rangiora", "rolleston", "rotorua",
        "southland", "taranaki", "tasman", "taupo", "tauranga", "te awamutu", "timaru",
        "tokoroa", "upper hutt", "waikato", "waitakere", "wanaka", "wanganui", "wellington",
        "west coast", "westport", "whakatane", "whanganui", "whangarei",
    }
)
_WORK_STYLE_WORDS = {"remote", "hybrid", "onsite", "on-site", "cbd", "central"}
_ALTERNATIVES = re.compile(r"\s*(?:/|;|\||\bor\b)\s*")
_PARTS = re.compile(r"\s*,\s*|\s+[-–—]\s+")


def fold_place(value: str) -> str:
    """Compare place names without capitals, macrons or extra spaces."""
    decomposed = unicodedata.normalize("NFKD", value)
    plain = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(plain.replace("’", "'").casefold().split())


def is_nz_location(location: str, chosen_places: Iterable[str] = ()) -> bool:
    """True if the location names NZ, or every part of one listed place is an NZ place."""
    text = fold_place(location)
    if contains_term(text, "new zealand") or contains_term(text, "nz"):
        return True

    known = NZ_PLACES | {fold_place(place) for place in chosen_places}
    for alternative in _ALTERNATIVES.split(text):
        parts = [part for part in _PARTS.split(alternative) if part]
        places = [part for part in parts if part not in _WORK_STYLE_WORDS]
        if places and all(place in known for place in places):
            return True
    return False
