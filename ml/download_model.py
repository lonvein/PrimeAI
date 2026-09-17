"""Скрипт загрузки стартовой модели с Roboflow или тестовой YOLO."""

from pathlib import Path
from ultralytics import YOLO

MODELS_DIR = Path("backend/models")
MODELS_DIR.mkdir(parents=True, exist_ok=True)
TARGET_WEIGHTS = MODELS_DIR / "best.pt"

if not TARGET_WEIGHTS.exists():
    print("Скачивание базовой модели YOLOv8m...")
    # Скачиваем официальную yolov8m как базовый бейзлайн
    model = YOLO("yolov8m.pt")
    # Копируем/сохраняем в backend/models/best.pt для детектора
    model.save(str(TARGET_WEIGHTS))
    print(f"Веса сохранены в: {TARGET_WEIGHTS.resolve()}")
else:
    print(f"Веса уже существуют: {TARGET_WEIGHTS.resolve()}")
    