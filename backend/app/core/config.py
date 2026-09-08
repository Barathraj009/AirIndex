"""Application settings, loaded from environment variables (see
.env.example at the project root). Uses pydantic-settings, which is not
installed in this offline sandbox — this file is syntax-checked
(py_compile) but not import/execution-verified here; it will run once
`pip install -r requirements.txt` succeeds in an internet-connected
environment."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"

    database_url: str = "postgresql+psycopg2://airindex:changeme@localhost:5432/airindex"

    jwt_secret_key: str = "change-me-in-.env"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7

    cors_allowed_origins: str = "http://localhost:5173"

    api_rate_limit_per_minute: int = 120

    ingestion_schedule_cron: str = "0 */6 * * *"

    scraper_user_agent: str = "AirIndexIndiaBot/1.0"
    scraper_min_delay_seconds: float = 5.0

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
