"""B1: Marcel-style component projection.

Each scoring category is projected as (games played) x (per-game rate).
Rates are a weighted average of the last three seasons, shrunk toward the
position mean with a games-equivalent constant K, then age-adjusted.
Games played is a weighted average of past GP fractions shrunk toward a prior.
Goalies: start share x per-start W/OTL/SO rates.

Every refinement from the plan is a switch in `params`, default off, so the
backtest can compare each one to this baseline.
"""
import numpy as np
import pandas as pd
from scipy.stats import poisson

from ..history import age_in, latest, opening_team, prev, safe_div, weighted, wide_history
from ..scoring import fantasy_points

DEFAULT = {
    "w": (5.0, 3.0, 2.0),          # weights for seasons N-1, N-2, N-3
    "K": {"G": 40.0, "A": 40.0, "GWG": 80.0},   # shrinkage, in games
    "age_peak": 26.5,
    "age_young": 0.03,             # rate growth per year below peak
    "age_old": 0.03,               # rate decline per year above peak
    "gp_w": (5.0, 3.0, 2.0),       # GP weights for seasons N-1, N-2, N-3
    "gp_K": 1.0,                   # GP shrinkage, in seasons
    "gp_rate": 0.0,                # GP fraction gained per extra fantasy point per game vs position mean
    "gp_mu": {"F": 0.80, "D": 0.80},
    "gp_age": 0.0,                 # extra GP fraction lost per year over 30
    "ht_mult": 1.0,                # calibration on Poisson hat-trick probability
    # goalies
    "g_w": (5.0, 3.0, 2.0),        # start-share season weights
    "gr_w": None,                  # per-start rate weights (None = same as g_w)
    "gs_K": 1.0,                   # start-share shrinkage, in seasons
    "gs_mu": 0.30,
    "g_K": {"W": 60.0, "OTL": 60.0, "SO": 60.0},  # per-start rate shrinkage, in starts
    "g_team_norm": False,          # cap each team's projected start shares at 1.0
    "g_age": 0.0,                  # start share lost per year over 33
    # refinement switches (Phase 4), all off in B1
    "xg_weight": 0.0,              # blend goals with ixG in the goal-rate estimate
    "a1_weight": 1.0,              # weight of primary vs secondary assists (1 = plain assists)
    "gwg_team": False,             # GWG = team wins x share of team goals
    "g_team_wins": False,          # goalie W/OTL from team strength, not own history
    "team_regress": 0.5,           # regression of prior team goal diff toward 0
    # round-2 goalie switches (all off = current model)
    "gs_late_w": 0.0,              # weight of last-20-games start share in last season's share
    "so_model": False,             # shutouts from team shots against and regressed save %
    "so_c": 1.0,                   # calibration of the shutout formula
    "sv_K": 3000.0,                # save % shrinkage, in shots
    "w_team_mix": 0.0,             # weight of team strength + goalie quality in the win rate
    "w_gsax": 0.10,                # win % per GSAx per start in that mix
    # round-4 switches (all off = current model)
    "xg_team_w": 0.0,              # weight of team expected-goal differential in team strength
    "env_adj": 0.0,                # rescale past seasons to last season's league scoring (1 = fully)
}


def _age_curve(age, p):
    a = np.asarray(age, dtype=float)
    sl = p.get("age_slopes")
    if sl:
        # Piecewise-linear curve anchored at 25: slopes per year for <22, 22-25, 25-30, 30-33, 33+.
        g = (1.0 - sl["s1"] * np.maximum(0, 22 - a) - sl["s2"] * np.clip(25 - a, 0, 3)
             + sl["s3"] * np.clip(a - 25, 0, 5) - sl["s4"] * np.clip(a - 30, 0, 3) - sl["s5"] * np.maximum(0, a - 33))
        return np.clip(g, 0.2, None)
    peak = p["age_peak"]
    g = 1.0 + p["age_young"] * (np.minimum(a, peak) - peak) - p["age_old"] * (np.maximum(a, peak) - peak)
    return np.clip(g, 0.2, None)


