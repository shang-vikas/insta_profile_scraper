import unittest
from pathlib import Path
import toml
import os

# Adjust path to import from src
import sys
src_path = Path(__file__).resolve().parent.parent / 'src'
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from igscraper.config import load_config, Config

class TestConfig(unittest.TestCase):
    """
    Unit tests for the configuration loading and processing logic.

    These tests verify that the `load_config` function correctly reads a TOML file,
    instantiates the Pydantic models, and expands path placeholders.
    """

    def setUp(self):
        """Set up a temporary directory and a mock config.toml file for each test."""
        self.test_dir = Path("tests/temp_test_files")
        self.test_dir.mkdir(exist_ok=True)
        self.config_path = self.test_dir / "test_config.toml"
        
        self.config_data = {
            "main": {
                "target_profile": "testuser",
                "num_posts": 10,
                "headless": True,
                "comment_scroll_steps": 20,
            },
            "data": {
                "output_dir": "outputs",
                "posts_path": "outputs/{target_profile}/posts_{target_profile}.txt",
                "metadata_path": "outputs/{target_profile}/metadata_{target_profile}.jsonl",
                "skipped_path": "outputs/{target_profile}/skipped_{target_profile}.txt",
                "tmp_path": "outputs/{target_profile}/scrape_results_tmp_{target_profile}.jsonl",
                "cookie_file": "tests/temp_test_files/fake_cookies.pkl"
            },
            "logging": {
                "level": "INFO"
            }
        }
        
        with open(self.config_path, "w") as f:
            toml.dump(self.config_data, f)
            
        # Create a dummy cookie file
        (self.test_dir / "fake_cookies.pkl").touch()

    def tearDown(self):
        """Clean up and remove the temporary directory and files after each test."""
        if self.config_path.exists():
            self.config_path.unlink()
        if (self.test_dir / "fake_cookies.pkl").exists():
            (self.test_dir / "fake_cookies.pkl").unlink()
        if self.test_dir.exists():
            self.test_dir.rmdir()

    def test_load_config_successfully(self):
        """
        Verify that `load_config` can successfully parse a valid TOML file
        and create a `Config` object with the correct values.
        """
        config = load_config(str(self.config_path))
        self.assertIsInstance(config, Config)
        self.assertEqual(config.main.target_profile, "testuser")
        self.assertEqual(config.main.num_posts, 10)
        self.assertEqual(config.logging.level, "INFO")

    def test_path_expansion(self):
        """
        Verify that path strings in the config containing placeholders like
        `{target_profile}` are correctly formatted and resolved to absolute paths.
        """
        config = load_config(str(self.config_path))

        # The `load_config` function resolves paths to be absolute.
        # It also expands the `{target_profile}` placeholder.
        expected_posts_path = Path.cwd() / "outputs" / "testuser" / "posts_testuser.txt"
        self.assertEqual(Path(config.data.posts_path), expected_posts_path)

        expected_metadata_path = Path.cwd() / "outputs" / "testuser" / "metadata_testuser.jsonl"
        self.assertEqual(Path(config.data.metadata_path), expected_metadata_path)

if __name__ == '__main__':
    unittest.main()