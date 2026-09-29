"""Export the pool's data for the website -> site/data/pool.json.

  uv run python -m nhlpool.site_export            # same as `python -m nhlpool.daily --no-refresh`, no history
  uv run python -m nhlpool.site_export --refresh  # re-download sources and player pages first

The numbers are computed by daily.py (real stats, updated projections, odds); this module
turns them into the JSON the site reads.

Every player carries three verified IDs (see ids.py): nhl_id, espn_id, df_id.
Photos are the NHL's official headshots (assets.nhle.com, keyed by NHL id), with
ESPN's headshot (a.espncdn.com, keyed by ESPN id) as a fallback. HockeyDB was
checked and has no player photos, and its robots.txt blocks automated agents.

Projections, games played, who counts, steals/busts, the forgotten and the odds all
come from external sources only (ESPN, NHL.com, CBS, HockeyBangers; see external.py).
Our own model is not used anywhere on the site.

Before the first game there are no real points yet: "points" are 0 and every ranking
uses the external consensus. Once games are played, standings, steals/busts, the top
players and the forgotten use real points.
"""
import argparse
import json
import re
import unicodedata
from datetime import date, datetime, timezone

import pandas as pd

from . import external
from .fetch import nhl_api
from .paths import ROOT

SITE_DATA = ROOT / "site" / "data"
COUNTED = {"F": 6, "D": 4, "G": 1}
DRAFTED = {"F": 8, "D": 6, "G": 2}
ESPN_PHOTO = "https://a.espncdn.com/i/headshots/nhl/players/full/{}.png"
NHL_PHOTO = "https://assets.nhle.com/mugs/nhl/{season}/{team}/{id}.png"
N_FORGOTTEN = 30


