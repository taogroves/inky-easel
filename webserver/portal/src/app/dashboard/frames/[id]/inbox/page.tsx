import Link from "next/link";
import { notFound } from "next/navigation";

import InboxList from "@/components/InboxList";
import InboxSettingsForm from "@/components/InboxSettingsForm";
import { ApiError, api, type FrameWithSecret, type InboxItem } from "@/lib/api";

export default async function InboxPage(props: { params: Promise<{ id: string }> }) {
  const { id } = await props.params;
  try {
    const [frame, items] = await Promise.all([
      api<FrameWithSecret>(`/api/frames/${id}`),
      api<InboxItem[]>(`/api/inbox/frames/${id}?include_archived=true`),
    ]);
    return (
      <div>
        <Link href={`/dashboard/frames/${frame.id}`} className="text-xs uppercase tracking-wide text-ink-soft hover:underline">
          &larr; Back to frame
        </Link>
        <h1 className="mt-3 font-display text-3xl">{frame.display_name} - inbox</h1>
        <p className="mt-2 max-w-prose text-sm text-ink-soft">
          New messages appear here. The "inbox" schedule item shows the oldest unread
          one, then marks it as displayed.
        </p>
        <InboxSettingsForm frame={frame} />
        <InboxList frameId={frame.id} items={items} timezone={frame.timezone} />
      </div>
    );
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }
}
