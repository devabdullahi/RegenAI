from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Supabase
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""

    # LLM provider: DeepSeek (OpenAI-compatible chat completions API)
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-flash"
    llm_max_tokens: int = 4096
    llm_temperature: float = 0.3

    # External data sources
    open_meteo_forecast_url: str = "https://api.open-meteo.com/v1/forecast"
    ssurgo_sda_url: str = "https://sdmdataaccess.sc.egov.usda.gov/Tabular/post.rest"

    # App
    environment: str = "development"
    cors_origins: list[str] = ["http://localhost:3000"]

    @model_validator(mode="after")
    def require_mandatory_secrets(self) -> "Settings":
        mandatory: dict[str, str] = {
            "SUPABASE_URL": self.supabase_url,
            "SUPABASE_ANON_KEY": self.supabase_anon_key,
            "DEEPSEEK_API_KEY": self.deepseek_api_key,
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
