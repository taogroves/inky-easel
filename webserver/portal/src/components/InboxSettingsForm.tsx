"use client";

import { useState, useTransition } from "react";

import { updateFrameAction } from "@/lib/actions";
import type { FrameWithSecret } from "@/lib/api";

export default function InboxSettingsForm({ frame }: { frame: FrameWithSecret }) {
  const [pending, startTransition] = useTransition();
  const [message, setMessage] = useState<string | null>(null);
  const [inboxMode, setInboxMode] = useState(frame.inbox_mode);

  return (
    <form
      className="card mt-6 space-y-3"
      onSubmit={(e) => {
        e.preventDefault();
        const fd = new FormData(e.currentTarget);
        startTransition(async () => {
          const result = await updateFrameAction(frame.id, fd);
          setMessage(result.ok ? "Inbox settings saved." : `Error: ${result.error}`);
        });
      }}
    >
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <h2 className="font-display text-xl">Inbox settings</h2>
          <p className="text-sm text-ink-soft">Control who can reach your inbox and how it behaves.</p>
        </div>
        <button type="submit" className="btn-primary" disabled={pending}>
          {pending ? "Saving..." : "Save inbox settings"}
        </button>
      </div>

      <div>
        <label className="label" htmlFor="inbox_mode">Who can send to this frame?</label>
        <select
          id="inbox_mode"
          name="inbox_mode"
          className="input"
          value={inboxMode}
          onChange={(e) => setInboxMode(e.target.value as FrameWithSecret["inbox_mode"])}
        >
          <option value="open">Open: anyone signed in can send</option>
          <option value="private">Private: require inbox password</option>
          <option value="closed">Closed: reject new messages</option>
        </select>
      </div>

      {inboxMode === "private" && (
        <div>
          <label className="label" htmlFor="inbox_password">Inbox password</label>
          <input
            id="inbox_password"
            name="inbox_password"
            className="input"
            defaultValue={frame.inbox_password ?? ""}
            placeholder="Share this with friends"
          />
          <p className="mt-1 text-xs text-ink-soft">Stored plainly; use it as a simple shared phrase, not a real secret.</p>
        </div>
      )}

      <label className="flex items-start gap-2 text-sm text-ink-soft">
        <input type="hidden" name="inbox_repeat_enabled" value="off" />
        <input
          type="checkbox"
          name="inbox_repeat_enabled"
          defaultChecked={frame.inbox_repeat_enabled}
          className="mt-1"
        />
        <span>When there are no new inbox items, show the least-recently-displayed item again.</span>
      </label>

      <div>
        <label className="label" htmlFor="inbox_delete_after_displays">Delete inbox items after this many displays</label>
        <input
          id="inbox_delete_after_displays"
          name="inbox_delete_after_displays"
          className="input"
          type="number"
          min={1}
          max={100}
          defaultValue={frame.inbox_delete_after_displays ?? ""}
          placeholder="Never delete automatically"
        />
      </div>

      {message && <p className="text-xs text-ink-soft">{message}</p>}
    </form>
  );
}
