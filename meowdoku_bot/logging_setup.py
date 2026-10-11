import logging
import sys
from pathlib import Path

LOGGER_NAME = "meowdoku"
LOG_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
LOG_DATE_FORMAT = "%H:%M:%S"

DEFAULT_LOG_FILE = Path("img/tmp/bot.log")


def setup_logging(verbose: bool = False, log_file: str | Path = DEFAULT_LOG_FILE, 
                  quiet_console: bool = False) -> logging.Logger:

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.DEBUG)

    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)

    destination = Path(log_file)
    destination.parent.mkdir(parents=True, exist_ok=True)

    file_handler = logging.FileHandler(destination, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    logger.addHandler(file_handler)

    if not quiet_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
        console_handler.setFormatter(formatter)

        logger.addHandler(console_handler)

    return logger


def get_logger(suffix: str | None = None) -> logging.Logger:
    if suffix:
        return logging.getLogger(f"{LOGGER_NAME}.{suffix}")

    return logging.getLogger(LOGGER_NAME)
