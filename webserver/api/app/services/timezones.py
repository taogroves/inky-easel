"""Timezone helpers for frame-local rendering.

Frame timestamps are stored as UTC datetimes in the database. A frame's
configured location is the source of truth for its display timezone.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from timezonefinder import TimezoneFinder

DEFAULT_TIMEZONE = "UTC"


@lru_cache(maxsize=1)
def _finder() -> TimezoneFinder:
    return TimezoneFinder()


def validate_timezone(name: str | None) -> str | None:
    if not name:
        return None
    try:
        ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return None
    return name


def timezone_for_location(latitude: float | None, longitude: float | None) -> str | None:
    if latitude is None or longitude is None:
        return None
    if not math.isfinite(latitude) or not math.isfinite(longitude):
        return None
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        return None

    finder = _finder()
    name = finder.timezone_at(lat=latitude, lng=longitude)
    if name is None:
        name = finder.certain_timezone_at(lat=latitude, lng=longitude)
    return validate_timezone(name)


def infer_timezone(
    latitude: float | None,
    longitude: float | None,
    fallback: str | None = None,
) -> str:
    return timezone_for_location(latitude, longitude) or validate_timezone(fallback) or DEFAULT_TIMEZONE


def localize_datetime(value: datetime, timezone_name: str | None) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.astimezone(ZoneInfo(validate_timezone(timezone_name) or DEFAULT_TIMEZONE))
