#!/usr/bin/env python3
"""
Lululemon Discount Page SKU Scraper

This scraper fetches all unique SKUs from Lululemon's "We Made Too Much"
discount page by paginating through all results.
"""

import re
import json
import time
import argparse
from typing import Set
from curl_cffi import requests


class LululemonScraper:
    """Scraper for Lululemon's discount page to count unique SKUs."""

    BASE_URL = "https://shop.lululemon.com"
    SALE_PAGE_PATH = "/c/we-made-too-much/n18mhd"

    def __init__(self, delay: float = 2.0):
        """
        Initialize the scraper.

        Args:
            delay: Delay between page loads in seconds.
        """
        self.delay = delay
        self.unique_skus: Set[str] = set()
        self.session = requests.Session(impersonate="chrome120")

    def fetch_page(self, page_num: int = 1) -> str:
        """
        Fetch a single page of the sale listing.

        Args:
            page_num: Page number to fetch (1-indexed).

        Returns:
            HTML content of the page.
        """
        url = f"{self.BASE_URL}{self.SALE_PAGE_PATH}"
        if page_num > 1:
            url = f"{url}?page={page_num}"

        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        return response.text

    def extract_skus_from_html(self, html: str) -> Set[str]:
        """
        Extract product SKUs from HTML content.

        SKUs are found in product URLs in the format:
        /p/category/product-name/prod[ID]?color=...

        Args:
            html: HTML content to parse.

        Returns:
            Set of unique SKU identifiers found in the HTML.
        """
        # Pattern to match product IDs like "prod11210211"
        sku_pattern = r'/p/[^/]+/[^/]+/(prod\d+)'
        matches = re.findall(sku_pattern, html)
        return set(matches)

    def extract_total_count(self, html: str) -> int | None:
        """
        Extract the total product count from the page.

        Args:
            html: HTML content to parse.

        Returns:
            Total product count if found, None otherwise.
        """
        # Look for patterns like "View Items (1532)" or similar
        count_pattern = r'(?:View Items?|items?|products?)\s*\((\d+(?:,\d+)?)\)'
        match = re.search(count_pattern, html, re.IGNORECASE)
        if match:
            count_str = match.group(1).replace(',', '')
            return int(count_str)

        # Also try JSON data embedded in page
        json_count_pattern = r'"totalNumRecs"\s*:\s*(\d+)'
        match = re.search(json_count_pattern, html)
        if match:
            return int(match.group(1))

        return None

    def has_next_page(self, html: str, current_page: int) -> bool:
        """
        Check if there's a next page of results.

        Args:
            html: HTML content to parse.
            current_page: Current page number.

        Returns:
            True if there's a next page, False otherwise.
        """
        next_page_pattern = rf'page={current_page + 1}'
        return bool(re.search(next_page_pattern, html))

    def scrape_all_skus(self, max_pages: int = 100) -> Set[str]:
        """
        Scrape all unique SKUs from all pages of the discount section.

        Args:
            max_pages: Maximum number of pages to scrape (safety limit).

        Returns:
            Set of all unique SKU identifiers.
        """
        page_num = 1
        total_count = None
        consecutive_no_new = 0

        print(f"Starting to scrape Lululemon 'We Made Too Much' page...")
        print(f"URL: {self.BASE_URL}{self.SALE_PAGE_PATH}")
        print("-" * 60)

        while page_num <= max_pages:
            try:
                print(f"Fetching page {page_num}...", end=" ", flush=True)
                html = self.fetch_page(page_num)

                # Get total count from first page
                if page_num == 1:
                    total_count = self.extract_total_count(html)
                    if total_count:
                        print(f"\nTotal items reported by site: {total_count}")
                        print("-" * 60)
                        print(f"Fetching page {page_num}...", end=" ", flush=True)

                # Extract SKUs from this page
                page_skus = self.extract_skus_from_html(html)
                new_skus = page_skus - self.unique_skus
                self.unique_skus.update(page_skus)

                print(f"Found {len(page_skus)} SKUs ({len(new_skus)} new). Total unique: {len(self.unique_skus)}")

                # Check if we should continue
                if not new_skus:
                    consecutive_no_new += 1
                    if consecutive_no_new >= 2:
                        print(f"\nNo new SKUs found for {consecutive_no_new} pages. Stopping.")
                        break
                else:
                    consecutive_no_new = 0

                if not self.has_next_page(html, page_num):
                    print(f"\nNo more pages found after page {page_num}.")
                    break

                page_num += 1
                time.sleep(self.delay)

            except Exception as e:
                print(f"\nError fetching page {page_num}: {e}")
                break

        return self.unique_skus

    def get_summary(self) -> dict:
        """
        Get a summary of the scraping results.

        Returns:
            Dictionary with scraping statistics.
        """
        return {
            "unique_sku_count": len(self.unique_skus),
            "skus": sorted(self.unique_skus),
        }


def main():
    """Main entry point for the scraper."""
    parser = argparse.ArgumentParser(description="Scrape Lululemon discount page for unique SKUs")
    parser.add_argument("--max-pages", type=int, default=100, help="Maximum pages to scrape")
    parser.add_argument("--delay", type=float, default=2.0, help="Delay between requests in seconds")
    args = parser.parse_args()

    print("=" * 60)
    print("Lululemon Discount Page SKU Scraper")
    print("=" * 60)
    print()

    scraper = LululemonScraper(delay=args.delay)

    try:
        skus = scraper.scrape_all_skus(max_pages=args.max_pages)

        print()
        print("=" * 60)
        print("RESULTS")
        print("=" * 60)
        print(f"\nTotal unique SKUs on discount: {len(skus)}")
        print()

        # Save results to file
        summary = scraper.get_summary()
        with open("lululemon_skus.json", "w") as f:
            json.dump(summary, f, indent=2)
        print(f"Results saved to lululemon_skus.json")

        return len(skus)

    except KeyboardInterrupt:
        print("\n\nScraping interrupted by user.")
        print(f"SKUs collected so far: {len(scraper.unique_skus)}")
        return len(scraper.unique_skus)


if __name__ == "__main__":
    main()
