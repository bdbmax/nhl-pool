"""The daily update's math: rate updates, games left, safety checks and award dates."""
from datetime import date

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
    # Only two late picks scored this week: 109 (round 9 of team 1, 4 points), then 212 (round 12 of team 2, 2).
    assert [(x["nhl_id"], x["value"]) for x in w["pick"]] == [(109, 4), (212, 2)]
    assert w["comeback"][0]["manager_id"] == 12 and len(w["comeback"]) == 3   # from 12th to 1st, then 11th, 10th
    assert [x["manager_id"] for x in w["drought"]] == [1, 2, 3]               # fewest points gained first
    assert w["bad_luck"][0]["manager_id"] == 1                               # player 105 missed games while hurt


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
    assert w["bad_luck"][0]["value"] == pytest.approx(16 * 2 * 2.0) and w["bad_luck"][0]["games"] == 32
    # Same players, same team all week: 4 missed games x 2 points.
    hist = [snap("2026-09-29", 0, "EDM", False), snap("2026-10-02", 2, "EDM", True), snap("2026-10-05", 4, "EDM", True)]
    [w] = daily.weekly_awards(hist, D, "2026-09-29", "2026-10-05", CFG)
    assert w["bad_luck"][0]["value"] == pytest.approx(16 * 4 * 2.0)


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
    lines = daily.headline(cur, prev, D, people, "hier")
    assert lines[0] == "M5 prend la tête du classement."
    assert "P1-5 (M1) : 5 points de pool hier." in lines                   # player 105 went from 3 to 8
    assert any("passent de 10,0 % à 16,5 %" in x for x in lines)
    assert "P1-1 (M1) est maintenant blessé." in lines
    assert len(lines) <= 4 and daily.headline(cur, None, D, people, "hier") == []
    assert "P1-5 (M1) : 5 points de pool depuis ce matin." in daily.headline(cur, prev, D, people, "depuis ce matin")


def test_since_says_since_when_in_words():
    d = date(2026, 10, 7)
    morning = lambda day: {"date": day}
    assert daily.since(False, morning("2026-10-06"), d) == "depuis hier"
    assert daily.since(False, morning("2026-10-04"), d) == "depuis la dernière mise à jour"   # mornings missed
    assert daily.since(True, morning("2026-10-07"), d) == "depuis ce matin"                  # 14:05, 22:35
    assert daily.since(True, morning("2026-10-06"), d) == "depuis hier matin"               # 0:35, before 5:35
    assert daily.since(True, morning("2026-10-05"), d) == "depuis la dernière mise à jour"
    assert daily.since(True, None, d) == daily.since(False, None, d) == ""


def test_season_awards():
    D = _draft()
    pl = lambda pts, hurt=None, tgp=0, gp=0: {str(p): [pts.get(p, 0), gp, hurt if p == 102 else None, 1.5, tgp, "EDM"]
                                              for p in D["playerId"]}
    pre = _snap("2026-09-29", list(range(1, 13)), [0] * 12, [8.0] * 12, pl({}))
    d1 = _snap("2026-10-01", [1, 2] + list(range(3, 13)), [10, 8] + [5] * 10, [9.0] * 12, pl({112: 6, 201: 9, 101: 0}, "IR", 2))
    d2 = _snap("2026-10-02", [2, 1] + list(range(3, 13)), [12, 13] + [6] * 10, [9.0] * 12, pl({112: 7, 201: 12, 101: 0}, "IR", 4))
    a = {x["key"]: x["podium"] for x in daily.season_awards([pre, d1, d2], D, CFG)}
    assert [x["nhl_id"] for x in a["player"]][:2] == [201, 112]   # most points: 12, then 7
    assert a["pick"][0]["nhl_id"] == 112 and a["pick"][0]["round"] == 12
    assert all(x["round"] <= 3 for x in a["bust"]) and len(a["bust"]) == 3
    assert a["bad_luck"][0]["manager_id"] == 1 and a["bad_luck"][0]["value"] == 4   # player 102 missed 2 + 2 games
    assert a["bad_luck"][0]["worst"] == {"nhl_id": 102, "games": 4}
    assert {x["manager_id"] for x in a["king"]} == {1, 2} and all(x["value"] == 1 and x["mornings"] == 2 for x in a["king"])
    assert [x["value"] for x in a["rollercoaster"]] == [1, 1]  # teams 1 and 2 swapped once
    # Banc en or: team 2's 12 points from player 201 count (best forward); team 1's 7 from player 112 (round 12, a D)
    # count too; nobody else scored, so the bench is empty everywhere and there is no award.
    assert "bench" not in a
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


