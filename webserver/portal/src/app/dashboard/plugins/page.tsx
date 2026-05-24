import Link from "next/link";

import PluginManager from "@/components/PluginManager";
import { api, type Plugin } from "@/lib/api";

export default async function PluginsPage() {
  let plugins: Plugin[] = [];
  try {
    plugins = await api<Plugin[]>("/api/plugins");
  } catch {
    plugins = [];
  }
  return (
    <div>
      <Link href="/dashboard" className="text-xs uppercase tracking-wide text-ink-soft hover:underline">&larr; Back to dashboard</Link>
      <h1 className="mt-3 font-display text-3xl">Your plugins</h1>
      <p className="mt-2 max-w-prose text-sm text-ink-soft">
        Plugins are short MicroPython files that run directly on your Inky Frame.
        Each plugin must define a top-level <code>draw(graphics, width, height, context)</code>{" "}
        function. Use the <code>graphics</code> object exactly like in{" "}
        <a
          href="https://github.com/pimoroni/inky-frame/tree/main/examples"
          target="_blank"
          rel="noopener noreferrer"
          className="text-ink-faint underline hover:text-ink-accent"
        >
          these examples
        </a>
        .
      </p>
      <PluginManager initial={plugins} />
    </div>
  );
}
