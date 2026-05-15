"""Battery monitoring for Inky Frame on Pico W / Pico 2 W.

VSYS is exposed on ADC3 (GP29) via a 1/3 voltage divider. On Pico W, sampling
VSYS requires WL_GPIO2 to be enabled so the wireless chip releases the line.
We use a small moving median over several reads to reject noise.
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


def read_voltage(samples: int = 9) -> float:
    readings = []
    for _ in range(samples):
        readings.append(_VSYS.read_u16())
        time.sleep_ms(2)
    readings.sort()
    median = readings[len(readings) // 2]
    return median * _CONVERSION


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


def is_low(percent: int) -> bool:
    return percent < LOW_BATTERY_PCT


def is_critical(percent: int) -> bool:
    return percent < CRITICAL_BATTERY_PCT
