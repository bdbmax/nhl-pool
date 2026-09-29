"""Daily update of the pool website: real points, standings, odds, history and weekly awards.

  uv run python -m nhlpool.daily                 # today's update -> site/data/pool.json, data/history/<date>.json
  uv run python -m nhlpool.daily --no-refresh    # reuse cached projections and player pages (quick local run)
  uv run python -m nhlpool.daily --season 20252026 --as-of 2026-01-15 --out /tmp/replay
                                                 # replay: last season's real stats up to a date (a test)

Runs every morning at 5:30 (Toronto) from GitHub Actions (.github/workflows/daily.yml).
Nothing here uses our own model: projections come from ESPN, NHL.com, CBS and HockeyBangers
(external.py), real stats from the NHL stats API, injuries from ESPN and Daily Faceoff.

1. Real points so far: season-to-date NHL stats (games up to yesterday), league scoring.
2. Rest of season, per player and per source:
   - each source becomes per-game rates (G, A, GWG, hat tricks; goalies W, OTL, SO per start),
   - each rate is updated with the player's real rate this season, weighted by games played:
       rate = (K x source_rate + GP x real_rate) / (K + GP),  K = 40 games (config: daily.real_weight_games)
   - games left = his NHL team's games left x availability (source games / season length),
     minus expected absences (IR 10, Out 3, Day-to-day 1, Suspended 3),
   - goalies: starts left = team games left x start share, the source's share updated with his
     real share of his team's games (weight 20 team games).
3. Odds: 20,000 simulated seasons. Final total = real points (fixed) + rest of season x surprise,
   with random source weights; the season-to-season surprise shrinks with sqrt(share of season left).
4. Safety checks (see checks()); if one fails nothing is written and yesterday's site stays up.
"""
import argparse
import json
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from . import dataset, external, ids, site_export
from .config import load_league
from .fetch import dailyfaceoff, espn, nhl_api, others, public
from .paths import ROOT
from .scoring import fantasy_points, pos_group

POOL = ROOT / "data" / "pool_2026"
HISTORY = ROOT / "data" / "history"
SEASON = 20262027
TEAMS, ROUNDS = 12, 16
COUNTED = {"F": 6, "D": 4, "G": 1}
DRAFTED = {"F": 8, "D": 6, "G": 2}
DEFAULTS = {
    "real_weight_games": 40,        # games of real play that count as much as the sources' projection
    "goalie_share_weight": 20,      # team games of real starts that count as much as the projected share
    "absence_games": {"IR": 10, "Out": 3, "Day-to-day": 1, "Suspended": 3},
    "sims": 20000,
    "late_round": 9,                # "Pick de la semaine": rounds 9 to 16
    "drop_tolerance": 2,            # stat corrections can take a point or two back; more than that fails
}
N_CANDIDATES = 60                   # undrafted players looked at for "the forgotten"
# The draft file uses ESPN's short codes for four teams; the NHL's own codes are used everywhere else.
TEAM_ALIAS = {"TB": "TBL", "NJ": "NJD", "LA": "LAK", "SJ": "SJS"}


def settings() -> dict:
    return {**DEFAULTS, **(load_league().get("daily") or {})}


def toronto_today() -> date:
    return datetime.now(ZoneInfo("America/Toronto")).date()


# --- Inputs -------------------------------------------------------------------------------

def load_draft() -> pd.DataFrame:
    """The 192 picks with NHL ids (draft_ids.csv pins the ids, checked against NHL names)."""
    D = pd.read_csv(POOL / "draft_results.csv", dtype={"pick": str})
    I = pd.read_csv(POOL / "draft_ids.csv", dtype={"pick": str})
    D = D.merge(I[["manager", "pick", "playerId", "espn_id", "df_id"]], on=["manager", "pick"], how="left", validate="1:1")
    D["round"] = D["pick"].str.split(".").str[0].astype(int)
    D["pick_in_round"] = D["pick"].str.split(".").str[1].astype(int)
    D["overall"] = (D["round"] - 1) * TEAMS + D["pick_in_round"]
    D["manager_id"] = D["manager"].map(D[D["round"] == 1].set_index("manager")["pick_in_round"])
    return D


def team_games(season: int, as_of: str, refresh: bool = True) -> tuple[pd.DataFrame, dict]:
    """Games played, total and left per NHL team, and league totals for the reconciliation check."""
    rows, seen, finished = [], {}, set()
    for team in nhl_api.current_team_abbrevs():
        games = nhl_api.schedule(team, season, refresh=refresh)
        done = [g for g in games if g["gameDate"] <= as_of and g.get("gameState") in ("OFF", "FINAL")]
        rows.append({"team": team, "played": len(done), "total": len(games),
                     "dates": sorted(g["gameDate"] for g in done),
                     "all_dates": sorted(g["gameDate"] for g in games)})
        finished.update(g["id"] for g in done if g["gameDate"] == as_of)
        for g in done:
            so = (g.get("gameOutcome") or {}).get("lastPeriodType") == "SO"
            # The shootout winner gets one goal on the scoreboard that no skater is credited with.
            seen[g["id"]] = g["awayTeam"].get("score", 0) + g["homeTeam"].get("score", 0) - int(so)
    T = pd.DataFrame(rows).set_index("team")
    T["left"] = T["total"] - T["played"]
    # finished_on_as_of: games of the as_of day that are over (the evening update counts only those).
    return T, {"games": len(seen), "goals": int(sum(seen.values())), "finished_on_as_of": finished}


