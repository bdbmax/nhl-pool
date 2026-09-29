"""Challenger for goalie start share: a small ridge regression.

Target: share of the 82 games a goalie starts in season t. Features describe
season t-1 and earlier, plus the competition on his opening-night team in t
(the prior-season shares of the other goalies there), which is known before
the season. Trained on every target season before the one projected.
"""
import numpy as np
import pandas as pd
from sklearn.linear_model import RidgeCV
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from ..history import age_in, latest, opening_team, prev, wide_history

COLS = ["GS", "season_games", "late_share", "gsax", "shotsAgainst"]
FIRST_TARGET = 20142015
_cache: dict = {}


def features(gl: pd.DataFrame, season: int, ids=None) -> pd.DataFrame:
    H = wide_history(gl, season, COLS)
    H = H.join(latest(gl, season, ["birthDate"]))
    if ids is not None:
        H = H[H.index.isin(ids)]
    X = pd.DataFrame(index=H.index)
    for k in (1, 2, 3):
        X[f"f{k}"] = (H[f"GS_{k}"] / H[f"season_games_{k}"]).fillna(0).clip(upper=1)
    X["late"] = H["late_share_1"].fillna(X["f1"])
    X["gsax_ps"] = (H[["gsax_1", "gsax_2"]].fillna(0).sum(axis=1)) / (H[["GS_1", "GS_2"]].fillna(0).sum(axis=1) + 30)
    X["age"] = age_in(season, H["birthDate"])
    X["old"] = np.maximum(0, X["age"] - 33)
    X["young"] = np.maximum(0, 26 - X["age"])
    X["new_team"] = 0.0
    team = opening_team(gl, season).reindex(X.index)
    lastt = gl[gl.seasonId == prev(season)].set_index("playerId")["last_team"].reindex(X.index)
    X["new_team"] = (team != lastt).astype(float)
    f1 = X["f1"]
    tot = f1.groupby(team).transform("sum")
    best_other = pd.Series([f1[(team == team[i]) & (f1.index != i)].max() if team[i] == team[i] else 0.0
                            for i in X.index], index=X.index).fillna(0)
    X["comp_sum"] = (tot - f1).fillna(0)
    X["comp_best"] = best_other
    X["f1_x_comp"] = X["f1"] * X["comp_best"]
    return X.fillna(0), team


def fit(gl: pd.DataFrame, season: int, alive: dict):
    key = (season, len(gl))
    if key in _cache:
        return _cache[key]
    rows = []
    t = FIRST_TARGET
    while t < season:
        X, _ = features(gl, t, alive.get(t))
        cur = gl[gl.seasonId == t].set_index("playerId")
        y = (cur["GS"] / cur["season_games"]).reindex(X.index).fillna(0).clip(upper=1)
        rows.append(X.assign(y=y))
        t += 10001
    tr = pd.concat(rows)
    m = make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-2, 3, 12)))
    m.fit(tr.drop(columns="y"), tr["y"])
    _cache[key] = m
    return m


def predict(data: dict, season: int, universe: set) -> pd.Series:
    from .. import backtest
    gl = data["goalies"]
    alive = {}
    t = FIRST_TARGET
    while t < season:
        alive[t] = backtest.universe(data, t)
        t += 10001
    m = fit(gl, season, alive)
    X, _ = features(gl, season, universe)
    return pd.Series(np.clip(m.predict(X), 0, 0.9), index=X.index)
