from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "api-sandbox"
    app_version: str = "0.1.0"
    debug: bool = False
    log_level: str = "INFO"

    database_url: str = "sqlite+aiosqlite:///./api_sandbox.db"
    session_lifetime_days: int = Field(default=30, ge=1, le=3650)

    mock_runtime_image: str = "api-sandbox/mock-runtime:dev"
    mock_network_name: str = "api-sandbox-mocks"
    mock_public_base_url: str = "http://localhost:8080"
    mock_runtime_port: int = Field(default=8080, ge=1, le=65535)
    mock_runtime_memory_limit: str = "128m"
    mock_runtime_cpu_period: int = Field(default=100000, ge=1000)
    mock_runtime_cpu_quota: int = Field(default=50000, ge=1000)
    mock_runtime_healthcheck_timeout_seconds: int = Field(default=45, ge=5, le=300)
    runtime_worker_poll_seconds: float = Field(default=2.0, ge=0.2, le=60)


settings = Settings()
