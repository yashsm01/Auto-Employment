"""New Zealand phone numbers in the international form a dialler needs (+64...)."""

import re

_NOT_DIGIT = re.compile(r"\D")


def nz_e164(raw: str | None) -> str | None:
    if not raw or not raw.strip():
        return None
    text = raw.strip()
    digits = _NOT_DIGIT.sub("", text)
    if text.startswith("+"):
        number = f"+{digits}"
    elif digits.startswith("64"):
        number = f"+{digits}"
    elif digits.startswith("0"):
        number = f"+64{digits[1:]}"
    else:
        return None
    return number if 9 <= len(number) - 1 <= 15 else None
