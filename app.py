"""Premier League Scout: current players, career statistics, and archetypes."""

from datetime import datetime, timezone
import sqlite3

import pandas as pd
import plotly.express as px
import streamlit as st

from src.dataset import DEFAULT_DATABASE, build_snapshot, load_snapshot, save_snapshot
from src.metrics import COUNTING_METRICS, POSITION_NAMES, RATE_METRICS
from src.pl_api import DataSourceError, PremierLeagueAPI
from src.roles import PLAYER_ROLES, ROLE_NOTES
from src.scouting import (
    available_role_metrics, calculate_role_score, prepare_players, similar_players,
)

st.set_page_config(page_title="Premier League Scout", page_icon="⚽", layout="wide")

CHART_CONFIG = {
    "modeBarButtonsToRemove": [
        "zoom2d", "pan2d", "zoomIn2d", "zoomOut2d", "autoScale2d", "resetScale2d",
        "select2d", "lasso2d",
    ],
}

COMPARISON_CORE_METRICS = [
    "Appearances", "Minutes", "Goals", "Goals per 90", "Assists", "Assists per 90",
]
HIGHER_STAT_HIGHLIGHT = "background-color: rgba(144, 238, 144, 0.5)"


@st.cache_data(show_spinner=False)
def read_players(revision):
    players, seasons, metadata = load_snapshot()
    return prepare_players(players), seasons, metadata


def refresh():
    with st.status("Updating Premier League data…", expanded=True) as status:
        message = st.empty()
        try:
            api = PremierLeagueAPI(DEFAULT_DATABASE.parent / "cache")
            roster, records, metadata = build_snapshot(api, progress=message.write)
            save_snapshot(DEFAULT_DATABASE, roster, records, metadata)
        except (DataSourceError, OSError, ValueError, sqlite3.Error) as exc:
            status.update(label="Refresh failed", state="error")
            st.error(f"{exc} Your previous snapshot has been retained.")
            return
        read_players.clear()
        status.update(label=f"Updated {len(roster)} players", state="complete")
    st.rerun()


def navigate(page, player_id=None):
    st.session_state.page = page
    if player_id is not None:
        st.session_state.selected_player = player_id
        st.session_state.pending_player = player_id
        st.session_state.find_method = "Search for a player"


def player_label(players, player_id):
    row = players.loc[players["Player ID"] == player_id].iloc[0]
    return f"{row['Player Name']} · {row['Club']} · #{player_id}"


def format_stat(value, metric):
    if pd.isna(value):
        return "Unavailable"
    if metric.endswith("%"):
        return f"{value:.1f}%"
    if metric.endswith("per 90"):
        return f"{value:.2f}"
    return f"{value:,.0f}"


def profile(player, seasons):
    st.header(player["Player Name"])
    st.write(f"{player['Club']} · {POSITION_NAMES.get(player['Position'], 'Unknown position')} · {player['Nationality']}")
    cols = st.columns(4)
    for column, metric in zip(cols, ["Appearances", "Minutes", "Goals", "Assists"]):
        column.metric(metric, format_stat(player[metric], metric))
    st.caption("Career Premier League totals from 2006/07 onward, including previous PL clubs. Other competitions are excluded.")
    if player.get("Coverage Note"):
        st.warning(player["Coverage Note"] + "Basic totals use the official career summary; incomplete detailed career metrics are unavailable for comparisons.")
    if player["Seasons Played"] == 0:
        st.info("This player is in a current squad but has no recorded Premier League minutes in the covered seasons.")
    with st.expander("Full career statistics"):
        rows = [{"Statistic": metric, "Career total": format_stat(player[metric], metric),
                 "Per 90": format_stat(player[f"{metric} per 90"], f"{metric} per 90")}
                for metric in COUNTING_METRICS]
        rows.extend({"Statistic": metric, "Career total": format_stat(player[metric], metric), "Per 90": "—"}
                    for metric in RATE_METRICS)
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        st.caption("Crosses are open-play crosses. Save Rate is saves ÷ (saves + goals conceded), calculated by this app. Unavailable values are not treated as zero.")
    with st.expander("Season-by-season statistics"):
        history = seasons[seasons["Player ID"] == player["Player ID"]].sort_values("Start Year", ascending=False)
        if history.empty:
            st.write("No Premier League appearances recorded.")
        else:
            st.dataframe(history[["Season", *COUNTING_METRICS]], hide_index=True, width="stretch")
            st.caption("A season is combined across clubs when a player transfers within the Premier League.")


