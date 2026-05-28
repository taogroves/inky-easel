"""Firmware release helpers backed by Firestore's MongoDB-compatible API.

Releases are immutable snapshots of the SD-card application files. The mounted
firmware directory is only the source for creating a release; published release
metadata and file contents live in the configured MongoDB/SCRAM datastore.
"""

from __future__ import annotations

import asyncio
import base64
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
    "wifi_config.py",
]

FIRMWARE_BINARY_FILES = [
    "wifi_unavailable.png",
]


@dataclass
class FirmwareFileDoc:
    path: str
    sha256: str
    size_bytes: int
    content: str = ""
    binary: bool = False


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


@dataclass
class FirmwareLocalChangeDoc:
    path: str
    status: str
    local_sha256: str | None = None
    active_sha256: str | None = None
    local_size_bytes: int | None = None
    active_size_bytes: int | None = None


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


def source_binary_files() -> dict[str, bytes]:
    root = firmware_dir()
    files: dict[str, bytes] = {}
    for name in FIRMWARE_BINARY_FILES:
        path = root / name
        if not path.exists():
            raise FileNotFoundError(name)
        files[name] = path.read_bytes()
    return files


def _source_files_best_effort() -> dict[str, str]:
    root = firmware_dir()
    files: dict[str, str] = {}
    for name in FIRMWARE_FILES:
        path = root / name
        if path.exists():
            files[name] = path.read_text(encoding="utf-8")
    return files


def _source_binary_files_best_effort() -> dict[str, bytes]:
    root = firmware_dir()
    files: dict[str, bytes] = {}
    for name in FIRMWARE_BINARY_FILES:
        path = root / name
        if path.exists():
            files[name] = path.read_bytes()
    return files


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _manifest_entries(
    files: dict[str, str],
    binary_files: dict[str, bytes] | None = None,
) -> list[dict[str, int | str]]:
    entries = [
        {"path": path, "sha256": _sha256(content), "size_bytes": len(content.encode("utf-8"))}
        for path, content in sorted(files.items())
    ]
    for path, data in sorted((binary_files or {}).items()):
        entries.append({"path": path, "sha256": _sha256_bytes(data), "size_bytes": len(data)})
    return entries


def manifest_hash(files: dict[str, str], binary_files: dict[str, bytes] | None = None) -> str:
    manifest = _manifest_entries(files, binary_files)
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
    version = str(doc["version"])
    files = [
        FirmwareFileDoc(
            path=str(item["path"]),
            sha256=str(item["sha256"]),
            size_bytes=int(item["size_bytes"]),
            content=str(item.get("content", "")),
            binary=bool(item.get("binary", False)),
        )
        for item in doc.get("files", [])
    ]
    if not any(file.path == "firmware_version.py" for file in files):
        content = _version_file(version)
        files.append(
            FirmwareFileDoc(
                path="firmware_version.py",
                sha256=_sha256(content),
                size_bytes=len(content.encode("utf-8")),
                content=content,
            )
        )
    return FirmwareReleaseDoc(
        id=str(doc["id"]),
        version=version,
        notes=doc.get("notes"),
        active=bool(doc.get("active", False)),
        manifest_hash=str(doc["manifest_hash"]),
        created_at=doc.get("created_at") or datetime.utcnow(),
        created_by_user_id=doc.get("created_by_user_id"),
        files=files,
    )


def _version_file(version: str) -> str:
    escaped = version.replace("\\", "\\\\").replace('"', '\\"')
    return 'FIRMWARE_VERSION = "{}"\n'.format(escaped)


def _file_doc(path: str, content: str) -> FirmwareFileDoc:
    return FirmwareFileDoc(
        path=path,
        sha256=_sha256(content),
        size_bytes=len(content.encode("utf-8")),
        content=content,
    )


def _binary_file_doc(path: str, data: bytes) -> FirmwareFileDoc:
    return FirmwareFileDoc(
        path=path,
        sha256=_sha256_bytes(data),
        size_bytes=len(data),
        content=base64.b64encode(data).decode("ascii"),
        binary=True,
    )


