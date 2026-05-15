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
  outside URLs - the Inky Frame uses `PUBLIC_BASE_URL` to fetch images.

## Manual smoke tests

Once the stack is up:

```bash
# health
curl -fs http://localhost:8000/healthz

# create a user via the portal, then call the API as if you were the portal:
curl -fs http://localhost:8000/api/frames \
  -H "X-Service-Auth: $SERVICE_SECRET" -H "X-User-Id: <uid>"
```
