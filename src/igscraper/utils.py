import os
import pdb
import re
import json
import time
import random
import traceback
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from selenium.webdriver import ActionChains
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    ElementClickInterceptedException,
)

import random
import time
from typing import Optional, Tuple, List, Dict
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By

from igscraper.logger import get_logger

logger = get_logger(__name__)


def random_delay(min_s: float, max_s: float) -> None:
    time.sleep(random.uniform(min_s, max_s))

def normalize_hashtags(caption: str) -> list[str]:
    return re.findall(r"#\w+", caption or '')

# def criteria_example(metadata: dict) -> bool:
#     """Example criteria function - include posts with more than 100 likes"""
#     return metadata.get('likes', 0) > 100

# def safe_write_jsonl(path: Path, data: dict) -> None:
#     with open(path, 'a', encoding='utf-8') as f:
#         f.write(json.dumps(data, ensure_ascii=False) + '\n')



def scrape_carousel_images(driver, image_gather_func, min_wait=0.5, max_wait=2.2):
    """
    Scrape all images from an Instagram carousel post.

    Args:
        driver: Selenium WebDriver instance already on a post page
        image_gather_func: function(driver) -> list of images/metadata
        min_wait, max_wait: range for random wait between swipes

    Returns:
        List of image data collected
    """
    image_data = []
    seen_srcs = set()  # track unique 'src' values
    wait = WebDriverWait(driver, 5)  # shorter timeout for Next button
    actions = ActionChains(driver)
    steps = 0

    while True:
        # Grab current visible images (filter duplicates)
        new_items = image_gather_func(driver)
        # image_data.extend(new_items)
        # pdb.set_trace()
        image_data.extend(new_items)
        # for item in new_items:
        #     src = item.get("src")
        #     if src not in seen_srcs:
        #         seen_srcs.add(src)
        #         image_data.extend(item)

        try:
            # Look for Next button
            next_button = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "button[aria-label='Next']"))
            )
        except (TimeoutException, NoSuchElementException):
            logging.info(f"Reached end of carousel after {steps} steps.")
            break

        # Try to click like a human
        if not human_like_click(driver, next_button, actions):
            logging.warning(f"Could not click Next button at step {steps}, stopping.")
            break

        steps += 1
        time.sleep(random.uniform(min_wait, max_wait))
    return image_data



def get_all_post_images_data(driver):
    """
    Given browser is on post page,
    this function will extract the AI title given to each image
    in the post.
    """
    all_images = []

    def extract_images_from_container(container):
        images = []
        try:
            ul = container.find_element(By.CLASS_NAME, "_acay")
            lis = ul.find_elements(By.CLASS_NAME, "_acaz")
            for li in lis:
                imgs = li.find_elements(By.TAG_NAME, "img")
                for img in imgs:
                    # collect common useful attributes
                    img_data = {
                        "src": img.get_attribute("src"),
                        "alt": img.get_attribute("alt"),
                        "title": img.get_attribute("title"),
                        "aria_label": img.get_attribute("aria-label"),
                        "text": img.text.strip() if img.text else None
                    }
                    images.append(img_data)
        except NoSuchElementException:
            pass
        return images

    # Case 1: containers with div.x1iyjqo2
    containers = driver.find_elements(By.CLASS_NAME, "x1iyjqo2")
    for c in containers:
        all_images.extend(extract_images_from_container(c))

    # Case 2: containers with div.x1lliihq.x1n2onr6
    containers = driver.find_elements(By.CSS_SELECTOR, "div.x1lliihq.x1n2onr6")
    for c in containers:
        all_images.extend(extract_images_from_container(c))

    # Case 3: fallback — any ul._acay > li._acaz > img
    if not all_images:
        uls = driver.find_elements(By.CLASS_NAME, "_acay")
        for ul in uls:
            lis = ul.find_elements(By.CLASS_NAME, "_acaz")
            for li in lis:
                imgs = li.find_elements(By.TAG_NAME, "img")
                for img in imgs:
                    img_data = {
                        "src": img.get_attribute("src"),
                        "alt": img.get_attribute("alt"),
                        "title": img.get_attribute("title"),
                        "aria_label": img.get_attribute("aria-label"),
                        "text": img.text.strip() if img.text else None
                    }
                    all_images.append(img_data)

    return all_images


def images_from_post(driver):
    ## try to extract multiple images if they exist
    images = get_instagram_post_images(driver)
    if images == []:
        logging.info("Trying to extract single image.")
        # grab the single image if it exists
        return get_first_img_attributes_in_div(driver)
    logging.info(f"Extracted {len(images)} images from carousel.")
    return images


def get_instagram_post_images(driver):
    """
    Extract all attributes of <img> tags in an Instagram post.
    Deduplicates results by 'src' attribute.
    Returns: list of dicts with all <img> attributes.
    """
    try:
        xp = "//article//ul[contains(@class,'_acay')]//li[contains(@class,'_acaz')]//img"
        imgs = driver.find_elements(By.XPATH, xp)

        if not imgs:
            return []

        # Pull all attributes in one shot
        img_attrs = driver.execute_script("""
            return arguments[0].map(el => {
                let items = {};
                for (let attr of el.attributes) {
                    items[attr.name] = attr.value;
                }
                return items;
            });
        """, imgs)

        # Dedup by src
        seen = set()
        unique_imgs = []
        for attrs in img_attrs:
            src = attrs.get("src")
            if src and src not in seen:
                seen.add(src)
                unique_imgs.append(attrs)

        return unique_imgs

    except Exception as e:
        import traceback
        traceback.print_exc()
        return []



# def extract_attributes_by_tag_in_section(
#     driver: WebDriver, 
#     target_tag_name: str = 'a', 
#     timeout: int = 10
# ) -> Optional[List[Dict[str, Any]]]:
#     """
#     Finds a specific <section> using a stable XPath, then finds all descendant
#     elements within that section that have the target tag, and extracts all
#     attributes + inner text.

#     Args:
#         driver: The Selenium WebDriver instance.
#         target_tag_name: The tag name of the descendant elements
#                          whose attributes and text should be extracted.
#         timeout: Max wait time for section to appear.

#     Returns:
#         A list of dicts, where each contains:
#             - element_index: Index of the element
#             - tag_name: The target tag
#             - attributes: Dict of all element attributes
#             - text: The visible text of the element
#         Returns None if the section is not found or an error occurs.
#         Returns [] if no matching elements are found.
#     """

#     stable_section_xpath = "//section[./div[contains(@class, 'html-div')]]"

#     try:
#         # 1. Wait for section to exist (fixes timing issues)
#         section_element = WebDriverWait(driver, timeout).until(
#             EC.presence_of_element_located((By.XPATH, stable_section_xpath))
#         )

#         # 2. Find all target tags within the section
#         elements_with_target_tag = section_element.find_elements(By.TAG_NAME, target_tag_name)

#         if not elements_with_target_tag:
#             print(f"No elements with tag '{target_tag_name}' found inside the section.")
#             return []

#         all_elements_data: List[Dict[str, Any]] = []

#         for i, element in enumerate(elements_with_target_tag):
#             # Get attributes via JS
#             attributes_dict = driver.execute_script(
#                 """
#                 let attributes = arguments[0].attributes;
#                 let obj = {};
#                 for (let i = 0; i < attributes.length; i++) {
#                     obj[attributes[i].name] = attributes[i].value;
#                 }
#                 return obj;
#                 """,
#                 element
#             )

#             # Also grab inner text
#             element_text = element.text.strip()

#             all_elements_data.append({
#                 "element_index": i,
#                 "tag_name": target_tag_name,
#                 "attributes": attributes_dict,
#                 "text": element_text
#             })

#         return all_elements_data

#     except NoSuchElementException:
#         print("Error: Could not find the section element using the stable XPath.")
#         return None
#     except Exception as e:
#         print(f"An unexpected error occurred: {e}")
#         return None


# def extract_elements_with_numbers_in_section(
#     driver: WebDriver, 
#     target_tag_name: str = 'a', 
#     timeout: int = 10
# ) -> Optional[List[Dict[str, Any]]]:
#     """
#     Finds a <section> using a stable XPath, then extracts only those descendant
#     elements of the given tag whose visible text contains numbers
#     (e.g. '98,501', '12345', 'random text 2,345 others').

#     Args:
#         driver: Selenium WebDriver instance.
#         target_tag_name: The tag name of descendant elements to extract (e.g. 'a').
#         timeout: Max wait time for section to appear.

#     Returns:
#         A list of dicts containing:
#             - element_index
#             - tag_name
#             - attributes
#             - text
#             - extracted_numbers: list of numbers found in text (as strings)
#         Only includes elements where text contains a number.
#         Returns [] if none found, None on error.
#     """

#     stable_section_xpath = "//section[./div[contains(@class, 'html-div')]]"
#     number_pattern = re.compile(r'\d{1,3}(?:,\d{3})*|\d+')  
#     # matches "98,501", "12345", "2,345", etc.

#     try:
#         # 1. Wait for section
#         section_element = WebDriverWait(driver, timeout).until(
#             EC.presence_of_element_located((By.XPATH, stable_section_xpath))
#         )

#         # 2. Find all target tags
#         elements_with_target_tag = section_element.find_elements(By.TAG_NAME, target_tag_name)

#         results: List[Dict[str, Any]] = []

#         for i, element in enumerate(elements_with_target_tag):
#             text = element.text.strip()
#             matches = number_pattern.findall(text)

#             if not matches:
#                 continue  # skip if no numbers inside text

#             attributes_dict = driver.execute_script(
#                 """
#                 let attributes = arguments[0].attributes;
#                 let obj = {};
#                 for (let i = 0; i < attributes.length; i++) {
#                     obj[attributes[i].name] = attributes[i].value;
#                 }
#                 return obj;
#                 """,
#                 element
#             )

#             results.append({
#                 "element_index": i,
#                 "tag_name": target_tag_name,
#                 "attributes": attributes_dict,
#                 "text": text,
#                 "extracted_numbers": matches  # list of number strings
#             })

#         return results

#     except NoSuchElementException:
#         print("Error: Could not find the section element using the stable XPath.")
#         return None
#     except Exception as e:
#         print(f"An unexpected error occurred: {e}")
#         return None



