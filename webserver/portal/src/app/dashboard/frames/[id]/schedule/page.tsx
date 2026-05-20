import Link from "next/link";
import { notFound } from "next/navigation";

import ScheduleEditor from "@/components/ScheduleEditor";
import { ApiError, api, type FrameWithSecret, type Plugin, type ScheduleItem } from "@/lib/api";

export default async function SchedulePage(props: { params: Promise<{ id: string }> }) {
  const { id } = await props.params;
  try {
    const [frame, schedule, plugins] = await Promise.all([
      api<FrameWithSecret>(`/api/frames/${id}`),
      api<ScheduleItem[]>(`/api/frames/${id}/schedule`),
      api<Plugin[]>("/api/plugins"),
    ]);

    return (
      <div>
        <Link href={`/dashboard/frames/${frame.id}`} className="text-xs uppercase tracking-wide text-ink-soft hover:underline">
          &larr; Back to frame
        </Link>
        <h1 className="mt-3 font-display text-3xl">{frame.display_name} - schedule</h1>
        <p className="mt-2 max-w-prose text-sm text-ink-soft">
          Use a simple top-to-bottom loop, or switch to a 24-hour day calendar where
          each item appears at a local time.
        </p>
        <ScheduleEditor frameId={frame.id} initialMode={frame.schedule_mode} initial={schedule} plugins={plugins} />
      </div>
    );
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }
}
