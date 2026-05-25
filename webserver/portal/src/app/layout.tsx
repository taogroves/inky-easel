import type { Metadata } from "next";
import Link from "next/link";
import { headers } from "next/headers";

import { auth } from "@/lib/auth";
import "./globals.css";

export const metadata: Metadata = {
  title: "Easel",
  description: "A portal for battery-powered e-paper picture frames",
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const session = await auth.api.getSession({ headers: await headers() }).catch(() => null);
  const user = session?.user ?? null;
  const username = user ? user.name || user.email.split("@")[0] : null;

  return (
    <html lang="en">
      <body>
        <header className="border-b border-ink/15 bg-paper">
          <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
            <Link href="/" className="text-xl font-display font-semibold tracking-tight">
              Easel
            </Link>
            <nav className="flex items-center gap-4 text-sm">
              {user ? (
                <>
                  <Link href="/dashboard" className="hover:underline">Dashboard</Link>
                  <Link href="/dashboard/plugins" className="hover:underline">Plugins</Link>
                  <Link href="/dashboard/send" className="hover:underline">Send</Link>
                  <span className="hidden font-semibold sm:inline">{username}</span>
                  <Link href="/account" className="btn-secondary">My account</Link>
                </>
              ) : (
                <>
                  <Link href="/sign-in" className="hover:underline">Sign in</Link>
                  <Link href="/sign-up" className="btn-primary">Get started</Link>
                </>
              )}
            </nav>
          </div>
        </header>
        <main className="mx-auto max-w-5xl px-6 py-10">{children}</main>
        <footer className="mx-auto max-w-5xl px-6 py-10 text-center text-xs text-ink-soft">
          A schedule-driven e-paper portal.
        </footer>
      </body>
    </html>
  );
}
