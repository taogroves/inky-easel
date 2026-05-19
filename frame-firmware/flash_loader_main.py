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


def _mount_sd():
    try:
        os.stat(APP_FILE)
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


def _prefer_sd_imports():
    while APP_DIR in sys.path:
        sys.path.remove(APP_DIR)
    sys.path.insert(0, APP_DIR)

    # Avoid accidentally reusing stale app modules from internal flash.
    for name in (
        APP_MODULE,
        "battery",
        "display",
        "frame_client",
        "frame_config",
        "inky_helper",
        "secrets",
    ):
        if name in sys.modules:
            del sys.modules[name]


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

    if not _mount_sd():
        _sleep_or_reset()
        return

    try:
        os.stat(APP_FILE)
    except OSError:
        print("Inky Easel loader: missing", APP_FILE)
        _sleep_or_reset()
        return

    _prefer_sd_imports()

    try:
        app = __import__(APP_MODULE)
        app.main()
    except Exception as e:
        print("Inky Easel loader: app failed:", e)
        _sleep_or_reset()


main()
