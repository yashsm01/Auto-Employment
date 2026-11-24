from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks

from app.core.deps import ConnDep, ProfileIdDep, SettingsDep
from app.schemas.prep import DeepSearchSettings, DeepSearchView, PrepRequest, PrepView
from app.services import prep_service
from app.workers.prep_job import process_prep_queue

router = APIRouter(tags=["deep search"])


@router.get("/deep-search")
def get_deep_search(
    conn: ConnDep, profile_id: ProfileIdDep, settings: SettingsDep
) -> DeepSearchView:
    return prep_service.settings_view(conn, profile_id, settings, datetime.now(UTC))


@router.put("/deep-search")
def save_deep_search(
    body: DeepSearchSettings, conn: ConnDep, profile_id: ProfileIdDep, settings: SettingsDep
) -> DeepSearchView:
    prep_service.save_settings(conn, profile_id, body)
    conn.commit()
    return prep_service.settings_view(conn, profile_id, settings, datetime.now(UTC))


@router.get("/applications/{application_id}/prep")
def get_prep(
    application_id: UUID, conn: ConnDep, profile_id: ProfileIdDep, settings: SettingsDep
) -> PrepView:
    return prep_service.view(conn, profile_id, application_id, settings, datetime.now(UTC))


@router.post("/applications/{application_id}/prep")
def run_prep(
    application_id: UUID,
    body: PrepRequest,
    conn: ConnDep,
    profile_id: ProfileIdDep,
    settings: SettingsDep,
    background: BackgroundTasks,
) -> PrepView:
    now = datetime.now(UTC)
    extra = body.extra.strip() if body.extra and body.extra.strip() else None
    prep_service.request_run(conn, profile_id, application_id, extra, settings, now)
    conn.commit()
    background.add_task(process_prep_queue, settings)
    return prep_service.view(conn, profile_id, application_id, settings, now)