def human_like_click(driver, element, actions, retries=3):
    """
    Try to click an element in a human-like way, with retries and JS fallback.
    """
    for attempt in range(retries):
        try:
            # Scroll into view
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
            time.sleep(random.uniform(0.3, 0.7))

            # Move "cursor" (Selenium-simulated)
            actions.move_to_element(element).perform()
            time.sleep(random.uniform(0.2, 0.6))

            # Normal click
            element.click()
            return True
        except ElementClickInterceptedException:
            if attempt < retries - 1:
                # Small random wait and retry
                time.sleep(random.uniform(0.5, 1.2))
            else:
                # Final fallback → force JS click
                driver.execute_script("arguments[0].click();", element)
                return True
        except TimeoutException:
            return False
    return False


def extract_post_title_details(driver: WebDriver):
    results = []
    # Select <div class="html-div"> with <time> OR <a> inside
    divs = driver.find_elements(
        "xpath", "//div[contains(@class, 'html-div')][.//time or .//a][not(.//div[contains(@class, 'html-div')])]"
    )

    for div in divs:
        div_data = {}

        # --- div attributes ---
        attrs = driver.execute_script(
            """
            let attrs = {};
            for (let attr of arguments[0].attributes) {
                attrs[attr.name] = attr.value;
            }
            return attrs;
            """,
            div,
        )
        div_data["div_attributes"] = attrs

        # --- visible text ---
        text = div.text.strip()
        if text:
            div_data["text"] = text

        # --- images ---
        imgs = div.find_elements("xpath", ".//img")
        if imgs:
            div_data["images"] = [
                {"src": img.get_attribute("src"), "alt": img.get_attribute("alt")}
                for img in imgs if img.get_attribute("src")
            ]

        # --- anchors ---
        anchors = div.find_elements("xpath", ".//a")
        if anchors:
            div_data["links"] = [
                {"href": a.get_attribute("href"), "text": a.text.strip()}
                for a in anchors if a.get_attribute("href")
            ]

        # --- times ---
        times = div.find_elements("xpath", ".//time")
        if times:
            div_data["times"] = [
                {"datetime": t.get_attribute("datetime"), "text": t.text.strip()}
                for t in times
            ]

        if div_data:
            results.append(div_data)

    return results


def cleanup_details(data):
    """
    Deduplicate images, links, and times in scraped div details.
    - Images: dedup by src, keep all unique alts in a list
    - Links: dedup by href, keep one text
    - Times: dedup by datetime or text
    """
    cleaned = []

    for item in data:
        new_item = item.copy()

        # Dedup images by src
        if "images" in new_item:
            img_map = {}
            for img in new_item["images"]:
                src = img.get("src")
                if not src:
                    continue
                if src not in img_map:
                    img_map[src] = {"src": src, "alt": []}

                alt = img.get("alt")
                if alt and alt not in img_map[src]["alt"]:
                    img_map[src]["alt"].append(alt)

            # If alt has only one entry, simplify to string
            for val in img_map.values():
                if len(val["alt"]) == 0:
                    val.pop("alt")  # no alts
                elif len(val["alt"]) == 1:
                    val["alt"] = val["alt"][0]

            new_item["images"] = list(img_map.values())

        # Dedup links by href
        if "links" in new_item:
            link_map = {}
            for link in new_item["links"]:
                href = link.get("href")
                if not href:
                    continue
                if href not in link_map:
                    link_map[href] = {"href": href}
                text_val = link.get("text")
                if text_val and not link_map[href].get("text"):
                    link_map[href]["text"] = text_val
            new_item["links"] = list(link_map.values())

        # Dedup times by datetime or text
        if "times" in new_item:
            time_map = {}
            for t in new_item["times"]:
                key = t.get("datetime") or t.get("text")
                if not key:
                    continue
                if key not in time_map:
                    time_map[key] = {}
                if t.get("datetime"):
                    time_map[key]["datetime"] = t["datetime"]
                if t.get("text") and not time_map[key].get("text"):
                    time_map[key]["text"] = t["text"]
            new_item["times"] = list(time_map.values())

        cleaned.append(new_item)

    return cleaned

# ##This functions works end to end.
# ## scrolling works fine
# ## extraction works fine for all scrolled comments.
# def scrape_comments(driver, wait_selector="div.html-div", steps=100, timeout=10):
#     """
#     Scrape Instagram-like comments from a page using Selenium.
    
#     Args:
#         driver: Selenium WebDriver instance.
#         wait_selector: CSS selector to wait for before executing JS.
#         timeout: Maximum seconds to wait for the comment container.
        
#     Returns:
#         List of dicts: Each dict has 'handle', 'date', 'comment', 'likes'.
#     """
#     # Wait until at least one comment container is present
#     WebDriverWait(driver, timeout).until(
#         EC.presence_of_element_located((By.CSS_SELECTOR, wait_selector))
#     )
#     # pdb.set_trace()
#     container_info = find_comment_container(driver)
#     logger.info(f"Found comment container: {container_info}")
#     steps = random.randint(int(steps * 0.8), int(steps * 1.2))
#     human_scroll(driver, container_info.get("selector"), steps=steps)
#     js_code = """
#     function parseComments() {
#         const results = [];
#         const seen = new Set();

#         const topDivs = document.querySelectorAll("div.html-div");

#         topDivs.forEach(topDiv => {
#             const profileDiv = topDiv.querySelector("div > div.html-div > div.html-div");
#             const commentDiv = Array.from(topDiv.querySelectorAll("div > div.html-div > div.html-div"))
#                 .find(div => !div.querySelector("span a, span time"));

#             if (!profileDiv || !commentDiv) return;

#             const data = { likes: null, handle: null, date: null, comment: null };

#             // --- Likes ---
#             const likeSpan = Array.from(topDiv.querySelectorAll("span"))
#                 .map(s => s.innerText && s.innerText.trim())
#                 .filter(Boolean)
#                 .find(t => /\\b\\d{1,3}(?:,\\d{3})*(?:\\.\\d+)?[kKmM]?\\s+likes?\\b/i.test(t));
#             if (likeSpan) data.likes = likeSpan;

#             // --- Handle & date ---
#             const spans = profileDiv.querySelectorAll("span");
#             spans.forEach(span => {
#                 const aTag = span.querySelector("a");
#                 if (aTag && !data.handle) data.handle = aTag.innerText.trim();
#                 const timeTag = span.querySelector("time");
#                 if (timeTag && !data.date) data.date = timeTag.innerText.trim();
#             });

#             // --- Comment ---
#             const text = commentDiv.innerText.trim();
#             if (text) data.comment = text;

#             // Only keep if comment and date exist
#             if (data.comment && data.date) {
#                 const key = (data.handle || "") + "::" + data.comment;
#                 if (!seen.has(key)) {
#                     seen.add(key);
#                     results.push(data);
#                 }
#             }
#         });

#         return results;
#     }

#     return parseComments();
#     """

#     # Execute JS in the browser context
#     return driver.execute_script(js_code)

def scrape_comments_with_gif(driver, config, wait_selector="div.html-div", timeout=10):
    """
    Scrape Instagram-like comments from a page using Selenium.
    
    Args:
        driver: Selenium WebDriver instance.
        wait_selector: CSS selector to wait for before executing JS.
        timeout: Maximum seconds to wait for the comment container.
        
    Returns:
        List of dicts: Each dict has 'handle', 'date', 'comment', 'likes',
                       and optional 'commentImg'.
    """
    # Wait until at least one comment container is present
    WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, wait_selector))
    )
    container_info = find_comment_container(driver)
    logger.info(f"Found comment container: {container_info}")
    # steps = 100
    steps = config.main.comment_scroll_steps
    steps = random.randint(int(steps * 0.8), int(steps * 1.2))
    human_scroll(driver, container_info.get("selector"), steps=steps,max_retries=config.main.comments_scroll_retries)
    # js_code = """
    # function parseComments() {
    #     const results = [];
    #     const seen = new Set();

    #     const topDivs = document.querySelectorAll("div.html-div");

    #     topDivs.forEach(topDiv => {
    #         const profileDiv = topDiv.querySelector("div > div.html-div > div.html-div");
    #         const commentDiv = Array.from(topDiv.querySelectorAll("div > div.html-div > div.html-div"))
    #             .find(div => !div.querySelector("span a, span time"));

    #         if (!profileDiv || !commentDiv) return;

    #         const data = { likes: null, handle: null, date: null, comment: null };

    #         // --- Likes ---
    #         const likeSpan = Array.from(topDiv.querySelectorAll("span"))
    #             .map(s => s.innerText && s.innerText.trim())
    #             .filter(Boolean)
    #             .find(t => /\\b\\d{1,3}(?:,\\d{3})*(?:\\.\\d+)?[kKmM]?\\s+likes?\\b/i.test(t));
    #         if (likeSpan) data.likes = likeSpan;

    #         // --- Handle & date ---
    #         const spans = profileDiv.querySelectorAll("span");
    #         spans.forEach(span => {
    #             const aTag = span.querySelector("a");
    #             if (aTag && !data.handle) data.handle = aTag.innerText.trim();
    #             const timeTag = span.querySelector("time");
    #             if (timeTag && !data.date) data.date = timeTag.innerText.trim();
    #         });

    #         // --- Comment text ---
    #         const text = commentDiv.innerText.trim();
    #         if (text) data.comment = text;

    #         // --- Image (if exists) ---
    #         const imgTag = commentDiv.querySelector("img");
    #         if (imgTag && imgTag.src) {
    #             data.commentImg = imgTag.src;
    #         }

    #         // Keep if (comment OR image) AND date exist
    #         if ((data.comment || data.commentImg) && data.date) {
    #             const key = (data.handle || "") + "::" + (data.comment || "") + "::" + (data.commentImg || "");
    #             if (!seen.has(key)) {
    #                 seen.add(key);
    #                 results.push(data);
    #             }
    #         }
    #     });

    #     return results;
    # }

    # return parseComments();
    # """
    js_code_mod = """
    function parseComments() {
        const results = [];
        const seen = new Set();

        const topDivs = document.querySelectorAll("div.html-div");

        topDivs.forEach(topDiv => {
            const profileDiv = topDiv.querySelector("div > div.html-div > div.html-div");
            const commentDiv = Array.from(topDiv.querySelectorAll("div > div.html-div > div.html-div"))
                .find(div => !div.querySelector("span a, span time"));

            if (!profileDiv || !commentDiv) return;

            const data = { likes: null, handle: null, date: null, comment: null, commentImgs: [] };

            // --- Likes ---
            const likeSpan = Array.from(topDiv.querySelectorAll("span"))
                .map(s => s.innerText && s.innerText.trim())
                .filter(Boolean)
                .find(t => /\\b\\d{1,3}(?:,\\d{3})*(?:\\.\\d+)?[kKmM]?\\s+likes?\\b/i.test(t));
            if (likeSpan) data.likes = likeSpan;

            // --- Handle & date ---
            const spans = profileDiv.querySelectorAll("span");
            spans.forEach(span => {
                const aTag = span.querySelector("a");
                if (aTag && !data.handle) data.handle = aTag.innerText.trim();
                const timeTag = span.querySelector("time");
                if (timeTag && !data.date) data.date = timeTag.innerText.trim();
            });

            // --- Comment text ---
            const text = commentDiv.innerText.trim();
            if (text) data.comment = text;

            // --- Collect all images under topDiv that have exactly "class" and "src" ---
            const imgTags = topDiv.querySelectorAll("img");
            if (imgTags.length > 0) {
                data.commentImgs = Array.from(imgTags)
                    .filter(img => {
                        const attrs = Array.from(img.attributes).map(a => a.name);
                        return attrs.length === 2 && attrs.includes("class") && attrs.includes("src");
                    })
                    .map(img => img.src);
            }

            // Keep if:
            // 1. commentImgs is present (regardless of comment/date)
            // OR
            // 2. commentImgs is NOT present, but both date AND comment exist
            const hasImages = data.commentImgs.length > 0;
            const hasCommentAndDate = data.comment && data.date;
            
            if (hasImages || hasCommentAndDate) {
                const key = (data.handle || "") + "::" + (data.comment || "") + "::" + data.commentImgs.join(",");
                if (!seen.has(key)) {
                    seen.add(key);
                    results.push(data);
                }
            }
        });

        return results;
    }

    // Execute the function and return results
    return parseComments();
    """


    # Execute JS in the browser context
    return driver.execute_script(js_code_mod)


