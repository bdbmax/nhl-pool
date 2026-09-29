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
            rows.append({"manager_id": m, "round": r, "overall": (r - 1) * 12 + m, "pos": pos,
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
