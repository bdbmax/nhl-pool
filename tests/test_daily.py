"""The daily update's math: rate updates, games left, safety checks and award dates."""
import pandas as pd
import pytest

from nhlpool import daily

CFG = {**daily.DEFAULTS}


def test_rate_update_weights_real_play_by_games():
    # No games yet: the source's rate. After 40 games: halfway between source and real.
    src = pd.Series([0.5, 0.5, 0.5])
    gp = pd.Series([0.0, 40.0, 400.0])
    real_goals = gp * 1.0  # scoring a goal a game
    out = daily.blend(src, real_goals, gp, 40)
    assert out.tolist() == pytest.approx([0.5, 0.75, (20 + 400) / 440])


def test_games_left_skaters_and_goalies():
    pos = pd.Series(["F", "F", "G", "G"])
    ext_gp = pd.Series([84.0, 42.0, 60.0, 60.0])
    ext_starts = pd.Series([None, None, 42.0, 42.0], dtype=float)
    left = pd.Series([40.0, 40.0, 40.0, 40.0])
    played = pd.Series([44.0, 44.0, 44.0, 0.0])
    gs = pd.Series([0.0, 0.0, 11.0, 0.0])
    injury = pd.Series([None, "IR", None, "Out"])
    out = daily.games_left(pos, ext_gp, ext_starts, 84.0, left, played, gs, injury, CFG)
    assert out[0] == pytest.approx(40)            # fully available
    assert out[1] == pytest.approx(40 * 0.5 - 10)  # half available, minus 10 for IR
    # Goalie: projected share 0.5, real share 11/44 = 0.25, weight 20 team games vs 44 played.
    share = (20 * 0.5 + 44 * 0.25) / 64
    assert out[2] == pytest.approx(40 * share)
    assert out[3] == pytest.approx((40 - 3) * 0.5)  # no games yet: the projected share, minus 3 for Out


def test_games_left_never_negative():
    out = daily.games_left(pd.Series(["F"]), pd.Series([20.0]), pd.Series([float("nan")]), 84.0,
                           pd.Series([5.0]), pd.Series([79.0]), pd.Series([0.0]), pd.Series(["IR"]), CFG)
    assert out[0] == 0


def _draft():
    rows = []
    for m in range(1, 13):
        for r in range(1, 17):
            pos = "F" if r <= 8 else ("D" if r <= 14 else "G")
            rows.append({"manager_id": m, "manager": f"M{m}", "round": r, "overall": (r - 1) * 12 + m, "pos": pos,
                         "playerId": m * 100 + r, "name": f"P{m}-{r}"})
    return pd.DataFrame(rows)


def _ids(D):
    X = D.set_index("playerId")[["name"]].copy()
    X["espn_id"] = range(1, len(X) + 1)
    X["df_id"] = range(1001, 1001 + len(X))
    for k in ("espn_id", "df_id"):
        X[f"{k}_name"], X[f"{k}_pos_ok"] = X["name"], True
    return X


def _real(goals=10, wins=5):
    return pd.DataFrame({"pos": ["F", "G"], "GP": [5, 5], "G": [goals, 0], "A": [0, 0], "GWG": [0, 0], "HT": [0, 0],
                         "GS": [0, 5], "W": [0, wins], "OTL": [0, 0], "SO": [0, 0], "FP": [goals, 2 * wins]},
                        index=[101, 115])


def _checks(**kw):
    D = _draft()
    args = dict(D=D, X=_ids(D), real=_real(), proj=pd.DataFrame({"ros": 50.0, "games_left": 70.0}, index=D["playerId"]),
                managers=pd.DataFrame({"points": [10] * 12}, index=range(1, 13)), previous=None,
                league={"goals": 10, "games": 5}, cfg=CFG)
    args.update(kw)
    return daily.checks(**args)


def test_checks_pass_on_clean_data():
    assert _checks() == []


def test_checks_catch_problems():
    D = _draft()
    assert any("teams of 16" in p for p in _checks(D=D.iloc[1:]))
    assert any("negative real" in p for p in _checks(real=_real(goals=-1)))
    assert any("scoreboard" in p for p in _checks(league={"goals": 40, "games": 5}))
    assert any("goalie wins" in p for p in _checks(league={"goals": 10, "games": 9}))
    prev = {"date": "2026-10-10", "managers": {str(m): {"points": 20} for m in range(1, 13)}}
    assert any("went from 20 to 10" in p for p in _checks(previous=prev))
    small = {"date": "2026-10-10", "managers": {str(m): {"points": 11} for m in range(1, 13)}}
    assert _checks(previous=small) == []  # a one-point stat correction is allowed
    X = _ids(D)
    X.loc[X.index[0], "df_id"] = None
    assert any("df_id missing" in p for p in _checks(X=X))


