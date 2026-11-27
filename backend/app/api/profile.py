from fastapi import APIRouter, UploadFile

from app.chains.manager import get_resume_chain
from app.core.deps import ConnDep, ProfileIdDep, SettingsDep
from app.schemas.resume import ProfileUpdate, ProfileView
from app.services import resume_service

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("")
def get_profile(conn: ConnDep, profile_id: ProfileIdDep, settings: SettingsDep) -> ProfileView:
    return resume_service.get_view(conn, profile_id, settings)


@router.put("")
def save_profile(
    body: ProfileUpdate, conn: ConnDep, profile_id: ProfileIdDep, settings: SettingsDep
) -> ProfileView:
    closed = resume_service.update(conn, profile_id, body)
    conn.commit()
    view = resume_service.get_view(conn, profile_id, settings)
    view.closed_outside_areas = closed
    return view


@router.post("/resume")
def upload_resume(
    file: UploadFile, conn: ConnDep, profile_id: ProfileIdDep, settings: SettingsDep
) -> ProfileView:
    # Read one byte past the limit, so an oversized file is detected without loading all of it.
    data = file.file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    warning = resume_service.upload_resume(
        conn, profile_id, file.filename or "", data, get_resume_chain(settings), settings
    )
    conn.commit()
    return resume_service.get_view(conn, profile_id, settings, warning=warning)