def _gp_fraction(H, w, K, mu, prefix="GP", denom="season_games", n=3):
    vals = []
    for k in range(1, n + 1):
        f = (H[f"{prefix}_{k}"] / H[f"{denom}_{k}"]).clip(upper=1.0)
        missing_real_zero = (~H[f"present_{k}"]) & H[f"established_{k}"]
        f = f.where(H[f"present_{k}"], np.where(missing_real_zero, 0.0, np.nan))
        vals.append(pd.Series(f, index=H.index))
    num, den = weighted(vals, w)
    return (num + K * mu) / (den + K)


def team_strength(teams: pd.DataFrame, season: int, regress: float, xg_w: float = 0.0) -> pd.DataFrame:
    """Prior-season goal-differential-based expected win share per game (no leakage).

    xg_w: weight of the expected-goal differential (MoneyPuck) in the differential.
    """
    t = teams[teams.seasonId == prev(season)].copy()
    gd = (t["team_GF"] - t["team_GA"]) / t["team_gp"]
    if xg_w and "team_xGF" in t:
        gd = (1 - xg_w) * gd + xg_w * ((t["team_xGF"] - t["team_xGA"]) / t["team_gp"]).fillna(gd)
    gd_pg = gd * (1 - regress)
    gf_pg = (t["team_GF"] / t["team_gp"] - (t["team_GF"] / t["team_gp"]).mean()) * (1 - regress) + (
        t["team_GF"] / t["team_gp"]).mean()
    # Win% vs goal differential per game, fitted on history: ~0.5 + 0.16*GD/game.
    t["exp_win_pct"] = (0.5 + 0.16 * gd_pg).clip(0.25, 0.75)
    t["exp_otl_pct"] = (t["team_OTL"] / t["team_gp"]).mean()
    t["exp_gf_pg"] = gf_pg
    return t.set_index("franchise")[["exp_win_pct", "exp_otl_pct", "exp_gf_pg"]]


SK_COLS = ["GP", "G", "A", "GWG", "HT", "season_games", "A1", "A2", "mp_I_F_xGoals", "age", "PTS", "ppGoals", "SOG",
           "ppPoints", "toi_pg", "pp_toi_pg", "late_toi_pg", "late_pp_toi_pg", "late_gp", "late_gp_frac",
           "po_GP", "po_G", "po_A", "hits_pg", "weight", "draftOverall"]
SKATER_SWITCHES = {
    "w_young": None,        # season weights for players under young_age (None = same as w)
    "young_age": 25,
    "age_D": None,          # {"age_peak":..,"age_young":..,"age_old":..} for defensemen
    "prior_toi": False,     # shrink toward the mean of players with similar ice time
    "dp_growth": 0.0,       # extra yearly growth for top-10 draft picks under 24
    "po_weight": 0.0,       # weight of playoff games in the scoring rates
    "evpp": False,          # even strength and power play projected separately, per minute
    "K_ev": 600.0, "K_pp": 150.0,  # per-minute shrinkage, in minutes
    "min_late_w": 0.0,      # weight of the last 6 weeks in next season's minutes
    "min_w1": 1.0,          # weight of last season's minutes vs the season before
    "gf_bottom_up": False,  # team goals for GWG = sum of the opening roster's projected goals
    "gp_late": 0.0,         # GP fraction lost per missed share of the last 6 weeks
    "gp_hits": 0.0,         # GP fraction per extra hit per game (vs position mean)
    "gp_size": 0.0,         # GP fraction per 20 lb over 200
    "age_slopes": None,     # flexible age curve, see _age_curve
    "old_depth": 0.0,       # extra yearly decline after 32 for below-median scorers
    "young_mid": 0.0,       # extra growth for players 23 and under in the middle of the scoring range
    "team_ctx": 0.0,        # elasticity of scoring to teammates' talent (opening roster vs last season)
    "line_ctx": 0.0,        # LEAKY upper-bound test only: elasticity to actual season-N linemates
    # round 4
    "sh_model": None,       # goals = shots x regressed shooting %: "pos" (last 3 seasons) or "career"
    "K_sh": 400.0,          # shooting % shrinkage toward the position, in shots
    "gp_inj": 0.0,          # GP fraction lost per season in the last five under inj_thresh of games
    "inj_thresh": 0.6,
    "pp_team_r": None,      # team power-play time: regression toward the league (None = off)
}


