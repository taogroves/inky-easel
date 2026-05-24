/**
 * Thin client for the FastAPI backend. Used exclusively on the server side
 * (server components and server actions). It attaches the shared service
 * secret and the current user's id so the API can authorise the request.
 */

import { headers } from "next/headers";

import { auth } from "@/lib/auth";

const API_BASE = process.env.API_BASE_URL ?? "http://api:8000";
const SERVICE_SECRET = process.env.SERVICE_SECRET ?? "dev-service-secret";

export class ApiError extends Error {
  constructor(public status: number, message: string, public details?: unknown) {
    super(message);
  }
}

async function userId(): Promise<string> {
  const session = await auth.api.getSession({ headers: await headers() });
  if (!session?.user) {
    throw new ApiError(401, "Not signed in");
  }
  return session.user.id;
}

type FetchOpts = RequestInit & { skipAuth?: boolean };

export async function api<T>(path: string, opts: FetchOpts = {}): Promise<T> {
  const headerBag: Record<string, string> = {
    "Content-Type": "application/json",
    "X-Service-Auth": SERVICE_SECRET,
  };
  if (!opts.skipAuth) {
    headerBag["X-User-Id"] = await userId();
  }
  const url = `${API_BASE}${path}`;
  const resp = await fetch(url, {
    ...opts,
    headers: { ...headerBag, ...(opts.headers as Record<string, string> | undefined) },
    cache: "no-store",
  });

  if (!resp.ok) {
    let body: unknown;
    try {
      body = await resp.json();
    } catch {
      body = await resp.text().catch(() => "");
    }
    const message = typeof body === "object" && body && "detail" in body
      ? String((body as { detail: unknown }).detail)
      : `API ${resp.status}`;
    throw new ApiError(resp.status, message, body);
  }

  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}

export async function apiBinary(path: string, opts: FetchOpts = {}): Promise<{ data: ArrayBuffer; mime: string }> {
  const headerBag: Record<string, string> = {
    "X-Service-Auth": SERVICE_SECRET,
  };
  if (!opts.skipAuth) {
    headerBag["X-User-Id"] = await userId();
  }
  const url = `${API_BASE}${path}`;
  const resp = await fetch(url, {
    ...opts,
    headers: { ...headerBag, ...(opts.headers as Record<string, string> | undefined) },
    cache: "no-store",
  });

  if (!resp.ok) {
    let body: unknown;
    try {
      body = await resp.json();
    } catch {
      body = await resp.text().catch(() => "");
    }
    const message = typeof body === "object" && body && "detail" in body
      ? String((body as { detail: unknown }).detail)
      : `API ${resp.status}`;
    throw new ApiError(resp.status, message, body);
  }

  return {
    data: await resp.arrayBuffer(),
    mime: resp.headers.get("content-type") ?? "application/octet-stream",
  };
}

export const apiBase = API_BASE;
export const apiServiceSecret = SERVICE_SECRET;

// ---------- Types mirrored from FastAPI ----------

export type ImageDelivery = {
  storage: string;
  format: string;
  compression: string;
};

export type Frame = {
  id: string;
  name: string;
  display_name: string;
  latitude: number | null;
  longitude: number | null;
  timezone: string | null;
  display_type: string;
  schedule_mode: "relative" | "calendar";
  inbox_mode: "open" | "private" | "closed";
  inbox_password: string | null;
  inbox_repeat_enabled: boolean;
  inbox_delete_after_displays: number | null;
  last_seen_at: string | null;
  next_expected_poll_at: string | null;
  disconnected_after: string | null;
  connection_status: "connected" | "disconnected" | "awaiting_first_check_in";
  last_battery_percent: number | null;
  last_battery_voltage: number | null;
  last_has_sd_card: boolean | null;
  firmware_version: string | null;
  target_firmware_version: string | null;
  last_firmware_status: string | null;
  last_firmware_update_at: string | null;
  image_delivery: ImageDelivery;
  created_at: string;
};

export type FrameWithSecret = Frame & { secret: string };

export type ScheduleItem = {
  id: string;
  position: number;
  item_type: "inbox" | "weather" | "xkcd" | "rss" | "reddit" | "bbc" | "plugin" | "static";
  item_ref: string | null;
  config: Record<string, unknown> | null;
  sleep_minutes: number;
  start_minute: number | null;
};

export type Plugin = {
  id: string;
  name: string;
  description: string | null;
  code: string;
  created_at: string;
  updated_at: string;
};

export type InboxItem = {
  id: string;
  kind: "text" | "image" | "link" | "drawing";
  text_body: string | null;
  image_mime: string | null;
  sender_label: string | null;
  created_at: string;
  displayed_at: string | null;
  display_count: number;
  archived: boolean;
};

export type SetupBundle = {
  frame: FrameWithSecret;
  files: Record<string, string>;
  server_url: string;
};

export type FirmwareFile = {
  path: string;
  sha256: string;
  size_bytes: number;
};

export type FirmwareRelease = {
  id: string;
  version: string;
  notes: string | null;
  active: boolean;
  manifest_hash: string;
  created_at: string;
  files: FirmwareFile[];
};

export type FirmwareLocalChange = {
  path: string;
  status: "added" | "modified" | "removed";
  local_sha256: string | null;
  active_sha256: string | null;
  local_size_bytes: number | null;
  active_size_bytes: number | null;
};

export type FirmwareAdmin = {
  frames: Frame[];
  releases: FirmwareRelease[];
  local_changes: FirmwareLocalChange[];
};

export type WifiCredential = {
  ssid: string;
  password: string;
};

export type FrameConfigurationReport = {
  status: "available" | "applied" | "error";
  message: string | null;
  wifi_credentials: WifiCredential[];
  active_wifi_index: number;
  server_url: string;
  firmware_version: string | null;
};

export type FrameConfigurationDesired = {
  wifi_credentials: WifiCredential[];
  active_wifi_index: number;
  server_url: string;
};

export type FrameConfigurationSession = {
  state: "idle" | "pending" | "entering" | "connected" | "applying" | "applied" | "error" | "cancelled";
  observed: FrameConfigurationReport | null;
  message: string | null;
  updated_at: string;
  releases: FirmwareRelease[];
};
