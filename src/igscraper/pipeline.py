"""
Main pipeline for the Instagram Profile Scraper.

This module orchestrates the entire scraping process, from loading the configuration
to initializing the backend, collecting post URLs, and scraping them in batches.
"""
import os
import copy
import sys
import random
import traceback
from .config import load_config, expand_paths, Config, ProfileTarget
from .backends import SeleniumBackend
from .logger import get_logger
from pathlib import Path

logger = get_logger(__name__)

class Pipeline:
    """
    Orchestrates the entire scraping process.

    This class initializes the backend and configuration, manages the browser
    lifecycle, and iterates through target profiles to scrape them sequentially.
    """

    def __init__(self, config_path: str, dry_run: bool = False):
        """
        Initializes the Pipeline.

        Args:
            config_path: The file path to the TOML configuration file.
            dry_run: A boolean flag for test runs (not currently implemented).
        """
        self.config = load_config(config_path)
        self.dry_run = dry_run
        self.backend = SeleniumBackend(self.config)
        self.all_results = {}

    def _scrape_single_profile(self, profile_target: ProfileTarget) -> dict:
        """
        Handles the scraping logic for a single profile using the shared browser session.

        Args:
            profile_target: The configuration object for the target profile.

        Returns:
            A dictionary containing the scraping results for this profile.
        """
        profile_name = profile_target.name
        num_posts_to_scrape = profile_target.num_posts
        results = {"scraped_posts": [], "skipped_posts": []}

        try:
            # Create a profile-specific config by copying the base and updating it
            profile_config = copy.deepcopy(self.config)
            profile_config.main.target_profile = profile_name # Needed for path expansion

            # Update the backend's config and expand paths for the current profile
            self.backend.config = profile_config 
            substitutions = {"target_profile": profile_name}
            expand_paths(profile_config, substitutions)

            self.backend.open_profile(profile_name)

            post_elements = self.backend.get_post_elements(num_posts_to_scrape)
            if not post_elements:
                logger.warning(f"No new posts to scrape for profile {profile_name}. Skipping.")
                return results

            batch_size = profile_config.main.batch_size
            if profile_config.main.randomize_batch:
                batch_size = random.randint(batch_size, batch_size + 4)

            results = self.backend.scrape_posts_in_batches(
                post_elements, batch_size=batch_size, save_every=profile_config.main.save_every
            )
            logger.info(f"Pipeline completed for profile {profile_name}.")

        except Exception as e:
            logger.critical(f"Pipeline for profile '{profile_name}' failed with an error: {e}")
            logger.debug(traceback.format_exc())
        
        return results

    def _scrape_from_url_file(self) -> dict:
        """
        Handles the scraping logic for a list of URLs provided in a file.

        Returns:
            A dictionary containing the scraping results.
        """
        run_name = self.config.main.run_name_for_url_file
        urls_filepath = self.config.data.urls_filepath
        logger.info(f"--- Starting URL file scrape for run: {run_name} ---")

        # Read URLs from the specified file
        try:
            with open(urls_filepath, "r", encoding="utf-8") as f:
                post_urls = [line.strip() for line in f if line.strip()]
            logger.info(f"Read {len(post_urls)} URLs from {urls_filepath}.")
        except FileNotFoundError:
            logger.error(f"URL file not found at: {urls_filepath}")
            return {}

        # Create a specific config for this run
        run_config = copy.deepcopy(self.config)
        run_config.main.target_profile = run_name # Used for path expansion

        # Update backend config and expand paths
        self.backend.config = run_config
        substitutions = {"target_profile": run_name}
        expand_paths(run_config, substitutions)

        # Filter out already processed URLs
        processed = self.backend._load_processed_urls(run_config.data.metadata_path)
        urls_to_scrape = [u for u in post_urls if u not in processed]
        logger.info(f"Found {len(urls_to_scrape)} new URLs to scrape after filtering.")

        if not urls_to_scrape:
            return {"scraped_posts": [], "skipped_posts": []}

        batch_size = run_config.main.batch_size
        if run_config.main.randomize_batch:
            batch_size = random.randint(batch_size, batch_size + 4)

        return self.backend.scrape_posts_in_batches(urls_to_scrape, batch_size=batch_size, save_every=run_config.main.save_every)

    def run(self) -> dict:
        """
        Executes the main scraping pipeline for all configured target profiles.

        It starts the browser, iterates through each profile, scrapes it, and
        then closes the browser session upon completion.

        Returns:
            A dictionary containing the aggregated results for all profiles.
        """
        try:
            self.backend.start()

            # Check which mode to run in
            if self.config.data.urls_filepath and os.path.exists(self.config.data.urls_filepath):
                # Mode 2: Scrape from a URL file
                run_name = self.config.main.run_name_for_url_file
                self.all_results[run_name] = self._scrape_from_url_file()
            elif self.config.main.target_profiles:
                # Mode 1: Scrape target profiles
                for profile_target in self.config.main.target_profiles:
                    logger.info(f"--- Starting scrape for profile: {profile_target.name} ---")
                    self.all_results[profile_target.name] = self._scrape_single_profile(profile_target)
            else:
                logger.warning("No target profiles or valid URL file provided in the configuration. Nothing to do.")
        except Exception as e:
            logger.critical(f"A critical error occurred during pipeline setup or teardown: {e}")
            logger.debug(traceback.format_exc())
        finally:
            # Stop the backend once after all profiles are processed
            if self.backend:
                self.backend.stop()
                logger.info("Browser has been closed.")

        return self.all_results

def run_pipeline(config_path: str, dry_run: bool = False):
    """Legacy function wrapper to instantiate and run the Pipeline class."""
    pipeline = Pipeline(config_path, dry_run)
    return pipeline.run()