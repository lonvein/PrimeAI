"""Consistent logging setup for inference and API failures."""

import logging
from backend.app.core.config import get_settings  # Импортируем наши настройки

def configure_logging() -> None:
    """Configure a concise process-wide log format once at startup."""
    
    # 1. Берем настройки (чтобы узнать, включен ли debug в .env)
    settings = get_settings()
    
    # 2. Если debug=True, ставим уровень DEBUG (покажет всё). Если False — INFO (чистый лог)
    log_level = logging.DEBUG if settings.debug else logging.INFO

    # 3. Базовая настройка
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s", 
        # "-8s" выравнивает слова INFO, WARNING, ERROR по ширине, чтобы логи не "скакали"
    )
    
    # Отключаем слишком частые системные логи от сторонних библиотек (например, PIL или matplotlib)
    # чтобы они не забивали консоль вашими ИИ-логами
    logging.getLogger("PIL").setLevel(logging.WARNING)
