"""Check the update gate against the Toronto-time schedule in daily.yml."""
import importlib.util
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
import yaml

from nhlpool.paths import ROOT

spec = importlib.util.spec_from_file_location("gate", ROOT / "scripts" / "gate.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

TORONTO = ZoneInfo("America/Toronto")
workflow = yaml.safe_load((ROOT / ".github" / "workflows" / "daily.yml").read_text())
SCHEDULES = workflow[True]["schedule"]  # YAML reads the "on" key as True.

MORNINGS = [("05:33", "morning"), ("06:33", "morning"), ("07:33", "morning"), ("11:33", "morning")]
EVENINGS = [(f"{hour:02}:{minute:02}", "evening") for hour in [0, 1, *range(12, 24)] for minute in (5, 35)]


def start_in_toronto(when: str) -> datetime:
    return datetime.fromisoformat(when).replace(tzinfo=TORONTO).astimezone(timezone.utc)


@pytest.mark.parametrize("day", ["2026-09-30", "2026-11-01", "2026-12-15", "2027-03-14"])
@pytest.mark.parametrize("saved", [True, False])
def test_schedule_in_toronto(day, saved, tmp_path):
    if saved:
        (tmp_path / f"{day}.json").write_text("{}")
    observed = []
    for slot in SCHEDULES:
        assert slot["timezone"] == TORONTO.key
        minutes, hour = slot["cron"].split()[:2]
        for minute in minutes.split(","):
            assert int(minute) != 0
            label = f"{int(hour):02}:{int(minute):02}"
            start = start_in_toronto(f"{day}T{label}") + timedelta(minutes=25)
            run, _, mode = gate.decide_mode("schedule", slot["cron"], start, tmp_path)
            if run:
                observed.append((label, mode))
    assert sorted(observed) == sorted((MORNINGS[:1] if saved else MORNINGS) + EVENINGS)


def test_manual_runs(tmp_path):
    now = datetime.now(timezone.utc)
    assert gate.decide_mode("workflow_dispatch", "", now, tmp_path) == (True, "workflow_dispatch: always runs", "morning")


def test_late_evening_runs(tmp_path):
    slot = "5,35 22 * * *"
    timely = start_in_toronto("2026-09-29T22:40")
    assert gate.decide_mode("schedule", slot, timely, tmp_path)[::2] == (True, "evening")
    late = start_in_toronto("2026-09-30T04:56")
    run, why, mode = gate.decide_mode("schedule", slot, late, tmp_path)
    assert not run and mode == "evening" and "too late" in why


def test_late_morning_runs_only_if_that_morning_is_missing(tmp_path):
    late = start_in_toronto("2026-09-30T09:10")
    assert gate.decide_mode("schedule", "33 5 * * *", late, tmp_path)[0]
    (tmp_path / "2026-09-30.json").write_text("{}")
    assert not gate.decide_mode("schedule", "33 5 * * *", late, tmp_path)[0]


def test_late_morning_respects_toronto_date(tmp_path):
    slot = "33 7 * * *"
    same_day = start_in_toronto("2026-12-15T19:20")  # already December 16 in UTC
    run, why, mode = gate.decide_mode("schedule", slot, same_day, tmp_path)
    assert run and mode == "morning" and "07:33" in why and "late" in why
    next_day = start_in_toronto("2026-12-16T00:20")
    assert not gate.decide_mode("schedule", slot, next_day, tmp_path)[0]
