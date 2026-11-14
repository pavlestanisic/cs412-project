"""
Logging setup for the whole app.

We use Python's built-in `logging` module (no external package).
Every module gets its own logger with `get_logger(__name__)`,
and `setup_logging()` is called ONCE at program start (in main.py).
"""

import logging

# One shared format for every log line: time, level, module name, message.
LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"

# The name of our top level logger. All app loggers live below it ("delivery.xxx").
APP_LOGGER_NAME = "delivery"


def get_logger(name):
    """Return a logger for one module. Pass `__name__` as the name."""
    return logging.getLogger(name)


def setup_logging(level="INFO", log_file=None, to_console=False):
    """
    Configure the app logger.

    level      -- text level like "DEBUG", "INFO", "WARNING".
    log_file   -- path of a file to write logs into (None = no file).
    to_console -- True = also print logs on the screen (stderr).

    Returns the configured app logger.
    """
    logger = logging.getLogger(APP_LOGGER_NAME)

    # Turn the text level ("INFO") into the logging number (20).
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove old handlers so calling this twice does not double the logs.
    for old_handler in list(logger.handlers):
        logger.removeHandler(old_handler)
        old_handler.close()

    formatter = logging.Formatter(LOG_FORMAT)

    if log_file:
        # Write logs into a file (append mode keeps older runs).
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    if to_console:
        # Print logs on stderr so they do not mix with normal app output.
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    if not logger.handlers:
        # No target chosen: swallow logs silently instead of warning.
        logger.addHandler(logging.NullHandler())

    return logger
