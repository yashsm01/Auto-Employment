"""Text helpers shared by providers, chains and services. No business rules."""

import re
from functools import lru_cache

_HOURLY = re.compile(r"per\s+hour|an\s+hour|/\s*h(?:ou)?r\b|\bp/?h\b|hourly", re.IGNORECASE)
_RANGE_IN_K = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:-|–|—|to)\s*\$?\s*(\d+(?:\.\d+)?)\s*k\b", re.IGNORECASE
)
_AMOUNT = re.compile(r"(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*(k)?\b", re.IGNORECASE)
_MIN_ANNUAL = 20_000
_MAX_ANNUAL = 1_000_000


def parse_annual_salary(text: str | None) -> tuple[int | None, int | None]:
    """Read a yearly NZ$ range from free text. Hourly or unclear pay returns (None, None)."""
    if not text or _HOURLY.search(text):
        return None, None

    expanded = _RANGE_IN_K.sub(lambda m: f"{m[1]}k - {m[2]}k", text)
    amounts = []
    for number, thousands in _AMOUNT.findall(expanded):
        value = float(number.replace(",", "")) * (1000 if thousands else 1)
        if _MIN_ANNUAL <= value <= _MAX_ANNUAL:
            amounts.append(int(value))

    if not amounts:
        return None, None
    return min(amounts), max(amounts)


@lru_cache(maxsize=512)
def _term_pattern(term: str) -> re.Pattern[str]:
    return re.compile(rf"(?<![\w+#]){re.escape(term)}s?(?![\w+#])", re.IGNORECASE)


def contains_term(text: str, term: str) -> bool:
    """True when term appears as a whole word or phrase, allowing a plural."""
    return _term_pattern(term).search(text) is not None
