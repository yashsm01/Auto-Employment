"""Looks up an employer's contact details in the background, after it is saved."""

import logging
from datetime import UTC, datetime
from uuid import UUID

import httpx

from app.core.config import Settings
from app.db.client import connect
from app.services import contact_service, source_service

logger = logging.getLogger(__name__)


def refresh_contacts(settings: Settings, company_id: UUID) -> None:
    """Read the employer's pages if they were not checked in the last 30 days. Never raises."""
    try:
        with httpx.Client(timeout=20) as client, connect(settings.database_url) as conn:
            tools = source_service.build_contact_tools(settings, client)
            contact_service.lookup(conn, company_id, tools, datetime.now(UTC))
            conn.commit()
    except Exception:
        logger.exception("Contact lookup failed for employer %s", company_id)
