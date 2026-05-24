"""Frame protocol routes (the Pico talks here)."""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import authenticate_frame
from ..db import get_session
from ..models import ContentCache, Frame
from ..schemas import (
    FirmwareUpdateFile,
    FirmwareUpdatePayload,
    FrameConfigurationCommand,
    FramePollRequest,
    FramePollResponse,
)
from ..services import frame_configuration
from ..services.firmware import get_release, latest_active_release
from ..services.schedule import resolve_next_for_frame

router = APIRouter(prefix="/api/frame", tags=["frame"])


def _poll_grace_minutes(sleep_minutes: int) -> int:
    return max(5, min(30, int(sleep_minutes * 0.25)))


def _firmware_payload(release, base_url: str) -> FirmwareUpdatePayload:
    return FirmwareUpdatePayload(
        version=release.version,
        release_id=release.id,
        files=[
            FirmwareUpdateFile(
                path=file.path,
                url=f"{base_url}/api/frame/firmware/{release.id}/{file.path}",
                sha256=file.sha256,
                size_bytes=file.size_bytes,
            )
            for file in release.files
        ],
    )


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
    if payload.firmware_version:
        frame.firmware_version = payload.firmware_version

    release = await latest_active_release()
    if release and payload.firmware_version == release.version:
        frame.target_firmware_version = release.version
        frame.last_firmware_status = "installed"
        frame.last_firmware_update_at = now
    elif payload.firmware_version and frame.target_firmware_version == payload.firmware_version:
        frame.last_firmware_status = "installed"
        frame.last_firmware_update_at = now

    base_url = (payload.server_url or str(request.base_url)).rstrip("/")
    if payload.configuration_status is not None:
        frame_configuration.record_frame_report(frame.id, payload.configuration_status)

    config_session = frame_configuration.get_session(frame.id)
    if config_session and config_session.state in {"pending", "connected", "applying", "cancelled", "error"}:
        command: FrameConfigurationCommand | None = None
        if config_session.state == "cancelled":
            command = FrameConfigurationCommand(mode="cancel")
            config_session.state = "idle"
            config_session.desired = None
            config_session.observed = None
            config_session.firmware_release_id = None
        elif config_session.state == "applying" and config_session.desired and config_session.observed:
            firmware_update = None
            can_apply = True
            if config_session.firmware_release_id:
                manual_release = await get_release(config_session.firmware_release_id)
                if manual_release is None:
                    config_session.state = "error"
                    config_session.message = "Selected firmware release is no longer available."
                    can_apply = False
                else:
                    firmware_update = _firmware_payload(manual_release, base_url)
                    frame.target_firmware_version = manual_release.version
                    frame.last_firmware_status = "manual-offered"
            if can_apply:
                command = FrameConfigurationCommand(
                    mode="apply",
                    config=config_session.desired,
                    firmware_update=firmware_update,
                )
            else:
                command = FrameConfigurationCommand(mode="enter")
        else:
            command = FrameConfigurationCommand(mode="enter")

        sleep_minutes = 1
        frame.next_expected_poll_at = now + timedelta(seconds=5)
        frame.disconnected_after = now + timedelta(minutes=2)
        await session.commit()
        return FramePollResponse(
            type="sleep",
            sleep_minutes=sleep_minutes,
            configuration=command,
            low_battery_warning=payload.battery_percent < 20,
        )

    response = await resolve_next_for_frame(
        session,
        frame,
        asset_base_url=base_url,
        has_sd_card=payload.has_sd_card,
    )
    response.low_battery_warning = payload.battery_percent < 20
    if (
        release
        and payload.has_sd_card is not False
        and payload.firmware_version != release.version
    ):
        response.firmware_update = _firmware_payload(release, base_url)
        frame.target_firmware_version = release.version
        frame.last_firmware_status = "offered"
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
