"""Chooses which job sources a search run uses."""

from collections.abc import Sequence

import httpx

from app.chains.alert_chain import AlertExtractChain
from app.chains.careers_chain import CareersPageChain
from app.chains.company_summary_chain import CompanySummaryChain
from app.core.config import Settings
from app.providers.company.places import PlacesClient
from app.providers.company.website_reader import WebsiteReader
from app.providers.jobs.ats import BoardSource
from app.providers.jobs.base import JobSource, UnavailableSource
from app.providers.jobs.employer_sites import EmployerSitesSource, SiteEmployer
from app.providers.jobs.example import ExampleJobSource
from app.providers.jobs.gmail_alerts import GmailAlertsSource, ImapMailReader
from app.providers.jobs.trademe import TradeMeSource
from app.providers.llm.factory import build_claude
from app.providers.search.tavily import TavilySearch
from app.schemas.resume import BoardEntry
from app.services.enrich_service import EmployerTools


def build_sources(
    settings: Settings,
    client: httpx.Client,
    boards: list[BoardEntry],
    use_examples: bool,
    employers: Sequence[SiteEmployer] = (),
) -> list[JobSource]:
    """Real sources first. Example jobs appear only for the example profile with no sources."""
    sources: list[JobSource] = [BoardSource(client, board) for board in boards]

    secret = settings.trademe_consumer_secret.get_secret_value()
    if settings.trademe_consumer_key and secret:
        sources.append(
            TradeMeSource(
                client,
                consumer_key=settings.trademe_consumer_key,
                consumer_secret=secret,
                token=settings.trademe_token or None,
                token_secret=settings.trademe_token_secret.get_secret_value() or None,
                base_url=settings.trademe_base_url,
            )
        )

    email_password = settings.email_app_password.get_secret_value()
    if settings.email_enabled and settings.email_address and email_password:
        llm = build_claude(settings, settings.scoring_model, effort="low")
        if llm:
            mail = ImapMailReader(
                settings.email_address, email_password, host=settings.email_imap_host
            )
            sources.append(
                GmailAlertsSource(
                    mail,
                    AlertExtractChain(llm).run,
                    settings.gmail_alert_query,
                    settings.max_alert_emails_per_run,
                )
            )
        else:
            sources.append(
                UnavailableSource("gmail_alert", "reading alert emails needs a Claude key")
            )

    if employers:
        llm = build_claude(settings, settings.scoring_model, effort="low")
        extract = CareersPageChain(llm).run if llm else None
        sources.append(
            EmployerSitesSource(client, WebsiteReader(client), extract, list(employers))
        )

    if not sources and use_examples:
        return [ExampleJobSource()]
    return sources


def build_places(settings: Settings, client: httpx.Client) -> PlacesClient | None:
    key = settings.google_maps_api_key.get_secret_value()
    return PlacesClient(client, key) if key else None


def build_employer_tools(settings: Settings, client: httpx.Client) -> EmployerTools | None:
    """Only tools with keys. Website text is read only when AI can summarise it."""
    maps_key = settings.google_maps_api_key.get_secret_value()
    tavily_key = settings.tavily_api_key.get_secret_value()
    llm = build_claude(settings, settings.scoring_model, effort="low")
    summary = CompanySummaryChain(llm) if llm else None
    if not (maps_key or tavily_key or summary):
        return None
    return EmployerTools(
        places=PlacesClient(client, maps_key) if maps_key else None,
        reader=WebsiteReader(client) if summary else None,
        search=TavilySearch(client, tavily_key) if tavily_key else None,
        summary=summary,
    )
