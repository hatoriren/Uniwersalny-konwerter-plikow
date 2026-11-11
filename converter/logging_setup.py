from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

DEFAULT_LOG_PATH = Path(__file__).resolve().parent.parent / "logs" / "converter.log"
_log_path: Path | None = None


def setup_logging(log_file: Path | None = None, verbose: bool = False) -> Path:
    global _log_path

    logger = logging.getLogger("converter")
    if _log_path is not None:
        return _log_path

    log_path = Path(
        os.environ.get("CONVERTER_LOG_FILE") or log_file or DEFAULT_LOG_PATH
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)

    level = logging.DEBUG if verbose else logging.INFO
    logger.setLevel(level)
    logger.propagate = False

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        log_path, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)
    logger.addHandler(file_handler)

    if sys.stderr is not None:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(level)
        logger.addHandler(console_handler)

    logger.debug("Dziennik uruchomiony: %s", log_path)
    _log_path = log_path
    return log_path
