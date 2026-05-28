"""Sleep / RTC test for Inky Frame — flash this file as main.py on internal flash.

Status is shown on the front-panel LEDs (not the e-ink). See README for the pattern key.

Edit DISPLAY below if you also want the e-ink summary (optional).
"""

import os
import sys
import time

import inky_frame
import machine
import network
from machine import ADC, Pin

# --- Configure for your panel (uncomment one) ---
try:
    from picographics import PicoGraphics, DISPLAY_INKY_FRAME_SPECTRA_7 as DISPLAY
except ImportError:
    PicoGraphics = None
    DISPLAY = None
# from picographics import PicoGraphics, DISPLAY_INKY_FRAME_7 as DISPLAY
# from picographics import PicoGraphics, DISPLAY_INKY_FRAME as DISPLAY
# from picographics import PicoGraphics, DISPLAY_INKY_FRAME_4 as DISPLAY

SLEEP_MINUTES = 2
SHOW_SECONDS = 10
BUTTON_SLEEP_MINUTES = 1
COUNTER_FILE = "sleep_test_count.txt"
# VSYS on USB/charge reads high (your 4.77V log); below this we use real power-off sleep.
USB_VOLTAGE_THRESHOLD = 4.55

BUTTONS = (
    inky_frame.button_a,
    inky_frame.button_b,
    inky_frame.button_c,
    inky_frame.button_d,
    inky_frame.button_e,
)


def _all_button_leds_off():
    for btn in BUTTONS:
        btn.led_off()


def _wifi_led(on):
    if on:
        inky_frame.led_wifi.on()
    else:
        inky_frame.led_wifi.off()


def _busy_led(on):
    if on:
        inky_frame.led_busy.on()
    else:
        inky_frame.led_busy.off()


def _all_leds_off():
    _all_button_leds_off()
    _wifi_led(False)
    _busy_led(False)


def _blink_button(btn, times=3, on_ms=120, off_ms=120):
    for _ in range(times):
        btn.led_on()
        time.sleep_ms(on_ms)
        btn.led_off()
        time.sleep_ms(off_ms)


def _chase_buttons(steps=5, on_ms=80, off_ms=40):
    for btn in BUTTONS[:steps]:
        btn.led_on()
        time.sleep_ms(on_ms)
        btn.led_off()
        time.sleep_ms(off_ms)


def _flash_all_buttons(times=4, on_ms=100, off_ms=100):
    for _ in range(times):
        for btn in BUTTONS:
            btn.led_on()
        time.sleep_ms(on_ms)
        _all_button_leds_off()
        time.sleep_ms(off_ms)


def _signal_boot():
    """Power-on: quick A→E chase."""
    print("LED: boot")
    _chase_buttons(5, 100, 50)


def _signal_wake(reason):
    """Wake source (read at boot)."""
    print("LED: wake", reason)
    _all_button_leds_off()
    if reason == "rtc":
        _blink_button(inky_frame.button_d, 4, 200, 150)
    elif reason == "button":
        _blink_button(inky_frame.button_e, 6, 120, 120)
    elif reason == "external":
        _blink_button(inky_frame.button_c, 3, 180, 180)
    else:
        _flash_all_buttons(2, 150, 150)


def _signal_rtc_start():
    """RTC sync starting: A on."""
    print("LED: rtc start")
    _all_button_leds_off()
    inky_frame.button_a.led_on()


def _signal_wifi_connecting():
    """Wi-Fi: B on + WiFi LED blink while connecting."""
    print("LED: wifi connecting")
    inky_frame.button_a.led_off()
    inky_frame.button_b.led_on()


def _signal_wifi_pulse():
    _wifi_led(True)
    time.sleep_ms(80)
    _wifi_led(False)


def _signal_wifi_ok():
    """Connected: B steady + WiFi LED on."""
    print("LED: wifi ok")
    inky_frame.button_b.led_on()
    _wifi_led(True)


def _signal_wifi_fail():
    """No Wi-Fi: B fast blink."""
    print("LED: wifi fail")
    _blink_button(inky_frame.button_b, 5, 80, 80)
    _wifi_led(False)


def _signal_ntp_ok():
    """NTP set_time OK: A+B on."""
    print("LED: ntp ok")
    _all_button_leds_off()
    inky_frame.button_a.led_on()
    inky_frame.button_b.led_on()
    _wifi_led(True)
    time.sleep_ms(400)


def _signal_pcf_ok():
    """PCF fallback: C on."""
    print("LED: pcf ok")
    _all_button_leds_off()
    inky_frame.button_c.led_on()
    time.sleep_ms(400)