def comparisons(players, player_id):
    st.subheader("Players with similar styles")
    controls = st.columns(2)
    minimum = controls[0].number_input("Minimum career PL minutes", min_value=0, max_value=100000,
                                       value=900, step=100, key="similarity_minutes")
    limit = controls[1].slider("Similar players to show", 3, 10, 5)
    matches, features, percentiles, note = similar_players(players, player_id, minimum, limit)
    if note:
        st.info(note)
    if matches.empty:
        return
    st.caption(f"Compared within a group of {len(percentiles)} current players at the same broad position, using {len(features)} career statistical measures. The chosen player also meets the minutes threshold.")
    st.dataframe(matches[["Player Name", "Club", "Minutes", "Similarity"]], hide_index=True,
                 width="stretch", column_config={
                     "Similarity": st.column_config.ProgressColumn("Style similarity / 100", min_value=0, max_value=100, format="%.1f"),
                 })
    chosen = st.selectbox("Compare with", matches["Player ID"].tolist(),
                          format_func=lambda pid: player_label(players, pid), key=f"compare_{player_id}")
    target = players.loc[players["Player ID"] == player_id].iloc[0]
    other = players.loc[players["Player ID"] == chosen].iloc[0]
    target_label = f"{target['Player Name']} (#{player_id})"
    other_label = f"{other['Player Name']} (#{chosen})"
    comparison_metrics = list(dict.fromkeys([*COMPARISON_CORE_METRICS, *features]))
    raw = [{"Metric": metric, target_label: target[metric], other_label: other[metric]}
           for metric in comparison_metrics]
    comparison = pd.DataFrame(raw)

    def highlight_higher_stat(row):
        target_value = comparison.loc[row.name, target_label]
        other_value = comparison.loc[row.name, other_label]
        styles = pd.Series("", index=row.index)
        if pd.notna(target_value) and pd.notna(other_value) and target_value != other_value:
            higher_column = target_label if target_value > other_value else other_label
            styles[higher_column] = HIGHER_STAT_HIGHLIGHT
        return styles

    display_comparison = comparison.astype({target_label: "object", other_label: "object"})
    for index, metric in enumerate(comparison_metrics):
        for label in [target_label, other_label]:
            display_comparison.loc[index, label] = format_stat(comparison.loc[index, label], metric)
    formatted_comparison = display_comparison.style.apply(highlight_higher_stat, axis=1)
    st.dataframe(formatted_comparison, hide_index=True, width="stretch")
    chart_metrics = [metric for metric in comparison_metrics if metric in features]
    chart_rows = [
        {"Metric": metric, "Player": name,
         "Positional percentile": percentiles.loc[pid, metric]}
        for pid, name in [(player_id, target_label), (chosen, other_label)]
        for metric in chart_metrics
    ]
    figure = px.bar(pd.DataFrame(chart_rows), x="Positional percentile", y="Metric", color="Player",
                    barmode="group", orientation="h", range_x=[0, 100],
                    category_orders={"Metric": chart_metrics},
                    color_discrete_sequence=["#6f42c1", "#009e89"], height=max(420, len(chart_metrics) * 65))
    figure.update_layout(legend_title_text="", yaxis_title=None, margin=dict(l=0, r=0, t=15, b=0))
    figure.update_traces(hovertemplate=(
        "Player = %{fullData.name}<br>Metric = %{y}<br>Positional percentile = %{x:.1f}<extra></extra>"
    ))
    st.plotly_chart(figure, use_container_width=True, config=CHART_CONFIG)
    gaps = (percentiles.loc[player_id] - percentiles.loc[chosen]).abs().sort_values()
    st.write("**Closest statistical matches:** " + ", ".join(gaps.head(3).index) + ".")
    st.write("**Largest differences:** " + ", ".join(gaps.tail(2).index[::-1]) + ".")
    st.button(f"Open {other['Player Name']}'s profile", on_click=navigate, args=("players", chosen))
    with st.expander("How style similarity works"):
        st.write("Each statistic is ranked within the same positional group. Similarity is 100 minus the average absolute gap in those percentiles, with equal weight per metric. Every candidate uses the same available metrics. A higher index means closer statistical profiles; it is not a probability or a measure of who is better.")
        st.write("Career averages can hide changes in role. Team possession, tactical system and opposition also affect these statistics. Small samples remain uncertain, even after converting totals to per-90 rates.")


