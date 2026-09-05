"""Explicit mappings from the Premier League site's SDP statistics feed."""

POSITIONS = {
    "Goalkeeper": "GKP", "Defender": "DEF", "Midfielder": "MID", "Forward": "FWD",
}
POSITION_NAMES = {value: key for key, value in POSITIONS.items()}

# A tuple contains additive components. Sparse, supported event counts follow
# the PL website's zero convention; an unsupported season metric stays unknown.
METRICS = {
    "Appearances": ("appearances",),
    "Minutes": ("timePlayed",),
    "Goals": ("goals",),
    "Assists": ("goalAssists",),
    "Shots": ("totalShots",),
    "Shots On Target": ("shotsOnTargetIncGoals",),
    "Touches": ("touches",),
    "Touches In Box": ("totalTouchesInOppositionBox",),
    "Passes": ("totalPasses",),
    "Unsuccessful Passes": ("totalUnsuccessfulPassesExclCrossesAndCorners",),
    "Successful Long Passes": ("successfulLongPasses",),
    "Long Passes": ("successfulLongPasses", "unsuccessfulLongPasses"),
    "Forward Passes": ("forwardPasses",),
    "Through Balls": ("throughBalls",),
    "Key Passes": ("keyPassesAttemptAssists",),
    "Crosses": ("successfulCrossesOpenPlay", "unsuccessfulCrossesOpenPlay"),
    "Successful Crosses": ("successfulCrossesOpenPlay",),
    "Dribbles": ("successfulDribbles", "unsuccessfulDribbles"),
    "Successful Dribbles": ("successfulDribbles",),
    "Recoveries": ("recoveries",),
    "Tackles": ("totalTackles",),
    "Tackles Won": ("tacklesWon",),
    "Interceptions": ("interceptions",),
    "Clearances": ("totalClearances",),
    "Blocks": ("blocks",),
    "Ground Duels Won": ("groundDuelsWon",),
    "Aerial Duels Won": ("aerialDuelsWon",),
    "Saves": ("savesMade",),
    "Goals Conceded": ("goalsConceded",),
    "Clean Sheets": ("cleanSheets",),
    "Punches": ("punches",),
    "Catches": ("catches",),
    "Penalties Saved": ("penaltiesSaved",),
    "Yellow Cards": ("yellowCards",),
    "Red Cards": ("totalRedCards",),
}
COUNTING_METRICS = [*METRICS, "Successful Passes"]
RATE_METRICS = ["Pass Completion %", "Long Pass Completion %", "Save Rate %"]


def normalise_stats(stats, supported):
    """Do not confuse a metric absent league-wide with a player's zero count."""
    values = {}
    for label, keys in METRICS.items():
        if not all(key in supported for key in keys):
            values[label] = None
        else:
            parts = [stats.get(key, 0) for key in keys]
            values[label] = None if any(v is None for v in parts) else sum(parts)
    # The PL site derives completed passes from total minus unsuccessful passes.
    passes, failed = values["Passes"], values["Unsuccessful Passes"]
    values["Successful Passes"] = (
        passes - failed if passes is not None and failed is not None else None
    )
    return values
