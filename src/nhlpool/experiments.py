"""Experiment runner: every candidate change vs the current model, tuning seasons only.

For each experiment we compute, per tuning season:
  component losses (skater rate, games played, goalie points), rank correlation,
  error, top-13 goalie overlap, and draft margin against naive opponents (last
  season's points) and savvy opponents (the current model's value).
Then the mean paired difference vs the current model and its standard error
(n = 5 seasons). Results accumulate in output/experiments.csv.

Decision rule: keep a change if it improves its target loss on the tuning
seasons, and its draft margin is not worse than the reference by more than one
standard error against either opponent type.

Round 4 adds `table`, which scores any model on any season list (tuning or the
fresh 2013-14 to 2017-18 seasons) against all four opponent types, and `delta`
for paired differences. The stricter round 4 rule is in `strict`.
"""
import numpy as np
import pandas as pd

from . import backtest, dataset, params, tune
from .config import load_league
from .models import marcel
from .paths import OUTPUT

LOG = OUTPUT / "experiments.csv"
OPPONENTS = ("naive", "savvy", "untuned", "noisy")
TABLE_COLS = ["rate", "gp", "goalie", "rho_F", "rho_D", "rho_G", "mae_F", "mae_D", "mae_G", "g_top13",
              "margin_naive", "margin_G_naive", "margin_savvy", "margin_untuned", "margin_noisy"]


def memo(fn):
    """Cache a projection function per season (data and universe are fixed within a run)."""
    cache = {}

    def f(d, s, u):
        if s not in cache:
            cache[s] = fn(d, s, u)
        return cache[s]
    return f


class Runner:
    def __init__(self, data=None, P=None, league=None):
        self.data = data or dataset.load()
        self.P = P or params.load()
        self.league = league or load_league()
        self.ctx = tune.Ctx(self.data, backtest.TUNE)
        self.fctx = tune.Ctx(self.data, backtest.FRESH)
        self.ref = memo(lambda d, s, u: marcel.project(d, s, self.P, u))
        self.untuned = memo(lambda d, s, u: marcel.project(d, s, None, u))
        self._ref_cache = None

    def _losses(self, fn):
        return pd.DataFrame(self.ctx.losses_fn(fn, per_season=True), index=backtest.TUNE)

    def _metrics(self, fn, sim_kw=None, opp=None, opp_noise=0.0, seasons=None):
        kw = dict(sim_kw or {})
        if opp_noise:
            kw.update({"opp_noise": opp_noise, "seeds": [0, 1, 2]})
        return backtest.run({"x": fn}, self.data, seasons or backtest.TUNE, league=self.league,
                            opp_model=opp, opp_vorp=opp is not None, sim_kw={"x": kw}).set_index("season")

    def table(self, fn, seasons, sim_kw=None) -> pd.DataFrame:
        """Per season: component losses, accuracy, and draft margin against each opponent type.

        naive: last season's points. savvy: the current model's value. untuned:
        untuned Marcel's value. noisy: the current model with 15% random disagreement.
        """
        ctx = {tuple(self.ctx.seasons): self.ctx, tuple(self.fctx.seasons): self.fctx}.get(tuple(seasons))
        ctx = ctx or tune.Ctx(self.data, seasons)
        try:
            L = pd.DataFrame(ctx.losses_fn(fn, per_season=True), index=seasons)[["rate", "gp", "goalie"]]
        except KeyError:  # no games-played projection (last-season baseline)
            L = pd.DataFrame(np.nan, index=seasons, columns=["rate", "gp", "goalie"])
        N = self._metrics(fn, sim_kw, seasons=seasons)
        out = L.join(N[["rho_F", "rho_D", "rho_G", "mae_F", "mae_D", "mae_G", "g_top13"]])
        out["margin_naive"], out["margin_G_naive"] = N["draft_margin"], N["draft_margin_G"]
        out["margin_savvy"] = self._metrics(fn, sim_kw, opp=self.ref, seasons=seasons)["draft_margin"]
        out["margin_untuned"] = self._metrics(fn, sim_kw, opp=self.untuned, seasons=seasons)["draft_margin"]
        out["margin_noisy"] = self._metrics(fn, sim_kw, opp=self.ref, opp_noise=0.15, seasons=seasons)["draft_margin"]
        return out[TABLE_COLS]

    def reference(self):
        if self._ref_cache is None:
            self._ref_cache = (self._losses(self.ref), self._metrics(self.ref), self._metrics(self.ref, opp=self.ref))
        return self._ref_cache

    def robust(self, name: str, fn, sim_kw=None) -> dict:
        """Draft margin vs the current model against three more opponent types:
        untuned Marcel, and the current model with 15% random disagreement."""
        untuned = lambda d, s, u: marcel.project(d, s, None, u)
        out = {"experiment": name}
        for label, opp, noise in (("untuned", untuned, 0.0), ("noisy", self.ref, 0.15)):
            a = self._metrics(fn, sim_kw, opp=opp, opp_noise=noise)["draft_margin"]
            b = self._metrics(self.ref, None, opp=opp, opp_noise=noise)["draft_margin"]
            d = a - b
            out[f"d_margin_{label}"] = d.mean()
            out[f"d_margin_{label}_se"] = d.std(ddof=1) / np.sqrt(len(d))
        return out

    def compare(self, name: str, fn=None, sim_kw=None, note: str = "", save: bool = True) -> dict:
        fn = fn or self.ref
        L0, N0, S0 = self.reference()
        L1 = self._losses(fn) if fn is not self.ref else L0
        N1 = self._metrics(fn, sim_kw)
        S1 = self._metrics(fn, sim_kw, opp=self.ref)
        row = {"experiment": name, "note": note}

        def add(key, a, b):
            d = (a - b).astype(float)
            row[key] = d.mean()
            row[key + "_se"] = d.std(ddof=1) / np.sqrt(len(d))

        for k in ("rate", "gp", "goalie"):
            add("d_loss_" + k, L1[k], L0[k])
        for k in ("rho_F", "rho_D", "rho_G", "mae_F", "mae_D", "mae_G", "g_top13"):
            add("d_" + k, N1[k], N0[k])
        add("d_margin_naive", N1["draft_margin"], N0["draft_margin"])
        add("d_margin_savvy", S1["draft_margin"], S0["draft_margin"])
        add("d_margin_G_naive", N1["draft_margin_G"], N0["draft_margin_G"])
        row["margin_savvy_level"] = S1["draft_margin"].mean()
        if save:
            self._save(row)
        return row

    @staticmethod
    def _save(row):
        df = pd.read_csv(LOG) if LOG.exists() else pd.DataFrame()
        if len(df):
            df = df[df.experiment != row["experiment"]]
        pd.concat([df, pd.DataFrame([row])], ignore_index=True).to_csv(LOG, index=False)


