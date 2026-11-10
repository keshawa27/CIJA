from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "dev"  # "dev" enables /api/docs
    database_url: str = "postgresql+psycopg://cija:cija_dev_only@127.0.0.1:5433/cija"
    secret_key: str  # no default on purpose: the app refuses to start without one
    session_minutes: int = 30
    cookie_secure: bool = True

    smtp_host: str = "127.0.0.1"
    smtp_port: int = 1025
    mail_from: str = "intake@example.com"


settings = Settings()
