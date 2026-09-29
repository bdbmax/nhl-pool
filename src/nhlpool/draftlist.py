"""Ranked draft list for 2026-27 -> output/draft_list.csv."""
import numpy as np
import pandas as pd

from . import project, value
from .config import load_league
from .paths import OUTPUT

COLUMNS = [
    "rank", "pos_rank", "playerId", "name", "pos", "team", "age", "proj_FP", "vorp", "p10", "median", "p90",
    "flags", "proj_GP", "proj_G", "proj_A", "proj_GWG", "proj_HT", "start_share", "proj_W", "proj_OTL", "proj_SO",
    "espn_G", "espn_A", "espn_W", "nhlcom_PTS", "pct_owned", "public_rank", "public_value", "espn_rank", "espn_adp",
    "opp_order", "df_line", "df_pp",
    "df_goalie", "source", "off_roster",
]


def build(refresh: bool = False) -> pd.DataFrame:
    league = load_league()
    proj = project.build(refresh=refresh)
    proj = proj[proj["proj_FP"].notna()]
    sims = value.simulate(proj, n=int(league.get("monte_carlo_sims", 5000)))
    proj = proj.join(sims)
    rl = value.replacement(proj, league)
    proj["vorp"] = proj["proj_FP"] - proj["pos"].map(rl)
    proj["flags"] = value.flags(proj)
    proj["public_value"] = public_value(proj, league["scoring"])
    proj["public_rank"] = proj["public_value"].rank(ascending=False, method="first")
    proj["opp_order"] = opponent_order(proj)
    proj = proj.sort_values("vorp", ascending=False)
    proj["rank"] = np.arange(1, len(proj) + 1)
    proj["pos_rank"] = proj.groupby("pos")["proj_FP"].rank(ascending=False, method="first").astype(int)
    out = proj.reset_index()
    for c in COLUMNS:
        if c not in out:
            out[c] = np.nan
    out = out[COLUMNS]
    num = out.select_dtypes("number").columns.difference(["playerId", "rank", "pos_rank", "public_rank", "opp_order"])
    out[num] = out[num].round(2)
    out.to_csv(OUTPUT / "draft_list.csv", index=False)
    pd.Series(rl).to_json(OUTPUT / "replacement.json")
    return out


def opponent_order(proj: pd.DataFrame) -> pd.Series:
    """The order the other managers are simulated to draft in (1 = first).

    The draft is on ESPN: its draft room lists players by ESPN rank and its
    autodraft follows that rank, so ESPN-ranked players come first in ESPN
    order. Players ESPN does not rank follow, by public projection value.
    """
    key = pd.DataFrame({"unranked": proj["espn_rank"].isna(), "rank": proj["espn_rank"],
                        "value": -proj["public_value"]}, index=proj.index)
    order = key.sort_values(["unranked", "rank", "value"]).index
    return pd.Series(np.arange(1, len(order) + 1), index=order).reindex(proj.index)


def public_value(proj: pd.DataFrame, rules: dict) -> pd.Series:
    """What a typical manager sees: ESPN and NHL.com projections under league scoring.

    Used only to simulate the other managers. Skaters: ESPN goals and assists,
    and NHL.com points split with our own goal share. Goalies: ESPN wins, OT
    losses and shutouts. Players without a public projection use ours.
    """
    v = pd.Series(np.nan, index=proj.index)
    sk = proj["pos"].isin(["F", "D"])
    gw = proj["pos"].map({"F": rules["F"]["goal"], "D": rules["D"]["goal"]}).fillna(1)
    share = (proj["proj_G"] / (proj["proj_G"] + proj["proj_A"])).fillna(0.35)
    espn = gw * proj["espn_G"] + proj["espn_A"]
    nhl = proj["nhlcom_PTS"] * (share * gw + (1 - share))
    v[sk] = pd.concat([espn, nhl], axis=1)[sk].mean(axis=1)
    g = proj["pos"] == "G"
    so = proj["espn_SO"] if "espn_SO" in proj else pd.Series(np.nan, index=proj.index)
    so = so.fillna(proj["rate_SO"] * proj["espn_GS"]) if "rate_SO" in proj else so
    gv = rules["G"]["win"] * proj["espn_W"] + rules["G"]["otl"] * proj["espn_OTL"] + rules["G"]["shutout"] * so
    v[g] = gv[g]
    return v.fillna(proj["proj_FP"])
