"""Extract photo date from EXIF metadata or file modification time.

Supports JPEG, PNG (limited), TIFF, HEIF images.
Falls back to file modification date if EXIF is not available.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from io import BytesIO
from pathlib import Path

logger = logging.getLogger(__name__)


def extract_photo_date(
    image_bytes: bytes | None = None,
    filename: str | None = None,
) -> datetime | None:
    """Try to extract the capture date from a photo.

    Strategy (in priority order):
    1. EXIF DateTimeOriginal / DateTimeDigitized / DateTime.
    2. Filename pattern matching (e.g. "IMG_20260922_1430.jpg").
    3. None (caller should use current datetime).
    """
    # --- Strategy 1: EXIF ---
    if image_bytes:
        exif_date = _extract_exif_date(image_bytes)
        if exif_date:
            logger.debug("Photo date from EXIF: %s", exif_date)
            return exif_date

    # --- Strategy 2: Filename pattern ---
    if filename:
        filename_date = _extract_filename_date(filename)
        if filename_date:
            logger.debug("Photo date from filename: %s", filename_date)
            return filename_date

    return None


def _extract_exif_date(image_bytes: bytes) -> datetime | None:
    """Extract date from EXIF metadata using Pillow."""
    try:
        from PIL import Image  # noqa: PLC0415
        from PIL.ExifTags import TAGS  # noqa: PLC0415

        img = Image.open(BytesIO(image_bytes))
        exif_data = img._getexif()
        if not exif_data:
            return None

        # Priority: DateTimeOriginal (36867) > DateTimeDigitized (36868) > DateTime (306)
        for tag_id in (36867, 36868, 306):
            value = exif_data.get(tag_id)
            if value:
                return _parse_exif_datetime(value)
    except Exception as exc:
        logger.debug("EXIF extraction failed: %s", exc)
    return None


def _parse_exif_datetime(value: str) -> datetime | None:
    """Parse EXIF datetime string: 'YYYY:MM:DD HH:MM:SS'."""
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y:%m:%d"):
        try:
            return datetime.strptime(str(value).strip(), fmt)
        except ValueError:
            continue
    return None


# Common filename date patterns.
_FILENAME_PATTERNS = [
    # IMG_20260922_143015.jpg or Screenshot_20260922-143015.png
    re.compile(r"(\d{4})(\d{2})(\d{2})[_-](\d{2})(\d{2})(\d{2})"),
    # 2026-09-22_14-30-15.jpg
    re.compile(r"(\d{4})-(\d{2})-(\d{2})[_T](\d{2})-(\d{2})-(\d{2})"),
    # 20260922.jpg
    re.compile(r"(\d{4})(\d{2})(\d{2})"),
    # 2026-09-22.jpg
    re.compile(r"(\d{4})-(\d{2})-(\d{2})"),
]


def _extract_filename_date(filename: str) -> datetime | None:
    """Try to parse a date from the filename."""
    stem = Path(filename).stem
    for pattern in _FILENAME_PATTERNS:
        match = pattern.search(stem)
        if match:
            groups = match.groups()
            try:
                if len(groups) >= 6:
                    return datetime(
                        int(groups[0]), int(groups[1]), int(groups[2]),
                        int(groups[3]), int(groups[4]), int(groups[5]),
                    )
                elif len(groups) >= 3:
                    return datetime(int(groups[0]), int(groups[1]), int(groups[2]))
            except ValueError:
                continue
    return None
