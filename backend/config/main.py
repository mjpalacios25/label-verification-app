from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore',
    )

    MODAL_API_KEY: str = ""
    MODAL_API_URL: str = "https://mjpalacios25--label-verification-app-serve.modal.run/v1"
    MODEL_NAME: str = "Qwen/Qwen3.5-2B-Base"
    HF_TOKEN: str = ""
    DATABASE_URL: str = "sqlite:///./label_verification.db"
    CORS_ALLOWED_ORIGINS: list[str] = ["http://localhost:3000"]


settings = AppSettings()
