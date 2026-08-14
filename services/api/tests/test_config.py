from app.config import Settings
from app.runtime import commands, migrate


def test_render_postgres_url_selects_installed_psycopg_driver():
    settings = Settings(database_url="postgresql://user:password@database.internal/clinicpass")
    assert settings.database_url == "postgresql+psycopg://user:password@database.internal/clinicpass"


def test_render_service_reference_gets_internal_http_scheme():
    settings = Settings(clinic_assist_url="clinicpass-mock:8090")
    assert settings.clinic_assist_url == "http://clinicpass-mock:8090"


def test_runtime_commands_share_the_configured_port(monkeypatch):
    monkeypatch.setenv("PORT", "9123")
    from app.config import get_settings

    get_settings.cache_clear()
    try:
        runtime_commands = commands()
        assert runtime_commands[0][-1] == "9123"
        assert runtime_commands[1][-1] == "app.worker"
    finally:
        get_settings.cache_clear()


def test_runtime_applies_migrations_before_starting_processes(monkeypatch):
    calls = []
    monkeypatch.setattr("app.runtime.subprocess.run", lambda command, check: calls.append((command, check)))
    migrate()
    assert calls[0][0][-3:] == ["alembic", "upgrade", "head"]
    assert calls[0][1] is True
