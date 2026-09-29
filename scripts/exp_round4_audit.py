"""Round 4, part 1: overfitting audit.

  uv run python scripts/exp_round4_audit.py rounds    # every round on the fresh seasons, no retuning
  uv run python scripts/exp_round4_audit.py ablation  # switch off each adopted piece, one at a time
  uv run python scripts/exp_round4_audit.py rookies   # rookie prior on fresh debut seasons
  uv run python scripts/exp_round4_audit.py loso      # leave-one-season-out tuning of the main numbers
  uv run python scripts/exp_round4_audit.py pruned    # the model after the removals vs round 3

Fresh seasons (2013-14 to 2017-18) were never used to choose anything. The audit
is of the round 3 model, rebuilt from config/params_b1.json with report.ROUND4_UNDO;
the script never writes that file (checked at exit). Tables go to output/round4/.
"""
import hashlib
import json
import sys

import numpy as np
import pandas as pd

from nhlpool import backtest, report, tune
from nhlpool.experiments import TABLE_COLS, Runner, delta, memo
from nhlpool.models import baseline, marcel
from nhlpool.paths import CONFIG, OUTPUT

pd.set_option("display.width", 250)
OUT = OUTPUT / "round4"
OUT.mkdir(exist_ok=True)
PFILE = CONFIG / "params_b1.json"
HASH0 = hashlib.sha256(PFILE.read_bytes()).hexdigest()
RULE = {"goalie_rule": {"second_last": 2}}
SETS = {"tune": backtest.TUNE, "fresh": backtest.FRESH}

P = report.round_params()[3]
r = Runner(P=P)


def fmt(m, se, d=1):
    return f"{m:+.{d}f} ± {se:.{d}f}"


def md(df: pd.DataFrame) -> str:
    head = "| " + " | ".join([df.index.name or ""] + [str(c) for c in df.columns]) + " |"
    sep = "|" + "---|" * (len(df.columns) + 1)
    rows = ["| " + " | ".join([str(i)] + [str(v) for v in row]) + " |" for i, row in zip(df.index, df.to_numpy())]
    return "\n".join([head, sep] + rows)


def tables(fn, sim_kw=None):
    return {k: r.table(fn, s, sim_kw) for k, s in SETS.items()}


def pct(d: pd.DataFrame, ref: pd.DataFrame, col: str) -> str:
    """Loss difference as a percent of the reference loss."""
    base = ref[col].mean()
    return fmt(100 * d.loc[col, "mean"] / base, 100 * d.loc[col, "se"] / base, 1) + "%"


# ---------------- rounds ----------------

