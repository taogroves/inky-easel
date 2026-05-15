"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { signUp } from "@/lib/auth-client";

export default function SignUpPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setPending(true);
    setError(null);
    const result = await signUp.email({ name, email, password });
    setPending(false);
    if (result.error) {
      setError(result.error.message ?? "Sign up failed");
      return;
    }
    router.replace("/dashboard");
    router.refresh();
  }

  return (
    <div className="mx-auto max-w-md">
      <h1 className="font-display text-3xl">Create your account</h1>
      <p className="mt-2 text-sm text-ink-soft">It takes about a minute.</p>
      <form onSubmit={onSubmit} className="mt-6 space-y-4 card">
        <div>
          <label className="label" htmlFor="name">Display name</label>
          <input id="name" className="input" required value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div>
          <label className="label" htmlFor="email">Email</label>
          <input id="email" className="input" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>
        <div>
          <label className="label" htmlFor="password">Password</label>
          <input id="password" className="input" type="password" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} />
          <p className="mt-1 text-xs text-ink-soft">At least 8 characters.</p>
        </div>
        {error && <p className="text-sm text-red-700">{error}</p>}
        <button className="btn-primary w-full" type="submit" disabled={pending}>
          {pending ? "Creating..." : "Create account"}
        </button>
        <p className="text-center text-xs text-ink-soft">
          Already have one? <a className="underline" href="/sign-in">Sign in</a>.
        </p>
      </form>
    </div>
  );
}
