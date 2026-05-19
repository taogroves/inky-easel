"""Pydantic request/response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


# ---------- Frame protocol ----------


class FramePollRequest(BaseModel):
    frame_id: str
    secret: str
    server_url: Optional[str] = None
    battery_voltage: float = 0.0
    battery_percent: int = 0
    wakeup: Literal["rtc", "button", "power"] = "rtc"


class TextPayload(BaseModel):
    title: str = ""
    body: str = ""
    accent: str = "BLUE"


class PluginPayload(BaseModel):
    code: str
    context: dict[str, Any] = Field(default_factory=dict)


class FramePollResponse(BaseModel):
    type: Literal["image", "text", "plugin", "sleep"] = "sleep"
    image_url: Optional[str] = None
    text: Optional[TextPayload] = None
    plugin: Optional[PluginPayload] = None
    sleep_minutes: int = 60
    low_battery_warning: bool = False


# ---------- Portal API ----------


class FrameCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=64, pattern=r"^[a-z0-9-]+$")
    display_name: str = Field(..., min_length=1, max_length=120)
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    timezone: Optional[str] = None
    display_type: str = "inky_frame_7_spectra"


class FrameUpdate(BaseModel):
    display_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    timezone: Optional[str] = None
    display_type: Optional[str] = None


class FrameOut(BaseModel):
    id: str
    name: str
    display_name: str
    latitude: Optional[float]
    longitude: Optional[float]
    timezone: Optional[str]
    display_type: str
    last_seen_at: Optional[datetime]
    last_battery_percent: Optional[int]
    last_battery_voltage: Optional[float]
    created_at: datetime

    class Config:
        from_attributes = True


class FrameSecretOut(FrameOut):
    secret: str


class ScheduleItemIn(BaseModel):
    item_type: Literal["inbox", "weather", "xkcd", "bbc", "plugin", "static"]
    item_ref: Optional[str] = None
    config: Optional[dict[str, Any]] = None
    sleep_minutes: int = Field(60, ge=1, le=1440)


class ScheduleItemOut(ScheduleItemIn):
    id: str
    position: int

    class Config:
        from_attributes = True


class ScheduleReplace(BaseModel):
    items: list[ScheduleItemIn]


class PluginIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: Optional[str] = None
    code: str


class PluginOut(PluginIn):
    id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class InboxSend(BaseModel):
    recipient_frame_name: str
    kind: Literal["text", "image"]
    text_body: Optional[str] = None
    image_base64: Optional[str] = None
    image_mime: Optional[str] = None
    sender_label: Optional[str] = None


class InboxItemOut(BaseModel):
    id: str
    kind: str
    text_body: Optional[str]
    image_mime: Optional[str]
    sender_label: Optional[str]
    created_at: datetime
    displayed_at: Optional[datetime]
    archived: bool

    class Config:
        from_attributes = True


class FramePublicOut(BaseModel):
    name: str
    display_name: str

    class Config:
        from_attributes = True


class SetupBundleOut(BaseModel):
    frame: FrameSecretOut
    files: dict[str, str]
    server_url: str
