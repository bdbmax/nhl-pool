"""NHL public APIs: api.nhle.com/stats/rest (season tables) and api-web.nhle.com."""
import pandas as pd

from .http import cached_json

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

def _to_date(kind: str, report: str, season: int, as_of: str, extra: str = "") -> pd.DataFrame:
    """Per-player totals over regular-season games up to and including `as_of` (YYYY-MM-DD)."""
    url = (f"{REST}/{kind}/{report}?isAggregate=true&isGame=true&limit=-1"
           f"&cayenneExp=seasonId={season}%20and%20gameTypeId=2%20and%20gameDate%3C=%22{as_of}%22{extra}")
    rel = f"nhl_rest/to_date/{kind}_{report}_{season}_{as_of}{'_ht' if extra else ''}.json"
    return pd.DataFrame(cached_json(url, rel, refresh=True)["data"])


def skaters_to_date(season: int, as_of: str) -> pd.DataFrame:
    return _to_date("skater", "summary", season, as_of)


def goalies_to_date(season: int, as_of: str) -> pd.DataFrame:
    return _to_date("goalie", "summary", season, as_of)


def hat_tricks_to_date(season: int, as_of: str) -> pd.DataFrame:
    """Every skater game with 3+ goals up to `as_of` (one row per game)."""
    url = (f"{REST}/skater/summary?isAggregate=false&isGame=true&limit=-1"
           f"&cayenneExp=seasonId={season}%20and%20gameTypeId=2%20and%20goals%3E=3%20and%20gameDate%3C=%22{as_of}%22")
    return pd.DataFrame(cached_json(url, f"nhl_rest/to_date/hat_tricks_{season}_{as_of}.json", refresh=True)["data"])


def schedule(team: str, season: int, refresh: bool = True) -> list[dict]:
    """A team's regular-season games (gameType 2)."""
    d = cached_json(f"{WEB}/club-schedule-season/{team}/{season}", f"web/schedule_{team}_{season}.json", refresh=refresh)
    return [g for g in d.get("games", []) if g.get("gameType") == 2]
