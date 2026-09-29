"""Component-wise tuning on TUNE seasons only (never VALID).

Each component is tuned on its own loss, which is less noisy than tuning
everything on the draft simulation:
  skater rate  : GP-weighted squared error of fantasy points per game (actual GP >= 20)
  skater GP    : squared error of projected GP (per 82) vs actual, 0 if did not play
  goalie       : squared error of projected fantasy points
Losses are computed on a population chosen from preseason information only:
the top 400 skaters and top 50 goalies by their best fantasy-point season over
the prior three years. Selecting on actual season-N output would bias the
games-played fit (everyone in an "actual top 300" played a lot).
"""
import itertools

import numpy as np
import pandas as pd

from . import backtest
from .models import baseline, marcel


def preseason_population(data: dict, season: int, uni: set, n_sk: int = 400, n_g: int = 50) -> pd.Index:
    ids = []
    for key, n in (("skaters", n_sk), ("goalies", n_g)):
        df = data[key]
        h = df[(df.seasonId < season) & (df.seasonId >= season - 30003) & df.playerId.isin(uni)]
        ids += list(h.groupby("playerId")["FP82"].max().nlargest(n).index)
    return pd.Index(sorted(set(ids)))


class Ctx:
    """Caches per-season universe, population and actuals."""

    def __init__(self, data: dict, seasons: list[int]):
        self.data, self.seasons, self.cache = data, seasons, {}
        for s in seasons:
            uni = backtest.universe(data, s)
            b0 = baseline.project(data, s, uni)
            act = backtest.actuals(data, s)
            pop = preseason_population(data, s, uni)
            sk = data["skaters"][data["skaters"].seasonId == s].set_index("playerId")
            gl = data["goalies"][data["goalies"].seasonId == s].set_index("playerId")
            gp82 = pd.concat([sk["GP"] * 82 / sk["season_games"], gl["GS"] * 82 / gl["season_games"]])
            self.cache[s] = {"uni": uni, "pop": pop, "act": act, "gp82": gp82, "pos": b0["pos"]}

    def losses(self, params: dict, per_season: bool = False) -> dict:
        return self.losses_fn(lambda d, s, u: marcel.project(d, s, params, u), per_season)

    def losses_fn(self, fn, per_season: bool = False) -> dict:
        """Component losses for any projection function fn(data, season, universe)."""
        out = {"rate": [], "gp": [], "goalie": [], "fp_sk": []}
        for s in self.seasons:
            c = self.cache[s]
            proj = fn(self.data, s, c["uni"]).reindex(c["pop"])
            pos = c["pos"].reindex(c["pop"])
            act = c["act"].reindex(c["pop"]).fillna(0.0)
            gp = c["gp82"].reindex(c["pop"]).fillna(0.0)
            sk = pos.isin(["F", "D"])
            m = sk & (gp >= 20)
            pr_rate = proj["proj_FP"] / proj["proj_GP"].clip(lower=1)
            ac_rate = act / gp.clip(lower=1)
            out["rate"].append(float(np.average((pr_rate[m] - ac_rate[m]) ** 2, weights=gp[m])))
            out["gp"].append(float(((proj["proj_GP"][sk].fillna(0) - gp[sk]) ** 2).mean()))
            out["fp_sk"].append(float(((proj["proj_FP"][sk].fillna(0) - act[sk]) ** 2).mean()))
            g = pos == "G"
            out["goalie"].append(float(((proj["proj_FP"][g].fillna(0) - act[g]) ** 2).mean()))
        if per_season:
            return out
        return {k: float(np.mean(v)) for k, v in out.items()}


def grid(ctx: Ctx, base: dict, space: dict, loss: str) -> tuple[dict, pd.DataFrame]:
    """Exhaustive search over `space` (name -> list of values), others fixed at base."""
    keys = list(space)
    rows = []
    for combo in itertools.product(*(space[k] for k in keys)):
        p = {**base}
        for k, v in zip(keys, combo):
            if "." in k:
                outer, inner = k.split(".")
                p[outer] = {**p[outer], inner: v}
            else:
                p[k] = v
        l = ctx.losses(p)
        rows.append({**dict(zip(keys, combo)), **l})
    df = pd.DataFrame(rows).sort_values(loss)
    best = df.iloc[0]
    p = {**base}
    for k in keys:
        v = best[k]
        if "." in k:
            outer, inner = k.split(".")
            p[outer] = {**p[outer], inner: v}
        else:
            p[k] = v
    return p, df
