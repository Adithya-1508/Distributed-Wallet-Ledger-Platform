from pydantic_settings import BaseSettings, SettingsConfigDict

#Settings  reads DATABASE_URL from the environment /.env and validates it exists at startup.
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_expiry_minutes: int = 30


settings = Settings()