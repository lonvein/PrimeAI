# Build Eye AI

Сервис мониторинга строительной площадки: детекция техники, сопоставление план-факт и explainable-статус этапа СМР.
Дополнительная информация (презентации и тп) - https://disk.360.yandex.ru/d/Vx0tS8GOj1kjqA

## Быстрый запуск через Docker

```powershell
docker compose up --build
```

Откройте веб-интерфейс: `http://localhost:5173`.

Документация API: `http://localhost:8000/docs`.

Остановка:

```powershell
docker compose down
```

Без файла весов YOLO сервис использует синтетическую fallback-детекцию для smoke-теста. Реальные веса следует положить в `ml/weights/`; Compose автоматически передает путь `/app/ml/weights/best_yolo11x_construction.pt` в backend.

## Тесты и линтинг

```powershell
pytest backend/tests
ruff check backend
black --check backend
```
