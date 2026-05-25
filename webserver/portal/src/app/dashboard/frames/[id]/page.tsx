import Link from "next/link";
import { headers } from "next/headers";
import { notFound } from "next/navigation";

import EditFrameForm from "@/components/EditFrameForm";
import DangerZone from "@/components/DangerZone";
import { auth } from "@/lib/auth";
import { ApiError, api, type FrameWithSecret } from "@/lib/api";
import { getDeveloperMode } from "@/lib/developer-mode";
import { formatDateTime } from "@/lib/time";

function statusLabel(status: FrameWithSecret["connection_status"]): string {
  if (status === "awaiting_first_check_in") return "awaiting first check-in";
  return status;
}

export default async function FrameDetailPage(props: { params: Promise<{ id: string }> }) {
  const { id } = await props.params;
  const session = await auth.api.getSession({ headers: await headers() }).catch(() => null);
  const developerMode = session?.user ? await getDeveloperMode(session.user.id) : false;
  let frame: FrameWithSecret;
  try {
    frame = await api<FrameWithSecret>(`/api/frames/${id}`);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }

  return (
    <div>
      <Link href="/dashboard" className="text-xs uppercase tracking-wide text-ink-soft hover:underline">
        &larr; Back to dashboard
      </Link>
      <div className="mt-3 flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <h1 className="font-display text-3xl">{frame.display_name}</h1>
          <p className="text-sm text-ink-soft">Handle <code className="rounded bg-ink/5 px-1">{frame.name}</code></p>
        </div>
        <div className="flex gap-2">
          <Link href={`/dashboard/frames/${frame.id}/configure`} className="btn-secondary">Configure</Link>
          <Link href={`/dashboard/frames/${frame.id}/setup`} className="btn-secondary">SD setup</Link>
          <Link href={`/dashboard/frames/${frame.id}/inbox`} className="btn-secondary">Inbox</Link>
          <Link href={`/dashboard/frames/${frame.id}/schedule`} className="btn-primary">Schedule</Link>
        </div>
      </div>

      <section className="mt-8 grid gap-6 md:grid-cols-2">
        <div className="card">
          <h2 className="font-display text-xl">Status</h2>
          <dl className="mt-3 space-y-2 text-sm">
            <div className="flex justify-between"><dt className="text-ink-soft">Connection</dt><dd className={frame.connection_status === "disconnected" ? "text-red-800" : ""}>{statusLabel(frame.connection_status)}</dd></div>
            <div className="flex justify-between"><dt className="text-ink-soft">Last check-in</dt><dd>{formatDateTime(frame.last_seen_at, frame.timezone)}</dd></div>
            <div className="flex justify-between"><dt className="text-ink-soft">Next expected poll</dt><dd>{formatDateTime(frame.next_expected_poll_at, frame.timezone)}</dd></div>
            <div className="flex justify-between"><dt className="text-ink-soft">Disconnects after</dt><dd>{formatDateTime(frame.disconnected_after, frame.timezone)}</dd></div>
            <div className="flex justify-between"><dt className="text-ink-soft">Battery</dt><dd>{frame.last_battery_percent != null ? `${frame.last_battery_percent}%` : "no data"}</dd></div>
            <div className="flex justify-between"><dt className="text-ink-soft">Voltage</dt><dd>{frame.last_battery_voltage != null ? `${frame.last_battery_voltage.toFixed(2)} V` : "—"}</dd></div>
            {developerMode ? (
              <>
                <div className="flex justify-between"><dt className="text-ink-soft">Firmware</dt><dd>{frame.firmware_version ?? "unknown"}</dd></div>
                <div className="flex justify-between"><dt className="text-ink-soft">Target firmware</dt><dd>{frame.target_firmware_version ?? "—"}</dd></div>
                <div className="flex justify-between"><dt className="text-ink-soft">Firmware status</dt><dd>{frame.last_firmware_status ?? "—"}</dd></div>
              </>
            ) : null}
            <div className="flex justify-between"><dt className="text-ink-soft">Display</dt><dd>{frame.display_type}</dd></div>
            <div className="flex justify-between"><dt className="text-ink-soft">Inbox</dt><dd>{frame.inbox_mode}</dd></div>
            <div className="flex justify-between"><dt className="text-ink-soft">Location</dt><dd>{frame.latitude != null && frame.longitude != null ? `${frame.latitude.toFixed(2)}, ${frame.longitude.toFixed(2)}` : "—"}</dd></div>
            <div className="flex justify-between"><dt className="text-ink-soft">Timezone</dt><dd>{frame.timezone ?? "—"}</dd></div>
            {developerMode ? (
              <>
                <div className="flex justify-between gap-4 border-t border-ink/10 pt-2">
                  <dt className="text-ink-soft">Storage</dt>
                  <dd className="text-right">{frame.image_delivery.storage}</dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-ink-soft">Image format</dt>
                  <dd className="text-right">{frame.image_delivery.format}</dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-ink-soft">Compression</dt>
                  <dd className="text-right">{frame.image_delivery.compression}</dd>
                </div>
              </>
            ) : null}
          </dl>
          <div className="mt-5 flex justify-end border-t border-ink/10 pt-4">
            <Link href={`/dashboard/frames/${frame.id}/troubleshooting`} className="btn-primary">
              Troubleshooting
            </Link>
          </div>
        </div>

        <div className="card">
          <h2 className="font-display text-xl">Edit details</h2>
          <EditFrameForm frame={frame} />
        </div>
      </section>

      <DangerZone frameId={frame.id} />
    </div>
  );
}
