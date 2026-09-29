"""Parts C and D: skater scoring and games-played switches, greedy, tuning seasons only."""
import json

import pandas as pd

from nhlpool import tune
from nhlpool.experiments import Runner, show
from nhlpool.models import marcel

pd.set_option("display.width", 250)
r = Runner()
P = dict(r.P)
log = []


def step(label, space, loss="rate", base=None, extra=None):
    """Grid-search a switch; keep it only if it lowers the target loss."""
    global P
    base = base or P
    b0 = r.ctx.losses(base)[loss]
    p, df = tune.grid(r.ctx, {**base, **(extra or {})}, space, loss)
    best = df.iloc[0]
    kept = best[loss] < b0 - 1e-9
    log.append({"step": label, "loss": loss, "before": b0, "after": float(best[loss]), "kept": bool(kept),
                "setting": {k: best[k] for k in space}})
    print(f"{label:48s} {loss} {b0:.5f} -> {best[loss]:.5f}  {'KEEP' if kept else 'drop'}  {dict((k, best[k]) for k in space)}")
    if kept:
        P = p
    return kept


step("C10 EV/PP split per minute", {"K_ev": [300, 600, 1200, 2400], "K_pp": [50, 150, 400]}, extra={"evpp": True})
if P.get("evpp"):
    step("C9 late-season minutes in the split", {"min_late_w": [0.0, 0.2, 0.4, 0.6], "min_w1": [1.0, 0.85, 0.7]})
step("C11 age-dependent season weights", {"w_young": [None, (3, 1, 0), (2, 1, 0), (3, 1, 1), (4, 1, 0)], "young_age": [24, 25, 26]})
step("C12 defense age curve", {"age_D": [None] + [{"age_peak": pk, "age_young": y, "age_old": o}
                                                  for pk in (26, 27, 28, 29) for y in (0.03, 0.06, 0.09) for o in (0.0, 0.02, 0.04)]})
step("C13 prior by ice time", {"prior_toi": [True], "K.G": [10, 20, 40], "K.A": [10, 20, 40]})
step("C14 draft pedigree growth", {"dp_growth": [0.02, 0.05, 0.1, 0.15]})
step("C15 playoff games as evidence", {"po_weight": [0.25, 0.5, 0.75, 1.0]})
step("C16 bottom-up team goals for GWG", {"gf_bottom_up": [True]})
step("D17 end-of-season absences", {"gp_late": [0.05, 0.1, 0.2, 0.3, 0.5]}, loss="gp")
step("D18 hits and body size", {"gp_hits": [-0.02, 0.0, 0.02], "gp_size": [-0.02, 0.0, 0.02]}, loss="gp")

kept = [x["step"] for x in log if x["kept"]]
print("kept:", kept)
rows = [r.compare("C+D kept skater and games-played switches", fn=lambda d, s, u: marcel.project(d, s, P, u),
                  note="; ".join(f"{x['step']}: {x['setting']}" for x in log if x["kept"]))]
print(show(rows))
pd.DataFrame(log).to_csv("output/experiments_cd_steps.csv", index=False)
json.dump({k: (list(v) if isinstance(v, tuple) else v) for k, v in P.items()}, open("/tmp/partcd_params.json", "w"),
          default=lambda o: list(o) if isinstance(o, tuple) else (o.item() if hasattr(o, "item") else str(o)))
