from functools import lru_cache
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    port: int = 8000
    database_url: str = "sqlite:///./clinicpass.db"
    session_secret: str = ""
    public_base_url: str = "http://localhost:8080"
    upload_dir: str = "/tmp/clinicpass-uploads"
    cookie_secure: bool = False
    clinicpass_v2_enabled: bool = True
    csrf_enabled: bool = True
    encryption_key: str = ""
    identity_hmac_key: str = ""
    upload_scanner: str = "deterministic_demo"
    upload_scan_required: bool = True
    retention_days: int = 30
    max_upload_bytes: int = 10 * 1024 * 1024
    max_document_pages: int = 6
    max_image_dimension: int = 1800
    image_jpeg_quality: int = 85
    ai_provider: str = "fixture"
    agnes_base_url: str = "https://apihub.agnes-ai.com/v1"
    agnes_model: str = "agnes-2.0-flash"
    agnes_api_key: str = ""
    agnes_timeout_seconds: int = 45
    clinic_assist_url: str = "http://mock-clinic-assist:8090/api/v1/patients"
    clinic_assist_secret: str = ""
    backend_gateway_secret: str = ""
    smtp_enabled: bool = True
    smtp_host: str = "mailpit"
    smtp_port: int = 1025
    staff_assistant_email: str = "assistant@clinicpass.test"
    staff_assistant_password: str = ""
    staff_manager_email: str = "manager@clinicpass.test"
    staff_manager_password: str = ""
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("database_url")
    @classmethod
    def select_psycopg_driver(cls, value: str) -> str:
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        return value

    @field_validator("clinic_assist_url")
    @classmethod
    def add_internal_http_scheme(cls, value: str) -> str:
        if "://" not in value:
            return f"http://{value}"
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
