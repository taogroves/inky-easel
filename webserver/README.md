# Inky Easel - Webserver

This folder runs every server-side component:

| Service | Folder | Port | Notes |
| --- | --- | --- | --- |
| `db` | (volume only) | 3306 | MariaDB 11. Holds better-auth + portal tables. |
| `api` | `api/` | 8000 | FastAPI / Uvicorn. The Inky Frame talks here directly. |
| `portal` | `portal/` | 3000 | Next.js 15 + better-auth. The user-facing UI. |

The two HTTP services share the same MariaDB database. The portal owns
schema migrations (Drizzle). FastAPI auto-creates its own `ie_*` tables on
startup.

## Quick start (local)

```bash
cd webserver
cp .env.example .env            # then edit the secrets
docker compose up --build
# wait for "Uvicorn running" and "Ready in..." messages
```

Then visit http://localhost:3000 to create the first user.

### Local physical frame setup

For fast local iteration, keep using the local portal in your browser, but build
the frame bundle with a server URL the frame can reach on your LAN:

1. Start the stack with `docker compose up --build`.
2. Find your development machine's LAN IP, for example `ipconfig getifaddr en0`
   on macOS.
3. If this is the first setup for the physical frame, copy
   `../frame-firmware/flash_loader_main.py` to internal flash as `main.py`.
4. In the setup wizard's "Frame server URL" field, enter
   `http://<lan-ip>:8000`.
5. Write the bundle to the SD card and reset the frame.

Do not use `localhost` in a physical frame bundle. On the Pico, `localhost`
means the frame itself. Image asset URLs are generated from the same origin the
frame used for `POST /api/frame/poll`, so a frame polling the LAN URL will also
fetch images from that LAN URL.

## Auth model

* Browser <-> Portal: better-auth (email + password by default; add OAuth in
  `portal/src/lib/auth.ts`).
* Portal <-> API: every server-side call adds the headers
  `X-Service-Auth: <SERVICE_SECRET>` and `X-User-Id: <user id>`. FastAPI trusts
  those if the shared secret matches.
* Frame <-> API: the Inky Frame includes its `frame_id` and per-frame `secret`
  in every poll body. The secret is generated server-side when the frame is
  created and re-rotatable from the portal.

## Frame protocol

`POST /api/frame/poll`

```json
{
  "frame_id": "<uuid>",
  "secret": "<token>",
  "server_url": "http://<lan-ip>:8000",
  "battery_voltage": 3.92,
  "battery_percent": 84,
  "wakeup": "rtc"
}
```

Response:

```json
{
  "type": "image",
  "image_url": "https://easel.example.com/api/frame/asset/<token>",
  "sleep_minutes": 60,
  "low_battery_warning": false
}
```

`type` can be `image`, `text`, `plugin`, or `sleep`. The frame fetches
`image_url` (if present) and decodes it with `jpegdec`, or runs the plugin
code, or draws the inline text.

## Coolify deployment

* Point Coolify at this folder's `docker-compose.yml`.
* Set every variable from `.env.example` in the Coolify UI.
* Map `easel.example.com` to the `portal` service and (optionally) a separate
  subdomain to the `api` service (or expose `api` via the portal's reverse
  proxy if you'd rather not).
* Make sure `PUBLIC_BASE_URL` and `BETTER_AUTH_URL` resolve to the right
  outside URLs. Production setup bundles default to `PUBLIC_BASE_URL`; local
  development can override the frame URL per bundle from the setup wizard.

## Manual smoke tests

Once the stack is up:

```bash
# health
curl -fs http://localhost:8000/healthz

# create a user via the portal, then call the API as if you were the portal:
curl -fs http://localhost:8000/api/frames \
  -H "X-Service-Auth: $SERVICE_SECRET" -H "X-User-Id: <uid>"
```
