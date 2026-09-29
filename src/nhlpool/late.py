"""Late-season windows, built from per-game goalie rows and date-filtered skater totals.

Goalies: each goalie's starts in his final team's last 20 games.
Skaters: games, ice time and power-play time over the last 42 days of the
regular season, and how many of his team's games he missed in that window.
All of it describes season N-1 and is used only to predict season N.
"""
import pandas as pd

from .fetch import nhl_api as nhl
from .paths import PROCESSED

FIRST, LAST = 2012, 2025
WINDOW_DAYS = 42


def season_end(g: pd.DataFrame) -> pd.Timestamp:
    return pd.to_datetime(g["gameDate"]).max()


def goalie_late(season: int, last_n: int = 20) -> pd.DataFrame:
    g = nhl.goalie_games(season)
    g["gameDate"] = pd.to_datetime(g["gameDate"])
    starts = g[g["gamesStarted"] == 1]
    rows = []
    for team, tg in starts.groupby("teamAbbrev"):
        games = tg.sort_values("gameDate").drop_duplicates("gameId")
        last_ids = set(games["gameId"].tail(last_n))
        cnt = tg[tg.gameId.isin(last_ids)].groupby("playerId").size()
        for pid, n in cnt.items():
            rows.append({"playerId": pid, "team": team, "late_gs": n, "late_games": len(last_ids)})
    df = pd.DataFrame(rows)
    # A goalie traded late can appear for two teams: keep his final team.
    last_team = g.sort_values("gameDate").groupby("playerId")["teamAbbrev"].last()
    df = df[df["team"] == df["playerId"].map(last_team)]
    df["late_share"] = df["late_gs"] / df["late_games"]
    df["seasonId"] = season
    return df[["playerId", "seasonId", "late_share", "late_gs"]]


def team_games_in_window(season: int, start: pd.Timestamp) -> pd.Series:
    g = nhl.goalie_games(season)
    g["gameDate"] = pd.to_datetime(g["gameDate"])
    s = g[(g["gamesStarted"] == 1) & (g["gameDate"] >= start)]
    return s.drop_duplicates(["teamAbbrev", "gameId"]).groupby("teamAbbrev").size()


def skater_late(season: int, last_team: pd.Series) -> pd.DataFrame:
    end = season_end(nhl.goalie_games(season))
    start = end - pd.Timedelta(days=WINDOW_DAYS)
    ds = start.strftime("%Y-%m-%d")
    toi = nhl.skater_window(season, "timeonice", ds)
    summ = nhl.skater_window(season, "summary", ds)
    df = toi[["playerId", "gamesPlayed", "timeOnIcePerGame", "ppTimeOnIcePerGame"]].merge(
        summ[["playerId", "points", "goals"]], on="playerId", how="left")
    tg = team_games_in_window(season, start)
    df["late_team_games"] = df["playerId"].map(last_team).map(tg)
    df = df.rename(columns={"gamesPlayed": "late_gp", "points": "late_pts", "goals": "late_g"})
    df["late_toi_pg"] = df["timeOnIcePerGame"] / 60
    df["late_pp_toi_pg"] = df["ppTimeOnIcePerGame"] / 60
    df["seasonId"] = season
    return df[["playerId", "seasonId", "late_gp", "late_team_games", "late_toi_pg", "late_pp_toi_pg", "late_pts", "late_g"]]


def build() -> tuple[pd.DataFrame, pd.DataFrame]:
    seasons = nhl.season_ids(FIRST, LAST)
    g = pd.concat([goalie_late(s) for s in seasons], ignore_index=True)
    sk = pd.read_csv(PROCESSED / "skaters.csv.gz", usecols=["playerId", "seasonId", "last_team"])
    k = pd.concat([skater_late(s, sk[sk.seasonId == s].set_index("playerId")["last_team"]) for s in seasons],
                  ignore_index=True)
    g.to_csv(PROCESSED / "goalie_late.csv.gz", index=False)
    k.to_csv(PROCESSED / "skater_late.csv.gz", index=False)
    return g, k
