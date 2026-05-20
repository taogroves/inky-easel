# Inky Easel - Frame Firmware

MicroPython firmware for the Inky Frame. Internal flash holds a tiny one-time
loader, while the real app and per-frame configuration live on the SD card. On
each wake-up the app polls the configured webserver, draws whatever the server
says to draw, optionally overlays a low-battery icon, then deep-sleeps for the
requested duration.

## Files

| File | Purpose |
| --- | --- |
| `flash_loader_main.py` | One-time internal-flash loader. Copy this to the frame as `main.py`. |
| `main.py` | SD-card compatibility wrapper for firmware that boots SD `main.py` directly. |
| `inky_easel_app.py` | App entry. Orchestrates wake -> poll -> render -> sleep. |
| `frame_client.py` | HTTP poll, JPEG streaming, plugin runner. |
| `battery.py` | VSYS ADC sampling and percent conversion. |
| `display.py` | Battery overlay, critical-battery screen, text rendering. |
| `inky_helper.py` | Wi-Fi connect, helpers (lifted from Pimoroni examples). |
| `secrets.py.template` | Replace with your Wi-Fi credentials before deploy. |
| `frame_config.py.template` | Replace with your `FRAME_ID` / `FRAME_SECRET` / `SERVER_URL`. |

## One-time flash loader

If your Inky Frame runs internal flash before the SD card, copy
`flash_loader_main.py` to the frame's internal flash as `main.py` once, using
Thonny or another MicroPython file browser. Do not put Wi-Fi credentials or
frame secrets in flash.

The loader mounts `/sd`, puts `/sd` first on `sys.path`, and imports
`/sd/inky_easel_app.py`. After the loader is installed, normal updates only
require rewriting the SD card bundle.

## How the portal deploys this

The Next.js portal renders the setup wizard, generates a per-frame
`frame_config.py` and `secrets.py`, then uses the browser's File System Access
API to write the SD bundle onto a directory the user selects (the mounted SD
card). The bundle includes `inky_easel_app.py`, helper modules, generated
configuration, and a compatibility `main.py` wrapper. The fallback path is a ZIP
download labeled "Inky Easel SD bundle - extract everything to a freshly
FAT32-formatted card".

You do **not** need to flash a custom UF2; the stock Pimoroni Inky Frame
MicroPython build with the `-with-examples` package is sufficient.

## Flash over USB (no SD card)

Use `flash_to_pico.py` to copy a portal setup bundle onto internal flash. You
still generate Wi-Fi and frame credentials in the setup wizard (ZIP download or
any folder with the same files); the CLI only uploads them.

```bash
pip install -r frame-firmware/requirements-flash.txt
python frame-firmware/flash_to_pico.py ~/Downloads/inky-easel-my-frame.zip
```

Plug the Inky Frame in over USB, run the command, then unplug or press reset.
The bundle's `main.py` starts `inky_easel_app.py` from flash. Image downloads
use `/_content.jpg` on flash when no SD card is present.

Options:

| Flag | Purpose |
| --- | --- |
| `--list-devices` | Show serial ports mpremote can use |
| `--device PATH` | Pick a board when several are connected |
| `--dry-run` | Print the file list without copying |
| `--install-sd-loader` | One-time: write `flash_loader_main.py` as `main.py` for the SD workflow |

## Local testing

You can drop the SD app files onto a USB-connected Inky Frame via Thonny to test
without an SD card. `inky_easel_app.py` will detect the missing `/sd` mount and
fall back to writing the content JPEG to flash.

For a physical frame on your Wi-Fi, set `SERVER_URL` to the API URL reachable
from the frame, such as `http://192.168.1.42:8000`. Do not use `localhost`
unless the API is running on the frame itself.
