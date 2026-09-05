"""Usage: python -m scripts.refresh_data [--force]"""

import argparse
import sqlite3
import sys

from src.dataset import DEFAULT_DATABASE, build_snapshot, save_snapshot
from src.pl_api import DataSourceError, PremierLeagueAPI


def main():
    parser = argparse.ArgumentParser(description="Refresh career PL stats for current PL squads (2006/07 onward).")
    parser.add_argument("--force", action="store_true", help="Refetch cached API responses too.")
    args = parser.parse_args()
    api = PremierLeagueAPI(DEFAULT_DATABASE.parent / "cache", force=args.force)
    try:
        roster, records, metadata = build_snapshot(api, progress=lambda message: print(message, flush=True))
        save_snapshot(DEFAULT_DATABASE, roster, records, metadata)
    except (DataSourceError, OSError, ValueError, sqlite3.Error) as exc:
        print(f"Refresh failed; previous snapshot retained. {exc}", file=sys.stderr)
        return 1
    print(f"Saved {len(roster)} current players and {len(records)} player-seasons to {DEFAULT_DATABASE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
