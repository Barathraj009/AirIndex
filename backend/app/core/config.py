"""Application settings, loaded from environment variables (see
.env.example at the project root). Uses pydantic-settings, which is not
installed in this offline sandbox — this file is syntax-checked
(py_compile) but not import/execution-verified here; it will run once
`pip install -r requirements.txt` succeeds in an internet-connected
environment."""

from functools import lru_cache

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Make .env values visible to plain os.environ lookups too: some live
# adapters (gds_adapter, kiwi_adapter) read API keys via os.getenv rather
# than through pydantic-settings, and without this their .env keys never
# reach the process.
load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"

    database_url: str = "postgresql+psycopg2://airindex:changeme@localhost:5432/airindex"

    jwt_secret_key: str = "change-me-in-.env"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7

    otp_service_jwt_secret: str = "dev-otp-jwt-secret-change-in-prod"

    cors_allowed_origins: str = "http://localhost:5173"

    api_rate_limit_per_minute: int = 120

    ingestion_schedule_cron: str = "0 */6 * * *"

    scraper_user_agent: str = "AirIndexIndiaBot/1.0"
    scraper_min_delay_seconds: float = 5.0

    # RapidAPI key for the Google Flights fare adapter (gds_adapter).
    rapidapi_key: str = ""
    # google-flights8 returns calendar prices in USD only; the live adapter
    # converts to INR at this reference rate before storing observations.
    fx_rate_usd_inr: float = 90.0

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]

    @property
    def database_url_fixed(self) -> str:
        """Fix Render's postgresql:// to postgresql+psycopg2://"""
        url = self.database_url
        if url.startswith("postgresql://"):
            url = "postgresql+psycopg2://" + url[len("postgresql://"):]
        return url


INSECURE_JWT_SECRETS = {
    "change-me-in-.env",
    "replace-with-a-long-random-value",
    "ci-not-for-production",
    "",
}
INSECURE_OTP_SECRETS = {
    "dev-otp-jwt-secret-change-in-prod",
    "placeholder",
    "",
}


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if settings.environment == "production":
        if settings.jwt_secret_key in INSECURE_JWT_SECRETS:
            raise RuntimeError(
                "Refusing to start in production: JWT_SECRET_KEY is the known/default "
                "value. Set a strong random secret via environment variable."
            )
        if settings.otp_service_jwt_secret in INSECURE_OTP_SECRETS:
            raise RuntimeError(
                "Refusing to start in production: OTP_SERVICE_JWT_SECRET is the "
                "known/default placeholder. Set a strong random secret via "
                "environment variable."
            )
    return settings
