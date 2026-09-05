"""Read-only client for the public JSON endpoints used by premierleague.com."""

import hashlib
import json
import re
import tempfile
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API_BASE = "https://sdp-prem-prod.premier-league-prod.pulselive.com/api"
SOURCE_URL = "https://www.premierleague.com/en/stats"
COMPETITION_ID = "8"
FIRST_YEAR = 2006


class DataSourceError(RuntimeError):
    """An incomplete or unavailable source must never replace a good snapshot."""


class EntityNotFound(DataSourceError):
    """The source explicitly has no record at this endpoint."""


class PremierLeagueAPI:
    def __init__(self, cache_dir, force=False, timeout=30, pause=0.15):
        self.cache_dir = Path(cache_dir)
        self.force = force
        self.timeout = timeout
        self.pause = pause

    def _download(self, url):
        for attempt in range(3):
            try:
                time.sleep(self.pause)
                request = Request(url, headers={
                    "User-Agent": "PremierLeagueScout/2.0",
                    "Accept": "application/json,text/html",
                    "Referer": SOURCE_URL,
                })
                with urlopen(request, timeout=self.timeout) as response:
                    return response.read().decode("utf-8")
            except HTTPError as exc:
                if exc.code == 404:
                    raise EntityNotFound(f"Premier League has no record at: {url}") from exc
                if exc.code == 429 or exc.code >= 500:
                    retry = exc.headers.get("Retry-After", "")
                    time.sleep(min(float(retry), 30) if retry.isdigit() else 2 ** attempt)
                else:
                    raise DataSourceError(f"Premier League returned HTTP {exc.code}: {url}") from exc
            except (URLError, TimeoutError, OSError):
                time.sleep(2 ** attempt)
        raise DataSourceError(f"Could not retrieve Premier League data after 3 attempts: {url}")

    def get(self, path, params=None, ttl=86400):
        url = API_BASE + path
        if params:
            url += "?" + urlencode(params)
        filename = hashlib.sha256(url.encode()).hexdigest() + ".json"
        cache = self.cache_dir / filename
        if not self.force and cache.exists() and time.time() - cache.stat().st_mtime < ttl:
            try:
                return json.loads(cache.read_text())
            except (ValueError, OSError):
                pass
        try:
            result = json.loads(self._download(url))
        except ValueError as exc:
            raise DataSourceError(f"Premier League returned invalid JSON: {url}") from exc
        if not isinstance(result, dict) or ("status" in result and "detail" in result):
            raise DataSourceError(f"Unexpected Premier League response: {url}")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", dir=self.cache_dir, suffix=".tmp", delete=False) as handle:
            json.dump(result, handle)
            temporary = Path(handle.name)
        temporary.replace(cache)
        return result

    def pages(self, path, ttl=86400):
        records, seen = [], set()
        params = {"_limit": 100}
        for _ in range(1000):
            response = self.get(path, params, ttl=ttl)
            if not isinstance(response.get("data"), list) or not isinstance(response.get("pagination"), dict):
                raise DataSourceError(f"Invalid pagination response: {path}")
            records.extend(response["data"])
            cursor = response["pagination"].get("_next")
            if not cursor:
                return records
            if cursor in seen or not response["data"]:
                raise DataSourceError(f"Pagination did not advance: {path}")
            seen.add(cursor)
            params["_next"] = cursor
        raise DataSourceError(f"Too many pages: {path}")

    def seasons(self):
        html = self._download(SOURCE_URL)
        match = re.search(r"ACTIVE_PL_SEASON_ID\s*=\s*['\"]([^'\"]+)", html)
        if not match:
            raise DataSourceError("Could not identify the site's active Premier League season.")
        active_id = match.group(1)
        response = self.get(f"/v2/competitions/{COMPETITION_ID}/details", ttl=3600)
        seasons = []
        for item in response.get("seasons", []):
            label = re.search(r"(\d{4})/(\d{4})", item.get("season", ""))
            if label:
                seasons.append({"id": str(item["id"]), "year": int(label[1]), "label": label[0]})
        active = next((s for s in seasons if s["id"] == active_id), None)
        if active is None:
            raise DataSourceError("The active season is absent from the competition catalogue.")
        seasons = sorted((s for s in seasons if FIRST_YEAR <= s["year"] <= active["year"]), key=lambda s: s["year"])
        if [s["year"] for s in seasons] != list(range(FIRST_YEAR, active["year"] + 1)):
            raise DataSourceError("The season catalogue has a gap after 2006/07.")
        return active, seasons

    def roster(self, season_id):
        base = f"/v1/competitions/{COMPETITION_ID}/seasons/{season_id}"
        teams = self.pages(base + "/teams", ttl=3600)
        if len(teams) != 20 or len({str(t["id"]) for t in teams}) != 20:
            raise DataSourceError("Expected 20 distinct clubs in the active Premier League season.")
        players = {}
        for team in teams:
            response = self.get(
                f"/v2/competitions/{COMPETITION_ID}/seasons/{season_id}/teams/{team['id']}/squad", ttl=3600
            )
            if not response.get("players"):
                raise DataSourceError(f"No squad returned for {team['name']}.")
            for player in response["players"]:
                player_id = str(player["id"])
                entry = {
                    "Player ID": player_id, "Player Name": player["name"]["display"],
                    "Club ID": str(team["id"]), "Club": team["name"],
                    "Nationality": player.get("country", {}).get("country", "Unknown"),
                    "Position": player.get("position", "Unknown"),
                }
                if player_id in players and players[player_id]["Club ID"] != str(team["id"]):
                    # Squad feeds can overlap during a transfer. Resolve against
                    # the site's current player metadata instead of list order.
                    basic = self.get(f"/v1/players/{player_id}/basic", ttl=3600)
                    current_id = str(basic.get("currentTeam", {}).get("id"))
                    if current_id == players[player_id]["Club ID"]:
                        continue
                    if current_id != entry["Club ID"]:
                        raise DataSourceError(f"Cannot resolve current club for {entry['Player Name']}.")
                players[player_id] = entry
        return list(players.values())

    def season_stats(self, season):
        return self.pages(
            f"/v3/competitions/{COMPETITION_ID}/seasons/{season['id']}/players/stats/leaderboard",
            ttl=86400 if season.get("active") else 30 * 86400,
        )

    def career_seasons(self, player_id):
        """PL-only basic totals by season, deduplicated across club memberships."""
        response = self.get(f"/v1/players/{player_id}/career")
        if not isinstance(response.get("person"), list):
            raise DataSourceError(f"Invalid career history for player {player_id}.")
        years, seen = {}, set()
        for person in response["person"]:
            for membership in person.get("membership", []):
                for stat in membership.get("stat", []):
                    label = re.fullmatch(r"(\d{4})/\d{4}", stat.get("tournamentCalendarName", ""))
                    if str(stat.get("opCompetitionId")) == COMPETITION_ID and label and stat.get("minutesPlayed", 0) > 0:
                        identity = (membership.get("opContestantId"), stat.get("tournamentCalendarId"),
                                    stat.get("minutesPlayed"), stat.get("appearances"))
                        if identity in seen:
                            continue
                        seen.add(identity)
                        totals = years.setdefault(int(label[1]), {})
                        for source, key in {"minutesPlayed": "timePlayed", "appearances": "appearances",
                                            "goals": "goals", "assists": "goalAssists",
                                            "yellowCards": "yellowCards"}.items():
                            if source in stat:
                                totals[key] = totals.get(key, 0) + stat[source]
        return years

    def player_season_stats(self, player_id, season_id):
        try:
            return self.get(f"/v2/competitions/{COMPETITION_ID}/seasons/{season_id}/players/{player_id}/stats")
        except EntityNotFound:
            # A known played season may exist only in the career-summary feed.
            return {"stats": {}}
