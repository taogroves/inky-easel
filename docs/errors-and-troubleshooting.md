# Errors and troubleshooting

This guide explains messages you may see on the frame, in the portal, and how to fix common problems.

## Portal connection status

The frame dashboard **Status** panel tracks whether your frame is polling on schedule.

| Status | Meaning |
| --- | --- |
| **awaiting first check-in** | Frame has never successfully polled. Complete SD setup and reset the frame. |
| **connected** | Frame checked in within the expected window. |
| **disconnected** | Frame missed its expected poll deadline (plus a grace period). |

### Status fields

- **Last check-in** — when the frame last contacted the server
- **Next expected poll** — when the server expects the next wake-up
- **Disconnects after** — deadline after which status becomes disconnected
- **Battery / Voltage** — last reported values from the frame

The disconnect grace window is based on the frame's sleep duration (roughly 25% of sleep minutes, clamped between 5 and 30 minutes). A frame showing weather every 60 minutes gets more slack than one polling every 5 minutes.

## On-frame messages

### BATTERY CRITICAL

**Display:** Red banner "BATTERY CRITICAL" with "Plug me in - sleeping for 1 hour"

**Cause:** Battery below 10% at wake-up.

**Behavior:** Frame does **not** contact the server. Sleeps one hour and tries again.

**Fix:** Plug in USB power or replace/charge the battery pack.

### Low battery overlay

**Display:** Small battery icon with percentage in the corner of normal content.

**Cause:** Battery below 20% but above the critical threshold.

**Behavior:** Frame still polls and renders normally.

**Fix:** Charge soon to avoid missing polls.

### WI-FI UNAVAILABLE

**Display:** Red banner with button slots A–E showing stored network names.

**Cause:** Wi-Fi connection failed after three attempts (2-second retries).

**Fix:**

1. Press **A–E** to switch to another stored network, or
2. Use portal **Configure** to update credentials, or
3. Re-run **SD setup** if you cannot reach the portal

On battery power, the frame powers off until a button selects a network. On USB, it waits indefinitely.

### CONFIGURATION MODE

**Display:** Blue banner "CONFIGURATION MODE" with status text.

**Cause:** Portal **Configure** flow is active.

**Behavior:** Frame polls every ~5 seconds instead of running its schedule.

**Fix:** Complete or cancel configuration in the portal. Keep the frame powered on until **Saved** appears.

### Bad server response

**Cause:** Poll returned data the frame could not parse.

**Fix:** Usually transient or a server bug. Press reset to retry. If persistent, check server logs.

### Server unreachable

**Cause:** HTTP failure — network down, wrong server URL, timeout, or authentication failure (401).

**Fix:**

- Verify Wi-Fi and server URL
- Confirm the API is reachable from the frame's network
- If you rotated the frame secret, rebuild the SD card or reconfigure
- Check firewall rules for the API port

Note: authentication failures appear as **Server unreachable** on the frame, not a separate auth message.

### Firmware update failed

**Cause:** Over-the-air firmware update during poll failed (download, hash mismatch, write error).

**Fix:** Press reset to retry on next poll. If repeated, re-run **SD setup** to refresh firmware files on the card. Check SD card health and free space.

### Render failed

**Cause:** Exception while drawing image, text, or running a plugin.

**Fix:** Press reset. Check schedule items (broken plugin, invalid config). Review plugin code if a custom plugin is involved.

### Content text cards

The server may return text instead of an image when content cannot be rendered:

| Message | Cause | Fix |
| --- | --- | --- |
| No schedule | Empty schedule | Add items in portal |
| No location configured | Weather without lat/lng | Set location on frame dashboard |
| Inbox empty | No unread inbox messages | Normal if inbox is empty |
| Plugin missing / deleted | Schedule references removed plugin | Update schedule |
| Could not fetch weather/comic/feed/subreddit | External API or URL failure | Check URLs, network, retry later |

### Hello! Go to inky.taogroves.com…

**Cause:** Internal flash loader is running but no SD app is installed.

**Fix:** Complete SD setup and insert the card.

## Portal setup errors

| Message | Cause | Fix |
| --- | --- | --- |
| Could not write to card: … | File System Access failed or cancelled | Retry; use ZIP download instead |
| No check-in yet. Press the reset button… | Verify step timed out (5 min) | Check Wi-Fi, server URL, reset frame |
| Frame name is taken | Duplicate handle | Pick a different handle |
| Server URL must be an http(s) URL… | Invalid developer-mode URL | Use full `http://` or `https://` URL |

## Configuration flow errors

| Situation | Fix |
| --- | --- |
| Stuck on Waiting | Reset the frame after starting configuration mode |
| Waiting for the frame | Frame has not entered configuration mode yet — reset it |
| Error state | Read the message; cancel and restart |
| Frame still in configuration mode after cancel | Reset the frame manually |

## Troubleshooting checklist

### Frame never connected

1. SD card inserted and formatted FAT32?
2. Wi-Fi SSID and password correct in bundle?
3. Frame reset after inserting card?
4. API server reachable from frame's network (not `localhost`)?
5. One-time flash loader installed if your board boots internal flash first?

### Frame was connected, now disconnected

1. Wi-Fi still working? Router changes, new password?
2. Battery critical? Plug in and wait.
3. Sleep duration very long? Status may show connected until grace expires.
4. Server down or URL changed?

### Wrong or stale content

1. Schedule saved in portal?
2. Location set for weather?
3. Press reset to force immediate poll.
4. Saving schedule resets to first item — expected behavior.

### Direct SD write unavailable

**Write directly** requires Chrome, Edge, or Opera with File System Access API support. Use **Download ZIP** on other browsers and copy files manually.

## Getting more help

Use the **Troubleshooting** page in the frame dashboard for a quick in-portal overview. For full detail on setup, Wi-Fi, schedules, and developer options, see the other guides in this folder.
