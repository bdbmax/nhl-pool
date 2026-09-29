"""The workflow gate: 5:30 Toronto year-round, retries at 6:30 and 7:30 only if the update is missing."""
import importlib.util
from datetime import datetime, timezone

from nhlpool.paths import ROOT

spec = importlib.util.spec_from_file_location("gate", ROOT / "scripts" / "gate.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

CRONS = ["30 9 * * *", "30 10 * * *", "30 11 * * *", "30 12 * * *"]


def runs(day: str, tmp_path, saved: bool = False, start_delay_min: int = 0):
    if saved:
        (tmp_path / f"{day}.json").write_text("{}")
    out = []
    for c in CRONS:
        h = int(c.split()[1])
        now = datetime.fromisoformat(f"{day}T{h:02d}:30:00").replace(tzinfo=timezone.utc)
        now = now.replace(minute=30 + start_delay_min) if start_delay_min < 30 else now
        out.append(gate.decide("schedule", c, now, tmp_path)[0])
    return out


def test_summer_first_morning(tmp_path):
    # Sept 30 2026 is EDT: 9:30 UTC = 5:30. Nothing saved yet -> main run plus both retries allowed.
    assert runs("2026-09-30", tmp_path) == [True, True, True, False]


def test_summer_after_success(tmp_path):
    assert runs("2026-09-30", tmp_path, saved=True) == [True, False, False, False]


def test_winter(tmp_path):
    # Dec 15 is EST: 10:30 UTC = 5:30; 9:30 UTC = 4:30 never runs.
    assert runs("2026-12-15", tmp_path) == [False, True, True, True]
    assert runs("2026-12-16", tmp_path, saved=True) == [False, True, False, False]


def test_dst_switch_days(tmp_path):
    # Nov 1 2026 clocks go back at 2:00, Mar 14 2027 forward: still exactly one 5:30 run.
    assert runs("2026-11-01", tmp_path, saved=True).count(True) == 1
    assert runs("2027-03-14", tmp_path, saved=True).count(True) == 1


def test_late_start_does_not_change_the_slot(tmp_path):
    assert runs("2026-09-30", tmp_path, saved=True, start_delay_min=25) == [True, False, False, False]


def test_manual_always_runs(tmp_path):
    assert gate.decide("workflow_dispatch", "", datetime.now(timezone.utc), tmp_path)[0]
