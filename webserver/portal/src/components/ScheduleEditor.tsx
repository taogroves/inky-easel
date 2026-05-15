"use client";

import { useState, useTransition } from "react";

import { saveScheduleAction } from "@/lib/actions";
import type { Plugin, ScheduleItem } from "@/lib/api";

type EditorItem = {
  item_type: ScheduleItem["item_type"];
  item_ref: string | null;
  config: Record<string, unknown> | null;
  sleep_minutes: number;
};

const PRESETS: Array<{ value: EditorItem["item_type"]; label: string; description: string; defaultSleep: number }> = [
  { value: "inbox", label: "Inbox", description: "Show the next unread message from another user.", defaultSleep: 180 },
  { value: "weather", label: "Weather", description: "Current conditions + 4-day forecast for the configured location.", defaultSleep: 60 },
  { value: "xkcd", label: "Daily XKCD", description: "The latest XKCD comic.", defaultSleep: 720 },
  { value: "bbc", label: "BBC headlines", description: "Top headlines from a BBC RSS feed.", defaultSleep: 120 },
  { value: "static", label: "Static text", description: "A fixed title + body you write here.", defaultSleep: 240 },
  { value: "plugin", label: "Custom plugin", description: "Run one of your MicroPython plugins.", defaultSleep: 60 },
];

function blankFor(type: EditorItem["item_type"]): EditorItem {
  const preset = PRESETS.find((p) => p.value === type) ?? PRESETS[0];
  let config: Record<string, unknown> | null = null;
  if (type === "static") config = { title: "Hello", body: "Some text", accent: "BLUE" };
  if (type === "bbc") config = { feed_url: "https://feeds.bbci.co.uk/news/rss.xml" };
  return { item_type: type, item_ref: null, config, sleep_minutes: preset.defaultSleep };
}

