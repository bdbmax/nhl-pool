"""Name normalization for joining sources that do not share player ids."""
import re
import unicodedata

import pandas as pd

NICK = {"matthew": "matt", "mitchell": "mitch", "alexander": "alex", "alexandre": "alex", "nicholas": "nick",
        "nicolas": "nick", "zachary": "zach", "joshua": "josh", "michael": "mike", "christopher": "chris",
        "jacob": "jake", "joseph": "joe", "samuel": "sam", "maxime": "max", "maximilian": "max",
        "william": "will", "daniel": "dan", "anthony": "tony", "thomas": "tom", "benjamin": "ben",
        "timothy": "tim", "cameron": "cam", "frederick": "fred", "frederik": "fred", "pierre-olivier": "po",
        "jj": "j.j.", "tj": "t.j."}


def norm(name: str) -> str:
    s = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z\- ]", "", s.replace(".", "")).strip()
    s = re.sub(r"\s+", " ", s)
    parts = s.split(" ")
    if parts and parts[0] in NICK:
        parts[0] = NICK[parts[0]].replace(".", "")
    return " ".join(parts)


def last_name(name: str) -> str:
    return norm(name).split(" ")[-1]


def match(left: pd.DataFrame, right: pd.DataFrame, pos_col: str = "pos_group") -> pd.Series:
    """Map right-row index -> left index (playerId).

    Pass 1: exact normalized name (position breaks ties between namesakes).
    Pass 2, for name variants only (Zack/Zachary, accents, etc.): same last name,
    same position and same first initial, and only if that left player found no
    exact match and exactly one right row points to him. This keeps relatives
    (Jack vs Cameron Hughes, William vs Alexander Nylander) from being joined.
    """
    L = left.assign(_n=left["name"].map(norm), _l=left["name"].map(last_name))
    R = right.assign(_n=right["name"].map(norm), _l=right["name"].map(last_name))
    L["_i"] = L["_n"].str[:1]
    R["_i"] = R["_n"].str[:1]
    by_name = L.groupby("_n").groups
    has_pos = pos_col in R and pos_col in L
    out = {}
    for ridx, r in R.iterrows():
        cands = list(by_name.get(r["_n"], []))
        if len(cands) > 1 and has_pos:
            cands = [c for c in cands if L.loc[c, pos_col] == r[pos_col]] or cands
        if cands:
            out[ridx] = cands[0]
    taken = set(out.values())
    fallback = {}
    if has_pos:
        for ridx, r in R[~R.index.isin(list(out))].iterrows():
            same = L[(L["_l"] == r["_l"]) & (L[pos_col] == r[pos_col]) & (L["_i"] == r["_i"]) & ~L.index.isin(taken)]
            if "team" in R and "team" in L and len(same) > 1:
                same = same[same["team"] == r["team"]]
            if len(same) == 1:
                fallback.setdefault(same.index[0], []).append(ridx)
    for lid, ridxs in fallback.items():
        if len(ridxs) == 1:
            out[ridxs[0]] = lid
    return pd.Series(out, dtype="object")
