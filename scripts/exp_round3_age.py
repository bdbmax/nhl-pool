"""Round 3: aging. Flexible age curve, veteran depth decline, young mid-tier breakouts. Tuning seasons only."""
import json

import numpy as np
import pandas as pd

from nhlpool import tune
from nhlpool.experiments import Runner
from nhlpool.models import marcel

r = Runner()
P = dict(r.P)
base = r.ctx.losses(P)["rate"]
print("reference rate loss (with EV/PP split):", round(base, 5))
cur = {"s1": 0.06, "s2": 0.06, "s3": 0.06 * 2 / 5, "s4": 0.03, "s5": 0.03}  # roughly today's straight line
grids = {"s1": [0.0, 0.04, 0.08, 0.12, 0.16], "s2": [0.0, 0.02, 0.04, 0.06, 0.08], "s3": [-0.02, -0.01, 0.0, 0.01, 0.02],
         "s4": [0.0, 0.01, 0.02, 0.04], "s5": [0.02, 0.03, 0.05, 0.07, 0.09]}
best = dict(cur); best_loss = r.ctx.losses({**P, "age_slopes": best})["rate"]
print("straight line as slopes:", round(best_loss, 5))
for _ in range(2):
    for k, vals in grids.items():
        for v in vals:
            trial = {**best, k: v}
            l = r.ctx.losses({**P, "age_slopes": trial})["rate"]
            if l < best_loss - 1e-9:
                best, best_loss = trial, l
        print("after", k, {kk: round(vv, 3) for kk, vv in best.items()}, round(best_loss, 5), flush=True)
Pa = {**P, "age_slopes": best}
p, df = tune.grid(r.ctx, Pa, {"old_depth": [0.0, 0.01, 0.02, 0.03, 0.05]}, "rate"); print(df[["old_depth", "rate"]].head(3).to_string(index=False))
Pb = p
p, df = tune.grid(r.ctx, Pb, {"young_mid": [0.0, 0.03, 0.06, 0.1, 0.15]}, "rate"); print(df[["young_mid", "rate"]].head(3).to_string(index=False))
Pc = p
json.dump({"age_slopes": best, "old_depth": float(Pc["old_depth"]), "young_mid": float(Pc["young_mid"])}, open("/tmp/r3_age.json", "w"))