def delta(a: pd.DataFrame, b: pd.DataFrame) -> pd.DataFrame:
    """Mean paired per-season difference a - b and its standard error, per column."""
    d = (a - b).astype(float)
    return pd.DataFrame({"mean": d.mean(), "se": d.std(ddof=1) / np.sqrt(len(d))})


LOWER_IS_BETTER = {"rate", "gp", "goalie", "mae_F", "mae_D", "mae_G"}


def strict(dt: pd.DataFrame, df: pd.DataFrame, target: str, pooled: pd.DataFrame | None = None) -> tuple[bool, str]:
    """Round 4 rule for a new idea, given deltas (new - current) on tuning (dt) and fresh (df) seasons.

    Kept only if: the target improves by at least 2 standard errors on the tuning
    seasons, it is not worse on the fresh seasons (point estimate), and the draft
    margin against the public-style opponents (untuned and noisy) is not worse by
    more than one standard error over all ten seasons (pooled).
    """
    sign = -1 if target in LOWER_IS_BETTER else 1
    gain_t = sign * dt.loc[target, "mean"]
    reasons = []
    if not gain_t >= 2 * dt.loc[target, "se"]:
        reasons.append(f"tuning gain {gain_t / max(dt.loc[target, 'se'], 1e-12):.1f} SE < 2")
    if sign * df.loc[target, "mean"] < 0:
        reasons.append("worse on fresh seasons")
    if pooled is not None:
        for o in ("margin_untuned", "margin_noisy"):
            if pooled.loc[o, "mean"] < -pooled.loc[o, "se"]:
                reasons.append(f"{o.split('_')[1]} margin {pooled.loc[o, 'mean']:+.1f} ± {pooled.loc[o, 'se']:.1f}")
    return (not reasons), ("; ".join(reasons) or "passes")


def show(rows) -> str:
    """Compact table: difference vs current model, with standard error."""
    out = []
    for r in rows:
        f = lambda k, d=3: f"{r[k]:+.{d}f} ± {r[k + '_se']:.{d}f}"
        out.append({"experiment": r["experiment"],
                    "rate loss": f("d_loss_rate", 5), "GP loss": f("d_loss_gp", 1), "goalie loss": f("d_loss_goalie", 1),
                    "rho F": f("d_rho_F"), "rho D": f("d_rho_D"), "rho G": f("d_rho_G"), "G top13": f("d_g_top13", 2),
                    "margin naive": f("d_margin_naive", 1), "margin savvy": f("d_margin_savvy", 1)})
    return pd.DataFrame(out).to_string(index=False)
