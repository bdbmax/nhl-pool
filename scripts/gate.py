"""Should this GitHub Actions run update the site, and how? Prints run=true/false and mode=morning/evening
for $GITHUB_OUTPUT.

GitHub cron has no time zones, so the workflow lists every UTC time that can be the right local time.
Mornings: the run scheduled at 5:xx in Toronto always updates (EDT or EST); 6:xx and 7:xx are retries that
update only if that morning's history file is not saved yet (5:xx failed or never started).
Evenings: runs scheduled between 22:00 and 23:29 in Toronto are evening updates (today's finished games,
site only); there are several, so a skipped or failed one is covered and later ones add games that ended
since. Their UTC times fall on the next UTC day. Manual runs are morning updates unless MODE says otherwise.
Standard library only (runs before Python is set up).
"""
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

TORONTO = ZoneInfo("America/Toronto")


def decide(event: str, schedule: str, now_utc: datetime, history: Path) -> tuple[bool, str]:
    run, why, _ = decide_mode(event, schedule, now_utc, history)
    return run, why


def decide_mode(event: str, schedule: str, now_utc: datetime, history: Path) -> tuple[bool, str, str]:
    if event != "schedule":
        return True, f"{event}: always runs", "morning"
    minute, hour = (int(x) for x in schedule.split()[:2])
    planned = now_utc.replace(hour=hour, minute=minute, second=0, microsecond=0).astimezone(TORONTO)
    saved = (history / f"{planned.date().isoformat()}.json").exists()
    label = planned.strftime("%H:%M %Z")
    if planned.hour == 5:
        return True, f"scheduled {label}: the morning update", "morning"
    if planned.hour in (6, 7):
        return (not saved), f"scheduled {label}: retry, today's update {'already saved' if saved else 'missing'}", "morning"
    if planned.hour == 22 or (planned.hour == 23 and planned.minute < 30):
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
