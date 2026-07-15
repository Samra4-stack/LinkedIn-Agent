"""
app/utils/logger.py
───────────────────
Structured logging configuration using Loguru.
Provides file rotation, colored console output, and
structured log records for production monitoring.
"""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

from app.config import settings


def setup_logging() -> None:
    """
    Configure Loguru logging for the application.
    - Console: colored, human-readable
    - File: JSON-structured with rotation
    """
    # Remove default handler
    logger.remove()

    # Ensure log directory exists
    log_path = Path(settings.log_file_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # ── Console handler ─────────────────────────────────────
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )
    logger.add(
        sys.stdout,
        format=log_format,
        level=settings.log_level,
        colorize=True,
        backtrace=True,
        diagnose=settings.debug,
    )

    # ── File handler (structured) ────────────────────────────
    logger.add(
        settings.log_file_path,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}",
        level=settings.log_level,
        rotation=settings.log_rotation,
        retention=settings.log_retention,
        compression="zip",
        backtrace=True,
        diagnose=False,  # Disable in file to avoid sensitive data leakage
        enqueue=True,    # Thread-safe async logging
    )

    logger.info(f"Logging initialized | level={settings.log_level} | file={settings.log_file_path}")


def get_logger(name: str):
    """
    Return a contextualized logger instance.

    Usage:
        from app.utils.logger import get_logger
        log = get_logger(__name__)
        log.info("Hello")
    """
    return logger.bind(name=name)
