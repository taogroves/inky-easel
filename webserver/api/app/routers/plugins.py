"""Custom user plugins (MicroPython snippets stored per user)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import require_service_user
from ..db import get_session
from ..models import Plugin, User
from ..schemas import PluginIn, PluginOut

router = APIRouter(prefix="/api/plugins", tags=["plugins"])

MAX_CODE_BYTES = 64 * 1024


def _validate_code(code: str) -> None:
    if not code.strip():
        raise HTTPException(422, "Plugin code is empty")
    if len(code.encode("utf-8")) > MAX_CODE_BYTES:
        raise HTTPException(413, "Plugin code too large (>64 KB)")
    if "def draw" not in code:
        raise HTTPException(422, "Plugin must define `def draw(graphics, width, height, context)`")


@router.get("", response_model=list[PluginOut])
async def list_plugins(
    user: User = Depends(require_service_user),
    session: AsyncSession = Depends(get_session),
):
    rows = (
        await session.execute(
            select(Plugin).where(Plugin.user_id == user.id).order_by(Plugin.created_at)
        )
    ).scalars().all()
    return rows


@router.post("", response_model=PluginOut, status_code=status.HTTP_201_CREATED)
async def create_plugin(
    payload: PluginIn,
    user: User = Depends(require_service_user),
    session: AsyncSession = Depends(get_session),
):
    _validate_code(payload.code)
    plugin = Plugin(
        user_id=user.id,
        name=payload.name,
        description=payload.description,
        code=payload.code,
    )
    session.add(plugin)
    await session.commit()
    await session.refresh(plugin)
    return plugin


@router.put("/{plugin_id}", response_model=PluginOut)
async def update_plugin(
    plugin_id: str,
    payload: PluginIn,
    user: User = Depends(require_service_user),
    session: AsyncSession = Depends(get_session),
):
    plugin = (
        await session.execute(
            select(Plugin).where(Plugin.id == plugin_id, Plugin.user_id == user.id)
        )
    ).scalar_one_or_none()
    if plugin is None:
        raise HTTPException(404, "Plugin not found")
    _validate_code(payload.code)
    plugin.name = payload.name
    plugin.description = payload.description
    plugin.code = payload.code
    await session.commit()
    await session.refresh(plugin)
    return plugin


@router.delete("/{plugin_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_plugin(
    plugin_id: str,
    user: User = Depends(require_service_user),
    session: AsyncSession = Depends(get_session),
):
    plugin = (
        await session.execute(
            select(Plugin).where(Plugin.id == plugin_id, Plugin.user_id == user.id)
        )
    ).scalar_one_or_none()
    if plugin is None:
        raise HTTPException(404, "Plugin not found")
    await session.delete(plugin)
    await session.commit()
