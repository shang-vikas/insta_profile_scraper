import toml
from pydantic import Field, ValidationError, BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, Callable, Any, List
from src.igscraper.logger import configure_root_logger, get_logger
from pathlib import Path
import logging

PROJECT_ROOT = Path.cwd()  # since you always start in root
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("selenium.webdriver.remote").setLevel(logging.INFO)

def resolve_path(path_str: str) -> Path:
    """
    Resolves a string path into an absolute Path object.

    If the path is relative, it is resolved against the project's root directory.
    If it's already absolute, it's returned as is.

    Args:
        path_str: The path string from the configuration file.

    Returns:
        An absolute Path object.
    """
    path = Path(path_str)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()

def expand_paths(section, substitutions: dict) -> None:
    """
    Recursively expands placeholders and resolves paths for string fields in a config section.

    This function modifies the Pydantic model object in-place. It iterates through
    the fields of a settings object. If a field is a string containing placeholders
    (e.g., "{target_profile}"), it formats the string using the `substitutions`
    dictionary and then resolves it to an absolute path. It also recurses into
    nested Pydantic models.

    Args:
        section: A Pydantic BaseSettings object to process.
        substitutions: A dictionary of key-value pairs for placeholder expansion.
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

class ProfileTarget(BaseModel):
    """Represents a single profile to be scraped."""
    name: str
    num_posts: int = Field(..., gt=0)

class MainConfig(BaseSettings):
    """
    Configuration settings related to the main application logic and scraping behavior.
    """
    # --- Scraping Mode ---
    # To scrape profiles (can be empty if using urls_filepath)
    target_profiles: List[ProfileTarget] = []
    # A name for the run when scraping from a URL file.
    run_name_for_url_file: str = "url_file_run"
    # Internal field for the currently processed profile, not for user config.
    target_profile: Optional[str] = None
    # If True, runs the browser in headless mode (no GUI).
    headless: bool = True
    # Minimum random delay (in seconds) between batches of requests.
    rate_limit_seconds_min: int = 2
    # Maximum random delay (in seconds) between batches of requests.
    rate_limit_seconds_max: int = 5
    # General-purpose retry count for various operations.
    max_retries: int = 3
    # Number of posts to open and scrape in a single batch.
    batch_size: int = 4
    # If True, the batch size will be randomized slightly to appear more human.
    randomize_batch: bool = False
    # Optional user-agent string for the browser.
    user_agent: Optional[str] = None
    # Duration (in seconds) for the simulated human mouse movement.
    human_mouse_move_duration: float = 0.5
    # Number of retries when scrolling the main profile page if no new content loads.
    page_scroll_retries: int = 3
    # Save scraped data to the final file after every N posts.
    save_every: int = 5
    # Number of retries when scrolling comments if no new content loads.
    comments_scroll_retries: int = 1
    # Number of scroll steps to perform when collecting comments.
    comment_scroll_steps: int = 30

    # Credentials can be loaded from env vars (e.g., IGSCRAPER_USERNAME)
    # The alias allows the TOML file to use 'instagram_username'.
    username: Optional[str] = Field(None, alias='instagram_username')
    password: Optional[str] = Field(None, alias='instagram_password')

class DataConfig(BaseSettings):
    """Configuration settings related to file paths and data storage."""
    # Directory where all output files will be stored.
    output_dir: str = "outputs"
    # Optional: Path to a file containing post URLs to scrape, one per line.
    urls_filepath: Optional[str] = None
    # Path to the file for storing collected post URLs. Supports placeholders.
    posts_path: str
    # Path to the final JSONL file for storing scraped post metadata. Supports placeholders.
    metadata_path: str
    # Path to the file for logging URLs of skipped posts. Supports placeholders.
    skipped_path: str
    # Path to the temporary file for intermediate scrape results. Supports placeholders.
    tmp_path: str
    # Path to the browser cookie file for authentication.
    cookie_file: str

class LoggingConfig(BaseSettings):
    """Configuration settings for logging."""
    # The logging level (e.g., "DEBUG", "INFO", "WARNING").
    level: str

class Config(BaseSettings):
    """
    The main configuration model that aggregates all other configuration sections.

    It is configured to load environment variables with the prefix "IGSCRAPER_".
    """
    model_config = SettingsConfigDict(env_prefix="IGSCRAPER_", case_sensitive=False)

    main: MainConfig
    data: DataConfig
    logging: LoggingConfig

def load_config(path: str) -> Config:
    """
    Loads configuration from a TOML file, sets up logging, and processes paths.

    Args:
        path: The path to the TOML configuration file.

    Returns:
        A fully validated and processed Config object.
    """
    with open(path, "r") as f:
        data = toml.load(f)

    # Configure logging once, using logging level from TOML
    if "logging" in data and "level" in data["logging"]:
        configure_root_logger(data["logging"]["level"])
    else:
        configure_root_logger("INFO")
    logger = get_logger("config")
    logger.debug("Configuration loaded successfully")
    
    # Return the config object without path expansion.
    # Path expansion will be handled per-profile in the pipeline.
    return Config(**data)
