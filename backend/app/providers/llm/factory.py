import anthropic
import httpx

from app.core.config import Settings
from app.providers.llm.claude import ClaudeProvider
from app.providers.llm.gemini import Embedder, GeminiEmbedder

REQUEST_TIMEOUT_SECONDS = 90.0


def build_claude(settings: Settings, model: str, effort: str = "low") -> ClaudeProvider | None:
    """Build a client only from this app's key, so no other credential is ever billed."""
    key = settings.anthropic_api_key.get_secret_value()
    if not key:
        return None
    client = anthropic.Anthropic(api_key=key, timeout=REQUEST_TIMEOUT_SECONDS, max_retries=2)
    return ClaudeProvider(client, model, effort=effort)


def build_embedder(settings: Settings, client: httpx.Client) -> Embedder | None:
    key = settings.google_api_key.get_secret_value()
    return GeminiEmbedder(client, key, settings.embedding_model) if key else None
