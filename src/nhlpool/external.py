"""External-only projections: ESPN, NHL.com, CBS and HockeyBangers. Nothing from our model.

Each source's projected stats are scored with league rules. Where a source does
not project something, it is filled from real league rates of the last completed
NHL season (actual stats, not projections):
  games played    ESPN's projection, else CBS's, else the position's median
  goal/assist     for NHL.com's points: the player's goal share in ESPN or CBS,
                  else the position's league share
  game-winners    CBS projects them; other sources use the league's GWG per goal
  hat tricks      Poisson chance of 3+ goals from the goal rate, scaled so it
                  matches the league's actual hat-trick count last season
  shutouts, OTL   ESPN's when given, else league rate per start
Consensus = plain average of the sources that cover the player.

Season-to-season surprise (for the odds) comes from real data too: how a player's
fantasy total changed from one season to the next, across the last three season
pairs, by position. That includes injuries and goalies losing the job.
"""
import numpy as np
import pandas as pd
from scipy.stats import poisson

from .config import load_league
from .fetch import espn, others, public
from .history import prev
from .names import match, norm

SOURCES = {"ESPN": "espn_fp", "NHL.com": "nhl_fp", "CBS": "cbs_fp", "HockeyBangers": "hb_fp"}


def league_facts(data: dict) -> dict:
    """Real league rates from the last completed season in the processed tables."""
    sk, gl = data["skaters"], data["goalies"]
    s = sk.seasonId.max()
    k, g = sk[sk.seasonId == s], gl[gl.seasonId == s]
    rate = (k["G"] / k["GP"].clip(lower=1)).clip(lower=0)
    expected_ht = (k["GP"] * poisson.sf(2, rate)).where(k["pos"] == "F").sum()
    return {
        "season": int(s),
        "gwg_per_goal": float(k["GWG"].sum() / k["G"].sum()),
        "ht_calib": float(k.loc[k.pos == "F", "HT"].sum() / expected_ht),
        "goal_share": (k.groupby("pos")["G"].sum() / k.groupby("pos")["PTS"].sum()).to_dict(),
        "so_per_start": float(g["SO"].sum() / g["GS"].sum()),
        "otl_per_start": float(g["OTL"].sum() / g["GS"].sum()),
        "median_gp": k[k.GP >= 20].groupby("pos")["GP"].median().to_dict(),
    }


SKATER_RATES = ("G", "A", "GWG", "HT")   # per game
GOALIE_RATES = ("W", "OTL", "SO")         # per start
KEYS = {"ESPN": "espn", "NHL.com": "nhl", "CBS": "cbs", "HockeyBangers": "hb"}


def _ht(goal_rate: pd.Series, facts: dict) -> pd.Series:
    """Hat tricks per game: Poisson chance of 3+ goals, calibrated to last season's real count."""
    return facts["ht_calib"] * pd.Series(poisson.sf(2, goal_rate.clip(lower=0).fillna(0)), index=goal_rate.index)


