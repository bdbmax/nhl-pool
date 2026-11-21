"""Choose whether and how to update the site from a Toronto-time GitHub Actions schedule."""
import os
import sys
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

TORONTO = ZoneInfo("America/Toronto")
LATE = timedelta(hours=2)


def decide(event: str, schedule: str, now_utc: datetime, history: Path) -> tuple[bool, str]:
    run, why, _ = decide_mode(event, schedule, now_utc, history)
    return run, why


def decide_mode(event: str, schedule: str, now_utc: datetime, history: Path) -> tuple[bool, str, str]:
    if event != "schedule":
        return True, f"{event}: always runs", "morning"
    minute_field, hour = schedule.split()[:2]
    now = now_utc.astimezone(TORONTO)
    # Each cron covers one local hour. Keep its date and mode even when GitHub starts late.
    slots = [
        datetime.combine(day, time(int(hour), int(minute), fold=fold), TORONTO).astimezone(timezone.utc)
        for day in (now.date(), now.date() - timedelta(days=1))
        for minute in minute_field.split(",")
        for fold in (0, 1)
    ]
    due = max(slot for slot in slots if slot <= now_utc)
    late = now_utc - due > LATE
    planned = due.astimezone(TORONTO)
    saved = (history / f"{planned.date().isoformat()}.json").exists()
    label = planned.strftime("%H:%M %Z") + (f", started {int((now_utc - due).total_seconds() // 60)} min late" if late else "")
    if planned.hour in (5, 6, 7, 11):
        if planned.date() != now.date():
            return False, f"scheduled {label}: the next morning's schedule covers it", "morning"
        if not saved:
            return True, f"scheduled {label}: the morning update (not saved yet)", "morning"
        if planned.hour == 5 and not late:
            return True, f"scheduled {label}: the morning update", "morning"
        return False, f"scheduled {label}: this morning's update is already saved", "morning"
    if planned.hour >= 12 or planned.hour <= 1:
        if late:
            return False, f"scheduled {label}: too late for an evening update (the morning update covers it)", "evening"
        return True, f"scheduled {label}: an evening update", "evening"
    return False, f"scheduled {label}: not an update slot", "morning"


if __name__ == "__main__":
    run, why, mode = decide_mode(os.environ.get("EVENT", ""), os.environ.get("SCHEDULE", ""),
                                 datetime.now(timezone.utc), Path(sys.argv[1] if len(sys.argv) > 1 else "data/history"))
    if os.environ.get("EVENT") != "schedule" and os.environ.get("MODE") in ("morning", "evening"):
        mode = os.environ["MODE"]  # a manual run can ask for either
    print(why, file=sys.stderr)
    print(f"run={'true' if run else 'false'}")
    print(f"mode={mode}")
