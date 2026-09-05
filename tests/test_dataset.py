import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.dataset import build_snapshot, load_snapshot, save_snapshot, SCHEMA_VERSION
from src.pl_api import DataSourceError, EntityNotFound, PremierLeagueAPI


class FakeAPI:
    def seasons(self):
        return {"id": "2026", "label": "2026/2027"}, [
            {"id": "7", "year": 2006, "label": "2006/2007"},
            {"id": "2026", "year": 2026, "label": "2026/2027"},
        ]

    def roster(self, season):
        return [{"Player ID": "a", "Player Name": "A", "Club ID": "1", "Club": "Current",
                 "Position": "Midfielder", "Nationality": "England"},
                {"Player ID": "new", "Player Name": "New", "Club ID": "1", "Club": "Current",
                 "Position": "Forward", "Nationality": "England"}]

    def season_stats(self, season):
        return [{"playerMetadata": {"id": "a", "currentTeam": {"name": "Former"}},
                 "stats": {"timePlayed": 90, "appearances": 1, "goals": 1}},
                {"playerMetadata": {"id": "retired"}, "stats": {"timePlayed": 90, "goals": 1}}]

    def career_seasons(self, pid):
        return {year: {"timePlayed": 90, "appearances": 1, "goals": 1} for year in [2006, 2026]} if pid == "a" else {}


class DatasetTests(unittest.TestCase):
    def test_round_trip_current_roster_prior_clubs_new_arrival(self):
        roster, records, metadata = build_snapshot(FakeAPI())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "snapshot.sqlite3"
            save_snapshot(path, roster, records, metadata)
            players, seasons, saved = load_snapshot(path)
        self.assertEqual(set(players["Player ID"]), {"a", "new"})
        self.assertEqual(players.iloc[0]["Club"], "Current")
        self.assertEqual(players.iloc[0]["Goals"], 2)
        self.assertEqual(players.iloc[1]["Minutes"], 0)
        self.assertEqual(seasons["Start Year"].min(), 2006)
        self.assertEqual(saved["schema_version"], SCHEMA_VERSION)

    def test_failed_transaction_retains_previous_snapshot(self):
        roster, records, metadata = build_snapshot(FakeAPI())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "snapshot.sqlite3"
            save_snapshot(path, roster, records, metadata)
            with self.assertRaises(sqlite3.IntegrityError):
                save_snapshot(path, roster + roster, records, metadata)
            self.assertEqual(len(load_snapshot(path)[0]), 2)

    def test_missing_database_is_actionable_and_not_created(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "missing.sqlite3"
            with self.assertRaises(DataSourceError):
                load_snapshot(path)
            self.assertFalse(path.exists())

    def test_incomplete_season_aborts_refresh(self):
        api = FakeAPI()
        api.season_stats = lambda season: []
        with self.assertRaises(DataSourceError):
            build_snapshot(api)

    def test_identityless_rows_reconciled_from_player_history(self):
        api = FakeAPI()
        api.season_stats = lambda season: [{"playerMetadata": {"^": None}, "stats": {"timePlayed": 90, "appearances": 1}}]
        api.player_season_stats = lambda pid, season: {"stats": {"timePlayed": 90, "appearances": 1, "goals": 2}}
        _, records, meta = build_snapshot(api)
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["values"]["Goals"], 2)
        self.assertEqual(meta["unidentified_historical_rows"]["2006/2007"], 1)

    def test_pagination_uses_next_cursor_and_detects_repeat(self):
        with tempfile.TemporaryDirectory() as directory:
            api = PremierLeagueAPI(directory)
            with patch.object(api, "get", side_effect=[
                {"data": [{"id": 1}], "pagination": {"_next": "abc"}},
                {"data": [{"id": 2}], "pagination": {"_next": None}},
            ]) as get:
                self.assertEqual(len(api.pages("/test")), 2)
                self.assertEqual(get.call_args.args[1]["_next"], "abc")
            with patch.object(api, "get", return_value={"data": [{}], "pagination": {"_next": "abc"}}):
                with self.assertRaises(DataSourceError):
                    api.pages("/test")

    def test_summary_fallback_retains_basic_totals_without_inventing_detail(self):
        api = FakeAPI()
        api.season_stats = lambda season: [{"playerMetadata": {"id": "a"}, "stats": {"yellowCards": 0}}]
        api.player_season_stats = lambda pid, season: {"stats": {"yellowCards": 0}}
        roster, records, _ = build_snapshot(api)
        self.assertEqual(records[0]["values"]["Minutes"], 90)
        self.assertEqual(records[0]["values"]["Goals"], 1)
        self.assertIsNone(records[0]["values"]["Passes"])
        self.assertIn("2006/2007", roster[0]["Coverage Note"])

    def test_changed_schema_is_a_source_error(self):
        api = FakeAPI()
        api.roster = lambda season: [{"unexpected": "field"}]
        with self.assertRaises(DataSourceError):
            build_snapshot(api)

    def test_missing_detail_allows_summary_but_network_errors_do_not(self):
        with tempfile.TemporaryDirectory() as directory:
            api = PremierLeagueAPI(directory)
            with patch.object(api, "get", side_effect=EntityNotFound("Missing season")):
                self.assertEqual(api.player_season_stats("a", "2026"), {"stats": {}})
            with patch.object(api, "get", side_effect=DataSourceError("Network failed")):
                with self.assertRaises(DataSourceError):
                    api.player_season_stats("a", "2026")

    def test_career_summary_filters_competition_and_combines_transfer_clubs(self):
        stat = {"opCompetitionId": "8", "tournamentCalendarName": "2025/2026",
                "tournamentCalendarId": "season", "minutesPlayed": 90, "appearances": 1, "goals": 1}
        membership = {"opContestantId": "club-a", "stat": [stat, {**stat, "opCompetitionId": "2"}]}
        with tempfile.TemporaryDirectory() as directory:
            api = PremierLeagueAPI(directory)
            with patch.object(api, "get", return_value={"person": [{"membership": [membership, membership,
                    {"opContestantId": "club-b", "stat": [{**stat, "minutesPlayed": 180}]}]}]}):
                result = api.career_seasons("player")
                self.assertEqual(result[2025]["timePlayed"], 270)
                self.assertEqual(result[2025]["goals"], 2)

    def test_catalogue_uses_historical_ids_and_excludes_pre_2006(self):
        with tempfile.TemporaryDirectory() as directory:
            api = PremierLeagueAPI(directory)
            with patch.object(api, "_download", return_value="window.ACTIVE_PL_SEASON_ID = '8';"), patch.object(api, "get", return_value={"seasons": [
                {"id": "6", "season": "Season 2005/2006"},
                {"id": "7", "season": "Season 2006/2007"},
                {"id": "8", "season": "Season 2007/2008"},
            ]}):
                active, seasons = api.seasons()
                self.assertEqual([s["id"] for s in seasons], ["7", "8"])
                self.assertEqual(active["year"], 2007)


if __name__ == "__main__":
    unittest.main()
