"""Ten tactical archetypes using available Premier League metrics."""

PLAYER_ROLES = {
    "GKP": {
        "Shot Stopper": {
            "Saves per 90": .40, "Save Rate %": .30,
            "Clean Sheets per 90": .20, "Catches per 90": .10,
        },
        "Sweeper Keeper": {
            "Passes per 90": .25, "Pass Completion %": .20,
            "Successful Long Passes per 90": .20, "Recoveries per 90": .20,
            "Touches per 90": .15,
        },
    },
    "DEF": {
        "Ball-Playing Defender": {
            "Passes per 90": .20, "Pass Completion %": .20,
            "Forward Passes per 90": .20, "Successful Long Passes per 90": .15,
            "Recoveries per 90": .15, "Successful Dribbles per 90": .10,
        },
        "Defensive Stopper": {
            "Tackles per 90": .25, "Interceptions per 90": .20,
            "Clearances per 90": .20, "Blocks per 90": .15,
            "Ground Duels Won per 90": .10, "Aerial Duels Won per 90": .10,
        },
    },
    "MID": {
        "Box-to-Box Midfielder": {
            "Successful Dribbles per 90": .20, "Recoveries per 90": .25,
            "Tackles per 90": .20, "Touches In Box per 90": .15,
            "Key Passes per 90": .10, "Interceptions per 90": .10,
        },
        "Ball-Winning Midfielder": {
            "Tackles per 90": .30, "Interceptions per 90": .25,
            "Recoveries per 90": .25, "Ground Duels Won per 90": .15,
            "Aerial Duels Won per 90": .05,
        },
        "Creative Midfielder": {
            "Assists per 90": .20, "Through Balls per 90": .20,
            "Key Passes per 90": .30, "Successful Dribbles per 90": .20,
            "Successful Crosses per 90": .10,
        },
        "Deep-Lying Playmaker": {
            "Passes per 90": .25, "Pass Completion %": .20,
            "Forward Passes per 90": .20, "Through Balls per 90": .15,
            "Successful Long Passes per 90": .20,
        },
    },
    "FWD": {
        "Goalscorer": {
            "Goals per 90": .35, "Shots On Target per 90": .25,
            "Shots per 90": .15, "Touches In Box per 90": .15,
            "Ground Duels Won per 90": .10,
        },
        "Creative Forward": {
            "Assists per 90": .25, "Through Balls per 90": .15,
            "Key Passes per 90": .25, "Successful Dribbles per 90": .20,
            "Successful Crosses per 90": .15,
        },
    },
}

ROLE_NOTES = {
    "Shot Stopper": "Save Rate is calculated as saves / (saves + goals conceded). It is an app-derived rate. Clean sheets use per-90 values to reduce career-length bias.",
    "Sweeper Keeper": "Distribution and involvement proxy: the source does not expose reliable sweeping actions. This score cannot establish how often a goalkeeper leaves their area.",
    "Ball-Playing Defender": "Forward passing, long passing and successful dribbles describe ball use; dribbles do not measure progressive carries.",
    "Box-to-Box Midfielder": "Combines recoveries and defending with dribbling, box involvement and chance creation. It does not measure distance covered.",
    "Creative Midfielder": "Key passes and successful dribbles replace unavailable final-third passes and progressive carries.",
    "Creative Forward": "Key passes and successful dribbles replace unavailable final-third passes and progressive carries.",
    "Deep-Lying Playmaker": "Forward and successful long passes describe distribution; they do not establish the player's starting position.",
}

# Equal weight per feature; statistical style is separate from role quality.
STYLE_METRICS = {
    "GKP": ["Passes per 90", "Long Passes per 90", "Pass Completion %",
            "Touches per 90", "Recoveries per 90", "Saves per 90",
            "Catches per 90", "Punches per 90"],
    "DEF": ["Passes per 90", "Forward Passes per 90", "Long Passes per 90",
            "Successful Crosses per 90", "Successful Dribbles per 90",
            "Tackles per 90", "Interceptions per 90", "Clearances per 90",
            "Aerial Duels Won per 90", "Touches In Box per 90"],
    "MID": ["Passes per 90", "Forward Passes per 90", "Long Passes per 90",
            "Key Passes per 90", "Successful Crosses per 90", "Successful Dribbles per 90",
            "Shots per 90", "Touches In Box per 90", "Tackles per 90", "Recoveries per 90"],
    "FWD": ["Shots per 90", "Touches In Box per 90", "Key Passes per 90",
            "Successful Crosses per 90", "Successful Dribbles per 90",
            "Passes per 90", "Aerial Duels Won per 90", "Recoveries per 90"],
}
