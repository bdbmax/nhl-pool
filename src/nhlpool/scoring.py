"""League scoring rules. The single source of truth for fantasy points."""
import numpy as np
import pandas as pd

from .config import load_league


def pos_group(position_code: pd.Series) -> pd.Series:
    """NHL position codes C/L/R -> F, D -> D, G -> G."""
    return position_code.map({"C": "F", "L": "F", "R": "F", "D": "D", "G": "G"})


def skater_points(df: pd.DataFrame, rules: dict | None = None) -> pd.Series:
    """df needs columns: pos (F/D), G, A, GWG, HT."""
    rules = rules or load_league()["scoring"]
    out = pd.Series(0.0, index=df.index)
    for grp in ("F", "D"):
        r = rules[grp]
        m = df["pos"] == grp
        out[m] = (
            r["goal"] * df.loc[m, "G"]
            + r["assist"] * df.loc[m, "A"]
            + r["gwg"] * df.loc[m, "GWG"]
            + r["hat_trick"] * df.loc[m, "HT"]
        )
    return out


def goalie_points(df: pd.DataFrame, rules: dict | None = None) -> pd.Series:
    """df needs columns: W, OTL, SO."""
    r = (rules or load_league()["scoring"])["G"]
    return r["win"] * df["W"] + r["otl"] * df["OTL"] + r["shutout"] * df["SO"]


def fantasy_points(df: pd.DataFrame, rules: dict | None = None) -> pd.Series:
    """Works on a mixed frame (pos in F/D/G) with skater and goalie columns."""
    out = pd.Series(np.nan, index=df.index)
    sk = df["pos"].isin(["F", "D"])
    if sk.any():
        out[sk] = skater_points(df[sk], rules)
    g = df["pos"] == "G"
    if g.any():
        out[g] = goalie_points(df[g], rules)
    return out
