"""Sends email from the user's own Gmail with an app password. Never signs in without TLS."""

import smtplib
import ssl
from collections.abc import Callable
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from pathlib import Path
from typing import Any

from app.core.emails import is_valid_email
from app.core.errors import ProviderError

NAME = "email"
TIMEOUT_SECONDS = 30
_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


class SmtpSender:
    def __init__(
        self,
        host: str,
        port: int,
        address: str,
        password: str,
        from_name: str | None = None,
        smtp_ssl: Callable[..., Any] = smtplib.SMTP_SSL,
        smtp: Callable[..., Any] = smtplib.SMTP,
    ) -> None:
        self._host = host
        self._port = port
        self._address = address
        self._password = password
        self._from_name = from_name
        self._smtp_ssl = smtp_ssl
        self._smtp = smtp

    def _message(self, to: str, subject: str, body: str, attachment: Path | None,
                 attachment_name: str | None, reply_to_message_id: str | None) -> EmailMessage:
        message = EmailMessage()
        message["From"] = formataddr((self._from_name or "", self._address))
        message["To"] = to
        message["Subject"] = subject
        domain = self._address.rsplit("@", 1)[-1]
        message["Message-ID"] = make_msgid(domain=domain)
        if reply_to_message_id:
            message["In-Reply-To"] = reply_to_message_id
            message["References"] = reply_to_message_id
        message.set_content(body)
        if attachment is not None:
            message.add_attachment(
                attachment.read_bytes(), maintype="application", subtype="pdf",
                filename=attachment_name or attachment.name,
            )
        return message

    def _connect(self) -> Any:
        context = ssl.create_default_context()
        if self._port == 465:
            return self._smtp_ssl(self._host, self._port, timeout=TIMEOUT_SECONDS, context=context)
        return self._smtp(self._host, self._port, timeout=TIMEOUT_SECONDS)

    def send(
        self,
        *,
        to: str,
        subject: str,
        body: str,
        attachment: Path | None = None,
        attachment_name: str | None = None,
        reply_to_message_id: str | None = None,
        from_name: str | None = None,
    ) -> str:
        """Send one email and return its Message-ID."""
        if not is_valid_email(to):
            raise ProviderError(NAME, "not a valid email address")
        if from_name:
            self._from_name = from_name
        try:
            message = self._message(to, subject, body, attachment, attachment_name,
                                    reply_to_message_id)
        except (ValueError, TypeError):
            raise ProviderError(
                NAME, "could not build the email (a line break in the subject or name)"
            ) from None
        try:
            with self._connect() as server:
                if self._port != 465:
                    server.ehlo()
                    if server.has_extn("starttls"):
                        server.starttls(context=ssl.create_default_context())
                        server.ehlo()
                    elif self._host not in _LOCAL_HOSTS:
                        raise ProviderError(NAME, "the mail server would send without encryption")
                server.login(self._address, self._password)
                server.send_message(message)
        except smtplib.SMTPAuthenticationError:
            raise ProviderError(
                NAME, "Gmail sign-in failed: the app password was refused"
            ) from None
        except smtplib.SMTPRecipientsRefused:
            raise ProviderError(NAME, "the mail server refused the address") from None
        except (smtplib.SMTPException, OSError) as error:
            raise ProviderError(NAME, f"sending failed ({type(error).__name__})") from None
        return message["Message-ID"]
