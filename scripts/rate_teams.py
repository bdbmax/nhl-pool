"""Rate every team of the actual 2026-27 draft (data/pool_2026/draft_results.csv).

  uv run python scripts/rate_teams.py

Only external projections are used for ratings and odds: ESPN, NHL.com, CBS and
HockeyBangers (see nhlpool/external.py). Our own model is shown in the report as
a reference column and does not affect the consensus or the odds.

A team's score is its best-ball total: best 6 F + best 4 D + best 1 G.

Finishing odds: 20,000 simulated seasons. Each season draws random weights over the
four sources (the truth sits somewhere among them). On top of that, each player's
season is multiplied by a real season-to-season change drawn from the last three NHL
season pairs (injuries, slumps, breakouts, goalies losing the job).
Writes output/pool_2026/team_ratings.md, team_ratings.csv, finish_odds.csv, team_players.csv.
"""
import json
import re

import numpy as np
import pandas as pd
from scipy.stats import poisson

from nhlpool import dataset, external
from nhlpool.config import load_league
from nhlpool.fetch import espn, others
from nhlpool.fetch.http import cached_text
from nhlpool.names import match, norm
from nhlpool.paths import OUTPUT, ROOT
from nhlpool.scoring import pos_group

OUT = OUTPUT / "pool_2026"
COUNTED = {"F": 6, "D": 4, "G": 1}
FP_URL = "https://www.fantasypros.com/nhl/rankings/overall.php"


def best_ball(df: pd.DataFrame, col: str) -> pd.Series:
    return pd.Series({m: sum(t.loc[t.pos == p, col].nlargest(n).sum() for p, n in COUNTED.items())
                      for m, t in df.groupby("manager")})


def espn_points(L: pd.DataFrame, rules: dict) -> pd.Series:
    """ESPN's projections under league scoring, per playerId."""
    e = espn.projections()
    e["pos_group"] = pos_group(e["pos"])
    left = L.set_index("playerId")[["name", "team"]].assign(pos_group=L.set_index("playerId")["pos"])
    e["playerId"] = match(left, e).reindex(e.index)
    e = e.dropna(subset=["playerId"]).astype({"playerId": int}).drop_duplicates("playerId").set_index("playerId")
    d = dataset.load()["goalies"]
    last = d[d.seasonId == d.seasonId.max()]
    so_rate = last["SO"].sum() / last["GS"].sum()
    v = pd.Series(np.nan, index=e.index)
    for p in ("F", "D"):
        m = e["pos_group"] == p
        r = rules[p]
        v[m] = (r["goal"] * e.loc[m, "espn_G"].fillna(0) + r["assist"] * e.loc[m, "espn_A"].fillna(0)
                + r["gwg"] * e.loc[m, "espn_GWG"].fillna(0) + r.get("hat_trick", 0) * e.loc[m, "espn_HAT"].fillna(0))
    g = e["pos_group"] == "G"
    so = e.loc[g, "espn_SO"].fillna(e.loc[g, "espn_GS"] * so_rate)
    r = rules["G"]
    v[g] = r["win"] * e.loc[g, "espn_W"].fillna(0) + r["otl"] * e.loc[g, "espn_OTL"].fillna(0) + r["shutout"] * so
    return v


def fantasypros() -> pd.DataFrame:
    html = cached_text(FP_URL, "public/fantasypros_nhl_2026.html")
    data = json.loads(re.search(r"var ecrData = (\{.*?\});", html).group(1))
    df = pd.DataFrame([{"name": p["player_name"], "rank": p["rank_ecr"], "pos_raw": p.get("player_positions", "")}
                       for p in data["players"]])
    df["rank"] = pd.to_numeric(df["rank"], errors="coerce")  # stored as text
    return df, data


def rank_to_points(L: pd.DataFrame, rank: pd.Series) -> pd.Series:
    """Consensus total of the k-th best drafted player at his position, k = the source's position rank."""
    out = pd.Series(np.nan, index=L.index)
    for p in ("F", "D", "G"):
        m = L["pos"] == p
        curve = np.sort(L.loc[m, "consensus"].to_numpy())[::-1]
        r = rank[m]
        k = r.rank(method="first").where(r.notna())
        k = k.fillna(r.notna().sum() + 1).astype(int) - 1  # unranked: just past the last ranked
        out[m] = curve[np.minimum(k, len(curve) - 1)]
    return out


def skater_points(rules, pos, g, a, gp, gwg_per_goal, ht_mult):
    """Season points from goals and assists; GWG from goals, hat tricks from the per-game goal rate."""
    goal = pd.Series(np.where(pos == "D", rules["D"]["goal"], rules["F"]["goal"]), index=pos.index)
    ht = np.where(pos == "F", gp * ht_mult * poisson.sf(2, (g / gp.clip(lower=1)).clip(lower=0)), 0.0)
    return goal * g + a + gwg_per_goal * g + rules["F"]["hat_trick"] * ht


