"""Tune the Marcel (B1) parameters on TUNE seasons only. Writes config/params_b1.json."""
import json

import pandas as pd

from nhlpool import backtest, dataset, tune
from nhlpool.models import marcel
from nhlpool.paths import CONFIG

pd.set_option("display.width", 250)


def show(df, keys, loss, n=3):
    print(df[keys + [loss]].head(n).to_string(index=False))


def main():
    data = dataset.load()
    ctx = tune.Ctx(data, backtest.TUNE)
    p = dict(marcel.DEFAULT)
    print("start", ctx.losses(p))

    # Skater per-game rates: coordinate descent, two passes.
    for _ in range(2):
        p, df = tune.grid(ctx, p, {"w": [(1, 0, 0), (2, 1, 0), (3, 2, 1), (2, 1, 1), (3, 2, 2), (5, 3, 2), (1, 1, 1)]}, "rate"); show(df, ["w"], "rate")
        p, df = tune.grid(ctx, p, {"K.G": [0, 5, 10, 20, 40, 80], "K.A": [0, 5, 10, 20, 40, 80]}, "rate"); show(df, ["K.G", "K.A"], "rate")
        p, df = tune.grid(ctx, p, {"K.GWG": [80, 160, 320, 640, 1280, 5000]}, "rate"); show(df, ["K.GWG"], "rate")
        p, df = tune.grid(ctx, p, {"age_peak": [25, 26, 27, 28, 29], "age_young": [0.0, 0.03, 0.06, 0.09, 0.12],
                                   "age_old": [0.0, 0.01, 0.02, 0.03, 0.045]}, "rate"); show(df, ["age_peak", "age_young", "age_old"], "rate")
    # Games played.
    for _ in range(2):
        p, df = tune.grid(ctx, p, {"gp_w": [(1, 0, 0), (3, 1, 0), (5, 2, 1), (3, 2, 1), (5, 3, 2)], "gp_K": [0.25, 0.5, 1, 2, 3]}, "gp"); show(df, ["gp_w", "gp_K"], "gp")
        p, df = tune.grid(ctx, p, {"gp_mu.F": [0.6, 0.7, 0.8, 0.9], "gp_mu.D": [0.6, 0.7, 0.8, 0.9], "gp_age": [0.0, 0.005, 0.01, 0.02]}, "gp"); show(df, ["gp_mu.F", "gp_mu.D", "gp_age"], "gp")
        p, df = tune.grid(ctx, p, {"gp_rate": [0.0, 0.1, 0.2, 0.3, 0.45, 0.6]}, "gp"); show(df, ["gp_rate"], "gp")
    # Goalies.
    for _ in range(2):
        p, df = tune.grid(ctx, p, {"g_w": [(1, 0, 0), (2, 1, 0), (3, 2, 1), (5, 3, 2)], "gs_K": [0.1, 0.25, 0.5, 1], "gs_mu": [0.3, 0.4, 0.5, 0.6, 0.7]}, "goalie"); show(df, ["g_w", "gs_K", "gs_mu"], "goalie")
        p, df = tune.grid(ctx, p, {"g_K.W": [5, 10, 20, 40, 80], "g_K.SO": [20, 40, 80, 160]}, "goalie"); show(df, ["g_K.W", "g_K.SO"], "goalie")
        p, df = tune.grid(ctx, p, {"g_team_norm": [False, True], "g_age": [0.0, 0.02, 0.04, 0.06, 0.08]}, "goalie"); show(df, ["g_team_norm", "g_age"], "goalie")
    print("final", ctx.losses(p))
    out = {k: (list(v) if isinstance(v, tuple) else v) for k, v in p.items()}
    (CONFIG / "params_b1.json").write_text(json.dumps(out, indent=2, default=float))


if __name__ == "__main__":
    main()
