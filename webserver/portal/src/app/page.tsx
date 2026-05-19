import Link from "next/link";
import { redirect } from "next/navigation";
import { headers } from "next/headers";

import { auth } from "@/lib/auth";

export default async function HomePage() {
  const session = await auth.api.getSession({ headers: await headers() }).catch(() => null);
  if (session?.user) redirect("/dashboard");

  return (
    <div className="grid gap-12 md:grid-cols-[1.2fr,1fr] items-center">
      <section>
        <h1 className="font-display text-4xl md:text-5xl leading-tight text-ink">
          A calm portal for your e-paper picture frame.
        </h1>
        <p className="mt-6 max-w-prose text-lg text-ink-soft">
          Schedule images, weather, news, XKCD, or your own MicroPython plugins.
          Send notes and photos to your friends&apos; frames. Set it once and let it
          loop quietly on the wall.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link href="/sign-up" className="btn-primary">Create an account</Link>
          <Link href="/sign-in" className="btn-secondary">I already have one</Link>
        </div>
      </section>
      <aside className="card">
        <h2 className="font-display text-2xl">How it works</h2>
        <ol className="mt-4 space-y-3 text-sm text-ink-soft">
          <li><span className="font-semibold text-ink">1.</span> Install the one-time flash loader on your Inky Frame.</li>
          <li><span className="font-semibold text-ink">2.</span> Plug a microSD card into your computer.</li>
          <li><span className="font-semibold text-ink">3.</span> Run the setup wizard to write your Wi-Fi, location, and a frame ID.</li>
          <li><span className="font-semibold text-ink">4.</span> Insert the card in your Inky Frame.</li>
          <li><span className="font-semibold text-ink">5.</span> Build a schedule and watch it loop forever.</li>
        </ol>
      </aside>
    </div>
  );
}
