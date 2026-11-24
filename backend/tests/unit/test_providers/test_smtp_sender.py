import smtplib
from email.message import EmailMessage

import pytest

from app.core.errors import ProviderError
from app.providers.channels.smtp_sender import SmtpSender


class FakeSMTP:
    instances: list["FakeSMTP"] = []

    def __init__(self, host, port, timeout=None, context=None, starttls=True, error=None):
        self.host, self.port = host, port
        self.logged_in = None
        self.sent: list[EmailMessage] = []
        self.tls = False
        self._starttls = starttls
        self._error = error
        FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def ehlo(self):
        return 250, b"ok"

    def has_extn(self, name):
        return name.lower() == "starttls" and self._starttls

    def starttls(self, context=None):
        self.tls = True

    def login(self, user, password):
        if isinstance(self._error, smtplib.SMTPAuthenticationError):
            raise self._error
        self.logged_in = (user, password)

    def send_message(self, message):
        if self._error and not isinstance(self._error, smtplib.SMTPAuthenticationError):
            raise self._error
        self.sent.append(message)


def factory(**kwargs):
    def make(host, port, timeout=None, context=None):
        return FakeSMTP(host, port, timeout, context, **kwargs)

    return make


@pytest.fixture(autouse=True)
def reset():
    FakeSMTP.instances.clear()


def _sender(host="smtp.gmail.com", port=465, **kwargs):
    return SmtpSender(host, port, "me@example.com", "app-password", "Sample Person",
                      smtp_ssl=factory(**kwargs), smtp=factory(**kwargs))


def test_sends_with_the_resume_attached_and_returns_the_message_id(tmp_path):
    pdf = tmp_path / "resume.pdf"
    pdf.write_bytes(b"%PDF-1.4 test")

    message_id = _sender().send(
        to="jobs@example.co.nz", subject="Application for Data Engineer", body="Kia ora,",
        attachment=pdf, attachment_name="Sample Person - Data Engineer.pdf",
    )

    smtp = FakeSMTP.instances[0]
    assert (smtp.host, smtp.port, smtp.logged_in) == (
        "smtp.gmail.com", 465, ("me@example.com", "app-password"))
    message = smtp.sent[0]
    assert message["To"] == "jobs@example.co.nz"
    assert message["From"] == "Sample Person <me@example.com>"
    assert message["Subject"] == "Application for Data Engineer"
    assert message["Message-ID"] == message_id
    attachment = next(message.iter_attachments())
    assert attachment.get_filename() == "Sample Person - Data Engineer.pdf"
    assert attachment.get_content_type() == "application/pdf"
    assert attachment.get_content() == b"%PDF-1.4 test"


def test_a_follow_up_replies_in_the_same_thread():
    _sender().send(to="jobs@example.co.nz", subject="Re: Application", body="Following up",
                   reply_to_message_id="<abc@example.com>")

    message = FakeSMTP.instances[0].sent[0]
    assert message["In-Reply-To"] == "<abc@example.com>"
    assert message["References"] == "<abc@example.com>"
    assert not list(message.iter_attachments())


def test_other_ports_use_starttls():
    _sender(port=587).send(to="jobs@example.co.nz", subject="s", body="b")

    assert FakeSMTP.instances[0].tls is True


def test_never_signs_in_without_encryption_except_on_this_computer():
    with pytest.raises(ProviderError, match="without encryption"):
        _sender(port=587, starttls=False).send(to="jobs@example.co.nz", subject="s", body="b")
    assert FakeSMTP.instances[0].logged_in is None

    _sender(host="127.0.0.1", port=2525, starttls=False).send(
        to="jobs@example.co.nz", subject="s", body="b")
    assert len(FakeSMTP.instances[1].sent) == 1


def test_a_refused_app_password_is_reported_plainly():
    with pytest.raises(ProviderError, match="app password was refused"):
        _sender(error=smtplib.SMTPAuthenticationError(535, b"bad")).send(
            to="jobs@example.co.nz", subject="s", body="b")


def test_a_refused_address_is_reported_plainly():
    error = smtplib.SMTPRecipientsRefused({"jobs@example.co.nz": (550, b"no such user")})
    with pytest.raises(ProviderError, match="refused the address"):
        _sender(error=error).send(to="jobs@example.co.nz", subject="s", body="b")


def test_header_injection_in_the_address_is_refused():
    with pytest.raises(ProviderError, match="not a valid email address"):
        _sender().send(to="jobs@x.com\r\nBcc: other@y.com", subject="s", body="b")
    assert FakeSMTP.instances == []


def test_a_bad_header_is_reported_instead_of_crashing():
    with pytest.raises(ProviderError, match="could not build the email"):
        _sender().send(to="jobs@example.co.nz", subject="Line\r\nBreak", body="b")
