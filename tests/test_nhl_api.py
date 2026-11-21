import json
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest

from nhlpool.fetch import http, nhl_api


def mock_pages(monkeypatch, tmp_path, pages):
    monkeypatch.setattr(http, "RAW", tmp_path)
    offsets = []

    def fetch(url):
        offset = int(parse_qs(urlsplit(url).query)["start"][0])
        offsets.append(offset)
        return SimpleNamespace(json=lambda: pages[offset])

    monkeypatch.setattr(nhl_api, "_get", fetch)
    return offsets


def test_player_totals_include_every_page(monkeypatch, tmp_path):
    first = [{"playerId": pid} for pid in range(1, 101)]
    offsets = mock_pages(monkeypatch, tmp_path, {
        0: {"data": first, "total": 101},
        100: {"data": [{"playerId": 101}], "total": 101},
    })

    stats = nhl_api.skaters_to_date(20262027, "2026-11-20")

    assert offsets == [0, 100]
    assert stats["playerId"].tolist() == list(range(1, 102))
    cache = tmp_path / "nhl_rest/to_date/skater_summary_20262027_2026-11-20.json"
    assert json.loads(cache.read_text()) == {"data": stats.to_dict("records"), "total": 101}


@pytest.mark.parametrize("cached_total", [1, 2])
def test_overlapping_pages_only_allow_a_complete_cache(monkeypatch, tmp_path, cached_total):
    row = {"playerId": 1}
    mock_pages(monkeypatch, tmp_path, {
        0: {"data": [row], "total": 2},
        1: {"data": [row], "total": 2},
    })
    cache = tmp_path / "nhl_rest/to_date/skater_summary_20262027_2026-11-20.json"
    cache.parent.mkdir(parents=True)
    original = json.dumps({"data": [row], "total": cached_total})
    cache.write_text(original)

    if cached_total == 1:
        assert nhl_api.skaters_to_date(20262027, "2026-11-20")["playerId"].tolist() == [1]
    else:
        with pytest.raises(RuntimeError, match="1 of 2 rows"):
            nhl_api.skaters_to_date(20262027, "2026-11-20")
    assert cache.read_text() == original


def test_game_rows_allow_the_same_player_in_different_games(monkeypatch, tmp_path):
    first = {"gameId": 1, "playerId": 1}
    second = {"gameId": 2, "playerId": 1}
    mock_pages(monkeypatch, tmp_path, {
        0: {"data": [first], "total": 2},
        1: {"data": [second], "total": 2},
    })

    assert nhl_api.goalie_games_to_date(20262027, "2026-11-20").to_dict("records") == [first, second]
