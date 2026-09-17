"""Consistent logging setup for inference and API failures."""

import logging


def configure_logging() -> None:
    """Configure a concise process-wide log format once at startup."""

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )