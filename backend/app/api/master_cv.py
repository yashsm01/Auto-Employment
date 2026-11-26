import secrets
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from app.chains.resume_sections_chain import ResumeSectionsChain
from app.core.deps import ConnDep, ProfileIdDep, SettingsDep, get_sections_chain
from app.core.resume_docx import render_resume_docx
from app.core.resume_layout import cv_file_name
from app.core.resume_pdf import render_resume_pdf
from app.schemas.master_cv import MasterCV, MasterCVView
from app.services import master_cv_service

router = APIRouter(prefix="/master-cv", tags=["master-cv"])
SectionsChainDep = Annotated[ResumeSectionsChain | None, Depends(get_sections_chain)]
MEDIA_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


@router.get("")
def get_master_cv(
    conn: ConnDep, profile_id: ProfileIdDep, sections_chain: SectionsChainDep, settings: SettingsDep
) -> MasterCVView:
    view = master_cv_service.load(conn, profile_id, sections_chain)
    conn.commit()  # The first read may cache the sections it just read with AI.
    return master_cv_service.with_ats(view, Path(settings.upload_dir), profile_id)


@router.put("")
def save_master_cv(
    body: MasterCV, conn: ConnDep, profile_id: ProfileIdDep, settings: SettingsDep
) -> MasterCVView:
    view = master_cv_service.save(conn, profile_id, body)
    conn.commit()
    return master_cv_service.with_ats(view, Path(settings.upload_dir), profile_id)


@router.get("/file")
def download_master_cv(
    conn: ConnDep,
    profile_id: ProfileIdDep,
    sections_chain: SectionsChainDep,
    settings: SettingsDep,
    fmt: Annotated[Literal["pdf", "docx"], Query(alias="format")] = "pdf",
) -> FileResponse:
    """The master CV as a PDF or Word file. The temporary file is removed after the response."""
    view = master_cv_service.load(conn, profile_id, sections_chain)
    conn.commit()
    directory = Path(settings.upload_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"master-cv-{secrets.token_hex(12)}.{fmt}"
    try:
        if fmt == "pdf":
            render_resume_pdf(view.contact, view.sections, path, template=view.template)
        else:
            render_resume_docx(view.contact, view.sections, path, template=view.template)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return FileResponse(
        path,
        media_type=MEDIA_TYPES[fmt],
        filename=cv_file_name(view.contact, fmt),
        background=BackgroundTask(path.unlink, missing_ok=True),
    )
