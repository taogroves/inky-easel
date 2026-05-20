"""Inky Easel app entry point loaded from the SD card.

Boot sequence:
  1. Mount SD card, sync RTC (NTP when online, else PCF85063A), init the display.
  2. Read battery. If critical (<10%) and not charging, draw the empty-battery
     screen and deep-sleep for an hour without contacting the server.
  3. Connect to Wi-Fi (credentials from secrets.py); retry every 2 s if not up yet.
  4. POST /api/frame/poll to the configured server with battery telemetry.
  5. Render whatever the server returns (image / text / plugin).
  6. Overlay the battery icon if percent < 20 or charging.
  7. Deep-sleep for the duration the server requested, or stay awake while
     charging and only refresh the battery overlay when needed.
"""

import gc
import json
import os
import time

import machine
import sdcard

import inky_frame
import inky_helper as ih

import battery
import display as scene
import frame_client


CHARGE_STATE_FILE = "inky_easel_charge.json"
CHARGING_DELTA_V = 0.005
CHARGING_CHECK_SECONDS = 60


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


WIFI_CONNECT_ATTEMPTS = 3
WIFI_CONNECT_RETRY_SEC = 2


def _reset_wifi():
    import network

    wlan = network.WLAN(network.STA_IF)
    try:
        wlan.disconnect()
    except OSError:
        pass
    wlan.active(False)
    time.sleep_ms(200)


def _connect_wifi():
    try:
        from secrets import WIFI_PASSWORD, WIFI_SSID
    except ImportError:
        print("Missing secrets.py")
        return False

    import network

    ih.warn_led(False)
    for attempt in range(1, WIFI_CONNECT_ATTEMPTS + 1):
        if attempt > 1:
            _reset_wifi()
        print("Wi-Fi attempt {}/{}".format(attempt, WIFI_CONNECT_ATTEMPTS))
        ih.network_connect(WIFI_SSID, WIFI_PASSWORD)
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


def _render_with_battery(graphics, width, height, response, percent, charging):
    _render(graphics, width, height, response)
    if charging or battery.is_low(percent):
        scene.draw_battery_overlay(graphics, width, percent, charging=charging)


def _scheduled_refresh(graphics, width, height, server_url, frame_id,
                       frame_secret, default_sleep_minutes, voltage, percent,
                       wakeup, charging):
    if not _connect_wifi():
        _show_error(graphics, width, height, "Wi-Fi unavailable")
        return None, 1, False

    try:
        ih.network_led(100)
        response = frame_client.poll(
            server_url, frame_id, frame_secret, voltage, percent, wakeup
        )
    except frame_client.PollError as e:
        ih.stop_network_led()
        print("Poll failed:", e)
        if "Bad JSON" in str(e):
            _show_error(graphics, width, height, "Bad server response")
        else:
            _show_error(graphics, width, height, "Server unreachable")
        return None, 1, False
    finally:
        ih.stop_network_led()

    try:
        _render_with_battery(graphics, width, height, response, percent, charging)
    except Exception as e:
        print("Render failed:", e)
        _show_error(graphics, width, height, "Render failed")
        return None, 1, False

    _update_display(graphics)
    gc.collect()
    sleep_minutes = int(response.get("sleep_minutes") or default_sleep_minutes)
    print("Server requested sleep_minutes =", sleep_minutes)
    return response, sleep_minutes, True


def _show_error(graphics, width, height, message):
    scene.draw_error_screen(graphics, width, height, message)
    _update_display(graphics)


def _charge_state_path(sd_ok):
    if sd_ok:
        return "/sd/" + CHARGE_STATE_FILE
    return "/" + CHARGE_STATE_FILE


def _load_charge_state(path):
    try:
        with open(path, "r") as f:
            data = json.loads(f.read())
        if type(data) is dict:
            return data
    except OSError:
        pass
    except Exception as e:
        print("Charge state load failed:", e)
    return {}


def _save_charge_state(path, voltage, percent, charging):
    data = {
        "last_voltage": round(voltage, 4),
        "last_percent": int(percent),
        "charging": bool(charging),
    }
    try:
        with open(path, "w") as f:
            f.write(json.dumps(data))
            f.flush()
    except Exception as e:
        print("Charge state save failed:", e)


def _number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _voltage_went_up(voltage, state):
    previous = _number(state.get("last_voltage"))
    return previous is not None and voltage > previous + CHARGING_DELTA_V


