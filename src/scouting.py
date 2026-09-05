"""Career rates, transparent archetype scores, and positional style similarity."""

import pandas as pd

from src.metrics import COUNTING_METRICS
from src.roles import STYLE_METRICS


def calculate_per_90(players, stats):
    players = players.copy()
    minutes = players["Minutes"].where(players["Minutes"] > 0)
    per90 = {f"{stat} per 90": players[stat] / minutes * 90 for stat in stats}
    return pd.concat([players, pd.DataFrame(per90, index=players.index)], axis=1)


def prepare_players(players):
    players = calculate_per_90(players, COUNTING_METRICS)
    for label, numerator, denominator in (
        ("Pass Completion %", players["Successful Passes"], players["Passes"]),
        ("Long Pass Completion %", players["Successful Long Passes"], players["Long Passes"]),
        ("Save Rate %", players["Saves"], players["Saves"] + players["Goals Conceded"]),
    ):
        players[label] = numerator / denominator.where(denominator > 0) * 100
    players.loc[players["Position"] != "GKP", "Save Rate %"] = float("nan")
    return players


def available_role_metrics(players, role_metrics):
    available = {metric: weight for metric, weight in role_metrics.items()
                 if metric in players and players[metric].notna().any()}
    missing = [metric for metric in role_metrics if metric not in available]
    total = sum(available.values())
    return ({metric: weight / total for metric, weight in available.items()} if total else {}), missing


def calculate_role_score(players, role_metrics):
    """Players missing an included metric receive no score, never a false zero."""
    players = players.copy()
    if not role_metrics:
        players["Scouting Score"] = float("nan")
        return players
    complete = players[list(role_metrics)].notna().all(axis=1)
    score = pd.Series(0.0, index=players.index)
    for metric, weight in role_metrics.items():
        rank = players.loc[complete, metric].rank(pct=True) * 100
        players[f"{metric} Percentile"] = rank
        score += rank.reindex(players.index) * weight
    players["Scouting Score"] = score.where(complete)
    return players


def similar_players(players, player_id, minimum_minutes=900, limit=5):
    """100 minus mean percentile gap on one shared, nonconstant feature set.

    Returns matches, feature names, the positional percentile table, and a
    coverage message. The chosen player must also meet the minutes threshold.
    """
    indexed = players.set_index("Player ID", drop=False)
    target = indexed.loc[player_id]
    empty = players.iloc[:0].copy()
    if pd.isna(target["Minutes"]) or target["Minutes"] <= 0 or target["Minutes"] < minimum_minutes:
        return empty, [], pd.DataFrame(), "This player does not yet meet the minimum PL minutes for a reliable comparison."
    configured = STYLE_METRICS.get(target["Position"], [])
    cohort = indexed[(indexed["Position"] == target["Position"]) &
                     (indexed["Minutes"] >= minimum_minutes) & (indexed["Minutes"] > 0)].copy()
    features = [m for m in configured if m in cohort and pd.notna(target[m]) and cohort[m].notna().any()]
    cohort = cohort.dropna(subset=features)
    features = [m for m in features if cohort[m].nunique() > 1]
    if len(features) < 4 or len(cohort) < 3:
        return empty, [], pd.DataFrame(), "Not enough players or varied, complete statistics to compare styles."
    percentiles = cohort[features].rank(pct=True) * 100
    gaps = percentiles.subtract(percentiles.loc[player_id]).abs()
    cohort["Similarity"] = (100 - gaps.mean(axis=1)).clip(0, 100)
    matches = cohort.drop(index=player_id).sort_values(
        ["Similarity", "Minutes"], ascending=[False, False], kind="stable"
    ).head(limit)
    note = ""
    omitted = [m for m in configured if m not in features]
    if omitted:
        note = "Unavailable or constant comparison metrics omitted: " + ", ".join(omitted) + "."
    return matches.reset_index(drop=True), features, percentiles, note
