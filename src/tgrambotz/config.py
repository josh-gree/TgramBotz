from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    telegram_token: str
    webhook_url: str = ""
    e2b_api_key: str = ""
    openrouter_api_key: str = ""
    openrouter_model: str = "anthropic/claude-sonnet-4-5"
    database_url: str = "sqlite+aiosqlite:///./tgrambotz.db"


settings = Settings()
