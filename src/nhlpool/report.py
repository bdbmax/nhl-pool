"""Backtest report -> output/backtest_report.md.

Tuning-season and fresh-season (2013-14 to 2017-18) results are always computed.
Held-out seasons (2024-25, 2025-26) are scored only with --validate; nothing was
tuned on them, but they have been looked at after rounds 1 to 4.
"""
import pandas as pd

from . import backtest, dataset, params
from .models import baseline, marcel
from .paths import OUTPUT

COLS = ["rho_F", "rho_D", "rho_G", "mae_F", "mae_D", "mae_G", "g_top13", "draft_margin", "draft_rank"]
LABELS = {"rho_F": "Rank corr. F", "rho_D": "Rank corr. D", "rho_G": "Rank corr. G", "mae_F": "MAE F",
          "mae_D": "MAE D", "mae_G": "MAE G", "g_top13": "Top-13 G found", "draft_margin": "Draft margin",
          "draft_rank": "Avg finish"}


def _md(df: pd.DataFrame) -> str:
    df = df.rename(columns=LABELS)
    head = "| " + " | ".join([df.index.name or ""] + list(df.columns)) + " |"
    sep = "|" + "---|" * (len(df.columns) + 1)
    rows = ["| " + " | ".join([str(i)] + [f"{v:.3f}" if abs(v) < 10 else f"{v:.1f}" for v in r]) + " |"
            for i, r in zip(df.index, df.to_numpy())]
    return "\n".join([head, sep] + rows)


ROUND3_OFF = {"evpp": False, "age_slopes": None}
# Round 4 audit: pieces and tuned values that were a tie on the fresh seasons (2013-14 to 2017-18).
# The audit and new-idea results in output/round4 were computed on round 3 minus all of these.
ROUND4_AUDIT_PRUNE = {"gs_late_w": 0.0, "a1_weight": 1.0, "K_pp": 150.0, "min_late_w": 0.0, "min_w1": 1.0}
# Final round 4 (the draft model): a season-by-season era check restored the other three, which help in
# recent seasons (late minutes help in both eras). Only the primary-assist weighting stays removed.
ROUND4_PRUNE = {"a1_weight": 1.0}
# The round 3 value, to rebuild the round 3 model from params_b1.json.
ROUND4_UNDO = {"a1_weight": 1.2}
ROUND2_OFF = {"gs_late_w": 0.0, "so_model": False, "w_team_mix": 0.0, "gf_bottom_up": False}


def round_params() -> dict:
    """Parameters of each round's model, rebuilt from the current params_b1.json (round 4)."""
    P4 = params.load()
    P3 = {**P4, **ROUND4_UNDO}
    P2 = {**P3, **ROUND3_OFF}
    P1 = {**P2, **ROUND2_OFF}
    return {1: P1, 2: P2, 3: P3, 4: P4}


def models():
    R = round_params()
    m = {"B0 last season": lambda d, s, u: baseline.project(d, s, u)}
    for k in (1, 2, 3, 4):
        m[f"Round {k} model"] = lambda d, s, u, q=R[k]: marcel.project(d, s, q, u)
    m[FINAL] = m["Round 4 model"]
    return m


FINAL = "Round 4 model + second-goalie rule"
SIM_KW = {FINAL: {"goalie_rule": {"second_last": 2}}}


def write(validate: bool = False) -> None:
    data = dataset.load()
    M = models()
    parts = ["# Backtest report\n",
             "Every projection for season N uses only data from before N. Metrics compare against actual fantasy "
             "points under league scoring, scaled to 82 games in shortened seasons. The draft simulation uses 13 "
             "teams drafting 8 F, 6 D and 2 G, scored best-ball (best 6 F, 4 D, 1 G), averaged over all 13 draft "
             "slots. \"Naive\" opponents draft by last season's points; \"savvy\" opponents draft by the round 1 "
             "model's value. Every experiment tried in rounds 2 to 4 is listed in "
             "output/experiments_round2.md.\n\n"
             "Three sets of seasons. Tuning seasons chose every parameter and switch. Fresh seasons (2013-14 to "
             "2017-18) were first scored in round 4, with no retuning, as an overfitting check; round 4 (the draft "
             "model) is round 3 without the primary-assist weighting, which did not hold up there. Held-out seasons (2024-25, 2025-26) were never tuned on, but have now "
             "been looked at four times, so they are only partly independent.\n"]
    for label, seasons in (("Tuning seasons (2018-19, 2019-20, 2021-22, 2022-23, 2023-24)", backtest.TUNE),
                           ("Fresh seasons (2013-14 to 2017-18), first scored in round 4", backtest.FRESH),
                           ("Held-out validation seasons (2024-25, 2025-26)", backtest.VALID if validate else None)):
        if seasons is None:
            parts.append(f"\n## {label}\n\nNot run. Use `run.py backtest --validate`.\n")
            continue
        naive = backtest.run(M, data, seasons, sim_kw=SIM_KW)
        savvy = backtest.run({k: v for k, v in M.items() if k != "B0 last season"}, data, seasons,
                             opp_model=M["Round 1 model"], opp_vorp=True, sim_kw=SIM_KW)
        s1 = backtest.summarize(naive)[COLS]
        s1.index.name = "Model"
        s2 = backtest.summarize(savvy)[["draft_margin", "draft_rank"]]
        s2.index.name = "Model"
        parts += [f"\n## {label}\n", "\n### Against naive opponents\n", _md(s1),
                  "\n\n### Against savvy opponents\n", _md(s2), "\n\n### Per season, final model vs baseline\n"]
        per = naive[naive.model.isin(["B0 last season", "Round 3 model", "Round 4 model"])]
        per = per.set_index(["season", "model"])[["rho_F", "rho_D", "rho_G", "mae_F", "draft_rank"]].unstack("model")
        per.columns = [f"{LABELS[a]} / {b}" for a, b in per.columns]
        per.index.name = "Season"
        parts.append(_md(per))
        print(f"== {label}\n", s1.round(3).to_string(), "\n", s2.round(2).to_string())
        print(naive.set_index(["season", "model"])[["rho_F", "rho_D", "rho_G", "g_top13", "draft_margin", "draft_rank"]].round(3).to_string())
    (OUTPUT / "backtest_report.md").write_text("\n".join(parts) + "\n")
    print("wrote", OUTPUT / "backtest_report.md")
