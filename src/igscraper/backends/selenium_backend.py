import os
import sys
import time
import json
import pickle
import random
import traceback
from typing import Iterator, Dict, List, Any

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException

from webdriver_manager.chrome import ChromeDriverManager

from .base_backend import Backend
from ..pages.profile_page import ProfilePage
from ..logger import get_logger

from src.igscraper.chrome import patch_driver
from src.igscraper.utils import (
    human_mouse_move,
    images_from_post,
    get_section_with_highest_likes,
    scrape_comments_with_gif,
    save_intermediate,
    save_scrape_results,
    clear_tmp_file,
    random_delay,
)


logger = get_logger(__name__)

class SeleniumBackend(Backend):
    """
    A backend implementation using Selenium to control a web browser for scraping.

    This class manages the browser lifecycle, navigation, and data extraction
    by interacting with web pages and executing JavaScript.
    """
    def __init__(self, config):
        """
        Initializes the SeleniumBackend.

        Args:
            config: The application's configuration object.
        """
        self.config = config
        self.driver = None
        self.profile_page = None

    def start(self):
        """
        Starts the Selenium WebDriver, configures it for stealth, and logs in.

        - Sets up Chrome options to evade bot detection.
        - Initializes the Chrome driver using webdriver-manager.
        - Patches the driver to monitor for suspicious navigation.
        - Logs in using cookies specified in the configuration.
        - Initializes the ProfilePage object for page interactions.
        """
        options = Options()

        # --- Anti-detection settings from test_sel.py ---
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)

        # Human-like settings
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--start-maximized")

        # Use user_agent from config or a default one
        user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
        options.add_argument(f'user-agent={user_agent}')

        if self.config.main.headless:
            options.add_argument("--headless=new")

        # Use WebDriver Manager for automatic driver management
        try:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
            self.driver = patch_driver(self.driver)
        except Exception as e:
            logger.error(f"Failed to initialize Chrome driver with webdriver-manager: {e}")
            logger.info("Falling back to default webdriver initialization.")
            self.driver = webdriver.Chrome(options=options)
            ## Patch driver to stop the script if detection happens and we are rerouted to a captcha page
            self.driver = patch_driver(self.driver)

        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        self._login_with_cookies()

        self.profile_page = ProfilePage(self.driver, self.config)

    def _login_with_cookies(self):
        """
        Loads cookies from a file to authenticate the browser session.

        The browser must first navigate to the domain ('instagram.com') before
        cookies can be added. The path to the cookie file is read from the
        configuration. If the file doesn't exist, the program will exit.
        """
        if not self.config.data.cookie_file or not os.path.exists(self.config.data.cookie_file):
            logger.info("No cookie file specified in config or cookie file does not exist. Exiting early.")
            sys.exit(1)

        logger.info(f"Attempting to log in using cookies from {self.config.data.cookie_file}")
        self.driver.get("https://www.instagram.com/")  # Must visit domain first

        try:
            with open(self.config.data.cookie_file, "rb") as f:
                cookies = pickle.load(f)
        except (pickle.UnpicklingError, EOFError) as e:
            logger.error(f"Could not load cookies from {self.config.data.cookie_file}. Error: {e}")
            return

        for cookie in cookies:
            # Selenium expects 'expiry' to be int if present
            if 'expiry' in cookie and isinstance(cookie['expiry'], float):
                cookie['expiry'] = int(cookie['expiry'])
            self.driver.add_cookie(cookie)

        self.driver.refresh()  # Apply cookies
        logger.info("✅ Successfully logged in using cookies.")
        time.sleep(3) # Wait a bit for page to settle

    def stop(self):
        """Quits the WebDriver and closes all associated browser windows."""
        if self.driver:
            self.driver.quit()

    def open_profile(self, profile_handle: str) -> None:
        """
        Navigates the browser to a specific Instagram profile page.

        Args:
            profile_handle: The Instagram username of the profile to open.
        """
        self.profile_page.navigate_to_profile(profile_handle)

    def _load_cached_urls(self, file_path: str) -> list[str] | None:
        """
        Loads a list of post URLs from a local JSON file if it exists.

        Args:
            file_path: The path to the JSON file containing post URLs.

        Returns:
            A list of URL strings if the file is found and loaded, otherwise None.
        """
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                urls = json.load(f)
            logger.info(f"Loaded {len(urls)} post URLs from {file_path}.")
            return urls
        return None

    def _save_urls(self, profile: str, urls: list[str], file_path: str) -> None:
        """
        Saves a list of post URLs to a local JSON file.

        Args:
            profile: The target profile name (used for logging).
            urls: A list of URL strings to save.
            file_path: The path where the JSON file will be saved.
        """
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(urls, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved {len(urls)} post URLs to {file_path}.")

    def _load_processed_urls(self, file_path: str) -> set[str]:
        """
        Loads URLs of already scraped posts from the output metadata file.

        This is used to avoid re-scraping posts that have already been processed
        in previous runs.

        Args:
            file_path: The path to the JSONL metadata output file.

        Returns:
            A set of post URL strings that have already been processed.
        """
        processed = set()
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        record = json.loads(line)
                        if "post_url" in record:
                            processed.add(record["post_url"])
                    except json.JSONDecodeError:
                        continue
            logger.info(f"Loaded {len(processed)} processed post URLs from {file_path}.")
        return processed

    def get_post_elements(self, limit: int) -> Iterator[Any]:
        """
        Retrieves a list of post URLs to be scraped for a given profile.

        This function implements a caching and filtering logic:
        1. It first tries to load post URLs from a cached file (`posts_path`).
        2. If no cache exists, it scrapes the profile page to collect the URLs and
           saves them to the cache file for future runs.
        3. It then loads the list of URLs that have already been processed from
           the final metadata output file.
        4. It filters the collected URLs, removing any that have already been processed.

        Args:
            limit: The maximum number of post URLs to collect if scraping from scratch.
        """
        profile = self.config.main.target_profile
        posts_path = self.config.data.posts_path

        # Load cached urls
        cached = self._load_cached_urls(posts_path)
        if cached is None:
            # Scrape fresh if no cache
            elements = self.profile_page.scroll_and_collect_(limit)
            urls = [elem for elem in elements]
            self._save_urls(profile, urls, posts_path)
        else:
            urls = cached

        # Filter out already processed urls
        processed_data_path = self.config.data.metadata_path
        processed = self._load_processed_urls(processed_data_path)
        urls = [u for u in urls if u not in processed]

        logger.info(f"Returning {len(urls)} post URLs after filtering out {len(processed)} processed ones.")
        return urls


    def extract_comments(self, steps:int = None):
        """
        Extracts comments from the currently open post page.

        Args:
            steps: The number of scroll steps to perform while collecting comments.
                   If None, a default value is used.
        """
        return self.profile_page.extract_comments(steps=steps)

    def extract_post_metadata(self, post_element: Any) -> Dict:
        """
        Placeholder for extracting metadata from a post element.
        (Not yet implemented)
        """
        pass

    def extract_public_comments(self, post_element: Any, max_comments: int) -> List[Dict]:
        """
        Placeholder for extracting public comments from a post.
        (Not yet implemented)
        """
        pass


    def scrape_posts_in_batches(self,
        post_elements,
        batch_size=3,
        save_every=5,
        tab_open_retries=4,
        debug=False
    ):
        """
        Scrapes a list of post URLs in batches, saving results periodically.

        This method iterates through the provided post URLs, opening each one in a
        new browser tab to scrape its content. It is designed to be robust,
        handling tab management, data extraction, and intermittent saving to
        prevent data loss.

        Args:
            post_elements (list[str]): A list of post URLs to scrape.
            batch_size (int): The number of posts to open in tabs at a time.
            save_every (int): The number of posts to scrape before saving the
                              collected data to the output files.
            tab_open_retries (int): The number of retries for detecting a new tab.
            debug (bool): If True, scraped tabs will not be closed, which is useful
                          for debugging.

        Returns:
            A dictionary containing lists of 'scraped_posts' and 'skipped_posts'.
        """
        results = {"scraped_posts": [], "skipped_posts": []}
        total_scraped = 0

        main_handle = self.driver.current_window_handle
        tmp_file = self.config.data.tmp_path

        # main loop over batches
        for batch_start in range(0, len(post_elements), batch_size):
            batch = post_elements[batch_start: batch_start + batch_size]
            opened = []  # list of tuples (index, href, handle)

            # --- open all posts in batch (in new tabs) ---
            for i, post_element in enumerate(batch, start=batch_start):
                try:
                    # href = post_element.get_attribute("href")
                    href = post_element
                    if not href:
                        logger.warning(
                            f"Skipping post {i+1} from profile {self.config.target_profile}: missing href."
                        )
                        results["skipped_posts"].append({
                            "index": i,
                            "reason": "missing href",
                            "profile": self.config.target_profile
                        })
                        continue

                    try:
                        new_handle = self.open_href_in_new_tab(href, tab_open_retries)
                        # optionally give the new tab a moment to start loading
                        time.sleep(random.uniform(0.8, 1.5))
                        opened.append((i, href, new_handle))
                        logger.info(f"Opened post {i+1} in new tab: {href} -> handle {new_handle}")
                    except Exception as e:
                        logger.error(f"Failed to open new tab for post {i+1}: {e}")
                        results["skipped_posts"].append({
                            "index": i,
                            "reason": f"failed to open tab: {str(e)}",
                            "profile": self.config.target_profile
                        })
                except Exception as e:
                    logger.exception(f"Unexpected error when preparing post {i+1}: {e}")
                    results["skipped_posts"].append({
                        "index": i,
                        "reason": f"error extracting href: {str(e)}",
                        "profile": self.config.target_profile
                    })

            # --- scrape each opened tab, one-by-one, ensuring closure ---
            for i, href, handle in opened:
                try:
                    # switch to the new tab
                    self.driver.switch_to.window(handle)
                    # Anti Bot measure
                    human_mouse_move(self.driver,duration=self.config.main.human_mouse_move_duration)
                    logger.info(f"Switched to tab {handle} for post {i} ({href})")
                    # optional short wait for page to start loading
                    try:
                        # If you have a reliable "post content" element to wait for, use it here.
                        # Example (commented): WebDriverWait(driver, page_load_timeout).until(
                        #     EC.presence_of_element_located((By.CSS_SELECTOR, "article"))
                        # )
                        time.sleep(random.uniform(0.6, 1.2))
                    except Exception:
                        # non-fatal - proceed and rely on backend.extract_* waits
                        logger.debug("Page load wait did not find expected element, continuing.")

                    post_id = f"post_{i}"
                    post_data = {
                        "post_url": href,
                        "post_id": post_id,
                        "post_title": None,
                        "post_images": [],
                        "post_comments": [],
                    }

                    # Title / metadata
                    try:
                        handle_slug = f"/{self.config.main.target_profile}/"
                        logger.info(f"Extracting title data for {href} with handle {handle_slug}")
                        post_data["post_title"] = self.get_post_title_data(handle_slug) or ""
                    except Exception as e:
                        logger.error(f"Title extraction failed for {href}: {e}")
                        logger.debug(traceback.format_exc())

                    # Images
                    try:
                        post_data["post_images"] = images_from_post(self.driver) or []
                        logger.info(f"Images extraction successful for {href}")
                        logger.info(f'{post_data["post_images"]}')
                    except Exception as e:
                        logger.error(f"Images extraction failed for {href}: {e}")
                        logger.debug(traceback.format_exc())

                    # Likes / other sections
                    try:
                        post_data["likes"] = get_section_with_highest_likes(self.driver) or {}
                        logger.info(f"Likes extraction successful for {href}")
                    except Exception as e:
                        logger.error(f"Likes extraction failed for {href}: {e}")
                        logger.debug(traceback.format_exc())
                    
                    # comments
                    try:
                        post_data["post_comments_gif"] = scrape_comments_with_gif(self.driver,self.config) or []
                    except Exception as e:
                        logger.error(f"Comments extraction with gif failed for {href}: {e}")
                        logger.debug(traceback.format_exc())


                    results["scraped_posts"].append(post_data)
                    total_scraped += 1
                    logger.info(f"Scraped post {i} ({href}). Total scraped: {total_scraped}")

                    # --- save every result immediately to tmp file ---
                    try:
                        save_intermediate(post_data, tmp_file)
                    except Exception as e:
                        logger.warning(f"Failed to write tmp result for {href}: {e}")

                    # --- every N posts, save final and clear tmp ---
                    if total_scraped % save_every == self.config.main.save_every:
                        save_scrape_results(results, self.data.output_dir,self.config)
                        clear_tmp_file(tmp_file)
                        logger.info(f"Saved results after {total_scraped} scraped posts.")


                except Exception as e:
                    logger.exception(f"Unexpected error while scraping post {i} ({href}): {e}")
                    results["skipped_posts"].append({
                        "index": i,
                        "reason": str(e),
                        "profile": self.config.main.target_profile
                    })
                finally:
                    # Ensure this tab is closed and we switch back to a known handle.
                    try:
                        if debug:
                            logger.info(f"DEBUG mode: leaving tab {handle} open.")
                        else:
                            self.driver.close()
                            logger.debug(f"Closed tab {handle}")
                    except Exception as e:
                        logger.warning(f"Error closing tab {handle}: {e}")
                    # switch back to main handle (if it's still present) or to any remaining handle
                    handles = self.driver.window_handles
                    if not handles:
                        logger.info("No browser windows left after closing tab.")
                        return results
                    # prefer main_handle if still available
                    if main_handle in handles:
                        self.driver.switch_to.window(main_handle)
                    else:
                        # fallback to last handle
                        self.driver.switch_to.window(handles[0])
                    logger.debug(f"Switched back to handle {self.driver.current_window_handle}")

            # optional: jittered wait between batches to mimic human rate-limits
            random_delay(self.config.main.rate_limit_seconds_min, self.config.main.rate_limit_seconds_max)

        # final save
        if results["scraped_posts"] or results["skipped_posts"]:
            save_scrape_results(results, self.config.data.output_dir, self.config)
            clear_tmp_file(tmp_file)
            logger.info("Saved final scrape results.")

        return results


    def open_href_in_new_tab(self, href,tab_open_retries):
        """
        Opens a URL in a new browser tab and returns the new window handle.

        It works by recording the set of window handles before opening the new
        tab, and then finding the handle that was added.

        Args:
            href (str): The URL to open.
            tab_open_retries (int): The number of times to check for a new handle.

        Returns:
            The window handle (string) of the newly opened tab.
        """
        before_handles = set(self.driver.window_handles)
        # Open new tab with specified href - this opens a new tab in most browsers
        self.driver.execute_script("window.open(arguments[0], '_blank');", href)

        # Wait for the new handle to appear
        new_handle = None
        for _ in range(tab_open_retries):
            after_handles = set(self.driver.window_handles)
            diff = after_handles - before_handles
            if diff:
                new_handle = diff.pop()
                break
            time.sleep(0.5 + random.random() * 0.5)  # jittered wait
        if not new_handle:
            raise RuntimeError(f"New tab did not appear for href={href}")
        return new_handle

    def get_post_title_data(self, href_string, timeout=5):
        """
        Executes a JavaScript snippet to extract post title, timestamp, and author data.

        The JavaScript code searches for a specific DOM structure that typically
        contains the post's header information. It looks for the innermost `div`
        that contains both a link (`<a>`) to the author's profile and a `<time>` element.

        Args:
            href_string (str): The profile slug (e.g., `"/ladbible/"`) used to
                               identify the correct author link.

        Returns:
            A dictionary containing the extracted data, or None if not found.
        """
        random_delay(2, 4.5)  # small wait to ensure content is fully loaded
        href_string_js = json.dumps(href_string)  # safely quote special characters
        
        js_code = f"""
        function getPostTitleData(variableA) {{
            const divs = Array.from(document.querySelectorAll('div'));
            let innermostDiv = null;

            for (const div of divs) {{
                const aEl = div.querySelector(`a[href="${{variableA}}"]`);
                const timeEl = div.querySelector('time');

                if (aEl && timeEl) {{
                    const childDivs = div.querySelectorAll('div');
                    let hasNestedBoth = false;

                    for (const child of childDivs) {{
                        if (child.querySelector(`a[href="${{variableA}}"]`) && child.querySelector('time')) {{
                            hasNestedBoth = true;
                            break;
                        }}
                    }}

                    if (!hasNestedBoth) {{
                        innermostDiv = div;
                    }}
                }}
            }}

            if (!innermostDiv) return null;

            const aEl = innermostDiv.querySelector(`a[href="${{variableA}}"]`);
            const timeEl = innermostDiv.querySelector('time');

            const data = {{
                topDivClass: innermostDiv.className,
                aHref: aEl ? aEl.getAttribute('href') : null,
                aSrc: aEl ? aEl.getAttribute('src') : null,
                timeDatetime: timeEl ? timeEl.getAttribute('datetime') : null,
                siblingTexts: []
            }};

            const parent = innermostDiv.parentElement;
            if (parent) {{
                const siblings = Array.from(parent.children).filter(el => el !== innermostDiv);
                data.siblingTexts = siblings
                    .map(sib => sib.textContent.trim())
                    .filter(t => t.length > 0);
            }}

            return data;
        }}

        return getPostTitleData({href_string_js});
        """

        logger.debug(f"Executing JS - {js_code} to get post title data for href: {href_string}")
        return self.driver.execute_script(js_code)
