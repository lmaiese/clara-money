from pydantic_settings import BaseSettings, SettingsConfigDict

_DEV_JWT_SECRET = "dev-secret-change-in-production"


class Settings(BaseSettings):
    database_url: str = "postgresql://postgres:postgres@localhost:5433/clara_test"
    jwt_secret: str = _DEV_JWT_SECRET
    jwt_algorithm: str = "HS256"
    jwt_expire_days: int = 7
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    claude_model: str = "claude-sonnet-4-6"
    cookie_secure: bool = False
    allowed_origins: list[str] = ["http://localhost:3000"]

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
JWT_SECRET_IS_DEV_DEFAULT = settings.jwt_secret == _DEV_JWT_SECRET
