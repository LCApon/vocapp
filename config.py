from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class Settings(BaseSettings):
    database_url: str
    app_env: str
    schema: str

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,  # DB_HOST and db_host both work
    )

@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
