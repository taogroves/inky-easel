"use client";

import { useState, useTransition } from "react";

import { sendMessageAction } from "@/lib/actions";

async function fileToBase64(file: File): Promise<string> {
  const buffer = await file.arrayBuffer();
  let binary = "";
  const bytes = new Uint8Array(buffer);
  for (let i = 0; i < bytes.byteLength; i++) binary += String.fromCharCode(bytes[i]);
  return btoa(binary);
}

export default function SendForm() {
  const [recipient, setRecipient] = useState("");
  const [kind, setKind] = useState<"text" | "image">("text");
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [senderLabel, setSenderLabel] = useState("");
  const [inboxPassword, setInboxPassword] = useState("");
  const [pending, startTransition] = useTransition();
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    setMessage(null);
    setError(null);
    startTransition(async () => {
      const payload: Parameters<typeof sendMessageAction>[0] = {
        recipient_frame_name: recipient.trim().toLowerCase(),
        kind,
        sender_label: senderLabel || undefined,
        inbox_password: inboxPassword || undefined,
      };
      if (kind === "text") {
        payload.text_body = text;
      } else if (file) {
        payload.image_base64 = await fileToBase64(file);
        payload.image_mime = file.type || "image/jpeg";
      } else {
        setError("Choose an image first.");
        return;
      }
      const result = await sendMessageAction(payload);
      if (!result.ok) {
        setError(result.error);
        return;
      }
      setMessage("Sent!");
      setText("");
      setFile(null);
      setInboxPassword("");
    });
  }

  return (
    <form onSubmit={submit} className="card mt-6 space-y-4">
      <div>
        <label className="label" htmlFor="to">Recipient handle</label>
        <input id="to" className="input" required value={recipient} onChange={(e) => setRecipient(e.target.value)} placeholder="kitchen-frame" />
      </div>
      <div>
        <label className="label" htmlFor="sender">From (optional)</label>
        <input id="sender" className="input" value={senderLabel} onChange={(e) => setSenderLabel(e.target.value)} placeholder="Defaults to your display name" />
      </div>
      <div>
        <label className="label" htmlFor="inbox-password">Inbox password (if needed)</label>
        <input
          id="inbox-password"
          className="input"
          value={inboxPassword}
          onChange={(e) => setInboxPassword(e.target.value)}
          placeholder="Ask your friend for this"
        />
      </div>
      <div className="flex gap-3 text-sm">
        <label className="inline-flex items-center gap-2">
          <input type="radio" name="kind" checked={kind === "text"} onChange={() => setKind("text")} /> Text
        </label>
        <label className="inline-flex items-center gap-2">
          <input type="radio" name="kind" checked={kind === "image"} onChange={() => setKind("image")} /> Image
        </label>
      </div>
      {kind === "text" ? (
        <div>
          <label className="label" htmlFor="text">Message</label>
          <textarea id="text" className="input min-h-[120px]" required value={text} onChange={(e) => setText(e.target.value)} />
        </div>
      ) : (
        <div>
          <label className="label" htmlFor="image">Image (jpg/png up to 5 MB)</label>
          <input
            id="image"
            type="file"
            accept="image/jpeg,image/png"
            className="input"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
          {file && <p className="mt-1 text-xs text-ink-soft">Selected: {file.name} ({Math.round(file.size / 1024)} KB). It will be resized for the recipient frame.</p>}
        </div>
      )}
      {error && <p className="text-sm text-red-700">{error}</p>}
      {message && <p className="text-sm text-emerald-700">{message}</p>}
      <button type="submit" className="btn-primary w-full" disabled={pending}>
        {pending ? "Sending..." : "Send"}
      </button>
    </form>
  );
}
