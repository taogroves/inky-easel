"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { signIn } from "@/lib/auth-client";

export default function SignInPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setPending(true);
    setError(null);
    const result = await signIn.email({ email, password });
    setPending(false);
    if (result.error) {
      setError(result.error.message ?? "Sign in failed");
      return;
    }
    router.replace("/dashboard");
    router.refresh();
  }

  return (
    <div className="mx-auto max-w-md">
      <h1 className="font-display text-3xl">Sign in</h1>
      <p className="mt-2 text-sm text-ink-soft">Welcome back.</p>
      <form onSubmit={onSubmit} className="mt-6 space-y-4 card">
        <div>
          <label className="label" htmlFor="email">Email</label>
          <input id="email" className="input" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>
        <div>
          <label className="label" htmlFor="password">Password</label>
          <input id="password" className="input" type="password" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} />
        </div>
        {error && <p className="text-sm text-red-700">{error}</p>}
        <button className="btn-primary w-full" type="submit" disabled={pending}>
          {pending ? "Signing in..." : "Sign in"}
        </button>
        <p className="text-center text-xs text-ink-soft">
          Need an account? <a className="underline" href="/sign-up">Create one</a>.
        </p>
      </form>
    </div>
  );
}
