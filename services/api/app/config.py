from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./clinicpass.db"
    session_secret: str = "local-demo-only"
    public_base_url: str = "http://localhost:8080"
    upload_dir: str = "/tmp/clinicpass-uploads"
    max_upload_bytes: int = 10 * 1024 * 1024
    max_document_pages: int = 6
    max_image_dimension: int = 1800
    image_jpeg_quality: int = 85
    ai_provider: str = "fixture"
    agnes_base_url: str = "https://apihub.agnes-ai.com/v1"
    agnes_model: str = "agnes-2.0-flash"
    agnes_api_key: str = ""
    agnes_timeout_seconds: int = 45
    clinic_assist_url: str = "http://mock-clinic-assist:8090"
    smtp_host: str = "mailpit"
    smtp_port: int = 1025
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