def test_bench_award_counts_points_left_on_the_bench():
    D = _draft()
    # Team 3: its 8 forwards (rounds 1-8) scored 10, 9, ..., 3; only the best 6 count, so 4 + 3 = 7 sit on the bench.
    fwd = D[(D.manager_id == 3) & (D.pos == "F")].sort_values("round")["playerId"].tolist()
    pts = {pid: 10 - i for i, pid in enumerate(fwd)}
    players = {str(p): [pts.get(p, 0), 1, None, 1.0, 1, "EDM"] for p in D["playerId"]}
    best_ball = 10 + 9 + 8 + 7 + 6 + 5
    snap = _snap("2026-10-02", list(range(1, 13)), [best_ball if m == 3 else 0 for m in range(1, 13)], [8.0] * 12, players)
    a = {x["key"]: x["podium"] for x in daily.season_awards([snap], D, CFG)}
    assert a["bench"] == [{"manager_id": 3, "value": 7, "best": {"nhl_id": fwd[6], "points": 4}}]


def test_counted_players_follow_pool_points_then_projection():
    D = _draft()
    g1, g2 = D.loc[(D.manager_id == 1) & (D.pos == "G"), "playerId"]
    fwd = D.loc[(D.manager_id == 1) & (D.pos == "F"), "playerId"].tolist()
    points = pd.Series({g2: 2.0, fwd[7]: 1.0})   # the second goalie won his start; the 8th forward has an assist
    final = pd.Series({g1: 70.6, g2: 70.3, **{p: 100.0 - i for i, p in enumerate(fwd)}})
    counts = daily.counted_players(D, points, final)
    assert g2 in counts and g1 not in counts     # 2 points beat a better projection
    assert {p for p in fwd if p in counts} == {*fwd[:5], fwd[7]}   # the rest are tied at 0: best projections
    # The counted players' points add up to the standings.
    x = D.assign(v=D["playerId"].map(points).fillna(0.0))
    assert x[x.playerId.isin(counts)].groupby("manager_id")["v"].sum().to_dict() == daily.best_ball(D, points).to_dict()
    # Before the first game: the projection alone.
    assert {p for p in fwd if p in daily.counted_players(D, pd.Series(dtype=float), final)} == set(fwd[:6])


def test_bench_award_breaks_ties_like_the_badges():
    D = _draft()
    # Team 3: 7 forwards with 1 point each; the one with the worst projection (round 1 here) sits on the bench.
    fwd = D[(D.manager_id == 3) & (D.pos == "F")].sort_values("round")["playerId"].tolist()
    players = {str(p): [1 if p in fwd[:7] else 0, 1, None, 1.0, 1, "EDM"] for p in D["playerId"]}
    snap = _snap("2026-10-02", list(range(1, 13)), [6 if m == 3 else 0 for m in range(1, 13)], [8.0] * 12, players)
    final = pd.Series({p: 50.0 + i for i, p in enumerate(fwd)})
    a = {x["key"]: x["podium"] for x in daily.season_awards([snap], D, CFG, final)}
    assert a["bench"] == [{"manager_id": 3, "value": 1, "best": {"nhl_id": fwd[0], "points": 1}}]


