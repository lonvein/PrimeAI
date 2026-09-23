"""Unit tests for EXIF date extraction utility."""

from datetime import datetime
from io import BytesIO

from PIL import Image

from backend.app.services.exif_utils import extract_photo_date


def test_extract_photo_date_from_filename_patterns() -> None:
    # Pattern 1: IMG_YYYYMMDD_HHMMSS
    dt = extract_photo_date(filename="IMG_20260922_143015.jpg")
    assert dt == datetime(2026, 9, 22, 14, 30, 15)

    # Pattern 2: YYYY-MM-DD_HH-MM-SS
    dt2 = extract_photo_date(filename="Screenshot_2026-10-05_09-15-00.png")
    assert dt2 == datetime(2026, 10, 5, 9, 15, 0)

    # Pattern 3: YYYYMMDD
    dt3 = extract_photo_date(filename="site_20260815.jpg")
    assert dt3 == datetime(2026, 8, 15)

    # Pattern 4: YYYY-MM-DD
    dt4 = extract_photo_date(filename="camera1_2026-11-20.png")
    assert dt4 == datetime(2026, 11, 20)


def test_extract_photo_date_none_when_no_date() -> None:
    dt = extract_photo_date(filename="Screenshot_1.png")
    assert dt is None


def test_extract_photo_date_from_real_exif() -> None:
    # Create an image in memory with real EXIF DateTimeOriginal
    img = Image.new("RGB", (100, 100), color="blue")
    exif = img.getexif()
    # 36867 is DateTimeOriginal tag in EXIF
    exif[36867] = "2026:09:23 11:45:30"
    buffer = BytesIO()
    img.save(buffer, format="JPEG", exif=exif)
    img_bytes = buffer.getvalue()

    extracted = extract_photo_date(image_bytes=img_bytes)
    assert extracted == datetime(2026, 9, 23, 11, 45, 30)
