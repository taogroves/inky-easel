# Sleep / RTC test firmware

Standalone MicroPython app to verify deep sleep on a physical Inky Frame.

## Flash (Thonny or file browser)

1. Use the stock Pimoroni Inky Frame MicroPython image (`-with-examples` is fine).
2. Copy **`main.py`** from this folder to the frame’s **internal flash** as `main.py` (replace any existing loader/app temporarily).
3. Open **`main.py`** and set `DISPLAY` to match your panel (see the commented imports at the top).
4. Copy **`secrets.py`** (Wi-Fi credentials) to internal flash or `/sd` so the frame can run `inky_frame.set_time()` over NTP. Without it, the test falls back to the PCF85063A clock.
5. Optionally change `SLEEP_MINUTES` (default `2` for a quick loop).

Reset the board. **Status is shown on the LEDs** (the e-ink update is optional).

## USB power (important)

Pimoroni’s `inky_frame.sleep_for()` always calls `turn_off()` (`vsys.off()`). On **USB**, the board often cannot actually power down, but VSYS hold is still released — buttons and peripherals stop working while MicroPython keeps running the minute-count loop. That matches “shell twitched after 1 min but nothing else / buttons dead”.

This test detects USB power (battery voltage **≥ 4.55 V**, e.g. your 4.77 V reading) and uses a **USB-safe path** instead:

- Keeps `vsys.on()` (no `turn_off()`)
- Sets the same RTC alarm as `sleep_for()`
- Polls `rtc.read_alarm_flag()` every 250 ms
- **B + C** LEDs on during the wait; **WiFi** LED blinks every 10 s
- Press a button to wake early
- On alarm, button, or timeout → `machine.reset()` so you get a full reboot (boot chase, new shell output)

For a true power-off + RTC wake test, run on **battery** (expect **D** blink = RTC wake).

## LED pattern key

| Pattern | Meaning |
| --- | --- |
| A→E chase (fast) | Boot / test started |
| D blinks | Woke from **RTC alarm** |
| E blinks | Woke from **button** |
| C blinks | Woke from **external** trigger |
| All flash twice | Woke from **power** / USB reset |
| **A** steady | RTC sync started |
| **B** steady + WiFi LED blinking | Connecting to Wi-Fi |
| **B** steady + WiFi LED on | Wi-Fi connected |
| **B** fast blink | Wi-Fi failed (falls back to PCF clock) |
| **A + B** on | NTP time set (`inky_frame.set_time()`) |
| **C** on | PCF85063A clock used (no NTP) |
| All buttons fast blink | RTC sync failed |
| **Busy** LED on | E-ink updating (if display works) |
| **D** brief on | E-ink update finished |
| All fast blink | E-ink failed (test continues anyway) |
| **A→E** moves each second | Countdown before sleep (10s) |
| **E** slow triple blink | About to sleep |
| **B + C** on | **USB sleep** — waiting for alarm (VSYS stays on) |
| WiFi LED blink every 10 s | USB sleep heartbeat |

## What to expect

| Power | Behaviour |
| --- | --- |
| **Battery** (< ~4.55 V on VSYS) | `inky_frame.sleep_for()` powers off; next boot **Wake: rtc** and **Boot #** increments. |
| **USB** (≥ ~4.55 V) | No power-off; polls RTC alarm; reboots when alarm fires. Shell prints `USB sleep...` countdown. |

## Restore normal firmware

Copy `../flash_loader_main.py` back to internal flash as `main.py`, or reinstall your usual SD bundle loader.

## Production app

`../inky_helper.py` uses the same USB detection in `sleep()` so development on USB does not hit `turn_off()` either.
