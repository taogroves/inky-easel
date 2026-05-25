"""Build comparison payloads for the Me and You display."""

from __future__ import annotations

import asyncio
import re
from datetime import date, datetime, timezone
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from .weather import fetch_weather

if TYPE_CHECKING:
    from ..models import Frame


_HANDLE_RE = re.compile(r"^[a-z0-9-]{3,64}$")


def normalize_frame_handle(value: Any) -> str | None:
    handle = str(value or "").strip().lower()
    if not _HANDLE_RE.fullmatch(handle):
        return None
    return handle


def _timezone(name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(name or "UTC")
    except Exception:
        return ZoneInfo("UTC")


def _local_now(timezone_name: str | None) -> datetime:
    return datetime.now(_timezone(timezone_name))


def _offset_minutes(timezone_name: str | None) -> int:
    now = _local_now(timezone_name)
    offset = now.utcoffset()
    return int(offset.total_seconds() // 60) if offset else 0


def _duration_label(total_minutes: int) -> str:
    minutes = abs(total_minutes)
    hours, remainder = divmod(minutes, 60)
    parts: list[str] = []
    if hours:
        parts.append(f"{hours}h")
    if remainder:
        parts.append(f"{remainder}m")
    return " ".join(parts) or "0h"


def _time_difference_label(other_name: str, current_timezone: str | None, other_timezone: str | None) -> str:
    diff = _offset_minutes(other_timezone) - _offset_minutes(current_timezone)
    if diff == 0:
        return "Same time zone"
    direction = "ahead" if diff > 0 else "behind"
    return f"{other_name} is {_duration_label(diff)} {direction}"


def _days_apart(config: dict[str, Any], timezone_name: str | None) -> int:
    try:
        base = int(config.get("days_apart_value") or 0)
    except (TypeError, ValueError):
        base = 0
    raw_as_of = str(config.get("days_apart_as_of") or "").strip()
    try:
        as_of = date.fromisoformat(raw_as_of)
    except ValueError:
        as_of = _local_now(timezone_name).date()
    today = _local_now(timezone_name).date()
    return base + (today - as_of).days


def _weather_summary(payload: dict[str, Any]) -> dict[str, Any]:
    current = payload.get("current") or {}
    return {
        "temperature": current.get("temperature"),
        "description": current.get("description") or "Unknown",
        "units": payload.get("units") or "celsius",
    }


async def build_me_and_you_payload(
    current_frame: "Frame",
    other_frame: "Frame",
    config: dict[str, Any] | None,
) -> dict[str, Any]:
    cfg = config or {}
    other_name = str(cfg.get("other_person_name") or "").strip() or "Friend"
    units = str(cfg.get("units") or "celsius").lower()
    if units not in {"celsius", "fahrenheit"}:
        units = "celsius"

    current_now = _local_now(current_frame.timezone)
    other_now = _local_now(other_frame.timezone)
    current_weather, other_weather = await asyncio.gather(
        fetch_weather(current_frame.latitude, current_frame.longitude, current_frame.timezone, units),
        fetch_weather(other_frame.latitude, other_frame.longitude, other_frame.timezone, units),
    )

    return {
        "title": f"{other_name} + You",
        "other_name": other_name,
        "current": {
            "label": "You",
            "handle": current_frame.name,
            "latitude": current_frame.latitude,
            "longitude": current_frame.longitude,
            "timezone": current_frame.timezone,
            "time": current_now.strftime("%H:%M"),
            "date": current_now.strftime("%b %-d"),
            "weather": _weather_summary(current_weather),
        },
        "other": {
            "label": other_name,
            "handle": other_frame.name,
            "latitude": other_frame.latitude,
            "longitude": other_frame.longitude,
            "timezone": other_frame.timezone,
            "time": other_now.strftime("%H:%M"),
            "date": other_now.strftime("%b %-d"),
            "weather": _weather_summary(other_weather),
        },
        "time_difference": _time_difference_label(other_name, current_frame.timezone, other_frame.timezone),
        "days_apart": _days_apart(cfg, current_frame.timezone),
        "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
