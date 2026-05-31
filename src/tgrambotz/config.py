from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    telegram_token: str
    e2b_api_key: str
    openrouter_api_key: str = ""
    openrouter_model: str = "anthropic/claude-sonnet-4-5"


settings = Settings()
