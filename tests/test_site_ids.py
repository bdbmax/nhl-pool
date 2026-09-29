"""Every player exported to the website has three positive, unique, real IDs."""
import json

import pytest

from nhlpool.paths import ROOT

POOL = ROOT / "site" / "data" / "pool.json"


@pytest.mark.skipif(not POOL.exists(), reason="run `python -m nhlpool.site_export` first")
def test_all_players_have_positive_unique_ids():
    d = json.loads(POOL.read_text())
    players = d["players"] + d["forgotten"]
    assert len(d["players"]) == 192
    for key in ("nhl_id", "espn_id", "df_id"):
        vals = [p[key] for p in players]
        assert all(isinstance(v, int) and v > 0 for v in vals), key
        assert len(set(vals)) == len(vals), f"duplicate {key}"
    assert all(p["photo"] and str(p["nhl_id"]) in p["photo"] for p in players)
    assert sorted({p["manager_id"] for p in d["players"]}) == list(range(1, 13))
