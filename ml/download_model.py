"""Download and verify lightweight construction machinery detection model.

Target architecture: YOLOv8n / YOLOv8s (<25 MB weights, <2 GB VRAM).
Default model: rangerhkai/ranger-heavy-equipment-detection-model (5.2 MB, 7 construction classes).
"""

from __future__ import annotations

import logging
import sys
import urllib.request
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("download_model")

MODELS_DIR = Path("backend/models")
MODELS_DIR.mkdir(parents=True, exist_ok=True)
TARGET_WEIGHTS = MODELS_DIR / "best.pt"

# Primary source: Lightweight YOLOv8n construction equipment detector (5.2 MB)
PRIMARY_URL = "https://huggingface.co/rangerhkai/ranger-heavy-equipment-detection-model/resolve/main/detect.pt"
FALLBACK_URL = "https://huggingface.co/thalostech2025/thalos-heavy-equipment-v1/resolve/main/heavy_equipment_weights.pt"


def download_weights(target_path: Path = TARGET_WEIGHTS, force: bool = False) -> Path:
    """Download specialized construction YOLO weights and verify integrity."""
    from ultralytics import YOLO  # noqa: PLC0415

    if target_path.exists() and not force:
        # Check if already a specialized model
        try:
            m = YOLO(str(target_path))
            if len(m.names) <= 15:  # specialized domain model
                logger.info(
                    "Specialized model already in place at %s (%d classes: %s)",
                    target_path, len(m.names), list(m.names.values())[:5],
                )
                return target_path
            logger.info("Found generic model (%d classes). Updating to specialized construction model...", len(m.names))
        except Exception as e:
            logger.warning("Existing weights invalid (%s). Re-downloading...", e)

    temp_path = target_path.with_suffix(".tmp.pt")
    urls = [PRIMARY_URL, FALLBACK_URL]

    success = False
    for url in urls:
        logger.info("Downloading specialized weights from: %s", url)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 BuildEyeAI/1.0"})
            with urllib.request.urlopen(req, timeout=60) as resp, open(temp_path, "wb") as f:
                total_bytes = 0
                while chunk := resp.read(65536):
                    f.write(chunk)
                    total_bytes += len(chunk)

            logger.info("Downloaded %.2f MB. Verifying model with Ultralytics...", total_bytes / (1024 * 1024))
            model = YOLO(str(temp_path))
            logger.info("Verification passed! Classes: %s", model.names)

            temp_path.replace(target_path)
            logger.info("Weights deployed to %s (size: %.2f MB)", target_path, target_path.stat().st_size / (1024 * 1024))
            success = True
            break
        except Exception as exc:
            logger.warning("Download from %s failed: %s", url, exc)
            if temp_path.exists():
                temp_path.unlink()

    if not success:
        logger.error("Could not download external model. Falling back to local fine-tuning scaffold.")
        from ml.train import train  # noqa: PLC0415
        deployed = train(data_yaml="ml/datasets/construction.yaml", base_weights="yolov8n.pt", epochs=5, batch_size=4)
        if deployed:
            return deployed
        raise RuntimeError("Failed to obtain specialized construction model weights.")

    return target_path


if __name__ == "__main__":
    force_download = "--force" in sys.argv
    path = download_weights(force=force_download)
    print(f"Model ready: {path.resolve()}")