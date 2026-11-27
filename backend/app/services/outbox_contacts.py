"""The Outbox contacts list: the details each employer publishes, and why no address was found."""

from datetime import datetime
from typing import Any
from uuid import UUID

import psycopg

from app.core.errors import NotFound
from app.core.urls import safe_url
from app.core.workdays import NZ_TIME
from app.providers.company.website_reader import is_allowed_url
from app.repositories import outbox_repo
from app.schemas.contacts import EmployerContacts
from app.schemas.outbox_contacts import ContactRow, OutboxContacts
from app.services import contact_service, outbox_service
from app.services.advert_contact import AdvertContact, advert_contact, applies_on_site_only
from app.services.contact_service import ContactTools

STATUSES = ("approved", "sent", "followed_up", "replied")
SITE_ONLY = "Advert asks you to apply on the job site"
NO_WEBSITE = "No website known"
NOT_CHECKED = "Website not checked yet"
COULD_NOT_READ = "Could not read the website"


def rows(conn: psycopg.Connection, profile_id: UUID) -> OutboxContacts:
    found = outbox_repo.contact_rows(conn, profile_id, statuses=STATUSES)
    return OutboxContacts(rows=_build(conn, found))


def find_contacts(
    conn: psycopg.Connection,
    profile_id: UUID,
    application_id: UUID,
    tools: ContactTools,
    now: datetime,
) -> ContactRow:
    """Read the employer's pages now, then return the application's row."""
    found = outbox_repo.contact_rows(conn, profile_id, application_id=application_id)
    if not found or found[0]["company_id"] is None:
        raise NotFound("Application not found")
    contact_service.lookup(conn, found[0]["company_id"], tools, now, force=True)
    refreshed = outbox_repo.contact_rows(conn, profile_id, application_id=application_id)
    return _build(conn, refreshed)[0]


def _build(conn: psycopg.Connection, found: list[dict[str, Any]]) -> list[ContactRow]:
    addresses = outbox_repo.first_application_addresses(conn, [row["id"] for row in found])
    contacts: dict[UUID, EmployerContacts] = {}
    result = []
    for row in found:
        company_id = row["company_id"]
        if company_id is not None and company_id not in contacts:
            contacts[company_id] = contact_service.view(conn, company_id)
        details = contacts[company_id] if company_id is not None else EmployerContacts()
        address_used = addresses.get(row["id"])
        known = address_used or outbox_service.suggested_address(conn, row)
        result.append(ContactRow(
            application_id=row["id"],
            title=row["title"],
            company=row["company"],
            kind=row["kind"],
            status=row["status"],
            hiring_emails=details.hiring_emails,
            emails=details.emails,
            advert_contact=_advert(row),
            phone=details.phone,
            phone_source=details.phone_source,
            address_used=address_used,
            missing_reason=None if known else missing_reason(row),
            checked_at=row["contacts_checked_at"],
        ))
    return result


def _advert(row: dict[str, Any]) -> AdvertContact | None:
    if row["kind"] != "advert":
        return None
    return advert_contact(row["description"] or "", company=row["company_name"])


def missing_reason(row: dict[str, Any]) -> str:
    """Why no address is known, from a contact_rows row. Only called when there is none."""
    if row["kind"] == "advert" and applies_on_site_only(row["description"], row["url"]):
        return SITE_ONLY
    website = (row["website"] or "").strip()
    if not website:
        return NO_WEBSITE
    checked, attempted = row["contacts_checked_at"], row["contacts_attempted_at"]
    if checked is None and attempted is None:
        return NOT_CHECKED
    if row["site_unreadable"]:
        return COULD_NOT_READ
    address = contact_service.web_address(website)
    if not (safe_url(address) and is_allowed_url(address)):
        return COULD_NOT_READ
    # An attempt that never finished leaves nothing checked since it started.
    if attempted is not None and (checked is None or checked < attempted):
        return COULD_NOT_READ
    day = checked.astimezone(NZ_TIME).date()
    return f"Checked {day.day} {day:%b} {day.year}: no email on the site"
