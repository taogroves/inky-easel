"""Auth dependencies.

Two distinct authentication paths:

* `require_service_user` — used by the portal (Next.js) when calling FastAPI.
  Next.js validates the better-auth session, then proxies with
  `X-Service-Auth: <shared secret>` and `X-User-Id: <user id>`. We trust those
  headers iff the shared secret matches.
* `require_frame` — used by the Pico. The Frame sends its own `frame_id` /
  `secret` in the request body; we validate against `ie_frame.secret`.
"""

from __future__ import annotations

import hmac
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_settings
from .db import get_session
from .models import Frame, User


async def require_service_user(
    x_service_auth: Annotated[str | None, Header()] = None,
    x_user_id: Annotated[str | None, Header()] = None,
    session: AsyncSession = Depends(get_session),
) -> User:
    settings = get_settings()
    if not x_service_auth or not x_user_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing service auth")
    if not hmac.compare_digest(x_service_auth, settings.service_secret):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "bad service auth")

    user = (await session.execute(select(User).where(User.id == x_user_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "unknown user")
    return user


async def authenticate_frame(
    frame_id: str, secret: str, session: AsyncSession
) -> Frame:
    frame = (
        await session.execute(select(Frame).where(Frame.id == frame_id))
    ).scalar_one_or_none()
    if frame is None or not hmac.compare_digest(frame.secret, secret):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "frame auth failed")
    return frame