def _release_file_entries(files: dict[str, str], binary_files: dict[str, bytes]) -> list[dict[str, str | int | bool]]:
    entries: list[dict[str, str | int | bool]] = []
    for path, content in sorted(files.items()):
        entries.append(
            {
                "path": path,
                "content": content,
                "sha256": _sha256(content),
                "size_bytes": len(content.encode("utf-8")),
                "binary": False,
            }
        )
    for path, data in sorted(binary_files.items()):
        entries.append(
            {
                "path": path,
                "content": base64.b64encode(data).decode("ascii"),
                "sha256": _sha256_bytes(data),
                "size_bytes": len(data),
                "binary": True,
            }
        )
    return entries


async def compare_local_to_active_release() -> list[FirmwareLocalChangeDoc]:
    release = await latest_active_release()
    if release is None:
        return []

    local = _source_files_best_effort()
    local["firmware_version.py"] = _version_file(release.version)
    local_binary = _source_binary_files_best_effort()

    local_files = {path: _file_doc(path, content) for path, content in local.items()}
    local_files.update({path: _binary_file_doc(path, data) for path, data in local_binary.items()})
    active_files = {file.path: file for file in release.files}
    changes: list[FirmwareLocalChangeDoc] = []
    for path in sorted(set(local_files) | set(active_files)):
        local_file = local_files.get(path)
        active_file = active_files.get(path)
        if local_file is None and active_file is not None:
            changes.append(
                FirmwareLocalChangeDoc(
                    path=path,
                    status="removed",
                    active_sha256=active_file.sha256,
                    active_size_bytes=active_file.size_bytes,
                )
            )
        elif local_file is not None and active_file is None:
            changes.append(
                FirmwareLocalChangeDoc(
                    path=path,
                    status="added",
                    local_sha256=local_file.sha256,
                    local_size_bytes=local_file.size_bytes,
                )
            )
        elif local_file and active_file and local_file.sha256 != active_file.sha256:
            changes.append(
                FirmwareLocalChangeDoc(
                    path=path,
                    status="modified",
                    local_sha256=local_file.sha256,
                    active_sha256=active_file.sha256,
                    local_size_bytes=local_file.size_bytes,
                    active_size_bytes=active_file.size_bytes,
                )
            )
    return changes


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


async def get_release(release_id: str) -> FirmwareReleaseDoc | None:
    def _get() -> FirmwareReleaseDoc | None:
        return _release_from_doc(_collection().find_one({"id": release_id}))

    try:
        return await asyncio.to_thread(_get)
    except RuntimeError:
        return None
    except PyMongoError as e:
        log.warning("Firmware database release lookup failed: %s", e)
        raise HTTPException(503, f"Firmware database unavailable: {e}")


async def create_release_from_source(
    *,
    version: str,
    notes: str | None,
    user: User,
    activate: bool = True,
) -> FirmwareReleaseDoc:
    files = source_files()
    binary_files = source_binary_files()
    files["firmware_version.py"] = _version_file(version)
    now = datetime.utcnow()
    doc = {
        "id": str(uuid.uuid4()),
        "version": version,
        "notes": notes,
        "active": False,
        "manifest_hash": manifest_hash(files, binary_files),
        "created_by_user_id": user.id,
        "created_at": now,
        "files": _release_file_entries(files, binary_files),
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
        if item is None and path == "firmware_version.py":
            content = _version_file(str(doc["version"]))
            return FirmwareFileDoc(
                path="firmware_version.py",
                sha256=_sha256(content),
                size_bytes=len(content.encode("utf-8")),
                content=content,
            )
        if not item:
            return None
        return FirmwareFileDoc(
            path=str(item["path"]),
            sha256=str(item["sha256"]),
            size_bytes=int(item["size_bytes"]),
            content=str(item.get("content", "")),
            binary=bool(item.get("binary", False)),
        )

    try:
        return await asyncio.to_thread(_get)
    except RuntimeError:
        return None
    except PyMongoError as e:
        log.warning("Firmware database file lookup failed: %s", e)
        raise HTTPException(503, f"Firmware database unavailable: {e}")
