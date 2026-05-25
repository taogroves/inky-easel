"use client";

import { useState, useTransition } from "react";

import LocationPicker from "@/components/LocationPicker";
import type { FrameWithSecret } from "@/lib/api";
import { updateFrameAction } from "@/lib/actions";

export default function EditFrameForm({ frame }: { frame: FrameWithSecret }) {
  const [pending, startTransition] = useTransition();
  const [message, setMessage] = useState<string | null>(null);

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        const fd = new FormData(e.currentTarget);
        startTransition(async () => {
          const result = await updateFrameAction(frame.id, fd);
          setMessage(result.ok ? "Saved." : `Error: ${result.error}`);
        });
      }}
      className="mt-3 space-y-3"
    >
      <div>
        <label className="label" htmlFor="display_name">Display name</label>
        <input id="display_name" name="display_name" className="input" defaultValue={frame.display_name} />
      </div>
      <LocationPicker initialLatitude={frame.latitude} initialLongitude={frame.longitude} initialTimezone={frame.timezone} />
      <label className="flex items-start gap-3 rounded border border-ink/10 bg-ink/5 p-3 text-sm">
        <input type="hidden" name="me_and_you_enabled" value="off" />
        <input
          type="checkbox"
          name="me_and_you_enabled"
          defaultChecked={frame.me_and_you_enabled}
          className="mt-1"
        />
        <span>
          <span className="block font-medium">Allow Me and You sharing</span>
          <span className="block text-xs text-ink-soft">
            Friends who know this frame&apos;s handle can compare time, approximate location, and weather with their frame.
          </span>
        </span>
      </label>
      <button type="submit" className="btn-primary" disabled={pending}>
        {pending ? "Saving..." : "Save changes"}
      </button>
      {message && <p className="text-xs text-ink-soft">{message}</p>}
    </form>
  );
}