def _signal_rtc_fail():
    """RTC sync failed: all buttons panic blink."""
    print("LED: rtc fail")
    _flash_all_buttons(6, 60, 60)


def _signal_display_busy():
    _busy_led(True)


def _signal_display_ok():
    _busy_led(False)
    inky_frame.button_d.led_on()
    time.sleep_ms(300)
    inky_frame.button_d.led_off()


def _signal_display_fail():
    _busy_led(False)
    _flash_all_buttons(3, 100, 100)


def _signal_countdown_tick(second_left):
    """Countdown before sleep: chase moves each second."""
    idx = second_left % len(BUTTONS)
    _all_button_leds_off()
    BUTTONS[idx].led_on()


def _signal_entering_sleep(minutes):
    """About to sleep: E slow blinks, then all off."""
    print("LED: sleep", minutes, "min")
    for _ in range(3):
        inky_frame.button_e.led_on()
        time.sleep_ms(250)
        inky_frame.button_e.led_off()
        time.sleep_ms(250)
    _all_leds_off()


def _signal_usb_sleep():
    """USB path: B+C on (no VSYS power-off)."""
    print("LED: usb sleep mode")
    _all_button_leds_off()
    inky_frame.button_b.led_on()
    inky_frame.button_c.led_on()
    _wifi_led(False)


def _signal_usb_sleep_tick():
    """Heartbeat while waiting on USB."""
    _wifi_led(True)
    time.sleep_ms(60)
    _wifi_led(False)


def _wakeup_reason():
    if inky_frame.woken_by_rtc():
        return "rtc"
    if inky_frame.woken_by_button():
        return "button"
    if inky_frame.woken_by_ext_trigger():
        return "external"
    return "power"


def _load_count():
    try:
        with open(COUNTER_FILE, "r") as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return 0


def _save_count(count):
    with open(COUNTER_FILE, "w") as f:
        f.write(str(count))


def _read_battery():
    try:
        wl = Pin("WL_GPIO2", Pin.OUT)
        wl.value(1)
    except Exception:
        pass
    adc = ADC(29)
    readings = []
    for _ in range(9):
        readings.append(adc.read_u16())
        time.sleep_ms(2)
    readings.sort()
    voltage = readings[len(readings) // 2] * (3 * 3.3) / 65535
    pct = int(max(0, min(100, (voltage - 3.2) / (4.2 - 3.2) * 100)))
    return voltage, pct


def _rtc_time_str():
    year, month, day, hour, minute, second, dow = inky_frame.rtc.datetime()
    return "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(
        year, month, day, hour, minute, second
    )


def _prefer_sd_secrets():
    if "/sd" not in sys.path:
        try:
            os.stat("/sd")
            sys.path.insert(0, "/sd")
        except OSError:
            pass


def _connect_wifi():
    _signal_wifi_connecting()
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.config(pm=0xA11140)
    try:
        from secrets import WIFI_PASSWORD, WIFI_SSID
    except ImportError:
        print("No secrets.py for Wi-Fi")
        _signal_wifi_fail()
        return False
    print("Connecting to", WIFI_SSID)
    wlan.connect(WIFI_SSID, WIFI_PASSWORD)
    for _ in range(15):
        _signal_wifi_pulse()
        if wlan.status() < 0 or wlan.status() >= 3:
            break
        time.sleep(1)
    if wlan.isconnected():
        _signal_wifi_ok()
        return True
    _signal_wifi_fail()
    return False


def _sync_rtc_time():
    """NTP via inky_frame.set_time() when online; else PCF85063A -> Pico RTC."""
    _signal_rtc_start()
    _prefer_sd_secrets()

    if _connect_wifi():
        try:
            inky_frame.set_time()
            print("RTC set from NTP")
            _signal_ntp_ok()
            return "ntp"
        except Exception as e:
            print("NTP set_time failed:", e)

    try:
        inky_frame.pcf_to_pico_rtc()
        print("RTC synced from PCF85063A")
        _signal_pcf_ok()
        return "pcf"
    except Exception as e:
        print("RTC sync failed:", e)
        _signal_rtc_fail()
        return None


def _any_button_pressed():
    return any(btn.raw() for btn in BUTTONS)