def get_section_with_highest_likes(driver, wait_selector="section", timeout=10):
    """
    Finds the section with the highest likes on the page using Selenium and JS.

    Args:
        driver: Selenium WebDriver instance.
        wait_selector: CSS selector to wait for before executing JS.
        timeout: Max seconds to wait for at least one section.

    Returns:
        dict with 'likesText' and 'likesNumber' of the top section (or None).
    """
    # Wait until at least one section is present
    WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, wait_selector))
    )

    js_code = """
    return (function() {
        function parseLikes(text) {
            let num = parseFloat(text.replace(/[^\\d.kKmM]/g, ""));
            if (/k/i.test(text)) num *= 1;
            else if (/m/i.test(text)) num *= 1000;
            return num;
        }

        let maxLikes = -1;
        let topSection = null;

        const sections = document.querySelectorAll("section");

        sections.forEach(section => {
            if (!section.querySelector("span") || !section.querySelector("a")) return;

            const likeSpan = Array.from(section.querySelectorAll("span"))
                .find(span => span.innerText && /like/i.test(span.innerText));

            if (!likeSpan) return;

            const likesText = likeSpan.innerText.trim();
            const likesNumber = parseLikes(likesText);

            if (likesNumber > maxLikes) {
                maxLikes = likesNumber;
                topSection = { likesText: likesText, likesNumber: likesNumber };
            }
        });

        return topSection;  // null if none found
    })();
    """

    return driver.execute_script(js_code)


def get_first_img_attributes_in_div(driver, wait_selector="div img", timeout=10):
    """
    Finds the first <img> nested anywhere inside a <div> that has alt, crossorigin, and src attributes,
    and returns all its attributes as a Python dictionary.
    
    Args:
        driver: Selenium WebDriver instance
        wait_selector: CSS selector to wait for
        timeout: Max seconds to wait for element
    
    Returns:
        dict of all attributes of the first matching <img>, or None if not found
    """
    # Wait until at least one image under a div is present
    WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, wait_selector))
    )

    js_code = """
    return (function() {
        const img = Array.from(document.querySelectorAll("div img"))
            .find(i => i.hasAttribute("alt") && i.hasAttribute("crossorigin") && i.hasAttribute("src"));

        if (!img) return null;

        const attrs = {};
        Array.from(img.attributes).forEach(attr => {
            attrs[attr.name] = attr.value;
        });

        return attrs;
    })();
    """

    return driver.execute_script(js_code)



## --- div   (main container)
##    --- h2
##        --- there can be more nested classes here
##         -- <a href="variable_1">
##    --- div
##       --- h1
##          --- there can be more nested classes here
##          --- text we want

# from selenium import webdriver
# ## the time attribute needs to be fixed, its null as of now.
# def extract_h1_data(driver):
#     """
#     Extracts all <h1> text under containers with <h2>, deduplicated by h1 class,
#     and also extracts all attributes from any '.time' element inside the container.
    
#     Args:
#         driver (selenium.webdriver): Selenium WebDriver instance
    
#     Returns:
#         List[dict]: List of dictionaries with keys:
#                     'h1Class', 'h2Text', 'h1Text', 'timeAttributes'
#     """
#     js_code = """
#     function getUniqueH1sWithTimeAttributes() {
#         const results = [];
#         const seenH1Classes = new Set();

#         const containers = document.querySelectorAll("div");

#         containers.forEach(container => {
#             const h2 = container.querySelector("h2");
#             if (!h2) return;

#             const h1 = container.querySelector(":scope > div h1");
#             if (!h1) return;

#             const h1Text = (h1.textContent || "").trim();
#             if (!h1Text) return;

#             const h1Class = h1.className || "";
#             if (seenH1Classes.has(h1Class)) return;
#             seenH1Classes.add(h1Class);

#             const timeEl = container.querySelector("h1 time");
#             let timeAttributes = null;
#             if (timeEl) {
#                 timeAttributes = {};
#                 for (const attr of timeEl.attributes) {
#                     timeAttributes[attr.name] = attr.value;
#                 }
#             }

#             results.push({
#                 h1Class: h1Class,
#                 h2Text: (h2.textContent || "").trim(),
#                 h1Text: h1Text,
#                 timeAttributes: timeAttributes
#             });
#         });

#         return results;
#     }

#     return getUniqueH1sWithTimeAttributes();
#     """
#     # Execute the JS in the context of the page
#     return driver.execute_script(js_code)



# **Pseudo Logic:**

# 1. **Get all div elements** on the page.
# 2. **Loop through each div**:
#    a. Check if it contains an `<a>` element with `href = handle_name`.
#    b. Check if it contains a `<time>` element.
# 3. **Filter out divs that are not innermost**:

#    * For each candidate div, check if any **child div** also contains both `<a>` and `<time>`.
#    * If yes, skip this div; if no, mark it as the innermost div.
# 4. Once the innermost div is found:
#    a. Extract its `class` attribute.
#    b. Extract the `<a>` element’s `href` and `src` attributes.
#    c. Extract the `<time>` element’s `datetime` attribute.
# 5. **Get sibling elements** of the innermost div:

#    * Exclude the innermost div itself.
#    * Collect the **text content** from each sibling, trimming empty strings.
# 6. **Return all collected data** as an object:

#    * `topDivClass`
#    * `aHref`
#    * `aSrc`
#    * `timeDatetime`
#    * `siblingTexts` (array of strings)


# #Update: This function works.
# def get_post_title_data(driver, variable_a, timeout=5):
#     """
#     Extract data from the innermost div containing an <a> with href=variable_a and <time>.

#     Args:
#         driver: Selenium WebDriver instance.
#         variable_a: The href string to search for.

#     Returns:
#         dict with keys: topDivClass, aHref, aSrc, timeDatetime, siblingTexts
#     """
#     random_delay(2, 4.5)  # small wait to ensure content is fully loaded
#     variable_a_js = json.dumps(variable_a)  # safely quote special characters
    
#     js_code = f"""
#     function getPostTitleData(variableA) {{
#         const divs = Array.from(document.querySelectorAll('div'));
#         let innermostDiv = null;

#         for (const div of divs) {{
#             const aEl = div.querySelector(`a[href="${{variableA}}"]`);
#             const timeEl = div.querySelector('time');

#             if (aEl && timeEl) {{
#                 const childDivs = div.querySelectorAll('div');
#                 let hasNestedBoth = false;

#                 for (const child of childDivs) {{
#                     if (child.querySelector(`a[href="${{variableA}}"]`) && child.querySelector('time')) {{
#                         hasNestedBoth = true;
#                         break;
#                     }}
#                 }}

#                 if (!hasNestedBoth) {{
#                     innermostDiv = div;
#                 }}
#             }}
#         }}

#         if (!innermostDiv) return null;

#         const aEl = innermostDiv.querySelector(`a[href="${{variableA}}"]`);
#         const timeEl = innermostDiv.querySelector('time');

#         const data = {{
#             topDivClass: innermostDiv.className,
#             aHref: aEl ? aEl.getAttribute('href') : null,
#             aSrc: aEl ? aEl.getAttribute('src') : null,
#             timeDatetime: timeEl ? timeEl.getAttribute('datetime') : null,
#             siblingTexts: []
#         }};

#         const parent = innermostDiv.parentElement;
#         if (parent) {{
#             const siblings = Array.from(parent.children).filter(el => el !== innermostDiv);
#             data.siblingTexts = siblings
#                 .map(sib => sib.textContent.trim())
#                 .filter(t => t.length > 0);
#         }}

#         return data;
#     }}

#     return getPostTitleData({variable_a_js});
#     """

#     logging.info(js_code)
#     return driver.execute_script(js_code)


# def get_post_title_data_org(driver, variable_a, timeout=10):
#     """
#     Extract data from the innermost div containing an <a> with href=variable_a and <time>.
#     This version handles iframes, dynamic content, and JavaScript execution issues.

#     Args:
#         driver: Selenium WebDriver instance
#         variable_a: The href string to search for
#         timeout: Maximum time to wait for elements (default: 10 seconds)

