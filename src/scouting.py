import pandas as pd


def calculate_per_90(players, stats):

    players = players.copy()

    for stat in stats:
        players[f"{stat} per 90"] = (
            players[stat] / players["Minutes"] * 90
        )

    return players


def calculate_role_score(players, role_metrics):

    players = players.copy()

    score_columns = []

    for metric, weight in role_metrics.items():

        percentile_column = f"{metric} Percentile"

        players[percentile_column] = (
            players[metric].rank(pct=True) * 100
        )

        weighted_column = f"{metric} Weighted"

        players[weighted_column] = (
            players[percentile_column] * weight
        )

        score_columns.append(weighted_column)

    players["Scouting Score"] = (
        players[score_columns].sum(axis=1)
    )

    return players