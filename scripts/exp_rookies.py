"""Item 22: backtest the rookie translation on historical first NHL seasons (rate per game only).

For debut season s, factors are fitted only on debuts before s. Games played is
not evaluated here: live it comes from the Daily Faceoff lineup, which has no archive.
"""
import numpy as np
import pandas as pd

from nhlpool import backtest, dataset, params
from nhlpool.models import marcel, rookies

data = dataset.load(); P = params.load()
sk = data["skaters"]
first_any = sk.groupby("playerId").seasonId.min()
rows = []
for s in backtest.TUNE:
    ids = first_any[first_any == s].index
    cur = sk[(sk.seasonId == s) & sk.playerId.isin(ids)].set_index("playerId")
    new = pd.DataFrame({"name": cur["name"], "pos_group": cur["pos"], "team": cur["first_team"], "birthDate": cur["birthDate"]})
    strength = marcel.team_strength(data["teams"], s, P["team_regress"])
    fac = rookies.fit_factors(data, before=s)
    for K in (10, 20, 40):
        for pr in (0.6, 0.8, 1.0, 1.2):
            out = rookies.project(new, data, P, strength, pd.DataFrame(columns=["df_line"]), season=s, K=K, prior=pr, factors=fac)
            out = out[out["pos"] != "G"].join(cur[["GP", "G", "A"]])
            out = out[out.GP >= 20]
            rows.append({"season": s, "K": K, "prior": pr, "n": len(out),
                         "pred_pts": float(((out.rate_G + out.rate_A) * out.GP).sum()), "act_pts": float((out.G + out.A).sum()),
                         "mse": float(np.average(((out.rate_G + out.rate_A) - (out.G + out.A) / out.GP) ** 2, weights=out.GP)),
                         "corr": float(np.corrcoef(out.rate_G + out.rate_A, (out.G + out.A) / out.GP)[0, 1])})
df = pd.DataFrame(rows)
g = df.groupby(["K", "prior"]).agg(n=("n", "sum"), pred=("pred_pts", "sum"), act=("act_pts", "sum"), mse=("mse", "mean"), corr=("corr", "mean"))
g["actual_over_predicted"] = g.act / g.pred
print(g.round(4).sort_values("mse").to_string())
