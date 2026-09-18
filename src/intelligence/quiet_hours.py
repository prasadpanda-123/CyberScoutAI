"""
Quiet Hours and Timezone Evaluator for CyberScout AI (Phase 7).

Evaluates whether the current local time in a user's configured timezone
falls within quiet hours, deferring immediate notifications until permissible hours.
"""

from datetime import datetime, time, timezone
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from src.core.logging import get_logger

logger = get_logger(__name__)


def parse_time_str(val: Optional[str], default_hour: int, default_minute: int) -> time:
    """Safely parses 'HH:MM' string to datetime.time."""
    if not val:
        return time(default_hour, default_minute)
    try:
        parts = str(val).strip().split(":")
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
        return time(max(0, min(23, hour)), max(0, min(59, minute)))
    except Exception:
        return time(default_hour, default_minute)


def is_in_quiet_hours(
    *args,
    now_dt: Optional[datetime] = None,
    now_utc: Optional[datetime] = None,
    tz_str: str = "UTC",
    quiet_hours_start: str = "22:00",
    quiet_hours_end: str = "08:00",
    quiet_hours_enabled: bool = True,
    **kwargs,
) -> bool:
    """
    Determines if the given or current timestamp falls within the user's quiet hours window.
    Supports both keyword-based and positional calling conventions:
      is_in_quiet_hours(now_dt, tz_str, start, end, enabled)
      is_in_quiet_hours(start, end, tz_str, now_utc=...)
    """
    if not quiet_hours_enabled:
        return False

    ref_utc = now_utc or now_dt or kwargs.get("now_dt")
    start_str = quiet_hours_start
    end_str = quiet_hours_end
    target_tz_str = tz_str

    if args:
        if isinstance(args[0], datetime):
            ref_utc = args[0]
            if len(args) > 1 and isinstance(args[1], str):
                target_tz_str = args[1]
            if len(args) > 2 and isinstance(args[2], str):
                start_str = args[2]
            if len(args) > 3 and isinstance(args[3], str):
                end_str = args[3]
        elif isinstance(args[0], str):
            start_str = args[0]
            if len(args) > 1 and isinstance(args[1], str):
                end_str = args[1]
            if len(args) > 2 and isinstance(args[2], str):
                target_tz_str = args[2]
            if len(args) > 3 and isinstance(args[3], datetime):
                ref_utc = args[3]

    if ref_utc is None:
        ref_utc = datetime.now(timezone.utc)
    elif ref_utc.tzinfo is None:
        ref_utc = ref_utc.replace(tzinfo=timezone.utc)

    # Resolve target timezone
    try:
        user_tz = ZoneInfo(target_tz_str or "UTC")
    except (ZoneInfoNotFoundError, ValueError, Exception):
        logger.debug(f"Invalid timezone '{tz_str}', falling back to UTC.")
        user_tz = timezone.utc

    user_local_dt = ref_utc.astimezone(user_tz)
    current_time = user_local_dt.time()

    start_t = parse_time_str(quiet_hours_start, 22, 0)
    end_t = parse_time_str(quiet_hours_end, 8, 0)

    # If start and end are equal, quiet hours are effectively 0 duration
    if start_t == end_t:
        return False

    # Overnight range: e.g. 22:00 -> 08:00
    if start_t > end_t:
        return current_time >= start_t or current_time < end_t
    # Same-day range: e.g. 13:00 -> 15:00
    else:
        return start_t <= current_time < end_t
