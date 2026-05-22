"""Small import-safe logger configuration for development.

This module configures a named logger. Importing it has no side effects
beyond creating the logger instance.
"""
import logging


def get_logger(name: str = "healthcare") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


logger = get_logger()