STAT_COLS = ["name", "pos", "GP", "G", "A", "GWG", "HT", "GS", "W", "OTL", "SO"]


def _stat_frame(sk: pd.DataFrame, gl: pd.DataFrame, ht: pd.Series) -> pd.DataFrame:
    """NHL skater and goalie summary rows (one per player) -> our columns. ht: hat tricks per playerId."""
    parts = []
    if len(sk):
        s = pd.DataFrame({"playerId": sk["playerId"], "name": sk["skaterFullName"], "pos": pos_group(sk["positionCode"]),
                          "GP": sk["gamesPlayed"], "G": sk["goals"], "A": sk["assists"], "GWG": sk["gameWinningGoals"]})
        s["HT"] = s["playerId"].map(ht).fillna(0)
        parts.append(s)
    if len(gl):
        parts.append(pd.DataFrame({"playerId": gl["playerId"], "name": gl["goalieFullName"], "pos": "G",
                                   "GP": gl["gamesPlayed"], "GS": gl["gamesStarted"], "W": gl["wins"],
                                   "OTL": gl["otLosses"], "SO": gl["shutouts"]}))
    R = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=["playerId"] + STAT_COLS)
    R = R.drop_duplicates("playerId").set_index("playerId").reindex(columns=STAT_COLS)
    R[STAT_COLS[2:]] = R[STAT_COLS[2:]].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    return R


def _per_player(rows: pd.DataFrame, name_col: str) -> pd.DataFrame:
    """Per-game rows -> one summed row per player (keeps name and position)."""
    if not len(rows):
        return rows
    keep = [c for c in (name_col, "positionCode") if c in rows]
    num = [c for c in rows.columns if c not in keep + ["playerId"] and pd.api.types.is_numeric_dtype(rows[c])]
    return rows.groupby("playerId").agg({**{c: "first" for c in keep}, **{c: "sum" for c in num}}).reset_index()


def real_stats(season: int, as_of: str, finished_today: set | None = None) -> pd.DataFrame:
    """Season-to-date counting stats and league points, one row per player (index playerId).

    finished_today: the evening update. as_of is today; games up to yesterday come from the season
    totals and today's games count only if they are over (game ids from the schedule), so a game
    still in progress never half-counts."""
    if finished_today is None:
        ht = nhl_api.hat_tricks_to_date(season, as_of)
        R = _stat_frame(nhl_api.skaters_to_date(season, as_of), nhl_api.goalies_to_date(season, as_of),
                        ht.groupby("playerId").size() if len(ht) else pd.Series(dtype=float))
    else:
        yesterday = (date.fromisoformat(as_of) - timedelta(days=1)).isoformat()
        base = real_stats(season, yesterday)
        sk = nhl_api.skater_games_on(season, as_of)
        sk = sk[sk["gameId"].isin(finished_today)] if len(sk) else sk
        gl = nhl_api.goalie_games_to_date(season, as_of)
        gl = gl[gl["gameId"].isin(finished_today)] if len(gl) else gl
        ht = sk.loc[sk["goals"] >= 3].groupby("playerId").size() if len(sk) else pd.Series(dtype=float)
        tonight = _stat_frame(_per_player(sk, "skaterFullName"), _per_player(gl, "goalieFullName"), ht)
        R = base.reindex(base.index.union(tonight.index))
        for c in ("name", "pos"):
            R[c] = R[c].fillna(tonight[c].reindex(R.index))
        num = STAT_COLS[2:]
        R[num] = R[num].fillna(0.0).add(tonight[num].reindex(R.index).fillna(0.0))
    R["FP"] = fantasy_points(R) if len(R) else pd.Series(dtype=float)
    return R


