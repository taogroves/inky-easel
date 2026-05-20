import json
import math
import os
import time

import inky_frame
import machine
import network
from machine import PWM, Pin, Timer

led_warn = Pin(6, Pin.OUT)

# set up for the network LED
network_led_pwm = PWM(Pin(7))
network_led_pwm.freq(1000)
network_led_pwm.duty_u16(0)


# set the brightness of the network led
def network_led(brightness):
    brightness = max(0, min(100, brightness))  # clamp to range
    # gamma correct the brightness (gamma 2.8)
    value = int(pow(brightness / 100.0, 2.8) * 65535.0 + 0.5)
    network_led_pwm.duty_u16(value)


network_led_timer = Timer(-1)
network_led_pulse_speed_hz = 1


def network_led_callback(_t):
    # updates the network led brightness based on a sinusoid seeded by the current time
    brightness = (math.sin(time.ticks_ms() * math.pi * 2 / (1000 / network_led_pulse_speed_hz)) * 40) + 60
    value = int(pow(brightness / 100.0, 2.8) * 65535.0 + 0.5)
    network_led_pwm.duty_u16(value)


# set the network led into pulsing mode
def pulse_network_led(speed_hz=1):
    global network_led_timer, network_led_pulse_speed_hz
    network_led_pulse_speed_hz = speed_hz
    network_led_timer.deinit()
    network_led_timer.init(period=50, mode=Timer.PERIODIC, callback=network_led_callback)


# turn off the network led and disable any pulsing animation that's running
def stop_network_led():
    global network_led_timer
    network_led_timer.deinit()
    network_led_pwm.duty_u16(0)


def warn_led(on):
    led_warn.value(1 if on else 0)


def all_leds_off():
    stop_network_led()
    warn_led(False)
    clear_button_leds()
    try:
        inky_frame.led_busy.off()
    except AttributeError:
        pass


def sync_rtc_time(ssid=None, password=None):
    """Set Pico + PCF85063A from NTP when Wi-Fi is up; else PCF -> Pico."""
    wlan = network.WLAN(network.STA_IF)

    if ssid is not None and password is not None and not wlan.isconnected():
        network_connect(ssid, password)
        wlan = network.WLAN(network.STA_IF)

    if wlan.active() and wlan.isconnected():
        try:
            inky_frame.set_time()
            print("RTC set from NTP")
            return "ntp"
        except Exception as e:
            print("NTP set_time failed:", e)

    try:
        inky_frame.pcf_to_pico_rtc()
        print("RTC synced from PCF85063A")
        return "pcf"
    except Exception as e:
        print("RTC sync failed:", e)
        return None


USB_VOLTAGE_THRESHOLD = 4.55


def is_usb_power(voltage):
    """USB / charging usually reads well above a LiPo cell alone."""
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


def sleep_usb(minutes):
    """USB-safe wait: keep VSYS held, poll RTC alarm, then reset (no turn_off)."""
    minutes = max(1, int(minutes))
    print("USB power: holding VSYS, polling RTC alarm for", minutes, "min")
    inky_frame.vsys.on()
    alarm = _prepare_rtc_alarm(minutes)
    print("RTC alarm at {:02d}:{:02d} day {}".format(alarm[3], alarm[4], alarm[2]))

    wlan = network.WLAN(network.STA_IF)
    try:
        wlan.active(False)
    except Exception:
        pass

    end = time.time() + minutes * 60
    while time.time() < end:
        if inky_frame.rtc.read_alarm_flag():
            print("RTC alarm fired")
            inky_frame.rtc.clear_alarm_flag()
            machine.reset()
        time.sleep(1)

    print("Sleep interval complete")
    machine.reset()


def sleep(minutes, voltage=None):
    """Deep-sleep on battery; USB-safe simulated sleep when externally powered."""
    minutes = max(1, int(minutes))
    all_leds_off()

    if voltage is None:
        try:
            import battery

            voltage, _ = battery.read()
        except Exception:
            voltage = 0.0

    if is_usb_power(voltage):
        sleep_usb(minutes)
        return

    try:
        inky_frame.sleep_for(minutes)
    except Exception as e:
        print("RTC sleep setup failed:", e)
        time.sleep(60 * minutes)
        machine.reset()


# Turns off the button LEDs
def clear_button_leds():
    inky_frame.button_a.led_off()
    inky_frame.button_b.led_off()
    inky_frame.button_c.led_off()
    inky_frame.button_d.led_off()
    inky_frame.button_e.led_off()


def network_connect(SSID, PSK):
    # Enable the Wireless
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    # Number of attempts to make before timeout
    max_wait = 10

    # Sets the Wireless LED pulsing and attempts to connect to your local network.
    pulse_network_led()
    wlan.config(pm=0xa11140)  # Turn WiFi power saving off for some slow APs
    wlan.connect(SSID, PSK)

    while max_wait > 0:
        if wlan.status() < 0 or wlan.status() >= 3:
            break
        max_wait -= 1
        print("waiting for connection...")
        time.sleep(1)

    stop_network_led()

    # Handle connection error. Switches the Warn LED on.
    if wlan.status() != 3:
        stop_network_led()
        warn_led(True)


state = {"run": None}
app = None


def file_exists(filename):
    try:
        return (os.stat(filename)[0] & 0x4000) == 0
    except OSError:
        return False


def clear_state():
    if file_exists("state.json"):
        os.remove("state.json")


def save_state(data):
    with open("/state.json", "w") as f:
        f.write(json.dumps(data))
        f.flush()


def load_state():
    global state
    data = json.loads(open("/state.json", "r").read())
    if type(data) is dict:
        state = data


def update_state(running):
    global state
    state["run"] = running
    save_state(state)


def launch_app(app_name):
    global app
    app = __import__(app_name)
    print(app)
    update_state(app_name)
