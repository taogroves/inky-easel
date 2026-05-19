"use client";

import { useState, useTransition } from "react";

import { archiveInboxAction, deleteInboxAction } from "@/lib/actions";
import type { InboxItem } from "@/lib/api";
import { formatDateTime } from "@/lib/time";

export default function InboxList({
  frameId,
  items: initial,
  timezone,
}: {
  frameId: string;
  items: InboxItem[];
  timezone: string | null;
}) {
  const [items, setItems] = useState(initial);
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);

  function archive(id: string) {
    startTransition(async () => {
      const result = await archiveInboxAction(frameId, id);
      if (!result.ok) {
        setError(result.error);
        return;
      }
      setItems((prev) => prev.map((it) => (it.id === id ? { ...it, archived: true } : it)));
    });
  }

  function remove(id: string) {
    if (!confirm("Delete this item?")) return;
    startTransition(async () => {
      const result = await deleteInboxAction(frameId, id);
      if (!result.ok) {
        setError(result.error);
        return;
      }
      setItems((prev) => prev.filter((it) => it.id !== id));
    });
  }

  if (items.length === 0) {
    return <p className="card mt-6 text-sm text-ink-soft">No messages yet. Tell a friend your handle!</p>;
  }

  return (
    <div className="mt-6 space-y-3">
      {error && <p className="text-sm text-red-700">{error}</p>}
      {items.map((item) => (
        <article key={item.id} className={`card ${item.archived ? "opacity-60" : ""}`}>
          <div className="flex items-baseline justify-between gap-3">
            <div>
              <div className="text-xs text-ink-soft">
                {item.sender_label || "Anonymous"} - {formatDateTime(item.created_at, timezone)}
                {item.displayed_at && <span className="ml-2 inline-block rounded bg-emerald-100 px-1.5 text-[10px] text-emerald-800">shown</span>}
                {item.display_count > 0 && <span className="ml-2 inline-block rounded bg-ink/10 px-1.5 text-[10px]">displayed {item.display_count}x</span>}
                {item.archived && <span className="ml-2 inline-block rounded bg-ink/10 px-1.5 text-[10px]">archived</span>}
              </div>
              <h2 className="font-display text-lg">
                {item.kind === "image" ? "Image" : item.text_body ? item.text_body.slice(0, 80) : "(empty)"}
              </h2>
            </div>
            <div className="flex gap-2">
              {!item.archived && (
                <button className="btn-secondary text-xs" onClick={() => archive(item.id)} disabled={pending}>Archive</button>
              )}
              <button className="btn-danger text-xs" onClick={() => remove(item.id)} disabled={pending}>Delete</button>
            </div>
          </div>
          {item.kind === "text" && item.text_body && item.text_body.length > 80 && (
            <p className="mt-3 whitespace-pre-wrap text-sm text-ink-soft">{item.text_body}</p>
          )}
        </article>
      ))}
    </div>
  );
}