#     Returns:
#         dict with keys: topDivClass, aHref, aSrc, timeDatetime, siblingTexts
#         or None if not found
#     """
#     original_window = driver.current_window_handle
    
#     try:
#         # Switch to default content first
#         driver.switch_to.default_content()
        
#         # Check for and handle iframes
#         iframes = driver.find_elements(By.TAG_NAME, "iframe")
#         element_found = False
        
#         # First try main document
#         try:
#             WebDriverWait(driver, 3).until(
#                 EC.presence_of_element_located((By.XPATH, f'//a[@href="{variable_a}"]'))
#             )
#             element_found = True
#             logging.info(f"Found <a> with href={variable_a} in main document")
#         except TimeoutException:
#             # If not found in main document, check iframes
#             for iframe in iframes:
#                 try:
#                     driver.switch_to.frame(iframe)
#                     WebDriverWait(driver, 3).until(
#                         EC.presence_of_element_located((By.XPATH, f'//a[@href="{variable_a}"]'))
#                     )
#                     element_found = True
#                     logging.info(f"Found <a> with href={variable_a} in iframe")
#                     break
#                 except TimeoutException:
#                     driver.switch_to.default_content()
#                     continue
            
#         if not element_found:
#             logging.warning(f"Element with href {variable_a} not found in main document or iframes")
#             return None
        
#         # Wait a bit more for dynamic content to stabilize
#         time.sleep(1)
        
#         # Prepare JavaScript code with proper error handling
#         js_code = """
#         function getPostTitleData(variableA) {
#             try {
#                 const divs = Array.from(document.querySelectorAll('div'));
#                 let innermostDiv = null;

#                 for (const div of divs) {
#                     const aEl = div.querySelector('a[href="' + variableA + '"]');
#                     const timeEl = div.querySelector('time');

#                     if (aEl && timeEl) {
#                         const childDivs = div.querySelectorAll('div');
#                         let hasNestedBoth = false;

#                         for (const child of childDivs) {
#                             if (child.querySelector('a[href="' + variableA + '"]') && child.querySelector('time')) {
#                                 hasNestedBoth = true;
#                                 break;
#                             }
#                         }

#                         if (!hasNestedBoth) {
#                             innermostDiv = div;
#                         }
#                     }
#                 }

#                 if (!innermostDiv) {
#                     console.log('No innermost div found');
#                     return null;
#                 }

#                 const aEl = innermostDiv.querySelector('a[href="' + variableA + '"]');
#                 const timeEl = innermostDiv.querySelector('time');

#                 const data = {
#                     topDivClass: innermostDiv.className,
#                     aHref: aEl ? aEl.getAttribute('href') : null,
#                     aSrc: aEl ? aEl.getAttribute('src') : null,
#                     timeDatetime: timeEl ? timeEl.getAttribute('datetime') : null,
#                     siblingTexts: []
#                 };

#                 const parent = innermostDiv.parentElement;
#                 if (parent) {
#                     const siblings = Array.from(parent.children).filter(el => el !== innermostDiv);
#                     data.siblingTexts = siblings
#                         .map(sib => sib.textContent.trim())
#                         .filter(t => t.length > 0);
#                 }

#                 return data;
#             } catch (error) {
#                 console.error('Error in getPostTitleData:', error);
#                 return null;
#             }
#         }
        
#         return getPostTitleData(arguments[0]);
#         """
        
#         # Execute JavaScript with the variable
#         result = driver.execute_script(js_code, variable_a)
        
#         if not result:
#             logging.warning("JavaScript executed but returned no results")
            
#         return result
        
#     except JavascriptException as e:
#         logging.error(f"JavaScript execution error: {e}")
#         return None
#     except Exception as e:
#         logging.error(f"Unexpected error: {e}")
#         return None
#     finally:
#         # Always return to default content and original window
#         try:
#             driver.switch_to.default_content()
#             if original_window in driver.window_handles:
#                 driver.switch_to.window(original_window)
#         except:
#             pass

# def extract_innermost_div_data_selenium(driver, variable_a, iframe_selector=None, timeout=10):
#     # Switch to iframe if needed
#     if iframe_selector:
#         WebDriverWait(driver, timeout).until(
#             EC.frame_to_be_available_and_switch_to_it((By.CSS_SELECTOR, iframe_selector))
#         )

#     # Wait for at least one <a> with href=variable_a
#     WebDriverWait(driver, timeout).until(
#         EC.presence_of_element_located((By.CSS_SELECTOR, f'a[href="{variable_a}"]'))
#     )

#     # Find all divs
#     divs = driver.find_elements(By.TAG_NAME, 'div')
#     innermost = None

#     for div in divs:
#         try:
#             a_el = div.find_element(By.CSS_SELECTOR, f'a[href="{variable_a}"]')
#             time_el = div.find_element(By.TAG_NAME, 'time')
#         except:
#             continue  # skip divs missing <a> or <time>

#         # Check if any child div also contains both
#         child_divs = div.find_elements(By.TAG_NAME, 'div')
#         if any(
#             (child.find_elements(By.CSS_SELECTOR, f'a[href="{variable_a}"]') and
#              child.find_elements(By.TAG_NAME, 'time'))
#             for child in child_divs
#         ):
#             continue

#         innermost = div

#     if not innermost:
#         if iframe_selector:
#             driver.switch_to.default_content()
#         return None

#     # Extract data
#     a_el = innermost.find_element(By.CSS_SELECTOR, f'a[href="{variable_a}"]')
#     time_el = innermost.find_element(By.TAG_NAME, 'time')
#     parent = innermost.find_element(By.XPATH, '..')
#     siblings = [sib.text.strip() for sib in parent.find_elements(By.XPATH, '*') if sib != innermost and sib.text.strip()]

#     data = {
#         'topDivClass': innermost.get_attribute('class'),
#         'aHref': a_el.get_attribute('href'),
#         'aSrc': a_el.get_attribute('src') or None,
#         'timeDatetime': time_el.get_attribute('datetime'),
#         'siblingTexts': siblings
#     }

#     if iframe_selector:
#         driver.switch_to.default_content()

#     return data

def scroll_with_mouse(
    self,
    steps: int = 10,
    min_step: int = 150,
    max_step: int = 400,
    min_delay: float = 0.2,
    max_delay: float = 0.6
):
    """
    Scrolls down the page like a human using random wheel steps.
    
    Args:
        steps (int): How many scroll actions to perform.
        min_step (int): Minimum pixels per scroll.
        max_step (int): Maximum pixels per scroll.
        min_delay (float): Minimum pause between steps.
        max_delay (float): Maximum pause between steps.
    """
    actions = ActionChains(self.driver)
    for _ in range(steps):
        delta_y = random.randint(min_step, max_step)  # random scroll size
        actions.scroll_by_amount(0, delta_y).perform()
        time.sleep(random.uniform(min_delay, max_delay))

def save_intermediate(post_data, tmp_file):
    """Append a single post_data dict to a JSONL tmp file."""
    with open(tmp_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(post_data, ensure_ascii=False) + "\n")

def clear_tmp_file(tmp_file):
    """Clear the tmp file after results are flushed to final."""
    try:
        open(tmp_file, "w").close()
    except Exception as e:
        logger.warning(f"Failed to clear tmp file {tmp_file}: {e}")



# def scrape_posts_in_batches(
#     backend,
#     post_elements,
#     config,
#     batch_size=3,
#     save_every=5,
#     output_dir=".",
#     tab_open_retries=4,
#     debug=False
# ):
#     """
#     Robust batch scraper that opens posts in new tabs, scrapes them, closes each tab,
#     and saves results periodically.

#     Important behaviors/fixes:
#     - DOES NOT call `window.location.href` (that navigates the current tab)
#     - Waits for new window handle reliably (with small retries)
#     - Always closes the scraped tab in a finally block and switches back to main handle
#     - Uses WebDriverWait for elements where appropriate (backend.extract_comments etc still
#       govern their own waits)
#     - Optional debug flag to keep tabs open / print extra info
#     """
#     results = {"scraped_posts": [], "skipped_posts": []}
#     total_scraped = 0

#     driver = backend.driver
#     main_handle = driver.current_window_handle
#     tmp_file = os.path.join(output_dir, f"scrape_results_tmp_{config.target_profile}.jsonl")

#     # helper: open href in new tab and return new handle (or raise)
#     def open_href_in_new_tab(href):
#         before_handles = set(driver.window_handles)
#         # Open new tab with specified href - this opens a new tab in most browsers
#         driver.execute_script("window.open(arguments[0], '_blank');", href)

#         # Wait for the new handle to appear
#         new_handle = None
#         for attempt in range(tab_open_retries):
#             after_handles = set(driver.window_handles)
#             diff = after_handles - before_handles
#             if diff:
#                 new_handle = diff.pop()
#                 break
#             time.sleep(0.5 + random.random() * 0.5)  # jittered wait
#         if not new_handle:
#             raise RuntimeError(f"New tab did not appear for href={href}")
#         return new_handle

#     # main loop over batches
#     for batch_start in range(0, len(post_elements), batch_size):
#         batch = post_elements[batch_start: batch_start + batch_size]
#         opened = []  # list of tuples (index, href, handle)

#         # --- open all posts in batch (in new tabs) ---
#         for i, post_element in enumerate(batch, start=batch_start):
#             # if i == 0:
#                 # continue
#             try:
#                 # href = post_element.get_attribute("href")
#                 href = post_element
#                 if not href:
#                     logger.warning(
#                         f"Skipping post {i+1} from profile {config.target_profile}: missing href."
#                     )
#                     results["skipped_posts"].append({
#                         "index": i,
#                         "reason": "missing href",
#                         "profile": config.target_profile
#                     })
#                     continue

#                 try:
#                     new_handle = open_href_in_new_tab(href)
#                     # optionally give the new tab a moment to start loading
#                     time.sleep(random.uniform(0.8, 1.5))
#                     opened.append((i, href, new_handle))
#                     logger.info(f"Opened post {i+1} in new tab: {href} -> handle {new_handle}")
#                 except Exception as e:
#                     logger.error(f"Failed to open new tab for post {i+1}: {e}")
#                     results["skipped_posts"].append({
#                         "index": i,
#                         "reason": f"failed to open tab: {str(e)}",
#                         "profile": config.target_profile
#                     })
#             except Exception as e:
#                 logger.exception(f"Unexpected error when preparing post {i+1}: {e}")
#                 results["skipped_posts"].append({
#                     "index": i,
#                     "reason": f"error extracting href: {str(e)}",
#                     "profile": config.target_profile
#                 })

