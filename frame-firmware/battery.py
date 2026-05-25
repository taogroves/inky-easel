"""Battery monitoring for Inky Frame on Pico W / Pico 2 W.

VSYS is exposed on ADC3 (GP29) via a 1/3 voltage divider. On Pico W, sampling
VSYS requires WL_GPIO2 to be enabled so the wireless chip releases the line.
We average several median-filtered snapshots over time to reject short spikes.
"""

import time

from machine import ADC, Pin

try:
    _WL_VSYS_EN = Pin("WL_GPIO2", Pin.OUT)
    _WL_VSYS_EN.value(1)
except Exception:
    _WL_VSYS_EN = None

_VSYS = ADC(29)
_CONVERSION = (3 * 3.3) / 65535

BATTERY_FULL_V = 4.2
BATTERY_EMPTY_V = 3.2
LOW_BATTERY_PCT = 20
CRITICAL_BATTERY_PCT = 10
USB_VOLTAGE_THRESHOLD = 4.55
MIN_PLAUSIBLE_VSYS_V = 2.0


def _enable_vsys_adc():
    if _WL_VSYS_EN is not None:
        _WL_VSYS_EN.value(1)
        time.sleep_ms(10)


def _read_median_voltage(samples: int) -> float:
    _enable_vsys_adc()
    readings = []
    for _ in range(samples):
        readings.append(_VSYS.read_u16())
        time.sleep_ms(2)
    readings.sort()
    median = readings[len(readings) // 2]
    return median * _CONVERSION


def read_voltage(samples: int = 9, rounds: int = 5, delay_ms: int = 200) -> float:
    samples = max(3, int(samples))
    rounds = max(3, int(rounds))
    voltages = []
    for idx in range(rounds):
        voltages.append(_read_median_voltage(samples))
        if idx < rounds - 1 and delay_ms > 0:
            time.sleep_ms(delay_ms)

    plausible = [v for v in voltages if v >= MIN_PLAUSIBLE_VSYS_V]
    if len(plausible) >= 3:
        voltages = plausible

    voltages.sort()
    if len(voltages) > 2:
        voltages = voltages[1:-1]
    return sum(voltages) / len(voltages)


def voltage_to_percent(voltage: float) -> int:
    if voltage <= 0:
        return 0
    span = BATTERY_FULL_V - BATTERY_EMPTY_V
    pct = (voltage - BATTERY_EMPTY_V) / span * 100
    if pct < 0:
        return 0
    if pct > 100:
        return 100
    return int(pct)


def read():
    voltage = read_voltage()
    return voltage, voltage_to_percent(voltage)


def is_usb_power(voltage: float) -> bool:
    """External power: USB/charge VSYS reads well above LiPo voltage."""
    return voltage >= USB_VOLTAGE_THRESHOLD


def is_low(percent: int, voltage: float = None) -> bool:
    if voltage is not None and is_usb_power(voltage):
        return False
    return percent < LOW_BATTERY_PCT


def is_critical(percent: int, voltage: float = None) -> bool:
    if voltage is not None and is_usb_power(voltage):
        return False
    return percent < CRITICAL_BATTERY_PCT
