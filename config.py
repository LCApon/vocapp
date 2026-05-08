from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    urlDatabase: str = Field(init=False)
    urlDatabaseLocal: str = Field(init=False)
    envApp: str = Field(init=False)
    schemaDb: str = Field(init=False)
    originsCORS: list = Field(init=False)
    dbNamer: str = Field(init=False)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,  # DB_HOST and db_host both work
    )

settings = Settings()
