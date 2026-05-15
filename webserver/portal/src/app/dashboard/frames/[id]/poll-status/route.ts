import { NextResponse } from "next/server";

import { api, type FrameWithSecret } from "@/lib/api";

export const dynamic = "force-dynamic";

export async function GET(_req: Request, props: { params: Promise<{ id: string }> }) {
  const { id } = await props.params;
  try {
    const frame = await api<FrameWithSecret>(`/api/frames/${id}`);
    return NextResponse.json({ last_seen_at: frame.last_seen_at });
  } catch {
    return NextResponse.json({ last_seen_at: null }, { status: 200 });
  }
}
