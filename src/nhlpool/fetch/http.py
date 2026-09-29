"""Cached HTTP. Every response is written under data/raw and reused on rerun.

Historical seasons never change, so they are cached forever. Current-season
sources (rosters, lines, projections) pass refresh=True to re-download.
"""
import json
import time
from pathlib import Path

import requests

from ..paths import RAW

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
_session = requests.Session()
_session.headers.update({"User-Agent": UA})
_last_call = [0.0]
MIN_INTERVAL = 0.25  # seconds between network calls, to be polite


def _get(url: str, headers: dict | None = None, retries: int = 6) -> requests.Response:
    for attempt in range(retries):
        wait = MIN_INTERVAL - (time.time() - _last_call[0])
        if wait > 0:
            time.sleep(wait)
        _last_call[0] = time.time()
        try:
            r = _session.get(url, headers=headers, timeout=60)
            if r.status_code == 200:
                return r
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(2 ** attempt)
                continue
            r.raise_for_status()
        except requests.RequestException:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError(f"failed after {retries} tries: {url}")


def cached_text(url: str, rel_path: str, refresh: bool = False, headers: dict | None = None) -> str:
    path: Path = RAW / rel_path
    if path.exists() and not refresh:
        return path.read_text()
    text = _get(url, headers=headers).text
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return text


def cached_json(url: str, rel_path: str, refresh: bool = False, headers: dict | None = None):
    return json.loads(cached_text(url, rel_path, refresh=refresh, headers=headers))