def rates(people: pd.DataFrame, data: dict, hb_names: list[str] | None = None,
          refresh: bool = False, hb_refresh: bool | None = None) -> pd.DataFrame:
    """Per-game rates from each external source, per player.

    people: index playerId (NHL id), columns name, team, pos (F/D/G).
    hb_names: players to look up on HockeyBangers (one page each); default all skaters.
    Columns: {src}_{G,A,GWG,HT} per game for skaters, {src}_{W,OTL,SO} per start for goalies,
    with src in espn/nhl/cbs/hb (NaN where the source does not cover the player), plus
    ext_gp (projected games, ESPN else CBS else the position's median) and ext_starts
    (goalies: ESPN starts, else ESPN games, else CBS starts).
    Per-game rates mean the same thing whether a source publishes season totals or
    rest-of-season numbers, which is what the daily update needs.
    """
    facts = league_facts(data)
    P = people.copy()
    P["k"] = P["name"].map(norm)
    left = P.assign(pos_group=P["pos"])[["name", "team", "pos_group"]]
    out = pd.DataFrame(index=P.index)
    sk, gmask = P["pos"].isin(["F", "D"]), P["pos"] == "G"
    nan = pd.Series(np.nan, index=P.index)

    # ESPN
    e = espn.projections(refresh=refresh)
    e["pos_group"] = e["pos"].map({"C": "F", "L": "F", "R": "F", "D": "D", "G": "G"})
    e["playerId"] = match(left, e).reindex(e.index)
    E = e.dropna(subset=["playerId"]).astype({"playerId": int}).drop_duplicates("playerId").set_index("playerId").reindex(P.index)
    # CBS
    c = others.cbs(refresh=refresh)
    c["k"] = c["name"].map(norm)
    C = c.drop_duplicates(["k", "cbs_pos"]).set_index(["k", "cbs_pos"]).reindex(list(zip(P["k"], P["pos"])))
    C.index = P.index

    gp = E["espn_GP"].where(E["espn_GP"] > 0).fillna(C["cbs_GP"].where(C["cbs_GP"] > 0))
    gp = gp.fillna(P["pos"].map(facts["median_gp"])).fillna(70.0)
    out["ext_gp"] = gp
    starts = E["espn_GS"].where(E["espn_GS"] > 0).fillna(E["espn_GP"].where(E["espn_GP"] > 0))
    out["ext_starts"] = starts.fillna(C["cbs_GS"].where(C["cbs_GS"] > 0)).where(gmask)
    # ESPN's horizon (84 games for a full season, fewer if it switches to rest-of-season).
    hz = E.loc[sk, "espn_GP"].dropna()
    out.attrs["horizon"] = float(hz[hz > 0].quantile(0.98)) if (hz > 0).any() else 82.0

    def skater(key, g, a, gwg):
        g, a = g.where(sk), a.where(sk)
        out[f"{key}_G"], out[f"{key}_A"] = g, a
        out[f"{key}_GWG"] = gwg.where(sk).fillna(g * facts["gwg_per_goal"])
        out[f"{key}_HT"] = _ht(g, facts).where(g.notna() & (P["pos"] == "F"), 0.0).where(g.notna())

    def goalie(key, w, otl, so):
        for col, v in (("W", w), ("OTL", otl), ("SO", so)):
            out.loc[gmask, f"{key}_{col}"] = v[gmask]

    # ESPN: totals over its games (skaters) or starts (goalies)
    skater("espn", E["espn_G"] / gp, E["espn_A"] / gp, nan)
    gs = E["espn_GS"].where(E["espn_GS"] > 0).fillna(E["espn_GP"].where(E["espn_GP"] > 0))
    goalie("espn", E["espn_W"] / gs, (E["espn_OTL"] / gs).fillna(facts["otl_per_start"]).where(E["espn_W"].notna()),
           (E["espn_SO"] / gs).fillna(facts["so_per_start"]).where(E["espn_W"].notna()))

    # NHL.com (skaters, points only): split with the player's goal share in ESPN or CBS
    n = public.nhlcom_points(refresh=refresh)
    n["playerId"] = match(left, n).reindex(n.index)
    N = n.dropna(subset=["playerId"]).astype({"playerId": int}).drop_duplicates("playerId").set_index("playerId").reindex(P.index)
    share = (E["espn_G"] / (E["espn_G"] + E["espn_A"])).fillna(C["cbs_G"] / (C["cbs_G"] + C["cbs_A"]))
    share = share.fillna(P["pos"].map(facts["goal_share"])).fillna(0.35)
    skater("nhl", N["nhlcom_PTS"] * share / gp, N["nhlcom_PTS"] * (1 - share) / gp, nan)

    # CBS: its own per-game rates (CBS gives every skater about 81 games)
    cgp = C["cbs_GP"].where(C["cbs_GP"] > 0)
    skater("cbs", C["cbs_G"] / cgp, C["cbs_A"] / cgp, C["cbs_GWG"] / cgp)
    cgs = C["cbs_GS"].where(C["cbs_GS"] > 0)
    goalie("cbs", C["cbs_W"] / cgs, C["cbs_OTL"] / cgs, C["cbs_SO"] / cgs)

    # HockeyBangers (skaters, per 82 games)
    names = hb_names if hb_names is not None else list(P.loc[sk, "name"])
    hb = others.hockeybangers(names, refresh=refresh if hb_refresh is None else hb_refresh)
    if len(hb):
        hb["k"] = hb["name"].map(norm)
        H = hb.drop_duplicates("k").set_index("k").reindex(P["k"])
        H.index = P.index
        skater("hb", H["hb_G82"] / 82, H["hb_A82"] / 82, nan)
    else:
        skater("hb", nan, nan, nan)
    for key in KEYS.values():
        for col in GOALIE_RATES:
            if f"{key}_{col}" not in out:
                out[f"{key}_{col}"] = np.nan
    return out


