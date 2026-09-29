"""Part A: noise, board-matching simulation, Habs bonus cost, ridge/GBM revisited."""
import numpy as np
import pandas as pd

from nhlpool.experiments import Runner, show
from nhlpool.models import ridge

r = Runner()
L0, N0, S0 = r.reference()
print("Reference per season (naive margin, savvy margin, rank):")
print(pd.DataFrame({"naive": N0.draft_margin, "savvy": S0.draft_margin, "rank_naive": N0.draft_rank}).round(1).to_string())
print("season-to-season sd of naive margin:", round(N0.draft_margin.std(), 1))
rows = []
rows.append(r.compare("A2 dynamic replacement (board logic)", sim_kw={"dynamic": True}))
habs = lambda proj: pd.Series(np.where(proj["team"] == "MTL", 10.0, 0.0), index=proj.index)
rows.append(r.compare("A2 Habs bonus +10", sim_kw={"my_bonus": habs, "dynamic": True}))
P = r.P
rows.append(r.compare("A3 ridge 50% blend", fn=lambda d, s, u: ridge.project(d, s, P, u, blend=0.5)))
rows.append(r.compare("A3 gradient boosting 50% blend", fn=lambda d, s, u: ridge.project(d, s, P, u, blend=0.5, kind="gbm")))
rows.append(r.compare("A3 gradient boosting alone", fn=lambda d, s, u: ridge.project(d, s, P, u, blend=1.0, kind="gbm")))
print(show(rows))
