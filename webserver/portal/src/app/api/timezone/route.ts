import { NextRequest, NextResponse } from "next/server";

import { api } from "@/lib/api";

export async function GET(req: NextRequest) {
  const latitude = Number(req.nextUrl.searchParams.get("latitude"));
  const longitude = Number(req.nextUrl.searchParams.get("longitude"));

  if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) {
    return NextResponse.json({ error: "Invalid coordinates" }, { status: 400 });
  }

  try {
    const data = await api<{ timezone: string }>(
      `/api/frames/timezone?latitude=${encodeURIComponent(latitude)}&longitude=${encodeURIComponent(longitude)}`,
    );
    return NextResponse.json(data);
  } catch {
    return NextResponse.json({ error: "Timezone service unavailable" }, { status: 502 });
  }
}
