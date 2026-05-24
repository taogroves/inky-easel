import { headers } from "next/headers";
import { redirect } from "next/navigation";

import AccountActions from "@/components/AccountActions";
import { auth } from "@/lib/auth";
import { getDeveloperMode } from "@/lib/developer-mode";

export default async function AccountPage() {
  const session = await auth.api.getSession({ headers: await headers() }).catch(() => null);
  if (!session?.user) redirect("/sign-in");

  const developerMode = await getDeveloperMode(session.user.id);
  const name = session.user.name || session.user.email.split("@")[0];

  return (
    <div>
      <h1 className="font-display text-3xl">My account</h1>
      <p className="mt-1 text-sm text-ink-soft">{session.user.email}</p>
      <div className="mt-8">
        <AccountActions initialName={name} initialDeveloperMode={developerMode} />
      </div>
    </div>
  );
}
