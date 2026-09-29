"""Round 4, part 2: new ideas under the stricter rule.

  uv run python scripts/exp_round4_ideas.py            # every idea
  uv run python scripts/exp_round4_ideas.py env shots  # some of them

Each idea's parameter is tuned on the tuning seasons only, on its own target loss.
Then it is scored against the current model (after the part 1 pruning in PRUNE)
on the tuning and fresh seasons, against all four opponent types. Kept only if
experiments.strict passes: at least 2 standard errors better on its target on the
tuning seasons, not worse on the fresh seasons, and draft margin against the
untuned and noisy opponents not worse by more than one standard error over all ten.
Never writes config/params_b1.json. Tables go to output/round4/ideas_<names>.csv.
"""
import hashlib
import sys

import numpy as np
import pandas as pd

from nhlpool import backtest, params, report, tune
from nhlpool.experiments import Runner, delta, memo, strict
from nhlpool.models import marcel
from nhlpool.paths import CONFIG, OUTPUT

pd.set_option("display.width", 250)
OUT = OUTPUT / "round4"
PFILE = CONFIG / "params_b1.json"
HASH0 = hashlib.sha256(PFILE.read_bytes()).hexdigest()
RULE = {"goalie_rule": {"second_last": 2}}
# Part 1 decisions, applied on top of params_b1.json.
PRUNE = report.ROUND4_AUDIT_PRUNE

P = {**params.load(), **PRUNE}
r = Runner(P=P)


def fmt(m, se, d=1):
    return f"{m:+.{d}f} ± {se:.{d}f}"


def md(df):
    head = "| " + " | ".join([df.index.name or ""] + [str(c) for c in df.columns]) + " |"
    sep = "|" + "---|" * (len(df.columns) + 1)
    return "\n".join([head, sep] + ["| " + " | ".join([str(i)] + [str(v) for v in row]) + " |"
                                    for i, row in zip(df.index, df.to_numpy())])


_full = {}


def full():
    if not _full:
        _full["tune"] = r.table(r.ref, backtest.TUNE, RULE)
        _full["fresh"] = r.table(r.ref, backtest.FRESH, RULE)
    return _full


def score(name, p_new, target, setting, sim_kw=None):
    fn = r.ref if p_new is None else memo(lambda d, s, u: marcel.project(d, s, p_new, u))
    kw = {**RULE, **(sim_kw or {})}
    F = full()
    t = {k: r.table(fn, s, kw) for k, s in (("tune", backtest.TUNE), ("fresh", backtest.FRESH))}
    dt, df = delta(t["tune"], F["tune"]), delta(t["fresh"], F["fresh"])
    pooled = delta(pd.concat([t["tune"], t["fresh"]]), pd.concat([F["tune"], F["fresh"]]))
    if target == "margin_public":  # draft-only idea: mean of the untuned and noisy margins
        for d, tt, ff in ((dt, t["tune"], F["tune"]), (df, t["fresh"], F["fresh"])):
            x = (tt["margin_untuned"] + tt["margin_noisy"]) / 2 - (ff["margin_untuned"] + ff["margin_noisy"]) / 2
            d.loc["margin_public"] = [x.mean(), x.std(ddof=1) / np.sqrt(len(x))]
    ok, why = strict(dt, df, target, pooled)
    row = {"idea": name, "setting": setting, "target": target}
    for k, d, ref in (("tune", dt, F["tune"]), ("fresh", df, F["fresh"])):
        if target in ("rate", "gp", "goalie"):
            b = ref[target].mean()
            row[f"target, {k}"] = fmt(100 * d.loc[target, "mean"] / b, 100 * d.loc[target, "se"] / b) + "%"
        else:
            row[f"target, {k}"] = fmt(d.loc[target, "mean"], d.loc[target, "se"])
    for k, d in (("tune", dt), ("fresh", df)):
        for o in ("untuned", "noisy", "savvy", "naive"):
            row[f"{o}, {k}"] = fmt(d.loc[f"margin_{o}", "mean"], d.loc[f"margin_{o}", "se"])
    row["rho F/D/G fresh"] = "/".join(f"{df.loc[c, 'mean']:+.3f}" for c in ("rho_F", "rho_D", "rho_G"))
    row["decision"] = ("KEEP" if ok else "reject") + f" ({why})"
    print(row, flush=True)
    return row


