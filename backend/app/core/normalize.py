"""Text helpers shared by providers, chains and services. No business rules."""

import html
import re
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any

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


_HIDDEN_HTML = re.compile(r"<(script|style)\b.*?</\1\s*>", re.IGNORECASE | re.DOTALL)
_BLOCK_TAG = re.compile(r"</?(?:p|div|li|ul|ol|br|h[1-6]|tr|table|section)\b[^>]*>", re.IGNORECASE)
_ANY_TAG = re.compile(r"<[^>]+>")


def strip_html(value: str | None) -> str:
    """Turn HTML, including entity-escaped HTML, into plain text."""
    if not value:
        return ""
    text = _HIDDEN_HTML.sub(" ", html.unescape(value))
    text = _ANY_TAG.sub("", _BLOCK_TAG.sub("\n", text))
    lines = (" ".join(line.split()) for line in html.unescape(text).splitlines())
    return "\n".join(line for line in lines if line)


def parse_timestamp(value: Any) -> datetime | None:
    """Read an ISO date or a millisecond timestamp. Unreadable values return None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return datetime.fromtimestamp(value / 1000, tz=UTC)
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


@lru_cache(maxsize=512)
def _term_pattern(term: str) -> re.Pattern[str]:
    return re.compile(rf"(?<![\w+#]){re.escape(term)}s?(?![\w+#])", re.IGNORECASE)


def find_term(text: str, term: str) -> str | None:
    """The text as it appears where term matches (whole word or phrase, plural allowed)."""
    match = _term_pattern(term).search(text)
    return match.group(0) if match else None


def contains_term(text: str, term: str) -> bool:
    """True when term appears as a whole word or phrase, allowing a plural."""
    return find_term(text, term) is not None


def mentions_term(text: str, term: str) -> bool:
    """Like contains_term, except a term of two characters or fewer must match its exact case.

    So "Go" is not found in "we go live", but is found in "Go and Python". Only skill matching
    uses this; contains_term is unchanged for everything else.
    """
    if len(term.strip()) > 2:
        return contains_term(text, term)
    return re.search(rf"(?<![\w+#]){re.escape(term.strip())}s?(?![\w+#])", text) is not None
