"""Rookies and imports: league-equivalency translation of pre-NHL scoring.

Translation factors (NHL goals/assists per game per league goal/assist per
game) are fitted on our own data: every skater whose first 30+ GP NHL season
started 2012-13 or later, paired with his previous season in another league.
They are shrunk toward published NHLe values where the sample is thin.

Games played for rookies cannot be backtested (it depends on making the team),
so it comes from the Daily Faceoff projected lineup, a judgment call:
  top-9 F / top-4 D slot -> 65 GP, 4th line / 3rd pair -> 50, not in lineup -> 12.
All rookies are flagged high uncertainty and get wider Monte Carlo intervals.
"""
import json

import numpy as np
import pandas as pd
from scipy.stats import poisson

from ..fetch import nhl_api
from ..history import prev
from ..paths import PROCESSED

GROUP = {
    "AHL": "AHL", "KHL": "KHL", "SHL": "SHL", "Sweden": "SHL", "Liiga": "Liiga", "Finland": "Liiga",
    "NL": "NL", "Swiss": "NL", "NLA": "NL", "DEL": "DEL", "Czechia": "Czech", "Czech": "Czech",
    "OHL": "OHL", "WHL": "WHL", "QMJHL": "QMJHL", "USHL": "USHL",
    "CCHA": "NCAA", "H-East": "NCAA", "WCHA": "NCAA", "ECAC": "NCAA", "NCHC": "NCAA", "Big Ten": "NCAA",
    "B1G": "NCAA", "Big-10": "NCAA", "Atlantic": "NCAA", "AHA": "NCAA", "Hockey East": "NCAA", "NCAA": "NCAA",
}
# Published NHLe (points per game), approximate consensus values; fallback only.
PUBLISHED = {"KHL": 0.77, "SHL": 0.57, "NL": 0.46, "Liiga": 0.44, "Czech": 0.47, "AHL": 0.39, "DEL": 0.37,
             "NCAA": 0.19, "OHL": 0.14, "WHL": 0.14, "QMJHL": 0.12, "USHL": 0.12}
PRIOR_N = 20  # games-equivalent weight of the published value in the shrinkage


def league_lines(pid: int) -> pd.DataFrame:
    try:
        d = nhl_api.landing(int(pid))
    except Exception:
        return pd.DataFrame()
    rows = [{"season": s["season"], "league": s["leagueAbbrev"], "GP": s.get("gamesPlayed", 0),
             "G": s.get("goals", 0), "A": s.get("assists", 0)}
            for s in d.get("seasonTotals", []) if s.get("gameTypeId") == 2 and s.get("leagueAbbrev") != "NHL"]
    df = pd.DataFrame(rows)
    if len(df):
        df["group"] = df["league"].map(GROUP)
        df = df.dropna(subset=["group"])
    return df


_fcache: dict = {}


def fit_factors(data: dict, refresh: bool = False, before: int | None = None) -> dict:
    """before: only use debut seasons earlier than this one (for backtests)."""
    path = PROCESSED / "nhle_factors.json"
    if before is None and path.exists() and not refresh:
        return json.loads(path.read_text())
    if before is not None and before in _fcache:
        return _fcache[before]
    sk = data["skaters"]
    reg = sk[sk.GP >= 30]
    first = reg.groupby("playerId").seasonId.min()
    first = first[first >= 20122013]
    if before is not None:
        first = first[first < before]
    rows = []
    for pid, s in first.items():
        lines = league_lines(pid)
        if not len(lines):
            continue
        p = lines[(lines.season == prev(s)) & (lines.GP >= 15)]
        if not len(p):
            continue
        p = p.sort_values("GP").iloc[-1]
        n = reg[(reg.playerId == pid) & (reg.seasonId == s)].iloc[0]
        rows.append({"group": p["group"], "pos": n["pos"], "lg_gpg": p["G"] / p["GP"], "lg_apg": p["A"] / p["GP"],
                     "nhl_G": n["G"], "nhl_A": n["A"], "nhl_GP": n["GP"]})
    df = pd.DataFrame(rows)
    out = {}
    for g, grp in df.groupby("group"):
        n = len(grp)
        fg = grp["nhl_G"].sum() / max((grp["lg_gpg"] * grp["nhl_GP"]).sum(), 1e-9)
        fa = grp["nhl_A"].sum() / max((grp["lg_apg"] * grp["nhl_GP"]).sum(), 1e-9)
        pub = PUBLISHED.get(g, 0.3)
        out[g] = {"n": n, "fit_G": fg, "fit_A": fa,
                  "G": (n * fg + PRIOR_N * pub) / (n + PRIOR_N), "A": (n * fa + PRIOR_N * pub) / (n + PRIOR_N)}
    for g, pub in PUBLISHED.items():
        out.setdefault(g, {"n": 0, "fit_G": None, "fit_A": None, "G": pub, "A": pub})
    if before is None:
        path.write_text(json.dumps(out, indent=2))
    else:
        _fcache[before] = out
    return out


