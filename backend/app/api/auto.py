from datetime import UTC, datetime

from fastapi import APIRouter

from app.core.deps import ConnDep, ProfileIdDep, SettingsDep
from app.schemas.auto import AutoModeSettings, AutoModeView
from app.services import auto_service

router = APIRouter(tags=["auto mode"])


@router.get("/auto-mode")
def get_auto_mode(conn: ConnDep, profile_id: ProfileIdDep, settings: SettingsDep) -> AutoModeView:
    return auto_service.view(conn, profile_id, settings, datetime.now(UTC))


@router.put("/auto-mode")
def save_auto_mode(
    body: AutoModeSettings, conn: ConnDep, profile_id: ProfileIdDep, settings: SettingsDep
) -> AutoModeView:
    auto_service.save_settings(conn, profile_id, body)
    conn.commit()
    return auto_service.view(conn, profile_id, settings, datetime.now(UTC))
