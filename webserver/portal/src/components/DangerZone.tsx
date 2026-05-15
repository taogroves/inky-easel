"use client";

import { useTransition } from "react";

import { deleteFrameAction } from "@/lib/actions";

export default function DangerZone({ frameId }: { frameId: string }) {
  const [pending, startTransition] = useTransition();

  return (
    <section className="mt-10 rounded-lg border border-red-300 bg-red-50 p-6">
      <h2 className="font-display text-xl text-red-900">Danger zone</h2>
      <p className="mt-2 text-sm text-red-800">
        Deleting this frame removes its schedule, inbox, and lifetime stats from the server.
        The physical device will start showing a "frame auth failed" screen the next time it polls.
      </p>
      <button
        className="btn-danger mt-4"
        disabled={pending}
        onClick={() => {
          if (!confirm("Really delete this frame?")) return;
          startTransition(() => deleteFrameAction(frameId));
        }}
      >
        {pending ? "Deleting..." : "Delete frame"}
      </button>
    </section>
  );
}
