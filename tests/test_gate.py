"""The workflow gate: mornings at 5:33 Toronto year-round (retries at 6:33 and 7:33 only if the update is
missing), evenings at 22:05, 22:35 and 23:05. Checked against the schedule lines in daily.yml themselves."""
import importlib.util
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import yaml

from nhlpool.paths import ROOT

spec = importlib.util.spec_from_file_location("gate", ROOT / "scripts" / "gate.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

TORONTO = ZoneInfo("America/Toronto")
workflow = yaml.safe_load((ROOT / ".github" / "workflows" / "daily.yml").read_text())
CRONS = [c["cron"] for c in workflow[True]["schedule"]]   # YAML reads the "on" key as True


def local_day(day: str, tmp_path, saved: bool = False, delay_min: int = 0) -> list[tuple[str, str]]:
    """Every run the gate lets through for Toronto day `day`: (local HH:MM, mode)."""
    if saved:
        (tmp_path / f"{day}.json").write_text("{}")
    d = datetime.fromisoformat(day)
    out = []
    for c in CRONS:
        minute, hour = (int(x) for x in c.split()[:2])
        # The UTC day on which this cron fires for Toronto day `day`: evening crons fire on the next UTC day.
        for utc_day in (d, d + timedelta(days=1)):
            planned = datetime(utc_day.year, utc_day.month, utc_day.day, hour, minute, tzinfo=timezone.utc)
            local = planned.astimezone(TORONTO)
            if local.date().isoformat() != day:
                continue
            run, _, mode = gate.decide_mode("schedule", c, planned + timedelta(minutes=delay_min), tmp_path)
            if run:
                out.append((local.strftime("%H:%M"), mode))
    return sorted(out)


EVENINGS = [("22:05", "evening"), ("22:35", "evening"), ("23:05", "evening")]


def test_summer_day(tmp_path):
    # Sept 30 2026 is EDT. Nothing saved yet: the morning run and both retries may go.
    assert local_day("2026-09-30", tmp_path) == [("05:33", "morning"), ("06:33", "morning"), ("07:33", "morning")] + EVENINGS


def test_summer_day_after_a_good_morning(tmp_path):
    assert local_day("2026-09-30", tmp_path, saved=True) == [("05:33", "morning")] + EVENINGS


def test_winter_day(tmp_path):
    assert local_day("2026-12-15", tmp_path, saved=True) == [("05:33", "morning")] + EVENINGS
    assert local_day("2026-12-16", tmp_path) == [("05:33", "morning"), ("06:33", "morning"), ("07:33", "morning")] + EVENINGS


def test_dst_switch_days(tmp_path):
    # Nov 1 2026 clocks go back at 2:00, Mar 14 2027 forward: still one morning run and the three evenings.
    for day in ("2026-11-01", "2027-03-14", "2027-03-15"):
        assert local_day(day, tmp_path, saved=True) == [("05:33", "morning")] + EVENINGS, day


def test_late_start_does_not_change_the_slot(tmp_path):
    # GitHub can start a scheduled run late; the gate goes by the scheduled time, not the start time.
    assert local_day("2026-09-30", tmp_path, saved=True, delay_min=25) == [("05:33", "morning")] + EVENINGS


def test_no_cron_on_the_hour():
    # GitHub delays and drops scheduled runs at :00 most; none of ours are there.
    assert all(c.split()[0] not in ("0", "00") for c in CRONS)


def test_manual_runs(tmp_path):
    now = datetime.now(timezone.utc)
    assert gate.decide_mode("workflow_dispatch", "", now, tmp_path) == (True, "workflow_dispatch: always runs", "morning")
    assert gate.decide("workflow_dispatch", "", now, tmp_path)[0]


def test_what_happened_on_sept_30(tmp_path):
    # The 22:35 slot (cron 35 2 UTC) started at 8:56 UTC (4:56 Toronto): it must not run as an evening update.
    run, why, mode = gate.decide_mode("schedule", "35 2 * * *", datetime(2026, 9, 30, 8, 56, tzinfo=timezone.utc), tmp_path)
    assert not run and mode == "evening" and "too late" in why
    # An evening slot on time still runs.
    assert gate.decide_mode("schedule", "35 2 * * *", datetime(2026, 9, 30, 2, 40, tzinfo=timezone.utc), tmp_path)[:3:2] == (True, "evening")


def test_late_morning_runs_only_if_the_morning_is_missing(tmp_path):
    late = datetime(2026, 9, 30, 13, 10, tzinfo=timezone.utc)   # the 5:33 slot starting at 9:10 Toronto
    assert gate.decide_mode("schedule", "33 9 * * *", late, tmp_path)[0]          # nothing saved: run
    (tmp_path / "2026-09-30.json").write_text("{}")
    assert not gate.decide_mode("schedule", "33 9 * * *", late, tmp_path)[0]      # saved: leave it
    on_time = datetime(2026, 9, 30, 9, 40, tzinfo=timezone.utc)
    assert gate.decide_mode("schedule", "33 9 * * *", on_time, tmp_path)[0]       # on time: run anyway


def test_run_starting_after_midnight_utc(tmp_path):
    # The 7:33 EST retry (cron 33 12 UTC) delayed past midnight UTC still belongs to the day it was due.
    run, why, _ = gate.decide_mode("schedule", "33 12 * * *", datetime(2026, 12, 16, 0, 20, tzinfo=timezone.utc), tmp_path)
    assert run and "07:33" in why and "late" in why
