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


def test_empty_values_in_env_files_mean_use_the_default(tmp_path):
    env = tmp_path / ".env"
    env.write_text("OMNIDIM_AGENT_ID=\nMAX_CALLS_PER_MONTH=\nCALLS_ENABLED=\n", encoding="utf-8")

    settings = Settings(_env_file=env)

    assert settings.omnidim_agent_id is None
    assert settings.max_calls_per_month == 5
    assert settings.calls_enabled is False


def test_whatsapp_uses_the_bundled_service_by_default(monkeypatch):
    monkeypatch.delenv("WHATSAPP_SERVICE_URL", raising=False)

    assert Settings(_env_file=None).whatsapp_service_url == "http://127.0.0.1:3010/send"
