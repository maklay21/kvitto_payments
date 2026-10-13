import logging.config
import os
from pathlib import Path


def configure_logging() -> None:
    """Конфигурация логгера с записью в консоль и файл logs/app.log"""

    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "standard": {
                    "format": "%(asctime)s %(levelname)s [%(name)s] %(message)s",
                    "datefmt": "%Y-%m-%dT%H:%M:%S%z",
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "level": level,
                    "formatter": "standard",
                    "stream": "ext://sys.stdout",
                },
                "file": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "level": level,
                    "formatter": "standard",
                    "filename": str(log_dir / "app.log"),
                    "encoding": "utf-8",
                    "mode": "a",
                    "maxBytes": 1_048_576,
                    "backupCount": 5
                },
            },
            "root": {"level": level, "handlers": ["console", "file"]},
        }
    )