export default function ScheduleEditor({
  frameId,
  initial,
  plugins,
}: {
  frameId: string;
  initial: ScheduleItem[];
  plugins: Plugin[];
}) {
  const [items, setItems] = useState<EditorItem[]>(
    initial.map((i) => ({
      item_type: i.item_type,
      item_ref: i.item_ref,
      config: i.config,
      sleep_minutes: i.sleep_minutes,
    })),
  );
  const [pending, startTransition] = useTransition();
  const [message, setMessage] = useState<string | null>(null);

  const totalMinutes = items.reduce((a, b) => a + b.sleep_minutes, 0);

  function update(index: number, patch: Partial<EditorItem>) {
    setItems((prev) => prev.map((it, i) => (i === index ? { ...it, ...patch } : it)));
  }

  function move(index: number, delta: number) {
    setItems((prev) => {
      const next = [...prev];
      const target = index + delta;
      if (target < 0 || target >= next.length) return prev;
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });
  }

  function remove(index: number) {
    setItems((prev) => prev.filter((_, i) => i !== index));
  }

  function add(type: EditorItem["item_type"]) {
    setItems((prev) => [...prev, blankFor(type)]);
  }

  function save() {
    setMessage(null);
    startTransition(async () => {
      const payload = items.map((it) => ({
        item_type: it.item_type,
        item_ref: it.item_ref,
        config: it.config,
        sleep_minutes: it.sleep_minutes,
      }));
      const result = await saveScheduleAction(frameId, payload);
      setMessage(result.ok ? "Schedule saved." : `Error: ${result.error}`);
    });
  }

  return (
    <div className="mt-6 space-y-4">
      <div className="card flex flex-wrap items-center gap-2">
        <span className="text-sm text-ink-soft">Add item:</span>
        {PRESETS.map((p) => (
          <button key={p.value} className="btn-secondary text-xs" onClick={() => add(p.value)}>+ {p.label}</button>
        ))}
        <span className="ml-auto text-xs text-ink-soft">
          Loop duration: <strong>{totalMinutes} min</strong> ({(totalMinutes / 60).toFixed(1)}h)
        </span>
      </div>

      {items.length === 0 && (
        <div className="card text-sm text-ink-soft">No items yet. Add one above.</div>
      )}

      <ol className="space-y-3">
        {items.map((item, idx) => {
          const preset = PRESETS.find((p) => p.value === item.item_type);
          return (
            <li key={idx} className="card">
              <div className="flex items-baseline justify-between gap-3">
                <div>
                  <div className="text-xs text-ink-soft">Step {idx + 1}</div>
                  <h3 className="font-display text-lg">{preset?.label ?? item.item_type}</h3>
                  <p className="text-xs text-ink-soft">{preset?.description}</p>
                </div>
                <div className="flex gap-1">
                  <button className="btn-secondary text-xs" disabled={idx === 0} onClick={() => move(idx, -1)}>&uarr;</button>
                  <button className="btn-secondary text-xs" disabled={idx === items.length - 1} onClick={() => move(idx, 1)}>&darr;</button>
                  <button className="btn-danger text-xs" onClick={() => remove(idx)}>Remove</button>
                </div>
              </div>

              <div className="mt-3 grid gap-3 md:grid-cols-2">
                <div>
                  <label className="label">Sleep after (minutes)</label>
                  <input
                    type="number"
                    className="input"
                    min={1}
                    max={1440}
                    value={item.sleep_minutes}
                    onChange={(e) => update(idx, { sleep_minutes: Number(e.target.value) || 1 })}
                  />
                </div>

                {item.item_type === "static" && (
                  <>
                    <div>
                      <label className="label">Title</label>
                      <input
                        className="input"
                        value={String((item.config as any)?.title ?? "")}
                        onChange={(e) => update(idx, { config: { ...item.config, title: e.target.value } })}
                      />
                    </div>
                    <div className="md:col-span-2">
                      <label className="label">Body</label>
                      <textarea
                        className="input min-h-[80px]"
                        value={String((item.config as any)?.body ?? "")}
                        onChange={(e) => update(idx, { config: { ...item.config, body: e.target.value } })}
                      />
                    </div>
                    <div>
                      <label className="label">Accent color</label>
                      <select
                        className="input"
                        value={String((item.config as any)?.accent ?? "BLUE")}
                        onChange={(e) => update(idx, { config: { ...item.config, accent: e.target.value } })}
                      >
                        {["BLUE", "GREEN", "RED", "YELLOW", "ORANGE", "BLACK"].map((c) => (
                          <option key={c} value={c}>{c}</option>
                        ))}
                      </select>
                    </div>
                  </>
                )}

                {item.item_type === "bbc" && (
                  <div className="md:col-span-2">
                    <label className="label">RSS feed URL</label>
                    <input
                      className="input"
                      value={String((item.config as any)?.feed_url ?? "")}
                      onChange={(e) => update(idx, { config: { ...item.config, feed_url: e.target.value } })}
                    />
                  </div>
                )}

                {item.item_type === "plugin" && (
                  <div>
                    <label className="label">Plugin</label>
                    <select
                      className="input"
                      value={item.item_ref ?? ""}
                      onChange={(e) => update(idx, { item_ref: e.target.value || null })}
                    >
                      <option value="">— Select a plugin —</option>
                      {plugins.map((p) => (
                        <option key={p.id} value={p.id}>{p.name}</option>
                      ))}
                    </select>
                    {plugins.length === 0 && (
                      <p className="mt-1 text-xs text-amber-700">
                        You don&apos;t have any plugins yet.{" "}
                        <a className="underline" href="/dashboard/plugins">Create one</a> first.
                      </p>
                    )}
                  </div>
                )}
              </div>
            </li>
          );
        })}
      </ol>

      <div className="flex items-center gap-3">
        <button className="btn-primary" onClick={save} disabled={pending}>
          {pending ? "Saving..." : "Save schedule"}
        </button>
        {message && <span className="text-xs text-ink-soft">{message}</span>}
      </div>
    </div>
  );
}
