"""Live 2026-27 projection: tuned model + current rosters + manual inputs + public blend."""
import numpy as np
import pandas as pd

from . import dataset, params
from .config import load_league
from .fetch import dailyfaceoff, espn, nhl_api, public
from .models import marcel, rookies
from .names import match, norm
from .paths import MANUAL, PROCESSED
from .scoring import pos_group

SEASON = 20262027
AVG_OTL = 10.5  # league-average OT/SO losses per team-season, used to turn points into wins


# ---------- manual inputs ----------

def seed_team_totals(refresh: bool = False) -> pd.DataFrame:
    path = MANUAL / "team_point_totals.csv"
    if path.exists() and not refresh:
        return pd.read_csv(path)
    m = public.market_point_totals()
    tm = nhl_api.teams()
    names = dict(zip(tm["fullName"].map(norm), tm["team"]))
    m["team"] = m["team_name"].map(lambda n: names.get(norm(n)))
    m["source"] = "gambling911 (BetOnline opening numbers), fetched " + pd.Timestamp.today().strftime("%Y-%m-%d")
    out = m[["team", "team_name", "point_total", "source"]]
    out.to_csv(path, index=False)
    return out


def live_strength(data: dict, P: dict, league: dict) -> pd.DataFrame:
    ts = marcel.team_strength(data["teams"], SEASON, P["team_regress"], P.get("xg_team_w", 0.0))
    tot = seed_team_totals().set_index("team")["point_total"]
    market_win = ((tot - AVG_OTL) / 2) / 82
    w = float(league.get("market_weight", 0.75))
    ts["gd_win_pct"] = ts["exp_win_pct"]
    ts["market_win_pct"] = market_win.reindex(ts.index)
    ts["exp_win_pct"] = (w * ts["market_win_pct"] + (1 - w) * ts["gd_win_pct"]).fillna(ts["gd_win_pct"])
    return ts


def load_overrides() -> pd.DataFrame:
    path = MANUAL / "overrides.csv"
    if not path.exists():
        pd.DataFrame(columns=["playerId", "name", "proj_GP", "exclude", "note"]).to_csv(path, index=False)
    return pd.read_csv(path)


# ---------- helpers ----------

def roster_frame(refresh: bool, data: dict | None = None) -> pd.DataFrame:
    path = PROCESSED / "rosters_20262027.csv"
    if refresh or not path.exists():
        r = nhl_api.all_rosters(SEASON, refresh=refresh)
        r.to_csv(path, index=False)
    r = pd.read_csv(path).drop_duplicates("playerId", keep="last").set_index("playerId")
    r["off_roster"] = False
    if data is not None:
        r = pd.concat([r, off_roster_players(data, set(r.index), refresh)])
    r["pos_group"] = pos_group(r["pos"])
    return r


def off_roster_players(data: dict, on_roster: set, refresh: bool, min_fp: float = 15.0) -> pd.DataFrame:
    """Recent NHL players missing from the team roster lists but still listed with a
    current team (typically unsigned RFAs or long-term injured). Flagged for review."""
    parts = []
    for k in ("skaters", "goalies"):
        df = data[k]
        parts.append(df[df.seasonId >= 20242025].groupby("playerId").agg(name=("name", "last"), FP=("FP", "max")))
    cand = pd.concat(parts)
    cand = cand[~cand.index.isin(on_roster) & (cand.FP >= min_fp)]
    rows = []
    for pid, x in cand.iterrows():
        try:
            L = nhl_api.landing(int(pid), refresh=refresh)
        except Exception:
            continue
        if L.get("isActive") and L.get("currentTeamAbbrev"):
            rows.append({"playerId": int(pid), "name": x["name"], "pos": L.get("position"),
                         "team": L["currentTeamAbbrev"], "birthDate": L.get("birthDate"),
                         "roster_group": "off roster", "off_roster": True})
    return pd.DataFrame(rows).set_index("playerId") if rows else pd.DataFrame()


