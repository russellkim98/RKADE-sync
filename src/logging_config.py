"""Logging configuration for the application."""

import logging
import sys


class JupyterFormatter(logging.Formatter):
    """Custom formatter for better Jupyter notebook display"""

    def format(self, record):
        colors = {
            "DEBUG": "\033[36m",  # Cyan
            "INFO": "\033[32m",  # Green
            "WARNING": "\033[33m",  # Yellow
            "ERROR": "\033[31m",  # Red
            "CRITICAL": "\033[35m",  # Magenta
        }
        reset = "\033[0m"

        color = colors.get(record.levelname, "")
        formatted = f"{color}[{record.levelname}]{reset} {record.getMessage()}"

        if record.levelno >= logging.INFO:
            timestamp = self.formatTime(record, "%H:%M:%S")
            formatted = f"{timestamp} - {formatted}"

        return formatted


def setup_logging(level=logging.INFO):
    """Set up the root logger for the application."""
    logger = logging.getLogger()
    logger.setLevel(level)

    # Remove any existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(JupyterFormatter())

    # Create file handler
    file_handler = logging.FileHandler("music_sync.log")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    logger.propagate = False