#         # --- scrape each opened tab, one-by-one, ensuring closure ---
#         for i, href, handle in opened:
#             try:
#                 # switch to the new tab
#                 driver.switch_to.window(handle)
#                 human_mouse_move(driver,duration=random.randrange(1, 2))
#                 logger.info(f"Switched to tab {handle} for post {i} ({href})")
#                 # optional short wait for page to start loading
#                 try:
#                     # If you have a reliable "post content" element to wait for, use it here.
#                     # Example (commented): WebDriverWait(driver, page_load_timeout).until(
#                     #     EC.presence_of_element_located((By.CSS_SELECTOR, "article"))
#                     # )
#                     time.sleep(random.uniform(0.6, 1.2))
#                 except Exception:
#                     # non-fatal - proceed and rely on backend.extract_* waits
#                     logger.debug("Page load wait did not find expected element, continuing.")

#                 post_id = f"post_{i}"
#                 post_data = {
#                     "post_url": href,
#                     "post_id": post_id,
#                     "post_title": None,
#                     "post_images": [],
#                     "post_comments": [],
#                 }

#                 # # Comments
#                 # try:
#                 #     post_data["post_comments"] = backend.extract_comments(steps=80) or []
#                 # except Exception as e:
#                 #     logger.error(f"Comments extraction failed for {href}: {e}")
#                 #     logger.debug(traceback.format_exc())
#                 # Title / metadata
#                 try:
#                     handle_slug = f"/{config.target_profile}/"
#                     logger.info(f"Extracting title data for {href} with handle {handle_slug}")
#                     post_data["post_title"] = get_post_title_data(driver, handle_slug) or ""
#                 except Exception as e:
#                     logger.error(f"Title extraction failed for {href}: {e}")
#                     logger.debug(traceback.format_exc())

#                 # Images
#                 try:
#                     post_data["post_images"] = images_from_post(driver) or []
#                     logger.info(f"Images extraction successful for {href}")
#                     logger.info(f'{post_data["post_images"]}')
#                 except Exception as e:
#                     logger.error(f"Images extraction failed for {href}: {e}")
#                     logger.debug(traceback.format_exc())

#                 # Likes / other sections
#                 try:
#                     post_data["likes"] = get_section_with_highest_likes(driver) or {}
#                     logger.info(f"Likes extraction successful for {href}")
#                 except Exception as e:
#                     logger.error(f"Likes extraction failed for {href}: {e}")
#                     logger.debug(traceback.format_exc())
                
#                 # comments
#                 try:
#                     post_data["post_comments_gif"] = scrape_comments_with_gif(backend.driver) or []
#                 except Exception as e:
#                     logger.error(f"Comments extraction with gif failed for {href}: {e}")
#                     logger.debug(traceback.format_exc())


#                 results["scraped_posts"].append(post_data)
#                 total_scraped += 1
#                 logger.info(f"Scraped post {i} ({href}). Total scraped: {total_scraped}")

#                 # --- save every result immediately to tmp file ---
#                 try:
#                     save_intermediate(post_data, tmp_file)
#                 except Exception as e:
#                     logger.warning(f"Failed to write tmp result for {href}: {e}")

#                 # --- every N posts, save final and clear tmp ---
#                 if total_scraped % save_every == 0:
#                     save_scrape_results(results, output_dir,config)
#                     clear_tmp_file(tmp_file)
#                     logger.info(f"Saved results after {total_scraped} scraped posts.")


#             except Exception as e:
#                 logger.exception(f"Unexpected error while scraping post {i} ({href}): {e}")
#                 results["skipped_posts"].append({
#                     "index": i,
#                     "reason": str(e),
#                     "profile": config.target_profile
#                 })
#             finally:
#                 # Ensure this tab is closed and we switch back to a known handle.
#                 try:
#                     if debug:
#                         logger.info(f"DEBUG mode: leaving tab {handle} open.")
#                     else:
#                         driver.close()
#                         logger.debug(f"Closed tab {handle}")
#                 except Exception as e:
#                     logger.warning(f"Error closing tab {handle}: {e}")
#                 # switch back to main handle (if it's still present) or to any remaining handle
#                 handles = driver.window_handles
#                 if not handles:
#                     logger.info("No browser windows left after closing tab.")
#                     return results
#                 # prefer main_handle if still available
#                 if main_handle in handles:
#                     driver.switch_to.window(main_handle)
#                 else:
#                     # fallback to last handle
#                     driver.switch_to.window(handles[0])
#                 logger.debug(f"Switched back to handle {driver.current_window_handle}")

#         # optional: jittered wait between batches to mimic human rate-limits
#         random_delay(config.rate_limit_seconds_min, config.rate_limit_seconds_max)

#     # final save
#     if results["scraped_posts"] or results["skipped_posts"]:
#         save_scrape_results(results, output_dir, config)
#         clear_tmp_file(tmp_file)
#         logger.info("Saved final scrape results.")

#     return results


def save_scrape_results(results: dict, output_dir: str, config: dict):
    """
    Save scraped and skipped posts to JSONL files.

    Args:
        results: dict with keys "scraped_posts" and "skipped_posts"
        output_dir: path to save files
    """
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    metadata_file = config.data.metadata_path
    skipped_file = config.data.skipped_path

    # Save scraped posts
    if results.get("scraped_posts"):
        with open(metadata_file, "a", encoding="utf-8") as f:
            for post in results["scraped_posts"]:
                f.write(json.dumps(post, ensure_ascii=False) + "\n")

    # Save skipped posts
    if results.get("skipped_posts"):
        with open(skipped_file, "a", encoding="utf-8") as f:
            for post in results["skipped_posts"]:
                f.write(json.dumps(post, ensure_ascii=False) + "\n")
    # Clear results list after saving
    results["scraped_posts"].clear()
    results["skipped_posts"].clear()

import time
import random
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException

# def human_like_scroll_container(driver,
#                                 top_div_selector=None,
#                                 scroll_steps=4,
#                                 min_step_px=100,
#                                 max_step_px=350,
#                                 micro_pause=(0.25, 0.8),
#                                 read_pause=(1.0, 2.2),
#                                 max_scrolls=20,
#                                 wait_timeout=10):
#     """
#     Find the comments scroll container (structural heuristic) and scroll it in a human-like way.

#     Args:
#         driver: Selenium WebDriver instance (page already loaded).
#         top_div_selector: optional CSS selector to narrow the topDiv search (if you already know one).
#         scroll_steps: number of micro-step scrolls per iteration (your requested param).
#         min_step_px/max_step_px: pixel range for each micro-step.
#         micro_pause: (min,max) seconds sleep between micro-steps.
#         read_pause: (min,max) seconds sleep after each group of micro-steps (simulate reading).
#         max_scrolls: maximum number of iterations (group of micro-steps).
#         wait_timeout: seconds to wait searching for a suitable container before raising TimeoutException.

#     Returns:
#         dict with keys:
#             - 'selector': short CSS selector returned from page JS (string or None)
#             - 'container': Selenium WebElement for the chosen container
#             - 'iterations': number of iterations performed
#             - 'last_height': final scrollHeight observed
#     Raises:
#         TimeoutException if a container couldn't be found in wait_timeout seconds.
#     """

#     js_find_container = r"""
#     (function(sel){
#         function isScrollableStyle(el){
#             if(!el) return false;
#             const s = window.getComputedStyle(el);
#             const oy = s.overflowY || s.overflow || '';
#             return /auto|scroll|overlay/i.test(oy) && el.scrollHeight > el.clientHeight;
#         }
#         function hasOverflowPotential(el){
#             if(!el) return false;
#             const s = window.getComputedStyle(el);
#             const oy = s.overflowY || s.overflow || '';
#             return /auto|scroll|overlay|hidden/i.test(oy);
#         }
#         function cssPath(el){
#             if(!el) return null;
#             if(el.id) return '#' + el.id;
#             const parts = [];
#             let cur = el;
#             while(cur && cur.nodeType === 1 && cur.tagName.toLowerCase() !== 'html') {
#                 let part = cur.tagName.toLowerCase();
#                 if(cur.className){
#                     const cls = String(cur.className).split(/\\s+/).filter(Boolean)[0];
#                     if(cls) part += '.' + cls.replace(/[^a-zA-Z0-9_-]/g,'');
#                 } else {
#                     const parent = cur.parentElement;
#                     if(parent){
#                         const idx = Array.from(parent.children).indexOf(cur) + 1;
#                         part += ':nth-child(' + idx + ')';
#                     }
#                 }
#                 parts.unshift(part);
#                 cur = cur.parentElement;
#                 if(parts.length > 6) break;
#             }
#             return parts.length ? parts.join(' > ') : el.tagName.toLowerCase();
#         }

#         const selector = sel || null;
#         const allDivs = selector ? Array.from(document.querySelectorAll(selector)) : Array.from(document.querySelectorAll('div'));
#         const topDivs = allDivs.filter(topDiv => {
#             try {
#                 const profileDiv = topDiv.querySelector('div > div > div');
#                 const candidates = Array.from(topDiv.querySelectorAll('div > div > div'));
#                 const commentDiv = candidates.find(div => !div.querySelector('span a, span time'));
#                 return !!profileDiv && !!commentDiv;
#             } catch(e){
#                 return false;
#             }
#         });

#         if(topDivs.length === 0) return null;

#         const map = new Map();
#         topDivs.forEach(td => {
#             let el = td;
#             const visited = new Set();
#             while(el && el !== document.documentElement && !visited.has(el)){
#                 visited.add(el);
#                 if(el.nodeType === 1){
#                     const entry = map.get(el) || {count: 0, scrollable: false, overflowPotential: false};
#                     entry.count += 1;
#                     if(isScrollableStyle(el)) entry.scrollable = true;
#                     if(hasOverflowPotential(el)) entry.overflowPotential = true;
#                     map.set(el, entry);
#                 }
#                 el = el.parentElement;
#             }
#         });

