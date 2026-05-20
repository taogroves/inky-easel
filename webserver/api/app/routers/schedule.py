"""Schedule endpoints. We replace the entire schedule on PUT for simplicity."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import require_service_user
from ..db import get_session
from ..models import Frame, FrameState, ScheduleItem, User
from ..schemas import ScheduleItemOut, ScheduleReplace

router = APIRouter(prefix="/api/frames/{frame_id}/schedule", tags=["schedule"])


async def _owned_frame(frame_id: str, user_id: str, session: AsyncSession) -> Frame:
    frame = (
        await session.execute(select(Frame).where(Frame.id == frame_id, Frame.user_id == user_id))
    ).scalar_one_or_none()
    if frame is None:
        raise HTTPException(404, "Frame not found")
    return frame


@router.get("", response_model=list[ScheduleItemOut])
async def get_schedule(
    frame_id: str,
    user: User = Depends(require_service_user),
    session: AsyncSession = Depends(get_session),
):
    await _owned_frame(frame_id, user.id, session)
    items = (
        await session.execute(
            select(ScheduleItem).where(ScheduleItem.frame_id == frame_id).order_by(ScheduleItem.position)
        )
    ).scalars().all()
    return items


@router.put("", response_model=list[ScheduleItemOut])
async def replace_schedule(
    frame_id: str,
    payload: ScheduleReplace,
    user: User = Depends(require_service_user),
    session: AsyncSession = Depends(get_session),
):
    frame = await _owned_frame(frame_id, user.id, session)
    frame.schedule_mode = payload.schedule_mode

    await session.execute(delete(ScheduleItem).where(ScheduleItem.frame_id == frame_id))
    await session.flush()

    new_items = [
        ScheduleItem(
            frame_id=frame.id,
            position=idx,
            item_type=item.item_type,
            item_ref=item.item_ref,
            config=item.config,
            sleep_minutes=item.sleep_minutes,
            start_minute=item.start_minute,
        )
        for idx, item in enumerate(payload.items)
    ]
    session.add_all(new_items)

    state = (
        await session.execute(select(FrameState).where(FrameState.frame_id == frame_id))
    ).scalar_one_or_none()
    if state is None:
        session.add(FrameState(frame_id=frame_id, current_index=0))
    else:
        state.current_index = 0
        state.last_advance_at = None

    await session.commit()
    items = (
        await session.execute(
            select(ScheduleItem).where(ScheduleItem.frame_id == frame_id).order_by(ScheduleItem.position)
        )
    ).scalars().all()
    return items
