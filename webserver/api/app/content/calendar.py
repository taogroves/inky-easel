"""Fetch and summarize events from an iCalendar feed."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx


@dataclass
class CalendarEvent:
    summary: str
    starts_at: datetime
    ends_at: datetime | None = None
    all_day: bool = False


def _unfold_lines(body: str) -> list[str]:
    lines: list[str] = []
    for raw in body.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if raw.startswith((" ", "\t")) and lines:
            lines[-1] += raw[1:]
        else:
            lines.append(raw)
    return lines


def _unescape(value: str) -> str:
    return (
        value
        .replace(r"\n", "\n")
        .replace(r"\N", "\n")
        .replace(r"\,", ",")
        .replace(r"\;", ";")
        .replace(r"\\", "\\")
    )


def _parse_prop(line: str) -> tuple[str, dict[str, str], str] | None:
    if ":" not in line:
        return None
    left, value = line.split(":", 1)
    parts = left.split(";")
    name = parts[0].upper()
    params: dict[str, str] = {}
    for part in parts[1:]:
        if "=" in part:
            key, param_value = part.split("=", 1)
            params[key.upper()] = param_value.strip('"')
    return name, params, _unescape(value.strip())


def _parse_datetime(value: str, params: dict[str, str], default_tz: ZoneInfo) -> tuple[datetime, bool]:
    if params.get("VALUE", "").upper() == "DATE" or (len(value) == 8 and value.isdigit()):
        parsed_date = datetime.strptime(value[:8], "%Y%m%d").date()
        return datetime.combine(parsed_date, time.min, tzinfo=default_tz), True

    tz = default_tz
    raw = value
    if raw.endswith("Z"):
        tz = timezone.utc
        raw = raw[:-1]
    elif params.get("TZID"):
        try:
            tz = ZoneInfo(params["TZID"])
        except Exception:
            tz = default_tz

    fmt = "%Y%m%dT%H%M%S" if len(raw) >= 15 else "%Y%m%dT%H%M"
    parsed = datetime.strptime(raw[:15] if fmt.endswith("%S") else raw[:13], fmt)
    return parsed.replace(tzinfo=tz).astimezone(default_tz), False


def _parse_rrule(value: str) -> dict[str, str]:
    rule: dict[str, str] = {}
    for part in value.split(";"):
        if "=" in part:
            key, rule_value = part.split("=", 1)
            rule[key.upper()] = rule_value
    return rule


def _weekday_token(day: date) -> str:
    return ("MO", "TU", "WE", "TH", "FR", "SA", "SU")[day.weekday()]


def _recurs_on_day(start: datetime, rule: dict[str, str], target_day: date, default_tz: ZoneInfo) -> bool:
    if start.date() > target_day:
        return False
    until = rule.get("UNTIL")
    if until:
        try:
            until_dt, _ = _parse_datetime(until, {}, default_tz)
            if until_dt.date() < target_day:
                return False
        except ValueError:
            pass

    interval = max(1, int(rule.get("INTERVAL", "1") or "1"))
    freq = rule.get("FREQ", "").upper()
    delta_days = (target_day - start.date()).days
    if freq == "DAILY":
        return delta_days % interval == 0
    if freq == "WEEKLY":
        byday = {part[-2:] for part in rule.get("BYDAY", _weekday_token(start.date())).split(",")}
        return delta_days // 7 % interval == 0 and _weekday_token(target_day) in byday
    if freq == "MONTHLY":
        return start.day == target_day.day and (
            (target_day.year - start.year) * 12 + target_day.month - start.month
        ) % interval == 0
    if freq == "YEARLY":
        return start.month == target_day.month and start.day == target_day.day and (target_day.year - start.year) % interval == 0
    return False


def _event_occurrence_for_day(event: dict, target_day: date, default_tz: ZoneInfo) -> CalendarEvent | None:
    if "DTSTART" not in event:
        return None
    starts_at, all_day = _parse_datetime(event["DTSTART"][0], event["DTSTART"][1], default_tz)
    ends_at = None
    if "DTEND" in event:
        ends_at, _ = _parse_datetime(event["DTEND"][0], event["DTEND"][1], default_tz)

    rule = _parse_rrule(event["RRULE"][0]) if "RRULE" in event else None
    if starts_at.date() != target_day:
        if not rule or not _recurs_on_day(starts_at, rule, target_day, default_tz):
            return None
        duration = (ends_at - starts_at) if ends_at else None
        starts_at = datetime.combine(target_day, starts_at.timetz()).replace(tzinfo=starts_at.tzinfo)
        ends_at = starts_at + duration if duration else None

    summary = event.get("SUMMARY", ("Untitled event", {}))[0] or "Untitled event"
    return CalendarEvent(summary=summary, starts_at=starts_at, ends_at=ends_at, all_day=all_day)


def _parse_events(body: str, target_day: date, default_tz: ZoneInfo) -> list[CalendarEvent]:
    events: list[CalendarEvent] = []
    current: dict[str, tuple[str, dict[str, str]]] | None = None
    for line in _unfold_lines(body):
        parsed = _parse_prop(line)
        if parsed is None:
            continue
        name, params, value = parsed
        if name == "BEGIN" and value.upper() == "VEVENT":
            current = {}
            continue
        if name == "END" and value.upper() == "VEVENT":
            if current is not None:
                try:
                    event = _event_occurrence_for_day(current, target_day, default_tz)
                except ValueError:
                    event = None
                if event is not None:
                    events.append(event)
            current = None
            continue
        if current is not None and name in {"SUMMARY", "DTSTART", "DTEND", "RRULE"}:
            current[name] = (value, params)

    return sorted(events, key=lambda event: (not event.all_day, event.starts_at.time(), event.summary.lower()))


async def fetch_today_events(calendar_url: str, timezone_name: str | None) -> list[CalendarEvent]:
    url = calendar_url.strip()
    if not url:
        raise ValueError("Calendar URL is required.")
    try:
        default_tz = ZoneInfo(timezone_name or "UTC")
    except Exception:
        default_tz = ZoneInfo("UTC")

    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        resp = await client.get(url, headers={"User-Agent": "InkyEasel/1.0"})
        resp.raise_for_status()

    today = datetime.now(default_tz).date()
    return _parse_events(resp.text, today, default_tz)
