import Link from "next/link";
import { headers } from "next/headers";
import { redirect } from "next/navigation";

import { activateFirmwareReleaseAction, createFirmwareReleaseAction } from "@/lib/actions";
import {
  grantAdminDashboardAccess,
  hasAdminDashboardAccess,
  isAdminPasswordConfigured,
  verifyAdminPassword,
} from "@/lib/admin-auth";
import { auth } from "@/lib/auth";
import { api, type FirmwareAdmin, type Frame } from "@/lib/api";
import { getDeveloperMode } from "@/lib/developer-mode";
import { formatDateTime, parseApiDate } from "@/lib/time";

function relativeTime(iso: string | null): string {
  if (!iso) return "never";
  const mins = Math.floor((Date.now() - parseApiDate(iso).getTime()) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

function firmwareState(frame: Frame, activeVersion: string | null): { label: string; cls: string } {
  if (!frame.firmware_version) return { label: "unknown", cls: "bg-amber-100 text-amber-800" };
  if (activeVersion && frame.firmware_version !== activeVersion) {
    return { label: `needs ${activeVersion}`, cls: "bg-red-100 text-red-800" };
  }
  return { label: "current", cls: "bg-emerald-100 text-emerald-800" };
}

function AdminPasswordForm({ error }: { error: boolean }) {
  return (
    <div>
      <Link href="/dashboard" className="text-xs uppercase tracking-wide text-ink-soft hover:underline">
        &larr; Back to dashboard
      </Link>
      <section className="card mt-8 max-w-md">
        <h1 className="font-display text-2xl">Admin access</h1>
        <p className="mt-2 text-sm text-ink-soft">Enter the global sudo password to continue.</p>
        <form action={adminLoginAction} className="mt-5 space-y-4">
          <div>
            <label className="label" htmlFor="admin_password">Sudo password</label>
            <input className="input" id="admin_password" name="admin_password" type="password" autoComplete="current-password" required />
          </div>
          {error ? <p className="text-sm text-red-800">That password did not match.</p> : null}
          <button className="btn-primary" type="submit">Unlock admin</button>
        </form>
      </section>
    </div>
  );
}

async function adminLoginAction(formData: FormData) {
  "use server";
  const password = String(formData.get("admin_password") ?? "");
  if (!verifyAdminPassword(password)) {
    redirect("/dashboard/admin?error=1");
  }
  await grantAdminDashboardAccess();
  redirect("/dashboard/admin");
}

export default async function AdminPage(props: { searchParams: Promise<{ error?: string }> }) {
  async function createRelease(formData: FormData) {
    "use server";
    await createFirmwareReleaseAction(formData);
  }

  async function activateRelease(releaseId: string) {
    "use server";
    await activateFirmwareReleaseAction(releaseId);
  }

  const { error } = await props.searchParams;
  const session = await auth.api.getSession({ headers: await headers() }).catch(() => null);
  if (!session?.user) redirect("/sign-in");
  if (!(await getDeveloperMode(session.user.id))) redirect("/dashboard");

  if (!isAdminPasswordConfigured()) {
    return (
      <div>
        <Link href="/dashboard" className="text-xs uppercase tracking-wide text-ink-soft hover:underline">
          &larr; Back to dashboard
        </Link>
        <section className="card mt-8 max-w-xl">
          <h1 className="font-display text-2xl">Admin access is not configured</h1>
          <p className="mt-2 text-sm text-ink-soft">
            Set ADMIN_DASHBOARD_PASSWORD in the portal environment to enable this dashboard.
          </p>
        </section>
      </div>
    );
  }
  if (!(await hasAdminDashboardAccess())) {
    return <AdminPasswordForm error={error === "1"} />;
  }

  let data: FirmwareAdmin = { frames: [], releases: [], local_changes: [] };
  try {
    data = await api<FirmwareAdmin>("/api/firmware/admin");
  } catch {
    data = { frames: [], releases: [], local_changes: [] };
  }

  const activeRelease = data.releases.find((release) => release.active) ?? null;
  const connected = data.frames.filter((frame) => frame.connection_status === "connected").length;
  const stale = data.frames.filter((frame) => activeRelease && frame.firmware_version !== activeRelease.version).length;
  const lowBattery = data.frames.filter((frame) => (frame.last_battery_percent ?? 100) < 20).length;

  return (
    <div>
      <Link href="/dashboard" className="text-xs uppercase tracking-wide text-ink-soft hover:underline">
        &larr; Back to dashboard
      </Link>
      <div className="mt-3 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl">Admin</h1>
          <p className="mt-1 text-sm text-ink-soft">Fleet check-ins, firmware versions, and release snapshots.</p>
        </div>
        <Link href="/dashboard/frames/new" className="btn-secondary">New frame</Link>
      </div>

      <section className="mt-8 grid gap-4 md:grid-cols-4">
        <div className="card"><p className="text-xs uppercase tracking-wide text-ink-soft">Frames</p><p className="mt-2 text-2xl font-semibold">{data.frames.length}</p></div>
        <div className="card"><p className="text-xs uppercase tracking-wide text-ink-soft">Connected</p><p className="mt-2 text-2xl font-semibold">{connected}</p></div>
        <div className="card"><p className="text-xs uppercase tracking-wide text-ink-soft">Outdated</p><p className="mt-2 text-2xl font-semibold">{stale}</p></div>
        <div className="card"><p className="text-xs uppercase tracking-wide text-ink-soft">Low battery</p><p className="mt-2 text-2xl font-semibold">{lowBattery}</p></div>
      </section>

      <section className="mt-8 grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        <div className="card overflow-x-auto">
          <h2 className="font-display text-xl">Frame fleet</h2>
          <table className="mt-4 w-full min-w-[760px] text-left text-sm">
            <thead className="border-b border-ink/10 text-xs uppercase tracking-wide text-ink-soft">
              <tr>
                <th className="py-2 pr-4">Frame</th>
                <th className="py-2 pr-4">Check-in</th>
                <th className="py-2 pr-4">Battery</th>
                <th className="py-2 pr-4">Firmware</th>
                <th className="py-2 pr-4">State</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ink/10">
              {data.frames.map((frame) => {
                const state = firmwareState(frame, activeRelease?.version ?? null);
                return (
                  <tr key={frame.id}>
                    <td className="py-3 pr-4">
                      <Link href={`/dashboard/frames/${frame.id}`} className="font-medium hover:underline">{frame.display_name}</Link>
                      <div className="text-xs text-ink-soft">/{frame.name}</div>
                    </td>
                    <td className="py-3 pr-4">{relativeTime(frame.last_seen_at)}</td>
                    <td className="py-3 pr-4">{frame.last_battery_percent != null ? `${frame.last_battery_percent}%` : "no data"}</td>
                    <td className="py-3 pr-4">
                      <code className="rounded bg-ink/5 px-1">{frame.firmware_version ?? "unknown"}</code>
                      {frame.last_firmware_status ? <div className="text-xs text-ink-soft">{frame.last_firmware_status}</div> : null}
                    </td>
                    <td className="py-3 pr-4"><span className={`rounded-full px-2 py-1 text-xs ${state.cls}`}>{state.label}</span></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <div className="card">
          <h2 className="font-display text-xl">Publish firmware</h2>
          <p className="mt-2 text-sm text-ink-soft">
            Creates an immutable backup snapshot from the server&apos;s mounted frame-firmware files.
          </p>
          <div className="mt-4 rounded-md border border-ink/10 bg-ink/5 p-3">
            <div className="flex items-center justify-between gap-3">
              <h3 className="text-sm font-semibold">Local changes</h3>
              <span className={`rounded-full px-2 py-0.5 text-xs ${data.local_changes.length ? "bg-amber-100 text-amber-800" : "bg-emerald-100 text-emerald-800"}`}>
                {data.local_changes.length ? `${data.local_changes.length} changed` : "in sync"}
              </span>
            </div>
            {data.local_changes.length ? (
              <ul className="mt-3 space-y-2 text-xs">
                {data.local_changes.slice(0, 8).map((change) => (
                  <li key={change.path} className="flex items-center justify-between gap-3">
                    <span className="font-mono">{change.path}</span>
                    <span className="rounded bg-white px-2 py-0.5 text-ink-soft">{change.status}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-2 text-xs text-ink-soft">Server files match the active release.</p>
            )}
            {data.local_changes.length > 8 ? (
              <p className="mt-2 text-xs text-ink-soft">Plus {data.local_changes.length - 8} more files.</p>
            ) : null}
          </div>
          <form action={createRelease} className="mt-4 space-y-3">
            <div>
              <label className="label" htmlFor="version">Version</label>
              <input className="input" id="version" name="version" placeholder="0.2.0" required />
            </div>
            <div>
              <label className="label" htmlFor="notes">Notes</label>
              <textarea className="input min-h-24" id="notes" name="notes" />
            </div>
            <input name="activate" type="hidden" value="off" />
            <label className="flex items-center gap-2 text-sm">
              <input name="activate" type="checkbox" defaultChecked value="on" />
              Activate immediately
            </label>
            <button className="btn-primary" type="submit">Create release</button>
          </form>
        </div>
      </section>

      <section className="mt-8 card">
        <h2 className="font-display text-xl">Firmware releases</h2>
        <div className="mt-4 grid gap-3">
          {data.releases.map((release) => (
            <div key={release.id} className="rounded-md border border-ink/10 p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <code className="rounded bg-ink/5 px-1">{release.version}</code>
                    {release.active ? <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs text-emerald-800">active</span> : null}
                  </div>
                  <p className="mt-1 text-xs text-ink-soft">
                    {formatDateTime(release.created_at, null)} &middot; {release.files.length} files &middot; {release.manifest_hash.slice(0, 12)}
                  </p>
                </div>
                {!release.active ? (
                  <form action={activateRelease.bind(null, release.id)}>
                    <button className="btn-secondary" type="submit">Activate</button>
                  </form>
                ) : null}
              </div>
              {release.notes ? <p className="mt-3 text-sm text-ink-soft">{release.notes}</p> : null}
            </div>
          ))}
          {data.releases.length === 0 ? <p className="text-sm text-ink-soft">No firmware releases yet.</p> : null}
        </div>
      </section>
    </div>
  );
}
