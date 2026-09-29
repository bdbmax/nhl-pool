"""B0: rank by last season's fantasy points (per-82 for shortened seasons)."""
import pandas as pd

from ..history import latest, opening_team, prev


def project(data: dict, season: int, universe: set | None = None) -> pd.DataFrame:
    frames = []
    for key, pos_col in (("skaters", "pos"), ("goalies", None)):
        df = data[key]
        ident = latest(df, season, ["name"] + ([pos_col] if pos_col else []))
        if pos_col is None:
            ident["pos"] = "G"
        last = df[df.seasonId == prev(season)].set_index("playerId")["FP82"]
        ident["proj_FP"] = last.reindex(ident.index).fillna(0.0)
        ident["team"] = opening_team(df, season).reindex(ident.index)
        frames.append(ident)
    out = pd.concat(frames)
    if universe is not None:
        out = out[out.index.isin(universe)]
    return out.rename_axis("playerId")
