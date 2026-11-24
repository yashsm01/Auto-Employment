"""Resume upload and the editable profile."""

import logging
import secrets
from pathlib import Path, PurePosixPath
from uuid import UUID

import psycopg

from app.chains.resume_profile_chain import OfflineResumeChain, ResumeChain
from app.core.config import Settings
from app.core.documents import extract_contact_details, extract_resume_text, file_suffix
from app.core.errors import BadRequest, NotFound, ProviderError
from app.repositories import profiles_repo
from app.schemas.resume import ProfileUpdate, ProfileView, ResumeProfile

logger = logging.getLogger(__name__)

_OFFLINE_WARNING = (
    "AI reading is not connected, so basic matching was used. Please check your titles and skills."
)
_FAILED_WARNING = (
    "AI reading failed ({reason}), so basic matching was used. "
    "Please check your titles and skills."
)


def read_profile(text: str, chain: ResumeChain | None) -> tuple[ResumeProfile, str | None]:
    """Read with AI when available. Any AI failure falls back to free matching."""
    if chain is None:
        return OfflineResumeChain().run(text), _OFFLINE_WARNING
    try:
        profile = chain.run(text)
    except ProviderError as error:
        logger.warning("Resume AI failed: %s", error)
        return OfflineResumeChain().run(text), _FAILED_WARNING.format(reason=error)
    if not profile.titles and not profile.skills:
        reason = "no titles or skills were found"
        return OfflineResumeChain().run(text), _FAILED_WARNING.format(reason=reason)
    return profile, None


def connections(settings: Settings) -> dict[str, bool]:
    """Which services have keys. Never includes the keys themselves."""
    return {
        "claude": bool(settings.anthropic_api_key.get_secret_value()),
        "gemini": bool(settings.google_api_key.get_secret_value()),
        "trademe": bool(
            settings.trademe_consumer_key and settings.trademe_consumer_secret.get_secret_value()
        ),
        "gmail": bool(
            settings.email_enabled
            and settings.email_address
            and settings.email_app_password.get_secret_value()
        ),
        "places": bool(settings.google_maps_api_key.get_secret_value()),
        "tavily": bool(settings.tavily_api_key.get_secret_value()),
    }


def get_view(
    conn: psycopg.Connection,
    profile_id: UUID,
    settings: Settings,
    warning: str | None = None,
) -> ProfileView:
    row = profiles_repo.load_view_row(conn, profile_id)
    if row is None:
        raise NotFound("No resume profile found.")
    content = row["content"]
    contact = content.get("contact") or (
        extract_contact_details(content["text"]).model_dump() if content.get("text") else {}
    )
    return ProfileView(
        is_example=content.get("example") is True,
        filename=content.get("filename"),
        titles=row["titles"],
        skills=row["skills"],
        tools=row["tools"],
        industries=row["industries"],
        seniority=row["seniority"],
        search_queries=row["search_queries"],
        regions=row["regions"],
        work_rights=row["work_rights"],
        salary_min=row["salary_min"],
        avoid_keywords=row["avoid_keywords"],
        shortlist_threshold=row["shortlist_threshold"],
        boards=row["boards"],
        connections=connections(settings),
        contact=contact,
        warning=warning,
    )


def update(conn: psycopg.Connection, profile_id: UUID, body: ProfileUpdate) -> None:
    with conn.transaction():
        profiles_repo.update_profile(conn, profile_id, body)


def _display_name(filename: str) -> str:
    return PurePosixPath(filename.replace("\\", "/")).name[:120]


def upload_resume(
    conn: psycopg.Connection,
    profile_id: UUID,
    filename: str,
    data: bytes,
    chain: ResumeChain | None,
    settings: Settings,
) -> str | None:
    """Read and store a new base resume. The first real resume clears all example data."""
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise BadRequest(f"This file is too large. The limit is {settings.max_upload_mb} MB.")

    text = extract_resume_text(filename, data)
    resume, warning = read_profile(text, chain)

    directory = Path(settings.upload_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{secrets.token_hex(16)}{file_suffix(filename)}"
    path.write_bytes(data)
    try:
        with conn.transaction():
            if profiles_repo.has_example_resume(conn, profile_id):
                profiles_repo.clear_example_data(conn, profile_id)
            content = {
                "filename": _display_name(filename),
                "text": text,
                "contact": extract_contact_details(text).model_dump(),
            }
            profiles_repo.add_base_resume(conn, profile_id, content, str(path), resume)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return warning