def test_award_mondays():
    # Opening night Tuesday Sept 29: first awards Monday Oct 5, then weekly.
    assert daily.award_mondays("2026-09-29", "2026-10-04") == []
    assert daily.award_mondays("2026-09-29", "2026-10-19") == ["2026-10-05", "2026-10-12", "2026-10-19"]


def test_weekly_awards():
    D = _draft()
    def snap(day, pts, gp, tgp, injury=None):
        players = {str(p): [pts.get(p, 0), gp.get(p, 0), injury.get(p) if injury else None, 1.0, tgp]
                   for p in D["playerId"]}
        managers = {str(m): {"points": 100 + m if day > "2026-10-01" else 0, "rank": 13 - m if day > "2026-10-01" else m}
                    for m in range(1, 13)}
        return {"date": day, "managers": managers, "players": players}
    hist = [snap("2026-09-29", {}, {}, 0),
            snap("2026-10-03", {109: 1}, {}, 3, {105: "IR"}),
            snap("2026-10-05", {109: 4, 212: 2}, {109: 4}, 4)]
    [w] = daily.weekly_awards(hist, D, "2026-09-29", "2026-10-05", CFG)
    assert w["pick"]["nhl_id"] == 109 and w["pick"]["value"] == 4   # round 9 of team 1
    assert w["comeback"]["manager_id"] == 12                          # from 12th to 1st
    assert w["drought"]["manager_id"] == 1                            # fewest points gained
    assert w["bad_luck"]["manager_id"] == 1                           # player 105 missed 4 games while hurt


def test_simulate_with_a_player_no_source_covers():
    # Frames built the way run() builds them; one drafted goalie has no source today (fill_missing gave him "ros").
    D = _draft()
    idx = D["playerId"]
    proj = pd.DataFrame({f"ros_{k}": 50.0 for k in ("espn", "nhl", "cbs", "hb")}, index=idx)
    proj["ros"] = 50.0
    gk = D.loc[D.pos == "G", "playerId"].iloc[0]
    proj.loc[gk, ["ros_espn", "ros_nhl", "ros_cbs", "ros_hb"]] = float("nan")
    proj.loc[gk, "ros"] = 30.0
    people = D.set_index("playerId")[["pos"]]
    ratios = {"F": [1.0], "D": [1.0], "G": [1.0]}
    MC = daily.simulate(D, people, proj, pd.Series(10.0, index=idx), pd.Series(1.0, index=idx), ratios, 50)
    assert MC.shape == (50, 12) and MC.notna().all().all()
    # 6 F + 4 D + 1 G, each 10 real + 50 left; the uncovered goalie is the team's backup.
    assert MC.iloc[0].tolist() == pytest.approx([11 * 60.0] * 12)
    od = daily.odds(MC)
    assert abs(od[list(range(1, 13))].sum(axis=1) - 1).max() < 1e-9


def _team_dates(n, start="2026-10-01"):
    from datetime import date, timedelta
    d0 = date.fromisoformat(start)
    return [(d0 + timedelta(days=2 * i)).isoformat() for i in range(n)]


