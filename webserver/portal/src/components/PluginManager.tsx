"use client";

import { useState, useTransition } from "react";

import { deletePluginAction, savePluginAction } from "@/lib/actions";
import type { Plugin } from "@/lib/api";

const TEMPLATE = `# context contains: frame_name, display_name, latitude, longitude,
# timezone, now_iso (UTC), now_local_iso, plus any item-level config you added in the schedule.
import time

def draw(graphics, width, height, context):
    graphics.set_pen(1)        # WHITE
    graphics.clear()
    graphics.set_pen(0)        # BLACK
    graphics.set_font("bitmap8")
    title = "Hello, " + context.get("display_name", "Inky")
    graphics.text(title, 20, 20, width - 40, 4)
    graphics.text("Drawn at " + context.get("now_iso", ""), 20, 80, width - 40, 2)
`;

type Draft = { id: string | null; name: string; description: string; code: string };

function emptyDraft(): Draft {
  return { id: null, name: "Untitled plugin", description: "", code: TEMPLATE };
}

export default function PluginManager({ initial }: { initial: Plugin[] }) {
  const [plugins, setPlugins] = useState(initial);
  const [draft, setDraft] = useState<Draft>(emptyDraft());
  const [pending, startTransition] = useTransition();
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  function pick(p: Plugin) {
    setDraft({ id: p.id, name: p.name, description: p.description ?? "", code: p.code });
    setMessage(null);
    setError(null);
  }

  function save() {
    setMessage(null);
    setError(null);
    startTransition(async () => {
      const result = await savePluginAction(draft.id, {
        name: draft.name,
        description: draft.description,
        code: draft.code,
      });
      if (!result.ok) {
        setError(result.error);
        return;
      }
      const saved = result.data;
      setPlugins((prev) => {
        const exists = prev.find((p) => p.id === saved.id);
        return exists ? prev.map((p) => (p.id === saved.id ? saved : p)) : [...prev, saved];
      });
      setDraft({ id: saved.id, name: saved.name, description: saved.description ?? "", code: saved.code });
      setMessage("Saved.");
    });
  }

  function remove(id: string) {
    if (!confirm("Delete this plugin? Any schedule item using it will show an error.")) return;
    startTransition(async () => {
      const result = await deletePluginAction(id);
      if (!result.ok) {
        setError(result.error);
        return;
      }
      setPlugins((prev) => prev.filter((p) => p.id !== id));
      if (draft.id === id) setDraft(emptyDraft());
    });
  }

  return (
    <div className="mt-6 grid gap-6 md:grid-cols-[260px,1fr]">
      <aside className="card">
        <button className="btn-secondary w-full" onClick={() => setDraft(emptyDraft())}>+ New plugin</button>
        <ul className="mt-3 space-y-1 text-sm">
          {plugins.map((p) => (
            <li key={p.id}>
              <button
                className={`flex w-full items-center justify-between rounded px-2 py-1 text-left hover:bg-ink/5 ${draft.id === p.id ? "bg-ink/10" : ""}`}
                onClick={() => pick(p)}
              >
                <span className="truncate">{p.name}</span>
              </button>
            </li>
          ))}
          {plugins.length === 0 && <li className="text-xs text-ink-soft">No plugins yet.</li>}
        </ul>
      </aside>

      <section className="card space-y-3">
        <div>
          <label className="label">Name</label>
          <input className="input" value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
        </div>
        <div>
          <label className="label">Description</label>
          <input className="input" value={draft.description} onChange={(e) => setDraft({ ...draft, description: e.target.value })} />
        </div>
        <div>
          <label className="label">MicroPython code</label>
          <textarea
            className="input font-mono text-xs min-h-[420px]"
            value={draft.code}
            spellCheck={false}
            onChange={(e) => setDraft({ ...draft, code: e.target.value })}
          />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button className="btn-primary" onClick={save} disabled={pending}>
            {pending ? "Saving..." : draft.id ? "Save changes" : "Create plugin"}
          </button>
          {draft.id && (
            <button className="btn-danger" onClick={() => remove(draft.id!)} disabled={pending}>
              Delete
            </button>
          )}
          {message && <span className="text-xs text-emerald-700">{message}</span>}
          {error && <span className="text-xs text-red-700">{error}</span>}
        </div>
      </section>
    </div>
  );
}