def test_tonight_lists_players_with_a_game_today_counted_first():
    D = _draft()
    people = D.set_index("playerId")[["pos"]].assign(nhl_team="MTL")
    people.loc[D.loc[D.manager_id == 1, "playerId"].iloc[:2], "nhl_team"] = "EDM"
    T = pd.DataFrame({"games": [[{"date": "2026-10-01", "opp": "TOR", "home": True, "start": "2026-10-01T23:00:00Z"}],
                                [{"date": "2026-10-02", "opp": "BOS", "home": False, "start": "2026-10-02T23:00:00Z"}]]},
                     index=["EDM", "MTL"])
    a, b = D.loc[D.manager_id == 1, "playerId"].iloc[:2]
    out = daily.tonight(D, people, T, counts={b}, today="2026-10-01")
    assert [(r["nhl_id"], r["counts"], r["opp"], r["home"]) for r in out["managers"]["1"]] == [(b, True, "TOR", True), (a, False, "TOR", True)]
    assert out["managers"]["2"] == []   # Montreal does not play that day


def test_race_says_when_the_chaser_catches_up():
    M = pd.DataFrame({"points": [100, 90, 50], "rank": [1, 2, 3]}, index=[1, 2, 3])
    T = pd.DataFrame({"all_dates": [["2026-10-01", "2026-10-29"]]}, index=["EDM"])  # 28 days left after Oct 1
    pace_ = {"1": {"ppg": 1.0, "left": 280}, "2": {"ppg": 1.5, "left": 280}, "3": {"ppg": 1.0, "left": 280}}
    r = daily.race(M, pace_, T, as_of="2026-10-01")
    # Team 2 scores 15/day vs 10/day for team 1: a 10-point gap closes in 2 days.
    assert r["2"]["ahead"]["manager_id"] == 1 and r["2"]["ahead"]["gap"] == 10 and r["2"]["catch_weeks"] == round(2 / 7, 1)
    assert r["1"]["ahead"] is None and r["1"]["caught_weeks"] == round(2 / 7, 1)
    assert r["3"]["catch_weeks"] is None   # 40 behind team 2, and slower: not at this pace


def test_hot_cold_compares_real_points_with_the_projection():
    D = _draft()
    def snap(day, pts, gp):
        return {"date": day, "managers": {}, "players": {str(p): [pts.get(p, 0), gp.get(p, 0), None, 1.0, gp.get(p, 0), "EDM"]
                                                         for p in D["playerId"]}}
    hot, cold = D["playerId"].iloc[0], D["playerId"].iloc[1]
    h = daily.hot_cold([snap("2026-10-01", {}, {}), snap("2026-10-08", {hot: 7, cold: 0}, {hot: 3, cold: 3})], D)
    assert h["hot"][0] == {"nhl_id": int(hot), "points": 7, "games": 3, "expected": 3.0, "diff": 4.0}
    assert h["cold"][0]["nhl_id"] == int(cold) and h["cold"][0]["diff"] == -3.0
    assert daily.hot_cold([snap("2026-10-01", {}, {})], D) is None


def test_player_weeks_keeps_mondays_and_the_latest_morning():
    D = _draft()
    snaps = [{"date": d, "managers": {}, "players": {str(p): [i, 0, None, 1, 0] for p in D["playerId"]}}
             for i, d in enumerate(["2026-09-29", "2026-10-04", "2026-10-05", "2026-10-06"])]
    w = daily.player_weeks(snaps, D)
    assert w["dates"] == ["2026-09-29", "2026-10-05", "2026-10-06"]   # opening day, Monday Oct 5, latest
    assert w["points"][str(D["playerId"].iloc[0])] == [0, 2, 3]


def test_evening_waits_for_games_whose_stats_are_not_published(monkeypatch):
    from nhlpool.fetch import nhl_api
    # Game 1 is over and in the stats; game 2 is over on the scoreboard but its lines are not published yet.
    monkeypatch.setattr(nhl_api, "skater_games_on", lambda s, d: pd.DataFrame({"gameId": [1, 1, 3]}))
    monkeypatch.setattr(nhl_api, "goalie_games_to_date", lambda s, d: pd.DataFrame({"gameId": [1, 1, 7]}))
    assert daily.stats_ready(20262027, "2026-09-29", {1, 2}) == {1}
    monkeypatch.setattr(nhl_api, "skater_games_on", lambda s, d: pd.DataFrame())
    assert daily.stats_ready(20262027, "2026-09-29", {1}) == set()