def test_goalie_start_share_counts_only_his_current_team():
    T = pd.DataFrame({"dates": [_team_dates(44), _team_dates(30)], "played": [44, 30], "left": [40, 54]},
                     index=["VAN", "EDM"])
    edm = T.loc["EDM", "dates"]
    games = pd.DataFrame(
        [{"playerId": 1, "teamAbbrev": "VAN", "gameDate": d, "gamesStarted": 1} for d in T.loc["VAN", "dates"][:11]]
        # goalie 2: 20 starts in Vancouver, traded to Edmonton, started 2 of Edmonton's last 4 games
        + [{"playerId": 2, "teamAbbrev": "VAN", "gameDate": d, "gamesStarted": 1} for d in T.loc["VAN", "dates"][:20]]
        + [{"playerId": 2, "teamAbbrev": "EDM", "gameDate": d, "gamesStarted": s} for d, s in zip(edm[-4:], [1, 0, 1, 0])]
        # goalie 3: 15 starts in Vancouver, just traded to Edmonton, no game there yet
        + [{"playerId": 3, "teamAbbrev": "VAN", "gameDate": d, "gamesStarted": 1} for d in T.loc["VAN", "dates"][:15]])
    G = pd.DataFrame({"nhl_team": ["VAN", "EDM", "EDM"]}, index=[1, 2, 3])
    w = daily.goalie_team_starts(G, T, games)
    assert w.loc[1].tolist() == [11, 44]   # never traded: all his team's games
    assert w.loc[2].tolist() == [2, 4]     # traded: only Edmonton's games since his first one there
    assert w.loc[3].tolist() == [0, 0]     # no game with his new team yet: nothing real to go on
    # Games left for goalie 3 then rest on his projected share alone (0.5 here), not 15/30.
    out = daily.games_left(pd.Series(["G"], index=[3]), pd.Series([60.0], index=[3]), pd.Series([42.0], index=[3]),
                           84.0, pd.Series([54.0], index=[3]), w.loc[[3], "team_games"], w.loc[[3], "starts"],
                           pd.Series([None], index=[3]), CFG)
    assert out[3] == pytest.approx(54 * 0.5)


def test_bad_luck_skips_a_player_traded_that_week():
    D = _draft()
    def snap(day, tgp, team, hurt):
        players = {str(p): [0, 0, "IR" if hurt else None, 2.0, tgp, team] for p in D["playerId"]}
        return {"date": day, "players": players,
                "managers": {str(m): {"points": 0, "rank": m} for m in range(1, 13)}}
    # Everyone hurt all week and traded midweek: the jump from Vancouver's count to Edmonton's is not
    # counted, only the 2 Edmonton games missed after the trade (16 players x 2 games x 2 points).
    hist = [snap("2026-09-29", 0, "VAN", False), snap("2026-10-02", 2, "EDM", True), snap("2026-10-05", 4, "EDM", True)]
    [w] = daily.weekly_awards(hist, D, "2026-09-29", "2026-10-05", CFG)
    assert w["bad_luck"]["value"] == pytest.approx(16 * 2 * 2.0) and w["bad_luck"]["games"] == 32
    # Same players, same team all week: 4 missed games x 2 points.
    hist = [snap("2026-09-29", 0, "EDM", False), snap("2026-10-02", 2, "EDM", True), snap("2026-10-05", 4, "EDM", True)]
    [w] = daily.weekly_awards(hist, D, "2026-09-29", "2026-10-05", CFG)
    assert w["bad_luck"]["value"] == pytest.approx(16 * 4 * 2.0)


def test_week_games_counts_counted_healthy_players_left_this_week():
    D = _draft()
    people = D.set_index("playerId")[["name", "pos"]].assign(nhl_team="EDM", injury=None)
    # Wednesday Oct 7 2026 (week Mon 5 to Sun 11); EDM plays Mon, Wed, Fri, Sun, and next Tue.
    T = pd.DataFrame({"all_dates": [["2026-10-05", "2026-10-07", "2026-10-09", "2026-10-11", "2026-10-13"]]}, index=["EDM"])
    counts = set(D.loc[(D.manager_id == 1) & (D["round"].isin([1, 2, 9])), "playerId"])
    people.loc[D.loc[(D.manager_id == 1) & (D["round"] == 2), "playerId"], "injury"] = "IR"  # out: not counted
    w = daily.week_games(D, people, T, counts, today="2026-10-07", as_of="2026-10-06")
    assert (w["start"], w["end"]) == ("2026-10-05", "2026-10-11")
    assert w["managers"]["1"] == {"left": 2 * 3, "total": 2 * 4}   # 2 healthy counted players: Wed, Fri, Sun left
    assert w["managers"]["2"] == {"left": 0, "total": 0}           # nobody counted


def _snap(day, ranks, points, win, players=None):
    return {"date": day, "managers": {str(m): {"rank": ranks[m - 1], "points": points[m - 1], "win_pct": win[m - 1],
                                               "expected_total": 900} for m in range(1, 13)},
            "players": players or {}}


