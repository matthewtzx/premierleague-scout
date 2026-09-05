"""Validated snapshots: refresh in one transaction and retain raw source totals."""

import json
import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.metrics import COUNTING_METRICS, POSITIONS, normalise_stats
from src.pl_api import DataSourceError, SOURCE_URL

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE = PROJECT_ROOT / "data" / "premier_league.sqlite3"
SCHEMA_VERSION = 1


def build_snapshot(api, progress=lambda message: None):
    try:
        return _build_snapshot(api, progress)
    except (KeyError, TypeError, AttributeError) as exc:
        raise DataSourceError("The Premier League response format has changed or contains incomplete records.") from exc


def validate_stats(stats, label):
    if not isinstance(stats, dict) or any(
        v is not None and (not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0)
        for v in stats.values()
    ):
        raise DataSourceError(f"Invalid numeric statistics in {label}.")


def _build_snapshot(api, progress):
    active, seasons = api.seasons()
    progress(f"Loading {active['label']} Premier League squads")
    roster = api.roster(active["id"])
    ids = {p["Player ID"] for p in roster}
    for player in roster:
        player["Position"] = POSITIONS.get(player["Position"], "UNK")
        player["Coverage Note"] = ""
    records, coverage, unidentified = [], {}, {}
    for season in seasons:
        progress(f"Loading {season['label']} statistics")
        rows = api.season_stats({**season, "active": season["id"] == active["id"]})
        if not rows and season["id"] != active["id"]:
            raise DataSourceError(f"No statistics returned for completed season {season['label']}.")
        supported = {key for row in rows for key in row.get("stats", {})}
        coverage[season["label"]] = sorted(supported)
        seen = set()
        for row in rows:
            player_id = str(row.get("playerMetadata", {}).get("id", ""))
            if not player_id:
                # Some historical rows contain {'^': None} instead of player
                # metadata. Reconcile current players against their careers below.
                unidentified[season["label"]] = unidentified.get(season["label"], 0) + 1
                continue
            if player_id in seen:
                raise DataSourceError(f"Duplicate player ID in {season['label']}.")
            seen.add(player_id)
            stats = row.get("stats", {})
            validate_stats(stats, season["label"])
            if player_id not in ids or not stats:
                continue
            if stats.get("appearances", 0) > 0 and not stats.get("timePlayed", 0):
                raise DataSourceError(f"Appearances without playing time for player {player_id}.")
            if not stats.get("timePlayed", 0):
                continue
            values = normalise_stats(stats, supported)
            if values["Minutes"] is None or values["Appearances"] is None:
                raise DataSourceError(f"Missing playing-time coverage in {season['label']}.")
            if values["Successful Passes"] is not None and values["Successful Passes"] < 0:
                raise DataSourceError(f"Inconsistent passing totals for player {player_id}.")
            records.append({
                "Player ID": player_id, "Season ID": season["id"],
                "Season": season["label"], "Start Year": season["year"],
                "values": values, "raw": stats,
            })
    present = {(r["Player ID"], r["Start Year"]) for r in records}
    for number, player in enumerate(roster, 1):
        progress(f"Checking career coverage {number}/{len(roster)}: {player['Player Name']}")
        years = api.career_seasons(player["Player ID"])
        for season in seasons:
            if season["year"] not in years or (player["Player ID"], season["year"]) in present:
                continue
            response = api.player_season_stats(player["Player ID"], season["id"])
            raw = response.get("stats", {})
            validate_stats(raw, season["label"])
            if not raw.get("timePlayed", 0) or not raw.get("appearances", 0):
                # The official career summary can be ahead of its detailed feed.
                # Preserve those basic totals and mark detailed metrics unknown.
                raw = years[season["year"]]
                validate_stats(raw, season["label"])
                if not raw.get("timePlayed", 0) or not raw.get("appearances", 0):
                    raise DataSourceError(f"Incomplete career summary for {player['Player Name']} in {season['label']}.")
                values = normalise_stats(raw, set(raw))
                player["Coverage Note"] += f"Detailed statistics unavailable for {season['label']}. "
                source = "career summary"
            else:
                values = normalise_stats(raw, set(coverage[season["label"]]) | set(raw))
                source = "season statistics"
            if values["Successful Passes"] is not None and values["Successful Passes"] < 0:
                raise DataSourceError(f"Inconsistent passing totals for {player['Player Name']}.")
            records.append({
                "Player ID": player["Player ID"], "Season ID": season["id"],
                "Season": season["label"], "Start Year": season["year"], "raw": raw,
                "values": values, "source": source,
            })
    if not records:
        raise DataSourceError("No career statistics were found for the current squads.")
    metadata = {
        "schema_version": SCHEMA_VERSION, "source": SOURCE_URL,
        "refreshed_at": datetime.now(timezone.utc).isoformat(),
        "active_season": active["label"], "first_season": "2006/2007",
        "player_count": len(roster), "season_count": len(seasons),
        "season_coverage": coverage,
        "unidentified_historical_rows": unidentified,
    }
    return roster, records, metadata


