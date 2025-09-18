import logging
import sys
import time
from pathlib import Path

def configure_root_logger(level: str = "INFO", log_dir: Path = None) -> None:
    """Configure the root logger with handlers and formatting."""
    root = logging.getLogger()

    # Set level first, so handlers respect it
    level_value = getattr(logging, level.upper(), logging.INFO)
    root.setLevel(level_value)

    if not root.handlers:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        root.addHandler(console_handler)

        # File handler
        if log_dir is None:
            log_dir = Path.cwd()
        
        # Ensure the log directory exists
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"scraper_log_{int(time.time())}.log"
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
        root.info(f"Logging to file: {log_file}")

def get_logger(name: str = "igscraper") -> logging.Logger:
    """Get a named logger that inherits settings from root."""
    return logging.getLogger(name)