def goalie_team_starts(G: pd.DataFrame, T: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
    """Starts with his current team, and that team's games that count, per goalie (G: index playerId; nhl_team).

    A goalie who played only for his current team: all his team's games. A goalie who also played
    for another team this season (traded, claimed): only his new team's games since his first game
    with them, so 20 starts elsewhere do not look like a starting job on his new team. Before his
    first game with the new team the window is 0 games and his projected share stands alone."""
    out = pd.DataFrame({"starts": 0.0, "team_games": 0.0}, index=G.index)
    for pid, team in G["nhl_team"].items():
        rows = games[games["playerId"] == pid] if len(games) else games
        dates = T["dates"].get(team, [])
        mine = rows[rows["teamAbbrev"] == team] if len(rows) else rows
        out.loc[pid, "starts"] = float(mine["gamesStarted"].sum()) if len(mine) else 0.0
        if len(rows) and set(rows["teamAbbrev"]) - {team}:
            first = mine["gameDate"].min() if len(mine) else None
            out.loc[pid, "team_games"] = float(sum(d >= first for d in dates)) if first else 0.0
        else:
            out.loc[pid, "team_games"] = float(len(dates))
    return out


def refresh_sources(refresh: bool) -> dict:
    """Re-download ESPN, CBS, NHL.com and Daily Faceoff. On failure use the cached copy (if any)."""
    status = {}
    for name, fn in (("ESPN", espn.projections), ("CBS", others.cbs), ("NHL.com", public.nhlcom_points),
                     ("Daily Faceoff", dailyfaceoff.lines)):
        try:
            fn(refresh=refresh)
            status[name] = "fresh" if refresh else "cached"
        except Exception as e:
            print(f"WARNING {name} download failed ({type(e).__name__}: {e}); using the cached copy")
            fn(refresh=False)  # raises if there is no cached copy: the job stops
            status[name] = "cached"
    return status


# --- Projection ---------------------------------------------------------------------------

def blend(source: pd.Series, real_total: pd.Series, n: pd.Series, k: float) -> pd.Series:
    """Source rate updated with the real rate: (k x source + n x real/n) / (k + n) = (k x source + real) / (k + n)."""
    return (k * source + real_total) / (k + n)


def games_left(pos: pd.Series, ext_gp: pd.Series, ext_starts: pd.Series, horizon: float, left: pd.Series,
               played: pd.Series, gs: pd.Series, injury: pd.Series, cfg: dict) -> pd.Series:
    """Skaters: team games left x availability - absence. Goalies: (team games left - absence) x start share."""
    absence = injury.map(cfg["absence_games"]).fillna(0.0)
    avail = (ext_gp / horizon).clip(0, 1)
    skater = (left * avail - absence).clip(lower=0)
    src_share = (ext_starts / horizon).clip(0, 1).fillna(0.0)
    real_share = (gs / played.where(played > 0)).fillna(0.0).clip(0, 1)
    kg = cfg["goalie_share_weight"]
    share = (kg * src_share + played * real_share) / (kg + played)
    goalie = (left - absence).clip(lower=0) * share
    return goalie.where(pos == "G", skater)


def project(P: pd.DataFrame, R: pd.DataFrame, real: pd.DataFrame, T: pd.DataFrame, cfg: dict,
            goalie_games: pd.DataFrame | None = None) -> pd.DataFrame:
    """Rest-of-season points per source for the players in P (index playerId; pos, nhl_team, injury).
    goalie_games: every goalie appearance so far (for start shares with the current team).

    Returns games_left, ppg (consensus points per team game), ros_{src} and ros (consensus)."""
    rules = load_league()["scoring"]
    k = cfg["real_weight_games"]
    stats = ["GP", "G", "A", "GWG", "HT", "GS", "W", "OTL", "SO"]
    rl = real.reindex(P.index)[stats].astype(float).fillna(0.0)
    team = T.reindex(P["nhl_team"].values)
    left = pd.Series(team["left"].fillna(0).to_numpy(), index=P.index)
    played = pd.Series(team["played"].fillna(0).to_numpy(), index=P.index)
    horizon = R.attrs.get("horizon", 82.0)
    goalie = P["pos"] == "G"
    # Start share: his starts with his current team over that team's games (see goalie_team_starts).
    share_gs, share_games = rl["GS"].copy(), played.copy()
    if goalie.any():
        w = goalie_team_starts(P[goalie], T, goalie_games if goalie_games is not None else pd.DataFrame())
        share_gs[goalie], share_games[goalie] = w["starts"], w["team_games"]
    gl = games_left(P["pos"], R["ext_gp"], R["ext_starts"], horizon, left, share_games, share_gs, P["injury"], cfg)
    n = rl["GS"].where(goalie, rl["GP"])
    out = pd.DataFrame({"games_left": gl}, index=P.index)
    per = {}
    for key in external.KEYS.values():
        B = pd.DataFrame({f"{key}_{c}": blend(R[f"{key}_{c}"], rl[c], n, k)
                          for c in external.SKATER_RATES + external.GOALIE_RATES}, index=P.index)
        per[key] = external.rate_points(B, P["pos"], key, rules)  # per game (skaters) or per start (goalies)
        out[f"ros_{key}"] = per[key] * gl
    out["ros"] = out[[f"ros_{key}" for key in per]].mean(axis=1)
    # Points per team game, for the "Malchance" award (what an absent player would have scored).
    absence = P["injury"].map(cfg["absence_games"]).fillna(0.0)
    share = (gl / (left - absence).clip(lower=1)).where(goalie, 1.0)
    out["ppg"] = pd.DataFrame(per).mean(axis=1).fillna(0.0) * share
    return out


def fill_missing(proj: pd.DataFrame, D: pd.DataFrame, people: pd.DataFrame, T: pd.DataFrame,
                 previous: dict | None, cfg: dict) -> pd.DataFrame:
    """A drafted player no source projects today (dropped from ESPN and CBS, say) keeps yesterday's
    points per game instead of stopping the update."""
    ids_ = D["playerId"]
    miss = ids_[proj.loc[ids_, "ros"].isna().to_numpy()]
    if not len(miss) or not previous:
        return proj
    proj = proj.copy()
    for pid in miss:
        entry = previous["players"].get(str(pid)) or [0, 0, None, 0.0, 0]
        ppg = entry[3]
        if people.loc[pid, "pos"] == "G":
            left = T["left"].get(people.loc[pid, "nhl_team"], 0)
            games = max(0.0, left - cfg["absence_games"].get(people.loc[pid, "injury"], 0))
            if len(entry) >= 7:  # yesterday's share of his team's games: his starts left
                proj.loc[pid, "games_left"] = entry[6] * games
        else:
            games = proj.loc[pid, "games_left"]
        proj.loc[pid, "ros"] = ppg * games
        print(f"WARNING no source projects {people.loc[pid, 'name']} today; using yesterday's pace ({ppg:.2f}/game)")
    return proj


# --- Odds ---------------------------------------------------------------------------------

def best_ball(D: pd.DataFrame, pts: pd.Series) -> pd.Series:
    """Best 6 F + 4 D + 1 G per manager."""
    x = D.assign(v=D["playerId"].map(pts).fillna(0.0))
    return pd.Series({m: sum(t.loc[t.pos == p, "v"].nlargest(n).sum() for p, n in COUNTED.items())
                      for m, t in x.groupby("manager_id")})


def simulate(D: pd.DataFrame, P: pd.DataFrame, proj: pd.DataFrame, real_fp: pd.Series, frac_left: pd.Series,
             ratios: dict, n_sims: int, seed: int = 2026) -> pd.DataFrame:
    """Final best-ball totals, managers x sims. The same seed every day keeps day-to-day moves real."""
    rng = np.random.default_rng(seed)
    ids_ = D["playerId"].to_numpy()
    V = np.array(proj.loc[ids_, [f"ros_{k}" for k in external.KEYS.values()]], dtype=float)  # a writable copy
    # A player no source covers today (see fill_missing) keeps his consensus in every draw.
    none = np.isnan(V).all(axis=1)
    V[none] = np.array(proj.loc[ids_, "ros"], dtype=float)[none][:, None]
    Wt = rng.dirichlet(np.ones(V.shape[1]), n_sims)
    den = (~np.isnan(V)).astype(float) @ Wt.T
    ros = np.where(den > 0, (np.nan_to_num(V) @ Wt.T) / np.where(den > 0, den, 1), 0.0)
    R = np.vstack([rng.choice(ratios[p], n_sims) for p in P.loc[ids_, "pos"]])
    R = 1 + (R - 1) * np.sqrt(frac_left.loc[ids_].to_numpy())[:, None]
    S = real_fp.reindex(ids_).fillna(0).to_numpy()[:, None] + ros * R
    tot = {}
    for mid, t in D.reset_index(drop=True).groupby("manager_id"):
        s = 0
        for p, n in COUNTED.items():
            rows = t.index[t["pos"] == p].to_numpy()
            s = s + np.sort(S[rows], axis=0)[-n:].sum(axis=0)
        tot[mid] = s
    return pd.DataFrame(tot)


def odds(MC: pd.DataFrame) -> pd.DataFrame:
    rank = MC.rank(axis=1, ascending=False, method="first")
    return pd.DataFrame({"expected_total": MC.mean(), "expected_finish": rank.mean(),
                         **{k: (rank == k).mean() for k in range(1, TEAMS + 1)}})


# --- History and awards -------------------------------------------------------------------

def load_history(folder) -> list[dict]:
    return [json.loads(f.read_text()) for f in sorted(folder.glob("*.json"))] if folder.exists() else []


def snapshot(day: str, as_of: str, managers: pd.DataFrame, players: pd.DataFrame, odds_: pd.DataFrame) -> dict:
    """One morning: standings and odds per manager; points, games, injury, points per game per drafted player."""
    return {
        "date": day, "as_of": as_of,
        "managers": {str(m): {"points": int(r["points"]), "rank": int(r["rank"]),
                              "expected_total": round(float(odds_.loc[m, "expected_total"]), 1),
                              "win_pct": round(float(odds_.loc[m, 1]) * 100, 2)} for m, r in managers.iterrows()},
        "players": {str(pid): [int(r["FP"]), int(r["GP"]), r["injury"] if isinstance(r["injury"], str) else None,
                               round(float(r["ppg"]), 3), int(r["team_played"]), r["nhl_team"],
                               round(float(r["games_left"]) / max(float(r["team_left"]), 1.0), 3)]
                    for pid, r in players.iterrows()},
    }


def award_mondays(season_start: str, today: str) -> list[str]:
    """First Monday at least six days after opening night, then every Monday up to today."""
    d = date.fromisoformat(season_start) + timedelta(days=6)
    d += timedelta(days=(7 - d.weekday()) % 7)
    out = []
    while d.isoformat() <= today:
        out.append(d.isoformat())
        d += timedelta(days=7)
    return out


def weekly_awards(hist: list[dict], D: pd.DataFrame, season_start: str, today: str, cfg: dict) -> list[dict]:
    """Pick de la semaine, Meilleure remontée, Malchance and Disette for every Monday so far (newest first)."""
    if not hist:
        return []
    hist = sorted(hist, key=lambda h: h["date"])

    def at(day):  # latest morning on or before `day`, else the first one (opening day: all zeros)
        before = [h for h in hist if h["date"] <= day]
        return before[-1] if before else hist[0]

    out = []
    for monday in award_mondays(season_start, today):
        end = at(monday)
        start = at((date.fromisoformat(monday) - timedelta(days=7)).isoformat())
        if end["date"] <= start["date"]:
            continue
        week = [h for h in hist if start["date"] < h["date"] <= end["date"]]

        def gain(pid, i=0):
            e, s = end["players"].get(str(pid)), start["players"].get(str(pid))
            return (e[i] - s[i]) if e and s else 0

        late = D[D["round"] >= cfg["late_round"]].assign(g=lambda x: x["playerId"].map(gain))
        pick = late.sort_values(["g", "overall"], ascending=[False, False]).iloc[0]
        # Team points this week: best-ball total at the end minus at the start.
        team_gain = {m: end["managers"][m]["points"] - start["managers"][m]["points"] for m in end["managers"]}
        climb = {m: start["managers"][m]["rank"] - end["managers"][m]["rank"] for m in end["managers"]}
        best = max(climb, key=lambda m: (climb[m], team_gain[m]))
        worst = min(team_gain, key=lambda m: (team_gain[m], -end["managers"][m]["rank"]))
        # Points lost to injuries: games a player missed while listed as hurt, times his points per game.
        loss = injury_losses([start] + week, D)
        lost = {m: v["points"] for m, v in loss.items()}
        unlucky = max(lost, key=lambda m: lost[m])
        out.append({
            "week_end": monday, "from": start["date"], "to": end["date"],
            "pick": {"nhl_id": int(pick["playerId"]), "manager_id": int(pick["manager_id"]), "value": int(pick["g"]),
                     "round": int(pick["round"])} if pick["g"] > 0 else None,
            "comeback": {"manager_id": int(best), "value": int(climb[best]), "from": start["managers"][best]["rank"],
                         "to": end["managers"][best]["rank"]} if climb[best] > 0 else None,
            "bad_luck": {"manager_id": int(unlucky), "value": round(lost[unlucky], 1),
                         "games": int(loss[unlucky]["games"])} if lost[unlucky] > 0 else None,
            "drought": {"manager_id": int(worst), "value": int(team_gain[worst])},
        })
    return out[::-1]


# --- Stories: headline, this week's games, season awards ------------------------------

HURT = ("IR", "Out", "Day-to-day")


def counted_players(D: pd.DataFrame, final: pd.Series) -> set:
    """Who counts: best 6 F, 4 D, 1 G per manager by projected final total (as on the site)."""
    x = D.assign(v=D["playerId"].map(final).fillna(0.0))
    return {pid for _, t in x.groupby("manager_id") for p, n in COUNTED.items()
            for pid in t[t.pos == p].sort_values("v", ascending=False)["playerId"].head(n)}


def week_games(D: pd.DataFrame, people: pd.DataFrame, T: pd.DataFrame, counts: set, today: str, as_of: str) -> dict:
    """Games this week (Monday to Sunday) for each manager's counted players, skipping players listed hurt.
    left: games still to play (after as_of); total: the whole week."""
    d = date.fromisoformat(today)
    monday = d - timedelta(days=d.weekday())
    sunday = monday + timedelta(days=6)
    mon, sun = monday.isoformat(), sunday.isoformat()
    out = {}
    for mid, t in D.groupby("manager_id"):
        left = total = 0
        for pid in t["playerId"]:
            if pid not in counts or people.loc[pid, "injury"] in ("IR", "Out"):
                continue
            dates = T["all_dates"].get(people.loc[pid, "nhl_team"], [])
            total += sum(mon <= x <= sun for x in dates)
            left += sum(as_of < x <= sun for x in dates)
        out[str(mid)] = {"left": left, "total": total}
    return {"start": mon, "end": sun, "managers": out}


def pace(D: pd.DataFrame, people: pd.DataFrame, real: pd.DataFrame, T: pd.DataFrame, counts: set) -> dict:
    """Per manager, for his counted players: real points per game actually played (games missed through
    injury are not in the count) and the NHL games left on their teams' schedules this season."""
    rl = real.reindex(people.index)
    out = {}
    for mid, t in D.groupby("manager_id"):
        mine = [p for p in t["playerId"] if p in counts]
        gp = float(rl.loc[mine, "GP"].fillna(0).sum())
        pts = float(rl.loc[mine, "FP"].fillna(0).sum())
        left = int(sum(T["left"].get(people.loc[p, "nhl_team"], 0) for p in mine))
        out[str(mid)] = {"gp": int(gp), "points": int(pts), "ppg": round(pts / gp, 3) if gp else None, "left": left}
    avg = sum(v["left"] for v in out.values()) / len(out)
    for v in out.values():
        v["left_vs_avg"] = round(v["left"] - avg)
    return out


def injury_losses(snaps: list[dict], D: pd.DataFrame) -> dict:
    """Games drafted players missed while listed hurt, and the points that cost (games x his points per game),
    per manager, over consecutive mornings. A player who changed teams between two mornings is skipped
    for that pair (his team's game count is not comparable)."""
    out = {str(m): {"games": 0, "points": 0.0, "worst": None} for m in D["manager_id"].unique()}
    by_player = {}
    for s, e in zip(snaps, snaps[1:]):
        for pid in D["playerId"]:
            a, b = s["players"].get(str(pid)), e["players"].get(str(pid))
            if not a or not b or b[2] not in HURT:
                continue
            if len(a) >= 6 and len(b) >= 6 and a[5] != b[5]:
                continue
            missed = max(0, (b[4] - a[4]) - (b[1] - a[1]))
            if missed:
                by_player[pid] = by_player.get(pid, 0) + missed
                o = out[str(D.loc[D.playerId == pid, "manager_id"].iloc[0])]
                o["games"] += missed
                o["points"] += missed * b[3]
    for m, o in out.items():
        mine = {p: g for p, g in by_player.items() if str(D.loc[D.playerId == p, "manager_id"].iloc[0]) == m}
        if mine:
            p = max(mine, key=mine.get)
            o["worst"] = {"nhl_id": int(p), "games": int(mine[p])}
    return out


def headline(snap: dict, previous: dict | None, D: pd.DataFrame, people: pd.DataFrame, evening: bool) -> list[str]:
    """Up to four short lines on what changed since the previous update (French, for the site)."""
    if not previous:
        return []
    name = D.drop_duplicates("manager_id").set_index("manager_id")["manager"]
    nm = lambda m: name[int(m)]
    cur, old = snap["managers"], previous["managers"]
    when = "ce soir" if evening else "hier soir"
    lines = []
    order = sorted(cur, key=lambda m: cur[m]["rank"])
    lead, second = order[0], order[1]
    gap = cur[lead]["points"] - cur[second]["points"]
    if old.get(lead, {}).get("rank") != 1:
        lines.append(f"{nm(lead)} prend la tête du classement.")
    elif gap > 0:
        lines.append(f"{nm(lead)} garde la tête, {gap} point{'s' if gap > 1 else ''} devant {nm(second)}.")
    climb = {m: old[m]["rank"] - cur[m]["rank"] for m in cur if m in old}
    up = max(climb, key=lambda m: (climb[m], cur[m]["points"])) if climb else None
    if up and climb[up] >= 2 and up != lead:
        lines.append(f"{nm(up)} gagne {climb[up]} rangs, du {_ord(old[up]['rank'])} au {_ord(cur[up]['rank'])}.")
    gains = {pid: v[0] - previous["players"].get(pid, [0])[0] for pid, v in snap["players"].items()}
    best = max(gains, key=gains.get) if gains else None
    if best and gains[best] >= 2:
        mid = int(D.loc[D.playerId == int(best), "manager_id"].iloc[0])
        lines.append(f"{people.loc[int(best), 'name']} ({nm(mid)}) : {gains[best]} points {when}.")
    moves = {m: cur[m]["win_pct"] - old[m]["win_pct"] for m in cur if m in old}
    big = max(moves, key=lambda m: abs(moves[m])) if moves else None
    if big and abs(moves[big]) >= 2:
        lines.append(f"Les odds de {nm(big)} passent de {_pct(old[big]['win_pct'])} à {_pct(cur[big]['win_pct'])}.")
    hurt = [pid for pid, v in snap["players"].items()
            if v[2] in ("IR", "Out") and previous["players"].get(pid, [0, 0, None])[2] not in ("IR", "Out")]
    for pid in hurt[: max(0, 4 - len(lines))]:
        mid = int(D.loc[D.playerId == int(pid), "manager_id"].iloc[0])
        lines.append(f"{people.loc[int(pid), 'name']} ({nm(mid)}) est maintenant {'blessé' if snap['players'][pid][2] == 'IR' else 'absent'}.")
    return lines[:4]


def _ord(n: int) -> str:
    return "1er" if n == 1 else f"{n}e"


def _pct(x: float) -> str:
    return f"{x:.1f}".replace(".", ",") + "\u00a0%"


def season_awards(hist: list[dict], D: pd.DataFrame, cfg: dict) -> list[dict]:
    """The season so far, recomputed every morning from data/history (empty before the first game)."""
    snaps = [h for h in sorted(hist, key=lambda h: h["date"])]
    live = [h for h in snaps if any(v["points"] > 0 for v in h["managers"].values())]
    if not live:
        return []
    end = live[-1]
    pts = D.assign(p=D["playerId"].map(lambda p: (end["players"].get(str(p)) or [0])[0]))
    out = []
    top = pts.sort_values(["p", "overall"], ascending=[False, True]).iloc[0]
    out.append({"key": "player", "nhl_id": int(top.playerId), "manager_id": int(top.manager_id), "value": int(top.p)})
    late = pts[pts["round"] >= cfg["late_round"]].sort_values(["p", "overall"], ascending=[False, False]).iloc[0]
    out.append({"key": "pick", "nhl_id": int(late.playerId), "manager_id": int(late.manager_id), "value": int(late.p),
                "round": int(late["round"])})
    early = pts[pts["round"] <= 3].assign(gap=lambda x: x["p"] - x.groupby("round")["p"].transform("mean"))
    flop = early.sort_values(["gap", "overall"]).iloc[0]
    out.append({"key": "bust", "nhl_id": int(flop.playerId), "manager_id": int(flop.manager_id), "value": int(flop.p),
                "gap": round(float(flop.gap), 1), "round": int(flop["round"])})
    loss = injury_losses(snaps, D)
    m = max(loss, key=lambda k: (loss[k]["games"], loss[k]["points"]))
    if loss[m]["games"] > 0:
        out.append({"key": "bad_luck", "manager_id": int(m), "value": int(loss[m]["games"]),
                    "points": round(loss[m]["points"], 1), "worst": loss[m]["worst"]})
    ids_ = list(end["managers"])
    firsts = {k: sum(h["managers"][k]["rank"] == 1 for h in live) for k in ids_}
    king = max(firsts, key=lambda k: (firsts[k], -end["managers"][k]["rank"]))
    out.append({"key": "king", "manager_id": int(king), "value": int(firsts[king]), "mornings": len(live)})
    swings = {k: sum(abs(a["managers"][k]["rank"] - b["managers"][k]["rank"]) for a, b in zip(live, live[1:])) for k in ids_}
    wild = max(swings, key=lambda k: (swings[k], -end["managers"][k]["rank"]))
    if swings[wild] > 0:
        out.append({"key": "rollercoaster", "manager_id": int(wild), "value": int(swings[wild])})
    return out


# --- Safety checks ------------------------------------------------------------------------

def checks(D, X, real, proj, managers, previous: dict | None, league: dict, cfg: dict,
           teams: pd.Series | None = None, nhl: set | None = None) -> list[str]:
    problems = []
    if teams is not None and nhl:
        bad = teams.loc[D["playerId"]][~teams.loc[D["playerId"]].isin(nhl)]
        if len(bad):
            problems.append("drafted players without a known NHL team (no schedule, no games left): "
                            + ", ".join(f"{pid} {t!r}" for pid, t in bad.items()))
    if len(D) != TEAMS * ROUNDS or D["playerId"].isna().any() or not D["playerId"].is_unique:
        problems.append(f"expected {TEAMS * ROUNDS} drafted players with unique NHL ids, got {len(D)}")
    sizes = D.groupby("manager_id").size()
    if len(sizes) != TEAMS or (sizes != ROUNDS).any():
        problems.append(f"expected {TEAMS} teams of {ROUNDS}: {sizes.to_dict()}")
    for pos, n in DRAFTED.items():
        bad = D[D.pos == pos].groupby("manager_id").size().reindex(sizes.index, fill_value=0)
        if (bad != n).any():
            problems.append(f"expected {n} {pos} per team: {bad[bad != n].to_dict()}")
    problems += ids.check(X.loc[D["playerId"]])
    stats = ["GP", "G", "A", "GWG", "HT", "GS", "W", "OTL", "SO", "FP"]
    if len(real) and (real[stats] < 0).any().any():
        problems.append("negative real stats: " + ", ".join(real.index[(real[stats] < 0).any(axis=1)].astype(str)))
    if (proj["ros"].fillna(0) < 0).any() or (proj["games_left"] < 0).any():
        problems.append("negative rest-of-season projection")
    if proj.loc[D["playerId"], "ros"].isna().any():
        problems.append("drafted players without any projection: "
                        + ", ".join(D.loc[proj.loc[D["playerId"], "ros"].isna().to_numpy(), "name"]))
    if previous:
        for m, r in managers.iterrows():
            before = previous["managers"].get(str(m), {}).get("points", 0)
            if r["points"] < before - cfg["drop_tolerance"]:
                problems.append(f"team {m} went from {before} to {r['points']} real points since {previous['date']}")
    # NHL totals reconcile: skater goals vs scoreboard goals (minus shootout winners), goalie wins vs games.
    goals = int(real.loc[real.pos.isin(["F", "D"]), "G"].sum()) if len(real) else 0
    wins = int(real.loc[real.pos == "G", "W"].sum()) if len(real) else 0
    if abs(goals - league["goals"]) > 3 + 0.002 * league["goals"]:
        problems.append(f"skater goals {goals} vs scoreboard goals {league['goals']}")
    if abs(wins - league["games"]) > 2:
        problems.append(f"goalie wins {wins} vs games played {league['games']}")
    return problems


# --- The job ------------------------------------------------------------------------------

def run(season: int = SEASON, as_of: str | None = None, refresh: bool = True, out_dir=None,
        write_history: bool = True, evening: bool = False) -> dict:
    """The morning update (games up to yesterday; writes the day's history) or, with evening=True, the
    10 pm update (adds today's finished games to the site only; the next morning makes it official)."""
    cfg = settings()
    replay = as_of is not None
    if evening:
        today = as_of or toronto_today().isoformat()
        as_of = today
    else:
        today = (date.fromisoformat(as_of) + timedelta(days=1)).isoformat() if replay else toronto_today().isoformat()
        as_of = as_of or (date.fromisoformat(today) - timedelta(days=1)).isoformat()
    site_dir = (out_dir / "site") if out_dir else site_export.SITE_DATA
    hist_dir = (out_dir / "history") if out_dir else HISTORY
    print(f"{'evening' if evening else 'daily'} update {today}: season {season}, games up to {as_of}"
          + (" (finished games only)" if evening else ""))

    D = load_draft()
    data = dataset.load()
    T, league = team_games(season, as_of, refresh=refresh or replay)
    finished = league["finished_on_as_of"] if evening else None
    real = real_stats(season, as_of, finished)
    goalie_games = nhl_api.goalie_games_to_date(season, as_of)
    if evening and len(goalie_games):
        goalie_games = goalie_games[(goalie_games["gameDate"] < as_of) | goalie_games["gameId"].isin(finished)]
    started = bool(T["played"].sum() > 0)
    print(f"  {league['games']} games played, {len(real)} players with stats")

    status = refresh_sources(refresh)
    # Player universe: drafted players, current NHL rosters, and anyone with stats this season.
    rost = nhl_api.all_rosters(SEASON, refresh=refresh).drop_duplicates("playerId").set_index("playerId")
    rost["pos"] = pos_group(rost["pos"])
    U = pd.concat([
        D.set_index("playerId")[["name", "team", "pos"]],
        rost[["name", "team", "pos"]],
        real.loc[real.GP > 0, ["name", "pos"]].assign(team=""),
    ])
    U = U[~U.index.duplicated()].dropna(subset=["pos"])

    # First pass without HockeyBangers to pick the undrafted candidates.
    R0 = external.rates(U, data, hb_names=[])
    first = pd.DataFrame({k: external.rate_points(R0, U["pos"], k) for k in external.KEYS.values()}).mean(axis=1)
    first = first * R0["ext_starts"].where(U["pos"] == "G", R0["ext_gp"]) + real["FP"].reindex(U.index).fillna(0)
    taken = set(D["playerId"])
    und = first[~first.index.isin(taken)]
    cand = list(und.sort_values(ascending=False).head(N_CANDIDATES).index)
    if started:
        cand += [p for p in real.loc[real.index.isin(und.index)].sort_values("FP", ascending=False).head(40).index
                 if p not in cand]
    people = U.loc[list(D["playerId"]) + cand].copy()

    if evening:  # compare with this morning; the history on disk is not changed
        hist = load_history(hist_dir)
        previous = hist[-1] if hist else None
    else:
        hist = [h for h in load_history(hist_dir) if h["date"] != today]
        previous = hist[-1] if hist and hist[-1]["date"] < today else None

    # Current NHL team: his NHL.com player page, else today's NHL rosters, else his team at the previous
    # update, else the draft file (short codes translated). Games left come from this team's schedule.
    shots = site_export.headshots(people.index, refresh)
    before = {int(k): v[5] for k, v in (previous or {}).get("players", {}).items() if len(v) >= 6}
    people["nhl_team"] = [shots.get(p, {}).get("nhl_team_now") or rost["team"].get(p) or before.get(p)
                          or TEAM_ALIAS.get(t, t) for p, t in zip(people.index, people["team"])]
    X = ids.pin(ids.build(people[["name", "team", "pos"]]), D.set_index("playerId")[["espn_id", "df_id"]])
    people["injury"] = [site_export.injury(*a) for a in zip(X["espn_injury"], X["df_injury"], X["df_ir"])]
    R = external.rates(people[["name", "team", "pos"]], data, hb_names=list(people.loc[people.pos != "G", "name"]),
                       hb_refresh=refresh)
    proj = project(people, R, real, T, cfg, goalie_games)
    proj = fill_missing(proj, D, people, T, previous, cfg)
    team = T.reindex(people["nhl_team"].values)
    frac_left = pd.Series((team["left"] / team["total"]).fillna(1.0).to_numpy(), index=people.index)
    people["team_played"] = team["played"].fillna(0).to_numpy()
    people["team_left"] = team["left"].fillna(0).to_numpy()
    real_fp = real["FP"].reindex(people.index).fillna(0.0)

    # Odds and standings.
    ratios = external.outcome_ratios(data)
    MC = simulate(D, people, proj, real_fp, frac_left, ratios, cfg["sims"])
    od = odds(MC)
    final = real_fp + proj["ros"].fillna(0)
    M = pd.DataFrame({"points": best_ball(D, real_fp), "proj_consensus": best_ball(D, final)})
    M = M.join(od[["expected_total"]])
    by_finish = od.sort_values("expected_finish").index
    order = M.sort_values(["points", "expected_total"], ascending=False).index if started else by_finish
    M["rank"] = pd.Series(range(1, TEAMS + 1), index=order)
    M["proj_rank"] = pd.Series(range(1, TEAMS + 1), index=by_finish)

    problems = checks(D, X, real, proj, M, previous, league, cfg, people["nhl_team"], set(T.index))
    if problems:
        raise SystemExit("safety checks failed, nothing written:\n  " + "\n  ".join(problems))

    rows = people.join(real.reindex(people.index)[["GP", "FP"]].fillna(0)).join(proj[["ppg", "games_left"]])
    snap = snapshot(today, as_of, M, rows.loc[D["playerId"]], od)
    if not evening:
        hist.append(snap)
    awards = weekly_awards(hist, D, site_export.season_start(season), today, cfg)
    counts = counted_players(D, final)
    stories = {
        "headline": headline(snap, previous, D, people, evening) if started else [],
        "week": week_games(D, people, T, counts, today, as_of),
        "pace": pace(D, people, real, T, counts),
        "season_awards": season_awards(hist, D, cfg),
    }

    payload = site_export.payload(
        D=D, people=people, X=X, shots=shots, real=real, proj=proj, managers=M, odds_=od,
        started=started, as_of=as_of, T=T, hist=hist, awards=awards, season=season, cfg=cfg,
        counts=counts, stories=stories, snap=snap, previous=previous, evening=evening)
    site_export.write(payload, site_dir)
    if write_history and not evening:
        hist_dir.mkdir(parents=True, exist_ok=True)
        (hist_dir / f"{today}.json").write_text(json.dumps(snap, ensure_ascii=False, separators=(",", ":"), allow_nan=False))
    print(f"  sources: {status}; history: {len(hist)} mornings; awards: {len(awards)} weeks")
    for line in stories["headline"]:
        print("  la une:", line)
    print(M.sort_values("rank").to_string())
    return payload


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-refresh", action="store_true", help="reuse cached projections and player pages")
    ap.add_argument("--season", type=int, default=SEASON)
    ap.add_argument("--as-of", help="replay: real stats up to this date (YYYY-MM-DD)")
    ap.add_argument("--out", help="write site data and history under this folder instead")
    ap.add_argument("--evening", action="store_true", help="10 pm update: add today's finished games (site only)")
    a = ap.parse_args()
    from pathlib import Path
    run(a.season, a.as_of, refresh=not a.no_refresh, out_dir=Path(a.out) if a.out else None, evening=a.evening)


if __name__ == "__main__":
    main()
