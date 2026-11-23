import httpx

from app.core.config import Settings
from app.providers.jobs.base import JobSource
from app.providers.jobs.example import ExampleJobSource
from app.providers.jobs.trademe import TradeMeSource


def build_sources(settings: Settings, client: httpx.Client) -> list[JobSource]:
    """Use real sources that have keys. Example jobs appear only when none do."""
    secret = settings.trademe_consumer_secret.get_secret_value()
    if settings.trademe_consumer_key and secret:
        return [
            TradeMeSource(
                client,
                consumer_key=settings.trademe_consumer_key,
                consumer_secret=secret,
                token=settings.trademe_token or None,
                token_secret=settings.trademe_token_secret.get_secret_value() or None,
                base_url=settings.trademe_base_url,
            )
        ]
    return [ExampleJobSource()]