def rate_points(R: pd.DataFrame, pos: pd.Series, key: str, rules: dict | None = None) -> pd.Series:
    """League points per game (skaters) or per start (goalies) from one source's rates."""
    rules = rules or load_league()["scoring"]
    out = pd.Series(np.nan, index=R.index)
    for grp in ("F", "D"):
        r, m = rules[grp], pos == grp
        out[m] = (r["goal"] * R.loc[m, f"{key}_G"] + r["assist"] * R.loc[m, f"{key}_A"]
                  + r["gwg"] * R.loc[m, f"{key}_GWG"] + r["hat_trick"] * R.loc[m, f"{key}_HT"])
    r, m = rules["G"], pos == "G"
    out[m] = r["win"] * R.loc[m, f"{key}_W"] + r["otl"] * R.loc[m, f"{key}_OTL"] + r["shutout"] * R.loc[m, f"{key}_SO"]
    return out


def projections(people: pd.DataFrame, data: dict, hb_names: list[str] | None = None,
                refresh: bool = False) -> pd.DataFrame:
    """Full-season points per source: per-game rates times projected games (skaters) or starts (goalies)."""
    R = rates(people, data, hb_names, refresh)
    games = R["ext_starts"].where(people["pos"] == "G", R["ext_gp"])
    out = pd.DataFrame({"ext_gp": R["ext_gp"]}, index=R.index)
    for lab, col in SOURCES.items():
        out[col] = rate_points(R, people["pos"], KEYS[lab]) * games
    src = list(SOURCES.values())
    out["n_sources"] = out[src].notna().sum(axis=1)
    out["consensus"] = out[src].mean(axis=1)
    return out


def outcome_ratios(data: dict, pairs: int = 3, min_fp: float = 20.0) -> dict:
    """Real season-to-season change: FP in season N over FP in N-1 (per 82 games), by position,
    for players with at least `min_fp` in N-1. Players who played 0 games in N count as 0.
    Each position's ratios are rescaled to mean 1, so they add spread but do not move the average."""
    out = {}
    for key, pos_of in (("skaters", lambda d: d["pos"]), ("goalies", lambda d: pd.Series("G", index=d.index))):
        df = data[key]
        last = int(df.seasonId.max())
        rows = []
        for i in range(pairs):
            s = prev(last, i)
            a = df[df.seasonId == prev(s)].set_index("playerId")
            b = df[df.seasonId == s].set_index("playerId")["FP82"]
            a = a[a["FP82"] >= min_fp]
            active_next = set(df.loc[df.seasonId >= s, "playerId"])
            a = a[a.index.isin(active_next)]  # drop players who left the league
            rows.append(pd.DataFrame({"pos": pos_of(a), "ratio": b.reindex(a.index).fillna(0.0) / a["FP82"]}))
        r = pd.concat(rows)
        for p, g in r.groupby("pos"):
            v = g["ratio"].clip(upper=3).to_numpy()
            out[p] = v / v.mean()
    return out
