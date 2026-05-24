"use client";

import { useEffect, useMemo, useState } from "react";

import type {
  FirmwareRelease,
  FrameConfigurationDesired,
  FrameConfigurationSession,
  WifiCredential,
} from "@/lib/api";

type SavePayload = {
  config: FrameConfigurationDesired;
  firmware_release_id: string | null;
};

function blankCredential(): WifiCredential {
  return { ssid: "", password: "" };
}

function cleanCredentials(credentials: WifiCredential[]): WifiCredential[] {
  return credentials
    .map((item) => ({ ssid: item.ssid.trim(), password: item.password }))
    .filter((item) => item.ssid)
    .slice(0, 5);
}

export default function FrameConfigureClient({
  frameId,
  initialSession,
  developerMode,
}: {
  frameId: string;
  initialSession: FrameConfigurationSession;
  developerMode: boolean;
}) {
  const [session, setSession] = useState(initialSession);
  const [credentials, setCredentials] = useState<WifiCredential[]>([]);
  const [activeWifiIndex, setActiveWifiIndex] = useState(0);
  const [serverUrl, setServerUrl] = useState("");
  const [firmwareReleaseId, setFirmwareReleaseId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hydratedFromFrame, setHydratedFromFrame] = useState(false);

  const releases = session.releases;
  const canSave = useMemo(() => {
    const cleaned = cleanCredentials(credentials);
    const hasServerUrl = developerMode ? serverUrl.trim().length > 0 : Boolean(session.observed?.server_url || serverUrl.trim());
    return cleaned.length > 0 && activeWifiIndex < cleaned.length && hasServerUrl;
  }, [activeWifiIndex, credentials, developerMode, serverUrl, session.observed?.server_url]);

  useEffect(() => {
    if (!session.observed || hydratedFromFrame) return;
    setCredentials(session.observed.wifi_credentials.length ? session.observed.wifi_credentials : [blankCredential()]);
    setActiveWifiIndex(session.observed.active_wifi_index);
    setServerUrl(session.observed.server_url);
    setHydratedFromFrame(true);
  }, [hydratedFromFrame, session.observed]);

  useEffect(() => {
    if (!["pending", "entering", "connected", "applying", "error"].includes(session.state)) return;
    let cancelled = false;
    const id = window.setInterval(async () => {
      const next = await fetchSession();
      if (!cancelled && next) setSession(next);
    }, 3000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [session.state]);

  useEffect(() => {
    if (session.state !== "applied") return;
    setCredentials([]);
    setActiveWifiIndex(0);
    setFirmwareReleaseId("");
  }, [session.state]);

  async function fetchSession(): Promise<FrameConfigurationSession | null> {
    try {
      const resp = await fetch(`/dashboard/frames/${frameId}/configure/session`, { cache: "no-store" });
      if (!resp.ok) throw new Error("Could not refresh configuration state");
      return (await resp.json()) as FrameConfigurationSession;
    } catch (e) {
      setError((e as Error).message);
      return null;
    }
  }

  async function post(action: "start" | "save" | "cancel", payload?: SavePayload) {
    setBusy(true);
    setError(null);
    if (action === "start") {
      setHydratedFromFrame(false);
      setCredentials([]);
      setActiveWifiIndex(0);
      setServerUrl("");
      setFirmwareReleaseId("");
    }
    try {
      const resp = await fetch(`/dashboard/frames/${frameId}/configure/session`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action, payload }),
      });
      const json = await resp.json();
      if (!resp.ok) throw new Error(json.error ?? "Configuration request failed");
      setSession(json as FrameConfigurationSession);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function updateCredential(index: number, patch: Partial<WifiCredential>) {
    setCredentials((items) => items.map((item, i) => (i === index ? { ...item, ...patch } : item)));
  }

  function removeCredential(index: number) {
    setCredentials((items) => {
      const next = items.filter((_, i) => i !== index);
      setActiveWifiIndex(Math.max(0, Math.min(activeWifiIndex, next.length - 1)));
      return next.length ? next : [blankCredential()];
    });
  }

  function saveAndExit() {
    const cleaned = cleanCredentials(credentials);
    post("save", {
      config: {
        wifi_credentials: cleaned,
        active_wifi_index: Math.max(0, Math.min(activeWifiIndex, cleaned.length - 1)),
        server_url: (developerMode ? serverUrl : session.observed?.server_url || serverUrl).trim().replace(/\/+$/, ""),
      },
      firmware_release_id: developerMode ? firmwareReleaseId || null : null,
    });
  }

  return (
    <div className="mt-8 grid gap-6 lg:grid-cols-[1fr_1.2fr]">
      <section className="card">
        <h2 className="font-display text-xl">1. Start configuration mode</h2>
        <p className="mt-2 text-sm text-ink-soft">
          Start here, then press reset on the frame. When it checks in, it will keep polling every few seconds until this flow ends.
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          <button className="btn-primary" type="button" disabled={busy} onClick={() => post("start")}>
            {session.state === "pending" ? "Waiting..." : session.state === "entering" ? "Connecting..." : "Start configuration mode"}
          </button>
          <button className="btn-secondary" type="button" disabled={busy} onClick={() => post("cancel")}>
            Cancel
          </button>
        </div>
        <StatusBlock state={session.state} message={session.message} />
        {error ? <p className="mt-3 text-sm text-red-700">{error}</p> : null}
      </section>

      <section className="card">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="font-display text-xl">2. Edit frame settings</h2>
            <p className="mt-2 text-sm text-ink-soft">
              Values appear after the frame reports what is currently on its SD card.
            </p>
          </div>
          {developerMode && session.observed?.firmware_version ? (
            <code className="rounded bg-ink/5 px-2 py-1 text-xs">Firmware {session.observed.firmware_version}</code>
          ) : null}
        </div>

        {!session.observed && session.state !== "applied" ? (
          <p className="mt-5 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
            Waiting for the frame. Start configuration mode, then reset the frame manually.
          </p>
        ) : null}

        {session.state === "applied" ? (
          <p className="mt-5 rounded-md border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900">
            The frame confirmed the changes and rebooted. Credentials have been cleared from this page.
          </p>
        ) : (
          <div className="mt-5 space-y-5">
            {developerMode ? (
              <div>
                <label className="label" htmlFor="server-url">API server address</label>
                <input
                  id="server-url"
                  className="input"
                  type="url"
                  value={serverUrl}
                  onChange={(e) => setServerUrl(e.target.value)}
                  placeholder="https://your-server.example.com"
                />
                <p className="mt-1 text-xs text-red-800">
                  Changing this can strand the frame if the address is unreachable from its Wi-Fi network.
                </p>
              </div>
            ) : null}

            <div>
              <div className="mb-2 flex items-center justify-between gap-3">
                <h3 className="font-display text-lg">Wi-Fi networks</h3>
                <button
                  className="btn-secondary"
                  type="button"
                  disabled={credentials.length >= 5}
                  onClick={() => setCredentials([...credentials, blankCredential()])}
                >
                  Add network
                </button>
              </div>
              <div className="space-y-3">
                {(credentials.length ? credentials : [blankCredential()]).map((credential, index) => (
                  <div key={index} className="rounded-md border border-ink/10 p-3">
                    <div className="grid gap-3 md:grid-cols-[1fr_1fr_auto]">
                      <div>
                        <label className="label" htmlFor={`ssid-${index}`}>SSID</label>
                        <input
                          id={`ssid-${index}`}
                          className="input"
                          value={credential.ssid}
                          onChange={(e) => updateCredential(index, { ssid: e.target.value })}
                        />
                      </div>
                      <div>
                        <label className="label" htmlFor={`password-${index}`}>Password</label>
                        <input
                          id={`password-${index}`}
                          className="input"
                          type="password"
                          value={credential.password}
                          onChange={(e) => updateCredential(index, { password: e.target.value })}
                        />
                      </div>
                      <div className="flex items-end gap-2">
                        <label className="mb-2 flex items-center gap-2 text-sm">
                          <input
                            type="radio"
                            name="active-wifi"
                            checked={activeWifiIndex === index}
                            onChange={() => setActiveWifiIndex(index)}
                          />
                          Active
                        </label>
                        <button className="btn-secondary" type="button" onClick={() => removeCredential(index)}>
                          Remove
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {developerMode ? (
              <FirmwareSelector
                releases={releases}
                value={firmwareReleaseId}
                onChange={setFirmwareReleaseId}
              />
            ) : null}

            <div className="flex flex-wrap items-center gap-3 border-t border-ink/10 pt-5">
              <button className="btn-primary" type="button" disabled={!canSave || busy} onClick={saveAndExit}>
                Save and exit
              </button>
              {session.state === "applying" ? <span className="text-sm text-ink-soft">Waiting for final frame confirmation...</span> : null}
            </div>
          </div>
        )}
      </section>
    </div>
  );
}

function StatusBlock({
  state,
  message,
}: {
  state: FrameConfigurationSession["state"];
  message: string | null;
}) {
  const cls =
    state === "connected" || state === "applied"
      ? "bg-emerald-100 text-emerald-800"
      : state === "error"
        ? "bg-red-100 text-red-800"
        : state === "idle"
          ? "bg-ink/10 text-ink-soft"
          : "bg-amber-100 text-amber-900";
  const labels: Record<FrameConfigurationSession["state"], string> = {
    idle: "Idle",
    pending: "Waiting...",
    entering: "Connecting...",
    connected: "Connected",
    applying: "Saving...",
    applied: "Saved",
    error: "Error",
    cancelled: "Cancelled",
  };
  const help: Record<FrameConfigurationSession["state"], string> = {
    idle: "Start configuration mode, then reset the frame when prompted.",
    pending: "The portal is ready. Reset the frame so it can check in and receive the configuration-mode command.",
    entering: "The frame checked in and was told to enter configuration mode. Wait for its display to update and report back.",
    connected: "The frame is in configuration mode. Edit the settings, then save and exit when ready.",
    applying: "The frame is writing the new settings. Keep it powered on until it confirms.",
    applied: "The frame confirmed the changes and should reboot back into its schedule.",
    error: "The frame reported a problem. Check the message below, then cancel or restart configuration mode.",
    cancelled: "Configuration was cancelled. Restart the frame if it is still showing configuration mode.",
  };
  return (
    <div className="mt-4">
      <span className={`inline-flex rounded-full px-3 py-1 text-xs font-medium ${cls}`}>{labels[state]}</span>
      <p className="mt-2 text-sm text-ink-soft">{message || help[state]}</p>
      {message ? <p className="mt-1 text-xs text-ink-soft">{help[state]}</p> : null}
    </div>
  );
}

function FirmwareSelector({
  releases,
  value,
  onChange,
}: {
  releases: FirmwareRelease[];
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div>
      <label className="label" htmlFor="firmware-release">Firmware</label>
      <select id="firmware-release" className="input" value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">Leave installed firmware unchanged</option>
        {releases.map((release) => (
          <option key={release.id} value={release.id}>
            {release.version}{release.active ? " (active)" : ""}
          </option>
        ))}
      </select>
    </div>
  );
}
