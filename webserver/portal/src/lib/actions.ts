"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { api, ApiError, type FrameWithSecret, type InboxItem, type Plugin, type ScheduleItem, type SetupBundle } from "@/lib/api";

export type ActionResult<T = undefined> = { ok: true; data: T } | { ok: false; error: string };

function fail(e: unknown): ActionResult<never> {
  if (e instanceof ApiError) return { ok: false, error: e.message };
  return { ok: false, error: (e as Error).message ?? "Unknown error" };
}

function nullableString(value: FormDataEntryValue | null): string | null {
  const text = String(value ?? "").trim();
  return text || null;
}

function nullableNumber(value: FormDataEntryValue | null): number | null {
  const text = String(value ?? "").trim();
  return text ? Number(text) : null;
}

// ---------- Frames ----------

export async function createFrameAction(formData: FormData): Promise<void> {
  const payload = {
    name: String(formData.get("name") ?? "").trim().toLowerCase(),
    display_name: String(formData.get("display_name") ?? "").trim(),
    latitude: nullableNumber(formData.get("latitude")),
    longitude: nullableNumber(formData.get("longitude")),
    timezone: nullableString(formData.get("timezone")),
    display_type: String(formData.get("display_type") ?? "inky_frame_7_spectra"),
  };

  const frame = await api<FrameWithSecret>("/api/frames", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  revalidatePath("/dashboard");
  redirect(`/dashboard/frames/${frame.id}/setup`);
}

export async function updateFrameAction(frameId: string, formData: FormData): Promise<ActionResult<FrameWithSecret>> {
  try {
    const payload: Record<string, unknown> = {};
    const dn = formData.get("display_name");
    if (dn) payload.display_name = String(dn);
    if (formData.has("latitude")) payload.latitude = nullableNumber(formData.get("latitude"));
    if (formData.has("longitude")) payload.longitude = nullableNumber(formData.get("longitude"));
    if (formData.has("timezone")) payload.timezone = nullableString(formData.get("timezone"));
    const dt = formData.get("display_type");
    if (dt) payload.display_type = String(dt);
    if (formData.has("inbox_mode")) payload.inbox_mode = String(formData.get("inbox_mode") ?? "open");
    if (formData.has("inbox_password")) payload.inbox_password = nullableString(formData.get("inbox_password"));
    if (formData.has("inbox_repeat_enabled")) {
      payload.inbox_repeat_enabled = formData.getAll("inbox_repeat_enabled").includes("on");
    }
    if (formData.has("inbox_delete_after_displays")) {
      payload.inbox_delete_after_displays = nullableNumber(formData.get("inbox_delete_after_displays"));
    }
    const frame = await api<FrameWithSecret>(`/api/frames/${frameId}`, { method: "PATCH", body: JSON.stringify(payload) });
    revalidatePath(`/dashboard/frames/${frameId}`);
    revalidatePath("/dashboard");
    return { ok: true, data: frame };
  } catch (e) {
    return fail(e);
  }
}

export async function deleteFrameAction(frameId: string): Promise<void> {
  await api(`/api/frames/${frameId}`, { method: "DELETE" });
  revalidatePath("/dashboard");
  redirect("/dashboard");
}

export async function rotateFrameSecretAction(frameId: string): Promise<ActionResult<FrameWithSecret>> {
  try {
    const frame = await api<FrameWithSecret>(`/api/frames/${frameId}/rotate-secret`, { method: "POST" });
    revalidatePath(`/dashboard/frames/${frameId}/setup`);
    return { ok: true, data: frame };
  } catch (e) {
    return fail(e);
  }
}

// ---------- Setup bundle ----------

export async function buildBundleAction(
  frameId: string,
  wifi_ssid: string,
  wifi_password: string,
  server_url?: string,
): Promise<ActionResult<SetupBundle>> {
  try {
    const payload = {
      wifi_ssid,
      wifi_password,
      ...(server_url?.trim() ? { server_url: server_url.trim() } : {}),
    };
    const bundle = await api<SetupBundle>(`/api/setup/${frameId}/bundle`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
    return { ok: true, data: bundle };
  } catch (e) {
    return fail(e);
  }
}

// ---------- Schedule ----------

export async function saveScheduleAction(
  frameId: string,
  scheduleMode: "relative" | "calendar",
  items: Array<Omit<ScheduleItem, "id" | "position">>,
): Promise<ActionResult<ScheduleItem[]>> {
  try {
    const saved = await api<ScheduleItem[]>(`/api/frames/${frameId}/schedule`, {
      method: "PUT",
      body: JSON.stringify({ schedule_mode: scheduleMode, items }),
    });
    revalidatePath(`/dashboard/frames/${frameId}/schedule`);
    return { ok: true, data: saved };
  } catch (e) {
    return fail(e);
  }
}

// ---------- Inbox ----------

export async function archiveInboxAction(frameId: string, itemId: string): Promise<ActionResult> {
  try {
    await api(`/api/inbox/${itemId}/archive`, { method: "POST" });
    revalidatePath(`/dashboard/frames/${frameId}/inbox`);
    return { ok: true, data: undefined };
  } catch (e) {
    return fail(e);
  }
}

export async function unarchiveInboxAction(frameId: string, itemId: string): Promise<ActionResult> {
  try {
    await api(`/api/inbox/${itemId}/unarchive`, { method: "POST" });
    revalidatePath(`/dashboard/frames/${frameId}/inbox`);
    return { ok: true, data: undefined };
  } catch (e) {
    return fail(e);
  }
}

export async function deleteInboxAction(frameId: string, itemId: string): Promise<ActionResult> {
  try {
    await api(`/api/inbox/${itemId}`, { method: "DELETE" });
    revalidatePath(`/dashboard/frames/${frameId}/inbox`);
    return { ok: true, data: undefined };
  } catch (e) {
    return fail(e);
  }
}

// ---------- Send ----------

export async function sendMessageAction(payload: {
  recipient_frame_name: string;
  kind: "text" | "image" | "link" | "drawing";
  text_body?: string;
  image_base64?: string;
  image_mime?: string;
  sender_label?: string;
  inbox_password?: string;
}): Promise<ActionResult<InboxItem>> {
  try {
    const item = await api<InboxItem>("/api/inbox", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    return { ok: true, data: item };
  } catch (e) {
    return fail(e);
  }
}

// ---------- Plugins ----------

export async function savePluginAction(
  pluginId: string | null,
  payload: { name: string; description: string; code: string },
): Promise<ActionResult<Plugin>> {
  try {
    const path = pluginId ? `/api/plugins/${pluginId}` : "/api/plugins";
    const method = pluginId ? "PUT" : "POST";
    const result = await api<Plugin>(path, { method, body: JSON.stringify(payload) });
    revalidatePath("/dashboard/plugins");
    return { ok: true, data: result };
  } catch (e) {
    return fail(e);
  }
}

export async function deletePluginAction(pluginId: string): Promise<ActionResult> {
  try {
    await api(`/api/plugins/${pluginId}`, { method: "DELETE" });
    revalidatePath("/dashboard/plugins");
    return { ok: true, data: undefined };
  } catch (e) {
    return fail(e);
  }
}
