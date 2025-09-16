from selenium import webdriver
from urllib.parse import urlparse
import time
import threading

# ---------------------------
# URL validator
# ---------------------------
from urllib.parse import urlparse

def is_allowed_instagram_url(url: str) -> bool:
    # Allow blank/empty tabs
    if url in ("about:blank", "data:,"):
        return True

    parsed = urlparse(url)
    if parsed.netloc != "www.instagram.com":
        return False
    
    path_parts = [p for p in parsed.path.strip("/").split("/") if p]

    # Case 1: homepage (/)
    if not path_parts:
        return True

    # Case 2: post page (/p/{id}/)
    if len(path_parts) == 2 and path_parts[0] == "p":
        return True

    # Case 3: profile page (/{username}/)
    if len(path_parts) == 1:
        return True

    # Case 4: nested post under profile (/{username}/p/{id}/)
    if len(path_parts) == 3 and path_parts[1] == "p":
        return True

    return False

def _check_page(url):
    if not is_allowed_instagram_url(url):
        print(f"⚠️ Suspicious navigation: {url}")
        input("Press Enter to continue after checking...")

# ---------------------------
# Patch WebDriver.get
# ---------------------------
def patch_driver(driver):
    original_get = driver.get
    def safe_get(url, *args, **kwargs):
        result = original_get(url, *args, **kwargs)
        _check_page(driver.current_url)
        return result
    driver.get = safe_get

    # ---------------------------
    # Patch WebElement.click
    # ---------------------------
    original_click = webdriver.remote.webelement.WebElement.click
    def safe_click(self, *args, **kwargs):
        result = original_click(self, *args, **kwargs)
        _check_page(self.parent.current_url)
        return result
    webdriver.remote.webelement.WebElement.click = safe_click

    # ---------------------------
    # Patch execute_script
    # ---------------------------
    original_exec = driver.execute_script
    def safe_exec(script, *args, **kwargs):
        result = original_exec(script, *args, **kwargs)
        _check_page(driver.current_url)
        return result
    driver.execute_script = safe_exec

    # ---------------------------
    # Background watchdog thread
    # ---------------------------
    def watchdog():
        while True:
            try:
                _check_page(driver.current_url)
                time.sleep(1)
            except Exception:
                break
    threading.Thread(target=watchdog, daemon=True).start()

    return driver