import logging
import sys


LOG_FORMAT = (
    "%(asctime)s | %(levelname)s | "
    "%(name)s | %(message)s"
)


def setup_logging() -> None:
    """
    Configure application-wide logging.

    Logs are written to the console so they are visible during
    local development and can also be captured by deployment
    platforms.
    """

    logging.basicConfig(
        level=logging.INFO,
        format=LOG_FORMAT,
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
        force=True,
    )


def get_logger(name: str) -> logging.Logger:
    """
    Return a logger for the requested module.
    """

    return logging.getLogger(name)