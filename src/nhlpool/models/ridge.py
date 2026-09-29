"""Challenger: ridge regression for next-season fantasy points per game.

Features come from seasons before the target only. For target season N the
model trains on every (features before t, outcome in t) pair with t < N, so
there is no leakage. Games played comes from the Marcel GP model; the ridge
replaces only the per-game scoring rate. Fitted separately for F and D,
weighted by the target season's games played.
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import RidgeCV
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from ..history import age_in, latest, prev, wide_history
from . import marcel

COLS = ["GP", "G", "A", "A1", "GWG", "HT", "FP", "SOG", "mp_I_F_xGoals", "toi_pg", "pp_toi_pg",
        "ppTimeOnIcePctPerGame", "season_games"]
FIRST_TRAIN_TARGET = 20132014
_cache: dict = {}


def features(sk: pd.DataFrame, season: int) -> pd.DataFrame:
    key = ("f", season, len(sk))
    if key in _cache:
        return _cache[key]
    H = wide_history(sk, season, COLS)
    H = H.join(latest(sk, season, ["pos", "birthDate"]))
    X = pd.DataFrame(index=H.index)
    w = (3.0, 2.0, 1.0)
    gp = [H[f"GP_{k}"].fillna(0) for k in (1, 2, 3)]
    den = sum(wk * g for wk, g in zip(w, gp)) + 10.0
    for c in ["G", "A", "A1", "FP", "SOG", "mp_I_F_xGoals", "GWG"]:
        num = sum(wk * H[f"{c}_{k}"].fillna(0) for k, wk in zip((1, 2, 3), w))
        X[f"w_{c}"] = num / den
    for k in (1, 2):
        X[f"fp_rate_{k}"] = (H[f"FP_{k}"] / H[f"GP_{k}"].clip(lower=1)).fillna(X["w_FP"])
        X[f"gpf_{k}"] = (H[f"GP_{k}"] / H[f"season_games_{k}"]).fillna(0).clip(upper=1)
    for c in ["toi_pg", "pp_toi_pg", "ppTimeOnIcePctPerGame"]:
        X[c] = H[f"{c}_1"].fillna(H[f"{c}_2"]).fillna(0)
    X["gp_total"] = sum(gp)
    X["age"] = age_in(season, H["birthDate"])
    X["age2"] = (X["age"] - 27) ** 2
    X["young"] = np.maximum(0, 24 - X["age"])
    X["pos"] = H["pos"]
    X = X.dropna(subset=["age"])
    _cache[key] = X
    return X


def training(sk: pd.DataFrame, season: int) -> pd.DataFrame:
    rows = []
    t = FIRST_TRAIN_TARGET
    while t < season:
        X = features(sk, t)
        cur = sk[sk.seasonId == t].set_index("playerId")
        y = (cur["FP"] / cur["GP"]).reindex(X.index)
        wgt = cur["GP"].reindex(X.index)
        d = X.assign(y=y, wgt=wgt).dropna(subset=["y"])
        rows.append(d[d.wgt >= 20])
        t = t + 10001
    return pd.concat(rows)


def fit(sk: pd.DataFrame, season: int, kind: str = "ridge") -> dict:
    key = ("m", season, len(sk), kind)
    if key in _cache:
        return _cache[key]
    tr = training(sk, season)
    models = {}
    for pos in ("F", "D"):
        d = tr[tr.pos == pos]
        Xc = d.drop(columns=["pos", "y", "wgt"])
        if kind == "gbm":
            m = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.05, max_leaf_nodes=15,
                                              min_samples_leaf=40, l2_regularization=1.0, random_state=0)
            m.fit(Xc, d["y"], sample_weight=d["wgt"])
        else:
            m = make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-2, 3, 12)))
            m.fit(Xc, d["y"], ridgecv__sample_weight=d["wgt"])
        models[pos] = (m, list(Xc.columns))
    _cache[key] = models
    return models


def project(data: dict, season: int, params: dict, universe: set | None = None, blend: float = 1.0,
            kind: str = "ridge") -> pd.DataFrame:
    """Marcel projection with the skater FP rate replaced (or blended) by the ridge rate."""
    base = marcel.project(data, season, params, universe)
    sk = data["skaters"]
    models = fit(sk, season, kind)
    X = features(sk, season)
    out = base.copy()
    for pos in ("F", "D"):
        m, cols = models[pos]
        ids = out.index[(out["pos"] == pos) & out.index.isin(X.index)]
        rate = pd.Series(m.predict(X.loc[ids, cols]), index=ids).clip(lower=0)
        b_rate = out.loc[ids, "proj_FP"] / out.loc[ids, "proj_GP"].clip(lower=1)
        new = blend * rate + (1 - blend) * b_rate
        out.loc[ids, "proj_FP"] = new * out.loc[ids, "proj_GP"]
    return out
