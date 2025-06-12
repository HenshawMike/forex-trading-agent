import requests
import time
import json
from datetime import datetime, timedelta
from contextlib import contextmanager
from typing import Annotated
import os
import re

ticker_to_company = {
    "AAPL": "Apple",
    "MSFT": "Microsoft",
    "GOOGL": "Google",
    "AMZN": "Amazon",
    "TSLA": "Tesla",
    "NVDA": "Nvidia",
    "TSM": "Taiwan Semiconductor Manufacturing Company OR TSMC",
    "JPM": "JPMorgan Chase OR JP Morgan",
    "JNJ": "Johnson & Johnson OR JNJ",
    "V": "Visa",
    "WMT": "Walmart",
    "META": "Meta OR Facebook",
    "AMD": "AMD",
    "INTC": "Intel",
    "QCOM": "Qualcomm",
    "BABA": "Alibaba",
    "ADBE": "Adobe",
    "NFLX": "Netflix",
    "CRM": "Salesforce",
    "PYPL": "PayPal",
    "PLTR": "Palantir",
    "MU": "Micron",
    "SQ": "Block OR Square",
    "ZM": "Zoom",
    "CSCO": "Cisco",
    "SHOP": "Shopify",
    "ORCL": "Oracle",
    "X": "Twitter OR X",
    "SPOT": "Spotify",
    "AVGO": "Broadcom",
    "ASML": "ASML ",
    "TWLO": "Twilio",
    "SNAP": "Snap Inc.",
    "TEAM": "Atlassian",
    "SQSP": "Squarespace",
    "UBER": "Uber",
    "ROKU": "Roku",
    "PINS": "Pinterest",
}


def fetch_top_from_category(
    category: Annotated[
        str, "Category to fetch top post from. Collection of subreddits."
    ],
    date: Annotated[str, "Date to fetch top posts from."],
    max_limit: Annotated[int, "Maximum number of posts to fetch."],
    query: Annotated[str, "Optional query to search for in the subreddit."] = None,
    data_path: Annotated[
        str,
        "Path to the data folder. Default is 'reddit_data'.",
    ] = "reddit_data",
):
    base_path = data_path

    all_content = []

    if max_limit < len(os.listdir(os.path.join(base_path, category))):
        raise ValueError(
            "REDDIT FETCHING ERROR: max limit is less than the number of files in the category. Will not be able to fetch any posts"
        )

    limit_per_subreddit = max_limit // len(
        os.listdir(os.path.join(base_path, category))
    )

    for data_file in os.listdir(os.path.join(base_path, category)):
        # check if data_file is a .jsonl file
        if not data_file.endswith(".jsonl"):
            continue

        all_content_curr_subreddit = []

        with open(os.path.join(base_path, category, data_file), "rb") as f:
            for i, line_bytes in enumerate(f):
                # skip empty lines
                if not line_bytes.strip():
                    continue

                # Attempt to extract created_utc and check date before full JSON parsing
                # This is an optimization to reduce calls to json.loads()
                # We search in the raw bytes for speed, then decode only the timestamp part.
                try:
                    # Regex to find "created_utc": followed by a number (integer or float)
                    # This assumes "created_utc" is reasonably early in the JSON string.
                    match = re.search(b'"created_utc":\\s*([0-9.]+)', line_bytes)
                    if match:
                        timestamp_bytes = match.group(1)
                        timestamp = float(timestamp_bytes.decode('utf-8'))
                        post_date_str = datetime.utcfromtimestamp(timestamp).strftime("%Y-%m-%d")

                        if post_date_str != date:
                            continue  # Skip this line as it's not for the target date
                    else:
                        # If created_utc is not found via regex (e.g., unusual formatting or not present),
                        # we'll have to parse the whole line to be sure.
                        # This path will be slower but ensures correctness.
                        pass # Fall through to full parsing

                except Exception:
                    # If any error occurs during this pre-check (e.g., decoding, float conversion),
                    # fall through to full parsing to ensure data isn't wrongly skipped.
                    pass

                # Full parsing if pre-check didn't skip or failed
                try:
                    line_str = line_bytes.decode('utf-8') # Decode once here
                    parsed_line = json.loads(line_str)
                except json.JSONDecodeError:
                    print(f"Warning: Could not decode JSON for line in {data_file}: {line_bytes[:200]}") # Log problematic line
                    continue # Skip malformed JSON lines

                # Re-check date if not done or if pre-check failed and fell through
                # (this check is cheap once parsed_line is available)
                current_post_date_str = datetime.utcfromtimestamp(
                    parsed_line.get("created_utc", 0) # Use .get for safety
                ).strftime("%Y-%m-%d")

                if current_post_date_str != date:
                    continue

                # Store the validated post_date to avoid re-calculating later
                post_date = current_post_date_str

                # if is company_news, check that the title or the content has the company's name (query) mentioned
                if "company" in category and query:
                    search_terms = []
                    if "OR" in ticker_to_company[query]:
                        search_terms = ticker_to_company[query].split(" OR ")
                    else:
                        search_terms = [ticker_to_company[query]]

                    search_terms.append(query)

                    found = False
                    for term in search_terms:
                        if re.search(
                            term, parsed_line["title"], re.IGNORECASE
                        ) or re.search(term, parsed_line["selftext"], re.IGNORECASE):
                            found = True
                            break

                    if not found:
                        continue

                post = {
                    "title": parsed_line["title"],
                    "content": parsed_line["selftext"],
                    "url": parsed_line["url"],
                    "upvotes": parsed_line["ups"],
                    "posted_date": post_date,
                }

                all_content_curr_subreddit.append(post)

        # sort all_content_curr_subreddit by upvote_ratio in descending order
        all_content_curr_subreddit.sort(key=lambda x: x["upvotes"], reverse=True)

        all_content.extend(all_content_curr_subreddit[:limit_per_subreddit])

    return all_content
