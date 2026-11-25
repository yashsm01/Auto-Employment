from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import UUID

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel, Field

from app.core.config import Settings
from app.core.deps import ConnDep, ProfileIdDep, SettingsDep, get_settings
from app.core.errors import ProviderError
from app.providers.channels.whatsapp_service import WhatsAppService
from app.providers.voice.omnidim import OmniDimClient
from app.schemas.outbox import OutboxView, SendRequest
from app.services import calls_service, notify_service, outbox_service
from app.workers.outbox_job import process_outbox

router = APIRouter(tags=["calls and WhatsApp"])
HTTP_TIMEOUT_SECONDS = 30


def get_omni(settings: Settings = Depends(get_settings)) -> Iterator[OmniDimClient | None]:
    if not calls_service.configured(settings):
        yield None
        return
    with httpx.Client(timeout=HTTP_TIMEOUT_SECONDS) as client:
        yield OmniDimClient(client, settings.omnidim_api_key.get_secret_value(),
                            settings.omnidim_base_url)


def get_whatsapp(settings: Settings = Depends(get_settings)) -> Iterator[WhatsAppService | None]:
    if not notify_service.configured(settings):
        yield None
        return
    with httpx.Client(timeout=HTTP_TIMEOUT_SECONDS) as client:
        yield WhatsAppService(client, settings.whatsapp_service_url,
                              settings.whatsapp_service_token.get_secret_value(),
                              settings.whatsapp_to_field, settings.whatsapp_text_field)


class CallsStatus(BaseModel):
    configured: bool
    enabled: bool
    used_this_month: int
    monthly_limit: int


class WhatsAppStatus(BaseModel):
    configured: bool
    to: str | None = None


class CallItem(BaseModel):
    id: UUID
    purpose: str
    status: str
    title: str | None = None
    company: str | None = None
    created_at: datetime
    duration_sec: int | None = None
    captured_email: str | None = None
    error: str | None = None
    transcript: str | None = None


class WhatsAppLink(BaseModel):
    state: str
    qr: str | None = None
    me: str | None = None
    error: str | None = None


class Phase4View(BaseModel):
    calls: CallsStatus
    whatsapp: WhatsAppStatus
    recent_calls: list[CallItem] = Field(default_factory=list)


def _view(conn, profile_id, settings: Settings) -> Phase4View:
    now = datetime.now(UTC)
    return Phase4View(
        calls=CallsStatus(
            configured=calls_service.configured(settings),
            enabled=calls_service.automatic(settings),
            used_this_month=calls_service.used_this_month(conn, profile_id, now),
            monthly_limit=settings.max_calls_per_month,
        ),
        whatsapp=WhatsAppStatus(
            configured=notify_service.configured(settings),
            to=notify_service.masked(settings.whatsapp_to) if settings.whatsapp_to else None,
        ),
        recent_calls=[
            CallItem(
                id=row["id"], purpose=row["purpose"], status=row["status"], title=row["title"],
                company=row["company"] or None, created_at=row["created_at"],
                duration_sec=row["duration_sec"],
                captured_email=(row["extracted"] or {}).get("captured_email"),
                error=row["error"], transcript=row["transcript"],
            )
            for row in calls_service.calls_repo.recent(conn, profile_id)
        ],
    )


@router.get("/settings/phase4")
def phase4_settings(conn: ConnDep, profile_id: ProfileIdDep, settings: SettingsDep) -> Phase4View:
    return _view(conn, profile_id, settings)


@router.post("/calls/test")
def test_call(
    conn: ConnDep,
    profile_id: ProfileIdDep,
    settings: SettingsDep,
    omni: OmniDimClient | None = Depends(get_omni),
) -> Phase4View:
    calls_service.test_call(conn, settings, omni, profile_id, datetime.now(UTC))
    conn.commit()
    return _view(conn, profile_id, settings)


@router.post("/notifications/test")
def test_whatsapp(
    conn: ConnDep,
    profile_id: ProfileIdDep,
    settings: SettingsDep,
    whatsapp: WhatsAppService | None = Depends(get_whatsapp),
) -> Phase4View:
    if whatsapp is None:
        raise ProviderError(
            "whatsapp", "set WHATSAPP_ENABLED, WHATSAPP_SERVICE_URL and WHATSAPP_TO in backend/.env"
        )
    whatsapp.send(settings.whatsapp_to, notify_service.TEST_MESSAGE)
    return _view(conn, profile_id, settings)


@router.get("/whatsapp/status")
def whatsapp_status(
    settings: SettingsDep, whatsapp: WhatsAppService | None = Depends(get_whatsapp)
) -> WhatsAppLink:
    """The WhatsApp Web link: a QR code to scan, connected, or the service isn't running."""
    if whatsapp is None:
        return WhatsAppLink(
            state="disabled",
            error="Add WHATSAPP_ENABLED=true and WHATSAPP_TO to backend/.env, then restart.",
        )
    try:
        data = whatsapp.status()
    except ProviderError as error:
        return WhatsAppLink(state="offline", error=str(error))
    me = data.get("me")
    return WhatsAppLink(
        state=str(data.get("state") or "unknown"),
        qr=data.get("qr") if str(data.get("qr") or "").startswith("data:image/png") else None,
        me=notify_service.masked(f"+{me}") if me else None,
        error=data.get("error"),
    )


@router.post("/whatsapp/logout")
def whatsapp_logout(
    settings: SettingsDep, whatsapp: WhatsAppService | None = Depends(get_whatsapp)
) -> WhatsAppLink:
    if whatsapp is None:
        raise ProviderError("whatsapp", "WhatsApp is not set up in backend/.env")
    whatsapp.logout()
    return WhatsAppLink(state="logged_out")


@router.post("/applications/{application_id}/send-after-call")
def send_after_call(
    application_id: UUID,
    body: SendRequest,
    conn: ConnDep,
    profile_id: ProfileIdDep,
    settings: SettingsDep,
    background: BackgroundTasks,
) -> OutboxView:
    now = datetime.now(UTC)
    calls_service.send_after_call(conn, profile_id, application_id, body.to, settings, now)
    conn.commit()
    background.add_task(process_outbox, settings)
    return outbox_service.view(conn, profile_id, settings, now)
