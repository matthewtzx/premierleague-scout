# Premier League Scout

An interactive football scouting dashboard that helps you find Premier League
players whose statistics match specific tactical roles. Built with Python and
Streamlit, it turns player statistics into per-90 metrics, percentile rankings,
and weighted scouting scores.

Use it to build a shortlist, explore a player's statistical strengths, or compare
how players rank under different role definitions. For example, you can look for
a creative midfielder using passing and chance-creation metrics, then switch to
a ball-winning midfielder to focus on defensive contributions.

## Features

- **10 tactical roles across four positions:** goalkeepers, defenders,
  midfielders, and forwards.
- **Scouting filters:** set a minimum playing-time threshold and narrow results
  by club and nationality.
- **Ranked recommendations:** display up to 5–30 players, with rank, club,
  nationality, minutes, and a scouting score out of 100.
- **Player profiles:** inspect a player's club, position, score, and individual
  role metrics.
- **Statistical breakdowns:** view raw totals, per-90 values, percentile progress
  bars, and an interactive Plotly chart.
- **Missing-metric handling:** see which role metrics are unavailable and receive
  a score based on the remaining metrics.

The app reads a local CSV. It does not fetch live results, update player data
automatically, or require an API key.

## Getting started

You need Python with `pip` and the project files, including
[`data/players.csv`](data/players.csv). The app has been checked locally with
Python 3.9.6 and Streamlit 1.50.0. Direct dependencies are pinned to the versions
tested locally; transitive dependencies are resolved by pip.

From the project directory, create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

On Windows PowerShell, use these commands instead:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Install the dependencies and start the dashboard:

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Open the local URL printed in the terminal. Keep the terminal running while using
the app, and press `Ctrl+C` to stop it.

For later sessions, activate the existing virtual environment and run the same
Streamlit command; you do not need to recreate the environment.

## Using the dashboard

1. **Set minimum minutes.** The default is 900, with a slider from 0 to 3,000.
   Players with zero or negative minutes are always excluded.
2. **Choose a position and role.** The available roles change with the position.
3. **Optionally select clubs and nationalities.** Leave either filter empty to
   include all values. Multiple selections within a filter are alternatives;
   when both filters are set, players must satisfy both.
4. **Choose the number of recommendations.** The default is 10. Fewer rows appear
   if fewer players match your filters.
5. **Explore a player profile.** The player selector includes all matching
   players, even those outside the displayed recommendation limit.

If no players match, the app displays a message. Lower the minutes threshold or
broaden the club and nationality filters to see more results.

## Available roles

The exact metrics and weights are defined in [`src/roles.py`](src/roles.py).

| Position | Role | Statistical focus |
| --- | --- | --- |
| Goalkeeper (`GKP`) | Shot Stopper | Saves, save percentage, clean sheets, punches |
| Goalkeeper (`GKP`) | Sweeper Keeper | Sweeping, passing, save percentage, high claims |
| Defender (`DEF`) | Ball-Playing Defender | Passing, final-third passes, interceptions, possession won, progressive carries |
| Defender (`DEF`) | Defensive Stopper | Tackles, interceptions, clearances, blocks, duels won |
| Midfielder (`MID`) | Box-to-Box Midfielder | Progressive carries, possession won, tackles, final-third passes, interceptions |
| Midfielder (`MID`) | Ball-Winning Midfielder | Tackles, interceptions, possession won, duels won |
| Midfielder (`MID`) | Creative Midfielder | Assists, through balls, final-third passes, progressive carries, successful crosses |
| Midfielder (`MID`) | Deep-Lying Playmaker | Passing volume and completion, final-third passes, through balls, progressive carries |
| Forward (`FWD`) | Goalscorer | Goals, shots on target, shots, box touches, ground duels won |
| Forward (`FWD`) | Creative Forward | Assists, through balls, final-third passes, progressive carries, successful crosses |

Sweeping and box touches are part of the configured role definitions but are
absent from the bundled dataset. See the missing-data behavior below.

## How scoring works

### 1. Establish the comparison group

The app first selects players who meet the minutes threshold and play the chosen
position. Each player's statistics are ranked against this group.

Club and nationality filters are applied **after scoring**. Selecting one club
therefore keeps the broader positional benchmark. Changing the minutes threshold
changes the comparison group and can change scores.

### 2. Calculate per-90 statistics

Counting statistics in the app's `stats` list are converted using:

```text
Statistic per 90 = statistic total / minutes played × 90
```

For example, five assists in 900 minutes becomes 0.5 assists per 90.
Percentage columns such as `Saves %` are converted from strings like `75%` to
numeric values. Metrics configured as percentages or raw totals retain those
units; clean sheets currently use the raw total.

### 3. Rank each role metric

For each metric, the app uses pandas' `rank(pct=True) × 100`. Higher values receive
higher ranks, and tied values share their average rank. These are relative ranks
within the selected comparison group, rather than fixed performance targets.

