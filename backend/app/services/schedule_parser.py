"""
Реализуем парсер, который принимает на вход Excel-файл в виде байтов и 
возвращает список словарей, где каждый словарь представляет собой СТРОКУ из таблицы.
"""

# Необходио для чтения Excel-файлов в памяти, без сохранения на диск
from io import BytesIO 
from typing import Any
import pandas as pd


def parse_schedule(file_bytes: bytes) -> list[dict[str, Any]]:
    """Read the first Excel sheet into JSON-compatible row dictionaries."""

    frame = pd.read_excel(BytesIO(file_bytes))
    # Заменяем все NaN на None, чтобы результат был JSON-совместимым
    frame = frame.where(pd.notna(frame), None)
    
    return frame.to_dict(orient="records")