def rounds():
    P2 = {**P, **report.ROUND3_OFF}
    P1 = {**P2, **report.ROUND2_OFF}
    models = {
        "B0 last season": (memo(lambda d, s, u: baseline.project(d, s, u)), None),
        "Untuned Marcel": (r.untuned, None),
        "Round 1": (memo(lambda d, s, u: marcel.project(d, s, P1, u)), None),
        "Round 2": (memo(lambda d, s, u: marcel.project(d, s, P2, u)), None),
        "Round 3": (r.ref, None),
        "Round 3 + second-goalie rule": (r.ref, RULE),
    }
    T = {name: tables(fn, kw) for name, (fn, kw) in models.items()}
    for name, t in T.items():
        for k, df in t.items():
            df.assign(model=name).to_csv(OUT / f"rounds_{k}_{name.replace(' ', '_')}.csv")
    out = ["## Every round scored on tuning and fresh seasons, no retuning\n"]
    lv_cols = ["rho_F", "rho_D", "rho_G", "mae_F", "mae_D", "mae_G", "g_top13",
               "margin_naive", "margin_savvy", "margin_untuned", "margin_noisy"]
    for k in SETS:
        lv = pd.DataFrame({name: t[k][lv_cols].mean() for name, t in T.items()}).T
        lv.index.name = f"{k} seasons, mean"
        out += [f"\n### Levels, {k} seasons\n", md(lv.round(3))]
        print(lv.round(3).to_string(), flush=True)
    steps = [("Round 1 vs untuned", "Round 1", "Untuned Marcel"), ("Round 2 vs Round 1", "Round 2", "Round 1"),
             ("Round 3 vs Round 2", "Round 3", "Round 2"),
             ("Second-goalie rule vs Round 3", "Round 3 + second-goalie rule", "Round 3"),
             ("Round 3 + rule vs Round 1", "Round 3 + second-goalie rule", "Round 1")]
    rows = []
    for label, a, b in steps:
        for k in SETS:
            d = delta(T[a][k], T[b][k])
            ref = T[b][k]
            rows.append({"step": label, "seasons": k,
                         "rate loss": pct(d, ref, "rate"), "GP loss": pct(d, ref, "gp"), "goalie loss": pct(d, ref, "goalie"),
                         "rho F": fmt(d.loc["rho_F", "mean"], d.loc["rho_F", "se"], 3),
                         "rho D": fmt(d.loc["rho_D", "mean"], d.loc["rho_D", "se"], 3),
                         "rho G": fmt(d.loc["rho_G", "mean"], d.loc["rho_G", "se"], 3),
                         **{f"margin {o}": fmt(d.loc[f"margin_{o}", "mean"], d.loc[f"margin_{o}", "se"])
                            for o in ("naive", "savvy", "untuned", "noisy")}})
    st = pd.DataFrame(rows).set_index("step")
    out += ["\n### Paired changes (mean per season ± standard error, n = 5)\n", md(st)]
    print(st.to_string(), flush=True)
    (OUT / "rounds.md").write_text("\n".join(out) + "\n")


# ---------------- ablation ----------------

PIECES = [
    # name, params to switch off, target, sim_kw for the ablated model (None = same as full model)
    ("Late goalie start share", {"gs_late_w": 0.0}, "goalie"),
    ("Shutout model", {"so_model": False}, "goalie"),
    ("Goalie win mix", {"w_team_mix": 0.0}, "goalie"),
    ("Roster-built team goals", {"gf_bottom_up": False}, "rate"),
    ("GWG from team wins (round 1)", {"gwg_team": False, "gf_bottom_up": False}, "rate"),
    ("Power-play split", {"evpp": False}, "rate"),
    ("Flexible age curve (back to round 1 line)", {"age_slopes": None}, "rate"),
    ("Any age curve", {"age_slopes": None, "age_young": 0.0, "age_old": 0.0}, "rate"),
    ("Expected-goals blend", {"xg_weight": 0.0}, "rate"),
    ("Primary assists", {"a1_weight": 1.0}, "rate"),
    ("Games played rises for scorers (round 1)", {"gp_rate": 0.0}, "gp"),
    ("Hat-trick overdispersion (round 1)", {"ht_mult": 1.0}, "rate"),
]


def ablation():
    full = tables(r.ref, RULE)
    rows, raw = [], {}
    items = [(n, sw, tgt, RULE) for n, sw, tgt in PIECES] + [("Second-goalie rule", {}, "margin_untuned", None)]
    for name, sw, target, kw in items:
        fn = r.ref if not sw else memo(lambda d, s, u, q={**P, **sw}: marcel.project(d, s, q, u))
        t = tables(fn, kw)
        dt, df = delta(t["tune"], full["tune"]), delta(t["fresh"], full["fresh"])
        pooled = delta(pd.concat([t["tune"], t["fresh"]]), pd.concat([full["tune"], full["fresh"]]))
        raw[name] = {"tune": dt, "fresh": df, "pooled": pooled}
        row = {"piece switched off": name, "target": target}
        for k, d in (("tune", dt), ("fresh", df)):
            if target in ("rate", "gp", "goalie"):
                row[f"target loss, {k}"] = pct(d, full[k], target)
            else:
                row[f"target loss, {k}"] = "(draft only)"
        for k, d in (("tune", dt), ("fresh", df)):
            for o in ("untuned", "noisy", "savvy", "naive"):
                row[f"{o}, {k}"] = fmt(d.loc[f"margin_{o}", "mean"], d.loc[f"margin_{o}", "se"])
        for k, d in (("tune", dt), ("fresh", df)):
            row[f"rho G, {k}"] = fmt(d.loc["rho_G", "mean"], d.loc["rho_G", "se"], 3)
        rows.append(row)
        print(row, flush=True)
    ab = pd.DataFrame(rows).set_index("piece switched off")
    ab.to_csv(OUT / "ablation.csv")
    pd.to_pickle(raw, OUT / "ablation_raw.pkl")
    txt = ["## Ablation: each adopted piece switched off, change vs the full model\n",
           "Positive loss change or negative margin change means removing the piece hurts (the piece helps).\n",
           md(ab)]
    (OUT / "ablation.md").write_text("\n".join(txt) + "\n")
    print(ab.to_string())