def _charge_bucket(percent):
    percent = max(0, min(100, int(percent)))
    return percent // 5


def _minutes_until(timestamp):
    remaining = int(timestamp - time.time())
    if remaining <= 0:
        return 1
    return max(1, (remaining + 59) // 60)


def _flash_charge_check_led():
    inky_frame.button_e.led_on()
    time.sleep_ms(120)
    inky_frame.button_e.led_off()


def _disable_wifi_for_charge_monitor():
    ih.stop_network_led()
    try:
        import network

        network.WLAN(network.STA_IF).active(False)
    except Exception:
        pass


def _monitor_charging(graphics, width, height, response, sleep_minutes,
                      state_path, voltage, percent, server_url, frame_id,
                      frame_secret, default_sleep_minutes):
    print("Charging detected; checking battery every minute")
    _disable_wifi_for_charge_monitor()
    inky_frame.vsys.on()

    last_voltage = voltage
    last_bucket = _charge_bucket(percent)
    next_refresh_at = time.time() + max(1, int(sleep_minutes)) * 60
    _save_charge_state(state_path, voltage, percent, True)

    while True:
        time.sleep(CHARGING_CHECK_SECONDS)
        _flash_charge_check_led()

        voltage, percent = battery.read()
        now = time.time()
        print("Charging check {:.2f}V ({}%)".format(voltage, percent))

        if voltage < last_voltage - CHARGING_DELTA_V:
            print("Battery voltage dropped; ending charge monitor")
            _save_charge_state(state_path, voltage, percent, False)
            if now >= next_refresh_at:
                response, sleep_minutes, _ = _scheduled_refresh(
                    graphics, width, height, server_url, frame_id, frame_secret,
                    default_sleep_minutes, voltage, percent, "rtc", False
                )
                _save_charge_state(state_path, voltage, percent, False)
                _deep_sleep(sleep_minutes, voltage=voltage)
            else:
                if response is not None:
                    _render_with_battery(graphics, width, height, response, percent, False)
                    _update_display(graphics)
                    gc.collect()
                _deep_sleep(_minutes_until(next_refresh_at), voltage=voltage)
            return

        if now >= next_refresh_at:
            response, sleep_minutes, _ = _scheduled_refresh(
                graphics, width, height, server_url, frame_id, frame_secret,
                default_sleep_minutes, voltage, percent, "rtc", True
            )
            _disable_wifi_for_charge_monitor()
            next_refresh_at = time.time() + max(1, int(sleep_minutes)) * 60
            last_bucket = _charge_bucket(percent)
        else:
            bucket = _charge_bucket(percent)
            if bucket > last_bucket:
                print("Charge reached {}% bucket".format(bucket * 5))
                if response is not None:
                    scene.draw_battery_overlay(graphics, width, percent, charging=True)
                    _update_display(graphics)
                    gc.collect()
                last_bucket = bucket

        last_voltage = voltage
        _save_charge_state(state_path, voltage, percent, True)


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

    state_path = _charge_state_path(sd_ok)
    charge_state = _load_charge_state(state_path)

    voltage, percent = battery.read()
    charging = _voltage_went_up(voltage, charge_state)
    print("Battery {:.2f}V ({}%) charging={}".format(voltage, percent, charging))
    _save_charge_state(state_path, voltage, percent, charging)

    if battery.is_critical(percent) and not charging:
        _save_charge_state(state_path, voltage, percent, False)
        scene.draw_critical_battery_screen(graphics, width, height)
        _deep_sleep(60, voltage=voltage)
        return

    wakeup = _wakeup_reason()

    response, sleep_minutes, ok = _scheduled_refresh(
        graphics, width, height, SERVER_URL, FRAME_ID, FRAME_SECRET,
        DEFAULT_SLEEP_MINUTES, voltage, percent, wakeup, charging
    )

    if charging:
        _monitor_charging(
            graphics, width, height, response, sleep_minutes,
            state_path, voltage, percent, SERVER_URL, FRAME_ID, FRAME_SECRET,
            DEFAULT_SLEEP_MINUTES
        )
        return

    _save_charge_state(state_path, voltage, percent, False)
    if not ok:
        _deep_sleep(1, voltage=voltage)
        return
    _deep_sleep(sleep_minutes, voltage=voltage)


if __name__ == "__main__":
    main()
