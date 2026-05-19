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

import secrets as _secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..content import bbc, weather, xkcd
from ..content.renderer import (
    RenderTarget,
    render_bbc,
    render_inbox_image,
    render_inbox_text,
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


@dataclass
class ResolvedItem:
    response: FramePollResponse


async def _cache_jpeg(session: AsyncSession, payload: bytes) -> str:
    settings = get_settings()
    token = _secrets.token_urlsafe(24)
    expires = datetime.utcnow() + timedelta(minutes=settings.content_cache_minutes)
    entry = ContentCache(token=token, mime="image/jpeg", payload=payload, expires_at=expires)
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


async def _resolve_inbox(
    session: AsyncSession, frame: Frame, target: RenderTarget
) -> tuple[str, Optional[dict]]:
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

    if item is None:
        jpeg = render_title_body(
            target,
            title="Inbox empty",
            body="No new messages waiting.\nAsk a friend to send something!",
            accent="GREEN",
        )
        return jpeg, {"kind": "empty"}

    if item.kind == "image" and item.image_bytes:
        jpeg = render_inbox_image(target, item.image_bytes, item.sender_label)
    else:
        jpeg = render_inbox_text(
            target,
            sender=item.sender_label or "Friend",
            text=item.text_body or "",
            when=item.created_at,
        )

    item.displayed_at = datetime.utcnow()
    return jpeg, {"kind": item.kind, "inbox_id": item.id}


async def _resolve_weather(frame: Frame, target: RenderTarget) -> bytes:
    if frame.latitude is None or frame.longitude is None:
        return render_title_body(
            target,
            title="Weather",
            body="No location configured.\nUpdate it in the portal.",
            accent="BLUE",
        )
    try:
        data = await weather.fetch_weather(frame.latitude, frame.longitude)
        location = data.get("timezone") or f"{frame.latitude:.1f},{frame.longitude:.1f}"
        return render_weather(target, location, data["current"], data["forecast"])
    except Exception as e:
        return render_title_body(target, "Weather", f"Could not fetch weather:\n{e}", accent="RED")


async def _resolve_xkcd(target: RenderTarget) -> bytes:
    try:
        comic = await xkcd.fetch_xkcd()
        return render_xkcd(target, comic["img_bytes"], comic["title"], comic.get("alt"))
    except Exception as e:
        return render_title_body(target, "XKCD", f"Could not fetch comic:\n{e}", accent="RED")


async def _resolve_bbc(target: RenderTarget, feed: Optional[str]) -> bytes:
    try:
        items = await bbc.fetch_bbc(feed)
        return render_bbc(target, items)
    except Exception as e:
        return render_title_body(target, "BBC", f"Could not fetch headlines:\n{e}", accent="RED")


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

    context = dict(item.config or {})
    context.update({
        "frame_name": frame.name,
        "display_name": frame.display_name,
        "latitude": frame.latitude,
        "longitude": frame.longitude,
        "timezone": frame.timezone,
        "now_iso": datetime.utcnow().isoformat() + "Z",
    })
    return PluginPayload(code=plugin.code, context=context)


async def resolve_next_for_frame(
    session: AsyncSession, frame: Frame, asset_base_url: str | None = None
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

    idx = state.current_index % len(schedule)
    item = schedule[idx]
    target = target_for(frame.display_type)

    response = FramePollResponse(
        type="text",
        text=TextPayload(title="...", body="..."),
        sleep_minutes=max(1, item.sleep_minutes),
    )

    if item.item_type == "inbox":
        jpeg, _meta = await _resolve_inbox(session, frame, target)
        token = await _cache_jpeg(session, jpeg)
        response.type = "image"
        response.image_url = _image_url(token, asset_base_url)
        response.text = None
    elif item.item_type == "weather":
        jpeg = await _resolve_weather(frame, target)
        token = await _cache_jpeg(session, jpeg)
        response.type = "image"
        response.image_url = _image_url(token, asset_base_url)
        response.text = None
    elif item.item_type == "xkcd":
        jpeg = await _resolve_xkcd(target)
        token = await _cache_jpeg(session, jpeg)
        response.type = "image"
        response.image_url = _image_url(token, asset_base_url)
        response.text = None
    elif item.item_type == "bbc":
        feed = (item.config or {}).get("feed_url") if item.config else None
        jpeg = await _resolve_bbc(target, feed)
        token = await _cache_jpeg(session, jpeg)
        response.type = "image"
        response.image_url = _image_url(token, asset_base_url)
        response.text = None
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

    state.current_index = (idx + 1) % len(schedule)
    state.last_advance_at = datetime.utcnow()

    await _prune_cache(session)
    return response
