#!/usr/bin/env python3
"""
Google Trends Scraper with Quarterly Aggregation

This scraper fetches Google Trends data for specified keywords
and aggregates the interest values by quarter.
"""

import json
import time
import argparse
from datetime import datetime
from typing import Dict, List, Optional
from pytrends.request import TrendReq


class GoogleTrendsScraper:
    """Scraper for Google Trends data with quarterly aggregation."""

    def __init__(self, delay: float = 1.0, hl: str = "en-US", tz: int = 360):
        """
        Initialize the Google Trends scraper.

        Args:
            delay: Delay between API requests in seconds.
            hl: Host language for Google Trends.
            tz: Timezone offset in minutes from UTC.
        """
        self.delay = delay
        self.pytrends = TrendReq(hl=hl, tz=tz)
        self.raw_data: Dict[str, Dict] = {}
        self.quarterly_data: Dict[str, Dict] = {}

    def fetch_interest_over_time(
        self,
        keywords: List[str],
        timeframe: str = "today 5-y",
        geo: str = "",
        cat: int = 0,
    ) -> Optional[Dict]:
        """
        Fetch interest over time data for given keywords.

        Args:
            keywords: List of keywords to fetch (max 5 at a time).
            timeframe: Time range for data (e.g., "today 5-y", "2020-01-01 2024-12-31").
            geo: Geographic location (e.g., "US", "" for worldwide).
            cat: Category ID (0 for all categories).

        Returns:
            Dictionary with raw trend data or None if failed.
        """
        try:
            # Google Trends allows max 5 keywords at once
            if len(keywords) > 5:
                print(f"Warning: Only first 5 keywords will be fetched. Got {len(keywords)}.")
                keywords = keywords[:5]

            print(f"Building payload for keywords: {keywords}")
            self.pytrends.build_payload(
                kw_list=keywords,
                timeframe=timeframe,
                geo=geo,
                cat=cat,
            )

            time.sleep(self.delay)

            print("Fetching interest over time...")
            df = self.pytrends.interest_over_time()

            if df.empty:
                print("No data returned from Google Trends.")
                return None

            # Convert DataFrame to dictionary
            result = {}
            for keyword in keywords:
                if keyword in df.columns:
                    result[keyword] = {
                        str(date): int(value)
                        for date, value in df[keyword].items()
                    }

            return result

        except Exception as e:
            print(f"Error fetching trend data: {e}")
            return None

    def aggregate_by_quarter(self, data: Dict[str, Dict]) -> Dict[str, Dict]:
        """
        Aggregate trend data by quarter.

        Args:
            data: Dictionary with keyword -> {date: value} mapping.

        Returns:
            Dictionary with keyword -> {quarter: aggregated_value} mapping.
        """
        quarterly = {}

        for keyword, date_values in data.items():
            quarterly[keyword] = {}
            quarter_sums = {}
            quarter_counts = {}

            for date_str, value in date_values.items():
                # Parse date string (format: "YYYY-MM-DD HH:MM:SS" or "YYYY-MM-DD")
                try:
                    date = datetime.fromisoformat(date_str.split()[0])
                except ValueError:
                    continue

                # Calculate quarter
                quarter = (date.month - 1) // 3 + 1
                quarter_key = f"{date.year}-Q{quarter}"

                if quarter_key not in quarter_sums:
                    quarter_sums[quarter_key] = 0
                    quarter_counts[quarter_key] = 0

                quarter_sums[quarter_key] += value
                quarter_counts[quarter_key] += 1

            # Calculate average for each quarter
            for quarter_key in sorted(quarter_sums.keys()):
                avg_value = round(quarter_sums[quarter_key] / quarter_counts[quarter_key], 2)
                quarterly[keyword][quarter_key] = {
                    "average": avg_value,
                    "sum": quarter_sums[quarter_key],
                    "data_points": quarter_counts[quarter_key],
                }

        return quarterly

    def scrape_keywords(
        self,
        keywords: List[str],
        timeframe: str = "today 5-y",
        geo: str = "",
        cat: int = 0,
        batch_size: int = 5,
    ) -> Dict[str, Dict]:
        """
        Scrape trend data for multiple keywords with batching.

        Args:
            keywords: List of keywords to scrape.
            timeframe: Time range for data.
            geo: Geographic location.
            cat: Category ID.
            batch_size: Number of keywords per API call (max 5).

        Returns:
            Dictionary with all quarterly aggregated data.
        """
        batch_size = min(batch_size, 5)  # Google Trends limit
        all_data = {}

        print("=" * 60)
        print("Google Trends Scraper - Quarterly Aggregation")
        print("=" * 60)
        print(f"\nKeywords: {', '.join(keywords)}")
        print(f"Timeframe: {timeframe}")
        print(f"Geographic filter: {geo or 'Worldwide'}")
        print("-" * 60)

        # Process keywords in batches
        for i in range(0, len(keywords), batch_size):
            batch = keywords[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (len(keywords) + batch_size - 1) // batch_size

            print(f"\nProcessing batch {batch_num}/{total_batches}: {batch}")

            raw_data = self.fetch_interest_over_time(
                keywords=batch,
                timeframe=timeframe,
                geo=geo,
                cat=cat,
            )

            if raw_data:
                self.raw_data.update(raw_data)
                all_data.update(raw_data)
                print(f"Successfully fetched data for: {list(raw_data.keys())}")
            else:
                print(f"Failed to fetch data for batch: {batch}")

            # Delay between batches
            if i + batch_size < len(keywords):
                print(f"Waiting {self.delay}s before next batch...")
                time.sleep(self.delay)

        # Aggregate by quarter
        print("\n" + "-" * 60)
        print("Aggregating data by quarter...")
        self.quarterly_data = self.aggregate_by_quarter(all_data)

        return self.quarterly_data

    def get_summary(self) -> Dict:
        """
        Get a summary of the scraping results.

        Returns:
            Dictionary with scraping statistics and data.
        """
        summary = {
            "scraped_at": datetime.now().isoformat(),
            "keywords_count": len(self.quarterly_data),
            "keywords": list(self.quarterly_data.keys()),
            "quarterly_data": self.quarterly_data,
        }

        # Add quarter range info
        all_quarters = set()
        for keyword_data in self.quarterly_data.values():
            all_quarters.update(keyword_data.keys())

        if all_quarters:
            sorted_quarters = sorted(all_quarters)
            summary["quarter_range"] = {
                "start": sorted_quarters[0],
                "end": sorted_quarters[-1],
                "total_quarters": len(sorted_quarters),
            }

        return summary

    def print_results(self):
        """Print formatted results to console."""
        print("\n" + "=" * 60)
        print("QUARTERLY AGGREGATION RESULTS")
        print("=" * 60)

        for keyword, quarters in self.quarterly_data.items():
            print(f"\n{keyword}:")
            print("-" * 40)
            for quarter, values in quarters.items():
                print(f"  {quarter}: avg={values['average']:.1f}, "
                      f"sum={values['sum']}, points={values['data_points']}")


def main():
    """Main entry point for the scraper."""
    parser = argparse.ArgumentParser(
        description="Scrape Google Trends data and aggregate by quarter",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s -k "python" "javascript" "rust"
  %(prog)s -k "bitcoin" -t "2020-01-01 2024-12-31" -g US
  %(prog)s -k "machine learning" "deep learning" -o ml_trends.json
        """
    )
    parser.add_argument(
        "-k", "--keywords",
        nargs="+",
        required=True,
        help="Keywords to search (space-separated, use quotes for multi-word terms)"
    )
    parser.add_argument(
        "-t", "--timeframe",
        default="today 5-y",
        help="Timeframe for data (default: 'today 5-y'). "
             "Options: 'today 5-y', 'today 12-m', 'today 3-m', "
             "or custom range like '2020-01-01 2024-12-31'"
    )
    parser.add_argument(
        "-g", "--geo",
        default="",
        help="Geographic location code (e.g., 'US', 'GB'). "
             "Leave empty for worldwide."
    )
    parser.add_argument(
        "-c", "--category",
        type=int,
        default=0,
        help="Google Trends category ID (default: 0 for all)"
    )
    parser.add_argument(
        "-d", "--delay",
        type=float,
        default=1.0,
        help="Delay between API requests in seconds (default: 1.0)"
    )
    parser.add_argument(
        "-o", "--output",
        default="google_trends_quarterly.json",
        help="Output JSON file path (default: google_trends_quarterly.json)"
    )

    args = parser.parse_args()

    scraper = GoogleTrendsScraper(delay=args.delay)

    try:
        quarterly_data = scraper.scrape_keywords(
            keywords=args.keywords,
            timeframe=args.timeframe,
            geo=args.geo,
            cat=args.category,
        )

        if quarterly_data:
            scraper.print_results()

            # Save results to file
            summary = scraper.get_summary()
            with open(args.output, "w") as f:
                json.dump(summary, f, indent=2)

            print(f"\nResults saved to {args.output}")
            return 0
        else:
            print("\nNo data collected.")
            return 1

    except KeyboardInterrupt:
        print("\n\nScraping interrupted by user.")
        if scraper.quarterly_data:
            summary = scraper.get_summary()
            with open(args.output, "w") as f:
                json.dump(summary, f, indent=2)
            print(f"Partial results saved to {args.output}")
        return 1


if __name__ == "__main__":
    exit(main())