def save_snapshot(path, roster, records, metadata):
    """Readers see either the previous complete snapshot or the new one."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path, timeout=30) as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        connection.execute("CREATE TABLE IF NOT EXISTS players (player_id TEXT PRIMARY KEY, record TEXT NOT NULL)")
        connection.execute("""CREATE TABLE IF NOT EXISTS player_seasons (
            player_id TEXT, season_id TEXT, record TEXT NOT NULL,
            PRIMARY KEY (player_id, season_id))""")
        for table in ("metadata", "players", "player_seasons"):
            connection.execute(f"DELETE FROM {table}")
        connection.executemany("INSERT INTO metadata VALUES (?, ?)",
                               [(k, json.dumps(v, allow_nan=False)) for k, v in metadata.items()])
        connection.executemany("INSERT INTO players VALUES (?, ?)",
                               [(p["Player ID"], json.dumps(p, allow_nan=False)) for p in roster])
        connection.executemany("INSERT INTO player_seasons VALUES (?, ?, ?)", [
            (r["Player ID"], r["Season ID"], json.dumps(r, allow_nan=False)) for r in records
        ])


def load_snapshot(path=DEFAULT_DATABASE):
    path = Path(path)
    if not path.exists():
        raise DataSourceError("No Premier League snapshot exists yet. Refresh the data to get started.")
    try:
        with sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True) as connection:
            connection.execute("BEGIN")
            metadata = {k: json.loads(v) for k, v in connection.execute("SELECT key, value FROM metadata")}
            if metadata.get("schema_version") != SCHEMA_VERSION:
                raise DataSourceError("The saved snapshot needs a refresh for this app version.")
            roster = [json.loads(r[0]) for r in connection.execute("SELECT record FROM players")]
            records = [json.loads(r[0]) for r in connection.execute("SELECT record FROM player_seasons")]
    except (sqlite3.Error, ValueError) as exc:
        raise DataSourceError("The saved snapshot cannot be read. Refresh the Premier League data.") from exc
    if not roster or not records:
        raise DataSourceError("The saved snapshot is empty. Refresh the Premier League data.")
    seasons = pd.DataFrame([{
        **{k: r[k] for k in ("Player ID", "Season ID", "Season", "Start Year")}, **r["values"]
    } for r in records])
    return aggregate_careers(pd.DataFrame(roster), seasons), seasons, metadata


def aggregate_careers(roster, seasons):
    counts = seasons.groupby("Player ID")[COUNTING_METRICS].agg(
        lambda values: values.sum() if values.notna().all() else float("nan")
    )
    careers = roster.merge(counts, on="Player ID", how="left", validate="one_to_one")
    counts_by_player = seasons.groupby("Player ID").size()
    careers["Seasons Played"] = careers["Player ID"].map(counts_by_player).fillna(0).astype(int)
    no_history = careers["Seasons Played"] == 0
    careers.loc[no_history, COUNTING_METRICS] = 0
    return careers
