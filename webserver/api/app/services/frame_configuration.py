"""Volatile frame configuration sessions.

Wi-Fi passwords intentionally live only in memory during a dashboard-driven
configuration handshake. They are never written to SQL or firmware release
storage.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ..schemas import FrameConfigurationDesired, FrameConfigurationReport


@dataclass
class ConfigurationSession:
    frame_id: str
    state: str
    updated_at: datetime
    observed: FrameConfigurationReport | None = None
    desired: FrameConfigurationDesired | None = None
    firmware_release_id: str | None = None
    message: str | None = None


_sessions: dict[str, ConfigurationSession] = {}


def _now() -> datetime:
    return datetime.utcnow()


def get_session(frame_id: str) -> ConfigurationSession | None:
    return _sessions.get(frame_id)


def start_session(frame_id: str) -> ConfigurationSession:
    session = ConfigurationSession(frame_id=frame_id, state="pending", updated_at=_now())
    _sessions[frame_id] = session
    return session


def cancel_session(frame_id: str) -> ConfigurationSession:
    session = _sessions.get(frame_id)
    if session is None:
        session = ConfigurationSession(frame_id=frame_id, state="cancelled", updated_at=_now())
        _sessions[frame_id] = session
    session.state = "cancelled"
    session.desired = None
    session.message = "Configuration cancelled."
    session.updated_at = _now()
    return session


def save_session(
    frame_id: str,
    desired: FrameConfigurationDesired,
    firmware_release_id: str | None,
) -> ConfigurationSession:
    session = _sessions.get(frame_id)
    if session is None or session.state in {"idle", "applied", "cancelled"}:
        session = start_session(frame_id)
    session.desired = desired
    session.firmware_release_id = firmware_release_id
    session.state = "applying"
    session.message = "Waiting for the frame to apply changes."
    session.updated_at = _now()
    return session


def record_frame_report(frame_id: str, report: FrameConfigurationReport) -> ConfigurationSession | None:
    session = _sessions.get(frame_id)
    if session is None:
        return None
    session.observed = report
    session.updated_at = _now()
    if report.status == "applied":
        session.state = "applied"
        session.message = report.message or "Configuration saved on the frame."
        session.desired = None
        session.observed = None
        session.firmware_release_id = None
    elif report.status == "error":
        session.state = "error"
        session.message = report.message or "The frame reported an error."
    elif session.state == "pending":
        session.state = "connected"
        session.message = "Frame is in configuration mode."
    return session
