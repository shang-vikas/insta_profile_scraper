import logging
import sys

def configure_root_logger(level: str = "INFO") -> None:
    """Configure the root logger with handlers and formatting."""
    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        root.addHandler(handler)

    # Apply level to root logger
    level_value = getattr(logging, level.upper(), logging.INFO)
    root.setLevel(level_value)


def get_logger(name: str = "igscraper") -> logging.Logger:
    """Get a named logger that inherits settings from root."""
    return logging.getLogger(name)