def _try_draw_summary(wake, boot_count, rtc_source, voltage, percent, sleep_minutes):
    if PicoGraphics is None or DISPLAY is None:
        print("Display: picographics not available")
        _signal_display_fail()
        return False

    try:
        graphics = PicoGraphics(DISPLAY)
        width, height = graphics.get_bounds()
        _signal_display_busy()
        graphics.set_pen(inky_frame.WHITE)
        graphics.clear()
        graphics.set_pen(inky_frame.BLACK)
        graphics.set_font("bitmap8")
        lines = [
            "Sleep / RTC test",
            "Wake: " + wake,
            "Boot #" + str(boot_count),
            "Time (" + str(rtc_source) + "):",
            _rtc_time_str(),
            "Batt {:.2f}V {}%".format(voltage, percent),
            "Sleep {}m".format(sleep_minutes),
        ]
        y = 8
        for line in lines:
            graphics.text(line, 8, y, width - 16, 2)
            y += 22
        graphics.update()
        _signal_display_ok()
        print("Display: ok")
        return True
    except Exception as e:
        print("Display failed:", e)
        _signal_display_fail()
        return False


def _wait_for_sleep_or_button(default_minutes):
    for remaining in range(SHOW_SECONDS, 0, -1):
        _signal_countdown_tick(remaining)
        if _any_button_pressed():
            _blink_button(inky_frame.button_e, 2, 100, 100)
            return BUTTON_SLEEP_MINUTES
        time.sleep(1)
    return default_minutes


def _is_usb_power(voltage):
    return voltage >= USB_VOLTAGE_THRESHOLD


def _prepare_rtc_alarm(minutes):
    rtc = inky_frame.rtc
    year, month, day, hour, minute, second, dow = rtc.datetime()
    if second >= 55:
        minute += 1
    minutes = min(max(1, int(minutes)), 40320)
    sec_since_epoch = time.mktime((year, month, day, hour, minute, second, dow, 0))
    sec_since_epoch += minutes * 60
    alarm = time.localtime(sec_since_epoch)
    rtc.clear_alarm_flag()
    rtc.set_alarm(0, alarm[4], alarm[3], alarm[2])
    rtc.enable_alarm_interrupt(True)
    return alarm


def _sleep_usb(minutes):
    """Do not call turn_off() on USB — it kills buttons while the shell loop still runs."""
    print("USB sleep: keeping VSYS on for", minutes, "min")
    _signal_usb_sleep()
    inky_frame.vsys.on()
    alarm = _prepare_rtc_alarm(minutes)
    print(
        "RTC alarm at {:04d}-{:02d}-{:02d} {:02d}:{:02d}".format(
            alarm[0], alarm[1], alarm[2], alarm[3], alarm[4]
        )
    )

    wlan = network.WLAN(network.STA_IF)
    try:
        wlan.active(False)
    except Exception:
        pass

    end = time.time() + minutes * 60
    last_print = time.time()
    while time.time() < end:
        if inky_frame.rtc.read_alarm_flag():
            print("Wake: RTC alarm flag (USB test)")
            inky_frame.rtc.clear_alarm_flag()
            _signal_wake("rtc")
            machine.reset()

        if _any_button_pressed():
            print("Wake: button during USB sleep")
            _signal_wake("button")
            machine.reset()

        now = time.time()
        if now - last_print >= 10:
            left = int(end - now)
            print("USB sleep... {}s left".format(left))
            _signal_usb_sleep_tick()
            last_print = now

        time.sleep(0.25)

    print("USB sleep interval over; rebooting")
    machine.reset()


def _sleep_minutes(minutes, voltage):
    if _is_usb_power(voltage):
        _sleep_usb(minutes)
    else:
        print("Battery sleep: power-off via sleep_for")
        inky_frame.sleep_for(minutes)


def main():
    time.sleep(0.3)
    _all_leds_off()
    _signal_boot()

    wake = _wakeup_reason()
    _signal_wake(wake)

    rtc_source = _sync_rtc_time() or "unknown"

    boot_count = _load_count() + 1
    _save_count(boot_count)

    voltage, percent = _read_battery()
    print(
        "Status wake={} boot={} rtc={} batt={:.2f}V".format(
            wake, boot_count, rtc_source, voltage
        )
    )

    sleep_minutes = _wait_for_sleep_or_button(SLEEP_MINUTES)
    _try_draw_summary(wake, boot_count, rtc_source, voltage, percent, sleep_minutes)
    _signal_entering_sleep(sleep_minutes)

    power = "usb" if _is_usb_power(voltage) else "battery"
    print("Sleep test: sleep_min={} power={}".format(sleep_minutes, power))
    _sleep_minutes(sleep_minutes, voltage)


main()