def other_sources(L: pd.DataFrame, X: pd.DataFrame, rules: dict) -> pd.DataFrame:
    """NHL.com, CBS and HockeyBangers season points under league scoring, per drafted playerId."""
    ht_mult = params.load()["ht_mult"]
    B = L.loc[X["playerId"].unique()].copy()
    sk = B["pos"].isin(["F", "D"])
    g = B["pos"] == "G"
    gpg = (B["proj_GWG"] / B["proj_G"].replace(0, np.nan)).fillna(0.08)  # our GWG per goal
    share = (B["proj_G"] / (B["proj_G"] + B["proj_A"])).fillna(0.35)
    gp = B["proj_GP"]
    out = pd.DataFrame(index=B.index)
    # NHL.com
    out["nhl_fp"] = skater_points(rules, B["pos"], B["nhlcom_PTS"] * share, B["nhlcom_PTS"] * (1 - share),
                                  gp, gpg, ht_mult).where(sk & B["nhlcom_PTS"].notna())
    # CBS
    c = others.cbs()
    c["k"] = c["name"].map(norm)
    c = c.drop_duplicates(["k", "cbs_pos"]).set_index(["k", "cbs_pos"])
    C = c.reindex(list(zip(B["k"], B["pos"])))
    C.index = B.index
    out["cbs_fp"] = skater_points(rules, B["pos"], C["cbs_G"] / C["cbs_GP"] * gp, C["cbs_A"] / C["cbs_GP"] * gp,
                                  gp, gpg, ht_mult).where(sk & (C["cbs_GP"] > 0))
    per = lambda col: C[col] / C["cbs_GS"].where(C["cbs_GS"] > 0)
    r = rules["G"]
    gv = gp * (r["win"] * per("cbs_W") + r["otl"] * per("cbs_OTL") + r["shutout"] * per("cbs_SO"))
    out.loc[g, "cbs_fp"] = gv[g]
    # HockeyBangers
    hb = others.hockeybangers(list(B.loc[sk, "name"]))
    hb["k"] = hb["name"].map(norm)
    H = hb.drop_duplicates("k").set_index("k").reindex(B["k"])
    H.index = B.index
    out["hb_fp"] = skater_points(rules, B["pos"], H["hb_G82"] / 82 * gp, H["hb_A82"] / 82 * gp, gp, gpg,
                                 ht_mult).where(sk & H["hb_G82"].notna())
    return out


POINTS = external.SOURCES  # ESPN, NHL.com, CBS, HockeyBangers


def md(df):
    head = "| " + " | ".join([df.index.name] + list(df.columns)) + " |"
    sep = "|" + "---|" * (len(df.columns) + 1)
    return "\n".join([head, sep] + ["| " + " | ".join([str(i)] + [str(v) for v in row]) + " |"
                                    for i, row in zip(df.index, df.to_numpy())])


