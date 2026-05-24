"use client";

import { useState, useTransition } from "react";

import { saveScheduleAction } from "@/lib/actions";
import type { Plugin, ScheduleItem } from "@/lib/api";

type EditorItem = {
  item_type: ScheduleItem["item_type"];
  item_ref: string | null;
  config: Record<string, unknown> | null;
  sleep_minutes: number;
  start_minute: number | null;
};

const PRESETS: Array<{ value: EditorItem["item_type"]; label: string; description: string; defaultSleep: number }> = [
  { value: "inbox", label: "Inbox", description: "Show the next unread message from another user.", defaultSleep: 180 },
  { value: "weather", label: "Weather", description: "Today's conditions with hourly temp, rain chance, wind, and sun times.", defaultSleep: 60 },
  { value: "xkcd", label: "Daily XKCD", description: "The latest XKCD comic.", defaultSleep: 720 },
  { value: "rss", label: "RSS headlines", description: "Magazine-style headlines from any RSS feed (Pimoroni BBC layout).", defaultSleep: 120 },
  { value: "reddit", label: "Reddit", description: "Top posts from a subreddit with QR links (Reddit RSS).", defaultSleep: 120 },
  { value: "static", label: "Static text", description: "A fixed title + body you write here.", defaultSleep: 240 },
  { value: "plugin", label: "Custom plugin", description: "Run one of your MicroPython plugins.", defaultSleep: 60 },
];

function blankFor(type: EditorItem["item_type"]): EditorItem {
  const preset = PRESETS.find((p) => p.value === type) ?? PRESETS[0];
  let config: Record<string, unknown> | null = null;
  if (type === "static") config = { title: "Hello", body: "Some text", accent: "BLUE" };
  if (type === "rss") config = { feed_url: "https://feeds.bbci.co.uk/news/rss.xml" };
  if (type === "reddit") config = { subreddit: "news" };
  if (type === "weather") config = { units: "celsius" };
  return { item_type: type, item_ref: null, config, sleep_minutes: preset.defaultSleep, start_minute: null };
}

