"""Environment-backed application settings."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for API, storage, and model inference."""

    app_name: str = "Build Eye AI"
    debug: bool = True
    database_url: str = "sqlite:///./build_eye.db"
    yolo_weights: Path = Path("ml/weights/baseline_yolov8m.pt")
    static_dir: Path = Path("backend/static")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """Return one cached settings instance for the process."""

    return Settings()