"""SQLAlchemy ORM models.

The `user`, `session`, `account`, `verification` tables are owned and migrated
by better-auth in the Next.js portal. We declare lightweight read views of the
columns we actually need so FastAPI can join against them. Our own tables (the
`ie_*` prefix) are managed by Alembic-free `Base.metadata.create_all` during
container startup — they are simple enough that this is fine for now.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.mysql import LONGBLOB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    """The better-auth `user` table. Declared in full so FastAPI's startup
    `create_all` can bootstrap a fresh database without the portal needing to
    run a migration first.
    """

    __tablename__ = "user"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    emailVerified: Mapped[Optional[bool]] = mapped_column(Boolean, default=False)
    name: Mapped[Optional[str]] = mapped_column(String(255))
    image: Mapped[Optional[str]] = mapped_column(Text)
    createdAt: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updatedAt: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class AuthSession(Base):
    __tablename__ = "session"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    expiresAt: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    createdAt: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updatedAt: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
    ipAddress: Mapped[Optional[str]] = mapped_column(String(64))
    userAgent: Mapped[Optional[str]] = mapped_column(Text)
    userId: Mapped[str] = mapped_column(String(64), nullable=False)


class AuthAccount(Base):
    __tablename__ = "account"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    accountId: Mapped[str] = mapped_column(String(255), nullable=False)
    providerId: Mapped[str] = mapped_column(String(64), nullable=False)
    userId: Mapped[str] = mapped_column(String(64), nullable=False)
    accessToken: Mapped[Optional[str]] = mapped_column(Text)
    refreshToken: Mapped[Optional[str]] = mapped_column(Text)
    idToken: Mapped[Optional[str]] = mapped_column(Text)
    accessTokenExpiresAt: Mapped[Optional[datetime]] = mapped_column(DateTime)
    refreshTokenExpiresAt: Mapped[Optional[datetime]] = mapped_column(DateTime)
    scope: Mapped[Optional[str]] = mapped_column(Text)
    password: Mapped[Optional[str]] = mapped_column(Text)
    createdAt: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updatedAt: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class AuthVerification(Base):
    __tablename__ = "verification"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    identifier: Mapped[str] = mapped_column(String(255), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    expiresAt: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    createdAt: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())
    updatedAt: Mapped[Optional[datetime]] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class Frame(Base):
    __tablename__ = "ie_frame"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("user.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    display_name: Mapped[str] = mapped_column(String(120))
    secret: Mapped[str] = mapped_column(String(128))
    latitude: Mapped[Optional[float]] = mapped_column()
    longitude: Mapped[Optional[float]] = mapped_column()
    timezone: Mapped[Optional[str]] = mapped_column(String(64))
    display_type: Mapped[str] = mapped_column(String(40), default="inky_frame_7_spectra")
    inbox_mode: Mapped[str] = mapped_column(String(16), default="open")
    inbox_password: Mapped[Optional[str]] = mapped_column(String(120))
    inbox_repeat_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    inbox_delete_after_displays: Mapped[Optional[int]] = mapped_column(Integer)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_battery_percent: Mapped[Optional[int]] = mapped_column(Integer)
    last_battery_voltage: Mapped[Optional[float]] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    schedule_items: Mapped[list["ScheduleItem"]] = relationship(
        back_populates="frame", cascade="all, delete-orphan", order_by="ScheduleItem.position"
    )
    state: Mapped[Optional["FrameState"]] = relationship(
        back_populates="frame", uselist=False, cascade="all, delete-orphan"
    )
    inbox_items: Mapped[list["InboxItem"]] = relationship(
        back_populates="recipient_frame", cascade="all, delete-orphan",
        order_by="InboxItem.created_at",
        foreign_keys="InboxItem.recipient_frame_id",
    )


class FrameState(Base):
    __tablename__ = "ie_frame_state"

    frame_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("ie_frame.id", ondelete="CASCADE"), primary_key=True
    )
    current_index: Mapped[int] = mapped_column(Integer, default=0)
    last_advance_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    schedule_hash: Mapped[Optional[str]] = mapped_column(String(64))

    frame: Mapped[Frame] = relationship(back_populates="state")


class ScheduleItem(Base):
    __tablename__ = "ie_schedule_item"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    frame_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("ie_frame.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer)
    item_type: Mapped[str] = mapped_column(String(32))  # inbox|weather|xkcd|bbc|plugin|static
    item_ref: Mapped[Optional[str]] = mapped_column(String(255))
    config: Mapped[Optional[dict]] = mapped_column(JSON)
    sleep_minutes: Mapped[int] = mapped_column(Integer, default=60)

    frame: Mapped[Frame] = relationship(back_populates="schedule_items")

    __table_args__ = (UniqueConstraint("frame_id", "position", name="uq_schedule_position"),)


class Plugin(Base):
    __tablename__ = "ie_plugin"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("user.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[Optional[str]] = mapped_column(Text)
    code: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class InboxItem(Base):
    __tablename__ = "ie_inbox_item"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    recipient_frame_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("ie_frame.id", ondelete="CASCADE"), index=True
    )
    sender_user_id: Mapped[Optional[str]] = mapped_column(String(64), ForeignKey("user.id", ondelete="SET NULL"))
    sender_label: Mapped[Optional[str]] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(16))  # "text" | "image"
    text_body: Mapped[Optional[str]] = mapped_column(Text)
    image_mime: Mapped[Optional[str]] = mapped_column(String(64))
    image_bytes: Mapped[Optional[bytes]] = mapped_column(LONGBLOB)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    displayed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    display_count: Mapped[int] = mapped_column(Integer, default=0)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)

    recipient_frame: Mapped[Frame] = relationship(
        back_populates="inbox_items", foreign_keys=[recipient_frame_id]
    )


class ContentCache(Base):
    """Cache for server-rendered JPEGs so frames can re-download a stable URL."""

    __tablename__ = "ie_content_cache"

    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    mime: Mapped[str] = mapped_column(String(64), default="image/jpeg")
    payload: Mapped[bytes] = mapped_column(LONGBLOB)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
