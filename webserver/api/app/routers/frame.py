"""Frame protocol routes (the Pico talks here)."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import authenticate_frame
from ..db import get_session
from ..models import ContentCache, Frame
from ..schemas import FramePollRequest, FramePollResponse
from ..services.schedule import resolve_next_for_frame

router = APIRouter(prefix="/api/frame", tags=["frame"])


@router.post("/poll", response_model=FramePollResponse)
async def poll(
    payload: FramePollRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> FramePollResponse:
    frame = await authenticate_frame(payload.frame_id, payload.secret, session)

    frame.last_seen_at = datetime.utcnow()
    frame.last_battery_percent = payload.battery_percent
    frame.last_battery_voltage = payload.battery_voltage

    response = await resolve_next_for_frame(
        session,
        frame,
        asset_base_url=(payload.server_url or str(request.base_url)).rstrip("/"),
    )
    response.low_battery_warning = payload.battery_percent < 20
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
