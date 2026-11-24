"""Job alerts from the user's own Gmail, read over IMAP with an app password.

The mailbox is opened read-only, so nothing is sent, deleted or marked as read.
Links in alerts are stored, never opened.
"""

import email
import hashlib
import imaplib
import re
from collections.abc import Callable
from dataclasses import dataclass
from email.message import Message
from email.policy import default as default_policy
from typing import Any, Protocol
from urllib.parse import urlsplit

from app.core.errors import ProviderError
from app.core.normalize import strip_html
from app.schemas.job import AlertJob, JobDraft

NAME = "gmail"
GMAIL_IMAP_HOST = "imap.gmail.com"
ALL_MAIL = '"[Gmail]/All Mail"'
MAX_EMAIL_CHARS = 20_000
SIGN_IN_FAILED = (
    "sign-in failed. Check EMAIL_ADDRESS and EMAIL_APP_PASSWORD in backend/.env, "
    "and that 2-Step Verification is on for this Google account"
)
_LINK = re.compile(
    r"""<a\b[^>]*?href=["']([^"']+)["'][^>]*>(.*?)</a>""", re.IGNORECASE | re.DOTALL
)


@dataclass(frozen=True)
class EmailMessage:
    id: str
    subject: str
    sender: str
    text: str


def message_text(message: Message) -> str:
    """Prefer plain text. For HTML, keep each link's address beside its text."""
    part = message.get_body(preferencelist=("plain", "html"))
    if part is None:
        return ""
    content = part.get_content()
    if part.get_content_subtype() == "plain":
        return content.strip()
    return strip_html(_LINK.sub(lambda m: f"{m[2]} ({m[1]})", content))


def _quoted(query: str) -> str:
    return '"' + query.replace("\\", "\\\\").replace('"', '\\"') + '"'


class ImapMailReader:
    """Reads Gmail over IMAP. Signs in once per search run."""

    def __init__(
        self,
        address: str,
        app_password: str,
        host: str = GMAIL_IMAP_HOST,
        connect: Callable[[str], Any] = imaplib.IMAP4_SSL,
    ) -> None:
        self._address = address
        self._password = app_password
        self._host = host
        self._connect = connect
        self._connection: Any = None

    def _open(self) -> Any:
        if self._connection is not None:
            return self._connection
        try:
            connection = self._connect(self._host)
        except OSError as error:
            raise ProviderError(NAME, f"could not connect ({type(error).__name__})") from None
        try:
            connection.login(self._address, self._password)
        except imaplib.IMAP4.error:
            raise ProviderError(NAME, SIGN_IN_FAILED) from None
        status, _ = connection.select(ALL_MAIL, readonly=True)
        if status != "OK":
            status, _ = connection.select("INBOX", readonly=True)
        if status != "OK":
            raise ProviderError(NAME, "could not open the mailbox")
        self._connection = connection
        return connection

    def list_ids(self, query: str, limit: int) -> list[str]:
        """Message IDs matching a Gmail search, newest first."""
        try:
            status, data = self._open().uid("SEARCH", None, "X-GM-RAW", _quoted(query))
        except (imaplib.IMAP4.error, OSError):
            raise ProviderError(NAME, "search failed") from None
        if status != "OK":
            raise ProviderError(NAME, "search failed")
        ids = [value.decode() for value in (data[0] or b"").split()]
        return list(reversed(ids[-limit:]))

    def read(self, message_id: str) -> EmailMessage:
        try:
            status, data = self._open().uid("FETCH", message_id, "(BODY.PEEK[])")
        except (imaplib.IMAP4.error, OSError):
            raise ProviderError(NAME, "could not read an email") from None
        raw = next((item[1] for item in data or [] if isinstance(item, tuple)), None)
        if status != "OK" or raw is None:
            raise ProviderError(NAME, "could not read an email")
        message = email.message_from_bytes(raw, policy=default_policy)
        return EmailMessage(
            id=message_id,
            subject=str(message["subject"] or ""),
            sender=str(message["from"] or ""),
            text=message_text(message),
        )

    def close(self) -> None:
        if self._connection is not None:
            try:
                self._connection.logout()
            except (imaplib.IMAP4.error, OSError):
                pass
            self._connection = None


class MailReader(Protocol):
    def list_ids(self, query: str, limit: int) -> list[str]: ...

    def read(self, message_id: str) -> EmailMessage: ...


def _web_link(url: str | None) -> str | None:
    if not url:
        return None
    try:
        return url if urlsplit(url).scheme in ("http", "https") else None
    except ValueError:
        return None


class GmailAlertsSource:
    """Reads recent alert emails once per search run."""

    name = "gmail_alert"
    label = "Gmail job alerts"

    def __init__(
        self,
        mail: MailReader,
        extract: Callable[[str], list[AlertJob]],
        query: str,
        limit: int,
    ) -> None:
        self._mail = mail
        self._extract = extract
        self._query = query
        self._limit = limit
        self._fetched = False

    def _to_job(self, message_id: str, alert: AlertJob) -> JobDraft | None:
        title, company = alert.title.strip(), alert.company.strip()
        if not title or not company:
            return None
        key = hashlib.sha256(f"{title}|{company}".casefold().encode("utf-8")).hexdigest()[:16]
        return JobDraft(
            source=self.name,
            external_id=f"{message_id}:{key}",
            title=title,
            company=company,
            location=alert.location.strip(),
            url=_web_link(alert.url),
            description=alert.summary.strip(),
        )

    def _read_all(self) -> list[JobDraft]:
        ids = self._mail.list_ids(self._query, self._limit)
        jobs: list[JobDraft] = []
        failure: ProviderError | None = None
        succeeded = 0
        for message_id in ids:
            try:
                message = self._mail.read(message_id)
                text = f"Subject: {message.subject}\nFrom: {message.sender}\n\n{message.text}"
                alerts = self._extract(text[:MAX_EMAIL_CHARS])
            except ProviderError as error:
                failure = error
                continue
            succeeded += 1
            jobs.extend(job for a in alerts if (job := self._to_job(message_id, a)))
        if ids and not succeeded and failure:
            raise failure
        return jobs

    def search(self, keywords: str) -> list[JobDraft]:
        if self._fetched:
            return []
        self._fetched = True
        try:
            return self._read_all()
        finally:
            close = getattr(self._mail, "close", None)
            if close:
                close()
