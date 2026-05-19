"""Frame management (portal-side)."""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import require_service_user
from ..db import get_session
from ..models import Frame, FrameState, User
from ..schemas import FrameCreate, FrameOut, FramePublicOut, FrameSecretOut, FrameUpdate
from ..services.timezones import infer_timezone

router = APIRouter(prefix="/api/frames", tags=["frames"])


@router.get("", response_model=list[FrameOut])
async def list_frames(
    user: User = Depends(require_service_user),
    session: AsyncSession = Depends(get_session),
):
    rows = (
        await session.execute(select(Frame).where(Frame.user_id == user.id).order_by(Frame.created_at))
    ).scalars().all()
    return rows


@router.post("", response_model=FrameSecretOut, status_code=status.HTTP_201_CREATED)
async def create_frame(
    payload: FrameCreate,
    user: User = Depends(require_service_user),
    session: AsyncSession = Depends(get_session),
):
    frame = Frame(
        user_id=user.id,
        name=payload.name,
        display_name=payload.display_name,
        latitude=payload.latitude,
        longitude=payload.longitude,
        timezone=infer_timezone(payload.latitude, payload.longitude, payload.timezone),
        display_type=payload.display_type,
        secret=secrets.token_urlsafe(32),
    )
    session.add(frame)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(409, "Frame name is taken; pick another.")

    session.add(FrameState(frame_id=frame.id, current_index=0))
    await session.commit()
    await session.refresh(frame)
    return frame


@router.get("/timezone")
async def get_timezone_for_location(
    latitude: float,
    longitude: float,
    user: User = Depends(require_service_user),
):
    _ = user
    return {"timezone": infer_timezone(latitude, longitude)}


@router.get("/{frame_id}", response_model=FrameSecretOut)
async def get_frame(
    frame_id: str,
    user: User = Depends(require_service_user),
    session: AsyncSession = Depends(get_session),
):
    frame = (
        await session.execute(select(Frame).where(Frame.id == frame_id, Frame.user_id == user.id))
    ).scalar_one_or_none()
    if frame is None:
        raise HTTPException(404, "Frame not found")
    return frame


@router.patch("/{frame_id}", response_model=FrameSecretOut)
async def update_frame(
    frame_id: str,
    payload: FrameUpdate,
    user: User = Depends(require_service_user),
    session: AsyncSession = Depends(get_session),
):
    frame = (
        await session.execute(select(Frame).where(Frame.id == frame_id, Frame.user_id == user.id))
    ).scalar_one_or_none()
    if frame is None:
        raise HTTPException(404, "Frame not found")
    updates = payload.model_dump(exclude_unset=True)
    if {"latitude", "longitude", "timezone"} & updates.keys():
        latitude = updates.get("latitude", frame.latitude)
        longitude = updates.get("longitude", frame.longitude)
        updates["timezone"] = infer_timezone(latitude, longitude, updates.get("timezone", frame.timezone))
    if "inbox_mode" in updates and updates["inbox_mode"] != "private":
        updates["inbox_password"] = None
    for field, value in updates.items():
        setattr(frame, field, value)
    await session.commit()
    await session.refresh(frame)
    return frame


@router.delete("/{frame_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_frame(
    frame_id: str,
    user: User = Depends(require_service_user),
    session: AsyncSession = Depends(get_session),
):
    frame = (
        await session.execute(select(Frame).where(Frame.id == frame_id, Frame.user_id == user.id))
    ).scalar_one_or_none()
    if frame is None:
        raise HTTPException(404, "Frame not found")
    await session.delete(frame)
    await session.commit()


@router.post("/{frame_id}/rotate-secret", response_model=FrameSecretOut)
async def rotate_secret(
    frame_id: str,
    user: User = Depends(require_service_user),
    session: AsyncSession = Depends(get_session),
):
    frame = (
        await session.execute(select(Frame).where(Frame.id == frame_id, Frame.user_id == user.id))
    ).scalar_one_or_none()
    if frame is None:
        raise HTTPException(404, "Frame not found")
    frame.secret = secrets.token_urlsafe(32)
    await session.commit()
    await session.refresh(frame)
    return frame


@router.get("/lookup/{name}", response_model=FramePublicOut)
async def lookup(
    name: str,
    user: User = Depends(require_service_user),
    session: AsyncSession = Depends(get_session),
):
    frame = (
        await session.execute(select(Frame).where(Frame.name == name))
    ).scalar_one_or_none()
    if frame is None:
        raise HTTPException(404, "Frame not found")
    return frame
