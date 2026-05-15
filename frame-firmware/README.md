# Inky Easel - Frame Firmware

MicroPython firmware that lives on the Inky Frame's SD card. On each wake-up
it polls the configured webserver, draws whatever the server says to draw,
optionally overlays a low-battery icon, then deep-sleeps for the requested
duration.

## Files

| File | Purpose |
| --- | --- |
| `main.py` | Boot entry. Orchestrates wake -> poll -> render -> sleep. |
| `frame_client.py` | HTTP poll, JPEG streaming, plugin runner. |
| `battery.py` | VSYS ADC sampling and percent conversion. |
| `display.py` | Battery overlay, critical-battery screen, text rendering. |
| `inky_helper.py` | Wi-Fi connect, helpers (lifted from Pimoroni examples). |
| `secrets.py.template` | Replace with your Wi-Fi credentials before deploy. |
| `frame_config.py.template` | Replace with your `FRAME_ID` / `FRAME_SECRET` / `SERVER_URL`. |

## How the portal deploys this

The Next.js portal renders the setup wizard, generates a per-frame
`frame_config.py` and `secrets.py`, then uses the browser's File System Access
API to write **all** of the files above (plus `inky_helper.py`) onto a directory
the user selects (the mounted SD card). The fallback path is a ZIP download
labeled "Inky Easel SD bundle - extract everything to a freshly FAT32-formatted
card".

You do **not** need to flash a custom UF2; the stock Pimoroni Inky Frame
MicroPython build with the `-with-examples` package is sufficient.

## Local testing

You can drop these files onto a USB-connected Inky Frame via Thonny to test
without an SD card. `main.py` will detect the missing `/sd` mount and fall
back to writing the content JPEG to flash.
