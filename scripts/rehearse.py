"""Dress rehearsal of the daily update: the season's first two weeks, with seeded games, end to end.

  uv run python scripts/rehearse.py --out /tmp/rehearsal            # 14 mornings, Sept 30 to Oct 13
  uv run python scripts/rehearse.py --out /tmp/rehearsal --days 1   # just tomorrow morning

Nothing in the repo is touched: site data and history go under --out (history starts from the real
data/history). Games are seeded with the real opening fortnight of 2025-26, shifted to 2026-27 dates
(2025-26 opened Oct 7, 2025; 2026-27 opens Sept 29, 2026), through the same NHL API calls. Everything
else is live: ESPN, CBS, NHL.com, HockeyBangers, Daily Faceoff, rosters and player pages.

Before the first morning: the evening of opening night (Sept 29), like tonight's first 10 pm run. Of the
seeded day's 3 games, one is over, one is over on the scoreboard but its stats are not published yet,
and one is still being played: only the first may count, and the next morning counts all three.

Some mornings also break things on purpose, to prove the update still goes through:
  day 2   ESPN, CBS, NHL.com, Daily Faceoff and HockeyBangers all fail to download (cached copies used)
  day 3   a drafted forward vanishes from Daily Faceoff, a drafted goalie from ESPN and CBS
  day 4   every player page fails (NHL photos come from the fixed address pattern)
  day 5+  trade: a drafted forward and a drafted starting goalie change NHL teams and stay there
  evenings of days 5, 7 and 12: the 10 pm update (that day's finished games, site only, history untouched)
After every morning the output is checked like the site and the workflow would check it.
"""
import argparse
import json
import shutil
from contextlib import ExitStack
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

import pandas as pd

from nhlpool import daily, ids, site_export
from nhlpool.fetch import espn, http, nhl_api, others

SEED_SEASON = 20252026
SHIFT = date(2025, 10, 7) - date(2026, 9, 29)
FIRST_MORNING = date(2026, 9, 30)


def seeded(fn):
    return lambda season, as_of: fn(SEED_SEASON, (date.fromisoformat(as_of) + SHIFT).isoformat())


def seed_patches(stack: ExitStack) -> None:
    for name in ("skaters_to_date", "goalies_to_date", "hat_tricks_to_date", "goalie_games_to_date", "skater_games_on"):
        stack.enter_context(mock.patch.object(nhl_api, name, seeded(getattr(nhl_api, name))))
    team_games = daily.team_games

    def shifted(season, as_of, refresh=True, skip=None):
        T, league = seeded(lambda s, a: team_games(s, a, refresh=False, skip=skip))(season, as_of)
        # The week's schedule in this season's dates ("Cette semaine"); played dates stay in the seed's
        # dates, like the goalie game rows they are compared with.
        T["all_dates"] = [[(date.fromisoformat(x) - SHIFT).isoformat() for x in ds] for ds in T["all_dates"]]
        T["games"] = [[{**g, "date": (date.fromisoformat(g["date"]) - SHIFT).isoformat()} for g in gs] for gs in T["games"]]
        return T, league
    stack.enter_context(mock.patch.object(daily, "team_games", shifted))


def outage(stack: ExitStack) -> None:
    """Every projection and lineup site is down: downloads raise, cached copies must carry the day."""
    real_get = http._get
    down = ("espn.com", "cbssports.com", "nhl.com/news", "dailyfaceoff.com", "hockeybangers.com")

    def get(url, headers=None, retries=6):
        if any(d in url for d in down):
            raise ConnectionError(f"rehearsal outage: {url}")
        return real_get(url, headers, retries)
    stack.enter_context(mock.patch.object(http, "_get", get))


