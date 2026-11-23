from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    database_url: str = ""
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    trademe_base_url: str = "https://api.trademe.co.nz"
    trademe_consumer_key: str = ""
    trademe_consumer_secret: SecretStr = SecretStr("")
    trademe_token: str = ""
    trademe_token_secret: SecretStr = SecretStr("")
