from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from src.roles import PLAYER_ROLES
from src.scouting import calculate_per_90, calculate_role_score

st.set_page_config(
    page_title="Premier League Scout",
    page_icon="⚽",
    layout="wide",
)

st.title("⚽ Premier League Scout")

st.write("Find Premier League players who match specific tactical roles.")

# -------------------------
# LOAD DATA
# -------------------------

players = pd.read_csv(Path(__file__).parent / "data" / "players.csv")

for column in players.columns:
    if column.endswith("%"):
        players[column] = pd.to_numeric(players[column].astype(str).str.rstrip("%"))

# -------------------------
# SIDEBAR
# -------------------------

st.sidebar.header("Scouting Filters")

minimum_minutes = st.sidebar.slider(
    "Minimum minutes",
    min_value=0,
    max_value=3000,
    value=900,
    step=100,
)

clubs = sorted(players["Club"].unique())

selected_clubs = st.sidebar.multiselect(
    "Clubs",
    clubs,
)

nationalities = sorted(players["Nationality"].unique())

selected_nationalities = st.sidebar.multiselect(
    "Nationalities",
    nationalities,
)

position_names = {
    "GKP": "Goalkeeper",
    "DEF": "Defender",
    "MID": "Midfielder",
    "FWD": "Forward",
}

selected_position = st.sidebar.selectbox(
    "Position",
    list(position_names.keys()),
    format_func=lambda x: position_names[x],
)

available_roles = PLAYER_ROLES[selected_position]

role_name = st.sidebar.selectbox(
    "Player Role",
    list(available_roles.keys()),
)

number_of_results = st.sidebar.slider(
    "Number of recommendations",
    min_value=5,
    max_value=30,
    value=10,
    step=5,
)

# -------------------------
# FILTER DATA
# -------------------------

players = players[
    (players["Minutes"] >= minimum_minutes) & (players["Minutes"] > 0)
].copy()

position_players = players[players["Position"] == selected_position].copy()

# -------------------------
# PER 90
# -------------------------

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
    "Saves",
    "Punches",
    "High Claims",
    "Keeper Sweeper",
    "Touches Box",
]

position_players = calculate_per_90(
    position_players, [stat for stat in stats if stat in position_players.columns]
)

# -------------------------
# SCOUTING SCORE
# -------------------------

role_metrics = PLAYER_ROLES[selected_position][role_name]

missing_metrics = [
    metric for metric in role_metrics if metric not in position_players.columns
]
if missing_metrics:
    st.info(
        "The dataset does not include "
        + ", ".join(missing_metrics)
        + ". This role's score uses the available metrics, "
        "with their weights rescaled to total 100%."
    )
    role_metrics = {
        metric: weight
        for metric, weight in role_metrics.items()
        if metric in position_players.columns
    }
    if not role_metrics:
        st.warning("No statistics are available for this role.")
        st.stop()
    total_weight = sum(role_metrics.values())
    role_metrics = {
        metric: weight / total_weight for metric, weight in role_metrics.items()
    }

results = calculate_role_score(position_players, role_metrics)

# -------------------------
# APPLY SEARCH FILTERS
# -------------------------

if selected_clubs:
    results = results[results["Club"].isin(selected_clubs)].copy()

if selected_nationalities:
    results = results[results["Nationality"].isin(selected_nationalities)].copy()

# -------------------------
# SORT RESULTS
# -------------------------

results = results.sort_values(
    "Scouting Score",
    ascending=False,
)

# -------------------------
# HANDLE NO RESULTS
# -------------------------

if results.empty:
    st.warning("No players match your current filters.")
    st.stop()

# -------------------------
# DISPLAY
# -------------------------

st.subheader(f"Top Recommendations — {role_name}")

display_results = (
    results[
        [
            "Player Name",
            "Club",
            "Nationality",
            "Minutes",
            "Scouting Score",
        ]
    ]
    .head(number_of_results)
    .copy()
)

display_results.insert(
    0,
    "Rank",
    range(1, len(display_results) + 1),
)

display_results["Scouting Score"] = display_results["Scouting Score"].round(1)

st.dataframe(
    display_results,
    width="stretch",
    hide_index=True,
    column_config={
        "Player Name": "Player",
        "Club": "Club",
        "Nationality": "Nationality",
        "Minutes": st.column_config.NumberColumn(
            "Minutes",
            format="%d",
        ),
        "Scouting Score": st.column_config.ProgressColumn(
            "Scouting Score",
            min_value=0,
            max_value=100,
            format="%.1f",
        ),
    },
)

st.divider()

st.header("Player Profile")

player_names = results["Player Name"].tolist()

selected_player_name = st.selectbox(
    "Select a player",
    player_names,
)

selected_player = results[results["Player Name"] == selected_player_name].iloc[0]

st.subheader(selected_player["Player Name"])

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "Club",
        selected_player["Club"],
    )

with col2:
    st.metric(
        "Position",
        selected_player["Position"],
    )

with col3:
    st.metric(
        "Scouting Score",
        f"{selected_player['Scouting Score']:.1f}",
    )

for metric in role_metrics:
    percentile_column = f"{metric} Percentile"

    percentile = selected_player[percentile_column]

    actual_value = selected_player[metric]

    clean_name = metric.replace(
        " per 90",
        "",
    )

    if metric.endswith(" per 90"):
        formatted_value = f"{actual_value:.2f} per 90"
    elif metric.endswith("%"):
        formatted_value = f"{actual_value:.1f}%"
    else:
        formatted_value = f"{actual_value:.0f}"

    st.write(f"**{clean_name}** — {formatted_value}")

    st.progress(int(percentile) / 100)

    st.caption(f"{percentile:.0f}th percentile")

chart_data = []

for metric in role_metrics:
    percentile_column = f"{metric} Percentile"

    chart_data.append(
        {
            "Metric": metric.replace(
                " per 90",
                "",
            ),
            "Percentile": selected_player[percentile_column],
        }
    )

chart_df = pd.DataFrame(chart_data)

chart_df = chart_df.sort_values(
    "Percentile",
    ascending=True,
)

st.subheader("Player Statistics")

stats_display = {
    "Appearances": selected_player["Appearances"],
    "Minutes": selected_player["Minutes"],
    "Goals": selected_player["Goals"],
    "Assists": selected_player["Assists"],
    "Goals per 90": selected_player["Goals per 90"],
    "Assists per 90": selected_player["Assists per 90"],
    "Passes per 90": selected_player["Passes per 90"],
    "Progressive Carries per 90": selected_player["Progressive Carries per 90"],
    "Tackles per 90": selected_player["Tackles per 90"],
    "Interceptions per 90": selected_player["Interceptions per 90"],
}

stats_df = pd.DataFrame(
    stats_display.items(),
    columns=[
        "Statistic",
        "Value",
    ],
)

st.dataframe(
    stats_df,
    width="stretch",
    hide_index=True,
)

fig = px.bar(
    chart_df,
    x="Percentile",
    y="Metric",
    orientation="h",
    range_x=[0, 100],
    title="Role Percentiles",
)

st.plotly_chart(
    fig,
    use_container_width=True,
)
