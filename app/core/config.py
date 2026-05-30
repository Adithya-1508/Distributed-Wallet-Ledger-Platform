from pydantic_settings import BaseSettings, SettingsConfigDict

#Settings  reads DATABASE_URL from the environment /.env and validates it exists at startup.
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str


settings = Settings()