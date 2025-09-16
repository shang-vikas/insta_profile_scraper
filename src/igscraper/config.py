import toml
from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, Callable, Any
from src.igscraper.logger import configure_root_logger, get_logger
from pathlib import Path
import logging

PROJECT_ROOT = Path.cwd()  # since you always start in root
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("selenium.webdriver.remote").setLevel(logging.INFO)

def resolve_path(path_str: str) -> Path:
    """Resolve a path from config into an absolute Path."""
    path = Path(path_str)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()

def expand_paths(section, substitutions: dict) -> None:
    """
    Recursively expand placeholders and resolve paths for string fields in a section.
    Modifies the section object in-place.
    """
    for field, value in section.__dict__.items():
        if isinstance(value, str):
            # Expand placeholders if present
            if "{" in value and "}" in value:
                expanded = value.format(**substitutions)
                # Make it absolute
                setattr(section, field, str(resolve_path(expanded)))
        elif isinstance(value, BaseSettings):
            # Recurse into nested models (like DataConfig, MainConfig)
            expand_paths(value, substitutions)

class MainConfig(BaseSettings):
    """
    Application configuration model.
    Loads settings from a TOML file and overrides with environment variables.
    """
    target_profile: str
    num_posts: int = Field(..., gt=0)
    headless: bool = True
    rate_limit_seconds_min: int = 2
    rate_limit_seconds_max: int = 5
    max_retries: int = 3
    batch_size: int = 4
    randomize_batch: bool = False
    user_agent: Optional[str] = None
    human_mouse_move_duration: float = 0.5
    page_scroll_retries: int = 3
    save_every: int = 5
    comments_scroll_retries: int = 1
    comment_scroll_steps: int = 15

    # Credentials can be loaded from env vars (e.g., IGSCRAPER_USERNAME)
    # The alias allows the TOML file to use 'instagram_username'.
    username: Optional[str] = Field(None, alias='instagram_username')
    password: Optional[str] = Field(None, alias='instagram_password')

class DataConfig(BaseSettings):
    posts_path: str
    metadata_path: str
    output_dir: str = "outputs"
    skipped_path: str
    tmp_path: str
    cookie_file: str

class LoggingConfig(BaseSettings):
    level: str

class Config(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="IGSCRAPER_", case_sensitive=False)

    main: MainConfig
    data: DataConfig
    logging: LoggingConfig

def load_config(path: str) -> Config:
    """Load configuration from TOML file and merge with environment variables."""
    with open(path, "r") as f:
        data = toml.load(f)
    # Normalize paths in config

    for key, value in data["data"].items():
        data["data"][key] = str(resolve_path(value))

    # Configure logging once, using logging level from TOML
    if "logging" in data and "level" in data["logging"]:
        configure_root_logger(data["logging"]["level"])
    else:
        configure_root_logger("INFO")

    # Create logger for config
    logger = get_logger("config")
    logger.debug("Configuration loaded successfully")
    config = Config(**data)

    # Expand and normalize all paths in one go
    substitutions = {"target_profile": config.main.target_profile}
    expand_paths(config, substitutions)

    return config

