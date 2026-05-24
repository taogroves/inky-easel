# Inky Easel Agent Guide

Inky Easel is a self-hosted e-paper picture frame system for Pimoroni Inky Frame devices. The frame runs MicroPython, polls a FastAPI service for work, and is managed through a Next.js portal backed by MariaDB.

## Project Structure

- `frame-firmware/`: MicroPython code copied to the Inky Frame SD card or internal flash. Important entry points are `flash_loader_main.py`, `main.py`, `inky_easel_app.py`, `frame_client.py`, `firmware_updater.py`, `display.py`, and `inky_helper.py`.
- `webserver/api/`: FastAPI service used by both the physical frame and the portal. It owns frame polling, image/content rendering, firmware release metadata, schedule resolution, and frame setup/configuration endpoints.
- `webserver/portal/`: Next.js app for users and admins. It uses better-auth, Drizzle, MariaDB, server-side calls to the API, and browser-based frame setup flows.
- `webserver/`: Deployment docs, Compose files, and environment examples for running the server stack.
- `inky-frame/`: Untracked upstream Pimoroni documentation/examples kept in the working tree as reference material. Treat it as read-only context unless the user explicitly asks otherwise. Do not add it to commits or refactor against it as if it were product code.

## Docker Setup

Run Docker commands from `webserver/`.

- `docker-compose.yml` is the primary stack. It starts `db` (`mariadb:11`), `api` (FastAPI/Uvicorn), and `portal` (Next.js standalone server).
- `db` is private by default. The API and portal reach it on the Compose network as `db:3306`.
- `api` builds with context `..` using `webserver/api/Dockerfile` so the container can copy both `webserver/api/app` and `frame-firmware`. It exposes port `8000` inside Compose and uses `FRAME_FIRMWARE_DIR=/app/frame-firmware`.
- `portal` builds from `webserver/portal/Dockerfile`, runs on port `3000`, talks to the API at `http://api:8000`, and expects the same `SERVICE_SECRET` as the API.
- For local development, copy `webserver/docker-compose.override.example.yml` to `webserver/docker-compose.override.yml` to publish `localhost` ports for MariaDB, API, and portal.
- `docker-compose.bare-metal.yml` is for direct Docker Compose deployment with explicit host port bindings and required production env vars.
- `docker-compose.coolify-direct.yml` is for Coolify/direct deployments where services are bound to host ports and Traefik labels are disabled.

## Development Notes

- Keep changes scoped to the relevant layer. Firmware runs under MicroPython, not CPython, so avoid introducing desktop-only Python APIs there.
- The frame authenticates with `frame_id` and per-frame `secret`; portal-to-API calls use `X-Service-Auth` plus `X-User-Id`.
- The portal owns Drizzle/better-auth tables. The FastAPI service auto-creates its own `ie_*` tables on startup.
- Physical frame bundles must use an API URL reachable from the frame on the LAN or internet. Do not put `localhost` in frame configuration unless the API is running on the frame itself.
- Be careful with generated or per-device files such as Wi-Fi credentials, frame secrets, setup bundles, firmware release outputs, and local `.env` files.
- The portal and API run on the same server/docker network, but have seperate public domains.

## Verification Expectations

Do not verify routine agent changes by building the full project or starting the Docker stack. In particular, avoid `docker compose up --build`, `docker build`, `npm run build`, or broad end-to-end server startup unless the user explicitly asks.

Instead:

- Inspect the diff carefully with `git diff`.
- Run lightweight, targeted syntax checks for changed files when practical, such as Python compilation for touched CPython API files or TypeScript checks that do not build the app.
- For firmware changes, prefer careful code review and syntax-oriented checks; remember MicroPython compatibility may differ from local CPython.
- Report any checks you skipped and why.