#         const candidates = Array.from(map.entries()).map(([el, meta]) => {
#             return {el: el, count: meta.count, scrollable: meta.scrollable, overflowPotential: meta.overflowPotential,
#                     gap: (el.scrollHeight - el.clientHeight)};
#         });

#         if(candidates.length === 0) return null;

#         candidates.sort((a,b) => {
#             if(a.scrollable !== b.scrollable) return a.scrollable ? -1 : 1;
#             if(a.count !== b.count) return b.count - a.count;
#             if(a.overflowPotential !== b.overflowPotential) return a.overflowPotential ? -1 : 1;
#             return b.gap - a.gap;
#         });

#         let best = candidates.find(c => c.count >= 3) || candidates[0];
#         if(best.gap <= 0){
#             const positive = candidates.find(c => c.gap > 0 && (c.scrollable || c.overflowPotential));
#             if(positive) best = positive;
#         }

#         return [best.el, cssPath(best.el)];
#     })(arguments[0]);
#     """

#     # wait & find container (within wait_timeout)
#     end_time = time.time() + float(wait_timeout)
#     container_info = None
#     while time.time() < end_time:
#         try:
#             container_info = driver.execute_script(js_find_container, top_div_selector)
#         except Exception:
#             container_info = None
#         if container_info:
#             break
#         time.sleep(0.2)
#     if not container_info:
#         raise TimeoutException("Couldn't find comments/container within timeout. Provide top_div_selector or increase wait_timeout.")

#     # container_info is expected to be [WebElement, selector_string]
#     container_el = container_info[0] if isinstance(container_info, (list, tuple)) and len(container_info) > 0 else None
#     chosen_selector = container_info[1] if isinstance(container_info, (list, tuple)) and len(container_info) > 1 else None

#     # fallback to document scroller if needed
#     if not container_el:
#         container_el = driver.execute_script("return document.scrollingElement || document.documentElement || document.body;")
#         chosen_selector = chosen_selector or 'document.scrollingElement'

#     # now scroll in human-like micro-steps
#     last_height = -1
#     iterations = 0
#     for i in range(int(max_scrolls)):
#         iterations += 1
#         for _ in range(max(1, int(scroll_steps))):
#             step_px = random.randint(int(min_step_px), int(max_step_px))
#             try:
#                 driver.execute_script("arguments[0].scrollTop += arguments[1];", container_el, step_px)
#             except StaleElementReferenceException:
#                 # try to re-find container once
#                 try:
#                     container_info = driver.execute_script(js_find_container, top_div_selector) or driver.execute_script("return [document.scrollingElement || document.documentElement || document.body, 'document.scrollingElement'];")
#                     if isinstance(container_info, (list, tuple)) and container_info[0]:
#                         container_el = container_info[0]
#                         chosen_selector = container_info[1] or chosen_selector
#                     else:
#                         container_el = container_info
#                 except Exception:
#                     # last resort: document scroller
#                     container_el = driver.execute_script("return document.scrollingElement || document.documentElement || document.body;")
#                 # retry the scroll once
#                 try:
#                     driver.execute_script("arguments[0].scrollTop += arguments[1];", container_el, step_px)
#                 except Exception:
#                     pass
#             time.sleep(random.uniform(float(micro_pause[0]), float(micro_pause[1])))

#         # reading pause
#         time.sleep(random.uniform(float(read_pause[0]), float(read_pause[1])))

#         # check for new content
#         try:
#             new_height = driver.execute_script("return arguments[0].scrollHeight;", container_el)
#         except StaleElementReferenceException:
#             # re-find container and read height
#             container_info = driver.execute_script(js_find_container, top_div_selector) or driver.execute_script("return [document.scrollingElement || document.documentElement || document.body, 'document.scrollingElement'];")
#             if isinstance(container_info, (list, tuple)) and container_info[0]:
#                 container_el = container_info[0]
#                 chosen_selector = container_info[1] or chosen_selector
#             new_height = driver.execute_script("return arguments[0].scrollHeight;", container_el)

#         if new_height == last_height:
#             break
#         last_height = new_height

#     return {
#         'selector': chosen_selector,
#         'container': container_el,
#         'iterations': iterations,
#         'last_height': last_height
#     }

import time
import random
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selenium.webdriver.common.by import By

# def human_scroll_and_scrape_comments(driver,
#                                      top_div_selector=None,
#                                      scroll_steps=4,
#                                      min_step_px=100,
#                                      max_step_px=350,
#                                      micro_pause=(0.25, 0.8),
#                                      read_pause=(1.0, 2.2),
#                                      max_scrolls=20,
#                                      wait_timeout=10):
#     """
#     Find the real comments scroll container via JS, scroll it in a human-like way,
#     and return parsed comments.

#     Parameters
#     ----------
#     driver : selenium.webdriver
#         Active webdriver instance, page already loaded to comments.
#     top_div_selector : str or None
#         Optional CSS selector for the "topDiv" comment blocks. If None, function
#         will search all <div>s using the structural heuristic (div > div > div).
#     scroll_steps : int
#         Number of micro scroll steps to perform per scroll iteration (human-like).
#     min_step_px, max_step_px : int
#         Pixel range for each micro-step.
#     micro_pause : tuple(float,float)
#         Pause (seconds) between micro-steps (random between these).
#     read_pause : tuple(float,float)
#         Pause (seconds) after a group of micro-steps to simulate reading.
#     max_scrolls : int
#         Max iterations of the (micro-steps + read pause) loop.
#     wait_timeout : int/float
#         Seconds to try to find a suitable comment container before raising TimeoutException.

#     Returns
#     -------
#     list of dict
#         Each dict has keys 'handle','date','comment','likes' (as returned by the parser JS).
#     """
#     # JS to find best scrollable ancestor and also return a short selector (returns [el, selector] or null)
#     js_find_container = r"""
#     (function(sel){
#         function isScrollableStyle(el){
#             if(!el) return false;
#             const s = window.getComputedStyle(el);
#             const oy = s.overflowY || s.overflow || '';
#             return /auto|scroll|overlay/i.test(oy) && el.scrollHeight > el.clientHeight;
#         }
#         function hasOverflowPotential(el){
#             if(!el) return false;
#             const s = window.getComputedStyle(el);
#             const oy = s.overflowY || s.overflow || '';
#             return /auto|scroll|overlay|hidden/i.test(oy);
#         }
#         function cssPath(el){
#             if(!el) return null;
#             if(el.id) return '#' + el.id;
#             const parts = [];
#             let cur = el;
#             while(cur && cur.nodeType === 1 && cur.tagName.toLowerCase() !== 'html') {
#                 let part = cur.tagName.toLowerCase();
#                 if(cur.className){
#                     const cls = String(cur.className).split(/\s+/).filter(Boolean)[0];
#                     if(cls) part += '.' + cls.replace(/[^a-zA-Z0-9_-]/g,'');
#                 } else {
#                     const parent = cur.parentElement;
#                     if(parent){
#                         const idx = Array.from(parent.children).indexOf(cur) + 1;
#                         part += ':nth-child(' + idx + ')';
#                     }
#                 }
#                 parts.unshift(part);
#                 cur = cur.parentElement;
#                 if(parts.length > 6) break;
#             }
#             return parts.length ? parts.join(' > ') : el.tagName.toLowerCase();
#         }

#         const selector = sel || null;
#         const allDivs = selector ? Array.from(document.querySelectorAll(selector)) : Array.from(document.querySelectorAll('div'));
#         const topDivs = allDivs.filter(topDiv => {
#             try {
#                 const profileDiv = topDiv.querySelector('div > div > div');
#                 const candidates = Array.from(topDiv.querySelectorAll('div > div > div'));
#                 const commentDiv = candidates.find(div => !div.querySelector('span a, span time'));
#                 return !!profileDiv && !!commentDiv;
#             } catch(e){
#                 return false;
#             }
#         });

#         if(topDivs.length === 0) return null;

#         const map = new Map();
#         topDivs.forEach(td => {
#             let el = td;
#             const visited = new Set();
#             while(el && el !== document.documentElement && !visited.has(el)){
#                 visited.add(el);
#                 if(el.nodeType === 1){
#                     const entry = map.get(el) || {count: 0, scrollable: false, overflowPotential: false};
#                     entry.count += 1;
#                     if(isScrollableStyle(el)) entry.scrollable = true;
#                     if(hasOverflowPotential(el)) entry.overflowPotential = true;
#                     map.set(el, entry);
#                 }
#                 el = el.parentElement;
#             }
#         });

#         const candidates = Array.from(map.entries()).map(([el, meta]) => {
#             return {el: el, count: meta.count, scrollable: meta.scrollable, overflowPotential: meta.overflowPotential,
#                     gap: (el.scrollHeight - el.clientHeight)};
#         });

#         if(candidates.length === 0) return null;

#         candidates.sort((a,b) => {
#             if(a.scrollable !== b.scrollable) return a.scrollable ? -1 : 1;
#             if(a.count !== b.count) return b.count - a.count;
#             if(a.overflowPotential !== b.overflowPotential) return a.overflowPotential ? -1 : 1;
#             return b.gap - a.gap;
#         });

#         let best = candidates.find(c => c.count >= 3) || candidates[0];
#         if(best.gap <= 0){
#             const positive = candidates.find(c => c.gap > 0 && (c.scrollable || c.overflowPotential));
#             if(positive) best = positive;
#         }

#         // return the element and a short selector for later use
#         return [best.el, cssPath(best.el)];
#     })(arguments[0]);
#     """
#     # pdb.set_trace()
#     # small helper to repeatedly try to find a container until wait_timeout
#     end_time = time.time() + wait_timeout
#     container_info = None
#     while time.time() < end_time:
#         try:
#             container_info = driver.execute_script(js_find_container, top_div_selector)
#         except Exception:
#             container_info = None
#         if container_info:
#             break
#         time.sleep(0.2)
#     if not container_info:
#         raise TimeoutException("Couldn't find comments topDiv/container within timeout. Try supplying top_div_selector.")

#     # container_info expected [WebElement, selector_string]
#     container_el = container_info[0]  # Selenium WebElement
#     chosen_selector = container_info[1] if len(container_info) > 1 else None

#     # Fallback: if container_el is falsy, use document.scrollingElement
#     if container_el is None:
#         container_el = driver.execute_script("return document.scrollingElement || document.documentElement || document.body;")