def player_view(players, seasons):
    method = st.radio("Find a player", ["Search for a player", "Filter by club"], horizontal=True, key="find_method")
    pool = players.sort_values(["Player Name", "Player ID"])
    if method == "Filter by club":
        clubs = sorted(players["Club"].unique())
        preferred = st.session_state.get("selected_player")
        preferred_rows = players[players["Player ID"] == preferred]
        default_club = preferred_rows.iloc[0]["Club"] if not preferred_rows.empty else clubs[0]
        club = st.selectbox("Club", clubs, index=clubs.index(default_club))
        pool = pool[pool["Club"] == club]
    ids = pool["Player ID"].tolist()
    preferred = st.session_state.get("selected_player")
    # A separate widget key allows profile navigation to update selection safely.
    selection_key = f"player_picker_{method}_{pool.iloc[0]['Club'] if method == 'Filter by club' else 'all'}"
    pending = st.session_state.pop("pending_player", None)
    if pending in ids:
        st.session_state[selection_key] = pending
    elif selection_key not in st.session_state:
        st.session_state[selection_key] = preferred if preferred in ids else None
    elif st.session_state[selection_key] not in ids:
        st.session_state[selection_key] = None
    # Streamlit's selectbox provides case-insensitive type-to-search matching.
    selected = st.selectbox("Select a player — type a name to search", ids,
                            index=None,
                            placeholder="Choose a current Premier League player",
                            format_func=lambda pid: player_label(players, pid), key=selection_key)
    if selected is None:
        st.info("Search by name or choose a club to explore a player's PL career and closest statistical matches.")
        return
    st.session_state.selected_player = selected
    profile(players.loc[players["Player ID"] == selected].iloc[0], seasons)
    st.divider()
    comparisons(players, selected)