def age_from_roster(roster: pd.DataFrame, season: int = 20262027) -> pd.Series:
    mid = pd.Timestamp(f"{season % 10000}-02-01")
    return (mid - pd.to_datetime(roster["birthDate"])).dt.days / 365.25


def lineup_gp(df_line) -> float:
    if not isinstance(df_line, str):
        return 12.0
    if df_line in ("f1", "f2", "f3", "d1", "d2"):
        return 65.0
    return 50.0


def project(new: pd.DataFrame, data: dict, P: dict, strength: pd.DataFrame, dfo: pd.DataFrame,
            share_override: pd.Series | None = None, season: int = 20262027,
            K: float | None = None, prior: float | None = None, factors: dict | None = None) -> pd.DataFrame:
    """new: roster rows (index playerId) with no NHL history."""
    K = P.get("rookie_K", 20.0) if K is None else K
    prior = P.get("rookie_prior", 0.6) if prior is None else prior
    factors = factors or fit_factors(data)
    sk_hist = data["skaters"]
    last = sk_hist[sk_hist.seasonId == prev(season)]
    mu = {c: (last.groupby("pos")[c].sum() / last.groupby("pos")["GP"].sum()) for c in ("G", "A")}
    fr = new["team"].replace({"ARI": "UTA"})
    rows = []
    for pid, r in new.iterrows():
        pos = r["pos_group"]
        base = {"name": r["name"], "pos": pos, "team": r["team"], "source": "rookie"}
        dl = dfo["df_line"].get(pid) if pid in dfo.index else None
        if pos == "G":
            share = share_override.get(pid, 0.05) if share_override is not None else 0.05
            last_g = data["goalies"][data["goalies"].seasonId == prev(season)]
            win = strength["exp_win_pct"].get(fr[pid], 0.5)
            base.update({"start_share": share, "proj_GP": 82 * share,
                         "rate_W": win * 0.95, "rate_OTL": last_g["OTL"].sum() / last_g["GS"].sum(),
                         "rate_SO": last_g["SO"].sum() / last_g["GS"].sum() * 0.8})
            rows.append(pd.Series(base, name=pid))
            continue
        lines = league_lines(pid)
        lines = lines[lines.season.isin([prev(season, 1), prev(season, 2)]) & (lines.GP >= 10)] if len(lines) else lines
        rg = ra = None
        if len(lines):
            w = np.where(lines.season == prev(season, 1), 2.0, 1.0) * lines.GP
            fg = lines["group"].map(lambda g: factors[g]["G"])
            fa = lines["group"].map(lambda g: factors[g]["A"])
            num_g = (w * fg * lines.G / lines.GP).sum()
            num_a = (w * fa * lines.A / lines.GP).sum()
            n_games = lines.GP.sum()
            prior_g, prior_a = prior * mu["G"][pos], prior * mu["A"][pos]
            rg = (num_g / w.sum() * n_games + K * prior_g) / (n_games + K)
            ra = (num_a / w.sum() * n_games + K * prior_a) / (n_games + K)
        if rg is None:
            rg, ra = 0.5 * mu["G"][pos], 0.5 * mu["A"][pos]
        win = strength["exp_win_pct"].get(fr[pid], 0.5)
        gf = strength["exp_gf_pg"].get(fr[pid], strength["exp_gf_pg"].mean())
        base.update({"proj_GP": lineup_gp(dl), "rate_G": rg, "rate_A": ra,
                     "rate_GWG": rg / gf * win * 0.91,
                     "rate_HT": P["ht_mult"] * poisson.sf(2, rg) if pos == "F" else 0.0})
        rows.append(pd.Series(base, name=pid))
    out = pd.DataFrame(rows)
    out["age"] = age_from_roster(new).reindex(out.index)
    return out
