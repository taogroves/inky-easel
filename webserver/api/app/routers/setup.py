"""Setup-bundle endpoint.

Returns the contents of every firmware file plus a configured `secrets.py`
and `frame_config.py` for the requested frame. The portal writes these to
the user's SD card via the File System Access API (or downloads a ZIP).
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import require_service_user
from ..config import get_settings
from ..db import get_session
from ..models import Frame, User
from ..schemas import FrameSecretOut, SetupBundleOut

router = APIRouter(prefix="/api/setup", tags=["setup"])


def _firmware_dir() -> Path:
    configured = Path(get_settings().frame_firmware_dir)
    if configured.exists():
        return configured
    # Fallback for local `uvicorn app.main:app` runs from repo root.
    return Path(__file__).resolve().parents[4] / "frame-firmware"


FIRMWARE_FILES = [
    "main.py",
    "frame_client.py",
    "battery.py",
    "display.py",
    "inky_helper.py",
]


class WifiBody(BaseModel):
    wifi_ssid: str
    wifi_password: str


def _render_secrets(body: WifiBody) -> str:
    ssid = body.wifi_ssid.replace('"', '\\"')
    pw = body.wifi_password.replace('"', '\\"')
    return (
        f'WIFI_SSID = "{ssid}"\n'
        f'WIFI_PASSWORD = "{pw}"\n'
    )


def _render_config(frame: Frame, server_url: str) -> str:
    return (
        f'FRAME_ID = "{frame.id}"\n'
        f'FRAME_SECRET = "{frame.secret}"\n'
        f'SERVER_URL = "{server_url}"\n'
        f'DISPLAY_TYPE = "{frame.display_type}"\n'
        f'TIMEZONE_OFFSET_HOURS = 0\n'
        f'DEFAULT_SLEEP_MINUTES = 30\n'
    )


@router.post("/{frame_id}/bundle", response_model=SetupBundleOut)
async def build_bundle(
    frame_id: str,
    body: WifiBody,
    user: User = Depends(require_service_user),
    session: AsyncSession = Depends(get_session),
):
    frame = (
        await session.execute(select(Frame).where(Frame.id == frame_id, Frame.user_id == user.id))
    ).scalar_one_or_none()
    if frame is None:
        raise HTTPException(404, "Frame not found")

    settings = get_settings()

    firmware_dir = _firmware_dir()
    files: dict[str, str] = {}
    for name in FIRMWARE_FILES:
        path = firmware_dir / name
        if not path.exists():
            raise HTTPException(500, f"Firmware source missing: {name}")
        files[name] = path.read_text(encoding="utf-8")

    files["secrets.py"] = _render_secrets(body)
    files["frame_config.py"] = _render_config(frame, settings.public_base_url)
    files["README.txt"] = (
        "Inky Easel SD bundle\n"
        "====================\n"
        "Copy every file in this folder to the root of a FAT32-formatted\n"
        "microSD card, then insert it into your Inky Frame.\n"
        f"\nFrame name: {frame.name}\nDisplay: {frame.display_type}\n"
        "If you change Wi-Fi or your server URL, re-run the setup wizard.\n"
    )

    return SetupBundleOut(
        frame=FrameSecretOut.model_validate(frame, from_attributes=True),
        files=files,
        server_url=settings.public_base_url,
    )