def main():
    league = load_league()
    rules = league["scoring"]
    L = pd.read_csv(OUTPUT / "draft_list.csv")
    L["k"] = L["name"].map(norm)
    D = pd.read_csv(ROOT / "data" / "pool_2026" / "draft_results.csv", dtype={"pick": str})  # "1.10" = round 1, pick 10
    D["k"] = D["name"].map(norm)
    D = D.merge(L[["k", "pos", "playerId"]], on=["k", "pos"], how="left")
    assert D["playerId"].notna().all(), D[D.playerId.isna()]
    L = L.set_index("playerId")

    data = dataset.load()
    fp, meta = fantasypros()
    fp["k"] = fp["name"].map(norm)
    L["fp_rank"] = L["k"].map(fp.drop_duplicates("k").set_index("k")["rank"])
    ids = D["playerId"].astype(int).unique()
    E = external.projections(L.loc[ids, ["name", "team", "pos"]], data)

    X = D.join(L[["proj_FP", "espn_rank", "fp_rank", "source"]], on="playerId").join(E, on="playerId")
    src = list(POINTS.values())
    coverage = {lab: int(X[c].notna().sum()) for lab, c in POINTS.items()}
    avail = X[src].mean(axis=1)
    for c in src:  # a player missing from a source gets the other sources' average
        X[c + "_f"] = X[c].fillna(avail)
    X["consensus"] = X[[c + "_f" for c in src]].mean(axis=1)
    X["espn_rank_pts"] = rank_to_points(X.set_index("playerId"), X.set_index("playerId")["espn_rank"]).to_numpy()
    X["fp_rank_pts"] = rank_to_points(X.set_index("playerId"), X.set_index("playerId")["fp_rank"]).to_numpy()
    cols = {**{lab: c + "_f" for lab, c in POINTS.items()}, "Consensus": "consensus",
            "Our model (not used)": "proj_FP", "ESPN draft rank": "espn_rank_pts", "FantasyPros": "fp_rank_pts"}
    T = pd.DataFrame({lab: best_ball(X, c) for lab, c in cols.items()})

    # Simulated seasons: random source weights, times real season-to-season changes.
    e = X.drop_duplicates("playerId").set_index("playerId")
    n_sims = 20000
    rng = np.random.default_rng(2026)
    V = e[src].to_numpy()                                                        # players x sources
    Wt = rng.dirichlet(np.ones(V.shape[1]), n_sims)                              # sims x sources
    blend = (np.nan_to_num(V) @ Wt.T) / ((~np.isnan(V)).astype(float) @ Wt.T)    # players x sims
    ratios = external.outcome_ratios(data)
    R = np.vstack([rng.choice(ratios[p], n_sims) for p in e["pos"]])
    S = pd.DataFrame(blend * R, index=e.index)

    def season_totals(Sm: pd.DataFrame) -> pd.DataFrame:
        tot = {}
        for mgr, t in X.groupby("manager"):
            s = 0
            for p, n in COUNTED.items():
                ids_ = t.loc[t.pos == p, "playerId"]
                s = s + np.sort(Sm.loc[ids_].to_numpy(), axis=0)[-n:].sum(axis=0)
            tot[mgr] = s
        return pd.DataFrame(tot)

    MC = season_totals(S)
    rank = MC.rank(axis=1, ascending=False, method="first")
    odds = pd.DataFrame({"Expected total": MC.mean(), "Expected finish": rank.mean(),
                         **{k: (rank == k).mean() for k in range(1, 13)}})
    odds.sort_values("Expected finish").round(4).to_csv(OUT / "finish_odds.csv")

    T = T.sort_values("Consensus", ascending=False)
    for c in cols:
        T[f"{c} rank"] = T[c].rank(ascending=False).astype(int)
    rnd, slot = X["pick"].str.split(".").str[0].astype(int), X["pick"].str.split(".").str[1].astype(int)
    T["Pick slot"] = slot[rnd == 1].groupby(X.loc[rnd == 1, "manager"]).first()
    T.index.name = "Manager"
    X["overall"] = (rnd - 1) * 12 + slot
    X.to_csv(OUT / "team_players.csv", index=False)
    T.round(3).to_csv(OUT / "team_ratings.csv")

    show = pd.DataFrame(index=T.index)
    show["Slot"] = T["Pick slot"]
    for c in cols:
        show[c] = [f"{v:.0f} ({r})" for v, r in zip(T[c], T[f"{c} rank"])]
    print(show.to_string())
    print("\nDrafted players covered (of 192):", coverage)
    fo = pd.DataFrame(index=odds.sort_values("Expected finish").index)
    fo.index.name = "Manager"
    o = odds.loc[fo.index]
    fo["Expected total"] = o["Expected total"].round(0).astype(int)
    fo["Avg finish"] = o["Expected finish"].round(1)
    fo["Win %"] = (100 * o[1]).round(1)
    fo["Top 3 %"] = (100 * o[[1, 2, 3]].sum(axis=1)).round(1)
    fo["Bottom 3 %"] = (100 * o[[10, 11, 12]].sum(axis=1)).round(1)
    fo["Last %"] = (100 * o[12]).round(1)
    print(fo.to_string())
    print(f"\nFantasyPros: {meta.get('total_experts')} experts, {meta.get('scoring')} scoring, updated {meta.get('last_updated')}")
    cov = ", ".join(f"{k} {v}" for k, v in coverage.items())
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "team_ratings.md").write_text(HEADER + f"Drafted players each source covers (of 192): {cov}.\n\n"
                                         + md(show) + "\n\n" + ODDS + md(fo) + "\n" + FOOTER)


HEADER = """# 2026-27 pool: team ratings after the draft

12 teams, 16 rounds, snake. Each score is the best-ball total: best 6 F + best 4 D + best 1 G, in season
points under league scoring. The number in brackets is the team's rank under that source. Sorted by the
consensus, the plain average of the four external sources. **Our own model does not affect the consensus
or the odds**; it is shown once, as a reference.

- **ESPN**: ESPN's projections as published, scored with league rules.
- **NHL.com**: NHL.com point projections, split into goals and assists with the player's goal share in
  ESPN or CBS (else the league's). Skaters only.
- **CBS**: CBS Sports projections. CBS gives every skater about 81 games, so its per-game rates are used
  with ESPN's games played.
- **HockeyBangers**: free player pages (goals and assists per 82 games), with ESPN's games played. Skaters only.
- **ESPN draft rank**, **FantasyPros**: ranking-only sources, put on the consensus points scale by position
  rank. Shown, not used in the odds.
- What a source does not project (game-winning goals, hat tricks, missing shutouts) comes from real league
  rates of the 2025-26 NHL season. A player a source does not cover gets the average of the sources that do.

"""
ODDS = """## Finishing odds, external sources only

20,000 simulated seasons. In each one, random weights over the four sources decide where the truth sits.
On top of that, each player's season is multiplied by a real season-to-season change drawn from NHL players
over the last three season pairs (injuries, slumps, breakouts, goalies losing the job). Rosters are fixed
(draft and hold) and only the best 6 F, 4 D and 1 G count.

"""
FOOTER = """
Not included: players on the same NHL team rising or falling together, and every source being wrong in
the same direction. Rebuild with `uv run python scripts/rate_teams.py`.
"""


if __name__ == "__main__":
    main()