def archetype_view(players):
    st.header("Player Archetypes")
    st.write("Find current Premier League players whose career statistics fit a tactical role.")
    controls = st.columns(3)
    position = controls[0].selectbox("Position", list(PLAYER_ROLES), format_func=POSITION_NAMES.get)
    role = controls[1].selectbox("Archetype", list(PLAYER_ROLES[position]))
    minimum = controls[2].number_input("Minimum career PL minutes", 0, 100000, 900, 100, key="role_minutes")
    cohort = players[(players["Position"] == position) & (players["Minutes"] >= minimum) & (players["Minutes"] > 0)]
    if cohort.empty:
        st.info("No players meet this position and minutes threshold.")
        return
    metrics, missing = available_role_metrics(cohort, PLAYER_ROLES[position][role])
    if missing:
        st.info("Unavailable metrics omitted and weights rescaled: " + ", ".join(missing))
    if not metrics:
        st.warning("No metrics are available for this archetype.")
        return
    if role in ROLE_NOTES:
        st.caption(ROLE_NOTES[role])
    results = calculate_role_score(cohort, metrics)
    incomplete = results["Scouting Score"].isna().sum()
    if incomplete:
        st.info(f"{incomplete} players lack complete career coverage for the selected metrics and cannot be ranked.")
    results = results.dropna(subset=["Scouting Score"])
    filters = st.columns(2)
    clubs = filters[0].multiselect("Clubs", sorted(cohort["Club"].unique()))
    countries = filters[1].multiselect("Nationalities", sorted(cohort["Nationality"].unique()))
    if clubs:
        results = results[results["Club"].isin(clubs)]
    if countries:
        results = results[results["Nationality"].isin(countries)]
    results = results.sort_values("Scouting Score", ascending=False)
    st.caption("Scores are weighted positional percentiles. Club and nationality filters keep the wider positional benchmark.")
    with st.expander("Archetype metrics and weights"):
        st.dataframe(pd.DataFrame([{"Metric": m, "Weight (%)": round(w * 100, 1)} for m, w in metrics.items()]),
                     hide_index=True, width="stretch")
    if results.empty:
        st.info("No players match these filters with complete statistics.")
        return
    limit = st.slider("Recommendations to show", 5, 30, 10, 5)
    st.dataframe(results[["Player Name", "Club", "Nationality", "Minutes", "Scouting Score"]].head(limit),
                 hide_index=True, width="stretch", column_config={
                     "Scouting Score": st.column_config.ProgressColumn("Archetype score / 100", min_value=0, max_value=100, format="%.1f"),
                 })
    selected = st.selectbox("Explore an archetype player", results["Player ID"].tolist(),
                            format_func=lambda pid: player_label(players, pid))
    row = results[results["Player ID"] == selected].iloc[0]
    st.button("View career and similar players", on_click=navigate, args=("players", selected), type="primary")
    chart = pd.DataFrame([{"Metric": m, "Percentile": row[f"{m} Percentile"]} for m in metrics])
    figure = px.bar(chart, x="Percentile", y="Metric", orientation="h", range_x=[0, 100],
                    title=f"{row['Player Name']} · {role}")
    figure.update_traces(hovertemplate="Metric = %{y}<br>Percentile = %{x:.1f}<extra></extra>")
    st.plotly_chart(figure, use_container_width=True,
                    config=CHART_CONFIG)


def main():
    st.title("⚽ Premier League Scout ⚽️")
    st.caption("Find players of similar styles with your chosen player.")
    page = st.session_state.get("page", "players")
    nav = st.columns([1, 1, 3])
    nav[0].button("Player Search", on_click=navigate, args=("players",),
                  type="primary" if page == "players" else "secondary", use_container_width=True)
    nav[1].button("Player Archetypes", on_click=navigate, args=("archetypes",),
                  type="primary" if page == "archetypes" else "secondary", use_container_width=True)
    st.sidebar.header("Premier League data")
    st.sidebar.caption("Official PL statistics · 2006/07 onward")
    if st.sidebar.button("Refresh Premier League data"):
        refresh()
    try:
        revision = DEFAULT_DATABASE.stat().st_mtime_ns if DEFAULT_DATABASE.exists() else 0
        players, seasons, metadata = read_players(revision)
    except (DataSourceError, OSError) as exc:
        st.info(str(exc))
        st.write("The first import collects current squads and the covered PL seasons. It can take several minutes; subsequent refreshes reuse cached responses.")
        if st.button("Load Premier League data", type="primary"):
            refresh()
        st.code("python -m scripts.refresh_data", language="bash")
        return
    refreshed = datetime.fromisoformat(metadata["refreshed_at"])
    age = datetime.now(timezone.utc) - refreshed
    st.sidebar.write(f"{len(players)} players · {metadata['active_season']} squads")
    st.sidebar.caption(f"Last refreshed: {refreshed:%d %b %Y, %H:%M} UTC")
    st.sidebar.link_button("Premier League statistics", metadata["source"])
    if age.days >= 7:
        st.sidebar.warning("This snapshot is over a week old. Refresh to check transfers and recent matches.")
    st.sidebar.caption("Squads refresh after one hour; current-season statistics after one day. Historical responses are cached for 30 days.")
    if page == "archetypes":
        archetype_view(players)
    else:
        player_view(players, seasons)


main()
