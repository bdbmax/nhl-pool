"""Daily Faceoff projected line combinations (current season only, not archived).

Each team page embeds Next.js JSON with every player's slot:
f1..f4 forward lines, d1..d3 pairs, g (g1 starter, g2 backup), pp1/pp2, pk1/pk2, ir.
"""
import json
import re

import pandas as pd

from .http import cached_text

URL = "https://www.dailyfaceoff.com/teams/{slug}/line-combinations"
NEXT_RE = re.compile(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S)


def _page(slug: str, refresh: bool) -> dict:
    html = cached_text(URL.format(slug=slug), f"dailyfaceoff/{slug}.html", refresh=refresh)
    return json.loads(NEXT_RE.search(html).group(1))["props"]["pageProps"]


def team_slugs(refresh: bool = False) -> list[dict]:
    return _page("edmonton-oilers", refresh)["sortedTeams"]


def lines(refresh: bool = False) -> pd.DataFrame:
    rows = []
    for t in team_slugs(refresh):
        c = _page(t["slug"], refresh)["combinations"]
        for p in c["players"]:
            rows.append(
                {
                    "team": t["shortName"],
                    "name": p["name"],
                    "group": p["groupIdentifier"],
                    "slot": p["positionIdentifier"],
                    "injury": p.get("injuryStatus"),
                    "updated": c.get("updatedAt"),
                }
            )
    df = pd.DataFrame(rows)
    # One row per player: ev line/pair, goalie slot, pp unit, injured flag.
    out = []
    for (team, name), g in df.groupby(["team", "name"], sort=False):
        groups = set(g["group"])
        ev = next((x for x in g["group"] if x[0] in "fd" and x[1:].isdigit()), None)
        gslot = next((s for grp, s in zip(g["group"], g["slot"]) if grp == "g"), None)
        out.append(
            {
                "team": team,
                "name": name,
                "df_line": ev,
                "df_goalie": gslot,
                "df_pp": "pp1" if "pp1" in groups else ("pp2" if "pp2" in groups else None),
                "df_ir": "ir" in groups,
                "df_injury": next((i for i in g["injury"] if i), None),
                "df_updated": g["updated"].iloc[0],
            }
        )
    return pd.DataFrame(out)
