"""One-time internal-flash loader for Inky Easel.

Copy this file to the Inky Frame's internal flash as main.py. It keeps flash
stable and always runs the real application from /sd/inky_easel_app.py.
"""

import os
import sys
import time

import machine
import sdcard

APP_DIR = "/sd"
APP_MODULE = "inky_easel_app"
APP_FILE = APP_DIR + "/" + APP_MODULE + ".py"
FLASH_APP_FILE = "/" + APP_MODULE + ".py"


def _mount_sd():
    try:
        os.stat(APP_DIR)
        return True
    except OSError:
        pass

    try:
        spi = machine.SPI(0, sck=machine.Pin(18, machine.Pin.OUT),
                          mosi=machine.Pin(19, machine.Pin.OUT),
                          miso=machine.Pin(16, machine.Pin.OUT))
        sd = sdcard.SDCard(spi, machine.Pin(22))
        os.mount(sd, APP_DIR)
        return True
    except Exception as e:
        print("Inky Easel loader: SD mount failed:", e)
        return False


def _app_file_exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False


def _resolve_app_dir():
    if _app_file_exists(APP_FILE):
        return APP_DIR
    if _app_file_exists(FLASH_APP_FILE):
        return ""
    return None


def _prefer_imports(app_dir):
    while APP_DIR in sys.path:
        sys.path.remove(APP_DIR)
    if app_dir == APP_DIR:
        sys.path.insert(0, APP_DIR)
    elif app_dir == "" and "" not in sys.path:
        sys.path.insert(0, "")

    # Avoid accidentally reusing stale app modules from internal flash.
    for name in (
        APP_MODULE,
        "battery",
        "display",
        "frame_client",
        "frame_config",
        "firmware_updater",
        "firmware_version",
        "inky_helper",
        "secrets",
    ):
        if name in sys.modules:
            del sys.modules[name]


def _show_setup_screen():
    try:
        import inky_frame
        from picographics import PicoGraphics, DISPLAY_INKY_FRAME_SPECTRA_7 as DISPLAY

        graphics = PicoGraphics(DISPLAY)
        width, height = graphics.get_bounds()

        graphics.set_pen(inky_frame.WHITE)
        graphics.clear()
        graphics.set_font("bitmap8")

        title = "Hello!"
        title_scale = 6
        graphics.set_pen(inky_frame.BLUE)
        title_w = graphics.measure_text(title, title_scale)
        title_y = height // 2 - 60
        graphics.text(title, (width - title_w) // 2, title_y, width, title_scale)

        subtitle = "Go to inky.taogroves.com to begin setup."
        subtitle_scale = 2
        graphics.set_pen(inky_frame.BLACK)
        subtitle_w = graphics.measure_text(subtitle, subtitle_scale)
        subtitle_y = title_y + (8 * title_scale) + 24
        graphics.text(
            subtitle,
            (width - subtitle_w) // 2,
            subtitle_y,
            width,
            subtitle_scale,
        )

        inky_frame.led_busy.on()
        graphics.update()
        inky_frame.led_busy.off()
        print("Inky Easel loader: setup screen shown")
    except Exception as e:
        print("Inky Easel loader: setup screen failed:", e)


def _sleep_or_reset(minutes=15):
    print("Inky Easel loader: sleeping for", minutes, "minutes")
    try:
        import inky_frame

        inky_frame.sleep_for(minutes)
    except Exception as e:
        print("Inky Easel loader: sleep_for failed, resetting later:", e)
        time.sleep(60 * minutes)
        machine.reset()


def main():
    print("Inky Easel loader: starting")

    _mount_sd()

    app_dir = _resolve_app_dir()
    if app_dir is None:
        print("Inky Easel loader: no app on SD or flash — new device")
        _show_setup_screen()
        _sleep_or_reset()
        return

    _prefer_imports(app_dir)

    try:
        app = __import__(APP_MODULE)
        app.main()
    except Exception as e:
        print("Inky Easel loader: app failed:", e)
        _sleep_or_reset()


main()
