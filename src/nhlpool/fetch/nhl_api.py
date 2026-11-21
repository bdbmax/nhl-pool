"""NHL public APIs: api.nhle.com/stats/rest (season tables) and api-web.nhle.com."""
import json
from urllib.parse import urlencode

import pandas as pd

from .http import _get, cached_download, cached_json

REST = "https://api.nhle.com/stats/rest/en"
WEB = "https://api-web.nhle.com/v1"

SKATER_REPORTS = ["summary", "timeonice", "powerplay", "scoringpergame", "bios"]
GOALIE_REPORTS = ["summary", "startedVsRelieved", "bios"]


def season_ids(first: int = 2010, last: int = 2025) -> list[int]:
    """Season ids like 20102011, keyed by start year."""
    return [int(f"{y}{y + 1}") for y in range(first, last + 1)]


def report(kind: str, name: str, season: int) -> pd.DataFrame:
    """One NHL stats REST report for a full regular season."""
    url = (
        f"{REST}/{kind}/{name}?isAggregate=false&isGame=false&limit=-1"
        f"&cayenneExp=seasonId={season}%20and%20gameTypeId=2"
    )
    data = cached_json(url, f"nhl_rest/{kind}_{name}_{season}.json")["data"]
    return pd.DataFrame(data)


def hat_trick_games(season: int) -> pd.DataFrame:
    """Every skater game with 3+ goals in a regular season."""
    url = (
        f"{REST}/skater/summary?isAggregate=false&isGame=true&limit=-1"
        f"&cayenneExp=seasonId={season}%20and%20gameTypeId=2%20and%20goals%3E=3"
    )
    data = cached_json(url, f"nhl_rest/hat_tricks_{season}.json")["data"]
    return pd.DataFrame(data)


def teams() -> pd.DataFrame:
    data = cached_json(f"{REST}/team", "nhl_rest/teams.json")["data"]
    return pd.DataFrame(data)[["id", "triCode", "fullName"]].rename(
        columns={"id": "teamId", "triCode": "team"}
    )


def current_team_abbrevs() -> list[str]:
    d = cached_json(f"{WEB}/standings/now", "web/standings_now.json")
    return sorted(t["teamAbbrev"]["default"] for t in d["standings"])


def roster(team: str, season: int, refresh: bool = False) -> pd.DataFrame:
    d = cached_json(f"{WEB}/roster/{team}/{season}", f"web/roster_{team}_{season}.json", refresh=refresh)
    rows = []
    for group, players in d.items():
        for p in players:
            rows.append(
                {
                    "playerId": p["id"],
                    "name": f"{p['firstName']['default']} {p['lastName']['default']}",
                    "pos": p["positionCode"],
                    "team": team,
                    "birthDate": p.get("birthDate"),
                    "roster_group": group,
                }
            )
    return pd.DataFrame(rows)


def all_rosters(season: int, refresh: bool = False) -> pd.DataFrame:
    return pd.concat([roster(t, season, refresh) for t in current_team_abbrevs()], ignore_index=True)


def landing(player_id: int, refresh: bool = False) -> dict:
    return cached_json(f"{WEB}/player/{player_id}/landing", f"web/landing/{player_id}.json", refresh=refresh)


def fetch_history(first: int = 2010, last: int = 2025) -> None:
    """Download every historical table used by the model."""
    for s in season_ids(first, last):
        for r in SKATER_REPORTS:
            report("skater", r, s)
        for r in GOALIE_REPORTS:
            report("goalie", r, s)
        report("team", "summary", s)
        hat_trick_games(s)
        print(f"  nhl {s} ok")
    teams()


def logo_svg(team: str, refresh: bool = False) -> str:
    """Official team logo (light-background version), cached."""
    from .http import cached_text
    return cached_text(f"https://assets.nhle.com/logos/nhl/svg/{team}_light.svg", f"logos/{team}.svg", refresh=refresh)


def goalie_games(season: int, game_type: int = 2) -> pd.DataFrame:
    """Every goalie appearance in a season (about 2,800 rows, under the API's 10,000 cap)."""
    url = (f"{REST}/goalie/summary?isAggregate=false&isGame=true&limit=-1"
           f"&cayenneExp=seasonId={season}%20and%20gameTypeId={game_type}")
    return pd.DataFrame(cached_json(url, f"nhl_rest/goalie_games_{season}_{game_type}.json")["data"])