# ---------------- rookies ----------------

def rookies_audit():
    from nhlpool.models import rookies
    data = r.data
    sk = data["skaters"]
    first_any = sk.groupby("playerId").seasonId.min()
    rows = []
    for label, seasons in SETS.items():
        for s in seasons:
            ids = first_any[first_any == s].index
            cur = sk[(sk.seasonId == s) & sk.playerId.isin(ids)].set_index("playerId")
            new = pd.DataFrame({"name": cur["name"], "pos_group": cur["pos"], "team": cur["first_team"],
                                "birthDate": cur["birthDate"]})
            strength = marcel.team_strength(data["teams"], s, P["team_regress"])
            fac = rookies.fit_factors(data, before=s)
            for pr in (0.6, 0.8, 1.0, 1.2):
                o = rookies.project(new, data, P, strength, pd.DataFrame(columns=["df_line"]), season=s,
                                    prior=pr, factors=fac)
                o = o[o["pos"] != "G"].join(cur[["GP", "G", "A"]])
                o = o[o.GP >= 20]
                pred, act = o.rate_G + o.rate_A, (o.G + o.A) / o.GP
                rows.append({"set": label, "season": s, "prior": pr, "n": len(o),
                             "pred_pts": float((pred * o.GP).sum()), "act_pts": float((o.G + o.A).sum()),
                             "mse": float(np.average((pred - act) ** 2, weights=o.GP))})
            print(label, s, len(o), flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "rookies.csv", index=False)
    g = df.groupby(["set", "prior"]).agg(n=("n", "sum"), pred=("pred_pts", "sum"), act=("act_pts", "sum"),
                                         mse=("mse", "mean"))
    g["actual / projected"] = g.act / g.pred
    # Paired per-season change vs the old prior 0.6.
    base = df[df.prior == 0.6].set_index(["set", "season"])["mse"]
    d = df.set_index(["set", "season"]).assign(d=lambda x: x["mse"] - base.reindex(x.index)).reset_index()
    se = d.groupby(["set", "prior"])["d"].agg(lambda x: x.std(ddof=1) / np.sqrt(len(x)))
    g["mse change vs 0.6"] = [fmt(m, s_, 4) for m, s_ in zip(d.groupby(["set", "prior"])["d"].mean(), se)]
    print(g.round(4).to_string())
    (OUT / "rookies.md").write_text("## Rookie prior on debut seasons\n\n" + md(g.round(4)) + "\n")


# ---------------- pruned model ----------------

def pruned():
    """The model after the audit removals vs the round 3 model, on both season sets."""
    q = {**P, **report.ROUND4_AUDIT_PRUNE}
    fn = memo(lambda d, s, u: marcel.project(d, s, q, u))
    a, b = tables(fn, RULE), tables(r.ref, RULE)
    rows = []
    for k in SETS:
        d = delta(a[k], b[k])
        rows.append({"seasons": k, **{c: pct(d, b[k], c) for c in ("rate", "gp", "goalie")},
                     **{c: fmt(d.loc[c, "mean"], d.loc[c, "se"], 3) for c in ("rho_F", "rho_D", "rho_G")},
                     **{o: fmt(d.loc[f"margin_{o}", "mean"], d.loc[f"margin_{o}", "se"])
                        for o in ("naive", "savvy", "untuned", "noisy")}})
    t = pd.DataFrame(rows).set_index("seasons")
    print(t.to_string())
    (OUT / "pruned.md").write_text("## Pruned model vs round 3 (both with the second-goalie rule)\n\n" + md(t) + "\n")


