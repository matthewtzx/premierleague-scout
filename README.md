# Premier League Scout

Explore the Premier League careers of players in current PL squads, find players
with similar statistical styles, and rank players against ten tactical archetypes.
Built with Python, Streamlit, pandas and Plotly.

The dataset comes from the JSON API used by the
[official Premier League statistics site](https://www.premierleague.com/en/stats).
The old bundled CSV has been removed. The app stores a refreshable SQLite snapshot
locally and works offline after the first successful import.

## Run locally

Python 3.9 or later is required; dependencies remain pinned to the versions used
by this project.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m scripts.refresh_data
python -m streamlit run app.py
```

On Windows, activate with `.venv\Scripts\activate` instead. You can also start
Streamlit before importing and press **Load Premier League data**. The initial
import makes several hundred requests and may take several minutes, depending
on the source. Progress is displayed throughout. No API key is required by the
endpoints used here.

## Explore players

1. Choose **Search for a player**, then type a name in the player selector, or
   choose **Filter by club**, pick a club, and select a player.
2. View career appearances, minutes, goals and assists. Expand the full career
   or season-by-season tables for the other statistics.
3. See the closest statistical matches among current players at the same broad
   position. Choose a match for side-by-side totals, per-90 values and an
   interactive percentile chart.
4. Adjust minimum career PL minutes or the number of matches displayed. Players
   with no PL minutes still have profiles but cannot receive a similarity score.

Player IDs identify records and selections, so duplicate names and transfers do
not combine different people. Career totals include previous Premier League
clubs. The club shown beside a player comes from the current squad snapshot.

## Player Archetypes

Press **Player Archetypes** to enter the role-scoring interface. Select a position,
archetype and minimum minutes, then optionally filter by club and nationality.
Use **View career and similar players** to return to that player's main profile.

All ten original archetypes are retained. Their weights now refer to metrics
available in the Premier League feed:

| Position | Archetype | Statistical emphasis |
| --- | --- | --- |
| Goalkeeper | Shot Stopper | Saves, derived save rate, clean sheets per 90, catches |
| Goalkeeper | Sweeper Keeper | Passing, completion, long passes, recoveries, touches |
| Defender | Ball-Playing Defender | Passing, forward distribution, long passes, recoveries, dribbling |
| Defender | Defensive Stopper | Tackles, interceptions, clearances, blocks, ground and aerial duels won |
| Midfielder | Box-to-Box Midfielder | Dribbling, recoveries, tackles, box touches, key passes, interceptions |
| Midfielder | Ball-Winning Midfielder | Tackles, interceptions, recoveries, duels won |
| Midfielder | Creative Midfielder | Assists, through balls, key passes, dribbling, open-play crosses |
| Midfielder | Deep-Lying Playmaker | Passing volume and completion, forward passes, through balls, long passes |
| Forward | Goalscorer | Goals, shots on target, shots, box touches, ground duels won |
| Forward | Creative Forward | Assists, through balls, key passes, dribbling, open-play crosses |

The **Sweeper Keeper** score is a distribution-and-involvement proxy. The feed
does not provide a reliable sweeping-action metric. Successful dribbles also do
not mean progressive carries, and forward passes do not mean final-third passes.
These substitutions are named explicitly in the interface and definitions.

Weights and positional style features live in [`src/roles.py`](src/roles.py).
The interface exposes each archetype's effective weights.

## Data source and coverage

Only Premier League competition `8` is imported, starting with **2006/07**.
Earlier statistics, other domestic leagues, cups and European competitions are
excluded. The app detects the active PL season from the official statistics page
and reads the competition's season catalogue, rather than guessing IDs from
calendar years: for example, 2006/07 has API season ID `7`.

The API base currently used by the website is:

```text
https://sdp-prem-prod.premier-league-prod.pulselive.com/api
```

The importer uses these website endpoints:

| Endpoint | Purpose |
| --- | --- |
| `/v2/competitions/8/details` | Season labels and IDs |
| `/v1/competitions/8/seasons/{season}/teams` | Active-season clubs |
| `/v2/competitions/8/seasons/{season}/teams/{team}/squad` | Current squad membership |
| `/v3/competitions/8/seasons/{season}/players/stats/leaderboard` | Player-season totals, across all clubs |
| `/v1/players/{player}/career` | Check each current player's PL season coverage |
| `/v2/competitions/8/seasons/{season}/players/{player}/stats` | Recover a season missing from the leaderboard |
| `/v1/players/{player}/basic` | Resolve overlapping squads during transfers |

List requests follow `_next` pagination until completion. The importer checks
that there are 20 distinct clubs and no gaps in the covered season catalogue.
Some historical leaderboard records have missing player identities; each current
player’s career history is checked, and missing seasons are requested individually.
Unidentified source-row counts and season metric coverage are recorded in snapshot
metadata. Raw values are retained alongside normalized player-season values.

If the official career summary records a played season but the detailed feed
still has no playing-time record, the summary supplies basic totals. Detailed
metrics for that season remain unavailable, and the player profile shows a
coverage notice. They are not replaced by zero or estimates.

The source's squads define “current players”; squad changes are only reflected
after a refresh and depend on the provider updating its records. This is a website
API, not a versioned service contract for this application. If its response format
or availability changes, the importer may need updating.

### Missing statistics and units

The source uses sparse event counts. As in the site's presentation, an omitted
player count is treated as zero **only if that metric exists elsewhere in the
same season's feed**. A metric absent across an entire season, or explicitly null,
is unavailable. If a player has an unavailable metric in a season they played,
the corresponding career total is unavailable instead of a partial total labeled
as a complete career total.

All counting-statistic per-90 values use summed career totals divided by summed
career minutes, multiplied by 90. Rates are calculated from summed components,
not averaged season percentages:

- Pass completion: `(total passes − unsuccessful passes) / total passes × 100`.
- Long-pass completion: `successful long passes / long passes × 100`.
- Save Rate: `saves / (saves + goals conceded) × 100`, for goalkeepers only. This
  is an app-derived rate, not a claim to reproduce an official save percentage.

Crosses refer to open-play crosses. Recoveries, catches and shots on target map
to `recoveries`, `catches` and `shotsOnTargetIncGoals` respectively. The full mapping
is in [`src/metrics.py`](src/metrics.py). The app intentionally does not use xG/xA
for career similarity because their coverage differs from the core event metrics.

## How comparisons work

Similarity and archetype scores answer different questions.

**Style similarity** compares per-90 activity and selected rates within the same
broad position (`GKP`, `DEF`, `MID`, `FWD`):

```text
metric percentile = average-tie positional rank / cohort size × 100
style similarity = 100 − mean absolute percentile gap from the chosen player
```

Every candidate uses the same features with equal weight. The chosen player and
candidates must meet the minutes threshold (default 900). Unavailable target
features and constant features are omitted with a notice; candidates missing a
remaining feature are excluded. At least four varying features and three players
are required. The chosen player is excluded from the results. Ties use career
minutes and stable source order. A similarity index of 90 is not a 90% probability
that two players play identically.

**Archetype scores** are weighted averages of metric percentiles among eligible
players at that position. Higher values are preferred for each configured metric.
A metric unavailable to the whole cohort is omitted and remaining weights are
normalized. Players missing any remaining metric are not ranked. Club and
nationality filters apply after scoring, preserving the wider positional benchmark.

Neither calculation trains a predictive model. Broad position labels can group
players with different tactical jobs. Career averages hide role changes; per-90
rates do not adjust for team possession, opposition, age, tactics or match context.
These comparisons are starting points for further scouting.

## Refresh and persistence

Use the sidebar's **Refresh Premier League data** button or run:

```bash
python -m scripts.refresh_data
```

Squad and club responses are cached for one hour, current-season statistics and
career histories for one day, and historical statistics for 30 days. Force every
response to be downloaded again with:

```bash
python -m scripts.refresh_data --force
```

Raw responses are cached under `data/cache/`; the complete dataset is saved to
`data/premier_league.sqlite3`. Both are ignored by Git. A refresh validates and
builds a complete snapshot before replacing the previous data in a single database
transaction. Network or validation failure keeps the previous snapshot intact.
Interrupted imports can reuse successful cached responses when retried. There is
no automatic background scheduler; run the CLI periodically or refresh manually.
The app shows the last successful refresh time and warns after a week.

Requests have timeouts, pacing and bounded retries for network failures, HTTP 429
and server errors. HTTP 403 is surfaced as an error. The application does not
attempt to bypass access controls.

## Checks

```bash
python -m unittest discover -s tests -v
python -m pip check
```

Tests cover season filtering and IDs, pagination, coverage reconciliation, snapshot
rollback, career aggregation, missing statistics, zero minutes, similarity cohorts,
role scoring and the Streamlit navigation flows. Test fixtures are synthetic and
are never used as application data.

## Project structure

```text
app.py                    Player search, comparisons and archetype interface
src/pl_api.py             Premier League API client, pagination, caching
src/dataset.py            Import validation, snapshots and career aggregation
src/metrics.py            Source field mappings and units
src/scouting.py           Career rates, similarity and archetype calculations
src/roles.py              Ten archetypes and positional style metrics
scripts/refresh_data.py   Command-line data refresh
tests/                    Data, scoring and interface checks
data/                     Generated database and response cache
```

## Troubleshooting

| Symptom | Action |
| --- | --- |
| No snapshot exists | Use **Load Premier League data** or the refresh CLI. |
| Refresh fails | Check network access and the displayed source error. Retry; the prior snapshot remains usable. |
| Data seems old | Check the refresh time and cache intervals; use `--force` when needed. |
| No similar players | Lower the minutes threshold or select a player with more PL history. |
| Unavailable career statistic | At least one played season lacks that metric; the app avoids presenting partial totals. |
| No archetype recommendations | Broaden filters, lower minimum minutes, or inspect missing-metric notices. |

See [`LICENSE`](LICENSE) for the code license.
