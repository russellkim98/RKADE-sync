"""Logging utilities for the music matcher application."""

import logging
import sys
from typing import Optional

from database import Database


class DatabaseHandler(logging.Handler):
    """Custom logging handler that writes to database."""

    def __init__(self, db: Database, run_id: Optional[int] = None):
        """Initialize database handler.

        Args:
            db: Database instance
            run_id: Optional run ID to associate logs with
        """
        super().__init__()
        self.db = db
        self.run_id = run_id

    def emit(self, record):
        """Write log record to database.

        Args:
            record: Log record to write
        """
        self.db.add_log(
            level=record.levelname, message=self.format(record), run_id=self.run_id
        )


def setup_logging(
    log_file: str, log_level: str, db: Database, run_id: Optional[int] = None
) -> logging.Logger:
    """Set up logging to file, console, and database.

    Args:
        log_file: Path to log file
        log_level: Logging level (DEBUG, INFO, etc.)
        db: Database instance
        run_id: Optional run ID to associate logs with

    Returns:
        Configured logger instance
    """
    # Create logger
    logger = logging.getLogger("music_matcher")
    logger.setLevel(getattr(logging, log_level))
    logger.handlers = []  # Clear any existing handlers

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Create file handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Create database handler
    db_handler = DatabaseHandler(db, run_id)
    db_handler.setFormatter(formatter)
    logger.addHandler(db_handler)

    return logger
