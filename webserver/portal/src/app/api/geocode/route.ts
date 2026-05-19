import { NextRequest, NextResponse } from "next/server";

/**
 * Proxies address search to OpenStreetMap Nominatim.
 * https://operations.osmfoundation.org/policies/nominatim/
 */
export async function GET(req: NextRequest) {
  const q = req.nextUrl.searchParams.get("q")?.trim();
  if (!q || q.length < 2) {
    return NextResponse.json({ error: "Query too short" }, { status: 400 });
  }

  const url = new URL("https://nominatim.openstreetmap.org/search");
  url.searchParams.set("q", q);
  url.searchParams.set("format", "json");
  url.searchParams.set("limit", "6");
  url.searchParams.set("addressdetails", "0");

  const userAgent =
    process.env.NOMINATIM_USER_AGENT?.trim() ||
    "InkyEaselPortal/1.0 (+https://github.com/inky-easel/inky-easel)";

  const res = await fetch(url.toString(), {
    headers: {
      Accept: "application/json",
      "User-Agent": userAgent,
    },
    next: { revalidate: 3600 },
  });

  if (!res.ok) {
    return NextResponse.json({ error: "Geocoding service unavailable" }, { status: 502 });
  }

  const data = (await res.json()) as Array<{ lat: string; lon: string; display_name: string }>;

  const results = data.map((r) => ({
    lat: Number(r.lat),
    lng: Number(r.lon),
    label: r.display_name,
  }));

  return NextResponse.json({ results });
}