function formatStartTime(minutes: number | null): string {
  const value = Math.max(0, Math.min(1439, minutes ?? 8 * 60));
  const h = Math.floor(value / 60);
  const m = value % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

function parseStartTime(value: string): number {
  const [h, m] = value.split(":").map((part) => Number(part));
  if (!Number.isFinite(h) || !Number.isFinite(m)) return 8 * 60;
  return Math.max(0, Math.min(1439, h * 60 + m));
}

export default function ScheduleEditor({
  frameId,
  initialMode,
  initial,
  plugins,
}: {
  frameId: string;
  initialMode: "relative" | "calendar";
  initial: ScheduleItem[];
  plugins: Plugin[];
}) {
  const [scheduleMode, setScheduleMode] = useState<"relative" | "calendar">(initialMode);
  const [items, setItems] = useState<EditorItem[]>(
    initial.map((i, idx) => ({
      item_type: i.item_type,
      item_ref: i.item_ref,
      config: i.config,
      sleep_minutes: i.sleep_minutes,
      start_minute: i.start_minute ?? idx * 60,
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
    setItems((prev) => {
      const next = blankFor(type);
      next.start_minute = prev.length ? ((prev[prev.length - 1].start_minute ?? 8 * 60) + 60) % 1440 : 8 * 60;
      return [...prev, next];
    });
  }

  function save() {
    setMessage(null);
    startTransition(async () => {
      const payload = items.map((it) => ({
        item_type: it.item_type,
        item_ref: it.item_ref,
        config: it.config,
        sleep_minutes: it.sleep_minutes,
        start_minute: scheduleMode === "calendar" ? it.start_minute ?? 0 : null,
      }));
      const result = await saveScheduleAction(frameId, scheduleMode, payload);
      setMessage(result.ok ? "Schedule saved." : `Error: ${result.error}`);
    });
  }

  return (
    <div className="mt-6 space-y-4">
      <div className="card space-y-4">
        <div className="flex flex-wrap items-center gap-3">
          <div>
            <div className="font-display text-lg">Schedule mode</div>
            <p className="text-xs text-ink-soft">
              Relative loops run top to bottom. Day calendar jumps to the event for the frame&apos;s local time.
            </p>
          </div>
          <label className="ml-auto inline-flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={scheduleMode === "calendar"}
              onChange={(e) => setScheduleMode(e.target.checked ? "calendar" : "relative")}
            />
            Use 24-hour day calendar
          </label>
        </div>
        <div className="flex flex-wrap items-center gap-2 border-t border-ink/10 pt-3">
          <span className="text-sm text-ink-soft">Add item:</span>
          {PRESETS.map((p) => (
            <button key={p.value} className="btn-secondary text-xs" onClick={() => add(p.value)}>+ {p.label}</button>
          ))}
          <span className="ml-auto text-xs text-ink-soft">
            {scheduleMode === "relative" ? (
              <>Loop duration: <strong>{totalMinutes} min</strong> ({(totalMinutes / 60).toFixed(1)}h)</>
            ) : (
              <>Events are selected by local clock time.</>
            )}
          </span>
        </div>
      </div>

      {items.length === 0 && (
        <div className="card text-sm text-ink-soft">No items yet. Add one above.</div>
      )}

      <ol className="space-y-0">
        {items.map((item, idx) => {
          const preset = PRESETS.find((p) => p.value === item.item_type);
          return (
            <li key={idx} className="relative pl-10">
              <div className="absolute left-4 top-0 h-full w-px bg-ink/15" />
              <div className="absolute left-[9px] top-6 h-3 w-3 rounded-full bg-ink" />
              <div className="card">
                <div className="flex items-baseline justify-between gap-3">
                  <div>
                    {scheduleMode === "relative" && <div className="text-xs text-ink-soft">Step {idx + 1}</div>}
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
                  {scheduleMode === "calendar" && (
                    <div>
                      <label className="label">Start time</label>
                      <input
                        type="time"
                        className="input"
                        value={formatStartTime(item.start_minute)}
                        onChange={(e) => update(idx, { start_minute: parseStartTime(e.target.value) })}
                      />
                    </div>
                  )}

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
                          {["BLUE", "GREEN", "RED", "YELLOW", "BLACK"].map((c) => (
                            <option key={c} value={c}>{c}</option>
                          ))}
                        </select>
                      </div>
                    </>
                  )}

                  {item.item_type === "weather" && (
                    <div>
                      <label className="label">Temperature units</label>
                      <select
                        className="input"
                        value={String((item.config as { units?: string })?.units ?? "celsius")}
                        onChange={(e) => update(idx, { config: { ...item.config, units: e.target.value } })}
                      >
                        <option value="celsius">Celsius (°C, km/h wind)</option>
                        <option value="fahrenheit">Fahrenheit (°F, mph wind)</option>
                      </select>
                    </div>
                  )}

                  {(item.item_type === "rss" || item.item_type === "bbc") && (
                    <>
                      <div className="md:col-span-2">
                        <label className="label">RSS feed URL</label>
                        <input
                          className="input"
                          placeholder="https://example.com/feed.xml"
                          value={String((item.config as { feed_url?: string })?.feed_url ?? "")}
                          onChange={(e) => update(idx, { config: { ...item.config, feed_url: e.target.value } })}
                        />
                      </div>
                      <div className="md:col-span-2">
                        <label className="label">Header title (optional)</label>
                        <input
                          className="input"
                          placeholder="Leave blank to use the feed title"
                          value={String((item.config as { feed_title?: string })?.feed_title ?? "")}
                          onChange={(e) => update(idx, { config: { ...item.config, feed_title: e.target.value } })}
                        />
                      </div>
                    </>
                  )}

                  {item.item_type === "reddit" && (
                    <div className="md:col-span-2">
                      <label className="label">Subreddit</label>
                      <input
                        className="input"
                        placeholder="news, worldnews, or front for the home feed"
                        value={String((item.config as { subreddit?: string })?.subreddit ?? "")}
                        onChange={(e) => update(idx, { config: { ...item.config, subreddit: e.target.value } })}
                      />
                      <p className="mt-1 text-xs text-ink-soft">
                        Uses Reddit&apos;s public RSS feed (e.g. r/news → reddit.com/r/news/.rss).
                      </p>
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
              </div>

              {scheduleMode === "relative" && (
                <div className="relative py-3 pl-4">
                  <div className="inline-flex items-center gap-2 rounded border border-dashed border-ink/20 bg-ink/5 p-2 text-sm text-ink-soft">
                    <span>Wait</span>
                    <input
                      type="number"
                      className="input w-20 py-1 text-sm"
                      min={1}
                      max={1440}
                      value={item.sleep_minutes}
                      onChange={(e) => update(idx, { sleep_minutes: Number(e.target.value) || 1 })}
                    />
                    <span>min</span>
                  </div>
                </div>
              )}
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
