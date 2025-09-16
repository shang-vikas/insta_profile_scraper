"""
Main pipeline for the Instagram Profile Scraper.

This module orchestrates the entire scraping process, from loading the configuration
to initializing the backend, collecting post URLs, and scraping them in batches.
"""
import pdb
import random
import traceback
from .config import load_config
from .backends import SeleniumBackend
from .logger import get_logger
from pathlib import Path

import sys
import traceback
# import json,sys
from pathlib import Path
logger = get_logger(__name__)

def run_pipeline(config_path: str, dry_run: bool = False):
    """
    Executes the main scraping pipeline.

    This function initializes the configuration, sets up the scraping backend (Selenium),
    navigates to the target profile, collects post URLs, and then scrapes the content
    of those posts in batches. It handles the setup and teardown of the backend
    and logs the overall progress.

    Args:
        config_path: The file path to the TOML configuration file.
        dry_run: A boolean flag (not currently implemented) intended for test runs.

    Returns:
        A dictionary containing the final lists of 'scraped_posts' and 'skipped_posts'.
    """
    config = load_config(config_path)

    backend = SeleniumBackend(config)

    results = {"scraped_posts": [], "skipped_posts": []}

    output_dir = Path(config.data.output_dir)
    output_dir.mkdir(exist_ok=True)

    try:
        backend.start()
        backend.open_profile(config.main.target_profile)

        post_elements = backend.get_post_elements(config.main.num_posts) ## these are hrefs
        if not post_elements:
            logger.warning(
                f"No posts found for profile {config.main.target_profile}. Exiting early."
            )
            return results

        # choose batch size (fixed or random)
        batch_size = config.main.batch_size if not config.main.randomize_batch else random.randint(config.main.batch_size, config.main.batch_size + 4)

        results = backend.scrape_posts_in_batches(
            post_elements,
            batch_size=batch_size,
            save_every=config.main.save_every
        )
        
        logger.info(f"Pipeline completed for profile {config.main.target_profile}.")

    except Exception as e:
        logger.critical(f"Pipeline failed for profile {config.main.target_profile}: {e}")
        logger.debug(traceback.format_exc())
    finally:
        backend.stop()

    return results
