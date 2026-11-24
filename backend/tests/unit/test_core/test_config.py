from app.core.config import Settings


def test_deep_search_settings_have_safe_defaults(monkeypatch):
    for name in ("PREP_MODEL", "PREP_WRITE_MODEL", "USD_TO_NZD", "MAX_PREP_PLACES_CALLS_PER_MONTH"):
        monkeypatch.delenv(name, raising=False)

    settings = Settings(_env_file=None)

    assert settings.prep_model == "claude-haiku-5-5"
    assert settings.prep_write_model == "claude-sonnet-5-5"
    assert settings.usd_to_nzd == 1.70
    assert settings.max_prep_places_calls_per_month == 1000


def test_search_keys_are_read_only_from_the_project_env_file(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "shell-key")
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "shell-key")

    settings = Settings(_env_file=None)

    assert settings.tavily_api_key.get_secret_value() == ""
    assert settings.google_maps_api_key.get_secret_value() == ""
