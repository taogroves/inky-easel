"""Frame management (portal-side)."""

from __future__ import annotations

import secrets
from datetime import datetime
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import require_service_user
from ..db import get_session
from ..models import Frame, FrameState, User
from ..schemas import (
    FrameConfigurationSave,
    FrameConfigurationSessionOut,
    FrameCreate,
    FrameOut,
    FramePublicOut,
    FrameSecretOut,
    FrameUpdate,
)
from ..services import frame_configuration
from ..services.firmware import get_release, list_releases
from ..services.timezones import infer_timezone

router = APIRouter(prefix="/api/frames", tags=["frames"])


async def _owned_frame(frame_id: str, user: User, session: AsyncSession) -> Frame:
    frame = (
        await session.execute(select(Frame).where(Frame.id == frame_id, Frame.user_id == user.id))
    ).scalar_one_or_none()
    if frame is None:
        raise HTTPException(404, "Frame not found")
    return frame


async def _configuration_out(frame_id: str) -> FrameConfigurationSessionOut:
    session_state = frame_configuration.get_session(frame_id)
    try:
        releases = await list_releases()
    except HTTPException:
        releases = []
    if session_state is None:
        return FrameConfigurationSessionOut(
            state="idle",
            observed=None,
            message=None,
            updated_at=datetime.utcnow(),
            releases=releases,
        )
    return FrameConfigurationSessionOut(
        state=session_state.state,
        observed=session_state.observed,
        message=session_state.message,
        updated_at=session_state.updated_at,
        releases=releases,
    )


def _validate_configuration_save(payload: FrameConfigurationSave) -> None:
    if payload.config.active_wifi_index >= len(payload.config.wifi_credentials):
        raise HTTPException(400, "Active Wi-Fi index must reference one of the configured networks.")
    parsed = urlparse(payload.config.server_url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(400, "Server URL must be an http(s) URL.")
    if parsed.query or parsed.fragment:
        raise HTTPException(400, "Server URL must not include a query string or fragment.")


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


@router.get("/{frame_id}/configuration", response_model=FrameConfigurationSessionOut)
async def configuration_status(
    frame_id: str,
    reset_terminal: bool = False,
    user: User = Depends(require_service_user),
    session: AsyncSession = Depends(get_session),
):
    await _owned_frame(frame_id, user, session)
    if reset_terminal:
        frame_configuration.clear_inactive_session(frame_id)
    return await _configuration_out(frame_id)


@router.post("/{frame_id}/configuration/start", response_model=FrameConfigurationSessionOut)
async def start_configuration(
    frame_id: str,
    user: User = Depends(require_service_user),
    session: AsyncSession = Depends(get_session),
):
    await _owned_frame(frame_id, user, session)
    frame_configuration.start_session(frame_id)
    return await _configuration_out(frame_id)


@router.post("/{frame_id}/configuration/save", response_model=FrameConfigurationSessionOut)
async def save_configuration(
    frame_id: str,
    payload: FrameConfigurationSave,
    user: User = Depends(require_service_user),
    session: AsyncSession = Depends(get_session),
):
    await _owned_frame(frame_id, user, session)
    _validate_configuration_save(payload)
    if payload.firmware_release_id and await get_release(payload.firmware_release_id) is None:
        raise HTTPException(404, "Firmware release not found")
    frame_configuration.save_session(
        frame_id,
        payload.config,
        payload.firmware_release_id,
    )
    return await _configuration_out(frame_id)


@router.post("/{frame_id}/configuration/cancel", response_model=FrameConfigurationSessionOut)
async def cancel_configuration(
    frame_id: str,
    user: User = Depends(require_service_user),
    session: AsyncSession = Depends(get_session),
):
    await _owned_frame(frame_id, user, session)
    frame_configuration.cancel_session(frame_id)
    return await _configuration_out(frame_id)


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