# ---------------- leave one season out ----------------

def _set(p, k, v):
    if "." in k:
        a, b = k.split(".")
        return {**p, a: {**p[a], b: v}}
    return {**p, k: v}


def _val(p, k):
    if "." in k:
        a, b = k.split(".")
        return p[a][b]
    return p[k]


def age_search(ctx, p):
    """Coordinate descent over the five age slopes (as in round 3)."""
    grids = {"s1": [0.0, 0.04, 0.08, 0.12, 0.16], "s2": [0.0, 0.02, 0.04, 0.06, 0.08],
             "s3": [-0.02, -0.01, 0.0, 0.01, 0.02], "s4": [0.0, 0.01, 0.02, 0.04], "s5": [0.02, 0.03, 0.05, 0.07, 0.09]}
    best = dict(p["age_slopes"])
    best_loss = ctx.losses({**p, "age_slopes": best})["rate"]
    for _ in range(2):
        for k, vals in grids.items():
            for v in vals:
                trial = {**best, k: v}
                l = ctx.losses({**p, "age_slopes": trial})["rate"]
                if l < best_loss - 1e-12:
                    best, best_loss = trial, l
    return {**p, "age_slopes": best}


GROUPS = {
    # name: (grid or "age", loss, simpler values)
    "Season weights": ({"w": [(1, 0, 0), (2, 1, 0), (3, 2, 1), (2, 1, 1), (3, 2, 2), (5, 3, 2), (1, 1, 1)]},
                       "rate", {"w": (5.0, 3.0, 2.0)}),
    "Per-minute shrinkage": ({"K_ev": [150, 300, 600, 1200, 2400], "K_pp": [25, 50, 150, 400]},
                             "rate", {"K_ev": 600.0, "K_pp": 150.0}),
    "Next season's minutes": ({"min_late_w": [0.0, 0.1, 0.2, 0.4], "min_w1": [1.0, 0.85, 0.7]},
                              "rate", {"min_late_w": 0.0, "min_w1": 1.0}),
    "Age slopes": ("age", "rate", {"age_slopes": None}),
    "Games-played weights and shrinkage": ({"gp_w": [(1, 0, 0), (3, 1, 0), (5, 2, 1), (5, 3, 2)],
                                            "gp_K": [0.5, 1, 2, 3]}, "gp", {"gp_w": (5.0, 3.0, 2.0), "gp_K": 1.0}),
    "Games-played prior": ({"gp_mu.F": [0.7, 0.8, 0.9], "gp_mu.D": [0.7, 0.8, 0.9], "gp_age": [0.0, 0.005, 0.01],
                            "gp_rate": [0.0, 0.1, 0.2]}, "gp",
                           {"gp_mu": {"F": 0.8, "D": 0.8}, "gp_age": 0.0, "gp_rate": 0.0}),
    "Goalie start share": ({"g_w": [(1, 0, 0), (2, 1, 0), (3, 2, 1)], "gs_K": [0.1, 0.25, 0.5, 1.0],
                            "gs_mu": [0.4, 0.5, 0.6, 0.7], "gs_late_w": [0.0, 0.25, 0.5]}, "goalie",
                           {"g_w": (5.0, 3.0, 2.0), "gs_K": 1.0, "gs_mu": 0.3, "gs_late_w": 0.0}),
    "Goalie per-start rates": ({"g_K.W": [5, 10, 20, 40], "sv_K": [1000, 3000, 8000], "so_c": [0.7, 0.85, 1.0],
                                "w_team_mix": [0.0, 0.25, 0.5, 0.75]}, "goalie",
                               {"g_K": {"W": 60.0, "OTL": 60.0, "SO": 60.0}, "sv_K": 3000.0, "so_c": 1.0,
                                "w_team_mix": 0.0}),
}


def _search(ctx, p, space, loss):
    if space == "age":
        return age_search(ctx, p)
    best, _ = tune.grid(ctx, p, space, loss)
    return best


