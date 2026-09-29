"""Part E: pick strategy with the final projections, tuning seasons only.

Late-round upside uses simulated seasons whose error tables leave the scored
season out, so nothing about season N's outcomes leaks into its own draft.
"""
import numpy as np
import pandas as pd

from nhlpool import value
from nhlpool.experiments import Runner

pd.set_option("display.width", 250)
r = Runner()
_res = {}


def p75(proj, season):
    if season not in _res:
        _res[season] = value.residuals(r.data, r.P, exclude=season)
    src = proj.assign(source="model")
    sims = value.draws(src, n=600, seed=season % 997, res=_res[season])
    return pd.Series(np.percentile(sims, 75, axis=1), index=proj.index)


strategies = {"E19 upside (75th percentile) after round 10": {"my_late": p75, "late_round": 10, "dynamic": True},
              "E19 upside after round 12": {"my_late": p75, "late_round": 12, "dynamic": True}}
for x in (4, 6, 8, 10):
    strategies[f"E20 first goalie no earlier than round {x}"] = {"goalie_rule": {"first_round": x}}
strategies["E20 second goalie only in the last 2 rounds"] = {"goalie_rule": {"second_last": 2}}
strategies["E20 first goalie round 8+, second in last 2"] = {"goalie_rule": {"first_round": 8, "second_last": 2}}

rows = []
f = lambda x, k: f"{x[k]:+.1f} ± {x[k + '_se']:.1f}"
for name, kw in strategies.items():
    a = r.compare(name, sim_kw=kw)
    b = r.robust(name, r.ref, sim_kw=kw)
    rows.append({"strategy": name, "naive": f(a, "d_margin_naive"), "savvy": f(a, "d_margin_savvy"),
                 "untuned": f(b, "d_margin_untuned"), "noisy": f(b, "d_margin_noisy")})
    print(rows[-1], flush=True)
print(pd.DataFrame(rows).to_string(index=False))
