import os
import shutil
from pathlib import Path
from ultralytics import YOLO

# Пути
# .resolve() превратит относительный путь в абсолютный (начиная с диска C:\)
RAW_PHOTOS_DIR = Path(r"C:\Data_Science\PrimeAI\data\raw_photos")
OUTPUT_DIR = Path(r"C:\Data_Science\PrimeAI\ml\datasets\temp_autolabel")
MODEL_PATH = Path(r"C:\Data_Science\PrimeAI\backend\models\best.pt")

# Метод .resolve() теперь даже не обязателен, так как пути уже жестко прописаны


os.makedirs(OUTPUT_DIR, exist_ok=True)

# Загружаем базовую модель
model = YOLO(str(MODEL_PATH))

# Прогоняем все фото с сохранением .txt разметки
# agnostic_nms=True защитит от явных двойных рамок сразу
results = model.predict(
    source=str(RAW_PHOTOS_DIR),
    conf=0.25,             
    iou=0.45,
    agnostic_nms=True,
    save_txt=True,         # Сохранять аннотации
    save_conf=False,
    save=True,             # <- Полезно: сохранит размеченные фото рядом для проверки
    project=str(OUTPUT_DIR),
    name="labels_run",
    exist_ok=True
)

print(f"Готово! Разметка сохранена в {OUTPUT_DIR}/labels_run/labels")