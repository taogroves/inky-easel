# Wi-Fi configuration

Inky Easel stores Wi-Fi credentials on the frame's SD card, not in the portal database. There are three ways to change networks depending on your situation.

## How Wi-Fi is stored

The frame reads networks from `/sd/inky_easel_config.json` (up to **five** networks). If that file is missing or empty, it falls back to legacy `/sd/secrets.py`.

Each network entry has an SSID and password. One network is marked **active** and tried first on each wake-up.

The API server address (`server_url`) is also stored in `inky_easel_config.json`. It must be reachable from the frame's Wi-Fi network.

## Method 1: Configure through the portal (recommended)

Use this when the frame is already set up and can still reach the server (or will after you fix Wi-Fi).

1. Open the frame dashboard and click **Configure**.
2. Click **Start configuration mode**.
3. **Reset the frame** manually.
4. Wait for the frame display to show **CONFIGURATION MODE** and for the portal to show **Connected**.
5. Edit Wi-Fi networks:
   - Add, remove, or change SSID/password fields
   - Select which network is **Active**
6. Click **Save and exit**.

The frame writes the new config to its SD card and reboots. Wi-Fi passwords exist only in the server's memory during this session — they are never saved to the database.

### Configuration session states

| State | What it means |
| --- | --- |
| Idle | Ready to start |
| Waiting... | Portal is ready; reset the frame |
| Connecting... | Frame checked in and is entering configuration mode |
| Connected | Edit settings and save |
| Saving... | Frame is writing new settings |
| Saved | Frame confirmed and rebooted |
| Error | Something failed — read the message, cancel, and retry |

Keep the frame **powered on** throughout configuration mode. If stuck, click **Cancel**, reset the frame, and start again.

## Method 2: SD setup (full card refresh)

Use this when:

- The frame has never connected
- You replaced the SD card
- Configure mode is unavailable and you have physical access to the card
- You rotated the frame secret and need a fresh bundle

1. Open **SD setup** from the frame dashboard.
2. Re-enter Wi-Fi credentials (and location if needed).
3. Build and write a new bundle to the SD card.
4. Insert the card and reset the frame.

This rewrites all firmware files and configuration, not just Wi-Fi.

## Method 3: On-frame network picker

When Wi-Fi connection fails after three attempts, the frame shows **WI-FI UNAVAILABLE**.

- Buttons **A** through **E** map to stored network slots 1–5.
- LEDs indicate which slots have configured networks.
- Press a button to switch to that network; the frame tries again.

On **USB power**, the frame waits indefinitely for a button press. On **battery**, it turns off until a button wake selects a network.

This works without the portal — useful when you moved the frame to a location with a different network that you already stored as slot B, C, etc.

To add new networks beyond what is already on the card, use **Configure** or **SD setup**.

## Adding multiple networks

In **Configure**, click **Add network** (up to five total). Typical uses:

- Home and office Wi-Fi
- Phone hotspot as backup
- Guest network

Mark one network as **Active**. The frame tries the active network first; the on-frame picker lets you switch among stored networks without a portal session.

## Server URL notes

By default, the SD bundle points at the server's public API URL. The portal hostname and API hostname may differ in self-hosted deployments — the frame must reach the **API**, not the portal.

In developer mode, you can edit the server URL during SD setup or Configure. Use a LAN IP during local development (e.g. `http://192.168.1.42:8000`). Never use `localhost` — that refers to the frame itself.

## Troubleshooting Wi-Fi

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| WI-FI UNAVAILABLE on display | Wrong password, out of range, or wrong network | Press A–E to try another stored network, or use Configure / SD setup |
| Frame never checks in | Server URL unreachable | Verify API is on the LAN/internet; check firewall |
| Configure stuck on Waiting | Frame not reset or wrong Wi-Fi | Reset frame; ensure it can still reach server on current network |
| Auth works but no content | Unrelated to Wi-Fi | Check schedule and location settings |

See [Errors and troubleshooting](errors-and-troubleshooting.md) for more detail.
