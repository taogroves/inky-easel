import { NextResponse } from "next/server";

import { ApiError, api, type FrameConfigurationSession } from "@/lib/api";

export const dynamic = "force-dynamic";

export async function GET(_req: Request, props: { params: Promise<{ id: string }> }) {
  const { id } = await props.params;
  try {
    const session = await api<FrameConfigurationSession>(`/api/frames/${id}/configuration`);
    return NextResponse.json(session);
  } catch (e) {
    const status = e instanceof ApiError ? e.status : 500;
    return NextResponse.json({ error: (e as Error).message }, { status });
  }
}

export async function POST(req: Request, props: { params: Promise<{ id: string }> }) {
  const { id } = await props.params;
  const body = await req.json().catch(() => ({}));
  const action = String(body.action ?? "");
  const path =
    action === "start"
      ? `/api/frames/${id}/configuration/start`
      : action === "save"
        ? `/api/frames/${id}/configuration/save`
        : action === "cancel"
          ? `/api/frames/${id}/configuration/cancel`
          : null;
  if (!path) {
    return NextResponse.json({ error: "Unknown configuration action" }, { status: 400 });
  }
  try {
    const session = await api<FrameConfigurationSession>(path, {
      method: "POST",
      body: JSON.stringify(action === "save" ? body.payload : {}),
    });
    return NextResponse.json(session);
  } catch (e) {
    const status = e instanceof ApiError ? e.status : 500;
    return NextResponse.json({ error: (e as Error).message }, { status });
  }
}