#     # scrolling loop (human-like)
#     last_height = -1
#     for _ in range(max_scrolls):
#         # do 'scroll_steps' micro-step scrolls
#         for _step in range(max(1, int(scroll_steps))):
#             step_px = random.randint(int(min_step_px), int(max_step_px))
#             try:
#                 driver.execute_script("arguments[0].scrollTop += arguments[1];", container_el, step_px)
#             except StaleElementReferenceException:
#                 # re-find container and retry once
#                 container_info = driver.execute_script(js_find_container, top_div_selector) or driver.execute_script("return document.scrollingElement || document.documentElement || document.body;")
#                 container_el = container_info[0] if isinstance(container_info, (list,tuple)) and container_info[0] else container_info
#                 driver.execute_script("arguments[0].scrollTop += arguments[1];", container_el, step_px)
#             time.sleep(random.uniform(float(micro_pause[0]), float(micro_pause[1])))

#         # reading pause
#         time.sleep(random.uniform(float(read_pause[0]), float(read_pause[1])))

#         # check whether new content loaded
#         try:
#             new_height = driver.execute_script("return arguments[0].scrollHeight;", container_el)
#         except StaleElementReferenceException:
#             container_info = driver.execute_script(js_find_container, top_div_selector) or driver.execute_script("return document.scrollingElement || document.documentElement || document.body;")
#             container_el = container_info[0] if isinstance(container_info, (list,tuple)) and container_info[0] else container_info
#             new_height = driver.execute_script("return arguments[0].scrollHeight;", container_el)

#         if new_height == last_height:
#             break
#         last_height = new_height

#     # Parse comments using your parser JS and return to Python
#     js_parse = r"""
#     (function parseComments(){
#         const results = [];
#         const seen = new Set();
#         // Heuristic parser (adjust selectors inside if needed)
#         const topDivs = Array.from(document.querySelectorAll('div')).filter(topDiv => {
#             try {
#                 const profileDiv = topDiv.querySelector('div > div > div');
#                 const candidates = Array.from(topDiv.querySelectorAll('div > div > div'));
#                 const commentDiv = candidates.find(div => !div.querySelector('span a, span time'));
#                 return !!profileDiv && !!commentDiv;
#             } catch(e){
#                 return false;
#             }
#         });

#         topDivs.forEach(topDiv => {
#             const profileDiv = topDiv.querySelector('div > div > div');
#             const commentDiv = Array.from(topDiv.querySelectorAll('div > div > div'))
#                 .find(div => !div.querySelector('span a, span time'));
#             if (!profileDiv || !commentDiv) return;

#             const data = { likes: null, handle: null, date: null, comment: null };

#             const likeSpan = Array.from(topDiv.querySelectorAll('span'))
#                 .map(s => s.innerText && s.innerText.trim())
#                 .filter(Boolean)
#                 .find(t => /\b\d{1,3}(?:,\d{3})*(?:\.\d+)?[kKmM]?\s+likes?\b/i.test(t));
#             if (likeSpan) data.likes = likeSpan;

#             const spans = profileDiv.querySelectorAll('span');
#             spans.forEach(span => {
#                 const aTag = span.querySelector('a');
#                 if (aTag && !data.handle) data.handle = aTag.innerText.trim();
#                 const timeTag = span.querySelector('time');
#                 if (timeTag && !data.date) data.date = timeTag.innerText.trim();
#             });

#             const text = commentDiv.innerText.trim();
#             if (text) data.comment = text;

#             if (data.comment && data.date) {
#                 const key = (data.handle || '') + '::' + data.comment;
#                 if (!seen.has(key)) {
#                     seen.add(key);
#                     results.push(data);
#                 }
#             }
#         });

#         return results;
#     })();
#     """
#     comments = driver.execute_script(js_parse)
#     return comments


from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import time

def find_comment_container(driver, min_matches=3):
    js_code = """
        return (function(minMatches){
            const logs = [];

            function log(...args){
                logs.push(args.join(" "));
            }

            function isScrollableStyle(el){
                if(!el) return false;
                const s = window.getComputedStyle(el);
                const oy = s.overflowY || s.overflow || '';
                return /auto|scroll|overlay/i.test(oy) && el.scrollHeight > el.clientHeight;
            }
            function hasOverflowPotential(el){
                if(!el) return false;
                const s = window.getComputedStyle(el);
                const oy = s.overflowY || s.overflow || '';
                return /auto|scroll|overlay|hidden/i.test(oy);
            }
            function info(el){
                if(!el) return null;
                log("→ Candidate element:", el.tagName, "class:", el.className || "(no class)");
                log("   scrollHeight:", el.scrollHeight, "clientHeight:", el.clientHeight);
                log("   overflow-y:", window.getComputedStyle(el).overflowY);
                return el;
            }
            function cssPath(el){
                if(!el) return null;
                if(el.id) return `#${el.id}`;
                const parts = [];
                let cur = el;
                while(cur && cur.nodeType === 1 && cur.tagName.toLowerCase() !== 'html'){
                    let part = cur.tagName.toLowerCase();
                    if(cur.className){
                        const cls = String(cur.className).split(/\\s+/).filter(Boolean)[0];
                        if(cls) part += `.${cls.replace(/[^a-zA-Z0-9_-]/g,'')}`;
                    } else {
                        const parent = cur.parentElement;
                        if(parent){
                            const idx = Array.from(parent.children).indexOf(cur) + 1;
                            part += `:nth-child(${idx})`;
                        }
                    }
                    parts.unshift(part);
                    cur = cur.parentElement;
                    if(parts.length > 6) break;
                }
                return parts.length ? parts.join(' > ') : el.tagName.toLowerCase();
            }

            log("🚀 Starting container detection with minMatches =", minMatches);

            const allDivs = Array.from(document.querySelectorAll('div'));
            const topDivs = allDivs.filter(topDiv => {
                try {
                    const profileDiv = topDiv.querySelector('div > div > div');
                    const candidates = Array.from(topDiv.querySelectorAll('div > div > div'));
                    const commentDiv = candidates.find(div => !div.querySelector('span a, span time'));
                    return !!profileDiv && !!commentDiv;
                } catch(e){
                    return false;
                }
            });

            if(topDivs.length === 0){
                log("⚠️ No matching comment topDivs found.");
                return {logs};
            }
            log("✅ Found", topDivs.length, "candidate comment topDivs.");

            const map = new Map();
            topDivs.forEach(td => {
                let el = td;
                const visited = new Set();
                while(el && el !== document.documentElement && !visited.has(el)){
                    visited.add(el);
                    if(el.nodeType === 1){
                        const entry = map.get(el) || {count: 0, scrollable: false, overflowPotential: false};
                        entry.count += 1;
                        if(isScrollableStyle(el)) entry.scrollable = true;
                        if(hasOverflowPotential(el)) entry.overflowPotential = true;
                        map.set(el, entry);
                    }
                    el = el.parentElement;
                }
            });

            const candidates = Array.from(map.entries()).map(([el, meta]) => {
                return {el, count: meta.count, scrollable: meta.scrollable, overflowPotential: meta.overflowPotential,
                        gap: (el.scrollHeight - el.clientHeight)};
            });

            if(candidates.length === 0){
                log("⚠️ No ancestor candidates collected.");
                return {logs};
            }

            candidates.sort((a,b) => {
                if(a.scrollable !== b.scrollable) return a.scrollable ? -1 : 1;
                if(a.count !== b.count) return b.count - a.count;
                if(a.overflowPotential !== b.overflowPotential) return a.overflowPotential ? -1 : 1;
                return b.gap - a.gap;
            });

            let best = candidates.find(c => c.count >= minMatches) || candidates[0];
            if(best.gap <= 0){
                const positive = candidates.find(c => c.gap > 0 && (c.scrollable || c.overflowPotential));
                if(positive) best = positive;
            }

            candidates.slice(0,3).forEach((c, idx) => {
                try {
                    c.el.style.outline = (idx===0) ? '3px solid red' : (idx===1) ? '3px dashed orange' : '2px dashed yellow';
                } catch(e){}
                log(`#${idx+1} candidate: count=${c.count}, scrollable=${c.scrollable}, gap=${c.gap}`);
                info(c.el);
            });

            const selector = cssPath(best.el);
            log("🎯 SELECTOR for chosen container:", selector);

            return {selector, logs};
        })(arguments[0]);
    """

    return driver.execute_script(js_code, min_matches)


import random
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains

# def human_scroll_bk(driver, selector, steps=10, min_step=100, max_step=400, min_pause=0.3, max_pause=1.2):
#     """
#     Scroll inside the element identified by `selector` in a human-like way.
    
#     Args:
#         driver: Selenium WebDriver instance
#         selector: CSS selector string for the scrollable container
#         steps: number of scroll increments
#         min_step: minimum scroll step in pixels
#         max_step: maximum scroll step in pixels
#         min_pause: minimum pause between steps (seconds)
#         max_pause: maximum pause between steps (seconds)
#     """
#     el = driver.find_element(By.CSS_SELECTOR, selector)
#     actions = ActionChains(driver)
    
#     for i in range(steps):
#         # Random scroll amount
#         scroll_by = random.randint(min_step, max_step)
#         if random.choice([True, False]):
#             human_mouse_move(driver, selector=selector,duration=random.randrange(1, 3))
#         # Execute JS to scroll the element
#         driver.execute_script("arguments[0].scrollBy(0, arguments[1]);", el, scroll_by)
        
#         # Optional: small mouse movement over the container (looks more human)
#         actions.move_to_element_with_offset(el, random.randint(10, 50), random.randint(10, 50)).perform()
        
#         # Random pause
#         pause = round(random.uniform(min_pause, max_pause), 2)
#         print(f"Step {i+1}/{steps}: scrolled by {scroll_by}px, sleeping {pause}s")
#         time.sleep(pause)
# import random
# import time
# from selenium.webdriver.common.by import By
# from selenium.webdriver.common.action_chains import ActionChains