def league_env(df: pd.DataFrame, season: int, cols: list[str], per: str) -> pd.DataFrame:
    """Factor per season before N that rescales its totals of `cols` to season N-1's league rate per `per`."""
    tot = df[df.seasonId < season].groupby("seasonId")[cols + [per]].sum()
    rate = tot[cols].div(tot[per], axis=0)
    return rate.loc[prev(season)] / rate if prev(season) in rate.index else rate * np.nan


def _env_adjust(H: pd.DataFrame, sk: pd.DataFrame, season: int, a: float) -> pd.DataFrame:
    """Rescale goals and assists of seasons N-2 and N-3 to last season's league level."""
    f = league_env(sk, season, ["G", "A"], "GP") ** a
    H = H.copy()
    for k in (2, 3):
        s = prev(season, k)
        if s not in f.index or f.loc[s].isna().any():
            continue
        fg, fa = f.loc[s, "G"], f.loc[s, "A"]
        pp_a = H[f"ppPoints_{k}"] - H[f"ppGoals_{k}"]
        for c in ("G", "ppGoals", "mp_I_F_xGoals", "GWG"):
            H[f"{c}_{k}"] = H[f"{c}_{k}"] * fg
        for c in ("A", "A1", "A2"):
            H[f"{c}_{k}"] = H[f"{c}_{k}"] * fa
        H[f"PTS_{k}"] = H[f"G_{k}"] + H[f"A_{k}"]
        H[f"ppPoints_{k}"] = H[f"ppGoals_{k}"] + pp_a * fa
    return H


def _shooting(H, W, p, last, sk, season):
    """Regressed shooting %: last three seasons (weighted) or whole career, shrunk toward the position."""
    mu = H["pos"].map(last.groupby("pos")["G"].sum() / last.groupby("pos")["SOG"].sum()).astype(float)
    if p["sh_model"] == "career":
        car = sk[sk.seasonId < season].groupby("playerId")[["G", "SOG"]].sum().reindex(H.index).fillna(0)
        g, n = car["G"], car["SOG"]
    else:
        g = sum(wk * H[f"G_{k}"].fillna(0) for wk, k in zip(W, (1, 2, 3)))
        n = sum(wk * H[f"SOG_{k}"].fillna(0) for wk, k in zip(W, (1, 2, 3)))
    return (g + p["K_sh"] * mu) / (n + p["K_sh"])


def _injury_seasons(sk: pd.DataFrame, season: int, idx: pd.Index, thresh: float) -> pd.Series:
    """Seasons in the last five in which the player appeared but played under `thresh` of the games."""
    H5 = wide_history(sk, season, ["GP", "season_games"], n=5).reindex(idx)
    return sum(((H5[f"GP_{k}"] / H5[f"season_games_{k}"]) < thresh).astype(float) for k in range(1, 6))


def _pp_team_mult(sk, teams, season, team, idx, r):
    """Next season's PP minutes x (opening team's PP time, regressed toward the league) / last team's PP time."""
    t = teams[teams.seasonId == prev(season)]
    tp = t.groupby("franchise")["team_pp_pg"].mean()
    lg = tp.mean()
    fr = lambda x: x.replace({"ARI": "UTA", "PHX": "UTA", "ATL": "WPG"})
    old = fr(sk[sk.seasonId == prev(season)].set_index("playerId")["last_team"]).reindex(idx).map(tp)
    new = fr(team.reindex(idx)).map(tp)
    mult = (lg + (1 - r) * (new - lg)) / old
    return mult.clip(0.5, 2.0).fillna(1.0)


def _age_curve_pos(age, pos, p):
    g = _age_curve(age, p)
    if p.get("age_D"):
        gd = _age_curve(age, {**p, **p["age_D"]})
        g = np.where(np.asarray(pos) == "D", gd, g)
    return g


