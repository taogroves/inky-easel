"use client";

import { useEffect, useMemo, useState, useTransition } from "react";

import LocationPicker from "@/components/LocationPicker";
import { buildBundleAction, rotateFrameSecretAction, updateFrameAction } from "@/lib/actions";
import type { FrameWithSecret, SetupBundle } from "@/lib/api";
import { formatDateTime } from "@/lib/time";

type Step = "review" | "wifi" | "deploy" | "verify";

export default function SetupWizard({ frame: initialFrame }: { frame: FrameWithSecret }) {
  const [frame, setFrame] = useState(initialFrame);
  const [step, setStep] = useState<Step>("review");
  const [ssid, setSsid] = useState("");
  const [password, setPassword] = useState("");
  const [serverUrl, setServerUrl] = useState("");
  const [bundle, setBundle] = useState<SetupBundle | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();
  const fsAccessSupported = useMemo(
    () => typeof window !== "undefined" && "showDirectoryPicker" in window,
    [],
  );
  const [writeStatus, setWriteStatus] = useState<string | null>(null);
  const [verifyStatus, setVerifyStatus] = useState<"idle" | "polling" | "ok" | "stalled">("idle");
  const [verifyDetail, setVerifyDetail] = useState<string>("");

  useEffect(() => {
    try {
      const saved = window.localStorage.getItem("inky-easel.frameServerUrl");
      if (saved) {
        setServerUrl(saved);
        return;
      }
      const { hostname, protocol } = window.location;
      const canSuggestLanUrl = process.env.NODE_ENV === "development"
        && hostname
        && !["localhost", "127.0.0.1", "::1"].includes(hostname);
      if (canSuggestLanUrl) {
        setServerUrl(`${protocol}//${hostname}:8000`);
      }
    } catch {
      // localStorage may be unavailable in private browsing or hardened contexts.
    }
  }, []);

  async function buildBundle() {
    setError(null);
    const trimmedServerUrl = serverUrl.trim();
    if (trimmedServerUrl) {
      try {
        window.localStorage.setItem("inky-easel.frameServerUrl", trimmedServerUrl);
      } catch {
        // Non-critical convenience only.
      }
    }
    const result = await buildBundleAction(frame.id, ssid, password, trimmedServerUrl || undefined);
    if (!result.ok) {
      setError(result.error);
      return;
    }
    setBundle(result.data);
    setStep("deploy");
  }

  async function writeToCard() {
    if (!bundle) return;
    setWriteStatus(null);
    setError(null);
    try {
      const handle = await (window as any).showDirectoryPicker({ mode: "readwrite" });
      let written = 0;
      for (const [name, contents] of Object.entries(bundle.files)) {
        const file = await handle.getFileHandle(name, { create: true });
        const writable = await file.createWritable();
        await writable.write(contents);
        await writable.close();
        written += 1;
      }
      setWriteStatus(`Wrote ${written} files to the selected folder. Eject the card and insert it into the frame.`);
    } catch (e) {
      const msg = (e as Error).message || "Cancelled";
      setError(`Could not write to card: ${msg}`);
    }
  }

  async function downloadZip() {
    if (!bundle) return;
    const zipBlob = await buildZip(bundle.files);
    const url = URL.createObjectURL(zipBlob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `inky-easel-${frame.name}.zip`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  async function verifyConnection() {
    setVerifyStatus("polling");
    setVerifyDetail("Waiting for the frame to phone home...");
    const baseline = frame.last_seen_at;
    const deadline = Date.now() + 1000 * 60 * 5; // 5 minutes
    while (Date.now() < deadline) {
      await new Promise((r) => setTimeout(r, 6000));
      try {
        const resp = await fetch(`/dashboard/frames/${frame.id}/poll-status`, { cache: "no-store" });
        if (resp.ok) {
          const json = (await resp.json()) as { last_seen_at: string | null };
          if (json.last_seen_at && json.last_seen_at !== baseline) {
            setFrame({ ...frame, last_seen_at: json.last_seen_at });
            setVerifyStatus("ok");
            setVerifyDetail(`Frame connected at ${formatDateTime(json.last_seen_at, frame.timezone)}.`);
            return;
          }
        }
      } catch {
        // ignore transient errors during polling
      }
    }
    setVerifyStatus("stalled");
    setVerifyDetail("No check-in yet. Press the reset button on the frame and try again.");
  }

  async function rotateSecret() {
    startTransition(async () => {
      const result = await rotateFrameSecretAction(frame.id);
      if (result.ok) {
        setFrame(result.data);
        setBundle(null);
      }
    });
  }

  async function commitLocation(formData: FormData) {
    startTransition(async () => {
      const result = await updateFrameAction(frame.id, formData);
      if (result.ok) setFrame(result.data);
    });
  }

  return (
    <ol className="mt-8 space-y-6">
      <Step
        index={1}
        active={step === "review"}
        title="Confirm location and display"
        done={step !== "review"}
        onEnter={() => setStep("review")}
      >
        <form
          className="space-y-3"
          onSubmit={(e) => {
            e.preventDefault();
            commitLocation(new FormData(e.currentTarget));
            setStep("wifi");
          }}
        >
          <LocationPicker initialLatitude={frame.latitude} initialLongitude={frame.longitude} initialTimezone={frame.timezone} />
          <button type="submit" className="btn-primary">Continue &rarr;</button>
        </form>
      </Step>

      <Step
        index={2}
        active={step === "wifi"}
        title="Wi-Fi credentials"
        done={step === "deploy" || step === "verify"}
        onEnter={() => setStep("wifi")}
      >
        <div className="space-y-3">
          <p className="mt-2 max-w-prose text-sm text-ink-soft">
            Enter your Wi-Fi network name and password. This lets your frame access the internet.
          </p>
          <div>
            <label className="label" htmlFor="ssid">Network name</label>
            <input id="ssid" className="input" value={ssid} onChange={(e) => setSsid(e.target.value)} placeholder="MyHomeNet" />
          </div>
          <div>
            <label className="label" htmlFor="psk">Password</label>
            <input id="psk" className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
            <p className="mt-1 text-xs text-ink-soft">
              Stored only on the SD card (locally on the frame) as <code>secrets.py</code>. Not stored on the server.
            </p>
          </div>
          <div>
            <label className="label" htmlFor="server-url">Frame server URL (Optional)</label>
            <input
              id="server-url"
              className="input"
              type="url"
              value={serverUrl}
              onChange={(e) => setServerUrl(e.target.value)}
              placeholder="http://192.168.1.42:8000"
            />
            <p className="mt-1 text-xs text-ink-soft">
              Leave blank unless you know what you're doing. For local development, use the server&apos;s LAN IP and API port, not <code>localhost</code>.
            </p>
          </div>
          {error && <p className="text-sm text-red-700">{error}</p>}
          <button
            type="button"
            className="btn-primary"
            disabled={!ssid || !password}
            onClick={() => buildBundle()}
          >
            Build SD card bundle &rarr;
          </button>
        </div>
      </Step>

      <Step
        index={3}
        active={step === "deploy"}
        title="Write to the SD card"
        done={step === "verify"}
        onEnter={() => bundle && setStep("deploy")}
      >
        {!bundle ? (
          <p className="text-sm text-ink-soft">Finish the previous step first.</p>
        ) : (
          <div className="space-y-3">
            <p className="text-sm text-ink-soft">
              This bundle configures the frame to communicate and display content.
            </p>
            {/* <p className="text-sm text-ink-soft">
              On a new frame, first copy <code>flash_loader_main.py</code> to internal
              flash as <code>main.py</code>. After that one-time step, future setup
              bundles only need to be written to the SD card.
            </p> */}
            <p className="text-sm text-ink-soft">
              Insert a FAT32-formatted microSD card into your computer. Then either:
            </p>
            <ul className="ml-5 list-disc text-sm text-ink-soft">
              <li>
                <strong>Recommended (Chrome / Edge / Opera):</strong> click "Write directly" and
                pick the SD card&apos;s root folder when prompted.
              </li>
              <li>
                Otherwise download the bundle and copy every file inside it to the SD card root.
              </li>
            </ul>
            <div className="flex flex-wrap gap-2">
              <button type="button" className="btn-primary" disabled={!fsAccessSupported} onClick={writeToCard}>
                {fsAccessSupported ? "Write directly to SD card" : "Direct write unsupported in this browser"}
              </button>
              <button type="button" className="btn-secondary" onClick={downloadZip}>
                Download bundle as ZIP
              </button>
              <button type="button" className="btn-secondary" onClick={rotateSecret} disabled={pending}>
                {pending ? "Rotating..." : "Regenerate frame secret"}
              </button>
            </div>
            {writeStatus && <p className="text-sm text-emerald-800">{writeStatus}</p>}
            {error && <p className="text-sm text-red-700">{error}</p>}
            <details className="rounded border border-ink/10 bg-ink/5 p-3 text-xs">
              <summary className="cursor-pointer">Preview generated files</summary>
              <ul className="mt-2 list-disc pl-5">
                {Object.entries(bundle.files).map(([name, content]) => (
                  <li key={name}>
                    <span className="font-mono">{name}</span>
                    <pre className="mt-1 max-h-40 overflow-auto rounded bg-white p-2 text-[10px] leading-snug">{content.slice(0, 800)}{content.length > 800 ? "\n... (truncated)" : ""}</pre>
                  </li>
                ))}
              </ul>
            </details>
            <button type="button" className="btn-primary" onClick={() => setStep("verify")}>
              Done copying &mdash; verify connection &rarr;
            </button>
          </div>
        )}
      </Step>

      <Step index={4} active={step === "verify"} title="Verify the frame connects" done={false} onEnter={() => setStep("verify")}>
        <p className="text-sm text-ink-soft">
          Insert the SD card into your Inky Frame, then tap the reset button. The frame will wake up, 
          phone home, and we&apos;ll show a confirmation here if it connects successfully.
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <button type="button" className="btn-primary" onClick={verifyConnection} disabled={verifyStatus === "polling"}>
            {verifyStatus === "polling" ? "Listening..." : "Start verification"}
          </button>
          {verifyStatus === "ok" && (
            <span className="inline-flex items-center gap-2 rounded bg-emerald-100 px-3 py-1 text-sm text-emerald-800">
              <span className="h-2 w-2 rounded-full bg-emerald-600" /> Connected
            </span>
          )}
          {verifyStatus === "stalled" && (
            <span className="inline-flex items-center gap-2 rounded bg-amber-100 px-3 py-1 text-sm text-amber-800">
              <span className="h-2 w-2 rounded-full bg-amber-500" /> Still waiting
            </span>
          )}
        </div>
        {verifyDetail && <p className="mt-2 text-xs text-ink-soft">{verifyDetail}</p>}
      </Step>
    </ol>
  );
}

function Step({
  index,
  title,
  active,
  done,
  onEnter,
  children,
}: {
  index: number;
  title: string;
  active: boolean;
  done: boolean;
  onEnter: () => void;
  children: React.ReactNode;
}) {
  return (
    <li className={`card transition ${active ? "border-ink ring-1 ring-ink/30" : ""}`}>
      <button
        type="button"
        onClick={onEnter}
        className="flex w-full items-baseline gap-3 text-left"
      >
        <span className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-semibold ${done ? "bg-emerald-600 text-white" : active ? "bg-ink text-paper" : "bg-ink/10 text-ink-soft"}`}>
          {done ? "" : index}
        </span>
        <span className="font-display text-lg">{title}</span>
      </button>
      {active && <div className="mt-4">{children}</div>}
    </li>
  );
}

// ---------- Minimal ZIP writer (store-only, no compression) ----------

function crc32(bytes: Uint8Array): number {
  let c = 0xffffffff;
  for (let i = 0; i < bytes.length; i++) {
    c = c ^ bytes[i];
    for (let k = 0; k < 8; k++) {
      c = (c >>> 1) ^ (0xedb88320 & -(c & 1));
    }
  }
  return (c ^ 0xffffffff) >>> 0;
}

function dosTime(d = new Date()): { time: number; date: number } {
  const time = ((d.getHours() & 0x1f) << 11) | ((d.getMinutes() & 0x3f) << 5) | ((d.getSeconds() >> 1) & 0x1f);
  const date = (((d.getFullYear() - 1980) & 0x7f) << 9) | (((d.getMonth() + 1) & 0x0f) << 5) | (d.getDate() & 0x1f);
  return { time, date };
}

async function buildZip(files: Record<string, string>): Promise<Blob> {
  const encoder = new TextEncoder();
  const parts: BlobPart[] = [];
  const central: Uint8Array[] = [];
  let offset = 0;

  for (const [name, contents] of Object.entries(files)) {
    const data = encoder.encode(contents);
    const nameBytes = encoder.encode(name);
    const { time, date } = dosTime();
    const crc = crc32(data);

    const local = new ArrayBuffer(30 + nameBytes.length);
    const lv = new DataView(local);
    lv.setUint32(0, 0x04034b50, true);
    lv.setUint16(4, 20, true);
    lv.setUint16(6, 0, true);
    lv.setUint16(8, 0, true); // store
    lv.setUint16(10, time, true);
    lv.setUint16(12, date, true);
    lv.setUint32(14, crc, true);
    lv.setUint32(18, data.length, true);
    lv.setUint32(22, data.length, true);
    lv.setUint16(26, nameBytes.length, true);
    lv.setUint16(28, 0, true);
    const localHeader = new Uint8Array(local);
    localHeader.set(nameBytes, 30);

    parts.push(localHeader, data);

    const cdir = new ArrayBuffer(46 + nameBytes.length);
    const cv = new DataView(cdir);
    cv.setUint32(0, 0x02014b50, true);
    cv.setUint16(4, 20, true);
    cv.setUint16(6, 20, true);
    cv.setUint16(8, 0, true);
    cv.setUint16(10, 0, true);
    cv.setUint16(12, time, true);
    cv.setUint16(14, date, true);
    cv.setUint32(16, crc, true);
    cv.setUint32(20, data.length, true);
    cv.setUint32(24, data.length, true);
    cv.setUint16(28, nameBytes.length, true);
    cv.setUint16(30, 0, true);
    cv.setUint16(32, 0, true);
    cv.setUint16(34, 0, true);
    cv.setUint16(36, 0, true);
    cv.setUint32(38, 0, true);
    cv.setUint32(42, offset, true);
    const cdirEntry = new Uint8Array(cdir);
    cdirEntry.set(nameBytes, 46);
    central.push(cdirEntry);

    offset += localHeader.length + data.length;
  }

  const centralSize = central.reduce((a, b) => a + b.length, 0);
  const centralOffset = offset;
  for (const c of central) parts.push(c as BlobPart);
  offset += centralSize;

  const eocd = new ArrayBuffer(22);
  const ev = new DataView(eocd);
  ev.setUint32(0, 0x06054b50, true);
  ev.setUint16(4, 0, true);
  ev.setUint16(6, 0, true);
  ev.setUint16(8, central.length, true);
  ev.setUint16(10, central.length, true);
  ev.setUint32(12, centralSize, true);
  ev.setUint32(16, centralOffset, true);
  ev.setUint16(20, 0, true);
  parts.push(new Uint8Array(eocd));

  return new Blob(parts, { type: "application/zip" });
}
