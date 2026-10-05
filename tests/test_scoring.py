import pandas as pd

from nhlpool.scoring import fantasy_points

RULES = {
    "F": {"goal": 1, "assist": 1, "gwg": 1, "hat_trick": 1},
    "D": {"goal": 2, "assist": 1, "gwg": 1, "hat_trick": 0},
    "G": {"win": 2, "otl": 1, "shutout": 3, "goal": 10},
}


def test_forward_with_hat_trick():
    df = pd.DataFrame([{"pos": "F", "G": 48, "A": 90, "GWG": 4, "HT": 3}])
    assert fantasy_points(df, RULES).iloc[0] == 48 + 90 + 4 + 3


def test_defense_goals_double_and_no_hat_trick_bonus():
    df = pd.DataFrame([{"pos": "D", "G": 20, "A": 59, "GWG": 4, "HT": 1}])
    assert fantasy_points(df, RULES).iloc[0] == 40 + 59 + 4


def test_goalie():
    df = pd.DataFrame([{"pos": "G", "W": 23, "OTL": 11, "SO": 2}])
    assert fantasy_points(df, RULES).iloc[0] == 46 + 11 + 6


def test_goalie_goal_is_worth_10():
    df = pd.DataFrame([{"pos": "G", "W": 2, "OTL": 0, "SO": 0, "G": 1}])
    assert fantasy_points(df, RULES).iloc[0] == 4 + 10


def test_mixed_frame():
    df = pd.DataFrame(
        [
            {"pos": "F", "G": 1, "A": 1, "GWG": 0, "HT": 0},
            {"pos": "G", "W": 1, "OTL": 0, "SO": 1},
        ]
    )
    assert fantasy_points(df, RULES).tolist() == [2, 5]
