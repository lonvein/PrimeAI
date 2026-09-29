"""Environment-backed application settings."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


MODEL_ONNX_PATH: Path = Path("backend/models/best.onnx")
MODEL_PT_PATH: Path = Path("backend/models/best.pt")
YOLO_WEIGHTS: str = str(MODEL_ONNX_PATH if MODEL_ONNX_PATH.exists() else MODEL_PT_PATH)


class Settings(BaseSettings):
    """Runtime settings for API, storage, and model inference."""

    app_name: str = "Build Eye AI"
    debug: bool = True
    # Priority given to ONNX, fallback to .pt if not present.
    # Override via .env: YOLO_WEIGHTS=ml/weights/best_construction.pt
    database_url: str = "sqlite:///./build_eye.db"
    model_onnx_path: Path = MODEL_ONNX_PATH
    model_pt_path: Path = MODEL_PT_PATH
    yolo_weights: Path = Path(YOLO_WEIGHTS)
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