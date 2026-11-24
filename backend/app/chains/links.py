"""Swaps long links for short labels before text goes to a model, and back afterwards.

Job alert and careers links are often hundreds of characters of tracking data. Labels keep
answers short and stop a model from copying a link wrongly.
"""

import re

_URL = re.compile(r"https?://[^\s<>()\[\]\"']+")
_LABEL = re.compile(r"\[?\s*link\s*(\d+)\s*\]?", re.IGNORECASE)
_TRAILING = ".,;:!?"

LINK_RULE = (
    "Links appear as labels such as [link 3]. For url, return the label of that job's link "
    "exactly as written, or null if it has none."
)


def shorten_links(text: str) -> tuple[str, dict[str, str]]:
    """Return the text with labels, and a map from each label to its link."""
    labels: dict[str, str] = {}

    def swap(match: re.Match[str]) -> str:
        found = match.group(0)
        url = found.rstrip(_TRAILING)
        label = labels.setdefault(url, f"[link {len(labels) + 1}]")
        return label + found[len(url) :]

    return _URL.sub(swap, text), {label: url for url, label in labels.items()}


def restore_link(value: str | None, links: dict[str, str], original: str) -> str | None:
    """The real link for a label. A link the model wrote is kept only if it was in the text."""
    if not value or not value.strip():
        return None
    label = _LABEL.fullmatch(value.strip())
    if label:
        return links.get(f"[link {label[1]}]")
    return value if value in original else None
