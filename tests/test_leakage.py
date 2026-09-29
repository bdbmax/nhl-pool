"""Projections for season N must not change when season N and later stats are wiped.

Only the opening team (first team in N) is allowed through, since it is known
on opening night and is used for team context only.
"""
import numpy as np
import pandas as pd
import pytest

from nhlpool import backtest, dataset, params
from nhlpool.models import marcel

KEEP = {"playerId", "seasonId", "first_team", "last_team", "name", "pos", "birthDate", "season_games"}
ROUND4_ON = {"env_adj": 1.0, "xg_team_w": 0.5, "sh_model": "career", "xg_weight": 0.0, "gp_inj": 0.03,
             "pp_team_r": 0.5}


def _wipe(data: dict, season: int) -> dict:
    wiped = {}
    for k in ("skaters", "goalies", "teams"):
        df = data[k].copy()
        future = df.seasonId >= season
        for c in df.columns:
            if c not in KEEP and pd.api.types.is_numeric_dtype(df[c]):
                df.loc[future, c] = np.nan
        wiped[k] = df
    return wiped


@pytest.mark.parametrize("season,extra", [(20132014, {}), (20212022, {}), (20242025, {}),
                                          (20152016, ROUND4_ON), (20242025, ROUND4_ON)])
def test_no_future_stats(season, extra):
    data = dataset.load()
    P = {**params.load(), **extra}
    uni = backtest.universe(data, season)
    full = marcel.project(data, season, P, uni)
    cut = marcel.project(_wipe(data, season), season, P, uni)
    pd.testing.assert_series_equal(full["proj_FP"], cut["proj_FP"], check_exact=False, rtol=1e-9)
