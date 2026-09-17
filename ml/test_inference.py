from pathlib import Path
import cv2
from ultralytics import YOLO

# Пути к данным
PHOTOS_DIR = Path("C:\\Data_Science\\PrimeAI\\data\\raw_photos")  # или data/raw_photos, если файлы перенесены


OUTPUT_DIR = Path("ml/output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

WEIGHTS_PATH = Path("backend/models/best.pt")

# Ищем любые изображения (.jpg, .jpeg, .png)
image_paths = list(PHOTOS_DIR.glob("*.[jJ][pP][gG]")) + list(
    PHOTOS_DIR.glob("*.[pP][nN][gG]")
)

if not image_paths:
    # Поиск с рекурсией по подпапкам, если архив был распакован глубже
    image_paths = list(PHOTOS_DIR.rglob("*.[jJ][pP][gG]"))

print(f"Найдено изображений: {len(image_paths)}")

if not image_paths:
    print(
        f"Внимание: папка '{PHOTOS_DIR}' пуста или путь некорректен. Укажите правильный путь к распакованным фото."
    )
    exit(1)

model = YOLO(str(WEIGHTS_PATH))

# Тестируем на первых 3 снимках
for idx, img_path in enumerate(image_paths[:3]):
    print(f"\n[{idx+1}/3] Обработка {img_path.name}...")

    # Инференс с порогом 0.25
    results = model.predict(source=str(img_path), conf=0.25, verbose=False)
    res = results[0]

    detected_classes = [res.names[int(box.cls[0])] for box in res.boxes]
    print(f"Обнаружено объектов: {len(detected_classes)} -> {detected_classes}")

    # Сохраняем визуализацию
    annotated_img = res.plot()
    save_path = OUTPUT_DIR / f"result_{img_path.name}"
    cv2.imwrite(str(save_path), annotated_img)
    print(f"Результат с разметкой сохранен: {save_path.resolve()}")