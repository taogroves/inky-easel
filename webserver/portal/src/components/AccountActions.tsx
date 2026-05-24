"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import { authClient, signOut } from "@/lib/auth-client";
import { updateAccountAction } from "@/lib/actions";

export default function AccountActions({
  initialName,
  initialDeveloperMode,
}: {
  initialName: string;
  initialDeveloperMode: boolean;
}) {
  const router = useRouter();
  const [name, setName] = useState(initialName);
  const [developerMode, setDeveloperMode] = useState(initialDeveloperMode);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [password, setPassword] = useState("");
  const [pending, startTransition] = useTransition();

  function save() {
    const formData = new FormData();
    formData.set("name", name);
    if (developerMode) formData.set("developerMode", "on");

    startTransition(async () => {
      setError(null);
      setMessage(null);
      const result = await updateAccountAction(formData);
      if (!result.ok) {
        setError(result.error);
        return;
      }
      setMessage("Account updated.");
      router.refresh();
    });
  }

  function signOutAndLeave() {
    startTransition(async () => {
      await signOut();
      router.replace("/");
      router.refresh();
    });
  }

  function deleteAccount() {
    if (!window.confirm("Delete your account and all frames, plugins, schedules, and inbox items? This cannot be undone.")) return;
    startTransition(async () => {
      setError(null);
      const result = await authClient.deleteUser({ password: password || undefined, callbackURL: "/" });
      if (result.error) {
        setError(result.error.message || "Could not delete account.");
        return;
      }
      router.replace("/");
      router.refresh();
    });
  }

  return (
    <div className="space-y-6">
      <section className="card">
        <h2 className="font-display text-xl">Profile</h2>
        <div className="mt-4 space-y-4">
          <div>
            <label className="label" htmlFor="account-name">Username</label>
            <input id="account-name" className="input" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <label className="flex items-start gap-3 rounded-md border border-ink/10 p-3 text-sm">
            <input
              className="mt-1"
              type="checkbox"
              checked={developerMode}
              onChange={(e) => setDeveloperMode(e.target.checked)}
            />
            <span>
              <span className="block font-medium">Developer mode</span>
              <span className="block text-ink-soft">Show server addresses, firmware controls, and file delivery details.</span>
            </span>
          </label>
          <div className="flex flex-wrap items-center gap-3">
            <button type="button" className="btn-primary" disabled={pending} onClick={save}>
              {pending ? "Saving..." : "Save changes"}
            </button>
            {message ? <span className="text-sm text-emerald-800">{message}</span> : null}
          </div>
          {error ? <p className="text-sm text-red-700">{error}</p> : null}
        </div>
      </section>

      <section className="card">
        <h2 className="font-display text-xl">Account access</h2>
        <div className="mt-4 flex flex-wrap gap-2">
          <button type="button" className="btn-secondary" disabled={pending} onClick={signOutAndLeave}>
            {pending ? "Working..." : "Sign out"}
          </button>
        </div>
      </section>

      <section className="card border-red-700/20">
        <h2 className="font-display text-xl text-red-800">Delete account</h2>
        <p className="mt-2 text-sm text-ink-soft">
          This removes your account, frames, schedules, plugins, and inbox items.
        </p>
        <div className="mt-4 max-w-sm">
          <label className="label" htmlFor="delete-password">Password</label>
          <input
            id="delete-password"
            className="input"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        <button type="button" className="btn-danger mt-4" disabled={pending} onClick={deleteAccount}>
          Delete account
        </button>
      </section>
    </div>
  );
}