def test_team_games_can_skip_games(monkeypatch):
    from nhlpool.fetch import nhl_api
    g = lambda i, state, a="EDM", h="TOR", sa=2, sh=3: {"id": i, "gameDate": "2026-09-29", "gameState": state,
                                                       "awayTeam": {"abbrev": a, "score": sa}, "homeTeam": {"abbrev": h, "score": sh}}
    games = {"EDM": [g(1, "OFF"), g(2, "OFF", "EDM", "MTL")], "TOR": [g(1, "OFF")], "MTL": [g(2, "OFF", "EDM", "MTL")]}
    monkeypatch.setattr(nhl_api, "current_team_abbrevs", lambda: list(games))
    monkeypatch.setattr(nhl_api, "schedule", lambda t, s, refresh=True: games[t])
    T, league = daily.team_games(20262027, "2026-09-29", skip={2})
    assert T.loc["EDM", "played"] == 1 and T.loc["MTL", "played"] == 0 and league["games"] == 1 and league["goals"] == 5
    assert league["finished_on_as_of"] == {1}


def test_evening_day_after_midnight(monkeypatch):
    from datetime import datetime as real_dt
    class Late(real_dt):
        @classmethod
        def now(cls, tz=None):
            return real_dt(2026, 9, 30, 0, 40, tzinfo=tz)
    monkeypatch.setattr(daily, "datetime", Late)
    assert str(daily.evening_day()) == "2026-09-29"   # a 22:00 run that started at 0:40 is still about the 29th
    class OnTime(real_dt):
        @classmethod
        def now(cls, tz=None):
            return real_dt(2026, 9, 29, 22, 10, tzinfo=tz)
    monkeypatch.setattr(daily, "datetime", OnTime)
    assert str(daily.evening_day()) == "2026-09-29"


def test_evening_stats_on_opening_night_with_no_earlier_games(monkeypatch):
    # Tonight's case: nothing played before today, so the season totals up to yesterday are empty.
    from nhlpool.fetch import nhl_api
    empty = lambda *a: pd.DataFrame()
    for f in ("skaters_to_date", "goalies_to_date", "hat_tricks_to_date"):
        monkeypatch.setattr(nhl_api, f, empty)
    sk = pd.DataFrame([
        {"gameId": 1, "playerId": 10, "skaterFullName": "A", "positionCode": "C", "gamesPlayed": 1, "goals": 3, "assists": 1, "gameWinningGoals": 1},
        {"gameId": 1, "playerId": 11, "skaterFullName": "B", "positionCode": "D", "gamesPlayed": 1, "goals": 1, "assists": 0, "gameWinningGoals": 0},
        {"gameId": 2, "playerId": 12, "skaterFullName": "C", "positionCode": "L", "gamesPlayed": 1, "goals": 2, "assists": 0, "gameWinningGoals": 0}])
    gl = pd.DataFrame([{"gameId": 1, "gameDate": "2026-09-29", "playerId": 20, "goalieFullName": "G", "gamesPlayed": 1,
                        "gamesStarted": 1, "wins": 1, "otLosses": 0, "shutouts": 0}])
    monkeypatch.setattr(nhl_api, "skater_games_on", lambda s, d: sk)
    monkeypatch.setattr(nhl_api, "goalie_games_to_date", lambda s, d: gl)
    R = daily.real_stats(20262027, "2026-09-29", finished_today={1})   # game 2 still being played
    assert R["GP"].dtype == float and R["FP"].dtype == float
    assert R.loc[10, "FP"] == 3 + 1 + 1 + 1   # hat trick bonus
    assert R.loc[11, "FP"] == 2               # a defenseman's goal counts double
    assert R.loc[20, "FP"] == 2 and 12 not in R.index
