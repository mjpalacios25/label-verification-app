from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore',
    )

    MODAL_API_KEY: str = ""
    MODAL_API_URL: str = ""
    MODEL_NAME: str = ""
    HF_TOKEN: str = ""
    DATABASE_URL: str = "sqlite:///./label_verification.db"
    CORS_ALLOWED_ORIGINS: list[str] = ["http://localhost:3000"]


settings = AppSettings()
