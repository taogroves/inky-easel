# Inky Easel

A scheduled e-paper picture frame system built around the Pimoroni
**Inky Frame** (Raspberry Pi Pico 2 W + 7.3"/5.7"/4.0" Spectra display) and a
self-hosted server.

```
+--------------+ poll /api/frame/poll  +----------+   +--------+
| Inky Frame   | --------------------> | FastAPI  |<->| MariaDB|
| (MicroPython)| <---- JPEG / text --- | (api)    |   +--------+
+--------------+                       +----+-----+        ^
                                            ^              |
                                            | service-auth |
                                       +----+-----+        |
                                       | Next.js  | -------+
                                       | portal   | (better-auth)
                                       +----------+
```

## Repository layout

| Path | What lives there |
| --- | --- |
| `frame-firmware/` | The MicroPython loader and SD-card app files for the Inky Frame. |
| `inky-frame/` | Upstream Pimoroni examples + docs. Used as reference. |
| `webserver/api/` | FastAPI service. The Inky Frame talks to this directly. |
| `webserver/portal/` | Next.js + better-auth + Drizzle (MariaDB) user portal. |
| `webserver/docker-compose.yml` | Brings up MariaDB, the API, and the portal. |

## What it does

* **The Inky Frame** wakes up (RTC or button), measures its battery, contacts
  `/api/frame/poll`, renders the next scheduled item (image / text / custom
  MicroPython plugin), overlays a low-battery icon when below 20%, then
  deep-sleeps for the duration the server requested. If the battery is below
  10% at wake it draws a fullscreen "plug me in" screen and sleeps an hour.

* **The webserver** stores each user's frame configuration, schedule, plugins,
  and inbox. It renders weather (Open-Meteo), the latest XKCD, BBC headlines,
  static text cards, and inbox text/images into JPEGs at the frame's native
  resolution. For custom plugins it just forwards the MicroPython source code.

* **The portal** lets a user sign up, register one or more frames, configure
  their location and Wi-Fi, write the result directly to a microSD card
  (browser's File System Access API, ZIP fallback), build a looping schedule,
  manage their inbox, and write plugins in the browser.

## Getting started

1. Flash any recent Pimoroni MicroPython build (with `-with-examples` if you
   like) onto your Inky Frame. The default board firmware is enough.
2. Copy `frame-firmware/flash_loader_main.py` to the frame's internal flash as
   `main.py`. This is a one-time loader; it runs the app from the SD card.
3. Stand up the server stack:
   ```bash
   cd webserver
   cp .env.example .env       # edit the secrets
   docker compose up --build
   ```
4. Open http://localhost:3000, create an account, click **+ New frame**.
5. Walk through the SD card setup wizard. Plug the SD card into the frame and
   tap reset.
6. Build a schedule. Watch it loop.

See `webserver/README.md` and `frame-firmware/README.md` for component-level
details.

## Customising

* **New schedule item type:** add a branch in
  `webserver/api/app/services/schedule.py:resolve_next_for_frame` and a
  matching renderer in `webserver/api/app/content/renderer.py`. Add it to the
  `PRESETS` array in `webserver/portal/src/components/ScheduleEditor.tsx`.
* **New display size:** map a `DISPLAY_TYPE` string in
  `frame-firmware/inky_easel_app.py:_import_display` and add an entry to
  `DISPLAY_DIMENSIONS` in the renderer.
* **OAuth or other auth providers:** configure better-auth in
  `webserver/portal/src/lib/auth.ts`.

## Limitations / future work

* `ie_content_cache` lives in the database (not S3); fine for a small set of
  frames, but you may want object storage for scale.
* The plugin runtime is fully trusting — plugins run on *your own* Pico, so
  don't import other users' plugins.
* The setup wizard's "write directly" path requires a Chromium-based browser
  (File System Access API). All others fall back to a ZIP download.