def tuned(space, loss, extra=None):
    """Grid on tuning seasons only; returns the best params and a short label."""
    p, df = tune.grid(r.ctx, {**P, **(extra or {})}, space, loss)
    best = df.iloc[0]
    label = ", ".join(f"{k}={best[k]}" for k in space)
    print(df[list(space) + [loss]].head(4).to_string(index=False), flush=True)
    return p, label


def idea_weights():
    """Not a new idea: leave-one-season-out picked (3, 2, 2) in all five folds (current 2, 1, 1)."""
    p, lab = tuned({"w": [(2, 1, 1), (3, 2, 1), (3, 2, 2), (1, 1, 1)]}, "rate")
    return [score("Season weights retuned (from the audit)", p, "rate", lab)]


def idea_env():
    p, lab = tuned({"env_adj": [0.25, 0.5, 0.75, 1.0]}, "rate")
    return [score("5 League scoring environment", p, "rate", lab)]


def idea_team_xg():
    p, lab = tuned({"xg_team_w": [0.25, 0.5, 0.75, 1.0]}, "goalie")
    return [score("6 Team strength from expected goals", p, "goalie", lab)]


def idea_shots():
    rows = []
    for variant in ("pos", "career"):
        p, lab = tuned({"K_sh": [100, 200, 400, 800, 1600, 3200]}, "rate", {"sh_model": variant, "xg_weight": 0.0})
        rows.append(score(f"7 Goals = shots x shooting % ({variant}), replacing the xG blend", p, "rate",
                          f"sh_model={variant}, {lab}, xg_weight=0"))
    return rows


def idea_injury():
    p, lab = tuned({"gp_inj": [0.005, 0.01, 0.02, 0.03, 0.05]}, "gp")
    return [score("8 Longer injury history (seasons under 60% of games, last five)", p, "gp", lab)]


def idea_pp_team():
    p, lab = tuned({"pp_team_r": [0.0, 0.25, 0.5, 0.75, 1.0]}, "rate")
    return [score("9 Team power-play volume", p, "rate", lab)]


def idea_scarcity():
    best, best_v, rows = None, -np.inf, []
    for m in (5, 10, 20):
        kw = {**RULE, "scarcity": {"margin": m, "sims": 30, "noise": 0.15}}
        t = r.table(r.ref, backtest.TUNE, kw)
        v = ((t["margin_untuned"] + t["margin_noisy"]) / 2).mean()
        print("scarcity margin", m, round(v, 1), flush=True)
        if v > best_v:
            best, best_v = m, v
    return [score("10 Scarcity-aware picks", None, "margin_public", f"margin={best} points, 30 sims",
                  {"scarcity": {"margin": best, "sims": 30, "noise": 0.15}})]


IDEAS = {"weights": idea_weights, "env": idea_env, "teamxg": idea_team_xg, "shots": idea_shots, "injury": idea_injury,
         "pp": idea_pp_team, "scarcity": idea_scarcity}

if __name__ == "__main__":
    names = sys.argv[1:] or list(IDEAS)
    rows = []
    for n in names:
        rows += IDEAS[n]()
    t = pd.DataFrame(rows).set_index("idea")
    t.to_csv(OUT / f"ideas_{'_'.join(names)}.csv")
    print(t.to_string())
    assert hashlib.sha256(PFILE.read_bytes()).hexdigest() == HASH0, "params_b1.json changed"
    print("params_b1.json unchanged")
