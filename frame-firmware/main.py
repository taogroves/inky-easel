"""Compatibility entry point for SD-first Inky Frame firmware.

New installs should put flash_loader_main.py on internal flash as main.py. This
file stays in the SD bundle so devices that already boot SD main.py still work.
"""

import os
import sys


def _prefer_sd():
    try:
        os.stat("/sd/inky_easel_app.py")
    except OSError:
        return
    while "/sd" in sys.path:
        sys.path.remove("/sd")
    sys.path.insert(0, "/sd")


def main():
    _prefer_sd()
    import inky_easel_app

    inky_easel_app.main()


main()
