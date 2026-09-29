"""More public 2026-27 projections, used only to rate the drafted teams (scripts/rate_teams.py).

CBS Sports: rest-of-season projections, top 100 per position (C, W, D) and 68 goalies.
  Every skater is projected for ~81 games, so use its per-game rates.
HockeyBangers: the free player pages (hockeybangers.com/<slug>), goals and assists per
  82 games, skaters only. The full board is a paid product and is not used.
Both are cached under data/raw like every other download.
"""
import html as htmllib
import re
import time

import pandas as pd

from ..names import norm
from ..paths import RAW
from .http import cached_text

CBS = "https://www.cbssports.com/fantasy/hockey/stats/{pos}/2026/restofseason/projections/"
HB = "https://hockeybangers.com/"


def _cells(row: str) -> list[str]:
    return [re.sub(r"\s+", " ", re.sub("<[^>]+>", " ", c)).strip() for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]


def _num(x: str) -> float:
    try:
        return float(x.replace(",", ""))
    except ValueError:
        return float("nan")


def cbs(refresh: bool = False) -> pd.DataFrame:
    rows = []
    for pos in ("C", "W", "D", "G"):
        h = cached_text(CBS.format(pos=pos), f"cbs/proj_2026_{pos}.html", refresh=refresh)
        head = [re.sub(r"\s+", " ", re.sub("<[^>]+>", "", x)).strip().split(" ")[0]
                for x in re.findall(r"<th[^>]*>(.*?)</th>", h, re.S)]
        for tr in re.findall(r'<tr class="TableBase-bodyTr[^"]*">(.*?)</tr>', h, re.S):
            c = _cells(tr)
            # "N. MacKinnon C COL Nathan MacKinnon C COL": the full name is the second half.
            words = c[0].split(" ")
            name = " ".join(words[len(words) // 2:-2])
            r = {"name": name, "cbs_pos": "G" if pos == "G" else ("D" if pos == "D" else "F")}
            r.update({k: _num(v) for k, v in zip(head[1:], c[1:])})
            rows.append(r)
    df = pd.DataFrame(rows).rename(columns={"gp": "cbs_GP", "g": "cbs_G", "a": "cbs_A", "gw": "cbs_GWG",
                                            "gs": "cbs_GS", "w": "cbs_W", "l": "cbs_L", "so": "cbs_SO"})
    df["cbs_OTL"] = (df["cbs_GS"] - df["cbs_W"] - df["cbs_L"]).clip(lower=0)  # L is regulation losses
    return df


def _utf8(x: str) -> str:
    """The site sends UTF-8 without a charset, so cached text can be mis-decoded as Latin-1."""
    try:
        return x.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return x


def hockeybangers(names: list[str], refresh: bool = False) -> pd.DataFrame:
    """Goals and assists per 82 games for the given skaters (one free page each, fetched politely)."""
    try:
        index = cached_text(HB + "players/", "hockeybangers/players_index.html", refresh=refresh)
    except Exception as e:  # site down and nothing cached: the other three sources carry on
        print(f"WARNING hockeybangers unavailable ({type(e).__name__}); skipped")
        return pd.DataFrame(columns=["name", "hb_G82", "hb_A82"])
    slug = {norm(_utf8(htmllib.unescape(n))): s for s, n in re.findall(r'<a[^>]*href="([a-z0-9-]+)"[^>]*>([^<]+)</a>', index)}
    rows, failures = [], 0
    for n in names:
        s = slug.get(norm(n))
        if not s:
            continue
        rel = f"hockeybangers/{s}.html"
        fresh = not (RAW / rel).exists()
        try:
            # After 3 failed pages, stop re-downloading and use what is cached (the site is down).
            h = cached_text(HB + s, rel, refresh=refresh and failures < 3)
        except Exception as e:
            failures += 1
            print(f"  hockeybangers: {n} failed ({type(e).__name__})")
            if not (RAW / rel).exists():
                continue
            h = cached_text(HB + s, rel)
        if fresh:
            time.sleep(0.75)
        t = re.sub("<(script|style)[^>]*>.*?</\\1>", " ", h, flags=re.S)
        t = re.sub(r"(\s*\|\s*)+", " | ", re.sub("<[^>]+>", " | ", re.sub(r"\s+", " ", t)))
        m = re.search(r"\| G \| (\d+) \| A \| (\d+) \| PPP \| (\d+)", t)
        if m:
            rows.append({"name": n, "hb_G82": float(m.group(1)), "hb_A82": float(m.group(2))})
    return pd.DataFrame(rows)
