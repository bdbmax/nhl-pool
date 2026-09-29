"""Cross-source player IDs for the drafted players.

Every drafted player gets three positive IDs:
  nhl_id   NHL stats and web APIs (also MoneyPuck, which uses the same ids)
  espn_id  ESPN fantasy API (injury status, projections)
  df_id    Daily Faceoff (projected lines, injured reserve)
Matching is by normalized name and position, then verified: IDs must be unique,
names must agree exactly after normalization, and positions must agree.
"""
import glob
import json
import re

import pandas as pd

from .names import match, norm
from .paths import RAW

ESPN_POS = {1: "F", 2: "F", 3: "F", 4: "D", 5: "G"}


def espn_players() -> pd.DataFrame:
    raw = json.loads((RAW / "espn" / "projections_2027.json").read_text())["players"]
    return pd.DataFrame([{"espn_id": p["player"]["id"], "name": p["player"]["fullName"],
                          "pos_group": ESPN_POS.get(p["player"].get("defaultPositionId")),
                          "espn_injury": p["player"].get("injuryStatus")} for p in raw])


def df_players() -> pd.DataFrame:
    """One row per Daily Faceoff player. Position comes from his line or pairing slot
    (f1-f4, d1-d3, g); players listed only on injured reserve or special teams get none."""
    rows = []
    for f in glob.glob(str(RAW / "dailyfaceoff" / "*.html")):
        m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', open(f).read(), re.S)
        if not m:
            continue
        c = json.loads(m.group(1))["props"]["pageProps"]["combinations"]
        for p in c["players"]:
            g = p["groupIdentifier"]
            pos = "G" if g == "g" else ("F" if re.fullmatch(r"f\d", g) else ("D" if re.fullmatch(r"d\d", g) else None))
            rows.append({"df_id": p["playerId"], "name": p["name"], "pos_group": pos,
                         "df_injury": p.get("injuryStatus"), "df_ir": g == "ir"})
    df = pd.DataFrame(rows)
    agg = df.groupby("df_id").agg(name=("name", "first"), pos_group=("pos_group", lambda x: next((v for v in x if v), None)),
                                  df_injury=("df_injury", lambda x: next((v for v in x if v), None)), df_ir=("df_ir", "any"))
    return agg.reset_index()


def build(players: pd.DataFrame) -> pd.DataFrame:
    """players: index nhl playerId, columns name, team, pos (F/D/G)."""
    left = players.assign(pos_group=players["pos"])[["name", "team", "pos_group"]]
    out = players.copy()
    for src, key, extra in ((espn_players(), "espn_id", ["espn_injury"]), (df_players(), "df_id", ["df_injury", "df_ir"])):
        src = src.copy()
        src["playerId"] = match(left, src).reindex(src.index)
        src = src.dropna(subset=["playerId"]).astype({"playerId": int})
        # Prefer the candidate whose position agrees, then drop duplicates.
        mine = left["pos_group"].reindex(src["playerId"]).values
        src["pos_ok"] = [None if pd.isna(sp) else sp == mp for sp, mp in zip(src["pos_group"], mine)]
        src = src.sort_values("pos_ok", ascending=False).drop_duplicates("playerId").set_index("playerId")
        out[key] = src[key].reindex(out.index)
        out[f"{key}_name"] = src["name"].reindex(out.index)
        out[f"{key}_pos_ok"] = src["pos_ok"].reindex(out.index)
        for col in extra:
            out[col] = src[col].reindex(out.index)
    return out


def check(ids: pd.DataFrame) -> list[str]:
    problems = []
    for key in ("espn_id", "df_id"):
        col = ids[key]
        if col.isna().any():
            problems += [f"{key} missing: {n}" for n in ids.loc[col.isna(), "name"]]
        if (col.dropna() <= 0).any():
            problems.append(f"{key} not positive")
        dup = col.dropna()[col.dropna().duplicated(keep=False)]
        problems += [f"{key} {int(v)} shared by {', '.join(ids.loc[dup[dup == v].index, 'name'])}" for v in dup.unique()]
        bad = ids[ids[f"{key}_name"].map(lambda x: norm(x) if isinstance(x, str) else "") != ids["name"].map(norm)]
        problems += [f"{key} name differs: {r['name']} vs {r[f'{key}_name']}" for _, r in bad.iterrows()]
        problems += [f"{key} position differs: {n}" for n in ids.loc[ids[f"{key}_pos_ok"].eq(False), "name"]]
    if (ids.index <= 0).any() or ids.index.duplicated().any():
        problems.append("nhl_id not positive or not unique")
    return problems
