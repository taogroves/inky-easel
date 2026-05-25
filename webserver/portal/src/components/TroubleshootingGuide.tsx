"use client";

import { DOC_CATALOG, DOC_LINKS } from "@/lib/docs";

type Section = {
  id: string;
  title: string;
  summary: string;
  content: React.ReactNode;
};

const SECTIONS: Section[] = [
  {
    id: "getting-started",
    title: "Getting started",
    summary: "Create a frame, write the SD card, and confirm the first check-in.",
    content: (
      <>
        <ol className="list-decimal space-y-2 pl-5">
          <li>
            From the dashboard, click <strong>+ New frame</strong> and choose a handle, display name,
            location, and display type that matches your hardware.
          </li>
          <li>
            Complete the four-step <strong>SD setup</strong> wizard: location, Wi-Fi, write to card,
            verify connection.
          </li>
          <li>
            Insert the SD card into the frame and press <strong>reset</strong>.
          </li>
          <li>
            Open <strong>Schedule</strong> and add at least one item, then save.
          </li>
        </ol>
        <p className="mt-3 text-sm text-ink-soft">
          If you have not installed the one-time internal flash loader yet, copy{" "}
          <code className="rounded bg-ink/5 px-1">flash_loader_main.py</code> to the frame as{" "}
          <code className="rounded bg-ink/5 px-1">main.py</code> using Thonny before first use.
        </p>
      </>
    ),
  },
  {
    id: "connection-status",
    title: "Connection status",
    summary: "What awaiting first check-in, connected, and disconnected mean.",
    content: (
      <>
        <dl className="space-y-3 text-sm">
          <div>
            <dt className="font-medium">awaiting first check-in</dt>
            <dd className="mt-1 text-ink-soft">
              The frame has never polled successfully. Finish SD setup, confirm Wi-Fi, and reset the frame.
            </dd>
          </div>
          <div>
            <dt className="font-medium">connected</dt>
            <dd className="mt-1 text-ink-soft">
              The frame checked in within its expected window. Long sleep schedules may make check-ins look
              infrequent even when healthy.
            </dd>
          </div>
          <div>
            <dt className="font-medium">disconnected</dt>
            <dd className="mt-1 text-ink-soft">
              The frame missed its poll deadline plus a grace period. Check Wi-Fi, battery, and whether the
              API server is reachable.
            </dd>
          </div>
        </dl>
        <p className="mt-3 text-sm text-ink-soft">
          Use <strong>Last check-in</strong>, <strong>Next expected poll</strong>, and{" "}
          <strong>Disconnects after</strong> in the status panel to see timing details in your frame&apos;s
          timezone.
        </p>
      </>
    ),
  },
  {
    id: "wifi",
    title: "Changing Wi-Fi",
    summary: "Portal Configure, SD card refresh, or on-frame network buttons.",
    content: (
      <>
        <h4 className="font-medium">Configure (recommended for connected frames)</h4>
        <ol className="mt-2 list-decimal space-y-2 pl-5 text-sm">
          <li>Open <strong>Configure</strong> and click <strong>Start configuration mode</strong>.</li>
          <li>Reset the frame. Wait for <strong>CONFIGURATION MODE</strong> on the display.</li>
          <li>Edit networks, pick the <strong>Active</strong> network, then <strong>Save and exit</strong>.</li>
        </ol>
        <h4 className="mt-4 font-medium">SD setup</h4>
        <p className="mt-2 text-sm text-ink-soft">
          Rebuild the full SD bundle when replacing the card, refreshing firmware files, or setting up a frame
          that has never connected. Wi-Fi passwords are written only to the card, not stored on the server.
        </p>
        <h4 className="mt-4 font-medium">On-frame picker</h4>
        <p className="mt-2 text-sm text-ink-soft">
          When the display shows <strong>WI-FI UNAVAILABLE</strong>, press buttons A through E to switch among
          up to five stored networks, then the frame retries automatically.
        </p>
      </>
    ),
  },
  {
    id: "schedules",
    title: "Schedules",
    summary: "Relative loops vs calendar mode and common content issues.",
    content: (
      <>
        <p className="text-sm text-ink-soft">
          <strong>Relative</strong> mode loops items top to bottom using each item&apos;s sleep duration.{" "}
          <strong>Calendar</strong> mode shows items at fixed local times throughout the day.
        </p>
        <ul className="mt-3 list-disc space-y-2 pl-5 text-sm text-ink-soft">
          <li>Saving replaces the entire schedule and restarts from the first item.</li>
          <li>Weather needs a frame location — set it under <strong>Edit details</strong>.</li>
          <li>Empty inbox or missing plugins show text cards on the frame until fixed.</li>
          <li>Press reset on the frame to force an immediate poll after schedule changes.</li>
        </ul>
      </>
    ),
  },
  {
    id: "on-frame-errors",
    title: "On-frame error messages",
    summary: "What the frame display is telling you.",
    content: (
      <div className="overflow-x-auto">
        <table className="w-full min-w-[28rem] text-left text-sm">
          <thead>
            <tr className="border-b border-ink/10 text-xs uppercase tracking-wide text-ink-soft">
              <th className="py-2 pr-4 font-medium">Message</th>
              <th className="py-2 font-medium">What to do</th>
            </tr>
          </thead>
          <tbody className="text-ink-soft">
            <tr className="border-b border-ink/5">
              <td className="py-2 pr-4 align-top font-medium text-ink">BATTERY CRITICAL</td>
              <td className="py-2 align-top">Plug in USB power. Frame sleeps one hour without contacting the server.</td>
            </tr>
            <tr className="border-b border-ink/5">
              <td className="py-2 pr-4 align-top font-medium text-ink">WI-FI UNAVAILABLE</td>
              <td className="py-2 align-top">Press A–E to try another network, or update Wi-Fi via Configure.</td>
            </tr>
            <tr className="border-b border-ink/5">
              <td className="py-2 pr-4 align-top font-medium text-ink">CONFIGURATION MODE</td>
              <td className="py-2 align-top">Complete or cancel Configure in the portal. Keep the frame powered on.</td>
            </tr>
            <tr className="border-b border-ink/5">
              <td className="py-2 pr-4 align-top font-medium text-ink">Server unreachable</td>
              <td className="py-2 align-top">Check Wi-Fi, API server URL, and frame secret after rotation.</td>
            </tr>
            <tr className="border-b border-ink/5">
              <td className="py-2 pr-4 align-top font-medium text-ink">Bad server response</td>
              <td className="py-2 align-top">Press reset to retry. Persistent errors may indicate a server issue.</td>
            </tr>
            <tr className="border-b border-ink/5">
              <td className="py-2 pr-4 align-top font-medium text-ink">Firmware update failed</td>
              <td className="py-2 align-top">Retry on next poll, or re-run SD setup to refresh card files.</td>
            </tr>
            <tr>
              <td className="py-2 pr-4 align-top font-medium text-ink">Render failed</td>
              <td className="py-2 align-top">Check schedule items and custom plugins; press reset to retry.</td>
            </tr>
          </tbody>
        </table>
      </div>
    ),
  },
  {
    id: "common-fixes",
    title: "Common fixes",
    summary: "Quick checklist for the most frequent problems.",
    content: (
      <ul className="list-disc space-y-2 pl-5 text-sm text-ink-soft">
        <li>
          <strong>Never connected:</strong> SD card inserted, FAT32 formatted, Wi-Fi correct, frame reset,
          API reachable from the LAN (not localhost).
        </li>
        <li>
          <strong>Was connected, now disconnected:</strong> Router or password change, low battery, or server
          downtime.
        </li>
        <li>
          <strong>Direct SD write unavailable:</strong> Use ZIP download in Chrome/Edge/Opera alternatives or
          copy files manually.
        </li>
        <li>
          <strong>Verify step timed out:</strong> Press reset and retry; confirm the server URL in the bundle
          points at the API, not the portal.
        </li>
        <li>
          <strong>Wrong content:</strong> Save the schedule, set location for weather, reset the frame to poll
          immediately.
        </li>
        <li>
          <strong>Configure stuck:</strong> Cancel, reset the frame, and start configuration mode again while
          keeping it powered.
        </li>
      </ul>
    ),
  },
];

