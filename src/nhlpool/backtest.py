"""Backtest harness.

For each target season N, a model sees only seasons < N (see history.py).
Metrics, all against actual fantasy points under league rules (per-82 in
shortened seasons):
  * Spearman rank correlation and MAE on a fixed evaluation population per
    season: the top 300 skaters and top 40 goalies by actual points, plus the
    same counts by prior-season points. The population does not depend on the
    model being scored, so models are compared on identical players.
  * Snake-draft simulation: my team drafts by the model's VORP, the other
    teams draft by last season's points (naive). Teams draft 8F/6D/2G and are
    scored best-ball (best 6F, 4D, 1G actual totals). Averaged over all slots.
"""
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from .config import load_league
from .draft import simulate
from .history import active_next, prev
from .models import baseline

TUNE = [20182019, 20192020, 20212022, 20222023, 20232024]
VALID = [20242025, 20252026]
# Never used to choose anything before round 4 (each needs three prior seasons, data starts 2010-11).
FRESH = [20132014, 20142015, 20152016, 20162017, 20172018]


def actuals(data: dict, season: int) -> pd.Series:
    parts = [data[k].loc[data[k].seasonId == season].set_index("playerId")["FP82"] for k in ("skaters", "goalies")]
    return pd.concat(parts)


def universe(data: dict, season: int) -> set:
    hist = set()
    for k in ("skaters", "goalies"):
        df = data[k]
        hist |= set(df.loc[df.seasonId.isin([prev(season, i) for i in (1, 2, 3)]), "playerId"])
    return hist & active_next(data["skaters"], data["goalies"], season)


def population(b0: pd.DataFrame, act: pd.Series, n_sk: int = 300, n_g: int = 40) -> pd.Index:
    ids = set()
    for pos, n in (("F", None), ("D", None), ("G", n_g)):
        pass
    sk = b0[b0.pos.isin(["F", "D"])]
    g = b0[b0.pos == "G"]
    a = act.reindex(b0.index).fillna(0.0)
    ids |= set(a[sk.index].nlargest(n_sk).index) | set(sk["proj_FP"].nlargest(n_sk).index)
    ids |= set(a[g.index].nlargest(n_g).index) | set(g["proj_FP"].nlargest(n_g).index)
    return pd.Index(sorted(ids))


def goalie_overlap(proj: pd.DataFrame, act: pd.Series, uni_pos: pd.Series, n: int = 13) -> float:
    """Share of the actual top-n goalies that the model also had in its top n."""
    g = uni_pos.index[uni_pos == "G"]
    top_model = set(proj["proj_FP"].reindex(g).fillna(0).nlargest(n).index)
    top_act = set(act.reindex(g).fillna(0).nlargest(n).index)
    return len(top_model & top_act) / n


def evaluate(proj: pd.DataFrame, data: dict, season: int, league: dict,
             opp: pd.DataFrame | None = None, opp_vorp: bool = False, b0: pd.DataFrame | None = None,
             best_ball_draws: pd.DataFrame | None = None, my_repl: dict | None = None, **sim_kw) -> dict:
    act = actuals(data, season)
    uni = universe(data, season)
    b0 = b0 if b0 is not None else baseline.project(data, season, uni)
    pop = population(b0, act)
    pr = proj["proj_FP"].reindex(pop).fillna(0.0)
    ac = act.reindex(pop).fillna(0.0)
    pos = b0["pos"].reindex(pop)
    res = {"season": season}
    for name, m in (("F", pos == "F"), ("D", pos == "D"), ("G", pos == "G"), ("sk", pos.isin(["F", "D"]))):
        res[f"rho_{name}"] = spearmanr(pr[m], ac[m]).statistic
        res[f"mae_{name}"] = float(np.abs(pr[m] - ac[m]).mean())
    res["g_top13"] = goalie_overlap(proj, act, b0["pos"])
    opp = b0 if opp is None else opp
    all_pos = pd.concat([b0["pos"], proj["pos"]])
    all_pos = all_pos[~all_pos.index.duplicated()]
    seeds = sim_kw.pop("seeds", [0])
    sims = [simulate(proj["proj_FP"], opp["proj_FP"], all_pos, act, league["teams"], league["drafted"],
                     my_pick=k, my_vorp=True, opp_vorp=opp_vorp, counted=league["counted"],
                     my_draws=best_ball_draws, my_repl=my_repl, seed=sd, **sim_kw)
            for k in range(1, league["teams"] + 1) for sd in seeds]
    for key in ("margin", "rank", "margin_F", "margin_D", "margin_G"):
        res["draft_" + key] = float(np.mean([s[key] for s in sims]))
    return res


def run(models: dict, data: dict, seasons: list[int], league: dict | None = None,
        opp_model=None, opp_vorp: bool = False, best_ball: set | None = None,
        repl: dict | None = None, sim_kw: dict | None = None) -> pd.DataFrame:
    """models: name -> callable(data, season, universe) -> projection frame.
    Models named in best_ball draft with the best-ball-aware strategy."""
    from .value import draws
    league = league or load_league()
    rows = []
    for s in seasons:
        uni = universe(data, s)
        b0 = baseline.project(data, s, uni)
        opp = opp_model(data, s, uni) if opp_model else None
        for name, fn in models.items():
            proj = fn(data, s, uni)
            bb = None
            if best_ball and name in best_ball:
                top = proj.sort_values("proj_FP", ascending=False).groupby("pos").head(150)
                bb = pd.DataFrame(draws(top, n=300, seed=s % 997), index=top.index)
            kw = dict((sim_kw or {}).get(name, {}))
            if callable(kw.get("my_bonus")):
                kw["my_bonus"] = kw["my_bonus"](proj)
            if callable(kw.get("my_late")):
                kw["my_late"] = kw["my_late"](proj, s)
            r = evaluate(proj, data, s, league, opp=opp, opp_vorp=opp_vorp, b0=b0, best_ball_draws=bb,
                         my_repl=(repl or {}).get(name), **kw)
            r["model"] = name
            rows.append(r)
    return pd.DataFrame(rows)


def summarize(res: pd.DataFrame) -> pd.DataFrame:
    cols = ["rho_F", "rho_D", "rho_G", "rho_sk", "mae_F", "mae_D", "mae_G", "g_top13", "draft_margin", "draft_rank"]
    return res.groupby("model")[cols].mean().round(3)


def paired(res: pd.DataFrame, ref: str, metrics: list[str] | None = None) -> pd.DataFrame:
    """Mean per-season difference vs the reference model, with its standard error.

    Positive is better for rank correlation, overlap and draft margin; negative
    is better for errors and draft rank. n = number of seasons.
    """
    metrics = metrics or ["rho_F", "rho_D", "rho_G", "mae_F", "mae_D", "mae_G", "g_top13",
                          "draft_margin", "draft_margin_G", "draft_rank"]
    base = res[res.model == ref].set_index("season")
    rows = []
    for name, g in res.groupby("model", sort=False):
        if name == ref:
            continue
        d = g.set_index("season")[metrics] - base[metrics]
        row = {"model": name}
        for m in metrics:
            row[m] = d[m].mean()
            row[m + "_se"] = d[m].std(ddof=1) / np.sqrt(len(d)) if len(d) > 1 else np.nan
        rows.append(row)
    return pd.DataFrame(rows).set_index("model")
