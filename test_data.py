import pandas as pd

from src.roles import MIDFIELDER_ROLES
from src.scouting import calculate_per_90
from src.scouting import calculate_role_score


# Load data
players = pd.read_csv("data/players.csv")


# Minimum minutes
players = players[
    players["Minutes"] >= 900
].copy()


# Statistics that need per-90 calculations
stats = [
    "Goals",
    "Assists",
    "Shots",
    "Shots On Target",
    "Touches",
    "Passes",
    "Successful Passes",
    "Crosses",
    "Successful Crosses",
    "fThird Passes",
    "Successful fThird Passes",
    "Through Balls",
    "Carries",
    "Progressive Carries",
    "Possession Won",
    "Dispossessed",
    "Clearances",
    "Interceptions",
    "Blocks",
    "Tackles",
    "Ground Duels",
    "gDuels Won",
    "Aerial Duels",
    "aDuels Won",
]


# Calculate per-90 statistics
players = calculate_per_90(
    players,
    stats
)


# Keep midfielders
midfielders = players[
    players["Position"] == "MID"
].copy()


# Choose role
role_name = "Creative Midfielder"

role_metrics = MIDFIELDER_ROLES[
    role_name
]


# Calculate scouting scores
results = calculate_role_score(
    midfielders,
    role_metrics
)


# Rank highest to lowest
results = results.sort_values(
    "Scouting Score",
    ascending=False
)


print(f"\nTOP 10 — {role_name.upper()}\n")

print(
    results[
        [
            "Player Name",
            "Club",
            "Minutes",
            "Scouting Score",
        ]
    ].head(10)
)