"""Environment-backed application settings."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for API, storage, and model inference."""

    app_name: str = "Build Eye AI"
    debug: bool = True
    # Default points to the actual file that exists.
    # Override via .env: YOLO_WEIGHTS=ml/weights/best_construction.pt
    database_url: str = "sqlite:///./build_eye.db"
    yolo_weights: Path = Path("backend/models/best.pt")
    yolo_confidence: float = 0.25
    static_dir: Path = Path("backend/static")

    @property
    def raw_dir(self) -> Path:
        p = self.static_dir / "raw"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def annotated_dir(self) -> Path:
        p = self.static_dir / "annotated"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def debug_dir(self) -> Path:
        p = self.static_dir / "debug"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def demo_dir(self) -> Path:
        p = self.static_dir / "demo"
        p.mkdir(parents=True, exist_ok=True)
        return p

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """Return one cached settings instance for the process."""
    settings = Settings()
    # Ensure static subdirectories exist upon initialization
    settings.raw_dir
    settings.annotated_dir
    settings.debug_dir
    settings.demo_dir
    return settings