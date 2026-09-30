"""Should this GitHub Actions run update the site, and how? Prints run=true/false and mode=morning/evening
for $GITHUB_OUTPUT.

GitHub cron has no time zones, so the workflow lists every UTC time that can be the right local time.
Mornings: the run scheduled at 5:xx in Toronto always updates (EDT or EST); 6:xx and 7:xx are retries that
update only if that morning's history file is not saved yet (5:xx failed or never started).
Evenings: runs scheduled between 22:00 and 23:29 in Toronto are evening updates (today's finished games,
site only); there are several, so a skipped or failed one is covered and later ones add games that ended
since. Their UTC times fall on the next UTC day. Manual runs are morning updates unless MODE says otherwise.

GitHub can start scheduled runs hours late (on Sept 30, 2026 the 22:35 evening slot started at 4:56). So:
an evening slot more than 2 hours late does nothing (the next morning covers those games), and a morning
slot runs whenever that morning's update is still missing, but a late one (2+ hours) never redoes a
morning that is already saved.
Standard library only (runs before Python is set up).
"""
import os
import sys
from datetime import datetime, timedelta, timezone
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
    minute, hour = (int(x) for x in schedule.split()[:2])
    # The most recent time this cron was due (a run can start hours late, even past midnight UTC).
    due = now_utc.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if due > now_utc:
        due -= timedelta(days=1)
    late = now_utc - due > LATE
    planned = due.astimezone(TORONTO)
    saved = (history / f"{planned.date().isoformat()}.json").exists()
    label = planned.strftime("%H:%M %Z") + (f", started {int((now_utc - due).total_seconds() // 60)} min late" if late else "")
    if planned.hour in (5, 6, 7):
        if not saved:
            return True, f"scheduled {label}: the morning update (not saved yet)", "morning"
        if planned.hour == 5 and not late:
            return True, f"scheduled {label}: the morning update", "morning"
        return False, f"scheduled {label}: this morning's update is already saved", "morning"
    if planned.hour == 22 or (planned.hour == 23 and planned.minute < 30):
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