def vanish(stack: ExitStack, D: pd.DataFrame) -> list[str]:
    """A drafted forward disappears from Daily Faceoff; a drafted goalie from ESPN and CBS."""
    fwd = D[(D.pos == "F") & (D["round"] == 12)].iloc[0]
    gk = D[D.pos == "G"].sort_values("overall").iloc[-1]
    df_players, espn_proj, cbs = ids.df_players, espn.projections, others.cbs
    fdf, gesp, gname = fwd["df_id"], gk["espn_id"], gk["name"]
    stack.enter_context(mock.patch.object(ids, "df_players", lambda: (lambda x: x[x["df_id"] != fdf])(df_players())))
    stack.enter_context(mock.patch.object(espn, "projections", lambda **k: (lambda x: x[x["espn_id"] != gesp])(espn_proj(**k))))
    stack.enter_context(mock.patch.object(others, "cbs", lambda **k: (lambda x: x[x["name"] != gname])(cbs(**k))))
    return [fwd["name"], gk["name"]]


def no_player_pages(stack: ExitStack) -> None:
    def landing(pid, refresh=False):
        raise ConnectionError("rehearsal: player page down")
    stack.enter_context(mock.patch.object(nhl_api, "landing", landing))


def traded(D: pd.DataFrame) -> dict:
    """The traded players: a second-round forward and the first goalie drafted, to teams they are not on."""
    fwd = D[(D.pos == "F") & (D["round"] == 2)].iloc[0]
    gk = D[D.pos == "G"].sort_values("overall").iloc[0]
    now = site_export.headshots([fwd["playerId"], gk["playerId"]], refresh=False)
    pick = lambda pid, a, b: a if now[pid].get("nhl_team_now") != a else b
    return {int(fwd["playerId"]): pick(fwd["playerId"], "SJS", "ANA"), int(gk["playerId"]): pick(gk["playerId"], "CHI", "CBJ")}


def trade(stack: ExitStack, moves: dict) -> None:
    real = site_export.headshots

    def headshots(ids_, refresh):
        out = real(ids_, refresh)
        for pid, team in moves.items():
            if pid in out:
                out[pid] = {**out[pid], "nhl_team_now": team}
        return out
    stack.enter_context(mock.patch.object(site_export, "headshots", headshots))


def check_trade(day: str, d: dict, prev: dict | None, moves: dict) -> str:
    """The traded players show their new team, keep their points, and their games left follow the new team."""
    as_of = (date.fromisoformat(day) - timedelta(days=1)).isoformat()
    T, _ = daily.team_games(daily.SEASON, as_of)
    notes = []
    for pid, team in moves.items():
        p = next(x for x in d["players"] if x["nhl_id"] == pid)
        assert p["nhl_team"] == team, (p["name"], p["nhl_team"], team)
        left = int(T.loc[team, "left"])
        assert p["games_left"] <= left, (p["name"], p["games_left"], left)
        if prev:
            q = next(x for x in prev["players"] if x["nhl_id"] == pid)
            assert p["points"] >= q["points"], (p["name"], q["points"], p["points"])
        notes.append(f"{p['name']} -> {team}: {p['points']} pts, {p['games_left']:.0f} of {left} games left, proj {p['proj']}")
    return "; ".join(notes)


def opening_evening(out: Path) -> dict:
    """Sept 29 at 10 pm: the first evening update, with no stats before today."""
    seed_day = (FIRST_MORNING - timedelta(days=1) + SHIFT).isoformat()      # 2025-10-07
    games = sorted({g["id"] for t in nhl_api.current_team_abbrevs()
                    for g in nhl_api.schedule(t, SEED_SEASON, refresh=False) if g["gameDate"] == seed_day})
    assert len(games) >= 3, games
    counted, lagging, live = games[0], games[1], games[2]
    schedule, skaters = nhl_api.schedule, nhl_api.skater_games_on
    with ExitStack() as stack:
        day = FIRST_MORNING - timedelta(days=1)
        stack.enter_context(mock.patch.object(daily, "toronto_today", lambda: day))
        stack.enter_context(mock.patch.object(daily, "evening_day", lambda: day))
        # One game still in progress on the scoreboard...
        stack.enter_context(mock.patch.object(nhl_api, "schedule", lambda t, season, refresh=True: [
            {**g, "gameState": "LIVE"} if g["id"] == live else g for g in schedule(t, season, refresh=refresh)]))
        # ...and one over, but its lines not in the NHL stats yet. seed_patches() comes last so it wraps these.
        stack.enter_context(mock.patch.object(nhl_api, "skater_games_on", lambda season, d: (
            lambda x: x[x["gameId"] != lagging] if len(x) else x)(skaters(season, d))))
        seed_patches(stack)
        print(f"\n=== evening {day} (opening night: game {counted} over, {lagging} over without stats, {live} live) ===")
        daily.run(refresh=True, out_dir=out, evening=True)
    d = check(day.isoformat(), out, None, evening=True)
    assert d["season_started"] and d["games_played"] == round(2 / 32, 1), d["games_played"]  # 1 game, 2 teams
    assert sorted(p.name for p in (out / "history").glob("*.json")) == ["2026-09-29.json"], "evening touched history"
    return d


