# Frame setup

This guide walks through setting up a new Inky Frame from scratch using the portal and a microSD card.

## What you need

- A Pimoroni Inky Frame (4", 5.7", 7", or 7" Spectra) running the stock Pimoroni MicroPython build
- A microSD card formatted as **FAT32**
- Your Wi-Fi network name (SSID) and password
- A computer with Chrome, Edge, or Opera (for direct SD card writing) or any browser (for ZIP download)

## One-time internal flash loader (recommended)

Before your first SD setup, install the tiny loader on the frame's internal flash **once**:

1. Connect the frame to your computer over USB.
2. Open Thonny (or another MicroPython file browser).
3. Copy `frame-firmware/flash_loader_main.py` to internal flash as `main.py`.

After this, all normal updates happen through the SD card or over-the-air during polls. You do not need to open the case again for routine firmware updates.

If no SD app is installed yet, the loader shows:

> Hello! Go to inky.taogroves.com to begin setup.

## Create a frame in the portal

1. Sign in and open **Dashboard**.
2. Click **+ New frame**.
3. Fill in:
   - **Handle** — lowercase letters, numbers, and hyphens only (3–64 characters). This is permanent and globally unique.
   - **Display name** — friendly name shown in the portal.
   - **Location** — used for weather and calendar scheduling. Pick a point on the map.
   - **Display type** — must match your physical hardware. This is written to the SD card and cannot be changed casually afterward.
4. Click **Create & continue to SD setup**.

You are redirected to the four-step setup wizard.

## SD setup wizard

### Step 1: Confirm location and display

Review the map pin and timezone. Adjust if needed, then click **Continue**.

Location affects weather content and calendar schedule timing. You can change it later on the frame dashboard under **Edit details**.

### Step 2: Wi-Fi credentials

Enter the Wi-Fi **SSID** and **password** the frame should use.

- Credentials are written **only to the SD card**, not stored on the server.
- In [developer mode](for-developers.md), you can optionally override the **API server address**. Use an `http://` or `https://` URL reachable from the frame's network — never `localhost` unless the API literally runs on the frame itself.

Click **Build SD bundle** when ready.

### Step 3: Write to SD card

The portal generates a bundle containing:

| File | Purpose |
| --- | --- |
| `inky_easel_app.py` and helpers | Frame application and firmware modules |
| `frame_config.py` | Frame ID, secret, display type, server URL |
| `inky_easel_config.json` | Wi-Fi network list and server URL (canonical config) |
| `secrets.py` | Legacy Wi-Fi fallback |
| `main.py` | SD compatibility wrapper |
| `README.txt` | Copy instructions |

Choose one deployment method:

- **Write directly** (Chrome/Edge/Opera) — select the mounted SD card folder. The browser writes all files to the card root.
- **Download ZIP** — extract everything to the root of a freshly formatted FAT32 card.

Optional: **Regenerate frame secret** rotates the authentication secret on the server. You must rebuild and rewrite the SD card afterward, or the frame will fail to authenticate.

### Step 4: Verify connection

1. Safely eject the SD card and insert it into the frame.
2. Press the **reset** button (or power-cycle).
3. Click **Verify connection** in the portal.

The portal polls for up to five minutes. When the frame checks in, you see a success message with the check-in time.

If verification stalls:

- Confirm Wi-Fi credentials are correct.
- Ensure the frame can reach the API server from your LAN (firewall, wrong server URL).
- Press reset again and retry.

## After setup

Once connected:

1. Open **Schedule** and add content.
2. Optionally configure **Inbox** settings for messages from other users.
3. Use the frame dashboard **Status** panel to monitor battery and connection.

## Re-running SD setup

Use **SD setup** from the frame dashboard when you need to:

- Replace the SD card
- Refresh all firmware files on the card
- Change Wi-Fi during initial deployment (before the frame has ever connected)
- Apply a rotated frame secret

For changing Wi-Fi on an already-connected frame, **Configure** is usually easier — see [Wi-Fi configuration](wifi.md).

## USB flash without an SD card

Advanced users can deploy the same bundle to internal flash using `frame-firmware/flash_to_pico.py`. See [For developers](for-developers.md) for details.