def _chosen(p, space):
    if space == "age":
        return {k: round(v, 3) for k, v in p["age_slopes"].items()}
    out = {}
    for k in space:
        v = _val(p, k)
        out[k] = tuple(int(x) if float(x).is_integer() else x for x in v) if isinstance(v, (tuple, list)) else (
            float(v) if isinstance(v, (int, float, np.floating)) and not isinstance(v, bool) else v)
    return out


def loso():
    data = r.data
    one = {s: tune.Ctx(data, [s]) for s in backtest.TUNE}
    rows, detail = [], []
    for name, (space, loss, simple) in GROUPS.items():
        p_simple = dict(P)
        for k, v in simple.items():
            p_simple[k] = v
        p_all = _search(r.ctx, P, space, loss)
        folds = []
        for h in backtest.TUNE:
            ctx4 = tune.Ctx(data, [s for s in backtest.TUNE if s != h])
            ph = _search(ctx4, P, space, loss)
            lh = {lab: one[h].losses(q)[loss] for lab, q in (("fold", ph), ("all", p_all), ("current", P),
                                                            ("simple", p_simple))}
            folds.append({"held": h, **lh, "chosen": _chosen(ph, space)})
            detail.append({"group": name, "held_out": h, "chosen": json.dumps(_chosen(ph, space), default=str),
                           **{f"loss_{k}": v for k, v in lh.items()}})
            print(name, h, _chosen(ph, space), flush=True)
        F = pd.DataFrame(folds)
        in_gain = F["simple"] - F["all"]       # tuned on all five, scored in sample
        out_gain = F["simple"] - F["fold"]     # tuned on four, scored on the fifth
        fr = {lab: np.array(r.fctx.losses(q, per_season=True)[loss])
              for lab, q in (("simple", p_simple), ("current", P))}
        fresh_gain = fr["simple"] - fr["current"]
        base = F["simple"].mean()
        n_same = sum(json.dumps(c, default=str) == json.dumps(_chosen(p_all, space), default=str) for c in F["chosen"])
        se = lambda x: x.std(ddof=1) / np.sqrt(len(x))
        rows.append({
            "group": name, "loss": loss,
            "tuned on all 5": json.dumps(_chosen(p_all, space), default=str),
            "current": json.dumps(_chosen(P, space), default=str),
            "folds agreeing": f"{n_same}/5",
            "in-sample gain vs simpler": f"{100 * in_gain.mean() / base:+.2f}%",
            "left-out gain vs simpler": f"{100 * out_gain.mean() / base:+.2f} ± {100 * se(out_gain) / base:.2f}%",
            "optimism": f"{100 * (in_gain.mean() - out_gain.mean()) / base:.2f} pts",
            "fresh gain, current vs simpler": f"{100 * fresh_gain.mean() / fr['simple'].mean():+.2f} ± "
                                              f"{100 * se(fresh_gain) / fr['simple'].mean():.2f}%",
        })
        print(rows[-1], flush=True)
    t = pd.DataFrame(rows).set_index("group")
    t.to_csv(OUT / "loso.csv")
    pd.DataFrame(detail).to_csv(OUT / "loso_folds.csv", index=False)
    txt = ["## Leave-one-season-out tuning\n",
           "Gains are the loss reduction versus the simpler values, as a percent of the simpler loss. "
           "In-sample: tuned on all five tuning seasons and scored on them. Left-out: tuned on four, scored on the "
           "fifth. Optimism is the difference. Fresh: the current values vs the simpler ones on 2013-14 to 2017-18.\n",
           md(t)]
    (OUT / "loso.md").write_text("\n".join(txt) + "\n")
    print(t.to_string())


if __name__ == "__main__":
    parts = sys.argv[1:] or ["rounds", "ablation", "rookies", "loso"]
    for part in parts:
        {"rounds": rounds, "ablation": ablation, "rookies": rookies_audit, "loso": loso, "pruned": pruned}[part]()
    assert hashlib.sha256(PFILE.read_bytes()).hexdigest() == HASH0, "params_b1.json changed during the audit"
    print("params_b1.json unchanged")
