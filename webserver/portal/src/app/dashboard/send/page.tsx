import Link from "next/link";

import SendForm from "@/components/SendForm";

export default function SendPage() {
  return (
    <div className="mx-auto max-w-xl">
      <Link href="/dashboard" className="text-xs uppercase tracking-wide text-ink-soft hover:underline">
        &larr; Back to dashboard
      </Link>
      <h1 className="mt-3 font-display text-3xl">Send to a frame</h1>
      <p className="mt-2 text-sm text-ink-soft">
        Type the recipient&apos;s frame handle. They&apos;ll see your message the next
        time their schedule reaches an "inbox" item.
      </p>
      <SendForm />
    </div>
  );
}
