"""Entry point.

  uv run python run.py fetch      # download/cache all historical data (idempotent)
  uv run python run.py build      # build processed tables + reconciliation checks
  uv run python run.py tune       # re-tune model parameters on TUNE seasons
  uv run python run.py backtest   # baseline vs model on tuning seasons (add --validate for held-out)
  uv run python run.py project    # 2026-27 projections -> output/draft_list.csv  (add --refresh)
  uv run python run.py board      # output/board.html from the draft list
  uv run python run.py all        # project + board
  uv run python run.py serve      # draft night: opens the board, saves every pick to data/drafts.sqlite
"""
import argparse
import subprocess
import sys

import pandas as pd

pd.set_option("display.width", 250)


def cmd_fetch(a):
    from nhlpool.fetch import moneypuck, nhl_api
    nhl_api.fetch_history()
    moneypuck.fetch_history()
    r = nhl_api.all_rosters(20262027, refresh=a.refresh)
    from nhlpool.paths import PROCESSED
    r.to_csv(PROCESSED / "rosters_20262027.csv", index=False)


def cmd_build(a):
    from nhlpool import dataset
    d = dataset.build()
    print(dataset.checks(d).to_string(index=False))


def cmd_tune(a):
    subprocess.run([sys.executable, "scripts/tune_b1.py"], check=True)


def cmd_backtest(a):
    from nhlpool import report
    report.write(validate=a.validate)


def cmd_project(a):
    from nhlpool import draftlist
    df = draftlist.build(refresh=a.refresh)
    cols = ["rank", "name", "pos", "team", "age", "proj_FP", "vorp", "p10", "p90", "flags"]
    print(df[cols].head(40).to_string(index=False))


def cmd_board(a):
    from nhlpool import board
    print(board.write())


def cmd_serve(a):
    from nhlpool import serve
    host = a.host or ("0.0.0.0" if a.phone else "127.0.0.1")
    serve.run(host=host, port=a.port, open_browser=not a.no_open)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["fetch", "build", "tune", "backtest", "project", "board", "all", "serve"])
    ap.add_argument("--refresh", action="store_true", help="re-download current-season sources")
    ap.add_argument("--validate", action="store_true", help="also score the held-out seasons")
    ap.add_argument("--phone", action="store_true", help="serve: also allow a phone on the same Wi-Fi to connect")
    ap.add_argument("--host", default=None, help="serve: advanced, overrides --phone")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--no-open", action="store_true", help="serve: do not open the browser automatically")
    a = ap.parse_args()
    if a.cmd == "all":
        cmd_project(a)
        cmd_board(a)
    else:
        globals()[f"cmd_{a.cmd}"](a)


if __name__ == "__main__":
    main()
