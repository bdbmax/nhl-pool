"""ESPN public fantasy API: 2026-27 projections (statSourceId=1)."""
import json

import pandas as pd

from .http import cached_json

URL = (
    "https://lm-api-reads.fantasy.espn.com/apis/v3/games/fhl/seasons/{yr}"
    "/segments/0/leaguedefaults/1?view=kona_player_info"
)
# Verified against NHL actuals for 2025-26 (McDavid, Makar, MacKinnon, Hellebuyck).
SKATER = {"13": "G", "14": "A", "16": "PTS", "22": "GWG", "28": "HAT", "30": "GP"}
GOALIE = {"0": "GS", "1": "W", "2": "L", "7": "SO", "9": "OTL", "30": "GP"}
POS = {1: "C", 2: "L", 3: "R", 4: "D", 5: "G"}


def projections(end_year: int = 2027, refresh: bool = False) -> pd.DataFrame:
    flt = {"players": {"filterStatsForSourceIds": {"value": [1]}, "limit": 3000,
                       "sortPercOwned": {"sortPriority": 1, "sortAsc": False}}}
    d = cached_json(URL.format(yr=end_year), f"espn/projections_{end_year}.json", refresh=refresh,
                    headers={"X-Fantasy-Filter": json.dumps(flt)})
    rows = []
    for item in d["players"]:
        p = item["player"]
        pos = POS.get(p.get("defaultPositionId"))
        stats = next((s["stats"] for s in p.get("stats", [])
                      if s["seasonId"] == end_year and s["statSourceId"] == 1 and s["statSplitTypeId"] == 0), None)
        if not stats or pos is None:
            continue
        m = GOALIE if pos == "G" else SKATER
        own = p.get("ownership") or {}
        rank = ((p.get("draftRanksByRankType") or {}).get("STANDARD") or {}).get("rank")
        row = {"espn_id": p["id"], "name": p["fullName"], "pos": pos, "pct_owned": own.get("percentOwned"),
               # ESPN's default draft-room order (autodraft follows it) and average draft position.
               "espn_rank": rank or None, "espn_adp": own.get("averageDraftPosition")}
        row.update({f"espn_{v}": stats.get(k) for k, v in m.items()})
        rows.append(row)
    return pd.DataFrame(rows)
