from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import (
    BaseSettings,
    EnvSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

BACKEND_DIR = Path(__file__).parents[2]
ENV_FILE = BACKEND_DIR / ".env"

# These names are often set globally for other tools. Using them could bill the wrong account,
# so this app reads them only from backend/.env.
_PROJECT_FILE_ONLY = {
    "anthropic_api_key",
    "google_api_key",
    "tavily_api_key",
    "google_maps_api_key",
}


class _ShellSettings(EnvSettingsSource):
    def get_field_value(self, field, field_name):
        if field_name in _PROJECT_FILE_ONLY:
            return None, field_name, False
        return super().get_field_value(field, field_name)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return init_settings, _ShellSettings(settings_cls), dotenv_settings, file_secret_settings

    database_url: str = ""
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    upload_dir: Path = BACKEND_DIR / "uploads"
    max_upload_mb: int = 5

    # Claude reads the resume and scores jobs.
    anthropic_api_key: SecretStr = SecretStr("")
    resume_model: str = "claude-sonnet-5-5"
    scoring_model: str = "claude-haiku-5-5"
    tailor_model: str = "claude-haiku-5-5"
    # Deep search: Haiku plans, reads and explores; Sonnet writes the pack.
    prep_model: str = "claude-haiku-5-5"
    prep_write_model: str = "claude-sonnet-5-5"
    usd_to_nzd: float = 1.70
    max_prep_places_calls_per_month: int = 1000
    max_ai_scores_per_run: int = 30

    # Gemini embeddings rank jobs before AI scoring.
    google_api_key: SecretStr = SecretStr("")
    embedding_model: str = "gemini-embedding-2"
    embedding_keep_similarity: float = 0.6

    trademe_base_url: str = "https://api.trademe.co.nz"
    trademe_consumer_key: str = ""
    trademe_consumer_secret: SecretStr = SecretStr("")
    trademe_token: str = ""
    trademe_token_secret: SecretStr = SecretStr("")

    # Gmail job alerts, read over IMAP with a Google app password.
    email_enabled: bool = False
    email_address: str = ""
    email_app_password: SecretStr = SecretStr("")
    email_imap_host: str = "imap.gmail.com"
    gmail_alert_query: str = (
        "newer_than:3d (from:seek OR from:linkedin OR from:indeed OR subject:(job alert))"
    )
    max_alert_emails_per_run: int = 15

    google_maps_api_key: SecretStr = SecretStr("")
    tavily_api_key: SecretStr = SecretStr("")
    max_employer_profiles_per_run: int = 10
    max_nearby_searches_per_day: int = 30
    max_discovery_searches_per_run: int = 3
    max_employer_sites_per_run: int = 8

    scheduler_enabled: bool = True
    daily_search_hour: int = 7
