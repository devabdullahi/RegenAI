from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Supabase
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""

    # Database (direct connection for migrations)
    database_url: str = ""

    # Claude API
    anthropic_api_key: str = ""

    # Resend email
    resend_api_key: str = ""

    # App
    environment: str = "development"
    cors_origins: list[str] = ["http://localhost:3000"]

    @field_validator("supabase_url")
    @classmethod
    def require_supabase_url(cls, v: str) -> str:
        if not v:
            raise ValueError("Missing mandatory secret: SUPABASE_URL must be set")
        return v

    @field_validator("supabase_anon_key")
    @classmethod
    def require_supabase_anon_key(cls, v: str) -> str:
        if not v:
            raise ValueError("Missing mandatory secret: SUPABASE_ANON_KEY must be set")
        return v

    @field_validator("supabase_service_role_key")
    @classmethod
    def require_supabase_service_role_key(cls, v: str) -> str:
        if not v:
            raise ValueError(
                "Missing mandatory secret: SUPABASE_SERVICE_ROLE_KEY must be set"
            )
        return v

    @field_validator("anthropic_api_key")
    @classmethod
    def require_anthropic_api_key(cls, v: str) -> str:
        if not v:
            raise ValueError("Missing mandatory secret: ANTHROPIC_API_KEY must be set")
        return v

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


settings = Settings()
