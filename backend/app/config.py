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

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"

    # Resend email
    resend_api_key: str = ""

    # App
    environment: str = "development"
    cors_origins: list[str] = ["http://localhost:3000"]

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


settings = Settings()
