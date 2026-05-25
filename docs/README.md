# Inky Easel documentation

Inky Easel turns a Pimoroni Inky Frame into a scheduled e-paper picture frame managed through a web portal. Your frame wakes on a timer, contacts the server, renders the next scheduled item, then deep-sleeps until the next poll.

## Guides

| Topic | What you'll learn |
| --- | --- |
| [Frame setup](setup.md) | Create a frame in the portal, write the SD card bundle, and verify the first check-in |
| [Schedule management](schedules.md) | Build looping or calendar-based schedules with weather, RSS, inbox, plugins, and more |
| [Wi-Fi configuration](wifi.md) | Change networks through the portal, rebuild the SD card, or pick a network on the frame |
| [Errors and troubleshooting](errors-and-troubleshooting.md) | Interpret on-frame messages, portal status, and common fixes |
| [For developers](for-developers.md) | Developer mode, deeper frame options, poll protocol, and design decisions |

## Quick reference

### Portal pages (per frame)

| Page | Purpose |
| --- | --- |
| Frame dashboard | Connection status, battery, location, edit details |
| **Configure** | Change Wi-Fi and (in developer mode) server URL without rebuilding the SD card |
| **SD setup** | Initial setup or full SD card refresh (Wi-Fi, secrets, firmware files) |
| **Schedule** | Edit what the frame shows and when |
| **Inbox** | Messages and images sent to the frame |
| **Troubleshooting** | In-portal overview with links back to these docs |

### Typical first-time flow

1. Sign up and create a frame (`+ New frame`).
2. Complete the four-step **SD setup** wizard (location → Wi-Fi → write card → verify).
3. Insert the SD card and press **reset** on the frame.
4. Open **Schedule** and add items.
5. Return to the frame dashboard and confirm status shows **connected**.

### When something goes wrong

Start with the frame dashboard **Status** panel and the in-portal **Troubleshooting** page. For deeper detail, see [Errors and troubleshooting](errors-and-troubleshooting.md).