def _evpp_rates(H, W, p, last, pp_mult=None):
    """Goals and assists per game as per-minute rates times projected minutes."""
    ks = (1, 2, 3)
    v = lambda c, k: H[f"{c}_{k}"].fillna(0)
    ev_min = [((H[f"toi_pg_{k}"] - H[f"pp_toi_pg_{k}"]) * H[f"GP_{k}"]).fillna(0) for k in ks]
    pp_min = [(H[f"pp_toi_pg_{k}"] * H[f"GP_{k}"]).fillna(0) for k in ks]
    comp = {
        "evG": [v("G", k) - v("ppGoals", k) for k in ks],
        "ppG": [v("ppGoals", k) for k in ks],
        "evA": [(v("PTS", k) - v("ppPoints", k)) - (v("G", k) - v("ppGoals", k)) for k in ks],
        "ppA": [v("ppPoints", k) - v("ppGoals", k) for k in ks],
    }
    lm_ev = ((last["toi_pg"] - last["pp_toi_pg"]) * last["GP"]).groupby(last["pos"]).sum()
    lm_pp = (last["pp_toi_pg"] * last["GP"]).groupby(last["pos"]).sum()
    lg = {
        "evG": (last["G"] - last["ppGoals"]).groupby(last["pos"]).sum() / lm_ev,
        "ppG": last["ppGoals"].groupby(last["pos"]).sum() / lm_pp,
        "evA": ((last["PTS"] - last["ppPoints"]) - (last["G"] - last["ppGoals"])).groupby(last["pos"]).sum() / lm_ev,
        "ppA": (last["ppPoints"] - last["ppGoals"]).groupby(last["pos"]).sum() / lm_pp,
    }
    per_min = {}
    for c, vals in comp.items():
        mins = ev_min if c.startswith("ev") else pp_min
        K = p["K_ev"] if c.startswith("ev") else p["K_pp"]
        mu = H["pos"].map(lg[c]).astype(float)
        per_min[c] = (sum(w * x for w, x in zip(W, vals)) + K * mu) / (sum(w * m for w, m in zip(W, mins)) + K)
    # Next season's minutes per game: last season, blended with the season before and the last 6 weeks.
    def minutes(kind):
        m1 = (H["toi_pg_1"] - H["pp_toi_pg_1"]) if kind == "ev" else H["pp_toi_pg_1"]
        m2 = (H["toi_pg_2"] - H["pp_toi_pg_2"]) if kind == "ev" else H["pp_toi_pg_2"]
        late = (H["late_toi_pg_1"] - H["late_pp_toi_pg_1"]) if kind == "ev" else H["late_pp_toi_pg_1"]
        ok_late = H["late_gp_1"].fillna(0) >= 5
        m = m1.where(~ok_late, (1 - p["min_late_w"]) * m1 + p["min_late_w"] * late)
        m = m.where(m2.isna(), p["min_w1"] * m + (1 - p["min_w1"]) * m2)
        return m.fillna(m2).fillna(0)
    ev_m, pp_m = minutes("ev"), minutes("pp")
    if pp_mult is not None:
        pp_m = pp_m * pp_mult
    return per_min["evG"] * ev_m + per_min["ppG"] * pp_m, per_min["evA"] * ev_m + per_min["ppA"] * pp_m


