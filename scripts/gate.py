"""Should this GitHub Actions run update the site? Prints run=true/false for $GITHUB_OUTPUT.

The workflow is scheduled at 9:30, 10:30, 11:30 and 12:30 UTC because GitHub cron has no time zones.
The run whose scheduled time is 5:30 in Toronto always updates (EDT or EST). The ones at 6:30 and 7:30
Toronto are retries: they update only if that morning's history file is not saved yet (the 5:30 run failed
or never started). Manual runs always update. Standard library only (runs before Python is set up).
"""
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

TORONTO = ZoneInfo("America/Toronto")


def decide(event: str, schedule: str, now_utc: datetime, history: Path) -> tuple[bool, str]:
    if event != "schedule":
        return True, f"{event}: always runs"
    minute, hour = (int(x) for x in schedule.split()[:2])
    planned = now_utc.replace(hour=hour, minute=minute, second=0, microsecond=0).astimezone(TORONTO)
    saved = (history / f"{planned.date().isoformat()}.json").exists()
    label = planned.strftime("%H:%M %Z")
    if planned.hour == 5:
        return True, f"scheduled {label}: the morning update"
    if planned.hour in (6, 7):
        return (not saved), f"scheduled {label}: retry, today's update {'already saved' if saved else 'missing'}"
    return False, f"scheduled {label}: not a 5:30 to 7:30 slot"


if __name__ == "__main__":
    run, why = decide(os.environ.get("EVENT", ""), os.environ.get("SCHEDULE", ""), datetime.now(timezone.utc),
                      Path(sys.argv[1] if len(sys.argv) > 1 else "data/history"))
    print(why, file=sys.stderr)
    print(f"run={'true' if run else 'false'}")