def daily_faceoff(roster: pd.DataFrame, refresh: bool) -> pd.DataFrame:
    df = dailyfaceoff.lines(refresh=refresh)
    left = roster.reset_index()[["playerId", "name", "team", "pos_group"]].set_index("playerId")
    df["pos_group"] = np.where(df["df_goalie"].notna(), "G",
                               np.where(df["df_line"].fillna("").str.startswith("d"), "D", "F"))
    m = match(left, df, pos_col="pos_group")
    df["playerId"] = m.reindex(df.index)
    df = df.dropna(subset=["playerId"]).astype({"playerId": int}).drop_duplicates("playerId")
    return df.set_index("playerId")[["df_line", "df_goalie", "df_pp", "df_ir", "df_injury", "df_updated"]]


def public_projections(roster: pd.DataFrame, refresh: bool) -> pd.DataFrame:
    left = roster.reset_index()[["playerId", "name", "team", "pos_group"]].set_index("playerId")
    e = espn.projections(refresh=refresh)
    e["pos_group"] = pos_group(e["pos"])
    e["playerId"] = match(left, e).reindex(e.index)
    e = e.dropna(subset=["playerId"]).astype({"playerId": int}).drop_duplicates("playerId").set_index("playerId")
    n = public.nhlcom_points(refresh=refresh)
    n["playerId"] = match(left, n).reindex(n.index)
    n = n.dropna(subset=["playerId"]).astype({"playerId": int}).drop_duplicates("playerId").set_index("playerId")
    cols = ["espn_G", "espn_A", "espn_GP", "espn_GS", "espn_W", "espn_OTL", "espn_SO", "pct_owned",
            "espn_rank", "espn_adp"]
    return e[cols].join(n[["nhlcom_PTS"]], how="outer")


def blend_public(proj: pd.DataFrame, pub: pd.DataFrame, weight: float) -> pd.DataFrame:
    """Blend per-game rates with the public average; games played stay ours.

    Skaters: goal and assist rates from ESPN (G/GP, A/GP) and NHL.com (points,
    split using our own goal share, assuming ESPN's GP or 80). Goalies: ESPN
    per-start W, OTL, SO. GWG and hat tricks scale with the blended goal rate.
    """
    out = proj.join(pub, how="left")
    if weight <= 0:
        return out
    sk = out["pos"].isin(["F", "D"])
    gp_pub = out["espn_GP"].where(out["espn_GP"] > 0, 80.0)
    r_g_espn = out["espn_G"] / gp_pub
    r_a_espn = out["espn_A"] / gp_pub
    g_share = (out["rate_G"] / (out["rate_G"] + out["rate_A"])).fillna(0.35)
    r_pts_nhl = out["nhlcom_PTS"] / gp_pub
    r_g_pub = pd.concat([r_g_espn, r_pts_nhl * g_share], axis=1).mean(axis=1)
    r_a_pub = pd.concat([r_a_espn, r_pts_nhl * (1 - g_share)], axis=1).mean(axis=1)
    for c, pubr in (("G", r_g_pub), ("A", r_a_pub)):
        has = sk & pubr.notna()
        new = out.loc[has, f"rate_{c}"] * (1 - weight) + pubr[has] * weight
        if c == "G":
            ratio = (new / out.loc[has, "rate_G"]).replace([np.inf, -np.inf], 1).fillna(1)
            out.loc[has, "rate_GWG"] *= ratio
            out.loc[has, "rate_HT"] *= ratio ** 2.5  # P(3+ goals) scales faster than the rate
        out.loc[has, f"rate_{c}"] = new
    g = (out["pos"] == "G") & (out["espn_GS"] > 0)
    for c in ("W", "OTL", "SO"):
        # ESPN omits some stats (often shutouts); blend only where it projects one.
        has = g & out[f"espn_{c}"].notna()
        pubr = out.loc[has, f"espn_{c}"] / out.loc[has, "espn_GS"]
        out.loc[has, f"rate_{c}"] = out.loc[has, f"rate_{c}"] * (1 - weight) + pubr * weight
    return out


