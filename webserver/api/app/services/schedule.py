"""Schedule resolution.

On every poll we:
  1. Read the current schedule position (0 if first poll).
  2. Resolve the schedule item to a renderable payload.
  3. Advance the pointer so the *next* poll gets the *next* item.
  4. Persist the new position and an audit timestamp.

The schedule loops indefinitely; if the list is empty we return a friendly
"no schedule" text card.
"""

from __future__ import annotations

import asyncio
import secrets as _secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..content import calendar, me_and_you, reddit, rss, weather, xkcd
from ..content.renderer import (
    RenderTarget,
    render_me_and_you,
    render_calendar_day,
    render_reddit_magazine,
    render_rss_magazine,
    render_title_body,
    render_weather,
    render_xkcd,
    target_for,
)
from ..models import (
    ContentCache,
    Frame,
    FrameState,
    InboxItem,
    Plugin,
    ScheduleItem,
    User,
)
from ..schemas import FramePollResponse, PluginPayload, TextPayload
from .timezones import localize_datetime
from .inbox_render import render_stored_inbox_item


@dataclass
class ResolvedItem:
    response: FramePollResponse


async def _cache_image(session: AsyncSession, payload: bytes, mime: str) -> str:
    settings = get_settings()
    token = _secrets.token_urlsafe(24)
    expires = datetime.utcnow() + timedelta(minutes=settings.content_cache_minutes)
    entry = ContentCache(token=token, mime=mime, payload=payload, expires_at=expires)
    session.add(entry)
    await session.flush()
    return token


async def _prune_cache(session: AsyncSession) -> None:
    await session.execute(
        delete(ContentCache).where(ContentCache.expires_at < datetime.utcnow())
    )


def _image_url(token: str, base_url: str | None = None) -> str:
    settings = get_settings()
    public_base_url = (base_url or settings.public_base_url).rstrip("/")
    return public_base_url + f"/api/frame/asset/{token}"


async def _attach_image(
    session: AsyncSession,
    response: FramePollResponse,
    target: RenderTarget,
    payload: bytes,
    asset_base_url: str | None,
) -> None:
    mime = "image/png"
    token = await _cache_image(session, payload, mime)
    response.type = "image"
    response.image_url = _image_url(token, asset_base_url)
    response.image_mime = mime
    response.text = None


