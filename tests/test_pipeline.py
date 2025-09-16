import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

# Adjust path to import from src
import sys
src_path = Path(__file__).resolve().parent.parent / 'src'
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from igscraper.pipeline import run_pipeline

class TestPipeline(unittest.TestCase):

    @patch('igscraper.pipeline.load_config')
    @patch('igscraper.pipeline.SeleniumBackend')
    def test_run_pipeline_happy_path(self, mock_backend_class, mock_load_config):
        """Test the main pipeline execution flow with mocks."""
        # --- Setup Mocks ---
        # Mock config
        mock_config = MagicMock()
        mock_config.main.target_profile = "mockuser"
        mock_config.main.num_posts = 5
        mock_config.main.randomize_batch = False
        mock_config.main.batch_size = 2
        mock_config.main.save_every = 5
        mock_config.data.output_dir = "mock_outputs"
        mock_load_config.return_value = mock_config

        # Mock backend instance
        mock_backend_instance = MagicMock()
        mock_backend_class.return_value = mock_backend_instance
        
        # Mock backend methods
        mock_backend_instance.get_post_elements.return_value = ["http://post1", "http://post2"]
        mock_backend_instance.scrape_posts_in_batches.return_value = {
            "scraped_posts": [{}, {}],
            "skipped_posts": []
        }

        # --- Run the pipeline ---
        config_path = "dummy/config.toml"
        run_pipeline(config_path, dry_run=False)

        # --- Assertions ---
        # Config was loaded
        mock_load_config.assert_called_once_with(config_path)

        # Backend was initialized and started
        mock_backend_class.assert_called_once_with(mock_config)
        mock_backend_instance.start.assert_called_once()

        # Profile was opened
        mock_backend_instance.open_profile.assert_called_once_with("mockuser")

        # Post elements were retrieved
        mock_backend_instance.get_post_elements.assert_called_once_with(5)

        # Posts were scraped
        mock_backend_instance.scrape_posts_in_batches.assert_called_once_with(
            ["http://post1", "http://post2"],
            batch_size=2,
            save_every=5
        )

        # Backend was stopped
        mock_backend_instance.stop.assert_called_once()

    @patch('igscraper.pipeline.load_config')
    @patch('igscraper.pipeline.SeleniumBackend')
    def test_run_pipeline_no_posts_found(self, mock_backend_class, mock_load_config):
        """Test the pipeline exits gracefully if no posts are found."""
        # --- Setup Mocks ---
        mock_config = MagicMock()
        mock_config.main.target_profile = "nopostsuser"
        mock_load_config.return_value = mock_config
        
        mock_backend_instance = MagicMock()
        mock_backend_class.return_value = mock_backend_instance
        mock_backend_instance.get_post_elements.return_value = [] # No posts

        # --- Run and Assert ---
        run_pipeline("dummy/config.toml", dry_run=False)

        # Check that scraping was NOT called
        mock_backend_instance.scrape_posts_in_batches.assert_not_called()
        
        # Check that the backend was still stopped
        mock_backend_instance.stop.assert_called_once()

if __name__ == '__main__':
    unittest.main()