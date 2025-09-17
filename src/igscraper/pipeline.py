"""
Main pipeline for the Instagram Profile Scraper.

This module orchestrates the entire scraping process, from loading the configuration
to initializing the backend, collecting post URLs, and scraping them in batches.
"""
import copy, sys
import random
import traceback
from .config import load_config,expand_paths
from .backends import SeleniumBackend
from .logger import get_logger
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

    all_results = {}

    # Initialize backend once, outside the loop
    # We use a placeholder config first, it will be updated for each profile.
    backend = SeleniumBackend(config)

    try:
        backend.start()

        for profile_target in config.main.target_profiles:
            profile_name = profile_target.name
            num_posts_to_scrape = profile_target.num_posts
            logger.info(f"--- Starting pipeline for profile: {profile_name} ---")

            # Create a deep copy of the config to make it profile-specific
            profile_config = copy.deepcopy(config)
            
            # Temporarily set single profile info for path expansion and backend logic
            profile_config.main.target_profile = profile_name
            profile_config.main.num_posts = num_posts_to_scrape
            
            # Update the backend's config to the profile-specific one
            backend.config = profile_config
            
            # Expand paths with the current profile name. This must be done
            # after the backend's config is updated.
            substitutions = {"target_profile": backend.config.main.target_profile}
            expand_paths(profile_config, substitutions)

            results = {"scraped_posts": [], "skipped_posts": []}
            try:
                backend.open_profile(profile_name)

                post_elements = backend.get_post_elements(num_posts_to_scrape)
                if not post_elements:
                    logger.warning(f"No new posts to scrape for profile {profile_name}. Skipping.")
                    all_results[profile_name] = results
                    continue

                batch_size = profile_config.main.batch_size
                if profile_config.main.randomize_batch:
                    batch_size = random.randint(batch_size, batch_size + 4)

                results = backend.scrape_posts_in_batches(
                    post_elements,
                    batch_size=batch_size,
                    save_every=profile_config.main.save_every
                )
                
                logger.info(f"Pipeline completed for profile {profile_name}.")

            except Exception as e:
                logger.critical(f"Pipeline for profile '{profile_name}' failed with an error: {e}")
                logger.debug(traceback.format_exc())
            finally:
                all_results[profile_name] = results
            
    except Exception as e:
        logger.critical(f"A critical error occurred outside the profile loop: {e}")
        logger.debug(traceback.format_exc())
    finally:
        # Stop the backend once after all profiles are processed
        if backend:
            backend.stop()
            logger.info("Browser has been closed.")
    return all_results