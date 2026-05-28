"""Pydantic request/response schemas."""

from __future__ import annotations

import base64
from datetime import datetime, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, computed_field, field_serializer

from .services.image_delivery import ImageDeliveryOut, image_delivery_for_frame

MAX_WIFI_CREDENTIALS = 3
MAX_WIFI_INDEX = MAX_WIFI_CREDENTIALS - 1


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


class WifiCredential(ApiModel):
    ssid: str = Field(..., min_length=1, max_length=64)
    password: str = Field(default="", max_length=128)


class FrameConfigurationReport(ApiModel):
    status: Literal["available", "applied", "error"] = "available"
    message: Optional[str] = None
    wifi_credentials: list[WifiCredential] = Field(default_factory=list, max_length=MAX_WIFI_CREDENTIALS)
    active_wifi_index: int = Field(0, ge=0, le=MAX_WIFI_INDEX)
    server_url: str = Field("", max_length=256)
    firmware_version: Optional[str] = None


class FrameConfigurationDesired(ApiModel):
    wifi_credentials: list[WifiCredential] = Field(default_factory=list, min_length=1, max_length=MAX_WIFI_CREDENTIALS)
    active_wifi_index: int = Field(0, ge=0, le=MAX_WIFI_INDEX)
    server_url: str = Field(..., min_length=1, max_length=256)


class FirmwareUpdateFile(ApiModel):
    path: str
    url: str
    sha256: str
    size_bytes: int


class FirmwareUpdatePayload(ApiModel):
    version: str
    release_id: str
    files: list[FirmwareUpdateFile]


class FrameConfigurationCommand(ApiModel):
    mode: Literal["enter", "apply", "cancel"]
    poll_seconds: int = 5
    config: Optional[FrameConfigurationDesired] = None
    firmware_update: Optional[FirmwareUpdatePayload] = None


class FramePollRequest(ApiModel):
    frame_id: str
    secret: str
    server_url: Optional[str] = None
    battery_voltage: float = 0.0
    battery_percent: int = 0
    wakeup: Literal["rtc", "button", "power"] = "rtc"
    has_sd_card: Optional[bool] = None
    firmware_version: Optional[str] = None
    configuration_status: Optional[FrameConfigurationReport] = None


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
    image_mime: Optional[str] = None
    text: Optional[TextPayload] = None
    plugin: Optional[PluginPayload] = None
    firmware_update: Optional[FirmwareUpdatePayload] = None
    configuration: Optional[FrameConfigurationCommand] = None
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
    me_and_you_enabled: Optional[bool] = None


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
    me_and_you_enabled: bool
    last_seen_at: Optional[datetime]
    next_expected_poll_at: Optional[datetime]
    disconnected_after: Optional[datetime]
    connection_status: Literal["connected", "disconnected", "awaiting_first_check_in"]
    last_battery_percent: Optional[int]
    last_battery_voltage: Optional[float]
    last_has_sd_card: Optional[bool] = None
    firmware_version: Optional[str] = None
    target_firmware_version: Optional[str] = None
    last_firmware_status: Optional[str] = None
    last_firmware_update_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True

    @computed_field
    @property
    def image_delivery(self) -> ImageDeliveryOut:
        return image_delivery_for_frame(self.last_has_sd_card)


class FrameAdminOut(FrameOut):
    owner_email: str


class FrameSecretOut(FrameOut):
    secret: str


class ScheduleItemIn(ApiModel):
    item_type: Literal["inbox", "weather", "xkcd", "rss", "reddit", "bbc", "calendar", "art", "plugin", "static", "me_and_you"]
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
    kind: Literal["text", "image", "link", "drawing"]
    text_body: Optional[str] = None
    image_base64: Optional[str] = None
    image_mime: Optional[str] = None
    sender_label: Optional[str] = None
    inbox_password: Optional[str] = None


class InboxPreviewRequest(ApiModel):
    recipient_frame_name: str
    kind: Literal["text", "image", "link", "drawing"]
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
    thumbnail_mime: Optional[str] = None
    thumbnail_bytes: Optional[bytes] = Field(default=None, exclude=True)
    sender_label: Optional[str]
    created_at: datetime
    displayed_at: Optional[datetime]
    display_count: int
    archived: bool

    @computed_field
    @property
    def thumbnail_data_url(self) -> Optional[str]:
        if not self.thumbnail_mime or not self.thumbnail_bytes:
            return None
        encoded = base64.b64encode(self.thumbnail_bytes).decode("ascii")
        return f"data:{self.thumbnail_mime};base64,{encoded}"

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
    binary_files: list[str] = Field(default_factory=list)
    server_url: str


class FirmwareReleaseCreate(ApiModel):
    version: str = Field(..., min_length=1, max_length=64, pattern=r"^[A-Za-z0-9._+-]+$")
    notes: Optional[str] = None
    activate: bool = True


class FirmwareFileOut(ApiModel):
    path: str
    sha256: str
    size_bytes: int

    class Config:
        from_attributes = True


class FirmwareReleaseOut(ApiModel):
    id: str
    version: str
    notes: Optional[str]
    active: bool
    manifest_hash: str
    created_at: datetime
    files: list[FirmwareFileOut] = Field(default_factory=list)

    class Config:
        from_attributes = True


class FirmwareLocalChangeOut(ApiModel):
    path: str
    status: Literal["added", "modified", "removed"]
    local_sha256: Optional[str] = None
    active_sha256: Optional[str] = None
    local_size_bytes: Optional[int] = None
    active_size_bytes: Optional[int] = None

    class Config:
        from_attributes = True


class FirmwareAdminOut(ApiModel):
    frames: list[FrameAdminOut]
    releases: list[FirmwareReleaseOut]
    local_changes: list[FirmwareLocalChangeOut] = Field(default_factory=list)


class FrameConfigurationSave(ApiModel):
    config: FrameConfigurationDesired
    firmware_release_id: Optional[str] = None


class FrameConfigurationSessionOut(ApiModel):
    state: Literal["idle", "pending", "entering", "connected", "applying", "applied", "error", "cancelled"]
    observed: Optional[FrameConfigurationReport] = None
    message: Optional[str] = None
    updated_at: datetime
    releases: list[FirmwareReleaseOut] = Field(default_factory=list)
