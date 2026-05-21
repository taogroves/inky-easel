"""Inbox: list, archive, and send messages/images between frames."""

from __future__ import annotations

import base64
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, status
from PIL import UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import require_service_user
from ..content.link_preview import LinkPreview, resolve_link_preview
from ..content.renderer import prepare_inbox_image, render_link_preview, target_for
from ..content.url_clean import clean_url_for_qr
from ..db import get_session
from ..models import Frame, InboxItem, User
from ..schemas import InboxItemOut, InboxSend

router = APIRouter(prefix="/api/inbox", tags=["inbox"])

MAX_IMAGE_BYTES = 5 * 1024 * 1024


@router.get("/frames/{frame_id}", response_model=list[InboxItemOut])
async def list_inbox(
    frame_id: str,
    include_archived: bool = False,
    user: User = Depends(require_service_user),
    session: AsyncSession = Depends(get_session),
):
    frame = (
        await session.execute(select(Frame).where(Frame.id == frame_id, Frame.user_id == user.id))
    ).scalar_one_or_none()
    if frame is None:
        raise HTTPException(404, "Frame not found")

    stmt = select(InboxItem).where(InboxItem.recipient_frame_id == frame_id)
    if not include_archived:
        stmt = stmt.where(InboxItem.archived.is_(False))
    stmt = stmt.order_by(InboxItem.created_at.desc())
    items = (await session.execute(stmt)).scalars().all()
    return items


@router.post("", response_model=InboxItemOut, status_code=status.HTTP_201_CREATED)
async def send_inbox(
    payload: InboxSend,
    user: User = Depends(require_service_user),
    session: AsyncSession = Depends(get_session),
):
    recipient = (
        await session.execute(select(Frame).where(Frame.name == payload.recipient_frame_name))
    ).scalar_one_or_none()
    if recipient is None:
        raise HTTPException(404, "Recipient frame not found")
    if recipient.inbox_mode == "closed":
        raise HTTPException(403, "This frame's inbox is closed")
    if recipient.inbox_mode == "private":
        expected = (recipient.inbox_password or "").strip()
        provided = (payload.inbox_password or "").strip()
        if not expected or provided != expected:
            raise HTTPException(403, "Inbox password required")

    sender_label = payload.sender_label or user.name or user.email.split("@")[0]

    item = InboxItem(
        recipient_frame_id=recipient.id,
        sender_user_id=user.id,
        sender_label=sender_label[:120],
        kind=payload.kind,
    )

    target = target_for(recipient.display_type)

    if payload.kind == "text":
        if not payload.text_body or not payload.text_body.strip():
            raise HTTPException(422, "text_body is required for text messages")
        item.text_body = payload.text_body
    elif payload.kind in {"image", "drawing"}:
        if not payload.image_base64:
            raise HTTPException(422, "image_base64 is required for image/drawing messages")
        try:
            data = base64.b64decode(payload.image_base64, validate=True)
        except Exception:
            raise HTTPException(422, "image_base64 is not valid base64")
        if len(data) > MAX_IMAGE_BYTES:
            raise HTTPException(413, f"Image too large (>{MAX_IMAGE_BYTES // 1024} KB)")
        try:
            item.image_bytes = prepare_inbox_image(data, target)
        except UnidentifiedImageError:
            raise HTTPException(422, "image_base64 is not a supported image")
        except Exception as e:
            raise HTTPException(422, f"Could not process image: {e}")
        item.image_mime = "image/jpeg"
    elif payload.kind == "link":
        if not payload.text_body or not payload.text_body.strip():
            raise HTTPException(422, "text_body is required for link messages")
        try:
            preview = await resolve_link_preview(payload.text_body.strip())
        except ValueError as e:
            raise HTTPException(422, str(e))
        except Exception:
            cleaned = clean_url_for_qr(payload.text_body.strip())
            parsed = urlparse(cleaned)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise HTTPException(422, "Link must be an http(s) URL")
            preview = LinkPreview(
                url=cleaned,
                final_url=cleaned,
                domain=parsed.netloc[4:] if parsed.netloc.startswith("www.") else parsed.netloc,
            )
        item.text_body = preview.final_url
        item.image_bytes = render_link_preview(target, preview)
        item.image_mime = "image/jpeg"
    else:  # pragma: no cover - pydantic enforces this
        raise HTTPException(422, "Unknown kind")

    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item


@router.post("/{item_id}/archive", response_model=InboxItemOut)
async def archive_item(
    item_id: str,
    user: User = Depends(require_service_user),
    session: AsyncSession = Depends(get_session),
):
    item = (
        await session.execute(
            select(InboxItem)
            .join(Frame, Frame.id == InboxItem.recipient_frame_id)
            .where(InboxItem.id == item_id, Frame.user_id == user.id)
        )
    ).scalar_one_or_none()
    if item is None:
        raise HTTPException(404, "Item not found")
    item.archived = True
    await session.commit()
    await session.refresh(item)
    return item


@router.post("/{item_id}/unarchive", response_model=InboxItemOut)
async def unarchive_item(
    item_id: str,
    user: User = Depends(require_service_user),
    session: AsyncSession = Depends(get_session),
):
    item = (
        await session.execute(
            select(InboxItem)
            .join(Frame, Frame.id == InboxItem.recipient_frame_id)
            .where(InboxItem.id == item_id, Frame.user_id == user.id)
        )
    ).scalar_one_or_none()
    if item is None:
        raise HTTPException(404, "Item not found")
    item.archived = False
    await session.commit()
    await session.refresh(item)
    return item


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(
    item_id: str,
    user: User = Depends(require_service_user),
    session: AsyncSession = Depends(get_session),
):
    item = (
        await session.execute(
            select(InboxItem)
            .join(Frame, Frame.id == InboxItem.recipient_frame_id)
            .where(InboxItem.id == item_id, Frame.user_id == user.id)
        )
    ).scalar_one_or_none()
    if item is None:
        raise HTTPException(404, "Item not found")
    await session.delete(item)
    await session.commit()
