import Link from "next/link";

export default function NotFound() {
  return (
    <div className="text-center">
      <h1 className="font-display text-4xl">Not found</h1>
      <p className="mt-2 text-sm text-ink-soft">That page doesn&apos;t exist (or isn&apos;t yours).</p>
      <Link href="/dashboard" className="btn-primary mt-6 inline-flex">Back to dashboard</Link>
    </div>
  );
}