def skater_window(season: int, report: str, start: str) -> pd.DataFrame:
    """Per-player totals over games on or after `start` (YYYY-MM-DD) in a regular season."""
    url = (f"{REST}/skater/{report}?isAggregate=true&isGame=true&limit=-1"
           f"&cayenneExp=seasonId={season}%20and%20gameTypeId=2%20and%20gameDate%3E=%22{start}%22")
    return pd.DataFrame(cached_json(url, f"nhl_rest/skater_{report}_from_{start}_{season}.json")["data"])


def playoffs(kind: str, season: int) -> pd.DataFrame:
    url = (f"{REST}/{kind}/summary?isAggregate=false&isGame=false&limit=-1"
           f"&cayenneExp=seasonId={season}%20and%20gameTypeId=3")
    return pd.DataFrame(cached_json(url, f"nhl_rest/{kind}_summary_{season}_playoffs.json")["data"])


# --- Season to date (the daily job). Always re-downloaded: these change every night. ---

def _game_report(kind: str, filters: str, cache_name: str, aggregate: bool = False) -> pd.DataFrame:
    """Fetch a complete report before replacing the cached copy."""
    key_fields = ("playerId",) if aggregate else ("gameId", "playerId")
    params = {
        "isAggregate": str(aggregate).lower(),
        "isGame": "true",
        "cayenneExp": filters,
        "limit": 100,  # the API caps responses at 100 rows, including requests for limit=-1
        "sort": json.dumps([{"property": field, "direction": "ASC"} for field in key_fields]),
    }

    def download() -> str:
        rows, seen = [], set()
        total = None
        while total is None or len(rows) < total:
            query = urlencode({**params, "start": len(rows)})
            page = _get(f"{REST}/{kind}/summary?{query}").json()
            if total is None:
                total = page["total"]
            batch = page["data"]
            keys = {tuple(row[field] for field in key_fields) for row in batch}
            if (page["total"] != total or len(rows) + len(batch) > total
                    or (not batch and len(rows) < total) or len(keys) != len(batch) or seen & keys):
                raise RuntimeError(f"Inconsistent NHL {cache_name} at offset {len(rows)} of {total}")
            rows.extend(batch)
            seen.update(keys)
        return json.dumps({"data": rows, "total": total}, separators=(",", ":"))

    report = json.loads(cached_download(f"nhl_rest/to_date/{cache_name}.json", True, download))
    rows = report["data"]
    if len(rows) != report["total"]:
        raise RuntimeError(f"Incomplete NHL {cache_name}: {len(rows)} of {report['total']} rows")
    return pd.DataFrame(rows)


def skaters_to_date(season: int, as_of: str) -> pd.DataFrame:
    return _game_report("skater", f'seasonId={season} and gameTypeId=2 and gameDate<="{as_of}"',
                        f"skater_summary_{season}_{as_of}", aggregate=True)


def goalies_to_date(season: int, as_of: str) -> pd.DataFrame:
    return _game_report("goalie", f'seasonId={season} and gameTypeId=2 and gameDate<="{as_of}"',
                        f"goalie_summary_{season}_{as_of}", aggregate=True)


def hat_tricks_to_date(season: int, as_of: str) -> pd.DataFrame:
    """Every skater game with 3+ goals up to `as_of` (one row per game)."""
    filters = f'seasonId={season} and gameTypeId=2 and goals>=3 and gameDate<="{as_of}"'
    return _game_report("skater", filters, f"hat_tricks_{season}_{as_of}")


def schedule(team: str, season: int, refresh: bool = True) -> list[dict]:
    """A team's regular-season games (gameType 2)."""
    d = cached_json(f"{WEB}/club-schedule-season/{team}/{season}", f"web/schedule_{team}_{season}.json", refresh=refresh)
    return [g for g in d.get("games", []) if g.get("gameType") == 2]


def goalie_games_to_date(season: int, as_of: str) -> pd.DataFrame:
    """Every goalie appearance up to `as_of`, with the team he played for (about 2,800 rows a season)."""
    return _game_report("goalie", f'seasonId={season} and gameTypeId=2 and gameDate<="{as_of}"',
                        f"goalie_games_{season}_{as_of}")


def skater_games_on(season: int, day: str) -> pd.DataFrame:
    """Every skater line of one day's games, with the game id (the evening update keeps finished games only)."""
    return _game_report("skater", f'seasonId={season} and gameTypeId=2 and gameDate="{day}"',
                        f"skater_games_{season}_{day}")
