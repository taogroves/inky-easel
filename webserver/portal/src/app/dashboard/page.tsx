import Link from "next/link";
import { headers } from "next/headers";
import { redirect } from "next/navigation";

import { auth } from "@/lib/auth";
import { api, type Frame } from "@/lib/api";
import { parseApiDate } from "@/lib/time";

function batteryBadge(pct: number | null): { label: string; cls: string } {
  if (pct == null) return { label: "no data", cls: "bg-ink/10 text-ink-soft" };
  if (pct < 10) return { label: `${pct}% critical`, cls: "bg-red-100 text-red-800" };
  if (pct < 20) return { label: `${pct}% low`, cls: "bg-amber-100 text-amber-800" };
  return { label: `${pct}%`, cls: "bg-emerald-100 text-emerald-800" };
}

function relativeTime(iso: string | null): string {
  if (!iso) return "never";
  const then = parseApiDate(iso).getTime();
  const diff = Date.now() - then;
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

function relativeFuture(iso: string | null): string {
  if (!iso) return "unknown";
  const then = parseApiDate(iso).getTime();
  const diff = then - Date.now();
  if (diff <= 0) return "now";
  const mins = Math.ceil(diff / 60000);
  if (mins < 60) return `in ${mins}m`;
  const hours = Math.ceil(mins / 60);
  if (hours < 24) return `in ${hours}h`;
  return `in ${Math.ceil(hours / 24)}d`;
}

function connectionBadge(frame: Frame): { label: string; dot: string; cls: string } {
  if (frame.connection_status === "disconnected") {
    return { label: "disconnected", dot: "bg-red-500", cls: "text-red-800" };
  }
  if (frame.connection_status === "awaiting_first_check_in") {
    return { label: "awaiting first check-in", dot: "bg-amber-500", cls: "text-amber-800" };
  }
  return { label: "connected", dot: "bg-emerald-500", cls: "text-emerald-800" };
}

export default async function DashboardPage() {
  const session = await auth.api.getSession({ headers: await headers() }).catch(() => null);
  if (!session?.user) redirect("/sign-in");

  let frames: Frame[] = [];
  try {
    frames = await api<Frame[]>("/api/frames");
  } catch {
    frames = [];
  }

  return (
    <div>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-3xl">Your frames</h1>
          <p className="mt-1 text-sm text-ink-soft">
            Hi {session.user.name || session.user.email}. Manage every frame you own here.
          </p>
        </div>
        <Link href="/dashboard/frames/new" className="btn-primary">+ New frame</Link>
      </div>

      {frames.length === 0 ? (
        <div className="card mt-8">
          <p className="text-sm text-ink-soft">
            You don&apos;t have any frames yet. Create one to start the setup wizard.
          </p>
          <Link href="/dashboard/frames/new" className="btn-primary mt-4">Create your first frame</Link>
        </div>
      ) : (
        <ul className="mt-8 grid gap-4 md:grid-cols-2">
          {frames.map((frame) => {
            const batt = batteryBadge(frame.last_battery_percent);
            const conn = connectionBadge(frame);
            return (
              <li key={frame.id} className="card flex flex-col gap-3">
                <div className="flex items-baseline justify-between gap-3">
                  <div>
                    <h2 className="font-display text-xl">{frame.display_name}</h2>
                    <p className="text-xs text-ink-soft">/{frame.name}</p>
                  </div>
                  <span className={`rounded-full px-2 py-0.5 text-xs ${batt.cls}`}>{batt.label}</span>
                </div>
                <div className="text-xs text-ink-soft">
                  Last seen {relativeTime(frame.last_seen_at)}
                  <span className={`ml-2 inline-flex items-center gap-1 ${conn.cls}`}>
                    <span className={`inline-block h-2 w-2 rounded-full ${conn.dot}`} /> {conn.label}
                  </span>
                  {frame.next_expected_poll_at && (
                    <span className="block">Next expected {relativeFuture(frame.next_expected_poll_at)}</span>
                  )}
                </div>
                <div className="mt-2 flex flex-wrap gap-2">
                  <Link className="btn-secondary" href={`/dashboard/frames/${frame.id}`}>Manage</Link>
                  <Link className="btn-secondary" href={`/dashboard/frames/${frame.id}/setup`}>SD setup</Link>
                  <Link className="btn-secondary" href={`/dashboard/frames/${frame.id}/schedule`}>Schedule</Link>
                  <Link className="btn-secondary" href={`/dashboard/frames/${frame.id}/inbox`}>Inbox</Link>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
