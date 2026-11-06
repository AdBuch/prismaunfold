"""Edition windows per time zone (IANA zones, so DST and odd offsets like +05:45 are handled)."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

UTC = timezone.utc
DEFAULT_HOURS = (0, 6, 12, 18)


def _local(day: date, hour: int, tz: ZoneInfo) -> datetime:
    """Wall-clock boundary as an aware datetime. Skips forward if the wall time does not exist."""
    candidate = datetime(day.year, day.month, day.day, hour, tzinfo=tz)
    round_trip = candidate.astimezone(UTC).astimezone(tz).replace(tzinfo=None)
    if round_trip != candidate.replace(tzinfo=None):
        candidate = candidate + timedelta(hours=1)
    return candidate


def edition_window(
    now: datetime, tz_name: str, hours: tuple[int, ...] = DEFAULT_HOURS
) -> tuple[datetime, datetime]:
    """Return (start, end) in UTC of the edition window that contains `now`."""
    tz = ZoneInfo(tz_name)
    local_day = now.astimezone(tz).date()
    points = sorted(
        _local(local_day + timedelta(days=offset), hour, tz).astimezone(UTC)
        for offset in (-1, 0, 1)
        for hour in hours
    )
    start = max(p for p in points if p <= now)
    end = min(p for p in points if p > now)
    return start, end


def edition_label(start: datetime, tz_name: str) -> str:
    return f"{start.astimezone(ZoneInfo(tz_name)):%Y-%m-%d %H:%M} {tz_name}"
