import unittest

import pandas as pd

from src.metrics import COUNTING_METRICS, normalise_stats
from src.roles import PLAYER_ROLES, STYLE_METRICS
from src.scouting import calculate_role_score, prepare_players, similar_players
from src.dataset import aggregate_careers


def player(pid, position="MID", minutes=1800, level=1):
    row = {metric: float(level * 10) for metric in COUNTING_METRICS}
    row.update({"Player ID": pid, "Player Name": "Same Name", "Club": "Club",
                "Nationality": "England", "Position": position, "Minutes": minutes,
                "Successful Passes": level * 7.0, "Seasons Played": 1})
    return row


class ScoutingTests(unittest.TestCase):
    def test_career_aggregation_weights_minutes_and_percentages(self):
        roster = pd.DataFrame([{k: v for k, v in player("a").items() if k not in COUNTING_METRICS}])
        rows = []
        for minutes, goals, passes, completed in [(90, 1, 10, 5), (900, 2, 100, 90)]:
            row = {metric: 0.0 for metric in COUNTING_METRICS}
            row.update({"Player ID": "a", "Minutes": minutes, "Goals": goals,
                        "Passes": passes, "Successful Passes": completed})
            rows.append(row)
        result = prepare_players(aggregate_careers(roster, pd.DataFrame(rows))).iloc[0]
        self.assertAlmostEqual(result["Goals per 90"], 3 / 990 * 90)
        self.assertAlmostEqual(result["Pass Completion %"], 95 / 110 * 100)

    def test_unsupported_metrics_are_unknown_and_sparse_events_are_zero(self):
        values = normalise_stats({"timePlayed": 900}, {"timePlayed", "goals"})
        self.assertEqual(values["Goals"], 0)
        self.assertIsNone(values["Through Balls"])
        values = normalise_stats({"goals": None}, {"goals"})
        self.assertIsNone(values["Goals"])

    def test_missing_season_is_not_filled_in_career(self):
        roster = pd.DataFrame([{k: v for k, v in player("a").items() if k not in COUNTING_METRICS}])
        rows = pd.DataFrame([player("a"), player("a")])
        rows.loc[1, "Key Passes"] = float("nan")
        result = aggregate_careers(roster, rows).iloc[0]
        self.assertTrue(pd.isna(result["Key Passes"]))
        self.assertEqual(result["Minutes"], 3600)

    def test_zero_minutes_produces_no_rates_or_similarity(self):
        rows = prepare_players(pd.DataFrame([player("a", minutes=0), player("b"), player("c", level=2)]))
        self.assertTrue(pd.isna(rows.iloc[0]["Goals per 90"]))
        matches, _, _, note = similar_players(rows, "a", minimum_minutes=0)
        self.assertTrue(matches.empty)
        self.assertIn("minutes", note)

    def test_similarity_excludes_self_other_positions_and_small_samples(self):
        rows = prepare_players(pd.DataFrame([
            player("a"), player("b"), player("c", level=3),
            player("other", position="DEF"), player("small", minutes=90),
        ]))
        matches, features, _, _ = similar_players(rows, "a")
        self.assertEqual(matches["Player ID"].tolist(), ["b", "c"])
        self.assertEqual(matches.iloc[0]["Similarity"], 100)
        self.assertGreaterEqual(len(features), 4)
        self.assertTrue(matches["Similarity"].between(0, 100).all())

    def test_flat_profiles_cannot_produce_artificial_matches(self):
        rows = prepare_players(pd.DataFrame([player("a"), player("b"), player("c")]))
        self.assertTrue(similar_players(rows, "a")[0].empty)

    def test_missing_candidate_cannot_win_by_using_fewer_features(self):
        rows = prepare_players(pd.DataFrame([player("a"), player("b"), player("c", level=3), player("d", level=2)]))
        rows.loc[rows["Player ID"] == "b", STYLE_METRICS["MID"][0]] = float("nan")
        matches, _, _, _ = similar_players(rows, "a")
        self.assertNotIn("b", matches["Player ID"].tolist())

    def test_style_metrics_include_goal_contributions_and_defender_recoveries(self):
        for position in ("DEF", "MID", "FWD"):
            self.assertIn("Goals per 90", STYLE_METRICS[position])
            self.assertIn("Assists per 90", STYLE_METRICS[position])
        self.assertIn("Recoveries per 90", STYLE_METRICS["DEF"])
        self.assertIn("Touches In Box per 90", STYLE_METRICS["DEF"])
        for position in ("MID", "FWD"):
            metrics = STYLE_METRICS[position]
            self.assertEqual(metrics.index("Key Passes per 90"), metrics.index("Passes per 90") + 1)

    def test_roles_have_complete_valid_metrics_and_missing_rows_not_scored(self):
        rows = prepare_players(pd.DataFrame([player("a", "GKP"), player("b", "GKP", level=2)]))
        self.assertEqual(sum(len(roles) for roles in PLAYER_ROLES.values()), 10)
        for roles in PLAYER_ROLES.values():
            for metrics in roles.values():
                self.assertAlmostEqual(sum(metrics.values()), 1)
                self.assertTrue(set(metrics).issubset(rows.columns))
        rows.loc[0, "Goals per 90"] = float("nan")
        scores = calculate_role_score(rows, {"Goals per 90": .5, "Assists per 90": .5})
        self.assertTrue(pd.isna(scores.iloc[0]["Scouting Score"]))
        self.assertEqual(scores.iloc[1]["Scouting Score"], 100)


if __name__ == "__main__":
    unittest.main()
