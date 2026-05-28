# For developers

This guide covers advanced frame options, how the system works under the hood, and key design decisions. It assumes you are comfortable editing configuration and reading logs.

Enable **Developer mode** on your **Account** page to unlock extra controls in the portal. Developer mode is per-user and stored in your account settings.

## Developer mode features

| Feature | Where |
| --- | --- |
| Custom API server URL during SD setup | SD setup wizard, step 2 |
| Preview generated bundle file list | SD setup wizard, deploy step |
| Edit API server address during Configure | Configure page |
| Pin a specific firmware release | Configure page |
| Firmware version and status on frame dashboard | Status panel |
| Image delivery details (storage, format, compression) | Status panel |
| Firmware version on dashboard frame cards | Dashboard |

Developer mode does not change frame behavior by itself — it exposes controls that can strand a frame if misused (especially server URL changes).

## Architecture overview

```
Inky Frame (MicroPython)          FastAPI (api)              Next.js (portal)
        |                              |                            |
        |  POST /api/frame/poll          |                            |
        |----------------------------->|                            |
        |  image / text / plugin       |  service auth + user id    |
        |<-----------------------------|<---------------------------|
        |                              |                            |
        |                              |         MariaDB            |
        |                              |<-------------------------->|
```

- The **frame** talks only to the **API** using `frame_id` and a per-frame secret.
- The **portal** manages users, schedules, and configuration through the API with service authentication.
- The frame never contacts the portal directly.

## Boot and poll cycle

Each wake-up (`frame-firmware/inky_easel_app.py`):

1. Mount SD card; sync RTC via NTP when online.
2. If battery &lt; 10%: critical screen, sleep 60 minutes, no server contact.
3. Connect Wi-Fi (3 attempts, 2 s apart).
4. `POST /api/frame/poll` with battery telemetry, firmware version, SD presence.
5. Render response (PNG image, text card, or plugin source).
6. Low-battery overlay if &lt; 20%.
7. Deep-sleep for `sleep_minutes` from server response.

Wake sources: RTC timer, front button, or power-on.

## SD card vs internal flash

**Recommended:** tiny loader on internal flash (`flash_loader_main.py` → `main.py`), full app on SD card.

Benefits:

- Field updates without opening the case
- OTA firmware updates during normal polls
- Wi-Fi and secrets stay on removable media

**Alternative:** flash entire bundle over USB with `flash_to_pico.py` when no SD card is used. Content caches to `/_content.png` on flash instead of SD.

## Wi-Fi and secrets design

Wi-Fi passwords are **never persisted in the database**:

- Initial SD setup writes credentials only to the SD card.
- Configure mode keeps passwords in server **memory** for the duration of the session, then clears them.

Canonical storage: `/sd/inky_easel_config.json` (up to 3 networks, active index, server URL).

Legacy fallback: `/sd/secrets.py` for older bundles.

When connection fails, the on-frame button picker (`/sd/_wifi_select_mode`) lets users switch networks without portal access.

## Configuration mode

When you start **Configure** in the portal:

1. Server marks an in-memory configuration session for the frame.
2. On next poll, the frame receives a command to enter configuration mode.
3. Frame shows **CONFIGURATION MODE** and polls every ~5 seconds.
4. Frame uploads current SD settings (Wi-Fi list, server URL, firmware version).
5. Portal sends desired changes; frame writes `inky_easel_config.json` and reboots.

Configuration interrupts the normal schedule. A 2-minute disconnect grace applies while in this mode.

## Schedule resolution

Schedule state lives on the server (`FrameState.current_index`), not on the frame:

- **Relative mode:** advance index after each poll; wrap at end of list.
- **Calendar mode:** pick item by `start_minute` vs current local time; sleep until next event.

The server renders content (weather, RSS, etc.) into PNG images at the frame's native resolution using six-color Stucki dithering. Plugins return MicroPython source executed on-device.