def project_skaters(sk: pd.DataFrame, season: int, p: dict, teams: pd.DataFrame | None = None,
                    universe: set | None = None, team_override: pd.Series | None = None,
                    strength: pd.DataFrame | None = None) -> pd.DataFrame:
    p = {**SKATER_SWITCHES, **p}
    cols = [c for c in SK_COLS if c in sk.columns]
    H = wide_history(sk, season, cols)
    for c in SK_COLS:
        for k in (1, 2, 3):
            if f"{c}_{k}" not in H:
                H[f"{c}_{k}"] = np.nan
    H = H.join(latest(sk, season, ["name", "pos", "birthDate"]))
    if universe is not None:
        H = H[H.index.isin(universe)]
    H["age"] = age_in(season, H["birthDate"])
    H["team"] = opening_team(sk, season).reindex(H.index)
    if team_override is not None:
        H["team"] = team_override.reindex(H.index).combine_first(H["team"])
    if p["env_adj"]:
        H = _env_adjust(H, sk, season, p["env_adj"])
    w = p["w"]
    young = H["age"] < p["young_age"]
    wy = p["w_young"]
    W = [pd.Series(np.where(young, wy[k], w[k]) if wy else float(w[k]), index=H.index) for k in range(3)]
    last = sk[sk.seasonId == prev(season)]

    out = pd.DataFrame(index=H.index)
    out["name"], out["pos"], out["team"], out["age"] = H["name"], H["pos"], H["team"], H["age"]

    # Games played
    mu_gp = H["pos"].map(p["gp_mu"]).astype(float)
    gpf = _gp_fraction(H, p["gp_w"], p["gp_K"], mu_gp)
    gpf = gpf - p["gp_age"] * np.maximum(0, H["age"] - 30)
    if p["gp_late"]:
        regular = H["GP_1"].fillna(0) >= 20
        miss = (1 - H["late_gp_frac_1"]).clip(0, 1).where(regular & H["late_gp_frac_1"].notna(), 0)
        gpf = gpf - p["gp_late"] * miss
    if p["gp_hits"]:
        mh = last.groupby("pos")["hits_pg"].median()
        gpf = gpf + p["gp_hits"] * (H["hits_pg_1"] - H["pos"].map(mh)).fillna(0)
    if p["gp_size"]:
        gpf = gpf + p["gp_size"] * ((H["weight_1"] - 200) / 20).fillna(0)
    if p["gp_inj"]:
        gpf = gpf - p["gp_inj"] * _injury_seasons(sk, season, H.index, p["inj_thresh"])
    out["gp_frac"] = gpf.clip(0, 1)

    # History age (GP-weighted) for the age adjustment
    ages = [H["age"] - k for k in range(1, 4)]
    gps = [H[f"GP_{k}"].fillna(0) for k in range(1, 4)]
    wa = sum(wk * g * a for wk, g, a in zip(W, gps, ages))
    wg = sum(wk * g for wk, g in zip(W, gps))
    age_hist = pd.Series(safe_div(wa, wg), index=H.index).where(wg > 0, H["age"] - 1)
    age_mult = _age_curve_pos(H["age"], H["pos"], p) / _age_curve_pos(age_hist, H["pos"], p)
    if p["dp_growth"]:
        top = (H["draftOverall_1"].fillna(H["draftOverall_2"]).fillna(999) <= 10)
        age_mult = age_mult * (1 + p["dp_growth"] * top * np.maximum(0, 24 - H["age"]) / 4)

    pw = p["po_weight"]
    gp_eff = [H[f"GP_{k}"].fillna(0) + pw * H[f"po_GP_{k}"].fillna(0) for k in range(1, 4)]
    gp_num = sum(wk * g for wk, g in zip(W, gp_eff))
    raw_num = {}
    for c in ["G", "A", "GWG"]:
        if c == "G" and p["sh_model"]:
            shp = _shooting(H, W, p, last, sk, season)
            vals = [H[f"SOG_{k}"].fillna(0) * shp for k in range(1, 4)]
        elif c == "G" and p["xg_weight"] > 0:
            vals = [(1 - p["xg_weight"]) * H[f"G_{k}"].fillna(0) + p["xg_weight"] * H[f"mp_I_F_xGoals_{k}"].fillna(H[f"G_{k}"]).fillna(0)
                    for k in range(1, 4)]
        elif c == "A" and p["a1_weight"] != 1.0:
            # Weighted assists rescaled so the league total is unchanged.
            aw = p["a1_weight"]
            share1 = last["A1"].sum() / max(last["A"].sum(), 1)
            scale = 1.0 / (aw * share1 + (1 - share1) * (2 - aw))
            vals = [scale * (aw * H[f"A1_{k}"].fillna(0) + (2 - aw) * H[f"A2_{k}"].fillna(0)) for k in range(1, 4)]
        else:
            vals = [H[f"{c}_{k}"].fillna(0) for k in range(1, 4)]
        if pw and c in ("G", "A"):
            vals = [x + pw * H[f"po_{c}_{k}"].fillna(0) for x, k in zip(vals, range(1, 4))]
        num = sum(wk * x for wk, x in zip(W, vals))
        raw_num[c] = (num, sum(wk * H[f"{c}_{k}"].fillna(0) for wk, k in zip(W, range(1, 4))))
        mu = (last.groupby("pos")[c].sum() / last.groupby("pos")["GP"].sum())
        mu_i = H["pos"].map(mu).astype(float)
        if p["prior_toi"] and c in ("G", "A"):
            reg = last[last.GP >= 20]
            mu_i = pd.Series(np.nan, index=H.index)
            for pos, g in reg.groupby("pos"):
                b, a0 = np.polyfit(g["toi_pg"], g[c] / g["GP"], 1)
                m = H["pos"] == pos
                mu_i[m] = (a0 + b * H.loc[m, "toi_pg_1"]).clip(lower=0)
            mu_i = mu_i.fillna(H["pos"].map(mu).astype(float))
        K = p["K"][c]
        rate = (num + K * mu_i) / (gp_num + K)
        out[f"rate_{c}"] = rate

    if p["evpp"]:
        pp_mult = None
        if p["pp_team_r"] is not None and teams is not None and "team_pp_pg" in teams:
            pp_mult = _pp_team_mult(sk, teams, season, H["team"], H.index, p["pp_team_r"])
        rg, ra = _evpp_rates(H, W, p, last, pp_mult)
        # Keep the goal (xG) and assist (primary) adjustments as ratios on top.
        adj_g = pd.Series(safe_div(raw_num["G"][0], raw_num["G"][1]), index=H.index).where(raw_num["G"][1] > 0, 1.0)
        adj_a = pd.Series(safe_div(raw_num["A"][0], raw_num["A"][1]), index=H.index).where(raw_num["A"][1] > 0, 1.0)
        has = H["toi_pg_1"].notna() | H["toi_pg_2"].notna()
        out.loc[has, "rate_G"] = (rg * adj_g)[has]
        out.loc[has, "rate_A"] = (ra * adj_a)[has]
    if p["old_depth"] or p["young_mid"]:
        fp_rate = np.where(out["pos"] == "D", 2, 1) * out["rate_G"] + out["rate_A"]
        rk = pd.Series(fp_rate, index=out.index).groupby(out["pos"]).rank(pct=True)
        if p["old_depth"]:
            depth = ((0.5 - rk) / 0.5).clip(0, 1)
            age_mult = age_mult * (1 - p["old_depth"] * depth * np.maximum(0, H["age"] - 32))
        if p["young_mid"]:
            mid = (1 - (rk - 0.4).abs() / 0.3).clip(0, 1)  # peaks around the 40th percentile
            age_mult = age_mult * (1 + p["young_mid"] * mid * (H["age"] <= 23))
    if p["team_ctx"] or p["line_ctx"]:
        from ..teammates import line_context, team_context
        if p["team_ctx"]:
            ratio = team_context(sk, season, H["team"]).reindex(H.index).fillna(1.0).clip(0.7, 1.4)
            age_mult = age_mult * ratio ** p["team_ctx"]
        if p["line_ctx"]:
            ratio = line_context(sk, season).reindex(H.index).fillna(1.0).clip(0.6, 1.6)
            age_mult = age_mult * ratio ** p["line_ctx"]
    out["rate_G"] = out["rate_G"] * age_mult
    out["rate_A"] = out["rate_A"] * age_mult

    if p["gp_rate"]:
        fp_rate = np.where(out["pos"] == "D", 2, 1) * out["rate_G"] + out["rate_A"]
        dev = fp_rate - pd.Series(fp_rate, index=out.index).groupby(out["pos"]).transform("mean")
        out["gp_frac"] = (out["gp_frac"] + p["gp_rate"] * dev).clip(0, 1)
    out["proj_GP"] = 82 * out["gp_frac"]

    if p["gwg_team"] and (teams is not None or strength is not None):
        ts = strength if strength is not None else team_strength(teams, season, p["team_regress"], p["xg_team_w"])
        fr = out["team"].replace({"ARI": "UTA", "PHX": "UTA", "ATL": "WPG"})
        win_pct = fr.map(ts["exp_win_pct"]).fillna(0.5)
        gf_pg = fr.map(ts["exp_gf_pg"]).fillna(ts["exp_gf_pg"].mean())
        if p["gf_bottom_up"]:
            tg = (out["rate_G"] * out["proj_GP"]).groupby(fr).sum() / 82
            tg = tg * ts["exp_gf_pg"].mean() / tg.mean()  # rookies are missing: keep the league level
            gf_pg = fr.map(tg).fillna(gf_pg)
        # Share of team goals while in the lineup, times team non-shootout wins per game.
        so_share = 0.09
        out["rate_GWG"] = out["rate_G"] / gf_pg * win_pct * (1 - so_share)

    lam = out["rate_G"].clip(lower=0)
    out["rate_HT"] = np.where(out["pos"] == "F", p["ht_mult"] * poisson.sf(2, lam), 0.0)

    for c in ["G", "A", "GWG", "HT"]:
        out[f"proj_{c}"] = out[f"rate_{c}"] * out["proj_GP"]
    tmp = out.rename(columns={"proj_G": "G", "proj_A": "A", "proj_GWG": "GWG", "proj_HT": "HT"})
    out["proj_FP"] = fantasy_points(tmp)
    return out


