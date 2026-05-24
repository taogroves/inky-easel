"use client";

import { useCallback, useEffect, useState } from "react";

import DisplayPreview from "@/components/DisplayPreview";

function bufferToBase64(buffer: ArrayBuffer): string {
  let binary = "";
  const bytes = new Uint8Array(buffer);
  for (let i = 0; i < bytes.byteLength; i++) binary += String.fromCharCode(bytes[i]);
  return btoa(binary);
}

type PreviewResult =
  | { ok: true; data: { buffer: ArrayBuffer; mime: string } }
  | { ok: false; error: string };

export default function FrameContentPreview({
  loadPreview,
  reloadKey,
  className = "",
}: {
  loadPreview: () => Promise<PreviewResult>;
  reloadKey?: string | number;
  className?: string;
}) {
  const [src, setSrc] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchPreview = useCallback(() => loadPreview(), [loadPreview]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setSrc(null);

    fetchPreview().then((result) => {
      if (cancelled) return;
      if (!result.ok) {
        setError(result.error);
        setLoading(false);
        return;
      }
      const encoded = bufferToBase64(result.data.buffer);
      setSrc(`data:${result.data.mime};base64,${encoded}`);
      setLoading(false);
    });

    return () => {
      cancelled = true;
    };
  }, [fetchPreview, reloadKey]);

  return (
    <div className={`mx-auto w-full max-w-xl ${className}`.trim()}>
      <DisplayPreview>
        {loading && (
          <div className="flex h-full items-center justify-center bg-white text-xs text-ink-soft">
            Loading preview...
          </div>
        )}
        {!loading && error && (
          <div className="flex h-full items-center justify-center bg-white px-4 text-center text-xs text-red-700">
            {error}
          </div>
        )}
        {!loading && src && (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={src} alt="Frame preview" className="h-full w-full object-contain bg-white" />
        )}
      </DisplayPreview>
    </div>
  );
}
