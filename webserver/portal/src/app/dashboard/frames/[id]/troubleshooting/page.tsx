import Link from "next/link";
import { notFound } from "next/navigation";

import TroubleshootingGuide from "@/components/TroubleshootingGuide";
import { ApiError, api, type FrameWithSecret } from "@/lib/api";

export default async function TroubleshootingPage(props: { params: Promise<{ id: string }> }) {
  const { id } = await props.params;
  try {
    const frame = await api<FrameWithSecret>(`/api/frames/${id}`);

    return (
      <div>
        <Link href={`/dashboard/frames/${frame.id}`} className="text-xs uppercase tracking-wide text-ink-soft hover:underline">
          &larr; Back to frame
        </Link>
        <h1 className="mt-3 font-display text-3xl">{frame.display_name} — troubleshooting</h1>
        <p className="mt-2 max-w-prose text-sm text-ink-soft">
          Expand a section below for help with setup, connection status, Wi-Fi, schedules, and on-frame error
          messages. Links at the bottom point to the full markdown guides.
        </p>
        <TroubleshootingGuide />
      </div>
    );
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }
}