## Image delivery

Poll responses include image bytes or a download URL depending on SD presence and payload size. Developer mode exposes:

- **Storage** — where the frame writes cached images (SD vs flash)
- **Format** — PNG with posterize decode on device
- **Compression** — transport encoding

Display type (`DISPLAY_TYPE` in `frame_config.py`) is fixed at setup and maps to PicoGraphics constants for 4", 5.7", 7", and 7" Spectra panels.

## OTA firmware updates

When an SD card is present and the server's target firmware version differs from the frame's reported version:

1. Server includes update metadata in poll response.
2. `firmware_updater.py` downloads files, verifies SHA-256.
3. Previous files backed up under `/sd/_firmware_backups`.
4. Verified files swapped in; frame resets.

Developer mode lets you pin a specific firmware release during Configure instead of using the server's active release.

## Connection heuristics

Portal **connected/disconnected** status is computed from:

- `last_seen_at` — last successful poll
- `next_expected_poll_at` — derived from last sleep duration
- Grace window — `max(5, min(30, sleep_minutes * 0.25))` minutes

There is no separate heartbeat from the portal to the frame.

## Server URL configuration

The SD bundle defaults to the API's `public_base_url`. In self-hosted deployments, the portal and API may have different public hostnames — frames must use the **API** URL.

During local development, developer mode can set a LAN address (e.g. `http://192.168.1.42:8000`). The portal may suggest this when accessed from a LAN IP in development mode.

Never use `localhost` in frame configuration unless the API runs on the device itself.

## Frame authentication

Each frame has a unique secret generated at creation. The frame sends `frame_id` and `secret` on every poll. Wrong secrets return HTTP 401; the frame displays **Server unreachable**.

Rotating the secret (SD setup → Regenerate frame secret) invalidates the old secret immediately. You must deploy the new secret via SD setup or Configure.

## Plugins

Plugins are MicroPython modules stored in the portal database. On a plugin schedule item, the server sends source code; the frame executes it with access to the display and frame helpers.

Keep plugins small and avoid desktop-only Python APIs — the frame runs MicroPython.

## USB flash tooling

```bash
pip install -r frame-firmware/requirements-flash.txt
python frame-firmware/flash_to_pico.py ~/Downloads/inky-easel-my-frame.zip
```

Useful flags: `--list-devices`, `--port`, `--no-reset`.

Re-flash after major firmware changes when running without an SD card.

## Key design decisions

1. **SD-first deployment** — Routine updates without USB access; internal flash holds only a minimal loader.

2. **Credentials off-server** — Wi-Fi passwords on SD card (and transiently in memory during Configure). Reduces breach impact.

3. **Server-side schedule pointer** — Frame stays simple; schedule changes take effect without rewriting SD config.

4. **Configuration mode handshake** — Remote Wi-Fi changes without physical SD access, with explicit user initiation (reset required).

5. **Multi-network failover** — Up to three stored networks plus on-device button selection when connect fails.

6. **Battery-aware behavior** — Critical threshold skips network entirely; low threshold shows overlay but continues.

7. **Grace-based disconnect detection** — Longer sleep schedules tolerate more lateness before marking disconnected.

8. **Dual Wi-Fi config format** — JSON canonical, `secrets.py` legacy, for backward-compatible bundles.

9. **OTA with verification** — SHA-256 checked before swap; backups allow manual recovery.

10. **Display-locked at setup** — Hardware type in `frame_config.py` matches physical panel; prevents resolution mismatches.

## Repository layout

| Path | Role |
| --- | --- |
| `frame-firmware/` | MicroPython app, loader, Wi-Fi config, display helpers |
| `webserver/api/` | FastAPI poll endpoint, rendering, schedule resolution |
| `webserver/portal/` | Next.js user portal |
| `docs/` | User and developer documentation (this folder) |

See `frame-firmware/README.md` and root `README.md` for deployment and Docker setup.