export default function TroubleshootingGuide() {
  return (
    <div className="space-y-3">
      {SECTIONS.map((section) => (
        <details
          key={section.id}
          id={section.id}
          className="group rounded-lg border border-ink/15 bg-white shadow-sm open:shadow-md"
        >
          <summary className="cursor-pointer list-none px-5 py-4 marker:content-none [&::-webkit-details-marker]:hidden">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="font-display text-lg">{section.title}</h2>
                <p className="mt-1 text-sm text-ink-soft">{section.summary}</p>
              </div>
              <span
                className="mt-1 shrink-0 text-ink-soft transition-transform group-open:rotate-180"
                aria-hidden="true"
              >
                ▾
              </span>
            </div>
          </summary>
          <div className="border-t border-ink/10 px-5 pb-5 pt-4">{section.content}</div>
        </details>
      ))}

      <section className="card mt-8">
        <h2 className="font-display text-xl">Full documentation</h2>
        <p className="mt-2 max-w-prose text-sm text-ink-soft">
          This page is a quick overview. For step-by-step guides, Wi-Fi procedures, schedule details, and
          developer options, see the markdown documentation in the repository.
        </p>
        <ul className="mt-4 space-y-2">
          {DOC_CATALOG.map((doc) => (
            <li key={doc.key}>
              <a
                href={DOC_LINKS[doc.key]}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm font-medium text-ink underline decoration-ink/30 underline-offset-2 hover:decoration-ink"
              >
                {doc.title}
              </a>
              <span className="text-sm text-ink-soft"> — {doc.description}</span>
            </li>
          ))}
        </ul>
        <p className="mt-4 text-xs text-ink-soft">
          Self-hosted installations also have these files at{" "}
          <code className="rounded bg-ink/5 px-1">docs/</code> in the project root. Set{" "}
          <code className="rounded bg-ink/5 px-1">NEXT_PUBLIC_DOCS_BASE_URL</code> to point links at your own
          doc host.
        </p>
      </section>
    </div>
  );
}
