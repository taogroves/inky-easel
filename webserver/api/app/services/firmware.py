"""Firmware release helpers backed by Firestore's MongoDB-compatible API.

Releases are immutable snapshots of the SD-card application files. The mounted
firmware directory is only the source for creating a release; published release
metadata and file contents live in the configured MongoDB/SCRAM datastore.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from fastapi import HTTPException
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError, PyMongoError

from ..config import get_settings
from ..models import User

log = logging.getLogger("inky-easel.firmware")

FIRMWARE_FILES = [
    "main.py",
    "flash_loader_main.py",
    "inky_easel_app.py",
    "frame_client.py",
    "firmware_updater.py",
    "firmware_version.py",
    "battery.py",
    "display.py",
    "inky_helper.py",
]


@dataclass
class FirmwareFileDoc:
    path: str
    sha256: str
    size_bytes: int
    content: str = ""


@dataclass
class FirmwareReleaseDoc:
    id: str
    version: str
    notes: str | None
    active: bool
    manifest_hash: str
    created_at: datetime
    files: list[FirmwareFileDoc] = field(default_factory=list)
    created_by_user_id: str | None = None


def firmware_dir() -> Path:
    configured = Path(get_settings().frame_firmware_dir)
    if configured.exists():
        return configured
    return Path(__file__).resolve().parents[4] / "frame-firmware"


def source_files() -> dict[str, str]:
    root = firmware_dir()
    files: dict[str, str] = {}
    for name in FIRMWARE_FILES:
        path = root / name
        if not path.exists():
            raise FileNotFoundError(name)
        files[name] = path.read_text(encoding="utf-8")
    return files


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def manifest_hash(files: dict[str, str]) -> str:
    manifest = [
        {"path": path, "sha256": _sha256(content), "size_bytes": len(content.encode("utf-8"))}
        for path, content in sorted(files.items())
    ]
    return hashlib.sha256(json.dumps(manifest, sort_keys=True).encode("utf-8")).hexdigest()


@lru_cache
def _collection() -> Collection[dict[str, Any]]:
    settings = get_settings()
    if not settings.firestore_mongodb_uri:
        raise RuntimeError("FIRESTORE_MONGODB_URI is not configured")
    uri_db = urlparse(settings.firestore_mongodb_uri).path.lstrip("/")
    db_name = uri_db or settings.firestore_mongodb_database
    if uri_db and settings.firestore_mongodb_database and uri_db != settings.firestore_mongodb_database:
        log.info(
            "Using Firestore MongoDB database from URI path; FIRESTORE_MONGODB_DATABASE differs"
        )
    client: MongoClient[dict[str, Any]] = MongoClient(
        settings.firestore_mongodb_uri,
        serverSelectionTimeoutMS=5000,
    )
    return client[db_name][settings.firmware_releases_collection]


def _release_from_doc(doc: dict[str, Any] | None) -> FirmwareReleaseDoc | None:
    if not doc:
        return None
    return FirmwareReleaseDoc(
        id=str(doc["id"]),
        version=str(doc["version"]),
        notes=doc.get("notes"),
        active=bool(doc.get("active", False)),
        manifest_hash=str(doc["manifest_hash"]),
        created_at=doc.get("created_at") or datetime.utcnow(),
        created_by_user_id=doc.get("created_by_user_id"),
        files=[
            FirmwareFileDoc(
                path=str(item["path"]),
                sha256=str(item["sha256"]),
                size_bytes=int(item["size_bytes"]),
                content=str(item.get("content", "")),
            )
            for item in doc.get("files", [])
        ],
    )


def _version_file(version: str) -> str:
    escaped = version.replace("\\", "\\\\").replace('"', '\\"')
    return 'FIRMWARE_VERSION = "{}"\n'.format(escaped)


async def list_releases() -> list[FirmwareReleaseDoc]:
    def _list() -> list[FirmwareReleaseDoc]:
        docs = _collection().find({})
        releases = [release for doc in docs if (release := _release_from_doc(doc))]
        return sorted(releases, key=lambda release: release.created_at, reverse=True)

    try:
        return await asyncio.to_thread(_list)
    except RuntimeError:
        return []
    except PyMongoError as e:
        log.warning("Firmware database list failed: %s", e)
        raise HTTPException(503, f"Firmware database unavailable: {e}")


async def latest_active_release() -> FirmwareReleaseDoc | None:
    def _latest() -> FirmwareReleaseDoc | None:
        docs = _collection().find({"active": True})
        releases = [release for doc in docs if (release := _release_from_doc(doc))]
        if not releases:
            return None
        return sorted(releases, key=lambda release: release.created_at, reverse=True)[0]

    try:
        return await asyncio.to_thread(_latest)
    except RuntimeError:
        return None
    except PyMongoError as e:
        log.warning("Firmware database active-release lookup failed: %s", e)
        raise HTTPException(503, f"Firmware database unavailable: {e}")


async def create_release_from_source(
    *,
    version: str,
    notes: str | None,
    user: User,
    activate: bool = True,
) -> FirmwareReleaseDoc:
    files = source_files()
    files["firmware_version.py"] = _version_file(version)
    now = datetime.utcnow()
    doc = {
        "id": str(uuid.uuid4()),
        "version": version,
        "notes": notes,
        "active": False,
        "manifest_hash": manifest_hash(files),
        "created_by_user_id": user.id,
        "created_at": now,
        "files": [
            {
                "path": path,
                "content": content,
                "sha256": _sha256(content),
                "size_bytes": len(content.encode("utf-8")),
            }
            for path, content in sorted(files.items())
        ],
    }

    def _create() -> FirmwareReleaseDoc:
        collection = _collection()
        if collection.find_one({"version": version}) is not None:
            raise DuplicateKeyError("Firmware version already exists")
        collection.insert_one(doc)
        if activate:
            collection.update_many({"active": True}, {"$set": {"active": False}})
            collection.update_one({"id": doc["id"]}, {"$set": {"active": True}})
        release = _release_from_doc(collection.find_one({"id": doc["id"]}))
        if release is None:
            raise RuntimeError("Created firmware release could not be read")
        return release

    try:
        return await asyncio.to_thread(_create)
    except DuplicateKeyError:
        raise HTTPException(409, "Firmware version already exists")
    except RuntimeError as e:
        raise HTTPException(503, str(e))
    except PyMongoError as e:
        log.warning("Firmware database create failed: %s", e)
        raise HTTPException(503, f"Firmware database unavailable: {e}")


async def activate_release(release_id: str) -> FirmwareReleaseDoc | None:
    def _activate() -> FirmwareReleaseDoc | None:
        collection = _collection()
        existing = collection.find_one({"id": release_id})
        if existing is None:
            return None
        collection.update_many({"active": True}, {"$set": {"active": False}})
        collection.update_one({"id": release_id}, {"$set": {"active": True}})
        return _release_from_doc(collection.find_one({"id": release_id}))

    try:
        return await asyncio.to_thread(_activate)
    except RuntimeError as e:
        raise HTTPException(503, str(e))
    except PyMongoError as e:
        log.warning("Firmware database activate failed: %s", e)
        raise HTTPException(503, f"Firmware database unavailable: {e}")


async def get_firmware_file(release_id: str, path: str) -> FirmwareFileDoc | None:
    def _get() -> FirmwareFileDoc | None:
        doc = _collection().find_one({"id": release_id})
        if not doc:
            return None
        item = next(
            (file for file in doc.get("files", []) if str(file.get("path")) == path),
            None,
        )
        if not item:
            return None
        return FirmwareFileDoc(
            path=str(item["path"]),
            sha256=str(item["sha256"]),
            size_bytes=int(item["size_bytes"]),
            content=str(item.get("content", "")),
        )

    try:
        return await asyncio.to_thread(_get)
    except RuntimeError:
        return None
    except PyMongoError as e:
        log.warning("Firmware database file lookup failed: %s", e)
        raise HTTPException(503, f"Firmware database unavailable: {e}")
