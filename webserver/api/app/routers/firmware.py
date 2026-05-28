"""Firmware release management and frame download endpoints."""

from __future__ import annotations

import base64
import mimetypes

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import require_service_user
from ..db import get_session
from ..models import Frame, User
from ..schemas import FrameAdminOut, FrameOut, FirmwareAdminOut, FirmwareReleaseCreate, FirmwareReleaseOut
from ..services.firmware import (
    activate_release as activate_firmware_release,
    compare_local_to_active_release,
    create_release_from_source,
    get_firmware_file,
    list_releases,
)

router = APIRouter(tags=["firmware"])


@router.get("/api/firmware/admin", response_model=FirmwareAdminOut)
async def admin_status(
    user: User = Depends(require_service_user),
    session: AsyncSession = Depends(get_session),
):
    _ = user
    rows = (
        await session.execute(
            select(Frame, User.email)
            .outerjoin(User, Frame.user_id == User.id)
            .order_by(Frame.created_at)
        )
    ).all()
    frames = [
        FrameAdminOut(
            **FrameOut.model_validate(frame, from_attributes=True).model_dump(),
            owner_email=email or "unknown",
        )
        for frame, email in rows
    ]
    releases = await list_releases()
    local_changes = await compare_local_to_active_release()
    return FirmwareAdminOut(frames=frames, releases=releases, local_changes=local_changes)


@router.post("/api/firmware/releases", response_model=FirmwareReleaseOut, status_code=status.HTTP_201_CREATED)
async def create_release(
    payload: FirmwareReleaseCreate,
    user: User = Depends(require_service_user),
):
    try:
        release = await create_release_from_source(
            version=payload.version,
            notes=payload.notes,
            user=user,
            activate=payload.activate,
        )
    except FileNotFoundError as e:
        raise HTTPException(500, f"Firmware source missing: {e.args[0]}")
    return release


@router.post("/api/firmware/releases/{release_id}/activate", response_model=FirmwareReleaseOut)
async def activate_release(
    release_id: str,
    user: User = Depends(require_service_user),
):
    _ = user
    release = await activate_firmware_release(release_id)
    if release is None:
        raise HTTPException(404, "Firmware release not found")
    return release


@router.get("/api/frame/firmware/{release_id}/{path:path}")
async def firmware_file(
    release_id: str,
    path: str,
) -> Response:
    entry = await get_firmware_file(release_id, path)
    if entry is None:
        raise HTTPException(404, "Firmware file not found")
    if entry.binary:
        content = base64.b64decode(entry.content)
        media_type = mimetypes.guess_type(path)[0] or "application/octet-stream"
        return Response(content=content, media_type=media_type)
    return Response(content=entry.content, media_type="text/x-python; charset=utf-8")