def test_headline_tells_the_story():
    D = _draft()
    people = D.set_index("playerId")[["name"]]
    r0 = list(range(1, 13))
    r1 = [2, 5, 3, 4, 1] + list(range(6, 13))  # team 5 jumps from 5th to 1st, team 1 drops to 2nd
    prev = _snap("2026-10-06", r0, [50] * 12, [10.0] * 12, {"105": [3, 2, None, 1, 2], "101": [0, 2, None, 1, 2]})
    cur = _snap("2026-10-07", r1, [52, 40, 45, 44, 55] + [30] * 7, [9.0, 8, 8, 8, 16.5] + [8] * 7,
                {"105": [8, 3, None, 1, 3], "101": [0, 2, "IR", 1, 3]})
    lines = daily.headline(cur, prev, D, people, evening=False)
    assert lines[0] == "M5 prend la tête du classement."
    assert "P1-5 (M1) : 5 points hier soir." in lines                   # player 105 went from 3 to 8
    assert any("passent de 10,0 % à 16,5 %" in x for x in lines)
    assert "P1-1 (M1) est maintenant blessé." in lines
    assert len(lines) <= 4 and daily.headline(cur, None, D, people, False) == []


def test_season_awards():
    D = _draft()
    pl = lambda pts, hurt=None, tgp=0, gp=0: {str(p): [pts.get(p, 0), gp, hurt if p == 102 else None, 1.5, tgp, "EDM"]
                                              for p in D["playerId"]}
    pre = _snap("2026-09-29", list(range(1, 13)), [0] * 12, [8.0] * 12, pl({}))
    d1 = _snap("2026-10-01", [1, 2] + list(range(3, 13)), [10, 8] + [5] * 10, [9.0] * 12, pl({112: 6, 201: 9, 101: 0}, "IR", 2))
    d2 = _snap("2026-10-02", [2, 1] + list(range(3, 13)), [12, 13] + [6] * 10, [9.0] * 12, pl({112: 7, 201: 12, 101: 0}, "IR", 4))
    a = {x["key"]: x for x in daily.season_awards([pre, d1, d2], D, CFG)}
    assert a["player"]["nhl_id"] == 201                        # most points
    assert a["pick"]["nhl_id"] == 112 and a["pick"]["round"] == 12
    assert a["bust"]["round"] <= 3
    assert a["bad_luck"]["manager_id"] == 1 and a["bad_luck"]["value"] == 4   # player 102 missed 2 + 2 games
    assert a["bad_luck"]["worst"] == {"nhl_id": 102, "games": 4}
    assert a["king"]["manager_id"] in (1, 2) and a["king"]["value"] == 1 and a["king"]["mornings"] == 2
    assert a["rollercoaster"]["value"] == 1                      # teams 1 and 2 swapped once
    assert daily.season_awards([pre], D, CFG) == []            # nothing before the first game


def test_checks_catch_a_drafted_player_without_a_known_team():
    D = _draft()
    teams = pd.Series("EDM", index=D["playerId"])
    assert _checks(teams=teams, nhl={"EDM", "TBL"}) == []
    teams.iloc[3] = "TB"  # the draft file's short code: no schedule would match
    assert any("without a known NHL team" in p and "'TB'" in p for p in _checks(teams=teams, nhl={"EDM", "TBL"}))
    assert daily.TEAM_ALIAS["TB"] == "TBL" and set(daily.TEAM_ALIAS.values()) <= {"TBL", "NJD", "LAK", "SJS"}


def test_pace_counts_games_played_and_games_left_of_counted_players():
    D = _draft()
    people = D.set_index("playerId")[["pos"]].assign(nhl_team=["EDM", "MTL"] * 96)
    T = pd.DataFrame({"left": [70, 60]}, index=["EDM", "MTL"])
    # Team 1: two counted players, one played 10 games for 12 pts, the other missed everything (hurt).
    a, b, bench = D.loc[D.manager_id == 1, "playerId"].iloc[[0, 1, 2]]
    real = pd.DataFrame({"GP": [10.0, 0.0, 10.0], "FP": [12.0, 0.0, 30.0]}, index=[a, b, bench])
    out = daily.pace(D, people, real, T, counts={a, b})
    t1 = out["1"]
    assert (t1["gp"], t1["points"], t1["ppg"]) == (10, 12, 1.2)  # the bench player's 30 points don't count
    assert t1["left"] == T.loc[people.loc[a, "nhl_team"], "left"] + T.loc[people.loc[b, "nhl_team"], "left"]
    assert out["2"]["ppg"] is None and out["2"]["left"] == 0   # nobody counted, no games yet
    assert sum(v["left_vs_avg"] for v in out.values()) in range(-12, 13)
