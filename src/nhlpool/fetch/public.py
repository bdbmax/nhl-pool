"""Free public projections and market numbers parsed from articles."""
import html as htmllib
import re

import pandas as pd

from .http import cached_text

UA_NOTE = "Parsed from public web pages. Re-check by eye; layouts change."


def nhlcom_points(refresh: bool = False) -> pd.DataFrame:
    url = "https://www.nhl.com/news/nhl-points-projections-fantasy-hockey-2026-27"
    raw = cached_text(url, "public/nhlcom_points_2026.html", refresh=refresh)
    text = htmllib.unescape(re.sub(r"<[^>]+>", " ", raw))
    rows = re.findall(r"([A-Z][A-Za-z\.'\- ]+?), ([FD]), ([A-Z]{3}): (\d+)", text)
    df = pd.DataFrame(rows, columns=["name", "pos_group", "team", "nhlcom_PTS"])
    df["name"] = df["name"].str.strip()
    df["nhlcom_PTS"] = df["nhlcom_PTS"].astype(int)
    return df.drop_duplicates(["name", "team"])


def market_point_totals(refresh: bool = False) -> pd.DataFrame:
    """2026-27 season point over/unders (gambling911 table: team, last year, this year, change)."""
    url = "https://www.gambling911.com/2026-2027-nhl-totals-for-every-team-futures-odds"
    raw = cached_text(url, "public/gambling911_totals_2026.html", refresh=refresh)
    text = htmllib.unescape(re.sub(r"<[^>]+>", " ", raw))
    text = re.sub(r"\s+", " ", text)
    rows = re.findall(r"([A-Z][A-Za-z\.]+(?: [A-Z][A-Za-z\.]+){0,2}) (\d{2,3}\.5) (\d{2,3}\.5) ([+-−]?\s?\d+)", text)
    df = pd.DataFrame(rows, columns=["team_name", "prev_total", "point_total", "change"])
    df["point_total"] = df["point_total"].astype(float)
    return df.drop_duplicates("team_name")
