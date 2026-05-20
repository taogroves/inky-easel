"""Inky Easel app entry point loaded from the SD card.

Boot sequence:
  1. Mount SD card, sync RTC (NTP when online, else PCF85063A), init the display.
  2. Read battery. If critical (<10%) draw the empty-battery screen and
     deep-sleep for an hour without contacting the server.
  3. Connect to Wi-Fi (credentials from secrets.py).
  4. POST /api/frame/poll to the configured server with battery telemetry.
  5. Render whatever the server returns (image / text / plugin).
  6. Overlay the low-battery icon if percent < 20.
  7. Deep-sleep for the duration the server requested.
"""

import gc
import os
import time

import machine
import sdcard

import inky_frame
import inky_helper as ih

import battery
import display as scene
import frame_client


def _import_display():
    """Resolve the PicoGraphics DISPLAY constant from frame_config.DISPLAY_TYPE."""
    from frame_config import DISPLAY_TYPE
    import picographics

    mapping = {
        "inky_frame_4": "DISPLAY_INKY_FRAME_4",
        "inky_frame_5_7": "DISPLAY_INKY_FRAME",
        "inky_frame_7": "DISPLAY_INKY_FRAME_7",
        "inky_frame_7_spectra": "DISPLAY_INKY_FRAME_SPECTRA_7",
    }
    attr = mapping.get(DISPLAY_TYPE, "DISPLAY_INKY_FRAME_SPECTRA_7")
    return picographics.PicoGraphics(getattr(picographics, attr))


def _mount_sd():
    try:
        os.stat("/sd")
        return True
    except OSError:
        pass
    try:
        spi = machine.SPI(0, sck=machine.Pin(18, machine.Pin.OUT),
                          mosi=machine.Pin(19, machine.Pin.OUT),
                          miso=machine.Pin(16, machine.Pin.OUT))
        sd = sdcard.SDCard(spi, machine.Pin(22))
        os.mount(sd, "/sd")
        return True
    except Exception as e:
        print("SD mount failed:", e)
        return False


def _wakeup_reason():
    if inky_frame.woken_by_rtc():
        return "rtc"
    if inky_frame.woken_by_button():
        return "button"
    return "power"


def _deep_sleep(minutes, voltage=None):
    minutes = max(1, int(minutes))
    print("Sleeping for", minutes, "minutes")
    ih.sleep(minutes, voltage=voltage)


def _show_error_then_next(graphics, width, height, message):
    scene.draw_error_screen(graphics, width, height, message)
    graphics.update()
    _deep_sleep(1)


def _connect_wifi():
    try:
        from secrets import WIFI_PASSWORD, WIFI_SSID
    except ImportError:
        print("Missing secrets.py")
        return False
    ih.warn_led(False)
    ih.network_connect(WIFI_SSID, WIFI_PASSWORD)
    import network
    connected = network.WLAN(network.STA_IF).isconnected()
    if connected:
        ih.sync_rtc_time()
    return connected


def _render(graphics, width, height, response):
    kind = response.get("type", "sleep")
    if kind == "image":
        url = response.get("image_url")
        if not url:
            raise RuntimeError("No image URL")
        ih.network_led(100)
        try:
            frame_client.download_jpeg(url)
        finally:
            ih.stop_network_led()
        scene.clear(graphics)
        frame_client.render_image(graphics)
    elif kind == "text":
        payload = response.get("text") or {}
        accent_name = (payload.get("accent") or "BLUE").upper()
        accent = getattr(scene, accent_name, scene.BLUE)
        scene.draw_text_content(
            graphics, width, height,
            payload.get("title", ""),
            payload.get("body", ""),
            accent=accent,
        )
    elif kind == "plugin":
        payload = response.get("plugin") or {}
        code = payload.get("code", "")
        context = payload.get("context") or {}
        frame_client.run_plugin(graphics, width, height, code, context)
    else:
        return


def main():
    time.sleep(0.3)
    ih.all_leds_off()

    ih.sync_rtc_time()

    sd_ok = _mount_sd()
    if not sd_ok:
        print("Continuing without SD; image content will be stored in flash.")
        frame_client.CONTENT_PATH = "/_content.jpg"

    try:
        from frame_config import DEFAULT_SLEEP_MINUTES, FRAME_ID, FRAME_SECRET, SERVER_URL
    except ImportError:
        print("Missing frame_config.py - cannot continue")
        _deep_sleep(15, voltage=None)
        return

    graphics = _import_display()
    width, height = graphics.get_bounds()
    graphics.set_font("bitmap8")

    voltage, percent = battery.read()
    print("Battery {:.2f}V ({}%)".format(voltage, percent))

    if battery.is_critical(percent):
        scene.draw_critical_battery_screen(graphics, width, height)
        _deep_sleep(60, voltage=voltage)
        return

    wakeup = _wakeup_reason()

    if not _connect_wifi():
        _show_error_then_next(graphics, width, height, "Wi-Fi unavailable")
        return

    try:
        ih.network_led(100)
        response = frame_client.poll(SERVER_URL, FRAME_ID, FRAME_SECRET, voltage, percent, wakeup)
    except frame_client.PollError as e:
        ih.stop_network_led()
        print("Poll failed:", e)
        if "Bad JSON" in str(e):
            _show_error_then_next(graphics, width, height, "Bad server response")
        else:
            _show_error_then_next(graphics, width, height, "Server unreachable")
        return
    finally:
        ih.stop_network_led()

    try:
        _render(graphics, width, height, response)
    except Exception as e:
        print("Render failed:", e)
        _show_error_then_next(graphics, width, height, "Render failed")
        return

    if battery.is_low(percent):
        scene.draw_low_battery_overlay(graphics, width, percent)

    try:
        inky_frame.led_busy.on()
        graphics.update()
    finally:
        inky_frame.led_busy.off()
    gc.collect()

    sleep_minutes = int(response.get("sleep_minutes") or DEFAULT_SLEEP_MINUTES)
    print("Server requested sleep_minutes =", sleep_minutes)
    _deep_sleep(sleep_minutes, voltage=voltage)


if __name__ == "__main__":
    main()