def check(day: str, out: Path, prev: dict | None, evening: bool = False) -> dict:
    """What the workflow tests and the site rely on."""
    d = json.loads((out / "site" / "pool.json").read_text())  # strict JSON (no NaN)
    players = d["players"] + d["forgotten"]
    assert len(d["players"]) == 192 and len(d["managers"]) == 12
    for key in ("nhl_id", "espn_id", "df_id"):
        vals = [p[key] for p in players]
        assert all(isinstance(v, int) and v > 0 for v in vals), key
        assert len(set(vals)) == len(vals), f"duplicate {key}"
    assert all(p["photo"] and str(p["nhl_id"]) in p["photo"] for p in players)
    assert sorted(m["id"] for m in d["managers"]) == list(range(1, 13))
    assert d["season_started"] is True and (d["as_of"] == day if evening else d["as_of"] < day)
    assert d["update"] == ("evening" if evening else "morning")
    assert all(isinstance(x, str) and x for x in d["headline"]) and len(d["headline"]) <= 4
    assert d["week"]["start"] <= day <= d["week"]["end"] and len(d["week"]["managers"]) == 12
    assert all(0 <= w["left"] <= w["total"] for w in d["week"]["managers"].values())
    assert sum(w["total"] for w in d["week"]["managers"].values()) > 0, "no games this week for anyone"
    # Season awards come from morning records; before the first morning with points (tonight) there are none.
    morning_points = any(v > 0 for h in d["history"] for v in h["points"].values())
    assert ({a["key"] for a in d["season_awards"]} >= {"player", "pick", "bust", "king"}) if morning_points else not d["season_awards"]
    assert all("rank_change" in m and "win_change" in m for m in d["managers"])
    # Trophies are top 3s; the new sections are there and consistent.
    assert all(1 <= len(a["podium"]) <= 3 for a in d["season_awards"])
    assert all(len(v) <= 3 for w in d["awards"] for k, v in w.items() if isinstance(v, list))
    assert d["race"] and all((r["ahead"] is None) == (m["rank"] == 1) for m in d["managers"] for r in [d["race"][str(m["id"])]])
    assert d["tonight"]["date"] == day and len(d["tonight"]["managers"]) == 12
    ids_ = {p["nhl_id"] for p in d["players"]}
    assert all(g["nhl_id"] in ids_ for gs in d["tonight"]["managers"].values() for g in gs)
    assert d["player_weeks"]["dates"][-1] == d["history"][-1]["date"]
    assert all(len(v) == len(d["player_weeks"]["dates"]) for v in d["player_weeks"]["points"].values())
    if d["hot_cold"]:
        assert all(r["diff"] > 0 for r in d["hot_cold"]["hot"]) and all(r["diff"] < 0 for r in d["hot_cold"]["cold"])
    nhl = set(nhl_api.current_team_abbrevs())
    assert all(p["nhl_team"] in nhl for p in d["players"]), [p["name"] for p in d["players"] if p["nhl_team"] not in nhl]
    # A healthy drafted player always has games left (a wrong team code once gave 0 and sank a manager's odds).
    zero = [p["name"] for p in d["players"] if not p["injury"] and (p["games_left"] or 0) == 0]
    assert not zero, zero
    assert d["history"][-1]["date"] == day
    assert sorted(m["rank"] for m in d["managers"]) == list(range(1, 13))
    for m in d["managers"]:
        assert abs(sum(m["finish_odds"]) - 100) < 1.0, m
        assert m["expected_total"] >= m["points"]
        c = sum(p["points"] for p in d["players"] if p["manager_id"] == m["id"])
        assert m["points"] <= c
    assert abs(sum(m["win_pct"] for m in d["managers"]) - 100) < 1.0
    for p in d["players"]:
        assert p["points"] >= 0 and p["proj"] is not None and p["proj"] >= p["points"] - 0.05, p["name"]
    counted = pd.DataFrame(d["players"]).groupby(["manager_id", "pos"])["counts"].sum()
    assert (counted.xs("F", level="pos") == 6).all() and (counted.xs("D", level="pos") == 4).all()
    assert (counted.xs("G", level="pos") == 1).all()
    if prev:
        before = {m["id"]: m["points"] for m in prev["managers"]}
        assert all(m["points"] >= before[m["id"]] for m in d["managers"]), "a team lost points"
    mondays = daily.award_mondays(d["season_start"], day)
    assert len(d["awards"]) == len(mondays), (len(d["awards"]), mondays)
    return d


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--days", type=int, default=14)
    a = ap.parse_args()
    out = Path(a.out)
    shutil.rmtree(out, ignore_errors=True)
    (out / "history").mkdir(parents=True)
    for f in sorted(daily.HISTORY.glob("*.json")):
        if f.stem < FIRST_MORNING.isoformat():
            shutil.copy(f, out / "history" / f.name)
    D = daily.load_draft()
    moves = traded(D)
    prev = opening_evening(out)
    summary = [f"2026-09-29  {'opening-night evening: 1 of 3 games counted':<45} "
               f"points {sum(m['points'] for m in prev['managers'])}, headline: {prev['headline'][0] if prev['headline'] else '-'}"]
    for i in range(a.days):
        day = FIRST_MORNING + timedelta(days=i)
        with ExitStack() as stack:
            seed_patches(stack)
            stack.enter_context(mock.patch.object(daily, "toronto_today", lambda day=day: day))
            note = "normal"
            if i == 1:
                outage(stack); note = "all projection and lineup sites down"
            elif i == 2:
                note = "vanished: " + ", ".join(vanish(stack, D))
            elif i == 3:
                no_player_pages(stack); note = "every player page down"
            if i >= 4:
                trade(stack, moves); note = "trade in effect" if i > 4 else "trade: forward and goalie change teams"
            print(f"\n=== morning {day} ({note}) ===")
            daily.run(refresh=i in (0, 1, 2, 3), out_dir=out)
            d = check(day.isoformat(), out, prev)
            if i >= 4:
                print("  trade check:", check_trade(day.isoformat(), d, prev, moves))
            if i in (4, 6, 11):
                files = sorted(p.name for p in (out / "history").glob("*.json"))
                print(f"\n=== evening {day} (10 pm update) ===")
                daily.run(refresh=False, out_dir=out, evening=True)
                e = check(day.isoformat(), out, d, evening=True)
                assert sorted(p.name for p in (out / "history").glob("*.json")) == files, "evening touched history"
                gained = sum(m["points"] for m in e["managers"]) - sum(m["points"] for m in d["managers"])
                assert gained >= 0
                summary.append(f"{day}  {'evening: +' + str(gained) + ' team points tonight':<45} "
                               f"headline: {e['headline'][0] if e['headline'] else '-'}")
                shutil.copy(out / "site" / "pool.json", out / f"pool_{day}_evening.json")
        lead = min(d["managers"], key=lambda m: m["rank"])
        tonight_n = sum(len(v) for v in d["tonight"]["managers"].values())
        summary.append(f"{day}  {note:<45} games {d['games_played']:>4}  leader {lead['name']} {lead['points']} pts, "
                       f"win {lead['win_pct']}%  awards {len(d['awards'])}  playing today {tonight_n}")
        shutil.copy(out / "site" / "pool.json", out / f"pool_{day}.json")
        prev = d
    print("\nREHEARSAL PASSED\n" + "\n".join(summary))


if __name__ == "__main__":
    main()
