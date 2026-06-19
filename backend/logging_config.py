import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

COMPONENT_LOGGERS = {
    "chainlit": "music_ai_chat.chainlit",
    "llm": "music_ai_chat.llm",
    "tools": "music_ai_chat.tools",
    "persistence": "music_ai_chat.persistence",
    "api": "music_ai_chat.api",
}

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
_configured = False


def setup_logging(level: str = "INFO", log_file: str | None = None) -> None:
    global _configured
    if _configured:
        return

    log_level = getattr(logging, level.upper(), logging.INFO)
    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    root_logger = logging.getLogger("music_ai_chat")
    root_logger.setLevel(log_level)
    root_logger.propagate = False

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    for component_logger in COMPONENT_LOGGERS.values():
        logging.getLogger(component_logger).setLevel(log_level)

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    _configured = True


def get_logger(component: str) -> logging.Logger:
    logger_name = COMPONENT_LOGGERS.get(component, f"music_ai_chat.{component}")
    return logging.getLogger(logger_name)