import unittest
from unittest.mock import patch

import pandas as pd
import streamlit as st
from streamlit.testing.v1 import AppTest

from src.metrics import COUNTING_METRICS
from src.roles import PLAYER_ROLES


def snapshot():
    roster, history = [], []
    for position in PLAYER_ROLES:
        for n in range(4):
            pid = f"{position}{n}"
            counts = {m: float(10 * (n + 1)) for m in COUNTING_METRICS}
            counts.update({"Minutes": 1800.0, "Appearances": 20.0})
            roster.append({**counts, "Player ID": pid, "Player Name": f"Player {position} {n}",
                           "Club": "Club A" if n % 2 == 0 else "Club B", "Club ID": str(n % 2),
                           "Nationality": "England", "Position": position, "Seasons Played": 1})
            history.append({**counts, "Player ID": pid, "Season ID": "2025", "Season": "2025/2026", "Start Year": 2025})
    return pd.DataFrame(roster), pd.DataFrame(history), {
        "refreshed_at": "2026-09-05T00:00:00+00:00", "active_season": "2026/2027",
        "source": "https://www.premierleague.com/en/stats",
    }


def labelled(elements, label):
    return next(element for element in elements if element.label == label)


class InterfaceTests(unittest.TestCase):
    def setUp(self):
        st.cache_data.clear()
        self.mock = patch("src.dataset.load_snapshot", return_value=snapshot())
        self.loader = self.mock.start()
        self.app = AppTest.from_file("app.py", default_timeout=20).run()

    def tearDown(self):
        self.mock.stop()
        st.cache_data.clear()

    def assert_clean(self):
        self.assertEqual(len(self.app.exception), 0, str(self.app.exception))

    def test_search_compare_and_open_matching_profile(self):
        self.assert_clean()
        self.app.selectbox[0].select("MID0").run()
        self.assert_clean()
        self.assertIn("Player MID 0", [h.value for h in self.app.header])
        self.app.selectbox[0].select("MID2").run()
        self.assertIn("Player MID 2", [h.value for h in self.app.header])
        labelled(self.app.selectbox, "Compare with").select("MID1").run()
        labelled(self.app.button, "Open Player MID 1's profile").click().run()
        self.assert_clean()
        self.assertIn("Player MID 1", [h.value for h in self.app.header])

    def test_club_filter_and_archetype_navigation(self):
        self.app.radio[0].set_value("Filter by club").run()
        labelled(self.app.selectbox, "Club").select("Club B").run()
        selector = labelled(self.app.selectbox, "Select a player — type a name to search")
        self.assertTrue(all("Club B" in option for option in selector.options))
        selector.select("DEF1").run()
        labelled(self.app.button, "Player Archetypes").click().run()
        self.assert_clean()
        labelled(self.app.selectbox, "Position").select("MID").run()
        labelled(self.app.selectbox, "Archetype").select("Creative Midfielder").run()
        labelled(self.app.selectbox, "Explore an archetype player").select("MID2").run()
        labelled(self.app.button, "View career and similar players").click().run()
        self.assert_clean()
        self.assertIn("Player MID 2", [h.value for h in self.app.header])
        self.assertEqual(self.app.radio[0].value, "Search for a player")

    def test_all_ten_roles_render(self):
        labelled(self.app.button, "Player Archetypes").click().run()
        for position, roles in PLAYER_ROLES.items():
            labelled(self.app.selectbox, "Position").select(position).run()
            for role in roles:
                labelled(self.app.selectbox, "Archetype").select(role).run()
                self.assert_clean()
                self.assertTrue(len(self.app.dataframe) > 0)

    def test_empty_snapshot_shows_load_action(self):
        from src.pl_api import DataSourceError
        st.cache_data.clear()
        self.loader.side_effect = DataSourceError("No snapshot exists yet.")
        self.app = AppTest.from_file("app.py", default_timeout=20).run()
        self.assert_clean()
        self.assertTrue(any(b.label == "Load Premier League data" for b in self.app.button))


if __name__ == "__main__":
    unittest.main()