def project_goalies(gl: pd.DataFrame, season: int, p: dict, teams: pd.DataFrame | None = None,
                    universe: set | None = None, share_override: pd.Series | None = None,
                    team_override: pd.Series | None = None, strength: pd.DataFrame | None = None,
                    share_model: pd.Series | None = None) -> pd.DataFrame:
    cols = ["GP", "GS", "W", "OTL", "SO", "season_games", "gsax", "shotsAgainst", "goalsAgainst", "late_share"]
    cols = [c for c in cols if c in gl.columns]
    H = wide_history(gl, season, cols)
    H = H.join(latest(gl, season, ["name", "birthDate"]))
    if universe is not None:
        H = H[H.index.isin(universe)]
    H["age"] = age_in(season, H["birthDate"])
    H["team"] = opening_team(gl, season).reindex(H.index)
    if team_override is not None:
        H["team"] = team_override.reindex(H.index).combine_first(H["team"])
    w = p["g_w"]
    last = gl[gl.seasonId == prev(season)]

    out = pd.DataFrame(index=H.index)
    out["name"], out["pos"], out["team"], out["age"] = H["name"], "G", H["team"], H["age"]
    if p.get("gs_late_w") and "late_share_1" in H:
        a = p["gs_late_w"]
        full = H["GS_1"] / H["season_games_1"]
        blend = (1 - a) * full + a * H["late_share_1"].fillna(full)
        H["GS_1"] = (blend * H["season_games_1"]).where(H["GS_1"].notna())
    share = _gp_fraction(H, w, p["gs_K"], p["gs_mu"], prefix="GS")
    share = share * (1 - p["g_age"] * np.maximum(0, H["age"] - 33))
    if share_model is not None:
        share = share_model.reindex(H.index).combine_first(share)
    share = share.clip(0, 0.9)
    if p["g_team_norm"]:
        tot = share.groupby(out["team"]).transform("sum")
        share = share / np.maximum(tot, 1.0)
    if share_override is not None:
        share = share_override.reindex(H.index).combine_first(share)
    out["start_share"] = share
    out["proj_GS"] = 82 * share
    out["proj_GP"] = out["proj_GS"]

    wr = tuple(p["gr_w"]) if p.get("gr_w") else w
    gs_num = sum(wk * H[f"GS_{k}"].fillna(0) for k, wk in enumerate(wr, 1))
    for c in ["W", "OTL", "SO"]:
        num = sum(wk * H[f"{c}_{k}"].fillna(0) for k, wk in enumerate(wr, 1))
        mu = last[c].sum() / max(last["GS"].sum(), 1)
        K = p["g_K"][c]
        out[f"rate_{c}"] = (num + K * mu) / (gs_num + K)

    if p["g_team_wins"] and (teams is not None or strength is not None):
        ts = strength if strength is not None else team_strength(teams, season, p["team_regress"], p["xg_team_w"])
        fr = out["team"].replace({"ARI": "UTA", "PHX": "UTA", "ATL": "WPG"})
        team_w = fr.map(ts["exp_win_pct"]).fillna(0.5)
        # Goalie-specific edge from regressed GSAx per start, ~0.01 win% per 0.1 GSAx/start.
        gsax_num = sum(wk * H[f"gsax_{k}"].fillna(0) for k, wk in enumerate(wr, 1))
        gsax_ps = gsax_num / (gs_num + 80.0)
        out["rate_W"] = (team_w + 0.10 * gsax_ps).clip(0.25, 0.75)
        out["rate_OTL"] = fr.map(ts["exp_otl_pct"]).fillna(last["OTL"].sum() / last["GS"].sum())

    if (p.get("so_model") or p.get("w_team_mix")) and teams is not None or strength is not None and p.get("w_team_mix"):
        fr = out["team"].replace({"ARI": "UTA", "PHX": "UTA", "ATL": "WPG"})
        # Regressed save % from the last three seasons.
        sa = sum(wk * H[f"shotsAgainst_{k}"].fillna(0) for k, wk in enumerate((3, 2, 1), 1))
        genv = pd.Series(1.0, index=[1, 2, 3])
        if p.get("env_adj"):
            f = league_env(gl, season, ["goalsAgainst"], "shotsAgainst")["goalsAgainst"] ** p["env_adj"]
            genv = pd.Series({k: f.get(prev(season, k), 1.0) for k in (1, 2, 3)}).fillna(1.0)
        ga = sum(wk * genv[k] * H[f"goalsAgainst_{k}"].fillna(0) for k, wk in enumerate((3, 2, 1), 1))
        lg_sv = 1 - last["goalsAgainst"].sum() / max(last["shotsAgainst"].sum(), 1)
        sv = (sa - ga + p["sv_K"] * lg_sv) / (sa + p["sv_K"])
        if p.get("so_model") and teams is not None:
            tprev = teams[teams.seasonId == prev(season)].set_index("franchise")["team_SA_pg"]
            sa_pg = fr.map(tprev).fillna(tprev.mean())
            out["rate_SO"] = p["so_c"] * np.exp(-sa_pg * (1 - sv))
        if p.get("w_team_mix"):
            ts = strength if strength is not None else team_strength(teams, season, p["team_regress"], p["xg_team_w"])
            gsax_num = sum(wk * H[f"gsax_{k}"].fillna(0) for k, wk in enumerate((3, 2, 1), 1))
            gsax_ps = gsax_num / (sum(wk * H[f"GS_{k}"].fillna(0) for k, wk in enumerate((3, 2, 1), 1)) + 60.0)
            team_w = fr.map(ts["exp_win_pct"]).fillna(0.5) + p["w_gsax"] * gsax_ps
            out["rate_W"] = (1 - p["w_team_mix"]) * out["rate_W"] + p["w_team_mix"] * team_w.clip(0.25, 0.75)

    for c in ["W", "OTL", "SO"]:
        out[f"proj_{c}"] = out[f"rate_{c}"] * out["proj_GS"]
    tmp = out.rename(columns={"proj_W": "W", "proj_OTL": "OTL", "proj_SO": "SO"})
    out["proj_FP"] = fantasy_points(tmp)
    return out


def project(data: dict, season: int, params: dict | None = None, universe: set | None = None) -> pd.DataFrame:
    p = {**DEFAULT, **(params or {})}
    a = project_skaters(data["skaters"], season, p, data["teams"], universe)
    sm = None
    if p.get("gs_regression"):
        from .goalie_share import predict
        sm = predict(data, season, universe if universe is not None else set(data["goalies"].playerId))
    b = project_goalies(data["goalies"], season, p, data["teams"], universe, share_model=sm)
    return pd.concat([a, b]).rename_axis("playerId")