async def _resolve_inbox(
    session: AsyncSession,
    frame: Frame,
    target: RenderTarget,
) -> tuple[bytes, Optional[dict]]:
    item = (
        await session.execute(
            select(InboxItem)
            .where(
                InboxItem.recipient_frame_id == frame.id,
                InboxItem.archived.is_(False),
                InboxItem.displayed_at.is_(None),
            )
            .order_by(InboxItem.created_at.asc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if item is None and frame.inbox_repeat_enabled:
        filters = [
            InboxItem.recipient_frame_id == frame.id,
            InboxItem.archived.is_(False),
            InboxItem.displayed_at.is_not(None),
        ]
        if frame.inbox_delete_after_displays:
            filters.append(InboxItem.display_count < frame.inbox_delete_after_displays)
        item = (
            await session.execute(
                select(InboxItem)
                .where(*filters)
                .order_by(InboxItem.displayed_at.asc(), InboxItem.created_at.asc())
                .limit(1)
            )
        ).scalar_one_or_none()

    if item is None:
        png = await asyncio.to_thread(
            render_title_body,
            target,
            "Inbox empty",
            "No new messages waiting.\nAsk a friend to send something!",
            "GREEN",
        )
        return png, {"kind": "empty"}

    png = await asyncio.to_thread(render_stored_inbox_item, target, frame, item)

    item.display_count = (item.display_count or 0) + 1
    item.displayed_at = datetime.utcnow()
    delete_after = frame.inbox_delete_after_displays
    if delete_after and item.display_count >= delete_after:
        await session.delete(item)
    return png, {"kind": item.kind, "inbox_id": item.id}


async def _resolve_weather(frame: Frame, target: RenderTarget, config: Optional[dict] = None) -> bytes:
    if frame.latitude is None or frame.longitude is None:
        return await asyncio.to_thread(
            render_title_body,
            target,
            "Local Weather",
            "No location configured.\nUpdate it in the portal.",
            "BLUE",
        )
    units = (config or {}).get("units", "celsius")
    try:
        data = await weather.fetch_weather(
            frame.latitude,
            frame.longitude,
            frame.timezone,
            units=units,
        )
        return await asyncio.to_thread(render_weather, target, data)
    except Exception as e:
        return await asyncio.to_thread(render_title_body, target, "Local Weather", f"Could not fetch weather:\n{e}", "RED")


async def _resolve_xkcd(target: RenderTarget) -> bytes:
    try:
        comic = await xkcd.fetch_xkcd()
        return await asyncio.to_thread(render_xkcd, target, comic["img_bytes"], comic["title"], comic.get("alt"))
    except Exception as e:
        return await asyncio.to_thread(render_title_body, target, "XKCD", f"Could not fetch comic:\n{e}", "RED")


async def _resolve_rss(target: RenderTarget, config: Optional[dict]) -> bytes:
    cfg = config or {}
    feed_url = cfg.get("feed_url")
    feed_title = cfg.get("feed_title")
    try:
        payload = await rss.fetch_rss(feed_url)
        title = feed_title or payload.get("title") or rss.DEFAULT_TITLE
        return await asyncio.to_thread(render_rss_magazine, target, title, payload.get("items", []))
    except Exception as e:
        return await asyncio.to_thread(render_title_body, target, "RSS", f"Could not fetch feed:\n{e}", "RED")


async def _resolve_reddit(target: RenderTarget, config: Optional[dict]) -> bytes:
    cfg = config or {}
    subreddit = cfg.get("subreddit") if "subreddit" in cfg else None
    try:
        payload = await reddit.fetch_reddit(subreddit)
        label = payload.get("label") or reddit.display_label(subreddit)
        return await asyncio.to_thread(render_reddit_magazine, target, label, payload.get("items", []))
    except Exception as e:
        return await asyncio.to_thread(render_title_body, target, "Reddit", f"Could not fetch subreddit:\n{e}", "RED")


async def _resolve_calendar(frame: Frame, target: RenderTarget, config: Optional[dict]) -> bytes:
    cfg = config or {}
    calendar_url = str(cfg.get("calendar_url") or cfg.get("ical_url") or "").strip()
    accent = str(cfg.get("accent") or "BLUE")
    try:
        events = await calendar.fetch_today_events(calendar_url, frame.timezone)
        now_local = localize_datetime(datetime.now(timezone.utc), frame.timezone)
        return await asyncio.to_thread(render_calendar_day, target, events, accent, now_local.strftime("%A, %b %-d"))
    except Exception as e:
        return await asyncio.to_thread(render_title_body, target, "Calendar", f"Could not fetch calendar:\n{e}", "RED")


def _has_me_you_location(frame: Frame) -> bool:
    return (
        frame.latitude is not None
        and frame.longitude is not None
        and bool(frame.timezone)
    )


async def _resolve_me_and_you(
    session: AsyncSession,
    frame: Frame,
    target: RenderTarget,
    config: Optional[dict],
) -> bytes:
    cfg = config or {}
    handle = me_and_you.normalize_frame_handle(cfg.get("other_frame_handle"))
    if not handle:
        return await asyncio.to_thread(
            render_title_body,
            target,
            "Me and You",
            "Add a friend's frame handle in the schedule item.",
            "BLUE",
        )
    if handle == frame.name:
        return await asyncio.to_thread(
            render_title_body,
            target,
            "Me and You",
            "Choose a different frame handle to compare with.",
            "BLUE",
        )
    if not _has_me_you_location(frame):
        return await asyncio.to_thread(
            render_title_body,
            target,
            "Me and You",
            "Add this frame's location and timezone before comparing with a friend.",
            "BLUE",
        )

    other = (
        await session.execute(select(Frame).where(Frame.name == handle))
    ).scalar_one_or_none()
    if other is None or not other.me_and_you_enabled:
        return await asyncio.to_thread(
            render_title_body,
            target,
            "Me and You",
            "That handle is not available for Me and You.\nAsk them to enable sharing on their frame.",
            "RED",
        )
    if not _has_me_you_location(other):
        return await asyncio.to_thread(
            render_title_body,
            target,
            "Me and You",
            "The other frame needs a location and timezone before it can be compared.",
            "BLUE",
        )

    try:
        payload = await me_and_you.build_me_and_you_payload(frame, other, cfg)
        return await asyncio.to_thread(render_me_and_you, target, payload)
    except Exception as e:
        return await asyncio.to_thread(render_title_body, target, "Me and You", f"Could not build comparison:\n{e}", "RED")


async def _resolve_plugin(
    session: AsyncSession, frame: Frame, item: ScheduleItem
) -> Optional[PluginPayload]:
    if not item.item_ref:
        return None
    plugin = (
        await session.execute(
            select(Plugin).where(Plugin.id == item.item_ref, Plugin.user_id == frame.user_id)
        )
    ).scalar_one_or_none()
    if plugin is None:
        return None

    now_utc = datetime.now(timezone.utc)
    now_local = localize_datetime(now_utc, frame.timezone)
    context = dict(item.config or {})
    context.update({
        "frame_name": frame.name,
        "display_name": frame.display_name,
        "latitude": frame.latitude,
        "longitude": frame.longitude,
        "timezone": frame.timezone,
        "now_iso": now_utc.isoformat().replace("+00:00", "Z"),
        "now_local_iso": now_local.isoformat(),
    })
    return PluginPayload(code=plugin.code, context=context)


def _item_start_minute(item: ScheduleItem) -> int:
    return max(0, min(1439, item.start_minute if item.start_minute is not None else 0))


def _minutes_until(next_start: int, current_minute: int) -> int:
    diff = next_start - current_minute
    if diff <= 0:
        diff += 1440
    return max(1, diff)


def _calendar_item_for_now(frame: Frame, schedule: list[ScheduleItem]) -> tuple[ScheduleItem, int, int]:
    now_local = localize_datetime(datetime.utcnow(), frame.timezone)
    current_minute = now_local.hour * 60 + now_local.minute
    ordered = sorted(schedule, key=lambda item: (_item_start_minute(item), item.position))

    current_idx = len(ordered) - 1
    for idx, item in enumerate(ordered):
        if _item_start_minute(item) <= current_minute:
            current_idx = idx
        else:
            break

    item = ordered[current_idx]
    next_item = ordered[(current_idx + 1) % len(ordered)]
    return item, _minutes_until(_item_start_minute(next_item), current_minute), current_idx


async def resolve_next_for_frame(
    session: AsyncSession,
    frame: Frame,
    asset_base_url: str | None = None,
    *,
    has_sd_card: bool | None = None,
) -> FramePollResponse:
    state = (
        await session.execute(select(FrameState).where(FrameState.frame_id == frame.id))
    ).scalar_one_or_none()
    if state is None:
        state = FrameState(frame_id=frame.id, current_index=0)
        session.add(state)

    schedule = (
        await session.execute(
            select(ScheduleItem)
            .where(ScheduleItem.frame_id == frame.id)
            .order_by(ScheduleItem.position)
        )
    ).scalars().all()

    if not schedule:
        return FramePollResponse(
            type="text",
            text=TextPayload(
                title="No schedule",
                body="Set up your schedule in the portal to get started.",
                accent="BLUE",
            ),
            sleep_minutes=60,
        )

    if frame.schedule_mode == "calendar":
        item, sleep_minutes, idx = _calendar_item_for_now(frame, schedule)
    else:
        idx = state.current_index % len(schedule)
        item = schedule[idx]
        sleep_minutes = max(1, item.sleep_minutes)
    target = target_for(frame.display_type, has_sd_card=bool(has_sd_card))

    response = FramePollResponse(
        type="text",
        text=TextPayload(title="...", body="..."),
        sleep_minutes=sleep_minutes,
    )

    if item.item_type == "inbox":
        png, meta = await _resolve_inbox(session, frame, target)
        await _attach_image(
            session,
            response,
            target,
            png,
            asset_base_url,
        )
    elif item.item_type == "weather":
        png = await _resolve_weather(frame, target, item.config)
        await _attach_image(session, response, target, png, asset_base_url)
    elif item.item_type == "me_and_you":
        png = await _resolve_me_and_you(session, frame, target, item.config)
        await _attach_image(session, response, target, png, asset_base_url)
    elif item.item_type == "xkcd":
        png = await _resolve_xkcd(target)
        await _attach_image(session, response, target, png, asset_base_url)
    elif item.item_type in ("rss", "bbc"):
        png = await _resolve_rss(target, item.config)
        await _attach_image(session, response, target, png, asset_base_url)
    elif item.item_type == "reddit":
        png = await _resolve_reddit(target, item.config)
        await _attach_image(session, response, target, png, asset_base_url)
    elif item.item_type == "calendar":
        png = await _resolve_calendar(frame, target, item.config)
        await _attach_image(session, response, target, png, asset_base_url)
    elif item.item_type == "static":
        text = (item.config or {}) if item.config else {}
        response.type = "text"
        response.text = TextPayload(
            title=text.get("title", "Hello"),
            body=text.get("body", ""),
            accent=text.get("accent", "BLUE"),
        )
    elif item.item_type == "plugin":
        plugin_payload = await _resolve_plugin(session, frame, item)
        if plugin_payload is None:
            response.type = "text"
            response.text = TextPayload(title="Plugin missing", body="Plugin was deleted.", accent="RED")
        else:
            response.type = "plugin"
            response.plugin = plugin_payload
            response.text = None

    if frame.schedule_mode == "calendar":
        state.current_index = schedule.index(item)
    else:
        state.current_index = (idx + 1) % len(schedule)
    state.last_advance_at = datetime.utcnow()

    await _prune_cache(session)
    return response
