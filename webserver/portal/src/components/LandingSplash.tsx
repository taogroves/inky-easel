import Link from "next/link";

import DisplayPreview from "@/components/DisplayPreview";

const features = [
  {
    title: "Schedules that run themselves",
    description:
      "Build a playlist of images, weather, news, comics, or custom plugins. Your frame picks it up and loops quietly on the wall.",
  },
  {
    title: "Send to any frame",
    description:
      "Share a note, photo, or link with friends by handle. Messages land in an inbox and show up on their display.",
  },
  {
    title: "Self-hosted, yours to keep",
    description:
      "Run the portal on your own server. Your frames, your content, your accounts — no subscription required.",
  },
];

const useCases = [
  {
    label: "Kitchen board",
    detail: "Morning weather, a family photo, and today’s calendar at a glance.",
  },
  {
    label: "Living room art",
    detail: "Cycle through your own images or curated feeds without a bright TV glow.",
  },
  {
    label: "Desk companion",
    detail: "News headlines, XKCD, or a custom plugin while you work.",
  },
  {
    label: "Gift a frame",
    detail: "Give someone a display their friends can message — a slow, thoughtful inbox.",
  },
];

export default function LandingSplash() {
  return (
    <div className="-mx-6 -mt-10">
      <section className="relative overflow-hidden border-b border-ink/10 bg-gradient-to-b from-white via-paper to-paper px-6 pb-16 pt-14 md:pb-24 md:pt-20">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 opacity-[0.35]"
          style={{
            backgroundImage:
              "radial-gradient(circle at 20% 20%, rgba(194,65,12,0.08), transparent 45%), radial-gradient(circle at 80% 0%, rgba(35,70,160,0.08), transparent 40%)",
          }}
        />
        <div className="relative mx-auto grid max-w-5xl items-center gap-12 lg:grid-cols-[1.05fr,0.95fr]">
          <div>
            <p className="text-xs font-medium uppercase tracking-[0.2em] text-accent">
              Self-hosted e-paper
            </p>
            <h1 className="mt-4 font-display text-4xl leading-[1.08] text-ink md:text-6xl">
              A calm display for the rooms you live in.
            </h1>
            <p className="mt-6 max-w-xl text-lg leading-relaxed text-ink-soft">
              Inky Easel connects Pimoroni Inky Frame displays to a portal you control.
              Schedule what appears on the wall, send messages between frames, and let
              low-power e-paper do its thing.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link href="/sign-up" className="btn-primary px-6 py-2.5 text-base">
                Create an account
              </Link>
              <Link href="/sign-in" className="btn-secondary px-6 py-2.5 text-base">
                Sign in
              </Link>
            </div>
            <ul className="mt-10 flex flex-wrap gap-2 text-xs text-ink-soft">
              {["Images & photos", "Weather", "News & RSS", "Custom plugins", "Frame inbox"].map(
                (item) => (
                  <li
                    key={item}
                    className="rounded-full border border-ink/10 bg-white/70 px-3 py-1 backdrop-blur-sm"
                  >
                    {item}
                  </li>
                ),
              )}
            </ul>
          </div>

          <div className="relative mx-auto w-full max-w-md lg:max-w-none">
            <div
              aria-hidden
              className="absolute -inset-4 rounded-[2rem] bg-ink/[0.03] blur-2xl"
            />
            <DisplayPreview className="relative shadow-2xl shadow-ink/10">
              <div className="flex h-full flex-col bg-white p-5 md:p-6">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="text-[10px] uppercase tracking-[0.18em] text-ink-soft">
                      Now showing
                    </p>
                    <p className="mt-1 font-display text-2xl text-ink">Tuesday forecast</p>
                  </div>
                  <span className="rounded-full bg-ink/5 px-2 py-1 text-[10px] font-medium text-ink-soft">
                    Schedule
                  </span>
                </div>
                <div className="mt-5 grid flex-1 grid-cols-3 gap-3">
                  <div className="rounded-md bg-[#2346a0]/15 p-3">
                    <p className="text-[10px] uppercase tracking-wide text-[#2346a0]">High</p>
                    <p className="mt-1 font-display text-3xl text-ink">68°</p>
                  </div>
                  <div className="rounded-md bg-[#28823c]/15 p-3">
                    <p className="text-[10px] uppercase tracking-wide text-[#28823c]">Low</p>
                    <p className="mt-1 font-display text-3xl text-ink">52°</p>
                  </div>
                  <div className="rounded-md bg-[#c81e1e]/10 p-3">
                    <p className="text-[10px] uppercase tracking-wide text-[#c81e1e]">Rain</p>
                    <p className="mt-1 font-display text-3xl text-ink">20%</p>
                  </div>
                </div>
                <div className="mt-4 flex items-center justify-between border-t border-ink/10 pt-4 text-xs text-ink-soft">
                  <span>Next: family photo</span>
                  <span>in 15 min</span>
                </div>
              </div>
            </DisplayPreview>
          </div>
        </div>
      </section>

      <section className="border-b border-ink/10 px-6 py-16 md:py-20">
        <div className="mx-auto max-w-5xl">
          <div className="max-w-2xl">
            <p className="text-xs font-medium uppercase tracking-[0.2em] text-accent">
              What it does
            </p>
            <h2 className="mt-3 font-display text-3xl text-ink md:text-4xl">
              One portal for every frame on your network.
            </h2>
            <p className="mt-4 text-ink-soft">
              Frames poll your server for the next thing to show. You manage schedules,
              plugins, and inboxes from the browser — the display stays simple and offline-friendly.
            </p>
          </div>
          <div className="mt-10 grid gap-5 md:grid-cols-3">
            {features.map((feature) => (
              <article key={feature.title} className="card bg-paper/50">
                <h3 className="font-display text-xl text-ink">{feature.title}</h3>
                <p className="mt-3 text-sm leading-relaxed text-ink-soft">{feature.description}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="px-6 py-16 md:py-20">
        <div className="mx-auto max-w-5xl">
          <div className="grid gap-10 lg:grid-cols-[0.9fr,1.1fr] lg:items-end">
            <div>
              <p className="text-xs font-medium uppercase tracking-[0.2em] text-accent">
                Use cases
              </p>
              <h2 className="mt-3 font-display text-3xl text-ink md:text-4xl">
                Made for rooms, not dashboards.
              </h2>
              <p className="mt-4 text-ink-soft">
                E-paper is readable in daylight, gentle at night, and always on without
                feeling loud. Inky Easel is built for displays you actually want to live with.
              </p>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              {useCases.map((useCase) => (
                <div
                  key={useCase.label}
                  className="rounded-lg border border-ink/10 bg-white px-4 py-4 shadow-sm"
                >
                  <p className="font-display text-lg text-ink">{useCase.label}</p>
                  <p className="mt-2 text-sm leading-relaxed text-ink-soft">{useCase.detail}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="mt-14 rounded-2xl border border-ink/10 bg-ink px-6 py-10 text-center text-paper md:px-10">
            <h2 className="font-display text-3xl md:text-4xl">Ready to hang something new?</h2>
            <p className="mx-auto mt-3 max-w-2xl text-sm leading-relaxed text-paper/75 md:text-base">
              Create an account, register a frame, and start scheduling content in minutes.
            </p>
            <div className="mt-6 flex flex-wrap justify-center gap-3">
              <Link
                href="/sign-up"
                className="inline-flex items-center justify-center rounded-md bg-paper px-5 py-2.5 text-sm font-medium text-ink transition-colors hover:bg-white"
              >
                Get started free
              </Link>
              <Link
                href="/sign-in"
                className="inline-flex items-center justify-center rounded-md border border-paper/25 px-5 py-2.5 text-sm font-medium text-paper transition-colors hover:bg-paper/10"
              >
                I already have an account
              </Link>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