def finalize_counts(out: pd.DataFrame, rules: dict) -> pd.DataFrame:
    sk = out["pos"].isin(["F", "D"])
    for c in ("G", "A", "GWG", "HT"):
        out.loc[sk, f"proj_{c}"] = out.loc[sk, f"rate_{c}"] * out.loc[sk, "proj_GP"]
    g = out["pos"] == "G"
    out.loc[g, "proj_GS"] = out.loc[g, "proj_GP"]
    for c in ("W", "OTL", "SO"):
        out.loc[g, f"proj_{c}"] = out.loc[g, f"rate_{c}"] * out.loc[g, "proj_GS"]
    f = rules
    fp = pd.Series(0.0, index=out.index)
    for grp in ("F", "D"):
        m = out["pos"] == grp
        r = f[grp]
        fp[m] = (r["goal"] * out.loc[m, "proj_G"] + r["assist"] * out.loc[m, "proj_A"]
                 + r["gwg"] * out.loc[m, "proj_GWG"] + r["hat_trick"] * out.loc[m, "proj_HT"])
    r = f["G"]
    fp[g] = r["win"] * out.loc[g, "proj_W"] + r["otl"] * out.loc[g, "proj_OTL"] + r["shutout"] * out.loc[g, "proj_SO"]
    out["proj_FP"] = fp
    return out


# ---------- main ----------

def build(refresh: bool = False) -> pd.DataFrame:
    league = load_league()
    P = params.load()
    data = dataset.load()
    roster = roster_frame(refresh, data)
    uni = set(roster.index)
    team = roster["team"]
    strength = live_strength(data, P, league)

    depth_path = MANUAL / "goalie_depth.csv"
    share_override = None
    if depth_path.exists():
        dep = pd.read_csv(depth_path)
        share_override = dep.set_index("playerId")["start_share"].dropna()

    sk = marcel.project_skaters(data["skaters"], SEASON, P, None, uni, team_override=team, strength=strength)
    gl = marcel.project_goalies(data["goalies"], SEASON, P, data["teams"], uni, share_override=share_override,
                                team_override=team, strength=strength)
    gl = adjust_goalie_team(gl, data, strength)
    proj = pd.concat([sk, gl])
    proj["source"] = "model"
    # Position from the current roster (skaters who switched F/D).
    proj["pos"] = roster["pos_group"].reindex(proj.index).fillna(proj["pos"])
    proj["name"] = roster["name"].reindex(proj.index).fillna(proj["name"])

    # Rookies and imports: no NHL history.
    dfo = daily_faceoff(roster, refresh)
    new = roster[~roster.index.isin(proj.index)]
    rk = rookies.project(new, data, P, strength, dfo, share_override)
    proj = pd.concat([proj, rk]).rename_axis("playerId")
    proj = proj.join(dfo, how="left")

    if not depth_path.exists():
        seed_goalie_depth(proj)
    else:
        append_new_goalies(proj, depth_path)
    # Keep each team's starts at or under 100% after manual edits.
    g = proj["pos"] == "G"
    tot = proj.loc[g, "start_share"].groupby(proj.loc[g, "team"]).transform("sum")
    scale = 1.0 / np.maximum(tot, 1.0)
    proj.loc[g, "start_share"] = proj.loc[g, "start_share"] * scale
    proj.loc[g, "proj_GP"] = proj.loc[g, "proj_GP"] * scale

    pub = public_projections(roster, refresh)
    rk_mask = proj["source"].eq("rookie")
    vet = blend_public(proj[~rk_mask], pub, float(league.get("public_blend_weight", 0.25)))
    rook = blend_public(proj[rk_mask], pub, float(league.get("rookie_public_weight", 0.5)))
    proj = pd.concat([vet, rook])

    # Starting on injured reserve per Daily Faceoff: default games lost (judgment, configurable).
    ir = proj["df_ir"].fillna(False).astype(bool)
    proj.loc[ir, "proj_GP"] = (proj.loc[ir, "proj_GP"] - float(league.get("ir_games_lost", 10))).clip(lower=0)

    ov = load_overrides()
    if len(ov):
        ov = ov.set_index("playerId")
        gp = ov["proj_GP"].dropna()
        proj.loc[proj.index.intersection(gp.index), "proj_GP"] = gp
        excl = ov.index[ov["exclude"].fillna(0).astype(int) == 1]
        proj = proj.drop(index=proj.index.intersection(excl))

    proj = finalize_counts(proj, league["scoring"])
    proj["team"] = team.reindex(proj.index).fillna(proj["team"])
    proj["age"] = proj["age"].fillna(rookies.age_from_roster(roster).reindex(proj.index))
    proj["last_team"] = last_teams(data).reindex(proj.index)
    proj["history"] = history_flags(data).reindex(proj.index)
    proj["off_roster"] = roster["off_roster"].reindex(proj.index).fillna(False).astype(bool)
    return proj.rename_axis("playerId")


