"""FastAPI entry point.

We rely on better-auth (Next.js portal) to create the shared `user`/`session`/
`account`/`verification` tables on first boot. Our own tables are created on
startup with `Base.metadata.create_all`. In production you would migrate with
Alembic; this keeps the bootstrap simple and self-healing.
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from .config import get_settings
from .db import Base, engine
from .models import (  # noqa: F401 ensure metadata sees these tables
    AuthAccount,
    AuthSession,
    AuthVerification,
    ContentCache,
    Frame,
    FrameState,
    InboxItem,
    Plugin,
    ScheduleItem,
    User,
)
from .routers import firmware, frame, frames, inbox, plugins, schedule, setup

settings = get_settings()
log = logging.getLogger("inky-easel.api")
logging.basicConfig(level=logging.INFO)


async def _repair_schema() -> None:
    """Keep dev/self-hosted DBs aligned with lightweight schema changes."""
    statements = [
        "ALTER TABLE ie_inbox_item MODIFY image_bytes LONGBLOB NULL",
        "ALTER TABLE ie_inbox_item ADD COLUMN IF NOT EXISTS thumbnail_mime VARCHAR(64) NULL",
        "ALTER TABLE ie_inbox_item ADD COLUMN IF NOT EXISTS thumbnail_bytes LONGBLOB NULL",
        "ALTER TABLE ie_content_cache MODIFY payload LONGBLOB NOT NULL",
        "ALTER TABLE ie_frame ADD COLUMN IF NOT EXISTS inbox_mode VARCHAR(16) NOT NULL DEFAULT 'open'",
        "ALTER TABLE ie_frame ADD COLUMN IF NOT EXISTS inbox_password VARCHAR(120) NULL",
        "ALTER TABLE ie_frame ADD COLUMN IF NOT EXISTS inbox_repeat_enabled BOOL NOT NULL DEFAULT 0",
        "ALTER TABLE ie_frame ADD COLUMN IF NOT EXISTS inbox_delete_after_displays INT NULL",
        "ALTER TABLE ie_frame ADD COLUMN IF NOT EXISTS schedule_mode VARCHAR(16) NOT NULL DEFAULT 'relative'",
        "ALTER TABLE ie_frame ADD COLUMN IF NOT EXISTS next_expected_poll_at DATETIME NULL",
        "ALTER TABLE ie_frame ADD COLUMN IF NOT EXISTS disconnected_after DATETIME NULL",
        "ALTER TABLE ie_frame ADD COLUMN IF NOT EXISTS last_has_sd_card BOOL NULL",
        "ALTER TABLE ie_frame ADD COLUMN IF NOT EXISTS firmware_version VARCHAR(64) NULL",
        "ALTER TABLE ie_frame ADD COLUMN IF NOT EXISTS target_firmware_version VARCHAR(64) NULL",
        "ALTER TABLE ie_frame ADD COLUMN IF NOT EXISTS last_firmware_status VARCHAR(32) NULL",
        "ALTER TABLE ie_frame ADD COLUMN IF NOT EXISTS last_firmware_update_at DATETIME NULL",
        "ALTER TABLE ie_inbox_item ADD COLUMN IF NOT EXISTS display_count INT NOT NULL DEFAULT 0",
        "ALTER TABLE ie_schedule_item ADD COLUMN IF NOT EXISTS start_minute INT NULL",
    ]
    async with engine.begin() as conn:
        for stmt in statements:
            try:
                await conn.execute(text(stmt))
            except OperationalError as e:
                log.warning("Could not apply schema repair `%s`: %s", stmt, e)


def create_app() -> FastAPI:
    app = FastAPI(title="Inky Easel API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(frame.router)
    app.include_router(frames.router)
    app.include_router(schedule.router)
    app.include_router(inbox.router)
    app.include_router(plugins.router)
    app.include_router(firmware.router)
    app.include_router(setup.router)

    @app.get("/healthz")
    async def healthz():
        return {"ok": True}

    @app.on_event("startup")
    async def _startup() -> None:
        # Wait for the DB to be up, then ensure our tables exist.
        for attempt in range(30):
            try:
                async with engine.begin() as conn:
                    await conn.execute(text("SELECT 1"))
                break
            except OperationalError as e:
                log.info("DB not ready yet (attempt %d): %s", attempt + 1, e)
                await asyncio.sleep(2)
        else:
            log.error("DB did not come up in time")
            return

        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        except OperationalError as e:
            # If the `user` table doesn't exist yet (better-auth hasn't run),
            # our FK references will fail. Create only our `ie_*` tables.
            log.warning("Full schema create failed (%s); creating ie_* tables only", e)
            ie_tables = [
                t for t in Base.metadata.sorted_tables if t.name.startswith("ie_")
            ]
            async with engine.begin() as conn:
                await conn.run_sync(lambda sync_conn: Base.metadata.create_all(sync_conn, tables=ie_tables))
        await _repair_schema()

    return app


app = create_app()
