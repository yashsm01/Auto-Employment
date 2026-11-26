"""Finds a company's job board or careers page from the text of its website."""

import re
from urllib.parse import urljoin, urlsplit

from app.core.urls import without_fragment
from app.providers.company.website_reader import is_allowed_url

_BOARD_PATTERNS = (
    ("greenhouse", re.compile(r"https?://(?:job-)?boards(?:\.eu)?\.greenhouse\.io/([\w.-]+)")),
    ("lever", re.compile(r"https?://jobs(?:\.eu)?\.lever\.co/([\w.-]+)")),
    ("ashby", re.compile(r"https?://jobs\.ashbyhq\.com/([\w.-]+)")),
)
# Hiring systems that companies use to host their own job lists.
_HIRING_SITES = (
    "myworkdayjobs.com",
    "smartrecruiters.com",
    "applynow.net.nz",
    "jobadder.com",
    "employmenthero.com",
    "teamtailor.com",
    "recruitee.com",
    "bamboohr.com",
    "workable.com",
    "pinpointhq.com",
    "breezy.hr",
    "elmotalent.com.au",
    "livehire.com",
    "snaphire.com",
    "applytojob.com",
    "icims.com",
    "successfactors.com",
    "taleo.net",
)
_LINK = re.compile(r"\[([^\]]*)\]\(([^)\s]+)")
_MAIN_CAREERS_TEXT = re.compile(
    r"^\s*(?:careers?|jobs|vacancies|current (?:vacancies|opportunities)|open (?:roles|positions)"
    r"|join (?:us|our team)|work (?:with|for) us)\s*$",
    re.IGNORECASE,
)
_CAREER_WORDS = re.compile(
    r"career|vacanc|\bjobs?\b|join[- ]?(?:us|our)|work[- ](?:with|for)[- ]us|opportunit",
    re.IGNORECASE,
)
_SIDE_PAGES = re.compile(r"scholarship|graduate|intern|blog|news|stor(?:y|ies)", re.IGNORECASE)


def find_board(page: str) -> tuple[str, str] | None:
    """The (platform, board name) of a public job board linked from the page."""
    for platform, pattern in _BOARD_PATTERNS:
        match = pattern.search(page)
        if match:
            return platform, match[1]
    return None


def site_host(url: str) -> str:
    host = (urlsplit(url).hostname or "").casefold()
    return host.removeprefix("www.")


def _on(host: str, domain: str) -> bool:
    return host == domain or host.endswith(f".{domain}")


def find_careers_link(page: str, base_url: str) -> str | None:
    """The best careers link on the employer's site, a careers subdomain, or a hiring site."""
    home = site_host(base_url)
    best: tuple[int, int, str] | None = None
    for text, href in _LINK.findall(page):
        try:
            url = without_fragment(urljoin(base_url, href))
            host = site_host(url)
        except ValueError:  # malformed href on an untrusted page
            continue
        hiring_site = any(_on(host, domain) for domain in _HIRING_SITES)
        if not (_on(host, home) or hiring_site) or not is_allowed_url(url):
            continue

        path = urlsplit(url).path
        if _MAIN_CAREERS_TEXT.match(text):
            score = 3
        elif _CAREER_WORDS.search(text):
            score = 2
        elif _CAREER_WORDS.search(path) or hiring_site:
            score = 1
        else:
            continue
        if _SIDE_PAGES.search(f"{text} {path}"):
            score -= 1
        if score > 0 and (best is None or (score, -len(path)) > best[:2]):
            best = (score, -len(path), url)
    return best[2] if best else None