def human_scroll(
    driver,
    selector,
    steps=10,
    min_step=180,
    max_step=400,
    min_pause=0.3,
    max_pause=1.1,
    max_retries=8,  # max consecutive retries with no height change
):
    """
    Scroll inside the element identified by `selector` in a human-like way.
    Stops early if bottom is reached or max_retries are hit.
    """
    el = driver.find_element(By.CSS_SELECTOR, selector)
    actions = ActionChains(driver)

    last_scroll_top = driver.execute_script("return arguments[0].scrollTop;", el)
    max_scroll_height = driver.execute_script("return arguments[0].scrollHeight;", el)

    retry_count = 0
    wait_retry_count = 0
    for i in range(steps):
        client_height = driver.execute_script("return arguments[0].clientHeight;", el)

        # Stop if at bottom
        if last_scroll_top + client_height >= max_scroll_height:
            print(f"Probably reached bottom at step {i+1}. retry count {wait_retry_count}")
            wait_retry_count += 1
            if wait_retry_count >= 3:
                print(f"Waiting too long at step {i+1}, giving up.")
                break
            random_delay(1, 3)
        wait_retry_count = 0
        # Random scroll amount
        scroll_by = random.randint(min_step, max_step)

        if random.choice([True, False, False, False]):
            human_mouse_move(driver, selector=selector, duration=random.randrange(1, 3))

        driver.execute_script("arguments[0].scrollBy(0, arguments[1]);", el, scroll_by)

        new_scroll_top = driver.execute_script("return arguments[0].scrollTop;", el)
        new_scroll_height = driver.execute_script("return arguments[0].scrollHeight;", el)

        if new_scroll_top == last_scroll_top and new_scroll_height == max_scroll_height:
            retry_count += 1
            random_delay(1, 4)
            print(f"No height change detected at step {i+1}, retry {retry_count}/{max_retries}")
            if retry_count >= max_retries:
                print(f"Max retries reached at step {i+1}, exiting scroll.")
                break
        else:
            retry_count = 0  # reset retries if height changed

        last_scroll_top = new_scroll_top
        max_scroll_height = new_scroll_height

        # Optional small mouse movement
        actions.move_to_element_with_offset(el, random.randint(10, 50), random.randint(10, 50)).perform()

        # Random pause
        pause = round(random.uniform(min_pause, max_pause), 2)
        print(f"Step {i+1}/{steps}: scrolled by {scroll_by}px, sleeping {pause}s")
        time.sleep(pause)



def human_mouse_move(
    driver: WebDriver,
    element: Optional[WebElement] = None,
    selector: Optional[str] = None,
    duration: float = 1.2,
    steps: int = 12,
    margin: int = 6,
    pause_jitter: Tuple[float, float] = (0.02, 0.12),
    use_action_chains: bool = True,
    seed: Optional[int] = None,
) -> Dict:
    """
    Move the mouse in a human-like randomized path over an element (or body if no element).
    
    Args:
        driver: Selenium WebDriver instance.
        element: Selenium WebElement to move over (preferred).
        selector: CSS selector to locate element (used only if element is None).
        duration: approx total time (seconds) to spend moving.
        steps: number of intermediate points (higher = smoother).
        margin: pixels inset from element edges for target points.
        pause_jitter: (min, max) pause between sub-movements in seconds (randomized).
        use_action_chains: if True use ActionChains.move_to_element_with_offset; otherwise dispatch JS MouseEvents.
        seed: optional RNG seed for reproducible movement (useful for debugging).
    
    Returns:
        dict with keys:
          - success: bool
          - points: list of (x, y, t) visited (client coordinates and timestamp)
          - error: error string if failed
    Notes:
        - In headless mode, visible movement may not be meaningful, but events still fire.
        - ActionChains offsets are computed relative to element's top-left.
    """
    if seed is not None:
        random.seed(seed)

    result = {"success": False, "points": [], "error": None}

    try:
        # Resolve element
        if element is None and selector:
            try:
                element = driver.find_element(By.CSS_SELECTOR, selector)
            except Exception as e:
                result["error"] = f"selector not found: {e}"
                return result

        # Get bounding rect (client coordinates)
        if element is not None:
            rect = driver.execute_script(
                "const r = arguments[0].getBoundingClientRect();"
                "return {left: r.left, top: r.top, width: r.width, height: r.height};",
                element,
            )
        else:
            # Use viewport (body) if no element
            vp = driver.execute_script(
                "return {left: 0, top: 0, width: Math.max(document.documentElement.clientWidth, window.innerWidth || 0),"
                "height: Math.max(document.documentElement.clientHeight, window.innerHeight || 0)};"
            )
            rect = vp

        # Sanity clamp
        width = max(1, int(rect.get("width", 1)))
        height = max(1, int(rect.get("height", 1)))
        left = float(rect.get("left", 0))
        top = float(rect.get("top", 0))

        # Ensure margin leaves room
        margin = max(0, min(margin, min(width // 3, height // 3)))

        # Starting point: center of element
        start_x = left + width / 2.0
        start_y = top + height / 2.0

        # Build a sequence of target points using smooth-ish random walk toward random edges/points
        points: List[Tuple[float, float]] = []
        for i in range(steps):
            # target region bias: sometimes nearer edges, sometimes center
            t = i / max(1, steps - 1)
            # sample within inner box
            x = random.uniform(left + margin, left + width - margin)
            y = random.uniform(top + margin, top + height - margin)

            # small lerp from previous toward new random target to smooth jumps
            if points:
                prev_x, prev_y = points[-1]
                # move fractionally toward new random target
                frac = random.uniform(0.2, 0.8)
                x = prev_x + (x - prev_x) * frac
                y = prev_y + (y - prev_y) * frac
            else:
                # first step should be close to center
                x = start_x + (x - start_x) * random.uniform(0.15, 0.6)
                y = start_y + (y - start_y) * random.uniform(0.15, 0.6)

            # clamp to element bounds
            x = max(left + 1, min(left + width - 1, x))
            y = max(top + 1, min(top + height - 1, y))
            points.append((x, y))

        # Add final subtle pause and maybe small corrective movement back toward center
        if random.random() < 0.4:
            points.append((start_x + random.uniform(-5, 5), start_y + random.uniform(-5, 5)))

        # Map points to timestamps distributed across duration
        now = time.time()
        timestamps = []
        for idx in range(len(points)):
            # distribute nonlinearly: small random jitter around equal spacing
            frac = (idx / max(1, len(points) - 1))
            ts = now + frac * duration + random.uniform(-0.02, 0.05)
            timestamps.append(ts)

        # Perform movements
        if use_action_chains:
            actions = ActionChains(driver)
            # Move to first point by moving to element and offset
            for (x, y), ts in zip(points, timestamps):
                # offsets relative to element top-left
                offset_x = int(round(x - left))
                offset_y = int(round(y - top))

                # clamp offsets to element sizes (ActionChains expects offsets inside element)
                offset_x = max(0, min(width - 1, offset_x))
                offset_y = max(0, min(height - 1, offset_y))

                try:
                    actions.move_to_element_with_offset(element if element is not None else driver.find_element(By.TAG_NAME, "body"), offset_x, offset_y)
                    actions.perform()
                except WebDriverException:
                    # fallback: attempt a JS dispatch if ActionChains fails mid-run
                    driver.execute_script(
                        """
                        (function(cx, cy){
                          const ev = new MouseEvent('mousemove', {bubbles:true, cancelable:true, clientX:cx, clientY:cy});
                          document.elementFromPoint(cx, cy)?.dispatchEvent(ev);
                        })(arguments[0], arguments[1]);
                        """,
                        int(round(x)), int(round(y))
                    )

                # sleep a bit (distributed)
                pause = random.uniform(pause_jitter[0], pause_jitter[1])
                time.sleep(pause)
                result["points"].append((int(round(x)), int(round(y)), time.time()))
        else:
            # Use JS synthetic MouseEvents (fires events on the element at client coordinates)
            dispatch_script = """
                (function(cx, cy){
                  const targ = document.elementFromPoint(cx, cy) || document.body;
                  const evMove = new MouseEvent('mousemove', {bubbles:true, cancelable:true, clientX:cx, clientY:cy});
                  const evOver = new MouseEvent('mouseover', {bubbles:true, cancelable:true, clientX:cx, clientY:cy});
                  targ.dispatchEvent(evMove);
                  targ.dispatchEvent(evOver);
                })(arguments[0], arguments[1]);
            """
            for (x, y), ts in zip(points, timestamps):
                try:
                    driver.execute_script(dispatch_script, int(round(x)), int(round(y)))
                except WebDriverException as e:
                    # ignore occasional failures
                    result.setdefault("js_errors", []).append(str(e))
                pause = random.uniform(pause_jitter[0], pause_jitter[1])
                time.sleep(pause)
                result["points"].append((int(round(x)), int(round(y)), time.time()))

        result["success"] = True
        return result

    except Exception as exc:
        result["error"] = str(exc)
        return result

# def move_over_selector(
#     driver,
#     selector,
#     duration=1.2,
#     steps=12,
#     margin=6,
#     pause_jitter=(0.02, 0.12),
#     use_action_chains=True,
#     wait_timeout=8,
#     seed=None,
# ):
#     """
#     Find element by CSS selector, scroll it into view, wait for presence/visibility,
#     then call human_mouse_move on it.

#     Returns the dict result produced by human_mouse_move.
#     Raises meaningful exceptions on failure.
#     """
#     # Wait for presence (you can change to visibility if you prefer)
#     el = WebDriverWait(driver, wait_timeout).until(
#         EC.presence_of_element_located((By.CSS_SELECTOR, selector))
#     )

#     # If element is present but possibly off-screen, scroll it to center of viewport
#     try:
#         driver.execute_script(
#             "arguments[0].scrollIntoView({block: 'center', inline: 'center', behavior: 'auto'});",
#             el,
#         )
#     except Exception:
#         # fallback: try a simpler scroll
#         try:
#             driver.execute_script("arguments[0].scrollIntoView(true);", el)
#         except Exception:
#             pass

#     # Tiny pause to let layout settle
#     time.sleep(0.18 + (seed or 0) * 0)  # small deterministic-ish pause if seed set

#     # call the existing human_mouse_move function (element preferred)
#     result = human_mouse_move(
#         driver=driver,
#         element=el,
#         duration=duration,
#         steps=steps,
#         margin=margin,
#         pause_jitter=pause_jitter,
#         use_action_chains=use_action_chains,
#         seed=seed,
#     )
#     return result

# def full_path(path:str):
#     return os.path.join(os.getcwd(), path)