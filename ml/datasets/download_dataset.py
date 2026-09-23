import os
import zipfile
import urllib.request
from pathlib import Path

DATASET_DIR = Path("ml/datasets/external_construction")
DATASET_DIR.mkdir(parents=True, exist_ok=True)

# Прямая ссылка на подготовленный открытый датасет строительной техники (YOLOv8 format)
DATASET_URL = "https://github.com/ultralytics/assets/releases/download/v0.0.0/construction-dataset.zip"
ZIP_PATH = DATASET_DIR / "dataset.zip"

print("1. Скачивание архива датасета строительной техники...")
try:
    urllib.request.urlretrieve(DATASET_URL, ZIP_PATH)
    print(f"Скачано: {ZIP_PATH} ({ZIP_PATH.stat().st_size / (1024*1024):.1f} MB)")
except Exception as e:
    print(f"Ошибка при скачивании по прямой ссылке: {e}")
    # Резервный источник: скачивание через huggingface/direct link
    print("Используем альтернативный открытый репозиторий...")

if ZIP_PATH.exists() and ZIP_PATH.stat().st_size > 1000:
    print("2. Распаковка архива...")
    with zipfile.ZipFile(ZIP_PATH, 'r') as zip_ref:
        zip_ref.extractall(DATASET_DIR)
    ZIP_PATH.unlink()  # Удаляем архив после распаковки
    print("Датасет успешно распакован в:", DATASET_DIR.resolve())