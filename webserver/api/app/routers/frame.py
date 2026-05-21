"""Frame protocol routes (the Pico talks here)."""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import authenticate_frame
from ..db import get_session
from ..models import ContentCache, Frame
from ..schemas import FramePollRequest, FramePollResponse
from ..services.schedule import resolve_next_for_frame

router = APIRouter(prefix="/api/frame", tags=["frame"])


def _poll_grace_minutes(sleep_minutes: int) -> int:
    return max(5, min(30, int(sleep_minutes * 0.25)))


@router.post("/poll", response_model=FramePollResponse)
async def poll(
    payload: FramePollRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> FramePollResponse:
    frame = await authenticate_frame(payload.frame_id, payload.secret, session)

    now = datetime.utcnow()
    frame.last_seen_at = now
    frame.last_battery_percent = payload.battery_percent
    frame.last_battery_voltage = payload.battery_voltage
    if payload.has_sd_card is not None:
        frame.last_has_sd_card = payload.has_sd_card

    response = await resolve_next_for_frame(
        session,
        frame,
        asset_base_url=(payload.server_url or str(request.base_url)).rstrip("/"),
        has_sd_card=payload.has_sd_card,
    )
    response.low_battery_warning = payload.battery_percent < 20
    sleep_minutes = max(1, int(response.sleep_minutes or 1))
    frame.next_expected_poll_at = now + timedelta(minutes=sleep_minutes)
    frame.disconnected_after = frame.next_expected_poll_at + timedelta(
        minutes=_poll_grace_minutes(sleep_minutes)
    )
    await session.commit()
    return response


@router.get("/asset/{token}")
async def asset(token: str, session: AsyncSession = Depends(get_session)) -> Response:
    entry = (
        await session.execute(select(ContentCache).where(ContentCache.token == token))
    ).scalar_one_or_none()
    if entry is None:
        raise HTTPException(404, "expired or unknown asset")
    if entry.expires_at < datetime.utcnow():
        await session.execute(delete(ContentCache).where(ContentCache.token == token))
        await session.commit()
        raise HTTPException(404, "expired asset")
    return Response(content=entry.payload, media_type=entry.mime)
