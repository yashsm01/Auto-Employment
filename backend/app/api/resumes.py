from uuid import UUID

from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import FileResponse

from app.core.deps import ConnDep, ProfileIdDep, SettingsDep
from app.schemas.tailoring import (
    CoverNoteUpdate,
    ResumeDecision,
    ReviewList,
    StatusResponse,
    TailoredResumeView,
)
from app.services import resume_review_service
from app.workers.tailor_job import tailor_one

router = APIRouter(tags=["resumes"])


@router.get("/resume-review")
def resume_review(conn: ConnDep, profile_id: ProfileIdDep) -> ReviewList:
    return resume_review_service.review_list(conn, profile_id)


@router.get("/applications/{application_id}/resume")
def tailored_resume(
    application_id: UUID, conn: ConnDep, profile_id: ProfileIdDep
) -> TailoredResumeView:
    return resume_review_service.view(conn, profile_id, application_id)


@router.put("/applications/{application_id}/resume")
def save_cover_note(
    application_id: UUID, body: CoverNoteUpdate, conn: ConnDep, profile_id: ProfileIdDep
) -> TailoredResumeView:
    resume_review_service.update_cover_note(conn, profile_id, application_id, body.cover_note)
    conn.commit()
    return resume_review_service.view(conn, profile_id, application_id)


@router.post("/applications/{application_id}/resume-decision")
def resume_decision(
    application_id: UUID, body: ResumeDecision, conn: ConnDep, profile_id: ProfileIdDep
) -> StatusResponse:
    result = resume_review_service.decide(conn, profile_id, application_id, body.action)
    conn.commit()
    return result


@router.post("/applications/{application_id}/tailor")
def regenerate(
    application_id: UUID,
    conn: ConnDep,
    profile_id: ProfileIdDep,
    settings: SettingsDep,
    background: BackgroundTasks,
) -> StatusResponse:
    resume_review_service.request_tailoring(conn, profile_id, application_id)
    conn.commit()
    background.add_task(tailor_one, settings, str(application_id))
    return StatusResponse(id=application_id, status="tailoring")


@router.get("/resumes/{resume_id}/pdf")
def resume_pdf(
    resume_id: UUID, conn: ConnDep, profile_id: ProfileIdDep, settings: SettingsDep
) -> FileResponse:
    path = resume_review_service.pdf_path(conn, profile_id, resume_id, settings.upload_dir)
    return FileResponse(path, media_type="application/pdf", filename="Resume.pdf")
