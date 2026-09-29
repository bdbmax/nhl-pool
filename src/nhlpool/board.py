"""Write output/board.html: the draft list embedded as JSON in a single file."""
import json

import numpy as np
import pandas as pd

from .config import load_league
from .fetch import nhl_api
from .paths import OUTPUT, TEMPLATES


def _num(x, d=2):
    return None if pd.isna(x) else round(float(x), d)


def write(min_fp: float = 3.0) -> str:
    league = load_league()
    df = pd.read_csv(OUTPUT / "draft_list.csv")
    df = df[df["proj_FP"] >= min_fp]
    sc = league["scoring"]
    players = []
    for r in df.itertuples():
        # ESPN's goals and assists under league scoring (ESPN projects no GWG or hat tricks).
        espn = None
        if r.pos != "G" and not pd.isna(r.espn_G):
            espn = sc[r.pos]["goal"] * r.espn_G + sc[r.pos]["assist"] * r.espn_A
        players.append({
            "id": int(r.playerId), "name": r.name, "pos": r.pos, "team": r.team, "age": _num(r.age, 1),
            "fp": _num(r.proj_FP, 1), "p10": _num(r.p10, 1), "p90": _num(r.p90, 1), "med": _num(r.median, 1),
            "rank": int(r.rank), "flags": "" if pd.isna(r.flags) else r.flags,
            "gp": _num(r.proj_GP, 1), "g": _num(r.proj_G), "a": _num(r.proj_A), "gwg": _num(r.proj_GWG),
            "ht": _num(r.proj_HT), "w": _num(r.proj_W), "otl": _num(r.proj_OTL), "so": _num(r.proj_SO),
            "share": _num(r.start_share, 3), "espn": _num(espn, 0) if espn is not None else None,
            "nhl": _num(r.nhlcom_PTS, 0), "pv": _num(r.public_value, 1),
            "oo": int(r.opp_order), "er": None if pd.isna(r.espn_rank) else int(r.espn_rank),
        })
    names = nhl_api.teams().set_index("team")["fullName"].to_dict()
    teams = sorted(df["team"].dropna().unique())
    logos, team_names = {}, {}
    for t in teams:
        team_names[t] = names.get(t, t)
        try:
            logos[t] = nhl_api.logo_svg(t)
        except Exception:
            pass  # board falls back to the abbreviation
    from .names import norm
    wanted = {norm(n) for n in league.get("watch", [])}
    default_watch = [int(r.playerId) for r in df.itertuples() if norm(r.name) in wanted]
    data = {
        "season": league["season"],
        "defaultWatch": default_watch,
        "teamNames": team_names,
        "logos": logos,
        "built": pd.Timestamp.today().strftime("%Y-%m-%d"),
        "maxfp": float(np.ceil(df["p90"].max() / 10) * 10),
        "league": {k: league[k] for k in ("teams", "my_pick", "draft_format", "drafted", "counted", "replacement_slots",
                                          "favorite_team", "favorite_bonus", "opponent_noise",
                                          "second_goalie_last")},
        "players": players,
    }
    blob = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    html = (TEMPLATES / "board.html").read_text().replace("__DATA__", blob)
    out = OUTPUT / "board.html"
    out.write_text(html)
    return f"wrote {out} ({len(players)} players, {len(html) / 1024:.0f} KB)"
