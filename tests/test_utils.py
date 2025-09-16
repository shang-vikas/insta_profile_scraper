import unittest
from pathlib import Path
import os, sys
import json

# Adjust path to import from src
import sys
src_path = Path(__file__).resolve().parent.parent / 'src'
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from unittest.mock import MagicMock, patch

from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException

from igscraper.utils import (
    normalize_hashtags, cleanup_details, save_intermediate, save_scrape_results, clear_tmp_file, get_all_post_images_data, extract_post_title_details, scrape_carousel_images,
    scrape_comments_with_gif, get_section_with_highest_likes
)

class TestUtils(unittest.TestCase):
    """Unit tests for utility functions in utils.py."""

    def setUp(self):
        """Create a temporary directory for file-based tests."""
        self.test_dir = Path("tests/temp_test_files")
        self.test_dir.mkdir(exist_ok=True)

    def tearDown(self):
        """Clean up the temporary directory."""
        for f in self.test_dir.glob("*"):
            f.unlink()
        self.test_dir.rmdir()

    def test_normalize_hashtags(self):
        """Test the hashtag extraction utility function."""
        caption1 = "This is a great post! #awesome #python #coding"
        self.assertEqual(normalize_hashtags(caption1), ["#awesome", "#python", "#coding"])

        caption2 = "No hashtags here."
        self.assertEqual(normalize_hashtags(caption2), [])

        caption3 = "A #single hashtag."
        self.assertEqual(normalize_hashtags(caption3), ["#single"])

        caption4 = "Hashtag with numbers #v1 and special_chars #test_ing"
        self.assertEqual(normalize_hashtags(caption4), ["#v1", "#test_ing"])
        
        caption5 = None
        self.assertEqual(normalize_hashtags(caption5), [])

    def test_cleanup_details(self):
        """Test the data cleanup and deduplication logic for post details."""
        raw_data = [
            {
                "images": [
                    {"src": "img1.jpg", "alt": "alt1"},
                    {"src": "img1.jpg", "alt": "alt2"},  # Duplicate src, different alt
                    {"src": "img2.jpg", "alt": "alt3"},
                    {"src": "img1.jpg", "alt": "alt1"},  # Complete duplicate
                ],
                "links": [
                    {"href": "/link1", "text": "text1"},
                    {"href": "/link1", "text": "should be ignored"},  # Duplicate href
                    {"href": "/link2", "text": "text2"},
                ],
                "times": [
                    {"datetime": "T1", "text": "time1"},
                    {"datetime": "T1", "text": "should be ignored"},  # Duplicate datetime
                    {"datetime": "T2", "text": "time2"},
                ]
            }
        ]

        cleaned = cleanup_details(raw_data)
        self.assertEqual(len(cleaned), 1)
        item = cleaned[0]

        # Test image deduplication and alt text aggregation
        self.assertEqual(len(item["images"]), 2)
        img1 = next(i for i in item["images"] if i["src"] == "img1.jpg")
        self.assertEqual(sorted(img1["alt"]), sorted(["alt1", "alt2"]))

        # Test link deduplication
        self.assertEqual(len(item["links"]), 2)
        link1 = next(l for l in item["links"] if l["href"] == "/link1")
        self.assertEqual(link1["text"], "text1")

        # Test time deduplication
        self.assertEqual(len(item["times"]), 2)
        time1 = next(t for t in item["times"] if t["datetime"] == "T1")
        self.assertEqual(time1["text"], "time1")

    def test_save_intermediate_and_clear(self):
        """Test saving a single record to a temporary file and clearing it."""
        tmp_file = self.test_dir / "intermediate.jsonl"
        post_data = {"post_id": "123", "content": "test"}

        # Save one record
        save_intermediate(post_data, tmp_file)
        self.assertTrue(tmp_file.exists())
        with open(tmp_file, "r") as f:
            self.assertEqual(len(f.readlines()), 1)

        # Save another record
        save_intermediate(post_data, tmp_file)
        with open(tmp_file, "r") as f:
            self.assertEqual(len(f.readlines()), 2)

        # Clear the file
        clear_tmp_file(tmp_file)
        self.assertEqual(tmp_file.stat().st_size, 0)

    def test_save_scrape_results(self):
        """Test saving final scraped and skipped results to files."""
        # Mock config object with path attributes
        class MockDataConfig:
            metadata_path = self.test_dir / "metadata.jsonl"
            skipped_path = self.test_dir / "skipped.jsonl"
        
        mock_config = unittest.mock.Mock()
        mock_config.data = MockDataConfig()

        results = {
            "scraped_posts": [{"id": 1, "status": "ok"}, {"id": 2, "status": "ok"}],
            "skipped_posts": [{"id": 3, "reason": "error"}]
        }

        save_scrape_results(results, str(self.test_dir), mock_config)

        # Verify metadata file
        self.assertTrue(mock_config.data.metadata_path.exists())
        with open(mock_config.data.metadata_path, "r") as f:
            lines = f.readlines()
            self.assertEqual(len(lines), 2)
            self.assertIn('"id": 1', lines[0])

        # Verify skipped file
        self.assertTrue(mock_config.data.skipped_path.exists())
        with open(mock_config.data.skipped_path, "r") as f:
            self.assertIn('"reason": "error"', f.read())

        # Verify that the original results lists are cleared
        self.assertEqual(len(results["scraped_posts"]), 0)
        self.assertEqual(len(results["skipped_posts"]), 0)

    def test_get_all_post_images_data(self):
        """Test extracting image data from various simulated DOM structures."""
        mock_driver = MagicMock()

        # --- Mock DOM elements ---
        mock_img1 = MagicMock()
        mock_img1.get_attribute.side_effect = lambda x: {"src": "img1.jpg", "alt": "alt1"}.get(x)
        mock_img2 = MagicMock()
        mock_img2.get_attribute.side_effect = lambda x: {"src": "img2.jpg", "alt": "alt2"}.get(x)

        mock_li1 = MagicMock()
        mock_li1.find_elements.return_value = [mock_img1]
        mock_li2 = MagicMock()
        mock_li2.find_elements.return_value = [mock_img2]

        mock_ul = MagicMock()
        mock_ul.find_elements.return_value = [mock_li1, mock_li2]

        mock_container = MagicMock()
        mock_container.find_element.return_value = mock_ul

        # --- Test Case 1: Primary container class ---
        mock_driver.find_elements.side_effect = [
            [mock_container], # Case 1: .x1iyjqo2
            [],             # Case 2: .x1lliihq.x1n2onr6
            [],             # Case 3: fallback
        ]
        
        result = get_all_post_images_data(mock_driver)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['src'], 'img1.jpg')

    def test_extract_post_title_details(self):
        """Test extraction of post title details from a simulated DOM."""
        mock_driver = MagicMock()

        # --- Mock DOM elements ---
        mock_div = MagicMock()
        mock_div.text = "Post caption text"

        mock_img = MagicMock()
        mock_img.get_attribute.return_value = "img.jpg"
        mock_a = MagicMock()
        mock_a.get_attribute.return_value = "/profile/"
        mock_a.text = "username"
        mock_time = MagicMock()
        mock_time.get_attribute.return_value = "2024-01-01T12:00:00.000Z"
        mock_time.text = "1h"

        # Configure find_elements on the mock_div
        def div_find_elements(by, value):
            if value == ".//img": return [mock_img]
            if value == ".//a": return [mock_a]
            if value == ".//time": return [mock_time]
            return []
        mock_div.find_elements.side_effect = div_find_elements

        # Configure driver mocks
        mock_driver.find_elements.return_value = [mock_div]
        mock_driver.execute_script.return_value = {"class": "some-class"}

        # --- Run function ---
        result = extract_post_title_details(mock_driver)

        # --- Assertions ---
        self.assertEqual(len(result), 1)
        details = result[0]
        self.assertEqual(details['text'], "Post caption text")
        self.assertEqual(details['images'][0]['src'], "img.jpg")
        self.assertEqual(details['links'][0]['href'], "/profile/")
        self.assertEqual(details['times'][0]['datetime'], "2024-01-01T12:00:00.000Z")

    @patch('igscraper.utils.human_like_click')
    @patch('selenium.webdriver.support.ui.WebDriverWait')
    def test_scrape_carousel_images(self, mock_wait, mock_human_click):
        """Test the logic of scraping a carousel by simulating button clicks."""
        mock_driver = MagicMock()
        mock_human_click.return_value = True # Assume clicks are always successful

        # --- Mock the "Next" button ---
        # It should be found twice, then raise an exception to stop the loop
        mock_next_button = MagicMock()
        mock_wait.return_value.until.side_effect = [
            mock_next_button, # First call finds the button
            mock_next_button, # Second call finds it again
            TimeoutException("Button not found") # Third call fails, ending the loop
        ]

        # --- Mock the function that gathers images on each step ---
        mock_image_gather_func = MagicMock()
        mock_image_gather_func.side_effect = [
            [{"src": "img1.jpg"}], # First call sees image 1
            [{"src": "img2.jpg"}], # Second call sees image 2
            [{"src": "img3.jpg"}], # Third call sees image 3
        ]

        result = scrape_carousel_images(mock_driver, mock_image_gather_func)

        # --- Assertions ---
        # It should have gathered images from 3 states (initial + 2 clicks)
        self.assertEqual(mock_image_gather_func.call_count, 3)
        # It should have tried to click "Next" twice
        self.assertEqual(mock_human_click.call_count, 2)
        # The final result should contain all unique images
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]['src'], 'img1.jpg')
        self.assertEqual(result[2]['src'], 'img3.jpg')

    @patch('igscraper.utils.WebDriverWait')
    @patch('igscraper.utils.find_comment_container')
    @patch('igscraper.utils.human_scroll')
    def test_scrape_comments_with_gif(self, mock_human_scroll, mock_find_container, mock_wait):
        """Test the orchestration logic of scraping comments."""
        mock_driver = MagicMock()
        mock_config = MagicMock()
        mock_config.main.comment_scroll_steps = 50
        mock_config.main.comments_scroll_retries = 2

        # Mock dependencies
        mock_find_container.return_value = {"selector": ".comment-container"}
        expected_comments = [{"handle": "user1", "comment": "nice post"}]
        mock_driver.execute_script.return_value = expected_comments

        # Call the function
        result = scrape_comments_with_gif(mock_driver, mock_config)

        # Assertions
        mock_wait.assert_called_once()
        mock_find_container.assert_called_once_with(mock_driver)
        mock_human_scroll.assert_called_once()
        # Check that the selector from find_comment_container was passed to human_scroll
        self.assertEqual(mock_human_scroll.call_args[0][1], ".comment-container")
        # Check that retries from config were passed
        self.assertEqual(mock_human_scroll.call_args[1]['max_retries'], 2)

        mock_driver.execute_script.assert_called_once()
        self.assertEqual(result, expected_comments)

    @patch('igscraper.utils.WebDriverWait')
    def test_get_section_with_highest_likes(self, mock_wait):
        """Test the extraction of the like count section."""
        mock_driver = MagicMock()

        # Mock dependencies
        expected_likes_data = {"likesText": "1,234 likes", "likesNumber": 1234}
        mock_driver.execute_script.return_value = expected_likes_data

        # Call the function
        result = get_section_with_highest_likes(mock_driver)

        # Assertions
        mock_wait.assert_called_once()
        mock_driver.execute_script.assert_called_once()
        self.assertIn("function()", mock_driver.execute_script.call_args[0][0]) # Check if correct JS was passed
        self.assertEqual(result, expected_likes_data)

if __name__ == '__main__':
    unittest.main()