### 4. Combine the percentiles

```text
Scouting score = sum(metric percentile × metric weight)
```

For example, the Creative Midfielder role uses:

| Metric | Weight |
| --- | ---: |
| Assists per 90 | 20% |
| Through Balls per 90 | 25% |
| fThird Passes per 90 | 25% |
| Progressive Carries per 90 | 20% |
| Successful Crosses per 90 | 10% |

The recommendation table sorts scores from highest to lowest and displays one
decimal place. A score of 85 is a weighted average of metric percentiles; it does
not mean the player is in the 85th percentile of the final score distribution or
has an 85% probability of succeeding in that role.

### Missing role metrics

If a configured metric is absent, the app shows a notice, excludes that metric,
and rescales the remaining weights to total 100%. It does not invent values for
missing statistics. If no metrics remain, it stops with a message.

In the bundled CSV:

- `High Claims` is the goalkeeper claims column.
- `Keeper Sweeper` is missing, so Sweeper Keeper scores use the other four metrics.
- `Touches Box` is missing, so Goalscorer scores use the other four metrics.

For example, removing the Sweeper Keeper metric with a 30% weight leaves 70% of
the original weights. Each remaining weight is divided by 0.70. This keeps the
score on the same scale, but changes what the score measures.

## Dataset requirements

The dashboard loads [`data/players.csv`](data/players.csv) relative to `app.py`.
To use a replacement dataset, preserve the expected column names and units.

| Purpose | Columns |
| --- | --- |
| Identity and filters | `Player Name`, `Club`, `Nationality`, `Position` |
| Playing time | `Appearances`, `Minutes` |
| Profile statistics | `Goals`, `Assists`, `Passes`, `Progressive Carries`, `Tackles`, `Interceptions` |
| Role scoring | Additional metrics referenced by `PLAYER_ROLES`, such as `Saves %`, `Through Balls`, and `gDuels Won` |

Use `GKP`, `DEF`, `MID`, or `FWD` for positions. Counting statistics should contain
numeric totals for a consistent reporting period. Percentage columns may contain
values such as `75%`; the app strips the trailing percent sign before conversion.
Keep player names unique because the profile selector identifies players by name.

Missing-role handling does not replace general CSV validation: required identity
and profile columns must still exist, and values should be complete and valid.
The app does not verify the dataset's source, season, or accuracy.

## Project structure

```text
premierleague-scout/
├── app.py              # Dashboard, data preparation, filters, and visualizations
├── data/
│   └── players.csv     # Local player statistics
├── src/
│   ├── roles.py        # Position-specific role metrics and weights
│   └── scouting.py     # Per-90 calculations and weighted percentile scoring
├── requirements.txt    # Python dependencies
├── README.md
└── LICENSE
```

Streamlit provides the interface, pandas handles data processing, and Plotly
renders the percentile chart.

## Customizing the scouting model

Edit `PLAYER_ROLES` in [`src/roles.py`](src/roles.py) to add a role or change its
weights. Use nonnegative weights that sum to `1.0`; complete role definitions
are used as written without automatic normalization.

For a new per-90 metric, add its raw column to the CSV and to the `stats` list in
[`app.py`](app.py), then reference it as `Column Name per 90` in the role.
Percentage or total metrics can be referenced by their existing column names.

The current ranking logic always treats a higher value as better. Metrics where
lower is preferable, such as errors or goals conceded, require a change to the
ranking logic before they can be used meaningfully.

## Checks and troubleshooting

To check installed dependency compatibility, run:

```bash
python -m pip check
```

| Symptom | What to check |
| --- | --- |
| `streamlit: command not found` | Activate `.venv`, install the requirements, and use `python -m streamlit run app.py`. |
| `ModuleNotFoundError` | Install requirements with the same Python interpreter used to launch the app. |
| CSV file not found | Confirm `data/players.csv` exists alongside the project files. |
| `KeyError` after replacing the CSV | Check exact column names, including capitalization and spaces, against the dataset requirements. |
| Numeric conversion error | Check numeric and percentage columns for invalid text or inconsistent values. |
| No matching players | Broaden filters or lower the minutes threshold. |
| Missing-statistics notice | Supply the missing columns or interpret the score using the available metrics listed in the role. |

## Interpretation and limitations

The model provides a transparent statistical shortlist. Its weights are manually
defined, and it does not train a machine-learning model or predict future
performance. Scores should support further scouting and video analysis.

Per-90 normalization reduces playing-time differences but does not adjust for
team possession, tactical system, opposition strength, age, injuries, or match
context. Small samples can produce extreme rates, and raw clean-sheet totals
remain sensitive to playing time. A higher minutes threshold can improve sample
size, while also changing the comparison group.

Scores from different roles, datasets, or minutes thresholds are not directly
equivalent. Missing metrics can also weaken how well a score represents its
named role, especially when the absent metric describes a defining behavior.

## License

See [`LICENSE`](LICENSE) for the project license.
