"""Phase 4: compare challengers to tuned B1 on TUNE seasons (never VALID).

Usage: uv run python scripts/challengers.py
"""
import numpy as np
import pandas as pd

from nhlpool import backtest, dataset, params, tune
from nhlpool.models import baseline, marcel, ridge

pd.set_option("display.width", 250)


def rate_loss(fn, data, ctx):
    out = []
    for s in ctx.seasons:
        c = ctx.cache[s]
        proj = fn(data, s, c["uni"]).reindex(c["pop"])
        pos, act, gp = c["pos"].reindex(c["pop"]), c["act"].reindex(c["pop"]).fillna(0), c["gp82"].reindex(c["pop"]).fillna(0)
        m = pos.isin(["F", "D"]) & (gp >= 20)
        pr = proj["proj_FP"] / proj["proj_GP"].clip(lower=1)
        out.append(float(np.average((pr[m] - act[m] / gp[m]) ** 2, weights=gp[m])))
    return float(np.mean(out))


def main():
    data = dataset.load()
    P = params.load()
    Pxa = {**P, "xg_weight": 0.25, "a1_weight": 1.2}
    models = {
        "B0_last_season": lambda d, s, u: baseline.project(d, s, u),
        "B1_tuned": lambda d, s, u: marcel.project(d, s, P, u),
        "B1_xg_a1": lambda d, s, u: marcel.project(d, s, Pxa, u),
        "ridge": lambda d, s, u: ridge.project(d, s, P, u, blend=1.0),
        "ridge50_B1": lambda d, s, u: ridge.project(d, s, P, u, blend=0.5),
        "ridge50_B1xa": lambda d, s, u: ridge.project(d, s, Pxa, u, blend=0.5),
    }
    ctx = tune.Ctx(data, backtest.TUNE)
    print("skater rate loss (lower is better):")
    for k, f in models.items():
        if k != "B0_last_season":
            print(f"  {k:14s} {rate_loss(f, data, ctx):.5f}")
    naive = backtest.run(models, data, backtest.TUNE)
    print("\nvs naive opponents:\n", backtest.summarize(naive).to_string())
    savvy = backtest.run({k: v for k, v in models.items() if k != "B0_last_season"}, data, backtest.TUNE,
                         opp_model=models["B1_tuned"], opp_vorp=True)
    print("\nvs savvy opponents (all draft with tuned B1 VORP):\n", backtest.summarize(savvy)[["draft_margin", "draft_rank"]].to_string())


if __name__ == "__main__":
    main()
