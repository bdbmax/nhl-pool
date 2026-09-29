"""Teammate quality.

team_context (backtestable): talent of a player's opening-night teammates vs his
teammates last season. Talent = last season's points per game (20+ GP), top 12
skaters on the team excluding the player. Everything is known before season N.

line_context (NOT backtestable, upper bound only): talent of the linemates a
player actually skated with at 5v5 in season N (MoneyPuck lines), which is only
known after the fact. Used to measure how much linemates could matter at most.
"""
import numpy as np
import pandas as pd

from .fetch import moneypuck as mp
from .history import prev

TOP = 12


def _rates(sk: pd.DataFrame, season: int) -> pd.Series:
    last = sk[(sk.seasonId == prev(season)) & (sk.GP >= 20)].set_index("playerId")
    return (last["G"] + last["A"]) / last["GP"]


def _quality(members: pd.Series, rate: pd.Series) -> pd.Series:
    """members: playerId -> team. Mean rate of the top-12 teammates, excluding the player."""
    df = pd.DataFrame({"team": members, "rate": rate.reindex(members.index)}).dropna()
    out = {}
    for team, g in df.groupby("team"):
        r = g["rate"].sort_values(ascending=False)
        top = r.head(TOP + 1)
        for pid in members[members == team].index:
            rr = top.drop(pid, errors="ignore").head(TOP)
            out[pid] = rr.mean() if len(rr) else np.nan
    return pd.Series(out)


def team_context(sk: pd.DataFrame, season: int, opening: pd.Series) -> pd.Series:
    rate = _rates(sk, season)
    new = _quality(opening.dropna(), rate)
    last = sk[sk.seasonId == prev(season)].set_index("playerId")["last_team"]
    old = _quality(last, rate)
    return (new / old).reindex(opening.index)


def _line_quality(year: int, rate: pd.Series) -> pd.Series:
    L = mp.lines(year)
    L = L[(L.situation == "5on5") & L.position.isin(["line", "pairing"])]
    num, den = {}, {}
    for lid, ice in zip(L.lineId.astype(str), L.icetime):
        ids = [int(lid[i:i + 7]) for i in range(0, len(lid), 7)]
        for pid in ids:
            mates = [rate.get(m) for m in ids if m != pid and m in rate.index]
            if mates:
                num[pid] = num.get(pid, 0.0) + ice * float(np.mean(mates))
                den[pid] = den.get(pid, 0.0) + ice
    return pd.Series({k: num[k] / den[k] for k in num})


def line_context(sk: pd.DataFrame, season: int) -> pd.Series:
    """LEAKY upper bound: linemates in season N vs season N-1, both rated by N-1 points per game."""
    rate = _rates(sk, season)
    y = season // 10000
    return _line_quality(y, rate) / _line_quality(y - 1, rate)
