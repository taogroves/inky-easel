"use client";

import { useRouter } from "next/navigation";
import { useTransition } from "react";

import { signOut } from "@/lib/auth-client";

export default function SignOutButton() {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  return (
    <button
      type="button"
      className="btn-secondary"
      disabled={pending}
      onClick={() =>
        startTransition(async () => {
          await signOut();
          router.replace("/");
          router.refresh();
        })
      }
    >
      {pending ? "Signing out..." : "Sign out"}
    </button>
  );
}
