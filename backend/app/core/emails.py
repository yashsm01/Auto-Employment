"""Email addresses published in job adverts, and a strict check before anything is sent."""

import re

_FIND = re.compile(r"[A-Za-z0-9._%+'-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
_VALID = re.compile(r"[A-Za-z0-9._%+'-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
_NO_REPLY = re.compile(r"^(no-?reply|do-?not-?reply|mailer-daemon|postmaster)@", re.IGNORECASE)
# Addresses at job boards belong to the board, not the employer.
_BOARD_DOMAINS = ("seek.co.nz", "seek.com", "seek.com.au", "linkedin.com", "indeed.com",
                  "indeed.co.nz", "trademe.co.nz", "glassdoor.com", "glassdoor.co.nz")


def is_valid_email(address: str) -> bool:
    return bool(address) and len(address) <= 254 and bool(_VALID.fullmatch(address))


def _is_board(address: str) -> bool:
    domain = address.rsplit("@", 1)[-1]
    return any(domain == board or domain.endswith(f".{board}") for board in _BOARD_DOMAINS)


def find_emails(text: str) -> list[str]:
    """Addresses in the text, lower-cased, in order of first appearance."""
    found: list[str] = []
    for match in _FIND.findall(text or ""):
        address = match.strip(".'").casefold()
        if (
            is_valid_email(address)
            and not _NO_REPLY.match(address)
            and not _is_board(address)
            and address not in found
        ):
            found.append(address)
    return found
