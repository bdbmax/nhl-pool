"""Build tidy player-season and team-season tables from the cached raw data.

Outputs (data/processed):
  skaters.csv.gz   one row per skater-season, raw counts + features + fantasy points
  goalies.csv.gz   one row per goalie-season
  teams.csv.gz     one row per team-season
"""
import numpy as np
import pandas as pd

from .fetch import moneypuck as mp
from .fetch import nhl_api as nhl
from .paths import PROCESSED
from .scoring import fantasy_points, pos_group

FIRST, LAST = 2010, 2025  # season start years

# MoneyPuck uses dotted codes for some teams.
MP_TEAM = {"T.B": "TBL", "N.J": "NJD", "L.A": "LAK", "S.J": "SJS"}
# Franchise continuity for "prior season team strength".
FRANCHISE = {"ARI": "UTA", "PHX": "UTA", "ATL": "WPG"}


def _sec(x):
    return pd.to_numeric(x, errors="coerce")


def season_games() -> pd.Series:
    """Scheduled games per team by season (82, or 48/70/56 in short years)."""
    out = {}
    for s in nhl.season_ids(FIRST, LAST):
        t = nhl.report("team", "summary", s)
        out[s] = float(t["gamesPlayed"].median())
    return pd.Series(out, name="season_games")


def _moneypuck_teams(year: int) -> pd.DataFrame:
    """Team expected goals for and against (all situations) and 5-on-4 ice time, in seconds."""
    m = mp.season_summary(year, "teams")
    a = m[m.situation == "all"][["team", "xGoalsFor", "xGoalsAgainst"]].rename(
        columns={"xGoalsFor": "team_xGF", "xGoalsAgainst": "team_xGA"})
    pp = m[m.situation == "5on4"][["team", "iceTime"]].rename(columns={"iceTime": "team_pp_sec"})
    out = a.merge(pp, on="team", how="left")
    out["team"] = out["team"].replace(MP_TEAM)
    return out


