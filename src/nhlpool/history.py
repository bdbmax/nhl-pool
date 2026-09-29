"""Assemble each player's recent history as seen from before target season N.

Everything here uses only seasons strictly before N. The one piece of season-N
information used is the opening team (first team a player appears for in N),
which is known on opening night; it is used only for team context, never as a
feature of the player's own production or games played.
"""
import numpy as np
import pandas as pd

from .paths import PROCESSED


def prev(season: int, k: int = 1) -> int:
    start = season // 10000 - k
    return start * 10000 + start + 1


def active_next(sk: pd.DataFrame, gl: pd.DataFrame, season: int) -> set[int]:
    """Players who played in season N or N+1 (or are on a 2026-27 roster).

    Used only to drop players who had retired or left the NHL before season N,
    which is public knowledge preseason. Injured-all-season players stay in
    (they come back in N+1) and score 0, as they would for a real drafter.
    """
    ids = set()
    for df in (sk, gl):
        ids |= set(df.loc[df.seasonId.isin([season, prev(season, -1)]), "playerId"])
    if season >= 20252026:
        r = pd.read_csv(PROCESSED / "rosters_20262027.csv")
        ids |= set(r.playerId)
    return ids


def wide_history(df: pd.DataFrame, season: int, cols: list[str], n: int = 3) -> pd.DataFrame:
    """One row per player with columns f'{col}_{k}' for k=1..n seasons back.

    Also returns established_k: True if the player had any NHL season before
    N-k, so a missing season N-k is a real zero (injury, demotion) rather than
    a pre-debut gap.
    """
    hist = df[df.seasonId < season]
    first_season = hist.groupby("playerId")["seasonId"].min()
    out = None
    for k in range(1, n + 1):
        s = prev(season, k)
        part = hist[hist.seasonId == s].set_index("playerId")[cols].add_suffix(f"_{k}")
        out = part if out is None else out.join(part, how="outer")
    out = out if out is not None else pd.DataFrame()
    out["first_season"] = first_season.reindex(out.index)
    for k in range(1, n + 1):
        out[f"established_{k}"] = out["first_season"] < prev(season, k)
        out[f"present_{k}"] = out[f"GP_{k}"].notna() if f"GP_{k}" in out else False
    return out


def latest(df: pd.DataFrame, season: int, cols: list[str]) -> pd.DataFrame:
    """Most recent pre-N row per player for identity fields (name, pos, birthDate)."""
    hist = df[df.seasonId < season].sort_values("seasonId")
    return hist.groupby("playerId")[cols].last()


def opening_team(df: pd.DataFrame, season: int) -> pd.Series:
    """First team in season N if the player played in N, else last team of N-1."""
    cur = df[df.seasonId == season].set_index("playerId")["first_team"]
    last = df[df.seasonId < season].sort_values("seasonId").groupby("playerId")["last_team"].last()
    return cur.combine_first(last)


def age_in(season: int, birth: pd.Series) -> pd.Series:
    mid = pd.Timestamp(f"{season % 10000}-02-01")
    return (mid - pd.to_datetime(birth)).dt.days / 365.25


def weighted(values: list[pd.Series], weights: list[float]) -> tuple[pd.Series, pd.Series]:
    """Sum of w*v and sum of w over non-missing entries."""
    num = sum(w * v.fillna(0.0) for v, w in zip(values, weights))
    den = sum(w * v.notna().astype(float) for v, w in zip(values, weights))
    return num, den


def safe_div(a, b):
    return np.where(b > 0, a / np.where(b > 0, b, 1.0), 0.0)