ROLE_PRIOR = {"g1": 0.62, "g2": 0.30}


def adjust_goalie_team(gl: pd.DataFrame, data: dict, strength: pd.DataFrame) -> pd.DataFrame:
    """Scale per-start win rate by (2026-27 team strength / last season's team win rate).

    Judgment call, live only: the backtest can't evaluate it because there is
    no archive of preseason market totals. Clipped to +/-25%.
    """
    t = data["teams"][data["teams"].seasonId == 20252026].set_index("team")
    last_win = t["team_W"] / t["team_gp"]
    hist = data["goalies"][data["goalies"].seasonId == 20252026].set_index("playerId")["last_team"]
    old = hist.reindex(gl.index).map(last_win)
    new = gl["team"].replace({"ARI": "UTA"}).map(strength["exp_win_pct"])
    ratio = (new / old).clip(0.75, 1.25).fillna(1.0)
    gl = gl.copy()
    gl["rate_W"] = gl["rate_W"] * ratio
    gl["team_adj"] = ratio
    return gl


def append_new_goalies(proj: pd.DataFrame, path) -> None:
    dep = pd.read_csv(path)
    new = proj[(proj["pos"] == "G") & ~proj.index.isin(dep["playerId"])]
    if not len(new):
        return
    add = new.reset_index()[["playerId", "team", "name", "df_goalie"]].assign(
        model_share=new["start_share"].fillna(0.05).round(3).to_numpy(),
        start_share=new["start_share"].fillna(0.05).round(3).to_numpy())
    pd.concat([dep, add]).sort_values(["team", "start_share"], ascending=[True, False]).to_csv(path, index=False)
    print(f"goalie_depth.csv: added {', '.join(add['name'])}. Review their start shares.")


def seed_goalie_depth(proj: pd.DataFrame) -> None:
    """Seed the editable depth chart: half model share, half Daily Faceoff role."""
    g = proj[proj["pos"] == "G"].copy()
    g["model_share"] = g["start_share"].fillna(0.05).round(3)
    prior = g["df_goalie"].map(ROLE_PRIOR).fillna(0.08)
    share = 0.5 * g["model_share"] + 0.5 * prior
    tot = share.groupby(g["team"]).transform("sum")
    g["start_share"] = (share / np.maximum(tot, 1.0)).round(3)
    cols = ["team", "name", "df_goalie", "model_share", "start_share"]
    g = g.reset_index()[["playerId"] + cols].sort_values(["team", "model_share"], ascending=[True, False])
    g.to_csv(MANUAL / "goalie_depth.csv", index=False)


def last_teams(data: dict) -> pd.Series:
    parts = []
    for k in ("skaters", "goalies"):
        df = data[k].sort_values("seasonId")
        parts.append(df.groupby("playerId")["last_team"].last())
    s = pd.concat(parts)
    return s[~s.index.duplicated()]


def history_flags(data: dict) -> pd.Series:
    """'injury-prone' if under 80% of games in 2 of the last 3 seasons played."""
    sk = data["skaters"]
    h = sk[sk.seasonId >= 20232024]
    low = (h.assign(low=h["gp_frac"] < 0.8).groupby("playerId")["low"].sum() >= 2)
    return low.map({True: "injury-prone", False: ""})
