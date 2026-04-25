#!/usr/bin/env python3
"""
Reddit Subreddit Weekly Visitor YoY Scraper

Fetches daily traffic data for a given subreddit via the Reddit API,
aggregates it into ISO calendar weeks, and calculates year-over-year (YoY)
change in unique weekly visitors.

Requirements:
  - You must be a moderator of the target subreddit (Reddit restricts traffic
    data to moderators only).
  - A Reddit "script" app: https://www.reddit.com/prefs/apps

Usage:
  python subreddit_visitor_scraper.py <subreddit> [options]

  Credentials can be passed as flags or via environment variables:
    REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USERNAME, REDDIT_PASSWORD
"""

import csv
import json
import os
import argparse
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests


REDDIT_TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
REDDIT_API_BASE = "https://oauth.reddit.com"


class SubredditVisitorScraper:
    """Fetches and analyses weekly unique-visitor trends for a subreddit."""

    def __init__(self, client_id: str, client_secret: str, username: str, password: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.session.headers["User-Agent"] = f"SubredditVisitorScraper/1.0 by u/{username}"

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    def authenticate(self) -> None:
        """Obtain an OAuth2 bearer token via the Reddit script-app flow."""
        resp = self.session.post(
            REDDIT_TOKEN_URL,
            auth=(self.client_id, self.client_secret),
            data={
                "grant_type": "password",
                "username": self.username,
                "password": self.password,
            },
            timeout=15,
        )
        resp.raise_for_status()
        payload = resp.json()
        token = payload.get("access_token")
        if not token:
            raise RuntimeError(f"Authentication failed: {payload}")
        self.session.headers["Authorization"] = f"bearer {token}"

    # ------------------------------------------------------------------
    # Data fetching
    # ------------------------------------------------------------------

    def fetch_traffic(self, subreddit: str) -> dict:
        """Return the raw traffic JSON from the Reddit API."""
        url = f"{REDDIT_API_BASE}/r/{subreddit}/about/traffic"
        resp = self.session.get(url, timeout=15)
        if resp.status_code == 403:
            raise PermissionError(
                f"Access denied for r/{subreddit}. "
                "Traffic data is only available to subreddit moderators."
            )
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Aggregation & analysis
    # ------------------------------------------------------------------

    @staticmethod
    def aggregate_to_weeks(daily: list) -> list:
        """
        Group daily [ts, uniques, pageviews] entries into ISO calendar weeks,
        summing uniques and pageviews. Returns rows sorted by week.
        """
        weekly: dict = defaultdict(lambda: {"uniques": 0, "pageviews": 0, "week_start": None})

        for entry in daily:
            ts, uniques, pageviews = entry[0], entry[1], entry[2]
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            iso_year, iso_week, _ = dt.isocalendar()
            key = (iso_year, iso_week)

            weekly[key]["uniques"] += uniques
            weekly[key]["pageviews"] += pageviews

            # Record Monday of this ISO week as the human-readable label
            if weekly[key]["week_start"] is None:
                monday = dt - timedelta(days=dt.weekday())
                weekly[key]["week_start"] = monday.date().isoformat()

        return [
            {
                "date": v["week_start"],
                "iso_year": k[0],
                "iso_week": k[1],
                "uniques": v["uniques"],
                "pageviews": v["pageviews"],
            }
            for k, v in sorted(weekly.items())
        ]

    @staticmethod
    def compute_yoy(weeks: list) -> list:
        """
        For each week, look up the same ISO week from the prior year and attach:
          yoy_uniques    – unique visitors in that prior-year week
          yoy_change_pct – percentage change (positive = growth)
        """
        index = {(w["iso_year"], w["iso_week"]): w for w in weeks}
        result = []
        for w in weeks:
            prior = index.get((w["iso_year"] - 1, w["iso_week"]))
            yoy_uniques = prior["uniques"] if prior else None
            if yoy_uniques:
                change_pct = round((w["uniques"] - yoy_uniques) / yoy_uniques * 100, 2)
            else:
                change_pct = None
            result.append(
                {
                    **w,
                    "yoy_uniques": yoy_uniques,
                    "yoy_change_pct": change_pct,
                }
            )
        return result

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def run(self, subreddit: str) -> list:
        """Authenticate, fetch, aggregate, and return YoY weekly rows."""
        print("Authenticating with Reddit...")
        self.authenticate()

        print(f"Fetching traffic data for r/{subreddit}...")
        traffic = self.fetch_traffic(subreddit)

        daily = traffic.get("day", [])
        if not daily:
            raise RuntimeError(
                "No daily traffic data returned. "
                "Confirm you are a moderator of this subreddit."
            )
        print(f"  Received {len(daily)} days of data.")

        weeks = self.aggregate_to_weeks(daily)
        print(f"  Aggregated into {len(weeks)} ISO weeks.")

        return self.compute_yoy(weeks)


# ------------------------------------------------------------------
# Output helpers
# ------------------------------------------------------------------

def print_table(rows: list, subreddit: str) -> None:
    """Print a human-readable table of weekly YoY visitor data."""
    col = {"date": 12, "week": 9, "uniques": 12, "yoy_uniques": 13, "change": 12}
    header = (
        f"{'Date':<{col['date']}} "
        f"{'Week':<{col['week']}} "
        f"{'Uniques':>{col['uniques']}} "
        f"{'YoY Uniques':>{col['yoy_uniques']}} "
        f"{'YoY Change':>{col['change']}}"
    )
    separator = "-" * len(header)

    print()
    print(f"r/{subreddit} — Weekly Unique Visitors (YoY)")
    print(separator)
    print(header)
    print(separator)

    for r in rows:
        week_label = f"{r['iso_year']}W{r['iso_week']:02d}"
        yoy_str = f"{r['yoy_uniques']:,}" if r["yoy_uniques"] is not None else "n/a"
        if r["yoy_change_pct"] is not None:
            arrow = "▲" if r["yoy_change_pct"] >= 0 else "▼"
            change_str = f"{arrow} {abs(r['yoy_change_pct']):.1f}%"
        else:
            change_str = "n/a"

        print(
            f"{r['date']:<{col['date']}} "
            f"{week_label:<{col['week']}} "
            f"{r['uniques']:>{col['uniques']},} "
            f"{yoy_str:>{col['yoy_uniques']}} "
            f"{change_str:>{col['change']}}"
        )

    print(separator)

    # Summary: most recent week with YoY data
    with_yoy = [r for r in rows if r["yoy_change_pct"] is not None]
    if with_yoy:
        latest = with_yoy[-1]
        direction = "up" if latest["yoy_change_pct"] >= 0 else "down"
        print(
            f"\nLatest comparable week ({latest['date']}): "
            f"{latest['uniques']:,} unique visitors, "
            f"{direction} {abs(latest['yoy_change_pct']):.1f}% YoY."
        )


def save_json(rows: list, subreddit: str) -> str:
    fname = f"{subreddit}_weekly_visitors.json"
    with open(fname, "w") as f:
        json.dump(rows, f, indent=2)
    return fname


def save_csv(rows: list, subreddit: str) -> str:
    fname = f"{subreddit}_weekly_visitors.csv"
    fields = ["date", "iso_year", "iso_week", "uniques", "pageviews", "yoy_uniques", "yoy_change_pct"]
    with open(fname, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return fname


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Fetch weekly visitor YoY change for a Reddit subreddit.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Credentials can also be supplied via environment variables:
  REDDIT_CLIENT_ID      Reddit script-app client ID
  REDDIT_CLIENT_SECRET  Reddit script-app client secret
  REDDIT_USERNAME       Your Reddit username
  REDDIT_PASSWORD       Your Reddit password

NOTE: You must be a moderator of the target subreddit.
Create a Reddit script app at: https://www.reddit.com/prefs/apps
        """,
    )
    parser.add_argument("subreddit", help="Subreddit name (without the r/ prefix)")
    parser.add_argument(
        "--client-id",
        default=os.getenv("REDDIT_CLIENT_ID"),
        help="Reddit app client ID",
    )
    parser.add_argument(
        "--client-secret",
        default=os.getenv("REDDIT_CLIENT_SECRET"),
        help="Reddit app client secret",
    )
    parser.add_argument(
        "--username",
        default=os.getenv("REDDIT_USERNAME"),
        help="Reddit username",
    )
    parser.add_argument(
        "--password",
        default=os.getenv("REDDIT_PASSWORD"),
        help="Reddit password",
    )
    parser.add_argument(
        "--output",
        choices=["json", "csv", "none"],
        default="none",
        help="Save results to a file (default: none, only print to stdout)",
    )
    parser.add_argument(
        "--weeks",
        type=int,
        default=None,
        help="Only show the most recent N weeks (default: all available)",
    )
    args = parser.parse_args()

    missing = [
        flag
        for flag, val in [
            ("--client-id / REDDIT_CLIENT_ID", args.client_id),
            ("--client-secret / REDDIT_CLIENT_SECRET", args.client_secret),
            ("--username / REDDIT_USERNAME", args.username),
            ("--password / REDDIT_PASSWORD", args.password),
        ]
        if not val
    ]
    if missing:
        parser.error("Missing required credentials:\n  " + "\n  ".join(missing))

    print("=" * 55)
    print(f"  Subreddit Weekly Visitor YoY Scraper")
    print(f"  Target: r/{args.subreddit}")
    print("=" * 55)

    scraper = SubredditVisitorScraper(
        client_id=args.client_id,
        client_secret=args.client_secret,
        username=args.username,
        password=args.password,
    )

    try:
        rows = scraper.run(args.subreddit)
    except PermissionError as e:
        print(f"\nError: {e}")
        raise SystemExit(1)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        raise SystemExit(1)

    if args.weeks:
        rows = rows[-args.weeks:]

    print_table(rows, args.subreddit)

    if args.output == "json":
        fname = save_json(rows, args.subreddit)
        print(f"\nResults saved to {fname}")
    elif args.output == "csv":
        fname = save_csv(rows, args.subreddit)
        print(f"\nResults saved to {fname}")


if __name__ == "__main__":
    main()
