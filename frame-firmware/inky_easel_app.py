"""Inky Easel app entry point loaded from the SD card.

Boot sequence:
  1. Mount SD card, sync RTC (NTP when online, else PCF85063A), init the display.
  2. Read battery. If critical (<10%) draw the empty-battery screen and
     deep-sleep for an hour without contacting the server.
  3. Connect to Wi-Fi (credentials from secrets.py); retry every 2 s if not up yet.
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
import wifi_config

try:
    from firmware_version import FIRMWARE_VERSION
except ImportError:
    FIRMWARE_VERSION = "unknown"


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


def _update_display(graphics):
    try:
        inky_frame.led_busy.on()
        graphics.update()
    finally:
        inky_frame.led_busy.off()


def _reset_cleanly():
    try:
        ih.all_leds_off()
    except Exception as e:
        print("LED cleanup failed:", e)
    time.sleep_ms(100)
    machine.reset()


BUTTONS = (
    inky_frame.button_a,
    inky_frame.button_b,
    inky_frame.button_c,
    inky_frame.button_d,
    inky_frame.button_e,
)
WIFI_SELECTION_MARKER = "/sd/_wifi_select_mode"
WIFI_CONNECT_ATTEMPTS = 3
WIFI_CONNECT_RETRY_SEC = 2


def _button_wake_index():
    for idx, button in enumerate(BUTTONS):
        try:
            if button.raw():
                return idx
        except Exception:
            pass
    return None


def _wifi_selection_pending():
    try:
        os.stat(WIFI_SELECTION_MARKER)
        return True
    except OSError:
        return False


def _mark_wifi_selection_pending():
    try:
        with open(WIFI_SELECTION_MARKER, "w") as f:
            f.write("1")
            f.flush()
    except OSError as e:
        print("Could not mark Wi-Fi selection mode:", e)


def _clear_wifi_selection_pending():
    try:
        os.remove(WIFI_SELECTION_MARKER)
    except OSError:
        pass


def _maybe_switch_wifi_from_button(wakeup):
    if wakeup != "button" or not _wifi_selection_pending():
        return
    idx = _button_wake_index()
    _clear_wifi_selection_pending()
    credentials = wifi_config.get_credentials()
    if idx is None or idx >= len(credentials):
        print("Button wake did not match a configured Wi-Fi slot")
        return
    wifi_config.set_active_wifi_index(idx)
    print("Selected Wi-Fi slot", idx + 1, credentials[idx].get("ssid"))


def _reset_wifi():
    import network

    wlan = network.WLAN(network.STA_IF)
    try:
        wlan.disconnect()
    except OSError:
        pass
    wlan.active(False)
    time.sleep_ms(200)


def _connect_wifi(credential):
    if not credential:
        print("Missing Wi-Fi credentials")
        return False
    ssid = credential.get("ssid")
    password = credential.get("password") or ""
    if not ssid:
        print("Missing Wi-Fi SSID")
        return False

    import network

    ih.warn_led(False)
    for attempt in range(1, WIFI_CONNECT_ATTEMPTS + 1):
        if attempt > 1:
            _reset_wifi()
        print("Wi-Fi attempt {}/{}".format(attempt, WIFI_CONNECT_ATTEMPTS))
        ih.network_connect(ssid, password)
        if network.WLAN(network.STA_IF).isconnected():
            ih.sync_rtc_time()
            return True
        if attempt < WIFI_CONNECT_ATTEMPTS:
            print("Wi-Fi not ready; retry in {} s".format(WIFI_CONNECT_RETRY_SEC))
            time.sleep(WIFI_CONNECT_RETRY_SEC)
    return False


def _render(graphics, width, height, response):
    kind = response.get("type", "sleep")
    if kind == "image":
        url = response.get("image_url")
        if not url:
            raise RuntimeError("No image URL")
        mime = response.get("image_mime") or "image/jpeg"
        posterize = bool(response.get("image_posterize"))
        ih.network_led(100)
        try:
            on_sd = frame_client.CONTENT_PATH.startswith("/sd")
            content_path = frame_client.content_path_for(mime, on_sd=on_sd)
            frame_client.CONTENT_PATH = content_path
            frame_client.download_image(url, content_path, mime=mime)
        finally:
            ih.stop_network_led()
        scene.clear(graphics)
        frame_client.render_image(graphics, content_path, mime=mime, posterize=posterize)
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


def _render_with_battery(graphics, width, height, response, voltage, percent):
    _render(graphics, width, height, response)
    if battery.is_low(percent, voltage):
        scene.draw_low_battery_overlay(graphics, width, percent)


def _scheduled_refresh(graphics, width, height, server_url, frame_id,
                       frame_secret, default_sleep_minutes, voltage, percent,
                       wakeup, has_sd_card=False, credential=None):
    if not _connect_wifi(credential):
        return None, 0, False, "wifi"

    try:
        ih.network_led(100)
        response = frame_client.poll(
            server_url, frame_id, frame_secret, voltage, percent, wakeup,
            has_sd_card=has_sd_card, firmware_version=FIRMWARE_VERSION,
        )
    except frame_client.PollError as e:
        ih.stop_network_led()
        print("Poll failed:", e)
        if "Bad JSON" in str(e):
            _show_error(graphics, width, height, "Bad server response")
        else:
            _show_error(graphics, width, height, "Server unreachable")
        return None, 1, False, "poll"
    finally:
        ih.stop_network_led()

    if response.get("configuration"):
        return response, 0, True, "configuration"

    update = response.get("firmware_update")
    if update:
        try:
            import firmware_updater

            ih.pulse_firmware_update_leds()
            firmware_updater.apply_update(update, current_version=FIRMWARE_VERSION)
            print("Resetting into updated firmware")
            _reset_cleanly()
        except Exception as e:
            ih.stop_firmware_update_leds()
            print("Firmware update failed:", e)
            _show_error(graphics, width, height, "Firmware update failed")
            return None, 1, False, "firmware"

    try:
        _render_with_battery(graphics, width, height, response, voltage, percent)
    except Exception as e:
        print("Render failed:", e)
        _show_error(graphics, width, height, "Render failed")
        return None, 1, False, "render"

    _update_display(graphics)
    gc.collect()
    sleep_minutes = int(response.get("sleep_minutes") or default_sleep_minutes)
    print("Server requested sleep_minutes =", sleep_minutes)
    return response, sleep_minutes, True, "ok"


def _show_error(graphics, width, height, message):
    scene.draw_error_screen(graphics, width, height, message)
    _update_display(graphics)


def _show_wifi_selection_and_sleep(graphics, width, height, voltage):
    credentials = wifi_config.get_credentials()
    scene.draw_wifi_selection_screen(graphics, width, height, credentials)
    _update_display(graphics)
    _mark_wifi_selection_pending()
    ih.all_leds_off()
    for idx, button in enumerate(BUTTONS):
        if idx < len(credentials):
            button.led_on()
    if ih.is_usb_power(voltage):
        print("USB power: waiting forever for Wi-Fi selection button")
        while True:
            for idx, button in enumerate(BUTTONS):
                if idx < len(credentials) and button.read():
                    wifi_config.set_active_wifi_index(idx)
                    _clear_wifi_selection_pending()
                    _reset_cleanly()
            time.sleep_ms(100)
    print("Battery power: turning off until a button selects Wi-Fi")
    inky_frame.turn_off()
    while True:
        time.sleep(60)


def _configuration_status(status="available", message=None):
    config = wifi_config.load()
    return {
        "status": status,
        "message": message,
        "wifi_credentials": config.get("wifi_credentials") or [],
        "active_wifi_index": int(config.get("active_wifi_index") or 0),
        "server_url": config.get("server_url") or "",
        "firmware_version": FIRMWARE_VERSION,
    }


def _flash_configuration_exit_leds():
    ih.stop_configuration_mode_leds()
    for _ in range(3):
        try:
            inky_frame.led_busy.on()
        except AttributeError:
            pass
        ih.network_led(85)
        time.sleep_ms(180)
        try:
            inky_frame.led_busy.off()
        except AttributeError:
            pass
        ih.network_led(0)
        time.sleep_ms(180)


def _apply_configuration(command):
    desired = command.get("config") or {}
    wifi_config.update(
        server_url=desired.get("server_url"),
        wifi_credentials=desired.get("wifi_credentials"),
        active_wifi_index=desired.get("active_wifi_index"),
    )
    update = command.get("firmware_update")
    if update:
        import firmware_updater

        ih.pulse_firmware_update_leds()
        try:
            firmware_updater.apply_update(update, current_version=FIRMWARE_VERSION)
        finally:
            ih.stop_firmware_update_leds()


def _configuration_loop(graphics, width, height, server_url, frame_id, frame_secret,
                        voltage, percent, has_sd_card=False):
    scene.draw_configuration_screen(graphics, width, height, "listening")
    _update_display(graphics)
    ih.pulse_configuration_mode_leds()
    status = _configuration_status("available")

    while True:
        time.sleep(5)
        try:
            voltage, percent = battery.read()
        except Exception:
            pass
        try:
            response = frame_client.poll(
                server_url,
                frame_id,
                frame_secret,
                voltage,
                percent,
                "power",
                has_sd_card=has_sd_card,
                firmware_version=FIRMWARE_VERSION,
                configuration_status=status,
            )
        except frame_client.PollError as e:
            print("Configuration poll failed:", e)
            continue

        command = response.get("configuration") or {}
        mode = command.get("mode")
        if mode == "cancel":
            scene.draw_configuration_screen(graphics, width, height, "cancelled")
            _update_display(graphics)
            _reset_cleanly()
        if mode != "apply":
            continue

        try:
            scene.draw_configuration_screen(graphics, width, height, "saving")
            _update_display(graphics)
            _apply_configuration(command)
            status = _configuration_status("applied", "Configuration saved")
            frame_client.poll(
                server_url,
                frame_id,
                frame_secret,
                voltage,
                percent,
                "power",
                has_sd_card=has_sd_card,
                firmware_version=FIRMWARE_VERSION,
                configuration_status=status,
            )
            _flash_configuration_exit_leds()
            _reset_cleanly()
        except Exception as e:
            print("Configuration apply failed:", e)
            status = _configuration_status("error", str(e))
            scene.draw_configuration_screen(graphics, width, height, "error")
            _update_display(graphics)


def main():
    time.sleep(0.3)
    ih.all_leds_off()

    ih.sync_rtc_time()

    sd_ok = _mount_sd()
    if not sd_ok:
        print("Continuing without SD; content and plugins will use internal flash.")
        frame_client.CONTENT_PATH = "/_content.jpg"
        frame_client.PLUGIN_PATH = "/_plugin.py"

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

    if battery.is_critical(percent, voltage):
        scene.draw_critical_battery_screen(graphics, width, height)
        _deep_sleep(60, voltage=voltage)
        return

    wakeup = _wakeup_reason()
    _maybe_switch_wifi_from_button(wakeup)

    server_url = wifi_config.get_server_url() or SERVER_URL
    credential = wifi_config.get_active_credential()

    response, sleep_minutes, ok, status = _scheduled_refresh(
        graphics, width, height, server_url, FRAME_ID, FRAME_SECRET,
        DEFAULT_SLEEP_MINUTES, voltage, percent, wakeup, has_sd_card=sd_ok,
        credential=credential,
    )

    if not ok:
        if status == "wifi":
            _show_wifi_selection_and_sleep(graphics, width, height, voltage)
            return
        _deep_sleep(1, voltage=voltage)
        return
    if status == "configuration":
        _configuration_loop(
            graphics, width, height, server_url, FRAME_ID, FRAME_SECRET,
            voltage, percent, has_sd_card=sd_ok,
        )
        return
    _deep_sleep(sleep_minutes, voltage=voltage)


if __name__ == "__main__":
    main()
