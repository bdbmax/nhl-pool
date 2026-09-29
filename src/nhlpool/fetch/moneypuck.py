"""MoneyPuck season summaries (free CSV downloads). Season label = start year."""
import io

import pandas as pd

from .http import cached_text

BASE = "https://moneypuck.com/moneypuck/playerData/seasonSummary"


def season_summary(year: int, kind: str) -> pd.DataFrame:
    """kind in {'skaters','goalies','teams'}; year 2025 means 2025-26."""
    text = cached_text(f"{BASE}/{year}/regular/{kind}.csv", f"moneypuck/{kind}_{year}.csv")
    return pd.read_csv(io.StringIO(text))


def fetch_history(first: int = 2010, last: int = 2025) -> None:
    for y in range(first, last + 1):
        for k in ("skaters", "goalies", "teams"):
            season_summary(y, k)
        print(f"  moneypuck {y} ok")


def lines(year: int) -> pd.DataFrame:
    """Line combinations with ice time (5on5 lines and pairings). lineId concatenates 7-digit player ids."""
    text = cached_text(f"{BASE}/{year}/regular/lines.csv", f"moneypuck/lines_{year}.csv")
    return pd.read_csv(io.StringIO(text))