def build_teams() -> pd.DataFrame:
    tm = nhl.teams()
    rows = []
    for s in nhl.season_ids(FIRST, LAST):
        t = nhl.report("team", "summary", s).merge(tm[["teamId", "team"]], on="teamId", how="left")
        t["mp_team"] = t["team"].replace({"PHX": "ARI"})  # MoneyPuck uses ARI for Phoenix too
        t = t.merge(_moneypuck_teams(s // 10000).rename(columns={"team": "mp_team"}), on="mp_team", how="left")
        t["seasonId"] = s
        rows.append(t)
    t = pd.concat(rows, ignore_index=True)
    t = t.rename(
        columns={"gamesPlayed": "team_gp", "wins": "team_W", "otLosses": "team_OTL",
                 "goalsFor": "team_GF", "goalsAgainst": "team_GA", "winsInShootout": "team_SOW"}
    )
    t["team_SA_pg"] = t["shotsAgainstPerGame"]
    t["team_pp_pg"] = t["team_pp_sec"] / 60 / t["team_gp"]  # 5-on-4 minutes per game
    t["franchise"] = t["team"].replace(FRANCHISE)
    keep = ["seasonId", "team", "franchise", "team_gp", "team_W", "team_OTL", "team_GF", "team_GA",
            "team_SOW", "team_SA_pg", "points", "teamShutouts", "team_xGF", "team_xGA", "team_pp_pg"]
    return t[keep]


def _moneypuck_skaters(year: int) -> pd.DataFrame:
    m = mp.season_summary(year, "skaters")
    base = m[m.situation == "all"][
        ["playerId", "icetime", "games_played", "I_F_xGoals", "I_F_goals", "I_F_shotsOnGoal",
         "I_F_primaryAssists", "I_F_secondaryAssists", "OnIce_F_xGoals", "OnIce_F_goals",
         "I_F_highDangerxGoals"]
    ].rename(columns=lambda c: c if c == "playerId" else f"mp_{c}")
    pp = m[m.situation == "5on4"][["playerId", "icetime", "I_F_xGoals", "I_F_points"]].rename(
        columns={"icetime": "mp_pp_icetime", "I_F_xGoals": "mp_pp_ixG", "I_F_points": "mp_pp_points"}
    )
    ev = m[m.situation == "5on5"][["playerId", "icetime", "I_F_xGoals", "I_F_points", "OnIce_F_xGoals"]].rename(
        columns={"icetime": "mp_ev_icetime", "I_F_xGoals": "mp_ev_ixG", "I_F_points": "mp_ev_points",
                 "OnIce_F_xGoals": "mp_ev_onice_xGF"}
    )
    return base.merge(pp, on="playerId", how="left").merge(ev, on="playerId", how="left")


def build_skaters(games: pd.Series) -> pd.DataFrame:
    frames = []
    for s in nhl.season_ids(FIRST, LAST):
        summ = nhl.report("skater", "summary", s)[
            ["playerId", "skaterFullName", "positionCode", "teamAbbrevs", "gamesPlayed", "goals",
             "assists", "points", "gameWinningGoals", "evGoals", "evPoints", "ppGoals", "ppPoints",
             "shGoals", "shPoints", "shots", "timeOnIcePerGame", "otGoals"]
        ]
        toi = nhl.report("skater", "timeonice", s)[
            ["playerId", "evTimeOnIcePerGame", "ppTimeOnIcePerGame", "shTimeOnIcePerGame"]
        ]
        pp = nhl.report("skater", "powerplay", s)
        pp = pp[["playerId", "ppPrimaryAssists", "ppSecondaryAssists", "ppTimeOnIcePctPerGame", "ppShots"]]
        spg = nhl.report("skater", "scoringpergame", s)[["playerId", "totalPrimaryAssists", "totalSecondaryAssists",
                                                        "hits", "blockedShots"]]
        bios = nhl.report("skater", "bios", s)[["playerId", "birthDate", "draftOverall", "height", "weight"]]
        ht = nhl.hat_trick_games(s)
        ht = ht.groupby("playerId").size().rename("HT").reset_index() if len(ht) else pd.DataFrame(columns=["playerId", "HT"])
        df = (summ.merge(toi, on="playerId", how="left").merge(pp, on="playerId", how="left")
              .merge(spg, on="playerId", how="left").merge(bios, on="playerId", how="left")
              .merge(ht, on="playerId", how="left"))
        df = df.merge(_moneypuck_skaters(s // 10000), on="playerId", how="left")
        if s >= 20122013:
            po = nhl.playoffs("skater", s)
            if len(po):
                po = po[["playerId", "gamesPlayed", "goals", "assists"]].rename(
                    columns={"gamesPlayed": "po_GP", "goals": "po_G", "assists": "po_A"})
                df = df.merge(po, on="playerId", how="left")
        df["seasonId"] = s
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    for c in ("po_GP", "po_G", "po_A"):
        df[c] = df[c].fillna(0.0) if c in df else 0.0

    df = df.rename(columns={"skaterFullName": "name", "gamesPlayed": "GP", "goals": "G", "assists": "A",
                            "points": "PTS", "gameWinningGoals": "GWG", "shots": "SOG",
                            "totalPrimaryAssists": "A1", "totalSecondaryAssists": "A2"})
    df["pos"] = pos_group(df["positionCode"])
    for c in ["HT", "ppPrimaryAssists", "ppSecondaryAssists", "ppTimeOnIcePctPerGame", "ppShots", "A1", "A2"]:
        df[c] = df[c].fillna(0.0)
    df["first_team"] = df["teamAbbrevs"].str.split(",").str[0]
    df["last_team"] = df["teamAbbrevs"].str.split(",").str[-1]
    df["season_games"] = df["seasonId"].map(games)
    df["gp_frac"] = (df["GP"] / df["season_games"]).clip(upper=1.0)
    # Age on Feb 1 of the season (mid-season convention).
    mid = pd.to_datetime((df["seasonId"] % 10000).astype(str) + "-02-01")
    df["age"] = (mid - pd.to_datetime(df["birthDate"])).dt.days / 365.25
    df["toi_pg"] = df["timeOnIcePerGame"] / 60.0  # minutes
    df["pp_toi_pg"] = df["ppTimeOnIcePerGame"] / 60.0
    df["ev_toi_pg"] = df["evTimeOnIcePerGame"] / 60.0
    df["sh_toi_pg"] = df["shTimeOnIcePerGame"] / 60.0
    df["hits_pg"] = df["hits"] / df["GP"]
    df["blocks_pg"] = df["blockedShots"] / df["GP"]
    df["FP"] = fantasy_points(df)
    df["FP82"] = df["FP"] * 82.0 / df["season_games"]
    return df


def build_goalies(games: pd.Series) -> pd.DataFrame:
    frames = []
    for s in nhl.season_ids(FIRST, LAST):
        summ = nhl.report("goalie", "summary", s)[
            ["playerId", "goalieFullName", "teamAbbrevs", "gamesPlayed", "gamesStarted", "wins", "losses",
             "otLosses", "shutouts", "savePct", "shotsAgainst", "goalsAgainst", "timeOnIce"]
        ]
        svr = nhl.report("goalie", "startedVsRelieved", s)[
            ["playerId", "gamesStartedWins", "gamesStartedOtLosses", "gamesRelievedWins", "gamesRelievedOtLosses"]
        ]
        bios = nhl.report("goalie", "bios", s)[["playerId", "birthDate", "draftOverall"]]
        df = summ.merge(svr, on="playerId", how="left").merge(bios, on="playerId", how="left")
        m = mp.season_summary(s // 10000, "goalies")
        m = m[m.situation == "all"][["playerId", "xGoals", "goals", "icetime"]].rename(
            columns={"xGoals": "mp_xGA", "goals": "mp_GA", "icetime": "mp_icetime"})
        df = df.merge(m, on="playerId", how="left")
        df["seasonId"] = s
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    df = df.rename(columns={"goalieFullName": "name", "gamesPlayed": "GP", "gamesStarted": "GS",
                            "wins": "W", "losses": "L", "otLosses": "OTL", "shutouts": "SO"})
    df["pos"] = "G"
    df["first_team"] = df["teamAbbrevs"].str.split(",").str[0]
    df["last_team"] = df["teamAbbrevs"].str.split(",").str[-1]
    df["season_games"] = df["seasonId"].map(games)
    mid = pd.to_datetime((df["seasonId"] % 10000).astype(str) + "-02-01")
    df["age"] = (mid - pd.to_datetime(df["birthDate"])).dt.days / 365.25
    df["gsax"] = df["mp_xGA"] - df["mp_GA"]
    df["FP"] = fantasy_points(df)
    df["FP82"] = df["FP"] * 82.0 / df["season_games"]
    return df


def attach_late(sk: pd.DataFrame, gl: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Join late-season window stats (see late.py) when they have been built."""
    kp, gp = PROCESSED / "skater_late.csv.gz", PROCESSED / "goalie_late.csv.gz"
    if kp.exists():
        k = pd.read_csv(kp)
        sk = sk.drop(columns=[c for c in k.columns if c.startswith("late_")], errors="ignore")
        sk = sk.merge(k, on=["playerId", "seasonId"], how="left")
        sk["late_gp_frac"] = (sk["late_gp"] / sk["late_team_games"]).clip(upper=1)
    if gp.exists():
        g = pd.read_csv(gp)
        gl = gl.drop(columns=[c for c in g.columns if c.startswith("late_")], errors="ignore")
        gl = gl.merge(g, on=["playerId", "seasonId"], how="left")
        gl["late_share"] = gl["late_share"].fillna(0.0)
    return sk, gl


def build() -> dict[str, pd.DataFrame]:
    games = season_games()
    teams = build_teams()
    sk = build_skaters(games)
    gl = build_goalies(games)
    sk, gl = attach_late(sk, gl)
    teams.to_csv(PROCESSED / "teams.csv.gz", index=False)
    sk.to_csv(PROCESSED / "skaters.csv.gz", index=False)
    gl.to_csv(PROCESSED / "goalies.csv.gz", index=False)
    return {"teams": teams, "skaters": sk, "goalies": gl}


def load() -> dict[str, pd.DataFrame]:
    return {k: pd.read_csv(PROCESSED / f"{k}.csv.gz") for k in ("teams", "skaters", "goalies")}


def checks(d: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Reconciliation checks printed by `run.py build`."""
    sk, gl, tm = d["skaters"], d["goalies"], d["teams"]
    rows = []
    for s, g in sk.groupby("seasonId"):
        t = tm[tm.seasonId == s]
        gg = gl[gl.seasonId == s]
        rows.append({
            "season": s,
            "nhl_goals": int(g["G"].sum()),
            "mp_goals": int(g["mp_I_F_goals"].sum()) if g["mp_I_F_goals"].notna().any() else np.nan,
            "team_GF": int(t["team_GF"].sum()),
            "gwg": int(g["GWG"].sum()),
            "wins_minus_SO_wins": int(t["team_W"].sum() - t["team_SOW"].sum()),
            "goalie_W": int(gg["W"].sum()),
            "team_W": int(t["team_W"].sum()),
            "hat_tricks": int(g["HT"].sum()),
            "mp_match_rate": round(g["mp_icetime"].notna().mean(), 3),
        })
    return pd.DataFrame(rows)
