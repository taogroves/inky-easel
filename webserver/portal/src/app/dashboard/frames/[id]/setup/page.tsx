import Link from "next/link";
import { notFound } from "next/navigation";

import SetupWizard from "@/components/SetupWizard";
import { ApiError, api, type FrameWithSecret } from "@/lib/api";

export default async function SetupPage(props: { params: Promise<{ id: string }> }) {
  const { id } = await props.params;
  let frame: FrameWithSecret;
  try {
    frame = await api<FrameWithSecret>(`/api/frames/${id}`);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }

  return (
    <div>
      <Link href={`/dashboard/frames/${frame.id}`} className="text-xs uppercase tracking-wide text-ink-soft hover:underline">
        &larr; Back to frame
      </Link>
      <h1 className="mt-3 font-display text-3xl">SD card setup</h1>
      <p className="mt-2 max-w-prose text-sm text-ink-soft">
        Follow these steps to prepare a microSD card for <strong>{frame.display_name}</strong>.
        You can re-run this any time you want to change Wi-Fi details or replace the card.
      </p>
      <SetupWizard frame={frame} />
    </div>
  );
}
