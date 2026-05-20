"""Pydantic request/response schemas."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_serializer


def _utc_json(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.isoformat().replace("+00:00", "Z")


class ApiModel(BaseModel):
    @field_serializer("*", when_used="json")
    def serialize_datetimes(self, value: Any) -> Any:
        if isinstance(value, datetime):
            return _utc_json(value)
        return value


# ---------- Frame protocol ----------


class FramePollRequest(ApiModel):
    frame_id: str
    secret: str
    server_url: Optional[str] = None
    battery_voltage: float = 0.0
    battery_percent: int = 0
    wakeup: Literal["rtc", "button", "power"] = "rtc"


class TextPayload(ApiModel):
    title: str = ""
    body: str = ""
    accent: str = "BLUE"


class PluginPayload(ApiModel):
    code: str
    context: dict[str, Any] = Field(default_factory=dict)


class FramePollResponse(ApiModel):
    type: Literal["image", "text", "plugin", "sleep"] = "sleep"
    image_url: Optional[str] = None
    text: Optional[TextPayload] = None
    plugin: Optional[PluginPayload] = None
    sleep_minutes: int = 60
    low_battery_warning: bool = False


# ---------- Portal API ----------


class FrameCreate(ApiModel):
    name: str = Field(..., min_length=3, max_length=64, pattern=r"^[a-z0-9-]+$")
    display_name: str = Field(..., min_length=1, max_length=120)
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    timezone: Optional[str] = None
    display_type: str = "inky_frame_7_spectra"


class FrameUpdate(ApiModel):
    display_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    timezone: Optional[str] = None
    display_type: Optional[str] = None
    schedule_mode: Optional[Literal["relative", "calendar"]] = None
    inbox_mode: Optional[Literal["open", "private", "closed"]] = None
    inbox_password: Optional[str] = Field(default=None, max_length=120)
    inbox_repeat_enabled: Optional[bool] = None
    inbox_delete_after_displays: Optional[int] = Field(default=None, ge=1, le=100)


class FrameOut(ApiModel):
    id: str
    name: str
    display_name: str
    latitude: Optional[float]
    longitude: Optional[float]
    timezone: Optional[str]
    display_type: str
    schedule_mode: str
    inbox_mode: str
    inbox_password: Optional[str]
    inbox_repeat_enabled: bool
    inbox_delete_after_displays: Optional[int]
    last_seen_at: Optional[datetime]
    next_expected_poll_at: Optional[datetime]
    disconnected_after: Optional[datetime]
    connection_status: Literal["connected", "disconnected", "awaiting_first_check_in"]
    last_battery_percent: Optional[int]
    last_battery_voltage: Optional[float]
    created_at: datetime

    class Config:
        from_attributes = True


class FrameSecretOut(FrameOut):
    secret: str


class ScheduleItemIn(ApiModel):
    item_type: Literal["inbox", "weather", "xkcd", "rss", "reddit", "bbc", "plugin", "static"]
    item_ref: Optional[str] = None
    config: Optional[dict[str, Any]] = None
    sleep_minutes: int = Field(60, ge=1, le=1440)
    start_minute: Optional[int] = Field(default=None, ge=0, le=1439)


class ScheduleItemOut(ScheduleItemIn):
    id: str
    position: int

    class Config:
        from_attributes = True


class ScheduleReplace(ApiModel):
    schedule_mode: Literal["relative", "calendar"] = "relative"
    items: list[ScheduleItemIn]


class PluginIn(ApiModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: Optional[str] = None
    code: str


class PluginOut(PluginIn):
    id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class InboxSend(ApiModel):
    recipient_frame_name: str
    kind: Literal["text", "image"]
    text_body: Optional[str] = None
    image_base64: Optional[str] = None
    image_mime: Optional[str] = None
    sender_label: Optional[str] = None
    inbox_password: Optional[str] = None


class InboxItemOut(ApiModel):
    id: str
    kind: str
    text_body: Optional[str]
    image_mime: Optional[str]
    sender_label: Optional[str]
    created_at: datetime
    displayed_at: Optional[datetime]
    display_count: int
    archived: bool

    class Config:
        from_attributes = True


class FramePublicOut(ApiModel):
    name: str
    display_name: str

    class Config:
        from_attributes = True


class SetupBundleOut(ApiModel):
    frame: FrameSecretOut
    files: dict[str, str]
    server_url: str
