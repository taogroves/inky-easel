"""Setup-bundle endpoint.

Returns the contents of every firmware file plus a configured `secrets.py`
and `frame_config.py` for the requested frame. The portal writes these to
the user's SD card via the File System Access API (or downloads a ZIP).
"""

from __future__ import annotations

import json
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import require_service_user
from ..config import get_settings
from ..db import get_session
from ..models import Frame, User
from ..schemas import FrameSecretOut, SetupBundleOut
from ..services.firmware import FIRMWARE_FILES, firmware_dir, latest_active_release

router = APIRouter(prefix="/api/setup", tags=["setup"])


class WifiBody(BaseModel):
    wifi_ssid: str
    wifi_password: str
    server_url: str | None = Field(default=None, max_length=256)

    @field_validator("server_url")
    @classmethod
    def validate_server_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip().rstrip("/")
        if not cleaned:
            return None
        parsed = urlparse(cleaned)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Server URL must be an http(s) URL such as http://192.168.1.42:8000")
        if parsed.query or parsed.fragment:
            raise ValueError("Server URL must not include a query string or fragment")
        return cleaned


def _py_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _render_secrets(body: WifiBody) -> str:
    ssid = _py_string(body.wifi_ssid)
    pw = _py_string(body.wifi_password)
    return (
        f'WIFI_SSID = "{ssid}"\n'
        f'WIFI_PASSWORD = "{pw}"\n'
    )


def _render_wifi_config(body: WifiBody, server_url: str) -> str:
    return json.dumps(
        {
            "wifi_credentials": [
                {"ssid": body.wifi_ssid, "password": body.wifi_password}
            ],
            "active_wifi_index": 0,
            "server_url": server_url,
        },
        indent=2,
    ) + "\n"


def _render_config(frame: Frame, server_url: str) -> str:
    return (
        f'FRAME_ID = "{frame.id}"\n'
        f'FRAME_SECRET = "{frame.secret}"\n'
        f'SERVER_URL = "{_py_string(server_url)}"\n'
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
    server_url = body.server_url or settings.public_base_url.rstrip("/")

    files: dict[str, str] = {}
    release = await latest_active_release()
    if release:
        files.update({file.path: file.content for file in release.files})
        root = firmware_dir()
        for name in FIRMWARE_FILES:
            if name not in files and (root / name).exists():
                files[name] = (root / name).read_text(encoding="utf-8")
    else:
        root = firmware_dir()
        for name in FIRMWARE_FILES:
            path = root / name
            if not path.exists():
                raise HTTPException(500, f"Firmware source missing: {name}")
            files[name] = path.read_text(encoding="utf-8")

    files["secrets.py"] = _render_secrets(body)
    files["inky_easel_config.json"] = _render_wifi_config(body, server_url)
    files["frame_config.py"] = _render_config(frame, server_url)
    files["README.txt"] = (
        "Inky Easel SD bundle\n"
        "====================\n"
        "Copy every file in this folder to the root of a FAT32-formatted\n"
        "microSD card, then insert it into your Inky Frame.\n"
        "\nFor new frames, also copy flash_loader_main.py to the frame's internal\n"
        "flash as main.py. You only need to do that once.\n"
        f"\nFrame name: {frame.name}\nDisplay: {frame.display_type}\nServer URL: {server_url}\n"
        "Wi-Fi credentials live in inky_easel_config.json on the SD card.\n"
        "After first setup, you can change Wi-Fi or your server URL from the frame dashboard.\n"
        "After this first SD write, firmware updates are delivered automatically\n"
        "during frame check-ins and the previous SD files are backed up.\n"
    )

    return SetupBundleOut(
        frame=FrameSecretOut.model_validate(frame, from_attributes=True),
        files=files,
        server_url=server_url,
    )
