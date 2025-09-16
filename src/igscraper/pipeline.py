import pdb
import random
import traceback
from .config import load_config
from .backends import SeleniumBackend
# from .utils import random_delay, scrape_posts_in_batches
from .logger import get_logger
from pathlib import Path

logger = get_logger(__name__)
import sys
import traceback
# import json,sys
from pathlib import Path

def run_pipeline(config_path: str, dry_run: bool = False):
    config = load_config(config_path)
    # print(config)
    # sys.exit(0)
    # logger.info(f"{list(config.items())}")
    # Initialize backend
    backend = SeleniumBackend(config)

    results = {"scraped_posts": [], "skipped_posts": []}

    output_dir = Path(config.data.output_dir)
    output_dir.mkdir(exist_ok=True)
    # metadata_file = config.data.metadata_path
    # skipped_file = config.data.skipped_path

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

        # # --- persist scraped posts ---
        # if results["scraped_posts"]:
        #     with open(metadata_file, "w", encoding="utf-8") as f:
        #         for post in results["scraped_posts"]:
        #             f.write(json.dumps(post, ensure_ascii=False) + "\n")

        # # --- persist skipped posts ---
        # if results["skipped_posts"]:
        #     with open(skipped_file, "w", encoding="utf-8") as f:
        #         for post in results["skipped_posts"]:
        #             f.write(json.dumps(post, ensure_ascii=False) + "\n")
        
        logger.info(f"Pipeline completed for profile {config.main.target_profile}.")

    except Exception as e:
        logger.critical(f"Pipeline failed for profile {config.main.target_profile}: {e}")
        logger.debug(traceback.format_exc())
    finally:
        backend.stop()

    return results


