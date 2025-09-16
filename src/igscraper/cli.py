import argparse
import sys
from pathlib import Path

# Add the project's 'src' directory to the Python path.
# This ensures that modules can be imported using their full path from 'src'
# (e.g., 'igscraper.utils') regardless of how the script is run.
src_path = Path(__file__).resolve().parent.parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from igscraper.pipeline import run_pipeline

def main():
    parser = argparse.ArgumentParser(description='Instagram Profile Scraper')
    parser.add_argument('--config', required=True, help='Path to config file')
    parser.add_argument('--dry-run', action='store_true', help='Test without downloading')
    args = parser.parse_args()

    run_pipeline(args.config, args.dry_run)

if __name__ == '__main__':
    main()
