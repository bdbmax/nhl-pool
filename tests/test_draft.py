import pandas as pd

from nhlpool.draft import best_ball, snake_order


def test_snake_order():
    o = snake_order(3, 3)
    assert o == [0, 1, 2, 2, 1, 0, 0, 1, 2]


def test_best_ball_counts_only_top_n():
    v = pd.Series([10, 50, 30, 5, 80, 60])
    pos = pd.Series(["F", "F", "F", "D", "D", "G"])
    # best 2 F (50+30), best 1 D (80), best 1 G (60)
    assert best_ball(v, pos, {"F": 2, "D": 1, "G": 1}) == 220
