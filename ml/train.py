"""Fine-tuning pipeline for construction site machinery detection using Ultralytics YOLO.

Target ontology (8 classes):
0: excavator
1: dump_truck
2: bulldozer
3: concrete_mixer
4: mobile_crane
5: crane_manipulator
6: roller
7: truck
"""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("train")


def check_environment() -> dict[str, str | bool]:
    """Check PyTorch, CUDA, and GPU availability."""
    import torch  # noqa: PLC0415

    has_cuda = torch.cuda.is_available()
    gpu_name = torch.cuda.get_device_name(0) if has_cuda else "N/A (CPU only)"
    device_count = torch.cuda.device_count() if has_cuda else 0

    info = {
        "pytorch_version": torch.__version__,
        "cuda_available": has_cuda,
        "gpu_name": gpu_name,
        "device_count": str(device_count),
    }
    logger.info("Environment check: %s", info)
    return info


def generate_default_data_yaml(output_path: Path, dataset_dir: Path) -> Path:
    """Create a default data.yaml file if none exists."""
    content = f"""# Ultralytics YOLO format for Build Eye AI Construction Machinery
path: {dataset_dir.as_posix()}
train: images/train
val: images/val
test: images/test

names:
  0: excavator
  1: dump_truck
  2: bulldozer
  3: concrete_mixer
  4: mobile_crane
  5: crane_manipulator
  6: roller
  7: truck
"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    logger.info("Created dataset config at: %s", output_path)
    return output_path


def train(
    data_yaml: str | Path,
    base_weights: str | Path = "yolov8m.pt",
    epochs: int = 50,
    batch_size: int = 16,
    img_size: int = 640,
    device: str | int = 0,
    project: str | Path = "ml/runs",
    name: str = "construction_yolov8m",
) -> Path | None:
    """Run YOLO fine-tuning on construction site dataset."""
    from ultralytics import YOLO  # noqa: PLC0415

    data_path = Path(data_yaml)
    if not data_path.is_file():
        logger.error("Dataset YAML not found at: %s", data_path)
        return None

    weights_path = Path(base_weights)
    if not weights_path.is_file():
        logger.warning("Base weights %s not found locally; Ultralytics will auto-download.", weights_path)

    logger.info("Initializing YOLO model with base weights: %s", base_weights)
    model = YOLO(str(base_weights))

    logger.info(
        "Starting training: epochs=%d, batch=%d, imgsz=%d, device=%s",
        epochs, batch_size, img_size, device,
    )

    results = model.train(
        data=str(data_path),
        epochs=epochs,
        batch=batch_size,
        imgsz=img_size,
        device=device,
        project=str(project),
        name=name,
        # Augmentations suitable for high-angle / mast construction cameras:
        degrees=10.0,
        fliplr=0.5,
        mosaic=1.0,
        mixup=0.1,
        save=True,
        verbose=True,
    )

    best_pt = Path(project) / name / "weights" / "best.pt"
    if best_pt.is_file():
        logger.info("Training complete! Best weights saved to: %s", best_pt)
        # Copy to backend/models for immediate API availability
        target_dir = Path("backend/models")
        target_dir.mkdir(parents=True, exist_ok=True)
        deployed_pt = target_dir / "best_construction.pt"
        shutil.copy2(best_pt, deployed_pt)
        logger.info("Deployed weights to: %s", deployed_pt)
        return deployed_pt

    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Fine-tune YOLO for construction machinery.")
    parser.add_argument("--data", type=str, default="ml/datasets/construction.yaml", help="Path to data.yaml")
    parser.add_argument("--weights", type=str, default="yolov8m.pt", help="Pretrained weights checkpoint")
    parser.add_argument("--epochs", type=int, default=50, help="Number of training epochs")
    parser.add_argument("--batch", type=int, default=16, help="Batch size")
    parser.add_argument("--imgsz", type=int, default=640, help="Image size")
    parser.add_argument("--device", type=str, default="0", help="CUDA device index or 'cpu'")
    parser.add_argument("--dry-run", action="store_true", help="Check environment and paths without training")

    args = parser.parse_args()

    env_info = check_environment()

    if args.dry_run:
        logger.info("Dry-run complete. Environment is ready for training.")
        if not Path(args.data).exists():
            logger.info("Generating template data.yaml...")
            generate_default_data_yaml(Path(args.data), Path("ml/datasets"))
        sys.exit(0)

    train(
        data_yaml=args.data,
        base_weights=args.weights,
        epochs=args.epochs,
        batch_size=args.batch,
        img_size=args.imgsz,
        device=args.device if env_info["cuda_available"] else "cpu",
    )


if __name__ == "__main__":
    main()