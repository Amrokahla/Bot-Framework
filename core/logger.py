import logging
import os
from datetime import datetime

LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")
os.makedirs(LOG_DIR, exist_ok=True)

def setup_logger(name="bot", level=logging.INFO):
    """Create and configure a logger for consistent formatting."""
    log_file = os.path.join(LOG_DIR, f"{name}_{datetime.now().strftime('%Y-%m-%d')}.log")

    logger = logging.getLogger(name)
    logger.setLevel(level)

    if not logger.handlers:
        # File handler
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(level)

        # Console handler
        ch = logging.StreamHandler()
        ch.setLevel(level)

        # Formatter
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] [%(name)s]: %(message)s",
            "%Y-%m-%d %H:%M:%S"
        )
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)

        # Attach handlers
        logger.addHandler(fh)
        logger.addHandler(ch)

    return logger
