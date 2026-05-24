"""Shared inbox rendering for schedule delivery and portal previews."""

from __future__ import annotations

import base64
from datetime import datetime
from urllib.parse import urlparse

from PIL import UnidentifiedImageError
from sqlalchemy.ext.asyncio import AsyncSession

from ..content.link_preview import LinkPreview, resolve_link_preview
from ..content.renderer import (
    RenderTarget,
    prepare_inbox_image,
    render_inbox_image,
    render_inbox_text,
    render_link_preview,
    target_for,
)
from ..content.url_clean import clean_url_for_qr
from ..models import Frame, InboxItem
from .timezones import localize_datetime

MAX_IMAGE_BYTES = 5 * 1024 * 1024


def render_stored_inbox_item(target: RenderTarget, frame: Frame, item: InboxItem) -> bytes:
    if item.kind == "link" and item.image_bytes:
        return render_inbox_image(target, item.image_bytes, None)
    if item.kind in {"image", "drawing"} and item.image_bytes:
        return render_inbox_image(target, item.image_bytes, item.sender_label)
    return render_inbox_text(
        target,
        sender=item.sender_label or "Friend",
        text=item.text_body or "",
        when=localize_datetime(item.created_at, frame.timezone),
    )


def _preview_target(frame: Frame) -> RenderTarget:
    return target_for(frame.display_type)


async def render_inbox_preview(
    session: AsyncSession,
    frame: Frame,
    *,
    kind: str,
    text_body: str | None = None,
    image_bytes: bytes | None = None,
    sender_label: str | None = None,
    created_at: datetime | None = None,
) -> tuple[bytes, str]:
    target = _preview_target(frame)

    if kind == "text":
        payload = render_inbox_text(
            target,
            sender=sender_label or "Friend",
            text=text_body or "",
            when=localize_datetime(created_at or datetime.utcnow(), frame.timezone),
        )
    elif kind in {"image", "drawing"}:
        if not image_bytes:
            raise ValueError("image is required")
        stored = prepare_inbox_image(image_bytes, target)
        payload = render_inbox_image(target, stored, sender_label)
    elif kind == "link":
        if not text_body or not text_body.strip():
            raise ValueError("link URL is required")
        try:
            preview = await resolve_link_preview(text_body.strip())
        except Exception:
            cleaned = clean_url_for_qr(text_body.strip())
            parsed = urlparse(cleaned)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError("Link must be an http(s) URL")
            preview = LinkPreview(
                url=cleaned,
                final_url=cleaned,
                domain=parsed.netloc[4:] if parsed.netloc.startswith("www.") else parsed.netloc,
            )
        card = render_link_preview(target, preview)
        payload = render_inbox_image(target, card, None)
    else:
        raise ValueError("Unknown kind")

    return payload, "image/png"


async def render_stored_item_preview(
    session: AsyncSession,
    frame: Frame,
    item: InboxItem,
) -> tuple[bytes, str]:
    target = _preview_target(frame)
    payload = render_stored_inbox_item(target, frame, item)
    return payload, "image/png"


class ImageTooLargeError(ValueError):
    pass


def decode_image_base64(image_base64: str) -> bytes:
    try:
        data = base64.b64decode(image_base64, validate=True)
    except Exception as exc:
        raise ValueError("image_base64 is not valid base64") from exc
    if len(data) > MAX_IMAGE_BYTES:
        raise ImageTooLargeError(f"Image too large (>{MAX_IMAGE_BYTES // 1024} KB)")
    return data


def validate_image_bytes(data: bytes) -> None:
    try:
        prepare_inbox_image(data, target_for("inky_frame_7_spectra"))
    except UnidentifiedImageError as exc:
        raise ValueError("image is not a supported image") from exc
    except Exception as exc:
        raise ValueError(f"Could not process image: {exc}") from exc
