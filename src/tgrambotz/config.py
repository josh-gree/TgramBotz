from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    telegram_token: str
    e2b_api_key: str
    doppler_token: str = ""
    openrouter_api_key: str = ""
    openrouter_model: str = "openrouter/deepseek/deepseek-v4-flash"
    max_turns: int = 20


settings = Settings()
