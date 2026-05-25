# Schedule management

The schedule controls what your frame shows on each poll. Edit it from the portal under **Schedule** for any frame.

## Schedule modes

### Relative loop (default)

Items run **top to bottom** in a continuous loop:

1. Show item 1, sleep for its duration
2. Show item 2, sleep for its duration
3. …
4. Return to item 1

Each item has a **sleep duration** in minutes — how long the frame waits before showing the next item. The portal shows the total loop duration (sum of all sleep minutes).

Example: inbox (180 min) → weather (60 min) → XKCD (720 min) completes one loop every 960 minutes (16 hours).

### Calendar mode (24-hour day)

Each item has a **start time** (local to the frame's timezone). At any moment, the frame shows the item whose start time is most recent but still in the past today.

Between events, the frame sleeps until the next start time.

Use calendar mode for morning weather, midday headlines, evening inbox, etc.

Switch modes with the toggle at the top of the schedule editor. The mode is saved with the schedule.

## Schedule item types

| Type | What it shows | Default sleep | Configuration |
| --- | --- | --- | --- |
| **Inbox** | Next unread message from another user | 180 min | — |
| **Weather** | Today's conditions, hourly temp, rain, wind, sun times | 60 min | Celsius or Fahrenheit |
| **Daily XKCD** | Latest XKCD comic | 720 min | — |
| **RSS headlines** | Headlines from any RSS feed | 120 min | Feed URL, optional title |
| **Reddit** | Top posts from a subreddit with QR links | 120 min | Subreddit name |
| **Static text** | Fixed title and body you write | 240 min | Title, body, accent color |
| **Custom plugin** | Your MicroPython plugin | 60 min | Plugin selection |

Click **+ [type]** to add an item. Use the arrow buttons to reorder. Each item can be removed individually.

## Saving changes

Click **Save schedule** to apply. Saving **replaces the entire schedule** and resets the frame to the first item on its next poll.

There is no partial save — review your full list before saving.

## Location and weather

Weather items require a frame **location** (latitude/longitude). Set this during setup or on the frame dashboard under **Edit details**.

If location is missing, the frame shows a text card: **No location configured.**

## Inbox integration

Inbox items pull from your frame's inbox queue. Configure inbox behavior (who can send, display mode) on the **Inbox** page.

If the inbox is empty, the frame shows **Inbox empty**.

## Plugins

Custom plugins are MicroPython scripts you write in the portal under **Plugins**. Add a **Custom plugin** schedule item and select which plugin to run.

If a plugin was deleted but still referenced in the schedule, the frame shows **Plugin missing** or **Plugin was deleted.**

## Content fetch failures

When the server cannot fetch external content (weather API, RSS, Reddit, XKCD), the frame shows a text card explaining the failure, for example:

- Could not fetch weather
- Could not fetch comic / feed / subreddit

These usually resolve on the next poll if the external service recovers. Check feed URLs and subreddit names in the schedule editor.

## Empty schedule

If no items are configured, the frame shows:

> **No schedule** — Set up your schedule in the portal…

Add at least one item and save.

## How the frame advances

The frame itself is stateless about schedule position. On each poll, the server:

1. Reads the current schedule item for this frame
2. Renders the content (image, text, or plugin source)
3. Advances an internal pointer for the next poll
4. Returns how many minutes to sleep

You do not need to sync anything manually — just save the schedule in the portal.

## Tips

- Start with one or two items and short sleep durations while testing.
- Weather and RSS benefit from reasonable sleep times — e-paper updates are slow and frequent polls drain battery.
- Calendar mode requires accurate timezone on the frame (set via location during setup).
- After major schedule changes, the frame picks up the new list on its next wake — you can press reset to force an immediate update.
