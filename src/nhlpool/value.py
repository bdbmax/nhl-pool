"""Monte Carlo intervals, replacement level, VORP and risk flags.

The simulation resamples the model's own backtest errors (tuning seasons only):
  skaters: games played = projection + a residual drawn from players with a
           similar GP projection; scoring rate = projection x a ratio drawn
           from players with a similar projected rate.
  goalies: fantasy points = projection x a ratio drawn from goalies with a
           similar projected start count (captures job loss, team swings).
So the 80% intervals are calibrated to how wrong the model actually was, not
to an assumed distribution. Rookies/imports get their log-ratio widened x1.5.
"""
import numpy as np
import pandas as pd

from . import backtest, dataset, params, tune
from .draft import POSITIONS
from .models import marcel
from .paths import PROCESSED

GP_BINS = [-1, 45, 60, 70, 76, 83]
RATE_Q = 4
GS_BINS = [-1, 20, 35, 50, 83]


def residuals(data: dict | None = None, P: dict | None = None, exclude: int | None = None) -> dict:
    """Error tables from the tuning seasons. exclude: leave one season out (for backtests of season `exclude`)."""
    path = PROCESSED / "residuals.pkl"
    if path.exists() and data is None and exclude is None:
        return pd.read_pickle(path)
    data = data or dataset.load()
    P = P or params.load()
    sk_rows, g_rows = [], []
    for s in [x for x in backtest.TUNE if x != exclude]:
        uni = backtest.universe(data, s)
        pop = tune.preseason_population(data, s, uni)
        pr = marcel.project(data, s, P, uni).reindex(pop)
        cur_sk = data["skaters"][data["skaters"].seasonId == s].set_index("playerId")
        cur_g = data["goalies"][data["goalies"].seasonId == s].set_index("playerId")
        act = backtest.actuals(data, s).reindex(pop).fillna(0.0)
        sk = pr["pos"].isin(["F", "D"])
        gp = (cur_sk["GP"] * 82 / cur_sk["season_games"]).reindex(pop).fillna(0.0)
        d = pd.DataFrame({"proj_GP": pr.loc[sk, "proj_GP"], "gp_resid": gp[sk] - pr.loc[sk, "proj_GP"],
                          "proj_rate": pr.loc[sk, "proj_FP"] / pr.loc[sk, "proj_GP"].clip(lower=1),
                          "act_rate": act[sk] / gp[sk].clip(lower=1), "act_gp": gp[sk]})
        sk_rows.append(d)
        g = pr["pos"] == "G"
        g_rows.append(pd.DataFrame({"proj_GS": pr.loc[g, "proj_GS"], "ratio": act[g] / pr.loc[g, "proj_FP"].clip(lower=5)}))
    sk = pd.concat(sk_rows)
    g = pd.concat(g_rows)
    rate_edges = np.quantile(sk["proj_rate"], np.linspace(0, 1, RATE_Q + 1))
    rate_edges[0], rate_edges[-1] = -np.inf, np.inf
    out = {
        "gp": {i: grp["gp_resid"].to_numpy() for i, grp in sk.groupby(pd.cut(sk["proj_GP"], GP_BINS, labels=False))},
        "rate_edges": rate_edges,
        "rate": {i: (grp["act_rate"] / grp["proj_rate"]).to_numpy()
                 for i, grp in sk[sk["act_gp"] >= 20].groupby(pd.cut(sk.loc[sk["act_gp"] >= 20, "proj_rate"], rate_edges, labels=False))},
        "goalie": {i: grp["ratio"].to_numpy() for i, grp in g.groupby(pd.cut(g["proj_GS"], GS_BINS, labels=False))},
    }
    if exclude is None:
        pd.to_pickle(out, path)
    return out


def draws(proj: pd.DataFrame, n: int = 5000, seed: int = 7, res: dict | None = None) -> np.ndarray:
    """Simulated season fantasy points, shape (players, n)."""
    res = res or residuals()
    rng = np.random.default_rng(seed)
    src = proj["source"] if "source" in proj else pd.Series("model", index=proj.index)
    rookie = src.eq("rookie").to_numpy()
    sk = proj["pos"].isin(["F", "D"]).to_numpy()
    gp_proj = proj["proj_GP"].fillna(0).to_numpy()
    fp = proj["proj_FP"].fillna(0).to_numpy()
    gp_bin = np.clip(np.digitize(gp_proj, GP_BINS) - 1, 0, len(GP_BINS) - 2)
    rate = fp / np.clip(gp_proj, 1, None)
    rate_bin = np.clip(np.searchsorted(res["rate_edges"], rate, side="right") - 1, 0, RATE_Q - 1)
    gs_bin = np.clip(np.digitize(gp_proj, GS_BINS) - 1, 0, len(GS_BINS) - 2)
    sims = np.zeros((len(proj), n))
    for i in range(len(proj)):
        if sk[i]:
            gp = np.clip(gp_proj[i] + rng.choice(res["gp"][gp_bin[i]], n), 0, 82)
            ratio = rng.choice(res["rate"][rate_bin[i]], n)
        else:
            ratio = rng.choice(res["goalie"][gs_bin[i]], n)
        if rookie[i]:
            ratio = np.exp(1.5 * np.log(np.clip(ratio, 0.05, None)))
        sims[i] = gp * rate[i] * ratio if sk[i] else fp[i] * ratio
    return sims


def simulate(proj: pd.DataFrame, n: int = 5000, seed: int = 7, res: dict | None = None) -> pd.DataFrame:
    sims = draws(proj, n, seed, res)
    q = np.percentile(sims, [10, 50, 90], axis=1)
    return pd.DataFrame({"p10": q[0], "median": q[1], "p90": q[2], "sim_mean": sims.mean(axis=1)}, index=proj.index)


def replacement(proj: pd.DataFrame, league: dict, col: str = "proj_FP") -> dict:
    """Projection of the first player at each position who would go undrafted."""
    T, slots = league["teams"], league.get("replacement_slots", league["drafted"])
    out = {}
    for p in POSITIONS:
        vals = proj.loc[proj["pos"] == p, col].sort_values(ascending=False)
        n = T * slots[p]
        out[p] = float(vals.iloc[n]) if len(vals) > n else 0.0
    return out


def flags(proj: pd.DataFrame) -> pd.Series:
    f = []
    for _, r in proj.iterrows():
        x = []
        if r.get("source") == "rookie":
            x.append("rookie/import")
        if r["age"] >= 33:
            x.append("age 33+")
        if r.get("history") == "injury-prone":
            x.append("injury-prone")
        if r.get("df_ir") is True:
            x.append("IR at camp")
        if r.get("off_roster") is True:
            x.append("off roster: unsigned or long-term injured, check")
        if r["pos"] == "G":
            ss = r.get("start_share", np.nan)
            if ss < 0.35:
                x.append("backup")
            elif ss < 0.55:
                x.append("tandem")
        else:
            if r.get("df_pp") == "pp1":
                x.append("PP1")
            if pd.isna(r.get("df_line")) and r.get("df_ir") is not True:
                x.append("not in DF lineup")
        if isinstance(r.get("last_team"), str) and r["last_team"] != r["team"] and r.get("source") != "rookie":
            x.append("new team")
        if r["proj_FP"] > 20 and (r["p90"] - r["p10"]) / max(r["proj_FP"], 1) > 0.9:
            x.append("volatile")
        f.append(", ".join(x))
    return pd.Series(f, index=proj.index)
