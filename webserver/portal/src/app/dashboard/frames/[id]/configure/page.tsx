import Link from "next/link";
import { notFound } from "next/navigation";

import FrameConfigureClient from "@/components/FrameConfigureClient";
import { ApiError, api, type FrameConfigurationSession, type FrameWithSecret } from "@/lib/api";

export default async function FrameConfigurePage(props: { params: Promise<{ id: string }> }) {
  const { id } = await props.params;
  let frame: FrameWithSecret;
  let session: FrameConfigurationSession;
  try {
    frame = await api<FrameWithSecret>(`/api/frames/${id}`);
    session = await api<FrameConfigurationSession>(`/api/frames/${id}/configuration`);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }

  return (
    <div>
      <Link href={`/dashboard/frames/${frame.id}`} className="text-xs uppercase tracking-wide text-ink-soft hover:underline">
        &larr; Back to frame
      </Link>
      <div className="mt-3">
        <h1 className="font-display text-3xl">Configure {frame.display_name}</h1>
        <p className="mt-1 text-sm text-ink-soft">
          Update Wi-Fi networks, server address, and firmware without rebuilding the SD card.
        </p>
      </div>
      <FrameConfigureClient frameId={frame.id} initialSession={session} />
    </div>
  );
}
