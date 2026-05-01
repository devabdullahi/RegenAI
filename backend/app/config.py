from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Supabase
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""

    # Claude API
    anthropic_api_key: str = ""

    # Resend email
    resend_api_key: str = ""

    # App
    environment: str = "development"
    cors_origins: list[str] = ["http://localhost:3000"]

    @model_validator(mode="after")
    def require_mandatory_secrets(self) -> "Settings":
        mandatory: dict[str, str] = {
            "SUPABASE_URL": self.supabase_url,
            "SUPABASE_ANON_KEY": self.supabase_anon_key,
            "ANTHROPIC_API_KEY": self.anthropic_api_key,
        }
        missing = [name for name, value in mandatory.items() if not value]
        if missing:
            raise ValueError(
                "Missing mandatory secrets — set the following environment variables: "
                + ", ".join(missing)
            )
        return self

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


settings = Settings()
