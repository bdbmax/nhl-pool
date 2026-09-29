"""Part B: goalie experiments, tuned on TUNE seasons, then compared with standard errors."""
import json

import pandas as pd

from nhlpool import tune
from nhlpool.experiments import Runner, show
from nhlpool.models import marcel

pd.set_option("display.width", 250)
r = Runner()
P = r.P
print("reference goalie loss:", round(r.ctx.losses(P)["goalie"], 1))

p, df = tune.grid(r.ctx, P, {"gs_late_w": [0.0, 0.25, 0.4, 0.5, 0.6, 0.75, 1.0]}, "goalie")
print(df[["gs_late_w", "goalie"]].to_string(index=False))
p4 = {**P, "gs_late_w": p["gs_late_w"]}
p, df = tune.grid(r.ctx, p4, {"gs_K": [0.1, 0.25, 0.5], "gs_mu": [0.4, 0.5, 0.6, 0.7]}, "goalie")
print(df[["gs_K", "gs_mu", "goalie"]].head(3).to_string(index=False))
p4 = p

p, df = tune.grid(r.ctx, {**p4, "so_model": True}, {"so_c": [0.7, 0.85, 1.0, 1.15, 1.3], "sv_K": [1000, 3000, 8000]}, "goalie")
print(df[["so_c", "sv_K", "goalie"]].head(4).to_string(index=False))
p6 = p

p, df = tune.grid(r.ctx, p6, {"w_team_mix": [0.0, 0.25, 0.5, 0.75], "w_gsax": [0.0, 0.1, 0.2]}, "goalie")
print(df[["w_team_mix", "w_gsax", "goalie"]].head(4).to_string(index=False))
p7 = p

rows = [
    r.compare("B4 late-season start share", fn=lambda d, s, u: marcel.project(d, s, p4, u),
              note=f"gs_late_w={p4['gs_late_w']}, gs_K={p4['gs_K']}, gs_mu={p4['gs_mu']}"),
    r.compare("B6 + shutouts from shots and save %", fn=lambda d, s, u: marcel.project(d, s, p6, u),
              note=f"so_c={p6['so_c']}, sv_K={p6['sv_K']}"),
    r.compare("B7 + win rate mixed with team and goalie quality", fn=lambda d, s, u: marcel.project(d, s, p7, u),
              note=f"w_team_mix={p7['w_team_mix']}, w_gsax={p7['w_gsax']}"),
]
print(show(rows))
json.dump({k: (list(v) if isinstance(v, tuple) else v) for k, v in {"p4": p4, "p6": p6, "p7": p7}.items()},
          open("/tmp/partb_params.json", "w"), default=lambda o: list(o) if isinstance(o, tuple) else float(o))