def slug(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def num(x, d=1):
    return None if x is None or pd.isna(x) else round(float(x), d)


def season_start(season: int = 20262027) -> str:
    """Date of the first regular-season game, from every team's NHL schedule."""
    return min(g["gameDate"] for team in nhl_api.current_team_abbrevs()
               for g in nhl_api.schedule(team, season, refresh=False))


def headshots(nhl_ids, refresh: bool) -> dict:
    out = {}
    for pid in nhl_ids:
        try:
            L = nhl_api.landing(int(pid), refresh=refresh)
            out[int(pid)] = {"photo": L.get("headshot"), "nhl_team_now": L.get("currentTeamAbbrev"),
                             "number": L.get("sweaterNumber"), "birth": L.get("birthDate")}
        except Exception:
            out[int(pid)] = {}
    return out


def injury(espn_status, df_injury, df_ir) -> str | None:
    """One status label, most serious first."""
    e = espn_status.upper() if isinstance(espn_status, str) else ""
    df_injury = df_injury if isinstance(df_injury, str) else None
    df_ir = bool(df_ir) if not pd.isna(df_ir) else False
    if e == "INJURY_RESERVE" or df_ir:
        return "IR"
    if e == "OUT" or df_injury == "out":
        return "Out"
    if e == "SUSPENSION":
        return "Suspended"
    if e == "DAY_TO_DAY" or df_injury in ("game-time-decision", "day-to-day"):
        return "Day-to-day"
    return None


def payload(D, people, X, shots, real, proj, managers, odds_, started, as_of, T, hist, awards, season, cfg) -> dict:
    """Everything the site shows. Drafted players and the forgotten carry real stats and projections."""
    today = date.today()
    rl = real.reindex(people.index)
    final = rl["FP"].fillna(0) + proj["ros"].fillna(0)

    def player(pid) -> dict:
        row, x, h, r, pr = people.loc[pid], X.loc[pid], shots.get(pid, {}), rl.loc[pid], proj.loc[pid]
        goalie = row["pos"] == "G"
        gp = 0 if pd.isna(r["GP"]) else int(r["GP"])
        stats = (["GS", "W", "OTL", "SO"] if goalie else ["G", "A", "GWG", "HT"])
        birth = h.get("birth")
        pts = 0 if pd.isna(r["FP"]) else int(r["FP"])
        return {
            "nhl_id": int(pid), "espn_id": int(x["espn_id"]), "df_id": int(x["df_id"]),
            "slug": slug(row["name"]), "name": row["name"], "pos": row["pos"],
            "nhl_team": row["nhl_team"], "number": h.get("number"),
            # The NHL's headshot address follows a fixed pattern, used if the player page did not load.
            "photo": h.get("photo") or NHL_PHOTO.format(season=season, team=row["nhl_team"], id=int(pid)),
            "photo_fallback": ESPN_PHOTO.format(int(x["espn_id"])),
            "injury": row["injury"] if isinstance(row["injury"], str) else None,
            "points": pts, "gp": gp,
            "stats": {k: (0 if pd.isna(r[k]) else int(r[k])) for k in stats},
            "proj": num(final[pid]),
            "proj_left": num(pr["ros"]),
            "games_left": num(pr["games_left"], 0),
            "proj_gp": num(gp + pr["games_left"], 0),  # goalies: games so far + starts left
            "sources": {lab: num(pts + pr[f"ros_{k}"]) for lab, k in external.KEYS.items()},
            "age": num((pd.Timestamp(today) - pd.Timestamp(birth)).days / 365.25) if birth else None,
        }

    players = []
    for mid, g in D.sort_values(["manager_id", "overall"]).groupby("manager_id", sort=False):
        roster = []
        for _, r in g.iterrows():
            p = player(r["playerId"])
            p.update({"manager_id": int(mid), "round": int(r["round"]), "overall": int(r["overall"])})
            roster.append(p)
        # Who counts: best 6 F, 4 D, 1 G by projected final total (real points + rest of season).
        for pos, n in COUNTED.items():
            ps = sorted([p for p in roster if p["pos"] == pos], key=lambda p: -(p["proj"] or 0))
            for i, p in enumerate(ps):
                p["counts"] = i < n
        players += roster

    # Draft value: real points (projection before the first game) vs the average of that round.
    key = (lambda p: p["points"]) if started else (lambda p: p["proj"] or 0)
    by_round = pd.DataFrame([{"round": p["round"], "v": key(p)} for p in players]).groupby("round")["v"].mean()
    for p in players:
        p["vs_round"] = num(key(p) - by_round[p["round"]])

    # The forgotten: best undrafted players with all three IDs, by real points once games are played.
    taken = set(D["playerId"])
    und = people[~people.index.isin(taken)].copy()
    und = und[X.loc[und.index, "espn_id"].notna() & X.loc[und.index, "df_id"].notna()]
    und["pts"], und["final"] = rl.loc[und.index, "FP"].fillna(0), final[und.index]
    und = und.sort_values(["pts", "final"] if started else ["final"], ascending=False).head(N_FORGOTTEN)

    names = D.drop_duplicates("manager_id").set_index("manager_id")["manager"]
    mgrs = []
    for mid, m in managers.iterrows():
        o = odds_.loc[mid]
        mgrs.append({"id": int(mid), "name": names[mid], "slot": int(mid), "rank": int(m["rank"]),
                     "proj_rank": int(m["proj_rank"]), "points": int(m["points"]),
                     "proj_consensus": num(m["proj_consensus"], 0), "expected_total": num(o["expected_total"], 0),
                     "expected_finish": num(o["expected_finish"], 2), "win_pct": num(o[1] * 100, 1),
                     "finish_odds": [num(o[k] * 100, 1) for k in range(1, len(managers) + 1)]})
    mgrs.sort(key=lambda m: m["rank"])

    nhl_teams = pd.Series([p["nhl_team"] for p in players]).value_counts()
    return {
        "season": f"{season // 10000}-{str(season % 10000)[2:]}",
        "projection_sources": list(external.SOURCES),
        "generated": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "as_of": as_of,
        "season_start": season_start(season),
        # True once real games are in; until then rankings use projections.
        "season_started": started,
        "games_played": round(float(T["played"].mean()), 1),
        "season_games": int(T["total"].median()),
        "real_weight_games": cfg["real_weight_games"],
        "rules": {"counted": COUNTED, "drafted": DRAFTED, "teams": len(mgrs), "rounds": int(D["round"].max())},
        "managers": mgrs,
        "players": players,
        "forgotten": [player(pid) for pid in und.index],
        "nhl_teams": [{"team": t, "count": int(c)} for t, c in nhl_teams.items()],
        "history": [{"date": h["date"], "ranks": {k: v["rank"] for k, v in h["managers"].items()},
                     "points": {k: v["points"] for k, v in h["managers"].items()}} for h in hist],
        "awards": awards,
    }


def write(out: dict, folder=SITE_DATA) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "pool.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, allow_nan=False))
    miss = [p["name"] for p in out["players"] + out["forgotten"] if not p["photo"]]
    print(f"wrote {folder / 'pool.json'}: {len(out['managers'])} managers, {len(out['players'])} drafted, "
          f"{len(out['forgotten'])} forgotten; players without an NHL photo: {miss or 'none'}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    from .daily import run
    run(refresh=ap.parse_args().refresh, write_history=False)
