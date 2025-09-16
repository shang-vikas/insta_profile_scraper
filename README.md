# Instagram Profile Scraper

A maintainable Python project for collecting public Instagram profile data.

## Legal Notice

This project is for educational purposes only. Please:
- Respect Instagram's Terms of Service
- Only scrape publicly available data
- Respect rate limits and add delays between requests
- Do not store or distribute copyrighted content without permission

## Quick Start
This guide will walk you through setting up and running the Instagram Profile Scraper.

### 1. Prerequisites
- Python 3.11 or newer.
- Google Chrome browser installed.

### 2. Installation

First, clone the repository and set up a virtual environment.
```bash
# Clone the repository
# git clone <repository-url>
# cd ig_profile_scraper

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate

# Install the required dependencies
pip install -r requirements.txt
```

### 3. Authentication (Cookie Generation)
The scraper logs in using browser cookies to appear like a real user. You need to generate a cookie file first.

1.  Run the `login_Save_cookie.py` script:
    ```bash
    python src/igscraper/login_Save_cookie.py
    ```
2.  A Chrome browser window will open to the Instagram login page. **Log in to your Instagram account manually.**
3.  After you have successfully logged in, go back to your terminal and **press Enter**.
4.  A cookie file named `cookies_xxxxxxxxxx.pkl` will be saved in the project's root directory. **Copy the full name of this file** for the next step.

### 4. Configuration

Before running the main scraper, you must configure it. A `sample_config.toml` is provided as a template.

1.  It's recommended to copy `sample_config.toml` to a new file, for example `config.toml`.
2.  Open your `config.toml` file and edit the following fields:
    -   `target_profile`: The Instagram username you want to scrape (e.g., `"ladbible"`).
    -   `num_posts`: The maximum number of posts you want to collect URLs for.
    -   `cookie_file`: The full path to the `.pkl` cookie file you generated in the previous step (e.g., `"cookies_1678886400.pkl"`).

### 5. Run the Scraper

Now you are ready to start scraping. Run the command below, pointing to your configuration file.
```bash
python -m src.igscraper.cli --config config.toml
```
The scraper will start, open the target profile, collect post URLs, and then scrape each post one by one, saving the data as it goes.

### 6. Understanding the Output

The scraper will create an `outputs/` directory (or as configured in your `.toml` file) containing the results inside a folder named after the `target_profile`:

-   **`posts_{target_profile}.txt`**: A text file containing the list of all post URLs collected from the profile page.
-   **`metadata_{target_profile}.jsonl`**: The main data file. Each line is a JSON object containing the scraped data for a single post (e.g., title, images, comments, likes).
-   **`skipped_{target_profile}.txt`**: A log of posts that were skipped due to errors, saved in JSONL format.
