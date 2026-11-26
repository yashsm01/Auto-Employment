"""URL helpers shared by services. Kept apart so services can import each other freely."""

from urllib.parse import urlsplit


def safe_url(url: str | None) -> str | None:
    """Links come from third parties, so only plain web links reach the browser."""
    if not url:
        return None
    try:
        return url if urlsplit(url).scheme in ("http", "https") else None
    except ValueError:
        return None


def without_fragment(url: str) -> str:
    """The page itself: an anchor such as #contact names a place on the page, not another page."""
    return urlsplit(url)._replace(fragment="").geturl()
