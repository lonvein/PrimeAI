"""Prepare a unified YOLO dataset for the eight target machinery classes."""

from pathlib import Path

TARGET_CLASSES = [
    "excavator",
    "dump_truck",
    "bulldozer",
    "concrete_mixer",
    "mobile_crane",
    "crane_manipulator",
    "roller",
    "truck",
]


def main() -> None:
    """Print the target ontology; dataset download adapters belong here."""

    print(f"Target classes: {', '.join(TARGET_CLASSES)}")
    print(f"Dataset root: {Path(__file__).parent.resolve()}")


if __name__ == "__main__":
    main()